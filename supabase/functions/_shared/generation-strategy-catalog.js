/*
 * Canonical generation strategy contract.
 *
 * This module is intentionally pure: it does not read environment variables,
 * touch storage, call providers or infer execution readiness. The browser may
 * consume publicGenerationStrategyCatalog(); server code must additionally use
 * validateGenerationStrategyForExecution() with an exact, server-owned runtime
 * capability map before a provider request can be built.
 *
 * Runway recipe and pricing references, verified 2026-08-14:
 * - https://docs.dev.runwayml.com/recipes/product-ugc/
 * - https://docs.dev.runwayml.com/recipes/product-swap/
 * - https://docs.dev.runwayml.com/recipes/product-ad/
 * - https://docs.dev.runwayml.com/guides/pricing/
 */

export const GENERATION_STRATEGY_CATALOG_VERSION = "2026-08-14.v1";
export const RUNWAY_RECIPE_VERSION = "2026-06";
export const RUNWAY_RECIPE_PRICING_VERSION =
  "runway-recipe-credits-2026-08-14.v1";
export const FAL_RECIPE_PRICING_VERSION = "fal-usd-per-run-2026-08-18.v1";
// Посекундная ставка не может жить под именем «за ролик»: имя входит в
// хеш-подпись строки привязки, и совпадение имён означало бы подпись,
// утверждающую не то, что было посчитано.
export const FAL_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-2026-08-18.v1";

// Версия прайса — свойство маршрута, а не константа стратегии: у Runway она
// считается ступенями кредитов, у fal — фиксированной ценой за ролик либо
// ставкой за секунду. Набор повторяет ограничение базы на колонку
// pricing_version, поэтому расшириться он может только вместе с ней.
export const GENERATION_STRATEGY_PRICING_VERSIONS = Object.freeze([
  RUNWAY_RECIPE_PRICING_VERSION,
  FAL_RECIPE_PRICING_VERSION,
  FAL_PER_SECOND_PRICING_VERSION,
]);

export function isKnownStrategyPricingVersion(value) {
  return typeof value === "string" &&
    GENERATION_STRATEGY_PRICING_VERSIONS.includes(value);
}

// Провайдеры, которым разрешено исполнять стратегию. Тот же набор стоит в
// ограничении базы на колонку provider таблицы квитанций готовности.
export const GENERATION_STRATEGY_PROVIDERS = Object.freeze([
  "runway",
  "fal",
]);

export function isKnownStrategyProvider(value) {
  return typeof value === "string" &&
    GENERATION_STRATEGY_PROVIDERS.includes(value);
}

export const GENERATION_STRATEGY_IDS = Object.freeze({
  avatarUgc: "viral_avatar_ugc",
  productSwap: "viral_product_swap",
  rebuild: "viral_rebuild",
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const TOP_LEVEL_SELECTION_FIELDS = Object.freeze([
  "version",
  "strategy_id",
  "recipe_version",
  "duration_seconds",
  "ratio",
  "resolution",
  "audio",
  "assets",
  "attestations",
]);
const EXECUTION_CAPABILITY_FIELDS = Object.freeze([
  "enabled",
  "catalog_version",
  "strategy_id",
  "provider",
  "recipe",
  "recipe_version",
  "provider_path",
  "pricing_version",
]);

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
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

function failure(code, field, message) {
  return Object.freeze({ ok: false, code, field, message });
}

function success(value = {}) {
  return deepFreeze({ ok: true, ...value });
}

function assetRole(value) {
  return deepFreeze({
    allowed_views: [],
    duration_required: false,
    min_duration_seconds: null,
    max_duration_seconds: null,
    ...value,
  });
}

function attestation(id, public_label) {
  return Object.freeze({ id, public_label });
}

function pricing(base_720p, base_1080p) {
  return deepFreeze({
    kind: "base_at_4_seconds_plus_per_additional_second",
    unit: "runway_credit",
    usd_cents_per_credit: 1,
    base_duration_seconds: 4,
    tiers: {
      "720p": {
        base_credits: base_720p,
        additional_credits_per_second: 36,
      },
      "1080p": {
        base_credits: base_1080p,
        additional_credits_per_second: 40,
      },
    },
  });
}

const COMMON_ATTESTATIONS = Object.freeze([
  attestation(
    "source_media_rights_confirmed",
    "У меня есть права использовать исходный ролик как референс.",
  ),
  attestation(
    "transformative_use_confirmed",
    "Права на исходный ролик разрешают его переработку для нового рекламного материала.",
  ),
  attestation(
    "product_assets_rights_confirmed",
    "У меня есть права использовать изображения товара.",
  ),
  attestation(
    "depicted_people_consent_confirmed",
    "Для всех узнаваемых людей есть согласие на такое использование, либо людей в исходниках нет.",
  ),
]);

const RAW_CATALOG = [
  {
    strategy_id: GENERATION_STRATEGY_IDS.avatarUgc,
    public_label: "Новый UGC с аватаром и товаром",
    public_summary:
      "Создаёт новый вертикальный UGC-ролик с выбранным аватаром и товаром, ориентируясь на механику референса.",
    transformation_kind: "new_ugc_remake",
    source_reference_mode: "mechanics_only_not_provider_input",
    preservation_notice:
      "Это новый ролик: исходные кадры, движения, монтаж и тайминг не сохраняются покадрово.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_ugc",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Ролик-референс механики",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: false,
        provider_field: null,
      }),
      assetRole({
        role: "avatar_image",
        public_label: "Фото аватара",
        media_kind: "image",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "characterImage",
        min_aspect_ratio: 0.4,
        max_aspect_ratio: 4,
      }),
      assetRole({
        role: "product_image",
        public_label: "Фото товара",
        media_kind: "image",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "productImage",
        min_aspect_ratio: 0.4,
        max_aspect_ratio: 4,
      }),
    ],
    required_attestations: [
      ...COMMON_ATTESTATIONS,
      attestation(
        "avatar_likeness_consent_confirmed",
        "Есть явное согласие на использование внешности выбранного аватара.",
      ),
    ],
    output_rules: {
      duration: { min_seconds: 4, max_seconds: 15, default_seconds: 15 },
      dimension_field: "ratio",
      ratios: ["720:1280", "1080:1920"],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {
        "720:1280": "720p",
        "1080:1920": "1080p",
      },
      audio: { required_explicit_boolean: true, provider_default: true },
    },
    server: {
      provider_path: "/v1/recipes/product_ugc",
      pricing: pricing(192, 208),
    },
  },
  {
    strategy_id: GENERATION_STRATEGY_IDS.productSwap,
    public_label: "Заменить товар в исходном ролике",
    public_summary:
      "Заменяет показанный товар на ваш и сохраняет механику исходной сцены в пределах возможностей Product Swap.",
    transformation_kind: "product_swap_preserve_scene",
    source_reference_mode: "provider_reference_video",
    preservation_notice:
      "Рецепт сохраняет движение камеры, свет и композицию, но не гарантирует пиксельную идентичность; лучше всего работают товары сходной формы и назначения.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_swap",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Исходный ролик с заменяемым товаром",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "referenceVideo",
        duration_required: true,
        min_duration_seconds: 1.8,
        max_duration_seconds: 15,
      }),
      assetRole({
        role: "original_product_image",
        public_label: "Фото исходного товара",
        media_kind: "image",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "originalProductImage",
      }),
      assetRole({
        role: "new_product_image",
        public_label: "Фото вашего товара",
        media_kind: "image",
        min_count: 1,
        max_count: 10,
        forwarded_to_provider: true,
        provider_field: "newProductImages",
        allowed_views: ["front", "side", "back"],
      }),
    ],
    required_attestations: COMMON_ATTESTATIONS,
    output_rules: {
      duration: { min_seconds: 4, max_seconds: 15, default_seconds: 10 },
      dimension_field: "resolution",
      ratios: [],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {},
      audio: { required_explicit_boolean: true, provider_default: true },
    },
    server: {
      // Runway has no /v1/recipes/* endpoints (verified in the live Request
      // History filter). Product Swap runs on the real video_to_video API
      // (Gen-4 Aleph): edit the confirmed source MP4 by prompt with image
      // references. Pricing stays the internal spend-contour authority.
      provider_path: "/v1/video_to_video",
      pricing: pricing(212, 228),
    },
  },
  {
    strategy_id: GENERATION_STRATEGY_IDS.rebuild,
    public_label: "Создать новый ролик по механике референса",
    public_summary:
      "Создаёт рекламный ролик с нуля из фотографий вашего товара и описания механики или стиля референса.",
    transformation_kind: "new_product_ad_remake",
    source_reference_mode: "mechanics_and_style_only_not_provider_input",
    preservation_notice:
      "Это новый Product Ad: исходные кадры, актёр, движение и монтаж не переносятся как есть.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_ad",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Ролик-референс механики и стиля",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: false,
        provider_field: null,
      }),
      assetRole({
        role: "product_image",
        public_label: "Фото вашего товара",
        media_kind: "image",
        min_count: 1,
        max_count: 10,
        forwarded_to_provider: true,
        provider_field: "productImages",
      }),
      assetRole({
        role: "style_image",
        public_label: "Дополнительный стилевой референс",
        media_kind: "image",
        min_count: 0,
        max_count: 4,
        forwarded_to_provider: true,
        provider_field: "styleImages",
      }),
    ],
    required_attestations: COMMON_ATTESTATIONS,
    output_rules: {
      duration: { min_seconds: 4, max_seconds: 15, default_seconds: 10 },
      dimension_field: "ratio",
      ratios: [
        "1280:720",
        "720:1280",
        "960:960",
        "834:1112",
        "1920:1080",
        "1080:1920",
        "1440:1440",
        "1248:1664",
      ],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {
        "1280:720": "720p",
        "720:1280": "720p",
        "960:960": "720p",
        "834:1112": "720p",
        "1920:1080": "1080p",
        "1080:1920": "1080p",
        "1440:1440": "1080p",
        "1248:1664": "1080p",
      },
      audio: { required_explicit_boolean: true, provider_default: false },
    },
    server: {
      provider_path: "/v1/recipes/product_ad",
      pricing: pricing(200, 216),
    },
  },
];

export const GENERATION_STRATEGY_CATALOG = deepFreeze(RAW_CATALOG);

export function generationStrategyCatalogEntry(strategyId) {
  return (
    GENERATION_STRATEGY_CATALOG.find(
      (entry) => entry.strategy_id === String(strategyId || ""),
    ) || null
  );
}

function validateOutputSelection(entry, value) {
  if (!Number.isInteger(value?.duration_seconds)) {
    return failure(
      "duration_invalid",
      "duration_seconds",
      "duration_seconds must be an integer",
    );
  }
  const duration = entry.output_rules.duration;
  if (
    value.duration_seconds < duration.min_seconds ||
    value.duration_seconds > duration.max_seconds
  ) {
    return failure(
      "duration_unsupported",
      "duration_seconds",
      `duration_seconds must be between ${duration.min_seconds} and ${duration.max_seconds}`,
    );
  }
  if (typeof value.audio !== "boolean") {
    return failure(
      "audio_invalid",
      "audio",
      "audio must be an explicit boolean",
    );
  }

  if (entry.output_rules.dimension_field === "ratio") {
    if (hasOwn(value, "resolution")) {
      return failure(
        "dimension_field_forbidden",
        "resolution",
        "this strategy derives resolution from ratio",
      );
    }
    if (!entry.output_rules.ratios.includes(value.ratio)) {
      return failure("ratio_unsupported", "ratio", "ratio is not supported");
    }
    return success({
      duration_seconds: value.duration_seconds,
      ratio: value.ratio,
      resolution: entry.output_rules.resolution_by_ratio[value.ratio],
      audio: value.audio,
    });
  }

  if (hasOwn(value, "ratio")) {
    return failure(
      "dimension_field_forbidden",
      "ratio",
      "this strategy uses resolution and preserves the source composition",
    );
  }
  if (!entry.output_rules.resolutions.includes(value.resolution)) {
    return failure(
      "resolution_unsupported",
      "resolution",
      "resolution is not supported",
    );
  }
  return success({
    duration_seconds: value.duration_seconds,
    ratio: null,
    resolution: value.resolution,
    audio: value.audio,
  });
}

function validateAssets(entry, assets) {
  if (!Array.isArray(assets)) {
    return failure("assets_invalid", "assets", "assets must be an array");
  }
  const roles = new Map(entry.asset_roles.map((role) => [role.role, role]));
  const counts = new Map(entry.asset_roles.map((role) => [role.role, 0]));
  const mediaIds = new Set();

  for (let index = 0; index < assets.length; index += 1) {
    const asset = assets[index];
    const field = `assets[${index}]`;
    if (!isPlainObject(asset)) {
      return failure("asset_invalid", field, "each asset must be an object");
    }
    const role = roles.get(asset.role);
    if (!role) {
      return failure(
        "asset_role_unknown",
        `${field}.role`,
        "asset role is unknown",
      );
    }
    const allowedFields = ["role", "media_id"];
    if (role.media_kind === "video") allowedFields.push("duration_seconds");
    if (role.allowed_views.length > 0) allowedFields.push("view");
    const unknownField = Object.keys(asset).find(
      (key) => !allowedFields.includes(key),
    );
    if (unknownField) {
      return failure(
        "asset_field_unknown",
        `${field}.${unknownField}`,
        "asset contains an unsupported field",
      );
    }
    if (
      typeof asset.media_id !== "string" ||
      !UUID_PATTERN.test(asset.media_id) ||
      asset.media_id.toLowerCase() === ZERO_UUID
    ) {
      return failure(
        "asset_media_id_invalid",
        `${field}.media_id`,
        "media_id must be a non-zero UUID",
      );
    }
    const normalizedMediaId = asset.media_id.toLowerCase();
    if (mediaIds.has(normalizedMediaId)) {
      return failure(
        "asset_media_id_duplicate",
        `${field}.media_id`,
        "the same media_id cannot satisfy more than one asset slot",
      );
    }
    mediaIds.add(normalizedMediaId);

    if (role.media_kind === "video") {
      if (role.duration_required && !hasOwn(asset, "duration_seconds")) {
        return failure(
          "asset_duration_required",
          `${field}.duration_seconds`,
          "duration_seconds is required for this video role",
        );
      }
      if (hasOwn(asset, "duration_seconds")) {
        if (
          typeof asset.duration_seconds !== "number" ||
          !Number.isFinite(asset.duration_seconds) ||
          asset.duration_seconds <= 0
        ) {
          return failure(
            "asset_duration_invalid",
            `${field}.duration_seconds`,
            "video duration_seconds must be a positive finite number",
          );
        }
        if (
          role.min_duration_seconds !== null &&
          asset.duration_seconds < role.min_duration_seconds
        ) {
          return failure(
            "asset_duration_unsupported",
            `${field}.duration_seconds`,
            `video duration_seconds must be at least ${role.min_duration_seconds}`,
          );
        }
        if (
          role.max_duration_seconds !== null &&
          asset.duration_seconds > role.max_duration_seconds
        ) {
          return failure(
            "asset_duration_unsupported",
            `${field}.duration_seconds`,
            `video duration_seconds must be at most ${role.max_duration_seconds}`,
          );
        }
      }
    }

    if (hasOwn(asset, "view") && !role.allowed_views.includes(asset.view)) {
      return failure(
        "asset_view_unsupported",
        `${field}.view`,
        "asset view is not supported",
      );
    }
    counts.set(role.role, counts.get(role.role) + 1);
  }

  for (const role of entry.asset_roles) {
    const count = counts.get(role.role);
    if (count < role.min_count || count > role.max_count) {
      return failure(
        "asset_role_count_invalid",
        `assets.${role.role}`,
        `${role.role} requires ${role.min_count}..${role.max_count} assets`,
      );
    }
  }
  return success({ asset_count: assets.length });
}

function validateAttestations(entry, attestations) {
  if (!isPlainObject(attestations)) {
    return failure(
      "attestations_invalid",
      "attestations",
      "attestations must be an object",
    );
  }
  const required = entry.required_attestations.map((item) => item.id);
  const unknownField = Object.keys(attestations).find(
    (key) => !required.includes(key),
  );
  if (unknownField) {
    return failure(
      "attestation_unknown",
      `attestations.${unknownField}`,
      "attestation is not part of this versioned contract",
    );
  }
  for (const id of required) {
    if (attestations[id] !== true) {
      return failure(
        "attestation_required",
        `attestations.${id}`,
        "every required rights attestation must be exactly true",
      );
    }
  }
  return success({ attestation_count: required.length });
}

export function estimateGenerationStrategyCredits(strategyId, output) {
  const entry = generationStrategyCatalogEntry(strategyId);
  if (!entry) {
    return failure("strategy_unknown", "strategy_id", "strategy_id is unknown");
  }
  if (!isPlainObject(output)) {
    return failure("output_invalid", "output", "output must be an object");
  }
  const validated = validateOutputSelection(entry, output);
  if (!validated.ok) return validated;
  const tier = entry.server.pricing.tiers[validated.resolution];
  const additionalSeconds = validated.duration_seconds -
    entry.server.pricing.base_duration_seconds;
  const estimatedCredits = tier.base_credits +
    tier.additional_credits_per_second * additionalSeconds;
  return success({
    strategy_id: entry.strategy_id,
    provider: entry.provider,
    recipe: entry.recipe,
    pricing_version: entry.pricing_version,
    resolution: validated.resolution,
    duration_seconds: validated.duration_seconds,
    estimated_credits: estimatedCredits,
    estimated_pre_tax_usd_minor: estimatedCredits,
    currency: "USD",
  });
}

export function validateGenerationStrategySelection(selection) {
  if (!isPlainObject(selection)) {
    return failure(
      "selection_invalid",
      "generation_strategy",
      "generation_strategy must be an object",
    );
  }
  const unknownField = Object.keys(selection).find(
    (key) => !TOP_LEVEL_SELECTION_FIELDS.includes(key),
  );
  if (unknownField) {
    return failure(
      "selection_field_unknown",
      unknownField,
      "generation_strategy contains an unsupported field",
    );
  }
  if (selection.version !== GENERATION_STRATEGY_CATALOG_VERSION) {
    return failure(
      "catalog_version_mismatch",
      "version",
      "generation strategy catalog version does not match",
    );
  }
  const entry = generationStrategyCatalogEntry(selection.strategy_id);
  if (!entry) {
    return failure("strategy_unknown", "strategy_id", "strategy_id is unknown");
  }
  if (selection.recipe_version !== entry.recipe_version) {
    return failure(
      "recipe_version_mismatch",
      "recipe_version",
      "recipe_version does not match the catalog",
    );
  }
  const output = validateOutputSelection(entry, selection);
  if (!output.ok) return output;
  const assets = validateAssets(entry, selection.assets);
  if (!assets.ok) return assets;
  const attestations = validateAttestations(entry, selection.attestations);
  if (!attestations.ok) return attestations;
  const cost = estimateGenerationStrategyCredits(entry.strategy_id, selection);
  if (!cost.ok) return cost;
  return success({
    strategy_id: entry.strategy_id,
    provider: entry.provider,
    recipe: entry.recipe,
    recipe_version: entry.recipe_version,
    output: {
      duration_seconds: output.duration_seconds,
      ratio: output.ratio,
      resolution: output.resolution,
      audio: output.audio,
    },
    estimated_credits: cost.estimated_credits,
    estimated_pre_tax_usd_minor: cost.estimated_pre_tax_usd_minor,
    pricing_version: cost.pricing_version,
  });
}

function exactExecutionCapability(entry, capabilities) {
  const capability = isPlainObject(capabilities)
    ? capabilities[entry.strategy_id]
    : null;
  if (!isPlainObject(capability)) return false;
  const keys = Object.keys(capability).sort();
  const expectedKeys = [...EXECUTION_CAPABILITY_FIELDS].sort();
  if (
    keys.length !== expectedKeys.length ||
    keys.some((key, index) => key !== expectedKeys[index])
  ) {
    return false;
  }
  return (
    capability.enabled === true &&
    capability.catalog_version === GENERATION_STRATEGY_CATALOG_VERSION &&
    capability.strategy_id === entry.strategy_id &&
    capability.provider === entry.provider &&
    capability.recipe === entry.recipe &&
    capability.recipe_version === entry.recipe_version &&
    capability.provider_path === entry.server.provider_path &&
    // Версия прайса приходит от действующего маршрута, а не из статического
    // описания стратегии: у Runway и у fal она разная, и сверять её с
    // константой каталога значило бы гасить стратегию при смене движка.
    isKnownStrategyPricingVersion(capability.pricing_version)
  );
}

export function generationStrategyExecutionEnabled(
  strategyId,
  capabilities = {},
) {
  const entry = generationStrategyCatalogEntry(strategyId);
  return Boolean(entry && exactExecutionCapability(entry, capabilities));
}

export function validateGenerationStrategyForExecution(
  selection,
  { executionCapabilities = {} } = {},
) {
  const validated = validateGenerationStrategySelection(selection);
  if (!validated.ok) return validated;
  const entry = generationStrategyCatalogEntry(validated.strategy_id);
  if (!exactExecutionCapability(entry, executionCapabilities)) {
    return failure(
      "strategy_execution_not_enabled",
      "strategy_id",
      "the exact server-side strategy route is not enabled",
    );
  }
  return success({
    ...validated,
    provider_path: entry.server.provider_path,
  });
}

function publicAssetRole(role) {
  return {
    role: role.role,
    public_label: role.public_label,
    media_kind: role.media_kind,
    min_count: role.min_count,
    max_count: role.max_count,
    source_use: role.forwarded_to_provider
      ? "provider_input"
      : "mechanics_or_style_reference_only",
    allowed_views: [...role.allowed_views],
    duration_required: role.duration_required,
    min_duration_seconds: role.min_duration_seconds,
    max_duration_seconds: role.max_duration_seconds,
  };
}

function publicPricing(entry) {
  const pricingValue = entry.server.pricing;
  return {
    pricing_version: entry.pricing_version,
    kind: pricingValue.kind,
    unit: pricingValue.unit,
    usd_cents_per_credit: pricingValue.usd_cents_per_credit,
    base_duration_seconds: pricingValue.base_duration_seconds,
    tiers: {
      "720p": { ...pricingValue.tiers["720p"] },
      "1080p": { ...pricingValue.tiers["1080p"] },
    },
  };
}

export function publicGenerationStrategyCatalog(
  { executionCapabilities = {} } = {},
) {
  return deepFreeze({
    version: GENERATION_STRATEGY_CATALOG_VERSION,
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    strategies: GENERATION_STRATEGY_CATALOG.map((entry) => {
      const enabled = exactExecutionCapability(entry, executionCapabilities);
      return {
        strategy_id: entry.strategy_id,
        public_label: entry.public_label,
        public_summary: entry.public_summary,
        transformation_kind: entry.transformation_kind,
        source_reference_mode: entry.source_reference_mode,
        preservation_notice: entry.preservation_notice,
        human_review_required: entry.human_review_required,
        provider: entry.provider,
        recipe: entry.recipe,
        recipe_version: entry.recipe_version,
        asset_roles: entry.asset_roles.map(publicAssetRole),
        required_attestations: entry.required_attestations.map((item) => ({
          id: item.id,
          public_label: item.public_label,
        })),
        output_rules: {
          duration: { ...entry.output_rules.duration },
          dimension_field: entry.output_rules.dimension_field,
          ratios: [...entry.output_rules.ratios],
          resolutions: [...entry.output_rules.resolutions],
          audio: { ...entry.output_rules.audio },
        },
        pricing: publicPricing(entry),
        enabled,
        disabled_reason: enabled ? null : "strategy_route_not_verified",
      };
    }),
  });
}
