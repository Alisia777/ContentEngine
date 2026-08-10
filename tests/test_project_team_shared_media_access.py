"""Contracts for explicit project membership and shared private media reads."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
PREVIOUS = MIGRATIONS / "202608100002_workspace_media_classification_and_folders.sql"
MIGRATION = MIGRATIONS / "202608100003_project_team_shared_media_access.sql"
GRANT_CONFLICT_FIX = (
    MIGRATIONS / "202608100012_project_member_grant_conflict_fix.sql"
)
WORKSPACE_PGTAP = ROOT / "supabase/tests/workspace_folders_test.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(source: str) -> str:
    return re.sub(r"\s+", " ", source.lower()).strip()


def _function(source: str, schema: str, name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(schema)}\."
        rf"{re.escape(name)}\s*\([\s\S]*?\n\$\$;",
        source,
        flags=re.IGNORECASE,
    )
    assert match, f"missing {schema}.{name}"
    return _normalized(match.group(0))


def test_acl_is_one_ordered_parseable_migration() -> None:
    versions = [path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql")]
    source = _read(MIGRATION)
    normalized = _normalized(source)

    assert PREVIOUS.is_file()
    assert MIGRATION.is_file()
    assert PREVIOUS.name < MIGRATION.name
    assert versions.count("202608100003") == 1
    parse_sql(source)
    assert normalized.startswith("begin;")
    assert normalized.endswith("commit;")
    assert "notify pgrst, 'reload schema';" in normalized
    assert not re.search(r"\bowner\s+to\b", normalized)


def test_private_aliases_fit_postgresql_identifier_limit() -> None:
    source = _normalized(_read(MIGRATION))
    aliases = (
        "contentengine_generation_research_recommendations_pre_acl_v423",
        "contentengine_bind_generation_spec_ai_research_pre_project_acl",
        "contentengine_generation_spec_ai_research_binding_pre_acl_v423",
    )

    for alias in aliases:
        assert len(alias.encode("utf-8")) <= 63
        assert alias in source

    assert (
        "contentengine_generation_research_recommendations_pre_project_acl"
        not in source
    )
    assert (
        "contentengine_generation_spec_ai_research_binding_pre_project_acl"
        not in source
    )


def test_project_acl_table_is_fail_closed_and_exact_project_scoped() -> None:
    source = _normalized(_read(MIGRATION))

    assert "create table if not exists content_factory.workspace_project_memberships" in source
    assert "primary key (organization_id, project_id, profile_id)" in source
    assert (
        "foreign key (organization_id, project_id) references "
        "content_factory.workspace_folders(organization_id, id)"
    ) in source
    assert (
        "foreign key (organization_id, profile_id) references "
        "content_factory.memberships(organization_id, profile_id)"
    ) in source
    assert (
        "alter table content_factory.workspace_project_memberships "
        "enable row level security"
    ) in source
    assert (
        "revoke all on content_factory.workspace_project_memberships "
        "from public, anon, authenticated"
    ) in source
    assert "grant select on content_factory.workspace_project_memberships to authenticated" not in source
    assert "workspace_project_membership_project_invalid" in source
    assert "workspace_project_member_not_operational" in source


def test_backfill_preserves_admins_creators_and_real_contributors_only() -> None:
    source = _normalized(_read(MIGRATION))

    assert "membership.role in ('owner', 'admin')" in source
    assert "membership.profile_id = project.created_by" in source
    assert "with existing_contributors as" in source
    for contributor in (
        "media.owner_id",
        "task.assignee_id",
        "task.created_by",
        "batch.created_by",
        "job.requested_by",
        "job.assigned_to",
        "review.requested_by",
        "research.created_by",
        "draft.created_by",
        "placement.assigned_to",
        "placement.created_by",
    ):
        assert contributor in source
    assert "membership.status = 'active'" in source
    assert "profile.status = 'active'" in source
    assert "seed_workspace_project_memberships" in source
    assert "or membership.profile_id = new.created_by" in source
    assert re.search(
        r"membership\.role in \( ?'owner', 'admin', 'producer', "
        r"'reviewer', 'operator' ?\)",
        source,
    )


def test_runtime_workspace_fixture_grants_exact_project_collaborators() -> None:
    source = _read(WORKSPACE_PGTAP)
    normalized = _normalized(source)

    parse_sql(source)
    assert "insert into content_factory.workspace_project_memberships" in normalized
    for profile_id in (
        "94000000-0000-4000-8000-000000000002",
        "94000000-0000-4000-8000-000000000003",
    ):
        assert profile_id in normalized
    assert normalized.count("94400000-0000-4000-8000-000000000100") >= 2


def test_membership_management_is_owner_admin_only_and_audited() -> None:
    source = _read(MIGRATION)

    for name in (
        "creator_project_members",
        "creator_grant_project_member",
        "creator_revoke_project_member",
    ):
        function = _function(source, "public", name)
        assert "security definer set search_path = ''" in function
        assert "array['owner', 'admin']" in function
        assert "content_factory_private.require_workspace_project(" in function
        assert f"grant execute on function public.{name}(jsonb) to authenticated" in _normalized(source)

    grant = _function(source, "public", "creator_grant_project_member")
    revoke = _function(source, "public", "creator_revoke_project_member")
    assert "project_member_target_not_operational" in grant
    assert "content_factory_private.begin_command(" in grant
    assert "content_factory_private.finish_command(" in grant
    assert "workspace_project_member_granted" in grant
    assert "project_member_is_protected" in revoke
    assert "target_role in ('owner', 'admin')" in revoke
    assert "target_profile_id = project_creator_id" in revoke
    assert "workspace_project_member_revoked" in revoke


def test_project_member_grant_names_the_primary_key_conflict_arbiter() -> None:
    source = _read(GRANT_CONFLICT_FIX)
    normalized = _normalized(source)

    parse_sql(source)
    assert normalized.startswith("begin;")
    assert normalized.endswith("commit;")
    grant = _function(source, "public", "creator_grant_project_member")
    assert (
        "on conflict on constraint workspace_project_memberships_pkey "
        "do update"
    ) in grant
    assert "on conflict (organization_id, project_id, profile_id)" not in grant
    assert "#variable_conflict use_variable" in grant
    assert (
        "grant execute on function public.creator_grant_project_member(jsonb) "
        "to authenticated"
    ) in normalized


def test_project_catalog_and_readers_require_explicit_project_access() -> None:
    source = _read(MIGRATION)
    required = "content_factory_private.require_workspace_project_access("

    access = _function(
        source,
        "content_factory_private",
        "workspace_project_access_allowed",
    )
    assert "project_member.project_id = p_project_id" in access
    assert "project_member.profile_id = p_profile_id" in access
    assert "project_member.status = 'active'" in access
    assert "organization_member.status = 'active'" in access
    assert "project.status = 'active'" in access

    for name in (
        "creator_project_flow",
        "creator_project_media",
        "creator_workspace_browser",
        "creator_workspace_section",
    ):
        function = _function(source, "public", name)
        assert required in function

    catalog = _function(source, "public", "creator_project_flow")
    assert "join content_factory.workspace_project_memberships project_member" in catalog
    assert "project_member.profile_id = user_id" in catalog
    assert "project_member.status = 'active'" in catalog
    assert "when actor_role = 'operator' then 'reviewer'" in catalog


def test_legacy_project_writes_and_paid_generation_share_the_acl_gateway() -> None:
    source = _read(MIGRATION)
    gateway = _function(
        source,
        "content_factory_private",
        "require_workspace_project",
    )

    assert "caller_id uuid := auth.uid()" in gateway
    assert "workspace_project_access_allowed(" in gateway
    assert "workspace_project_access_required" in gateway
    assert "coalesce(auth.role(), '') <> 'service_role'" in gateway
    assert gateway.index("project.status = 'active'") < gateway.index(
        "workspace_project_access_allowed("
    )

    # These browser commands already call require_workspace_project through
    # their preserved project-scoped gateway/spec functions. Replacing the
    # shared helper therefore closes both free writes and the paid start before
    # a job, outbox row, or provider call can be created.
    legacy = _read(
        ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
    )
    scoped = _function(
        legacy,
        "content_factory_private",
        "call_project_scoped_v47",
    )
    assert "content_factory_private.require_workspace_project(" in scoped
    assert "'creator_start_real_generation_pre_project_v47'" in scoped

    spec_source = _read(
        ROOT
        / "supabase/migrations/202608040014_generation_spec_project_boundaries.sql"
    )
    for name in (
        "creator_prepare_generation_spec",
        "creator_generation_spec_status",
        "creator_control_generation_spec",
    ):
        assert "content_factory_private.require_workspace_project(" in _function(
            spec_source,
            "public",
            name,
        )


def test_ai_recommendation_and_spec_binding_cannot_bypass_project_acl() -> None:
    source = _read(MIGRATION)
    normalized = _normalized(source)
    required = "content_factory_private.require_workspace_project_access("

    for name in (
        "contentengine_generation_research_recommendations",
        "contentengine_bind_generation_spec_ai_research",
        "contentengine_generation_spec_ai_research_binding",
    ):
        function = _function(source, "public", name)
        assert required in function
        assert "security definer set search_path = ''" in function
        assert f"grant execute on function public.{name}(jsonb)" in normalized

    assert (
        "contentengine_generation_research_recommendations_pre_acl_v423"
        in normalized
    )
    assert (
        "contentengine_bind_generation_spec_ai_research_pre_project_acl"
        in normalized
    )
    assert (
        "contentengine_generation_spec_ai_research_binding_pre_acl_v423"
        in normalized
    )

    guard = _function(
        source,
        "content_factory_private",
        "guard_generation_spec_ai_research_project_access",
    )
    assert "before insert on content_factory.generation_spec_ai_research_bindings" in normalized
    assert "new.applied_by is distinct from auth.uid()" in guard
    assert "workspace_project_access_allowed(" in guard
    assert "generation_spec_ai_research_project_access_required" in guard


def test_shared_finder_returns_project_team_data_not_only_caller_owned_rows() -> None:
    source = _read(MIGRATION)
    finder = _function(source, "public", "creator_workspace_browser")
    media = _function(source, "public", "creator_workspace_section")
    exact = _function(source, "public", "creator_project_media")

    assert "media.project_id = project_id_value" in finder
    assert "task.project_id = project_id_value" in finder
    assert "media.owner_id = user_id" not in finder
    assert "task.assignee_id = user_id" not in finder
    assert "'shared_project_read', true" in finder
    assert "workspace_folder_scope_matches( p_payload, location.folder_id )" in finder
    assert "workspace_media_kind_supported(" in finder
    assert "candidate.project_id = project_id_value" in media
    assert "candidate.owner_id = user_id" not in media
    assert media.index("require_workspace_project_access(") < media.index(
        "creator_workspace_section_pre_project_reader_recovery_v416"
    )
    assert "media.owner_id = user_id" not in exact
    assert "'artifact_class', media.artifact_class" in finder
    assert "'lifecycle_stage', media.lifecycle_stage" in finder


def test_storage_select_matches_project_acl_without_widening_writes() -> None:
    source = _read(MIGRATION)
    normalized = _normalized(source)
    storage = _function(
        source,
        "content_factory",
        "storage_project_read_allowed",
    )

    assert "p_bucket_id = 'contentengine-private'" in storage
    assert "content_factory.storage_access_allowed(" in storage
    assert "auth.uid()::text, false" in storage
    assert "media.bucket_id = p_bucket_id" in storage
    assert "media.object_name = p_object_name" in storage
    assert "media.project_id is not null" in storage
    assert "media.status <> 'deleted'" in storage
    assert "content_factory_private.workspace_project_access_allowed(" in storage
    assert "split_part(p_object_name, '/', 2) = auth.uid()::text" in storage
    assert "drop policy if exists contentengine_private_select" in normalized
    assert "content_factory.storage_project_read_allowed( storage.objects.bucket_id, storage.objects.name )" in normalized

    # Upload, replacement, and deletion ownership are intentionally untouched.
    assert "create policy contentengine_private_insert" not in normalized
    assert "create policy contentengine_private_update" not in normalized
    assert "create policy contentengine_private_delete" not in normalized
    assert "for insert" not in normalized
    assert "for update" not in normalized
    assert "for delete" not in normalized
