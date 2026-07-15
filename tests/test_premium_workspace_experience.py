from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
SUPABASE_API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


EXPECTED_FLOW = ["media", "generation", "tasks", "placement", "stats", "payouts"]


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _workspace_tab_keys() -> list[str]:
    block = _between(CATALOG, "export const WORKSPACE_TABS", "]);",)
    return re.findall(r'\[\s*"([a-z]+)"\s*,', block)


def test_workspace_opens_on_a_dedicated_today_home() -> None:
    assert 'const WORKSPACE_HOME_TAB = Object.freeze(["home", "Сегодня", "⌂"]);' in APP
    assert 'WORKSPACE_HOME_TAB,' in _between(
        APP, "function visibleWorkspaceTabs", "function mobileTopbarMarkup"
    )
    assert 'navigate("/workspace/home", true)' in APP
    assert 'href="#/workspace/home"' in APP


def test_factory_flow_has_six_ordered_user_facing_stages() -> None:
    flow = _between(APP, "const FACTORY_FLOW", "const HOME_SECTION_KEYS")
    flow_keys = re.findall(r'key:\s*"([a-z]+)"', flow)
    flow_steps = re.findall(r'step:\s*"(\d{2})"', flow)

    assert flow_keys == EXPECTED_FLOW
    assert flow_steps == ["01", "02", "03", "04", "05", "06"]
    assert _workspace_tab_keys()[:6] == EXPECTED_FLOW
    assert [
        "Материалы",
        "Создание видео",
        "Задачи",
        "Публикации",
        "Результаты",
        "Выплаты",
    ] == re.findall(r'\[\s*"[a-z]+"\s*,\s*"([^"]+)"', _between(
        CATALOG, "export const WORKSPACE_TABS", "]);"
    ))[:6]


def test_home_and_section_headers_share_the_premium_flow_language() -> None:
    home = _between(APP, "function renderHomeSection", "function realGenerationSku")
    header = _between(APP, "function pageHeader", "function factoryFlowMarkup")
    flow = _between(APP, "function factoryFlowMarkup", "function sectionBody")

    assert 'class="home-hero"' in home
    assert 'class="home-flow-list"' in home
    assert "FACTORY_FLOW.map" in home
    assert "Шесть этапов одного результата" in home
    assert 'class="workspace-page-intro"' in header
    assert "factoryFlowMarkup(activeSection)" in header
    assert 'class="factory-flow"' in flow
    assert 'aria-label="Этапы производственного цикла"' in flow
    assert 'aria-current="step"' in flow

    for selector in (
        ".workspace-page-intro",
        ".factory-flow",
        ".home-hero",
        ".home-flow-list",
    ):
        assert selector in STYLES


def test_error_states_never_render_raw_service_messages() -> None:
    section_body = _between(APP, "function sectionBody", "function emptyState")
    fatal = _between(APP, "function renderFatal", "function parseRoute")

    assert "console.error(sectionState.error)" in section_body
    assert "sectionState.error?.message" not in APP
    assert "sectionState.error.message" not in APP
    assert "error?.message" not in fatal
    assert "error.message" not in fatal
    assert "Обновите страницу" in fatal


def test_route_motion_is_scoped_and_respects_reduced_motion() -> None:
    assert 'return "route-enter";' in APP
    assert ".route-enter" in STYLES
    assert re.search(r"\.route-enter\s*\{[^}]*animation\s*:", STYLES, re.DOTALL)

    reduced_motion = _between(
        STYLES,
        "@media (prefers-reduced-motion: reduce)",
        "}",
    )
    assert "animation-duration: 0.01ms !important" in STYLES
    assert "transition-duration: 0.01ms !important" in STYLES
    assert "scroll-behavior: auto !important" in STYLES
    assert reduced_motion


def test_mobile_menu_exposes_state_and_keyboard_escape() -> None:
    topbar = _between(APP, "function mobileTopbarMarkup", "function mobileNavMarkup")
    mobile_nav = _between(APP, "function mobileNavMarkup", "async function loadHome")

    assert 'aria-controls="mobile-navigation"' in topbar
    assert 'aria-expanded="${state.mobileNavOpen}"' in topbar
    assert "Открыть меню" in topbar
    assert 'id="mobile-navigation"' in mobile_nav
    assert 'aria-label="Мобильная навигация"' in mobile_nav
    assert "setMobileNavOpen" in APP
    assert '"Escape"' in APP or "'Escape'" in APP
    assert ".mobile-nav-trigger" in STYLES
    assert ".mobile-nav" in STYLES


def test_home_loading_is_race_safe_and_survives_partial_api_failure() -> None:
    load_home = _between(APP, "async function loadHome", "function isActionablePlacement")

    assert "requestEpoch = state.dataEpoch" in load_home
    assert "requestUserId = state.user?.id" in load_home
    assert "requestId = state.home.requestId + 1" in load_home
    assert "requestEpoch !== state.dataEpoch" in load_home
    assert "requestId !== state.home.requestId" in load_home
    assert 'state.route.path === "/workspace/home"' in load_home
    assert "previousData[section] || {}" in load_home
    assert "failed.length === results.length" in load_home
    assert "state.home.unavailable" in load_home
    assert "state.sections[section].data = data" not in load_home
    assert "options.silent" not in load_home

    load_section = _between(APP, "async function loadSection", "async function hydratePrivateMedia")
    assert "requestId = target.requestId + 1" in load_section
    assert "requestId !== target.requestId" in load_section
    assert "state.sections[section].requestId += 1" in APP


def test_bootstrap_context_commits_only_for_the_current_user_request() -> None:
    load = _between(APP, "async function loadBootstrap", "function normalizeBootstrap")
    clear = _between(APP, "function clearAuthenticatedState", "function consumeRouteTransitionClass")
    fetch = _between(SUPABASE_API, "async bootstrap", "commitBootstrapContext")
    commit = _between(SUPABASE_API, "commitBootstrapContext", "completeModule")

    assert "bootstrapRequestId: 0" in APP
    assert "requestEpoch = state.dataEpoch" in load
    assert "requestUserId = state.user?.id" in load
    assert "requestId = state.bootstrapRequestId + 1" in load
    assert load.count("requestId !== state.bootstrapRequestId") == 2
    assert load.count("requestEpoch !== state.dataEpoch") == 2
    assert load.count("requestUserId !== state.user?.id") == 2
    assert load.index("requestUserId !== state.user?.id") < load.index("commitBootstrapContext(raw)")

    assert "this.organizationId" not in fetch
    assert "this.storageBucket" not in fetch
    assert "this.storagePrefix" not in fetch
    assert "this.organizationId = organizationId" in commit
    assert "this.storageBucket = storageBucket" in commit
    assert "this.storagePrefix = storagePrefix" in commit
    assert "clearBootstrapContext()" in SUPABASE_API

    assert "state.dataEpoch += 1" in clear
    assert "state.bootstrapRequestId += 1" in clear
    assert "state.session = null" in clear
    assert "state.user = null" in clear
    assert "state.api?.clearBootstrapContext()" in clear
    assert "state.realGenerationStartInFlight = false" in clear


def test_workspace_refresh_preserves_dirty_forms_and_files() -> None:
    workspace = _between(APP, "function renderWorkspace", "function workspaceScaffold")

    assert "workspaceInitialLoadingMarkup(section)" in workspace
    assert "captureDirtyWorkspaceForms(existingContent)" in workspace
    assert "restoreDirtyWorkspaceForms(existingContent, dirtyForms)" in workspace
    assert 'form[data-dirty="true"]' in workspace
    assert "new DataTransfer()" in workspace
    assert '["checkbox", "radio"].includes(field.type)' in workspace
    assert 'document.addEventListener("input", handleFormActivity)' in APP
    assert 'form.dataset.dirty = "true"' in APP
    assert 'zone.closest("form")?.setAttribute("data-dirty", "true")' in APP


def test_paid_generation_stays_single_flight_across_workspace_rerenders() -> None:
    workspace = _between(APP, "function renderWorkspace", "function workspaceScaffold")
    submit = _between(APP, "async function submitRealGeneration", "async function submitMockBatch")
    busy = _between(APP, "function setFormBusy", "function withUiTimeout")

    assert "realGenerationStartInFlight: false" in APP
    assert 'form[data-busy="true"]' in workspace
    assert "busyLabel:" in workspace
    assert "if (snapshot.busy) setFormBusy(form, true" in workspace

    assert "if (state.realGenerationStartInFlight)" in submit
    assert "state.realGenerationStartInFlight = true" in submit
    assert "finally" in submit
    assert "state.realGenerationStartInFlight = false" in submit
    assert 'document.querySelector("#mock-batch-form")' in submit

    assert 'form.dataset.busy = "true"' in busy
    assert "delete form.dataset.busy" in busy


def test_home_counts_only_real_user_actions_and_labels_data_scope() -> None:
    helpers = _between(APP, "function isActionablePlacement", "function realGenerationSku")

    assert '["scheduled", "ready"]' in helpers
    assert "placements.filter(isActionablePlacement)" in helpers
    assert "!isAutomaticGenerationWait(item)" in helpers
    assert "последние 50 записей каждого раздела" in helpers
    assert ".home-data-scope" in STYLES


def test_mobile_grids_and_focus_states_are_explicitly_accessible() -> None:
    assert ".form-grid-2" in STYLES
    assert re.search(
        r"@media \(max-width: 820px\).*?\.form-grid-2\s*\{\s*grid-template-columns:\s*1fr",
        STYLES,
        re.DOTALL,
    )
    assert "outline: 3px solid #315e91" in STYLES
    assert ".factory-flow a:focus-visible" in STYLES
    assert ".home-metric-card:focus-visible" in STYLES


def test_skip_link_does_not_change_the_hash_router() -> None:
    assert 'class="skip-link"' in INDEX
    assert 'data-action="skip-to-content"' in INDEX
    assert 'href="#main-content"' not in INDEX
    assert 'action === "skip-to-content"' in APP
