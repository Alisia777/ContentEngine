const MODES = new Set(["", "mock", "real_photo", "real_seedance", "real_gen4"]);
const GENERATION_STRATEGY_IDS = new Set([
  "viral_avatar_ugc",
  "viral_product_swap",
  "viral_rebuild",
]);
const GENERATION_STRATEGY_SOURCE_BASES = new Set([
  "ai_research_recommendation",
  "operator_summary_only",
  "exact_source_video",
]);
const PRODUCT_CATEGORIES = new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
const PLATFORMS = new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]);
const FORMATS = new Set(["9:16", "1:1", "16:9", "2048:2048"]);
const VIDEO_DURATIONS = new Set(["2", "4", "5", "8", "10", "12", "15"]);
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;

export const GENERATION_FORM_DRAFT_VERSION = 4;
export const GENERATION_FORM_DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1_000;

function boundedText(value, maximum) {
  const normalized = String(value ?? "").trim();
  return normalized.length <= maximum ? normalized : normalized.slice(0, maximum);
}

function optionalUuid(value) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return UUID_RE.test(normalized) ? normalized : "";
}

function boundedInteger(value, minimum, maximum, fallback) {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric >= minimum && numeric <= maximum
    ? numeric
    : fallback;
}

function normalizedContext(value = {}) {
  return {
    projectId: optionalUuid(value.projectId || value.project_id),
    handoffDraftId: boundedText(value.handoffDraftId, 180),
    handoffResearchId: boundedText(value.handoffResearchId, 180),
    repairSourceReviewId: optionalUuid(value.repairSourceReviewId),
  };
}

export function generationDraftContextMatches(draftContext, activeContext) {
  const draft = normalizedContext(draftContext);
  const active = normalizedContext(activeContext);
  return Boolean(draft.projectId)
    && draft.projectId === active.projectId
    && draft.handoffDraftId === active.handoffDraftId
    && draft.handoffResearchId === active.handoffResearchId
    && draft.repairSourceReviewId === active.repairSourceReviewId;
}

export function buildGenerationFormDraft(value = {}, {
  now = Date.now(),
  context = {},
} = {}) {
  const mode = MODES.has(String(value.generation_mode || ""))
    ? String(value.generation_mode || "")
    : "";
  const real = Boolean(mode && mode !== "mock");
  const durationSeconds = String(value.duration_seconds ?? "").trim();
  const productCategory = String(value.product_category || "").trim();
  const platform = String(value.platform || "").trim();
  const format = String(value.format || "").trim();
  const mediaIds = [...new Set(
    (Array.isArray(value.media_ids) ? value.media_ids : [])
      .map((item) => boundedText(item, 180))
      .filter(Boolean),
  )].slice(0, real ? 5 : 50);
  const requestedPrimaryMediaId = boundedText(value.primary_media_id, 180);
  const primaryMediaId = mediaIds.includes(requestedPrimaryMediaId)
    ? requestedPrimaryMediaId
    : mediaIds[0] || "";

  return {
    version: GENERATION_FORM_DRAFT_VERSION,
    updatedAt: Number.isFinite(Number(now)) ? Number(now) : Date.now(),
    context: normalizedContext(context),
    values: {
      generation_mode: mode,
      duration_seconds: VIDEO_DURATIONS.has(durationSeconds)
        ? durationSeconds
        : mode === "real_seedance"
          ? "8"
          : mode === "real_gen4"
            ? "5"
            : "",
      campaign_id: optionalUuid(value.campaign_id),
      campaign_selection_required: value.campaign_selection_required === true,
      sku: boundedText(value.sku, 120),
      product_name: boundedText(value.product_name, 180),
      product_category: PRODUCT_CATEGORIES.has(productCategory)
        ? productCategory
        : "",
      platform: PLATFORMS.has(platform) ? platform : "",
      destination_ref: boundedText(value.destination_ref, 240),
      assignee_id: optionalUuid(value.assignee_id),
      payout_rub: boundedText(value.payout_rub, 32),
      count: boundedInteger(value.count, 1, 50, real ? 1 : 5),
      format: FORMATS.has(format) ? format : (real ? "9:16" : "9:16"),
      brief: boundedText(value.brief, 4_000),
      scenario_intent: boundedText(value.scenario_intent, 1_200),
      generation_reference_url: boundedText(
        value.generation_reference_url,
        500,
      ),
      generation_reference_mechanics: boundedText(
        value.generation_reference_mechanics,
        360,
      ),
      generation_reference_source_access_confirmed:
        value.generation_reference_source_access_confirmed === true,
      generation_reference_transformative_use_confirmed:
        value.generation_reference_transformative_use_confirmed === true,
      generation_strategy_id: GENERATION_STRATEGY_IDS.has(
        String(value.generation_strategy_id || ""),
      ) ? String(value.generation_strategy_id) : "",
      generation_strategy_version: boundedText(
        value.generation_strategy_version,
        80,
      ),
      generation_strategy_recipe_version: boundedText(
        value.generation_strategy_recipe_version,
        80,
      ),
      generation_strategy_source_basis: GENERATION_STRATEGY_SOURCE_BASES.has(
        String(value.generation_strategy_source_basis || ""),
      ) ? String(value.generation_strategy_source_basis) : "",
      // Предел по стратегии черновика: сохранённые 20 секунд "Дуэта" -
      // законное значение по строке реестра heygen, и обнулять его при
      // восстановлении нельзя. Раньше поле молча пустело без объяснения.
      generation_strategy_duration_seconds: boundedInteger(
        value.generation_strategy_duration_seconds,
        String(value.generation_strategy_id || "") === "viral_avatar_ugc" ? 3 : 4,
        String(value.generation_strategy_id || "") === "viral_avatar_ugc" ? 60 : 15,
        0,
      ),
      generation_strategy_ratio: /^\d{3,4}:\d{3,4}$/u.test(
        String(value.generation_strategy_ratio || ""),
      ) ? String(value.generation_strategy_ratio) : "",
      generation_strategy_resolution: ["720p", "1080p"].includes(
        String(value.generation_strategy_resolution || ""),
      ) ? String(value.generation_strategy_resolution) : "",
      generation_strategy_audio: ["true", "false"].includes(
        String(value.generation_strategy_audio || ""),
      ) ? String(value.generation_strategy_audio) : "",
      generation_strategy_source_video_id: optionalUuid(
        value.generation_strategy_source_video_id,
      ),
      generation_strategy_avatar_media_id: optionalUuid(
        value.generation_strategy_avatar_media_id,
      ),
      generation_strategy_original_product_media_id: optionalUuid(
        value.generation_strategy_original_product_media_id,
      ),
      // Rights, likeness and transformative-use confirmations belong to one
      // exact launch. A local draft may restore choices, but never consent.
      generation_strategy_attestations: {},
      media_ids: mediaIds,
      primary_media_id: primaryMediaId,
    },
  };
}

export function normalizeGenerationFormDraft(raw, {
  now = Date.now(),
  maxAgeMs = GENERATION_FORM_DRAFT_MAX_AGE_MS,
  activeContext = {},
} = {}) {
  if (
    !raw
    || typeof raw !== "object"
    || Array.isArray(raw)
    || raw.version !== GENERATION_FORM_DRAFT_VERSION
    || !raw.values
    || typeof raw.values !== "object"
    || Array.isArray(raw.values)
  ) return null;
  const updatedAt = Number(raw.updatedAt);
  const referenceNow = Number(now);
  const allowedAge = Number(maxAgeMs);
  if (
    !Number.isFinite(updatedAt)
    || !Number.isFinite(referenceNow)
    || !Number.isFinite(allowedAge)
    || allowedAge <= 0
    || updatedAt <= 0
    || updatedAt > referenceNow + 5 * 60 * 1_000
    || referenceNow - updatedAt > allowedAge
    || !generationDraftContextMatches(raw.context, activeContext)
  ) return null;
  return buildGenerationFormDraft(raw.values, {
    now: updatedAt,
    context: raw.context,
  });
}
