from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608200005_generation_strategy_fal_result_recovery_v1.sql"
PGTAP = ROOT / "supabase/tests/generation_strategy_fal_result_recovery_test.sql"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_migration_and_pgtap_are_valid_postgresql_and_append_only_files() -> None:
    migration = _source(MIGRATION)
    pgtap = _source(PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert pgtap.startswith("begin;\n")
    assert pgtap.rstrip().endswith("rollback;")
    assert len(list((ROOT / "supabase/migrations").glob("202608200005_*.sql"))) == 1


def test_rpc_has_exact_edge_request_and_response_contract() -> None:
    source = _source(MIGRATION)

    assert "public.system_recover_generation_strategy_provider_result(" in source
    assert "input_payload jsonb default '{}'::jsonb" in source
    assert "generation-strategy-provider-result-recovery-request-v1" in source
    assert "FAL_RESULT_HTTP_405_RECOVERY_VERIFIED" in source
    assert (
        "'strategy-result-recovery:' || generation_job_id_value::text || ':' ||"
        in source
    )
    assert "generation-strategy-provider-result-recovery-response-v1" in source
    for exact_response_fact in (
        "'provider_post_retried', false",
        "'ledger_mutated', false",
        "'manual_human_review_required', true",
        "'previous_status', 'failed'",
        "'provider_status', 'succeeded'",
        "'mime_type', 'video/mp4'",
    ):
        assert exact_response_fact in source

    request_keys = {
        "version",
        "organization_id",
        "project_id",
        "actor_id",
        "generation_job_id",
        "provider_task_id",
        "output",
        "provider_evidence_hash",
        "confirmation",
        "idempotency_key",
    }
    validation_prefix = source.split(
        "organization_id_value := content_factory_private.require_uuid", 1
    )[0]
    for key in request_keys:
        assert f"'{key}'" in validation_prefix
    assert "'failed_event_id'" not in validation_prefix


def test_recovery_fails_closed_to_the_single_paid_fal_405_case() -> None:
    source = _source(MIGRATION)

    required_guards = (
        "receipt_row.provider is distinct from 'fal'",
        "receipt_row.strategy_id is distinct from 'viral_product_swap'",
        "receipt_row.recipe is distinct from 'product_swap'",
        "dispatch_row.outcome is distinct from 'submitted'",
        "dispatch_row.provider_post_started is distinct from true",
        "dispatch_row.provider_task_id is distinct from provider_task_id_value",
        "job_row.provider is distinct from 'fal'",
        "job_row.status is distinct from 'failed'",
        "job_row.actual_cost_minor is distinct from job_row.estimated_cost_minor",
        "(job_row.output ->> 'provider_billing_outcome') is distinct from",
        "latest_event_row.provider_status is distinct from 'failed'",
        "latest_event_row.failure_code is distinct from",
        "task_row.status is distinct from 'cancelled'",
        "generation_strategy_dispatch_reconciliations",
    )
    for guard in required_guards:
        assert guard in source

    constraint = source.split(
        "add constraint generation_strategy_provider_status_transition_v2_check", 1
    )[1].split("create or replace function", 1)[0]
    assert "previous_status = 'failed'" in constraint
    assert "provider_status = 'succeeded'" in constraint
    assert "is not distinct from" in constraint
    assert "strategy-result-recovery:%" in constraint
    assert "provider_result_http_405" in constraint


def test_provider_history_is_corrected_by_insert_never_rewritten() -> None:
    source = _source(MIGRATION).casefold()
    function_body = source.split("as $$", 1)[1].split("\nend;\n$$;", 1)[0]

    assert (
        function_body.count(
            "insert into content_factory.generation_strategy_provider_status_events"
        )
        == 1
    )
    assert "update content_factory.generation_strategy_provider_status_events" not in function_body
    assert "delete from content_factory.generation_strategy_provider_status_events" not in function_body
    assert "recovered_from_event_id" in function_body
    assert "next_transition_ordinal_value := latest_event_row.transition_ordinal + 1" in function_body


def test_recovery_never_writes_spend_or_dispatch_and_proves_ledger_unchanged() -> None:
    source = _source(MIGRATION).casefold()
    function_body = source.split("as $$", 1)[1].split("\nend;\n$$;", 1)[0]

    for forbidden_dml in (
        "insert into content_factory.generation_spend_ledger",
        "update content_factory.generation_spend_ledger",
        "delete from content_factory.generation_spend_ledger",
        "insert into content_factory.generation_strategy_dispatch_attempts",
        "insert into content_factory.generation_strategy_dispatch_results",
    ):
        assert forbidden_dml not in function_body

    assert "ledger.event_type = 'reserved'" in function_body
    assert "ledger.event_type = 'settled'" in function_body
    assert "ledger.event_type = 'frozen'" in function_body
    assert "ledger_hash_before_value" in function_body
    assert (
        "ledger_hash_after_value is distinct from ledger_hash_before_value"
        in function_body
    )
    assert "generation_strategy_provider_result_recovery_ledger_changed" in function_body
    for network_primitive in ("http_post", "net.http", "pg_net", "fetch("):
        assert network_primitive not in function_body


def test_exact_uploaded_mp4_and_all_success_projections_are_atomic() -> None:
    source = _source(MIGRATION)

    for storage_guard in (
        "from storage.objects storage_object",
        "storage_object.bucket_id = 'contentengine-private'",
        "storage_size_value is distinct from size_bytes_value",
        "storage_mime_type_value is distinct from 'video/mp4'",
        "storage_sha256_value is distinct from sha256_value",
        "for update;",
    ):
        assert storage_guard in source

    assert "insert into content_factory.media_objects" in source
    assert "'provider', 'fal'" in source
    assert "'kind', 'generated_video'" in source
    assert "update content_factory.generation_jobs job" in source
    assert "update content_factory.generation_batches batch" in source
    assert "update content_factory.creator_tasks task" in source
    assert "task.result - array[" in source
    for stale_failure_key in (
        "'failure_code'",
        "'provider_failure_code'",
        "'provider_billing_outcome'",
        "'failed_at'",
        "'error_code'",
        "'error_message'",
    ):
        assert stale_failure_key in source
    assert "'review_mode', 'manual_human_review'" in source


def test_json_null_and_missing_critical_facts_are_rejected_not_unknown() -> None:
    source = _source(MIGRATION)

    null_safe_guards = (
        "(input_payload ->> 'version') is distinct from",
        "(input_payload ->> 'confirmation') is distinct from",
        "provider_evidence_hash_value is null",
        "idempotency_key_value is distinct from",
        "mime_type_value is distinct from 'video/mp4'",
        "sha256_value is null",
        "(event_row.output_snapshot ->> 'recovery_version') is distinct from",
        "(job_row.input ->> 'provider') is distinct from 'fal'",
        "(job_row.output ->> 'failure_code') is distinct from",
        "(job_row.output ->> 'provider_billing_outcome') is distinct from",
        "(task_row.result ->> 'failure_code') is distinct from",
        "latest_event_row.failure_code is distinct from",
        "storage_mime_type_value is distinct from 'video/mp4'",
        "storage_sha256_value is distinct from sha256_value",
        "(media_row.metadata ->> 'provider') is distinct from 'fal'",
        "(ledger.metadata ->> 'provider_task_id') is distinct from",
    )
    for guard in null_safe_guards:
        assert guard in source

    transition = source.split(
        "add constraint generation_strategy_provider_status_transition_v2_check", 1
    )[1].split("create or replace function", 1)[0]
    assert (
        "(output_snapshot ->> 'recovery_version') is not distinct from"
        in transition
    )
    assert (
        "(output_snapshot ->> 'recovered_failure_code') is not distinct from"
        in transition
    )


def test_rpc_is_service_role_only_and_identifiers_fit_postgres() -> None:
    source = _source(MIGRATION)

    assert re.search(
        r"revoke all on function\s+public\.system_recover_generation_strategy_provider_result\(jsonb\)\s+from public, anon, authenticated, service_role;",
        source,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant execute on function\s+public\.system_recover_generation_strategy_provider_result\(jsonb\)\s+to service_role;",
        source,
        flags=re.IGNORECASE,
    )
    explicit_identifiers = (
        "system_recover_generation_strategy_provider_result",
        "generation_strategy_provider_status_transition_v2_check",
    )
    assert all(len(identifier.encode("utf-8")) <= 63 for identifier in explicit_identifiers)


def test_pgtap_covers_authority_append_only_storage_money_and_projection_contracts() -> None:
    pgtap = _source(PGTAP)

    for contract in (
        "system_recover_generation_strategy_provider_result",
        "service-role only",
        "provider_result_http_405",
        "pre-uploaded MP4",
        "generation_spend_ledger",
        "correction is append-only",
        "generation_jobs",
        "generation_batches",
        "creator_tasks",
        "provider_post_retried",
        "ledger_mutated",
        "manual_human_review_required",
        "JSON null request version is rejected",
        "missing output sha256 is rejected",
        "JSON null output MIME type is rejected",
    ):
        assert contract in pgtap
