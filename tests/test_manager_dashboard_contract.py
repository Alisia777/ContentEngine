from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607150003_manager_stuck_dashboard.sql"
).read_text(encoding="utf-8")
VIEW = (ROOT / "web" / "app" / "manager-dashboard-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "manager-dashboard.css").read_text(encoding="utf-8")


def test_manager_dashboard_is_a_manager_only_authenticated_rpc():
    assert "create or replace function public.creator_manager_dashboard" in MIGRATION
    assert "array['owner', 'admin']" in MIGRATION
    assert "revoke all on function public.creator_manager_dashboard(jsonb) from public, anon" in MIGRATION
    assert "grant execute on function public.creator_manager_dashboard(jsonb) to authenticated" in MIGRATION


def test_dashboard_covers_every_requested_funnel_stage():
    for stage in (
        "email",
        "login",
        "course",
        "exam",
        "generation",
        "task",
        "publication",
        "payout",
        "access",
        "ready",
    ):
        assert f"'{stage}'" in MIGRATION
        assert f"{stage}: Object.freeze" in VIEW


def test_dashboard_detects_real_operational_blockers():
    for code in (
        "temporary_password_change_required",
        "first_login_pending",
        "courses_incomplete",
        "final_exam_pending",
        "generation_failed",
        "task_blocked",
        "placement_failed",
        "payout_approved_not_paid",
        "profile_suspended",
        "profile_disabled",
        "auth_user_banned",
        "auth_user_deleted",
    ):
        assert code in MIGRATION
        assert code in VIEW


def test_dashboard_returns_no_secrets_or_recovery_tokens():
    returned_payload = MIGRATION[MIGRATION.index("'members', coalesce") :]
    for forbidden in (
        "encrypted_password",
        "access_token",
        "refresh_token",
        "token_hash",
        "external_payment_reference",
        "provider_task_id",
        "signed_url",
        "'profile_id'",
        "'generation_job_id'",
        "'placement_id'",
        "'payout_id'",
        "'task_id'",
        "'payout_amount_minor'",
        "'request_id'",
    ):
        assert forbidden not in returned_payload


def test_generation_action_is_status_check_not_a_new_paid_start():
    generation_action = VIEW[
        VIEW.index('if (action === "generation_status")') :
        VIEW.index('if (action === "placement")')
    ]
    assert "Проверить без нового запуска" in generation_action
    assert "startRealGeneration" not in generation_action
    assert "submit" not in generation_action.lower()


def test_access_repair_is_scoped_to_one_exact_email_and_server_verified():
    assert 'data-action="open-manager-access"' in VIEW
    assert 'data-email="${escapeHtml(invite.email || "")}"' in VIEW
    assert 'data-email="${escapeHtml(member.email || "")}"' in VIEW
    assert "Проверить и восстановить доступ" in VIEW
    assert 'data-action="retry-manager-invite"' not in VIEW
    assert 'data-action="send-manager-recovery"' not in VIEW


def test_password_change_detection_matches_current_and_legacy_auth_contracts():
    for marker in (
        "contentengine_password_change_required",
        "contentengine_password_change_completed",
        "contentengine_github_member_provisioned",
        "contentengine_owner_password_reset_once_20260714",
    ):
        assert marker in MIGRATION


def test_course_progress_uses_the_same_refreshed_attempt_gate_as_workspace_access():
    course_progress = MIGRATION[
        MIGRATION.index("left join lateral (", MIGRATION.index("course_requirement")) :
        MIGRATION.index(") course_progress on true")
    ]
    for contract in (
        "join content_factory.training_attempts attempt",
        "attempt.status = 'completed'",
        "attempt.passed",
        "attempt.idempotency_key like 'course-check:%'",
        "attempt.question_count = jsonb_array_length",
        "attempt.answered_count = attempt.question_count",
        "attempt.correct_count >=",
    ):
        assert contract in course_progress


def test_terminal_failures_do_not_outrank_newer_terminal_successes_forever():
    generation_lookup = MIGRATION[
        MIGRATION.index("from content_factory.generation_jobs job") :
        MIGRATION.index(") latest_generation on true")
    ]
    placement_lookup = MIGRATION[
        MIGRATION.index("from content_factory.placements placement") :
        MIGRATION.index(") latest_placement on true")
    ]
    assert "when job.status in ('queued', 'starting', 'submitted', 'processing') then 0" in generation_lookup
    assert "'processing', 'failed'" not in generation_lookup
    assert "placement.status in ('scheduled', 'ready')" in placement_lookup
    assert "'ready', 'failed'" not in placement_lookup


def test_task_and_access_are_visible_in_summary_and_have_safe_actions():
    assert "'task', count(*) filter (where member.stage = 'task')" in MIGRATION
    assert "'access', count(*) filter (where member.stage = 'access')" in MIGRATION
    assert 'if (action === "task")' in VIEW
    assert 'href="#/workspace/tasks"' in VIEW
    assert "grid-template-columns: repeat(5" in CSS


def test_zero_member_aggregates_keep_a_stable_json_shape():
    assert "count(*) filter (where member.stage = 'ready')" in MIGRATION
    assert "coalesce(jsonb_agg(jsonb_build_object(" in MIGRATION
    assert "'[]'::jsonb" in MIGRATION


def test_unknown_server_reason_codes_are_not_echoed_into_the_page():
    fallback = VIEW[VIEW.index("function reasonLabel") : VIEW.index("function initials")]
    assert "code.replaceAll" not in fallback
    assert "Статус требует проверки руководителем" in fallback
