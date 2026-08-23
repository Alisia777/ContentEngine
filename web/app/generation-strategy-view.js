/*
 * Pure browser view contract for the server-owned generation strategy catalog.
 *
 * No strategy, provider, recipe or price is executable merely because it is
 * rendered here. There is deliberately no default selection. A strategy can
 * enter local view state only through the literal SELECT reducer action, and a
 * disabled server row cannot be selected.
 */

export const GENERATION_STRATEGY_VIEW_VERSION = "2026-08-14.v1";
export const GENERATION_STRATEGY_SELECT_ACTION = "SELECT";

const EXPECTED_STRATEGY_COUNT = 3;
const TOP_LEVEL_KEYS = Object.freeze([
  "version",
  "recipe_version",
  "pricing_version",
  "strategies",
]);
const STRATEGY_KEYS = Object.freeze([
  "strategy_id",
  "public_label",
  "public_summary",
  "transformation_kind",
  "source_reference_mode",
  "preservation_notice",
  "human_review_required",
  "provider",
  "recipe",
  "recipe_version",
  "asset_roles",
  "required_attestations",
  "output_rules",
  "pricing",
  "enabled",
  "disabled_reason",
]);
const ASSET_ROLE_KEYS = Object.freeze([
  "role",
  "public_label",
  "media_kind",
  "min_count",
  "max_count",
  "source_use",
  "allowed_views",
  "duration_required",
  "min_duration_seconds",
  "max_duration_seconds",
]);
const ATTESTATION_KEYS = Object.freeze(["id", "public_label"]);
const OUTPUT_RULE_KEYS = Object.freeze([
  "duration",
  "dimension_field",
  "ratios",
  "resolutions",
  "audio",
]);
const DURATION_KEYS = Object.freeze([
  "min_seconds",
  "max_seconds",
  "default_seconds",
]);
const AUDIO_KEYS = Object.freeze([
  "required_explicit_boolean",
  "provider_default",
]);
const PRICING_KEYS = Object.freeze([
  "pricing_version",
  "kind",
  "unit",
  "usd_cents_per_credit",
  "base_duration_seconds",
  "tiers",
]);
const PRICING_TIER_KEYS = Object.freeze(["720p", "1080p"]);
const PRICING_FORMULA_KEYS = Object.freeze([
  "base_credits",
  "additional_credits_per_second",
]);
const DRAFT_KEYS = Object.freeze([
  "duration_seconds",
  "ratio",
  "resolution",
  "audio",
  "asset_counts",
  "attestations",
]);
const CODE_PATTERN = /^[a-z0-9][a-z0-9_.-]{0,127}$/u;
const DISABLED_REASON_COPY = Object.freeze({
  strategy_route_not_verified:
    "Маршрут запуска этой стратегии ещё не подтверждён сервером.",
});

class CatalogContractError extends Error {
  constructor(code, field) {
    super(code);
    this.name = "CatalogContractError";
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

function exactObject(value, keys, field) {
  if (!isPlainObject(value)) {
    throw new CatalogContractError("object_required", field);
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length ||
    actual.some((key, index) => key !== expected[index])
  ) {
    throw new CatalogContractError("object_keys_mismatch", field);
  }
  return value;
}

function requiredText(value, field, maxLength = 5_000) {
  if (typeof value !== "string") {
    throw new CatalogContractError("text_required", field);
  }
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) {
    throw new CatalogContractError("text_invalid", field);
  }
  return normalized;
}

function requiredCode(value, field) {
  const normalized = requiredText(value, field, 128).toLowerCase();
  if (!CODE_PATTERN.test(normalized)) {
    throw new CatalogContractError("code_invalid", field);
  }
  return normalized;
}

function requiredBoolean(value, field) {
  if (typeof value !== "boolean") {
    throw new CatalogContractError("boolean_required", field);
  }
  return value;
}

function safeInteger(value, field, { min = 0, max = Number.MAX_SAFE_INTEGER } = {}) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new CatalogContractError("integer_invalid", field);
  }
  return value;
}

function finiteNumberOrNull(value, field) {
  if (value === null) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    throw new CatalogContractError("number_invalid", field);
  }
  return value;
}

function uniqueStringArray(value, field, { allowEmpty = true } = {}) {
  if (!Array.isArray(value) || (!allowEmpty && value.length === 0) || value.length > 32) {
    throw new CatalogContractError("array_invalid", field);
  }
  const normalized = value.map((item, index) =>
    requiredText(item, `${field}[${index}]`, 128)
  );
  if (new Set(normalized).size !== normalized.length) {
    throw new CatalogContractError("array_duplicate", field);
  }
  return normalized;
}

function normalizeAssetRole(value, field) {
  const source = exactObject(value, ASSET_ROLE_KEYS, field);
  const role = requiredCode(source.role, `${field}.role`);
  const mediaKind = requiredCode(source.media_kind, `${field}.media_kind`);
  if (!new Set(["image", "video"]).has(mediaKind)) {
    throw new CatalogContractError("media_kind_unsupported", `${field}.media_kind`);
  }
  const sourceUse = requiredCode(source.source_use, `${field}.source_use`);
  if (!new Set([
    "provider_input",
    "mechanics_or_style_reference_only",
  ]).has(sourceUse)) {
    throw new CatalogContractError("source_use_unsupported", `${field}.source_use`);
  }
  const minCount = safeInteger(source.min_count, `${field}.min_count`, {
    min: 0,
    max: 10,
  });
  const maxCount = safeInteger(source.max_count, `${field}.max_count`, {
    min: 0,
    max: 10,
  });
  if (minCount > maxCount) {
    throw new CatalogContractError("asset_count_range_invalid", field);
  }
  const durationRequired = requiredBoolean(
    source.duration_required,
    `${field}.duration_required`,
  );
  const minDuration = finiteNumberOrNull(
    source.min_duration_seconds,
    `${field}.min_duration_seconds`,
  );
  const maxDuration = finiteNumberOrNull(
    source.max_duration_seconds,
    `${field}.max_duration_seconds`,
  );
  if (
    durationRequired &&
    (mediaKind !== "video" || minDuration === null || maxDuration === null)
  ) {
    throw new CatalogContractError("asset_duration_contract_invalid", field);
  }
  if (!durationRequired && (minDuration !== null || maxDuration !== null)) {
    throw new CatalogContractError("asset_duration_contract_invalid", field);
  }
  if (minDuration !== null && maxDuration !== null && minDuration > maxDuration) {
    throw new CatalogContractError("asset_duration_range_invalid", field);
  }
  return {
    role,
    public_label: requiredText(source.public_label, `${field}.public_label`),
    media_kind: mediaKind,
    min_count: minCount,
    max_count: maxCount,
    source_use: sourceUse,
    allowed_views: uniqueStringArray(source.allowed_views, `${field}.allowed_views`)
      .map((item) => requiredCode(item, `${field}.allowed_views`)),
    duration_required: durationRequired,
    min_duration_seconds: minDuration,
    max_duration_seconds: maxDuration,
  };
}

function normalizeAttestation(value, field) {
  const source = exactObject(value, ATTESTATION_KEYS, field);
  return {
    id: requiredCode(source.id, `${field}.id`),
    public_label: requiredText(source.public_label, `${field}.public_label`),
  };
}

function normalizeOutputRules(value, field) {
  const source = exactObject(value, OUTPUT_RULE_KEYS, field);
  const duration = exactObject(source.duration, DURATION_KEYS, `${field}.duration`);
  const minSeconds = safeInteger(
    duration.min_seconds,
    `${field}.duration.min_seconds`,
    { min: 1, max: 300 },
  );
  const maxSeconds = safeInteger(
    duration.max_seconds,
    `${field}.duration.max_seconds`,
    { min: 1, max: 300 },
  );
  const defaultSeconds = safeInteger(
    duration.default_seconds,
    `${field}.duration.default_seconds`,
    { min: 1, max: 300 },
  );
  if (
    minSeconds > maxSeconds ||
    defaultSeconds < minSeconds ||
    defaultSeconds > maxSeconds
  ) {
    throw new CatalogContractError("output_duration_range_invalid", `${field}.duration`);
  }
  const dimensionField = requiredCode(
    source.dimension_field,
    `${field}.dimension_field`,
  );
  if (!new Set(["ratio", "resolution"]).has(dimensionField)) {
    throw new CatalogContractError(
      "dimension_field_unsupported",
      `${field}.dimension_field`,
    );
  }
  const ratios = uniqueStringArray(source.ratios, `${field}.ratios`, {
    allowEmpty: dimensionField !== "ratio",
  });
  const resolutions = uniqueStringArray(
    source.resolutions,
    `${field}.resolutions`,
    { allowEmpty: false },
  );
  if (dimensionField === "resolution" && ratios.length > 0) {
    throw new CatalogContractError("dimension_options_mismatch", `${field}.ratios`);
  }
  const audio = exactObject(source.audio, AUDIO_KEYS, `${field}.audio`);
  if (audio.required_explicit_boolean !== true) {
    throw new CatalogContractError(
      "explicit_audio_contract_required",
      `${field}.audio.required_explicit_boolean`,
    );
  }
  return {
    duration: {
      min_seconds: minSeconds,
      max_seconds: maxSeconds,
      default_seconds: defaultSeconds,
    },
    dimension_field: dimensionField,
    ratios,
    resolutions,
    audio: {
      required_explicit_boolean: true,
      provider_default: requiredBoolean(
        audio.provider_default,
        `${field}.audio.provider_default`,
      ),
    },
  };
}

function normalizePricing(value, field, catalogPricingVersion) {
  const source = exactObject(value, PRICING_KEYS, field);
  const pricingVersion = requiredText(
    source.pricing_version,
    `${field}.pricing_version`,
    160,
  );
  if (pricingVersion !== catalogPricingVersion) {
    throw new CatalogContractError(
      "pricing_version_mismatch",
      `${field}.pricing_version`,
    );
  }
  const tiers = exactObject(source.tiers, PRICING_TIER_KEYS, `${field}.tiers`);
  const normalizedTiers = Object.fromEntries(
    PRICING_TIER_KEYS.map((tier) => {
      const formula = exactObject(
        tiers[tier],
        PRICING_FORMULA_KEYS,
        `${field}.tiers.${tier}`,
      );
      return [tier, {
        base_credits: safeInteger(
          formula.base_credits,
          `${field}.tiers.${tier}.base_credits`,
          { min: 1, max: 1_000_000 },
        ),
        additional_credits_per_second: safeInteger(
          formula.additional_credits_per_second,
          `${field}.tiers.${tier}.additional_credits_per_second`,
          { min: 0, max: 1_000_000 },
        ),
      }];
    }),
  );
  return {
    pricing_version: pricingVersion,
    kind: requiredCode(source.kind, `${field}.kind`),
    unit: requiredCode(source.unit, `${field}.unit`),
    usd_cents_per_credit: safeInteger(
      source.usd_cents_per_credit,
      `${field}.usd_cents_per_credit`,
      { min: 1, max: 100_000 },
    ),
    base_duration_seconds: safeInteger(
      source.base_duration_seconds,
      `${field}.base_duration_seconds`,
      { min: 1, max: 300 },
    ),
    tiers: normalizedTiers,
  };
}

function normalizeStrategy(value, index, catalog) {
  const field = `strategies[${index}]`;
  const source = exactObject(value, STRATEGY_KEYS, field);
  const assetRoles = source.asset_roles;
  if (!Array.isArray(assetRoles) || assetRoles.length === 0 || assetRoles.length > 16) {
    throw new CatalogContractError("asset_roles_invalid", `${field}.asset_roles`);
  }
  const normalizedRoles = assetRoles.map((item, roleIndex) =>
    normalizeAssetRole(item, `${field}.asset_roles[${roleIndex}]`)
  );
  if (new Set(normalizedRoles.map((item) => item.role)).size !== normalizedRoles.length) {
    throw new CatalogContractError("asset_role_duplicate", `${field}.asset_roles`);
  }
  const attestations = source.required_attestations;
  if (!Array.isArray(attestations) || attestations.length === 0 || attestations.length > 16) {
    throw new CatalogContractError(
      "required_attestations_invalid",
      `${field}.required_attestations`,
    );
  }
  const normalizedAttestations = attestations.map((item, attestationIndex) =>
    normalizeAttestation(
      item,
      `${field}.required_attestations[${attestationIndex}]`,
    )
  );
  if (
    new Set(normalizedAttestations.map((item) => item.id)).size !==
    normalizedAttestations.length
  ) {
    throw new CatalogContractError(
      "attestation_duplicate",
      `${field}.required_attestations`,
    );
  }
  if (source.human_review_required !== true) {
    throw new CatalogContractError(
      "human_review_contract_required",
      `${field}.human_review_required`,
    );
  }
  const enabled = requiredBoolean(source.enabled, `${field}.enabled`);
  let disabledReason = null;
  if (enabled) {
    if (source.disabled_reason !== null) {
      throw new CatalogContractError(
        "enabled_reason_mismatch",
        `${field}.disabled_reason`,
      );
    }
  } else {
    disabledReason = requiredCode(
      source.disabled_reason,
      `${field}.disabled_reason`,
    );
  }
  const recipeVersion = requiredText(
    source.recipe_version,
    `${field}.recipe_version`,
    160,
  );
  if (recipeVersion !== catalog.recipe_version) {
    throw new CatalogContractError(
      "recipe_version_mismatch",
      `${field}.recipe_version`,
    );
  }
  return {
    strategy_id: requiredCode(source.strategy_id, `${field}.strategy_id`),
    public_label: requiredText(source.public_label, `${field}.public_label`),
    public_summary: requiredText(source.public_summary, `${field}.public_summary`),
    transformation_kind: requiredCode(
      source.transformation_kind,
      `${field}.transformation_kind`,
    ),
    source_reference_mode: requiredCode(
      source.source_reference_mode,
      `${field}.source_reference_mode`,
    ),
    preservation_notice: requiredText(
      source.preservation_notice,
      `${field}.preservation_notice`,
    ),
    human_review_required: true,
    provider: requiredCode(source.provider, `${field}.provider`),
    recipe: requiredCode(source.recipe, `${field}.recipe`),
    recipe_version: recipeVersion,
    asset_roles: normalizedRoles,
    required_attestations: normalizedAttestations,
    output_rules: normalizeOutputRules(source.output_rules, `${field}.output_rules`),
    pricing: normalizePricing(
      source.pricing,
      `${field}.pricing`,
      catalog.pricing_version,
    ),
    enabled,
    disabled_reason: disabledReason,
  };
}

export function normalizeGenerationStrategyCatalog(raw) {
  try {
    const source = exactObject(raw, TOP_LEVEL_KEYS, "catalog");
    const catalog = {
      version: requiredText(source.version, "catalog.version", 160),
      recipe_version: requiredText(
        source.recipe_version,
        "catalog.recipe_version",
        160,
      ),
      pricing_version: requiredText(
        source.pricing_version,
        "catalog.pricing_version",
        160,
      ),
    };
    if (
      !Array.isArray(source.strategies) ||
      source.strategies.length !== EXPECTED_STRATEGY_COUNT
    ) {
      throw new CatalogContractError(
        "strategy_count_mismatch",
        "catalog.strategies",
      );
    }
    const strategies = source.strategies.map((item, index) =>
      normalizeStrategy(item, index, catalog)
    );
    if (new Set(strategies.map((item) => item.strategy_id)).size !== strategies.length) {
      throw new CatalogContractError(
        "strategy_id_duplicate",
        "catalog.strategies",
      );
    }
    return deepFreeze({
      ok: true,
      catalog: { ...catalog, strategies },
      error: null,
    });
  } catch (error) {
    const known = error instanceof CatalogContractError;
    return deepFreeze({
      ok: false,
      catalog: null,
      error: {
        code: known ? error.code : "catalog_contract_invalid",
        field: known ? error.field : "catalog",
      },
    });
  }
}

function normalizedResult(value) {
  if (
    isPlainObject(value) &&
    typeof value.ok === "boolean" &&
    Object.prototype.hasOwnProperty.call(value, "catalog") &&
    Object.prototype.hasOwnProperty.call(value, "error")
  ) {
    if (value.ok === true) {
      return normalizeGenerationStrategyCatalog(value.catalog);
    }
    // A failed result from this module is already a strict, bounded contract.
    // Preserve its exact diagnostic instead of replacing every failure with a
    // generic code; the state remains fail-closed (no catalog, no selection).
    if (
      value.catalog === null &&
      isPlainObject(value.error) &&
      Object.keys(value.error).length === 2 &&
      Object.prototype.hasOwnProperty.call(value.error, "code") &&
      Object.prototype.hasOwnProperty.call(value.error, "field")
    ) {
      try {
        return deepFreeze({
          ok: false,
          catalog: null,
          error: {
            code: requiredCode(value.error.code, "catalog.error.code"),
            field: requiredText(value.error.field, "catalog.error.field", 500),
          },
        });
      } catch {
        // Malformed external failure envelopes are not trusted diagnostics.
      }
    }
    return deepFreeze({
      ok: false,
      catalog: null,
      error: {
        code: "catalog_contract_invalid",
        field: "catalog",
      },
    });
  }
  return normalizeGenerationStrategyCatalog(value);
}

export function createGenerationStrategyViewState(catalogOrNormalized) {
  const result = normalizedResult(catalogOrNormalized);
  return deepFreeze({
    catalog_status: result.ok ? "ready" : "invalid",
    catalog: result.ok ? result.catalog : null,
    catalog_error: result.ok ? null : result.error,
    selected_strategy_id: null,
    selection_origin: null,
    selection_error: null,
  });
}

function withSelectionError(state, code) {
  return deepFreeze({
    ...state,
    selection_error: code,
  });
}

export function reduceGenerationStrategyViewState(state, action) {
  if (!isPlainObject(state) || state.catalog_status !== "ready" || !state.catalog) {
    return state;
  }
  if (!isPlainObject(action)) return withSelectionError(state, "select_action_invalid");
  const keys = Object.keys(action).sort();
  if (keys.length !== 2 || keys[0] !== "strategy_id" || keys[1] !== "type") {
    return withSelectionError(state, "select_action_invalid");
  }
  if (action.type !== GENERATION_STRATEGY_SELECT_ACTION) {
    return withSelectionError(state, "select_action_unsupported");
  }
  const strategyId = typeof action.strategy_id === "string"
    ? action.strategy_id.trim().toLowerCase()
    : "";
  const strategy = state.catalog.strategies.find(
    (item) => item.strategy_id === strategyId,
  );
  if (!strategy) return withSelectionError(state, "strategy_unknown");
  if (!strategy.enabled) return withSelectionError(state, "strategy_disabled");
  return deepFreeze({
    ...state,
    selected_strategy_id: strategy.strategy_id,
    selection_origin: "explicit_select_action",
    selection_error: null,
  });
}

export function selectedGenerationStrategySummary(state) {
  const strategy = state?.catalog?.strategies?.find(
    (item) => item.strategy_id === state.selected_strategy_id,
  );
  if (!strategy || state.selection_origin !== "explicit_select_action") {
    return deepFreeze({
      ok: false,
      code: "strategy_not_selected",
      summary: null,
    });
  }
  return deepFreeze({
    ok: true,
    code: null,
    summary: {
      strategy_id: strategy.strategy_id,
      public_label: strategy.public_label,
      public_summary: strategy.public_summary,
      preservation_notice: strategy.preservation_notice,
      transformation_kind: strategy.transformation_kind,
      source_reference_mode: strategy.source_reference_mode,
      human_review_required: strategy.human_review_required,
      provider: strategy.provider,
      recipe: strategy.recipe,
      recipe_version: strategy.recipe_version,
      required_asset_roles: strategy.asset_roles.map((role) => ({
        role: role.role,
        min_count: role.min_count,
        max_count: role.max_count,
        media_kind: role.media_kind,
      })),
      required_attestation_ids: strategy.required_attestations.map(
        (item) => item.id,
      ),
      output_rules: strategy.output_rules,
      pricing: strategy.pricing,
    },
  });
}

function validationError(code, field) {
  return { code, field };
}

export function validateSelectedGenerationStrategyDraft(state, draft) {
  const selected = selectedGenerationStrategySummary(state);
  if (!selected.ok) {
    return deepFreeze({
      ok: false,
      strategy_id: null,
      errors: [validationError(selected.code, "strategy_id")],
      normalized: null,
    });
  }
  const strategy = state.catalog.strategies.find(
    (item) => item.strategy_id === selected.summary.strategy_id,
  );
  const errors = [];
  if (!strategy.enabled) {
    errors.push(validationError("strategy_disabled", "strategy_id"));
  }
  if (!isPlainObject(draft)) {
    errors.push(validationError("draft_invalid", "draft"));
    return deepFreeze({
      ok: false,
      strategy_id: strategy.strategy_id,
      errors,
      normalized: null,
    });
  }
  const unknownDraftField = Object.keys(draft).find(
    (key) => !DRAFT_KEYS.includes(key),
  );
  if (unknownDraftField) {
    errors.push(validationError("draft_field_unknown", unknownDraftField));
  }
  const duration = draft.duration_seconds;
  if (
    !Number.isSafeInteger(duration) ||
    duration < strategy.output_rules.duration.min_seconds ||
    duration > strategy.output_rules.duration.max_seconds
  ) {
    errors.push(validationError("duration_unsupported", "duration_seconds"));
  }
  if (typeof draft.audio !== "boolean") {
    errors.push(validationError("audio_invalid", "audio"));
  }
  const dimensionField = strategy.output_rules.dimension_field;
  if (dimensionField === "ratio") {
    if (!strategy.output_rules.ratios.includes(draft.ratio)) {
      errors.push(validationError("ratio_unsupported", "ratio"));
    }
    if (Object.prototype.hasOwnProperty.call(draft, "resolution")) {
      errors.push(validationError("dimension_field_forbidden", "resolution"));
    }
  } else {
    if (!strategy.output_rules.resolutions.includes(draft.resolution)) {
      errors.push(validationError("resolution_unsupported", "resolution"));
    }
    if (Object.prototype.hasOwnProperty.call(draft, "ratio")) {
      errors.push(validationError("dimension_field_forbidden", "ratio"));
    }
  }

  const assetCounts = isPlainObject(draft.asset_counts) ? draft.asset_counts : null;
  if (!assetCounts) {
    errors.push(validationError("asset_counts_invalid", "asset_counts"));
  } else {
    const roleIds = strategy.asset_roles.map((role) => role.role);
    for (const key of Object.keys(assetCounts)) {
      if (!roleIds.includes(key)) {
        errors.push(validationError("asset_role_unknown", `asset_counts.${key}`));
      }
    }
    for (const role of strategy.asset_roles) {
      const count = Object.prototype.hasOwnProperty.call(assetCounts, role.role)
        ? assetCounts[role.role]
        : 0;
      if (
        !Number.isSafeInteger(count) ||
        count < role.min_count ||
        count > role.max_count
      ) {
        errors.push(validationError(
          "asset_role_count_invalid",
          `asset_counts.${role.role}`,
        ));
      }
    }
  }

  const attestations = isPlainObject(draft.attestations)
    ? draft.attestations
    : null;
  if (!attestations) {
    errors.push(validationError("attestations_invalid", "attestations"));
  } else {
    const attestationIds = strategy.required_attestations.map((item) => item.id);
    for (const key of Object.keys(attestations)) {
      if (!attestationIds.includes(key)) {
        errors.push(validationError("attestation_unknown", `attestations.${key}`));
      }
    }
    for (const id of attestationIds) {
      if (attestations[id] !== true) {
        errors.push(validationError("attestation_required", `attestations.${id}`));
      }
    }
  }

  const ok = errors.length === 0;
  return deepFreeze({
    ok,
    strategy_id: strategy.strategy_id,
    errors,
    normalized: ok ? {
      strategy_id: strategy.strategy_id,
      duration_seconds: duration,
      ratio: dimensionField === "ratio" ? draft.ratio : null,
      resolution: dimensionField === "resolution" ? draft.resolution : null,
      audio: draft.audio,
      asset_counts: { ...assetCounts },
      attestations: { ...attestations },
    } : null,
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function countCopy(role) {
  if (role.min_count === role.max_count) {
    return role.min_count === 1
      ? "1 файл · обязательно"
      : `${role.min_count} файла · обязательно`;
  }
  if (role.min_count === 0) return `до ${role.max_count} файлов · необязательно`;
  return `${role.min_count}–${role.max_count} файлов`;
}

function mediaKindCopy(kind) {
  return kind === "video" ? "видео" : "изображение";
}

function sourceUseCopy(sourceUse) {
  return sourceUse === "provider_input"
    ? "передаётся в рецепт"
    : "только референс механики или стиля";
}

function disabledReasonCopy(code) {
  return DISABLED_REASON_COPY[code]
    || `Стратегия отключена сервером: ${code}`;
}

function pricingMarkup(strategy) {
  const pricing = strategy.pricing;
  return `
    <div class="generation-strategy-card__pricing">
      <h4>Цена ${escapeHtml(strategy.provider)} по серверному каталогу</h4>
      <ul>
        ${Object.entries(pricing.tiers).map(([resolution, formula]) => `
          <li>
            <strong>${escapeHtml(resolution)}</strong>
            <span>${formula.base_credits} кредитов за ${pricing.base_duration_seconds} с + ${formula.additional_credits_per_second} за каждую следующую секунду</span>
          </li>
        `).join("")}
      </ul>
      <small>1 кредит = ${(pricing.usd_cents_per_credit / 100).toFixed(2)} USD до налогов · версия ${escapeHtml(pricing.pricing_version)}</small>
    </div>
  `;
}

function strategyCardMarkup(strategy, selectedStrategyId, moduleIndex = 0) {
  const selected = strategy.strategy_id === selectedStrategyId;
  const duration = strategy.output_rules.duration;
  const moduleNumber = String(moduleIndex + 1).padStart(2, "0");
  return `
    <article
      class="generation-strategy-card${selected ? " is-selected" : ""}${strategy.enabled ? "" : " is-disabled"}"
      data-generation-strategy-card="${escapeHtml(strategy.strategy_id)}"
      data-generation-strategy-module="${escapeHtml(strategy.strategy_id)}"
      data-generation-strategy-enabled="${strategy.enabled ? "true" : "false"}"
      data-state="${selected ? "selected" : strategy.enabled ? "available" : "blocked"}"
      aria-label="Модуль ${escapeHtml(moduleNumber)}. ${escapeHtml(strategy.public_label)}"
      ${selected ? 'aria-current="true"' : ""}
      ${strategy.enabled ? "" : 'aria-disabled="true"'}
    >
      <header>
        <div>
          <p class="eyebrow">МОДУЛЬ ${escapeHtml(moduleNumber)} · ${escapeHtml(strategy.provider)} · ${escapeHtml(strategy.recipe)}</p>
          <h3>${escapeHtml(strategy.public_label)}</h3>
          <p>${escapeHtml(strategy.public_summary)}</p>
        </div>
        ${selected ? '<span class="badge badge-success">Выбрано вручную</span>' : ""}
      </header>
      <div class="generation-strategy-card__preservation" role="note">
        <strong>Что сохраняется и что создаётся заново</strong>
        <p>${escapeHtml(strategy.preservation_notice)}</p>
      </div>
      <div class="generation-strategy-card__requirements">
        <section>
          <h4>Нужные материалы</h4>
          <ul>
            ${strategy.asset_roles.map((role) => `
              <li data-generation-strategy-role="${escapeHtml(role.role)}">
                <strong>${escapeHtml(role.public_label)}</strong>
                <span>${escapeHtml(mediaKindCopy(role.media_kind))} · ${escapeHtml(countCopy(role))} · ${escapeHtml(sourceUseCopy(role.source_use))}</span>
              </li>
            `).join("")}
          </ul>
        </section>
        <section>
          <h4>Подтверждения прав</h4>
          <ul>
            ${strategy.required_attestations.map((item) => `
              <li data-generation-strategy-attestation="${escapeHtml(item.id)}">${escapeHtml(item.public_label)}</li>
            `).join("")}
          </ul>
        </section>
      </div>
      <div class="generation-strategy-card__output">
        <strong>Результат: ${duration.min_seconds}–${duration.max_seconds} с</strong>
        <span>${strategy.output_rules.dimension_field === "ratio"
          ? `Форматы: ${strategy.output_rules.ratios.map(escapeHtml).join(", ")}`
          : `Качество: ${strategy.output_rules.resolutions.map(escapeHtml).join(", ")}`}</span>
        <span>Аудио задаётся явно · значение рецепта по умолчанию: ${strategy.output_rules.audio.provider_default ? "включено" : "выключено"}</span>
        <small>Перед публикацией результат обязательно проверяет человек.</small>
      </div>
      ${pricingMarkup(strategy)}
      ${strategy.enabled ? "" : `
        <p class="generation-strategy-card__disabled" data-generation-strategy-disabled-reason="${escapeHtml(strategy.disabled_reason)}" role="status">
          ${escapeHtml(disabledReasonCopy(strategy.disabled_reason))}
          <small>Код сервера: ${escapeHtml(strategy.disabled_reason)}</small>
        </p>
      `}
      <button
        class="btn ${selected ? "btn-secondary" : ""}"
        type="button"
        data-action="select-generation-strategy"
        data-generation-strategy-action="SELECT"
        data-strategy-id="${escapeHtml(strategy.strategy_id)}"
        aria-pressed="${selected ? "true" : "false"}"
        ${strategy.enabled ? "" : "disabled"}
      >${selected ? "Выбрано вручную" : strategy.enabled ? "Выбрать стратегию" : "Сейчас недоступно"}</button>
    </article>
  `;
}

export function generationStrategyViewMarkup(state) {
  if (!state || state.catalog_status !== "ready" || !state.catalog) {
    const code = state?.catalog_error?.code || "catalog_unavailable";
    return `
      <section class="generation-strategy-view" data-generation-strategy-status="invalid">
        <div class="alert alert-warning" role="alert">
          <strong>Стратегии генерации временно недоступны.</strong>
          <span>Серверный каталог не прошёл строгую проверку. Ничего не выбрано и не применяется.</span>
          <small>Код: ${escapeHtml(code)}</small>
          <button
            type="button"
            class="btn"
            data-generation-strategy-catalog-retry
          >Повторить загрузку</button>
        </div>
      </section>
    `;
  }
  const selected = selectedGenerationStrategySummary(state);
  return `
    <section
      class="generation-strategy-view"
      data-generation-strategy-status="ready"
      data-selected-strategy-id="${escapeHtml(state.selected_strategy_id || "")}"
      aria-labelledby="generation-strategy-title"
    >
      <header class="generation-strategy-view__header">
        <div>
          <p class="eyebrow">Способ создания</p>
          <h2 id="generation-strategy-title">Как создать ролик по вирусному референсу</h2>
          <p>Сравните три стратегии, требования и цену. Выбор выполняется только вручную отдельной кнопкой.</p>
        </div>
        <span class="badge ${selected.ok ? "badge-success" : "badge-warning"}">
          ${selected.ok ? "Стратегия выбрана" : "Стратегия не выбрана"}
        </span>
      </header>
      ${state.selection_error ? `
        <p class="generation-strategy-view__selection-error" role="status">Выбор не изменён · ${escapeHtml(state.selection_error)}</p>
      ` : ""}
      <div class="generation-strategy-view__cards">
        ${state.catalog.strategies.map((strategy, moduleIndex) =>
          strategyCardMarkup(strategy, state.selected_strategy_id, moduleIndex)
        ).join("")}
      </div>
      ${selected.ok ? `
        <aside class="generation-strategy-view__selected" data-selected-strategy-summary="${escapeHtml(selected.summary.strategy_id)}">
          <strong>Вы выбрали: ${escapeHtml(selected.summary.public_label)}</strong>
          <p>${escapeHtml(selected.summary.preservation_notice)}</p>
          <small>Это только локальный выбор интерфейса. Генерация и списание не запускаются.</small>
        </aside>
      ` : `
        <aside class="generation-strategy-view__selected" data-selected-strategy-summary="none">
          <strong>Ничего не выбрано</strong>
          <p>Интерфейс не подставляет стратегию автоматически. Нажмите «Выбрать стратегию» на подходящей доступной карточке.</p>
        </aside>
      `}
    </section>
  `;
}
