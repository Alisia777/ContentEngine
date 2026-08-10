from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = (
    MIGRATIONS / "202608100013_content_review_catalog_media_status.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "content_review_catalog_media_status_test.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_catalog_status_wrapper_is_latest_transactional_and_parseable() -> None:
    migration_names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))

    assert MIGRATION.name in migration_names
    assert migration_names.index(MIGRATION.name) > migration_names.index(
        "202608100012_project_member_grant_conflict_fix.sql"
    )
    migration = _read(MIGRATION)
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert parse_sql(migration)
    assert parse_sql(_read(PGTAP))


def test_wrapper_preserves_the_existing_catalog_and_project_acl() -> None:
    migration = _read(MIGRATION)
    repair_contract = _read(
        ROOT / "supabase" / "tests" / "generation_repair_next_action_test.sql"
    )

    assert "creator_content_review_catalog_pre_media_status" in migration
    assert migration.index(
        "creator_content_review_catalog_pre_media_status(\n      p_payload"
    ) < migration.index("from jsonb_array_elements(")
    assert "content_factory_private.require_workspace_project(" in migration
    assert "media.organization_id = organization_id_value" in migration
    assert "media.project_id = project_id_value" in migration
    assert "media.id::text = item.value ->> 'id'" in migration
    assert "media.status = 'ready'" in migration
    assert "creator_content_review_catalog_pre_media_status" in repair_contract
    assert (
        "preserves the privacy-minimized repair action through the status wrapper"
        in repair_contract
    )


def test_media_fields_come_from_the_authoritative_relational_row() -> None:
    migration = _read(MIGRATION)

    enrichment = migration[
        migration.index("item.value || jsonb_build_object(") :
        migration.index("order by item.ordinality")
    ]
    assert "'status', media.status" in enrichment
    assert "'product_id', media.product_id" in enrichment
    assert "metadata" not in enrichment
    assert "'status', 'ready'" not in enrichment


def test_public_and_preserved_function_privileges_stay_narrow() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    assert (
        "content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)\n"
        "  from public, anon, authenticated, service_role;"
    ) in migration
    assert (
        "revoke all on function public.creator_content_review_catalog(jsonb)\n"
        "  from public, anon;"
    ) in migration
    assert (
        "grant execute on function public.creator_content_review_catalog(jsonb)\n"
        "  to authenticated;"
    ) in migration
    assert "workspace_project_access_required" in pgtap
    assert "relational identity, not metadata" in pgtap
    assert "media status is serialized from the authoritative row" in pgtap
