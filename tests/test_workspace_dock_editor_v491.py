from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
APP_RUNTIME = (APP / "app.js").read_text(encoding="utf-8")
CONTRACT = APP / "workspace-dock-contract.js"
HARNESS = ROOT / "tests" / "fixtures" / "workspace_dock_editor_v491_harness.html"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


def _chrome_path() -> str:
    candidates = [
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for Dock editor runtime QA")
    return chrome


def _run_node(source: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for Dock editor reducer QA")
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _run_exact_viewport(width: int, height: int, expression: str) -> dict[str, object]:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-dock-editor-v491-")
    process = subprocess.Popen(
        [
            _chrome_path(),
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
            cdp(
                "Page.navigate",
                {
                    "url": (
                        f"http://127.0.0.1:{server.server_port}/tests/fixtures/"
                        "workspace_dock_editor_v491_harness.html"
                    ),
                },
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                ready = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": 'document.body?.dataset.fixtureDockEditorReady || ""',
                        "returnByValue": True,
                    },
                )
                value = ready.get("result", {}).get("result", {}).get("value", "")
                if value == "true":
                    break
                time.sleep(0.04)
            else:
                raise AssertionError("Dock editor fixture did not become ready")

            result = cdp(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            )
            assert "exceptionDetails" not in result.get("result", {}), result
            raw = result["result"]["result"].get("value")
            return json.loads(raw) if isinstance(raw, str) else raw
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


def test_pure_reducer_can_restore_a_standard_app_without_breaking_edit_transaction() -> None:
    result = _run_node(
        f"""
        const subject = await import({json.dumps(CONTRACT.as_uri())});
        let state = subject.createWorkspaceDockState();
        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        const baseline = JSON.stringify(state.editSession.baseline);
        state = subject.workspaceDockReducer(state, {{ type: "unpin", key: "results" }});
        const afterRemove = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        const reentryBaseline = JSON.stringify(state.editSession.baseline);
        state = subject.workspaceDockReducer(state, {{ type: "cancelEdit" }});
        const cancelled = JSON.parse(JSON.stringify(state));

        state = subject.workspaceDockReducer(state, {{ type: "enterEdit" }});
        state = subject.workspaceDockReducer(state, {{ type: "unpin", key: "results" }});
        state = subject.workspaceDockReducer(state, {{ type: "pinApp", key: "results" }});
        const restored = JSON.parse(JSON.stringify(state));
        state = subject.workspaceDockReducer(state, {{ type: "unpin", key: "publish" }});
        state = subject.workspaceDockReducer(state, {{ type: "doneEdit" }});
        const done = JSON.parse(JSON.stringify(state));
        process.stdout.write(JSON.stringify({{
          actions: subject.WORKSPACE_DOCK_ACTIONS,
          baseline,
          reentryBaseline,
          afterRemove,
          cancelled,
          restored,
          done,
        }}));
        """
    )

    assert "pinApp" in result["actions"]
    assert "results" not in result["afterRemove"]["preference"]["order"]
    assert result["afterRemove"]["effects"] == []
    assert result["baseline"] == result["reentryBaseline"]
    assert "results" in result["cancelled"]["preference"]["order"]
    assert result["cancelled"]["effects"] == []
    assert result["restored"]["preference"]["order"][:3] == ["finder", "research", "ai"]
    assert result["restored"]["effects"] == []
    assert result["done"]["effects"] == [
        {
            "type": "persist_preference",
            "reason": "edit_done",
            "preference": result["done"]["preference"],
        }
    ]


def test_shell_has_one_editor_owner_and_scoped_dynamic_command_runtime() -> None:
    harness = HARNESS.read_text(encoding="utf-8")
    assert "workspaceDockReducer" in CORE
    assert CORE.count('ceV4DockEditEntry = "true"') == 1
    assert CORE.count('const library = create("section", "ce-v4-dock-library")') == 1
    assert 'tablist.setAttribute("role", "tablist")' in CORE
    assert 'tab.setAttribute("role", "tab")' in CORE
    assert 'tab.setAttribute("aria-selected", String(index === 0))' in CORE
    assert 'tab.tabIndex = index === 0 ? 0 : -1' in CORE
    assert 'consumeDockTransition({ type: "enterEdit" })' in CORE
    assert 'consumeDockTransition({ type: "cancelEdit" })' in CORE
    assert 'consumeDockTransition({ type: "doneEdit" })' in CORE
    assert 'type: "pointerReorder"' in CORE
    assert 'type: "keyboardTakeOrDrop"' in CORE
    assert "drag.movement < 6" in CORE
    assert 'dock.dataset.ceV4DockPersistence = "identity-required"' in CORE
    assert 'window.localStorage.setItem(runtime.dockStorageKey' in CORE
    assert 'effect.reason !== "edit_done"' in CORE
    assert "workspace-command-registry" in CORE
    assert 'type: "addShortcut"' in CORE
    assert 'surface: "pin_zone"' in CORE
    assert 'WORKSPACE_DOCK_PIN_HOVER_MS' in CORE
    assert "tile.append(dockIcon(item.dockIcon, 52), count, editMarker)" in CORE
    assert "trashTile.append(dockIcon(\"ce-dock-trash\", 52), trashEditMarker)" in CORE
    assert ".ce-v4-dock__edit-marker.is-lock" in CSS
    assert ".ce-v4-dock-library__marker.is-lock" in CSS
    assert "fixtureDockEditorReady" in harness
    assert "Storage.prototype.setItem" in harness


def test_dock_bridge_pins_actor_project_and_existing_route_transport_owners() -> None:
    assert "getDockScope: workspaceDockAuthenticatedScope" in APP_RUNTIME
    assert "getDockLibrarySnapshot: workspaceDockLibrarySnapshot" in APP_RUNTIME
    assert "resolveDockShortcut: resolveWorkspaceDockShortcut" in APP_RUNTIME
    assert "executeDockCommand: executeWorkspaceDockCommand" in APP_RUNTIME
    assert "const expectedActorId = scope.userId;" in APP_RUNTIME
    assert 'requestApi.callAsExpectedActor(rpcName, payload, expectedActorId' in APP_RUNTIME
    assert 'isContextCurrent: () => workspaceDockScopeMatches(scope) && requestApi === state.api' in APP_RUNTIME
    assert 'invokeAsPinnedActor("creator_project_media"' in APP_RUNTIME
    assert 'invokeAsPinnedActor("creator_workspace_browser"' in APP_RUNTIME
    assert "normalizeWorkspaceInternalTarget" in APP_RUNTIME
    assert 'internalTarget?.kind === "app"' in APP_RUNTIME
    assert 'internalTarget?.kind === "desktop"' in APP_RUNTIME
    assert "navigate(" in APP_RUNTIME
    assert "window.history.pushState" not in CORE
    assert "requestApi.withOrganization" in APP_RUNTIME
    assert 'window.ContentEngineDesktopV4?.acceptsDockFileDrag?.(entityId) === true' in APP_RUNTIME
    assert "if (!workspaceBoardOrganizeMode() && !dockFileDrag)" in APP_RUNTIME


def test_runtime_snapshot_cancel_library_reorder_and_done_are_one_transaction() -> None:
    expression = r"""
    (async () => {
      const dock = document.querySelector(".ce-v4-dock");
      const entry = dock.querySelector("[data-ce-v4-dock-edit-entry]");
      const item = (key) => dock.querySelector(`[data-ce-v4-dock-key="${key}"]`);
      const visibleOrder = () => [...dock.querySelectorAll("[data-ce-v4-dock-key]")]
        .filter((node) => !node.hidden)
        .map((node) => node.dataset.ceV4DockKey);
      const inside = (marker) => {
        const tile = marker.closest(".ce-v4-dock__tile, .ce-v4-dock-library__tile");
        const mr = marker.getBoundingClientRect();
        const tr = tile.getBoundingClientRect();
        return mr.left >= tr.left - .5 && mr.right <= tr.right + .5
          && mr.top >= tr.top - .5 && mr.bottom <= tr.bottom + .5;
      };

      window.__dockEditorFixture.resetStorageWrites();
      entry.click();
      const initial = visibleOrder();
      item("results").click();
      const removedBeforeReentry = item("results").hidden;
      entry.click();
      dock.querySelector("[data-ce-v4-dock-edit-cancel]").click();
      const cancelRestored = !item("results").hidden;
      const cancelEffects = dock.dataset.ceV4DockLastCancelEffects;
      const cancelFocusRestored = document.activeElement === entry;

      entry.click();
      const markersContained = ["finder", "review", "ai", "trash", "results"]
        .map((key) => item(key).querySelector("[data-ce-v4-dock-edit-marker]"))
        .every((marker) => marker && inside(marker));
      const locked = ["finder", "review", "ai", "trash"].every((key) => (
        item(key).classList.contains("is-edit-locked")
        && item(key).querySelector("[data-ce-v4-dock-edit-marker]").classList.contains("is-lock")
      ));

      const libraryOpen = dock.querySelector("[data-ce-v4-dock-library-open]");
      libraryOpen.click();
      const library = dock.querySelector("[data-ce-v4-dock-library]");
      const appsTab = library.querySelector('[data-ce-v4-dock-library-tab="apps"]');
      appsTab.focus();
      appsTab.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
      const rovedRight = library.dataset.ceV4DockLibraryActiveTab === "projects"
        && document.activeElement.dataset.ceV4DockLibraryTab === "projects"
        && document.activeElement.tabIndex === 0;
      document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
      const rovedHome = library.dataset.ceV4DockLibraryActiveTab === "apps"
        && document.activeElement === library.querySelector('[data-ce-v4-dock-library-tab="apps"]');

      library.querySelector('[data-ce-v4-dock-library-app="results"]').click();
      const removedInLibrary = item("results").hidden;
      library.querySelector('[data-ce-v4-dock-library-app="results"]').click();
      const addedInLibrary = !item("results").hidden;
      library.querySelector("[data-ce-v4-dock-library-close]").click();
      const libraryClosedOnly = library.hidden
        && !dock.querySelector("[data-ce-v4-dock-editor]").hidden
        && document.activeElement === libraryOpen;

      const publish = item("publish");
      publish.focus();
      publish.dispatchEvent(new KeyboardEvent("keydown", { code: "Space", key: " ", bubbles: true }));
      publish.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
      publish.dispatchEvent(new KeyboardEvent("keydown", { code: "Space", key: " ", bubbles: true }));
      const keyboardMoved = [...dock.querySelectorAll("[data-ce-v4-dock-key]")]
        .map((node) => node.dataset.ceV4DockKey).indexOf("publish") === 1;

      const research = item("research");
      const create = item("create");
      const rr = research.getBoundingClientRect();
      const cr = create.getBoundingClientRect();
      const pointerId = 41;
      research.dispatchEvent(new PointerEvent("pointerdown", {
        bubbles: true, button: 0, pointerId, clientX: rr.left + rr.width / 2, clientY: rr.top + rr.height / 2,
      }));
      research.dispatchEvent(new PointerEvent("pointermove", {
        bubbles: true, button: 0, pointerId, clientX: cr.right - 1, clientY: cr.top + cr.height / 2,
      }));
      research.dispatchEvent(new PointerEvent("pointerup", {
        bubbles: true, button: 0, pointerId, clientX: cr.right - 1, clientY: cr.top + cr.height / 2,
      }));
      const domOrder = [...dock.querySelectorAll("[data-ce-v4-dock-key]")]
        .map((node) => node.dataset.ceV4DockKey);
      const pointerMoved = domOrder.indexOf("research") === domOrder.indexOf("create") + 1;

      dock.querySelector("[data-ce-v4-dock-edit-done]").click();
      const doneEffects = dock.dataset.ceV4DockLastDoneEffects;
      const scopedPersistence = dock.dataset.ceV4DockPersistence === "authenticated-local"
        && dock.dataset.ceV4DockStorageWrites === "1";
      const storageWrites = window.__dockEditorFixture.storageWrites();
      await window.ContentEngineDesktopV4.flush();
      await window.ContentEngineDesktopV4.flush();
      return JSON.stringify({
        initial,
        removedBeforeReentry,
        cancelRestored,
        cancelEffects,
        cancelFocusRestored,
        markersContained,
        locked,
        rovedRight,
        rovedHome,
        removedInLibrary,
        addedInLibrary,
        libraryClosedOnly,
        keyboardMoved,
        pointerMoved,
        doneEffects,
        scopedPersistence,
        storageWrites,
        dockCount: document.querySelectorAll(".ce-v4-dock").length,
        editorCount: document.querySelectorAll("[data-ce-v4-dock-editor]").length,
        libraryCount: document.querySelectorAll("[data-ce-v4-dock-library]").length,
      });
    })()
    """
    result = _run_exact_viewport(540, 820, expression)

    assert result["removedBeforeReentry"] is True
    assert result["cancelRestored"] is True
    assert result["cancelEffects"] == "0"
    assert result["cancelFocusRestored"] is True
    assert result["markersContained"] is True
    assert result["locked"] is True
    assert result["rovedRight"] is True
    assert result["rovedHome"] is True
    assert result["removedInLibrary"] is True
    assert result["addedInLibrary"] is True
    assert result["libraryClosedOnly"] is True
    assert result["keyboardMoved"] is True
    assert result["pointerMoved"] is True
    assert result["doneEffects"] == "1"
    assert result["scopedPersistence"] is True
    assert result["storageWrites"] == 1
    assert result["dockCount"] == 1
    assert result["editorCount"] == 1
    assert result["libraryCount"] == 1


def test_dynamic_shortcut_reload_scope_isolation_cancel_and_one_native_gesture() -> None:
    expression = r"""
    (async () => {
      const fixture = window.__dockEditorFixture;
      const dock = document.querySelector(".ce-v4-dock");
      const entry = dock.querySelector("[data-ce-v4-dock-edit-entry]");
      fixture.resetStorageWrites();

      entry.click();
      dock.querySelector("[data-ce-v4-dock-library-open]").click();
      dock.querySelector('[data-ce-v4-dock-library-tab="files"]').click();
      const fileCandidate = dock.querySelector('[data-ce-v4-dock-library-candidate="candidate-0"]');
      fileCandidate.click();
      const dynamicBeforeDone = dock.querySelector('[data-ce-v4-dock-shortcut="file_shortcut"]');
      const shortcutKey = dynamicBeforeDone?.dataset.ceV4DockKey || "";
      dock.querySelector("[data-ce-v4-dock-library-close]").click();
      dock.querySelector("[data-ce-v4-dock-edit-done]").click();
      const writesAfterDone = fixture.storageWrites();

      window.ContentEngineDesktopV4.refreshDockPreferences();
      await window.ContentEngineDesktopV4.flush();
      const restoredSameScope = Boolean(dock.querySelector(`[data-ce-v4-dock-key="${shortcutKey}"]`));

      fixture.setScope("organizationB");
      window.ContentEngineDesktopV4.refreshDockPreferences();
      await window.ContentEngineDesktopV4.flush();
      const absentOtherOrganization = !dock.querySelector(`[data-ce-v4-dock-key="${shortcutKey}"]`);

      fixture.setScope("userB");
      window.ContentEngineDesktopV4.refreshDockPreferences();
      await window.ContentEngineDesktopV4.flush();
      const absentOtherUser = !dock.querySelector(`[data-ce-v4-dock-key="${shortcutKey}"]`);

      fixture.setScope("a");
      window.ContentEngineDesktopV4.refreshDockPreferences();
      await window.ContentEngineDesktopV4.flush();
      const restoredAfterIsolation = dock.querySelector(`[data-ce-v4-dock-key="${shortcutKey}"]`);
      restoredAfterIsolation.click();
      await new Promise((resolve) => setTimeout(resolve, 30));
      const gestures = fixture.commandGestures();

      entry.click();
      dock.querySelector("[data-ce-v4-dock-library-open]").click();
      dock.querySelector('[data-ce-v4-dock-library-tab="files"]').click();
      dock.querySelector('[data-ce-v4-dock-external-url]').value = "https://example.com/docs?utm_source=test";
      dock.querySelector('[data-ce-v4-dock-external-form]').dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      const externalBeforeCancel = Boolean(dock.querySelector('[data-ce-v4-dock-shortcut="external_link_shortcut"]'));
      dock.querySelector("[data-ce-v4-dock-edit-cancel]").click();
      const cancelRolledBack = !dock.querySelector('[data-ce-v4-dock-shortcut="external_link_shortcut"]');

      return JSON.stringify({
        shortcutKey,
        writesAfterDone,
        writesAfterCancel: fixture.storageWrites(),
        restoredSameScope,
        absentOtherOrganization,
        absentOtherUser,
        restoredAfterIsolation: Boolean(restoredAfterIsolation),
        commandCount: gestures.length,
        uniqueGestureCount: new Set(gestures).size,
        externalBeforeCancel,
        cancelRolledBack,
        persistence: dock.dataset.ceV4DockPersistence,
      });
    })()
    """
    result = _run_exact_viewport(1280, 820, expression)

    assert result["shortcutKey"].startswith("file-shortcut:")
    assert result["writesAfterDone"] == 1
    assert result["writesAfterCancel"] == 1
    assert result["restoredSameScope"] is True
    assert result["absentOtherOrganization"] is True
    assert result["absentOtherUser"] is True
    assert result["restoredAfterIsolation"] is True
    assert result["commandCount"] == 1
    assert result["uniqueGestureCount"] == 1
    assert result["externalBeforeCancel"] is True
    assert result["cancelRolledBack"] is True
    assert result["persistence"] == "authenticated-local"


def test_file_drag_arms_real_pin_zone_and_creates_one_uncommitted_shortcut() -> None:
    expression = r"""
    (async () => {
      const fixture = window.__dockEditorFixture;
      const dock = document.querySelector(".ce-v4-dock");
      const handle = document.querySelector("[data-workspace-drag-item]");
      fixture.resetStorageWrites();
      handle.dispatchEvent(new DragEvent("dragstart", { bubbles: true, cancelable: true }));
      const zone = dock.querySelector("[data-ce-v4-dock-pin-zone]");
      const exposed = !zone.hidden;
      zone.dispatchEvent(new DragEvent("dragenter", { bubbles: true, cancelable: true }));
      const arming = zone.dataset.ceV4DockPinPhase === "arming";
      await new Promise((resolve) => setTimeout(resolve, 500));
      const ready = zone.dataset.ceV4DockPinPhase === "ready";
      zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true }));
      await new Promise((resolve) => setTimeout(resolve, 50));
      const shortcuts = [...dock.querySelectorAll('[data-ce-v4-dock-shortcut="file_shortcut"]')];
      return JSON.stringify({
        exposed,
        arming,
        ready,
        resetAfterDrop: zone.hidden && zone.dataset.ceV4DockPinPhase === "idle",
        shortcutCount: shortcuts.length,
        editing: dock.dataset.ceV4DockEditing,
        storageWrites: fixture.storageWrites(),
      });
    })()
    """
    result = _run_exact_viewport(390, 820, expression)

    assert result == {
        "exposed": True,
        "arming": True,
        "ready": True,
        "resetAfterDrop": True,
        "shortcutCount": 1,
        "editing": "true",
        "storageWrites": 0,
    }


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_editor_library_and_six_item_dock_fit_exact_narrow_viewports(width: int) -> None:
    expression = r"""
    (() => {
      const dock = document.querySelector(".ce-v4-dock");
      dock.querySelector("[data-ce-v4-dock-edit-entry]").click();
      dock.querySelector("[data-ce-v4-dock-library-open]").click();
      const glass = dock.querySelector(".ce-v4-dock__glass");
      const editor = dock.querySelector("[data-ce-v4-dock-editor]");
      const library = dock.querySelector("[data-ce-v4-dock-library]");
      const within = (node) => {
        const rect = node.getBoundingClientRect();
        return rect.left >= -.5 && rect.right <= innerWidth + .5
          && rect.top >= -.5 && rect.bottom <= innerHeight + .5;
      };
      const visibleParts = [...glass.children].filter((node) => (
        !node.hidden && node.matches(".ce-v4-dock__item, .ce-v4-dock__separator")
      ));
      return JSON.stringify({
        width: innerWidth,
        capacity: Number(dock.dataset.ceV4DockCapacity),
        visibleCount: Number(dock.dataset.ceV4DockVisibleCount),
        dockFits: within(dock) && within(glass) && visibleParts.every(within),
        editorFits: within(editor),
        libraryFits: within(library),
        noPageOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
        noGlassOverflow: glass.scrollWidth <= glass.clientWidth,
        oneDock: document.querySelectorAll(".ce-v4-dock").length === 1,
        oneLibrary: document.querySelectorAll("[data-ce-v4-dock-library]").length === 1,
      });
    })()
    """
    result = _run_exact_viewport(width, 820, expression)

    assert result["width"] == width
    assert result["capacity"] >= 6
    assert result["visibleCount"] >= 6
    assert result["dockFits"] is True
    assert result["editorFits"] is True
    assert result["libraryFits"] is True
    assert result["noPageOverflow"] is True
    assert result["noGlassOverflow"] is True
    assert result["oneDock"] is True
    assert result["oneLibrary"] is True
