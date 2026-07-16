from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607160005_operational_workspace_foundation.sql"
)
SQL = MIGRATION_PATH.read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/operational_workspace_foundation_test.sql"
).read_text(encoding="utf-8")

BROWSER_RPCS = (
    "creator_my_work",
    "creator_notifications",
    "creator_mark_notifications_read",
    "creator_training_progress",
    "creator_save_training_progress",
    "creator_saved_work_views",
)


def _function_body(name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{name}"
        rf"\s*\(\s*p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing {name}(p_payload jsonb)"
    header = match.group("header").casefold()
    assert "security definer" in header
    assert "set search_path = ''" in header
    return match.group("body")


def test_migration_is_the_next_ordered_supabase_version() -> None:
    versions = sorted(
        path.name
        for path in (ROOT / "supabase/migrations").glob("*.sql")
    )
    assert "202607160004_real_generation_reconciliation.sql" in versions
    assert MIGRATION_PATH.name in versions
    assert versions.index(MIGRATION_PATH.name) == (
        versions.index("202607160004_real_generation_reconciliation.sql") + 1
    )


def test_operational_tables_are_rls_and_rpc_only() -> None:
    for table in (
        "user_notifications",
        "training_walkthrough_progress",
        "saved_work_views",
    ):
        assert f"create table if not exists content_factory.{table}" in SQL
        assert (
            f"alter table content_factory.{table} enable row level security"
            in " ".join(SQL.split())
        )
        assert re.search(
            rf"revoke\s+all\s+on\s+content_factory\.{table}"
            rf"\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
            SQL,
            flags=re.IGNORECASE,
        )
        assert re.search(
            rf"grant\s+all\s+on\s+content_factory\.{table}"
            rf"\s+to\s+service_role",
            SQL,
            flags=re.IGNORECASE,
        )


def test_browser_rpcs_are_one_arg_authenticated_only() -> None:
    for name in BROWSER_RPCS:
        _function_body(name)
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{name}"
            rf"\s*\(\s*jsonb\s*\)\s+from\s+public\s*,\s*anon",
            SQL,
            flags=re.IGNORECASE,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{name}"
            rf"\s*\(\s*jsonb\s*\)\s+to\s+authenticated",
            SQL,
            flags=re.IGNORECASE,
        )

    assert re.search(
        r"revoke\s+all\s+on\s+function\s+public\.system_emit_notification"
        r"\s*\(\s*jsonb\s*\)\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
        SQL,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+public\.system_emit_notification"
        r"\s*\(\s*jsonb\s*\)\s+to\s+service_role",
        SQL,
        flags=re.IGNORECASE,
    )


def test_my_work_is_org_scoped_filtered_counted_and_keyset_paginated() -> None:
    body = " ".join(_function_body("creator_my_work").split())

    assert "current_profile_id()" in body
    assert "resolve_organization(p_payload)" in body
    assert "membership_role( organization_id, true, null" in body
    for item_type in ("task", "generation", "review", "placement", "payout"):
        assert f"'{item_type}'::text" in body
        assert f"'{item_type}', count(*) filter" in body
    assert (
        "job.status in ( 'queued', 'starting', 'submitted', 'processing', 'failed' )"
        in body
    )
    assert "job.status = 'failed'" in body
    assert "review_task.status not in ('done', 'cancelled')" in body
    assert "real_generation_reconciliation_unresolved( job.output )" in body
    assert "review.status = 'failed' and retry_review.id is null" in body
    assert "child.parent_review_id = review.id" in body
    assert "child.status <> 'cancelled'" in body
    assert "'awaiting_decision'" in body
    assert "normalize_work_filters(" in body
    assert "cardinality(statuses_value) = 0" in body
    assert "cardinality(item_types_value) = 0" in body
    assert "item.search_text like '%' || query_value || '%'" in body
    assert "(item.updated_at, item.item_type, item.id) <" in body
    assert "limit page_size + 1" in body
    assert "'next_cursor'" in body
    assert "'action_required'" in body
    assert "'blockers'" in body
    assert "'blocker', item.blocker" in body
    assert "'overdue'" in body
    assert "'cursor_mode', 'keyset_updated_at_type_id'" in body
    assert "task.assignee_id = user_id" in body
    assert "payout.profile_id = user_id" in body
    assert "placement.assigned_to = user_id" in body


def test_notification_contract_is_safe_idempotent_and_audited() -> None:
    listing = " ".join(_function_body("creator_notifications").split())
    marking = " ".join(
        _function_body("creator_mark_notifications_read").split()
    )
    emitting = " ".join(_function_body("system_emit_notification").split())

    assert "notification.recipient_id = user_id" in listing
    assert "'total'" in listing
    assert "'unread'" in listing
    assert "'deep_link'" in listing
    assert "(notification.created_at, notification.id) <" in listing
    assert "limit page_size + 1" in listing

    assert "jsonb_array_length(p_payload -> 'notification_ids')" in marking
    assert "notification.recipient_id = user_id" in marking
    assert "begin_command(" in marking
    assert "finish_command(" in marking
    assert "emit_event(" in marking
    assert "notification_access_denied" in marking
    assert "notification_id_duplicate" in marking
    assert "'all_unread'" in marking
    assert "notification.read_at is null" in marking
    assert "'scope', 'all_unread'" in marking
    assert "'remaining_unread', 0" in marking

    assert "notification_recipient_not_found" in emitting
    assert "notification_idempotency_conflict" in emitting
    assert "pg_advisory_xact_lock(" in emitting
    assert "content_factory_private.json_hash(request_payload)" in emitting
    assert "'notification_emitted'" in emitting
    assert "'system'" in emitting
    assert "length(deep_link_value) not between 3 and 600" in emitting
    assert "deep_link_value !~ '^#/" in emitting
    assert "{1,597}" not in SQL


def test_training_progress_is_catalog_bound_monotonic_and_syncable() -> None:
    listing = " ".join(_function_body("creator_training_progress").split())
    saving = " ".join(
        _function_body("creator_save_training_progress").split()
    )

    assert "training_walkthrough_progress progress" in listing
    assert "progress.profile_id = user_id" in listing
    assert "'completed_frame_ids'" in listing
    assert "'version'" in listing

    assert "module.content -> 'interactive_walkthroughs'" in saving
    assert "walkthrough.value ->> 'id' = walkthrough_id_value" in saving
    assert "training_walkthrough_not_found" in saving
    assert "training_current_frame_unknown" in saving
    assert "training_completed_frame_unknown" in saving
    assert "normalized_frame_ids := all_frame_ids" in saving
    assert "training_progress_version_conflict" in saving
    assert "progress_row.completed_frame_ids || normalized_frame_ids" in saving
    assert "greatest( progress.position_seconds, position_seconds_value )" in saving
    assert "begin_command(" in saving
    assert "finish_command(" in saving
    assert "emit_event(" in saving

    normalized_sql = " ".join(SQL.split())
    assert "old.completed_frame_ids <@ new.completed_frame_ids" in normalized_sql
    assert "old.completed and not new.completed" in normalized_sql
    assert "new.version := old.version + 1" in normalized_sql


def test_saved_views_are_normalized_capped_versioned_and_idempotent() -> None:
    body = " ".join(_function_body("creator_saved_work_views").split())
    helper = " ".join(SQL.split())

    assert "action_value not in ('list', 'upsert', 'delete', 'set_default')" in body
    assert "'is_default', make_default_value" in body
    assert "saved_work_view_is_default_invalid" in body
    assert "organization_id, profile_id, name, filters, is_default" in body
    assert "when make_default_value then true" in body
    assert "normalize_work_filters(" in body
    assert ">= 50" in body
    assert "saved_work_view_limit_exceeded" in body
    assert "saved_work_view_name_conflict" in body
    assert "saved_work_view_version_conflict" in body
    assert "expected_version_value is null or view.version = expected_version_value" in body
    assert "begin_command(" in body
    assert "finish_command(" in body
    assert "emit_event(" in body
    assert "saved_work_views_json(" in body
    assert "saved_work_views_one_default_uq" in helper
    assert "where is_default" in helper
    assert "new.version := old.version + 1" in helper


def test_filter_validation_is_shared_by_live_and_saved_views() -> None:
    normalized = " ".join(SQL.split())

    assert (
        "create or replace function "
        "content_factory_private.normalize_work_filters" in normalized
    )
    assert "value - array['query', 'statuses', 'item_types']::text[]" in normalized
    assert "jsonb_array_length(value -> 'statuses') > 20" in normalized
    assert "jsonb_array_length(value -> 'item_types') > 5" in normalized
    assert (
        "'task', 'generation', 'review', 'placement', 'payout'"
        in normalized
    )
    assert normalized.count("normalize_work_filters(") >= 3


def test_pgtap_covers_runtime_isolation_and_all_five_work_types() -> None:
    assert "select plan(59);" in PGTAP
    assert "set local role authenticated;" in PGTAP
    assert "active_membership_required" in PGTAP
    assert "notification_idempotency_conflict" in PGTAP
    assert "training_progress_version_conflict" in PGTAP
    assert "saved_work_view_version_conflict" in PGTAP
    assert "saved view creation atomically selects the default" in PGTAP
    assert "mark all unread updates every remaining server-side notification" in PGTAP
    for path in (
        "{counts,task}",
        "{counts,generation}",
        "{counts,review}",
        "{counts,placement}",
        "{counts,payout}",
    ):
        assert path in PGTAP
