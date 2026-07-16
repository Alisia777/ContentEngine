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
  submitExam: "creator_submit_exam",
  workspaceSection: "creator_workspace_section",
  workspaceBrowser: "creator_workspace_browser",
  createWorkspaceFolder: "creator_create_workspace_folder",
  updateWorkspaceFolder: "creator_update_workspace_folder",
  moveWorkspaceItems: "creator_move_workspace_items",
  createMockBatch: "creator_create_mock_batch",
  recordMetric: "creator_record_metric",
  setWbAlias: "creator_set_wb_alias",
  decidePayout: "creator_decide_payout",
  confirmPlacement: "creator_confirm_placement",
  transitionTask: "creator_transition_task",
  createFeedback: "creator_create_feedback",
  registerMedia: "creator_register_media",
  captureEvent: "creator_capture_event",
  inviteAttempts: "creator_invite_delivery_attempts",
  managerDashboard: "creator_manager_dashboard",
  myWork: "creator_my_work",
  notifications: "creator_notifications",
  markNotificationsRead: "creator_mark_notifications_read",
  trainingProgress: "creator_training_progress",
  saveTrainingProgress: "creator_save_training_progress",
  savedWorkViews: "creator_saved_work_views",
  startProductResearch: "creator_start_product_research",
  productResearchStatus: "creator_product_research_status",
  saveCreativeBriefDraft: "creator_save_creative_brief_draft",
  approveCreativeBrief: "creator_approve_creative_brief",
  contentReviewCatalog: "creator_content_review_catalog",
  startContentReview: "creator_start_content_review",
  contentReviewStatus: "creator_content_review_status",
  decideContentReview: "creator_decide_content_review",
});

const REAL_GENERATION_FUNCTION = "creator-generate";
const PRODUCT_RESEARCH_FUNCTION = "creator-product-research";
const CONTENT_REVIEW_FUNCTION = "creator-content-review";
const REAL_GENERATION_SKUS = Object.freeze({
  gen4_turbo: Object.freeze({
    duration_seconds: 5,
    audio: false,
    confirmation: "RUNWAY_GEN4_TURBO_5S_USD_0.25",
    estimated_usd: "0.25",
  }),
  seedance2_fast: Object.freeze({
    duration_seconds: 8,
    audio: true,
    format: "9:16",
    confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32",
    estimated_usd: "2.32",
  }),
});

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

  submitCourseCheck(moduleCode, answers) {
    return this.mutate(RPC.submitCourseCheck, {
      module_code: moduleCode,
      answers,
    });
  }

  submitExam(answers) {
    return this.mutate(RPC.submitExam, {
      module_code: "operator_final_exam",
      answers,
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
    return this.call(RPC.workspaceSection, this.withOrganization(payload));
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
    const supportedPlatforms = new Set(["instagram", "youtube", "vk"]);
    if (
      !Array.isArray(input?.platforms)
      || input.platforms.length < 1
      || input.platforms.some((platform) => !supportedPlatforms.has(String(platform)))
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

  productResearchStatus(runId) {
    return this.call(RPC.productResearchStatus, this.withOrganization({
      run_id: this.requireResearchRunId(runId),
    }));
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

  async startContentReview(input, { frames = [], onRunCreated } = {}) {
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
    const safeFrames = normalizeContentReviewFrames(
      frames,
      String(technicalMetrics.source_type || "").toLowerCase(),
    );

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

    let accepted;
    try {
      accepted = await this.invokeContentReview({
        action: "analyze",
        review_id: reviewId,
        frames: safeFrames,
      });
    } catch (error) {
      error.job = { id: reviewId, status: String(run?.status || "queued") };
      throw error;
    }
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: accepted,
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
    if (!Array.isArray(batch?.media_ids) || batch.media_ids.length !== 1) {
      throw new CreatorApiError("Для платного запуска выберите ровно одно точное фото товара.", {
        code: "real_generation_exactly_one_media_required",
      });
    }
    const model = String(batch?.model || "gen4_turbo");
    const sku = REAL_GENERATION_SKUS[model];
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
      throw new CreatorApiError(`Подтвердите создание одного платного видео примерно за $${sku.estimated_usd}.`, {
        code: "real_spend_confirmation_required",
      });
    }

    return this.invokeRealGeneration("start", {
      ...batch,
      count: 1,
      media_ids: [String(batch.media_ids[0])],
      mode: "real",
      provider: "runway",
      model,
      duration_seconds: sku.duration_seconds,
      audio: sku.audio,
      allow_real_spend: true,
      spend_confirmation: sku.confirmation,
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
    if (!new Set(["start", "status", "reconcile"]).has(action)) {
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
    const idempotencyKey = action !== "status"
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
    return this.mutate(RPC.registerMedia, media);
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

function normalizeContentReviewFrames(frames, sourceType = "") {
  const expectedCount = sourceType === "video"
    ? Array.isArray(frames) && frames.length >= 4 && frames.length <= 5
    : sourceType === "image"
      ? Array.isArray(frames) && frames.length === 1
      : Array.isArray(frames) && frames.length >= 1 && frames.length <= 5;
  if (!expectedCount) {
    throw new CreatorApiError("Проверке нужен один кадр изображения или от четырёх до пяти кадров видео.", {
      code: "content_review_frames_invalid",
    });
  }
  const normalized = frames.map((value) => String(value || ""));
  const framePattern = /^data:image\/jpeg;base64,[a-z0-9+/=]+$/iu;
  if (
    normalized.some((value) => value.length < 100 || value.length > 330_000 || !framePattern.test(value))
    || normalized.reduce((total, value) => total + value.length, 0) > 1_650_000
  ) {
    throw new CreatorApiError("Кадры имеют небезопасный формат или слишком большой размер.", {
      code: "content_review_frames_invalid",
    });
  }
  return normalized;
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
    refreshed_courses_required: "Пройдите обновлённые мини-тесты всех четырёх блоков и завершите каждый блок заново.",
    course_not_found: "Учебный модуль больше недоступен. Обновите каталог.",
    course_knowledge_check_required: "Сначала пройдите мини-тест этого блока на сервере.",
    course_check_answers_invalid: "Проверьте ответы мини-теста и отправьте их ещё раз.",
    course_check_catalog_unavailable: "Мини-тест временно недоступен. Обновите страницу.",
    unknown_course_check_question: "Мини-тест обновился. Обновите страницу и ответьте заново.",
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
    mock_only_required: "Платная генерация отключена. Доступны только тестовые варианты без списаний.",
    real_generation_is_disabled: "Платная генерация сейчас недоступна. Используйте тестовый режим без списаний.",
    real_generation_exactly_one_media_required: "Для платного запуска выберите ровно одно точное фото товара.",
    real_spend_confirmation_required: "Подтвердите создание одного платного видео по указанной цене.",
    real_generation_sku_invalid: "Параметры платного режима не совпадают с подтверждённой ценой.",
    real_generation_action_invalid: "Неизвестное действие платной генерации.",
    real_generation_response_invalid: "Сервис генерации вернул некорректный ответ.",
    real_generation_request_failed: "Не удалось вызвать сервис платной генерации. Повторите попытку позже.",
    real_generation_failed: "Платная генерация завершилась ошибкой. Проверьте статус задачи.",
    real_generation_user_daily_quota_exceeded: "Дневной лимит платных запусков исчерпан. Продолжите после обновления лимита.",
    real_generation_organization_daily_quota_exceeded: "Командный дневной лимит платных запусков исчерпан. Обратитесь к руководителю.",
    real_generation_assignee_concurrency_exceeded: "У выбранного исполнителя уже создаётся платный ролик. Дождитесь его завершения — повторная оплата не требуется.",
    real_generation_organization_concurrency_exceeded: "Командная очередь платных роликов заполнена. Дождитесь завершения текущих задач.",
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
    generated_video_platform_prohibited: "Платную рекламную публикацию на выбранной площадке выпускать нельзя. Выберите разрешённый канал и создайте новое задание.",
    generated_video_review_context_invalid: "Контекст проверки не совпадает с платным заданием: площадка, рекламный статус или AI-происхождение изменились.",
    generated_video_product_context_invalid: "Категория или товар изменились после проверки. Запустите новую проверку из актуальной карточки товара.",
    generated_video_placement_input_invalid: "У платного запуска не подтверждены площадка или точный аккаунт размещения. Исправьте вводные до одобрения.",
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
    product_not_found: "Товар с таким артикулом не найден. Сначала создайте для него тестовые варианты.",
    feedback_category_invalid: "Проверьте тип и раздел запроса.",
    task_not_found: "Задача не найдена. Обновите список.",
    task_access_denied: "Эта задача назначена другому участнику.",
    task_transition_not_allowed: "Для текущего статуса это действие недоступно. Обновите список задач.",
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
