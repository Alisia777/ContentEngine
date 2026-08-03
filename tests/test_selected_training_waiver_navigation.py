from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web/app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE_STYLES = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
ACTIVE_INDEX = re.sub(r"<!--.*?-->", "", INDEX, flags=re.DOTALL)


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def test_one_authenticated_start_policy_handles_login_password_and_root() -> None:
    policy = _between(
        APP,
        "function authenticatedStartPath()",
        "function establishDefaultRoute()",
    )
    assert 'if (academyRequired()) return "/learn";' in policy
    assert "WORKSPACE_START_PATH" in policy
    assert "WORKSPACE_ACCESS_REQUIRED_PATH" in policy
    assert policy.index("academyRequired()") < policy.index("hasWorkspaceAccess()")
    assert 'if (membershipLockDetails()) return "/access-locked";' in policy

    default_route = _between(APP, "function establishDefaultRoute()", "function destroyAccountVisualController")
    login = _between(APP, "async function submitLogin", "async function submitReset")
    password = _between(APP, "async function submitPassword", "async function submitCourseKnowledgeCheck")
    assert 'navigate(authenticatedStartPath(), true);' in default_route
    assert 'navigate(authenticatedStartPath(), true);' in login
    assert 'navigate(authenticatedStartPath(), true);' in password
    assert 'else navigate("/learn", true);' not in password


def test_direct_academy_routes_are_reachable_only_while_the_gate_is_required() -> None:
    render = _between(APP, "function render()", "function renderLogin")
    academy_gate = _between(
        render,
        "if (academyRequired()) {",
        '\n  if (path === "/learn" || path.startsWith("/learn/"))',
    )
    redirect = _between(
        render,
        'if (path === "/learn" || path.startsWith("/learn/"))',
        "\n  }",
    )
    route_access = _between(
        APP,
        "function academyRoutesReachable(bootstrap = state.bootstrap)",
        "function hasWorkspaceAccess",
    )

    assert "return academyRequired(bootstrap);" in route_access
    assert "renderLearningHome()" in academy_gate
    assert "renderFirstShift()" in academy_gate
    assert "accountLaunchSlugFromPath(path)" in academy_gate
    assert "navigate(authenticatedStartPath(), true);" in redirect
    assert render.index("if (academyRequired()) {") < render.index(
        'if (path === "/learn" || path.startsWith("/learn/"))'
    )
    for identity in ("guest", "klimov", "artiukhins"):
        assert identity not in APP.casefold()


def test_workspace_hides_academy_deep_links_when_the_gate_is_not_reachable() -> None:
    scaffold = _between(APP, "function workspaceScaffold", "function refreshNotificationLayer")
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

    assert "#/learn" not in scaffold
    assert "academyRoutesReachable()" in header
    assert "${guideLink}" in header
    for generation_markup in (generation_repair, generation_learning):
        assert "const training = academyRoutesReachable()" in generation_markup
        assert ": null;" in generation_markup


def test_global_desktop_never_mounts_over_academy() -> None:
    routes = _between(CORE, "const ROUTES", "const ALL_ROUTES")
    route_policy = _between(CORE, "function isWorkspaceRoute", "function hasAuthenticatedWorkspace")
    mount = _between(CORE, "function mount()", "function scheduleMount")
    loader_policy = _between(LOADER, "function isManagedRoute", "function setLoading")

    assert 'route: "/learn"' not in routes
    assert 'return route.startsWith("/workspace/");' in route_policy
    assert 'route === "/learn"' not in route_policy
    assert 'route.startsWith("/learn/")' not in route_policy
    assert "hasAuthenticatedWorkspace()" in mount
    assert 'document.documentElement.removeAttribute("data-contentengine-os")' in mount
    assert 'return route.startsWith("/workspace/");' in loader_policy
    assert "/learn" not in loader_policy


def test_academy_has_no_v4_route_adapter_or_lazy_desktop_assets() -> None:
    route_assets = _between(LOADER, "const ROUTE_ASSETS", "function routePath")
    assert "finder:" in route_assets
    assert "academy:" not in route_assets
    assert "/learn" not in route_assets
    assert "workspace-academy-os-v2" not in LOADER
    assert "workspace-academy-lab-v3" not in LOADER


def test_legacy_global_and_academy_local_docks_are_outside_the_active_graph() -> None:
    assert "workspace-desktop-os.js" not in ACTIVE_INDEX
    assert "workspace-academy-os-v2.js" not in ACTIVE_INDEX
    assert "workspace-academy-lab-v3.js" not in ACTIVE_INDEX
    assert "workspace-desktop-os" not in LOADER

    guard = re.search(
        r"/\* Retired nested Academy chrome.*?\*/(?P<body>.*?)\}",
        CORE_STYLES,
        flags=re.DOTALL,
    )
    assert guard is not None
    for selector in (
        ".academy-os-dock",
        ".academy-course-os-dock",
        ".academy-v2-dock",
        ".learning-command-bar",
    ):
        assert selector in guard.group("body")
    assert "display: none !important" in guard.group("body")


def test_global_desktop_shortcuts_require_an_authenticated_workspace() -> None:
    keydown = _between(CORE, "function handleKeydown", "function handleScroll")

    guard = "if (!isWorkspaceRoute() || !hasAuthenticatedWorkspace()) return;"
    assert guard in keydown
    assert keydown.index(guard) < keydown.index("event.preventDefault()")
