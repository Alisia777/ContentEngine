from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608130008_generation_strategy_spec_mechanics_v1.sql"
)
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608160003_generation_strategy_spec_project_scope_forward.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "generation_strategy_spec_project_scope_forward_test.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _delegated_payload(source: str) -> str:
    start = source.index(
        "result_value := public.creator_prepare_generation_spec("
    )
    end = source.index("  );\n  result_spec :=", start)
    return source[start:end]


def test_forward_migration_parses_and_has_one_guarded_semantic_delta() -> None:
    base = _read(BASE)
    migration = _read(MIGRATION)
    old_fragment = """'organization_id', organization_id_value,
      'idempotency_key',"""
    new_fragment = """'organization_id', organization_id_value,
      'project_id', project_id_value,
      'idempotency_key',"""

    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert len(parse_sql(migration)) >= 6
    assert old_fragment in _delegated_payload(base)
    assert "'project_id', project_id_value" not in _delegated_payload(base)
    assert f"new_fragment constant text := $new${new_fragment}$new$;" in migration
    assert "old_pattern constant text :=" in migration
    assert "organization_id_value' ||" in migration
    assert "''idempotency_key''[[:space:]]*," in migration
    assert migration.count("'project_id', project_id_value") == 1
    assert migration.count("execute patched_definition;") == 1
    assert "generation_strategy_spec_project_scope_target_invalid" in migration
    assert "generation_strategy_spec_project_scope_patch_invalid" in migration
    assert "position(new_fragment in function_definition) <> 0" in migration
    assert "regexp_count(function_definition, old_pattern) <> 1" in migration
    assert "regexp_count(patched_definition, old_pattern) <> 0" in migration
    assert "notify pgrst, 'reload schema';" in migration


def test_forward_migration_preserves_rpc_acl_and_cannot_add_paid_authority() -> None:
    migration = _read(MIGRATION)
    lowered = migration.lower()

    assert (
        "revoke all on function\n"
        "  public.creator_prepare_generation_strategy_spec(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in migration
    assert (
        "grant execute on function\n"
        "  public.creator_prepare_generation_strategy_spec(jsonb)\n"
        "  to authenticated"
    ) in migration
    for forbidden in (
        "create table",
        "alter table",
        "insert into",
        "update content_factory",
        "delete from",
        "net.http",
        "http_post",
        "allow_real_spend",
        "generation_strategy_start_claims",
        "generation_strategy_dispatch_attempts",
        "spend_ledger",
    ):
        assert forbidden not in lowered


def test_pgtap_exercises_browser_project_scope_replay_and_tenant_failures() -> None:
    pgtap = _read(PGTAP)

    assert pgtap.startswith("begin;\n")
    assert pgtap.rstrip().endswith("rollback;")
    assert len(parse_sql(pgtap)) >= 20
    assert "set local role authenticated;" in pgtap
    assert "generation-strategy-spec-prepare-request-v1" in pgtap
    assert "'project_id', 'cc120000-0000-4000-8000-000000000001'" in pgtap
    assert pgtap.count("public.creator_prepare_generation_strategy_spec(") >= 5
    assert "same project-scoped idempotency key replays an unchanged response" in pgtap
    assert "browser wrapper rejects a missing project" in pgtap
    assert "browser wrapper rejects an unknown project" in pgtap
    assert "browser wrapper rejects a project from another tenant" in pgtap
    assert "success and replay create one immutable exact-scope spec version" in pgtap
    for paid_table in (
        "generation_strategy_start_claims",
        "generation_strategy_dispatch_attempts",
        "generation_strategy_dispatch_results",
        "generation_spend_ledger",
    ):
        assert paid_table in pgtap
    assert "free prepare and replay create no paid claim, dispatch or spend row" in pgtap
