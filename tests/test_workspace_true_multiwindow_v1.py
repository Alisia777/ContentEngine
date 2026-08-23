from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import html as html_module
import re
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
PARENT_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "workspace_true_multiwindow_v1_harness.html"
CHILD_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "workspace_true_multiwindow_v1_child.html"
PARENT_FIXTURE = PARENT_FIXTURE_PATH.read_text(encoding="utf-8")
CHILD_FIXTURE = CHILD_FIXTURE_PATH.read_text(encoding="utf-8")


class _TrueMultiwindowHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if query.get("ce_window") == ["1"]:
            # The production URL builder still owns the requested URL.  The
            # focused probe substitutes only its response body so no account,
            # session, API, or business backend is required for browser QA.
            self.server.embedded_requests.append(self.path)  # type: ignore[attr-defined]
            payload = CHILD_FIXTURE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def _chrome_binary() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    ]
    return next((str(path) for path in candidates if path and Path(path).exists()), None)


def _run_true_multiwindow_probe() -> tuple[str, list[str]]:
    chrome = _chrome_binary()
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for true multiwindow runtime QA")

    handler = partial(_TrueMultiwindowHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.embedded_requests = []  # type: ignore[attr-defined]
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = (
        f"http://127.0.0.1:{server.server_port}/tests/fixtures/"
        "workspace_true_multiwindow_v1_harness.html"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="ce-true-multiwindow-v1-") as profile:
            result = subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--no-sandbox",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--run-all-compositor-stages-before-draw",
                    "--virtual-time-budget=30000",
                    "--window-size=1720,960",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=55,
                check=False,
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)

    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout, list(server.embedded_requests)  # type: ignore[attr-defined]


def _attribute(html: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}=([\"'])(?P<value>.*?)\1", html, re.DOTALL)
    return html_module.unescape(match.group("value")) if match else ""


def test_true_multiwindow_fixture_models_document_isolation_not_dom_cloning() -> None:
    assert PARENT_FIXTURE.count('id="workspace-content"') == 1
    assert 'iframe[data-ce-v4-window-surface]' in PARENT_FIXTURE
    assert "cloneNode" not in PARENT_FIXTURE
    assert ".innerHTML" not in PARENT_FIXTURE

    # Both live children intentionally use these same IDs.  This is valid only
    # because every surface owns an independent Document.
    for isolated_id in (
        "ce-window-live-form",
        "ce-window-live-input",
        "ce-window-live-submit",
        "ce-window-live-proof",
    ):
        assert CHILD_FIXTURE.count(f'id="{isolated_id}"') == 1
    assert 'data-ce-window-child="true"' not in PARENT_FIXTURE.lower()
    assert 'type: "contentengine:embedded-window"' in CHILD_FIXTURE
    assert 'window.parent.postMessage' in CHILD_FIXTURE


def test_two_live_same_origin_window_documents_survive_window_lifecycle() -> None:
    rendered, requests = _run_true_multiwindow_probe()
    error = _attribute(rendered, "data-fixture-true-multi-error")
    assert _attribute(rendered, "data-fixture-true-multi-ready") == "true", error or rendered[-4000:]
    assert _attribute(rendered, "data-fixture-true-multi-failed") == "false", error

    required_truths = (
        "data-fixture-true-multi-two-visible-shells",
        "data-fixture-true-multi-two-surfaces",
        "data-fixture-true-multi-both-surfaces-interactive",
        "data-fixture-true-multi-distinct-windows",
        "data-fixture-true-multi-distinct-documents",
        "data-fixture-true-multi-children-have-no-nested-desktop",
        "data-fixture-true-multi-same-origin",
        "data-fixture-true-multi-window-ids-bound",
        "data-fixture-true-multi-independent-routes",
        "data-fixture-true-multi-scoped-query",
        "data-fixture-true-multi-parent-ids-unique",
        "data-fixture-true-multi-parent-has-no-child-form",
        "data-fixture-true-multi-child-form-ids-isolated",
        "data-fixture-true-multi-forms-independent",
        "data-fixture-true-multi-both-children-running",
        "data-fixture-true-multi-child-focus-raises-shell",
        "data-fixture-true-multi-focus-preserves-children",
        "data-fixture-true-multi-drag-moves-shell",
        "data-fixture-true-multi-drag-preserves-children",
        "data-fixture-true-multi-minimize-keeps-children",
        "data-fixture-true-multi-restore-preserves-children",
        "data-fixture-true-multi-desktop-hides-shells",
        "data-fixture-true-multi-desktop-keeps-children",
        "data-fixture-true-multi-desktop-visible",
        "data-fixture-true-multi-final-parent-ids-unique",
    )
    failures = {
        marker: _attribute(rendered, marker)
        for marker in required_truths
        if _attribute(rendered, marker) != "true"
    }
    assert not failures, f"true multiwindow contract failures: {failures}; probe error: {error}"

    parsed_requests = [urlsplit(request) for request in requests]
    scoped_requests = [
        parsed
        for parsed in parsed_requests
        if parse_qs(parsed.query).get("ce_window") == ["1"]
    ]
    requested_ids = {
        parse_qs(parsed.query).get("ce_window_id", [""])[0]
        for parsed in scoped_requests
    }
    assert len(scoped_requests) >= 2
    assert len(requested_ids - {""}) == 2
    # URL fragments are intentionally client-side and therefore never reach
    # the HTTP handler.  The in-browser independent-routes marker above reads
    # both child locations directly and owns that part of the assertion.
    assert all(parsed.path.endswith("/index.html") for parsed in scoped_requests)
