const AI_LEARNING_CONTROL_ROOM_VERSION = "ai-learning-control-room-v1";
const AI_MARKET_SCOPE_INDEX_VERSION = "ai-learning-market-scope-index-v1";
const AI_MARKET_READINESS_KIND = "category_evidence_readiness_not_model_iq";
const AI_MARKET_READINESS_VERSION = "category-evidence-readiness-v3";
const AI_MARKET_SCOPE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const AI_MARKET_SCOPE_HASH = /^[0-9a-f]{64}$/u;
const AI_MARKET_SCOPE_STATUSES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
  "cancelled",
]);
const AI_MARKET_PRODUCT_STATUSES = new Set(["active", "paused"]);
const AI_MARKET_GUIDANCE_STATUSES = new Set([
  "strong_evidence",
  "developing_evidence",
  "insufficient_evidence",
]);
const AI_MARKET_DIMENSION_KEYS = Object.freeze([
  "source_volume",
  "platform_diversity",
  "competitor_observations",
  "trend_recency",
  "analysis_coverage",
  "human_validation",
]);
const AI_LEARNING_VIEWS = new Set(["overview", "knowledge", "teach", "history"]);
const AI_LEARNING_STATUSES = new Set([
  "strong_evidence",
  "developing_evidence",
  "insufficient_evidence",
  "cold_start",
  "processing",
  "paused",
  "error",
  "unknown",
]);
const AI_TEACHING_DECISIONS = new Set(["approve", "reject"]);
const AI_TEACHING_STATUSES = new Set([
  "pending",
  "approved",
  "rejected",
  "superseded",
]);

export const AI_PRODUCT_CATEGORIES = Object.freeze([
  Object.freeze({ id: "cosmetics", value: "cosmetics", key: "cosmetics", slug: "cosmetics", label: "Косметика и уход" }),
  Object.freeze({ id: "baa", value: "baa", key: "baa", slug: "baa", label: "БАД" }),
  Object.freeze({ id: "sports_food", value: "sports_food", key: "sports_food", slug: "sports_food", label: "Спортивное питание" }),
  Object.freeze({ id: "food", value: "food", key: "food", slug: "food", label: "Еда и напитки" }),
  Object.freeze({ id: "household", value: "household", key: "household", slug: "household", label: "Товары для дома" }),
  Object.freeze({ id: "apparel", value: "apparel", key: "apparel", slug: "apparel", label: "Одежда и аксессуары" }),
  Object.freeze({ id: "electronics", value: "electronics", key: "electronics", slug: "electronics", label: "Электроника" }),
  Object.freeze({ id: "other", value: "other", key: "other", slug: "other", label: "Другая категория" }),
]);

const AI_CATEGORY_BY_KEY = new Map(
  AI_PRODUCT_CATEGORIES.map((category) => [category.key, category]),
);

const DIMENSION_LABELS = Object.freeze({
  source_volume: "Объём проверяемых источников",
  platform_diversity: "Разнообразие площадок",
  competitor_observations: "Наблюдения конкурентов",
  trend_recency: "Свежесть трендов",
  analysis_coverage: "Структурированный охват",
  human_validation: "Проверка человеком",
});

const STATUS_META = Object.freeze({
  strong_evidence: Object.freeze({
    label: "Сильная доказательная база",
    short: "Сильная база",
    tone: "strong",
  }),
  developing_evidence: Object.freeze({
    label: "Доказательная база развивается",
    short: "Развивается",
    tone: "developing",
  }),
  insufficient_evidence: Object.freeze({
    label: "Доказательств пока недостаточно",
    short: "Нужны данные",
    tone: "insufficient",
  }),
  cold_start: Object.freeze({
    label: "Холодный старт категории",
    short: "Холодный старт",
    tone: "insufficient",
  }),
  processing: Object.freeze({
    label: "Пересчитываем правила категории",
    short: "Пересчёт",
    tone: "processing",
  }),
  paused: Object.freeze({
    label: "Обновление категории приостановлено",
    short: "Пауза",
    tone: "paused",
  }),
  error: Object.freeze({
    label: "Статус категории требует проверки",
    short: "Нужна проверка",
    tone: "error",
  }),
  unknown: Object.freeze({
    label: "Данных для статуса пока нет",
    short: "Нет данных",
    tone: "unknown",
  }),
});

/**
 * Converts a category-like value to one of the eight server-supported slugs.
 * It is deliberately pure so app.js and Node contract tests can share it.
 */
export function aiLearningCategory(value, fallback = "other") {
  const candidate = cleanText(
    typeof value === "object" && value
      ? value.key || value.slug || value.category_key || value.categoryKey
        || value.selected_category || value.selectedCategory
      : value,
    80,
  ).toLowerCase();
  if (AI_CATEGORY_BY_KEY.has(candidate)) return candidate;
  const normalizedFallback = cleanText(fallback, 80).toLowerCase();
  return AI_CATEGORY_BY_KEY.has(normalizedFallback) ? normalizedFallback : "other";
}

/** Returns a supported control-room view, defaulting safely to overview. */
export function aiLearningView(value) {
  const candidate = cleanText(
    typeof value === "object" && value ? value.view || value.aiView : value,
    40,
  ).toLowerCase();
  return AI_LEARNING_VIEWS.has(candidate) ? candidate : "overview";
}

/**
 * Strictly normalizes the server-owned index of dynamic market-category
 * contexts.  A context is product-specific because automatic collection
 * policy is product-specific even when evidence/readiness is shared by a
 * market category.  Unknown category names are never mapped to `other`.
 */
export function normalizeAiLearningMarketScopeIndex(value) {
  const unavailable = (reason = "invalid_contract") => ({
    available: false,
    ok: false,
    version: AI_MARKET_SCOPE_INDEX_VERSION,
    organizationId: "",
    metricKind: AI_MARKET_READINESS_KIND,
    asOf: null,
    scopes: [],
    itemLimit: 50,
    reason,
  });
  let source = objectValue(value) || {};
  if (objectValue(source.data)) source = source.data;
  if (!exactObjectKeys(source, [
    "ok",
    "version",
    "organization_id",
    "metric_kind",
    "as_of",
    "scopes",
    "limits",
  ])) return unavailable();
  const organizationId = exactUuid(source.organization_id);
  const asOf = timestamp(source.as_of);
  const limits = objectValue(source.limits);
  if (
    source.ok !== true
    || source.version !== AI_MARKET_SCOPE_INDEX_VERSION
    || !organizationId
    || source.metric_kind !== AI_MARKET_READINESS_KIND
    || !asOf
    || !exactObjectKeys(limits, [
      "item_limit",
      "detail_rpc",
      "score_is_model_iq",
      "status_read_only",
      "external_call_started",
    ])
    || !Number.isSafeInteger(limits.item_limit)
    || limits.item_limit < 1
    || limits.item_limit > 50
    || limits.detail_rpc !== "creator_research_category_learning_status"
    || limits.score_is_model_iq !== false
    || limits.status_read_only !== true
    || limits.external_call_started !== false
  ) return unavailable();

  const rawScopes = arrayFrom(source.scopes);
  if (rawScopes.length > limits.item_limit) return unavailable();
  const scopes = [];
  const scopeIds = new Set();
  const productIds = new Set();
  for (const rawScope of rawScopes) {
    const scope = objectValue(rawScope);
    if (!exactObjectKeys(scope, [
      "scope_id",
      "product_id",
      "product_name",
      "product_status",
      "market_category_id",
      "canonical_name",
      "definition",
      "binding_id",
      "binding_version",
      "run_id",
      "run_status",
      "run_finished_at",
      "readiness",
      "guidance",
    ])) return unavailable();
    const scopeId = exactUuid(scope.scope_id);
    const productId = exactUuid(scope.product_id);
    const categoryId = exactUuid(scope.market_category_id);
    const bindingId = exactUuid(scope.binding_id);
    const runId = exactUuid(scope.run_id);
    const productName = cleanText(scope.product_name, 240);
    const canonicalName = cleanText(scope.canonical_name, 160);
    const definition = cleanText(scope.definition, 2_000);
    const bindingVersion = Number(scope.binding_version);
    const runFinishedAt = scope.run_finished_at === null
      ? null
      : timestamp(scope.run_finished_at);
    if (
      !scopeId
      || !productId
      || !categoryId
      || !bindingId
      || !runId
      || scopeId !== bindingId
      || scopeIds.has(scopeId)
      || productIds.has(productId)
      || productName.length < 2
      || canonicalName.length < 2
      || definition.length < 10
      || !AI_MARKET_PRODUCT_STATUSES.has(scope.product_status)
      || !AI_MARKET_SCOPE_STATUSES.has(scope.run_status)
      || !Number.isSafeInteger(bindingVersion)
      || bindingVersion < 1
      || (scope.run_finished_at !== null && !runFinishedAt)
      || (["completed", "failed", "cancelled"].includes(scope.run_status)
        ? !runFinishedAt
        : scope.run_finished_at !== null)
    ) return unavailable();

    const readiness = normalizeMarketReadiness(scope.readiness, asOf);
    const guidance = normalizeMarketGuidance(scope.guidance, readiness);
    if (!readiness || !guidance) return unavailable();
    scopeIds.add(scopeId);
    productIds.add(productId);
    scopes.push({
      scopeId,
      productId,
      productName,
      productStatus: scope.product_status,
      categoryId,
      canonicalName,
      definition,
      bindingId,
      bindingVersion,
      runId,
      runStatus: scope.run_status,
      runFinishedAt,
      score: readiness.score,
      evidenceHash: readiness.evidenceHash,
      readiness,
      guidance,
    });
  }
  return {
    available: true,
    ok: true,
    version: AI_MARKET_SCOPE_INDEX_VERSION,
    organizationId,
    metricKind: AI_MARKET_READINESS_KIND,
    asOf,
    scopes,
    itemLimit: limits.item_limit,
    reason: "",
  };
}

export function aiLearningMarketScopeIndexMarkup(value, options = {}) {
  const control = value?.available
    && Array.isArray(value.scopes)
    && value.version === AI_MARKET_SCOPE_INDEX_VERSION
    ? value
    : normalizeAiLearningMarketScopeIndex(value);
  const requestedScopeId = exactUuid(options.selectedScopeId);
  const selected = requestedScopeId
    ? control.scopes.find((scope) => scope.scopeId === requestedScopeId) || null
    : control.scopes[0] || null;
  const loading = options.loading === true;
  const error = cleanText(options.error, 800);
  const detailMarkup = selected ? String(options.detailMarkup || "") : "";
  const selectorMarkup = control.scopes.map((scope) => {
    const active = scope.scopeId === selected?.scopeId;
    const gapHint = scope.guidance.gaps.length
      ? scope.guidance.gaps.map((gap) =>
        `${gap.label}: ${gap.current}/${gap.target}; не хватает ${gap.missing}`
      ).join(" · ")
      : "Все шесть измерений достигли текущих целевых порогов.";
    return `<button class="ai-market-scope-card${active ? " is-active" : ""}" type="button" data-action="select-ai-market-learning-scope" data-scope-id="${escapeHtml(scope.scopeId)}" aria-pressed="${active ? "true" : "false"}" aria-label="${escapeHtml(`${scope.canonicalName}. ${scope.productName}. ${gapHint}`)}" title="${escapeHtml(gapHint)}" ${loading ? "disabled" : ""}>
      <span><strong>${escapeHtml(scope.canonicalName)}</strong><small>${escapeHtml(scope.productName)} · binding v${scope.bindingVersion}</small></span>
      <b>${scope.score}%</b>
    </button>`;
  }).join("");
  const content = !control.available
    ? `<div class="ai-market-learning-empty" role="status"><strong>Динамические категории временно недоступны</strong><p>Процент скрыт: сервер не подтвердил точный UUID scope или readiness v3. Legacy‑оценка не подставляется.</p></div>`
    : !selected && control.scopes.length
      ? `<div class="ai-market-learning-layout">
          <aside class="ai-market-scope-selector" aria-label="Категория и товар">${selectorMarkup}</aside>
          <div class="ai-market-learning-detail"><div class="ai-market-learning-empty" role="status"><strong>Выберите актуальный product context</strong><p>UUID из ссылки устарел или больше недоступен. Доступные категории показаны слева; ни одна из них не выбрана автоматически.</p></div></div>
        </div>`
      : !selected
      ? `<div class="ai-market-learning-empty"><strong>Подтверждённых рыночных категорий пока нет</strong><p>Запустите исследование товара: ИИ предложит границу новой категории, соберёт источники и попросит подтвердить привязку.</p><a class="btn btn-secondary btn-small" href="#/workspace/research">Начать исследование</a></div>`
      : `<div class="ai-market-learning-layout">
          <aside class="ai-market-scope-selector" aria-label="Категория и товар">${selectorMarkup}</aside>
          <div class="ai-market-learning-detail" data-learning-context="ai" data-learning-run-id="${escapeHtml(selected.runId)}" data-learning-scope-id="${escapeHtml(selected.scopeId)}">
            <div class="ai-market-context-note" role="note"><strong>${escapeHtml(selected.canonicalName)}</strong><span>Товар: ${escapeHtml(selected.productName)}. Readiness и source ledger общие для точной market category; политика автосбора меняется только в этом product context.</span></div>
            ${detailMarkup || `<div class="ai-market-learning-empty"><strong>${loading ? "Загружаем доказательства…" : "Деталь пока недоступна"}</strong><p>Индекс остаётся read-only; provider call и retry не запускались.</p></div>`}
          </div>
        </div>`;
  return `<section class="ai-market-learning" aria-labelledby="ai-market-learning-title" data-ce-patch-key="ai-market-learning">
    <div class="ai-market-learning-heading">
      <div><p class="ai-learning-eyebrow">Evidence-grounded market learning</p><h2 id="ai-market-learning-title">Новые категории, источники и управляемый анализ</h2><p>Здесь процент означает покрытие доказательств, а не IQ модели. Каждую интерпретацию можно проверить и исправить.</p></div>
      <span class="ai-learning-status-pill is-${selected?.guidance.status === "strong_evidence" ? "strong" : selected?.guidance.status === "developing_evidence" ? "developing" : "insufficient"}">${selected ? `${selected.score}% evidence` : "нет scope"}</span>
    </div>
    ${error ? `<div class="ai-learning-message is-error" role="alert">${escapeHtml(error)}</div>` : ""}
    ${content}
  </section>`;
}

function normalizeMarketReadiness(value, expectedAsOf) {
  const source = objectValue(value);
  if (!exactObjectKeys(source, [
    "metric_kind",
    "definition_version",
    "score",
    "dimensions",
    "weights_total",
    "evidence_hash",
    "as_of",
  ])) return null;
  const asOf = timestamp(source.as_of);
  const score = Number(source.score);
  const dimensions = arrayFrom(source.dimensions).map(normalizeMarketDimension);
  if (
    source.metric_kind !== AI_MARKET_READINESS_KIND
    || source.definition_version !== AI_MARKET_READINESS_VERSION
    || !Number.isSafeInteger(score)
    || score < 0
    || score > 100
    || source.weights_total !== 100
    || !AI_MARKET_SCOPE_HASH.test(String(source.evidence_hash || ""))
    || !asOf
    || Date.parse(asOf) !== Date.parse(expectedAsOf)
    || dimensions.length !== AI_MARKET_DIMENSION_KEYS.length
    || dimensions.some((dimension) => !dimension)
    || new Set(dimensions.map((dimension) => dimension.key)).size
      !== AI_MARKET_DIMENSION_KEYS.length
    || !AI_MARKET_DIMENSION_KEYS.every((key) =>
      dimensions.some((dimension) => dimension.key === key)
    )
    || dimensions.reduce((sum, dimension) => sum + dimension.weight, 0) !== 100
    || dimensions.reduce((sum, dimension) => sum + dimension.weightedPoints, 0)
      !== score
  ) return null;
  return {
    definitionVersion: source.definition_version,
    score,
    dimensions,
    evidenceHash: source.evidence_hash,
    asOf,
  };
}

function normalizeMarketDimension(value) {
  const source = objectValue(value);
  if (!exactObjectKeys(source, [
    "key",
    "label",
    "weight",
    "current",
    "target",
    "score",
    "weighted_points",
    "missing",
    "next_action",
  ])) return null;
  const key = cleanText(source.key, 100);
  const label = cleanText(source.label, 200);
  const values = [
    source.weight,
    source.current,
    source.target,
    source.score,
    source.weighted_points,
    source.missing,
  ].map(Number);
  const [weight, current, target, score, weightedPoints, missing] = values;
  const nextAction = source.next_action === null
    ? ""
    : safeKey(source.next_action, 120);
  if (
    !AI_MARKET_DIMENSION_KEYS.includes(key)
    || !label
    || values.some((number) => !Number.isSafeInteger(number) || number < 0)
    || weight > 100
    || target < 1
    || current + missing < target
    || score > 100
    || weightedPoints > weight
    || (missing > 0 && !nextAction)
    || (missing === 0 && source.next_action !== null)
  ) return null;
  return {
    key,
    label,
    weight,
    current,
    target,
    score,
    weightedPoints,
    missing,
    nextAction,
  };
}

function normalizeMarketGuidance(value, readiness) {
  const source = objectValue(value);
  if (!exactObjectKeys(source, [
    "status",
    "gaps",
    "recommended_next_action",
  ])) return null;
  const gaps = arrayFrom(source.gaps).map(normalizeMarketDimension);
  const expectedGaps = readiness.dimensions.filter((dimension) => dimension.missing > 0);
  const recommendedNextAction = source.recommended_next_action === null
    ? ""
    : safeKey(source.recommended_next_action, 120);
  if (
    !AI_MARKET_GUIDANCE_STATUSES.has(source.status)
    || gaps.some((gap) => !gap)
    || gaps.length !== expectedGaps.length
    || gaps.some((gap, index) =>
      gap.key !== expectedGaps[index].key
      || gap.current !== expectedGaps[index].current
      || gap.missing !== expectedGaps[index].missing
    )
    || (expectedGaps.length > 0
      ? recommendedNextAction !== expectedGaps[0].nextAction
      : source.recommended_next_action !== null)
  ) return null;
  return {
    status: source.status,
    gaps,
    recommendedNextAction,
  };
}

export function normalizeAiLearningControlRoom(value, options = {}) {
  const source = envelopeSource(value);
  const explicitVersion = cleanText(
    source.version || source.schema || source.schema_version || source.schemaVersion,
    100,
  );
  const versionValid = explicitVersion === AI_LEARNING_CONTROL_ROOM_VERSION;
  const suppliedCategories = arrayFrom(
    source.categories?.items || source.category_summaries || source.categorySummaries
      || source.categories,
  );
  const rawDetail = objectValue(
    source.category_detail || source.categoryDetail || source.category
      || source.detail || source.selected,
  );
  const suppliedCategoryKeys = suppliedCategories.map(categoryKeyFrom);
  const firstSuppliedKey = suppliedCategoryKeys
    .find((key) => AI_CATEGORY_BY_KEY.has(key));
  const categoryContractValid = suppliedCategories.length === AI_PRODUCT_CATEGORIES.length
    && suppliedCategoryKeys.every((key) => AI_CATEGORY_BY_KEY.has(key))
    && new Set(suppliedCategoryKeys).size === AI_PRODUCT_CATEGORIES.length
    && AI_PRODUCT_CATEGORIES.every(({ key }) => suppliedCategoryKeys.includes(key));
  const selectedCategory = aiLearningCategory(
    options.category || options.selectedCategory
      || source.selected_category || source.selectedCategory
      || categoryKeyFrom(rawDetail) || firstSuppliedKey,
    firstSuppliedKey || "cosmetics",
  );
  const actor = normalizeActor(source.actor);
  const capabilities = normalizeCapabilities(
    source.capabilities || objectValue(source.actor)?.capabilities,
    actor,
  );

  const rawByCategory = new Map();
  for (const candidate of suppliedCategories) {
    const key = categoryKeyFrom(candidate);
    if (AI_CATEGORY_BY_KEY.has(key) && !rawByCategory.has(key)) {
      rawByCategory.set(key, candidate);
    }
  }
  if (rawDetail) {
    const detailKey = categoryKeyFrom(rawDetail) || selectedCategory;
    if (AI_CATEGORY_BY_KEY.has(detailKey)) {
      rawByCategory.set(detailKey, {
        ...(objectValue(rawByCategory.get(detailKey)) || {}),
        ...rawDetail,
        key: detailKey,
      });
    }
  }

  const categories = AI_PRODUCT_CATEGORIES.map((definition) =>
    normalizeCategorySummary(rawByCategory.get(definition.key), definition)
  );
  const selectedSummary = categories.find((item) => item.key === selectedCategory)
    || categories[0];
  const selectedRaw = rawByCategory.get(selectedCategory) || rawDetail || {};
  const category = normalizeCategoryDetail(selectedRaw, selectedSummary);
  const stateVersion = nonNegativeInteger(
    source.state_version ?? source.stateVersion,
    0,
  );
  const eventCursor = nonNegativeInteger(
    source.event_cursor ?? source.eventCursor,
    stateVersion,
  );
  const asOf = timestamp(
    source.as_of || source.asOf || category.asOf || source.updated_at
      || source.updatedAt,
  );
  const hasSnapshotData = suppliedCategories.length > 0
    || Boolean(rawDetail)
    || Boolean(source.selected_category || source.selectedCategory);
  const available = Boolean(source)
    && source.ok !== false
    && versionValid
    && categoryContractValid
    && hasSnapshotData;

  return {
    available,
    reason: !versionValid
      ? "invalid_schema"
      : !categoryContractValid
        ? "invalid_categories"
        : available ? "" : "snapshot_unavailable",
    ok: available,
    version: AI_LEARNING_CONTROL_ROOM_VERSION,
    schemaVersion: AI_LEARNING_CONTROL_ROOM_VERSION,
    organizationId: cleanText(
      source.organization_id || source.organizationId,
      180,
    ),
    runId: cleanText(source.run_id || source.runId, 180),
    stateVersion,
    eventCursor,
    asOf,
    selectedCategory,
    actor,
    capabilities,
    categories,
    category,
    categoryDetail: category,
    guidance: normalizeGuidance(source.guidance, category),
    notice: cleanText(source.notice || source.message, 800),
    error: cleanText(
      source.error?.message || source.error_message || source.errorMessage,
      800,
    ),
  };
}

/**
 * Applies only a monotonic, versioned server snapshot. No readiness score or
 * teaching result is ever calculated optimistically in the browser.
 */
export function applyAiLearningControlRoomMutation(current, response) {
  const currentSnapshot = normalizedSnapshot(current);
  if (objectValue(response)?.ok === false) return currentSnapshot;
  const responseSource = envelopeSource(response);
  const responseVersion = cleanText(
    responseSource.version || responseSource.schema || responseSource.schema_version
      || responseSource.schemaVersion,
    100,
  );
  const nextStateVersion = strictNonNegativeInteger(
    responseSource.state_version ?? responseSource.stateVersion,
  );
  const nextEventCursor = strictNonNegativeInteger(
    responseSource.event_cursor ?? responseSource.eventCursor,
  );
  if (
    !responseSource
    || responseSource.ok === false
    || responseVersion !== AI_LEARNING_CONTROL_ROOM_VERSION
    || nextStateVersion === null
    || nextEventCursor === null
    || nextStateVersion < currentSnapshot.stateVersion
    || nextEventCursor < currentSnapshot.eventCursor
    || (
      nextStateVersion === currentSnapshot.stateVersion
      && nextEventCursor === currentSnapshot.eventCursor
    )
  ) {
    return currentSnapshot;
  }

  const suppliedCategories = arrayFrom(
    responseSource.categories?.items || responseSource.category_summaries
      || responseSource.categorySummaries || responseSource.categories,
  );
  const suppliedKeys = suppliedCategories.map(categoryKeyFrom);
  const categoryContractValid = suppliedCategories.length === AI_PRODUCT_CATEGORIES.length
    && suppliedKeys.every((key) => AI_CATEGORY_BY_KEY.has(key))
    && new Set(suppliedKeys).size === AI_PRODUCT_CATEGORIES.length
    && AI_PRODUCT_CATEGORIES.every(({ key }) => suppliedKeys.includes(key));
  if (!categoryContractValid) return currentSnapshot;
  const selectedCategory = currentSnapshot.selectedCategory;
  const authoritative = normalizeAiLearningControlRoom({
    ...responseSource,
    ok: true,
    version: AI_LEARNING_CONTROL_ROOM_VERSION,
    state_version: nextStateVersion,
    event_cursor: nextEventCursor,
    selected_category: selectedCategory,
  }, { category: selectedCategory });
  return authoritative.available ? authoritative : currentSnapshot;
}

export function aiLearningControlRoomMarkup(snapshot, options = {}) {
  const control = normalizedSnapshot(snapshot);
  const view = aiLearningView(options.view || options.selectedView);
  const selectedCategory = aiLearningCategory(
    options.selectedCategory || options.category || control.selectedCategory,
    control.selectedCategory,
  );
  const categorySummary = control.categories.find(
    (item) => item.key === selectedCategory,
  ) || control.categories[0];
  const category = selectedCategory === control.category.key
    ? control.category
    : normalizeCategoryDetail(categorySummary, categorySummary);
  const status = statusMeta(category.status, category.score, category.available);
  const busyCardId = cleanText(options.busyCardId, 200);
  const busy = Boolean(
    options.busy || options.saving || options.loading || options.refreshing
      || busyCardId,
  );
  const notice = cleanText(options.notice || control.notice, 800);
  const error = cleanText(options.error || control.error, 800);
  const legacyReadOnly = options.legacyReadOnly === true;
  const marketLearningMarkup = String(options.marketLearningMarkup || "");
  const canAddLink = control.available && control.capabilities.canAddLink
    && !busy && !legacyReadOnly;
  const canUploadFile = control.available && control.capabilities.canUploadFile
    && !busy && !legacyReadOnly;
  const canDecide = control.available && control.capabilities.canDecide
    && !busy && !legacyReadOnly;
  const updatedLabel = formatDateTime(options.lastUpdatedAt || control.asOf);
  const statusAnnouncement = legacyReadOnly
    ? `${category.label}. Архивный legacy-показатель ${category.score} процентов; он не используется как readiness или generation policy.`
    : busy
    ? `Обновляем категорию «${category.label}». Текущая готовность доказательной базы ${category.score} процентов.`
    : `${category.label}. ${status.label}. Готовность доказательной базы ${category.score} процентов.`;

  return `<section class="ai-learning-control-room" data-ai-view="${view}" data-ai-category="${escapeHtml(selectedCategory)}" data-state-version="${control.stateVersion}" data-event-cursor="${control.eventCursor}" data-ce-patch-key="ai-learning-control-room" aria-labelledby="ai-learning-title">
    <div class="ai-learning-atmosphere" aria-hidden="true"></div>
    <header class="ai-learning-hero">
      <div class="ai-learning-identity">
        <div class="ai-learning-orb is-${status.tone}${busy ? " is-thinking" : ""}" role="img" aria-label="${escapeHtml(busy ? "ИИ пересчитывает правила категории" : status.label)}">
          <span class="ai-learning-orb-core"></span>
          <span class="ai-learning-orb-ring ai-learning-orb-ring-one"></span>
          <span class="ai-learning-orb-ring ai-learning-orb-ring-two"></span>
        </div>
        <div>
          <p class="ai-learning-eyebrow">AI Learning Control Room</p>
          <h1 id="ai-learning-title">Командный пункт обучения ИИ</h1>
          <p>Управляем доказательствами и ограниченными правилами отдельно для каждой категории товаров.</p>
        </div>
      </div>
      <div class="ai-learning-live" aria-live="polite" aria-atomic="true" data-ce-patch-key="ai-learning-live-status">
        <span class="ai-learning-live-dot${busy ? " is-busy" : ""}" aria-hidden="true"></span>
        <span>${escapeHtml(statusAnnouncement)}</span>
        <small>${updatedLabel ? `Снимок: ${escapeHtml(updatedLabel)}` : "Ожидаем первый серверный снимок"}</small>
      </div>
      <button class="ai-learning-refresh" type="button" data-action="refresh-ai-learning" ${busy ? "disabled" : ""}>
        <span aria-hidden="true">↻</span><span>Обновить статус</span>
      </button>
    </header>

    ${!control.available ? unavailableMarkup(control.reason) : ""}
    ${error ? `<div class="ai-learning-message is-error" role="alert">${escapeHtml(error)}</div>` : ""}
    ${notice ? `<div class="ai-learning-message" role="status">${escapeHtml(notice)}</div>` : ""}

    ${marketLearningMarkup}

    ${legacyReadOnly ? `<aside class="ai-learning-legacy-boundary" role="note">
      <strong>Legacy safety bucket · только история</strong>
      <span>Восемь старых product_category сохранены для совместимости и аудита. Их регистрации и teaching cards не считаются анализом и больше не меняют платную генерацию. Для решений используйте точную market category и evidence ledger выше.</span>
    </aside>` : ""}

    <div class="ai-learning-category-strip" role="group" aria-label="Legacy safety categories">
      ${control.categories.map((item) => categoryButtonMarkup(item, selectedCategory, busy)).join("")}
    </div>

    <div class="ai-learning-view-tabs" role="tablist" aria-label="Разделы командного пункта">
      ${viewTabMarkup("overview", "Обзор", view)}
      ${viewTabMarkup("knowledge", "База знаний", view)}
      ${viewTabMarkup("teach", "Обучить", view, category.pendingTeachingCount)}
      ${viewTabMarkup("history", "История", view)}
    </div>

    <div class="ai-learning-view-panel" id="ai-learning-panel-overview" role="tabpanel" aria-labelledby="ai-learning-tab-overview" ${view === "overview" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-overview">
      ${overviewMarkup(category, control, status, legacyReadOnly)}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-knowledge" role="tabpanel" aria-labelledby="ai-learning-tab-knowledge" ${view === "knowledge" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-knowledge">
      ${knowledgeMarkup(category, control, { canAddLink, canUploadFile, busy })}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-teach" role="tabpanel" aria-labelledby="ai-learning-tab-teach" ${view === "teach" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-teach">
      ${teachMarkup(category, control, {
        canDecide,
        busy,
        busyCardId,
        legacyReadOnly,
      })}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-history" role="tabpanel" aria-labelledby="ai-learning-tab-history" ${view === "history" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-history">
      ${historyMarkup(category, control, legacyReadOnly)}
    </div>
  </section>`;
}

function overviewMarkup(category, control, status, legacyReadOnly = false) {
  const confidence = confidenceText(category);
  return `<div class="ai-learning-overview-grid">
    <article class="ai-learning-readiness-card is-${status.tone}" data-ce-patch-key="ai-readiness-${category.key}">
      <div class="ai-learning-score-ring" style="--ai-learning-score:${category.score}" role="img" aria-label="${legacyReadOnly ? "Архивный legacy-показатель" : "Готовность доказательной базы категории"}: ${category.score} процентов">
        <strong>${category.score}%</strong>
        <span>evidence</span>
      </div>
      <div class="ai-learning-readiness-copy">
        <p class="ai-learning-eyebrow">${escapeHtml(category.label)}</p>
        <h2>Готовность доказательной базы</h2>
        <span class="ai-learning-status-pill is-${status.tone}">${escapeHtml(status.label)}</span>
        <p>Показатель отражает покрытие проверяемых источников и решений команды. Это не IQ, не accuracy модели и не гарантия качества результата.</p>
        <small>Версия области: ${category.scopeVersion || "—"}${category.evidenceHash ? ` · evidence ${escapeHtml(shortHash(category.evidenceHash))}` : ""}</small>
      </div>
    </article>
    <div class="ai-learning-metric-grid" aria-label="Метрики категории">
      ${metricMarkup("Доказательства", category.evidenceCount, "проверяемых наблюдений")}
      ${metricMarkup("Источники", category.sourceCount, "в журнале происхождения")}
      ${metricMarkup("Уверенность", confidence.value, confidence.note)}
      ${metricMarkup("Ждут решения", category.pendingTeachingCount, "карточек хорошо / плохо")}
    </div>
  </div>

  <section class="ai-learning-section ai-learning-dimensions-section" aria-labelledby="ai-learning-dimensions-title">
    <div class="ai-learning-section-heading">
      <div><p class="ai-learning-eyebrow">Signal map</p><h2 id="ai-learning-dimensions-title">Из чего складывается готовность</h2></div>
      <span>${category.dimensions.length ? `${category.dimensions.length} измерений` : "Ожидаем метрики"}</span>
    </div>
    <div class="ai-learning-dimensions">
      ${category.dimensions.length
        ? category.dimensions.map(dimensionMarkup).join("")
        : emptyMarkup("Сервер ещё не прислал измерения", "До этого момента процент не интерпретируется как оценка интеллекта модели.")}
    </div>
  </section>

  <section class="ai-learning-section ai-learning-gaps-section" aria-labelledby="ai-learning-gaps-title">
    <div class="ai-learning-section-heading">
      <div><p class="ai-learning-eyebrow">Next best evidence</p><h2 id="ai-learning-gaps-title">Чего не хватает ИИ</h2></div>
      <span>${category.gaps.length ? `${category.gaps.length} пробела` : "Пробелы закрыты"}</span>
    </div>
    <div class="ai-learning-gap-grid">
      ${category.gaps.length
        ? category.gaps.map(gapMarkup).join("")
        : emptyMarkup("Явных пробелов сейчас нет", "Продолжайте проверять свежесть источников и новые решения команды.")}
    </div>
  </section>

  ${effectivePolicyMarkup(category.effectivePolicy, control, false, legacyReadOnly)} `;
}

function knowledgeMarkup(category, control, { canAddLink, canUploadFile, busy }) {
  const disabledLink = canAddLink ? "" : "disabled";
  const disabledFile = canUploadFile ? "" : "disabled";
  return `<div class="ai-learning-knowledge-intro">
    <div>
      <p class="ai-learning-eyebrow">Knowledge intake</p>
      <h2>Добавить знания о категории «${escapeHtml(category.label)}»</h2>
      <p>Файл или ссылка регистрируется с происхождением и контрольными данными. До отдельного проверенного разбора сырое содержимое не попадает в промпт.</p>
    </div>
    <span class="ai-learning-boundary-note">Только проверяемые данные</span>
  </div>
  <div class="ai-learning-intake-grid">
    <form id="ai-knowledge-link-form" class="ai-learning-intake-card" data-form="ai-learning-link" data-ce-patch-key="ai-knowledge-link-form" novalidate>
      ${scopeInputs(control, category)}
      <div class="ai-learning-intake-icon" aria-hidden="true">↗</div>
      <h3>Добавить ссылку</h3>
      <p>Публичная карточка товара, обзор, документация или проверяемый материал.</p>
      <label><span>URL источника</span><input type="url" name="source_url" inputmode="url" maxlength="2000" placeholder="https://…" required ${disabledLink} /></label>
      <label><span>Название</span><input type="text" name="title" minlength="2" maxlength="160" placeholder="Что содержит источник" required ${disabledLink} /></label>
      <label><span>Заметка <small>(необязательно)</small></span><textarea name="note" maxlength="1000" placeholder="Что важно проверить в этом материале" ${disabledLink}></textarea></label>
      <label class="ai-learning-rights"><input type="checkbox" name="rights_confirmed" required ${disabledLink} /><span>У команды есть право хранить и анализировать этот источник.</span></label>
      <button type="submit" ${disabledLink}>${busy ? "Сохраняем…" : "Зарегистрировать источник"}</button>
      ${capabilityHint(control.capabilities.canAddLink, "добавлять ссылки")}
    </form>
    <form id="ai-knowledge-file-form" class="ai-learning-intake-card" data-form="ai-learning-file" data-ce-patch-key="ai-knowledge-file-form" enctype="multipart/form-data" novalidate>
      ${scopeInputs(control, category)}
      <div class="ai-learning-intake-icon" aria-hidden="true">＋</div>
      <h3>Загрузить файл</h3>
      <p>PDF, DOCX, XLSX, CSV, Markdown или TXT с подтверждаемым происхождением, до 25 МБ.</p>
      <label class="ai-learning-file-field"><span>Выберите файл</span><input id="ai-knowledge-file" type="file" name="file" accept=".pdf,.docx,.xlsx,.csv,.md,.txt" required ${disabledFile} /><small data-ai-file-summary aria-live="polite">Файл не выбран</small></label>
      <label><span>Название</span><input type="text" name="title" minlength="2" maxlength="160" placeholder="Кратко о содержимом" required ${disabledFile} /></label>
      <label><span>Заметка <small>(необязательно)</small></span><textarea name="note" maxlength="1000" placeholder="Что важно извлечь и проверить" ${disabledFile}></textarea></label>
      <label class="ai-learning-rights"><input type="checkbox" name="rights_confirmed" required ${disabledFile} /><span>У команды есть право хранить и анализировать этот файл.</span></label>
      <button type="submit" ${disabledFile}>${busy ? "Загружаем…" : "Сохранить в базе знаний"}</button>
      ${capabilityHint(control.capabilities.canUploadFile, "загружать файлы")}
    </form>
  </div>
  <aside class="ai-learning-safety-note" role="note">
    <strong>Граница безопасности</strong>
    <p>Загрузка создаёт запись в журнале источников, но не меняет промпт и не включает новое правило сама по себе. Влияние появляется только после серверной проверки и отдельного решения человека.</p>
  </aside>
  <section class="ai-learning-section" aria-labelledby="ai-learning-ledger-title">
    <div class="ai-learning-section-heading">
      <div><p class="ai-learning-eyebrow">Source ledger</p><h2 id="ai-learning-ledger-title">Журнал знаний и происхождения</h2></div>
      <span>${category.sources.length} источников</span>
    </div>
    <div class="ai-learning-source-list">
      ${category.sources.length
        ? category.sources.map(sourceMarkup).join("")
        : emptyMarkup("Источников пока нет", "Добавьте ссылку или файл: система зафиксирует происхождение и статус регистрации здесь.")}
    </div>
  </section>`;
}

function teachMarkup(category, control, {
  canDecide,
  busy,
  busyCardId,
  legacyReadOnly = false,
}) {
  return `<div class="ai-learning-teach-intro">
    <div>
      <p class="ai-learning-eyebrow">Human-in-the-loop</p>
      <h2>Что для категории хорошо, а что плохо</h2>
      <p>${legacyReadOnly
        ? "Это прежняя восьмикатегорийная история. Она не подтверждена parser lineage и больше не применяется к генерации."
        : "ИИ показывает своё текущее суждение по одному ограниченному сигналу. Вы подтверждаете или отклоняете его — решение применяется сервером к новой версии правила без перезагрузки страницы."}</p>
    </div>
    <div class="ai-learning-teach-legend" aria-label="Решение команды">
      <span class="is-good"><b aria-hidden="true">✓</b> ОК, верно</span>
      <span class="is-bad"><b aria-hidden="true">×</b> Не ОК</span>
    </div>
  </div>
  <aside class="ai-learning-safety-note is-accent" role="note">
    <strong>${legacyReadOnly ? "Audit-only: влияние отключено" : "Немедленное, но ограниченное влияние"}</strong>
    <p>${legacyReadOnly
      ? "Для управляемого решения откройте точную market category выше: там доступны source analysis, история версий и CAS-исправления."
      : "После authoritative-ответа меняется только указанное правило этой категории и его версия. Решение не переобучает базовую модель, не переносится на другие категории и не гарантирует результат."}</p>
  </aside>
  <div class="ai-learning-teaching-list" aria-live="polite">
    ${category.teachingCards.length
      ? category.teachingCards.map((card) => teachingCardMarkup(card, category, control, { canDecide, busy, busyCardId })).join("")
      : emptyMarkup("Нет карточек для решения", "Новые карточки появятся после анализа проверенных источников и результатов контента.")}
  </div>`;
}

function historyMarkup(category, control, legacyReadOnly = false) {
  return `<div class="ai-learning-history-head">
    <div><p class="ai-learning-eyebrow">Immutable activity</p><h2>История обучения категории</h2><p>Серверный журнал показывает, кто и когда добавил доказательство, принял решение или выпустил новую версию правила.</p></div>
    <dl>
      <div><dt>State version</dt><dd>${control.stateVersion}</dd></div>
      <div><dt>Event cursor</dt><dd>${control.eventCursor}</dd></div>
      <div><dt>Scope version</dt><dd>${category.scopeVersion || "—"}</dd></div>
    </dl>
  </div>
  <ol class="ai-learning-timeline">
    ${category.activity.length
      ? category.activity.map(activityMarkup).join("")
      : `<li class="ai-learning-timeline-empty" data-ce-patch-key="ai-history-empty"><span></span><div><strong>История пока пуста</strong><p>Первое принятое сервером действие появится здесь без обновления страницы.</p></div></li>`}
  </ol>
  ${effectivePolicyMarkup(category.effectivePolicy, control, true, legacyReadOnly)}`;
}

function categoryButtonMarkup(category, selectedCategory, busy) {
  const selected = category.key === selectedCategory;
  const status = statusMeta(category.status, category.score, category.available);
  return `<button class="ai-learning-category${selected ? " is-active" : ""}" type="button" data-action="select-ai-learning-category" data-category-key="${category.key}" data-ce-patch-key="ai-category-button-${category.key}" aria-pressed="${selected}" ${busy ? "disabled" : ""}>
    <span>${escapeHtml(category.label)}</span>
    <strong>${category.available ? `${category.score}%` : "—"}</strong>
    <small class="is-${status.tone}">${escapeHtml(status.short)}</small>
  </button>`;
}

function viewTabMarkup(key, label, activeView, count = 0) {
  const active = key === activeView;
  return `<button id="ai-learning-tab-${key}" type="button" role="tab" data-action="select-ai-learning-view" data-view="${key}" aria-controls="ai-learning-panel-${key}" aria-selected="${active}" tabindex="${active ? "0" : "-1"}">${escapeHtml(label)}${count > 0 ? `<span>${count}</span>` : ""}</button>`;
}

function metricMarkup(label, value, note) {
  return `<article class="ai-learning-metric">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(String(value ?? "—"))}</strong>
    <small>${escapeHtml(note)}</small>
  </article>`;
}

function dimensionMarkup(dimension) {
  const complete = dimension.missing <= 0 && dimension.target > 0;
  const progress = dimension.target > 0
    ? clampScore(Math.round(dimension.current / dimension.target * 100))
    : dimension.score;
  return `<article class="ai-learning-dimension${complete ? " is-complete" : ""}" data-ce-patch-key="ai-dimension-${escapeHtml(dimension.key)}">
    <div><span>${escapeHtml(dimension.label)}</span><strong>${dimension.current} / ${dimension.target || "—"}</strong></div>
    <div class="ai-learning-progress" role="progressbar" aria-label="${escapeHtml(dimension.label)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><span style="--ai-dimension-progress:${progress}"></span></div>
    <p>${complete ? "Цель по доказательствам достигнута." : escapeHtml(dimension.nextAction || `Не хватает: ${dimension.missing}.`)}</p>
  </article>`;
}

function gapMarkup(gap) {
  return `<article class="ai-learning-gap is-${escapeHtml(gap.priority)}" data-ce-patch-key="ai-gap-${escapeHtml(gap.key)}">
    <span class="ai-learning-gap-mark" aria-hidden="true">${gap.priority === "high" ? "!" : "+"}</span>
    <div><h3>${escapeHtml(gap.title)}</h3>${gap.description ? `<p>${escapeHtml(gap.description)}</p>` : ""}<small>${escapeHtml(gap.nextAction || "Добавить проверяемое доказательство")}</small></div>
    ${gap.missing > 0 ? `<strong>−${gap.missing}</strong>` : ""}
  </article>`;
}

function sourceMarkup(source) {
  const link = source.url
    ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">Открыть <span aria-hidden="true">↗</span></a>`
    : "";
  return `<article class="ai-learning-source is-${escapeHtml(source.status)}" data-source-id="${escapeHtml(source.id)}" data-ce-patch-key="ai-source-${escapeHtml(source.id)}">
    <div class="ai-learning-source-kind" aria-hidden="true">${source.kind === "file" ? "▤" : "↗"}</div>
    <div class="ai-learning-source-copy">
      <div><span>${escapeHtml(sourceKindLabel(source.kind))}</span><span class="ai-learning-source-status">${escapeHtml(sourceStatusLabel(source.status))}</span></div>
      <h3>${escapeHtml(source.title || "Источник без названия")}</h3>
      <p>${escapeHtml(source.provenance || source.host || "Происхождение проверяется")}</p>
      <small>${formatDateTime(source.addedAt) ? `Добавлен ${escapeHtml(formatDateTime(source.addedAt))}` : "Дата добавления не указана"}${source.evidenceHash ? ` · ${escapeHtml(shortHash(source.evidenceHash))}` : ""}</small>
    </div>
    ${link}
  </article>`;
}

function teachingCardMarkup(card, category, control, { canDecide, busy, busyCardId }) {
  const decided = card.status !== "pending";
  const cardBusy = Boolean(busyCardId && busyCardId === card.id);
  const disabled = !canDecide || decided || busy || cardBusy;
  const judgement = card.aiJudgement === "good"
    ? "ИИ считает сигнал хорошим"
    : card.aiJudgement === "bad"
      ? "ИИ считает сигнал плохим"
      : "ИИ просит решения человека";
  const cardKey = `ai-teaching-${category.key}-${card.id}-${card.version}-${card.hash || "nohash"}`;
  return `<article class="ai-learning-teaching-card is-${escapeHtml(card.status)}${cardBusy ? " is-busy" : ""}" data-ai-teaching-card data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-ce-patch-key="${escapeHtml(cardKey)}">
    <header>
      <div><p class="ai-learning-eyebrow">${escapeHtml(card.signalKey || "Сигнал категории")}</p><h3>${escapeHtml(card.title || "Проверить суждение ИИ")}</h3></div>
      <span class="ai-learning-judgement is-${escapeHtml(card.aiJudgement)}">${escapeHtml(judgement)}</span>
    </header>
    ${card.context ? `<p class="ai-learning-teaching-context">${escapeHtml(card.context)}</p>` : ""}
    ${card.rationale ? `<blockquote>${escapeHtml(card.rationale)}</blockquote>` : ""}
    <dl>
      <div><dt>Доказательств</dt><dd>${card.evidenceCount}</dd></div>
      <div><dt>Версия</dt><dd>${card.version}</dd></div>
      <div><dt>Candidate</dt><dd><code>${escapeHtml(shortHash(card.hash || card.id))}</code></dd></div>
    </dl>
    ${decided ? teachingDecisionMarkup(card) : `<form class="ai-learning-decision-form" data-form="ai-learning-decision" data-ce-patch-key="ai-decision-form-${escapeHtml(card.id)}" novalidate>
      ${scopeInputs(control, category)}
      <input type="hidden" name="card_id" value="${escapeHtml(card.id)}" />
      <input type="hidden" name="card_version" value="${card.version}" />
      <input type="hidden" name="card_hash" value="${escapeHtml(card.hash)}" />
      <input type="hidden" name="expected_scope_version" value="${category.scopeVersion}" />
      <label class="ai-learning-confirm"><input type="checkbox" name="confirmation" value="true" required ${disabled ? "disabled" : ""} /><span>Я проверил контекст и понимаю, что решение изменит только bounded-правило этой категории.</span></label>
      <div class="ai-learning-decision-actions">
        <button class="is-good" type="submit" data-action="decide-ai-teaching-card" data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-decision="approve" ${disabled ? "disabled" : ""}><span aria-hidden="true">✓</span> ${cardBusy ? "Применяем…" : "ОК, верно"}</button>
        <button class="is-bad" type="submit" data-action="decide-ai-teaching-card" data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-decision="reject" ${disabled ? "disabled" : ""}><span aria-hidden="true">×</span> ${cardBusy ? "Применяем…" : "Не ОК"}</button>
      </div>
      ${capabilityHint(control.capabilities.canDecide, "принимать решения")}
    </form>`}
  </article>`;
}

function teachingDecisionMarkup(card) {
  const decision = AI_TEACHING_DECISIONS.has(card.decision)
    ? card.decision
    : card.status === "approved" ? "approve" : "reject";
  return `<div class="ai-learning-recorded-decision is-${decision === "approve" ? "good" : "bad"}" role="status">
    <strong>${decision === "approve" ? "Подтверждено: суждение верно" : "Отклонено: суждение неверно"}</strong>
    <span>${card.decidedBy ? `${escapeHtml(card.decidedBy)} · ` : ""}${escapeHtml(formatDateTime(card.decidedAt) || "решение сохранено")}</span>
    ${card.reason ? `<p>${escapeHtml(card.reason)}</p>` : ""}
  </div>`;
}

function activityMarkup(item) {
  return `<li data-ce-patch-key="ai-activity-${escapeHtml(item.id)}">
    <span class="is-${escapeHtml(item.tone)}" aria-hidden="true"></span>
    <div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.description)}</p><small>${item.actor ? `${escapeHtml(item.actor)} · ` : ""}${escapeHtml(formatDateTime(item.createdAt) || "Время не указано")}${item.stateVersion ? ` · state ${item.stateVersion}` : ""}</small></div>
  </li>`;
}

function effectivePolicyMarkup(
  policy,
  control,
  compact = false,
  legacyReadOnly = false,
) {
  const instance = compact ? "history" : "overview";
  const headingId = `ai-learning-policy-${instance}-title`;
  const rules = policy.rules.length
    ? `<ul>${policy.rules.map((rule) => `<li data-ce-patch-key="ai-policy-rule-${escapeHtml(rule.id)}"><span>${escapeHtml(rule.label)}</span><small>${escapeHtml(rule.effect)}</small></li>`).join("")}</ul>`
    : emptyMarkup("Активных правил пока нет", "Решения человека появятся здесь только после серверного выпуска новой версии политики.");
  return `<section class="ai-learning-section ai-learning-policy${compact ? " is-compact" : ""}" aria-labelledby="${headingId}" data-ce-patch-key="ai-effective-policy-${instance}-${escapeHtml(policy.hash || "empty")}">
    <div class="ai-learning-section-heading">
      <div><p class="ai-learning-eyebrow">${legacyReadOnly ? "Archived legacy policy" : "Effective policy"}</p><h2 id="${headingId}">${legacyReadOnly ? "Архивная политика: влияние отключено" : "Правила, которые реально учитывает ИИ"}</h2></div>
      <span>${policy.version ? `v${escapeHtml(policy.version)}` : "Нет версии"}</span>
    </div>
    <div class="ai-learning-policy-body">
      <div><strong>${legacyReadOnly ? "Audit-only" : escapeHtml(policyStatusLabel(policy.status))}</strong><p>${legacyReadOnly ? "Снимок сохранён только для истории. Он не влияет на prompt, paid generation или policy точной market category." : "Только этот серверный снимок может влиять на bounded-подсказки выбранной категории. Сырые источники и pending-карточки сюда не входят."}</p><small>${policy.hash ? `Policy ${escapeHtml(shortHash(policy.hash))}` : "Policy hash ещё не выпущен"}${control.asOf ? ` · ${escapeHtml(formatDateTime(control.asOf))}` : ""}</small></div>
      ${rules}
    </div>
  </section>`;
}

function scopeInputs(control, category) {
  return `<input type="hidden" name="run_id" value="${escapeHtml(control.runId)}" /><input type="hidden" name="product_category" value="${escapeHtml(category.key)}" /><input type="hidden" name="scope_version" value="${category.scopeVersion}" /><input type="hidden" name="expected_state_version" value="${control.stateVersion}" />`;
}

function capabilityHint(allowed, action) {
  return allowed
    ? ""
    : `<small class="ai-learning-capability-note">У вашей роли нет права ${escapeHtml(action)} в этом контуре.</small>`;
}

function unavailableMarkup(reason) {
  const invalidSchema = reason === "invalid_schema";
  const invalidCategories = reason === "invalid_categories";
  return `<div class="ai-learning-message is-warning" role="alert">
    <strong>${invalidSchema
      ? "Неизвестная версия снимка"
      : invalidCategories
        ? "Неполный список категорий"
        : "Первый снимок ещё не получен"}</strong>
    <span>${invalidSchema
      ? "Метрики скрыты, чтобы не создавать ложную точность. Проверьте совместимость backend-контракта."
      : invalidCategories
        ? "Сервер должен вернуть ровно восемь уникальных категорий. До этого момента решения и загрузка знаний заблокированы."
        : "Командный пункт покажет метрики после ответа authoritative-контура."}</span>
  </div>`;
}

function emptyMarkup(title, description) {
  return `<div class="ai-learning-empty"><span aria-hidden="true">◇</span><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div></div>`;
}

function normalizeCategorySummary(raw, definition) {
  const source = objectValue(raw) || {};
  const readiness = objectValue(source.readiness) || source;
  const hasData = Boolean(raw);
  const score = clampScore(
    readiness.score ?? readiness.readiness_score ?? source.score,
  );
  const status = normalizeStatus(
    source.status || readiness.status || source.readiness_status
      || source.readinessStatus || source.guidance_status,
    score,
    hasData,
  );
  const confidence = normalizeConfidence(
    readiness.confidence ?? source.confidence,
  );
  const sources = arrayFrom(
    source.knowledge_sources || source.knowledgeSources || source.sources,
  );
  const cards = arrayFrom(source.teaching_cards || source.teachingCards);
  return {
    available: hasData,
    key: definition.key,
    slug: definition.slug,
    label: definition.label,
    score,
    status,
    confidence: confidence.value,
    confidencePercent: confidence.percent,
    evidenceCount: nonNegativeInteger(
      readiness.evidence_count ?? readiness.evidenceCount
        ?? source.evidence_count ?? source.evidenceCount,
      0,
    ),
    sourceCount: nonNegativeInteger(
      readiness.source_count ?? readiness.sourceCount
        ?? source.source_count ?? source.sourceCount,
      sources.length,
    ),
    pendingTeachingCount: nonNegativeInteger(
      source.pending_teaching_count ?? source.pendingTeachingCount,
      cards.filter((item) => cleanText(item?.status, 40).toLowerCase() === "pending").length,
    ),
    scopeVersion: nonNegativeInteger(
      source.scope_version ?? source.scopeVersion,
      0,
    ),
    asOf: timestamp(source.as_of || source.asOf),
    evidenceHash: cleanText(
      readiness.evidence_hash || readiness.evidenceHash
        || source.evidence_hash || source.evidenceHash,
      240,
    ),
  };
}

function normalizeCategoryDetail(raw, summary) {
  const source = objectValue(raw) || {};
  const readiness = objectValue(source.readiness) || source;
  const confidence = normalizeConfidence(
    readiness.confidence ?? source.confidence ?? summary.confidence,
  );
  const dimensions = arrayFrom(
    readiness.dimensions || source.dimensions,
  ).map(normalizeDimension).filter(Boolean).slice(0, 12);
  const explicitGaps = arrayFrom(
    source.gaps || objectValue(source.guidance)?.gaps,
  ).map(normalizeGap).filter(Boolean).slice(0, 24);
  const gaps = explicitGaps.length
    ? explicitGaps
    : dimensions.filter((item) => item.missing > 0).map((item) => ({
      key: item.key,
      title: item.label,
      description: `Не хватает ${item.missing} до целевого покрытия ${item.target}.`,
      missing: item.missing,
      nextAction: item.nextAction || "Добавить проверяемое доказательство",
      priority: item.missing >= Math.max(2, Math.ceil(item.target / 2)) ? "high" : "normal",
    }));
  const sources = arrayFrom(
    source.knowledge_sources || source.knowledgeSources || source.sources,
  ).map(normalizeSource).filter(Boolean).slice(0, 100);
  const teachingCards = arrayFrom(
    source.teaching_cards || source.teachingCards,
  ).map(normalizeTeachingCard).filter(Boolean).slice(0, 100);
  const activity = arrayFrom(
    source.activity?.items || source.activity || source.history?.items
      || source.history,
  ).map(normalizeActivity).filter(Boolean).slice(0, 100);
  const score = clampScore(readiness.score ?? source.score ?? summary.score);
  const status = normalizeStatus(
    source.status || readiness.status || summary.status,
    score,
    summary.available || Boolean(raw),
  );
  return {
    ...summary,
    available: summary.available || Boolean(raw),
    score,
    status,
    confidence: confidence.value,
    confidencePercent: confidence.percent,
    evidenceCount: nonNegativeInteger(
      readiness.evidence_count ?? readiness.evidenceCount
        ?? source.evidence_count ?? source.evidenceCount,
      summary.evidenceCount,
    ),
    sourceCount: nonNegativeInteger(
      readiness.source_count ?? readiness.sourceCount
        ?? source.source_count ?? source.sourceCount,
      sources.length || summary.sourceCount,
    ),
    pendingTeachingCount: teachingCards.filter((item) => item.status === "pending").length,
    scopeVersion: nonNegativeInteger(
      source.scope_version ?? source.scopeVersion,
      summary.scopeVersion,
    ),
    evidenceHash: cleanText(
      readiness.evidence_hash || readiness.evidenceHash
        || source.evidence_hash || source.evidenceHash
        || summary.evidenceHash,
      240,
    ),
    asOf: timestamp(source.as_of || source.asOf || summary.asOf),
    dimensions,
    gaps,
    sources,
    teachingCards,
    activity,
    effectivePolicy: normalizePolicy(
      source.effective_policy || source.effectivePolicy,
    ),
  };
}

function normalizeDimension(raw) {
  const source = objectValue(raw);
  if (!source) return null;
  const key = safeKey(source.key || source.dimension, 80);
  if (!key) return null;
  const current = nonNegativeNumber(source.current ?? source.value, 0);
  const target = nonNegativeNumber(source.target, 0);
  const missing = nonNegativeNumber(
    source.missing,
    Math.max(0, target - current),
  );
  return {
    key,
    label: cleanText(source.label, 180) || DIMENSION_LABELS[key] || humanizeKey(key),
    current,
    target,
    missing,
    weight: clampScore(source.weight),
    score: clampScore(
      source.score ?? (target > 0 ? Math.round(current / target * 100) : 0),
    ),
    nextAction: cleanText(
      source.next_action || source.nextAction || source.guidance,
      600,
    ),
  };
}

function normalizeGap(raw) {
  const source = objectValue(raw);
  if (!source) return null;
  const key = safeKey(source.key || source.code || source.dimension, 100);
  if (!key) return null;
  const missing = nonNegativeNumber(source.missing ?? source.count, 0);
  const priorityCandidate = cleanText(source.priority, 20).toLowerCase();
  return {
    key,
    title: cleanText(source.title || source.label, 220)
      || DIMENSION_LABELS[key] || humanizeKey(key),
    description: cleanText(
      source.description || source.message || source.reason,
      800,
    ),
    missing,
    nextAction: cleanText(
      source.next_action || source.nextAction || source.action,
      600,
    ),
    priority: ["high", "normal", "low"].includes(priorityCandidate)
      ? priorityCandidate
      : missing > 3 ? "high" : "normal",
  };
}

function normalizeSource(raw, index) {
  const source = objectValue(raw);
  if (!source) return null;
  const url = safeHttpUrl(source.url || source.source_url || source.sourceUrl);
  const id = cleanText(
    source.id || source.source_id || source.sourceId || source.media_id
      || source.mediaId,
    200,
  ) || `source-${index + 1}`;
  const kindCandidate = cleanText(
    source.kind || source.type || source.source_kind || source.sourceKind
      || source.source_type || source.sourceType,
    40,
  ).toLowerCase();
  const kind = ["file", "link", "marketplace", "document", "image", "video"]
    .includes(kindCandidate)
    ? kindCandidate
    : url ? "link" : "file";
  const statusCandidate = cleanText(source.status, 40).toLowerCase();
  const status = ["queued", "processing", "active", "verified", "rejected", "failed"]
    .includes(statusCandidate)
    ? statusCandidate
    : "queued";
  return {
    id,
    kind,
    title: cleanText(source.title || source.name || source.filename, 240),
    url,
    host: url ? urlHost(url) : "",
    status,
    provenance: cleanText(
      source.provenance || source.lineage || source.publisher,
      500,
    ),
    mediaId: cleanText(source.media_id || source.mediaId, 180),
    evidenceHash: cleanText(
      source.evidence_hash || source.evidenceHash || source.hash,
      240,
    ),
    addedAt: timestamp(
      source.added_at || source.addedAt || source.created_at || source.createdAt,
    ),
    verifiedAt: timestamp(source.verified_at || source.verifiedAt),
  };
}

function normalizeTeachingCard(raw, index) {
  const source = objectValue(raw);
  if (!source) return null;
  const id = cleanText(
    source.id || source.card_id || source.cardId
      || source.candidate_id || source.candidateId,
    200,
  ) || `candidate-${index + 1}`;
  const version = positiveInteger(
    source.version || source.card_version || source.cardVersion
      || source.candidate_version || source.candidateVersion,
    1,
  );
  const hash = cleanText(
    source.hash || source.card_hash || source.cardHash
      || source.candidate_hash || source.candidateHash,
    240,
  );
  const judgementCandidate = cleanText(
    source.ai_judgement || source.aiJudgement || source.judgement
      || source.polarity,
    40,
  ).toLowerCase();
  const statusCandidate = cleanText(source.status, 40).toLowerCase();
  const decisionCandidate = cleanText(
    source.decision?.decision || source.decision,
    40,
  ).toLowerCase();
  const decision = AI_TEACHING_DECISIONS.has(decisionCandidate)
    ? decisionCandidate
    : statusCandidate === "approved" ? "approve"
      : statusCandidate === "rejected" ? "reject" : "";
  const status = AI_TEACHING_STATUSES.has(statusCandidate)
    ? statusCandidate
    : decision === "approve" ? "approved"
      : decision === "reject" ? "rejected" : "pending";
  return {
    id,
    version,
    hash,
    signalKey: cleanText(
      source.signal_key || source.signalKey || source.key,
      180,
    ),
    title: cleanText(source.title || source.label, 240),
    context: cleanText(source.context || source.example, 1200),
    rationale: cleanText(
      source.rationale || source.explanation || source.ai_reason || source.aiReason,
      1200,
    ),
    impact: cleanText(source.impact || source.rule_effect, 800),
    aiJudgement: ["good", "bad", "unknown"].includes(judgementCandidate)
      ? judgementCandidate
      : "unknown",
    status,
    decision,
    evidenceCount: nonNegativeInteger(
      source.evidence_count ?? source.evidenceCount,
      0,
    ),
    decidedBy: cleanText(
      source.decided_by || source.decidedBy || source.actor?.name,
      180,
    ),
    decidedAt: timestamp(
      source.decided_at || source.decidedAt || source.decision?.decided_at,
    ),
    reason: cleanText(source.reason || source.decision?.reason, 800),
  };
}

function normalizeActivity(raw, index) {
  const source = objectValue(raw);
  if (!source) return null;
  const type = safeKey(source.type || source.event_type || source.eventType, 100)
    || "update";
  return {
    id: cleanText(source.id || source.event_id || source.eventId, 200)
      || `event-${index + 1}`,
    type,
    tone: activityTone(type),
    title: cleanText(source.title || source.label, 240) || activityTitle(type),
    description: cleanText(
      source.description || source.message || source.reason,
      1000,
    ),
    actor: cleanText(
      source.actor?.name || source.actor_name || source.actorName
        || source.created_by_name,
      180,
    ),
    createdAt: timestamp(
      source.created_at || source.createdAt || source.occurred_at
        || source.occurredAt,
    ),
    stateVersion: nonNegativeInteger(
      source.state_version ?? source.stateVersion,
      0,
    ),
  };
}

function normalizePolicy(raw) {
  const source = objectValue(raw) || {};
  const rawRules = arrayFrom(source.rules || source.items);
  const rules = rawRules.map((item, index) => {
    const rule = objectValue(item);
    if (!rule) return null;
    return {
      id: cleanText(rule.id || rule.key || rule.signal_key || rule.signalKey, 180)
        || `rule-${index + 1}`,
      label: cleanText(rule.label || rule.title || rule.key, 300)
        || `Правило ${index + 1}`,
      effect: cleanText(
        rule.effect || rule.description || rule.value,
        800,
      ),
    };
  }).filter(Boolean).slice(0, 50);
  const statusCandidate = cleanText(source.status, 40).toLowerCase();
  return {
    version: cleanText(source.version || source.policy_version || source.policyVersion, 120),
    hash: cleanText(source.hash || source.policy_hash || source.policyHash, 240),
    status: ["active", "draft", "paused", "superseded", "none"]
      .includes(statusCandidate) ? statusCandidate : rules.length ? "active" : "none",
    updatedAt: timestamp(source.updated_at || source.updatedAt),
    rules,
  };
}

function normalizeActor(raw) {
  const source = objectValue(raw) || {};
  return {
    id: cleanText(source.id || source.actor_id || source.actorId, 180),
    name: cleanText(source.name || source.display_name || source.displayName, 180),
    role: cleanText(source.role, 80).toLowerCase(),
  };
}

function normalizeCapabilities(raw, actor) {
  const source = objectValue(raw) || {};
  const administrator = ["owner", "admin"].includes(actor.role);
  const broadWrite = capability(source, ["write", "can_write", "canWrite"], administrator);
  return {
    canRead: capability(source, ["read", "can_read", "canRead"], true),
    canAddLink: capability(
      source,
      ["add_link", "can_add_link", "canAddLink", "add_sources", "canAddSources", "can_register_source", "canRegisterSource"],
      broadWrite,
    ),
    canUploadFile: capability(
      source,
      ["upload_file", "can_upload_file", "canUploadFile", "add_sources", "canAddSources", "can_register_source", "canRegisterSource"],
      broadWrite,
    ),
    canDecide: capability(
      source,
      ["decide", "can_decide", "canDecide", "teach", "can_teach", "canTeach", "can_decide_teaching_card", "canDecideTeachingCard"],
      broadWrite,
    ),
    canViewHistory: capability(
      source,
      ["view_history", "can_view_history", "canViewHistory"],
      true,
    ),
  };
}

function normalizeGuidance(raw, category) {
  const source = objectValue(raw) || {};
  return {
    status: cleanText(source.status, 80).toLowerCase() || category.status,
    summary: cleanText(source.summary || source.message, 800),
    scoreIsNotModelIq: source.score_is_not_model_iq !== false,
    rawSourcesEnterPromptAutomatically:
      source.raw_sources_enter_prompt_automatically === true,
  };
}

function normalizedSnapshot(value) {
  if (
    objectValue(value)
    && value.version === AI_LEARNING_CONTROL_ROOM_VERSION
    && Array.isArray(value.categories)
    && objectValue(value.category)
    && Number.isSafeInteger(value.stateVersion)
    && Number.isSafeInteger(value.eventCursor)
  ) return value;
  return normalizeAiLearningControlRoom(value);
}

function envelopeSource(value) {
  let source = objectValue(value) || {};
  for (let depth = 0; depth < 4; depth += 1) {
    const nested = objectValue(source.control_room)
      || objectValue(source.controlRoom)
      || objectValue(source.snapshot)
      || objectValue(source.ai_learning)
      || objectValue(source.aiLearning);
    if (nested) {
      source = nested;
      continue;
    }
    const data = objectValue(source.data);
    if (data && (
      data.version || data.schema_version || data.categories
      || data.category_detail || data.control_room || data.snapshot
    )) {
      source = data;
      continue;
    }
    break;
  }
  return source;
}

function categoryKeyFrom(value) {
  const source = objectValue(value);
  if (!source) return "";
  return cleanText(
    source.key || source.slug || source.product_category || source.productCategory
      || source.category_key || source.categoryKey,
    80,
  ).toLowerCase();
}

function statusMeta(value, score, available = true) {
  const status = normalizeStatus(value, score, available);
  return STATUS_META[status] || STATUS_META.unknown;
}

function normalizeStatus(value, score, available = true) {
  const candidate = cleanText(value, 80).toLowerCase();
  const aliases = {
    ready: "strong_evidence",
    strong: "strong_evidence",
    developing: "developing_evidence",
    insufficient: "insufficient_evidence",
    weak: "insufficient_evidence",
    empty: "cold_start",
    queued: "processing",
    running: "processing",
  };
  const normalized = aliases[candidate] || candidate;
  if (AI_LEARNING_STATUSES.has(normalized)) return normalized;
  if (!available) return "unknown";
  if (score >= 80) return "strong_evidence";
  if (score >= 50) return "developing_evidence";
  return score > 0 ? "insufficient_evidence" : "cold_start";
}

function normalizeConfidence(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    const percent = value >= 0 && value <= 1 && !Number.isInteger(value)
      ? Math.round(value * 100)
      : clampScore(value);
    return { value, percent };
  }
  const candidate = cleanText(value, 40).toLowerCase();
  if (/^\d+(?:\.\d+)?%?$/u.test(candidate)) {
    const number = Number(candidate.replace("%", ""));
    return { value: Number.isFinite(number) ? number : "unknown", percent: clampScore(number) };
  }
  const percent = ({ low: 30, medium: 60, high: 85 })[candidate] ?? null;
  return { value: ["low", "medium", "high"].includes(candidate) ? candidate : "unknown", percent };
}

function confidenceText(category) {
  const value = category.confidence;
  if (typeof category.confidencePercent === "number") {
    return {
      value: `${category.confidencePercent}%`,
      note: "уверенность по собранным доказательствам",
    };
  }
  const label = ({ low: "Низкая", medium: "Средняя", high: "Высокая" })[value];
  return {
    value: label || "—",
    note: "не является accuracy модели",
  };
}

function sourceKindLabel(value) {
  return ({
    file: "Файл",
    link: "Ссылка",
    marketplace: "Маркетплейс",
    document: "Документ",
    image: "Изображение",
    video: "Видео",
  })[value] || "Источник";
}

function sourceStatusLabel(value) {
  return ({
    queued: "В очереди",
    processing: "Разбирается",
    active: "Зарегистрирован",
    verified: "Проверен",
    rejected: "Исключён",
    failed: "Ошибка",
  })[value] || "Статус неизвестен";
}

function policyStatusLabel(value) {
  return ({
    active: "Активная серверная политика",
    draft: "Черновик — ещё не влияет",
    paused: "Политика приостановлена",
    superseded: "Версия заменена новой",
    none: "Политика ещё не выпущена",
  })[value] || "Статус политики неизвестен";
}

function activityTitle(type) {
  if (type.includes("decision")) return "Решение человека";
  if (type.includes("source") || type.includes("ingestion")) return "Изменение источника";
  if (type.includes("policy") || type.includes("rule")) return "Новая версия правил";
  return "Обновление категории";
}

function activityTone(type) {
  if (type.includes("reject") || type.includes("fail")) return "bad";
  if (type.includes("approve") || type.includes("verified")) return "good";
  if (type.includes("policy") || type.includes("rule")) return "policy";
  return "neutral";
}

function capability(source, keys, fallback) {
  for (const key of keys) {
    if (typeof source[key] === "boolean") return source[key];
  }
  return Boolean(fallback);
}

function safeHttpUrl(value) {
  const candidate = cleanText(value, 2_000);
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate);
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
  } catch {
    return "";
  }
}

function urlHost(value) {
  try {
    return new URL(value).hostname.replace(/^www\./u, "");
  } catch {
    return "";
  }
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Moscow",
    }).format(date);
  } catch {
    return date.toISOString();
  }
}

function timestamp(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

function shortHash(value) {
  const candidate = cleanText(value, 240);
  if (!candidate) return "—";
  return candidate.length > 14 ? `${candidate.slice(0, 12)}…` : candidate;
}

function safeKey(value, limit = 100) {
  const candidate = cleanText(value, limit).toLowerCase();
  return /^[a-z][a-z0-9_.-]*$/u.test(candidate) ? candidate : "";
}

function humanizeKey(value) {
  const candidate = cleanText(value, 120).replace(/[_.-]+/gu, " ");
  return candidate ? candidate.charAt(0).toUpperCase() + candidate.slice(1) : "Метрика";
}

function cleanText(value, limit = 500) {
  return String(value ?? "")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, limit);
}

function arrayFrom(value) {
  return Array.isArray(value) ? value : [];
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function exactObjectKeys(value, keys) {
  const source = objectValue(value);
  if (!source) return false;
  const actual = Object.keys(source).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length
    && actual.every((key, index) => key === expected[index]);
}

function exactUuid(value) {
  const candidate = cleanText(value, 80).toLowerCase();
  return AI_MARKET_SCOPE_UUID.test(candidate) ? candidate : "";
}

function clampScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function nonNegativeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : fallback;
}

function nonNegativeInteger(value, fallback = 0) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : fallback;
}

function strictNonNegativeInteger(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function positiveInteger(value, fallback = 1) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
