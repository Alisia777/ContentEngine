"""Regression contracts for project state isolation across authenticated contexts."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


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
    assert node is not None, "Node.js is required for project isolation runtime tests"
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        cwd=ROOT,
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == "ok"


def test_logout_and_account_switch_destroy_the_previous_project_cache() -> None:
    clear = _function(APP, "function clearAuthenticatedState(")
    auth = _function(APP, "async function handleAuthStateChange(")

    for statement in (
        "state.projectFlow.requestId += 1;",
        'state.projectFlow.status = "idle";',
        "state.projectFlow.data = null;",
        "state.projectFlow.error = null;",
        'state.projectFlow.projectId = "";',
        'state.projectFlow.contextKey = "";',
        "window.sessionStorage.removeItem(WORKSPACE_PROJECT_STORAGE_KEY);",
        'state.workspaceBoard.projectDraftName = "";',
        'state.workspaceBoard.projectCreateError = "";',
    ):
        assert statement in clear
    assert clear.index("state.projectFlow.requestId += 1;") < clear.index("state.user = null;")
    assert clear.index("window.sessionStorage.removeItem(WORKSPACE_PROJECT_STORAGE_KEY);") < clear.index(
        "state.user = null;"
    )

    identity_switch = auth[
        auth.index("if (previousUserId && previousUserId !== nextUserId)") :
        auth.index("state.session = session;", auth.index("if (previousUserId && previousUserId !== nextUserId)"))
    ]
    assert "clearAuthenticatedState();" in identity_switch
    assert auth.index('if (event === "SIGNED_OUT")') < auth.index("clearAuthenticatedState();")


def test_bootstrap_profile_organization_or_role_change_invalidates_project_state() -> None:
    context = _function(APP, "function workspaceProjectContextKey(")
    bootstrap = _function(APP, "async function loadBootstrap(")
    clear_selection = _function(APP, "function clearWorkspaceProjectSelection(")

    for boundary in (
        "user?.id",
        "bootstrap?.profile?.id",
        "bootstrap?.organization?.id",
        "bootstrap?.membership?.role",
    ):
        assert boundary in context
    assert 'if (!userId || !profileId || !organizationId || !role) return "";' in context
    assert "const previousProjectContextKey" in bootstrap
    assert "workspaceProjectContextKey()" in bootstrap
    assert "const nextProjectContextKey" in bootstrap
    assert "workspaceProjectContextKey(bootstrap)" in bootstrap
    assert "previousProjectContextKey !== nextProjectContextKey" in bootstrap
    assert "clearWorkspaceProjectSelection();" in bootstrap
    assert bootstrap.index("clearWorkspaceProjectSelection();") < bootstrap.index("state.bootstrap = bootstrap;")
    assert "state.projectFlow.contextKey = nextProjectContextKey;" in bootstrap

    assert "state.home.requestId += 1;" in clear_selection
    assert "state.home.data = null;" in clear_selection
    assert "state.home.unavailable = [];" in clear_selection
    assert 'state.workspaceBoard.projectDraftName = "";' in clear_selection
    assert 'state.workspaceBoard.projectCreateError = "";' in clear_selection


def test_runtime_account_organization_and_role_switches_cannot_reuse_ready_catalog() -> None:
    context = _function(APP, "function workspaceProjectContextKey(")
    loader = _function(APP, "async function loadProjectFlow(")
    script = r"""
const oldProject = "11111111-1111-4111-8111-111111111111";
const calls = [];
let clears = 0;
const storage = new Map([["contentengine.desktop-v4.project", oldProject]]);
const state = {
  dataEpoch: 9,
  user: { id: "user-a" },
  bootstrap: {
    profile: { id: "profile-a" },
    organization: { id: "org-a" },
    membership: { role: "operator" },
  },
  route: { path: "/workspace/home", query: new URLSearchParams() },
  projectFlow: {
    status: "ready",
    projectId: "",
    requestId: 4,
    data: { project_id: null, projects: [{ id: oldProject, name: "Чужой кеш" }] },
    error: null,
    contextKey: "",
  },
  api: {
    projectFlow: async () => {
      calls.push(workspaceProjectContextKey());
      return {
        project_id: null,
        projects: [{ id: `22222222-2222-4222-8222-${String(calls.length).padStart(12, "2")}`, name: `Каталог ${calls.length}` }],
      };
    },
  },
};
__CONTEXT__
state.projectFlow.contextKey = workspaceProjectContextKey();
const WORKSPACE_PROJECT_FLOW_TIMEOUT_MS = 10_000;
const projectFlowRequestProjectId = () => "";
const withUiTimeout = (promise) => promise;
const normalizeProjectFlow = (value) => ({ project_id: null, projects: [], ...value });
const render = () => undefined;
const persistWorkspaceProject = () => undefined;
const currentWorkspaceProjectName = () => "Проект";
const navigate = () => undefined;
const workspaceSectionRequiresProject = () => false;
function clearWorkspaceProjectSelection() {
  clears += 1;
  storage.delete("contentengine.desktop-v4.project");
  state.projectFlow.requestId += 1;
  state.projectFlow.status = "idle";
  state.projectFlow.data = null;
  state.projectFlow.error = null;
  state.projectFlow.projectId = "";
  state.projectFlow.contextKey = "";
  return true;
}
__LOADER__

state.user = { id: "user-b" };
state.bootstrap = {
  profile: { id: "profile-b" },
  organization: { id: "org-b" },
  membership: { role: "operator" },
};
await loadProjectFlow({ silent: true });
if (calls.length !== 1 || clears !== 1) throw new Error(`account:${calls.length}:${clears}`);
if (storage.has("contentengine.desktop-v4.project")) throw new Error("stored-project-leaked");

state.bootstrap = {
  ...state.bootstrap,
  organization: { id: "org-c" },
};
await loadProjectFlow({ silent: true });
if (calls.length !== 2 || clears !== 2) throw new Error(`organization:${calls.length}:${clears}`);

state.bootstrap = {
  ...state.bootstrap,
  membership: { role: "reviewer" },
};
await loadProjectFlow({ silent: true });
if (calls.length !== 3 || clears !== 3) throw new Error(`role:${calls.length}:${clears}`);
if (state.projectFlow.data?.projects?.[0]?.name !== "Каталог 3") throw new Error("stale-catalog-returned");
if (state.projectFlow.contextKey !== workspaceProjectContextKey()) throw new Error("context-not-bound");
process.stdout.write("ok");
""".replace("__CONTEXT__", context).replace("__LOADER__", loader)
    _run_node(script)


def test_access_required_runtime_clears_selection_and_returns_to_chooser() -> None:
    context = _function(APP, "function workspaceProjectContextKey(")
    loader = _function(APP, "async function loadProjectFlow(")
    script = r"""
const projectId = "33333333-3333-4333-8333-333333333333";
const navigations = [];
const cleared = [];
const state = {
  dataEpoch: 2,
  user: { id: "user-b" },
  bootstrap: {
    profile: { id: "profile-b" },
    organization: { id: "org-b" },
    membership: { role: "operator" },
  },
  route: {
    path: "/workspace/generation",
    query: new URLSearchParams(`project_id=${projectId}`),
  },
  projectFlow: {
    status: "idle",
    projectId,
    requestId: 0,
    data: null,
    error: null,
    contextKey: "",
  },
  api: {
    projectFlow: async () => {
      const failure = new Error("access revoked");
      failure.serverCode = "workspace_project_access_required";
      throw failure;
    },
  },
};
__CONTEXT__
state.projectFlow.contextKey = workspaceProjectContextKey();
const WORKSPACE_PROJECT_FLOW_TIMEOUT_MS = 10_000;
const projectFlowRequestProjectId = () => projectId;
const withUiTimeout = (promise) => promise;
const normalizeProjectFlow = (value) => value;
const render = () => undefined;
const persistWorkspaceProject = () => undefined;
const currentWorkspaceProjectName = () => "Проект";
const workspaceSectionRequiresProject = () => true;
const clearWorkspaceProjectSelection = (id) => {
  cleared.push(id);
  state.projectFlow.requestId += 1;
  state.projectFlow.status = "idle";
  state.projectFlow.data = null;
  state.projectFlow.error = null;
  state.projectFlow.projectId = "";
  state.projectFlow.contextKey = "";
  return true;
};
const navigate = (...args) => navigations.push(args);
__LOADER__

await loadProjectFlow({ silent: true });
if (JSON.stringify(cleared) !== JSON.stringify([projectId])) throw new Error(`clear:${JSON.stringify(cleared)}`);
if (navigations.length !== 1 || navigations[0][0] !== "/workspace/home") {
  throw new Error(`navigate:${JSON.stringify(navigations)}`);
}
if (navigations[0][1] !== true || navigations[0][2]?.scopeProject !== false) {
  throw new Error(`navigation-options:${JSON.stringify(navigations[0])}`);
}
if (state.projectFlow.data !== null || state.projectFlow.projectId !== "") throw new Error("selection-survived");
process.stdout.write("ok");
""".replace("__CONTEXT__", context).replace("__LOADER__", loader)
    _run_node(script)


def test_manual_home_refresh_forces_project_flow_and_empty_copy_describes_access() -> None:
    click = _function(APP, "async function handleClick(")
    refresh = click[
        click.index('if (action === "refresh-home")') :
        click.index('if (action === "repeat-real-generation")')
    ]
    assert "await loadProjectFlow({ silent: true, force: true });" in refresh
    assert 'if (state.route.path === "/workspace/home") render();' in refresh
    assert (
        "Доступных вам проектов пока нет. Попросите руководителя выдать доступ к нужному проекту."
        in APP
    )


def test_first_project_open_ignores_responses_after_logout_at_either_await() -> None:
    context = _function(APP, "function workspaceProjectContextKey(")
    opener = _function(APP, "async function openFirstAvailableWorkspaceProject(")
    script = r"""
const projectId = "44444444-4444-4444-8444-444444444444";
let calls = 0;
let activations = 0;
let firstResolve;
let secondResolve;
const navigations = [];
const storage = new Map();
const state = {
  dataEpoch: 1,
  user: { id: "user-a" },
  bootstrap: {
    profile: { id: "profile-a" },
    organization: { id: "org-a" },
    membership: { role: "operator" },
  },
  projectFlow: { status: "idle", data: null, error: null, projectId: "", contextKey: "" },
  api: { projectFlow: null },
};
__CONTEXT__
state.projectFlow.contextKey = workspaceProjectContextKey();
const WORKSPACE_PROJECT_FLOW_TIMEOUT_MS = 10_000;
const hasWorkspaceAccess = () => true;
const withUiTimeout = (promise) => promise;
const normalizeProjectFlow = (value) => ({ project_id: null, projects: [], ...value });
const storedWorkspaceProject = () => null;
const isWorkspaceProjectId = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(String(value));
const activateWorkspaceProject = (id, name) => {
  activations += 1;
  storage.set("project", { id, name });
  return true;
};
const navigate = (...args) => navigations.push(args);
const exactProjectNextActionRoute = () => "";
__OPENER__

state.api.projectFlow = () => {
  calls += 1;
  return new Promise((resolve) => { firstResolve = resolve; });
};
const staleCatalog = openFirstAvailableWorkspaceProject();
state.dataEpoch += 1;
state.user = null;
state.projectFlow.contextKey = "";
storage.clear();
firstResolve({ projects: [{ id: projectId, name: "Старый проект" }] });
if (await staleCatalog !== false) throw new Error("stale-catalog-returned-true");
if (calls !== 1 || activations !== 0 || storage.size || navigations.length) {
  throw new Error(`catalog-leak:${calls}:${activations}:${storage.size}:${navigations.length}`);
}

calls = 0;
state.dataEpoch = 10;
state.user = { id: "user-a" };
state.bootstrap = {
  profile: { id: "profile-a" },
  organization: { id: "org-a" },
  membership: { role: "operator" },
};
state.projectFlow = { status: "idle", data: null, error: null, projectId: "", contextKey: workspaceProjectContextKey() };
state.api.projectFlow = () => {
  calls += 1;
  if (calls === 1) return Promise.resolve({ projects: [{ id: projectId, name: "Старый проект" }] });
  return new Promise((resolve) => { secondResolve = resolve; });
};
const staleSelected = openFirstAvailableWorkspaceProject();
while (calls < 2) await Promise.resolve();
state.dataEpoch += 1;
state.user = { id: "user-b" };
state.bootstrap = {
  profile: { id: "profile-b" },
  organization: { id: "org-b" },
  membership: { role: "operator" },
};
state.projectFlow = { status: "idle", data: null, error: null, projectId: "", contextKey: "" };
storage.clear();
secondResolve({ project_id: projectId, project: { id: projectId }, projects: [] });
if (await staleSelected !== false) throw new Error("stale-selected-returned-true");
if (activations !== 0 || storage.size || state.projectFlow.data !== null || navigations.length) {
  throw new Error(`selected-leak:${activations}:${storage.size}:${navigations.length}`);
}
process.stdout.write("ok");
""".replace("__CONTEXT__", context).replace("__OPENER__", opener)
    _run_node(script)


def test_project_create_response_cannot_repopulate_state_after_context_switch() -> None:
    context = _function(APP, "function workspaceProjectContextKey(")
    submit = _function(APP, "async function submitHomeProjectCreate(")
    script = r"""
const projectId = "55555555-5555-4555-8555-555555555555";
let resolveCreate;
let activations = 0;
let handoffs = 0;
const navigations = [];
const state = {
  dataEpoch: 3,
  user: { id: "user-a" },
  bootstrap: {
    profile: { id: "profile-a" },
    organization: { id: "org-a" },
    membership: { role: "owner" },
  },
  route: { path: "/workspace/home" },
  projectFlow: {
    status: "ready",
    data: { projects: [{ id: "66666666-6666-4666-8666-666666666666", name: "Старый" }] },
    error: null,
    projectId: "",
    contextKey: "",
  },
  workspaceBoard: {
    busy: false,
    projectDraftName: "",
    projectCreateError: "",
    notice: "",
    error: "",
    selectedFolderId: "all",
  },
  api: {
    createProject: () => new Promise((resolve) => { resolveCreate = resolve; }),
  },
};
__CONTEXT__
state.projectFlow.contextKey = workspaceProjectContextKey();
globalThis.FormData = class { get(name) { return name === "folder_name" ? "Новый старый проект" : ""; } };
const normalizeProjectFlow = (value) => ({ projects: [], ...value });
const renderWorkspace = () => undefined;
const actionErrorMessage = (error) => String(error?.message || error);
const isWorkspaceProjectId = (value) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(String(value));
const activateWorkspaceProject = () => { activations += 1; return true; };
const toast = () => undefined;
const navigate = (...args) => navigations.push(args);
const exactProjectNextActionRoute = () => "";
const flowHandoff = async () => { handoffs += 1; };
__SUBMIT__

const pending = submitHomeProjectCreate({});
if (!state.workspaceBoard.busy) throw new Error("create-never-entered-busy-state");
state.bootstrap = {
  ...state.bootstrap,
  organization: { id: "org-b" },
};
state.projectFlow = { status: "idle", data: null, error: null, projectId: "", contextKey: "" };
state.workspaceBoard.busy = false;
state.workspaceBoard.projectDraftName = "";
state.workspaceBoard.projectCreateError = "";
resolveCreate({
  project_id: projectId,
  project: { id: projectId, name: "Новый старый проект" },
  projects: [],
});
await pending;
if (activations || handoffs || navigations.length) {
  throw new Error(`stale-side-effect:${activations}:${handoffs}:${navigations.length}`);
}
if (state.projectFlow.data !== null || state.projectFlow.projectId !== "") throw new Error("stale-flow-restored");
if (state.workspaceBoard.busy || state.workspaceBoard.projectDraftName) throw new Error("new-context-stuck");
process.stdout.write("ok");
""".replace("__CONTEXT__", context).replace("__SUBMIT__", submit)
    _run_node(script)


def test_password_recovery_for_another_user_clears_old_project_state_once() -> None:
    handler = _function(APP, "async function handleAuthStateChange(")
    script = r"""
const projectId = "77777777-7777-4777-8777-777777777777";
let clears = 0;
const storage = new Map([["project", projectId]]);
const navigations = [];
const state = {
  session: { user: { id: "user-a" } },
  user: { id: "user-a" },
  projectFlow: { status: "ready", data: { project_id: projectId }, projectId },
  authPurpose: null,
  forcePassword: false,
};
function clearAuthenticatedState() {
  clears += 1;
  storage.clear();
  state.session = null;
  state.user = null;
  state.projectFlow = { status: "idle", data: null, error: null, projectId: "" };
}
const navigate = (...args) => navigations.push(args);
const requiresPasswordChange = () => false;
const loadBootstrap = async () => undefined;
const authenticatedStartPath = () => "/workspace/home";
const refreshBootstrapAccessState = () => undefined;
__HANDLER__

const recoverySession = { user: { id: "user-b" } };
await handleAuthStateChange("PASSWORD_RECOVERY", recoverySession);
if (clears !== 1 || storage.size) throw new Error(`cross-user-clear:${clears}:${storage.size}`);
if (state.user?.id !== "user-b" || state.session !== recoverySession) throw new Error("recovery-user-not-committed");
if (state.projectFlow.data !== null || state.projectFlow.projectId !== "") throw new Error("old-project-survived");
if (state.authPurpose !== "recovery" || state.forcePassword !== true) throw new Error("recovery-state-missing");
if (navigations.length !== 1 || navigations[0][0] !== "/set-password" || navigations[0][1] !== true) {
  throw new Error(`recovery-navigation:${JSON.stringify(navigations)}`);
}

storage.set("project", "same-user-project");
state.user = { id: "user-b" };
state.session = recoverySession;
await handleAuthStateChange("PASSWORD_RECOVERY", recoverySession);
if (clears !== 1 || storage.get("project") !== "same-user-project") {
  throw new Error(`same-user-cleared:${clears}:${storage.size}`);
}
process.stdout.write("ok");
""".replace("__HANDLER__", handler)
    _run_node(script)
