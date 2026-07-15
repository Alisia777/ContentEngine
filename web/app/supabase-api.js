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
});

const REAL_GENERATION_FUNCTION = "creator-generate";
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

  workspaceSection(section) {
    return this.call(RPC.workspaceSection, this.withOrganization({ section }));
  }

  inviteAttempts() {
    return this.call(RPC.inviteAttempts, this.withOrganization({}));
  }

  managerDashboard() {
    return this.call(RPC.managerDashboard, this.withOrganization({}));
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

  async invokeRealGeneration(action, payload = {}) {
    if (!new Set(["start", "status"]).has(action)) {
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
    const idempotencyKey = action === "start"
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
    auth_session_required: "Сессия истекла. Войдите снова перед платным запуском.",
    authentication_required: "Сессия истекла. Войдите снова перед платным запуском.",
    invalid_payload: "Проверьте поля платного запуска и выбранный исходник.",
    origin_not_allowed: "Платная генерация недоступна с этого адреса портала.",
    generation_rejected: "Сервер отклонил платный запуск. Проверьте доступ, исходник и подтверждение расходов.",
    generation_unavailable: "Сервис платной генерации временно недоступен. Повторите попытку позже.",
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
