/*
 * ContentEngine generation intake v2.
 *
 * This module describes the operator-facing fields for three genuinely
 * different production routes. It is deliberately pure: no DOM, storage,
 * provider calls, paid actions, secrets, or implicit strategy selection.
 */

export const GENERATION_INTAKE_VERSION = "generation-intake-v2";

export const GENERATION_INTAKE_STRATEGY_IDS = Object.freeze({
  copy: "copy_video",
  avatar: "avatar_video",
  strategy: "strategy_video",
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

function field(value) {
  return deepFreeze({
    required: false,
    max_length: null,
    ...value,
  });
}

export const GENERATION_INTAKE_STRATEGIES = deepFreeze([
  {
    strategy_id: GENERATION_INTAKE_STRATEGY_IDS.copy,
    preparation_recipe: "product_swap",
    authority_strategy_id: "viral_product_swap",
    public_label: "Скопировать ролик",
    public_summary:
      "Повторить действия, ракурсы, темп, свет и монтаж референса максимально близко и заменить товар на ваш.",
    promise:
      "Система стремится сохранить механику исходной сцены целиком. Пиксель-в-пиксель идентичность не обещается: после генерации результат проходит обязательную проверку.",
    form_kind: "compact",
    fields: [
      field({ id: "source_url", kind: "url", required: true }),
      field({ id: "product_media_ids", kind: "product_media", required: true }),
      field({ id: "description", kind: "textarea", max_length: 1_200 }),
    ],
    internal_pipeline: [
      "register_source",
      "attach_lawful_media",
      "analyze_reference",
      "extract_original_product_reference",
      "run_product_swap",
      "human_review",
    ],
  },
  {
    strategy_id: GENERATION_INTAKE_STRATEGY_IDS.avatar,
    preparation_recipe: "character_performance",
    authority_strategy_id: null,
    public_label: "Сделать с аватаром",
    public_summary:
      "Создать нового героя по вашему описанию и повторить им механику выбранного ролика.",
    promise:
      "В форме остаются только пожелания к аватару, ссылка на ролик и необязательный комментарий. Технический character reference система готовит сама и не маскирует его под ввод пользователя.",
    form_kind: "compact",
    fields: [
      field({ id: "avatar_wishes", kind: "textarea", required: true, max_length: 1_200 }),
      field({ id: "source_url", kind: "url", required: true }),
      field({ id: "description", kind: "textarea", max_length: 1_200 }),
    ],
    internal_pipeline: [
      "register_source",
      "attach_lawful_media",
      "analyze_reference",
      "generate_avatar_reference",
      "run_character_performance",
      "human_review",
    ],
  },
  {
    strategy_id: GENERATION_INTAKE_STRATEGY_IDS.strategy,
    preparation_recipe: "generation_spec",
    authority_strategy_id: "viral_rebuild",
    public_label: "Создать видео по стратегии",
    public_summary:
      "Полный конструктор: товар, задача, площадка, сценарий, исходники, модель, длительность и бюджет.",
    promise:
      "Это отдельный режиссёрский маршрут для нового ролика, а не копирование исходника и не простая замена героя.",
    form_kind: "full",
    fields: [],
    internal_pipeline: [
      "full_generation_spec",
      "model_recommendation",
      "provider_preflight",
      "explicit_paid_confirmation",
      "generation",
      "human_review",
    ],
  },
]);

export function generationIntakeStrategy(strategyId) {
  const normalized = String(strategyId || "").trim().toLowerCase();
  return GENERATION_INTAKE_STRATEGIES.find(
    (strategy) => strategy.strategy_id === normalized,
  ) || null;
}

export function generationIntakeStrategyForAuthority(authorityStrategyId) {
  const normalized = String(authorityStrategyId || "").trim().toLowerCase();
  if (!normalized) return null;
  return GENERATION_INTAKE_STRATEGIES.find(
    (strategy) => strategy.authority_strategy_id === normalized,
  ) || null;
}

// Compatibility name for old drafts and tests. It is intentionally an alias
// to authority lookup, not a claim that every compact route has a legacy paid
// strategy. Avatar uses Character Performance and therefore returns null for
// the old Product UGC authority.
export const generationIntakeStrategyForLegacy =
  generationIntakeStrategyForAuthority;

export function canonicalGenerationIntakeSourceUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  if (url.protocol !== "https:") return "";
  const host = url.hostname.toLowerCase().replace(/\.$/u, "");
  const parts = url.pathname.split("/").filter(Boolean);
  const youtubeHosts = new Set([
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
  ]);
  if (!youtubeHosts.has(host)) return "";
  const candidate = host === "youtu.be"
    ? parts[0]
    : url.pathname === "/watch"
      ? url.searchParams.get("v")
      : ["shorts", "embed", "live"].includes(parts[0] || "")
        ? parts[1]
        : "";
  return YOUTUBE_VIDEO_ID.test(String(candidate || ""))
    ? `https://youtube.com/watch?v=${candidate}`
    : "";
}

function cleanText(value, maxLength) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, maxLength);
}

function normalizeMediaIds(value) {
  if (!Array.isArray(value)) return [];
  const result = [];
  const seen = new Set();
  for (const raw of value) {
    const id = String(raw || "").trim().toLowerCase();
    if (!UUID_PATTERN.test(id) || seen.has(id)) continue;
    seen.add(id);
    result.push(id);
  }
  return result.slice(0, 10);
}

export function createGenerationIntakeDraft(strategyId, seed = {}) {
  const strategy = generationIntakeStrategy(strategyId);
  if (!strategy) return null;
  return deepFreeze({
    version: GENERATION_INTAKE_VERSION,
    strategy_id: strategy.strategy_id,
    preparation_recipe: strategy.preparation_recipe,
    authority_strategy_id: strategy.authority_strategy_id,
    source_url: canonicalGenerationIntakeSourceUrl(seed.source_url),
    source_id: UUID_PATTERN.test(String(seed.source_id || "").trim())
      ? String(seed.source_id).trim().toLowerCase()
      : "",
    avatar_wishes: cleanText(seed.avatar_wishes, 1_200),
    description: cleanText(seed.description, 1_200),
    product_media_ids: normalizeMediaIds(seed.product_media_ids),
  });
}

export function validateGenerationIntakeDraft(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return deepFreeze({ ok: false, errors: [{ code: "draft_invalid", field: "draft" }], normalized: null });
  }
  const strategy = generationIntakeStrategy(value.strategy_id);
  if (!strategy) {
    return deepFreeze({ ok: false, errors: [{ code: "strategy_unknown", field: "strategy_id" }], normalized: null });
  }
  const normalized = createGenerationIntakeDraft(strategy.strategy_id, value);
  const errors = [];
  if (value.version !== GENERATION_INTAKE_VERSION) {
    errors.push({ code: "version_mismatch", field: "version" });
  }
  if (String(value.preparation_recipe || "") !== strategy.preparation_recipe) {
    errors.push({ code: "preparation_recipe_mismatch", field: "preparation_recipe" });
  }
  const suppliedAuthority = value.authority_strategy_id === null
    ? null
    : String(value.authority_strategy_id || "");
  if (suppliedAuthority !== strategy.authority_strategy_id) {
    errors.push({ code: "authority_strategy_mismatch", field: "authority_strategy_id" });
  }
  if (strategy.form_kind === "compact" && !normalized.source_url) {
    errors.push({ code: "source_url_required", field: "source_url" });
  }
  if (
    strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
    && normalized.product_media_ids.length < 1
  ) {
    errors.push({ code: "product_media_required", field: "product_media_ids" });
  }
  if (
    strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.avatar
    && normalized.avatar_wishes.length < 10
  ) {
    errors.push({ code: "avatar_wishes_required", field: "avatar_wishes" });
  }
  if (
    strategy.strategy_id !== GENERATION_INTAKE_STRATEGY_IDS.avatar
    && normalized.avatar_wishes
  ) {
    errors.push({ code: "avatar_wishes_forbidden", field: "avatar_wishes" });
  }
  if (
    strategy.strategy_id !== GENERATION_INTAKE_STRATEGY_IDS.copy
    && normalized.product_media_ids.length > 0
  ) {
    errors.push({ code: "product_media_forbidden", field: "product_media_ids" });
  }
  return deepFreeze({
    ok: errors.length === 0,
    errors,
    normalized: errors.length === 0 ? normalized : null,
  });
}

export function generationIntakeInternalBrief(value) {
  const validation = validateGenerationIntakeDraft(value);
  if (!validation.ok) return null;
  const draft = validation.normalized;
  const optional = draft.description ? ` Дополнительное пожелание: ${draft.description}` : "";
  if (draft.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy) {
    return (
      "Повтори исходный ролик максимально близко по действиям, ракурсам, темпу, свету, композиции и монтажу. "
      + "Замени показанный товар на точный товар проекта; не меняй его форму, цвет, упаковку, этикетку и пропорции."
      + optional
    );
  }
  if (draft.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.avatar) {
    return (
      `Создай аватара по пожеланию оператора: ${draft.avatar_wishes}. `
      + "Повтори им механику исходного ролика максимально близко по движениям, темпу, ракурсам и композиции."
      + optional
    );
  }
  return draft.description || "";
}

export function generationIntakePublicSummary(value) {
  const strategy = generationIntakeStrategy(value?.strategy_id);
  if (!strategy) return null;
  const draft = createGenerationIntakeDraft(strategy.strategy_id, value);
  return deepFreeze({
    version: draft.version,
    strategy_id: strategy.strategy_id,
    preparation_recipe: strategy.preparation_recipe,
    authority_strategy_id: strategy.authority_strategy_id,
    public_label: strategy.public_label,
    source_url: draft.source_url,
    source_registered: Boolean(draft.source_id),
    avatar_wishes_present: Boolean(draft.avatar_wishes),
    description_present: Boolean(draft.description),
    product_media_count: draft.product_media_ids.length,
    form_kind: strategy.form_kind,
  });
}
