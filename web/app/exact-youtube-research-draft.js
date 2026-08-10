/*
 * Short-lived Research -> exact YouTube evidence draft.
 *
 * The server remains authoritative for product/media identity and access. This
 * module only preserves editable operator input while the same browser tab
 * leaves Research to attach an MP4 and returns to the exact evidence form.
 */

export const EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY =
  "contentengine.research.youtube.exact-draft.v1";
export const EXACT_YOUTUBE_RESEARCH_DRAFT_MAX_AGE_MS = 4 * 60 * 60 * 1_000;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const AI_CATEGORIES = new Set([
  "cosmetics", "baa", "sports_food", "food", "household", "apparel",
  "electronics", "other",
]);
const PLATFORMS = new Set([
  "instagram", "youtube", "vk", "wildberries", "ozon",
]);
const OBJECTIVES = new Set(["conversion", "awareness", "ugc", "education"]);

function uuid(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return UUID_PATTERN.test(normalized) ? normalized : "";
}

function compactText(value, limit) {
  const normalized = String(value ?? "").replace(/\s+/gu, " ").trim();
  return normalized.length <= limit ? normalized : "";
}

function multilineText(value, limit) {
  const normalized = String(value ?? "")
    .replace(/\r\n?/gu, "\n")
    .split("\n")
    .map((line) => line.replace(/\s+/gu, " ").trim())
    .filter(Boolean)
    .join("\n")
    .trim();
  return normalized.length <= limit ? normalized : "";
}

function httpsUrl(value) {
  const normalized = String(value ?? "").trim();
  if (!normalized) return "";
  if (normalized.length > 1_000) return "";
  try {
    const parsed = new URL(normalized);
    return parsed.protocol === "https:" ? parsed.toString() : "";
  } catch {
    return "";
  }
}

function identity(input = {}) {
  return {
    organization_id: uuid(input.organization_id ?? input.organizationId),
    user_id: uuid(input.user_id ?? input.userId),
    project_id: uuid(input.project_id ?? input.projectId),
    source_id: uuid(input.source_id ?? input.sourceId),
  };
}

function identityComplete(value) {
  return Object.values(value).every(Boolean);
}

function uniqueAllowed(values, allowed, limit) {
  const result = [];
  for (const value of Array.isArray(values) ? values : []) {
    const normalized = String(value || "").trim().toLowerCase();
    if (!allowed.has(normalized) || result.includes(normalized)) continue;
    result.push(normalized);
    if (result.length >= limit) break;
  }
  return result;
}

function uniqueUuids(values, limit = 5) {
  const result = [];
  for (const value of Array.isArray(values) ? values : []) {
    const normalized = uuid(value);
    if (!normalized || result.includes(normalized)) continue;
    result.push(normalized);
    if (result.length >= limit) break;
  }
  return result;
}

function normalizedDraft(input = {}) {
  const categoryInput = String(
    input.product_category ?? input.productCategory ?? "",
  ).trim().toLowerCase();
  const objectiveInput = String(input.objective || "").trim().toLowerCase();
  return {
    product_category: AI_CATEGORIES.has(categoryInput) ? categoryInput : "",
    category_name: compactText(
      input.category_name ?? input.categoryName,
      160,
    ),
    research_focus: compactText(
      input.research_focus ?? input.researchFocus,
      200,
    ),
    marketplace_url: httpsUrl(
      input.marketplace_url ?? input.marketplaceUrl,
    ),
    competitor_references: multilineText(
      input.competitor_references ?? input.competitorReferences,
      650,
    ),
    objective: OBJECTIVES.has(objectiveInput) ? objectiveInput : "",
    known_facts: multilineText(
      input.known_facts ?? input.knownFacts,
      500,
    ),
    platforms: uniqueAllowed(input.platforms, PLATFORMS, 5),
    source_media_ids: uniqueUuids(
      input.source_media_ids ?? input.sourceMediaIds,
      5,
    ),
  };
}

function parseStored(storage) {
  try {
    const raw = storage?.getItem?.(EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : null;
  } catch {
    return null;
  }
}

export function writeExactYoutubeResearchDraft(storage, input = {}) {
  const exactIdentity = identity(input);
  if (!identityComplete(exactIdentity)) return false;
  // Retain the old v1 field for rollback/mixed-cache compatibility only.
  // sessionStorage provides tab locality; this volatile UUID is not authority.
  const legacySessionId = uuid(input.session_id ?? input.sessionId);
  const requestedAt = compactText(
    input.requested_at ?? input.requestedAt,
    64,
  ) || new Date().toISOString();
  if (!Number.isFinite(Date.parse(requestedAt))) return false;
  try {
    storage?.setItem?.(
      EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        ...exactIdentity,
        ...(legacySessionId ? { session_id: legacySessionId } : {}),
        ...normalizedDraft(input),
        requested_at: requestedAt,
      }),
    );
    return true;
  } catch {
    return false;
  }
}

export function readExactYoutubeResearchDraft(
  storage,
  expected = {},
  {
    now = Date.now(),
    maxAgeMs = EXACT_YOUTUBE_RESEARCH_DRAFT_MAX_AGE_MS,
  } = {},
) {
  const expectedIdentity = identity(expected);
  if (!identityComplete(expectedIdentity)) {
    return { ok: false, code: "draft_context_invalid" };
  }
  const parsed = parseStored(storage);
  if (!parsed) return { ok: false, code: "draft_missing" };
  if (parsed.version !== 1) {
    return { ok: false, code: "draft_payload_invalid" };
  }
  const storedIdentity = identity(parsed);
  if (
    !identityComplete(storedIdentity)
    || Object.entries(expectedIdentity).some(
      ([key, value]) => storedIdentity[key] !== value,
    )
  ) return { ok: false, code: "draft_scope_mismatch" };
  const requestedAt = Date.parse(compactText(parsed.requested_at, 64));
  const age = Number(now) - requestedAt;
  if (
    !Number.isFinite(requestedAt)
    || !Number.isFinite(age)
    || age < -60_000
    || age > Math.max(60_000, Number(maxAgeMs) || 0)
  ) return { ok: false, code: "draft_expired" };
  return {
    ok: true,
    code: "ok",
    draft: {
      version: 1,
      ...expectedIdentity,
      ...normalizedDraft(parsed),
      requested_at: new Date(requestedAt).toISOString(),
    },
  };
}

export function clearExactYoutubeResearchDraft(storage) {
  try {
    storage?.removeItem?.(EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function exactYoutubeResearchObjective(draft, base = "") {
  const source = normalizedDraft(draft || {});
  const objectiveLabels = {
    conversion: "заказы и переходы",
    awareness: "узнаваемость товара",
    ugc: "нативный UGC-обзор",
    education: "объяснить применение",
  };
  const lines = [compactText(base, 1_200)];
  if (source.category_name) lines.push(`Точная категория: ${source.category_name}.`);
  if (source.research_focus) lines.push(`Фокус исследования: ${source.research_focus}.`);
  if (source.known_facts) lines.push(`Подтверждённые вводные: ${source.known_facts}`);
  if (source.objective) {
    lines.push(`Главная цель: ${objectiveLabels[source.objective]}.`);
  }
  if (source.competitor_references) {
    lines.push(`Ориентиры для поиска: ${source.competitor_references}`);
  }
  return lines.filter(Boolean).join("\n").slice(0, 1_200).trim();
}

export function exactYoutubeResearchHydration(
  draft,
  availableSourceMediaIds = [],
  baseObjective = "",
) {
  const source = normalizedDraft(draft || {});
  const available = new Set(uniqueUuids(availableSourceMediaIds, 100));
  const sourceMediaId = source.source_media_ids.find((id) => available.has(id))
    || "";
  return {
    productCategory: source.product_category,
    marketplaceUrl: source.marketplace_url,
    platforms: [...source.platforms],
    sourceMediaId,
    objective: exactYoutubeResearchObjective(source, baseObjective),
  };
}
