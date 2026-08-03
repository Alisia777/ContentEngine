from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
CONTEXT = (APP_DIR / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
STARTUP = (APP_DIR / "startup-route.js").read_text(encoding="utf-8")
CORE_CSS = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _function_source(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.index(f"\nfunction {next_name}(", start)
    return source[start:end].strip()


def test_v44_preserves_mandatory_learning_and_normalizes_only_the_obsolete_alias() -> None:
    assert 'content="20260803.os4.4"' in INDEX
    assert './startup-route.js?v=20260803.entry1' in INDEX
    assert INDEX.index("./startup-route.js") < INDEX.index("./app.js")
    assert '/^#\\/academy' in STARTUP
    assert 'hash.replace(/^#\\/academy/u, "#/learn")' in STARTUP
    assert '#/workspace/home' not in STARTUP
    assert "history.replaceState" in STARTUP
    assert "academy" not in INDEX.casefold()


def test_every_authenticated_entry_uses_one_route_resolver() -> None:
    resolver = _between(
        APP,
        "function authenticatedStartPath() {",
        "\n}\n\nfunction establishDefaultRoute",
    )
    for route in (
        'return "/login"',
        'return "/set-password"',
        'return "/access-locked"',
        'return "/learn"',
        "WORKSPACE_START_PATH",
        "WORKSPACE_ACCESS_REQUIRED_PATH",
    ):
        assert route in resolver
    assert "academyRequired()" in resolver

    default_route = _between(
        APP,
        "function establishDefaultRoute() {",
        "\n}\n\nfunction destroyAccountVisualController",
    )
    assert "navigate(authenticatedStartPath(), true)" in default_route
    assert 'next.hash = ["invite", "recovery"].includes(purpose) ? "#/set-password" : "#/"' in APP
    assert APP.count("navigate(authenticatedStartPath(), true)") >= 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node is unavailable")
def test_authenticated_start_matrix_executes_the_current_route_policy() -> None:
    functions = "\n\n".join(
        (
            _function_source(APP, "membershipLockDetails", "hasOperationalWorkspaceRole"),
            _function_source(APP, "hasOperationalWorkspaceRole", "practicalProjectApproved"),
            _function_source(APP, "practicalProjectApproved", "trainingAccessWaiverActive"),
            _function_source(APP, "trainingAccessWaiverActive", "academyRequired"),
            _function_source(APP, "academyRequired", "hasWorkspaceAccess"),
            _function_source(APP, "hasWorkspaceAccess", "prerequisitesComplete"),
            _function_source(APP, "authenticatedStartPath", "establishDefaultRoute"),
        )
    )
    harness = r"""
const state = { session: { user: { id: "qa" } }, forcePassword: false, bootstrap: null };
const MEMBERSHIP_LOCK_COPY = Object.freeze({
  membership_suspended: Object.freeze({ title: "suspended" }),
  membership_revoked: Object.freeze({ title: "revoked" }),
});
const OPERATIONAL_WORKSPACE_ROLES = new Set(["owner", "admin", "producer", "reviewer", "operator"]);
const REQUIRED_MODULE_CODES = Object.freeze(["course-a", "course-b"]);
const WORKSPACE_START_PATH = "/workspace/home";
const WORKSPACE_ACCESS_REQUIRED_PATH = "/access-required";
function normalizeTrainingPracticalProject(value) {
  return { approved: value?.approved === true };
}
function trainingCatalogReady() { return true; }

__FUNCTIONS__

const training = ({ waiver = false, completed = false } = {}) => ({
  accessWaiver: { active: waiver, scope: waiver ? "workspace_generation" : "" },
  completedModules: completed ? [...REQUIRED_MODULE_CODES] : [],
  practicalProject: { approved: completed },
  exam: { passed: completed },
});
const rows = [
  {
    name: "learning_without_waiver",
    bootstrap: {
      accessState: "learning",
      workspaceAccess: false,
      membership: { role: "operator" },
      training: training(),
    },
    expected: "/learn",
  },
  {
    name: "active_workspace_generation_waiver",
    bootstrap: {
      accessState: "learning",
      workspaceAccess: true,
      membership: { role: "operator" },
      training: training({ waiver: true }),
    },
    expected: "/workspace/home",
  },
  {
    name: "completed_training_workspace_open",
    bootstrap: {
      accessState: "workspace_open",
      workspaceAccess: true,
      membership: { role: "operator" },
      training: training({ completed: true }),
    },
    expected: "/workspace/home",
  },
  {
    name: "missing_membership_and_access",
    bootstrap: {
      accessState: "",
      workspaceAccess: false,
      membership: {},
      training: training(),
    },
    expected: "/access-required",
  },
];
const result = rows.map((row) => {
  state.bootstrap = row.bootstrap;
  const actual = authenticatedStartPath();
  if (actual !== row.expected) {
    throw new Error(`${row.name}: expected ${row.expected}, received ${actual}`);
  }
  return [row.name, actual];
});
process.stdout.write(JSON.stringify(result));
""".replace("__FUNCTIONS__", functions)
    result = subprocess.run(
        [shutil.which("node"), "-e", harness],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == (
        '[["learning_without_waiver","/learn"],'
        '["active_workspace_generation_waiver","/workspace/home"],'
        '["completed_training_workspace_open","/workspace/home"],'
        '["missing_membership_and_access","/access-required"]]'
    )


def test_academy_renders_only_for_people_who_still_require_it() -> None:
    render = _between(APP, "function render() {", "\n}\n\nfunction renderLogin")
    academy_gate = _between(render, "if (academyRequired()) {", '\n  if (path === "/learn" || path.startsWith("/learn/"))')
    assert 'navigate("/learn", true)' in academy_gate
    for required_renderer in (
        "renderLearningHome",
        "renderFirstShift",
        "renderAccountLaunch",
        "renderTrainingPracticalProject",
        "renderCourse",
        "renderExam",
    ):
        assert required_renderer in academy_gate
    assert 'path === "/learn/first-shift"' in academy_gate
    assert "accountLaunchSlugFromPath(path)" in academy_gate

    legacy_guard = 'if (path === "/learn" || path.startsWith("/learn/"))'
    assert legacy_guard in render
    guard = _between(render, legacy_guard, "\n  }")
    assert "navigate(authenticatedStartPath(), true)" in guard


def test_academy_is_one_gate_screen_without_workspace_or_duplicate_navigation() -> None:
    scaffold = _between(APP, "function learningScaffold(content, activePath) {", "\n}\n\nfunction renderLearningScaffold")
    home = _between(APP, "function renderLearningHome() {", "\n}\n\nfunction renderAccountLaunch")
    assert 'class="learning-gate-shell"' in scaffold
    assert 'class="workspace-shell"' not in scaffold
    assert "learningActionSwitchMarkup" not in scaffold
    assert 'class="sidebar"' not in scaffold
    assert "mobileNavMarkup" not in scaffold
    assert 'data-primary-action="true"' in home
    assert home.count("${actionMarkup}") == 1
    assert "trainingAchievementShelfMarkup" not in home
    assert home.index("learningGateRoleMarkup()") < home.index(
        'class="learning-gate-roadmap"'
    )


def test_workspace_navigation_has_one_production_dock_and_no_academy_entry() -> None:
    scaffold = _between(APP, "function workspaceScaffold(", "\n}\n\nfunction refreshNotificationLayer")
    primary_routes = _between(CORE, "const ROUTES = Object.freeze([", "\n]);\n\nconst SECONDARY_ROUTES")
    secondary_routes = _between(CORE, "const SECONDARY_ROUTES = Object.freeze([", "\n]);\n\nconst ALL_ROUTES")

    assert "#/learn" not in scaffold
    assert "Обучение" not in scaffold
    assert 'route: "/learn"' not in primary_routes
    assert 'route: "/learn"' not in secondary_routes
    assert "Инструкции" not in secondary_routes
    assert 'menuAction("Инструкции"' not in CONTEXT
    assert '"#/learn"' not in CONTEXT
    assert "Помощь и обратная связь" in CONTEXT


def test_workspace_tabs_without_permission_open_an_explicit_access_screen_not_academy() -> None:
    screen = _between(
        APP,
        "function renderWorkspaceAccessRequired() {",
        "\n}\n\nfunction trainingAchievementShelfMarkup",
    )
    assert "Рабочее место ещё не подключено" in screen
    assert 'data-action="retry-bootstrap"' in screen


def test_menubar_search_opens_finder_without_another_window() -> None:
    menubar = _between(CORE, "function ensureMenubar() {", "\n}\n\nfunction updateClock")
    public_api = CORE[CORE.index("window.ContentEngineDesktopV4 = Object.freeze({") :]
    assert "ceV4FinderSearch" in menubar
    assert "focusFinderSearch();" in menubar
    assert "ceV4Spotlight" not in menubar
    assert "openSpotlight();" not in menubar
    assert "ce-v4-traffic" in menubar
    assert "ceV4Fullscreen" in menubar
    assert "void toggleFullscreen()" in menubar
    for retired_window in ("openMission,", "openSpotlight,", "openZen,", "closeZen,"):
        assert retired_window not in public_api


def test_secondary_menu_is_navigation_not_a_window() -> None:
    menubar = _between(CORE, "function ensureMenubar() {", "\n}\n\nfunction updateClock")
    for marker in (
        'setAttribute("aria-haspopup", "menu")',
        'setAttribute("aria-expanded", "false")',
        'setAttribute("role", "menu")',
        'setAttribute("role", "menuitem")',
        "SECONDARY_ROUTES.forEach",
        'toolsMenu.dataset.ceV4ToolsMenu = "true"',
        "link.href = `#${item.route}`",
    ):
        assert marker in menubar
    for forbidden in (
        "overlayBase",
        'setAttribute("role", "dialog")',
        'setAttribute("aria-modal"',
        "backdrop",
        "openMission",
        "openSpotlight",
        "openZen",
        "window.open",
    ):
        assert forbidden not in menubar


def test_nested_academy_chrome_has_a_global_fail_closed_guard() -> None:
    for selector in (
        ".academy-os-dock",
        ".academy-course-os-dock",
        ".academy-v2-dock",
        ".learning-command-bar",
    ):
        assert selector in CORE_CSS
    guard = re.search(
        r"/\* Retired nested Academy chrome.*?\*/(?P<body>.*?)\}",
        CORE_CSS,
        flags=re.DOTALL,
    )
    assert guard is not None
    assert "display: none !important" in guard.group("body")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is unavailable")
@pytest.mark.parametrize(
    ("hash_value", "expected_hash"),
    [
        ("#/learn", "#/learn"),
        ("#/learn/exam?step=2", "#/learn/exam?step=2"),
        ("#/academy/exam?step=2", "#/learn/exam?step=2"),
        ("#/workspace/board", "#/workspace/board"),
    ],
)
def test_startup_route_executes_without_redirect_loops(hash_value: str, expected_hash: str) -> None:
    node = shutil.which("node")
    harness = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
let current = new URL(`https://example.test/ContentEngine/${process.argv[2]}`);
const location = {};
Object.defineProperties(location, {
  href: { get: () => current.href },
  hash: { get: () => current.hash },
});
const history = {
  replaceState(_state, _title, next) { current = new URL(String(next)); },
};
vm.runInNewContext(source, { window: { location, history }, URL });
process.stdout.write(current.hash);
"""
    result = subprocess.run(
        [node, "-e", harness, str(APP_DIR / "startup-route.js"), hash_value],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == expected_hash
