from pathlib import Path
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
SUPABASE_API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


EXPECTED_FLOW = [
    "media",
    "generation",
    "review",
    "tasks",
    "placement",
    "stats",
    "payouts",
]


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _workspace_tab_keys() -> list[str]:
    block = _between(CATALOG, "export const WORKSPACE_TABS", "]);",)
    return re.findall(r'\[\s*"([a-z]+)"\s*,', block)


def _run_home_next_action(payload: dict) -> dict:
    functions = "\n".join(
        (
            _between(APP, "function isActionablePlacement", "function isCompletedPlacement"),
            _between(APP, "function isCompletedPlacement", "function isAutomaticGenerationWait"),
            _between(APP, "function isAutomaticGenerationWait", "function homeNextAction"),
            _between(APP, "function homeNextAction", "function renderHomeSection"),
        )
    )
    script = f"""
import fs from "node:fs";
{functions}
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(homeNextAction(payload)));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        input=json.dumps(payload),
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_workspace_opens_on_a_dedicated_today_home() -> None:
    assert 'const WORKSPACE_HOME_TAB = Object.freeze(["home", "Сегодня", "⌂"]);' in APP
    assert 'WORKSPACE_HOME_TAB,' in _between(
        APP, "function visibleWorkspaceTabs", "function mobileTopbarMarkup"
    )
    assert 'navigate("/workspace/home", true)' in APP
    assert 'href="#/workspace/home"' in APP


def test_factory_flow_has_seven_ordered_user_facing_stages() -> None:
    flow = _between(APP, "const FACTORY_FLOW", "const HOME_SECTION_KEYS")
    flow_keys = re.findall(r'key:\s*"([a-z]+)"', flow)
    flow_steps = re.findall(r'step:\s*"(\d{2})"', flow)

    assert flow_keys == EXPECTED_FLOW
    assert flow_steps == ["01", "02", "03", "04", "05", "06", "07"]
    assert _workspace_tab_keys()[:7] == EXPECTED_FLOW
    assert [
        "Материалы",
        "Создание видео",
        "Проверка контента",
        "Задачи",
        "Публикации",
        "Результаты",
        "Выплаты",
    ] == re.findall(r'\[\s*"[a-z]+"\s*,\s*"([^"]+)"', _between(
        CATALOG, "export const WORKSPACE_TABS", "]);"
    ))[:7]


def test_home_and_section_headers_share_the_premium_flow_language() -> None:
    home = _between(APP, "function renderHomeSection", "function realGenerationSku")
    header = _between(APP, "function pageHeader", "function factoryFlowMarkup")
    flow = _between(APP, "function factoryFlowMarkup", "function sectionBody")

    assert 'class="home-hero"' in home
    assert 'class="home-flow-list"' in home
    assert "FACTORY_FLOW.map" in home
    assert "<h2>${FACTORY_FLOW.length} этапов одного результата</h2>" in home
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


def test_every_workspace_step_explains_now_done_stop_and_next() -> None:
    metadata = _between(APP, "const WORKSPACE_SECTION_META", "const COURSE_VISUAL_EXAMPLES")
    direction = _between(APP, "function workspaceDirectionMarkup", "function pageHeader")
    header = _between(APP, "function pageHeader", "function factoryFlowMarkup")

    for key in EXPECTED_FLOW:
        block = _between(metadata, f"  {key}: Object.freeze({{", "  }),")
        for field in ("now", "done", "guard", "nextLabel", "nextHref", "guideHref"):
            assert f"{field}:" in block

    assert "Сделайте сейчас" in direction
    assert "Готово, когда" in direction
    assert "Стоп-правило" in direction
    assert "Когда закончите" in direction
    assert 'aria-label="Что делать в этом разделе"' in direction
    assert "workspaceDirectionMarkup(meta)" in header
    assert 'meta.guideHref || "#/learn"' in header

    for selector in (
        ".workspace-direction",
        ".workspace-direction-steps",
        ".workspace-direction-footer",
        ".direction-next-link",
    ):
        assert selector in STYLES


def test_navigation_is_grouped_and_factory_steps_are_numbered() -> None:
    nav_link = _between(APP, "function workspaceNavLinkMarkup", "function workspaceScaffold")
    scaffold = _between(APP, "function workspaceScaffold", "function canManageTeam")
    mobile = _between(APP, "function mobileNavMarkup", "async function loadSection")

    assert "FACTORY_FLOW.find" in nav_link
    assert '"nav-stage-number"' in nav_link
    assert 'class="nav-link-copy"' in nav_link
    assert "workspaceNavLinkMarkup" in scaffold
    assert "Знания" in scaffold
    assert "Производство · 01–07" in mobile
    assert "Знания" in mobile
    assert ".nav-link-stage" in STYLES
    assert ".nav-stage-number" in STYLES


def test_home_action_closes_the_loop_through_metrics_and_payouts() -> None:
    home = _between(APP, "function homeNextAction", "function renderHomeSection")
    rendered_home = _between(APP, "function renderHomeSection", "function realGenerationSku")

    assert "publications" in home
    assert "payouts" in home
    assert 'href: "#/workspace/stats"' in home
    assert 'href: "#/workspace/payouts"' in home
    assert "doneWhen" in home
    assert "nextHint" in home
    assert 'class="home-next-action-proof"' in rendered_home
    assert "Готово, когда" in rendered_home
    assert ".home-next-action-proof" in STYLES


def test_home_action_routes_from_publication_to_metrics_then_payout() -> None:
    base = {
        "media": [{"id": "media-1"}],
        "batches": [],
        "tasks": [],
        "placements": [{"id": "placement-1", "status": "published"}],
        "publications": [
            {
                "placement_id": "placement-1",
                "status": "published",
                "observed_at": None,
            }
        ],
        "payouts": [],
    }

    assert _run_home_next_action(base)["href"] == "#/workspace/stats"

    with_metric_and_payout = {
        **base,
        "publications": [
            {
                "placement_id": "placement-1",
                "status": "published",
                "observed_at": "2026-07-15T12:00:00Z",
            }
        ],
        "payouts": [{"id": "payout-1", "status": "pending"}],
    }

    assert _run_home_next_action(with_metric_and_payout)["href"] == "#/workspace/payouts"


def test_learning_home_has_one_explicit_mandatory_next_step() -> None:
    learning = _between(APP, "function renderLearningHome", "function renderAccountLaunch")

    assert 'class="card learning-now"' in learning
    assert "Один обязательный шаг" in learning
    assert "Завершите только этот блок" in learning
    assert 'href="${nextHref}"' in learning
    assert ".learning-now" in STYLES


def test_empty_states_can_explain_waiting_and_offer_one_action() -> None:
    empty_state = _between(APP, "function emptyState", "function reserveManagerEmailAction")

    assert "action?.href" in empty_state
    assert "action?.target" in empty_state
    assert 'class="btn btn-secondary btn-small empty-state-action"' in empty_state
    assert "Ничего делать не нужно" in APP
    assert ".empty-state-action" in STYLES


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
