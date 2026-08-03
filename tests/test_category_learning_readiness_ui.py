from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "web/app/supabase-api.js"
VIEW_PATH = ROOT / "web/app/product-research-view.js"
APP_PATH = ROOT / "web/app/app.js"
CSS_PATH = ROOT / "web/app/product-research.css"
INDEX_PATH = ROOT / "web/app/index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable readiness UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(_read(path), encoding="utf-8")
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


READINESS_FIXTURE = r"""
const runId = "22222222-2222-4222-8222-222222222222";
const analysis = {
  schema_version: "research-source-interpretation-v1",
  classification: "competitor",
  relevance_score: 80,
  confidence: "medium",
  summary: "Структурное наблюдение о демонстрации товара без копирования чужого текста.",
  structural_signal_keys: ["hook.demonstration_first"],
  limitations: ["Только один публичный источник."],
};
const dimensionSpecs = [
  ["source_volume", "Current reviewable source volume", 20, 2, 12, "collect_more_reviewable_sources"],
  ["platform_diversity", "Platform diversity", 15, 1, 3, "add_an_independent_platform"],
  ["competitor_observations", "Competitor observations / retained YouTube channels", 20, 2, 5, "collect_competitor_observations"],
  ["trend_recency", "Recent canonical trend evidence", 15, 0, 6, "refresh_canonical_trend_evidence"],
  ["analysis_coverage", "Structured / normalized source coverage", 15, 2, 8, "analyze_unreviewed_sources"],
  ["human_validation", "Human-validated evidence", 15, 2, 4, "review_and_correct_source_analysis"],
];
const dimensions = dimensionSpecs.map(([key, label, weight, current, target, nextAction]) => {
  const score = Math.min(100, Math.floor(100 * current / target));
  return {
    key,
    label,
    weight,
    current,
    target,
    score,
    weighted_points: Math.min(weight, Math.floor(weight * score / 100)),
    missing: Math.max(target - current, 0),
    next_action: current >= target ? null : nextAction,
  };
});
const score = dimensions.reduce((sum, item) => sum + item.weighted_points, 0);
const fixture = {
  ok: true,
  version: "research-category-learning-readiness-v1",
  organization_id: "11111111-1111-4111-8111-111111111111",
  run_id: runId,
  metric: {
    label: "Category evidence readiness",
    kind: "category_evidence_readiness_not_model_iq",
    is_ai_iq: false,
    readiness: {
      metric_kind: "category_evidence_readiness_not_model_iq",
      definition_version: "category-evidence-readiness-v1",
      score,
      dimensions,
      weights_total: 100,
      evidence_hash: "e".repeat(64),
      as_of: "2026-08-03T15:00:00.000Z",
      limits: {
        is_model_iq: false,
        is_quality_guarantee: false,
        competitor_metric_is_unique_publishers: false,
        retained_youtube_uses_unique_channel_ids: true,
        youtube_retention_days: 29,
        meaning: "Coverage of durable evidence plus current retention-bound YouTube metadata",
      },
    },
  },
  category: {
    category_id: "33333333-3333-4333-8333-333333333333",
    canonical_name: "Тестовая категория",
    definition: "Устойчивая граница тестовой товарной категории для проверки интерфейса.",
    binding_id: "44444444-4444-4444-8444-444444444444",
    binding_version: 2,
  },
  source_ledger: {
    item_limit: 50,
    analysis_history_limit_per_source: 10,
    lineage_history_limit_per_source: 10,
    raw_captions_stored: false,
    items: [{
      source_ledger_id: "66666666-6666-4666-8666-666666666666",
      source_id: "77777777-7777-4777-8777-777777777777",
      run_id: runId,
      product_id: "55555555-5555-4555-8555-555555555555",
      source_type: "competitor",
      title: "Публичное наблюдение конкурента",
      source_url: "https://example.com/video",
      provider_key: "youtube_data_api_v3",
      platform: "youtube",
      trust_level: "public",
      source_identity_key: "a".repeat(64),
      fetched_at: "2026-08-03T14:00:00.000Z",
      published_at: "2026-08-01T10:00:00.000Z",
      lineage_hash: "b".repeat(64),
      registered_at: "2026-08-03T14:01:00.000Z",
      lineage_history: [{
        source_ledger_id: "66666666-6666-4666-8666-666666666666",
        source_id: "77777777-7777-4777-8777-777777777777",
        source_content_hash: "3".repeat(64),
        lineage_hash: "b".repeat(64),
        fetched_at: "2026-08-03T14:00:00.000Z",
        published_at: "2026-08-01T10:00:00.000Z",
        registered_at: "2026-08-03T14:01:00.000Z",
      }],
      current_analysis: {
        event_id: "88888888-8888-4888-8888-888888888888",
        analysis_version: 2,
        origin: "human_correction",
        parser_key: "human_correction",
        parser_version: "v1",
        analysis,
        correction_reason: "Уточнена классификация по проверенному источнику.",
        event_hash: "c".repeat(64),
        created_at: "2026-08-03T14:04:00.000Z",
      },
      analysis_history: [{
        event_id: "88888888-8888-4888-8888-888888888888",
        analysis_version: 2,
        parent_event_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        origin: "human_correction",
        actor_id: "99999999-9999-4999-8999-999999999999",
        parser_key: "human_correction",
        parser_version: "v1",
        analysis,
        correction_reason: "Уточнена классификация по проверенному источнику.",
        event_hash: "c".repeat(64),
        created_at: "2026-08-03T14:04:00.000Z",
      }, {
        event_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        analysis_version: 1,
        parent_event_id: null,
        origin: "system_parser",
        actor_id: null,
        parser_key: "bounded_source_parser",
        parser_version: "v1",
        analysis,
        correction_reason: null,
        event_hash: "d".repeat(64),
        created_at: "2026-08-03T14:02:00.000Z",
      }],
    }],
  },
  retained_youtube_evidence: {
    item_limit: 50,
    retention_days: 29,
    raw_captions_stored: false,
    corrected_by: "creator_decide_research_youtube_candidate",
    items: [{
      source_kind: "retained_youtube_observation",
      observation_id: "12121212-1212-4212-8212-121212121212",
      ingestion_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      source_url: "https://www.youtube.com/watch?v=AbCdEfGhI_1",
      provider_key: "youtube_data_api_v3",
      platform: "youtube",
      video_id: "AbCdEfGhI_1",
      channel_id: "UCabcdefghijklmnopqrstuv",
      title: "Bounded public metadata observation",
      channel_title: "Public competitor channel",
      published_at: "2026-08-01T10:00:00.000Z",
      observed_at: "2026-08-03T14:00:00.000Z",
      retention_expires_at: "2026-09-01T14:00:00.000Z",
      observation_hash: "4".repeat(64),
      latest_decision: {
        decision_id: "13131313-1313-4313-8313-131313131313",
        decision: "confirm_candidate",
        reason: "Checked against the public YouTube metadata.",
        decided_by: "99999999-9999-4999-8999-999999999999",
        decided_at: "2026-08-03T14:30:00.000Z",
        decision_hash: "5".repeat(64),
      },
      included_in_readiness: true,
    }],
  },
  readiness_history: {
    item_limit: 24,
    captured_only_by_mutation: true,
    items: [{
      snapshot_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      definition_version: "category-evidence-readiness-v1",
      score,
      dimensions,
      evidence_hash: "e".repeat(64),
      snapshot_hash: "f".repeat(64),
      captured_by: "99999999-9999-4999-8999-999999999999",
      captured_at: "2026-08-03T15:01:00.000Z",
    }],
  },
  collection: {
    default_status: "paused",
    policies: [{
      policy_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      policy_hash: "1".repeat(64),
      policy_version: 1,
      platform: "youtube",
      provider_key: "youtube_data_api_v3",
      status: "enabled",
      automatic_collection_ack: true,
      terms_version: "youtube-developer-policies-2026-08-03-v1",
      terms_ack: true,
      quota_ack: true,
      no_retry_ack: true,
      cadence_hours: 168,
      max_records: 10,
      monthly_hard_budget_units: 10,
      legal_review_reference: "LEGAL-2026-08",
      reason: "Ограниченный автоматический сбор категории.",
      created_at: "2026-08-03T15:02:00.000Z",
      automatic_enqueue_supported: true,
      handoff: "automatic_youtube_ingestion_queue",
    }],
    history: [{
      intent_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      policy_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      platform: "youtube",
      provider_key: "youtube_data_api_v3",
      ingestion_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      status: "queued",
      capability: "automatic_youtube_enqueue",
      blocked_reason: null,
      query_text: "Тестовая категория",
      max_records: 10,
      planned_quota_units: 2,
      monthly_hard_budget_units: 10,
      monthly_reserved_units: 2,
      scheduled_for: "2026-08-04T15:00:00.000Z",
      automatic_enqueue_supported: true,
      external_call_started: false,
      no_retry: true,
      no_fallback: true,
      intent_hash: "2".repeat(64),
      created_at: "2026-08-03T15:03:00.000Z",
      ingestion_status: "queued",
      ingestion_error_code: null,
      ingestion_requested_at: "2026-08-03T15:02:59.000Z",
      ingestion_completed_at: null,
      transport_attempt_count: 0,
    }],
    history_limit: 24,
    scheduler_starts_external_calls: false,
    automatic_retry_allowed: false,
    automatic_fallback_allowed: false,
    instagram_automatic_collection: "blocked_pending_provider_and_legal_choice",
  },
  guidance: {
    status: "insufficient_evidence",
    gaps: dimensions.filter((item) => item.missing > 0),
    expected_evidence_hash: "e".repeat(64),
    score_is_not_model_iq: true,
  },
};
"""


def test_strict_readiness_normalizer_markup_and_accessible_gaps() -> None:
    result = _run_module(
        VIEW_PATH,
        READINESS_FIXTURE
        + r"""
const normalized = subject.normalizeResearchCategoryLearning({
  status: fixture,
  unavailable: false,
  expectedRunId: runId,
});
const markup = subject.researchCategoryLearningMarkup(normalized, {
  saving: false,
  policyWritable: true,
});
const wrongVersion = structuredClone(fixture);
wrongVersion.version = "research-category-learning-readiness-v2";
const wrongRun = structuredClone(fixture);
wrongRun.run_id = "ffffffff-ffff-4fff-8fff-ffffffffffff";
const stringScore = structuredClone(fixture);
stringScore.metric.readiness.score = String(score);
const missingIdentity = structuredClone(fixture);
delete missingIdentity.source_ledger.items[0].source_identity_key;
const missingLineageLimit = structuredClone(fixture);
delete missingLineageLimit.source_ledger.lineage_history_limit_per_source;
const wrongLineageLimit = structuredClone(fixture);
wrongLineageLimit.source_ledger.lineage_history_limit_per_source = 9;
const invalidRetention = structuredClone(fixture);
invalidRetention.retained_youtube_evidence.items[0].retention_expires_at = "2026-09-02T14:00:00.000Z";
const stringAttemptCount = structuredClone(fixture);
stringAttemptCount.collection.history[0].transport_attempt_count = "0";
const completedIngestion = structuredClone(fixture);
completedIngestion.collection.history[0].ingestion_status = "completed";
completedIngestion.collection.history[0].ingestion_completed_at = "2026-08-03T15:05:00.000Z";
completedIngestion.collection.history[0].transport_attempt_count = 1;
const failedIngestion = structuredClone(fixture);
failedIngestion.collection.history[0].ingestion_status = "failed";
failedIngestion.collection.history[0].ingestion_error_code = "provider_unavailable";
failedIngestion.collection.history[0].ingestion_completed_at = "2026-08-03T15:05:00.000Z";
failedIngestion.collection.history[0].transport_attempt_count = 1;
const missingActualIngestion = structuredClone(fixture);
missingActualIngestion.collection.history[0].ingestion_status = null;
return {
  available: normalized.available,
  score: normalized.score,
  dimensions: normalized.dimensions.length,
  sources: normalized.sources.length,
  retainedYoutube: normalized.retainedYoutubeEvidence.length,
  lineageEvents: normalized.sources[0].lineageHistory.length,
  corrections: normalized.sources[0].analysisHistory.length,
  activePolicy: normalized.policies[0].status,
  queuedIngestion: normalized.collectionHistory[0].ingestionId,
  ingestionStatus: normalized.collectionHistory[0].ingestionStatus,
  wording: markup.includes("Готовность доказательной базы категории")
    && markup.includes("Это не IQ, не accuracy модели")
    && !markup.includes("обученность ИИ в процентах"),
  hover: markup.includes('title="Наблюдения конкурентов / сохранённые YouTube-каналы:'),
  keyboardTouch: markup.includes("<details class=\"product-research-learning-dimension")
    && markup.includes("aria-describedby=\"research-category-dimension-2\""),
  sourceLedger: markup.includes("youtube_data_api_v3")
    && markup.includes("История исправлений (2)")
    && markup.includes("source_identity_key") === false
    && markup.includes("Identity"),
  retainedLedger: markup.includes("Retained YouTube evidence")
    && markup.includes("creator_decide_research_youtube_candidate")
    && markup.includes("29 дней"),
  lineageHistory: markup.includes("История lineage (1)")
    && markup.includes("source_content_hash"),
  actualIngestion: markup.includes("Фактический ingestion:")
    && markup.includes("решение планировщика")
    && markup.includes("transport attempts 0/2"),
  exactHead: markup.includes('name="expected_head_event_id"')
    && markup.includes('name="expected_head_hash"'),
  controls: markup.includes("automatic_collection_ack")
    && markup.includes("terms_ack")
    && markup.includes("quota_ack")
    && markup.includes("no_retry_ack")
    && markup.includes("Только owner/admin"),
  wrongVersion: subject.normalizeResearchCategoryLearning({
    status: wrongVersion, expectedRunId: runId,
  }).available,
  wrongRun: subject.normalizeResearchCategoryLearning({
    status: wrongRun, expectedRunId: runId,
  }).available,
  stringScore: subject.normalizeResearchCategoryLearning({
    status: stringScore, expectedRunId: runId,
  }).available,
  missingIdentity: subject.normalizeResearchCategoryLearning({
    status: missingIdentity, expectedRunId: runId,
  }).available,
  missingLineageLimit: subject.normalizeResearchCategoryLearning({
    status: missingLineageLimit, expectedRunId: runId,
  }).available,
  wrongLineageLimit: subject.normalizeResearchCategoryLearning({
    status: wrongLineageLimit, expectedRunId: runId,
  }).available,
  invalidRetention: subject.normalizeResearchCategoryLearning({
    status: invalidRetention, expectedRunId: runId,
  }).available,
  stringAttemptCount: subject.normalizeResearchCategoryLearning({
    status: stringAttemptCount, expectedRunId: runId,
  }).available,
  completedIngestion: subject.normalizeResearchCategoryLearning({
    status: completedIngestion, expectedRunId: runId,
  }).available,
  failedIngestion: subject.normalizeResearchCategoryLearning({
    status: failedIngestion, expectedRunId: runId,
  }).available,
  missingActualIngestion: subject.normalizeResearchCategoryLearning({
    status: missingActualIngestion, expectedRunId: runId,
  }).available,
  invalidAnalysis: subject.normalizeResearchSourceAnalysisInput({
    arbitrary: true,
    raw_caption: "forbidden",
  }) === null,
};
""",
    )
    assert result == {
        "available": True,
        "score": 25,
        "dimensions": 6,
        "sources": 1,
        "retainedYoutube": 1,
        "lineageEvents": 1,
        "corrections": 2,
        "activePolicy": "enabled",
        "queuedIngestion": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        "ingestionStatus": "queued",
        "wording": True,
        "hover": True,
        "keyboardTouch": True,
        "sourceLedger": True,
        "retainedLedger": True,
        "lineageHistory": True,
        "actualIngestion": True,
        "exactHead": True,
        "controls": True,
        "wrongVersion": False,
        "wrongRun": False,
        "stringScore": False,
        "missingIdentity": False,
        "missingLineageLimit": False,
        "wrongLineageLimit": False,
        "invalidRetention": False,
        "stringAttemptCount": False,
        "completedIngestion": True,
        "failedIngestion": True,
        "missingActualIngestion": False,
        "invalidAnalysis": True,
    }


def test_api_mutations_are_exact_and_satellite_failure_does_not_block_research() -> None:
    result = _run_module(
        API_PATH,
        r"""
const ids = {
  run: "22222222-2222-4222-8222-222222222222",
  ledger: "66666666-6666-4666-8666-666666666666",
  event: "88888888-8888-4888-8888-888888888888",
  policy: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
};
const analysis = {
  schema_version: "research-source-interpretation-v1",
  classification: "competitor",
  relevance_score: 80,
  confidence: "medium",
  summary: "Структурное наблюдение о демонстрации товара без копирования чужого текста.",
  structural_signal_keys: ["hook.demonstration_first"],
  limitations: ["Только один публичный источник."],
};
const calls = [];
const api = Object.create(subject.CreatorApi.prototype);
api.mutate = async (rpc, payload) => {
  calls.push({ rpc, payload });
  if (rpc === "creator_correct_research_source_analysis") return {
    ok: true,
    event_id: ids.event,
    event_hash: "c".repeat(64),
    analysis_version: 2,
    origin: "human_correction",
    external_call_started: false,
  };
  if (rpc === "creator_configure_research_source_collection_policy") return {
    ok: true,
    policy: {
      policy_id: ids.policy,
      policy_hash: "1".repeat(64),
      policy_version: 1,
      platform: payload.platform,
      provider_key: payload.provider_key,
      status: payload.status,
      automatic_collection_ack: payload.automatic_collection_ack,
      terms_version: payload.terms_version,
      terms_ack: payload.terms_ack,
      quota_ack: payload.quota_ack,
      no_retry_ack: payload.no_retry_ack,
      cadence_hours: payload.cadence_hours,
      max_records: payload.max_records,
      monthly_hard_budget_units: payload.monthly_hard_budget_units,
    },
    capability: {
      automatic_enqueue_supported: true,
      external_call_started: false,
      queued_ingestion_is_claimed_by_internal_worker: true,
      instagram_enabled: false,
    },
  };
  throw new Error(`Unexpected RPC ${rpc}`);
};
await api.correctResearchSourceAnalysis({
  source_ledger_id: ids.ledger,
  expected_head_event_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  expected_head_hash: "d".repeat(64),
  analysis,
  correction_reason: "Проверено человеком по публичному источнику.",
});
await api.configureResearchSourceCollectionPolicy(ids.run, {
  platform: "youtube",
  provider_key: "youtube_data_api_v3",
  status: "enabled",
  automatic_collection_ack: true,
  terms_version: "youtube-developer-policies-2026-08-03-v1",
  terms_ack: true,
  quota_ack: true,
  no_retry_ack: true,
  cadence_hours: 168,
  max_records: 10,
  monthly_hard_budget_units: 10,
  legal_review_reference: "LEGAL-2026-08",
  reason: "Ограниченный автоматический сбор категории.",
  expected_policy_id: null,
  expected_policy_hash: null,
});
let invalidAnalysis = "";
try {
  await api.correctResearchSourceAnalysis({
    source_ledger_id: ids.ledger,
    expected_head_event_id: ids.event,
    expected_head_hash: "c".repeat(64),
    analysis: { raw_caption: "forbidden" },
    correction_reason: "Неверная схема.",
  });
} catch (error) {
  invalidAnalysis = error.code;
}
let missingAck = "";
try {
  await api.configureResearchSourceCollectionPolicy(ids.run, {
    platform: "youtube",
    provider_key: "youtube_data_api_v3",
    status: "enabled",
    automatic_collection_ack: true,
    terms_version: "youtube-developer-policies-2026-08-03-v1",
    terms_ack: false,
    quota_ack: true,
    no_retry_ack: true,
    cadence_hours: 168,
    max_records: 10,
    monthly_hard_budget_units: 10,
    legal_review_reference: "LEGAL-2026-08",
    reason: "Нет terms ack.",
    expected_policy_id: null,
    expected_policy_hash: null,
  });
} catch (error) {
  missingAck = error.code;
}

const satellite = Object.create(subject.CreatorApi.prototype);
satellite.organizationId = "11111111-1111-4111-8111-111111111111";
satellite.call = async (rpc) => {
  if (rpc === "creator_product_research_status") {
    return { run: { id: ids.run, status: "completed" } };
  }
  if (rpc === "creator_research_category_learning_status") {
    throw Object.assign(new Error("satellite down"), { code: "satellite_down" });
  }
  if (rpc === "creator_research_watchlist_status") {
    return { watchlist: null, snapshots: [] };
  }
  return {};
};
const originalWarn = console.warn;
console.warn = () => {};
const status = await satellite.productResearchStatus(ids.run);
console.warn = originalWarn;
return {
  correctionRpc: calls[0].rpc,
  exactHead: calls[0].payload.expected_head_event_id,
  policyRpc: calls[1].rpc,
  policyAcks: [
    calls[1].payload.automatic_collection_ack,
    calls[1].payload.terms_ack,
    calls[1].payload.quota_ack,
    calls[1].payload.no_retry_ack,
  ],
  expectedPair: [
    calls[1].payload.expected_policy_id,
    calls[1].payload.expected_policy_hash,
  ],
  invalidAnalysis,
  missingAck,
  mainStatus: status.run.status,
  learningUnavailable: status.research_category_learning_unavailable,
};
""",
    )
    assert result == {
        "correctionRpc": "creator_correct_research_source_analysis",
        "exactHead": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "policyRpc": "creator_configure_research_source_collection_policy",
        "policyAcks": [True, True, True, True],
        "expectedPair": [None, None],
        "invalidAnalysis": "research_source_correction_invalid",
        "missingAck": "research_collection_policy_invalid",
        "mainStatus": "completed",
        "learningUnavailable": True,
    }


def test_runtime_wiring_is_bounded_honest_and_mobile_safe() -> None:
    api = _read(API_PATH)
    app = _read(APP_PATH)
    view = _read(VIEW_PATH)
    css = _read(CSS_PATH)
    index = _read(INDEX_PATH)

    for rpc in (
        "creator_research_category_learning_status",
        "creator_capture_research_category_readiness",
        "creator_correct_research_source_analysis",
        "creator_configure_research_source_collection_policy",
    ):
        assert rpc in api
    assert "settleResearchSatellite(" in api
    assert '"research_category_learning_status"' in api
    assert "research_category_learning_unavailable = true" in api
    assert "product-research-readiness-capture-form" in app
    assert "product-research-source-correction-form" in app
    assert "product-research-collection-policy-form" in app
    assert "Политику автосбора может менять только owner/admin" in app
    assert "raw captions не хранятся" in view
    assert '"retained_youtube_evidence"' in view
    assert '"lineage_history_limit_per_source"' in view
    assert '"ingestion_status"' in view
    assert "Фактический ingestion:" in view
    assert "решение планировщика" in view
    assert "status/render без provider call" in view
    assert "automatic retry и provider fallback запрещены" in view
    assert "@media (hover: hover)" in css
    assert ":focus-within" in css
    assert "@media (max-width: 620px)" in css
    assert '"./supabase-api.js?v=20260803.7"' in app
    assert '"./product-research-view.js?v=20260803.9"' in app
    assert 'href="./product-research.css?v=20260803.8"' in index
    assert 'src="./app.js?v=20260803.os4.10"' in index
    assert "20260803.os4.8" not in index
