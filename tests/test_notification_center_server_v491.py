from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608130001_notification_center_v491.sql"
PGTAP = ROOT / "supabase/tests/notification_center_v491_test.sql"
LEGACY_INBOX = (
    ROOT / "supabase/migrations/202607160005_operational_workspace_foundation.sql"
)
DURABLE_CHAIN = (
    ROOT / "supabase/migrations/202607160006_background_worker_durability.sql"
)
PROJECT_SCOPE = (
    ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
)
WATCHLIST_PRODUCER = (
    ROOT / "supabase/migrations/202608030007_research_watchlist_memory.sql"
)
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(source: str, signature: str) -> str:
    start = -1
    for occurrence in re.finditer(re.escape(signature), source):
        declaration = source.rfind("create or replace function", 0, occurrence.start())
        if declaration >= 0 and not source[declaration : occurrence.start()].strip().endswith(
            "--"
        ):
            between = source[declaration : occurrence.start()]
            if ";" not in between:
                start = declaration
                break
    assert start >= 0, signature
    match = re.search(r"\$function\$(.*?)\$function\$;", source[start:], re.DOTALL)
    assert match is not None
    return source[start : start + match.end()]


def test_migration_and_pgtap_parse_transactionally() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.lstrip().casefold().startswith("begin;")
    assert migration.rstrip().casefold().endswith("commit;")
    assert pgtap.lstrip().casefold().startswith("begin;")
    assert pgtap.rstrip().casefold().endswith("rollback;")
    assert "select plan(36);" in pgtap
    assertion_count = sum(
        len(re.findall(rf"(?im)^select\s+{name}\s*\(", pgtap))
        for name in ("has_column", "ok", "is", "throws_ok")
    )
    assert assertion_count == 36


def test_adds_to_the_one_existing_inbox_outbox_chain() -> None:
    migration = _read(MIGRATION).casefold()
    legacy = _read(LEGACY_INBOX).casefold()
    durable = _read(DURABLE_CHAIN).casefold()
    project_scope = _read(PROJECT_SCOPE).casefold()

    assert "create table if not exists content_factory.user_notifications" in legacy
    assert "create table if not exists content_factory.notification_outbox" in durable
    assert "scope_notification_outbox_v47" in project_scope
    assert "create table" not in migration
    assert "alter table content_factory.user_notifications" in migration
    assert "alter table content_factory.notification_outbox" in migration
    assert migration.count("insert into content_factory.notification_outbox") == 1
    assert "content_factory_private.enqueue_notification_v491(" in migration
    assert "public.system_emit_notification(" in migration
    assert "content_factory_private.deliver_notification_v491(" in migration
    assert "second feed" not in migration


def test_canonical_vocabularies_are_closed_and_matrix_exact() -> None:
    source = _read(MIGRATION)
    enqueue = _function(source, "enqueue_notification_v491(")

    for notification_type in (
        "action_required",
        "mention",
        "assignment",
        "process_complete",
        "warning",
        "error",
        "access_change",
        "system_info",
    ):
        assert f"'{notification_type}'" in enqueue
    assert "notification_type_value = 'system'" in enqueue
    assert "notification_type_value := 'system_info'" in enqueue
    for source_section in (
        "finder",
        "results",
        "research",
        "ai",
        "create",
        "review",
        "publish",
        "processes",
        "settings",
        "trash",
        "system",
    ):
        assert f"'{source_section}'" in enqueue
    for role in (
        "owner",
        "admin",
        "producer",
        "reviewer",
        "operator",
        "trainee",
        "viewer",
    ):
        assert f"'{role}'" in source
    for action_key in (
        "ai.open-decisions",
        "process.open",
        "review.open-object",
        "object.open",
    ):
        assert f"'{action_key}'" in enqueue
    assert "paid.retry" not in source
    assert "notification_action_key_invalid" in enqueue
    assert "notification_action_target_required" in enqueue


def test_severity_action_target_and_safe_route_are_server_validated() -> None:
    source = _read(MIGRATION)
    enqueue = _function(source, "enqueue_notification_v491(")
    route = _function(source, "notification_route_v491(")
    deliver = _function(source, "deliver_notification_v491(")

    expected_severity = {
        "action_required": "warning",
        "mention": "info",
        "assignment": "info",
        "process_complete": "success",
        "warning": "warning",
        "error": "danger",
        "access_change": "neutral",
        "system_info": "neutral",
    }
    for notification_type, severity in expected_severity.items():
        assert f"when '{notification_type}' then '{severity}'" in enqueue
    assert "notification_severity_type_mismatch" in enqueue
    assert "requires_action_value" in enqueue
    assert "project_id_value" in enqueue
    assert "object_id_value" in enqueue
    assert "process_id_value" in enqueue
    assert "#/workspace/ai?project_id=" in route
    assert "&tab=decisions" in route
    assert "#/workspace/work?process_id=" in route
    assert "#/workspace/review" in route
    assert "#/workspace/board" in route
    assert "notification_action_route_invalid" in deliver
    assert "notification_delivery_not_claimed" in deliver
    assert "http" not in route.casefold()
    assert "contentengine://" not in route.casefold()


def test_plpgsql_if_conditions_parenthesize_nested_case_expressions() -> None:
    source = _read(MIGRATION)
    enqueue = _function(source, "enqueue_notification_v491(")
    deliver = _function(source, "deliver_notification_v491(")

    for function in (enqueue, deliver):
        assert "severity_value <> (case notification_type_value" in function
        assert (
            "requires_action_value is distinct from (case notification_type_value"
            in function
        )
        assert "severity_value <> case notification_type_value" not in function
        assert (
            "requires_action_value is distinct from case notification_type_value"
            not in function
        )


def test_sensitive_payload_and_untrusted_envelope_are_fail_closed() -> None:
    source = _read(MIGRATION)
    sensitive = _function(source, "notification_payload_sensitive_v491(")
    enqueue = _function(source, "enqueue_notification_v491(")
    deliver = _function(source, "deliver_notification_v491(")

    for token in (
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "signed_url",
        "file_content",
        "provider_payload",
        "paid_confirmation",
        "prompt",
    ):
        assert token in sensitive
    assert "notification_sensitive_payload_rejected" in enqueue
    assert "properties_value ? '_notification_v491'" in enqueue
    assert "properties_value := wire_properties_value - '_notification_v491'" in deliver
    assert "metadata_value - array[" in deliver
    assert "notification_v491_metadata_invalid" in deliver
    assert "jsonb_typeof(properties_value) <> 'object'" in enqueue
    assert "length(properties_value::text) > 8192" in enqueue


def test_role_targets_expand_once_to_per_user_durable_rows() -> None:
    source = _read(MIGRATION)
    enqueue = _function(source, "enqueue_notification_v491(")

    assert "recipient_user_id_value is null and recipient_roles_value is null" in enqueue
    assert "membership.status = 'active'" in enqueue
    assert "organization.status = 'active'" in enqueue
    assert "profile.status = 'active'" in enqueue
    assert "membership.role = any(recipient_roles_value)" in enqueue
    assert "recipient_snapshot_ids" in enqueue
    assert "notification-v491-targets:" in enqueue
    assert "from unnest(recipient_snapshot_ids)" in enqueue
    assert "target_count > 500" in enqueue
    assert "recipient_id, kind, severity" in enqueue
    assert "recipient_role_ids" in enqueue
    assert "shared-read" in source


def test_dedupe_versions_are_actor_rows_not_duplicate_feed_rows() -> None:
    source = _read(MIGRATION)
    enqueue = _function(source, "enqueue_notification_v491(")
    deliver = _function(source, "deliver_notification_v491(")
    guard = _function(source, "guard_user_notification()")

    assert "user_notifications_current_dedupe_v491_uq" in source
    assert "organization_id, recipient_id, canonical_dedupe_key" in source
    assert "dedupe_version_value not between 1 and 2147483647" in enqueue
    assert "latest_version_value > dedupe_version_value" in enqueue
    assert "notification_idempotency_conflict" in enqueue
    assert "notification_row.dedupe_version < dedupe_version_value" in deliver
    assert "where notification.id = notification_row.id" in deliver
    assert "read_at = null" in deliver
    assert "notification_revision_regression" in guard
    assert "new.dedupe_version = old.dedupe_version" in guard
    assert "new.read_at is not null" in guard


def test_retention_expiry_and_legacy_backfill_are_finite_and_honest() -> None:
    source = _read(MIGRATION).casefold()
    claim = _function(_read(MIGRATION), "system_claim_notification_outbox(")
    complete = _function(_read(MIGRATION), "system_complete_notification_outbox(")
    projection = _function(_read(MIGRATION), "creator_notification_center(")

    assert source.count("interval '180 days'") >= 8
    assert "contract_version = 1" in source
    assert "event_created_at = notification.created_at" in source
    assert "event_created_at = outbox.created_at" in source
    assert "expires_at = notification.created_at + interval '180 days'" in source
    assert "expires_at = outbox.created_at + interval '180 days'" in source
    assert "recipient_role_ids =" not in source[: source.index("create or replace function")]
    assert "source_section =" not in source[: source.index("create or replace function")]
    assert "status = 'expired'" in claim
    assert "outbox.expires_at > now()" in claim
    assert "status = 'expired'" in complete
    assert "notification.expires_at > now()" in projection
    assert "legacy_unknown_type_is_null" in projection


def test_projection_is_org_user_active_role_scoped_before_counts_and_page() -> None:
    source = _read(MIGRATION)
    projection = _function(source, "creator_notification_center(")

    scoped_position = projection.index("with scoped as materialized")
    filtered_position = projection.index("filtered as materialized")
    candidates_position = projection.index("candidates as materialized")
    assert scoped_position < filtered_position < candidates_position
    for token in (
        "notification.organization_id = organization_id",
        "notification.recipient_id = user_id",
        "membership.status = 'active'",
        "organization.status = 'active'",
        "profile.status = 'active'",
        "membership.role = any(notification.recipient_role_ids)",
        "notification.expires_at > now()",
    ):
        assert token in projection
    assert "active_role_ids" in projection
    assert "read_state_version" in projection
    assert "keyset_event_created_at_id" in projection
    assert "limit page_size + 1" in projection
    assert "properties" not in projection[projection.index("'items'") :]
    assert "deep_link" not in projection[projection.index("'items'") :]


def test_mark_read_is_exact_visible_filter_and_actor_scoped() -> None:
    source = _read(MIGRATION)
    mark = _function(source, "creator_mark_visible_notifications_read(")

    assert "notification_ids" in mark
    assert "filter_value" in mark
    assert "notification_filter_matches_v491(" in mark
    assert "notification.expires_at > now()" in mark
    assert "notification.recipient_id = user_id" in mark
    assert "membership.role = any(notification.recipient_role_ids)" in mark
    assert "visible_count <> cardinality(notification_ids)" in mark
    assert "notification_visible_scope_denied" in mark
    assert "scope', 'visible_filter'" in mark
    assert "scoped_idempotency_key_value" in mark
    assert "user_id::text || ':' || idempotency_key_value" in mark
    assert "read_state_version" in mark
    assert "all_unread" not in mark
    assert "delete " not in mark.casefold()


def test_worker_wire_shape_and_existing_direct_recipient_path_are_preserved() -> None:
    source = _read(MIGRATION)
    claim = _function(source, "system_claim_notification_outbox(")
    emit = _function(source, "public.system_emit_notification(")
    worker = _read(WORKER)

    wire_keys = (
        "organization_id",
        "recipient_id",
        "kind",
        "severity",
        "title",
        "body",
        "deep_link",
        "entity_type",
        "entity_id",
        "properties",
        "idempotency_key",
    )
    payload_block = claim[claim.index("'payload', jsonb_build_object(") :]
    for key in wire_keys:
        assert f"'{key}'" in payload_block
        assert f'"{key}"' in worker
    assert "Keep this exact 11-key payload shape" in claim
    assert "if p_payload #>> '{properties,_notification_v491,contract_version}' = '491'" in emit
    assert "kind_value !~ '^[a-z][a-z0-9_]{2,79}$'" in emit
    assert "notification_recipient_not_found" in emit
    assert "contract_version, event_created_at, expires_at" in emit
    assert "statement_timestamp() + interval '180 days'" in emit


def test_grants_rls_no_client_delete_and_private_producer_boundary() -> None:
    source = _read(MIGRATION).casefold()

    assert "alter table content_factory.user_notifications enable row level security" not in source
    assert "disable row level security" not in source
    assert "revoke all on content_factory.user_notifications" in source
    assert "revoke all on content_factory.notification_outbox" in source
    assert "from public, anon, authenticated;" in source
    assert "grant all on content_factory.user_notifications to service_role" in source
    assert "grant all on content_factory.notification_outbox to service_role" in source
    assert "grant execute on function public.creator_notification_center(jsonb)" in source
    assert "grant execute on function\n  public.creator_mark_visible_notifications_read(jsonb)" in source
    assert "revoke all on function\n  content_factory_private.enqueue_notification_v491(jsonb)" in source
    assert "from public, anon, authenticated, service_role" in source
    assert "notification_deletion_forbidden" in source
    assert "notification_outbox_deletion_forbidden" in source
    assert "delete from content_factory.user_notifications" not in source
    assert "delete from content_factory.notification_outbox" not in source


def test_research_producer_and_edge_are_not_modified_or_reimplemented() -> None:
    migration = _read(MIGRATION)
    watchlist = _read(WATCHLIST_PRODUCER)
    worker = _read(WORKER)

    assert "research_watchlist_scheduler" not in migration
    assert "research_refresh_due" not in migration
    assert "insert into content_factory.notification_outbox" in watchlist
    assert '"system_claim_notification_outbox"' in worker
    assert '"system_emit_notification"' in worker
    assert '"system_complete_notification_outbox"' in worker
    assert "fetch(" not in migration


def test_deploy_and_rollback_notes_are_explicit_and_non_destructive() -> None:
    header = _read(MIGRATION)[:2500].casefold()

    assert "deploy after 202608040005_project_scoped_workflow.sql" in header
    assert re.search(
        r"before any v4\.9\.1\s*--\s*producer or notification center ui",
        header,
    )
    assert "rolling deployment" in header
    assert "rollback:" in header
    assert re.search(
        r"disable\s*--\s*producers/ui first and roll forward",
        header,
    )
    assert re.search(
        r"no rollback path grants client delete",
        header,
    )
