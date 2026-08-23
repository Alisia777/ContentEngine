from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608150001_generation_direct_mp4_source_v1.sql"
)
PGTAP = ROOT / "supabase" / "tests" / (
    "generation_direct_mp4_attachment_v1_test.sql"
)
INTAKE = ROOT / "web" / "app" / "generation-strategy-intake-v4.js"
CREATOR_GENERATE = ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_at = source.index(start)
    return source[start_at : source.index(end, start_at)]


def test_migration_and_pgtap_parse() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert parse_sql(migration)
    assert parse_sql(pgtap)


def test_direct_attachment_is_a_separate_private_append_only_ledger() -> None:
    source = _read(MIGRATION)
    table = _between(
        source,
        "create table content_factory.generation_direct_mp4_attachments",
        "create index generation_direct_mp4_attachment_project_idx",
    )

    assert "inherits (content_factory.research_exact_youtube_media_attachments)" in table
    assert "source_kind = 'direct_mp4'" in table
    assert "generation_direct_mp4_attachment_media_uq" in table
    assert "generation_direct_mp4_attachment_command_uq" in table
    assert "generation_direct_mp4_attachment_hash_uq" in table
    assert "generation_direct_mp4_attachment_media_fk" in table
    assert "generation_direct_mp4_attachment_project_fk" in table
    assert "generation_direct_mp4_attachment_actor_fk" in table
    assert (
        "before insert or update or delete\n"
        "  on content_factory.generation_direct_mp4_attachments"
    ) in source
    assert "generation_direct_mp4_attachment_append_only" in source
    assert (
        "revoke all on content_factory.generation_direct_mp4_attachments\n"
        "  from public, anon, authenticated, service_role"
    ) in source


def test_rpc_is_actor_project_storage_and_byte_scoped() -> None:
    source = _read(MIGRATION)
    rpc = _between(
        source,
        "create or replace function public.contentengine_attach_generation_direct_mp4(",
        "revoke all on function\n"
        "  public.contentengine_attach_generation_direct_mp4(jsonb)",
    )

    for marker in (
        "current_profile_id()",
        "resolve_organization(p_payload)",
        "require_workspace_project_access(",
        "media.project_id = project_id_value",
        "media.owner_id = actor_id_value",
        "media.bucket_id = 'contentengine-private'",
        "split_part(media.object_name, '/', 1) = organization_id_value::text",
        "split_part(media.object_name, '/', 2) = actor_id_value::text",
        "media.mime_type = 'video/mp4'",
        "media.sha256 ~ '^[0-9a-f]{64}$'",
        "media.metadata ->> 'kind' = 'source_video'",
        "media.metadata -> 'rights_confirmed' = 'true'::jsonb",
        "media.artifact_class = 'source'",
        "media.lifecycle_stage = 'sources'",
        "storage_object.metadata ->> 'size' = media.size_bytes::text",
        "storage_object.metadata ->> 'mimetype'",
    ):
        assert marker in rpc


def test_rpc_is_idempotent_hashed_and_does_not_fabricate_social_source() -> None:
    source = _read(MIGRATION)
    rpc = _between(
        source,
        "create or replace function public.contentengine_attach_generation_direct_mp4(",
        "revoke all on function\n"
        "  public.contentengine_attach_generation_direct_mp4(jsonb)",
    )

    assert "begin_command(" in rpc
    assert "finish_command(" in rpc
    assert "generation-direct-mp4-source-v1" in rpc
    assert "generation-direct-mp4-attachment-v1" in rpc
    assert "source_id, media_object_id" in rpc
    assert "attachment_id_value, media_row.id" in rpc
    assert "insert into content_factory.generation_direct_mp4_attachments" in rpc
    assert "insert into content_factory.research_exact_youtube_sources" not in source
    assert "insert into content_factory.research_exact_youtube_media_attachments" not in source
    assert "'youtube_source_created', false" in rpc
    assert "'social_url_required', false" in rpc


def test_attachment_does_not_create_a_paid_or_provider_authority() -> None:
    source = _read(MIGRATION).casefold()
    rpc = _between(
        source,
        "create or replace function public.contentengine_attach_generation_direct_mp4(",
        "revoke all on function\n"
        "  public.contentengine_attach_generation_direct_mp4(jsonb)",
    )

    for forbidden in (
        "net.http",
        "http_post(",
        "api.runway",
        "generation_spend_ledger",
        "generation_strategy_start_claims",
        "generation_strategy_dispatch_attempts",
        "creator_start_real_generation",
    ):
        assert forbidden not in rpc
    for marker in (
        "'analysis_started', false",
        "'provider_call_started', false",
        "'paid_call_started', false",
        "'budget_reserved', false",
    ):
        assert marker in rpc


def test_existing_server_probe_and_creator_generate_remain_the_execution_path() -> None:
    migration = _read(MIGRATION)
    creator_generate = _read(CREATOR_GENERATE)

    assert "generation_strategy_media_durations" in migration
    assert "guard_generation_strategy_duration_attachment" in migration
    assert "system_generation_strategy_media_probe_context" in creator_generate
    assert "system_record_generation_strategy_media_duration" in creator_generate
    assert "checkRunwayStrategyReadiness" in creator_generate
    assert "system_claim_generation_strategy_start" in creator_generate
    assert "system_mark_generation_strategy_dispatch_attempt" in creator_generate
    assert "create or replace function public.creator_generate" not in migration.casefold()
    assert "generation_strategy_start_claims" not in _between(
        migration.casefold(),
        "create or replace function public.contentengine_attach_generation_direct_mp4(",
        "revoke all on function\n"
        "  public.contentengine_attach_generation_direct_mp4(jsonb)",
    )


def test_candidate_wrapper_reports_direct_provenance_without_youtube_label() -> None:
    source = _read(MIGRATION)
    wrapper = _between(
        source,
        "create or replace function public.creator_generation_strategy_asset_candidates(",
        "revoke all on function\n"
        "  public.creator_generation_strategy_asset_candidates(jsonb)",
    )

    assert "creator_generation_strategy_asset_candidates_pre_direct_mp4_v1" in wrapper
    assert "from content_factory.generation_direct_mp4_attachments direct" in wrapper
    assert "from only content_factory.research_exact_youtube_media_attachments exact" in wrapper
    assert "'exact_youtube_attached'" in wrapper
    assert "'direct_mp4_attached'" in wrapper
    assert "'source_attachment_kind'" in wrapper
    assert "'direct_mp4_supported', true" in wrapper
    assert "'social_url_required_for_direct_mp4', false" in wrapper


def test_browser_and_rpc_response_contract_match_exactly() -> None:
    migration = _read(MIGRATION)
    intake = _read(INTAKE)

    assert '"contentengine_attach_generation_direct_mp4"' in intake
    assert 'root?.version !== "generation-direct-mp4-attachment-v1"' in intake
    assert "'version', 'generation-direct-mp4-attachment-v1'" in migration
    assert "'registered_media_reused', true" in migration
    assert "'provider_call_started', false" in migration
    assert "'paid_call_started', false" in migration


def test_explicit_postgres_identifiers_fit_the_63_byte_limit() -> None:
    source = _read(MIGRATION)
    patterns = (
        r"create (?:or replace )?function\s+([\w.]+)",
        r"create (?:unique )?index\s+([\w.]+)",
        r"create trigger\s+([\w.]+)",
        r"create table\s+([\w.]+)",
        r"add constraint\s+([\w.]+)",
    )
    names = [
        match.split(".")[-1]
        for pattern in patterns
        for match in re.findall(pattern, source, flags=re.IGNORECASE)
    ]

    assert names
    assert all(len(name.encode("utf-8")) <= 63 for name in names)
