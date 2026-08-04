"""Regression contracts for the project chooser's recoverable states.

The project catalog and project creation use different RPCs.  A catalog
failure must therefore not remove the creation action, and retrying the
catalog must remain possible after any number of transient failures.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    """Extract one JavaScript function without pinning its next neighbour."""

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
    assert node is not None, "Node.js is required for chooser runtime contracts"
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


def test_chooser_matrix_keeps_project_creation_independent_from_catalog_rpc() -> None:
    switcher = _function(APP, "function homeProjectSwitcherMarkup(")
    script = f"""
const projectId = "11111111-1111-4111-8111-111111111111";
const state = {{
  sections: {{ board: {{ data: {{ capabilities: {{ manageFolders: false }} }} }} }},
  bootstrap: {{ membership: {{ role: "owner" }} }},
  projectFlow: {{ status: "idle", data: null }},
  workspaceBoard: {{ busy: false, error: "", notice: "", projectCreateError: "" }},
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
let storedProject = null;
const storedWorkspaceProject = () => storedProject;
const escapeHtml = (value) => String(value ?? "");
const formatDate = () => "сейчас";
const readableHomeActionTitle = (action) => action.title || "Выберите проект";
{switcher}

const action = {{
  step: "Один проект — одна цепочка",
  title: "Выберите проект",
  description: "Выберите или создайте проект.",
  href: "#/workspace/home",
  cta: "Выбрать проект",
}};
const render = (status, data) => {{
  state.projectFlow.status = status;
  state.projectFlow.data = data;
  return homeProjectSwitcherMarkup(action);
}};
const must = (condition, message) => {{ if (!condition) throw new Error(message); }};
const count = (text, token) => text.split(token).length - 1;

const loading = render("loading", null);
must(count(loading, "home-project-card--loading") === 3, "loading-skeletons");
must(loading.includes('id="home-project-create-form"'), "loading-create-missing");
must(!loading.includes('data-action="retry-project-flow"'), "loading-has-retry");

const empty = render("ready", {{ projects: [] }});
must(!empty.includes("home-project-card--loading"), "empty-has-skeleton");
must(empty.includes('id="home-project-create-form"'), "empty-create-missing");
must(/class="home-project-create"[^>]*\\sopen(?:\\s|>)/u.test(empty), "empty-create-closed");
must(!empty.includes('data-action="retry-project-flow"'), "empty-has-retry");

const projects = render("ready", {{
  projects: [{{
    id: projectId,
    name: "Проект 1",
    current_stage: "files",
    next_action: {{ label: "Открыть проект" }},
    counts: {{ files: 0 }},
  }}],
}});
must(projects.includes('data-ce-v4-project-id="' + projectId + '"'), "projects-card-missing");
must(projects.includes('id="home-project-create-form"'), "projects-create-missing");
must(!projects.includes('data-action="retry-project-flow"'), "projects-has-retry");

const failed = render("error", null);
must(failed.includes('id="home-project-create-form"'), "error-create-missing");
must(failed.includes('data-action="retry-project-flow"'), "error-retry-missing");
must(/class="btn[^\"]*btn-secondary[^\"]*home-project-board-retry"/u.test(failed), "error-retry-not-secondary");
must(count(failed, 'data-primary-action="true"') === 1, "error-primary-count");
must(!failed.includes('href="#/workspace/home">'), "error-dead-home-action");
must(!failed.includes('class="home-next-action-compact"'), "error-duplicate-action-panel");

storedProject = {{ id: projectId, name: "Последний проект" }};
const recovered = render("error", null);
must(recovered.includes('data-ce-v4-project-id="' + projectId + '"'), "recovery-card-missing");
must(recovered.includes("Сохранён в этом браузере"), "recovery-card-not-explained");
must(recovered.includes(`/workspace/home?project_id=${{projectId}}`), "recovery-route-missing");
storedProject = null;

const stale = render("error", {{
  projects: [{{
    id: projectId,
    name: "Кешированный проект",
    current_stage: "files",
    next_action: {{ label: "Открыть проект" }},
    counts: {{ files: 1 }},
  }}],
}});
must(stale.includes('data-ce-v4-project-id="' + projectId + '"'), "stale-card-missing");
must(stale.includes('id="home-project-create-form"'), "stale-create-missing");
must(stale.includes('data-action="retry-project-flow"'), "stale-retry-missing");
process.stdout.write("ok");
"""
    _run_node(script)


def test_catalog_retry_is_repeatable_and_recovers_without_a_stuck_button() -> None:
    loader = _function(APP, "async function loadProjectFlow(")
    click = _function(APP, "async function handleClick(")
    script = f"""
let callCount = 0;
const projectId = "22222222-2222-4222-8222-222222222222";
const state = {{
  mobileNavOpen: false,
  api: {{
    projectFlow: async () => {{
      callCount += 1;
      if (callCount < 3) throw new Error(`temporary-${{callCount}}`);
      return {{ project_id: "", projects: [{{ id: projectId, name: "Восстановлен" }}] }};
    }},
  }},
  dataEpoch: 4,
  user: {{ id: "user-1" }},
  route: {{ path: "/workspace/home", query: new URLSearchParams() }},
  projectFlow: {{ status: "error", projectId: "", requestId: 0, data: null, error: new Error("initial") }},
}};
const WORKSPACE_PROJECT_FLOW_TIMEOUT_MS = 10_000;
const projectFlowRequestProjectId = () => "";
const withUiTimeout = (promise) => promise;
const normalizeProjectFlow = (value) => ({{ project_id: null, projects: [], ...value }});
const render = () => undefined;
const persistWorkspaceProject = () => undefined;
const currentWorkspaceProjectName = () => "Проект";
const navigate = () => undefined;
const workspaceSectionRequiresProject = () => false;
const clearWorkspaceProjectSelection = () => true;
{loader}
{click}

const control = {{ dataset: {{ action: "retry-project-flow" }}, disabled: false, isConnected: true }};
const event = {{ target: {{ closest: (selector) => selector === "[data-action]" ? control : null }} }};
const retry = async (expectedStatus, expectedCalls) => {{
  await handleClick(event);
  if (callCount !== expectedCalls) throw new Error(`calls:${{callCount}}`);
  if (state.projectFlow.status !== expectedStatus) throw new Error(`status:${{state.projectFlow.status}}`);
  if (control.disabled) throw new Error("retry-stuck-disabled");
}};
await retry("error", 1);
await retry("error", 2);
await retry("ready", 3);
if (state.projectFlow.data?.projects?.[0]?.id !== projectId) throw new Error("catalog-not-restored");
if (state.projectFlow.error !== null) throw new Error("error-not-cleared");
process.stdout.write("ok");
"""
    _run_node(script)


def test_create_project_submission_can_succeed_while_catalog_is_in_error() -> None:
    submit = _function(APP, "async function submitHomeProjectCreate(")
    script = f"""
const projectId = "33333333-3333-4333-8333-333333333333";
let createCalls = 0;
const navigations = [];
const state = {{
  api: {{
    createProject: async (payload) => {{
      createCalls += 1;
      if (payload.name !== "Новый проект") throw new Error("wrong-name");
      return {{ project_id: projectId, project: {{ id: projectId, name: payload.name }} }};
    }},
  }},
  route: {{ path: "/workspace/home" }},
  projectFlow: {{ status: "error", projectId: "", data: null, error: new Error("catalog-down") }},
  workspaceBoard: {{ busy: false, error: "", notice: "", projectCreateError: "", selectedFolderId: "all" }},
}};
globalThis.FormData = class {{
  get(name) {{ return name === "folder_name" ? "Новый проект" : ""; }}
}};
const renderWorkspace = () => undefined;
const normalizeProjectFlow = (value) => ({{ project_id: value.project_id, projects: [], ...value }});
const isWorkspaceProjectId = (value) => /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu.test(String(value));
const persistWorkspaceProject = () => true;
const refreshWorkspaceBoardAfterMutation = async () => undefined;
const navigate = (route) => navigations.push(route);
const actionErrorMessage = (error) => error.message;
{submit}

await submitHomeProjectCreate({{}});
if (createCalls !== 1) throw new Error(`create-calls:${{createCalls}}`);
if (state.workspaceBoard.busy) throw new Error("create-stuck-busy");
if (state.projectFlow.status !== "ready") throw new Error(`status:${{state.projectFlow.status}}`);
if (state.projectFlow.projectId !== projectId) throw new Error(`project:${{state.projectFlow.projectId}}`);
if (state.projectFlow.error !== null) throw new Error("catalog-error-not-cleared");
if (navigations[0] !== `/workspace/board?project_id=${{projectId}}`) throw new Error(`navigation:${{navigations[0]}}`);
process.stdout.write("ok");
"""
    _run_node(script)


def test_failed_create_keeps_the_draft_and_explains_the_error_inline() -> None:
    submit = _function(APP, "async function submitHomeProjectCreate(")
    switcher = _function(APP, "function homeProjectSwitcherMarkup(")
    script = f"""
const state = {{
  api: {{ createProject: async () => {{ throw new Error("create-offline"); }} }},
  bootstrap: {{ membership: {{ role: "owner" }} }},
  route: {{ path: "/workspace/home" }},
  sections: {{ board: {{ data: {{ capabilities: {{ manageFolders: false }} }} }} }},
  projectFlow: {{ status: "error", projectId: "", data: null, error: new Error("catalog-down") }},
  workspaceBoard: {{
    busy: false,
    error: "",
    notice: "",
    projectDraftName: "",
    projectCreateError: "",
    selectedFolderId: "all",
  }},
}};
globalThis.FormData = class {{
  get(name) {{ return name === "folder_name" ? "Черновик проекта" : ""; }}
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
const renderWorkspace = () => undefined;
const isWorkspaceProjectId = () => false;
const persistWorkspaceProject = () => true;
const refreshWorkspaceBoardAfterMutation = async () => undefined;
const navigate = () => {{ throw new Error("unexpected-navigation"); }};
const actionErrorMessage = (error) => error.message;
const exactProjectNextActionRoute = () => "";
const escapeHtml = (value) => String(value ?? "");
const formatDate = () => "сейчас";
const readableHomeActionTitle = (action) => action.title || "Выберите проект";
const storedWorkspaceProject = () => null;
{submit}
{switcher}

await submitHomeProjectCreate({{}});
if (state.workspaceBoard.busy) throw new Error("create-stuck-busy");
if (state.workspaceBoard.projectDraftName !== "Черновик проекта") throw new Error("draft-lost");
if (state.workspaceBoard.projectCreateError !== "create-offline") throw new Error(`error:${{state.workspaceBoard.projectCreateError}}`);
if (state.projectFlow.status !== "error") throw new Error("catalog-state-overwritten");

const markup = homeProjectSwitcherMarkup({{
  step: "Один проект — одна цепочка",
  title: "Выберите проект",
  description: "Выберите или создайте проект.",
  href: "#/workspace/home",
  cta: "Выбрать проект",
}});
if (!markup.includes('value="Черновик проекта"')) throw new Error("draft-not-rendered");
if (!markup.includes('class="home-project-create__error" role="alert"')) throw new Error("inline-error-missing");
if (!markup.includes("create-offline")) throw new Error("inline-error-text-missing");
process.stdout.write("ok");
"""
    _run_node(script)
