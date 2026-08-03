from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _run_node(source: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the app markup contract")
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


def test_v4_scaffold_exposes_authorized_inline_route_without_legacy_navigation() -> None:
    scaffold = _between(
        APP,
        "function workspaceScaffold(content, activeSection)",
        "\n}\n\nfunction refreshNotificationLayer",
    ) + "\n}"
    result = _run_node(
        f"""
        globalThis.window = {{ CONTENTENGINE_DESKTOP_V4: true }};
        const state = {{
          route: {{ path: "/workspace/work", query: new URLSearchParams("view=notifications") }},
          myWork: {{
            notifications: {{ counts: {{ unread: 3 }} }},
            notificationsOpen: true,
            notificationsStatus: "ready",
            notificationsError: "",
          }},
          mobileNavOpen: false,
          bootstrap: {{ membership: {{ role: "operator" }} }},
        }};
        const escapeHtml = (value) => String(value);
        const displayProfile = () => ({{}});
        const visibleWorkspaceTabs = () => [["home"], ["work"], ["board"]];
        const workspaceNavigationTabs = () => [["work", "Моя работа", "✓"]];
        const consumeRouteTransitionClass = () => "";
        const brandMarkup = () => "";
        const workspaceNavLinkMarkup = () => "";
        const sidebarFooterMarkup = () => "";
        const brandAtmosphereMarkup = () => "";
        const workspaceContextBarMarkup = () => "";
        const mobileTopbarMarkup = () => "";
        const mobileNavMarkup = () => "";
        const notificationCenterMarkup = () => {{ throw new Error("legacy drawer mounted in v4"); }};
        {scaffold}
        const html = workspaceScaffold("<section data-notification-view></section>", "work");
        process.stdout.write(JSON.stringify({{
          nativeShell: html.includes("workspace-shell-v4"),
          authorized: html.includes('data-workspace-authorized-routes="/workspace/home /workspace/work /workspace/board"'),
          role: html.includes('data-workspace-role="operator"'),
          content: html.includes("data-notification-view"),
          sidebar: html.includes('class="sidebar"'),
          layer: html.includes("workspace-notification-layer"),
          dialog: html.includes('role="dialog"') || html.includes('aria-modal="true"'),
          backdrop: html.includes("notification-backdrop"),
          drawerAction: html.includes("toggle-work-notifications"),
        }}));
        """
    )
    assert result == {
        "nativeShell": True,
        "authorized": True,
        "role": True,
        "content": True,
        "sidebar": False,
        "layer": False,
        "dialog": False,
        "backdrop": False,
        "drawerAction": False,
    }


def test_v4_notification_refresh_retires_stale_drawer_without_replacing_shell_regions() -> None:
    refresh = _between(
        APP,
        "function refreshNotificationLayer({ focus = false } = {})",
        "\n}\n\nfunction canManageTeam",
    ) + "\n}"
    result = _run_node(
        f"""
        globalThis.window = {{ CONTENTENGINE_DESKTOP_V4: true }};
        const calls = {{ removedLayer: 0, removedBodyClass: 0, removedInert: 0, replacements: 0 }};
        const state = {{ myWork: {{ notificationsOpen: true }} }};
        const regions = [
          {{ removeAttribute(name) {{ if (name === "inert") calls.removedInert += 1; }} }},
          {{ removeAttribute(name) {{ if (name === "inert") calls.removedInert += 1; }} }},
        ];
        globalThis.document = {{
          body: {{ classList: {{
            remove(name) {{ if (name === "notification-center-open") calls.removedBodyClass += 1; }},
            toggle() {{ throw new Error("legacy body toggle reached"); }},
          }} }},
          querySelector(selector) {{
            if (selector === "#workspace-notification-layer") return {{ remove() {{ calls.removedLayer += 1; }} }};
            return null;
          }},
          querySelectorAll(selector) {{
            if (selector.includes("workspace-shell")) return regions;
            calls.replacements += 1;
            return [];
          }},
          createElement() {{ calls.replacements += 1; throw new Error("legacy replacement reached"); }},
        }};
        {refresh}
        refreshNotificationLayer({{ focus: true }});
        process.stdout.write(JSON.stringify({{ ...calls, open: state.myWork.notificationsOpen }}));
        """
    )
    assert result == {
        "removedLayer": 1,
        "removedBodyClass": 1,
        "removedInert": 2,
        "replacements": 0,
        "open": False,
    }


def test_app_routes_my_work_modes_explicitly_and_defaults_to_one_action() -> None:
    renderer = _between(
        APP,
        "function renderMyWorkSection(sectionState)",
        "\n}\n\nfunction renderPlacementSection",
    ) + "\n}"
    result = _run_node(
        f"""
        let rendered = null;
        const state = {{
          route: {{ query: new URLSearchParams() }},
          myWork: {{
            notifications: {{ items: [] }},
            savedViews: [],
            filters: {{}},
            selectedViewId: "",
            notice: "",
            error: "",
            loadingMore: false,
            notificationsStatus: "ready",
            notificationsError: "",
          }},
        }};
        const myWorkWorkspaceMarkup = (options) => {{ rendered = options; return options.mode; }};
        const workspaceActionSwitch = (_className, _label, activeView, items) =>
          items.map((item) => `${{item.view}}:${{item.href}}:${{item.view === activeView}}`).join("|");
        {renderer}
        const modes = {{}};
        for (const query of ["", "view=next", "view=notifications", "view=unsupported"]) {{
          state.route.query = new URLSearchParams(query);
          modes[query || "default"] = renderMyWorkSection({{ data: {{ items: [1, 2] }}, status: "ready" }});
        }}
        state.route.query = new URLSearchParams("view=notifications");
        renderMyWorkSection({{ data: {{}}, status: "ready" }});
        process.stdout.write(JSON.stringify({{
          modes,
          directNotificationRoute: rendered.actionSwitch.includes("notifications:#/workspace/work?view=notifications:true"),
          notificationStatus: rendered.notificationsLoading === false && rendered.notificationsError === "",
        }}));
        """
    )
    assert result == {
        "modes": {
            "default": "next",
            "view=next": "next",
            "view=notifications": "notifications",
            "view=unsupported": "next",
        },
        "directNotificationRoute": True,
        "notificationStatus": True,
    }


def test_async_notification_patch_keeps_shell_focus_and_nested_scroll_identity() -> None:
    renderer = _between(APP, "function renderWorkspace(section)", "\n}\n\nconst WORKSPACE_SCROLL_OWNERS")
    notification_loader = _between(
        APP,
        "async function loadMyWorkNotifications({ silent = false } = {})",
        "\n}\n\nasync function markMyWorkNotificationsRead",
    )
    capture_focus = _between(APP, "function captureWorkspaceFocus(container)", "\n}\n\nfunction restoreWorkspaceFocus")
    restore_focus = _between(APP, "function restoreWorkspaceFocus(container, identity, section)", "\n}\n\nfunction captureDirtyWorkspaceForms")

    ordered_markers = [
        "const existingShell = app.querySelector",
        "const focusedControl = sameAction ? captureWorkspaceFocus(existingContent) : null",
        "const scrollSnapshot = sameAction ? captureWorkspaceScroll(existingContent) : []",
        "patchWorkspaceContent(existingContent, content)",
        "restoreWorkspaceFocus(existingContent, focusedControl, section)",
        "restoreWorkspaceScroll(existingContent, scrollSnapshot, section)",
    ]
    positions = [renderer.index(marker) for marker in ordered_markers]
    assert positions == sorted(positions)
    assert 'existingShell?.dataset.workspaceSection === section' in renderer
    assert 'if (state.route.path === "/workspace/work") renderWorkspace("work")' in notification_loader
    assert '".notification-list"' in APP
    assert 'notificationId: String(active.dataset?.notificationId || "")' in capture_focus
    assert "!identity.notificationId || item.dataset?.notificationId === identity.notificationId" in restore_focus


def test_payout_reject_is_the_only_marker_and_only_visual_primary() -> None:
    payout = _between(
        APP,
        "function payoutDecisionMarkup(item)",
        "\n}\n\nfunction renderTasksSection",
    ) + "\n}"
    result = _run_node(
        f"""
        const state = {{ user: {{ id: "manager" }} }};
        const escapeHtml = (value) => String(value);
        {payout}
        const html = payoutDecisionMarkup({{ id: "payout-1", profile_id: "creator", status: "pending" }});
        const classes = [...html.matchAll(/<button class="([^"]+)"/g)].map((match) => match[1]);
        const visualPrimaries = classes.filter((value) => value.includes("btn-danger") || !value.includes("btn-secondary"));
        process.stdout.write(JSON.stringify({{
          markerCount: (html.match(/data-primary-action="true"/g) || []).length,
          visualPrimaryCount: visualPrimaries.length,
          rejectDangerPrimary: html.includes('class="btn btn-danger btn-small" type="submit" data-primary-action="true"'),
          approveSecondary: html.includes('class="btn btn-secondary btn-small" type="button"') && html.includes('data-decision="approve"'),
        }}));
        """
    )
    assert result == {
        "markerCount": 1,
        "visualPrimaryCount": 1,
        "rejectDangerPrimary": True,
        "approveSecondary": True,
    }
