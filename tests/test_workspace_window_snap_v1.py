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
CORE_PATH = ROOT / "web" / "app" / "workspace-os-v4.js"
CSS_PATH = ROOT / "web" / "app" / "workspace-os-v4.css"
PARENT_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "workspace_window_snap_v1_harness.html"
CHILD_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "workspace_window_snap_v1_child.html"
CORE = CORE_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")
PARENT_FIXTURE = PARENT_FIXTURE_PATH.read_text(encoding="utf-8")
CHILD_FIXTURE = CHILD_FIXTURE_PATH.read_text(encoding="utf-8")


class _WindowSnapHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        if query.get("ce_window") == ["1"]:
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


def _run_snap_probe() -> tuple[str, list[str]]:
    chrome = _chrome_binary()
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for window snap runtime QA")

    handler = partial(_WindowSnapHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.embedded_requests = []  # type: ignore[attr-defined]
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = (
        f"http://127.0.0.1:{server.server_port}/tests/fixtures/"
        "workspace_window_snap_v1_harness.html"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="ce-window-snap-v1-") as profile:
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
                    "--virtual-time-budget=45000",
                    "--window-size=1720,960",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=70,
                check=False,
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)

    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout, list(server.embedded_requests)  # type: ignore[attr-defined]


def _attribute(rendered: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}=([\"'])(?P<value>.*?)\1", rendered, re.DOTALL)
    return html_module.unescape(match.group("value")) if match else ""


def test_snap_contract_wires_force_zoom_edges_accessible_choice_and_resize_reflow() -> None:
    assert 'zoom.addEventListener("dblclick", (event) => {' in CORE
    assert "toggleWorkspaceWindowZoom(true, windowId);" in CORE
    assert 'else if (action === "zoom") handleWorkspaceWindowZoomClick(windowId);' in CORE
    assert "function clearWorkspaceWindowZoomClick(windowId)" in CORE
    assert "}, 260);" in CORE
    assert 'if (event.clientY <= rect.top + WINDOW_SNAP_EDGE) return "top";' in CORE
    assert 'if (event.clientX <= rect.left + WINDOW_SNAP_EDGE) return "left";' in CORE
    assert 'if (event.clientX >= rect.right - WINDOW_SNAP_EDGE) return "right";' in CORE
    assert 'applyWorkspaceSnap(drag.windowId, { count: 2, index: 0, slot: "left" });' in CORE
    assert 'applyWorkspaceSnap(drag.windowId, { count: 2, index: 1, slot: "right" });' in CORE
    assert "openWorkspaceSnapAssist(drag.windowId);" in CORE
    assert 'reduceWorkspaceWindow({ type: "resize", windowId, size: existingWindow.size });' not in CORE

    assert 'assist.setAttribute("role", "dialog");' in CORE
    assert 'assist.setAttribute("aria-modal", "false");' in CORE
    assert 'assist.setAttribute("aria-labelledby", "ce-v4-window-snap-assist-title");' in CORE
    assert '{ key: "full", label: "Полный экран", count: 1, enabled: true }' in CORE
    assert '{ key: "two", label: "2 окна", count: 2, enabled: canTileTwo }' in CORE
    assert '{ key: "three", label: "3 окна", count: 3, enabled: canTileThree }' in CORE
    assert "tileWorkspaceWindows(windowId, 2)" in CORE
    assert "tileWorkspaceWindows(windowId, 3)" in CORE

    assert "function reflowWorkspaceSnappedWindows()" in CORE
    assert "reflowWorkspaceSnappedWindows();" in CORE
    assert 'window.addEventListener("resize", handleWorkspaceResize, { passive: true });' in CORE
    assert "frame.src = createContentEngineEmbeddedWindowUrl" in CORE
    assert "runtime.windowSurfaces.set(windowRecord.windowId, frame);" in CORE
    assert 'surface.style.pointerEvents = visible ? "auto" : "none";' in CORE

    for selector in (
        ".ce-v4-window.is-snapped",
        ".ce-v4-window-snap-preview",
        ".ce-v4-window-snap-assist",
        ".ce-v4-window-snap-assist__choice",
    ):
        assert selector in CSS


def test_snap_fixture_uses_isolated_live_documents_not_cloned_forms() -> None:
    assert PARENT_FIXTURE.count('id="workspace-content"') == 1
    assert 'iframe[data-ce-v4-window-surface]' in PARENT_FIXTURE
    assert "cloneNode" not in PARENT_FIXTURE
    assert ".innerHTML" not in PARENT_FIXTURE
    assert CHILD_FIXTURE.count('id="ce-window-live-form"') == 1
    assert CHILD_FIXTURE.count('id="ce-window-live-input"') == 1
    assert 'window.parent.postMessage' in CHILD_FIXTURE


def test_green_zoom_edge_snap_two_three_layout_and_resize_keep_every_surface_live() -> None:
    rendered, requests = _run_snap_probe()
    error = _attribute(rendered, "data-fixture-snap-error")
    assert _attribute(rendered, "data-fixture-snap-ready") == "true", error or rendered[-5000:]
    assert _attribute(rendered, "data-fixture-snap-failed") == "false", error

    required_truths = (
        "data-fixture-snap-green-double-click-forces-zoom",
        "data-fixture-snap-zoom-preserves-surfaces",
        "data-fixture-snap-left-half",
        "data-fixture-snap-left-preserves-surfaces",
        "data-fixture-snap-right-half",
        "data-fixture-snap-right-preserves-surfaces",
        "data-fixture-snap-top-opens-accessible-chooser",
        "data-fixture-snap-two-layout-geometry",
        "data-fixture-snap-two-layout-all-surfaces-live",
        "data-fixture-snap-three-choice-available",
        "data-fixture-snap-three-layout-geometry",
        "data-fixture-snap-three-layout-all-surfaces-live",
        "data-fixture-snap-resize-reflows",
        "data-fixture-snap-resize-preserves-surface-identity",
        "data-fixture-snap-resize-keeps-all-interactive",
        "data-fixture-snap-all-sources-stable",
    )
    failures = {
        marker: _attribute(rendered, marker)
        for marker in required_truths
        if _attribute(rendered, marker) != "true"
    }
    assert not failures, f"window snap contract failures: {failures}; probe error: {error}"

    scoped_requests = [
        urlsplit(request)
        for request in requests
        if parse_qs(urlsplit(request).query).get("ce_window") == ["1"]
    ]
    requested_ids = {
        parse_qs(parsed.query).get("ce_window_id", [""])[0]
        for parsed in scoped_requests
    }
    assert len(scoped_requests) == 3
    assert len(requested_ids - {""}) == 3
    # A resize or layout change must not trigger another child navigation.
    assert all(parsed.path.endswith("/index.html") for parsed in scoped_requests)
