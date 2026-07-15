from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _media_blocks(css: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r"@media\s*\([^)]*\)\s*\{", css):
        depth = 1
        cursor = match.end()
        while cursor < len(css) and depth:
            if css[cursor] == "{":
                depth += 1
            elif css[cursor] == "}":
                depth -= 1
            cursor += 1
        assert depth == 0, "unterminated @media block"
        blocks.append(css[match.start() : cursor])
    return blocks


def test_first_shift_has_six_ordered_beginner_scenarios() -> None:
    catalog = _between(APP, "const FIRST_SHIFT_SCENARIO", "const state =")
    step_ids = re.findall(r'^\s+id: "([a-z]+)",$', catalog, flags=re.MULTILINE)

    assert step_ids == [
        "task",
        "materials",
        "production",
        "quality",
        "publication",
        "payout",
    ]
    for term in (
        "подменный артикул",
        "точные исходники",
        "9:16",
        "стоимость проверена",
        "искажённая этикетка",
        "рекламной маркировке",
        "URL клипа",
        "Выплачено",
    ):
        assert term.casefold() in catalog.casefold()


def test_first_shift_route_is_handled_before_generic_course_route_for_both_gates() -> None:
    render = _between(APP, "function render()", "function renderLogin")
    route = 'path === "/learn/first-shift"'
    generic = 'path.startsWith("/learn/") && path !== "/learn/exam"'

    assert render.count(route) == 2
    assert render.count("renderFirstShift();") == 2
    first_gate, second_gate = render.split('if (path === "/learn")', maxsplit=1)
    assert first_gate.index(route) < first_gate.index(generic)
    assert second_gate.index(route) < second_gate.index(generic)


def test_first_shift_progress_is_user_scoped_session_only_and_resettable() -> None:
    state_helpers = _between(APP, "function createFirstShiftState", "function renderFirstShift()")
    clear = _between(APP, "function clearAuthenticatedState", "function consumeRouteTransitionClass")

    assert 'const FIRST_SHIFT_STORAGE_PREFIX = "contentengine.first-shift.v1";' in APP
    assert "state.user?.id" in state_helpers
    assert "encodeURIComponent" in state_helpers
    assert "window.sessionStorage.getItem(firstShiftStorageKey(userId))" in state_helpers
    assert "window.sessionStorage.setItem(firstShiftStorageKey(practice.userId)" in state_helpers
    assert "window.localStorage" not in state_helpers
    assert "function resetFirstShiftState()" in state_helpers
    assert "state.firstShift = null" in clear


def test_first_shift_feedback_blocks_next_until_the_wrong_answer_is_corrected() -> None:
    renderer = _between(APP, "function renderFirstShift()", "function firstShiftSafetyBanner")
    submit = _between(APP, "function submitFirstShift", "async function submitLogin")
    clicks = _between(APP, "async function handleClick", "async function handleSubmit")

    assert 'id="first-shift-form"' in renderer
    assert 'aria-live="polite"' in renderer
    assert "Исправьте решение" in renderer
    assert "stepComplete" in renderer
    assert 'data-action="first-shift-next"' in renderer
    assert "expected.size === actual.size" in submit
    assert "practice.feedback = { stepId: step.id, passed" in submit
    assert "if (passed && !practice.completedStepIds.includes(step.id))" in submit
    assert "persistFirstShiftState()" in submit
    assert 'document.querySelector("#first-shift-feedback")' in submit

    next_action = _between(clicks, 'if (action === "first-shift-next")', 'if (action === "complete-course")')
    assert "if (!practice.completedStepIds.includes(step.id))" in next_action
    assert next_action.index("if (!practice.completedStepIds.includes(step.id))") < next_action.index("practice.stepIndex += 1")


def test_first_shift_is_a_zero_side_effect_practice_not_a_training_gate() -> None:
    renderer = _between(APP, "function renderFirstShift()", "function courseVisualExamplesMarkup")
    submit = _between(APP, "function submitFirstShift", "async function submitLogin")
    isolated = renderer + submit

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
    assert "Это тренировка, а не сертификация." in renderer
    assert "Прогресс курсов, экзамен и доступ к кабинету не изменились." in renderer
    assert "Учебный режим · списаний нет" in renderer


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
    assert 'id="first-shift-title" tabindex="-1"' in APP
    assert 'id="first-shift-step-title" tabindex="-1"' in APP
    assert 'aria-current="step"' in APP
    assert 'role="progressbar" aria-label="Прогресс первой смены"' in APP
    assert ".first-shift-options input:focus-visible + span" in STYLES
    assert "outline: 3px solid #315e91" in STYLES
    assert ".first-shift-layout" in STYLES
    assert ".first-shift-stage-grid" in STYLES
    assert "min-width: 0" in STYLES

    responsive = _media_blocks(STYLES)
    tablet = next(block for block in responsive if "max-width: 820px" in block)
    phone = next(block for block in responsive if "max-width: 560px" in block)
    narrow = next(block for block in responsive if "max-width: 380px" in block)
    assert re.search(r"\.first-shift-layout\s*\{[^}]*grid-template-columns:\s*1fr", tablet, re.DOTALL)
    assert re.search(r"\.first-shift-stage-grid\s*\{[^}]*grid-template-columns:\s*1fr", tablet, re.DOTALL)
    assert re.search(
        r"\.first-shift-roadmap ol\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        phone,
        re.DOTALL,
    )
    assert re.search(r"\.first-shift-roadmap ol\s*\{[^}]*grid-template-columns:\s*1fr", narrow, re.DOTALL)
