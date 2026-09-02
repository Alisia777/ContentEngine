"""Executable product contracts for the project-scoped Desktop v4.7 flow.

The assertions stay at semantic boundaries instead of pinning build hashes,
line numbers, or exact visual copy.  They describe what the browser and the
server must agree on: one selected project, one server-owned next action, one
scroll owner, and reversible Finder operations.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


APP = _read("web/app/app.js")
API = _read("web/app/supabase-api.js")
CONTENT_REVIEW_VIEW = _read("web/app/content-review-view.js")
CORE = _read("web/app/workspace-os-v4.js")
LOADER = _read("web/app/workspace-os-v4-loader.js")
FINDER = _read("web/app/workspace-os-v4-finder.js")
BOARD = _read("web/app/workspace-board-view.js")
CONTEXT_TRASH = _read("web/app/workspace-os-v4-context-trash.js")
CONTEXT_TRASH_CSS = _read("web/app/workspace-os-v4-context-trash.css")
TRAINING = _read("web/app/training-journey.js")
INDEX = _read("web/app/index.html")
CORE_CSS = _read("web/app/workspace-os-v4.css")
FINDER_CSS = _read("web/app/workspace-os-v4-finder.css")
FLOW_CSS = _read("web/app/workspace-os-v4-flow.css")
GENERATION_CSS = _read("web/app/workspace-os-v4-generation-guided.css")
REVIEW_CSS = _read("web/app/workspace-os-v4-review-guided.css")
TRAINING_CSS = _read("web/app/training-journey.css")
ALL_CSS = "\n".join(
    (CORE_CSS, FINDER_CSS, FLOW_CSS, GENERATION_CSS, REVIEW_CSS, TRAINING_CSS)
)
V4_CSS = {
    path.name: path.read_text(encoding="utf-8")
    for path in sorted(APP_DIR.glob("workspace-os-v4*.css"))
}
MIGRATIONS = "\n".join(
    path.read_text(encoding="utf-8")
    for path in sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
)
PROJECT_CATALOG_HOTFIX = _read(
    "supabase/migrations/202608040007_project_flow_catalog_hotfix.sql"
)


def test_review_decision_actions_do_not_share_the_sticky_preview_grid_area() -> None:
    preview_rule = re.search(
        r'\.content-review-decision-form > \.content-review-decision-preview\s*\{([^}]*)\}',
        REVIEW_CSS,
        re.S,
    )
    actions_rule = re.search(
        r'\.content-review-decision-form > \.content-review-decision-actions\s*\{([^}]*)\}',
        REVIEW_CSS,
        re.S,
    )
    assert preview_rule and actions_rule
    assert "grid-column: 1" in preview_rule.group(1)
    assert "overflow: hidden" in preview_rule.group(1)
    assert "grid-column: 2" in actions_rule.group(1)
    assert "grid-row: auto" in actions_rule.group(1)
    assert "z-index: 2" in actions_rule.group(1)
    assert "pointer-events" not in actions_rule.group(1)


def _function(source: str, declaration: str) -> str:
    """Extract a JavaScript function without depending on its next neighbour."""

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
    raise AssertionError(f"Unbalanced JavaScript function: {declaration}")


def _css_rules(source: str, selector_fragment: str) -> list[str]:
    return [
        match.group("body")
        for match in re.finditer(
            r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}",
            source,
            flags=re.DOTALL,
        )
        if selector_fragment in match.group("selector")
    ]


def _action_region(action: str, limit: int = 1_800) -> str:
    marker = f'action === "{action}"'
    start = APP.index(marker)
    return APP[start : start + limit]


def test_project_id_is_the_canonical_url_and_api_scope() -> None:
    browser_sources = "\n".join((APP, CORE, FINDER, BOARD))
    assert re.search(r"[\"']project_id[\"']", browser_sources)
    assert re.search(r"\.get\(\s*[\"']project_id[\"']", browser_sources)
    assert re.search(r"\.set\(\s*[\"']project_id[\"']", browser_sources)

    # Project scope must cross the network boundary; sessionStorage alone is
    # not sufficient because it can label a global queue as a project queue.
    assert re.search(r"\bproject_id\b", API)
    assert re.search(
        r"(?:workspace|project).{0,120}(?:progress|flow|board|next_action).{0,240}project_id"
        r"|project_id.{0,240}(?:progress|flow|board|next_action)",
        API,
        flags=re.IGNORECASE | re.DOTALL,
    )


def test_every_primary_transition_preserves_project_id() -> None:
    dock = _function(CORE, "function ensureDock(")
    core_navigate = _function(CORE, "function navigate(")
    assert re.search(r"project|scoped|context", dock, re.IGNORECASE)
    assert re.search(r"project|scoped|context", core_navigate, re.IGNORECASE)

    for action, route in (
        ("create-from-workspace-media", "/workspace/generation?view=create"),
        ("open-generated-content-review", "/workspace/review"),
    ):
        region = _action_region(action)
        assert route in region
        assert "project" in region.casefold(), f"{action} drops the selected project"

    decision = _function(APP, "async function submitContentReviewDecision(")
    assert 'resolvedDecision === "needs_changes"' in decision
    assert "/workspace/generation" in decision
    assert 'resolvedDecision === "approved"' in decision
    assert "/workspace/placement?view=next" in decision
    assert "project" in decision.casefold()
    assert 'navigate("/workspace/generation")' not in decision
    assert 'navigate("/workspace/placement?view=next")' not in decision


def test_server_owns_project_progress_and_next_action() -> None:
    function_match = re.search(
        r"create\s+or\s+replace\s+function\s+(?:public\.)?"
        r"creator_(?:workspace_)?project_(?:flow|progress|dashboard)",
        MIGRATIONS,
        flags=re.IGNORECASE,
    )
    assert function_match, "A project progress RPC must be the shared source of truth"

    contract_window = MIGRATIONS[function_match.start() : function_match.start() + 24_000]
    for field in ("project_id", "next_action", "stages"):
        assert field in contract_window.casefold()
    assert re.search(r"\b(?:current|complete|completed|blocked)\b", contract_window, re.IGNORECASE)
    assert re.search(r"project_(?:flow|progress|dashboard)", API, re.IGNORECASE)

    progress = _function(CORE, "function syncProjectProgress(")
    assert "next" in progress.casefold() or "progress" in progress.casefold()
    assert "index < activeIndex" not in progress, (
        "The client must not mark stages complete merely because their route is left of the current route"
    )


def test_exact_next_action_is_validated_and_drives_the_canonical_dock_destination() -> None:
    normalize = _function(CORE, "function normalizeProjectNextAction(")
    snapshot = _function(CORE, "function projectFlowSnapshot(")
    stage_for_route = _function(CORE, "function stageForRoute(")
    active_index = _function(CORE, "function activeProjectFlowIndex(")
    dock_destination = _function(CORE, "function dockDestination(")
    update_dock = _function(CORE, "function updateDock(")

    for guard in (
        "PROJECT_ID_PATTERN.test(normalizedProjectId)",
        "PROJECT_FLOW.some((item) => item.code === stage)",
        "NEXT_ACTION_PATHS.has(path)",
        "payloadProjectId && payloadProjectId !== normalizedProjectId",
        "routeProjectId && routeProjectId !== normalizedProjectId",
        "entityId && !PROJECT_ID_PATTERN.test(entityId)",
    ):
        assert guard in normalize
    assert "routeWithProject(route, normalizedProjectId)" in normalize
    assert "canonicalRoute: routeWithProject(item.route, id)" in snapshot
    assert "destination: routeWithProject(" in snapshot
    assert "nextAction?.stage === item.code && nextAction?.route" in snapshot
    assert "routeParts(stage.canonicalRoute).path" in stage_for_route
    assert "workspaceActionKey() === workspaceActionKey(snapshot.nextAction.route)" in active_index
    assert "stage?.destination || projectRoute(record.route, context)" in dock_destination
    assert "dockDestination(record, snapshot)" in update_dock
    assert 'item.href = `#${destination}`' in update_dock


def test_future_stage_click_opens_the_required_action_instead_of_dead_end_toasts() -> None:
    locked = _function(CORE, "function openRequiredStage(")
    dock = _function(CORE, "function ensureDock(")
    activate = _function(CORE, "function activateDockKey(")
    progress = _function(CORE, "function syncProjectProgress(")

    assert 'snapshot.nextAction?.route || required?.destination' in locked
    assert 'item.state === "current"' in locked
    assert 'item.state === "blocked"' in locked
    assert "navigatePrimaryRoute(destination)" in locked
    assert "activateDockKey(item.dataset.ceV4DockKey, event)" in dock
    assert "openRequiredStage(stage, snapshot)" in activate
    assert "openRequiredStage(stage, currentSnapshot)" in progress
    assert "Проверку выполняете вы" in CORE


def test_exact_task_handoff_uses_fresh_server_flow_and_keeps_origin_stage() -> None:
    exact = _function(APP, "function exactProjectNextActionRoute(")
    click = _function(APP, "async function handleClick(")
    transition_start = click.index('if (action === "transition-task")')
    transition_end = click.index('if (action === "decide-payout")', transition_start)
    transition = click[transition_start:transition_end]

    assert "flow.project_id !== projectId" in exact
    assert "actionProjectId !== projectId" in exact
    assert "routeProjectIds.length !== 1" in exact
    assert "routeProjectIds[0]" in exact
    assert "entityId && !isWorkspaceProjectId(entityId)" in exact
    assert "await state.api.transitionTask" in transition
    assert "projectId: currentWorkspaceProjectId()" in transition
    assert "await loadProjectFlow({ silent: true, force: true })" in transition
    assert "exactProjectNextActionRoute(freshFlow, projectId)" in transition
    assert "await flowHandoff(" in transition
    assert 'navigate("/workspace/tasks")' not in transition

    active_index = _function(CORE, "function activeProjectFlowIndex(")
    active_dock = _function(CORE, "function activeDockKey(")
    dock_destination = _function(CORE, "function dockDestination(")
    assert 'routeQuery().get("stage") || routeQuery().get("origin_stage")' in active_index
    assert 'if (route !== "/workspace/tasks") return -1' in active_index
    assert 'if (requested >= 0) return requested' in active_index
    assert '["/workspace/tasks", "/workspace/work"].includes(path)' in active_dock
    assert 'return "processes"' in active_dock
    assert "stage?.destination || projectRoute(record.route, context)" in dock_destination


def test_review_repair_handoff_keeps_the_exact_review_in_the_url() -> None:
    click = _function(APP, "async function handleClick(")
    prepare_start = click.index('if (action === "prepare-generation-repair")')
    prepare_end = click.index('if (action === "open-generated-content-review")', prepare_start)
    prepare = click[prepare_start:prepare_end]
    decision = _function(APP, "async function submitContentReviewDecision(")

    assert "/workspace/generation?view=create&review=${encodeURIComponent(reviewId)}" in prepare
    assert "workspaceProjectHref(" in prepare
    assert "requireWorkspaceProjectId()" in prepare
    assert 'navigate("/workspace/generation")' not in prepare
    assert "await loadProjectFlow({ silent: true, force: true })" in decision
    assert "exactProjectNextActionRoute(freshFlow, projectId)" in decision
    assert "content_review_exact_repair_missing" in decision
    assert "await flowHandoff(\n        exactNext," in decision


def test_research_handoff_has_its_own_project_identity_and_no_free_review_variable() -> None:
    click = _function(APP, "async function handleClick(")
    research_start = click.index('if (action === "generate-research-scenario")')
    research_end = click.index('if (action === "dismiss-generation-handoff")', research_start)
    research = click[research_start:research_end]

    assert "const projectId = requireWorkspaceProjectId()" in research
    assert "{ projectId }" in research
    assert 'workspaceProjectHref("/workspace/generation?view=create", projectId)' in research
    assert "reviewId" not in research


def test_restore_placement_is_an_inline_exact_review_action() -> None:
    review = _function(APP, "function renderContentReviewSection(")
    decision = _function(CONTENT_REVIEW_VIEW, "function reviewDecisionMarkup(")

    assert 'state.route.query.get("action") === "restore-placement"' in review
    assert "restorePlacement && run.decision.decision === \"approved\"" in decision
    restore_start = decision.index(
        'restorePlacement && run.decision.decision === "approved"'
    )
    restore_end = decision.index("generationRepairNextActionMarkup", restore_start)
    restore = decision[restore_start:restore_end]
    assert 'data-action="restore-project-placement"' in restore
    assert 'data-review-id="${escapeHtml(run.id)}"' in restore
    assert "content-review-next-action" in restore
    assert 'role="dialog"' not in restore
    assert 'aria-modal="true"' not in restore


def test_restore_placement_handler_requires_exact_ids_and_handoffs_the_created_item() -> None:
    click = _function(APP, "async function handleClick(")
    restore_start = click.index('if (action === "restore-project-placement")')
    restore_end = click.index('if (action === "prepare-generation-repair")', restore_start)
    restore = click[restore_start:restore_end]

    assert "const projectId = requireWorkspaceProjectId()" in restore
    assert "control.dataset.reviewId" in restore
    assert "contentReviewUuid(reviewId)" in restore
    assert "state.api.restoreProjectPlacement(reviewId, { projectId })" in restore
    assert "result.placement_id || result.placement?.id" in restore
    assert "contentReviewUuid(placementId)" in restore
    assert 'new Error("project_placement_restore_invalid")' in restore
    assert "await loadProjectFlow({ silent: true, force: true })" in restore
    assert "exactProjectNextActionRoute(freshFlow, projectId)" in restore
    assert "/workspace/placement?view=next&placement=${encodeURIComponent(placementId)}" in restore
    assert "workspaceProjectHref(" in restore
    assert "await flowHandoff(" in restore
    assert "navigate(" not in restore


def test_exact_media_review_and_job_links_fail_closed_without_substitution() -> None:
    generation = _function(APP, "function renderGenerationSection(")
    review = _function(APP, "function renderContentReviewSection(")
    repair = _function(APP, "async function loadGenerationRepairForReview(")

    assert "routeMediaId && !routeSelectedMediaId" in generation
    assert 'generationView === "history" && routeJobId && routeFilteredBatches.length === 0' in generation
    assert "exactRouteUnavailable" in generation
    assert "routeMediaId\n      ? routeSelectedMediaId" in generation
    assert "routeMediaId\n      ? finderSelectedMediaId" not in generation

    assert "const exactReviewMissing" in review
    assert "const exactMediaMissing" in review
    assert "!catalog.media.some" in review
    assert "exactMediaMissing\n          ? emptyState(" in review
    assert "exactReviewMissing\n          ? emptyState(" in review

    assert "generationRepairPolicy(" in repair
    assert "projectId: requireWorkspaceProjectId()" in repair
    assert "repairPolicy.sourceReviewId" in repair
    assert "generation_repair_review_mismatch" in repair


def test_home_cards_and_focus_queue_use_server_next_actions() -> None:
    home = _function(APP, "function homeProjectSwitcherMarkup(")
    assert re.search(r"next[_-]?action", home, flags=re.IGNORECASE)
    assert re.search(r"focus[-_ ]?queue|фокус[- ]очеред", APP, flags=re.IGNORECASE)
    assert re.search(r"data-[^=\s]*(?:focus-queue|next-action)", APP, flags=re.IGNORECASE)

    # A project card must carry its own route/action; a single global action
    # below an unrelated collection of projects recreates the old ambiguity.
    project_loop = home[home.index("visibleProjects.map") :]
    assert re.search(r"project\.(?:nextAction|next_action|nextRoute|next_route)", project_loop)
    assert re.search(r"project[_-]?id", project_loop, flags=re.IGNORECASE)


def test_project_choice_never_leaves_permanent_skeletons_when_flow_fails() -> None:
    switcher = _function(APP, "function homeProjectSwitcherMarkup(")
    loader = _function(APP, "async function loadProjectFlow(")

    # An unrelated idle Finder section cannot keep the project chooser loading.
    assert "const loading = !projects.length && projectFlowLoading" in switcher
    assert "boardLoading" not in switcher
    assert 'state.projectFlow.status === "error"' in switcher
    assert 'data-action="retry-project-flow"' in switcher

    # A missing API adapter is a visible recoverable error, not an eternal
    # `idle` state that continuously renders loading cards.
    missing_api = loader[: loader.index("const projectId")]
    assert 'state.projectFlow.status = "error"' in missing_api
    assert 'state.projectFlow.error' in missing_api


def test_project_list_retry_is_one_bounded_precise_request() -> None:
    click = _function(APP, "async function handleClick(")
    retry_start = click.index('if (action === "retry-project-flow")')
    retry_end = click.index('if (action === "select-ai-learning-category")', retry_start)
    retry = click[retry_start:retry_end]

    assert "await loadProjectFlow({ silent: true, force: true })" in retry
    assert "state.sections.board.requestId" not in retry


def test_project_catalog_is_lightweight_until_one_project_is_selected() -> None:
    catalog = PROJECT_CATALOG_HOTFIX

    assert "create or replace function public.creator_project_flow" in catalog
    assert catalog.count("content_factory_private.project_flow_snapshot(") == 1
    assert "cross join lateral" not in catalog
    assert "from content_factory.workspace_folders project" in catalog
    assert "'catalog_state', 'summary'" in catalog
    assert "'/workspace/home?project_id=' || project.id::text" in catalog
    assert "grant execute on function public.creator_project_flow(jsonb)" in catalog


def test_unscoped_home_is_a_catalog_request_and_never_reuses_stale_project_state() -> None:
    route_id = _function(APP, "function routeWorkspaceProjectId(")
    chooser = _function(APP, "function workspaceProjectChooserMode(")
    current_id = _function(APP, "function currentWorkspaceProjectId(")
    request_id = _function(APP, "function projectFlowRequestProjectId(")
    workspace = _function(APP, "function renderWorkspace(")
    loader = _function(APP, "async function loadProjectFlow(")
    home = _function(APP, "function renderHomeSection(")
    v4_snapshot = _function(CORE, "function projectFlowSnapshot(")

    # Only one valid URL value can select a project. The bare home route is a
    # deliberate chooser, even if sessionStorage still remembers yesterday's
    # project.
    assert 'state.route.query.getAll("project_id")' in route_id
    assert 'state.route.path === "/workspace/home"' in chooser
    assert "!routeWorkspaceProjectId()" in chooser
    assert 'if (workspaceProjectChooserMode()) return ""' in current_id
    assert current_id.index("workspaceProjectChooserMode()") < current_id.index(
        "storedWorkspaceProject()"
    )

    # The request scope is computed once and passed through unchanged. In
    # chooser mode this value is the empty string, which invokes the lightweight
    # catalog branch instead of one expensive project snapshot.
    assert 'if (workspaceProjectChooserMode()) return ""' in request_id
    assert "const requestedProjectId = projectFlowRequestProjectId()" in workspace
    assert "requestedProjectId !== state.projectFlow.projectId" in workspace
    assert '["loading", "refreshing"].includes(state.projectFlow.status)' not in workspace[
        workspace.index("const requestedProjectId") : workspace.index("loadProjectFlow")
    ]
    assert "const projectId = projectFlowRequestProjectId()" in loader
    assert loader.count("projectId !== projectFlowRequestProjectId()") == 2
    assert "const unavailableProjectId = projectFlowRequestProjectId()" in loader
    assert "state.projectFlow.projectId = unavailableProjectId" in loader
    assert "state.api.projectFlow({ projectId, includeProjects: true })" in loader
    assert "currentWorkspaceProjectId()" not in loader[
        : loader.index("state.api.projectFlow({ projectId, includeProjects: true })")
    ]
    assert "workspaceProjectChooserMode()" in home

    # Desktop v4 independently derives its Dock snapshot. It must apply the
    # same chooser boundary and therefore cannot resurrect a stored project.
    assert "const chooserMode = projectChooserMode()" in v4_snapshot
    assert "const stored = chooserMode ? null : storedProjectContext()" in v4_snapshot
    assert 'const id = chooserMode ? "" :' in v4_snapshot
    assert 'const id = queryProjectId || rootProjectId || rawProjectId || stored?.id || ""' not in v4_snapshot


def test_catalog_request_supersedes_an_inflight_stale_project_snapshot() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the project-flow race contract"
    loader = _function(APP, "async function loadProjectFlow(")
    script = f"""
const projectA = "11111111-1111-4111-8111-111111111111";
let requestScope = projectA;
let resolveProjectA;
let resolveCatalog;
const calls = [];
const navigations = [];
const state = {{
  api: {{
    projectFlow: ({{ projectId }}) => {{
      calls.push(projectId);
      return new Promise((resolve) => {{
        if (projectId) resolveProjectA = resolve;
        else resolveCatalog = resolve;
      }});
    }},
  }},
  dataEpoch: 7,
  user: {{ id: "user-1" }},
  route: {{ path: "/workspace/review", query: new URLSearchParams(`project_id=${{projectA}}`) }},
  projectFlow: {{ status: "idle", projectId: "", requestId: 0, data: null, error: null }},
}};
const WORKSPACE_PROJECT_FLOW_TIMEOUT_MS = 10_000;
const projectFlowRequestProjectId = () => requestScope;
const withUiTimeout = (promise) => promise;
const normalizeProjectFlow = (value) => value;
const render = () => undefined;
const persistWorkspaceProject = () => undefined;
const currentWorkspaceProjectName = () => "Проект";
const navigate = (route) => navigations.push(route);
const workspaceSectionRequiresProject = () => false;
const clearWorkspaceProjectSelection = () => true;
{loader}

const staleRequest = loadProjectFlow({{ silent: true }});
requestScope = "";
state.route = {{ path: "/workspace/home", query: new URLSearchParams() }};
const catalogRequest = loadProjectFlow({{ silent: true }});

if (JSON.stringify(calls) !== JSON.stringify([projectA, ""])) throw new Error(`calls:${{JSON.stringify(calls)}}`);
resolveProjectA({{ project_id: projectA, project: {{ id: projectA, name: "Старый" }}, projects: [], stages: [] }});
await staleRequest;
if (navigations.length) throw new Error(`stale-navigation:${{navigations.join(",")}}`);
resolveCatalog({{
  project_id: "",
  project: null,
  projects: [{{ id: "22222222-2222-4222-8222-222222222222", name: "Новый" }}],
  stages: [],
}});
await catalogRequest;
if (state.projectFlow.projectId !== "") throw new Error(`scope:${{state.projectFlow.projectId}}`);
if (state.projectFlow.data?.project_id !== "") throw new Error("catalog-lost");
if (navigations.length) throw new Error(`catalog-navigation:${{navigations.join(",")}}`);
process.stdout.write("ok");
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == "ok"


def test_global_workspace_routes_work_without_a_project_but_production_routes_do_not() -> None:
    policy = _function(APP, "function workspaceSectionRequiresProject(")
    workspace = _function(APP, "function renderWorkspace(")
    ai_loader = _function(APP, "async function loadAiLearningControlRoom(")

    assert 'new Set(["home", "team", "feedback", "ai"])' in APP
    assert 'normalizedSection === "work"' in policy
    assert '=== "notifications"' in policy
    assert "workspaceSectionRequiresProject(section)" in workspace
    assert 'if (section !== "home" && !currentWorkspaceProjectId())' not in workspace
    assert 'const notificationOnlyWork = section === "work"' in workspace
    assert 'sectionState.status = "ready"' in workspace
    assert "const hasProject = isWorkspaceProjectId(projectId)" in ai_loader
    assert "const marketIndexRequest = hasProject" in ai_loader
    assert "Promise.resolve({ skipped: true })" in ai_loader
    assert "state.api.aiLearningControlRoom({ category })" in ai_loader


def test_project_change_invalidates_generation_receipt_before_new_scope_is_used() -> None:
    activate = _function(APP, "function activateWorkspaceProject(")
    clear = _function(APP, "function clearWorkspaceProjectSelection(")
    draft_key = _function(APP, "function generationFormDraftStorageKey(")

    for source in (activate, clear):
        assert "cancelGenerationFormDraftSave();" in source
        assert "resetGenerationSpecState();" in source
        assert "clearContentGenerationHandoff();" in source
        assert "clearGenerationRepair();" in source
        assert "clearGenerationMediaSelection();" in source
        assert "clearGenerationFormDraft();" not in source

    assert activate.index("cancelGenerationFormDraftSave();") < activate.index(
        "persistWorkspaceProject(id, projectName);"
    )
    assert "currentWorkspaceProjectId()" in draft_key
    assert ":${organizationId}:${userId}:${projectId}`" in draft_key


def test_stale_or_archived_project_selection_recovers_to_the_catalog() -> None:
    loader = _function(APP, "async function loadProjectFlow(")

    assert "workspace_project_not_found" in loader
    assert "workspace_project_archived" in loader
    assert "clearWorkspaceProjectSelection(projectId)" in loader
    assert "workspaceSectionRequiresProject(activeSection, state.route.query)" in loader
    assert "if (mustLeaveRoute)" in loader
    assert 'navigate("/workspace/home", true, { scopeProject: false })' in loader
    assert 'query.delete("project_id")' in loader
    assert 'navigate(`${state.route.path}${search ? `?${search}` : ""}`, true, { scopeProject: false })' in loader


def test_project_catalog_redirects_only_sections_that_require_a_project() -> None:
    loader = _function(APP, "async function loadProjectFlow(")

    assert "&& workspaceSectionRequiresProject(" in loader
    assert 'state.route.path.split("/").filter(Boolean).at(-1) || "home"' in loader
    assert '&& state.route.path !== "/workspace/home"' not in loader


def test_project_load_failure_keeps_exactly_one_primary_action() -> None:
    switcher = _function(APP, "function homeProjectSwitcherMarkup(")
    create = _function(APP, "async function submitHomeProjectCreate(")

    # Losing the catalog must never remove project creation for a role that is
    # allowed to create one.  Creation remains the primary recovery path;
    # catalog retry is primary only for read-only users.
    assert "const createProject = canCreateProject" in switcher
    assert 'class="home-project-create" ${!loading && !projects.length ? "open" : ""}' in switcher
    assert "const retryIsPrimary = projectListFailed && !canCreateProject" in switcher
    assert "retryIsPrimary ? 'data-primary-action=\"true\"' : \"\"" in switcher
    assert 'class="home-project-switcher__body"' in switcher
    assert 'value="${escapeHtml(projectDraftName)}"' in switcher
    assert "state.workspaceBoard.projectDraftName = name" in create
    assert 'state.workspaceBoard.projectDraftName = ""' in create
    assert "state.workspaceBoard.projectCreateError = actionErrorMessage(error)" in create
    assert "const storedProject = projectListFailed ? storedWorkspaceProject() : null" in switcher
    assert 'next_action: { label: "Проверить доступ и продолжить" }' in switcher
    recovery_body = _css_rules(CORE_CSS, ".home-project-switcher__body")
    assert recovery_body
    assert any("align-content: start" in body and "overflow-y: visible" in body for body in recovery_body)


def test_selected_project_home_renders_one_action_instead_of_a_dashboard() -> None:
    home = _function(APP, "function renderHomeSection(")
    selected = home[home.index("const action = serverProjectNextAction") :]
    template = selected[selected.index("return `", selected.index("const actionControl")) :]

    assert "serverProjectNextAction(projectFlow.next_action, projectFlow)" in selected
    assert "homeNextAction(" not in selected
    assert "workspace-home--single-action" in template
    assert template.count('class="card home-single-action"') == 1
    assert template.count("${actionControl}") == 1
    assert "home-project-grid" not in template
    assert "home-project-card" not in template
    assert "metric-card" not in template
    assert "factory-flow" not in template
    assert "doneWhen" in template and "nextHint" in template


def test_workspace_links_and_context_menu_keep_the_selected_project() -> None:
    scope_links = _function(APP, "function scopeWorkspaceAnchorHrefs(")
    scoped_hash = _function(CONTEXT_TRASH, "function scopedWorkspaceHash(")
    open_route = _function(CONTEXT_TRASH, "function openWorkspaceRoute(")

    assert 'a[href^="#/workspace/"]' in scope_links
    assert "scopedWorkspaceAnchorHref(href)" in scope_links
    assert 'link.setAttribute("href", scopedHref)' in scope_links
    assert "project_id" in scoped_hash
    assert 'query.set("project_id", projectId)' in scoped_hash
    assert "window.location.hash = scopedWorkspaceHash(route)" in open_route
    for route in (
        "/workspace/board",
        "/workspace/media",
        "/workspace/research",
        "/workspace/team",
        "/workspace/feedback",
    ):
        assert f'openWorkspaceRoute("{route}' in CONTEXT_TRASH


def test_system_folders_are_read_only_in_forms_handlers_and_the_context_menu() -> None:
    normalize = _function(BOARD, "function normalizeFolder(")
    tree = _function(BOARD, "function folderTreeMarkup(")
    management = _function(BOARD, "function folderManagementMarkup(")
    descriptor = _function(CONTEXT_TRASH, "function folderDescriptor(")
    actions = _function(CONTEXT_TRASH, "function folderActions(")
    edit = _function(APP, "async function submitWorkspaceFolderEdit(")
    archive = _function(APP, "async function archiveWorkspaceBoardFolder(")

    assert "editable: !systemRole &&" in normalize
    assert "source.can_edit === true" in normalize
    assert 'data-system-role="${escapeHtml(folder.systemRole || "")}"' in tree
    assert "Boolean(String(row.dataset.systemRole || \"\").trim())" in descriptor
    assert 'row.dataset.systemFolder === "true"' in descriptor
    assert 'id === "all"' in descriptor and 'id === "root"' in descriptor

    # System rows retain only truthful open/copy affordances. Every mutation
    # is absent from their PKM menu instead of failing after a misleading click.
    assert actions.count("!folder.system") >= 3
    assert re.search(
        r"finderOrganizeMode\(\)\s*&&\s*!folder\.system[\s\S]*"
        r"focusFolderEditor\(folder,\s*\"rename\"\)",
        actions,
    )
    assert re.search(
        r"if\s*\(!folder\.system\)[\s\S]*copyText\(folder\.id",
        actions,
    )
    assert re.search(
        r"finderOrganizeMode\(\)\s*&&\s*!folder\.system[\s\S]*"
        r"archiveFolder\(folder\)",
        actions,
    )

    assert "selected && selected.editable" in management
    assert "busy || !selected?.editable" in management
    assert "if (folder?.systemRole)" in edit
    assert edit.index("if (folder?.systemRole)") < edit.index("state.api.updateWorkspaceFolder")
    assert "if (folder.systemRole)" in archive
    assert archive.index("if (folder.systemRole)") < archive.index("state.api.archiveProject")


def test_archiving_a_project_uses_its_dedicated_path_and_clears_stale_scope() -> None:
    archive = _function(APP, "async function archiveWorkspaceBoardFolder(")
    management = _function(BOARD, "function folderManagementMarkup(")
    project_start = archive.index('if (folder.kind === "project")')
    project_end = archive.index("await state.api.updateWorkspaceFolder", project_start)
    project_branch = archive[project_start:project_end]

    assert 'selected?.kind === "project"' in management
    assert "archiveLabel" in management and "selectedIsProject" in management
    assert "archiveHint" in management and "selectedIsProject" in management
    assert "await state.api.archiveProject(" in project_branch
    assert "folder.id" in project_branch
    assert "expectedVersion" in project_branch
    assert "clearWorkspaceProjectSelection(folder.id)" in project_branch
    assert 'state.workspaceBoard.selectedFolderId = "all"' in project_branch
    assert 'state.workspaceBoard.selectedItemKey = ""' in project_branch
    assert 'navigate("/workspace/home", false, { scopeProject: false })' in project_branch
    assert "updateWorkspaceFolder" not in project_branch


def test_v47_assets_share_one_release_key() -> None:
    build = "20260826.rebuild-clean.54"
    assert f'const BUILD = "{build}"' in LOADER
    assert f'const BUILD = "{build}"' in CORE
    assert './workspace-os-v4-loader.js?v=20260826.rebuild-clean.54' in INDEX
    assert './app.js?v=20260826.rebuild-clean.54' in INDEX
    assert './workspace-os-v4.css?v=20260826.rebuild-clean.54' in INDEX
    assert f'./training-journey.css?v={build}' in INDEX
    assert (
        './workspace-build-guard.js?v=20260826.rebuild-clean.54'
        in INDEX
    )
    for asset in (
        "workspace-dom-patch.js",
        "workspace-action-key.js",
        "content-generation-handoff.js",
        "product-research-view.js",
        "training-journey.js",
    ):
        assert f'./{asset}?v={build}' in APP
    assert (
        './supabase-api.js?v=20260826.rebuild-clean.54'
        in APP
    )
    assert (
        './generation-form-draft.js?v=20260826.rebuild-clean.54'
        in APP
    )


def test_academy_achievement_is_inline_status_not_a_subwindow() -> None:
    achievement = _function(TRAINING, "export function achievementMarkup(")
    click = _function(APP, "async function handleClick(")
    completion_start = click.index('if (action === "complete-course")')
    completion = click[
        completion_start : click.index('if (action === "refresh-section")', completion_start)
    ]
    rules = _css_rules(TRAINING_CSS, ".training-achievement")

    assert "training-achievement--inline" in achievement
    assert 'role="status"' in achievement
    assert 'aria-live="polite"' in achievement
    for modal_marker in ('role="dialog"', 'aria-modal="true"', "data-action=", "<button"):
        assert modal_marker not in achievement
    assert rules
    assert not any(re.search(r"position\s*:\s*fixed", rule) for rule in rules)
    assert "const nextCourse" in completion
    assert "const destination = nextCourse" in completion
    assert '"/learn/practical"' in completion
    assert "await flowHandoff(" in completion
    assert "showTrainingAchievement" not in completion
    assert 'role="dialog"' not in completion


def test_persistent_project_switcher_dock_and_bell_expose_live_state() -> None:
    menubar = _function(CORE, "function ensureMenubar(")
    dock = _function(CORE, "function ensureDock(")
    update_dock = _function(CORE, "function updateDock(")
    update_menubar = _function(CORE, "function updateMenubar(")

    assert re.search(r"project[-_ ]switch|сменить проект|выбрать проект", menubar, re.IGNORECASE)
    assert re.search(r"aria-(?:label|expanded).{0,100}проект", menubar, re.IGNORECASE | re.DOTALL)
    assert "project" in dock.casefold()
    assert re.search(r"(?:complete|completed|blocked|next|waiting|count)", update_dock, re.IGNORECASE)

    # The bell must say that work exists without forcing the user to open it.
    bell_sources = f"{menubar}\n{update_menubar}"
    assert re.search(
        r"notification.{0,300}(?:badge|count|unread)",
        bell_sources,
        re.IGNORECASE | re.DOTALL,
    )
    assert re.search(
        r"(?:badge|count|unread).{0,300}notification",
        bell_sources,
        re.IGNORECASE | re.DOTALL,
    )
    assert "/workspace/work?view=notifications" in bell_sources


def test_finder_has_breadcrumb_and_folder_history_in_the_url() -> None:
    finder_markup = f"{BOARD}\n{FINDER}"
    assert re.search(r"breadcrumb|хлебн", finder_markup, re.IGNORECASE)
    assert re.search(r"aria-label=[^>]*(?:путь|папк|breadcrumb)", finder_markup, re.IGNORECASE)

    selection = _function(FINDER, "function handleBoardFolderSelection(")
    assert re.search(
        r"URLSearchParams|location\.hash|history\.(?:pushState|replaceState)"
        r"|folder.{0,80}(?:route|url)|(?:route|url).{0,80}folder",
        selection,
        re.IGNORECASE | re.DOTALL,
    )
    assert re.search(r"\.set\(\s*[\"']folder[\"']", FINDER)


def test_finder_tree_can_collapse_and_remembers_expansion() -> None:
    tree = _function(BOARD, "function folderTreeMarkup(")
    finder_sources = f"{FINDER}\n{tree}"
    assert "aria-expanded" in tree
    assert re.search(r"folder[-_](?:toggle|expand|collapse)|toggle[-_]folder", finder_sources, re.IGNORECASE)
    assert re.search(r"expanded|collapsed", FINDER, re.IGNORECASE)
    assert "remember(" in FINDER or "Storage" in FINDER


def test_finder_multiselect_supports_batch_move_and_reversible_trash() -> None:
    finder_sources = f"{FINDER}\n{BOARD}\n{CONTEXT_TRASH}"
    assert re.search(r"selected(?:Items|Keys|Cards)|multiSelect|multiSelection", FINDER, re.IGNORECASE)
    assert re.search(r"(?:ctrlKey|metaKey)", FINDER)
    assert "shiftKey" in FINDER
    assert re.search(r"aria-selected|data-[^=\s]*selected", BOARD, re.IGNORECASE)
    assert re.search(r"(?:batch|selected).{0,180}(?:move|перемест)", finder_sources, re.IGNORECASE | re.DOTALL)
    assert re.search(r"(?:batch|selected).{0,180}(?:trash|корзин)", finder_sources, re.IGNORECASE | re.DOTALL)
    assert "showUndoToast" in CONTEXT_TRASH


def test_new_projects_receive_a_small_default_folder_set_server_side() -> None:
    # Defaults are created atomically with the project so a reload cannot leave
    # an apparently successful but empty project shell.
    assert re.search(r"Исходники", MIGRATIONS, re.IGNORECASE)
    assert re.search(r"Готов(?:ые|о)|Создан(?:ные|о)", MIGRATIONS, re.IGNORECASE)
    assert re.search(r"Опублик", MIGRATIONS, re.IGNORECASE)
    assert re.search(
        r"(?:create_workspace_folder|project).{0,8000}(?:Исходники).{0,2000}(?:Опублик)",
        MIGRATIONS,
        flags=re.IGNORECASE | re.DOTALL,
    )


def test_readable_typography_has_shared_ui_and_meta_scales() -> None:
    assert re.search(
        r"--ce-v4-(?=[-\w]*(?:ui|body|readable))(?=[-\w]*(?:text|font|size))"
        r"[-\w]*\s*:\s*(?:14px|0?\.875rem)",
        ALL_CSS,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"--ce-v4-(?=[-\w]*(?:meta|small|caption))(?=[-\w]*(?:text|font|size))"
        r"[-\w]*\s*:\s*(?:12px|0?\.75rem)",
        ALL_CSS,
        flags=re.IGNORECASE,
    )
    assert "--ce-v4-font-control: var(--ce-v4-ui-font-size)" in CORE_CSS
    assert "--ce-v4-font-helper: var(--ce-v4-meta-font-size)" in CORE_CSS
    assert "font-size: var(--ce-v4-font-control)" in ALL_CSS
    assert "font-size: var(--ce-v4-font-helper)" in ALL_CSS

    for filename, source in V4_CSS.items():
        for match in re.finditer(
            r"font-size\s*:\s*(?P<value>\d+(?:\.\d+)?)(?P<unit>px|rem)",
            source,
            flags=re.IGNORECASE,
        ):
            value = float(match.group("value"))
            size_px = value if match.group("unit").lower() == "px" else value * 16
            assert size_px >= 12, (
                f"{filename} exposes {match.group(0)!r}; helper text must stay at least 12px"
            )
        for match in re.finditer(
            r"\bfont\s*:[^;{}]*?(?P<value>\d+(?:\.\d+)?)(?P<unit>px|rem)\s*/",
            source,
            flags=re.IGNORECASE,
        ):
            value = float(match.group("value"))
            size_px = value if match.group("unit").lower() == "px" else value * 16
            assert size_px >= 12, (
                f"{filename} exposes {match.group(0)!r}; helper text must stay at least 12px"
            )

    assert re.search(
        r"body\.contentengine-desktop-v4\s+:is\([^{}]*(?:button|input)[^{}]*\)\s*"
        r"\{[^{}]*font-size\s*:\s*var\(--ce-v4-font-control\)\s*!important",
        CORE_CSS,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for selector in (
        ".ce-v4-flowbar__label",
        ".ce-v4-stage strong",
        ".ce-v4-spotlight-result strong",
    ):
        rules = _css_rules(CORE_CSS, selector)
        assert rules and any("var(--ce-v4-font-control)" in body for body in rules), selector
    dock_label_rules = _css_rules(CORE_CSS, ".ce-v4-dock__label")
    assert dock_label_rules and any("clip-path: inset(50%)" in body for body in dock_label_rules)
    home_summary_rules = _css_rules(CORE_CSS, ".home-project-create summary")
    assert home_summary_rules and any(
        "var(--ce-v4-font-control)" in body for body in home_summary_rules
    )


def test_workspace_window_scroll_contract_allows_only_finder_desktop_panes() -> None:
    main_rules = _css_rules(CORE_CSS, "#main-content")
    assert main_rules and any(re.search(r"overflow\s*:\s*hidden", body) for body in main_rules)
    window_body_rules = _css_rules(CORE_CSS, ".ce-v4-window__body")
    assert window_body_rules and any(
        re.search(r"overflow-y\s*:\s*auto", body) for body in window_body_rules
    )

    nested_scrollers = (
        (CORE_CSS, ".home-project-grid"),
        (GENERATION_CSS, ".ce-v4-generation-guided__panel-content"),
        (REVIEW_CSS, ".ce-v4-review-guided__panel-content"),
        (CONTEXT_TRASH_CSS, ".ce-v4-trash-surface__body"),
        (CONTEXT_TRASH_CSS, ".ce-v4-trash-preview__body > aside"),
        (CONTEXT_TRASH_CSS, ".ce-v4-trash-preview__body"),
    )
    for source, selector in nested_scrollers:
        for body in _css_rules(source, selector):
            assert not re.search(r"overflow-y\s*:\s*(?:auto|scroll)", body), (
                f"{selector} must grow inside the workspace window body instead of creating a second vertical scroll"
            )

    # Finder is a three-pane file manager on desktop: its folder tree, file
    # collection and inspector stay aligned while each long pane scrolls.
    # The compact layout explicitly gives ownership back to the route scroll.
    for selector in (
        ".workspace-board__folders",
        ".workspace-board__grid",
        ".workspace-board__drawer",
    ):
        rules = _css_rules(FINDER_CSS, selector)
        assert rules and any(
            re.search(r"overflow-y\s*:\s*auto", body) for body in rules
        ), selector

    mobile = FINDER_CSS[
        FINDER_CSS.index("@container ce-v4-finder-host (max-width: 760px)"):
        FINDER_CSS.index("@container ce-v4-finder-host (max-width: 480px)")
    ]
    for selector in (".workspace-board__folders", ".workspace-board__grid"):
        rules = _css_rules(mobile, selector)
        assert rules and any(
            re.search(r"overflow-y\s*:\s*visible", body) for body in rules
        ), selector


def test_route_loader_failure_is_an_inline_retryable_state() -> None:
    assert re.search(
        r"data-[^=\s]*(?:loader|route)[^=\s]*retry|dataset\.[A-Za-z]*(?:Loader|Route)[A-Za-z]*Retry",
        LOADER,
        re.IGNORECASE,
    )
    assert re.search(r"Повтор(?:ить|ная)|retry", LOADER, re.IGNORECASE)
    assert re.search(r"addEventListener\(.{0,240}(?:retry|click)", LOADER, re.IGNORECASE | re.DOTALL)
    exported = LOADER[LOADER.index("window.ContentEngineDesktopV4Loader") :]
    assert re.search(r"\bretry\s*:", exported)
    assert "location.reload" not in LOADER


def test_same_route_handoff_replaces_the_completed_item_from_the_top() -> None:
    handoff = _function(APP, "async function flowHandoff(")
    reset = _function(CORE, "function resetActionScroll(")
    # Запись 29.08.2026: якорь сдвинут ОСОЗНАННО — публичный API теперь за
    # стражем эпохи (коммит 88dcae02): глобалом владеет ПЕРВАЯ загрузившаяся
    # сборка. Хвост от нового якоря по-прежнему накрывает Object.freeze({...}).
    exported = CORE[CORE.index("window.ContentEngineDesktopV4 = desktopEpochHeld") :]

    assert "sameDestination" in handoff
    assert "resetActionScroll?.(destination)" in handoff
    assert "navigate(destination)" in handoff
    assert "delete states[actionKey]" in reset
    assert "node.scrollTop = 0" in reset
    assert 'shell.dataset.workspaceActionKey = ""' in reset
    assert "resetActionScroll," in exported


def test_flow_handoff_shows_one_confirmation_instead_of_a_second_toast() -> None:
    handoff = _function(APP, "async function flowHandoff(")

    assert 'confirmation.dataset.flowConfirmation = "true"' in handoff
    desktop_call = handoff[handoff.index("ContentEngineDesktopV4.handoff") :]
    assert "message," not in desktop_call
    assert 'tone: "success"' not in desktop_call
    assert 'action === "retry-project-flow"' not in handoff
    assert "control.disabled" not in handoff

    click = _function(APP, "async function handleClick(")
    retry_start = click.index('if (action === "retry-project-flow")')
    retry_end = click.index('if (action === "choose-media-upload-files")', retry_start)
    retry = click[retry_start:retry_end]
    assert "await loadProjectFlow({ silent: true, force: true })" in retry
    assert "if (control.isConnected) control.disabled = false" in retry


def test_academy_completion_can_request_workspace_access_without_bypassing_gate() -> None:
    render = _function(APP, "function render(")
    assert render.index("if (academyRequired())") < render.index("if (!hasWorkspaceAccess())")

    access = _function(APP, "function renderWorkspaceAccessRequired(")
    assert re.search(r"Запросить доступ|request-workspace-access", access, re.IGNORECASE)
    assert re.search(r"Академ|обучен|сертифик", access, re.IGNORECASE)
    assert re.search(r"data-action=[\"']request[^\"']*access", access, re.IGNORECASE)

    assert re.search(r"requestWorkspaceAccess|request_workspace_access", API)
    request_handlers = list(re.finditer(
        r"(?:request-workspace-access|request_workspace_access)[\s\S]{0,2500}",
        APP,
        flags=re.IGNORECASE,
    ))
    request_handler = next(
        (
            match.group(0)
            for match in request_handlers
            if re.search(r"state\.api\.[A-Za-z]*request[A-Za-z]*Access", match.group(0), re.IGNORECASE)
        ),
        "",
    )
    assert request_handler
    assert not re.search(r"navigate\([^)]*/workspace/home", request_handler)


def test_placement_and_stats_deep_links_prepend_the_exact_project_object() -> None:
    load = _function(APP, "async function loadSection(")
    merge = _function(APP, "function mergeProjectPlacementDeepLink(")
    prepend = _function(APP, "function prependExactPlacementItem(")

    assert '["placement", "stats"].includes(section)' in load
    assert 'safeWorkspaceRouteEntityId("placement")' in load
    assert "state.api.projectPlacement(routePlacementId, { projectId })" in load
    assert '"project_placement_deep_link_timeout"' in load
    assert load.index("const projectPlacementRequest") < load.index("let raw = await")
    assert "await projectPlacementRequest" in load
    assert "mergeProjectPlacementDeepLink(" in load

    assert "resultProjectId !== normalizedProjectId" in merge
    assert "placement?.project_id" in merge
    for collection in ("placements", "publications", "publication_options"):
        assert f"{collection}: prependExactPlacementItem(" in merge
    assert "exactPlacementItemId(candidate) !== normalizedPlacementId" in prepend
    assert "return [item, ...withoutExact]" in prepend


def test_generation_review_and_files_deep_links_prepend_exact_media_without_fallback() -> None:
    load = _function(APP, "async function loadSection(")
    exact = _function(APP, "function exactProjectMediaDeepLinkRecord(")
    merge = _function(APP, "function mergeProjectMediaDeepLink(")
    generation = _function(APP, "function renderGenerationSection(")
    review = _function(APP, "function renderContentReviewSection(")

    assert '["generation", "review", "board"].includes(section)' in load
    assert 'safeWorkspaceRouteEntityId("media")' in load
    assert 'section === "board" ? "files" : section' in load
    assert "state.api.projectMedia(routeMediaId, { projectId, surface: projectMediaSurface })" in load
    assert '"project_media_deep_link_timeout"' in load
    assert load.index("const projectMediaRequest") < load.index("let raw = await")
    assert "await projectMediaRequest" in load
    assert "mergeProjectMediaDeepLink(" in load

    assert "resultProjectId !== normalizedProjectId" in exact
    assert "resultSurface !== normalizedSurface" in exact
    assert '["generation", "review", "files"].includes(normalizedSurface)' in exact
    assert "exactMediaId !== normalizedMediaId" in exact
    assert "media?.project_id" in exact
    assert "return null" in exact
    assert 'listFrom(source, "media", "media_items", "artifacts")' in merge
    assert 'normalizedSurface === "files" ? "items" : "media"' in merge
    assert "media," in merge
    assert "!== normalizedMediaId" in merge

    assert "routeMediaId" in generation and "routeSelectedMediaId" in generation
    assert "routeMediaId && !routeSelectedMediaId" in generation
    assert "exactMediaMissing" in review
    assert "!catalog.media.some" in review
