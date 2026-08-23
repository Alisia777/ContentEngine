from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608200007_generation_media_kind_mime_contract_v1.sql"
)
PGTAP = ROOT / "supabase/tests/generation_media_kind_mime_contract_test.sql"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_append_only_migration_and_pgtap_are_valid_postgresql() -> None:
    migration = _text(MIGRATION)
    pgtap = _text(PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert pgtap.startswith("begin;\n")
    assert pgtap.rstrip().endswith("rollback;")
    assert len(list((ROOT / "supabase/migrations").glob("202608200007_*.sql"))) == 1


def test_registration_boundary_enforces_the_exact_kind_mime_matrix() -> None:
    migration = _text(MIGRATION).casefold()

    assert "'product_photo', 'packshot', 'creator_reference'" in migration
    assert "'image/jpeg', 'image/png', 'image/webp'" in migration
    assert "kind_value = 'source_video'" in migration
    assert "mime_value <> 'video/mp4'" in migration
    assert migration.count("message = 'media_kind_mime_mismatch'") == 2
    assert "image_material_requires_image_mime" in migration
    assert "source_video_requires_video_mp4" in migration


def test_registration_boundary_is_null_safe_and_preserves_validation_layers() -> None:
    migration = _text(MIGRATION).casefold()

    assert "coalesce(p_payload ->> 'kind', '')" in migration
    assert "coalesce(p_payload ->> 'mime_type', '')" in migration
    assert "creator_register_media_pre_project_v47" in migration
    assert "call_project_scoped_v47" in migration
    assert "security definer" in migration
    assert "set search_path = ''" in migration
    assert "grant execute on function public.creator_register_media(jsonb)" in migration
    assert "to authenticated" in migration
    assert "from public, anon" in migration


def test_migration_does_not_rewrite_or_delete_existing_media() -> None:
    migration = _text(MIGRATION).casefold()

    for forbidden in (
        "update content_factory.media_objects",
        "delete from content_factory.media_objects",
        "alter table content_factory.media_objects",
        "insert into content_factory.media_objects",
        "update storage.objects",
        "delete from storage.objects",
    ):
        assert forbidden not in migration

    assert "existing rows are deliberately neither" in migration
    assert "rewritten nor deleted" in migration


def test_pgtap_covers_rejections_acceptance_and_legacy_rows() -> None:
    pgtap = _text(PGTAP)

    assert "video/mp4 cannot be registered as product_photo" in pgtap
    assert "image/webp cannot be registered as source_video" in pgtap
    assert "JSON null MIME fails closed" in pgtap
    assert "missing MIME fails closed for source_video" in pgtap
    assert "rejected MIME-kind pairs create no media rows" in pgtap

    for accepted in (
        "image/webp remains valid for product_photo",
        "image/png remains valid for packshot",
        "image/jpeg remains valid for creator_reference",
        "video/mp4 remains valid for source_video",
    ):
        assert accepted in pgtap

    assert "legacy mismatched rows remain representable and untouched" in pgtap
    assert "creator_register_media_pre_project_v47" in pgtap
