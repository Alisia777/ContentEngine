from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")


def test_account_launch_center_is_reachable_from_the_live_portal() -> None:
    assert 'from "./account-launch-view.js?v=20260715.4"' in APP
    assert 'from "./account-launch-guides.js?v=20260715.4"' in (
        ROOT / "web" / "app" / "account-launch-view.js"
    ).read_text(encoding="utf-8")
    assert "const accountLaunchSlug = accountLaunchSlugFromPath(path);" in APP
    assert "renderAccountLaunch(accountLaunchSlug);" in APP
    assert 'href="#${ACCOUNT_LAUNCH_PATH}"' in APP
    assert 'form.id === "account-ad-form"' in APP
    assert 'product_focus: values.get("product_focus")' in APP
    assert "purchase_focus" not in APP
    assert 'event.target.matches("[data-account-check]")' in APP
    assert "clearAccountLaunchChecks(state.user?.id);" in APP
    assert './account-launch.css?v=20260715.4' in INDEX
    assert 'const ACCOUNT_VISUAL_MODULE_URL = "./account-launch-visual-examples.js?v=20260715.4"' in APP
    assert "await import(ACCOUNT_VISUAL_MODULE_URL)" in APP
    assert "visualModule.mountAccountLaunchVisualExamples(visualRoot" in APP
    assert "lockPlatform: true" in APP
    assert "state.accountVisualStates.set(current.slug, current.instance.getState())" in APP
    assert "Account launch visual examples failed" in APP
    assert './account-launch-visual-examples.css?v=20260715.4' in INDEX
    assert './first-shift-full-scenario.css?v=20260715.4' in INDEX


def test_manager_dashboard_uses_the_scoped_rpc_and_live_handlers() -> None:
    assert 'managerDashboard: "creator_manager_dashboard"' in API
    assert re.search(
        r"managerDashboard\(\)\s*\{\s*return this\.call\(RPC\.managerDashboard, this\.withOrganization\(\{\}\)\);\s*\}",
        API,
    )
    assert 'from "./manager-dashboard-view.js?v=20260715.4"' in APP
    assert "state.api.managerDashboard()" in APP
    assert "managerDashboardMarkup(dashboard.data || {})" in APP
    for action in (
        "refresh-manager-dashboard",
        "retry-manager-invite",
        "send-manager-recovery",
        "copy-manager-reminder",
    ):
        assert f'action === "{action}"' in APP
    assert './manager-dashboard.css?v=20260715.4' in INDEX
    assert "MANAGER_DASHBOARD_MAX_AGE_MS" in APP
    assert "state.managerDashboard.updatedAt" in APP
    assert "reserveManagerEmailAction(state.managerRecoveryCooldowns, email)" in APP
    assert "reserveManagerEmailAction(state.managerInviteCooldowns, normalizedEmail)" in APP
    assert "Отправить восстановление может только сертифицированный руководитель" in APP
    assert APP.count('href="#${ACCOUNT_LAUNCH_PATH}"') >= 4


def test_release_assets_share_one_cache_version() -> None:
    assert './styles.css?v=20260715.4' in INDEX
    assert './config.js?v=20260715.4' in INDEX
    assert './app.js?v=20260715.4' in INDEX
    assert './supabase-api.js?v=20260715.4' in APP
    assert './catalog.js?v=20260715.4' in APP
