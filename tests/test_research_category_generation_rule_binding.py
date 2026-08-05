from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040013_research_category_generation_rule_binding.sql"
)


def _sql() -> str:
    assert MIGRATION.is_file(), f"Missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        source,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"Missing SQL function {qualified_name}"
    next_match = re.search(
        r"\ncreate\s+or\s+replace\s+function\s+",
        source[match.end() :],
        flags=re.IGNORECASE,
    )
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _between(source: str, start: str, end: str) -> str:
    start_at = source.casefold().index(start.casefold())
    end_at = source.casefold().index(end.casefold(), start_at)
    return source[start_at:end_at]


def test_migration_is_valid_postgresql_and_transactional() -> None:
    sql = _sql()

    assert parse_sql(sql)
    assert sql.casefold().startswith("begin;")
    assert sql.casefold().rstrip().endswith("commit;")


def test_authoritative_research_structure_uses_exact_handoff_fields() -> None:
    compiler = _function(
        _sql(),
        "content_factory_private.generation_spec_research_structure",
    ).casefold()

    assert "scenario_value := brief_value #> array[" in compiler
    assert "'scenarios', (scenario_position_value - 1)::text" in compiler
    assert "hook_value := btrim(regexp_replace(" in compiler
    assert "jsonb_typeof(scenario_value -> 'shot_list') = 'array'" in compiler
    assert "jsonb_array_elements(scenario_value -> 'shot_list')" in compiler
    assert "string_agg(" in compiler
    assert "item.value ->> 'seconds'" in compiler
    assert "item.value ->> 'visual'" in compiler
    assert "item.value ->> 'voiceover'" in compiler
    assert "item.value ->> 'on_screen_text'" in compiler
    assert "item.value::text" in compiler
    assert "research_text := lower(concat_ws(' ', hook_value, shot_list_value))" in compiler
    assert "(^|[^[:alnum:]_])(why|" in compiler
    assert "(^|[^[:alnum:]_])(compare|versus|vs|" in compiler
    assert "task_blueprint" not in compiler
    assert "mandatory_shots" not in compiler
    assert "visual_direction" not in compiler
    assert "visualdirection" not in compiler
    assert "'compiler_version', 'safe-brief-v7'" in compiler
    assert "'{category_analysis,maturity}'" in compiler
    assert "'{competitor_analysis,coverage}'" in compiler
    assert "'{trend_analysis,signal_catalog_version}'" in compiler
    assert "signal.value ->> 'recommended_use' = 'test'" in compiler
    assert "signal.value ->> 'confidence' in ('medium', 'high')" in compiler
    assert "'primary_signal', primary_signal_value" in compiler

    ordered_signals = (
        '"question_led"',
        '"why_explanation"',
        '"before_buying"',
        '"comparison"',
        '"demonstration"',
        '"first_person"',
        '"numbered"',
        '"concise"',
    )
    positions = [compiler.index(signal) for signal in ordered_signals]
    assert positions == sorted(positions)
    for angle in (
        "comparison",
        "objection_handling",
        "demonstration",
        "curiosity_gap",
        "trust_builder",
        "product_focus",
    ):
        assert f"'{angle}'" in compiler


def test_external_reference_guard_rejects_schemes_and_bare_domains() -> None:
    helper = _function(
        _sql(),
        "content_factory_private.generation_spec_prompt_has_external_reference",
    ).casefold()

    assert "returns boolean" in helper
    assert "immutable" in helper
    for scheme in ("data", "mailto", "javascript", "ipfs"):
        assert scheme in helper
    assert "([0-9]{1,3}[.]){3}[0-9]{1,3}" in helper
    assert "xn--[a-z0-9-]{2,59}" in helper
    assert "[a-z]{2}" in helper
    assert "рф" in helper
    assert "[^[:alnum:]_-]" in helper


def test_fragment_helper_is_exact_ascii_and_allowlisted() -> None:
    helper = _function(
        _sql(),
        "content_factory_private.generation_spec_research_category_rule_fragment",
    ).casefold()

    assert "canonical_learning_context_value jsonb" in helper
    assert "returns text" in helper
    assert "immutable" in helper
    assert "strict" in helper
    assert "set search_path = ''" in helper
    assert "is distinct from 'approved_research'" in helper
    assert "is distinct from 'safe-brief-v7'" in helper
    assert (
        "researchcategoryrule/v2 category_maturity=%s "
        "competitor_coverage=%s primary_signal=%s "
        "creative_angle=%s primary_hook=%s."
        in helper
    )
    for category_value in (
        "emerging",
        "growing",
        "established",
        "saturated",
        "unknown",
        "limited",
        "sufficient",
        "format.comparison",
        "proof.product_in_use",
    ):
        assert f"'{category_value}'" in helper
    for angle in (
        "product_focus",
        "trust_builder",
        "demonstration",
        "comparison",
        "objection_handling",
        "curiosity_gap",
    ):
        assert f"'{angle}'" in helper
    for hook in (
        "question_led",
        "why_explanation",
        "before_buying",
        "comparison",
        "demonstration",
        "first_person",
        "numbered",
        "concise",
    ):
        assert f"'{hook}'" in helper
    assert "jsonb_typeof(hook.value) is distinct from 'string'" in helper
    assert "coalesce(hooks_value ->> 0, 'none')" in helper
    assert "octet_length(fragment_value) <> length(fragment_value)" in helper
    assert r"fragment_value ~ e'[\\r\\n]'" in helper
    assert "draft.brief" not in helper
    assert "source_url" not in helper


def test_prompt_requires_one_exact_standalone_fragment() -> None:
    helper = _function(
        _sql(),
        "content_factory_private.generation_spec_prompt_has_exact_category_rule",
    ).casefold()

    assert (
        r"regexp_split_to_table(compiled_prompt_value, e'\\r?\\n')"
        in helper
    )
    assert "prompt_line.value = rule_fragment_value" in helper
    assert "select count(*) = 1" in helper
    assert "length(replace(" in helper
    assert "= length(rule_fragment_value)" in helper
    assert "lower(compiled_prompt_value), 'researchcategoryrule/', ''" in helper
    assert "= length('researchcategoryrule/')" in helper


def test_temporal_binding_uses_dynamic_uuid_identity_without_legacy_fallback() -> None:
    helper = _function(
        _sql(),
        "content_factory_private.generation_spec_research_category_temporal_binding",
    ).casefold()

    assert "category_binding_id uuid" in helper
    assert "market_category_id uuid" in helper
    assert "category_binding_version integer" in helper
    assert "research_product_market_category_bindings" in helper
    assert "binding.confirmed_at <= draft.created_at" in helper
    assert "binding.source_run_id = draft.run_id" in helper
    assert "binding.source_draft_id = draft.id" in helper
    assert "binding.candidate_hash = content_factory_private.json_hash(" in helper
    assert "research_market_identity_key(" in helper
    assert "research_market_category_aliases" in helper
    exact_at = helper.index("binding.source_run_id = draft.run_id")
    earlier_at = helper.index("binding.confirmed_at <= draft.created_at")
    assert exact_at < earlier_at
    assert "then binding.binding_version end desc" in helper
    assert "product_category" not in helper
    assert "'other'" not in helper


def test_source_freshness_uses_the_same_exact_first_category_and_repairs_history() -> None:
    sql = _sql()
    source_helper = _function(
        sql,
        "content_factory_private.research_draft_market_category_id",
    ).casefold()
    repair = _between(
        sql,
        "do $research_category_rule_source_binding_repair$",
        "create table content_factory.generation_spec_research_category_rule_bindings",
    ).casefold()

    assert "generation_spec_research_category_temporal_binding(" in source_helper
    assert "select temporal.market_category_id" in source_helper
    assert "system_register_research_category_sources" in repair
    assert "distinct on (binding.organization_id, binding.product_id)" in repair
    assert "binding.binding_version desc" in repair
    assert "binding.candidate_hash = content_factory_private.json_hash(" in repair
    assert "append_research_draft_source_analysis_binding(" in repair
    assert "analysis_event_id_value, 'backfill'" in repair
    assert "research_category_rule_source_binding_backfill_failed" in repair
    assert (
        "revoke all on function\n"
        "  content_factory_private.research_draft_market_category_id("
        in sql.casefold()
    )


def test_modern_research_provenance_is_captured_and_legacy_drafts_are_explicit() -> None:
    capture = _function(
        _sql(),
        "content_factory_private.capture_generation_spec_research_category_rule",
    ).casefold()

    assert "if new.research_provenance is null then" in capture
    assert "'researchcategoryrule/' in lower(new.compiled_prompt)" in capture
    assert "is distinct from 'approved_research'" in capture
    assert "new.performance_policy_provenance is not null" in capture
    assert "research_category_rule_single_owner_required" in capture
    assert "draft.status = 'approved'" in capture
    assert "draft_row.brief -> 'category_analysis'" in capture
    legacy_at = capture.index(
        "jsonb_typeof(draft_row.brief -> 'category_analysis')"
    )
    legacy_token_guard_at = capture.index(
        "'researchcategoryrule/' in lower(new.compiled_prompt)",
        legacy_at,
    )
    legacy_return_at = capture.index("return new;", legacy_token_guard_at)
    assert legacy_at < legacy_token_guard_at < legacy_return_at
    assert "generation_spec_research_category_temporal_binding" in capture
    assert "category.status = 'active'" in capture
    structure_at = capture.index("generation_spec_research_structure(")
    synthetic_context_at = capture.index(
        "research_rule_context_value := research_structure_value"
    )
    fragment_at = capture.index(
        ".generation_spec_research_category_rule_fragment("
    )
    receipt_at = capture.index(
        "content_factory.generation_spec_research_category_rule_bindings"
    )
    assert structure_at < synthetic_context_at < fragment_at < receipt_at
    assert "jsonb_build_object('source', 'approved_research')" in capture
    assert (
        "canonical_learning_context ->> 'source' = 'approved_research'"
        in capture
    )
    assert "research_structure_value ->> 'creative_angle'" in capture
    assert "research_structure_value -> 'hook_patterns'" in capture
    assert "generation_spec_prompt_has_exact_category_rule" in capture
    assert "raw_text_sha256(new.compiled_prompt)" in capture
    assert "research_prompt_external_url_forbidden" in capture
    assert "message = 'generation_spec_research_category_rule_stale'" in capture

    sql = _sql().casefold()
    assert "after insert on content_factory.generation_spec_versions" in sql
    assert "capture_generation_spec_research_category_rule_binding" in sql


def test_receipt_is_exact_hash_only_and_append_only() -> None:
    sql = _sql()
    table = _between(
        sql,
        "create table content_factory.generation_spec_research_category_rule_bindings",
        "create index generation_spec_research_category_rule_bindings_category_idx",
    ).casefold()

    for column in (
        "market_category_id uuid not null",
        "category_binding_id uuid not null",
        "category_binding_version integer not null",
        "research_run_id uuid not null",
        "research_draft_id uuid not null",
        "spec_hash text not null",
        "prompt_hash text not null",
        "rule_hash text not null",
        "receipt_hash text not null",
    ):
        assert column in table
    assert "research-product" not in table
    assert "generation-spec-research-category-rule-binding-v2" in table
    assert "researchcategoryrule/v2" in table
    for column in (
        "category_maturity text not null",
        "competitor_coverage text not null",
        "primary_signal text not null",
    ):
        assert column in table
    assert "raw_text_sha256(" in table
    assert "json_hash(jsonb_build_object(" in table
    assert "category_binding_confirmed_at <= research_draft_created_at" in table
    assert "category_binding_source_run_id = research_run_id" in table
    assert "category_binding_source_draft_id = research_draft_id" in table
    for forbidden in (
        "source_url",
        "source_text",
        "extracted_facts",
        "compiled_prompt",
        "draft.brief",
        "canonical_name",
        "definition",
    ):
        assert forbidden not in table

    lowered = sql.casefold()
    assert (
        "generation_spec_research_category_rule_bindings_append_only"
        in lowered
    )
    assert "before update or delete" in lowered
    assert "reject_generation_spec_mutation()" in lowered
    assert (
        "revoke all on content_factory."
        "generation_spec_research_category_rule_bindings"
        in lowered
    )


def test_job_guard_revalidates_drift_retirement_and_source_correction_twice() -> None:
    current = _function(
        _sql(),
        "content_factory_private.generation_spec_research_category_rule_current",
    ).casefold()
    guard = _function(
        _sql(),
        "content_factory_private.guard_generation_job_research_category_rule",
    ).casefold()

    assert "order by binding.binding_version desc, binding.id desc" in current
    assert "current_binding.id <> receipt_row.category_binding_id" in current
    assert (
        "current_binding.binding_version <>\n"
        "          receipt_row.category_binding_version"
        in current
    )
    assert "category.status = 'active'" in current
    assert "research_generation_spec_evidence_fresh(" in current
    assert "generation_spec_research_category_temporal_binding(" in current
    assert "generation_spec_research_structure(" in current
    assert "generation_spec_prompt_has_exact_category_rule(" in current
    assert "generation_spec_prompt_has_external_reference(" in current
    assert "spec_row.research_provenance is null" in current
    assert "is distinct from 'approved_research'" in current
    assert "spec_row.performance_policy_provenance is not null" in current
    assert "receipt_row.category_maturity" in current
    assert "receipt_row.competitor_coverage" in current
    assert "receipt_row.primary_signal" in current
    assert "jsonb_build_object('source', 'approved_research')" in current
    legacy_at = current.index(
        "jsonb_typeof(draft_row.brief -> 'category_analysis')"
    )
    compatibility_at = current.index("return position(", legacy_at)
    receipt_lookup_at = current.index("select receipt.* into receipt_row")
    fail_closed_at = current.index("if receipt_row.id is null then")
    assert legacy_at < compatibility_at < receipt_lookup_at < fail_closed_at
    assert "return false;" in current[fail_closed_at:]

    assert "new.mode <> 'real'" in guard
    assert "new.provider <> 'runway'" in guard
    assert "not new.allow_real_spend" in guard
    assert "old.status = 'queued' and new.status = 'starting'" in guard
    assert "research-market-product:" in guard
    assert "pg_advisory_xact_lock" in guard
    assert "generation_spec_research_category_rule_current(" in guard
    assert "message = 'generation_spec_research_category_rule_stale'" in guard
    assert "message = 'generation_spec_provider_start_stale'" in guard
    assert "detail = 'generation_spec_research_category_rule_stale'" in guard

    lowered = _sql().casefold()
    assert "create trigger c_research_category_generation_rule_guard" in lowered
    assert (
        "before insert or update of status on content_factory.generation_jobs"
        in lowered
    )


def test_provider_boundary_is_local_and_has_no_raw_or_network_side_effect() -> None:
    sql = _sql().casefold()

    assert sql.count("create or replace function public.") == 1
    assert "public.creator_retire_research_market_category" in sql
    assert sql.count("grant execute") == 1
    assert "net.http" not in sql
    assert "provider_task_id" not in sql
    assert "source_url" not in sql
    assert "'other'" not in sql
    assert "stale_error_code" in sql
    assert "generation_spec_research_category_rule_stale" in sql
    assert "generation_spec_provider_start_stale" in sql


def test_category_retirement_is_audited_idempotent_and_single_transition() -> None:
    sql = _sql().casefold()
    table = _between(
        sql,
        "create table content_factory.research_market_category_retirement_events",
        "alter table content_factory.research_market_category_retirement_events",
    )
    retirement = _function(
        sql, "public.creator_retire_research_market_category"
    )
    mutation_guard = _function(
        sql, "content_factory_private.reject_research_market_identity_mutation"
    )

    assert "unique (organization_id, category_id)" in table
    assert "unique (organization_id, idempotency_key)" in table
    assert "request_hash text not null" in table
    assert "event_hash text not null" in table
    assert "array['owner', 'admin']" in retirement
    assert "pg_advisory_xact_lock" in retirement
    assert "for update" in retirement
    assert "category.status = 'active'" in retirement
    assert "set status = 'retired'" in retirement
    assert "research-market-category-retirement-v1" in retirement
    assert "idempotency_key_conflict" in retirement
    assert "previous_retirement_setting" in retirement
    assert "to_jsonb(new) - 'status' = to_jsonb(old) - 'status'" in mutation_guard
    assert "to_jsonb(old) ->> 'status' = 'active'" in mutation_guard
    assert "to_jsonb(new) ->> 'status' = 'retired'" in mutation_guard
    assert "research_market_categories'" in mutation_guard
    assert "reject_research_market_category_retirement_event_mutation" in sql
