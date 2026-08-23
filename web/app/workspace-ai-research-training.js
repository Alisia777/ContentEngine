/*
 * ContentEngine · Research -> AI Center -> editable recommendations.
 *
 * This route adapter renders a rich, governed training queue. It never trains
 * on receipt arrival alone: the operator chooses analysis blocks and scenario
 * candidates, can edit every recommendation, and confirms one append-only
 * server decision.
 */

const ROUTE = "/workspace/ai";
const RPC_QUEUE = "contentengine_ai_research_training_queue";
const RPC_DECIDE = "contentengine_decide_ai_research_training";
const ROOT_ATTRIBUTE = "data-ai-research-training-root";
const CATEGORY_KEY = "contentengine.ai-research-training.category";
const PROJECT_CONTEXT_KEY = "contentengine.desktop-v4.project";
const GENERATION_INTENT_PREFIX = "contentengine.ai-research-generation.intent.v1:";
const DECISION_INTENT_PREFIX = "contentengine.ai-research-training.decision-intent.v1:";
const DECISION_INTENT_VERSION = "ai-research-training-decision-intent-v1";
const DECISION_INSIGHT_KEYS = Object.freeze([
  "category",
  "competitors",
  "trends",
  "brief",
]);
const DECISION_EDIT_FIELDS = Object.freeze([
  "title",
  "hook",
  "spoken_script",
  "shot_list",
  "key_message",
  "visual_direction",
  "cta",
]);
const CATEGORIES = Object.freeze([
  ["cosmetics", "Косметика и уход"],
  ["baa", "БАД"],
  ["sports_food", "Спортивное питание"],
  ["food", "Еда и напитки"],
  ["household", "Товары для дома"],
  ["apparel", "Одежда и аксессуары"],
  ["electronics", "Электроника"],
  ["other", "Другая категория"],
]);
const CATEGORY_SET = new Set(CATEGORIES.map(([value]) => value));
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;

const runtime = {
  root: null,
  category: "other",
  projectId: "",
  loading: false,
  loadToken: 0,
  mutating: false,
  requestKey: "",
  mountQueued: false,
};

function routePath() {
  const apiRoute = globalThis.window?.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(globalThis.window?.location?.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const raw = String(globalThis.window?.location?.hash || "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  return new URLSearchParams(query);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function clean(value, limit = 4000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value, limit = 12) {
  return (Array.isArray(value) ? value : [])
    .slice(0, limit)
    .map((item) => {
      if (typeof item === "string") return clean(item, 600);
      if (!item || typeof item !== "object") return "";
      return clean(
        item.label || item.title || item.name || item.text || item.summary
          || item.claim || item.pain || item.objection || JSON.stringify(item),
        600,
      );
    })
    .filter(Boolean);
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function unwrap(value) {
  return object(value?.data || value);
}

function normalizedCategory(value) {
  const category = clean(value, 40).toLowerCase();
  return CATEGORY_SET.has(category) ? category : "";
}

function normalizedProjectId(value) {
  const projectId = clean(value, 80).toLowerCase();
  return UUID_PATTERN.test(projectId) ? projectId : "";
}

export function resolveTrainingProjectId({
  routeValues = [],
  storedValue = "",
} = {}) {
  const explicitValues = Array.isArray(routeValues) ? routeValues : [];
  if (explicitValues.length) {
    return explicitValues.length === 1
      ? normalizedProjectId(explicitValues[0])
      : "";
  }
  return normalizedProjectId(storedValue);
}

function storedTrainingProjectId() {
  try {
    const stored = JSON.parse(
      window.sessionStorage.getItem(PROJECT_CONTEXT_KEY) || "null",
    );
    return normalizedProjectId(stored?.id || stored?.project_id);
  } catch {
    return "";
  }
}

function currentTrainingProjectId() {
  return resolveTrainingProjectId({
    routeValues: routeParams().getAll("project_id"),
    storedValue: storedTrainingProjectId(),
  });
}

function trainingShellAccess() {
  const shell = typeof document === "undefined"
    ? null
    : document.querySelector(".workspace-shell");
  const receiptScope = clean(
    shell?.dataset?.aiResearchReceiptScope,
    20,
  ).toLowerCase();
  if (!shell && typeof document !== "undefined" && !document.documentElement) {
    return {
      allowed: true,
      receiptScope: "project",
      ownOnly: false,
      canDecide: true,
      canEdit: true,
    };
  }
  return {
    allowed: ["own", "project"].includes(receiptScope),
    receiptScope,
    ownOnly: receiptScope === "own",
    canDecide: shell?.dataset?.aiResearchCanDecide === "true",
    canEdit: shell?.dataset?.aiResearchCanEdit === "true",
  };
}

export function projectScopedTrainingPayload(payload, projectId) {
  const normalized = normalizedProjectId(projectId);
  if (!normalized) throw new Error("project_id_required");
  return { ...object(payload), project_id: normalized };
}

export function projectScopedTrainingSnapshot(
  value,
  expectedProjectId,
  receiptScope = "project",
) {
  const projectId = normalizedProjectId(expectedProjectId);
  const source = unwrap(value);
  const normalizedReceiptScope = ["own", "project"].includes(receiptScope)
    ? receiptScope
    : "none";
  if (
    !projectId
    || normalizedReceiptScope === "none"
    || normalizedProjectId(source.project_id) !== projectId
  ) {
    return null;
  }
  const exactProjectItems = (items) => {
    const candidates = Array.isArray(items) ? items : [];
    if (normalizedReceiptScope === "own") {
      if (candidates.some((item) => (
        normalizedProjectId(item?.project_id) !== projectId
        || item?.ownership !== "own"
      ))) return null;
      return candidates;
    }
    return candidates.filter((item) => (
      normalizedProjectId(item?.project_id) === projectId
    ));
  };
  const queue = exactProjectItems(source.queue);
  const learned = exactProjectItems(source.learned);
  if (!queue || !learned) return null;
  return {
    ...source,
    project_id: projectId,
    queue,
    learned,
  };
}

function categoryLabel(value) {
  const category = normalizedCategory(value) || "other";
  return CATEGORIES.find(([key]) => key === category)?.[1] || "Другая категория";
}

function routeCategory() {
  const params = routeParams();
  return normalizedCategory(
    params.get("category") || params.get("product_category") || "",
  );
}

function routeReceipt() {
  const params = routeParams();
  const values = params.getAll("receipt");
  if (!values.length) return { requested: false, valid: true, id: "" };
  const id = values.length === 1
    ? clean(values[0], 80).toLowerCase()
    : "";
  return {
    requested: true,
    valid: values.length === 1 && UUID_PATTERN.test(id),
    id,
  };
}

function legacyCategoryControlVisible(control) {
  if (!control || control.hidden || control.closest?.("[hidden]")) return false;
  if (control.getAttribute?.("aria-hidden") === "true") return false;
  const style = globalThis.window?.getComputedStyle?.(control);
  return !style || (style.display !== "none" && style.visibility !== "hidden");
}

function selectedLegacyCategory() {
  if (typeof document === "undefined") return "";
  const controls = document.querySelectorAll(
    '.ai-learning-category[aria-pressed="true"][data-category-key]',
  );
  for (const control of controls) {
    if (!legacyCategoryControlVisible(control)) continue;
    const category = normalizedCategory(control.dataset?.categoryKey);
    if (category) return category;
  }
  return "";
}

export function resolveTrainingCategory({
  routeValue = "",
  legacyValue = "",
  selectValue = "",
  storedValue = "",
} = {}) {
  return normalizedCategory(routeValue)
    || normalizedCategory(legacyValue)
    || normalizedCategory(selectValue)
    || normalizedCategory(storedValue)
    || "other";
}

function currentCategory() {
  const explicitRouteCategory = routeCategory();
  const visibleLegacyCategory = selectedLegacyCategory();
  const existing = typeof document === "undefined"
    ? null
    : document.querySelector('[data-ai-category-select]');
  const existingValue = normalizedCategory(existing?.value);
  let storedValue = "";
  try {
    storedValue = window.sessionStorage.getItem(CATEGORY_KEY) || "";
  } catch {
    // Optional route memory.
  }
  return resolveTrainingCategory({
    routeValue: explicitRouteCategory,
    legacyValue: visibleLegacyCategory,
    selectValue: existingValue,
    storedValue,
  });
}

function rememberCategory(category) {
  const normalized = normalizedCategory(category);
  if (!normalized) return;
  try {
    window.sessionStorage.setItem(CATEGORY_KEY, normalized);
  } catch {
    // Optional route memory.
  }
}

export function trainingCategoryHash(category, rawHash = "#/workspace/ai") {
  const normalized = normalizedCategory(category) || "other";
  const raw = String(rawHash || "#/workspace/ai").replace(/^#/, "");
  const separator = raw.indexOf("?");
  const rawPath = separator >= 0 ? raw.slice(0, separator) : raw;
  const rawQuery = separator >= 0 ? raw.slice(separator + 1) : "";
  const path = (`/${rawPath || "workspace/ai"}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || ROUTE;
  const params = new URLSearchParams(rawQuery);
  params.set("category", normalized);
  return `#${path}?${params.toString()}`;
}

export function trainingProjectHash(projectId, rawHash = "#/workspace/ai") {
  const normalized = normalizedProjectId(projectId);
  if (!normalized) throw new Error("project_id_required");
  const raw = String(rawHash || "#/workspace/ai").replace(/^#/, "");
  const separator = raw.indexOf("?");
  const rawPath = separator >= 0 ? raw.slice(0, separator) : raw;
  const rawQuery = separator >= 0 ? raw.slice(separator + 1) : "";
  const path = (`/${rawPath || "workspace/ai"}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || ROUTE;
  const params = new URLSearchParams(rawQuery);
  params.delete("project_id");
  params.set("project_id", normalized);
  return `#${path}?${params.toString()}`;
}

function canonicalizeTrainingRoute(category, projectId) {
  if (typeof window === "undefined") return false;
  const routeProjectValues = routeParams().getAll("project_id");
  if (
    routeProjectValues.length === 1
    && normalizedProjectId(routeProjectValues[0]) === projectId
  ) return false;
  if (routeProjectValues.length) return false;
  const categoryHash = trainingCategoryHash(category, window.location.hash);
  const nextHash = trainingProjectHash(projectId, categoryHash);
  window.history?.replaceState?.(window.history.state, "", nextHash);
  return true;
}

function syncLegacyCategoryButtons(category) {
  if (typeof document === "undefined") return;
  document.querySelectorAll(
    ".ai-learning-category[data-category-key]",
  ).forEach((control) => {
    const selected = normalizedCategory(control.dataset?.categoryKey) === category;
    control.setAttribute("aria-pressed", selected ? "true" : "false");
    control.classList?.toggle("is-active", selected);
  });
}

function syncTrainingCategorySelect(category) {
  const select = runtime.root?.querySelector("[data-training-category]");
  if (select instanceof HTMLSelectElement && select.value !== category) {
    select.value = category;
  }
}

function updateCategoryRoute(category) {
  const nextHash = trainingCategoryHash(category, window.location.hash);
  if (nextHash === window.location.hash) return false;
  window.location.hash = nextHash;
  return true;
}

function restoreProjectScopeAfterLegacyNavigation(category, projectId) {
  if (!projectId || typeof window === "undefined") return;
  const params = routeParams();
  if (params.get("project_id") === projectId && routeCategory() === category) {
    return;
  }
  const nextHash = trainingCategoryHash(category, window.location.hash);
  const separator = nextHash.indexOf("?");
  const path = separator >= 0 ? nextHash.slice(0, separator) : nextHash;
  const nextParams = new URLSearchParams(
    separator >= 0 ? nextHash.slice(separator + 1) : "",
  );
  nextParams.set("project_id", projectId);
  const restoredHash = `${path}?${nextParams.toString()}`;
  window.history?.replaceState?.(window.history.state, "", restoredHash);
}

function payloadWithOrganization(api, payload) {
  if (typeof api?.withOrganization === "function") {
    return api.withOrganization(payload);
  }
  if (api?.organizationId) {
    return { organization_id: api.organizationId, ...payload };
  }
  return payload;
}

async function getApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return api;
}

function idempotencyKey(prefix) {
  const uuid = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${uuid}`.slice(0, 178);
}

function decisionError(code, message, cause = null) {
  const error = new Error(message);
  error.name = "AiResearchTrainingDecisionError";
  error.code = code;
  if (cause) error.cause = cause;
  return error;
}

function decisionText(value) {
  return String(value ?? "").replace(/\r\n?/gu, "\n").trim();
}

function decisionUuid(value) {
  return normalizedProjectId(value);
}

function normalizedDecisionList(values, allowed) {
  const selected = new Set(
    (Array.isArray(values) ? values : [])
      .map((value) => clean(value, 40).toLowerCase())
      .filter((value) => allowed.includes(value)),
  );
  return allowed.filter((value) => selected.has(value));
}

function normalizedDecisionPositions(values) {
  return [...new Set(
    (Array.isArray(values) ? values : [])
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3),
  )].sort((left, right) => left - right);
}

function normalizedDecisionEdits(values, positions) {
  if (!Array.isArray(values)) return [];
  const selected = new Set(positions);
  const byPosition = new Map();
  values.forEach((value) => {
    const source = object(value);
    const position = Number(source.position);
    if (!selected.has(position) || byPosition.has(position)) return;
    const edit = { position };
    DECISION_EDIT_FIELDS.forEach((fieldName) => {
      edit[fieldName] = decisionText(source[fieldName]);
    });
    byPosition.set(position, edit);
  });
  return positions
    .filter((position) => byPosition.has(position))
    .map((position) => byPosition.get(position));
}

export function normalizeTrainingDecisionScope(value = {}) {
  const source = object(value);
  const scope = {
    actorId: decisionUuid(source.actorId || source.actor_id),
    organizationId: decisionUuid(
      source.organizationId || source.organization_id,
    ),
    projectId: decisionUuid(source.projectId || source.project_id),
    receiptId: decisionUuid(source.receiptId || source.receipt_id),
  };
  return Object.values(scope).every(Boolean) ? scope : null;
}

export function canonicalTrainingDecisionRequest(value = {}) {
  const source = object(value);
  const decision = clean(source.decision, 20).toLowerCase();
  const positions = decision === "approve"
    ? normalizedDecisionPositions(source.selected_scenario_positions)
    : [];
  const request = {
    organization_id: decisionUuid(source.organization_id),
    project_id: decisionUuid(source.project_id),
    product_category: normalizedCategory(source.product_category),
    receipt_id: decisionUuid(source.receipt_id),
    receipt_hash: clean(source.receipt_hash, 80).toLowerCase(),
    decision,
    selected_insight_keys: decision === "approve"
      ? normalizedDecisionList(
          source.selected_insight_keys,
          DECISION_INSIGHT_KEYS,
        )
      : [],
    selected_scenario_positions: positions,
    edits: decision === "approve"
      ? normalizedDecisionEdits(source.edits, positions)
      : [],
    operator_notes: decisionText(source.operator_notes),
    confirmation: source.confirmation === true,
  };
  if (
    !request.organization_id
    || !request.project_id
    || !request.product_category
    || !request.receipt_id
    || !/^[0-9a-f]{64}$/u.test(request.receipt_hash)
    || !["approve", "reject"].includes(request.decision)
    || request.confirmation !== true
    || (
      request.decision === "approve"
      && (
        !request.selected_insight_keys.length
        || !request.selected_scenario_positions.length
      )
    )
  ) {
    throw decisionError(
      "ai_research_training_decision_scope_invalid",
      "Не удалось зафиксировать точный контур выбранного решения. Обновите ИИ-центр и повторите выбор.",
    );
  }
  return request;
}

function trainingDecisionIntentFingerprint(scopeValue, requestValue) {
  const scope = normalizeTrainingDecisionScope(scopeValue);
  const request = canonicalTrainingDecisionRequest(requestValue);
  if (!scope) return "";
  return JSON.stringify({
    actor_id: scope.actorId,
    organization_id: scope.organizationId,
    project_id: scope.projectId,
    receipt_id: scope.receiptId,
    request,
  });
}

export function trainingDecisionIntentStorageKey(scopeValue) {
  const scope = normalizeTrainingDecisionScope(scopeValue);
  if (!scope) {
    throw decisionError(
      "ai_research_training_decision_scope_invalid",
      "Не удалось определить пользователя, команду, проект и чек решения.",
    );
  }
  return `${DECISION_INTENT_PREFIX}${[
    scope.actorId,
    scope.organizationId,
    scope.projectId,
    scope.receiptId,
  ].join(":")}`;
}

function validDecisionIdempotencyKey(value) {
  const key = String(value || "").trim().toLowerCase();
  return /^[a-z0-9][a-z0-9._:-]{7,177}$/u.test(key) ? key : "";
}

function sameDecisionScope(left, right) {
  const a = normalizeTrainingDecisionScope(left);
  const b = normalizeTrainingDecisionScope(right);
  return Boolean(
    a
    && b
    && a.actorId === b.actorId
    && a.organizationId === b.organizationId
    && a.projectId === b.projectId
    && a.receiptId === b.receiptId,
  );
}

function readTrainingDecisionIntent(storage, scope) {
  const key = trainingDecisionIntentStorageKey(scope);
  let parsed = null;
  try {
    parsed = JSON.parse(storage?.getItem?.(key) || "null");
  } catch {
    parsed = null;
  }
  const createdAt = Number(parsed?.created_at);
  const idempotencyKeyValue = validDecisionIdempotencyKey(
    parsed?.idempotency_key,
  );
  let request = null;
  try {
    request = canonicalTrainingDecisionRequest(parsed?.request);
  } catch {
    request = null;
  }
  const valid = parsed?.version === DECISION_INTENT_VERSION
    && sameDecisionScope(parsed?.scope, scope)
    && idempotencyKeyValue
    && request
    && parsed?.request_fingerprint
      === trainingDecisionIntentFingerprint(scope, request)
    && Number.isFinite(createdAt)
    && createdAt > 0;
  if (!valid) {
    try {
      storage?.removeItem?.(key);
    } catch {
      // A broken storage backend must not make a stale intent reusable.
    }
    return null;
  }
  return {
    version: DECISION_INTENT_VERSION,
    scope: normalizeTrainingDecisionScope(scope),
    request,
    requestFingerprint: parsed.request_fingerprint,
    idempotencyKey: idempotencyKeyValue,
    createdAt,
  };
}

function writeTrainingDecisionIntent(storage, intent) {
  const key = trainingDecisionIntentStorageKey(intent.scope);
  const record = {
    version: DECISION_INTENT_VERSION,
    scope: {
      actor_id: intent.scope.actorId,
      organization_id: intent.scope.organizationId,
      project_id: intent.scope.projectId,
      receipt_id: intent.scope.receiptId,
    },
    request: intent.request,
    request_fingerprint: intent.requestFingerprint,
    idempotency_key: intent.idempotencyKey,
    created_at: intent.createdAt,
  };
  try {
    storage?.setItem?.(key, JSON.stringify(record));
  } catch (cause) {
    throw decisionError(
      "ai_research_training_decision_storage_unavailable",
      "Браузер не смог сохранить ключ безопасного повтора. Решение не отправлено.",
      cause,
    );
  }
  const persisted = readTrainingDecisionIntent(
    storage,
    intent.scope,
  );
  if (!persisted || persisted.idempotencyKey !== intent.idempotencyKey) {
    throw decisionError(
      "ai_research_training_decision_storage_unavailable",
      "Браузер не подтвердил сохранение ключа безопасного повтора. Решение не отправлено.",
    );
  }
  return persisted;
}

export function clearTrainingDecisionIntent(storage, scope) {
  try {
    storage?.removeItem?.(trainingDecisionIntentStorageKey(scope));
  } catch {
    // Terminal state is authoritative even if optional browser cleanup fails.
  }
}

function acquireTrainingDecisionIntent({
  storage,
  scope: scopeValue,
  request: requestValue,
  createIdempotencyKey = () => idempotencyKey("research-training"),
  now = Date.now(),
}) {
  const scope = normalizeTrainingDecisionScope(scopeValue);
  const request = canonicalTrainingDecisionRequest(requestValue);
  if (
    !scope
    || scope.organizationId !== request.organization_id
    || scope.projectId !== request.project_id
    || scope.receiptId !== request.receipt_id
  ) {
    throw decisionError(
      "ai_research_training_decision_scope_invalid",
      "Контур решения не совпал с текущими пользователем, командой, проектом и чеком.",
    );
  }
  const requestFingerprint = trainingDecisionIntentFingerprint(scope, request);
  const existing = readTrainingDecisionIntent(storage, scope);
  if (existing) {
    return {
      intent: existing,
      existed: true,
      requestMatches: existing.requestFingerprint === requestFingerprint,
      requested: request,
    };
  }
  const idempotencyKeyValue = validDecisionIdempotencyKey(
    createIdempotencyKey(),
  );
  if (!idempotencyKeyValue) {
    throw decisionError(
      "ai_research_training_decision_idempotency_invalid",
      "Не удалось создать безопасный ключ решения. Решение не отправлено.",
    );
  }
  const intent = writeTrainingDecisionIntent(storage, {
    version: DECISION_INTENT_VERSION,
    scope,
    request,
    requestFingerprint,
    idempotencyKey: idempotencyKeyValue,
    createdAt: now,
  });
  return {
    intent,
    existed: false,
    requestMatches: true,
    requested: request,
  };
}

function decisionArrayEquals(left, right) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => value === right[index]);
}

function decisionRecommendationText(value) {
  if (Array.isArray(value)) return decisionText(value.join("\n"));
  return decisionText(value);
}

function selectionMatchesTrainingDecision(selectionValue, intent) {
  const selection = object(selectionValue);
  const request = intent.request;
  if (
    !decisionUuid(selection.selection_id)
    || decisionUuid(selection.receipt_id) !== intent.scope.receiptId
    || decisionUuid(selection.project_id) !== intent.scope.projectId
    || decisionUuid(selection.selected_by) !== intent.scope.actorId
    || clean(selection.receipt_hash, 80).toLowerCase()
      !== request.receipt_hash
    || normalizedCategory(selection.product_category)
      !== request.product_category
    || clean(selection.decision, 20).toLowerCase() !== request.decision
    || !decisionArrayEquals(
      normalizedDecisionList(
        selection.selected_insight_keys,
        DECISION_INSIGHT_KEYS,
      ),
      request.selected_insight_keys,
    )
    || !decisionArrayEquals(
      normalizedDecisionPositions(selection.selected_scenario_positions),
      request.selected_scenario_positions,
    )
    || decisionText(selection.operator_notes) !== request.operator_notes
  ) return false;
  if (request.decision !== "approve") return true;
  const recommendations = Array.isArray(selection.recommendations)
    ? selection.recommendations
    : [];
  return request.edits.every((edit) => {
    const recommendation = recommendations.find((candidate) => (
      Number(candidate?.position) === edit.position
    ));
    if (!recommendation) return false;
    return DECISION_EDIT_FIELDS.every((fieldName) => {
      const expected = decisionText(edit[fieldName]);
      if (!expected) return true;
      return decisionRecommendationText(recommendation[fieldName]) === expected;
    });
  });
}

function trainingDecisionSnapshot(value) {
  const source = unwrap(value);
  const nested = object(source.snapshot);
  return Object.keys(nested).length ? unwrap(nested) : source;
}

export function classifyTrainingDecisionSnapshot(
  value,
  intentValue,
  receiptScope = "project",
) {
  const intent = object(intentValue);
  const scope = normalizeTrainingDecisionScope(intent.scope);
  if (!scope || !intent.request) return { state: "invalid", snapshot: null };
  const snapshot = trainingDecisionSnapshot(value);
  if (decisionUuid(snapshot.organization_id) !== scope.organizationId) {
    return { state: "invalid", snapshot: null };
  }
  const scoped = projectScopedTrainingSnapshot(
    snapshot,
    scope.projectId,
    receiptScope,
  );
  if (
    !scoped
    || normalizedCategory(scoped.product_category)
      !== intent.request.product_category
  ) return { state: "invalid", snapshot: null };
  const learned = (Array.isArray(scoped.learned) ? scoped.learned : [])
    .filter((selection) => (
      decisionUuid(selection?.receipt_id) === scope.receiptId
    ));
  const matched = learned.find((selection) => (
    selectionMatchesTrainingDecision(selection, intent)
  ));
  if (matched) return { state: "matched", snapshot: scoped, selection: matched };
  if (learned.length) {
    return { state: "conflict", snapshot: scoped, selection: learned[0] };
  }
  const queue = (Array.isArray(scoped.queue) ? scoped.queue : [])
    .filter((receipt) => (
      decisionUuid(receipt?.receipt_id) === scope.receiptId
      && clean(receipt?.receipt_hash, 80).toLowerCase()
        === intent.request.receipt_hash
    ));
  if (queue.length) return { state: "pending", snapshot: scoped };
  return { state: "unavailable", snapshot: scoped };
}

function trainingDecisionServerCode(error) {
  const candidates = [
    error?.serverCode,
    error?.server_code,
    error?.details?.serverCode,
    error?.details?.server_code,
    error?.details?.message,
    error?.code,
    error?.message,
  ];
  return candidates
    .map((value) => String(value || "").trim().toLowerCase())
    .find((value) => /^[a-z][a-z0-9_]{2,95}$/u.test(value)) || "";
}

function terminalTrainingDecisionError(error) {
  const code = trainingDecisionServerCode(error);
  if (new Set([
    "ai_research_training_decision_response_ambiguous",
    "ai_research_training_decision_unconfirmed",
    "ai_research_training_decision_reconcile_unavailable",
    "ai_research_training_decision_reconcile_invalid",
  ]).has(code)) return false;
  return code.startsWith("ai_research_training_")
    || new Set([
      "authentication_required",
      "auth_session_required",
      "auth_session_actor_changed",
      "auth_session_actor_invalid",
      "auth_session_context_changed",
      "membership_required",
      "project_not_found",
      "rpc_transport_config_invalid",
      "role_not_allowed",
    ]).has(code);
}

async function reconcileTrainingDecision({
  storage,
  intent,
  reload,
  receiptScope,
  originalError = null,
}) {
  let snapshotResponse;
  try {
    snapshotResponse = await reload();
  } catch (cause) {
    if (
      originalError
      && terminalTrainingDecisionError(originalError)
      && trainingDecisionServerCode(originalError)
        !== "ai_research_training_already_decided"
    ) {
      clearTrainingDecisionIntent(storage, intent.scope);
      throw originalError;
    }
    throw decisionError(
      "ai_research_training_decision_reconcile_unavailable",
      "Итог решения пока нельзя подтвердить по точному чеку. Новый запрос не отправлен; повторите тот же выбор после восстановления связи.",
      originalError || cause,
    );
  }
  const resolution = classifyTrainingDecisionSnapshot(
    snapshotResponse,
    intent,
    receiptScope,
  );
  if (
    resolution.state === "invalid"
    && originalError
    && terminalTrainingDecisionError(originalError)
    && trainingDecisionServerCode(originalError)
      !== "ai_research_training_already_decided"
  ) {
    clearTrainingDecisionIntent(storage, intent.scope);
    throw originalError;
  }
  if (resolution.state === "matched") {
    clearTrainingDecisionIntent(storage, intent.scope);
    return {
      status: "success",
      recovered: true,
      snapshot: resolution.snapshot,
      selection: resolution.selection,
      intent,
    };
  }
  if (resolution.state === "conflict") {
    clearTrainingDecisionIntent(storage, intent.scope);
    const error = decisionError(
      "ai_research_training_decision_conflict",
      "По этому чеку уже сохранено другое неизменяемое решение. Показан авторитетный серверный результат; новое решение не создавалось.",
      originalError,
    );
    error.snapshot = resolution.snapshot;
    throw error;
  }
  if (resolution.state === "unavailable") {
    clearTrainingDecisionIntent(storage, intent.scope);
    const error = decisionError(
      "ai_research_training_receipt_unavailable",
      "Точный чек больше не доступен в очереди или истории. Новое решение не создавалось.",
      originalError,
    );
    error.snapshot = resolution.snapshot;
    throw error;
  }
  if (resolution.state === "pending" && originalError) {
    if (
      terminalTrainingDecisionError(originalError)
      && trainingDecisionServerCode(originalError)
        !== "ai_research_training_already_decided"
    ) {
      clearTrainingDecisionIntent(storage, intent.scope);
      throw originalError;
    }
    throw decisionError(
      "ai_research_training_decision_unconfirmed",
      "Сервер пока не подтвердил фиксацию решения. Ключ безопасного повтора сохранён; повторите тот же выбор — новый логический запрос создан не будет.",
      originalError,
    );
  }
  if (resolution.state === "pending") return resolution;
  throw decisionError(
    "ai_research_training_decision_reconcile_invalid",
    "Сервер вернул ответ не из текущего контура пользователя, команды, проекта и чека. Решение повторно не отправлено.",
    originalError,
  );
}

export async function performTrainingDecisionMutation({
  storage,
  scope,
  request,
  send,
  reload,
  receiptScope = "project",
  createIdempotencyKey,
  now = Date.now(),
} = {}) {
  if (typeof send !== "function" || typeof reload !== "function") {
    throw decisionError(
      "ai_research_training_decision_transport_invalid",
      "Сервис решения или точной сверки недоступен. Решение не отправлено.",
    );
  }
  let acquired = acquireTrainingDecisionIntent({
    storage,
    scope,
    request,
    createIdempotencyKey,
    now,
  });
  if (acquired.existed) {
    const beforeRetry = await reconcileTrainingDecision({
      storage,
      intent: acquired.intent,
      reload,
      receiptScope,
    });
    if (beforeRetry.state !== "pending") return beforeRetry;
    if (!acquired.requestMatches) {
      clearTrainingDecisionIntent(storage, acquired.intent.scope);
      acquired = acquireTrainingDecisionIntent({
        storage,
        scope,
        request: acquired.requested,
        createIdempotencyKey,
        now,
      });
    }
  }

  const intent = acquired.intent;
  let response;
  try {
    response = await send({
      ...intent.request,
      idempotency_key: intent.idempotencyKey,
    });
  } catch (error) {
    return reconcileTrainingDecision({
      storage,
      intent,
      reload,
      receiptScope,
      originalError: error,
    });
  }

  const direct = classifyTrainingDecisionSnapshot(
    response,
    intent,
    receiptScope,
  );
  if (direct.state === "matched") {
    clearTrainingDecisionIntent(storage, intent.scope);
    return {
      status: "success",
      recovered: false,
      snapshot: direct.snapshot,
      selection: direct.selection,
      intent,
    };
  }
  if (direct.state === "conflict") {
    clearTrainingDecisionIntent(storage, intent.scope);
    const error = decisionError(
      "ai_research_training_decision_conflict",
      "Сервер подтвердил другое неизменяемое решение по этому чеку. Новое решение не создавалось.",
    );
    error.snapshot = direct.snapshot;
    throw error;
  }
  return reconcileTrainingDecision({
    storage,
    intent,
    reload,
    receiptScope,
    originalError: decisionError(
      "ai_research_training_decision_response_ambiguous",
      "Ответ фиксации потерян или неполон.",
    ),
  });
}

async function authenticatedTrainingDecisionScope(api, projectId, receiptId) {
  const getSession = api?.supabase?.auth?.getSession;
  if (typeof getSession !== "function") {
    throw decisionError(
      "auth_session_required",
      "Не удалось подтвердить текущего пользователя. Решение не отправлено.",
    );
  }
  const { data, error } = await getSession.call(api.supabase.auth);
  const actorId = decisionUuid(data?.session?.user?.id);
  const organizationId = decisionUuid(api?.organizationId);
  if (error || !actorId || !organizationId) {
    throw decisionError(
      "auth_session_required",
      "Сессия пользователя или команда не подтверждены. Войдите снова перед решением.",
      error,
    );
  }
  const sharedContext = window.ContentEngineWorkspaceRuntime
    ?.getExactYoutubeHandoffContext?.() || {};
  const contextActorId = decisionUuid(sharedContext.user_id);
  const contextOrganizationId = decisionUuid(sharedContext.organization_id);
  const contextProjectId = decisionUuid(sharedContext.project_id);
  if (
    (contextActorId && contextActorId !== actorId)
    || (
      contextOrganizationId
      && contextOrganizationId !== organizationId
    )
    || (contextProjectId && contextProjectId !== projectId)
  ) {
    throw decisionError(
      "ai_research_training_decision_scope_changed",
      "Пользователь, команда или проект изменились перед отправкой. Решение не отправлено.",
    );
  }
  const scope = normalizeTrainingDecisionScope({
    actorId,
    organizationId,
    projectId,
    receiptId,
  });
  if (!scope) {
    throw decisionError(
      "ai_research_training_decision_scope_invalid",
      "Не удалось подтвердить точный контур решения. Решение не отправлено.",
    );
  }
  return scope;
}

function trainingDecisionStorage() {
  try {
    return window.sessionStorage;
  } catch (cause) {
    throw decisionError(
      "ai_research_training_decision_storage_unavailable",
      "Хранилище безопасного повтора недоступно. Решение не отправлено.",
      cause,
    );
  }
}

function setStatus(root, message, tone = "neutral") {
  const target = root.querySelector("[data-ai-research-training-status]");
  if (!target) return;
  target.textContent = message;
  target.dataset.tone = tone;
}

function addTextList(parent, values, emptyText = "Нет подтверждённых пунктов") {
  const items = list(values);
  if (!items.length) {
    parent.append(el("p", "ai-research-training__empty-copy", emptyText));
    return;
  }
  const ul = el("ul", "ai-research-training__bullets");
  items.forEach((item) => ul.append(el("li", "", item)));
  parent.append(ul);
}

function insightCard({ key, title, description, content, disabled = false }) {
  const label = el("label", "ai-research-training__insight");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  // Analysis blocks are suggestions too; approval requires a human check.
  checkbox.checked = false;
  checkbox.disabled = disabled;
  checkbox.dataset.insightKey = key;
  const body = el("span", "ai-research-training__insight-body");
  const head = el("span", "ai-research-training__insight-title");
  head.append(el("strong", "", title), el("small", "", description));
  const detail = el("span", "ai-research-training__insight-detail");
  if (typeof content === "string") detail.textContent = content;
  else if (content instanceof Node) detail.append(content);
  body.append(head, detail);
  label.append(checkbox, body);
  return label;
}

function categoryInsight(analysis, disabled = false) {
  const category = object(analysis.category_analysis);
  const block = el("span");
  const summary = clean(category.definition || category.summary || category.category_name, 900);
  if (summary) block.append(el("span", "", summary));
  const jobs = list(category.buyer_jobs || category.jobs, 6);
  if (jobs.length) {
    const jobsLine = el("small", "");
    jobsLine.textContent = `Задачи покупателя: ${jobs.join(" · ")}`;
    block.append(jobsLine);
  }
  return insightCard({
    key: "category",
    title: "Категория и покупатель",
    description: "Что человек пытается решить товаром",
    content: block,
    disabled,
  });
}

function competitorInsight(analysis, disabled = false) {
  const competitors = object(analysis.competitor_analysis);
  const block = el("span");
  const reusable = list(
    competitors.reusable_structures || competitors.content_gaps
      || competitors.opportunities,
    6,
  );
  const saturated = list(competitors.saturated_patterns, 4);
  if (reusable.length) {
    const line = el("span");
    line.textContent = `Можно использовать: ${reusable.join(" · ")}`;
    block.append(line);
  }
  if (saturated.length) {
    const line = el("small");
    line.textContent = `Не повторять вслепую: ${saturated.join(" · ")}`;
    block.append(line);
  }
  return insightCard({
    key: "competitors",
    title: "Конкуренты и насыщенные приёмы",
    description: "Структуры для адаптации, а не копирования",
    content: block,
    disabled,
  });
}

function trendInsight(analysis, disabled = false) {
  const trends = object(analysis.trend_analysis);
  const signals = Array.isArray(trends.signals) ? trends.signals.slice(0, 6) : [];
  const block = el("span");
  if (signals.length) {
    const ul = el("ul", "ai-research-training__compact-list");
    signals.forEach((signal) => {
      const source = object(signal);
      const name = clean(source.name || source.signal || source.title, 260);
      const direction = clean(source.direction, 80);
      const use = clean(source.recommended_use || source.use, 240);
      if (!name && !use) return;
      ul.append(el(
        "li",
        "",
        [name, direction && `(${direction})`, use].filter(Boolean).join(" — "),
      ));
    });
    block.append(ul);
  }
  return insightCard({
    key: "trends",
    title: "Тренды и свежие сигналы",
    description: "Только подтверждённые или честно помеченные гипотезы",
    content: block,
    disabled,
  });
}

function briefInsight(brief, disabled = false) {
  const block = el("span");
  const audience = list(brief.audience, 4);
  const pains = list(brief.pains, 4);
  const objections = list(brief.objections, 4);
  const lines = [
    audience.length ? `Аудитория: ${audience.join(" · ")}` : "",
    pains.length ? `Боли: ${pains.join(" · ")}` : "",
    objections.length ? `Возражения: ${objections.join(" · ")}` : "",
  ].filter(Boolean);
  lines.forEach((line, index) => block.append(el(index ? "small" : "span", "", line)));
  return insightCard({
    key: "brief",
    title: "Коммуникационная рамка",
    description: "Аудитория, боли, возражения и доказательства",
    content: block,
    disabled,
  });
}

function shotListText(value) {
  if (typeof value === "string") return value.trim();
  if (!Array.isArray(value)) return "";
  return value.slice(0, 12).map((shot) => {
    if (typeof shot === "string") return shot.trim();
    const source = object(shot);
    const seconds = clean(source.seconds || source.time || source.duration, 60);
    const visual = clean(source.visual || source.shot || source.description, 700);
    const text = clean(source.on_screen_text || source.text, 300);
    return [seconds && `${seconds}:`, visual, text && `Текст: ${text}`]
      .filter(Boolean)
      .join(" ");
  }).filter(Boolean).join("\n");
}

function field(
  labelText,
  value,
  name,
  { textarea = false, rows = 2, disabled = false } = {},
) {
  const label = el("label", "field ai-research-training__edit-field");
  label.append(el("span", "", labelText));
  const control = el(textarea ? "textarea" : "input");
  control.name = name;
  control.value = String(value || "");
  if (textarea) control.rows = rows;
  control.maxLength = textarea ? 5000 : 1500;
  control.disabled = disabled;
  label.append(control);
  return label;
}

function scenarioCard(scenario, position, { disabled = false } = {}) {
  const source = object(scenario);
  const card = el("article", "ai-research-training__scenario");
  card.dataset.scenarioPosition = String(position);
  const header = el("header", "ai-research-training__scenario-header");
  const select = el("label", "ai-research-training__scenario-select");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  // Every recommendation is advisory: even position 1 waits for a human choice.
  checkbox.checked = false;
  checkbox.disabled = disabled;
  checkbox.dataset.scenarioSelect = String(position);
  select.append(
    checkbox,
    el("strong", "", `Рекомендация ${position}`),
  );
  const mode = clean(source.recommended_generation_mode, 80);
  header.append(select, el("span", "ai-research-training__scenario-mode", mode || "сценарий"));

  const grid = el("div", "ai-research-training__scenario-grid");
  grid.append(
    field("Название", source.title, "title", { disabled }),
    field("Хук", source.hook, "hook", { textarea: true, rows: 2, disabled }),
    field(
      "Реплика / сценарий",
      source.spoken_script || source.script,
      "spoken_script",
      { textarea: true, rows: 4, disabled },
    ),
    field(
      "Кадры",
      shotListText(source.shot_list || source.shots),
      "shot_list",
      { textarea: true, rows: 5, disabled },
    ),
    field("Ключевое сообщение", source.goal || source.angle, "key_message", { textarea: true, rows: 2, disabled }),
    field("Визуальное направление", source.angle, "visual_direction", { textarea: true, rows: 2, disabled }),
    field("CTA", source.cta, "cta", { textarea: true, rows: 2, disabled }),
  );
  const evidence = el("div", "ai-research-training__scenario-evidence");
  const proof = list(source.proof_points, 6);
  const risks = list(source.risks, 6);
  if (proof.length) evidence.append(el("p", "", `Доказательства: ${proof.join(" · ")}`));
  if (risks.length) evidence.append(el("p", "", `Ограничения: ${risks.join(" · ")}`));
  card.append(header, grid, evidence);
  return card;
}

function sourceCard(source) {
  const item = object(source);
  const card = el("article", "ai-research-training__source");
  const externalUrl = safeUrl(
    item.source_url || item.preview_url || item.media_url || item.download_url,
  );
  const projectId = clean(item.project_id, 80).toLowerCase();
  const mediaId = clean(item.media_object_id, 80).toLowerCase();
  const projectFileUrl = UUID_PATTERN.test(projectId) && UUID_PATTERN.test(mediaId)
    ? `#/workspace/board?project_id=${encodeURIComponent(projectId)}&folder=all&media=${encodeURIComponent(mediaId)}`
    : "";
  const url = externalUrl || projectFileUrl;
  const title = clean(item.title, 300) || "Источник исследования";
  const heading = url ? el("a", "", title) : el("strong", "", title);
  if (url) {
    heading.href = url;
    if (externalUrl) {
      heading.target = "_blank";
      heading.rel = "noopener noreferrer";
    }
  }
  const meta = el("small", "", [
    clean(item.source_type, 80),
    clean(item.trust_level, 80),
    item.media_object_id ? "файл проекта" : "",
  ].filter(Boolean).join(" · "));
  card.append(heading, meta);
  const analysis = object(item.analysis);
  const summary = clean(analysis.summary, 1000);
  if (summary) card.append(el("p", "", summary));
  const signals = list(analysis.structural_signal_keys, 8);
  if (signals.length) card.append(el("small", "", `Сигналы: ${signals.join(" · ")}`));
  if (!summary && externalUrl) {
    card.append(el(
      "p",
      "ai-research-training__source-limit",
      "Ссылка сохранена. Показываем только реально доступный разбор; кадры или расшифровку не выдумываем.",
    ));
  }
  return card;
}

function normalizeLearnedSource(value) {
  const source = object(value);
  const media = object(source.media);
  return {
    ...source,
    title: firstText(
      source.title,
      media.filename,
      source.filename,
      "Источник исследования",
    ),
    media_object_id: firstText(
      source.media_object_id,
      media.media_object_id,
    ),
    project_id: firstText(source.project_id, media.project_id),
    mime_type: firstText(source.mime_type, media.mime_type),
    status: firstText(source.status, media.status),
  };
}

function mergeLearnedSources(source) {
  const candidates = [
    source.source_snapshot,
    source.material_snapshot,
    source.sources,
    source.materials,
    source.material,
  ].flatMap((value) => (Array.isArray(value) ? value : []));
  const merged = new Map();
  candidates.forEach((value, index) => {
    const normalized = normalizeLearnedSource(value);
    const key = firstText(
      normalized.source_id,
      normalized.media_object_id,
      normalized.source_url,
      `${normalized.title}:${index}`,
    );
    const existing = merged.get(key);
    merged.set(key, existing
      ? {
          ...existing,
          ...normalized,
          analysis: {
            ...object(existing.analysis),
            ...object(normalized.analysis),
          },
        }
      : normalized);
  });
  return [...merged.values()].slice(0, 24);
}

function firstText(...values) {
  for (const value of values) {
    if (typeof value === "string" || typeof value === "number") {
      const result = clean(value, 2000);
      if (result) return result;
    }
  }
  return "";
}

function normalizeResearchSummary(value) {
  if (typeof value === "string") {
    return { headline: clean(value, 2000), conclusions: [], limitations: [] };
  }
  const source = object(value);
  return {
    headline: firstText(
      source.executive_summary,
      source.summary,
      source.overview,
      source.result,
      source.conclusion,
    ),
    conclusions: list(
      source.conclusions || source.key_findings || source.findings
        || source.results || source.takeaways,
      12,
    ),
    limitations: list(source.limitations || source.caveats, 8),
  };
}

function normalizeResearchForecast(value) {
  const initial = Array.isArray(value)
    ? value.find((item) => item && typeof item === "object" && !Array.isArray(item))
    : value;
  const source = object(initial);
  const nestedForecast = object(source.forecast);
  const nested = Object.keys(source).length === 1
    && Object.keys(nestedForecast).length
    ? object(source.forecast)
    : source;
  const factors = object(nested.factors);
  const scoreNumber = Number(nested.score);
  const confidenceNumber = Number(nested.confidence);
  const forecast = {
    score: Number.isFinite(scoreNumber) ? scoreNumber : null,
    confidence: Number.isFinite(confidenceNumber) ? confidenceNumber : null,
    summary: firstText(
      nested.summary,
      nested.forecast_summary,
      nested.explanation,
      nested.reason,
    ),
    strengths: list(factors.strengths || nested.strengths, 8),
    risks: list(factors.risks || nested.risks, 8),
    limitations: list(nested.limitations, 8),
  };
  return forecast.score !== null
    || forecast.confidence !== null
    || forecast.summary
    || forecast.strengths.length
    || forecast.risks.length
    || forecast.limitations.length
    ? forecast
    : null;
}

function normalizeLearnedRecommendation(value, index) {
  const source = object(value);
  return {
    position: Number(source.position) || index + 1,
    title: firstText(source.title, `Рекомендация ${index + 1}`),
    platform: clean(source.platform, 80),
    generationMode: clean(
      source.recommended_generation_mode || source.generation_mode,
      80,
    ),
    hook: firstText(source.hook),
    keyMessage: firstText(source.key_message, source.goal, source.angle),
    spokenScript: firstText(source.spoken_script, source.script),
    shotList: shotListText(source.shot_list || source.shots),
    visualDirection: firstText(source.visual_direction, source.angle),
    cta: firstText(source.cta),
    proofPoints: list(source.proof_points, 8),
    avoidClaims: list(source.avoid_claims || source.risks, 8),
  };
}

function safeWorkspaceDeepLink(value) {
  const href = String(value || "").trim();
  return /^#\/workspace\/[a-z0-9/_-]+(?:\?[^\s#]*)?$/iu.test(href)
    ? href
    : "";
}

export function normalizeLearnedResearch(item) {
  const source = object(item);
  const rawSources = mergeLearnedSources(source);
  const rawRecommendations = Array.isArray(source.recommendations)
    ? source.recommendations
    : [];
  const summaryValue = source.research_summary
    ?? source.summary
    ?? object(source.run).summary;
  const forecastValue = source.research_forecast
    ?? source.forecast
    ?? source.forecasts;
  return {
    selectionId: clean(source.selection_id, 80),
    receiptId: clean(source.receipt_id, 80).toLowerCase(),
    projectId: normalizedProjectId(source.project_id),
    title: clean(source.product_name, 300)
      || clean(source.research_title, 300)
      || "Исследование",
    productSku: clean(source.product_sku, 120),
    category: normalizedCategory(source.product_category),
    decision: source.decision === "approve" ? "approve" : "reject",
    selectedAt: clean(source.selected_at, 80),
    selectedInsights: (Array.isArray(source.selected_insight_keys)
      ? source.selected_insight_keys
      : [])
      .map((value) => clean(value, 80).toLowerCase())
      .filter(Boolean),
    selectedScenarioPositions: (Array.isArray(source.selected_scenario_positions)
      ? source.selected_scenario_positions
      : [])
      .map(Number)
      .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3),
    sources: rawSources,
    analysis: object(source.analysis_snapshot || source.analysis),
    summary: normalizeResearchSummary(summaryValue),
    forecast: normalizeResearchForecast(forecastValue),
    recommendations: rawRecommendations
      .slice(0, 3)
      .map(normalizeLearnedRecommendation),
    operatorNotes: clean(source.operator_notes, 1200),
    deepLink: safeWorkspaceDeepLink(source.deep_link),
  };
}

function normalizeJourneyConfidence(value) {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    const percent = Math.max(
      0,
      Math.min(100, Math.round(numeric >= 0 && numeric <= 1 ? numeric * 100 : numeric)),
    );
    return {
      percent,
      label: `${percent}%`,
      note: "уверенность по доказательствам, не accuracy модели",
    };
  }
  const candidate = clean(value, 30).toLowerCase();
  const mapped = { low: 30, medium: 60, high: 85 }[candidate];
  if (mapped) {
    return {
      percent: mapped,
      label: ({ low: "Низкая", medium: "Средняя", high: "Высокая" })[candidate],
      note: "качественная оценка из project snapshot",
    };
  }
  return {
    percent: 0,
    label: "Не рассчитана",
    note: "сервер не прислал confidence",
  };
}

function compactJourneyIdentity(value) {
  const candidate = clean(value, 160);
  if (!candidate) return "Snapshot без hash";
  return candidate.length > 18
    ? `${candidate.slice(0, 10)}…${candidate.slice(-5)}`
    : candidate;
}

/**
 * Produces a bounded read-only presentation model from the already
 * project-scoped research snapshot.  It does not infer a generation choice,
 * persist edits or grant an authority that the shell/server did not provide.
 */
export function normalizeProjectResearchJourney(value, options = {}) {
  const source = unwrap(value);
  const queueItems = Array.isArray(options.queue)
    ? options.queue
    : Array.isArray(source.queue) ? source.queue : [];
  const learnedItems = Array.isArray(options.learned)
    ? options.learned
    : Array.isArray(source.learned) ? source.learned : [];
  const pending = object(queueItems[0]);
  const learned = learnedItems.length ? normalizeLearnedResearch(learnedItems[0]) : null;
  const pendingScenarios = Array.isArray(pending.scenarios)
    ? pending.scenarios.slice(0, 3)
    : [];
  const pendingRecommendation = object(pendingScenarios[0]);
  const learnedRecommendation = learned?.recommendations?.[0] || null;
  const recommendation = Object.keys(pendingRecommendation).length
    ? pendingRecommendation
    : object(learnedRecommendation);
  const pendingAnalysis = object(pending.analysis);
  const pendingForecast = normalizeResearchForecast(
    pending.research_forecast
      ?? pending.forecast
      ?? pendingAnalysis.research_forecast
      ?? pendingAnalysis.forecast,
  );
  const forecast = pendingForecast || learned?.forecast || null;
  const confidence = normalizeJourneyConfidence(
    forecast?.confidence
      ?? recommendation.confidence
      ?? source.confidence,
  );
  const pendingSources = Array.isArray(pending.sources) ? pending.sources : [];
  const provenanceSource = object(pendingSources[0] || learned?.sources?.[0]);
  const selectedCategory = normalizedCategory(
    options.selectedCategory
      || source.product_category
      || pending.product_category
      || learned?.category,
  ) || "other";
  const hasPending = queueItems.length > 0;
  const hasLearned = Boolean(learned);
  const canEdit = options.canEdit === true && hasPending;
  const canDecide = options.canDecide === true && hasPending;
  const loading = options.loading === true;
  const projectRequired = options.projectRequired === true;

  let state = "empty";
  let decisionTitle = "Ожидаем исследование";
  let decisionCopy = "Рекомендация появится после завершённого разбора и не будет применена автоматически.";
  let decisionBadge = "Нет кандидата";
  if (loading) {
    state = "loading";
    decisionTitle = "Загружаем project snapshot";
    decisionCopy = "До ответа сервера никакие параметры не считаются выбранными или подтверждёнными.";
    decisionBadge = "Только чтение";
  } else if (projectRequired) {
    state = "locked";
    decisionTitle = "Сначала выберите проект";
    decisionCopy = "ИИ-центр не смешивает исследования и решения разных проектов.";
    decisionBadge = "Project scope";
  } else if (hasPending) {
    state = "pending";
    decisionTitle = canDecide
      ? "Ожидает подтверждения"
      : "Ожидает уполномоченного человека";
    decisionCopy = canDecide
      ? "Выбор и правки ещё не сохранены. Только явное подтверждение в карточке исследования создаст серверную версию рекомендации."
      : "Текущая роль видит рекомендацию, но не может подтвердить её или изменить серверный отбор.";
    decisionBadge = canDecide ? "Решает человек" : "Только чтение";
  } else if (hasLearned && learned.decision === "approve") {
    state = "confirmed";
    decisionTitle = "Подтверждено человеком";
    decisionCopy = "Показана сохранённая серверная версия. Дальнейшие параметры результата всё равно выбираются человеком в отдельной форме стратегии.";
    decisionBadge = learned.selectedAt || "Решение записано";
  } else if (hasLearned) {
    state = "rejected";
    decisionTitle = "Отклонено человеком";
    decisionCopy = "Исследование осталось в истории, но не используется как рекомендация и не меняет параметры генерации.";
    decisionBadge = "Не применять";
  }

  const generationMode = firstText(
    recommendation.recommended_generation_mode,
    recommendation.generationMode,
    recommendation.generation_mode,
  );
  const platform = firstText(recommendation.platform, pending.platform);
  const durationRaw = firstText(
    recommendation.duration,
    recommendation.duration_seconds,
    recommendation.target_duration,
    pending.duration,
  );
  const duration = durationRaw
    ? /^\d+(?:[.,]\d+)?$/u.test(durationRaw) ? `${durationRaw} сек` : durationRaw
    : "Определяет человек";
  const format = firstText(
    recommendation.aspect_ratio,
    recommendation.format,
    recommendation.output_format,
    pending.aspect_ratio,
  );
  const proofPoints = list(
    recommendation.proof_points || recommendation.proofPoints,
    8,
  );
  const sourceCount = Number(pending.source_count)
    || pendingSources.length
    || learned?.sources?.length
    || 0;
  const snapshotIdentity = firstText(
    pending.receipt_hash,
    pending.receipt_id,
    learned?.selectionId,
    learned?.receiptId,
  );

  return {
    state,
    category: selectedCategory,
    categoryLabel: categoryLabel(selectedCategory),
    projectId: normalizedProjectId(source.project_id || pending.project_id || learned?.projectId),
    recommendationTitle: firstText(
      recommendation.title,
      recommendation.hook,
      "Рекомендация появится после разбора",
    ),
    recommendationSummary: firstText(
      recommendation.hook,
      recommendation.key_message,
      recommendation.keyMessage,
      recommendation.spoken_script,
      recommendation.spokenScript,
      forecast?.summary,
      object(pendingAnalysis.guidance).reason,
      "ИИ показывает только подтверждаемую гипотезу из project snapshot.",
    ),
    confidence,
    proofCount: proofPoints.length,
    sourceCount,
    provenanceTitle: firstText(
      provenanceSource.title,
      object(provenanceSource.media).filename,
      provenanceSource.filename,
      pending.research_title,
      "Project research snapshot",
    ),
    provenanceDetail: firstText(
      provenanceSource.provenance,
      provenanceSource.lineage,
      provenanceSource.trust_level,
      provenanceSource.source_type,
      provenanceSource.mime_type,
      "Источник зарегистрирован в выбранном проекте",
    ),
    provenanceIdentity: compactJourneyIdentity(snapshotIdentity),
    parameters: [
      ["Категория", categoryLabel(selectedCategory)],
      ["Площадка", platform || "Не задана"],
      ["ИИ / режим", generationMode || "Выбирает человек"],
      ["Длительность", duration],
      ["Формат", format || "Определяет человек"],
      ["Доказательства", `Сигналов: ${proofPoints.length || sourceCount}`],
    ],
    editTitle: canEdit ? "Параметры можно поправить ниже" : "Параметры доступны только для чтения",
    editCopy: canEdit
      ? "Форма исследования хранит ручные правки отдельно от исходной рекомендации ИИ."
      : "Ни один показанный параметр нельзя изменить от имени ИИ или текущей роли.",
    decisionTitle,
    decisionCopy,
    decisionBadge,
    stateVersion: clean(source.state_version || source.stateVersion, 80) || "—",
    eventCursor: clean(source.event_cursor || source.eventCursor, 80) || "—",
    actorName: firstText(
      object(source.actor).display_name,
      object(source.actor).name,
      "Уполномоченный сотрудник",
    ),
  };
}

function journeySvgNode(tag, attributes = {}) {
  const node = typeof document.createElementNS === "function"
    ? document.createElementNS("http://www.w3.org/2000/svg", tag)
    : document.createElement(tag);
  Object.entries(attributes).forEach(([key, value]) => {
    node.setAttribute(key, String(value));
  });
  return node;
}

function projectJourneyVisual(kind) {
  const visual = el("div", `ai-research-training__journey-visual is-${kind}`);
  visual.setAttribute("aria-hidden", "true");
  const svg = journeySvgNode("svg", {
    viewBox: "0 0 220 110",
    focusable: "false",
  });
  if (kind === "ai") {
    svg.append(
      journeySvgNode("path", {
        class: "ai-research-training__journey-network",
        d: "M18 72 58 31l45 31 47-39 52 36",
      }),
      journeySvgNode("path", {
        class: "ai-research-training__journey-network is-soft",
        d: "M18 72 70 89l33-27 47 18 52-21",
      }),
    );
    [[18, 72, 5], [58, 31, 7], [103, 62, 9], [150, 23, 6], [202, 59, 8]]
      .forEach(([cx, cy, radius], index) => svg.append(journeySvgNode("circle", {
        class: `ai-research-training__journey-node is-${index + 1}`,
        cx,
        cy,
        r: radius,
      })));
    svg.append(
      journeySvgNode("circle", {
        class: "ai-research-training__journey-core",
        cx: 103,
        cy: 62,
        r: 18,
      }),
      journeySvgNode("path", {
        class: "ai-research-training__journey-spark",
        d: "m103 49 4 9 9 4-9 4-4 9-4-9-9-4 9-4Z",
      }),
    );
  } else if (kind === "edit") {
    svg.append(
      journeySvgNode("rect", { x: 22, y: 17, width: 176, height: 74, rx: 14 }),
      journeySvgNode("path", { d: "M45 38h90M45 55h113M45 72h72" }),
      journeySvgNode("circle", { cx: 153, cy: 38, r: 8 }),
      journeySvgNode("circle", { cx: 94, cy: 55, r: 8 }),
      journeySvgNode("circle", { cx: 141, cy: 72, r: 8 }),
      journeySvgNode("path", {
        class: "ai-research-training__journey-pencil",
        d: "m168 72 26-26 9 9-26 26-13 4Z",
      }),
    );
  } else {
    svg.append(
      journeySvgNode("circle", {
        class: "ai-research-training__journey-orbit is-one",
        cx: 110,
        cy: 55,
        r: 41,
      }),
      journeySvgNode("circle", {
        class: "ai-research-training__journey-orbit is-two",
        cx: 110,
        cy: 55,
        r: 29,
      }),
      journeySvgNode("path", {
        class: "ai-research-training__journey-shield",
        d: "M110 27c13 8 24 8 24 8v18c0 15-10 25-24 31-14-6-24-16-24-31V35s11 0 24-8Z",
      }),
      journeySvgNode("path", {
        class: "ai-research-training__journey-check",
        d: "m99 55 8 8 15-18",
      }),
    );
  }
  visual.append(svg);
  return visual;
}

function projectJourneyTopline(step, label) {
  const topline = el("div", "ai-research-training__journey-topline");
  topline.append(el("span", "", step), el("small", "", label));
  return topline;
}

function projectJourneyCopy(title, description) {
  const copy = el("div", "ai-research-training__journey-copy");
  copy.append(el("h4", "", title), el("p", "", description));
  return copy;
}

function projectJourneyConnector(label) {
  const connector = el("div", "ai-research-training__journey-connector");
  connector.setAttribute("aria-hidden", "true");
  connector.append(el("i"), el("span", "", label));
  return connector;
}

function renderProjectResearchJourney(host, snapshot, options = {}) {
  if (!(host instanceof HTMLElement)) return;
  const model = normalizeProjectResearchJourney(snapshot, options);
  host.dataset.aiProjectRecommendationJourney = "true";
  host.dataset.authority = "human-final";
  host.dataset.snapshotMode = "read-only";
  host.dataset.journeyState = model.state;
  host.setAttribute("aria-labelledby", "ai-project-recommendation-journey-title");
  host.replaceChildren();

  const header = el("header", "ai-research-training__journey-header");
  const heading = el("div");
  const headingTitle = el("h3", "", "Как гипотеза становится рабочим решением");
  headingTitle.id = "ai-project-recommendation-journey-title";
  heading.append(
    el("p", "eyebrow", "РЕКОМЕНДАЦИЯ ПОД КОНТРОЛЕМ ЧЕЛОВЕКА"),
    headingTitle,
    el("p", "", "ИИ показывает проектную рекомендацию и её основания. Человек правит рабочую форму и отдельно подтверждает итоговую серверную версию."),
  );
  const readOnly = el("span", "ai-research-training__journey-readonly");
  readOnly.append(el("i"), el("span", "", "Project snapshot · read-only"));
  header.append(heading, readOnly);

  const flow = el("div", "ai-research-training__journey-flow");
  flow.setAttribute("role", "list");
  flow.setAttribute("aria-label", "ИИ рекомендует, человек правит, человек подтверждает");

  const aiCard = el("article", "ai-research-training__journey-card is-ai");
  aiCard.dataset.aiProjectJourneyStage = "recommend";
  aiCard.setAttribute("role", "listitem");
  const aiVisual = projectJourneyVisual("ai");
  aiVisual.append(el("span", "ai-research-training__journey-visual-badge", "Project recommendation"));
  const confidence = el("div", "ai-research-training__journey-confidence");
  confidence.setAttribute("style", `--airt-confidence:${model.confidence.percent}`);
  confidence.setAttribute("aria-label", `Confidence: ${model.confidence.label}`);
  const confidenceHead = el("span");
  confidenceHead.append(el("b", "", "Confidence"), el("strong", "", model.confidence.label));
  const confidenceTrack = el("i");
  confidenceTrack.append(el("i"));
  confidence.append(confidenceHead, confidenceTrack, el("small", "", model.confidence.note));
  const provenance = el("div", "ai-research-training__journey-provenance");
  const provenanceIcon = el("span", "", "⌁");
  provenanceIcon.setAttribute("aria-hidden", "true");
  const provenanceCopy = el("div");
  provenanceCopy.append(
    el("small", "", `Provenance · ${model.sourceCount} источн.`),
    el("strong", "", model.provenanceTitle),
    el("span", "", model.provenanceDetail),
  );
  provenance.append(
    provenanceIcon,
    provenanceCopy,
    el("em", "", model.provenanceIdentity),
  );
  aiCard.append(
    projectJourneyTopline("01", "ИИ-центр рекомендует"),
    aiVisual,
    projectJourneyCopy(model.recommendationTitle, model.recommendationSummary),
    confidence,
    provenance,
  );

  const editCard = el("article", "ai-research-training__journey-card is-edit");
  editCard.dataset.aiProjectJourneyStage = "edit";
  editCard.setAttribute("role", "listitem");
  const editVisual = projectJourneyVisual("edit");
  editVisual.append(el("span", "ai-research-training__journey-visual-badge", "Черновик · не применён"));
  const parameters = el("dl", "ai-research-training__journey-parameters");
  model.parameters.forEach(([label, value]) => {
    const row = el("div");
    row.append(el("dt", "", label), el("dd", "", value));
    parameters.append(row);
  });
  const humanNote = el("div", "ai-research-training__journey-human-note");
  const humanIcon = el("span", "", "✎");
  humanIcon.setAttribute("aria-hidden", "true");
  const humanCopy = el("p");
  humanCopy.append(
    el("strong", "", "Правки принадлежат человеку"),
    el("small", "", "Обновление ИИ не перезаписывает уже введённые значения формы."),
  );
  humanNote.append(humanIcon, humanCopy);
  editCard.append(
    projectJourneyTopline("02", "Человек правит"),
    editVisual,
    projectJourneyCopy(model.editTitle, model.editCopy),
    parameters,
    humanNote,
  );

  const confirmCard = el(
    "article",
    `ai-research-training__journey-card is-confirm is-${model.state}`,
  );
  confirmCard.dataset.aiProjectJourneyStage = "confirm";
  confirmCard.setAttribute("role", "listitem");
  const confirmVisual = projectJourneyVisual("confirm");
  confirmVisual.append(el(
    "span",
    `ai-research-training__journey-visual-badge is-${model.state}`,
    model.decisionBadge,
  ));
  const ledger = el("div", "ai-research-training__journey-ledger");
  [
    ["◇", "Источник решения", model.actorName],
    ["#", "Версия project snapshot", `State ${model.stateVersion} · cursor ${model.eventCursor}`],
    ["⌁", "Автоприменение", "Выключено"],
  ].forEach(([icon, label, value]) => {
    const row = el("div");
    const glyph = el("span", "", icon);
    glyph.setAttribute("aria-hidden", "true");
    const copy = el("p");
    copy.append(el("strong", "", label), el("small", "", value));
    row.append(glyph, copy);
    ledger.append(row);
  });
  confirmCard.append(
    projectJourneyTopline("03", "Человек подтверждает"),
    confirmVisual,
    projectJourneyCopy(model.decisionTitle, model.decisionCopy),
    ledger,
  );

  flow.append(
    aiCard,
    projectJourneyConnector("человек"),
    editCard,
    projectJourneyConnector("явное решение"),
    confirmCard,
  );

  const boundary = el("footer", "ai-research-training__journey-boundary");
  boundary.setAttribute("role", "note");
  const boundaryIcon = el("span", "", "⌾");
  boundaryIcon.setAttribute("aria-hidden", "true");
  const boundaryCopy = el("p");
  boundaryCopy.append(
    el("strong", "", "Граница полномочий"),
    el("small", "", "Этот визуальный snapshot не запускает генерацию, не отправляет решение, не изменяет effective policy и не записывает финальные параметры. Любое изменение состояния остаётся отдельным явным действием человека в существующей форме ниже."),
  );
  boundary.append(boundaryIcon, boundaryCopy);
  host.append(header, flow, boundary);
}

function createProjectResearchJourneyHost(options = {}) {
  const host = el("section", "ai-research-training__journey");
  renderProjectResearchJourney(host, {}, {
    selectedCategory: options.selectedCategory || runtime.category,
    loading: options.loading !== false,
    projectRequired: options.projectRequired === true,
  });
  return host;
}

function learnedSection(title, className = "") {
  const section = el(
    "section",
    `ai-research-training__learned-section${className ? ` ${className}` : ""}`,
  );
  section.append(el("h5", "", title));
  return section;
}

function analysisSnapshotCard(title, value, { summaryKeys = [], listKeys = [] } = {}) {
  const source = object(value);
  const card = el("article", "ai-research-training__snapshot-card");
  card.append(el("strong", "", title));
  const summary = firstText(...summaryKeys.map((key) => source[key]));
  if (summary) card.append(el("p", "", summary));
  const items = [];
  listKeys.forEach(([key, label]) => {
    list(source[key], 6).forEach((item) => items.push(`${label}: ${item}`));
  });
  if (items.length) addTextList(card, items);
  if (!summary && !items.length) {
    card.append(el("p", "ai-research-training__empty-copy", "Сервер не вернул содержимое этого блока."));
  }
  return card;
}

function learnedAnalysisSection(analysis) {
  const section = learnedSection("Выводы ИИ", "ai-research-training__learned-analysis");
  const grid = el("div", "ai-research-training__snapshot-grid");
  grid.append(
    analysisSnapshotCard("Категория и покупатель", analysis.category_analysis, {
      summaryKeys: ["definition", "summary", "category_name"],
      listKeys: [["buyer_jobs", "Задачи"], ["jobs", "Задачи"]],
    }),
    analysisSnapshotCard("Конкуренты", analysis.competitor_analysis, {
      summaryKeys: ["summary", "conclusion"],
      listKeys: [
        ["reusable_structures", "Можно использовать"],
        ["content_gaps", "Пробелы"],
        ["saturated_patterns", "Не копировать"],
      ],
    }),
    analysisSnapshotCard("Тренды", analysis.trend_analysis, {
      summaryKeys: ["summary", "conclusion"],
      listKeys: [["signals", "Сигнал"], ["limitations", "Ограничение"]],
    }),
    analysisSnapshotCard("Итоговая рамка", analysis.creative_brief, {
      summaryKeys: ["summary", "key_message"],
      listKeys: [
        ["audience", "Аудитория"],
        ["pains", "Боли"],
        ["objections", "Возражения"],
        ["facts", "Факты"],
        ["claims", "Ограничения обещаний"],
      ],
    }),
    analysisSnapshotCard("Рекомендованный следующий шаг", analysis.guidance, {
      summaryKeys: ["reason", "recommended_next_step", "summary"],
      listKeys: [["questions", "Проверить"], ["actions", "Действие"]],
    }),
  );
  section.append(grid);
  return section;
}

function generationRecommendationDeepLink(learned, recommendation, intent = "") {
  const selectionId = String(learned?.selectionId || "").trim().toLowerCase();
  const projectId = normalizedProjectId(learned?.projectId);
  const position = Number(recommendation?.position);
  if (
    !projectId
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u
      .test(selectionId)
    || ![1, 2, 3].includes(position)
  ) return "";
  const params = new URLSearchParams({
    project_id: projectId,
    selection_id: selectionId,
    recommendation_position: String(position),
  });
  if (UUID_PATTERN.test(intent)) params.set("recommendation_intent", intent);
  return `#/workspace/generation?${params.toString()}`;
}

function armGenerationRecommendationIntent(learned, recommendation) {
  const selectionId = String(learned?.selectionId || "").trim().toLowerCase();
  const position = Number(recommendation?.position);
  if (
    !UUID_PATTERN.test(selectionId)
    || ![1, 2, 3].includes(position)
    || typeof globalThis.crypto?.randomUUID !== "function"
  ) return "";
  const intent = globalThis.crypto.randomUUID().toLowerCase();
  if (!UUID_PATTERN.test(intent)) return "";
  try {
    globalThis.localStorage?.setItem(
      `${GENERATION_INTENT_PREFIX}${intent}`,
      JSON.stringify({ selectionId, recommendationPosition: position, createdAt: Date.now() }),
    );
    return intent;
  } catch {
    return "";
  }
}

function learnedRecommendationCard(recommendation, learned) {
  const card = el("article", "ai-research-training__learned-recommendation");
  const head = el("header", "");
  head.append(
    el("strong", "", recommendation.title),
    el(
      "small",
      "",
      [recommendation.platform, recommendation.generationMode]
        .filter(Boolean)
        .join(" · ") || `Вариант ${recommendation.position}`,
    ),
  );
  card.append(head);
  [
    ["Хук", recommendation.hook],
    ["Ключевое сообщение", recommendation.keyMessage],
    ["Реплика / сюжет", recommendation.spokenScript],
    ["Кадры", recommendation.shotList],
    ["Визуальное направление", recommendation.visualDirection],
    ["CTA", recommendation.cta],
    ["Доказательства", recommendation.proofPoints.join(" · ")],
    ["Не обещать / учесть", recommendation.avoidClaims.join(" · ")],
  ].forEach(([label, value]) => {
    if (!value) return;
    const line = el("p", "");
    line.append(el("b", "", `${label}: `), document.createTextNode(value));
    card.append(line);
  });
  card.append(el(
    "small",
    "ai-research-training__editable-note",
    "Это сохранённая редактируемая рекомендация. Ссылка передаёт только номер серверного отбора и позицию; категорию и товар «Создать» заново проверит на сервере.",
  ));
  const createHref = generationRecommendationDeepLink(learned, recommendation);
  if (learned?.decision === "approve" && createHref) {
    const action = el(
      "a",
      "btn btn-secondary btn-small",
      "Использовать этот вариант в «Создать»",
    );
    action.href = createHref;
    action.dataset.aiResearchGenerationSelection = learned.selectionId;
    action.dataset.aiResearchGenerationPosition = String(
      recommendation.position,
    );
    action.addEventListener("click", () => {
      const intent = armGenerationRecommendationIntent(learned, recommendation);
      if (intent) {
        action.href = generationRecommendationDeepLink(learned, recommendation, intent);
      }
    });
    card.append(action);
  }
  return card;
}

function receiptCard(item, {
  canDecide = false,
  canEdit = false,
  open = false,
} = {}) {
  const source = object(item);
  const card = el("details", "ai-research-training__receipt");
  card.open = open;
  card.dataset.receiptId = clean(source.receipt_id, 80);
  card.dataset.receiptHash = clean(source.receipt_hash, 80);
  card.dataset.projectId = normalizedProjectId(source.project_id);
  card.dataset.ownership = clean(source.ownership, 20).toLowerCase();
  card.dataset.canDecide = String(canDecide);
  card.dataset.canEdit = String(canEdit);

  const summary = el("summary", "ai-research-training__receipt-summary");
  const titleBox = el("span");
  titleBox.append(
    el("strong", "", clean(source.product_name, 300) || "Исследование"),
    el("small", "", [
      clean(source.project_name, 180),
      clean(source.product_sku, 100),
      `${Number(source.source_count) || 0} источников`,
    ].filter(Boolean).join(" · ")),
  );
  const state = el(
    "span",
    "ai-research-training__receipt-state",
    source.review_state === "approved_waiting_for_learning_selection"
      ? "Проверено · выберите знания"
      : "Нужен отбор",
  );
  summary.append(titleBox, state);

  const body = el("div", "ai-research-training__receipt-body");
  const sourcesSection = el("section", "ai-research-training__section");
  sourcesSection.append(el("h4", "", "1. Источники и разбор ролика"));
  const sourcesGrid = el("div", "ai-research-training__sources");
  const sources = Array.isArray(source.sources) ? source.sources : [];
  if (sources.length) sources.slice(0, 12).forEach((entry) => sourcesGrid.append(sourceCard(entry)));
  else sourcesGrid.append(el("p", "ai-research-training__empty-copy", "Источники ещё не прикреплены к завершённому разбору."));
  sourcesSection.append(sourcesGrid);

  const insightSection = el("section", "ai-research-training__section");
  insightSection.append(
    el("h4", "", "2. Что именно взять в обучение"),
    el(
      "p",
      "muted",
      canEdit
        ? "Снимите галочку с блока, который не должен влиять на рекомендации."
        : "Сервер открыл этот чек только для чтения.",
    ),
  );
  const insights = el("div", "ai-research-training__insights");
  const analysis = object(source.analysis);
  const brief = object(source.creative_brief);
  insights.append(
    categoryInsight(analysis, !canEdit),
    competitorInsight(analysis, !canEdit),
    trendInsight(analysis, !canEdit),
    briefInsight(brief, !canEdit),
  );
  insightSection.append(insights);

  const scenarioSection = el("section", "ai-research-training__section");
  scenarioSection.append(
    el("h4", "", "3. Рекомендации, которые получит генерация"),
    el(
      "p",
      "muted",
      canEdit
        ? "Отметьте варианты и поправьте текст прямо здесь. Эти правки станут утверждённой версией."
        : "Рекомендации показаны без права изменения.",
    ),
  );
  const scenarios = el("div", "ai-research-training__scenarios");
  const scenarioItems = Array.isArray(source.scenarios) ? source.scenarios.slice(0, 3) : [];
  if (scenarioItems.length) {
    scenarioItems.forEach((scenario, index) => scenarios.append(
      scenarioCard(scenario, index + 1, { disabled: !canEdit }),
    ));
  } else {
    scenarios.append(el("p", "ai-research-training__empty-copy", "В исследовании нет пригодных сценариев. Такой результат нельзя обучить как рекомендацию."));
  }
  scenarioSection.append(scenarios);

  const controls = el("footer", "ai-research-training__controls");
  const notes = field(
    "Комментарий к отбору (необязательно)",
    "",
    "operator_notes",
    { textarea: true, rows: 2, disabled: !canEdit },
  );
  notes.classList.add("ai-research-training__notes");
  const confirmation = el("label", "check-row ai-research-training__confirmation");
  const confirmationInput = el("input");
  confirmationInput.type = "checkbox";
  confirmationInput.disabled = !canDecide;
  confirmationInput.dataset.trainingConfirmation = "true";
  confirmation.append(
    confirmationInput,
    el("span", "", "Я проверила разбор и понимаю, какие выводы станут рекомендациями ИИ."),
  );
  const actions = el("div", "ai-research-training__actions");
  const reject = el("button", "btn btn-secondary", "Не использовать");
  reject.type = "button";
  reject.dataset.trainingDecision = "reject";
  const approve = el("button", "btn", "Обучить на выбранном и сохранить рекомендации");
  approve.type = "button";
  approve.dataset.trainingDecision = "approve";
  approve.disabled = !canDecide || !canEdit || !scenarioItems.length;
  reject.disabled = !canDecide;
  actions.append(reject, approve);
  controls.append(notes, confirmation, actions);

  body.append(sourcesSection, insightSection, scenarioSection, controls);
  card.append(summary, body);
  return card;
}

function learnedCard(item, { open = false } = {}) {
  const learned = normalizeLearnedResearch(item);
  const card = el("details", "ai-research-training__learned-card");
  card.open = open;
  card.dataset.selectionId = learned.selectionId;
  card.dataset.receiptId = learned.receiptId;

  const summary = el("summary", "ai-research-training__learned-summary");
  const head = el("span");
  head.append(
    el("strong", "", learned.title),
    el("small", "", [
      learned.productSku,
      learned.category ? categoryLabel(learned.category) : "",
      learned.selectedAt,
    ].filter(Boolean).join(" · ")),
  );
  const state = el(
    "span",
    "ai-research-training__learned-state",
    learned.decision === "approve"
      ? `Используется · ${learned.recommendations.length} рекомендац.`
      : "Отклонено",
  );
  summary.append(head, state);

  const body = el("div", "ai-research-training__learned-body");

  const material = learnedSection("Материал и источники");
  const sourcesGrid = el("div", "ai-research-training__sources");
  if (learned.sources.length) {
    learned.sources.forEach((source) => sourcesGrid.append(sourceCard(source)));
  } else {
    sourcesGrid.append(el(
      "p",
      "ai-research-training__empty-copy",
      "Снимок материалов отсутствует в ответе сервера.",
    ));
  }
  material.append(sourcesGrid);

  const results = learnedSection("Итоги исследования");
  if (learned.summary.headline) results.append(el("p", "", learned.summary.headline));
  if (learned.summary.conclusions.length) {
    results.append(el("strong", "", "Итоговые выводы"));
    addTextList(results, learned.summary.conclusions);
  }
  if (learned.summary.limitations.length) {
    results.append(el("strong", "", "Ограничения"));
    addTextList(results, learned.summary.limitations);
  }
  if (
    !learned.summary.headline
    && !learned.summary.conclusions.length
    && !learned.summary.limitations.length
  ) {
    results.append(el(
      "p",
      "ai-research-training__empty-copy",
      "Общий итог исследования отсутствует в ответе сервера; сохранённые блоки анализа показаны ниже.",
    ));
  }

  if (learned.forecast) {
    const forecast = learnedSection("Прогноз и уверенность");
    const forecastMeta = [
      learned.forecast.score !== null ? `оценка ${learned.forecast.score}` : "",
      learned.forecast.confidence !== null
        ? `уверенность ${Math.round(
          learned.forecast.confidence <= 1
            ? learned.forecast.confidence * 100
            : learned.forecast.confidence,
        )}%`
        : "",
    ].filter(Boolean).join(" · ");
    if (forecastMeta) forecast.append(el("strong", "", forecastMeta));
    if (learned.forecast.summary) forecast.append(el("p", "", learned.forecast.summary));
    if (learned.forecast.strengths.length) {
      forecast.append(el("small", "", `Сильные стороны: ${learned.forecast.strengths.join(" · ")}`));
    }
    if (learned.forecast.risks.length) {
      forecast.append(el("small", "", `Риски: ${learned.forecast.risks.join(" · ")}`));
    }
    if (learned.forecast.limitations.length) {
      forecast.append(el("small", "", `Ограничения: ${learned.forecast.limitations.join(" · ")}`));
    }
    results.append(forecast);
  }

  const selection = learnedSection("Что выбрано для обучения");
  const insightLabels = {
    category: "Категория и покупатель",
    competitors: "Конкуренты",
    trends: "Тренды",
    brief: "Коммуникационная рамка",
  };
  const chips = el("div", "ai-research-training__learned-chips");
  learned.selectedInsights.forEach((key) => {
    chips.append(el("span", "", insightLabels[key] || key));
  });
  learned.selectedScenarioPositions.forEach((position) => {
    chips.append(el("span", "", `Сценарий ${position}`));
  });
  if (chips.childNodes.length) selection.append(chips);
  else selection.append(el("p", "ai-research-training__empty-copy", "Состав отбора не указан."));
  if (learned.operatorNotes) {
    selection.append(el("p", "", `Комментарий: ${learned.operatorNotes}`));
  }

  const recommendations = learnedSection("Сохранённые редактируемые рекомендации");
  const recommendationGrid = el("div", "ai-research-training__learned-recommendations");
  if (learned.recommendations.length) {
    learned.recommendations.forEach((recommendation) => {
      recommendationGrid.append(
        learnedRecommendationCard(recommendation, learned),
      );
    });
  } else {
    recommendationGrid.append(el(
      "p",
      "ai-research-training__empty-copy",
      learned.decision === "approve"
        ? "Сервер не вернул сохранённые рекомендации."
        : "Отклонённое исследование не влияет на рекомендации.",
    ));
  }
  recommendations.append(recommendationGrid);

  body.append(material, results, learnedAnalysisSection(learned.analysis), selection, recommendations);
  if (learned.deepLink) {
    const link = el("a", "btn btn-secondary btn-small", "Открыть исходное исследование");
    link.href = learned.deepLink;
    body.append(link);
  }
  card.append(summary, body);
  return card;
}

function renderSnapshot(root, snapshot, expectedProjectId = runtime.projectId) {
  const shellAccess = trainingShellAccess();
  if (!shellAccess.allowed) return false;
  const projectSnapshot = projectScopedTrainingSnapshot(snapshot, expectedProjectId);
  const source = shellAccess.ownOnly
    ? projectScopedTrainingSnapshot(snapshot, expectedProjectId, "own")
    : projectSnapshot;
  if (!source) return false;
  const receiptRoute = routeReceipt();
  const allQueue = Array.isArray(source.queue) ? source.queue : [];
  const allLearned = Array.isArray(source.learned) ? source.learned : [];
  const queue = receiptRoute.requested
    ? receiptRoute.valid
      ? allQueue.filter((item) => (
          clean(item?.receipt_id, 80).toLowerCase() === receiptRoute.id
        ))
      : []
    : allQueue;
  const learned = receiptRoute.requested
    ? receiptRoute.valid
      ? allLearned.filter((item) => (
          clean(item?.receipt_id, 80).toLowerCase() === receiptRoute.id
        ))
      : []
    : allLearned;
  const capabilities = object(source.capabilities);
  const canDecide = shellAccess.canDecide
    && capabilities.can_decide === true;
  const canEdit = shellAccess.canEdit
    && capabilities.can_edit_recommendations === true;
  const selectedCategory = normalizedCategory(source.product_category)
    || normalizedCategory(runtime.category)
    || "other";
  const selectedCategoryLabel = categoryLabel(selectedCategory);
  const journeyHost = root.querySelector("[data-ai-project-recommendation-journey]");
  const queueHost = root.querySelector("[data-ai-research-training-queue]");
  const historyHost = root.querySelector("[data-ai-research-training-history]");
  if (!journeyHost || !queueHost || !historyHost) return;
  renderProjectResearchJourney(journeyHost, {
    ...source,
    queue,
    learned,
  }, {
    selectedCategory,
    canEdit,
    canDecide,
  });
  queueHost.replaceChildren();
  historyHost.replaceChildren();

  if (receiptRoute.requested && !queue.length && !learned.length) {
    const unavailable = el("div", "ai-research-training__empty");
    unavailable.append(
      el("strong", "", "Этот чек недоступен"),
      el("p", "", "Сервер не подтвердил, что чек принадлежит вам и выбранному проекту. Другие чеки по этой ссылке не открываются."),
    );
    queueHost.append(unavailable);
  } else if (!queue.length) {
    const empty = el("div", "ai-research-training__empty");
    empty.append(
      el("strong", "", `В категории «${selectedCategoryLabel}» нет исследований для отбора`),
      el("p", "", "Сначала завершите анализ ролика в «Исследованиях». После этого здесь появятся источники, разбор и варианты рекомендаций."),
    );
    const link = el("a", "btn btn-secondary btn-small", "Начать новый разбор");
    link.href = `#/workspace/research?project_id=${encodeURIComponent(source.project_id)}&category=${encodeURIComponent(selectedCategory)}&new=1`;
    empty.append(link);
    queueHost.append(empty);
  } else {
    queue.forEach((item, index) => queueHost.append(receiptCard(item, {
      canDecide,
      canEdit,
      open: receiptRoute.requested || index === 0,
    })));
  }

  if (!learned.length) {
    historyHost.append(el(
      "p",
      "ai-research-training__empty-copy",
      `В категории «${selectedCategoryLabel}» пока нет сохранённых отборов.`,
    ));
  } else {
    learned.slice(0, 12).forEach((item) => historyHost.append(learnedCard(item, {
      open: receiptRoute.requested,
    })));
  }

  const oldInbox = document.querySelector(".ai-learning-research-inbox");
  if (oldInbox instanceof HTMLElement) {
    oldInbox.hidden = true;
    oldInbox.dataset.replacedByResearchTraining = "true";
  }
  setStatus(
    root,
    receiptRoute.requested && !queue.length && !learned.length
      ? "Сервер не подтвердил доступ к запрошенному чеку."
      : queue.length
      ? `Категория «${selectedCategoryLabel}»: исследований для отбора — ${queue.length}.`
      : `Категория «${selectedCategoryLabel}»: очередь пуста — ждём завершённое исследование.`,
    queue.length ? "ready" : "neutral",
  );
  root.dataset.renderedProjectId = expectedProjectId;
  root.dataset.renderedCategory = selectedCategory;
  root.dataset.renderedReceiptId = receiptRoute.requested
    ? receiptRoute.id
    : "";
  return true;
}

function invalidateRenderedTrainingScope(root) {
  if (!(root instanceof HTMLElement)) return;
  root.dataset.renderedProjectId = "";
  root.dataset.renderedCategory = "";
  root.dataset.renderedReceiptId = "";
  root.querySelector("[data-ai-research-training-queue]")?.replaceChildren();
  root.querySelector("[data-ai-research-training-history]")?.replaceChildren();
}

function guardRenderedTrainingScopeClick(event) {
  const root = event.currentTarget;
  if (!(root instanceof HTMLElement)) return;
  const activeReceipt = typeof routeReceipt === "function"
    && routeReceipt().requested
    ? routeReceipt().id
    : "";
  if (
    routePath() === ROUTE
    && root.dataset.renderedProjectId === currentTrainingProjectId()
    && root.dataset.renderedCategory === currentCategory()
    && String(root.dataset.renderedReceiptId || "") === activeReceipt
  ) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function prepareTrainingRoot(root) {
  root.dataset.ceV4Owned = "ai-research-training";
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  const queue = root.querySelector("[data-ai-research-training-queue]");
  if (
    queue
    && !root.querySelector("[data-ai-project-recommendation-journey]")
  ) {
    queue.parentNode?.insertBefore(createProjectResearchJourneyHost({
      selectedCategory: runtime.category,
    }), queue);
  }
  if (root.dataset.renderedScopeGuardBound !== "true") {
    root.addEventListener("click", guardRenderedTrainingScopeClick, true);
    root.dataset.renderedScopeGuardBound = "true";
  }
  return root;
}

function buildRoot() {
  const root = el("section", "ai-research-training card card-pad");
  prepareTrainingRoot(root);
  const header = el("header", "ai-research-training__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "ИССЛЕДОВАНИЯ → ОБУЧЕНИЕ → РЕКОМЕНДАЦИИ"),
    el("h2", "", "Разбор исследований для ИИ"),
    el("p", "muted", "Здесь ИИ не «глотает» всё подряд. Вы видите разбор ролика, выбираете полезные выводы, правите рекомендации и только затем допускаете их в создание."),
  );
  const selectLabel = el("label", "field ai-research-training__category");
  selectLabel.append(el("span", "", "Категория обучения"));
  const select = el("select");
  select.dataset.trainingCategory = "true";
  CATEGORIES.forEach(([value, label]) => {
    const option = el("option", "", label);
    option.value = value;
    select.append(option);
  });
  selectLabel.append(select);
  header.append(copy, selectLabel);

  const status = el("p", "ai-research-training__status", "Загружаем очередь…");
  status.dataset.aiResearchTrainingStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const journey = createProjectResearchJourneyHost({
    selectedCategory: runtime.category,
  });
  const queue = el("div", "ai-research-training__queue");
  queue.dataset.aiResearchTrainingQueue = "true";
  const historyWrap = el("details", "ai-research-training__history");
  const historySummary = el("summary", "", "Уже отобранные исследования");
  const history = el("div", "ai-research-training__history-grid");
  history.dataset.aiResearchTrainingHistory = "true";
  historyWrap.append(historySummary, history);

  root.append(header, status, journey, queue, historyWrap);
  root.addEventListener("change", handleChange);
  root.addEventListener("click", handleClick);
  return root;
}

function hostForRoot() {
  return document.querySelector("[data-ai-research-training-host]")
    || document.querySelector(".ai-learning-control-room")
    || document.querySelector(".ai-learning-page")
    || document.querySelector("#workspace-content")
    || document.querySelector("#main-content");
}

function ensureRoot() {
  let root = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (root instanceof HTMLElement) return prepareTrainingRoot(root);
  const host = hostForRoot();
  if (!(host instanceof HTMLElement)) return null;
  if (
    host.matches("[data-ai-research-training-host]")
    && normalizedProjectId(host.dataset.projectId)
      !== currentTrainingProjectId()
  ) return null;
  root = buildRoot();
  const oldInbox = host.querySelector(".ai-learning-research-inbox");
  if (oldInbox?.parentNode) oldInbox.parentNode.insertBefore(root, oldInbox);
  else {
    const header = host.querySelector(":scope > header, .ai-learning-hero");
    if (header?.nextSibling) host.insertBefore(root, header.nextSibling);
    else host.prepend(root);
  }
  return root;
}

function suspendProjectTraining(root) {
  runtime.loadToken += 1;
  runtime.loading = false;
  if (root) {
    root.hidden = false;
    root.dataset.loading = "false";
    root.dataset.projectRequired = "true";
    const journey = root.querySelector("[data-ai-project-recommendation-journey]");
    const queue = root.querySelector("[data-ai-research-training-queue]");
    const history = root.querySelector("[data-ai-research-training-history]");
    if (journey) {
      renderProjectResearchJourney(journey, {}, {
        selectedCategory: runtime.category,
        loading: false,
        projectRequired: true,
      });
    }
    queue?.replaceChildren();
    history?.replaceChildren();
    if (queue) {
      const empty = el("div", "ai-research-training__empty");
      empty.append(
        el("strong", "", "Выберите проект для обучения на исследованиях"),
        el("p", "", "Глобальные знания ИИ-центра доступны ниже. Очередь исследований и решения открываются только в контексте выбранного проекта."),
      );
      queue.append(empty);
    }
    setStatus(root, "Проект не выбран — данные исследований не загружаются.", "neutral");
  }
  const oldInbox = document.querySelector(".ai-learning-research-inbox");
  if (oldInbox instanceof HTMLElement) {
    oldInbox.hidden = true;
    oldInbox.dataset.replacedByResearchTraining = "true";
  }
}

async function load(
  root,
  category = runtime.category,
  projectId = runtime.projectId || currentTrainingProjectId(),
) {
  const shellAccess = trainingShellAccess();
  const selectedCategory = normalizedCategory(category) || "other";
  const selectedProjectId = normalizedProjectId(projectId);
  const selectedReceipt = routeReceipt();
  const selectedReceiptKey = selectedReceipt.requested
    ? selectedReceipt.id
    : "";
  if (!root || routePath() !== ROUTE || !shellAccess.allowed) return;
  if (!selectedProjectId) return;
  root.hidden = false;
  delete root.dataset.projectRequired;
  const loadToken = ++runtime.loadToken;
  runtime.loading = true;
  root.dataset.loading = "true";
  setStatus(
    root,
    `Загружаем разборы категории «${categoryLabel(selectedCategory)}»…`,
  );
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_QUEUE,
      payloadWithOrganization(api, projectScopedTrainingPayload({
        product_category: selectedCategory,
        ...(selectedReceiptKey ? { receipt_id: selectedReceiptKey } : {}),
        limit: 30,
      }, selectedProjectId)),
    );
    if (
      loadToken !== runtime.loadToken
      || routePath() !== ROUTE
      || runtime.category !== selectedCategory
      || runtime.projectId !== selectedProjectId
      || currentTrainingProjectId() !== selectedProjectId
      || !trainingShellAccess().allowed
      || trainingShellAccess().receiptScope !== shellAccess.receiptScope
      || (routeReceipt().requested ? routeReceipt().id : "")
        !== selectedReceiptKey
    ) return;
    if (!renderSnapshot(root, response, selectedProjectId)) {
      throw new Error("ai_research_training_project_scope_mismatch");
    }
  } catch (error) {
    if (
      loadToken !== runtime.loadToken
      || runtime.category !== selectedCategory
      || runtime.projectId !== selectedProjectId
      || currentTrainingProjectId() !== selectedProjectId
      || !trainingShellAccess().allowed
      || trainingShellAccess().receiptScope !== shellAccess.receiptScope
      || (routeReceipt().requested ? routeReceipt().id : "")
        !== selectedReceiptKey
    ) return;
    console.warn("Research training queue unavailable", error);
    setStatus(
      root,
      `Категория «${categoryLabel(selectedCategory)}»: не удалось загрузить очередь. Миграция/RPC должны быть развёрнуты вместе с интерфейсом.`,
      "danger",
    );
  } finally {
    if (loadToken === runtime.loadToken) {
      runtime.loading = false;
      root.dataset.loading = "false";
    }
  }
}

function selectedInsights(card) {
  return [...card.querySelectorAll("[data-insight-key]:checked")]
    .map((input) => input.dataset.insightKey)
    .filter((value) => ["category", "competitors", "trends", "brief"].includes(value));
}

function selectedScenarios(card) {
  return [...card.querySelectorAll("[data-scenario-select]:checked")]
    .map((input) => Number(input.dataset.scenarioSelect))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3);
}

function scenarioEdits(card, positions) {
  return positions.map((position) => {
    const scenario = card.querySelector(`[data-scenario-position="${position}"]`);
    const read = (name) => String(scenario?.querySelector(`[name="${name}"]`)?.value || "").trim();
    return {
      position,
      title: read("title"),
      hook: read("hook"),
      spoken_script: read("spoken_script"),
      shot_list: read("shot_list"),
      key_message: read("key_message"),
      visual_direction: read("visual_direction"),
      cta: read("cta"),
    };
  });
}

async function decide(card, decision) {
  if (runtime.mutating) return;
  const mutationRoot = runtime.root;
  const projectId = currentTrainingProjectId()
    || normalizedProjectId(routeParams().get("project_id"));
  const category = runtime.category;
  const shellAccess = trainingShellAccess();
  if (
    routePath() !== ROUTE
    || !mutationRoot
    || !projectId
    || runtime.projectId !== projectId
    || normalizedProjectId(card.dataset.projectId) !== projectId
    || !shellAccess.allowed
    || card.dataset.canDecide !== "true"
    || (
      decision === "approve"
      && card.dataset.canEdit !== "true"
    )
    || (
      shellAccess.ownOnly
      && card.dataset.ownership !== "own"
    )
  ) return;
  const confirmation = card.querySelector("[data-training-confirmation]");
  if (!(confirmation instanceof HTMLInputElement) || !confirmation.checked) {
    confirmation?.focus();
    setStatus(runtime.root, "Сначала подтвердите, что вы проверили разбор.", "danger");
    return;
  }
  const insights = decision === "approve" ? selectedInsights(card) : [];
  const positions = decision === "approve" ? selectedScenarios(card) : [];
  if (decision === "approve" && (!insights.length || !positions.length)) {
    setStatus(runtime.root, "Выберите минимум один блок анализа и одну рекомендацию.", "danger");
    return;
  }
  const notes = String(card.querySelector('[name="operator_notes"]')?.value || "").trim();
  runtime.mutating = true;
  mutationRoot.dataset.mutating = "true";
  setStatus(
    runtime.root,
    decision === "approve" ? "Сохраняем выбранное обучение…" : "Отклоняем исследование…",
  );
  try {
    const api = await getApi();
    const receiptId = decisionUuid(card.dataset.receiptId);
    const request = payloadWithOrganization(
      api,
      projectScopedTrainingPayload({
        product_category: category,
        receipt_id: receiptId,
        receipt_hash: card.dataset.receiptHash,
        decision,
        selected_insight_keys: insights,
        selected_scenario_positions: positions,
        edits: decision === "approve" ? scenarioEdits(card, positions) : [],
        ...(notes ? { operator_notes: notes } : {}),
        confirmation: true,
      }, projectId),
    );
    const scope = await authenticatedTrainingDecisionScope(
      api,
      projectId,
      receiptId,
    );
    const decisionScopeIsCurrent = () => Boolean(
      routePath() === ROUTE
      && runtime.root === mutationRoot
      && mutationRoot.isConnected
      && runtime.category === category
      && runtime.projectId === projectId
      && currentTrainingProjectId() === projectId
      && decisionUuid(api.organizationId) === scope.organizationId
    );
    const callWithinDecisionScope = (rpcName, payload) => {
      if (!decisionScopeIsCurrent()) {
        throw decisionError(
          "ai_research_training_decision_scope_changed",
          "Пользователь, команда, проект или открытый чек изменились. Решение не отправлено; откройте чек заново.",
        );
      }
      return api.callAsExpectedActor(rpcName, payload, scope.actorId, {
        isContextCurrent: decisionScopeIsCurrent,
      });
    };
    const result = await performTrainingDecisionMutation({
      storage: trainingDecisionStorage(),
      scope,
      request,
      receiptScope: shellAccess.receiptScope,
      send: (payload) => callWithinDecisionScope(RPC_DECIDE, payload),
      reload: () => callWithinDecisionScope(
        RPC_QUEUE,
        payloadWithOrganization(api, projectScopedTrainingPayload({
          product_category: request.product_category,
          receipt_id: receiptId,
          limit: 30,
        }, projectId)),
      ),
    });
    if (
      routePath() !== ROUTE
      || runtime.root !== mutationRoot
      || runtime.category !== category
      || runtime.projectId !== projectId
      || currentTrainingProjectId() !== projectId
    ) return;
    if (!renderSnapshot(mutationRoot, result.snapshot, projectId)) {
      throw new Error("ai_research_training_project_scope_mismatch");
    }
    const savedDecision = result.intent.request.decision;
    setStatus(
      runtime.root,
      savedDecision === "approve"
        ? "Готово: выбранные выводы стали редактируемыми рекомендациями для создания."
        : "Исследование исключено из обучения.",
      "ready",
    );
  } catch (error) {
    if (
      runtime.root !== mutationRoot
      || runtime.projectId !== projectId
      || currentTrainingProjectId() !== projectId
    ) return;
    if (error?.snapshot) {
      renderSnapshot(mutationRoot, error.snapshot, projectId);
    }
    console.warn("Research training decision failed", error);
    setStatus(
      runtime.root,
      error?.message || "Не удалось сохранить решение. Обновите страницу и повторите.",
      "danger",
    );
  } finally {
    runtime.mutating = false;
    if (mutationRoot?.isConnected) mutationRoot.dataset.mutating = "false";
  }
}

function handleChange(event) {
  const select = event.target.closest?.("[data-training-category]");
  if (!select) return;
  const category = normalizedCategory(select.value);
  if (!category) return;
  const changed = category !== runtime.category;
  runtime.category = category;
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  updateCategoryRoute(category);
  const projectId = currentTrainingProjectId();
  const receipt = routeReceipt();
  const requestKey = `${projectId}:${category}:${receipt.requested ? receipt.id : ""}:${trainingShellAccess().receiptScope}:${runtime.root?.isConnected}`;
  if (changed || runtime.requestKey !== requestKey) {
    if (changed) invalidateRenderedTrainingScope(runtime.root);
    runtime.requestKey = requestKey;
    void load(runtime.root, category, projectId);
  }
}

function handleLegacyCategoryClick(event) {
  if (routePath() !== ROUTE) return;
  const control = event.target.closest?.(
    ".ai-learning-category[data-category-key]",
  );
  if (!control || !legacyCategoryControlVisible(control)) return;
  const category = normalizedCategory(control.dataset?.categoryKey);
  if (!category) return;
  const projectId = currentTrainingProjectId();
  const changed = category !== runtime.category;
  runtime.category = category;
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  syncTrainingCategorySelect(category);
  if (changed && runtime.root?.isConnected) {
    invalidateRenderedTrainingScope(runtime.root);
    const receipt = routeReceipt();
    runtime.requestKey = `${projectId}:${category}:${receipt.requested ? receipt.id : ""}:${trainingShellAccess().receiptScope}:${runtime.root.isConnected}`;
    void load(runtime.root, category, projectId);
  }
  window.queueMicrotask(() => {
    restoreProjectScopeAfterLegacyNavigation(category, projectId);
  });
}

function handleClick(event) {
  const root = event.currentTarget;
  if (
    routePath() !== ROUTE
    || (
      root instanceof HTMLElement
      && (
        root.dataset.renderedProjectId !== currentTrainingProjectId()
        || root.dataset.renderedCategory !== currentCategory()
        || root.dataset.renderedReceiptId !== (
          routeReceipt().requested ? routeReceipt().id : ""
        )
      )
    )
  ) {
    event.preventDefault();
    return;
  }
  const button = event.target.closest?.("[data-training-decision]");
  if (!(button instanceof HTMLButtonElement)) return;
  event.preventDefault();
  const card = button.closest("[data-receipt-id]");
  if (!(card instanceof HTMLElement)) return;
  const decision = button.dataset.trainingDecision;
  if (!["approve", "reject"].includes(decision)) return;
  void decide(card, decision);
}

function unmount() {
  runtime.loadToken += 1;
  runtime.loading = false;
  runtime.requestKey = "";
  runtime.root = null;
  runtime.projectId = "";
  document.querySelectorAll(`[${ROOT_ATTRIBUTE}]`).forEach((root) => root.remove());
}

function mount() {
  const shellAccess = trainingShellAccess();
  if (routePath() !== ROUTE || !shellAccess.allowed) {
    unmount();
    return;
  }
  const previousRoot = runtime.root;
  const previousProjectId = runtime.projectId;
  const previousCategory = runtime.category;
  const root = ensureRoot();
  if (!root) return;
  const category = currentCategory();
  const projectId = currentTrainingProjectId();
  if (shellAccess.ownOnly) {
    const projectHost = root.closest("[data-ai-research-training-host]");
    if (
      !(projectHost instanceof HTMLElement)
      || normalizedProjectId(projectHost.dataset.projectId) !== projectId
    ) {
      unmount();
      return;
    }
  }
  const scopeChanged = previousRoot !== root
    || previousProjectId !== projectId
    || previousCategory !== category;
  runtime.root = root;
  if (projectId) canonicalizeTrainingRoute(category, projectId);
  const receipt = routeReceipt();
  const requestKey = `${projectId}:${category}:${receipt.requested ? receipt.id : ""}:${shellAccess.receiptScope}:${root.isConnected}`;
  runtime.category = category;
  runtime.projectId = projectId;
  const requestChanged = runtime.requestKey !== requestKey;
  if (scopeChanged) invalidateRenderedTrainingScope(root);
  else if (requestChanged) invalidateRenderedTrainingScope(root);
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  syncTrainingCategorySelect(category);
  if (!projectId) {
    runtime.requestKey = requestKey;
    suspendProjectTraining(root);
    return;
  }
  root.hidden = false;
  if (requestChanged || !root.dataset.loaded) {
    runtime.requestKey = requestKey;
    root.dataset.loaded = "true";
    void load(root, category, projectId);
  }
}

function scheduleMount() {
  if (runtime.mountQueued) return;
  runtime.mountQueued = true;
  window.queueMicrotask(() => {
    runtime.mountQueued = false;
    mount();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "ai-research-training",
      mount,
      { priority: 205 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", scheduleMount);
  window.addEventListener(
    "contentengine:workspace-capabilities-ready",
    scheduleMount,
  );
  window.addEventListener("hashchange", scheduleMount);
  document.addEventListener("click", handleLegacyCategoryClick, true);
  window.queueMicrotask(scheduleMount);
}

export const AiResearchTraining = Object.freeze({ mount, load });
