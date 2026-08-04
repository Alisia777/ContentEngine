from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040010_research_category_alias_reaffirmation.sql"
)


def _sql() -> str:
    assert MIGRATION.is_file(), f"Missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def test_reaffirmation_migration_parses_and_extends_only_append_action() -> None:
    sql = _sql().casefold()

    assert parse_sql(_sql())
    assert sql.startswith("begin;") and sql.rstrip().endswith("commit;")
    assert "research_product_market_category_bindings_decision_action_check" in sql
    for action in (
        "bind_existing",
        "create_and_bind",
        "reclassify",
        "create_and_reclassify",
        "reaffirm",
    ):
        assert f"'{action}'" in sql
    assert "update content_factory.research_market_categories" not in sql
    assert "update content_factory.research_market_category_aliases" not in sql
    assert "delete from content_factory.research_market_category_aliases" not in sql


def test_reaffirmation_is_exact_confirmed_idempotent_and_role_bounded() -> None:
    sql = _sql().casefold()

    assert "public.creator_reaffirm_research_market_category" in sql
    assert "p_payload ->> 'action' <> 'reaffirm'" in sql
    assert "p_payload -> 'confirmation' is distinct from 'true'::jsonb" in sql
    assert "array['owner', 'admin', 'producer']" in sql
    assert "begin_command(" in sql and "finish_command(" in sql
    assert sql.count("'creator_reaffirm_research_market_category'") >= 2
    assert "research_market_category_candidate(" in sql
    assert "candidate_hash_value" in sql
    assert "for update" in sql
    assert "research-market-category-registry" in sql
    assert "research-market-product:" in sql
    assert "current_binding.category_id <> category_id_value" in sql
    assert "category.status = 'active'" in sql
    assert "research_market_category_alias_conflict" in sql
    assert "research_market_category_alias_already_registered" in sql


def test_reaffirmation_appends_alias_binding_and_local_source_heads() -> None:
    sql = _sql().casefold()

    assert "insert into content_factory.research_market_category_aliases" in sql
    assert "insert into content_factory.research_product_market_category_bindings" in sql
    assert "current_binding.binding_version + 1, 'reaffirm'" in sql
    assert "source_run_id, source_draft_id" in sql
    assert "system_register_research_category_sources" in sql
    assert "append_research_draft_source_analysis_binding" in sql
    assert "'baseline_adoption'" in sql
    assert "research_market_category_reaffirmation_source_failed" in sql
    assert "research_market_category_reaffirmed" in sql
    assert "paid_provider_action', false" in sql
    assert "net.http" not in sql


def test_public_surface_is_only_authenticated_rpc() -> None:
    sql = _sql().casefold()

    assert (
        "revoke all on function public.creator_reaffirm_research_market_category(jsonb)\n"
        "  from public, anon, authenticated, service_role;"
        in sql
    )
    assert (
        "grant execute on function public.creator_reaffirm_research_market_category(jsonb)\n"
        "  to authenticated;"
        in sql
    )
    assert "grant execute on function content_factory_private" not in sql
    assert "select pg_notify('pgrst', 'reload schema');" in sql
