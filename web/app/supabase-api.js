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
});

export class CreatorApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "CreatorApiError";
    this.code = details.code || "creator_api_error";
    this.details = details.details || null;
    this.hint = details.hint || null;
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
    const response = await this.call(RPC.bootstrap, {
      client_version: "supabase-spa-v1",
      ...clientContext,
    });
    const source = response?.data && typeof response.data === "object" ? response.data : response;
    this.organizationId =
      source?.organization?.id ??
      source?.membership?.organization_id ??
      source?.organization_id ??
      null;
    const serverBucket = source?.storage?.bucket;
    if (serverBucket && serverBucket !== this.config.STORAGE_BUCKET) {
      throw new CreatorApiError("Supabase вернул неожиданный приватный bucket.", {
        code: "storage_bucket_mismatch",
      });
    }
    this.storageBucket = serverBucket || this.config.STORAGE_BUCKET;
    this.storagePrefix = source?.storage?.path_prefix || null;
    return response;
  }

  completeModule(moduleCode) {
    return this.mutate(RPC.completeModule, { module_code: moduleCode });
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

  createMockBatch(batch) {
    const count = Number(batch?.count);
    if (!Number.isInteger(count) || count < 1 || count > 50) {
      throw new CreatorApiError("В одном mock batch разрешено от 1 до 50 вариантов.", {
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
      throw new CreatorApiError("Добавьте точное фото товара или packshot из Медиатеки.", {
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

  confirmPlacement(taskId, finalUrl) {
    return this.mutate(RPC.confirmPlacement, {
      task_id: taskId,
      final_url: finalUrl,
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
        "Для аккаунта ещё не назначена команда. Обратитесь к администратору.",
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
    course_not_found: "Учебный модуль больше недоступен. Обновите каталог.",
    exam_catalog_unavailable: "Каталог экзамена временно недоступен. Обновите страницу позже.",
    exam_cooldown: "Новая попытка экзамена пока недоступна. Дождитесь времени, указанного на экране.",
    exam_attempt_limit_active: "Лимит попыток за 24 часа исчерпан. Дождитесь времени следующей попытки на экране.",
    membership_required: "Для аккаунта ещё не назначена команда. Обратитесь к администратору.",
    membership_suspended: "Доступ приостановлен. Обратитесь к owner/admin вашей команды.",
    membership_revoked: "Доступ отозван. Обратитесь к owner/admin вашей команды.",
    inactive_membership: "Доступ к команде приостановлен. Обратитесь к администратору.",
    active_membership_required: "Доступ к команде приостановлен. Обратитесь к администратору.",
    profile_not_active: "Аккаунт приостановлен. Обратитесь к администратору.",
    verified_email_required: "Для работы нужен аккаунт с подтверждённой почтой.",
    role_not_allowed: "У вашей роли нет права на это действие.",
    mock_only_required: "Платная генерация отключена. Разрешён только mock-режим.",
    real_generation_is_disabled: "Платная генерация отключена. Разрешён только mock-режим.",
    invalid_batch_size: "В одном mock batch разрешено от 1 до 50 вариантов.",
    count_invalid: "В одном mock batch разрешено от 1 до 50 вариантов.",
    platform_invalid: "Выберите поддерживаемую площадку размещения.",
    format_invalid: "Выберите поддерживаемый формат видео.",
    brief_invalid: "Сократите описание ролика до 1200 символов.",
    exact_product_media_required: "Добавьте и выберите точное фото товара или packshot из Медиатеки.",
    placement_destination_invalid: "Проверьте площадку и точный аккаунт или карточку размещения.",
    payout_minor_invalid: "Проверьте сумму вознаграждения.",
    certified_assignee_required: "Выберите активного участника, который уже сдал итоговый экзамен.",
    payout_role_not_allowed: "Вознаграждение может назначить только owner или admin.",
    assignee_role_not_allowed: "Назначать задачу другому участнику может только руководитель.",
    invalid_final_url: "Проверьте публичную ссылку на опубликованный ролик.",
    placement_not_found: "Задача размещения не найдена. Обновите раздел.",
    placement_access_denied: "Эта задача размещения назначена другому участнику.",
    placement_not_publishable: "Публикацию нельзя подтвердить в текущем статусе.",
    placement_already_published: "Для этой публикации уже сохранён другой final URL.",
    published_placement_required: "Сначала подтвердите публикацию и её final URL.",
    observed_at_in_future: "Время снятия метрик не может быть в будущем.",
    observed_at_before_publication: "Снимок метрик должен быть сделан после публикации.",
    cumulative_metric_regression: "Накопительные метрики не могут быть меньше предыдущего снимка.",
    metric_payload_invalid: "Проверьте значения ручного снимка метрик.",
    storage_access_denied: "Нет доступа к этой папке медиатеки.",
    storage_object_not_found: "Загруженный файл не найден в приватном bucket. Повторите загрузку.",
    media_metadata_invalid: "Проверьте тип, размер и формат файла.",
    media_size_invalid: "Проверьте размер загружаемого файла.",
    media_object_conflict: "Файл с таким путём уже зарегистрирован с другими данными.",
    media_access_denied: "Один из выбранных исходников больше недоступен. Обновите медиатеку.",
    storage_bucket_mismatch: "Supabase вернул неожиданный приватный bucket.",
    invalid_workspace_section: "Этот раздел кабинета недоступен.",
    workspace_section_invalid: "Этот раздел кабинета недоступен.",
    payout_decision_forbidden: "Решение по выплате доступно только владельцу или администратору.",
    self_payout_decision_forbidden: "Собственное начисление должен проверить другой владелец или администратор.",
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
    wb_alias_product_immutable: "Существующую alias-связь нельзя перенести на другой товар.",
    product_not_found: "Товар с таким SKU не найден. Сначала создайте для него mock batch.",
    feedback_category_invalid: "Проверьте тип и раздел запроса.",
    task_not_found: "Задача не найдена. Обновите список.",
    task_access_denied: "Эта задача назначена другому участнику.",
    task_transition_not_allowed: "Для текущего статуса это действие недоступно. Обновите список задач.",
    idempotency_key_conflict: "Запрос изменился во время повтора. Обновите раздел и выполните действие ещё раз.",
  };

  const matched = Object.keys(known).find((code) => diagnostic.includes(code));
  if (matched) return known[matched];
  if (raw.toLowerCase().includes("function") && raw.toLowerCase().includes("not found")) {
    return "Облачный API ещё не применён к проекту Supabase.";
  }
  return raw;
}
