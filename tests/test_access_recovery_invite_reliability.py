from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_invalid_auth_link_is_sanitized_and_has_recovery_specific_cta() -> None:
    app = _text("web/app/app.js")

    assert 'state.authLinkError = normalizeAuthLinkError(error)' in app
    assert 'clearAuthLinkUrl("/auth-link-error")' in app
    assert 'path === "/auth-link-error"' in app
    assert "function renderAuthLinkError()" in app
    assert 'data-action="request-new-auth-link"' in app
    assert "Запросить новую ссылку" in app
    assert "Нужно новое приглашение" in app
    assert 'next.search = ""' in app
    assert "Токен удалён из адресной строки" in app


def test_required_password_change_is_server_marked_and_workspace_gated() -> None:
    app = _text("web/app/app.js")
    member = _text("scripts/provision_supabase_member.py")
    owner_reset = _text("scripts/reset_supabase_owner_password.py")
    edge = _text("supabase/functions/creator-set-password/index.ts")

    marker = "contentengine_password_change_required"
    completed = "contentengine_password_change_completed"
    assert marker in app and marker in member and marker in owner_reset and marker in edge
    assert completed in app and completed in edge
    assert "state.forcePassword = requiresPasswordChange(data.user)" in app
    assert 'navigate("/set-password", true)' in app
    assert 'state.supabase.functions.invoke("creator-set-password"' in app
    assert "getUserById(userId)" in edge
    assert "updateUserById(userId" in edge
    assert "passwordChangeRequired(metadata)" in edge
    assert "password_change_not_required" in edge


def test_reset_and_invite_have_soft_timeouts_and_honest_delivery_copy() -> None:
    app = _text("web/app/app.js")

    assert "AUTH_REQUEST_TIMEOUT_MS = 15_000" in app
    assert "INVITE_REQUEST_TIMEOUT_MS = 25_000" in app
    assert "RESET_RESEND_COOLDOWN_MS = 60_000" in app
    assert "resetPasswordForEmail" in app and "withUiTimeout(" in app
    assert "function startResetResendCountdown()" in app
    assert "Это ещё не подтверждение доставки письма" in app
    assert "Доставка писем ещё не подтверждена" in app
    assert 'status: "pending_verification"' in app
    assert 'reason_code: "client_timeout"' in app


def test_invite_attempts_are_reasoned_and_persisted_server_side() -> None:
    edge = _text("supabase/functions/creator-invite/index.ts")
    migration = _text(
        "supabase/migrations/202607150002_access_recovery_invite_reliability.sql"
    ).casefold()
    api = _text("web/app/supabase-api.js")
    app = _text("web/app/app.js")

    assert "reason_code" in edge
    assert "delivery_status" in edge
    assert 'const requestId = crypto.randomUUID()' in edge
    assert '"system_record_invite_delivery_attempts"' in edge
    assert "create table if not exists content_factory.invite_delivery_attempts" in migration
    assert "create or replace function public.system_record_invite_delivery_attempts" in migration
    assert "create or replace function public.creator_invite_delivery_attempts" in migration
    assert (
        "grant execute on function public.system_record_invite_delivery_attempts(jsonb)"
        in migration
    )
    assert "to service_role" in migration
    assert (
        "grant execute on function public.creator_invite_delivery_attempts(jsonb)"
        in migration
    )
    assert "creator_invite_delivery_attempts" in api
    assert "persistTeamInviteResult" in app
    assert 'data-action="prepare-failed-invites"' in app


def test_fifty_address_invite_is_prejournaled_bounded_and_idempotently_updated() -> None:
    edge = _text("supabase/functions/creator-invite/index.ts")
    migration = _text(
        "supabase/migrations/202607150004_invite_batch_resilience.sql"
    ).casefold()
    pgtap = _text("supabase/tests/invite_batch_resilience_test.sql").casefold()

    assert "const MAX_INVITES = 50" in edge
    assert "const MAX_CONCURRENT_INVITES = 5" in edge
    assert 'status: "pending_verification"' in edge
    assert 'reason_code: "invite_processing_started"' in edge
    assert 'delivery_status: "unknown"' in edge
    assert 'code: "invite_journal_unavailable"' in edge
    assert "const reservation = await persistResults(pendingResults)" in edge
    assert 'reason_code: "duplicate_request_suppressed"' in edge
    assert "const workIndexes: number[] = []" in edge
    assert edge.index("persistResults(pendingResults)") < edge.index(
        ".auth.admin.inviteUserByEmail"
    )
    assert "Math.min(MAX_CONCURRENT_INVITES, workIndexes.length)" in edge
    assert "await Promise.all(" in edge
    assert "persistResults([result])" in edge
    assert "persistencePending" in edge
    assert "persistResults(retryResults)" in edge
    assert edge.count(".auth.admin.inviteUserByEmail") == 1

    assert "pending_verification" in migration
    assert "delivery_status in ('accepted_unconfirmed', 'not_requested', 'unknown')" in migration
    assert "pg_catalog.pg_advisory_xact_lock" in migration
    assert "interval '10 minutes'" in migration
    assert "duplicate_request_suppressed" in migration
    assert "'suppressed', suppressed_value" in migration
    assert "on conflict on constraint invite_delivery_attempts_request_email_uq do update" in migration
    assert "to service_role" in migration
    assert "select plan(6)" in pgtap
    assert "duplicate_request_suppressed" in pgtap
    assert "not has_function_privilege" in pgtap
