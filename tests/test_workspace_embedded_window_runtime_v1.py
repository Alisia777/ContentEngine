from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
CONTRACT_PATH = APP_DIR / "workspace-embedded-window-contract.js"
RUNTIME_PATH = APP_DIR / "workspace-embedded-window-runtime.js"
CONTRACT = CONTRACT_PATH.read_text(encoding="utf-8")
RUNTIME = (APP_DIR / "workspace-embedded-window-runtime.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CHILD_CSS = (APP_DIR / "workspace-embedded-window.css").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")


def _run_node(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the embedded window contract")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
            import * as subject from {json.dumps(CONTRACT_PATH.as_uri())};
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


def _run_runtime_node(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the embedded window runtime")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
            import * as subject from {json.dumps(RUNTIME_PATH.as_uri())};
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


def test_builder_creates_one_same_origin_child_document_url_and_rejects_route_escape() -> None:
    result = _run_node(
        """
        const projectId = "8a825c4f-7927-4af5-8c55-4ed18c7c8761";
        const href = subject.createContentEngineEmbeddedWindowUrl(
          `/workspace/board?project_id=${projectId}&view=grid`,
          {
            baseUrl: "https://contentengine.example/app/index.html?stale=1#/workspace/home",
            windowId: "board:primary",
          },
        );
        const url = new URL(href);
        const request = subject.readContentEngineEmbeddedWindowRequest(url);
        const invalidRoutes = [
          "https://evil.example/workspace/board",
          "//evil.example/workspace/board",
          "/login",
          "/workspace/board/extra",
          "/workspace/%2f%2fevil",
          "/workspace/board#nested",
        ].map(subject.normalizeContentEngineEmbeddedWindowRoute);
        const duplicateMode = subject.readContentEngineEmbeddedWindowRequest({
          search: "?ce_window=1&ce_window=1&ce_window_id=board:primary",
        });
        process.stdout.write(JSON.stringify({
          origin: url.origin,
          pathname: url.pathname,
          mode: url.searchParams.get("ce_window"),
          windowId: url.searchParams.get("ce_window_id"),
          hash: url.hash,
          request,
          invalidRoutes,
          duplicateMode,
        }));
        """
    )

    assert result == {
        "origin": "https://contentengine.example",
        "pathname": "/app/index.html",
        "mode": "1",
        "windowId": "board:primary",
        "hash": "#/workspace/board?project_id=8a825c4f-7927-4af5-8c55-4ed18c7c8761&view=grid",
        "request": {"version": 1, "windowId": "board:primary"},
        "invalidRoutes": ["", "", "", "", "", ""],
        "duplicateMode": None,
    }


def test_message_contract_is_exact_window_scoped_and_carries_no_session_material() -> None:
    result = _run_node(
        """
        const validCommand = {
          type: subject.CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
          version: subject.CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
          command: "navigate",
          windowId: "review:one",
          route: "/workspace/review?view=current",
        };
        const command = subject.readContentEngineEmbeddedWindowCommand(validCommand, "review:one");
        const wrongWindow = subject.readContentEngineEmbeddedWindowCommand(validCommand, "review:two");
        const external = subject.readContentEngineEmbeddedWindowCommand(
          { ...validCommand, route: "https://evil.example/workspace/review" },
          "review:one",
        );
        const focus = subject.createContentEngineEmbeddedWindowEvent("focus", {
          windowId: "review:one",
          route: "/workspace/review?project_id=private-route-context",
        });
        const ready = subject.readContentEngineEmbeddedWindowEvent({
          ...focus,
          event: "ready",
        }, "review:one");
        const shortcut = subject.createContentEngineEmbeddedWindowEvent("shortcut", {
          windowId: "review:one",
          route: "/workspace/review",
          shortcut: "search",
        });
        const readShortcut = subject.readContentEngineEmbeddedWindowEvent(shortcut, "review:one");
        const invalidShortcut = subject.readContentEngineEmbeddedWindowEvent({
          ...shortcut,
          shortcut: "passwords",
        }, "review:one");
        process.stdout.write(JSON.stringify({
          command,
          wrongWindow,
          external,
          focus,
          ready,
          shortcut,
          readShortcut,
          invalidShortcut,
        }));
        """
    )

    assert result["command"] == {
        "command": "navigate",
        "windowId": "review:one",
        "route": "/workspace/review?view=current",
    }
    assert result["wrongWindow"] is None
    assert result["external"] is None
    assert result["focus"] == {
        "type": "contentengine:embedded-window",
        "version": 1,
        "event": "focus",
        "windowId": "review:one",
        "route": "/workspace/review",
    }
    assert result["ready"] == {
        "event": "ready",
        "windowId": "review:one",
        "route": "/workspace/review",
    }
    assert result["shortcut"] == {
        "type": "contentengine:embedded-window",
        "version": 1,
        "event": "shortcut",
        "windowId": "review:one",
        "route": "/workspace/review",
        "shortcut": "search",
    }
    assert result["readShortcut"] == {
        "event": "shortcut",
        "windowId": "review:one",
        "route": "/workspace/review",
        "shortcut": "search",
    }
    assert result["invalidShortcut"] is None

    combined = CONTRACT + RUNTIME
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "accessToken",
        "refreshToken",
        "serviceRole",
        "password",
    ):
        assert forbidden not in combined


def test_child_mode_requires_an_actual_same_origin_parent() -> None:
    result = _run_runtime_node(
        """
        const location = {
          search: "?ce_window=1&ce_window_id=board:one",
          origin: "https://contentengine.example",
        };
        const topContext = {};
        const topLevel = subject.contentEngineEmbeddedWindowRequest({
          location,
          self: topContext,
          top: topContext,
          parent: topContext,
        });
        const childContext = {};
        const sameOriginParent = { location: { origin: location.origin } };
        const sameOrigin = subject.contentEngineEmbeddedWindowRequest({
          location,
          self: childContext,
          top: sameOriginParent,
          parent: sameOriginParent,
        });
        const foreignParent = { location: { origin: "https://evil.example" } };
        const crossOrigin = subject.contentEngineEmbeddedWindowRequest({
          location,
          self: childContext,
          top: foreignParent,
          parent: foreignParent,
        });
        process.stdout.write(JSON.stringify({ topLevel, sameOrigin, crossOrigin }));
        """
    )

    assert result == {
        "topLevel": None,
        "sameOrigin": {"version": 1, "windowId": "board:one"},
        "crossOrigin": None,
    }


def test_loader_keeps_full_adapter_core_but_child_bootstrap_never_owns_nested_chrome() -> None:
    assert "contentEngineEmbeddedWindowRequest" in LOADER
    assert "installContentEngineEmbeddedWindowRuntime" in LOADER
    assert "workspace-embedded-window.css" in LOADER
    assert "ensureCore();" in LOADER
    assert "await corePromise;" in LOADER
    assert "embeddedRuntime?.markLoading?.(route)" in LOADER
    assert "embeddedRuntime?.markFailed?.(route)" in LOADER
    assert "embeddedRuntime.markReady(pendingRoute)" in LOADER
    assert '".ce-v4-menubar, .ce-v4-dock, .ce-v4-desktop, [data-ce-v4-window]"' in LOADER

    assert "window.CONTENTENGINE_DESKTOP_V4 = true" in RUNTIME
    assert "window.CONTENTENGINE_EMBEDDED_WINDOW = true" in RUNTIME
    assert "window.ContentEngineDesktopV4 =" not in RUNTIME
    assert 'event.origin !== window.location.origin' in RUNTIME
    assert 'event.source !== window.parent' in RUNTIME
    assert 'document.addEventListener("pointerdown", announceFocus, true)' in RUNTIME
    assert 'document.addEventListener("focusin", announceFocus, true)' in RUNTIME
    assert "requestShortcut" in RUNTIME

    assert 'html[data-ce-window-child="true"]' in CHILD_CSS
    assert "padding: 0 !important" in CHILD_CSS
    assert "overflow-y: auto !important" in CHILD_CSS
    for nested_chrome in (
        ".ce-v4-menubar",
        ".ce-v4-dock",
        ".ce-v4-desktop",
        ".ce-v4-mission",
        "[data-ce-v4-window]",
    ):
        assert nested_chrome in CHILD_CSS


def test_csp_allows_only_same_origin_live_children() -> None:
    assert "frame-src 'self'" in INDEX
    assert "frame-ancestors 'self'" in INDEX
    assert "frame-src 'none'" not in INDEX
    assert "frame-ancestors 'none'" not in INDEX
    assert "workspace-os-v4-loader.js?v=20260826.rebuild-clean.20" in INDEX
