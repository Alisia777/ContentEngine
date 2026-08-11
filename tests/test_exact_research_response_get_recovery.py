from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = (
    MIGRATIONS / "202608110003_exact_research_response_get_recovery.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "exact_research_response_get_recovery_test.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(sql: str, name: str, next_marker: str) -> str:
    marker = f"create or replace function\n  {name}"
    if marker not in sql:
        marker = f"create or replace function {name}"
    start = sql.index(marker)
    end = sql.index(next_marker, start)
    return sql[start:end]


def test_migration_prefix_is_unique_and_sql_is_parseable() -> None:
    assert MIGRATION.name.startswith("202608110003_")
    matching_prefixes = sorted(
        path.name for path in MIGRATIONS.glob("202608110003_*.sql")
    )
    assert matching_prefixes == [MIGRATION.name]
    migration_sql = _read(MIGRATION)
    assert parse_sql(migration_sql)
    assert parse_sql(_read(PGTAP))
    assert not re.search(
        r"research_provider_response_recovery_authorizations\s+authorization\b",
        migration_sql,
        flags=re.IGNORECASE,
    )
    assert "recovery_auth." in migration_sql


def test_recovery_ledgers_are_private_append_only_and_lineage_composite() -> None:
    sql = _read(MIGRATION).casefold()
    ledgers = {
        "research_provider_response_recovery_authorizations":
            "research_response_recovery_authorization_append_only",
        "research_provider_response_recovery_get_reservations":
            "research_response_recovery_reservation_append_only",
        "research_provider_response_recovery_outcomes":
            "research_response_recovery_outcome_append_only",
    }
    for table, trigger in ledgers.items():
        assert f"content_factory.{table}" in sql
        assert f"alter table\n  content_factory.{table}\n  enable row level security" in sql
        assert f"content_factory.{table}\n  from public, anon, authenticated, service_role" in sql
        assert trigger in sql

    assert "unique (organization_id, project_id, run_id, id)" in sql
    assert "unique (organization_id, run_id, id)" in sql
    assert "unique (organization_id, run_id)" in sql
    assert "maximum_provider_gets = 1" in sql
    assert "not provider_post_allowed" in sql
    assert "include_web_search_sources" in sql

    ledger_ddl = sql[: sql.index("create index if not exists")]
    for forbidden_column in (
        "response_body",
        "output_text",
        "bearer_token",
        "api_key",
    ):
        assert forbidden_column not in ledger_ddl
    assert not re.search(r"\bprompt\s+(?:text|jsonb|bytea)\b", ledger_ddl)


def test_creator_authorization_requires_role_project_exact_and_completed_response() -> None:
    sql = _read(MIGRATION).casefold()
    authorization = _function(
        sql,
        "public.creator_authorize_product_research_response_recovery(",
        "create or replace function\n  content_factory_private.capture_research_response_recovery_outcome",
    )
    for marker in (
        "current_profile_id()",
        "array['owner', 'admin', 'producer']",
        "membership_role(\n    organization_id_value, false",
        "require_workspace_project_access",
        "require_project_entity",
        "run_row.status <> 'failed'",
        "run_row.error_code <> 'provider_response_invalid'",
        "research_exact_youtube_research_bindings",
        "media_matches_registered_source",
        "paid_analysis_ack_snapshot",
        "analysis_scope = 'sampled_frames_only'",
        "research_provider_response_bindings",
        "latest_provider_status_value",
        "response_row.accepted_at >\n       clock_timestamp() - interval '8 minutes'",
        ") <> 'completed'",
        "recovery_ack",
    ):
        assert marker in authorization
    assert "provider_response_id" not in authorization
    assert "interval '9 minutes'" not in authorization


def test_claim_reserves_before_transition_and_never_creates_paid_work() -> None:
    sql = _read(MIGRATION).casefold()
    claim = _function(
        sql,
        "public.system_claim_product_research_response_recovery(",
        "create or replace function\n  public.system_read_product_research_response_recovery_reservation",
    )
    reservation_insert = claim.index(
        "insert into\n    content_factory.research_provider_response_recovery_get_reservations"
    )
    run_transition = claim.index("update content_factory.product_research_runs run")
    response_return = claim.rindex("'provider_response_id'")
    assert reservation_insert < run_transition < response_return
    assert "product_research_exact_response_recovery" in claim
    assert "interval '90 seconds'" in claim
    assert (
        "response_row.accepted_at >\n       clock_timestamp() - interval '8 minutes'"
        in claim
    )
    assert "research_response_recovery_get_already_reserved" in claim
    assert "'get_allowed', false" in claim
    replay_start = claim.index("if reservation_row.id is not null then")
    replay_end = claim.index("end if;", replay_start)
    assert "provider_response_id" not in claim[replay_start:replay_end]
    for forbidden in (
        "system_begin_research_provider_attempt",
        "insert into content_factory.research_run_provider_bindings",
        "insert into content_factory.research_execution_authorizations",
        "api.openai.com",
        "method: \"post\"",
    ):
        assert forbidden not in claim

    read_guard = _function(
        sql,
        "public.system_read_product_research_response_recovery_reservation(",
        "create or replace function\n  public.system_record_product_research_response_recovery_outcome",
    )
    assert "p_payload - 'run_id'" in read_guard
    assert "'get_reserved', reservation_row.id is not null" in read_guard
    assert "'reservation_id', reservation_row.id" in read_guard
    assert "'outcome_recorded', outcome_recorded_value" in read_guard
    assert "provider_response_id" not in read_guard


def test_run_guard_requires_the_recovery_reservation_and_preserves_old_path() -> None:
    sql = _read(MIGRATION).casefold()
    guard = _function(
        sql,
        "content_factory_private.guard_research_run_mutation()",
        "create or replace function\n  public.creator_authorize_product_research_response_recovery",
    )
    for marker in (
        "product_research_response_revalidation",
        "product_research_exact_response_recovery",
        "ordinary_response_revalidation or exact_response_recovery",
        "research_provider_response_recovery_get_reservations",
        "research_provider_response_recovery_authorizations",
        "research_exact_youtube_research_bindings",
        "research_provider_response_bindings",
        "maximum_provider_gets = 1",
        "not reservation.provider_post_allowed",
        "provider_response_invalid",
        "new.project_id is distinct from old.project_id",
        "research_response_recovery_transition_invalid",
    ):
        assert marker in guard


def test_terminal_outcome_is_atomic_with_completion_and_reconcilable() -> None:
    sql = _read(MIGRATION).casefold()
    capture = _function(
        sql,
        "content_factory_private.capture_research_response_recovery_outcome()",
        "create or replace function\n  public.system_claim_product_research_response_recovery",
    )
    assert "old.status <> 'processing'" in capture
    assert "new.status not in ('completed', 'failed')" in capture
    assert "research_provider_response_recovery_get_reservations" in capture
    assert "insert into content_factory.research_provider_response_recovery_outcomes" in capture
    assert "research_response_recovery_outcome_conflict" in capture
    assert re.search(
        r"create trigger capture_research_response_recovery_outcome\s+"
        r"after update on content_factory\.product_research_runs",
        sql,
    )

    outcome = _function(
        sql,
        "public.system_record_product_research_response_recovery_outcome(",
        "revoke all on function\n  public.creator_authorize_product_research_response_recovery",
    )
    assert "p_payload - 'reservation_id'" in outcome
    assert "run_row.status not in ('completed', 'failed')" in outcome
    assert "run_row.completion_hash is null" in outcome
    assert "research_response_recovery_outcome_already_recorded" in outcome
    assert "outcome_row.terminal_status <> run_row.status" in outcome


def test_rpc_privileges_are_exact() -> None:
    sql = _read(MIGRATION).casefold()
    assert re.search(
        r"grant execute on function\s+"
        r"public\.creator_authorize_product_research_response_recovery\(jsonb\)\s+"
        r"to authenticated",
        sql,
    )
    for function_name in (
        "system_claim_product_research_response_recovery",
        "system_read_product_research_response_recovery_reservation",
        "system_record_product_research_response_recovery_outcome",
    ):
        assert re.search(
            rf"grant execute on function\s+public\.{function_name}\(jsonb\)\s+"
            r"to service_role",
            sql,
        )


def test_pgtap_covers_acl_one_get_rollback_atomic_outcome_and_append_only() -> None:
    pgtap = _read(PGTAP).casefold()
    for marker in (
        "viewer cannot authorize saved-response recovery",
        "producer without exact-project membership cannot authorize recovery",
        "without an exact-video binding is ineligible",
        "human authorization is idempotent",
        "service guard reports no reservation without exposing the provider id",
        "a rejected claim rolls back without a get reservation or run transition",
        "a successful claim rolls back its reservation and transition atomically",
        "the first claim returns the saved response id",
        "preserves the single original provider attempt",
        "later requests can detect the reserved get without receiving response inputs",
        "claim replay cannot authorize or reveal inputs for a second provider get",
        "outcome cannot be recorded before authoritative local completion",
        "terminal outcome is server-derived, append-only and idempotent",
        "service guard exposes the atomic terminal receipt without response inputs",
        "recovery authorization cannot be rewritten",
        "one-get reservation cannot be deleted for replay",
        "recorded recovery outcome cannot be rewritten",
        "producer with exact-project acl can reuse",
    ):
        assert marker in pgtap
    assert "session_replication_role = replica" in pgtap
    assert "session_replication_role = origin" in pgtap
    assert pgtap.index("session_replication_role = origin") < pgtap.index(
        "creator_authorize_product_research_response_recovery"
    )
