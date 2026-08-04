/**
 * The only module allowed to know the Supabase RPC/Storage contract.
 *
 * Database functions are narrow SECURITY DEFINER entry points. Every function
 * receives one `p_payload jsonb` argument and derives the current user from
 * auth.uid(); the browser never sends a user/profile/organization authority.
 * Keeping this boundary in one file makes a later transport change mechanical.
 */

export const RPC = Object.freeze({
  bootstrap: "creator_bootstrap",
  completeModule: "creator_complete_module",
  submitCourseCheck: "creator_submit_course_check",
  submitPlatformSimulator: "creator_submit_platform_simulator",
  submitExam: "creator_submit_exam",
  workspaceSection: "creator_workspace_section",
  generationMediaIdentity: "creator_generation_media_identity",
  generationLearningPolicy: "creator_generation_learning_policy",
  aiLearningControlRoom: "creator_ai_learning_control_room",
  registerAiKnowledgeSource: "creator_register_ai_knowledge_source",
  decideAiTeachingCard: "creator_decide_ai_teaching_card",
  generationRepairPolicy: "creator_generation_repair_policy",
  generationSpecStatus: "creator_generation_spec_status",
  prepareGenerationSpec: "creator_prepare_generation_spec",
  controlGenerationSpec: "creator_control_generation_spec",
  generationSpecEffectivePolicy: "creator_generation_spec_effective_policy",
  generationArchive: "creator_generation_archive",
  workspaceBrowser: "creator_workspace_browser",
  createWorkspaceFolder: "creator_create_workspace_folder",
  updateWorkspaceFolder: "creator_update_workspace_folder",
  moveWorkspaceItems: "creator_move_workspace_items",
  createMockBatch: "creator_create_mock_batch",
  recordMetric: "creator_record_metric",
  configureTrackingLink: "creator_configure_tracking_link",
  setWbAlias: "creator_set_wb_alias",
  decidePayout: "creator_decide_payout",
  confirmPlacement: "creator_confirm_placement",
  transitionTask: "creator_transition_task",
  createFeedback: "creator_create_feedback",
  registerMedia: "creator_register_media",
  captureEvent: "creator_capture_event",
  inviteAttempts: "creator_invite_delivery_attempts",
  managerDashboard: "creator_manager_dashboard",
  operationalHealth: "creator_operational_health",
  generationSpendOverview: "creator_generation_spend_overview",
  generationModelAcceptance: "creator_generation_model_acceptance",
  updateGenerationSpendPolicy: "creator_update_generation_spend_policy",
  createGenerationCampaign: "creator_create_generation_campaign",
  updateGenerationCampaignSpendPolicy: "creator_update_generation_campaign_spend_policy",
  myWork: "creator_my_work",
  notifications: "creator_notifications",
  markNotificationsRead: "creator_mark_notifications_read",
  trainingProgress: "creator_training_progress",
  saveTrainingProgress: "creator_save_training_progress",
  savePracticalProject: "creator_save_practical_project",
  decidePracticalProject: "creator_decide_practical_project",
  savedWorkViews: "creator_saved_work_views",
  startProductResearch: "creator_start_product_research",
  productResearchStatus: "creator_product_research_status",
  researchStageControlStatus: "creator_research_stage_control_status",
  controlResearchStage: "creator_control_research_stage",
  researchCategoryLearningStatus: "creator_research_category_learning_status",
  captureResearchCategoryReadiness: "creator_capture_research_category_readiness",
  correctResearchSourceAnalysis: "creator_correct_research_source_analysis",
  correctResearchYoutubeObservationAnalysis:
    "creator_correct_research_youtube_observation_analysis",
  configureResearchSourceCollectionPolicy:
    "creator_configure_research_source_collection_policy",
  researchWatchlistStatus: "creator_research_watchlist_status",
  configureResearchWatchlist: "creator_configure_research_watchlist",
  researchProviderStatus: "creator_research_provider_status",
  researchMarketCategoryRegistry: "creator_research_market_category_registry",
  resolveResearchMarketCategory: "creator_resolve_research_market_category",
  researchOutcomeLearningScopes: "creator_research_outcome_learning_scopes",
  researchOutcomeLearningStatus: "creator_research_outcome_learning_status",
  refreshResearchOutcomeLearning: "creator_refresh_research_outcome_learning",
  decideResearchOutcomeLearning: "creator_decide_research_outcome_learning",
  researchYoutubeOverview: "creator_research_youtube_overview",
  researchYoutubeStatus: "creator_research_youtube_status",
  requestResearchYoutubeCanary: "creator_request_research_youtube_canary",
  requestResearchYoutubeRefresh: "creator_request_research_youtube_refresh",
  decideResearchYoutubeRollout: "creator_decide_research_youtube_rollout",
  decideResearchYoutubeCandidate: "creator_decide_research_youtube_candidate",
  saveCreativeBriefDraft: "creator_save_creative_brief_draft",
  approveCreativeBrief: "creator_approve_creative_brief",
  contentReviewCatalog: "creator_content_review_catalog",
  prepareContentReviewEvidence: "creator_prepare_content_review_evidence",
  commitContentReviewEvidence: "creator_commit_content_review_evidence",
  startContentReview: "creator_start_content_review",
  startGeneratedVideoReview: "creator_start_generated_video_review",
  contentReviewStatus: "creator_content_review_status",
  decideContentReview: "creator_decide_content_review",
  approveGeneratedPhotoWithContext:
    "creator_approve_generated_photo_review_with_context",
  approveGeneratedVideoWithContext:
    "creator_approve_generated_video_review_with_context",
});

export const PRODUCT_RESEARCH_PLATFORMS = Object.freeze([
  "instagram",
  "youtube",
  "vk",
  "wildberries",
  "ozon",
]);
export const AI_PRODUCT_CATEGORIES = Object.freeze([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
export const AI_KNOWLEDGE_BUCKET = "contentengine-knowledge";
const AI_PRODUCT_CATEGORY_SET = new Set(AI_PRODUCT_CATEGORIES);
const AI_KNOWLEDGE_MIME_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
  "text/markdown",
  "text/plain",
]);
const PRODUCT_RESEARCH_PLATFORM_SET = new Set(PRODUCT_RESEARCH_PLATFORMS);
const RESEARCH_STAGE_SET = new Set([
  "sources",
  "category",
  "competitors",
  "trends",
  "guidance",
  "brief",
  "scenarios",
]);
const RESEARCH_STAGE_ACTION_SET = new Set([
  "patch",
  "reject",
  "revert",
  "fork",
  "recompute",
  "cancel",
]);
const RESEARCH_STAGE_HASH_PATTERN = /^[0-9a-f]{64}$/u;
const RESEARCH_STAGE_BRANCH_KEY_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/u;
const RESEARCH_COLLECTION_PROVIDER_PATTERN = /^[a-z][a-z0-9_.-]{1,79}$/u;
const RESEARCH_ANALYSIS_FORBIDDEN_KEYS = new Set([
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
const RESEARCH_SOURCE_ANALYSIS_SCHEMA_VERSION =
  "research-source-interpretation-v1";
const RESEARCH_SOURCE_ANALYSIS_CLASSIFICATIONS = new Set([
  "competitor",
  "adjacent",
  "trend_signal",
  "reference",
  "irrelevant",
  "unknown",
]);
const RESEARCH_SOURCE_ANALYSIS_CONFIDENCE = new Set([
  "low",
  "medium",
  "high",
]);
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA_VERSION =
  "research-youtube-observation-analysis-v1";
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS = new Set([
  "potential_competitor",
  "adjacent",
  "unknown",
]);
const RESEARCH_SOURCE_STRUCTURAL_SIGNAL_PATTERN =
  /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$/u;

const REAL_GENERATION_FUNCTION = "creator-generate";
const PRODUCT_RESEARCH_FUNCTION = "creator-product-research";
const RESEARCH_INGESTION_FUNCTION = "creator-research-ingestion";
const RESEARCH_SATELLITE_TIMEOUT_MS = 3500;
const RESEARCH_YOUTUBE_TERMS_VERSION = "youtube-developer-policies-2026-08-03-v1";
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
const CONTENT_REVIEW_FUNCTION = "creator-content-review";
const ACCESS_FUNCTION = "creator-access";
const PUBLIC_RECOVERY_FUNCTION = "creator-recovery";
const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8";
const PROVIDER_READINESS_RECEIPT_VERSION =
  "generation-provider-readiness-receipt-v2";
const PROVIDER_READINESS_UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const PROVIDER_READINESS_SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const PROVIDER_READINESS_TTL_MS = 15 * 60 * 1_000;
const PROVIDER_READINESS_FUTURE_SKEW_MS = 60 * 1_000;
const REAL_GENERATION_SKUS = Object.freeze({
  gen4_turbo: Object.freeze({
    audio: false,
    prompt_max_length: 1000,
    min_duration_seconds: 2,
    max_duration_seconds: 10,
    credits_per_second: 5,
  }),
  seedance2_fast: Object.freeze({
    audio: true,
    format: "9:16",
    prompt_max_length: 1200,
    min_duration_seconds: 4,
    max_duration_seconds: 15,
    credits_per_second: 29,
  }),
  seedream5_lite: Object.freeze({
    duration_seconds: 0,
    audio: false,
    format: "1:1",
    prompt_max_length: 1200,
    confirmation: "RUNWAY_SEEDREAM5_LITE_2K_USD_0.04",
    estimated_usd: "0.04",
  }),
});

function realGenerationSku(model, durationSeconds) {
  const normalizedModel = String(model || "");
  const base = REAL_GENERATION_SKUS[normalizedModel];
  const duration = Number(durationSeconds);
  if (!base) return null;
  if (normalizedModel === "seedream5_lite") {
    return duration === 0 ? base : null;
  }
  if (
    !Number.isInteger(duration)
    || duration < base.min_duration_seconds
    || duration > base.max_duration_seconds
  ) return null;
  const estimatedCredits = duration * base.credits_per_second;
  const estimatedUsd = (estimatedCredits / 100).toFixed(2);
  return Object.freeze({
    ...base,
    duration_seconds: duration,
    estimated_credits: estimatedCredits,
    estimated_usd: estimatedUsd,
    confirmation: normalizedModel === "seedance2_fast"
      ? `RUNWAY_SEEDANCE2_FAST_${duration}S_AUDIO_USD_${estimatedUsd}`
      : `RUNWAY_GEN4_TURBO_${duration}S_USD_${estimatedUsd}`,
  });
}

function normalizeApiGenerationProviderPreflight(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const model = typeof value.model === "string"
    ? value.model.trim()
    : "";
  const checkedAt = typeof value.checked_at === "string"
    ? value.checked_at.trim()
    : "";
  const expiresAt = typeof value.expires_at === "string"
    ? value.expires_at.trim()
    : "";
  const checkedAtMs = Date.parse(checkedAt);
  const expiresAtMs = Date.parse(expiresAt);
  const nowMs = Date.now();
  const sku = realGenerationSku(model, value.duration_seconds);
  if (
    sku === null ||
    value.provider !== "runway" ||
    value.ready !== true ||
    value.balance_sufficient !== true ||
    value.model_available !== true ||
    value.daily_quota_available !== true ||
    value.estimated_credits !== sku.estimated_credits ||
    (
      value.failure_code !== undefined
      && value.failure_code !== null
    ) ||
    value.learning_gate_version !== GENERATION_LEARNING_GATE_VERSION ||
    value.receipt_version !== PROVIDER_READINESS_RECEIPT_VERSION ||
    value.fresh !== true ||
    !PROVIDER_READINESS_UUID_PATTERN.test(
      String(value.receipt_id || "").trim(),
    ) ||
    !PROVIDER_READINESS_SHA256_PATTERN.test(
      String(value.receipt_hash || "").trim(),
    ) ||
    !Number.isFinite(checkedAtMs) ||
    !Number.isFinite(expiresAtMs) ||
    checkedAtMs > nowMs + PROVIDER_READINESS_FUTURE_SKEW_MS ||
    expiresAtMs <= nowMs ||
    expiresAtMs - checkedAtMs !== PROVIDER_READINESS_TTL_MS
  ) {
    return null;
  }
  return Object.freeze({
    provider: "runway",
    model,
    duration_seconds: sku.duration_seconds,
    ready: true,
    estimated_credits: sku.estimated_credits,
    balance_sufficient: true,
    model_available: true,
    daily_quota_available: true,
    learning_gate_version: GENERATION_LEARNING_GATE_VERSION,
    checked_at: checkedAt,
    expires_at: expiresAt,
    receipt_id: String(value.receipt_id).trim(),
    receipt_hash: String(value.receipt_hash).trim(),
    receipt_version: PROVIDER_READINESS_RECEIPT_VERSION,
    fresh: true,
  });
}

export function mediaKindRequiresProduct(kind) {
  return ["product_photo", "packshot"].includes(String(kind || "").trim());
}

async function settleResearchSatellite(callPromise, code) {
  let timeoutId;
  try {
    return await Promise.race([
      Promise.resolve(callPromise).then(
        (value) => ({ ok: true, value }),
        (error) => ({ ok: false, error }),
      ),
      new Promise((resolve) => {
        timeoutId = globalThis.setTimeout(() => resolve({
          ok: false,
          error: { code: `${code}_timeout` },
        }), RESEARCH_SATELLITE_TIMEOUT_MS);
      }),
    ]);
  } finally {
    if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId);
  }
}

function requireResearchOutcomeScope(value) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const marketCategoryId = String(
    source.market_category_id || source.marketCategoryId || "",
  ).trim().toLowerCase();
  const platform = String(source.platform || "").trim().toLowerCase();
  const model = String(source.model || "").trim().toLowerCase();
  if (
    !isUuid(marketCategoryId)
    || !RESEARCH_OUTCOME_PLATFORMS.has(platform)
    || !RESEARCH_OUTCOME_MODELS.has(model)
  ) {
    throw new CreatorApiError("Обновите исследование и выберите точный контур результата.", {
      code: "research_outcome_scope_invalid",
    });
  }
  return { market_category_id: marketCategoryId, platform, model };
}

function researchOutcomeScopeKey(scope) {
  const exact = requireResearchOutcomeScope(scope);
  return `${exact.market_category_id}:${exact.platform}:${exact.model}`;
}

function readResearchOutcomeScopeRegistry(value, expectedRunId) {
  const source = value?.data && typeof value.data === "object" && !Array.isArray(value.data)
    ? value.data
    : value && typeof value === "object" && !Array.isArray(value)
      ? value
      : null;
  if (
    !source
    || source.ok !== true
    || source.version !== "research-outcome-scope-registry-v1"
    || String(source.run_id || "").toLowerCase() !== expectedRunId
    || !isUuid(String(source.product_id || ""))
    || typeof source.truncated !== "boolean"
    || !Array.isArray(source.scopes)
    || source.scopes.length > 50
    || Number(source.returned_scope_count) !== source.scopes.length
  ) return null;
  const seen = new Set();
  const scopes = [];
  for (const item of source.scopes) {
    if (!item || typeof item !== "object" || Array.isArray(item)) return null;
    let scope;
    try {
      scope = requireResearchOutcomeScope(item.scope);
    } catch {
      return null;
    }
    const key = researchOutcomeScopeKey(scope);
    if (item.scope_key !== key || seen.has(key)) return null;
    const category = item.market_category;
    if (
      !category
      || typeof category !== "object"
      || Array.isArray(category)
      || String(category.market_category_id || "").toLowerCase()
        !== scope.market_category_id
      || typeof category.canonical_name !== "string"
      || !["active", "retired"].includes(String(category.status || ""))
    ) return null;
    seen.add(key);
    scopes.push({ key, scope, raw: item });
  }
  return { raw: source, scopes, truncated: source.truncated };
}

export class CreatorApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "CreatorApiError";
    this.code = details.code || "creator_api_error";
    this.serverCode = /^[a-z0-9_]{3,96}$/u.test(String(details.message || ""))
      ? String(details.message)
      : null;
    this.details = details.details || null;
    this.hint = details.hint || null;
    this.job = details.job && typeof details.job === "object" && !Array.isArray(details.job)
      ? { ...details.job }
      : null;
  }
}

export class CreatorApi {
  constructor(supabase, config) {
    this.supabase = supabase;
    this.config = config;
    this.rpcClient = supabase.schema(config.RPC_SCHEMA || "public");
    this.organizationId = null;
    this.storageBucket = config.STORAGE_BUCKET;
    this.storagePrefix = null;
    this.mutationKeys = readMutationKeys();
    this.researchRecomputeInvocations = new Set();
  }

  async call(functionName, payload = {}) {
    const { data, error } = await this.rpcClient.rpc(functionName, { p_payload: payload });

    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }

    if (data && typeof data === "object" && !Array.isArray(data) && data.error) {
      throw new CreatorApiError(toFriendlyMessage(data.error), data.error);
    }

    return data ?? {};
  }

  async bootstrap(clientContext = {}) {
    return this.call(RPC.bootstrap, {
      client_version: "supabase-spa-v1",
      ...clientContext,
    });
  }

  commitBootstrapContext(response) {
    const source = response?.data && typeof response.data === "object" ? response.data : response;
    const organizationId =
      source?.organization?.id ??
      source?.membership?.organization_id ??
      source?.organization_id ??
      null;
    const serverBucket = source?.storage?.bucket;
    if (serverBucket && serverBucket !== this.config.STORAGE_BUCKET) {
      throw new CreatorApiError("Защищённое хранилище вернуло неожиданный ответ.", {
        code: "storage_bucket_mismatch",
      });
    }
    const storageBucket = serverBucket || this.config.STORAGE_BUCKET;
    const storagePrefix = source?.storage?.path_prefix || null;

    this.organizationId = organizationId;
    this.storageBucket = storageBucket;
    this.storagePrefix = storagePrefix;
  }

  clearBootstrapContext() {
    this.organizationId = null;
    this.storageBucket = this.config.STORAGE_BUCKET;
    this.storagePrefix = null;
  }

  completeModule(moduleCode) {
    return this.mutate(RPC.completeModule, { module_code: moduleCode });
  }

  submitCourseCheck(moduleCode, answers, rationales = {}) {
    return this.mutate(RPC.submitCourseCheck, {
      module_code: moduleCode,
      answers,
      rationales,
    });
  }

  submitPlatformSimulator({ platformId, assessmentVersion = 1, decisions = {}, rationales = {} }) {
    const platform = String(platformId || "").trim().toLowerCase();
    if (!["instagram", "youtube", "vk"].includes(platform)) {
      throw new CreatorApiError("Выберите Instagram, YouTube или VK.", {
        code: "platform_simulator_platform_invalid",
      });
    }
    return this.mutate(RPC.submitPlatformSimulator, {
      platform,
      assessment_version: Number(assessmentVersion),
      decisions,
      rationales,
    });
  }

  submitExam(answers, rationales) {
    return this.mutate(RPC.submitExam, {
      module_code: "operator_final_exam",
      answers,
      rationales,
    });
  }

  workspaceSection(section, options = {}) {
    const payload = { section };
    if (options.page_size !== undefined) {
      const pageSize = Number(options.page_size);
      if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
        throw new CreatorApiError("Можно загрузить от 1 до 100 записей за один запрос.", {
          code: "workspace_page_size_invalid",
        });
      }
      payload.page_size = pageSize;
    }
    if (options.cursor !== undefined) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор истории имеет неверный формат.", {
          code: "workspace_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(
      RPC.workspaceSection,
      this.withOrganization(payload),
    ).then((response) => {
      if (section !== "generation") return response;

      const source = response?.data && typeof response.data === "object"
        ? response.data
        : response;
      const mediaIds = [...new Set(
        (Array.isArray(source?.media) ? source.media : [])
          .map((item) => String(item?.public_id || item?.id || "").trim())
          .filter((mediaId) => isUuid(mediaId)),
      )].slice(0, 100);
      if (!mediaIds.length) return response;

      return this.generationMediaIdentity(mediaIds)
        .then((identityResponse) =>
          mergeGenerationMediaIdentity(response, identityResponse)
        )
        .catch((error) => {
          console.warn(
            "Generation media identity unavailable",
            error?.serverCode || error?.code || "",
          );
          return mergeGenerationMediaIdentity(response, { items: [] });
        });
    });
  }

  generationMediaIdentity(mediaIds) {
    const normalized = [...new Set(
      (Array.isArray(mediaIds) ? mediaIds : [])
        .map((mediaId) => String(mediaId || "").trim())
        .filter(Boolean),
    )];
    if (
      normalized.length < 1
      || normalized.length > 100
      || normalized.some((mediaId) => !isUuid(mediaId))
    ) {
      throw new CreatorApiError("Не удалось проверить привязку фото к товару.", {
        code: "generation_media_identity_ids_invalid",
      });
    }
    return this.call(RPC.generationMediaIdentity, this.withOrganization({
      media_ids: normalized,
    }));
  }

  generationLearningPolicy({ mediaId, platform, model, productCategory }) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedPlatform = String(platform || "").trim().toLowerCase();
    const normalizedModel = String(model || "").trim().toLowerCase();
    const normalizedProductCategory = String(productCategory || "")
      .trim()
      .toLowerCase();
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Не удалось определить исходник для самообучения.", {
        code: "generation_learning_policy_media_invalid",
      });
    }
    if (!["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"].includes(normalizedPlatform)) {
      throw new CreatorApiError("Выберите площадку для подбора обученного ТЗ.", {
        code: "generation_learning_policy_scope_invalid",
      });
    }
    if (!Object.hasOwn(REAL_GENERATION_SKUS, normalizedModel)) {
      throw new CreatorApiError("Выберите режим генерации для обученного ТЗ.", {
        code: "generation_learning_policy_scope_invalid",
      });
    }
    if (
      ![
        "cosmetics",
        "baa",
        "sports_food",
        "food",
        "household",
        "apparel",
        "electronics",
        "other",
      ].includes(normalizedProductCategory)
    ) {
      throw new CreatorApiError("Выберите категорию для отдельного контура обучения.", {
        code: "generation_learning_policy_category_invalid",
      });
    }
    return this.call(RPC.generationLearningPolicy, this.withOrganization({
      media_id: normalizedMediaId,
      platform: normalizedPlatform,
      model: normalizedModel,
      product_category: normalizedProductCategory,
    }));
  }

  aiLearningControlRoom({ category = "cosmetics" } = {}) {
    const normalizedCategory = String(category || "").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(normalizedCategory)) {
      throw new CreatorApiError("Выберите точную товарную категорию ИИ‑центра.", {
        code: "ai_learning_category_invalid",
      });
    }
    return this.call(
      RPC.aiLearningControlRoom,
      this.withOrganization({ product_category: normalizedCategory }),
    );
  }

  registerAiKnowledgeSource(source = {}) {
    const productCategory = String(source.product_category || "")
      .trim()
      .toLowerCase();
    const sourceKind = String(source.source_kind || "").trim().toLowerCase();
    const title = String(source.title || "").replace(/\s+/gu, " ").trim();
    const note = String(source.note || "").replace(/\s+/gu, " ").trim();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Источник должен относиться к одной точной товарной категории.", {
        code: "ai_learning_category_invalid",
      });
    }
    if (!new Set(["link", "file"]).has(sourceKind)) {
      throw new CreatorApiError("Добавьте HTTPS‑ссылку или поддерживаемый файл.", {
        code: "ai_knowledge_source_kind_invalid",
      });
    }
    if (title.length < 2 || title.length > 180 || note.length > 1_000) {
      throw new CreatorApiError("Проверьте название и короткое пояснение к источнику.", {
        code: "ai_knowledge_source_copy_invalid",
      });
    }
    if (source.rights_confirmed !== true) {
      throw new CreatorApiError("Подтвердите право команды использовать источник для обучения.", {
        code: "ai_knowledge_source_rights_required",
      });
    }

    const payload = {
      product_category: productCategory,
      source_kind: sourceKind,
      title,
      note,
      rights_confirmed: true,
    };
    if (sourceKind === "link") {
      const sourceUrl = String(source.source_url || "").trim();
      let parsed;
      try {
        parsed = new URL(sourceUrl);
      } catch {
        parsed = null;
      }
      if (
        !parsed
        || parsed.protocol !== "https:"
        || parsed.username
        || parsed.password
        || sourceUrl.length > 2_048
      ) {
        throw new CreatorApiError("Добавьте публичную HTTPS‑ссылку без логина и пароля.", {
          code: "ai_knowledge_source_url_invalid",
        });
      }
      payload.source_url = parsed.href;
    } else {
      const objectKey = String(source.object_key || "").trim();
      const originalFilename = String(source.original_filename || "").trim();
      const mimeType = String(source.mime_type || "").trim().toLowerCase();
      const sizeBytes = Number(source.size_bytes);
      const sha256 = String(source.sha256 || "").trim().toLowerCase();
      this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
      if (
        originalFilename.length < 1
        || originalFilename.length > 240
        || !AI_KNOWLEDGE_MIME_TYPES.has(mimeType)
        || !Number.isInteger(sizeBytes)
        || sizeBytes < 1
        || sizeBytes > 25 * 1024 * 1024
        || !/^[0-9a-f]{64}$/u.test(sha256)
      ) {
        throw new CreatorApiError("Файл знаний не прошёл проверку типа, размера или контрольной суммы.", {
          code: "ai_knowledge_source_file_invalid",
        });
      }
      Object.assign(payload, {
        bucket: AI_KNOWLEDGE_BUCKET,
        object_key: objectKey,
        original_filename: originalFilename,
        mime_type: mimeType,
        size_bytes: sizeBytes,
        sha256,
      });
    }
    return this.mutate(RPC.registerAiKnowledgeSource, payload);
  }

  decideAiTeachingCard(input = {}) {
    const productCategory = String(input.product_category || "")
      .trim()
      .toLowerCase();
    const cardId = String(input.card_id || "").trim().toLowerCase();
    const cardHash = String(input.card_hash || "").trim().toLowerCase();
    const decision = String(input.decision || "").trim().toLowerCase();
    const cardVersion = Number(input.card_version);
    const expectedScopeVersion = Number(input.expected_scope_version);
    const reasonCode = String(input.reason_code || "").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Карточка обратной связи относится к другой категории.", {
        code: "ai_learning_category_invalid",
      });
    }
    if (
      !isUuid(cardId)
      || !/^[0-9a-f]{64}$/u.test(cardHash)
      || !["approve", "reject"].includes(decision)
      || !Number.isInteger(cardVersion)
      || cardVersion < 1
      || !Number.isInteger(expectedScopeVersion)
      || expectedScopeVersion < 0
      || !["operator_confirmed", "operator_rejected"].includes(reasonCode)
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Карточка изменилась. Обновите ИИ‑центр и повторите решение.", {
        code: "ai_teaching_decision_invalid",
      });
    }
    return this.mutate(RPC.decideAiTeachingCard, {
      product_category: productCategory,
      card_id: cardId,
      card_hash: cardHash,
      card_version: cardVersion,
      expected_scope_version: expectedScopeVersion,
      decision,
      reason_code: reasonCode,
      confirmation: true,
    });
  }


  generationRepairPolicy(reviewId) {
    const normalizedReviewId = String(reviewId || "").trim();
    if (!isUuid(normalizedReviewId)) {
      throw new CreatorApiError("Не удалось определить проверку для исправления.", {
        code: "generation_repair_review_invalid",
      });
    }
    return this.call(RPC.generationRepairPolicy, this.withOrganization({
      review_id: normalizedReviewId,
    }));
  }

  generationSpecStatus(context) {
    return this.call(
      RPC.generationSpecStatus,
      this.withOrganization(normalizeGenerationSpecReference(context)),
    );
  }

  prepareGenerationSpec(input = {}) {
    const exactScope = normalizeGenerationSpecScopeInput(input.exact_scope);
    const editableIntent = String(input.editable_intent || "").trim();
    const proposedPrompt = String(input.proposed_prompt || "").trim();
    const reason = String(input.reason || "").trim();
    if (
      editableIntent.length < 1
      || editableIntent.length > 1_200
      || proposedPrompt.length < 1
      || proposedPrompt.length > 1_200
      || reason.length < 3
      || reason.length > 500
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Проверьте замысел и подготовленное ТЗ перед сохранением версии.", {
        code: "generation_spec_prepare_payload_invalid",
      });
    }
    return this.mutate(RPC.prepareGenerationSpec, {
      exact_scope: exactScope,
      editable_intent: editableIntent,
      proposed_prompt: proposedPrompt,
      learning_context: normalizeGenerationSpecLearningContext(
        input.learning_context,
      ),
      repair_context: normalizeGenerationSpecRepairContext(
        input.repair_context,
      ),
      research_provenance: normalizeGenerationSpecResearchProvenance(
        input.research_provenance,
      ),
      performance_policy_provenance:
        normalizeGenerationSpecPerformanceProvenance(
          input.performance_policy_provenance,
        ),
      repair_provenance: normalizeGenerationSpecRepairProvenance(
        input.repair_provenance,
      ),
      ...(input.outcome_selection_id
        ? { outcome_selection_id: requireGenerationSpecUuid(
            input.outcome_selection_id,
            "generation_spec_outcome_selection_invalid",
          ) }
        : {}),
      confirmation: true,
      reason,
    });
  }

  controlGenerationSpec(input = {}) {
    const reference = normalizeGenerationSpecReference({
      spec_id: input.spec_id,
      spec_version: input.expected_spec_version,
      spec_hash: input.expected_spec_hash,
    });
    const action = String(input.action || "").trim().toLowerCase();
    const reason = String(input.reason || "").trim();
    if (
      !["patch", "approve", "reject", "revert", "recompute"].includes(action)
      || input.confirmation !== true
      || reason.length < 3
      || reason.length > 500
    ) {
      throw new CreatorApiError("Действие с версией ТЗ заполнено не полностью.", {
        code: "generation_spec_control_payload_invalid",
      });
    }
    const payload = {
      spec_id: reference.spec_id,
      expected_spec_version: reference.spec_version,
      expected_spec_hash: reference.spec_hash,
      action,
      confirmation: true,
      reason,
    };
    if (action === "patch") {
      payload.patch = normalizeGenerationSpecPatch(input.patch);
    }
    if (action === "revert") {
      const target = Number(input.target_spec_version);
      if (!Number.isInteger(target) || target < 1 || target >= reference.spec_version) {
        throw new CreatorApiError("Выберите существующую прошлую версию ТЗ.", {
          code: "generation_spec_revert_target_invalid",
        });
      }
      payload.target_spec_version = target;
    }
    return this.mutate(RPC.controlGenerationSpec, payload);
  }

  generationSpecEffectivePolicy(context) {
    return this.call(
      RPC.generationSpecEffectivePolicy,
      this.withOrganization(normalizeGenerationSpecReference(context)),
    );
  }

  savePracticalProject(payload) {
    return this.mutate(RPC.savePracticalProject, payload);
  }

  decidePracticalProject(payload) {
    return this.mutate(RPC.decidePracticalProject, payload);
  }

  generationArchive(options = {}) {
    const periods = new Set(["week", "4w", "12w", "all"]);
    const statuses = new Set(["all", "active", "ready", "issue"]);
    const period = String(options.period || "4w").trim().toLowerCase();
    const status = String(options.status || "all").trim().toLowerCase();
    const query = String(options.query || "").trim();
    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!periods.has(period)) {
      throw new CreatorApiError("Выберите доступный период архива.", {
        code: "generation_archive_period_invalid",
      });
    }
    if (!statuses.has(status)) {
      throw new CreatorApiError("Выберите доступную группу статусов.", {
        code: "generation_archive_status_invalid",
      });
    }
    if (query.length > 120 || /[\u0000-\u001f\u007f]/u.test(query)) {
      throw new CreatorApiError("Сократите поиск до 120 символов.", {
        code: "generation_archive_query_invalid",
      });
    }
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 запусков за один запрос.", {
        code: "generation_archive_page_size_invalid",
      });
    }
    const payload = {
      period,
      status,
      page_size: pageSize,
    };
    if (query) payload.query = query;
    if (options.cursor !== undefined && options.cursor !== null) {
      const cursor = options.cursor;
      if (
        !cursor
        || typeof cursor !== "object"
        || Array.isArray(cursor)
        || Object.keys(cursor).some((key) => !["at", "id"].includes(key))
        || !String(cursor.at || "").trim()
        || !String(cursor.id || "").trim()
      ) {
        throw new CreatorApiError("Курсор архива имеет неверный формат.", {
          code: "generation_archive_cursor_invalid",
        });
      }
      payload.cursor = {
        at: String(cursor.at).trim(),
        id: String(cursor.id).trim(),
      };
    }
    return this.call(RPC.generationArchive, this.withOrganization(payload));
  }

  workspaceBrowser(options = {}) {
    const payload = {};
    if (
      Object.prototype.hasOwnProperty.call(options, "folder_id")
      || Object.prototype.hasOwnProperty.call(options, "folderId")
    ) {
      const folderId = options.folder_id ?? options.folderId;
      payload.folder_id = folderId && folderId !== "root" ? String(folderId) : null;
    }
    if (options.page_size !== undefined) {
      const pageSize = Number(options.page_size);
      if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
        throw new CreatorApiError("Можно загрузить от 1 до 100 объектов за один запрос.", {
          code: "workspace_page_size_invalid",
        });
      }
      payload.page_size = pageSize;
    }
    if (options.search !== undefined) {
      const search = String(options.search || "").trim();
      if (search.length > 120 || /[\u0000-\u001f\u007f]/u.test(search)) {
        throw new CreatorApiError("Сократите запрос поиска до 120 символов.", {
          code: "workspace_search_invalid",
        });
      }
      if (search) payload.search = search;
    }
    if (options.entity_types !== undefined) {
      const supported = new Set(["media", "task"]);
      if (
        !Array.isArray(options.entity_types)
        || options.entity_types.length < 1
        || options.entity_types.length > 2
        || options.entity_types.some((type) => !supported.has(String(type)))
      ) {
        throw new CreatorApiError("Выберите материалы, задачи или оба типа объектов.", {
          code: "workspace_entity_types_invalid",
        });
      }
      payload.entity_types = [...new Set(options.entity_types.map(String))];
    }
    if (options.cursor !== undefined) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор рабочего пространства имеет неверный формат.", {
          code: "workspace_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.workspaceBrowser, this.withOrganization(payload));
  }

  createWorkspaceFolder({ name, parentId = null, colorToken = "emerald" }) {
    const folderName = String(name || "").trim();
    const color = String(colorToken || "emerald").trim().toLowerCase();
    if (!folderName || folderName.length > 120 || /[\u0000-\u001f\u007f]/u.test(folderName)) {
      throw new CreatorApiError("Укажите название папки длиной до 120 символов.", {
        code: "workspace_folder_name_invalid",
      });
    }
    if (!["emerald", "gold", "rose", "blue", "violet", "slate"].includes(color)) {
      throw new CreatorApiError("Выберите доступный цвет папки.", {
        code: "workspace_folder_color_invalid",
      });
    }
    return this.mutate(RPC.createWorkspaceFolder, {
      name: folderName,
      parent_id: parentId || null,
      color_token: color,
    });
  }

  updateWorkspaceFolder(folderId, changes = {}) {
    const expectedVersion = Number(changes.expectedVersion);
    if (!folderId || !Number.isInteger(expectedVersion) || expectedVersion < 1) {
      throw new CreatorApiError("Папка изменилась. Обновите рабочий стол и повторите действие.", {
        code: "workspace_folder_version_invalid",
      });
    }
    const payload = {
      folder_id: String(folderId),
      expected_version: expectedVersion,
    };
    if (changes.name !== undefined) {
      const name = String(changes.name || "").trim();
      if (!name || name.length > 120 || /[\u0000-\u001f\u007f]/u.test(name)) {
        throw new CreatorApiError("Укажите название папки длиной до 120 символов.", {
          code: "workspace_folder_name_invalid",
        });
      }
      payload.name = name;
    }
    if (Object.prototype.hasOwnProperty.call(changes, "parentId")) {
      payload.parent_id = changes.parentId || null;
    }
    if (changes.colorToken !== undefined) {
      payload.color_token = String(changes.colorToken || "").trim().toLowerCase();
    }
    if (changes.archive === true) payload.archive = true;
    if (Object.keys(payload).length === 2) {
      throw new CreatorApiError("Выберите изменение папки.", {
        code: "workspace_folder_update_payload_invalid",
      });
    }
    return this.mutate(RPC.updateWorkspaceFolder, payload);
  }

  moveWorkspaceItems(items, destinationFolderId = null) {
    const normalized = Array.isArray(items)
      ? items.map((item) => ({
          type: String(item?.type || ""),
          id: String(item?.id || ""),
        }))
      : [];
    if (
      normalized.length < 1
      || normalized.length > 100
      || normalized.some((item) => !["media", "task"].includes(item.type) || !item.id)
    ) {
      throw new CreatorApiError("Выберите от 1 до 100 доступных материалов или задач.", {
        code: "workspace_items_invalid",
      });
    }
    return this.mutate(RPC.moveWorkspaceItems, {
      destination_folder_id: destinationFolderId || null,
      items: normalized,
    });
  }

  inviteAttempts() {
    return this.call(RPC.inviteAttempts, this.withOrganization({}));
  }

  managerDashboard() {
    return this.call(RPC.managerDashboard, this.withOrganization({}));
  }

  operationalHealth() {
    return this.call(RPC.operationalHealth, this.withOrganization({}));
  }

  generationSpendOverview() {
    return this.call(RPC.generationSpendOverview, this.withOrganization({}));
  }

  generationModelAcceptance() {
    return this.call(
      RPC.generationModelAcceptance,
      this.withOrganization({}),
    );
  }

  updateGenerationSpendPolicy(policy = {}) {
    const dailyLimitMinor = normalizeSpendLimit(policy.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(policy.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(policy.per_request_limit_minor, "разовый");
    const enabled = policy.paid_generation_enabled === true;
    const expectedVersion = Number(policy.expected_version);
    const timezone = String(policy.timezone || "Europe/Moscow").trim();
    const reason = String(policy.reason || "").trim();
    if (!Number.isSafeInteger(expectedVersion) || expectedVersion < 0) {
      throw new CreatorApiError("Сводка лимитов устарела. Обновите остаток и повторите изменение.", {
        code: "generation_budget_policy_changed",
      });
    }
    if (!/^[A-Za-z0-9_+./-]{1,80}$/u.test(timezone)) {
      throw new CreatorApiError("Не удалось определить часовой пояс денежного лимита.", {
        code: "generation_budget_timezone_invalid",
      });
    }
    if (reason.length < 10 || reason.length > 500 || /[\u0000-\u001f\u007f]/u.test(reason)) {
      throw new CreatorApiError("Укажите причину изменения бюджета длиной от 10 до 500 символов.", {
        code: "generation_budget_reason_invalid",
      });
    }
    if (
      enabled
      && (perRequestLimitMinor > dailyLimitMinor || dailyLimitMinor > monthlyLimitMinor)
    ) {
      throw new CreatorApiError("Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.", {
        code: "generation_budget_limits_invalid",
      });
    }
    return this.mutate(RPC.updateGenerationSpendPolicy, {
      paid_generation_enabled: enabled,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      timezone,
      reason,
      expected_version: expectedVersion,
    });
  }

  createGenerationCampaign(campaign = {}) {
    const name = String(campaign.name || "").trim();
    const dailyLimitMinor = normalizeSpendLimit(campaign.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(campaign.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(campaign.per_request_limit_minor, "разовый");
    const reason = String(campaign.reason || "").trim();
    if (name.length < 2 || name.length > 160 || /[\u0000-\u001f\u007f]/u.test(name)) {
      throw new CreatorApiError("Название кампании должно содержать от 2 до 160 символов.", {
        code: "generation_campaign_name_invalid",
      });
    }
    validateCampaignPolicyInput({
      dailyLimitMinor,
      monthlyLimitMinor,
      perRequestLimitMinor,
      reason,
    });
    return this.mutate(RPC.createGenerationCampaign, {
      name,
      paid_generation_enabled: campaign.paid_generation_enabled === true,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      reason,
    });
  }

  updateGenerationCampaignSpendPolicy(campaignId, policy = {}) {
    const normalizedCampaignId = String(campaignId || "").trim();
    const dailyLimitMinor = normalizeSpendLimit(policy.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(policy.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(policy.per_request_limit_minor, "разовый");
    const reason = String(policy.reason || "").trim();
    const expectedVersion = Number(policy.expected_version);
    if (!isUuid(normalizedCampaignId)) {
      throw new CreatorApiError("Выберите кампанию из свежего списка.", {
        code: "paid_generation_campaign_required",
      });
    }
    if (!Number.isSafeInteger(expectedVersion) || expectedVersion < 1) {
      throw new CreatorApiError("Лимит кампании устарел. Обновите сводку.", {
        code: "generation_campaign_budget_policy_changed",
      });
    }
    validateCampaignPolicyInput({
      dailyLimitMinor,
      monthlyLimitMinor,
      perRequestLimitMinor,
      reason,
    });
    return this.mutate(RPC.updateGenerationCampaignSpendPolicy, {
      campaign_id: normalizedCampaignId,
      paid_generation_enabled: policy.paid_generation_enabled === true,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      expected_version: expectedVersion,
      reason,
    });
  }

  inspectAccess(email) {
    return this.invokeAccess("inspect", email);
  }

  repairAccess(email, requestId = "") {
    return this.invokeAccess("repair", email, { requestId });
  }

  async invokeAccess(action, email, { requestId = "" } = {}) {
    const normalizedAction = String(action || "").trim().toLowerCase();
    const normalizedEmail = normalizeAccessEmail(email);
    if (!["inspect", "repair"].includes(normalizedAction)) {
      throw new CreatorApiError("Не удалось определить безопасное действие с доступом.", {
        code: "access_action_invalid",
      });
    }
    if (!normalizedEmail) {
      throw new CreatorApiError("Укажите точный рабочий email участника.", {
        code: "access_email_invalid",
      });
    }

    const payload = { action: normalizedAction, email: normalizedEmail };
    if (normalizedAction === "repair") {
      const normalizedRequestId = String(requestId || "").trim() || crypto.randomUUID();
      if (!isUuid(normalizedRequestId)) {
        throw new CreatorApiError("Не удалось подготовить безопасный номер восстановления.", {
          code: "access_request_id_invalid",
        });
      }
      payload.request_id = normalizedRequestId;
    }

    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия завершилась. Войдите снова перед проверкой доступа.", {
        code: "auth_session_required",
      });
    }

    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(ACCESS_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Сервис доступа временно не ответил. Обновите сводку и повторите позже.", {
        code: "access_request_failed",
      });
    }
    if (error) throw await accessFunctionError(error);

    const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
      ? data.data
      : data;
    if (
      !source
      || typeof source !== "object"
      || Array.isArray(source)
      || source.ok !== true
      || String(source.action || "") !== normalizedAction
      || normalizeAccessEmail(source.email) !== normalizedEmail
      || !source.access
      || typeof source.access !== "object"
      || Array.isArray(source.access)
    ) {
      throw new CreatorApiError("Сервис доступа вернул неполный ответ. Новое письмо не отправляйте.", {
        code: "access_response_invalid",
      });
    }
    return source;
  }

  async requestPublicPasswordRecovery({ email, requestId }) {
    const normalizedEmail = normalizeAccessEmail(email);
    const normalizedRequestId = String(requestId || "").trim();
    if (!normalizedEmail) {
      throw new CreatorApiError("Укажите рабочую почту в формате name@company.ru.", {
        code: "public_recovery_email_invalid",
      });
    }
    if (!isUuid(normalizedRequestId)) {
      throw new CreatorApiError("Не удалось подготовить безопасный номер запроса.", {
        code: "public_recovery_request_id_invalid",
      });
    }

    return this.invokePublicRecovery("request", {
      email: normalizedEmail,
      request_id: normalizedRequestId,
    });
  }

  async getPublicRecoveryReceipt({ receiptToken } = {}) {
    const normalizedReceiptToken = normalizePublicRecoveryToken(receiptToken);
    if (!normalizedReceiptToken) {
      throw new CreatorApiError("Сохранённая квитанция недоступна.", {
        code: "public_recovery_receipt_invalid",
      });
    }
    return this.invokePublicRecovery("status", { receipt_token: normalizedReceiptToken });
  }

  async invokePublicRecovery(action, payload) {
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(PUBLIC_RECOVERY_FUNCTION, {
        body: { action, ...payload },
      }));
    } catch {
      throw new CreatorApiError("Сервис восстановления временно не ответил. Сохраните квитанцию и повторите проверку позже.", {
        code: "public_recovery_request_failed",
      });
    }
    if (error) throw await publicRecoveryFunctionError(error);
    return normalizePublicRecoveryResponse(data, action, payload);
  }

  myWork(options = {}) {
    const payload = {};
    const query = String(options.query || "").trim();
    if (query.length > 120 || /[\u0000-\u001f\u007f]/u.test(query)) {
      throw new CreatorApiError("Сократите запрос поиска до 120 символов.", {
        code: "my_work_query_invalid",
      });
    }
    if (query) payload.query = query;

    const itemTypes = normalizeStringArray(options.item_types ?? options.itemTypes);
    const supportedItemTypes = new Set(["task", "generation", "review", "placement", "payout"]);
    if (
      itemTypes.length > supportedItemTypes.size
      || itemTypes.some((itemType) => !supportedItemTypes.has(itemType))
    ) {
      throw new CreatorApiError("Выберите доступные типы рабочих объектов.", {
        code: "my_work_item_types_invalid",
      });
    }
    if (itemTypes.length) payload.item_types = itemTypes;

    const statuses = normalizeStringArray(options.statuses);
    if (
      statuses.length > 20
      || statuses.some((status) => !/^[a-z0-9_-]{1,80}$/u.test(status))
    ) {
      throw new CreatorApiError("Проверьте выбранные статусы очереди.", {
        code: "my_work_statuses_invalid",
      });
    }
    if (statuses.length) payload.statuses = statuses;

    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 рабочих объектов.", {
        code: "my_work_page_size_invalid",
      });
    }
    payload.page_size = pageSize;
    if (options.cursor !== undefined && options.cursor !== null) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор рабочей очереди имеет неверный формат.", {
          code: "my_work_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.myWork, this.withOrganization(payload));
  }

  notifications(options = {}) {
    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 уведомлений.", {
        code: "notifications_page_size_invalid",
      });
    }
    const payload = {
      unread_only: options.unread_only === true,
      page_size: pageSize,
    };
    if (options.cursor !== undefined && options.cursor !== null) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор уведомлений имеет неверный формат.", {
          code: "notifications_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.notifications, this.withOrganization(payload));
  }

  markNotificationsRead(notificationIds, isRead = true) {
    const ids = normalizeStringArray(notificationIds);
    if (
      ids.length < 1
      || ids.length > 100
      || ids.some((id) => !/^[0-9a-f]{8}-[0-9a-f-]{27,36}$/iu.test(id))
    ) {
      throw new CreatorApiError("Выберите от 1 до 100 уведомлений.", {
        code: "notification_ids_invalid",
      });
    }
    return this.mutate(RPC.markNotificationsRead, {
      notification_ids: ids,
      is_read: isRead === true,
    });
  }

  markAllNotificationsRead() {
    return this.mutate(RPC.markNotificationsRead, {
      all_unread: true,
      is_read: true,
    });
  }

  trainingProgress(moduleCode = "") {
    const normalizedModuleCode = String(moduleCode || "").trim();
    if (
      normalizedModuleCode
      && !/^[a-z0-9_:-]{1,120}$/iu.test(normalizedModuleCode)
    ) {
      throw new CreatorApiError("Код учебного блока имеет неверный формат.", {
        code: "training_module_code_invalid",
      });
    }
    return this.call(RPC.trainingProgress, this.withOrganization(
      normalizedModuleCode ? { module_code: normalizedModuleCode } : {},
    ));
  }

  saveTrainingProgress(progress) {
    const moduleCode = String(progress?.module_code || "").trim();
    const walkthroughId = String(progress?.walkthrough_id || "").trim();
    if (
      !/^[a-z0-9_:-]{1,120}$/iu.test(moduleCode)
      || !/^[a-z0-9_:-]{1,160}$/iu.test(walkthroughId)
    ) {
      throw new CreatorApiError("Не удалось определить учебный тренажёр.", {
        code: "training_progress_identity_invalid",
      });
    }
    const completedFrameIds = normalizeStringArray(progress?.completed_frame_ids);
    if (
      completedFrameIds.length > 200
      || completedFrameIds.some((frameId) => frameId.length > 160)
    ) {
      throw new CreatorApiError("Прогресс учебного тренажёра имеет неверный формат.", {
        code: "training_progress_frames_invalid",
      });
    }
    const positionSeconds = Number(progress?.position_seconds || 0);
    if (!Number.isFinite(positionSeconds) || positionSeconds < 0 || positionSeconds > 86_400) {
      throw new CreatorApiError("Позиция учебного видео имеет неверный формат.", {
        code: "training_progress_position_invalid",
      });
    }
    const payload = {
      module_code: moduleCode,
      walkthrough_id: walkthroughId,
      current_frame_id: progress?.current_frame_id
        ? String(progress.current_frame_id).slice(0, 160)
        : null,
      position_seconds: positionSeconds,
      completed_frame_ids: completedFrameIds,
      completed: progress?.completed === true,
    };
    if (progress?.expected_version !== undefined && progress?.expected_version !== null) {
      const expectedVersion = Number(progress.expected_version);
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
        throw new CreatorApiError("Версия учебного прогресса устарела.", {
          code: "training_progress_version_invalid",
        });
      }
      payload.expected_version = expectedVersion;
    }
    return this.mutate(RPC.saveTrainingProgress, payload);
  }

  savedWorkViews(options = {}) {
    const action = String(options.action || "list").trim().toLowerCase();
    if (!["list", "upsert", "delete", "set_default"].includes(action)) {
      throw new CreatorApiError("Неизвестное действие с сохранённым фильтром.", {
        code: "saved_work_view_action_invalid",
      });
    }
    const payload = { action };
    if (options.view_id) payload.view_id = String(options.view_id);
    if (options.expected_version !== undefined) {
      const expectedVersion = Number(options.expected_version);
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
        throw new CreatorApiError("Версия сохранённого фильтра устарела.", {
          code: "saved_work_view_version_invalid",
        });
      }
      payload.expected_version = expectedVersion;
    }
    if (action === "upsert") {
      const name = String(options.name || "").trim();
      if (name.length < 2 || name.length > 80 || /[\u0000-\u001f\u007f]/u.test(name)) {
        throw new CreatorApiError("Введите название фильтра от 2 до 80 символов.", {
          code: "saved_work_view_name_invalid",
        });
      }
      payload.name = name;
      if (
        options.is_default !== undefined
        && typeof options.is_default !== "boolean"
      ) {
        throw new CreatorApiError("Признак фильтра по умолчанию имеет неверный формат.", {
          code: "saved_work_view_is_default_invalid",
        });
      }
      payload.is_default = options.is_default === true;
      payload.filters = {
        query: String(options.filters?.query || "").trim().slice(0, 120),
        statuses: normalizeStringArray(options.filters?.statuses).slice(0, 20),
        item_types: normalizeStringArray(
          options.filters?.item_types ?? options.filters?.itemTypes,
        ).filter((itemType) => ["task", "generation", "review", "placement", "payout"].includes(itemType)),
      };
    }
    if (action === "list") {
      return this.call(RPC.savedWorkViews, this.withOrganization(payload));
    }
    return this.mutate(RPC.savedWorkViews, payload);
  }

  async startProductResearch(input, { onRunCreated } = {}) {
    const productName = String(input?.product_name || "").trim();
    const sku = String(input?.sku || "").trim();
    if (!productName || !sku || productName.length > 180 || sku.length > 120) {
      throw new CreatorApiError("Укажите название товара и проверьте артикул.", {
        code: "product_research_input_invalid",
      });
    }
    if (input?.paid_analysis_ack !== true) {
      throw new CreatorApiError("Подтвердите платный ИИ-анализ перед запуском.", {
        code: "product_research_paid_confirmation_required",
      });
    }
    if (
      !Array.isArray(input?.platforms)
      || input.platforms.length < 1
      || input.platforms.some((platform) =>
        !PRODUCT_RESEARCH_PLATFORM_SET.has(String(platform))
      )
    ) {
      throw new CreatorApiError("Выберите хотя бы одну площадку для будущих роликов.", {
        code: "product_research_platform_required",
      });
    }

    const created = await this.mutate(RPC.startProductResearch, input);
    const source = created?.data && typeof created.data === "object" ? created.data : created;
    const run = source?.run || source?.research || {};
    const runId = String(run?.id || source?.run_id || source?.research_id || source?.id || "").trim();
    if (!runId) {
      throw new CreatorApiError("Сервер не вернул номер исследования. Обновите раздел и повторите.", {
        code: "product_research_run_missing",
      });
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({ id: runId, status: String(run?.status || "queued") });
      } catch {
        // Recovery storage is a UI convenience; it must not cancel a paid run.
      }
    }

    let accepted;
    try {
      accepted = await this.invokeProductResearch({
        action: "analyze",
        research_id: runId,
      });
    } catch (error) {
      error.job = { id: runId, status: String(run?.status || "queued") };
      throw error;
    }
    return { ...source, run: { ...run, id: runId }, analysis_request: accepted };
  }

  async productResearchStatus(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const scopedPayload = this.withOrganization({ run_id: normalizedRunId });
    const requestedOutcomeScope = options?.outcome_scope
      ? requireResearchOutcomeScope(options.outcome_scope)
      : null;
    const [
      status,
      monitorResult,
      providerResult,
      marketRegistryResult,
      outcomeScopeRegistryResult,
      youtubeOverviewResult,
      categoryLearningResult,
    ] = await Promise.all([
      this.call(RPC.productResearchStatus, scopedPayload),
      settleResearchSatellite(
        this.call(RPC.researchWatchlistStatus, scopedPayload),
        "research_watchlist_status",
      ),
      settleResearchSatellite(
        this.call(RPC.researchProviderStatus, scopedPayload),
        "research_provider_status",
      ),
      settleResearchSatellite(
        this.call(RPC.researchMarketCategoryRegistry, scopedPayload),
        "research_market_registry",
      ),
      settleResearchSatellite(
        this.call(RPC.researchOutcomeLearningScopes, {
          ...scopedPayload,
          limit: 50,
        }),
        "research_outcome_scope_registry",
      ),
      settleResearchSatellite(
        this.call(RPC.researchYoutubeOverview, {
          ...scopedPayload,
          limit: 12,
        }),
        "research_youtube_overview",
      ),
      settleResearchSatellite(
        this.call(RPC.researchCategoryLearningStatus, scopedPayload),
        "research_category_learning_status",
      ),
    ]);
    const statusRoot = status?.data && typeof status.data === "object"
      && !Array.isArray(status.data)
      ? status.data
      : status;
    const result = {
      ...(statusRoot && typeof statusRoot === "object" ? statusRoot : {}),
    };
    if (!monitorResult.ok) {
      console.warn(
        "Research watchlist status unavailable",
        monitorResult.error?.serverCode || monitorResult.error?.code || "",
      );
      result.watchlist_monitor_unavailable = true;
    } else {
      const monitor = monitorResult.value?.data
        && typeof monitorResult.value.data === "object"
        && !Array.isArray(monitorResult.value.data)
        ? monitorResult.value.data
        : monitorResult.value;
      result.watchlist = monitor?.watchlist ?? null;
      result.watchlist_history = Array.isArray(monitor?.snapshots)
        ? monitor.snapshots
        : [];
      result.watchlist_proposal = monitor?.proposal ?? null;
      result.watchlist_guidance = monitor?.guidance ?? null;
      result.watchlist_monitor_unavailable = false;
    }
    if (!providerResult.ok) {
      console.warn(
        "Research provider control status unavailable",
        providerResult.error?.serverCode || providerResult.error?.code || "",
      );
      result.research_provider_control = null;
      result.research_provider_control_unavailable = true;
    } else {
      result.research_provider_control = providerResult.value?.data
        && typeof providerResult.value.data === "object"
        && !Array.isArray(providerResult.value.data)
        ? providerResult.value.data
        : providerResult.value;
      result.research_provider_control_unavailable = false;
    }
    if (!marketRegistryResult.ok) {
      console.warn(
        "Research market category registry unavailable",
        marketRegistryResult.error?.serverCode || marketRegistryResult.error?.code || "",
      );
      result.research_market_registry = null;
      result.research_market_registry_unavailable = true;
    } else {
      result.research_market_registry = marketRegistryResult.value?.data
        && typeof marketRegistryResult.value.data === "object"
        && !Array.isArray(marketRegistryResult.value.data)
        ? marketRegistryResult.value.data
        : marketRegistryResult.value;
      result.research_market_registry_unavailable = false;
    }
    if (!categoryLearningResult.ok) {
      console.warn(
        "Research category evidence readiness unavailable",
        categoryLearningResult.error?.serverCode
          || categoryLearningResult.error?.code
          || "",
      );
      result.research_category_learning = null;
      result.research_category_learning_unavailable = true;
    } else {
      result.research_category_learning = categoryLearningResult.value?.data
        && typeof categoryLearningResult.value.data === "object"
        && !Array.isArray(categoryLearningResult.value.data)
        ? categoryLearningResult.value.data
        : categoryLearningResult.value;
      result.research_category_learning_unavailable = false;
    }
    let outcomeScopeRegistry = null;
    if (!outcomeScopeRegistryResult.ok) {
      console.warn(
        "Research outcome scope registry unavailable",
        outcomeScopeRegistryResult.error?.serverCode
          || outcomeScopeRegistryResult.error?.code
          || "",
      );
      result.research_outcome_scope_registry = null;
      result.research_outcome_scope_registry_unavailable = true;
    } else {
      outcomeScopeRegistry = readResearchOutcomeScopeRegistry(
        outcomeScopeRegistryResult.value,
        normalizedRunId,
      );
      result.research_outcome_scope_registry = outcomeScopeRegistry?.raw || null;
      result.research_outcome_scope_registry_unavailable = !outcomeScopeRegistry;
    }
    let outcomeScope = null;
    if (outcomeScopeRegistry) {
      if (requestedOutcomeScope) {
        const requestedKey = researchOutcomeScopeKey(requestedOutcomeScope);
        outcomeScope = outcomeScopeRegistry.scopes
          .find((entry) => entry.key === requestedKey)?.scope || null;
      } else if (!outcomeScopeRegistry.truncated && outcomeScopeRegistry.scopes.length === 1) {
        outcomeScope = outcomeScopeRegistry.scopes[0].scope;
      }
    }
    result.research_outcome_learning_scope = outcomeScope;
    result.research_outcome_learning_scope_missing = outcomeScope === null;
    if (outcomeScope) {
      const outcomeResult = await settleResearchSatellite(
        this.call(
          RPC.researchOutcomeLearningStatus,
          this.withOrganization(outcomeScope),
        ),
        "research_outcome_learning_status",
      );
      if (!outcomeResult.ok) {
        console.warn(
          "Research outcome learning status unavailable",
          outcomeResult.error?.serverCode || outcomeResult.error?.code || "",
        );
        result.research_outcome_learning = null;
        result.research_outcome_learning_unavailable = true;
      } else {
        result.research_outcome_learning = outcomeResult.value?.data
          && typeof outcomeResult.value.data === "object"
          && !Array.isArray(outcomeResult.value.data)
          ? outcomeResult.value.data
          : outcomeResult.value;
        result.research_outcome_learning_unavailable = false;
      }
    } else {
      result.research_outcome_learning = null;
      result.research_outcome_learning_unavailable = false;
    }
    let youtubeOverview = null;
    if (!youtubeOverviewResult.ok) {
      console.warn(
        "Research YouTube overview unavailable",
        youtubeOverviewResult.error?.serverCode
          || youtubeOverviewResult.error?.code
          || "",
      );
      result.research_youtube_overview = null;
      result.research_youtube_overview_unavailable = true;
      result.research_youtube_latest = null;
      result.research_youtube_latest_unavailable = true;
    } else {
      const candidate = youtubeOverviewResult.value?.data
        && typeof youtubeOverviewResult.value.data === "object"
        && !Array.isArray(youtubeOverviewResult.value.data)
        ? youtubeOverviewResult.value.data
        : youtubeOverviewResult.value;
      youtubeOverview = candidate
        && typeof candidate === "object"
        && !Array.isArray(candidate)
        && candidate.ok === true
        && candidate.version === "research-youtube-live-ingestion-v1"
        && String(candidate.run_id || "").toLowerCase() === normalizedRunId
        && Array.isArray(candidate.ingestions)
        && candidate.ingestions.length <= 20
        ? candidate
        : null;
      result.research_youtube_overview = youtubeOverview;
      result.research_youtube_overview_unavailable = !youtubeOverview;
      const latestIngestionId = String(
        youtubeOverview?.ingestions?.[0]?.ingestion_id || "",
      ).trim().toLowerCase();
      if (isUuid(latestIngestionId)) {
        const youtubeStatusResult = await settleResearchSatellite(
          this.call(RPC.researchYoutubeStatus, {
            ingestion_id: latestIngestionId,
          }),
          "research_youtube_status",
        );
        if (youtubeStatusResult.ok) {
          result.research_youtube_latest = youtubeStatusResult.value?.data
            && typeof youtubeStatusResult.value.data === "object"
            && !Array.isArray(youtubeStatusResult.value.data)
            ? youtubeStatusResult.value.data
            : youtubeStatusResult.value;
          result.research_youtube_latest_unavailable = false;
        } else {
          result.research_youtube_latest = null;
          result.research_youtube_latest_unavailable = true;
        }
      } else {
        result.research_youtube_latest = null;
        result.research_youtube_latest_unavailable = false;
      }
    }
    return result;
  }

  researchStageControlStatus(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const payload = { run_id: normalizedRunId };
    if (options.branch_id !== undefined || options.branchId !== undefined) {
      const branchId = String(
        options.branch_id ?? options.branchId ?? "",
      ).trim().toLowerCase();
      if (!isUuid(branchId)) {
        throw new CreatorApiError("Не удалось определить ветку исправлений.", {
          code: "research_stage_branch_invalid",
        });
      }
      payload.branch_id = branchId;
    }
    if (options.history_limit !== undefined || options.historyLimit !== undefined) {
      const historyLimit = Number(
        options.history_limit ?? options.historyLimit,
      );
      if (!Number.isInteger(historyLimit) || historyLimit < 1 || historyLimit > 100) {
        throw new CreatorApiError("История этапов может содержать от 1 до 100 событий.", {
          code: "research_stage_history_limit_invalid",
        });
      }
      payload.history_limit = historyLimit;
    }
    return this.call(
      RPC.researchStageControlStatus,
      this.withOrganization(payload),
    );
  }

  async controlResearchStage(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const branchId = String(
      options.branch_id ?? options.branchId ?? "",
    ).trim().toLowerCase();
    const stage = String(options.stage || "").trim().toLowerCase();
    const action = String(options.action || "").trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedArtifactId = String(
      options.expected_artifact_id ?? options.expectedArtifactId ?? "",
    ).trim().toLowerCase();
    const expectedContentHash = String(
      options.expected_content_hash ?? options.expectedContentHash ?? "",
    ).trim().toLowerCase();
    const expectedBranchRevisionHash = String(
      options.expected_branch_revision_hash
        ?? options.expectedBranchRevisionHash
        ?? "",
    ).trim().toLowerCase();
    const reason = String(options.reason || "").trim();
    if (
      !isUuid(branchId)
      || !RESEARCH_STAGE_SET.has(stage)
      || !RESEARCH_STAGE_ACTION_SET.has(action)
      || !isUuid(expectedHeadEventId)
      || !isUuid(expectedArtifactId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedContentHash)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedBranchRevisionHash)
      || reason.length < 3
      || reason.length > 500
      || options.confirmation !== true
    ) {
      throw new CreatorApiError("Снимок этапа изменился или команда заполнена не полностью.", {
        code: "research_stage_control_invalid",
      });
    }

    const payload = {
      run_id: normalizedRunId,
      branch_id: branchId,
      stage,
      action,
      expected_head_event_id: expectedHeadEventId,
      expected_artifact_id: expectedArtifactId,
      expected_content_hash: expectedContentHash,
      expected_branch_revision_hash: expectedBranchRevisionHash,
      reason,
      confirmation: true,
    };
    if (action === "patch") {
      const replacement = options.replacement;
      const userInput = String(
        options.user_input ?? options.userInput ?? "",
      ).trim();
      if (
        !replacement
        || typeof replacement !== "object"
        || Array.isArray(replacement)
        || stableStringify(replacement).length > 524_288
        || userInput.length < 3
        || userInput.length > 4_000
      ) {
        throw new CreatorApiError("Для правки нужен структурированный JSON и объяснение от 3 до 4000 символов.", {
          code: "research_stage_patch_invalid",
        });
      }
      payload.replacement = replacement;
      payload.user_input = userInput;
    } else if (action === "revert") {
      const targetArtifactId = String(
        options.target_artifact_id ?? options.targetArtifactId ?? "",
      ).trim().toLowerCase();
      if (!isUuid(targetArtifactId) || targetArtifactId === expectedArtifactId) {
        throw new CreatorApiError("Выберите другую точную версию этапа для отката.", {
          code: "research_stage_revert_invalid",
        });
      }
      payload.target_artifact_id = targetArtifactId;
    } else if (action === "fork") {
      const newBranchKey = String(
        options.new_branch_key ?? options.newBranchKey ?? "",
      ).trim().toLowerCase();
      if (
        newBranchKey === "main"
        || newBranchKey.length < 3
        || !RESEARCH_STAGE_BRANCH_KEY_PATTERN.test(newBranchKey)
      ) {
        throw new CreatorApiError("Ключ новой ветки: 3–64 строчных латинских символа, цифры, _ или -.", {
          code: "research_stage_fork_invalid",
        });
      }
      payload.new_branch_key = newBranchKey;
    } else if (action === "recompute") {
      const userInput = String(
        options.user_input ?? options.userInput ?? "",
      ).trim();
      if (
        stage === "sources"
        || options.paid_analysis_ack !== true
        || userInput.length < 3
        || userInput.length > 4_000
      ) {
        throw new CreatorApiError("Для пересчёта опишите изменение и отдельно подтвердите платный анализ.", {
          code: "research_stage_recompute_invalid",
        });
      }
      payload.user_input = userInput;
      payload.paid_analysis_ack = true;
    }

    const prepared = await this.mutate(RPC.controlResearchStage, payload);
    if (action !== "recompute") return prepared;

    const source = prepared?.data && typeof prepared.data === "object"
      && !Array.isArray(prepared.data)
      ? prepared.data
      : prepared;
    const recompute = source?.recompute_request;
    const requestId = String(recompute?.request_id || "").trim().toLowerCase();
    const childRunId = String(recompute?.child_run_id || "").trim().toLowerCase();
    if (
      !recompute
      || typeof recompute !== "object"
      || Array.isArray(recompute)
      || !isUuid(requestId)
      || !isUuid(childRunId)
      || recompute.status !== "queued"
      || recompute.paid_analysis_ack !== true
      || recompute.automatic_provider_action !== false
      || recompute.max_provider_attempts !== 1
      || recompute.invoke?.action !== "analyze"
      || String(recompute.invoke?.research_id || "").toLowerCase() !== childRunId
    ) {
      throw new CreatorApiError("Запрос пересчёта сохранён, но точный дочерний запуск не подтверждён. Не повторяйте команду.", {
        code: "research_stage_recompute_prepare_invalid",
      });
    }

    if (this.researchRecomputeInvocations.has(requestId)) {
      return {
        ...source,
        analysis_request: {
          ok: true,
          skipped: true,
          reason: "recompute_invoke_already_attempted",
        },
      };
    }
    this.researchRecomputeInvocations.add(requestId);
    try {
      const accepted = await this.invokeProductResearch({
        action: "analyze",
        research_id: childRunId,
      });
      return { ...source, analysis_request: accepted };
    } catch (error) {
      error.job = {
        id: childRunId,
        status: "queued",
        recompute_request_id: requestId,
      };
      error.stageControl = source;
      throw error;
    }
  }

  async resumeResearchStageRecompute(childRunId, requestId) {
    const normalizedChildRunId = String(childRunId || "").trim().toLowerCase();
    const normalizedRequestId = String(requestId || "").trim().toLowerCase();
    if (!isUuid(normalizedChildRunId) || !isUuid(normalizedRequestId)) {
      throw new CreatorApiError("Сохранённый пересчёт изменился. Сначала обновите его статус.", {
        code: "research_stage_recompute_resume_invalid",
      });
    }
    try {
      return await this.invokeProductResearch({
        action: "analyze",
        research_id: normalizedChildRunId,
      });
    } catch (error) {
      error.job = {
        id: normalizedChildRunId,
        status: "queued",
        recompute_request_id: normalizedRequestId,
      };
      throw error;
    }
  }

  researchCategoryLearningStatus(runId) {
    const normalizedRunId = this.requireResearchRunId(runId);
    return this.call(
      RPC.researchCategoryLearningStatus,
      this.withOrganization({ run_id: normalizedRunId }),
    );
  }

  async captureResearchCategoryReadiness(runId, expectedEvidenceHash) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const normalizedHash = String(expectedEvidenceHash || "")
      .trim()
      .toLowerCase();
    if (!RESEARCH_STAGE_HASH_PATTERN.test(normalizedHash)) {
      throw new CreatorApiError(
        "Снимок готовности устарел. Обновите доказательную базу категории.",
        { code: "research_category_readiness_hash_invalid" },
      );
    }
    const response = await this.mutate(RPC.captureResearchCategoryReadiness, {
      run_id: normalizedRunId,
      expected_evidence_hash: normalizedHash,
    });
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    const snapshot = source?.snapshot;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "metric_kind",
        "source_ledger_rows_registered",
        "snapshot",
        "external_call_started",
      ])
      || source.ok !== true
      || source.metric_kind !== "category_evidence_readiness_not_model_iq"
      || source.external_call_started !== false
      || !Number.isInteger(source.source_ledger_rows_registered)
      || source.source_ledger_rows_registered < 0
      || !hasExactObjectKeys(snapshot, [
        "snapshot_id",
        "score",
        "dimensions",
        "evidence_hash",
        "snapshot_hash",
        "captured_at",
      ])
      || !isUuid(String(snapshot.snapshot_id || "").toLowerCase())
      || !Number.isInteger(snapshot.score)
      || snapshot.score < 0
      || snapshot.score > 100
      || !Array.isArray(snapshot.dimensions)
      || snapshot.dimensions.length !== 6
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(snapshot.evidence_hash || ""))
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(snapshot.snapshot_hash || ""))
      || typeof snapshot.captured_at !== "string"
      || !Number.isFinite(Date.parse(snapshot.captured_at))
    ) {
      throw new CreatorApiError(
        "Снимок готовности сохранён с неожиданным ответом. Не повторяйте действие автоматически.",
        { code: "research_category_readiness_capture_invalid" },
      );
    }
    return source;
  }

  async correctResearchSourceAnalysis(options = {}) {
    const sourceLedgerId = String(
      options.source_ledger_id ?? options.sourceLedgerId ?? "",
    ).trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedHeadHash = String(
      options.expected_head_hash ?? options.expectedHeadHash ?? "",
    ).trim().toLowerCase();
    const correctionReason = String(
      options.correction_reason ?? options.correctionReason ?? "",
    ).replace(/\s+/gu, " ").trim();
    const analysis = options.analysis;
    let analysisBytes = Number.POSITIVE_INFINITY;
    try {
      analysisBytes = new TextEncoder().encode(stableStringify(analysis)).length;
    } catch {
      analysisBytes = Number.POSITIVE_INFINITY;
    }
    if (
      !isUuid(sourceLedgerId)
      || !isUuid(expectedHeadEventId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedHeadHash)
      || !researchSourceAnalysisIsValid(analysis)
      || analysisBytes > 32_768
      || correctionReason.length < 3
      || correctionReason.length > 1_000
    ) {
      throw new CreatorApiError(
        "Проверьте структурированный разбор, точную версию источника и причину исправления.",
        { code: "research_source_correction_invalid" },
      );
    }
    const response = await this.mutate(RPC.correctResearchSourceAnalysis, {
      source_ledger_id: sourceLedgerId,
      expected_head_event_id: expectedHeadEventId,
      expected_head_hash: expectedHeadHash,
      analysis,
      correction_reason: correctionReason,
    });
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "event_id",
        "event_hash",
        "analysis_version",
        "origin",
        "external_call_started",
      ])
      || source.ok !== true
      || !isUuid(String(source.event_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(source.event_hash || ""))
      || !Number.isInteger(source.analysis_version)
      || source.analysis_version < 2
      || source.origin !== "human_correction"
      || source.external_call_started !== false
    ) {
      throw new CreatorApiError(
        "Исправление сохранено с неожиданным ответом. Не повторяйте его автоматически.",
        { code: "research_source_correction_response_invalid" },
      );
    }
    return source;
  }

  async correctResearchYoutubeObservationAnalysis(options = {}) {
    const observationId = String(
      options.observation_id ?? options.observationId ?? "",
    ).trim().toLowerCase();
    const observationHash = String(
      options.observation_hash ?? options.observationHash ?? "",
    ).trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedHeadHash = String(
      options.expected_head_hash ?? options.expectedHeadHash ?? "",
    ).trim().toLowerCase();
    const expectedRetentionExpiresAt = String(
      options.expected_retention_expires_at
        ?? options.expectedRetentionExpiresAt
        ?? "",
    ).trim();
    const expectedRetentionExpiresAtMs = Date.parse(
      expectedRetentionExpiresAt,
    );
    const correctionReason = String(
      options.correction_reason ?? options.correctionReason ?? "",
    ).replace(/\s+/gu, " ").trim();
    const analysis = options.analysis;
    let analysisBytes = Number.POSITIVE_INFINITY;
    try {
      analysisBytes = new TextEncoder().encode(stableStringify(analysis)).length;
    } catch {
      analysisBytes = Number.POSITIVE_INFINITY;
    }
    if (
      !isUuid(observationId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(observationHash)
      || !isUuid(expectedHeadEventId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedHeadHash)
      || !Number.isFinite(expectedRetentionExpiresAtMs)
      || !researchYoutubeObservationAnalysisIsValid(analysis)
      || analysisBytes > 16_384
      || correctionReason.length < 3
      || correctionReason.length > 1_000
    ) {
      throw new CreatorApiError(
        "Проверьте гипотезу, точную версию YouTube-наблюдения и причину исправления.",
        { code: "research_youtube_observation_analysis_correction_invalid" },
      );
    }
    const response = await this.mutate(
      RPC.correctResearchYoutubeObservationAnalysis,
      {
        observation_id: observationId,
        observation_hash: observationHash,
        expected_head_event_id: expectedHeadEventId,
        expected_head_hash: expectedHeadHash,
        analysis,
        correction_reason: correctionReason,
      },
    );
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "event_id",
        "event_hash",
        "analysis_version",
        "origin",
        "retention_expires_at",
        "external_call_started",
        "provider_attempt_count",
        "automatic_retry_started",
      ])
      || source.ok !== true
      || !isUuid(String(source.event_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(source.event_hash || ""))
      || !Number.isInteger(source.analysis_version)
      || source.analysis_version < 2
      || source.origin !== "human_correction"
      || typeof source.retention_expires_at !== "string"
      || !Number.isFinite(Date.parse(source.retention_expires_at))
      || Date.parse(source.retention_expires_at)
        !== expectedRetentionExpiresAtMs
      || source.external_call_started !== false
      || source.provider_attempt_count !== 0
      || source.automatic_retry_started !== false
    ) {
      throw new CreatorApiError(
        "Исправление гипотезы сохранено с неожиданным ответом. Не повторяйте его автоматически.",
        { code: "research_youtube_observation_analysis_response_invalid" },
      );
    }
    return source;
  }

  async configureResearchSourceCollectionPolicy(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const platform = String(options.platform || "").trim().toLowerCase();
    const providerKey = String(
      options.provider_key ?? options.providerKey ?? "",
    ).trim().toLowerCase();
    const status = String(options.status || "").trim().toLowerCase();
    const cadenceHours = Number(
      options.cadence_hours ?? options.cadenceHours,
    );
    const maxRecords = Number(options.max_records ?? options.maxRecords);
    const monthlyHardBudgetUnits = Number(
      options.monthly_hard_budget_units ?? options.monthlyHardBudgetUnits,
    );
    const termsVersion = String(
      options.terms_version ?? options.termsVersion ?? "",
    ).trim();
    const termsAck = options.terms_ack;
    const quotaAck = options.quota_ack;
    const noRetryAck = options.no_retry_ack;
    const legalReviewReference = String(
      options.legal_review_reference ?? options.legalReviewReference ?? "",
    ).replace(/\s+/gu, " ").trim();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    const expectedPolicyId = options.expected_policy_id
      ?? options.expectedPolicyId
      ?? null;
    const expectedPolicyHash = options.expected_policy_hash
      ?? options.expectedPolicyHash
      ?? null;
    const normalizedPolicyId = expectedPolicyId === null
      ? null
      : String(expectedPolicyId).trim().toLowerCase();
    const normalizedPolicyHash = expectedPolicyHash === null
      ? null
      : String(expectedPolicyHash).trim().toLowerCase();
    const expectedPairValid = normalizedPolicyId === null
      ? normalizedPolicyHash === null
      : isUuid(normalizedPolicyId)
        && RESEARCH_STAGE_HASH_PATTERN.test(normalizedPolicyHash || "");
    if (
      !["youtube", "instagram"].includes(platform)
      || !RESEARCH_COLLECTION_PROVIDER_PATTERN.test(providerKey)
      || !["paused", "enabled"].includes(status)
      || typeof options.automatic_collection_ack !== "boolean"
      || termsVersion.length < 3
      || termsVersion.length > 80
      || typeof termsAck !== "boolean"
      || typeof quotaAck !== "boolean"
      || typeof noRetryAck !== "boolean"
      || !Number.isInteger(cadenceHours)
      || cadenceHours < 24
      || cadenceHours > 720
      || !Number.isInteger(maxRecords)
      || maxRecords < 1
      || maxRecords > 25
      || !Number.isInteger(monthlyHardBudgetUnits)
      || monthlyHardBudgetUnits < 0
      || monthlyHardBudgetUnits > 100
      || (legalReviewReference && (
        legalReviewReference.length < 3
        || legalReviewReference.length > 160
      ))
      || reason.length < 3
      || reason.length > 500
      || !expectedPairValid
      || (status === "enabled" && (
        platform !== "youtube"
        || providerKey !== "youtube_data_api_v3"
        || options.automatic_collection_ack !== true
        || termsVersion !== RESEARCH_YOUTUBE_TERMS_VERSION
        || termsAck !== true
        || quotaAck !== true
        || noRetryAck !== true
        || monthlyHardBudgetUnits < 2
        || !legalReviewReference
      ))
    ) {
      throw new CreatorApiError(
        "Политика автосбора заполнена не полностью или не поддерживается выбранным provider-контуром.",
        { code: "research_collection_policy_invalid" },
      );
    }
    const response = await this.mutate(
      RPC.configureResearchSourceCollectionPolicy,
      {
        run_id: normalizedRunId,
        platform,
        provider_key: providerKey,
        status,
        automatic_collection_ack: options.automatic_collection_ack,
        terms_version: termsVersion,
        terms_ack: termsAck,
        quota_ack: quotaAck,
        no_retry_ack: noRetryAck,
        cadence_hours: cadenceHours,
        max_records: maxRecords,
        monthly_hard_budget_units: monthlyHardBudgetUnits,
        legal_review_reference: legalReviewReference || null,
        reason,
        expected_policy_id: normalizedPolicyId,
        expected_policy_hash: normalizedPolicyHash,
      },
    );
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    const policy = source?.policy;
    const capability = source?.capability;
    if (
      !hasExactObjectKeys(source, ["ok", "policy", "capability"])
      || source.ok !== true
      || !hasExactObjectKeys(policy, [
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
      ])
      || !isUuid(String(policy.policy_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(policy.policy_hash || ""))
      || !Number.isInteger(policy.policy_version)
      || policy.policy_version < 1
      || policy.platform !== platform
      || policy.provider_key !== providerKey
      || policy.status !== status
      || policy.automatic_collection_ack !== options.automatic_collection_ack
      || policy.terms_version !== termsVersion
      || policy.terms_ack !== termsAck
      || policy.quota_ack !== quotaAck
      || policy.no_retry_ack !== noRetryAck
      || policy.cadence_hours !== cadenceHours
      || policy.max_records !== maxRecords
      || policy.monthly_hard_budget_units !== monthlyHardBudgetUnits
      || !hasExactObjectKeys(capability, [
        "automatic_enqueue_supported",
        "external_call_started",
        "queued_ingestion_is_claimed_by_internal_worker",
        "instagram_enabled",
      ])
      || capability.automatic_enqueue_supported !== (status === "enabled")
      || capability.external_call_started !== false
      || capability.queued_ingestion_is_claimed_by_internal_worker !== true
      || capability.instagram_enabled !== false
    ) {
      throw new CreatorApiError(
        "Политика сохранена с неожиданным ответом. Не повторяйте изменение автоматически.",
        { code: "research_collection_policy_response_invalid" },
      );
    }
    return source;
  }

  async configureResearchWatchlist(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const action = String(options.action || "").trim().toLowerCase();
    if (!["enable", "update", "pause", "resume"].includes(action)) {
      throw new CreatorApiError("Выберите действие для наблюдения за исследованием.", {
        code: "research_watchlist_action_invalid",
      });
    }
    const payload = { run_id: normalizedRunId, action };
    if (["enable", "update", "resume"].includes(action)) {
      const intervalDays = Number(options.refresh_interval_days);
      if (!Number.isInteger(intervalDays) || intervalDays < 3 || intervalDays > 90) {
        throw new CreatorApiError("Интервал наблюдения должен быть от 3 до 90 дней.", {
          code: "research_watchlist_interval_invalid",
        });
      }
      payload.refresh_interval_days = intervalDays;
    }
    await this.mutate(RPC.configureResearchWatchlist, payload);
    return this.productResearchStatus(normalizedRunId);
  }

  async resolveResearchMarketCategory(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const action = String(options.action || "").trim().toLowerCase();
    const createActions = new Set(["create_and_bind", "create_and_reclassify"]);
    const existingActions = new Set(["bind_existing", "reclassify"]);
    if (!createActions.has(action) && !existingActions.has(action)) {
      throw new CreatorApiError("Выберите, как подтвердить рыночную категорию.", {
        code: "research_market_decision_action_invalid",
      });
    }
    if (options.confirmation !== true) {
      throw new CreatorApiError("Подтвердите решение по рыночной категории.", {
        code: "research_market_decision_confirmation_required",
      });
    }
    const candidateHash = String(options.candidate_hash || "").trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/u.test(candidateHash)) {
      throw new CreatorApiError("Предложение категории устарело. Обновите исследование.", {
        code: "research_market_category_candidate_stale",
      });
    }
    const payload = {
      run_id: normalizedRunId,
      action,
      candidate_hash: candidateHash,
      confirmation: true,
    };
    if (existingActions.has(action)) {
      const categoryId = String(options.category_id || "").trim();
      if (!isUuid(categoryId)) {
        throw new CreatorApiError("Выберите сохранённую рыночную категорию.", {
          code: "research_market_category_not_found",
        });
      }
      payload.category_id = categoryId;
    } else {
      const canonicalName = String(options.canonical_name || "").replace(/\s+/gu, " ").trim();
      const definition = String(options.definition || "").trim();
      const aliases = [];
      const aliasKeys = new Set();
      (Array.isArray(options.aliases) ? options.aliases : []).forEach((item) => {
        const alias = String(item || "").replace(/\s+/gu, " ").trim();
        const aliasKey = alias.toLocaleLowerCase("ru-RU");
        if (alias && !aliasKeys.has(aliasKey)) {
          aliasKeys.add(aliasKey);
          aliases.push(alias);
        }
      });
      if (canonicalName.length < 2 || canonicalName.length > 160) {
        throw new CreatorApiError("Укажите название рыночной категории длиной 2–160 символов.", {
          code: "canonical_name_invalid",
        });
      }
      if (definition.length < 10 || definition.length > 2000) {
        throw new CreatorApiError("Опишите границы категории длиной 10–2000 символов.", {
          code: "research_market_category_definition_invalid",
        });
      }
      if (aliases.length > 10 || aliases.some((value) => value.length < 2 || value.length > 160)) {
        throw new CreatorApiError("Добавьте не более 10 корректных названий-синонимов.", {
          code: "research_market_aliases_invalid",
        });
      }
      payload.canonical_name = canonicalName;
      payload.definition = definition;
      payload.aliases = aliases;
    }
    const reason = String(options.reason || "").trim();
    if (reason) {
      if (reason.length < 3 || reason.length > 500) {
        throw new CreatorApiError("Кратко объясните решение по категории (3–500 символов).", {
          code: "research_market_decision_reason_invalid",
        });
      }
      payload.reason = reason;
    }
    return this.mutate(RPC.resolveResearchMarketCategory, payload);
  }

  searchResearchMarketCategories(runId, query) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const normalizedQuery = String(query || "").replace(/\s+/gu, " ").trim();
    if (normalizedQuery.length < 2 || normalizedQuery.length > 160) {
      throw new CreatorApiError("Введите точное название или синоним категории.", {
        code: "research_market_registry_query_invalid",
      });
    }
    return this.call(
      RPC.researchMarketCategoryRegistry,
      this.withOrganization({
        run_id: normalizedRunId,
        query: normalizedQuery,
        limit: 20,
      }),
    );
  }

  researchOutcomeLearningScopes(runId) {
    const normalizedRunId = this.requireResearchRunId(runId);
    return this.call(
      RPC.researchOutcomeLearningScopes,
      this.withOrganization({ run_id: normalizedRunId, limit: 50 }),
    );
  }

  researchOutcomeLearningStatus(scope) {
    return this.call(
      RPC.researchOutcomeLearningStatus,
      this.withOrganization(requireResearchOutcomeScope(scope)),
    );
  }

  refreshResearchOutcomeLearning(scope) {
    return this.mutate(
      RPC.refreshResearchOutcomeLearning,
      requireResearchOutcomeScope(scope),
    );
  }

  decideResearchOutcomeLearning(scope, options = {}) {
    requireResearchOutcomeScope(scope);
    const action = String(options.action || "").trim().toLowerCase();
    if (!["activate", "reject", "quarantine", "deactivate", "revert"].includes(action)) {
      throw new CreatorApiError("Выберите допустимое решение по обучающей памяти.", {
        code: "research_outcome_decision_action_invalid",
      });
    }
    if (options.confirmation !== true) {
      throw new CreatorApiError("Подтвердите решение по обучающей памяти.", {
        code: "research_outcome_decision_confirmation_required",
      });
    }
    const candidateId = String(options.candidate_id || "").trim().toLowerCase();
    const candidateHash = String(options.candidate_hash || "").trim().toLowerCase();
    const candidateVersion = Number(options.candidate_version);
    const expectedScopeVersion = Number(options.expected_scope_version);
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (!isUuid(candidateId)) {
      throw new CreatorApiError("Кандидат обучения устарел. Обновите статус.", {
        code: "research_outcome_candidate_not_found",
      });
    }
    if (!/^[0-9a-f]{64}$/u.test(candidateHash)) {
      throw new CreatorApiError("Кандидат обучения изменился. Обновите статус.", {
        code: "research_outcome_candidate_stale",
      });
    }
    if (
      !Number.isInteger(candidateVersion)
      || candidateVersion < 1
      || candidateVersion > 100000
      || !Number.isInteger(expectedScopeVersion)
      || expectedScopeVersion < 0
      || expectedScopeVersion > 100000
    ) {
      throw new CreatorApiError("Версия обучающей памяти изменилась. Обновите статус.", {
        code: "research_outcome_decision_version_invalid",
      });
    }
    if (reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Кратко объясните решение (3–500 символов).", {
        code: "research_outcome_decision_reason_invalid",
      });
    }
    const payload = {
      candidate_id: candidateId,
      action,
      candidate_version: candidateVersion,
      candidate_hash: candidateHash,
      expected_scope_version: expectedScopeVersion,
      reason,
      confirmation: true,
    };
    if (action === "revert") {
      const rollbackId = String(options.rollback_memory_version_id || "")
        .trim().toLowerCase();
      if (!isUuid(rollbackId)) {
        throw new CreatorApiError("Точная версия для отката больше недоступна.", {
          code: "research_outcome_rollback_target_invalid",
        });
      }
      payload.rollback_memory_version_id = rollbackId;
    } else if (options.rollback_memory_version_id) {
      throw new CreatorApiError("Версия отката допустима только для действия «откатить».", {
        code: "research_outcome_rollback_target_unexpected",
      });
    }
    return this.mutate(RPC.decideResearchOutcomeLearning, payload);
  }

  researchYoutubeStatus(ingestionId) {
    const normalizedId = String(ingestionId || "").trim().toLowerCase();
    if (!isUuid(normalizedId)) {
      throw new CreatorApiError("Не удалось определить запуск YouTube‑проверки.", {
        code: "research_youtube_ingestion_not_found",
      });
    }
    return this.call(RPC.researchYoutubeStatus, { ingestion_id: normalizedId });
  }

  async requestResearchYoutube(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const mode = String(options.mode || "").trim().toLowerCase();
    if (!["manual_canary", "category_refresh"].includes(mode)) {
      throw new CreatorApiError("Выберите ручной canary или явное обновление категории.", {
        code: "research_youtube_request_payload_invalid",
      });
    }
    const queryText = String(options.query_text || "")
      .replace(/\s+/gu, " ")
      .trim();
    const regionCode = String(options.region_code || "").trim().toUpperCase();
    const relevanceLanguage = String(options.relevance_language || "").trim();
    const publishedAfterRaw = String(options.published_after || "").trim();
    const maxResults = Number(options.max_results);
    const expectedResults = mode === "manual_canary" ? 1 : maxResults;
    if (
      queryText.length < 2
      || queryText.length > 200
      || /[\u0000-\u001f\u007f]/u.test(queryText)
    ) {
      throw new CreatorApiError("Укажите точный YouTube‑запрос длиной 2–200 символов.", {
        code: "research_youtube_query_invalid",
      });
    }
    if (regionCode && !/^[A-Z]{2}$/u.test(regionCode)) {
      throw new CreatorApiError("Код региона должен состоять из двух латинских букв.", {
        code: "research_youtube_locale_invalid",
      });
    }
    if (
      relevanceLanguage
      && !/^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/u.test(relevanceLanguage)
    ) {
      throw new CreatorApiError("Проверьте языковой код YouTube, например ru или zh-Hans.", {
        code: "research_youtube_locale_invalid",
      });
    }
    let publishedAfter = null;
    if (publishedAfterRaw) {
      const timestamp = Date.parse(publishedAfterRaw);
      if (
        !Number.isFinite(timestamp)
        || timestamp < Date.now() - 366 * 86_400_000
        || timestamp > Date.now() + 60_000
      ) {
        throw new CreatorApiError("Дата начала поиска должна быть в пределах последних 366 дней.", {
          code: "research_youtube_published_after_invalid",
        });
      }
      publishedAfter = new Date(timestamp).toISOString();
    }
    if (
      !Number.isInteger(expectedResults)
      || expectedResults < 1
      || expectedResults > 25
      || (mode === "manual_canary" && maxResults !== 1)
    ) {
      throw new CreatorApiError("Canary проверяет 1 видео, обновление — от 1 до 25.", {
        code: "research_youtube_quota_plan_invalid",
      });
    }
    if (
      options.quota_ack !== true
      || options.no_retry_ack !== true
      || options.terms_ack !== true
      || String(options.terms_version || "") !== RESEARCH_YOUTUBE_TERMS_VERSION
    ) {
      throw new CreatorApiError("Подтвердите квоту, отсутствие повтора и актуальные условия YouTube API.", {
        code: "research_youtube_confirmation_required",
      });
    }
    const payload = {
      run_id: normalizedRunId,
      query_text: queryText,
      region_code: regionCode || null,
      relevance_language: relevanceLanguage || null,
      published_after: publishedAfter,
      max_results: expectedResults,
      max_http_requests: 2,
      max_quota_units: 2,
      quota_ack: true,
      no_retry_ack: true,
      terms_ack: true,
      terms_version: RESEARCH_YOUTUBE_TERMS_VERSION,
    };
    const rpcName = mode === "manual_canary"
      ? RPC.requestResearchYoutubeCanary
      : RPC.requestResearchYoutubeRefresh;
    const requested = await this.mutate(rpcName, payload);
    const source = requested?.data && typeof requested.data === "object"
      && !Array.isArray(requested.data)
      ? requested.data
      : requested;
    const ingestion = source?.ingestion;
    const ingestionId = String(ingestion?.id || "").trim().toLowerCase();
    if (
      source?.ok !== true
      || source?.version !== "research-youtube-live-ingestion-v1"
      || !isUuid(ingestionId)
      || ingestion?.status !== "queued"
      || ingestion?.mode !== mode
      || Number(ingestion?.max_http_requests) !== 2
      || Number(ingestion?.max_quota_units) !== 2
    ) {
      throw new CreatorApiError("Сервер не подтвердил ограниченный план YouTube‑запроса.", {
        code: "research_youtube_request_response_invalid",
      });
    }
    let execution;
    try {
      execution = await this.invokeResearchIngestion(ingestionId);
    } catch (error) {
      error.job = { id: ingestionId, status: "queued", kind: "youtube_ingestion" };
      throw error;
    }
    return { request: source, execution };
  }

  decideResearchYoutubeRollout(options = {}) {
    const decision = String(options.decision || "").trim().toLowerCase();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (!["enable_category_refresh", "pause_category_refresh"].includes(decision)) {
      throw new CreatorApiError("Выберите включение или паузу обновлений YouTube.", {
        code: "research_youtube_rollout_decision_invalid",
      });
    }
    if (reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Кратко объясните решение по rollout (3–500 символов).", {
        code: "research_youtube_rollout_payload_invalid",
      });
    }
    if (
      options.terms_ack !== true
      || String(options.terms_version || "") !== RESEARCH_YOUTUBE_TERMS_VERSION
    ) {
      throw new CreatorApiError("Подтвердите актуальную версию условий YouTube API.", {
        code: "research_youtube_confirmation_required",
      });
    }
    const payload = {
      decision,
      reason,
      terms_ack: true,
      terms_version: RESEARCH_YOUTUBE_TERMS_VERSION,
    };
    if (decision === "enable_category_refresh") {
      const canaryId = String(options.canary_ingestion_id || "").trim().toLowerCase();
      if (!isUuid(canaryId)) {
        throw new CreatorApiError("Сначала завершите свежий двухэтапный canary.", {
          code: "research_youtube_fresh_canary_required",
        });
      }
      payload.canary_ingestion_id = canaryId;
    }
    return this.mutate(RPC.decideResearchYoutubeRollout, payload);
  }

  decideResearchYoutubeCandidate(options = {}) {
    const ingestionId = String(options.ingestion_id || "").trim().toLowerCase();
    const observationId = String(options.observation_id || "").trim().toLowerCase();
    const observationHash = String(options.observation_hash || "").trim().toLowerCase();
    const decision = String(options.decision || "").trim().toLowerCase();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (
      !isUuid(ingestionId)
      || !isUuid(observationId)
      || !/^[0-9a-f]{64}$/u.test(observationHash)
      || !["confirm_candidate", "exclude_candidate"].includes(decision)
    ) {
      throw new CreatorApiError("Кандидат YouTube изменился. Обновите статус.", {
        code: "research_youtube_candidate_stale",
      });
    }
    if (options.confirmation !== true || reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Подтвердите временное решение и укажите причину (3–500 символов).", {
        code: "research_youtube_candidate_payload_invalid",
      });
    }
    return this.mutate(RPC.decideResearchYoutubeCandidate, {
      ingestion_id: ingestionId,
      observation_id: observationId,
      observation_hash: observationHash,
      decision,
      reason,
      confirmation: true,
    });
  }

  async invokeResearchIngestion(ingestionId) {
    const normalizedId = String(ingestionId || "").trim().toLowerCase();
    if (!isUuid(normalizedId)) {
      throw new CreatorApiError("Не удалось определить YouTube‑запуск.", {
        code: "research_youtube_ingestion_not_found",
      });
    }
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла перед ручным YouTube‑запросом.", {
        code: "auth_session_required",
      });
    }
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(
        RESEARCH_INGESTION_FUNCTION,
        {
          body: { action: "ingest", ingestion_id: normalizedId },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      ));
    } catch {
      throw new CreatorApiError("Запуск сохранён, но транспорт YouTube не подтвердил начало.", {
        code: "research_youtube_ingestion_unavailable",
      });
    }
    if (error) throw await researchIngestionFunctionError(error);
    const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
      ? data.data
      : data;
    if (
      !source
      || typeof source !== "object"
      || Array.isArray(source)
      || source.ok !== true
      || source.version !== "research-youtube-live-ingestion-v1"
      || String(source.ingestion?.id || "").toLowerCase() !== normalizedId
      || !["queued", "processing", "completed", "failed"].includes(
        String(source.ingestion?.status || ""),
      )
    ) {
      throw new CreatorApiError("YouTube‑транспорт вернул неполный статус. Не повторяйте запрос автоматически.", {
        code: "research_youtube_ingestion_response_invalid",
      });
    }
    return source;
  }

  saveCreativeBriefDraft(runId, draft) {
    return this.mutate(RPC.saveCreativeBriefDraft, {
      run_id: this.requireResearchRunId(runId),
      title: draft?.title,
      brief: draft?.brief,
      source_ids: draft?.source_ids,
      task_blueprint: draft?.task_blueprint,
    });
  }

  approveCreativeBrief(draftId) {
    const normalizedDraftId = String(draftId || "").trim();
    if (!normalizedDraftId || normalizedDraftId.length > 128) {
      throw new CreatorApiError("Сначала сохраните актуальный черновик ТЗ.", {
        code: "creative_brief_draft_invalid",
      });
    }
    return this.mutate(RPC.approveCreativeBrief, {
      draft_id: normalizedDraftId,
    });
  }

  requireResearchRunId(value) {
    const runId = String(value || "").trim();
    if (!runId || runId.length > 128) {
      throw new CreatorApiError("Не удалось определить исследование. Начните новый разбор.", {
        code: "product_research_run_invalid",
      });
    }
    return runId;
  }

  async invokeProductResearch(payload) {
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед запуском анализа.", {
        code: "auth_session_required",
      });
    }

    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(PRODUCT_RESEARCH_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось запустить анализ товара. Повторите попытку позже.", {
        code: "product_research_request_failed",
      });
    }
    if (error) {
      throw new CreatorApiError("Сервис анализа товара временно недоступен. Запуск сохранён — проверьте его статус позже.", {
        code: error?.code || "product_research_request_failed",
      });
    }
    if (!data || typeof data !== "object" || Array.isArray(data) || data.ok === false || data.error) {
      throw new CreatorApiError("Сервис анализа товара вернул некорректный ответ.", {
        code: "product_research_response_invalid",
      });
    }
    return data;
  }

  contentReviewCatalog({ limit = 50 } = {}) {
    const normalizedLimit = Number(limit);
    if (!Number.isInteger(normalizedLimit) || normalizedLimit < 1 || normalizedLimit > 50) {
      throw new CreatorApiError("История проверки может содержать от 1 до 50 записей.", {
        code: "content_review_limit_invalid",
      });
    }
    return this.call(RPC.contentReviewCatalog, this.withOrganization({
      media_limit: normalizedLimit,
      run_limit: normalizedLimit,
    }));
  }

  async prepareContentReviewEvidence({ mediaId, frameCount }) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedFrameCount = Number(frameCount);
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Не удалось определить видео для сохранения кадров.", {
        code: "content_review_media_required",
      });
    }
    if (!Number.isInteger(normalizedFrameCount) || normalizedFrameCount !== 5) {
      throw new CreatorApiError("Для MP4 нужно подготовить четыре кадра и пятый JPEG-атлас.", {
        code: "content_review_frames_invalid",
      });
    }
    const response = await this.mutate(RPC.prepareContentReviewEvidence, {
      media_id: normalizedMediaId,
      frame_count: normalizedFrameCount,
    });
    const source = response?.data && typeof response.data === "object" && !Array.isArray(response.data)
      ? response.data
      : response;
    const evidenceId = String(source?.evidence_id || source?.evidence?.id || "").trim();
    const objectNames = Array.isArray(source?.frame_object_names)
      ? source.frame_object_names.map((value) => String(value || "").trim())
      : [];
    const expiresAt = String(source?.expires_at || source?.evidence?.expires_at || "").trim();
    if (
      !isUuid(evidenceId)
      || objectNames.length !== normalizedFrameCount
      || new Set(objectNames).size !== objectNames.length
      || !Number.isFinite(Date.parse(expiresAt))
      || Date.parse(expiresAt) <= Date.now()
    ) {
      throw new CreatorApiError("Сервер не подготовил защищённые места для всех кадров.", {
        code: "content_review_evidence_prepare_invalid",
      });
    }
    objectNames.forEach((objectName) => this.assertPrivateObjectKey(objectName));
    return {
      evidenceId,
      frameObjectNames: objectNames,
      expiresAt,
    };
  }

  async commitContentReviewEvidence({ evidenceId, frames, technicalMetrics, idempotencyKey = "" }) {
    const normalizedEvidenceId = String(evidenceId || "").trim();
    const normalizedIdempotencyKey = String(idempotencyKey || "").trim().toLowerCase();
    if (
      !isUuid(normalizedEvidenceId)
      || !Array.isArray(frames)
      || frames.length !== 5
      || !technicalMetrics
      || typeof technicalMetrics !== "object"
      || Array.isArray(technicalMetrics)
      || String(technicalMetrics.source_type || "").toLowerCase() !== "video"
      || !validContentReviewTechnicalMetrics(technicalMetrics)
      || (normalizedIdempotencyKey && !isUuid(normalizedIdempotencyKey))
    ) {
      throw new CreatorApiError("Не удалось подтвердить полный набор контрольных кадров.", {
        code: "content_review_evidence_commit_invalid",
      });
    }
    const normalizedFrames = frames.map((frame) => {
      const objectName = String(frame?.object_name || "").trim();
      const sha256 = String(frame?.sha256 || "").trim().toLowerCase();
      const sizeBytes = Number(frame?.size_bytes);
      const timecodeSeconds = Number(frame?.timecode_seconds);
      this.assertPrivateObjectKey(objectName);
      if (
        !/^[0-9a-f]{64}$/u.test(sha256)
        || !Number.isInteger(sizeBytes)
        || sizeBytes < 128
        || sizeBytes > 250_000
        || !Number.isFinite(timecodeSeconds)
        || timecodeSeconds < 0
        || timecodeSeconds > 3_600
      ) {
        throw new CreatorApiError("Один из контрольных кадров имеет неверные параметры.", {
          code: "content_review_evidence_frame_invalid",
        });
      }
      return {
        object_name: objectName,
        sha256,
        size_bytes: sizeBytes,
        timecode_seconds: Math.round(timecodeSeconds * 1_000) / 1_000,
      };
    });
    if (new Set(normalizedFrames.map((frame) => frame.object_name)).size !== normalizedFrames.length) {
      throw new CreatorApiError("Контрольные кадры должны иметь разные защищённые имена.", {
        code: "content_review_evidence_frame_invalid",
      });
    }
    const commitPayload = {
      evidence_id: normalizedEvidenceId,
      frames: normalizedFrames,
      technical_metrics: technicalMetrics,
    };
    const response = normalizedIdempotencyKey
      ? await this.call(RPC.commitContentReviewEvidence, {
          ...this.withOrganization(commitPayload),
          idempotency_key: normalizedIdempotencyKey,
        })
      : await this.mutate(RPC.commitContentReviewEvidence, commitPayload);
    const source = response?.data && typeof response.data === "object" && !Array.isArray(response.data)
      ? response.data
      : response;
    const returnedEvidenceId = String(source?.evidence_id || source?.evidence?.id || normalizedEvidenceId).trim();
    const status = String(source?.status || source?.evidence?.status || "").trim().toLowerCase();
    if (returnedEvidenceId !== normalizedEvidenceId || status !== "ready") {
      throw new CreatorApiError("Сервер не подтвердил сохранение контрольных кадров.", {
        code: "content_review_evidence_commit_invalid",
      });
    }
    return { ...source, evidence_id: normalizedEvidenceId, status: "ready" };
  }

  async startContentReview(input, { onRunCreated } = {}) {
    const mediaId = String(input?.media_id || "").trim();
    const platform = String(input?.platform || "").trim().toLowerCase();
    const contentKind = String(input?.content_kind || "").trim().toLowerCase();
    const productCategory = String(input?.product_category || "").trim().toLowerCase();
    const peoplePresent = String(input?.people_present || "unknown").trim().toLowerCase();
    const supportedPlatforms = new Set(["instagram", "youtube", "vk", "tiktok", "telegram", "wildberries", "other"]);
    const supportedContentKinds = new Set(["unknown", "informational", "advertising"]);
    const supportedCategories = new Set(["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]);
    if (!mediaId || mediaId.length > 180) {
      throw new CreatorApiError("Выберите точное изображение или MP4 из раздела «Материалы».", {
        code: "content_review_media_required",
      });
    }
    if (!supportedPlatforms.has(platform) || !supportedContentKinds.has(contentKind)) {
      throw new CreatorApiError("Проверьте площадку и рекламный статус материала.", {
        code: "content_review_context_invalid",
      });
    }
    if (!supportedCategories.has(productCategory) || !["unknown", "yes", "no"].includes(peoplePresent)) {
      throw new CreatorApiError("Проверьте категорию товара и наличие людей в кадре.", {
        code: "content_review_context_invalid",
      });
    }
    if (peoplePresent !== "no" && input?.external_ai_processing_confirmed !== true) {
      throw new CreatorApiError("Подтвердите законное основание и информирование для передачи контрольных кадров с узнаваемыми людьми внешнему AI-провайдеру.", {
        code: "content_review_external_ai_processing_required",
      });
    }
    const captionText = String(input?.caption_text || "").trim();
    const scriptText = String(input?.script_text || "").trim();
    if (captionText.length > 6_000 || scriptText.length > 6_000) {
      throw new CreatorApiError("Сократите подпись и сценарий до 6000 символов каждый.", {
        code: "content_review_text_too_large",
      });
    }
    const technicalMetrics = input?.technical_metrics;
    if (!technicalMetrics || typeof technicalMetrics !== "object" || Array.isArray(technicalMetrics)) {
      throw new CreatorApiError("Браузер не смог подготовить технические параметры файла.", {
        code: "content_review_metrics_required",
      });
    }
    const sourceType = String(technicalMetrics.source_type || "").toLowerCase();
    if (!validContentReviewTechnicalMetrics(technicalMetrics)) {
      throw new CreatorApiError("Технические параметры файла неполны или повреждены.", {
        code: "content_review_metrics_invalid",
      });
    }
    const evidenceId = String(input?.evidence_id || "").trim();
    if (sourceType === "video" && !isUuid(evidenceId)) {
      throw new CreatorApiError("Сначала сохраните контрольные кадры MP4.", {
        code: "content_review_evidence_required",
      });
    }
    if (evidenceId && !isUuid(evidenceId)) {
      throw new CreatorApiError("Сохранённый набор кадров имеет неверный номер.", {
        code: "content_review_evidence_invalid",
      });
    }

    const payload = {
      media_id: mediaId,
      ...(input?.parent_review_id ? { parent_review_id: String(input.parent_review_id) } : {}),
      platform,
      content_kind: contentKind,
      product_category: productCategory,
      caption_text: captionText,
      script_text: scriptText,
      advertiser_name: String(input?.advertiser_name || "").trim(),
      erid: String(input?.erid || "").trim(),
      technical_metrics: technicalMetrics,
      ...(evidenceId ? { evidence_id: evidenceId } : {}),
      rights_confirmed: input?.rights_confirmed === true,
      claims_verified: input?.claims_verified === true,
      ad_label_confirmed: input?.ad_label_confirmed === true,
      ord_confirmed: input?.ord_confirmed === true,
      audience_over_10000: input?.audience_over_10000 === true,
      rkn_registered: input?.rkn_registered === true,
      people_present: peoplePresent,
      person_consent_confirmed: input?.person_consent_confirmed === true,
      external_ai_processing_confirmed: input?.external_ai_processing_confirmed === true,
      ai_generated: input?.ai_generated === true,
      ai_disclosure_confirmed: input?.ai_disclosure_confirmed === true,
      captions_confirmed: input?.captions_confirmed === true,
      mandatory_warning_confirmed: input?.mandatory_warning_confirmed === true,
    };
    const created = await this.mutate(RPC.startContentReview, payload);
    const source = created?.data && typeof created.data === "object" ? created.data : created;
    const run = source?.run || source?.review || {};
    const reviewId = String(run?.id || source?.review_id || source?.id || "").trim();
    if (!reviewId) {
      throw new CreatorApiError("Сервер не вернул номер проверки. Обновите раздел и повторите.", {
        code: "content_review_run_missing",
      });
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({ ...run, id: reviewId, status: String(run?.status || "queued") });
      } catch {
        // UI recovery must never cancel the durable server-side run.
      }
    }

    const accepted = {
      ok: true,
      status: "background_queued",
    };
    // This dispatch is only a latency optimization. The durable worker owns
    // completion, so the user never waits for an Edge/provider round trip and
    // closing the tab cannot invalidate the queued run.
    void this.invokeContentReview({
      action: "analyze",
      review_id: reviewId,
    }).catch(() => {});
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: accepted,
    };
  }

  async startGeneratedVideoReview({ mediaId, evidenceId } = {}, {
    onRunCreated,
  } = {}) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedEvidenceId = String(evidenceId || "").trim();
    if (!isUuid(normalizedMediaId) || !isUuid(normalizedEvidenceId)) {
      throw new CreatorApiError("Сначала дождитесь сохранения точного MP4 и его контрольных кадров.", {
        code: "generated_video_review_evidence_required",
      });
    }
    const created = await this.mutate(RPC.startGeneratedVideoReview, {
      media_id: normalizedMediaId,
      evidence_id: normalizedEvidenceId,
    });
    const source = created?.data && typeof created.data === "object"
      ? created.data
      : created;
    const run = source?.run || source?.review || {};
    const reviewId = String(
      run?.id || source?.review_id || source?.id || "",
    ).trim();
    if (!isUuid(reviewId)) {
      throw new CreatorApiError("Сервер не вернул номер проверки готового ролика.", {
        code: "content_review_run_missing",
      });
    }
    if (source?.transcription_requested !== false) {
      throw new CreatorApiError("Без отдельного разрешения транскрипция ролика должна оставаться выключенной.", {
        code: "generated_video_transcription_guard_failed",
      });
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({
          ...run,
          id: reviewId,
          status: String(run?.status || "queued"),
        });
      } catch {
        // UI recovery is best effort; the durable run remains authoritative.
      }
    }
    void this.invokeContentReview({
      action: "analyze",
      review_id: reviewId,
    }).catch(() => {});
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: {
        ok: true,
        status: "background_queued",
        transcription_requested: false,
      },
    };
  }

  contentReviewStatus(reviewId) {
    return this.call(RPC.contentReviewStatus, this.withOrganization({
      review_id: this.requireContentReviewId(reviewId),
    }));
  }

  decideContentReview(reviewId, decision, comment, {
    resolvedRecommendationCodes = [],
    riskAcknowledgements = [],
    mediaWatchedConfirmed = false,
  } = {}) {
    const normalizedDecision = String(decision || "").trim().toLowerCase();
    const normalizedComment = String(comment || "").trim();
    if (!["approved", "needs_changes", "rejected"].includes(normalizedDecision)) {
      throw new CreatorApiError("Выберите итог проверки: одобрить, доработать или отклонить.", {
        code: "content_review_decision_invalid",
      });
    }
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    if (mediaWatchedConfirmed !== true) {
      throw new CreatorApiError("Перед решением полностью просмотрите защищённый файл со звуком и субтитрами.", {
        code: "content_review_media_watch_required",
      });
    }
    return this.mutate(RPC.decideContentReview, {
      review_id: this.requireContentReviewId(reviewId),
      decision: normalizedDecision,
      comment: normalizedComment,
      resolved_recommendation_codes: safeResolvedCodes,
      risk_acknowledgements: safeRiskAcknowledgements,
      media_watched_confirmed: true,
    });
  }

  approveGeneratedPhotoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
  } = {}) {
    const normalizedComment = String(comment || "").trim();
    const productCategory = String(context?.productCategory || "").trim().toLowerCase();
    const advertiserName = String(context?.advertiserName || "").trim();
    const erid = String(context?.erid || "").trim();
    const peoplePresent = String(context?.peoplePresent || "").trim().toLowerCase();
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
      || advertiserName.length < 2
      || advertiserName.length > 240
      || erid.length < 6
      || erid.length > 180
      || !["yes", "no"].includes(peoplePresent)
    ) {
      throw new CreatorApiError("Заполните категорию, рекламодателя, ERID и наличие людей для точного PNG.", {
        code: "generated_photo_context_approval_invalid",
      });
    }
    if (
      context?.adLabelConfirmed !== true
      || context?.ordConfirmed !== true
      || context?.rightsConfirmed !== true
      || context?.claimsVerified !== true
      || (peoplePresent === "yes" && context?.personConsentConfirmed !== true)
      || mediaWatchedConfirmed !== true
    ) {
      throw new CreatorApiError("Подтвердите осмотр PNG, маркировку, ОРД, права, claims и согласия людей.", {
        code: "generated_photo_context_approval_invalid",
      });
    }
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    return this.mutate(RPC.approveGeneratedPhotoWithContext, {
      review_id: this.requireContentReviewId(reviewId),
      reason: normalizedComment,
      product_category: productCategory,
      advertiser_name: advertiserName,
      erid,
      people_present: peoplePresent,
      media_watched_confirmed: true,
      ad_label_confirmed: true,
      ord_confirmed: true,
      rights_confirmed: true,
      claims_verified: true,
      person_consent_confirmed: context?.personConsentConfirmed === true,
      ai_disclosure_confirmed: context?.aiDisclosureConfirmed === true,
      mandatory_warning_confirmed: context?.mandatoryWarningConfirmed === true,
      audience_over_10000: context?.audienceOver10000 === true,
      rkn_registered: context?.rknRegistered === true,
      risk_acknowledgements: safeRiskAcknowledgements,
      resolved_recommendation_codes: safeResolvedCodes,
    });
  }

  approveGeneratedVideoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
  } = {}) {
    const normalizedComment = String(comment || "").trim();
    const productCategory = String(context?.productCategory || "").trim().toLowerCase();
    const advertiserName = String(context?.advertiserName || "").trim();
    const erid = String(context?.erid || "").trim();
    const peoplePresent = String(context?.peoplePresent || "").trim().toLowerCase();
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
      || advertiserName.length < 2
      || advertiserName.length > 240
      || erid.length < 6
      || erid.length > 180
      || !["yes", "no"].includes(peoplePresent)
    ) {
      throw new CreatorApiError("Заполните категорию, рекламодателя, ERID и наличие людей для точного MP4.", {
        code: "generated_video_context_approval_invalid",
      });
    }
    if (
      context?.adLabelConfirmed !== true
      || context?.ordConfirmed !== true
      || context?.rightsConfirmed !== true
      || context?.claimsVerified !== true
      || (context?.captionsRequired === true && context?.captionsConfirmed !== true)
      || (peoplePresent === "yes" && context?.personConsentConfirmed !== true)
      || mediaWatchedConfirmed !== true
    ) {
      throw new CreatorApiError("Подтвердите полный просмотр MP4, маркировку, ОРД, права, claims, субтитры и согласия людей.", {
        code: "generated_video_context_approval_invalid",
      });
    }
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    return this.mutate(RPC.approveGeneratedVideoWithContext, {
      review_id: this.requireContentReviewId(reviewId),
      reason: normalizedComment,
      product_category: productCategory,
      advertiser_name: advertiserName,
      erid,
      people_present: peoplePresent,
      media_watched_confirmed: true,
      ad_label_confirmed: true,
      ord_confirmed: true,
      rights_confirmed: true,
      claims_verified: true,
      captions_confirmed: context?.captionsConfirmed === true,
      person_consent_confirmed: context?.personConsentConfirmed === true,
      ai_disclosure_confirmed: context?.aiDisclosureConfirmed === true,
      mandatory_warning_confirmed: context?.mandatoryWarningConfirmed === true,
      audience_over_10000: context?.audienceOver10000 === true,
      rkn_registered: context?.rknRegistered === true,
      risk_acknowledgements: safeRiskAcknowledgements,
      resolved_recommendation_codes: safeResolvedCodes,
    });
  }

  requireContentReviewId(value) {
    const reviewId = String(value || "").trim();
    if (!reviewId || reviewId.length > 180) {
      throw new CreatorApiError("Не удалось определить проверку. Обновите раздел.", {
        code: "content_review_id_invalid",
      });
    }
    return reviewId;
  }

  async invokeContentReview(payload) {
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед проверкой контента.", {
        code: "auth_session_required",
      });
    }
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(CONTENT_REVIEW_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось запустить проверку контента. Запись сохранена — проверьте статус позже.", {
        code: "content_review_request_failed",
      });
    }
    if (error) {
      throw await contentReviewFunctionError(error);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new CreatorApiError("Сервис проверки контента вернул некорректный ответ.", {
        code: "content_review_response_invalid",
      });
    }
    if (data.ok === false || data.error) {
      const responseError = data.error && typeof data.error === "object" && !Array.isArray(data.error)
        ? data.error
        : {
            code: data.code || (typeof data.error === "string" ? data.error : "content_review_response_invalid"),
            details: data.details || null,
            hint: data.hint || null,
          };
      throw new CreatorApiError(safeContentReviewMessage(responseError), responseError);
    }
    return data;
  }

  createMockBatch(batch) {
    const count = Number(batch?.count);
    if (!Number.isInteger(count) || count < 1 || count > 50) {
      throw new CreatorApiError("За один раз можно создать от 1 до 50 тестовых вариантов.", {
        code: "invalid_batch_size",
      });
    }
    const platforms = new Set(["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"]);
    const destination = String(batch?.destination_ref || "").trim();
    if (!platforms.has(batch?.platform) || destination.length < 2 || destination.length > 240) {
      throw new CreatorApiError("Проверьте площадку и точный аккаунт или карточку размещения.", {
        code: "placement_destination_invalid",
      });
    }
    if (!Array.isArray(batch?.media_ids) || batch.media_ids.length < 1) {
      throw new CreatorApiError("Добавьте точное фото товара или упаковки из раздела «Материалы».", {
        code: "exact_product_media_required",
      });
    }
    if (
      batch?.payout_minor !== undefined &&
      (!Number.isSafeInteger(batch.payout_minor) || batch.payout_minor < 0 || batch.payout_minor > 1_000_000)
    ) {
      throw new CreatorApiError("Проверьте сумму вознаграждения.", {
        code: "payout_minor_invalid",
      });
    }
    return this.mutate(RPC.createMockBatch, {
      ...batch,
      mode: "mock",
      allow_real_spend: false,
      spend_confirmation: "MOCK_ONLY",
    });
  }

  startRealGeneration(batch) {
    if (this.config.REAL_GENERATION_ENABLED !== true) {
      throw new CreatorApiError("Платная генерация выключена в конфигурации портала.", {
        code: "real_generation_is_disabled",
      });
    }
    if (
      !Array.isArray(batch?.media_ids)
      || batch.media_ids.length < 1
      || batch.media_ids.length > 5
      || new Set(batch.media_ids.map(String)).size !== batch.media_ids.length
      || batch.media_ids.some((mediaId) => !isUuid(String(mediaId || "")))
    ) {
      throw new CreatorApiError("Выберите от одного до пяти точных фото одного товара.", {
        code: "real_generation_product_references_invalid",
      });
    }
    const campaignId = String(batch?.campaign_id || "").trim();
    if (!isUuid(campaignId)) {
      throw new CreatorApiError("Выберите активную кампанию из свежей денежной сводки.", {
        code: "paid_generation_campaign_required",
      });
    }
    const model = String(batch?.model || "gen4_turbo");
    const sku = realGenerationSku(model, batch?.duration_seconds);
    if (!sku) {
      throw new CreatorApiError("Выберите доступный платный режим.", {
        code: "real_generation_sku_invalid",
      });
    }
    if (
      Number(batch?.duration_seconds) !== sku.duration_seconds ||
      Boolean(batch?.audio) !== sku.audio ||
      (sku.format && batch?.format !== sku.format)
    ) {
      throw new CreatorApiError("Параметры платного режима не совпадают с подтверждённой ценой.", {
        code: "real_generation_sku_invalid",
      });
    }
    if (batch?.spend_confirmation !== sku.confirmation) {
      const contentLabel = model === "seedream5_lite" ? "фото" : "видео";
      throw new CreatorApiError(`Подтвердите создание одного платного ${contentLabel} примерно за $${sku.estimated_usd}.`, {
        code: "real_spend_confirmation_required",
      });
    }
    const brief = String(batch?.brief || "").trim();
    if (!brief || brief.length > sku.prompt_max_length) {
      throw new CreatorApiError(
        `Сократите ТЗ для выбранной модели до ${sku.prompt_max_length} символов.`,
        { code: "brief_invalid" },
      );
    }
    const productCategory = String(batch?.product_category || "").trim().toLowerCase();
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
    ) {
      throw new CreatorApiError(
        "Выберите категорию товара для правил QA и обязательных предупреждений.",
        { code: "paid_generation_product_category_invalid" },
      );
    }
    const learningContext = batch?.learning_context;
    if (
      !learningContext
      || typeof learningContext !== "object"
      || Array.isArray(learningContext)
    ) {
      throw new CreatorApiError(
        "Восстановите безопасное авто-ТЗ и дождитесь проверки обучения.",
        { code: "generation_learning_context_required" },
      );
    }
    if (!hasExactObjectKeys(batch?.generation_spec_context, [
      "spec_id", "spec_version", "spec_hash",
    ])) {
      throw new CreatorApiError(
        "Подготовьте и утвердите актуальную серверную версию ТЗ.",
        { code: "generation_spec_context_required" },
      );
    }
    const generationSpecContext = normalizeGenerationSpecReference(
      batch.generation_spec_context,
    );
    if (
      batch?.learning_opt_out !== undefined
      && (
        batch.learning_opt_out !== true
        || learningContext.source === "performance_learning"
      )
    ) {
      throw new CreatorApiError(
        "Не удалось подтвердить осознанное отключение обученного ракурса.",
        { code: "generation_learning_opt_out_invalid" },
      );
    }
    const repairContext = batch?.repair_context;
    if (repairContext !== undefined) {
      const allowedRepairCodes = new Set([
        "product_fidelity",
        "technical_stability",
        "audio_quality",
        "speech_fidelity",
        "hook_clarity",
        "visual_quality",
        "trust",
        "platform_fit",
      ]);
      const guardCodes = repairContext?.guard_codes;
      if (
        !repairContext
        || typeof repairContext !== "object"
        || Array.isArray(repairContext)
        || repairContext.compiler_version !== "review-repair-v1"
        || !isUuid(String(repairContext.source_review_id || ""))
        || !isUuid(String(repairContext.source_generation_job_id || ""))
        || !/^[0-9a-f]{64}$/u.test(String(repairContext.policy_hash || ""))
        || !Array.isArray(guardCodes)
        || guardCodes.length < 1
        || guardCodes.length > 3
        || new Set(guardCodes).size !== guardCodes.length
        || guardCodes.some((code) => !allowedRepairCodes.has(code))
        || Object.keys(repairContext).some((key) => ![
          "source_review_id",
          "source_generation_job_id",
          "guard_codes",
          "policy_hash",
          "compiler_version",
        ].includes(key))
        || Object.keys(repairContext).length !== 5
      ) {
        throw new CreatorApiError(
          "Исправление после QA устарело. Вернитесь в проверку и подготовьте его снова.",
          { code: "generation_repair_context_invalid" },
        );
      }
    }

    return this.invokeRealGeneration("start", {
      ...batch,
      generation_spec_context: generationSpecContext,
      campaign_id: campaignId,
      count: 1,
      media_ids: batch.media_ids.map(String),
      mode: "real",
      provider: "runway",
      model,
      duration_seconds: sku.duration_seconds,
      audio: sku.audio,
      allow_real_spend: true,
      spend_confirmation: sku.confirmation,
    });
  }

  realGenerationPreflight(model, durationSeconds) {
    const normalizedModel = String(model || "").trim();
    const sku = realGenerationSku(normalizedModel, durationSeconds);
    if (!sku) {
      throw new CreatorApiError("Выберите доступный платный режим.", {
        code: "real_generation_sku_invalid",
      });
    }
    return this.invokeRealGeneration("preflight", {
      model: normalizedModel,
      duration_seconds: sku.duration_seconds,
    });
  }

  realGenerationStatus(jobId) {
    const normalizedJobId = String(jobId || "").trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(normalizedJobId)) {
      throw new CreatorApiError("Не удалось определить платную задачу. Обновите раздел.", {
        code: "generation_job_id_invalid",
      });
    }
    return this.invokeRealGeneration("status", { job_id: normalizedJobId });
  }

  reconcileRealGeneration(jobId, details = {}) {
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const normalizedJobId = String(jobId || "").trim();
    const incidentId = String(details.incident_id || "").trim();
    const resolution = String(details.resolution || "").trim();
    const evidenceReference = String(details.evidence_reference || "").trim();
    const reason = String(details.reason || "").trim();
    const providerTaskId = String(details.provider_task_id || "").trim();
    const attachExistingTask = resolution === "attach_existing_task";
    const confirmNoSubmission = resolution === "confirm_no_submission";

    if (!uuidPattern.test(normalizedJobId) || !uuidPattern.test(incidentId)) {
      throw new CreatorApiError("Не удалось определить инцидент платного запуска. Обновите раздел.", {
        code: "generation_reconciliation_incident_invalid",
      });
    }
    if (!attachExistingTask && !confirmNoSubmission) {
      throw new CreatorApiError("Выберите результат ручной сверки платного запуска.", {
        code: "generation_reconciliation_resolution_invalid",
      });
    }
    if (
      evidenceReference.length < 8
      || evidenceReference.length > 500
      || reason.length < 20
      || reason.length > 1_000
    ) {
      throw new CreatorApiError("Добавьте проверяемое основание и подробную причину ручной сверки.", {
        code: "generation_reconciliation_evidence_invalid",
      });
    }
    if (
      attachExistingTask
      && !/^[a-z0-9][a-z0-9_-]{0,127}$/i.test(providerTaskId)
    ) {
      throw new CreatorApiError("Укажите точный Runway task ID из панели видеосервиса.", {
        code: "generation_reconciliation_task_id_invalid",
      });
    }

    return this.invokeRealGeneration("reconcile", {
      job_id: normalizedJobId,
      incident_id: incidentId,
      resolution,
      evidence_reference: evidenceReference,
      reason,
      confirmation: attachExistingTask
        ? "RUNWAY_TASK_ID_VERIFIED"
        : "RUNWAY_NO_TASK_VERIFIED",
      ...(attachExistingTask ? { provider_task_id: providerTaskId } : {}),
    });
  }

  async invokeRealGeneration(action, payload = {}) {
    if (!new Set(["preflight", "start", "status", "reconcile"]).has(action)) {
      throw new CreatorApiError("Неизвестное действие платной генерации.", {
        code: "real_generation_action_invalid",
      });
    }

    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед платным запуском.", {
        code: "auth_session_required",
      });
    }

    const scopedPayload = this.withOrganization({ ...payload, action });
    const actorId = String(sessionData.session?.user?.id || "unknown");
    const fingerprint = `edge:${REAL_GENERATION_FUNCTION}:${actorId}:${stableStringify(scopedPayload)}`;
    const idempotencyKey = new Set(["start", "reconcile"]).has(action)
      ? (this.mutationKeys[fingerprint] || crypto.randomUUID())
      : null;
    if (idempotencyKey) {
      this.mutationKeys[fingerprint] = idempotencyKey;
      writeMutationKeys(this.mutationKeys);
    }

    const requestBody = idempotencyKey
      ? { ...scopedPayload, idempotency_key: idempotencyKey }
      : scopedPayload;
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(REAL_GENERATION_FUNCTION, {
        body: requestBody,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось связаться с сервисом платной генерации. Повторите попытку позже.", {
        code: "real_generation_request_failed",
      });
    }

    if (error) {
      throw await creatorFunctionError(error);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new CreatorApiError("Сервис генерации вернул некорректный ответ.", {
        code: "real_generation_response_invalid",
      });
    }
    if (data.ok === false || data.error) {
      const details = data.error && typeof data.error === "object"
        ? data.error
        : {
            code: data.code || "real_generation_failed",
            message: String(data.error || data.code || "Generation failed"),
          };
      throw new CreatorApiError(safeGenerationMessage(details), details);
    }
    if (action === "preflight") {
      const preflight = normalizeApiGenerationProviderPreflight(
        data.preflight,
      );
      if (
        preflight === null ||
        preflight.model !== payload.model ||
        preflight.duration_seconds !== payload.duration_seconds ||
        preflight.estimated_credits !==
          realGenerationSku(
            payload.model,
            payload.duration_seconds,
          )?.estimated_credits
      ) {
        throw new CreatorApiError(
          "Runway не подтвердил готовность выбранной модели. Платный запуск не создан.",
          { code: "provider_preflight_invalid" },
        );
      }
      return { ...data, preflight };
    }
    if (!data.job || typeof data.job !== "object" || !data.job.id || !data.job.status) {
      throw new CreatorApiError("Сервис генерации вернул некорректную задачу.", {
        code: "real_generation_response_invalid",
      });
    }

    if (idempotencyKey) {
      delete this.mutationKeys[fingerprint];
      writeMutationKeys(this.mutationKeys);
    }
    return data;
  }

  recordMetric(snapshot) {
    return this.mutate(RPC.recordMetric, {
      ...snapshot,
      source: "manual",
    });
  }

  configureTrackingLink(placementId, targetUrl) {
    return this.mutate(RPC.configureTrackingLink, {
      placement_id: placementId,
      target_url: targetUrl,
    });
  }

  setWbAlias(alias) {
    return this.mutate(RPC.setWbAlias, alias);
  }

  decidePayout(payoutId, decision, details = {}) {
    return this.mutate(RPC.decidePayout, {
      payout_id: payoutId,
      decision,
      ...details,
    });
  }

  confirmPlacement(taskId, finalUrl, complianceAck) {
    return this.mutate(RPC.confirmPlacement, {
      task_id: taskId,
      final_url: finalUrl,
      compliance_ack: complianceAck === true,
    });
  }

  transitionTask(taskId, status, result = {}) {
    return this.mutate(RPC.transitionTask, {
      task_id: taskId,
      status,
      result,
    });
  }

  createFeedback(feedback) {
    return this.mutate(RPC.createFeedback, feedback);
  }

  registerMedia(media) {
    const kind = String(media?.kind || "").trim();
    const payload = { ...media, kind };
    if (mediaKindRequiresProduct(kind)) {
      const sku = String(media?.sku || "").trim();
      const productName = String(media?.product_name || "").trim();
      if (!sku || sku.length > 120) {
        throw new CreatorApiError(
          "Укажите точный артикул товара длиной до 120 символов.",
          { code: "media_sku_required" },
        );
      }
      if (productName.length < 2 || productName.length > 180) {
        throw new CreatorApiError(
          "Укажите точное название товара длиной от 2 до 180 символов.",
          { code: "media_product_name_required" },
        );
      }
      payload.sku = sku;
      payload.product_name = productName;
    } else {
      delete payload.sku;
      delete payload.product_name;
    }
    return this.mutate(RPC.registerMedia, payload);
  }

  captureEvent(event) {
    return this.mutate(RPC.captureEvent, event, { retainOnError: false });
  }

  withOrganization(payload) {
    if (this.organizationId === null || this.organizationId === undefined) {
      throw new CreatorApiError(
        "Для аккаунта ещё не назначена команда. Обратитесь к руководителю.",
        { code: "membership_required" },
      );
    }
    return { ...payload, organization_id: this.organizationId };
  }

  async mutate(functionName, payload, { retainOnError = true } = {}) {
    const scopedPayload = this.withOrganization(payload);
    const fingerprint = `${functionName}:${stableStringify(scopedPayload)}`;
    const idempotencyKey = this.mutationKeys[fingerprint] || crypto.randomUUID();
    this.mutationKeys[fingerprint] = idempotencyKey;
    writeMutationKeys(this.mutationKeys);

    try {
      const response = await this.call(functionName, {
        ...scopedPayload,
        idempotency_key: idempotencyKey,
      });
      delete this.mutationKeys[fingerprint];
      writeMutationKeys(this.mutationKeys);
      return response;
    } catch (error) {
      if (!retainOnError) {
        delete this.mutationKeys[fingerprint];
        writeMutationKeys(this.mutationKeys);
      }
      throw error;
    }
  }

  async uploadPrivateObject(objectKey, file) {
    this.assertPrivateObjectKey(objectKey);
    const { data, error } = await this.supabase.storage
      .from(this.storageBucket)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: file.type || "application/octet-stream",
        upsert: false,
      });

    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
    return data;
  }

  async uploadAiKnowledgeObject(objectKey, file, contentType = file?.type) {
    this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
    const mimeType = String(contentType || "").trim().toLowerCase();
    const sizeBytes = Number(file?.size);
    if (
      !AI_KNOWLEDGE_MIME_TYPES.has(mimeType)
      || !Number.isInteger(sizeBytes)
      || sizeBytes < 1
      || sizeBytes > 25 * 1024 * 1024
    ) {
      throw new CreatorApiError("Файл знаний не прошёл проверку типа или размера.", {
        code: "ai_knowledge_source_file_invalid",
      });
    }
    const { data, error } = await this.supabase.storage
      .from(AI_KNOWLEDGE_BUCKET)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: mimeType,
        upsert: false,
      });
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return data;
  }

  async removeAiKnowledgeObject(objectKey) {
    this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
    const { error } = await this.supabase.storage
      .from(AI_KNOWLEDGE_BUCKET)
      .remove([objectKey]);
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
  }


  async removePrivateObject(objectKey) {
    this.assertPrivateObjectKey(objectKey);
    const { error } = await this.supabase.storage
      .from(this.storageBucket)
      .remove([objectKey]);
    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
  }

  async removePrivateObjects(objectKeys) {
    const keys = [...new Set((objectKeys || []).map((value) => String(value || "").trim()).filter(Boolean))];
    if (!keys.length) return;
    keys.forEach((objectKey) => this.assertPrivateObjectKey(objectKey));
    const { error } = await this.supabase.storage
      .from(this.storageBucket)
      .remove(keys);
    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
  }

  async signedPrivateObjectUrls(objectKeys, expiresIn = 600) {
    const keys = [...new Set((objectKeys || []).map(String).filter(Boolean))];
    if (!keys.length) return new Map();
    keys.forEach((key) => this.assertReadableObjectKey(key));
    const { data, error } = await this.supabase.storage
      .from(this.storageBucket)
      .createSignedUrls(keys, Math.min(900, Math.max(60, Number(expiresIn) || 600)));
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return new Map(
      (data || [])
        .filter((item) => item?.path && item?.signedUrl && !item?.error)
        .map((item) => [item.path, item.signedUrl]),
    );
  }

  async uploadTrainingPracticalObject(bucketId, pathPrefix, objectKey, file) {
    this.assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, true);
    const { data, error } = await this.supabase.storage
      .from(bucketId)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: file.type || "video/mp4",
        upsert: false,
      });
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return data;
  }

  async removeTrainingPracticalObject(bucketId, pathPrefix, objectKey) {
    this.assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, true);
    const { error } = await this.supabase.storage.from(bucketId).remove([objectKey]);
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
  }

  async signedTrainingPracticalObjectUrls(bucketId, objectKeys, expiresIn = 600) {
    const keys = [...new Set((objectKeys || []).map(String).filter(Boolean))];
    if (!keys.length) return new Map();
    keys.forEach((key) => this.assertTrainingPracticalObjectKey(bucketId, "", key, false));
    const { data, error } = await this.supabase.storage
      .from(bucketId)
      .createSignedUrls(keys, Math.min(900, Math.max(60, Number(expiresIn) || 600)));
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return new Map(
      (data || [])
        .filter((item) => item?.path && item?.signedUrl && !item?.error)
        .map((item) => [item.path, item.signedUrl]),
    );
  }

  assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, requireOwnPrefix) {
    const bucket = String(bucketId || "");
    const prefix = String(pathPrefix || "");
    const key = String(objectKey || "");
    const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
    const pattern = new RegExp(`^${uuid}/${uuid}/practical/[0-9a-f-]{20,80}\\.(?:mp4|webm|mov)$`, "iu");
    if (
      bucket !== "contentengine-training"
      || !pattern.test(key)
      || key.includes("..")
      || key.includes("\\")
      || (requireOwnPrefix && (!prefix || !key.startsWith(prefix)))
    ) {
      throw new CreatorApiError("Нет доступа к защищённой пробной работе.", {
        code: "training_practical_storage_denied",
      });
    }
  }

  assertPrivateObjectKey(objectKey) {
    const key = String(objectKey || "");
    if (
      !this.storagePrefix ||
      !key.startsWith(this.storagePrefix) ||
      key === this.storagePrefix ||
      key.includes("..") ||
      key.includes("\\")
    ) {
      throw new CreatorApiError("Нет доступа к этой папке медиатеки.", {
        code: "storage_access_denied",
      });
    }
  }

  assertAiKnowledgeObjectKey(bucketId, objectKey) {
    const key = String(objectKey || "");
    if (
      bucketId !== AI_KNOWLEDGE_BUCKET
      || !this.storagePrefix
      || !key.startsWith(`${this.storagePrefix}ai-knowledge/`)
      || key === `${this.storagePrefix}ai-knowledge/`
      || key.includes("..")
      || key.includes("\\")
    ) {
      throw new CreatorApiError("Нет доступа к защищённой базе знаний.", {
        code: "storage_access_denied",
      });
    }
  }


  assertReadableObjectKey(objectKey) {
    const key = String(objectKey || "");
    const organizationPrefix = String(this.storagePrefix || "").split("/")[0];
    const withinOrganization = organizationPrefix && key.startsWith(`${organizationPrefix}/`);
    if (!withinOrganization || key.includes("..") || key.includes("\\")) {
      throw new CreatorApiError("Нет доступа к этой папке медиатеки.", {
        code: "storage_access_denied",
      });
    }
  }
}

function normalizeContentReviewCodes(values) {
  if (!Array.isArray(values) || values.length > 80) {
    throw new CreatorApiError("Список подтверждений проверки имеет неверный формат.", {
      code: "content_review_decision_codes_invalid",
    });
  }
  const normalized = [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))];
  if (normalized.some((value) => value.length > 120 || !/^[a-z0-9_.:-]+$/iu.test(value))) {
    throw new CreatorApiError("Список подтверждений проверки имеет неверный формат.", {
      code: "content_review_decision_codes_invalid",
    });
  }
  return normalized;
}

const MUTATION_KEY_STORAGE = "contentengine.pending-mutation-keys.v1";

function readMutationKeys() {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(MUTATION_KEY_STORAGE) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function writeMutationKeys(keys) {
  try {
    window.sessionStorage.setItem(MUTATION_KEY_STORAGE, JSON.stringify(keys));
  } catch {
    // RPC idempotency still works for retries made before a page reload.
  }
}

function hasExactObjectKeys(value, keys) {
  return Boolean(value)
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function researchAnalysisHasForbiddenKeys(value) {
  const pending = [value];
  let visitedNodes = 0;
  while (pending.length) {
    const current = pending.pop();
    if (!current || typeof current !== "object") continue;
    visitedNodes += 1;
    if (visitedNodes > 10_000) return true;
    if (Array.isArray(current)) {
      pending.push(...current);
      continue;
    }
    for (const [key, child] of Object.entries(current)) {
      if (RESEARCH_ANALYSIS_FORBIDDEN_KEYS.has(key.toLowerCase())) return true;
      if (child && typeof child === "object") pending.push(child);
    }
  }
  return false;
}

function researchSourceAnalysisIsValid(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
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
    Object.keys(value).length !== exactKeys.length
    || exactKeys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))
    || value.schema_version !== RESEARCH_SOURCE_ANALYSIS_SCHEMA_VERSION
    || !RESEARCH_SOURCE_ANALYSIS_CLASSIFICATIONS.has(value.classification)
    || !Number.isInteger(value.relevance_score)
    || value.relevance_score < 0
    || value.relevance_score > 100
    || !RESEARCH_SOURCE_ANALYSIS_CONFIDENCE.has(value.confidence)
    || typeof value.summary !== "string"
    || value.summary.trim().length < 20
    || value.summary.trim().length > 2_000
    || !Array.isArray(value.structural_signal_keys)
    || value.structural_signal_keys.length > 20
    || !Array.isArray(value.limitations)
    || value.limitations.length > 20
    || researchAnalysisHasForbiddenKeys(value)
  ) return false;
  const structuralSignals = value.structural_signal_keys.map((item) =>
    typeof item === "string" ? item.trim() : ""
  );
  if (
    structuralSignals.some((item) =>
      item.length < 3
      || item.length > 100
      || !RESEARCH_SOURCE_STRUCTURAL_SIGNAL_PATTERN.test(item)
    )
    || new Set(structuralSignals).size !== structuralSignals.length
    || value.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
  ) return false;
  return true;
}

function researchYoutubeObservationAnalysisIsValid(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const exactKeys = [
    "schema_version",
    "classification",
    "review_priority",
    "confidence",
    "recommendation",
    "signals",
    "summary",
    "limitations",
  ];
  const signals = value.signals;
  const signalKeys = [
    "search_position",
    "query_token_overlap_count",
    "query_token_count",
    "published_age_days",
    "same_channel_observation_count",
    "counters_present",
  ];
  if (
    Object.keys(value).length !== exactKeys.length
    || exactKeys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))
    || value.schema_version
      !== RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA_VERSION
    || !RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS.has(
      value.classification,
    )
    || !Number.isInteger(value.review_priority)
    || value.review_priority < 0
    || value.review_priority > 100
    || !["low", "medium"].includes(value.confidence)
    || !["review_candidate", "needs_more_evidence"].includes(
      value.recommendation,
    )
    || !signals
    || typeof signals !== "object"
    || Array.isArray(signals)
    || Object.keys(signals).length !== signalKeys.length
    || signalKeys.some((key) =>
      !Object.prototype.hasOwnProperty.call(signals, key)
    )
    || !Number.isInteger(signals.search_position)
    || signals.search_position < 1
    || signals.search_position > 25
    || !Number.isInteger(signals.query_token_overlap_count)
    || signals.query_token_overlap_count < 0
    || signals.query_token_overlap_count > 999
    || !Number.isInteger(signals.query_token_count)
    || signals.query_token_count < signals.query_token_overlap_count
    || signals.query_token_count > 999
    || !Number.isInteger(signals.published_age_days)
    || signals.published_age_days < 0
    || signals.published_age_days > 9_999_999
    || !Number.isInteger(signals.same_channel_observation_count)
    || signals.same_channel_observation_count < 1
    || signals.same_channel_observation_count > 9_999_999
    || typeof signals.counters_present !== "boolean"
    || typeof value.summary !== "string"
    || value.summary.trim().length < 20
    || value.summary.trim().length > 1_200
    || !Array.isArray(value.limitations)
    || value.limitations.length < 1
    || value.limitations.length > 8
    || value.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
    || researchAnalysisHasForbiddenKeys(value)
  ) return false;
  return true;
}

function normalizeStringArray(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  )];
}

function normalizeGenerationSpecReference(value = {}) {
  if (!hasExactObjectKeys(value, ["spec_id", "spec_version", "spec_hash"])) {
    throw new CreatorApiError("Для проверки нужны точные id, версия и hash ТЗ.", {
      code: "generation_spec_reference_invalid",
    });
  }
  const specId = requireGenerationSpecUuid(
    value.spec_id,
    "generation_spec_id_invalid",
  );
  const specVersion = Number(value.spec_version);
  const specHash = String(value.spec_hash || "").trim().toLowerCase();
  if (
    !Number.isInteger(specVersion)
    || specVersion < 1
    || specVersion > 100_000
    || !/^[0-9a-f]{64}$/u.test(specHash)
  ) {
    throw new CreatorApiError("Серверная версия ТЗ устарела или повреждена.", {
      code: "generation_spec_reference_invalid",
    });
  }
  return {
    spec_id: specId,
    spec_version: specVersion,
    spec_hash: specHash,
  };
}

function normalizeGenerationSpecScopeInput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Заполните точный товар и режим управляемого ТЗ.", {
      code: "generation_spec_scope_invalid",
    });
  }
  const allowedKeys = [
    "primary_media_id",
    "media_ids",
    "platform",
    "model",
    "duration_seconds",
    "product_category",
    "format",
    "audio",
  ];
  if (!hasExactObjectKeys(value, allowedKeys)) {
    throw new CreatorApiError("Параметры управляемого ТЗ заполнены не полностью.", {
      code: "generation_spec_scope_invalid",
    });
  }
  const primaryMediaId = requireGenerationSpecUuid(
    value.primary_media_id,
    "generation_spec_scope_invalid",
  );
  const mediaIds = Array.isArray(value.media_ids)
    ? value.media_ids.map((item) => requireGenerationSpecUuid(
        item,
        "generation_spec_scope_invalid",
      ))
    : [];
  const platform = String(value.platform || "").trim().toLowerCase();
  const model = String(value.model || "").trim().toLowerCase();
  const productCategory = String(value.product_category || "").trim().toLowerCase();
  const format = String(value.format || "").trim();
  const audio = value.audio;
  const durationSeconds = Number(value.duration_seconds);
  const validDuration = model === "seedream5_lite"
    ? durationSeconds === 0
    : model === "gen4_turbo"
      ? [2, 5, 8, 10].includes(durationSeconds)
      : [4, 8, 12, 15].includes(durationSeconds);
  if (
    mediaIds.length < 1
    || mediaIds.length > 5
    || new Set(mediaIds).size !== mediaIds.length
    || mediaIds[0] !== primaryMediaId
    || !["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"]
      .includes(platform)
    || !["gen4_turbo", "seedance2_fast", "seedream5_lite"].includes(model)
    || ![
      "cosmetics", "baa", "sports_food", "food", "household", "apparel",
      "electronics", "other",
    ].includes(productCategory)
    || !["9:16", "1:1", "16:9"].includes(format)
    || typeof audio !== "boolean"
    || !validDuration
  ) {
    throw new CreatorApiError("Параметры управляемого ТЗ не совпадают с выбранным режимом.", {
      code: "generation_spec_scope_invalid",
    });
  }
  return {
    primary_media_id: primaryMediaId,
    media_ids: mediaIds,
    platform,
    model,
    duration_seconds: durationSeconds,
    product_category: productCategory,
    format,
    audio,
  };
}

function normalizeGenerationSpecResearchProvenance(value) {
  if (value === null || value === undefined) return null;
  if (
    !hasExactObjectKeys(value, [
      "research_id", "creative_brief_draft_id", "scenario_position",
    ])
    || ![1, 2, 3].includes(Number(value.scenario_position))
  ) {
    throw new CreatorApiError("Связь ТЗ с утверждённым исследованием устарела.", {
      code: "generation_spec_research_provenance_invalid",
    });
  }
  return {
    research_id: requireGenerationSpecUuid(
      value.research_id,
      "generation_spec_research_provenance_invalid",
    ),
    creative_brief_draft_id: requireGenerationSpecUuid(
      value.creative_brief_draft_id,
      "generation_spec_research_provenance_invalid",
    ),
    scenario_position: Number(value.scenario_position),
  };
}

function normalizeGenerationSpecPerformanceProvenance(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, ["policy_hash", "policy_version"])) {
    throw new CreatorApiError("Связь ТЗ с обученной политикой устарела.", {
      code: "generation_spec_performance_provenance_invalid",
    });
  }
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  const policyVersion = String(value.policy_version || "").trim();
  if (
    !/^[0-9a-f]{64}$/u.test(policyHash)
    || policyVersion.length < 3
    || policyVersion.length > 80
  ) {
    throw new CreatorApiError("Связь ТЗ с обученной политикой устарела.", {
      code: "generation_spec_performance_provenance_invalid",
    });
  }
  return { policy_hash: policyHash, policy_version: policyVersion };
}

function normalizeGenerationSpecRepairProvenance(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, [
    "source_review_id", "source_generation_job_id", "policy_hash",
  ])) {
    throw new CreatorApiError("Связь исправления с QA устарела.", {
      code: "generation_spec_repair_provenance_invalid",
    });
  }
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/u.test(policyHash)) {
    throw new CreatorApiError("Связь исправления с QA устарела.", {
      code: "generation_spec_repair_provenance_invalid",
    });
  }
  return {
    source_review_id: requireGenerationSpecUuid(
      value.source_review_id,
      "generation_spec_repair_provenance_invalid",
    ),
    source_generation_job_id: requireGenerationSpecUuid(
      value.source_generation_job_id,
      "generation_spec_repair_provenance_invalid",
    ),
    policy_hash: policyHash,
  };
}

function normalizeGenerationSpecLearningContext(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Контекст обучения для ТЗ отсутствует.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const source = String(value.source || "").trim().toLowerCase();
  const required = [
    "creative_angle", "hook_patterns", "source", "compiler_version",
    "product_category",
  ];
  const optional = source === "performance_learning"
    ? ["applied_policy_hash"]
    : source === "approved_research"
      ? ["creative_brief_draft_id", "scenario_position"]
      : [];
  if (!hasExactObjectKeys(value, [...required, ...optional])) {
    throw new CreatorApiError("Контекст обучения для ТЗ имеет неизвестные поля.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const creativeAngle = String(value.creative_angle || "").trim().toLowerCase();
  const hooks = Array.isArray(value.hook_patterns)
    ? value.hook_patterns.map((item) => String(item || "").trim().toLowerCase())
    : [];
  const compilerVersion = String(value.compiler_version || "").trim();
  const productCategory = String(value.product_category || "").trim().toLowerCase();
  const allowedAngles = new Set([
    "product_focus", "trust_builder", "demonstration", "comparison",
    "objection_handling", "curiosity_gap",
  ]);
  const allowedHooks = new Set([
    "question_led", "why_explanation", "before_buying", "comparison",
    "demonstration", "first_person", "numbered", "concise",
  ]);
  if (
    !["baseline", "approved_research", "performance_learning"].includes(source)
    || !allowedAngles.has(creativeAngle)
    || hooks.length > 8
    || new Set(hooks).size !== hooks.length
    || hooks.some((item) => !allowedHooks.has(item))
    || !/^[a-z0-9][a-z0-9._-]{2,63}$/u.test(compilerVersion)
    || ![
      "cosmetics", "baa", "sports_food", "food", "household", "apparel",
      "electronics", "other",
    ].includes(productCategory)
    || (source === "baseline" && (
      creativeAngle !== "product_focus" || hooks.length !== 0
    ))
  ) {
    throw new CreatorApiError("Контекст обучения для ТЗ устарел.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const normalized = {
    creative_angle: creativeAngle,
    hook_patterns: hooks,
    source,
    compiler_version: compilerVersion,
    product_category: productCategory,
  };
  if (source === "performance_learning") {
    const hash = String(value.applied_policy_hash || "").trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/u.test(hash)) {
      throw new CreatorApiError("Hash обученной политики для ТЗ устарел.", {
        code: "generation_spec_learning_context_invalid",
      });
    }
    normalized.applied_policy_hash = hash;
  } else if (source === "approved_research") {
    const position = Number(value.scenario_position);
    if (![1, 2, 3].includes(position)) {
      throw new CreatorApiError("Позиция исследовательского сценария устарела.", {
        code: "generation_spec_learning_context_invalid",
      });
    }
    normalized.creative_brief_draft_id = requireGenerationSpecUuid(
      value.creative_brief_draft_id,
      "generation_spec_learning_context_invalid",
    );
    normalized.scenario_position = position;
  }
  return normalized;
}

function normalizeGenerationSpecRepairContext(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, [
    "source_review_id", "source_generation_job_id", "guard_codes",
    "policy_hash", "compiler_version",
  ])) {
    throw new CreatorApiError("Контекст исправления для ТЗ устарел.", {
      code: "generation_spec_repair_context_invalid",
    });
  }
  const guardCodes = Array.isArray(value.guard_codes)
    ? value.guard_codes.map((item) => String(item || "").trim().toLowerCase())
    : [];
  const allowed = new Set([
    "product_fidelity", "technical_stability", "audio_quality",
    "speech_fidelity", "hook_clarity", "visual_quality", "trust",
    "platform_fit",
  ]);
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  if (
    value.compiler_version !== "review-repair-v1"
    || guardCodes.length < 1
    || guardCodes.length > 3
    || new Set(guardCodes).size !== guardCodes.length
    || guardCodes.some((code) => !allowed.has(code))
    || !/^[0-9a-f]{64}$/u.test(policyHash)
  ) {
    throw new CreatorApiError("Контекст исправления для ТЗ устарел.", {
      code: "generation_spec_repair_context_invalid",
    });
  }
  return {
    source_review_id: requireGenerationSpecUuid(
      value.source_review_id,
      "generation_spec_repair_context_invalid",
    ),
    source_generation_job_id: requireGenerationSpecUuid(
      value.source_generation_job_id,
      "generation_spec_repair_context_invalid",
    ),
    guard_codes: guardCodes,
    policy_hash: policyHash,
    compiler_version: "review-repair-v1",
  };
}

function normalizeGenerationSpecPatch(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Исправленная версия ТЗ заполнена не полностью.", {
      code: "generation_spec_patch_invalid",
    });
  }
  const allowed = [
    "exact_scope",
    "editable_intent",
    "proposed_prompt",
    "learning_context",
    "repair_context",
    "research_provenance",
    "performance_policy_provenance",
    "repair_provenance",
    "outcome_selection_id",
  ];
  if (
    Object.keys(value).some((key) => !allowed.includes(key))
    || !Object.hasOwn(value, "exact_scope")
    || !Object.hasOwn(value, "editable_intent")
    || !Object.hasOwn(value, "proposed_prompt")
    || !Object.hasOwn(value, "learning_context")
    || !Object.hasOwn(value, "repair_context")
  ) {
    throw new CreatorApiError("Исправленная версия ТЗ содержит неизвестные поля.", {
      code: "generation_spec_patch_invalid",
    });
  }
  const editableIntent = String(value.editable_intent || "").trim();
  const proposedPrompt = String(value.proposed_prompt || "").trim();
  if (
    editableIntent.length < 1
    || editableIntent.length > 1_200
    || proposedPrompt.length < 1
    || proposedPrompt.length > 1_200
  ) {
    throw new CreatorApiError("Исправленный замысел или prompt имеет неверную длину.", {
      code: "generation_spec_patch_invalid",
    });
  }
  return {
    exact_scope: normalizeGenerationSpecScopeInput(value.exact_scope),
    editable_intent: editableIntent,
    proposed_prompt: proposedPrompt,
    learning_context: normalizeGenerationSpecLearningContext(
      value.learning_context,
    ),
    repair_context: normalizeGenerationSpecRepairContext(
      value.repair_context,
    ),
    research_provenance: normalizeGenerationSpecResearchProvenance(
      value.research_provenance,
    ),
    performance_policy_provenance:
      normalizeGenerationSpecPerformanceProvenance(
        value.performance_policy_provenance,
      ),
    repair_provenance: normalizeGenerationSpecRepairProvenance(
      value.repair_provenance,
    ),
    ...(value.outcome_selection_id
      ? { outcome_selection_id: requireGenerationSpecUuid(
          value.outcome_selection_id,
          "generation_spec_outcome_selection_invalid",
        ) }
      : {}),
  };
}

function requireGenerationSpecUuid(value, code) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!isUuid(normalized)) {
    throw new CreatorApiError("Ссылка управляемого ТЗ имеет неверный формат.", {
      code,
    });
  }
  return normalized;
}

function normalizeSpendLimit(value, label) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1 || number > 100_000_000) {
    throw new CreatorApiError(`Укажите ${label} лимит от $0.01 до $1 000 000.`, {
      code: "generation_budget_limits_invalid",
    });
  }
  return number;
}

function validateCampaignPolicyInput({
  dailyLimitMinor,
  monthlyLimitMinor,
  perRequestLimitMinor,
  reason,
}) {
  if (perRequestLimitMinor > dailyLimitMinor || dailyLimitMinor > monthlyLimitMinor) {
    throw new CreatorApiError("Лимит одного запуска должен быть не больше дневного, а дневной — месячного.", {
      code: "generation_campaign_policy_values_invalid",
    });
  }
  if (reason.length < 8 || reason.length > 500 || /[\u0000-\u001f\u007f]/u.test(reason)) {
    throw new CreatorApiError("Укажите причину изменения бюджета кампании длиной от 8 до 500 символов.", {
      code: "generation_budget_reason_invalid",
    });
  }
}

function normalizeAccessEmail(value) {
  const email = String(value || "").trim().toLowerCase();
  if (
    !email
    || email.length > 320
    || !/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u.test(email)
  ) return "";
  return email;
}

export function mergeGenerationMediaIdentity(response, identityResponse) {
  const wrapped = response?.data && typeof response.data === "object"
    && !Array.isArray(response.data);
  const source = wrapped ? response.data : response;
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return response;
  }
  const identitySource = identityResponse?.data
    && typeof identityResponse.data === "object"
    && !Array.isArray(identityResponse.data)
    ? identityResponse.data
    : identityResponse;
  const identities = Array.isArray(identitySource?.items)
    ? identitySource.items
    : [];
  const identityById = new Map();
  for (const item of identities) {
    const id = String(item?.public_id || item?.id || "").trim();
    const sku = String(item?.sku || "").trim();
    const productName = String(item?.product_name || "").trim();
    if (
      !isUuid(id)
      || item?.identity_verified !== true
      || !sku
      || !productName
    ) continue;
    identityById.set(id, {
      product_id: String(item?.product_id || "").trim(),
      sku,
      product_name: productName,
      rights_confirmed: item?.rights_confirmed === true,
      identity_verified: true,
    });
  }
  const media = Array.isArray(source.media) ? source.media : [];
  const mergedSource = {
    ...source,
    media: media.map((item) => {
      const id = String(item?.public_id || item?.id || "").trim();
      const identity = identityById.get(id);
      return identity
        ? { ...item, ...identity }
        : {
            ...item,
            identity_verified: false,
            rights_confirmed: false,
          };
    }),
  };
  return wrapped
    ? { ...response, data: mergedSource }
    : mergedSource;
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
    String(value || ""),
  );
}

function validContentReviewTechnicalMetrics(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const sourceType = String(value.source_type || "").trim().toLowerCase();
  const finiteInRange = (field, minimum, maximum) =>
    typeof value[field] === "number"
    && Number.isFinite(value[field])
    && value[field] >= minimum
    && value[field] <= maximum;
  if (sourceType === "image") {
    return Number.isInteger(Number(value.frame_count))
      && Number(value.frame_count) === 1;
  }
  const temporalScanValid = value.temporal_scan_status === "completed"
    && value.temporal_scan_strategy === "uniform_full_duration_v1"
    && Number.isInteger(value.temporal_scan_frame_count)
    && value.temporal_scan_frame_count >= 12
    && value.temporal_scan_frame_count <= 24
    && finiteInRange("duration_seconds", 0.001, 3_600)
    && finiteInRange("temporal_scan_first_second", 0, 3_600)
    && finiteInRange("temporal_scan_last_second", 0, 3_600)
    && value.temporal_scan_last_second > value.temporal_scan_first_second
    && value.temporal_scan_last_second <= value.duration_seconds
    && finiteInRange("temporal_scan_coverage_ratio", 0.9, 1)
    && Math.abs(
      (
        value.temporal_scan_last_second - value.temporal_scan_first_second
      ) / value.duration_seconds - value.temporal_scan_coverage_ratio,
    ) <= 0.02
    && finiteInRange("temporal_black_frame_ratio", 0, 1)
    && finiteInRange("temporal_frozen_transition_ratio", 0, 1)
    && finiteInRange("temporal_mean_frame_difference", 0, 1);
  const sampledAt = Array.isArray(value.sampled_at_seconds)
    ? value.sampled_at_seconds
    : [];
  const sampledAtValid = sampledAt.length === 5
    && sampledAt.every((item, index) =>
      typeof item === "number"
      && Number.isFinite(item)
      && item >= 0
      && item <= value.duration_seconds
      && (index === 0 || item > sampledAt[index - 1])
    );
  const timelineAtlasValid = value.timeline_atlas_status === "completed"
    && value.timeline_atlas_version === "dense_full_duration_v1"
    && value.timeline_atlas_frame_ordinal === 5
    && Number.isInteger(value.timeline_atlas_frame_count)
    && value.timeline_atlas_frame_count >= 12
    && value.timeline_atlas_frame_count <= 24
    && value.timeline_atlas_frame_count === value.temporal_scan_frame_count
    && finiteInRange("timeline_atlas_first_second", 0, 3_600)
    && finiteInRange("timeline_atlas_last_second", 0, 3_600)
    && value.timeline_atlas_last_second > value.timeline_atlas_first_second
    && value.timeline_atlas_last_second <= value.duration_seconds
    && Math.abs(
      value.timeline_atlas_first_second - value.temporal_scan_first_second,
    ) <= 0.002
    && Math.abs(
      value.timeline_atlas_last_second - value.temporal_scan_last_second,
    ) <= 0.002
    && finiteInRange("timeline_atlas_coverage_ratio", 0.9, 1)
    && Math.abs(
      value.timeline_atlas_coverage_ratio - value.temporal_scan_coverage_ratio,
    ) <= 0.002
    && finiteInRange("timeline_atlas_max_gap_seconds", 0.001, 3_600)
    && value.timeline_atlas_max_gap_seconds <= value.duration_seconds
    && finiteInRange("timeline_atlas_sample_rate_fps", 0.003, 24_000)
    && Math.abs(
      value.timeline_atlas_sample_rate_fps -
        value.timeline_atlas_frame_count / value.duration_seconds,
    ) <= 0.02
    && Number.isInteger(value.timeline_atlas_columns)
    && value.timeline_atlas_columns >= 2
    && value.timeline_atlas_columns <= 8
    && Number.isInteger(value.timeline_atlas_rows)
    && value.timeline_atlas_rows >= 2
    && value.timeline_atlas_rows <= 8
    && value.timeline_atlas_columns * value.timeline_atlas_rows >=
      value.timeline_atlas_frame_count
    && value.timeline_atlas_columns * (value.timeline_atlas_rows - 1) <
      value.timeline_atlas_frame_count
    && value.timeline_atlas_order === "row_major_chronological"
    && typeof value.timeline_atlas_dense_short_video === "boolean"
    && value.timeline_atlas_dense_short_video === (
      value.duration_seconds <= 10
      && value.timeline_atlas_coverage_ratio >= 0.9
      && value.timeline_atlas_max_gap_seconds <= 0.5
    )
    && sampledAtValid
    && Math.abs(
      sampledAt.at(-1) - value.timeline_atlas_last_second,
    ) <= 0.002;
  const continuityScanValid = value.duration_seconds <= 15
    ? value.continuity_scan_status === "completed"
      && value.continuity_scan_strategy === "browser_presented_frames_v1"
      && Number.isInteger(value.continuity_scan_callback_count)
      && value.continuity_scan_callback_count >= 2
      && value.continuity_scan_callback_count <= 3_600
      && Number.isInteger(value.continuity_scan_presented_frame_count)
      && value.continuity_scan_presented_frame_count ===
        value.continuity_scan_callback_count
      && value.continuity_scan_presented_frame_count <= 10_000
      && Number.isInteger(value.continuity_scan_missed_frame_count)
      && value.continuity_scan_missed_frame_count === 0
      && finiteInRange("continuity_scan_first_second", 0, 15)
      && finiteInRange("continuity_scan_last_second", 0, 15)
      && value.continuity_scan_last_second >
        value.continuity_scan_first_second
      && value.continuity_scan_last_second <= value.duration_seconds
      && finiteInRange("continuity_scan_coverage_ratio", 0.8, 1)
      && Math.abs(
        (
          value.continuity_scan_last_second -
          value.continuity_scan_first_second
        ) / value.duration_seconds -
          value.continuity_scan_coverage_ratio,
      ) <= 0.02
      && finiteInRange("continuity_scan_max_gap_seconds", 0, 0.5)
      && finiteInRange("continuity_black_frame_ratio", 0, 1)
      && finiteInRange(
        "continuity_longest_black_run_seconds",
        0,
        value.duration_seconds,
      )
      && finiteInRange("continuity_duplicate_transition_ratio", 0, 1)
      && finiteInRange(
        "continuity_longest_duplicate_run_seconds",
        0,
        value.duration_seconds,
      )
      && finiteInRange("continuity_mean_frame_difference", 0, 1)
      && value.continuity_raw_frames_persisted === false
    : value.continuity_scan_status === "not_applicable"
      && value.continuity_scan_strategy === "browser_presented_frames_v1"
      && value.continuity_scan_not_applicable_reason ===
        "duration_above_short_video_limit"
      && value.continuity_scan_duration_limit_seconds === 15;
  if (
    sourceType !== "video"
    || !Number.isInteger(Number(value.frame_count))
    || Number(value.frame_count) !== 5
    || typeof value.audio_analyzed !== "boolean"
    || !["completed", "unavailable"].includes(
      String(value.audio_analysis_status || ""),
    )
    || !(
      value.audio_expected === null
      || typeof value.audio_expected === "boolean"
    )
    || value.speech_transcription_notice_version !== "openai_mp4_v1"
    || !temporalScanValid
    || !timelineAtlasValid
    || !continuityScanValid
  ) return false;
  if (value.audio_analysis_status === "unavailable") {
    return value.audio_analyzed === false;
  }
  return value.audio_analyzed === true
    && Number.isInteger(value.audio_channel_count)
    && value.audio_channel_count >= 1
    && value.audio_channel_count <= 32
    && Number.isInteger(value.audio_sample_rate_hz)
    && value.audio_sample_rate_hz >= 8_000
    && value.audio_sample_rate_hz <= 384_000
    && finiteInRange("audio_duration_seconds", 0.001, 3_600)
    && (
      value.audio_video_duration_delta_seconds === null
      || finiteInRange("audio_video_duration_delta_seconds", 0, 3_600)
    )
    && finiteInRange("audio_peak_dbfs", -160, 0)
    && finiteInRange("audio_rms_dbfs", -160, 0)
    && finiteInRange("audio_silence_ratio", 0, 1)
    && finiteInRange("audio_clipping_ratio", 0, 1);
}

function normalizePublicRecoveryToken(value) {
  const token = String(value || "").trim();
  if (token.length < 16 || token.length > 512 || !/^[a-z0-9._~-]+$/iu.test(token)) return "";
  return token;
}

function normalizePublicRecoveryResponse(data, expectedAction, context = {}) {
  const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
    ? data.data
    : data;
  const receipt = source?.receipt && typeof source.receipt === "object" && !Array.isArray(source.receipt)
    ? source.receipt
    : source;
  const action = String(source?.action || receipt?.action || expectedAction).trim().toLowerCase();
  const receiptToken = normalizePublicRecoveryToken(
    receipt?.receipt_token || source?.receipt_token || context.receipt_token,
  );
  const requestId = String(
    receipt?.request_id || source?.request_id || context.request_id || "",
  ).trim();
  const status = String(receipt?.status || source?.status || "accepted").trim().toLowerCase();
  const retryAfterSeconds = Number(
    receipt?.retry_after_seconds ?? source?.retry_after_seconds ?? 0,
  );
  const requestedAt = String(receipt?.requested_at || source?.requested_at || "").trim();
  const cooldownCandidate = String(
    receipt?.cooldown_until || source?.cooldown_until
      || receipt?.retry_not_before || source?.retry_not_before || "",
  ).trim();
  const cooldownDate = cooldownCandidate ? new Date(cooldownCandidate) : null;
  const requestedDate = requestedAt ? new Date(requestedAt) : null;

  if (
    !source
    || typeof source !== "object"
    || Array.isArray(source)
    || source.ok !== true
    || action !== expectedAction
    || !receiptToken
    || (expectedAction === "request" && !isUuid(requestId))
    || !/^[a-z0-9_]{2,64}$/u.test(status)
    || !Number.isInteger(retryAfterSeconds)
    || retryAfterSeconds < 0
    || retryAfterSeconds > 86_400
    || (requestedDate && Number.isNaN(requestedDate.getTime()))
    || (cooldownDate && Number.isNaN(cooldownDate.getTime()))
  ) {
    throw new CreatorApiError("Сервис восстановления вернул неполную квитанцию. Не запускайте новый запрос.", {
      code: "public_recovery_response_invalid",
    });
  }

  return {
    receiptToken,
    requestId,
    status,
    requestedAt: requestedDate?.toISOString() || new Date().toISOString(),
    cooldownUntil: cooldownDate?.toISOString()
      || new Date(Date.now() + retryAfterSeconds * 1000).toISOString(),
    retryAfterSeconds,
  };
}

async function publicRecoveryFunctionError(error) {
  let code = String(error?.code || "public_recovery_request_failed");
  let retryAfterSeconds = 0;
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(body.code || body.error?.code || "");
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
        const retryCandidate = Number(body.retry_after_seconds || body.error?.retry_after_seconds);
        if (Number.isInteger(retryCandidate) && retryCandidate > 0 && retryCandidate <= 86_400) {
          retryAfterSeconds = retryCandidate;
        }
      }
    } catch {
      // Never expose account existence or raw Auth provider responses.
    }
  }
  const retry = retryAfterSeconds
    ? ` Повторная проверка станет доступна примерно через ${retryAfterSeconds} сек.`
    : "";
  const message = ["email_rate_limited", "public_recovery_rate_limited"].includes(code)
    ? `Запрос уже принят сервером.${retry}`
    : "Сервис восстановления временно не ответил. Квитанция сохранена; повторите проверку позже.";
  return new CreatorApiError(message, {
    code,
    details: retryAfterSeconds ? { retry_after_seconds: retryAfterSeconds } : null,
  });
}

async function accessFunctionError(error) {
  let code = String(error?.code || "access_request_failed");
  let retryAfterSeconds = 0;
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(body.code || body.error?.code || "");
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
        const retryCandidate = Number(body.retry_after_seconds || body.error?.retry_after_seconds);
        if (Number.isInteger(retryCandidate) && retryCandidate > 0 && retryCandidate <= 86_400) {
          retryAfterSeconds = retryCandidate;
        }
      }
    } catch {
      // Do not expose raw provider, Auth, or delivery responses to the browser.
    }
  }

  return new CreatorApiError(safeAccessMessage(code, retryAfterSeconds), {
    code,
    details: retryAfterSeconds ? { retry_after_seconds: retryAfterSeconds } : null,
  });
}

function safeAccessMessage(code, retryAfterSeconds = 0) {
  const retry = retryAfterSeconds
    ? ` Повторите проверку примерно через ${retryAfterSeconds} сек.`
    : "";
  const messages = {
    access_action_invalid: "Не удалось определить безопасное действие с доступом.",
    access_email_invalid: "Укажите точный рабочий email участника.",
    access_request_id_invalid: "Не удалось подготовить безопасный номер восстановления.",
    authentication_required: "Сессия завершилась. Войдите снова перед проверкой доступа.",
    auth_session_required: "Сессия завершилась. Войдите снова перед проверкой доступа.",
    authorization_required: "Проверять доступ может только руководитель команды.",
    role_not_allowed: "Проверять доступ может только руководитель команды.",
    email_rate_limited: `Почтовый сервис временно ограничил повтор.${retry}`,
    manual_review_required: "Автоматическое восстановление остановлено. Проверьте адрес и состояние участника вручную.",
    access_status_unavailable: "Состояние доступа временно не удалось проверить. Новое письмо не отправляйте.",
    access_journal_unavailable: "Журнал писем временно недоступен. Новое письмо не отправляйте.",
    access_journal_finalize_failed: "Действие принято, но журнал не подтвердил итог. Обновите сводку перед повтором.",
    auth_runtime_not_configured: "Сервис восстановления требует настройки руководителем системы.",
    recovery_provider_unavailable: "Почтовый сервис восстановления временно недоступен.",
    recovery_provider_failed: "Почтовый сервис не подтвердил восстановление. Проверьте статус перед повтором.",
    recovery_provider_outcome_unknown: "Итог восстановления не подтверждён. Не запускайте повтор до обновления статуса.",
    invite_provider_outcome_unknown: "Итог приглашения не подтверждён. Не запускайте повтор до обновления статуса.",
    access_request_failed: "Сервис доступа временно не ответил. Обновите сводку и повторите позже.",
    access_response_invalid: "Сервис доступа вернул неполный ответ. Новое письмо не отправляйте.",
  };
  return messages[code] || "Не удалось безопасно проверить доступ. Обновите сводку и повторите позже.";
}

async function researchIngestionFunctionError(error) {
  let code = String(error?.code || "research_youtube_ingestion_unavailable");
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(
          body.code
          || (body.error && typeof body.error === "object" ? body.error.code : body.error)
          || "",
        );
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
      }
    } catch {
      // Never expose raw provider or infrastructure responses to the browser.
    }
  }
  const messages = {
    authentication_required: "Сессия завершилась. Войдите снова перед ручной YouTube‑проверкой.",
    auth_session_required: "Сессия завершилась. Войдите снова перед ручной YouTube‑проверкой.",
    authorization_required: "У этой роли нет права запускать внешний YouTube‑запрос.",
    research_youtube_invoke_not_authorized: "Сервер не подтвердил право этого пользователя на сохранённый YouTube‑запуск.",
    research_youtube_global_rollout_gate_required: "Глобальный контур YouTube пока закрыт оператором.",
    research_youtube_rollout_gate_required: "Обновление категории ещё не включено после успешного canary.",
    research_youtube_retention_control_required: "YouTube‑запрос остановлен: сервер не подтвердил свежую очистку API‑данных.",
    research_youtube_transport_gate_closed: "Условия запуска изменились до внешнего вызова. Запрос остановлен без автоматического повтора.",
    research_youtube_ingestion_lease_inactive: "Безопасная аренда запуска истекла. Запрос завершён без автоматического повтора.",
    research_youtube_local_daily_quota_exhausted: "Дневной лимит YouTube‑запросов по тихоокеанскому времени исчерпан.",
    provider_configuration_error: "Ключ YouTube Data API не настроен. Внешний запрос не выполнен.",
    provider_authentication_failed: "YouTube Data API отклонил ключ. Внешний запрос остановлен.",
    provider_quota_exhausted: "Квота YouTube Data API исчерпана. Автоматического повтора не будет.",
    provider_rate_limited: "YouTube временно ограничил запрос. Автоматического повтора не будет.",
    provider_request_rejected: "YouTube отклонил параметры запроса. Проверьте статус запуска.",
    provider_unavailable: "YouTube Data API временно не ответил. Автоматического повтора не будет.",
    provider_response_invalid: "YouTube вернул неполный ответ. Данные не приняты.",
    provider_outcome_unknown: "Результат внешнего вызова не подтверждён. Не повторяйте запрос до обновления статуса.",
    youtube_transport_receipt_failed: "Квитанция внешнего вызова не сохранена. Не повторяйте запрос до проверки статуса.",
    ingestion_rejected: "Сервер остановил YouTube‑запуск до безопасного завершения.",
    ingestion_unavailable: "Запуск сохранён, но транспорт YouTube временно недоступен. Проверьте статус перед новым запросом.",
    research_youtube_ingestion_unavailable: "Запуск сохранён, но транспорт YouTube временно недоступен. Проверьте статус перед новым запросом.",
  };
  return new CreatorApiError(
    messages[code]
      || "YouTube‑запуск не завершён. Обновите статус и не повторяйте внешний запрос автоматически.",
    { code, message: /^[a-z0-9_]{3,96}$/u.test(code) ? code : null },
  );
}

async function creatorFunctionError(error) {
  let details = {
    code: error?.code || "real_generation_request_failed",
    message: error?.message || "Не удалось вызвать сервис платной генерации.",
  };
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body?.error && typeof body.error === "object") details = { ...details, ...body.error };
      else if (body && typeof body === "object") details = { ...details, ...body };
    } catch {
      // Do not surface raw provider or infrastructure responses to the browser.
    }
  }
  return new CreatorApiError(safeGenerationMessage(details), details);
}

async function contentReviewFunctionError(error) {
  let details = {
    code: error?.code || "content_review_request_failed",
    message: error?.message || "Не удалось вызвать сервис проверки контента.",
  };
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body?.error && typeof body.error === "object" && !Array.isArray(body.error)) {
        details = { ...details, ...body.error };
      } else if (body && typeof body === "object" && !Array.isArray(body)) {
        details = {
          ...details,
          ...body,
          code: body.code || (typeof body.error === "string" ? body.error : details.code),
        };
      }
    } catch {
      // Never expose raw provider or infrastructure responses to the browser.
    }
  }
  return new CreatorApiError(safeContentReviewMessage(details), details);
}

function safeContentReviewMessage(details) {
  return toFriendlyMessage({
    code: details?.code || "content_review_request_failed",
    message: "Сервис проверки временно недоступен. Запуск сохранён — проверьте его статус позже.",
  });
}

function safeGenerationMessage(details) {
  return toFriendlyMessage({
    code: details?.code || "real_generation_request_failed",
    message: "Не удалось выполнить платную генерацию. Повторите попытку позже.",
  });
}

function toFriendlyMessage(error) {
  const raw = String(error?.message || "Неизвестная ошибка");
  const diagnostic = [error?.code, error?.message, error?.details, error?.hint]
    .filter(Boolean)
    .join(" ");
  const known = {
    onboarding_required: "Сначала завершите обучение и сдайте экзамен.",
    final_exam_required: "Рабочий кабинет откроется после итогового экзамена.",
    four_courses_required: "Сначала завершите все четыре обязательных курса.",
    required_courses_incomplete: "Сначала завершите все четыре обязательных курса.",
    refreshed_courses_required: "Пройдите обновлённые рабочие аттестации всех четырёх блоков и завершите каждый блок заново.",
    course_not_found: "Учебный модуль больше недоступен. Обновите каталог.",
    course_knowledge_check_required: "Сначала пройдите рабочую аттестацию этого блока на сервере.",
    course_practice_required: "Сначала завершите обязательную практику этого блока.",
    training_progress_sync_required: "Не удалось подтвердить практику на сервере. Проверьте соединение и повторите завершение блока — прогресс на экране сохранён.",
    course_check_answers_invalid: "Проверьте все решения рабочей аттестации и отправьте их ещё раз.",
    course_check_catalog_unavailable: "Рабочая аттестация временно недоступна. Обновите страницу.",
    unknown_course_check_question: "Аттестация обновилась. Обновите страницу и ответьте заново.",
    course_check_cooldown: "Следующая попытка рабочей аттестации откроется после обязательной паузы.",
    course_check_daily_attempt_limit: "Лимит попыток рабочей аттестации за 24 часа исчерпан. Повторите материал и вернитесь позже.",
    practical_project_self_review_not_allowed: "Свою пробную работу принимать нельзя: её должен независимо проверить другой руководитель.",
    practical_project_private_file_required: "Финальный допуск выдаётся только по защищённому MP4. Верните внешнюю ссылку на доработку и запросите файл.",
    practical_project_review_pending: "Работа уже отправлена и ожидает решения руководителя.",
    practical_project_version_conflict: "Работа изменилась в другой вкладке. Обновите очередь перед решением.",
    exam_catalog_unavailable: "Каталог экзамена временно недоступен. Обновите страницу позже.",
    exam_cooldown: "Новая попытка экзамена пока недоступна. Дождитесь времени, указанного на экране.",
    exam_attempt_limit_active: "Лимит попыток за 24 часа исчерпан. Дождитесь времени следующей попытки на экране.",
    membership_required: "Для аккаунта ещё не назначена команда. Обратитесь к руководителю.",
    membership_suspended: "Доступ приостановлен. Обратитесь к руководителю вашей команды.",
    membership_revoked: "Доступ отозван. Обратитесь к руководителю вашей команды.",
    inactive_membership: "Доступ к команде приостановлен. Обратитесь к руководителю.",
    active_membership_required: "Доступ к команде приостановлен. Обратитесь к руководителю.",
    profile_not_active: "Аккаунт приостановлен. Обратитесь к руководителю.",
    verified_email_required: "Для работы нужен аккаунт с подтверждённой почтой.",
    role_not_allowed: "У вашей роли нет права на это действие.",
    mock_only_required: "Платная генерация отключена. Доступен только dry-run задач без файлов и списаний.",
    real_generation_is_disabled: "Платная генерация сейчас недоступна. Используйте dry-run задач без файлов и списаний.",
    real_generation_exactly_one_media_required: "Для платного запуска выберите ровно одно точное фото товара.",
    real_generation_product_references_invalid: "Выберите от одного до пяти точных фото одного товара.",
    product_reference_media_ids_invalid: "Выберите от одного до пяти разных ракурсов одного товара.",
    exact_product_reference_bundle_mismatch: "Выбранные фото должны принадлежать одному товару и иметь подтверждённые права.",
    generation_product_interaction_invalid: "Восстановите безопасное ТЗ с учётом реального размера и способа использования товара.",
    real_spend_confirmation_required: "Подтвердите создание одного платного видео по указанной цене.",
    real_generation_payload_invalid: "Форма платного запуска несовместима с сервером. Обновите портал перед повторной попыткой.",
    real_generation_sku_invalid: "Параметры платного режима не совпадают с подтверждённой ценой.",
    real_generation_sku_binding_invalid: "Сервер не смог связать длительность, звук и подтверждённую цену запуска.",
    real_generation_action_invalid: "Неизвестное действие платной генерации.",
    real_generation_response_invalid: "Сервис генерации вернул некорректный ответ.",
    real_generation_request_failed: "Не удалось вызвать сервис платной генерации. Повторите попытку позже.",
    provider_preflight_invalid: "Runway не подтвердил готовность выбранной модели. Платный запуск не создан.",
    provider_configuration_error: "Ключ Runway не настроен. Платный запуск не создан.",
    provider_authentication_failed: "Runway отклонил ключ доступа. Платный запуск не создан.",
    provider_credits_unavailable: "В Runway недостаточно кредитов для выбранного запуска. Деньги не списаны.",
    provider_rate_limited: "Суточная квота Runway исчерпана. Платный запуск не создан.",
    provider_request_rejected: "Выбранная модель сейчас недоступна в Runway. Платный запуск не создан.",
    provider_request_failed: "Runway не ответил на бесплатную проверку готовности. Платный запуск не создан.",
    provider_response_invalid: "Runway вернул некорректный ответ проверки. Платный запуск не создан.",
    real_generation_failed: "Платная генерация завершилась ошибкой. Проверьте статус задачи.",
    real_generation_user_daily_quota_exceeded: "Дневной лимит платных запусков исчерпан. Продолжите после обновления лимита.",
    real_generation_organization_daily_quota_exceeded: "Командный дневной лимит платных запусков исчерпан. Обратитесь к руководителю.",
    real_generation_assignee_concurrency_exceeded: "У выбранного исполнителя уже создаётся платный ролик. Дождитесь его завершения — повторная оплата не требуется.",
    real_generation_organization_concurrency_exceeded: "Командная очередь платных роликов заполнена. Дождитесь завершения текущих задач.",
    paid_generation_paused: "Платная генерация приостановлена руководителем. Dry-run задач без файлов остаётся доступен.",
    paid_generation_policy_missing: "Для команды ещё не настроен безопасный денежный лимит платной генерации.",
    generation_daily_budget_exceeded: "Дневной бюджет платной генерации исчерпан. Dry-run задач без файлов остаётся доступен.",
    generation_monthly_budget_exceeded: "Месячный бюджет платной генерации исчерпан. Обратитесь к руководителю.",
    generation_per_request_budget_exceeded: "Цена запуска превышает утверждённый разовый лимит.",
    generation_budget_reservation_invalid: "Сервер не подтвердил резерв денег. Платный запрос провайдеру не отправлен.",
    generation_budget_policy_changed: "Лимиты изменились. Обновите остаток перед новым платным запуском.",
    generation_budget_limits_invalid: "Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.",
    generation_budget_reason_invalid: "Укажите проверяемую причину изменения денежного лимита.",
    generation_budget_timezone_invalid: "Не удалось определить часовой пояс денежного лимита.",
    paid_generation_campaign_required: "Выберите активную кампанию для платного запуска.",
    paid_generation_campaign_not_active: "Выбранная кампания не активна.",
    paid_generation_product_category_invalid: "Выберите категорию товара для правил QA и обязательных предупреждений.",
    paid_generation_product_category_binding_invalid: "Сервер не смог связать категорию с точным товаром платного запуска.",
    ai_learning_category_invalid: "Выберите точную товарную категорию ИИ‑центра.",
    ai_learning_control_room_payload_invalid: "Параметры ИИ‑центра устарели. Откройте категорию заново.",
    ai_knowledge_source_kind_invalid: "Добавьте HTTPS‑ссылку или поддерживаемый файл.",
    ai_knowledge_source_payload_invalid: "Форма источника устарела. Обновите ИИ‑центр и повторите добавление.",
    ai_knowledge_source_copy_invalid: "Проверьте название и пояснение к источнику.",
    ai_knowledge_source_rights_required: "Подтвердите право команды использовать источник для обучения.",
    ai_knowledge_source_link_invalid: "Проверьте ссылку и её контрольные данные.",
    ai_knowledge_source_url_invalid: "Добавьте публичную HTTPS‑ссылку без логина и пароля.",
    ai_knowledge_source_file_invalid: "Файл знаний не прошёл проверку типа, размера или контрольной суммы.",
    ai_knowledge_storage_access_denied: "Сервер отклонил путь файла вне защищённой папки этой команды.",
    ai_knowledge_storage_object_not_found: "Загруженный файл не найден в защищённой папке команды.",
    ai_knowledge_storage_metadata_invalid: "Хранилище вернуло неполные контрольные данные файла.",
    ai_knowledge_storage_metadata_mismatch: "Размер или тип файла изменился при загрузке; источник не зарегистрирован.",
    ai_knowledge_source_quota_exceeded: "Для этой категории уже зарегистрировано слишком много источников.",
    ai_knowledge_storage_quota_exceeded: "Лимит закрытой базы знаний исчерпан.",
    ai_teaching_card_not_found: "Карточка обучения изменилась. Обновите ИИ‑центр.",
    ai_teaching_card_stale: "Версия карточки изменилась. Решение не применено — обновите ИИ‑центр.",
    ai_teaching_scope_version_conflict: "Эта категория уже получила новую обратную связь. Данные обновлены; повторите решение осознанно.",
    ai_teaching_decision_payload_invalid: "Форма решения устарела. Обновите ИИ‑центр.",
    ai_teaching_decision_identity_invalid: "Не удалось подтвердить точную версию карточки и категории.",
    ai_teaching_decision_invalid: "Проверьте решение по карточке обучения.",
    paid_generation_campaign_policy_missing: "Для кампании ещё не настроен денежный лимит.",
    paid_generation_campaign_paused: "Платные запуски в этой кампании приостановлены.",
    generation_campaign_per_request_budget_exceeded: "Цена ролика превышает разовый лимит кампании.",
    generation_campaign_daily_budget_exceeded: "Дневной бюджет кампании исчерпан.",
    generation_campaign_monthly_budget_exceeded: "Месячный бюджет кампании исчерпан.",
    generation_campaign_budget_policy_changed: "Лимит кампании изменился. Обновите сводку и повторите запуск.",
    generation_campaign_name_invalid: "Укажите понятное название кампании длиной от 2 до 160 символов.",
    generation_campaign_payload_invalid: "Форма новой кампании устарела. Обновите страницу и повторите.",
    generation_campaign_policy_payload_invalid: "Форма бюджета кампании устарела. Обновите страницу и повторите.",
    generation_campaign_policy_values_invalid: "Лимиты кампании должны быть положительными, согласованными между собой и не выше лимитов команды.",
    generation_campaign_not_found: "Кампания больше недоступна. Обновите денежную сводку.",
    generation_campaign_quota_exceeded: "В команде уже создано слишком много кампаний. Завершите или архивируйте старые.",
    generation_spend_platform_control_missing: "Общий защитный рубильник платной генерации не настроен.",
    generation_spend_platform_disabled: "Платная генерация остановлена общим защитным рубильником. Dry-run задач без файлов доступен.",
    generation_spend_policy_missing: "Для команды ещё не настроен безопасный денежный лимит.",
    generation_spend_organization_disabled: "Платная генерация приостановлена руководителем. Dry-run задач без файлов доступен.",
    generation_spend_daily_limit_exceeded: "Дневной бюджет платной генерации исчерпан.",
    generation_spend_monthly_limit_exceeded: "Месячный бюджет платной генерации исчерпан.",
    generation_spend_per_request_limit_exceeded: "Цена запуска превышает утверждённый разовый лимит.",
    generation_spend_reservation_missing: "Сервер не подтвердил денежный резерв. Запрос провайдеру не отправлен.",
    generation_spend_reservation_not_active: "Денежный резерв запуска уже закрыт. Обновите очередь.",
    generation_spend_reservation_frozen: "Денежный резерв заморожен до ручной сверки запуска.",
    generation_spend_policy_version_conflict: "Лимиты уже изменились в другой вкладке. Обновите остаток.",
    generation_spend_policy_values_invalid: "Проверьте денежные лимиты, часовой пояс и причину изменения.",
    generation_spend_active_reservations_exist: "Часовой пояс нельзя изменить, пока есть активные денежные резервы.",
    seedance_approved_product_media_required: "Для восьмисекундного ролика выберите подтверждённое точное фото этого товара.",
    generation_job_id_invalid: "Не удалось определить платную задачу. Обновите раздел.",
    generation_reconciliation_incident_invalid: "Не удалось определить инцидент платного запуска. Обновите раздел.",
    generation_reconciliation_resolution_invalid: "Выберите результат ручной сверки платного запуска.",
    generation_reconciliation_evidence_invalid: "Добавьте проверяемое основание и подробную причину ручной сверки.",
    generation_reconciliation_task_id_invalid: "Укажите точный Runway task ID из панели видеосервиса.",
    generation_reconciliation_forbidden: "Ручную сверку платного запуска может выполнить только владелец или администратор команды.",
    generation_reconciliation_task_not_found: "Runway task с таким ID не найден. Проверьте номер в панели видеосервиса.",
    generation_reconciliation_task_mismatch: "Runway task не совпадает со временем этого запуска. Не прикрепляйте чужую задачу.",
    generation_reconciliation_wait_required: "Для подтверждения отсутствия Runway task подождите две минуты после фиксации инцидента.",
    generation_reconciliation_rejected: "Состояние запуска изменилось. Обновите очередь перед ручной сверкой.",
    real_generation_reconciliation_required: "Новый платный запуск временно закрыт: сначала владелец или администратор должен завершить ручную сверку предыдущего запроса к Runway.",
    generation_learning_context_required: "Восстановите безопасное авто-ТЗ и дождитесь бесплатной проверки обучения.",
    generation_learning_policy_category_invalid: "Выберите категорию товара для отдельного контура обучения.",
    generation_learning_category_mismatch: "Категория товара изменилась. Дождитесь нового обучения с нуля и восстановите авто-ТЗ.",
    generation_learning_category_binding_invalid: "Сервер не смог сохранить категорию вместе с обучающим сигналом. Платный запуск не создан.",
    generation_learning_opt_out_invalid: "Не удалось подтвердить осознанное отключение обученного ракурса.",
    generation_learning_unavailable: "Обученное ТЗ временно не проверено. Платный запуск не создан.",
    generation_learning_policy_required: "Для товара уже есть подтверждённое обучение. Обновите авто-ТЗ перед запуском.",
    generation_learning_policy_stale: "Обученное ТЗ обновилось. Восстановите авто-ТЗ и повторите запуск.",
    generation_learning_prompt_binding_invalid: "Обученные инструкции не попали в фактическое ТЗ. Восстановите безопасное авто-ТЗ перед запуском.",
    generation_mode_prompt_binding_invalid: "ТЗ не соответствует техническому контракту выбранной модели. Восстановите безопасное авто-ТЗ: точный товар, формат, длительность, реплика и запрет надписей будут проверены заново.",
    generation_spec_context_required: "Подготовьте и явно утвердите актуальную серверную версию ТЗ.",
    generation_spec_context_invalid: "Ссылка на серверную версию ТЗ повреждена. Обновите карточку и подготовьте версию заново.",
    generation_spec_effective_payload_invalid: "Сервер не смог проверить точную версию ТЗ. Обновите карточку перед запуском.",
    generation_spec_effective_policy_invalid: "Сервер вернул неполную проверку ТЗ. Платный запуск остановлен.",
    generation_spec_effective_policy_unavailable: "Проверка актуальности ТЗ временно недоступна. Runway и списание не запускались.",
    generation_spec_exact_scope_invalid: "Товар, ракурсы, модель, длительность, формат или аудио не совпадают с версией ТЗ.",
    generation_spec_approval_required: "Текущая версия ТЗ ещё не утверждена. Проверьте prompt и утвердите её явно.",
    generation_spec_approval_state_invalid: "Статус версии ТЗ изменился. Обновите историю и примите решение заново.",
    generation_spec_stale: "Источники или обученная политика изменились. Бесплатно пересчитайте ТЗ и утвердите новую версию.",
    generation_spec_head_invalid: "Появилась более новая версия ТЗ. Обновите историю перед решением.",
    generation_spec_media_stale: "Один из исходников ТЗ изменился или недоступен. Проверьте точные ракурсы.",
    generation_spec_request_mismatch: "Поля запуска отличаются от утверждённой версии ТЗ. Сохраните их новой версией.",
    generation_spec_learning_binding_invalid: "Обученная политика не совпадает с утверждённым ТЗ. Пересчитайте версию бесплатно.",
    generation_spec_repair_binding_invalid: "QA-исправление не совпадает с утверждённым ТЗ. Подготовьте новую версию.",
    generation_spec_outcome_binding_invalid: "Выбор результата обучения изменился. Обновите advisory и подготовьте новую версию ТЗ.",
    generation_spec_provider_start_stale: "ТЗ устарело непосредственно перед запуском. Runway и списание остановлены.",
    generation_spec_policy_blocked: "Серверная политика качества остановила эту версию. Проверьте рекомендуемый следующий шаг.",
    generation_spec_prompt_binding_invalid: "Фактический prompt отличается от утверждённой серверной версии. Платный запуск остановлен.",
    generation_spec_policy_binding_invalid: "Контекст обучения или QA отличается от утверждённой версии ТЗ.",
    generation_spec_scope_binding_invalid: "Параметры платного режима отличаются от утверждённой версии ТЗ.",
    generation_spec_state_conflict: "Сервер остановил запуск из-за конфликта истории ТЗ. Обновите карточку; Runway не вызван.",
    generation_learning_rejection_guard_blocked: "Эта модель временно остановлена серверным контуром качества. Портал подберёт безопасную альтернативу без запуска Runway.",
    generation_quality_guard_control_review_pending: "Контрольный результат уже создан и ждёт независимого QA. Новый платный контроль не нужен.",
    generation_research_claim_evidence_invalid: "Одобренное исследование не содержит проверяемую immutable-базу safe/forbidden claims. Платный запуск не создан: обновите AI-исследование и одобрите его без ручной подмены.",
    auth_session_required: "Сессия истекла. Войдите снова перед платным запуском.",
    authentication_required: "Сессия истекла. Войдите снова перед платным запуском.",
    invalid_payload: "Проверьте поля платного запуска и выбранный исходник.",
    origin_not_allowed: "Платная генерация недоступна с этого адреса портала.",
    generation_rejected: "Сервер отклонил платный запуск. Проверьте доступ, исходник и подтверждение расходов.",
    generation_unavailable: "Сервис платной генерации временно недоступен. Повторите попытку позже.",
    product_research_input_invalid: "Проверьте название товара и артикул.",
    product_research_paid_confirmation_required: "Подтвердите платный ИИ-анализ перед запуском.",
    paid_analysis_ack_required: "Подтвердите платный ИИ-анализ перед запуском.",
    research_execution_authorization_required: "Сервер не получил подтверждение платного анализа. Начните новый запуск и подтвердите расход ещё раз.",
    research_provider_attempt_not_authorized: "Платный вызов не авторизован сервером. Новый внешний запрос не выполнен.",
    research_provider_attempt_conflict: "Провайдер уже привязан к этому запуску с другими параметрами. Обновите статус.",
    research_provider_not_active: "Выбранный исследовательский провайдер не активен. Новый внешний запрос не выполнен.",
    research_market_decision_confirmation_required: "Подтвердите решение по рыночной категории.",
    research_market_decision_action_invalid: "Выберите допустимое действие с рыночной категорией.",
    research_market_decision_action_payload_invalid: "Проверьте поля выбранного действия с рыночной категорией.",
    research_market_category_candidate_stale: "Предложение категории изменилось. Обновите исследование и подтвердите его заново.",
    research_market_category_not_found: "Выбранная рыночная категория больше недоступна. Обновите список.",
    research_market_category_reclassify_required: "У товара уже есть категория. Используйте явную переклассификацию.",
    research_market_category_binding_required: "Сначала подтвердите исходную рыночную категорию товара.",
    research_market_category_unchanged: "Выберите категорию, отличную от текущей.",
    research_market_category_alias_conflict: "Такое название уже принадлежит другой рыночной категории.",
    research_market_aliases_invalid: "Добавьте не более 10 корректных названий-синонимов.",
    research_market_registry_query_invalid: "Введите точное название или сохранённый синоним категории.",
    research_outcome_refresh_payload_invalid: "Не удалось определить точный контур результатов. Обновите исследование.",
    research_outcome_scope_invalid: "Выберите точную рыночную категорию, площадку и модель.",
    research_outcome_status_payload_invalid: "Статус обучающей памяти запрошен с некорректным контуром.",
    research_outcome_decision_payload_invalid: "Проверьте поля решения по обучающей памяти.",
    research_outcome_decision_action_invalid: "Выберите допустимое решение по обучающей памяти.",
    research_outcome_decision_confirmation_required: "Подтвердите решение по обучающей памяти.",
    research_outcome_decision_version_invalid: "Версия обучающей памяти изменилась. Обновите статус.",
    research_outcome_candidate_not_found: "Кандидат обучения больше недоступен. Обновите статус.",
    research_outcome_refresh_required: "Появились новые зрелые результаты. Сначала явно обновите evidence и проверьте нового кандидата.",
    research_outcome_candidate_stale: "Доказательства кандидата изменились. Обновите и проверьте их заново.",
    research_outcome_candidate_superseded: "Появился более новый кандидат. Проверьте его перед активацией.",
    research_outcome_scope_version_stale: "Активная версия памяти уже изменилась. Обновите статус.",
    research_outcome_candidate_already_decided: "По этому кандидату уже принято решение. Обновите историю.",
    research_outcome_active_memory_mismatch: "Выбранный кандидат сейчас не активен. Обновите статус.",
    research_outcome_rollback_target_invalid: "Точная версия для отката больше недоступна.",
    research_outcome_rollback_target_unexpected: "Версия отката допустима только для действия «откатить».",
    research_youtube_request_payload_invalid: "Параметры YouTube‑проверки устарели. Обновите исследование.",
    research_youtube_query_invalid: "Укажите точный YouTube‑запрос длиной 2–200 символов.",
    research_youtube_locale_invalid: "Проверьте код региона и язык YouTube‑запроса.",
    research_youtube_published_after_invalid: "Дата начала поиска должна быть в пределах последних 366 дней.",
    research_youtube_quota_plan_invalid: "Canary допускает ровно 1 результат и 2 запроса; обновление — 1–25 результатов и 2 запроса.",
    research_youtube_confirmation_required: "Подтвердите квоту, отсутствие автоматического повтора и условия YouTube API.",
    research_youtube_terms_version_invalid: "Версия подтверждённых условий YouTube API устарела. Обновите раздел.",
    research_youtube_market_category_required: "Сначала подтвердите актуальную рыночную категорию товара.",
    research_youtube_provider_contract_invalid: "Контракт провайдера YouTube ещё не разрешён оператором.",
    research_youtube_retention_control_required: "Сервер не подтвердил свежую очистку YouTube API‑данных.",
    research_youtube_global_rollout_gate_required: "Глобальный контур YouTube пока закрыт оператором.",
    research_youtube_rollout_gate_required: "Сначала завершите canary и явно включите обновление категории.",
    research_youtube_fresh_canary_required: "Для включения нужен свежий успешный canary через search.list и videos.list.",
    research_youtube_rollout_decision_invalid: "Выберите включение или паузу обновлений YouTube.",
    research_youtube_rollout_payload_invalid: "Кратко объясните решение по YouTube rollout.",
    research_youtube_rollout_canary_unexpected: "Для паузы не нужно указывать canary. Обновите раздел.",
    research_youtube_ingestion_not_found: "YouTube‑запуск больше недоступен. Обновите исследование.",
    research_youtube_ingestion_lease_inactive: "Безопасная аренда YouTube‑запуска истекла; автоматического повтора не будет.",
    research_youtube_invoke_not_authorized: "Сервер не подтвердил право этого пользователя на сохранённый YouTube‑запуск.",
    research_youtube_local_daily_quota_exhausted: "Дневной лимит YouTube‑запросов по тихоокеанскому времени исчерпан.",
    research_youtube_transport_gate_closed: "Условия запуска изменились до внешнего вызова. Запрос остановлен.",
    research_youtube_candidate_payload_invalid: "Подтвердите временное решение по наблюдению и укажите причину.",
    research_youtube_candidate_stale: "Наблюдение YouTube изменилось или удалено по сроку хранения. Обновите статус.",
    research_youtube_overview_payload_invalid: "Не удалось определить исследование для YouTube‑сводки.",
    research_youtube_overview_limit_invalid: "Лимит истории YouTube‑запусков должен быть от 1 до 20.",
    research_youtube_status_payload_invalid: "Не удалось определить точный YouTube‑запуск.",
    canonical_name_invalid: "Укажите корректное каноническое название рыночной категории.",
    candidate_hash_invalid: "Предложение категории устарело. Обновите исследование.",
    product_research_platform_required: "Выберите хотя бы одну площадку для будущего контента.",
    product_research_run_missing: "Сервер не вернул номер исследования. Обновите раздел и повторите.",
    product_research_run_invalid: "Не удалось определить исследование. Начните новый разбор.",
    product_research_request_failed: "Не удалось запустить анализ товара. Повторите попытку позже.",
    product_research_response_invalid: "Сервис анализа товара вернул некорректный ответ.",
    research_category_learning_status_payload_invalid: "Не удалось определить исследование для готовности доказательной базы.",
    research_market_category_required: "Сначала подтвердите устойчивую рыночную категорию товара.",
    research_market_category_inactive: "Рыночная категория больше не активна. Обновите привязку перед сбором доказательств.",
    research_category_readiness_capture_payload_invalid: "Снимок готовности заполнен не полностью. Обновите статус.",
    research_category_evidence_changed: "Доказательная база изменилась. Проверьте новый процент перед фиксацией.",
    research_source_correction_payload_invalid: "Проверьте точный head, JSON-разбор и причину исправления.",
    research_source_analysis_head_stale: "Разбор источника уже изменился. Обновите ledger и проверьте новую версию.",
    research_source_analysis_invalid: "Разбор должен соответствовать schema v1 и не содержать raw captions, transcript или полный чужой текст.",
    research_source_ledger_not_found: "Источник больше не доступен в выбранной категории. Обновите ledger.",
    research_youtube_analysis_correction_payload_invalid: "Проверьте точный head, JSON-гипотезу и причину исправления YouTube-наблюдения.",
    research_youtube_observation_analysis_invalid: "Гипотеза должна соответствовать retention-bound schema v1 и не может содержать raw captions, transcript или provider payload.",
    research_youtube_derived_analysis_approval_required: "Разбор YouTube остановлен до принятого analytics amendment и точного approval reference.",
    research_youtube_observation_analysis_head_stale: "Гипотеза YouTube уже изменилась. Обновите статус и проверьте новую версию.",
    research_youtube_observation_not_found: "YouTube-наблюдение изменилось или удалено по сроку хранения. Обновите статус.",
    research_collection_policy_payload_invalid: "Политика автосбора заполнена не полностью. Обновите статус.",
    research_collection_policy_invalid: "Проверьте provider, период, hard budget и четыре явных подтверждения.",
    research_collection_expected_policy_invalid: "Точная версия политики не определена. Обновите статус.",
    research_collection_policy_head_stale: "Политика уже изменилась. Обновите статус перед новым решением.",
    research_instagram_provider_legal_choice_required: "Автосбор Instagram остаётся paused до выбора provider и подтверждённой legal-политики.",
    research_youtube_automatic_policy_ack_required: "Для YouTube подтвердите terms, quota, no-retry, hard budget и legal review.",
    legal_review_reference_invalid: "Укажите корректный номер или ссылку на legal review длиной 3–160 символов.",
    research_stage_branch_not_found: "Ветка исправлений больше недоступна. Обновите снимок этапов.",
    research_stage_branch_revision_stale: "Ветка изменилась после загрузки. Обновите точный снимок всей ветки перед решением.",
    research_stage_head_missing: "Точная версия этапа не найдена. Обновите снимок перед решением.",
    research_stage_head_stale: "Этап уже изменился в другой вкладке. Обновите снимок и повторно проверьте решение.",
    research_stage_run_locked: "Main-версия уже утверждена. Ветки доступны только для сравнения; для новой управляемой версии начните отдельное исследование.",
    research_stage_recompute_main_branch_required: "Пересчёт разрешён только для main-ветки. Сравните текущую ветку отдельно.",
    research_stage_recompute_pending: "Сохранённый пересчёт ещё не завершён. Проверьте его статус без нового запуска.",
    research_stage_recompute_active: "В ветке уже есть сохранённый пересчёт. Проверьте или явно отмените его без нового запуска.",
    research_stage_recompute_not_active: "Сохранённый пересчёт уже завершён или изменился. Обновите его статус.",
    research_stage_recompute_lease_active: "Попытка провайдера ещё защищена активной серверной блокировкой. Отмена сейчас закрыта.",
    research_stage_recompute_cancel_invalid: "Условия безопасной отмены изменились. Обновите сохранённый статус без повторного запуска.",
    research_stage_recompute_cancel_not_allowed: "Этот пересчёт нельзя отменить в текущем состоянии. Обновите сохранённый статус.",
    research_stage_comparison_branch_read_only: "Ветка сравнения доступна только для чтения. Вернитесь в main для управляемых изменений.",
    research_stage_revert_target_invalid: "Выбранная версия не подходит для отката. Обновите ограниченную историю этапа.",
    research_stage_replacement_schema_invalid: "Структурная версия не соответствует схеме этапа. Исправьте JSON, не меняя типы обязательных полей.",
    research_stage_rejected: "Один из этапов отклонён. Исправьте или верните его до утверждения.",
    research_stage_dependencies_stale: "Зависимый этап устарел после правки. Начните с самого раннего проблемного этапа.",
    research_stage_snapshot_mismatch: "Семь этапов не привязаны к одному точному черновику. Восстановите снимок перед утверждением.",
    research_v2_human_draft_required: "ИИ-версию должен проверить человек и сохранить как точный review-снимок.",
    research_payload_too_large: "Слишком много вводных для одного разбора. Сократите текст или количество фотографий.",
    research_payload_invalid: "Проверьте название, артикул, ссылку и вводные товара.",
    marketplace_url_invalid: "Укажите полную публичную ссылку на карточку товара, начиная с https://.",
    source_media_ids_invalid: "Можно выбрать не более пяти фотографий товара.",
    platforms_invalid: "Выберите хотя бы одну площадку: Instagram, YouTube, VK, Wildberries или Ozon.",
    content_review_limit_invalid: "История проверки может содержать от 1 до 50 записей.",
    content_review_media_required: "Выберите точное изображение или MP4 из раздела «Материалы».",
    content_review_context_invalid: "Проверьте площадку, статус публикации, категорию товара и наличие людей.",
    content_review_text_too_large: "Сократите подпись и сценарий до 6000 символов каждый.",
    content_review_metrics_required: "Браузер не смог подготовить технические параметры файла.",
    content_review_frames_invalid: "Не удалось подготовить безопасную выборку кадров.",
    content_review_evidence_required: "Сначала сохраните контрольные кадры MP4 в защищённой папке.",
    content_review_evidence_invalid: "Сохранённый набор кадров недоступен или устарел. Подготовьте его заново.",
    content_review_evidence_prepare_invalid: "Сервер не подготовил защищённые места для кадров. Повторите запуск.",
    content_review_evidence_commit_invalid: "Сервер не подтвердил сохранение всех кадров. Повторите запуск.",
    content_review_evidence_frame_invalid: "Один из контрольных кадров повреждён или имеет неверные параметры.",
    content_review_video_evidence_required: "Для MP4 сначала сохраните контрольные кадры в защищённой папке.",
    content_review_video_evidence_not_ready: "Контрольные кадры MP4 ещё не подтверждены. Безопасно повторите подтверждение.",
    content_review_evidence_prepare_payload_invalid: "Не удалось подготовить безопасный запрос для кадров.",
    content_review_evidence_frame_count_invalid: "Для MP4 нужно подготовить четыре кадра и пятый JPEG-атлас.",
    content_review_evidence_audio_metrics_invalid: "Локальные аудиометрики неполны. Подготовьте evidence заново и обязательно прослушайте точный MP4.",
    content_review_evidence_temporal_metrics_invalid: "Локальный скан таймлайна неполон. Обновите страницу и подготовьте evidence заново без нового рендера.",
    content_review_evidence_media_not_accessible: "Видео недоступно вашей роли или уже изменилось. Обновите материалы.",
    content_review_evidence_media_type_invalid: "Для этого evidence выбран неподдерживаемый тип исходного файла.",
    content_review_evidence_active_limit: "Для этого видео уже сохраняется набор кадров. Подождите и повторите запуск.",
    content_review_evidence_daily_limit: "Дневной лимит подготовки кадров исчерпан. Обратитесь к руководителю.",
    content_review_evidence_commit_payload_invalid: "Сервер отклонил неполный запрос подтверждения кадров.",
    content_review_evidence_manifest_invalid: "Список сохранённых кадров имеет неверный формат.",
    content_review_evidence_not_accessible: "Сохранённый evidence недоступен этому аккаунту.",
    content_review_evidence_source_stale: "Исходное видео изменилось после подготовки кадров. Запустите проверку заново.",
    content_review_evidence_object_path_invalid: "Сервер вернул неверный защищённый путь кадра.",
    content_review_evidence_storage_object_invalid: "Один из кадров не найден в защищённой папке.",
    content_review_evidence_storage_metadata_invalid: "Защищённое хранилище не подтвердило тип или размер кадра.",
    content_review_evidence_storage_metadata_mismatch: "Параметры загруженного кадра не совпали с подтверждением.",
    content_review_evidence_total_size_exceeded: "Контрольные кадры слишком велики. Подготовьте их заново.",
    content_review_evidence_storage_object_count_mismatch: "Не все контрольные кадры были загружены.",
    content_review_evidence_manifest_conflict: "Evidence уже подтверждён с другим составом кадров.",
    content_review_evidence_metrics_mismatch: "Технические параметры видео изменились после подтверждения кадров. Используйте восстановленный черновик или начните новую проверку.",
    content_review_evidence_commit_conflict: "Подтверждение evidence изменилось в другой вкладке. Обновите раздел перед повтором.",
    content_review_evidence_not_preparing: "Evidence уже закрыт для изменений. Подготовьте новый набор.",
    content_review_evidence_expired: "Время подготовки кадров истекло. Запустите проверку заново.",
    content_review_run_evidence_bind_invalid: "Не удалось безопасно связать проверку с сохранёнными кадрами.",
    content_review_evidence_already_consumed: "Этот evidence уже использован другой проверкой.",
    content_review_evidence_bind_conflict: "Evidence уже связан с другой проверкой.",
    content_review_video_evidence_invalid: "Сохранённые кадры видео неполны или устарели. Запустите новую проверку.",
    content_review_run_missing: "Сервер не вернул номер проверки. Обновите раздел и повторите.",
    content_review_id_invalid: "Не удалось определить проверку. Обновите раздел.",
    content_review_request_failed: "Сервис проверки временно недоступен. Запуск сохранён — проверьте его статус позже.",
    content_review_response_invalid: "Сервис проверки контента вернул некорректный ответ.",
    content_review_decision_invalid: "Выберите итог проверки: одобрить, доработать или отклонить.",
    content_review_decision_reason_invalid: "Объясните решение текстом от 10 до 2000 символов.",
    content_review_decision_codes_invalid: "Список подтверждений проверки имеет неверный формат.",
    content_review_media_watch_required: "Перед решением полностью просмотрите защищённый файл со звуком и субтитрами.",
    content_review_external_ai_processing_required: "Для контрольных кадров с узнаваемыми людьми подтвердите законное основание и необходимое информирование о внешней AI-обработке.",
    external_ai_processing_basis_required: "Для контрольных кадров с узнаваемыми людьми подтвердите законное основание и необходимое информирование о передаче данных внешнему AI-провайдеру.",
    content_review_not_completed: "Решение можно сохранить только после завершения проверки.",
    content_review_already_decided: "По этой версии уже сохранено неизменяемое решение.",
    content_review_approval_blocked: "Одобрение недоступно, пока в результате есть критические блокеры.",
    content_review_media_unavailable: "Выбранный материал недоступен вашей команде.",
    content_review_start_payload_invalid: "Проверьте поля новой проверки и выбранный материал.",
    content_review_input_invalid: "Проверьте площадку, категорию, тексты и подтверждения.",
    content_review_media_not_accessible: "Выбранный материал недоступен вашей роли или уже удалён.",
    content_review_certification_required: "Сначала завершите обучение и итоговый экзамен оператора.",
    content_review_product_category_unverified: "Категория товара ещё не подтверждена руководителем. Попросите владельца или проверяющего классифицировать товар.",
    content_review_product_category_mismatch: "Выбранная категория не совпадает с сохранённой категорией этого товара.",
    content_review_already_active: "Для этого файла уже выполняется проверка. Откройте её в истории.",
    content_review_user_daily_limit: "Дневной лимит проверок для аккаунта исчерпан.",
    content_review_org_daily_limit: "Командный дневной лимит проверок исчерпан.",
    content_review_not_found: "Проверка не найдена или недоступна вашей роли.",
    content_review_not_decidable: "Решение можно сохранить только после завершения проверки.",
    content_review_decision_already_recorded: "По этой версии уже сохранено неизменяемое решение.",
    content_review_blockers_unresolved: "Одобрение недоступно, пока остаются критические блокеры.",
    content_review_risk_acknowledgement_required: "Отметьте риск, который был проверен человеком.",
    risk_acknowledgement_unknown: "Подтверждать можно только риски из текущего неизменяемого результата.",
    resolved_recommendation_code_unknown: "Отмечать исправленными можно только рекомендации из текущего результата.",
    content_review_media_stale: "Файл изменился после проверки. Запустите новую проверку этой версии.",
    high_risk_content_requires_independent_review: "Контент высокого риска должен проверить другой руководитель.",
    content_review_generation_not_succeeded: "Готовый ролик ещё не подтверждён видеосервисом. Обновите генерацию и не принимайте задачу вручную.",
    content_review_approval_evidence_required: "Задачу готового ролика можно завершить только через сохранённое решение в разделе «Проверка контента».",
    generated_video_review_task_invalid: "Задача готового ролика изменилась или уже обработана. Обновите задачи и проверку контента.",
    generated_video_job_invalid: "Готовый файл больше не совпадает с подтверждённым платным запуском. Обновите генерацию и обратитесь к руководителю.",
    generated_video_review_start_payload_invalid: "Запрос запуска AI-проверки ролика устарел. Обновите генерацию.",
    generated_video_review_source_invalid: "Точный MP4 или его evidence изменились. Обновите генерацию и подготовьте кадры заново.",
    generated_video_review_platform_invalid: "Площадка ролика не подходит для безопасного автоматического QA.",
    generated_video_review_category_required: "Сначала один раз подтвердите категорию товара в полной форме проверки; дальше портал будет подставлять её сам.",
    generated_video_review_evidence_required: "Сначала дождитесь сохранения пяти evidence-изображений точного MP4.",
    generated_video_transcription_guard_failed: "Проверка остановлена: без отдельного разрешения транскрипция ролика должна оставаться выключенной.",
    generated_video_autopilot_input_invalid: "Сервер не подтвердил происхождение ролика для ускоренного QA. Откройте полную форму проверки.",
    generated_video_autopilot_input_not_bound: "Проверка остановлена: сервер не смог неизменяемо запретить транскрипцию и связать evidence.",
    generated_video_platform_prohibited: "Платную рекламную публикацию на выбранной площадке выпускать нельзя. Выберите разрешённый канал и создайте новое задание.",
    generated_video_review_context_invalid: "Контекст проверки не совпадает с платным заданием: площадка, рекламный статус или AI-происхождение изменились.",
    generated_video_product_context_invalid: "Категория или товар изменились после проверки. Запустите новую проверку из актуальной карточки товара.",
    generated_video_placement_input_invalid: "У платного запуска не подтверждены площадка или точный аккаунт размещения. Исправьте вводные до одобрения.",
    generated_video_context_approval_payload_invalid: "Форма одобрения ролика устарела. Обновите проверку и заполните реквизиты заново.",
    generated_video_context_approval_boolean_invalid: "Одно из подтверждений ролика имеет неверный формат. Обновите страницу.",
    generated_video_context_approval_invalid: "Заполните рекламодателя, ERID, наличие людей и все обязательные подтверждения точного MP4.",
    generated_video_context_source_invalid: "AI-проверка ролика уже обработана или больше не совпадает с точным MP4 и evidence.",
    generated_video_context_platform_invalid: "Для этой площадки, категории или ролика не хватает раскрытия, предупреждения, субтитров либо регистрации канала.",
    generated_video_context_non_context_blockers: "У ролика остались замечания к изображению, звуку или смыслу. Используйте «На доработку» — контекст их не скрывает.",
    generated_video_context_review_not_bound: "Сервер не смог связать реквизиты с точным MP4 и evidence. Решение не сохранено.",
    generated_video_independent_review_required: "Готовый ролик должен принять другой руководитель или проверяющий, не участвовавший в платном запуске.",
    generated_image_review_task_invalid: "Задача товарного фото изменилась или уже обработана. Обновите генерацию и проверку контента.",
    generated_image_job_invalid: "PNG больше не совпадает с подтверждённым платным запуском. Обновите генерацию и обратитесь к руководителю.",
    generated_image_platform_invalid: "Площадка товарного фото не совпадает с разрешённым каналом платного запуска.",
    generated_image_product_invalid: "Товар сгенерированного фото больше недоступен. Обновите карточку товара перед новой проверкой.",
    generated_image_review_requester_invalid: "Проверку сгенерированного фото нужно начать заново из текущего аккаунта.",
    generated_image_independent_review_required: "Сгенерированное фото должен принять другой руководитель или проверяющий, не участвовавший в платном запуске.",
    generated_image_review_context_invalid: "Фото нельзя выпускать по автоматическому черновику. Запустите новую проверку PNG и подтвердите категорию товара, маркировку рекламы, ОРД, ERID, права и обещания.",
    generated_photo_context_approval_payload_invalid: "Форма одобрения фото устарела. Обновите проверку и заполните реквизиты заново.",
    generated_photo_context_approval_boolean_invalid: "Одно из подтверждений фото имеет неверный формат. Обновите страницу.",
    generated_photo_context_approval_invalid: "Заполните категорию, рекламодателя, ERID, наличие людей и все обязательные подтверждения.",
    generated_photo_context_source_invalid: "Автоматическая проверка фото уже обработана или больше не совпадает с платным PNG. Обновите раздел.",
    generated_photo_context_platform_invalid: "Для этой площадки или категории не хватает обязательного раскрытия, предупреждения либо регистрации канала.",
    generated_photo_context_non_context_blockers: "У фото остались замечания к самому содержанию. Используйте «На доработку» — контекст не может скрыть визуальный или смысловой блокер.",
    generated_photo_context_review_not_bound: "Сервер не смог неизменяемо связать рекламный контекст с точным PNG. Решение не сохранено.",
    generation_repair_review_lineage_invalid: "Связь исправления с исходной QA-проверкой изменилась. Новый анализ не запущен: обновите генерацию и проверку контента.",
    generation_repair_review_job_mismatch: "Исправленный файл больше не совпадает с защищённым заданием генерации. Новый анализ не запущен.",
    generation_repair_review_lineage_not_bound: "Сервер не смог связать исправление с точным исходным QA-решением. Новый анализ не запущен.",
    final_url_platform_mismatch: "Финальная ссылка ведёт не на ту площадку, которая указана в задаче размещения.",
    content_review_placement_task_conflict: "Публикационная задача для этого решения уже существует в другом состоянии. Обновите задачи.",
    content_review_placement_conflict: "Публикация для этого решения уже существует в другом состоянии. Обновите раздел публикаций.",
    parent_content_review_invalid: "Предыдущая проверка для сравнения недоступна.",
    parent_content_review_product_mismatch: "Сравнивать можно только версии того же товара.",
    research_source_required: "Добавьте публичную ссылку на товар или точное фото из «Материалов».",
    research_user_daily_limit: "Ваш дневной лимит анализов исчерпан. Новые платные запросы будут доступны после обновления лимита.",
    research_org_daily_limit: "Дневной лимит анализов команды исчерпан. Обратитесь к руководителю.",
    research_media_not_allowed: "Выбранное фото недоступно для анализа. Проверьте формат, права и статус материала.",
    research_run_not_found: "Исследование не найдено. Начните новый разбор.",
    research_run_not_allowed: "У вас нет доступа к этому исследованию.",
    research_run_not_completed: "Анализ ещё не завершён. Сначала обновите его статус.",
    research_watchlist_payload_invalid: "Параметры наблюдения устарели. Обновите раздел и повторите действие.",
    research_watchlist_action_invalid: "Выберите доступное действие: подключить, изменить, поставить на паузу или возобновить.",
    refresh_interval_days_invalid: "Интервал наблюдения должен быть от 3 до 90 дней.",
    approved_research_v2_draft_required: "Для наблюдения нужен утверждённый человеком результат с категорией, конкурентами, трендами и рекомендацией.",
    research_watchlist_use_resume: "Наблюдение уже существует и стоит на паузе. Используйте «Возобновить».",
    research_watchlist_not_found: "Наблюдение для этого товара ещё не подключено.",
    input_validation_failed: "Сервис не смог безопасно прочитать исходные данные. Проверьте товар и начните новый разбор.",
    processing_lease_expired: "Анализ завершён по безопасному таймауту и не будет запущен повторно автоматически. Новый запуск требует отдельного подтверждения.",
    provider_outcome_unknown: "Провайдер мог принять платный запрос, но результат не подтверждён. Автоматического повторного списания нет — перед новым запуском проверьте расходы.",
    source_ids_invalid: "У ТЗ нет подтверждённых источников. Обновите исследование.",
    brief_source_mismatch: "Один из источников больше не относится к этому исследованию. Обновите раздел.",
    task_blueprint_invalid: "Проверьте названия и содержание трёх будущих задач.",
    creative_brief_draft_invalid: "Сначала сохраните актуальный черновик ТЗ.",
    creative_brief_not_latest: "ТЗ уже изменилось в другой вкладке. Обновите раздел перед утверждением.",
    creative_brief_not_approvable: "Этот черновик уже обработан. Обновите раздел.",
    provider_unavailable: "Сервис видео временно недоступен. Повторите проверку позже — новый платный запуск не требуется.",
    invalid_batch_size: "За один раз можно создать от 1 до 50 тестовых вариантов.",
    count_invalid: "За один раз можно создать от 1 до 50 тестовых вариантов.",
    platform_invalid: "Выберите поддерживаемую площадку размещения.",
    format_invalid: "Выберите поддерживаемый формат видео.",
    brief_invalid: "Сократите описание ролика до 1200 символов.",
    exact_product_media_required: "Добавьте и выберите точное фото товара или упаковки из раздела «Материалы».",
    placement_destination_invalid: "Проверьте площадку и точный аккаунт или карточку размещения.",
    payout_minor_invalid: "Проверьте сумму вознаграждения.",
    certified_assignee_required: "Выберите активного участника, который уже сдал итоговый экзамен.",
    payout_role_not_allowed: "Вознаграждение может назначить только руководитель.",
    assignee_role_not_allowed: "Назначать задачу другому участнику может только руководитель.",
    invalid_final_url: "Проверьте публичную ссылку на опубликованный ролик.",
    placement_not_found: "Задача размещения не найдена. Обновите раздел.",
    placement_access_denied: "Эта задача размещения назначена другому участнику.",
    placement_not_publishable: "Публикацию нельзя подтвердить в текущем статусе.",
    placement_already_published: "Для этой публикации уже сохранена другая ссылка на пост.",
    placement_compliance_ack_required: "Подтвердите проверку рекламного статуса и реквизитов из инструкции задачи.",
    placement_compliance_audit_failed: "Не удалось сохранить подтверждение рекламной проверки. Обновите задачу и повторите.",
    published_placement_required: "Сначала подтвердите публикацию и сохраните ссылку на пост.",
    observed_at_in_future: "Время снятия метрик не может быть в будущем.",
    observed_at_before_publication: "Снимок метрик должен быть сделан после публикации.",
    cumulative_metric_regression: "Накопительные метрики не могут быть меньше предыдущего снимка.",
    metric_payload_invalid: "Проверьте значения ручного снимка метрик.",
    tracking_link_payload_invalid: "Не удалось подготовить ссылку учёта.",
    tracking_target_invalid: "Укажите прямую HTTPS-ссылку на товар или лендинг.",
    tracking_placement_not_found: "Публикационная задача для ссылки не найдена.",
    tracking_link_access_denied: "Эта публикация назначена другому участнику.",
    tracking_placement_not_configurable: "Для закрытой публикации нельзя создать новую ссылку.",
    tracking_link_target_immutable: "У этой публикации уже есть ссылка на другой адрес. Создайте новую публикационную задачу.",
    tracking_slug_generation_failed: "Не удалось выпустить безопасную короткую ссылку. Повторите ещё раз.",
    storage_access_denied: "Нет доступа к этой папке раздела «Материалы».",
    storage_object_not_found: "Загруженный файл не найден в защищённом хранилище. Повторите загрузку.",
    media_metadata_invalid: "Проверьте тип, размер и формат файла.",
    media_size_invalid: "Проверьте размер загружаемого файла.",
    media_object_conflict: "Файл с таким путём уже зарегистрирован с другими данными.",
    media_access_denied: "Один из выбранных исходников больше недоступен. Обновите раздел «Материалы».",
    storage_bucket_mismatch: "Защищённое хранилище вернуло неожиданный ответ.",
    invalid_workspace_section: "Этот раздел кабинета недоступен.",
    workspace_section_invalid: "Этот раздел кабинета недоступен.",
    workspace_browser_payload_invalid: "Фильтры рабочего пространства имеют неверный формат.",
    workspace_page_size_invalid: "Можно загрузить от 1 до 100 объектов за один запрос.",
    workspace_search_invalid: "Сократите запрос поиска до 120 символов.",
    workspace_entity_types_invalid: "Выберите материалы, задачи или оба типа объектов.",
    workspace_media_kinds_invalid: "Один из типов материалов больше не поддерживается.",
    workspace_task_statuses_invalid: "Один из статусов задач больше не поддерживается.",
    workspace_cursor_invalid: "Список объектов изменился. Обновите рабочий стол.",
    workspace_folder_create_payload_invalid: "Проверьте название и расположение новой папки.",
    workspace_folder_update_payload_invalid: "Выберите изменение папки и повторите действие.",
    workspace_folder_name_invalid: "Укажите понятное название папки длиной до 120 символов.",
    workspace_folder_color_invalid: "Выберите доступный цвет папки.",
    workspace_folder_name_conflict: "В этой папке уже есть папка с таким названием.",
    workspace_folder_parent_not_found: "Родительская папка больше не существует. Обновите рабочий стол.",
    workspace_folder_not_found: "Папка больше не существует или недоступна.",
    workspace_folder_archived: "Папка уже находится в архиве.",
    workspace_folder_version_invalid: "Папка изменилась. Обновите рабочий стол и повторите действие.",
    workspace_folder_version_conflict: "Папка была изменена в другой вкладке. Обновите рабочий стол.",
    workspace_folder_not_empty: "Перед архивацией переместите из папки все объекты и вложенные папки.",
    workspace_folder_cycle: "Папку нельзя переместить внутрь самой себя.",
    workspace_folder_depth_exceeded: "Достигнута максимальная глубина: восемь уровней папок.",
    workspace_active_folder_quota_exceeded: "В команде уже создано слишком много активных папок.",
    workspace_total_folder_quota_exceeded: "Лимит истории папок исчерпан. Обратитесь к администратору.",
    workspace_position_exhausted: "Не удалось определить порядок объектов. Обновите рабочий стол.",
    workspace_move_payload_invalid: "Не удалось прочитать команду перемещения.",
    workspace_items_invalid: "Выберите от 1 до 100 доступных материалов или задач.",
    workspace_items_duplicate: "Один объект выбран для перемещения несколько раз.",
    workspace_item_access_denied: "Один из выбранных объектов недоступен вашей роли.",
    payout_decision_forbidden: "Решение по выплате доступно только руководителю.",
    self_payout_decision_forbidden: "Собственное начисление должен проверить другой руководитель.",
    payout_rejection_reason_required: "Укажите понятную причину отказа — не меньше 10 символов.",
    external_payment_reference_required: "Укажите номер внешней оплаты.",
    payout_must_be_approved_first: "Сначала одобрите начисление, затем фиксируйте оплату.",
    payout_not_found: "Начисление не найдено. Обновите реестр.",
    payout_not_pending: "Начисление уже обработано. Обновите реестр.",
    payout_already_paid: "Выплата уже подтверждена с другим номером оплаты.",
    payout_already_rejected: "Начисление уже отклонено с другой причиной.",
    wb_alias_forbidden: "Изменять связи артикулов может только уполномоченный участник команды.",
    wb_article_invalid: "Проверьте текущий и подменный артикулы Wildberries.",
    wb_alias_already_assigned: "Этот подменный артикул уже связан с другим товаром.",
    wb_alias_product_immutable: "Существующую связь артикулов нельзя перенести на другой товар.",
    product_not_found: "Товар с таким артикулом не найден. Сначала добавьте товар и его точный исходник.",
    feedback_category_invalid: "Проверьте тип и раздел запроса.",
    task_not_found: "Задача не найдена. Обновите список.",
    task_access_denied: "Эта задача назначена другому участнику.",
    task_transition_not_allowed: "Для текущего статуса это действие недоступно. Обновите список задач.",
    final_exam_rationales_required: "Письменно разберите четыре ключевых кейса итогового экзамена.",
    final_exam_rationale_invalid: "Заполните обоснование по схеме «Риск / Проверка / Действие» своими словами.",
    final_exam_rationales_must_be_unique: "Для каждого ключевого кейса нужно отдельное обоснование.",
    final_exam_rationales_immutable: "Уже отправленные обоснования этой попытки нельзя изменить. Обновите экзамен.",
    idempotency_key_conflict: "Запрос изменился во время повтора. Обновите раздел и выполните действие ещё раз.",
  };

  const matched = Object.keys(known).find((code) => diagnostic.includes(code));
  if (matched) return known[matched];
  if (raw.toLowerCase().includes("function") && raw.toLowerCase().includes("not found")) {
    return "Рабочий сервис ещё не обновлён. Повторите попытку позже или сообщите руководителю.";
  }
  if (/network|fetch|timeout|connection/i.test(raw)) {
    return "Связь прервалась. Проверьте интернет и повторите действие.";
  }
  return "Не удалось выполнить действие. Обновите раздел и попробуйте ещё раз.";
}
