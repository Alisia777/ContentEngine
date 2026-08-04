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
APP_DIR = ROOT / "web" / "app"
APP_PATH = APP_DIR / "app.js"
API_PATH = APP_DIR / "supabase-api.js"
CATALOG_PATH = APP_DIR / "catalog.js"
LOADER_PATH = APP_DIR / "workspace-os-v4-loader.js"
CORE_PATH = APP_DIR / "workspace-os-v4.js"
ACTION_KEY_PATH = APP_DIR / "workspace-action-key.js"
VIEW_PATH = APP_DIR / "ai-learning-control-room.js"
CSS_PATH = APP_DIR / "ai-learning-control-room.css"
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608040002_ai_learning_control_room.sql"
)
GENERATION_SPEC_MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608030017_generation_spec_control.sql"
)

PRODUCT_CATEGORIES = (
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
)


def _read(path: Path) -> str:
    assert path.is_file(), f"Missing AI learning control-room asset: {path}"
    return path.read_text(encoding="utf-8")


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable AI learning UI contracts")
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


def _js_function(source: str, name: str) -> str:
    markers = (f"async function {name}(", f"function {name}(")
    starts = [source.find(marker) for marker in markers]
    starts = [index for index in starts if index >= 0]
    assert starts, f"Missing JavaScript function {name}"
    start = min(starts)
    next_markers = (
        source.find("\nasync function ", start + 1),
        source.find("\nfunction ", start + 1),
    )
    ends = [index for index in next_markers if index >= 0]
    return source[start : min(ends) if ends else len(source)]


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
    end = (
        match.end() + next_match.start()
        if next_match is not None
        else len(source)
    )
    return source[match.start() : end]


def _sql_policy(source: str, policy_name: str) -> str:
    match = re.search(
        rf"create\s+policy\s+{re.escape(policy_name)}\b.*?;",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, f"Missing SQL policy {policy_name}"
    return match.group(0)


AI_CONTROL_ROOM_FIXTURE = r"""
const organizationId = "10000000-0000-4000-8000-000000000001";
const runId = "20000000-0000-4000-8000-000000000001";
const categoryLabels = Object.freeze({
  cosmetics: "Косметика и уход",
  baa: "БАДы",
  sports_food: "Спортивное питание",
  food: "Продукты питания",
  household: "Товары для дома",
  apparel: "Одежда",
  electronics: "Электроника",
  other: "Другое",
});
const categoryKeys = Object.freeze(Object.keys(categoryLabels));
const dimensionSpecs = Object.freeze([
  ["source_volume", 20, 2, 12, "add_reviewable_source"],
  ["platform_diversity", 15, 1, 3, "add_independent_platform"],
  ["competitor_observations", 20, 2, 5, "add_competitor_observation"],
  ["trend_recency", 15, 0, 6, "refresh_trend_evidence"],
  ["analysis_coverage", 15, 2, 8, "analyze_source"],
  ["human_validation", 15, 2, 4, "validate_evidence"],
]);
const dimensions = dimensionSpecs.map(([key, weight, current, target, nextAction]) => {
  const score = Math.floor(100 * current / target);
  return {
    key,
    label: key.replaceAll("_", " "),
    weight,
    current,
    target,
    score,
    weighted_points: Math.floor(weight * score / 100),
    missing: target - current,
    next_action: nextAction,
  };
});
const evidenceScore = dimensions.reduce((sum, item) => sum + item.weighted_points, 0);
const teachingCard = {
  card_id: "30000000-0000-4000-8000-000000000001",
  card_version: 1,
  card_hash: "a".repeat(64),
  product_category: "cosmetics",
  signal_key: "hook.demonstration_first",
  ai_judgement: "good",
  status: "pending",
  evidence_count: 3,
  title: "Сначала показать товар в действии",
  explanation: "Гипотеза основана на трёх проверяемых исходах этой категории.",
};
const makeCategory = (key) => ({
  key,
  product_category: key,
  label: categoryLabels[key],
  readiness: {
    metric_kind: "category_evidence_readiness_not_model_iq",
    is_ai_iq: false,
    is_quality_guarantee: false,
    score: key === "cosmetics" ? evidenceScore : 0,
    dimensions: key === "cosmetics" ? dimensions : dimensions.map((item) => ({
      ...item,
      current: 0,
      score: 0,
      weighted_points: 0,
      missing: item.target,
    })),
    evidence_hash: key === "cosmetics" ? "b".repeat(64) : "c".repeat(64),
    as_of: "2026-08-04T10:00:00.000Z",
  },
  knowledge_sources: key === "cosmetics" ? [{
    source_id: "40000000-0000-4000-8000-000000000001",
    source_kind: "link",
    source_url: "https://example.com/category-guide",
    title: "Проверяемый источник категории",
    status: "active",
    created_at: "2026-08-04T09:00:00.000Z",
  }] : [],
  gaps: (key === "cosmetics" ? dimensions : dimensions.map((item) => ({
    ...item, current: 0, missing: item.target,
  }))).filter((item) => item.missing > 0),
  teaching_cards: key === "cosmetics" ? [teachingCard] : [],
});
const envelope = {
  ok: true,
  version: "ai-learning-control-room-v1",
  organization_id: organizationId,
  run_id: runId,
  state_version: 3,
  event_cursor: 9,
  as_of: "2026-08-04T10:00:00.000Z",
  categories: categoryKeys.map(makeCategory),
  guidance: {
    status: "needs_evidence",
    recommended_next_action: "add_category_source",
    score_is_not_model_iq: true,
    provider_action: false,
    generation_action: false,
    spend_action: false,
  },
  capabilities: {
    can_register_source: true,
    can_decide_teaching_card: true,
  },
};
"""


def test_ai_workspace_route_assets_and_bounded_polling_are_wired() -> None:
    catalog = _read(CATALOG_PATH)
    loader = _read(LOADER_PATH)
    core = _read(CORE_PATH)
    action_key = _read(ACTION_KEY_PATH)
    app = _read(APP_PATH)

    assert re.search(
        r"\[\s*[\"']ai[\"']\s*,\s*[\"']ИИ-центр[\"']\s*,",
        catalog,
    )
    assert "ai-learning-control-room.js" in app or "ai-learning-control-room.js" in loader
    assert "ai-learning-control-room.css" in loader
    assert 'route === "/workspace/ai"' in loader or "route === '/workspace/ai'" in loader
    assert re.search(
        r"\baiLearning\s*:\s*Object\.freeze\s*\(\s*\{.*?"
        r"/workspace/ai.*?ai-learning-control-room\.css",
        loader,
        flags=re.DOTALL,
    )
    assert "renderAiLearningSection" in app
    assert "loadAiLearningControlRoom" in app
    assert re.search(r"\bai\s*:\s*renderAiLearningSection\b", app)
    assert '[data-action="refresh-ai-learning"]' in core
    assert '"/workspace/ai": Object.freeze({' in action_key
    assert 'qualifiers: {' in action_key
    category_action = _js_function(app, "currentAiLearningCategory")
    view_action = _js_function(app, "currentAiLearningView")
    assert "workspaceActionDescriptor(state.route)" in category_action
    assert "workspaceActionDescriptor(state.route)" in view_action
    assert 'aiLearningCategory(requested, available[0] || "cosmetics")' in category_action
    assert '.query.get("category")' not in category_action
    assert '.query.get("view")' not in view_action

    load = _js_function(app, "loadAiLearningControlRoom")
    schedule = _js_function(app, "scheduleAiLearningPolling")
    stop = _js_function(app, "stopAiLearningPolling")
    polling_contract = "\n".join((load, schedule, stop))
    assert '"/workspace/ai"' in polling_contract or "'/workspace/ai'" in polling_contract
    assert "document.visibilityState" in polling_contract
    assert "setTimeout" in polling_contract
    assert "clearTimeout" in polling_contract
    assert "setInterval" not in polling_contract
    assert "requestId" in load
    assert "normalized.stateVersion < current.stateVersion" in load
    assert "normalized.eventCursor < current.eventCursor" in load
    assert "location.reload" not in polling_contract
    assert "window.location" not in polling_contract


def test_normalizer_markup_and_authoritative_mutations_execute_in_node() -> None:
    result = _run_module(
        VIEW_PATH,
        AI_CONTROL_ROOM_FIXTURE
        + r"""
const normalized = subject.normalizeAiLearningControlRoom(envelope, {
  category: "cosmetics",
});
const normalizedFood = subject.normalizeAiLearningControlRoom(envelope, {
  category: "food",
});
const markup = subject.aiLearningControlRoomMarkup(normalized, {
  category: "cosmetics",
  view: "overview",
  saving: false,
});
const wrongVersion = subject.normalizeAiLearningControlRoom({
  ...envelope,
  version: "ai-learning-control-room-v2",
});
const unknownCategory = subject.normalizeAiLearningControlRoom({
  ...envelope,
  categories: [...envelope.categories, makeCategory("pets")],
});
const missingCategory = subject.normalizeAiLearningControlRoom({
  ...envelope,
  categories: envelope.categories.slice(0, -1),
});
const duplicateCategory = subject.normalizeAiLearningControlRoom({
  ...envelope,
  categories: [...envelope.categories.slice(0, -1), makeCategory("electronics")],
});
const approvedEnvelope = structuredClone(envelope);
approvedEnvelope.state_version = 4;
approvedEnvelope.event_cursor = 10;
approvedEnvelope.categories[0].teaching_cards[0].status = "approved";
const afterApproved = subject.applyAiLearningControlRoomMutation(normalized, {
  ok: true,
  snapshot: approvedEnvelope,
});
const staleEnvelope = structuredClone(envelope);
staleEnvelope.state_version = 2;
staleEnvelope.event_cursor = 99;
staleEnvelope.categories[0].readiness.score = 99;
const afterStale = subject.applyAiLearningControlRoomMutation(afterApproved, {
  ok: true,
  snapshot: staleEnvelope,
});
const categoryOf = (value, key) => value.categories.find((item) => (
  item.productCategory === key
  || item.product_category === key
  || item.categoryKey === key
  || item.category_key === key
  || item.key === key
));
const selectedOf = (value) => (
  value.selectedCategoryKey
  || value.selected_category
  || (typeof value.selectedCategory === "string" ? value.selectedCategory : "")
  || value.selectedCategory?.productCategory
  || value.selectedCategory?.product_category
  || value.selectedCategory?.categoryKey
  || value.selectedCategory?.category_key
  || value.selectedCategory?.key
  || ""
);
const cosmetics = categoryOf(normalized, "cosmetics");
const staleCosmetics = categoryOf(afterStale, "cosmetics");
const approvedCategory = afterApproved.category || afterApproved.categoryDetail;
const approvedCard = approvedCategory.teachingCards?.[0]
  || approvedCategory.teaching_cards?.[0];
return {
  available: normalized.available,
  categories: normalized.categories.length,
  exactKeys: categoryKeys.every((key) => Boolean(categoryOf(normalized, key))),
  selected: selectedOf(normalizedFood),
  readinessDisclosure: normalized.guidance.scoreIsNotModelIq,
  score: cosmetics.score,
  wrongVersion: wrongVersion.available,
  unknownCategory: unknownCategory.available,
  missingCategory: missingCategory.available,
  duplicateCategory: duplicateCategory.available,
  categoryControls: categoryKeys.every((key) => markup.includes(key)),
  gapGuidance: markup.includes("Чего не хватает ИИ")
    && (markup.includes("Не хватает") || markup.includes("add_reviewable_source")),
  honestMetric: /evidence|доказательн/iu.test(markup)
    && /IQ/iu.test(markup)
    && /не|not/iu.test(markup),
  forms: [
    markup.includes('id="ai-knowledge-link-form"'),
    markup.includes('id="ai-knowledge-file-form"'),
    markup.includes('type="url"'),
    markup.includes('type="file"'),
  ],
  decisions: markup.includes('data-action="decide-ai-teaching-card"')
    && (markup.includes('value="approve"') || markup.includes('data-decision="approve"'))
    && (markup.includes('value="reject"') || markup.includes('data-decision="reject"')),
  exactDecisionIdentity: markup.includes('name="card_id"')
    && markup.includes('name="card_version"')
    && markup.includes('name="card_hash"')
    && markup.includes('name="expected_scope_version"'),
  accessibleStatus: markup.includes('aria-live=') || markup.includes('role="status"'),
  policyHeadingIds: [...markup.matchAll(/id="(ai-learning-policy-[^"]+-title)"/g)].map((match) => match[1]),
  authoritativeVersion: afterApproved.stateVersion ?? afterApproved.state_version,
  authoritativeCursor: afterApproved.eventCursor ?? afterApproved.event_cursor,
  authoritativeDecision: approvedCard.status,
  selectionPreserved: selectedOf(afterApproved),
  staleVersion: afterStale.stateVersion ?? afterStale.state_version,
  staleScore: staleCosmetics.score,
};
""",
    )

    assert result == {
        "available": True,
        "categories": 8,
        "exactKeys": True,
        "selected": "food",
        "readinessDisclosure": True,
        "score": 25,
        "wrongVersion": False,
        "unknownCategory": False,
        "missingCategory": False,
        "duplicateCategory": False,
        "categoryControls": True,
        "gapGuidance": True,
        "honestMetric": True,
        "forms": [True, True, True, True],
        "decisions": True,
        "exactDecisionIdentity": True,
        "accessibleStatus": True,
        "policyHeadingIds": [
            "ai-learning-policy-overview-title",
            "ai-learning-policy-history-title",
        ],
        "authoritativeVersion": 4,
        "authoritativeCursor": 10,
        "authoritativeDecision": "approved",
        "selectionPreserved": "cosmetics",
        "staleVersion": 4,
        "staleScore": 25,
    }


def test_browser_api_validates_source_and_decision_payloads_before_rpc() -> None:
    result = _run_module(
        API_PATH,
        AI_CONTROL_ROOM_FIXTURE
        + r"""
const calls = [];
const api = Object.create(subject.CreatorApi.prototype);
api.organizationId = organizationId;
api.storagePrefix = `${organizationId}/60000000-0000-4000-8000-000000000001/`;
api.call = async (rpc, payload) => {
  calls.push({ kind: "call", rpc, payload });
  return envelope;
};
api.mutate = async function (rpc, payload) {
  const scopedPayload = this.withOrganization(payload);
  calls.push({ kind: "mutate", rpc, payload: scopedPayload });
  return { ok: true, snapshot: envelope };
};
await api.aiLearningControlRoom({ category: "cosmetics" });
await api.registerAiKnowledgeSource({
  product_category: "cosmetics",
  source_kind: "link",
  source_url: "https://example.com/category-guide",
  title: "Проверяемый источник",
  rights_confirmed: true,
});
await api.registerAiKnowledgeSource({
  product_category: "food",
  source_kind: "file",
  object_key: `${api.storagePrefix}ai-knowledge/50000000-0000-4000-8000-000000000001.pdf`,
  title: "Паспорт товара",
  original_filename: "Паспорт товара.pdf",
  mime_type: "application/pdf",
  size_bytes: 4096,
  sha256: "d".repeat(64),
  rights_confirmed: true,
});
await api.decideAiTeachingCard({
  product_category: "cosmetics",
  card_id: teachingCard.card_id,
  card_version: teachingCard.card_version,
  card_hash: teachingCard.card_hash,
  expected_scope_version: envelope.state_version,
  decision: "approve",
  reason_code: "operator_confirmed",
  confirmation: true,
});
const beforeInvalid = calls.length;
const rejected = [];
for (const [name, operation] of [
  ["category", () => api.aiLearningControlRoom({ category: "pets" })],
  ["url", () => api.registerAiKnowledgeSource({ product_category: "food", source_kind: "link", source_url: "javascript:alert(1)", title: "bad", rights_confirmed: true })],
  ["rights", () => api.registerAiKnowledgeSource({ product_category: "food", source_kind: "link", source_url: "https://example.com/no-rights", title: "bad", rights_confirmed: false })],
  ["decision", () => api.decideAiTeachingCard({
    product_category: "cosmetics",
    card_id: teachingCard.card_id,
    card_version: 1,
    card_hash: teachingCard.card_hash,
    expected_scope_version: 3,
    decision: "good",
    reason_code: "operator_confirmed",
    confirmation: true,
  })],
  ["confirmation", () => api.decideAiTeachingCard({
    product_category: "cosmetics",
    card_id: teachingCard.card_id,
    card_version: 1,
    card_hash: teachingCard.card_hash,
    expected_scope_version: 3,
    decision: "reject",
    reason_code: "operator_rejected",
    confirmation: false,
  })],
]) {
  try { await operation(); }
  catch { rejected.push(name); }
}
return { calls, rejected, invalidReachedRpc: calls.length !== beforeInvalid };
""",
    )

    assert [item["rpc"] for item in result["calls"]] == [
        "creator_ai_learning_control_room",
        "creator_register_ai_knowledge_source",
        "creator_register_ai_knowledge_source",
        "creator_decide_ai_teaching_card",
    ]
    assert [item["kind"] for item in result["calls"]] == [
        "call",
        "mutate",
        "mutate",
        "mutate",
    ]
    assert result["rejected"] == [
        "category",
        "url",
        "rights",
        "decision",
        "confirmation",
    ]
    assert result["invalidReachedRpc"] is False

    read, link, file_source, decision = [
        item["payload"] for item in result["calls"]
    ]
    for payload in (read, link, file_source, decision):
        assert payload["organization_id"] == "10000000-0000-4000-8000-000000000001"
        assert payload.get("product_category", payload.get("category")) in PRODUCT_CATEGORIES
    assert link["source_url"] == "https://example.com/category-guide"
    assert link["source_kind"] == "link"
    assert link["rights_confirmed"] is True
    assert file_source["source_kind"] == "file"
    assert file_source["object_key"].endswith(".pdf")
    assert file_source["original_filename"] == "Паспорт товара.pdf"
    assert file_source["mime_type"] == "application/pdf"
    assert file_source["size_bytes"] == 4096
    assert file_source["sha256"] == "d" * 64
    assert file_source["rights_confirmed"] is True
    assert decision["decision"] == "approve"
    assert decision["confirmation"] is True
    assert decision["card_hash"] == "a" * 64
    assert decision["expected_scope_version"] == 3


def test_decision_handler_applies_the_authoritative_snapshot_without_side_effects() -> None:
    app = _read(APP_PATH)
    view = _read(VIEW_PATH)
    link = _js_function(app, "submitAiKnowledgeLink")
    file_source = _js_function(app, "submitAiKnowledgeFile")
    decision = _js_function(app, "decideAiTeachingCard")
    authoritative = _js_function(app, "applyAuthoritativeAiLearningResponse")
    finish_knowledge = _js_function(app, "finishAiKnowledgeMutation")

    assert 'id="ai-knowledge-link-form"' in view
    assert 'id="ai-knowledge-file-form"' in view
    assert 'data-action="decide-ai-teaching-card"' in view
    assert link.count("registerAiKnowledgeSource(") == 1
    assert file_source.count("registerAiKnowledgeSource(") == 1
    assert decision.count("decideAiTeachingCard(") >= 1
    assert "applyAuthoritativeAiLearningResponse" in decision
    assert "applyAiLearningControlRoomMutation" in authoritative
    assert "section.data = next" in authoritative
    api_call = decision.find("state.api.decideAiTeachingCard(")
    assert api_call >= 0
    assert api_call < decision.index(
        "applyAuthoritativeAiLearningResponse"
    )
    assert 'renderWorkspace("ai")' in decision or "renderWorkspace('ai')" in decision
    assert "stopAiLearningPolling()" in decision
    assert "state.aiLearning.requestId += 1" in decision

    for source_handler in (link, file_source):
        assert "state.aiLearning.knowledgeMutationKind" in source_handler
        assert "stopAiLearningPolling()" in source_handler
        assert "state.aiLearning.requestId += 1" in source_handler
        assert "finishAiKnowledgeMutation" in source_handler
    assert 'state.aiLearning.knowledgeMutationKind = ""' in finish_knowledge
    assert "document.getElementById(form.id)" in finish_knowledge
    assert "setFormBusy(candidate, false)" in finish_knowledge

    schedule = _js_function(app, "scheduleAiLearningPolling")
    poll = _js_function(app, "pollAiLearningControlRoom")
    assert "knowledgeMutationKind" in schedule
    assert "knowledgeMutationKind" in poll

    handlers = "\n".join((link, file_source, decision, authoritative))
    for forbidden in (
        "location.reload",
        "window.location",
        "startRealGeneration",
        "submitRealGeneration",
        "generationPreflight",
        "invokeProductResearch",
        "fetchWithTimeout",
        "confirmPlacement",
        "allow_real_spend",
        "real_spend_confirmation",
    ):
        assert forbidden not in handlers


def test_ai_control_room_css_is_responsive_accessible_and_motion_safe() -> None:
    css = _read(CSS_PATH)
    lowered = css.casefold()
    assert ".ai-learning" in css
    assert re.search(r"@media\s*\(max-width\s*:", css)
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css or ":focus-within" in css
    assert "grid-template-columns" in css
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert "animation" in reduced or "transition" in reduced
    assert "overflow-x" in lowered or "min-width: 0" in lowered
    assert css.count("{") == css.count("}")


def test_sql_wraps_existing_policy_and_keeps_mutations_category_isolated() -> None:
    sql = _read(MIGRATION_PATH)
    lowered = sql.casefold()
    assert parse_sql(sql)

    room = _sql_function(sql, "public.creator_ai_learning_control_room")
    register = _sql_function(sql, "public.creator_register_ai_knowledge_source")
    decide = _sql_function(sql, "public.creator_decide_ai_teaching_card")

    for category in PRODUCT_CATEGORIES:
        assert f"'{category}'" in lowered
    assert "category" in room.casefold()
    assert "creator_generation_learning_policy" in room.casefold()
    assert "product_category" in room.casefold()
    assert (
        "cross_category_learning_forbidden" in room.casefold()
        or "category_value" in room.casefold()
    )

    for function_source in (room, register, decide):
        function_lower = function_source.casefold()
        assert "security definer" in function_lower
        assert "set search_path = ''" in function_lower
        assert "organization_id" in function_lower
        assert "category" in function_lower

    assert "'link'" in register.casefold()
    assert "'file'" in register.casefold()
    for source_field in (
        "source_kind",
        "rights_confirmed",
        "object_key",
        "original_filename",
        "mime_type",
        "size_bytes",
        "sha256",
    ):
        assert source_field in register.casefold()
    assert "insert into" in register.casefold()
    assert "'approve'" in decide.casefold()
    assert "'reject'" in decide.casefold()
    assert "card_version" in decide.casefold()
    assert "card_hash" in decide.casefold()
    assert "expected_scope_version" in decide.casefold()
    assert "insert into" in decide.casefold()

    mutation_sql = f"{register}\n{decide}".casefold()
    for forbidden in (
        "creator_start_real_generation",
        "net.http",
        "http_post",
        "provider call",
        "allow_real_spend",
        "confirm_placement",
    ):
        assert forbidden not in mutation_sql

    for function_name in (
        "creator_ai_learning_control_room",
        "creator_register_ai_knowledge_source",
        "creator_decide_ai_teaching_card",
    ):
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+(?:public\.)?{function_name}",
            lowered,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+(?:public\.)?{function_name}",
            lowered,
        )


def test_knowledge_storage_mutations_enforce_the_rpc_role_contract() -> None:
    sql = _read(MIGRATION_PATH)
    assert parse_sql(sql)

    role_gate = _sql_function(
        sql,
        "content_factory.ai_knowledge_storage_role_allowed",
    ).casefold()
    assert "security definer" in role_gate
    assert "set search_path = ''" in role_gate
    assert "p_owner_id = auth.uid()::text" in role_gate
    assert "membership.status = 'active'" in role_gate
    assert "profile.status = 'active'" in role_gate
    assert "organization.status = 'active'" in role_gate
    for role in ("owner", "admin", "producer"):
        assert f"'{role}'" in role_gate
    for role in ("reviewer", "operator", "trainee", "viewer"):
        assert f"'{role}'" not in role_gate

    insert_policy = _sql_policy(sql, "contentengine_knowledge_insert").casefold()
    delete_policy = _sql_policy(sql, "contentengine_knowledge_delete").casefold()
    for policy in (insert_policy, delete_policy):
        assert "ai_knowledge_storage_role_allowed(" in policy
        assert "storage_access_allowed(" in policy
    assert "ai_knowledge_object_is_unregistered(" in delete_policy

    lowered = sql.casefold()
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"content_factory\.ai_knowledge_storage_role_allowed\(text,\s*text\)",
        lowered,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"content_factory\.ai_knowledge_storage_role_allowed\(text,\s*text\)",
        lowered,
    )


def test_knowledge_sha256_is_explicitly_client_declared_not_authoritative() -> None:
    sql = _read(MIGRATION_PATH)
    lowered = sql.casefold()
    assert parse_sql(sql)
    assert "'client_sha256', source.sha256" in lowered
    assert "'client_sha256', sha_value" in lowered
    assert "client_declared_not_server_recomputed" in lowered
    assert "not server-recomputed" in lowered
    assert "not authoritative content verification" in lowered
    assert "'sha256', source.sha256" not in lowered


def test_human_teaching_exits_mutable_exploration_before_live_provider_guard() -> None:
    migration = _read(MIGRATION_PATH)
    generation_spec = _read(GENERATION_SPEC_MIGRATION_PATH)
    assert parse_sql(migration)
    assert parse_sql(generation_spec)

    wrapper = _sql_function(
        migration,
        "public.creator_generation_learning_policy",
    ).casefold()
    live_claim = _sql_function(
        generation_spec,
        "content_factory_private.generation_spec_live_claim_snapshot",
    ).casefold()

    # The installed live-claim guard gives bounded exploration a narrow,
    # mutable two-arm allowance. A human category rule must never retain that
    # cursor while selecting any of the six teaching-card angles.
    assert re.search(
        r"expected_learning_policy\s*->>\s*'selection_mode'\s*=\s*"
        r"'bounded_exploration'",
        live_claim,
    )
    assert "selected_prior_use_count" in live_claim
    assert "'product_focus'" in live_claim
    assert "'demonstration'" in live_claim

    assert re.search(
        r"base_policy\s*-\s*'policy_hash'\s*-\s*'requested_model'\s*"
        r"-\s*'exploration'",
        wrapper,
    )
    assert re.search(
        r"'selection_mode'\s*,\s*'performance'",
        wrapper,
    )
    assert "'selection_provenance'" in wrapper
    assert "'ai-teaching-selection-provenance-v1'" in wrapper
    assert "'human_teaching_card_policy'" in wrapper
    assert "'deterministic', true" in wrapper
    assert "'base_policy_version'" in wrapper
    assert "'base_selection_mode'" not in wrapper
    assert "'base_policy_hash'" not in wrapper

    # The overlay removes only hash/model/exploration state. All independent
    # generation_allowed, rejection and quality guard fields stay inherited.
    assert "generation_allowed_preserved" in wrapper
    assert "rejection_guards_preserved" in wrapper
    assert "bounded_exploration_cursor_removed" in wrapper
