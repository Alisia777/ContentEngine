from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170009_generation_storage_health.sql"
)
PGTAP_PATH = (
    ROOT / "supabase" / "tests" / "generation_storage_health_test.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
PGTAP = PGTAP_PATH.read_text(encoding="utf-8")


def _function_body() -> str:
    start = MIGRATION.index(
        "create or replace function public.creator_operational_health("
    )
    end = MIGRATION.index(
        "revoke all on function public.creator_operational_health(jsonb)",
        start,
    )
    return MIGRATION[start:end]


def test_migration_is_ordered_after_prior_slice_and_replaces_only_health_rpc() -> None:
    assert MIGRATION_PATH.name == "202607170009_generation_storage_health.sql"
    assert MIGRATION.startswith("begin;\n")
    assert MIGRATION.rstrip().endswith("commit;")
    assert MIGRATION.count(
        "create or replace function public.creator_operational_health("
    ) == 1
    assert "create table" not in MIGRATION.lower()
    assert "alter table" not in MIGRATION.lower()


def test_existing_health_contract_and_manager_boundary_are_preserved() -> None:
    body = _function_body()
    for marker in (
        "security definer",
        "set search_path = ''",
        "content_factory_private.current_profile_id()",
        "content_factory_private.resolve_organization(p_payload)",
        "array['owner', 'admin']",
        "'ok', true",
        "'organization_id', organization_id_value",
        "'scheduler', jsonb_build_object(",
        "'worker', jsonb_build_object(",
        "'generation', jsonb_build_object(",
        "'content_review', jsonb_build_object(",
    ):
        assert marker in body
    assert (
        "revoke all on function public.creator_operational_health(jsonb)"
        in MIGRATION
    )
    assert "from public, anon;" in MIGRATION
    assert (
        "grant execute on function public.creator_operational_health(jsonb)"
        in MIGRATION
    )
    assert "to authenticated;" in MIGRATION


def test_generation_metrics_keep_legacy_semantics_and_add_wire_shape() -> None:
    body = _function_body()
    for marker in (
        "job.organization_id = organization_id_value",
        "job.mode = 'real'",
        "job.provider = 'runway'",
        "job.status in ('submitted', 'processing')",
        "job.provider_next_poll_at <= now()",
        "job.provider_stalled_at is not null",
        "'active', active_generation_count",
        "'due', due_count",
        "'stalled', stalled_count",
        "'queued', generation_queued_count",
        "'starting', generation_starting_count",
        "'submitted', generation_submitted_count",
        "'processing', generation_processing_count",
        "'oldest_active_age_seconds', generation_oldest_active_age_seconds",
        "'oldest_queued_age_seconds', generation_oldest_queued_age_seconds",
        "'oldest_starting_age_seconds', generation_oldest_starting_age_seconds",
    ):
        assert marker in body
    assert body.count("min(job.created_at) filter (") == 3


def test_storage_metrics_match_authoritative_quota_without_bucket_mutation() -> None:
    body = _function_body()
    for marker in (
        "storage_quota_bytes constant bigint := 107374182400",
        "from content_factory.media_objects media",
        "media.organization_id = organization_id_value",
        "media.status in ('uploading', 'ready', 'archived')",
        "storage_quota_bytes - storage_registered_bytes",
        "storage_registered_bytes::numeric * 100 / storage_quota_bytes",
        "'storage', jsonb_build_object(",
        "'registered_count', storage_registered_count",
        "'registered_bytes', storage_registered_bytes",
        "'quota_bytes', storage_quota_bytes",
        "'remaining_bytes', storage_remaining_bytes",
        "'utilization_percent', storage_utilization_percent",
    ):
        assert marker in body
    assert "storage.objects" not in body
    assert "orphan" not in body.lower()


def test_health_function_is_observation_only() -> None:
    body = _function_body().lower()
    for forbidden in (
        "insert into ",
        "update content_factory.",
        "delete from ",
        "truncate ",
        "provider post",
        "retry_generation",
        "storage.empty_bucket",
        "storage.delete",
    ):
        assert forbidden not in body


def test_pgtap_covers_counts_ages_storage_roles_and_tenant_isolation() -> None:
    for marker in (
        "generation and storage extend rather than replace the health response",
        "queued generation count is organization scoped",
        "legacy active semantics remain submitted plus processing",
        "legacy due semantics remain eligible provider polls",
        "legacy stalled semantics remain durable provider stalls",
        "oldest active age uses the oldest submitted or processing job",
        "registered storage counts only quota-consuming states",
        "registered storage bytes exclude deleted registrations and other tenants",
        "organization storage quota matches the authoritative registration guard",
        "the other owner sees only that tenant generation queue",
        "the other owner sees only that tenant registered storage",
        "an active administrator may inspect organization operational health",
        "an operator cannot inspect organization-wide health",
        "an owner cannot inspect another organization health scope",
        "health reads do not delete or rewrite media registrations",
        "health reads do not retry or replace generation jobs",
    ):
        assert marker in PGTAP


def test_pgtap_plan_matches_static_assertion_count() -> None:
    planned = re.search(r"select plan\((\d+)\);", PGTAP)
    assert planned is not None
    assertions = re.findall(
        r"(?m)^select\s+(?:has_function|ok|is|cmp_ok|throws_ok|lives_ok)\s*\(",
        PGTAP,
    )
    assert int(planned.group(1)) == len(assertions) == 31
