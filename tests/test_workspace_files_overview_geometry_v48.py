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
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


def _dump_files_overview_harness(
    viewport_width: int,
    *,
    programmatic_window_width: int | None = None,
) -> str:
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import InvalidHandshake
    except ImportError:
        pytest.skip("websockets is required for deterministic Files geometry QA")
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for Files overview geometry QA")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    query = (
        f"?window_width={programmatic_window_width}"
        if programmatic_window_width is not None
        else ""
    )
    url = (
        f"http://127.0.0.1:{server.server_port}/tests/fixtures/"
        f"workspace_files_overview_v48_harness.html{query}"
    )
    profile = tempfile.mkdtemp(prefix="ce-files-overview-v48-")
    process = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-sandbox",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
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

        websocket = None
        connect_deadline = time.monotonic() + 30
        last_connect_error: BaseException | None = None
        while websocket is None:
            remaining = connect_deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    "Chrome DevTools WebSocket did not accept a connection within 30 seconds",
                ) from last_connect_error
            try:
                websocket = connect(
                    browser_endpoint,
                    origin="http://localhost",
                    open_timeout=min(5, remaining),
                )
            except (InvalidHandshake, OSError, TimeoutError) as exc:
                last_connect_error = exc
                if process.poll() is not None:
                    raise AssertionError(
                        f"Chrome exited before DevTools accepted a connection: {process.returncode}",
                    ) from exc
                time.sleep(min(0.25, max(remaining, 0)))

        with websocket:
            request_id = 0
            events: list[dict[str, object]] = []

            def cdp(
                method: str,
                params: dict[str, object] | None = None,
                *,
                session_id: str | None = None,
                timeout: float = 30,
            ) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                expected_id = request_id
                message: dict[str, object] = {
                    "id": expected_id,
                    "method": method,
                    "params": params or {},
                }
                if session_id is not None:
                    message["sessionId"] = session_id
                websocket.send(json.dumps(message))
                while True:
                    response = json.loads(websocket.recv(timeout=timeout))
                    if response.get("id") == expected_id:
                        return response
                    events.append(response)

            def wait_for_event(
                method: str,
                *,
                session_id: str | None = None,
            ) -> dict[str, object]:
                for index, event in enumerate(events):
                    if event.get("method") == method and (
                        session_id is None or event.get("sessionId") == session_id
                    ):
                        return events.pop(index)
                while True:
                    event = json.loads(websocket.recv(timeout=30))
                    if event.get("method") == method and (
                        session_id is None or event.get("sessionId") == session_id
                    ):
                        return event
                    events.append(event)

            targets = cdp("Target.getTargets")
            target_infos = targets.get("result", {}).get("targetInfos", [])
            page = next(
                item
                for item in target_infos
                if item.get("type") == "page" and item.get("url") == "about:blank"
            )
            attached = cdp(
                "Target.attachToTarget",
                {"targetId": page["targetId"], "flatten": True},
            )
            session_id = attached.get("result", {}).get("sessionId")
            assert isinstance(session_id, str), attached

            cdp("Page.enable", session_id=session_id)
            cdp("Runtime.enable", session_id=session_id)
            cdp(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": viewport_width,
                    "height": 900,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
                session_id=session_id,
            )
            navigation = cdp(
                "Page.navigate",
                {"url": url},
                session_id=session_id,
            )
            assert "error" not in navigation, navigation
            wait_for_event("Page.loadEventFired", session_id=session_id)
            result = cdp(
                "Runtime.evaluate",
                {
                    "expression": """
                      new Promise((resolve, reject) => {
                        const abort = window.setTimeout(
                          () => reject(new Error("files-overview-fixture-not-ready")),
                          30_000,
                        );
                        const finish = () => {
                          window.clearTimeout(abort);
                          resolve(document.documentElement.outerHTML);
                        };
                        if (document.body?.dataset.fixtureReady === "true") {
                          finish();
                          return;
                        }
                        const observer = new MutationObserver(() => {
                          if (document.body?.dataset.fixtureReady !== "true") return;
                          observer.disconnect();
                          finish();
                        });
                        observer.observe(document.body, {
                          attributes: true,
                          attributeFilter: ["data-fixture-ready"],
                        });
                      })
                    """,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
                session_id=session_id,
            )
            assert "error" not in result, result
            value = result.get("result", {}).get("result", {}).get("value")
            assert isinstance(value, str), result
            return value
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


@pytest.mark.parametrize(
    ("viewport_width", "programmatic_window_width", "expected_layout"),
    [
        (320, None, "one-column"),
        (390, None, "one-column"),
        (1280, 760, "two-plus-one"),
    ],
)
def test_files_semantic_overview_geometry_tracks_the_real_window_container(
    viewport_width: int,
    programmatic_window_width: int | None,
    expected_layout: str,
) -> None:
    html = _dump_files_overview_harness(
        viewport_width,
        programmatic_window_width=programmatic_window_width,
    )

    for marker in (
        'data-fixture-ready="true"',
        'data-fixture-semantic-overview="true"',
        'data-fixture-overview-cards="3"',
        'data-fixture-board-grid-present="false"',
        'data-fixture-measured-nodes="8"',
        'data-fixture-no-horizontal-overflow="true"',
        'data-fixture-overflow-failures=""',
    ):
        assert marker in html

    content_width_match = re.search(r'data-fixture-content-width="(\d+)"', html)
    assert content_width_match is not None
    content_width = int(content_width_match.group(1))

    if expected_layout == "one-column":
        assert content_width < 560
        assert 'data-fixture-one-column="true"' in html
        assert 'data-fixture-two-plus-one="false"' in html
        assert 'data-fixture-programmatic-window="false"' in html
    else:
        assert 560 <= content_width <= 819
        assert 'data-fixture-one-column="false"' in html
        assert 'data-fixture-two-plus-one="true"' in html
        assert 'data-fixture-programmatic-window="true"' in html
        assert f'data-fixture-programmatic-width="{programmatic_window_width}"' in html
