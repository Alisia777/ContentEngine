export const PORTAL_THEME_STORAGE_KEY = "contentengine.portal-theme.v1";

export const PORTAL_THEMES = Object.freeze([
  Object.freeze({
    id: "emerald",
    label: "Изумруд",
    description: "Фирменный зелёный и золото",
  }),
  Object.freeze({
    id: "bordeaux",
    label: "Бордо",
    description: "Винный оттенок и розовое золото",
  }),
  Object.freeze({
    id: "sapphire",
    label: "Сапфир",
    description: "Глубокий синий и шампань",
  }),
]);

export const GENERATION_ARCHIVE_PAGE_SIZE = 50;
export const GENERATION_VISIBLE_STEP = 20;
export const GENERATION_VISIBLE_CAP = 200;

const PORTAL_THEME_IDS = new Set(PORTAL_THEMES.map((theme) => theme.id));
const GENERATION_PERIODS = new Set(["week", "4w", "12w", "all"]);
const GENERATION_STATUS_GROUPS = new Set(["all", "active", "ready", "issue"]);
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
  return PORTAL_THEME_IDS.has(normalized) ? normalized : "emerald";
}

export function readPortalThemePreference(storage) {
  try {
    const preferenceStorage = storage === undefined ? globalThis.localStorage : storage;
    return normalizePortalTheme(preferenceStorage?.getItem?.(PORTAL_THEME_STORAGE_KEY));
  } catch {
    return "emerald";
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
  const query = String(filters.query || "").trim().slice(0, 120);
  const requestedVisible = Number(filters.visible);
  const visible = Number.isInteger(requestedVisible) && requestedVisible >= GENERATION_VISIBLE_STEP
    ? Math.min(GENERATION_VISIBLE_CAP, requestedVisible)
    : GENERATION_VISIBLE_STEP;
  return {
    period: GENERATION_PERIODS.has(period) ? period : "4w",
    status: GENERATION_STATUS_GROUPS.has(status) ? status : "all",
    query,
    visible,
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
