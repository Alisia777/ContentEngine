/**
 * Strict browser projection of one server-issued provider-readiness receipt.
 *
 * This module never prices a model, infers a provider, authorizes a launch, or
 * treats an API response as consent. It validates immutable v3 receipts for
 * the three legacy models and exact spec-bound v4 receipts for the four new
 * Runway models. The paid start still reloads and atomically consumes the
 * receipt against the exact actor, project, spec and server-computed scope.
 */

const PROVIDER_RECEIPT_VERSION_V3 =
  "generation-provider-readiness-receipt-v3";
const PROVIDER_RECEIPT_VERSION_V4 =
  "generation-provider-readiness-receipt-v4";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const SAFE_MODEL_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const SAFE_VERSION_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const SAFE_CONFIRMATION_PATTERN = /^[A-Z0-9][A-Z0-9_.:-]{2,255}$/u;
const RATIO_PATTERN = /^\d{1,4}:\d{1,4}$/u;
const RESOLUTION_PATTERN = /^(?:\d{3,4}p|[1-9]\d?K)$/u;
const PROVIDERS = new Set(["runway", "google"]);
const INPUT_MODES = new Set(["image"]);
const RECEIPT_TTL_MS = 15 * 60 * 1_000;
const FUTURE_SKEW_MS = 60 * 1_000;

const RECEIPT_KEYS = Object.freeze([
  "version",
  "receipt_id",
  "receipt_hash",
  "organization_id",
  "checked_by",
  "provider",
  "model",
  "input_mode",
  "duration_seconds",
  "format",
  "resolution",
  "audio",
  "last_frame",
  "ready",
  "estimated_cost_minor",
  "estimated_credits",
  "credential_configured",
  "balance_sufficient",
  "model_available",
  "daily_quota_available",
  "failure_code",
  "catalog_version",
  "pricing_version",
  "learning_gate_version",
  "checked_at",
  "expires_at",
  "status",
  "fresh",
  "spend_confirmation",
  "automatic_generation",
  "automatic_spend",
]);
const RECEIPT_V4_KEYS = Object.freeze([
  ...RECEIPT_KEYS,
  "project_id",
  "spec_id",
  "spec_version",
  "spec_hash",
  "scope_hash",
]);

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function hasExactKeys(value, keys) {
  const actual = Object.keys(value);
  if (actual.length !== keys.length) return false;
  const allowed = new Set(keys);
  return actual.every((key) => allowed.has(key));
}

function exactNullableBoolean(value) {
  return value === null || typeof value === "boolean";
}

function selectionValue(source = {}) {
  const value = objectValue(source) || {};
  return Object.freeze({
    provider: safeText(value.provider),
    model: safeText(value.model),
    inputMode: safeText(value.inputMode ?? value.input_mode),
    durationSeconds: Number(value.durationSeconds ?? value.duration_seconds),
    ratio: safeText(value.ratio ?? value.format),
    resolution: safeText(value.resolution),
    audio: value.audio,
    lastFrame: value.lastFrame ?? value.last_frame,
  });
}

function generationSpecContextValue(source = {}) {
  const value = objectValue(
    source.generationSpecContext ?? source.generation_spec_context ?? source,
  ) || {};
  return Object.freeze({
    specId: safeText(value.specId ?? value.spec_id).toLowerCase(),
    specVersion: Number(value.specVersion ?? value.spec_version),
    specHash: safeText(value.specHash ?? value.spec_hash).toLowerCase(),
  });
}

function matchesExpectedSpec(receipt, options = {}) {
  if (receipt.version !== PROVIDER_RECEIPT_VERSION_V4) return true;
  const projectId = safeText(options.projectId ?? options.project_id)
    .toLowerCase();
  const expected = generationSpecContextValue(options);
  return Boolean(
    (!projectId || safeText(receipt.project_id).toLowerCase() === projectId)
    && (!expected.specId
      || safeText(receipt.spec_id).toLowerCase() === expected.specId)
    && (!Number.isSafeInteger(expected.specVersion)
      || receipt.spec_version === expected.specVersion)
    && (!expected.specHash
      || safeText(receipt.spec_hash).toLowerCase() === expected.specHash)
  );
}

function matchesExpectedSelection(receipt, expectedSelection) {
  if (!expectedSelection) return true;
  const expected = selectionValue(expectedSelection);
  return Boolean(
    expected.provider
    && expected.model
    && expected.inputMode
    && Number.isSafeInteger(expected.durationSeconds)
    && RATIO_PATTERN.test(expected.ratio)
    && RESOLUTION_PATTERN.test(expected.resolution)
    && typeof expected.audio === "boolean"
    && typeof expected.lastFrame === "boolean"
    && receipt.provider === expected.provider
    && receipt.model === expected.model
    && receipt.input_mode === expected.inputMode
    && receipt.duration_seconds === expected.durationSeconds
    && receipt.format === expected.ratio
    && receipt.resolution === expected.resolution
    && receipt.audio === expected.audio
    && receipt.last_frame === expected.lastFrame
  );
}

function exactReadyReceipt(value, options = {}) {
  const item = objectValue(value);
  const nowMs = Number(options.nowMs ?? Date.now());
  if (!item || !Number.isFinite(nowMs)) {
    return null;
  }

  const provider = safeText(item.provider);
  const model = safeText(item.model);
  const requiredVersion = safeText(options.requiredVersion);
  const specBound = item.version === PROVIDER_RECEIPT_VERSION_V4;
  const expectedVersion = specBound
    ? PROVIDER_RECEIPT_VERSION_V4
    : PROVIDER_RECEIPT_VERSION_V3;
  const expectedKeys = specBound ? RECEIPT_V4_KEYS : RECEIPT_KEYS;
  if (!hasExactKeys(item, expectedKeys)) return null;
  const inputMode = safeText(item.input_mode);
  const format = safeText(item.format);
  const resolution = safeText(item.resolution);
  const durationSeconds = Number(item.duration_seconds);
  const estimatedCostMinor = Number(item.estimated_cost_minor);
  const checkedAt = safeText(item.checked_at);
  const expiresAt = safeText(item.expires_at);
  const checkedAtMs = Date.parse(checkedAt);
  const expiresAtMs = Date.parse(expiresAt);
  const gateVersion = safeText(options.gateVersion);
  const catalogVersion = safeText(options.catalogVersion);
  const pricingVersion = safeText(options.pricingVersion);
  const organizationId = safeText(options.organizationId).toLowerCase();
  const actorId = safeText(options.actorId).toLowerCase();
  const projectId = safeText(item.project_id).toLowerCase();
  const specId = safeText(item.spec_id).toLowerCase();
  const specVersion = Number(item.spec_version);
  const specHash = safeText(item.spec_hash).toLowerCase();
  const scopeHash = safeText(item.scope_hash).toLowerCase();

  if (
    item.version !== expectedVersion
    || (requiredVersion && item.version !== requiredVersion)
    || !UUID_PATTERN.test(safeText(item.receipt_id))
    || !SHA256_PATTERN.test(safeText(item.receipt_hash))
    || !UUID_PATTERN.test(safeText(item.organization_id))
    || !UUID_PATTERN.test(safeText(item.checked_by))
    || (organizationId && safeText(item.organization_id).toLowerCase() !== organizationId)
    || (actorId && safeText(item.checked_by).toLowerCase() !== actorId)
    || !PROVIDERS.has(provider)
    || !SAFE_MODEL_PATTERN.test(model)
    || !INPUT_MODES.has(inputMode)
    || !Number.isSafeInteger(durationSeconds)
    || durationSeconds < 0
    || durationSeconds > 3_600
    || !RATIO_PATTERN.test(format)
    || !RESOLUTION_PATTERN.test(resolution)
    || typeof item.audio !== "boolean"
    || typeof item.last_frame !== "boolean"
    || item.ready !== true
    || item.status !== "ready"
    || item.fresh !== true
    || item.failure_code !== null
    || !Number.isSafeInteger(estimatedCostMinor)
    || estimatedCostMinor < 0
    || !Number.isSafeInteger(item.estimated_credits) && item.estimated_credits !== null
    || Number(item.estimated_credits) < 0
    || item.credential_configured !== true
    || item.model_available !== true
    || !exactNullableBoolean(item.balance_sufficient)
    || !exactNullableBoolean(item.daily_quota_available)
    || (item.balance_sufficient !== null && item.balance_sufficient !== true)
    || (item.daily_quota_available !== null && item.daily_quota_available !== true)
    || (provider === "runway" && !Number.isSafeInteger(item.estimated_credits))
    || (provider === "runway" && item.balance_sufficient !== true)
    || (provider === "runway" && item.daily_quota_available !== true)
    || (provider === "google" && item.estimated_credits !== null)
    || !SAFE_VERSION_PATTERN.test(safeText(item.catalog_version))
    || !SAFE_VERSION_PATTERN.test(safeText(item.pricing_version))
    || !SAFE_VERSION_PATTERN.test(safeText(item.learning_gate_version))
    || (gateVersion && item.learning_gate_version !== gateVersion)
    || (catalogVersion && item.catalog_version !== catalogVersion)
    || (pricingVersion && item.pricing_version !== pricingVersion)
    || !SAFE_CONFIRMATION_PATTERN.test(safeText(item.spend_confirmation))
    || item.automatic_generation !== false
    || item.automatic_spend !== false
    || !Number.isFinite(checkedAtMs)
    || !Number.isFinite(expiresAtMs)
    || checkedAtMs > nowMs + FUTURE_SKEW_MS
    || expiresAtMs <= nowMs
    || expiresAtMs - checkedAtMs !== RECEIPT_TTL_MS
    || !matchesExpectedSelection(item, options.expectedSelection)
    || (specBound && (
      !UUID_PATTERN.test(projectId)
      || !UUID_PATTERN.test(specId)
      || !Number.isSafeInteger(specVersion)
      || specVersion < 1
      || specVersion > 100_000
      || !SHA256_PATTERN.test(specHash)
      || !SHA256_PATTERN.test(scopeHash)
      || !matchesExpectedSpec(item, options)
    ))
  ) return null;

  return Object.freeze({
    version: expectedVersion,
    receipt_id: safeText(item.receipt_id).toLowerCase(),
    receipt_hash: safeText(item.receipt_hash),
    organization_id: safeText(item.organization_id).toLowerCase(),
    checked_by: safeText(item.checked_by).toLowerCase(),
    provider,
    model,
    input_mode: inputMode,
    duration_seconds: durationSeconds,
    format,
    resolution,
    audio: item.audio,
    last_frame: item.last_frame,
    ready: true,
    estimated_cost_minor: estimatedCostMinor,
    estimated_credits: item.estimated_credits,
    credential_configured: true,
    balance_sufficient: item.balance_sufficient,
    model_available: true,
    daily_quota_available: item.daily_quota_available,
    failure_code: null,
    catalog_version: safeText(item.catalog_version),
    pricing_version: safeText(item.pricing_version),
    learning_gate_version: safeText(item.learning_gate_version),
    checked_at: checkedAt,
    expires_at: expiresAt,
    status: "ready",
    fresh: true,
    spend_confirmation: safeText(item.spend_confirmation),
    automatic_generation: false,
    automatic_spend: false,
    ...(specBound
      ? {
          project_id: projectId,
          spec_id: specId,
          spec_version: specVersion,
          spec_hash: specHash,
          scope_hash: scopeHash,
        }
      : {}),
  });
}

function receiptScopeKey(receipt) {
  return [
    receipt.provider,
    receipt.model,
    receipt.input_mode,
    receipt.duration_seconds,
    receipt.format,
    receipt.resolution,
    receipt.audio ? "audio" : "silent",
    receipt.last_frame ? "last" : "single",
    receipt.version === PROVIDER_RECEIPT_VERSION_V4
      ? `${receipt.project_id}:${receipt.spec_id}:${receipt.spec_version}:${receipt.spec_hash}`
      : PROVIDER_RECEIPT_VERSION_V3,
  ].join(":");
}

export function normalizeGenerationProviderPreflight(value, options = {}) {
  return exactReadyReceipt(value, options);
}

export function generationProviderReadinessPreflights(value, options = {}) {
  const source = objectValue(value?.data) || objectValue(value) || {};
  const rows = Array.isArray(source.provider_readiness)
    ? source.provider_readiness
    : [];
  const normalized = rows
    .map((row) => exactReadyReceipt(row, options))
    .filter(Boolean);
  const counts = new Map();
  for (const receipt of normalized) {
    const key = receiptScopeKey(receipt);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return Object.freeze(
    normalized.filter((receipt) => counts.get(receiptScopeKey(receipt)) === 1),
  );
}

export const GENERATION_PROVIDER_READINESS_RECEIPT_VERSION =
  PROVIDER_RECEIPT_VERSION_V3;

export const GENERATION_PROVIDER_READINESS_RECEIPT_VERSION_V4 =
  PROVIDER_RECEIPT_VERSION_V4;

export const GENERATION_PROVIDER_READINESS_RECEIPT_FIELDS = RECEIPT_KEYS;

export const GENERATION_PROVIDER_READINESS_RECEIPT_V4_FIELDS =
  RECEIPT_V4_KEYS;
