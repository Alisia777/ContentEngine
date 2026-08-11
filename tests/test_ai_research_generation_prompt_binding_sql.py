"""SQL contracts for exact AI-recommendation provider prompt binding."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608110008_ai_research_generation_prompt_binding.sql"
)
WORKING_DRAFT_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608110006_ai_research_generation_working_draft.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "ai_research_generation_prompt_binding_test.sql"
)
SHARED_PATH_PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "research_ai_generation_shared_project_path_test.sql"
)


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing SQL contract file: {path}"
    return path.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    pattern = re.compile(
        rf"create\s+or\s+replace\s+function\s+"
        rf"{re.escape(qualified_name).replace(r'\.', r'\s*\.\s*')}\s*\(",
        flags=re.IGNORECASE,
    )
    match = pattern.search(source)
    assert match is not None, f"Missing SQL function {qualified_name}"
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    return source[match.start() : match.end() + terminator.end()]


def test_migration_and_pgtap_are_transactional_ordered_and_parseable() -> None:
    sql = _read(MIGRATION)
    pgtap = _read(PGTAP)
    shared_path_pgtap = _read(SHARED_PATH_PGTAP)
    assert MIGRATION.name > "202608110007_generation_media_product_identity.sql"
    assert sql.lstrip().casefold().startswith("begin;")
    assert sql.rstrip().casefold().endswith("commit;")
    assert pgtap.lstrip().casefold().startswith("begin;")
    assert pgtap.rstrip().casefold().endswith("rollback;")
    assert shared_path_pgtap.rstrip().casefold().endswith("rollback;")
    assert parse_sql(sql)
    assert parse_sql(pgtap)
    assert parse_sql(shared_path_pgtap)


def test_server_fragment_is_bounded_versioned_and_has_five_parts() -> None:
    sql = _read(MIGRATION)
    fragment = _function(
        sql, "content_factory_private.ai_research_provider_prompt_fragment"
    ).casefold()
    for marker in (
        "airesearchselection/v1 c=",
        "|| '|h=' ||",
        "|| '|cta=' ||",
        "|| '|p=' ||",
        "|| '|a=' ||",
        "ai_research_prompt_part(\n    p_recommendation ->> 'hook', 18",
        "p_recommendation ->> 'cta', 64",
        ".ai_research_prompt_proof(\n    p_recommendation",
        ".ai_research_prompt_avoid(\n    p_recommendation",
        "char_length(fragment_value) > 240",
    ):
        assert marker in fragment
    assert "'airesearchselection/v1'" in fragment
    assert "'airesearchhumanintent/v1'" in fragment
    assert "return null" in fragment


def test_human_capsule_uses_codepoint_safe_five_section_budget() -> None:
    sql = _read(MIGRATION)
    part = _function(
        sql, "content_factory_private.ai_research_prompt_part"
    ).casefold()
    human = _function(
        sql, "content_factory_private.ai_research_human_intent_fragment"
    ).casefold()
    assert "char_length(value_value)" in part
    assert "left(value_value, p_limit - 1)" in part
    assert "|| '…'" in part
    assert "e'[ \\t\\r\\n\\f\\013]+'" in part
    assert r"\v" not in part
    assert "replace(value_value, '|', '/')" in part
    assert "regexp_replace(source_value, e'^[ \\t\\r\\n\\f\\013]+'" in human
    assert r"\013" in human
    assert r"\v" not in human
    for label in (
        "КОНЦЕПЦИЯ",
        "ХУК",
        "CTA",
        "ДОКАЗАТЕЛЬСТВА",
        "НЕ ОБЕЩАТЬ / УЧЕСТЬ",
    ):
        assert label.casefold() in human
    for cap in ("16, false", "24, false", "20, false"):
        assert cap in human
    assert "seen_concept <> 1" in human
    assert "char_length(fragment_value) > 150" in human


def test_exact_resolver_and_shared_draft_deliver_server_envelope() -> None:
    sql = _read(MIGRATION).casefold()
    working = _read(WORKING_DRAFT_MIGRATION).casefold()
    snapshot = _function(
        _read(MIGRATION),
        "content_factory_private.ai_research_recommendation_snapshot",
    ).casefold()
    for key in (
        "'provider_prompt_fragment_version'",
        "'ai-research-provider-fragment-v1'",
        "'provider_prompt_fragment'",
        "'provider_prompt_fragment_hash'",
        "raw_text_sha256",
    ):
        assert key in snapshot
    assert "contentengine_generation_research_recommendation" in working
    assert "generation_ai_research_working_draft_snapshot" in working
    assert working.count("ai_research_recommendation_snapshot(") >= 6
    assert "provider_prompt_fragment_value" in sql


def test_binding_delegate_is_exact_product_append_only_and_provider_free() -> None:
    sql = _read(MIGRATION)
    lowered = sql.casefold()
    binding = _function(
        sql,
        "content_factory_private."
        "contentengine_bind_generation_spec_ai_research_pre_project_acl",
    ).casefold()
    assert "selection_row.product_id <> product_id_value" in binding
    assert "selection_row.product_category <> spec_row.product_category" in binding
    assert "position_value = any(selection_row.selected_scenario_positions)" in binding
    assert "provider_marker_count_value <> 1" in binding
    assert "lower(spec_row.compiled_prompt), lower('airesearchselection/v1')" in binding
    assert "lower(spec_row.compiled_prompt), lower('airesearchhumanintent/v1')" in binding
    assert "provider_fragment_count_value <> 1" in binding
    assert "human_marker_count_value <> 1" in binding
    assert "human_fragment_count_value <> 1" in binding
    assert "ai_research_prompt_budget_exceeded" in binding
    assert "generation_spec_ai_research_prompt_binding_invalid" in binding
    assert "'scope_match', 'exact_product'" in binding
    assert "generation_spec_ai_research_prompt_proof_check" in lowered
    for column in (
        "provider_prompt_fragment_version",
        "provider_prompt_fragment_hash",
        "human_intent_fragment_version",
        "human_intent_fragment_hash",
        "compiled_prompt_hash",
        "prompt_binding_proof_hash",
    ):
        assert f"add column if not exists {column}" in lowered
        assert f"'{column}'" in binding
    for forbidden in (
        "net.http_post",
        "http_post(",
        "provider_start",
        "reserve_generation",
    ):
        assert forbidden not in binding


def test_public_project_acl_wrapper_is_not_replaced() -> None:
    sql = _read(MIGRATION).casefold()
    assert not re.search(
        r"create\s+or\s+replace\s+function\s+public\s*\.\s*"
        r"contentengine_bind_generation_spec_ai_research\s*\(",
        sql,
    )
    assert "contentengine_bind_generation_spec_ai_research_pre_project_acl" in sql
    assert "contentengine_generation_spec_ai_research_binding_pre_acl_v423" in sql


def test_paid_start_delegates_full_legacy_chain_before_ai_proof() -> None:
    sql = _read(MIGRATION)
    start = _function(sql, "public.creator_start_real_generation").casefold()
    delegate = (
        ".creator_start_real_generation_pre_ai_research_prompt_v55(p_payload)"
    )
    assert delegate in start
    assert start.index(delegate) < start.index("provider_marker_count_value :=")
    assert start.index(delegate) < start.index(
        "select count(*)::integer into binding_count_value"
    )
    assert "creator_start_real_generation_pre_video_reference_v54" in _read(
        ROOT
        / "supabase"
        / "migrations"
        / "202608100014_generation_video_reference_lineage.sql"
    ).casefold()
    assert "provider_marker_count_value <> human_marker_count_value" in start
    assert "lower(spec_row.compiled_prompt), lower('airesearchselection/v1')" in start
    assert "lower(spec_row.compiled_prompt), lower('airesearchhumanintent/v1')" in start
    assert "generation_ai_research_legacy_binding_start_forbidden" in start
    assert "if binding_count_value = 0 then\n      return result_value" in start
    assert "provider_fragment_count_value <> 1" in start
    assert "human_fragment_count_value <> 1" in start
    assert "return result_value" in start


def test_grants_comments_schema_reload_and_no_external_side_effects() -> None:
    sql = _read(MIGRATION).casefold()
    assert "grant execute on function public.creator_start_real_generation(jsonb)" in sql
    assert "revoke all on function public.creator_start_real_generation(jsonb)" in sql
    assert "comment on function" in sql
    assert "comment on column" in sql
    assert "notify pgrst, 'reload schema'" in sql
    for forbidden in (
        "net.http_post",
        "extensions.http_post",
        "supabase_functions.http_request",
        "runway",
    ):
        assert forbidden not in sql


def test_pgtap_covers_positions_xor_duplicates_manual_legacy_and_rollback() -> None:
    pgtap = _read(PGTAP).casefold()
    for marker in (
        "recommendation_position = 1",
        "recommendation_position = 2",
        "recommendation_position = 3",
        "exact product mismatch",
        "duplicate provider marker",
        "provider-only xor",
        "lower(state.provider_fragment)",
        "human-only xor",
        "manual no-marker/no-binding",
        "legacy binding cannot start",
        "legacy validation keeps precedence",
        "delegated writes roll back",
        "🚀",
        "ai_research_prompt_budget_exceeded",
    ):
        assert marker in pgtap
