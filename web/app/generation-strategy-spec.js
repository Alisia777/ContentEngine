/*
 * Pure client contract for generation-strategy specification authority.
 *
 * This module intentionally performs no DOM, storage, network, provider, or
 * spend work. Browser-authored mechanics remain a proposal until the server
 * returns an exact draft and a human separately approves that exact spec
 * identity through creator_control_generation_spec.
 */

export const GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_VERSION =
  "generation-strategy-spec-prepare-request-v1";
export const GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION =
  "generation-strategy-spec-prepare-response-v1";
export const GENERATION_STRATEGY_SPEC_SCOPE_VERSION =
  "generation-strategy-spec-scope-v2";
export const GENERATION_STRATEGY_SPEC_LEGACY_SCOPE_VERSION =
  "generation-strategy-spec-scope-v1";
export const GENERATION_STRATEGY_ROUTE_POLICY_VERSION =
  "generation-strategy-route-policy-v1";
export const GENERATION_STRATEGY_SPEC_MECHANICS_VERSION =
  "generation-strategy-mechanics-summary-v1";
export const GENERATION_STRATEGY_SPEC_CONTROL_VERSION =
  "generation-spec-control-v1";

const CATALOG_VERSION = "2026-08-14.v1";

// Пределы длительности ИСХОДНОГО ролика, в секундах с дробной частью.
// Это НЕ то же, что пределы выбранной длительности ролика: те целые и
// живут в реестре маршрутов. Здесь измеренная длина файла, и нижняя
// граница 1.8 повторяет проверку привязки в базе (202608230005).
//
// Стратегия вне этого набора длительность исходника не принимает
// вовсе: у «Создания» исходника нет, и число там говорило бы ни о чём.
const SOURCE_DURATION_BOUNDS = Object.freeze({
  viral_product_swap: Object.freeze({ minimum: 1.8, maximum: 15 }),
  viral_avatar_ugc: Object.freeze({ minimum: 1.8, maximum: 60 }),
});
const RECIPE_VERSION = "2026-06";
const SOURCE_VERSION = "generation-strategy-exact-source-snapshot-v1";
const MECHANICS_SNAPSHOT_VERSION =
  "generation-strategy-mechanics-snapshot-v1";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,120}$/u;
const CONTROL_PATTERN = /[\u0000-\u001f\u007f-\u009f]/u;
const IMAGE_MIMES = Object.freeze(new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]));
const PLATFORMS = Object.freeze(new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]));
const PRODUCT_CATEGORIES = Object.freeze(new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]));
const COMMON_ATTESTATIONS = Object.freeze([
  "source_media_rights_confirmed",
  "transformative_use_confirmed",
  "product_assets_rights_confirmed",
  "depicted_people_consent_confirmed",
]);
const MECHANICS_KEYS = Object.freeze([
  "version",
  "hook",
  "beat_sequence",
  "pacing",
  "camera_language",
  "composition",
  "audio_pattern",
  "cta_pattern",
]);
const PREPARE_INPUT_KEYS = Object.freeze([
  "organization_id",
  "project_id",
  "platform",
  "product_category",
  "selection",
  "editable_intent",
  "proposed_prompt",
  "mechanics_summary",
  "confirmation",
  "reason",
  "idempotency_key",
]);
const PREPARE_REQUEST_KEYS = Object.freeze([
  "version",
  ...PREPARE_INPUT_KEYS,
]);
// Товар «Дуэта» приходит ЯВНЫМ полем, а не выводится из фотографий: фотографий
// товара у него нет вовсе. У «Копии» и «Создания» товар уже назван снимками, и
// принимать его вторым путём нельзя — два источника одного факта однажды
// разойдутся, и разойдутся молча.
const DUET_PRODUCT_STRATEGY = "viral_avatar_ugc";
const PREPARE_INPUT_KEYS_WITH_PRODUCT = Object.freeze([
  ...PREPARE_INPUT_KEYS,
  "product_id",
]);
const PREPARE_REQUEST_KEYS_WITH_PRODUCT = Object.freeze([
  "version",
  ...PREPARE_INPUT_KEYS_WITH_PRODUCT,
]);
function prepareKeysFor(value, withVersion) {
  const duet = isPlainObject(value?.selection)
    && value.selection.strategy_id === DUET_PRODUCT_STRATEGY;
  if (duet) {
    return withVersion
      ? PREPARE_REQUEST_KEYS_WITH_PRODUCT
      : PREPARE_INPUT_KEYS_WITH_PRODUCT;
  }
  return withVersion ? PREPARE_REQUEST_KEYS : PREPARE_INPUT_KEYS;
}
const PREPARE_RESPONSE_KEYS = Object.freeze([
  "ok",
  "version",
  "generation_spec",
  "history",
  "recommended_next_action",
  "strategy",
  "contract",
]);
const CONTROL_RESPONSE_KEYS = Object.freeze([
  "ok",
  "version",
  "generation_spec",
  "history",
  "recommended_next_action",
  "automatic_approval",
  "automatic_spend",
  "automatic_generation",
]);
const SCOPE_COMMON_KEYS = Object.freeze([
  "version",
  "authority_kind",
  "primary_media_id",
  "media_ids",
  "platform",
  "strategy_id",
  "recipe",
  "input_mode",
  "duration_seconds",
  "product_category",
  "format",
  "ratio",
  "resolution",
  "audio",
  "spoken_dialogue",
  "reference_count",
  "reference_video",
  "first_frame",
  "last_frame",
  "selection",
  "selection_hash",
  "asset_snapshot",
  "asset_snapshot_hash",
  "source",
  "source_hash",
  "mechanics",
  "mechanics_hash",
]);
const LEGACY_SCOPE_KEYS = Object.freeze([
  ...SCOPE_COMMON_KEYS,
  "provider",
]);
const SCOPE_KEYS = Object.freeze([
  ...SCOPE_COMMON_KEYS,
  "route_policy",
]);
const ROUTE_POLICY_KEYS = Object.freeze([
  "version",
  "authority",
  "binding",
]);
const ROUTE_POLICY = deepFreeze({
  version: GENERATION_STRATEGY_ROUTE_POLICY_VERSION,
  authority: "generation_strategy_provider_routes",
  binding: "deferred_until_preflight",
});
const ASSET_SNAPSHOT_KEYS = Object.freeze([
  "selection_role",
  "selection_ordinal",
  "media_id",
  "sha256",
  "kind",
  "mime_type",
  "product_id",
  "rights_confirmed",
]);
const SOURCE_KEYS = Object.freeze([
  "version",
  "attachment_id",
  "attachment_hash",
  "source_id",
  "source_hash",
  "media_object_id",
  "media_sha256",
  "size_bytes",
  "duration_seconds",
]);
const MECHANICS_SNAPSHOT_KEYS = Object.freeze([
  "version",
  "strategy_id",
  "source_attachment_id",
  "source_attachment_hash",
  "source_media_id",
  "source_media_sha256",
  "summary",
  "reviewed_by",
  "review_confirmation",
]);
const SPEC_REQUIRED_KEYS = Object.freeze([
  "spec_id",
  "spec_version",
  "spec_hash",
  "status",
  "exact_scope",
  "editable_intent",
  "compiled_prompt",
  "prompt_hash",
  "research_provenance",
  "performance_policy_provenance",
  "repair_provenance",
  "outcome_selection_id",
  "created_at",
  "updated_at",
]);
const SPEC_OPTIONAL_KEYS = Object.freeze(["approved_at"]);
const ACTION_KEYS = Object.freeze([
  "code",
  "action",
  "label",
  "reason",
  "requires_confirmation",
  "provider_action",
  "spend_action",
]);
const STRATEGY_RESPONSE_KEYS = Object.freeze([
  "strategy_id",
  "recipe",
  "selection_hash",
  "source_media_id",
  "source_snapshot_hash",
  "mechanics_required",
  "mechanics_snapshot_hash",
  "human_approval_required",
]);
const CONTRACT_KEYS = Object.freeze([
  "server_resolved_recipe",
  "server_resolved_source",
  "browser_hashes_accepted",
  "browser_source_binding_accepted",
  "mechanics_text_is_proposal_until_spec_approval",
  "provider_call_started",
  "paid_start_integrated",
  "automatic_approval",
]);
const APPROVAL_INPUT_KEYS = Object.freeze([
  "project_id",
  "draft",
  "human_confirmation",
  "reason",
]);
const NORMALIZED_PREPARE_KEYS = Object.freeze([
  "version",
  "organization_id",
  "project_id",
  "generationSpec",
  "history",
  "recommendedNextAction",
  "strategy",
  "contract",
]);
const APPROVED_CONTEXT_KEYS = Object.freeze([
  "organization_id",
  "project_id",
  "spec_id",
  "spec_version",
  "spec_hash",
  "prompt_hash",
  "status",
  "strategy_id",
  "recipe",
  "selection_hash",
  "asset_snapshot_hash",
  "source_media_id",
  "source_snapshot_hash",
  "mechanics_snapshot_hash",
  "approved_at",
]);

// Рецепты, у которых исходник становится НАСТОЯЩИМ ВХОДОМ ПРОВАЙДЕРА.
//
// Это единственная «Копия»: только она переписывает сам ролик. У «Дуэта» кадр
// тоже приходит из исходника, но провайдеру он не отдаётся — ведущего снимают
// отдельно, а соединение делает наш ffmpeg. У «Создания» исходник и вовсе
// только механика.
//
// Ранняя редакция (21.08.2026) держала здесь и product_ugc: тогда «Аватар»
// считался заменой человека в кадре. Владелец это отменил 22.08.2026, и признак
// «уходит провайдеру» разошёлся с признаком «кадр из исходника» — их больше
// нельзя выражать одним набором.
const PROVIDER_SOURCE_INPUT_RECIPES = new Set(["product_swap"]);

const STRATEGY_RULES = deepFreeze({
  // «Аватар» с 22.08.2026 правит готовый ролик, а не снимает новый UGC про
  // товар: измерение разрешением (кадр задаёт исходник), товара нет, фотография
  // аватара необязательна — его можно задать описанием, которое исполняет
  // Runway Aleph. Верхняя граница четыре — предел ссылок на изображения у Kling.
  viral_avatar_ugc: {
    recipe: "product_ugc",
    inputMode: "video_and_avatar_images",
    // Цель работы «Дуэта» — САМ КОММЕНТИРУЕМЫЙ РОЛИК (решение владельца
    // 22.08.2026). Ведущий приходит из библиотеки проекта и медиа-объектом
    // формы не бывает, а товар остаётся полем учёта: дуэт снимают, чтобы
    // продать наш товар, даже когда разбирают чужую рекламу.
    //
    // Пустой список здесь тоже был возможен — сборщик объёма умеет отсутствие
    // цели, — но тогда дуэт выпал бы из фильтров архива и разрезов бюджета по
    // товару, а версия ТЗ требует непустого целевого медиа.
    targetRoles: ["source_video"],
    dimension: "resolution",
    dimensions: {
      "720p": "source",
      "1080p": "source",
    },
    // Длина дуэта задана комментируемым роликом, а не вкусом оператора.
    // Числа те же, что в строке реестра маршрута heygen.
    duration: { minimum: 3, maximum: 60 },
    // Ровно один ассет: ведущего задаёт запись в библиотеке, а не фотография.
    // В теле запроса к HeyGen медиа нет вовсе — личность приходит avatar_id.
    roles: {
      source_video: [1, 1],
    },
    attestationKeys: [
      ...COMMON_ATTESTATIONS,
      "avatar_likeness_consent_confirmed",
    ],
    // ДУЭТ: исходный ролик остаётся собой, а снизу врезается сгенерированный
    // ведущий и КОММЕНТИРУЕТ происходящее. Модель ведущего исходное видео не
    // получает вовсе — она делает говорящего человека, и всё, что он скажет,
    // приходит текстом. Значит разбор ролика тут не лишний шаг, а источник
    // речи: комментатор, не знающий, что в ролике, скажет только общие слова.
    //
    // «Копия» разбора по-прежнему не требует: она правит сам ролик, и сцена
    // доезжает до модели целиком, а не пересказом.
    mechanicsRequired: true,
  },
  viral_product_swap: {
    recipe: "product_swap",
    inputMode: "video_and_product_images",
    targetRoles: ["new_product_image"],
    dimension: "resolution",
    dimensions: {
      "720p": "source",
      "1080p": "source",
    },
    roles: {
      source_video: [1, 1],
      original_product_image: [1, 1],
      new_product_image: [1, 10],
    },
    attestationKeys: COMMON_ATTESTATIONS,
    mechanicsRequired: false,
  },
  viral_rebuild: {
    recipe: "product_ad",
    inputMode: "product_images",
    targetRoles: ["product_image"],
    dimension: "ratio",
    dimensions: {
      "1280:720": "720p",
      "720:1280": "720p",
      "960:960": "720p",
      "834:1112": "720p",
      "1920:1080": "1080p",
      "1080:1920": "1080p",
      "1440:1440": "1080p",
      "1248:1664": "1080p",
    },
    roles: {
      source_video: [1, 1],
      product_image: [1, 10],
      style_image: [0, 4],
    },
    attestationKeys: COMMON_ATTESTATIONS,
    mechanicsRequired: true,
  },
});
const EXPECTED_PREPARE_CONTRACT = deepFreeze({
  server_resolved_recipe: true,
  server_resolved_source: true,
  browser_hashes_accepted: false,
  browser_source_binding_accepted: false,
  mechanics_text_is_proposal_until_spec_approval: true,
  provider_call_started: false,
  paid_start_integrated: false,
  automatic_approval: false,
});

class StrategySpecContractError extends Error {
  constructor(code, field) {
    super(code);
    this.name = "StrategySpecContractError";
    this.code = code;
    this.field = field;
  }
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function exactObject(value, keys, field) {
  if (!isPlainObject(value)) {
    throw new StrategySpecContractError("object_required", field);
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length
    || actual.some((key, index) => key !== expected[index])
  ) {
    throw new StrategySpecContractError("object_keys_mismatch", field);
  }
  return value;
}

function onlyObjectKeys(value, keys, requiredKeys, field) {
  if (!isPlainObject(value)) {
    throw new StrategySpecContractError("object_required", field);
  }
  if (
    Object.keys(value).some((key) => !keys.includes(key))
    || requiredKeys.some((key) => !hasOwn(value, key))
  ) {
    throw new StrategySpecContractError("object_keys_mismatch", field);
  }
  return value;
}

function exactText(value, field, minLength, maxLength) {
  if (typeof value !== "string" || value !== value.trim()) {
    throw new StrategySpecContractError("text_not_canonical", field);
  }
  if (
    value.length < minLength
    || value.length > maxLength
    || CONTROL_PATTERN.test(value)
  ) {
    throw new StrategySpecContractError("text_invalid", field);
  }
  return value;
}

function proposedText(value, field, minLength, maxLength) {
  if (typeof value !== "string") {
    throw new StrategySpecContractError("text_required", field);
  }
  const normalized = value.trim();
  if (
    normalized.length < minLength
    || normalized.length > maxLength
    || CONTROL_PATTERN.test(normalized)
  ) {
    throw new StrategySpecContractError("text_invalid", field);
  }
  return normalized;
}

function exactCode(value, field) {
  const normalized = exactText(value, field, 1, 128);
  if (!/^[a-z0-9][a-z0-9_.-]{0,127}$/u.test(normalized)) {
    throw new StrategySpecContractError("code_invalid", field);
  }
  return normalized;
}

function exactUuid(value, field) {
  const normalized = exactText(value, field, 36, 36);
  if (!UUID_PATTERN.test(normalized) || normalized === "00000000-0000-0000-0000-000000000000") {
    throw new StrategySpecContractError("uuid_invalid", field);
  }
  return normalized;
}

function exactSha256(value, field) {
  const normalized = exactText(value, field, 64, 64);
  if (!SHA256_PATTERN.test(normalized)) {
    throw new StrategySpecContractError("sha256_invalid", field);
  }
  return normalized;
}

function exactBoolean(value, field) {
  if (typeof value !== "boolean") {
    throw new StrategySpecContractError("boolean_required", field);
  }
  return value;
}

function safeInteger(value, field, min, max) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new StrategySpecContractError("integer_invalid", field);
  }
  return value;
}

function positiveNumber(value, field, max = 3_600) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0 || value > max) {
    throw new StrategySpecContractError("number_invalid", field);
  }
  return value;
}

function exactTimestamp(value, field) {
  const normalized = exactText(value, field, 20, 80);
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u.test(normalized)
    || !Number.isFinite(Date.parse(normalized))
  ) {
    throw new StrategySpecContractError("timestamp_invalid", field);
  }
  return normalized;
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => (
      `${JSON.stringify(key)}:${stableStringify(value[key])}`
    )).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sameValue(left, right) {
  return stableStringify(left) === stableStringify(right);
}

function valueResult(normalizer, raw, expected = undefined) {
  try {
    return deepFreeze({
      ok: true,
      value: normalizer(raw, expected),
      error: null,
    });
  } catch (error) {
    const known = error instanceof StrategySpecContractError;
    return deepFreeze({
      ok: false,
      value: null,
      error: {
        code: known ? error.code : "generation_strategy_spec_contract_invalid",
        field: known ? error.field : "generation_strategy_spec",
      },
    });
  }
}

function requestResult(builder, raw) {
  try {
    return deepFreeze({ ok: true, request: builder(raw), error: null });
  } catch (error) {
    const known = error instanceof StrategySpecContractError;
    return deepFreeze({
      ok: false,
      request: null,
      error: {
        code: known ? error.code : "generation_strategy_spec_request_invalid",
        field: known ? error.field : "request",
      },
    });
  }
}

function normalizeMechanics(value, strategyId, field = "mechanics_summary") {
  const rules = STRATEGY_RULES[strategyId];
  if (!rules) throw new StrategySpecContractError("strategy_unknown", "strategy_id");
  if (!rules.mechanicsRequired) {
    if (value !== null) {
      throw new StrategySpecContractError("mechanics_must_be_null", field);
    }
    return null;
  }
  const source = exactObject(value, MECHANICS_KEYS, field);
  if (source.version !== GENERATION_STRATEGY_SPEC_MECHANICS_VERSION) {
    throw new StrategySpecContractError("mechanics_version_invalid", `${field}.version`);
  }
  if (!Array.isArray(source.beat_sequence) || source.beat_sequence.length < 2 || source.beat_sequence.length > 6) {
    throw new StrategySpecContractError("mechanics_beats_invalid", `${field}.beat_sequence`);
  }
  const beats = source.beat_sequence.map((beat, index) => proposedText(
    beat,
    `${field}.beat_sequence.${index}`,
    12,
    120,
  ));
  if (new Set(beats).size !== beats.length) {
    throw new StrategySpecContractError("mechanics_beats_duplicate", `${field}.beat_sequence`);
  }
  const normalized = {
    version: GENERATION_STRATEGY_SPEC_MECHANICS_VERSION,
    hook: proposedText(source.hook, `${field}.hook`, 20, 160),
    beat_sequence: beats,
    pacing: proposedText(source.pacing, `${field}.pacing`, 8, 100),
    camera_language: proposedText(
      source.camera_language,
      `${field}.camera_language`,
      8,
      100,
    ),
    composition: proposedText(source.composition, `${field}.composition`, 8, 100),
    audio_pattern: proposedText(source.audio_pattern, `${field}.audio_pattern`, 8, 100),
    cta_pattern: proposedText(source.cta_pattern, `${field}.cta_pattern`, 8, 100),
  };
  if (JSON.stringify(normalized).length > 4_096) {
    throw new StrategySpecContractError("mechanics_too_large", field);
  }
  return normalized;
}

export function normalizeGenerationStrategySpecMechanics(value, strategyId) {
  return valueResult((raw) => normalizeMechanics(raw, strategyId), value);
}

function normalizeSelectionAsset(value, strategyId, index) {
  const field = `selection.assets.${index}`;
  if (!isPlainObject(value)) {
    throw new StrategySpecContractError("object_required", field);
  }
  const role = exactCode(value.role, `${field}.role`);
  const mediaId = exactUuid(value.media_id, `${field}.media_id`);
  if (role === "source_video") {
    const keys = hasOwn(value, "duration_seconds")
      ? ["role", "media_id", "duration_seconds"]
      : ["role", "media_id"];
    exactObject(value, keys, field);
    // Длительность исходника обязательна обеим правкам готового видео.
    // Сервер требует её и у «Дуэта» (duration_source = 'source_video' в
    // строке реестра), а браузер её не просил — запуск обрывался
    // на generation_strategy_source_duration_mismatch.
    const durationBounds = SOURCE_DURATION_BOUNDS[strategyId] ?? null;
    if (durationBounds !== null && !hasOwn(value, "duration_seconds")) {
      throw new StrategySpecContractError("source_duration_required", field);
    }
    const duration = hasOwn(value, "duration_seconds")
      ? positiveNumber(value.duration_seconds, `${field}.duration_seconds`)
      : null;
    if (
      durationBounds !== null &&
      (duration < durationBounds.minimum || duration > durationBounds.maximum)
    ) {
      throw new StrategySpecContractError("source_duration_unsupported", field);
    }
    return {
      role,
      media_id: mediaId,
      ...(duration === null ? {} : { duration_seconds: duration }),
    };
  }
  if (role === "new_product_image") {
    const keys = hasOwn(value, "view")
      ? ["role", "media_id", "view"]
      : ["role", "media_id"];
    exactObject(value, keys, field);
    const view = hasOwn(value, "view")
      ? exactCode(value.view, `${field}.view`)
      : null;
    if (view !== null && !["front", "side", "back"].includes(view)) {
      throw new StrategySpecContractError("asset_view_invalid", `${field}.view`);
    }
    return { role, media_id: mediaId, ...(view === null ? {} : { view }) };
  }
  exactObject(value, ["role", "media_id"], field);
  return { role, media_id: mediaId };
}

function normalizeSelection(value, field = "selection") {
  if (!isPlainObject(value)) {
    throw new StrategySpecContractError("object_required", field);
  }
  const strategyId = exactCode(value.strategy_id, `${field}.strategy_id`);
  const rules = STRATEGY_RULES[strategyId];
  if (!rules) throw new StrategySpecContractError("strategy_unknown", `${field}.strategy_id`);
  const dimensionKey = rules.dimension;
  exactObject(value, [
    "version",
    "strategy_id",
    "recipe_version",
    "duration_seconds",
    dimensionKey,
    "audio",
    "assets",
    "attestations",
  ], field);
  if (value.version !== CATALOG_VERSION || value.recipe_version !== RECIPE_VERSION) {
    throw new StrategySpecContractError("selection_version_invalid", field);
  }
  // Предел — свойство стратегии: у «Дуэта» он 3–60 по строке реестра, у
  // остальных прежние 4–15.
  const durationSeconds = safeInteger(
    value.duration_seconds,
    `${field}.duration_seconds`,
    rules.duration?.minimum ?? 4,
    rules.duration?.maximum ?? 15,
  );
  const dimension = exactText(value[dimensionKey], `${field}.${dimensionKey}`, 1, 32);
  if (!hasOwn(rules.dimensions, dimension)) {
    throw new StrategySpecContractError("selection_dimension_invalid", `${field}.${dimensionKey}`);
  }
  const audio = exactBoolean(value.audio, `${field}.audio`);
  // Нижняя граница — один ассет: у «Дуэта» в выборе ровно один исходник.
  // Точный состав ролей каждой стратегии проверяется ниже счётчиком —
  // здесь только защита от пустого и непомерного набора.
  if (!Array.isArray(value.assets) || value.assets.length < 1 || value.assets.length > 15) {
    throw new StrategySpecContractError("selection_assets_invalid", `${field}.assets`);
  }
  const assets = value.assets.map((asset, index) => (
    normalizeSelectionAsset(asset, strategyId, index)
  ));
  if (new Set(assets.map((asset) => asset.media_id)).size !== assets.length) {
    throw new StrategySpecContractError("selection_media_duplicate", `${field}.assets`);
  }
  const counts = Object.fromEntries(Object.keys(rules.roles).map((role) => [role, 0]));
  for (const asset of assets) {
    if (!hasOwn(rules.roles, asset.role)) {
      throw new StrategySpecContractError("selection_role_invalid", `${field}.assets`);
    }
    counts[asset.role] += 1;
  }
  for (const [role, [minimum, maximum]] of Object.entries(rules.roles)) {
    if (counts[role] < minimum || counts[role] > maximum) {
      throw new StrategySpecContractError("selection_role_count_invalid", `${field}.assets.${role}`);
    }
  }
  const attestations = exactObject(
    value.attestations,
    rules.attestationKeys,
    `${field}.attestations`,
  );
  const normalizedAttestations = Object.fromEntries(
    rules.attestationKeys.map((key) => {
      if (attestations[key] !== true) {
        throw new StrategySpecContractError("attestation_required", `${field}.attestations.${key}`);
      }
      return [key, true];
    }),
  );
  return {
    version: CATALOG_VERSION,
    strategy_id: strategyId,
    recipe_version: RECIPE_VERSION,
    duration_seconds: durationSeconds,
    [dimensionKey]: dimension,
    audio,
    assets,
    attestations: normalizedAttestations,
  };
}

function normalizePrepareRequest(value, field = "request") {
  const source = exactObject(value, prepareKeysFor(value, true), field);
  if (source.version !== GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_VERSION) {
    throw new StrategySpecContractError("prepare_version_invalid", `${field}.version`);
  }
  const selection = normalizeSelection(source.selection, `${field}.selection`);
  const mechanics = normalizeMechanics(
    source.mechanics_summary,
    selection.strategy_id,
    `${field}.mechanics_summary`,
  );
  const platform = exactCode(source.platform, `${field}.platform`);
  const category = exactCode(source.product_category, `${field}.product_category`);
  if (!PLATFORMS.has(platform)) {
    throw new StrategySpecContractError("platform_invalid", `${field}.platform`);
  }
  if (!PRODUCT_CATEGORIES.has(category)) {
    throw new StrategySpecContractError("product_category_invalid", `${field}.product_category`);
  }
  if (source.confirmation !== true) {
    throw new StrategySpecContractError("human_confirmation_required", `${field}.confirmation`);
  }
  const idempotencyKey = exactText(source.idempotency_key, `${field}.idempotency_key`, 8, 120);
  if (!IDEMPOTENCY_PATTERN.test(idempotencyKey)) {
    throw new StrategySpecContractError("idempotency_key_invalid", `${field}.idempotency_key`);
  }
  const duet = selection.strategy_id === DUET_PRODUCT_STRATEGY;
  return {
    version: GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_VERSION,
    organization_id: exactUuid(source.organization_id, `${field}.organization_id`),
    project_id: exactUuid(source.project_id, `${field}.project_id`),
    // Товар только у «Дуэта»: состав ключей уже проверен выше по стратегии,
    // здесь остаётся назвать его точным идентификатором.
    ...(duet
      ? { product_id: exactUuid(source.product_id, `${field}.product_id`) }
      : {}),
    platform,
    product_category: category,
    selection,
    editable_intent: proposedText(source.editable_intent, `${field}.editable_intent`, 1, 800),
    proposed_prompt: proposedText(source.proposed_prompt, `${field}.proposed_prompt`, 1, 1_200),
    mechanics_summary: mechanics,
    confirmation: true,
    reason: proposedText(source.reason, `${field}.reason`, 3, 500),
    idempotency_key: idempotencyKey,
  };
}

function createPrepareRequest(value) {
  const source = exactObject(value, prepareKeysFor(value, false), "input");
  return normalizePrepareRequest({
    version: GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_VERSION,
    ...source,
  });
}

export function buildGenerationStrategySpecPrepareRequest(input = {}) {
  return requestResult(createPrepareRequest, input);
}

function normalizeAssetSnapshot(value, selection, field = "exact_scope.asset_snapshot") {
  if (!Array.isArray(value) || value.length !== selection.assets.length) {
    throw new StrategySpecContractError("asset_snapshot_length_invalid", field);
  }
  const normalized = value.map((entry, index) => {
    const itemField = `${field}.${index}`;
    const source = exactObject(entry, ASSET_SNAPSHOT_KEYS, itemField);
    const selected = selection.assets[index];
    const role = exactCode(source.selection_role, `${itemField}.selection_role`);
    const ordinal = safeInteger(
      source.selection_ordinal,
      `${itemField}.selection_ordinal`,
      1,
      15,
    );
    const mediaId = exactUuid(source.media_id, `${itemField}.media_id`);
    const kind = exactCode(source.kind, `${itemField}.kind`);
    const mimeType = exactText(source.mime_type, `${itemField}.mime_type`, 5, 100);
    const productId = source.product_id === null
      ? null
      : exactUuid(source.product_id, `${itemField}.product_id`);
    if (
      ordinal !== index + 1
      || role !== selected.role
      || mediaId !== selected.media_id
      || source.rights_confirmed !== true
    ) {
      throw new StrategySpecContractError("asset_snapshot_selection_mismatch", itemField);
    }
    const imageRole = role !== "source_video";
    if (
      (role === "source_video" && (kind !== "source_video" || mimeType !== "video/mp4"))
      || (imageRole && !IMAGE_MIMES.has(mimeType))
      || (["product_image", "new_product_image"].includes(role)
        && !["product_photo", "packshot"].includes(kind))
      || (["avatar_image", "original_product_image", "style_image"].includes(role)
        && kind !== "creator_reference")
    ) {
      throw new StrategySpecContractError("asset_snapshot_media_invalid", itemField);
    }
    if (["product_image", "new_product_image"].includes(role) && productId === null) {
      throw new StrategySpecContractError("asset_snapshot_product_required", itemField);
    }
    return {
      selection_role: role,
      selection_ordinal: ordinal,
      media_id: mediaId,
      sha256: exactSha256(source.sha256, `${itemField}.sha256`),
      kind,
      mime_type: mimeType,
      product_id: productId,
      rights_confirmed: true,
    };
  });
  const targetProducts = normalized
    .filter((asset) => ["product_image", "new_product_image"].includes(
      asset.selection_role,
    ))
    .map((asset) => asset.product_id);
  // Все товарные фотографии обязаны принадлежать ОДНОМУ товару — иначе в один
  // ролик собрали бы разные изделия. Но проверять это имеет смысл только там,
  // где товарные фотографии есть: у «Аватара» их нет вовсе с 22.08.2026, и
  // пустой набор нарушить правило не может. Требовать «ровно один товар» от
  // стратегии без товара значило бы запретить её саму.
  if (targetProducts.length && new Set(targetProducts).size !== 1) {
    throw new StrategySpecContractError("asset_snapshot_product_mismatch", field);
  }
  return normalized;
}

function normalizeSourceSnapshot(value, selection, assets, field = "exact_scope.source") {
  const source = exactObject(value, SOURCE_KEYS, field);
  if (source.version !== SOURCE_VERSION) {
    throw new StrategySpecContractError("source_version_invalid", `${field}.version`);
  }
  const sourceSelection = selection.assets.find((asset) => asset.role === "source_video");
  const sourceAsset = assets.find((asset) => asset.selection_role === "source_video");
  const duration = source.duration_seconds === null
    ? null
    : positiveNumber(source.duration_seconds, `${field}.duration_seconds`);
  const mediaObjectId = exactUuid(source.media_object_id, `${field}.media_object_id`);
  const mediaSha256 = exactSha256(source.media_sha256, `${field}.media_sha256`);
  if (
    !sourceSelection
    || !sourceAsset
    || mediaObjectId !== sourceSelection.media_id
    || mediaObjectId !== sourceAsset.media_id
    || mediaSha256 !== sourceAsset.sha256
  ) {
    throw new StrategySpecContractError("source_asset_mismatch", field);
  }
  if (
    selection.strategy_id === "viral_product_swap"
    && (duration === null || duration !== sourceSelection.duration_seconds)
  ) {
    throw new StrategySpecContractError("source_duration_mismatch", `${field}.duration_seconds`);
  }
  return {
    version: SOURCE_VERSION,
    attachment_id: exactUuid(source.attachment_id, `${field}.attachment_id`),
    attachment_hash: exactSha256(
      source.attachment_hash,
      `${field}.attachment_hash`,
    ),
    source_id: exactUuid(source.source_id, `${field}.source_id`),
    source_hash: exactSha256(source.source_hash, `${field}.source_hash`),
    media_object_id: mediaObjectId,
    media_sha256: mediaSha256,
    size_bytes: safeInteger(source.size_bytes, `${field}.size_bytes`, 1, Number.MAX_SAFE_INTEGER),
    duration_seconds: duration,
  };
}

function normalizeMechanicsSnapshot(
  value,
  mechanicsHash,
  selection,
  source,
  field = "exact_scope.mechanics",
) {
  const rules = STRATEGY_RULES[selection.strategy_id];
  if (!rules.mechanicsRequired) {
    if (value !== null || mechanicsHash !== null) {
      throw new StrategySpecContractError("mechanics_snapshot_must_be_null", field);
    }
    return { mechanics: null, mechanicsHash: null };
  }
  const snapshot = exactObject(value, MECHANICS_SNAPSHOT_KEYS, field);
  const normalizedHash = exactSha256(mechanicsHash, "exact_scope.mechanics_hash");
  if (
    snapshot.version !== MECHANICS_SNAPSHOT_VERSION
    || snapshot.strategy_id !== selection.strategy_id
    || snapshot.review_confirmation !== true
  ) {
    throw new StrategySpecContractError("mechanics_snapshot_invalid", field);
  }
  const attachmentId = exactUuid(
    snapshot.source_attachment_id,
    `${field}.source_attachment_id`,
  );
  const attachmentHash = exactSha256(
    snapshot.source_attachment_hash,
    `${field}.source_attachment_hash`,
  );
  const mediaId = exactUuid(snapshot.source_media_id, `${field}.source_media_id`);
  const mediaHash = exactSha256(
    snapshot.source_media_sha256,
    `${field}.source_media_sha256`,
  );
  if (
    attachmentId !== source.attachment_id
    || attachmentHash !== source.attachment_hash
    || mediaId !== source.media_object_id
    || mediaHash !== source.media_sha256
  ) {
    throw new StrategySpecContractError("mechanics_source_mismatch", field);
  }
  return {
    mechanics: {
      version: MECHANICS_SNAPSHOT_VERSION,
      strategy_id: selection.strategy_id,
      source_attachment_id: attachmentId,
      source_attachment_hash: attachmentHash,
      source_media_id: mediaId,
      source_media_sha256: mediaHash,
      summary: normalizeMechanics(
        snapshot.summary,
        selection.strategy_id,
        `${field}.summary`,
      ),
      reviewed_by: exactUuid(snapshot.reviewed_by, `${field}.reviewed_by`),
      review_confirmation: true,
    },
    mechanicsHash: normalizedHash,
  };
}

function normalizeRoutePolicy(value, field) {
  const source = exactObject(value, ROUTE_POLICY_KEYS, field);
  if (
    source.version !== ROUTE_POLICY.version
    || source.authority !== ROUTE_POLICY.authority
    || source.binding !== ROUTE_POLICY.binding
  ) {
    throw new StrategySpecContractError("strategy_route_policy_invalid", field);
  }
  return ROUTE_POLICY;
}

function normalizeStrategyScope(value, field = "generation_spec.exact_scope") {
  if (!isPlainObject(value)) {
    throw new StrategySpecContractError("object_required", field);
  }
  const legacy = value.version === GENERATION_STRATEGY_SPEC_LEGACY_SCOPE_VERSION;
  const source = exactObject(value, legacy ? LEGACY_SCOPE_KEYS : SCOPE_KEYS, field);
  if (
    (!legacy && source.version !== GENERATION_STRATEGY_SPEC_SCOPE_VERSION)
    || source.authority_kind !== "strategy_recipe"
    || (legacy && source.provider !== "runway")
  ) {
    throw new StrategySpecContractError("strategy_scope_identity_invalid", field);
  }
  // Scope v1 stored a Runway-era implementation hint as if it were the
  // execution provider. The provider was never part of the approved recipe:
  // the paid preflight resolves an engine from the server route registry and
  // binds it into the signed readiness receipt/runtime fingerprint. Preserve
  // old approved specs, but normalize that legacy hint to the same deferred,
  // provider-neutral policy emitted by scope v2.
  const routePolicy = legacy
    ? ROUTE_POLICY
    : normalizeRoutePolicy(source.route_policy, `${field}.route_policy`);
  const selection = normalizeSelection(source.selection, `${field}.selection`);
  const rules = STRATEGY_RULES[selection.strategy_id];
  const strategyId = exactCode(source.strategy_id, `${field}.strategy_id`);
  const dimension = selection[rules.dimension];
  const expectedResolution = rules.dimension === "resolution"
    ? dimension
    : rules.dimensions[dimension];
  const expectedRatio = rules.dimension === "resolution" ? "source" : dimension;
  if (
    strategyId !== selection.strategy_id
    || source.recipe !== rules.recipe
    || source.input_mode !== rules.inputMode
    || source.duration_seconds !== selection.duration_seconds
    || source.resolution !== expectedResolution
    || source.ratio !== expectedRatio
    || source.format !== expectedRatio
    || source.audio !== selection.audio
    || source.spoken_dialogue !== false
    || source.reference_count !== selection.assets.length - 1
    // Признак берётся по рецепту, а не по литералу стратегии: следующая правка
    // видео добавляется в набор, а не новым сравнением.
    || source.reference_video !== PROVIDER_SOURCE_INPUT_RECIPES.has(rules.recipe)
    || source.first_frame !== false
    || source.last_frame !== false
  ) {
    throw new StrategySpecContractError("strategy_scope_output_mismatch", field);
  }
  if (!PLATFORMS.has(source.platform) || !PRODUCT_CATEGORIES.has(source.product_category)) {
    throw new StrategySpecContractError("strategy_scope_taxonomy_invalid", field);
  }
  // Цель работы — то, ПРО ЧТО делается ролик. У «Копии» и «Создания» это товар,
  // у «Аватара» с 22.08.2026 — персонаж: товара у него нет вовсе.
  const targetMediaIds = selection.assets
    .filter((asset) => rules.targetRoles.includes(asset.role))
    .map((asset) => asset.media_id);
  const mediaIds = Array.isArray(source.media_ids)
    ? source.media_ids.map((mediaId, index) => exactUuid(
      mediaId,
      `${field}.media_ids.${index}`,
    ))
    : [];
  const expectedMediaIds = targetMediaIds.slice(0, 5);
  // Цели может не быть вовсе: «Аватара» задают ЛИБО фотографией, либо
  // описанием, и во втором случае медиа-объекта, про который делается ролик, не
  // существует. Тогда сервер кладёт null — и это правда, а не пропущенная
  // проверка: сам состав ассетов проверяется отдельно счётчиком ролей.
  const primaryMediaId = targetMediaIds.length
    ? exactUuid(source.primary_media_id, `${field}.primary_media_id`)
    : source.primary_media_id ?? null;
  if (
    primaryMediaId !== (targetMediaIds[0] ?? null)
    || !sameValue(mediaIds, expectedMediaIds)
  ) {
    throw new StrategySpecContractError("strategy_scope_media_mismatch", field);
  }
  const selectionHash = exactSha256(source.selection_hash, `${field}.selection_hash`);
  const assetSnapshot = normalizeAssetSnapshot(
    source.asset_snapshot,
    selection,
    `${field}.asset_snapshot`,
  );
  const assetSnapshotHash = exactSha256(
    source.asset_snapshot_hash,
    `${field}.asset_snapshot_hash`,
  );
  const sourceSnapshot = normalizeSourceSnapshot(
    source.source,
    selection,
    assetSnapshot,
    `${field}.source`,
  );
  const sourceHash = exactSha256(source.source_hash, `${field}.source_hash`);
  const mechanics = normalizeMechanicsSnapshot(
    source.mechanics,
    source.mechanics_hash,
    selection,
    sourceSnapshot,
    `${field}.mechanics`,
  );
  return {
    // Canonical client representation is always v2. This makes subsequent
    // local validation unambiguous: a v1-shaped object without its historical
    // provider field is never accepted as wire data.
    version: GENERATION_STRATEGY_SPEC_SCOPE_VERSION,
    authority_kind: "strategy_recipe",
    primary_media_id: primaryMediaId,
    media_ids: mediaIds,
    platform: source.platform,
    route_policy: routePolicy,
    strategy_id: strategyId,
    recipe: rules.recipe,
    input_mode: rules.inputMode,
    duration_seconds: selection.duration_seconds,
    product_category: source.product_category,
    format: expectedRatio,
    ratio: expectedRatio,
    resolution: expectedResolution,
    audio: selection.audio,
    spoken_dialogue: false,
    reference_count: selection.assets.length - 1,
    // Тот же признак, что и в сверке выше: собранное и проверяемое обязаны
    // считаться одним выражением, иначе повторная сверка падает сама об себя.
    reference_video: PROVIDER_SOURCE_INPUT_RECIPES.has(rules.recipe),
    first_frame: false,
    last_frame: false,
    selection,
    selection_hash: selectionHash,
    asset_snapshot: assetSnapshot,
    asset_snapshot_hash: assetSnapshotHash,
    source: sourceSnapshot,
    source_hash: sourceHash,
    mechanics: mechanics.mechanics,
    mechanics_hash: mechanics.mechanicsHash,
  };
}

function normalizeSpecDocument(value, expectedStatus, field = "generation_spec") {
  const source = onlyObjectKeys(
    value,
    [...SPEC_REQUIRED_KEYS, ...SPEC_OPTIONAL_KEYS],
    SPEC_REQUIRED_KEYS,
    field,
  );
  const status = exactCode(source.status, `${field}.status`);
  if (status !== expectedStatus) {
    throw new StrategySpecContractError("spec_status_invalid", `${field}.status`);
  }
  const hasApprovedAt = hasOwn(source, "approved_at");
  if ((status === "approved") !== hasApprovedAt) {
    throw new StrategySpecContractError("spec_approval_timestamp_invalid", field);
  }
  if (
    source.research_provenance !== null
    || source.performance_policy_provenance !== null
    || source.repair_provenance !== null
    || source.outcome_selection_id !== null
  ) {
    throw new StrategySpecContractError("spec_provenance_unexpected", field);
  }
  const normalized = {
    spec_id: exactUuid(source.spec_id, `${field}.spec_id`),
    spec_version: safeInteger(source.spec_version, `${field}.spec_version`, 1, 100_000),
    spec_hash: exactSha256(source.spec_hash, `${field}.spec_hash`),
    status,
    exact_scope: normalizeStrategyScope(source.exact_scope, `${field}.exact_scope`),
    editable_intent: exactText(source.editable_intent, `${field}.editable_intent`, 1, 800),
    compiled_prompt: exactText(source.compiled_prompt, `${field}.compiled_prompt`, 1, 1_200),
    prompt_hash: exactSha256(source.prompt_hash, `${field}.prompt_hash`),
    research_provenance: null,
    performance_policy_provenance: null,
    repair_provenance: null,
    outcome_selection_id: null,
    created_at: exactTimestamp(source.created_at, `${field}.created_at`),
    updated_at: exactTimestamp(source.updated_at, `${field}.updated_at`),
  };
  if (hasApprovedAt) {
    normalized.approved_at = exactTimestamp(
      source.approved_at,
      `${field}.approved_at`,
    );
  }
  return normalized;
}

function normalizeAction(value, expectedAction, expectedCode, field) {
  const source = exactObject(value, ACTION_KEYS, field);
  const code = exactCode(source.code, `${field}.code`);
  const action = exactCode(source.action, `${field}.action`);
  if (
    code !== expectedCode
    || action !== expectedAction
    || source.requires_confirmation !== true
    || source.provider_action !== false
    || source.spend_action !== false
  ) {
    throw new StrategySpecContractError("recommended_action_invalid", field);
  }
  return {
    code,
    action,
    label: exactText(source.label, `${field}.label`, 2, 120),
    reason: exactText(source.reason, `${field}.reason`, 3, 500),
    requires_confirmation: true,
    provider_action: false,
    spend_action: false,
  };
}

function unwrapResponse(raw) {
  return isPlainObject(raw?.data) ? raw.data : raw;
}

function normalizeExpectedRequest(expected) {
  const candidate = expected?.ok === true && expected.request
    ? expected.request
    : expected;
  return normalizePrepareRequest(candidate, "expected_request");
}

function normalizePrepareResponse(raw, expected) {
  const expectedRequest = normalizeExpectedRequest(expected);
  const source = exactObject(
    unwrapResponse(raw),
    PREPARE_RESPONSE_KEYS,
    "prepare_response",
  );
  if (
    source.ok !== true
    || source.version !== GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION
  ) {
    throw new StrategySpecContractError("prepare_response_identity_invalid", "prepare_response");
  }
  const spec = normalizeSpecDocument(source.generation_spec, "draft");
  if (spec.spec_version !== 1) {
    throw new StrategySpecContractError("independent_spec_required", "generation_spec.spec_version");
  }
  if (!Array.isArray(source.history) || source.history.length !== 1) {
    throw new StrategySpecContractError("prepare_history_invalid", "prepare_response.history");
  }
  const historySpec = normalizeSpecDocument(source.history[0], "draft", "history.0");
  if (!sameValue(spec, historySpec)) {
    throw new StrategySpecContractError("prepare_history_mismatch", "prepare_response.history");
  }
  const scope = spec.exact_scope;
  if (
    !sameValue(scope.selection, expectedRequest.selection)
    || scope.platform !== expectedRequest.platform
    || scope.product_category !== expectedRequest.product_category
    || spec.editable_intent !== expectedRequest.editable_intent
    || spec.compiled_prompt !== expectedRequest.proposed_prompt
    || !sameValue(scope.mechanics?.summary ?? null, expectedRequest.mechanics_summary)
  ) {
    throw new StrategySpecContractError("prepare_response_request_mismatch", "prepare_response");
  }
  const action = normalizeAction(
    source.recommended_next_action,
    "approve",
    "review_and_approve_generation_spec",
    "prepare_response.recommended_next_action",
  );
  const strategy = exactObject(
    source.strategy,
    STRATEGY_RESPONSE_KEYS,
    "prepare_response.strategy",
  );
  const rules = STRATEGY_RULES[scope.strategy_id];
  const mechanicsHash = scope.mechanics_hash;
  if (
    strategy.strategy_id !== scope.strategy_id
    || strategy.recipe !== scope.recipe
    || strategy.selection_hash !== scope.selection_hash
    || strategy.source_media_id !== scope.source.media_object_id
    || strategy.source_snapshot_hash !== scope.source_hash
    || strategy.mechanics_required !== rules.mechanicsRequired
    || strategy.mechanics_snapshot_hash !== mechanicsHash
    || strategy.human_approval_required !== true
  ) {
    throw new StrategySpecContractError("prepare_strategy_mismatch", "prepare_response.strategy");
  }
  exactSha256(strategy.selection_hash, "prepare_response.strategy.selection_hash");
  exactUuid(strategy.source_media_id, "prepare_response.strategy.source_media_id");
  exactSha256(
    strategy.source_snapshot_hash,
    "prepare_response.strategy.source_snapshot_hash",
  );
  if (strategy.mechanics_snapshot_hash !== null) {
    exactSha256(
      strategy.mechanics_snapshot_hash,
      "prepare_response.strategy.mechanics_snapshot_hash",
    );
  }
  const contract = exactObject(
    source.contract,
    CONTRACT_KEYS,
    "prepare_response.contract",
  );
  if (!sameValue(contract, EXPECTED_PREPARE_CONTRACT)) {
    throw new StrategySpecContractError("prepare_contract_invalid", "prepare_response.contract");
  }
  return {
    version: GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION,
    organization_id: expectedRequest.organization_id,
    project_id: expectedRequest.project_id,
    generationSpec: spec,
    history: [historySpec],
    recommendedNextAction: action,
    strategy: {
      strategy_id: scope.strategy_id,
      recipe: scope.recipe,
      selection_hash: scope.selection_hash,
      source_media_id: scope.source.media_object_id,
      source_snapshot_hash: scope.source_hash,
      mechanics_required: rules.mechanicsRequired,
      mechanics_snapshot_hash: mechanicsHash,
      human_approval_required: true,
    },
    contract: EXPECTED_PREPARE_CONTRACT,
  };
}

export function normalizeGenerationStrategySpecPrepareResponse(raw, expectedRequest) {
  return valueResult(normalizePrepareResponse, raw, expectedRequest);
}

function expectedDraftValue(value, field = "draft") {
  const candidate = value?.ok === true && value.value ? value.value : value;
  if (!isPlainObject(candidate)) {
    throw new StrategySpecContractError("normalized_draft_required", field);
  }
  exactObject(candidate, NORMALIZED_PREPARE_KEYS, field);
  if (candidate.version !== GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION) {
    throw new StrategySpecContractError("normalized_draft_required", field);
  }
  const organizationId = exactUuid(
    candidate.organization_id,
    `${field}.organization_id`,
  );
  const projectId = exactUuid(candidate.project_id, `${field}.project_id`);
  const spec = normalizeSpecDocument(
    candidate.generationSpec,
    "draft",
    `${field}.generationSpec`,
  );
  if (spec.spec_version !== 1) {
    throw new StrategySpecContractError("independent_spec_required", field);
  }
  if (!Array.isArray(candidate.history) || candidate.history.length !== 1) {
    throw new StrategySpecContractError("normalized_draft_history_invalid", field);
  }
  const historySpec = normalizeSpecDocument(
    candidate.history[0],
    "draft",
    `${field}.history.0`,
  );
  if (!sameValue(spec, historySpec)) {
    throw new StrategySpecContractError("normalized_draft_history_invalid", field);
  }
  normalizeAction(
    candidate.recommendedNextAction,
    "approve",
    "review_and_approve_generation_spec",
    `${field}.recommendedNextAction`,
  );
  const strategy = exactObject(
    candidate.strategy,
    STRATEGY_RESPONSE_KEYS,
    `${field}.strategy`,
  );
  const rules = STRATEGY_RULES[spec.exact_scope.strategy_id];
  if (
    strategy.strategy_id !== spec.exact_scope.strategy_id
    || strategy.recipe !== spec.exact_scope.recipe
    || strategy.selection_hash !== spec.exact_scope.selection_hash
    || strategy.source_media_id !== spec.exact_scope.source.media_object_id
    || strategy.source_snapshot_hash !== spec.exact_scope.source_hash
    || strategy.mechanics_required !== rules.mechanicsRequired
    || strategy.mechanics_snapshot_hash !== spec.exact_scope.mechanics_hash
    || strategy.human_approval_required !== true
  ) {
    throw new StrategySpecContractError("normalized_draft_strategy_invalid", field);
  }
  exactObject(candidate.contract, CONTRACT_KEYS, `${field}.contract`);
  if (!sameValue(candidate.contract, EXPECTED_PREPARE_CONTRACT)) {
    throw new StrategySpecContractError("normalized_draft_contract_invalid", field);
  }
  return { organizationId, projectId, spec };
}

function createApprovalRequest(value) {
  const source = exactObject(value, APPROVAL_INPUT_KEYS, "approval_input");
  const draft = expectedDraftValue(source.draft, "approval_input.draft");
  const projectId = exactUuid(source.project_id, "approval_input.project_id");
  if (projectId !== draft.projectId) {
    throw new StrategySpecContractError("approval_project_mismatch", "approval_input.project_id");
  }
  if (source.human_confirmation !== true) {
    throw new StrategySpecContractError(
      "human_approval_confirmation_required",
      "approval_input.human_confirmation",
    );
  }
  return {
    project_id: projectId,
    spec_id: draft.spec.spec_id,
    expected_spec_version: draft.spec.spec_version,
    expected_spec_hash: draft.spec.spec_hash,
    action: "approve",
    confirmation: true,
    reason: proposedText(source.reason, "approval_input.reason", 3, 500),
  };
}

export function buildGenerationStrategySpecApprovalRequest(input = {}) {
  return requestResult(createApprovalRequest, input);
}

function sameApprovedSpecIdentity(approved, draft) {
  return approved.spec_id === draft.spec_id
    && approved.spec_version === draft.spec_version
    && approved.spec_hash === draft.spec_hash
    && approved.prompt_hash === draft.prompt_hash
    && approved.created_at === draft.created_at
    && approved.editable_intent === draft.editable_intent
    && approved.compiled_prompt === draft.compiled_prompt
    && approved.research_provenance === null
    && approved.performance_policy_provenance === null
    && approved.repair_provenance === null
    && approved.outcome_selection_id === null
    && sameValue(approved.exact_scope, draft.exact_scope);
}

function approvedContext(draft, approved) {
  const scope = approved.exact_scope;
  return {
    organization_id: draft.organizationId,
    project_id: draft.projectId,
    spec_id: approved.spec_id,
    spec_version: approved.spec_version,
    spec_hash: approved.spec_hash,
    prompt_hash: approved.prompt_hash,
    status: "approved",
    strategy_id: scope.strategy_id,
    recipe: scope.recipe,
    selection_hash: scope.selection_hash,
    asset_snapshot_hash: scope.asset_snapshot_hash,
    source_media_id: scope.source.media_object_id,
    source_snapshot_hash: scope.source_hash,
    mechanics_snapshot_hash: scope.mechanics_hash,
    approved_at: approved.approved_at,
  };
}

function normalizeControlResponse(raw, expectedDraft) {
  const draft = expectedDraftValue(expectedDraft, "expected_draft");
  const source = exactObject(
    unwrapResponse(raw),
    CONTROL_RESPONSE_KEYS,
    "control_response",
  );
  if (
    source.ok !== true
    || source.version !== GENERATION_STRATEGY_SPEC_CONTROL_VERSION
    || source.automatic_approval !== false
    || source.automatic_spend !== false
    || source.automatic_generation !== false
  ) {
    throw new StrategySpecContractError("control_response_identity_invalid", "control_response");
  }
  const approved = normalizeSpecDocument(
    source.generation_spec,
    "approved",
    "control_response.generation_spec",
  );
  if (
    approved.updated_at !== approved.approved_at
    || Date.parse(approved.approved_at) < Date.parse(approved.created_at)
    || !sameApprovedSpecIdentity(approved, draft.spec)
  ) {
    throw new StrategySpecContractError(
      "approved_spec_identity_mismatch",
      "control_response.generation_spec",
    );
  }
  if (!Array.isArray(source.history) || source.history.length !== 1) {
    throw new StrategySpecContractError("control_history_invalid", "control_response.history");
  }
  const historySpec = normalizeSpecDocument(
    source.history[0],
    "approved",
    "control_response.history.0",
  );
  if (!sameValue(approved, historySpec)) {
    throw new StrategySpecContractError("control_history_mismatch", "control_response.history");
  }
  const action = normalizeAction(
    source.recommended_next_action,
    "confirm_spend",
    "confirm_spend_for_approved_spec",
    "control_response.recommended_next_action",
  );
  return {
    version: GENERATION_STRATEGY_SPEC_CONTROL_VERSION,
    approvedContext: approvedContext(draft, approved),
    recommendedNextAction: action,
    automaticApproval: false,
    automaticSpend: false,
    automaticGeneration: false,
  };
}

export function normalizeGenerationStrategySpecControlResponse(raw, expectedDraft) {
  return valueResult(normalizeControlResponse, raw, expectedDraft);
}

function identityFromValue(value) {
  const candidate = value?.ok === true && value.value ? value.value : value;
  if (isPlainObject(candidate?.approvedContext)) {
    const context = candidate.approvedContext;
    exactObject(context, APPROVED_CONTEXT_KEYS, "approvedContext");
    const strategyId = exactCode(context.strategy_id, "approvedContext.strategy_id");
    const rules = STRATEGY_RULES[strategyId];
    if (
      !rules
      || context.recipe !== rules.recipe
      || context.status !== "approved"
      || rules.mechanicsRequired !== (context.mechanics_snapshot_hash !== null)
    ) {
      throw new StrategySpecContractError(
        "approved_context_strategy_invalid",
        "approvedContext",
      );
    }
    exactTimestamp(context.approved_at, "approvedContext.approved_at");
    return {
      organization_id: exactUuid(context.organization_id, "approvedContext.organization_id"),
      project_id: exactUuid(context.project_id, "approvedContext.project_id"),
      spec_id: exactUuid(context.spec_id, "approvedContext.spec_id"),
      spec_version: safeInteger(context.spec_version, "approvedContext.spec_version", 1, 100_000),
      spec_hash: exactSha256(context.spec_hash, "approvedContext.spec_hash"),
      prompt_hash: exactSha256(context.prompt_hash, "approvedContext.prompt_hash"),
      status: "approved",
      strategy_id: strategyId,
      recipe: exactCode(context.recipe, "approvedContext.recipe"),
      selection_hash: exactSha256(context.selection_hash, "approvedContext.selection_hash"),
      asset_snapshot_hash: exactSha256(
        context.asset_snapshot_hash,
        "approvedContext.asset_snapshot_hash",
      ),
      source_media_id: exactUuid(context.source_media_id, "approvedContext.source_media_id"),
      source_snapshot_hash: exactSha256(
        context.source_snapshot_hash,
        "approvedContext.source_snapshot_hash",
      ),
      mechanics_snapshot_hash: context.mechanics_snapshot_hash === null
        ? null
        : exactSha256(
          context.mechanics_snapshot_hash,
          "approvedContext.mechanics_snapshot_hash",
        ),
    };
  }
  if (
    !isPlainObject(candidate)
    || candidate.version !== GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION
  ) {
    throw new StrategySpecContractError("normalized_spec_required", "value");
  }
  const draft = expectedDraftValue(candidate);
  const scope = draft.spec.exact_scope;
  return {
    organization_id: draft.organizationId,
    project_id: draft.projectId,
    spec_id: draft.spec.spec_id,
    spec_version: draft.spec.spec_version,
    spec_hash: draft.spec.spec_hash,
    prompt_hash: draft.spec.prompt_hash,
    status: "draft",
    strategy_id: scope.strategy_id,
    recipe: scope.recipe,
    selection_hash: scope.selection_hash,
    asset_snapshot_hash: scope.asset_snapshot_hash,
    source_media_id: scope.source.media_object_id,
    source_snapshot_hash: scope.source_hash,
    mechanics_snapshot_hash: scope.mechanics_hash,
  };
}

export function generationStrategySpecIdentity(value) {
  try {
    return deepFreeze(identityFromValue(value));
  } catch {
    return null;
  }
}

export function generationStrategySpecSafeProjection(value) {
  try {
    const identity = identityFromValue(value);
    const candidate = value?.ok === true && value.value ? value.value : value;
    if (isPlainObject(candidate?.approvedContext)) {
      return deepFreeze({
        version: GENERATION_STRATEGY_SPEC_CONTROL_VERSION,
        identity,
        human_approval_required: false,
        next_action: candidate.recommendedNextAction?.action || null,
      });
    }
    const draft = expectedDraftValue(candidate);
    const scope = draft.spec.exact_scope;
    return deepFreeze({
      version: GENERATION_STRATEGY_SPEC_PREPARE_RESPONSE_VERSION,
      identity,
      execution_route: scope.route_policy,
      output: {
        duration_seconds: scope.duration_seconds,
        ratio: scope.ratio,
        resolution: scope.resolution,
        audio: scope.audio,
        reference_count: scope.reference_count,
        reference_video: scope.reference_video,
      },
      human_approval_required: true,
      next_action: "approve",
    });
  } catch {
    return null;
  }
}
