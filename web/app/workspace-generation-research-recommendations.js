/*
 * ContentEngine · AI-first, human-editable research recommendations.
 *
 * Only human-approved research selections are read. Every recommendation stays
 * advisory until a human explicitly applies its exact selection + position.
 * After a human edits a field the adapter never overwrites it automatically.
 */

import {
  cachedGenerationAiResearchWorkingDraft,
  clearGenerationAiResearchWorkingDraft,
  generationAiResearchEditableFieldsFromForm,
  preferAuthoritativeGenerationAiResearchWorkingDraft,
  readGenerationAiResearchWorkingDraft,
  resolveGenerationAiResearchProductIdentity,
  resolveGenerationExpectedProductMatch,
  saveGenerationAiResearchWorkingDraft,
} from "./generation-ai-research-working-draft.js?v=20260826.rebuild-clean.60";

const ROUTE = "/workspace/generation";
const RPC_RECOMMENDATIONS = "contentengine_generation_research_recommendations";
const RPC_RECOMMENDATION = "contentengine_generation_research_recommendation";
const ROOT_ATTRIBUTE = "data-generation-research-recommendations";
const STATE_PREFIX = "contentengine.generation.research-recommendation.v3";
const MAX_BRIEF_LENGTH = 1180;
const PRESET_EVENT = "contentengine:generation-research-preset-applied";
const PRESET_OPT_OUT_EVENT = "contentengine:generation-research-preset-opt-out";
const GENERATION_INTENT_PREFIX = "contentengine.ai-research-generation.intent.v1:";
const GENERATION_INTENT_MAX_AGE_MS = 5 * 60 * 1000;
const MAX_RESEARCH_CONCLUSION_LINES = 6;
const MAX_RESEARCH_CONCLUSION_LENGTH = 260;
// Однократная ошибка чтения общего черновика больше не замораживает форму до
// F5: сначала автоматические повторы с нарастающей паузой, затем явная кнопка.
const WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS = Object.freeze([2_000, 5_000, 15_000]);
const PRESET_FIELDS = Object.freeze([
  "product_category",
  "platform",
  "mode",
  "duration_seconds",
  "format",
  "brief",
]);
const PRESET_FORM_FIELDS = Object.freeze({
  product_category: "product_category",
  platform: "platform",
  mode: "generation_mode",
  duration_seconds: "duration_seconds",
  format: "format",
  brief: "brief",
});
const PRESET_FIELD_LABELS = Object.freeze({
  product_category: "категория",
  platform: "площадка",
  mode: "режим",
  duration_seconds: "длительность",
  format: "формат",
  brief: "замысел",
});
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
const GENERATION_PLATFORMS = new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]);
const GENERATION_FORMATS = new Set(["9:16", "1:1", "16:9"]);
const GENERATION_MODE_DURATIONS = Object.freeze({
  real_gen4: new Set([2, 5, 8, 10]),
  real_seedance: new Set([4, 8, 12, 15]),
});
const GENERATION_MODE_ALIASES = Object.freeze({
  mock: "mock",
  real_photo: "real_photo",
  photo: "real_photo",
  image: "real_photo",
  seedream: "real_photo",
  seedream5_lite: "real_photo",
  real_gen4: "real_gen4",
  gen4: "real_gen4",
  gen4_turbo: "real_gen4",
  product_animation: "real_gen4",
  real_seedance: "real_seedance",
  seedance: "real_seedance",
  seedance2_fast: "real_seedance",
  ugc_video: "real_seedance",
});

const runtime = {
  form: null,
  root: null,
  apiPromise: null,
  loading: false,
  loadPending: false,
  loadForcePending: false,
  applying: false,
  loadTimer: 0,
  key: "",
  response: null,
  activeIndex: -1,
  mountQueued: false,
  workingDraft: null,
  workingDraftProjectId: "",
  workingDraftHydrating: false,
  workingDraftHydratePending: null,
  workingDraftSaveTimer: 0,
  workingDraftSaving: false,
  workingDraftSavePending: false,
  workingDraftClearPending: false,
  workingDraftConflict: false,
  workingDraftAuthority: "unknown",
  workingDraftAuthorityProjectId: "",
  workingDraftHydrateRetryCount: 0,
  workingDraftHydrateRetryTimer: 0,
  workingDraftHydrateRetryDue: false,
  explicitApplyTargetKey: "",
  freshRouteApplyTargetKey: "",
  freshRouteApplyProjectId: "",
  tombstoneReplacementKey: "",
};

function setWorkingDraftAuthority(projectIdValue, authority) {
  const normalizedProjectId = normalizedUuid(projectIdValue);
  if (normalizedProjectId !== runtime.workingDraftAuthorityProjectId) {
    // A project/form switch starts a clean retry budget for hydration.
    runtime.workingDraftHydrateRetryCount = 0;
    runtime.workingDraftHydrateRetryDue = false;
    window.clearTimeout(runtime.workingDraftHydrateRetryTimer);
    runtime.workingDraftHydrateRetryTimer = 0;
  }
  runtime.workingDraftAuthorityProjectId = normalizedProjectId;
  runtime.workingDraftAuthority = authority;
}

function workingDraftAuthorityVerified(context) {
  return runtime.workingDraftAuthority === "verified"
    && runtime.workingDraftAuthorityProjectId === normalizedUuid(context?.projectId);
}

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

function routeRecommendationTarget() {
  const params = routeParams();
  const selectionId = normalizedUuid(params.get("selection_id"));
  const position = Number(params.get("recommendation_position"));
  const intent = normalizedUuid(params.get("recommendation_intent"));
  return selectionId && [1, 2, 3].includes(position)
    ? { selectionId, recommendationPosition: position, intent }
    : null;
}

function recommendationTargetKey(target) {
  return target?.selectionId && [1, 2, 3].includes(target.recommendationPosition)
    ? `${target.selectionId}:${target.recommendationPosition}`
    : "";
}

export function researchRecommendationApplicationAuthorized(
  target,
  { freshRouteTargetKey = "", explicitApplyTargetKey = "" } = {},
) {
  const targetKey = recommendationTargetKey(target);
  return Boolean(
    targetKey
    && (targetKey === freshRouteTargetKey || targetKey === explicitApplyTargetKey),
  );
}

export function explicitResearchRecommendationForTarget(
  recommendations,
  target,
  { requireSingleton = false } = {},
) {
  const targetKey = recommendationTargetKey(target);
  const list = Array.isArray(recommendations) ? recommendations : [];
  if (!targetKey || (requireSingleton && list.length !== 1)) return null;
  const matches = list.filter((item) => recommendationTargetKey({
    selectionId: recommendationSelectionId(item),
    recommendationPosition: recommendationPosition(item),
  }) === targetKey);
  return matches.length === 1 ? matches[0] : null;
}

export function researchRecommendationReplacementAuthorizationKey(
  projectIdValue,
  target,
) {
  const normalizedProjectId = normalizedUuid(projectIdValue);
  const targetKey = recommendationTargetKey(target);
  return normalizedProjectId && targetKey
    ? `${normalizedProjectId}:${targetKey}`
    : "";
}

function authorizeTombstoneReplacement(context, target) {
  runtime.tombstoneReplacementKey =
    researchRecommendationReplacementAuthorizationKey(context?.projectId, target);
}

function tombstoneReplacementAuthorized(context, target) {
  const key = researchRecommendationReplacementAuthorizationKey(
    context?.projectId,
    target,
  );
  return Boolean(key && runtime.tombstoneReplacementKey === key);
}

function clearTombstoneReplacementAuthorization(context = null, target = null) {
  if (
    !context
    || !target
    || tombstoneReplacementAuthorized(context, target)
  ) runtime.tombstoneReplacementKey = "";
}

export function validExplicitResearchRecommendationIntent(
  target,
  rawRecord,
  now = Date.now(),
) {
  const intent = normalizedUuid(target?.intent);
  if (!intent || !recommendationTargetKey(target)) return false;
  let record;
  try {
    record = typeof rawRecord === "string" ? JSON.parse(rawRecord) : rawRecord;
  } catch {
    return false;
  }
  const createdAt = Number(record?.createdAt);
  return recommendationTargetKey(record) === recommendationTargetKey(target)
    && Number.isFinite(createdAt)
    && createdAt <= Number(now)
    && Number(now) - createdAt <= GENERATION_INTENT_MAX_AGE_MS;
}

function explicitResearchRecommendationIntentIsFresh(target) {
  const intent = normalizedUuid(target?.intent);
  if (!intent) return false;
  try {
    return validExplicitResearchRecommendationIntent(
      target,
      globalThis.localStorage?.getItem(`${GENERATION_INTENT_PREFIX}${intent}`),
    );
  } catch {
    return false;
  }
}

function consumeExplicitResearchRecommendationIntent(target) {
  const intent = normalizedUuid(target?.intent);
  if (!intent) return;
  try {
    globalThis.localStorage?.removeItem(`${GENERATION_INTENT_PREFIX}${intent}`);
  } catch {
    // The route is still consumed even when local storage is unavailable.
  }
}

export function routeAfterResearchRecommendationConsumption(
  rawHash,
  expectedTarget = null,
) {
  const raw = String(rawHash || "").replace(/^#/, "");
  const [path, query = ""] = raw.split("?", 2);
  const params = new URLSearchParams(query);
  const current = {
    selectionId: normalizedUuid(params.get("selection_id")),
    recommendationPosition: Number(params.get("recommendation_position")),
  };
  if (
    expectedTarget
    && recommendationTargetKey(current) !== recommendationTargetKey(expectedTarget)
  ) return `#${raw}`;
  params.delete("selection_id");
  params.delete("recommendation_position");
  params.delete("recommendation_intent");
  const nextQuery = params.toString();
  return `#${path}${nextQuery ? `?${nextQuery}` : ""}`;
}

function consumeRouteRecommendationTarget(target = routeRecommendationTarget()) {
  if (!target) return false;
  consumeExplicitResearchRecommendationIntent(target);
  if (typeof window?.history?.replaceState !== "function") return false;
  const currentHash = String(window.location?.hash || "");
  const nextHash = routeAfterResearchRecommendationConsumption(currentHash, target);
  if (!nextHash || nextHash === currentHash) return false;
  const nextUrl = `${window.location.pathname || ""}${window.location.search || ""}${nextHash}`;
  window.history.replaceState(window.history.state, "", nextUrl);
  return true;
}

function clean(value, limit = 4000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function normalizedUuid(value) {
  const candidate = clean(value, 80).toLowerCase();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(candidate)
    ? candidate
    : "";
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function asList(value, limit = 10) {
  return (Array.isArray(value) ? value : [])
    .slice(0, limit)
    .map((item) => {
      if (typeof item === "string") return clean(item, 500);
      if (!item || typeof item !== "object") return "";
      return clean(
        item.label || item.title || item.name || item.text || item.summary
          || item.claim || item.pain || item.objection || JSON.stringify(item),
        500,
      );
    })
    .filter(Boolean);
}

function shotLines(value) {
  if (typeof value === "string") {
    return value.split(/\r?\n/gu).map((line) => clean(line, 400)).filter(Boolean);
  }
  if (!Array.isArray(value)) return [];
  return value.slice(0, 10).map((shot) => {
    if (typeof shot === "string") return clean(shot, 500);
    const source = object(shot);
    const seconds = clean(source.seconds || source.time || source.duration, 50);
    const visual = clean(source.visual || source.shot || source.description, 500);
    const onScreen = clean(source.on_screen_text || source.text, 250);
    return [seconds && `${seconds}:`, visual, onScreen && `Текст: ${onScreen}`]
      .filter(Boolean)
      .join(" ");
  }).filter(Boolean);
}

function truncateBrief(text, limit = MAX_BRIEF_LENGTH) {
  const value = String(text || "").trim();
  if (value.length <= limit) return value;
  const sliced = value.slice(0, limit - 1);
  const boundary = Math.max(sliced.lastIndexOf("\n"), sliced.lastIndexOf(". "));
  return `${sliced.slice(0, boundary > limit * 0.72 ? boundary : limit - 1).trim()}…`;
}

function compactSectionText(value, limit) {
  const normalized = String(value || "").replace(/\r\n?/gu, "\n").trim();
  if (normalized.length <= limit) return normalized;
  if (limit <= 1) return normalized.slice(0, Math.max(0, limit));
  const slice = normalized.slice(0, limit - 1);
  const boundary = Math.max(
    slice.lastIndexOf("\n"),
    slice.lastIndexOf(" · "),
    slice.lastIndexOf(". "),
    slice.lastIndexOf(", "),
    slice.lastIndexOf(" "),
  );
  const compacted = slice.slice(
    0,
    boundary >= Math.max(12, Math.floor(limit * 0.62))
      ? boundary
      : limit - 1,
  ).trim().replace(/[,:;\s]+$/u, "");
  return `${compacted || slice.trim()}…`;
}

/**
 * Compact complete labelled sections instead of truncating the assembled
 * string.  Safety/provenance tails always retain a value; a normal CTA up to
 * 220 characters is kept verbatim.  This prevents a provider-bound prompt
 * from ending at a dangling `CTA:` label and silently losing proof/avoidance.
 */
export function compactResearchRecommendationSections(
  sections,
  limit = MAX_BRIEF_LENGTH,
) {
  const normalized = (Array.isArray(sections) ? sections : [])
    .map(([title, value]) => [clean(title, 80), String(value || "").trim()])
    .filter(([title, value]) => title && value);
  if (!normalized.length) return "";
  const overhead = normalized.reduce(
    (total, [title]) => total + title.length + 2,
    Math.max(0, normalized.length - 1) * 2,
  );
  const capacity = Math.max(normalized.length, Number(limit) - overhead);
  const minimumByTitle = {
    "ТОВАР": 36,
    "КОНЦЕПЦИЯ": 54,
    "ХУК": 54,
    "КЛЮЧЕВОЕ СООБЩЕНИЕ": 64,
    "АУДИТОРИЯ": 36,
    "РЕПЛИКА / СЮЖЕТ": 70,
    "КАДРЫ": 90,
    "ВИЗУАЛ": 44,
    "CTA": 60,
    "ДОКАЗАТЕЛЬСТВА": 72,
    "НЕ ОБЕЩАТЬ / УЧЕСТЬ": 90,
  };
  const weightByTitle = {
    "ТОВАР": 1,
    "КОНЦЕПЦИЯ": 2,
    "ХУК": 2,
    "КЛЮЧЕВОЕ СООБЩЕНИЕ": 2,
    "АУДИТОРИЯ": 1,
    "РЕПЛИКА / СЮЖЕТ": 3,
    "КАДРЫ": 3,
    "ВИЗУАЛ": 2,
    "CTA": 4,
    "ДОКАЗАТЕЛЬСТВА": 4,
    "НЕ ОБЕЩАТЬ / УЧЕСТЬ": 5,
  };
  const allocations = normalized.map(([title, value]) => {
    const minimum = title === "CTA" && value.length <= 220
      ? value.length
      : Math.min(value.length, minimumByTitle[title] || 36);
    return Math.max(1, minimum);
  });
  let allocated = allocations.reduce((sum, value) => sum + value, 0);
  if (allocated > capacity) {
    const protectedTitles = new Set([
      "CTA", "ДОКАЗАТЕЛЬСТВА", "НЕ ОБЕЩАТЬ / УЧЕСТЬ",
    ]);
    for (let index = 0; index < allocations.length && allocated > capacity; index += 1) {
      if (protectedTitles.has(normalized[index][0])) continue;
      const reducible = Math.max(0, allocations[index] - 12);
      const reduction = Math.min(reducible, allocated - capacity);
      allocations[index] -= reduction;
      allocated -= reduction;
    }
  }
  while (allocated < capacity) {
    const eligible = normalized
      .map(([title, value], index) => ({
        index,
        remaining: value.length - allocations[index],
        weight: weightByTitle[title] || 1,
      }))
      .filter((item) => item.remaining > 0);
    if (!eligible.length) break;
    const totalWeight = eligible.reduce((sum, item) => sum + item.weight, 0);
    const available = capacity - allocated;
    let granted = 0;
    eligible.forEach((item) => {
      if (allocated + granted >= capacity) return;
      const share = Math.max(
        1,
        Math.floor((available * item.weight) / totalWeight),
      );
      const increment = Math.min(
        item.remaining,
        share,
        capacity - allocated - granted,
      );
      allocations[item.index] += increment;
      granted += increment;
    });
    if (!granted) break;
    allocated += granted;
  }
  const result = normalized.map(([title, value], index) => (
    `${title}:\n${compactSectionText(value, allocations[index])}`
  )).join("\n\n");
  return result.length <= limit ? result : truncateBrief(result, limit);
}

// Одна рекомендация ИИ-центра — три разных текста, потому что у трёх стратегий
// поле «замысел» значит разное: у «Копии» — что сохранить и как заменить
// товар (модель видит ролик сама), у «Дуэта» — реплика, которую ведущий
// произнесёт вслух за деньги, у «Создания» — полная концепция нового ролика.
const ROUTE_BRIEF_LIMITS = Object.freeze({
  copy_video: 800,
  avatar_video: 420,
});

function formatCopyRecommendation(recommendation, productName, avoid, shots) {
  const keep = [clean(recommendation.visual_direction, 600), ...shots.slice(0, 4)]
    .filter(Boolean)
    .join("\n");
  const sections = [
    ["СОХРАНИТЬ", keep],
    [
      "ЗАМЕНИТЬ",
      `Исходный товар — на «${productName}» с выбранных фото: форма, материал, цвет, упаковка и логотип без изменений.`,
    ],
    ["ДЕРЖАТЬ В КАДРЕ", clean(recommendation.key_message, 400)],
    ["НЕ ОБЕЩАТЬ", avoid.join(" · ")],
  ].filter(([, value]) => value);
  return compactResearchRecommendationSections(sections, ROUTE_BRIEF_LIMITS.copy_video);
}

function formatDuetRecommendation(recommendation) {
  // Только то, что ведущий скажет: без заголовков секций и служебных слов —
  // весь текст уходит в речь. Предел по длительности ролика подскажет панель.
  const script = clean(recommendation.spoken_script, 1800);
  const speech = script || [
    clean(recommendation.hook, 400),
    clean(recommendation.key_message, 500),
    clean(recommendation.cta, 300),
  ].filter(Boolean).join(" ");
  return truncateBrief(speech, ROUTE_BRIEF_LIMITS.avatar_video);
}

export function formatResearchRecommendation(item, context = {}) {
  const envelope = object(item);
  const recommendation = object(envelope.recommendation || envelope);
  const productName = clean(context.productName || context.product_name, 260)
    || clean(envelope.source_product_name, 260)
    || "товар";
  const audience = asList(recommendation.target_audience, 4);
  const proof = asList(recommendation.proof_points, 6);
  const avoid = asList(recommendation.avoid_claims, 6);
  const shots = shotLines(recommendation.shot_list);
  const route = clean(context.route, 40);
  if (route === "copy_video") {
    return formatCopyRecommendation(recommendation, productName, avoid, shots);
  }
  if (route === "avatar_video") return formatDuetRecommendation(recommendation);
  const sections = [
    ["ТОВАР", productName],
    ["КОНЦЕПЦИЯ", clean(recommendation.title, 260)],
    ["ХУК", clean(recommendation.hook, 700)],
    ["КЛЮЧЕВОЕ СООБЩЕНИЕ", clean(recommendation.key_message, 900)],
    ["АУДИТОРИЯ", audience.join(" · ")],
    ["РЕПЛИКА / СЮЖЕТ", clean(recommendation.spoken_script, 1800)],
    ["КАДРЫ", shots.join("\n")],
    ["ВИЗУАЛ", clean(recommendation.visual_direction, 1000)],
    ["CTA", clean(recommendation.cta, 700)],
    ["ДОКАЗАТЕЛЬСТВА", proof.join(" · ")],
    ["НЕ ОБЕЩАТЬ / УЧЕСТЬ", avoid.join(" · ")],
  ].filter(([, value]) => value);
  return compactResearchRecommendationSections(sections);
}

function firstClean(values, limit = 4000) {
  for (const value of values) {
    const normalized = clean(value, limit);
    if (normalized) return normalized;
  }
  return "";
}

function firstBrief(values) {
  for (const value of values) {
    const normalized = String(value ?? "")
      .replace(/\r\n?/gu, "\n")
      .trim();
    if (normalized) return truncateBrief(normalized);
  }
  return "";
}

function normalizedMode(value) {
  return GENERATION_MODE_ALIASES[clean(value, 80).toLowerCase()] || "";
}

function normalizedPlatform(value) {
  const platform = clean(value, 80).toLowerCase();
  return {
    instagram_reels: "instagram",
    reels: "instagram",
    youtube_shorts: "youtube",
    shorts: "youtube",
    vk_clips: "vk",
    "vk clips": "vk",
  }[platform] || platform;
}

function normalizedDuration(value, mode) {
  const duration = Number(value);
  const allowed = GENERATION_MODE_DURATIONS[mode];
  if (allowed && Number.isInteger(duration) && allowed.has(duration)) {
    return duration;
  }
  if (mode === "real_gen4") return 5;
  if (mode === "real_seedance") return 8;
  return null;
}

function normalizedFormat(value, mode) {
  if (mode === "real_seedance") return "9:16";
  if (mode === "real_photo") return "1:1";
  const format = clean(value, 40).toLowerCase().replace(/\s+/gu, "");
  const normalized = {
    "9x16": "9:16",
    "9/16": "9:16",
    vertical: "9:16",
    portrait: "9:16",
    "1x1": "1:1",
    "1/1": "1:1",
    square: "1:1",
    "16x9": "16:9",
    "16/9": "16:9",
    horizontal: "16:9",
    landscape: "16:9",
  }[format] || format;
  return GENERATION_FORMATS.has(normalized) ? normalized : "";
}

function withValue(target, key, value) {
  if (value !== "" && value !== null && value !== undefined) target[key] = value;
}

/**
 * Convert either the new envelope.preset contract or the historical
 * recommendation object into the small, editable subset owned by this bridge.
 * Financial authority, media and placement controls are intentionally absent.
 */
export function normalizeResearchRecommendationPreset(item, context = {}) {
  const envelope = object(item);
  const recommendation = object(envelope.recommendation || envelope);
  const declaredPreset = object(envelope.preset);
  const source = { ...recommendation, ...declaredPreset };
  const category = firstClean([
    source.product_category,
    source.category,
    envelope.product_category,
  ], 40).toLowerCase();
  const platform = normalizedPlatform(firstClean([
    source.platform,
    envelope.platform,
  ], 40));
  const mode = normalizedMode(firstClean([
    source.mode,
    source.generation_mode,
    source.recommended_generation_mode,
    source.model,
  ], 80));
  const duration = normalizedDuration(
    source.duration_seconds ?? source.duration,
    mode,
  );
  const format = normalizedFormat(firstClean([
    source.format,
    source.aspect_ratio,
    source.aspectRatio,
  ], 40), mode);
  const declaredBrief = firstBrief([
    source.brief,
    source.editable_brief,
  ]);
  const brief = declaredBrief || formatResearchRecommendation(envelope, context);
  const preset = {};
  if (PRODUCT_CATEGORIES.has(category)) withValue(preset, "product_category", category);
  if (GENERATION_PLATFORMS.has(platform)) withValue(preset, "platform", platform);
  withValue(preset, "mode", mode);
  withValue(preset, "duration_seconds", duration);
  withValue(preset, "format", format);
  withValue(preset, "brief", brief);
  return preset;
}

export function isExactResearchRecommendation(item) {
  const envelope = object(item);
  return ["exact_sku", "exact_product", "selected_product_advisory"].includes(
    clean(envelope.scope_match, 40).toLowerCase(),
  );
}

function recommendationSelectionId(item) {
  const envelope = object(item);
  return firstClean([
    envelope.selection_id,
    envelope.selectionId,
  ], 80);
}

function recommendationPosition(item) {
  const envelope = object(item);
  const recommendation = object(envelope.recommendation);
  const preset = object(envelope.preset);
  const value = Number(
    envelope.recommendation_position
      ?? preset.position
      ?? recommendation.position
      ?? envelope.position,
  );
  return Number.isInteger(value) && value >= 1 && value <= 3 ? value : null;
}

function normalizedTouchedFields(state = {}) {
  const values = Array.isArray(state.touchedFields) ? state.touchedFields : [];
  const touched = new Set(values.filter((field) => PRESET_FIELDS.includes(field)));
  if (state.touched === true) touched.add("brief");
  return touched;
}

export function resolveResearchPresetAppliedFields({
  preset = {},
  touchedFields = [],
  exact = false,
  explicit = false,
  optedOut = false,
} = {}) {
  if ((!explicit && optedOut) || (!explicit && exact !== true)) return [];
  const touched = new Set(
    Array.from(touchedFields || []).filter((field) => PRESET_FIELDS.includes(field)),
  );
  return PRESET_FIELDS.filter((field) => (
    Object.hasOwn(object(preset), field)
    && (explicit || !touched.has(field))
  ));
}

function formControl(form, presetField) {
  const name = PRESET_FORM_FIELDS[presetField];
  return name ? form?.elements?.[name] || form?.querySelector?.(`[name="${name}"]`) : null;
}

function controlValue(control) {
  return String(control?.value ?? "");
}

function controlAcceptsValue(control, value) {
  if (!control) return false;
  const options = Array.from(control.options || []);
  return !options.length || options.some((option) => String(option.value) === String(value));
}

function browserEvent(type) {
  if (typeof globalThis.Event === "function") {
    return new globalThis.Event(type, { bubbles: true });
  }
  return { type, bubbles: true };
}

function browserCustomEvent(type, detail) {
  if (typeof globalThis.CustomEvent === "function") {
    return new globalThis.CustomEvent(type, { bubbles: true, detail });
  }
  const event = browserEvent(type);
  try {
    Object.defineProperty(event, "detail", { configurable: true, value: detail });
  } catch {
    event.detail = detail;
  }
  return event;
}

function dispatchPresetProvenance(form, type, detail) {
  if (typeof form?.dispatchEvent !== "function") return;
  form.dispatchEvent(browserCustomEvent(type, detail));
}

export function verifiedResearchRecommendationProvenanceDetail(
  form,
  envelope,
  state = {},
  context = {},
) {
  const selectionId = normalizedUuid(recommendationSelectionId(envelope));
  const position = recommendationPosition(envelope);
  const projectId = normalizedUuid(envelope?.project_id);
  const contextProjectId = normalizedUuid(context?.projectId);
  const productId = normalizedUuid(envelope?.product_id);
  const selectedProductId = normalizedUuid(form?.dataset?.identityProductId);
  const storedProductId = normalizedUuid(
    form?.dataset?.researchRecommendationProductId,
  );
  const category = clean(envelope?.product_category, 40).toLowerCase();
  const currentCategory = clean(
    formControl(form, "product_category")?.value,
    40,
  ).toLowerCase();
  const providerVersion = String(
    envelope?.provider_prompt_fragment_version || "",
  );
  const providerFragment = String(envelope?.provider_prompt_fragment || "");
  const providerHash = String(envelope?.provider_prompt_fragment_hash || "");
  const appliedFields = [...new Set(
    (Array.isArray(state?.appliedFields) ? state.appliedFields : [])
      .filter((field) => PRESET_FIELDS.includes(field)),
  )];
  const verifiedTarget = {
    selectionId: normalizedUuid(
      form?.dataset?.researchRecommendationVerificationSelectionId,
    ),
    recommendationPosition: Number(
      form?.dataset?.researchRecommendationVerificationPosition,
    ),
  };
  if (
    form?.dataset?.researchRecommendationLineage !== "active"
    || form.dataset.researchRecommendationVerificationRequired !== "true"
    || form.dataset.researchRecommendationVerificationState !== "verified"
    || recommendationTargetKey(verifiedTarget) !== recommendationTargetKey({
      selectionId,
      recommendationPosition: position,
    })
    || !projectId
    || projectId !== contextProjectId
    || !productId
    || productId !== selectedProductId
    || productId !== storedProductId
    || !PRODUCT_CATEGORIES.has(category)
    || category !== currentCategory
    || !appliedFields.length
    || providerVersion !== "ai-research-provider-fragment-v1"
    || !providerFragment
    || Array.from(providerFragment).length > 240
    || providerFragment.trim() !== providerFragment
    || !providerFragment.startsWith("AIResearchSelection/v1 ")
    || /[\u0000-\u001f\u007f]/u.test(providerFragment)
    || !/^[0-9a-f]{64}$/u.test(providerHash)
  ) return null;
  return {
    verification_only: true,
    authoritative_project_id: projectId,
    selection_id: selectionId,
    recommendation_position: position,
    authoritative_product_id: productId,
    authoritative_product_category: category,
    preset: normalizeResearchRecommendationPreset(envelope, context),
    applied_fields: appliedFields,
    provider_prompt_fragment_version: providerVersion,
    provider_prompt_fragment: providerFragment,
    provider_prompt_fragment_hash: providerHash,
  };
}

export function dispatchVerifiedResearchRecommendationProvenance(
  form,
  envelope,
  state = {},
  context = {},
) {
  const detail = verifiedResearchRecommendationProvenanceDetail(
    form,
    envelope,
    state,
    context,
  );
  if (!detail) return false;
  dispatchPresetProvenance(form, PRESET_EVENT, detail);
  return true;
}

/**
 * Apply only the governed editable preset fields. This function deliberately
 * has no references to campaign, media, destination, quantity or spend fields.
 */
export function applyResearchRecommendationPresetToForm(
  form,
  item,
  {
    context = {},
    touchedFields = [],
    exact = isExactResearchRecommendation(item),
    explicit = false,
    optedOut = false,
    dispatch = true,
  } = {},
) {
  const preset = normalizeResearchRecommendationPreset(item, context);
  const candidateFields = resolveResearchPresetAppliedFields({
    preset,
    touchedFields,
    exact,
    explicit,
    optedOut,
  });
  const selectionId = recommendationSelectionId(item);
  const position = recommendationPosition(item);
  const appliedFields = [];
  const previousValues = {};

  for (const field of candidateFields) {
    const control = formControl(form, field);
    const value = preset[field];
    if (!control || !controlAcceptsValue(control, value)) continue;
    const previous = controlValue(control);
    previousValues[field] = previous;
    control.value = String(value);
    if (control.dataset) {
      control.dataset.researchRecommendationApplied = selectionId || "approved-research";
      control.dataset.researchRecommendationField = field;
      delete control.dataset.researchRecommendationEdited;
    }
    appliedFields.push(field);
    if (dispatch && previous !== String(value) && typeof control.dispatchEvent === "function") {
      if (field === "brief") control.dispatchEvent(browserEvent("input"));
      control.dispatchEvent(browserEvent("change"));
    }
  }

  const detail = {
    selection_id: selectionId || null,
    recommendation_position: position,
    preset,
    applied_fields: [...appliedFields],
  };
  if (form?.dataset && appliedFields.length) {
    form.dataset.researchRecommendationLineage = "active";
    form.dataset.researchRecommendationSelectionId = selectionId;
    form.dataset.researchRecommendationPosition = position === null ? "" : String(position);
    form.dataset.researchRecommendationAppliedFields = appliedFields.join(",");
  }
  if (dispatch && appliedFields.length) {
    dispatchPresetProvenance(form, PRESET_EVENT, detail);
  }
  return {
    preset,
    appliedFields,
    previousValues,
    selectionId,
    recommendationPosition: position,
    detail,
  };
}

/** Restore lineage on a freshly rendered form without writing any form value. */
export function restoreResearchRecommendationPresetLineage(
  form,
  item,
  state = {},
  { context = {}, dispatch = true } = {},
) {
  if (state.optedOut === true) return { restored: false, detail: null };
  const preset = normalizeResearchRecommendationPreset(item, context);
  const envelopeSelectionId = recommendationSelectionId(item);
  const stateSelectionId = clean(state.selectionId, 80);
  const envelopePosition = recommendationPosition(item);
  const statePosition = Number(state.recommendationPosition);
  if (
    !stateSelectionId
    || stateSelectionId !== envelopeSelectionId
    || !Number.isInteger(statePosition)
    || statePosition < 1
    || statePosition > 3
    || envelopePosition !== statePosition
  ) {
    return { restored: false, detail: null };
  }
  const appliedFields = (Array.isArray(state.appliedFields) ? state.appliedFields : [])
    .filter((field) => (
      PRESET_FIELDS.includes(field)
      && Object.hasOwn(preset, field)
      && Boolean(formControl(form, field))
    ));
  if (!appliedFields.length) return { restored: false, detail: null };
  const touched = normalizedTouchedFields(state);
  appliedFields.forEach((field) => {
    const control = formControl(form, field);
    if (!control?.dataset) return;
    control.dataset.researchRecommendationApplied = stateSelectionId;
    control.dataset.researchRecommendationField = field;
    if (touched.has(field)) control.dataset.researchRecommendationEdited = "true";
  });
  const signature = appliedFields.join(",");
  const alreadyRestored = Boolean(
    form?.dataset?.researchRecommendationLineage === "active"
    && form.dataset.researchRecommendationSelectionId === stateSelectionId
    && form.dataset.researchRecommendationPosition === String(statePosition)
    && form.dataset.researchRecommendationAppliedFields === signature,
  );
  if (form?.dataset) {
    form.dataset.researchRecommendationLineage = "active";
    form.dataset.researchRecommendationSelectionId = stateSelectionId;
    form.dataset.researchRecommendationPosition = String(statePosition);
    form.dataset.researchRecommendationAppliedFields = signature;
  }
  const detail = {
    selection_id: stateSelectionId,
    recommendation_position: statePosition,
    preset,
    applied_fields: [...appliedFields],
  };
  if (dispatch && !alreadyRestored) {
    dispatchPresetProvenance(form, PRESET_EVENT, detail);
  }
  return { restored: true, dispatched: dispatch && !alreadyRestored, detail };
}

export function optOutResearchRecommendationForForm(
  form,
  item,
  {
    context = {},
    dispatch = true,
    state = null,
    forceRollback = false,
  } = {},
) {
  const preset = normalizeResearchRecommendationPreset(item, context);
  const selectionId = recommendationSelectionId(item);
  const position = recommendationPosition(item);
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    PRESET_FIELDS.forEach((field) => {
      const control = formControl(form, field);
      if (!control?.dataset) return;
      delete control.dataset.researchRecommendationApplied;
      delete control.dataset.researchRecommendationField;
    });
    if (form?.dataset) {
      delete form.dataset.researchRecommendationLineage;
      delete form.dataset.researchRecommendationSelectionId;
      delete form.dataset.researchRecommendationPosition;
      delete form.dataset.researchRecommendationAppliedFields;
    }
    const legacyDetail = {
      selection_id: selectionId || null,
      recommendation_position: position,
      preset,
      applied_fields: [],
      opted_out: true,
    };
    if (dispatch) {
      dispatchPresetProvenance(form, PRESET_OPT_OUT_EVENT, legacyDetail);
    }
    return legacyDetail;
  }

  const applied = (Array.isArray(state.appliedFields)
    ? state.appliedFields
    : [])
    .filter((field) => PRESET_FIELDS.includes(field));
  const touched = normalizedTouchedFields(state);
  const previousValues = object(state.previousValues);
  const lastAppliedValues = object(state.lastAppliedValues);
  const rolledBackFields = [];
  const retainedFields = [];

  applied.forEach((field) => {
    const control = formControl(form, field);
    if (!control) return;
    const current = controlValue(control);
    const hasRollbackValue = Object.hasOwn(previousValues, field);
    const untouchedAutoValue = hasRollbackValue
      && Object.hasOwn(lastAppliedValues, field)
      && (
        forceRollback
        || (!touched.has(field) && current === String(lastAppliedValues[field]))
      );
    if (untouchedAutoValue && controlAcceptsValue(control, previousValues[field])) {
      const restored = String(previousValues[field]);
      control.value = restored;
      if (control.dataset) {
        delete control.dataset.researchRecommendationApplied;
        delete control.dataset.researchRecommendationField;
        delete control.dataset.researchRecommendationEdited;
      }
      rolledBackFields.push(field);
      if (dispatch && current !== restored && typeof control.dispatchEvent === "function") {
        if (field === "brief") control.dispatchEvent(browserEvent("input"));
        control.dispatchEvent(browserEvent("change"));
      }
    } else {
      retainedFields.push(field);
      if (control.dataset) {
        control.dataset.researchRecommendationApplied = selectionId;
        control.dataset.researchRecommendationField = field;
        control.dataset.researchRecommendationEdited = "true";
      }
    }
  });

  const lineageRetained = retainedFields.length > 0;
  if (form?.dataset) {
    if (lineageRetained) {
      form.dataset.researchRecommendationLineage = "active";
      form.dataset.researchRecommendationSelectionId = selectionId;
      form.dataset.researchRecommendationPosition = String(position || "");
      form.dataset.researchRecommendationAppliedFields = retainedFields.join(",");
      form.dataset.researchRecommendationAutoApplyDisabled = "true";
    } else {
      delete form.dataset.researchRecommendationLineage;
      delete form.dataset.researchRecommendationSelectionId;
      delete form.dataset.researchRecommendationPosition;
      delete form.dataset.researchRecommendationAppliedFields;
      delete form.dataset.researchRecommendationAutoApplyDisabled;
    }
  }
  const detail = {
    selection_id: selectionId || null,
    recommendation_position: position,
    preset,
    applied_fields: [...retainedFields],
    rolled_back_fields: [...rolledBackFields],
    retained_fields: [...retainedFields],
    opted_out: !lineageRetained,
    auto_apply_disabled: lineageRetained,
    lineage_retained: lineageRetained,
  };
  if (dispatch) dispatchPresetProvenance(form, PRESET_OPT_OUT_EVENT, detail);
  return detail;
}

export function shouldAutoApplyResearchRecommendation() {
  // Kept as a compatibility export for older callers. Selection is always a
  // human action now, regardless of ranking, exact-product scope or empty form.
  return false;
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function projectId() {
  return clean(routeParams().get("project_id"), 80).toLowerCase();
}

function formContext(form) {
  const read = (name) => String(form.elements?.[name]?.value || "").trim();
  const routeTarget = routeRecommendationTarget();
  const datasetSelectionId = normalizedUuid(
    form?.dataset?.generationAiResearchWorkingSelectionId
      || form?.dataset?.researchRecommendationSelectionId,
  );
  const datasetPosition = Number(
    form?.dataset?.generationAiResearchWorkingPosition
      || form?.dataset?.researchRecommendationPosition,
  );
  return {
    projectId: projectId(),
    productId: normalizedUuid(form?.dataset?.identityProductId),
    category: clean(read("product_category"), 40).toLowerCase(),
    productName: read("product_name"),
    sku: read("sku"),
    platform: clean(read("platform"), 40).toLowerCase(),
    // Маршрут панели: замысел для «Копии», речь для «Дуэта», концепция для
    // «Создания» собираются из одной рекомендации по-разному.
    route: intakeRoute(form),
    selectionId: routeTarget?.selectionId || datasetSelectionId,
    recommendationPosition: routeTarget?.recommendationPosition
      || ([1, 2, 3].includes(datasetPosition) ? datasetPosition : null),
  };
}

export function captureGenerationResearchWorkingDraftHydration(form) {
  const read = (name) => String(form?.elements?.[name]?.value ?? "");
  const revision = Number(form?.dataset?.generationUserEditRevision || 0);
  return JSON.stringify({
    revision: Number.isSafeInteger(revision) && revision >= 0 ? revision : 0,
    productName: read("product_name"),
    sku: read("sku"),
    productCategory: read("product_category"),
    platform: read("platform"),
    generationMode: read("generation_mode"),
    durationSeconds: read("duration_seconds"),
    format: read("format"),
    brief: read("brief"),
    mediaId: read("media_id"),
    primaryMediaId: read("primary_media_id"),
    identityProductId: String(form?.dataset?.identityProductId || ""),
    handoffSku: String(form?.dataset?.generationHandoffSku || ""),
    handoffProductName: String(
      form?.dataset?.generationHandoffProductName || "",
    ),
    workingSelectionId: String(
      form?.dataset?.generationAiResearchWorkingSelectionId || "",
    ),
    workingPosition: String(
      form?.dataset?.generationAiResearchWorkingPosition || "",
    ),
    verificationRequired: String(
      form?.dataset?.researchRecommendationVerificationRequired || "",
    ),
    verificationState: String(
      form?.dataset?.researchRecommendationVerificationState || "",
    ),
    verificationSelectionId: String(
      form?.dataset?.researchRecommendationVerificationSelectionId || "",
    ),
    verificationPosition: String(
      form?.dataset?.researchRecommendationVerificationPosition || "",
    ),
    verificationFailure: String(
      form?.dataset?.researchRecommendationVerificationFailure || "",
    ),
    explicitApplyTargetKey: String(runtime.explicitApplyTargetKey || ""),
  });
}

export function generationResearchWorkingDraftHydrationUnchanged(
  form,
  captured,
) {
  return Boolean(
    form
    && typeof captured === "string"
    && captureGenerationResearchWorkingDraftHydration(form) === captured,
  );
}

function stateKey(context) {
  return [
    STATE_PREFIX,
    context.projectId || "no-project",
    context.selectionId && context.recommendationPosition
      ? `selection:${context.selectionId}:${context.recommendationPosition}`
      : context.productId
      || clean(context.sku || context.productName, 120).toLowerCase()
      || "no-product",
  ].join(":");
}

function readState(context) {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(stateKey(context)) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeState(context, patch) {
  try {
    const previous = readState(context);
    window.sessionStorage.setItem(stateKey(context), JSON.stringify({
      ...previous,
      ...patch,
      updatedAt: Date.now(),
    }));
  } catch {
    // Session memory is optional; the textarea itself remains authoritative.
  }
}

function payloadWithOrganization(api, payload) {
  if (typeof api?.withOrganization === "function") return api.withOrganization(payload);
  if (api?.organizationId) return { organization_id: api.organizationId, ...payload };
  return payload;
}

async function getApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") throw new Error("api_runtime_unavailable");
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") throw new Error("api_runtime_unavailable");
  return api;
}

function authoritativeWorkingDraft(context = formContext(runtime.form), candidate = null) {
  const cached = cachedGenerationAiResearchWorkingDraft(context.projectId);
  const local = runtime.workingDraftProjectId === context.projectId
    ? runtime.workingDraft
    : null;
  const authoritative = preferAuthoritativeGenerationAiResearchWorkingDraft(
    local,
    cached,
    candidate,
  );
  if (authoritative) {
    runtime.workingDraft = authoritative;
    runtime.workingDraftProjectId = context.projectId;
    if (runtime.form?.dataset) {
      runtime.form.dataset.generationAiResearchWorkingRevision = String(
        authoritative.revision,
      );
    }
  }
  return authoritative;
}

function workingDraftRevision(context = formContext(runtime.form)) {
  const authoritative = authoritativeWorkingDraft(context);
  if (Number.isSafeInteger(Number(authoritative?.revision))) {
    return Number(authoritative.revision);
  }
  const datasetRevision = Number(
    runtime.form?.dataset?.generationAiResearchWorkingRevision,
  );
  return Number.isSafeInteger(datasetRevision) && datasetRevision >= 0
    ? datasetRevision
    : 0;
}

function workingDraftSaveState() {
  if (!runtime.form) return null;
  const context = formContext(runtime.form);
  const state = readState(context);
  const authoritative = authoritativeWorkingDraft(context);
  const selectionId = normalizedUuid(state.selectionId || context.selectionId);
  const position = Number(
    state.recommendationPosition || context.recommendationPosition,
  );
  const target = {
    selectionId,
    recommendationPosition: position,
  };
  if (
    Number(authoritative?.revision) > 0
    && authoritative?.draft === null
    && !tombstoneReplacementAuthorized(context, target)
  ) return null;
  const editableFields = generationAiResearchEditableFieldsFromForm(
    runtime.form,
  );
  const appliedFields = (Array.isArray(state.appliedFields)
    ? state.appliedFields
    : [])
    .filter((field) => PRESET_FIELDS.includes(field));
  if (
    !context.projectId
    || !selectionId
    || ![1, 2, 3].includes(position)
    || !editableFields
    || !appliedFields.length
  ) return null;
  const keepMap = (value) => Object.fromEntries(
    Object.entries(object(value))
      .filter(([field]) => PRESET_FIELDS.includes(field))
      .map(([field, fieldValue]) => [field, String(fieldValue ?? "").slice(0, 1200)]),
  );
  return {
    context,
    selectionId,
    recommendationPosition: position,
    editableFields,
    appliedFields,
    touchedFields: [...normalizedTouchedFields(state)],
    previousValues: keepMap(state.previousValues),
    lastAppliedValues: keepMap(state.lastAppliedValues),
    autoApplyDisabled: state.autoApplyDisabled === true,
  };
}

function workingDraftConflict(error) {
  return /generation_ai_research_working_draft_(?:revision_conflict|response_superseded)/u.test([
    error?.code,
    error?.serverCode,
    error?.message,
  ].filter(Boolean).join(" "));
}

function stopWorkingDraftConflictRetries() {
  runtime.workingDraftConflict = true;
  runtime.workingDraftSavePending = false;
  window.clearTimeout(runtime.workingDraftSaveTimer);
  runtime.workingDraftSaveTimer = 0;
  renderWorkingDraftRecovery("conflict");
}

function scheduleWorkingDraftHydrateRetry(form, context) {
  const attempt = runtime.workingDraftHydrateRetryCount;
  if (attempt >= WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS.length) {
    renderWorkingDraftRecovery("hydrate_failed");
    return;
  }
  runtime.workingDraftHydrateRetryCount = attempt + 1;
  window.clearTimeout(runtime.workingDraftHydrateRetryTimer);
  runtime.workingDraftHydrateRetryTimer = window.setTimeout(() => {
    runtime.workingDraftHydrateRetryTimer = 0;
    if (
      routePath() !== ROUTE
      || runtime.form !== form
      || !form.isConnected
      || formContext(form).projectId !== context.projectId
      || runtime.workingDraftAuthority !== "failed"
    ) return;
    // One-shot grant: mount() consumes the flag before restarting hydration,
    // so plain observer mutations never restart a settled failed read.
    runtime.workingDraftHydrateRetryDue = true;
    scheduleMount();
  }, WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS[attempt]);
}

function selectedVerifiedMediaProduct(form, expectedProductId) {
  const selectedMedia = Array.from(
    form?.querySelectorAll?.('input[name="media_id"]') || [],
  ).filter((input) => (
    input.checked
    && (
      !input.disabled
      || (
        form?.dataset?.busy === "true"
        && input.dataset?.wasDisabled === "false"
      )
    )
  ));
  if (!selectedMedia.length) {
    return { selected: false, valid: true, product: null };
  }
  const selectedPrimaryId = String(
    Array.from(
      form?.querySelectorAll?.('input[name="primary_media_id"]') || [],
    ).find((input) => (
      input.checked
      && (
        !input.disabled
        || (
          form?.dataset?.busy === "true"
          && input.dataset?.wasDisabled === "false"
        )
      )
    ))?.value
      || form?.dataset?.primaryGenerationMediaId
      || "",
  ).trim();
  const primary = selectedMedia.find((input) => (
    String(input.value || "").trim() === selectedPrimaryId
  )) || (selectedMedia.length === 1 ? selectedMedia[0] : null);
  const identity = (input) => ({
    productId: normalizedUuid(input?.dataset?.mediaProductId),
    sku: clean(input?.dataset?.mediaSku, 120),
    productName: clean(input?.dataset?.mediaProductName, 180),
    verified: input?.dataset?.mediaIdentityVerified === "true",
    rightsConfirmed: input?.dataset?.mediaRightsConfirmed === "true",
  });
  const primaryIdentity = identity(primary);
  const valid = Boolean(
    primary
    && primaryIdentity.verified
    && primaryIdentity.rightsConfirmed
    && primaryIdentity.productId === expectedProductId
    && primaryIdentity.sku
    && primaryIdentity.productName
    && selectedMedia.every((input) => {
      const candidate = identity(input);
      return candidate.verified
        && candidate.rightsConfirmed
        && candidate.productId === primaryIdentity.productId
        && candidate.sku === primaryIdentity.sku
        && candidate.productName === primaryIdentity.productName;
    }),
  );
  return {
    selected: true,
    valid,
    product: valid
      ? {
          sku: primaryIdentity.sku,
          productName: primaryIdentity.productName,
        }
      : null,
  };
}

export function resolveAuthoritativeRecommendationProductFields({
  recommendationSku = "",
  recommendationProductName = "",
  selectedMedia = null,
  currentSku = "",
  currentProductName = "",
} = {}) {
  const mediaSku = clean(selectedMedia?.sku, 120);
  const mediaProductName = clean(selectedMedia?.productName, 180);
  if (mediaSku && mediaProductName) {
    return {
      sku: mediaSku,
      productName: mediaProductName,
      source: "verified_media",
    };
  }
  const authoritativeSku = clean(recommendationSku, 120);
  const authoritativeProductName = clean(recommendationProductName, 180);
  const preservedSku = clean(currentSku, 120);
  const preservedProductName = clean(currentProductName, 180);
  if (authoritativeSku && authoritativeProductName) {
    return {
      sku: authoritativeSku,
      productName: authoritativeProductName,
      source: "recommendation",
    };
  }
  return {
    // Older selections can legitimately lack one display field. Never mix
    // that incomplete advisory identity with the human's exact product pair.
    sku: preservedSku,
    productName: preservedProductName,
    source: "preserved",
  };
}

export function recommendationProductIdentityMatches(form, envelope) {
  const source = object(envelope);
  const handoffProduct = resolveGenerationExpectedProductMatch({
    expectedSku: form?.dataset?.generationHandoffSku,
    expectedProductName: form?.dataset?.generationHandoffProductName,
    candidateSku: source.source_product_sku,
    candidateProductName: source.source_product_name,
  });
  if (!handoffProduct.ok) return false;
  const productId = normalizedUuid(source.product_id);
  const selectedMediaProductId = normalizedUuid(
    form?.dataset?.identityProductId,
  );
  if (!resolveGenerationAiResearchProductIdentity(
    productId,
    selectedMediaProductId,
  ).ok) {
    return false;
  }
  const selectedMedia = selectedVerifiedMediaProduct(form, productId);
  if (selectedMedia.selected && !selectedMedia.valid) return false;
  return true;
}

export function applyAuthoritativeRecommendationProduct(form, envelope) {
  if (!recommendationProductIdentityMatches(form, envelope)) return false;
  const source = object(envelope);
  const productId = normalizedUuid(source.product_id);
  const sku = form?.elements?.sku;
  const productName = form?.elements?.product_name;
  const selectedMedia = selectedVerifiedMediaProduct(form, productId);
  const values = resolveAuthoritativeRecommendationProductFields({
    recommendationSku: source.source_product_sku,
    recommendationProductName: source.source_product_name,
    selectedMedia: selectedMedia.product,
    currentSku: sku?.value,
    currentProductName: productName?.value,
  });
  if (sku) sku.value = values.sku;
  if (productName) productName.value = values.productName;
  form.dataset.researchRecommendationProductId = productId;
  const productCategory = clean(source.product_category, 40).toLowerCase();
  if (PRODUCT_CATEGORIES.has(productCategory)) {
    form.dataset.researchRecommendationProductCategory = productCategory;
  }
  return true;
}

function blockRecommendationProductMismatch(
  form,
  envelope,
  failure = "product_mismatch",
) {
  const selectionId = recommendationSelectionId(envelope);
  const position = recommendationPosition(envelope);
  if (form?.dataset) {
    form.dataset.researchRecommendationVerificationRequired = "true";
    form.dataset.researchRecommendationVerificationState = "failed";
    form.dataset.researchRecommendationVerificationFailure = failure;
    if (selectionId) {
      form.dataset.researchRecommendationVerificationSelectionId = selectionId;
    }
    if (position !== null) {
      form.dataset.researchRecommendationVerificationPosition = String(position);
    }
  }
  if (form?.elements?.real_spend_confirmation) {
    form.elements.real_spend_confirmation.checked = false;
  }
  setStatus(
    failure === "selected_media_product_unverified"
      ? "Общий черновик проекта не применён: сначала явно выберите проверенное медиа точного товара. Название, SKU, категория и замысел текущей формы не изменены."
      : "Выбранные медиа относятся к другому товару, чем рекомендация ИИ‑центра. Поля рекомендации не применены, техническое ТЗ и платный запуск заблокированы. Выберите проверенные медиа рекомендованного товара либо полностью перейдите в ручной режим.",
    "danger",
  );
}

export function quarantinePassiveWorkingDraft(
  form,
  envelope,
  failure = "product_mismatch",
) {
  if (!form?.dataset) return false;
  delete form.dataset.researchRecommendationVerificationRequired;
  delete form.dataset.researchRecommendationVerificationState;
  delete form.dataset.researchRecommendationVerificationFailure;
  delete form.dataset.researchRecommendationVerificationSelectionId;
  delete form.dataset.researchRecommendationVerificationPosition;
  delete form.dataset.researchRecommendationLineage;
  delete form.dataset.researchRecommendationSelectionId;
  delete form.dataset.researchRecommendationPosition;
  delete form.dataset.researchRecommendationAppliedFields;
  delete form.dataset.researchRecommendationProductId;
  delete form.dataset.researchRecommendationProductCategory;
  delete form.dataset.researchRecommendationProviderFragmentStatus;
  delete form.dataset.researchRecommendationProviderFragmentVersion;
  delete form.dataset.researchRecommendationProviderFragmentHash;
  delete form.dataset.generationAiResearchWorkingSelectionId;
  delete form.dataset.generationAiResearchWorkingPosition;
  form.querySelectorAll?.("[data-research-recommendation-applied]").forEach(
    (control) => {
      delete control.dataset.researchRecommendationApplied;
      delete control.dataset.researchRecommendationField;
      delete control.dataset.researchRecommendationEdited;
    },
  );
  const context = formContext(form);
  const staleTargetContext = {
    ...context,
    selectionId: recommendationSelectionId(envelope),
    recommendationPosition: recommendationPosition(envelope),
  };
  try {
    window.sessionStorage.removeItem(stateKey(staleTargetContext));
  } catch {
    // Session memory is optional; the server draft stays available for its own product.
  }
  writeState(context, {
    selectionId: "",
    recommendationPosition: null,
    appliedFields: [],
    previousValues: {},
    lastAppliedValues: {},
    optedOut: true,
    explicit: false,
  });
  runtime.explicitApplyTargetKey = "";
  runtime.activeIndex = -1;
  runtime.root?.setAttribute("data-manual-mode", "true");
  runtime.root?.setAttribute("data-passive-draft-quarantined", failure);
  const previousProduct = clean(
    envelope?.source_product_name || envelope?.recommendation?.source_product_name,
    160,
  ) || "другого товара";
  const currentProduct = clean(form.elements?.product_name?.value, 160)
    || "текущего товара";
  setStatus(
    `В проекте сохранён ИИ‑черновик «${previousProduct}», но сейчас выбран «${currentProduct}». Старый вариант изолирован: он не изменил товар, категорию или замысел и не блокирует ручное ТЗ. Для нового товара выберите категорию и, при необходимости, новый вариант ИИ.`,
    "neutral",
  );
  return true;
}

async function saveWorkingDraft() {
  if (runtime.workingDraftSaving || runtime.workingDraftHydrating) {
    runtime.workingDraftSavePending = true;
    return;
  }
  const candidate = workingDraftSaveState();
  if (!candidate) return;
  runtime.workingDraftSavePending = false;
  runtime.workingDraftSaving = true;
  try {
    const api = await getApi();
    const saved = await saveGenerationAiResearchWorkingDraft(
      api,
      candidate.context.projectId,
      candidate,
      workingDraftRevision(candidate.context),
    );
    clearTombstoneReplacementAuthorization(
      candidate.context,
      {
        selectionId: candidate.selectionId,
        recommendationPosition: candidate.recommendationPosition,
      },
    );
    if (
      routePath() !== ROUTE
      || formContext(runtime.form).projectId !== candidate.context.projectId
    ) return;
    runtime.workingDraft = saved;
    runtime.workingDraftProjectId = candidate.context.projectId;
    runtime.workingDraftConflict = false;
    if (runtime.form?.dataset) {
      runtime.form.dataset.generationAiResearchWorkingRevision = String(
        saved.revision,
      );
    }
    setStatus(
      "Общий творческий черновик сохранён в проекте. Другой участник увидит выбранный вариант и ваши правки; оплата, кампания и медиа не сохранялись.",
      "ready",
    );
  } catch (error) {
    clearTombstoneReplacementAuthorization(
      candidate.context,
      {
        selectionId: candidate.selectionId,
        recommendationPosition: candidate.recommendationPosition,
      },
    );
    console.warn("Generation AI research working draft save failed", error);
    if (workingDraftConflict(error)) {
      stopWorkingDraftConflictRetries();
      setStatus(
        "Другой участник уже обновил общий черновик. Ваши поля не перезаписаны: обновите страницу и решите, какую версию оставить.",
        "danger",
      );
    } else {
      setStatus(
        "Сервер пока не подтвердил общий черновик. Поля этой вкладки сохранены локально; платный запуск не выполнялся.",
        "danger",
      );
    }
  } finally {
    runtime.workingDraftSaving = false;
    if (runtime.workingDraftClearPending) {
      runtime.workingDraftClearPending = false;
      void clearWorkingDraft();
    } else if (runtime.workingDraftSavePending) {
      scheduleWorkingDraftSave();
    }
  }
}

function scheduleWorkingDraftSave() {
  if (runtime.workingDraftConflict) {
    runtime.workingDraftSavePending = false;
    window.clearTimeout(runtime.workingDraftSaveTimer);
    runtime.workingDraftSaveTimer = 0;
    // The dropped sync stays visible: every later edit re-asserts the banner
    // with the explicit resolution actions instead of being swallowed.
    renderWorkingDraftRecovery("conflict");
    return;
  }
  runtime.workingDraftSavePending = true;
  window.clearTimeout(runtime.workingDraftSaveTimer);
  runtime.workingDraftSaveTimer = window.setTimeout(() => {
    runtime.workingDraftSaveTimer = 0;
    void saveWorkingDraft();
  }, 260);
}

async function clearWorkingDraft() {
  if (!runtime.form) return;
  if (runtime.workingDraftSaving) {
    runtime.workingDraftClearPending = true;
    return;
  }
  const originForm = runtime.form;
  const context = formContext(originForm);
  if (!context.projectId) return;
  window.clearTimeout(runtime.workingDraftSaveTimer);
  runtime.workingDraftSaveTimer = 0;
  runtime.workingDraftSavePending = false;
  runtime.workingDraftClearPending = false;
  runtime.workingDraftSaving = true;
  try {
    const api = await getApi();
    const cleared = await clearGenerationAiResearchWorkingDraft(
      api,
      context.projectId,
      workingDraftRevision(context),
    );
    if (
      routePath() !== ROUTE
      || runtime.form !== originForm
      || !originForm.isConnected
      || formContext(originForm).projectId !== context.projectId
    ) return;
    runtime.workingDraft = cleared;
    runtime.workingDraftProjectId = context.projectId;
    runtime.workingDraftConflict = false;
    if (runtime.form?.dataset) {
      runtime.form.dataset.generationAiResearchWorkingRevision = String(
        cleared.revision,
      );
      delete runtime.form.dataset.generationAiResearchWorkingSelectionId;
      delete runtime.form.dataset.generationAiResearchWorkingPosition;
    }
  } catch (error) {
    console.warn("Generation AI research working draft clear failed", error);
    if (workingDraftConflict(error)) stopWorkingDraftConflictRetries();
    if (
      routePath() === ROUTE
      && runtime.form === originForm
      && originForm.isConnected
      && formContext(originForm).projectId === context.projectId
    ) {
      setStatus(
        workingDraftConflict(error)
          ? "Другой участник уже изменил общий черновик. Ручные поля этой вкладки не перезаписаны; обновите страницу перед повторным отключением."
          : "Ручные поля оставлены в форме, но сервер пока не подтвердил снятие общего выбора.",
        "danger",
      );
    }
  } finally {
    runtime.workingDraftSaving = false;
    if (runtime.workingDraftClearPending) {
      runtime.workingDraftClearPending = false;
      void clearWorkingDraft();
    } else if (runtime.workingDraftSavePending) {
      scheduleWorkingDraftSave();
    }
  }
}

async function resolveWorkingDraftConflict(strategy /* "theirs" | "mine" */) {
  if (
    !runtime.form
    || runtime.workingDraftSaving
    || runtime.workingDraftHydrating
  ) return;
  const form = runtime.form;
  const context = formContext(form);
  if (!context.projectId) return;
  const recovery = workingDraftRecoveryContainer();
  recovery?.querySelectorAll?.("button")?.forEach?.((button) => {
    button.disabled = true;
  });
  try {
    const api = await getApi();
    const fresh = await readGenerationAiResearchWorkingDraft(
      api,
      context.projectId,
      { force: true },
    );
    if (
      routePath() !== ROUTE
      || runtime.form !== form
      || !form.isConnected
      || formContext(form).projectId !== context.projectId
    ) return;
    runtime.workingDraft = fresh;
    runtime.workingDraftProjectId = context.projectId;
    form.dataset.generationAiResearchWorkingRevision = String(fresh.revision);
    const freshTombstone = Number(fresh.revision) > 0 && fresh.draft === null;
    if (strategy === "mine" && freshTombstone) {
      // Другой участник явно очистил общий черновик: не пересоздаём его
      // молча поверх — остаётся только явное принятие его версии.
      renderWorkingDraftRecovery("conflict");
      setStatus(
        "Другой участник очистил общий черновик проекта. Ваши правки не записаны поверх: можно только принять его версию.",
        "danger",
      );
      return;
    }
    runtime.workingDraftConflict = false;
    if (strategy === "theirs") {
      if (fresh.draft) {
        applySharedWorkingDraft(form, fresh);
      } else {
        delete form.dataset.generationAiResearchWorkingSelectionId;
        delete form.dataset.generationAiResearchWorkingPosition;
        runtime.root?.setAttribute("data-manual-mode", "true");
        runtime.response = { recommendations: [] };
        renderRecommendationPanel();
      }
      setStatus(
        "Применена версия другого участника. Локальные правки этой вкладки заменены его версией.",
        "ready",
      );
    } else {
      scheduleWorkingDraftSave();
      setStatus(
        "Ваши правки будут записаны поверх новой версии общего черновика.",
        "ready",
      );
    }
    renderWorkingDraftRecovery(null);
  } catch (error) {
    console.warn(
      "Generation AI research working draft conflict resolution failed",
      error,
    );
    renderWorkingDraftRecovery("conflict");
    setStatus(
      "Не удалось получить свежую версию общего черновика — повторите.",
      "danger",
    );
  }
}

function applySharedWorkingDraft(form, shared) {
  shared = authoritativeWorkingDraft(formContext(form), shared);
  const draft = shared?.draft;
  if (!draft?.recommendation || !draft?.editableFields) return false;
  const routeTarget = routeRecommendationTarget();
  if (
    routeTarget
    && (
      routeTarget.selectionId !== draft.selectionId
      || routeTarget.recommendationPosition !== draft.recommendationPosition
    )
  ) return false;
  const passiveProductIdentity = resolveGenerationAiResearchProductIdentity(
    normalizedUuid(draft.recommendation.product_id),
    normalizedUuid(form?.dataset?.identityProductId),
    { requireSelectedMedia: true },
  );
  const passiveHandoffProduct = resolveGenerationExpectedProductMatch({
    expectedSku: form?.dataset?.generationHandoffSku,
    expectedProductName: form?.dataset?.generationHandoffProductName,
    candidateSku: draft.recommendation.source_product_sku,
    candidateProductName: draft.recommendation.source_product_name,
  });
  const passiveProductFailure = !passiveHandoffProduct.ok
    ? passiveHandoffProduct.code
    : !passiveProductIdentity.ok
      ? passiveProductIdentity.code
      : "";
  if (passiveProductFailure) {
    if (routeTarget) {
      blockRecommendationProductMismatch(
        form,
        draft.recommendation,
        passiveProductFailure,
      );
    } else {
      quarantinePassiveWorkingDraft(
        form,
        draft.recommendation,
        passiveProductFailure,
      );
    }
    return false;
  }
  if (!applyAuthoritativeRecommendationProduct(form, draft.recommendation)) {
    blockRecommendationProductMismatch(form, draft.recommendation);
    return false;
  }
  runtime.root?.removeAttribute("data-passive-draft-quarantined");
  const values = draft.editableFields;
  const controls = {
    product_category: formControl(form, "product_category"),
    platform: formControl(form, "platform"),
    mode: formControl(form, "mode"),
    duration_seconds: formControl(form, "duration_seconds"),
    format: formControl(form, "format"),
    brief: formControl(form, "brief"),
  };
  runtime.applying = true;
  if (controls.mode && controlAcceptsValue(controls.mode, values.generation_mode)) {
    controls.mode.value = values.generation_mode;
    controls.mode.dispatchEvent?.(browserEvent("change"));
  }
  const editable = {
    product_category: values.product_category,
    platform: values.platform,
    duration_seconds: values.duration_seconds,
    format: values.format,
    brief: values.brief,
  };
  Object.entries(editable).forEach(([field, value]) => {
    const control = controls[field];
    if (value === null || !control || !controlAcceptsValue(control, value)) return;
    const previous = controlValue(control);
    control.value = String(value);
    if (previous !== String(value)) {
      if (field === "brief") control.dispatchEvent?.(browserEvent("input"));
      control.dispatchEvent?.(browserEvent("change"));
    }
  });
  runtime.applying = false;
  form.dataset.generationAiResearchWorkingRevision = String(shared.revision);
  form.dataset.generationAiResearchWorkingSelectionId = draft.selectionId;
  form.dataset.generationAiResearchWorkingPosition = String(
    draft.recommendationPosition,
  );
  const context = formContext(form);
  writeState(context, {
    selectionId: draft.selectionId,
    recommendationPosition: draft.recommendationPosition,
    appliedFields: [...draft.appliedFields],
    touchedFields: [...draft.touchedFields],
    touched: draft.touchedFields.includes("brief"),
    previousValues: { ...draft.previousValues },
    lastAppliedValues: { ...draft.lastAppliedValues },
    optedOut: false,
    autoApplyDisabled: draft.autoApplyDisabled === true,
    explicit: true,
  });
  restoreResearchRecommendationPresetLineage(
    form,
    draft.recommendation,
    readState(context),
    { context },
  );
  if (draft.autoApplyDisabled) {
    runtime.root?.setAttribute("data-auto-apply-disabled", "true");
  }
  if (routeTarget) consumeRouteRecommendationTarget(routeTarget);
  return true;
}

async function hydrateSharedWorkingDraft(form, context) {
  if (!context.projectId || routePath() !== ROUTE) return;
  if (runtime.workingDraftHydrating) {
    runtime.workingDraftHydratePending = { form, context };
    return;
  }
  if (runtime.workingDraftAuthorityProjectId !== context.projectId) {
    setWorkingDraftAuthority(context.projectId, "unknown");
  }
  const hydrationSnapshot = captureGenerationResearchWorkingDraftHydration(form);
  runtime.workingDraftHydrating = true;
  setStatus("Проверяем общий творческий черновик проекта…");
  try {
    const api = await getApi();
    const shared = await readGenerationAiResearchWorkingDraft(
      api,
      context.projectId,
    );
    if (
      routePath() !== ROUTE
      || runtime.form !== form
      || !form.isConnected
      || formContext(form).projectId !== context.projectId
    ) return;
    const authoritative = authoritativeWorkingDraft(context, shared);
    setWorkingDraftAuthority(context.projectId, "verified");
    runtime.workingDraftHydrateRetryCount = 0;
    window.clearTimeout(runtime.workingDraftHydrateRetryTimer);
    runtime.workingDraftHydrateRetryTimer = 0;
    runtime.workingDraftConflict = false;
    renderWorkingDraftRecovery(null);
    if (!generationResearchWorkingDraftHydrationUnchanged(form, hydrationSnapshot)) {
      setStatus(
        "Вы уже изменили товар или параметры запуска. Поздний общий черновик не применён, ваши поля сохранены.",
        "neutral",
      );
      return;
    }
    applySharedWorkingDraft(form, authoritative);
  } catch (error) {
    console.warn("Generation AI research working draft hydrate failed", error);
    if (
      routePath() === ROUTE
      && runtime.form === form
      && form.isConnected
      && formContext(form).projectId === context.projectId
    ) {
      setWorkingDraftAuthority(context.projectId, "failed");
      scheduleWorkingDraftHydrateRetry(form, context);
      setStatus(
        "Общий черновик временно недоступен; сначала используем резервную копию этой вкладки. Автоматически повторим проверку через несколько секунд; рекомендации остаются необязательными.",
        "danger",
      );
    }
  } finally {
    runtime.workingDraftHydrating = false;
    const pending = runtime.workingDraftHydratePending;
    runtime.workingDraftHydratePending = null;
    if (
      pending?.form === runtime.form
      && pending.form.isConnected
      && routePath() === ROUTE
    ) {
      void hydrateSharedWorkingDraft(pending.form, formContext(pending.form))
        .finally(() => {
          if (runtime.form?.isConnected && routePath() === ROUTE) scheduleLoad();
        });
    }
  }
}

function briefControl(form = runtime.form) {
  return form?.elements?.brief || form?.querySelector?.('[name="brief"]') || null;
}

function setStatus(message, tone = "neutral") {
  const status = runtime.root?.querySelector("[data-research-recommendation-status]");
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function workingDraftRecoveryContainer() {
  return runtime.root?.querySelector(
    "[data-research-recommendation-recovery]",
  ) || null;
}

function renderWorkingDraftRecovery(kind /* null | "hydrate_failed" | "conflict" */) {
  const root = runtime.root;
  const recovery = workingDraftRecoveryContainer();
  if (!recovery) return;
  if (!kind) {
    recovery.replaceChildren();
    delete recovery.dataset.state;
    root?.removeAttribute("data-working-draft-conflict");
    return;
  }
  const recoveryButton = (label, datasetKey) => {
    const button = el("button", "btn btn-secondary btn-small", label);
    button.type = "button";
    button.dataset[datasetKey] = "true";
    return button;
  };
  if (kind === "hydrate_failed") {
    root?.removeAttribute("data-working-draft-conflict");
    recovery.dataset.state = "hydrate-failed";
    recovery.replaceChildren(
      el(
        "p",
        "generation-research-recommendations__recovery-note",
        "Автоматические повторы исчерпаны: сервер так и не подтвердил общий черновик проекта. Поля этой вкладки сохранены локально.",
      ),
      recoveryButton(
        "Повторить проверку общего черновика",
        "researchRecommendationWorkingDraftRetry",
      ),
    );
    return;
  }
  // kind === "conflict"
  root?.setAttribute("data-working-draft-conflict", "true");
  recovery.dataset.state = "conflict";
  const authoritative = runtime.form
    ? authoritativeWorkingDraft(formContext(runtime.form))
    : null;
  const clearedTombstone = Number(authoritative?.revision) > 0
    && authoritative?.draft === null;
  const children = [
    el(
      "p",
      "generation-research-recommendations__recovery-note",
      clearedTombstone
        ? "Другой участник очистил общий черновик проекта. Ваши поля не перезаписаны, но и не синхронизируются: очищенный черновик не пересоздаётся — примите версию коллеги."
        : "Другой участник обновил общий черновик проекта. Ваши поля не перезаписаны, но и не синхронизируются, пока вы не выберете, какую версию оставить.",
    ),
    recoveryButton(
      "Взять версию коллеги",
      "researchRecommendationConflictTakeTheirs",
    ),
  ];
  if (!clearedTombstone) {
    children.push(
      recoveryButton(
        "Оставить мою",
        "researchRecommendationConflictKeepMine",
      ),
    );
  }
  recovery.replaceChildren(...children);
}

function selectedEnvelope() {
  const recommendations = Array.isArray(runtime.response?.recommendations)
    ? runtime.response.recommendations
    : [];
  if (!recommendations.length) return null;
  return Number.isInteger(runtime.activeIndex)
    && runtime.activeIndex >= 0
    && runtime.activeIndex < recommendations.length
    ? recommendations[runtime.activeIndex]
    : null;
}

function recommendationWhy(envelope) {
  const recommendation = object(envelope?.recommendation);
  const basis = object(recommendation.learning_basis);
  const selected = asList(basis.selected_insight_keys, 4);
  const labels = {
    category: "категория и покупатель",
    competitors: "приёмы конкурентов",
    trends: "тренды",
    brief: "коммуникационная рамка",
  };
  return selected.length
    ? `Основание: ${selected.map((key) => labels[key] || key).join(" · ")}.`
    : "Основание: выбранное человеком исследование из ИИ-центра.";
}

function requestExplicitRecommendation(envelope) {
  if (!runtime.form || !envelope) return false;
  const target = {
    selectionId: recommendationSelectionId(envelope),
    recommendationPosition: recommendationPosition(envelope),
  };
  const targetKey = recommendationTargetKey(target);
  if (!targetKey) return false;
  const previousContext = formContext(runtime.form);
  const previousState = readState(previousContext);
  runtime.form.dataset.generationAiResearchWorkingSelectionId = target.selectionId;
  runtime.form.dataset.generationAiResearchWorkingPosition = String(
    target.recommendationPosition,
  );
  runtime.form.dataset.researchRecommendationVerificationRequired = "true";
  runtime.form.dataset.researchRecommendationVerificationState = "pending";
  runtime.form.dataset.researchRecommendationVerificationSelectionId =
    target.selectionId;
  runtime.form.dataset.researchRecommendationVerificationPosition = String(
    target.recommendationPosition,
  );
  delete runtime.form.dataset.researchRecommendationVerificationFailure;
  const targetedContext = formContext(runtime.form);
  writeState(targetedContext, {
    ...previousState,
    selectionId: target.selectionId,
    recommendationPosition: target.recommendationPosition,
    appliedFields: [],
    optedOut: false,
    explicit: true,
  });
  runtime.explicitApplyTargetKey = targetKey;
  authorizeTombstoneReplacement(targetedContext, target);
  runtime.key = recommendationKey(targetedContext);
  void loadRecommendations(runtime.form, targetedContext);
  return true;
}

function applyRecommendation(envelope, { explicit = false } = {}) {
  if (!runtime.form || !envelope) return false;
  const verifiedTarget = {
    selectionId: normalizedUuid(
      runtime.form.dataset.researchRecommendationVerificationSelectionId,
    ),
    recommendationPosition: Number(
      runtime.form.dataset.researchRecommendationVerificationPosition,
    ),
  };
  if (
    runtime.form.dataset.researchRecommendationVerificationRequired !== "true"
    || runtime.form.dataset.researchRecommendationVerificationState !== "verified"
    || recommendationTargetKey(verifiedTarget) !== recommendationTargetKey({
      selectionId: recommendationSelectionId(envelope),
      recommendationPosition: recommendationPosition(envelope),
    })
  ) {
    setStatus(
      "Сначала сервер должен подтвердить точный выбранный вариант и товар. ИИ‑поля не применены.",
      "danger",
    );
    return false;
  }
  if (!applyAuthoritativeRecommendationProduct(runtime.form, envelope)) {
    blockRecommendationProductMismatch(runtime.form, envelope);
    return false;
  }
  const context = formContext(runtime.form);
  const state = readState(context);
  const touched = normalizedTouchedFields(state);
  runtime.applying = true;
  const result = applyResearchRecommendationPresetToForm(runtime.form, envelope, {
    context,
    touchedFields: touched,
    explicit,
    optedOut: state.optedOut === true,
  });
  runtime.applying = false;
  if (!result.appliedFields.length) return false;
  const nextTouched = new Set(touched);
  if (explicit) result.appliedFields.forEach((field) => nextTouched.delete(field));
  const lastAppliedValues = {
    ...object(state.lastAppliedValues),
    ...Object.fromEntries(
      result.appliedFields.map((field) => [field, String(result.preset[field] ?? "")]),
    ),
  };
  const previousValues = {
    ...object(state.previousValues),
    ...Object.fromEntries(
      result.appliedFields.map((field) => [
        field,
        String(result.previousValues[field] ?? ""),
      ]),
    ),
  };
  writeState(context, {
    touched: nextTouched.has("brief"),
    touchedFields: [...nextTouched],
    appliedFields: result.appliedFields,
    lastAppliedText: String(result.preset.brief || state.lastAppliedText || ""),
    lastAppliedValues,
    previousValues,
    selectionId: result.selectionId,
    recommendationPosition: result.recommendationPosition,
    explicit,
    optedOut: false,
    autoApplyDisabled: false,
  });
  runtime.root?.removeAttribute("data-manual-mode");
  runtime.root?.setAttribute("data-ai-ready", "true");
  renderRecommendationPanel();
  const labels = result.appliedFields.map((field) => PRESET_FIELD_LABELS[field]).join(" · ");
  setStatus(
    explicit
      ? `Готово ИИ: ${labels}. Все поля можно изменить.`
      : `Готово ИИ: ${labels}. Проверьте настройки — все поля можно изменить.`,
    "ready",
  );
  scheduleWorkingDraftSave();
  return true;
}

function markHumanEdit(field) {
  if (runtime.applying || !runtime.form) return;
  if (!PRESET_FIELDS.includes(field)) return;
  const control = formControl(runtime.form, field);
  const context = formContext(runtime.form);
  const state = readState(context);
  const touched = normalizedTouchedFields(state);
  touched.add(field);
  if (control?.dataset) control.dataset.researchRecommendationEdited = "true";
  writeState(context, {
    touched: touched.has("brief"),
    touchedFields: [...touched],
    lastHumanValues: {
      ...object(state.lastHumanValues),
      [field]: controlValue(control),
    },
    ...(field === "brief" ? { lastHumanText: controlValue(control) } : {}),
  });
  runtime.root?.setAttribute("data-human-edited", "true");
  if (runtime.workingDraftConflict) {
    setStatus(
      `Поле «${PRESET_FIELD_LABELS[field]}» изменено, но не синхронизируется: сначала разрешите конфликт версий общего черновика.`,
      "danger",
    );
  } else {
    setStatus(
      `Поле «${PRESET_FIELD_LABELS[field]}» изменено вручную. ИИ больше не перезапишет его автоматически.`,
      "edited",
    );
  }
  renderRecommendationPanel();
  scheduleWorkingDraftSave();
}

function optOutResearchRecommendation() {
  if (!runtime.form) return;
  const envelope = selectedEnvelope();
  const context = formContext(runtime.form);
  const state = readState(context);
  const forceFullOptOut = state.autoApplyDisabled === true;
  runtime.applying = true;
  const result = optOutResearchRecommendationForForm(runtime.form, envelope, {
    context,
    state,
    forceRollback: forceFullOptOut,
  });
  runtime.applying = false;
  if (result.lineage_retained) {
    const retained = new Set(result.retained_fields);
    writeState(context, {
      optedOut: false,
      autoApplyDisabled: true,
      appliedFields: [...retained],
      touched: retained.has("brief"),
      touchedFields: [...retained],
    });
    runtime.root?.setAttribute("data-ai-ready", "true");
    runtime.root?.setAttribute("data-auto-apply-disabled", "true");
    runtime.root?.removeAttribute("data-manual-mode");
    scheduleWorkingDraftSave();
  } else {
    writeState(context, {
      optedOut: true,
      autoApplyDisabled: false,
      appliedFields: [],
      selectionId: "",
      recommendationPosition: null,
      previousValues: {},
      lastAppliedValues: {},
    });
    runtime.root?.removeAttribute("data-ai-ready");
    runtime.root?.removeAttribute("data-auto-apply-disabled");
    runtime.root?.setAttribute("data-manual-mode", "true");
    delete runtime.form.dataset.researchRecommendationVerificationRequired;
    delete runtime.form.dataset.researchRecommendationVerificationState;
    delete runtime.form.dataset.researchRecommendationVerificationFailure;
    delete runtime.form.dataset.researchRecommendationVerificationSelectionId;
    delete runtime.form.dataset.researchRecommendationVerificationPosition;
    delete runtime.form.dataset.generationAiResearchWorkingSelectionId;
    delete runtime.form.dataset.generationAiResearchWorkingPosition;
    delete runtime.form.dataset.researchRecommendationProductId;
    runtime.explicitApplyTargetKey = "";
    clearTombstoneReplacementAuthorization();
    runtime.activeIndex = -1;
    consumeRouteRecommendationTarget();
    void clearWorkingDraft();
  }
  renderRecommendationPanel();
  setStatus(
    result.lineage_retained
      ? "Автоподстановка отключена. Нетронутые значения возвращены, а ваши правки сохранены с происхождением выбранной рекомендации."
      : forceFullOptOut
        ? "Полный ручной режим включён: ИИ‑поля сброшены к значениям до рекомендации, связь снята."
        : "Ручной режим включён: все нетронутые автополя возвращены к прежним значениям, связь с рекомендацией снята.",
    result.lineage_retained ? "edited" : "manual",
  );
}

function optionButton(envelope, index, total) {
  const recommendation = object(envelope.recommendation);
  const button = el("button", "generation-research-recommendations__option");
  button.type = "button";
  button.dataset.recommendationIndex = String(index);
  button.classList.toggle("is-active", index === runtime.activeIndex);
  if (index === runtime.activeIndex) button.setAttribute("aria-current", "true");
  button.append(
    el("span", "generation-research-recommendations__option-number", `${index + 1}/${total}`),
    el("strong", "", clean(recommendation.title, 180) || `Вариант ${index + 1}`),
    el("small", "", envelope.scope_match === "exact_sku"
      ? "Точный SKU"
      : envelope.scope_match === "exact_product"
        ? "Точный товар"
        : "Обучение категории"),
  );
  return button;
}

function presetDisplayValue(field, value) {
  if (field === "mode") {
    return {
      mock: "Dry-run",
      real_photo: "Фото · Seedream",
      real_gen4: "Видео без речи · Gen4",
      real_seedance: "Видео с речью · Seedance",
    }[value] || value;
  }
  if (field === "duration_seconds") return `${value} сек.`;
  if (field === "format") {
    return {
      "9:16": "9:16 · вертикальный",
      "1:1": "1:1 · квадрат",
      "16:9": "16:9 · горизонтальный",
    }[value] || value;
  }
  if (field === "brief") return "готовый замысел";
  return String(value || "");
}

function presetSummary(preset, state) {
  const applied = new Set(Array.isArray(state.appliedFields) ? state.appliedFields : []);
  const touched = normalizedTouchedFields(state);
  const list = el("ul", "generation-research-recommendations__preset");
  PRESET_FIELDS.filter((field) => Object.hasOwn(preset, field)).forEach((field) => {
    const item = el("li");
    item.dataset.field = field;
    if (applied.has(field)) item.dataset.applied = "true";
    if (touched.has(field)) item.dataset.edited = "true";
    item.append(
      el("span", "generation-research-recommendations__preset-label", PRESET_FIELD_LABELS[field]),
      el("strong", "", presetDisplayValue(field, preset[field])),
      el(
        "small",
        "generation-research-recommendations__preset-state",
        touched.has(field)
          ? "изменено вами"
          : applied.has(field)
            ? "Готово ИИ"
            : "рекомендация",
      ),
    );
    list.append(item);
  });
  return list;
}

export function researchRecommendationConclusionLines(envelope) {
  const recommendation = object(envelope?.recommendation);
  const basis = object(recommendation.learning_basis);
  const selected = new Set(asList(basis.selected_insight_keys, 4));
  const sections = [
    ["category", object(basis.category_analysis)],
    ["competitors", object(basis.competitor_analysis)],
    ["trends", object(basis.trend_analysis)],
    ["brief", object(basis.creative_brief)],
  ];
  const allowedKeys = new Set([
    "summary", "definition", "buyer_jobs", "unknowns", "competitors",
    "positioning", "recurring_formats", "strengths", "weaknesses",
    "reusable_structures", "gap", "content_gaps", "limitations", "signals",
    "signal", "evidence", "recommended_use", "audience", "pains",
    "objections", "claims", "facts", "creative_potential", "reason",
    "recommended_next_step",
  ]);
  const collected = [];
  const visit = (value, key = "") => {
    if (collected.length >= MAX_RESEARCH_CONCLUSION_LINES) return;
    if (typeof value === "string" || typeof value === "number") {
      const line = clean(value, MAX_RESEARCH_CONCLUSION_LENGTH);
      if (line && !collected.includes(line)) collected.push(line);
      return;
    }
    if (Array.isArray(value)) {
      value.slice(0, MAX_RESEARCH_CONCLUSION_LINES).forEach((item) => visit(item, key));
      return;
    }
    const source = object(value);
    Object.entries(source).forEach(([childKey, childValue]) => {
      if (allowedKeys.has(childKey)) visit(childValue, childKey);
    });
  };
  sections.forEach(([section, value]) => {
    if (selected.has(section)) visit(value, section);
  });
  return collected.slice(0, MAX_RESEARCH_CONCLUSION_LINES);
}

// Совет о СПОСОБЕ — единственное место, где ИИ-центр говорит «это лучше
// сделать Дуэтом», а не «поставь такой-то движок». Человек переключает способ
// сам: совет не меняет маршрут молча.
const STRATEGY_ROUTES = Object.freeze({
  viral_product_swap: Object.freeze({ route: "copy_video", label: "Копия" }),
  viral_avatar_ugc: Object.freeze({ route: "avatar_video", label: "Дуэт" }),
  viral_rebuild: Object.freeze({ route: "strategy_video", label: "Создание" }),
});

function strategyAdviceNodes(envelope) {
  const recommendation = object(object(envelope).recommendation || envelope);
  const strategyId = clean(recommendation.recommended_strategy, 40);
  const target = STRATEGY_ROUTES[strategyId];
  if (!target) return [];
  const form = runtime.form;
  const activeRoute = intakeRoute(form);
  const advice = el("p", "generation-research-recommendations__strategy");
  advice.dataset.researchRecommendationStrategy = strategyId;
  const reason = clean(recommendation.strategy_reason, 400);
  advice.append(
    el("strong", "", `ИИ-центр советует способ: «${target.label}»`),
    el("span", "", reason ? ` — ${reason}` : ""),
  );
  if (activeRoute && activeRoute !== target.route && form?.querySelector(
    `[data-generation-intake-route="${target.route}"]`,
  )) {
    const switchButton = el("button", "btn btn-secondary btn-small", `Перейти в «${target.label}»`);
    switchButton.type = "button";
    switchButton.dataset.researchRecommendationSwitchRoute = target.route;
    advice.append(" ", switchButton);
  } else if (activeRoute === target.route) {
    advice.append(" ", el("span", "muted tiny", "— вы уже здесь"));
  }
  return [advice];
}

function renderRecommendationPanel() {
  const root = runtime.root;
  if (!root) return;
  const options = root.querySelector("[data-research-recommendation-options]");
  const preview = root.querySelector("[data-research-recommendation-preview]");
  const actions = root.querySelector("[data-research-recommendation-actions]");
  if (!options || !preview || !actions) return;
  options.replaceChildren();
  preview.replaceChildren();
  actions.replaceChildren();

  const recommendations = Array.isArray(runtime.response?.recommendations)
    ? runtime.response.recommendations
    : [];
  if (!recommendations.length) {
    const headerBadge = root.querySelector("[data-research-recommendation-badge]");
    if (headerBadge) {
      headerBadge.textContent = "Рекомендация · не обязательна";
      headerBadge.dataset.state = "empty";
    }
    preview.append(
      el("strong", "", "Пока нет одобренных рекомендаций"),
      el("p", "", "Завершите исследование ролика и выберите полезные выводы в ИИ-центре. После этого здесь появится готовый замысел."),
    );
    const research = el("a", "btn btn-secondary btn-small", "Открыть Исследования");
    research.href = `#/workspace/research?project_id=${encodeURIComponent(projectId())}`;
    const ai = el("a", "btn btn-secondary btn-small", "Открыть ИИ-центр");
    ai.href = `#/workspace/ai?project_id=${encodeURIComponent(projectId())}`;
    actions.append(research, ai);
    return;
  }

  recommendations.forEach((item, index) => options.append(optionButton(item, index, recommendations.length)));
  const previewEnvelope = selectedEnvelope() || recommendations[0];
  if (previewEnvelope) preview.append(...strategyAdviceNodes(previewEnvelope));
  if (!previewEnvelope) {
    preview.append(
      el("strong", "", "Выберите вариант"),
      el("p", "", "Ни один вариант не выбран заранее. Откройте нужную карточку, проверьте её и только затем примените."),
    );
    const ai = el("a", "btn btn-secondary", "Изменить обучение в ИИ‑центре");
    ai.href = `#/workspace/ai?project_id=${encodeURIComponent(projectId())}`;
    actions.append(ai);
    return;
  }
  const envelope = previewEnvelope;
  const recommendation = object(envelope?.recommendation);
  const context = formContext(runtime.form);
  const state = readState(context);
  const preset = normalizeResearchRecommendationPreset(envelope, context);
  const selectedId = recommendationSelectionId(envelope);
  const selectedPosition = recommendationPosition(envelope);
  const appliedToSelected = state.optedOut !== true
    && Boolean(state.selectionId)
    && state.selectionId === selectedId
    && Number(state.recommendationPosition) === selectedPosition
    && Array.isArray(state.appliedFields)
    && state.appliedFields.length > 0;
  const headerBadge = root.querySelector("[data-research-recommendation-badge]");
  if (headerBadge) {
    headerBadge.textContent = state.optedOut
      ? "Ручной режим"
      : state.autoApplyDisabled
        ? "ИИ‑основа · автоподстановка выключена"
      : appliedToSelected
        ? "Готово ИИ · можно изменить"
        : "Рекомендация · не обязательна";
    headerBadge.dataset.state = state.optedOut
      ? "manual"
      : state.autoApplyDisabled
        ? "edited"
      : appliedToSelected
        ? "ready"
        : "suggested";
  }
  const previewTitle = el("div", "generation-research-recommendations__preview-title");
  previewTitle.append(
    el("strong", "", clean(recommendation.title, 260) || "Рекомендация"),
    el(
      "span",
      "generation-research-recommendations__scope",
      isExactResearchRecommendation(envelope)
        ? "точный товар · можно подготовить"
        : "категория · только по кнопке",
    ),
  );
  const hook = clean(recommendation.hook, 700);
  const script = clean(recommendation.spoken_script, 1200);
  preview.append(previewTitle);
  if (hook) preview.append(el("p", "", `Хук: ${hook}`));
  if (script) preview.append(el("p", "muted", `Сюжет: ${script}`));
  const conclusions = researchRecommendationConclusionLines(envelope);
  if (conclusions.length) {
    const conclusionBlock = el("section", "generation-research-recommendations__conclusions");
    conclusionBlock.setAttribute("data-research-recommendation-conclusions", "true");
    conclusionBlock.append(el("strong", "", "Выводы ИИ, выбранные человеком"));
    const conclusionList = el("ul");
    conclusions.forEach((line) => conclusionList.append(el("li", "", line)));
    conclusionBlock.append(
      conclusionList,
      el("small", "muted", "Это проверяемое основание варианта. В замысел оно попадёт только после явной кнопки ниже; применение ничего не оплачивает и не запускает генерацию."),
    );
    preview.append(conclusionBlock);
  }
  preview.append(presetSummary(preset, state));
  preview.append(el("small", "", recommendationWhy(envelope)));
  preview.append(el("small", "", "Все подготовленные ИИ поля остаются редактируемыми. Бюджет, исходники, место размещения, количество и подтверждение оплаты ИИ не меняет."));

  const touched = normalizedTouchedFields(state).size > 0;
  const apply = el(
    "button",
    "btn",
    state.optedOut
      ? "Вставить этот вариант в «Замысел»"
      : touched
        ? "Вставить этот вариант вместо моих правок"
        : appliedToSelected
          ? "Вставить вариант в «Замысел» заново"
          : "Вставить этот вариант в «Замысел»",
  );
  apply.type = "button";
  apply.dataset.applyResearchRecommendation = "true";
  const restore = el("button", "btn btn-secondary", "Вернуть рекомендацию ИИ");
  restore.type = "button";
  restore.dataset.restoreResearchRecommendation = "true";
  restore.hidden = !touched || state.optedOut === true;
  const manual = el(
    "button",
    "btn btn-secondary",
    state.optedOut
      ? "Ручной режим включён"
      : state.autoApplyDisabled
        ? "Сбросить ИИ‑поля и перейти полностью вручную"
        : "Отключить автоподстановку",
  );
  manual.type = "button";
  manual.dataset.startResearchRecommendationManually = "true";
  manual.disabled = state.optedOut === true;
  const ai = el("a", "btn btn-secondary", "Изменить обучение в ИИ-центре");
  ai.href = `#/workspace/ai?project_id=${encodeURIComponent(context.projectId)}&category=${encodeURIComponent(context.category || "other")}`;
  actions.append(apply, restore, manual, ai);
}

function buildRoot() {
  const root = el("section", "generation-research-recommendations");
  root.dataset.ceV4Owned = "generation-research-recommendations";
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  const header = el("header", "generation-research-recommendations__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "РЕКОМЕНДАЦИИ ИИ ИЗ ИССЛЕДОВАНИЙ"),
    el("h4", "", "ИИ предлагает замысел — человек остаётся редактором"),
    el("p", "muted", "Берём только выводы, которые человек выбрал в ИИ‑центре. По ссылке конкретного варианта сервер сам подтверждает отбор, категорию и товар, затем заполняет только творческие поля. Любое поле можно изменить."),
    el("p", "muted tiny", "У проекта один активный общий ИИ‑черновик. Новый явно выбранный вариант заменит его только с проверкой версии; параллельная правка другого участника не перезаписывается молча."),
    el("p", "muted tiny", "OpenAI помогает с исследованием и текстовым замыслом. Готовый ролик рендерит выбранный в каскаде движок; применение рекомендации само по себе провайдера не вызывает и ничего не списывает."),
  );
  const badge = el("span", "generation-research-recommendations__badge", "Рекомендация · не обязательна");
  badge.dataset.researchRecommendationBadge = "true";
  header.append(copy, badge);
  const options = el("div", "generation-research-recommendations__options");
  options.dataset.researchRecommendationOptions = "true";
  const preview = el("div", "generation-research-recommendations__preview");
  preview.dataset.researchRecommendationPreview = "true";
  // Persistent recovery surface: unlike the shared status line it is never
  // overwritten by later edits and never cleared by renderRecommendationPanel.
  const recovery = el("div", "generation-research-recommendations__recovery");
  recovery.dataset.researchRecommendationRecovery = "true";
  const status = el("p", "generation-research-recommendations__status", "Выберите товар — загрузим обученные рекомендации.");
  status.dataset.researchRecommendationStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const actions = el("div", "generation-research-recommendations__actions");
  actions.dataset.researchRecommendationActions = "true";
  root.append(header, options, preview, recovery, status, actions);
  root.addEventListener("click", handleRootClick);
  return root;
}

// Маршруты «Копия» и «Дуэт» живут в компактных панелях, где мастер (и шаг
// «Замысел» с нашим корнем) скрыт стилями. Совет ИИ-центра должен стоять там,
// где человек пишет замысел: в слоте рекомендации активной панели. «Создание»
// идёт через полный мастер — там корень остаётся в шаге «Замысел».
const COMPACT_ROUTES = new Set(["copy_video", "avatar_video"]);

function intakeRoute(form) {
  return String(form?.dataset?.generationIntakeV4Route || "").trim();
}

function rootHost(form) {
  const route = intakeRoute(form);
  const mode = String(form?.dataset?.generationIntakeV4Mode || "").trim();
  if (COMPACT_ROUTES.has(route) && ["compact", "copy"].includes(mode)) {
    const slot = form.querySelector(
      `[data-generation-intake-recommendation="${route}"]`,
    );
    if (slot instanceof HTMLElement) return { host: slot, placement: "after-head" };
  }
  const guidedHost = form.querySelector('[data-ce-v4-generation-content="brief"]');
  if (guidedHost instanceof HTMLElement) return { host: guidedHost, placement: "prepend" };
  return null;
}

function placeRoot(root, form) {
  const target = rootHost(form);
  if (target) {
    const { host, placement } = target;
    if (placement === "after-head") {
      const head = host.querySelector(".generation-intake-v4__recommendation-head");
      const anchor = head?.nextSibling || null;
      if (root.parentNode !== host || root.previousElementSibling !== head) {
        host.insertBefore(root, anchor);
      }
      return;
    }
    if (root.parentNode !== host || host.firstElementChild !== root) host.prepend(root);
    return;
  }
  if (root.isConnected) return;
  const assist = form.querySelector("#generation-brief-assist");
  const control = briefControl(form);
  if (assist?.parentNode) assist.parentNode.insertBefore(root, assist);
  else if (control?.parentNode) control.parentNode.insertBefore(root, control);
  else form.prepend(root);
}

function ensureRoot(form) {
  let root = form.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (!(root instanceof HTMLElement)) root = buildRoot();
  // Хост зависит от активного маршрута: при смене панели корень переезжает.
  placeRoot(root, form);
  return root;
}

function updateGuidedHint(form) {
  const panel = form.querySelector('[data-ce-v4-generation-panel="brief"]');
  const hint = panel?.querySelector(".ce-v4-generation-guided__panel-hint");
  if (hint) {
    hint.textContent = "Сервер подготовит точный выбранный вариант из ИИ‑центра. Вы можете изменить любую строку; применение совета не запускает Runway.";
  }
  const actionHint = form.querySelector("[data-ce-v4-generation-action-hint]");
  if (actionHint && form.dataset.ceV4GenerationStep === "brief") {
    actionHint.textContent = "Рекомендация уже подготовлена — проверьте и поправьте её при необходимости";
  }
}

function recommendationKey(context) {
  return [
    context.projectId,
    context.selectionId,
    context.recommendationPosition,
    context.productId,
    context.category,
    context.sku,
    context.productName,
    context.platform,
  ]
    .map((value) => clean(value, 180).toLowerCase())
    .join("|");
}

async function loadRecommendations(form, context) {
  if (routePath() !== ROUTE) return;
  if (runtime.loading) {
    runtime.loadPending = true;
    return;
  }
  runtime.loadPending = false;
  const rememberedState = readState(context);
  const rememberedSelectionId = normalizedUuid(rememberedState.selectionId);
  const rememberedPosition = Number(rememberedState.recommendationPosition);
  const routedTarget = routeRecommendationTarget();
  const target = routedTarget || (context.selectionId
    && [1, 2, 3].includes(Number(context.recommendationPosition))
    ? {
        selectionId: context.selectionId,
        recommendationPosition: Number(context.recommendationPosition),
      }
    : (rememberedSelectionId && [1, 2, 3].includes(rememberedPosition)
        ? {
            selectionId: rememberedSelectionId,
            recommendationPosition: rememberedPosition,
          }
        : null));
  const routedTargetKey = recommendationTargetKey(routedTarget);
  if (
    routedTargetKey
    && explicitResearchRecommendationIntentIsFresh(routedTarget)
  ) {
    runtime.freshRouteApplyTargetKey = routedTargetKey;
    runtime.freshRouteApplyProjectId = normalizedUuid(context.projectId);
    // Consume the one-shot browser intent before any asynchronous work. A
    // reload can still preview the exact server response, but cannot apply it
    // again without a fresh human click.
    consumeExplicitResearchRecommendationIntent(routedTarget);
  } else if (
    !routedTargetKey
    || runtime.freshRouteApplyProjectId !== normalizedUuid(context.projectId)
    || runtime.freshRouteApplyTargetKey !== routedTargetKey
  ) {
    runtime.freshRouteApplyTargetKey = "";
    runtime.freshRouteApplyProjectId = "";
  }
  const freshRouteApplyTargetKey =
    runtime.freshRouteApplyProjectId === normalizedUuid(context.projectId)
      ? runtime.freshRouteApplyTargetKey
      : "";
  if (
    routedTarget
    && recommendationTargetKey(routedTarget) === recommendationTargetKey(target)
    && freshRouteApplyTargetKey === recommendationTargetKey(routedTarget)
  ) {
    authorizeTombstoneReplacement(context, routedTarget);
  }
  const authoritativeDraft = authoritativeWorkingDraft(context);
  if (target && !workingDraftAuthorityVerified(context)) {
    form.dataset.researchRecommendationVerificationRequired = "true";
    form.dataset.researchRecommendationVerificationState = "failed";
    form.dataset.researchRecommendationVerificationFailure = "working_draft_unverified";
    runtime.response = { recommendations: [] };
    runtime.activeIndex = -1;
    renderRecommendationPanel();
    // Keep the rendered blocker, but do not cache it as a completed catalog;
    // hydrateSharedWorkingDraft schedules a real retry after authority returns.
    runtime.response = null;
    setStatus(
      "Сначала сервер должен подтвердить общий черновик проекта. Вариант не выбран и ИИ‑поля не применены; повторите после восстановления связи.",
      "danger",
    );
    return;
  }
  if (
    target
    && Number(authoritativeDraft?.revision) > 0
    && authoritativeDraft?.draft === null
    && !tombstoneReplacementAuthorized(context, target)
  ) {
    consumeRouteRecommendationTarget(target);
    runtime.explicitApplyTargetKey = "";
    clearTombstoneReplacementAuthorization(context, target);
    delete form.dataset.generationAiResearchWorkingSelectionId;
    delete form.dataset.generationAiResearchWorkingPosition;
    delete form.dataset.researchRecommendationVerificationRequired;
    delete form.dataset.researchRecommendationVerificationState;
    delete form.dataset.researchRecommendationVerificationFailure;
    delete form.dataset.researchRecommendationVerificationSelectionId;
    delete form.dataset.researchRecommendationVerificationPosition;
    delete form.dataset.researchRecommendationLineage;
    delete form.dataset.researchRecommendationSelectionId;
    delete form.dataset.researchRecommendationPosition;
    delete form.dataset.researchRecommendationAppliedFields;
    delete form.dataset.researchRecommendationProductId;
    delete form.dataset.researchRecommendationProductCategory;
    form.querySelectorAll("[data-research-recommendation-applied]").forEach(
      (control) => {
        delete control.dataset.researchRecommendationApplied;
        delete control.dataset.researchRecommendationField;
        delete control.dataset.researchRecommendationEdited;
      },
    );
    runtime.response = { recommendations: [] };
    runtime.root?.setAttribute("data-manual-mode", "true");
    renderRecommendationPanel();
    setStatus(
      "Ручной режим сохранён: серверный выбор ИИ‑центра уже был очищен. Старый deep link не применён повторно и общая ревизия не изменена.",
      "manual",
    );
    return;
  }
  if (target && !context.selectionId) {
    form.dataset.generationAiResearchWorkingSelectionId = target.selectionId;
    form.dataset.generationAiResearchWorkingPosition = String(
      target.recommendationPosition,
    );
    const targetedContext = formContext(form);
    writeState(targetedContext, rememberedState);
    context = targetedContext;
  }
  if (target) {
    form.dataset.researchRecommendationVerificationRequired = "true";
    form.dataset.researchRecommendationVerificationState = "pending";
    form.dataset.researchRecommendationVerificationSelectionId =
      target.selectionId;
    form.dataset.researchRecommendationVerificationPosition = String(
      target.recommendationPosition,
    );
  }
  const key = recommendationKey(context);
  if (!context.projectId || (!target && !context.category)) {
    runtime.response = { recommendations: [] };
    renderRecommendationPanel();
    setStatus(
      "Откройте выбранный вариант из ИИ‑центра либо выберите товар и категорию. Категория из адресной строки не считается подтверждением.",
    );
    return;
  }
  runtime.loading = true;
  const requestRoot = runtime.root;
  if (requestRoot?.dataset) requestRoot.dataset.loading = "true";
  setStatus("ИИ-центр подбирает рекомендации из одобренных исследований…");
  try {
    const api = await getApi();
    const response = target
      ? typeof api.generationResearchRecommendation === "function"
        ? await api.generationResearchRecommendation({
            project_id: context.projectId,
            selection_id: target.selectionId,
            recommendation_position: target.recommendationPosition,
          })
        : await api.call(
            RPC_RECOMMENDATION,
            payloadWithOrganization(api, {
              project_id: context.projectId,
              selection_id: target.selectionId,
              recommendation_position: target.recommendationPosition,
            }),
          )
      : await api.call(
          RPC_RECOMMENDATIONS,
          payloadWithOrganization(api, {
            project_id: context.projectId,
            ...(context.productId ? { product_id: context.productId } : {}),
            product_category: context.category,
            product_name: context.productName,
            sku: context.sku,
            // The RPC uses this only as a ranking preference. It deliberately
            // keeps cross-platform recommendations in the response.
            platform: context.platform,
            limit: 3,
          }),
        );
    if (
      routePath() !== ROUTE
      || runtime.form !== form
      || !form.isConnected
      || recommendationKey(formContext(form)) !== key
    ) return;
    const source = object(response?.data || response);
    runtime.response = source;
    const recommendations = Array.isArray(source.recommendations)
      ? source.recommendations
      : [];
    const exactTarget = target
      ? explicitResearchRecommendationForTarget(
          recommendations,
          target,
        )
      : null;
    if (target) {
      if (!exactTarget) {
        throw new Error("generation_research_recommendation_response_mismatch");
      }
      if (!recommendationProductIdentityMatches(form, exactTarget)) {
        blockRecommendationProductMismatch(form, exactTarget);
        throw new Error("generation_research_recommendation_product_mismatch");
      }
      delete form.dataset.researchRecommendationVerificationFailure;
      form.dataset.researchRecommendationVerificationState = "verified";
    }
    const state = readState(context);
    const restoredIndex = recommendations.findIndex((item) => (
      state.selectionId
      && state.selectionId === recommendationSelectionId(item)
      && Number(state.recommendationPosition) === recommendationPosition(item)
    ));
    const targetIndex = target
      ? recommendations.findIndex((item) => recommendationTargetKey({
          selectionId: recommendationSelectionId(item),
          recommendationPosition: recommendationPosition(item),
        }) === recommendationTargetKey(target))
      : -1;
    runtime.activeIndex = targetIndex >= 0
      ? targetIndex
      : restoredIndex >= 0
        ? restoredIndex
        : -1;
    renderRecommendationPanel();

    const defaultPreview = recommendations[0] || null;
    const selected = exactTarget
      || (restoredIndex >= 0 ? recommendations[restoredIndex] : defaultPreview);
    const touched = normalizedTouchedFields(state);
    const selectedPosition = recommendationPosition(selected);
    const alreadyApplied = Boolean(
      state.selectionId
      && state.selectionId === recommendationSelectionId(selected)
      && Number(state.recommendationPosition) === selectedPosition
      && Array.isArray(state.appliedFields)
      && state.appliedFields.length,
    );
    if (alreadyApplied) {
      restoreResearchRecommendationPresetLineage(form, selected, state, { context });
      // The main generation runtime can be freshly rendered even when this
      // adapter already restored DOM lineage. Re-emit only the exact,
      // server-verified envelope; no control value is applied or changed.
      dispatchVerifiedResearchRecommendationProvenance(
        form,
        selected,
        state,
        context,
      );
      if (!runtime.workingDraft?.draft) scheduleWorkingDraftSave();
      if (target) {
        runtime.freshRouteApplyTargetKey = "";
        runtime.freshRouteApplyProjectId = "";
        consumeRouteRecommendationTarget(target);
      }
    }
    const explicitApplyRequested = researchRecommendationApplicationAuthorized(
      target,
      {
        freshRouteTargetKey: freshRouteApplyTargetKey,
        explicitApplyTargetKey: runtime.explicitApplyTargetKey,
      },
    );
    if (
      selected
      && target
      && explicitApplyRequested
      && !alreadyApplied
    ) {
      const applied = applyRecommendation(selected, { explicit: true });
      runtime.explicitApplyTargetKey = "";
      if (applied && target) {
        runtime.freshRouteApplyTargetKey = "";
        runtime.freshRouteApplyProjectId = "";
        consumeRouteRecommendationTarget(target);
      }
    } else if (defaultPreview) {
      setStatus(
        alreadyApplied
          ? "Готово ИИ восстановлено. Все подготовленные поля можно изменить."
          : state.optedOut
            ? "Ручной режим включён. Рекомендации доступны только по вашему явному выбору."
            : touched.size
              ? "Рекомендации обновлены, но ваши правки сохранены без изменений."
              : isExactResearchRecommendation(defaultPreview)
                && defaultPreview.can_auto_apply !== false
                ? "Рекомендация готова. Примените её или продолжайте со своим текстом."
                : "Есть обученные идеи категории. Выберите вариант и адаптируйте его к товару.",
        alreadyApplied ? "ready" : state.optedOut ? "manual" : touched.size ? "edited" : "ready",
      );
    } else {
      setStatus("Нет одобренных рекомендаций для этого проекта и категории.");
    }
  } catch (error) {
    if (target) clearTombstoneReplacementAuthorization(context, target);
    if (
      routePath() !== ROUTE
      || runtime.form !== form
      || !form.isConnected
      || recommendationKey(formContext(form)) !== key
    ) return;
    console.warn("Generation research recommendations unavailable", error);
    const productMismatch = /generation_research_recommendation_product_mismatch/u
      .test(String(error?.message || ""));
    if (target) {
      form.dataset.researchRecommendationVerificationState = "failed";
      if (productMismatch) {
        form.dataset.researchRecommendationVerificationFailure = "product_mismatch";
      }
    }
    runtime.response = { recommendations: [] };
    renderRecommendationPanel();
    setStatus(
      target
        ? productMismatch
          ? "Выбранные медиа относятся к другому товару, чем точный вариант ИИ‑центра. Рекомендация не применена и не сохранена; техническое ТЗ и платный запуск заблокированы."
          : "Сервер не подтвердил точный выбранный вариант. Его текст оставлен видимым, но техническое ТЗ и платный запуск заблокированы до восстановления происхождения или полного перехода в ручной режим."
        : "Рекомендации временно недоступны. Ручной замысел сохранён и запуск не блокируется.",
      "danger",
    );
  } finally {
    runtime.loading = false;
    if (requestRoot?.dataset) requestRoot.dataset.loading = "false";
    const replayForm = runtime.form;
    if (
      runtime.loadPending
      && routePath() === ROUTE
      && replayForm?.isConnected
    ) {
      runtime.loadPending = false;
      const nextContext = formContext(replayForm);
      runtime.key = recommendationKey(nextContext);
      void loadRecommendations(replayForm, nextContext);
    }
  }
}

function scheduleLoad({ force = false } = {}) {
  if (force === true && runtime.loadForcePending && runtime.loadTimer) return;
  runtime.loadForcePending = runtime.loadForcePending || force === true;
  window.clearTimeout(runtime.loadTimer);
  runtime.loadTimer = window.setTimeout(() => {
    runtime.loadTimer = 0;
    const forceLoad = runtime.loadForcePending;
    runtime.loadForcePending = false;
    if (!runtime.form?.isConnected) return;
    const context = formContext(runtime.form);
    const key = recommendationKey(context);
    const routedTarget = routeRecommendationTarget();
    const freshExplicitRoute = routedTarget
      && explicitResearchRecommendationIntentIsFresh(routedTarget);
    if (
      key === runtime.key
      && runtime.response
      && !freshExplicitRoute
      && !forceLoad
    ) return;
    runtime.key = key;
    void loadRecommendations(runtime.form, context);
  }, 180);
}

function handleStrategySwitchClick(event) {
  const button = event.target instanceof Element
    ? event.target.closest("[data-research-recommendation-switch-route]")
    : null;
  if (!(button instanceof HTMLElement)) return false;
  const route = clean(button.dataset.researchRecommendationSwitchRoute, 40);
  const trigger = runtime.form?.querySelector(
    `[data-generation-intake-route="${route}"]`,
  );
  if (trigger instanceof HTMLElement) trigger.click();
  return true;
}

function handleRootClick(event) {
  if (handleStrategySwitchClick(event)) return;
  if (event.target.closest?.("[data-research-recommendation-working-draft-retry]")) {
    event.preventDefault();
    runtime.workingDraftHydrateRetryCount = 0;
    runtime.workingDraftHydrateRetryDue = true;
    renderWorkingDraftRecovery(null);
    scheduleMount();
    return;
  }
  if (event.target.closest?.("[data-research-recommendation-conflict-take-theirs]")) {
    event.preventDefault();
    void resolveWorkingDraftConflict("theirs");
    return;
  }
  if (event.target.closest?.("[data-research-recommendation-conflict-keep-mine]")) {
    event.preventDefault();
    void resolveWorkingDraftConflict("mine");
    return;
  }
  const option = event.target.closest?.("[data-recommendation-index]");
  if (option) {
    event.preventDefault();
    runtime.activeIndex = Number(option.dataset.recommendationIndex) || 0;
    renderRecommendationPanel();
    return;
  }
  if (event.target.closest?.("[data-apply-research-recommendation]")) {
    event.preventDefault();
    requestExplicitRecommendation(
      selectedEnvelope() || runtime.response?.recommendations?.[0],
    );
    return;
  }
  if (event.target.closest?.("[data-restore-research-recommendation]")) {
    event.preventDefault();
    requestExplicitRecommendation(selectedEnvelope());
    return;
  }
  if (event.target.closest?.("[data-start-research-recommendation-manually]")) {
    event.preventDefault();
    optOutResearchRecommendation();
  }
}

function presetFieldForControl(control) {
  const name = String(control?.name || "");
  return PRESET_FIELDS.find((field) => PRESET_FORM_FIELDS[field] === name) || "";
}

function bindForm(form) {
  if (form.dataset.researchRecommendationsBound === "true") return;
  form.dataset.researchRecommendationsBound = "true";
  form.addEventListener("input", (event) => {
    const field = presetFieldForControl(event.target);
    if (field) {
      markHumanEdit(field);
    }
    if (field === "brief") {
      return;
    }
    if (["product_name", "sku", "media_id", "primary_media_id"].includes(event.target?.name)) scheduleLoad();
  });
  form.addEventListener("change", (event) => {
    const field = presetFieldForControl(event.target);
    if (field) markHumanEdit(field);
    if ([
      "product_category",
      "platform",
      "product_name",
      "sku",
      "media_id",
      "primary_media_id",
    ].includes(event.target?.name)) {
      scheduleLoad();
    }
  });
}

function defaultControlValue(control) {
  const options = Array.from(control?.options || []);
  if (options.length) {
    return String(options.find((option) => option.defaultSelected)?.value ?? options[0]?.value ?? "");
  }
  return String(control?.defaultValue ?? "");
}

function inferTouchedFields(form, state) {
  const touched = normalizedTouchedFields(state);
  const lastApplied = object(state.lastAppliedValues);
  PRESET_FIELDS.forEach((field) => {
    const control = formControl(form, field);
    if (!control) return;
    const value = controlValue(control);
    if (Object.hasOwn(lastApplied, field)) {
      if (value !== String(lastApplied[field])) touched.add(field);
      return;
    }
    if (value && value !== defaultControlValue(control)) touched.add(field);
  });
  return touched;
}

export function shouldHydrateGenerationResearchWorkingDraft({
  formChanged = false,
  authorityProjectId = "",
  contextProjectId = "",
  authority = "unknown",
  hydrating = false,
  hydrateRetryDue = false,
} = {}) {
  const projectId = normalizedUuid(contextProjectId);
  if (!projectId) return false;
  return formChanged
    || normalizedUuid(authorityProjectId) !== projectId
    || (!hydrating && (
      authority === "unknown"
      || (authority === "failed" && hydrateRetryDue)
    ));
}

export function generationResearchRecommendationMountResolveAction({
  contextKey = "",
  loadedKey = "",
  selectionId = "",
  recommendationPosition = null,
  verificationRequired = false,
  verificationState = "",
  loading = false,
} = {}) {
  if (!String(contextKey || "")) return "none";
  const hasExactTarget = Boolean(
    normalizedUuid(selectionId)
    && [1, 2, 3].includes(Number(recommendationPosition)),
  );
  const exactTargetNeedsVerification = Boolean(
    hasExactTarget
    && verificationRequired === true
    && verificationState === "pending",
  );
  const contextChanged = contextKey !== loadedKey;
  if (!contextChanged && !exactTargetNeedsVerification) return "none";
  if (loading) return contextChanged ? "replay" : "in_flight";
  return exactTargetNeedsVerification ? "force" : "schedule";
}

function mount() {
  if (routePath() !== ROUTE) {
    window.clearTimeout(runtime.workingDraftSaveTimer);
    runtime.workingDraftSaveTimer = 0;
    // Fresh URL and explicit-button grants live only for one uninterrupted
    // Create-route visit. Leaving while verification is in flight must not
    // let a later back-navigation reuse an already-consumed human intent.
    runtime.freshRouteApplyTargetKey = "";
    runtime.freshRouteApplyProjectId = "";
    runtime.explicitApplyTargetKey = "";
    runtime.tombstoneReplacementKey = "";
    runtime.form = null;
    runtime.root = null;
    return;
  }
  const form = document.querySelector("#mock-batch-form");
  if (!(form instanceof HTMLFormElement)) return;
  const formChanged = runtime.form !== form;
  runtime.form = form;
  runtime.root = ensureRoot(form);
  bindForm(form);
  updateGuidedHint(form);
  const context = formContext(form);
  const shouldHydrate = shouldHydrateGenerationResearchWorkingDraft({
    formChanged,
    authorityProjectId: runtime.workingDraftAuthorityProjectId,
    contextProjectId: context.projectId,
    authority: runtime.workingDraftAuthority,
    hydrating: runtime.workingDraftHydrating,
    hydrateRetryDue: runtime.workingDraftHydrateRetryDue,
  });
  const state = readState(context);
  const touched = inferTouchedFields(form, state);
  if (touched.size) {
    writeState(context, {
      touched: touched.has("brief"),
      touchedFields: [...touched],
    });
  }
  if (
    formChanged
    && runtime.response
    && runtime.key === recommendationKey(context)
  ) {
    const recommendations = Array.isArray(runtime.response.recommendations)
      ? runtime.response.recommendations
      : [];
    const restoredIndex = recommendations.findIndex((item) => (
      state.selectionId
      && state.selectionId === recommendationSelectionId(item)
      && Number(state.recommendationPosition) === recommendationPosition(item)
    ));
    if (restoredIndex >= 0) runtime.activeIndex = restoredIndex;
    renderRecommendationPanel();
    if (restoredIndex >= 0) {
      restoreResearchRecommendationPresetLineage(
        form,
        recommendations[restoredIndex],
        state,
        { context },
      );
    }
  }
  const knownShared = authoritativeWorkingDraft(context);
  if (knownShared) {
    runtime.workingDraft = knownShared;
    runtime.workingDraftProjectId = context.projectId;
  }
  // The desktop adapter is invoked by a MutationObserver. Hydration itself
  // updates the status and form, so rehydrating the same connected form on
  // every observer callback creates a self-sustaining checking loop and never
  // reaches the recommendation resolver. A new form or project still starts a
  // fresh authoritative read. A settled form only queues recommendation work
  // when its exact context changed or a restored selection is still pending.
  if (!shouldHydrate) {
    const contextKey = recommendationKey(context);
    const resolveAction = generationResearchRecommendationMountResolveAction({
      contextKey,
      loadedKey: runtime.key,
      selectionId: context.selectionId,
      recommendationPosition: context.recommendationPosition,
      verificationRequired:
        form.dataset.researchRecommendationVerificationRequired === "true",
      verificationState:
        form.dataset.researchRecommendationVerificationState || "",
      loading: runtime.loading,
    });
    // A changed programmatic restore must replay after the in-flight request.
    // The same exact verification already in flight needs no duplicate RPC.
    if (resolveAction === "replay") runtime.loadPending = true;
    else if (resolveAction === "force") scheduleLoad({ force: true });
    else if (resolveAction === "schedule") scheduleLoad();
    return;
  }
  // A cached value can be the previous side of an app-level force refresh.
  // Never mark it verified or exact-resolve it before the shared read settles;
  // readGenerationAiResearchWorkingDraft joins that in-flight promise.
  // A due retry is a one-shot grant: consume it here so only the timer or the
  // explicit button — never a plain observer mutation — restarts hydration.
  runtime.workingDraftHydrateRetryDue = false;
  setWorkingDraftAuthority(context.projectId, "unknown");
  void hydrateSharedWorkingDraft(form, context).finally(() => {
    if (form.isConnected && routePath() === ROUTE) scheduleLoad();
  });
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
      "generation-research-recommendations",
      mount,
      { priority: 220 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", scheduleMount);
  window.addEventListener("hashchange", scheduleMount);
  window.queueMicrotask(scheduleMount);
}

export const GenerationResearchRecommendations = Object.freeze({
  mount,
  format: formatResearchRecommendation,
  normalizePreset: normalizeResearchRecommendationPreset,
  resolveAppliedFields: resolveResearchPresetAppliedFields,
  applyPresetToForm: applyResearchRecommendationPresetToForm,
  restoreLineage: restoreResearchRecommendationPresetLineage,
  optOutForForm: optOutResearchRecommendationForForm,
  shouldAutoApply: shouldAutoApplyResearchRecommendation,
  presetEvent: PRESET_EVENT,
  optOutEvent: PRESET_OPT_OUT_EVENT,
});
