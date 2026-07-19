from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607190004_training_result_oracle_hardening.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    start = APP.index(f"function {name}(")
    next_sync = APP.find("\nfunction ", start + 1)
    next_async = APP.find("\nasync function ", start + 1)
    ends = [value for value in (next_sync, next_async) if value >= 0]
    return APP[start : min(ends) if ends else len(APP)]


def _async_function_source(name: str) -> str:
    start = APP.index(f"async function {name}(")
    next_sync = APP.find("\nfunction ", start + 1)
    next_async = APP.find("\nasync function ", start + 1)
    ends = [value for value in (next_sync, next_async) if value >= 0]
    return APP[start : min(ends) if ends else len(APP)]


def test_historical_receipts_are_sanitized_without_breaking_replay() -> None:
    assert "update content_factory.command_receipts receipt" in MIGRATION
    for command in (
        "creator_submit_course_check",
        "creator_submit_platform_simulator",
        "creator_submit_exam",
    ):
        assert f"'{command}'" in MIGRATION
    for oracle_field in (
        "- 'correct_count'",
        "- 'critical_error_count'",
        "- 'score_percent'",
        "- 'review_topics'",
    ):
        assert oracle_field in MIGRATION
    assert "delete from content_factory.command_receipts" not in MIGRATION.lower()


def test_public_final_exam_wrapper_never_returns_exact_grading_data() -> None:
    assert "creator_submit_exam_pre_result_sanitize" in MIGRATION
    assert "revoke all on function" in MIGRATION
    assert "from public, anon, authenticated" in MIGRATION
    public_wrapper = MIGRATION[
        MIGRATION.index("create or replace function public.creator_submit_exam(") :
        MIGRATION.index("comment on function public.creator_submit_exam")
    ]
    for oracle_field in (
        "- 'correct_count'",
        "- 'critical_error_count'",
        "- 'score_percent'",
        "- 'review_topics'",
        "- 'topics'",
    ):
        assert oracle_field in public_wrapper


def test_browser_failure_views_do_not_render_score_or_exact_remediation() -> None:
    course_submit = _async_function_source("submitCourseKnowledgeCheck")
    exam_submit = _async_function_source("submitExam")
    exam_result = _function_source("examResultMarkup")

    assert "source.correct_count" not in course_submit
    assert "source.review_topics" not in course_submit
    assert "score:" not in course_submit.split('track("course_check_submitted"', 1)[1]
    assert "source.correct_count" not in exam_submit
    assert "source.score_percent" not in exam_submit
    assert "score:" not in exam_submit.split('track("exam_submitted"', 1)[1]
    assert "Точный балл и правильные ответы не раскрываются" in exam_result
    assert "result.correctCount" not in exam_result
    assert "result.topics" not in exam_result
    assert "if (!state.examResult.passed)" in exam_submit
    assert "Экзамен не зачтён. Точный балл скрыт" in exam_submit
    assert exam_submit.index("if (!state.examResult.passed)") < exam_submit.index(
        "else if (hasWorkspaceAccess())"
    )
