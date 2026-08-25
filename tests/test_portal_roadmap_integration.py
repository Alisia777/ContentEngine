import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")
WORKSPACE_OS = (ROOT / "web" / "app" / "workspace-os-v4.js").read_text(encoding="utf-8")
BUILD_ID = json.loads((ROOT / "web" / "app" / "build.json").read_text(encoding="utf-8"))["id"]


def test_account_launch_center_is_reachable_from_the_live_portal() -> None:
    assert 'from "./account-launch-view.js?v=20260825.login-rain.4"' in APP
    assert 'from "./account-launch-guides.js?v=20260825.login-rain.4"' in (
        ROOT / "web" / "app" / "account-launch-view.js"
    ).read_text(encoding="utf-8")
    route_dispatch = APP[APP.index("function render() {") : APP.index("function renderLogin")]
    assert 'if (path === "/learn/first-shift")' in route_dispatch
    assert "renderFirstShift();" in route_dispatch
    assert "const accountLaunchSlug = accountLaunchSlugFromPath(path);" in route_dispatch
    assert "if (accountLaunchSlug !== null)" in route_dispatch
    assert "renderAccountLaunch(accountLaunchSlug);" in route_dispatch
    assert 'href="#${ACCOUNT_LAUNCH_PATH}"' in APP
    assert 'form.id === "account-ad-form"' in APP
    assert 'product_focus: values.get("product_focus")' in APP
    assert "purchase_focus" not in APP
    assert 'event.target.matches("[data-account-check]")' in APP
    assert "clearAccountLaunchChecks(state.user?.id);" in APP
    assert './account-launch.css?v=20260825.login-rain.4' in INDEX
    assert 'const ACCOUNT_VISUAL_MODULE_URL = "./account-launch-visual-examples.js?v=20260825.login-rain.4"' in APP
    assert "await import(ACCOUNT_VISUAL_MODULE_URL)" in APP
    assert "visualModule.mountAccountLaunchVisualExamples(visualRoot" in APP
    assert "lockPlatform: true" in APP
    assert "state.accountVisualStates.set(current.slug, current.instance.getState())" in APP
    assert "Account launch visual examples failed" in APP
    assert './account-launch-visual-examples.css?v=20260825.login-rain.4' in INDEX
    assert './first-shift-full-scenario.css?v=20260825.login-rain.4' in INDEX


def test_manager_dashboard_uses_the_scoped_rpc_and_live_handlers() -> None:
    assert 'managerDashboard: "creator_manager_dashboard"' in API
    assert re.search(
        r"managerDashboard\(\)\s*\{\s*return this\.call\(RPC\.managerDashboard, this\.withOrganization\(\{\}\)\);\s*\}",
        API,
    )
    assert 'from "./manager-dashboard-view.js?v=20260825.login-rain.4"' in APP
    assert 'from "./access-center-view.js?v=20260825.login-rain.4"' in APP
    assert "state.api.managerDashboard()" in APP
    assert "managerDashboardMarkup(dashboard.data || {}, state.operationalHealth)" in APP
    for action in (
        "refresh-manager-dashboard",
        "open-manager-access",
        "reset-manager-access",
        "copy-manager-reminder",
    ):
        assert f'action === "{action}"' in APP
    assert './manager-dashboard.css?v=20260825.login-rain.4' in INDEX
    assert "MANAGER_DASHBOARD_MAX_AGE_MS" in APP
    assert "state.managerDashboard.updatedAt" in APP
    assert 'const ACCESS_FUNCTION = "creator-access"' in API
    assert "inspectAccess(email)" in API
    assert "repairAccess(email, requestId" in API
    assert "state.api.inspectAccess(normalizedEmail)" in APP
    assert "state.api.repairAccess(normalizedEmail)" in APP
    assert "Проверять и восстанавливать доступ может только сертифицированный руководитель" in APP

    team = APP[
        APP.index("function renderTeamSection(sectionState) {") :
        APP.index("function managerDashboardSectionMarkup()")
    ]
    health = APP[
        APP.index("function managerDashboardSectionMarkup()") :
        APP.index("function teamMembersTable")
    ]
    assert 'teamView === "health" && state.managerDashboard.status === "idle"' in team
    assert 'teamView === "health"' in team
    assert '<section class="team-health-panel">${managerDashboardSectionMarkup()}</section>' in team
    assert 'href: "#/workspace/team?view=health"' in team
    assert "managerGenerationSpendMarkup" not in health

    assert 'new Set(["/workspace/research", "/workspace/ai", "/workspace/team"])' in WORKSPACE_OS
    assert "function routeIsAuthorized(route)" in WORKSPACE_OS
    assert "authorizedRoutes(SECONDARY_ROUTES)" in WORKSPACE_OS


def test_release_entry_assets_use_current_cache_versions() -> None:
    assert './styles.css?v=20260825.login-rain.4' in INDEX
    assert './config.js?v=20260825.login-rain.4' in INDEX
    assert f'<meta name="contentengine-build" content="{BUILD_ID}"' in INDEX
    assert './app.js?v=20260825.login-rain.4' in INDEX
    assert './workspace-os-v4-loader.js?v=20260825.login-rain.4' in INDEX
    assert f'./interface-system.css?v={BUILD_ID}' in INDEX
    assert './workspace-os-v4.css?v=20260825.login-rain.4' in INDEX
    assert f'./workspace-build-guard.js?v={BUILD_ID}' in INDEX
    assert './supabase-api.js?v=20260825.login-rain.4' in APP
    assert './catalog.js?v=20260825.login-rain.4' in APP
