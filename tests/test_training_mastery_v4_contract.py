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
INTERACTIVE = (ROOT / "web/app/training-interactive.js").read_text(
    encoding="utf-8"
)
SUPABASE_API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CREATOR_FACTORY_TEST = (ROOT / "supabase/tests/creator_factory_test.sql").read_text(
    encoding="utf-8"
)


def _run_module(source: str, module_name: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable training mastery tests")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / f"{module_name}.mjs").write_text(source, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            f"import * as subject from './{module_name}.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
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
    prefixes = (f"function {name}(", f"async function {name}(")
    starts = [APP.find(prefix) for prefix in prefixes]
    start = min(position for position in starts if position >= 0)
    candidates = [
        position
        for marker in ("\nfunction ", "\nasync function ")
        if (position := APP.find(marker, start + 1)) >= 0
    ]
    return APP[start : min(candidates) if candidates else len(APP)]


def _click_action_source(action: str) -> str:
    marker = f'if (action === "{action}") {{'
    start = APP.index(marker)
    end = APP.find("\n  if (", start + len(marker))
    return APP[start : end if end >= 0 else len(APP)]


def test_mastery_normalization_and_snapshot_are_deterministic() -> None:
    payload = _run_module(
        JOURNEY,
        "training-journey",
        r"""
        const normalized = subject.normalizeCourseMastery({
          required_walkthrough_ids: ["lab-a", "lab-a", "", "lab-b"],
          lesson_requirement: "unsupported",
          xp: { lessons: 40, practice: -9, test: 20, confirmation: 10 },
        });
        const emptyWeights = subject.normalizeCourseMastery({
          xp: { lessons: 0, practice: 0, test: 0, confirmation: 0 },
        });
        const partial = subject.courseMasterySnapshot({
          requiredLessonIds: ["intro", "policy"],
          understoodLessonIds: ["intro", "intro", "not-required"],
          requiredWalkthroughIds: ["lab-a", "lab-b"],
          completedWalkthroughIds: ["lab-a", "not-required"],
          testPassed: false,
          confirmationCount: 2,
          confirmedCount: 1,
        });
        const practiceNext = subject.courseMasterySnapshot({
          requiredLessonIds: ["intro"],
          understoodLessonIds: ["intro"],
          requiredWalkthroughIds: ["lab-a"],
          completedWalkthroughIds: [],
          testPassed: true,
          confirmationCount: 1,
          confirmedCount: 1,
        });
        const ready = subject.courseMasterySnapshot({
          requiredLessonIds: ["intro"],
          understoodLessonIds: ["intro"],
          requiredWalkthroughIds: ["lab-a"],
          completedWalkthroughIds: ["lab-a"],
          testPassed: true,
          confirmationCount: 2,
          confirmedCount: 99,
        });
        return { normalized, emptyWeights, partial, practiceNext, ready };
        """,
    )

    assert payload["normalized"]["requiredWalkthroughIds"] == ["lab-a", "lab-b"]
    assert payload["normalized"]["lessonRequirement"] == "recommended"
    assert payload["normalized"]["weights"] == {
        "lessons": 40,
        "practice": 30,
        "test": 20,
        "confirmation": 10,
    }
    assert payload["emptyWeights"]["weights"] == {
        "lessons": 35,
        "practice": 30,
        "test": 25,
        "confirmation": 10,
    }

    partial = payload["partial"]
    assert partial["xp"] == 38
    assert partial["ready"] is False
    assert partial["nextStep"] == "lessons"
    assert partial["tasks"]["lessons"] == {"complete": False, "done": 1, "total": 2}
    assert partial["tasks"]["practice"] == {"complete": False, "done": 1, "total": 2}
    assert payload["practiceNext"]["nextStep"] == "practice"
    assert payload["ready"]["xp"] == 100
    assert payload["ready"]["ready"] is True
    assert payload["ready"]["nextStep"] == "done"
    assert payload["ready"]["tasks"]["confirmation"]["done"] == 2


def test_course_mastery_coach_drives_and_guards_completion() -> None:
    course_parser = _function_source("learningCourses")
    coach_markup = _function_source("courseMasteryCoachMarkup")
    mastery_state = _function_source("courseMasteryState")
    mastery_sync = _function_source("syncCourseMasteryPanel")
    mastery_action = _click_action_source("training-mastery-next")
    completion = _click_action_source("complete-course")
    flush = _function_source("flushRequiredTrainingProgress")

    assert "normalizeCourseMastery(" in course_parser
    assert "COURSE_MASTERY_FALLBACKS" in course_parser
    assert "knowledge_remediation" in course_parser
    assert "knownLessonIds.has(item.lessonId)" in course_parser

    assert 'data-course-mastery-coach' in coach_markup
    assert 'data-course-mastery-xp' in coach_markup
    assert 'role="progressbar"' in coach_markup
    for step in ("lessons", "practice", "test", "confirmation"):
        assert step in coach_markup
    assert 'data-action="training-mastery-next"' in coach_markup

    assert "courseMasterySnapshot({" in mastery_state
    assert "serverCompleted ? requiredLessonIds" in mastery_state
    assert "serverCompleted\n    ? requiredWalkthroughIds" in mastery_state
    assert "testPassed:" in mastery_state and "serverCompleted" in mastery_state
    assert "button.disabled = !snapshot.ready || completionInFlight" in mastery_sync
    assert 'button.setAttribute("aria-busy"' in mastery_sync
    assert 'data-course-completion-reason' in APP

    for route in ("lessons", "practice", "test", "confirmation"):
        assert f'if (step === "{route}")' in mastery_action or f'else if (step === "{route}")' in mastery_action
    assert "courseRequiredLessonIds(course)" in mastery_action
    assert "requiredWalkthroughIds" in mastery_action
    assert "training_mastery_step_opened" in mastery_action

    guard = completion.index("if (!mastery?.ready)")
    flush_call = completion.index("await flushRequiredTrainingProgress(course)")
    complete_call = completion.index("await state.api.completeModule(moduleCode)")
    assert guard < flush_call < complete_call
    assert "persistTrainingWalkthroughState(root)" in flush
    assert "await drainTrainingProgressSaveQueue(key)" in flush
    assert "await waitForCompletedTrainingProgress(key)" in flush
    assert "completionInFlight.has(moduleCode)" in completion
    assert "completionInFlight.add(moduleCode)" in completion
    assert "completionInFlight.delete(moduleCode)" in completion


def test_failed_mini_test_has_exact_lesson_remediation() -> None:
    parser = _function_source("learningCourses")
    submit = _function_source("submitCourseKnowledgeCheck")

    assert "knowledge_remediation" in parser
    assert "lessonId" in parser and "tip" in parser
    assert "course.knowledgeRemediation?.[questionCode]" in submit
    assert "course.lessons.findIndex" in submit
    assert 'data-action="training-lesson-open"' in submit
    assert 'data-lesson-index="${topic.lessonIndex}"' in submit
    assert "escapeHtml(topic.tip || topic.prompt)" in submit
    assert "escapeHtml(topic.lessonTitle)" in submit


def test_achievement_shelf_uses_only_server_completed_modules() -> None:
    shelf = _function_source("trainingAchievementShelfMarkup")
    home = _function_source("renderLearningHome")

    assert "completedModules instanceof Set" in shelf
    assert "completed.has(course.code)" in shelf
    assert "Подтверждено сервером" in shelf
    assert "Локальные отметки и XP сами по себе его не выдают" in shelf
    assert "trainingAchievementShelfMarkup(courses, completed)" in home


def test_checklist_ids_are_stable_and_persisted_by_identity() -> None:
    payload = _run_module(
        INTERACTIVE,
        "training-interactive",
        r"""
        const walkthroughs = [{
          id: "lab alpha",
          title: "Stable checklist",
          frames: [
            { id: "one", title: "One", body: "First action" },
            { id: "two", title: "Two", body: "Second action" },
          ],
          checklist: [
            { id: "verify sku", text: "Verify SKU" },
            "Save result",
            { id: "verify sku", text: "Verify source" },
          ],
        }];
        const normalized = subject.normalizeInteractiveWalkthroughs(walkthroughs);
        return {
          ids: normalized[0].checklist.map((item) => item.id),
          markup: subject.trainingInteractiveMarkup("course/demo", walkthroughs),
        };
        """,
    )

    assert payload["ids"] == ["verify_sku", "lab_alpha_check_2", "verify_sku_2"]
    assert 'data-training-check="verify_sku"' in payload["markup"]
    assert 'data-training-check="lab_alpha_check_2"' in payload["markup"]
    assert 'data-training-check="verify_sku_2"' in payload["markup"]

    persist = _function_source("persistTrainingWalkthroughState")
    restore = _function_source("restoreTrainingWalkthroughState")
    assert "checkIds:" in persist
    assert 'input.dataset.trainingCheck || ""' in persist
    assert "Array.isArray(saved.checkIds)" in restore
    assert "checkIds.has(String(input.dataset.trainingCheck || \"\"))" in restore
    assert "checks[index] === true" in restore, "legacy positional state must remain readable"


def test_practice_role_uses_one_visible_catalog_without_a_second_picker() -> None:
    payload = _run_module(
        INTERACTIVE,
        "training-interactive",
        r"""
        const walkthroughs = [{
          id: "shoot",
          title: "Shoot",
          audience: ["self"],
          frames: [
            { id: "one", title: "One", body: "First action" },
            { id: "two", title: "Two", body: "Second action" },
          ],
        }, {
          id: "generate",
          title: "Generate",
          audience: ["ai"],
          frames: [
            { id: "one", title: "One", body: "First action" },
            { id: "two", title: "Two", body: "Second action" },
          ],
        }];
        return { markup: subject.trainingInteractiveMarkup("video_quality", walkthroughs) };
        """,
    )

    markup = payload["markup"]
    assert 'data-action="training-audience-select"' not in markup
    assert "data-training-audience-value" not in markup
    assert markup.count("data-training-audience-badge") == 2
    assert "data-training-audience=\"self\"" in markup
    assert "data-training-audience=\"ai\"" in markup

    audience_controller = INTERACTIVE.split(
        "export function setTrainingAudience(", 1
    )[1].split("\nexport function ", 1)[0]
    assert "walkthrough.hidden = false" in audience_controller
    assert 'setAttribute?.("aria-hidden", "false")' in audience_controller
    assert 'toggle?.("is-audience-recommended", matches)' in audience_controller
    assert 'toggle?.("is-audience-reference", !matches)' in audience_controller
    assert 'trainingMasteryRequired === "true"' in audience_controller
    assert "Обязательная лаборатория курса" in audience_controller


def test_server_completion_requires_the_configured_practice_receipts() -> None:
    migrations = sorted(
        (ROOT / "supabase/migrations").glob("*training_mastery*.sql")
    )
    if not migrations:
        pytest.skip("training mastery server migration has not been added yet")

    sql = migrations[-1].read_text(encoding="utf-8").lower()
    assert "begin;" in sql and "commit;" in sql
    assert "required_walkthrough_ids" in sql
    assert "training_walkthrough_progress" in sql
    assert "creator_complete_module" in sql
    assert "course_practice_required" in sql
    assert "and progress.completed" in sql
    assert "'version', 4" in sql
    assert "knowledge_remediation" in sql
    assert "freeze checklist identity" in sql
    assert "duplicate checklist ids" in sql
    assert "when strpos(" in sql
    assert "then coalesce(question.value ->> 'id', '')" in sql
    assert "course_practice_required:" in SUPABASE_API
    assert "training_progress_sync_required:" in SUPABASE_API

    fixture_source = CREATOR_FACTORY_TEST.lower()
    practice_fixture = fixture_source.index(
        "perform public.creator_save_training_progress"
    )
    completion_fixture = fixture_source.index(
        "perform public.creator_complete_module",
        practice_fixture,
    )
    assert practice_fixture < completion_fixture
    assert "module_row.required_walkthrough_ids" in fixture_source

    for course_code in (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    ):
        assert f"'{course_code}'" in sql
    for walkthrough_id in (
        "first_login_route",
        "eight_second_quality",
        "advertising_stop_decision",
        "substitute_article_match",
        "payout_status_route",
    ):
        assert f"'{walkthrough_id}'" in sql

    completion_function = sql.split(
        "create or replace function public.creator_complete_module", 1
    )[1].split("do $training_mastery_v4_function_contract$", 1)[0]
    practice_gate = completion_function.index("message = 'course_practice_required'")
    receipt_lookup = completion_function.index(
        "content_factory_private.begin_command"
    )
    certification_write = completion_function.index(
        "insert into content_factory.training_certifications"
    )
    assert practice_gate < receipt_lookup < certification_write
    for identity_predicate in (
        "progress.organization_id = organization_id",
        "progress.profile_id = user_id",
        "progress.module_code = course_code",
        "progress.walkthrough_id = required_walkthrough.walkthrough_id",
    ):
        assert identity_predicate in completion_function
