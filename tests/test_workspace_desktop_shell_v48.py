from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
STABILITY_CSS = (APP / "workspace-os-v4-stability.css").read_text(encoding="utf-8")
WINDOW_CONTRACT = (APP / "workspace-window-manager-contract.js").read_text(encoding="utf-8")
SPRITE_PATH = APP / "assets" / "workspace_dock_icon_sprite_v4_7_1.svg"
HARNESS = (ROOT / "tests" / "fixtures" / "workspace_os_v48_shell_harness.html").read_text(encoding="utf-8")
DOCK_RUNTIME_PROBE = HARNESS.replace(
    "</body>",
    """
    <script type="module">
      while (document.body.dataset.fixtureReady !== "true") {
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      const keyed = [...document.querySelectorAll("[data-ce-v4-dock-key]")];
      const keys = keyed.map((item) => item.dataset.ceV4DockKey);
      document.body.dataset.fixtureDockCanonicalKeys = keys.join(",");
      document.body.dataset.fixtureDockUniqueKeys = String(keys.length === 12 && new Set(keys).size === 12);

      let directChanges = 0;
      const directRoute = "#/workspace/board?project_id=11111111-1111-4111-8111-111111111111";
      const directListener = () => {
        directChanges += 1;
        if (window.location.hash === directRoute) {
          window.removeEventListener("hashchange", directListener);
          document.body.dataset.fixtureDockDirectNavigationCount = String(directChanges);
          document.body.dataset.fixtureDockDirectRoute = window.location.hash;
        }
      };
      window.addEventListener("hashchange", directListener, { once: false });
      document.querySelector('[data-ce-v4-dock-key="finder"]').click();
      window.addEventListener("hashchange", () => {
        const more = document.querySelector("[data-ce-v4-dock-more]");
        more.click();
        const overflowTarget = document.querySelector('[data-ce-v4-more-key="processes"]')
          || document.querySelector("[data-ce-v4-more-key]");
        const beforeOverflow = window.location.hash;
        let overflowChanges = 0;
        window.addEventListener("hashchange", () => {
          overflowChanges += 1;
          document.body.dataset.fixtureDockOverflowNavigationCount = String(overflowChanges);
          document.body.dataset.fixtureDockOverflowRoute = window.location.hash;
        });
        overflowTarget.click();
        document.body.dataset.fixtureDockOverflowDispatched = String(beforeOverflow !== window.location.hash);
        document.body.dataset.fixtureDockMountCount = String(document.querySelectorAll(".ce-v4-dock").length);
      }, { once: true });
    </script>
    </body>
    """,
)


EXPECTED_DOCK_SYMBOLS = {
    "ce-dock-finder",
    "ce-dock-results",
    "ce-dock-passports",
    "ce-dock-hypotheses",
    "ce-dock-research",
    "ce-dock-ai",
    "ce-dock-create",
    "ce-dock-review",
    "ce-dock-publish",
    "ce-dock-processes",
    "ce-dock-settings",
    "ce-dock-trash",
}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


class _DockProbeHandler(_QuietHandler):
    def do_GET(self) -> None:
        if self.path.partition("?")[0] == "/tests/fixtures/workspace_dock_shell_v491_runtime.html":
            payload = DOCK_RUNTIME_PROBE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()


def _dump_shell_harness(
    query: str = "",
    *,
    window_size: tuple[int, int] = (1280, 800),
    dock_probe: bool = False,
) -> str:
    candidates = [
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for shell runtime QA")
    handler = partial(_DockProbeHandler if dock_probe else _QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    suffix = f"?{query}" if query else ""
    fixture = "workspace_dock_shell_v491_runtime.html" if dock_probe else "workspace_os_v48_shell_harness.html"
    url = f"http://127.0.0.1:{server.server_port}/tests/fixtures/{fixture}{suffix}"
    try:
        with tempfile.TemporaryDirectory(prefix="ce-shell-v48-") as profile:
            result = subprocess.run(
                [
                    chrome,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    # The shell now imports the Dock and Notification contracts
                    # before activating a desktop object. Leave enough virtual
                    # time for that exact integration path under a loaded CI
                    # host; the fixture itself still owns the readiness markers.
                    "--virtual-time-budget=12000",
                    f"--window-size={window_size[0]},{window_size[1]}",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
                check=False,
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout


def _dump_exact_width_dock_probe(
    width: int,
    height: int,
    *,
    shell_query: str | None = None,
) -> str:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")
    candidates = [
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for exact Dock runtime QA")

    handler = partial(_DockProbeHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-shell-dock-v491-")
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
        stderr=subprocess.DEVNULL,
    )
    try:
        port_file = Path(profile) / "DevToolsActivePort"
        deadline = time.monotonic() + 8
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.04)
        assert port_file.exists(), "Chrome DevTools port did not become ready"
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
        page = next(item for item in pages if item.get("type") == "page" and item.get("url") == "about:blank")

        with connect(page["webSocketDebuggerUrl"], origin="http://localhost", open_timeout=5) as websocket:
            request_id = 0

            def cdp(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                websocket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
                while True:
                    response = json.loads(websocket.recv())
                    if response.get("id") == request_id:
                        return response

            cdp(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            )
            fixture = (
                "workspace_os_v48_shell_harness.html"
                if shell_query is not None
                else "workspace_dock_shell_v491_runtime.html"
            )
            suffix = f"?{shell_query}" if shell_query else ""
            cdp(
                "Page.navigate",
                {
                    "url": (
                        f"http://127.0.0.1:{server.server_port}/tests/fixtures/"
                        f"{fixture}{suffix}"
                    ),
                },
            )
            wait_for_activation = (
                shell_query is not None and "activate=shortcut" in shell_query
            )
            wait_for_logout = (
                shell_query is not None and "probe=logout" in shell_query
            )
            wait_for_multiwindow = (
                shell_query is not None and "probe=multiwindow" in shell_query
            )
            # Activation includes the hashchange-owned mount and an explicit
            # fixture flush. It can be CPU-starved when several Chrome probes
            # run concurrently, so reserve a bounded real-time allowance for
            # that multi-event path only.
            if wait_for_activation or wait_for_multiwindow:
                ready_timeout = 30
            else:
                ready_timeout = 10
            required_markers = ["fixtureReady=true"]
            if wait_for_activation:
                required_markers.append("fixtureAfterActionWindowCount=1")
            if wait_for_logout:
                required_markers.append("fixtureLogoutLeakPassed=true")
            if wait_for_multiwindow:
                required_markers.append("fixtureMultiReady=true")
            deadline = time.monotonic() + ready_timeout
            attempts = 0
            last_state: dict[str, object] = {"probe": "not evaluated"}
            while time.monotonic() < deadline:
                probe = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": (
                            'JSON.stringify({width: innerWidth, readyState: document.readyState, '
                            'href: window.location.href, ready: document.body?.dataset.'
                            'fixtureReady || "", mount: document.body?.dataset.'
                            'fixtureDockMountCount || "", overflow: document.body?.dataset.'
                            'fixtureDockOverflowNavigationCount || "", afterAction: '
                            'document.body?.dataset.fixtureAfterActionWindowCount || "", logout: '
                            'document.body?.dataset.fixtureLogoutLeakPassed || "", multi: '
                            'document.body?.dataset.fixtureMultiReady || ""})'
                        ),
                        "returnByValue": True,
                    },
                )
                raw_state = (
                    probe.get("result", {})
                    .get("result", {})
                    .get("value", "")
                )
                try:
                    state = json.loads(raw_state) if isinstance(raw_state, str) else raw_state
                except json.JSONDecodeError:
                    state = {"raw": raw_state}
                last_state = state if isinstance(state, dict) else {"raw": state}
                attempts += 1
                dock_ready = (
                    last_state.get("mount") == "1"
                    and last_state.get("overflow") == "1"
                )
                shell_ready = (
                    last_state.get("ready") == "true"
                    and (
                        not wait_for_activation
                        or last_state.get("afterAction") == "1"
                    )
                    and (not wait_for_logout or last_state.get("logout") == "true")
                    and (not wait_for_multiwindow or last_state.get("multi") == "true")
                )
                if last_state.get("width") == width and (
                    shell_ready if shell_query is not None else dock_ready
                ):
                    break
                time.sleep(0.04)
            else:
                raise AssertionError(
                    "Exact-width Dock probe did not finish "
                    f"after {ready_timeout}s and {attempts} samples; expected width={width} "
                    f"and {', '.join(required_markers)}; last CDP state: "
                    f"{json.dumps(last_state, ensure_ascii=False, sort_keys=True)}"
                )
            result = cdp(
                "Runtime.evaluate",
                {"expression": "document.documentElement.outerHTML", "returnByValue": True},
            )
            return result["result"]["result"]["value"]
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
        time.sleep(0.1)
        shutil.rmtree(profile, ignore_errors=True)


def test_preserved_v471_dock_sprite_is_the_canonical_visual_source() -> None:
    root = ET.parse(SPRITE_PATH).getroot()
    symbols = {
        node.attrib["id"]
        for node in root.iter()
        if node.tag.endswith("symbol") and node.attrib.get("id")
    }
    assert symbols == EXPECTED_DOCK_SYMBOLS
    assert "new URL(\"./assets/workspace_dock_icon_sprite_v4_7_1.svg" in CORE
    assert "function dockIcon(symbol, size = 52)" in CORE
    assert 'createElementNS(SVG_NS, "use")' in CORE
    assert "emoji" not in CORE.lower()


def test_window_shells_own_persistent_live_surfaces_while_parent_dom_stays_parked() -> None:
    assert 'import {\n  createWorkspaceWindowManagerState,\n  workspaceWindowManagerReducer,' in CORE
    assert "createContentEngineEmbeddedWindowUrl" in CORE
    assert "readContentEngineEmbeddedWindowEvent" in CORE
    assert 'shell.dataset.ceV4Window = "true"' in CORE
    assert 'body.dataset.ceV4WindowBody = "true"' in CORE
    assert "function createWorkspaceWindowShell(windowId)" in CORE
    assert "runtime.windowShells.set(windowId, shell);" in CORE
    assert "windowSurfaces: new Map()" in CORE
    assert "function ensureWorkspaceWindowSurface(body, windowRecord)" in CORE
    assert 'frame = create("iframe", "ce-v4-window__surface")' in CORE
    assert 'frame.dataset.ceV4WindowSurface = "true"' in CORE
    assert "createContentEngineEmbeddedWindowUrl(routeForWorkspaceWindow(windowRecord)" in CORE
    assert "runtime.windowSurfaces.set(windowRecord.windowId, frame);" in CORE
    assert "body.replaceChildren(frame)" in CORE
    assert "parkWorkspaceContent();" in CORE
    assert "ensureWorkspaceWindowSurface(q(\"[data-ce-v4-window-body]\", shell), windowRecord);" in CORE
    assert "function handleWorkspaceWindowSurfaceMessage(event)" in CORE
    assert "event.origin !== window.location.origin" in CORE
    assert "workspaceWindowSurfaceForSource(event.source)" in CORE
    assert 'window.addEventListener("message", handleWorkspaceWindowSurfaceMessage);' in CORE
    assert "cloneNode" not in CORE
    assert ".innerHTML" not in CORE
    assert ".outerHTML" not in CORE
    assert "XMLSerializer" not in CORE
    assert "FormData" not in CORE
    assert "html2canvas" not in CORE
    assert "fetch(" not in CORE
    assert "XMLHttpRequest" not in CORE
    assert "container: ce-v4-window / inline-size" in CSS
    surface_rule = re.search(
        r"\.ce-v4-window__surface\s*\{(?P<body>.*?)\n\}",
        CSS,
        re.DOTALL,
    )
    assert surface_rule
    for marker in ("display: block", "width: 100%", "height: 100%", "border: 0", "pointer-events: auto"):
        assert marker in surface_rule.group("body")
    for action in ("close", "minimize", "zoom", "desktop", "mission"):
        assert f'window-action="{action}"' in CORE or f'windowControl("{action}"' in CORE or f'action === "{action}"' in CORE
    assert 'create("span", "ce-v4-window__desktop-label", "Рабочий стол")' in CORE
    assert 'navigate("/workspace/home")' in CORE
    assert ".ce-v4-window__desktop" in CSS


def test_desktop_parks_the_live_dom_without_destroying_the_window_manager() -> None:
    assert 'desktop.dataset.ceV4Desktop = "true"' in CORE
    assert "const snapshot = projectFlowSnapshot();" in CORE
    assert "desktop.replaceChildren(widgets, shortcuts);" in CORE
    assert "ensureWorkspaceDesktop();" in CORE
    assert "ensureWorkspaceWindow();" in CORE
    assert "function workspaceDesktopRoute(" in CORE
    assert "if (workspaceDesktopRoute()) {" in CORE
    assert 'document.body.dataset.ceV4DesktopHome = "true"' in CORE
    assert "parkWorkspaceContent();\n    syncWorkspaceWindowState();" in CORE
    mount_start = CORE.index("function mount()")
    desktop_start = CORE.index("if (workspaceDesktopRoute()) {", mount_start)
    desktop_branch = CORE[
        desktop_start : CORE.index("updateWorkspaceDesktop();", desktop_start)
    ]
    assert "removeWorkspaceWindow()" not in desktop_branch
    assert "setWorkspaceContentParked(false);\n    ensureWorkspaceWindow();" in CORE
    assert ".ce-v4-desktop {" in CSS
    assert ".ce-v4-window {" in CSS
    assert 'body.contentengine-desktop-v4 [data-ce-v4-desktop-parked="true"]' in CSS
    assert ".ce-v4-window[hidden]" in CSS
    assert "display: none !important" in CSS
    assert re.search(r"\.ce-v4-desktop\s*\{[^}]*z-index:\s*1", CSS, re.DOTALL)
    assert re.search(r"\.ce-v4-window\s*\{[^}]*z-index:\s*20", CSS, re.DOTALL)


@pytest.mark.parametrize("width,height", [(1440, 900), (390, 844), (320, 700)])
def test_home_route_is_a_visible_desktop_with_zero_windows_at_exact_widths(
    width: int,
    height: int,
) -> None:
    html = _dump_exact_width_dock_probe(
        width,
        height,
        shell_query="route=home&project=none",
    )

    for marker in (
        'data-ce-v4-desktop-home="true"',
        'data-fixture-desktop-window-count="0"',
        'data-fixture-desktop-content-parked="true"',
        'data-fixture-desktop-widgets-visible="3"',
        'data-fixture-desktop-shortcuts-visible="1"',
        'data-fixture-desktop-objects-visible="4"',
        'data-fixture-desktop-fits="true"',
        'data-fixture-desktop-dock-active-count="0"',
        'data-fixture-decision-widget-has-null="false"',
        'data-fixture-decision-widget-value="—"',
        'data-fixture-dock-fits="true"',
        'data-fixture-dock-menu-fits="true"',
    ):
        assert marker in html
    assert html.count('class="ce-v4-dock"') == 1
    assert 'data-ce-v4-window="true"' not in html


def test_desktop_object_activation_opens_one_live_window_surface() -> None:
    html = _dump_exact_width_dock_probe(
        1280,
        800,
        shell_query="route=home&activate=shortcut",
    )

    assert 'data-fixture-desktop-window-count="0"' in html
    assert 'data-fixture-after-action-window-count="1"' in html
    assert 'data-fixture-after-action-content-parked="true"' in html
    assert 'data-fixture-after-action-surface-count="1"' in html
    assert (
        'data-fixture-after-action-route="#/workspace/board?project_id='
        '11111111-1111-4111-8111-111111111111&amp;folder='
        '11111111-1111-4111-8111-111111111111"'
    ) in html
    assert html.count('data-ce-v4-window="true"') == 1


def test_multiple_visible_live_surfaces_survive_desktop_home() -> None:
    html = _dump_exact_width_dock_probe(
        3440,
        1440,
        shell_query="route=ai&probe=multiwindow",
    )

    for marker in (
        'data-fixture-multi-ready="true"',
        'data-fixture-multi-shell-count="2"',
        'data-fixture-multi-visible-shell-count="2"',
        'data-fixture-multi-surface-count="2"',
        'data-fixture-multi-parent-coordinator-parked="true"',
        'data-fixture-multi-both-surfaces-interactive="true"',
        'data-fixture-multi-duplicate-business-ui-removed="true"',
        'data-fixture-multi-desktop-obscured="true"',
        'data-fixture-multi-windows-avoid-chrome="true"',
        'data-fixture-multi-inactive-titlebar-exposed="true"',
        'data-fixture-multi-initial-windows-cascade="true"',
        'data-fixture-window-titlebar-drag-moves="true"',
        'data-fixture-window-pointer-focus-raises="true"',
        'data-fixture-window-focus-keeps-parent-route="true"',
        'data-fixture-window-control-does-not-drag="true"',
        'data-fixture-window-minimize-works="true"',
        'data-fixture-window-restore-works="true"',
        'data-fixture-window-desktop-control-works="true"',
        'data-fixture-multi-manager-window-count="2"',
        'data-fixture-multi-route-geometry="true"',
        'data-fixture-multi-manager-survives-home="true"',
        'data-fixture-multi-home-visible-shell-count="0"',
        'data-fixture-multi-desktop-restored-on-home="true"',
    ):
        assert marker in html
    assert html.count('id="workspace-content"') == 1
    assert html.count('data-ce-v4-window="true"') == 2


def test_window_controls_work_at_the_reported_desktop_viewport() -> None:
    html = _dump_exact_width_dock_probe(
        1720,
        1000,
        shell_query="route=ai&probe=multiwindow",
    )

    for marker in (
        'data-fixture-multi-visible-shell-count="2"',
        'data-fixture-multi-inactive-titlebar-exposed="true"',
        'data-fixture-multi-windows-avoid-chrome="true"',
        'data-fixture-multi-desktop-obscured="true"',
        'data-fixture-multi-duplicate-business-ui-removed="true"',
        'data-fixture-multi-surface-count="2"',
        'data-fixture-multi-both-surfaces-interactive="true"',
        'data-fixture-multi-parent-coordinator-parked="true"',
        'data-fixture-multi-initial-windows-cascade="true"',
        'data-fixture-window-titlebar-drag-moves="true"',
        'data-fixture-window-pointer-focus-raises="true"',
        'data-fixture-window-focus-keeps-parent-route="true"',
        'data-fixture-window-control-does-not-drag="true"',
        'data-fixture-window-minimize-works="true"',
        'data-fixture-window-restore-works="true"',
    ):
        assert marker in html
    assert html.count('id="workspace-content"') == 1
    assert html.count('data-ce-v4-window="true"') == 2


def test_ultrawide_geometry_is_route_aware_and_stays_inside_the_workspace() -> None:
    geometry = CORE[
        CORE.index("function defaultWorkspaceWindowGeometry(") : CORE.index(
            "function reduceWorkspaceWindow(",
        )
    ]
    for marker in (
        'const wideSurface = ["/workspace/board", "/workspace/review", "/workspace/stats", "/workspace/placement"]',
        "bounds.width >= 2400",
        "bounds.width * (wideSurface ? 0.08 : 0.11)",
        "bounds.width * (wideSurface ? 0.06 : 0.09)",
        "const routeMaximum = wideSurface ? 2480 : 2140;",
        "bounds.width - horizontalInset * 2",
        "bounds.height - verticalInset * 2",
        "Math.min(ordinal, 5) * (bounds.width >= 1400 ? 42 : 30)",
        "Math.min(bounds.width - width",
        "Math.min(bounds.height - height",
    ):
        assert marker in geometry
    # Новое окно ложится каскадом ПОВЕРХ предыдущего (виден край старого);
    # авто-тайлинг первых двух окон отменён решением владельца 27.08.2026.
    assert "arrangeInitialWorkspaceWindows" not in CORE
    assert "cascade ON TOP" in geometry


def test_titlebar_drag_focus_and_desktop_isolation_keep_one_live_business_authority() -> None:
    drag = CORE[
        CORE.index("function stopWorkspaceWindowDragTracking(") : CORE.index(
            "function observeWorkspaceWindowGeometry(",
        )
    ]
    sync = CORE[
        CORE.index("function syncWorkspaceWindowState(") : CORE.index(
            "function beginWorkspaceWindowDrag(",
        )
    ]
    authority = CORE[
        CORE.index("function enforceSingleWorkspaceContent(") : CORE.index(
            "function parkWorkspaceContent(",
        )
    ]
    for marker in (
        'reduceWorkspaceWindow({ type: "focus", windowId })',
        "pendingActivation",
        "setPointerCapture",
        "releasePointerCapture",
        'window.addEventListener("pointermove", moveWorkspaceWindow, true)',
        'window.removeEventListener("pointermove", moveWorkspaceWindow, true)',
        "runtime.windowGeometryTouched.add(drag.windowId)",
        "activateWorkspaceWindow(drag.windowId",
        'event.target.closest("button, a, input, select, textarea")',
    ):
        assert marker in drag
    assert "syncWorkspaceDesktopExposure(desktopMode);" in sync
    assert "enforceSingleWorkspaceContent(host)" in sync
    assert 'const contents = qa("#workspace-content")' in authority
    assert "activeShell?.contains(node)" in authority
    assert 'node.setAttribute("inert", "")' in authority
    assert "node.remove();" in authority
    assert "FormData" not in authority
    assert "requestSubmit" not in authority
    assert "submit(" not in authority
    assert ".ce-v4-desktop[hidden]" in CSS
    assert ".ce-v4-desktop.is-obscured" in CSS
    titlebar_rule = re.search(r"\.ce-v4-window__titlebar\s*\{(?P<body>.*?)\n\}", CSS, re.DOTALL)
    assert titlebar_rule
    assert "cursor: grab" in titlebar_rule.group("body")


def test_dock_contract_is_the_only_visibility_and_overflow_owner() -> None:
    assert 'from "./workspace-dock-contract.js?v=20260826.rebuild-clean.47"' in CORE
    assert "createWorkspaceDockState(" in CORE
    assert "{ order: DOCK_CANONICAL_ORDER, shortcuts: {} }," in CORE
    assert "{ internalPolicy: DOCK_INTERNAL_POLICY }," in CORE
    assert CORE.count("computeWorkspaceDockPresentation(") == 1
    assert "function syncDockPresentation(activeKey = activeDockKey())" in CORE
    assert "syncDockAccess" not in CORE
    assert "syncDockOverflow" not in CORE
    assert "source?.click" not in CORE
    assert "activateDockKey(overflowKey, event);" in CORE
    assert "activateDockKey(item.dataset.ceV4DockKey, event);" in CORE
    assert 'link.dataset.ceV4DockKey = item.key' in CORE
    assert 'trash.dataset.ceV4DockKey = "trash"' in CORE
    canonical = re.search(
        r"const DOCK_CANONICAL_ORDER = Object\.freeze\(\[(.*?)\]\);",
        CORE,
        re.DOTALL,
    )
    assert canonical is not None
    assert re.findall(r'"([a-z]+)"', canonical.group(1)) == [
        "finder",
        "research",
        "ai",
        "create",
        "review",
        "publish",
        "results",
        "passports",
        "hypotheses",
        "processes",
        "settings",
        "trash",
    ]
    for marker in (
        'more.dataset.ceV4DockMore = "true"',
        'moreMenu.dataset.ceV4DockMoreMenu = "true"',
        'trash.append(trashTile, create("span", "ce-v4-dock__label", "Корзина"), trashRunning)',
        "return Math.max(6, Math.min(DOCK_CANONICAL_ORDER.length, measured));",
    ):
        assert marker in CORE
    assert "glass.scrollTo" not in CORE
    assert ".ce-v4-dock-more-menu {" in CSS
    assert ".ce-v4-dock-more-menu[hidden]" in CSS
    assert "@media (max-width: 360px)" in CSS
    assert "flex-basis: 42px !important;" in CSS
    assert "box-sizing: border-box;" in CSS
    assert "overflow: visible !important;" in STABILITY_CSS


def test_320px_dock_fits_and_each_native_click_navigates_once() -> None:
    html = _dump_exact_width_dock_probe(320, 700)

    for marker in (
        'data-fixture-dock-fits="true"',
        'data-fixture-dock-menu-fits="true"',
        'data-ce-v4-dock-capacity="6"',
        'data-ce-v4-dock-visible-count="6"',
        'data-ce-v4-dock-overflow="true"',
        'data-fixture-dock-unique-keys="true"',
        'data-fixture-dock-direct-navigation-count="1"',
        'data-fixture-dock-overflow-navigation-count="1"',
        'data-fixture-dock-mount-count="1"',
    ):
        assert marker in html
    assert (
        'data-fixture-dock-canonical-keys="finder,research,ai,create,review,'
        'publish,results,passports,hypotheses,processes,settings,trash"'
    ) in html
    assert 'data-fixture-dock-direct-route="#/workspace/board?project_id=11111111-1111-4111-8111-111111111111"' in html
    assert 'data-fixture-dock-overflow-route="#/workspace/work?project_id=11111111-1111-4111-8111-111111111111"' in html
    assert html.count('class="ce-v4-dock"') == 1


def test_running_and_stage_markers_are_not_the_same_dock_state() -> None:
    assert 'create("i", "ce-v4-dock__running")' in CORE
    assert 'create("span", "ce-v4-dock__stage")' in CORE
    assert '.ce-v4-dock__item.is-active > .ce-v4-dock__running' in CSS
    for state in ("done", "current", "blocked", "future"):
        assert f'.ce-v4-dock__stage[data-state="{state}"]' in CSS
    assert ".ce-v4-dock__item.is-stage-done > i" not in CSS


def test_window_contract_remains_pure_and_harness_proves_node_identity() -> None:
    for forbidden in ("document.", "window.", "localStorage", "sessionStorage", "fetch(", "XMLHttpRequest"):
        assert forbidden not in WINDOW_CONTRACT
    assert 'await import("../../web/app/workspace-os-v4.js?fixture=v48-shell-5")' in HARNESS
    assert 'document.querySelector("#workspace-content") === originalContent' in HARNESS
    assert 'action.addEventListener("click"' in HARNESS
    assert 'document.activeElement === focused' in HARNESS
    assert 'focused.selectionStart === 2 && focused.selectionEnd === 11' in HARNESS
    assert 'data.fixtureLogoutLeakPassed' not in HARNESS
    assert 'fixtureLogoutLeakPassed' in HARNESS
    assert 'data-workspace-role="operator"' in HARNESS
    assert "ИИ рекомендует · решение принимает человек" in HARNESS


def test_shell_runtime_preserves_dom_focus_selection_and_existing_handlers() -> None:
    html = _dump_exact_width_dock_probe(
        1280,
        800,
        shell_query="",
    )

    for marker in (
        'data-fixture-ready="true"',
        'data-fixture-original-node-preserved="true"',
        'data-fixture-focus-preserved="true"',
        'data-fixture-selection-preserved="true"',
        'data-fixture-dock-fits="true"',
        'data-fixture-dock-menu-fits="true"',
    ):
        assert marker in html
    assert html.count('data-ce-v4-window="true"') == 1
    assert html.count('class="ce-v4-dock"') == 1


def test_logout_never_rehomes_detached_project_dom_into_login() -> None:
    html = _dump_exact_width_dock_probe(
        1280,
        800,
        shell_query="probe=logout",
    )

    assert 'data-fixture-logout-leak-passed="true"' in html
    assert '<h1>Вход</h1>' in html
    assert 'id="workspace-content"' not in html
    assert "<h1>Машина предлагает" not in html


def test_mission_control_renders_window_manager_spaces_not_a_second_route_grid() -> None:
    for marker in (
        "function routeForWorkspaceWindow(record)",
        "function missionSpaceRecords(snapshot = projectFlowSnapshot())",
        'spaceList.setAttribute("role", "tablist")',
        'button.dataset.ceV4MissionWindow = windowRecord.windowId',
        'reduceWorkspaceWindow({ type: "switchSpace", spaceId: windowRecord.spaceId })',
        'reduceWorkspaceWindow({ type: "restore", windowId })',
        "runtime.windowRoutes.get(record.windowId)",
    ):
        assert marker in CORE
    assert 'button.dataset.route = item.route' not in CORE
    assert ".ce-v4-mission__spaces {" in CSS
    assert ".ce-v4-mission-window {" in CSS
    assert ".ce-v4-mission-window__canvas {" in CSS


def test_restored_window_reuses_its_live_surface_and_dock_shortcuts_follow_visual_order() -> None:
    for marker in (
        "function ensureWorkspaceWindowSurface(body, windowRecord)",
        "const frame = runtime.windowSurfaces.get(windowId);",
        'reduceWorkspaceWindow({ type: "restore", windowId });',
        "frame?.focus?.({ preventScroll: true })",
        '(presentation?.items || [])',
        '.filter((node) => {',
        'activateDockKey(item.dataset.ceV4DockKey, event)',
    ):
        assert marker in CORE


def test_desktop_project_and_ai_actions_obey_live_role_contract() -> None:
    for marker in (
        "function workspaceCanCreateProject()",
        "if (canCreateProject) {",
        'const aiAuthorized = routeIsAuthorized("/workspace/ai")',
        'action.disabled = true',
        'link.dataset.ceV4ProjectId',
        'link.dataset.ceV4ProjectName',
    ):
        assert marker in CORE
