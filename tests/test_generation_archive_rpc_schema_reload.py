from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607240005_reload_generation_archive_rpc_schema.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_archive_rpc_reasserts_volatile_contract_before_schema_reload() -> None:
    assert "alter function public.creator_generation_archive(jsonb) volatile" in LOWER


def test_postgrest_schema_cache_is_reloaded_after_volatility_change() -> None:
    alter_position = LOWER.index(
        "alter function public.creator_generation_archive(jsonb) volatile"
    )
    reload_position = LOWER.index("notify pgrst, 'reload schema'")

    assert alter_position < reload_position
