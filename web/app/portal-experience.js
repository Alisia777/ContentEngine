export const PORTAL_THEME_STORAGE_KEY = "contentengine.portal-theme.v1";

export const PORTAL_THEMES = Object.freeze([
  Object.freeze({
    id: "obsidian",
    label: "Обсидиан",
    description: "Глубокий чёрный, графит и тёплая медь",
  }),
]);

export const GENERATION_ARCHIVE_PAGE_SIZE = 50;
export const GENERATION_VISIBLE_STEP = 20;
export const GENERATION_VISIBLE_CAP = 200;

const PORTAL_THEME_IDS = new Set(PORTAL_THEMES.map((theme) => theme.id));
const GENERATION_PERIODS = new Set(["week", "4w", "12w", "all"]);
const GENERATION_STATUS_GROUPS = new Set(["all", "active", "ready", "issue"]);
const GENERATION_PROVIDERS = new Set(["all", "runway", "google", "fal"]);
const GENERATION_STRATEGIES = new Set([
  "all",
  "viral_avatar_ugc",
  "viral_product_swap",
  "viral_rebuild",
]);
const GENERATION_CONTENT_KINDS = new Set(["all", "video", "photo"]);
const GENERATION_SELECTION_SOURCES = new Set([
  "all",
  "system_recommendation",
  "research_recommendation",
  "performance_recommendation",
  "manual_choice",
  "alternative_after_block",
]);
const GENERATION_QUALITY_STATUSES = new Set([
  "all",
  "accepted",
  "needs_revalidation",
  "unproven",
]);
const GENERATION_MODEL_FILTER_PATTERN = /^[a-z0-9][a-z0-9._-]{0,79}$/u;
const ACTIVE_GENERATION_STATUSES = new Set([
  "queued",
  "starting",
  "submitted",
  "processing",
  "running",
  "saving",
  "uploading",
]);
const READY_GENERATION_STATUSES = new Set(["mock_ready", "ready", "succeeded", "completed", "done"]);
const ISSUE_GENERATION_STATUSES = new Set(["failed", "cancelled", "canceled"]);
const WEEK_MS = 7 * 24 * 60 * 60 * 1_000;

export function normalizePortalTheme(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return PORTAL_THEME_IDS.has(normalized) ? normalized : "obsidian";
}

export function readPortalThemePreference(storage) {
  try {
    const preferenceStorage = storage === undefined ? globalThis.localStorage : storage;
    return normalizePortalTheme(preferenceStorage?.getItem?.(PORTAL_THEME_STORAGE_KEY));
  } catch {
    return "obsidian";
  }
}

export function persistPortalThemePreference(theme, storage) {
  const normalized = normalizePortalTheme(theme);
  try {
    const preferenceStorage = storage === undefined ? globalThis.localStorage : storage;
    preferenceStorage?.setItem?.(PORTAL_THEME_STORAGE_KEY, normalized);
  } catch {
    // Appearance preferences are optional; a blocked storage API must never block work.
  }
  return normalized;
}

export function boundedRoundRobinWindow(items, cursor = 0, limit = 4) {
  const safeItems = Array.isArray(items) ? items : [];
  if (!safeItems.length) return { items: [], nextCursor: 0 };
  const requestedCursor = Number(cursor);
  const start = Number.isInteger(requestedCursor)
    ? ((requestedCursor % safeItems.length) + safeItems.length) % safeItems.length
    : 0;
  const requestedLimit = Number(limit);
  const size = Number.isInteger(requestedLimit) && requestedLimit > 0
    ? Math.min(requestedLimit, safeItems.length)
    : Math.min(4, safeItems.length);
  const selected = Array.from(
    { length: size },
    (_, offset) => safeItems[(start + offset) % safeItems.length],
  );
  return {
    items: selected,
    nextCursor: (start + size) % safeItems.length,
  };
}

export function normalizeGenerationFilters(filters = {}) {
  const period = String(filters.period || "4w").toLowerCase();
  const status = String(filters.status || "all").toLowerCase();
  const provider = String(filters.provider || "all").trim().toLowerCase();
  const requestedModel = String(filters.model || "all").trim().toLowerCase();
  const strategyId = String(
    filters.strategyId || filters.strategy_id || "all",
  ).trim().toLowerCase();
  const contentKind = String(filters.contentKind || filters.content_kind || "all").trim().toLowerCase();
  const selectionSource = String(filters.selectionSource || filters.selection_source || "all").trim().toLowerCase();
  const qualityStatus = String(filters.qualityStatus || filters.quality_status || "all").trim().toLowerCase();
  const query = String(filters.query || "").trim().slice(0, 120);
  const requestedVisible = Number(filters.visible);
  const visible = Number.isInteger(requestedVisible) && requestedVisible >= GENERATION_VISIBLE_STEP
    ? Math.min(GENERATION_VISIBLE_CAP, requestedVisible)
    : GENERATION_VISIBLE_STEP;
  return {
    period: GENERATION_PERIODS.has(period) ? period : "4w",
    status: GENERATION_STATUS_GROUPS.has(status) ? status : "all",
    provider: GENERATION_PROVIDERS.has(provider) ? provider : "all",
    model: requestedModel === "all" || GENERATION_MODEL_FILTER_PATTERN.test(requestedModel)
      ? requestedModel
      : "all",
    strategyId: GENERATION_STRATEGIES.has(strategyId) ? strategyId : "all",
    contentKind: GENERATION_CONTENT_KINDS.has(contentKind) ? contentKind : "all",
    selectionSource: GENERATION_SELECTION_SOURCES.has(selectionSource) ? selectionSource : "all",
    qualityStatus: GENERATION_QUALITY_STATUSES.has(qualityStatus) ? qualityStatus : "all",
    query,
    visible,
  };
}

function generationSelectionSnapshot(item) {
  const parameters = item?.parameters && typeof item.parameters === "object"
    ? item.parameters
    : {};
  // Once the server projects the authoritative archive field, its presence is
  // terminal even when the value is null. A legacy row must stay visibly
  // legacy; never resurrect a client/input snapshot from `parameters`.
  const hasAuthoritativeSnapshot = Boolean(item)
    && Object.prototype.hasOwnProperty.call(item, "generation_selection_snapshot");
  const candidates = hasAuthoritativeSnapshot
    ? [item.generation_selection_snapshot]
    : [
      item?.selection_snapshot,
      parameters.generation_selection_snapshot,
      parameters.selection_snapshot,
    ];
  return candidates.find((value) => value && typeof value === "object" && !Array.isArray(value)) || {};
}

function generationArchiveIdentity(item) {
  const parameters = item?.parameters && typeof item.parameters === "object"
    ? item.parameters
    : {};
  const hasAuthoritativeSnapshot = Boolean(item)
    && Object.prototype.hasOwnProperty.call(item, "generation_selection_snapshot");
  const snapshot = generationSelectionSnapshot(item);
  return {
    provider: String(snapshot.provider || item?.provider || (hasAuthoritativeSnapshot ? "" : parameters.provider) || "").trim().toLowerCase(),
    model: String(snapshot.model || item?.model || (hasAuthoritativeSnapshot ? "" : parameters.model) || "").trim().toLowerCase(),
    modelPublicLabel: String(snapshot.model_public_label || item?.model_public_label || (hasAuthoritativeSnapshot ? "" : parameters.model_public_label) || "").trim(),
    contentKind: String(item?.content_kind || (hasAuthoritativeSnapshot ? "" : parameters.content_kind) || "").trim().toLowerCase(),
    selectionSource: String(snapshot.selection_source || item?.selection_source || (hasAuthoritativeSnapshot ? "" : parameters.selection_source) || "").trim().toLowerCase(),
    qualityStatus: String(snapshot.acceptance_status_at_launch || item?.quality_status || (hasAuthoritativeSnapshot ? "" : parameters.quality_status) || "").trim().toLowerCase(),
  };
}

function generationStatus(item) {
  const parameters = item?.parameters && typeof item.parameters === "object" ? item.parameters : {};
  return String(item?.status || parameters.job_status || parameters.status || "queued").toLowerCase();
}

function generationPeriodCutoff(period, nowMs) {
  if (period === "all") return null;
  const weeks = period === "week" ? 1 : period === "12w" ? 12 : 4;
  const now = new Date(nowMs);
  if (!Number.isFinite(now.getTime())) return null;
  const mondayOffset = (now.getDay() + 6) % 7;
  now.setHours(0, 0, 0, 0);
  now.setDate(now.getDate() - mondayOffset);
  return now.getTime() - (weeks - 1) * WEEK_MS;
}

function matchesGenerationStatus(item, statusGroup) {
  if (statusGroup === "all") return true;
  const status = generationStatus(item);
  if (statusGroup === "active") return ACTIVE_GENERATION_STATUSES.has(status);
  if (statusGroup === "ready") return READY_GENERATION_STATUSES.has(status);
  return ISSUE_GENERATION_STATUSES.has(status);
}

function normalizedSearchText(value) {
  return String(value || "").normalize("NFKC").toLocaleLowerCase("ru-RU");
}

export function filterGenerationBatches(items, filters = {}, nowMs = Date.now()) {
  const safeItems = Array.isArray(items) ? items : [];
  const normalized = normalizeGenerationFilters(filters);
  const cutoff = generationPeriodCutoff(normalized.period, nowMs);
  const query = normalizedSearchText(normalized.query);

  return safeItems.filter((item) => {
    if (!matchesGenerationStatus(item, normalized.status)) return false;
    const identity = generationArchiveIdentity(item);
    if (normalized.provider !== "all" && identity.provider !== normalized.provider) return false;
    if (normalized.model !== "all" && identity.model !== normalized.model) return false;
    if (
      normalized.strategyId !== "all"
      && String(item?.strategy_id || "").trim().toLowerCase()
        !== normalized.strategyId
    ) return false;
    if (normalized.contentKind !== "all" && identity.contentKind !== normalized.contentKind) return false;
    if (normalized.selectionSource !== "all" && identity.selectionSource !== normalized.selectionSource) return false;
    if (normalized.qualityStatus !== "all" && identity.qualityStatus !== normalized.qualityStatus) return false;
    if (cutoff !== null) {
      const createdAt = new Date(item?.created_at || "").getTime();
      if (Number.isFinite(createdAt) && createdAt < cutoff) return false;
    }
    if (!query) return true;
    return normalizedSearchText([
      item?.name,
      item?.public_id,
      item?.id,
      item?.sku,
      item?.product_name,
      identity.provider,
      identity.model,
      identity.modelPublicLabel,
      item?.strategy_id,
    ].filter(Boolean).join(" ")).includes(query);
  });
}

export function generationWeekLabel(value) {
  const createdAt = new Date(value || "");
  if (!Number.isFinite(createdAt.getTime())) return "Дата не указана";
  const start = new Date(createdAt);
  const mondayOffset = (start.getDay() + 6) % 7;
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - mondayOffset);
  const end = new Date(start.getTime() + 6 * 24 * 60 * 60 * 1_000);
  const formatter = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
  return `${formatter.format(start)} — ${formatter.format(end)}`;
}

export function mergeGenerationPages(currentItems, incomingItems) {
  const merged = [];
  const seen = new Set();
  for (const item of [...(Array.isArray(currentItems) ? currentItems : []), ...(Array.isArray(incomingItems) ? incomingItems : [])]) {
    const key = String(item?.id || item?.public_id || "");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(item);
  }
  return merged;
}

export function generationArchiveCursor(items) {
  const safeItems = Array.isArray(items) ? items : [];
  const cursor = safeItems.at(-1)?._cursor;
  const at = String(cursor?.at || "").trim();
  const id = String(cursor?.id || "").trim();
  return at && id ? { generation_batches: { at, id } } : null;
}
