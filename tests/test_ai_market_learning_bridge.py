from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040005_ai_market_learning_bridge.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "ai_market_learning_bridge_test.sql"
VIEW = ROOT / "web" / "app" / "ai-learning-control-room.js"
APP = ROOT / "web" / "app" / "app.js"
API = ROOT / "web" / "app" / "supabase-api.js"
ACTION_KEY = ROOT / "web" / "app" / "workspace-action-key.js"


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing AI market-learning asset: {path}"
    return path.read_text(encoding="utf-8")


def _sql_function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(qualified_name)}\s*\(",
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


def _run_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable AI market-learning contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(_read(VIEW), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_forward_migration_and_pgtap_parse() -> None:
    assert parse_sql(_read(MIGRATION))
    assert parse_sql(_read(PGTAP))


def test_market_scope_index_is_dynamic_read_only_and_truthful() -> None:
    sql = _read(MIGRATION)
    index = _sql_function(sql, "public.creator_ai_learning_market_scope_index")
    lowered = index.casefold()

    assert "research_product_market_category_bindings" in lowered
    assert "research_market_categories" in lowered
    assert "research_category_evidence_readiness" in lowered
    assert "category-evidence-readiness-v3" in lowered
    assert "category_evidence_readiness_not_model_iq" in lowered
    assert "distinct on (binding.product_id)" in lowered
    assert "binding.binding_version desc" in lowered
    assert "source_run.id = binding.source_run_id" in lowered
    assert "order by run.created_at desc" not in lowered
    assert "readiness_by_category as materialized" in lowered
    assert "statement_timestamp()" in lowered
    assert "security definer" in lowered
    assert "set search_path = ''" in lowered
    assert "ai_category_knowledge_sources" not in lowered
    assert "ai_effective_category_policies" not in lowered
    for mutation in ("insert into", "update ", "delete from"):
        assert mutation not in lowered
    assert "notify pgrst, 'reload schema'" in sql.casefold()


def test_legacy_static_teaching_no_longer_changes_generation_policy() -> None:
    sql = _read(MIGRATION)
    policy = _sql_function(sql, "public.creator_generation_learning_policy")
    lowered = policy.casefold()

    assert "creator_generation_learning_policy_pre_ai_control_room_v8" in lowered
    assert "return base_policy" in lowered
    assert "security definer" in lowered
    assert "set search_path = ''" in lowered
    assert "ai_effective_category_policies" not in lowered
    assert "human_teaching_card_policy" not in lowered


def test_dynamic_uuid_scope_normalizes_without_other_fallback() -> None:
    result = _run_module(
        r'''
const organizationId = "10000000-0000-4000-8000-000000000001";
const bindingId = "20000000-0000-4000-8000-000000000001";
const categoryId = "30000000-0000-4000-8000-000000000001";
const productId = "40000000-0000-4000-8000-000000000001";
const runId = "50000000-0000-4000-8000-000000000001";
const dimensions = [
  ["source_volume", 20, 4, 12],
  ["platform_diversity", 15, 2, 3],
  ["competitor_observations", 20, 2, 5],
  ["trend_recency", 15, 3, 6],
  ["analysis_coverage", 15, 4, 8],
  ["human_validation", 15, 2, 4],
].map(([key, weight, current, target]) => {
  const score = Math.floor(100 * current / target);
  return {
    key,
    label: key,
    weight,
    current,
    target,
    score,
    weighted_points: Math.floor(weight * score / 100),
    missing: target - current,
    next_action: `improve_${key}`,
  };
});
const score = dimensions.reduce((sum, item) => sum + item.weighted_points, 0);
const raw = {
  ok: true,
  version: "ai-learning-market-scope-index-v1",
  organization_id: organizationId,
  metric_kind: "category_evidence_readiness_not_model_iq",
  as_of: "2026-08-04T12:00:00.000Z",
  scopes: [{
    scope_id: bindingId,
    product_id: productId,
    product_name: "Новый продукт",
    product_status: "active",
    market_category_id: categoryId,
    canonical_name: "Новая динамическая категория",
    definition: "Точная проверяемая граница новой динамической категории товара.",
    binding_id: bindingId,
    binding_version: 3,
    run_id: runId,
    run_status: "completed",
    run_finished_at: "2026-08-04T11:00:00.000Z",
    readiness: {
      metric_kind: "category_evidence_readiness_not_model_iq",
      definition_version: "category-evidence-readiness-v3",
      score,
      dimensions,
      weights_total: 100,
      evidence_hash: "a".repeat(64),
      as_of: "2026-08-04T12:00:00.000Z",
    },
    guidance: {
      status: "developing_evidence",
      gaps: dimensions,
      recommended_next_action: "improve_source_volume",
    },
  }],
  limits: {
    item_limit: 50,
    detail_rpc: "creator_research_category_learning_status",
    score_is_model_iq: false,
    status_read_only: true,
    external_call_started: false,
  },
};
const normalized = subject.normalizeAiLearningMarketScopeIndex(raw);
const markup = subject.aiLearningMarketScopeIndexMarkup(normalized, {
  selectedScopeId: bindingId,
  detailMarkup: '<div id="evidence-detail">lineage</div>',
});
const staleMarkup = subject.aiLearningMarketScopeIndexMarkup(normalized, {
  selectedScopeId: "20000000-0000-4000-8000-000000000099",
  detailMarkup: '<div id="stale-evidence-detail">must-not-render</div>',
});
const invalid = subject.normalizeAiLearningMarketScopeIndex({
  ...raw,
  scopes: [{ ...raw.scopes[0], market_category_id: "other" }],
});
return {
  available: normalized.available,
  selected: normalized.scopes[0]?.scopeId,
  category: normalized.scopes[0]?.categoryId,
  name: normalized.scopes[0]?.canonicalName,
  containsDetail: markup.includes("evidence-detail"),
  containsScore: markup.includes(`${score}%`),
  containsSelector: markup.includes('data-action="select-ai-market-learning-scope"'),
  staleContainsDetail: staleMarkup.includes("stale-evidence-detail"),
  staleContainsSelector: staleMarkup.includes('data-action="select-ai-market-learning-scope"'),
  staleMarksFirstActive: staleMarkup.includes("ai-market-scope-card is-active"),
  invalidAvailable: invalid.available,
};
'''
    )
    assert result == {
        "available": True,
        "selected": "20000000-0000-4000-8000-000000000001",
        "category": "30000000-0000-4000-8000-000000000001",
        "name": "Новая динамическая категория",
        "containsDetail": True,
        "containsScore": True,
        "containsSelector": True,
        "staleContainsDetail": False,
        "staleContainsSelector": True,
        "staleMarksFirstActive": False,
        "invalidAvailable": False,
    }


def test_spa_reuses_research_detail_and_routes_exact_scope() -> None:
    app = _read(APP)
    api = _read(API)
    action_key = _read(ACTION_KEY)

    assert "researchCategoryLearningMarkup" in app
    assert "normalizeAiLearningMarketScopeIndex" in app
    assert "aiLearningMarketScopeIndex" in api
    assert 'aiLearningMarketScopeIndex: "creator_ai_learning_market_scope_index"' in api
    assert "state.api.researchCategoryLearningStatus" in app
    assert 'data-learning-context="ai"' in app
    assert "aiLearningMarketDetailMatchesScope" in app
    assert "categoryLearningUiMutationIsCurrent" in app
    assert 'previousAiPath !== "/workspace/ai"' in app
    assert 'entities: { scope:' in action_key
    assert 'action === "select-ai-market-learning-scope"' in app
