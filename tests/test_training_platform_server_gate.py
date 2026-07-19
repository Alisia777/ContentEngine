from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607190003_training_platform_assessment_server.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
SIMULATOR = (ROOT / "web/app/training-platform-simulators.js").read_text(encoding="utf-8")


def _public_function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(name)}"
        rf"\s*\(.*?\)\s*returns\s+jsonb(?P<header>.*?)as\s+\$\$"
        rf"(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, name
    return match.group("header").casefold(), match.group("body").casefold()


def test_migration_is_transactional_and_parses_as_postgresql() -> None:
    assert MIGRATION.exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")

    from pglast import parse_sql

    statements = parse_sql(SQL)
    assert len(statements) >= 25


def test_answer_key_table_is_private_and_public_migration_is_data_free() -> None:
    assert "content_factory_private.training_platform_answer_keys" in LOWER
    assert (
        "alter table content_factory_private.training_platform_answer_keys\n"
        "  enable row level security"
    ) in LOWER
    assert (
        "revoke all on content_factory_private.training_platform_answer_keys\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert "grant select on content_factory_private.training_platform_answer_keys" not in LOWER
    assert "SUPABASE_TRAINING_KEYS_B64" in SQL
    assert "values\n  (1, 'instagram'" not in SQL
    assert "'complete', '[\"borrowed\"]'" not in SQL


def test_attempt_receipt_is_rpc_only_append_only_and_bounded() -> None:
    table = LOWER.split(
        "create table content_factory.training_platform_assessment_attempts", 1
    )[1].split("create index training_platform_attempts_rate_limit_idx", 1)[0]
    for field in (
        "assessment_version",
        "platform_code",
        "decisions jsonb",
        "rationales jsonb",
        "correct_count",
        "critical_error_count",
        "score_percent",
        "request_hash",
        "idempotency_key",
        "completed_at",
    ):
        assert field in table
    assert "length(decisions::text) <= 4096" in table
    assert "length(rationales::text) <= 12000" in table
    assert "unique (organization_id, profile_id, idempotency_key)" in table
    assert "correct_count >= 5 and critical_error_count = 0" in table
    assert (
        "alter table content_factory.training_platform_assessment_attempts\n"
        "  enable row level security"
    ) in LOWER
    assert (
        "revoke all on content_factory.training_platform_assessment_attempts\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert "before update or delete" in LOWER
    assert "training_platform_attempt_immutable" in LOWER


def test_public_progress_rpc_blocks_all_platform_walkthrough_forgery() -> None:
    header, body = _public_function("creator_save_training_progress")
    assert "security definer" in header
    assert "set search_path = ''" in header
    for walkthrough_id in (
        "platform_publish_instagram",
        "platform_publish_youtube",
        "platform_publish_vk",
    ):
        assert walkthrough_id in body
    assert "platform_simulator_server_grading_required" in body
    assert (
        "creator_save_training_progress_before_platform_gate(p_payload)" in body
    )
    assert (
        "revoke all on function\n"
        "  content_factory_private.creator_save_training_progress_before_platform_gate(jsonb)\n"
        "  from public, anon, authenticated"
    ) in LOWER


def test_submit_rpc_requires_six_real_decisions_and_six_unique_explanations() -> None:
    header, body = _public_function("creator_submit_platform_simulator")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "constant_assessment_version constant integer := 1" in body
    assert "decision_key_count <> 6" in body
    assert "rationale_key_count <> 6" in body
    assert "platform_simulator_exact_six_steps_required" in body
    assert "jsonb_typeof(decisions_value -> expected.step_code) <> 'string'" in body
    assert "valid_platform_assessment_rationale(" in body
    assert "distinct_rationale_count <> 6" in body
    assert "platform_simulator_distinct_rationales_required" in body

    rationale_helper = LOWER.split(
        "valid_platform_assessment_rationale(", 1
    )[1].split("$$;", 1)[0]
    assert "jsonb_typeof(submitted) = 'string'" in rationale_helper
    assert "char_length(token_counts.body) between 50 and 900" in rationale_helper
    assert "word_count >= 8" in rationale_helper
    assert "meaningful_distinct_word_count >= 6" in rationale_helper
    assert "regexp_replace" in rationale_helper


def test_server_grades_privately_rate_limits_and_only_pass_marks_progress() -> None:
    _header, body = _public_function("creator_submit_platform_simulator")
    assert "content_factory_private.training_platform_answer_keys" in body
    assert "content_factory_private.begin_command" in body
    assert "content_factory_private.finish_command" in body
    assert "'profile_id', user_id" in body
    assert "pg_advisory_xact_lock" in body
    assert "attempt.completed_at > now() - interval '24 hours'" in body
    assert "last_attempt_at > now() - interval '60 seconds'" in body
    assert "recent_attempt_count >= 8" in body
    assert "platform_simulator_cooldown" in body
    assert "platform_simulator_daily_attempt_limit" in body
    assert "passed_value := correct_count_value >= 5" in body
    assert "and critical_error_count_value = 0" in body

    pass_block = body.split("if passed_value then", 1)[1].split(
        "result_value := jsonb_build_object(", 1
    )[0]
    assert "insert into content_factory.training_walkthrough_progress" in pass_block
    before_pass = body.split("if passed_value then", 1)[0]
    assert "insert into content_factory.training_walkthrough_progress" not in before_pass


def test_public_receipt_is_pass_fail_only_and_cannot_be_used_as_an_answer_oracle() -> None:
    _header, body = _public_function("creator_submit_platform_simulator")
    public_receipt = body.split("result_value := jsonb_build_object(", 1)[1].split(
        "perform content_factory_private.emit_event", 1
    )[0]
    for aggregate in (
        "'attempt_id'",
        "'assessment_version'",
        "'passed'",
    ):
        assert aggregate in public_receipt
    for secret in (
        "decisions_value",
        "rationales_value",
        "correct_option",
        "critical_options",
        "allowed_options",
        "step_code",
        "score_percent_value",
        "critical_error_count_value",
        "correct_count_value",
    ):
        assert secret not in public_receipt


def test_pre_server_client_progress_and_certification_are_invalidated() -> None:
    invalidation = LOWER.split(
        "-- existing client-authored progress", 1
    )[1].split(
        "-- preserve the original validated implementation", 1
    )[0]
    assert "delete from content_factory.training_walkthrough_progress" in invalidation
    assert "module_code = 'publishing_funnel'" in invalidation
    assert "update content_factory.training_certifications" in invalidation
    assert "set status = 'revoked'" in invalidation


def test_frontend_submits_full_attempt_and_never_uses_legacy_progress_for_platforms() -> None:
    assert 'submitPlatformSimulator: "creator_submit_platform_simulator"' in API
    assert "submitPlatformSimulator({ platformId, assessmentVersion = 1, decisions = {}, rationales = {} })" in API
    assert "onSubmitAttempt(payload)" in APP
    assert "state.api.submitPlatformSimulator" in APP
    assert "normalizeServerTrainingProgress({ items: [rawProgress] })" in APP
    assert "DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(walkthroughId)" in APP
    assert 'new Error("platform_simulator_server_grading_required")' in APP
    assert "authoritativeWalkthroughIds" in APP
    assert "state.trainingProgress.items.get(trainingProgressKey(course.code, walkthroughId))?.completed === true" in APP
    assert 'root.dataset.trainingServerComplete = "true"' in APP
    assert 'panel.dataset?.trainingServerComplete === "true"' in SIMULATOR
    assert "effectivePassed = authoritativeComplete || state.passed" in SIMULATOR
    assert "platformSimulatorAttemptPayload" in SIMULATOR
    assert "correct: true" not in SIMULATOR
    assert "critical: true" not in SIMULATOR


def test_server_completed_simulator_restores_the_visual_receipt() -> None:
    assert "syncPlatformSimulatorWalkthroughDOM" in APP
    progress = APP[
        APP.index("function applyServerTrainingProgress(") :
        APP.index("function serverTrainingProgressPayload(")
    ]
    assert "DEDICATED_PLATFORM_WALKTHROUGH_IDS.has(progress.walkthroughId)" in progress
    assert 'progress.walkthroughId.replace("platform_publish_", "")' in progress
    assert progress.index('root.dataset.trainingServerComplete = "true"') < progress.index(
        "syncPlatformSimulatorWalkthroughDOM(root"
    )
