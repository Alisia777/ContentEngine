from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
FULL = (ROOT / "web/app/first-shift-full-scenario.js").read_text(encoding="utf-8")
FULL_STYLES = (ROOT / "web/app/first-shift-full-scenario.css").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_first_shift_uses_the_full_thirteen_decision_scenario() -> None:
    step_ids = re.findall(r'^\s+id: "([a-z0-9_]+)",$', FULL, flags=re.MULTILINE)

    assert 'from "./first-shift-full-scenario.js?v=20260715.8"' in APP
    assert len(set(step_ids) & {
        "receive_task",
        "verify_articles_reward",
        "select_sources",
        "build_shot_plan",
        "approve_8s_brief",
        "choose_production_path",
        "paid_preflight",
        "paid_status_without_restart",
        "quality_control",
        "choose_platform_disclosure",
        "return_post_url",
        "record_metrics",
        "understand_payout",
    }) == 13
    for term in (
        "подменный артикул",
        "точные исходники",
        "9:16",
        "Стоимость видна до запуска",
        "Этикетка меняет буквы",
        "раскрытие",
        "URL конкретного опубликованного клипа",
        "Выплачено",
    ):
        assert term.casefold() in FULL.casefold()


def test_first_shift_route_is_handled_before_generic_course_route_for_both_gates() -> None:
    render = _between(APP, "function render()", "function renderLogin")
    route = 'path === "/learn/first-shift"'
    generic = 'path.startsWith("/learn/") && path !== "/learn/exam"'

    assert render.count(route) == 2
    assert render.count("renderFirstShift();") == 2
    first_gate, second_gate = render.split('if (path === "/learn")', maxsplit=1)
    assert first_gate.index(route) < first_gate.index(generic)
    assert second_gate.index(route) < second_gate.index(generic)


def test_first_shift_progress_is_user_scoped_session_only_and_restartable() -> None:
    state_helpers = _between(APP, "function firstShiftStorageKey", "function renderFirstShift()")
    clear = _between(APP, "function clearAuthenticatedState", "function consumeRouteTransitionClass")

    assert 'const FIRST_SHIFT_STORAGE_PREFIX = "contentengine.first-shift.v2";' in APP
    assert "createFirstShiftFullState" in state_helpers
    assert "state.user?.id" in state_helpers
    assert "encodeURIComponent" in state_helpers
    assert "window.sessionStorage.getItem(firstShiftStorageKey(userId))" in state_helpers
    assert "window.sessionStorage.setItem(firstShiftStorageKey(practice.userId)" in state_helpers
    assert "window.localStorage" not in state_helpers
    assert '[FIRST_SHIFT_FULL_ACTIONS.restart]: "restart"' in APP
    assert 'restart: "first-shift-full-restart"' in FULL
    assert "state.firstShift = null" in clear


def test_first_shift_feedback_blocks_next_until_the_wrong_answer_is_corrected() -> None:
    clicks = _between(APP, "async function handleClick", "async function handleSubmit")
    adapter = _between(clicks, "const firstShiftEventType", 'if (action === "complete-course")')

    assert "data-first-shift-form" in FULL
    assert 'role="status" tabindex="-1"' in FULL
    assert 'data-action="${FIRST_SHIFT_FULL_ACTIONS.check}"' in FULL
    assert 'data-action="${FIRST_SHIFT_FULL_ACTIONS.next}"' in FULL
    assert "if (!passed) return state" in FULL
    assert "evaluateFirstShiftFullAnswer" in FULL
    assert "reduceFirstShiftFullState(practice, eventPayload)" in adapter
    assert "persistFirstShiftState()" in adapter
    assert 'app.querySelector(".first-shift-full__feedback")' in adapter
    assert 'if (firstShiftEventType === "select")' in adapter
    assert "renderFirstShift()" in adapter
    assert "selectedControl?.focus?.({ preventScroll: true })" in adapter


def test_first_shift_is_a_zero_side_effect_practice_not_a_training_gate() -> None:
    renderer = _between(APP, "function renderFirstShift()", "function courseVisualExamplesMarkup")
    clicks = _between(APP, "async function handleClick", "async function handleSubmit")
    adapter = _between(clicks, "const firstShiftEventType", 'if (action === "complete-course")')
    isolated = renderer + FULL + adapter

    for forbidden in (
        "state.api",
        "completeModule",
        "submitExam",
        "submitCourseCheck",
        "track(",
        "REAL_GENERATION_ENABLED",
        "submitRealGeneration",
    ):
        assert forbidden not in isolated
    assert "не заменяет курсы или итоговый экзамен" in renderer
    assert "Учебный режим · списаний нет" in renderer


def test_first_shift_legacy_simulator_is_fully_removed() -> None:
    for legacy_contract in (
        "const FIRST_SHIFT_SCENARIO",
        "function createFirstShiftState",
        "function resetFirstShiftState",
        "function renderFirstShiftComplete",
        "function submitFirstShift",
        'action === "first-shift-reset"',
        'action === "first-shift-previous"',
        'action === "first-shift-next"',
        'id="first-shift-form"',
        "first_shift_answer",
        "completedStepIds",
        "practice.finished",
    ):
        assert legacy_contract not in APP


def test_first_shift_is_linked_from_home_sidebar_and_mobile_navigation() -> None:
    home = _between(APP, "function renderLearningHome", "function portalWorkflowMarkup")
    sidebar = _between(APP, "function learningScaffold", "function renderWorkspace")
    mobile = _between(APP, "function mobileNavMarkup", "async function loadSection")

    assert 'href="#/learn/first-shift"' in home
    assert "Тренажёр не создаёт задач, не списывает деньги и не влияет на допуск." in home
    assert 'activePath === "/learn/first-shift"' in sidebar
    assert 'aria-current="page"' in sidebar
    assert 'activeLearningPath === "/learn/first-shift"' in mobile
    assert "Первая смена" in sidebar
    assert "Первая смена" in mobile


def test_first_shift_has_keyboard_focus_status_and_360px_safe_layout_contracts() -> None:
    assert 'id="first-shift-full-title" tabindex="-1"' in FULL
    assert 'id="first-shift-step-title" tabindex="-1"' in FULL
    assert 'role="progressbar"' in FULL
    assert 'aria-current="step"' in FULL
    assert 'role="status" tabindex="-1"' in FULL
    assert ".first-shift-full__option:has(input:focus-visible)" in FULL_STYLES
    assert "min-width: 0" in FULL_STYLES
    assert "width: 100%" in FULL_STYLES
    assert "box-sizing: border-box" in FULL_STYLES
    assert "@media (max-width: 760px)" in FULL_STYLES
    assert "@media (prefers-reduced-motion: reduce)" in FULL_STYLES
    assert './first-shift-full-scenario.css?v=20260715.8' in INDEX
