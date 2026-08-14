from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "workspace-window-manager-contract.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _run_node(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the workspace window manager contract")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
            import * as subject from {json.dumps(MODULE.as_uri())};
            {body}
            """,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_contract_is_pure_and_exposes_one_complete_reducer_action_vocabulary() -> None:
    for forbidden in (
        "document.",
        "globalThis.document",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "fetch(",
        "XMLHttpRequest",
        "location.",
        "history.",
        "pushState",
        "replaceState",
    ):
        assert forbidden not in SOURCE

    result = _run_node(
        """
        const state = subject.createWorkspaceWindowManagerState();
        process.stdout.write(JSON.stringify({
          version: subject.WORKSPACE_WINDOW_MANAGER_CONTRACT_VERSION,
          actions: subject.WORKSPACE_WINDOW_MANAGER_ACTIONS,
          state,
          exports: [
            typeof subject.workspaceWindowManagerReducer,
            typeof subject.clampWorkspaceWindowGeometry,
            typeof subject.serializeWorkspaceWindowManagerState,
            typeof subject.deserializeWorkspaceWindowManagerState,
          ],
        }));
        """
    )
    assert result["version"] == "4.8"
    assert result["actions"] == [
        "open",
        "focus",
        "close",
        "minimize",
        "restore",
        "move",
        "resize",
        "toggleZoom",
        "switchSpace",
    ]
    assert result["exports"] == ["function"] * 4
    assert result["state"]["activeSpaceId"] == "space:main"
    assert result["state"]["spaces"] == [
        {"spaceId": "space:main", "windowIds": [], "activeWindowId": None}
    ]
    assert result["state"]["windows"] == []


def test_open_focus_close_and_spaces_have_one_deterministic_state_owner() -> None:
    result = _run_node(
        """
        const reduce = subject.workspaceWindowManagerReducer;
        let state = subject.createWorkspaceWindowManagerState({ bounds: { width: 1200, height: 800 } });
        state = reduce(state, {
          type: "open",
          appId: "research",
          windowId: "research:one",
          spaceId: "space:main",
          position: { x: 20, y: 30 },
          size: { width: 700, height: 500 },
          projectContext: { organizationId: "org-1", projectId: "project-1" },
        });
        state = reduce(state, { type: "switchSpace", spaceId: "space:review" });
        state = reduce(state, {
          type: "open",
          appId: "review",
          windowId: "review:one",
          spaceId: "space:review",
        });
        const isolated = JSON.parse(JSON.stringify(state));
        state = reduce(state, { type: "focus", windowId: "research:one" });
        const focused = JSON.parse(JSON.stringify(state));
        state = reduce(state, { type: "close", windowId: "research:one" });
        process.stdout.write(JSON.stringify({ isolated, focused, closed: state }));
        """
    )

    isolated = result["isolated"]
    assert isolated["activeSpaceId"] == "space:review"
    assert {space["spaceId"] for space in isolated["spaces"]} == {
        "space:main",
        "space:review",
    }
    by_space = {space["spaceId"]: space for space in isolated["spaces"]}
    assert by_space["space:main"]["windowIds"] == ["research:one"]
    assert by_space["space:review"]["windowIds"] == ["review:one"]

    focused = result["focused"]
    assert focused["activeSpaceId"] == "space:main"
    focused_windows = {item["windowId"]: item for item in focused["windows"]}
    assert focused_windows["research:one"]["zIndex"] > focused_windows["review:one"]["zIndex"]
    assert next(
        space for space in focused["spaces"] if space["spaceId"] == "space:main"
    )["activeWindowId"] == "research:one"

    closed = result["closed"]
    assert [item["windowId"] for item in closed["windows"]] == ["review:one"]
    assert next(
        space for space in closed["spaces"] if space["spaceId"] == "space:main"
    )["activeWindowId"] is None


def test_every_accepted_project_window_keeps_its_exact_project_space_at_capacity() -> None:
    result = _run_node(
        """
        const reduce = subject.workspaceWindowManagerReducer;
        let state = subject.createWorkspaceWindowManagerState();
        for (let index = 0; index < 128; index += 1) {
          state = reduce(state, {
            type: "open",
            appId: "board",
            windowId: `window:${index}`,
            spaceId: `space:project:${index}`,
            projectContext: { projectId: `project:${index}` },
          });
        }
        const accepted = state.windows.at(-1);
        const beforeOverflow = JSON.stringify(state);
        state = reduce(state, {
          type: "open",
          appId: "board",
          windowId: "window:overflow",
          spaceId: "space:project:overflow",
          projectContext: { projectId: "project:overflow" },
        });
        process.stdout.write(JSON.stringify({
          windowCount: state.windows.length,
          spaceCount: state.spaces.length,
          accepted,
          hasExactSpace: state.spaces.some((space) => space.spaceId === accepted.spaceId),
          overflowRejectedWithoutMutation: JSON.stringify(state) === beforeOverflow,
        }));
        """
    )

    assert result["windowCount"] == 128
    assert result["spaceCount"] == 129
    assert result["accepted"]["projectContext"]["projectId"] == "project:127"
    assert result["accepted"]["spaceId"] == "space:project:127"
    assert result["hasExactSpace"] is True
    assert result["overflowRejectedWithoutMutation"] is True


def test_minimize_restore_and_zoom_preserve_safe_window_memory() -> None:
    result = _run_node(
        """
        const reduce = subject.workspaceWindowManagerReducer;
        let state = reduce(undefined, {
          type: "open",
          appId: "board",
          windowId: "board:primary",
          selection: { kind: "media", id: "media-1", tabId: "recent", unsafe: "drop-me" },
          scroll: { top: 318.4, left: -20, pending: true },
        });
        state = reduce(state, { type: "minimize", windowId: "board:primary" });
        const minimized = JSON.parse(JSON.stringify(state));
        state = reduce(state, {
          type: "restore",
          windowId: "board:primary",
          selection: { kind: "media", ids: ["media-2", "media-2", "https://bad.example/file"] },
          scroll: { top: 900, left: 12 },
        });
        const restored = JSON.parse(JSON.stringify(state));
        state = reduce(state, { type: "toggleZoom", windowId: "board:primary" });
        const zoomed = JSON.parse(JSON.stringify(state));
        state = reduce(state, { type: "toggleZoom", windowId: "board:primary" });
        process.stdout.write(JSON.stringify({ minimized, restored, zoomed, unzoomed: state }));
        """
    )
    minimized_window = result["minimized"]["windows"][0]
    assert minimized_window["minimized"] is True
    assert result["minimized"]["spaces"][0]["activeWindowId"] is None
    assert minimized_window["selection"] == {
        "kind": "media",
        "id": "media-1",
        "tabId": "recent",
    }
    assert minimized_window["scroll"] == {"top": 318, "left": 0}

    restored_window = result["restored"]["windows"][0]
    assert restored_window["minimized"] is False
    assert restored_window["selection"] == {"kind": "media", "ids": ["media-2"]}
    assert restored_window["scroll"] == {"top": 900, "left": 12}
    assert result["restored"]["spaces"][0]["activeWindowId"] == "board:primary"
    assert result["zoomed"]["windows"][0]["zoomed"] is True
    assert result["unzoomed"]["windows"][0]["zoomed"] is False


def test_move_resize_and_bounds_changes_clamp_every_geometry_edge() -> None:
    result = _run_node(
        """
        const reduce = subject.workspaceWindowManagerReducer;
        const direct = subject.clampWorkspaceWindowGeometry(
          { position: { x: -100, y: 9999 }, size: { width: 9999, height: 20 } },
          { width: 1000, height: 700 },
        );
        let state = reduce(undefined, {
          type: "open",
          appId: "generation",
          windowId: "generation:one",
          bounds: { width: 1000, height: 700 },
          position: { x: 900, y: 650 },
          size: { width: 600, height: 500 },
        });
        state = reduce(state, {
          type: "move",
          windowId: "generation:one",
          position: { x: -40, y: 9000 },
        });
        const moved = JSON.parse(JSON.stringify(state.windows[0]));
        state = reduce(state, {
          type: "resize",
          windowId: "generation:one",
          size: { width: 10, height: 9999 },
        });
        const resized = JSON.parse(JSON.stringify(state.windows[0]));
        state = reduce(state, {
          type: "focus",
          windowId: "generation:one",
          bounds: { width: 280, height: 180 },
        });
        process.stdout.write(JSON.stringify({ direct, moved, resized, rebound: state.windows[0] }));
        """
    )
    assert result["direct"] == {
        "position": {"x": 0, "y": 480},
        "size": {"width": 1000, "height": 220},
    }
    assert result["moved"]["position"] == {"x": 0, "y": 200}
    assert result["resized"]["position"] == {"x": 0, "y": 0}
    assert result["resized"]["size"] == {"width": 320, "height": 700}
    assert result["rebound"]["position"] == {"x": 0, "y": 0}
    assert result["rebound"]["size"] == {"width": 280, "height": 180}


def test_allowlisted_serialization_excludes_sensitive_and_transient_state() -> None:
    result = _run_node(
        """
        const raw = {
          version: "hostile",
          bounds: { width: 1280, height: 760, signedUrl: "https://secret.example/bounds" },
          activeSpaceId: "space:main",
          spaces: [{
            spaceId: "space:main",
            activeWindowId: "research:one",
            formValues: { prompt: "private-form-value" },
          }],
          windows: [{
            appId: "research",
            windowId: "research:one",
            spaceId: "space:main",
            position: { x: 10, y: 20, secret: "position-secret" },
            size: { width: 800, height: 600, pending: true },
            zIndex: 7,
            minimized: false,
            zoomed: false,
            projectContext: {
              organizationId: "org-1",
              projectId: "project-1",
              signedUrl: "https://secret.example/project?signature=abc",
              secret: "project-secret",
            },
            selection: {
              kind: "source",
              id: "source-1",
              signedUrl: "https://secret.example/object?token=abc",
              accessToken: "token-private",
            },
            scroll: { top: 44, left: 9, fileInput: "binary-private" },
            formValues: { prompt: "private-form-value" },
            fileInput: { name: "private-file.mov" },
            paidAnalysisAck: true,
            paidFlags: { approved: true },
            pending: { requestId: "pending-private" },
            signedUrl: "https://secret.example/file?signature=abc",
            secret: "sk-private-value",
          }],
          apiToken: "token-top-private",
        };
        const snapshot = subject.serializeWorkspaceWindowManagerState(raw);
        const encoded = JSON.stringify(snapshot);
        const restored = subject.deserializeWorkspaceWindowManagerState(encoded);
        process.stdout.write(JSON.stringify({ snapshot, encoded, restored }));
        """
    )
    snapshot = result["snapshot"]
    window = snapshot["windows"][0]
    assert set(snapshot) == {"version", "bounds", "activeSpaceId", "spaces", "windows"}
    assert set(window) == {
        "appId",
        "windowId",
        "spaceId",
        "position",
        "size",
        "zIndex",
        "minimized",
        "zoomed",
        "projectContext",
        "selection",
        "scroll",
    }
    assert window["projectContext"] == {
        "organizationId": "org-1",
        "projectId": "project-1",
    }
    assert window["selection"] == {"kind": "source", "id": "source-1"}
    assert window["scroll"] == {"top": 44, "left": 9}
    encoded = result["encoded"]
    for forbidden in (
        "formValues",
        "private-form-value",
        "fileInput",
        "private-file.mov",
        "paidAnalysisAck",
        "paidFlags",
        "pending-private",
        "signedUrl",
        "signature=abc",
        "accessToken",
        "token-private",
        "project-secret",
        "sk-private-value",
    ):
        assert forbidden not in encoded
    assert result["restored"] == snapshot


def test_reducer_does_not_mutate_inputs_and_normalizes_unknown_actions() -> None:
    result = _run_node(
        """
        const initial = subject.createWorkspaceWindowManagerState({ bounds: { width: 900, height: 600 } });
        const action = {
          type: "open",
          appId: "tasks",
          windowId: "tasks:one",
          position: { x: 42, y: 51 },
          size: { width: 500, height: 400 },
        };
        const initialBefore = JSON.stringify(initial);
        const actionBefore = JSON.stringify(action);
        const opened = subject.workspaceWindowManagerReducer(initial, action);
        const unknown = subject.workspaceWindowManagerReducer(opened, {
          type: "executePaidRequest",
          paid: true,
          secret: "sk-nope",
        });
        process.stdout.write(JSON.stringify({
          initialUnchanged: JSON.stringify(initial) === initialBefore,
          actionUnchanged: JSON.stringify(action) === actionBefore,
          opened,
          unknown,
        }));
        """
    )
    assert result["initialUnchanged"] is True
    assert result["actionUnchanged"] is True
    assert result["unknown"] == result["opened"]
