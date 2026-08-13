const ACTIVE_STATUSES = new Set(["queued", "starting", "researching", "processing", "running"]);
const READY_STATUSES = new Set(["ready", "completed", "succeeded", "draft", "approved"]);
export const PRODUCT_RESEARCH_AI_CATEGORIES = Object.freeze([
  Object.freeze({ value: "cosmetics", label: "Косметика и уход" }),
  Object.freeze({ value: "baa", label: "БАДы" }),
  Object.freeze({ value: "sports_food", label: "Спортивное питание" }),
  Object.freeze({ value: "food", label: "Еда и напитки" }),
  Object.freeze({ value: "household", label: "Товары для дома" }),
  Object.freeze({ value: "apparel", label: "Одежда и аксессуары" }),
  Object.freeze({ value: "electronics", label: "Электроника" }),
  Object.freeze({ value: "other", label: "Другая категория" }),
]);
const PRODUCT_RESEARCH_AI_CATEGORY_SET = new Set(
  PRODUCT_RESEARCH_AI_CATEGORIES.map(({ value }) => value),
);
const RESEARCH_OUTCOME_VERSION = "research-outcome-learning-control-v1";
const RESEARCH_OUTCOME_SCOPE_REGISTRY_VERSION = "research-outcome-scope-registry-v1";
const RESEARCH_OUTCOME_ANGLES = new Set([
  "product_focus",
  "trust_builder",
  "demonstration",
  "comparison",
  "objection_handling",
  "curiosity_gap",
]);
const RESEARCH_OUTCOME_PLATFORMS = new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]);
const RESEARCH_OUTCOME_MODELS = new Set([
  "gen4_turbo",
  "seedance2_fast",
  "seedream5_lite",
]);
const RESEARCH_YOUTUBE_VERSION = "research-youtube-live-ingestion-v1";
const RESEARCH_YOUTUBE_TERMS_VERSION =
  "youtube-developer-policies-2026-08-03-v1";
const RESEARCH_YOUTUBE_PROVIDER_KEY = "youtube_data_api_v3";
const RESEARCH_YOUTUBE_ADAPTER_VERSION =
  "youtube-data-api-v3-public-metadata-v1";
const RESEARCH_YOUTUBE_GLOBAL_STATES = new Set([
  "disabled",
  "canary_enabled",
  "controlled_rollout",
  "emergency_paused",
]);
const RESEARCH_YOUTUBE_STATUSES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
]);
const RESEARCH_PROVIDER_RESPONSE_STATUSES = new Set([
  "queued",
  "in_progress",
  "completed",
  "failed",
  "cancelled",
  "incomplete",
]);
const RESEARCH_UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const RESEARCH_PROVIDER_DIAGNOSTIC_TOKEN =
  /^[a-z0-9][a-z0-9._:-]{0,79}$/u;
const RESEARCH_YOUTUBE_TRANSPORT_FAILURE_CODES = new Set([
  "provider_configuration_error",
  "provider_authentication_failed",
  "provider_quota_exhausted",
  "provider_rate_limited",
  "provider_request_rejected",
  "provider_response_invalid",
  "provider_outcome_unknown",
  "provider_unavailable",
]);
const RESEARCH_YOUTUBE_ERROR_CODES = new Set([
  ...RESEARCH_YOUTUBE_TRANSPORT_FAILURE_CODES,
  "retention_control_unavailable",
  "category_binding_stale",
  "rollout_gate_closed",
  "ingestion_lease_expired",
  "internal_error",
]);
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_ERROR_CODES = new Set([
  "analysis_input_changed",
  "analysis_evidence_expired",
  "analysis_parser_failed",
]);
const RESEARCH_YOUTUBE_SAVING_PHASES = new Set([
  "youtube-canary",
  "youtube-refresh",
  "youtube-rollout",
  "youtube-candidate",
]);
const RESEARCH_YOUTUBE_NORMALIZED_VALUES = new WeakSet();
const RESEARCH_STAGE_CONTROL_VERSION = "research-stage-control-v2";
const RESEARCH_STAGE_ORDER = Object.freeze([
  "sources",
  "category",
  "competitors",
  "trends",
  "guidance",
  "brief",
  "scenarios",
]);
const RESEARCH_STAGE_CONTROL_ACTIONS = new Set([
  "patch",
  "reject",
  "revert",
  "fork",
  "recompute",
  "cancel",
]);
const RESEARCH_STAGE_CONTROL_STATES = new Set([
  "current",
  "stale_dependency",
  "rejected",
  "recompute_queued",
  "recompute_processing",
  "recompute_failed",
]);
const RESEARCH_STAGE_CONTROL_HASH_PATTERN = /^[0-9a-f]{64}$/u;
const RESEARCH_CATEGORY_LEARNING_VERSION =
  "research-category-learning-readiness-v2";
const RESEARCH_CATEGORY_LEARNING_VERSIONS = new Set([
  "research-category-learning-readiness-v1",
  RESEARCH_CATEGORY_LEARNING_VERSION,
]);
const RESEARCH_CATEGORY_READINESS_DEFINITION =
  "category-evidence-readiness-v3";
const RESEARCH_CATEGORY_READINESS_DEFINITIONS = new Set([
  "category-evidence-readiness-v1",
  "category-evidence-readiness-v2",
  RESEARCH_CATEGORY_READINESS_DEFINITION,
]);
const RESEARCH_CATEGORY_READINESS_MEANINGS = new Map([
  [
    "category-evidence-readiness-v1",
    "Coverage of durable evidence plus current retention-bound YouTube metadata",
  ],
  [
    "category-evidence-readiness-v2",
    "Coverage of durable evidence plus retention-bound YouTube metadata; only confirmed candidates add semantic credit",
  ],
  [
    RESEARCH_CATEGORY_READINESS_DEFINITION,
    "Coverage of durable evidence plus retention-bound YouTube metadata; deterministic parser heads add analysis coverage, while only human decisions add semantic credit",
  ],
]);
const RESEARCH_CATEGORY_READINESS_KIND =
  "category_evidence_readiness_not_model_iq";
const RESEARCH_CATEGORY_DIMENSIONS = Object.freeze([
  Object.freeze({
    key: "source_volume",
    label: "Current reviewable source volume",
    weight: 20,
    target: 12,
    nextAction: "collect_more_reviewable_sources",
  }),
  Object.freeze({
    key: "platform_diversity",
    label: "Platform diversity",
    weight: 15,
    target: 3,
    nextAction: "add_an_independent_platform",
  }),
  Object.freeze({
    key: "competitor_observations",
    label: "Competitor observations / retained YouTube channels",
    weight: 20,
    target: 5,
    nextAction: "collect_competitor_observations",
  }),
  Object.freeze({
    key: "trend_recency",
    label: "Recent canonical trend evidence",
    weight: 15,
    target: 6,
    nextAction: "refresh_canonical_trend_evidence",
  }),
  Object.freeze({
    key: "analysis_coverage",
    label: "Structured / normalized source coverage",
    weight: 15,
    target: 8,
    nextAction: "analyze_unreviewed_sources",
  }),
  Object.freeze({
    key: "human_validation",
    label: "Human-validated evidence",
    weight: 15,
    target: 4,
    nextAction: "review_and_correct_source_analysis",
  }),
]);
const RESEARCH_CATEGORY_GUIDANCE_STATUSES = new Set([
  "strong_evidence",
  "developing_evidence",
  "insufficient_evidence",
]);
const RESEARCH_CATEGORY_SOURCE_TYPES = new Set([
  "user_input",
  "product_photo",
  "marketplace_page",
  "review",
  "competitor",
  "social_video",
  "market_data",
  "other",
]);
const RESEARCH_CATEGORY_SOURCE_PLATFORMS = new Set([
  "youtube",
  "instagram",
  "marketplace",
  "web",
  "first_party",
  "other",
]);
const RESEARCH_CATEGORY_TRUST_LEVELS = new Set([
  "first_party",
  "official",
  "public",
  "unverified",
]);
const RESEARCH_CATEGORY_POLICY_PLATFORMS = new Set([
  "youtube",
  "instagram",
]);
const RESEARCH_CATEGORY_PROVIDER_PATTERN = /^[a-z][a-z0-9_.-]{1,79}$/u;
const RESEARCH_CATEGORY_ANALYSIS_ORIGINS = new Set([
  "system_parser",
  "human_correction",
]);
const RESEARCH_TREND_VELOCITY_VERSION =
  "approved-structural-support-velocity-v1";
const RESEARCH_TREND_VELOCITY_MODES = new Set([
  "baseline",
  "comparable",
  "category_reset",
  "signal_new",
  "signal_removed",
  "interval_too_short",
]);
const RESEARCH_TREND_SUPPORT_STATES = new Set([
  "no_velocity_claim",
  "support_breadth_increasing",
  "support_breadth_decreasing",
  "support_breadth_stable",
]);
const RESEARCH_TREND_DIRECTIONS = new Set([
  "emerging",
  "growing",
  "stable",
  "declining",
  "unclear",
]);
const RESEARCH_CATEGORY_INTENT_BLOCKERS = new Set([
  "category_binding_stale",
  "provider_contract_closed",
  "retention_control_unavailable",
  "global_rollout_gate_closed",
  "organization_rollout_gate_closed",
  "monthly_hard_budget_exhausted",
  "instagram_provider_legal_choice_required",
  "policy_creator_inactive",
  "category_inactive",
  "policy_ack_invalid",
]);
const RESEARCH_CATEGORY_YOUTUBE_DECISIONS = new Set([
  "confirm_candidate",
  "exclude_candidate",
]);
const RESEARCH_CATEGORY_ANALYSIS_FORBIDDEN_KEYS = new Set([
  "caption",
  "captions",
  "raw_caption",
  "raw_captions",
  "transcript",
  "transcripts",
  "raw_transcript",
  "raw_transcripts",
  "raw_text",
  "source_text",
  "full_text",
]);
const RESEARCH_CATEGORY_ANALYSIS_SCHEMA =
  "research-source-interpretation-v1";
const RESEARCH_CATEGORY_ANALYSIS_CLASSIFICATIONS = new Set([
  "competitor",
  "adjacent",
  "trend_signal",
  "reference",
  "irrelevant",
  "unknown",
]);
const RESEARCH_CATEGORY_ANALYSIS_CONFIDENCE = new Set([
  "low",
  "medium",
  "high",
]);
const RESEARCH_CATEGORY_STRUCTURAL_SIGNAL_PATTERN =
  /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$/u;
const RESEARCH_CATEGORY_YOUTUBE_TERMS_VERSION =
  "youtube-developer-policies-2026-08-03-v1";
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA =
  "research-youtube-observation-analysis-v1";
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS = new Set([
  "potential_competitor",
  "adjacent",
  "unknown",
]);
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_RECOMMENDATIONS = new Set([
  "review_candidate",
  "needs_more_evidence",
]);
const RESEARCH_YOUTUBE_OBSERVATION_JOB_STATUSES = new Set([
  "approval_required",
  "queued",
  "processing",
  "completed",
  "failed",
]);

function researchInputContextFromObjective(value) {
  const objective = String(value || "").trim().slice(0, 2_000);
  const lines = objective.split(/\r?\n/u);
  const firstLine = String(lines[0] || "").toLowerCase();
  const focusPrefix = "Приоритет исследования: ";
  const competitorHeader =
    "Ориентиры конкурентов пользователя (проверить публичными источниками, не копировать):";
  const factsPrefix = "Подтверждённые вводные пользователя: ";
  const researchFocus = String(
    lines.find((line) => line.startsWith(focusPrefix)) || "",
  ).slice(focusPrefix.length).trim().slice(0, 200);
  const knownFacts = String(
    lines.find((line) => line.startsWith(factsPrefix)) || "",
  ).slice(factsPrefix.length).trim().slice(0, 500);
  const competitorHeaderIndex = lines.findIndex(
    (line) => line === competitorHeader,
  );
  const competitorReferences = competitorHeaderIndex < 0
    ? ""
    : lines.slice(competitorHeaderIndex + 1)
      .filter((line) => !line.startsWith(factsPrefix))
      .join("\n")
      .trim()
      .slice(0, 650);
  const objectiveKey = firstLine.includes("ugc-обзор")
    ? "ugc"
    : firstLine.includes("узнаваемост")
      ? "awareness"
      : firstLine.includes("применение товара")
        ? "education"
        : "conversion";
  return {
    objective,
    objectiveKey,
    researchFocus,
    competitorReferences,
    knownFacts,
  };
}

function normalizeExactVideoEvidence(value) {
  const source = objectValue(value) || {};
  const oneUuid = (snakeKey, camelKey) => {
    const candidate = String(source[snakeKey] || source[camelKey] || "")
      .trim()
      .toLowerCase();
    return RESEARCH_UUID_PATTERN.test(candidate) ? candidate : "";
  };
  const frameCount = Number(source.frame_count ?? source.frameCount);
  const normalized = {
    verified: source.verified === true,
    markerSource: String(
      source.marker_source || source.markerSource || "",
    ).trim(),
    bindingId: oneUuid("binding_id", "bindingId"),
    sourceId: oneUuid("source_id", "sourceId"),
    attachmentId: oneUuid("attachment_id", "attachmentId"),
    mediaId: oneUuid("media_id", "mediaId"),
    evidenceId: oneUuid("evidence_id", "evidenceId"),
    frameCount: Number.isSafeInteger(frameCount) ? frameCount : 0,
    analysisScope: String(
      source.analysis_scope || source.analysisScope || "",
    ).trim().toLowerCase(),
    fullStreamAccess: source.full_stream_access === true
      || source.fullStreamAccess === true,
    transcriptAvailable: source.transcript_available === true
      || source.transcriptAvailable === true,
    mediaMatchesRegisteredSource:
      source.media_matches_registered_source === true
      || source.mediaMatchesRegisteredSource === true,
  };
  const valid = normalized.verified
    && normalized.markerSource === "server_exact_video_binding"
    && normalized.bindingId
    && normalized.sourceId
    && normalized.attachmentId
    && normalized.mediaId
    && normalized.evidenceId
    && normalized.frameCount === 5
    && normalized.analysisScope === "sampled_frames_only"
    && !normalized.fullStreamAccess
    && !normalized.transcriptAvailable
    && normalized.mediaMatchesRegisteredSource;
  return valid ? normalized : null;
}

function normalizeProductResearchStatusContext(value) {
  const source = objectValue(value) || {};
  const runId = String(source.run_id || "").trim().toLowerCase();
  const projectId = String(source.project_id || "").trim().toLowerCase();
  const ownership = String(source.ownership || "").trim().toLowerCase();
  if (
    !RESEARCH_UUID_PATTERN.test(runId)
    || !RESEARCH_UUID_PATTERN.test(projectId)
    || !["own", "project"].includes(ownership)
  ) return null;
  const category = normalizeProductResearchAiCategory(
    source.product_category,
  );
  const receiptSource = objectValue(source.ai_receipt) || {};
  const receiptId = String(receiptSource.receipt_id || "")
    .trim()
    .toLowerCase();
  const aiReceipt = receiptId && RESEARCH_UUID_PATTERN.test(receiptId)
    ? {
        receiptId,
        status: String(receiptSource.status || "").trim().toLowerCase(),
      }
    : null;
  return {
    runId,
    projectId,
    ownership,
    productCategory: category,
    aiReceipt,
  };
}

export function productResearchStatusMatchesContext(
  record,
  { runId = "", projectId = "", runScope = "none" } = {},
) {
  const expectedRunId = String(runId || "").trim().toLowerCase();
  const expectedProjectId = String(projectId || "").trim().toLowerCase();
  if (
    !RESEARCH_UUID_PATTERN.test(expectedRunId)
    || !RESEARCH_UUID_PATTERN.test(expectedProjectId)
    || record?.statusAuthorityVerified !== true
    || String(record?.id || "").trim().toLowerCase() !== expectedRunId
    || String(record?.projectId || "").trim().toLowerCase()
      !== expectedProjectId
  ) return false;
  if (runScope === "own") return record?.ownership === "own";
  return runScope === "project"
    && ["own", "project"].includes(record?.ownership);
}

export function productResearchRequestContextMatches(
  captured,
  { requestId = 0, projectId = "" } = {},
) {
  return Number.isSafeInteger(captured?.requestId)
    && captured.requestId === Number(requestId)
    && RESEARCH_UUID_PATTERN.test(String(captured?.projectId || ""))
    && captured.projectId === String(projectId || "").trim().toLowerCase();
}

export function normalizeProductResearch(raw, previous = null) {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  const run = objectValue(root.run) || objectValue(root.research) || root;
  const statusContext = normalizeProductResearchStatusContext(
    root.research_context,
  );
  const result = objectValue(run.result) || objectValue(root.result) || {};
  const analysis = objectValue(run.analysis) || objectValue(result.analysis) || objectValue(root.analysis) || result;
  const latestDraft = objectValue(root.latest_draft) || objectValue(root.draft) || objectValue(run.latest_draft) || {};
  const latestBrief = objectValue(latestDraft.brief) || {};
  const summary = objectValue(run.summary) || objectValue(root.summary) || {};
  const rawResearchInput = {
    ...(objectValue(previous?.researchInput) || {}),
    ...(objectValue(run.input) || objectValue(root.input) || {}),
  };
  const recoveredResearchInput = researchInputContextFromObjective(
    rawResearchInput.objective,
  );
  const researchInput = {
    productCategory: normalizeProductResearchAiCategory(
      rawResearchInput.product_category || rawResearchInput.productCategory,
    ),
    objective: recoveredResearchInput.objective,
    objectiveKey: String(
      rawResearchInput.objective_key
        || rawResearchInput.objectiveKey
        || recoveredResearchInput.objectiveKey,
    ).trim().slice(0, 32),
    marketplaceUrl: String(
      rawResearchInput.marketplace_url || rawResearchInput.marketplaceUrl || "",
    ).trim().slice(0, 2_048),
    sourceMediaIds: stringArray(
      rawResearchInput.source_media_ids || rawResearchInput.sourceMediaIds,
    ).slice(0, 5),
    platforms: stringArray(rawResearchInput.platforms).slice(0, 8),
    researchFocus: String(
      rawResearchInput.research_focus
        || rawResearchInput.researchFocus
        || recoveredResearchInput.researchFocus,
    ).trim().slice(0, 200),
    competitorReferences: String(
      rawResearchInput.competitor_references
        || rawResearchInput.competitorReferences
        || recoveredResearchInput.competitorReferences,
    ).trim().slice(0, 650),
    knownFacts: String(
      rawResearchInput.known_facts
        || rawResearchInput.knownFacts
        || recoveredResearchInput.knownFacts,
    ).trim().slice(0, 500),
  };
  const exactVideo = normalizeExactVideoEvidence(
    run.exact_video || root.exact_video,
  );
  const forecast = objectValue(arrayValue(root.forecasts)[0]) || objectValue(root.forecast) || {};
  const prediction = objectValue(analysis.prediction)
    || objectValue(analysis.forecast)
    || objectValue(latestBrief.creative_potential)
    || objectValue(summary.creative_potential)
    || forecast;
  const briefSource = Object.keys(latestBrief).length
    ? { ...latestBrief, title: latestDraft.title || latestBrief.title }
    : objectValue(run.brief_draft)
      || objectValue(run.brief)
      || objectValue(analysis.brief)
      || objectValue(result.brief)
      || previous?.brief;
  const envelopeBrief = objectValue(run.brief_draft)
    || objectValue(run.brief)
    || objectValue(analysis.brief)
    || objectValue(result.brief)
    || {};
  const rawBrief = Object.keys(latestBrief).length
    ? latestBrief
    : Object.keys(envelopeBrief).length
      ? envelopeBrief
      : (previous?.rawBrief || {});
  const hasCategoryAnalysis = Boolean(
    rawBrief?.category_analysis
    && typeof rawBrief.category_analysis === "object"
    && !Array.isArray(rawBrief.category_analysis),
  );
  const brief = normalizeBrief(briefSource);
  const scenarios = normalizeScenarios(
    arrayValue(brief.scenarios).length
      ? brief.scenarios
      : arrayValue(analysis.scenarios).length
        ? analysis.scenarios
        : arrayValue(result.scenarios).length
          ? result.scenarios
          : previous?.scenarios,
  );
  const score = clampScore(
    prediction.score
      ?? prediction.success_score
      ?? analysis.success_score
      ?? analysis.score
      ?? run.success_score
      ?? previous?.score,
  );
  const taskIds = [root.task_ids, run.task_ids, result.task_ids, previous?.taskIds]
    .map(stringArray)
    .find((items) => items.length) || [];
  const rawApproval = root.approval ?? run.approval ?? result.approval ?? previous?.approval ?? null;
  const approval = objectValue(rawApproval) || {};
  const approvalStatus = String(
    typeof rawApproval === "string" ? rawApproval : approval.status || latestDraft.status || "",
  ).toLowerCase();
  const approved = rawApproval === true
    || approvalStatus === "approved"
    || Boolean(approval.approved_at || approval.approvedAt)
    || taskIds.length > 0
    || previous?.approved === true;
  const runStatus = String(run.status || root.status || previous?.status || "queued").toLowerCase();
  const status = approved ? "approved" : runStatus;
  const id = String(run.id || root.run_id || root.research_id || root.id || previous?.id || "");
  const recommendedScenarioPosition = normalizeRecommendedScenarioPosition(
    prediction.recommended_scenario_position
      ?? prediction.recommendedScenarioPosition
      ?? previous?.recommendedScenarioPosition,
  );
  const recommendedScenarioReason = String(
    prediction.recommended_scenario_reason
      || prediction.recommendedScenarioReason
      || previous?.recommendedScenarioReason
      || "",
  ).replace(/\s+/gu, " ").trim().slice(0, 500);
  const categoryAnalysis = normalizeCategoryAnalysis(
    latestBrief.category_analysis
      || summary.category_analysis
      || analysis.category_analysis
      || result.category_analysis
      || previous?.categoryAnalysis,
  );
  const competitorAnalysis = normalizeCompetitorAnalysis(
    latestBrief.competitor_analysis
      || summary.competitor_analysis
      || analysis.competitor_analysis
      || result.competitor_analysis
      || previous?.competitorAnalysis,
  );
  const trendAnalysis = normalizeTrendAnalysis(
    latestBrief.trend_analysis
      || summary.trend_analysis
      || analysis.trend_analysis
      || result.trend_analysis
      || previous?.trendAnalysis,
  );
  const guidance = normalizeResearchGuidance(
    latestBrief.guidance
      || summary.guidance
      || analysis.guidance
      || result.guidance
      || previous?.guidance,
  );
  const humanResearchDecision = normalizeHumanResearchDecision(
    latestBrief.human_research_decision
      || briefSource?.human_research_decision
      || previous?.humanResearchDecision,
  );
  const hasWatchlistEnvelope = [
    "watchlist",
    "watchlist_history",
    "watchlist_proposal",
    "watchlist_guidance",
    "watchlist_monitor_unavailable",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const watchlist = hasWatchlistEnvelope
    ? normalizeResearchWatchlist({
      watchlist: root.watchlist,
      snapshots: root.watchlist_history,
      proposal: root.watchlist_proposal,
      guidance: root.watchlist_guidance,
      unavailable: root.watchlist_monitor_unavailable === true,
    })
    : (previous?.watchlist || null);
  const hasProviderControlEnvelope = [
    "research_provider_control",
    "research_provider_control_unavailable",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const providerControl = hasProviderControlEnvelope
    ? normalizeResearchProviderControl({
      control: root.research_provider_control,
      unavailable: root.research_provider_control_unavailable === true,
    })
    : (previous?.providerControl || null);
  const hasMarketRegistryEnvelope = [
    "research_market_registry",
    "research_market_registry_unavailable",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const marketRegistry = hasMarketRegistryEnvelope
    ? normalizeResearchMarketRegistry({
      registry: root.research_market_registry,
      unavailable: root.research_market_registry_unavailable === true,
    })
    : (previous?.marketRegistry || null);
  const hasCategoryLearningEnvelope = [
    "research_category_learning",
    "research_category_learning_unavailable",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const categoryLearning = hasCategoryLearningEnvelope
    ? normalizeResearchCategoryLearning({
      status: root.research_category_learning,
      unavailable: root.research_category_learning_unavailable === true,
      expectedRunId: id,
    })
    : (previous?.categoryLearning || null);
  const hasOutcomeScopeRegistryEnvelope = [
    "research_outcome_scope_registry",
    "research_outcome_scope_registry_unavailable",
    "research_outcome_learning_scope",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const outcomeScopeRegistry = hasOutcomeScopeRegistryEnvelope
    ? normalizeResearchOutcomeScopeRegistry({
      registry: root.research_outcome_scope_registry,
      unavailable: root.research_outcome_scope_registry_unavailable === true,
      selectedScope: root.research_outcome_learning_scope,
    })
    : (previous?.outcomeScopeRegistry || null);
  const hasOutcomeLearningEnvelope = [
    "research_outcome_learning",
    "research_outcome_learning_unavailable",
    "research_outcome_learning_scope",
    "research_outcome_learning_scope_missing",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const outcomeLearning = hasOutcomeLearningEnvelope
    ? normalizeResearchOutcomeLearning({
      control: root.research_outcome_learning,
      unavailable: root.research_outcome_learning_unavailable === true,
      scope: root.research_outcome_learning_scope,
      scopeMissing: root.research_outcome_learning_scope_missing === true,
    })
    : (previous?.outcomeLearning || null);
  const hasYoutubeEnvelope = [
    "research_youtube_overview",
    "research_youtube_overview_unavailable",
    "research_youtube_latest",
    "research_youtube_latest_unavailable",
  ].some((key) => Object.prototype.hasOwnProperty.call(root, key));
  const youtubeResearch = hasYoutubeEnvelope
    ? normalizeResearchYoutube({
      overview: root.research_youtube_overview,
      overviewUnavailable: root.research_youtube_overview_unavailable === true,
      latest: root.research_youtube_latest,
      latestUnavailable: root.research_youtube_latest_unavailable === true,
    })
    : (previous?.youtubeResearch || null);

  return {
    id,
    projectId: statusContext?.projectId || "",
    ownership: statusContext?.ownership || "",
    statusAuthorityVerified: Boolean(
      statusContext && statusContext.runId === String(id).trim().toLowerCase()
    ),
    statusProductCategory: statusContext?.productCategory || "",
    aiReceipt: statusContext?.aiReceipt || null,
    status,
    productName: String(run.product_name || run.product?.name || root.product_name || previous?.productName || ""),
    sku: String(run.sku || run.product?.sku || root.sku || previous?.sku || ""),
    score,
    confidence: normalizeConfidence(prediction.confidence_label || prediction.confidence || analysis.confidence || run.confidence || previous?.confidence),
    forecastSummary: String(prediction.summary || prediction.explanation || forecast.factors?.summary || analysis.forecast_summary || previous?.forecastSummary || ""),
    factors: normalizeFactors(forecast.factors || prediction.factors || analysis.score_factors || analysis.factors || previous?.factors),
    sources: normalizeSources(root.sources || run.sources || analysis.sources || result.sources || previous?.sources),
    brief: { ...brief, scenarios },
    rawBrief,
    hasCategoryAnalysis,
    rawTaskBlueprint: arrayValue(latestDraft.task_blueprint).length ? latestDraft.task_blueprint : (previous?.rawTaskBlueprint || []),
    draftId: String(approval.draft_id || approval.draftId || latestDraft.id || root.draft_id || previous?.draftId || ""),
    sourceIds: stringArray(latestDraft.source_ids).length
      ? stringArray(latestDraft.source_ids)
      : stringArray(root.source_ids).length
        ? stringArray(root.source_ids)
      : normalizeSources(root.sources || run.sources).map((source) => source.id).filter(Boolean).length
        ? normalizeSources(root.sources || run.sources).map((source) => source.id).filter(Boolean)
        : stringArray(previous?.sourceIds),
    scenarios,
    recommendedScenarioPosition,
    recommendedScenarioIndex: recommendedScenarioPosition
      ? recommendedScenarioPosition - 1
      : -1,
    recommendedScenarioReason,
    categoryAnalysis,
    competitorAnalysis,
    trendAnalysis,
    guidance,
    watchlist,
    providerControl,
    marketRegistry,
    categoryLearning,
    outcomeScopeRegistry,
    outcomeLearning,
    youtubeResearch,
    researchInput,
    exactVideo,
    humanResearchDecision,
    stageCorrections: normalizeStageCorrections(
      latestBrief.human_stage_corrections
        || briefSource?.human_stage_corrections
        || previous?.stageCorrections,
    ),
    approval,
    approved,
    taskIds,
    statusNotice: String(root.status_notice || root.statusNotice || previous?.statusNotice || ""),
    failureCode: String(
      run.error_code || run.failure_code || root.error_code
        || root.failure_code || previous?.failureCode || "",
    ).trim().toLowerCase(),
    failureMessage: String(run.error_message || run.failure_message || root.error_message || root.failure_message || root.error?.message || ""),
    updatedAt: String(run.updated_at || root.updated_at || previous?.updatedAt || ""),
  };
}

function researchCategoryLearningUnavailable(expectedRunId, reason) {
  return {
    available: false,
    version: RESEARCH_CATEGORY_LEARNING_VERSION,
    runId: String(expectedRunId || "").trim().toLowerCase(),
    reason,
    dimensions: [],
    sources: [],
    retainedYoutubeEvidence: [],
    readinessHistory: [],
    policies: [],
    collectionHistory: [],
    gaps: [],
    providerStrategy: null,
  };
}

function researchCategoryExactObject(value, keys) {
  const source = objectValue(value);
  return source
      && Object.keys(source).length === keys.length
      && keys.every((key) => Object.prototype.hasOwnProperty.call(source, key))
    ? source
    : null;
}

function researchCategoryDimensionList(value) {
  if (!Array.isArray(value) || value.length !== RESEARCH_CATEGORY_DIMENSIONS.length) {
    return null;
  }
  const normalized = [];
  for (let index = 0; index < RESEARCH_CATEGORY_DIMENSIONS.length; index += 1) {
    const expected = RESEARCH_CATEGORY_DIMENSIONS[index];
    const item = researchCategoryExactObject(value[index], [
      "key",
      "label",
      "weight",
      "current",
      "target",
      "score",
      "weighted_points",
      "missing",
      "next_action",
    ]);
    if (!item) return null;
    const current = item.current;
    const score = item.score;
    const weightedPoints = item.weighted_points;
    const missing = item.missing;
    const expectedScore = Math.min(100, Math.floor((100 * current) / expected.target));
    const expectedWeightedPoints = Math.min(
      expected.weight,
      Math.floor((expected.weight * expectedScore) / 100),
    );
    const expectedMissing = Math.max(expected.target - current, 0);
    if (
      item.key !== expected.key
      || item.label !== expected.label
      || item.weight !== expected.weight
      || item.target !== expected.target
      || !Number.isSafeInteger(current)
      || current < 0
      || !Number.isSafeInteger(score)
      || score !== expectedScore
      || !Number.isSafeInteger(weightedPoints)
      || weightedPoints !== expectedWeightedPoints
      || !Number.isSafeInteger(missing)
      || missing !== expectedMissing
      || (missing === 0
        ? item.next_action !== null
        : item.next_action !== expected.nextAction)
    ) return null;
    normalized.push({
      key: expected.key,
      label: expected.label,
      weight: expected.weight,
      current,
      target: expected.target,
      score,
      weightedPoints,
      missing,
      nextAction: item.next_action,
    });
  }
  return normalized;
}

function researchCategoryAnalysisHasForbiddenKeys(value) {
  const pending = [value];
  let visited = 0;
  while (pending.length) {
    const current = pending.pop();
    if (!current || typeof current !== "object") continue;
    visited += 1;
    if (visited > 10_000) return true;
    if (Array.isArray(current)) {
      pending.push(...current);
      continue;
    }
    for (const [key, child] of Object.entries(current)) {
      if (RESEARCH_CATEGORY_ANALYSIS_FORBIDDEN_KEYS.has(key.toLowerCase())) {
        return true;
      }
      if (child && typeof child === "object") pending.push(child);
    }
  }
  return false;
}

function researchCategoryAnalysisPayload(value) {
  const analysis = objectValue(value);
  const exactKeys = [
    "schema_version",
    "classification",
    "relevance_score",
    "confidence",
    "summary",
    "structural_signal_keys",
    "limitations",
  ];
  if (
    !analysis
    || Object.keys(analysis).length !== exactKeys.length
    || exactKeys.some((key) =>
      !Object.prototype.hasOwnProperty.call(analysis, key)
    )
    || analysis.schema_version !== RESEARCH_CATEGORY_ANALYSIS_SCHEMA
    || !RESEARCH_CATEGORY_ANALYSIS_CLASSIFICATIONS.has(
      analysis.classification,
    )
    || !Number.isInteger(analysis.relevance_score)
    || analysis.relevance_score < 0
    || analysis.relevance_score > 100
    || !RESEARCH_CATEGORY_ANALYSIS_CONFIDENCE.has(analysis.confidence)
    || typeof analysis.summary !== "string"
    || analysis.summary.trim().length < 20
    || analysis.summary.trim().length > 2_000
    || !Array.isArray(analysis.structural_signal_keys)
    || analysis.structural_signal_keys.length > 20
    || !Array.isArray(analysis.limitations)
    || analysis.limitations.length > 20
    || researchCategoryAnalysisHasForbiddenKeys(analysis)
  ) return null;
  const structuralSignals = analysis.structural_signal_keys.map((item) =>
    typeof item === "string" ? item.trim() : ""
  );
  if (
    structuralSignals.some((item) =>
      item.length < 3
      || item.length > 100
      || !RESEARCH_CATEGORY_STRUCTURAL_SIGNAL_PATTERN.test(item)
    )
    || new Set(structuralSignals).size !== structuralSignals.length
    || analysis.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
  ) return null;
  try {
    if (new TextEncoder().encode(JSON.stringify(analysis)).length > 32_768) {
      return null;
    }
  } catch {
    return null;
  }
  return analysis;
}

export function normalizeResearchSourceAnalysisInput(value) {
  return researchCategoryAnalysisPayload(value);
}

function researchCategoryAnalysisEvent(value, { history = false } = {}) {
  const keys = history
    ? [
        "event_id",
        "analysis_version",
        "parent_event_id",
        "origin",
        "actor_id",
        "parser_key",
        "parser_version",
        "analysis",
        "correction_reason",
        "event_hash",
        "created_at",
      ]
    : [
        "event_id",
        "analysis_version",
        "origin",
        "parser_key",
        "parser_version",
        "analysis",
        "correction_reason",
        "event_hash",
        "created_at",
      ];
  const source = researchCategoryExactObject(value, keys);
  if (!source) return null;
  const eventId = researchOutcomeUuid(source.event_id);
  const analysisVersion = source.analysis_version;
  const origin = String(source.origin || "");
  const parserKey = String(source.parser_key || "");
  const parserVersion = String(source.parser_version || "").trim();
  const analysis = researchCategoryAnalysisPayload(source.analysis);
  const eventHash = researchYoutubeHash(source.event_hash);
  const createdAt = researchYoutubeTimestamp(source.created_at);
  const correctionReason = source.correction_reason === null
    ? ""
    : String(source.correction_reason || "").trim();
  let parentEventId = "";
  let actorId = "";
  if (history) {
    parentEventId = source.parent_event_id === null
      ? ""
      : researchOutcomeUuid(source.parent_event_id);
    actorId = source.actor_id === null
      ? ""
      : researchOutcomeUuid(source.actor_id);
  }
  if (
    !eventId
    || !Number.isSafeInteger(analysisVersion)
    || analysisVersion < 1
    || analysisVersion > 100_000
    || !RESEARCH_CATEGORY_ANALYSIS_ORIGINS.has(origin)
    || !RESEARCH_CATEGORY_PROVIDER_PATTERN.test(parserKey)
    || parserVersion.length < 1
    || parserVersion.length > 120
    || !analysis
    || !eventHash
    || !createdAt
    || (origin === "system_parser" && correctionReason)
    || (origin === "human_correction" && (
      correctionReason.length < 3
      || correctionReason.length > 1_000
    ))
    || (history && analysisVersion === 1 && (parentEventId || actorId))
    || (history && analysisVersion > 1 && !parentEventId)
    || (history && origin === "system_parser" && actorId)
    || (history && origin === "human_correction" && !actorId)
  ) return null;
  return {
    eventId,
    analysisVersion,
    parentEventId,
    origin,
    actorId,
    parserKey,
    parserVersion,
    analysis,
    correctionReason,
    eventHash,
    createdAt,
  };
}

function researchCategorySourceLineageEntry(value) {
  const source = researchCategoryExactObject(value, [
    "source_ledger_id",
    "source_id",
    "source_content_hash",
    "lineage_hash",
    "fetched_at",
    "published_at",
    "registered_at",
  ]);
  if (!source) return null;
  const sourceLedgerId = researchOutcomeUuid(source.source_ledger_id);
  const sourceId = researchOutcomeUuid(source.source_id);
  const sourceContentHash = researchYoutubeHash(source.source_content_hash);
  const lineageHash = researchYoutubeHash(source.lineage_hash);
  const fetchedAt = source.fetched_at === null
    ? ""
    : researchYoutubeTimestamp(source.fetched_at);
  const publishedAt = source.published_at === null
    ? ""
    : researchYoutubeTimestamp(source.published_at);
  const registeredAt = researchYoutubeTimestamp(source.registered_at);
  if (
    !sourceLedgerId
    || !sourceId
    || !sourceContentHash
    || !lineageHash
    || (source.fetched_at !== null && !fetchedAt)
    || (source.published_at !== null && !publishedAt)
    || !registeredAt
  ) return null;
  return {
    sourceLedgerId,
    sourceId,
    sourceContentHash,
    lineageHash,
    fetchedAt,
    publishedAt,
    registeredAt,
  };
}

function researchCategorySourceItem(value) {
  const source = researchCategoryExactObject(value, [
    "source_ledger_id",
    "source_id",
    "run_id",
    "product_id",
    "source_type",
    "title",
    "source_url",
    "provider_key",
    "platform",
    "trust_level",
    "source_identity_key",
    "fetched_at",
    "published_at",
    "lineage_hash",
    "registered_at",
    "lineage_history",
    "current_analysis",
    "analysis_history",
  ]);
  if (!source) return null;
  const sourceLedgerId = researchOutcomeUuid(source.source_ledger_id);
  const sourceId = researchOutcomeUuid(source.source_id);
  const runId = researchOutcomeUuid(source.run_id);
  const productId = researchOutcomeUuid(source.product_id);
  const title = String(source.title || "").trim();
  const providerKey = String(source.provider_key || "");
  const sourceUrl = source.source_url === null
    ? ""
    : safeHttpsUrl(source.source_url);
  const fetchedAt = source.fetched_at === null
    ? ""
    : researchYoutubeTimestamp(source.fetched_at);
  const publishedAt = source.published_at === null
    ? ""
    : researchYoutubeTimestamp(source.published_at);
  const registeredAt = researchYoutubeTimestamp(source.registered_at);
  const sourceIdentityKey = researchYoutubeHash(source.source_identity_key);
  const lineageHash = researchYoutubeHash(source.lineage_hash);
  const rawLineageHistory = arrayValue(source.lineage_history);
  if (rawLineageHistory.length < 1 || rawLineageHistory.length > 10) return null;
  const lineageHistory = rawLineageHistory.map(
    researchCategorySourceLineageEntry,
  );
  const rawHistory = arrayValue(source.analysis_history);
  if (rawHistory.length > 10) return null;
  const analysisHistory = rawHistory.map((item) =>
    researchCategoryAnalysisEvent(item, { history: true })
  );
  const currentAnalysis = source.current_analysis === null
    ? null
    : researchCategoryAnalysisEvent(source.current_analysis);
  if (
    !sourceLedgerId
    || !sourceId
    || !runId
    || !productId
    || !RESEARCH_CATEGORY_SOURCE_TYPES.has(String(source.source_type || ""))
    || title.length < 2
    || title.length > 300
    || (source.source_url !== null && !sourceUrl)
    || !RESEARCH_CATEGORY_PROVIDER_PATTERN.test(providerKey)
    || !RESEARCH_CATEGORY_SOURCE_PLATFORMS.has(String(source.platform || ""))
    || !RESEARCH_CATEGORY_TRUST_LEVELS.has(String(source.trust_level || ""))
    || !sourceIdentityKey
    || (source.fetched_at !== null && !fetchedAt)
    || (source.published_at !== null && !publishedAt)
    || !lineageHash
    || !registeredAt
    || lineageHistory.some((item) => !item)
    || lineageHistory[0].sourceLedgerId !== sourceLedgerId
    || lineageHistory[0].sourceId !== sourceId
    || lineageHistory[0].lineageHash !== lineageHash
    || lineageHistory[0].fetchedAt !== fetchedAt
    || lineageHistory[0].publishedAt !== publishedAt
    || lineageHistory[0].registeredAt !== registeredAt
    || new Set(lineageHistory.map((item) => item.sourceLedgerId)).size
      !== lineageHistory.length
    || analysisHistory.some((item) => !item)
    || (source.current_analysis !== null && !currentAnalysis)
    || (analysisHistory.length > 0 && !currentAnalysis)
    || (currentAnalysis && !analysisHistory.length)
    || (
      currentAnalysis
      && (
        currentAnalysis.eventId !== analysisHistory[0].eventId
        || currentAnalysis.eventHash !== analysisHistory[0].eventHash
        || currentAnalysis.analysisVersion !== analysisHistory[0].analysisVersion
      )
    )
  ) return null;
  for (let index = 1; index < analysisHistory.length; index += 1) {
    if (
      analysisHistory[index - 1].analysisVersion
        !== analysisHistory[index].analysisVersion + 1
      || analysisHistory[index - 1].parentEventId
        !== analysisHistory[index].eventId
    ) {
      return null;
    }
  }
  for (let index = 1; index < lineageHistory.length; index += 1) {
    if (Date.parse(lineageHistory[index - 1].registeredAt)
      < Date.parse(lineageHistory[index].registeredAt)) return null;
  }
  return {
    sourceLedgerId,
    sourceId,
    runId,
    productId,
    sourceType: String(source.source_type),
    title,
    sourceUrl,
    providerKey,
    platform: String(source.platform),
    trustLevel: String(source.trust_level),
    sourceIdentityKey,
    fetchedAt,
    publishedAt,
    lineageHash,
    registeredAt,
    lineageHistory,
    currentAnalysis,
    analysisHistory,
  };
}

function researchCategoryYoutubeDecision(value) {
  const source = researchCategoryExactObject(value, [
    "decision_id",
    "decision",
    "reason",
    "decided_by",
    "decided_at",
    "decision_hash",
  ]);
  if (!source) return null;
  const decisionId = researchOutcomeUuid(source.decision_id);
  const decision = String(source.decision || "");
  const reason = source.reason === null
    ? ""
    : String(source.reason || "").trim();
  const decidedBy = researchOutcomeUuid(source.decided_by);
  const decidedAt = researchYoutubeTimestamp(source.decided_at);
  const decisionHash = researchYoutubeHash(source.decision_hash);
  if (
    !decisionId
    || !RESEARCH_CATEGORY_YOUTUBE_DECISIONS.has(decision)
    || (source.reason !== null && (reason.length < 3 || reason.length > 500))
    || !decidedBy
    || !decidedAt
    || !decisionHash
  ) return null;
  return {
    decisionId,
    decision,
    reason,
    decidedBy,
    decidedAt,
    decisionHash,
  };
}

function researchYoutubeObservationAnalysisPayload(value) {
  const analysis = researchCategoryExactObject(value, [
    "schema_version",
    "classification",
    "review_priority",
    "confidence",
    "recommendation",
    "signals",
    "summary",
    "limitations",
  ]);
  const signals = researchCategoryExactObject(analysis?.signals, [
    "search_position",
    "query_token_overlap_count",
    "query_token_count",
    "published_age_days",
    "same_channel_observation_count",
    "counters_present",
  ]);
  if (
    !analysis
    || analysis.schema_version !== RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA
    || !RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS.has(
      analysis.classification,
    )
    || !Number.isSafeInteger(analysis.review_priority)
    || analysis.review_priority < 0
    || analysis.review_priority > 100
    || !["low", "medium"].includes(analysis.confidence)
    || !RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_RECOMMENDATIONS.has(
      analysis.recommendation,
    )
    || !signals
    || !Number.isSafeInteger(signals.search_position)
    || signals.search_position < 1
    || signals.search_position > 25
    || !Number.isSafeInteger(signals.query_token_overlap_count)
    || signals.query_token_overlap_count < 0
    || signals.query_token_overlap_count > 999
    || !Number.isSafeInteger(signals.query_token_count)
    || signals.query_token_count < signals.query_token_overlap_count
    || signals.query_token_count > 999
    || !Number.isSafeInteger(signals.published_age_days)
    || signals.published_age_days < 0
    || signals.published_age_days > 9_999_999
    || !Number.isSafeInteger(signals.same_channel_observation_count)
    || signals.same_channel_observation_count < 1
    || signals.same_channel_observation_count > 9_999_999
    || typeof signals.counters_present !== "boolean"
    || typeof analysis.summary !== "string"
    || analysis.summary.trim().length < 20
    || analysis.summary.trim().length > 1_200
    || !Array.isArray(analysis.limitations)
    || analysis.limitations.length < 1
    || analysis.limitations.length > 8
    || analysis.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
    || researchCategoryAnalysisHasForbiddenKeys(analysis)
  ) return null;
  return analysis;
}

export function normalizeResearchYoutubeObservationAnalysisInput(value) {
  return researchYoutubeObservationAnalysisPayload(value);
}

function researchYoutubeObservationAnalysisEvent(value, { history = false } = {}) {
  const source = researchCategoryExactObject(value, history
    ? [
        "event_id",
        "analysis_version",
        "parent_event_id",
        "origin",
        "actor_id",
        "parser_key",
        "parser_version",
        "analysis",
        "correction_reason",
        "event_hash",
        "created_at",
        "retention_expires_at",
      ]
    : [
        "event_id",
        "analysis_version",
        "origin",
        "parser_key",
        "parser_version",
        "analysis",
        "correction_reason",
        "event_hash",
        "created_at",
        "retention_expires_at",
      ]);
  if (!source) return null;
  const eventId = researchOutcomeUuid(source.event_id);
  const eventHash = researchYoutubeHash(source.event_hash);
  const parserKey = String(source.parser_key || "");
  const parserVersion = String(source.parser_version || "").trim();
  const createdAt = researchYoutubeTimestamp(source.created_at);
  const retentionExpiresAt = researchYoutubeTimestamp(
    source.retention_expires_at,
  );
  const analysis = researchYoutubeObservationAnalysisPayload(source.analysis);
  const correctionReason = source.correction_reason === null
    ? ""
    : String(source.correction_reason || "").trim();
  const parentEventId = history && source.parent_event_id !== null
    ? researchOutcomeUuid(source.parent_event_id)
    : "";
  const actorId = history && source.actor_id !== null
    ? researchOutcomeUuid(source.actor_id)
    : "";
  if (
    !eventId
    || !eventHash
    || !Number.isSafeInteger(source.analysis_version)
    || source.analysis_version < 1
    || source.analysis_version > 100_000
    || !RESEARCH_CATEGORY_ANALYSIS_ORIGINS.has(source.origin)
    || !RESEARCH_CATEGORY_PROVIDER_PATTERN.test(parserKey)
    || parserVersion.length < 1
    || parserVersion.length > 120
    || !analysis
    || !createdAt
    || !retentionExpiresAt
    || Date.parse(createdAt) >= Date.parse(retentionExpiresAt)
    || (source.origin === "system_parser" && correctionReason)
    || (source.origin === "human_correction" && (
      correctionReason.length < 3 || correctionReason.length > 1_000
    ))
    || (history && source.analysis_version === 1 && (parentEventId || actorId))
    || (history && source.analysis_version > 1 && !parentEventId)
    || (history && source.origin === "system_parser" && actorId)
    || (history && source.origin === "human_correction" && !actorId)
  ) return null;
  return {
    eventId,
    eventHash,
    analysisVersion: source.analysis_version,
    parentEventId,
    origin: source.origin,
    actorId,
    parserKey,
    parserVersion,
    analysis,
    correctionReason,
    createdAt,
    retentionExpiresAt,
  };
}

function researchYoutubeObservationAnalysisJob(value, { asOf = "" } = {}) {
  const source = researchCategoryExactObject(value, [
    "job_id",
    "status",
    "attempt_count",
    "no_retry",
    "external_call_started",
    "parsed_count",
    "error_code",
    "input_hash",
    "job_hash",
    "created_at",
    "completed_at",
  ]);
  if (!source) return null;
  const jobId = researchOutcomeUuid(source.job_id);
  const status = String(source.status || "");
  const inputHash = researchYoutubeHash(source.input_hash);
  const jobHash = researchYoutubeHash(source.job_hash);
  const createdAt = researchYoutubeTimestamp(source.created_at);
  const completedAt = source.completed_at === null
    ? ""
    : researchYoutubeTimestamp(source.completed_at);
  const errorCode = source.error_code === null
    ? ""
    : String(source.error_code || "");
  const createdAtMs = Date.parse(createdAt);
  const completedAtMs = Date.parse(completedAt);
  const asOfMs = Date.parse(asOf);
  if (
    !jobId
    || !RESEARCH_YOUTUBE_OBSERVATION_JOB_STATUSES.has(status)
    || !Number.isSafeInteger(source.attempt_count)
    || source.attempt_count < 0
    || source.attempt_count > 1
    || source.no_retry !== true
    || source.external_call_started !== false
    || !Number.isSafeInteger(source.parsed_count)
    || source.parsed_count < 0
    || source.parsed_count > 25
    || !inputHash
    || !jobHash
    || !createdAt
    || !Number.isFinite(asOfMs)
    || createdAtMs > asOfMs
    || (source.completed_at !== null && !completedAt)
    || (["approval_required", "queued", "processing"].includes(status)
      && completedAt)
    || (["completed", "failed"].includes(status) && !completedAt)
    || (status === "failed"
      ? !RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_ERROR_CODES.has(errorCode)
      : Boolean(errorCode))
    || (completedAt && (
      completedAtMs < createdAtMs || completedAtMs > asOfMs
    ))
    || (["approval_required", "queued"].includes(status) && (
      source.attempt_count !== 0 || source.parsed_count !== 0
    ))
    || (["processing", "completed", "failed"].includes(status)
      && source.attempt_count !== 1)
    || (status === "failed" && source.parsed_count !== 0)
  ) return null;
  return {
    jobId,
    status,
    attemptCount: source.attempt_count,
    parsedCount: source.parsed_count,
    errorCode,
    inputHash,
    jobHash,
    createdAt,
    completedAt,
  };
}

function researchCategoryRetainedYoutubeItem(value, {
  asOf = "",
  analysisRequired = false,
  analysisApproved = false,
} = {}) {
  const keys = [
    "source_kind",
    "observation_id",
    "ingestion_id",
    "source_url",
    "provider_key",
    "platform",
    "video_id",
    "channel_id",
    "title",
    "channel_title",
    "published_at",
    "observed_at",
    "retention_expires_at",
    "observation_hash",
    "latest_decision",
    "included_in_readiness",
  ];
  if (analysisRequired) keys.push(
    "current_analysis",
    "analysis_history",
    "analysis_job",
    "can_correct_analysis",
  );
  const source = researchCategoryExactObject(value, keys);
  if (!source) return null;
  const observationId = researchOutcomeUuid(source.observation_id);
  const ingestionId = researchOutcomeUuid(source.ingestion_id);
  const videoId = String(source.video_id || "");
  const channelId = String(source.channel_id || "");
  const title = String(source.title || "").trim();
  const channelTitle = String(source.channel_title || "").trim();
  const sourceUrl = safeHttpsUrl(source.source_url);
  const publishedAt = researchYoutubeTimestamp(source.published_at);
  const observedAt = researchYoutubeTimestamp(source.observed_at);
  const retentionExpiresAt = researchYoutubeTimestamp(
    source.retention_expires_at,
  );
  const observationHash = researchYoutubeHash(source.observation_hash);
  const latestDecision = source.latest_decision === null
    ? null
    : researchCategoryYoutubeDecision(source.latest_decision);
  const currentAnalysis = analysisRequired && source.current_analysis !== null
    ? researchYoutubeObservationAnalysisEvent(source.current_analysis)
    : null;
  const rawAnalysisHistory = analysisRequired
    ? arrayValue(source.analysis_history)
    : [];
  const analysisHistory = rawAnalysisHistory.map((event) =>
    researchYoutubeObservationAnalysisEvent(event, { history: true })
  );
  const analysisJob = analysisRequired && source.analysis_job !== null
    ? researchYoutubeObservationAnalysisJob(source.analysis_job, { asOf })
    : null;
  const observedAtMs = Date.parse(observedAt);
  const publishedAtMs = Date.parse(publishedAt);
  const retentionExpiresAtMs = Date.parse(retentionExpiresAt);
  const asOfMs = Date.parse(asOf);
  const expectedIncluded = latestDecision?.decision !== "exclude_candidate";
  const expectedCanCorrect = Boolean(currentAnalysis) && analysisApproved;
  if (
    source.source_kind !== "retained_youtube_observation"
    || !observationId
    || !ingestionId
    || source.provider_key !== RESEARCH_YOUTUBE_PROVIDER_KEY
    || source.platform !== "youtube"
    || !/^[A-Za-z0-9_-]{11}$/u.test(videoId)
    || !/^UC[A-Za-z0-9_-]{22}$/u.test(channelId)
    || sourceUrl !== `https://www.youtube.com/watch?v=${videoId}`
    || title.length < 1
    || title.length > 300
    || channelTitle.length < 1
    || channelTitle.length > 300
    || !publishedAt
    || !observedAt
    || !retentionExpiresAt
    || !observationHash
    || (source.latest_decision !== null && !latestDecision)
    || typeof source.included_in_readiness !== "boolean"
    || source.included_in_readiness !== expectedIncluded
    || !Number.isFinite(asOfMs)
    || publishedAtMs > observedAtMs
    || observedAtMs > asOfMs
    || retentionExpiresAtMs <= asOfMs
    || retentionExpiresAtMs - observedAtMs !== 29 * 24 * 60 * 60 * 1_000
    || (latestDecision && (
      Date.parse(latestDecision.decidedAt) < observedAtMs
      || Date.parse(latestDecision.decidedAt) > asOfMs
      || Date.parse(latestDecision.decidedAt) >= retentionExpiresAtMs
    ))
    || (analysisRequired && (
      rawAnalysisHistory.length > 10
      || analysisHistory.some((event) => !event)
      || (source.current_analysis !== null && !currentAnalysis)
      || (source.analysis_job !== null && !analysisJob)
      || !analysisJob
      || typeof source.can_correct_analysis !== "boolean"
      || source.can_correct_analysis !== expectedCanCorrect
      || (currentAnalysis && (
        !analysisHistory.length
        || analysisHistory[0].eventId !== currentAnalysis.eventId
        || analysisHistory[0].eventHash !== currentAnalysis.eventHash
        || analysisHistory[0].analysisVersion
          !== currentAnalysis.analysisVersion
        || currentAnalysis.retentionExpiresAt !== retentionExpiresAt
      ))
      || analysisHistory.some((event) =>
        event.retentionExpiresAt !== retentionExpiresAt
        || Date.parse(event.createdAt) < observedAtMs
        || Date.parse(event.createdAt) > asOfMs
      )
      || (analysisJob.status === "completed" && !currentAnalysis)
      || (["approval_required", "queued", "processing"].includes(
        analysisJob.status,
      )
        && currentAnalysis)
    ))
  ) return null;
  return {
    observationId,
    ingestionId,
    sourceUrl,
    videoId,
    channelId,
    title,
    channelTitle,
    publishedAt,
    observedAt,
    retentionExpiresAt,
    observationHash,
    latestDecision,
    includedInReadiness: source.included_in_readiness,
    currentAnalysis,
    analysisHistory,
    analysisJob,
    canCorrectAnalysis: analysisRequired && expectedCanCorrect,
  };
}

function researchCategoryPolicy(value) {
  const source = researchCategoryExactObject(value, [
    "policy_id",
    "policy_hash",
    "policy_version",
    "platform",
    "provider_key",
    "status",
    "automatic_collection_ack",
    "terms_version",
    "terms_ack",
    "quota_ack",
    "no_retry_ack",
    "cadence_hours",
    "max_records",
    "monthly_hard_budget_units",
    "legal_review_reference",
    "reason",
    "created_at",
    "automatic_enqueue_supported",
    "handoff",
  ]);
  if (!source) return null;
  const policyId = researchOutcomeUuid(source.policy_id);
  const policyHash = researchYoutubeHash(source.policy_hash);
  const policyVersion = source.policy_version;
  const platform = String(source.platform || "");
  const providerKey = String(source.provider_key || "");
  const status = String(source.status || "");
  const termsVersion = String(source.terms_version || "").trim();
  const cadenceHours = source.cadence_hours;
  const maxRecords = source.max_records;
  const budgetUnits = source.monthly_hard_budget_units;
  const legalReviewReference = source.legal_review_reference === null
    ? ""
    : String(source.legal_review_reference || "").trim();
  const reason = String(source.reason || "").trim();
  const createdAt = researchYoutubeTimestamp(source.created_at);
  const expectedHandoff = status === "enabled" && platform === "youtube"
    ? "automatic_youtube_ingestion_queue"
    : platform === "instagram"
      ? "provider_and_legal_choice_required"
      : null;
  if (
    !policyId
    || !policyHash
    || !Number.isSafeInteger(policyVersion)
    || policyVersion < 1
    || policyVersion > 100_000
    || !RESEARCH_CATEGORY_POLICY_PLATFORMS.has(platform)
    || !RESEARCH_CATEGORY_PROVIDER_PATTERN.test(providerKey)
    || !["paused", "enabled"].includes(status)
    || typeof source.automatic_collection_ack !== "boolean"
    || termsVersion.length < 3
    || termsVersion.length > 80
    || typeof source.terms_ack !== "boolean"
    || typeof source.quota_ack !== "boolean"
    || typeof source.no_retry_ack !== "boolean"
    || !Number.isSafeInteger(cadenceHours)
    || cadenceHours < 24
    || cadenceHours > 720
    || !Number.isSafeInteger(maxRecords)
    || maxRecords < 1
    || maxRecords > 25
    || !Number.isSafeInteger(budgetUnits)
    || budgetUnits < 0
    || budgetUnits > 100
    || (source.legal_review_reference !== null && (
      legalReviewReference.length < 3
      || legalReviewReference.length > 160
    ))
    || reason.length < 3
    || reason.length > 500
    || !createdAt
    || source.automatic_enqueue_supported !== (status === "enabled")
    || source.handoff !== expectedHandoff
    || (platform === "instagram" && status !== "paused")
    || (status === "enabled" && (
      platform !== "youtube"
      || providerKey !== "youtube_data_api_v3"
      || source.automatic_collection_ack !== true
      || termsVersion !== RESEARCH_CATEGORY_YOUTUBE_TERMS_VERSION
      || source.terms_ack !== true
      || source.quota_ack !== true
      || source.no_retry_ack !== true
      || budgetUnits < 2
      || !legalReviewReference
    ))
  ) return null;
  return {
    policyId,
    policyHash,
    policyVersion,
    platform,
    providerKey,
    status,
    automaticCollectionAck: source.automatic_collection_ack,
    termsVersion,
    termsAck: source.terms_ack,
    quotaAck: source.quota_ack,
    noRetryAck: source.no_retry_ack,
    cadenceHours,
    maxRecords,
    monthlyHardBudgetUnits: budgetUnits,
    legalReviewReference,
    reason,
    createdAt,
    automaticEnqueueSupported: source.automatic_enqueue_supported,
    handoff: expectedHandoff || "",
  };
}

function researchCategoryCollectionIntent(value) {
  const source = researchCategoryExactObject(value, [
    "intent_id",
    "policy_id",
    "platform",
    "provider_key",
    "ingestion_id",
    "status",
    "capability",
    "blocked_reason",
    "query_text",
    "max_records",
    "planned_quota_units",
    "monthly_hard_budget_units",
    "monthly_reserved_units",
    "scheduled_for",
    "automatic_enqueue_supported",
    "external_call_started",
    "no_retry",
    "no_fallback",
    "intent_hash",
    "created_at",
    "ingestion_status",
    "ingestion_error_code",
    "ingestion_requested_at",
    "ingestion_completed_at",
    "transport_attempt_count",
  ]);
  if (!source) return null;
  const intentId = researchOutcomeUuid(source.intent_id);
  const policyId = researchOutcomeUuid(source.policy_id);
  const platform = String(source.platform || "");
  const providerKey = String(source.provider_key || "");
  const ingestionId = source.ingestion_id === null
    ? ""
    : researchOutcomeUuid(source.ingestion_id);
  const status = String(source.status || "");
  const capability = String(source.capability || "");
  const blockedReason = source.blocked_reason === null
    ? ""
    : String(source.blocked_reason || "");
  const queryText = String(source.query_text || "").trim();
  const maxRecords = source.max_records;
  const plannedQuotaUnits = source.planned_quota_units;
  const budgetUnits = source.monthly_hard_budget_units;
  const reservedUnits = source.monthly_reserved_units;
  const scheduledFor = researchYoutubeTimestamp(source.scheduled_for);
  const intentHash = researchYoutubeHash(source.intent_hash);
  const createdAt = researchYoutubeTimestamp(source.created_at);
  const ingestionStatus = source.ingestion_status === null
    ? ""
    : String(source.ingestion_status || "");
  const ingestionErrorCode = source.ingestion_error_code === null
    ? ""
    : String(source.ingestion_error_code || "");
  const ingestionRequestedAt = source.ingestion_requested_at === null
    ? ""
    : researchYoutubeTimestamp(source.ingestion_requested_at);
  const ingestionCompletedAt = source.ingestion_completed_at === null
    ? ""
    : researchYoutubeTimestamp(source.ingestion_completed_at);
  const transportAttemptCount = source.transport_attempt_count;
  const queued = status === "queued";
  if (
    !intentId
    || !policyId
    || (source.ingestion_id !== null && !ingestionId)
    || !RESEARCH_CATEGORY_POLICY_PLATFORMS.has(platform)
    || !RESEARCH_CATEGORY_PROVIDER_PATTERN.test(providerKey)
    || !["queued", "blocked"].includes(status)
    || ![
      "automatic_youtube_enqueue",
      "automatic_collection_unavailable",
    ].includes(capability)
    || (queued ? Boolean(blockedReason) : !RESEARCH_CATEGORY_INTENT_BLOCKERS.has(blockedReason))
    || queryText.length < 2
    || queryText.length > 200
    || !Number.isSafeInteger(maxRecords)
    || maxRecords < 1
    || maxRecords > 25
    || !Number.isSafeInteger(plannedQuotaUnits)
    || plannedQuotaUnits < 0
    || plannedQuotaUnits > 2
    || !Number.isSafeInteger(budgetUnits)
    || budgetUnits < 0
    || budgetUnits > 100
    || !Number.isSafeInteger(reservedUnits)
    || reservedUnits < 0
    || reservedUnits > 100_000
    || !scheduledFor
    || source.automatic_enqueue_supported !== queued
    || source.external_call_started !== false
    || source.no_retry !== true
    || source.no_fallback !== true
    || !intentHash
    || !createdAt
    || !Number.isSafeInteger(transportAttemptCount)
    || transportAttemptCount < 0
    || transportAttemptCount > 2
    || (queued && (
      capability !== "automatic_youtube_enqueue"
      || platform !== "youtube"
      || providerKey !== "youtube_data_api_v3"
      || plannedQuotaUnits !== 2
      || !ingestionId
      || !RESEARCH_YOUTUBE_STATUSES.has(ingestionStatus)
      || !ingestionRequestedAt
      || Date.parse(ingestionRequestedAt) > Date.parse(createdAt)
      || (ingestionStatus === "queued" && transportAttemptCount !== 0)
      || (
        ["queued", "processing"].includes(ingestionStatus)
        && (ingestionErrorCode || ingestionCompletedAt)
      )
      || (
        ingestionStatus === "completed"
        && (
          ingestionErrorCode
          || !ingestionCompletedAt
          || transportAttemptCount < 1
        )
      )
      || (
        ingestionStatus === "failed"
        && (
          !RESEARCH_YOUTUBE_ERROR_CODES.has(ingestionErrorCode)
          || !ingestionCompletedAt
        )
      )
      || (
        ingestionCompletedAt
        && Date.parse(ingestionCompletedAt) < Date.parse(ingestionRequestedAt)
      )
    ))
    || (!queued && (
      capability !== "automatic_collection_unavailable"
      || plannedQuotaUnits !== 0
      || Boolean(ingestionId)
      || ingestionStatus
      || ingestionErrorCode
      || ingestionRequestedAt
      || ingestionCompletedAt
      || transportAttemptCount !== 0
    ))
  ) return null;
  return {
    intentId,
    policyId,
    platform,
    providerKey,
    ingestionId,
    status,
    capability,
    blockedReason,
    queryText,
    maxRecords,
    plannedQuotaUnits,
    monthlyHardBudgetUnits: budgetUnits,
    monthlyReservedUnits: reservedUnits,
    scheduledFor,
    intentHash,
    createdAt,
    ingestionStatus,
    ingestionErrorCode,
    ingestionRequestedAt,
    ingestionCompletedAt,
    transportAttemptCount,
    automaticEnqueueSupported: source.automatic_enqueue_supported,
  };
}

function researchCategoryProviderStrategy(value) {
  const source = researchCategoryExactObject(value, [
    "version",
    "recommended_production_order",
    "youtube_retrieval_capability",
    "youtube_derived_analysis_state",
    "youtube_derived_analysis_policy",
    "youtube_derived_analysis_approval_ref",
    "instagram_activation_gate",
    "instagram_known_professional_lookup",
    "instagram_hashtag_discovery",
    "instagram_arbitrary_account_discovery",
    "disabled_by_policy",
    "recommendation",
  ]);
  const order = arrayValue(source?.recommended_production_order);
  const disabled = arrayValue(source?.disabled_by_policy);
  const approvalReference = source?.youtube_derived_analysis_approval_ref
    === null
    ? ""
    : String(source?.youtube_derived_analysis_approval_ref || "").trim();
  if (
    !source
    || source.version !== "social-observation-adapter-v1"
    || order.join("|") !== "youtube_data_api_v3|instagram_meta_graph"
    || source.youtube_retrieval_capability
      !== "official_api_controlled_rollout"
    || !["approval_required", "approved", "emergency_paused"].includes(
      source.youtube_derived_analysis_state,
    )
    || source.youtube_derived_analysis_policy
      !== "youtube-derived-metrics-policy-2026-06-01-v1"
    || (source.youtube_derived_analysis_state === "approved"
      ? approvalReference.length < 3 || approvalReference.length > 160
      : source.youtube_derived_analysis_approval_ref !== null)
    || source.instagram_activation_gate
      !== "oauth_app_review_permissions_and_legal_approval_required"
    || source.instagram_known_professional_lookup
      !== "supported_after_approval"
    || source.instagram_hashtag_discovery !== "limited_after_approval"
    || source.instagram_arbitrary_account_discovery
      !== "unsupported_coverage_gap"
    || disabled.join("|")
      !== "apify_scraper|bright_data_scraper|oxylabs_youtube_scraper|dataforseo_youtube_scraper"
    || source.recommendation
      !== "Use official APIs first; keep YouTube derived analysis approval-gated and expose unsupported coverage instead of silently scraping."
  ) return null;
  return {
    version: source.version,
    recommendedProductionOrder: order,
    youtubeRetrievalCapability: source.youtube_retrieval_capability,
    youtubeDerivedAnalysisState: source.youtube_derived_analysis_state,
    youtubeDerivedAnalysisPolicy: source.youtube_derived_analysis_policy,
    youtubeDerivedAnalysisApprovalRef: approvalReference,
    instagramActivationGate: source.instagram_activation_gate,
    instagramKnownProfessionalLookup: source.instagram_known_professional_lookup,
    instagramHashtagDiscovery: source.instagram_hashtag_discovery,
    instagramArbitraryAccountDiscovery:
      source.instagram_arbitrary_account_discovery,
    disabledByPolicy: disabled,
    recommendation: source.recommendation,
  };
}

export function normalizeResearchCategoryLearning(value) {
  const envelope = objectValue(value) || {};
  const expectedRunId = String(envelope.expectedRunId || "").trim().toLowerCase();
  const invalid = () =>
    researchCategoryLearningUnavailable(expectedRunId, "invalid_contract");
  if (envelope.unavailable === true) {
    return researchCategoryLearningUnavailable(expectedRunId, "satellite_unavailable");
  }
  const rawStatus = objectValue(envelope.status);
  const statusVersion = String(rawStatus?.version || "");
  if (!RESEARCH_CATEGORY_LEARNING_VERSIONS.has(statusVersion)) return invalid();
  const statusKeys = [
    "ok",
    "version",
    "organization_id",
    "run_id",
    "metric",
    "category",
    "source_ledger",
    "retained_youtube_evidence",
    "readiness_history",
    "collection",
    "guidance",
  ];
  if (statusVersion === RESEARCH_CATEGORY_LEARNING_VERSION) {
    statusKeys.push("provider_strategy");
  }
  const source = researchCategoryExactObject(rawStatus, statusKeys);
  if (
    !source
    || source.ok !== true
    || !RESEARCH_CATEGORY_LEARNING_VERSIONS.has(source.version)
  ) return invalid();
  const organizationId = researchOutcomeUuid(source.organization_id);
  const runId = researchOutcomeUuid(source.run_id);
  if (!organizationId || !runId || (expectedRunId && runId !== expectedRunId)) {
    return invalid();
  }

  const metric = researchCategoryExactObject(source.metric, [
    "label",
    "kind",
    "is_ai_iq",
    "readiness",
  ]);
  const readiness = researchCategoryExactObject(metric?.readiness, [
    "metric_kind",
    "definition_version",
    "score",
    "dimensions",
    "weights_total",
    "evidence_hash",
    "as_of",
    "limits",
  ]);
  const limits = researchCategoryExactObject(readiness?.limits, [
    "is_model_iq",
    "is_quality_guarantee",
    "competitor_metric_is_unique_publishers",
    "retained_youtube_uses_unique_channel_ids",
    "youtube_retention_days",
    "meaning",
  ]);
  const dimensions = researchCategoryDimensionList(readiness?.dimensions);
  const score = readiness?.score;
  const evidenceHash = researchYoutubeHash(readiness?.evidence_hash);
  const asOf = researchYoutubeTimestamp(readiness?.as_of);
  if (
    !metric
    || metric.label !== "Category evidence readiness"
    || metric.kind !== RESEARCH_CATEGORY_READINESS_KIND
    || metric.is_ai_iq !== false
    || !readiness
    || readiness.metric_kind !== RESEARCH_CATEGORY_READINESS_KIND
    || !RESEARCH_CATEGORY_READINESS_DEFINITIONS.has(
      readiness.definition_version,
    )
    || !Number.isSafeInteger(score)
    || score < 0
    || score > 100
    || !dimensions
    || dimensions.reduce((sum, item) => sum + item.weightedPoints, 0) !== score
    || readiness.weights_total !== 100
    || dimensions.reduce((sum, item) => sum + item.weight, 0) !== 100
    || !evidenceHash
    || !asOf
    || !limits
    || limits.is_model_iq !== false
    || limits.is_quality_guarantee !== false
    || limits.competitor_metric_is_unique_publishers !== false
    || limits.retained_youtube_uses_unique_channel_ids !== true
    || limits.youtube_retention_days !== 29
    || limits.meaning !== RESEARCH_CATEGORY_READINESS_MEANINGS.get(
      readiness.definition_version,
    )
  ) return invalid();

  const category = researchCategoryExactObject(source.category, [
    "category_id",
    "canonical_name",
    "definition",
    "binding_id",
    "binding_version",
  ]);
  const categoryId = researchOutcomeUuid(category?.category_id);
  const bindingId = researchOutcomeUuid(category?.binding_id);
  const canonicalName = String(category?.canonical_name || "").trim();
  const definition = String(category?.definition || "").trim();
  const bindingVersion = category?.binding_version;
  if (
    !category
    || !categoryId
    || !bindingId
    || canonicalName.length < 2
    || canonicalName.length > 160
    || definition.length < 10
    || definition.length > 2_000
    || !Number.isSafeInteger(bindingVersion)
    || bindingVersion < 1
  ) return invalid();

  const ledger = researchCategoryExactObject(source.source_ledger, [
    "items",
    "item_limit",
    "analysis_history_limit_per_source",
    "lineage_history_limit_per_source",
    "raw_captions_stored",
  ]);
  const rawSources = arrayValue(ledger?.items);
  const sources = rawSources.map(researchCategorySourceItem);
  if (
    !ledger
    || ledger.item_limit !== 50
    || ledger.analysis_history_limit_per_source !== 10
    || ledger.lineage_history_limit_per_source !== 10
    || ledger.raw_captions_stored !== false
    || rawSources.length > 50
    || sources.some((item) => !item)
    || new Set(sources.map((item) => item.sourceLedgerId)).size !== sources.length
  ) return invalid();

  const analysisRequired = source.version === RESEARCH_CATEGORY_LEARNING_VERSION;
  const providerStrategy = analysisRequired
    ? researchCategoryProviderStrategy(source.provider_strategy)
    : null;
  if (analysisRequired && !providerStrategy) return invalid();
  const retainedYoutubeKeys = [
    "items",
    "item_limit",
    "retention_days",
    "raw_captions_stored",
    "corrected_by",
  ];
  if (analysisRequired) retainedYoutubeKeys.push(
    "analysis_contract",
    "analysis_history_limit_per_observation",
    "analysis_corrected_by",
    "analysis_external_call_started",
    "analysis_automatic_retry_allowed",
  );
  const retainedYoutubeEnvelope = researchCategoryExactObject(
    source.retained_youtube_evidence,
    retainedYoutubeKeys,
  );
  const rawRetainedYoutubeEvidence = arrayValue(
    retainedYoutubeEnvelope?.items,
  );
  const retainedYoutubeEvidence = rawRetainedYoutubeEvidence.map((item) =>
    researchCategoryRetainedYoutubeItem(item, {
      asOf,
      analysisRequired,
      analysisApproved:
        providerStrategy?.youtubeDerivedAnalysisState === "approved",
    })
  );
  if (
    !retainedYoutubeEnvelope
    || retainedYoutubeEnvelope.item_limit !== 50
    || retainedYoutubeEnvelope.retention_days !== 29
    || retainedYoutubeEnvelope.raw_captions_stored !== false
    || retainedYoutubeEnvelope.corrected_by
      !== "creator_decide_research_youtube_candidate"
    || (analysisRequired && (
      retainedYoutubeEnvelope.analysis_contract
        !== RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA
      || retainedYoutubeEnvelope.analysis_history_limit_per_observation !== 10
      || retainedYoutubeEnvelope.analysis_corrected_by
        !== "creator_correct_research_youtube_observation_analysis"
      || retainedYoutubeEnvelope.analysis_external_call_started !== false
      || retainedYoutubeEnvelope.analysis_automatic_retry_allowed !== false
    ))
    || rawRetainedYoutubeEvidence.length > 50
    || retainedYoutubeEvidence.some((item) => !item)
    || new Set(retainedYoutubeEvidence.map((item) => item.observationId)).size
      !== retainedYoutubeEvidence.length
    || new Set(retainedYoutubeEvidence.map((item) => item.videoId)).size
      !== retainedYoutubeEvidence.length
  ) return invalid();

  const historyEnvelope = researchCategoryExactObject(source.readiness_history, [
    "items",
    "item_limit",
    "captured_only_by_mutation",
  ]);
  const rawSnapshots = arrayValue(historyEnvelope?.items);
  const readinessHistory = rawSnapshots.map((item) => {
    const snapshot = researchCategoryExactObject(item, [
      "snapshot_id",
      "definition_version",
      "score",
      "dimensions",
      "evidence_hash",
      "snapshot_hash",
      "captured_by",
      "captured_at",
    ]);
    if (!snapshot) return null;
    const snapshotDimensions = researchCategoryDimensionList(snapshot.dimensions);
    const snapshotScore = snapshot.score;
    const snapshotId = researchOutcomeUuid(snapshot.snapshot_id);
    const snapshotEvidenceHash = researchYoutubeHash(snapshot.evidence_hash);
    const snapshotHash = researchYoutubeHash(snapshot.snapshot_hash);
    const capturedBy = researchOutcomeUuid(snapshot.captured_by);
    const capturedAt = researchYoutubeTimestamp(snapshot.captured_at);
    if (
      !RESEARCH_CATEGORY_READINESS_DEFINITIONS.has(snapshot.definition_version)
      || !snapshotId
      || !Number.isSafeInteger(snapshotScore)
      || snapshotScore < 0
      || snapshotScore > 100
      || !snapshotDimensions
      || snapshotDimensions.reduce((sum, entry) => sum + entry.weightedPoints, 0)
        !== snapshotScore
      || !snapshotEvidenceHash
      || !snapshotHash
      || !capturedBy
      || !capturedAt
    ) return null;
    return {
      snapshotId,
      definitionVersion: snapshot.definition_version,
      score: snapshotScore,
      dimensions: snapshotDimensions,
      evidenceHash: snapshotEvidenceHash,
      snapshotHash,
      capturedBy,
      capturedAt,
    };
  });
  if (
    !historyEnvelope
    || historyEnvelope.item_limit !== 24
    || historyEnvelope.captured_only_by_mutation !== true
    || rawSnapshots.length > 24
    || readinessHistory.some((item) => !item)
  ) return invalid();

  const collection = researchCategoryExactObject(source.collection, [
    "default_status",
    "policies",
    "history",
    "history_limit",
    "scheduler_starts_external_calls",
    "automatic_retry_allowed",
    "automatic_fallback_allowed",
    "instagram_automatic_collection",
  ]);
  const rawPolicies = arrayValue(collection?.policies);
  const rawCollectionHistory = arrayValue(collection?.history);
  const policies = rawPolicies.map(researchCategoryPolicy);
  const collectionHistory = rawCollectionHistory.map(
    researchCategoryCollectionIntent,
  );
  if (
    !collection
    || collection.default_status !== "paused"
    || rawPolicies.length > 2
    || policies.some((item) => !item)
    || new Set(policies.map((item) => item.platform)).size !== policies.length
    || rawCollectionHistory.length > 24
    || collectionHistory.some((item) => !item)
    || collection.history_limit !== 24
    || collection.scheduler_starts_external_calls !== false
    || collection.automatic_retry_allowed !== false
    || collection.automatic_fallback_allowed !== false
    || collection.instagram_automatic_collection
      !== "blocked_pending_provider_and_legal_choice"
  ) return invalid();

  const guidance = researchCategoryExactObject(source.guidance, [
    "status",
    "gaps",
    "expected_evidence_hash",
    "score_is_not_model_iq",
  ]);
  const guidanceStatus = String(guidance?.status || "");
  const rawGaps = arrayValue(guidance?.gaps);
  const normalizedRawGaps = rawGaps.map((item) => {
    const key = String(objectValue(item)?.key || "");
    const index = RESEARCH_CATEGORY_DIMENSIONS.findIndex((entry) => entry.key === key);
    if (index < 0) return null;
    const expectedDimension = dimensions[index];
    const candidate = researchCategoryDimensionList(
      RESEARCH_CATEGORY_DIMENSIONS.map((entry, candidateIndex) => {
        const normalized = candidateIndex === index ? item : {
          key: entry.key,
          label: entry.label,
          weight: entry.weight,
          current: entry.target,
          target: entry.target,
          score: 100,
          weighted_points: entry.weight,
          missing: 0,
          next_action: null,
        };
        return normalized;
      }),
    )?.[index];
    return candidate
      && candidate.key === expectedDimension.key
      && candidate.current === expectedDimension.current
      && candidate.missing === expectedDimension.missing
      ? candidate
      : null;
  });
  const expectedGapKeys = dimensions
    .filter((item) => item.missing > 0)
    .map((item) => item.key);
  const expectedGuidanceStatus = score >= 80
    ? "strong_evidence"
    : score >= 50
      ? "developing_evidence"
      : "insufficient_evidence";
  if (
    !guidance
    || !RESEARCH_CATEGORY_GUIDANCE_STATUSES.has(guidanceStatus)
    || guidanceStatus !== expectedGuidanceStatus
    || guidance.expected_evidence_hash !== evidenceHash
    || guidance.score_is_not_model_iq !== true
    || normalizedRawGaps.some((item) => !item)
    || normalizedRawGaps.map((item) => item.key).join("|") !== expectedGapKeys.join("|")
  ) return invalid();

  return {
    available: true,
    version: source.version,
    organizationId,
    runId,
    category: {
      categoryId,
      canonicalName,
      definition,
      bindingId,
      bindingVersion,
    },
    score,
    readinessDefinition: readiness.definition_version,
    evidenceHash,
    asOf,
    dimensions,
    gaps: normalizedRawGaps,
    sources,
    retainedYoutubeEvidence,
    readinessHistory,
    policies,
    collectionHistory,
    providerStrategy,
    guidanceStatus,
    rawCaptionsStored: false,
    collection: {
      defaultStatus: "paused",
      schedulerStartsExternalCalls: false,
      automaticRetryAllowed: false,
      automaticFallbackAllowed: false,
      instagramAutomaticCollection:
        "blocked_pending_provider_and_legal_choice",
      retainedYoutubeRetentionDays: 29,
    },
  };
}

function researchCategoryDimensionLabel(key) {
  return ({
    source_volume: "Текущий объём проверяемых источников",
    platform_diversity: "Разнообразие площадок",
    competitor_observations: "Подтверждённые наблюдения конкурентов",
    trend_recency: "Свежесть трендов",
    analysis_coverage: "Структурированный / нормализованный охват",
    human_validation: "Доказательства, проверенные человеком",
  })[key] || key;
}

function researchCategoryNextActionLabel(value) {
  return ({
    collect_more_reviewable_sources:
      "Добавить проверяемые источники с URL, временем получения и lineage либо свежие bounded YouTube-наблюдения.",
    add_an_independent_platform:
      "Добавить независимую площадку, а не ещё одну публикацию того же аккаунта.",
    collect_competitor_observations:
      "Разобрать проверяемые источники конкурентов; YouTube-кандидат засчитывается только после подтверждения человеком и дедупликации по channel_id.",
    refresh_canonical_trend_evidence:
      "Обновить канонические трендовые наблюдения за последние 30 дней.",
    analyze_unreviewed_sources:
      "Разобрать ещё не обработанные источники в ограниченную структуру без raw captions.",
    review_and_correct_source_analysis:
      "Проверить разборы человеком и сохранить append-only исправления.",
  })[value] || "Проверить недостающие доказательства.";
}

function researchCategoryGuidanceLabel(value) {
  return ({
    strong_evidence: "Сильная доказательная база",
    developing_evidence: "Доказательная база развивается",
    insufficient_evidence: "Доказательств пока недостаточно",
  })[value] || "Статус доказательств не определён";
}

function researchCategoryPlatformLabel(value) {
  return ({
    youtube: "YouTube",
    instagram: "Instagram",
    marketplace: "Маркетплейс",
    web: "Веб",
    first_party: "Собственные данные",
    other: "Другая площадка",
  })[value] || value;
}

function researchCategoryTrustLabel(value) {
  return ({
    first_party: "собственный источник",
    official: "официальный",
    public: "публичный",
    unverified: "не проверен",
  })[value] || value;
}

function researchCategoryPrettyAnalysis(value) {
  try {
    return JSON.stringify(objectValue(value) || {}, null, 2);
  } catch {
    return "{}";
  }
}

function researchCategoryDimensionMarkup(dimension, index) {
  const detailId = `research-category-dimension-${index}`;
  const complete = dimension.missing === 0;
  const hoverSummary = `${researchCategoryDimensionLabel(dimension.key)}: ${dimension.current} из ${dimension.target}; ${complete ? "цель достигнута" : `не хватает ${dimension.missing}; ${researchCategoryNextActionLabel(dimension.nextAction)}`}`;
  return `<details class="product-research-learning-dimension ${complete ? "is-complete" : "needs-evidence"}">
    <summary aria-describedby="${detailId}" title="${escapeHtml(hoverSummary)}" data-gap-tooltip="${escapeHtml(hoverSummary)}">
      <span><strong>${escapeHtml(researchCategoryDimensionLabel(dimension.key))}</strong><small>${dimension.current} из ${dimension.target} · вес ${dimension.weight}%</small></span>
      <span class="product-research-learning-dimension-score">${dimension.score}%</span>
    </summary>
    <div class="product-research-learning-dimension-detail" id="${detailId}" role="note">
      <p><strong>${complete ? "Цель достигнута." : `Не хватает: ${dimension.missing}.`}</strong> В общий показатель сейчас входит ${dimension.weightedPoints} из ${dimension.weight} возможных пунктов.</p>
      <p>${complete ? "Новые данные всё равно проходят проверку источника и lineage." : escapeHtml(researchCategoryNextActionLabel(dimension.nextAction))}</p>
      <small>Это измерение покрытия доказательств, а не точности или интеллекта ИИ.</small>
    </div>
  </details>`;
}

function researchCategoryAnalysisHistoryMarkup(source) {
  if (!source.analysisHistory.length) {
    return '<p class="muted">История разбора пока пуста.</p>';
  }
  return `<ol>${source.analysisHistory.map((event) => `<li>
    <div><strong>Версия ${event.analysisVersion} · ${event.origin === "human_correction" ? "исправлено человеком" : "системный parser"}</strong><small>${escapeHtml(researchYoutubeDateTimeLabel(event.createdAt))}${event.correctionReason ? ` · ${escapeHtml(event.correctionReason)}` : ""}</small></div>
    <code>${escapeHtml(event.eventHash.slice(0, 10))}…</code>
  </li>`).join("")}</ol>`;
}

function researchCategoryLineageHistoryMarkup(source) {
  return `<ol>${source.lineageHistory.map((entry) => `<li>
    <div><strong>${escapeHtml(researchYoutubeDateTimeLabel(entry.registeredAt))} · ledger <code>${escapeHtml(entry.sourceLedgerId.slice(0, 8))}…</code></strong><small>${entry.fetchedAt ? `Получен ${escapeHtml(researchYoutubeDateTimeLabel(entry.fetchedAt))}` : "Время получения не зафиксировано"}${entry.publishedAt ? ` · опубликован ${escapeHtml(researchYoutubeDateTimeLabel(entry.publishedAt))}` : ""}</small></div>
    <span><code title="source_content_hash">${escapeHtml(entry.sourceContentHash.slice(0, 10))}…</code> · <code title="lineage_hash">${escapeHtml(entry.lineageHash.slice(0, 10))}…</code></span>
  </li>`).join("")}</ol>`;
}

function researchCategorySourceCardMarkup(source, { saving = false } = {}) {
  const current = source.currentAnalysis;
  const analysis = current
    ? researchCategoryPrettyAnalysis(current.analysis)
    : "";
  const lineage = `${source.lineageHash.slice(0, 12)}…`;
  const provenance = [
    researchCategoryPlatformLabel(source.platform),
    source.providerKey,
    researchCategoryTrustLabel(source.trustLevel),
    source.fetchedAt
      ? `получен ${researchYoutubeDateTimeLabel(source.fetchedAt)}`
      : "время получения не зафиксировано",
  ].join(" · ");
  return `<article class="product-research-learning-source">
    <header>
      <div><span class="badge">${escapeHtml(researchCategoryPlatformLabel(source.platform))}</span><span class="badge">${escapeHtml(source.providerKey)}</span></div>
      ${source.sourceUrl ? `<a href="${escapeHtml(source.sourceUrl)}" target="_blank" rel="noopener noreferrer nofollow">Открыть источник <span aria-hidden="true">↗</span></a>` : '<span class="muted">URL не сохранён</span>'}
    </header>
    <h3>${escapeHtml(source.title)}</h3>
    <p class="product-research-learning-provenance">${escapeHtml(provenance)}</p>
    <dl class="product-research-learning-lineage">
      <div><dt>Источник</dt><dd><code>${escapeHtml(source.sourceId.slice(0, 8))}…</code></dd></div>
      <div><dt>Identity</dt><dd><code>${escapeHtml(source.sourceIdentityKey.slice(0, 10))}…</code></dd></div>
      <div><dt>Lineage</dt><dd><code>${escapeHtml(lineage)}</code></dd></div>
      <div><dt>Разбор</dt><dd>${current ? `v${current.analysisVersion} · ${current.origin === "human_correction" ? "человек" : `${escapeHtml(current.parserKey)} ${escapeHtml(current.parserVersion)}`}` : "ещё не создан"}</dd></div>
    </dl>
    <details class="product-research-learning-lineage-history">
      <summary>История lineage (${source.lineageHistory.length})</summary>
      ${researchCategoryLineageHistoryMarkup(source)}
    </details>
    ${current ? `<details class="product-research-learning-analysis" open>
      <summary>Текущий структурированный разбор</summary>
      <pre>${escapeHtml(analysis)}</pre>
    </details>
    <details class="product-research-learning-analysis-history">
      <summary>История исправлений (${source.analysisHistory.length})</summary>
      ${researchCategoryAnalysisHistoryMarkup(source)}
    </details>
    <details class="product-research-learning-correction">
      <summary>Исправить разбор без перезаписи истории</summary>
      <form class="product-research-source-correction-form form-stack" data-source-ledger-id="${escapeHtml(source.sourceLedgerId)}" novalidate>
        <input type="hidden" name="expected_head_event_id" value="${escapeHtml(current.eventId)}" />
        <input type="hidden" name="expected_head_hash" value="${escapeHtml(current.eventHash)}" />
        <label class="field"><span>Исправленный JSON-разбор</span><textarea name="analysis" maxlength="32768" required>${escapeHtml(analysis)}</textarea><small>Raw captions, transcript и полный чужой текст запрещены. Сохраняйте только ограниченные признаки и выводы.</small></label>
        <label class="field"><span>Почему меняется разбор</span><textarea name="correction_reason" minlength="3" maxlength="1000" required placeholder="Что было неверно и на каком доказательстве основано исправление"></textarea></label>
        <label class="check-row"><input type="checkbox" name="correction_confirmation" required /><span><strong>Проверена точная версия ${current.analysisVersion}</strong><br /><small>Если head уже изменился, сервер отклонит команду; автоматического повтора и provider call нет.</small></span></label>
        <button class="btn btn-secondary btn-small" type="submit" ${saving ? "disabled" : ""}>Сохранить append-only исправление</button>
      </form>
    </details>` : '<p class="product-research-learning-source-note">Parser ещё не создал структурированный head. UI не подменяет его догадкой и не может создать первое исправление.</p>'}
  </article>`;
}

function researchCategoryRetainedYoutubeCardMarkup(item, { saving = false } = {}) {
  const decision = item.latestDecision;
  const current = item.currentAnalysis;
  const job = item.analysisJob;
  const decisionLabel = !decision
    ? "Решение ещё не зафиксировано"
    : decision.decision === "exclude_candidate"
      ? "Исключено человеком из готовности"
      : "Подтверждено человеком";
  const readinessLabel = decision?.decision === "confirm_candidate"
    ? "Подтверждён: конкурент + human validation"
    : decision?.decision === "exclude_candidate"
      ? "Не учитывается в готовности"
      : "Только объём источников и площадка";
  const hypothesisLabel = current
    ? ({
        potential_competitor: "возможный конкурент — проверить",
        adjacent: "смежное наблюдение",
        unknown: "недостаточно признаков",
      })[current.analysis.classification]
    : job?.status === "approval_required"
      ? "локальный разбор: требуется YouTube analytics approval"
      : job?.status === "failed"
      ? "локальный разбор завершился ошибкой"
      : job
        ? `локальный разбор: ${job.status}`
        : "локальный разбор ещё не поставлен";
  const analysisMarkup = current ? `<section class="product-research-learning-analysis" aria-label="Машинная гипотеза по YouTube-наблюдению">
    <header><strong>Машинная гипотеза, не установленный факт</strong><span class="badge">приоритет проверки ${current.analysis.review_priority}/100</span><span class="badge">${escapeHtml(current.analysis.confidence)}</span></header>
    <p>${escapeHtml(current.analysis.summary)}</p>
    <dl class="product-research-learning-lineage">
      <div><dt>Совпадение запроса</dt><dd>${current.analysis.signals.query_token_overlap_count}/${current.analysis.signals.query_token_count} токенов</dd></div>
      <div><dt>Позиция</dt><dd>${current.analysis.signals.search_position}</dd></div>
      <div><dt>Возраст</dt><dd>${current.analysis.signals.published_age_days} дн.</dd></div>
      <div><dt>Видео канала в сборе</dt><dd>${current.analysis.signals.same_channel_observation_count}</dd></div>
      <div><dt>Public counters</dt><dd>${current.analysis.signals.counters_present ? "есть" : "нет"}</dd></div>
      <div><dt>Версия head</dt><dd>${current.analysisVersion} · <code>${escapeHtml(current.eventHash.slice(0, 10))}…</code></dd></div>
    </dl>
    <ul>${current.analysis.limitations.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>
    <details><summary>Append-only история гипотезы (${item.analysisHistory.length} из максимум 10)</summary><ol>${item.analysisHistory.map((event) => `<li><strong>v${event.analysisVersion} · ${event.origin === "human_correction" ? "исправлено человеком" : "детерминированный parser"}</strong><span>${escapeHtml(researchYoutubeDateTimeLabel(event.createdAt))}${event.correctionReason ? ` · ${escapeHtml(event.correctionReason)}` : ""}</span><code>${escapeHtml(event.eventHash.slice(0, 10))}…</code></li>`).join("")}</ol></details>
    ${item.canCorrectAnalysis ? `<details><summary>Исправить гипотезу без повторного provider call</summary>
      <form class="product-research-youtube-analysis-correction-form form-stack" data-observation-id="${escapeHtml(item.observationId)}" novalidate>
        <input type="hidden" name="observation_hash" value="${escapeHtml(item.observationHash)}" />
        <input type="hidden" name="expected_head_event_id" value="${escapeHtml(current.eventId)}" />
        <input type="hidden" name="expected_head_hash" value="${escapeHtml(current.eventHash)}" />
        <label class="field"><span>Исправленная retention-bound гипотеза (JSON schema v1)</span><textarea name="analysis" rows="13" required>${escapeHtml(researchCategoryPrettyAnalysis(current.analysis))}</textarea><small>Допустимы potential_competitor, adjacent и unknown. Это не подтверждение конкурента; confirm/exclude остаётся отдельным решением.</small></label>
        <label class="field"><span>Почему меняется гипотеза</span><textarea name="correction_reason" minlength="3" maxlength="1000" required></textarea></label>
        <label class="check-row"><input type="checkbox" name="correction_confirmation" required /><span><strong>Проверена точная версия ${current.analysisVersion}</strong><br /><small>Stale head будет отклонён; автоматического retry, provider call или durable-копирования нет.</small></span></label>
        <button class="btn btn-secondary btn-small" type="submit" ${saving ? "disabled" : ""}>Сохранить append-only исправление</button>
      </form>
    </details>` : ""}
  </section>` : `<aside class="product-research-learning-provider-blocked" role="note"><strong>${escapeHtml(hypothesisLabel)}</strong><span>${job?.status === "approval_required" ? "Official retrieval/display и derived analysis разделены. Parser останется остановлен до зафиксированного analytics-amendment approval; это видимый coverage gap, а не скрытый scraping fallback." : job?.status === "failed" ? `Код: ${escapeHtml(job.errorCode)}. Ошибка видима и не запускает повтор YouTube ingestion.` : "Фоновый worker выполнит только локальный детерминированный parser: ноль HTTP, provider attempts и стоимости."}</span></aside>`;
  return `<article class="product-research-learning-source product-research-learning-retained-youtube-card ${item.includedInReadiness ? "is-included" : "is-excluded"}">
    <header>
      <div><span class="badge">YouTube · 29 дней</span><span class="badge">${escapeHtml(RESEARCH_YOUTUBE_PROVIDER_KEY)}</span><span class="badge">${escapeHtml(readinessLabel)}</span><span class="badge">${escapeHtml(hypothesisLabel)}</span></div>
      <a href="${escapeHtml(item.sourceUrl)}" target="_blank" rel="noopener noreferrer nofollow">Открыть видео <span aria-hidden="true">↗</span></a>
    </header>
    <h3>${escapeHtml(item.title)}</h3>
    <p class="product-research-learning-provenance">${escapeHtml(item.channelTitle)} · channel <code>${escapeHtml(item.channelId)}</code></p>
    <dl class="product-research-learning-lineage">
      <div><dt>Наблюдение</dt><dd><code>${escapeHtml(item.observationId.slice(0, 8))}…</code></dd></div>
      <div><dt>Получено</dt><dd>${escapeHtml(researchYoutubeDateTimeLabel(item.observedAt))}</dd></div>
      <div><dt>Опубликовано</dt><dd>${escapeHtml(researchYoutubeDateTimeLabel(item.publishedAt))}</dd></div>
      <div><dt>Удаление по retention</dt><dd>${escapeHtml(researchYoutubeDateTimeLabel(item.retentionExpiresAt))}</dd></div>
      <div><dt>Ingestion</dt><dd><code>${escapeHtml(item.ingestionId.slice(0, 8))}…</code></dd></div>
      <div><dt>Observation hash</dt><dd><code>${escapeHtml(item.observationHash.slice(0, 10))}…</code></dd></div>
    </dl>
    ${analysisMarkup}
    <aside class="product-research-learning-retained-decision" role="note">
      <strong>${escapeHtml(decisionLabel)}</strong>
      ${decision ? `<span>${escapeHtml(researchYoutubeDateTimeLabel(decision.decidedAt))}${decision.reason ? ` · ${escapeHtml(decision.reason)}` : ""}</span>` : ""}
      <small>Confirm_candidate добавляет только одно дедуплицированное наблюдение конкурента и human validation. Сырые metadata сами не повышают analysis coverage; его повышает только точный retention-bound parser head. Решение кандидата <code>creator_decide_research_youtube_candidate</code> и исправление гипотезы <code>creator_correct_research_youtube_observation_analysis</code> — разные append-only команды. Raw captions не хранятся.</small>
    </aside>
  </article>`;
}

function researchCategoryPolicyState(policy) {
  if (!policy) return "proposed";
  if (policy.status !== "enabled") return "paused";
  return policy.automaticEnqueueSupported ? "active" : "rollout_blocked";
}

function researchCategoryPolicyStateLabel(value) {
  return ({
    proposed: "Предложено, но не включено",
    active: "Политика включена",
    rollout_blocked: "Включено, rollout закрыт",
    paused: "Приостановлено",
  })[value] || value;
}

function researchCategoryPolicyMarkup(control, platform, {
  saving = false,
  writable = true,
} = {}) {
  const policy = control.policies.find((item) => item.platform === platform) || null;
  const state = researchCategoryPolicyState(policy);
  const youtube = platform === "youtube";
  const providerKey = policy?.providerKey
    || (youtube ? "youtube_data_api_v3" : "instagram_provider_pending");
  const cadenceHours = policy?.cadenceHours || 168;
  const maxRecords = policy?.maxRecords || (youtube ? 10 : 1);
  const budgetUnits = policy?.monthlyHardBudgetUnits || 0;
  const termsVersion = policy?.termsVersion
    || RESEARCH_CATEGORY_YOUTUBE_TERMS_VERSION;
  if (!writable) {
    return `<article class="product-research-learning-policy ${state === "active" ? "is-active" : ""}">
      <header><div><p class="eyebrow">${youtube ? "YouTube" : "Instagram"}</p><h3>${escapeHtml(researchCategoryPolicyStateLabel(state))}</h3></div><span class="badge">${escapeHtml(providerKey)}</span></header>
      <p>${policy ? `Период ${cadenceHours} ч. · до ${maxRecords} записей · hard budget ${budgetUnits} units/мес.` : "Политика ещё не сохранена."}</p>
      <aside class="product-research-learning-provider-blocked" role="note"><strong>Режим только для чтения.</strong><span>Активировать или приостановить автосбор может owner/admin после legal, terms и budget gates.</span></aside>
    </article>`;
  }
  return `<article class="product-research-learning-policy ${state === "active" ? "is-active" : ""}">
    <header><div><p class="eyebrow">${youtube ? "YouTube" : "Instagram"}</p><h3>${escapeHtml(researchCategoryPolicyStateLabel(state))}</h3></div><span class="badge">${escapeHtml(providerKey)}</span></header>
    <p>${youtube
      ? `Включение создаёт только bounded задания по расписанию после rollout, retention, legal и budget gates. Status/render ничего не собирают и не тратят.${policy?.automaticEnqueueSupported ? " Автоматический enqueue поддержан; внешний transport выполнит только внутренний worker." : " Автоматический enqueue сейчас выключен."}`
      : "Автосбор Instagram заблокирован до выбора лицензированного provider и юридической политики. Сохранить можно только paused-предложение."}</p>
    <form class="product-research-collection-policy-form form-stack" data-platform="${platform}" novalidate>
      <input type="hidden" name="provider_key" value="${escapeHtml(providerKey)}" />
      <input type="hidden" name="expected_policy_id" value="${escapeHtml(policy?.policyId || "")}" />
      <input type="hidden" name="expected_policy_hash" value="${escapeHtml(policy?.policyHash || "")}" />
      <input type="hidden" name="terms_version" value="${escapeHtml(termsVersion)}" />
      <div class="form-grid-3">
        <label class="field"><span>Период, часов</span><input type="number" name="cadence_hours" min="24" max="720" step="1" value="${cadenceHours}" required /></label>
        <label class="field"><span>Записей за цикл</span><input type="number" name="max_records" min="1" max="25" step="1" value="${maxRecords}" required /></label>
        <label class="field"><span>Hard budget, units/мес.</span><input type="number" name="monthly_hard_budget_units" min="0" max="100" step="1" value="${budgetUnits}" required /></label>
      </div>
      <label class="field"><span>Ссылка/номер legal review</span><input name="legal_review_reference" minlength="3" maxlength="160" value="${escapeHtml(policy?.legalReviewReference || "")}" placeholder="LEGAL-2026-…" /></label>
      <label class="field"><span>Причина изменения</span><textarea name="reason" minlength="3" maxlength="500" required>${escapeHtml(policy?.reason || (youtube ? "Настроить ограниченный сбор доказательств категории" : "Сохранить Instagram-контур paused до выбора provider"))}</textarea></label>
      ${youtube ? `<div class="product-research-learning-acks">
        <label class="check-row"><input type="checkbox" name="automatic_collection_ack" ${policy?.automaticCollectionAck ? "checked" : ""} /><span><strong>Явно разрешаю автоматический bounded enqueue</strong><br /><small>Это не разрешение на публикацию или копирование чужого контента.</small></span></label>
        <label class="check-row"><input type="checkbox" name="terms_ack" ${policy?.termsAck ? "checked" : ""} /><span><strong>Проверены YouTube Terms ${escapeHtml(termsVersion)}</strong></span></label>
        <label class="check-row"><input type="checkbox" name="quota_ack" ${policy?.quotaAck ? "checked" : ""} /><span><strong>Подтверждены quota и месячный hard budget</strong></span></label>
        <label class="check-row"><input type="checkbox" name="no_retry_ack" ${policy?.noRetryAck ? "checked" : ""} /><span><strong>Понимаю: automatic retry и provider fallback запрещены</strong></span></label>
      </div>` : `<aside class="product-research-learning-provider-blocked" role="note"><strong>Автоматический Instagram-сбор недоступен.</strong><span>Нужны provider contract, legal choice, retention и deletion SLA. UI не предложит фиктивное включение.</span></aside>`}
      <div class="inline-actions">
        <button class="btn btn-secondary btn-small" type="submit" data-collection-policy-status="paused" ${saving ? "disabled" : ""}>${policy ? "Сохранить и приостановить" : "Сохранить paused-предложение"}</button>
        ${youtube ? `<button class="btn btn-small" type="submit" data-collection-policy-status="enabled" ${saving ? "disabled" : ""}>Включить после всех подтверждений</button>` : ""}
      </div>
    </form>
  </article>`;
}

function researchCategoryCollectionHistoryMarkup(control) {
  if (!control.collectionHistory.length) {
    return '<p class="muted">Планировщик ещё не принимал bounded-решений. Проверка статуса сама ничего не запускает.</p>';
  }
  return `<ol>${control.collectionHistory.map((item) => `<li>
    <div>
      <strong>${escapeHtml(researchCategoryPlatformLabel(item.platform))} · решение планировщика: ${item.status === "queued" ? "bounded enqueue создан" : "автосбор заблокирован"}</strong>
      <small>${escapeHtml(researchYoutubeDateTimeLabel(item.createdAt))} · ${escapeHtml(item.queryText)}${item.blockedReason ? ` · ${escapeHtml(item.blockedReason)}` : ""} · это неизменяемая история решения, а не текущий статус задачи</small>
      <span class="product-research-learning-ingestion-status"><b>Фактический ingestion:</b> ${item.ingestionId ? `${escapeHtml(item.ingestionStatus)} · <code>${escapeHtml(item.ingestionId.slice(0, 8))}…</code> · transport attempts ${item.transportAttemptCount}/2` : "не создан"}${item.ingestionRequestedAt ? ` · запрошен ${escapeHtml(researchYoutubeDateTimeLabel(item.ingestionRequestedAt))}` : ""}${item.ingestionCompletedAt ? ` · завершён ${escapeHtml(researchYoutubeDateTimeLabel(item.ingestionCompletedAt))}` : ""}${item.ingestionErrorCode ? ` · ошибка ${escapeHtml(item.ingestionErrorCode)}` : ""}</span>
      <small>Automatic retry и provider fallback запрещены.</small>
    </div>
    <code>${escapeHtml(item.intentHash.slice(0, 10))}…</code>
  </li>`).join("")}</ol>`;
}

export function researchCategoryLearningMarkup(value, {
  saving = false,
  policyWritable = true,
} = {}) {
  const control = value?.available ? value : null;
  if (!control) {
    const invalid = value?.reason === "invalid_contract";
    return `<section class="card card-pad product-research-learning-unavailable" aria-labelledby="research-category-learning-title">
      <p class="eyebrow">Обучаемость категории</p>
      <h2 id="research-category-learning-title">Готовность доказательной базы категории пока недоступна</h2>
      <p>${invalid
        ? "Сервер вернул неизвестную версию или неполный lineage. Основное исследование осталось доступно, но процент не показывается, чтобы не создавать ложную точность."
        : "Категория ещё не привязана либо независимый status-контур временно не ответил. Основной разбор не заблокирован и никакой provider call не повторялся."}</p>
      <button class="btn btn-secondary btn-small" type="button" data-action="refresh-product-research">Проверить общий статус</button>
    </section>`;
  }
  const providerStrategyMarkup = control.providerStrategy
    ? `<aside class="product-research-learning-provider-blocked" role="note"><strong>Рекомендация источников: official-first</strong><span>YouTube Data API v3 используется только в controlled rollout для разрешённого retrieval/display. Derived competitor/trend analysis: <code>${escapeHtml(control.providerStrategy.youtubeDerivedAnalysisState)}</code>${control.providerStrategy.youtubeDerivedAnalysisApprovalRef ? ` · approval <code>${escapeHtml(control.providerStrategy.youtubeDerivedAnalysisApprovalRef)}</code>` : " · требуется отдельный analytics-amendment approval"}. Meta Instagram после OAuth/App Review поддерживает lookup известных Professional accounts и ограниченный hashtag discovery; произвольный поиск аккаунтов остаётся <code>unsupported_coverage_gap</code>. Apify, Bright Data, Oxylabs и DataForSEO scraping остаются disabled_by_policy.</span></aside>`
    : "";
  const historyMarkup = control.readinessHistory.length
    ? `<ol>${control.readinessHistory.map((snapshot, index) => {
      const newerSnapshot = control.readinessHistory[index - 1];
      const formulaBoundary = newerSnapshot
          && newerSnapshot.definitionVersion !== snapshot.definitionVersion
        ? `<li class="product-research-learning-formula-boundary" role="note"><strong>Формула изменена</strong><span>${escapeHtml(newerSnapshot.definitionVersion)} ↔ ${escapeHtml(snapshot.definitionVersion)} · точки напрямую не сравниваются</span></li>`
        : "";
      return `${formulaBoundary}<li><strong>${snapshot.score}%</strong><span>${escapeHtml(researchYoutubeDateTimeLabel(snapshot.capturedAt))} · ${escapeHtml(snapshot.definitionVersion)}</span><code>${escapeHtml(snapshot.snapshotHash.slice(0, 10))}…</code></li>`;
    }).join("")}</ol>`
    : '<p class="muted">История пуста. Она появляется только после явной фиксации снимка и не пишется при простом наведении или status-вызове.</p>';
  return `<section class="card product-research-learning" aria-labelledby="research-category-learning-title">
    <div class="card-header">
      <div><p class="eyebrow">Обучаемость категории</p><h2 id="research-category-learning-title">Готовность доказательной базы категории</h2><p>${escapeHtml(control.category.canonicalName)} · версия привязки ${control.category.bindingVersion}</p></div>
      <span class="badge">${escapeHtml(researchCategoryGuidanceLabel(control.guidanceStatus))}</span>
    </div>
    <div class="product-research-learning-overview">
      <div class="product-research-learning-meter" style="--research-learning-score:${control.score}" role="img" aria-label="Готовность доказательной базы категории: ${control.score} процентов" title="${escapeHtml(`Готовность доказательной базы: ${control.score}%. Это не IQ и не accuracy модели.`)}">
        <strong>${control.score}%</strong><small>доказательства</small>
      </div>
      <div><h3>Это не IQ, не accuracy модели и не гарантия качества</h3><p>Процент детерминированно показывает покрытие доказательств выбранной категории на ${escapeHtml(researchYoutubeDateTimeLabel(control.asOf))}. Сырые YouTube-метаданные с 29-дневным retention дают только объём и площадку; analysis coverage появляется лишь после точного локального parser head. Гипотеза не становится конкурентом или трендом без решения человека.</p><small>Формула ${escapeHtml(control.readinessDefinition || RESEARCH_CATEGORY_READINESS_DEFINITION)} · Evidence hash <code>${escapeHtml(control.evidenceHash.slice(0, 12))}…</code> · raw captions не хранятся.</small></div>
      <form class="product-research-readiness-capture-form" novalidate>
        <input type="hidden" name="expected_evidence_hash" value="${escapeHtml(control.evidenceHash)}" />
        <button class="btn btn-secondary btn-small" type="submit" ${saving ? "disabled" : ""}>Зафиксировать снимок в истории</button>
      </form>
    </div>
    <div class="product-research-learning-dimensions" aria-label="Шесть измерений готовности">${control.dimensions.map(researchCategoryDimensionMarkup).join("")}</div>
    <details class="product-research-learning-history">
      <summary>Оцифрованная история (${control.readinessHistory.length} из максимум 24)</summary>
      ${historyMarkup}
    </details>
    <div class="product-research-learning-section-heading"><div><p class="eyebrow">Source ledger</p><h3>Источники, разбор и lineage</h3></div><span class="badge">${control.sources.length} из максимум 50</span></div>
    <div class="product-research-learning-sources">${control.sources.length
      ? control.sources.map((source) => researchCategorySourceCardMarkup(source, { saving })).join("")
      : '<div class="product-research-empty-note"><strong>Устойчивых источников пока нет</strong><p>Процент остаётся низким; система должна предложить сбор, а не дорисовывать факты.</p></div>'}</div>
    <div class="product-research-learning-section-heading"><div><p class="eyebrow">Retained YouTube evidence</p><h3>Свежие YouTube-наблюдения и машинные гипотезы</h3><small>Метаданные, parser jobs, системные разборы и исправления человека удаляются вместе через 29 дней. Локальный parser не вызывает провайдера, не повторяет ingestion и даёт credit только analysis coverage. Competitor/trend credit остаётся за отдельным human decision.</small></div><span class="badge">${control.retainedYoutubeEvidence.length} из максимум 50</span></div>
    <div class="product-research-learning-sources product-research-learning-retained-youtube">${control.retainedYoutubeEvidence.length
      ? control.retainedYoutubeEvidence.map((item) => researchCategoryRetainedYoutubeCardMarkup(item, { saving })).join("")
      : '<div class="product-research-empty-note"><strong>Сохранённых YouTube-наблюдений пока нет</strong><p>При разрешённой политике внутренний worker может собрать bounded public metadata; status/render ничего не запускают.</p></div>'}</div>
    <div class="product-research-learning-section-heading"><div><p class="eyebrow">Управляемый автосбор</p><h3>Политики YouTube и Instagram</h3><small>Только owner/admin могут менять политику; остальная готовность и source ledger остаются видимыми команде.</small></div><span class="badge">status/render без provider call</span></div>
    ${providerStrategyMarkup}
    <div class="product-research-learning-policies">
      ${researchCategoryPolicyMarkup(control, "youtube", { saving, writable: policyWritable })}
      ${researchCategoryPolicyMarkup(control, "instagram", { saving, writable: policyWritable })}
    </div>
    <details class="product-research-learning-collection-history">
      <summary>Решения планировщика и фактический ingestion (${control.collectionHistory.length} из максимум 24)</summary>
      ${researchCategoryCollectionHistoryMarkup(control)}
    </details>
  </section>`;
}

export function normalizeResearchStageControl(raw, expectedRunId = "") {
  const source = objectValue(raw?.data) || objectValue(raw);
  const unavailable = {
    available: false,
    runId: String(expectedRunId || "").trim().toLowerCase(),
    branches: [],
    heads: [],
    history: [],
    activeRecompute: null,
    guidance: null,
  };
  if (
    !source
    || source.ok !== true
    || source.version !== RESEARCH_STAGE_CONTROL_VERSION
  ) return unavailable;
  const organizationId = researchOutcomeUuid(source.organization_id);
  const runId = researchOutcomeUuid(source.run_id);
  const expected = String(expectedRunId || "").trim().toLowerCase();
  const selectedSource = objectValue(source.selected_branch);
  const selectedBranchId = researchOutcomeUuid(selectedSource?.branch_id);
  const selectedBranchKey = String(selectedSource?.branch_key || "").trim();
  const selectedBranchRevisionHash = String(
    selectedSource?.branch_revision_hash || "",
  ).trim().toLowerCase();
  if (
    !organizationId
    || !runId
    || (expected && runId !== expected)
    || !selectedBranchId
    || !/^[a-z0-9][a-z0-9_-]{0,63}$/u.test(selectedBranchKey)
    || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(selectedBranchRevisionHash)
  ) return unavailable;

  const branchIds = new Set();
  const branches = [];
  for (const item of arrayValue(source.branches)) {
    const branch = objectValue(item);
    const branchId = researchOutcomeUuid(branch?.branch_id);
    const branchKey = String(branch?.branch_key || "").trim();
    const parentBranchId = branch?.parent_branch_id === null
      ? ""
      : researchOutcomeUuid(branch?.parent_branch_id);
    const headCount = Number(branch?.head_count);
    const problemCount = Number(branch?.problem_count);
    if (
      !branchId
      || branchIds.has(branchId)
      || !/^[a-z0-9][a-z0-9_-]{0,63}$/u.test(branchKey)
      || (branch?.parent_branch_id !== null && !parentBranchId)
      || !Number.isSafeInteger(headCount)
      || headCount < 0
      || headCount > RESEARCH_STAGE_ORDER.length
      || !Number.isSafeInteger(problemCount)
      || problemCount < 0
      || problemCount > headCount
    ) return unavailable;
    branchIds.add(branchId);
    branches.push({
      branchId,
      branchKey,
      parentBranchId,
      reason: String(branch.reason || "").trim().slice(0, 500),
      createdAt: String(branch.created_at || ""),
      selected: branch.is_selected === true || branchId === selectedBranchId,
      headCount,
      problemCount,
    });
  }
  if (!branchIds.has(selectedBranchId)) return unavailable;

  const stages = new Set();
  const heads = [];
  for (const item of arrayValue(source.heads)) {
    const head = objectValue(item);
    const stage = String(head?.stage || "").trim().toLowerCase();
    const state = String(head?.state || "").trim().toLowerCase();
    const headEventId = researchOutcomeUuid(head?.head_event_id);
    const artifactId = researchOutcomeUuid(head?.artifact_id);
    const parentArtifactId = head?.parent_artifact_id === null
      ? ""
      : researchOutcomeUuid(head?.parent_artifact_id);
    const currentDraftId = researchOutcomeUuid(head?.current_draft_id);
    const contentHash = String(head?.content_hash || "").trim().toLowerCase();
    const dependencyHash = String(head?.dependency_hash || "").trim().toLowerCase();
    const inputDependencyHash = String(
      head?.artifact_input_dependency_hash || "",
    ).trim().toLowerCase();
    const artifactVersion = Number(head?.artifact_version);
    const evidenceCount = Number(head?.evidence_count);
    const payload = objectValue(head?.payload);
    const allowedActions = [...new Set(arrayValue(head?.allowed_actions)
      .map((action) => String(action || "").trim().toLowerCase()))];
    const staleDueToArtifactIds = arrayValue(
      head?.stale_due_to_artifact_ids,
    ).map(researchOutcomeUuid);
    if (
      !RESEARCH_STAGE_ORDER.includes(stage)
      || stages.has(stage)
      || !RESEARCH_STAGE_CONTROL_STATES.has(state)
      || !headEventId
      || !artifactId
      || (head?.parent_artifact_id !== null && !parentArtifactId)
      || !currentDraftId
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(contentHash)
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(dependencyHash)
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(inputDependencyHash)
      || !Number.isSafeInteger(artifactVersion)
      || artifactVersion < 1
      || !Number.isSafeInteger(evidenceCount)
      || evidenceCount < 0
      || !payload
      || allowedActions.some((action) => !RESEARCH_STAGE_CONTROL_ACTIONS.has(action))
      || staleDueToArtifactIds.some((id) => !id)
    ) return unavailable;
    stages.add(stage);
    heads.push({
      stage,
      state,
      headEventId,
      artifactId,
      artifactVersion,
      parentArtifactId,
      currentDraftId,
      contentHash,
      dependencyHash,
      inputDependencyHash,
      staleDueToArtifactIds,
      payload,
      evidenceCount,
      artifactOrigin: String(head.artifact_origin || ""),
      artifactCreatedAt: String(head.artifact_created_at || ""),
      updatedAt: String(head.updated_at || ""),
      allowedActions,
    });
  }
  heads.sort((left, right) =>
    RESEARCH_STAGE_ORDER.indexOf(left.stage)
      - RESEARCH_STAGE_ORDER.indexOf(right.stage)
  );

  const historyLimit = Number(source.history_limit);
  if (
    !Number.isSafeInteger(historyLimit)
    || historyLimit < 1
    || historyLimit > 100
    || arrayValue(source.history).length > historyLimit
  ) return unavailable;
  const history = arrayValue(source.history).flatMap((item) => {
    const event = objectValue(item);
    const eventId = researchOutcomeUuid(event?.event_id);
    const commandId = researchOutcomeUuid(event?.command_id);
    const stage = String(event?.stage || "").trim().toLowerCase();
    const artifactId = researchOutcomeUuid(event?.artifact_id);
    const priorArtifactId = event?.prior_artifact_id === null
      ? ""
      : researchOutcomeUuid(event?.prior_artifact_id);
    if (
      !eventId
      || !commandId
      || !RESEARCH_STAGE_ORDER.includes(stage)
      || !artifactId
      || (event?.prior_artifact_id !== null && !priorArtifactId)
    ) return [];
    return [{
      eventId,
      commandId,
      stage,
      action: String(event.action || ""),
      state: String(event.state || ""),
      artifactId,
      priorArtifactId,
      reason: String(event.reason || "").trim().slice(0, 500),
      origin: String(event.origin || ""),
      createdAt: String(event.created_at || ""),
    }];
  });

  let activeRecompute = null;
  if (source.active_recompute !== null && source.active_recompute !== undefined) {
    const active = objectValue(source.active_recompute);
    const requestId = researchOutcomeUuid(active?.request_id);
    const childRunId = researchOutcomeUuid(active?.child_run_id);
    const status = String(active?.status || "").trim().toLowerCase();
    const providerAttemptCount = Number(active?.provider_attempt_count);
    const maxProviderAttempts = Number(active?.max_provider_attempts);
    const expectedBranchRevisionHash = String(
      active?.expected_branch_revision_hash || "",
    ).trim().toLowerCase();
    const leaseExpiresAt = active?.lease_expires_at === null
      ? ""
      : String(active?.lease_expires_at || "").trim();
    const cancelReason = active?.cancel_reason === null
      ? ""
      : String(active?.cancel_reason || "").trim();
    const invoke = objectValue(active?.invoke);
    const branchChangedAfterPrepare = cancelReason
      === "branch_changed_after_prepare";
    if (
      !active
      || !requestId
      || !childRunId
      || !RESEARCH_STAGE_ORDER.includes(String(active.stage || ""))
      || !["queued", "processing"].includes(status)
      || active.paid_analysis_ack !== true
      || active.provider_key !== "openai_web_search"
      || active.adapter_version !== "research-stage-recompute-v1"
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(expectedBranchRevisionHash)
      || active.automatic_provider_action !== false
      || typeof active.can_cancel !== "boolean"
      || (active?.lease_expires_at !== null && !leaseExpiresAt)
      || (leaseExpiresAt && Number.isNaN(Date.parse(leaseExpiresAt)))
      || (active?.cancel_reason !== null && !cancelReason)
      || cancelReason.length > 500
      || (active.can_cancel === true && !cancelReason)
      || (
        status === "queued"
        && branchChangedAfterPrepare
        && active?.invoke !== null
      )
      || (
        status === "queued"
        && !branchChangedAfterPrepare
        && (
          !invoke
          || invoke.action !== "analyze"
          || researchOutcomeUuid(invoke.research_id) !== childRunId
        )
      )
      || (status === "processing" && active.invoke !== null)
      || !Number.isSafeInteger(providerAttemptCount)
      || providerAttemptCount < 0
      || providerAttemptCount > 1
      || (status === "queued" && providerAttemptCount !== 0)
      || (status === "processing" && providerAttemptCount !== 1)
      || (status === "queued" && leaseExpiresAt)
      || (status === "processing" && !leaseExpiresAt)
      || !Number.isSafeInteger(maxProviderAttempts)
      || maxProviderAttempts !== 1
    ) return unavailable;
    activeRecompute = {
      requestId,
      childRunId,
      stage: String(active.stage),
      status,
      paidAnalysisAck: active.paid_analysis_ack === true,
      providerKey: String(active.provider_key || ""),
      adapterVersion: String(active.adapter_version || ""),
      maxProviderAttempts,
      providerAttemptCount,
      expectedBranchRevisionHash,
      createdAt: String(active.created_at || ""),
      startedAt: String(active.started_at || ""),
      errorCode: String(active.error_code || ""),
      errorMessage: String(active.error_message || ""),
      leaseExpiresAt,
      canCancel: active.can_cancel === true,
      cancelReason,
    };
    const activeHead = heads.find((head) => head.stage === activeRecompute.stage);
    if (
      !activeHead
      || (
        activeRecompute.canCancel
        && !activeHead.allowedActions.includes("cancel")
      )
    ) return unavailable;
  }

  const guidanceSource = objectValue(source.guidance);
  if (!guidanceSource) return unavailable;
  const affectedStages = arrayValue(guidanceSource.affected_stages)
    .map((stage) => String(stage || "").trim().toLowerCase());
  if (affectedStages.some((stage) => !RESEARCH_STAGE_ORDER.includes(stage))) {
    return unavailable;
  }
  if (
    guidanceSource.recompute_requires_paid_confirmation !== true
    || guidanceSource.automatic_provider_action !== false
    || guidanceSource.automatic_spend !== false
    || guidanceSource.automatic_generation !== false
    || guidanceSource.automatic_publication !== false
  ) return unavailable;
  const currentDraftId = guidanceSource.current_draft_id === null
    ? ""
    : researchOutcomeUuid(guidanceSource.current_draft_id);
  const approvedDraftId = guidanceSource.approved_draft_id === null
    ? ""
    : researchOutcomeUuid(guidanceSource.approved_draft_id);
  const currentDraftOrigin = String(
    guidanceSource.current_draft_origin || "",
  ).trim().toLowerCase();
  const currentDraftStatus = String(
    guidanceSource.current_draft_status || "",
  ).trim().toLowerCase();
  const exactSnapshotStageCount = Number(
    guidanceSource.exact_snapshot_stage_count,
  );
  const branchCount = Number(guidanceSource.branch_count);
  if (
    (guidanceSource.current_draft_id !== null && !currentDraftId)
    || (guidanceSource.approved_draft_id !== null && !approvedDraftId)
    || !Number.isSafeInteger(exactSnapshotStageCount)
    || exactSnapshotStageCount < 0
    || exactSnapshotStageCount > RESEARCH_STAGE_ORDER.length
    || exactSnapshotStageCount > heads.length
    || !Number.isSafeInteger(branchCount)
    || branchCount !== branches.length
    || typeof guidanceSource.approval_allowed !== "boolean"
    || typeof guidanceSource.generation_handoff_allowed !== "boolean"
    || (
      currentDraftId
      && (
        !["ai", "human"].includes(currentDraftOrigin)
        || !["draft", "approved", "superseded", "rejected"].includes(
          currentDraftStatus,
        )
      )
    )
    || (!currentDraftId && (currentDraftOrigin || currentDraftStatus))
    || (exactSnapshotStageCount > 0 && !currentDraftId)
    || (
      guidanceSource.approval_allowed === true
      && (
        currentDraftOrigin !== "human"
        || currentDraftStatus !== "draft"
        || exactSnapshotStageCount !== RESEARCH_STAGE_ORDER.length
      )
    )
    || (
      guidanceSource.generation_handoff_allowed === true
      && (
        !approvedDraftId
        || approvedDraftId !== currentDraftId
        || currentDraftStatus !== "approved"
        || exactSnapshotStageCount !== RESEARCH_STAGE_ORDER.length
      )
    )
  ) return unavailable;
  return {
    available: true,
    version: RESEARCH_STAGE_CONTROL_VERSION,
    organizationId,
    runId,
    selectedBranch: {
      branchId: selectedBranchId,
      branchKey: selectedBranchKey,
      branchRevisionHash: selectedBranchRevisionHash,
      parentBranchId: selectedSource.parent_branch_id === null
        ? ""
        : researchOutcomeUuid(selectedSource.parent_branch_id),
      reason: String(selectedSource.reason || "").trim().slice(0, 500),
      createdAt: String(selectedSource.created_at || ""),
    },
    branches,
    heads,
    history,
    historyLimit,
    historyHasMore: source.history_has_more === true,
    activeRecompute,
    guidance: {
      status: String(guidanceSource.status || "").trim(),
      recommendedNextAction: String(
        guidanceSource.recommended_next_action || "",
      ).trim(),
      earliestProblemStage: String(
        guidanceSource.earliest_problem_stage || "",
      ).trim(),
      earliestProblemState: String(
        guidanceSource.earliest_problem_state || "",
      ).trim(),
      affectedStages,
      approvalAllowed: guidanceSource.approval_allowed === true,
      currentDraftId,
      currentDraftOrigin,
      currentDraftStatus,
      exactSnapshotStageCount,
      approvedDraftId,
      generationHandoffAllowed:
        guidanceSource.generation_handoff_allowed === true,
      recomputeRequiresPaidConfirmation:
        guidanceSource.recompute_requires_paid_confirmation === true,
      automaticProviderAction:
        guidanceSource.automatic_provider_action === true,
      automaticSpend: guidanceSource.automatic_spend === true,
      automaticGeneration: guidanceSource.automatic_generation === true,
      automaticPublication: guidanceSource.automatic_publication === true,
      branchCount,
    },
  };
}

export function productResearchStatusKind(status) {
  const normalized = String(status || "").toLowerCase();
  if (READY_STATUSES.has(normalized)) return "ready";
  if (["failed", "cancelled", "rejected"].includes(normalized)) return "failed";
  return ACTIVE_STATUSES.has(normalized) ? "active" : "active";
}

/**
 * Accepts only the fixed category vocabulary shared with the AI control room.
 * Free-form titles and product names are deliberately never inferred here.
 */
export function normalizeProductResearchAiCategory(value, fallback = "") {
  const candidate = String(value || "").trim().toLowerCase();
  if (PRODUCT_RESEARCH_AI_CATEGORY_SET.has(candidate)) return candidate;
  const fallbackCandidate = String(fallback || "").trim().toLowerCase();
  return PRODUCT_RESEARCH_AI_CATEGORY_SET.has(fallbackCandidate)
    ? fallbackCandidate
    : "";
}

/**
 * Validates the one-shot route used when AI Center asks for a brand-new
 * product research form. Project and category are routing context only: no
 * product identity, media, SKU or previous research fields are inferred.
 */
export function normalizeProductResearchFreshRoute({
  newValues = [],
  projectValues = [],
  categoryValues = [],
  activeProjectId = "",
} = {}) {
  const freshValues = Array.isArray(newValues) ? newValues : [];
  const requested = freshValues.length > 0;
  if (!requested) {
    return {
      requested: false,
      valid: false,
      projectId: "",
      productCategory: "",
      reason: "",
    };
  }
  const projects = Array.isArray(projectValues) ? projectValues : [];
  const categories = Array.isArray(categoryValues) ? categoryValues : [];
  const projectId = projects.length === 1
    ? String(projects[0] || "").trim().toLowerCase()
    : "";
  const selectedProjectId = String(activeProjectId || "").trim().toLowerCase();
  const productCategory = categories.length === 1
    ? normalizeProductResearchAiCategory(categories[0])
    : "";
  const intentValid = freshValues.length === 1
    && String(freshValues[0] || "").trim() === "1";
  const projectValid = RESEARCH_UUID_PATTERN.test(projectId)
    && RESEARCH_UUID_PATTERN.test(selectedProjectId)
    && projectId === selectedProjectId;
  const categoryValid = Boolean(productCategory);
  const reason = !intentValid
    ? "fresh_intent_invalid"
    : !projectValid
      ? "project_context_invalid"
      : !categoryValid
        ? "product_category_invalid"
        : "";
  return {
    requested: true,
    valid: !reason,
    projectId: projectValid ? projectId : "",
    productCategory: categoryValid ? productCategory : "",
    reason,
  };
}

const PRODUCT_RESEARCH_SOURCE_MEDIA_KINDS = new Set([
  "product_photo",
  "packshot",
]);
const PRODUCT_RESEARCH_SOURCE_MEDIA_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

function productResearchMediaCanonicalRank(item, id) {
  const createdAt = String(item.created_at || item.createdAt || "").trim();
  return `${createdAt || "9999-12-31T23:59:59.999Z"}:${id}`;
}

function productResearchMediaDuplicateCount(value, fallback = 1) {
  const count = Number(value);
  return Number.isFinite(count) && count > 0
    ? Math.floor(count)
    : Math.max(1, Number(fallback) || 1);
}

export function normalizeProductResearchMediaSources(media = []) {
  const sourcesByContent = new Map();
  for (const candidate of Array.isArray(media) ? media : []) {
    const source = objectValue(candidate);
    if (!source) continue;
    const sourceId = String(source.id || source.media_id || "").trim();
    const id = String(
      source.canonical_id || source.canonicalId || sourceId,
    ).trim();
    const kind = String(source.kind || "").trim().toLowerCase();
    const status = String(source.status || "").trim().toLowerCase();
    const mimeType = String(source.mime_type || source.mimeType || "").trim().toLowerCase();
    const artifactClass = String(
      source.artifact_class || source.artifactClass || "",
    ).trim().toLowerCase();
    if (
      !id
      || status !== "ready"
      || !PRODUCT_RESEARCH_SOURCE_MEDIA_KINDS.has(kind)
      || !PRODUCT_RESEARCH_SOURCE_MEDIA_MIME_TYPES.has(mimeType)
      || (artifactClass && artifactClass !== "source")
    ) continue;

    const contentHash = String(
      source.sha256 || source.content_hash || source.contentHash || "",
    ).trim().toLowerCase();
    const contentKey = contentHash ? `hash:${contentHash}` : `media:${id}`;
    const duplicateMediaIds = [...new Set([
      ...(Array.isArray(source.duplicate_media_ids) ? source.duplicate_media_ids : []),
      ...(Array.isArray(source.duplicateMediaIds) ? source.duplicateMediaIds : []),
      sourceId,
      id,
    ].map(String).filter(Boolean))];
    const duplicateCount = Math.max(
      1,
      duplicateMediaIds.length,
      productResearchMediaDuplicateCount(
        source.duplicate_count || source.duplicateCount,
      ),
    );
    const normalized = {
      ...source,
      id,
      canonical_id: id,
      kind,
      status,
      mime_type: mimeType,
      artifact_class: artifactClass || "source",
      duplicate_count: duplicateCount,
      duplicate_media_ids: duplicateMediaIds,
    };
    const current = sourcesByContent.get(contentKey);
    if (!current) {
      sourcesByContent.set(contentKey, normalized);
      continue;
    }

    const duplicateIds = [...new Set([
      ...(current.duplicate_media_ids || []),
      ...(Array.isArray(source.duplicate_media_ids) ? source.duplicate_media_ids : []),
      id,
    ].map(String).filter(Boolean))];
    const totalDuplicateCount = productResearchMediaDuplicateCount(
      current.duplicate_count,
    ) + duplicateCount;
    const replaceCanonical = productResearchMediaCanonicalRank(normalized, id)
      < productResearchMediaCanonicalRank(current, current.id);
    const canonical = replaceCanonical ? normalized : current;
    sourcesByContent.set(contentKey, {
      ...canonical,
      canonical_id: canonical.id,
      duplicate_count: totalDuplicateCount,
      duplicate_media_ids: duplicateIds,
    });
  }
  return [...sourcesByContent.values()].sort((left, right) => (
    productResearchMediaCanonicalRank(left, left.id)
      .localeCompare(productResearchMediaCanonicalRank(right, right.id))
  ));
}

export function productResearchInputMarkup({
  media = [],
  mediaLoading = false,
  error = "",
  notice = "",
  defaults = {},
  paidTariff = null,
  exactPaidAuthorizationRequired = false,
} = {}) {
  const initial = objectValue(defaults) || {};
  const selectedMediaIds = new Set(stringArray(initial.sourceMediaIds).slice(0, 5));
  const selectedPlatforms = new Set(stringArray(initial.platforms).slice(0, 8));
  const objective = ["conversion", "awareness", "ugc", "education"].includes(
    String(initial.objective || "").trim(),
  ) ? String(initial.objective).trim() : "conversion";
  const selectedAiCategory = normalizeProductResearchAiCategory(
    initial.productCategory || initial.product_category,
  );
  const aiCategoryOptions = PRODUCT_RESEARCH_AI_CATEGORIES.map((category) => (
    `<option value="${category.value}" ${selectedAiCategory === category.value ? "selected" : ""}>${escapeHtml(category.label)}</option>`
  )).join("");
  const previousResearchId = String(initial.previousResearchId || "").trim();
  const researchMedia = normalizeProductResearchMediaSources(media);
  const mediaMarkup = researchMedia.length
    ? `<div class="product-research-media-grid">${researchMedia.map((item) => researchMediaMarkup(item, selectedMediaIds)).join("")}</div>`
    : `<div class="product-research-media-empty">
        <span aria-hidden="true">▧</span>
        <div><strong>${mediaLoading ? "Загружаем исходники…" : "Нет подходящих фото-исходников"}</strong><p>${mediaLoading ? "Подождите несколько секунд." : "Добавьте готовые к использованию product photo или packshot. Сгенерированные результаты сюда не попадают."}</p></div>
        ${mediaLoading ? "" : `<a class="btn btn-secondary btn-small" href="#/workspace/media">Открыть материалы</a>`}
      </div>`;
  const tariff = objectValue(paidTariff);
  const tariffKeys = [
    "version",
    "provider",
    "provider_key",
    "adapter_version",
    "model",
    "currency",
    "billing_mode",
    "service_tier",
    "input_usd_per_million_tokens",
    "output_usd_per_million_tokens",
    "long_context_threshold_input_tokens",
    "long_context_input_usd_per_million_tokens",
    "long_context_output_usd_per_million_tokens",
    "web_search_usd_per_call",
    "max_output_tokens",
    "max_provider_attempts",
    "fixed_total",
    "confirmation_value",
  ];
  const tariffTextKeys = [
    "version",
    "provider",
    "provider_key",
    "adapter_version",
    "model",
    "currency",
    "service_tier",
    "input_usd_per_million_tokens",
    "output_usd_per_million_tokens",
    "long_context_input_usd_per_million_tokens",
    "long_context_output_usd_per_million_tokens",
    "web_search_usd_per_call",
    "confirmation_value",
  ];
  const exactTariffAvailable = Boolean(
    tariff
      && Object.keys(tariff).length === tariffKeys.length
      && tariffKeys.every((key) => Object.hasOwn(tariff, key))
      && tariff.billing_mode === "metered_actual_usage"
      && tariff.service_tier === "default"
      && tariff.fixed_total === false
      && tariff.version === "openai-api-2026-08-13-gpt-5.5-standard-context-v3"
      && tariff.provider === "openai"
      && tariff.provider_key === "openai_web_search"
      && tariff.adapter_version === "openai-responses-web-search-v1"
      && tariff.model === "gpt-5.5"
      && tariff.currency === "USD"
      && tariff.input_usd_per_million_tokens === "5.00"
      && tariff.output_usd_per_million_tokens === "30.00"
      && tariff.long_context_threshold_input_tokens === 272_000
      && tariff.long_context_input_usd_per_million_tokens === "10.00"
      && tariff.long_context_output_usd_per_million_tokens === "45.00"
      && tariff.web_search_usd_per_call === "0.01"
      && tariff.confirmation_value
        === "OPENAI_GPT_5_5_WEB_RESEARCH_20260813_DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000"
      && tariffTextKeys.every((key) => (
        typeof tariff[key] === "string"
        && tariff[key].trim()
        && tariff[key].length <= 512
      ))
      && Number.isSafeInteger(tariff.max_output_tokens)
      && tariff.max_output_tokens === 18_000
      && tariff.max_provider_attempts === 1,
  );
  const paidAuthorizationMarkup = exactTariffAvailable
    ? `<div class="alert alert-warning" role="note"><strong aria-hidden="true">$</strong><span><strong>Это платный анализ по фактическому расходу.</strong> Модель ${escapeHtml(tariff.model)}, стандартный режим ${escapeHtml(tariff.service_tier)}: при входе до ${escapeHtml(tariff.long_context_threshold_input_tokens)} токенов включительно — вход $${escapeHtml(tariff.input_usd_per_million_tokens)} и выход $${escapeHtml(tariff.output_usd_per_million_tokens)} за 1 млн токенов; если вход превысит ${escapeHtml(tariff.long_context_threshold_input_tokens)}, повышенный тариф применяется ко всему запросу — вход $${escapeHtml(tariff.long_context_input_usd_per_million_tokens)} и выход $${escapeHtml(tariff.long_context_output_usd_per_million_tokens)} за 1 млн токенов; веб-поиск $${escapeHtml(tariff.web_search_usd_per_call)} за вызов. Максимум выходных токенов: ${escapeHtml(tariff.max_output_tokens)}; попытка провайдера только одна. Итоговая сумма заранее не фиксирована и зависит от фактического расхода и от того, пересечён ли порог long context.</span></div>
        <label class="check-row"><input type="checkbox" name="paid_analysis_confirmation" value="${escapeHtml(tariff.confirmation_value)}" required /><span><strong>Подтверждаю этот точный тариф и один платный запуск</strong><br /><small>Версия тарифа: ${escapeHtml(tariff.version)}. Подтверждение действует только для этого нажатия и не сохраняется на будущие запуски.</small></span></label>`
    : `<div class="alert alert-warning" role="alert"><strong aria-hidden="true">!</strong><span><strong>Точный тариф сейчас недоступен.</strong> Платный анализ заблокирован до получения свежего серверного тарифа. Обновите раздел и подтвердите его вручную.</span></div>`;
  let markup = `
    ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
    ${notice ? `<div class="alert alert-info" role="status"><strong aria-hidden="true">i</strong><span>${escapeHtml(notice)}</span>${previousResearchId ? `<button class="btn btn-ghost btn-small" type="button" data-action="restore-previous-product-research" data-research-id="${escapeHtml(previousResearchId)}">Открыть прежний снимок</button>` : ""}</div>` : ""}
    <section class="product-research-start-grid" aria-labelledby="product-research-form-title">
      <form id="product-research-start-form" class="card card-pad form-stack" novalidate>
        <div class="product-research-card-heading">
          <span class="product-research-step" aria-hidden="true">01</span>
          <div><p class="eyebrow">Исходные данные</p><h2 id="product-research-form-title">Что именно разбираем</h2><p>Заполните то, что знаете. Не придумывайте свойства товара — неизвестное найдёт анализ или отметит как гипотезу.</p></div>
        </div>
        <div class="form-grid-2">
          <label class="field"><span>Название товара *</span><input name="product_name" value="${escapeHtml(initial.productName || "")}" required maxlength="180" autocomplete="off" placeholder="Например: сывороточный протеин Bombbar" /></label>
          <label class="field"><span>Артикул / SKU *</span><input name="sku" value="${escapeHtml(initial.sku || "")}" required maxlength="120" autocomplete="off" placeholder="Например: 159068498" /></label>
        </div>
        <div class="form-grid-2">
          <label class="field"><span>Категория для ИИ-центра *</span><select name="product_category" required aria-describedby="product-research-ai-category-hint"><option value="">Выберите одну категорию</option>${aiCategoryOptions}</select><small id="product-research-ai-category-hint" class="field-hint">После анализа результат попадёт только во входящие этой категории. ИИ не применит его без проверки человеком.</small></label>
          <label class="field"><span>Точная подкатегория (необязательно)</span><input name="category_name" value="${escapeHtml(initial.categoryName || "")}" maxlength="160" autocomplete="off" placeholder="Например: несмываемый уход для волос" /><small class="field-hint">Это пояснение для анализа, а не скрытый выбор категории ИИ.</small></label>
        </div>
        <label class="field"><span>Что особенно важно исследовать</span><input name="research_focus" value="${escapeHtml(initial.researchFocus || "")}" maxlength="200" autocomplete="off" placeholder="Например: хуки конкурентов, возражения, сезонный спрос" /><small class="field-hint">Необязательно. Система всё равно проверит рынок, конкурентов, тренды и пробелы в данных.</small></label>
        <label class="field"><span>Ссылка на карточку товара</span><input name="marketplace_url" type="url" inputmode="url" value="${escapeHtml(initial.marketplaceUrl || "")}" placeholder="https://www.wildberries.ru/catalog/…" /><small class="field-hint">Только публичная HTTPS-ссылка. Пароли и ссылки из личного кабинета сюда не вставляйте.</small></label>
        <label class="field"><span>Известные конкуренты или ориентиры</span><textarea name="competitor_references" maxlength="650" placeholder="По одному названию, публичной ссылке или @аккаунту на строку. Если список пуст, ИИ сам найдёт сопоставимые предложения и честно оценит полноту выборки.">${escapeHtml(initial.competitorReferences || "")}</textarea><small class="field-hint">Это ориентиры для поиска, а не разрешение копировать чужие тексты, лица, музыку или последовательность кадров.</small></label>
        <fieldset class="product-research-platforms">
          <legend>Для каких площадок готовим контент *</legend>
          <label><input type="checkbox" name="platforms" value="instagram" ${selectedPlatforms.has("instagram") ? "checked" : ""} /> <span>Instagram Reels</span></label>
          <label><input type="checkbox" name="platforms" value="youtube" ${selectedPlatforms.has("youtube") ? "checked" : ""} /> <span>YouTube Shorts</span></label>
          <label><input type="checkbox" name="platforms" value="vk" ${selectedPlatforms.has("vk") ? "checked" : ""} /> <span>VK Клипы</span></label>
          <label><input type="checkbox" name="platforms" value="wildberries" ${selectedPlatforms.has("wildberries") ? "checked" : ""} /> <span>Wildberries</span></label>
          <label><input type="checkbox" name="platforms" value="ozon" ${selectedPlatforms.has("ozon") ? "checked" : ""} /> <span>Ozon</span></label>
        </fieldset>
        <label class="field"><span>Главная цель</span><select name="objective"><option value="conversion" ${objective === "conversion" ? "selected" : ""}>Заказы и переходы</option><option value="awareness" ${objective === "awareness" ? "selected" : ""}>Узнаваемость товара</option><option value="ugc" ${objective === "ugc" ? "selected" : ""}>Нативный UGC-обзор</option><option value="education" ${objective === "education" ? "selected" : ""}>Объяснить применение</option></select></label>
        <label class="field"><span>Подтверждённые вводные</span><textarea name="known_facts" maxlength="500" placeholder="Состав, объём, комплектация, способ применения — только то, что подтверждено упаковкой или документами.">${escapeHtml(initial.knownFacts || "")}</textarea><small class="field-hint">Каждый факт будет отделён от найденных источников и гипотез ИИ.</small></label>
        <div class="product-research-media-field">
          <div><strong>Фото-исходники из «Материалов»</strong><small>Только готовые product photo и packshot. Сгенерированный контент скрыт; одинаковые файлы объединены. Выберите 3–5 точных кадров.</small></div>
          ${mediaMarkup}
        </div>
        <div class="alert alert-warning" role="note"><strong aria-hidden="true">₽</strong><span><strong>Это платный ИИ-анализ.</strong> Используется поиск в интернете и модель анализа; итоговая стоимость определяется подключённым тарифом сервиса.</span></div>
        <label class="check-row"><input type="checkbox" name="paid_analysis_ack" required /><span><strong>Запускаю платный ИИ-анализ с поиском в интернете</strong><br /><small>Повторный клик с теми же вводными не создаст второй запуск.</small></span></label>
        <label class="check-row"><input type="checkbox" name="human_review_ack" required /><span><strong>Я проверю итог перед созданием задач</strong><br /><small>ИИ готовит черновик, но не принимает за человека факты, обещания и юридические решения.</small></span></label>
        <button class="btn btn-block" type="submit" data-primary-action="true">Запустить платный анализ и собрать 3 сценария <span aria-hidden="true">→</span></button>
      </form>
      <aside class="card card-pad product-research-explainer" aria-label="Что получится после анализа">
        <p class="eyebrow">На выходе</p>
        <h2>Не «магия», а проверяемый рабочий черновик</h2>
        <ol>
          <li><span>1</span><div><strong>Источники и факты</strong><p>У каждой находки будет ссылка и пометка, откуда она взялась.</p></div></li>
          <li><span>2</span><div><strong>ТЗ и три сценария</strong><p>Хуки, композиции фото, реплики и кадры видео, доказательства и стоп-формулировки можно исправить.</p></div></li>
          <li><span>3</span><div><strong>Оценка потенциала</strong><p>Сильные стороны и риски — без обещания «вирусности».</p></div></li>
          <li><span>4</span><div><strong>Задачи одним нажатием</strong><p>Только после вашего финального подтверждения.</p></div></li>
          <li><span>5</span><div><strong>Входящие ИИ-центра</strong><p>Готовое исследование появится в выбранной категории для разбора. Само по себе оно не меняет правила ИИ.</p></div></li>
        </ol>
        <div class="product-research-privacy"><strong>Что анализ не делает</strong><p>Не входит в чужие кабинеты, не обходит защиту площадок и не считает неподтверждённое свойство фактом.</p></div>
      </aside>
    </section>`;
  if (!exactPaidAuthorizationRequired) return markup;
  const legacyConfirmationMarker = 'name="paid_analysis_ack"';
  const legacyConfirmationIndex = markup.indexOf(legacyConfirmationMarker);
  const legacyPriceStart = markup.lastIndexOf(
    '<div class="alert alert-warning" role="note">',
    legacyConfirmationIndex,
  );
  const legacyConfirmationEnd = markup.indexOf("</label>", legacyConfirmationIndex);
  if (
    legacyPriceStart < 0
    || legacyConfirmationIndex < 0
    || legacyConfirmationEnd < 0
  ) return markup;
  markup = `${markup.slice(0, legacyPriceStart)}${paidAuthorizationMarkup}${markup.slice(
    legacyConfirmationEnd + "</label>".length,
  )}`;
  if (!exactTariffAvailable) {
    markup = markup.replace(
      'type="submit" data-primary-action="true"',
      'type="submit" data-primary-action="true" disabled aria-disabled="true"',
    );
  }
  return markup;
}

export function invalidateProductResearchPaidConfirmation(
  form,
  changedFieldName = "",
) {
  const confirmation = form?.elements?.paid_analysis_confirmation;
  if (
    !confirmation
    || String(changedFieldName || "") === "paid_analysis_confirmation"
  ) return false;
  confirmation.checked = false;
  return true;
}

export function productResearchProgressMarkup(record, error = "") {
  const failed = productResearchStatusKind(record?.status) === "failed";
  const providerAttemptExists = Boolean(
    record?.providerControl?.runControl?.attempt,
  );
  const waitingForProviderSlot = String(record?.status || "").trim().toLowerCase() === "queued"
    && !providerAttemptExists;
  const providerResponseBound =
    record?.providerControl?.responseState?.bindingState === "bound";
  const failureCode = String(record?.failureCode || "").trim().toLowerCase();
  const providerOutcomeUnknown = failed
    && (
      failureCode === "provider_outcome_unknown"
      || (failureCode === "processing_lease_expired" && providerAttemptExists)
    );
  const paidProviderResultFailed = failed
    && providerResponseBound
    && !providerOutcomeUnknown;
  const providerStatus = String(
    record?.providerControl?.responseState?.providerStatus || "",
  ).trim().toLowerCase();
  const terminalDiagnosticStatus = String(
    record?.providerControl?.responseState?.terminalDiagnostic?.terminalStatus
      || "",
  ).trim().toLowerCase();
  const responseValidationFailed = paidProviderResultFailed
    && failureCode === "provider_response_invalid"
    && providerStatus === "completed"
    && !["failed", "cancelled", "incomplete"].includes(
      terminalDiagnosticStatus,
    );
  const exactVideo = record?.exactVideo?.verified === true
    ? record.exactVideo
    : null;
  const exactVideoProviderFailure = paidProviderResultFailed
    && exactVideo !== null;
  const exactProductName = String(record?.productName || "")
    .replace(/\s+/gu, " ").trim().slice(0, 180);
  const exactProductSku = String(record?.sku || "")
    .replace(/\s+/gu, " ").trim().slice(0, 120);
  const exactVideoAttributes = exactVideo
    ? ` data-research-exact-video-evidence="verified" data-exact-video-marker-source="${escapeHtml(exactVideo.markerSource)}" data-exact-video-source-id="${escapeHtml(exactVideo.sourceId)}" data-exact-video-attachment-id="${escapeHtml(exactVideo.attachmentId)}" data-exact-video-media-id="${escapeHtml(exactVideo.mediaId)}" data-exact-video-evidence-id="${escapeHtml(exactVideo.evidenceId)}" data-exact-video-frame-count="${exactVideo.frameCount}" data-exact-video-analysis-scope="${escapeHtml(exactVideo.analysisScope)}" data-exact-video-product-name="${escapeHtml(exactProductName)}" data-exact-video-product-sku="${escapeHtml(exactProductSku)}"`
    : "";
  const providerTerminalStatus = ["failed", "cancelled", "incomplete"]
      .includes(terminalDiagnosticStatus)
    ? terminalDiagnosticStatus
    : providerStatus;
  const providerTerminalAttribute = ["failed", "cancelled", "incomplete"]
    .includes(providerTerminalStatus)
    ? ` data-provider-terminal-status="${escapeHtml(providerTerminalStatus)}"`
    : "";
  const failureMessage = providerOutcomeUnknown
    ? "Платный запрос мог быть принят провайдером, но итог не удалось подтвердить в доступное время. Портал не повторяет такой запрос автоматически. Скопируйте ID запуска для поддержки; новый платный анализ запускайте только отдельным осознанным действием."
    : responseValidationFailed
      ? `${record?.failureMessage || "Ответ провайдера получен, но локальная проверка не приняла его структуру или источники."} Можно повторно проверить тот же сохранённый response_id без нового платного запроса.`
    : exactVideoProviderFailure
      ? `${record?.failureMessage || "Провайдер принял запрос с пятью проверенными sampled-кадрами, но завершил его без пригодного результата."} Отсутствие подтверждённых цитат не означает, что кадры не передавались.`
    : paidProviderResultFailed
      ? `${record?.failureMessage || "Провайдер завершил платный запуск, но пригодный результат не сохранён."} Повторный анализ будет отдельным новым платным запросом.`
    : record?.failureMessage;
  const progress = `
    <section class="card card-pad product-research-progress"${exactVideoAttributes}${providerTerminalAttribute} ${failed || error ? 'role="alert"' : 'role="status"'} aria-live="polite">
      <div class="product-research-orbit" aria-hidden="true"><span></span><b>A</b></div>
      <p class="eyebrow">${providerOutcomeUnknown ? "Оплата требует сверки" : responseValidationFailed ? "Платный ответ сохранён" : paidProviderResultFailed ? "Платный запуск завершён" : failed || error ? "Нужна проверка" : waitingForProviderSlot ? "Анализ в очереди" : "Исследование запущено"}</p>
      <h2>${failed
        ? providerOutcomeUnknown
          ? "Ответ провайдера пока не подтверждён"
          : responseValidationFailed
            ? "Ответ получен — нужна повторная проверка"
          : exactVideoProviderFailure
            ? "Пять кадров переданы, но провайдер завершил запрос с ошибкой"
          : paidProviderResultFailed
            ? "Результат нельзя использовать"
          : "Анализ не завершился"
        : error
          ? "Не удалось подтвердить текущий статус"
          : waitingForProviderSlot
            ? "Ожидает свободного места у провайдера"
          : `Собираем доказательства для «${escapeHtml(record?.productName || "товара") }»`}</h2>
      <p>${escapeHtml(error || failureMessage || (waitingForProviderSlot
        ? "Запуск сохранён и начнётся автоматически. Повторно нажимать ничего не нужно — нового запроса и списания портал не создаст."
        : "Проверяем карточку, доступные публичные источники, формулировки покупателей и будущие сценарии. Страницу можно оставить открытой — статус обновляется автоматически."))}</p>
      ${!failed && record?.statusNotice ? `<div class="alert alert-warning" role="status"><strong>Запуск сохранён.</strong><span>${escapeHtml(record.statusNotice)}</span></div>` : ""}
      ${providerOutcomeUnknown
        ? `<div class="inline-actions"><button class="btn" type="button" data-primary-action="true" data-action="copy-product-research-support-id" data-research-id="${escapeHtml(record?.id || "")}">Скопировать ID для поддержки</button><button class="btn btn-ghost" type="button" data-action="new-product-research">Подготовить отдельный новый анализ</button></div><small class="product-research-paid-retry-warning">Это будет новая подтверждаемая оплата; старый запрос мог быть принят. Автоматического повтора нет: перед запуском снова откроется форма с обязательными подтверждениями.</small>`
        : responseValidationFailed
          ? `<div class="inline-actions"><button class="btn" type="button" data-primary-action="true" data-action="revalidate-product-research-response">Повторно проверить ответ — без оплаты</button><button class="btn btn-ghost" type="button" data-action="new-product-research">Подготовить отдельный новый анализ</button></div><small class="product-research-paid-retry-warning">Повторная проверка читает только уже привязанный response_id и не отправляет новый POST провайдеру. Если срок хранения ответа истёк, портал остановится и сообщит об этом до нового платного действия.</small>`
        : paidProviderResultFailed
          ? `<div class="inline-actions"><button class="btn" type="button" data-primary-action="true" data-action="new-product-research">Подготовить новый платный анализ</button><button class="btn btn-ghost" type="button" data-action="refresh-product-research">Проверить сохранённый статус</button></div><small class="product-research-paid-retry-warning">${exactVideoProviderFailure ? "Пять кадров предыдущего запуска уже были проверены и отправлены, а одноразовый evidence-набор потреблён. Для нового запуска портал должен создать новый набор из 5 кадров; затем вы отдельно подтвердите обработку ИИ и новую оплату. Автоматического POST нет." : "Предыдущий платный запуск уже был принят провайдером. Новый анализ создаст отдельный запрос и потребует нового подтверждения оплаты."}</small>`
        : failed
        ? `<div class="inline-actions"><button class="btn btn-secondary" type="button" data-action="refresh-product-research">Проверить статус</button><button class="btn btn-ghost" type="button" data-action="new-product-research">Начать заново</button></div>`
        : error
          ? `<div class="inline-actions"><button class="btn btn-secondary" type="button" data-action="refresh-product-research">Проверить статус активного запуска</button></div>`
          : `<div class="product-research-progress-steps" aria-hidden="true"><span class="done">Вводные</span><span class="active">Источники</span><span>ТЗ</span><span>Прогноз</span></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-product-research">Проверить сейчас</button>`}
    </section>`;
  return `${progress}${record?.providerControl
    ? researchProviderControlMarkup(record.providerControl, { compact: true })
    : ""}`;
}

function researchStageLabel(stage) {
  return {
    sources: "Источники",
    category: "Категория",
    competitors: "Конкуренты",
    trends: "Тренды",
    guidance: "Рекомендация ИИ",
    brief: "ТЗ",
    scenarios: "Сценарии",
  }[String(stage || "")] || "Этап";
}

function researchStageStateLabel(state) {
  return {
    current: "актуален",
    stale_dependency: "зависимости устарели",
    rejected: "отклонён",
    recompute_queued: "пересчёт сохранён",
    recompute_processing: "пересчитывается",
    recompute_failed: "пересчёт не завершён",
  }[String(state || "")] || "нужна проверка";
}

function researchStageControlStatusLabel(status) {
  return {
    approved_snapshot_mismatch: "утверждённый снимок не совпадает",
    approved_locked: "утверждено и заблокировано",
    recompute_pending: "пересчёт сохранён",
    missing_stage_heads: "не хватает этапов",
    rejected_stage: "есть отклонённый этап",
    stale_dependencies: "есть устаревшие зависимости",
    stage_snapshot_mismatch: "снимок этапов не совпадает",
    current_draft_not_editable: "черновик нельзя менять",
    ai_revision_needs_human_snapshot: "нужна проверка человеком",
    ready_for_review: "готово к проверке",
    branch_comparison: "ветка сравнения · только чтение",
  }[String(status || "")] || "нужна проверка";
}

function researchStageNextStepLabel(value) {
  return {
    check_saved_recompute_without_retry:
      "Проверьте сохранённый пересчёт. Новый платный запуск автоматически не создаётся.",
    invoke_saved_recompute_or_cancel:
      "Пересчёт сохранён до обращения к провайдеру. Возобновите этот же запуск либо отмените его; новый платный запрос не создавайте.",
    cancel_expired_recompute_without_retry:
      "Серверная блокировка истекла. Отмените сохранённый пересчёт без повторной попытки провайдера.",
    wait_for_active_provider_lease_without_retry:
      "Единственная попытка провайдера ещё защищена серверной блокировкой. Ждите и проверяйте статус — не запускайте повтор.",
    discard_superseded_recompute_without_retry:
      "Ветка изменилась после подготовки пересчёта. Завершите сохранённый запрос как superseded без нового spend, provider-вызова или retry.",
    restore_missing_stage_lineage:
      "Восстановите отсутствующую версию этапа до дальнейшей работы.",
    restore_exact_stage_snapshot:
      "Восстановите точную привязку всех семи этапов к одному текущему черновику.",
    patch_or_revert_rejected_stage:
      "Исправьте или верните предыдущую версию отклонённого этапа.",
    patch_or_recompute_earliest_stale_stage:
      "Начните с самого раннего устаревшего этапа: исправьте его вручную или подтвердите пересчёт.",
    review_and_approve_current_draft:
      "Все семь этапов согласованы. Проверьте текущий черновик перед утверждением.",
    start_new_research_and_preserve_approved_snapshot:
      "Утверждённый main-снимок остаётся неизменным. Для новой управляемой версии начните отдельное исследование.",
    fork_read_only_snapshot_or_start_new_research:
      "Создайте ветку только для сравнения снимка или начните отдельное исследование для управляемых изменений. Переноса в main нет.",
    start_new_research_or_fork_read_only_snapshot:
      "Для управляемых изменений начните отдельное исследование; ветку создавайте только как снимок для чтения и сравнения.",
    save_human_review_snapshot:
      "ИИ подготовил новую версию. Проверьте данные и сохраните структурную версию этапа — так появится точный человеческий review-снимок.",
    compare_read_only_branch_with_main:
      "Это ветка сравнения только для чтения. Сопоставьте её с main; переноса или автоматической замены результата нет.",
  }[String(value || "")] || String(value || "Проверьте состояние этапов.");
}

function researchStageShortId(value) {
  const normalized = String(value || "");
  return normalized ? `${normalized.slice(0, 8)}…` : "—";
}

function researchStageCancelReasonLabel(value) {
  return {
    saved_before_provider_claim:
      "Пересчёт сохранён, но попытка провайдера ещё не началась.",
    processing_lease_expired:
      "Серверная блокировка обработки истекла; повтор провайдера запрещён.",
    provider_attempt_lease_active:
      "Попытка провайдера защищена активной серверной блокировкой.",
    branch_changed_after_prepare:
      "Ветка изменилась после подготовки. Пересчёт можно немедленно завершить как superseded без нового spend или retry.",
  }[String(value || "")] || String(value || "");
}

function researchStageRecomputeHeading(active) {
  if (active?.cancelReason === "branch_changed_after_prepare") {
    return "ветка изменилась — запрос нужно завершить как superseded";
  }
  if (active?.status === "queued") return "ждёт запуска или проверки";
  if (active?.canCancel) {
    return "блокировка истекла — доступна безопасная отмена";
  }
  return "анализ выполняется";
}

function researchStageRevertCandidates(control, head) {
  const seen = new Set([head.artifactId]);
  const candidates = [];
  control.history.forEach((event) => {
    if (event.stage !== head.stage) return;
    [event.artifactId, event.priorArtifactId].forEach((artifactId) => {
      if (!artifactId || seen.has(artifactId)) return;
      seen.add(artifactId);
      candidates.push(artifactId);
    });
  });
  return candidates;
}

function researchStageHeadMarkup(control, head, { saving = false } = {}) {
  const allowed = new Set(head.allowedActions);
  const isComparisonBranch = control.selectedBranch.branchKey !== "main";
  const canPatch = !isComparisonBranch && allowed.has("patch");
  const canReject = !isComparisonBranch && allowed.has("reject");
  const canFork = !isComparisonBranch && allowed.has("fork");
  const canRecompute = allowed.has("recompute")
    && !isComparisonBranch
    && !control.activeRecompute;
  const revertCandidates = !isComparisonBranch && allowed.has("revert")
    ? researchStageRevertCandidates(control, head)
    : [];
  const earliest = control.guidance?.earliestProblemStage === head.stage
    || (
      control.guidance?.recommendedNextAction === "save_human_review_snapshot"
      && head.stage === RESEARCH_STAGE_ORDER[0]
    );
  const payloadJson = JSON.stringify(head.payload, null, 2);
  const actionButtons = [
    canPatch
      ? `<button class="btn btn-secondary btn-small" type="submit" data-stage-control-action="patch" ${saving ? "disabled" : ""}>Сохранить правку</button>`
      : "",
    canRecompute
      ? `<button class="btn btn-secondary btn-small" type="submit" data-stage-control-action="recompute" ${saving ? "disabled" : ""}>Пересчитать с новым поиском</button>`
      : "",
    canReject
      ? `<button class="btn btn-ghost btn-small" type="submit" data-stage-control-action="reject" ${saving ? "disabled" : ""}>Отклонить этап</button>`
      : "",
    revertCandidates.length
      ? `<button class="btn btn-ghost btn-small" type="submit" data-stage-control-action="revert" ${saving ? "disabled" : ""}>Вернуть версию</button>`
      : "",
    canFork
      ? `<button class="btn btn-ghost btn-small" type="submit" data-stage-control-action="fork" ${saving ? "disabled" : ""}>Создать ветку сравнения</button>`
      : "",
  ].filter(Boolean).join("");
  return `<details class="product-research-stage-head ${head.state === "current" ? "is-current" : "needs-attention"}" ${earliest ? "open" : ""}
      data-stage="${escapeHtml(head.stage)}"
      data-branch-id="${escapeHtml(control.selectedBranch.branchId)}"
      data-branch-revision-hash="${escapeHtml(control.selectedBranch.branchRevisionHash)}"
      data-head-event-id="${escapeHtml(head.headEventId)}"
      data-artifact-id="${escapeHtml(head.artifactId)}"
      data-content-hash="${escapeHtml(head.contentHash)}"
      data-artifact-version="${head.artifactVersion}">
    <summary>
      <span class="product-research-stage-index">${String(RESEARCH_STAGE_ORDER.indexOf(head.stage) + 1).padStart(2, "0")}</span>
      <span><strong>${escapeHtml(researchStageLabel(head.stage))}</strong><small>Версия ${head.artifactVersion} · ${head.evidenceCount} доказательств</small></span>
      <span class="badge">${escapeHtml(researchStageStateLabel(head.state))}</span>
    </summary>
    ${isComparisonBranch ? `<div class="product-research-stage-comparison form-stack" role="note">
      <div class="product-research-stage-snapshot">
        <span>Артефакт <code>${escapeHtml(researchStageShortId(head.artifactId))}</code></span>
        <span>Снимок <code>${escapeHtml(researchStageShortId(head.headEventId))}</code></span>
      </div>
      <p><strong>Ветка сравнения — только чтение.</strong> Её можно сопоставить с main, но нельзя править, пересчитывать, утверждать или переносить обратно.</p>
      <label class="field"><span>Структурная версия этапа</span><textarea rows="10" spellcheck="false" readonly>${escapeHtml(payloadJson)}</textarea></label>
    </div>` : `<form class="product-research-stage-control-form form-stack" novalidate>
      <div class="product-research-stage-snapshot" role="note">
        <span>Артефакт <code>${escapeHtml(researchStageShortId(head.artifactId))}</code></span>
        <span>Снимок <code>${escapeHtml(researchStageShortId(head.headEventId))}</code></span>
        ${head.staleDueToArtifactIds.length ? `<span>Затронуто зависимостей: ${head.staleDueToArtifactIds.length}</span>` : ""}
      </div>
      ${canPatch ? `<label class="field"><span>Структурная версия этапа</span><textarea name="replacement" rows="10" maxlength="524288" spellcheck="false">${escapeHtml(payloadJson)}</textarea><small class="field-hint">Сохраняется новая версия; прежняя остаётся в журнале. JSON должен оставаться объектом.</small></label>` : ""}
      ${canPatch || canRecompute ? `<label class="field"><span>Что именно изменить</span><textarea name="user_input" rows="3" maxlength="4000" placeholder="Опишите исправление для ИИ и журнала"></textarea></label>` : ""}
      <label class="field"><span>Причина решения</span><input name="reason" minlength="3" maxlength="500" placeholder="Почему версия требует этого действия" required /></label>
      ${revertCandidates.length ? `<label class="field"><span>Версия для отката</span><select name="target_artifact_id"><option value="">Выберите точный артефакт</option>${revertCandidates.map((artifactId) => `<option value="${escapeHtml(artifactId)}">${escapeHtml(researchStageShortId(artifactId))}</option>`).join("")}</select></label>` : ""}
      ${canFork ? `<label class="field"><span>Ключ ветки сравнения</span><input name="new_branch_key" maxlength="64" placeholder="comparison-angle" /></label>` : ""}
      ${canRecompute ? `<label class="check-row product-research-stage-paid"><input type="checkbox" name="paid_analysis_ack" /><span><strong>Подтверждаю один платный пересчёт</strong><br /><small>Сначала сервер сохранит точный запрос, затем браузер один раз вызовет анализ. Автоповтора нет.</small></span></label>` : ""}
      <label class="check-row"><input type="checkbox" name="confirmation" required /><span><strong>Применить к версии ${head.artifactVersion}</strong><br /><small>Если этап уже изменился, сервер отклонит команду и попросит обновить снимок.</small></span></label>
      <div class="product-research-stage-actions">${actionButtons || '<span class="muted">Для этой роли нет доступных действий.</span>'}</div>
    </form>`}
  </details>`;
}

export function researchStageControlMarkup(value, {
  loading = false,
  saving = false,
  error = "",
  notice = "",
} = {}) {
  if (loading && !value?.available) {
    return `<section class="card card-pad product-research-stage-control" aria-busy="true"><p class="eyebrow">Версии этапов</p><h2>Загружаем точный снимок…</h2><div class="loading-line" aria-hidden="true"><span></span></div></section>`;
  }
  const control = value?.available ? value : null;
  if (!control) {
    return `<section class="card card-pad product-research-stage-control">
      <p class="eyebrow">Версии этапов</p><h2>Контур исправлений пока недоступен</h2>
      ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
      <p>Основное исследование не менялось. Обновите только компактный статус этапов.</p>
      <button class="btn btn-secondary btn-small" type="button" data-action="refresh-research-stage-control">Проверить статус этапов</button>
    </section>`;
  }
  const guidance = control.guidance || {};
  const active = control.activeRecompute;
  const activeHead = active
    ? control.heads.find((head) => head.stage === active.stage)
    : null;
  const cancelAllowed = Boolean(
    active?.canCancel
      && activeHead?.allowedActions.includes("cancel")
      && control.selectedBranch.branchKey === "main",
  );
  const exactStageCount = Number(guidance.exactSnapshotStageCount) || 0;
  const humanSnapshot = guidance.currentDraftOrigin === "human";
  const exactSnapshot = exactStageCount === RESEARCH_STAGE_ORDER.length;
  const snapshotMarkup = `<div class="product-research-stage-review-gate ${humanSnapshot && exactSnapshot ? "is-ready" : "needs-attention"}" role="status">
    <div><p class="eyebrow">Шлюз ИИ → человек</p><h3>${humanSnapshot ? "Человеческий review-снимок сохранён" : "ИИ-версия ещё не стала человеческим решением"}</h3><p>${exactStageCount} из ${RESEARCH_STAGE_ORDER.length} этапов привязаны к текущему черновику${guidance.currentDraftId ? ` <code>${escapeHtml(researchStageShortId(guidance.currentDraftId))}</code>` : ""}. ${humanSnapshot && exactSnapshot ? "Точный снимок можно проверять для утверждения." : "Утверждение закрыто, пока человек не сохранит точный снимок всех этапов."}</p></div>
    <span class="badge">${escapeHtml(guidance.currentDraftOrigin || "нет снимка")} · ${escapeHtml(guidance.currentDraftStatus || "нет статуса")}</span>
  </div>`;
  const activeMarkup = active ? `<aside class="product-research-stage-recompute" role="status">
    <div><p class="eyebrow">Сохранённый пересчёт</p><h3>${escapeHtml(researchStageLabel(active.stage))}: ${escapeHtml(researchStageRecomputeHeading(active))}</h3><p>Запрос <code>${escapeHtml(researchStageShortId(active.requestId))}</code>${active.childRunId ? ` · дочерний запуск <code>${escapeHtml(researchStageShortId(active.childRunId))}</code>` : ""}. Попыток провайдера: ${active.providerAttemptCount} из ${active.maxProviderAttempts}.${active.leaseExpiresAt ? ` Серверная блокировка обработки до <code>${escapeHtml(active.leaseExpiresAt)}</code>.` : ""}</p>${active.cancelReason ? `<small>${escapeHtml(researchStageCancelReasonLabel(active.cancelReason))}</small>` : ""}</div>
    <div class="inline-actions">
      <button class="btn btn-secondary btn-small" type="button" data-action="refresh-research-stage-control">Проверить сохранённый статус</button>
      ${active.status === "queued" && active.providerAttemptCount === 0 && active.childRunId && active.cancelReason !== "branch_changed_after_prepare" ? `<button class="btn btn-ghost btn-small" type="button" data-action="resume-research-stage-recompute" data-request-id="${escapeHtml(active.requestId)}" data-child-run-id="${escapeHtml(active.childRunId)}" ${saving ? "disabled" : ""}>Вручную возобновить сохранённый запуск</button>` : ""}
    </div>
    ${cancelAllowed ? `<form class="product-research-stage-cancel-form form-stack" data-request-id="${escapeHtml(active.requestId)}" novalidate>
      <label class="field"><span>Причина отмены</span><input name="reason" minlength="3" maxlength="500" placeholder="Почему сохранённый пересчёт нужно закрыть" required /></label>
      <label class="check-row"><input type="checkbox" name="confirmation" required /><span><strong>${active.cancelReason === "branch_changed_after_prepare" ? "Завершить этот пересчёт как superseded" : "Отменить именно этот сохранённый пересчёт"}</strong><br /><small>Команда привязана к точному снимку всей main-ветки. Provider/Edge не вызывается, автоматического повтора нет.</small></span></label>
      <button class="btn btn-danger btn-small" type="submit" data-stage-control-action="cancel" ${saving ? "disabled" : ""}>${active.cancelReason === "branch_changed_after_prepare" ? "Завершить как superseded" : "Отменить сохранённый пересчёт"}</button>
    </form>` : ""}
    <small>${active.cancelReason === "branch_changed_after_prepare" ? "Ветка уже изменилась: завершение как superseded не вызывает Edge, не создаёт spend и не повторяет провайдера." : active.status === "queued" ? "Кнопка возобновления не создаёт новый запрос: Edge проверит сохранённый дочерний запуск и не допустит вторую попытку провайдера." : "Во время активной серверной блокировки доступна только проверка статуса. После её истечения сервер может открыть отмену без повторной попытки провайдера."}</small>
  </aside>` : "";
  const branchMarkup = control.branches.slice(0, 20).map((branch) => `
    <button class="btn ${branch.selected ? "btn-secondary" : "btn-ghost"} btn-small" type="button" data-action="select-research-stage-branch" data-branch-id="${escapeHtml(branch.branchId)}" ${branch.selected || saving ? "disabled" : ""}>
      ${escapeHtml(branch.branchKey)} · ${branch.branchKey === "main" ? "основная" : "ветка сравнения"}${branch.problemCount ? ` · ${branch.problemCount} проблем` : ""}
    </button>`).join("");
  const historyMarkup = control.history.slice(0, 8).map((event) => `
    <li><span class="badge">${escapeHtml(researchStageLabel(event.stage))}</span><div><strong>${escapeHtml(researchStageStateLabel(event.state))}</strong><p>${escapeHtml(event.reason || event.action)}</p></div><code>${escapeHtml(researchStageShortId(event.artifactId))}</code></li>`).join("");
  return `<section class="card product-research-stage-control" aria-labelledby="research-stage-control-title">
    <div class="card-header">
      <div><p class="eyebrow">Версионируемые этапы</p><h2 id="research-stage-control-title">Исправление с зависимостями и откатом</h2><p>Каждая команда привязана к точной версии. Изменённые зависимости блокируют устаревшие выводы до исправления или пересчёта.</p></div>
      <span class="badge">${escapeHtml(researchStageControlStatusLabel(guidance.status))}</span>
    </div>
    ${error ? `<div class="alert alert-danger product-research-stage-alert" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
    ${notice ? `<div class="alert alert-success product-research-stage-alert" role="status"><strong aria-hidden="true">✓</strong><span>${escapeHtml(notice)}</span></div>` : ""}
    <aside class="product-research-stage-guidance" role="status">
      <div><p class="eyebrow">Следующий шаг от сервера</p><h3>${escapeHtml(researchStageNextStepLabel(guidance.recommendedNextAction))}</h3>${guidance.earliestProblemStage ? `<p>Начать с этапа «${escapeHtml(researchStageLabel(guidance.earliestProblemStage))}».</p>` : ""}</div>
      <button class="btn btn-secondary btn-small" type="button" data-action="refresh-research-stage-control">Обновить снимок</button>
    </aside>
    ${snapshotMarkup}
    ${activeMarkup}
    <div class="product-research-stage-branches" aria-label="Ветки исследования">${branchMarkup}${control.branches.length > 20 ? '<span class="muted">Показаны первые 20 веток.</span>' : ""}</div>
    ${control.selectedBranch.branchKey !== "main" ? '<aside class="product-research-stage-comparison-note" role="note"><strong>Ветка сравнения — только чтение.</strong><span>Она не может быть утверждена, пересчитана или перенесена в main. Вернитесь в main для управляемых изменений.</span></aside>' : ""}
    <div class="product-research-stage-heads">${control.heads.map((head) => researchStageHeadMarkup(control, head, { saving })).join("") || '<p class="muted">Сервер не вернул этапы. Следуйте указанному выше шагу восстановления.</p>'}</div>
    ${historyMarkup ? `<details class="product-research-stage-history"><summary>Последние изменения (${Math.min(control.history.length, 8)}${control.historyHasMore ? "+" : ""})</summary><ol>${historyMarkup}</ol></details>` : ""}
  </section>`;
}

export function productResearchResultMarkup(record, {
  saving = false,
  approving = false,
  watchlistSaving = false,
  marketCategorySaving = false,
  outcomeLearningSaving = false,
  categoryLearningSaving = false,
  categoryLearningPolicyWritable = false,
  youtubeSavingPhase = "",
  notice = "",
  error = "",
  members = [],
  defaultAssigneeId = "",
  recommendedPrepared = false,
  stageControl = null,
  stageControlLoading = false,
  stageControlSaving = false,
  stageControlError = "",
  stageControlNotice = "",
  view = "evidence",
} = {}) {
  const researchView = ["evidence", "corrections", "brief", "approve", "handoff"].includes(view)
    ? view
    : "evidence";
  if (researchView === "corrections") {
    return `<div data-research-view="corrections">
      ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
      ${notice ? `<div class="alert alert-success" role="status"><strong aria-hidden="true">✓</strong><span>${escapeHtml(notice)}</span></div>` : ""}
      ${researchStageControlMarkup(stageControl, {
        loading: stageControlLoading,
        saving: stageControlSaving,
        error: stageControlError,
        notice: stageControlNotice,
      })}
    </div>`;
  }
  const brief = normalizeBrief(record?.brief);
  const scenarios = normalizeScenarios(record?.scenarios);
  const categoryAnalysis = normalizeCategoryAnalysis(record?.categoryAnalysis);
  const competitorAnalysis = normalizeCompetitorAnalysis(record?.competitorAnalysis);
  const trendAnalysis = normalizeTrendAnalysis(record?.trendAnalysis);
  const guidance = normalizeResearchGuidance(record?.guidance);
  const humanResearchDecision = normalizeHumanResearchDecision(
    record?.humanResearchDecision || brief.humanResearchDecision,
  );
  const stageCorrections = normalizeStageCorrections(
    record?.stageCorrections || brief.stageCorrections,
  );
  const confidence = confidenceCopy(record?.confidence);
  const score = clampScore(record?.score);
  const sourceMarkup = record?.sources?.length
    ? record.sources.map(sourceMarkupItem).join("")
    : `<div class="product-research-empty-note"><strong>Публичные источники не подтверждены</strong><p>Не переносите найденные ИИ формулировки в ролик как факт, пока не добавите доказательство.</p></div>`;
  const taskIds = stringArray(record?.taskIds);
  const approved = record?.approved === true || taskIds.length > 0;
  const generationHandoffAllowed = stageControl?.available === true
    && String(stageControl.runId || "").trim().toLowerCase()
      === String(record?.id || "").trim().toLowerCase()
    && String(stageControl.guidance?.currentDraftId || "").trim().toLowerCase()
      === String(record?.draftId || "").trim().toLowerCase()
    && stageControl.guidance?.generationHandoffAllowed === true;
  const generationHandoffBlocked = approved && !generationHandoffAllowed;
  const assignees = normalizeResearchMembers(members, defaultAssigneeId);
  const fallbackAssigneeId = String(defaultAssigneeId || assignees[0]?.profileId || "");
  const recommendedScenarioIndex = Number.isInteger(record?.recommendedScenarioIndex)
    && record.recommendedScenarioIndex >= 0
    && record.recommendedScenarioIndex < scenarios.length
    ? record.recommendedScenarioIndex
    : -1;
  const recommendedScenarioReason = String(
    record?.recommendedScenarioReason || "",
  ).trim();
  const guidanceNeedsOverride = guidance.status !== "ready_for_brief";
  const approvedActions = generationHandoffBlocked
    ? '<div class="inline-actions"><button class="btn" type="button" data-action="new-product-research" data-primary-action="true">Начать новое исследование →</button></div>'
    : recommendedScenarioIndex >= 0
    ? `<div class="inline-actions"><button class="btn" type="button" data-action="generate-research-scenario" data-scenario-index="${recommendedScenarioIndex}" data-primary-action="true">${recommendedPrepared ? "Перепроверить и открыть" : "Подготовить"} рекомендованный сценарий →</button></div>`
    : `<a class="btn" href="#/workspace/tasks" data-primary-action="true">Открыть задачи →</a>`;
  const categoryResetSnapshotIds = arrayValue(record?.marketRegistry?.trendTimeline)
    .filter((item) => ["canonical_reset", "category_reset"].includes(item?.comparisonMode))
    .map((item) => String(item?.snapshotId || ""))
    .filter(Boolean);
  const showOutcomeControl = !record?.outcomeScopeRegistry
    || Boolean(record.outcomeScopeRegistry.selectedScope);
  return `
    <div data-research-view="${researchView}">
    ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
    ${notice ? `<div class="alert alert-success" role="status"><strong aria-hidden="true">✓</strong><span>${escapeHtml(notice)}</span></div>` : ""}
    ${researchCategoryLearningMarkup(record?.categoryLearning, {
      saving: categoryLearningSaving,
      policyWritable: categoryLearningPolicyWritable,
    })}
    ${researchProviderControlMarkup(record?.providerControl)}
    ${researchMarketCategoryMarkup(record?.marketRegistry, {
      saving: marketCategorySaving,
      runId: record?.id || "",
    })}
    ${record?.youtubeResearch ? researchYoutubeMarkup(record.youtubeResearch, {
      saving: saving || approving,
      savingPhase: youtubeSavingPhase,
    }) : ""}
    ${generationHandoffBlocked ? '<div class="alert alert-warning" role="alert"><strong>Исследование устарело.</strong><span>Новый разбор источника запрещает передавать этот снимок в генерацию. Прежняя версия сохранена; начните отдельное исследование с предзаполненными исходными данными.</span></div>' : ""}
    ${approved ? `<section class="card card-pad product-research-approved" role="status"><span aria-hidden="true">✓</span><div><p class="eyebrow">ТЗ утверждено</p><h2>${taskIds.length ? `Задачи созданы: ${taskIds.length}` : "Задачи созданы"}</h2><p>${recommendedScenarioIndex >= 0 ? recommendedPrepared ? `Сценарий ${recommendedScenarioIndex + 1} уже подготовлен в генераторе как лучший первый безопасный эксперимент. Оплата и рендер не запускались.` : `Сценарий ${recommendedScenarioIndex + 1} рекомендован первым. Автоподготовка не заменила текущий рабочий контекст; при необходимости подготовьте его отдельной кнопкой.` : "Исполнители уже назначены. Повторное сохранение и утверждение заблокированы, чтобы ТЗ не разошлось с созданными задачами."}</p></div>${approvedActions}</section>` : ""}
    ${approved ? researchWatchlistMarkup(record?.watchlist, {
      saving: watchlistSaving,
      runId: record?.id || "",
      categoryResetSnapshotIds,
    }) : ""}
    ${record?.outcomeScopeRegistry ? researchOutcomeScopeRegistryMarkup(
      record.outcomeScopeRegistry,
      { saving: outcomeLearningSaving },
    ) : ""}
    ${showOutcomeControl && record?.outcomeLearning ? researchOutcomeLearningMarkup(
      record.outcomeLearning,
      { saving: outcomeLearningSaving },
    ) : ""}
    ${productResearchIntelligenceMarkup({
      categoryAnalysis,
      competitorAnalysis,
      trendAnalysis,
      guidance,
      stageCorrections,
      sources: record?.sources || [],
      disabled: approved || researchView === "evidence",
    })}
    <section class="product-research-scoreboard" aria-label="Предварительная оценка контента">
      <div class="card card-pad product-research-score" style="--research-score:${score}">
        <div class="product-research-score-ring"><strong>${score}</strong><small>из 100</small></div>
        <div><p class="eyebrow">Креативный потенциал</p><h2>${scoreLabel(score)}</h2><p>${escapeHtml(record?.forecastSummary || "Оценка показывает качество вводных и сценарной идеи.")}</p><small class="product-research-score-note">Это предпубликационная эвристика: она не гарантирует просмотры или продажи.</small></div>
      </div>
      <div class="card card-pad product-research-confidence"><span class="badge">${escapeHtml(confidence.label)}</span><h2>Уверенность: ${escapeHtml(confidence.label.toLowerCase())}</h2><p>${escapeHtml(confidence.description)}</p></div>
    </section>
    <div class="product-research-result-grid">
      <section class="card product-research-sources" aria-labelledby="research-sources-title">
        <div class="card-header"><div><p class="eyebrow">Доказательства</p><h2 id="research-sources-title">Что найдено и откуда</h2></div><span class="badge">${record?.sources?.length || 0} источников</span></div>
        <div class="product-research-source-list">${sourceMarkup}</div>
      </section>
      <section class="card product-research-factors" aria-labelledby="research-factors-title">
        <div class="card-header"><div><p class="eyebrow">Почему такой балл</p><h2 id="research-factors-title">Сильные стороны и риски</h2></div></div>
        <ul>${normalizeFactors(record?.factors).map((factor) => `<li class="${factor.impact < 0 ? "risk" : "strength"}"><span aria-hidden="true">${factor.impact < 0 ? "!" : "+"}</span><div><strong>${escapeHtml(factor.label)}</strong><p>${escapeHtml(factor.detail)}</p></div></li>`).join("") || `<li><div><strong>Недостаточно данных</strong><p>Добавьте источники и уточните ТЗ — оценка станет точнее.</p></div></li>`}</ul>
      </section>
    </div>
    <form id="product-research-brief-form" class="card product-research-brief" data-research-id="${escapeHtml(record?.id || "")}" data-ce-patch-key="research-brief:${escapeHtml(record?.id)}" novalidate>
      <input type="hidden" name="recommended_scenario_position" value="${recommendedScenarioIndex >= 0 ? recommendedScenarioIndex + 1 : ""}" />
      <input type="hidden" name="recommended_scenario_reason" value="${escapeHtml(recommendedScenarioReason)}" />
      <div class="card-header"><div><p class="eyebrow">${approved ? "Утверждённый результат" : "Редактируемый результат"}</p><h2>ТЗ для команды</h2><p>${approved ? "Это ТЗ уже превратилось в задачи. Чтобы не менять работу исполнителей незаметно, поля заблокированы." : "Исправьте всё, что звучит неточно. Сохранение не создаёт задачи."}</p></div><span class="badge">${approved ? "Утверждено" : "Черновик"}</span></div>
      <div class="product-research-brief-body">
        <div class="form-grid-2">
          ${textField("brief_title", "Название ТЗ", brief.title, 180, approved)}
          ${textField("target_audience", "Для кого контент", brief.targetAudience, 500, approved)}
        </div>
        ${textArea("key_message", "Главная мысль", brief.keyMessage, "Что зритель должен понять по первому кадру или первым секундам", 1200, approved)}
        <div class="form-grid-2">
          ${textArea("proof_points", "Что показать как доказательство", brief.proofPoints, "По одному пункту на строку", 2500, approved)}
          ${textArea("avoid_claims", "Что нельзя обещать", brief.avoidClaims, "Неподтверждённые, медицинские или абсолютные обещания", 2500, approved)}
        </div>
        <div class="form-grid-2">
          ${textArea("visual_direction", "Визуальный стиль", brief.visualDirection, "Локация, свет, план, товар в кадре", 1800, approved)}
          ${textArea("cta", "Безопасный CTA", brief.cta, "Что зритель делает после ролика", 800, approved)}
        </div>
        <div class="product-research-scenarios-heading"><div><p class="eyebrow">Три разные гипотезы</p><h2>Сценарии и будущие задачи</h2></div><p>Не делайте три копии одного хука — меняйте угол подачи.</p></div>
        ${recommendedScenarioIndex >= 0 ? `<div class="alert alert-info product-research-scenario-choice" role="note"><strong>Лучший первый эксперимент — сценарий ${recommendedScenarioIndex + 1}.</strong><span>${escapeHtml(recommendedScenarioReason || "Он даёт наиболее ясную и безопасную проверку идеи при точном показе товара.")} Это эвристика качества замысла, а не обещание просмотров или продаж.</span></div>` : ""}
        <div class="product-research-scenarios">${scenarios.map((scenario, index) => scenarioEditor(scenario, index, {
          members: assignees,
          defaultAssigneeId: fallbackAssigneeId,
          disabled: approved,
          recommended: index === recommendedScenarioIndex,
          generationHandoffAllowed: !generationHandoffBlocked,
        })).join("")}</div>
        ${guidanceNeedsOverride ? researchGapOverrideMarkup({ guidance, approved, humanResearchDecision }) : ""}
        <label class="check-row product-research-approval"><input type="checkbox" name="approve_ack" ${approved ? "checked disabled" : ""} /><span><strong>Факты, формулировки и три сценария проверены человеком</strong><br /><small>${approved ? "Проверка завершена: задачи уже созданы и назначены выбранным участникам." : "При утверждении портал создаст задачи и назначит каждую выбранному выше исполнителю."}</small></span></label>
      </div>
      <div class="product-research-brief-actions">
        <button class="btn btn-secondary" type="submit" data-research-submit="save" ${saving || approving || approved ? "disabled" : ""}>${approved ? "Сохранение заблокировано" : saving ? "Сохраняем…" : "Сохранить черновик"}</button>
        <button class="btn ${approved ? "btn-secondary" : ""}" type="submit" data-research-submit="approve" ${approved ? "" : 'data-primary-action="true"'} ${saving || approving || approved ? "disabled" : ""}>${approving ? "Создаём задачи…" : approved ? "Задачи уже созданы" : "Утвердить и создать 3 задачи →"}</button>
      </div>
    </form>
    </div>`;
}

export function productResearchEvidenceMarkup(record, {
  notice = "",
  error = "",
  aiReceiptHref = "",
  aiReceiptPending = false,
  canStartNew = false,
} = {}) {
  const categoryAnalysis = normalizeCategoryAnalysis(record?.categoryAnalysis);
  const competitorAnalysis = normalizeCompetitorAnalysis(record?.competitorAnalysis);
  const trendAnalysis = normalizeTrendAnalysis(record?.trendAnalysis);
  const guidance = normalizeResearchGuidance(record?.guidance);
  const stageCorrections = normalizeStageCorrections(record?.stageCorrections);
  const confidence = confidenceCopy(record?.confidence);
  const score = clampScore(record?.score);
  const sources = normalizeSources(record?.sources);
  const sourceMarkup = sources.length
    ? sources.map(sourceMarkupItem).join("")
    : `<div class="product-research-empty-note"><strong>Публичные источники не подтверждены</strong><p>Не переносите найденные ИИ формулировки в ролик как факт без доказательства.</p></div>`;
  const receiptAction = aiReceiptHref
    ? `<a class="btn" href="${escapeHtml(aiReceiptHref)}" data-primary-action="true">Открыть свой чек в ИИ-центре →</a>`
    : aiReceiptPending
      ? `<p class="muted" role="status">Чек ИИ-центра ещё формируется. Обновите раздел через несколько секунд; новый платный анализ для этого не нужен.</p>`
      : "";
  const newResearchAction = canStartNew
    ? `<button class="btn btn-secondary" type="button" data-action="new-product-research">Подготовить новое исследование</button>`
    : "";
  return `
    <div data-research-view="evidence" data-product-research-evidence-read-only="true">
      ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
      ${notice ? `<div class="alert alert-info" role="status"><strong aria-hidden="true">i</strong><span>${escapeHtml(notice)}</span></div>` : ""}
      <section class="card card-pad" aria-labelledby="operator-research-evidence-title">
        <p class="eyebrow">Ваш завершённый анализ</p>
        <h2 id="operator-research-evidence-title">Доказательства доступны только для чтения</h2>
        <p>Источники и выводы этого запуска сохранены без управленческих форм, утверждения задач и автоматической передачи в генерацию. Следующий выбор вы делаете сами в ИИ-центре.</p>
        <div class="inline-actions">${receiptAction}${newResearchAction}</div>
      </section>
      ${productResearchIntelligenceMarkup({
        categoryAnalysis,
        competitorAnalysis,
        trendAnalysis,
        guidance,
        stageCorrections,
        sources,
        readOnly: true,
      })}
      <section class="product-research-scoreboard" aria-label="Предварительная оценка контента">
        <div class="card card-pad product-research-score" style="--research-score:${score}">
          <div class="product-research-score-ring"><strong>${score}</strong><small>из 100</small></div>
          <div><p class="eyebrow">Креативный потенциал</p><h2>${scoreLabel(score)}</h2><p>${escapeHtml(record?.forecastSummary || "Оценка показывает качество вводных и сценарной идеи.")}</p><small class="product-research-score-note">Это предпубликационная эвристика: она не гарантирует просмотры или продажи.</small></div>
        </div>
        <div class="card card-pad product-research-confidence"><span class="badge">${escapeHtml(confidence.label)}</span><h2>Уверенность: ${escapeHtml(confidence.label.toLowerCase())}</h2><p>${escapeHtml(confidence.description)}</p></div>
      </section>
      <div class="product-research-result-grid">
        <section class="card product-research-sources" aria-labelledby="operator-research-sources-title">
          <div class="card-header"><div><p class="eyebrow">Доказательства</p><h2 id="operator-research-sources-title">Что найдено и откуда</h2></div><span class="badge">${sources.length} источников</span></div>
          <div class="product-research-source-list">${sourceMarkup}</div>
        </section>
        <section class="card product-research-factors" aria-labelledby="operator-research-factors-title">
          <div class="card-header"><div><p class="eyebrow">Почему такой балл</p><h2 id="operator-research-factors-title">Сильные стороны и риски</h2></div></div>
          <ul>${normalizeFactors(record?.factors).map((factor) => `<li class="${factor.impact < 0 ? "risk" : "strength"}"><span aria-hidden="true">${factor.impact < 0 ? "!" : "+"}</span><div><strong>${escapeHtml(factor.label)}</strong><p>${escapeHtml(factor.detail)}</p></div></li>`).join("") || `<li><div><strong>Недостаточно данных</strong><p>Проверьте источники и ограничения анализа перед решением.</p></div></li>`}</ul>
        </section>
      </div>
    </div>`;
}

export function readProductResearchBrief(form) {
  const data = new FormData(form);
  const scenarios = [0, 1, 2].map((index) => ({
    position: index + 1,
    title: value(data, `scenario_${index}_title`),
    platform: value(data, `scenario_${index}_platform`),
    generation_mode: value(data, `scenario_${index}_generation_mode`),
    generation_mode_reason: value(
      data,
      `scenario_${index}_generation_mode_reason`,
    ),
    hook: value(data, `scenario_${index}_hook`),
    script: value(data, `scenario_${index}_script`),
    shot_list: value(data, `scenario_${index}_shots`),
    task_title: value(data, `scenario_${index}_task_title`),
    assignee_id: value(data, `scenario_${index}_assignee_id`),
  }));
  return {
    title: value(data, "brief_title"),
    target_audience: value(data, "target_audience"),
    key_message: value(data, "key_message"),
    proof_points: value(data, "proof_points"),
    avoid_claims: value(data, "avoid_claims"),
    visual_direction: value(data, "visual_direction"),
    cta: value(data, "cta"),
    stage_corrections: {
      sources: value(data, "source_correction"),
      category: value(data, "category_correction"),
      competitors: value(data, "competitor_correction"),
      trends: value(data, "trend_correction"),
      strategy: value(data, "strategy_correction"),
    },
    research_gap_override_ack: data.has("research_gap_override_ack"),
    recommended_scenario_position: normalizeRecommendedScenarioPosition(
      value(data, "recommended_scenario_position"),
    ),
    recommended_scenario_reason: value(data, "recommended_scenario_reason"),
    scenarios,
  };
}

export function inspectResearchScenarioGenerationReadiness(scenario) {
  const mode = String(
    scenario?.generation_mode
      || scenario?.generationMode
      || scenario?.recommended_generation_mode
      || "",
  ).trim();
  const script = String(
    scenario?.script
      || scenario?.spokenScript
      || scenario?.spoken_script
      || "",
  ).replace(/\s+/gu, " ").trim();
  const shotList = String(
    scenario?.shot_list
      || scenario?.shotList
      || "",
  );
  const shotLines = shotList.split(/\r?\n/u)
    .map((line) => line.replace(/\s+/gu, " ").trim())
    .filter(Boolean);
  const spokenWords = script.match(
    /[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu,
  )?.length || 0;
  const generatedTextInstruction = shotLines.find((line) =>
    /(?:^|[^\p{L}\p{N}_])текст\s*:\s*(?!без текста(?:$|[.!]))/iu.test(line)
  );
  if (!["real_photo", "real_gen4", "real_seedance"].includes(mode)) {
    return {
      ready: false,
      code: "generation_mode_missing",
      message: "Не удалось определить технический режим генерации.",
    };
  }
  if (generatedTextInstruction) {
    return {
      ready: false,
      code: "generated_text_not_supported",
      message: "Уберите сгенерированные надписи: титры и маркировка добавляются после QA.",
    };
  }
  if (mode === "real_photo") {
    if (script || shotLines.length !== 3) {
      return {
        ready: false,
        code: "photo_scenario_not_ready",
        message: "Для фото оставьте пустую реплику и ровно три строки: композиция, свет и фон.",
      };
    }
    return {
      ready: true,
      code: "photo_scenario_ready",
      message: "Готово для квадратного Seedream-фото: один кадр, без речи и надписей.",
    };
  }
  if (mode === "real_gen4") {
    if (script || shotLines.length !== 1) {
      return {
        ready: false,
        code: "gen4_scenario_not_ready",
        message: "Для Gen‑4 оставьте пустую реплику и ровно одно действие на 5 секунд.",
      };
    }
    return {
      ready: true,
      code: "gen4_scenario_ready",
      message: "Готово для Gen‑4: одно 5‑секундное действие без речи и надписей.",
    };
  }
  if (spokenWords < 1 || spokenWords > 22 || shotLines.length < 2 || shotLines.length > 3) {
    return {
      ready: false,
      code: "seedance_scenario_not_ready",
      message: `Для Seedance нужны реплика 1–22 слова и 2–3 кадра; сейчас ${spokenWords} слов и ${shotLines.length} строк.`,
    };
  }
  return {
    ready: true,
    code: "seedance_scenario_ready",
    message: `Готово для Seedance: ${spokenWords} слов, ${shotLines.length} кадра, без сгенерированных надписей.`,
  };
}

function normalizeBrief(value) {
  const source = objectValue(value) || {};
  return {
    title: String(source.title || source.name || "ТЗ на три варианта товарного контента"),
    targetAudience: String(source.target_audience || source.targetAudience || formatAudience(source.audience)),
    keyMessage: String(source.key_message || source.keyMessage || source.message || source.summary || ""),
    proofPoints: lines(source.proof_points || source.proofPoints || source.proofs || formatFacts(source.facts)),
    avoidClaims: lines(source.avoid_claims || source.avoidClaims || source.restrictions || formatForbiddenClaims(source.claims)),
    visualDirection: String(source.visual_direction || source.visualDirection || source.visual_style || lines(source.task_blueprint?.mandatory_shots)),
    cta: String(source.cta || source.call_to_action || arrayValue(source.scenarios)[0]?.cta || ""),
    stageCorrections: normalizeStageCorrections(source.human_stage_corrections),
    humanResearchDecision: normalizeHumanResearchDecision(
      source.human_research_decision,
    ),
    scenarios: arrayValue(source.scenarios),
  };
}

function normalizeCategoryAnalysis(value) {
  const source = objectValue(value) || {};
  return {
    categoryName: String(source.category_name || source.categoryName || "").trim(),
    marketCategoryKey: String(
      source.market_category_key || source.marketCategoryKey || "",
    ).trim(),
    complianceCategory: String(
      source.compliance_category || source.complianceCategory || "",
    ).trim(),
    confidence: normalizeConfidence(source.confidence),
    maturity: String(source.maturity || "unknown").trim(),
    definition: String(source.definition || "").trim(),
    buyerJobs: stringArray(source.buyer_jobs || source.buyerJobs).slice(0, 10),
    substituteCategories: stringArray(
      source.substitute_categories || source.substituteCategories,
    ).slice(0, 10),
    unknowns: stringArray(source.unknowns).slice(0, 10),
    sourceIds: stringArray(source.source_ids || source.sourceIds).slice(0, 8),
  };
}

function normalizeCompetitorAnalysis(value) {
  const source = objectValue(value) || {};
  const competitors = arrayValue(source.competitors).slice(0, 12).map((item) => {
    const competitor = objectValue(item) || {};
    return {
      name: String(competitor.name || "Сопоставимое предложение").trim(),
      positioning: String(competitor.positioning || "").trim(),
      pricePositioning: String(
        competitor.price_positioning || competitor.pricePositioning || "",
      ).trim(),
      recurringFormats: stringArray(
        competitor.recurring_formats || competitor.recurringFormats,
      ).slice(0, 8),
      strengths: stringArray(competitor.strengths).slice(0, 8),
      weaknesses: stringArray(competitor.weaknesses).slice(0, 8),
      reusableStructures: stringArray(
        competitor.reusable_structures || competitor.reusableStructures,
      ).slice(0, 8),
      sourceIds: stringArray(
        competitor.source_ids || competitor.sourceIds,
      ).slice(0, 8),
    };
  });
  return {
    coverage: String(source.coverage || "none").trim(),
    competitors,
    saturatedPatterns: arrayValue(
      source.saturated_patterns || source.saturatedPatterns,
    ).map((item) => normalizeEvidenceItem(item, "pattern")).filter((item) => item.text).slice(0, 12),
    contentGaps: arrayValue(
      source.content_gaps || source.contentGaps,
    ).map((item) => normalizeEvidenceItem(item, "gap")).filter((item) => item.text).slice(0, 12),
    limitations: stringArray(source.limitations).slice(0, 10),
  };
}

function normalizeEvidenceItem(value, textKey) {
  if (typeof value === "string") return { text: value.trim(), sourceIds: [] };
  const source = objectValue(value) || {};
  return {
    text: String(source[textKey] || source.text || "").trim(),
    sourceIds: stringArray(source.source_ids || source.sourceIds).slice(0, 8),
  };
}

function normalizeTrendAnalysis(value) {
  const source = objectValue(value) || {};
  return {
    signalCatalogVersion: String(
      source.signal_catalog_version || source.signalCatalogVersion || "legacy",
    ).trim(),
    asOf: String(source.as_of || source.asOf || "").trim(),
    signals: arrayValue(source.signals).slice(0, 12).map((item) => {
      const signal = objectValue(item) || {};
      return {
        signalKey: String(signal.signal_key || signal.signalKey || "").trim(),
        signal: String(signal.signal || "").trim(),
        direction: String(signal.direction || "unclear").trim(),
        confidence: normalizeConfidence(signal.confidence),
        evidence: String(signal.evidence || "").trim(),
        sourceIds: stringArray(signal.source_ids || signal.sourceIds).slice(0, 8),
        recommendedUse: String(
          signal.recommended_use || signal.recommendedUse || "monitor",
        ).trim(),
      };
    }).filter((signal) => signal.signal),
    limitations: stringArray(source.limitations).slice(0, 10),
  };
}

function normalizeResearchGuidance(value) {
  const source = objectValue(value) || {};
  return {
    status: String(source.status || "needs_more_evidence").trim(),
    recommendedNextStep: String(
      source.recommended_next_step || source.recommendedNextStep || "",
    ).trim(),
    reason: String(source.reason || "").trim(),
    questions: stringArray(
      source.questions_for_user || source.questionsForUser || source.questions,
    ).slice(0, 8),
    actions: stringArray(
      source.suggested_actions || source.suggestedActions || source.actions,
    ).slice(0, 8),
  };
}

export function normalizeResearchProviderControl(value) {
  const envelope = objectValue(value) || {};
  const unavailable = envelope.unavailable === true;
  const source = objectValue(envelope.control) || objectValue(envelope.status) || (
    Object.prototype.hasOwnProperty.call(envelope, "providers") ? envelope : {}
  );
  const controlsSource = objectValue(source.controls) || {};
  const createsResearchRuns = controlsSource.creates_research_runs
    ?? controlsSource.createsResearchRuns;
  const automaticCanary = controlsSource.automatic_canary
    ?? controlsSource.automaticCanary;
  const automaticFallback = controlsSource.automatic_fallback
    ?? controlsSource.automaticFallback;
  const externalCallPerformed = controlsSource.external_call_performed
    ?? controlsSource.externalCallPerformed;
  const expectedAdapters = new Map([
    ["openai_web_search", "openai-responses-web-search-v1"],
    ["youtube_data_api_v3", "youtube-data-api-v3-public-metadata-v1"],
  ]);
  const providerCatalogValid = Array.isArray(source.providers)
    && source.providers.length > 0
    && source.providers.every((item) => {
      const provider = objectValue(item) || {};
      const providerKey = String(provider.provider_key || provider.providerKey || "");
      const adapterVersion = String(
        provider.adapter_version || provider.adapterVersion || "",
      );
      return expectedAdapters.get(providerKey) === adapterVersion;
    })
    && source.providers.some((item) => (
      String(item?.provider_key || item?.providerKey || "") === "openai_web_search"
    ));
  const contractValid = !unavailable
    && source.ok === true
    && source.version === "research-provider-control-plane-v1"
    && providerCatalogValid
    && (controlsSource.explicit_paid_analysis_required === true
      || controlsSource.explicitPaidAnalysisRequired === true)
    && createsResearchRuns === false
    && automaticCanary === false
    && automaticFallback === false
    && externalCallPerformed === false;
  const runSource = objectValue(source.run_control || source.runControl) || {};
  const responseSource = objectValue(
    source.response_state || source.responseState,
  ) || {};
  const terminalDiagnosticSource = objectValue(
    responseSource.terminal_diagnostic || responseSource.terminalDiagnostic,
  ) || {};
  const authorizationSource = objectValue(runSource.authorization) || {};
  const attemptSource = objectValue(runSource.attempt) || {};
  const providers = arrayValue(source.providers).slice(0, 12).map((item) => {
    const provider = objectValue(item) || {};
    const healthSource = objectValue(provider.health) || {};
    return {
      providerKey: String(provider.provider_key || provider.providerKey || "").trim(),
      displayName: String(provider.display_name || provider.displayName || provider.provider_key || "Провайдер").trim(),
      adapterVersion: String(provider.adapter_version || provider.adapterVersion || "").trim(),
      lifecycleStatus: String(provider.lifecycle_status || provider.lifecycleStatus || "unknown").trim(),
      rolloutStage: String(provider.rollout_stage || provider.rolloutStage || "unknown").trim(),
      billingMode: String(provider.billing_mode || provider.billingMode || "unknown").trim(),
      healthMode: String(provider.health_mode || provider.healthMode || "passive_receipts").trim(),
      canaryMode: String(provider.canary_mode || provider.canaryMode || "manual_only").trim(),
      automaticCanaryAllowed: provider.automatic_canary_allowed === true
        || provider.automaticCanaryAllowed === true,
      automaticFallbackAllowed: provider.automatic_fallback_allowed === true
        || provider.automaticFallbackAllowed === true,
      commercialUseAllowed: provider.commercial_use_allowed === true
        || provider.commercialUseAllowed === true,
      arbitraryPublicAccountsAllowed: provider.arbitrary_public_accounts_allowed === true
        || provider.arbitraryPublicAccountsAllowed === true,
      subjectAuthorizationRequired: provider.subject_authorization_required === true
        || provider.subjectAuthorizationRequired === true,
      capabilities: stringArray(provider.capabilities).slice(0, 20),
      platforms: stringArray(provider.platforms).slice(0, 20),
      health: {
        status: String(healthSource.status || "unknown").trim().toLowerCase(),
        fresh: healthSource.fresh === true,
        failureCode: String(healthSource.failure_code || healthSource.failureCode || "").trim(),
        citationCount: healthSource.citation_count === null
            || healthSource.citationCount === null
          ? null
          : boundedCount(
            healthSource.citation_count ?? healthSource.citationCount,
            0,
          ),
        checkedAt: String(healthSource.checked_at || healthSource.checkedAt || "").trim(),
        expiresAt: String(healthSource.expires_at || healthSource.expiresAt || "").trim(),
      },
    };
  }).filter((provider) => provider.providerKey);
  const responseBindingState = String(
    responseSource.binding_state || responseSource.bindingState || "not_bound",
  ).trim().toLowerCase();
  const responseStatusCandidate = String(
    responseSource.provider_status || responseSource.providerStatus || "",
  ).trim().toLowerCase();
  const responseSuffixCandidate = String(
    responseSource.provider_response_suffix
      || responseSource.providerResponseSuffix
      || "",
  ).trim();
  const responseBound = responseBindingState === "bound"
    && RESEARCH_PROVIDER_RESPONSE_STATUSES.has(responseStatusCandidate)
    && /^[A-Za-z0-9_-]{1,8}$/u.test(responseSuffixCandidate);
  const terminalStatus = String(
    terminalDiagnosticSource.terminal_status
      || terminalDiagnosticSource.terminalStatus
      || "",
  ).trim().toLowerCase();
  const diagnosticCode = String(
    terminalDiagnosticSource.diagnostic_code
      || terminalDiagnosticSource.diagnosticCode
      || "",
  ).trim().toLowerCase();
  const diagnosticType = String(
    terminalDiagnosticSource.diagnostic_type
      || terminalDiagnosticSource.diagnosticType
      || "",
  ).trim().toLowerCase();
  const diagnosticMessage = String(
    terminalDiagnosticSource.diagnostic_message
      || terminalDiagnosticSource.diagnosticMessage
      || "",
  ).replace(/\s+/gu, " ").trim().slice(0, 280);
  const terminalDiagnosticValid = ["failed", "cancelled", "incomplete"]
    .includes(terminalStatus)
    && RESEARCH_PROVIDER_DIAGNOSTIC_TOKEN.test(diagnosticCode)
    && RESEARCH_PROVIDER_DIAGNOSTIC_TOKEN.test(diagnosticType)
    && diagnosticMessage.length >= 10;
  return {
    available: contractValid,
    version: String(source.version || ""),
    providers,
    runControl: Object.keys(runSource).length ? {
      runId: String(runSource.run_id || runSource.runId || "").trim(),
      runStatus: String(runSource.run_status || runSource.runStatus || "unknown").trim(),
      authorized: runSource.authorized === true,
      authorization: Object.keys(authorizationSource).length ? {
        kind: String(authorizationSource.kind || "").trim(),
        paidAnalysisAck: authorizationSource.paid_analysis_ack === true
          || authorizationSource.paidAnalysisAck === true,
        providerKey: String(authorizationSource.provider_key || authorizationSource.providerKey || "").trim(),
        adapterVersion: String(authorizationSource.adapter_version || authorizationSource.adapterVersion || "").trim(),
        maxProviderAttempts: boundedCount(
          authorizationSource.max_provider_attempts ?? authorizationSource.maxProviderAttempts,
          0,
        ),
        automaticFallbackAllowed: authorizationSource.automatic_fallback_allowed === true
          || authorizationSource.automaticFallbackAllowed === true,
        reasonCode: String(authorizationSource.reason_code || authorizationSource.reasonCode || "").trim(),
        authorizedAt: String(authorizationSource.authorized_at || authorizationSource.authorizedAt || "").trim(),
      } : null,
      attempt: Object.keys(attemptSource).length ? {
        providerKey: String(attemptSource.provider_key || attemptSource.providerKey || "").trim(),
        adapterVersion: String(attemptSource.adapter_version || attemptSource.adapterVersion || "").trim(),
        model: String(attemptSource.model || "").trim(),
        attemptNumber: boundedCount(
          attemptSource.attempt_number ?? attemptSource.attemptNumber,
          0,
        ),
        boundAt: String(attemptSource.bound_at || attemptSource.boundAt || "").trim(),
      } : null,
    } : null,
    responseState: {
      bindingState: responseBound ? "bound" : "not_bound",
      providerStatus: responseBound ? responseStatusCandidate : "",
      providerResponseSuffix: responseBound ? responseSuffixCandidate : "",
      acceptedAt: responseBound
        ? String(responseSource.accepted_at || responseSource.acceptedAt || "").trim()
        : "",
      lastCheckedAt: responseBound
        ? String(
          responseSource.last_checked_at || responseSource.lastCheckedAt || "",
        ).trim()
        : "",
      terminalDiagnostic: terminalDiagnosticValid ? {
        terminalStatus,
        failureCode: String(
          terminalDiagnosticSource.failure_code
            || terminalDiagnosticSource.failureCode
            || "",
        ).trim().toLowerCase(),
        diagnosticCode,
        diagnosticType,
        diagnosticMessage,
        providerMessagePresent:
          terminalDiagnosticSource.provider_message_present === true
          || terminalDiagnosticSource.providerMessagePresent === true,
        checkedAt: String(
          terminalDiagnosticSource.checked_at
            || terminalDiagnosticSource.checkedAt
            || "",
        ).trim(),
      } : null,
    },
    controls: {
      explicitPaidAnalysisRequired: controlsSource.explicit_paid_analysis_required === true
        || controlsSource.explicitPaidAnalysisRequired === true,
      createsResearchRuns: controlsSource.creates_research_runs === true
        || controlsSource.createsResearchRuns === true,
      automaticCanary: controlsSource.automatic_canary === true
        || controlsSource.automaticCanary === true,
      automaticFallback: controlsSource.automatic_fallback === true
        || controlsSource.automaticFallback === true,
      externalCallPerformed: controlsSource.external_call_performed === true
        || controlsSource.externalCallPerformed === true,
    },
  };
}

export function normalizeResearchMarketRegistry(value) {
  const envelope = objectValue(value) || {};
  const unavailable = envelope.unavailable === true;
  const source = objectValue(envelope.registry) || (
    Object.prototype.hasOwnProperty.call(envelope, "categories") ? envelope : {}
  );
  const bindingSource = objectValue(source.current_binding || source.currentBinding);
  const candidateSource = objectValue(source.candidate);
  const guidanceSource = objectValue(source.guidance) || {};
  const velocityGuidanceSource = objectValue(
    guidanceSource.trend_velocity || guidanceSource.trendVelocity,
  ) || {};
  const hasRawVelocity = Object.prototype.hasOwnProperty.call(
    source,
    "trend_velocity",
  ) || Object.prototype.hasOwnProperty.call(source, "trendVelocity");
  const rawVelocity = Object.prototype.hasOwnProperty.call(source, "trend_velocity")
    ? source.trend_velocity
    : source.trendVelocity;
  let contractValid = !unavailable
    && source.ok === true
    && typeof (source.can_resolve ?? source.canResolve) === "boolean"
    && Array.isArray(source.categories)
    && Array.isArray(source.trend_timeline || source.trendTimeline)
    && (!hasRawVelocity || Array.isArray(rawVelocity))
    && Object.keys(guidanceSource).length > 0;
  const category = (item) => {
    const row = objectValue(item) || {};
    return {
      categoryId: String(row.category_key || row.category_id || row.categoryId || "").trim(),
      canonicalName: String(row.canonical_name || row.canonicalName || "").trim(),
      definition: String(row.definition || "").trim(),
      status: String(row.status || "active").trim(),
      aliases: stringArray(row.aliases).slice(0, 10),
      createdAt: String(row.created_at || row.createdAt || "").trim(),
    };
  };
  const field = (row, snakeKey, camelKey) => (
    Object.prototype.hasOwnProperty.call(row, snakeKey)
      ? row[snakeKey]
      : row[camelKey]
  );
  const strictInteger = (value, minimum, maximum) => (
    typeof value === "number"
      && Number.isSafeInteger(value)
      && value >= minimum
      && value <= maximum
      ? value
      : false
  );
  const strictNumber = (value, minimum, maximum) => (
    typeof value === "number"
      && Number.isFinite(value)
      && value >= minimum
      && value <= maximum
      ? value
      : false
  );
  const nullableUuid = (value) => (
    value === null ? null : researchOutcomeUuid(value) || false
  );
  const nullableTimestamp = (value) => (
    value === null ? null : researchYoutubeTimestamp(value) || false
  );
  const nullableInteger = (value, minimum, maximum) => (
    value === null ? null : strictInteger(value, minimum, maximum)
  );
  const nullableNumber = (value, minimum, maximum) => (
    value === null ? null : strictNumber(value, minimum, maximum)
  );
  const roundHalfAwayFromZero = (value, decimals = 0) => {
    const factor = 10 ** decimals;
    return Math.sign(value) * Math.round(Math.abs(value) * factor) / factor;
  };
  let velocityContractValid = true;
  const parsedTrendVelocity = arrayValue(rawVelocity).slice(0, 24).map((item) => {
    const row = objectValue(item) || {};
    const comparisonMode = String(
      row.comparison_mode || row.comparisonMode || "",
    ).trim();
    const definitionVersion = String(
      row.definition_version || row.definitionVersion || "",
    ).trim();
    const signalKey = String(row.signal_key || row.signalKey || "").trim();
    const eventHash = String(row.event_hash || row.eventHash || "").trim();
    const lineageHash = String(row.lineage_hash || row.lineageHash || "").trim();
    const snapshotId = researchOutcomeUuid(field(row, "snapshot_id", "snapshotId"));
    const previousSnapshotId = nullableUuid(
      field(row, "previous_snapshot_id", "previousSnapshotId"),
    );
    const runId = researchOutcomeUuid(field(row, "run_id", "runId"));
    const observedAt = researchYoutubeTimestamp(field(row, "observed_at", "observedAt"));
    const previousObservedAt = nullableTimestamp(
      field(row, "previous_observed_at", "previousObservedAt"),
    );
    const categoryId = nullableUuid(
      field(row, "category_key", "categoryId"),
    );
    const canonicalLabel = researchYoutubeText(
      field(row, "canonical_label", "canonicalLabel"),
      1,
      160,
    );
    const currentPresent = field(row, "current_present", "currentPresent");
    const previousPresent = field(row, "previous_present", "previousPresent");
    const currentDirection = field(row, "current_direction", "currentDirection");
    const previousDirection = field(row, "previous_direction", "previousDirection");
    const currentSourceCount = strictInteger(
      field(row, "current_source_count", "currentSourceCount"),
      0,
      100,
    );
    const previousSourceCount = strictInteger(
      field(row, "previous_source_count", "previousSourceCount"),
      0,
      100,
    );
    const currentTotalSourceCount = strictInteger(
      field(row, "current_total_source_count", "currentTotalSourceCount"),
      1,
      100,
    );
    const previousTotalSourceCount = nullableInteger(
      field(row, "previous_total_source_count", "previousTotalSourceCount"),
      1,
      100,
    );
    const currentSupportBps = strictInteger(
      field(row, "current_support_bps", "currentSupportBps"),
      0,
      10_000,
    );
    const previousSupportBps = nullableInteger(
      field(row, "previous_support_bps", "previousSupportBps"),
      0,
      10_000,
    );
    const supportDeltaBps = nullableInteger(
      field(row, "support_delta_bps", "supportDeltaBps"),
      -10_000,
      10_000,
    );
    const supportVelocity = nullableNumber(
      field(row, "support_velocity_bps_per_30d", "supportVelocityBpsPer30d"),
      -100_000,
      100_000,
    );
    const elapsedSeconds = nullableInteger(
      field(row, "elapsed_seconds", "elapsedSeconds"),
      0,
      Number.MAX_SAFE_INTEGER,
    );
    const claimAllowed = field(row, "claim_allowed", "claimAllowed");
    const supportState = String(
      row.support_state || row.supportState || "",
    ).trim();
    const recommendedNextStep = String(
      row.recommended_next_step || row.recommendedNextStep || "",
    ).trim();
    const modeShapeValid = ({
      baseline: previousSnapshotId === null
        && previousObservedAt === null
        && previousTotalSourceCount === null
        && previousSupportBps === null
        && elapsedSeconds === null
        && currentPresent === true
        && previousPresent === false,
      comparable: previousSnapshotId
        && previousObservedAt
        && previousTotalSourceCount !== null
        && elapsedSeconds >= 259_200
        && currentPresent === true
        && previousPresent === true,
      category_reset: previousSnapshotId
        && previousObservedAt
        && previousTotalSourceCount !== null
        && elapsedSeconds !== null
        && (currentPresent === true || previousPresent === true),
      signal_new: previousSnapshotId
        && previousObservedAt
        && previousTotalSourceCount !== null
        && elapsedSeconds !== null
        && currentPresent === true
        && previousPresent === false,
      signal_removed: previousSnapshotId
        && previousObservedAt
        && previousTotalSourceCount !== null
        && elapsedSeconds !== null
        && currentPresent === false
        && previousPresent === true,
      interval_too_short: previousSnapshotId
        && previousObservedAt
        && previousTotalSourceCount !== null
        && elapsedSeconds !== null
        && elapsedSeconds < 259_200
        && currentPresent === true
        && previousPresent === true,
    })[comparisonMode] === true;
    const expectedCurrentSupport = Number.isSafeInteger(currentSourceCount)
        && Number.isSafeInteger(currentTotalSourceCount)
      ? Math.round(10_000 * currentSourceCount / currentTotalSourceCount)
      : null;
    const expectedPreviousSupport = Number.isSafeInteger(previousSourceCount)
        && Number.isSafeInteger(previousTotalSourceCount)
      ? Math.round(10_000 * previousSourceCount / previousTotalSourceCount)
      : null;
    const expectedDelta = comparisonMode === "comparable"
        && Number.isSafeInteger(currentSupportBps)
        && Number.isSafeInteger(previousSupportBps)
      ? currentSupportBps - previousSupportBps
      : null;
    const expectedVelocity = comparisonMode === "comparable"
        && Number.isSafeInteger(expectedDelta)
        && Number.isSafeInteger(elapsedSeconds)
      ? roundHalfAwayFromZero(expectedDelta * 2_592_000 / elapsedSeconds, 2)
      : null;
    const expectedSupportState = comparisonMode !== "comparable"
      ? "no_velocity_claim"
      : expectedDelta > 0
        ? "support_breadth_increasing"
        : expectedDelta < 0
          ? "support_breadth_decreasing"
          : "support_breadth_stable";
    const expectedNextStep = ({
      baseline: "collect_next_approved_snapshot",
      comparable: "review_support_velocity",
      category_reset: "establish_new_category_baseline",
      signal_new: "collect_next_approved_snapshot",
      signal_removed: "review_trends_stage",
      interval_too_short: "wait_for_minimum_interval",
    })[comparisonMode];
    const observedElapsed = observedAt && previousObservedAt
      ? Math.floor((Date.parse(observedAt) - Date.parse(previousObservedAt)) / 1000)
      : null;
    const directionShapeValid = typeof currentPresent === "boolean"
      && typeof previousPresent === "boolean"
      && (currentPresent
        ? RESEARCH_TREND_DIRECTIONS.has(currentDirection)
        : currentDirection === null)
      && (previousPresent
        ? RESEARCH_TREND_DIRECTIONS.has(previousDirection)
        : previousDirection === null);
    const invalidVelocity = (
      definitionVersion !== RESEARCH_TREND_VELOCITY_VERSION
      || !RESEARCH_TREND_VELOCITY_MODES.has(comparisonMode)
      || !snapshotId
      || previousSnapshotId === false
      || !runId
      || !observedAt
      || previousObservedAt === false
      || categoryId === false
      || !RESEARCH_CATEGORY_STRUCTURAL_SIGNAL_PATTERN.test(signalKey)
      || !canonicalLabel
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(eventHash)
      || !RESEARCH_STAGE_CONTROL_HASH_PATTERN.test(lineageHash)
      || !Number.isSafeInteger(currentSourceCount)
      || !Number.isSafeInteger(previousSourceCount)
      || !Number.isSafeInteger(currentTotalSourceCount)
      || previousTotalSourceCount === false
      || !Number.isSafeInteger(currentSupportBps)
      || previousSupportBps === false
      || supportDeltaBps === false
      || supportVelocity === false
      || elapsedSeconds === false
      || currentSourceCount > currentTotalSourceCount
      || (previousTotalSourceCount !== null
        && previousSourceCount > previousTotalSourceCount)
      || (currentPresent ? currentSourceCount < 1 : currentSourceCount !== 0)
      || (previousPresent ? previousSourceCount < 1 : previousSourceCount !== 0)
      || currentSupportBps !== expectedCurrentSupport
      || (previousTotalSourceCount === null
        ? previousSupportBps !== null
        : previousSupportBps !== expectedPreviousSupport)
      || !modeShapeValid
      || !directionShapeValid
      || (previousObservedAt !== null
        && Math.abs(observedElapsed - elapsedSeconds) > 1)
      || !RESEARCH_TREND_SUPPORT_STATES.has(supportState)
      || supportState !== expectedSupportState
      || typeof claimAllowed !== "boolean"
      || claimAllowed !== (comparisonMode === "comparable")
      || supportDeltaBps !== expectedDelta
      || (expectedVelocity === null
        ? supportVelocity !== null
        : Math.abs(supportVelocity - expectedVelocity) > 0.005)
      || recommendedNextStep !== expectedNextStep
    );
    if (invalidVelocity) {
      velocityContractValid = false;
      return null;
    }
    return {
      snapshotId,
      previousSnapshotId,
      runId,
      observedAt,
      previousObservedAt,
      categoryId,
      signalKey,
      canonicalLabel,
      definitionVersion,
      comparisonMode,
      currentPresent,
      previousPresent,
      currentDirection,
      previousDirection,
      currentSourceCount,
      previousSourceCount,
      currentTotalSourceCount,
      previousTotalSourceCount,
      currentSupportBps,
      previousSupportBps,
      supportDeltaBps,
      supportVelocityBpsPer30d: supportVelocity,
      elapsedSeconds,
      lineageHash,
      eventHash,
      claimAllowed,
      supportState,
      recommendedNextStep,
    };
  }).filter(Boolean);
  if (
    arrayValue(rawVelocity).length > 24
    || new Set(parsedTrendVelocity.map((event) => event.eventHash)).size
      !== parsedTrendVelocity.length
    || new Set(parsedTrendVelocity.map(
      (event) => `${event.snapshotId}:${event.signalKey}`,
    )).size !== parsedTrendVelocity.length
  ) velocityContractValid = false;
  const trendVelocity = velocityContractValid ? parsedTrendVelocity : [];
  const velocityGuidancePresent = Object.keys(velocityGuidanceSource).length > 0;
  const velocityGuidanceStatus = String(
    velocityGuidanceSource.status || "",
  ).trim();
  const velocityGuidanceNextStep = String(
    velocityGuidanceSource.recommended_next_step
      || velocityGuidanceSource.recommendedNextStep
      || "",
  ).trim();
  const velocityGuidanceMetric = String(
    velocityGuidanceSource.metric_kind
      || velocityGuidanceSource.metricKind
      || "",
  ).trim();
  const velocityGuidanceInterval = field(
    velocityGuidanceSource,
    "minimum_interval_hours",
    "minimumIntervalHours",
  );
  const velocityGuidanceCorrectionStage = String(
    velocityGuidanceSource.human_correction_stage
      || velocityGuidanceSource.humanCorrectionStage
      || "",
  ).trim();
  const velocityGuidanceActions = new Set([
    "collect_next_approved_snapshot",
    "review_support_velocity",
    "establish_new_category_baseline",
    "review_trends_stage",
    "wait_for_minimum_interval",
  ]);
  if (hasRawVelocity && (
    !velocityContractValid
    || !velocityGuidancePresent
    || velocityGuidanceMetric
      !== "approved_structural_evidence_support_not_performance"
    || velocityGuidanceInterval !== 72
    || velocityGuidanceCorrectionStage !== "trends"
    || velocityGuidanceStatus !== velocityGuidanceNextStep
    || !velocityGuidanceActions.has(velocityGuidanceStatus)
  )) contractValid = false;
  return {
    available: contractValid,
    canResolve: contractValid
      && (source.can_resolve === true || source.canResolve === true),
    productId: String(source.product_id || source.productId || "").trim(),
    currentBinding: bindingSource ? {
      bindingId: String(bindingSource.binding_id || bindingSource.bindingId || "").trim(),
      bindingVersion: boundedCount(
        bindingSource.binding_version ?? bindingSource.bindingVersion,
        0,
      ),
      categoryId: String(
        bindingSource.category_key || bindingSource.category_id || bindingSource.categoryId || "",
      ).trim(),
      canonicalName: String(bindingSource.canonical_name || bindingSource.canonicalName || "").trim(),
      definition: String(bindingSource.definition || "").trim(),
      decisionAction: String(bindingSource.decision_action || bindingSource.decisionAction || "").trim(),
      sourceRunId: String(bindingSource.source_run_id || bindingSource.sourceRunId || "").trim(),
      sourceDraftId: String(bindingSource.source_draft_id || bindingSource.sourceDraftId || "").trim(),
      candidateHash: String(bindingSource.candidate_hash || bindingSource.candidateHash || "").trim(),
      confirmedBy: String(bindingSource.confirmed_by || bindingSource.confirmedBy || "").trim(),
      confirmedAt: String(bindingSource.confirmed_at || bindingSource.confirmedAt || "").trim(),
    } : null,
    candidate: candidateSource ? {
      runId: String(candidateSource.run_id || candidateSource.runId || "").trim(),
      draftId: String(candidateSource.draft_id || candidateSource.draftId || "").trim(),
      candidateHash: String(candidateSource.candidate_hash || candidateSource.candidateHash || "").trim(),
      categoryName: String(candidateSource.category_name || candidateSource.categoryName || "").trim(),
      definition: String(candidateSource.definition || "").trim(),
      maturity: String(candidateSource.maturity || "unknown").trim(),
    } : null,
    categories: arrayValue(source.categories).slice(0, 20)
      .map(category)
      .filter((item) => item.categoryId && item.canonicalName),
    trendTimeline: arrayValue(source.trend_timeline || source.trendTimeline).slice(0, 24)
      .map((item) => {
        const row = objectValue(item) || {};
        return {
          snapshotId: String(row.snapshot_id || row.snapshotId || "").trim(),
          runId: String(row.run_id || row.runId || "").trim(),
          observedAt: String(row.observed_at || row.observedAt || "").trim(),
          bindingId: String(row.binding_id || row.bindingId || "").trim(),
          categoryId: String(
            row.category_key || row.category_id || row.categoryId || "",
          ).trim(),
          categoryName: String(row.category_name || row.categoryName || "").trim(),
          signalKey: String(row.signal_key || row.signalKey || "").trim(),
          canonicalLabel: String(row.canonical_label || row.canonicalLabel || row.signal_key || "Сигнал").trim(),
          direction: String(row.direction || "unclear").trim(),
          previousDirection: String(row.previous_direction || row.previousDirection || "").trim(),
          confidence: normalizeConfidence(row.confidence),
          recommendedUse: String(row.recommended_use || row.recommendedUse || "monitor").trim(),
          comparisonMode: String(row.comparison_mode || row.comparisonMode || "baseline").trim(),
          directionChanged: row.direction_changed === true || row.directionChanged === true,
          potentialContradiction: row.potential_contradiction === true
            || row.potentialContradiction === true,
          sourceCount: boundedCount(row.source_count ?? row.sourceCount, 0),
        };
      }).filter((item) => item.signalKey),
    trendVelocity,
    guidance: {
      status: String(guidanceSource.status || (unavailable ? "unavailable" : "needs_research_evidence")),
      recommendedNextStep: String(
        guidanceSource.recommended_next_step
          || guidanceSource.recommendedNextStep
          || (unavailable ? "refresh_status" : "complete_product_research"),
      ),
      categoryDecisionRequiresConfirmation:
        guidanceSource.category_decision_requires_confirmation !== false
        && guidanceSource.categoryDecisionRequiresConfirmation !== false,
      paidProviderAction: guidanceSource.paid_provider_action === true
        || guidanceSource.paidProviderAction === true,
      trendVelocity: velocityGuidancePresent ? {
        status: velocityGuidanceStatus,
        recommendedNextStep: velocityGuidanceNextStep,
        metricKind: velocityGuidanceMetric,
        minimumIntervalHours: velocityGuidanceInterval,
        humanCorrectionStage: velocityGuidanceCorrectionStage,
      } : null,
    },
  };
}

export function applyResearchMarketCategoryResolution(record, raw) {
  const source = objectValue(raw?.data) || objectValue(raw) || {};
  const category = objectValue(source.category);
  const binding = objectValue(source.binding);
  if (!category || !binding) return record;
  const previous = record?.marketRegistry
    || normalizeResearchMarketRegistry({ unavailable: false });
  const categoryId = String(
    category.category_key
      || category.category_id
      || binding.category_key
      || binding.category_id
      || "",
  ).trim();
  const normalizedCategory = {
    categoryId,
    canonicalName: String(category.canonical_name || category.name || "").trim(),
    definition: String(category.definition || "").trim(),
    status: String(category.status || "active").trim(),
    aliases: stringArray(category.aliases).slice(0, 10),
    createdAt: String(category.created_at || "").trim(),
  };
  const guidanceSource = objectValue(source.guidance) || {};
  return {
    ...record,
    outcomeLearning: normalizeResearchOutcomeLearning({ scopeMissing: true }),
    outcomeScopeRegistry: normalizeResearchOutcomeScopeRegistry({
      unavailable: false,
    }),
    marketRegistry: {
      ...previous,
      available: true,
      currentBinding: {
        bindingId: String(binding.binding_id || binding.id || "").trim(),
        bindingVersion: boundedCount(
          binding.binding_version ?? binding.version,
          (previous.currentBinding?.bindingVersion || 0) + 1,
        ),
        categoryId,
        canonicalName: normalizedCategory.canonicalName,
        definition: normalizedCategory.definition,
        decisionAction: String(binding.decision_action || "").trim(),
        sourceRunId: String(binding.source_run_id || "").trim(),
        sourceDraftId: String(binding.source_draft_id || "").trim(),
        candidateHash: String(binding.candidate_hash || "").trim(),
        confirmedBy: String(binding.confirmed_by || "").trim(),
        confirmedAt: String(binding.confirmed_at || "").trim(),
      },
      categories: [
        normalizedCategory,
        ...previous.categories.filter((item) => item.categoryId !== categoryId),
      ].slice(0, 20),
      guidance: {
        status: String(guidanceSource.status || "ready"),
        recommendedNextStep: String(
          guidanceSource.recommended_next_step
            || guidanceSource.recommendedNextStep
            || "continue_with_bound_category",
        ),
        categoryDecisionRequiresConfirmation: true,
        paidProviderAction: false,
      },
    },
  };
}

function researchOutcomeHasOnlyKeys(value, allowed) {
  const source = objectValue(value);
  return Boolean(source) && Object.keys(source).every((key) => allowed.has(key));
}

function researchOutcomeUuid(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(normalized)
    ? normalized
    : "";
}

function researchYoutubeExactObject(value, keys) {
  const source = objectValue(value);
  return source
      && Object.keys(source).length === keys.length
      && keys.every((key) => Object.prototype.hasOwnProperty.call(source, key))
    ? source
    : null;
}

function researchYoutubeText(value, minimum, maximum) {
  if (typeof value !== "string" || value !== value.trim()) return "";
  if (value.length < minimum || value.length > maximum || /[\u0000-\u001f\u007f]/u.test(value)) {
    return "";
  }
  return value;
}

function researchYoutubeNullableText(value, minimum, maximum, pattern = null) {
  if (value === null) return null;
  const text = researchYoutubeText(value, minimum, maximum);
  return text && (!pattern || pattern.test(text)) ? text : false;
}

function researchYoutubeUuid(value) {
  return researchOutcomeUuid(value);
}

function researchYoutubeHash(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/u.test(value)
    ? value
    : "";
}

function researchYoutubeTimestamp(value) {
  return typeof value === "string"
      && value.length >= 20
      && value.length <= 64
      && Number.isFinite(Date.parse(value))
    ? value
    : "";
}

function researchYoutubeNullableTimestamp(value) {
  if (value === null) return null;
  return researchYoutubeTimestamp(value) || false;
}

function researchYoutubeInteger(value, minimum, maximum) {
  return Number.isSafeInteger(value) && value >= minimum && value <= maximum
    ? value
    : null;
}

function normalizeResearchYoutubeRollout(value) {
  if (value === null) return null;
  const source = researchYoutubeExactObject(value, [
    "decision_id",
    "decision",
    "canary_ingestion_id",
    "terms_version",
    "retention_days",
    "decided_at",
    "refresh_gate_open",
  ]);
  if (!source) return false;
  const decisionId = researchYoutubeUuid(source.decision_id);
  const decision = String(source.decision || "");
  const canaryIngestionId = source.canary_ingestion_id === null
    ? null
    : researchYoutubeUuid(source.canary_ingestion_id);
  const decidedAt = researchYoutubeTimestamp(source.decided_at);
  if (
    !decisionId
    || !["enable_category_refresh", "pause_category_refresh"].includes(decision)
    || (source.canary_ingestion_id !== null && !canaryIngestionId)
    || (decision === "enable_category_refresh" && !canaryIngestionId)
    || (decision === "pause_category_refresh" && canaryIngestionId !== null)
    || source.terms_version !== RESEARCH_YOUTUBE_TERMS_VERSION
    || source.retention_days !== 29
    || !decidedAt
    || typeof source.refresh_gate_open !== "boolean"
    || (decision === "pause_category_refresh" && source.refresh_gate_open)
  ) return false;
  return {
    decisionId,
    decision,
    canaryIngestionId,
    decidedAt,
    refreshGateOpen: source.refresh_gate_open,
  };
}

function normalizeResearchYoutubeQuota(value) {
  const source = researchYoutubeExactObject(value, [
    "provider_day",
    "provider_timezone",
    "resets_at",
    "organization_search_requests_started",
    "organization_search_requests_cap",
    "organization_video_detail_requests_started",
    "organization_video_detail_requests_cap",
    "monetary_cost_rub",
  ]);
  if (!source) return null;
  const searchStarted = researchYoutubeInteger(
    source.organization_search_requests_started,
    0,
    20,
  );
  const detailStarted = researchYoutubeInteger(
    source.organization_video_detail_requests_started,
    0,
    20,
  );
  const resetsAt = researchYoutubeTimestamp(source.resets_at);
  if (
    !/^\d{4}-\d{2}-\d{2}$/u.test(String(source.provider_day || ""))
    || source.provider_timezone !== "America/Los_Angeles"
    || !resetsAt
    || searchStarted === null
    || detailStarted === null
    || source.organization_search_requests_cap !== 20
    || source.organization_video_detail_requests_cap !== 20
    || source.monetary_cost_rub !== 0
  ) return null;
  return {
    providerDay: source.provider_day,
    providerTimezone: source.provider_timezone,
    resetsAt,
    organizationSearchRequestsStarted: searchStarted,
    organizationSearchRequestsCap: 20,
    organizationVideoDetailRequestsStarted: detailStarted,
    organizationVideoDetailRequestsCap: 20,
    monetaryCostRub: 0,
  };
}

function normalizeResearchYoutubeRetention(value, { latest = false } = {}) {
  const keys = [
    "retention_days",
    "provider_policy_limit_days",
    "physical_purge_schedule_ready",
    ...(latest ? ["api_data_present", "api_data_retention_expired"] : []),
  ];
  const source = researchYoutubeExactObject(value, keys);
  if (
    !source
    || source.retention_days !== 29
    || source.provider_policy_limit_days !== 30
    || typeof source.physical_purge_schedule_ready !== "boolean"
    || (latest && typeof source.api_data_present !== "boolean")
    || (latest && typeof source.api_data_retention_expired !== "boolean")
    || (latest && source.api_data_present && source.api_data_retention_expired)
  ) return null;
  return {
    retentionDays: 29,
    providerPolicyLimitDays: 30,
    physicalPurgeScheduleReady: source.physical_purge_schedule_ready,
    apiDataPresent: latest ? source.api_data_present : null,
    apiDataRetentionExpired: latest ? source.api_data_retention_expired : null,
  };
}

function normalizeResearchYoutubeOverviewGuidance(value) {
  const source = researchYoutubeExactObject(value, [
    "status",
    "recommended_next_step",
    "manual_external_action_required",
    "automatic_retry_allowed",
    "automatic_fallback_allowed",
    "generation_consumption",
  ]);
  const status = String(source?.status || "");
  const nextStep = String(source?.recommended_next_step || "");
  if (
    !source
    || !["blocked", "ready", "canary_required"].includes(status)
    || ![
      "confirm_active_market_category",
      "await_reviewed_global_youtube_rollout",
      "restore_physical_retention_schedule",
      "run_manual_canary",
      "await_reviewed_controlled_rollout",
      "review_canary_and_enable_refresh",
      "run_explicit_category_refresh",
    ].includes(nextStep)
    || source.manual_external_action_required !== true
    || source.automatic_retry_allowed !== false
    || source.automatic_fallback_allowed !== false
    || source.generation_consumption !== "forbidden"
  ) return null;
  return { status, nextStep };
}

function normalizeResearchYoutubeOverviewIngestion(value) {
  const source = researchYoutubeExactObject(value, [
    "ingestion_id",
    "status",
    "mode",
    "binding_id",
    "market_category_id",
    "query_text",
    "region_code",
    "relevance_language",
    "published_after",
    "max_results",
    "max_http_requests",
    "max_quota_units",
    "quota_units_started",
    "requested_at",
    "claimed_at",
    "lease_expires_at",
    "completed_at",
    "error_code",
  ]);
  if (!source) return null;
  const ingestionId = researchYoutubeUuid(source.ingestion_id);
  const bindingId = researchYoutubeUuid(source.binding_id);
  const marketCategoryId = researchYoutubeUuid(source.market_category_id);
  const status = String(source.status || "");
  const mode = String(source.mode || "");
  const queryText = researchYoutubeText(source.query_text, 2, 200);
  const regionCode = researchYoutubeNullableText(
    source.region_code,
    2,
    2,
    /^[A-Z]{2}$/u,
  );
  const relevanceLanguage = researchYoutubeNullableText(
    source.relevance_language,
    2,
    32,
    /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/u,
  );
  const publishedAfter = researchYoutubeNullableTimestamp(source.published_after);
  const requestedAt = researchYoutubeTimestamp(source.requested_at);
  const claimedAt = researchYoutubeNullableTimestamp(source.claimed_at);
  const leaseExpiresAt = researchYoutubeNullableTimestamp(source.lease_expires_at);
  const completedAt = researchYoutubeNullableTimestamp(source.completed_at);
  const maxResults = researchYoutubeInteger(source.max_results, 1, 25);
  const quotaUnitsStarted = researchYoutubeInteger(source.quota_units_started, 0, 2);
  const errorCode = source.error_code === null
    ? null
    : researchYoutubeText(source.error_code, 10, 80);
  if (
    !ingestionId
    || !bindingId
    || !marketCategoryId
    || !RESEARCH_YOUTUBE_STATUSES.has(status)
    || !["manual_canary", "category_refresh"].includes(mode)
    || !queryText
    || regionCode === false
    || relevanceLanguage === false
    || publishedAfter === false
    || maxResults === null
    || source.max_http_requests !== 2
    || source.max_quota_units !== 2
    || quotaUnitsStarted === null
    || !requestedAt
    || claimedAt === false
    || leaseExpiresAt === false
    || completedAt === false
    || (source.error_code !== null
      && (!errorCode || !RESEARCH_YOUTUBE_ERROR_CODES.has(errorCode)))
    || (mode === "manual_canary" && maxResults !== 1)
    || (status === "queued"
      && (claimedAt !== null || leaseExpiresAt !== null || completedAt !== null || errorCode !== null))
    || (status === "processing"
      && (!claimedAt || !leaseExpiresAt || completedAt !== null || errorCode !== null))
    || (status === "completed"
      && (!claimedAt || !leaseExpiresAt || !completedAt || errorCode !== null))
    || (status === "failed"
      && (!claimedAt || !leaseExpiresAt || !completedAt || !errorCode))
  ) return null;
  return {
    ingestionId,
    status,
    mode,
    bindingId,
    marketCategoryId,
    queryText,
    regionCode,
    relevanceLanguage,
    publishedAfter,
    maxResults,
    quotaUnitsStarted,
    requestedAt,
    claimedAt,
    leaseExpiresAt,
    completedAt,
    errorCode,
  };
}

function normalizeResearchYoutubeObservation(value) {
  const source = researchYoutubeExactObject(value, [
    "observation_id",
    "search_position",
    "video_id",
    "channel_id",
    "title",
    "channel_title",
    "youtube_category_id",
    "published_at",
    "duration_iso8601",
    "privacy_status",
    "embeddable",
    "view_count",
    "like_count",
    "comment_count",
    "observed_at",
    "retention_expires_at",
    "observation_hash",
  ]);
  if (!source) return null;
  const observationId = researchYoutubeUuid(source.observation_id);
  const searchPosition = researchYoutubeInteger(source.search_position, 1, 25);
  const videoId = typeof source.video_id === "string"
      && /^[A-Za-z0-9_-]{11}$/u.test(source.video_id)
    ? source.video_id
    : "";
  const channelId = typeof source.channel_id === "string"
      && /^UC[A-Za-z0-9_-]{22}$/u.test(source.channel_id)
    ? source.channel_id
    : "";
  const title = researchYoutubeText(source.title, 1, 300);
  const channelTitle = researchYoutubeText(source.channel_title, 1, 300);
  const youtubeCategoryId = typeof source.youtube_category_id === "string"
      && /^[0-9]{1,3}$/u.test(source.youtube_category_id)
    ? source.youtube_category_id
    : "";
  const publishedAt = researchYoutubeTimestamp(source.published_at);
  const observedAt = researchYoutubeTimestamp(source.observed_at);
  const retentionExpiresAt = researchYoutubeTimestamp(source.retention_expires_at);
  const durationIso8601 = typeof source.duration_iso8601 === "string"
      && source.duration_iso8601.length <= 40
      && /^P(?=\d|T\d)(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$/u.test(
        source.duration_iso8601,
      )
    ? source.duration_iso8601
    : "";
  const countersValid = [
    source.view_count,
    source.like_count,
    source.comment_count,
  ].every((counter) => counter === null
    || (typeof counter === "string" && /^[0-9]{1,30}$/u.test(counter)));
  if (
    !observationId
    || searchPosition === null
    || !videoId
    || !channelId
    || !title
    || !channelTitle
    || !youtubeCategoryId
    || !publishedAt
    || !observedAt
    || !retentionExpiresAt
    || !durationIso8601
    || source.privacy_status !== "public"
    || typeof source.embeddable !== "boolean"
    || !countersValid
    || !researchYoutubeHash(source.observation_hash)
    || Date.parse(publishedAt) < Date.parse("2005-02-14T00:00:00.000Z")
    || Date.parse(publishedAt) > Date.parse(observedAt) + 60_000
    || Date.parse(retentionExpiresAt) - Date.parse(observedAt) !== 29 * 86_400_000
  ) return null;
  return {
    observationId,
    searchPosition,
    videoId,
    channelId,
    title,
    channelTitle,
    youtubeCategoryId,
    publishedAt,
    durationIso8601,
    privacyStatus: "public",
    embeddable: source.embeddable,
    viewCount: source.view_count,
    likeCount: source.like_count,
    commentCount: source.comment_count,
    observedAt,
    retentionExpiresAt,
    observationHash: source.observation_hash,
  };
}

function normalizeResearchYoutubeCandidateDecision(value) {
  const source = researchYoutubeExactObject(value, [
    "decision_id",
    "ingestion_id",
    "observation_id",
    "observation_hash",
    "decision",
    "reason",
    "decided_at",
    "retention_expires_at",
    "decision_hash",
  ]);
  if (!source) return null;
  const decisionId = researchYoutubeUuid(source.decision_id);
  const ingestionId = researchYoutubeUuid(source.ingestion_id);
  const observationId = researchYoutubeUuid(source.observation_id);
  const observationHash = researchYoutubeHash(source.observation_hash);
  const decision = String(source.decision || "");
  const reason = researchYoutubeNullableText(source.reason, 3, 500);
  const decidedAt = researchYoutubeTimestamp(source.decided_at);
  const retentionExpiresAt = researchYoutubeTimestamp(source.retention_expires_at);
  const decisionHash = researchYoutubeHash(source.decision_hash);
  if (
    !decisionId
    || !ingestionId
    || !observationId
    || !observationHash
    || !["confirm_candidate", "exclude_candidate"].includes(decision)
    || reason === false
    || !decidedAt
    || !retentionExpiresAt
    || !decisionHash
    || Date.parse(retentionExpiresAt) <= Date.parse(decidedAt)
  ) return null;
  return {
    decisionId,
    ingestionId,
    observationId,
    observationHash,
    decision,
    reason,
    decidedAt,
    retentionExpiresAt,
    decisionHash,
  };
}

function normalizeResearchYoutubeTransportReceipt(value) {
  if (value === null) return null;
  const source = researchYoutubeExactObject(value, [
    "receipt_id",
    "status",
    "failure_code",
    "response_hash",
    "item_count",
    "checked_at",
  ]);
  if (!source) return false;
  const receiptId = researchYoutubeUuid(source.receipt_id);
  const status = String(source.status || "");
  const failureCode = source.failure_code === null
    ? null
    : researchYoutubeText(source.failure_code, 10, 80);
  const responseHash = source.response_hash === null
    ? null
    : researchYoutubeHash(source.response_hash);
  const itemCount = source.item_count === null
    ? null
    : researchYoutubeInteger(source.item_count, 0, 25);
  const checkedAt = researchYoutubeTimestamp(source.checked_at);
  if (
    !receiptId
    || !["ready", "degraded", "blocked", "unknown"].includes(status)
    || (source.failure_code !== null
      && (!failureCode || !RESEARCH_YOUTUBE_TRANSPORT_FAILURE_CODES.has(failureCode)))
    || (source.response_hash !== null && !responseHash)
    || (source.item_count !== null && itemCount === null)
    || !checkedAt
    || (status === "ready" && (failureCode !== null || !responseHash || itemCount === null))
    || (status !== "ready" && !failureCode)
  ) return false;
  return { receiptId, status, failureCode, responseHash, itemCount, checkedAt };
}

function normalizeResearchYoutubeTransport(value) {
  const source = researchYoutubeExactObject(value, [
    "transport_id",
    "request_ordinal",
    "request_kind",
    "quota_bucket",
    "quota_units",
    "request_hash",
    "started_at",
    "receipt",
  ]);
  if (!source) return null;
  const transportId = researchYoutubeUuid(source.transport_id);
  const requestOrdinal = researchYoutubeInteger(source.request_ordinal, 1, 2);
  const requestKind = String(source.request_kind || "");
  const quotaBucket = String(source.quota_bucket || "");
  const requestHash = researchYoutubeHash(source.request_hash);
  const startedAt = researchYoutubeTimestamp(source.started_at);
  const receipt = normalizeResearchYoutubeTransportReceipt(source.receipt);
  if (
    !transportId
    || requestOrdinal === null
    || !["search.list", "videos.list"].includes(requestKind)
    || !["search_queries", "default"].includes(quotaBucket)
    || (requestKind === "search.list" && quotaBucket !== "search_queries")
    || (requestKind === "videos.list" && quotaBucket !== "default")
    || source.quota_units !== 1
    || !requestHash
    || !startedAt
    || receipt === false
  ) return null;
  return {
    transportId,
    requestOrdinal,
    requestKind,
    quotaBucket,
    requestHash,
    startedAt,
    receipt,
  };
}

function normalizeResearchYoutubeLatestGuidance(value, status) {
  const source = researchYoutubeExactObject(value, [
    "status",
    "recommended_next_step",
    "automatic_retry_allowed",
    "automatic_fallback_allowed",
    "generation_consumption",
    "candidate_confirmation_required",
  ]);
  const nextStep = String(source?.recommended_next_step || "");
  if (
    !source
    || source.status !== status
    || ![
      "invoke_manual_youtube_ingestion",
      "wait_for_manual_ingestion_receipt",
      "inspect_transport_receipt_before_new_request",
      "review_canary_and_decide_rollout",
      "refine_query_before_next_refresh",
      "review_live_competitor_candidates",
      "request_new_ingestion_after_retention",
    ].includes(nextStep)
    || source.automatic_retry_allowed !== false
    || source.automatic_fallback_allowed !== false
    || source.generation_consumption !== "forbidden"
    || source.candidate_confirmation_required !== true
  ) return null;
  return { status, nextStep };
}

function normalizeResearchYoutubeLatestIngestion(value) {
  const source = researchYoutubeExactObject(value, [
    "id",
    "status",
    "mode",
    "run_id",
    "product_id",
    "binding_id",
    "market_category_id",
    "provider_key",
    "adapter_version",
    "query_text",
    "region_code",
    "relevance_language",
    "published_after",
    "max_results",
    "max_http_requests",
    "max_quota_units",
    "quota_units_started",
    "request_hash",
    "requested_at",
    "claimed_at",
    "lease_expires_at",
    "completed_at",
    "error_code",
    "error_message",
    "current_binding",
  ]);
  if (!source) return null;
  const id = researchYoutubeUuid(source.id);
  const runId = researchYoutubeUuid(source.run_id);
  const productId = researchYoutubeUuid(source.product_id);
  const bindingId = researchYoutubeUuid(source.binding_id);
  const marketCategoryId = researchYoutubeUuid(source.market_category_id);
  const status = String(source.status || "");
  const mode = String(source.mode || "");
  const queryText = researchYoutubeText(source.query_text, 2, 200);
  const regionCode = researchYoutubeNullableText(
    source.region_code,
    2,
    2,
    /^[A-Z]{2}$/u,
  );
  const relevanceLanguage = researchYoutubeNullableText(
    source.relevance_language,
    2,
    32,
    /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/u,
  );
  const publishedAfter = researchYoutubeNullableTimestamp(source.published_after);
  const maxResults = researchYoutubeInteger(source.max_results, 1, 25);
  const quotaUnitsStarted = researchYoutubeInteger(source.quota_units_started, 0, 2);
  const requestHash = researchYoutubeHash(source.request_hash);
  const requestedAt = researchYoutubeTimestamp(source.requested_at);
  const claimedAt = researchYoutubeNullableTimestamp(source.claimed_at);
  const leaseExpiresAt = researchYoutubeNullableTimestamp(source.lease_expires_at);
  const completedAt = researchYoutubeNullableTimestamp(source.completed_at);
  const errorCode = source.error_code === null
    ? null
    : researchYoutubeText(source.error_code, 10, 80);
  const errorMessage = source.error_message === null
    ? null
    : researchYoutubeText(source.error_message, 1, 2000);
  if (
    !id
    || !runId
    || !productId
    || !bindingId
    || !marketCategoryId
    || !RESEARCH_YOUTUBE_STATUSES.has(status)
    || !["manual_canary", "category_refresh"].includes(mode)
    || source.provider_key !== RESEARCH_YOUTUBE_PROVIDER_KEY
    || source.adapter_version !== RESEARCH_YOUTUBE_ADAPTER_VERSION
    || !queryText
    || regionCode === false
    || relevanceLanguage === false
    || publishedAfter === false
    || maxResults === null
    || source.max_http_requests !== 2
    || source.max_quota_units !== 2
    || quotaUnitsStarted === null
    || !requestHash
    || !requestedAt
    || claimedAt === false
    || leaseExpiresAt === false
    || completedAt === false
    || (source.error_code !== null
      && (!errorCode || !RESEARCH_YOUTUBE_ERROR_CODES.has(errorCode)))
    || (source.error_message !== null && !errorMessage)
    || typeof source.current_binding !== "boolean"
    || (mode === "manual_canary" && maxResults !== 1)
    || (status === "queued"
      && (claimedAt !== null || leaseExpiresAt !== null || completedAt !== null
        || errorCode !== null || errorMessage !== null))
    || (status === "processing"
      && (!claimedAt || !leaseExpiresAt || completedAt !== null
        || errorCode !== null || errorMessage !== null))
    || (status === "completed"
      && (!claimedAt || !leaseExpiresAt || !completedAt
        || errorCode !== null || errorMessage !== null))
    || (status === "failed"
      && (!claimedAt || !leaseExpiresAt || !completedAt || !errorCode || !errorMessage))
  ) return null;
  return {
    id,
    status,
    mode,
    runId,
    productId,
    bindingId,
    marketCategoryId,
    queryText,
    regionCode,
    relevanceLanguage,
    publishedAfter,
    maxResults,
    quotaUnitsStarted,
    requestHash,
    requestedAt,
    claimedAt,
    leaseExpiresAt,
    completedAt,
    errorCode,
    errorMessage,
    currentBinding: source.current_binding,
  };
}

function normalizeResearchYoutubeLatest(value, overview) {
  const source = researchYoutubeExactObject(value, [
    "ok",
    "version",
    "ingestion",
    "transports",
    "observations",
    "candidate_decisions",
    "global_rollout_state",
    "rollout",
    "quota",
    "retention",
    "guidance",
  ]);
  if (
    !source
    || source.ok !== true
    || source.version !== RESEARCH_YOUTUBE_VERSION
    || !Array.isArray(source.transports)
    || source.transports.length > 2
    || !Array.isArray(source.observations)
    || source.observations.length > 25
    || !Array.isArray(source.candidate_decisions)
    || source.candidate_decisions.length > 100
    || source.global_rollout_state !== overview.globalRolloutState
  ) return null;
  const ingestion = normalizeResearchYoutubeLatestIngestion(source.ingestion);
  const rollout = normalizeResearchYoutubeRollout(source.rollout);
  const quota = normalizeResearchYoutubeQuota(source.quota);
  const retention = normalizeResearchYoutubeRetention(source.retention, {
    latest: true,
  });
  if (
    !ingestion
    || rollout === false
    || !quota
    || !retention
    || ingestion.id !== overview.ingestions[0]?.ingestionId
    || ingestion.runId !== overview.runId
    || ingestion.productId !== overview.productId
  ) return null;
  const guidance = normalizeResearchYoutubeLatestGuidance(
    source.guidance,
    ingestion.status,
  );
  if (
    !guidance
    || (guidance.nextStep === "request_new_ingestion_after_retention")
      !== retention.apiDataRetentionExpired
  ) return null;
  const transports = source.transports.map(normalizeResearchYoutubeTransport);
  if (
    transports.some((item) => item === null)
    || new Set(transports.map((item) => item.transportId)).size !== transports.length
    || new Set(transports.map((item) => item.requestOrdinal)).size !== transports.length
  ) return null;
  transports.sort((left, right) => left.requestOrdinal - right.requestOrdinal);
  if (
    transports.some((item, index) => item.requestOrdinal !== index + 1)
    || transports.some((item) =>
      (item.requestOrdinal === 1 && item.requestKind !== "search.list")
      || (item.requestOrdinal === 2 && item.requestKind !== "videos.list")
    )
  ) {
    return null;
  }
  const observations = source.observations.map(normalizeResearchYoutubeObservation);
  if (
    observations.some((item) => item === null)
    || new Set(observations.map((item) => item.observationId)).size !== observations.length
    || new Set(observations.map((item) => item.videoId)).size !== observations.length
    || new Set(observations.map((item) => item.searchPosition)).size !== observations.length
    || observations.some((item) => item.searchPosition > ingestion.maxResults)
  ) return null;
  observations.sort((left, right) => left.searchPosition - right.searchPosition);
  if (ingestion.status === "completed") {
    if (retention.apiDataRetentionExpired) {
      if (
        retention.apiDataPresent
        || transports.some((item) => item.receipt !== null)
        || observations.length !== 0
        || source.candidate_decisions.length !== 0
      ) return null;
    } else if (!retention.apiDataPresent) {
      return null;
    } else {
      const searchReceipt = transports[0]?.receipt;
      const detailReceipt = transports[1]?.receipt;
      const manualCanary = ingestion.mode === "manual_canary";
      if (
        searchReceipt?.status !== "ready"
        || (searchReceipt.itemCount === 0
          && (transports.length !== 1 || observations.length !== 0))
        || (searchReceipt.itemCount > 0
          && (transports.length !== 2 || detailReceipt?.status !== "ready"
            || (manualCanary
              ? detailReceipt.itemCount !== 1
              : detailReceipt.itemCount !== observations.length)
            || detailReceipt.itemCount > searchReceipt.itemCount))
        || (manualCanary
          && (searchReceipt.itemCount !== 1 || detailReceipt?.itemCount !== 1
            || observations.length !== 0))
      ) return null;
    }
  }
  const candidateDecisions = source.candidate_decisions.map(
    normalizeResearchYoutubeCandidateDecision,
  );
  if (
    candidateDecisions.some((item) => item === null)
    || new Set(candidateDecisions.map((item) => item.decisionId)).size
      !== candidateDecisions.length
    || candidateDecisions.some((decision) => {
      const observation = observations.find((item) =>
        item.observationId === decision.observationId
      );
      return decision.ingestionId !== ingestion.id
        || !observation
        || observation.observationHash !== decision.observationHash;
    })
  ) return null;
  return {
    ingestion,
    transports,
    observations,
    candidateDecisions,
    rollout,
    quota,
    retention,
    guidance,
  };
}

function researchYoutubeUnavailableModel({ invalid = false } = {}) {
  const result = {
    kind: "research-youtube-control-v1",
    available: false,
    invalid,
    latestAvailable: false,
    latestInvalid: false,
    runId: "",
    productId: "",
    globalRolloutState: "disabled",
    currentBinding: null,
    canRequestCanary: false,
    canRequestRefresh: false,
    canDecideRollout: false,
    canDecideCandidates: false,
    ingestions: [],
    rollout: null,
    quota: null,
    retention: null,
    guidance: null,
    latest: null,
  };
  RESEARCH_YOUTUBE_NORMALIZED_VALUES.add(result);
  return result;
}

export function normalizeResearchYoutube(value) {
  const envelope = researchYoutubeExactObject(value, [
    "overview",
    "overviewUnavailable",
    "latest",
    "latestUnavailable",
  ]);
  if (
    !envelope
    || typeof envelope.overviewUnavailable !== "boolean"
    || typeof envelope.latestUnavailable !== "boolean"
  ) return researchYoutubeUnavailableModel({ invalid: true });
  if (envelope.overviewUnavailable) {
    return researchYoutubeUnavailableModel({ invalid: envelope.overview !== null });
  }
  const source = researchYoutubeExactObject(envelope.overview, [
    "ok",
    "version",
    "run_id",
    "product_id",
    "global_rollout_state",
    "current_binding",
    "can_request_canary",
    "can_request_refresh",
    "can_decide_rollout",
    "can_decide_candidates",
    "ingestions",
    "rollout",
    "quota",
    "retention",
    "guidance",
  ]);
  if (
    !source
    || source.ok !== true
    || source.version !== RESEARCH_YOUTUBE_VERSION
    || !researchYoutubeUuid(source.run_id)
    || !researchYoutubeUuid(source.product_id)
    || !RESEARCH_YOUTUBE_GLOBAL_STATES.has(source.global_rollout_state)
    || typeof source.can_request_canary !== "boolean"
    || typeof source.can_request_refresh !== "boolean"
    || typeof source.can_decide_rollout !== "boolean"
    || typeof source.can_decide_candidates !== "boolean"
    || !Array.isArray(source.ingestions)
    || source.ingestions.length > 20
  ) return researchYoutubeUnavailableModel({ invalid: true });
  let currentBinding = null;
  if (source.current_binding !== null) {
    const binding = researchYoutubeExactObject(source.current_binding, [
      "binding_id",
      "binding_version",
      "market_category_id",
      "canonical_name",
      "category_status",
    ]);
    if (
      !binding
      || !researchYoutubeUuid(binding.binding_id)
      || researchYoutubeInteger(binding.binding_version, 1, Number.MAX_SAFE_INTEGER) === null
      || !researchYoutubeUuid(binding.market_category_id)
      || !researchYoutubeText(binding.canonical_name, 1, 160)
      || !["active", "retired"].includes(binding.category_status)
    ) return researchYoutubeUnavailableModel({ invalid: true });
    currentBinding = {
      bindingId: binding.binding_id.toLowerCase(),
      bindingVersion: binding.binding_version,
      marketCategoryId: binding.market_category_id.toLowerCase(),
      canonicalName: binding.canonical_name,
      categoryStatus: binding.category_status,
    };
  }
  const ingestions = source.ingestions.map(normalizeResearchYoutubeOverviewIngestion);
  const rollout = normalizeResearchYoutubeRollout(source.rollout);
  const quota = normalizeResearchYoutubeQuota(source.quota);
  const retention = normalizeResearchYoutubeRetention(source.retention);
  const guidance = normalizeResearchYoutubeOverviewGuidance(source.guidance);
  if (
    ingestions.some((item) => item === null)
    || new Set(ingestions.map((item) => item.ingestionId)).size !== ingestions.length
    || rollout === false
    || !quota
    || !retention
    || !guidance
    || (source.can_request_canary
      && (!currentBinding || currentBinding.categoryStatus !== "active"
        || !retention.physicalPurgeScheduleReady
        || !["canary_enabled", "controlled_rollout"].includes(source.global_rollout_state)))
    || (source.can_request_refresh
      && (!currentBinding || currentBinding.categoryStatus !== "active"
        || !rollout?.refreshGateOpen))
    || (source.can_decide_rollout && source.global_rollout_state !== "controlled_rollout")
  ) return researchYoutubeUnavailableModel({ invalid: true });
  const overview = {
    runId: source.run_id.toLowerCase(),
    productId: source.product_id.toLowerCase(),
    globalRolloutState: source.global_rollout_state,
    currentBinding,
    canRequestCanary: source.can_request_canary,
    canRequestRefresh: source.can_request_refresh,
    canDecideRollout: source.can_decide_rollout,
    canDecideCandidates: source.can_decide_candidates,
    ingestions,
    rollout,
    quota,
    retention,
    guidance,
  };
  let latest = null;
  let latestInvalid = envelope.latestUnavailable && envelope.latest !== null;
  if (!envelope.latestUnavailable && envelope.latest !== null) {
    latest = normalizeResearchYoutubeLatest(envelope.latest, overview);
    latestInvalid = latest === null;
  } else if (
    !envelope.latestUnavailable
    && envelope.latest === null
    && ingestions.length > 0
  ) {
    latestInvalid = true;
  }
  const result = {
    kind: "research-youtube-control-v1",
    available: true,
    invalid: false,
    latestAvailable: latest !== null,
    latestInvalid,
    ...overview,
    latest,
  };
  RESEARCH_YOUTUBE_NORMALIZED_VALUES.add(result);
  return result;
}

function normalizeResearchOutcomeScope(value) {
  const source = objectValue(value) || {};
  const marketCategoryId = researchOutcomeUuid(
    source.market_category_id || source.marketCategoryId,
  );
  const platform = String(source.platform || "").trim().toLowerCase();
  const model = String(source.model || "").trim().toLowerCase();
  return marketCategoryId
      && RESEARCH_OUTCOME_PLATFORMS.has(platform)
      && RESEARCH_OUTCOME_MODELS.has(model)
    ? { marketCategoryId, platform, model }
    : null;
}

function researchOutcomeScopeMatches(left, right) {
  return Boolean(
    left
    && right
    && left.marketCategoryId === right.marketCategoryId
    && left.platform === right.platform
    && left.model === right.model,
  );
}

function researchOutcomeScopeKey(scope) {
  return scope
    ? `${scope.marketCategoryId}:${scope.platform}:${scope.model}`
    : "";
}

export function normalizeResearchOutcomeScopeRegistry(value) {
  const envelope = objectValue(value) || {};
  const unavailable = envelope.unavailable === true;
  const source = objectValue(envelope.registry);
  const empty = {
    available: false,
    unavailable,
    runId: "",
    productId: "",
    scopes: [],
    selectedScope: null,
    selectedScopeKey: "",
    suggestedScopeKey: "",
    truncated: false,
    selectionRequired: false,
    guidance: {
      status: unavailable ? "unavailable" : "no_exact_scopes",
      recommendedNextStep: unavailable
        ? "refresh_scope_registry"
        : "approve_scenario_and_confirm_exact_market_category",
    },
  };
  if (unavailable || !source) return empty;
  const topAllowed = new Set([
    "ok", "version", "run_id", "product_id", "limit",
    "returned_scope_count", "truncated", "suggested_scope_key", "scopes",
    "guidance",
  ]);
  const itemAllowed = new Set([
    "scope_key", "scope", "market_category", "sources",
    "approved_scenario_positions", "approved_recommended",
    "current_product_category", "current_memory_state",
    "current_memory_version", "latest_activity_at",
  ]);
  const categoryAllowed = new Set([
    "market_category_id", "canonical_name", "status",
  ]);
  const sourcesAllowed = new Set([
    "approved_scenario", "lineage", "candidate", "memory",
  ]);
  const guidanceAllowed = new Set([
    "status", "recommended_next_step", "selection_required",
    "automatic_selection", "read_only", "provider_action", "spend_action",
    "generation_action", "publication_action",
  ]);
  const guidance = objectValue(source.guidance);
  if (
    source.ok !== true
    || source.version !== RESEARCH_OUTCOME_SCOPE_REGISTRY_VERSION
    || !researchOutcomeHasOnlyKeys(source, topAllowed)
    || Object.keys(source).length !== topAllowed.size
    || !researchOutcomeUuid(source.run_id)
    || !researchOutcomeUuid(source.product_id)
    || !Number.isInteger(source.limit)
    || source.limit < 1
    || source.limit > 50
    || typeof source.truncated !== "boolean"
    || !Array.isArray(source.scopes)
    || source.scopes.length > 50
    || source.returned_scope_count !== source.scopes.length
    || !researchOutcomeHasOnlyKeys(guidance, guidanceAllowed)
    || Object.keys(guidance).length !== guidanceAllowed.size
    || typeof guidance.status !== "string"
    || typeof guidance.recommended_next_step !== "string"
    || typeof guidance.selection_required !== "boolean"
    || guidance.automatic_selection !== false
    || guidance.read_only !== true
    || guidance.provider_action !== false
    || guidance.spend_action !== false
    || guidance.generation_action !== false
    || guidance.publication_action !== false
  ) return empty;
  const seen = new Set();
  const scopes = [];
  for (const raw of source.scopes) {
    const item = objectValue(raw);
    const scope = normalizeResearchOutcomeScope(item?.scope);
    const category = objectValue(item?.market_category);
    const sources = objectValue(item?.sources);
    const scopeKey = researchOutcomeScopeKey(scope);
    const categoryId = researchOutcomeUuid(category?.market_category_id);
    const positions = arrayValue(item?.approved_scenario_positions).map(Number);
    if (
      !item
      || !researchOutcomeHasOnlyKeys(item, itemAllowed)
      || Object.keys(item).length !== itemAllowed.size
      || !scope
      || item.scope_key !== scopeKey
      || seen.has(scopeKey)
      || !researchOutcomeHasOnlyKeys(category, categoryAllowed)
      || Object.keys(category).length !== categoryAllowed.size
      || categoryId !== scope.marketCategoryId
      || typeof category.canonical_name !== "string"
      || !category.canonical_name.trim()
      || !["active", "retired"].includes(String(category.status || ""))
      || !researchOutcomeHasOnlyKeys(sources, sourcesAllowed)
      || Object.keys(sources).length !== sourcesAllowed.size
      || Object.values(sources).some((flag) => typeof flag !== "boolean")
      || positions.some((position) => !Number.isInteger(position) || position < 1 || position > 3)
      || new Set(positions).size !== positions.length
      || typeof item.approved_recommended !== "boolean"
      || typeof item.current_product_category !== "boolean"
      || (item.current_memory_state !== null
        && !["active", "inactive"].includes(String(item.current_memory_state)))
      || (item.current_memory_version !== null
        && (!Number.isInteger(item.current_memory_version)
          || item.current_memory_version < 1
          || item.current_memory_version > 100000))
    ) return empty;
    seen.add(scopeKey);
    scopes.push({
      key: scopeKey,
      scope,
      category: {
        id: categoryId,
        canonicalName: category.canonical_name.trim(),
        status: String(category.status),
      },
      sources: { ...sources },
      approvedScenarioPositions: positions,
      approvedRecommended: item.approved_recommended,
      currentProductCategory: item.current_product_category,
      currentMemoryState: item.current_memory_state,
      currentMemoryVersion: item.current_memory_version,
      latestActivityAt: String(item.latest_activity_at || ""),
    });
  }
  const selectedCandidate = normalizeResearchOutcomeScope(envelope.selectedScope);
  const selectedScopeKey = researchOutcomeScopeKey(selectedCandidate);
  const selectedEntry = scopes.find((item) => item.key === selectedScopeKey) || null;
  const suggestedScopeKey = typeof source.suggested_scope_key === "string"
      && seen.has(source.suggested_scope_key)
    ? source.suggested_scope_key
    : "";
  const selectionRequired = source.truncated || scopes.length > 1;
  if (
    guidance.selection_required !== selectionRequired
    || (scopes.length === 1 && !source.truncated && !selectedEntry)
    || (scopes.length !== 1 && selectedEntry && !selectedCandidate)
  ) return empty;
  return {
    available: true,
    unavailable: false,
    runId: researchOutcomeUuid(source.run_id),
    productId: researchOutcomeUuid(source.product_id),
    scopes,
    selectedScope: selectedEntry?.scope || null,
    selectedScopeKey: selectedEntry?.key || "",
    suggestedScopeKey,
    truncated: source.truncated,
    selectionRequired,
    guidance: {
      status: guidance.status,
      recommendedNextStep: guidance.recommended_next_step,
    },
  };
}

function normalizeResearchOutcomeGuidance(value) {
  const source = objectValue(value) || {};
  const allowed = new Set([
    "status",
    "recommended_next_step",
    "reason_codes",
    "automatic_activation",
    "advisory_only",
    "generation_consumption",
    "provider_action",
    "spend_action",
    "generation_action",
    "publication_action",
  ]);
  if (
    !researchOutcomeHasOnlyKeys(source, allowed)
    || typeof source.status !== "string"
    || typeof source.recommended_next_step !== "string"
    || source.automatic_activation !== false
    || source.advisory_only !== true
    || source.generation_consumption !== "not_wired"
    || source.provider_action !== false
    || source.spend_action !== false
    || source.generation_action !== false
    || source.publication_action !== false
  ) return null;
  return {
    status: source.status.trim(),
    recommendedNextStep: source.recommended_next_step.trim(),
    reasonCodes: stringArray(source.reason_codes).slice(0, 12),
    automaticActivation: false,
    advisoryOnly: true,
    generationConsumption: "not_wired",
    providerAction: false,
    spendAction: false,
    generationAction: false,
    publicationAction: false,
  };
}

function normalizeResearchOutcomeCandidate(value, expectedScope) {
  const source = objectValue(value) || {};
  const allowed = new Set([
    "candidate_id",
    "candidate_version",
    "candidate_hash",
    "candidate_kind",
    "scope",
    "candidate_payload",
    "effectiveness_evidence",
    "guard_evidence",
    "status",
    "created_at",
    "advisory_only",
    "generation_consumption",
  ]);
  const payload = objectValue(source.candidate_payload) || {};
  const effectiveness = objectValue(source.effectiveness_evidence) || {};
  const guard = objectValue(source.guard_evidence) || {};
  const preferred = objectValue(effectiveness.preferred) || {};
  const comparator = objectValue(effectiveness.comparator) || {};
  const deltas = objectValue(effectiveness.absolute_deltas) || {};
  const scope = normalizeResearchOutcomeScope(source.scope);
  const payloadScope = normalizeResearchOutcomeScope(payload.scope);
  const candidateId = researchOutcomeUuid(source.candidate_id);
  const candidateHash = String(source.candidate_hash || "").trim().toLowerCase();
  const candidateVersion = Number(source.candidate_version);
  const preferredAngle = String(payload.preferred_creative_angle || "").trim();
  const avoidAngle = payload.avoid_creative_angle === null
    ? ""
    : String(payload.avoid_creative_angle || "").trim();
  const comparatorAngle = String(comparator.creative_angle || "").trim();
  const status = String(source.status || "").trim();
  const payloadAllowed = new Set([
    "schema_version",
    "candidate_kind",
    "scope",
    "preferred_creative_angle",
    "avoid_creative_angle",
    "ruleset_version",
  ]);
  const effectivenessAllowed = new Set([
    "eligible_outcome_count",
    "eligible_angle_count",
    "minimum_outcomes_per_angle",
    "minimum_views_per_outcome",
    "minimum_maturity_hours",
    "maximum_outcomes_considered",
    "overlapping_product_count",
    "preferred",
    "comparator",
    "absolute_deltas",
    "views_are_not_a_rank_signal",
  ]);
  const guardAllowed = new Set([
    "qa_approved_outcome_count",
    "first_party_metric_outcome_count",
    "distinct_product_count",
    "market_category_exact",
    "tenant_scope_exact",
    "raw_competitor_content_excluded",
    "raw_prompt_caption_url_excluded",
    "automatic_activation",
    "advisory_only",
    "generation_consumption",
  ]);
  if (
    !researchOutcomeHasOnlyKeys(source, allowed)
    || !researchOutcomeHasOnlyKeys(payload, payloadAllowed)
    || !researchOutcomeHasOnlyKeys(effectiveness, effectivenessAllowed)
    || !researchOutcomeHasOnlyKeys(guard, guardAllowed)
    || !candidateId
    || !/^[0-9a-f]{64}$/u.test(candidateHash)
    || !Number.isInteger(candidateVersion)
    || candidateVersion < 1
    || candidateVersion > 100000
    || source.candidate_kind !== "creative_angle_preference"
    || payload.schema_version !== "research-outcome-learning-v1"
    || payload.candidate_kind !== "creative_angle_preference"
    || !researchOutcomeScopeMatches(scope, payloadScope)
    || !researchOutcomeScopeMatches(scope, expectedScope)
    || !RESEARCH_OUTCOME_ANGLES.has(preferredAngle)
    || (avoidAngle && !RESEARCH_OUTCOME_ANGLES.has(avoidAngle))
    || !RESEARCH_OUTCOME_ANGLES.has(comparatorAngle)
    || !["pending", "active", "rejected", "quarantined", "deactivated", "superseded"].includes(status)
    || source.advisory_only !== true
    || source.generation_consumption !== "not_wired"
    || effectiveness.views_are_not_a_rank_signal !== true
    || guard.market_category_exact !== true
    || guard.tenant_scope_exact !== true
    || guard.raw_competitor_content_excluded !== true
    || guard.raw_prompt_caption_url_excluded !== true
    || guard.automatic_activation !== false
    || guard.advisory_only !== true
    || guard.generation_consumption !== "not_wired"
  ) return null;
  const metric = (item, key) => {
    const number = Number(item?.[key]);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  };
  return {
    id: candidateId,
    version: candidateVersion,
    hash: candidateHash,
    kind: "creative_angle_preference",
    status,
    scope,
    preferredAngle,
    avoidAngle,
    comparatorAngle,
    eligibleOutcomeCount: boundedCount(effectiveness.eligible_outcome_count, 0),
    eligibleAngleCount: boundedCount(effectiveness.eligible_angle_count, 0),
    distinctProductCount: boundedCount(guard.distinct_product_count, 0),
    minimumOutcomesPerAngle: boundedCount(effectiveness.minimum_outcomes_per_angle, 0),
    minimumViewsPerOutcome: boundedCount(effectiveness.minimum_views_per_outcome, 0),
    minimumMaturityHours: boundedCount(effectiveness.minimum_maturity_hours, 0),
    maximumOutcomesConsidered: boundedCount(effectiveness.maximum_outcomes_considered, 0),
    overlappingProductCount: boundedCount(effectiveness.overlapping_product_count, 0),
    preferred: {
      outcomeCount: boundedCount(preferred.outcome_count, 0),
      meanCtr: metric(preferred, "mean_ctr"),
      meanOrderRate: metric(preferred, "mean_order_rate"),
      totalOrders: boundedCount(preferred.total_orders, 0),
      totalRevenueMinor: boundedCount(preferred.total_revenue_minor, 0),
    },
    comparator: {
      outcomeCount: boundedCount(comparator.outcome_count, 0),
      meanCtr: metric(comparator, "mean_ctr"),
      meanOrderRate: metric(comparator, "mean_order_rate"),
      totalOrders: boundedCount(comparator.total_orders, 0),
      totalRevenueMinor: boundedCount(comparator.total_revenue_minor, 0),
    },
    deltas: {
      meanCtr: Number.isFinite(Number(deltas.mean_ctr)) ? Number(deltas.mean_ctr) : 0,
      meanOrderRate: Number.isFinite(Number(deltas.mean_order_rate))
        ? Number(deltas.mean_order_rate)
        : 0,
    },
    createdAt: String(source.created_at || "").trim(),
    advisoryOnly: true,
    generationConsumption: "not_wired",
  };
}

export function normalizeResearchOutcomeLearning(value) {
  const envelope = objectValue(value) || {};
  const source = objectValue(envelope.control) || {};
  const scopeMissing = envelope.scopeMissing === true;
  const requestedScope = normalizeResearchOutcomeScope(envelope.scope);
  const empty = {
    available: false,
    unavailable: envelope.unavailable === true,
    scopeMissing,
    canDecide: false,
    canRefresh: false,
    scope: requestedScope,
    marketCategory: null,
    capturedOutcomeCount: 0,
    candidates: [],
    currentMemory: null,
    rollbackTarget: null,
    decisionHistory: [],
    guidance: {
      status: scopeMissing ? "scope_missing" : "unavailable",
      recommendedNextStep: scopeMissing
        ? "confirm_market_category_and_exact_scenario"
        : "refresh_status",
      reasonCodes: [],
      advisoryOnly: true,
      generationConsumption: "not_wired",
    },
  };
  const topAllowed = new Set([
    "ok",
    "version",
    "can_decide",
    "can_refresh",
    "market_category",
    "scope",
    "captured_current_outcome_count",
    "candidates",
    "current_memory",
    "rollback_target",
    "decision_history",
    "guidance",
  ]);
  const scope = normalizeResearchOutcomeScope(source.scope);
  const guidance = normalizeResearchOutcomeGuidance(source.guidance);
  const category = objectValue(source.market_category) || {};
  const candidates = arrayValue(source.candidates).slice(0, 20)
    .map((item) => normalizeResearchOutcomeCandidate(item, scope));
  const current = objectValue(source.current_memory);
  const rollback = objectValue(source.rollback_target);
  const history = arrayValue(source.decision_history).slice(0, 20).map((item) => {
    const row = objectValue(item) || {};
    const allowed = new Set([
      "action",
      "candidate_id",
      "candidate_version",
      "candidate_hash",
      "expected_scope_version",
      "rollback_memory_version_id",
      "reason",
      "decided_at",
    ]);
    const action = String(row.action || "").trim();
    const candidateId = researchOutcomeUuid(row.candidate_id);
    const candidateHash = String(row.candidate_hash || "").trim().toLowerCase();
    const version = Number(row.candidate_version);
    const expectedScopeVersion = Number(row.expected_scope_version);
    const reason = String(row.reason || "").replace(/\s+/gu, " ").trim();
    if (
      !researchOutcomeHasOnlyKeys(row, allowed)
      || !["activate", "reject", "quarantine", "deactivate", "revert"].includes(action)
      || !candidateId
      || !/^[0-9a-f]{64}$/u.test(candidateHash)
      || !Number.isInteger(version)
      || !Number.isInteger(expectedScopeVersion)
      || reason.length < 3
      || reason.length > 500
    ) return null;
    return {
      action,
      candidateId,
      candidateVersion: version,
      candidateHash,
      expectedScopeVersion,
      rollbackMemoryVersionId: researchOutcomeUuid(row.rollback_memory_version_id),
      reason,
      decidedAt: String(row.decided_at || "").trim(),
    };
  });
  const categoryId = researchOutcomeUuid(category.market_category_id);
  const contractValid = envelope.unavailable !== true
    && !scopeMissing
    && source.ok === true
    && source.version === RESEARCH_OUTCOME_VERSION
    && researchOutcomeHasOnlyKeys(source, topAllowed)
    && typeof source.can_decide === "boolean"
    && typeof source.can_refresh === "boolean"
    && scope
    && researchOutcomeScopeMatches(scope, requestedScope)
    && categoryId === scope.marketCategoryId
    && typeof category.canonical_name === "string"
    && Array.isArray(source.candidates)
    && candidates.length === source.candidates.slice(0, 20).length
    && candidates.every(Boolean)
    && Array.isArray(source.decision_history)
    && history.length === source.decision_history.slice(0, 20).length
    && history.every(Boolean)
    && guidance;
  if (!contractValid) return empty;
  const candidateById = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  let currentMemory = null;
  if (current) {
    const allowed = new Set([
      "memory_version_id",
      "memory_version",
      "state",
      "action",
      "candidate_id",
      "candidate",
      "previous_memory_version_id",
      "rollback_target_memory_version_id",
      "created_at",
      "advisory_only",
      "generation_consumption",
    ]);
    const currentId = researchOutcomeUuid(current.memory_version_id);
    const memoryVersion = Number(current.memory_version);
    const state = String(current.state || "").trim();
    const action = String(current.action || "").trim();
    const candidateId = researchOutcomeUuid(current.candidate_id);
    const previousMemoryVersionId = researchOutcomeUuid(current.previous_memory_version_id);
    const rollbackTargetMemoryVersionId = researchOutcomeUuid(
      current.rollback_target_memory_version_id,
    );
    const embedded = current.candidate
      ? normalizeResearchOutcomeCandidate(current.candidate, scope)
      : null;
    if (
      !researchOutcomeHasOnlyKeys(current, allowed)
      || !currentId
      || !Number.isInteger(memoryVersion)
      || memoryVersion < 1
      || !["active", "inactive"].includes(state)
      || !["activate", "deactivate", "revert"].includes(action)
      || current.advisory_only !== true
      || current.generation_consumption !== "not_wired"
      || (memoryVersion === 1 ? Boolean(previousMemoryVersionId) : !previousMemoryVersionId)
      || (action === "activate" ? Boolean(rollbackTargetMemoryVersionId) : !rollbackTargetMemoryVersionId)
      || (state === "active" && (
        !["activate", "revert"].includes(action)
        || !candidateId
        || !embedded
        || embedded.id !== candidateId
        || embedded.status !== "active"
      ))
      || (state === "inactive" && (action !== "deactivate" || candidateId || embedded))
    ) return empty;
    currentMemory = {
      id: currentId,
      version: memoryVersion,
      state,
      action,
      candidateId,
      candidate: embedded || candidateById.get(candidateId) || null,
      previousMemoryVersionId,
      rollbackTargetMemoryVersionId,
      createdAt: String(current.created_at || "").trim(),
      advisoryOnly: true,
      generationConsumption: "not_wired",
    };
  }
  let rollbackTarget = null;
  if (rollback) {
    const allowed = new Set([
      "memory_version_id",
      "memory_version",
      "candidate_id",
      "candidate_hash",
      "candidate_version",
      "candidate",
    ]);
    const memoryId = researchOutcomeUuid(rollback.memory_version_id);
    const candidateId = researchOutcomeUuid(rollback.candidate_id);
    const candidateHash = String(rollback.candidate_hash || "").trim().toLowerCase();
    const memoryVersion = Number(rollback.memory_version);
    const candidateVersion = Number(rollback.candidate_version);
    const rollbackCandidate = normalizeResearchOutcomeCandidate(
      rollback.candidate,
      scope,
    );
    if (
      !researchOutcomeHasOnlyKeys(rollback, allowed)
      || !memoryId
      || !candidateId
      || !/^[0-9a-f]{64}$/u.test(candidateHash)
      || !Number.isInteger(memoryVersion)
      || !Number.isInteger(candidateVersion)
      || !rollbackCandidate
      || rollbackCandidate.id !== candidateId
      || rollbackCandidate.hash !== candidateHash
      || rollbackCandidate.version !== candidateVersion
    ) return empty;
    rollbackTarget = {
      memoryId,
      memoryVersion,
      candidateId,
      candidateHash,
      candidateVersion,
      candidate: rollbackCandidate,
    };
  }
  return {
    available: true,
    unavailable: false,
    scopeMissing: false,
    canDecide: source.can_decide === true,
    canRefresh: source.can_refresh === true,
    scope,
    marketCategory: {
      id: categoryId,
      canonicalName: String(category.canonical_name).trim(),
      status: String(category.status || "active").trim(),
    },
    capturedOutcomeCount: boundedCount(source.captured_current_outcome_count, 0),
    candidates,
    currentMemory,
    rollbackTarget,
    decisionHistory: history,
    guidance,
  };
}

export function applyResearchOutcomeLearningMutation(record, raw) {
  const source = objectValue(raw?.data) || objectValue(raw) || {};
  const previous = record?.outcomeLearning;
  if (!previous?.available || source.ok !== true || source.version !== RESEARCH_OUTCOME_VERSION) {
    return record;
  }
  const guidance = normalizeResearchOutcomeGuidance(source.guidance);
  if (!guidance) return record;
  if (Object.prototype.hasOwnProperty.call(source, "candidate_created")) {
    const candidate = source.candidate
      ? normalizeResearchOutcomeCandidate(source.candidate, previous.scope)
      : null;
    if (source.candidate && !candidate) return record;
    const candidates = candidate
      ? [candidate, ...previous.candidates.filter((item) => item.id !== candidate.id)].slice(0, 20)
      : previous.candidates;
    return {
      ...record,
      outcomeLearning: {
        ...previous,
        lastRefreshEligibleOutcomeCount: boundedCount(
          source.eligible_outcome_count,
          previous.lastRefreshEligibleOutcomeCount || 0,
        ),
        candidates,
        guidance,
      },
    };
  }
  const action = String(source.action || "").trim();
  const decision = objectValue(source.decision) || {};
  const candidateId = researchOutcomeUuid(decision.candidate_id);
  const candidate = [
    ...previous.candidates,
    previous.currentMemory?.candidate,
    previous.rollbackTarget?.candidate,
  ].filter(Boolean).find((item) => item.id === candidateId);
  const expectedScopeVersion = Number(decision.expected_scope_version);
  const decisionRollbackMemoryVersionId = researchOutcomeUuid(
    decision.rollback_memory_version_id,
  );
  if (
    !["activate", "reject", "quarantine", "deactivate", "revert"].includes(action)
    || !candidate
    || Number(decision.candidate_version) !== candidate.version
    || String(decision.candidate_hash || "").trim().toLowerCase() !== candidate.hash
    || !Number.isInteger(expectedScopeVersion)
    || expectedScopeVersion < 0
    || (action === "revert" ? !decisionRollbackMemoryVersionId : Boolean(decisionRollbackMemoryVersionId))
  ) return record;
  const statusByAction = {
    activate: "active",
    reject: "rejected",
    quarantine: "quarantined",
    deactivate: "deactivated",
    revert: "active",
  };
  const candidates = previous.candidates.map((item) => {
    if (item.id === candidateId) return { ...item, status: statusByAction[action] };
    if (["activate", "revert"].includes(action) && item.status === "active") {
      return { ...item, status: "superseded" };
    }
    return item;
  });
  const memory = objectValue(source.memory);
  const memoryAction = ["activate", "deactivate", "revert"].includes(action);
  if (
    !Object.prototype.hasOwnProperty.call(source, "memory")
    || (!memoryAction && source.memory !== null)
    || (memoryAction && !memory)
  ) return record;
  let currentMemory = previous.currentMemory;
  if (memoryAction) {
    const memoryId = researchOutcomeUuid(memory?.memory_version_id);
    const memoryVersion = Number(memory?.memory_version);
    const state = String(memory?.state || "").trim();
    const memoryCandidateId = researchOutcomeUuid(memory?.candidate_id);
    const previousMemoryVersionId = researchOutcomeUuid(memory?.previous_memory_version_id);
    const rollbackTargetMemoryVersionId = researchOutcomeUuid(
      memory?.rollback_target_memory_version_id,
    );
    const expectedState = action === "deactivate" ? "inactive" : "active";
    if (
      !memoryId
      || !Number.isInteger(memoryVersion)
      || memoryVersion !== expectedScopeVersion + 1
      || state !== expectedState
      || memory?.advisory_only !== true
      || memory?.generation_consumption !== "not_wired"
      || (memoryVersion === 1 ? Boolean(previousMemoryVersionId) : !previousMemoryVersionId)
      || (action === "activate" ? Boolean(rollbackTargetMemoryVersionId) : !rollbackTargetMemoryVersionId)
      || (state === "active" ? memoryCandidateId !== candidateId : Boolean(memoryCandidateId))
    ) return record;
    currentMemory = {
      id: memoryId,
      version: memoryVersion,
      state,
      action,
      candidateId: state === "active" ? candidateId : "",
      candidate: state === "active" ? { ...candidate, status: "active" } : null,
      previousMemoryVersionId,
      rollbackTargetMemoryVersionId,
      createdAt: "",
      advisoryOnly: true,
      generationConsumption: "not_wired",
    };
  }
  return {
    ...record,
    outcomeLearning: {
      ...previous,
      candidates,
      currentMemory,
      rollbackTarget: null,
      guidance,
    },
  };
}

export function normalizeResearchWatchlist(value) {
  const monitor = objectValue(value) || {};
  const unavailable = monitor.unavailable === true;
  const source = objectValue(monitor.watchlist);
  const snapshots = arrayValue(monitor.snapshots).slice(0, 8).map((item) => {
    const snapshot = objectValue(item) || {};
    return {
      id: String(snapshot.id || ""),
      runId: String(snapshot.run_id || snapshot.runId || ""),
      draftId: String(snapshot.draft_id || snapshot.draftId || ""),
      observedAt: String(
        snapshot.observed_at || snapshot.observedAt || snapshot.created_at || "",
      ),
      sourceCount: boundedCount(
        snapshot.source_count ?? snapshot.sourceCount,
        stringArray(snapshot.source_ids || snapshot.sourceIds).length,
      ),
      contentHash: String(snapshot.content_hash || snapshot.contentHash || ""),
      change: normalizeResearchWatchlistChange(
        snapshot.change_set || snapshot.changeSet,
      ),
    };
  }).sort((left, right) => right.observedAt.localeCompare(left.observedAt));
  const proposalSource = objectValue(monitor.proposal);
  const proposalStatus = String(proposalSource?.status || "open").toLowerCase();
  const proposal = proposalSource && proposalStatus === "open"
    ? {
      id: String(proposalSource.id || ""),
      reasonCode: String(
        proposalSource.reason_code || proposalSource.reasonCode || "refresh_due",
      ),
      status: proposalStatus,
      dueAt: String(proposalSource.due_at || proposalSource.dueAt || ""),
      createdAt: String(proposalSource.created_at || proposalSource.createdAt || ""),
    }
    : null;
  const enabled = source !== null && Boolean(source.id);
  const status = enabled
    ? String(source.status || "active").toLowerCase()
    : "not_enabled";
  const freshnessSource = objectValue(source?.freshness) || {};
  const freshnessCandidate = String(
    freshnessSource.status
      || source?.freshness_status
      || (typeof source?.freshness === "string" ? source.freshness : "")
      || (status === "paused" ? "paused" : enabled ? "needs_baseline" : "not_enabled"),
  ).toLowerCase();
  const freshness = [
    "not_enabled",
    "needs_baseline",
    "fresh",
    "due",
    "stale",
    "paused",
  ].includes(freshnessCandidate)
    ? freshnessCandidate
    : "needs_baseline";
  const guidanceSource = objectValue(monitor.guidance) || {};
  const guidanceDefaults = unavailable
    ? {
      status: "needs_more_evidence",
      code: "watchlist_status_unavailable",
      title: "Наблюдение временно недоступно",
      reason: "Основной результат сохранён, но сервер не подтвердил состояние мониторинга. Обновите статус перед решением.",
      actions: ["Обновить статус исследования"],
    }
    : !enabled
      ? {
        status: "needs_user_decision",
        code: "watchlist_not_enabled",
        title: "Зафиксировать базовый снимок",
        reason: "После подключения система будет сравнивать только утверждённые исследования этого товара.",
        actions: ["Выбрать интервал наблюдения", "Подключить мониторинг"],
      }
      : {
        status: freshness === "fresh" ? "ready" : "needs_user_decision",
        code: `watchlist_${freshness}`,
        title: freshness === "fresh" ? "Продолжать наблюдение" : "Проверить свежесть данных",
        reason: "Изменения — это гипотезы по снимкам источников, а не доказанные победители.",
        actions: freshness === "fresh" ? ["Дождаться следующей проверки"] : ["Решить, нужен ли новый анализ"],
      };
  const actionCode = String(
    guidanceSource.code
      || guidanceSource.recommended_next_step
      || guidanceSource.recommendedNextStep
      || guidanceDefaults.code,
  );
  const localizedGuidance = researchWatchlistGuidanceCopy(actionCode);
  const guidance = {
    status: String(guidanceSource.status || guidanceDefaults.status),
    code: actionCode,
    title: String(
      guidanceSource.title
        || localizedGuidance?.title
        || guidanceDefaults.title,
    ),
    reason: String(
      localizedGuidance?.reason || guidanceSource.reason || guidanceDefaults.reason,
    ),
    actions: stringArray(
      guidanceSource.suggested_actions
        || guidanceSource.suggestedActions
        || guidanceSource.actions,
    ).slice(0, 8),
    paidRefreshRequiresConfirmation: true,
  };
  if (!guidance.actions.length) {
    guidance.actions = localizedGuidance?.actions || guidanceDefaults.actions;
  }
  return {
    available: !unavailable,
    enabled,
    id: String(source?.id || ""),
    status,
    freshness: unavailable ? "unavailable" : freshness,
    intervalDays: boundedInteger(
      source?.refresh_interval_days ?? source?.refreshIntervalDays,
      3,
      90,
      14,
    ),
    categoryKey: String(source?.category_key || source?.categoryKey || ""),
    lastSnapshotAt: String(
      source?.last_snapshot_at
        || source?.lastSnapshotAt
        || freshnessSource.observed_at
        || freshnessSource.observedAt
        || "",
    ),
    nextRefreshAt: String(source?.next_refresh_at || source?.nextRefreshAt || ""),
    snapshotCount: boundedCount(
      source?.snapshot_count ?? source?.snapshotCount,
      snapshots.length,
    ),
    version: boundedCount(source?.version, 0),
    snapshots,
    proposal,
    guidance,
  };
}

function normalizeResearchWatchlistChange(value) {
  const source = objectValue(value) || {};
  const categorySource = objectValue(source.category) || {};
  const competitorSource = objectValue(source.competitors) || {};
  const trendSource = objectValue(source.trends) || {};
  const names = (candidate) => arrayValue(candidate).map((item) => {
    const row = objectValue(item);
    return String(row?.name || row?.signal || row?.value || item || "").trim();
  }).filter(Boolean).slice(0, 20);
  const directionChanges = arrayValue(
    source.direction_changes
      || source.directionChanges
      || trendSource.direction_changes
      || trendSource.directionChanges,
  ).map((item) => {
    const row = objectValue(item) || {};
    return {
      signal: String(row.signal || row.name || "Сигнал").trim(),
      from: String(row.from || row.previous || row.old_direction || "unclear").trim(),
      to: String(row.to || row.current || row.new_direction || "unclear").trim(),
      contradiction: row.contradiction === true,
    };
  }).slice(0, 20);
  const explicitContradictions = names(
    source.contradictions
      || source.direction_contradictions
      || trendSource.direction_contradictions
      || trendSource.directionContradictions,
  );
  const contradictionCount = boundedCount(
    source.contradiction_count
      ?? source.contradictionCount
      ?? trendSource.contradiction_count
      ?? trendSource.contradictionCount,
    explicitContradictions.length
      + directionChanges.filter((item) => item.contradiction).length,
  );
  return {
    baseline: source.baseline === true || source.is_baseline === true,
    comparisonMode: String(
      source.comparison_mode
        || source.comparisonMode
        || trendSource.comparison_mode
        || trendSource.comparisonMode
        || "legacy",
    ),
    material: source.has_material_change === true
      || source.has_changes === true
      || source.material === true,
    categoryChanged: source.category_changed === true
      || source.categoryChanged === true
      || categorySource.changed === true,
    competitorsAdded: names(
      source.competitors_added
        || source.competitorsAdded
        || competitorSource.added_names
        || competitorSource.addedNames,
    ),
    competitorsRemoved: names(
      source.competitors_removed
        || source.competitorsRemoved
        || competitorSource.removed_names
        || competitorSource.removedNames,
    ),
    competitorsChanged: names(
      source.competitors_changed
        || source.competitorsChanged
        || competitorSource.changed_names
        || competitorSource.changedNames,
    ),
    trendsAdded: names(
      source.trend_signals_added
        || source.trends_added
        || source.trendsAdded
        || trendSource.added_signals
        || trendSource.addedSignals,
    ),
    trendsRemoved: names(
      source.trend_signals_removed
        || source.trends_removed
        || source.trendsRemoved
        || trendSource.removed_signals
        || trendSource.removedSignals,
    ),
    trendsChanged: names(
      source.trend_signals_changed
        || source.trends_changed
        || source.trendsChanged
        || trendSource.changed_signals
        || trendSource.changedSignals,
    ),
    directionChanges,
    contradictions: explicitContradictions,
    contradictionCount,
  };
}

function researchWatchlistGuidanceCopy(code) {
  return {
    enable_watchlist: {
      title: "Зафиксировать базовый снимок",
      reason: "Подключите наблюдение, чтобы сравнивать следующие утверждённые исследования того же товара.",
      actions: ["Выбрать интервал", "Подключить наблюдение"],
    },
    review_change_set: {
      title: "Разобрать противоречие",
      reason: "Последний снимок развернул направление одного из трендовых сигналов. Проверьте источники до следующего теста.",
      actions: ["Сравнить два последних снимка", "Зафиксировать решение человека"],
    },
    resume_when_ready: {
      title: "Решить, когда возобновить наблюдение",
      reason: "Предложения свежести поставлены на паузу, но история утверждённых снимков сохранена.",
      actions: ["Выбрать новый интервал", "Возобновить наблюдение"],
    },
    confirm_paid_refresh: {
      title: "Решить, нужен ли свежий анализ",
      reason: "Срок проверки наступил. Новый платный анализ начнётся только после подтверждения пользователя.",
      actions: ["Проверить вводные", "При необходимости открыть новую форму"],
    },
    await_refresh_proposal: {
      title: "Дождаться предложения обновить данные",
      reason: "Утверждённый снимок устарел; фоновый контур может только создать бесплатное предложение, но не запуск исследования.",
      actions: ["Обновить статус"],
    },
    continue_with_approved_research: {
      title: "Продолжать наблюдение",
      reason: "Последний утверждённый снимок ещё актуален. Изменения по-прежнему считаются гипотезами.",
      actions: ["Дождаться следующего срока проверки"],
    },
    approve_research_v2: {
      title: "Сначала утвердить исследование v2",
      reason: "Свежесть можно считать только от результата, который проверил и утвердил человек.",
      actions: ["Проверить доказательства", "Утвердить корректную версию"],
    },
  }[String(code || "")] || null;
}

function normalizeStageCorrections(value) {
  const source = objectValue(value) || {};
  return {
    sources: String(source.sources || "").trim(),
    category: String(source.category || "").trim(),
    competitors: String(source.competitors || "").trim(),
    trends: String(source.trends || "").trim(),
    strategy: String(source.strategy || "").trim(),
  };
}

function normalizeHumanResearchDecision(value) {
  const source = objectValue(value) || {};
  return {
    guidanceStatus: String(
      source.guidance_status || source.guidanceStatus || "",
    ).trim(),
    coldStartOverride: source.cold_start_override === true
      || source.coldStartOverride === true,
    strategy: String(source.strategy || "").trim(),
  };
}

function researchGapOverrideMarkup({ guidance, approved, humanResearchDecision }) {
  const stored = approved
    && humanResearchDecision.coldStartOverride === true
    && humanResearchDecision.guidanceStatus === guidance.status
    && Boolean(humanResearchDecision.strategy);
  if (approved && !stored) {
    return `<label class="check-row product-research-guidance-override"><input type="checkbox" name="research_gap_override_ack" disabled /><span><strong>Подтверждение cold start не зафиксировано</strong><br /><small>Это ТЗ было утверждено без сохранённого решения по пробелам исследования. Не считайте конкурентов или тренды подтверждёнными; для следующей версии зафиксируйте стратегию и явное подтверждение.</small></span></label>`;
  }
  const checked = stored ? "checked disabled" : "";
  const title = stored
    ? "Осознанный cold start подтверждён"
    : "Продолжить несмотря на пробелы исследования";
  const detail = stored
    ? "Сохранённое решение пользователя связано с этим статусом исследования. Задачи считаются ограниченным тестом, а не подтверждённой рыночной стратегией."
    : guidance.status === "needs_user_decision"
      ? "Сначала зафиксируйте своё решение в поле ИИ-наставника выше. Задачи будут созданы как ограниченный тест, а не как подтверждённая рыночная стратегия."
      : "Подтвердите осознанный cold start: неподтверждённые конкуренты и тренды не считаются фактами или победителями.";
  return `<label class="check-row product-research-guidance-override"><input type="checkbox" name="research_gap_override_ack" ${checked} /><span><strong>${title}</strong><br /><small>${detail}</small></span></label>`;
}

function normalizeScenarios(value) {
  const source = arrayValue(value);
  return [0, 1, 2].map((index) => {
    const item = objectValue(source[index]) || {};
    const script = String(
      item.script
        || item.spoken_script
        || item.voiceover
        || item.text
        || "",
    );
    const providerGenerationMode = normalizeGenerationMode(
      item.recommended_generation_mode
        || item.generation_mode
        || item.generationMode,
    );
    const spokenWords = script.match(
      /[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu,
    )?.length || 0;
    const durationFallback = providerGenerationMode === "real_seedance"
      && (spokenWords < 1 || spokenWords > 22);
    return {
      position: index + 1,
      title: String(item.title || item.name || `Сценарий ${index + 1}`),
      platform: normalizePlatform(item.platform),
      generationMode: durationFallback
        ? "real_gen4"
        : providerGenerationMode,
      generationModeReason: (
        durationFallback
          ? `Реплика содержит ${spokenWords} слов и не помещается в лимит 22 слов для 8 секунд; выбран визуальный ролик без речи.`
          : String(
            item.generation_mode_reason
              || item.generationModeReason
              || "",
          )
      ).replace(/\s+/gu, " ").trim().slice(0, 400),
      hook: String(item.hook || ""),
      script,
      shotList: formatShotList(item.shot_list || item.shotList || item.shots),
      taskTitle: String(item.task_title || item.taskTitle || item.title || `Снять сценарий ${index + 1}`),
      assigneeId: String(item.assignee_id || item.assigneeId || ""),
    };
  });
}

function normalizeSources(value) {
  return arrayValue(value).slice(0, 30).map((item, index) => {
    const source = objectValue(item) || {};
    const metadata = objectValue(source.metadata) || {};
    return {
      id: String(source.id || ""),
      modelId: String(
        metadata.model_source_id || source.model_source_id || source.modelId || "",
      ).trim(),
      title: String(source.title || source.name || `Источник ${index + 1}`),
      url: safeHttpsUrl(source.url || source.source_url || source.href),
      kind: String(source.kind || source.type || source.source_type || "public"),
      claim: String(source.claim || source.fact || source.finding || source.summary || formatExtractedFacts(source.extracted_facts)),
      excerpt: String(source.excerpt || source.note || ""),
      publisher: String(metadata.publisher || source.publisher || "").trim(),
      publishedAt: String(source.published_at || source.publishedAt || "").trim(),
      fetchedAt: String(
        source.fetched_at || source.accessed_at || source.fetchedAt || "",
      ).trim(),
      providerCitationVerified: metadata.provider_citation_verified === true,
      verified: source.verified === true || source.confidence === "high" || ["first_party", "official"].includes(source.trust_level),
    };
  });
}

function normalizeFactors(value) {
  const sourceValue = objectValue(value);
  const list = sourceValue
    ? [
        ...arrayValue(sourceValue.strengths).map((item) => ({ label: item, impact: 1 })),
        ...arrayValue(sourceValue.risks).map((item) => ({ label: item, impact: -1 })),
      ]
    : arrayValue(value);
  return list.slice(0, 12).map((item) => {
    if (typeof item === "string") return { label: item, detail: "", impact: 1 };
    const source = objectValue(item) || {};
    return {
      label: String(source.label || source.title || source.factor || "Фактор"),
      detail: String(source.detail || source.description || source.reason || ""),
      impact: Number(source.impact ?? source.weight ?? (source.kind === "risk" ? -1 : 1)) || 0,
    };
  });
}

function researchMediaMarkup(item, selectedMediaIds = new Set()) {
  const id = String(item.id || item.media_id || "");
  const label = String(item.title || item.filename || item.name || item.sku || "Фото товара");
  const preview = safeHttpsUrl(item.signed_url || item.preview_url || item.url);
  const duplicateIds = Array.isArray(item.duplicate_media_ids)
    ? item.duplicate_media_ids.map(String)
    : [];
  const selected = id && (
    selectedMediaIds.has(id)
    || duplicateIds.some((duplicateId) => selectedMediaIds.has(duplicateId))
  );
  const duplicateCount = productResearchMediaDuplicateCount(
    item.duplicate_count,
  );
  const kindLabel = String(item.kind || "Фото-исходник");
  const duplicateLabel = duplicateCount > 1
    ? ` · ${duplicateCount} одинаковых файлов объединены`
    : "";
  return `<label class="product-research-media-option">
    <input type="checkbox" name="source_media_ids" value="${escapeHtml(id)}" ${selected ? "checked" : ""} ${id ? "" : "disabled"} />
    <span class="product-research-media-thumb">${preview ? `<img src="${escapeHtml(preview)}" alt="" loading="lazy" />` : `<i aria-hidden="true">▧</i>`}</span>
    <span><strong>${escapeHtml(label)}</strong><small>${escapeHtml(String(item.sku || kindLabel))}${escapeHtml(duplicateLabel)}</small></span>
  </label>`;
}

function sourceMarkupItem(source) {
  const kind = source.kind === "provided" ? "Дано заказчиком" : source.verified ? "Подтверждено источником" : "Публичный источник";
  const provenance = [
    source.publisher ? `Заявленный издатель: ${source.publisher}` : "",
    source.publishedAt
      ? `Дата страницы (извлечена ИИ): ${source.publishedAt.slice(0, 10)}`
      : "Дата публикации не подтверждена",
    source.fetchedAt ? `Проверено: ${source.fetchedAt.slice(0, 10)}` : "",
    source.providerCitationVerified ? "URL подтверждён поисковым провайдером" : "",
  ].filter(Boolean).join(" · ");
  return `<article class="product-research-source">
    <div><span class="badge">${escapeHtml(kind)}</span>${source.url ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">Открыть источник <span aria-hidden="true">↗</span></a>` : ""}</div>
    <h3>${escapeHtml(source.title)}</h3>
    <p>${escapeHtml(source.claim || source.excerpt || "Источник добавлен, но подтверждённый вывод не указан.")}</p>
    ${source.claim && source.excerpt ? `<small>${escapeHtml(source.excerpt)}</small>` : ""}
    ${provenance ? `<small class="product-research-source-provenance">${escapeHtml(provenance)}</small>` : ""}
  </article>`;
}

function researchYoutubeDateTimeLabel(value, timeZone = undefined) {
  const timestamp = researchYoutubeTimestamp(value);
  if (!timestamp) return "не зафиксировано";
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
      ...(timeZone ? { timeZone } : {}),
    }).format(new Date(timestamp));
  } catch {
    return timestamp;
  }
}

function researchYoutubeGlobalStateLabel(value) {
  return ({
    disabled: "Глобально отключён",
    canary_enabled: "Разрешены ручные canary",
    controlled_rollout: "Контролируемый rollout",
    emergency_paused: "Экстренно приостановлен",
  })[value] || "Состояние не подтверждено";
}

function researchYoutubeStatusLabel(value) {
  return ({
    queued: "Ожидает ручного запуска",
    processing: "Выполняется без автоповтора",
    completed: "Завершён",
    failed: "Завершён с ошибкой",
  })[value] || "Статус не подтверждён";
}

function researchYoutubeGuidanceLabel(value) {
  return ({
    confirm_active_market_category: "Сначала подтвердите активную рыночную категорию.",
    await_reviewed_global_youtube_rollout: "Нужен проверенный глобальный допуск YouTube API.",
    restore_physical_retention_schedule: "Сначала восстановите подтверждённое физическое удаление API-данных.",
    run_manual_canary: "Запустите один ручной canary и проверьте квитанции.",
    await_reviewed_controlled_rollout: "Дождитесь проверенного controlled rollout.",
    review_canary_and_enable_refresh: "Владелец должен проверить свежий canary и отдельно включить refresh.",
    run_explicit_category_refresh: "Можно запросить только явный ручной refresh этой категории.",
    invoke_manual_youtube_ingestion: "Запуск создан, но внешний вызов должен быть выполнен вручную.",
    wait_for_manual_ingestion_receipt: "Дождитесь квитанции текущего ручного вызова; не повторяйте его автоматически.",
    inspect_transport_receipt_before_new_request: "Проверьте квитанцию ошибки до нового ручного запроса.",
    review_canary_and_decide_rollout: "Проверьте canary перед решением о rollout.",
    refine_query_before_next_refresh: "Уточните запрос перед отдельным следующим refresh.",
    review_live_competitor_candidates: "Проверьте каждого кандидата отдельно и примите временное решение.",
    request_new_ingestion_after_retention: "API-доказательства прошлого запуска удалены по сроку хранения. Создайте новый ручной canary или refresh.",
  })[value] || "Действие не подтверждено сервером.";
}

function researchYoutubePolicyLinksMarkup() {
  return `<nav class="product-research-youtube-policy-links" aria-label="Правила использования YouTube API">
    <a href="https://www.youtube.com/t/terms" target="_blank" rel="noopener noreferrer">Условия YouTube <span aria-hidden="true">↗</span></a>
    <a href="https://developers.google.com/youtube/terms/api-services-terms-of-service" target="_blank" rel="noopener noreferrer">Условия YouTube API Services <span aria-hidden="true">↗</span></a>
    <a href="https://developers.google.com/youtube/terms/developer-policies" target="_blank" rel="noopener noreferrer">Политики YouTube API <span aria-hidden="true">↗</span></a>
    <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Политика конфиденциальности Google <span aria-hidden="true">↗</span></a>
  </nav>`;
}

function researchYoutubeRequestMarkup(control, { saving = false } = {}) {
  const activeIngestion = ["queued", "processing"].includes(
    control.latest?.ingestion?.status,
  );
  const latestUnconfirmed = control.ingestions.length > 0
    && !control.latestAvailable;
  const mode = activeIngestion || latestUnconfirmed
    ? ""
    : control.canRequestRefresh
      ? "category_refresh"
      : control.canRequestCanary
        ? "manual_canary"
        : "";
  if (!mode) {
    const gateMessage = activeIngestion
      ? researchYoutubeGuidanceLabel(control.latest?.guidance?.nextStep)
      : latestUnconfirmed
        ? "Сначала восстановите точный статус последнего ingestion и его квитанции; новый внешний запрос не создаётся."
        : researchYoutubeGuidanceLabel(control.guidance?.nextStep);
    return `<div class="product-research-youtube-gate" role="note">
      <strong>Новый внешний запрос сейчас закрыт</strong>
      <p>${escapeHtml(gateMessage)}</p>
    </div>`;
  }
  const canary = mode === "manual_canary";
  const phase = canary ? "youtube-canary" : "youtube-refresh";
  const disabled = saving || control.savingPhase === phase;
  const latestIngestion = control.latest?.ingestion || control.ingestions[0] || null;
  const queryText = latestIngestion?.queryText
    || control.currentBinding?.canonicalName
    || "";
  const regionCode = latestIngestion?.regionCode || "RU";
  const relevanceLanguage = latestIngestion?.relevanceLanguage || "ru";
  const maxResults = canary ? 1 : latestIngestion?.mode === "category_refresh"
    ? latestIngestion.maxResults
    : 10;
  const action = canary ? "canary" : "refresh";
  return `<form id="product-research-youtube-request-form" class="product-research-youtube-form" data-research-id="${escapeHtml(control.runId)}" data-ce-patch-key="research-youtube-${mode}:${escapeHtml(control.runId)}" data-youtube-mode="${mode}" novalidate aria-busy="${disabled ? "true" : "false"}">
    <input type="hidden" name="mode" value="${mode}" />
    <input type="hidden" name="max_http_requests" value="2" />
    <input type="hidden" name="max_quota_units" value="2" />
    <input type="hidden" name="terms_version" value="${RESEARCH_YOUTUBE_TERMS_VERSION}" />
    ${canary ? '<input type="hidden" name="max_results" value="1" />' : ""}
    <div class="product-research-youtube-form-heading">
      <div><p class="eyebrow">${canary ? "Ручная проверка · 1 результат" : "Ручной refresh · до 25 результатов"}</p><h3>${canary ? "Проверить официальный YouTube API" : "Обновить кандидатов категории"}</h3></div>
      <span class="badge">2 запроса API максимум</span>
    </div>
    <p>${canary ? "Canary делает search.list и videos.list для одного видео. Это внешний ручной вызов, а не фоновая задача." : "Refresh разрешён сервером для этой организации. Он не запускается по расписанию и не повторяется автоматически."}</p>
    <div class="form-grid-2">
      <label class="field"><span>Точный поисковый запрос *</span><input name="query_text" minlength="2" maxlength="200" required value="${escapeHtml(queryText)}" ${disabled ? "disabled" : ""} /></label>
      ${canary
        ? '<label class="field"><span>Максимум результатов</span><input value="1" readonly disabled /></label>'
        : `<label class="field"><span>Максимум результатов *</span><input name="max_results" type="number" min="1" max="25" step="1" required value="${escapeHtml(maxResults)}" ${disabled ? "disabled" : ""} /></label>`}
      <label class="field"><span>Регион</span><input name="region_code" minlength="2" maxlength="2" pattern="[A-Z]{2}" value="${escapeHtml(regionCode)}" placeholder="RU" ${disabled ? "disabled" : ""} /></label>
      <label class="field"><span>Язык релевантности</span><input name="relevance_language" minlength="2" maxlength="32" pattern="[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*" value="${escapeHtml(relevanceLanguage)}" placeholder="ru" ${disabled ? "disabled" : ""} /></label>
      <label class="field"><span>Опубликовано после</span><input name="published_after" type="datetime-local" ${disabled ? "disabled" : ""} /><small class="field-hint">Необязательно; не старше 366 дней.</small></label>
    </div>
    <div class="product-research-youtube-confirmations">
      <label class="check-row"><input type="checkbox" name="quota_ack" value="true" required ${disabled ? "disabled" : ""} /><span><strong>Подтверждаю расход квоты организации</strong><br /><small>Будет начато не больше двух внешних запросов; точное глобальное использование API здесь не показывается.</small></span></label>
      <label class="check-row"><input type="checkbox" name="no_retry_ack" value="true" required ${disabled ? "disabled" : ""} /><span><strong>Понимаю: автоматического retry и fallback нет</strong><br /><small>При неизвестном сетевом исходе сначала проверю квитанцию и не повторю вызов вслепую.</small></span></label>
      <label class="check-row"><input type="checkbox" name="terms_ack" value="true" required ${disabled ? "disabled" : ""} /><span><strong>Подтверждаю правила YouTube API и временное хранение</strong><br /><small>API-данные удаляются через 29 дней; действующая версия условий: ${RESEARCH_YOUTUBE_TERMS_VERSION}.</small></span></label>
    </div>
    <button class="btn" type="submit" data-youtube-action="${action}" ${disabled ? "disabled" : ""}>${disabled ? "Сохраняем решение…" : canary ? "Создать и вручную запустить canary" : "Создать и вручную запустить refresh"}</button>
  </form>`;
}

function researchYoutubeRolloutMarkup(control, { saving = false } = {}) {
  if (!control.canDecideRollout) return "";
  const disabled = saving || control.savingPhase === "youtube-rollout";
  const latest = control.latest;
  const canaryReady = latest?.ingestion?.mode === "manual_canary"
    && latest.ingestion.status === "completed"
    && latest.transports.length === 2
    && latest.transports[0]?.requestKind === "search.list"
    && latest.transports[0]?.receipt?.status === "ready"
    && latest.transports[0]?.receipt?.itemCount === 1
    && latest.transports[1]?.requestKind === "videos.list"
    && latest.transports[1]?.receipt?.status === "ready"
    && latest.transports[1]?.receipt?.itemCount === 1;
  const options = canaryReady
    ? `<option value="${escapeHtml(latest.ingestion.id)}">${escapeHtml(latest.ingestion.id)} · ${escapeHtml(researchYoutubeDateTimeLabel(latest.ingestion.completedAt || latest.ingestion.requestedAt))}</option>`
    : "";
  return `<form id="product-research-youtube-rollout-form" class="product-research-youtube-form product-research-youtube-rollout-form" novalidate aria-busy="${disabled ? "true" : "false"}">
    <input type="hidden" name="terms_version" value="${RESEARCH_YOUTUBE_TERMS_VERSION}" />
    <div class="product-research-youtube-form-heading"><div><p class="eyebrow">Только owner / admin</p><h3>Rollout организации</h3></div><span class="badge">${escapeHtml(control.rollout?.decision === "enable_category_refresh" ? "Refresh включён" : "Refresh закрыт")}</span></div>
    <p>Включение требует точный ID свежего завершённого canary. Пауза создаёт новую неизменяемую запись и не удаляет историю.</p>
    <label class="field"><span>Canary ingestion ID для включения</span><select name="canary_ingestion_id" ${disabled ? "disabled" : ""}><option value="">Выберите точный завершённый canary</option>${options}</select><small class="field-hint">Сервер дополнительно проверит обе квитанции и свежесть не более 24 часов.</small></label>
    <label class="field"><span>Причина решения *</span><textarea name="reason" minlength="3" maxlength="500" required placeholder="Что проверено и почему rollout можно включить или нужно приостановить" ${disabled ? "disabled" : ""}></textarea></label>
    <label class="check-row"><input type="checkbox" name="terms_ack" value="true" required ${disabled ? "disabled" : ""} /><span><strong>Подтверждаю условия ${RESEARCH_YOUTUBE_TERMS_VERSION}</strong><br /><small>Решение действует только для этой организации и не меняет глобальный допуск.</small></span></label>
    <div class="inline-actions">
      <button class="btn" type="submit" name="decision" value="enable_category_refresh" data-youtube-action="rollout" data-youtube-decision="enable_category_refresh" ${disabled || !canaryReady ? "disabled" : ""}>${disabled ? "Сохраняем…" : "Включить refresh"}</button>
      <button class="btn btn-ghost" type="submit" name="decision" value="pause_category_refresh" data-youtube-action="rollout" data-youtube-decision="pause_category_refresh" ${disabled ? "disabled" : ""}>Приостановить refresh</button>
    </div>
  </form>`;
}

function researchYoutubeRawCounterMarkup(label, value) {
  return `<div><small>${escapeHtml(label)}</small><code>${value === null ? "не возвращено API" : escapeHtml(value)}</code></div>`;
}

function researchYoutubeObservationMarkup(
  observation,
  ingestion,
  decisions,
  { canDecide = false, saving = false } = {},
) {
  const existingDecision = decisions.find((item) =>
    item.observationId === observation.observationId
      && item.observationHash === observation.observationHash
  ) || null;
  const decisionCopy = existingDecision
    ? `<div class="product-research-youtube-decision-note"><strong>${existingDecision.decision === "confirm_candidate" ? "Ранее временно подтверждён" : "Ранее временно исключён"}</strong><span>Решение хранится до ${escapeHtml(researchYoutubeDateTimeLabel(existingDecision.retentionExpiresAt))} и не используется генерацией.</span></div>`
    : "";
  const candidateForm = canDecide
    ? `<form class="product-research-youtube-candidate-form" novalidate aria-busy="${saving ? "true" : "false"}">
        <input type="hidden" name="ingestion_id" value="${escapeHtml(ingestion.id)}" />
        <input type="hidden" name="observation_id" value="${escapeHtml(observation.observationId)}" />
        <input type="hidden" name="observation_hash" value="${escapeHtml(observation.observationHash)}" />
        <label class="field"><span>Причина решения *</span><textarea name="reason" minlength="3" maxlength="500" required placeholder="Почему этот канал сопоставим или почему его нужно исключить" ${saving ? "disabled" : ""}></textarea></label>
        <label class="check-row"><input type="checkbox" name="confirmation" value="true" required ${saving ? "disabled" : ""} /><span><strong>Подтверждаю временное решение по этой записи</strong><br /><small>Оно действует только до удаления API-данных, не обучает модель и не разрешает использовать запись в генерации.</small></span></label>
        <div class="inline-actions">
          <button class="btn" type="submit" name="decision" value="confirm_candidate" data-youtube-action="candidate" data-youtube-decision="confirm_candidate" ${saving ? "disabled" : ""}>${saving ? "Сохраняем…" : "Подтвердить кандидата"}</button>
          <button class="btn btn-ghost" type="submit" name="decision" value="exclude_candidate" data-youtube-action="candidate" data-youtube-decision="exclude_candidate" ${saving ? "disabled" : ""}>Исключить кандидата</button>
        </div>
      </form>`
    : `<p class="product-research-youtube-no-decision">У вашей роли нет права принимать решение по кандидату.</p>`;
  return `<article class="product-research-youtube-observation">
    <header>
      <div><span class="badge">Позиция API ${observation.searchPosition}</span><p class="eyebrow">Публичные метаданные YouTube</p><h3>${escapeHtml(observation.title)}</h3></div>
      <a class="btn btn-secondary btn-small" href="https://www.youtube.com/watch?v=${escapeHtml(observation.videoId)}" target="_blank" rel="noopener noreferrer nofollow">Открыть на YouTube <span aria-hidden="true">↗</span></a>
    </header>
    <p class="product-research-youtube-attribution"><strong>Источник: YouTube Data API v3.</strong> Канал «${escapeHtml(observation.channelTitle)}». Запись не означает, что канал уже признан конкурентом.</p>
    <dl class="product-research-youtube-metadata">
      <div><dt>Video ID</dt><dd><code>${escapeHtml(observation.videoId)}</code></dd></div>
      <div><dt>Channel ID</dt><dd><code>${escapeHtml(observation.channelId)}</code></dd></div>
      <div><dt>Категория YouTube</dt><dd><code>${escapeHtml(observation.youtubeCategoryId)}</code></dd></div>
      <div><dt>Длительность API</dt><dd><code>${escapeHtml(observation.durationIso8601)}</code></dd></div>
      <div><dt>Публичность</dt><dd>public · ${observation.embeddable ? "встраивание разрешено" : "встраивание запрещено"}</dd></div>
      <div><dt>Опубликовано</dt><dd><time datetime="${escapeHtml(observation.publishedAt)}">${escapeHtml(researchYoutubeDateTimeLabel(observation.publishedAt))}</time></dd></div>
    </dl>
    <div class="product-research-youtube-counters" aria-label="Исходные счётчики YouTube">
      ${researchYoutubeRawCounterMarkup("viewCount · как вернул API", observation.viewCount)}
      ${researchYoutubeRawCounterMarkup("likeCount · как вернул API", observation.likeCount)}
      ${researchYoutubeRawCounterMarkup("commentCount · как вернул API", observation.commentCount)}
    </div>
    <div class="product-research-youtube-retention-line">
      <span><strong>Наблюдалось:</strong> <time datetime="${escapeHtml(observation.observedAt)}">${escapeHtml(observation.observedAt)}</time></span>
      <span><strong>Удаление не позже:</strong> <time datetime="${escapeHtml(observation.retentionExpiresAt)}">${escapeHtml(observation.retentionExpiresAt)}</time></span>
    </div>
    ${decisionCopy}
    ${candidateForm}
  </article>`;
}

function researchYoutubeLatestMarkup(control, { saving = false } = {}) {
  if (control.latestInvalid) {
    return `<div class="alert alert-danger product-research-youtube-latest-alert" role="alert"><strong>Последний ingestion отклонён проверкой интерфейса.</strong><span>Структура ответа не совпала с hardened contract. Наблюдения и действия по кандидатам скрыты.</span></div>`;
  }
  if (!control.latestAvailable) {
    return control.ingestions.length
      ? `<div class="alert alert-warning product-research-youtube-latest-alert" role="status"><strong>Статус последнего ingestion недоступен.</strong><span>Не повторяйте внешний запрос, пока не будет проверена серверная квитанция.</span></div>`
      : `<div class="product-research-youtube-empty"><strong>Ручных запусков ещё нет</strong><p>Начните с canary на одном результате. Автоматический вызов и повтор запрещены.</p></div>`;
  }
  const latest = control.latest;
  const ingestion = latest.ingestion;
  const completedCanary = ingestion.mode === "manual_canary"
    && ingestion.status === "completed";
  const apiDataExpired = ingestion.status === "completed"
    && latest.retention.apiDataRetentionExpired === true;
  const observationMarkup = apiDataExpired
    ? `<div class="product-research-youtube-empty"><strong>API-доказательства удалены по retention</strong><p>Срок хранения 29 дней завершён. Контрольная запись запуска сохранена, но старые квитанции, наблюдения и решения кандидатов не восстанавливаются; создайте новый ручной canary или refresh.</p></div>`
    : latest.observations.length
    ? `<div class="product-research-youtube-observations">${latest.observations.map((observation) => researchYoutubeObservationMarkup(
      observation,
      ingestion,
      latest.candidateDecisions,
      {
        canDecide: control.canDecideCandidates && ingestion.status === "completed",
        saving,
      },
    )).join("")}</div>`
    : completedCanary
      ? `<div class="product-research-youtube-empty"><strong>Canary подтверждён двумя ready-квитанциями</strong><p>search.list и videos.list вернули по одному элементу. Canary намеренно не сохраняет наблюдение: точный ingestion ID доступен выше для отдельного rollout-решения.</p></div>`
      : `<div class="product-research-youtube-empty"><strong>Публичные видео не сохранены</strong><p>Это не нулевой рейтинг и не вывод об отсутствии конкурентов. Проверьте статус и поисковый запрос.</p></div>`;
  return `<div class="product-research-youtube-latest">
    <div class="product-research-youtube-latest-heading">
      <div><p class="eyebrow">Последний ручной ingestion</p><h3>${escapeHtml(researchYoutubeStatusLabel(ingestion.status))}</h3><p>${escapeHtml(researchYoutubeGuidanceLabel(latest.guidance.nextStep))}</p></div>
      <div class="product-research-youtube-run-meta"><span class="badge">${ingestion.mode === "manual_canary" ? "Canary" : "Category refresh"}</span><code>${escapeHtml(ingestion.id)}</code></div>
    </div>
    <dl class="product-research-youtube-metadata product-research-youtube-run-details">
      <div><dt>Запрос</dt><dd>${escapeHtml(ingestion.queryText)}</dd></div>
      <div><dt>Запрошено</dt><dd><time datetime="${escapeHtml(ingestion.requestedAt)}">${escapeHtml(researchYoutubeDateTimeLabel(ingestion.requestedAt))}</time></dd></div>
      <div><dt>Регион / язык</dt><dd>${escapeHtml([ingestion.regionCode, ingestion.relevanceLanguage].filter(Boolean).join(" · ") || "не заданы")}</dd></div>
      <div><dt>Вызовов начато</dt><dd><code>${escapeHtml(ingestion.quotaUnitsStarted)}</code> из строгого лимита <code>2</code></dd></div>
    </dl>
    ${ingestion.errorCode ? `<div class="alert alert-danger" role="alert"><strong>${escapeHtml(ingestion.errorCode)}</strong><span>${escapeHtml(ingestion.errorMessage || "Сервер не вернул безопасное описание ошибки.")}</span></div>` : ""}
    <div class="product-research-youtube-observation-heading"><div><p class="eyebrow">Без ранжирования и производных метрик</p><h3>Индивидуальные записи в порядке search_position</h3></div><p>Счётчики показаны ровно как строки API. Интерфейс не считает суммы, средние, коэффициенты или delta.</p></div>
    ${observationMarkup}
  </div>`;
}

export function researchYoutubeMarkup(value, {
  saving = false,
  savingPhase = "",
} = {}) {
  const control = objectValue(value) && RESEARCH_YOUTUBE_NORMALIZED_VALUES.has(value)
    ? value
    : normalizeResearchYoutube(value);
  const phase = RESEARCH_YOUTUBE_SAVING_PHASES.has(String(savingPhase || ""))
    ? String(savingPhase)
    : "";
  const busy = saving || Boolean(phase);
  if (!control.available) {
    return `<section class="card product-research-youtube product-research-youtube-unavailable" aria-labelledby="product-research-youtube-title">
      <div class="card-header"><div><p class="eyebrow">Официальный YouTube Data API v3</p><h2 id="product-research-youtube-title">Live-кандидаты недоступны</h2></div><span class="badge">Fail closed</span></div>
      <div class="product-research-youtube-unavailable-body"><p>${control.invalid ? "Ответ не прошёл строгую проверку структуры. Интерфейс скрыл данные и все действия." : "Сервер не подтвердил состояние YouTube research. Основное исследование остаётся доступным."}</p>${researchYoutubePolicyLinksMarkup()}</div>
    </section>`;
  }
  const scopedControl = { ...control, savingPhase: phase };
  const quota = control.quota;
  const retention = control.retention;
  return `<section class="card product-research-youtube" aria-labelledby="product-research-youtube-title" aria-busy="${busy ? "true" : "false"}">
    <div class="card-header product-research-youtube-header">
      <div><p class="eyebrow">Официальный YouTube Data API v3</p><h2 id="product-research-youtube-title">Публичные кандидаты категории</h2><p>Это отдельный ручной контур. Он не скрейпит страницы, не скачивает видео и не передаёт результаты в генерацию.</p></div>
      <span class="badge">${escapeHtml(researchYoutubeGlobalStateLabel(control.globalRolloutState))}</span>
    </div>
    <div class="product-research-youtube-safety" role="note"><strong>Generation consumption: forbidden.</strong><span>Ни одна запись ниже не становится конкурентом, трендом или инструкцией для контента без отдельного решения человека; даже это решение временное.</span></div>
    <div class="product-research-youtube-state-grid">
      <article><small>Глобальный reviewed state</small><strong>${escapeHtml(researchYoutubeGlobalStateLabel(control.globalRolloutState))}</strong><p>Точное глобальное использование API намеренно не показывается.</p></article>
      <article><small>Retention</small><strong>${retention.retentionDays} дней из policy limit ${retention.providerPolicyLimitDays}</strong><p>${retention.physicalPurgeScheduleReady ? "Физическое удаление подтверждено." : "Физическое удаление не подтверждено; новые запросы закрыты."}</p></article>
      <article><small>Рыночная категория</small><strong>${escapeHtml(control.currentBinding?.canonicalName || "Не подтверждена")}</strong><p>${escapeHtml(researchYoutubeGuidanceLabel(control.guidance.nextStep))}</p></article>
    </div>
    <div class="product-research-youtube-quota" aria-label="Квота этой организации по Pacific Time">
      <div><small>search.list · организация</small><strong>${quota.organizationSearchRequestsStarted} / ${quota.organizationSearchRequestsCap}</strong></div>
      <div><small>videos.list · организация</small><strong>${quota.organizationVideoDetailRequestsStarted} / ${quota.organizationVideoDetailRequestsCap}</strong></div>
      <div><small>Сброс окна · PT</small><strong>${escapeHtml(researchYoutubeDateTimeLabel(quota.resetsAt, quota.providerTimezone))}</strong><code>${escapeHtml(quota.resetsAt)}</code></div>
      <p>Это локальные счётчики организации за provider day ${escapeHtml(quota.providerDay)} в America/Los_Angeles. Они не раскрывают точное глобальное использование проекта Google API.</p>
    </div>
    ${researchYoutubePolicyLinksMarkup()}
    <div class="product-research-youtube-controls">
      ${researchYoutubeRequestMarkup(scopedControl, { saving: busy })}
      ${researchYoutubeRolloutMarkup(scopedControl, { saving: busy })}
    </div>
    ${researchYoutubeLatestMarkup(control, { saving: busy || phase === "youtube-candidate" })}
  </section>`;
}

export function researchProviderControlMarkup(value, { compact = false } = {}) {
  const control = objectValue(value) && Object.prototype.hasOwnProperty.call(value, "available")
    ? value
    : normalizeResearchProviderControl({ unavailable: true });
  const runControl = control.runControl || {};
  const providerKey = runControl.attempt?.providerKey
    || runControl.authorization?.providerKey
    || "";
  const provider = control.providers.find((item) => item.providerKey === providerKey)
    || null;
  const health = provider?.health || { status: "unknown", fresh: false };
  const healthExpired = health.expiresAt
    && Number.isFinite(Date.parse(health.expiresAt))
    && Date.parse(health.expiresAt) <= Date.now();
  const healthStatus = healthExpired || (health.status === "ready" && !health.fresh)
    ? "stale"
    : health.status;
  const healthLabels = {
    ready: "провайдер ответил",
    degraded: "ответ требует проверки",
    blocked: "провайдер заблокирован",
    unknown: "результат неизвестен",
    stale: "квитанция устарела",
  };
  const failureLabels = {
    provider_outcome_unknown: "исход платной попытки неизвестен",
    provider_configuration_error: "требуется настройка или пополнение баланса OpenAI API",
    provider_authentication_failed: "провайдер отклонил авторизацию",
    provider_request_rejected: "провайдер отклонил запрос",
    provider_rate_limited: "провайдер сообщил об ограничении квоты",
    provider_unavailable: "провайдер временно недоступен",
    provider_response_invalid: "ответ не прошёл проверку структуры или источников",
  };
  const badgeLabel = !control.available
    ? "статус недоступен"
    : healthLabels[healthStatus] || "нужна проверка";
  const authorizationLabel = runControl.authorized
    && runControl.authorization?.paidAnalysisAck
    ? runControl.authorization?.kind === "legacy_pre_gate"
      ? "исторический pre-gate запуск"
      : "явно подтверждён"
    : "не подтверждён";
  const attemptLabel = runControl.attempt
    ? `план ${runControl.attempt.attemptNumber || 1} привязан`
    : "план не привязан";
  const healthDetail = !control.available
    ? "Телеметрия недоступна — состояние не подменяется догадкой."
    : health.checkedAt
      ? `${researchDateLabel(health.checkedAt)} · ${health.citationCount === null ? "число цитат не зафиксировано" : `${health.citationCount} цитат`}${health.failureCode ? ` · ${failureLabels[health.failureCode] || "зафиксирован отказ"}` : ""}`
      : "Квитанция появится только после реальной попытки анализа.";
  const responseState = control.responseState || {};
  const responseBound = responseState.bindingState === "bound";
  const responseStatusLabels = {
    queued: "принят в очередь провайдера",
    in_progress: "провайдер выполняет анализ",
    completed: "ответ провайдера готов",
    failed: "провайдер завершил с ошибкой",
    cancelled: "провайдер отменил ответ",
    incomplete: "провайдер вернул неполный ответ",
  };
  const responseStateTitle = responseBound
    ? `привязан · …${responseState.providerResponseSuffix}`
    : "не привязан";
  const responseStateDetail = responseBound
    ? `${responseStatusLabels[responseState.providerStatus] || "статус требует проверки"}${responseState.acceptedAt ? ` · принят ${researchDateLabel(responseState.acceptedAt)}` : ""}${responseState.lastCheckedAt ? ` · последний GET ${researchDateLabel(responseState.lastCheckedAt)}` : " · GET ещё не зафиксирован"}`
    : runControl.attempt
      ? "Попытка создана, но сохранённый response_id пока не подтверждён. Новый POST не запускайте."
      : "Платный запрос ещё не создавался.";
  const terminalDiagnostic = responseState.terminalDiagnostic;
  const terminalDiagnosticDetail = terminalDiagnostic
    ? `Terminal status ${terminalDiagnostic.terminalStatus}; диагностический код ${terminalDiagnostic.diagnosticCode}; тип ${terminalDiagnostic.diagnosticType}. ${terminalDiagnostic.diagnosticMessage}`
    : "";
  return `
    <section class="card product-research-control-plane${compact ? " is-compact" : ""}" aria-labelledby="product-research-provider-title" data-provider-health="${escapeHtml(control.available ? healthStatus : "unavailable")}">
      <div class="card-header">
        <div><p class="eyebrow">Контроль платного провайдера</p><h2 id="product-research-provider-title">Одна разрешённая попытка, без скрытого переключения</h2><p>Сервер связывает явное подтверждение оплаты, выбранный адаптер и квитанцию фактического ответа. Проверка статуса не создаёт новый платный запуск: она читает только уже сохранённый response_id. Повторного POST и нового списания нет.</p></div>
        <span class="badge">${escapeHtml(badgeLabel)}</span>
      </div>
      ${!control.available ? `<div class="alert alert-warning product-research-control-alert" role="status"><strong>Контур телеметрии временно недоступен.</strong><span>Сохранённый результат исследования остаётся доступен; перед новым платным запуском обновите статус.</span></div>` : ""}
      <div class="product-research-control-summary">
        <div><small>Платный анализ</small><strong>${escapeHtml(authorizationLabel)}</strong></div>
        <div><small>Адаптер</small><strong>${escapeHtml(provider?.displayName || providerKey || "не выбран")}</strong><span>${escapeHtml(provider ? `${provider.lifecycleStatus} · ${provider.rolloutStage} · ${runControl.attempt?.adapterVersion || runControl.authorization?.adapterVersion || "—"}` : "нет привязки к запуску")}</span></div>
        <div><small>Привязка попытки</small><strong>${escapeHtml(attemptLabel)}</strong><span>${escapeHtml(runControl.attempt?.model || "без модели")}</span></div>
        <div><small>Последняя квитанция провайдера в команде</small><strong>${escapeHtml(healthLabels[healthStatus] || "нет данных")}</strong><span>${escapeHtml(healthDetail)}</span></div>
        <div><small>Сохранённый ответ этого запуска</small><strong>${escapeHtml(responseStateTitle)}</strong><span>${escapeHtml(responseStateDetail)}</span></div>
        ${terminalDiagnostic ? `<div><small>Безопасная terminal-диагностика</small><strong>${escapeHtml(terminalDiagnostic.diagnosticCode)}</strong><span>${escapeHtml(terminalDiagnosticDetail)}</span></div>` : ""}
      </div>
      ${compact || !control.available ? "" : `<div class="product-research-control-note"><strong>Автоматические canary и fallback выключены.</strong><span>Новый платный POST возможен только как отдельное явно подтверждённое действие. Проверка сохранённого response_id выполняет только GET и не создаёт повторной попытки или списания.</span></div>`}
    </section>`;
}

export function researchMarketCategoryMarkup(value, {
  saving = false,
  runId = "",
} = {}) {
  const registry = objectValue(value) && Object.prototype.hasOwnProperty.call(value, "available")
    ? value
    : normalizeResearchMarketRegistry({ unavailable: true });
  const current = registry.currentBinding;
  const candidate = registry.candidate;
  const candidateHashValid = /^[0-9a-f]{64}$/u.test(candidate?.candidateHash || "");
  const alternativeCategories = registry.categories.filter((category) => (
    category.categoryId !== current?.categoryId
  ));
  const currentCategory = registry.categories.find((category) => (
    category.categoryId === current?.categoryId
  )) || null;
  const marketIdentityKey = (text) => String(text || "")
    .normalize("NFKC")
    .toLocaleLowerCase("ru-RU")
    .replace(/[\s\p{P}]+/gu, " ")
    .trim();
  const candidateIdentityKey = marketIdentityKey(candidate?.categoryName);
  const knownCurrentIdentityKeys = new Set([
    current?.canonicalName,
    ...(currentCategory?.aliases || []),
  ].map(marketIdentityKey).filter(Boolean));
  const reaffirmSuggested = Boolean(
    current && candidateIdentityKey
      && !knownCurrentIdentityKeys.has(candidateIdentityKey),
  );
  const existingAction = current ? "reclassify" : "bind_existing";
  const createAction = current ? "create_and_reclassify" : "create_and_bind";
  const guidanceLabels = {
    needs_research_evidence: "нужны данные исследования",
    needs_user_decision: "нужно подтверждение",
    ready: "категория подтверждена",
    unavailable: "статус недоступен",
  };
  const categoryOptions = alternativeCategories.map((category) => `
    <option value="${escapeHtml(category.categoryId)}">${escapeHtml(category.canonicalName)}</option>`).join("");
  const supportPoints = (basisPoints, { signed = false } = {}) => {
    const points = Number(basisPoints || 0) / 100;
    const prefix = signed && points > 0 ? "+" : "";
    return `${prefix}${points.toLocaleString("ru-RU", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 2,
    })} п.п.`;
  };
  const supportPercent = (basisPoints) => `${(
    Number(basisPoints || 0) / 100
  ).toLocaleString("ru-RU", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  })}%`;
  const velocityModeLabels = {
    baseline: "базовый снимок",
    comparable: "сопоставимо",
    category_reset: "новая категория",
    signal_new: "новый сигнал",
    signal_removed: "сигнал исчез",
    interval_too_short: "интервал < 72 ч",
  };
  const velocityCopy = (event) => {
    if (event.comparisonMode === "comparable") {
      return `Поддержка источниками: ${supportPercent(event.previousSupportBps)} → ${supportPercent(event.currentSupportBps)}; изменение ${supportPoints(event.supportDeltaBps, { signed: true })}, скорость ${supportPoints(event.supportVelocityBpsPer30d, { signed: true })} / 30 дней.`;
    }
    return ({
      baseline: "Это первая утверждённая точка. Направление ещё не вычисляется.",
      category_reset: "Граница категории изменилась. Прежние точки намеренно не продолжают новый ряд.",
      signal_new: "Сигнала не было в предыдущем утверждённом снимке. Нужна следующая точка.",
      signal_removed: "Сигнал был в предыдущем снимке, но не подтверждён в текущем. Проверьте этап «Тренды».",
      interval_too_short: "Между утверждёнными снимками меньше 72 часов — числовая скорость заблокирована.",
    })[event.comparisonMode] || "Для этого события числовая скорость не заявляется.";
  };
  const velocityTimeline = registry.trendVelocity?.length
    ? `<div class="product-research-market-timeline product-research-market-velocity">${registry.trendVelocity.slice(0, 6).map((event) => `<article data-trend-velocity-mode="${escapeHtml(event.comparisonMode)}">
        <header><strong>${escapeHtml(event.canonicalLabel)}</strong><span class="badge">${escapeHtml(velocityModeLabels[event.comparisonMode] || "без вывода")}</span></header>
        <p>${escapeHtml(velocityCopy(event))}</p>
        <small>${escapeHtml(researchDateLabel(event.previousObservedAt))} → ${escapeHtml(researchDateLabel(event.observedAt))} · ${event.currentSourceCount}/${event.currentTotalSourceCount} ист. поддерживают сигнал</small>
        <button class="btn btn-ghost btn-small" type="button" data-action="focus-research-trends-stage">Проверить или скорректировать</button>
      </article>`).join("")}</div>`
    : `<div class="product-research-empty-note"><strong>Для скорости нужны утверждённые точки</strong><p>Система начнёт считать ширину доказательной поддержки после снимка с каноническими структурными сигналами.</p></div>`;
  const timeline = registry.trendTimeline.length
    ? `<div class="product-research-market-timeline">${registry.trendTimeline.slice(0, 6).map((signal) => {
      const reset = ["canonical_reset", "category_reset"].includes(signal.comparisonMode);
      return `<article>
        <header><strong>${escapeHtml(signal.canonicalLabel)}</strong><span class="badge">${escapeHtml(reset ? "новая база" : trendDirectionLabel(signal.direction))}</span></header>
        <p>${reset
          ? "Сравнение начато заново: этот сигнал не считается продолжением прежней категории или схемы ID."
          : signal.directionChanged
            ? `${escapeHtml(trendDirectionLabel(signal.previousDirection))} → ${escapeHtml(trendDirectionLabel(signal.direction))}`
            : `Направление: ${escapeHtml(trendDirectionLabel(signal.direction))}`}</p>
        <small>${escapeHtml(researchDateLabel(signal.observedAt))} · ${signal.sourceCount} ист.${signal.potentialContradiction ? " · нужно разрешить противоречие" : ""}</small>
      </article>`;
    }).join("")}</div>`
    : `<div class="product-research-empty-note"><strong>Стабильная история ещё не накоплена</strong><p>Структурные сигналы начнут сравниваться только внутри подтверждённой рыночной категории.</p></div>`;
  const confirmationField = `
    <label class="check-row product-research-market-confirmation"><input type="checkbox" name="market_category_confirmation" required ${saving ? "disabled" : ""} /><span><strong>Подтверждаю рыночную категорию для этого товара</strong><br /><small>Это не меняет compliance-категорию, не запускает новый анализ и не обращается к платному провайдеру.</small></span></label>`;
  const reasonField = `
    <label class="field product-research-market-reason"><span>Почему это верная граница${current ? " *" : ""}</span><textarea name="reason" maxlength="500" placeholder="Что отличает категорию и почему прежняя привязка требует изменения" ${saving ? "disabled" : ""}></textarea></label>`;
  const reaffirmForm = reaffirmSuggested
    ? `<form id="product-research-market-category-reaffirm-form" class="product-research-market-choice product-research-market-category-form" data-research-id="${escapeHtml(runId)}" data-ce-patch-key="research-market-reaffirm:${escapeHtml(runId)}" novalidate>
        <input type="hidden" name="candidate_hash" value="${escapeHtml(candidate.candidateHash)}" />
        <input type="hidden" name="category_id" value="${escapeHtml(current.categoryId)}" />
        <input type="hidden" name="market_category_action" value="reaffirm" />
        <div><strong>Подтвердить как новый синоним текущей категории</strong><small>«${escapeHtml(candidate.categoryName)}» будет добавлено к «${escapeHtml(current.canonicalName)}»; история и прежние доказательства не переписываются.</small></div>
        ${reasonField}
        ${confirmationField}
        <button class="btn btn-secondary" type="submit" data-market-category-action="reaffirm" ${saving ? "disabled" : ""}>${saving ? "Сохраняем…" : "Подтвердить синоним"}</button>
      </form>`
    : "";
  const decisionForm = registry.available
    && registry.canResolve !== false
    && candidate
    && candidateHashValid
    ? `<div class="product-research-market-forms">
        ${reaffirmForm}
        <form id="product-research-market-category-existing-form" class="product-research-market-choice product-research-market-category-form" data-research-id="${escapeHtml(runId)}" data-ce-patch-key="research-market-existing:${escapeHtml(runId)}" novalidate>
          <input type="hidden" name="candidate_hash" value="${escapeHtml(candidate.candidateHash)}" />
          <input type="hidden" name="market_category_action" value="${existingAction}" />
          <div><strong>${current ? "Переклассифицировать в сохранённую категорию" : "Связать с сохранённой категорией"}</strong><small>История старой привязки не переписывается.</small></div>
          <label class="field"><span>Рыночная категория</span><select name="category_id" ${saving || !alternativeCategories.length ? "disabled" : ""}>${categoryOptions || '<option value="">Нет других сохранённых категорий</option>'}</select></label>
          ${reasonField}
          ${confirmationField}
          <button class="btn btn-secondary" type="submit" data-market-category-action="${existingAction}" ${saving || !alternativeCategories.length ? "disabled" : ""}>${saving ? "Сохраняем…" : current ? "Переклассифицировать" : "Связать категорию"}</button>
        </form>
        <form id="product-research-market-category-create-form" class="product-research-market-choice product-research-market-category-form" data-research-id="${escapeHtml(runId)}" data-ce-patch-key="research-market-create:${escapeHtml(runId)}" novalidate>
          <input type="hidden" name="candidate_hash" value="${escapeHtml(candidate.candidateHash)}" />
          <input type="hidden" name="market_category_action" value="${createAction}" />
          <div><strong>${current ? "Создать новую категорию и переклассифицировать" : "Создать устойчивую категорию"}</strong><small>Название и границы станут переиспользуемыми только после вашего подтверждения.</small></div>
          <label class="field"><span>Каноническое название</span><input name="canonical_name" maxlength="160" value="${escapeHtml(candidate.categoryName)}" ${saving ? "disabled" : ""} /></label>
          <label class="field"><span>Определение и границы</span><textarea name="definition" maxlength="2000" ${saving ? "disabled" : ""}>${escapeHtml(candidate.definition)}</textarea></label>
          <label class="field"><span>Синонимы, по одному на строку</span><textarea name="aliases" maxlength="1600" placeholder="Не более 10 точных вариантов" ${saving ? "disabled" : ""}></textarea></label>
          ${reasonField}
          ${confirmationField}
          <button class="btn" type="submit" data-market-category-action="${createAction}" ${saving ? "disabled" : ""}>${saving ? "Сохраняем…" : current ? "Создать и переклассифицировать" : "Создать и связать"}</button>
        </form>
      </div>`
    : `<div class="product-research-market-unavailable">
        <div><strong>${!registry.available ? "Реестр категории временно недоступен" : registry.canResolve === false ? "Категория доступна только для просмотра" : "Сначала нужен актуальный кандидат из ТЗ"}</strong><p>${!registry.available ? "Сохранённое исследование не потеряно. Обновите статус перед изменением категории." : registry.canResolve === false ? "Текущая роль может проверить evidence и историю, но решение принимает owner, admin или producer." : "Сохраните результат исследования, затем система предложит устойчивую категорию и попросит решение."}</p></div>
        <button class="btn btn-secondary" type="button" data-action="refresh-product-research">Обновить статус</button>
      </div>`;
  const searchForm = registry.available
    ? `<form id="product-research-market-category-search-form" class="product-research-market-search" data-research-id="${escapeHtml(runId)}" data-ce-patch-key="research-market-search:${escapeHtml(runId)}" novalidate>
        <div><strong>Найти категорию за пределами последних 20</strong><small>Введите точное каноническое название или сохранённый синоним. Поиск бесплатный и не обращается к провайдеру.</small></div>
        <label class="field"><span>Точное название / синоним</span><input name="category_query" minlength="2" maxlength="160" required ${saving ? "disabled" : ""} /></label>
        <button class="btn btn-secondary" type="submit" ${saving ? "disabled" : ""}>Найти</button>
      </form>`
    : "";
  return `
    <section class="card product-research-market-registry" aria-labelledby="product-research-market-title" data-market-category-state="${escapeHtml(registry.available ? registry.guidance.status : "unavailable")}">
      <div class="card-header">
        <div><p class="eyebrow">Обучаемая карта категорий</p><h2 id="product-research-market-title">Рыночная идентичность отдельно от правил товара</h2><p>ИИ предлагает границы по доказательствам, но только пользователь создаёт или меняет устойчивую привязку. История решений остаётся неизменяемой.</p></div>
        <span class="badge">${escapeHtml(guidanceLabels[registry.available ? registry.guidance.status : "unavailable"] || "нужна проверка")}</span>
      </div>
      <div class="product-research-market-summary">
        <article><small>Текущая привязка</small><strong>${escapeHtml(current?.canonicalName || "не подтверждена")}</strong><p>${escapeHtml(current?.definition || "Новая категория не будет создана без вашего решения.")}</p></article>
        <article><small>Предложение ИИ</small><strong>${escapeHtml(candidate?.categoryName || "нет актуального кандидата")}</strong><p>${escapeHtml(candidate?.definition || "Система ждёт проверяемое исследование категории.")}</p></article>
        <article><small>Контур правил</small><strong>остаётся отдельным</strong><p>Рыночная переклассификация не меняет compliance-категорию и юридические ограничения.</p></article>
      </div>
      ${searchForm}
      ${decisionForm}
      <div class="product-research-market-history">
        <div><p class="eyebrow">Скорость и противоречия</p><h3>Сигналы внутри подтверждённой категории</h3><p>Смена категории или схемы структурных ID начинает новую базу и не изображается продолжением старого тренда.</p></div>
        <div><p class="eyebrow">Оцифрованная динамика</p><h3>Скорость доказательной поддержки</h3><p>Доля показывает, сколько источников утверждённого снимка поддерживает структурный сигнал. Это не просмотры, не продажи, не популярность платформы и не causal winner.</p></div>
        ${velocityTimeline}
        <div><p class="eyebrow">Семантическая история</p><h3>Заявленные направления и противоречия</h3></div>
        ${timeline}
      </div>
    </section>`;
}

function researchOutcomeAngleLabel(value) {
  return {
    product_focus: "фокус на товаре",
    trust_builder: "доверие и доказательства",
    demonstration: "демонстрация",
    comparison: "сравнение",
    objection_handling: "работа с возражением",
    curiosity_gap: "интрига",
  }[String(value || "")] || "структурный ракурс";
}

function researchOutcomePlatformLabel(value) {
  return {
    instagram: "Instagram",
    tiktok: "TikTok",
    youtube: "YouTube",
    vk: "VK",
    telegram: "Telegram",
    wildberries: "Wildberries",
  }[String(value || "")] || String(value || "площадка");
}

function researchOutcomeModelLabel(value) {
  return {
    gen4_turbo: "Gen‑4 Turbo",
    seedance2_fast: "Seedance 2 Fast",
    seedream5_lite: "Seedream 5 Lite",
  }[String(value || "")] || String(value || "модель");
}

export function researchOutcomeScopeRegistryMarkup(value, { saving = false } = {}) {
  const registry = objectValue(value) && Object.prototype.hasOwnProperty.call(value, "available")
    ? value
    : normalizeResearchOutcomeScopeRegistry({ unavailable: true });
  if (!registry.available) {
    return `<section class="card product-research-outcome-scope is-unavailable" data-outcome-scope-state="${registry.unavailable ? "unavailable" : "empty"}">
      <div class="card-header"><div><p class="eyebrow">Контуры обучения</p><h2>${registry.unavailable ? "Реестр временно недоступен" : "Точных контуров пока нет"}</h2></div><span class="badge">${registry.unavailable ? "нет статуса" : "нужно доказательство"}</span></div>
      <p>${registry.unavailable ? "Сохранённое исследование не изменено. Обновите статус позже." : "Утвердите сценарий и точную рыночную категорию. Браузер не угадывает контур из неутверждённого draft."}</p>
    </section>`;
  }
  if (!registry.scopes.length) return "";
  const optionMarkup = registry.scopes.map((entry) => {
    const flags = [
      entry.approvedRecommended ? "рекомендован в утверждённом сценарии" : "",
      entry.currentMemoryState === "active" ? "активная память" : "",
      entry.category.status === "retired" ? "историческая категория" : "",
    ].filter(Boolean).join(" · ");
    const label = `${entry.category.canonicalName} — ${researchOutcomePlatformLabel(entry.scope.platform)} / ${researchOutcomeModelLabel(entry.scope.model)}${flags ? ` (${flags})` : ""}`;
    return `<option value="${escapeHtml(entry.key)}" ${entry.key === registry.selectedScopeKey ? "selected" : ""}>${escapeHtml(label)}</option>`;
  }).join("");
  const selector = registry.selectionRequired
    ? `<form id="product-research-outcome-scope-form" class="product-research-outcome-scope-form" novalidate>
        <label class="field"><span>Какой точный контур открыть?</span><select name="scope_key" required ${saving ? "disabled" : ""}><option value="">Выберите категорию · площадку · модель</option>${optionMarkup}</select></label>
        <button class="btn btn-secondary" type="submit" ${saving ? "disabled" : ""}>${saving ? "Открываем…" : "Открыть выбранный контур"}</button>
      </form>`
    : `<div class="product-research-outcome-scope-current"><small>Единственный доказанный контур</small><strong>${escapeHtml(registry.scopes[0].category.canonicalName)} · ${escapeHtml(researchOutcomePlatformLabel(registry.scopes[0].scope.platform))} · ${escapeHtml(researchOutcomeModelLabel(registry.scopes[0].scope.model))}</strong></div>`;
  return `<section class="card product-research-outcome-scope" data-outcome-scope-state="${registry.selectedScope ? "selected" : "selection-required"}">
    <div class="card-header"><div><p class="eyebrow">Управляемое обучение</p><h2>Все точные контуры, без склейки версий</h2><p>Каждый вариант — категория · площадка · модель из утверждённого сценария или неизменяемой истории.</p></div><span class="badge">${registry.scopes.length} контур${registry.scopes.length === 1 ? "" : "а"}</span></div>
    ${registry.truncated ? `<div class="alert alert-warning" role="status"><strong>Показан ограниченный список.</strong><span>Выбор применится только к точному видимому контуру; скрытого auto-select нет.</span></div>` : ""}
    ${selector}
    <p class="muted tiny">Просмотр и выбор контура не запускают провайдера, генерацию, расход или публикацию.</p>
  </section>`;
}

function researchOutcomeRateLabel(value) {
  const rate = Number(value);
  if (!Number.isFinite(rate)) return "0%";
  return `${(rate * 100).toFixed(rate * 100 >= 10 ? 1 : 2).replace(".", ",")}%`;
}

function researchOutcomeHiddenFields(scope, candidate, expectedScopeVersion, rollbackId = "") {
  return `
    <input type="hidden" name="market_category_id" value="${escapeHtml(scope?.marketCategoryId || "")}" />
    <input type="hidden" name="platform" value="${escapeHtml(scope?.platform || "")}" />
    <input type="hidden" name="model" value="${escapeHtml(scope?.model || "")}" />
    <input type="hidden" name="candidate_id" value="${escapeHtml(candidate?.id || "")}" />
    <input type="hidden" name="candidate_version" value="${escapeHtml(candidate?.version || "")}" />
    <input type="hidden" name="candidate_hash" value="${escapeHtml(candidate?.hash || "")}" />
    <input type="hidden" name="expected_scope_version" value="${escapeHtml(expectedScopeVersion)}" />
    ${rollbackId ? `<input type="hidden" name="rollback_memory_version_id" value="${escapeHtml(rollbackId)}" />` : ""}`;
}

function researchOutcomeConfirmationField(label, saving) {
  return `<label class="check-row product-research-outcome-confirmation"><input type="checkbox" name="outcome_confirmation" required ${saving ? "disabled" : ""} /><span><strong>${escapeHtml(label)}</strong><br /><small>Решение сохранится в неизменяемой истории. Оно не запускает провайдера, генерацию или публикацию.</small></span></label>`;
}

function researchOutcomeCandidateMarkup(candidate, control, saving) {
  const statusLabels = {
    pending: "ждёт решения",
    active: "активна как совет",
    rejected: "отклонена",
    quarantined: "карантин",
    deactivated: "отключена",
    superseded: "заменена",
  };
  const expectedScopeVersion = control.currentMemory?.version || 0;
  const decisionForm = candidate.status === "pending" && control.canDecide
    ? `<form class="product-research-outcome-form product-research-outcome-decision" novalidate>
        ${researchOutcomeHiddenFields(control.scope, candidate, expectedScopeVersion)}
        <label class="field"><span>Почему принимаете это решение *</span><textarea name="reason" minlength="3" maxlength="500" placeholder="Что подтверждают результаты и какой риск нужно сохранить под контролем" ${saving ? "disabled" : ""}></textarea></label>
        ${researchOutcomeConfirmationField("Подтверждаю решение по этому кандидату", saving)}
        <div class="inline-actions product-research-outcome-actions">
          <button class="btn btn-ghost" type="submit" data-outcome-action="reject" ${saving ? "disabled" : ""}>Отклонить</button>
          <button class="btn btn-secondary" type="submit" data-outcome-action="quarantine" ${saving ? "disabled" : ""}>В карантин</button>
          <button class="btn" type="submit" data-outcome-action="activate" ${saving ? "disabled" : ""}>Активировать как совет</button>
        </div>
      </form>`
    : candidate.status === "pending" && !control.canDecide
      ? `<p class="muted tiny">Текущая роль может проверить доказательства, но решение принимает owner, admin или producer.</p>`
      : "";
  return `<article class="product-research-outcome-candidate" data-outcome-candidate-status="${escapeHtml(candidate.status)}">
    <header><div><small>Кандидат v${candidate.version}</small><h3>${escapeHtml(researchOutcomeAngleLabel(candidate.preferredAngle))}</h3></div><span class="badge">${escapeHtml(statusLabels[candidate.status] || "проверка")}</span></header>
    <p>Сравнение: <strong>${escapeHtml(researchOutcomeAngleLabel(candidate.comparatorAngle))}</strong>. Популярность конкурентов и абсолютные просмотры не используются как сигнал победителя.</p>
    <div class="product-research-outcome-evidence">
      <div><small>Зрелые исходы</small><strong>${candidate.eligibleOutcomeCount}</strong></div>
      <div><small>Товары в обоих ракурсах</small><strong>${candidate.overlappingProductCount}</strong></div>
      <div><small>CTR: кандидат / контроль</small><strong>${escapeHtml(researchOutcomeRateLabel(candidate.preferred.meanCtr))} / ${escapeHtml(researchOutcomeRateLabel(candidate.comparator.meanCtr))}</strong></div>
      <div><small>Заказы: кандидат / контроль</small><strong>${escapeHtml(researchOutcomeRateLabel(candidate.preferred.meanOrderRate))} / ${escapeHtml(researchOutcomeRateLabel(candidate.comparator.meanOrderRate))}</strong></div>
    </div>
    <small class="product-research-outcome-hash">hash ${escapeHtml(candidate.hash.slice(0, 12))}… · QA + публикация + метрика ≥ ${candidate.minimumMaturityHours} ч</small>
    ${decisionForm}
  </article>`;
}

export function researchOutcomeLearningMarkup(value, { saving = false } = {}) {
  const control = objectValue(value) && Object.prototype.hasOwnProperty.call(value, "available")
    ? value
    : normalizeResearchOutcomeLearning({ unavailable: true });
  if (!control.available) {
    const scopeCopy = control.scopeMissing
      ? "Сначала подтвердите рыночную категорию и сохраните точный сценарий с поддерживаемой площадкой и моделью. До этого система не будет угадывать контур обучения."
      : "Статус outcome‑памяти не прошёл проверку контракта. Исследование и ТЗ сохранены; не принимайте решение по памяти, пока статус не обновится.";
    return `<section class="card product-research-outcome-learning is-unavailable" aria-labelledby="product-research-outcome-title" data-outcome-state="${control.scopeMissing ? "scope-missing" : "unavailable"}">
      <div class="card-header"><div><p class="eyebrow">Обучение по своим результатам</p><h2 id="product-research-outcome-title">Сначала точная цепочка доказательств</h2><p>${escapeHtml(scopeCopy)}</p></div><span class="badge">${control.scopeMissing ? "нужен контур" : "статус недоступен"}</span></div>
      ${control.scopeMissing ? "" : '<button class="btn btn-secondary" type="button" data-action="refresh-product-research">Обновить общий статус</button>'}
    </section>`;
  }
  const statusLabels = {
    no_eligible_outcomes: "нет зрелых исходов",
    insufficient_comparable_evidence: "нужно больше сравнений",
    candidate_requires_decision: "нужно решение",
    advisory_memory_active: "совет активен",
    advisory_memory_inactive: "совет отключён",
    outcomes_need_comparison: "нужно обновить сравнение",
  };
  const activeCandidate = control.currentMemory?.state === "active"
    ? control.currentMemory.candidate
    : null;
  const expectedScopeVersion = control.currentMemory?.version || 0;
  const refreshForm = control.canRefresh
    ? `<form id="product-research-outcome-refresh-form" class="product-research-outcome-refresh-form" novalidate>
        <input type="hidden" name="market_category_id" value="${escapeHtml(control.scope.marketCategoryId)}" />
        <input type="hidden" name="platform" value="${escapeHtml(control.scope.platform)}" />
        <input type="hidden" name="model" value="${escapeHtml(control.scope.model)}" />
        <div><strong>Пересчитать только по собственным зрелым исходам</strong><small>Операция бесплатна: она фиксирует новые QA‑подтверждённые публикации и создаёт максимум кандидата, но никогда не активирует его.</small></div>
        <button class="btn btn-secondary" type="submit" ${saving ? "disabled" : ""}>${saving ? "Проверяем…" : "Проверить новые результаты"}</button>
      </form>`
    : "";
  const deactivateForm = activeCandidate && control.canDecide
    ? `<form class="product-research-outcome-form product-research-outcome-control-form" novalidate>
        ${researchOutcomeHiddenFields(control.scope, activeCandidate, expectedScopeVersion)}
        <label class="field"><span>Причина отключения *</span><textarea name="reason" minlength="3" maxlength="500" placeholder="Почему этот совет больше не должен направлять решения" ${saving ? "disabled" : ""}></textarea></label>
        ${researchOutcomeConfirmationField("Отключаю активную advisory‑версию", saving)}
        <button class="btn btn-ghost" type="submit" data-outcome-action="deactivate" ${saving ? "disabled" : ""}>Отключить совет</button>
      </form>`
    : "";
  const rollbackCandidate = control.rollbackTarget?.candidate || null;
  const rollbackForm = rollbackCandidate && control.canDecide
    ? `<form class="product-research-outcome-form product-research-outcome-control-form" novalidate>
        ${researchOutcomeHiddenFields(
          control.scope,
          rollbackCandidate,
          expectedScopeVersion,
          control.rollbackTarget.memoryId,
        )}
        <label class="field"><span>Почему возвращаете версию ${control.rollbackTarget.memoryVersion} *</span><textarea name="reason" minlength="3" maxlength="500" placeholder="Какое ухудшение или изменение контекста требует отката" ${saving ? "disabled" : ""}></textarea></label>
        ${researchOutcomeConfirmationField("Возвращаю точную прежнюю advisory‑версию", saving)}
        <button class="btn btn-secondary" type="submit" data-outcome-action="revert" ${saving ? "disabled" : ""}>Откатить к версии ${control.rollbackTarget.memoryVersion}</button>
      </form>`
    : "";
  const candidates = control.candidates.length
    ? `<div class="product-research-outcome-candidates">${control.candidates.map((candidate) => researchOutcomeCandidateMarkup(candidate, control, saving)).join("")}</div>`
    : `<div class="product-research-empty-note"><strong>Кандидата пока нет</strong><p>Нужны минимум два структурных ракурса, по три зрелых исхода на каждый и результаты как минимум двух товаров внутри точной категории.</p></div>`;
  const history = control.decisionHistory.length
    ? `<div class="product-research-outcome-history"><h3>Неизменяемая история решений</h3>${control.decisionHistory.slice(0, 8).map((item) => `<article><span class="badge">${escapeHtml({ activate: "активация", reject: "отказ", quarantine: "карантин", deactivate: "отключение", revert: "откат" }[item.action] || item.action)}</span><div><strong>Кандидат v${item.candidateVersion}</strong><p>${escapeHtml(item.reason)}</p><small>${escapeHtml(researchDateLabel(item.decidedAt))} · scope v${item.expectedScopeVersion}</small></div></article>`).join("")}</div>`
    : `<p class="muted tiny">Решений по этому контуру ещё нет.</p>`;
  return `<section class="card product-research-outcome-learning" aria-labelledby="product-research-outcome-title" data-outcome-state="${escapeHtml(control.guidance.status)}">
    <div class="card-header"><div><p class="eyebrow">Обучение по своим результатам</p><h2 id="product-research-outcome-title">Кандидат отдельно, активация отдельно, откат всегда доступен</h2><p>Система использует только точную цепочку research → scenario → generation → media → QA → publication → зрелая first‑party metric.</p></div><span class="badge">${escapeHtml(statusLabels[control.guidance.status] || "проверка")}</span></div>
    <div class="alert alert-warning product-research-outcome-advisory" role="note"><strong>Пока это только советующий контур.</strong><span>Даже статус «активен» не меняет авто‑ТЗ и не влияет на платную генерацию. Подключение к production потребует отдельного server‑gate.</span></div>
    <div class="product-research-outcome-summary">
      <div><small>Рыночная категория</small><strong>${escapeHtml(control.marketCategory?.canonicalName || "—")}</strong></div>
      <div><small>Точный контур</small><strong>${escapeHtml(researchOutcomePlatformLabel(control.scope.platform))} · ${escapeHtml(researchOutcomeModelLabel(control.scope.model))}</strong></div>
      <div><small>Зафиксировано зрелых исходов</small><strong>${control.capturedOutcomeCount}</strong></div>
      <div><small>Advisory‑версия</small><strong>${control.currentMemory ? `${control.currentMemory.state === "active" ? "активна" : "отключена"} · v${control.currentMemory.version}` : "не создавалась"}</strong></div>
    </div>
    <aside class="product-research-outcome-guidance" role="status"><div><p class="eyebrow">Следующий безопасный шаг</p><h3>${escapeHtml({ collect_qa_approved_mature_first_party_metrics: "Дождаться зрелых собственных результатов", review_activate_reject_or_quarantine: "Проверить кандидата и принять решение", monitor_effectiveness_and_keep_rollback_ready: "Следить за эффектом и держать откат готовым", review_rollback_target: "Проверить точную версию для отката", refresh_bounded_learning_candidates: "Пересчитать ограниченные кандидаты", gather_more_comparable_outcomes: "Накопить сопоставимые результаты", wait_for_new_candidate: "Ждать нового доказанного кандидата" }[control.guidance.recommendedNextStep] || "Проверить evidence и статус")}</h3><p>Никаких автоматических расходов, рендера или публикации.</p></div></aside>
    ${refreshForm}
    ${activeCandidate ? `<div class="product-research-outcome-active"><div><small>Активный advisory‑кандидат</small><strong>${escapeHtml(researchOutcomeAngleLabel(activeCandidate.preferredAngle))}</strong><p>Он зафиксирован как управленческий совет, но ещё не подключён к генератору.</p></div></div>` : ""}
    ${deactivateForm}
    ${rollbackForm}
    <div class="product-research-outcome-list-heading"><div><p class="eyebrow">Кандидаты</p><h3>Структурные признаки без чужого текста</h3></div></div>
    ${candidates}
    ${history}
  </section>`;
}

export function researchWatchlistMarkup(value, {
  saving = false,
  runId = "",
  categoryResetSnapshotIds = [],
} = {}) {
  const monitor = objectValue(value) && Object.prototype.hasOwnProperty.call(value, "enabled")
    ? value
    : normalizeResearchWatchlist({});
  const freshnessLabels = {
    unavailable: "статус недоступен",
    not_enabled: "не подключено",
    needs_baseline: "нужен базовый снимок",
    fresh: "данные актуальны",
    due: "пора проверить",
    stale: "данные устарели",
    paused: "наблюдение на паузе",
  };
  const intervalValues = [3, 7, 14, 30, 60, 90];
  if (!intervalValues.includes(monitor.intervalDays)) {
    intervalValues.push(monitor.intervalDays);
    intervalValues.sort((left, right) => left - right);
  }
  const intervalSelect = `<label class="field product-research-watchlist-interval"><span>Предлагать проверку через</span><select name="refresh_interval_days" required ${saving ? "disabled" : ""}>${intervalValues.map((days) => `<option value="${days}" ${days === monitor.intervalDays ? "selected" : ""}>${days} ${russianDayLabel(days)}</option>`).join("")}</select></label>`;
  const controls = !monitor.available
    ? `<button class="btn btn-secondary" type="button" data-action="refresh-product-research" ${saving ? "disabled" : ""}>Проверить статус ещё раз</button>`
    : !monitor.enabled
      ? `${intervalSelect}<button class="btn" type="submit" name="watchlist_action" value="enable" data-watchlist-action="enable" ${saving ? "disabled" : ""}>${saving ? "Подключаем…" : "Подключить наблюдение"}</button>`
      : monitor.status === "paused"
        ? `${intervalSelect}<button class="btn" type="submit" name="watchlist_action" value="resume" data-watchlist-action="resume" ${saving ? "disabled" : ""}>${saving ? "Возобновляем…" : "Возобновить наблюдение"}</button>`
        : `${intervalSelect}<button class="btn btn-secondary" type="submit" name="watchlist_action" value="update" data-watchlist-action="update" ${saving ? "disabled" : ""}>${saving ? "Сохраняем…" : "Изменить интервал"}</button><button class="btn btn-ghost" type="submit" name="watchlist_action" value="pause" data-watchlist-action="pause" ${saving ? "disabled" : ""}>Поставить на паузу</button>`;
  const latestSnapshot = monitor.snapshots[0] || null;
  const resetSnapshotIds = new Set(stringArray(categoryResetSnapshotIds));
  const history = monitor.snapshots.length
    ? `<div class="product-research-watchlist-history">${monitor.snapshots.map((snapshot, index) => `
        <article class="product-research-watchlist-snapshot">
          <header><div><strong>${index === 0 ? "Последний снимок" : `Снимок ${monitor.snapshots.length - index}`}</strong><small>${escapeHtml(researchDateLabel(snapshot.observedAt))} · ${snapshot.sourceCount} ист.</small></div><span class="badge">гипотеза</span></header>
          <ul>${researchWatchlistChangeItems(snapshot.change, {
            categoryReset: resetSnapshotIds.has(snapshot.id),
          }).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </article>`).join("")}</div>`
    : `<div class="product-research-empty-note"><strong>Снимков пока нет</strong><p>Первый снимок появится только из утверждённого человеком исследования версии v2.</p></div>`;
  const proposal = monitor.proposal
    ? `<div class="alert alert-warning product-research-watchlist-proposal" role="status"><strong>Система предлагает обновить данные.</strong><span>Срок наблюдения наступил${monitor.proposal.dueAt ? ` ${escapeHtml(researchDateLabel(monitor.proposal.dueAt))}` : ""}. Это предложение не создало исследование и ничего не списало.</span></div>`
    : "";
  const refreshCallToAction = monitor.enabled
    && ["due", "stale"].includes(monitor.freshness)
    ? `<div class="product-research-watchlist-refresh"><div><strong>Нужен новый снимок источников?</strong><p>Откройте новую форму, проверьте вводные и отдельно подтвердите платный анализ. Фоновый мониторинг его не запускает.</p></div><button class="btn" type="button" data-action="new-product-research">Подготовить новый анализ →</button></div>`
    : "";
  const guidanceActions = monitor.guidance.actions.length
    ? `<ul>${monitor.guidance.actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : "";

  return `
    <section class="card product-research-watchlist" aria-labelledby="product-research-watchlist-title" data-watchlist-freshness="${escapeHtml(monitor.freshness)}">
      <div class="card-header">
        <div><p class="eyebrow">Обучаемая память</p><h2 id="product-research-watchlist-title">Категория, конкуренты и тренды во времени</h2><p>Система сравнивает только утверждённые снимки и сама предлагает следующий шаг. Любое изменение остаётся гипотезой, а не «победителем».</p></div>
        <span class="badge">${escapeHtml(freshnessLabels[monitor.freshness] || "нужна проверка")}</span>
      </div>
      <div class="product-research-watchlist-summary">
        <div><small>Последний снимок</small><strong>${escapeHtml(researchDateLabel(monitor.lastSnapshotAt || latestSnapshot?.observedAt))}</strong></div>
        <div><small>Следующая проверка</small><strong>${monitor.status === "paused" ? "пауза" : escapeHtml(researchDateLabel(monitor.nextRefreshAt))}</strong></div>
        <div><small>История</small><strong>${monitor.snapshotCount} ${russianSnapshotLabel(monitor.snapshotCount)}</strong></div>
        <div><small>Противоречия</small><strong>${latestSnapshot && resetSnapshotIds.has(latestSnapshot.id) ? 0 : latestSnapshot?.change?.contradictionCount || 0}</strong></div>
      </div>
      ${proposal}
      <aside class="product-research-watchlist-guidance" role="status">
        <div><p class="eyebrow">Следующий шаг от ИИ</p><h3>${escapeHtml(monitor.guidance.title)}</h3><p>${escapeHtml(monitor.guidance.reason)}</p></div>
        ${guidanceActions}
      </aside>
      ${history}
      ${refreshCallToAction}
      <form id="product-research-watchlist-form" class="product-research-watchlist-controls" data-research-id="${escapeHtml(runId)}" data-ce-patch-key="research-watchlist:${escapeHtml(runId)}" novalidate>
        <div><strong>Вы управляете циклом</strong><small>Фоновая проверка только отмечает срок. Новый платный анализ запускается только после подтверждения пользователя в отдельной форме.</small></div>
        ${controls}
      </form>
    </section>`;
}

function researchWatchlistChangeItems(change, { categoryReset = false } = {}) {
  if (change.baseline) return ["Зафиксирован базовый снимок для будущих сравнений."];
  if (categoryReset) {
    return ["Рыночная категория или схема структурных ID изменилась: этот снимок стал новой базой без ложных трендов и противоречий."];
  }
  if (change.comparisonMode === "canonical_reset") {
    return ["Структурные ID трендов включены впервые: этот снимок стал новой базой без ложных добавлений, удалений и противоречий."];
  }
  const items = [];
  if (change.categoryChanged) items.push("Изменилась подтверждённая граница категории.");
  if (change.competitorsAdded.length) {
    items.push(`Добавлены сопоставимые предложения: ${change.competitorsAdded.join(", ")}.`);
  }
  if (change.competitorsRemoved.length) {
    items.push(`Больше не подтверждаются: ${change.competitorsRemoved.join(", ")}.`);
  }
  if (change.competitorsChanged.length) {
    items.push(`Обновились данные по предложениям: ${change.competitorsChanged.join(", ")}.`);
  }
  if (change.trendsAdded.length) items.push(`Появились сигналы: ${change.trendsAdded.join(", ")}.`);
  if (change.trendsRemoved.length) items.push(`Сигналы исчезли: ${change.trendsRemoved.join(", ")}.`);
  if (change.trendsChanged.length) items.push(`Обновилась доказательная база сигналов: ${change.trendsChanged.join(", ")}.`);
  change.directionChanges.forEach((item) => {
    items.push(`${item.signal}: ${trendDirectionLabel(item.from)} → ${trendDirectionLabel(item.to)}${item.contradiction ? "; направления противоречат друг другу" : ""}.`);
  });
  if (change.contradictions.length) {
    items.push(`Нужно разрешить противоречия: ${change.contradictions.join(", ")}.`);
  } else if (change.contradictionCount > 0) {
    items.push(`Обнаружено противоречий: ${change.contradictionCount}.`);
  }
  if (!items.length) {
    items.push(change.material
      ? "Состав или доказательная база исследования изменились; проверьте подробности снимка."
      : "Материальных изменений относительно прошлого снимка не найдено.");
  }
  return items;
}

function researchDateLabel(value) {
  const date = String(value || "").slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/u.exec(date);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : "не зафиксировано";
}

function russianDayLabel(value) {
  const remainder100 = value % 100;
  const remainder10 = value % 10;
  if (remainder100 >= 11 && remainder100 <= 14) return "дней";
  if (remainder10 === 1) return "день";
  if (remainder10 >= 2 && remainder10 <= 4) return "дня";
  return "дней";
}

function russianSnapshotLabel(value) {
  const remainder100 = value % 100;
  const remainder10 = value % 10;
  if (remainder100 >= 11 && remainder100 <= 14) return "снимков";
  if (remainder10 === 1) return "снимок";
  if (remainder10 >= 2 && remainder10 <= 4) return "снимка";
  return "снимков";
}

function productResearchIntelligenceMarkup({
  categoryAnalysis,
  competitorAnalysis,
  trendAnalysis,
  guidance,
  stageCorrections,
  sources = [],
  disabled = false,
  readOnly = false,
}) {
  const guidanceLabels = {
    ready_for_brief: "Можно переходить к ТЗ",
    needs_more_evidence: "Нужно больше данных",
    needs_user_decision: "Нужно решение пользователя",
  };
  const maturityLabels = {
    emerging: "Формирующаяся категория",
    growing: "Растущая категория",
    established: "Сформировавшаяся категория",
    saturated: "Насыщенная категория",
    unknown: "Нужно уточнение",
    new: "Новая категория",
    unclear: "Нужно уточнение",
  };
  const coverageLabels = {
    none: "Конкуренты не подтверждены",
    limited: "Ограниченная выборка",
    sufficient: "Рабочая выборка",
    insufficient: "Недостаточная выборка",
    partial: "Частичная выборка",
    representative: "Рабочая выборка",
  };
  const correctionField = (name, label, value, placeholder) => readOnly ? "" : `
    <label class="field product-research-stage-correction">
      <span>${escapeHtml(label)}</span>
      <textarea form="product-research-brief-form" name="${escapeHtml(name)}" maxlength="2000" placeholder="${escapeHtml(placeholder)}" ${disabled ? "disabled" : ""}>${escapeHtml(value || "")}</textarea>
      <small class="field-hint">Правка сохраняется отдельным человеческим слоем: исходные ссылки и найденные доказательства остаются неизменными для аудита.</small>
    </label>`;
  const list = (items, emptyText) => items.length
    ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
    : `<p class="muted">${escapeHtml(emptyText)}</p>`;
  const sourceIndex = new Map();
  sources.forEach((source) => {
    if (source?.id) sourceIndex.set(String(source.id), source);
    if (source?.modelId) sourceIndex.set(String(source.modelId), source);
  });
  const evidenceRefs = (sourceIds) => {
    const linked = stringArray(sourceIds)
      .map((sourceId) => sourceIndex.get(sourceId))
      .filter(Boolean)
      .filter((source, index, items) => items.indexOf(source) === index);
    if (!linked.length) {
      return sourceIds.length
        ? `<small class="product-research-evidence-count">${sourceIds.length} ист.</small>`
        : "";
    }
    return `<div class="product-research-evidence-refs"><small>Доказательства:</small>${linked.map((source) => source.url
      ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">${escapeHtml(source.title)}</a>`
      : `<span>${escapeHtml(source.title)}</span>`).join("")}</div>`;
  };
  const evidenceList = (items) => `<ul>${items.map((item) => `
    <li><span>${escapeHtml(item.text)}</span>${evidenceRefs(item.sourceIds)}</li>
  `).join("")}</ul>`;
  const competitorCards = competitorAnalysis.competitors.length
    ? competitorAnalysis.competitors.map((competitor) => `
        <article class="product-research-intel-item">
          <div><h4>${escapeHtml(competitor.name)}</h4><span class="badge">${competitor.sourceIds.length} ист.</span></div>
          ${evidenceRefs(competitor.sourceIds)}
          <p>${escapeHtml(competitor.positioning || "Позиционирование не подтверждено.")}</p>
          ${competitor.pricePositioning ? `<small>${escapeHtml(competitor.pricePositioning)}</small>` : ""}
          ${competitor.recurringFormats.length ? `<strong>Повторяющиеся форматы</strong>${list(competitor.recurringFormats, "")}` : ""}
          ${competitor.strengths.length ? `<strong>Сильные стороны</strong>${list(competitor.strengths, "")}` : ""}
          ${competitor.weaknesses.length ? `<strong>Риски и слабые места</strong>${list(competitor.weaknesses, "")}` : ""}
          ${competitor.reusableStructures.length ? `<strong>Структуры для собственного теста</strong>${list(competitor.reusableStructures, "")}` : ""}
        </article>`).join("")
    : '<p class="muted">Сопоставимые конкуренты пока не подтверждены. Система не будет изображать полноту рынка без доказательств.</p>';
  const trendCards = trendAnalysis.signals.length
    ? trendAnalysis.signals.map((signal) => `
        <article class="product-research-intel-item">
          <div><h4>${escapeHtml(signal.signal)}</h4><span class="badge">${escapeHtml(trendDirectionLabel(signal.direction))}</span></div>
          ${signal.signalKey ? `<small>Структурный ID: ${escapeHtml(signal.signalKey)}</small>` : ""}
          ${evidenceRefs(signal.sourceIds)}
          <p>${escapeHtml(signal.evidence || "Сигнал требует дополнительной проверки.")}</p>
          <small>${escapeHtml(`Уверенность: ${confidenceCopy(signal.confidence).label.toLowerCase()} · источников: ${signal.sourceIds.length} · действие: ${trendUseLabel(signal.recommendedUse)}`)}</small>
        </article>`).join("")
    : '<p class="muted">Свежих трендовых сигналов недостаточно. Это честный cold start, а не повод переносить выводы другой категории.</p>';
  const questions = guidance.questions.length
    ? `<div class="product-research-guidance-list"><strong>Что система просит уточнить</strong>${list(guidance.questions, "")}</div>`
    : "";
  const actions = guidance.actions.length
    ? `<div class="product-research-guidance-list"><strong>Что делать дальше</strong>${list(guidance.actions, "")}</div>`
    : "";

  return `
    <section class="card product-research-intelligence" aria-labelledby="product-research-intelligence-title">
      <div class="card-header">
        <div><p class="eyebrow">Управляемое исследование</p><h2 id="product-research-intelligence-title">Категория → конкуренты → тренды → решение</h2><p>${readOnly ? "Это завершённый снимок доказательств и выводов. Система показывает пробелы и рекомендуемый следующий шаг без изменения исходного исследования." : "Каждый вывод можно скорректировать до утверждения. Система сама показывает пробелы и рекомендует следующий шаг."}</p></div>
        <span class="badge">${escapeHtml(guidanceLabels[guidance.status] || "Нужна проверка")}</span>
      </div>
      <div class="product-research-intelligence-grid">
        <article class="product-research-intel-stage" data-research-stage="sources">
          <header><span>01</span><div><p class="eyebrow">Доказательства</p><h3>Источники и границы</h3></div></header>
          <p>${readOnly ? "Неизменяемая база ссылок остаётся в блоке доказательств и доступна для проверки." : "Неизменяемая база ссылок остаётся в блоке доказательств. Здесь можно указать, какой источник не использовать в решении и почему."}</p>
          ${correctionField("source_correction", "Корректировка источников", stageCorrections.sources, "Например: источник описывает другую комплектацию — не использовать его для оффера")}
        </article>
        <article class="product-research-intel-stage" data-research-stage="category">
          <header><span>02</span><div><p class="eyebrow">Категория</p><h3>${escapeHtml(categoryAnalysis.categoryName || "Категория уточняется")}</h3></div></header>
          <span class="badge">${escapeHtml(maturityLabels[categoryAnalysis.maturity] || maturityLabels.unclear)}</span>
          <p><strong>Контур правил:</strong> ${escapeHtml(categoryAnalysis.complianceCategory || "не определён")} · <strong>уверенность снимка:</strong> ${escapeHtml(confidenceCopy(categoryAnalysis.confidence).label.toLowerCase())}</p>
          ${categoryAnalysis.marketCategoryKey ? `<small>Предложение ИИ для этого снимка не является устойчивой привязкой; подтверждённая рыночная категория показана в отдельном реестре выше.</small>` : ""}
          <p>${escapeHtml(categoryAnalysis.definition || "ИИ не смог надёжно определить границы категории по доступным источникам.")}</p>
          ${evidenceRefs(categoryAnalysis.sourceIds)}
          <strong>Покупательские задачи</strong>
          ${list(categoryAnalysis.buyerJobs, "Пока не подтверждены.")}
          ${categoryAnalysis.substituteCategories.length ? `<strong>Категории-заменители</strong>${list(categoryAnalysis.substituteCategories, "")}` : ""}
          ${categoryAnalysis.unknowns.length ? `<strong>Что неизвестно</strong>${list(categoryAnalysis.unknowns, "")}` : ""}
          ${correctionField("category_correction", "Корректировка категории", stageCorrections.category, "Уточните границы категории, сценарий применения или аудиторию")}
        </article>
        <article class="product-research-intel-stage" data-research-stage="competitors">
          <header><span>03</span><div><p class="eyebrow">Конкуренты</p><h3>Карта сопоставимых предложений</h3></div></header>
          <span class="badge">${escapeHtml(coverageLabels[competitorAnalysis.coverage] || coverageLabels.insufficient)}</span>
          <div class="product-research-intel-items">${competitorCards}</div>
          ${competitorAnalysis.contentGaps.length ? `<strong>Контентные пробелы</strong>${evidenceList(competitorAnalysis.contentGaps)}` : ""}
          ${competitorAnalysis.saturatedPatterns.length ? `<strong>Перегретые приёмы</strong>${evidenceList(competitorAnalysis.saturatedPatterns)}` : ""}
          ${competitorAnalysis.limitations.length ? `<strong>Ограничения разбора конкурентов</strong>${list(competitorAnalysis.limitations, "")}` : ""}
          ${correctionField("competitor_correction", "Корректировка разбора конкурентов", stageCorrections.competitors, "Добавьте контекст или отметьте несопоставимого конкурента")}
        </article>
        <article class="product-research-intel-stage" data-research-stage="trends">
          <header><span>04</span><div><p class="eyebrow">Тренды</p><h3>Сигналы, а не обещания</h3></div></header>
          ${trendAnalysis.asOf ? `<span class="badge">На ${escapeHtml(trendAnalysis.asOf)}</span>` : ""}
          <div class="product-research-intel-items">${trendCards}</div>
          ${trendAnalysis.limitations.length ? `<strong>Ограничения анализа</strong>${list(trendAnalysis.limitations, "")}` : ""}
          ${correctionField("trend_correction", "Корректировка трендов", stageCorrections.trends, "Укажите сезонность, локальный контекст или сигнал, который нужно только наблюдать")}
        </article>
      </div>
      <aside class="product-research-guidance" role="status">
        <div><p class="eyebrow">ИИ-наставник</p><h3>${escapeHtml(guidance.recommendedNextStep || "Проверьте исследование перед ТЗ")}</h3><p>${escapeHtml(guidance.reason || "Система отделила подтверждённые данные от гипотез и ждёт человеческой проверки.")}</p></div>
        ${questions}${actions}
        ${correctionField("strategy_correction", "Ваше решение для следующего этапа", stageCorrections.strategy, "Например: сначала проверить демонстрацию на новой аудитории, сравнение пока не использовать")}
      </aside>
    </section>`;
}

function trendDirectionLabel(value) {
  return {
    emerging: "возникает",
    growing: "растёт",
    stable: "стабилен",
    declining: "снижается",
    unclear: "неясно",
  }[String(value || "unclear")] || "неясно";
}

function trendUseLabel(value) {
  return {
    test: "проверить малым тестом",
    monitor: "наблюдать",
    avoid: "не использовать",
  }[String(value || "monitor")] || "наблюдать";
}

function scenarioEditor(item, index, {
  members = [],
  defaultAssigneeId = "",
  disabled = false,
  recommended = false,
  generationHandoffAllowed = true,
} = {}) {
  const options = [["instagram", "Instagram Reels"], ["youtube", "YouTube Shorts"], ["vk", "VK Клипы"], ["wildberries", "Wildberries"], ["ozon", "Ozon"]];
  const selectedAssigneeId = String(item.assigneeId || defaultAssigneeId || members[0]?.profileId || "");
  const photo = item.generationMode === "real_photo";
  const silent = photo || item.generationMode === "real_gen4";
  const readiness = inspectResearchScenarioGenerationReadiness(item);
  const generationModeLabel = photo
    ? "квадратное товарное фото · Seedream"
    : item.generationMode === "real_gen4"
      ? "5 секунд · товарный ролик без речи"
      : item.generationMode === "real_seedance"
        ? "8 секунд · UGC с репликой"
        : "будет подобран по ограничениям сценария";
  const scriptLabel = silent ? "Реплика не нужна" : "Реплика блогера";
  const scriptPlaceholder = silent
    ? photo
      ? "Для статичного фото поле остаётся пустым"
      : "Для рекомендованного Gen4 поле остаётся пустым"
    : "Короткая разговорная реплика без неподтверждённых обещаний";
  const approvedExplanation = photo
    ? "Перенесём точный товар и композицию одного кадра в генератор квадратного фото."
    : "Перенесём товар, хук, реплику и кадры в генератор и проверим их под 5 или 8 секунд.";
  const generationButtonLabel = photo
    ? "Создать фото по сценарию →"
    : "Создать ролик по сценарию →";
  const assigneeOptions = members.length
    ? members.map((member) => `<option value="${escapeHtml(member.profileId)}" ${member.profileId === selectedAssigneeId ? "selected" : ""}>${escapeHtml(member.label)}</option>`).join("")
    : '<option value="">Нет активных участников</option>';
  return `<fieldset class="product-research-scenario">
    <legend><span>${String(index + 1).padStart(2, "0")}</span> Гипотеза ${index + 1}${recommended ? ' <b class="badge badge-info">Рекомендуем начать</b>' : ""}</legend>
    <input type="hidden" name="scenario_${index}_generation_mode" value="${escapeHtml(item.generationMode)}" />
    <input type="hidden" name="scenario_${index}_generation_mode_reason" value="${escapeHtml(item.generationModeReason)}" />
    <div class="form-grid-2">
      ${textField(`scenario_${index}_title`, "Угол подачи", item.title, 180, disabled)}
      <label class="field"><span>Площадка</span><select name="scenario_${index}_platform" ${disabled ? "disabled" : ""}>${options.map(([value, label]) => `<option value="${value}" ${item.platform === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    </div>
    <div class="alert alert-info product-research-mode-recommendation" role="note">
      <strong>Автовыбор генератора:</strong>
      <span>${escapeHtml(generationModeLabel)}${item.generationModeReason ? ` · ${escapeHtml(item.generationModeReason)}` : ""}. Стоимость всё равно подтверждается отдельно перед рендером.</span>
    </div>
    <div class="alert ${readiness.ready ? "alert-success" : "alert-warning"} product-research-generation-readiness" role="status">
      <strong>${readiness.ready ? "Технически готово" : "Нужна правка до утверждения"}:</strong>
      <span>${escapeHtml(readiness.message)}</span>
    </div>
    ${textArea(`scenario_${index}_hook`, photo ? "Визуальный хук" : "Хук первых секунд", item.hook, photo ? "Что сразу выделит товар в одном статичном кадре" : "Что зритель увидит и услышит сразу", 800, disabled)}
    ${textArea(`scenario_${index}_script`, scriptLabel, item.script, scriptPlaceholder, 2400, disabled)}
    ${textArea(`scenario_${index}_shots`, photo ? "Композиция одного кадра" : "Кадры по порядку", item.shotList, photo ? "Композиция, свет и фон — по одному ограничению на строку" : "Один кадр на строку", 2400, disabled)}
    ${textField(`scenario_${index}_task_title`, "Название задачи", item.taskTitle, 180, disabled)}
    <label class="field"><span>Исполнитель задачи</span><select name="scenario_${index}_assignee_id" required ${disabled ? "disabled" : ""}>${assigneeOptions}</select><small class="field-hint">При утверждении эта задача будет назначена выбранному участнику.</small></label>
    ${disabled ? `
      <div class="product-research-generation-action">
        <div><strong>${generationHandoffAllowed ? "Сценарий утверждён" : "Снимок исследования устарел"}</strong><small>${generationHandoffAllowed ? approvedExplanation : "Прежний сценарий сохранён для истории, но сервер запретил его передачу в генерацию."}</small></div>
        <button class="btn ${recommended ? "" : "btn-secondary"} btn-small" type="button" data-action="generate-research-scenario" data-scenario-index="${index}" ${generationHandoffAllowed ? "" : "disabled"}>${generationHandoffAllowed ? (recommended ? `Начать с рекомендованного ${photo ? "фото" : "ролика"} →` : generationButtonLabel) : "Нужно новое исследование"}</button>
      </div>
    ` : ""}
  </fieldset>`;
}

function textField(name, label, value, maxLength, disabled = false) {
  return `<label class="field"><span>${escapeHtml(label)}</span><input name="${escapeHtml(name)}" value="${escapeHtml(value || "")}" minlength="3" maxlength="${maxLength}" required ${disabled ? "disabled" : ""} /></label>`;
}

function textArea(name, label, value, placeholder, maxLength, disabled = false) {
  return `<label class="field"><span>${escapeHtml(label)}</span><textarea name="${escapeHtml(name)}" maxlength="${maxLength}" placeholder="${escapeHtml(placeholder)}" ${disabled ? "disabled" : ""}>${escapeHtml(value || "")}</textarea></label>`;
}

function normalizeResearchMembers(value, defaultAssigneeId = "") {
  const currentId = String(defaultAssigneeId || "");
  const seen = new Set();
  return arrayValue(value).flatMap((item) => {
    const member = objectValue(item) || {};
    const profileId = String(member.profileId || member.profile_id || member.id || "");
    if (!profileId || seen.has(profileId) || (member.status && member.status !== "active")) return [];
    seen.add(profileId);
    const name = String(member.label || member.display_name || member.displayName || member.email || "Участник команды");
    return [{
      profileId,
      label: `${name}${profileId === currentId ? " (вы)" : ""}`,
    }];
  });
}

function normalizeGenerationMode(value) {
  const normalized = String(value || "").trim();
  return ["real_photo", "real_gen4", "real_seedance"].includes(normalized)
    ? normalized
    : "";
}

function confidenceCopy(value) {
  const confidence = normalizeConfidence(value);
  if (confidence === "high") return { label: "Высокая", description: "Есть несколько согласованных источников и достаточно конкретные вводные. Результат всё равно нужно проверить человеком." };
  if (confidence === "medium") return { label: "Средняя", description: "Часть выводов подтверждена, но остаются гипотезы. Уточните факты и источники до запуска." };
  return { label: "Низкая", description: "Источников или вводных недостаточно. Используйте сценарии только как идеи, а не как готовые факты." };
}

function normalizeConfidence(value) {
  if (typeof value === "number") {
    if (value >= 0.7) return "high";
    if (value >= 0.4) return "medium";
    return "low";
  }
  const normalized = String(value || "low").toLowerCase();
  if (["high", "высокая", "высокий"].includes(normalized)) return "high";
  if (["medium", "средняя", "средний"].includes(normalized)) return "medium";
  return "low";
}

function normalizeRecommendedScenarioPosition(value) {
  const position = Number(value);
  return Number.isInteger(position) && position >= 1 && position <= 3
    ? position
    : 0;
}

function normalizePlatform(value) {
  const normalized = String(value || "instagram").toLowerCase();
  if (normalized.includes("ozon") || normalized.includes("озон")) return "ozon";
  if (normalized.includes("wildberries") || normalized.includes("вайлдберриз") || normalized === "wb") return "wildberries";
  if (normalized.includes("youtube")) return "youtube";
  if (normalized.includes("vk") || normalized.includes("вк")) return "vk";
  return "instagram";
}

function formatAudience(value) {
  return arrayValue(value).map((item) => {
    const source = objectValue(item) || {};
    return [source.name, source.profile].filter(Boolean).join(": ");
  }).filter(Boolean).join("\n");
}

function formatFacts(value) {
  return arrayValue(value).map((item) => String(item?.statement || item?.fact || item || "")).filter(Boolean);
}

function formatForbiddenClaims(value) {
  return arrayValue(objectValue(value)?.forbidden).map((item) => String(item?.claim || item || "")).filter(Boolean);
}

function formatExtractedFacts(value) {
  return arrayValue(value).map((item) => String(item?.statement || item?.fact || item || "")).filter(Boolean).join("; ");
}

function formatShotList(value) {
  return arrayValue(value).map((item) => {
    if (typeof item === "string") return item;
    const source = objectValue(item) || {};
    const timing = source.seconds ? `${source.seconds}: ` : "";
    const voice = source.voiceover ? ` Голос: ${source.voiceover}.` : "";
    const screen = source.on_screen_text ? ` Текст: ${source.on_screen_text}.` : "";
    return `${timing}${source.visual || "Кадр"}.${voice}${screen}`;
  }).filter(Boolean).join("\n");
}

function scoreLabel(score) {
  if (score >= 80) return "Сильная основа";
  if (score >= 60) return "Есть потенциал";
  if (score >= 40) return "Нужна доработка";
  return "Недостаточно данных";
}

function clampScore(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.round(Math.min(100, Math.max(0, numeric))) : 0;
}

function boundedCount(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isSafeInteger(numeric) && numeric >= 0
    ? numeric
    : Math.max(0, Number(fallback) || 0);
}

function boundedInteger(value, minimum, maximum, fallback) {
  const numeric = Number(value);
  return Number.isSafeInteger(numeric) && numeric >= minimum && numeric <= maximum
    ? numeric
    : fallback;
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function stringArray(value) {
  return arrayValue(value).map(String).filter(Boolean);
}

function lines(value) {
  return Array.isArray(value) ? value.map(String).filter(Boolean).join("\n") : String(value || "");
}

function value(data, name) {
  return String(data.get(name) || "").trim();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character]);
}
