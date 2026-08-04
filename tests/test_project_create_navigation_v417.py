"""Executable UI contracts for project switching and creation in Desktop v4.17."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
CORE = (ROOT / "web" / "app" / "workspace-os-v4.js").read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    start = source.index(declaration)
    body_match = re.search(r"\)\s*\{", source[start:])
    assert body_match, f"Missing JavaScript function body: {declaration}"
    opening = start + body_match.end() - 1
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated JavaScript function: {declaration}")


def _run_node(script: str) -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for project navigation contracts"
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        cwd=ROOT,
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == "ok"


def test_projects_dock_and_project_menu_have_explicit_unscoped_routes() -> None:
    navigate_primary = _function(CORE, "function navigatePrimaryRoute(")
    dock = _function(CORE, "function ensureDock(")
    update = _function(CORE, "function updateDock(")
    menu = _function(CORE, "function syncProjectSwitcher(")
    menubar = _function(CORE, "function ensureMenubar(")

    assert 'return navigate("/workspace/home", { preserveProject: false })' in navigate_primary
    assert 'const opensProjectCatalog = routeParts(destination).path === "/workspace/home"' in dock
    assert "navigatePrimaryRoute(destination)" in dock
    assert 'item.dataset.ceV4Route === "/workspace/home"' in update
    assert '? "/workspace/home"' in update

    assert 'ceV4AllProjects = "true"' in menu
    assert 'ceV4CreateProject = "true"' in menu
    assert '"owner", "admin", "producer"' in menu
    assert 'navigate("/workspace/home", { preserveProject: false })' in menubar
    assert 'navigate("/workspace/home?view=new", { preserveProject: false })' in menubar
    assert 'routeWithProject("/workspace/home", snapshot.id)' not in menu


def test_primary_project_route_drops_a_selected_project_at_runtime() -> None:
    route_parts = _function(CORE, "function routeParts(")
    route_with_project = _function(CORE, "function routeWithProject(")
    navigate = _function(CORE, "function navigate(")
    navigate_primary = _function(CORE, "function navigatePrimaryRoute(")
    script = f"""
const selectedProject = "11111111-1111-4111-8111-111111111111";
const CLOSE_TRANSIENTS_EVENT = "contentengine:v4-close-transients";
const window = {{ location: {{ hash: `#/workspace/review?project_id=${{selectedProject}}` }} }};
const document = {{ dispatchEvent: () => undefined }};
globalThis.CustomEvent = class {{ constructor(name, options) {{ this.name = name; this.detail = options?.detail; }} }};
const routeQuery = () => new URLSearchParams(`project_id=${{selectedProject}}`);
const projectContext = () => ({{ id: selectedProject }});
const workspaceRouteRequiresProject = () => false;
const explainProjectRequired = () => {{ throw new Error("unexpected-project-gate"); }};
const captureCurrentAction = () => undefined;
const closeTransientOverlays = () => undefined;
{route_parts}
{route_with_project}
{navigate}
{navigate_primary}

const destination = navigatePrimaryRoute("/workspace/home");
if (destination !== "/workspace/home") throw new Error(`destination:${{destination}}`);
if (window.location.hash !== "#/workspace/home") throw new Error(`hash:${{window.location.hash}}`);
process.stdout.write("ok");
"""
    _run_node(script)


def test_new_project_is_a_single_primary_action_surface_for_allowed_roles() -> None:
    switcher = _function(APP, "function homeProjectSwitcherMarkup(")
    script = f"""
const projectId = "22222222-2222-4222-8222-222222222222";
const state = {{
  route: {{ path: "/workspace/home", query: new URLSearchParams("view=new") }},
  sections: {{ board: {{ data: {{ capabilities: {{ manageFolders: false }} }} }} }},
  bootstrap: {{ membership: {{ role: "owner" }} }},
  projectFlow: {{
    status: "ready",
    data: {{ project_id: null, projects: [{{ id: projectId, name: "Бады" }}] }},
  }},
  workspaceBoard: {{
    busy: false,
    projectDraftName: "Август",
    projectCreateError: "",
  }},
}};
const normalizeWorkspaceBoard = (value) => value || {{ capabilities: {{ manageFolders: false }} }};
const normalizeProjectFlow = (value) => ({{
  project_id: null,
  projects: [],
  project: null,
  stages: [],
  next_action: null,
  counts: {{}},
  ...(value || {{}}),
}});
const exactProjectNextActionRoute = (_flow, id) => `/workspace/home?project_id=${{id}}`;
const storedWorkspaceProject = () => null;
const readableHomeActionTitle = (action) => action?.title || "Выберите проект";
const escapeHtml = (value) => String(value ?? "");
const formatDate = () => "сейчас";
{switcher}

const markup = homeProjectSwitcherMarkup({{
  step: "Один проект — одна цепочка",
  title: "Выберите проект",
  description: "Выберите или создайте проект.",
  href: "#/workspace/home",
  cta: "Выбрать проект",
}});
const formCount = (markup.match(/id="home-project-create-form"/gu) || []).length;
const primaryCount = (markup.match(/data-primary-action="true"/gu) || []).length;
if (!markup.includes("home-project-create-surface")) throw new Error("surface-missing");
if (!markup.includes('data-action="open-project-chooser"')) throw new Error("back-missing");
if (!markup.includes('value="Август"')) throw new Error("draft-missing");
if (markup.includes("home-project-grid")) throw new Error("catalog-leaked-into-create");
if (formCount !== 1) throw new Error(`forms:${{formCount}}`);
if (primaryCount !== 1) throw new Error(`primaries:${{primaryCount}}`);
process.stdout.write("ok");
"""
    _run_node(script)


def test_selected_home_exposes_secondary_project_switch_without_competing_primary() -> None:
    home = _function(APP, "function renderHomeSection(")
    selected = home[home.index("const action = serverProjectNextAction") :]
    chooser_control = home[
        home.index("const projectChooserControl") : home.index("const routeProjectId")
    ]

    assert 'data-action="open-project-chooser"' in home
    assert "Сменить или создать проект" in home
    assert 'class="btn btn-secondary home-project-switch-control"' in home
    assert 'data-primary-action="true"' not in chooser_control
    assert "home-single-action__project-nav" in selected


def test_successful_project_creation_never_waits_for_unscoped_finder() -> None:
    submit = _function(APP, "async function submitHomeProjectCreate(")

    assert "refreshWorkspaceBoardAfterMutation" not in submit
    assert "activateWorkspaceProject(projectId, name)" in submit
    assert "exactProjectNextActionRoute(createdFlow, projectId)" in submit
    assert "await flowHandoff(" in submit
    assert "Открываем первый шаг проекта" in submit
    assert 'navigate("/workspace/home", false, { scopeProject: false })' in submit
