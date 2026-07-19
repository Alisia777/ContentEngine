from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202607190002_training_assessment_v5.sql"
)
APP_PATH = ROOT / "web/app/app.js"
API_PATH = ROOT / "web/app/supabase-api.js"

SQL = MIGRATION_PATH.read_text(encoding="utf-8")
APP = APP_PATH.read_text(encoding="utf-8")
API = API_PATH.read_text(encoding="utf-8")


def _catalog(name: str) -> list[dict]:
    match = re.search(
        rf"\${re.escape(name)}\$\s*(\[.*?\])\s*\${re.escape(name)}\$::jsonb",
        SQL,
        flags=re.DOTALL,
    )
    assert match, f"missing JSON catalog {name}"
    return json.loads(match.group(1))


COURSES = {
    "factory_basics": _catalog("factory_questions"),
    "video_quality": _catalog("video_questions"),
    "publishing_funnel": _catalog("publishing_questions"),
    "security_wb": _catalog("security_questions"),
}


def test_every_course_uses_six_long_work_scenarios_with_plausible_choices() -> None:
    assert set(COURSES) == {
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    }

    for module_code, questions in COURSES.items():
        assert len(questions) == 6
        assert sum(q["question_type"] == "multi_select" for q in questions) >= 3
        for question in questions:
            assert question["id"].startswith(f"course_check_{module_code}_")
            assert len(question["prompt"]) >= 115
            assert question["requires_rationale"] is True
            assert len(question["rationale_prompt"]) >= 40
            assert len(question["options"]) >= 4
            assert len({option["value"] for option in question["options"]}) == len(
                question["options"]
            )
            assert "correct_answers" not in question
            assert "critical_answers" not in question
            assert "explanation" not in question


def test_scenarios_cover_real_work_risks_without_publishing_the_key() -> None:
    option_values = {
        option["value"]
        for questions in COURSES.values()
        for question in questions
        for option in question["options"]
    }
    scenario_text = " ".join(
        " ".join(
            (
                question["prompt"],
                question["rationale_prompt"],
                *(option["label"] for option in question["options"]),
            )
        ).casefold()
        for questions in COURSES.values()
        for question in questions
    )

    for required_value in (
        "shared_password",
        "repeat_paid",
        "use_wrong_variant",
        "borrow_audio",
        "buy_engagement",
        "hide_signs",
        "similar_is_enough",
        "manual_paid",
        "send_code",
    ):
        assert required_value in option_values

    for risk in ("чуж", "прав", "реклам", "артикул", "код"):
        assert risk in scenario_text
    assert '"correct_answers":' not in SQL
    assert '"critical_answers":' not in SQL
    assert '"explanation":' not in SQL
    assert "SUPABASE_TRAINING_KEYS_B64" in SQL


def test_server_not_browser_owns_answers_reasoning_and_critical_failure() -> None:
    assert "add column if not exists critical_answers jsonb" in SQL
    assert "add column if not exists rationales jsonb" in SQL
    assert "content_factory_private.answer_hits_any(" in SQL
    assert "critical_error_count = 0" in SQL
    assert "reasoning_count = total_count" in SQL
    assert "distinct_reasoning_count = total_count" in SQL
    assert "valid_training_rationale(" in SQL
    assert "jsonb_typeof(submitted) = 'string'" in SQL
    assert "char_length(normalized.body) between 40 and 900" in SQL
    assert "token_counts.word_count >= 7" in SQL
    assert "token_counts.meaningful_distinct_word_count >= 5" in SQL
    assert "token.value ~ '[[:alpha:]]'" in SQL
    assert "token.value ~ '[аеёиоуыэюяaeiouy]'" in SQL
    assert "'rationales', rationales" in SQL
    public_result = SQL[
        SQL.index("result := jsonb_build_object(") : SQL.index(
            "perform content_factory_private.emit_event",
            SQL.index("result := jsonb_build_object("),
        )
    ]
    for oracle_field in (
        "'correct_count'",
        "'critical_error_count'",
        "'score_percent'",
        "'review_topics'",
        "'reasoning_count'",
    ):
        assert oracle_field not in public_result

    assert "correct_answers" not in APP
    assert "critical_answers" not in APP


def test_public_options_are_deterministically_mixed_and_not_marked_required() -> None:
    assert SQL.count("jsonb_agg(option.item order by md5(") >= 2
    assert "(expanded.item ->> 'id') || ':' || (option.item ->> 'value')" in SQL
    assert "(question.item ->> 'id') || ':' || (option.item ->> 'value')" in SQL
    course_markup = APP[
        APP.index("function courseKnowledgeCheckMarkup(") :
        APP.index("function lessonVisualMarkup(")
    ]
    assert 'optionIndex === 0 ? "required"' not in course_markup
    assert 'name="${escapeHtml(inputName)}" value="${escapeHtml(option.value)}" />' in course_markup


def test_source_option_order_is_key_independent_and_has_no_single_pattern() -> None:
    source_permutations: list[tuple[int, ...]] = []

    for questions in COURSES.values():
        for question in questions:
            values = [option["value"] for option in question["options"]]
            expected = sorted(
                values,
                key=lambda value: hashlib.md5(
                    f"{question['id']}:{value}".encode("utf-8")
                ).hexdigest(),
            )
            assert values == expected

            lexical_rank = {
                value: index for index, value in enumerate(sorted(values))
            }
            source_permutations.append(
                tuple(lexical_rank[value] for value in values)
            )

    assert len(source_permutations) == 24
    assert len(set(source_permutations)) >= 18
    assert {permutation[0] for permutation in source_permutations} == {
        0,
        1,
        2,
        3,
        4,
    }


def test_server_rate_limits_attempts_and_returns_only_coarse_failure_feedback() -> None:
    assert "attempt.completed_at > now() - interval '24 hours'" in SQL
    assert "last_attempt_at > now() - interval '60 seconds'" in SQL
    assert "recent_attempt_count >= 8" in SQL
    assert "message = 'course_check_cooldown'" in SQL
    assert "message = 'course_check_daily_attempt_limit'" in SQL

    grading_block = SQL[SQL.index("passed :=") : SQL.index("insert into content_factory.training_attempts")]
    assert "review_topics := '[]'::jsonb" in grading_block
    assert "question_code" not in grading_block
    assert "Попытка остановлена критическим решением" not in grading_block
    assert "Попытка не зачтена" in grading_block


def test_browser_requires_exact_multi_select_and_written_reasoning() -> None:
    assert '.slice(0, 8)' in APP
    assert 'question.type === "multi_select"' in APP
    assert 'type="${isMulti ? "checkbox" : "radio"}"' in APP
    assert 'minlength="40"' in APP
    assert "rationale.length < 40" in APP
    assert "selected.map((input) => input.value)" in APP
    assert "submitCourseCheck(courseCode, answers, rationales)" in APP
    assert "правильные ответы и точный балл не раскрываются" in APP
    assert "meaningfulWords.size < 5" in APP
    assert "submitCourseCheck(moduleCode, answers, rationales = {})" in API
    assert "rationales," in API


def test_rationale_requires_risk_check_and_action_on_client_and_server() -> None:
    server_validator = SQL[
        SQL.index(
            "create or replace function content_factory_private.valid_training_rationale("
        ) : SQL.index(
            "create or replace function content_factory_private.answer_hits_any("
        )
    ]
    assert "and normalized.body ~" in server_validator
    assert "риск[[:space:]]*:.+" in server_validator
    assert "(проверка|доказательство)[[:space:]]*:.+" in server_validator
    assert "(действие|следующий шаг)[[:space:]]*:." in server_validator

    browser_submit = APP[
        APP.index("async function submitCourseKnowledgeCheck(") : APP.index(
            "async function submitExam("
        )
    ]
    assert "const structuredRationale =" in browser_submit
    assert "/риск\\s*:.+(проверка|доказательство)\\s*:.+" in browser_submit
    assert "(действие|следующий шаг)\\s*:/iu.test(rationale)" in browser_submit
    assert "|| !structuredRationale" in browser_submit

    check_markup = APP[
        APP.index("function courseKnowledgeCheckMarkup(") : APP.index(
            "function lessonVisualMarkup("
        )
    ]
    assert 'placeholder="Риск: … Проверка: … Действие: …"' in check_markup
    assert "три части «Риск / Проверка / Действие»" in check_markup


def test_course_assessment_draft_is_scoped_persisted_restored_and_cleared() -> None:
    draft_helpers = APP[
        APP.index("function courseAssessmentDraftKey(") : APP.index(
            "function trainingWalkthroughRoot("
        )
    ]
    assert "userId = state.user?.id" in draft_helpers
    assert "safeUser && safeCourse" in draft_helpers
    assert "contentengine.course-assessment-draft.v1:${safeUser}:${safeCourse}" in draft_helpers
    assert 'form.querySelectorAll("[data-check-question]")' in draft_helpers
    assert 'form.querySelectorAll(".knowledge-rationale textarea")' in draft_helpers
    assert ".slice(0, 8)" in draft_helpers
    assert ".slice(0, 900)" in draft_helpers
    assert "window.localStorage.setItem(key, JSON.stringify({" in draft_helpers
    for field in ("version: 1", "courseCode,", "updatedAt: Date.now()", "answers,", "rationales,"):
        assert field in draft_helpers

    assert "window.localStorage.getItem(key)" in draft_helpers
    assert "draft.version !== 1" in draft_helpers
    assert "draft.courseCode !== courseCode" in draft_helpers
    assert "7 * 24 * 60 * 60 * 1000" in draft_helpers
    assert "input.checked = selected.has" in draft_helpers
    assert "textarea.value = String(value || \"\").slice(0, 900)" in draft_helpers
    assert "counter.textContent = String(textarea.value.length)" in draft_helpers
    assert "window.localStorage.removeItem(key)" in draft_helpers

    course_render = APP[
        APP.index("function renderCourse(") : APP.index(
            "function courseAssessmentDraftKey("
        )
    ]
    assert "if (checkPassed) clearCourseAssessmentDraft(course.code)" in course_render
    assert "else restoreCourseAssessmentDraft(course.code)" in course_render

    form_activity = APP[
        APP.index("function handleFormActivity(") : APP.index(
            "function clearWorkspaceDropTargets("
        )
    ]
    assert 'event.target.closest?.("#course-check-form")' in form_activity
    assert "persistCourseAssessmentDraft(courseAssessmentForm)" in form_activity

    course_submit = APP[
        APP.index("async function submitCourseKnowledgeCheck(") : APP.index(
            "async function submitExam("
        )
    ]
    assert "if (passed) clearCourseAssessmentDraft(courseCode)" in course_submit
    assert "else persistCourseAssessmentDraft(form)" in course_submit


def test_platform_labs_are_part_of_authoritative_publishing_mastery() -> None:
    platform_catalog = _catalog("platform_walkthroughs")
    expected_ids = {
        "platform_publish_instagram",
        "platform_publish_youtube",
        "platform_publish_vk",
    }
    assert {item["id"] for item in platform_catalog} == expected_ids
    for walkthrough in platform_catalog:
        assert walkthrough["duration_seconds"] == 300
        assert len(walkthrough["frames"]) == 6
        assert len(walkthrough["transcript"]) == 6
        assert any("50" in item for item in walkthrough["checklist"])
        assert any("сервер" in item.casefold() for item in walkthrough["checklist"])

    for walkthrough_id in expected_ids:
        assert f"union all select '{walkthrough_id}'" in SQL
        assert f'"{walkthrough_id}",' in APP


def test_v5_invalidates_old_shallow_attempts_for_new_course_completion() -> None:
    # Existing shallow certifications are explicitly revoked so the UI exposes
    # the new course instead of deadlocking behind a stale passed badge.
    assert "add column if not exists assessment_version integer" in SQL
    assert "assessment_version between 1 and 100" in SQL
    assert "declared_assessment_version <> 5" in SQL
    assert "assessment_version," in SQL
    assert "attempt.assessment_version <> 5" in SQL
    assert "set status = 'invalidated'" in SQL
    assert "status = 'revoked'" in SQL
    assert "'final_exam'" not in SQL[
        SQL.index("update content_factory.training_certifications certification") :
        SQL.index("create or replace function content_factory_private.valid_training_rationale")
    ]
    assert "jsonb_array_length(catalog.questions) <> 6" in SQL
    assert "jsonb_array_length(module.content #> '{knowledge_check,questions}') <> 6" in SQL
    assert "jsonb_array_length(module.content #> '{knowledge_check,questions}')" in (
        ROOT / "supabase/migrations/202607180007_training_mastery_v4.sql"
    ).read_text(encoding="utf-8")


def test_bootstrap_cannot_reveal_failed_course_score_or_topics() -> None:
    assert "creator_bootstrap_pre_assessment_v5_sanitize" in SQL
    rename = (
        "alter function public.creator_bootstrap(jsonb)\n"
        "  rename to creator_bootstrap_pre_assessment_v5_sanitize;"
    )
    move = (
        "alter function public.creator_bootstrap_pre_assessment_v5_sanitize(jsonb)\n"
        "  set schema content_factory_private;"
    )
    assert rename in SQL
    assert move in SQL
    assert SQL.index(rename) < SQL.index(move)
    sanitizer = SQL[
        SQL.index("create or replace function public.creator_bootstrap(") :
        SQL.index("-- The server progress RPC accepts only walkthroughs")
    ]
    assert "{learning,course_checks}" in sanitizer
    assert "{training,course_checks}" in sanitizer
    for oracle_field in (
        "- 'attempt_id'",
        "- 'correct_count'",
        "- 'critical_error_count'",
        "- 'score_percent'",
        "- 'review_topics'",
    ):
        assert sanitizer.count(oracle_field) == 2
