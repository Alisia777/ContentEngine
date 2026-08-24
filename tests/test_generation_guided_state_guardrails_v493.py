"""Runtime regressions for truthful state in the guided generation wizard.

The harness mirrors the live form's native SKU, product-name and brief
requirements, then verifies the guided adapter's cross-step and media rules.
"""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-os-v4-generation-guided.js"
HARNESS = ROOT / "tests" / "fixtures" / "workspace_generation_guided_state_v493_harness.html"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


def _chrome_path() -> str | None:
    candidates = (
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    )
    return next((str(path) for path in candidates if path and Path(path).exists()), None)


def test_generation_guided_state_harness_covers_the_reported_failure_boundaries() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    for observable in (
        "persistedLaunchClampsToProduct",
        "nameWithoutSkuIsRejected",
        "skuWithoutNameIsRejected",
        "emptyRealBriefIsRejected",
        "realWithoutMediaIsRejected",
        "mockWithoutMediaIsRejected",
        "mockExplicitlyCreatesNoVideo",
        "mockExplicitlyCreatesNoFile",
    ):
        assert observable in source
    assert "workspace-os-v4-generation-guided.js?fixture=v493-state-guardrails" in source
    assert "contentengine.desktop.v4.generation-guided.v2" in source


def test_generation_guided_restores_only_a_valid_step_and_tells_the_truth_about_mock() -> None:
    chrome = _chrome_path()
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for generation wizard runtime QA")

    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for deterministic generation wizard QA")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = (
        f"http://127.0.0.1:{server.server_port}/"
        f"{HARNESS.relative_to(ROOT).as_posix()}"
    )
    profile = tempfile.mkdtemp(prefix="ce-generation-guided-v493-")
    process = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            "--window-size=1280,900",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        browser_endpoint = ""
        assert process.stderr is not None
        for line in process.stderr:
            match = re.search(r"DevTools listening on (ws://\S+)", line)
            if match:
                browser_endpoint = match.group(1)
                break
        assert browser_endpoint, "Chrome DevTools endpoint did not become ready"
        port_match = re.search(r"ws://[^:/]+:(\d+)/", browser_endpoint)
        assert port_match is not None
        pages = json.load(
            urllib.request.urlopen(
                f"http://127.0.0.1:{int(port_match.group(1))}/json/list",
                timeout=5,
            )
        )
        page = next(
            item
            for item in pages
            if item.get("type") == "page" and item.get("url") == "about:blank"
        )

        with connect(
            page["webSocketDebuggerUrl"],
            origin="http://localhost",
            open_timeout=5,
        ) as websocket:
            request_id = 0
            events: list[dict[str, object]] = []

            def cdp(
                method: str,
                params: dict[str, object] | None = None,
                *,
                timeout: float = 30,
            ) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                expected_id = request_id
                websocket.send(json.dumps({
                    "id": expected_id,
                    "method": method,
                    "params": params or {},
                }))
                while True:
                    response = json.loads(websocket.recv(timeout=timeout))
                    if response.get("id") == expected_id:
                        return response
                    events.append(response)

            def wait_for_event(method: str) -> dict[str, object]:
                for index, event in enumerate(events):
                    if event.get("method") == method:
                        return events.pop(index)
                while True:
                    event = json.loads(websocket.recv(timeout=30))
                    if event.get("method") == method:
                        return event
                    events.append(event)

            cdp("Page.enable")
            cdp("Runtime.enable")
            navigation = cdp("Page.navigate", {"url": url})
            assert "error" not in navigation, navigation
            wait_for_event("Page.loadEventFired")
            result = cdp(
                "Runtime.evaluate",
                {
                    "expression": """
                      new Promise((resolve, reject) => {
                        const output = document.querySelector("#result");
                        if (!output) {
                          reject(new Error("generation-guided-result-missing"));
                          return;
                        }
                        let observer = null;
                        const abort = window.setTimeout(
                          () => reject(new Error("generation-guided-result-not-ready")),
                          30_000,
                        );
                        const finish = () => {
                          if (String(output.textContent || "").trim() === "WAIT") return;
                          observer?.disconnect();
                          window.clearTimeout(abort);
                          resolve(output.outerHTML);
                        };
                        if (String(output.textContent || "").trim() !== "WAIT") {
                          finish();
                          return;
                        }
                        observer = new MutationObserver(finish);
                        observer.observe(output, {
                          attributes: true,
                          childList: true,
                          characterData: true,
                          subtree: true,
                        });
                      })
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
            )
            assert "error" not in result, result
            assert "exceptionDetails" not in result.get("result", {}), result
            output = result.get("result", {}).get("result", {}).get("value")
            assert isinstance(output, str), result
            assert 'data-passed="true"' in output, output
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        shutil.rmtree(profile, ignore_errors=True)


def test_generation_guided_module_is_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for JavaScript syntax validation")

    subprocess.run(
        [node, "--check", str(MODULE)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_hidden_attribute_wins_over_field_display_rules_in_the_generation_form() -> None:
    """syncLegacyModelVisibility прячет легаси-поля атрибутом hidden, но
    .field { display:grid } возвращал их на экран мёртвыми: задизейбленный
    «Режим генерации *» («не открывается», 24.08) и вся «каша» наслоения форм
    в «Сценарии с нуля». UA-правило [hidden] слабее любого display —
    визуальный слой обязан закреплять победу hidden явно."""
    css = (MODULE.parent / "content-factory-visual-v2.css").read_text(encoding="utf-8")
    start = css.index("#mock-batch-form [hidden]")
    block = css[start : css.index("}", start)]
    assert ".ce-v4-generation-guided [hidden]" in block
    assert "display: none !important;" in block
