/*
 * Runtime-only contract readers for the generation-strategy Edge owner.
 *
 * The database functions behind these readers are service-role boundaries.
 * Every reader therefore fails closed on an unexpected key, version, identity
 * or safety flag before any provider request can be constructed.  This module
 * is deliberately pure: it has no environment, database, storage or network
 * access and can be exercised by the Node contract harness.
 */

import {
  FAL_GROK_IMAGINE_PER_SECOND_PRICING_VERSION,
  FAL_GROK_IMAGINE_REFERENCE_MODEL,
  FAL_HAPPY_HORSE_PER_SECOND_PRICING_VERSION,
  FAL_HAPPY_HORSE_REFERENCE_MODEL,
  FAL_HAPPY_HORSE_REFERENCE_PER_SECOND_PRICING_VERSION,
  FAL_HAPPY_HORSE_VIDEO_EDIT_MODEL,
  FAL_KLING_O3_STANDARD_EDIT_MODEL,
  FAL_KLING_STANDARD_PER_SECOND_PRICING_VERSION,
  FAL_MINIMAX_H3_PER_SECOND_PRICING_VERSION,
  FAL_MINIMAX_H3_REFERENCE_MODEL,
  FAL_PER_SECOND_PRICING_VERSION,
  FAL_RECIPE_PRICING_VERSION,
  FAL_SEEDANCE_2_5_PER_SECOND_PRICING_VERSION,
  FAL_SEEDANCE_2_5_REFERENCE_MODEL,
  GENERATION_STRATEGY_CATALOG_VERSION,
  generationStrategyCatalogEntry,
  generationStrategyDurationBounds,
  HEYGEN_PER_SECOND_PRICING_VERSION,
  isKnownStrategyPricingVersion,
  isKnownStrategyProvider,
  RUNWAY_RECIPE_PRICING_VERSION,
  RUNWAY_RECIPE_VERSION,
  validateGenerationStrategySelection,
} from "./generation-strategy-catalog.js";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const FAL_REQUEST_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256 = /^[0-9a-f]{64}$/u;
const TASK_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const SAFE_CODE = /^[a-z][a-z0-9_]{1,95}$/u;
// fal exposes a machine-readable `error_type` on terminal COMPLETED statuses.
// Accept only a short identifier token. Human `error`/`detail` prose, URLs and
// arbitrary provider payloads must never become a ledger or diagnostic code.
const FAL_ERROR_TYPE =
  /^[A-Za-z0-9](?:[A-Za-z0-9_.:-]{0,78}[A-Za-z0-9])?$/u;
const FAL_QUEUE_ORIGIN = "https://queue.fal.run";
const FAL_PLATFORM_API_ORIGIN = "https://api.fal.ai";
// Рецепты, которые правят готовый ролик, а не собирают новый. У них кадр задаёт
// исходник, поэтому снимок цены несёт ratio = "source".
const RESOLUTION_FRAMED_RECIPES = new Set(["product_swap", "product_ugc"]);

const PROVIDER_PATHS = Object.freeze({
  viral_avatar_ugc: "/v1/recipes/product_ugc",
  // Product Swap dispatches to the real Runway video_to_video endpoint
  // (Gen-4 Aleph). The /v1/recipes/* paths do not exist on the provider.
  viral_product_swap: "/v1/video_to_video",
  viral_rebuild: "/v1/recipes/product_ad",
});
const RECIPES = Object.freeze({
  viral_avatar_ugc: "product_ugc",
  viral_product_swap: "product_swap",
  viral_rebuild: "product_ad",
});
// Exact server-executable policy routes.  The database carries prices and the
// enabled/recommended switches, but an enabled row is not sufficient by
// itself: this code must know the exact provider/model/path tuple before it
// can accept launch authority.  Unknown tuples fail closed.
const PROVIDER_POLICY_ROUTES = Object.freeze({
  viral_avatar_ugc: Object.freeze({
    // «Дуэт» исполняет HeyGen: он делает ГОВОРЯЩЕГО ВЕДУЩЕГО, а комментируемый
    // ролик остаётся нетронутым и соединяется с ведущим у нас. Провайдер не
    // получает ни одного медиа — только текст речи и постоянную личность.
    //
    // Прежняя строка называла runway:gen4_turbo по адресу /v1/recipes/
    // product_ugc. Такого маршрута нет ни в реестре, ни у самого провайдера:
    // пути /v1/recipes/* Runway не существуют. Дуэт упирался в этот запрет
    // ПОСЛЕ резерва денег, то есть оставлял повисшую бронь.
    // С 23.08.2026 — v2: фоновое видео + ведущий в углу, готовый MP4.
    "heygen:avatar_v3": Object.freeze({
      providerPath: "/v2/video/generate",
      pollKind: "heygen_video",
      pricingVersion: HEYGEN_PER_SECOND_PRICING_VERSION,
    }),
  }),
  viral_product_swap: Object.freeze({
    "runway:aleph2": Object.freeze({
      providerPath: "/v1/video_to_video",
      pollKind: "runway_task",
      pricingVersion: RUNWAY_RECIPE_PRICING_VERSION,
    }),
    "fal:fal-ai/pika/v2/pikaswaps": Object.freeze({
      providerPath: "fal-ai/pika/v2/pikaswaps",
      pollKind: "fal_request",
      pricingVersion: FAL_RECIPE_PRICING_VERSION,
    }),
    "fal:fal-ai/kling-video/o3/pro/video-to-video/edit": Object.freeze({
      providerPath: "fal-ai/kling-video/o3/pro/video-to-video/edit",
      pollKind: "fal_request",
      pricingVersion: FAL_PER_SECOND_PRICING_VERSION,
    }),
    // Движки, заведённые 23.08.2026. Имя модели берётся из каталога, чтобы
    // адрес отправки, адрес опроса и форма тела были одной и той же строкой.
    [`fal:${FAL_KLING_O3_STANDARD_EDIT_MODEL}`]: Object.freeze({
      providerPath: FAL_KLING_O3_STANDARD_EDIT_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_KLING_STANDARD_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_HAPPY_HORSE_VIDEO_EDIT_MODEL}`]: Object.freeze({
      providerPath: FAL_HAPPY_HORSE_VIDEO_EDIT_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_HAPPY_HORSE_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_SEEDANCE_2_5_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_SEEDANCE_2_5_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_SEEDANCE_2_5_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_MINIMAX_H3_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_MINIMAX_H3_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_MINIMAX_H3_PER_SECOND_PRICING_VERSION,
    }),
  }),
  viral_rebuild: Object.freeze({
    "runway:gen4_turbo": Object.freeze({
      providerPath: "/v1/recipes/product_ad",
      pollKind: "runway_task",
      pricingVersion: RUNWAY_RECIPE_PRICING_VERSION,
    }),
    // Движки «Создания» на fal, заведены 23.08.2026 (миграция 202608230021).
    [`fal:${FAL_MINIMAX_H3_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_MINIMAX_H3_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_MINIMAX_H3_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_GROK_IMAGINE_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_GROK_IMAGINE_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_GROK_IMAGINE_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_HAPPY_HORSE_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_HAPPY_HORSE_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_HAPPY_HORSE_REFERENCE_PER_SECOND_PRICING_VERSION,
    }),
    [`fal:${FAL_SEEDANCE_2_5_REFERENCE_MODEL}`]: Object.freeze({
      providerPath: FAL_SEEDANCE_2_5_REFERENCE_MODEL,
      pollKind: "fal_request",
      pricingVersion: FAL_SEEDANCE_2_5_PER_SECOND_PRICING_VERSION,
    }),
  }),
});
const FAL_QUEUE_MODEL_PATHS = new Set(
  Object.values(PROVIDER_POLICY_ROUTES).flatMap((routes) =>
    Object.values(routes)
      .filter((route) => route.pollKind === "fal_request")
      .map((route) => route.providerPath)
  ),
);
const DETERMINISTIC_REJECTION = new Set([
  400,
  401,
  402,
  403,
  404,
  405,
  422,
  429,
]);

function record(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exact(value, keys) {
  if (!record(value)) return false;
  const actual = Object.keys(value);
  const allowed = new Set(keys);
  return actual.length === allowed.size &&
    actual.every((key) => allowed.has(key));
}

function uuid(value) {
  return typeof value === "string" && UUID.test(value);
}

function hash(value) {
  return typeof value === "string" && SHA256.test(value);
}

function timestamp(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function integer(value, minimum = 0, maximum = Number.MAX_SAFE_INTEGER) {
  return Number.isSafeInteger(value) && value >= minimum && value <= maximum;
}

// Длительность в пределах СВОЕЙ стратегии. Незнакомая стратегия предела не
// имеет, и это отказ, а не свобода: без строки реестра сказать, сколько секунд
// допустимо, нечем.
function durationWithinStrategyBounds(strategyId, value) {
  const bounds = generationStrategyDurationBounds(strategyId);
  if (bounds === null) return false;
  return integer(value, bounds.minimum, bounds.maximum);
}

function forbiddenTextControl(value) {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (
      code === 0x7f ||
      (code <= 0x1f && code !== 0x09 && code !== 0x0a && code !== 0x0d)
    ) return true;
  }
  return false;
}

function text(value, minimum, maximum) {
  return typeof value === "string" && value === value.trim() &&
    value.length >= minimum && value.length <= maximum &&
    !forbiddenTextControl(value);
}

// Stable strategy/recipe identity is independent from the selected provider
// route.  The public catalog still describes the recipe family with its
// original Runway defaults, while provider/model/path/pricing is validated by
// PROVIDER_POLICY_ROUTES at the policy boundary below.
function strategyRecipeIdentity(strategyId, recipe) {
  if (RECIPES[strategyId] !== recipe) return false;
  const entry = generationStrategyCatalogEntry(strategyId);
  return entry?.recipe === recipe &&
    entry.recipe_version === RUNWAY_RECIPE_VERSION;
}

function immutableStrategy(value, withJobSnapshot) {
  const common = [
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
    "campaign_id",
  ];
  const keys = withJobSnapshot
    ? [
      ...common,
      "spend_confirmation",
      "job_strategy_snapshot_id",
      "job_strategy_snapshot_hash",
    ]
    : common;
  return exact(value, keys) &&
    value.version === "generation-strategy-immutable-execution-v1" &&
    strategyRecipeIdentity(value.strategy_id, value.recipe) &&
    value.catalog_version === GENERATION_STRATEGY_CATALOG_VERSION &&
    value.recipe_version === RUNWAY_RECIPE_VERSION &&
    isKnownStrategyPricingVersion(value.pricing_version) &&
    uuid(value.binding_id) && hash(value.binding_hash) &&
    uuid(value.receipt_id) && hash(value.receipt_hash) &&
    hash(value.selection_hash) && hash(value.price_hash) &&
    hash(value.strategy_prompt_hash) && uuid(value.campaign_id) &&
    (!withJobSnapshot || (
      text(value.spend_confirmation, 16, 180) &&
      uuid(value.job_strategy_snapshot_id) &&
      hash(value.job_strategy_snapshot_hash)
    ));
}

function recipeContext(value, expectedStrategy) {
  if (
    !exact(value, [
      "strategyVersion",
      "strategyId",
      "recipe",
      "recipeVersion",
      "durationSeconds",
      "audio",
      "ratio",
      "resolution",
      "productInfo",
      "productInfoHash",
      "userConcept",
      "userConceptHash",
    ])
  ) return null;
  // Предел длительности — свойство стратегии, а не общее число. «Дуэт»
  // комментирует чужой ролик целиком, и пятнадцатисекундный потолок отвергал
  // бы его уже ПОСЛЕ резерва денег. Незнакомая стратегия предела не получает.
  if (
    value.strategyVersion !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.recipeVersion !== RUNWAY_RECIPE_VERSION ||
    value.strategyId !== expectedStrategy.strategy_id ||
    value.recipe !== expectedStrategy.recipe ||
    !strategyRecipeIdentity(value.strategyId, value.recipe) ||
    !durationWithinStrategyBounds(value.strategyId, value.durationSeconds) ||
    typeof value.audio !== "boolean"
  ) return null;
  // Кадр приходит ИЗ ИСХОДНИКА у обеих правок готового видео: и «Копия», и
  // «Дуэт» отдают вертикаль исходного ролика, а не выбирают её. Развилка
  // опиралась на один product_swap, поэтому дуэт попадал в чужую половину и
  // падал на требовании resolution === null — снова после резерва.
  const sourceFramed = value.recipe === "product_swap" ||
    value.recipe === "product_ugc";
  if (sourceFramed) {
    // The swap price snapshot stores ratio as the literal marker "source"
    // (output follows the source video); the SQL attempt context forwards it
    // verbatim. Rejecting it here killed every paid dispatch before the
    // provider POST (generation_dispatch_state_unavailable with a dangling
    // attempt). Both the marker and null are valid for product_swap.
    // У «Дуэта» userConcept — это РЕЧЬ ведущего, а не задание модели: пустая
    // речь означает, что платить пришлось бы за молчание. Поблажка «прежних
    // запусков» принадлежит «Копии» и только ей.
    //
    // Верхняя граница длины остаётся общей и намеренно широкой. Настоящий
    // предел речи — длительность × 15 знаков — держит снимок указания в базе
    // (202608230004), и повторять его здесь значило бы завести второй источник
    // одного правила.
    const legacyConcept = value.recipe === "product_swap" &&
      value.userConcept === null && value.userConceptHash === null;
    const approvedConcept =
      text(value.userConcept, 1, 3_500) && hash(value.userConceptHash);
    const legacyProduct =
      value.productInfo === null && value.productInfoHash === null;
    const approvedProduct =
      text(value.productInfo, 1, 2_500) && hash(value.productInfoHash);
    if (
      !(value.ratio === null || value.ratio === "source") ||
      !new Set(["720p", "1080p"]).has(value.resolution) ||
      !(legacyConcept || approvedConcept) ||
      !(legacyProduct || approvedProduct)
    ) return null;
  } else {
    if (
      value.resolution !== null || !text(value.ratio, 3, 16) ||
      !text(value.productInfo, 1, 2_500) || !hash(value.productInfoHash) ||
      !text(value.userConcept, 1, 3_500) || !hash(value.userConceptHash)
    ) return null;
  }
  return value;
}

async function promptTextHashMatches(value, expectedHash, maximum) {
  if (value === null || expectedHash === null) {
    return value === null && expectedHash === null;
  }
  if (!text(value, 1, maximum) || !hash(expectedHash)) return false;
  try {
    const digest = await globalThis.crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(value),
    );
    const actualHash = Array.from(new Uint8Array(digest), (byte) =>
      byte.toString(16).padStart(2, "0")
    ).join("");
    return actualHash === expectedHash;
  } catch {
    return false;
  }
}

// Cryptographic half of the recipe-context reader. The structural readers
// above require exact null/null or text/hash pairs; this async seam verifies
// that each server-returned hash belongs to its accompanying text before any
// provider request can be constructed. Missing WebCrypto fails closed.
export async function generationStrategyPromptHashesMatch(recipeContext) {
  if (!record(recipeContext)) return false;
  return await promptTextHashMatches(
    recipeContext.productInfo,
    recipeContext.productInfoHash,
    2_500,
  ) && await promptTextHashMatches(
    recipeContext.userConcept,
    recipeContext.userConceptHash,
    3_500,
  );
}

function assetContext(value, strategyId) {
  if (!Array.isArray(value) || value.length < 1 || value.length > 16) {
    return null;
  }
  const output = [];
  let previousOrdinal = 0;
  const counts = new Map();
  for (const asset of value) {
    if (
      !exact(asset, [
        "role",
        "selection_ordinal",
        "media_object_id",
        "bucket_id",
        "object_name",
        "sha256",
        "mime_type",
        "size_bytes",
        "product_id",
        "view",
        "provider_field",
      ])
    ) return null;
    if (
      !integer(asset.selection_ordinal, 1, 32) ||
      asset.selection_ordinal <= previousOrdinal ||
      !uuid(asset.media_object_id) ||
      asset.bucket_id !== "contentengine-private" ||
      !text(asset.object_name, 3, 1_024) || hash(asset.sha256) === false ||
      !text(asset.mime_type, 3, 100) ||
      !integer(asset.size_bytes, 1, 52_428_800) ||
      !(asset.product_id === null || uuid(asset.product_id)) ||
      !(asset.view === null ||
        new Set(["front", "side", "back"]).has(asset.view))
    ) return null;
    // У «Дуэта» исходник провайдеру НЕ уходит: он подложка для сборки и
    // источник длительности. Поэтому поля провайдера у него нет — null.
    const expectedFields = strategyId === "viral_avatar_ugc"
      ? { source_video: null }
      : strategyId === "viral_product_swap"
      ? {
        source_video: "referenceVideo",
        original_product_image: "originalProductImage",
        new_product_image: "newProductImages",
      }
      : { product_image: "productImages", style_image: "styleImages" };
    if (expectedFields[asset.role] !== asset.provider_field) return null;
    if (
      (asset.role === "source_video" && asset.mime_type !== "video/mp4") ||
      (asset.role !== "source_video" && !new Set([
        "image/jpeg",
        "image/png",
        "image/webp",
      ]).has(asset.mime_type)) ||
      (asset.view !== null && asset.role !== "new_product_image")
    ) return null;
    previousOrdinal = asset.selection_ordinal;
    counts.set(asset.role, (counts.get(asset.role) || 0) + 1);
    output.push(asset);
  }
  const valid = strategyId === "viral_avatar_ugc"
    ? counts.get("source_video") === 1 && value.length === 1
    : strategyId === "viral_product_swap"
    ? counts.get("source_video") === 1 &&
      counts.get("original_product_image") === 1 &&
      (counts.get("new_product_image") || 0) >= 1 &&
      (counts.get("new_product_image") || 0) <= 10 &&
      value.length === 2 + counts.get("new_product_image")
    : (counts.get("product_image") || 0) >= 1 &&
      (counts.get("product_image") || 0) <= 10 &&
      (counts.get("style_image") || 0) <= 4 &&
      value.length === (counts.get("product_image") || 0) +
          (counts.get("style_image") || 0);
  return valid ? output : null;
}

export function readGenerationStrategyProbeContext(value, expected) {
  if (
    !exact(value, ["ok", "version", "media", "probe_contract"]) ||
    value.ok !== true ||
    value.version !== "generation-strategy-media-probe-context-response-v1" ||
    !exact(value.media, [
      "media_id",
      "bucket_id",
      "object_name",
      "sha256",
      "mime_type",
      "size_bytes",
      "attachment_id",
      "attachment_hash",
    ]) || value.media.media_id !== expected.mediaId ||
    value.media.bucket_id !== "contentengine-private" ||
    !text(value.media.object_name, 3, 1_024) || !hash(value.media.sha256) ||
    value.media.mime_type !== "video/mp4" ||
    !integer(value.media.size_bytes, 1, 33_554_432) ||
    !uuid(value.media.attachment_id) || !hash(value.media.attachment_hash) ||
    !exact(value.probe_contract, [
      "parser_version",
      "max_bytes",
      "full_object_sha256_required",
      "single_mvhd_required",
      "fragmented_mp4_allowed",
      "browser_measurement_accepted",
      "provider_call_started",
    ]) || value.probe_contract.parser_version !== "iso-bmff-mvhd-v1" ||
    value.probe_contract.max_bytes !== 33_554_432 ||
    value.probe_contract.full_object_sha256_required !== true ||
    value.probe_contract.single_mvhd_required !== true ||
    value.probe_contract.fragmented_mp4_allowed !== false ||
    value.probe_contract.browser_measurement_accepted !== false ||
    value.probe_contract.provider_call_started !== false
  ) return null;
  return value.media;
}

export function publicGenerationStrategyProbeResult(value, expected) {
  if (
    !exact(value, ["ok", "version", "replay", "duration", "contract"]) ||
    value.ok !== true ||
    value.version !== "generation-strategy-media-duration-record-response-v1" ||
    typeof value.replay !== "boolean" || !exact(value.duration, [
      "media_id",
      "attachment_id",
      "attachment_hash",
      "media_sha256",
      "size_bytes",
      "parser_version",
      "timescale",
      "duration_units",
      "duration_ms",
      "duration_seconds",
      "verification_method",
      "evidence_hash",
      "verification_hash",
      "verified_at",
    ]) || value.duration.media_id !== expected.mediaId ||
    value.duration.attachment_id !== expected.attachmentId ||
    value.duration.attachment_hash !== expected.attachmentHash ||
    value.duration.media_sha256 !== expected.mediaSha256 ||
    value.duration.size_bytes !== expected.sizeBytes ||
    value.duration.parser_version !== "iso-bmff-mvhd-v1" ||
    value.duration.timescale !== expected.timescale ||
    value.duration.duration_units !== expected.durationUnits ||
    value.duration.duration_ms !== expected.durationMs ||
    value.duration.duration_seconds !== expected.durationSeconds ||
    value.duration.verification_method !== "server_mp4_probe" ||
    !hash(value.duration.evidence_hash) ||
    !hash(value.duration.verification_hash) ||
    !timestamp(value.duration.verified_at) || !exact(value.contract, [
      "browser_measurement_accepted",
      "server_mp4_probe_required",
      "full_download_required",
      "sha256_match_required",
      "single_mvhd_required",
      "fragmented_mp4_allowed",
      "provider_call_started",
    ]) || value.contract.browser_measurement_accepted !== false ||
    value.contract.server_mp4_probe_required !== true ||
    value.contract.full_download_required !== true ||
    value.contract.sha256_match_required !== true ||
    value.contract.single_mvhd_required !== true ||
    value.contract.fragmented_mp4_allowed !== false ||
    value.contract.provider_call_started !== false
  ) return null;
  return Object.freeze({
    ok: true,
    version: "generation-strategy-media-probe-response-v1",
    media_id: value.duration.media_id,
    duration_seconds: value.duration.duration_seconds,
    verified_at: value.duration.verified_at,
    replay: value.replay,
  });
}

export function readGenerationStrategyReadiness(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "replay",
      "receipt",
      "strategy_prompt",
      "provider_preflight",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-readiness-record-response-v1" ||
    typeof value.replay !== "boolean" || !exact(value.receipt, [
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
      "spend_confirmation",
      "strategy_prompt_hash",
      "ready",
      "failure_code",
      "checked_at",
      "expires_at",
    ])
  ) return null;
  const receipt = value.receipt;
  if (
    !uuid(receipt.id) || !hash(receipt.receipt_hash) ||
    receipt.binding_id !== expected.bindingId ||
    receipt.binding_hash !== expected.bindingHash ||
    receipt.selection_hash !== expected.selectionHash ||
    receipt.price_hash !== expected.priceHash ||
    receipt.spend_confirmation !== expected.spendConfirmation ||
    !strategyRecipeIdentity(receipt.strategy_id, receipt.recipe) ||
    receipt.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    receipt.recipe_version !== RUNWAY_RECIPE_VERSION ||
    !isKnownStrategyPricingVersion(receipt.pricing_version) ||
    !hash(receipt.strategy_prompt_hash) || typeof receipt.ready !== "boolean" ||
    !(receipt.failure_code === null ||
      new Set([
        "provider_configuration_error",
        "provider_authentication_failed",
        "provider_balance_insufficient",
        "provider_readiness_unavailable",
      ]).has(receipt.failure_code)) ||
    (receipt.ready !== (receipt.failure_code === null)) ||
    !timestamp(receipt.checked_at) || !timestamp(receipt.expires_at) ||
    Date.parse(receipt.expires_at) <= Date.parse(receipt.checked_at) ||
    !exact(value.provider_preflight, [
      "credential_configured",
      "provider_authentication_confirmed",
      "recipe_catalog_supported",
      "recipe_precheck_supported",
      "recipe_available",
      "balance_sufficient",
      "daily_quota_precheck_supported",
      "daily_quota_available",
    ]) || typeof value.provider_preflight.credential_configured !== "boolean" ||
    typeof value.provider_preflight.provider_authentication_confirmed !==
      "boolean" ||
    value.provider_preflight.recipe_catalog_supported !== true ||
    value.provider_preflight.recipe_precheck_supported !== false ||
    value.provider_preflight.recipe_available !== null ||
    typeof value.provider_preflight.balance_sufficient !== "boolean" ||
    value.provider_preflight.daily_quota_precheck_supported !== false ||
    value.provider_preflight.daily_quota_available !== null ||
    !exact(value.contract, [
      "provider_call_started",
      "paid_start_authorized",
      "receipt_single_use",
      "browser_price_authority",
      "browser_prompt_authority",
    ]) || value.contract.provider_call_started !== false ||
    value.contract.paid_start_authorized !== false ||
    value.contract.receipt_single_use !== true ||
    value.contract.browser_price_authority !== false ||
    value.contract.browser_prompt_authority !== false ||
    !record(value.strategy_prompt)
  ) return null;
  return {
    receipt,
    strategyPrompt: value.strategy_prompt,
    providerPreflight: value.provider_preflight,
    publicResult: Object.freeze({
      ok: true,
      version: "generation-strategy-preflight-response-v1",
      replay: value.replay,
      receipt: Object.freeze({
        id: receipt.id,
        receipt_hash: receipt.receipt_hash,
        binding_id: receipt.binding_id,
        binding_hash: receipt.binding_hash,
        strategy_id: receipt.strategy_id,
        recipe: receipt.recipe,
        catalog_version: receipt.catalog_version,
        recipe_version: receipt.recipe_version,
        pricing_version: receipt.pricing_version,
        selection_hash: receipt.selection_hash,
        price_hash: receipt.price_hash,
        ready: receipt.ready,
        failure_code: receipt.failure_code,
        checked_at: receipt.checked_at,
        expires_at: receipt.expires_at,
      }),
      provider_preflight: value.provider_preflight,
      launch_enabled: false,
      contract: Object.freeze({
        provider_call_started: false,
        receipt_single_use: true,
        browser_price_authority: false,
        browser_prompt_authority: false,
      }),
    }),
  };
}

export function readGenerationStrategyProviderPolicy(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "execution_capabilities",
      "context",
      "checks",
      "blockers",
      "launch_enabled",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-provider-policy-response-v2" ||
    !record(value.execution_capabilities) ||
    !exact(value.execution_capabilities, [expected.strategyId]) ||
    !exact(value.execution_capabilities[expected.strategyId], [
      "enabled",
      "catalog_version",
      "strategy_id",
      "provider",
      "model_key",
      "recipe",
      "recipe_version",
      "provider_path",
      "poll_kind",
      "pricing_version",
    ])
  ) return null;
  const capability = value.execution_capabilities[expected.strategyId];
  const policyRoutes = PROVIDER_POLICY_ROUTES[expected.strategyId];
  const route = record(policyRoutes)
    ? policyRoutes[`${capability.provider}:${capability.model_key}`]
    : null;
  if (
    typeof capability.enabled !== "boolean" ||
    capability.strategy_id !== expected.strategyId ||
    !strategyRecipeIdentity(capability.strategy_id, capability.recipe) ||
    capability.provider !== expected.provider ||
    !isKnownStrategyProvider(capability.provider) ||
    !record(route) ||
    capability.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    capability.recipe_version !== RUNWAY_RECIPE_VERSION ||
    capability.provider_path !== route.providerPath ||
    capability.poll_kind !== route.pollKind ||
    capability.pricing_version !== route.pricingVersion ||
    capability.pricing_version !== expected.pricingVersion ||
    !isKnownStrategyPricingVersion(capability.pricing_version) ||
    !exact(value.context, [
      "strategy_id",
      "provider",
      "model_key",
      "recipe",
      "provider_path",
      "poll_kind",
      "binding_id",
      "binding_hash",
      "provider_readiness_receipt_id",
      "provider_readiness_receipt_hash",
      "catalog_version",
      "recipe_version",
      "pricing_version",
    ]) || value.context.strategy_id !== expected.strategyId ||
    value.context.provider !== capability.provider ||
    value.context.model_key !== capability.model_key ||
    value.context.recipe !== capability.recipe ||
    value.context.provider_path !== capability.provider_path ||
    value.context.poll_kind !== capability.poll_kind ||
    value.context.binding_id !== expected.bindingId ||
    value.context.binding_hash !== expected.bindingHash ||
    value.context.provider_readiness_receipt_id !== expected.receiptId ||
    value.context.provider_readiness_receipt_hash !== expected.receiptHash ||
    value.context.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.context.recipe_version !== RUNWAY_RECIPE_VERSION ||
    value.context.pricing_version !== capability.pricing_version ||
    !exact(value.checks, [
      "strategy_binding_current",
      "generation_spec_approved",
      "provider_readiness_receipt_current",
      "provider_readiness_receipt_unconsumed",
      "provider_route_current",
      "sql_provider_configuration_enabled",
      "start_path_integrated",
    ]) ||
    Object.values(value.checks).some((item) => typeof item !== "boolean") ||
    !Array.isArray(value.blockers) ||
    value.blockers.some((item) =>
      typeof item !== "string" || !SAFE_CODE.test(item)
    ) ||
    typeof value.launch_enabled !== "boolean" ||
    value.launch_enabled !==
      Object.values(value.checks).every((item) => item === true) ||
    value.launch_enabled !== (value.blockers.length === 0) ||
    value.launch_enabled !== capability.enabled ||
    !exact(value.contract, [
      "read_only",
      "server_authoritative",
      "provider_call_started",
      "paid_start_integrated",
      "receipt_single_use",
      "launch_enabled",
    ]) || value.contract.read_only !== true ||
    value.contract.server_authoritative !== true ||
    value.contract.provider_call_started !== false ||
    typeof value.contract.paid_start_integrated !== "boolean" ||
    value.contract.receipt_single_use !== true ||
    value.contract.launch_enabled !== value.launch_enabled
  ) return null;
  return {
    launchEnabled: value.launch_enabled,
    blockers: [...value.blockers],
    provider: capability.provider,
    modelKey: capability.model_key,
    pollKind: capability.poll_kind,
  };
}

export async function readGenerationStrategyStartClaim(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "claimed",
      "replay",
      "claim",
      "job",
      "strategy",
      "selection",
      "price",
      "recipe_context",
      "asset_context",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-start-claim-response-v1" ||
    typeof value.claimed !== "boolean" || typeof value.replay !== "boolean" ||
    value.claimed === value.replay || !exact(value.claim, [
      "id",
      "claim_hash",
      "batch_id",
      "generation_job_id",
      "review_task_id",
      "claimed_at",
    ]) || !uuid(value.claim.id) || !hash(value.claim.claim_hash) ||
    !uuid(value.claim.batch_id) || !uuid(value.claim.generation_job_id) ||
    !uuid(value.claim.review_task_id) || !timestamp(value.claim.claimed_at) ||
    !exact(value.job, [
      "id",
      "batch_id",
      "status",
      "output_object_name",
      "estimated_cost_minor",
      "estimated_credits",
      "currency",
      "campaign_id",
      "model_identity",
      "duration_seconds",
      "audio",
      "ratio",
      "resolution",
    ]) || value.job.id !== value.claim.generation_job_id ||
    value.job.batch_id !== value.claim.batch_id ||
    !new Set([
      "queued",
      "starting",
      "submitted",
      "processing",
      "succeeded",
      "failed",
      "cancelled",
    ]).has(value.job.status) ||
    !text(value.job.output_object_name, 3, 1_024) ||
    !integer(value.job.estimated_cost_minor) ||
    !integer(value.job.estimated_credits) ||
    value.job.currency !== "USD" ||
    value.job.campaign_id !== expected.campaignId ||
    !strategyRecipeIdentity(
      value.strategy?.strategy_id,
      value.job.model_identity,
    ) ||
    // Предел по стратегии, а не общий. Наряд «Дуэта» длиной с исходный ролик —
    // обычное дело, и упереться он должен в строку реестра, а не в число,
    // переехавшее сюда от первой стратегии.
    !durationWithinStrategyBounds(
      value.strategy?.strategy_id,
      value.job.duration_seconds,
    ) ||
    typeof value.job.audio !== "boolean" ||
    !immutableStrategy(value.strategy, true) ||
    value.strategy.receipt_id !== expected.receiptId ||
    value.strategy.receipt_hash !== expected.receiptHash ||
    value.strategy.binding_id !== expected.bindingId ||
    value.strategy.binding_hash !== expected.bindingHash ||
    value.strategy.selection_hash !== expected.selectionHash ||
    value.strategy.price_hash !== expected.priceHash ||
    value.strategy.spend_confirmation !== expected.spendConfirmation ||
    value.strategy.campaign_id !== expected.campaignId ||
    !record(value.selection) || !record(value.price) ||
    Object.hasOwn(value.price, "spend_confirmation") ||
    !exact(value.contract, [
      "provider_call_started",
      "dispatch_attempt_required",
      "dispatch_post_allowed",
      "review_mode",
      "review_autostart_confirmed",
      "signed_urls_persisted",
      "browser_prompt_authority",
    ]) || value.contract.provider_call_started !== false ||
    value.contract.dispatch_attempt_required !== true ||
    value.contract.dispatch_post_allowed !== false ||
    value.contract.review_mode !== "manual_human_review" ||
    value.contract.review_autostart_confirmed !== false ||
    value.contract.signed_urls_persisted !== false ||
    value.contract.browser_prompt_authority !== false
  ) return null;
  const context = recipeContext(value.recipe_context, value.strategy);
  const assets = assetContext(value.asset_context, value.strategy.strategy_id);
  if (
    context === null || assets === null ||
    !(await generationStrategyPromptHashesMatch(context))
  ) return null;
  return { ...value, recipe_context: context, asset_context: assets };
}

// Попытка отправки несёт провайдера: он взят из квитанции готовности и подписан
// вместе с ценой. Без него сторона отправки не знает, к какому движку идти.
//
// Принимаются ДВЕ формы, и это не послабление, а окно разворачивания: база
// и функция обновляются разными выкатками, и жёсткий набор ключей означал бы
// полный отказ отправки у ВСЕХ стратегий на время окна. Само значение при
// этом не подразумевается: если ключа нет, вызывающая сторона обязана отказать
// ДО запроса к провайдеру, а не выбирать движок по умолчанию.
function dispatchAttemptRow(value) {
  const legacy = [
    "id",
    "attempt_hash",
    "dispatch_token",
    "claim_id",
    "claim_hash",
    "generation_job_id",
    "reserved_at",
  ];
  if (exact(value, legacy)) return true;
  if (!exact(value, [...legacy, "provider", "product_category"])) return false;
  return isKnownStrategyProvider(value.provider) &&
    (value.product_category === null ||
      (typeof value.product_category === "string" &&
        SAFE_CODE.test(value.product_category)));
}

export async function readGenerationStrategyDispatchAttempt(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "dispatch_allowed",
      "replay",
      "attempt",
      "strategy",
      "recipe_context",
      "asset_context",
      "terminal_result",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-dispatch-attempt-response-v1" ||
    typeof value.dispatch_allowed !== "boolean" ||
    typeof value.replay !== "boolean" ||
    !dispatchAttemptRow(value.attempt) ||
    !uuid(value.attempt.id) || !hash(value.attempt.attempt_hash) ||
    !uuid(value.attempt.dispatch_token) ||
    value.attempt.claim_id !== expected.claimId ||
    value.attempt.claim_hash !== expected.claimHash ||
    value.attempt.generation_job_id !== expected.generationJobId ||
    !timestamp(value.attempt.reserved_at) ||
    !immutableStrategy(value.strategy, false) ||
    (expected.campaignId !== undefined &&
      value.strategy.campaign_id !== expected.campaignId) ||
    !exact(value.contract, [
      "provider_post_allowed",
      "provider_post_started",
      "one_post_maximum",
      "replay_post_allowed",
      "signed_urls_persisted",
      "input_failure_must_record_rejected",
      "terminalized_before_provider_post",
    ]) || value.contract.provider_post_allowed !== value.dispatch_allowed ||
    value.contract.provider_post_started !== false ||
    value.contract.one_post_maximum !== true ||
    value.contract.replay_post_allowed !== false ||
    value.contract.signed_urls_persisted !== false ||
    value.contract.input_failure_must_record_rejected !== true ||
    value.contract.terminalized_before_provider_post !==
      (value.terminal_result !== null)
  ) return null;
  if (
    value.terminal_result !== null && (!exact(value.terminal_result, [
      "id",
      "result_hash",
      "outcome",
      "provider_post_started",
      "failure_code",
      "recorded_at",
    ]) || !uuid(value.terminal_result.id) ||
      !hash(value.terminal_result.result_hash) ||
      value.terminal_result.outcome !== "rejected" ||
      value.terminal_result.provider_post_started !== false ||
      !SAFE_CODE.test(value.terminal_result.failure_code) ||
      !timestamp(value.terminal_result.recorded_at))
  ) return null;
  const context = recipeContext(value.recipe_context, value.strategy);
  const assets = value.terminal_result === null
    ? assetContext(value.asset_context, value.strategy.strategy_id)
    : Array.isArray(value.asset_context) && value.asset_context.length === 0
    ? []
    : null;
  if (
    context === null || assets === null ||
    !(await generationStrategyPromptHashesMatch(context))
  ) return null;
  if (
    value.dispatch_allowed && (value.replay || value.terminal_result !== null)
  ) return null;
  return { ...value, recipe_context: context, asset_context: assets };
}

export function classifyRunwayRecipeCreateOutcome(result) {
  if (!record(result) || !new Set(["network", "response"]).has(result.kind)) {
    return null;
  }
  if (result.kind === "network") {
    // Diagnostic enrichment (2026-08-17): the dispatch catch passes the thrown
    // error's name so the recorded result distinguishes network failure
    // classes (TypeError, AbortError, deadline, …). Money semantics are
    // unchanged — the outcome stays ambiguous with provider_post_started=true.
    // Callers without an errorName keep the legacy ambiguous code.
    const errorName = typeof result.errorName === "string"
      ? result.errorName.toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 40)
      : null;
    return Object.freeze({
      outcome: "ambiguous",
      provider_post_started: true,
      provider_http_status: null,
      provider_task_id: null,
      failure_code: errorName === null
        ? "provider_submission_ambiguous"
        : `provider_network_${errorName || "unknown"}`,
    });
  }
  const status = result.status;
  if (!integer(status, 100, 599)) return null;
  if (status >= 200 && status <= 299 && isRunwayTaskId(result.providerTaskId)) {
    return Object.freeze({
      outcome: "submitted",
      provider_post_started: true,
      provider_http_status: status,
      provider_task_id: result.providerTaskId,
      failure_code: null,
    });
  }
  if (DETERMINISTIC_REJECTION.has(status)) {
    const failure = status === 401 || status === 403
      ? "provider_authentication_failed"
      : status === 402
      ? "provider_balance_insufficient"
      : status === 404 || status === 405
      ? "provider_recipe_unavailable"
      : status === 429
      ? "provider_daily_quota_exceeded"
      : "provider_request_rejected";
    return Object.freeze({
      outcome: "rejected",
      provider_post_started: true,
      provider_http_status: status,
      provider_task_id: null,
      failure_code: failure,
    });
  }
  return Object.freeze({
    outcome: "ambiguous",
    provider_post_started: true,
    provider_http_status: status,
    provider_task_id: null,
    failure_code: "provider_submission_ambiguous",
  });
}

export function preDispatchStrategyFailure(code) {
  if (
    !new Set([
      "input_signing_failed",
      "input_asset_not_current",
      "signed_url_invalid",
    ]).has(code)
  ) return null;
  return Object.freeze({
    outcome: "rejected",
    provider_post_started: false,
    provider_http_status: null,
    provider_task_id: null,
    failure_code: code,
  });
}

export function readGenerationStrategyDispatchResult(value, expected) {
  if (
    !exact(value, ["ok", "version", "replay", "result", "job", "contract"]) ||
    value.ok !== true ||
    value.version !== "generation-strategy-dispatch-result-response-v1" ||
    typeof value.replay !== "boolean" || !exact(value.result, [
      "id",
      "result_hash",
      "attempt_id",
      "attempt_hash",
      "generation_job_id",
      "outcome",
      "provider_post_started",
      "provider_http_status",
      "provider_task_id",
      "failure_code",
      "recorded_at",
    ]) || !uuid(value.result.id) || !hash(value.result.result_hash) ||
    value.result.attempt_id !== expected.attemptId ||
    value.result.attempt_hash !== expected.attemptHash ||
    value.result.generation_job_id !== expected.generationJobId ||
    !new Set(["submitted", "ambiguous", "rejected"]).has(
      value.result.outcome,
    ) ||
    typeof value.result.provider_post_started !== "boolean" ||
    !(value.result.provider_http_status === null ||
      integer(value.result.provider_http_status, 100, 599)) ||
    !(value.result.provider_task_id === null ||
      isRunwayTaskId(value.result.provider_task_id)) ||
    !(value.result.failure_code === null ||
      SAFE_CODE.test(value.result.failure_code)) ||
    !timestamp(value.result.recorded_at) || !exact(value.job, [
      "id",
      "batch_id",
      "status",
      "submission_state",
      "reconciliation_required",
    ]) || value.job.id !== expected.generationJobId ||
    !uuid(value.job.batch_id) ||
    !new Set(["submitted", "failed", "starting"]).has(value.job.status) ||
    typeof value.job.submission_state !== "string" ||
    typeof value.job.reconciliation_required !== "boolean" ||
    !exact(value.contract, [
      "dispatch_slot_consumed",
      "second_post_allowed",
      "ambiguous_status_only",
      "pre_dispatch_failure_releases_reservation",
    ]) || value.contract.dispatch_slot_consumed !== true ||
    value.contract.second_post_allowed !== false ||
    typeof value.contract.ambiguous_status_only !== "boolean" ||
    typeof value.contract.pre_dispatch_failure_releases_reservation !==
      "boolean"
  ) return null;
  return value;
}

export function readGenerationStrategyProviderStatusResult(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "replay",
      "current_status_reused",
      "event",
      "output",
      "contract",
    ]) || value.ok !== true ||
    value.version !==
      "generation-strategy-provider-status-record-response-v1" ||
    typeof value.replay !== "boolean" ||
    typeof value.current_status_reused !== "boolean" ||
    !exact(value.event, [
      "id",
      "event_hash",
      "generation_job_id",
      "provider_task_id",
      "transition_ordinal",
      "previous_status",
      "provider_status",
      "failure_code",
      "occurred_at",
    ]) || !uuid(value.event.id) || !hash(value.event.event_hash) ||
    value.event.generation_job_id !== expected.generationJobId ||
    value.event.provider_task_id !== expected.providerTaskId ||
    !integer(value.event.transition_ordinal, 1, 1_000_000) ||
    !(value.event.previous_status === null || new Set([
      "processing",
      "succeeded",
      "failed",
      "cancelled",
    ]).has(value.event.previous_status)) ||
    !new Set(["processing", "succeeded", "failed", "cancelled"]).has(
      value.event.provider_status,
    ) ||
    !(value.event.failure_code === null ||
      SAFE_CODE.test(value.event.failure_code)) ||
    !timestamp(value.event.occurred_at) ||
    !(value.output === null || (exact(value.output, [
      "media_id",
      "mime_type",
      "size_bytes",
    ]) && uuid(value.output.media_id) &&
      value.output.mime_type === "video/mp4" &&
      integer(value.output.size_bytes, 1))) ||
    !exact(value.contract, [
      "monotonic",
      "same_status_returns_current",
      "provider_post_retried",
      "object_name_returned",
      "sha256_returned",
      "manual_human_review_required",
    ]) || value.contract.monotonic !== true ||
    value.contract.same_status_returns_current !== true ||
    value.contract.provider_post_retried !== false ||
    value.contract.object_name_returned !== false ||
    value.contract.sha256_returned !== false ||
    typeof value.contract.manual_human_review_required !== "boolean"
  ) return null;
  return value;
}

export function readGenerationStrategyReconciliationResult(value, expected) {
  if (
    !exact(value, [
      "ok",
      "version",
      "replay",
      "reconciliation",
      "job",
      "contract",
    ]) || value.ok !== true ||
    value.version !==
      "generation-strategy-dispatch-reconciliation-response-v1" ||
    typeof value.replay !== "boolean" || !exact(value.reconciliation, [
      "id",
      "reconciliation_hash",
      "dispatch_result_id",
      "generation_job_id",
      "resolution",
      "provider_task_id",
      "provider_task_created_at",
      "provider_status",
      "reconciled_at",
    ]) || !uuid(value.reconciliation.id) ||
    !hash(value.reconciliation.reconciliation_hash) ||
    value.reconciliation.dispatch_result_id !== expected.dispatchResultId ||
    value.reconciliation.generation_job_id !== expected.generationJobId ||
    !new Set(["provider_task_attached", "confirmed_not_submitted"]).has(
      value.reconciliation.resolution,
    ) || !timestamp(value.reconciliation.reconciled_at) ||
    !exact(value.job, [
      "id",
      "batch_id",
      "status",
      "provider_task_id",
      "reconciliation_required",
    ]) ||
    value.job.id !== expected.generationJobId || !uuid(value.job.batch_id) ||
    typeof value.job.status !== "string" ||
    !(value.job.provider_task_id === null ||
      isRunwayTaskId(value.job.provider_task_id)) ||
    value.job.reconciliation_required !== false || !exact(value.contract, [
      "second_post_allowed",
      "owner_admin_evidence_required",
      "reservation_settled_or_released",
    ]) || value.contract.second_post_allowed !== false ||
    value.contract.owner_admin_evidence_required !== true ||
    value.contract.reservation_settled_or_released !== true
  ) return null;
  return value;
}

export function isRunwayTaskId(value) {
  return typeof value === "string" && TASK_ID.test(value);
}

// Форму выбора проверяет канонический валидатор: длительность, кадр, разрешение,
// набор ассетов и подтверждения прав обязаны сойтись, и это не зависит от того,
// каким движком исполняется рецепт.
//
// А вот ЦЕНУ он всегда считает рунвеевскую: статический каталог знает только
// ступени кредитов Runway и всегда возвращает его же версию прайса. Сверять по
// ней снимок маршрута fal значило объявлять удачный платный запуск отказом:
// снимок несёт fal-usd-per-run-2026-08-18.v1 и 47 «кредитов», сверка не
// сходилась, readPublicGenerationStrategyStatus возвращал null, наружу уходило
// generation_unavailable — а деньги были уже зарезервированы и задача уже шла у
// провайдера. Резерв в такой развилке не снимался никогда.
//
// Поэтому версия прайса здесь больше не сверяется со статическим каталогом: её
// и число кредитов сверяет safeStatusPrice с ценой, замороженной в квитанции
// маршрута (price_hash подписан вместе с ней). Для Runway ничего не
// ослабляется — его ступени по-прежнему проходят через канонический
// калькулятор, см. safeStatusPrice.
function safeStatusSelection(value, strategy) {
  const validated = validateGenerationStrategySelection(value);
  return validated.ok === true &&
      validated.strategy_id === strategy.strategy_id &&
      validated.recipe === strategy.recipe &&
      validated.recipe_version === strategy.recipe_version
    ? validated
    : null;
}

function safeStatusPrice(value, strategy, selection) {
  if (!record(value)) return null;
  // Ступени кредитов считает только Runway, и для него сверка с каноническим
  // калькулятором остаётся обязательной слово в слово. У маршрута с собственной
  // ставкой (fal — фиксированная цена за ролик) рунвеевская арифметика цену не
  // описывает вовсе, поэтому у него проверяется внутренняя согласованность
  // ЗАМОРОЖЕННОГО снимка: «кредиты», доналоговая сумма и сумма списания обязаны
  // описывать одни и те же деньги (проверки ниже), а сам снимок обязан совпасть
  // с подписанным price_hash квитанции. Ослаблением это не является:
  // расхождение по-прежнему отвергается.
  const runwayCredits = value.provider === "runway";
  if (
    runwayCredits && value.estimated_credits !== selection.estimated_credits
  ) return null;
  // Версия прайса берётся не из каталога, а из подписанного снимка стратегии:
  // цена и движок подписаны вместе, поэтому назвать другую версию прайса в
  // снимке цены — это подмена, а не расхождение версий. И движок обязан
  // соответствовать своему прайсу: рунвеевские ступени принадлежат только
  // Runway, чужой маршрут не может ими считаться.
  if (
    value.pricing_version !== strategy.pricing_version ||
    runwayCredits !==
      (value.pricing_version === RUNWAY_RECIPE_PRICING_VERSION)
  ) return null;
  if (
    !exact(value, [
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
      "price_hash",
    ]) || value.version !== "generation-strategy-price-snapshot-v1" ||
    value.strategy_id !== strategy.strategy_id ||
    !isKnownStrategyProvider(value.provider) ||
    value.recipe !== strategy.recipe ||
    value.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    !isKnownStrategyPricingVersion(value.pricing_version) ||
    value.recipe_version !== RUNWAY_RECIPE_VERSION ||
    value.duration_seconds !== selection.output.duration_seconds ||
    value.audio !== selection.output.audio ||
    value.resolution !== selection.output.resolution ||
    // «Копия» и «Дуэт» кадр не выбирают — он приходит из исходника, и снимок
    // цены называет его словом "source". У «Копии» потому, что она переписывает
    // сам ролик; у «Дуэта» — потому, что ролик остаётся подложкой и задаёт
    // размер холста. «Создание» по-прежнему несёт соотношение сторон из выбора.
    value.ratio !==
      (RESOLUTION_FRAMED_RECIPES.has(strategy.recipe)
        ? "source"
        : selection.output.ratio) ||
    value.input_mode !== ({
        product_ugc: "video_and_avatar_images",
        product_swap: "video_and_product_images",
        product_ad: "product_images",
      })[strategy.recipe] ||
    !integer(value.estimated_credits, 1, 1_000_000) ||
    value.estimated_pre_tax_usd_minor !== value.estimated_credits ||
    value.estimated_cost_minor !== value.estimated_credits ||
    typeof value.estimated_cost_usd !== "string" ||
    value.estimated_cost_usd !== (value.estimated_credits / 100).toFixed(2) ||
    value.currency !== "USD" || value.credit_unit_cost_minor !== 1 ||
    !hash(value.price_hash) || value.price_hash !== strategy.price_hash
  ) return null;
  return value;
}

function safeStatusDispatch(value) {
  if (value === null) return null;
  if (
    !exact(value, [
      "result_id",
      "result_hash",
      "outcome",
      "provider_post_started",
      "provider_http_status",
      "recorded_at",
    ]) || !uuid(value.result_id) || !hash(value.result_hash) ||
    !new Set(["submitted", "ambiguous", "rejected"]).has(value.outcome) ||
    typeof value.provider_post_started !== "boolean" ||
    !(value.provider_http_status === null ||
      integer(value.provider_http_status, 100, 599)) ||
    !timestamp(value.recorded_at)
  ) return undefined;
  const deterministic = DETERMINISTIC_REJECTION.has(
    value.provider_http_status,
  );
  if (
    (value.outcome === "submitted" &&
      (value.provider_post_started !== true ||
        value.provider_http_status < 200 ||
        value.provider_http_status > 299)) ||
    (value.outcome === "ambiguous" &&
      (value.provider_post_started !== true || deterministic)) ||
    (value.outcome === "rejected" &&
      (value.provider_post_started
        ? !deterministic
        : value.provider_http_status !== null))
  ) return undefined;
  return value;
}

function safeStatusReconciliation(value) {
  if (value === null) return null;
  if (!record(value) || typeof value.required !== "boolean") return undefined;
  if (value.required) {
    return exact(value, [
        "required",
        "incident_id",
        "reason_code",
        "required_at",
      ]) &&
        uuid(value.incident_id) && SAFE_CODE.test(value.reason_code) &&
        timestamp(value.required_at)
      ? value
      : undefined;
  }
  return exact(value, [
      "required",
      "incident_id",
      "resolution",
      "reconciled_at",
    ]) &&
      uuid(value.incident_id) &&
      new Set(["provider_task_attached", "confirmed_not_submitted"]).has(
        value.resolution,
      ) && timestamp(value.reconciled_at)
    ? value
    : undefined;
}

function safeStatusOutput(value) {
  if (value === null) return null;
  return exact(value, ["media_id", "mime_type", "size_bytes"]) &&
      uuid(value.media_id) && value.mime_type === "video/mp4" &&
      integer(value.size_bytes, 1, 52_428_800)
    ? value
    : undefined;
}

function safeStatusError(value, job, dispatch, reconciliation) {
  if (value === null) return null;
  if (
    !exact(value, ["code", "provider_billing_outcome"]) ||
    typeof value.code !== "string" || !SAFE_CODE.test(value.code)
  ) return undefined;
  // Provider failures keep the conservative `unknown` billing outcome.  The
  // sole nullable outcome is stronger evidence, not weaker evidence: an
  // owner/admin resolved the exact ambiguous dispatch as not submitted, the
  // job has no provider task, and its actual cost is zero.  A null paired with
  // any other failure or reconciliation shape remains invalid.
  if (value.provider_billing_outcome === "unknown") return value;
  return value.provider_billing_outcome === null &&
      value.code === "provider_submission_not_found" &&
      job.status === "failed" && job.actual_cost_minor === 0 &&
      job.provider_status === null && job.provider_task_id === null &&
      dispatch?.outcome === "ambiguous" &&
      reconciliation?.required === false &&
      reconciliation.resolution === "confirmed_not_submitted"
    ? value
    : undefined;
}

function containsForbiddenPublicKey(value) {
  if (Array.isArray(value)) return value.some(containsForbiddenPublicKey);
  if (!record(value)) return false;
  const forbidden = new Set([
    "asset_context",
    "recipe_context",
    "bucket_id",
    "object_name",
    "output_object_name",
    "sha256",
    "signed_url",
    "dispatch_token",
    "spend_confirmation",
    "product_info",
    "user_concept",
  ]);
  return Object.entries(value).some(([key, item]) =>
    forbidden.has(key) || containsForbiddenPublicKey(item)
  );
}

export function readPublicGenerationStrategyStatus(value, expected) {
  if (
    !exact(value, [
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
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-status-response-v1" ||
    !exact(value.job, [
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
    ]) || value.job.id !== expected.generationJobId ||
    value.job.project_id !== expected.projectId || !uuid(value.job.batch_id) ||
    !uuid(value.job.campaign_id) ||
    !new Set([
      "queued",
      "starting",
      "submitted",
      "processing",
      "succeeded",
      "failed",
      "cancelled",
    ]).has(value.job.status) ||
    !(value.job.provider_status === null || new Set([
      // The dispatch writer records this first provider event atomically with
      // job.status = "submitted".  Rejecting the marker made an already paid,
      // provider-accepted job unprojectable until the first provider poll.
      "submitted",
      "processing",
      "succeeded",
      "failed",
      "cancelled",
    ]).has(value.job.provider_status)) ||
    !(value.job.provider_task_id === null ||
      isRunwayTaskId(value.job.provider_task_id)) ||
    !integer(value.job.estimated_cost_minor) ||
    !(value.job.actual_cost_minor === null ||
      integer(value.job.actual_cost_minor)) ||
    value.job.currency !== "USD" || !timestamp(value.job.created_at) ||
    !timestamp(value.job.updated_at) || !immutableStrategy({
      ...value.strategy,
      campaign_id: value.job.campaign_id,
    }, false) ||
    containsForbiddenPublicKey(value)
  ) return null;
  const selection = safeStatusSelection(value.selection, value.strategy);
  if (selection === null) return null;
  const price = safeStatusPrice(value.price, value.strategy, selection);
  const dispatch = safeStatusDispatch(value.dispatch);
  const reconciliation = safeStatusReconciliation(value.reconciliation);
  const output = safeStatusOutput(value.output);
  const error = safeStatusError(
    value.error,
    value.job,
    dispatch,
    reconciliation,
  );
  if (
    price === null || dispatch === undefined ||
    reconciliation === undefined || output === undefined ||
    error === undefined || value.job.estimated_cost_minor !==
      price.estimated_cost_minor ||
    !(value.job.actual_cost_minor === null ||
      value.job.actual_cost_minor === 0 ||
      value.job.actual_cost_minor === price.estimated_cost_minor) ||
    ((value.job.status === "succeeded") !== (output !== null)) ||
    (new Set(["failed", "cancelled"]).has(value.job.status) !==
      (error !== null)) ||
    (reconciliation?.required === true && dispatch?.outcome !== "ambiguous") ||
    (dispatch?.outcome === "submitted" &&
      value.job.provider_task_id === null) ||
    // `submitted` is a durable local dispatch receipt, not a provider poll
    // result. Accept it only in the exact state written by
    // system_record_generation_strategy_dispatch_result. This keeps the
    // reader fail-closed for manufactured or stale phase combinations while
    // allowing strategy_start to return the normal public status envelope.
    (value.job.provider_status === "submitted" &&
      (value.job.status !== "submitted" || dispatch?.outcome !== "submitted"))
  ) return null;
  if (
    !exact(value.contract, [
      "recipe_aware",
      "legacy_model_catalog_used",
      "poll_provider_allowed",
      "second_post_allowed",
      "object_names_returned",
      "media_hashes_returned",
      "signed_urls_returned",
      "manual_human_review_required",
    ]) || value.contract.recipe_aware !== true ||
    value.contract.legacy_model_catalog_used !== false ||
    value.contract.poll_provider_allowed !==
      (new Set(["submitted", "processing"]).has(value.job.status) &&
        value.job.provider_task_id !== null) ||
    value.contract.second_post_allowed !== false ||
    value.contract.object_names_returned !== false ||
    value.contract.media_hashes_returned !== false ||
    value.contract.signed_urls_returned !== false ||
    value.contract.manual_human_review_required !==
      (value.job.status === "succeeded")
  ) return null;
  return value;
}

// The only automatic recoveries allowed for a terminal strategy job are the
// two historical fal result-route defects. In both cases the provider POST was
// accepted, the exact request was recorded and billed, and only a GET against
// a queue result route failed. 405 was produced by the obsolete guessed
// `/response` handling; 413 was produced after the provider-owned
// `response_url` was stripped to a bare app-root route. Re-run the complete
// public status reader first so a caller cannot manufacture only this subset.
export function readFalResultHttp405RecoveryCandidate(value, expected) {
  return readFalResultHttpRecoveryCandidate(
    value,
    expected,
    "provider_result_http_405",
  );
}

export function readFalResultHttp413RecoveryCandidate(value, expected) {
  return readFalResultHttpRecoveryCandidate(
    value,
    expected,
    "provider_result_http_413",
  );
}

function readFalResultHttpRecoveryCandidate(value, expected, failureCode) {
  if (
    !record(expected) || !uuid(expected.projectId) ||
    !uuid(expected.generationJobId) ||
    !new Set([
      "provider_result_http_405",
      "provider_result_http_413",
    ]).has(failureCode)
  ) return null;
  const current = readPublicGenerationStrategyStatus(value, expected);
  if (current === null) return null;
  const job = current.job;
  const strategy = current.strategy;
  const price = current.price;
  const dispatch = current.dispatch;
  const error = current.error;
  if (
    job.status !== "failed" || job.provider_status !== "failed" ||
    typeof job.provider_task_id !== "string" ||
    !FAL_REQUEST_ID.test(job.provider_task_id) ||
    !integer(job.estimated_cost_minor, 1) ||
    job.actual_cost_minor !== job.estimated_cost_minor ||
    strategy.strategy_id !== "viral_product_swap" ||
    strategy.recipe !== "product_swap" || price.provider !== "fal" ||
    dispatch === null || dispatch.outcome !== "submitted" ||
    dispatch.provider_post_started !== true ||
    dispatch.provider_http_status !== 200 || current.reconciliation !== null ||
    current.output !== null || error === null ||
    error.code !== failureCode ||
    error.provider_billing_outcome !== "unknown" ||
    current.contract.poll_provider_allowed !== false ||
    current.contract.second_post_allowed !== false
  ) return null;
  return {
    providerTaskId: job.provider_task_id,
    recipe: strategy.recipe,
    failureCode,
  };
}

// Response from the one-shot ledger-preserving recovery writer. It may only
// turn the exact failed fal event into success; it cannot retry the provider
// POST, change billing or suppress the mandatory human review.
export function readGenerationStrategyProviderResultRecovery(value, expected) {
  if (
    !record(expected) || !uuid(expected.generationJobId) ||
    typeof expected.providerTaskId !== "string" ||
    !FAL_REQUEST_ID.test(expected.providerTaskId) ||
    !exact(value, [
      "ok",
      "version",
      "replay",
      "event",
      "output",
      "contract",
    ]) || value.ok !== true ||
    value.version !==
      "generation-strategy-provider-result-recovery-response-v1" ||
    typeof value.replay !== "boolean" || !exact(value.event, [
      "generation_job_id",
      "provider_task_id",
      "previous_status",
      "provider_status",
    ]) || value.event.generation_job_id !== expected.generationJobId ||
    value.event.provider_task_id !== expected.providerTaskId ||
    value.event.previous_status !== "failed" ||
    value.event.provider_status !== "succeeded" || !exact(value.output, [
      "media_id",
      "mime_type",
      "size_bytes",
    ]) || !uuid(value.output.media_id) ||
    value.output.mime_type !== "video/mp4" ||
    !integer(value.output.size_bytes, 1, 52_428_800) ||
    !exact(value.contract, [
      "provider_post_retried",
      "ledger_mutated",
      "manual_human_review_required",
    ]) || value.contract.provider_post_retried !== false ||
    value.contract.ledger_mutated !== false ||
    value.contract.manual_human_review_required !== true
  ) return null;
  return value;
}

export function runwayStrategyProviderStatus(value) {
  const task = record(value) && isRunwayTaskId(value.id) &&
      typeof value.status === "string"
    ? value
    : null;
  if (task === null) return null;
  if (new Set(["PENDING", "THROTTLED", "RUNNING"]).has(task.status)) {
    return { providerStatus: "processing", outputUrl: null, failureCode: null };
  }
  if (
    task.status === "SUCCEEDED" && Array.isArray(task.output) &&
    task.output.length === 1 && typeof task.output[0] === "string"
  ) {
    return {
      providerStatus: "succeeded",
      outputUrl: task.output[0],
      failureCode: null,
    };
  }
  if (new Set(["FAILED", "CANCELED", "CANCELLED"]).has(task.status)) {
    const raw = typeof task.failureCode === "string"
      ? task.failureCode.trim().toLowerCase().replace(/[^a-z0-9_]+/gu, "_")
        .slice(0, 80)
      : "provider_task_failed";
    return {
      providerStatus: task.status === "FAILED" ? "failed" : "cancelled",
      outputUrl: null,
      failureCode: SAFE_CODE.test(raw) ? raw : "provider_task_failed",
    };
  }
  return null;
}

// Ответ очереди fal на создание задачи. Адреса статуса и результата приходят
// в этом же ответе — собирать их самостоятельно нельзя, они принадлежат
// провайдеру и могут измениться.
// Идентификатор задачи HeyGen: непрозрачная строка провайдера. Проверяем не
// смысл, а границы — иначе в адрес опроса уехало бы что угодно.
const HEYGEN_VIDEO_ID = /^[A-Za-z0-9_-]{8,128}$/u;

/*
 * Ответ на создание ведущего. Идентификатор лежит ещё глубже, чем у ролика:
 * data.avatar_item.id против data.video_id. Разобрать одно другим нельзя.
 */
export function parseCreatedHeygenAvatar(value) {
  if (!record(value) || !record(value.data)) return null;
  const item = value.data.avatar_item;
  if (!record(item)) return null;
  const id = item.id;
  if (typeof id !== "string" || !HEYGEN_VIDEO_ID.test(id)) return null;
  const groupId = record(value.data.avatar_group) &&
      typeof value.data.avatar_group.id === "string" &&
      HEYGEN_VIDEO_ID.test(value.data.avatar_group.id)
    ? value.data.avatar_group.id
    : null;
  // Состояние может прийти сразу: обучение асинхронное, но короткое фото иногда
  // готово к моменту ответа.
  const status = typeof item.status === "string" ? item.status : null;
  return { id, groupId, status };
}

/*
 * Состояние обучения ведущего.
 *
 * pending_consent — НЕ отказ и НЕ готовность: провайдер ждёт подтверждения на
 * использование внешности. Смешать его с failed значило бы выбросить уже
 * оплаченного ведущего, а с completed — выдать за готового того, кем работать
 * ещё нельзя.
 */
export function heygenAvatarStatus(value, expectedAvatarId) {
  if (!record(value) || !record(value.data)) return null;
  const item = record(value.data.avatar_item) ? value.data.avatar_item : value.data;
  if (typeof item.status !== "string") return null;
  if (
    typeof item.id === "string" && typeof expectedAvatarId === "string" &&
    item.id !== expectedAvatarId
  ) return null;

  if (item.status === "processing") {
    return { avatarStatus: "training", avatarId: null, failureCode: null };
  }
  if (item.status === "pending_consent") {
    return { avatarStatus: "awaiting_consent", avatarId: null, failureCode: null };
  }
  if (item.status === "completed") {
    const id = typeof item.id === "string" && HEYGEN_VIDEO_ID.test(item.id)
      ? item.id
      : typeof expectedAvatarId === "string"
      ? expectedAvatarId
      : null;
    // Готовность без идентификатора готовностью не является: работать с таким
    // ведущим всё равно нечем, а запись о нём была бы ложью.
    if (id === null) return null;
    return { avatarStatus: "ready", avatarId: id, failureCode: null };
  }
  if (item.status === "failed") {
    const raw = typeof item.failure_code === "string"
      ? item.failure_code.trim().toLowerCase().replace(/[^a-z0-9_]+/gu, "_")
        .slice(0, 80)
      : "provider_avatar_failed";
    return {
      avatarStatus: "failed",
      avatarId: null,
      failureCode: SAFE_CODE.test(raw) && raw ? raw : "provider_avatar_failed",
    };
  }
  return null;
}

/*
 * Ответ HeyGen на создание задачи ведущего.
 *
 * Проверено 22.08.2026: идентификатор приходит как data.video_id — во
 * вложенном объекте, а не в корне, и называется иначе, чем у обоих других
 * провайдеров (Runway — id, очередь fal — request_id).
 *
 * Адресов статуса и результата в ответе нет и не должно быть: у HeyGen адрес
 * статуса предсказуем и собирается из идентификатора. Это отличает его от
 * очереди fal, где собирать адреса самостоятельно нельзя — они принадлежат
 * провайдеру и меняются на его стороне.
 */
export function parseCreatedHeygenVideo(value) {
  if (!record(value) || !record(value.data)) return null;
  const id = value.data.video_id;
  if (typeof id !== "string" || !HEYGEN_VIDEO_ID.test(id)) return null;
  return { id };
}

export function parseCreatedFalRequest(value) {
  if (!record(value)) return null;
  const id = value.request_id;
  if (typeof id !== "string" || !isRunwayTaskId(id)) return null;
  const statusUrl = falQueueUrl(value.status_url);
  const responseUrl = falQueueUrl(value.response_url);
  if (statusUrl === null || responseUrl === null) return null;
  return { id, statusUrl, responseUrl };
}

function falQueueUrl(value) {
  if (typeof value !== "string" || value.length > 1_024) return null;
  let url;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  return url.origin === FAL_QUEUE_ORIGIN && !url.username && !url.password
    ? url.toString()
    : null;
}

// Nested fal endpoints are submitted by their full model path, while queue
// status URLs can be rooted either at the owning app (`fal-ai/pika`) or at the
// full endpoint. Both are read-only candidates; the exact request id remains
// bound into every URL. These synthesized fallbacks use fal's documented bare
// result operation; a validated provider-owned `/response` URL is handled
// separately and always goes first.
export function falQueueUrlCandidates(modelKey, requestId) {
  if (
    !FAL_QUEUE_MODEL_PATHS.has(modelKey) ||
    typeof requestId !== "string" ||
    !TASK_ID.test(requestId)
  ) return [];
  const segments = modelKey.split("/");
  const roots = [`${segments[0]}/${segments[1]}`];
  if (!roots.includes(modelKey)) roots.push(modelKey);
  return roots.map((root) => {
    const resultUrl = `${FAL_QUEUE_ORIGIN}/${root}/requests/${requestId}`;
    return { statusUrl: `${resultUrl}/status`, resultUrl };
  });
}

function normalizeFalQueueResultUrl(value, requestId) {
  if (
    typeof requestId !== "string" ||
    !TASK_ID.test(requestId)
  ) return null;
  const parsedValue = falQueueUrl(value);
  if (parsedValue === null) return null;
  const url = new URL(parsedValue);
  const pathname = url.pathname.replace(/\/+$/u, "");
  if (
    !pathname.endsWith(`/requests/${requestId}`) &&
    !pathname.endsWith(`/requests/${requestId}/response`)
  ) return null;
  url.pathname = pathname;
  url.hash = "";
  return url.toString();
}

function bareFalQueueResultUrl(value, requestId) {
  const normalized = normalizeFalQueueResultUrl(value, requestId);
  if (normalized === null) return null;
  const url = new URL(normalized);
  const pathname = url.pathname.replace(/\/+$/u, "");
  if (pathname.endsWith("/response")) {
    url.pathname = pathname.slice(0, -"/response".length);
  }
  url.hash = "";
  return url.toString();
}

// COMPLETED status payloads include a provider-owned response_url. Validate
// its authority and request binding, but preserve it exactly: fal documents
// this `/response` convenience URL in submit/status responses even though its
// generic REST example also documents a bare request URL.
export function falQueueResultUrl(value, requestId) {
  if (!record(value)) return null;
  return normalizeFalQueueResultUrl(value.response_url, requestId);
}

// fal's model-request Platform API is an independent, read-only projection of
// stored request IO. It is the documented recovery path when a COMPLETED queue
// request exists but its queue result route cannot return the stored payload.
// Build the URL only from the executable model allowlist and a canonical fal
// request UUID; no provider-supplied authority or query fragment is accepted.
export function falModelRequestPayloadUrl(modelKey, requestId) {
  if (
    !FAL_QUEUE_MODEL_PATHS.has(modelKey) ||
    typeof requestId !== "string" ||
    !FAL_REQUEST_ID.test(requestId)
  ) return null;
  const url = new URL(
    "/v1/models/requests/by-endpoint",
    FAL_PLATFORM_API_ORIGIN,
  );
  url.searchParams.set("endpoint_id", modelKey);
  url.searchParams.set("request_id", requestId);
  url.searchParams.set("expand", "payloads");
  // Two rows are requested so `items.length === 1` plus the pagination fields
  // can prove that the exact filter produced one row, not merely one page.
  url.searchParams.set("limit", "2");
  return url.toString();
}

// The query is already exact, but the response is independently rebound to
// both identities before any media URL can be consumed. Multiple rows,
// mismatches and non-200 model executions are not recovery evidence.
export function readFalModelRequestOutput(
  value,
  modelKey,
  requestId,
  responseStatus,
) {
  if (
    responseStatus !== 200 ||
    !FAL_QUEUE_MODEL_PATHS.has(modelKey) ||
    typeof requestId !== "string" ||
    !FAL_REQUEST_ID.test(requestId) ||
    !record(value) ||
    !Array.isArray(value.items) ||
    value.items.length !== 1 ||
    value.has_more !== false ||
    value.next_cursor !== null
  ) return null;
  const item = value.items[0];
  if (
    !record(item) ||
    item.request_id !== requestId ||
    item.endpoint_id !== modelKey ||
    item.status_code !== 200 ||
    !record(item.json_output)
  ) return null;
  return {
    statusCode: 200,
    output: item.json_output,
  };
}

// The requester is injected so this contract module never owns network
// access, while the exact production fetch order remains executable under the
// Node harness. The validated provider-owned response_url is tried first, then
// its documented bare form and the bounded model/app-root fallbacks. 404, 405
// and 413 mean only that a result route did not match this queue deployment;
// they must not terminalize an already-paid, already-COMPLETED provider task.
export async function fetchFalQueueResult({
  statusValue,
  requestId,
  resultUrls,
  resultClasses,
  fetchJson,
}) {
  if (!Array.isArray(resultUrls) || typeof fetchJson !== "function") {
    return { response: null, refusedStatus: null, attempts: [] };
  }
  const candidates = [];
  const pushCandidate = (candidateClass, value) => {
    const normalized = normalizeFalQueueResultUrl(value, requestId);
    if (
      normalized !== null &&
      !candidates.some((candidate) => candidate.url === normalized)
    ) {
      candidates.push({ candidateClass, url: normalized });
    }
  };
  const statusResultUrl = falQueueResultUrl(statusValue, requestId);
  const statusBareResultUrl = bareFalQueueResultUrl(
    statusResultUrl,
    requestId,
  );
  pushCandidate("provider_response_exact", statusResultUrl);
  pushCandidate("provider_response_bare", statusBareResultUrl);
  const suppliedClasses = Array.isArray(resultClasses) ? resultClasses : [];
  for (let index = 0; index < resultUrls.length; index += 1) {
    // fal-js resolves nested endpoints through their owning app for result
    // reads (`fal-ai/pika/v2/pikaswaps` -> `fal-ai/pika`). Keep the second,
    // full-model route as a bounded compatibility fallback, and attach only a
    // closed class label so recovery diagnostics never need the URL itself.
    const suppliedClass = suppliedClasses[index];
    const candidateClass = suppliedClass === "app_root" ||
        suppliedClass === "full_model"
      ? suppliedClass
      : index === 0
      ? "app_root"
      : "full_model";
    pushCandidate(candidateClass, resultUrls[index]);
  }
  let refusedStatus = null;
  const attempts = [];
  for (const candidate of candidates) {
    let attempt;
    try {
      attempt = await fetchJson(candidate.url, { method: "GET" });
    } catch {
      attempts.push({
        candidateClass: candidate.candidateClass,
        outcome: "thrown",
        status: null,
      });
      continue;
    }
    if (
      !record(attempt) ||
      typeof attempt.ok !== "boolean" ||
      !integer(attempt.status, 100, 599)
    ) {
      attempts.push({
        candidateClass: candidate.candidateClass,
        outcome: "invalid",
        status: null,
      });
      continue;
    }
    const outcome = attempt.ok
      ? "ok"
      : attempt.status >= 300 && attempt.status < 400
      ? "redirect"
      : "http";
    attempts.push({
      candidateClass: candidate.candidateClass,
      outcome,
      status: attempt.status,
    });
    if (attempt.ok) {
      return { response: attempt, refusedStatus: null, attempts };
    }
    if (
      attempt.status === 404 || attempt.status === 405 ||
      attempt.status === 413
    ) continue;
    if (attempt.status >= 400 && refusedStatus === null) {
      refusedStatus = attempt.status;
    }
  }
  return { response: null, refusedStatus, attempts };
}

// Статус задачи fal. Готовый ролик лежит в теле результата, а не в статусе,
// поэтому succeeded здесь означает «пора забрать результат по response_url».
/*
 * Ответ HeyGen на опрос статуса ведущего.
 *
 * Проверено 22.08.2026 по https://developers.heygen.com/docs/quick-start :
 *   GET https://api.heygen.com/v3/videos/{video_id}
 *   { "data": { "id", "status", "video_url", "duration",
 *               "failure_code", "failure_message" } }
 *   status: "generating" | "completed" | "failed"
 *
 * ЧЕМ ЭТОТ ОТВЕТ ОТЛИЧАЕТСЯ ОТ ДВУХ ДРУГИХ. У Runway поля лежат в корне, у
 * очереди fal готовый ролик приходится забирать вторым запросом по отдельному
 * адресу. HeyGen отдаёт и статус, и ссылку на результат сразу, но всё это —
 * внутри вложенного `data`. Разбирать его тем же кодом, что и остальных,
 * нельзя: поля просто не найдутся, и наряд навсегда останется «в работе» при
 * уже списанных деньгах.
 *
 * ЛИЧНОСТЬ ЗАДАЧИ СВЕРЯЕТСЯ. Ответ обязан говорить о той задаче, о которой
 * спрашивали: чужой идентификатор означает, что мы читаем не свой запуск, и
 * принять его результат было бы хуже, чем не принять никакого.
 */

export function heygenStrategyProviderStatus(value, expectedVideoId) {
  if (!record(value) || !record(value.data)) return null;
  const data = value.data;
  if (typeof data.status !== "string") return null;
  // Сверка личности задачи. Идентификатор необязателен в ответе лишь потому,
  // что документация его не гарантирует для всех состояний; но если он есть и
  // не совпадает — это чужая задача, и ответ не наш.
  if (typeof data.id === "string" && typeof expectedVideoId === "string") {
    if (!HEYGEN_VIDEO_ID.test(data.id) || data.id !== expectedVideoId) {
      return null;
    }
  }

  // v3 отвечает generating/pending, v1 (/v1/video_status.get) — pending/
  // waiting/processing. Все — «ещё делается».
  if (
    data.status === "generating" || data.status === "pending" ||
    data.status === "waiting" || data.status === "processing"
  ) {
    return { providerStatus: "processing", outputUrl: null, failureCode: null };
  }

  if (data.status === "completed") {
    // Успех без ссылки на файл успехом не является: платить за ролик, который
    // некому забрать, нельзя. Такой ответ — неразобранный, а не готовый.
    if (typeof data.video_url !== "string" || !data.video_url) return null;
    return {
      providerStatus: "succeeded",
      outputUrl: data.video_url,
      failureCode: null,
    };
  }

  if (data.status === "failed") {
    // Код отказа приводится к тому же низкоэнтропийному словарю, что и у двух
    // других провайдеров: в журнал не должно попадать ничего, кроме короткого
    // машинного кода. failure_message провайдера сюда не переносится вовсе —
    // это свободный текст чужой системы.
    // v3 несёт failure_code, v1 — error.code; оба — чужие строки, которые
    // приводятся к короткому машинному коду.
    const rawSource = typeof data.failure_code === "string"
      ? data.failure_code
      : record(data.error) && typeof data.error.code === "string"
      ? data.error.code
      : "";
    const raw = rawSource
      ? rawSource.trim().toLowerCase().replace(/[^a-z0-9_]+/gu, "_").slice(0, 80)
      : "provider_task_failed";
    return {
      providerStatus: "failed",
      outputUrl: null,
      failureCode: SAFE_CODE.test(raw) && raw ? raw : "provider_task_failed",
    };
  }

  return null;
}

export function falStrategyProviderStatus(value) {
  if (!record(value) || typeof value.status !== "string") return null;
  if (new Set(["IN_QUEUE", "IN_PROGRESS"]).has(value.status)) {
    return { providerStatus: "processing", outputUrl: null, failureCode: null };
  }
  if (value.status === "COMPLETED") {
    const rawErrorType = value.error_type;
    if (typeof rawErrorType === "string" && FAL_ERROR_TYPE.test(rawErrorType)) {
      const normalizedErrorType = rawErrorType.toLowerCase().replace(
        /[_.:-]+/gu,
        "_",
      );
      const failureCode = `provider_${normalizedErrorType}`;
      // Keep the result compatible with the shared low-entropy diagnostic
      // vocabulary as well as the provider-status ledger contract.
      if (
        failureCode.length <= 80 &&
        SAFE_CODE.test(failureCode) &&
        normalizedErrorType.split("_").every((part) => part.length <= 24)
      ) {
        return {
          providerStatus: "failed",
          outputUrl: null,
          failureCode,
        };
      }
    }
    return { providerStatus: "succeeded", outputUrl: null, failureCode: null };
  }
  // Очередь умеет заканчивать задачу отказом, и такой ответ обязан закрывать
  // наряд. Неразобранный отказ оставлял его «в работе» навсегда: деньги
  // числились потраченными, а лимит одного открытого запуска — занятым.
  if (new Set(["FAILED", "ERROR"]).has(value.status)) {
    return {
      providerStatus: "failed",
      outputUrl: null,
      failureCode: "provider_task_failed",
    };
  }
  if (new Set(["CANCELED", "CANCELLED"]).has(value.status)) {
    return {
      providerStatus: "cancelled",
      outputUrl: null,
      failureCode: "provider_task_cancelled",
    };
  }
  return null;
}

// Тело результата fal: ссылка на готовый ролик.
export function readFalResultVideoUrl(value) {
  if (!record(value) || !record(value.video)) return null;
  const url = value.video.url;
  if (typeof url !== "string" || url.length > 2_048) return null;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  return parsed.protocol === "https:" ? parsed.toString() : null;
}

export const GENERATION_STRATEGY_EDGE_CONTRACT = Object.freeze({
  catalogVersion: GENERATION_STRATEGY_CATALOG_VERSION,
  recipeVersion: RUNWAY_RECIPE_VERSION,
  pricingVersion: RUNWAY_RECIPE_PRICING_VERSION,
  recipes: RECIPES,
  providerPaths: PROVIDER_PATHS,
  providerPolicyRoutes: PROVIDER_POLICY_ROUTES,
});
