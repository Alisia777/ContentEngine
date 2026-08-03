from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"

ROOT_INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
INDEX = (APP / "index.html").read_text(encoding="utf-8")
APP_JS = (APP / "app.js").read_text(encoding="utf-8")
MANIFEST = json.loads((APP / "build.json").read_text(encoding="utf-8"))
BUILD = MANIFEST["id"]
GUARD = (APP / "workspace-build-guard.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CORE_CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
MOTION_CSS = (APP / "workspace-os-v4-motion.css").read_text(encoding="utf-8")
STYLES = (APP / "styles.css").read_text(encoding="utf-8")
STARTUP_ROUTE = (APP / "startup-route.js").read_text(encoding="utf-8")
MY_WORK = (APP / "my-work-view.js").read_text(encoding="utf-8")
WEBKIT_FULL_MATRIX = (ROOT / "tests" / "webkit_full_app_matrix_v45_probe.cjs").read_text(
    encoding="utf-8"
)
WEBKIT_UI_RESET = (ROOT / "tests" / "webkit_ui_reset_probe.cjs").read_text(encoding="utf-8")
WEBKIT_FILE_SELECTION = (ROOT / "tests" / "webkit_file_selection_v45_probe.cjs").read_text(
    encoding="utf-8"
)


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def _route_array(name: str) -> list[str]:
    match = re.search(
        rf"const {name} = Object\.freeze\(\[(.*?)\]\);",
        CORE,
        flags=re.DOTALL,
    )
    assert match, f"missing {name}"
    return re.findall(r'route: "([^"]+)"', match.group(1))


def test_os44_build_and_cache_keys_are_consistent() -> None:
    assert BUILD == "20260803.os4.4"
    assert f'content="{BUILD}"' in ROOT_INDEX
    assert f'content="{BUILD}"' in INDEX
    assert f'const CURRENT_BUILD = "{BUILD}"' in GUARD
    assert f'const BUILD = "{BUILD}"' in LOADER
    assert f'const BUILD = "{BUILD}"' in CORE
    for asset in (
        "interface-system.css",
        "workspace-os-v4.css",
        "workspace-build-guard.css",
        "app.js",
        "workspace-os-v4-loader.js",
        "workspace-build-guard.js",
    ):
        assert f"./{asset}?v={BUILD}" in INDEX
    for dependency in (
        "generation-model-acceptance-view.js",
        "generation-spend-view.js",
        "manager-dashboard-view.js",
        "product-research-view.js",
        "training-media-cards.js",
    ):
        assert f'from "./{dependency}?v=' in APP_JS
    for dependency in (
        "my-work-view.js",
        "training-practical-review.js",
        "workspace-board-view.js",
    ):
        assert f'from "./{dependency}?v={BUILD}"' in APP_JS


def test_full_webkit_matrix_keeps_mac_retina_and_route_latency_modes() -> None:
    for marker in (
        "CE_MATRIX_DEVICE_SCALE_FACTOR",
        "deviceScaleFactor: matrixDeviceScaleFactor",
        "snapshot.settleMs = Date.now() - routeStartedAt",
        "routeP95 <= 2000",
        "routeMax <= 4000",
        "routePerformance:",
    ):
        assert marker in WEBKIT_FULL_MATRIX


def test_webkit_probes_keep_file_fullscreen_resize_and_focus_coverage() -> None:
    for marker in (
        "dockViewportResizeResult",
        "fullscreenResult",
        "dockMagnification.focusHierarchy",
        "permissionAwareToolsResult",
    ):
        assert marker in WEBKIT_UI_RESET
    for marker in (
        "workspace_webkit_file_selection_v45_harness.html",
        "nodeIdentity",
        "selectionPreserved",
        "focusPreserved",
        "listenerPreserved",
    ):
        assert marker in WEBKIT_FILE_SELECTION
    for marker in (
        "runSameWorkspaceViewScenario",
        "focusConnected",
        "expectedScrollTop",
        "sameWorkspaceViewContentMotion",
    ):
        assert marker in WEBKIT_FULL_MATRIX


def test_startup_normalizer_runs_before_app_without_hijacking_workspace_routes() -> None:
    startup = "./startup-route.js?v=20260803.entry1"
    assert startup in INDEX
    assert INDEX.index(startup) < INDEX.index(f'./app.js?v={BUILD}')
    assert 'if (!/^#\\/academy(?:\\/|\\?|$)/u.test(hash)) return;' in STARTUP_ROUTE
    assert 'hash.replace(/^#\\/academy/u, "#/learn")' in STARTUP_ROUTE
    assert "/workspace/" not in STARTUP_ROUTE


def test_replace_navigation_syncs_the_live_action_key_runtime() -> None:
    action_key_import = 'from "./workspace-action-key.js?v=20260803.os4.4"'
    assert action_key_import in APP_JS
    assert action_key_import in LOADER
    assert action_key_import in CORE

    navigate = _between(APP_JS, "function navigate(", "\nfunction clearAuthenticatedState(")
    replace_branch = _between(navigate, "if (replace)", "} else if")
    assert replace_branch.index("window.history.replaceState") < replace_branch.index(
        "state.route = parseRoute()"
    )
    assert replace_branch.index("state.route = parseRoute()") < replace_branch.index(
        "window.ContentEngineDesktopV4?.syncRoute?.()"
    )
    assert replace_branch.index("window.ContentEngineDesktopV4?.syncRoute?.()") < replace_branch.index(
        "window.ContentEngineDesktopV4Loader?.syncRoute?.()"
    )
    assert "syncRoute: handleHashChange" in CORE
    assert "syncRoute: schedule" in LOADER
    assert "const sameAction = actionKey === lastScheduledActionKey" in LOADER
    assert 'detail: Object.freeze({ route, actionKey, build: BUILD })' in LOADER
    assert 'window.addEventListener("hashchange", schedule, { passive: true })' in LOADER


def test_same_path_action_marks_scroll_as_app_restored_before_core_mount() -> None:
    render_workspace = _between(APP_JS, "function renderWorkspace(section)", "\nfunction ")
    same_section = _between(
        render_workspace,
        'if (existingShell?.dataset.workspaceSection === section && existingContent)',
        'if (\n    window.CONTENTENGINE_DESKTOP_V4 === true',
    )
    marker = "main.dataset.ceV4ActionEntry = nextActionKey"
    assert marker in same_section
    assert same_section.index(marker) < same_section.index(
        "if (existingContent.dataset.ceV4RenderSignature === contentSignature)"
    )


def test_task_next_action_marks_only_the_non_secondary_control_primary() -> None:
    actions = _between(APP_JS, "function taskActionsMarkup(item)", "\nfunction renderProductResearchSection")
    assert "secondary ? \"\" : ' data-primary-action=\"true\"'" in actions
    assert 'data-action="open-generated-content-review"' in actions
    assert 'data-primary-action="true"' in actions


def test_production_dock_and_tools_match_the_single_action_hierarchy() -> None:
    dock_routes = _route_array("ROUTES")
    tool_routes = _route_array("SECONDARY_ROUTES")
    assert dock_routes == [
        "/workspace/home",
        "/workspace/board",
        "/workspace/generation",
        "/workspace/review",
        "/workspace/placement",
        "/workspace/stats",
    ]
    assert tool_routes == [
        "/workspace/research",
        "/workspace/team",
        "/workspace/feedback",
    ]
    assert "/learn" not in dock_routes + tool_routes
    assert 'ROUTES.forEach((item)' in CORE
    assert 'SECONDARY_ROUTES.forEach((item)' in CORE
    assert 'route: "/learn"' not in CORE
    assert '"/learn"' not in LOADER
    assert "workspace-desktop-academy" not in LOADER
    assert "academy" not in INDEX.casefold()
    assert 'if (!isWorkspaceRoute(route) || !hasAuthenticatedWorkspace())' in CORE
    assert 'flowbar.setAttribute("aria-label", "Путь создания контента: 6 этапов")' in CORE


def test_tools_only_expose_routes_published_by_the_permission_checked_shell() -> None:
    assert 'data-workspace-authorized-routes="${escapeHtml(authorizedRoutes)}"' in APP_JS
    persistent_shell = _between(APP_JS, "function syncPersistentWorkspaceShell(", "\nfunction renderWorkspace(")
    assert "shell.dataset.workspaceAuthorizedRoutes = visibleWorkspaceTabs()" in persistent_shell
    assert "shell.dataset.workspaceRole" in persistent_shell

    authorization = _between(CORE, "function secondaryRouteIsAuthorized(", "\nfunction createToolsMenuItem(")
    sync = _between(CORE, "function syncToolsMenu(", "\nfunction closeToolsMenu(")
    assert "shell?.dataset.workspaceAuthorizedRoutes" in authorization
    assert "if (declaredRoutes.length) return declaredRoutes.includes(route)" in authorization
    assert 'const navigation = q(".workspace-nav", shell)' in authorization
    assert "SECONDARY_ROUTES.filter((item) => secondaryRouteIsAuthorized(item.route))" in sync
    assert "existing.forEach((link) => link.remove())" in sync


def test_same_path_views_animate_content_without_replacing_the_mac_shell() -> None:
    render = _between(APP_JS, "function renderWorkspace(section)", "\nconst WORKSPACE_SCROLL_OWNERS")
    settle = _between(APP_JS, "function settleRouteView(", "\nfunction authRedirectUrl(")
    hashchange = _between(APP_JS, 'window.addEventListener("hashchange", () => {', '\n  window.addEventListener("resize"')

    assert "function workspaceViewIdentity(section)" in APP_JS
    assert "state.route.query.toString()" in APP_JS
    assert "shell.dataset.workspaceActionKey = workspaceActionKey(state.route)" in APP_JS
    assert "shell.dataset.workspaceView = workspaceViewIdentity(section)" in APP_JS
    assert "const sameAction = previousActionKey === nextActionKey" in render
    assert "const viewChanged = existingShell.dataset.workspaceView !== workspaceViewIdentity(section)" in render
    assert "const preserveWorkspaceContext = existingShell.dataset.workspaceRoute === state.route.path" in render
    assert "sameAction ? captureWorkspaceFocus(existingContent) : null" in render
    assert "sameAction ? captureWorkspaceScroll(existingContent) : []" in render
    assert "!sameAction && preserveWorkspaceContext" in render
    assert "samePathFocusedControl" in render
    assert "samePathScrollSnapshot" in render
    assert "else if (preserveWorkspaceContext)" in render
    assert "if (revealLoadedContent || viewChanged) revealWorkspaceContent(existingContent)" in render
    assert "const preserveWorkspaceContext = previousPath === state.route.path" in hashchange
    assert "state.routeTransition = actionChanged && !preserveWorkspaceContext" in hashchange
    assert "preserveWorkspaceContext = false" in settle
    assert settle.index("if (preserveWorkspaceContext) return") < settle.index(
        "resetWorkspaceRouteEntry"
    )
    assert "const workspaceRevealTimers = new WeakMap()" in APP_JS
    assert "if (prefersReducedMotion()) return" in APP_JS
    assert "#workspace-content.ce-v4-content-reveal > .page-wrap" in MOTION_CSS
    assert "prefers-reduced-motion: reduce" in MOTION_CSS


def test_dock_recenters_on_viewport_changes_without_retained_webkit_transform() -> None:
    dock = _between(CORE, "function updateDock(", "\nfunction updateMenubar(")
    viewport = _between(CORE, "function handleViewportChange(", "\nfunction handlePointerDown(")
    for listener in (
        'window.addEventListener("resize", handleViewportChange',
        'window.addEventListener("orientationchange", handleViewportChange',
        'window.visualViewport?.addEventListener("resize", handleViewportChange',
    ):
        assert listener in CORE
    assert "updateDock({ immediate: true })" in viewport
    assert viewport.count("window.requestAnimationFrame") == 2
    assert "if (window.innerWidth > 680)" in dock
    assert 'glass.scrollTo({ left: 0, behavior: "auto" })' in dock
    assert "glass.scrollWidth - glass.clientWidth" in dock
    assert 'behavior: immediate || REDUCED_MOTION.matches ? "auto" : "smooth"' in dock
    assert "new ResizeObserver(handleViewportChange)" in CORE
    assert "new MutationObserver(handleViewportChange)" in CORE
    assert 'observe(glass, { childList: true })' in CORE
    assert ".ce-v4-dock__glass::before" in MOTION_CSS
    assert ".ce-v4-dock__glass::after" in MOTION_CSS
    assert "flex: 0 0 calc(50% - 22.5px)" in MOTION_CSS
    dock_motion = _between(
        MOTION_CSS,
        "body.contentengine-desktop-v4 .ce-v4-dock__glass {",
        "\n}",
    )
    assert "animation-fill-mode: none !important" in dock_motion
    assert " both " not in dock_motion


def test_team_health_and_budget_remain_distinct_action_views() -> None:
    team = _between(APP_JS, "function renderTeamSection(sectionState)", "\nfunction managerDashboardSectionMarkup(")
    assert 'teamView === "health"' in team
    assert '<section class="team-health-panel">${managerDashboardSectionMarkup()}</section>' in team
    assert '["budget", "campaigns", "campaign", "new-campaign"].includes(teamView)' in team
    assert "managerGenerationSpendMarkup(state.generationSpend" in team
    assert 'view: teamView === "budget" ? "policy" : teamView' in team


def test_menubar_notification_is_an_inline_route_not_an_overlay() -> None:
    menubar = _between(CORE, "function ensureMenubar(", "\nfunction updateClock(")
    notification = _between(
        menubar,
        'const notifications = iconButton(',
        'const tools = create("div", "ce-v4-menubar__tools")',
    )
    assert 'notifications.dataset.ceV4Notifications = "/workspace/work?view=notifications"' in notification
    assert 'notifications.setAttribute("aria-pressed", "false")' in notification
    assert "navigate(notificationControl.dataset.ceV4Notifications)" in menubar
    for overlay_marker in ("overlayBase", "dialog", "drawer", "backdrop", "aria-modal"):
        assert overlay_marker not in notification
    assert 'routePath() === "/workspace/work" && routeQuery().get("view") === "notifications"' in CORE
    assert 'notifications.setAttribute("aria-pressed", String(active))' in CORE
    assert 'class="card card-pad notification-inline" data-notification-view' in MY_WORK
    assert ".ce-v4-menubar__actions" in CORE_CSS


def test_only_payout_reject_is_the_visual_danger_primary() -> None:
    payout = _between(APP_JS, "function payoutDecisionMarkup(item)", "\nfunction renderTasksSection")
    assert payout.count('data-primary-action="true"') == 1
    assert 'class="btn btn-danger btn-small" type="submit" data-primary-action="true"' in payout
    assert 'class="btn btn-secondary btn-small" type="button" data-action="decide-payout"' in payout
    assert 'data-decision="approve"' in payout
    assert ".btn-danger {" in STYLES
