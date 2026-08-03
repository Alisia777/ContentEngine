from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_APP = ROOT / "web" / "app"
ACTION_KEY = (WEB_APP / "workspace-action-key.js").read_text(encoding="utf-8")
APP = (WEB_APP / "app.js").read_text(encoding="utf-8")
CORE = (WEB_APP / "workspace-os-v4.js").read_text(encoding="utf-8")
LOADER = (WEB_APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_node(source: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the workspace action contract")
    result = subprocess.run(
        [node, "--input-type=module", "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_normalized_action_key_executes_view_and_whitelisted_entity_boundaries() -> None:
    module_url = (WEB_APP / "workspace-action-key.js").as_uri()
    result = _run_node(
        f"""
        import {{ workspaceActionKey, workspaceActionDescriptor }} from {json.dumps(module_url)};
        const taskId = "123e4567-e89b-12d3-a456-426614174000";
        const campaignId = "223e4567-e89b-12d3-a456-426614174000";
        const reviewId = "323e4567-e89b-12d3-a456-426614174000";
        const keys = {{
          workDefault: workspaceActionKey("#/workspace/work"),
          workExplicit: workspaceActionKey("#/workspace/work?view=next"),
          workNoise: workspaceActionKey("#/workspace/work?filter=open&view=next"),
          workNotifications: workspaceActionKey("#/workspace/work?view=notifications"),
          teamMembers: workspaceActionKey("#/workspace/team?view=members"),
          teamBudget: workspaceActionKey("#/workspace/team?view=budget"),
          taskQueue: workspaceActionKey("#/workspace/tasks?view=queue"),
          taskDetail: workspaceActionKey(`#/workspace/tasks?view=next&item=${{taskId}}`),
          invalidTask: workspaceActionKey("#/workspace/tasks?view=next&item=not-an-id"),
          duplicateTask: workspaceActionKey(`#/workspace/tasks?view=next&item=${{taskId}}&item=${{taskId}}`),
          teamCampaign: workspaceActionKey(`#/workspace/team?view=campaign&campaign=${{campaignId}}`),
          wrongTeamEntity: workspaceActionKey(`#/workspace/team?view=budget&campaign=${{campaignId}}`),
          teamReview: workspaceActionKey(`#/workspace/team?view=review&review=${{reviewId}}`),
          implicitGenerationJob: workspaceActionDescriptor(`#/workspace/generation?job=${{taskId}}`),
        }};
        process.stdout.write(JSON.stringify(keys));
        """
    )
    assert result["workDefault"] == "/workspace/work?view=next"
    assert result["workExplicit"] == result["workDefault"] == result["workNoise"]
    assert result["workNotifications"] == "/workspace/work?view=notifications"
    assert result["teamMembers"] != result["teamBudget"]
    assert result["taskQueue"] == "/workspace/tasks?view=queue"
    assert result["taskDetail"].endswith("&item=123e4567-e89b-12d3-a456-426614174000")
    assert result["invalidTask"] == result["duplicateTask"] == "/workspace/tasks?view=next"
    assert result["teamCampaign"].endswith("&campaign=223e4567-e89b-12d3-a456-426614174000")
    assert result["wrongTeamEntity"] == "/workspace/team?view=budget"
    assert result["teamReview"].endswith("&review=323e4567-e89b-12d3-a456-426614174000")
    assert result["implicitGenerationJob"]["view"] == "history"
    assert result["implicitGenerationJob"]["entityParameter"] == "job"


def test_app_executes_one_action_entry_reset_without_settle_focus_race() -> None:
    reset = _between(
        APP,
        "function resetWorkspaceRouteEntry(container, section) {",
        "\n}\n\nfunction captureWorkspaceFocus",
    ) + "\n}"
    settle = _between(
        APP,
        "function settleRouteView(",
        "\n}\n\nfunction authRedirectUrl",
    ) + "\n}"
    result = _run_node(
        f"""
        class FakeElement {{}}
        globalThis.HTMLElement = FakeElement;
        const calls = {{ focus: 0, windowScroll: 0 }};
        const main = new FakeElement();
        main.dataset = {{}};
        main.scrollTop = 71;
        main.scrollLeft = 12;
        main.focus = () => {{ calls.focus += 1; }};
        const nested = {{ scrollTop: 33, scrollLeft: 9 }};
        const content = {{ closest: () => main }};
        const state = {{ route: {{ path: "/workspace/work", actionKey: "/workspace/work?view=notifications" }} }};
        const workspaceActionKey = (route) => route.actionKey;
        const workspaceScrollNodes = () => [main, nested];
        const visibleWorkspaceTabs = () => [["work", "Work"]];
        const learningCourses = () => [];
        globalThis.window = {{
          requestAnimationFrame(callback) {{ callback(); }},
          scrollTo() {{ calls.windowScroll += 1; }},
        }};
        globalThis.document = {{
          title: "",
          querySelector(selector) {{
            if (selector === "#workspace-content") return content;
            if (selector === "#main-content") return main;
            return null;
          }},
        }};
        {reset}
        {settle}
        const actionKey = state.route.actionKey;
        resetWorkspaceRouteEntry(content, "work");
        settleRouteView({{ resetAction: true, expectedActionKey: actionKey }});
        main.scrollTop = 83;
        nested.scrollTop = 19;
        settleRouteView({{ resetAction: false, expectedActionKey: actionKey }});
        const sameAction = {{ mainTop: main.scrollTop, nestedTop: nested.scrollTop, focus: calls.focus }};
        settleRouteView({{ resetAction: true, expectedActionKey: "/workspace/work?view=next" }});
        process.stdout.write(JSON.stringify({{
          firstReset: main.dataset.ceV4ActionEntry === actionKey,
          sameAction,
          finalFocus: calls.focus,
          windowScroll: calls.windowScroll,
        }}));
        """
    )
    assert result == {
        "firstReset": True,
        "sameAction": {"mainTop": 83, "nestedTop": 19, "focus": 1},
        "finalFocus": 1,
        "windowScroll": 0,
    }


def test_reduced_motion_action_enter_is_removed_synchronously() -> None:
    cleanup = _between(
        LOADER,
        "function armRouteEnterCleanup(route, actionKey, epoch) {",
        "\n}\n\nfunction setFailed",
    ) + "\n}"
    result = _run_node(
        f"""
        const calls = {{ removed: 0, listeners: 0, timeouts: 0 }};
        const page = {{ addEventListener() {{ calls.listeners += 1; }}, removeEventListener() {{}} }};
        const main = {{
          querySelector() {{ return page; }},
          classList: {{ remove(name) {{ if (name === "route-enter") calls.removed += 1; }} }},
        }};
        const document = {{ querySelector() {{ return main; }} }};
        const window = {{
          matchMedia() {{ return {{ matches: true }}; }},
          clearTimeout() {{}},
          setTimeout() {{ calls.timeouts += 1; return 1; }},
        }};
        const routeEpoch = 4;
        const routePath = () => "/workspace/work";
        const workspaceActionKey = () => "/workspace/work?view=notifications";
        {cleanup}
        armRouteEnterCleanup("/workspace/work", "/workspace/work?view=notifications", 4);
        process.stdout.write(JSON.stringify(calls));
        """
    )
    assert result == {"removed": 1, "listeners": 0, "timeouts": 0}


def test_loader_core_and_app_share_the_same_action_key_contract() -> None:
    import_marker = 'from "./workspace-action-key.js?v=20260803.os4.4"'
    assert import_marker in APP
    assert import_marker in CORE
    assert import_marker in LOADER

    assert "const sameAction = actionKey === lastScheduledActionKey" in LOADER
    assert "actionKey !== workspaceActionKey()" in LOADER
    assert "detail: Object.freeze({ route, actionKey, build: BUILD })" in LOADER

    capture = _between(CORE, "function captureScroll(", "\nfunction restoreScroll(")
    restore = _between(CORE, "function restoreScroll(", "\nfunction governVideo(")
    handle = _between(CORE, "function handleHashChange(", "\nfunction handleKeydown(")
    assert "states[actionKey]" in capture
    assert "function captureCurrentAction(expectedActionKey = runtime.actionKey)" in capture
    assert "expected !== runtime.actionKey" in capture
    assert "runtime.preNavigationActionKey = runtime.actionKey" in capture
    assert "runtime.state.scroll?.[actionKey]" in restore
    assert "const pendingReset = runtime.pendingActionReset === actionKey" in restore
    assert "if (pendingReset && appAlreadyReset)" in restore
    assert "runtime.pendingActionReset = previousActionKey === runtime.actionKey" in handle
    assert 'if (runtime.preNavigationActionKey === previousActionKey)' in handle
    assert "captureScroll(runtime.route, previousActionKey)" in handle
    assert "window.ContentEngineDesktopV4?.captureCurrentAction?.(previousActionKey)" in APP
    assert "window.ContentEngineDesktopV4?.syncRoute?.()" in APP

    renderer = _between(APP, "function renderWorkspace(section)", "\n}\n\nconst WORKSPACE_SCROLL_OWNERS")
    assert "const sameAction = previousActionKey === nextActionKey" in renderer
    assert "sameAction ? captureWorkspaceFocus(existingContent) : null" in renderer
    assert "sameAction ? captureDirtyWorkspaceForms(existingContent) : []" in renderer
    assert "sameAction ? captureWorkspaceScroll(existingContent) : []" in renderer
    assert "if (sameAction)" in renderer
    assert "resetWorkspaceRouteEntry(existingContent, section)" in renderer
