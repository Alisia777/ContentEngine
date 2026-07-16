from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607160006_background_worker_durability.sql"
)
PGTAP = ROOT / "supabase/tests/background_worker_durability_test.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    source = _text(MIGRATION)
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{name}\s*\("
        rf".*?\bas\s+\$\$(.*?)\$\$;",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, name
    return match.group(1)


def test_durability_migration_parses_and_pgtap_exists() -> None:
    parse_sql(_text(MIGRATION))
    assert PGTAP.is_file()
    assert "select plan(" in _text(PGTAP).lower()


def test_notification_outbox_is_private_durable_and_organization_scoped() -> None:
    source = " ".join(_text(MIGRATION).split())

    assert "create table if not exists content_factory.notification_outbox" in source
    assert (
        "foreign key (organization_id, recipient_id) references "
        "content_factory.memberships(organization_id, profile_id)"
    ) in source
    assert "unique (organization_id, recipient_id, dedupe_key)" in source
    assert "status in ('pending', 'delivering', 'delivered', 'failed')" in source
    assert "notification_outbox_deletion_forbidden" in source
    assert "notification_outbox_identity_immutable" in source
    assert (
        "alter table content_factory.notification_outbox enable row level security"
        in source
    )
    assert re.search(
        r"revoke all on content_factory\.notification_outbox\s+"
        r"from public, anon, authenticated",
        source,
    )
    assert "grant all on content_factory.notification_outbox to service_role" in source


def test_terminal_state_triggers_create_one_transactional_outbox_item() -> None:
    source = _text(MIGRATION)
    enqueue = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"content_factory_private\.enqueue_terminal_notification\(\)"
        r".*?\bas\s+\$\$(.*?)\$\$;",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert enqueue is not None
    body = " ".join(enqueue.group(1).split())

    for table in (
        "content_factory.generation_jobs",
        "content_factory.product_research_runs",
        "content_factory.content_review_runs",
    ):
        assert f"on {table}" in source
    assert "new.mode <> 'real'" in body
    assert "new.provider <> 'runway'" in body
    assert "background-worker:' || work_kind || ':'" in body
    assert (
        "on conflict (organization_id, recipient_id, dedupe_key) do nothing"
        in body
    )


def test_expired_paid_ai_leases_fail_atomically_without_generation_restart() -> None:
    body = " ".join(
        _function_body("system_reconcile_background_leases").split()
    )

    assert "from content_factory.product_research_runs run" in body
    assert "from content_factory.content_review_runs review" in body
    assert body.count("for update skip locked") == 2
    assert body.count("status = 'failed'") >= 2
    assert body.count("error_code = 'processing_lease_expired'") >= 2
    assert "status = 'queued'" not in body
    assert "generation_jobs" not in body
    assert "provider" not in body


def test_outbox_claim_recovers_lost_responses_and_expired_delivery_leases() -> None:
    body = " ".join(
        _function_body("system_claim_notification_outbox").split()
    )

    assert "from content_factory.user_notifications notification" in body
    assert "notification.dedupe_key = outbox.dedupe_key" in body
    assert "set status = 'delivered'" in body
    assert "outbox.lease_expires_at <= now()" in body
    assert "set status = 'pending'" in body
    assert "for update skip locked" in body
    assert "attempt_count = outbox.attempt_count + 1" in body
    assert "extensions.gen_random_uuid()" in body
    assert "now() + interval '3 minutes'" in body


def test_outbox_completion_retries_then_preserves_dead_letter() -> None:
    body = " ".join(
        _function_body("system_complete_notification_outbox").split()
    )

    assert "outbox_row.attempt_count >= 12" in body
    assert "set status = 'failed'" in body
    assert "set status = 'pending'" in body
    assert "make_interval(secs => retry_seconds)" in body
    assert "notification_outbox_lease_mismatch" in body
    assert "notification_outbox_lease_expired" in body
    assert "status in ('delivered', 'failed')" in body


def test_all_worker_durability_rpcs_are_service_role_only() -> None:
    source = " ".join(_text(MIGRATION).split())
    for name in (
        "system_reconcile_background_leases",
        "system_claim_notification_outbox",
        "system_complete_notification_outbox",
        "system_notification_outbox_health",
    ):
        assert re.search(
            rf"revoke all on function public\.{name}\(jsonb\) "
            rf"from public, anon, authenticated",
            source,
        )
        assert (
            f"grant execute on function public.{name}(jsonb) to service_role"
            in source
        )


def test_pgtap_covers_reconciliation_retry_idempotency_and_security() -> None:
    source = _text(PGTAP)

    for marker in (
        "processing_lease_expired",
        "system_reconcile_background_leases",
        "system_claim_notification_outbox",
        "system_complete_notification_outbox",
        "observed_deliveries",
        "notification_outbox_deletion_forbidden",
        "notification_outbox_lease_expired",
        "service role can reconcile expired work",
        "authenticated cannot claim notification delivery",
    ):
        assert marker in source
