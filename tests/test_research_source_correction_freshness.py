from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040001_research_source_correction_freshness.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "research_category_learning_readiness_test.sql"
)
APP = ROOT / "web" / "app" / "app.js"
GENERATION_SPEC = ROOT / "web" / "app" / "generation-spec.js"


def _migration() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_sql_and_runtime_fixture_are_postgresql_syntax() -> None:
    assert parse_sql(_migration())
    assert parse_sql(PGTAP.read_text(encoding="utf-8"))


def test_exact_source_analysis_heads_are_bound_append_only() -> None:
    sql = _migration().casefold()

    assert "research_draft_source_analysis_bindings" in sql
    assert "analysis_event_id" in sql
    assert "analysis_event_hash" in sql
    assert "research-draft-source-analysis-binding-v2" in sql
    assert "binding_version" in sql
    assert "parent_binding_id" in sql
    assert "binding_hash" in sql
    assert "reject_research_draft_source_analysis_binding_mutation" in sql
    assert "research_draft_source_analysis_fresh" in sql
    assert "event.created_at <= draft_row.created_at" in sql
    assert "event.parser_key = 'persisted_source_fallback'" in sql
    assert "event.parser_version = '1.0.0'" in sql


def test_corrections_invalidate_stage_and_generation_heads() -> None:
    sql = _migration().casefold()

    assert "invalidate_research_source_analysis_dependents" in sql
    assert "'dependency_refresh'" in sql
    assert "'stale_dependency'" in sql
    assert "write_research_stage_head_event" in sql
    assert "generation_spec_head_events" in sql
    assert "'recompute', 'draft'" in sql
    assert "guard_generation_spec_research_evidence_approval" in sql
    assert "generation_spec_research_provenance_stale" in sql
    assert "guard_generation_job_research_evidence" in sql
    assert "generation_spec_provider_start_stale" in sql
    assert "generation_spec_envelope_pre_source_freshness_v1" in sql
    assert "'code', 'start_new_research_after_source_change'" in sql
    assert "'action', 'start_new_research'" in sql
    assert "source_analysis_changed_before_provider_claim" in sql


def test_correction_guard_is_local_fail_closed_and_provider_neutral() -> None:
    sql = _migration().casefold()

    assert "create or replace function public." not in sql
    assert "grant execute" not in sql
    assert "http" not in sql
    assert "provider_attempt" not in sql
    assert "allow_real_spend" in sql
    assert "new.status = 'starting'" in sql
    assert "research-stage-ledger:" in sql
    assert "pg_advisory_xact_lock" in sql


def test_invalidation_uses_controller_lock_order_and_full_semantic_head() -> None:
    sql = _migration().casefold()
    helper_start = sql.rindex(
        "create or replace function\n"
        "  content_factory_private.invalidate_research_source_analysis_dependents_for_event"
    )
    helper_end = sql.index(
        "create or replace function\n"
        "  content_factory_private.invalidate_research_source_analysis_dependents()",
        helper_start,
    )
    helper = sql[helper_start:helper_end]

    stage_control = helper.index("research-stage-control:")
    brief = helper.index("brief:")
    ledger = helper.index("research-stage-ledger:")
    assert stage_control < brief < ledger
    assert "analysis_row.origin = 'human_correction'" not in helper
    assert "binding.analysis_event_id is distinct from analysis_row.id" in helper
    assert "binding.analysis_event_hash is distinct from analysis_row.event_hash" in helper
    assert "request.status = 'queued'" in helper
    assert "set status = 'superseded'" in helper


def test_binding_versions_use_an_acyclic_dedicated_lock_domain() -> None:
    sql = _migration().casefold()
    append_start = sql.index(
        "create or replace function\n"
        "  content_factory_private.append_research_draft_source_analysis_binding"
    )
    append_end = sql.index(
        "create or replace function\n"
        "  content_factory_private.capture_research_draft_source_analysis_bindings",
        append_start,
    )
    append = sql[append_start:append_end]

    assert "research-draft-source-binding:" in append
    assert "research-stage-control:" not in append
    assert "research-stage-ledger:" not in append
    assert "hashtext('research-market-product:'" not in append


def test_runtime_fixture_proves_all_seven_stages_become_stale() -> None:
    pgtap = PGTAP.read_text(encoding="utf-8")

    assert "every draft source is bound to its exact semantic analysis head" in pgtap
    assert "parser baselines extend draft lineage append-only" in pgtap
    assert "the initial draft is fresh" in pgtap
    assert "makes the exact draft evidence binding stale" in pgtap
    assert "invalidates all seven dependent main-branch stages" in pgtap
    assert "invalidation is append-only and auditable per stage" in pgtap
    assert "returns the exact dependent generation spec to draft" in pgtap
    assert "blocks generation-spec reapproval" in pgtap
    assert "generation provenance is fresh before source correction" in pgtap
    assert "generation provenance is stale after source correction" in pgtap
    assert "preserves the single immutable approval event" in pgtap
    assert "fails closed before provider start after source correction" in pgtap
    assert "releases the full reservation with zero spend" in pgtap
    assert "emits no provider-start event" in pgtap
    assert "a newer automatic parser can append an exact semantic head" in pgtap
    assert "a parser-v2 semantic change invalidates every dependent governed stage" in pgtap
    assert "stale generation guidance starts an append-only research recovery run" in pgtap


def test_browser_refreshes_stage_control_after_source_correction() -> None:
    app = APP.read_text(encoding="utf-8")
    start = app.index("async function submitProductResearchSourceCorrection")
    end = app.index("async function submitProductResearchCollectionPolicy", start)
    correction_flow = app[start:end]

    assert "refreshProductResearchCategoryLearning(runId)" in correction_flow
    assert "loadResearchStageControl({ runId, silent: true })" in correction_flow
    assert "Зависимые этапы и спецификации помечены устаревшими" in correction_flow


def test_browser_routes_stale_generation_guidance_to_a_new_research_form() -> None:
    app = APP.read_text(encoding="utf-8")
    generation_spec = GENERATION_SPEC.read_text(encoding="utf-8")

    assert '"start_new_research"' in generation_spec
    assert 'if (specAction === "start_new_research")' in app
    assert "beginNewProductResearch" in app
    assert 'navigate("/workspace/research", true)' in app
    assert "Проверьте предзаполненную форму" in app
