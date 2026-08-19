/*
 * Pure Runway recipe request adapters.
 *
 * This module only constructs an immutable provider request envelope. It has
 * no access to credentials, storage, billing, the network or database state.
 * The caller must derive the recipe from the server-owned strategy catalog
 * and supply already-authorized, short-lived signed media URLs by exact role.
 * Browser-provided URLs and cost estimates are intentionally not inputs.
 *
 * Provider sources checked for this contract (2026-08-14):
 * - https://docs.dev.runwayml.com/recipes/product-ugc/
 * - https://docs.dev.runwayml.com/recipes/product-swap/
 * - https://docs.dev.runwayml.com/recipes/product-ad/
 * - https://docs.dev.runwayml.com/assets/inputs/
 *
 * 2026-08-17: the live Runway API has no /v1/recipes/* endpoints (verified in
 * the Request History endpoint filter). Product Swap therefore dispatches to
 * the real video_to_video API (Gen-4 Aleph, x-runway-version 2024-11-06):
 * - https://docs.dev.runwayml.com/api/#tag/Start-generating/paths/~1v1~1video_to_video/post
 * Its body accepts only model/videoUri/promptText/ratio/references; foreign
 * recipe fields (duration/audio/resolution/version) must never be sent.
 */

import {
  GENERATION_STRATEGY_CATALOG,
  GENERATION_STRATEGY_CATALOG_VERSION,
  generationStrategyCatalogEntry,
  RUNWAY_RECIPE_VERSION,
} from "./generation-strategy-catalog.js";

export const GENERATION_STRATEGY_CONTRACT_VERSION =
  GENERATION_STRATEGY_CATALOG_VERSION;
export { RUNWAY_RECIPE_VERSION };

export const RUNWAY_RECIPE_BY_STRATEGY = Object.freeze(Object.fromEntries(
  GENERATION_STRATEGY_CATALOG.map((entry) => [
    entry.strategy_id,
    entry.recipe,
  ]),
));

export const RUNWAY_RECIPE_ENDPOINTS = Object.freeze(Object.fromEntries(
  GENERATION_STRATEGY_CATALOG.map((entry) => [
    entry.recipe,
    entry.server.provider_path,
  ]),
));

const UGC_RATIOS = new Set(["720:1280", "1080:1920"]);
const PRODUCT_AD_RATIOS = new Set([
  "1280:720",
  "720:1280",
  "960:960",
  "834:1112",
  "1920:1080",
  "1080:1920",
  "1440:1440",
  "1248:1664",
]);
const PRODUCT_SWAP_RESOLUTIONS = new Set(["720p", "1080p"]);
// aleph2 (video_to_video) contract: exact model id, prompt-only body, and the
// vertical ratio. The catalog resolution (720p/1080p) stays a spend-contour
// selection field; Aleph itself renders 720p and the Product Swap route is
// vertical (9:16), so both map to 720:1280.
const PRODUCT_SWAP_ALEPH_MODEL = "aleph2";
const PRODUCT_SWAP_ALEPH_RATIO = "9:16";
const PRODUCT_SWAP_PROMPT_LIMIT = 1_000;
const PRODUCT_VIEWS = new Set(["front", "side", "back"]);
const SIGNED_ASSET_ROLES = new Set([
  "avatar",
  "product_primary",
  "product_reference",
  "source_video",
  "original_product",
  "style_reference",
]);
const MAX_SIGNED_URL_LENGTH = 2_048;

export class GenerationRecipeAdapterError extends Error {
  constructor(code) {
    super(`generation_recipe_adapter:${code}`);
    this.name = "GenerationRecipeAdapterError";
    this.code = code;
  }
}

function fail(code) {
  throw new GenerationRecipeAdapterError(code);
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function assertExactOwnKeys(value, exactKeys, code) {
  if (!isPlainObject(value)) fail(code);
  const keys = Object.keys(value);
  const exact = new Set(exactKeys);
  if (keys.length !== exact.size || keys.some((key) => !exact.has(key))) {
    fail(code);
  }
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function hasDisallowedTextControl(value) {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (
      code === 0x7f ||
      (code <= 0x1f && code !== 0x09 && code !== 0x0a && code !== 0x0d)
    ) return true;
  }
  return false;
}

function hasAnyControl(value) {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

function exactText(value, minimum, maximum, code) {
  if (
    typeof value !== "string" ||
    value !== value.trim() ||
    value.length < minimum ||
    value.length > maximum ||
    hasDisallowedTextControl(value)
  ) fail(code);
  return value;
}

function exactDuration(value) {
  if (!Number.isInteger(value) || value < 4 || value > 15) {
    fail("duration_invalid");
  }
  return value;
}

function exactSignedUrl(value) {
  if (
    typeof value !== "string" ||
    value !== value.trim() ||
    value.length < 13 ||
    value.length > MAX_SIGNED_URL_LENGTH ||
    !value.startsWith("https://") ||
    hasAnyControl(value)
  ) fail("signed_asset_uri_invalid");
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail("signed_asset_uri_invalid");
  }
  if (
    parsed.protocol !== "https:" ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.hash ||
    /^\d{1,3}(?:[.]\d{1,3}){3}$/u.test(parsed.hostname) ||
    parsed.hostname.includes(":")
  ) fail("signed_asset_uri_invalid");
  return value;
}

function exactSelection(value) {
  if (!isPlainObject(value)) fail("selection_invalid");
  const strategyId = value.strategyId;
  const recipe = value.recipe;
  const catalogEntry = generationStrategyCatalogEntry(strategyId);
  const expectedRecipe = catalogEntry?.recipe;
  if (
    value.strategyVersion !== GENERATION_STRATEGY_CONTRACT_VERSION ||
    value.recipeVersion !== RUNWAY_RECIPE_VERSION ||
    typeof expectedRecipe !== "string" ||
    recipe !== expectedRecipe ||
    RUNWAY_RECIPE_ENDPOINTS[recipe] !== catalogEntry.server.provider_path
  ) fail("strategy_recipe_binding_invalid");

  const commonKeys = [
    "strategyVersion",
    "strategyId",
    "recipe",
    "recipeVersion",
    "durationSeconds",
    "audio",
  ];
  if (recipe === "product_swap") {
    // modifyRegion нужен только маршрутам с точечной заменой объекта (fal).
    // Ключ необязательный: маршрут Runway его не передаёт, и требовать его со
    // всех означало бы сломать работающую «Копию».
    const swapKeys = [...commonKeys, "resolution", "promptText"];
    if (hasOwn(value, "modifyRegion")) swapKeys.push("modifyRegion");
    assertExactOwnKeys(value, swapKeys, "selection_fields_invalid");
    if (hasOwn(value, "modifyRegion")) {
      exactText(value.modifyRegion, 3, 200, "modify_region_invalid");
    }
    if (!PRODUCT_SWAP_RESOLUTIONS.has(value.resolution)) {
      fail("resolution_invalid");
    }
    exactText(
      value.promptText,
      1,
      PRODUCT_SWAP_PROMPT_LIMIT,
      "prompt_text_invalid",
    );
  } else {
    assertExactOwnKeys(
      value,
      [...commonKeys, "ratio", "productInfo", "userConcept"],
      "selection_fields_invalid",
    );
    const ratios = recipe === "product_ugc" ? UGC_RATIOS : PRODUCT_AD_RATIOS;
    if (!ratios.has(value.ratio)) fail("ratio_invalid");
    exactText(value.productInfo, 1, 2_500, "product_info_invalid");
    exactText(value.userConcept, 1, 3_500, "user_concept_invalid");
  }
  exactDuration(value.durationSeconds);
  if (typeof value.audio !== "boolean") fail("audio_invalid");
  return value;
}

function exactSignedAssets(value) {
  if (!Array.isArray(value) || value.length < 1 || value.length > 16) {
    fail("signed_assets_invalid");
  }
  const seenUris = new Set();
  return value.map((asset) => {
    if (!isPlainObject(asset)) fail("signed_asset_invalid");
    const withView = hasOwn(asset, "view");
    assertExactOwnKeys(
      asset,
      withView ? ["role", "uri", "view"] : ["role", "uri"],
      "signed_asset_fields_invalid",
    );
    if (!SIGNED_ASSET_ROLES.has(asset.role)) fail("signed_asset_role_invalid");
    const uri = exactSignedUrl(asset.uri);
    if (seenUris.has(uri)) fail("signed_asset_duplicate");
    seenUris.add(uri);
    if (withView && !PRODUCT_VIEWS.has(asset.view)) {
      fail("signed_asset_view_invalid");
    }
    return { role: asset.role, uri, ...(withView ? { view: asset.view } : {}) };
  });
}

function assetsByRole(assets, role) {
  return assets.filter((asset) => asset.role === role);
}

function oneAsset(assets, role) {
  const matches = assetsByRole(assets, role);
  if (matches.length !== 1) fail(`${role}_count_invalid`);
  return matches[0];
}

function assertNoRoles(assets, roles) {
  if (assets.some((asset) => roles.includes(asset.role))) {
    fail("signed_asset_role_incompatible");
  }
}

function uriObject(asset, { allowView = false } = {}) {
  if (!allowView && hasOwn(asset, "view")) {
    fail("signed_asset_view_incompatible");
  }
  return {
    uri: asset.uri,
    ...(allowView && hasOwn(asset, "view") ? { view: asset.view } : {}),
  };
}

function buildProductUgc(selection, assets) {
  if (assets.length !== 2) fail("product_ugc_assets_invalid");
  assertNoRoles(assets, [
    "product_reference",
    "source_video",
    "original_product",
    "style_reference",
  ]);
  const avatar = oneAsset(assets, "avatar");
  const product = oneAsset(assets, "product_primary");
  return {
    version: RUNWAY_RECIPE_VERSION,
    characterImage: uriObject(avatar),
    productImage: uriObject(product),
    productInfo: selection.productInfo,
    userConcept: selection.userConcept,
    duration: selection.durationSeconds,
    ratio: selection.ratio,
    audio: selection.audio,
  };
}

function buildProductSwap(selection, assets) {
  assertNoRoles(assets, ["avatar", "style_reference"]);
  const source = oneAsset(assets, "source_video");
  // The original-product frame stays a mandatory server-validated selection
  // asset (the dispatch receives the full set), but video_to_video does not
  // accept it as a body field: that frame is already inside the source video.
  const original = oneAsset(assets, "original_product");
  const primary = oneAsset(assets, "product_primary");
  const references = assetsByRole(assets, "product_reference");
  if (references.length > 9 || assets.length !== 3 + references.length) {
    fail("product_swap_assets_invalid");
  }
  if (hasOwn(source, "view") || hasOwn(original, "view")) {
    fail("signed_asset_view_incompatible");
  }
  // aleph2 (video_to_video) is prompt-only for this route: timed keyframes
  // with product photos pull the scene toward the photos' interiors instead
  // of the source footage (verified on paid runs 17.08.2026), so the product
  // photos stay spend-contour validation assets and inform the prompt text,
  // while the body carries only the source video and the prompt.
  return {
    model: PRODUCT_SWAP_ALEPH_MODEL,
    videoUri: source.uri,
    promptText: selection.promptText,
    targetAspectRatio: PRODUCT_SWAP_ALEPH_RATIO,
  };
}

function buildProductAd(selection, assets) {
  assertNoRoles(assets, ["avatar", "source_video", "original_product"]);
  const primary = oneAsset(assets, "product_primary");
  const references = assetsByRole(assets, "product_reference");
  const styles = assetsByRole(assets, "style_reference");
  if (
    references.length > 9 ||
    styles.length > 4 ||
    assets.length !== 1 + references.length + styles.length
  ) fail("product_ad_assets_invalid");
  return {
    version: RUNWAY_RECIPE_VERSION,
    productImages: [primary, ...references].map((asset) => uriObject(asset)),
    ...(styles.length
      ? { styleImages: styles.map((asset) => uriObject(asset)) }
      : {}),
    productInfo: selection.productInfo,
    userConcept: selection.userConcept,
    ratio: selection.ratio,
    duration: selection.durationSeconds,
    audio: selection.audio,
  };
}

// fal.ai Pika Swaps: точечная замена объекта, а не переписывание кадра. Модель
// принимает исходное видео, ОДНО фото товара и текстовое указание, что именно
// в кадре заменить. Остальные фотографии остаются проверочными ассетами
// спенд-контура: провайдер берёт ровно одну ссылку на изображение.
const FAL_PRODUCT_SWAP_MODEL = "fal-ai/pika/v2/pikaswaps";

function buildFalProductSwap(selection, assets) {
  assertNoRoles(assets, ["avatar", "style_reference"]);
  const source = oneAsset(assets, "source_video");
  const original = oneAsset(assets, "original_product");
  const primary = oneAsset(assets, "product_primary");
  const references = assetsByRole(assets, "product_reference");
  if (references.length > 9 || assets.length !== 3 + references.length) {
    fail("product_swap_assets_invalid");
  }
  if (hasOwn(source, "view") || hasOwn(original, "view")) {
    fail("signed_asset_view_incompatible");
  }
  if (
    typeof selection.modifyRegion !== "string" ||
    selection.modifyRegion.trim().length < 3 ||
    selection.modifyRegion.length > 200
  ) fail("modify_region_invalid");
  return {
    video_url: source.uri,
    image_url: primary.uri,
    modify_region: selection.modifyRegion,
    prompt: selection.promptText,
  };
}

export function buildFalRecipeRequest(selectionValue, signedAssetsValue) {
  const selection = exactSelection(selectionValue);
  const assets = exactSignedAssets(signedAssetsValue);
  if (selection.recipe !== "product_swap") fail("fal_recipe_unsupported");
  return deepFreeze({
    provider: "fal",
    // У очереди fal путь и есть идентификатор модели: submit уходит на
    // {origin}/{model}, а адреса статуса и результата возвращает сам ответ —
    // собирать их руками нельзя, они меняются на стороне провайдера.
    endpointPath: FAL_PRODUCT_SWAP_MODEL,
    method: "POST",
    body: { input: buildFalProductSwap(selection, assets) },
    pollKind: "fal_request",
  });
}

export function buildRunwayRecipeRequest(selectionValue, signedAssetsValue) {
  const selection = exactSelection(selectionValue);
  const assets = exactSignedAssets(signedAssetsValue);
  const body = selection.recipe === "product_ugc"
    ? buildProductUgc(selection, assets)
    : selection.recipe === "product_swap"
    ? buildProductSwap(selection, assets)
    : buildProductAd(selection, assets);
  return deepFreeze({
    provider: "runway",
    endpointPath: RUNWAY_RECIPE_ENDPOINTS[selection.recipe],
    method: "POST",
    body,
    pollKind: "runway_task",
  });
}
