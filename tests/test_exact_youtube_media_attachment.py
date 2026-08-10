from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608100010_exact_youtube_media_attachment.sql"
)
REGISTER_MEDIA_MIGRATION = ROOT / "supabase" / "migrations" / (
    "202607130004_creator_rpcs.sql"
)
PROJECT_SCOPE_MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608040005_project_scoped_workflow.sql"
)
CLASSIFICATION_MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608100002_workspace_media_classification_and_folders.sql"
)
PROJECT_ACL_MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608100003_project_team_shared_media_access.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_attachment_migration_parses_and_is_provider_free() -> None:
    source = _read(MIGRATION)
    folded = source.casefold()

    assert parse_sql(source)
    for marker in (
        "content_factory.research_exact_youtube_media_attachments",
        "public.contentengine_attach_exact_youtube_media",
        "exact-youtube-media-attachment-v1",
        "exact-youtube-source-queue-v2",
        "source_hash_snapshot",
        "media_sha256_snapshot",
        "media_matches_registered_source",
        "attachment_hash",
        "source_row_mutated",
        "analysis_started",
        "paid_call_started",
    ):
        assert marker in source
    for forbidden in (
        "net.http",
        "http_post(",
        "api.openai.com",
        "system_begin_research_provider_attempt",
        "system_claim_product_research",
    ):
        assert forbidden not in folded


def test_explicit_postgres_identifiers_fit_the_63_byte_limit() -> None:
    source = _read(MIGRATION)
    patterns = (
        r"create (?:or replace )?function\s+([\w.]+)",
        r"create (?:unique )?index if not exists\s+(\w+)",
        r"create trigger\s+(\w+)",
        r"create table if not exists\s+([\w.]+)",
    )
    names = [
        match.split(".")[-1]
        for pattern in patterns
        for match in re.findall(pattern, source, flags=re.IGNORECASE)
    ]

    assert names
    assert all(len(name.encode("utf-8")) <= 63 for name in names)


def test_attachment_ledger_is_private_append_only_and_one_to_one() -> None:
    source = _read(MIGRATION)
    table = _between(
        source,
        "create table if not exists\n"
        "  content_factory.research_exact_youtube_media_attachments",
        "create index if not exists exact_youtube_media_attachment_project_idx",
    )

    for marker in (
        "unique (organization_id, source_id)",
        "unique (organization_id, media_object_id)",
        "unique (organization_id, idempotency_key)",
        "foreign key (organization_id, source_id)",
        "foreign key (organization_id, media_object_id)",
        "foreign key (organization_id, project_id)",
        "foreign key (organization_id, attached_by)",
        "check (rights_confirmed)",
        "check (\n      media_matches_registered_source\n    )",
        "check (status = 'attached')",
    ):
        assert marker in table
    assert (
        "before insert or update or delete\n"
        "  on content_factory.research_exact_youtube_media_attachments"
    ) in source
    assert "exact_youtube_media_attachment_append_only" in source
    assert "expected_attachment_hash_value := content_factory_private.json_hash(" in source
    assert "exact_youtube_media_attachment_hash_invalid" in source
    assert (
        "revoke all on content_factory.research_exact_youtube_media_attachments\n"
        "  from public, anon, authenticated, service_role"
    ) in source
    assert (
        "grant all on content_factory.research_exact_youtube_media_attachments\n"
        "  to service_role"
    ) in source
    guard = _between(
        source,
        "create or replace function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
        "revoke all on function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
    )
    assert "caller_id_value uuid := auth.uid()" in guard
    assert "if caller_id_value is null" in guard
    assert "service-role request without an authenticated human auth.uid()" in source


def test_attach_rpc_requires_authenticated_exact_project_access() -> None:
    source = _read(MIGRATION)
    attach = _between(
        source,
        "create or replace function public.contentengine_attach_exact_youtube_media(",
        "revoke all on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)",
    )

    for field in (
        "project_id",
        "source_id",
        "media_id",
        "rights_confirmed",
        "media_matches_registered_source",
        "idempotency_key",
    ):
        assert f"'{field}'" in attach
    acl = attach.index(
        "content_factory_private.require_workspace_project_access("
    )
    begin_command = attach.index("content_factory_private.begin_command(")
    source_lookup = attach.index(
        "from content_factory.research_exact_youtube_sources source"
    )
    media_lookup = attach.index("from content_factory.media_objects media")
    insert = attach.index(
        "insert into content_factory.research_exact_youtube_media_attachments"
    )
    assert acl < begin_command < source_lookup < media_lookup < insert
    assert "source.organization_id = organization_id_value" in attach
    assert "source.project_id = project_id_value" in attach
    assert "media.organization_id = organization_id_value" in attach
    assert "media.project_id = project_id_value" in attach
    assert (
        "grant execute on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)\n"
        "  to authenticated;"
    ) in source
    assert "to authenticated, service_role;" not in _between(
        source,
        "revoke all on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)",
        "-- Replace only the queue projection.",
    )


def test_attach_rpc_accepts_only_lawful_registered_source_mp4() -> None:
    source = _read(MIGRATION)
    attach = _between(
        source,
        "create or replace function public.contentengine_attach_exact_youtube_media(",
        "revoke all on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)",
    )
    guard = _between(
        source,
        "create or replace function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
        "revoke all on function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
    )

    for body in (attach, guard):
        for marker in (
            "media.status = 'ready'" if body is guard else "media_row.status <> 'ready'",
            "media.mime_type = 'video/mp4'"
            if body is guard
            else "media_row.mime_type <> 'video/mp4'",
            "metadata ->> 'kind'",
            "'source_video'",
            "metadata -> 'rights_confirmed'",
            "'true'::jsonb",
            "artifact_class",
            "'source'",
            "lifecycle_stage",
            "'sources'",
            "generation_job_id",
            "provider_job_id",
            "generated_from_job_id",
        ):
            assert marker in body
    assert "p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb" in attach
    assert (
        "p_payload -> 'media_matches_registered_source'\n"
        "       is distinct from 'true'::jsonb"
    ) in attach
    assert "exact_youtube_media_attachment_identity_required" in attach
    assert "exact_youtube_media_attachment_media_invalid" in attach


def test_attach_is_naturally_idempotent_with_exact_hash_lineage() -> None:
    source = _read(MIGRATION)
    attach = _between(
        source,
        "create or replace function public.contentengine_attach_exact_youtube_media(",
        "revoke all on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)",
    )

    begin_command = attach.index("content_factory_private.begin_command(")
    locks = attach.index("pg_advisory_xact_lock(", begin_command)
    source_binding = attach.index("into source_binding_row", locks)
    media_binding = attach.index("into media_binding_row", source_binding)
    key_binding = attach.index("into key_binding_row", media_binding)
    insert = attach.index(
        "insert into content_factory.research_exact_youtube_media_attachments",
        key_binding,
    )
    finish = attach.index("content_factory_private.finish_command(", insert)
    assert begin_command < locks < source_binding < media_binding < key_binding < insert < finish
    request_projection = attach.index(
        "request_payload_value := p_payload - 'organization_id' - 'idempotency_key'"
    )
    assert request_projection < begin_command
    assert "p_payload - 'project_id'" not in attach[request_projection:begin_command]
    assert "'source_hash', source_row.source_hash" in attach
    assert "'media_sha256', media_row.sha256" in attach
    assert "attachment_hash_value := content_factory_private.json_hash(" in attach
    assert "source_row.status" in attach
    assert "'derived_status', 'media_attached'" in attach
    assert "'source_row_mutated', false" in attach
    assert "'identity_attestation_recorded', true" in attach


def test_rpc_and_trigger_use_the_same_identity_bound_attachment_hash() -> None:
    source = _read(MIGRATION)
    guard = _between(
        source,
        "create or replace function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
        "revoke all on function\n"
        "  content_factory_private.guard_exact_youtube_media_attachment()",
    )
    attach = _between(
        source,
        "create or replace function public.contentengine_attach_exact_youtube_media(",
        "revoke all on function\n"
        "  public.contentengine_attach_exact_youtube_media(jsonb)",
    )
    guard_hash = _between(
        guard,
        "expected_attachment_hash_value := content_factory_private.json_hash(",
        "  if new.attachment_hash <> expected_attachment_hash_value then",
    )
    attach_hash = _between(
        attach,
        "attachment_hash_value := content_factory_private.json_hash(",
        "  select attachment.* into source_binding_row",
    )

    for hash_body in (guard_hash, attach_hash):
        for field in (
            "'version', 'exact-youtube-media-attachment-v1'",
            "'organization_id'",
            "'project_id'",
            "'source_id'",
            "'source_hash'",
            "'media_id'",
            "'media_sha256'",
            "'media_matches_registered_source', true",
        ):
            assert field in hash_body


def test_queue_derives_attachment_state_without_rewriting_source() -> None:
    source = _read(MIGRATION)
    queue = _between(
        source,
        "create or replace function public.contentengine_exact_youtube_source_queue(",
        "revoke all on function\n"
        "  public.contentengine_exact_youtube_source_queue(jsonb)",
    )

    assert "update content_factory.research_exact_youtube_sources" not in source.casefold()
    assert (
        "left join content_factory.research_exact_youtube_media_attachments attachment"
        in queue
    )
    assert "left join content_factory.media_objects media" in queue
    assert "when attachment.id is null then 'awaiting_media'" in queue
    assert "else 'media_attached'" in queue
    assert "'registered_status', source.status" in queue
    assert "'media_required', attachment.id is null" in queue
    assert "'analysis_ready'" in queue
    assert "media.sha256 = attachment.media_sha256_snapshot" in queue
    for marker in (
        "'attachment'",
        "'media'",
        "'source_hash_snapshot'",
        "'media_sha256_snapshot'",
        "'attachment_hash'",
        "'media_matches_registered_source'",
        "'start_exact_media_analysis'",
        "'attachment_starts_analysis', false",
        "'source_row_mutated', false",
    ):
        assert marker in queue


def test_existing_upload_path_registers_project_scoped_source_video() -> None:
    register = _read(REGISTER_MEDIA_MIGRATION)
    project_scope = _read(PROJECT_SCOPE_MIGRATION)
    classification = _read(CLASSIFICATION_MIGRATION)
    project_acl = _read(PROJECT_ACL_MIGRATION)

    assert "'video/mp4'" in register
    assert "'source_video'" in register
    assert "p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb" in register
    assert "'creator_register_media_pre_project_v47'" in project_scope
    assert (
        "create or replace function public.creator_register_media(" in project_scope
    )
    assert "contentengine.project_id" in project_scope
    assert "guard_media_object_project_lineage" in project_scope
    assert "when 'source_video' then 'source'" in classification
    assert "when 'source' then 'sources'" in classification
    assert "classify_workspace_media" in classification
    assert "result_value, '{media,project_id}'" in project_scope
    assert (
        "content_factory_private.require_workspace_project_access(" in project_acl
    )
    assert "workspace_project_access_allowed(" in project_acl
    assert PROJECT_ACL_MIGRATION.name < MIGRATION.name
