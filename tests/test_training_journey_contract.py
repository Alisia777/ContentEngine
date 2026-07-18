from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
JOURNEY = (ROOT / "web/app/training-journey.js").read_text(encoding="utf-8")
JOURNEY_STYLES = (ROOT / "web/app/training-journey.css").read_text(
    encoding="utf-8"
)
INTERACTIVE = (ROOT / "web/app/training-interactive.js").read_text(
    encoding="utf-8"
)
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _run_journey_javascript(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable training journey tests")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "training-journey.mjs").write_text(JOURNEY, encoding="utf-8")
        (directory / "journey-test.mjs").write_text(
            "import * as journey from './training-journey.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "journey-test.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _function_source(name: str) -> str:
    start = APP.index(f"function {name}(")
    next_function = APP.find("\nfunction ", start + 1)
    next_async = APP.find("\nasync function ", start + 1)
    candidates = [position for position in (next_function, next_async) if position >= 0]
    end = min(candidates) if candidates else len(APP)
    return APP[start:end]


def test_learning_track_and_lesson_journey_are_normalized_and_scoped() -> None:
    payload = _run_journey_javascript(
        r"""
        const initial = journey.normalizeLessonJourney({
          activeIndex: 99,
          understood: [2, 2, -1, "1", 88],
        }, 4);
        const advanced = journey.reduceLessonJourney(initial, {
          type: "understand",
          index: 3,
          moveNext: true,
        }, 4);
        return {
          validTrack: journey.normalizeLearningTrack("ai"),
          invalidTrack: journey.normalizeLearningTrack("owner"),
          trackKey: journey.learningTrackStorageKey("user 7"),
          lessonKey: journey.lessonJourneyStorageKey("user 7", "video_quality", 3),
          reordered: journey.normalizeLessonJourney({
            activeLessonId: "qa",
            understoodLessonIds: ["brief", "qa"],
          }, [{ id: "qa" }, { id: "brief" }, { id: "publish" }]),
          initial,
          advanced,
          percent: journey.lessonJourneyPercent(advanced, 4),
        };
        """
    )

    assert payload["validTrack"] == "ai"
    assert payload["invalidTrack"] == "all"
    assert payload["trackKey"].endswith("user%207")
    assert payload["lessonKey"].endswith("user%207:video_quality:curriculum-3")
    assert payload["initial"]["activeIndex"] == 3
    assert payload["initial"]["understood"] == [1, 2]
    assert payload["initial"]["activeLessonId"] == "lesson-4"
    assert payload["initial"]["understoodLessonIds"] == ["lesson-2", "lesson-3"]
    assert payload["advanced"]["activeIndex"] == 3
    assert payload["advanced"]["understood"] == [1, 2, 3]
    assert payload["reordered"]["activeIndex"] == 0
    assert payload["reordered"]["understoodLessonIds"] == ["qa", "brief"]
    assert payload["percent"] == 75


def test_home_asks_role_before_map_and_keeps_common_certification_explicit() -> None:
    home = _function_source("renderLearningHome")
    assert home.index("learningTrackPickerMarkup()") < home.index('id="work-map"')
    assert home.index("learningSafetyGateMarkup()") < home.index('id="work-map"')
    picker = _function_source("learningTrackPickerMarkup")
    assert "Кем вы будете в этой смене?" in picker
    assert "Четыре обязательных блока" in picker
    assert 'data-action="select-learning-track"' in picker
    assert "persistLearningTrack" in APP
    assert "training_track_selected" in APP
    safety = _function_source("learningSafetyGateMarkup")
    assert "Товар или артикул не совпадает" in safety
    assert "Рекламный статус публикации не подтверждён" in safety
    assert "Не пытайтесь убрать признаки рекламы" in safety


def test_role_path_reorders_groups_and_keeps_core_lessons() -> None:
    payload = _run_journey_javascript(
        r"""
        const lessons = [
          { id: "ai", audiences: ["ai"], required_core: false },
          { id: "shared", audiences: ["all"], required_core: true },
          { id: "self", audiences: ["self"], required_core: false },
          { id: "policy", audiences: ["publish"], required_core: true },
        ];
        const groups = [
          { id: "start", title: "Общее", lesson_ids: ["shared", "policy"] },
          { id: "branches", title: "Ветка", lesson_ids: ["self", "ai"] },
        ];
        return {
          selfIds: journey.roleAwareLessonPath("demo", lessons, groups, "self")
            .lessons.map((lesson) => lesson.id),
          selfRecommended: journey.roleAwareLessonPath("demo", lessons, groups, "self")
            .recommendedLessonIds,
          reviewIds: journey.roleAwareLessonPath("demo", lessons, groups, "review")
            .lessons.map((lesson) => lesson.id),
          reviewRecommended: journey.roleAwareLessonPath("demo", lessons, groups, "review")
            .recommendedLessonIds,
          allIds: journey.roleAwareLessonPath("demo", lessons, groups, "all")
            .lessons.map((lesson) => lesson.id),
        };
        """
    )

    assert payload["selfIds"] == ["shared", "policy", "self", "ai"]
    assert payload["selfRecommended"] == ["shared", "policy", "self"]
    assert payload["reviewIds"] == ["shared", "policy", "self", "ai"]
    assert payload["reviewRecommended"] == ["shared", "policy"]
    assert payload["allIds"] == ["shared", "policy", "self", "ai"]


def test_course_is_a_single_lesson_player_with_persisted_understanding() -> None:
    course = _function_source("renderCourse")
    lesson = _function_source("lessonMarkup")
    sync = _function_source("syncCourseLessonJourney")
    assert "courseLessonPlayerMarkup(course, lessonJourney)" in course
    assert 'data-action="training-lesson-open"' in course
    assert "lessonMarkup(lesson, index, course.lessons, lessonJourney)" in course
    assert "lesson.groupStart" in course
    assert "course-roadmap-group" in course
    assert 'data-course-lesson-details ${active ? "" : "hidden"}' in lesson
    assert 'data-action="training-lesson-understood"' in lesson
    assert "Понятно — следующий урок" in lesson
    assert "persistLessonJourney" in sync
    assert 'aria-current", index === normalized.activeIndex ? "step"' in sync
    assert "training_lesson_viewed" in sync


def test_walkthrough_restart_clears_answer_checks_feedback_and_completion() -> None:
    assert "export function resetTrainingWalkthroughState(" in INTERACTIVE
    reset = INTERACTIVE.split(
        "export function resetTrainingWalkthroughState(", 1
    )[1].split("\nexport function ", 1)[0]
    assert "input.checked = false" in reset
    assert 'trainingPracticeComplete = "false"' in reset
    assert 'trainingComplete = "false"' in reset
    assert "Выберите один вариант" in reset
    assert 'setTrainingWalkthroughMode(walkthrough, "watch")' in reset
    assert "resetTrainingWalkthroughState(root)" in APP
    reset_handler = APP.split('if (action === "training-walkthrough-reset") {', 1)[1].split("\n  if (", 1)[0]
    assert "persistTrainingWalkthroughState(root, { syncServer: false })" in reset_handler
    assert "Уже полученный зачёт сохраняется" in reset_handler


def test_achievement_requires_successful_server_completion_and_is_deduplicated() -> None:
    completion = APP.split('if (action === "complete-course") {', 1)[1].split(
        'if (action === "refresh-section")', 1
    )[0]
    complete_call = completion.index("await state.api.completeModule(moduleCode)")
    refresh_call = completion.index("await loadBootstrap()")
    confirmed = completion.index("const serverCompleted")
    decision = completion.index("shouldCelebrateCourse")
    display = completion.index("showTrainingAchievement(moduleCode, returnFocus)")
    assert complete_call < refresh_call < confirmed < decision < display
    assert "state.bootstrap.training.completedModules.includes(moduleCode)" in completion
    assert 'safeStorageGet(celebrationStorage, celebrationKey) === "shown"' in completion
    assert 'safeStorageSet(celebrationStorage, celebrationKey, "shown")' in completion
    assert "training_achievement_unlocked" in completion

    payload = _run_journey_javascript(
        r"""
        return {
          failed: journey.shouldCelebrateCourse({
            wasCompleted: false, serverCompleted: false, alreadyCelebrated: false,
          }),
          first: journey.shouldCelebrateCourse({
            wasCompleted: false, serverCompleted: true, alreadyCelebrated: false,
          }),
          repeat: journey.shouldCelebrateCourse({
            wasCompleted: true, serverCompleted: true, alreadyCelebrated: false,
          }),
          deduped: journey.shouldCelebrateCourse({
            wasCompleted: false, serverCompleted: true, alreadyCelebrated: true,
          }),
          markup: journey.achievementMarkup("factory_basics"),
        };
        """
    )
    assert payload["failed"] is False
    assert payload["first"] is True
    assert payload["repeat"] is False
    assert payload["deduped"] is False
    assert "Навигатор портала" in payload["markup"]
    assert 'data-action="play-training-fanfare"' in payload["markup"]
    assert "не заменяет итоговый экзамен" in payload["markup"]


def test_achievement_sound_is_explicit_and_motion_has_accessible_fallback() -> None:
    markup = JOURNEY.split("export function achievementMarkup", 1)[1].split(
        "export function playTrainingFanfare", 1
    )[0]
    assert "playTrainingFanfare()" not in markup
    assert "Звук включается только по вашему нажатию" in markup
    assert 'role="dialog"' in markup
    assert 'aria-modal="true"' in markup
    assert "if (action === \"play-training-fanfare\")" in APP
    assert "@media (prefers-reduced-motion: reduce)" in JOURNEY_STYLES
    reduced_motion = JOURNEY_STYLES.split(
        "@media (prefers-reduced-motion: reduce)", 1
    )[1]
    assert ".training-achievement__petals" in reduced_motion
    assert "display: none" in reduced_motion
    assert "max-height: calc(100svh - 40px)" in JOURNEY_STYLES
    assert "overflow-y: auto" in JOURNEY_STYLES
    assert 'event.key === "Escape"' in APP


def test_training_journey_assets_are_loaded_with_versioned_urls() -> None:
    assert './training-journey.css?v=20260718.3' in INDEX
    assert './app.js?v=20260718.6' in INDEX
    assert 'from "./training-journey.js?v=20260718.3"' in APP
    assert 'from "./training-interactive.js?v=20260718.4"' in APP


def test_missing_quiz_answers_move_focus_to_the_problem() -> None:
    course_check = APP.split("async function submitCourseKnowledgeCheck", 1)[1].split(
        "function syncCourseCompletionButton", 1
    )[0]
    exam = APP.split("async function submitExam", 1)[1].split(
        "async function ", 1
    )[0]
    assert 'fieldset?.setAttribute("aria-invalid", "true")' in course_check
    assert 'fieldset?.focus({ preventScroll: true })' in course_check
    assert 'firstIncorrect?.focus({ preventScroll: true })' in course_check
    assert 'card?.setAttribute("aria-invalid", "true")' in exam
    assert 'card?.focus({ preventScroll: true })' in exam
