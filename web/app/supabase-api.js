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
  projectFlow: "creator_project_flow",
  projectMedia: "creator_project_media",
  projectPlacement: "creator_project_placement",
  createProject: "creator_create_workspace_project",
  archiveProject: "creator_archive_workspace_project",
  requestWorkspaceAccess: "creator_request_workspace_access",
  generationMediaIdentity: "creator_generation_media_identity",
  generationLearningPolicy: "creator_generation_learning_policy",
  generationRepairPolicy: "creator_generation_repair_policy",
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
  startProductResearch: "creator_start_project_research",
  productResearchStatus: "creator_project_research_status",
  saveCreativeBriefDraft: "creator_save_project_creative_brief_draft",
  approveCreativeBrief: "creator_approve_project_creative_brief",
  contentReviewCatalog: "creator_content_review_catalog",
  prepareContentReviewEvidence: "creator_prepare_content_review_evidence",
  commitContentReviewEvidence: "creator_commit_content_review_evidence",
  startContentReview: "creator_start_content_review",
  startGeneratedVideoReview: "creator_start_generated_video_review",
  contentReviewStatus: "creator_content_review_status",
  decideContentReview: "creator_decide_content_review",
  restoreProjectPlacement: "creator_restore_project_placement",
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
]);
const PRODUCT_RESEARCH_PLATFORM_SET = new Set(PRODUCT_RESEARCH_PLATFORMS);

const REAL_GENERATION_FUNCTION = "creator-generate";
const PRODUCT_RESEARCH_FUNCTION = "creator-product-research";
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
    const organizationSection = ["team", "feedback"].includes(section);
    const projectId = organizationSection
      ? ""
      : requiredProjectId(options.project_id ?? options.projectId);
    if (!organizationSection) payload.project_id = projectId;
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

      return this.generationMediaIdentity(mediaIds, { projectId })
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

  generationMediaIdentity(mediaIds, {
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
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
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  generationLearningPolicy({
    mediaId,
    platform,
    model,
    productCategory,
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
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
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  generationRepairPolicy(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedReviewId = String(reviewId || "").trim();
    if (!isUuid(normalizedReviewId)) {
      throw new CreatorApiError("Не удалось определить проверку для исправления.", {
        code: "generation_repair_review_invalid",
      });
    }
    return this.call(RPC.generationRepairPolicy, this.withOrganization({
      review_id: normalizedReviewId,
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
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
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
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
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
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

  projectFlow({ projectId = "", project_id: projectIdSnake = "", includeProjects = true } = {}) {
    const normalizedProjectId = optionalProjectId(projectIdSnake || projectId);
    if (typeof includeProjects !== "boolean") {
      throw new CreatorApiError("Не удалось определить состав списка проектов.", {
        code: "project_flow_include_projects_invalid",
      });
    }
    return this.call(RPC.projectFlow, this.withOrganization({
      ...(normalizedProjectId ? { project_id: normalizedProjectId } : {}),
      ...(includeProjects === false ? { include_projects: false } : {}),
    }));
  }

  projectMedia(
    mediaId,
    {
      projectId = "",
      project_id: projectIdSnake = "",
      surface = "",
    } = {},
  ) {
    const normalizedMediaId = String(mediaId || "").trim().toLowerCase();
    const normalizedSurface = String(surface || "").trim().toLowerCase();
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Некорректная ссылка на материал.", {
        code: "project_media_id_invalid",
      });
    }
    if (!["generation", "review"].includes(normalizedSurface)) {
      throw new CreatorApiError("Некорректный раздел материала.", {
        code: "project_media_surface_invalid",
      });
    }
    return this.call(RPC.projectMedia, this.withOrganization({
      project_id: requiredProjectId(projectIdSnake || projectId),
      media_id: normalizedMediaId,
      surface: normalizedSurface,
    }));
  }

  projectPlacement(
    placementId,
    { projectId = "", project_id: projectIdSnake = "" } = {},
  ) {
    const normalizedPlacementId = String(placementId || "").trim().toLowerCase();
    if (!isUuid(normalizedPlacementId)) {
      throw new CreatorApiError("Некорректная ссылка на публикацию.", {
        code: "project_placement_id_invalid",
      });
    }
    return this.call(RPC.projectPlacement, this.withOrganization({
      project_id: requiredProjectId(projectIdSnake || projectId),
      placement_id: normalizedPlacementId,
    }));
  }

  createProject({ name, colorToken = "emerald", color_token: colorTokenSnake = "" } = {}) {
    const projectName = String(name || "").trim();
    const color = String(colorTokenSnake || colorToken || "emerald").trim().toLowerCase();
    if (!projectName || projectName.length > 120 || /[\u0000-\u001f\u007f]/u.test(projectName)) {
      throw new CreatorApiError("Укажите название проекта длиной до 120 символов.", {
        code: "workspace_project_name_invalid",
      });
    }
    if (!["emerald", "gold", "rose", "blue", "violet", "slate"].includes(color)) {
      throw new CreatorApiError("Выберите доступный цвет проекта.", {
        code: "workspace_project_color_invalid",
      });
    }
    return this.mutate(RPC.createProject, {
      name: projectName,
      color_token: color,
    });
  }

  archiveProject(projectId, expectedVersion) {
    const normalizedProjectId = requiredProjectId(projectId);
    const normalizedVersion = Number(expectedVersion);
    if (!Number.isInteger(normalizedVersion) || normalizedVersion < 1) {
      throw new CreatorApiError("Проект изменился. Обновите Finder и повторите действие.", {
        code: "workspace_project_version_invalid",
      });
    }
    return this.mutate(RPC.archiveProject, {
      project_id: normalizedProjectId,
      expected_version: normalizedVersion,
    });
  }

  requestWorkspaceAccess() {
    return this.mutate(RPC.requestWorkspaceAccess, {});
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
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
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

  async startProductResearch(input, {
    onRunCreated,
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const productName = String(input?.product_name || "").trim();
    const sku = String(input?.sku || "").trim();
    if (!productName || !sku || productName.length > 180 || sku.length > 120) {
      throw new CreatorApiError("Укажите название товара и проверьте артикул.", {
        code: "product_research_input_invalid",
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

    const normalizedProjectId = requiredProjectId(
      projectIdSnake || projectId || input?.project_id || input?.projectId,
    );
    const payload = { ...input, project_id: normalizedProjectId };
    delete payload.projectId;
    const created = await this.mutate(RPC.startProductResearch, payload);
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
        onRunCreated({
          id: runId,
          status: String(run?.status || "queued"),
          project_id: normalizedProjectId,
        });
      } catch {
        // Recovery storage is a UI convenience; it must not cancel a paid run.
      }
    }

    let accepted;
    try {
      accepted = await this.invokeProductResearch({
        action: "analyze",
        research_id: runId,
        project_id: normalizedProjectId,
      });
    } catch (error) {
      error.job = { id: runId, status: String(run?.status || "queued") };
      throw error;
    }
    return { ...source, run: { ...run, id: runId }, analysis_request: accepted };
  }

  productResearchStatus(runId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.call(RPC.productResearchStatus, this.withOrganization({
      run_id: this.requireResearchRunId(runId),
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  saveCreativeBriefDraft(runId, draft, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.mutate(RPC.saveCreativeBriefDraft, {
      run_id: this.requireResearchRunId(runId),
      project_id: requiredProjectId(projectIdSnake || projectId),
      title: draft?.title,
      brief: draft?.brief,
      source_ids: draft?.source_ids,
      task_blueprint: draft?.task_blueprint,
    });
  }

  approveCreativeBrief(draftId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedDraftId = String(draftId || "").trim();
    if (!normalizedDraftId || normalizedDraftId.length > 128) {
      throw new CreatorApiError("Сначала сохраните актуальный черновик ТЗ.", {
        code: "creative_brief_draft_invalid",
      });
    }
    return this.mutate(RPC.approveCreativeBrief, {
      draft_id: normalizedDraftId,
      project_id: requiredProjectId(projectIdSnake || projectId),
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

  contentReviewCatalog({ limit = 50, projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedLimit = Number(limit);
    if (!Number.isInteger(normalizedLimit) || normalizedLimit < 1 || normalizedLimit > 50) {
      throw new CreatorApiError("История проверки может содержать от 1 до 50 записей.", {
        code: "content_review_limit_invalid",
      });
    }
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.call(RPC.contentReviewCatalog, this.withOrganization({
      media_limit: normalizedLimit,
      run_limit: normalizedLimit,
      project_id: normalizedProjectId,
    }));
  }

  async prepareContentReviewEvidence({
    mediaId,
    frameCount,
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
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
      project_id: requiredProjectId(projectIdSnake || projectId),
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

  async commitContentReviewEvidence({
    evidenceId,
    frames,
    technicalMetrics,
    idempotencyKey = "",
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
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
      project_id: requiredProjectId(projectIdSnake || projectId),
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
    const normalizedProjectId = requiredProjectId(input?.project_id ?? input?.projectId);
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
      project_id: normalizedProjectId,
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
      project_id: normalizedProjectId,
    }).catch(() => {});
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: accepted,
    };
  }

  async startGeneratedVideoReview({ mediaId, evidenceId, projectId = "", project_id: projectIdSnake = "" } = {}, {
    onRunCreated,
  } = {}) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedEvidenceId = String(evidenceId || "").trim();
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    if (!isUuid(normalizedMediaId) || !isUuid(normalizedEvidenceId)) {
      throw new CreatorApiError("Сначала дождитесь сохранения точного MP4 и его контрольных кадров.", {
        code: "generated_video_review_evidence_required",
      });
    }
    const created = await this.mutate(RPC.startGeneratedVideoReview, {
      media_id: normalizedMediaId,
      evidence_id: normalizedEvidenceId,
      project_id: normalizedProjectId,
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
      project_id: normalizedProjectId,
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

  contentReviewStatus(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.call(RPC.contentReviewStatus, this.withOrganization({
      review_id: this.requireContentReviewId(reviewId),
      project_id: normalizedProjectId,
    }));
  }

  decideContentReview(reviewId, decision, comment, {
    resolvedRecommendationCodes = [],
    riskAcknowledgements = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
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
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
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
      project_id: normalizedProjectId,
    });
  }

  restoreProjectPlacement(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.mutate(RPC.restoreProjectPlacement, {
      review_id: this.requireContentReviewId(reviewId),
      project_id: requiredProjectId(projectIdSnake || projectId),
    });
  }

  approveGeneratedPhotoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
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
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
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
      project_id: normalizedProjectId,
    });
  }

  approveGeneratedVideoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
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
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
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
      project_id: normalizedProjectId,
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
    const projectId = requiredProjectId(batch?.project_id ?? batch?.projectId);
    const batchPayload = { ...(batch || {}) };
    delete batchPayload.projectId;
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
      ...batchPayload,
      project_id: projectId,
      mode: "mock",
      allow_real_spend: false,
      spend_confirmation: "MOCK_ONLY",
    });
  }

  startRealGeneration(batch) {
    const projectId = requiredProjectId(batch?.project_id ?? batch?.projectId);
    const batchPayload = { ...(batch || {}) };
    delete batchPayload.projectId;
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
      ...batchPayload,
      project_id: projectId,
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

  realGenerationStatus(jobId, {
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const normalizedJobId = String(jobId || "").trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(normalizedJobId)) {
      throw new CreatorApiError("Не удалось определить платную задачу. Обновите раздел.", {
        code: "generation_job_id_invalid",
      });
    }
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.invokeRealGeneration("status", {
      job_id: normalizedJobId,
      project_id: normalizedProjectId,
    });
  }

  reconcileRealGeneration(jobId, details = {}) {
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const normalizedJobId = String(jobId || "").trim();
    const incidentId = String(details.incident_id || "").trim();
    const resolution = String(details.resolution || "").trim();
    const evidenceReference = String(details.evidence_reference || "").trim();
    const reason = String(details.reason || "").trim();
    const providerTaskId = String(details.provider_task_id || "").trim();
    const projectId = requiredProjectId(details.project_id ?? details.projectId);
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
      project_id: projectId,
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
    const projectId = requiredProjectId(snapshot?.project_id ?? snapshot?.projectId);
    const snapshotPayload = { ...(snapshot || {}) };
    delete snapshotPayload.projectId;
    return this.mutate(RPC.recordMetric, {
      ...snapshotPayload,
      project_id: projectId,
      source: "manual",
    });
  }

  configureTrackingLink(placementId, targetUrl, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.mutate(RPC.configureTrackingLink, {
      placement_id: placementId,
      target_url: targetUrl,
      project_id: normalizedProjectId,
    });
  }

  setWbAlias(alias) {
    return this.mutate(RPC.setWbAlias, alias);
  }

  decidePayout(payoutId, decision, details = {}) {
    const projectId = requiredProjectId(details?.project_id ?? details?.projectId);
    const payload = { ...(details || {}) };
    delete payload.projectId;
    return this.mutate(RPC.decidePayout, {
      payout_id: payoutId,
      decision,
      ...payload,
      project_id: projectId,
    });
  }

  confirmPlacement(taskId, finalUrl, complianceAck) {
    const projectScope = arguments[3] && typeof arguments[3] === "object"
      ? arguments[3]
      : {};
    const normalizedProjectId = requiredProjectId(
      projectScope.project_id ?? projectScope.projectId,
    );
    return this.mutate(RPC.confirmPlacement, {
      task_id: taskId,
      final_url: finalUrl,
      compliance_ack: complianceAck === true,
      project_id: normalizedProjectId,
    });
  }

  transitionTask(taskId, status, result = {}, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.mutate(RPC.transitionTask, {
      task_id: taskId,
      status,
      result,
      project_id: normalizedProjectId,
    });
  }

  createFeedback(feedback) {
    return this.mutate(RPC.createFeedback, feedback);
  }

  registerMedia(media) {
    const kind = String(media?.kind || "").trim();
    const projectId = requiredProjectId(media?.project_id ?? media?.projectId);
    const mediaPayload = { ...(media || {}) };
    delete mediaPayload.projectId;
    const payload = {
      ...mediaPayload,
      kind,
      project_id: projectId,
    };
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

function normalizeStringArray(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  )];
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

function optionalProjectId(value) {
  const projectId = String(value || "").trim().toLowerCase();
  if (!projectId) return "";
  if (!isUuid(projectId)) {
    throw new CreatorApiError("Не удалось определить активный проект. Вернитесь на рабочий стол и откройте проект снова.", {
      code: "project_id_invalid",
    });
  }
  return projectId;
}

function requiredProjectId(value) {
  const projectId = optionalProjectId(value);
  if (!projectId) {
    throw new CreatorApiError("Сначала выберите проект. Исследование, ТЗ и задачи не могут быть общей очередью компании.", {
      code: "project_id_required",
    });
  }
  return projectId;
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
    product_research_platform_required: "Выберите хотя бы одну площадку для будущих роликов.",
    product_research_run_missing: "Сервер не вернул номер исследования. Обновите раздел и повторите.",
    product_research_run_invalid: "Не удалось определить исследование. Начните новый разбор.",
    product_research_request_failed: "Не удалось запустить анализ товара. Повторите попытку позже.",
    product_research_response_invalid: "Сервис анализа товара вернул некорректный ответ.",
    research_payload_too_large: "Слишком много вводных для одного разбора. Сократите текст или количество фотографий.",
    research_payload_invalid: "Проверьте название, артикул, ссылку и вводные товара.",
    marketplace_url_invalid: "Укажите полную публичную ссылку на карточку товара, начиная с https://.",
    source_media_ids_invalid: "Можно выбрать не более пяти фотографий товара.",
    platforms_invalid: "Выберите хотя бы одну площадку: Instagram, YouTube или VK.",
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
