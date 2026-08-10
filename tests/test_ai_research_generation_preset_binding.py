"""Contracts for the durable Research -> AI Center -> Generation bridge."""

from __future__ import annotations

from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608100001_research_ai_center_generation_presets.sql"
)
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")


def _sql() -> str:
    assert MIGRATION.is_file(), f"Missing migration: {MIGRATION}"
    return MIGRATION.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(qualified_name)}\s*\(",
        source,
        flags=re.IGNORECASE,
    )
    assert match is not None, f"Missing SQL function {qualified_name}"
    terminator = re.search(r"\n\$\$;", source[match.end() :])
    assert terminator is not None, f"Unterminated SQL function {qualified_name}"
    end = match.end() + terminator.end()
    return source[match.start() : end]


def test_migration_is_transactional_ordered_and_parseable() -> None:
    sql = _sql()
    assert MIGRATION.name > "202608050006_exact_youtube_source_intake.sql"
    assert sql.lstrip().casefold().startswith("begin;")
    assert sql.rstrip().casefold().endswith("commit;")
    assert parse_sql(sql)


def test_learned_queue_returns_durable_material_analysis_and_conclusions() -> None:
    queue = _function(
        _sql(), "public.creator_ai_research_training_queue"
    ).casefold()
    for marker in (
        "selection.analysis_snapshot",
        "selection.source_snapshot",
        "'material_snapshot'",
        "ai_research_source_snapshot(",
        "'research_summary'",
        "'forecast'",
        "selection.recommendations",
        "'deep_link'",
        "'learned_snapshots_are_durable', true",
    ):
        assert marker in queue
    assert "'raw_research_enters_prompt_automatically', false" in queue
    assert "'paid_call_started', false" in queue


def test_recommendations_are_cross_platform_advisory_editable_presets() -> None:
    sql = _sql()
    recommendations = _function(
        sql, "public.contentengine_generation_research_recommendations"
    ).casefold()
    preset = _function(
        sql, "content_factory_private.ai_research_generation_preset"
    ).casefold()
    for platform in (
        "'instagram'",
        "'tiktok'",
        "'youtube'",
        "'vk'",
        "'telegram'",
        "'wildberries'",
    ):
        assert platform in recommendations
    assert "platform_rank" in recommendations
    candidate_filter = recommendations[
        recommendations.index("where selection.organization_id"):
        recommendations.index("), bounded as")
    ]
    assert "platform_value" not in candidate_filter
    assert "'cross_platform_fallback', true" in recommendations
    assert "'presets_are_advisory', true" in recommendations
    assert "'human_edits_are_preserved', true" in recommendations
    assert "'preset'" in recommendations
    assert "real_gen4" in preset and "(2, 5, 8, 10)" in preset
    assert "real_seedance" in preset and "(4, 8, 12, 15)" in preset
    assert "'paid_call_started', false" in recommendations


def test_exact_spec_binding_is_append_only_scoped_and_provider_free() -> None:
    sql = _sql()
    lowered = sql.casefold()
    binding = _function(
        sql, "public.contentengine_bind_generation_spec_ai_research"
    ).casefold()
    assert "create table if not exists\n  content_factory.generation_spec_ai_research_bindings" in lowered
    assert "generation_spec_ai_research_binding_append_only" in lowered
    assert "reject_research_ai_handoff_mutation" in lowered
    assert "require_generation_spec_project_v49" in binding
    assert "selection_row.project_id <> project_id_value" in binding
    assert "selection_row.product_category <> spec_row.product_category" in binding
    assert "selection_row.decision <> 'approve'" in binding
    assert "position_value = any(selection_row.selected_scenario_positions)" in binding
    assert "selection_row.product_id <> product_id_value" not in binding
    assert "jsonb_typeof(recommendation_value) is distinct from 'object'" in binding
    assert "generation_spec_ai_research_binding_confirmation_required" in binding
    for forbidden in (
        "net.http_post",
        "http_post(",
        "runway",
        "provider_start",
        "reserve_generation",
    ):
        assert forbidden not in binding


def test_browser_binds_only_an_applied_recommendation_before_paid_start() -> None:
    for marker in (
        '"contentengine_bind_generation_spec_ai_research"',
        '"contentengine_generation_spec_ai_research_binding"',
        "bindGenerationSpecAiResearch(input = {})",
        "generationSpecAiResearchBinding(context = {})",
    ):
        assert marker in API
    bind_api = API[
        API.index("bindGenerationSpecAiResearch(input = {})"):
        API.index("generationSpecAiResearchBinding(context = {})")
    ]
    assert "return this.call(" in bind_api
    assert "this.mutate(" not in bind_api
    for marker in (
        '"contentengine:generation-research-preset-applied"',
        '"contentengine:generation-research-preset-opt-out"',
        "handleGenerationResearchPresetApplied",
        "handleGenerationResearchPresetOptOut",
        "generationSpecAiResearchSelection(payload",
        "bindGenerationSpecAiResearch(spec, preparedPayload)",
        "await bindGenerationSpecAiResearch(",
        "generationSpecAiResearchBindingMatches",
    ):
        assert marker in APP
    prepare = APP[
        APP.index("async function runGenerationSpecControl("):
        APP.index("async function ensurePreparedGenerationSpecForPaidStart(")
    ]
    assert prepare.index("await state.api.prepareGenerationSpec") < prepare.index(
        "await bindGenerationSpecAiResearch("
    )
    assert "real_spend_confirmation.checked = false" in APP
    assert "state.aiResearchRecommendation = null" in APP
