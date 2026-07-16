from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607140006_server_course_knowledge_gate.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
PGTAP_DIR = ROOT / "supabase/tests"
VISUAL_MIGRATION = (
    ROOT
    / "supabase/migrations/202607140005_training_visual_playbook.sql"
)
VISUAL_SQL = VISUAL_MIGRATION.read_text(encoding="utf-8")
VISUAL_LOWER = VISUAL_SQL.casefold()
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
BASE_RPC_SQL = (
    ROOT / "supabase/migrations/202607130004_creator_rpcs.sql"
).read_text(encoding="utf-8")


def _function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(name)}\s*"
        rf"\(.*?\)\s*returns\s+jsonb(?P<header>.*?)as\s+\$\$"
        rf"(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, name
    return match.group("header").casefold(), match.group("body").casefold()


def test_forward_migration_is_separate_and_ordered_after_visual_catalog() -> None:
    assert MIGRATION.exists()
    assert (
        ROOT
        / "supabase/migrations/202607140005_training_visual_playbook.sql"
    ).exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")


def test_visual_catalog_seeds_and_sanitizes_answers_in_one_transaction() -> None:
    question_seed = VISUAL_LOWER.index(
        "insert into content_factory.training_questions"
    )
    answer_seed = VISUAL_LOWER.index(
        "insert into content_factory_private.training_answer_keys"
    )
    sanitization = VISUAL_LOWER.index(
        "(question.item - 'correct_value' - 'explanation')"
    )
    contract = VISUAL_LOWER.index("do $training_visual_contract$")
    commit = VISUAL_LOWER.rindex("commit;")

    assert question_seed < answer_seed < sanitization < contract < commit
    assert "leaked_course_answer_count" in VISUAL_LOWER[contract:commit]
    assert "$.knowledge_check.questions[*].correct_value" in VISUAL_LOWER[
        sanitization:commit
    ]
    assert "$.knowledge_check.questions[*].explanation" in VISUAL_LOWER[
        sanitization:commit
    ]
    assert "private_course_key_count <> public_course_question_count" in VISUAL_LOWER[
        contract:commit
    ]


def test_public_course_questions_are_sanitized_and_keys_move_private() -> None:
    answer_seed = LOWER.index(
        "insert into content_factory_private.training_answer_keys"
    )
    sanitization = LOWER.index(
        "(question.item - 'correct_value' - 'explanation')"
    )

    assert answer_seed < sanitization
    assert "insert into content_factory.training_questions" in LOWER
    assert "'course_check_' || module.code || '_'" in LOWER
    assert "900 + source.question_order" in LOWER
    assert "jsonb_build_array(source.question ->> 'correct_value')" in LOWER
    assert "training_modules_no_public_course_answer_keys" in LOWER
    assert "$.knowledge_check.questions[*].correct_value" in LOWER
    assert "$.knowledge_check.questions[*].explanation" in LOWER
    assert "module_type <> 'course'" in LOWER


def test_submit_rpc_grades_only_on_the_server_and_records_every_attempt() -> None:
    header, body = _function("creator_submit_course_check")

    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "content_factory_private.current_profile_id()" in body
    assert "content_factory_private.resolve_organization(p_payload)" in body
    assert "content_factory_private.membership_role" in body
    assert "jsonb_typeof(answers) <> 'object'" in body
    assert "creator_submit_course_check" in body
    assert "pg_advisory_xact_lock" in body
    assert "content_factory_private.training_answer_keys" in body
    assert body.count("content_factory_private.normalize_answer") >= 4
    assert "unknown_course_check_question" in body
    assert "insert into content_factory.training_attempts" in body
    assert "insert into content_factory.training_certifications" not in body
    assert "answered_count = total_count" in body
    assert "correct_count >= required_correct" in body


def test_shared_workspace_gate_requires_every_refreshed_course_attempt() -> None:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"content_factory_private\.membership_role\s*\(.*?\)\s*"
        r"returns\s+text(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match
    header = match.group("header").casefold()
    body = match.group("body").casefold()

    assert "security definer" in header
    assert "stable" in header
    assert "set search_path = ''" in header
    assert "require_certification and exists" in body
    assert "module.module_type = 'course'" in body
    assert "certification.attempt_id" in body
    assert "attempt.idempotency_key like 'course-check:%'" in body
    assert "attempt.answered_count = attempt.question_count" in body
    assert "refreshed_courses_required" in body


def test_private_storage_gate_cannot_bypass_refreshed_courses() -> None:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"content_factory\.storage_access_allowed\s*\(.*?\)\s*"
        r"returns\s+boolean(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match
    header = match.group("header").casefold()
    body = match.group("body").casefold()

    assert "security definer" in header
    assert "stable" in header
    assert "set search_path = ''" in header
    assert "module.module_type = 'course'" in body
    assert "course_certification.attempt_id" in body
    assert "attempt.idempotency_key like 'course-check:%'" in body
    assert "attempt.answered_count = attempt.question_count" in body
    assert "not p_allow_team_read" in body
    assert re.search(
        r"not\s+p_allow_team_read\s+and\s+"
        r"p_owner_id\s*=\s*auth\.uid\(\)::text\s+and\s+"
        r"membership\.role\s+in\s*\(\s*"
        r"'owner'\s*,\s*'admin'\s*,\s*'producer'\s*,\s*"
        r"'reviewer'\s*,\s*'operator'\s*\)",
        body,
        flags=re.DOTALL,
    )
    assert "'trainee'" not in body
    assert "'viewer'" not in body

    register_media = re.search(
        r"create\s+or\s+replace\s+function\s+public\.creator_register_media"
        r"\s*\(.*?\)\s*returns\s+jsonb.*?as\s+\$\$(?P<body>.*?)\$\$;",
        BASE_RPC_SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert register_media
    register_body = register_media.group("body").casefold()
    assert (
        "array['owner', 'admin', 'producer', 'reviewer', 'operator']"
        in register_body
    )
    assert (
        "revoke all on function\n"
        "  content_factory.storage_access_allowed(text, text, boolean)"
        in LOWER
    )
    assert (
        "grant execute on function\n"
        "  content_factory.storage_access_allowed(text, text, boolean)"
        in LOWER
    )


def test_submit_result_contains_safe_feedback_but_never_an_answer_key() -> None:
    _, body = _function("creator_submit_course_check")
    result_start = body.index("result := jsonb_build_object(")
    result_end = body.index(
        "perform content_factory_private.emit_event", result_start
    )
    result_contract = body[result_start:result_end]

    for field in (
        "'passed'",
        "'correct_count'",
        "'question_count'",
        "'review_topics'",
        "'feedback'",
    ):
        assert field in result_contract

    assert "Проверка пройдена. Теперь можно завершить блок." in SQL
    assert "Повторите отмеченные темы и пройдите проверку ещё раз." in SQL
    assert "correct_answers" not in result_contract
    assert "correct_value" not in result_contract
    assert "'answers'" not in result_contract
    assert "'question_code'" in body
    assert "'prompt'" in body


def test_spa_uses_server_grading_and_restores_passed_state_after_refresh() -> None:
    assert 'submitCourseCheck: "creator_submit_course_check"' in ADAPTER
    assert "submitCourseCheck(moduleCode, answers)" in ADAPTER
    assert "await state.api.submitCourseCheck(courseCode, answers)" in APP
    assert "trainingSource.course_checks" in APP
    assert "state.bootstrap.training.courseChecks.map" in APP
    assert "correctValue" not in APP
    assert "question?.correct_value" not in APP
    assert "question?.explanation" not in APP
    assert "selected.value ===" not in APP[
        APP.index("async function submitCourseKnowledgeCheck") : APP.index(
            "function syncCourseCompletionButton"
        )
    ]
    assert "source.review_topics" in APP


def test_preserved_exam_does_not_claim_a_locked_workspace_is_ready() -> None:
    learning_home = APP[
        APP.index("function renderLearningHome()") : APP.index(
            "function portalWorkflowMarkup()"
        )
    ]

    assert "const workspaceReady = hasWorkspaceAccess();" in learning_home
    assert "const nextHref = workspaceReady" in learning_home
    assert "const nextLabel = workspaceReady" in learning_home
    assert '${workspaceReady ? "Вы готовы к производству"' in learning_home
    assert "nextCourse?.code === course.code && !workspaceReady" in learning_home
    assert "nextCourse?.code === course.code && !examPassed" not in learning_home
    assert '${examPassed ? "допуск получен"' not in learning_home


def test_bootstrap_course_wrapper_preserves_fail_closed_membership_states() -> None:
    _, body = _function("creator_bootstrap")
    membership_guard = body.index(
        "coalesce(result ->> 'state', '') not in ('learning', 'workspace')"
    )
    course_override = body.index(
        "result := jsonb_set(result, '{state}', '\"learning\"'::jsonb, true)"
    )

    assert membership_guard < course_override
    assert "return result;" in body[membership_guard:course_override]


def test_complete_module_requires_a_valid_passed_server_attempt() -> None:
    header, body = _function("creator_complete_module")

    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "insert into content_factory.training_attempts" not in body
    assert "from content_factory.training_attempts attempt" in body
    assert "attempt.status = 'completed'" in body
    assert "attempt.passed" in body
    assert "attempt.idempotency_key like 'course-check:%'" in body
    assert "attempt.question_count = declared_question_count" in body
    assert "attempt.answered_count = declared_question_count" in body
    assert "attempt.correct_count >= required_correct" in body
    assert "course_knowledge_check_required" in body
    assert body.index("course_knowledge_check_required") < body.index(
        "content_factory_private.begin_command"
    )
    assert "replay ->> 'knowledge_attempt_id'" in body
    assert "replay ->> 'attempt_id'" in body
    assert "= attempt_id::text" in body
    assert "insert into content_factory.training_certifications" in body
    assert "knowledge_attempt_id" in body


def test_bootstrap_returns_refresh_safe_course_check_state_and_relocks_workspace() -> None:
    header, body = _function("creator_bootstrap")

    assert "security definer" in header
    assert "set search_path = ''" in header
    assert (
        "content_factory_private.creator_bootstrap_pre_course_gate(p_payload)"
        in body
    )
    assert "'{learning,course_checks}'" in body
    assert "'not_started'" in body
    assert "'retry_required'" in body
    assert "'passed'" in body
    assert "attempt.question_count = jsonb_array_length" in body
    assert "refreshed_courses_ready" in body
    assert "'{workspace_open}'" in body
    assert "'{learning,exam,available}'" in body
    assert "'{learning,exam,questions}'" in body
    assert "'{capabilities,mock_generation}'" in body
    assert "'{capabilities,real_generation}'" in body
    assert "attempt.answers" not in body
    assert "correct_answers" not in body
    assert "correct_value" not in body


def test_old_synthetic_course_certificates_are_revoked_with_system_audit() -> None:
    revoke_start = LOWER.index("with revoked_certifications as")
    revoke_end = LOWER.index(
        "create or replace function public.creator_submit_course_check",
        revoke_start,
    )
    revoke_contract = LOWER[revoke_start:revoke_end]

    assert "module.module_type = 'course'" in revoke_contract
    assert "attempt.question_count = 0" in revoke_contract
    assert "attempt.answered_count = 0" in revoke_contract
    assert "attempt.correct_count = 0" in revoke_contract
    assert "set status = 'revoked'" in revoke_contract
    assert "training_course_certificate_revoked" in revoke_contract
    assert "'source'," not in revoke_contract  # columns and values stay positional
    assert "'system'" in revoke_contract
    assert (
        "synthetic_zero_question_attempt_replaced_by_server_gate"
        in revoke_contract
    )
    assert "module.module_type = 'exam'" not in revoke_contract


def test_private_legacy_bootstrap_and_new_public_rpcs_have_narrow_grants() -> None:
    assert (
        "alter function public.creator_bootstrap(jsonb)\n"
        "  rename to creator_bootstrap_pre_course_gate"
    ) in LOWER
    assert (
        "alter function public.creator_bootstrap_pre_course_gate(jsonb)\n"
        "  set schema content_factory_private"
    ) in LOWER
    assert (
        "content_factory_private.creator_bootstrap_pre_course_gate(jsonb)\n"
        "  from public, anon, authenticated"
    ) in LOWER

    for function_name in (
        "creator_submit_course_check",
        "creator_bootstrap",
        "creator_complete_module",
    ):
        assert (
            f"revoke all on function public.{function_name}(jsonb)"
            in LOWER
        )
        assert (
            f"grant execute on function public.{function_name}(jsonb)"
            in LOWER
        )


def test_migration_fails_closed_if_question_mapping_or_answer_keys_drift() -> None:
    contract_start = LOWER.index("do $server_course_gate_contract$")
    contract = LOWER[contract_start:]

    assert "public_question_count" in contract
    assert "server_question_count" in contract
    assert "private_key_count" in contract
    assert "invalid_question_count" in contract
    assert "leaked_answer_count" in contract
    assert "answer_key.correct_answers ->> 0" in contract
    assert "server_course_knowledge_gate_contract_failed" in contract


def test_pgtap_fixtures_satisfy_the_refreshed_course_gate() -> None:
    creator = (PGTAP_DIR / "creator_factory_test.sql").read_text(
        encoding="utf-8"
    ).casefold()
    assert "'creator_submit_course_check'" in creator
    assert creator.count("\n  22,\n") >= 2
    assert "perform public.creator_submit_course_check" in creator
    assert "'pgtap-course-check-' || module_row.code" in creator
    assert "answer_key.correct_answers" in creator
    assert "question.order_index between 901 and 1000" in creator
    assert "perform pg_temp.grant_refreshed_course_gate" not in creator

    fixture_files = {
        "limited_member_provisioning_test.sql": 2,
        "paid_runway_generation_test.sql": 1,
        "seedance2_fast_8s_generation_test.sql": 1,
    }
    for filename, expected_calls in fixture_files.items():
        fixture = (PGTAP_DIR / filename).read_text(encoding="utf-8").casefold()
        assert "create or replace function pg_temp.grant_refreshed_course_gate" in fixture
        assert "module.module_type = 'course'" in fixture
        assert "jsonb_array_length(" in fixture
        assert "answer_key.correct_answers" in fixture
        assert "'course-check:' || p_key_prefix || ':' || module_row.code" in fixture
        assert "insert into content_factory.training_attempts" in fixture
        assert "insert into content_factory.training_certifications" in fixture
        assert "on conflict on constraint training_certifications_org_profile_module_uq" in fixture
        assert fixture.count("perform pg_temp.grant_refreshed_course_gate") == expected_calls
        assert "'operator_final_exam'" in fixture

    paid = (PGTAP_DIR / "paid_runway_generation_test.sql").read_text(
        encoding="utf-8"
    ).casefold()
    certified_fixture = paid[
        paid.index("('81111111-1111-4111-8111-111111111111'::uuid, 'real-owner')") :
        paid.index("insert into content_factory.products")
    ]
    assert "81555555-5555-4555-8555-555555555555" in certified_fixture
    assert "81666666-6666-4666-8666-666666666666" not in certified_fixture
