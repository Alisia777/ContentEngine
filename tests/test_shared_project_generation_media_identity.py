from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608100007_shared_project_generation_media_identity.sql"
).read_text(encoding="utf-8").lower()


def test_shared_identity_migration_parses_as_postgresql():
    assert parse_sql(MIGRATION)


def test_identity_reader_uses_exact_project_acl_not_uploader_ownership():
    assert "require_workspace_project_access(" in MIGRATION
    assert "project_id_value,\n    user_id" in MIGRATION
    assert "media.project_id = project_id_value" in MIGRATION
    assert "media.owner_id =" not in MIGRATION
    assert "team_scope" not in MIGRATION
    assert "'shared_project_scope', true" in MIGRATION


def test_cross_project_or_ineligible_media_list_fails_closed():
    assert "from unnest(requested_media_ids) requested(media_id)" in MIGRATION
    assert "message = 'project_media_scope_mismatch'" in MIGRATION
    assert "media.artifact_class = 'source'" in MIGRATION
    assert "media.metadata ->> 'kind' in ('product_photo', 'packshot')" in MIGRATION
    assert MIGRATION.count("product.status = 'active'") >= 2
    assert "resolved_count is distinct from requested_count" in MIGRATION


def test_product_identity_is_preserved_for_recommendation_matching():
    assert "'product_id', product.id" in MIGRATION
    assert "'sku', product.sku" in MIGRATION
    assert "'product_name', product.title" in MIGRATION
    assert "'identity_verified', true" in MIGRATION


def test_verified_certified_project_members_receive_public_execute():
    assert "user_id := content_factory_private.current_profile_id()" in MIGRATION
    assert "content_factory_private.membership_role(" in MIGRATION
    assert "organization_id,\n    true," in MIGRATION
    assert "'operator'" in MIGRATION
    assert MIGRATION.index("membership_role(") < MIGRATION.index(
        "require_workspace_project_access("
    )
    assert (
        "revoke all on function public.creator_generation_media_identity(jsonb)\n"
        "  from public, anon;"
    ) in MIGRATION
    assert (
        "grant execute on function public.creator_generation_media_identity(jsonb)\n"
        "  to authenticated;"
    ) in MIGRATION


def test_payload_is_bounded_and_does_not_restore_owner_shortcuts():
    assert "'organization_id', 'project_id', 'media_ids'" in MIGRATION
    assert "jsonb_array_length(p_payload -> 'media_ids') not between 1 and 100" in MIGRATION
    assert "count(distinct requested.media_id)" in MIGRATION
    assert "media.owner_id =" not in MIGRATION
    assert "team_scope" not in MIGRATION
