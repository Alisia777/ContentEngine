from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608110007_generation_media_product_identity.sql"
).read_text(encoding="utf-8").lower()
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "generation_media_product_identity_test.sql"
).read_text(encoding="utf-8").lower()


def test_generation_media_product_identity_migration_parses():
    assert parse_sql(MIGRATION)


def test_generation_media_product_identity_pgtap_parses():
    assert parse_sql(PGTAP)


def test_complete_request_still_fails_closed_at_exact_project_boundary():
    visibility_start = MIGRATION.index("-- validate visibility for the complete input")
    projection_start = MIGRATION.index("-- product identity comes only")
    visibility = MIGRATION[visibility_start:projection_start]

    assert "from unnest(requested_media_ids) requested(media_id)" in visibility
    assert "media.organization_id = organization_id" in visibility
    assert "media.project_id = project_id_value" in visibility
    assert "media.status = 'ready'" in visibility
    assert "message = 'project_media_scope_mismatch'" in visibility
    assert "media.metadata ->> 'kind'" not in visibility
    assert "media.artifact_class" not in visibility


def test_only_authoritative_registered_source_photos_receive_identity():
    projection_start = MIGRATION.index("-- product identity comes only")
    projection = MIGRATION[projection_start:]

    assert "product.id = media.product_id" in projection
    assert "product.status = 'active'" in projection
    assert "media.artifact_class = 'source'" in projection
    assert "media.mime_type in ('image/jpeg', 'image/png', 'image/webp')" in projection
    assert "media.metadata ->> 'kind' in ('product_photo', 'packshot')" in projection
    assert "'product_id', product.id" in projection
    assert "'sku', product.sku" in projection
    assert "'product_name', product.title" in projection
    assert "'identity_verified', true" in projection


def test_rights_are_preserved_as_an_independent_paid_readiness_gate():
    assert (
        "media.metadata -> 'rights_confirmed'\n"
        "              is not distinct from 'true'::jsonb"
    ) in MIGRATION
    assert "'rights_confirmed'" in MIGRATION


def test_mixed_visible_catalog_can_return_a_partial_identity_projection():
    assert "resolved_count is distinct from requested_count" not in MIGRATION
    assert "'requested_count', requested_count" in MIGRATION
    assert "'resolved_count', resolved_count" in MIGRATION
    assert "'mixed_catalog_safe', true" in MIGRATION


def test_payload_acl_and_execute_contract_remain_bounded():
    assert "'organization_id', 'project_id', 'media_ids'" in MIGRATION
    assert "jsonb_array_length(p_payload -> 'media_ids') not between 1 and 100" in MIGRATION
    assert "count(distinct requested.media_id)" in MIGRATION
    assert "require_workspace_project_access(" in MIGRATION
    assert "media.owner_id =" not in MIGRATION
    assert (
        "revoke all on function public.creator_generation_media_identity(jsonb)\n"
        "  from public, anon;"
    ) in MIGRATION
    assert (
        "grant execute on function public.creator_generation_media_identity(jsonb)\n"
        "  to authenticated;"
    ) in MIGRATION


def test_no_filename_or_object_key_identity_inference():
    projection_start = MIGRATION.index("-- product identity comes only")
    projection = MIGRATION[projection_start:MIGRATION.index("return jsonb_build_object", projection_start)]

    assert "original_filename" not in projection
    assert "object_name" not in projection
    assert "regexp" not in projection


def test_pgtap_covers_mixed_catalog_and_cross_project_regressions():
    assert "a visible source video no longer suppresses an eligible source photo" in PGTAP
    assert "identity uses the relational product_id instead of metadata" in PGTAP
    assert "an mp4 mislabeled as product_photo never receives image identity" in PGTAP
    assert "a cross-project uuid still fails the complete request closed" in PGTAP
    assert "'project_media_scope_mismatch'" in PGTAP
