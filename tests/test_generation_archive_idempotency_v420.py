from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608050003_generation_archive_idempotency_hotfix.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_browser_mutation_key_is_accepted_by_the_archive_rpc() -> None:
    assert "'idempotency_key'" in LOWER
    assert "p_payload ? 'idempotency_key'" in LOWER
    assert "generation_batch_archive_payload_invalid" in LOWER
    assert "return this.mutate(" in API[API.index("archiveGenerationBatch(") :]


def test_hotfix_preserves_archive_safety_guards() -> None:
    for token in (
        "batch.project_id = project_id_value",
        "generation_batch_archive_forbidden",
        "generation_batch_archive_active",
        "source_media_preserved",
        "output_media_preserved",
    ):
        assert token in LOWER


def test_hotfix_is_transactional_and_reloads_postgrest() -> None:
    assert SQL.lstrip().casefold().startswith("begin;")
    assert "notify pgrst, 'reload schema'" in LOWER
    assert SQL.rstrip().casefold().endswith("commit;")
