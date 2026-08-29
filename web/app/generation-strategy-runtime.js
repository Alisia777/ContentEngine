/*
 * Pure browser state contract for the paid generation-strategy handshake.
 *
 * This module deliberately has no DOM, storage, network, or model-SKU
 * dependency. It accepts only versioned, exact-key server envelopes.
 * A local runtime fingerprint binds one project, one approved spec version,
 * and one complete strategy selection. The reducer stores the fingerprint and
 * a non-consent identity summary, never the raw selection or a user's spend
 * confirmation decision.
 */

export const GENERATION_STRATEGY_RUNTIME_VERSION = "2026-08-14.v1";

export const GENERATION_STRATEGY_RUNTIME_ACTIONS = Object.freeze({
  select: "SELECT",
  bindResolved: "BIND_RESOLVED",
  preflightResolved: "PREFLIGHT_RESOLVED",
  preflightRefreshRequested: "PREFLIGHT_REFRESH_REQUESTED",
  humanConfirmed: "HUMAN_CONFIRMED",
  startRequested: "START_REQUESTED",
  startResolved: "START_RESOLVED",
  statusResolved: "STATUS_RESOLVED",
  invalidate: "INVALIDATE",
  reset: "RESET",
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

// Пределы длительности ИСХОДНОГО ролика. Те же числа стоят в
// generation-strategy-spec.js: оба модуля чистые и ничего не импортируют,
// поэтому запись вторая, и разойтись они могут только молча.
const SOURCE_DURATION_BOUNDS = Object.freeze({
  viral_product_swap: Object.freeze({ minimum: 1.8, maximum: 15 }),
  viral_avatar_ugc: Object.freeze({ minimum: 1.8, maximum: 60 }),
});
const CODE_PATTERN = /^[a-z0-9][a-z0-9_.-]{0,127}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/u;
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const CATALOG_VERSION = "2026-08-14.v1";
const RECIPE_VERSION = "2026-06";
// Версия прайса зависит от маршрута: у Runway это ступени кредитов, у fal —
// фиксированная цена за ролик либо ставка за секунду. Набор повторяет
// ограничение базы на колонку pricing_version, поэтому пополняется только
// вместе с ним.
const PRICING_VERSIONS = Object.freeze([
  "runway-recipe-credits-2026-08-14.v1",
  "fal-usd-per-run-2026-08-18.v1",
  "fal-usd-per-second-2026-08-18.v1",
  // «Дуэт» считается посекундной ставкой ведущего. Своя версия прайса, а не
  // переиспользованная falовская: строка подтверждения траты несёт СПОСОБ
  // расчёта, и назвать чужой способ значило бы подписать не ту арифметику.
  "heygen-usd-per-second-2026-08-22.v1",
  // Движки «Копии», заведённые 23.08.2026 (миграция 202608230020). У каждого
  // своя версия прайса: пара (provider, pricing_version) — подпись маршрута.
  "fal-usd-per-second-kling-standard-2026-08-23.v1",
  "fal-usd-per-second-happy-horse-2026-08-23.v1",
  "fal-usd-per-second-bytedance-2-5-2026-08-23.v1",
  "fal-usd-per-second-minimax-h3-2026-08-23.v1",
  "fal-usd-per-second-grok-imagine-2026-08-23.v1",
  "fal-usd-per-second-happy-horse-reference-2026-08-23.v1",
  // «Создание» на Runway Gen-4 Turbo (29.08.2026): посекундная ставка
  // официального API (5 кредитов/с = $0.05/с), длительность только 5 или 10 с.
  "runway-usd-per-second-gen4-turbo-2026-08-29.v1",
]);

function knownPricingVersion(value) {
  return typeof value === "string" && PRICING_VERSIONS.includes(value);
}

// Тот же набор стоит в ограничении базы на колонку provider таблицы квитанций
// и в контракте edge. Расходиться им нельзя: иначе одна из сторон молча
// отвергает то, что другая считает верным.
const STRATEGY_PROVIDERS = Object.freeze(["runway", "fal", "heygen"]);

function knownStrategyProvider(value) {
  return typeof value === "string" && STRATEGY_PROVIDERS.includes(value);
}
const COMMON_ATTESTATION_KEYS = Object.freeze([
  "source_media_rights_confirmed",
  "transformative_use_confirmed",
  "product_assets_rights_confirmed",
  "depicted_people_consent_confirmed",
]);
const STRATEGY_RULES = deepFreeze({
  // «Дуэт»: исходник комментируется, а не переписывается, поэтому кадр задаёт он
  // сам — измерение разрешением. Ассет ровно один: ведущего даёт библиотека.
  viral_avatar_ugc: {
    recipe: "product_ugc",
    dimension: "resolution",
    dimensions: ["720p", "1080p"],
    // Длина дуэта задана комментируемым роликом, а не вкусом оператора:
    // типичная реклама длиннее пятнадцати секунд. Числа те же, что в строке
    // реестра маршрута heygen.
    duration: { minimum: 3, maximum: 60 },
    attestations: [
      ...COMMON_ATTESTATION_KEYS,
      "avatar_likeness_consent_confirmed",
    ],
    roles: {
      source_video: [1, 1],
    },
  },
  viral_product_swap: {
    recipe: "product_swap",
    dimension: "resolution",
    dimensions: ["720p", "1080p"],
    attestations: COMMON_ATTESTATION_KEYS,
    roles: {
      source_video: [1, 1],
      original_product_image: [1, 1],
      new_product_image: [1, 10],
    },
  },
  viral_rebuild: {
    recipe: "product_ad",
    dimension: "ratio",
    dimensions: [
      "1280:720",
      "720:1280",
      "960:960",
      "834:1112",
      "1920:1080",
      "1080:1920",
      "1440:1440",
      "1248:1664",
    ],
    attestations: COMMON_ATTESTATION_KEYS,
    roles: {
      source_video: [1, 1],
      product_image: [1, 10],
      style_image: [0, 4],
    },
  },
});

const CONTEXT_KEYS = Object.freeze([
  "organization_id",
  "project_id",
  "spec_id",
  "spec_version",
  "spec_hash",
  "generation_strategy",
]);
// Тот же контекст с выбранным движком каскада. Набор ключей проверяется точным
// совпадением, поэтому наборов два, а не один с «может быть, а может и нет»:
// контекст без движка обязан остаться правильным контекстом — так работает
// очередь из десяти исходников и все прежние вызовы.
const CONTEXT_KEYS_WITH_ENGINE = Object.freeze([...CONTEXT_KEYS, "engine"]);
// Необязательные ключи контекста. Набор ЗАКРЫТЫЙ: состав для точной сверки
// собирается из него, пересечённого с тем, что пришло, поэтому чужой ключ
// по-прежнему отвергается. Отдельный замороженный список на каждое сочетание
// (движок, ведущий, оба) разошёлся бы с остальными на первой же правке.
const CONTEXT_OPTIONAL_KEYS = Object.freeze(["engine", "duet_presenter_id"]);
const ENGINE_KEYS = Object.freeze(["provider", "model_key"]);
const SELECTION_COMMON_KEYS = Object.freeze([
  "version",
  "strategy_id",
  "recipe_version",
  "duration_seconds",
  "audio",
  "assets",
  "attestations",
]);
const ASSET_BASE_KEYS = Object.freeze(["role", "media_id"]);
const BIND_TOP_KEYS = Object.freeze([
  "ok",
  "version",
  "binding",
  "selection",
  "price",
  "contract",
]);
const BINDING_KEYS = Object.freeze([
  "id",
  "project_id",
  "spec_id",
  "spec_version",
  "spec_hash",
  "product_id",
  "strategy_id",
  "selection_hash",
  "source_basis",
  "source_binding_id",
  "source_binding_hash",
  "role_assets",
  "strategy_snapshot_hash",
  "binding_hash",
  "bound_at",
]);
const BINDING_ASSET_KEYS = Object.freeze([
  "role",
  "ordinal",
  "media_object_id",
  "sha256",
  "kind",
  "mime_type",
  "product_id",
  "rights_confirmed",
  "likeness_consent",
]);
const BINDING_ASSET_ROLES = Object.freeze(new Set([
  "product_primary",
  "product_reference",
  "creator_avatar",
  "original_product",
  "source_video",
  "style_reference",
]));
const BIND_SELECTION_KEYS = Object.freeze([
  "catalog_version",
  "recipe_version",
  "pricing_version",
  "strategy_id",
  "recipe",
  "selection_hash",
]);
const PRICE_KEYS = Object.freeze([
  "version",
  "strategy_id",
  "provider",
  "recipe",
  "input_mode",
  "duration_seconds",
  "resolution",
  "ratio",
  "audio",
  "estimated_credits",
  "estimated_pre_tax_usd_minor",
  "estimated_cost_minor",
  "estimated_cost_usd",
  "currency",
  "credit_unit_cost_minor",
  "catalog_version",
  "pricing_version",
  "recipe_version",
  "spend_confirmation",
  "price_hash",
]);
const BIND_CONTRACT_KEYS = Object.freeze([
  "server_resolved_source_binding",
  "server_resolved_media_hashes",
  "browser_hashes_accepted",
  "browser_source_binding_accepted",
  "provider_call_started",
  "paid_start_integrated",
  "launch_enabled",
]);
const PROBE_RESPONSE_KEYS = Object.freeze([
  "ok",
  "version",
  "media_id",
  "duration_seconds",
  "verified_at",
  "replay",
]);
const PREFLIGHT_TOP_KEYS = Object.freeze([
  "ok",
  "version",
  "replay",
  "receipt",
  "provider_preflight",
  "launch_enabled",
  "contract",
]);
const PREFLIGHT_RECEIPT_KEYS = Object.freeze([
  "id",
  "receipt_hash",
  "binding_id",
  "binding_hash",
  "strategy_id",
  "recipe",
  "catalog_version",
  "recipe_version",
  "pricing_version",
  "selection_hash",
  "price_hash",
  "ready",
  "failure_code",
  "checked_at",
  "expires_at",
]);
const PROVIDER_PREFLIGHT_KEYS = Object.freeze([
  "credential_configured",
  "provider_authentication_confirmed",
  "recipe_catalog_supported",
  "recipe_precheck_supported",
  "recipe_available",
  "balance_sufficient",
  "daily_quota_precheck_supported",
  "daily_quota_available",
]);
const PREFLIGHT_CONTRACT_KEYS = Object.freeze([
  "provider_call_started",
  "receipt_single_use",
  "browser_price_authority",
  "browser_prompt_authority",
]);
const STATUS_TOP_KEYS = Object.freeze([
  "ok",
  "version",
  "job",
  "strategy",
  "selection",
  "price",
  "dispatch",
  "reconciliation",
  "output",
  "error",
  "contract",
]);
const STATUS_JOB_KEYS = Object.freeze([
  "id",
  "batch_id",
  "project_id",
  "campaign_id",
  "status",
  "provider_status",
  "provider_task_id",
  "estimated_cost_minor",
  "actual_cost_minor",
  "currency",
  "created_at",
  "updated_at",
]);
const STATUS_STRATEGY_KEYS = Object.freeze([
  "version",
  "strategy_id",
  "recipe",
  "catalog_version",
  "recipe_version",
  "pricing_version",
  "binding_id",
  "binding_hash",
  "receipt_id",
  "receipt_hash",
  "selection_hash",
  "price_hash",
  "strategy_prompt_hash",
]);
const SAFE_PRICE_KEYS = Object.freeze(
  PRICE_KEYS.filter((key) => key !== "spend_confirmation"),
);
const STATUS_DISPATCH_KEYS = Object.freeze([
  "result_id",
  "result_hash",
  "outcome",
  "provider_post_started",
  "provider_http_status",
  "recorded_at",
]);
const STATUS_RECONCILIATION_REQUIRED_KEYS = Object.freeze([
  "required",
  "incident_id",
  "reason_code",
  "required_at",
]);
const STATUS_RECONCILIATION_RESOLVED_KEYS = Object.freeze([
  "required",
  "incident_id",
  "resolution",
  "reconciled_at",
]);
const STATUS_OUTPUT_KEYS = Object.freeze(["media_id", "mime_type", "size_bytes"]);
const STATUS_ERROR_KEYS = Object.freeze(["code", "provider_billing_outcome"]);
const STATUS_CONTRACT_KEYS = Object.freeze([
  "recipe_aware",
  "legacy_model_catalog_used",
  "poll_provider_allowed",
  "second_post_allowed",
  "object_names_returned",
  "media_hashes_returned",
  "signed_urls_returned",
  "manual_human_review_required",
]);
const RUNTIME_STATE_KEYS = Object.freeze([
  "version",
  "phase",
  "fingerprint",
  "identity",
  "bind",
  "preflight",
  "campaign_id",
  "start_context_fingerprint",
  "start",
  "status",
  "start_attempt_idempotency_key",
  "error",
]);
const RUNTIME_IDENTITY_KEYS = Object.freeze([
  "organization_id",
  "project_id",
  "spec_id",
  "spec_version",
  "spec_hash",
  "catalog_version",
  "strategy_id",
  "recipe_version",
]);
const SAFE_STATUS_STATE_KEYS = Object.freeze(
  STATUS_TOP_KEYS.filter((key) => key !== "selection"),
);
const START_STATE_KEYS = Object.freeze(["generation_job_id", "batch_id"]);

const SHA256_INITIAL = Object.freeze([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
]);
const SHA256_ROUND = Object.freeze([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);
const JOB_STATUSES = Object.freeze(new Set([
  "queued",
  "starting",
  "submitted",
  "processing",
  "succeeded",
  "failed",
  "cancelled",
]));
const PROVIDER_STATUSES = Object.freeze(new Set([
  "submitted",
  "processing",
  "succeeded",
  "failed",
  "cancelled",
]));
const TERMINAL_JOB_STATUSES = Object.freeze(new Set([
  "succeeded",
  "failed",
  "cancelled",
]));
const STATUS_RANK = Object.freeze({
  queued: 0,
  starting: 1,
  submitted: 2,
  processing: 3,
  succeeded: 4,
  failed: 4,
  cancelled: 4,
});
const PROVIDER_STATUS_RANK = Object.freeze({
  submitted: 0,
  processing: 1,
  succeeded: 2,
  failed: 2,
  cancelled: 2,
});

class RuntimeContractError extends Error {
  constructor(code, field) {
    super(code);
    this.name = "RuntimeContractError";
    this.code = code;
    this.field = field;
  }
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
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
    throw new RuntimeContractError("object_required", field);
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length ||
    actual.some((key, index) => key !== expected[index])
  ) {
    throw new RuntimeContractError("object_keys_mismatch", field);
  }
  return value;
}

function hasExactObjectKeys(value, keys) {
  if (!isPlainObject(value)) return false;
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length &&
    actual.every((key, index) => key === expected[index]);
}

function requiredText(value, field, maxLength = 5_000) {
  if (typeof value !== "string") {
    throw new RuntimeContractError("text_required", field);
  }
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength || /[\u0000-\u001f\u007f]/u.test(normalized)) {
    throw new RuntimeContractError("text_invalid", field);
  }
  return normalized;
}

function requiredCode(value, field) {
  const normalized = requiredText(value, field, 128).toLowerCase();
  if (!CODE_PATTERN.test(normalized)) {
    throw new RuntimeContractError("code_invalid", field);
  }
  return normalized;
}

function exactText(value, field, maxLength = 5_000) {
  const normalized = requiredText(value, field, maxLength);
  if (normalized !== value) {
    throw new RuntimeContractError("text_not_canonical", field);
  }
  return normalized;
}

function exactCode(value, field) {
  const normalized = exactText(value, field, 128);
  if (!CODE_PATTERN.test(normalized)) {
    throw new RuntimeContractError("code_invalid", field);
  }
  return normalized;
}

function requiredUuid(value, field) {
  const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (!UUID_PATTERN.test(normalized) || normalized === ZERO_UUID) {
    throw new RuntimeContractError("uuid_invalid", field);
  }
  return normalized;
}

function requiredSha256(value, field) {
  const normalized = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (!SHA256_PATTERN.test(normalized)) {
    throw new RuntimeContractError("sha256_invalid", field);
  }
  return normalized;
}

function exactUuid(value, field) {
  const normalized = requiredUuid(value, field);
  if (normalized !== value) {
    throw new RuntimeContractError("uuid_not_canonical", field);
  }
  return normalized;
}

function exactSha256(value, field) {
  const normalized = requiredSha256(value, field);
  if (normalized !== value) {
    throw new RuntimeContractError("sha256_not_canonical", field);
  }
  return normalized;
}

function requiredBoolean(value, field) {
  if (typeof value !== "boolean") {
    throw new RuntimeContractError("boolean_required", field);
  }
  return value;
}

function safeInteger(value, field, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new RuntimeContractError("integer_invalid", field);
  }
  return value;
}

function nullableExactText(value, field, maxLength = 5_000) {
  return value === null ? null : exactText(value, field, maxLength);
}

function nullableExactCode(value, field) {
  return value === null ? null : exactCode(value, field);
}

function nullableExactUuid(value, field) {
  return value === null ? null : exactUuid(value, field);
}

function nullableSafeInteger(value, field, min = 0, max = Number.MAX_SAFE_INTEGER) {
  return value === null ? null : safeInteger(value, field, min, max);
}

function positiveFiniteNumber(value, field, max = 86_400) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0 || value > max) {
    throw new RuntimeContractError("number_invalid", field);
  }
  return value;
}

function requiredTimestamp(value, field) {
  const normalized = exactText(value, field, 80);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/u.test(normalized) ||
      !Number.isFinite(Date.parse(normalized))) {
    throw new RuntimeContractError("timestamp_invalid", field);
  }
  return normalized;
}

function normalizedResult(normalizer, raw, expected = null) {
  try {
    return deepFreeze({
      ok: true,
      value: normalizer(raw, expected),
      error: null,
    });
  } catch (error) {
    const known = error instanceof RuntimeContractError;
    return deepFreeze({
      ok: false,
      value: null,
      error: {
        code: known ? error.code : "runtime_contract_invalid",
        field: known ? error.field : "runtime",
      },
    });
  }
}

function requestResult(request, fingerprint = null, startContextFingerprint = null) {
  return deepFreeze({
    ok: true,
    fingerprint,
    start_context_fingerprint: startContextFingerprint,
    request,
    error: null,
  });
}

function requestFailure(error, fallbackCode, fallbackField) {
  const known = error instanceof RuntimeContractError;
  return deepFreeze({
    ok: false,
    fingerprint: null,
    start_context_fingerprint: null,
    request: null,
    error: {
      code: known ? error.code : fallbackCode,
      field: known ? error.field : fallbackField,
    },
  });
}

function requiredIdempotencyKey(value, field = "idempotency_key") {
  const normalized = exactText(value, field, 180);
  if (!IDEMPOTENCY_PATTERN.test(normalized)) {
    throw new RuntimeContractError("idempotency_key_invalid", field);
  }
  return normalized;
}

function normalizeSelectionAsset(value, index) {
  const field = `context.generation_strategy.assets[${index}]`;
  if (!isPlainObject(value)) {
    throw new RuntimeContractError("object_required", field);
  }
  const optional = [
    ...(hasOwn(value, "duration_seconds") ? ["duration_seconds"] : []),
    ...(hasOwn(value, "view") ? ["view"] : []),
  ];
  const source = exactObject(value, [...ASSET_BASE_KEYS, ...optional], field);
  return {
    role: requiredCode(source.role, `${field}.role`),
    media_id: requiredUuid(source.media_id, `${field}.media_id`),
    ...(hasOwn(source, "duration_seconds")
      ? { duration_seconds: positiveFiniteNumber(source.duration_seconds, `${field}.duration_seconds`) }
      : {}),
    ...(hasOwn(source, "view")
      ? { view: requiredCode(source.view, `${field}.view`) }
      : {}),
  };
}

function normalizeAttestations(value, expectedKeys) {
  const source = exactObject(
    value,
    expectedKeys,
    "context.generation_strategy.attestations",
  );
  return Object.fromEntries(expectedKeys.map((key) => {
    if (source[key] !== true) {
      throw new RuntimeContractError(
        "attestation_required",
        `context.generation_strategy.attestations.${key}`,
      );
    }
    return [key, true];
  }));
}

function normalizeGenerationStrategySelection(value) {
  if (!isPlainObject(value)) {
    throw new RuntimeContractError("object_required", "context.generation_strategy");
  }
  const rawStrategyId = requiredCode(
    value.strategy_id,
    "context.generation_strategy.strategy_id",
  );
  const rules = STRATEGY_RULES[rawStrategyId];
  if (!rules) {
    throw new RuntimeContractError(
      "strategy_unknown",
      "context.generation_strategy.strategy_id",
    );
  }
  const hasRatio = hasOwn(value, "ratio");
  const hasResolution = hasOwn(value, "resolution");
  if (
    hasRatio === hasResolution ||
    (rules.dimension === "ratio") !== hasRatio
  ) {
    throw new RuntimeContractError(
      "selection_dimension_invalid",
      "context.generation_strategy",
    );
  }
  const dimensionField = hasRatio ? "ratio" : "resolution";
  const source = exactObject(
    value,
    [...SELECTION_COMMON_KEYS, dimensionField],
    "context.generation_strategy",
  );
  if (!Array.isArray(source.assets) || source.assets.length === 0 || source.assets.length > 32) {
    throw new RuntimeContractError("assets_invalid", "context.generation_strategy.assets");
  }
  const assets = source.assets.map(normalizeSelectionAsset);
  if (new Set(assets.map((asset) => asset.media_id)).size !== assets.length) {
    throw new RuntimeContractError(
      "asset_media_id_duplicate",
      "context.generation_strategy.assets",
    );
  }
  const counts = new Map();
  for (let index = 0; index < assets.length; index += 1) {
    const asset = assets[index];
    const field = `context.generation_strategy.assets[${index}]`;
    if (!hasOwn(rules.roles, asset.role)) {
      throw new RuntimeContractError("asset_role_unknown", `${field}.role`);
    }
    counts.set(asset.role, (counts.get(asset.role) || 0) + 1);
    if (asset.role === "source_video") {
      if (hasOwn(asset, "view")) {
        throw new RuntimeContractError("asset_field_invalid", `${field}.view`);
      }
      // Длительность исходника обязательна обеим правкам готового видео.
      // У «Дуэта» по ней считаются деньги: ставка посекундная. Без неё
      // запуск доходил бы до сервера и падал там — после резерва.
      const sourceBounds = SOURCE_DURATION_BOUNDS[rawStrategyId] ?? null;
      if (sourceBounds !== null) {
        if (!hasOwn(asset, "duration_seconds")) {
          throw new RuntimeContractError(
            "asset_duration_required",
            `${field}.duration_seconds`,
          );
        }
        if (
          asset.duration_seconds < sourceBounds.minimum ||
          asset.duration_seconds > sourceBounds.maximum
        ) {
          throw new RuntimeContractError(
            "asset_duration_unsupported",
            `${field}.duration_seconds`,
          );
        }
      }
    } else if (hasOwn(asset, "duration_seconds")) {
      throw new RuntimeContractError(
        "asset_field_invalid",
        `${field}.duration_seconds`,
      );
    }
    if (asset.role === "new_product_image") {
      if (hasOwn(asset, "view") && !["front", "side", "back"].includes(asset.view)) {
        throw new RuntimeContractError("asset_view_unsupported", `${field}.view`);
      }
    } else if (hasOwn(asset, "view")) {
      throw new RuntimeContractError("asset_field_invalid", `${field}.view`);
    }
  }
  for (const [role, limits] of Object.entries(rules.roles)) {
    const count = counts.get(role) || 0;
    if (count < limits[0] || count > limits[1]) {
      throw new RuntimeContractError(
        "asset_role_count_invalid",
        `context.generation_strategy.assets.${role}`,
      );
    }
  }
  const dimensionValue = requiredText(
    source[dimensionField],
    `context.generation_strategy.${dimensionField}`,
    128,
  ).toLowerCase();
  if (!rules.dimensions.includes(dimensionValue)) {
    throw new RuntimeContractError(
      "selection_dimension_unsupported",
      `context.generation_strategy.${dimensionField}`,
    );
  }
  const durationSeconds = safeInteger(
    source.duration_seconds,
    "context.generation_strategy.duration_seconds",
    rules.duration?.minimum ?? 4,
    rules.duration?.maximum ?? 15,
  );
  if (source.version !== CATALOG_VERSION) {
    throw new RuntimeContractError(
      "catalog_version_mismatch",
      "context.generation_strategy.version",
    );
  }
  if (source.recipe_version !== RECIPE_VERSION) {
    throw new RuntimeContractError(
      "recipe_version_mismatch",
      "context.generation_strategy.recipe_version",
    );
  }
  return {
    version: CATALOG_VERSION,
    strategy_id: rawStrategyId,
    recipe_version: RECIPE_VERSION,
    duration_seconds: durationSeconds,
    [dimensionField]: dimensionValue,
    audio: requiredBoolean(source.audio, "context.generation_strategy.audio"),
    assets,
    attestations: normalizeAttestations(source.attestations, rules.attestations),
  };
}

// Движок каскада: либо полный выбор из двух строк, либо его нет вовсе.
// Половина выбора — это не «почти движок», а запрос, по которому нельзя
// назвать цену, поэтому неполное значение здесь отказ, а не умолчание.
function normalizeRuntimeEngine(value) {
  if (value === null || value === undefined) return null;
  const source = exactObject(value, ENGINE_KEYS, "context.engine");
  return {
    provider: requiredText(source.provider, "context.engine.provider", 40),
    model_key: requiredText(source.model_key, "context.engine.model_key", 120),
  };
}

function normalizeRuntimeContext(value) {
  const present = CONTEXT_OPTIONAL_KEYS.filter((key) =>
    isPlainObject(value) && Object.prototype.hasOwnProperty.call(value, key)
  );
  const withEngine = present.includes("engine");
  const withPresenter = present.includes("duet_presenter_id");
  const source = exactObject(
    value,
    present.length === 0 ? CONTEXT_KEYS : [...CONTEXT_KEYS, ...present],
    "context",
  );
  const engine = withEngine ? normalizeRuntimeEngine(source.engine) : null;
  // Ведущий входит в ОТПЕЧАТОК запуска наравне с движком: сменить того, кто
  // говорит, после подтверждения цены — это другой запуск, а не подробность
  // прежнего.
  const duetPresenterId = withPresenter
    ? requiredUuid(source.duet_presenter_id, "context.duet_presenter_id")
    : null;
  return {
    organization_id: requiredUuid(source.organization_id, "context.organization_id"),
    project_id: requiredUuid(source.project_id, "context.project_id"),
    spec_id: requiredUuid(source.spec_id, "context.spec_id"),
    spec_version: safeInteger(source.spec_version, "context.spec_version", 1, 100_000),
    spec_hash: requiredSha256(source.spec_hash, "context.spec_hash"),
    generation_strategy: normalizeGenerationStrategySelection(
      source.generation_strategy,
    ),
    ...(engine === null ? {} : { engine }),
    ...(duetPresenterId === null
      ? {}
      : { duet_presenter_id: duetPresenterId }),
  };
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value).sort().map(
    (key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`,
  ).join(",")}}`;
}

function rotateRight(value, bits) {
  return (value >>> bits) | (value << (32 - bits));
}

function sha256Hex(message) {
  const bytes = new TextEncoder().encode(message);
  const bitLength = bytes.length * 8;
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x1_0000_0000), false);
  view.setUint32(paddedLength - 4, bitLength >>> 0, false);

  const hash = [...SHA256_INITIAL];
  const words = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4, false);
    }
    for (let index = 16; index < 64; index += 1) {
      const previous15 = words[index - 15];
      const previous2 = words[index - 2];
      const sigma0 = rotateRight(previous15, 7) ^ rotateRight(previous15, 18) ^
        (previous15 >>> 3);
      const sigma1 = rotateRight(previous2, 17) ^ rotateRight(previous2, 19) ^
        (previous2 >>> 10);
      words[index] = (
        words[index - 16] + sigma0 + words[index - 7] + sigma1
      ) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = hash;
    for (let index = 0; index < 64; index += 1) {
      const sum1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + sum1 + choice + SHA256_ROUND[index] + words[index]) >>> 0;
      const sum0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (sum0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }
    hash[0] = (hash[0] + a) >>> 0;
    hash[1] = (hash[1] + b) >>> 0;
    hash[2] = (hash[2] + c) >>> 0;
    hash[3] = (hash[3] + d) >>> 0;
    hash[4] = (hash[4] + e) >>> 0;
    hash[5] = (hash[5] + f) >>> 0;
    hash[6] = (hash[6] + g) >>> 0;
    hash[7] = (hash[7] + h) >>> 0;
  }
  return hash.map((word) => word.toString(16).padStart(8, "0")).join("");
}

function runtimeIdentity(context) {
  const selection = context.generation_strategy;
  return {
    organization_id: context.organization_id,
    project_id: context.project_id,
    spec_id: context.spec_id,
    spec_version: context.spec_version,
    spec_hash: context.spec_hash,
    catalog_version: selection.version,
    strategy_id: selection.strategy_id,
    recipe_version: selection.recipe_version,
  };
}

function runtimeValidationIdentity(context) {
  const selection = context.generation_strategy;
  const dimensionField = hasOwn(selection, "ratio") ? "ratio" : "resolution";
  return {
    ...runtimeIdentity(context),
    duration_seconds: selection.duration_seconds,
    dimension_field: dimensionField,
    dimension_value: selection[dimensionField],
    audio: selection.audio,
  };
}

export function createGenerationStrategyRuntimeFingerprint(raw) {
  try {
    const context = normalizeRuntimeContext(raw);
    return deepFreeze({
      ok: true,
      version: GENERATION_STRATEGY_RUNTIME_VERSION,
      fingerprint: sha256Hex(canonicalJson({
        version: GENERATION_STRATEGY_RUNTIME_VERSION,
        context,
      })),
      identity: runtimeIdentity(context),
      error: null,
    });
  } catch (error) {
    const known = error instanceof RuntimeContractError;
    return deepFreeze({
      ok: false,
      version: GENERATION_STRATEGY_RUNTIME_VERSION,
      fingerprint: null,
      identity: null,
      error: {
        code: known ? error.code : "runtime_context_invalid",
        field: known ? error.field : "context",
      },
    });
  }
}

function normalizeBindingAsset(value, index) {
  const field = `bind.binding.role_assets[${index}]`;
  const source = exactObject(value, BINDING_ASSET_KEYS, field);
  const role = exactCode(source.role, `${field}.role`);
  if (!BINDING_ASSET_ROLES.has(role)) {
    throw new RuntimeContractError("binding_asset_role_invalid", `${field}.role`);
  }
  const mimeType = exactText(source.mime_type, `${field}.mime_type`, 160);
  if (mimeType !== mimeType.toLowerCase()) {
    throw new RuntimeContractError("text_not_canonical", `${field}.mime_type`);
  }
  const kind = exactCode(source.kind, `${field}.kind`);
  const likenessConsent = requiredBoolean(
    source.likeness_consent,
    `${field}.likeness_consent`,
  );
  if (source.rights_confirmed !== true) {
    throw new RuntimeContractError("binding_asset_rights_invalid", `${field}.rights_confirmed`);
  }
  if ((role === "creator_avatar") !== likenessConsent) {
    throw new RuntimeContractError("binding_asset_likeness_invalid", `${field}.likeness_consent`);
  }
  if (role === "source_video" && (kind !== "source_video" || mimeType !== "video/mp4")) {
    throw new RuntimeContractError("binding_asset_media_invalid", field);
  }
  if (role !== "source_video" && !new Set(["image/jpeg", "image/png", "image/webp"]).has(mimeType)) {
    throw new RuntimeContractError("binding_asset_media_invalid", field);
  }
  return {
    role,
    ordinal: safeInteger(source.ordinal, `${field}.ordinal`, 1, 99),
    media_object_id: exactUuid(source.media_object_id, `${field}.media_object_id`),
    sha256: exactSha256(source.sha256, `${field}.sha256`),
    kind,
    mime_type: mimeType,
    product_id: source.product_id === null
      ? null
      : exactUuid(source.product_id, `${field}.product_id`),
    rights_confirmed: true,
    likeness_consent: likenessConsent,
  };
}

function bindingAssetsMatchStrategy(assets, strategyId, productId) {
  const counts = new Map();
  for (const asset of assets) {
    counts.set(asset.role, (counts.get(asset.role) || 0) + 1);
    const image = new Set(["image/jpeg", "image/png", "image/webp"])
      .has(asset.mime_type);
    if (
      ["product_primary", "product_reference"].includes(asset.role) &&
      (!image || !new Set(["product_photo", "packshot"]).has(asset.kind) ||
        asset.product_id !== productId || asset.likeness_consent)
    ) return false;
    if (
      ["creator_avatar", "original_product", "style_reference"].includes(asset.role) &&
      (!image || asset.kind !== "creator_reference")
    ) return false;
    if (
      asset.role === "source_video" &&
      (asset.kind !== "source_video" || asset.mime_type !== "video/mp4" ||
        asset.likeness_consent)
    ) return false;
    if (asset.role === "product_primary" && asset.ordinal !== 1) return false;
    if (
      ["creator_avatar", "original_product", "source_video"].includes(asset.role) &&
      asset.ordinal !== 1
    ) return false;
    if (asset.role === "product_reference" && asset.ordinal > 9) return false;
    if (asset.role === "style_reference" && asset.ordinal > 4) return false;
  }
  const count = (role) => counts.get(role) || 0;
  // «Дуэт» проверяется ДО общего требования товарного ассета: товара у него нет
  // по устройству, и общая проверка отвергла бы его раньше, чем дошла до формы.
  if (strategyId === "viral_avatar_ugc") {
    return assets.length === 1 && count("source_video") === 1 &&
      count("creator_avatar") === 0 && count("product_primary") === 0 &&
      count("product_reference") === 0 && count("original_product") === 0 &&
      count("style_reference") === 0;
  }
  if (count("product_primary") !== 1) return false;
  if (strategyId === "viral_product_swap") {
    return count("creator_avatar") === 0 && count("original_product") === 1 &&
      count("source_video") === 1 && count("style_reference") === 0 &&
      count("product_reference") <= 9 &&
      assets.length === count("product_reference") + 3;
  }
  if (strategyId === "viral_rebuild") {
    return count("creator_avatar") === 0 && count("original_product") === 0 &&
      count("source_video") === 1 && count("product_reference") <= 9 &&
      count("style_reference") <= 4 &&
      assets.length === count("product_reference") + count("style_reference") + 2;
  }
  return false;
}

function expectedBindingAssetIdentities(selectionAssets, strategyId) {
  const identities = new Map();
  for (const asset of selectionAssets) {
    let roles;
    if (["product_image", "new_product_image"].includes(asset.role)) {
      roles = new Set(["product_primary", "product_reference"]);
    } else if (asset.role === "avatar_image") {
      roles = new Set(["creator_avatar"]);
    } else if (asset.role === "original_product_image") {
      roles = new Set(["original_product"]);
      // Прежде исходник «Аватара» здесь намеренно пропускался: он не был входом
      // провайдера и в реестре ассетов не значился. У «Дуэта» он единственный
      // ассет и обязан сверяться, поэтому исключение снято.
    } else if (asset.role === "source_video") {
      roles = new Set(["source_video"]);
    } else if (asset.role === "style_image") {
      roles = new Set(["style_reference"]);
    } else {
      return null;
    }
    identities.set(asset.media_id, roles);
  }
  return identities;
}

function normalizePrice(value, identity, selection) {
  const source = exactObject(value, PRICE_KEYS, "bind.price");
  const estimatedCredits = safeInteger(
    source.estimated_credits,
    "bind.price.estimated_credits",
    1,
    1_000_000,
  );
  const estimatedPreTax = safeInteger(
    source.estimated_pre_tax_usd_minor,
    "bind.price.estimated_pre_tax_usd_minor",
    1,
    1_000_000,
  );
  const estimatedCost = safeInteger(
    source.estimated_cost_minor,
    "bind.price.estimated_cost_minor",
    1,
    1_000_000,
  );
  const costUsd = exactText(source.estimated_cost_usd, "bind.price.estimated_cost_usd", 32);
  const expectedInputMode = {
    viral_avatar_ugc: "video_and_avatar_images",
    viral_product_swap: "video_and_product_images",
    viral_rebuild: "product_images",
  }[identity.strategy_id];
  const baseCredits = {
    viral_avatar_ugc: { "720p": 192, "1080p": 208 },
    viral_product_swap: { "720p": 212, "1080p": 228 },
    viral_rebuild: { "720p": 200, "1080p": 216 },
  }[identity.strategy_id]?.[source.resolution];
  const expectedCredits = baseCredits === undefined
    ? null
    : baseCredits + (identity.duration_seconds - 4) *
      (source.resolution === "720p" ? 36 : 40);
  const spendConfirmation = exactText(
    source.spend_confirmation,
    "bind.price.spend_confirmation",
    180,
  );
  // Провайдер стоит в самой строке подтверждения: она обязана называть тот
  // маршрут, по которому посчитаны деньги. Жёсткий префикс RUNWAY_ отвергал
  // верный снимок другого маршрута, и отказ приходил без объяснения.
  const priceProvider = String(source.provider || "");
  const expectedSpendConfirmation = `${priceProvider.toUpperCase()}_${
    selection.recipe.toUpperCase()
  }_${
    identity.duration_seconds
  }S_${String(source.resolution).toUpperCase()}_${
    identity.audio ? "AUDIO" : "SILENT"
  }_USD_${costUsd}`;
  // Ступени кредитов принадлежат ПРАЙСУ, а не провайдеру: у Runway их два
  // способа счёта (aleph2 — ступени рецепта, gen4_turbo «Создания» — ставка
  // за секунду), и ветвление по провайдеру отвергало бы честный посекундный
  // снимок сверкой с чужой арифметикой ступеней — bind_price_mismatch на
  // валидной привязке. Перекрёстную подмену (runway с чужим прайсом) ловит
  // префикс: каждая версия прайса начинается именем своего провайдера — та
  // же пара инвариантов, что в edge safeStatusPrice.
  const recipeCredits =
    source.pricing_version === "runway-recipe-credits-2026-08-14.v1";
  const creditsMatchRoute = (recipeCredits
    ? estimatedCredits === expectedCredits
    : true) &&
    String(source.pricing_version || "").startsWith(`${priceProvider}-`);
  if (
    source.version !== "generation-strategy-price-snapshot-v1" ||
    source.strategy_id !== identity.strategy_id ||
    !knownStrategyProvider(priceProvider) ||
    source.recipe !== selection.recipe ||
    source.input_mode !== expectedInputMode ||
    source.duration_seconds !== identity.duration_seconds ||
    source.audio !== identity.audio ||
    !["720p", "1080p"].includes(source.resolution) ||
    (identity.dimension_field === "ratio"
      ? source.ratio !== identity.dimension_value
      : source.resolution !== identity.dimension_value || source.ratio !== "source") ||
    estimatedCredits !== estimatedPreTax ||
    estimatedCredits !== estimatedCost ||
    !creditsMatchRoute ||
    costUsd !== (estimatedCost / 100).toFixed(2) ||
    source.currency !== "USD" ||
    source.credit_unit_cost_minor !== 1 ||
    source.catalog_version !== selection.catalog_version ||
    source.pricing_version !== selection.pricing_version ||
    source.recipe_version !== selection.recipe_version ||
    spendConfirmation !== expectedSpendConfirmation
  ) {
    throw new RuntimeContractError("bind_price_mismatch", "bind.price");
  }
  return {
    version: source.version,
    strategy_id: identity.strategy_id,
    provider: priceProvider,
    recipe: selection.recipe,
    input_mode: exactCode(source.input_mode, "bind.price.input_mode"),
    duration_seconds: identity.duration_seconds,
    resolution: source.resolution,
    ratio: exactText(source.ratio, "bind.price.ratio", 128),
    audio: identity.audio,
    estimated_credits: estimatedCredits,
    estimated_pre_tax_usd_minor: estimatedPreTax,
    estimated_cost_minor: estimatedCost,
    estimated_cost_usd: costUsd,
    currency: "USD",
    credit_unit_cost_minor: 1,
    catalog_version: selection.catalog_version,
    pricing_version: selection.pricing_version,
    recipe_version: selection.recipe_version,
    spend_confirmation: spendConfirmation,
    price_hash: exactSha256(source.price_hash, "bind.price.price_hash"),
  };
}

function normalizeBindResponse(raw, expectedContext) {
  const source = exactObject(raw, BIND_TOP_KEYS, "bind");
  if (source.ok !== true || source.version !== "generation-strategy-resolve-bind-response-v1") {
    throw new RuntimeContractError("bind_envelope_invalid", "bind");
  }
  const normalizedContext = normalizeRuntimeContext(expectedContext);
  const identity = runtimeValidationIdentity(normalizedContext);
  const selectionSource = exactObject(source.selection, BIND_SELECTION_KEYS, "bind.selection");
  const selection = {
    catalog_version: exactText(selectionSource.catalog_version, "bind.selection.catalog_version", 160),
    recipe_version: exactText(selectionSource.recipe_version, "bind.selection.recipe_version", 160),
    pricing_version: exactText(selectionSource.pricing_version, "bind.selection.pricing_version", 160),
    strategy_id: exactCode(selectionSource.strategy_id, "bind.selection.strategy_id"),
    recipe: exactCode(selectionSource.recipe, "bind.selection.recipe"),
    selection_hash: exactSha256(selectionSource.selection_hash, "bind.selection.selection_hash"),
  };
  const bindingSource = exactObject(source.binding, BINDING_KEYS, "bind.binding");
  // Нижняя граница — один ассет, а не два: у «Дуэта» в привязке ровно один
  // исходник. Точное число ассетов каждой стратегии проверяет
  // bindingAssetsMatchStrategy — здесь только защита от пустого и
  // непомерного набора.
  if (!Array.isArray(bindingSource.role_assets) || bindingSource.role_assets.length < 1 || bindingSource.role_assets.length > 16) {
    throw new RuntimeContractError("binding_assets_invalid", "bind.binding.role_assets");
  }
  const roleAssets = bindingSource.role_assets.map(normalizeBindingAsset);
  const identities = new Set();
  for (const asset of roleAssets) {
    const ordinalIdentity = `${asset.role}:${asset.ordinal}`;
    if (identities.has(ordinalIdentity) || identities.has(asset.media_object_id)) {
      throw new RuntimeContractError("binding_asset_duplicate", "bind.binding.role_assets");
    }
    identities.add(ordinalIdentity);
    identities.add(asset.media_object_id);
  }
  const binding = {
    id: exactUuid(bindingSource.id, "bind.binding.id"),
    project_id: exactUuid(bindingSource.project_id, "bind.binding.project_id"),
    spec_id: exactUuid(bindingSource.spec_id, "bind.binding.spec_id"),
    spec_version: safeInteger(bindingSource.spec_version, "bind.binding.spec_version", 1, 100_000),
    spec_hash: exactSha256(bindingSource.spec_hash, "bind.binding.spec_hash"),
    product_id: exactUuid(bindingSource.product_id, "bind.binding.product_id"),
    strategy_id: exactCode(bindingSource.strategy_id, "bind.binding.strategy_id"),
    selection_hash: exactSha256(bindingSource.selection_hash, "bind.binding.selection_hash"),
    source_basis: exactCode(bindingSource.source_basis, "bind.binding.source_basis"),
    source_binding_id: exactUuid(bindingSource.source_binding_id, "bind.binding.source_binding_id"),
    source_binding_hash: exactSha256(bindingSource.source_binding_hash, "bind.binding.source_binding_hash"),
    role_assets: roleAssets,
    strategy_snapshot_hash: exactSha256(
      bindingSource.strategy_snapshot_hash,
      "bind.binding.strategy_snapshot_hash",
    ),
    binding_hash: exactSha256(bindingSource.binding_hash, "bind.binding.binding_hash"),
    bound_at: requiredTimestamp(bindingSource.bound_at, "bind.binding.bound_at"),
  };
  if (
    binding.project_id !== identity.project_id ||
    binding.spec_id !== identity.spec_id ||
    binding.spec_version !== identity.spec_version ||
    binding.spec_hash !== identity.spec_hash ||
    binding.strategy_id !== identity.strategy_id ||
    binding.source_basis !== "exact_source_video" ||
    binding.selection_hash !== selection.selection_hash ||
    selection.strategy_id !== identity.strategy_id ||
    selection.catalog_version !== CATALOG_VERSION ||
    selection.catalog_version !== identity.catalog_version ||
    selection.recipe_version !== RECIPE_VERSION ||
    selection.recipe_version !== identity.recipe_version ||
    !knownPricingVersion(selection.pricing_version) ||
    selection.recipe !== STRATEGY_RULES[identity.strategy_id]?.recipe
  ) {
    throw new RuntimeContractError("bind_identity_mismatch", "bind");
  }
  if (!bindingAssetsMatchStrategy(roleAssets, identity.strategy_id, binding.product_id)) {
    throw new RuntimeContractError("binding_assets_mismatch", "bind.binding.role_assets");
  }
  const expectedAssetIdentities = expectedBindingAssetIdentities(
    normalizedContext.generation_strategy.assets,
    identity.strategy_id,
  );
  if (
    expectedAssetIdentities === null ||
    expectedAssetIdentities.size !== roleAssets.length ||
    roleAssets.some((asset) =>
      !expectedAssetIdentities.get(asset.media_object_id)?.has(asset.role)
    )
  ) {
    throw new RuntimeContractError(
      "binding_asset_identity_mismatch",
      "bind.binding.role_assets",
    );
  }
  const price = normalizePrice(source.price, identity, selection);
  const contractSource = exactObject(source.contract, BIND_CONTRACT_KEYS, "bind.contract");
  if (
    contractSource.server_resolved_source_binding !== true ||
    contractSource.server_resolved_media_hashes !== true ||
    contractSource.browser_hashes_accepted !== false ||
    contractSource.browser_source_binding_accepted !== false ||
    contractSource.provider_call_started !== false ||
    contractSource.paid_start_integrated !== false ||
    contractSource.launch_enabled !== false
  ) {
    throw new RuntimeContractError("bind_contract_invalid", "bind.contract");
  }
  return deepFreeze({
    ok: true,
    version: source.version,
    binding,
    selection,
    price,
    contract: {
      server_resolved_source_binding: true,
      server_resolved_media_hashes: true,
      browser_hashes_accepted: false,
      browser_source_binding_accepted: false,
      provider_call_started: false,
      paid_start_integrated: false,
      launch_enabled: false,
    },
  });
}

export function normalizeGenerationStrategyBindResponse(raw, expectedContext) {
  return normalizedResult(normalizeBindResponse, raw, expectedContext);
}

export function generationStrategyRuntimeProbeRequest(raw, idempotencyKey) {
  try {
    const source = exactObject(
      raw,
      ["organization_id", "project_id", "media_id"],
      "probe_context",
    );
    return requestResult({
      action: "strategy_media_probe",
      organization_id: requiredUuid(
        source.organization_id,
        "probe_context.organization_id",
      ),
      project_id: requiredUuid(source.project_id, "probe_context.project_id"),
      media_id: requiredUuid(source.media_id, "probe_context.media_id"),
      confirmation: true,
      idempotency_key: requiredIdempotencyKey(idempotencyKey),
    });
  } catch (error) {
    return requestFailure(error, "probe_request_invalid", "probe_request");
  }
}

function normalizeProbeResponse(raw, expectedMediaId) {
  const source = exactObject(raw, PROBE_RESPONSE_KEYS, "probe");
  const mediaId = exactUuid(source.media_id, "probe.media_id");
  if (
    source.ok !== true ||
    source.version !== "generation-strategy-media-probe-response-v1" ||
    mediaId !== requiredUuid(expectedMediaId, "expected_media_id")
  ) {
    throw new RuntimeContractError("probe_identity_mismatch", "probe");
  }
  return deepFreeze({
    ok: true,
    version: source.version,
    media_id: mediaId,
    duration_seconds: positiveFiniteNumber(
      source.duration_seconds,
      "probe.duration_seconds",
      3_600,
    ),
    verified_at: requiredTimestamp(source.verified_at, "probe.verified_at"),
    replay: requiredBoolean(source.replay, "probe.replay"),
  });
}

export function normalizeGenerationStrategyProbeResponse(raw, expectedMediaId) {
  return normalizedResult(normalizeProbeResponse, raw, expectedMediaId);
}

function normalizeProviderPreflight(value) {
  const source = exactObject(
    value,
    PROVIDER_PREFLIGHT_KEYS,
    "preflight.provider_preflight",
  );
  if (
    source.credential_configured !== true ||
    source.provider_authentication_confirmed !== true ||
    source.recipe_catalog_supported !== true ||
    source.recipe_precheck_supported !== false ||
    source.recipe_available !== null ||
    source.balance_sufficient !== true ||
    source.daily_quota_precheck_supported !== false ||
    source.daily_quota_available !== null
  ) {
    throw new RuntimeContractError(
      "provider_preflight_not_ready",
      "preflight.provider_preflight",
    );
  }
  return {
    credential_configured: true,
    provider_authentication_confirmed: true,
    recipe_catalog_supported: true,
    recipe_precheck_supported: false,
    recipe_available: null,
    balance_sufficient: true,
    daily_quota_precheck_supported: false,
    daily_quota_available: null,
  };
}

function normalizePreflightResponse(raw, expectedState) {
  if (
    !validRuntimeState(expectedState) ||
    !["bound", "human_confirmed"].includes(expectedState.phase) ||
    !expectedState.bind
  ) {
    throw new RuntimeContractError("preflight_state_invalid", "expected_state");
  }
  const source = exactObject(raw, PREFLIGHT_TOP_KEYS, "preflight");
  if (
    source.ok !== true ||
    source.version !== "generation-strategy-preflight-response-v1" ||
    source.launch_enabled !== true
  ) {
    throw new RuntimeContractError("preflight_envelope_invalid", "preflight");
  }
  const receiptSource = exactObject(
    source.receipt,
    PREFLIGHT_RECEIPT_KEYS,
    "preflight.receipt",
  );
  const checkedAt = requiredTimestamp(
    receiptSource.checked_at,
    "preflight.receipt.checked_at",
  );
  const expiresAt = requiredTimestamp(
    receiptSource.expires_at,
    "preflight.receipt.expires_at",
  );
  const receipt = {
    id: exactUuid(receiptSource.id, "preflight.receipt.id"),
    receipt_hash: exactSha256(
      receiptSource.receipt_hash,
      "preflight.receipt.receipt_hash",
    ),
    binding_id: exactUuid(receiptSource.binding_id, "preflight.receipt.binding_id"),
    binding_hash: exactSha256(
      receiptSource.binding_hash,
      "preflight.receipt.binding_hash",
    ),
    strategy_id: exactCode(
      receiptSource.strategy_id,
      "preflight.receipt.strategy_id",
    ),
    recipe: exactCode(receiptSource.recipe, "preflight.receipt.recipe"),
    catalog_version: exactText(
      receiptSource.catalog_version,
      "preflight.receipt.catalog_version",
      160,
    ),
    recipe_version: exactText(
      receiptSource.recipe_version,
      "preflight.receipt.recipe_version",
      160,
    ),
    pricing_version: exactText(
      receiptSource.pricing_version,
      "preflight.receipt.pricing_version",
      160,
    ),
    selection_hash: exactSha256(
      receiptSource.selection_hash,
      "preflight.receipt.selection_hash",
    ),
    price_hash: exactSha256(
      receiptSource.price_hash,
      "preflight.receipt.price_hash",
    ),
    ready: requiredBoolean(receiptSource.ready, "preflight.receipt.ready"),
    failure_code: nullableExactCode(
      receiptSource.failure_code,
      "preflight.receipt.failure_code",
    ),
    checked_at: checkedAt,
    expires_at: expiresAt,
  };
  const binding = expectedState.bind.binding;
  const selection = expectedState.bind.selection;
  const price = expectedState.bind.price;
  if (
    receipt.ready !== true ||
    receipt.failure_code !== null ||
    Date.parse(expiresAt) <= Date.parse(checkedAt) ||
    receipt.binding_id !== binding.id ||
    receipt.binding_hash !== binding.binding_hash ||
    receipt.strategy_id !== selection.strategy_id ||
    receipt.recipe !== selection.recipe ||
    receipt.catalog_version !== selection.catalog_version ||
    receipt.recipe_version !== selection.recipe_version ||
    receipt.pricing_version !== selection.pricing_version ||
    receipt.selection_hash !== selection.selection_hash ||
    receipt.price_hash !== price.price_hash
  ) {
    throw new RuntimeContractError("preflight_identity_mismatch", "preflight.receipt");
  }
  if (expectedState.phase === "human_confirmed") {
    const previousReceipt = expectedState.preflight?.receipt;
    if (
      !previousReceipt ||
      receipt.id === previousReceipt.id ||
      receipt.receipt_hash === previousReceipt.receipt_hash ||
      Date.parse(receipt.checked_at) <= Date.parse(previousReceipt.checked_at) ||
      Date.parse(receipt.expires_at) <= Date.parse(previousReceipt.expires_at) ||
      receipt.binding_id !== previousReceipt.binding_id ||
      receipt.binding_hash !== previousReceipt.binding_hash ||
      receipt.strategy_id !== previousReceipt.strategy_id ||
      receipt.recipe !== previousReceipt.recipe ||
      receipt.catalog_version !== previousReceipt.catalog_version ||
      receipt.recipe_version !== previousReceipt.recipe_version ||
      receipt.pricing_version !== previousReceipt.pricing_version ||
      receipt.selection_hash !== previousReceipt.selection_hash ||
      receipt.price_hash !== previousReceipt.price_hash
    ) {
      throw new RuntimeContractError(
        "preflight_refresh_not_new",
        "preflight.receipt",
      );
    }
  }
  const contractSource = exactObject(
    source.contract,
    PREFLIGHT_CONTRACT_KEYS,
    "preflight.contract",
  );
  if (
    contractSource.provider_call_started !== false ||
    contractSource.receipt_single_use !== true ||
    contractSource.browser_price_authority !== false ||
    contractSource.browser_prompt_authority !== false
  ) {
    throw new RuntimeContractError("preflight_contract_invalid", "preflight.contract");
  }
  return deepFreeze({
    ok: true,
    version: source.version,
    replay: requiredBoolean(source.replay, "preflight.replay"),
    receipt,
    provider_preflight: normalizeProviderPreflight(source.provider_preflight),
    launch_enabled: true,
    contract: {
      provider_call_started: false,
      receipt_single_use: true,
      browser_price_authority: false,
      browser_prompt_authority: false,
    },
  });
}

export function normalizeGenerationStrategyPreflightResponse(raw, expectedState) {
  return normalizedResult(normalizePreflightResponse, raw, expectedState);
}

function normalizeSafeStatusPrice(value, expectedState) {
  const source = exactObject(value, SAFE_PRICE_KEYS, "status.price");
  const expected = expectedState.bind?.price;
  if (!expected) {
    throw new RuntimeContractError("status_state_invalid", "expected_state.bind.price");
  }
  const price = {};
  for (const key of SAFE_PRICE_KEYS) {
    if (source[key] !== expected[key]) {
      throw new RuntimeContractError("status_price_mismatch", `status.price.${key}`);
    }
    price[key] = source[key];
  }
  return price;
}

function normalizeStatusJob(value, expectedState) {
  const source = exactObject(value, STATUS_JOB_KEYS, "status.job");
  const status = exactCode(source.status, "status.job.status");
  if (!JOB_STATUSES.has(status)) {
    throw new RuntimeContractError("status_job_status_invalid", "status.job.status");
  }
  const providerStatus = source.provider_status === null
    ? null
    : exactCode(source.provider_status, "status.job.provider_status");
  if (providerStatus !== null && !PROVIDER_STATUSES.has(providerStatus)) {
    throw new RuntimeContractError(
      "status_provider_status_invalid",
      "status.job.provider_status",
    );
  }
  const providerTaskId = nullableExactText(
    source.provider_task_id,
    "status.job.provider_task_id",
    240,
  );
  if (
    (providerStatus === null) !== (providerTaskId === null) ||
    (providerTaskId !== null && providerTaskId.length < 8) ||
    (["queued", "starting"].includes(status) && providerStatus !== null) ||
    (["submitted", "processing", "succeeded"].includes(status) &&
      providerStatus !== status) ||
    (["failed", "cancelled"].includes(status) &&
      providerStatus !== null && providerStatus !== status)
  ) {
    throw new RuntimeContractError("status_job_provider_mismatch", "status.job");
  }
  const estimatedCost = safeInteger(
    source.estimated_cost_minor,
    "status.job.estimated_cost_minor",
    1,
    1_000_000,
  );
  const actualCost = nullableSafeInteger(
    source.actual_cost_minor,
    "status.job.actual_cost_minor",
    0,
    1_000_000,
  );
  const createdAt = requiredTimestamp(source.created_at, "status.job.created_at");
  const updatedAt = requiredTimestamp(source.updated_at, "status.job.updated_at");
  if (
    exactUuid(source.project_id, "status.job.project_id") !==
      expectedState.identity?.project_id ||
    exactUuid(source.campaign_id, "status.job.campaign_id") !==
      expectedState.campaign_id ||
    estimatedCost !== expectedState.bind?.price?.estimated_cost_minor ||
    ![null, 0, estimatedCost].includes(actualCost) ||
    source.currency !== "USD" ||
    Date.parse(updatedAt) < Date.parse(createdAt)
  ) {
    throw new RuntimeContractError("status_job_identity_mismatch", "status.job");
  }
  return {
    id: exactUuid(source.id, "status.job.id"),
    batch_id: exactUuid(source.batch_id, "status.job.batch_id"),
    project_id: source.project_id,
    campaign_id: source.campaign_id,
    status,
    provider_status: providerStatus,
    provider_task_id: providerTaskId,
    estimated_cost_minor: estimatedCost,
    actual_cost_minor: actualCost,
    currency: "USD",
    created_at: createdAt,
    updated_at: updatedAt,
  };
}

function normalizeStatusStrategy(value, expectedState) {
  const source = exactObject(value, STATUS_STRATEGY_KEYS, "status.strategy");
  const binding = expectedState.bind?.binding;
  const selection = expectedState.bind?.selection;
  const receipt = expectedState.preflight?.receipt;
  if (!binding || !selection || !receipt) {
    throw new RuntimeContractError("status_state_invalid", "expected_state");
  }
  const strategy = {
    version: exactText(source.version, "status.strategy.version", 160),
    strategy_id: exactCode(source.strategy_id, "status.strategy.strategy_id"),
    recipe: exactCode(source.recipe, "status.strategy.recipe"),
    catalog_version: exactText(
      source.catalog_version,
      "status.strategy.catalog_version",
      160,
    ),
    recipe_version: exactText(
      source.recipe_version,
      "status.strategy.recipe_version",
      160,
    ),
    pricing_version: exactText(
      source.pricing_version,
      "status.strategy.pricing_version",
      160,
    ),
    binding_id: exactUuid(source.binding_id, "status.strategy.binding_id"),
    binding_hash: exactSha256(
      source.binding_hash,
      "status.strategy.binding_hash",
    ),
    receipt_id: exactUuid(source.receipt_id, "status.strategy.receipt_id"),
    receipt_hash: exactSha256(
      source.receipt_hash,
      "status.strategy.receipt_hash",
    ),
    selection_hash: exactSha256(
      source.selection_hash,
      "status.strategy.selection_hash",
    ),
    price_hash: exactSha256(source.price_hash, "status.strategy.price_hash"),
    strategy_prompt_hash: exactSha256(
      source.strategy_prompt_hash,
      "status.strategy.strategy_prompt_hash",
    ),
  };
  if (
    strategy.version !== "generation-strategy-immutable-execution-v1" ||
    strategy.strategy_id !== selection.strategy_id ||
    strategy.recipe !== selection.recipe ||
    strategy.catalog_version !== selection.catalog_version ||
    strategy.recipe_version !== selection.recipe_version ||
    strategy.pricing_version !== selection.pricing_version ||
    strategy.binding_id !== binding.id ||
    strategy.binding_hash !== binding.binding_hash ||
    strategy.receipt_id !== receipt.id ||
    strategy.receipt_hash !== receipt.receipt_hash ||
    strategy.selection_hash !== selection.selection_hash ||
    strategy.price_hash !== expectedState.bind.price.price_hash
  ) {
    throw new RuntimeContractError("status_strategy_mismatch", "status.strategy");
  }
  return strategy;
}

function normalizeStatusSelection(value, expectedState) {
  const selection = normalizeGenerationStrategySelection(value);
  const identity = expectedState.identity;
  const price = expectedState.bind?.price;
  const dimensionField = hasOwn(selection, "ratio") ? "ratio" : "resolution";
  if (
    canonicalJson(value) !== canonicalJson(selection) ||
    selection.version !== identity?.catalog_version ||
    selection.strategy_id !== identity?.strategy_id ||
    selection.recipe_version !== identity?.recipe_version ||
    selection.duration_seconds !== price?.duration_seconds ||
    selection.audio !== price?.audio ||
    (dimensionField === "ratio"
      ? selection.ratio !== price?.ratio
      : selection.resolution !== price?.resolution)
  ) {
    throw new RuntimeContractError("status_selection_mismatch", "status.selection");
  }
  return selection;
}

function normalizeStatusDispatch(value) {
  if (value === null) return null;
  const source = exactObject(value, STATUS_DISPATCH_KEYS, "status.dispatch");
  const outcome = exactCode(source.outcome, "status.dispatch.outcome");
  if (!["submitted", "ambiguous", "rejected"].includes(outcome)) {
    throw new RuntimeContractError("status_dispatch_outcome_invalid", "status.dispatch.outcome");
  }
  const providerPostStarted = requiredBoolean(
    source.provider_post_started,
    "status.dispatch.provider_post_started",
  );
  const providerHttpStatus = nullableSafeInteger(
    source.provider_http_status,
    "status.dispatch.provider_http_status",
    100,
    599,
  );
  if (
    (outcome === "submitted" &&
      (!providerPostStarted || providerHttpStatus < 200 || providerHttpStatus > 299)) ||
    (outcome === "ambiguous" && !providerPostStarted) ||
    (outcome === "rejected" && !providerPostStarted && providerHttpStatus !== null)
  ) {
    throw new RuntimeContractError("status_dispatch_mismatch", "status.dispatch");
  }
  return {
    result_id: exactUuid(source.result_id, "status.dispatch.result_id"),
    result_hash: exactSha256(source.result_hash, "status.dispatch.result_hash"),
    outcome,
    provider_post_started: providerPostStarted,
    provider_http_status: providerHttpStatus,
    recorded_at: requiredTimestamp(source.recorded_at, "status.dispatch.recorded_at"),
  };
}

function normalizeStatusReconciliation(value) {
  if (value === null) return null;
  if (!isPlainObject(value) || typeof value.required !== "boolean") {
    throw new RuntimeContractError("status_reconciliation_invalid", "status.reconciliation");
  }
  if (value.required) {
    const source = exactObject(
      value,
      STATUS_RECONCILIATION_REQUIRED_KEYS,
      "status.reconciliation",
    );
    return {
      required: true,
      incident_id: exactUuid(source.incident_id, "status.reconciliation.incident_id"),
      reason_code: exactCode(source.reason_code, "status.reconciliation.reason_code"),
      required_at: requiredTimestamp(
        source.required_at,
        "status.reconciliation.required_at",
      ),
    };
  }
  const source = exactObject(
    value,
    STATUS_RECONCILIATION_RESOLVED_KEYS,
    "status.reconciliation",
  );
  const resolution = exactCode(source.resolution, "status.reconciliation.resolution");
  if (!["provider_task_attached", "confirmed_not_submitted"].includes(resolution)) {
    throw new RuntimeContractError(
      "status_reconciliation_resolution_invalid",
      "status.reconciliation.resolution",
    );
  }
  return {
    required: false,
    incident_id: exactUuid(source.incident_id, "status.reconciliation.incident_id"),
    resolution,
    reconciled_at: requiredTimestamp(
      source.reconciled_at,
      "status.reconciliation.reconciled_at",
    ),
  };
}

function normalizeStatusOutput(value) {
  if (value === null) return null;
  const source = exactObject(value, STATUS_OUTPUT_KEYS, "status.output");
  const mimeType = exactText(source.mime_type, "status.output.mime_type", 160);
  if (mimeType !== mimeType.toLowerCase() || !mimeType.startsWith("video/")) {
    throw new RuntimeContractError("status_output_mime_invalid", "status.output.mime_type");
  }
  return {
    media_id: exactUuid(source.media_id, "status.output.media_id"),
    mime_type: mimeType,
    size_bytes: safeInteger(source.size_bytes, "status.output.size_bytes", 1),
  };
}

function normalizeStatusError(value, job, dispatch, reconciliation) {
  if (value === null) return null;
  const source = exactObject(value, STATUS_ERROR_KEYS, "status.error");
  const code = exactCode(source.code, "status.error.code");
  const billingOutcome = source.provider_billing_outcome;
  const confirmedNotSubmitted = billingOutcome === null &&
    code === "provider_submission_not_found" &&
    job.status === "failed" && job.actual_cost_minor === 0 &&
    job.provider_status === null && job.provider_task_id === null &&
    dispatch?.outcome === "ambiguous" &&
    reconciliation?.required === false &&
    reconciliation.resolution === "confirmed_not_submitted";
  if (billingOutcome !== "unknown" && !confirmedNotSubmitted) {
    throw new RuntimeContractError(
      "status_billing_outcome_invalid",
      "status.error.provider_billing_outcome",
    );
  }
  return {
    code,
    provider_billing_outcome: billingOutcome,
  };
}

function normalizeStatusContract(value, job) {
  const source = exactObject(value, STATUS_CONTRACT_KEYS, "status.contract");
  const pollAllowed = ["submitted", "processing"].includes(job.status) &&
    job.provider_task_id !== null;
  if (
    source.recipe_aware !== true ||
    source.legacy_model_catalog_used !== false ||
    source.poll_provider_allowed !== pollAllowed ||
    source.second_post_allowed !== false ||
    source.object_names_returned !== false ||
    source.media_hashes_returned !== false ||
    source.signed_urls_returned !== false ||
    source.manual_human_review_required !== (job.status === "succeeded")
  ) {
    throw new RuntimeContractError("status_contract_invalid", "status.contract");
  }
  return {
    recipe_aware: true,
    legacy_model_catalog_used: false,
    poll_provider_allowed: pollAllowed,
    second_post_allowed: false,
    object_names_returned: false,
    media_hashes_returned: false,
    signed_urls_returned: false,
    manual_human_review_required: job.status === "succeeded",
  };
}

function statusTransitionIsMonotonic(previous, next) {
  if (!previous) return true;
  if (
    previous.job.id !== next.job.id ||
    previous.job.batch_id !== next.job.batch_id ||
    previous.job.created_at !== next.job.created_at ||
    (previous.job.provider_task_id !== null &&
      previous.job.provider_task_id !== next.job.provider_task_id) ||
    (previous.job.actual_cost_minor !== null &&
      previous.job.actual_cost_minor !== next.job.actual_cost_minor) ||
    previous.strategy.strategy_prompt_hash !== next.strategy.strategy_prompt_hash ||
    Date.parse(next.job.updated_at) < Date.parse(previous.job.updated_at)
  ) return false;
  const priorJobStatus = previous.job.status;
  if (
    (TERMINAL_JOB_STATUSES.has(priorJobStatus) && next.job.status !== priorJobStatus) ||
    STATUS_RANK[next.job.status] < STATUS_RANK[priorJobStatus]
  ) return false;
  const priorProvider = previous.job.provider_status;
  const nextProvider = next.job.provider_status;
  if (priorProvider !== null) {
    if (nextProvider === null) return false;
    if (
      TERMINAL_JOB_STATUSES.has(priorProvider) && nextProvider !== priorProvider
    ) return false;
    if (PROVIDER_STATUS_RANK[nextProvider] < PROVIDER_STATUS_RANK[priorProvider]) {
      return false;
    }
  }
  if (
    previous.dispatch !== null &&
    canonicalJson(previous.dispatch) !== canonicalJson(next.dispatch)
  ) return false;
  if (previous.reconciliation?.required === false &&
      canonicalJson(previous.reconciliation) !== canonicalJson(next.reconciliation)) {
    return false;
  }
  if (previous.reconciliation?.required === true) {
    if (next.reconciliation === null) return false;
    if (
      next.reconciliation.required === true &&
      canonicalJson(previous.reconciliation) !== canonicalJson(next.reconciliation)
    ) return false;
    if (
      next.reconciliation.required === false &&
      previous.reconciliation.incident_id !== next.reconciliation.incident_id
    ) return false;
  }
  if (
    previous.output !== null &&
    canonicalJson(previous.output) !== canonicalJson(next.output)
  ) return false;
  if (
    previous.error !== null &&
    canonicalJson(previous.error) !== canonicalJson(next.error)
  ) return false;
  return true;
}

function normalizeStatusResponse(raw, expectedState) {
  if (
    !validRuntimeState(expectedState) ||
    !["start_once", "status"].includes(expectedState.phase) ||
    !expectedState.bind ||
    !expectedState.preflight ||
    !expectedState.campaign_id ||
    !expectedState.start_context_fingerprint
  ) {
    throw new RuntimeContractError("status_state_invalid", "expected_state");
  }
  const source = exactObject(raw, STATUS_TOP_KEYS, "status");
  if (source.ok !== true || source.version !== "generation-strategy-status-response-v1") {
    throw new RuntimeContractError("status_envelope_invalid", "status");
  }
  const job = normalizeStatusJob(source.job, expectedState);
  const strategy = normalizeStatusStrategy(source.strategy, expectedState);
  normalizeStatusSelection(source.selection, expectedState);
  const price = normalizeSafeStatusPrice(source.price, expectedState);
  const dispatch = normalizeStatusDispatch(source.dispatch);
  const reconciliation = normalizeStatusReconciliation(source.reconciliation);
  const output = normalizeStatusOutput(source.output);
  const error = normalizeStatusError(
    source.error,
    job,
    dispatch,
    reconciliation,
  );
  if (
    (job.status === "succeeded") !== (output !== null) ||
    (["failed", "cancelled"].includes(job.status) !== (error !== null)) ||
    (reconciliation?.required === true && dispatch?.outcome !== "ambiguous") ||
    (dispatch?.outcome === "submitted" && job.provider_task_id === null)
  ) {
    throw new RuntimeContractError("status_payload_mismatch", "status");
  }
  const normalized = deepFreeze({
    ok: true,
    version: source.version,
    job,
    strategy,
    price,
    dispatch,
    reconciliation,
    output,
    error,
    contract: normalizeStatusContract(source.contract, job),
  });
  if (!statusTransitionIsMonotonic(expectedState.status, normalized)) {
    throw new RuntimeContractError("status_transition_stale", "status.job.status");
  }
  return normalized;
}

export function normalizeGenerationStrategyStatusResponse(raw, expectedState) {
  return normalizedResult(normalizeStatusResponse, raw, expectedState);
}

export function normalizeGenerationStrategyStartResponse(raw, expectedState) {
  return normalizedResult(normalizeStatusResponse, raw, expectedState);
}

function pristineState() {
  return deepFreeze({
    version: GENERATION_STRATEGY_RUNTIME_VERSION,
    phase: "idle",
    fingerprint: null,
    identity: null,
    bind: null,
    preflight: null,
    campaign_id: null,
    start_context_fingerprint: null,
    start: null,
    status: null,
    start_attempt_idempotency_key: null,
    error: null,
  });
}

export function createGenerationStrategyRuntimeState() {
  return pristineState();
}

function invalidState(state, code, field = "runtime") {
  return deepFreeze({
    ...pristineState(),
    phase: "invalid",
    error: { code, field },
  });
}

function isDeepFrozen(value) {
  return !value || typeof value !== "object" || (
    Object.isFrozen(value) && Object.values(value).every(isDeepFrozen)
  );
}

function validBindStateShape(value) {
  return hasExactObjectKeys(value, BIND_TOP_KEYS) &&
    hasExactObjectKeys(value.binding, BINDING_KEYS) &&
    Array.isArray(value.binding.role_assets) &&
    value.binding.role_assets.every((asset) =>
      hasExactObjectKeys(asset, BINDING_ASSET_KEYS)
    ) &&
    hasExactObjectKeys(value.selection, BIND_SELECTION_KEYS) &&
    hasExactObjectKeys(value.price, PRICE_KEYS) &&
    hasExactObjectKeys(value.contract, BIND_CONTRACT_KEYS);
}

function validPreflightStateShape(value) {
  return hasExactObjectKeys(value, PREFLIGHT_TOP_KEYS) &&
    hasExactObjectKeys(value.receipt, PREFLIGHT_RECEIPT_KEYS) &&
    hasExactObjectKeys(value.provider_preflight, PROVIDER_PREFLIGHT_KEYS) &&
    hasExactObjectKeys(value.contract, PREFLIGHT_CONTRACT_KEYS);
}

function validStatusStateShape(value) {
  if (
    !hasExactObjectKeys(value, SAFE_STATUS_STATE_KEYS) ||
    !hasExactObjectKeys(value.job, STATUS_JOB_KEYS) ||
    !hasExactObjectKeys(value.strategy, STATUS_STRATEGY_KEYS) ||
    !hasExactObjectKeys(value.price, SAFE_PRICE_KEYS) ||
    !hasExactObjectKeys(value.contract, STATUS_CONTRACT_KEYS) ||
    (value.dispatch !== null &&
      !hasExactObjectKeys(value.dispatch, STATUS_DISPATCH_KEYS)) ||
    (value.output !== null && !hasExactObjectKeys(value.output, STATUS_OUTPUT_KEYS)) ||
    (value.error !== null && !hasExactObjectKeys(value.error, STATUS_ERROR_KEYS))
  ) return false;
  return value.reconciliation === null || (
    value.reconciliation.required === true
      ? hasExactObjectKeys(
        value.reconciliation,
        STATUS_RECONCILIATION_REQUIRED_KEYS,
      )
      : value.reconciliation.required === false && hasExactObjectKeys(
        value.reconciliation,
        STATUS_RECONCILIATION_RESOLVED_KEYS,
      )
  );
}

function validRuntimeState(value) {
  if (!isPlainObject(value)) return false;
  const keys = Object.keys(value).sort();
  const expected = [...RUNTIME_STATE_KEYS].sort();
  if (
    keys.length !== expected.length ||
    keys.some((key, index) => key !== expected[index]) ||
    value.version !== GENERATION_STRATEGY_RUNTIME_VERSION ||
    !new Set([
      "idle",
      "selected",
      "bound",
      "preflight_ready",
      "human_confirmed",
      "start_once",
      "status",
      "invalid",
    ]).has(value.phase) ||
    !isDeepFrozen(value)
  ) return false;
  const authorityIsClear = value.fingerprint === null && value.identity === null &&
    value.bind === null && value.preflight === null && value.campaign_id === null &&
    value.start_context_fingerprint === null && value.start === null &&
    value.status === null && value.start_attempt_idempotency_key === null;
  if (value.phase === "idle") return authorityIsClear && value.error === null;
  if (value.phase === "invalid") {
    return authorityIsClear && isPlainObject(value.error) &&
      Object.keys(value.error).sort().join(",") === "code,field" &&
      typeof value.error.code === "string" && typeof value.error.field === "string";
  }
  if (
    typeof value.fingerprint !== "string" ||
    !SHA256_PATTERN.test(value.fingerprint) ||
    !hasExactObjectKeys(value.identity, RUNTIME_IDENTITY_KEYS) ||
    value.error !== null
  ) return false;
  if (value.phase === "selected") {
    return value.bind === null && value.preflight === null && value.campaign_id === null &&
      value.start_context_fingerprint === null && value.start === null &&
      value.status === null && value.start_attempt_idempotency_key === null;
  }
  if (!validBindStateShape(value.bind)) return false;
  if (value.phase === "bound") {
    return value.preflight === null && value.campaign_id === null &&
      value.start_context_fingerprint === null && value.start === null &&
      value.status === null && value.start_attempt_idempotency_key === null;
  }
  if (!validPreflightStateShape(value.preflight)) return false;
  if (value.phase === "preflight_ready") {
    return value.campaign_id === null && value.start_context_fingerprint === null &&
      value.start === null && value.status === null &&
      value.start_attempt_idempotency_key === null;
  }
  if (
    typeof value.campaign_id !== "string" || !UUID_PATTERN.test(value.campaign_id) ||
    typeof value.start_context_fingerprint !== "string" ||
    !SHA256_PATTERN.test(value.start_context_fingerprint)
  ) return false;
  if (value.phase === "human_confirmed") {
    return value.start === null && value.status === null &&
      value.start_attempt_idempotency_key === null;
  }
  if (
    typeof value.start_attempt_idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.start_attempt_idempotency_key)
  ) return false;
  if (value.phase === "start_once") {
    return value.start === null && value.status === null;
  }
  return hasExactObjectKeys(value.start, START_STATE_KEYS) &&
    validStatusStateShape(value.status);
}

function startContextFingerprintForState(state, campaignId) {
  if (!state.bind || !state.preflight) {
    throw new RuntimeContractError("start_state_invalid", "state");
  }
  const campaign = requiredUuid(campaignId, "campaign_id");
  return sha256Hex(canonicalJson({
    version: GENERATION_STRATEGY_RUNTIME_VERSION,
    runtime_fingerprint: state.fingerprint,
    organization_id: state.identity.organization_id,
    project_id: state.identity.project_id,
    spec_id: state.identity.spec_id,
    spec_version: state.identity.spec_version,
    spec_hash: state.identity.spec_hash,
    campaign_id: campaign,
    binding_id: state.bind.binding.id,
    binding_hash: state.bind.binding.binding_hash,
    receipt_id: state.preflight.receipt.id,
    receipt_hash: state.preflight.receipt.receipt_hash,
    selection_hash: state.bind.selection.selection_hash,
    price_hash: state.bind.price.price_hash,
  }));
}

export function reduceGenerationStrategyRuntimeState(state, action) {
  if (!validRuntimeState(state)) return pristineState();
  if (!isPlainObject(action) || typeof action.type !== "string") {
    return invalidState(state, "runtime_action_invalid", "action");
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.reset) {
    try {
      exactObject(action, ["type"], "action");
      return pristineState();
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.invalidate) {
    try {
      const source = exactObject(action, ["type", "reason"], "action");
      return invalidState(
        state,
        requiredCode(source.reason, "action.reason"),
        "context",
      );
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.select) {
    try {
      const source = exactObject(action, ["type", "context"], "action");
      const fingerprint = createGenerationStrategyRuntimeFingerprint(source.context);
      if (!fingerprint.ok) {
        return invalidState(
          state,
          fingerprint.error.code,
          fingerprint.error.field,
        );
      }
      return deepFreeze({
        ...pristineState(),
        phase: "selected",
        fingerprint: fingerprint.fingerprint,
        identity: fingerprint.identity,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved) {
    try {
      const source = exactObject(
        action,
        ["type", "fingerprint", "context", "response"],
        "action",
      );
      const responseFingerprint = exactSha256(
        source.fingerprint,
        "action.fingerprint",
      );
      if (
        state.phase !== "selected" ||
        !state.fingerprint ||
        responseFingerprint !== state.fingerprint ||
        !state.identity
      ) {
        return invalidState(state, "runtime_response_stale", "action.fingerprint");
      }
      const requestFingerprint = createGenerationStrategyRuntimeFingerprint(source.context);
      if (
        !requestFingerprint.ok ||
        requestFingerprint.fingerprint !== state.fingerprint
      ) {
        return invalidState(state, "runtime_response_stale", "action.context");
      }
      const normalized = normalizeGenerationStrategyBindResponse(
        source.response,
        source.context,
      );
      if (!normalized.ok) {
        return invalidState(
          state,
          normalized.error.code,
          normalized.error.field,
        );
      }
      return deepFreeze({
        ...state,
        phase: "bound",
        bind: normalized.value,
        error: null,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (
    action.type ===
      GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightRefreshRequested
  ) {
    try {
      const source = exactObject(
        action,
        ["type", "fingerprint", "receipt_id", "receipt_hash"],
        "action",
      );
      if (
        state.phase !== "preflight_ready" ||
        exactSha256(source.fingerprint, "action.fingerprint") !==
          state.fingerprint ||
        exactUuid(source.receipt_id, "action.receipt_id") !==
          state.preflight?.receipt?.id ||
        exactSha256(source.receipt_hash, "action.receipt_hash") !==
          state.preflight?.receipt?.receipt_hash
      ) {
        return invalidState(state, "runtime_response_stale", "action.receipt_id");
      }
      return deepFreeze({
        ...state,
        phase: "bound",
        preflight: null,
        error: null,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved) {
    try {
      const source = exactObject(
        action,
        ["type", "fingerprint", "response"],
        "action",
      );
      const refreshesHumanConfirmation = state.phase === "human_confirmed";
      if (
        !["bound", "human_confirmed"].includes(state.phase) ||
        exactSha256(source.fingerprint, "action.fingerprint") !== state.fingerprint
      ) {
        return invalidState(state, "runtime_response_stale", "action.fingerprint");
      }
      const normalized = normalizeGenerationStrategyPreflightResponse(
        source.response,
        state,
      );
      if (!normalized.ok) {
        return invalidState(state, normalized.error.code, normalized.error.field);
      }
      const nextState = {
        ...state,
        phase: refreshesHumanConfirmation ? "human_confirmed" : "preflight_ready",
        preflight: normalized.value,
        error: null,
      };
      if (refreshesHumanConfirmation) {
        nextState.start_context_fingerprint = startContextFingerprintForState(
          nextState,
          state.campaign_id,
        );
      }
      return deepFreeze(nextState);
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed) {
    try {
      const source = exactObject(
        action,
        [
          "type",
          "fingerprint",
          "campaign_id",
          "spend_confirmation",
          "confirmation",
        ],
        "action",
      );
      const campaignId = exactUuid(source.campaign_id, "action.campaign_id");
      if (
        state.phase !== "preflight_ready" ||
        exactSha256(source.fingerprint, "action.fingerprint") !== state.fingerprint ||
        source.confirmation !== true ||
        exactText(
          source.spend_confirmation,
          "action.spend_confirmation",
          180,
        ) !== state.bind.price.spend_confirmation
      ) {
        return invalidState(state, "runtime_confirmation_mismatch", "action");
      }
      return deepFreeze({
        ...state,
        phase: "human_confirmed",
        campaign_id: campaignId,
        start_context_fingerprint: startContextFingerprintForState(
          state,
          campaignId,
        ),
        error: null,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested) {
    try {
      const source = exactObject(
        action,
        [
          "type",
          "fingerprint",
          "start_context_fingerprint",
          "campaign_id",
          "idempotency_key",
        ],
        "action",
      );
      if (
        state.phase !== "human_confirmed" ||
        exactSha256(source.fingerprint, "action.fingerprint") !== state.fingerprint ||
        exactSha256(
          source.start_context_fingerprint,
          "action.start_context_fingerprint",
        ) !== state.start_context_fingerprint ||
        exactUuid(source.campaign_id, "action.campaign_id") !== state.campaign_id
      ) {
        return invalidState(state, "runtime_start_context_mismatch", "action");
      }
      return deepFreeze({
        ...state,
        phase: "start_once",
        start_attempt_idempotency_key: requiredIdempotencyKey(
          source.idempotency_key,
          "action.idempotency_key",
        ),
        error: null,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved) {
    try {
      const source = exactObject(
        action,
        [
          "type",
          "fingerprint",
          "start_context_fingerprint",
          "idempotency_key",
          "response",
        ],
        "action",
      );
      if (
        state.phase !== "start_once" ||
        exactSha256(source.fingerprint, "action.fingerprint") !== state.fingerprint ||
        exactSha256(
          source.start_context_fingerprint,
          "action.start_context_fingerprint",
        ) !== state.start_context_fingerprint ||
        requiredIdempotencyKey(source.idempotency_key, "action.idempotency_key") !==
          state.start_attempt_idempotency_key
      ) {
        return invalidState(state, "runtime_response_stale", "action");
      }
      const normalized = normalizeGenerationStrategyStartResponse(
        source.response,
        state,
      );
      if (!normalized.ok) {
        return invalidState(state, normalized.error.code, normalized.error.field);
      }
      return deepFreeze({
        ...state,
        phase: "status",
        start: {
          generation_job_id: normalized.value.job.id,
          batch_id: normalized.value.job.batch_id,
        },
        status: normalized.value,
        error: null,
      });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  if (action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.statusResolved) {
    try {
      const source = exactObject(
        action,
        [
          "type",
          "fingerprint",
          "start_context_fingerprint",
          "generation_job_id",
          "response",
        ],
        "action",
      );
      if (
        state.phase !== "status" ||
        exactSha256(source.fingerprint, "action.fingerprint") !== state.fingerprint ||
        exactSha256(
          source.start_context_fingerprint,
          "action.start_context_fingerprint",
        ) !== state.start_context_fingerprint ||
        exactUuid(source.generation_job_id, "action.generation_job_id") !==
          state.status.job.id
      ) {
        return invalidState(state, "runtime_response_stale", "action");
      }
      const normalized = normalizeGenerationStrategyStatusResponse(
        source.response,
        state,
      );
      if (!normalized.ok) {
        return invalidState(state, normalized.error.code, normalized.error.field);
      }
      return deepFreeze({ ...state, status: normalized.value, error: null });
    } catch {
      return invalidState(state, "runtime_action_invalid", "action");
    }
  }
  return invalidState(state, "runtime_action_unsupported", "action.type");
}

export function invalidateGenerationStrategyRuntimeState(
  state,
  reason = "generation_strategy_context_changed",
) {
  return reduceGenerationStrategyRuntimeState(state, {
    type: GENERATION_STRATEGY_RUNTIME_ACTIONS.invalidate,
    reason,
  });
}

export function generationStrategyRuntimeBindRequest(raw, idempotencyKey) {
  const fingerprint = createGenerationStrategyRuntimeFingerprint(raw);
  if (!fingerprint.ok) {
    return deepFreeze({
      ok: false,
      fingerprint: null,
      start_context_fingerprint: null,
      request: null,
      error: fingerprint.error,
    });
  }
  try {
    const context = normalizeRuntimeContext(raw);
    return requestResult({
      action: "strategy_bind",
      organization_id: context.organization_id,
      project_id: context.project_id,
      spec_id: context.spec_id,
      spec_version: context.spec_version,
      spec_hash: context.spec_hash,
      generation_strategy: context.generation_strategy,
      // Движок появляется в запросе только когда он выбран: сервер отличает
      // «движок не выбран» от «выбран» по наличию поля, а не по содержимому.
      ...(context.engine === undefined ? {} : { engine: context.engine }),
      // Ведущий «Дуэта» — так же по наличию поля. Сервер требует его у дуэта и
      // ЗАПРЕЩАЕТ остальным стратегиям: подписанный ведущий у «Копии» означал
      // бы подписанный факт, которого в запросе к провайдеру не будет.
      ...(context.duet_presenter_id === undefined
        ? {}
        : { duet_presenter_id: context.duet_presenter_id }),
      confirmation: true,
      idempotency_key: requiredIdempotencyKey(idempotencyKey),
    }, fingerprint.fingerprint);
  } catch (error) {
    return requestFailure(error, "bind_request_invalid", "bind_request");
  }
}

export function generationStrategyRuntimePreflightRequest(state, idempotencyKey) {
  try {
    if (
      !validRuntimeState(state) ||
      !["bound", "human_confirmed"].includes(state.phase)
    ) {
      throw new RuntimeContractError("preflight_state_invalid", "state");
    }
    return requestResult({
      action: "strategy_preflight",
      organization_id: state.identity.organization_id,
      project_id: state.identity.project_id,
      spec_id: state.identity.spec_id,
      spec_version: state.identity.spec_version,
      spec_hash: state.identity.spec_hash,
      binding_id: state.bind.binding.id,
      binding_hash: state.bind.binding.binding_hash,
      selection_hash: state.bind.selection.selection_hash,
      price_hash: state.bind.price.price_hash,
      spend_confirmation: state.bind.price.spend_confirmation,
      confirmation: true,
      idempotency_key: requiredIdempotencyKey(idempotencyKey),
    }, state.fingerprint, state.phase === "human_confirmed"
      ? state.start_context_fingerprint
      : null);
  } catch (error) {
    return requestFailure(error, "preflight_request_invalid", "preflight_request");
  }
}

export function generationStrategyRuntimeStartRequest(
  state,
  campaignId,
  idempotencyKey,
) {
  try {
    const campaign = requiredUuid(campaignId, "campaign_id");
    if (
      !validRuntimeState(state) ||
      state.phase !== "human_confirmed" ||
      campaign !== state.campaign_id ||
      startContextFingerprintForState(state, campaign) !==
        state.start_context_fingerprint
    ) {
      throw new RuntimeContractError("start_context_mismatch", "state");
    }
    return requestResult({
      action: "strategy_start",
      organization_id: state.identity.organization_id,
      project_id: state.identity.project_id,
      spec_id: state.identity.spec_id,
      spec_version: state.identity.spec_version,
      spec_hash: state.identity.spec_hash,
      binding_id: state.bind.binding.id,
      binding_hash: state.bind.binding.binding_hash,
      selection_hash: state.bind.selection.selection_hash,
      price_hash: state.bind.price.price_hash,
      spend_confirmation: state.bind.price.spend_confirmation,
      confirmation: true,
      receipt_id: state.preflight.receipt.id,
      receipt_hash: state.preflight.receipt.receipt_hash,
      campaign_id: campaign,
      idempotency_key: requiredIdempotencyKey(idempotencyKey),
    }, state.fingerprint, state.start_context_fingerprint);
  } catch (error) {
    return requestFailure(error, "start_request_invalid", "start_request");
  }
}

export function generationStrategyRuntimeStatusRequest(state) {
  try {
    if (!validRuntimeState(state) || state.phase !== "status" || !state.status) {
      throw new RuntimeContractError("status_state_invalid", "state");
    }
    return requestResult({
      action: "strategy_status",
      organization_id: state.identity.organization_id,
      project_id: state.identity.project_id,
      generation_job_id: state.status.job.id,
    }, state.fingerprint, state.start_context_fingerprint);
  } catch (error) {
    return requestFailure(error, "status_request_invalid", "status_request");
  }
}

export function generationStrategyRuntimeSafeProjection(state) {
  if (!validRuntimeState(state)) return null;
  const bind = state.bind;
  const preflight = state.preflight;
  const status = state.status;
  return deepFreeze({
    version: state.version,
    phase: state.phase,
    fingerprint: state.fingerprint,
    identity: state.identity ? { ...state.identity } : null,
    binding: bind ? {
      id: bind.binding.id,
      binding_hash: bind.binding.binding_hash,
      selection_hash: bind.selection.selection_hash,
      bound_at: bind.binding.bound_at,
    } : null,
    price: bind ? {
      price_hash: bind.price.price_hash,
      strategy_id: bind.price.strategy_id,
      recipe: bind.price.recipe,
      duration_seconds: bind.price.duration_seconds,
      resolution: bind.price.resolution,
      ratio: bind.price.ratio,
      audio: bind.price.audio,
      estimated_credits: bind.price.estimated_credits,
      estimated_cost_minor: bind.price.estimated_cost_minor,
      estimated_cost_usd: bind.price.estimated_cost_usd,
      currency: bind.price.currency,
      spend_confirmation: bind.price.spend_confirmation,
    } : null,
    readiness: preflight ? {
      receipt_id: preflight.receipt.id,
      receipt_hash: preflight.receipt.receipt_hash,
      ready: preflight.receipt.ready,
      checked_at: preflight.receipt.checked_at,
      expires_at: preflight.receipt.expires_at,
      provider_preflight: { ...preflight.provider_preflight },
      launch_enabled: preflight.launch_enabled,
    } : null,
    campaign_id: state.campaign_id,
    start_context_fingerprint: state.start_context_fingerprint,
    job: status ? {
      id: status.job.id,
      batch_id: status.job.batch_id,
      status: status.job.status,
      provider_status: status.job.provider_status,
      estimated_cost_minor: status.job.estimated_cost_minor,
      actual_cost_minor: status.job.actual_cost_minor,
      currency: status.job.currency,
      created_at: status.job.created_at,
      updated_at: status.job.updated_at,
    } : null,
    reconciliation: status?.reconciliation || null,
    output: status?.output || null,
    error: state.error || status?.error || null,
    can_preflight: state.phase === "bound",
    can_confirm: state.phase === "preflight_ready",
    can_start: state.phase === "human_confirmed",
    start_reserved: state.phase === "start_once",
    can_poll: state.phase === "status" && status.contract.poll_provider_allowed,
  });
}
