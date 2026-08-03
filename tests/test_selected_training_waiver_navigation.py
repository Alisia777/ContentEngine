from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
LEGACY_DESKTOP = (APP_DIR / "workspace-desktop-os.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_one_authenticated_start_policy_handles_login_password_and_root() -> None:
    policy = _between(
        APP,
        "function authenticatedStartPath()",
        "function establishDefaultRoute()",
    )
    assert 'return hasWorkspaceAccess() ? "/workspace/home" : "/learn";' in policy
    assert 'if (membershipLockDetails()) return "/access-locked";' in policy

    default_route = _between(APP, "function establishDefaultRoute()", "function destroyAccountVisualController")
    login = _between(APP, "async function submitLogin", "async function submitReset")
    password = _between(APP, "async function submitPassword", "async function submitCourseKnowledgeCheck")
    assert 'navigate(authenticatedStartPath(), true);' in default_route
    assert 'navigate(authenticatedStartPath(), true);' in login
    assert 'navigate(authenticatedStartPath(), true);' in password
    assert 'else navigate("/learn", true);' not in password


def test_active_waiver_blocks_direct_academy_routes_without_email_allowlist() -> None:
    render = _between(APP, "function render()", "function renderLogin")
    guard = (
        'if (trainingAccessWaiverActive() && path.startsWith("/learn")) {'
    )
    assert guard in render
    assert 'navigate(authenticatedStartPath(), true);' in render[render.index(guard) :]
    assert render.index(guard) < render.index('if (path === "/learn")')
    for identity in ("guest", "klimov", "artiukhins"):
        assert identity not in APP.casefold()


def test_waived_workspace_hides_all_academy_deep_links() -> None:
    scaffold = _between(APP, "function workspaceScaffold", "function refreshNotificationLayer")
    mobile = _between(APP, "function mobileNavMarkup", "async function loadSection")
    header = _between(APP, "function pageHeader", "function factoryFlowMarkup")
    generation_repair = _between(
        APP,
        "function generationRepairMarkup",
        "function generationHookPatternLabel",
    )
    generation_learning = _between(
        APP,
        "function generationLearningMarkup",
        "function syncGenerationLearningStatus",
    )

    assert 'const learningLinks = trainingAccessWaiverActive() ? ""' in scaffold
    assert 'const workspaceLearningLinks = trainingAccessWaiverActive() ? ""' in mobile
    assert 'const guideLink = trainingAccessWaiverActive()' in header
    assert "${learningLinks}" in scaffold
    assert "${workspaceLearningLinks}" in mobile
    assert "${guideLink}" in header
    for generation_markup in (generation_repair, generation_learning):
        assert "const training = trainingAccessWaiverActive()" in generation_markup
        assert "? null" in generation_markup


def test_global_desktop_never_mounts_over_academy() -> None:
    routes = _between(CORE, "const ROUTES", "const STAGES")
    route_policy = _between(CORE, "function routeMatches", "function navigate")
    mount = _between(CORE, "function mount()", "function scheduleMount")
    operations = _between(LOADER, "operations:", "review:")

    assert 'route: "/learn"' not in routes
    assert 'return route === expected;' in route_policy
    assert 'return route.startsWith("/workspace/");' in route_policy
    assert 'route === "/learn"' not in route_policy
    assert 'route.startsWith("/learn/")' not in route_policy
    assert "hasAuthenticatedWorkspace()" in mount
    assert "delete document.documentElement.dataset.contentengineOs;" in mount
    assert 'route === "/learn"' not in operations
    assert 'route.startsWith("/learn/")' not in operations


def test_academy_adapter_remains_available_for_users_without_waiver() -> None:
    academy = _between(LOADER, "academy:", "generation:")
    assert 'route === "/learn" || route.startsWith("/learn/")' in academy
    assert "workspace-academy-os-v2.js" in academy
    assert "workspace-academy-lab-v3.js" in academy


def test_legacy_global_dock_stays_retired_without_removing_academy_local_dock() -> None:
    mac_dock = _between(
        LEGACY_DESKTOP,
        "function mountMacDock",
        "function resetDockMagnification",
    )
    academy_home = _between(
        LEGACY_DESKTOP,
        "function setupAcademyHome",
        "function setupAcademyCourse",
    )

    assert "window.CONTENTENGINE_DESKTOP_V4 === true" in mac_dock
    assert "route === LEARN_ROUTE" in mac_dock
    assert 'qa(".ce-mac-dock").forEach((dock) => dock.remove());' in mac_dock
    assert 'document.body.classList.remove("ce-os-dock-visible");' in mac_dock
    assert 'class="academy-os-dock"' in academy_home


def test_global_desktop_shortcuts_require_an_authenticated_workspace() -> None:
    keydown = _between(CORE, "function handleKeydown", "function handleScroll")

    guard = "if (!isWorkspaceRoute() || !hasAuthenticatedWorkspace()) return;"
    assert guard in keydown
    assert keydown.index(guard) < keydown.index("event.preventDefault()")
