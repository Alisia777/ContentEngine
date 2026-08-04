from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
BOARD = (APP_DIR / "workspace-board-view.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
FLOW_CSS = (APP_DIR / "workspace-os-v4-flow.css").read_text(encoding="utf-8")
TRASH = (APP_DIR / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")


def _source_between(source: str, start: str, end: str) -> str:
    match = re.search(
        rf"{re.escape(start)}(?P<body>.*?){re.escape(end)}",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing source contract between {start!r} and {end!r}"
    return match.group("body")


def _css_rule_containing(marker: str) -> str:
    position = FLOW_CSS.find(marker)
    assert position >= 0, f"Missing flow selector: {marker}"
    rule_start = FLOW_CSS.rfind("}", 0, position) + 1
    rule_end = FLOW_CSS.find("}", position)
    assert rule_end >= 0, f"Unclosed flow rule for: {marker}"
    return FLOW_CSS[rule_start:rule_end]


def test_desktop_requires_the_authenticated_workspace_surface_and_excludes_learn() -> None:
    workspace_guard = _source_between(
        CORE,
        "function hasAuthenticatedWorkspace() {",
        "\n}\n\nfunction navigate",
    )
    route_guard = _source_between(
        CORE,
        "function isWorkspaceRoute(route = routePath()) {",
        "\n}\n\nfunction hasAuthenticatedWorkspace",
    )

    assert 'q(".workspace-shell[data-workspace-section]")' in workspace_guard
    assert 'q("#workspace-content")' in workspace_guard
    assert 'route.startsWith("/workspace/")' in route_guard
    assert "/learn" not in route_guard
    loader_guard = _source_between(
        LOADER,
        "function isManagedRoute(route = routePath()) {",
        "\n}\n\nfunction setLoading",
    )
    assert 'route.startsWith("/workspace/")' in loader_guard
    assert "/learn" not in loader_guard
    assert "if (!isWorkspaceRoute(route) || !hasAuthenticatedWorkspace())" in CORE


def test_mandatory_academy_is_conditional_and_not_a_second_desktop() -> None:
    render = _source_between(
        APP,
        "function render() {",
        "\n}\n\nfunction renderLogin",
    )
    academy_gate = _source_between(
        render,
        "if (academyRequired()) {",
        '\n  if (path === "/learn" || path.startsWith("/learn/"))',
    )
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
    assert "navigate(authenticatedStartPath(), true)" in render
    assert 'if (expected === "/learn")' not in CORE

    scaffold = _source_between(
        APP,
        "function learningScaffold(content, activePath) {",
        "\n}\n\nfunction renderLearningScaffold",
    )
    assert 'class="learning-gate-shell"' in scaffold
    assert 'class="workspace-shell"' not in scaffold
    assert 'class="sidebar"' not in scaffold
    assert "learningActionSwitchMarkup" not in scaffold


def test_native_v4_scaffold_contains_only_the_authorized_content_surface() -> None:
    scaffold = _source_between(
        APP,
        "function workspaceScaffold(content, activeSection) {",
        "\n}\n\nfunction refreshNotificationLayer",
    )
    native = _source_between(
        scaffold,
        "if (window.CONTENTENGINE_DESKTOP_V4 === true) {",
        "\n  const profile = displayProfile()",
    )
    for marker in (
        'class="workspace-shell workspace-shell-v4"',
        'class="workspace-main workspace-main-v4"',
        'id="main-content"',
        'id="workspace-content"',
        "data-workspace-authorized-routes",
        "data-workspace-role",
        "visibleWorkspaceTabs()",
    ):
        assert marker in native
    for legacy_chrome in (
        'class="sidebar"',
        "workspaceContextBarMarkup",
        "mobileTopbarMarkup",
        "mobileNavMarkup",
        "factoryFlowMarkup",
        "workspaceDirectionMarkup",
        "workspace-notification-layer",
    ):
        assert legacy_chrome not in native

    assert INDEX.index("./workspace-os-v4-loader.js") < INDEX.index("./app.js")


def test_canonical_factory_flow_is_five_actions_beneath_the_project_chooser() -> None:
    flow = _source_between(
        APP,
        "const FACTORY_FLOW = Object.freeze([",
        "\n]);\nconst FACTORY_FLOW_ALIASES",
    )
    assert re.findall(r'key:\s*"([^"]+)"', flow) == [
        "board",
        "generation",
        "review",
        "placement",
        "stats",
    ]
    assert re.findall(r'step:\s*"([^"]+)"', flow) == [
        "01",
        "02",
        "03",
        "04",
        "05",
    ]
    aliases = _source_between(
        APP,
        "const FACTORY_FLOW_ALIASES = Object.freeze({",
        "\n});\nconst HOME_SECTION_KEYS",
    )
    assert 'media: "board"' in aliases
    assert 'payouts: "stats"' in aliases
    for deep_context in ("tasks", "work", "media", "payouts"):
        assert f'key: "{deep_context}"' not in flow

    dock = _source_between(
        CORE,
        "const ROUTES = Object.freeze([",
        "\n]);\n\nconst SECONDARY_ROUTES",
    )
    assert re.findall(r'route:\s*"([^"]+)"', dock) == [
        "/workspace/home",
        "/workspace/board",
        "/workspace/generation",
        "/workspace/review",
        "/workspace/placement",
        "/workspace/stats",
        "/workspace/research",
        "/workspace/ai",
    ]


def test_v4_page_headers_replace_the_large_direction_bar_with_one_compact_instruction() -> None:
    header = _source_between(
        APP,
        "function pageHeader(title, description, actions = \"\") {",
        "\n}\n\nfunction factoryFlowMarkup",
    )
    assert "const nativeV4 = window.CONTENTENGINE_DESKTOP_V4 === true" in header
    assert "!nativeV4 && inFactoryFlow ? factoryFlowMarkup(activeSection)" in header
    assert 'nativeV4 ? "" : workspaceDirectionMarkup(meta)' in header
    assert 'nativeV4 && !ownsFocusedAction ? workspaceActionGuideMarkup(meta) : ""' in header
    assert '["board", "generation", "review", "placement", "stats", "tasks"]' in header
    assert ".workspace-action-guide" in FLOW_CSS
    assert "Готово, когда:" in APP
    assert "После выполнения" in APP


def test_review_decision_hands_the_user_to_the_only_logical_next_screen() -> None:
    decision = _source_between(
        APP,
        "async function submitContentReviewDecision(form, submitter) {",
        "\n}\n\nasync function submitMedia",
    )
    assert 'const resolvedDecision = contextApproval ? "approved" : decision.decision' in decision
    assert 'if (resolvedDecision === "needs_changes")' in decision
    assert 'flowHandoff(' in decision
    assert 'const freshFlow = await loadProjectFlow({ silent: true, force: true })' in decision
    assert 'const exactNext = exactProjectNextActionRoute(freshFlow, projectId)' in decision
    assert 'exactNext.startsWith("/workspace/generation?")' in decision
    assert 'if (resolvedDecision === "approved")' in decision
    assert '/workspace/placement?view=next&placement=' in decision
    assert 'content_review_exact_placement_missing' in decision
    assert decision.index('await track("content_review_decided"') < decision.index(
        '/workspace/placement?view=next&placement='
    )


def test_dock_adds_research_and_ai_after_the_six_primary_workflow_routes() -> None:
    dock_source = _source_between(
        CORE,
        "const ROUTES = Object.freeze([",
        "\n]);\n\nconst SECONDARY_ROUTES",
    )
    dock_routes = re.findall(r'route:\s*"([^"]+)"', dock_source)

    assert dock_routes == [
        "/workspace/home",
        "/workspace/board",
        "/workspace/generation",
        "/workspace/review",
        "/workspace/placement",
        "/workspace/stats",
        "/workspace/research",
        "/workspace/ai",
    ]
    for forbidden_label in ("Задачи", "Академия", "Выплаты", "Моя работа"):
        assert forbidden_label not in dock_source

    route_record = _source_between(
        CORE,
        "function routeRecord(route = routePath()) {",
        "\n}\n\nfunction isWorkspaceRoute",
    )
    assert "route === item.route" in route_record
    assert route_record.index("route === item.route") < route_record.index("routeMatches")


def test_home_is_project_first_and_keeps_valid_server_driven_review_links() -> None:
    project_home = _source_between(
        APP,
        "function homeProjectSwitcherMarkup(action) {",
        "\n}\n\nfunction renderHomeSection",
    )
    compositor = _source_between(
        CORE,
        "function mountHome() {",
        "\n}\n\nfunction projectContext",
    )
    assert "data-ce-v4-project-home" in project_home
    assert "data-ce-v4-project-id" in project_home
    assert "home-project-create-form" in project_home
    assert "projectFlow.projects" in project_home
    assert "project.next_action" in project_home
    assert "exactProjectNextActionRoute" in project_home
    assert 'href="#${escapeHtml(nextRoute)}"' in project_home
    assert "const projects = projectFlow.projects" in project_home
    assert "board.folders" not in project_home
    assert 'q("[data-ce-v4-project-home]", page)' in compositor
    assert "dataset.ceV4Surface" in compositor
    assert "home-project-create-form" not in compositor
    assert "WORK_SNAPSHOT_KEY" not in CORE
    assert APP.count(
        '#/workspace/review?view=current&review=${encodeURIComponent('
    ) >= 3
    assert '#/workspace/review/${' not in APP


def test_loader_uses_flow_css_without_legacy_route_adapters() -> None:
    assert "workspace-os-v4-flow.css?v=${BUILD}" in LOADER
    assert "reject(new Error(`ContentEngine stylesheet unavailable:" in LOADER
    assert 'link.addEventListener("error", resolve' not in LOADER
    assert "function setFailed(" in LOADER
    assert 'delete document.documentElement.dataset.ceV4Ready' in LOADER
    assert 'document.documentElement.dataset.ceV4Failed = "true"' in LOADER
    assert "setFailed(scheduledRoute, error)" in LOADER
    for retired_adapter in (
        "workspace-academy",
        "workspace-generation-os",
        "workspace-desktop-os",
        "workspace-publishing-os",
    ):
        assert retired_adapter not in LOADER


def test_generation_query_views_use_outcome_names_instead_of_model_names() -> None:
    assert 'const requestedView = String(state.route.query.get("view") ||' in APP
    assert '(routeJobId ? "history" : "create")' in APP
    assert '["create", "history", "products"].includes(requestedView)' in APP
    assert 'data-generation-view="${escapeHtml(generationView)}"' in APP
    assert '#/workspace/generation?view=${key}' in APP

    label_source = _source_between(
        APP,
        "function generationModeChoiceLabel(mode) {",
        "\n}\n\nfunction generationActionSwitch",
    )
    labels = re.findall(r':\s*"([^"]+)"', label_source)
    assert labels == [
        "Фото товара · квадрат 2K",
        "Ролик с человеком и голосом",
        "Анимация товара без речи",
    ]
    visible_labels = " ".join(labels).casefold()
    for model_name in ("runway", "seedream", "seedance", "gen-4", "gen4", "turbo"):
        assert model_name not in visible_labels


def test_media_query_views_separate_upload_from_recent_and_link_to_files() -> None:
    assert 'const requestedView = String(state.route.query.get("view") || "upload")' in APP
    assert 'const mediaView = requestedView === "recent" ? "recent" : "upload"' in APP
    assert 'data-media-view="${mediaView}"' in APP
    assert 'href="#/workspace/board">Файлы и папки</a>' in APP
    assert 'href="#/workspace/media?view=upload"' in APP
    assert 'href="#/workspace/media?view=recent"' in APP


def test_finder_media_handoff_is_persisted_and_preferred_by_generation() -> None:
    assert 'data-action="create-from-workspace-media"' in BOARD
    assert 'data-entity-id="${escapeHtml(selectedItem.id)}"' in BOARD
    assert (
        'GENERATION_MEDIA_SELECTION_STORAGE_KEY = '
        '"contentengine.generation-media-selection.v1"'
    ) in APP

    selection_storage = _source_between(
        APP,
        "function readStoredGenerationMediaSelection() {",
        "\n}\n\nfunction prepareRecommendedResearchHandoff",
    )
    assert "window.sessionStorage" in selection_storage
    assert "persistGenerationMediaSelection(mediaId, projectId)" in APP
    assert re.search(
        r"finderSelectedMediaId\s*\|\|\s*chooseInitialGenerationMedia",
        APP,
    )


def test_trash_reuses_the_authenticated_workspace_runtime_api() -> None:
    assert "window.ContentEngineWorkspaceRuntime" in APP
    assert "getApi: () => state.api" in APP
    assert "window.ContentEngineWorkspaceRuntime?.getApi?.()" in TRASH


def test_secondary_and_context_routes_stay_outside_the_primary_dock() -> None:
    menubar = _source_between(CORE, "function ensureMenubar() {", "\n}\n\nfunction updateClock")
    assert "SECONDARY_ROUTES.forEach" in menubar
    assert 'setAttribute("role", "menu")' in menubar
    assert 'setAttribute("role", "menuitem")' in menubar
    assert "link.dataset.ceV4ToolsRoute = item.route" in menubar
    for route in (
        "/workspace/research",
        "/workspace/ai",
        "/workspace/team",
        "/workspace/feedback",
    ):
        assert f'route: "{route}"' in CORE
    secondary = _source_between(
        CORE,
        "const SECONDARY_ROUTES = Object.freeze([",
        "\n]);\n\nconst CONTEXT_ROUTES",
    )
    context = _source_between(
        CORE,
        "const CONTEXT_ROUTES = Object.freeze([",
        "\n]);\nconst ALL_ROUTES",
    )
    assert re.findall(r'route:\s*"([^"]+)"', secondary) == [
        "/workspace/team",
        "/workspace/feedback",
    ]
    for duplicate in (
        "/workspace/tasks",
        "/workspace/work",
        "/workspace/media",
        "/workspace/payouts",
    ):
        assert f'route: "{duplicate}"' not in secondary
    for contextual in ("/workspace/tasks", "/workspace/work"):
        assert f'route: "{contextual}"' in context
    for detached in ("/workspace/media", "/workspace/payouts"):
        assert f'route: "{detached}"' not in context
    ensure_dock = _source_between(CORE, "function ensureDock() {", "\n}\n\nfunction updateDock")
    assert "ROUTES.forEach" in ensure_dock
    assert "SECONDARY_ROUTES.forEach" not in ensure_dock
    assert 'route: "/learn"' not in CORE
    for label, href in (
        ("Разбор товара", "/workspace/research"),
        ("Команда", "/workspace/team"),
        ("Помощь и обратная связь", "/workspace/feedback"),
    ):
        assert f'menuAction("{label}"' in TRASH
        assert f'openWorkspaceRoute("{href}")' in TRASH
    assert 'menuAction("Инструкции"' not in TRASH
    assert '"#/learn"' not in TRASH


def test_dock_is_the_only_global_switcher_and_project_progress_is_contextual() -> None:
    progress = _source_between(CORE, "function syncProjectProgress() {", "\n}\n\nfunction overlayBase")
    dock = _source_between(CORE, "function ensureDock() {", "\n}\n\nfunction updateDock")
    matches = _source_between(CORE, "function routeMatches(route, expected) {", "\n}\n\nfunction routeRecord")
    active_index = _source_between(
        CORE,
        "function activeProjectFlowIndex(",
        "\n}\n\nfunction stageLocked",
    )
    update_dock = _source_between(CORE, "function updateDock() {", "\n}\n\nfunction updateMenubar")

    assert "function ensureFlowbar" not in CORE
    assert 'create("nav", "ce-v4-flowbar")' not in CORE
    assert "data-ce-v4-flow-route" not in CORE
    assert "ce-v4-menubar__location" not in CORE
    assert CORE.count('const dock = create("nav", "ce-v4-dock");') == 1
    assert progress.count('create("nav", "ce-v4-project-progress")') == 1
    assert "progress.dataset.ceV4ProjectProgress = context.id" in progress
    assert "PROJECT_FLOW.forEach((item, index)" in progress
    assert 'link.setAttribute("aria-current", "step")' in progress
    assert "page.prepend(progress)" in progress
    assert 'create("span", "ce-v4-dock__label", item.label)' in dock
    assert "link.title = `${item.label} — ${item.description}`" in dock
    assert 'expected === "/workspace/home"' in matches
    assert 'route !== "/workspace/tasks"' in active_index
    assert 'routeQuery().get("stage") || routeQuery().get("origin_stage")' in active_index
    assert 'route === "/workspace/tasks"' in update_dock
    assert 'focusedStageIndex >= 0 ? PROJECT_FLOW[focusedStageIndex].route : "/workspace/home"' in update_dock
    assert "PROJECT_FLOW[focusedStageIndex].route" in update_dock


def test_flow_css_hides_every_surface_that_is_inactive_for_the_selected_view() -> None:
    inactive_surfaces = (
        '[data-generation-view="create"] .generation-archive-card',
        '[data-generation-view="create"] .generation-product-tools',
        '[data-generation-view="history"] .generation-launch-card',
        '[data-generation-view="history"] .generation-product-tools',
        '[data-generation-view="products"] .generation-launch-card',
        '[data-generation-view="products"] .generation-archive-card',
        '[data-media-view="recent"] .media-upload-panel',
        '[data-media-view="upload"] .media-library-panel',
    )

    for selector in inactive_surfaces:
        assert "display: none !important" in _css_rule_containing(selector)


def test_review_stats_tasks_and_placement_have_explicit_action_views() -> None:
    for marker in (
        'class="focus-queue__bar"',
        'workspaceActionSwitch("stats-action-switch"',
        'data-review-view="${escapeHtml(reviewView)}"',
        'data-placement-view="${placementView}"',
        'data-stats-view="${statsView}"',
        'data-task-view="${taskView}"',
        'data-focus-queue="review"',
        'data-focus-queue="placement"',
        'data-focus-queue="tasks"',
    ):
        assert marker in APP

    for inactive_selector in (
        '[data-review-view="new"] .content-review-output',
        '[data-review-view="current"] #content-review-form',
        '[data-review-view="history"] .content-review-layout',
        '[data-stats-view="overview"] .stats-entry-panel',
        '[data-stats-view="new"] .stats-overview-panel',
    ):
        assert "display: none !important" in _css_rule_containing(inactive_selector)


def test_default_task_and_placement_views_render_one_actionable_record() -> None:
    tasks = _source_between(
        APP,
        "function renderTasksSection(sectionState) {",
        "\n}\n\nfunction taskCard",
    )
    placements = _source_between(
        APP,
        "function renderPlacementSection(sectionState) {",
        "\n}\n\nfunction placementHistoryCard",
    )

    assert 'requestedView === "queue" ? "queue" : "next"' in tasks
    assert 'nextTask ? [nextTask] : []' in tasks
    assert "visibleItems.map(taskQueueCard)" in tasks
    assert 'requestedView === "history" ? "history" : "next"' in placements
    assert 'nextPlacement ? [nextPlacement] : []' in placements
    assert "visibleItems.map(placementHistoryCard)" in placements
    assert 'action("review", "Взять на проверку")' in APP
    assert 'action("review", "Взять на проверку") +' not in APP


def test_primary_dock_defaults_expose_one_unambiguous_next_action() -> None:
    review = _source_between(
        APP,
        "function renderContentReviewSection(sectionState) {",
        "\n}\n\nfunction selectPendingContentReviewMedia",
    )
    generation = _source_between(
        APP,
        "function renderGenerationSection(sectionState) {",
        "\n}\n\nfunction generationArchiveMarkup",
    )
    placement = _source_between(
        APP,
        "function placementCard(item) {",
        "\n}\n\nfunction renderStatsSection",
    )

    assert 'contentReviewStatusKind(item.status) === "ready" && !item.decision' in review
    assert "routeReviewId || activeReview || pendingDecision" in review

    acceptance = "generationModelAcceptanceMarkup("
    archive = '<section class="card generation-archive-card">'
    assert generation.count(acceptance) == 1
    assert generation.index(archive) < generation.index(acceptance)

    assert 'class="btn" type="submit" data-primary-action="true"' in placement
    assert 'class="btn btn-secondary" type="submit" data-primary-action="true"' not in placement


def test_same_route_refresh_restores_internal_scroll_before_next_paint() -> None:
    assert "captureWorkspaceScroll(existingContent)" in APP
    assert "restoreWorkspaceScroll(existingContent, scrollSnapshot, section)" in APP
    restore = _source_between(
        APP,
        "function restoreWorkspaceScroll(container, snapshot, section, expectedPath = `/workspace/${section}`) {",
        "\n}\n\nfunction captureWorkspaceFocus",
    )
    assert "apply();" in restore
    assert "requestAnimationFrame" not in restore


def test_mac_shell_stays_mounted_while_workspace_views_change() -> None:
    workspace_render = _source_between(
        APP,
        "function renderWorkspace(section) {",
        "\n}\n\nconst WORKSPACE_SCROLL_OWNERS",
    )
    assert "syncPersistentWorkspaceShell(existingShell, section)" in workspace_render
    assert "existingContent.innerHTML = content" in workspace_render
    same_section_branch = workspace_render[
        workspace_render.index(
            'if (existingShell?.dataset.workspaceSection === section && existingContent) {'
        ) : workspace_render.index(
            "\n  if (\n    window.CONTENTENGINE_DESKTOP_V4 === true"
        )
    ]
    assert "patchWorkspaceContent(existingContent, content)" in same_section_branch
    assert "existingContent.innerHTML" not in same_section_branch
    assert workspace_render.index("syncPersistentWorkspaceShell") < workspace_render.index(
        "app.innerHTML = workspaceScaffold"
    )
    persistent_branch = workspace_render[
        workspace_render.index("window.CONTENTENGINE_DESKTOP_V4 === true") :
        workspace_render.index("app.innerHTML = workspaceScaffold")
    ]
    assert "resetWorkspaceRouteEntry(existingContent, section)" in persistent_branch
    assert "const sameAction = previousActionKey === nextActionKey" in same_section_branch
    assert "if (!sameAction)" in same_section_branch
    assert "resetWorkspaceRouteEntry(existingContent, section)" in same_section_branch

    reset_entry = _source_between(
        APP,
        "function resetWorkspaceRouteEntry(container, section) {",
        "\n}\n\nfunction captureWorkspaceFocus",
    )
    assert "workspaceScrollNodes(container)" in reset_entry
    assert "node.scrollTop = 0" in reset_entry
    assert "node.scrollLeft = 0" in reset_entry
    assert 'main.focus({ preventScroll: true })' in reset_entry
