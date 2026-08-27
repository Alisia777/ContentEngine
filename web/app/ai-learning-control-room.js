const AI_LEARNING_CONTROL_ROOM_VERSION = "ai-learning-control-room-v1";
const AI_LEARNING_HUMAN_REVIEW_VISUAL_URL = new URL(
  "./assets/content-factory-ai-center-human-review-v1.png",
  import.meta.url,
).href;
const AI_MARKET_SCOPE_INDEX_VERSION = "ai-learning-market-scope-index-v2";
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
const AI_LEARNING_VIEWS = new Set(["overview", "knowledge", "teach", "cases", "history"]);
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
const AI_HISTORICAL_CASE_FILTERS = new Set(["all", "good", "bad", "review"]);
const AI_HISTORICAL_CASE_OUTCOMES = new Set(["good", "bad", "review"]);
const AI_HISTORICAL_CASE_REVIEW_STATUSES = new Set([
  "pending",
  "confirmed",
  "rejected",
]);
const AI_HISTORICAL_CASE_BINDING_STATUSES = new Set([
  "direct_product_id",
  "late_unique_product_sku",
  "late_unique_marketplace_sku",
  "missing_exact_binding",
]);
const AI_HISTORICAL_BATCH_STATUSES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
]);
const AI_RESEARCH_INBOX_STATUSES = new Set(["awaiting_human_review"]);
const AI_RESEARCH_DECISIONS = new Set(["approve", "reject"]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;

const CREATIVE_ANGLE_LABELS = Object.freeze({
  product_focus: "Товар — главный объект",
  trust_builder: "Проверяемое доверие",
  demonstration: "Показ товара в действии",
  comparison: "Сравнение вариантов",
  objection_handling: "Ответ на возражение",
  curiosity_gap: "Интрига без ложных обещаний",
});

const GUIDANCE_ACTION_LABELS = Object.freeze({
  add_category_source: "Добавить проверяемый источник",
  add_reviewable_source: "Добавить проверяемый источник",
  add_independent_platform: "Добавить данные с другой площадки",
  add_competitor_observation: "Добавить наблюдение о конкуренте",
  refresh_trend_evidence: "Обновить данные о трендах",
  analyze_source: "Разобрать добавленный источник",
  validate_evidence: "Подтвердить данные командой",
});

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

/** Builds the exact one-shot route for a clean research form. */
export function aiLearningFreshResearchHref(projectId, category) {
  const exactProjectId = exactUuid(projectId);
  const exactCategory = cleanText(category, 80).toLowerCase();
  if (!exactProjectId || !AI_CATEGORY_BY_KEY.has(exactCategory)) return "";
  const params = new URLSearchParams({
    project_id: exactProjectId,
    category: exactCategory,
    new: "1",
  });
  return `#/workspace/research?${params.toString()}`;
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
    projectId: "",
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
    "project_id",
    "metric_kind",
    "as_of",
    "scopes",
    "limits",
  ])) return unavailable();
  const organizationId = exactUuid(source.organization_id);
  const projectId = exactUuid(source.project_id);
  const asOf = timestamp(source.as_of);
  const limits = objectValue(source.limits);
  if (
    source.ok !== true
    || source.version !== AI_MARKET_SCOPE_INDEX_VERSION
    || !organizationId
    || !projectId
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
      "project_id",
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
    const scopeProjectId = exactUuid(scope.project_id);
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
      || !scopeProjectId
      || scopeProjectId !== projectId
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
      projectId: scopeProjectId,
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
    projectId,
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
  const requiresProject = options.requiresProject === true;
  const detailMarkup = selected ? String(options.detailMarkup || "") : "";
  const researchCategory = cleanText(options.researchCategory, 80).toLowerCase();
  const researchCategoryLabel = AI_CATEGORY_BY_KEY.get(researchCategory)?.label || "";
  const freshResearchHref = aiLearningFreshResearchHref(
    control.projectId,
    researchCategory,
  );
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
  const content = requiresProject
    ? `<div class="ai-market-learning-empty" role="status"><strong>Выберите проект для рыночного обучения</strong><p>Процент, источники и правила категории считаются только внутри точного проекта. Глобальный ИИ‑центр остаётся доступен, но проектные данные не смешиваются.</p><a class="btn btn-secondary btn-small" href="#/workspace/home">Выбрать проект</a></div>`
    : !control.available
    ? `<div class="ai-market-learning-empty" role="status"><strong>Динамические категории временно недоступны</strong><p>Процент скрыт: сервер не подтвердил точный UUID scope или readiness v3. Legacy‑оценка не подставляется.</p></div>`
    : !selected && control.scopes.length
      ? `<div class="ai-market-learning-layout">
          <aside class="ai-market-scope-selector" aria-label="Категория и товар">${selectorMarkup}</aside>
          <div class="ai-market-learning-detail"><div class="ai-market-learning-empty" role="status"><strong>Выберите актуальный product context</strong><p>UUID из ссылки устарел или больше недоступен. Доступные категории показаны слева; ни одна из них не выбрана автоматически.</p></div></div>
        </div>`
      : !selected
      ? `<div class="ai-market-learning-empty"><strong>Для текущего товара ещё нет подтверждённого исследования${researchCategoryLabel ? ` категории «${escapeHtml(researchCategoryLabel)}»` : ""}</strong><p>Архивные кейсы ниже относятся ко всей организации и не являются знаниями об этом товаре. Начните новый разбор: форма откроется без SKU, фото и выводов прошлого товара.</p>${freshResearchHref ? `<a class="btn btn-secondary btn-small" href="${escapeHtml(freshResearchHref)}">Начать новый разбор без старых данных</a>` : `<span class="ai-learning-capability-note">Обновите проект и выберите точную категорию перед новым разбором.</span>`}</div>`
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
      <span class="ai-learning-status-pill is-${selected?.guidance.status === "strong_evidence" ? "strong" : selected?.guidance.status === "developing_evidence" ? "developing" : "insufficient"}">${selected ? `${selected.score}% evidence` : requiresProject ? "нужен проект" : "нет scope"}</span>
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

/** Keeps the case filter URL/state-independent and constrained to known tabs. */
export function aiHistoricalCaseFilter(value) {
  const candidate = cleanText(value, 20).toLowerCase();
  return AI_HISTORICAL_CASE_FILTERS.has(candidate) ? candidate : "all";
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
  const researchInbox = available
    ? normalizeResearchInbox(
      source.research_inbox || source.researchInbox
        || rawDetail?.research_inbox || rawDetail?.researchInbox,
      selectedCategory,
    )
    : [];
  const researchDecisions = available
    ? normalizeResearchDecisions(
      source.research_decisions || source.researchDecisions
        || rawDetail?.research_decisions || rawDetail?.researchDecisions,
      selectedCategory,
    )
    : [];

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
    researchInbox,
    researchDecisions,
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
  const busyHistoricalCaseId = cleanText(options.busyHistoricalCaseId, 200);
  const busyResearchReceiptId = cleanText(options.busyResearchReceiptId, 200);
  const historicalCaseFilter = aiHistoricalCaseFilter(options.historicalCaseFilter);
  const busy = Boolean(
    options.busy || options.saving || options.loading || options.refreshing
      || busyCardId || busyHistoricalCaseId || busyResearchReceiptId,
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
  const canDecideHistoricalCase = control.available
    && control.capabilities.canDecideHistoricalCase
    && !busy;
  const canDecideResearchInbox = control.available
    && control.capabilities.canDecideResearchInbox
    && !busy && !legacyReadOnly;
  const updatedLabel = formatDateTime(options.lastUpdatedAt || control.asOf);
  const researchInbox = arrayFrom(control.researchInbox).filter(
    (item) => item.productCategory === selectedCategory,
  );
  const researchDecisions = arrayFrom(control.researchDecisions).filter(
    (item) => item.productCategory === selectedCategory,
  );
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
          <p class="ai-learning-eyebrow">Обучение ИИ по категориям</p>
          <h1 id="ai-learning-title">Что ИИ знает и чему его научить</h1>
          <p>Здесь видно, что можно использовать, чего нужно избегать и где данных пока мало.</p>
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
    ${researchInboxMarkup(
      researchInbox,
      researchDecisions,
      selectedCategory,
      control,
      { canDecideResearchInbox, busy, busyResearchReceiptId },
    )}

    <!-- Выбор и действия — первым экраном (решение владельца 27.08.2026):
         сначала «что отбирать» (категория) и «что сделать» (вкладки),
         большой блок рыночного разбора уходит ниже панелей. -->
    <div class="ai-learning-category-strip" role="group" aria-label="Категории обучения">
      ${control.categories.map((item) => categoryButtonMarkup(item, selectedCategory, busy)).join("")}
    </div>

    <div class="ai-learning-view-tabs" role="tablist" aria-label="Разделы командного пункта">
      ${viewTabMarkup("overview", "Обзор", view)}
      ${viewTabMarkup("knowledge", "База знаний", view)}
      ${viewTabMarkup("teach", "Обучить", view, category.pendingTeachingCount)}
      ${viewTabMarkup("cases", "Кейсы", view, category.pendingHistoricalCaseCount)}
      ${viewTabMarkup("history", "История", view)}
    </div>

    <div class="ai-learning-view-panel" id="ai-learning-panel-overview" role="tabpanel" aria-labelledby="ai-learning-tab-overview" ${view === "overview" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-overview">
      ${view === "overview" ? overviewMarkup(category, control, status, legacyReadOnly) : ""}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-knowledge" role="tabpanel" aria-labelledby="ai-learning-tab-knowledge" ${view === "knowledge" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-knowledge">
      ${view === "knowledge" ? knowledgeMarkup(category, control, { canAddLink, canUploadFile, busy }) : ""}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-teach" role="tabpanel" aria-labelledby="ai-learning-tab-teach" ${view === "teach" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-teach">
      ${view === "teach" ? teachMarkup(category, control, {
        canDecide,
        legacyReadOnly,
        busy,
        busyCardId,
      }) : ""}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-cases" role="tabpanel" aria-labelledby="ai-learning-tab-cases" ${view === "cases" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-cases">
      ${view === "cases" ? historicalCasesMarkup(category, control, {
        canDecideHistoricalCase,
        busy,
        busyHistoricalCaseId,
        filter: historicalCaseFilter,
        historicalImport: options.historicalImport,
      }) : ""}
    </div>
    <div class="ai-learning-view-panel" id="ai-learning-panel-history" role="tabpanel" aria-labelledby="ai-learning-tab-history" ${view === "history" ? "" : "hidden"} data-ce-patch-key="ai-learning-panel-history">
      ${view === "history" ? historyMarkup(category, control, legacyReadOnly) : ""}
    </div>

    ${marketLearningMarkup}

    ${legacyReadOnly ? `<aside class="ai-learning-legacy-boundary" role="note">
      <strong>Legacy safety bucket · только история</strong>
      <span>Восемь старых product_category сохранены для совместимости и аудита. Их registrations и teaching cards не считаются анализом и больше не меняют платную генерацию. Исторические кейсы можно пометить «Верно» или «Не учить», но даже подтверждённый кейс применяется только после точной связи с товаром и evidence-порога. Для новых решений используйте точную market category выше.</span>
    </aside>` : ""}
  </section>`;
}

function researchInboxMarkup(
  items,
  decisions,
  productCategory,
  control,
  { canDecideResearchInbox, busy, busyResearchReceiptId },
) {
  if (!items.length && !decisions.length) return "";
  const title = items.length === 1
    ? "1 исследование ждёт вашей проверки"
    : items.length > 1
      ? `${items.length} исследований ждут вашей проверки`
      : "Очередь исследований разобрана";
  const pendingMarkup = items.length
    ? `<div class="ai-learning-source-list">
      ${items.map((item) => {
        const itemBusy = busyResearchReceiptId === item.id;
        const disabled = busy || itemBusy || !canDecideResearchInbox;
        return `<article class="ai-learning-source is-active" data-research-receipt-id="${escapeHtml(item.id)}" data-ce-patch-key="ai-research-receipt-${escapeHtml(item.id)}">
          <div class="ai-learning-source-kind" aria-hidden="true">↳</div>
          <div class="ai-learning-source-copy">
            <div><span>Исследование</span><span class="ai-learning-source-status">Ждёт решения человека</span></div>
            <h3>${escapeHtml(item.title || item.productName || "Новое исследование")}</h3>
            <p>${escapeHtml([item.projectName, item.productName].filter(Boolean).join(" · ") || "Откройте точный проект и результат")}</p>
            <small>${item.sourceCount} ${item.sourceCount === 1 ? "источник" : "источников"}${item.receivedAt ? ` · получено ${escapeHtml(formatDateTime(item.receivedAt))}` : ""}</small>
            <a href="${escapeHtml(item.deepLink)}">Открыть факты и источники <span aria-hidden="true">→</span></a>
            <small>Нажимая «Проверено — принять», вы подтверждаете, что открыли результат и сверили факты и источники. Это решение не создаёт правило ИИ.</small>
            <div class="ai-learning-decision-actions">
              <button class="is-primary is-good" type="button" data-primary-action="true" data-action="decide-ai-research-receipt" data-product-category="${escapeHtml(productCategory)}" data-receipt-id="${escapeHtml(item.id)}" data-receipt-hash="${escapeHtml(item.receiptHash)}" data-event-cursor="${item.eventCursor}" data-decision="approve" data-confirmation="true" ${disabled ? "disabled" : ""}>${itemBusy ? "Сохраняем…" : "Проверено — принять"}</button>
              <button class="is-secondary" type="button" data-action="decide-ai-research-receipt" data-product-category="${escapeHtml(productCategory)}" data-receipt-id="${escapeHtml(item.id)}" data-receipt-hash="${escapeHtml(item.receiptHash)}" data-event-cursor="${item.eventCursor}" data-decision="reject" data-confirmation="true" ${disabled ? "disabled" : ""}>${itemBusy ? "Сохраняем…" : "Не использовать"}</button>
            </div>
            ${capabilityHint(control.capabilities.canDecideResearchInbox, "разбирать входящие исследования")}
          </div>
        </article>`;
      }).join("")}
    </div>`
    : `<div class="ai-learning-recorded-decision is-good" role="status"><strong>Новых исследований для решения нет</strong><span>Последние решения сохранены в журнале ниже.</span></div>`;
  const historyMarkup = decisions.length
    ? `<div class="ai-learning-research-decision-history" aria-label="Последние решения по исследованиям">
      <div class="ai-learning-section-heading"><div><p class="ai-learning-eyebrow">Сохранённые решения</p><h3>Что уже разобрано</h3></div><span>${decisions.length}</span></div>
      <div class="ai-learning-source-list">
        ${decisions.map((item) => `<article class="ai-learning-source" data-ce-patch-key="ai-research-decision-${escapeHtml(item.id)}">
          <div class="ai-learning-source-kind" aria-hidden="true">${item.decision === "approve" ? "✓" : "×"}</div>
          <div class="ai-learning-source-copy">
            <div><span>Решение человека</span><span class="ai-learning-source-status">${item.decision === "approve" ? "Проверено и принято" : "Исключено"}</span></div>
            <h3>${escapeHtml(item.title || item.productName || "Исследование")}</h3>
            <p>${escapeHtml([item.projectName, item.productName].filter(Boolean).join(" · ") || "Решение сохранено")}</p>
            <small>${item.decidedByName ? `${escapeHtml(item.decidedByName)} · ` : ""}${escapeHtml(formatDateTime(item.decidedAt) || "время решения не указано")}</small>
            <a href="${escapeHtml(item.deepLink)}">Открыть сохранённое исследование <span aria-hidden="true">→</span></a>
          </div>
        </article>`).join("")}
      </div>
    </div>`
    : "";
  return `<section class="ai-learning-signal-summary ai-learning-research-inbox" aria-labelledby="ai-learning-research-inbox-title" data-ce-patch-key="ai-research-inbox-${escapeHtml(productCategory)}-${items.length}-${items[0]?.eventCursor || 0}-${decisions[0]?.eventCursor || 0}">
    <div class="ai-learning-signal-summary__heading">
      <div><p class="ai-learning-eyebrow">Входящие из исследований</p><h2 id="ai-learning-research-inbox-title">${escapeHtml(title)}</h2><p>«Принять» закрывает входящее как проверенное человеком, «Не использовать» исключает его. Оба решения сохраняются в истории, но сами по себе не обучают ИИ, не копируют сырой анализ в промпт и не меняют правила генерации.</p></div>
    </div>
    ${pendingMarkup}
    ${historyMarkup}
  </section>`;
}

function creativeAngleKey(value) {
  const candidate = cleanText(value, 800).toLowerCase();
  const exact = candidate.split(".").at(-1) || "";
  if (Object.hasOwn(CREATIVE_ANGLE_LABELS, exact)) return exact;
  return Object.keys(CREATIVE_ANGLE_LABELS).find((key) => (
    candidate.includes(key)
  )) || "";
}

function creativeAngleLabel(value) {
  const key = creativeAngleKey(value);
  return key ? CREATIVE_ANGLE_LABELS[key] : "Сигнал ещё не распознан";
}

function effectivePolicyRule(policy, id) {
  return policy.rules.find((rule) => rule.id === id) || null;
}

/**
 * Read-only explanation of the recommendation boundary.  Every value shown
 * here already belongs to the normalized authoritative snapshot; this view
 * deliberately exposes no form, data-action or generation control.
 */
function recommendationJourneyMarkup(category, control, legacyReadOnly = false) {
  const pendingCard = category.teachingCards.find((card) => card.status === "pending") || null;
  const approvedCard = category.teachingCards.find((card) => card.status === "approved") || null;
  const rejectedCard = category.teachingCards.find((card) => card.status === "rejected") || null;
  const candidate = pendingCard || approvedCard || rejectedCard;
  const preferred = effectivePolicyRule(category.effectivePolicy, "preferred_angle");
  const avoided = effectivePolicyRule(category.effectivePolicy, "avoid_angle");
  const policyFallback = preferred || avoided;
  const candidateAngle = candidate
    ? creativeAngleLabel(candidate.signalKey)
    : policyFallback
      ? creativeAngleLabel(policyFallback.effect)
      : "Нужно больше доказательств";
  const candidateTitle = candidate?.title && candidate.title !== candidateAngle
    ? candidate.title
    : candidateAngle;
  const candidateMode = candidate?.aiJudgement === "bad" || (!candidate && avoided && !preferred)
    ? "Предложение: избегать"
    : candidate?.aiJudgement === "unknown" || (!candidate && !policyFallback)
      ? "Нужна ручная оценка"
      : "Предложение: использовать";
  const candidateTone = candidate?.aiJudgement === "bad" || (!candidate && avoided && !preferred)
    ? "avoid"
    : candidate?.aiJudgement === "unknown" || (!candidate && !policyFallback)
      ? "unknown"
      : "use";
  const rationale = candidate?.rationale
    || control.guidance?.summary
    || (policyFallback
      ? "Показано правило из последней выпущенной сервером политики категории."
      : "Серверный снимок пока не содержит кандидата правила для этой категории.");
  const confidence = confidenceText(category);
  const confidencePercent = typeof category.confidencePercent === "number"
    ? category.confidencePercent
    : 0;
  const source = category.sources.find((item) => item.status === "verified")
    || category.sources.find((item) => item.status === "active")
    || category.sources[0]
    || null;
  const sourceTitle = source?.title || source?.originalFilename
    || "Серверный снимок категории";
  const sourceDetail = source
    ? source.provenance || source.host || sourceKindLabel(source.kind)
    : category.evidenceHash
      ? `Evidence ${shortHash(category.evidenceHash)}`
      : "Происхождение появится вместе с первым проверяемым источником";
  const sourceStamp = formatDateTime(source?.verifiedAt || source?.addedAt || control.asOf)
    || "время не указано";
  const evidenceIdentity = category.evidenceHash
    ? `Evidence ${shortHash(category.evidenceHash)}`
    : `State ${control.stateVersion}`;
  const modeValue = candidateTone === "avoid"
    ? "Исключить приём"
    : candidateTone === "use" ? "Предпочесть приём" : "Не применять";
  const policyVersion = cleanText(category.effectivePolicy.version, 120);
  const policyValue = policyVersion
    ? `Policy ${/^v\d/iu.test(policyVersion)
      ? policyVersion
      : /^\d/iu.test(policyVersion) ? `v${policyVersion}` : policyVersion}`
    : "Вне active policy";

  let decisionTone = "locked";
  let decisionTitle = "Подтверждение недоступно";
  let decisionCopy = "Сначала нужен проверяемый кандидат. ИИ ничего не применит сам.";
  let decisionBadge = "Нет кандидата";
  if (legacyReadOnly) {
    decisionTone = "archive";
    decisionTitle = "Архивный снимок";
    decisionCopy = "Legacy-данные доступны только для чтения и не меняют финальные параметры.";
    decisionBadge = "Audit-only";
  } else if (pendingCard) {
    decisionTone = "pending";
    decisionTitle = "Ожидает подтверждения";
    decisionCopy = "До явного решения человека кандидат не входит в effective policy и не влияет на генерацию.";
    decisionBadge = "Решает человек";
  } else if (approvedCard) {
    decisionTone = "confirmed";
    decisionTitle = "Подтверждено человеком";
    decisionCopy = "Решение сохранено в журнале. Применяемым оно становится только в выпущенной сервером версии policy.";
    decisionBadge = approvedCard.decidedBy || "Решение записано";
  } else if (rejectedCard) {
    decisionTone = "rejected";
    decisionTitle = "Отклонено человеком";
    decisionCopy = "Кандидат сохранён в истории, но не используется как правило и не меняет параметры результата.";
    decisionBadge = rejectedCard.decidedBy || "Не применять";
  } else if (category.effectivePolicy.status === "active" && category.effectivePolicy.rules.length) {
    decisionTone = "confirmed";
    decisionTitle = "Выпущено после проверки";
    decisionCopy = "На экране только чтение: active policy пришла из authoritative-снимка после человеческого решения.";
    decisionBadge = policyValue;
  }

  return `<section class="ai-learning-decision-journey" data-ai-recommendation-journey data-authority="human-final" data-snapshot-mode="read-only" aria-labelledby="ai-learning-decision-journey-title">
    <header class="ai-learning-decision-journey__header">
      <div>
        <p class="ai-learning-eyebrow">Рекомендация под контролем человека</p>
        <h2 id="ai-learning-decision-journey-title">Как предложение становится решением</h2>
        <p>ИИ показывает аргументы и параметры. Человек может поправить рабочий черновик и только потом отдельно подтвердить его.</p>
      </div>
      <span class="ai-learning-decision-journey__readonly"><i aria-hidden="true"></i> Read-only snapshot</span>
    </header>

    <div class="ai-learning-decision-journey__scene" data-ai-recommendation-art aria-hidden="true">
      <img src="${escapeHtml(AI_LEARNING_HUMAN_REVIEW_VISUAL_URL)}" alt="" width="1672" height="941" loading="lazy" decoding="async" />
      <div class="ai-learning-decision-journey__scene-flow">
        <span><i>01</i>ИИ предлагает</span>
        <b></b>
        <span><i>02</i>Человек проверяет</span>
        <b></b>
        <span><i>03</i>Решение фиксируется</span>
      </div>
    </div>

    <div class="ai-learning-decision-journey__flow" role="list" aria-label="ИИ рекомендует, человек правит, человек подтверждает">
      <article class="ai-learning-journey-card is-ai is-${candidateTone}" role="listitem">
        <div class="ai-learning-journey-card__topline"><span>01</span><small>ИИ-центр рекомендует</small></div>
        <div class="ai-learning-journey-visual is-ai" aria-hidden="true">
          <svg viewBox="0 0 220 108" focusable="false">
            <defs><linearGradient id="ai-journey-pulse" x1="0" x2="1"><stop stop-color="#52dce6"/><stop offset="1" stop-color="#ae83ff"/></linearGradient></defs>
            <path class="ai-learning-journey-network" d="M18 70 58 33l44 28 48-38 52 34"/>
            <path class="ai-learning-journey-network is-soft" d="M18 70 70 88l32-27 48 18 52-22"/>
            <g class="ai-learning-journey-nodes"><circle cx="18" cy="70" r="5"/><circle cx="58" cy="33" r="7"/><circle cx="102" cy="61" r="9"/><circle cx="150" cy="23" r="6"/><circle cx="202" cy="57" r="8"/></g>
            <circle class="ai-learning-journey-core" cx="102" cy="61" r="18"/>
            <path class="ai-learning-journey-spark" d="m102 48 4 9 9 4-9 4-4 9-4-9-9-4 9-4Z"/>
          </svg>
          <span class="ai-learning-journey-mode is-${candidateTone}">${escapeHtml(candidateMode)}</span>
        </div>
        <div class="ai-learning-journey-card__copy">
          <h3>${escapeHtml(candidateTitle)}</h3>
          <p>${escapeHtml(rationale)}</p>
        </div>
        <div class="ai-learning-confidence" style="--ai-confidence:${confidencePercent}" aria-label="Уверенность по доказательствам: ${escapeHtml(confidence.value)}">
          <span><b>Confidence</b><strong>${escapeHtml(confidence.value)}</strong></span>
          <i aria-hidden="true"><i></i></i>
          <small>${escapeHtml(confidence.note)}</small>
        </div>
        <div class="ai-learning-provenance" aria-label="Контекст происхождения доказательств категории">
          <span class="ai-learning-provenance__glyph" aria-hidden="true">⌁</span>
          <div><small>Provenance контекста · ${escapeHtml(sourceStamp)}</small><strong>${escapeHtml(sourceTitle)}</strong><span>${escapeHtml(sourceDetail)}</span></div>
          <em>${escapeHtml(evidenceIdentity)}</em>
        </div>
      </article>

      <div class="ai-learning-journey-connector" aria-hidden="true"><i></i><span>человек</span></div>

      <article class="ai-learning-journey-card is-edit" role="listitem">
        <div class="ai-learning-journey-card__topline"><span>02</span><small>Человек правит</small></div>
        <div class="ai-learning-journey-visual is-edit" aria-hidden="true">
          <svg viewBox="0 0 220 108" focusable="false">
            <rect x="23" y="18" width="174" height="72" rx="14"/>
            <path d="M46 39h84M46 55h112M46 71h66"/>
            <circle cx="151" cy="39" r="8"/><circle cx="93" cy="55" r="8"/><circle cx="139" cy="71" r="8"/>
            <path class="ai-learning-journey-pencil" d="m169 70 25-25 9 9-25 25-13 4Z"/>
          </svg>
          <span>Рабочий черновик · не применён</span>
        </div>
        <div class="ai-learning-journey-card__copy">
          <h3>Параметры видны до решения</h3>
          <p>Это визуальная копия snapshot. Правки выполняются человеком в отдельной форме стратегии и не переписываются рекомендацией.</p>
        </div>
        <dl class="ai-learning-journey-parameters">
          <div><dt>Категория</dt><dd>${escapeHtml(category.label)}</dd></div>
          <div><dt>Творческий приём</dt><dd>${escapeHtml(candidateAngle)}</dd></div>
          <div><dt>Режим</dt><dd>${escapeHtml(modeValue)}</dd></div>
          <div><dt>Контур</dt><dd>${escapeHtml(policyValue)}</dd></div>
        </dl>
        <div class="ai-learning-human-note"><span aria-hidden="true">✎</span><p><strong>Правки принадлежат человеку</strong><small>ИИ может обновить рекомендацию, но не финальные значения формы.</small></p></div>
      </article>

      <div class="ai-learning-journey-connector" aria-hidden="true"><i></i><span>явное решение</span></div>

      <article class="ai-learning-journey-card is-confirm is-${decisionTone}" role="listitem">
        <div class="ai-learning-journey-card__topline"><span>03</span><small>Человек подтверждает</small></div>
        <div class="ai-learning-journey-visual is-confirm" aria-hidden="true">
          <svg viewBox="0 0 220 108" focusable="false">
            <circle class="ai-learning-confirm-orbit is-one" cx="110" cy="54" r="40"/>
            <circle class="ai-learning-confirm-orbit is-two" cx="110" cy="54" r="28"/>
            <path class="ai-learning-confirm-shield" d="M110 27c13 8 24 8 24 8v17c0 15-10 25-24 31-14-6-24-16-24-31V35s11 0 24-8Z"/>
            <path class="ai-learning-confirm-check" d="m99 54 8 8 15-18"/>
          </svg>
          <span class="ai-learning-confirm-badge is-${decisionTone}">${escapeHtml(decisionBadge)}</span>
        </div>
        <div class="ai-learning-journey-card__copy">
          <h3>${escapeHtml(decisionTitle)}</h3>
          <p>${escapeHtml(decisionCopy)}</p>
        </div>
        <div class="ai-learning-confirm-ledger">
          <div><span aria-hidden="true">◇</span><p><strong>Источник решения</strong><small>${escapeHtml(control.actor.name || "Уполномоченный сотрудник")}</small></p></div>
          <div><span aria-hidden="true">#</span><p><strong>Версия snapshot</strong><small>State ${control.stateVersion} · cursor ${control.eventCursor}</small></p></div>
          <div><span aria-hidden="true">⌁</span><p><strong>Автоприменение</strong><small>Выключено</small></p></div>
        </div>
      </article>
    </div>

    <footer class="ai-learning-decision-journey__boundary" role="note">
      <span aria-hidden="true">⌾</span>
      <p><strong>Граница полномочий</strong><small>Этот блок ничего не запускает, не меняет effective policy и не записывает финальные параметры. Для изменения состояния требуется отдельное явное действие человека в соответствующем рабочем контуре.</small></p>
    </footer>
  </section>`;
}

function signalSummaryMarkup(category, control, status) {
  const preferred = effectivePolicyRule(category.effectivePolicy, "preferred_angle");
  const avoided = effectivePolicyRule(category.effectivePolicy, "avoid_angle");
  const dataIsInsufficient = ["insufficient_evidence", "cold_start", "unknown"].includes(category.status);
  const dataIsReady = category.status === "strong_evidence";
  const recommended = cleanText(control.guidance?.recommendedNextAction, 120).toLowerCase();
  const nextView = category.pendingTeachingCount > 0
    ? "teach"
    : category.pendingHistoricalCaseCount > 0
      ? "cases"
      : category.gaps.length > 0 ? "knowledge" : "history";
  const nextLabel = category.pendingTeachingCount > 0
    ? "Проверить следующий сигнал"
    : category.pendingHistoricalCaseCount > 0
      ? "Проверить исторический кейс"
      : category.gaps.length > 0
        ? GUIDANCE_ACTION_LABELS[recommended] || "Добавить недостающие данные"
        : "Посмотреть историю решений";
  const dataLabel = dataIsInsufficient
    ? "Данных недостаточно"
    : dataIsReady ? "Данных достаточно" : "Данные ещё собираются";
  const dataCopy = dataIsInsufficient
    ? "Новые выводы пока не применяются без решения человека."
    : status.label;
  return `<section class="ai-learning-signal-summary" aria-labelledby="ai-learning-signal-summary-title" data-ce-patch-key="ai-signal-summary-${escapeHtml(category.key)}-${escapeHtml(category.effectivePolicy.hash || "empty")}">
    <div class="ai-learning-signal-summary__heading">
      <div><p class="ai-learning-eyebrow">Только подтверждённые правила</p><h2 id="ai-learning-signal-summary-title">Что ИИ реально применяет</h2></div>
      <button type="button" data-action="select-ai-learning-view" data-view="${nextView}" data-primary-action="true">${escapeHtml(nextLabel)} →</button>
    </div>
    <div class="ai-learning-signal-state-grid">
      <article class="ai-learning-signal-state is-good"><span><b aria-hidden="true">✓</b> Можно использовать</span><strong>${preferred ? escapeHtml(creativeAngleLabel(preferred.effect)) : "Пока не подтверждено"}</strong><small>${preferred ? "Это правило уже учитывается ИИ." : "Правило не применяется без решения команды."}</small></article>
      <article class="ai-learning-signal-state is-bad"><span><b aria-hidden="true">×</b> Нужно избегать</span><strong>${avoided ? escapeHtml(creativeAngleLabel(avoided.effect)) : "Пока не подтверждено"}</strong><small>${avoided ? "ИИ исключает этот приём из результата." : "Запрета пока нет."}</small></article>
      <article class="ai-learning-signal-state is-${dataIsReady ? "ready" : "unknown"}"><span><b aria-hidden="true">!</b> ${dataLabel}</span><strong>${category.score}% готовности</strong><small>${escapeHtml(dataCopy)}</small></article>
    </div>
  </section>`;
}

function overviewMarkup(category, control, status, legacyReadOnly = false) {
  const confidence = confidenceText(category);
  return `${recommendationJourneyMarkup(category, control, legacyReadOnly)}
  ${signalSummaryMarkup(category, control, status)}
  <div class="ai-learning-overview-grid">
    <article class="ai-learning-readiness-card is-${status.tone}" data-ce-patch-key="ai-readiness-${category.key}">
      <div class="ai-learning-score-ring" style="--ai-learning-score:${category.score}" role="img" aria-label="${legacyReadOnly ? "Архивный legacy-показатель" : "Готовность доказательной базы категории"}: ${category.score} процентов">
        <strong>${category.score}%</strong>
        <span>данные</span>
      </div>
      <div class="ai-learning-readiness-copy">
        <p class="ai-learning-eyebrow">${escapeHtml(category.label)}</p>
        <h2>Насколько хватает данных</h2>
        <span class="ai-learning-status-pill is-${status.tone}">${escapeHtml(status.label)}</span>
        <p>Процент показывает только объём проверенных источников и решений команды. Это не оценка интеллекта и не гарантия результата.</p>
        <small>${control.asOf ? `Обновлено ${escapeHtml(formatDateTime(control.asOf))}` : "Ожидаем первый расчёт"}</small>
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
      <div><p class="ai-learning-eyebrow">Почему такая оценка</p><h2 id="ai-learning-dimensions-title">Из чего складывается готовность</h2></div>
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
      <div><p class="ai-learning-eyebrow">Следующий шаг</p><h2 id="ai-learning-gaps-title">Чего не хватает ИИ</h2></div>
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
      <label><span>Название</span><input type="text" name="source_title" minlength="2" maxlength="160" placeholder="Что содержит источник" required ${disabledLink} /></label>
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
      <label><span>Название</span><input type="text" name="source_title" minlength="2" maxlength="160" placeholder="Кратко о содержимом" required ${disabledFile} /></label>
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
        ? category.sources.map((source) => sourceMarkup(source, category, {
          canImportHistoricalCases: canUploadFile,
          busy,
        })).join("")
        : emptyMarkup("Источников пока нет", "Добавьте ссылку или файл: система зафиксирует происхождение и статус регистрации здесь.")}
    </div>
  </section>`;
}

function teachMarkup(category, control, {
  canDecide,
  legacyReadOnly = false,
  busy,
  busyCardId,
}) {
  const pendingCards = category.teachingCards.filter((card) => card.status === "pending");
  const activeCard = pendingCards[0] || null;
  const position = activeCard
    ? Math.max(1, category.teachingCards.findIndex((card) => card.id === activeCard.id) + 1)
    : category.teachingCards.length;
  return `<div class="ai-learning-teach-intro">
    <div>
      <p class="ai-learning-eyebrow">${legacyReadOnly ? "Human-in-the-loop" : "Один сигнал — одно решение"}</p>
      <h2>${legacyReadOnly ? "Что для категории хорошо, а что плохо" : "Подтвердите, что ИИ должен делать"}</h2>
      <p>${legacyReadOnly
        ? "Это прежняя восьмикатегорийная история. Она не подтверждена parser lineage и больше не применяется к генерации."
        : "На экране только один кандидат правила. После решения следующая карточка появится автоматически."}</p>
    </div>
    <div class="ai-learning-teach-legend" aria-label="Решение команды">
      <span><b aria-hidden="true">${activeCard ? position : "✓"}</b> ${activeCard ? `из ${category.teachingCards.length}` : "всё проверено"}</span>
    </div>
  </div>
  <aside class="ai-learning-safety-note is-accent" role="note">
    <strong>${legacyReadOnly ? "Audit-only: влияние отключено" : "Немедленное, но ограниченное влияние"}</strong>
    <p>${legacyReadOnly
      ? "Для управляемого решения откройте точную market category выше: там доступны source analysis, история версий и CAS-исправления."
      : "После authoritative-ответа меняется только указанное правило этой категории и его версия. Решение не переобучает базовую модель, не переносится на другие категории и не гарантирует результат."}</p>
    ${legacyReadOnly ? "" : `
    <strong>Для карточек правил ниже</strong>
    <p>Подтверждение карточки суждения выпускает новую версию bounded‑правила категории. У исторических кейсов другой, более строгий порог влияния — он показан в отдельном блоке.</p>
    `}
  </aside>
  <section class="ai-learning-section ai-learning-judgement-section" aria-labelledby="ai-learning-judgement-title">
    <div class="ai-learning-section-heading">
      <div><p class="ai-learning-eyebrow">Кандидат правила</p><h2 id="ai-learning-judgement-title">Текущее решение</h2></div>
      <span>${activeCard ? `Сигнал ${position} из ${category.teachingCards.length}` : "Очередь закончена"}</span>
    </div>
  <div class="ai-learning-teaching-list" aria-live="polite">
    ${activeCard
      ? teachingCardMarkup(activeCard, category, control, { canDecide, busy, busyCardId })
      : emptyMarkup("Все предложения проверены", "Подтверждённые правила видны на вкладке «Обзор». Новые появятся после анализа свежих данных.")}
  </div>
  </section>`;
}

function historicalCasesMarkup(category, control, {
  canDecideHistoricalCase,
  busy,
  busyHistoricalCaseId,
  filter,
  historicalImport,
}) {
  const normalizedFilter = aiHistoricalCaseFilter(filter);
  const cases = category.historicalCases.filter((item) => {
    if (normalizedFilter === "all") return true;
    if (normalizedFilter === "review") return item.outcome === "review";
    return item.outcome === normalizedFilter;
  });
  const summary = category.historicalCaseSummary;
  const filterSpecs = [
    ["all", "Все", summary.total],
    ["good", "Хорошо", summary.good],
    ["bad", "Плохо", summary.bad],
    ["review", "Проверить", summary.review],
  ];
  const liveMessage = busyHistoricalCaseId
    ? "Сохраняем решение по историческому кейсу. Автообновление временно приостановлено."
    : `${summary.pending} кейсов ждут решения человека; показано ${cases.length}.`;
  return `<section class="ai-learning-section ai-learning-historical" aria-labelledby="ai-learning-historical-title" data-ce-patch-key="ai-historical-cases-${escapeHtml(category.key)}-${escapeHtml(normalizedFilter)}">
    <div class="ai-learning-historical-head">
      <div>
        <p class="ai-learning-eyebrow">Historical outcomes</p>
        <h2 id="ai-learning-historical-title">Исторические кейсы</h2>
        <p>Фактические результаты из таблиц отделены от сырых подписей и промптов. Решение сразу обновляет журнал и метрики; генерация использует кейсы только после отдельных строгих проверок.</p>
      </div>
      <span class="ai-learning-historical-live" role="status" aria-live="polite" aria-atomic="true">${escapeHtml(liveMessage)}</span>
    </div>
    ${historicalEvidenceMarkup(category.historicalCaseEvidence)}
    ${historicalImportMarkup(category, historicalImport, busy)}
    <div class="ai-learning-historical-kpis" aria-label="Метрики исторических кейсов">
      ${metricMarkup("Всего кейсов", summary.total, "в серверном снимке категории")}
      ${metricMarkup("Хорошо", summary.good, "положительных исходов")}
      ${metricMarkup("Плохо", summary.bad, "отрицательных исходов")}
      ${metricMarkup("На проверке", summary.pending, "ещё не влияют на обучение")}
      ${metricMarkup("Карантин", summary.quarantined, "не учить до проверки")}
    </div>
    <div class="ai-learning-historical-toolbar">
      <div class="ai-learning-historical-filters" role="group" aria-label="Фильтр исторических кейсов">
        ${filterSpecs.map(([key, label, count]) => `<button type="button" data-action="select-ai-historical-case-filter" data-historical-case-filter="${key}" aria-pressed="${normalizedFilter === key}" ${busy ? "disabled" : ""}>${escapeHtml(label)} <span>${count}</span></button>`).join("")}
      </div>
      <small>Источник, период и площадка сохраняются у каждого вывода.</small>
    </div>
    <div class="ai-learning-historical-list" aria-live="polite">
      ${cases.length
        ? cases.map((item) => historicalCaseMarkup(item, category, control, {
          canDecideHistoricalCase,
          busy,
          busyHistoricalCaseId,
        })).join("")
        : emptyMarkup("Нет кейсов в этом фильтре", "Выберите другой исход или дождитесь завершения разбора таблицы.")}
    </div>
    ${historicalBatchLedgerMarkup(category.historicalCaseBatches, category, busy)}
  </section>`;
}

function historicalEvidenceMarkup(evidence) {
  const source = objectValue(evidence) || normalizeHistoricalCaseEvidence({});
  const eligibleAngles = source.eligibleExactProduct > 0
    ? arrayFrom(source.angles).filter(
      (item) => item.preferredEligible || item.avoidEligible,
    )
    : [];
  return `<aside class="ai-learning-historical-evidence" role="note">
    <div>
      <strong>Когда кейсы могут подсказать генерации</strong>
      <p>Только последний подтверждённый исход вне карантина, с допустимым creative angle и точной товарной связью: внутренний <code>product_id</code> или однозначное совпадение <code>product_sku</code> / <code>current_wb_article</code>. Нечёткое и категорийное сопоставление запрещено. Нужно минимум ${source.threshold} непротиворечивых кейса одного направления; ручное обучение и базовая политика всегда приоритетнее fallback.</p>
    </div>
    <dl>
      <div><dt>Подтверждено</dt><dd>${source.confirmed}</dd></div>
      <div><dt>Точно применимы</dt><dd>${source.eligibleExactProduct}</dd></div>
      <div><dt>Связь product_id</dt><dd>${source.directProductBinding}</dd></div>
      <div><dt>Однозначный SKU</dt><dd>${source.lateExactSkuBinding}</dd></div>
      <div><dt>Без точного совпадения</dt><dd>${source.missingExactProductBinding}</dd></div>
      <div><dt>Порог направления</dt><dd>${source.threshold}</dd></div>
    </dl>
    ${eligibleAngles.length ? `<p class="ai-learning-historical-angle-ready">Категорийный порог пройден: ${eligibleAngles.map((item) => `${escapeHtml(item.key)} (${item.good} / ${item.bad})`).join(", ")}. В категории есть точно сопоставимые кейсы; применимость к выбранному товару сервер проверит отдельно.</p>` : `<p class="ai-learning-historical-angle-wait">Пока нет сочетания достаточного creative angle и точной товарной связи для generation fallback.</p>`}
  </aside>`;
}

function historicalImportMarkup(category, rawImport, busy) {
  const local = objectValue(rawImport) || {};
  const latest = category.historicalCaseBatches[0] || {};
  const localCategory = aiLearningCategory(local.productCategory || local.product_category);
  const latestStatus = cleanText(latest.status, 30).toLowerCase();
  const hasAuthoritativeLatest = AI_HISTORICAL_BATCH_STATUSES.has(latestStatus);
  const localSourceId = cleanText(local.sourceId || local.source_id, 200);
  const authoritativeCoversLocal = hasAuthoritativeLatest && Boolean(localSourceId)
    && localSourceId === latest.sourceId;
  const localVisible = Boolean(local.active) && localCategory === category.key
    && (local.inFlight === true || !authoritativeCoversLocal);
  const status = cleanText(
    localVisible ? local.status : latest.status,
    30,
  ).toLowerCase();
  if (!localVisible && !AI_HISTORICAL_BATCH_STATUSES.has(status)) return "";
  const parsed = nonNegativeInteger(
    localVisible ? local.parsed : latest.parsed,
    0,
  );
  const imported = nonNegativeInteger(
    localVisible ? local.imported : latest.imported,
    0,
  );
  const quarantined = nonNegativeInteger(
    localVisible ? local.quarantined : latest.quarantined,
    0,
  );
  const errors = nonNegativeInteger(
    localVisible ? local.errors : latest.errors,
    0,
  );
  const filename = cleanText(
    localVisible ? local.filename : latest.filename,
    240,
  );
  const categoryCounts = localVisible
    ? normalizeHistoricalCategoryCounts(
      local.recognizedCategories || local.perCategory || local.per_category,
    )
    : arrayFrom(latest.categoryCounts);
  const sourceId = cleanText(
    localVisible ? local.sourceId : latest.sourceId,
    200,
  );
  const retryable = ["queued", "processing", "failed"].includes(status)
    && Boolean(sourceId);
  const retryLabel = status === "failed" ? "Повторить разбор" : "Продолжить разбор";
  const importCategory = localVisible
    ? localCategory
    : latest.defaultProductCategory || category.key;
  const copy = status === "queued"
    ? "Файл поставлен в очередь. Начинаем безопасный разбор листов."
    : status === "processing"
      ? "Читаем таблицу, проверяем метрики и отделяем спорные строки в карантин."
      : status === "completed"
        ? `Разобрано ${parsed}; добавлено ${imported}; карантин ${quarantined}; ошибок ${errors}.`
        : cleanText(local.message, 500)
          || `Разбор остановлен. Ошибок: ${errors}. Уже зарегистрированный источник не потерян.`;
  return `<aside class="ai-learning-import-status is-${escapeHtml(status || "processing")}" role="status" aria-live="polite" aria-atomic="true" data-ce-patch-key="ai-historical-import-status">
    <span class="ai-learning-import-pulse" aria-hidden="true"></span>
    <div><strong>${status === "completed" ? "Разбор таблицы завершён" : status === "failed" ? "Таблица требует повторного разбора" : "Разбираем исторические кейсы"}</strong><p>${escapeHtml(copy)}</p>${filename ? `<small>${escapeHtml(filename)}</small>` : ""}${categoryCounts.length ? `<div class="ai-learning-import-categories"><span>Распознано по категориям:</span>${categoryCounts.map((item) => `<button type="button" data-action="select-ai-learning-category" data-category-key="${escapeHtml(item.key)}">${escapeHtml(item.label)} <b>${item.count}</b>${item.quarantined ? `<small>+${item.quarantined} карантин</small>` : ""}</button>`).join("")}</div>` : ""}</div>
    ${retryable ? `<button type="button" data-action="retry-ai-historical-case-import" data-source-id="${escapeHtml(sourceId)}" data-product-category="${escapeHtml(importCategory)}" data-filename="${escapeHtml(filename)}" ${busy ? "disabled" : ""}>${retryLabel}</button>` : ""}
  </aside>`;
}

function historicalCaseMarkup(item, category, control, {
  canDecideHistoricalCase,
  busy,
  busyHistoricalCaseId,
}) {
  const caseBusy = Boolean(busyHistoricalCaseId && busyHistoricalCaseId === item.id);
  const currentDecision = item.reviewStatus === "confirmed"
    ? "confirm"
    : item.reviewStatus === "rejected" ? "reject" : "";
  const disabled = !canDecideHistoricalCase || busy || caseBusy
    || !item.id || !item.eventId;
  const confirmDisabled = disabled || item.quarantined || currentDecision === "confirm";
  const rejectDisabled = disabled || currentDecision === "reject";
  const confirmLabel = currentDecision === "reject"
    ? "Изменить: верно"
    : currentDecision === "confirm" ? "Верно ✓" : "Верно";
  const rejectLabel = currentDecision === "confirm"
    ? "Изменить: не учить"
    : currentDecision === "reject" ? "Не учить ✓" : "Не учить";
  const bindingTone = item.directProductBinding
    ? "bound"
    : item.lateExactSkuBinding ? "late" : item.lateBindingCandidate ? "candidate" : "unbound";
  const bindingTitle = item.directProductBinding
    ? "Внутренняя привязка product_id"
    : item.lateExactSkuBinding
      ? "Однозначное совпадение SKU"
      : item.lateBindingCandidate
        ? "SKU сохранён для поздней точной связи"
        : "Нет точного идентификатора товара";
  const bindingCopy = item.directProductBinding
    ? "После подтверждения кейс может войти в evidence этого же product_id, если выполнены остальные пороги."
    : item.lateExactSkuBinding
      ? "Кейс может войти в evidence единственного товара, точно совпавшего по product_sku или current_wb_article; fuzzy-поиск не используется."
      : item.lateBindingCandidate
        ? "Если сейчас или позже ровно один товар совпадёт с этим product_sku или current_wb_article, кейс сможет примениться к нему. Неоднозначное и категорийное совпадение запрещено."
        : "Пока кейс остаётся только в памяти и метриках; generation fallback его не использует.";
  const title = item.productTitle || item.productSku || item.marketplaceSku
    || "Исторический кейс без названия товара";
  const identity = [item.brand, title].filter(Boolean).join(" · ");
  const source = [
    item.source.filename,
    item.source.sheet ? `лист «${item.source.sheet}»` : "",
    item.source.row ? `строка ${item.source.row}` : "",
  ].filter(Boolean).join(" · ") || "Источник не указан";
  const marketplaceIdentity = [
    platformLabel(item.platform),
    item.channel,
    item.marketplaceSku || item.productSku,
  ].filter(Boolean).join(" · ") || "Площадка не указана";
  const outcomeLabel = historicalOutcomeLabel(item.outcome);
  const scopeVersion = Number.isSafeInteger(item.scopeVersion)
    ? item.scopeVersion
    : category.scopeVersion;
  const eventCursor = item.eventCursor || control.eventCursor;
  return `<article class="ai-learning-historical-card is-${escapeHtml(item.outcome)} is-${escapeHtml(item.reviewStatus)}${caseBusy ? " is-busy" : ""}" data-ai-historical-case data-product-category="${escapeHtml(category.key)}" data-case-id="${escapeHtml(item.id)}" data-event-id="${escapeHtml(item.eventId)}" data-scope-version="${scopeVersion}" data-event-cursor="${eventCursor}" data-ce-patch-key="ai-historical-${escapeHtml(item.id)}-${escapeHtml(item.reviewStatus)}">
    <header>
      <div><p class="ai-learning-eyebrow">${escapeHtml(item.outcomeDimension || "фактический результат")}</p><h3>${escapeHtml(identity)}</h3></div>
      <div class="ai-learning-historical-badges"><span class="is-${escapeHtml(item.outcome)}">${escapeHtml(outcomeLabel)}</span>${item.quarantined ? `<span class="is-quarantine">quarantine</span>` : ""}</div>
    </header>
    ${item.statusLabel ? `<p class="ai-learning-historical-status-label">${escapeHtml(item.statusLabel)}</p>` : ""}
    <dl class="ai-learning-historical-context">
      <div><dt>Площадка / SKU</dt><dd>${escapeHtml(marketplaceIdentity)}</dd></div>
      <div><dt>Период</dt><dd>${escapeHtml(item.periodLabel || "Не указан")}</dd></div>
      <div><dt>Источник</dt><dd>${escapeHtml(source)}</dd></div>
      <div><dt>Уверенность</dt><dd>${escapeHtml(formatConfidence(item.confidence))}</dd></div>
    </dl>
    <p class="ai-learning-historical-binding is-${bindingTone}"><strong>${bindingTitle}</strong><span>${bindingCopy}</span></p>
    <div class="ai-learning-historical-metrics" aria-label="Фактические метрики кейса">
      ${item.metricItems.length
        ? item.metricItems.map(historicalMetricMarkup).join("")
        : `<span>В снимке нет безопасных агрегированных метрик.</span>`}
    </div>
    ${currentDecision ? `<div class="ai-learning-recorded-decision is-${item.reviewStatus === "confirmed" ? "good" : "bad"}" role="status"><strong>${item.reviewStatus === "confirmed" ? "Сейчас: верно" : "Сейчас: не учить"}</strong><span>Это активная версия решения в серверном журнале. Её можно исправить противоположной кнопкой.</span></div>` : ""}
    <div class="ai-learning-historical-actions">
        <p>«Верно» подтверждает исход, «Не учить» исключает его из evidence. Новое противоположное решение станет активной версией без перезагрузки; generation fallback всё равно требует точное сопоставление товара и порог доказательств.</p>
        <div>
          <button class="is-good" type="button" data-action="decide-ai-historical-case" data-product-category="${escapeHtml(category.key)}" data-case-id="${escapeHtml(item.id)}" data-event-id="${escapeHtml(item.eventId)}" data-scope-version="${scopeVersion}" data-event-cursor="${eventCursor}" data-current-decision="${escapeHtml(currentDecision)}" data-decision="confirm" ${confirmDisabled ? "disabled" : ""}${item.quarantined ? ' title="Сначала сопоставьте товар и выведите кейс из карантина"' : ""}>${caseBusy ? "Сохраняем…" : confirmLabel}</button>
          <button class="is-bad" type="button" data-action="decide-ai-historical-case" data-product-category="${escapeHtml(category.key)}" data-case-id="${escapeHtml(item.id)}" data-event-id="${escapeHtml(item.eventId)}" data-scope-version="${scopeVersion}" data-event-cursor="${eventCursor}" data-current-decision="${escapeHtml(currentDecision)}" data-decision="reject" ${rejectDisabled ? "disabled" : ""}>${caseBusy ? "Сохраняем…" : rejectLabel}</button>
        </div>
        ${capabilityHint(control.capabilities.canDecideHistoricalCase, "решать судьбу исторических кейсов")}
      </div>
  </article>`;
}

function historicalMetricMarkup(metric) {
  return `<span><small>${escapeHtml(metric.label)}</small><strong>${escapeHtml(metric.value)}</strong></span>`;
}

function historicalBatchLedgerMarkup(batches, category, busy) {
  if (!batches.length) return "";
  const incomplete = batches.filter((batch) => (
    ["queued", "processing", "failed"].includes(batch.status) && batch.sourceId
  ));
  const visible = [...incomplete, ...batches.filter((batch) => (
    !incomplete.some((candidate) => candidate.id === batch.id)
  )).slice(0, 5)];
  return `<details class="ai-learning-historical-batches"><summary>Последние импорты (${batches.length})</summary><ul>${visible.map((batch) => {
    const retryable = ["queued", "processing", "failed"].includes(batch.status)
      && Boolean(batch.sourceId);
    const importCategory = batch.defaultProductCategory || category.key;
    const actionLabel = batch.status === "failed" ? "Повторить разбор" : "Продолжить разбор";
    return `<li><span>${escapeHtml(batch.filename || "Таблица")}</span><small>${escapeHtml(historicalBatchStatusLabel(batch.status))} · добавлено ${batch.imported} · карантин ${batch.quarantined}${batch.completedAt ? ` · ${escapeHtml(formatDateTime(batch.completedAt))}` : ""}</small>${retryable ? `<button type="button" data-action="retry-ai-historical-case-import" data-source-id="${escapeHtml(batch.sourceId)}" data-product-category="${escapeHtml(importCategory)}" data-filename="${escapeHtml(batch.filename)}" ${busy ? "disabled" : ""}>${actionLabel}</button>` : ""}</li>`;
  }).join("")}</ul></details>`;
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

function sourceMarkup(source, category, { canImportHistoricalCases = false, busy = false } = {}) {
  const link = source.url
    ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">Открыть <span aria-hidden="true">↗</span></a>`
    : "";
  const filename = source.originalFilename || source.title;
  const lowerFilename = filename.toLocaleLowerCase("en-US");
  const spreadsheet = source.kind === "file"
    && (lowerFilename.endsWith(".xlsx") || lowerFilename.endsWith(".csv")
      || source.mimeType === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      || source.mimeType === "text/csv");
  const hasBatch = category.historicalCaseBatches.some((batch) => (
    batch.sourceId === source.id
  ));
  const parseAction = spreadsheet && !hasBatch && source.status !== "rejected"
    ? `<button type="button" data-action="retry-ai-historical-case-import" data-source-id="${escapeHtml(source.id)}" data-product-category="${escapeHtml(source.productCategory || category.key)}" data-filename="${escapeHtml(filename)}" ${!canImportHistoricalCases || busy ? "disabled" : ""}>Разобрать кейсы</button>`
    : "";
  return `<article class="ai-learning-source is-${escapeHtml(source.status)}" data-source-id="${escapeHtml(source.id)}" data-ce-patch-key="ai-source-${escapeHtml(source.id)}">
    <div class="ai-learning-source-kind" aria-hidden="true">${source.kind === "file" ? "▤" : "↗"}</div>
    <div class="ai-learning-source-copy">
      <div><span>${escapeHtml(sourceKindLabel(source.kind))}</span><span class="ai-learning-source-status">${escapeHtml(sourceStatusLabel(source.status))}</span></div>
      <h3>${escapeHtml(source.title || "Источник без названия")}</h3>
      <p>${escapeHtml(source.provenance || source.host || "Происхождение проверяется")}</p>
      <small>${formatDateTime(source.addedAt) ? `Добавлен ${escapeHtml(formatDateTime(source.addedAt))}` : "Дата добавления не указана"}${source.evidenceHash ? ` · ${escapeHtml(shortHash(source.evidenceHash))}` : ""}</small>
    </div>
    ${link}${parseAction}
  </article>`;
}

function teachingCardMarkup(card, category, control, { canDecide, busy, busyCardId }) {
  const decided = card.status !== "pending";
  const cardBusy = Boolean(busyCardId && busyCardId === card.id);
  const disabled = !canDecide || decided || busy || cardBusy;
  const angleKey = creativeAngleKey(card.signalKey);
  const signalLabel = angleKey
    ? creativeAngleLabel(angleKey)
    : card.title || humanizeKey(card.signalKey) || "Сигнал требует проверки";
  const authoritativeTitle = card.title && card.title !== signalLabel
    ? card.title
    : "";
  const isGood = card.aiJudgement === "good";
  const isBad = card.aiJudgement === "bad";
  const judgement = isGood
    ? "Предложение: использовать"
    : isBad ? "Предупреждение: избегать" : "Данных недостаточно";
  const explanation = isGood
    ? "Если подтвердить, ИИ будет чаще выбирать этот приём для данной категории."
    : isBad
      ? "Если подтвердить, ИИ будет избегать этого приёма для данной категории."
      : "Правило пока не применяется. Добавьте данные, чтобы команда могла принять решение.";
  const approveLabel = isGood ? "Да, использовать" : "Да, избегать";
  const rejectLabel = isGood ? "Нет, не считать полезным" : "Нет, не считать плохим";
  const cardKey = `ai-teaching-${category.key}-${card.id}-${card.version}-${card.hash || "nohash"}`;
  return `<article class="ai-learning-teaching-card is-${escapeHtml(card.status)}${cardBusy ? " is-busy" : ""}" data-ai-teaching-card data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-ai-judgement="${escapeHtml(card.aiJudgement)}" data-signal-label="${escapeHtml(signalLabel)}" data-ce-patch-key="${escapeHtml(cardKey)}">
    <header>
      <div><p class="ai-learning-eyebrow">Кандидат правила</p><h3>${escapeHtml(signalLabel)}</h3></div>
      <span class="ai-learning-judgement is-${escapeHtml(card.aiJudgement)}">${escapeHtml(judgement)}</span>
    </header>
    ${authoritativeTitle ? `<p class="ai-learning-teaching-context"><strong>Что именно:</strong> ${escapeHtml(authoritativeTitle)}</p>` : ""}
    ${card.context ? `<p class="ai-learning-teaching-context"><strong>Контекст:</strong> ${escapeHtml(card.context)}</p>` : ""}
    ${card.rationale ? `<blockquote><strong>Почему:</strong> ${escapeHtml(card.rationale)}</blockquote>` : ""}
    <p class="ai-learning-teaching-context">${escapeHtml(explanation)}</p>
    <dl>
      <div><dt>Решений команды</dt><dd>${card.evidenceCount}</dd></div>
    </dl>
    ${decided ? teachingDecisionMarkup(card) : !isGood && !isBad ? `<div class="ai-learning-decision-actions"><button class="is-primary" type="button" data-action="select-ai-learning-view" data-view="knowledge">Добавить данные</button></div>` : `<form class="ai-learning-decision-form" data-form="ai-learning-decision" data-ce-patch-key="ai-decision-form-${escapeHtml(card.id)}" novalidate>
      ${scopeInputs(control, category)}
      <input type="hidden" name="card_id" value="${escapeHtml(card.id)}" />
      <input type="hidden" name="card_version" value="${card.version}" />
      <input type="hidden" name="card_hash" value="${escapeHtml(card.hash)}" />
      <input type="hidden" name="expected_scope_version" value="${category.scopeVersion}" />
      <div class="ai-learning-decision-actions">
        <button class="is-primary is-${isGood ? "good" : "bad"}" type="submit" data-primary-action="true" data-action="decide-ai-teaching-card" data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-ai-judgement="${escapeHtml(card.aiJudgement)}" data-signal-label="${escapeHtml(signalLabel)}" data-decision="approve" ${disabled ? "disabled" : ""}><span aria-hidden="true">✓</span> ${cardBusy ? "Сохраняем…" : approveLabel}</button>
        <button class="is-secondary" type="submit" data-action="decide-ai-teaching-card" data-product-category="${escapeHtml(category.key)}" data-card-id="${escapeHtml(card.id)}" data-card-version="${card.version}" data-card-hash="${escapeHtml(card.hash)}" data-scope-version="${category.scopeVersion}" data-ai-judgement="${escapeHtml(card.aiJudgement)}" data-signal-label="${escapeHtml(signalLabel)}" data-decision="reject" ${disabled ? "disabled" : ""}><span aria-hidden="true">×</span> ${cardBusy ? "Сохраняем…" : rejectLabel}</button>
      </div>
      ${capabilityHint(control.capabilities.canDecide, "принимать решения")}
    </form>`}
  </article>`;
}

function teachingDecisionMarkup(card) {
  const decision = AI_TEACHING_DECISIONS.has(card.decision)
    ? card.decision
    : card.status === "approved" ? "approve" : "reject";
  const accepted = decision === "approve";
  const acceptedLabel = card.aiJudgement === "bad"
    ? "Подтверждено: ИИ избегает этот сигнал"
    : "Подтверждено: ИИ использует этот сигнал";
  return `<div class="ai-learning-recorded-decision is-${accepted ? "good" : "bad"}" role="status">
    <strong>${accepted ? acceptedLabel : "Отклонено: правило не применяется"}</strong>
    <span>${card.decidedBy ? `${escapeHtml(card.decidedBy)} · ` : ""}${escapeHtml(formatDateTime(card.decidedAt) || "решение сохранено")}</span>
    ${card.reason ? `<p>${escapeHtml(card.reason)}</p>` : ""}
  </div>`;
}

// Сервер пишет журнал техническими формулами («Use trust building in this
// category», «operator_confirmed»). Человеку показываем русскую расшифровку,
// а серверную формулировку оставляем мелкой строкой — журнал append-only,
// его смысл нельзя терять (фидбек владельца 27.08: «не всегда понятен смысл»).
const ANGLE_TITLE_ALIASES = Object.freeze({
  trust_building: "trust_builder",
});

const ACTIVITY_DESCRIPTION_LABELS = Object.freeze({
  operator_confirmed: "Человек подтвердил: ИИ может использовать этот приём в категории.",
  operator_rejected: "Человек отклонил: ИИ не использует этот приём в категории.",
});

function humanizeActivityTitle(rawTitle) {
  const title = String(rawTitle || "");
  const use = /^use\s+(.+?)\s+in\s+this\s+category$/iu.exec(title.trim());
  if (!use) return null;
  const slug = use[1].toLowerCase().replace(/[\s-]+/gu, "_");
  const key = Object.hasOwn(CREATIVE_ANGLE_LABELS, slug)
    ? slug
    : ANGLE_TITLE_ALIASES[slug] || "";
  const angle = key ? CREATIVE_ANGLE_LABELS[key] : use[1];
  return `Приём «${angle}» — использовать в этой категории`;
}

function activityMarkup(item) {
  const humanTitle = humanizeActivityTitle(item.title);
  const description = ACTIVITY_DESCRIPTION_LABELS[String(item.description || "").trim()]
    || item.description;
  return `<li data-ce-patch-key="ai-activity-${escapeHtml(item.id)}">
    <span class="is-${escapeHtml(item.tone)}" aria-hidden="true"></span>
    <div><strong>${escapeHtml(humanTitle || item.title)}</strong><p>${escapeHtml(description)}</p><small>${humanTitle ? `${escapeHtml(item.title)} · ` : ""}${item.actor ? `${escapeHtml(item.actor)} · ` : ""}${escapeHtml(formatDateTime(item.createdAt) || "Время не указано")}${item.stateVersion ? ` · state ${item.stateVersion}` : ""}</small></div>
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
    ? `<ul>${policy.rules.map((rule) => {
      const label = rule.id === "preferred_angle"
        ? "Можно использовать"
        : rule.id === "avoid_angle" ? "Нужно избегать" : rule.label;
      const angleKey = creativeAngleKey(rule.effect);
      const effect = angleKey ? creativeAngleLabel(angleKey) : rule.effect;
      return `<li data-ce-patch-key="ai-policy-rule-${escapeHtml(rule.id)}"><span>${escapeHtml(label)}</span><small>${escapeHtml(effect)}</small></li>`;
    }).join("")}</ul>`
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
  const historicalSummary = normalizeHistoricalCaseSummary(
    source.historical_case_summary || source.historicalCaseSummary,
    [],
  );
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
    historicalCaseCount: historicalSummary.total,
    pendingHistoricalCaseCount: historicalSummary.pending,
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
  const historicalCases = arrayFrom(
    source.historical_cases || source.historicalCases,
  ).map(normalizeHistoricalCase).filter(Boolean).slice(0, 500);
  const historicalCaseSummary = normalizeHistoricalCaseSummary(
    source.historical_case_summary || source.historicalCaseSummary,
    historicalCases,
  );
  const historicalCaseBatches = arrayFrom(
    source.historical_case_batches || source.historicalCaseBatches
      || source.batches,
  ).map(normalizeHistoricalCaseBatch).filter(Boolean).slice(0, 50);
  const historicalCaseEvidence = normalizeHistoricalCaseEvidence(
    source.historical_case_evidence || source.historicalCaseEvidence
      || readiness.historical_case_evidence || readiness.historicalCaseEvidence,
  );
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
    historicalCaseCount: historicalCaseSummary.total,
    pendingHistoricalCaseCount: historicalCaseSummary.pending,
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
    historicalCases,
    historicalCaseSummary,
    historicalCaseBatches,
    historicalCaseEvidence,
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
    objectKey: cleanText(source.object_key || source.objectKey, 500),
    originalFilename: cleanText(
      source.original_filename || source.originalFilename || source.filename,
      240,
    ),
    mimeType: cleanText(source.mime_type || source.mimeType, 160).toLowerCase(),
    productCategory: (() => {
      const candidate = cleanText(
        source.product_category || source.productCategory,
        80,
      ).toLowerCase();
      return AI_CATEGORY_BY_KEY.has(candidate) ? candidate : "";
    })(),
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

function normalizeHistoricalCase(raw, index) {
  const source = objectValue(raw);
  if (!source) return null;
  const outcomeCandidate = cleanText(source.outcome, 30).toLowerCase();
  const outcome = AI_HISTORICAL_CASE_OUTCOMES.has(outcomeCandidate)
    ? outcomeCandidate
    : "review";
  const reviewCandidate = cleanText(
    source.review_status || source.reviewStatus
      || source.decision_status || source.decisionStatus,
    30,
  ).toLowerCase();
  const reviewStatus = AI_HISTORICAL_CASE_REVIEW_STATUSES.has(reviewCandidate)
    ? reviewCandidate
    : "pending";
  const rawMetrics = objectValue(source.metrics) || {};
  const rawSource = objectValue(source.source)
    || objectValue(source.provenance)
    || {};
  const confidenceValue = Number(source.confidence);
  const confidence = Number.isFinite(confidenceValue)
    ? Math.max(0, Math.min(100, confidenceValue <= 1 ? confidenceValue * 100 : confidenceValue))
    : null;
  const periodStart = dateOnly(
    source.period_start || source.periodStart || rawMetrics.period_start
      || rawMetrics.periodStart || rawMetrics.date_from || rawMetrics.dateFrom,
  );
  const periodEnd = dateOnly(
    source.period_end || source.periodEnd || rawMetrics.period_end
      || rawMetrics.periodEnd || rawMetrics.date_to || rawMetrics.dateTo,
  );
  const explicitPeriod = cleanText(
    source.period || source.period_label || source.periodLabel
      || rawMetrics.period || rawMetrics.period_label || rawMetrics.periodLabel,
    100,
  );
  const statusLabel = cleanText(
    source.status_label || source.statusLabel,
    180,
  );
  const productId = cleanText(source.product_id || source.productId, 200);
  const productSku = cleanText(source.product_sku || source.productSku, 160);
  const marketplaceSku = cleanText(
    source.marketplace_sku || source.marketplaceSku,
    160,
  );
  const bindingCandidate = cleanText(
    source.historical_learning_binding_status
      || source.historicalLearningBindingStatus,
    50,
  ).toLowerCase();
  const bindingStatus = AI_HISTORICAL_CASE_BINDING_STATUSES.has(bindingCandidate)
    ? bindingCandidate
    : productId ? "direct_product_id" : "missing_exact_binding";
  const directProductBinding = source.exact_product_binding_present === true
    || source.exactProductBindingPresent === true
    || Boolean(productId)
    || bindingStatus === "direct_product_id";
  const lateExactSkuBinding = !directProductBinding && (
    source.late_exact_sku_binding_available === true
    || source.lateExactSkuBindingAvailable === true
    || bindingStatus === "late_unique_product_sku"
    || bindingStatus === "late_unique_marketplace_sku"
  );
  return {
    id: cleanText(
      source.case_id || source.caseId || source.id,
      200,
    ) || `historical-case-${index + 1}`,
    eventId: cleanText(
      source.head_event_id || source.headEventId
        || source.event_id || source.eventId,
      200,
    ),
    externalCaseId: cleanText(
      source.external_case_id || source.externalCaseId,
      240,
    ),
    productCategory: aiLearningCategory(
      source.product_category || source.productCategory,
    ),
    productId,
    productSku,
    marketplaceSku,
    bindingStatus,
    directProductBinding,
    lateExactSkuBinding,
    lateBindingCandidate: !directProductBinding && !lateExactSkuBinding
      && Boolean(productSku || marketplaceSku),
    productTitle: cleanText(
      source.product_title || source.productTitle,
      260,
    ),
    brand: cleanText(source.brand, 120),
    platform: safeKey(source.platform, 60),
    channel: cleanText(source.channel, 100),
    outcome,
    outcomeDimension: cleanText(
      source.outcome_dimension || source.outcomeDimension,
      120,
    ),
    statusLabel,
    confidence,
    reviewStatus,
    quarantined: source.quarantined === true
      || source.quarantine === true
      || cleanText(
        source.resolution_status || source.resolutionStatus,
        30,
      ).toLowerCase() === "quarantined"
      || /quarantine|карантин/iu.test(statusLabel),
    periodLabel: explicitPeriod || formatHistoricalPeriod(periodStart, periodEnd),
    periodStart,
    periodEnd,
    metricItems: normalizeHistoricalMetricItems(rawMetrics),
    source: {
      filename: cleanText(
        rawSource.filename || rawSource.original_filename
          || rawSource.originalFilename,
        240,
      ),
      sheet: cleanText(rawSource.sheet || rawSource.sheet_name || rawSource.sheetName, 120),
      row: positiveInteger(rawSource.row || rawSource.row_number || rawSource.rowNumber, 0),
    },
    scopeVersion: nonNegativeInteger(
      source.scope_version ?? source.scopeVersion
        ?? source.case_version ?? source.caseVersion,
      0,
    ),
    eventCursor: nonNegativeInteger(
      source.head_event_cursor ?? source.headEventCursor
        ?? source.event_cursor ?? source.eventCursor,
      0,
    ),
  };
}

function normalizeHistoricalMetricItems(raw) {
  const metrics = objectValue(raw) || {};
  const specs = [
    ["views", "Просмотры", "number", ["views", "impressions"]],
    ["visits", "Визиты", "number", ["visits"]],
    ["carts", "Корзины", "number", ["carts", "add_to_cart"]],
    ["orders", "Заказы", "number", ["orders"]],
    ["sales", "Продажи", "number", ["sales"]],
    ["revenue", "Выручка", "currency", ["revenue", "sales_amount"]],
    ["buyout", "Выкуп", "percent", ["buyout", "buyout_rate"]],
    ["sale_view", "Продажи / просмотры", "percent", ["sale_to_view_rate", "sales_to_views", "sale_view_rate", "sale_per_view"]],
    ["sales_1000", "Продажи / 1000 просмотров", "number", ["sales_per_1000_views"]],
    ["visit_cart", "Визит → корзина", "percent", ["visit_to_cart_rate", "visit_cart_rate"]],
    ["visit_order", "Визит → заказ", "percent", ["visit_to_order_rate", "conversion_rate", "cr"]],
    ["ad_spend", "Расход РК", "currency", ["ad_spend", "campaign_spend"]],
    ["drr", "ДРР", "percent", ["drr"]],
    ["margin", "Маржа", "currency", ["margin"]],
    ["margin_rate", "Маржа %", "percent", ["margin_rate", "margin_percent"]],
  ];
  return specs.map(([key, label, kind, aliases]) => {
    const alias = aliases.find((candidate) => Object.hasOwn(metrics, candidate));
    if (!alias) return null;
    const number = Number(metrics[alias]);
    if (!Number.isFinite(number)) return null;
    return { key, label, value: formatHistoricalMetricValue(number, kind) };
  }).filter(Boolean).slice(0, 8);
}

function normalizeHistoricalCaseSummary(raw, cases) {
  const source = objectValue(raw) || {};
  const computed = {
    total: cases.length,
    good: cases.filter((item) => item.outcome === "good").length,
    bad: cases.filter((item) => item.outcome === "bad").length,
    review: cases.filter((item) => item.outcome === "review").length,
    pending: cases.filter((item) => item.reviewStatus === "pending").length,
    confirmed: cases.filter((item) => item.reviewStatus === "confirmed").length,
    rejected: cases.filter((item) => item.reviewStatus === "rejected").length,
    quarantined: cases.filter((item) => item.quarantined).length,
  };
  return {
    total: nonNegativeInteger(
      source.total ?? source.total_cases ?? source.totalCases,
      computed.total,
    ),
    good: nonNegativeInteger(
      source.good ?? source.good_cases ?? source.goodCases,
      computed.good,
    ),
    bad: nonNegativeInteger(
      source.bad ?? source.bad_cases ?? source.badCases,
      computed.bad,
    ),
    review: nonNegativeInteger(
      source.review ?? source.review_cases ?? source.reviewCases,
      computed.review,
    ),
    pending: nonNegativeInteger(
      source.pending ?? source.pending_cases ?? source.pendingCases,
      computed.pending,
    ),
    confirmed: nonNegativeInteger(
      source.confirmed ?? source.confirmed_cases ?? source.confirmedCases,
      computed.confirmed,
    ),
    rejected: nonNegativeInteger(
      source.rejected ?? source.rejected_cases ?? source.rejectedCases,
      computed.rejected,
    ),
    quarantined: nonNegativeInteger(
      source.quarantined ?? source.quarantined_cases ?? source.quarantinedCases,
      computed.quarantined,
    ),
  };
}

function normalizeHistoricalCaseEvidence(raw) {
  const source = objectValue(raw) || {};
  const angles = arrayFrom(source.angles).map((item) => {
    const angle = objectValue(item);
    if (!angle) return null;
    const key = safeKey(angle.creative_angle || angle.creativeAngle, 80);
    if (!key) return null;
    return {
      key,
      confirmed: nonNegativeInteger(
        angle.confirmed_case_count ?? angle.confirmedCaseCount,
        0,
      ),
      good: nonNegativeInteger(angle.good_case_count ?? angle.goodCaseCount, 0),
      bad: nonNegativeInteger(angle.bad_case_count ?? angle.badCaseCount, 0),
      preferredEligible: angle.preferred_eligible === true,
      avoidEligible: angle.avoid_eligible === true,
    };
  }).filter(Boolean).slice(0, 20);
  return {
    version: cleanText(source.version, 100),
    confirmed: nonNegativeInteger(
      source.confirmed_case_count ?? source.confirmedCaseCount,
      0,
    ),
    eligibleExactProduct: nonNegativeInteger(
      source.historical_learning_eligible_count
        ?? source.historicalLearningEligibleCount,
      0,
    ),
    directProductBinding: nonNegativeInteger(
      source.historical_learning_direct_product_binding_count
        ?? source.historicalLearningDirectProductBindingCount,
      0,
    ),
    lateExactSkuBinding: nonNegativeInteger(
      source.historical_learning_late_exact_sku_binding_count
        ?? source.historicalLearningLateExactSkuBindingCount,
      0,
    ),
    missingExactProductBinding: nonNegativeInteger(
      source.missing_exact_product_binding_count
        ?? source.missingExactProductBindingCount,
      0,
    ),
    threshold: positiveInteger(
      source.minimum_confirmed_cases_per_direction
        || source.minimumConfirmedCasesPerDirection,
      2,
    ),
    preferredAngle: safeKey(
      source.advisory_preferred_creative_angle
        || source.advisoryPreferredCreativeAngle,
      80,
    ),
    avoidAngle: safeKey(
      source.advisory_avoid_creative_angle
        || source.advisoryAvoidCreativeAngle,
      80,
    ),
    angles,
  };
}

function normalizeHistoricalCaseBatch(raw, index) {
  const source = objectValue(raw);
  if (!source) return null;
  const statusCandidate = cleanText(
    source.status || source.import_status || source.importStatus,
    30,
  ).toLowerCase();
  const statusAlias = ({
    pending: "queued",
    in_progress: "processing",
    parsing: "processing",
    importing: "processing",
    imported: "completed",
    done: "completed",
    completed_with_quarantine: "completed",
    quarantined: "completed",
    parser_rejected: "failed",
    parser_rejected_all: "failed",
    error: "failed",
  })[statusCandidate] || statusCandidate;
  const status = AI_HISTORICAL_BATCH_STATUSES.has(statusAlias)
    ? statusAlias
    : "queued";
  const rawSource = objectValue(source.source) || {};
  const parserQuarantined = nonNegativeInteger(
    source.parser_quarantined_row_count ?? source.parserQuarantinedRowCount,
    0,
  );
  const databaseQuarantined = nonNegativeInteger(
    source.quarantined_case_count ?? source.quarantinedCaseCount,
    0,
  );
  const explicitQuarantined = source.quarantined ?? source.quarantined_cases
    ?? source.quarantinedCases;
  const explicitErrors = source.errors ?? source.error_count ?? source.errorCount;
  return {
    id: cleanText(
      source.import_id || source.importId || source.batch_id || source.batchId
        || source.id,
      200,
    )
      || `historical-batch-${index + 1}`,
    sourceId: cleanText(source.source_id || source.sourceId, 200),
    defaultProductCategory: (() => {
      const candidate = cleanText(
        source.default_product_category || source.defaultProductCategory,
        80,
      ).toLowerCase();
      return AI_CATEGORY_BY_KEY.has(candidate) ? candidate : "";
    })(),
    status,
    filename: cleanText(
      source.filename || source.original_filename || source.originalFilename
        || rawSource.filename,
      240,
    ),
    parsed: nonNegativeInteger(
      source.parsed ?? source.parsed_rows ?? source.parsedRows
        ?? source.parsed_row_count ?? source.parsedRowCount
        ?? source.case_count ?? source.caseCount,
      0,
    ),
    imported: nonNegativeInteger(
      source.imported ?? source.imported_cases ?? source.importedCases
        ?? source.matched_case_count ?? source.matchedCaseCount,
      0,
    ),
    quarantined: explicitQuarantined === undefined
      ? databaseQuarantined + parserQuarantined
      : nonNegativeInteger(explicitQuarantined, 0),
    errors: explicitErrors === undefined
      ? parserQuarantined
      : nonNegativeInteger(explicitErrors, 0),
    completedAt: timestamp(
      source.completed_at || source.completedAt
        || source.imported_at || source.importedAt,
    ),
    createdAt: timestamp(
      source.created_at || source.createdAt
        || source.imported_at || source.importedAt,
    ),
    categoryCounts: normalizeHistoricalCategoryCounts(
      source.per_category || source.perCategory || source.category_counts
        || source.categoryCounts || source.per_category_summary
        || source.perCategorySummary,
    ),
  };
}

function normalizeHistoricalCategoryCounts(raw) {
  const source = objectValue(raw);
  const items = source
    ? Object.entries(source).map(([productCategory, value]) => ({
      product_category: productCategory,
      ...(objectValue(value) || { imported: value }),
    }))
    : arrayFrom(raw);
  return items.map((item) => {
    const value = objectValue(item);
    if (!value) return null;
    const key = cleanText(
      value.product_category || value.productCategory || value.category,
      80,
    ).toLowerCase();
    if (!AI_CATEGORY_BY_KEY.has(key)) return null;
    return {
      key,
      label: AI_CATEGORY_BY_KEY.get(key).label,
      count: nonNegativeInteger(
        value.imported ?? value.count ?? value.cases ?? value.total
          ?? value.case_count ?? value.caseCount,
        0,
      ),
      quarantined: nonNegativeInteger(
        value.quarantined ?? value.review
          ?? value.quarantined_case_count ?? value.quarantinedCaseCount,
        0,
      ),
    };
  }).filter(Boolean);
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
    canDecideHistoricalCase: capability(
      source,
      ["can_decide_historical_case", "canDecideHistoricalCase"],
      false,
    ),
    canDecideResearchInbox: capability(
      source,
      ["can_decide_research_inbox", "canDecideResearchInbox"],
      false,
    ),
    // Fail closed: an older server that does not announce the reopened
    // legacy intake keeps the read-only archive stance.
    legacyIntakeReadOnly: capability(
      source,
      ["legacy_intake_read_only", "legacyIntakeReadOnly"],
      true,
    ),
    canViewHistory: capability(
      source,
      ["view_history", "can_view_history", "canViewHistory"],
      true,
    ),
  };
}

function normalizeResearchInbox(raw, selectedCategory) {
  return arrayFrom(raw).map((item, index) => {
    const source = objectValue(item);
    if (!source) return null;
    const productCategory = cleanText(
      source.product_category || source.productCategory,
      80,
    ).toLowerCase();
    const status = cleanText(source.status, 80).toLowerCase();
    const projectId = cleanText(source.project_id || source.projectId, 80);
    const runId = cleanText(source.run_id || source.runId, 80);
    const receiptId = cleanText(
      source.receipt_id || source.receiptId || source.id,
      80,
    );
    if (
      productCategory !== selectedCategory
      || !AI_CATEGORY_BY_KEY.has(productCategory)
      || !AI_RESEARCH_INBOX_STATUSES.has(status)
      || !UUID_PATTERN.test(projectId)
      || !UUID_PATTERN.test(runId)
      || !UUID_PATTERN.test(receiptId)
      || source.requires_human_review !== true
      || source.raw_research_enters_prompt_automatically !== false
      || source.affects_effective_policy !== false
    ) return null;
    return {
      id: receiptId,
      projectId,
      runId,
      productCategory,
      status,
      receiptHash: cleanText(
        source.receipt_hash || source.receiptHash,
        64,
      ).toLowerCase(),
      projectName: cleanText(
        source.project_name || source.projectName,
        180,
      ),
      productName: cleanText(
        source.product_name || source.productName,
        240,
      ),
      title: cleanText(
        source.research_title || source.researchTitle || source.title,
        240,
      ),
      sourceCount: nonNegativeInteger(
        source.source_count ?? source.sourceCount,
        0,
      ),
      eventCursor: nonNegativeInteger(
        source.event_cursor ?? source.eventCursor,
        index + 1,
      ),
      receivedAt: timestamp(
        source.received_at || source.receivedAt,
      ),
      deepLink: `#/workspace/research?project_id=${projectId}&run=${runId}`,
      requiresHumanReview: true,
      affectsEffectivePolicy: false,
    };
  }).filter((item) => (
    item && /^[0-9a-f]{64}$/u.test(item.receiptHash)
  )).slice(0, 50);
}

function normalizeResearchDecisions(raw, selectedCategory) {
  return arrayFrom(raw).map((item, index) => {
    const source = objectValue(item);
    if (!source) return null;
    const productCategory = cleanText(
      source.product_category || source.productCategory,
      80,
    ).toLowerCase();
    const decision = cleanText(source.decision, 20).toLowerCase();
    const dispositionId = cleanText(
      source.disposition_id || source.dispositionId || source.id,
      80,
    );
    const receiptId = cleanText(
      source.receipt_id || source.receiptId,
      80,
    );
    const projectId = cleanText(source.project_id || source.projectId, 80);
    const runId = cleanText(source.run_id || source.runId, 80);
    const receiptHash = cleanText(
      source.receipt_hash || source.receiptHash,
      64,
    ).toLowerCase();
    if (
      productCategory !== selectedCategory
      || !AI_CATEGORY_BY_KEY.has(productCategory)
      || !AI_RESEARCH_DECISIONS.has(decision)
      || !UUID_PATTERN.test(dispositionId)
      || !UUID_PATTERN.test(receiptId)
      || !UUID_PATTERN.test(projectId)
      || !UUID_PATTERN.test(runId)
      || !/^[0-9a-f]{64}$/u.test(receiptHash)
      || source.human_review_completed !== true
      || source.raw_research_enters_prompt_automatically !== false
      || source.affects_effective_policy !== false
    ) return null;
    return {
      id: dispositionId,
      receiptId,
      receiptHash,
      projectId,
      runId,
      productCategory,
      decision,
      reasonCode: cleanText(
        source.reason_code || source.reasonCode,
        120,
      ),
      projectName: cleanText(
        source.project_name || source.projectName,
        180,
      ),
      productName: cleanText(
        source.product_name || source.productName,
        240,
      ),
      title: cleanText(
        source.research_title || source.researchTitle || source.title,
        240,
      ),
      decidedBy: cleanText(
        source.decided_by || source.decidedBy,
        80,
      ),
      decidedByName: cleanText(
        source.decided_by_name || source.decidedByName,
        180,
      ),
      decidedAt: timestamp(source.decided_at || source.decidedAt),
      eventCursor: nonNegativeInteger(
        source.event_cursor ?? source.eventCursor,
        index + 1,
      ),
      deepLink: `#/workspace/research?project_id=${projectId}&run=${runId}`,
      humanReviewCompleted: true,
      affectsEffectivePolicy: false,
    };
  }).filter(Boolean).slice(0, 50);
}

function normalizeGuidance(raw, category) {
  const source = objectValue(raw) || {};
  return {
    status: cleanText(source.status, 80).toLowerCase() || category.status,
    summary: cleanText(source.summary || source.message, 800),
    recommendedNextAction: cleanText(
      source.recommended_next_action || source.recommendedNextAction,
      120,
    ).toLowerCase(),
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

function historicalOutcomeLabel(value) {
  return ({
    good: "Хорошо",
    bad: "Плохо",
    review: "Требует проверки",
  })[value] || "Требует проверки";
}

function historicalBatchStatusLabel(value) {
  return ({
    queued: "В очереди",
    processing: "Разбирается",
    completed: "Завершён",
    failed: "Ошибка",
  })[value] || "Статус неизвестен";
}

function platformLabel(value) {
  return ({
    wildberries: "Wildberries",
    wb: "Wildberries",
    ozon: "Ozon",
    instagram: "Instagram",
    youtube: "YouTube",
    vk: "VK",
  })[value] || cleanText(value, 60);
}

function formatConfidence(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value)}%`
    : "Не указана";
}

function formatHistoricalMetricValue(value, kind) {
  try {
    if (kind === "currency") {
      return new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 0,
      }).format(value);
    }
    if (kind === "percent") {
      const percent = Math.abs(value) <= 1 ? value * 100 : value;
      return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(percent)}%`;
    }
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
  } catch {
    return String(value);
  }
}

function dateOnly(value) {
  const candidate = cleanText(value, 40);
  if (!candidate) return "";
  const direct = candidate.match(/^(\d{4})-(\d{2})-(\d{2})/u);
  if (direct) return `${direct[1]}-${direct[2]}-${direct[3]}`;
  const date = new Date(candidate);
  return Number.isFinite(date.getTime()) ? date.toISOString().slice(0, 10) : "";
}

function formatHistoricalPeriod(start, end) {
  if (!start && !end) return "";
  const format = (value) => {
    if (!value) return "";
    const [year, month, day] = value.split("-");
    return [day, month, year].filter(Boolean).join(".");
  };
  if (start && end && start !== end) return `${format(start)} — ${format(end)}`;
  return format(start || end);
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
