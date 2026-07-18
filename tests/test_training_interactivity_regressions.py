from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web/app/app.js"
MODULE_PATH = ROOT / "web/app/training-interactive.js"
STYLES_PATH = ROOT / "web/app/training-interactive.css"
PRACTICE_MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202607180005_training_walkthrough_practice.sql"
)

APP = APP_PATH.read_text(encoding="utf-8")
MODULE = MODULE_PATH.read_text(encoding="utf-8")
STYLES = STYLES_PATH.read_text(encoding="utf-8")
PRACTICE_MIGRATION = PRACTICE_MIGRATION_PATH.read_text(encoding="utf-8")


def _run_javascript(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable training regressions")

    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "training-interactive.mjs").write_text(
            MODULE,
            encoding="utf-8",
        )
        (module_directory / "regression.mjs").write_text(
            "import * as training from './training-interactive.mjs';\n"
            f"const payload = (() => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "regression.mjs"],
            cwd=module_directory,
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
    next_async_function = APP.find("\nasync function ", start + 1)
    candidates = [
        position
        for position in (next_function, next_async_function)
        if position >= 0
    ]
    end = min(candidates) if candidates else len(APP)
    return APP[start:end]


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
        assert depth == 0, "unterminated training media query"
        blocks.append(css[match.start() : cursor])
    return blocks


def test_training_has_modes_timeline_decision_practice_and_explicit_completion() -> None:
    for export in (
        "setTrainingWalkthroughMode",
        "evaluateTrainingPractice",
        "syncTrainingWalkthroughStatus",
    ):
        assert f"export function {export}(" in MODULE

    payload = _run_javascript(
        r"""
        const walkthrough = [{
          id: "publish_rehearsal",
          title: "Publish safely",
          summary: "A guided practice scenario",
          mission: "Prepare the approved post",
          deliverable: "A checked publication draft",
          frames: [
            { id: "prepare", title: "Prepare", body: "Open the assignment" },
            { id: "check", title: "Check", body: "Compare all fields" },
            { id: "publish", title: "Publish", body: "Save the final URL" },
          ],
          checklist: ["Product matches", "Link matches"],
          practice: {
            prompt: "Which action is safe? <script>unsafe()</script>",
            options: [
              { id: "guess", label: "Publish before approval", correct: false, feedback: "Stop and check" },
              { id: "verify", label: "Verify the assignment first", correct: true, feedback: "Correct route" },
            ],
            success_message: "Scenario complete",
          },
        }];
        const markup = training.trainingInteractiveMarkup("publishing_funnel", walkthrough);
        return { markup };
        """
    )

    markup = payload["markup"]
    assert 'data-action="training-mode-select"' in markup
    assert 'data-training-mode-value="watch"' in markup
    assert 'data-training-mode-value="practice"' in markup
    assert markup.count('aria-pressed="') >= 2
    assert 'data-training-timeline' in markup
    assert markup.count('data-action="training-walkthrough-jump"') == 3
    assert 'data-training-step-target="0"' in markup
    assert 'data-training-step-target="2"' in markup
    assert 'data-training-practice' in markup
    assert 'role="radiogroup"' in markup
    assert markup.count('data-training-practice-option') == 2
    assert 'data-action="training-practice-check"' not in markup
    radiogroup = re.search(r'<div class="training-walkthrough__practice-options"[^>]*>', markup)
    assert radiogroup
    assert 'role="radiogroup"' in radiogroup.group(0)
    assert 'aria-labelledby="training-practice-' in radiogroup.group(0)
    assert 'aria-describedby="training-practice-' in radiogroup.group(0)
    assert 'data-training-practice-feedback' in markup
    assert 'role="status"' in markup
    assert 'aria-live="polite"' in markup
    assert 'data-training-status' in markup
    assert 'data-training-complete="false"' in markup
    assert "Prepare the approved post" in markup
    assert "A checked publication draft" in markup
    assert "<script>unsafe()</script>" not in markup
    assert "&lt;script&gt;unsafe()&lt;/script&gt;" in markup


def test_audience_filter_is_persistent_accessible_and_separate_from_certification() -> None:
    for export in ("setTrainingAudience", "trainingAudienceStorageKey"):
        assert f"export function {export}(" in MODULE

    payload = _run_javascript(
        r"""
        const makeWalkthrough = (id, audience) => ({
          id,
          title: id,
          audience,
          frames: [
            { id: "one", title: "One", body: "First" },
            { id: "two", title: "Two", body: "Second" },
          ],
          practice: {
            prompt: "Pick one",
            options: [
              { id: "wrong", label: "Wrong", correct: false, feedback: "No" },
              { id: "right", label: "Right", correct: true, feedback: "Yes" },
            ],
          },
        });
        const normalized = training.normalizeInteractiveWalkthroughs([
          makeWalkthrough("camera", ["self"]),
          makeWalkthrough("generator", ["ai"]),
          makeWalkthrough("posting", ["publish"]),
          makeWalkthrough("shared", ["self", "ai", "publish"]),
          {
            ...makeWalkthrough("invalid_practice", ["self"]),
            practice: {
              prompt: "Ambiguous",
              options: [
                { id: "one", label: "One", correct: true },
                { id: "two", label: "Two", correct: true },
              ],
            },
          },
        ]);
        const markup = training.trainingInteractiveMarkup("factory_basics", normalized);
        const legacyAudiences = training.normalizeInteractiveWalkthroughs([
          makeWalkthrough("legacy_creator", "creator"),
          makeWalkthrough("legacy_publisher", "publisher"),
          makeWalkthrough("legacy_all", "all"),
        ]).map((item) => item.audience);
        return {
          markup,
          audiences: normalized.map((item) => item.audience),
          legacyAudiences,
          practiceFlags: normalized.map((item) => Boolean(item.practice)),
          key: training.trainingAudienceStorageKey("user 1", "factory/basics"),
          missingKey: training.trainingAudienceStorageKey("", "factory_basics"),
        };
        """
    )

    assert payload["audiences"] == [
        ["self"],
        ["ai"],
        ["publish"],
        ["self", "ai", "publish"],
        ["self"],
    ]
    assert payload["practiceFlags"] == [True, True, True, True, False]
    assert payload["legacyAudiences"] == [
        ["self"],
        ["publish"],
        ["self", "ai", "publish"],
    ]
    assert payload["key"] == "contentengine.training-audience.v1:user%201:factory%2Fbasics"
    assert payload["missingKey"] is None

    markup = payload["markup"]
    for audience in ("all", "self", "ai", "publish"):
        assert f'data-training-audience-value="{audience}"' in markup
    assert markup.count('data-action="training-audience-select"') == 4
    assert markup.count('data-training-audience="') == 5
    assert 'data-training-audience-result' in markup
    assert "Снимаю сам" in markup
    assert "Генерирую с ИИ" in markup
    assert "Публикую" in markup
    assert "Показать всё" in markup
    assert "сертификац" in markup.casefold() or "обязательн" in markup.casefold()

    audience_controller = MODULE[
        MODULE.index("export function setTrainingAudience(") :
        MODULE.index("export function", MODULE.index("export function setTrainingAudience(") + 1)
    ]
    for forbidden in (
        "complete-course",
        "course-ack",
        "training_certification",
        "training_certifications",
        "completedModules",
    ):
        assert forbidden not in audience_controller

    render_course = _function_source("renderCourse")
    persist_audience = _function_source("persistTrainingAudience")
    restore_audience = _function_source("restoreTrainingAudience")
    click_handler = _function_source("handleClick")
    assert "restoreTrainingAudience(course.code)" in render_course
    assert "window.localStorage.setItem" in persist_audience
    assert "window.localStorage.getItem" in restore_audience
    assert "setTrainingAudience(courseRoot, saved)" in restore_audience
    assert "training-audience-select" in click_handler
    assert "persistTrainingAudience(" in click_handler
    assert "completeModule(" not in persist_audience
    assert "completeModule(" not in restore_audience


def test_practice_catalog_has_audience_metadata_and_one_unambiguous_answer() -> None:
    lowered = PRACTICE_MIGRATION.lower()
    assert "audience," in lowered
    assert "audience_label," in lowered
    assert "walkthrough_count <> 8" in lowered
    assert "malformed_walkthroughs" in lowered
    assert "jsonb_typeof(walkthrough -> 'practice')" in lowered
    assert "jsonb_array_length" in lowered
    assert "where option ->> 'correct' = 'true'" in lowered
    assert ") <> 1" in lowered
    assert (
        "raise exception 'training walkthrough practice contains % malformed walkthroughs'"
        in lowered
    )

    assert "insert into content_factory.training_questions" not in lowered
    assert "content_factory_private" not in lowered
    assert "training_answer_keys" not in lowered
    assert "training_certifications" not in lowered
    assert "creator_complete_module" not in lowered


def test_mode_decision_and_completion_controllers_form_one_coherent_state_machine() -> None:
    payload = _run_javascript(
        r"""
        const attrs = () => ({
          attributes: {},
          setAttribute(name, value) { this.attributes[name] = String(value); },
        });
        const watchPanel = { ...attrs(), dataset: { trainingModePanel: "watch" }, hidden: false };
        const practicePanel = {
          ...attrs(),
          dataset: {
            trainingModePanel: "practice",
            trainingSuccessMessage: "Safe answer accepted",
            trainingPracticeComplete: "false",
          },
          hidden: true,
        };
        const watchButton = { ...attrs(), dataset: { trainingModeValue: "watch" } };
        const practiceButton = { ...attrs(), dataset: { trainingModeValue: "practice" } };
        const wrong = {
          ...attrs(),
          value: "wrong",
          checked: false,
          dataset: { trainingPracticeCorrect: "false", trainingFeedback: "Try again" },
        };
        const safe = {
          ...attrs(),
          value: "safe",
          checked: false,
          dataset: { trainingPracticeCorrect: "true", trainingFeedback: "Good" },
        };
        const feedback = { textContent: "", dataset: {} };
        const status = { textContent: "", dataset: {} };
        const checks = [{ checked: true }, { checked: true }];
        practicePanel.querySelectorAll = (selector) => selector === "[data-training-practice-option]" ? [wrong, safe] : [];
        practicePanel.querySelector = (selector) => selector === "[data-training-practice-feedback]" ? feedback : null;
        const walkthrough = {
          dataset: {
            trainingMode: "watch",
            trainingStep: "2",
            trainingStepCount: "3",
            trainingPracticeRequired: "true",
            trainingPracticeComplete: "false",
            trainingComplete: "false",
          },
          classList: { toggle(_name, enabled) { this.enabled = enabled; } },
          matches(selector) { return selector === "[data-training-walkthrough]"; },
          closest() { return null; },
          querySelectorAll(selector) {
            if (selector === "[data-training-mode-panel]") return [watchPanel, practicePanel];
            if (selector === '[data-action="training-mode-select"]') return [watchButton, practiceButton];
            if (selector === "[data-training-check]") return checks;
            return [];
          },
          querySelector(selector) {
            if (selector === "[data-training-practice]") return practicePanel;
            if (selector === "[data-training-status]") return status;
            return null;
          },
        };

        const mode = training.setTrainingWalkthroughMode(walkthrough, "practice");
        const result = training.evaluateTrainingPractice(walkthrough, "safe");
        const completion = training.syncTrainingWalkthroughStatus(walkthrough);
        return {
          mode,
          result,
          completion,
          watchHidden: watchPanel.hidden,
          practiceHidden: practicePanel.hidden,
          watchPressed: watchButton.attributes["aria-pressed"],
          practicePressed: practiceButton.attributes["aria-pressed"],
          feedback: feedback.textContent,
          feedbackStatus: feedback.dataset.trainingFeedbackStatus,
          statusValue: status.dataset.trainingStatusValue,
          rootComplete: walkthrough.dataset.trainingComplete,
        };
        """
    )

    assert payload == {
        "mode": "practice",
        "result": {"answered": True, "passed": True, "selectedId": "safe"},
        "completion": {
            "complete": True,
            "stepComplete": True,
            "checksComplete": True,
            "practiceComplete": True,
        },
        "watchHidden": True,
        "practiceHidden": False,
        "watchPressed": "false",
        "practicePressed": "true",
        "feedback": "Safe answer accepted",
        "feedbackStatus": "success",
        "statusValue": "complete",
        "rootComplete": "true",
    }


def test_every_training_interaction_reuses_the_persistent_progress_path() -> None:
    render_course = _function_source("renderCourse")
    persist = _function_source("persistTrainingWalkthroughState")
    restore = _function_source("restoreTrainingWalkthroughState")
    server_payload = _function_source("serverTrainingProgressPayload")
    click_handler = _function_source("handleClick")
    change_handler = _function_source("handleChange")

    assert "restoreTrainingWalkthroughState(course.code)" in render_course
    assert "restoreServerTrainingWalkthroughState(course.code)" in render_course
    assert render_course.index("restoreTrainingWalkthroughState(course.code)") < render_course.index(
        "restoreServerTrainingWalkthroughState(course.code)"
    )

    assert "window.sessionStorage.setItem" in persist
    assert "window.localStorage.setItem" in persist
    assert persist.count("try {") >= 2
    assert persist.count("} catch {") >= 2
    assert "scheduleServerTrainingWalkthroughProgress(root)" in persist
    assert "practiceOption:" in persist
    assert "mode:" in persist
    assert "window.sessionStorage.getItem" in restore
    assert "window.localStorage.getItem" in restore
    assert "setTrainingWalkthroughStep" in restore
    assert "evaluateTrainingPractice" in restore
    assert "setTrainingWalkthroughMode" in restore
    assert "syncTrainingWalkthroughStatus" in restore
    assert "completed_frame_ids" in server_payload
    assert "completed" in server_payload
    assert "position_seconds" in server_payload

    for action in (
        "training-mode-select",
        "training-walkthrough-jump",
        "training-walkthrough-previous",
        "training-walkthrough-next",
        "training-walkthrough-reset",
    ):
        assert action in click_handler
    assert "training-practice-check" not in click_handler
    assert "setTrainingWalkthroughStepAndPersist(" in click_handler
    assert click_handler.count("persistTrainingWalkthroughState(") >= 1
    assert "[data-training-check]" in change_handler
    assert "[data-training-practice-option]" in change_handler
    assert "evaluateTrainingPractice(root, event.target.value)" in change_handler
    assert "persistTrainingWalkthroughState(" in change_handler


def test_server_completed_progress_restores_all_interactive_completion_state() -> None:
    apply_server = _function_source("applyServerTrainingProgress")

    assert "progress.completed === true" in apply_server
    assert "trainingPracticeComplete" in apply_server
    assert "[data-training-check]" in apply_server
    assert ".checked = true" in apply_server
    assert "syncTrainingWalkthroughStatus(root)" in apply_server


def test_plain_language_exam_presentation_never_changes_server_answer_values() -> None:
    presentation = APP[
        APP.index("const FINAL_EXAM_PRESENTATION") :
        APP.index("const REAL_GEN4_MODE")
    ]
    expected_codes = {
        "exam_sku_mismatch",
        "exam_provider_wrong_pack",
        "exam_qa_requirements",
        "exam_missing_destination",
        "exam_publication_evidence",
        "exam_metrics_source",
        "exam_secret_request",
        "exam_real_spend_disabled",
        "exam_wb_alias_history",
        "exam_payout_separation",
        "exam_platform_claims",
        "exam_idempotent_retry",
    }
    presented_codes = set(
        re.findall(r"^\s{2}(exam_[a-z0-9_]+): Object\.freeze\(", presentation, re.MULTILINE)
    )
    assert presented_codes == expected_codes
    assert "correct:" not in presentation
    assert "correct_answer" not in presentation

    final_questions = _function_source("finalExamQuestions")
    question_markup = _function_source("questionMarkup")
    submit_exam = APP[
        APP.index("async function submitExam(") :
        APP.index("async function submitGenerationBatch(")
    ]
    assert "const presentation = FINAL_EXAM_PRESENTATION[code]" in final_questions
    assert "value: option.value" in final_questions
    assert "presentation?.options?.[option.value] || option.label" in final_questions
    assert 'value="${escapeHtml(option.value)}"' in question_markup
    assert "selected.map((input) => input.value)" in submit_exam
    assert "state.api.submitExam(answers)" in submit_exam


def test_plain_language_training_copy_has_no_public_answer_key_migration_dependency() -> None:
    removed_migration = (
        ROOT
        / "supabase/migrations/202607180006_plain_language_training_assessment.sql"
    )
    assert not removed_migration.exists()
    assert "202607180006_plain_language_training_assessment" not in APP

    course_presentation = APP[
        APP.index("const COURSE_KNOWLEDGE_PRESENTATION") :
        APP.index("const FINAL_EXAM_PRESENTATION")
    ]
    assert set(
        re.findall(r"^\s{2}([a-z_]+): Object\.freeze\(", course_presentation, re.MULTILINE)
    ) == {
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    }
    learning_courses = _function_source("learningCourses")
    assert "COURSE_KNOWLEDGE_PRESENTATION[module.code]?.audienceLabel" in learning_courses
    assert "COURSE_KNOWLEDGE_PRESENTATION[module.code]?.roleHint" in learning_courses


def test_learning_information_architecture_keeps_the_mandatory_path_first() -> None:
    course_page = _function_source("renderCourse")
    learning_home = _function_source("renderLearningHome")

    roadmap = course_page.index('class="card course-roadmap"')
    lessons = course_page.index('class="lesson-stack"')
    walkthrough = course_page.index(
        "${trainingInteractiveMarkup(course.code, course.interactiveWalkthroughs)}"
    )
    knowledge_check = course_page.index("${courseKnowledgeCheckMarkup(course, checkPassed)}")
    assert roadmap < walkthrough
    assert lessons < walkthrough
    assert walkthrough < knowledge_check

    mandatory_courses = learning_home.index('class="course-grid"')
    optional_shift = learning_home.index('class="card first-shift-invite"')
    optional_account_launch = learning_home.index(
        'class="card first-shift-invite account-launch-invite"'
    )
    assert mandatory_courses < optional_shift
    assert mandatory_courses < optional_account_launch


def test_walkthrough_keyboard_navigation_is_scoped_and_uses_the_same_save_path() -> None:
    key_handler = _function_source("handleKeyDown")
    click_handler = _function_source("handleClick")

    assert "[data-training-timeline]" in key_handler
    assert "trainingWalkthroughRoot(trainingTimelineControl)" in key_handler
    assert "event.target.closest" in key_handler
    assert '"ArrowLeft"' in key_handler
    assert '"ArrowRight"' in key_handler
    assert "event.preventDefault()" in key_handler
    assert "setTrainingWalkthroughStepAndPersist" in key_handler
    assert 'querySelector("[data-training-practice-option]")?.focus' in click_handler

    payload = _run_javascript(
        r"""
        const markup = training.trainingInteractiveMarkup("video_quality", [{
          id: "camera_steps",
          title: "Camera rehearsal",
          frames: [
            { id: "one", title: "One", body: "First action" },
            { id: "two", title: "Two", body: "Second action" },
          ],
          checklist: ["Done"],
          practice: {
            prompt: "Choose",
            options: [
              { id: "a", label: "A", correct: false, feedback: "Try again" },
              { id: "b", label: "B", correct: true, feedback: "Correct" },
            ],
          },
        }]);
        return { markup };
        """
    )
    markup = payload["markup"]
    assert 'aria-labelledby="training-walkthrough-' in markup
    assert 'aria-live="polite" aria-atomic="true"' in markup
    assert 'role="progressbar"' in markup
    assert 'aria-valuemin="0"' in markup
    assert 'aria-valuemax="100"' in markup
    assert 'aria-valuenow="' in markup
    assert 'type="button"' in markup
    assert 'type="radio"' in markup


def test_training_failure_paths_do_not_render_raw_exception_details() -> None:
    render_course = _function_source("renderCourse")
    restore_server = APP[
        APP.index("async function restoreServerTrainingWalkthroughState(") :
        APP.index("function applyServerTrainingProgress(")
    ]
    drain_queue = APP[
        APP.index("async function drainTrainingProgressSaveQueue(") :
        APP.index("function scheduleServerTrainingWalkthroughProgress(")
    ]

    for source in (render_course, MODULE):
        assert "${error" not in source
        assert "${String(error" not in source
        assert "error.message" not in source
        assert "error.stack" not in source

    assert "console.warn(" in restore_server
    assert "console.warn(" in drain_queue
    assert "innerHTML" not in MODULE
    assert "outerHTML" not in MODULE
    assert "eval(" not in MODULE
    assert "new Function(" not in MODULE


def test_training_controls_remain_touch_ready_and_single_column_on_small_screens() -> None:
    assert ":focus-visible" in STYLES
    assert "min-height: 44px" in STYLES
    assert "@media (prefers-reduced-motion: reduce)" in STYLES
    assert "@media (forced-colors: active)" in STYLES

    mobile_blocks = [
        block
        for block in _media_blocks(STYLES)
        if "max-width" in block and "420px" in block
    ]
    assert mobile_blocks, "training needs an explicit narrow-phone breakpoint"
    for selector in (
        ".training-interactive__grid",
        ".training-walkthrough__stage",
        ".training-walkthrough__actions",
        ".training-walkthrough__mode-switcher",
        ".training-walkthrough__timeline",
    ):
        assert selector in STYLES, f"missing interactive control styling for {selector}"
    assert re.search(
        r"\.training-walkthrough__actions\s*\{[^}]*grid-template-columns\s*:\s*1fr",
        STYLES,
        flags=re.DOTALL,
    )
    assert "overflow-x: auto" in STYLES
    assert "scroll-snap-type: x proximity" in STYLES
    assert "min-height: 52px" in STYLES
    assert "position: fixed" not in STYLES
    assert "min-width: 100vw" not in STYLES
    assert "width: 100vw" not in STYLES
