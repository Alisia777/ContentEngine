from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
BUILD = "20260803.os4.4"

ROOT_INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
INDEX = (APP / "index.html").read_text(encoding="utf-8")
APP_JS = (APP / "app.js").read_text(encoding="utf-8")
MANIFEST = json.loads((APP / "build.json").read_text(encoding="utf-8"))
GUARD = (APP / "workspace-build-guard.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CORE_CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
STABILITY_CSS = (APP / "workspace-os-v4-stability.css").read_text(encoding="utf-8")
MOTION_CSS = (APP / "workspace-os-v4-motion.css").read_text(encoding="utf-8")
STARTUP_ROUTE = (APP / "startup-route.js").read_text(encoding="utf-8")
WEBKIT_FULL_MATRIX = (ROOT / "tests" / "webkit_full_app_matrix_v45_probe.cjs").read_text(
    encoding="utf-8"
)


def _route_array(name: str) -> list[str]:
    match = re.search(
        rf"const {name} = Object\.freeze\(\[(.*?)\]\);",
        CORE,
        flags=re.DOTALL,
    )
    assert match, f"missing {name}"
    return re.findall(r'route: "([^"]+)"', match.group(1))


def test_v44_build_and_cache_keys_are_consistent() -> None:
    assert MANIFEST["id"] == BUILD
    assert f'content="{BUILD}"' in ROOT_INDEX
    assert f'content="{BUILD}"' in INDEX
    assert f'const CURRENT_BUILD = "{BUILD}"' in GUARD
    assert f'const BUILD = "{BUILD}"' in LOADER
    assert f'const BUILD = "{BUILD}"' in CORE
    for asset in (
        "startup-route.js",
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
        "my-work-view.js",
        "product-research-view.js",
        "training-media-cards.js",
        "training-practical-review.js",
        "workspace-board-view.js",
    ):
        assert f'from "./{dependency}?v={BUILD}"' in APP_JS


def test_full_webkit_matrix_has_mac_retina_and_route_latency_modes() -> None:
    for marker in (
        "CE_MATRIX_DEVICE_SCALE_FACTOR",
        "deviceScaleFactor: matrixDeviceScaleFactor",
        "snapshot.settleMs = Date.now() - routeStartedAt",
        "routeP95 <= 2000",
        "routeMax <= 4000",
        "routePerformance:",
    ):
        assert marker in WEBKIT_FULL_MATRIX


def test_startup_normalizer_runs_before_app_without_hijacking_workspace_routes() -> None:
    startup = f'./startup-route.js?v={BUILD}'
    assert startup in INDEX
    assert INDEX.index(startup) < INDEX.index(f'./app.js?v={BUILD}')
    assert 'if (!/^#\\/academy(?:\\/|\\?|$)/u.test(hash)) return;' in STARTUP_ROUTE
    assert 'hash.replace(/^#\\/academy/u, "#/learn")' in STARTUP_ROUTE
    assert "/workspace/" not in STARTUP_ROUTE


def test_replace_navigation_notifies_the_loader_and_live_desktop_core() -> None:
    event_name = '"contentengine:route-replaced"'
    assert f"const ROUTE_REPLACED_EVENT = {event_name}" in APP_JS
    assert f"const ROUTE_REPLACED_EVENT = {event_name}" in LOADER
    assert f"const ROUTE_REPLACED_EVENT = {event_name}" in CORE

    navigate = APP_JS[APP_JS.index("function navigate(") : APP_JS.index("\nfunction clearAuthenticatedState(")]
    replace_branch = navigate[navigate.index("if (replace)") : navigate.index("} else if")]
    assert replace_branch.index("window.history.replaceState") < replace_branch.index(
        "window.dispatchEvent(new CustomEvent(ROUTE_REPLACED_EVENT"
    )
    assert replace_branch.index(
        "window.dispatchEvent(new CustomEvent(ROUTE_REPLACED_EVENT"
    ) < replace_branch.index("render();")
    assert 'window.addEventListener(ROUTE_REPLACED_EVENT, schedule, { passive: true })' in LOADER
    assert (
        'window.addEventListener(ROUTE_REPLACED_EVENT, handleHashChange, '
        '{ capture: true, passive: true })'
    ) in CORE


def test_production_dock_and_tools_have_fixed_route_counts_without_academy() -> None:
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
        "/workspace/tasks",
        "/workspace/work",
        "/workspace/media",
        "/workspace/payouts",
        "/workspace/research",
        "/workspace/feedback",
        "/workspace/team",
    ]
    assert "/learn" not in dock_routes + tool_routes
    assert 'ROUTES.forEach((item)' in CORE
    assert 'SECONDARY_ROUTES.forEach((item)' in CORE
    assert '"/learn"' not in CORE
    assert '"/learn"' not in LOADER
    assert "workspace-desktop-academy" not in LOADER
    assert "academy" not in INDEX.casefold()
    assert 'if (!isWorkspaceRoute(route) || !hasAuthenticatedWorkspace())' in CORE


def test_tools_only_expose_routes_published_by_the_permission_checked_shell() -> None:
    assert 'data-workspace-available-sections="${escapeHtml(availableSections)}"' in APP_JS
    assert "function workspaceAvailableSectionsValue()" in APP_JS
    assert "function syncWorkspaceAvailableSections(shell)" in APP_JS
    assert "syncPersistentWorkspaceShell(existingShell, section);" in APP_JS
    persistent_shell = APP_JS[
        APP_JS.index("function syncPersistentWorkspaceShell(") : APP_JS.index("\nfunction renderWorkspace(")
    ]
    assert "syncWorkspaceAvailableSections(shell);" in persistent_shell
    assert "function availableWorkspaceSections()" in CORE
    assert "function workspaceRouteAvailable(route)" in CORE
    assert "function syncToolsAvailability()" in CORE
    assert 'link.hidden = !available;' in CORE
    assert '.filter((item) => !item.hidden)' in CORE
    mount = CORE[CORE.index("function mount()") : CORE.index("\nfunction scheduleMount()")]
    assert mount.index("ensureMenubar();") < mount.index("syncToolsAvailability();") < mount.index("updateMenubar();")


def test_same_section_views_animate_content_without_resetting_workspace_context() -> None:
    render = APP_JS[APP_JS.index("function renderWorkspace(section)") : APP_JS.index("\nconst WORKSPACE_SCROLL_OWNERS")]
    settle = APP_JS[APP_JS.index("function settleRouteView(") : APP_JS.index("\nfunction authRedirectUrl(")]
    assert "function workspaceViewIdentity(section)" in APP_JS
    assert "state.route.query.toString()" in APP_JS
    assert 'data-workspace-view="${escapeHtml(workspaceViewIdentity(activeSection))}"' in APP_JS
    assert "const viewChanged = existingShell.dataset.workspaceView !== workspaceViewIdentity(section);" in render
    assert "syncPersistentWorkspaceShell(existingShell, section);" in render
    assert "if (revealLoadedContent || viewChanged) revealWorkspaceContent(existingContent);" in render
    assert "state.routeTransition = !preserveWorkspaceContext;" in APP_JS
    assert "function settleRouteView({ preserveWorkspaceContext = false } = {})" in settle
    assert settle.index("if (preserveWorkspaceContext) return;") < settle.index("window.scrollTo")
    assert "#workspace-content.ce-v4-content-reveal > .page-wrap" in MOTION_CSS
    assert "prefers-reduced-motion: reduce" in MOTION_CSS


def test_dock_recenters_on_viewport_changes_without_retained_webkit_transform() -> None:
    dock = CORE[CORE.index("function updateDock(") : CORE.index("\nfunction updateMenubar(")]
    viewport = CORE[CORE.index("function handleViewportChange(") : CORE.index("\nfunction handlePointerDown(")]
    for listener in (
        'window.addEventListener("resize", handleViewportChange',
        'window.addEventListener("orientationchange", handleViewportChange',
        'window.visualViewport?.addEventListener("resize", handleViewportChange',
    ):
        assert listener in CORE
    assert 'updateDock({ immediate: true });' in viewport
    assert viewport.count("window.requestAnimationFrame") == 2
    assert 'if (window.innerWidth > 680)' in dock
    assert 'glass.scrollTo({ left: 0, behavior: "auto" })' in dock
    assert "glass.scrollWidth - glass.clientWidth" in dock
    assert 'behavior: immediate || REDUCED_MOTION.matches ? "auto" : "smooth"' in dock
    assert "new ResizeObserver(handleViewportChange)" in CORE
    assert "new MutationObserver(handleViewportChange)" in CORE
    assert 'observe(glass, { childList: true })' in CORE
    assert ".ce-v4-dock__glass::before" in MOTION_CSS
    assert ".ce-v4-dock__glass::after" in MOTION_CSS
    assert "flex: 0 0 calc(50% - 22.5px)" in MOTION_CSS
    dock_motion = MOTION_CSS[
        MOTION_CSS.index("body.contentengine-desktop-v4 .ce-v4-dock__glass {") :
        MOTION_CSS.index("\n}", MOTION_CSS.index("body.contentengine-desktop-v4 .ce-v4-dock__glass {"))
    ]
    assert "animation-fill-mode: none !important" in dock_motion
    assert " both " not in dock_motion


def test_team_health_is_read_only_and_budget_remains_its_own_action_view() -> None:
    team = APP_JS[APP_JS.index("function renderTeamSection(") : APP_JS.index("\nfunction teamMembersTable(")]
    assert 'teamView === "health"' in team
    assert 'managerDashboardSectionMarkup({ includeSpend: false })' in team
    assert 'function managerDashboardSectionMarkup({ includeSpend = true } = {})' in team
    dashboard = team[team.index("function managerDashboardSectionMarkup(") :]
    assert "const spendMarkup = includeSpend" in dashboard
    assert '? managerGenerationSpendMarkup(state.generationSpend' in dashboard


def test_menubar_notification_is_an_inline_route_link_not_an_overlay() -> None:
    menubar = CORE[CORE.index("function ensureMenubar(") : CORE.index("\nfunction updateClock(")]
    notification = menubar[
        menubar.index('const notifications = create("a"') : menubar.index("const tools =")
    ]
    assert 'notifications.href = "#/workspace/work?view=notifications"' in notification
    assert 'notifications.dataset.ceV4Notifications = "true"' in notification
    assert 'notifications.setAttribute("aria-label", "Уведомления")' in notification
    for overlay_marker in ("overlayBase", "dialog", "drawer", "backdrop", "aria-modal"):
        assert overlay_marker not in notification
    assert 'routeQuery().get("view") === "notifications"' in CORE
    assert 'notificationsActive && link.dataset.ceV4ToolsRoute === "/workspace/work"' in CORE
    assert 'notifications.setAttribute("aria-current", "page")' in CORE
    assert ".ce-v4-menubar__notifications" in CORE_CSS


def test_only_explicit_payout_reject_action_gets_danger_primary_fill() -> None:
    assert APP_JS.count('data-danger-primary="true"') == 1
    assert '[data-danger-primary="true"]' in STABILITY_CSS
    assert "linear-gradient(135deg, #ff9d91 0%, #dc4d48 100%)" in STABILITY_CSS
    assert '.btn-danger' not in STABILITY_CSS
