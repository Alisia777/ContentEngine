/*
 * Immutable launch metadata for multi-model generation (§12).
 *
 * This pure module creates and reads one exact audit snapshot. It does not
 * infer missing historical metadata, persist data, read secrets, validate a
 * provider receipt's freshness, calculate price, or authorize a paid call.
 */

import {
  GENERATION_MODEL_CATALOG_VERSION,
  generationModelCatalogEntry,
} from "./generation-model-catalog.js";

export const GENERATION_SELECTION_SOURCES = Object.freeze([
  "system_recommendation",
  "research_recommendation",
  "performance_recommendation",
  "manual_choice",
  "alternative_after_block",
]);

export const GENERATION_ACCEPTANCE_STATUSES = Object.freeze([
  "accepted",
  "needs_revalidation",
  "unproven",
]);

export const GENERATION_SELECTION_SNAPSHOT_FIELDS = Object.freeze([
  "provider",
  "model",
  "model_public_label",
  "selection_source",
  "recommendation_reason_codes",
  "recommendation_warning_codes",
  "recommendation_catalog_version",
  "pricing_version",
  "estimated_cost_minor",
  "requested_duration_seconds",
  "requested_ratio",
  "requested_resolution",
  "requested_audio",
  "input_mode",
  "reference_count",
  "acceptance_status_at_launch",
  "provider_readiness_receipt_id",
]);

const EXACT_SELECTION_KEYS = Object.freeze([
  "ok",
  "provider",
  "model",
  "inputMode",
  "durationSeconds",
  "ratio",
  "resolution",
  "audio",
  "spokenDialogue",
  "referenceImageCount",
  "referenceVideo",
  "firstFrame",
  "lastFrame",
  "catalogVersion",
  "pricingVersion",
]);

const EXACT_LAUNCH_KEYS = Object.freeze([
  "selectionSource",
  "recommendationReasonCodes",
  "recommendationWarningCodes",
  "recommendationCatalogVersion",
  "pricingVersion",
  "estimatedCostMinor",
  "acceptanceStatusAtLaunch",
  "providerReadinessReceiptId",
]);

const SOURCE_SET = new Set(GENERATION_SELECTION_SOURCES);
const ACCEPTANCE_SET = new Set(GENERATION_ACCEPTANCE_STATUSES);
const SAFE_TOKEN_PATTERN = /^[a-z][a-z0-9_]{0,63}$/u;
const VERSION_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const PROVIDER_PATTERN = /^[a-z][a-z0-9_-]{0,31}$/u;
const MODEL_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const RATIO_PATTERN = /^\d{1,4}:\d{1,4}$/u;
const RESOLUTION_PATTERN = /^(?:\d{3,4}p|[1-9]\d?K)$/u;
const RECEIPT_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const MAX_PUBLIC_LABEL_LENGTH = 96;
const MAX_CODES = 32;
const MAX_TOTAL_CODE_LENGTH = 1_024;
const MAX_HISTORICAL_DURATION_SECONDS = 3_600;
const MAX_HISTORICAL_REFERENCE_COUNT = 64;
const INPUT_MODE_SET = new Set(["text", "image", "video"]);

export class GenerationSelectionSnapshotError extends Error {
  constructor(code) {
    super(`generation_selection_snapshot:${code}`);
    this.name = "GenerationSelectionSnapshotError";
    this.code = code;
  }
}

function fail(code) {
  throw new GenerationSelectionSnapshotError(code);
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function deepFreeze(value, seen = new Set()) {
  if (!value || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function assertExactKeys(value, keys, code) {
  if (!isPlainObject(value)) fail(code);
  const actual = Object.keys(value);
  if (actual.length !== keys.length) fail(code);
  const allowed = new Set(keys);
  if (actual.some((key) => !allowed.has(key))) fail(code);
}

function exactString(value, pattern, code) {
  if (
    typeof value !== "string" ||
    value !== value.trim() ||
    !pattern.test(value)
  ) fail(code);
  return value;
}

function exactPublicLabel(value) {
  if (
    typeof value !== "string" ||
    value !== value.trim() ||
    !value ||
    value.length > MAX_PUBLIC_LABEL_LENGTH ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) fail("model_public_label_invalid");
  return value;
}

function exactNonNegativeInteger(value, code) {
  if (!Number.isSafeInteger(value) || value < 0) fail(code);
  return value;
}

function exactCodes(value, code) {
  if (!Array.isArray(value) || value.length > MAX_CODES) fail(code);
  const result = [];
  const seen = new Set();
  let totalLength = 0;
  for (const item of value) {
    const token = exactString(item, SAFE_TOKEN_PATTERN, code);
    if (seen.has(token)) fail(code);
    seen.add(token);
    totalLength += token.length;
    if (totalLength > MAX_TOTAL_CODE_LENGTH) fail(code);
    result.push(token);
  }
  return result;
}

function canonicalEntry(entry) {
  if (!isPlainObject(entry)) fail("catalog_entry_invalid");
  const canonical = generationModelCatalogEntry(entry.provider, entry.model);
  if (canonical !== entry) fail("catalog_entry_not_canonical");
  return canonical;
}

function assertExactSelection(entry, selection) {
  assertExactKeys(selection, EXACT_SELECTION_KEYS, "selection_not_exact");
  if (
    selection.ok !== true ||
    selection.provider !== entry.provider ||
    selection.model !== entry.model ||
    selection.catalogVersion !== GENERATION_MODEL_CATALOG_VERSION ||
    selection.pricingVersion !== entry.pricingVersion
  ) fail("selection_binding_invalid");
  const contract = entry.server?.inputContracts?.[selection.inputMode];
  if (
    !contract ||
    !entry.inputModes.includes(selection.inputMode) ||
    !entry.allowedDurations.includes(selection.durationSeconds) ||
    !contract.allowedRatios.includes(selection.ratio) ||
    !contract.allowedResolutions.includes(selection.resolution) ||
    typeof selection.audio !== "boolean" ||
    typeof selection.spokenDialogue !== "boolean" ||
    typeof selection.referenceVideo !== "boolean" ||
    typeof selection.firstFrame !== "boolean" ||
    typeof selection.lastFrame !== "boolean" ||
    !Number.isSafeInteger(selection.referenceImageCount) ||
    selection.referenceImageCount < 0 ||
    selection.referenceImageCount > Number(contract.maxReferenceImages || 0)
  ) fail("selection_capability_invalid");
  const durationsForResolution = contract.allowedDurationsByResolution?.[selection.resolution];
  if (
    Array.isArray(durationsForResolution) &&
    !durationsForResolution.includes(selection.durationSeconds)
  ) fail("selection_capability_invalid");
  if (
    (selection.audio && !entry.supportsGeneratedAudio) ||
    (selection.spokenDialogue && !entry.supportsSpokenDialogue) ||
    (selection.spokenDialogue && !selection.audio) ||
    (selection.referenceVideo && contract.supportsReferenceVideo !== true) ||
    (selection.firstFrame && contract.supportsFirstFrame !== true) ||
    (selection.lastFrame && contract.supportsLastFrame !== true) ||
    (selection.lastFrame &&
      Number.isInteger(contract.lastFrameDurationSeconds) &&
      selection.durationSeconds !== contract.lastFrameDurationSeconds)
  ) fail("selection_capability_invalid");
}

function exactSnapshot(value, { requireCurrentVersions }) {
  assertExactKeys(value, GENERATION_SELECTION_SNAPSHOT_FIELDS, "snapshot_not_exact");
  const provider = exactString(value.provider, PROVIDER_PATTERN, "provider_invalid");
  const model = exactString(value.model, MODEL_PATTERN, "model_invalid");
  const entry = generationModelCatalogEntry(provider, model);
  if (!entry) fail("catalog_identity_unknown");
  const modelPublicLabel = exactPublicLabel(value.model_public_label);
  if (modelPublicLabel !== entry.publicLabel) fail("model_public_label_mismatch");

  const selectionSource = exactString(
    value.selection_source,
    SAFE_TOKEN_PATTERN,
    "selection_source_invalid",
  );
  if (!SOURCE_SET.has(selectionSource)) fail("selection_source_invalid");
  const reasonCodes = exactCodes(
    value.recommendation_reason_codes,
    "recommendation_reason_codes_invalid",
  );
  const warningCodes = exactCodes(
    value.recommendation_warning_codes,
    "recommendation_warning_codes_invalid",
  );
  const catalogVersion = exactString(
    value.recommendation_catalog_version,
    VERSION_PATTERN,
    "catalog_version_invalid",
  );
  const pricingVersion = exactString(
    value.pricing_version,
    VERSION_PATTERN,
    "pricing_version_invalid",
  );
  if (
    requireCurrentVersions &&
    (catalogVersion !== GENERATION_MODEL_CATALOG_VERSION ||
      pricingVersion !== entry.pricingVersion)
  ) fail("version_parity_invalid");

  const durationSeconds = exactNonNegativeInteger(
    value.requested_duration_seconds,
    "duration_invalid",
  );
  const ratio = exactString(value.requested_ratio, RATIO_PATTERN, "ratio_invalid");
  const resolution = exactString(
    value.requested_resolution,
    RESOLUTION_PATTERN,
    "resolution_invalid",
  );
  if (!INPUT_MODE_SET.has(value.input_mode)) fail("input_mode_invalid");
  if (durationSeconds > MAX_HISTORICAL_DURATION_SECONDS) fail("duration_invalid");
  if (typeof value.requested_audio !== "boolean") fail("audio_invalid");
  const referenceCount = exactNonNegativeInteger(
    value.reference_count,
    "reference_count_invalid",
  );
  if (referenceCount > MAX_HISTORICAL_REFERENCE_COUNT) fail("reference_count_invalid");
  if (requireCurrentVersions) {
    const contract = entry.server?.inputContracts?.[value.input_mode];
    if (
      !contract ||
      !entry.inputModes.includes(value.input_mode) ||
      !entry.allowedDurations.includes(durationSeconds) ||
      !contract.allowedRatios.includes(ratio) ||
      !contract.allowedResolutions.includes(resolution) ||
      (value.requested_audio && !entry.supportsGeneratedAudio) ||
      referenceCount > Number(contract.maxReferenceImages || 0)
    ) fail("snapshot_capability_invalid");
    const durationsForResolution = contract.allowedDurationsByResolution?.[resolution];
    if (
      Array.isArray(durationsForResolution) &&
      !durationsForResolution.includes(durationSeconds)
    ) fail("snapshot_capability_invalid");
  }
  const acceptanceStatus = exactString(
    value.acceptance_status_at_launch,
    SAFE_TOKEN_PATTERN,
    "acceptance_status_invalid",
  );
  if (!ACCEPTANCE_SET.has(acceptanceStatus)) fail("acceptance_status_invalid");
  const receiptId = value.provider_readiness_receipt_id === ""
    ? ""
    : exactString(
      value.provider_readiness_receipt_id,
      RECEIPT_ID_PATTERN,
      "readiness_receipt_id_invalid",
    );

  return deepFreeze({
    provider,
    model,
    model_public_label: modelPublicLabel,
    selection_source: selectionSource,
    recommendation_reason_codes: reasonCodes,
    recommendation_warning_codes: warningCodes,
    recommendation_catalog_version: catalogVersion,
    pricing_version: pricingVersion,
    estimated_cost_minor: exactNonNegativeInteger(
      value.estimated_cost_minor,
      "estimated_cost_invalid",
    ),
    requested_duration_seconds: durationSeconds,
    requested_ratio: ratio,
    requested_resolution: resolution,
    requested_audio: value.requested_audio,
    input_mode: value.input_mode,
    reference_count: referenceCount,
    acceptance_status_at_launch: acceptanceStatus,
    provider_readiness_receipt_id: receiptId,
  });
}

export function createGenerationSelectionSnapshot(entry, selection, launchMetadata) {
  const canonical = canonicalEntry(entry);
  assertExactSelection(canonical, selection);
  assertExactKeys(launchMetadata, EXACT_LAUNCH_KEYS, "launch_metadata_not_exact");
  if (
    launchMetadata.recommendationCatalogVersion !== GENERATION_MODEL_CATALOG_VERSION ||
    launchMetadata.pricingVersion !== canonical.pricingVersion
  ) fail("version_parity_invalid");
  return exactSnapshot({
    provider: canonical.provider,
    model: canonical.model,
    model_public_label: canonical.publicLabel,
    selection_source: launchMetadata.selectionSource,
    recommendation_reason_codes: launchMetadata.recommendationReasonCodes,
    recommendation_warning_codes: launchMetadata.recommendationWarningCodes,
    recommendation_catalog_version: launchMetadata.recommendationCatalogVersion,
    pricing_version: launchMetadata.pricingVersion,
    estimated_cost_minor: launchMetadata.estimatedCostMinor,
    requested_duration_seconds: selection.durationSeconds,
    requested_ratio: selection.ratio,
    requested_resolution: selection.resolution,
    requested_audio: selection.audio,
    input_mode: selection.inputMode,
    reference_count: selection.referenceImageCount,
    acceptance_status_at_launch: launchMetadata.acceptanceStatusAtLaunch,
    provider_readiness_receipt_id: launchMetadata.providerReadinessReceiptId,
  }, { requireCurrentVersions: true });
}

export function readGenerationSelectionSnapshot(value) {
  if (value === null || value === undefined) {
    return deepFreeze({ state: "legacy_absent", snapshot: null });
  }
  return deepFreeze({
    state: "present",
    snapshot: exactSnapshot(value, { requireCurrentVersions: false }),
  });
}

/**
 * Audit metadata is not launch authority. This helper only distinguishes an
 * honestly absent receipt from a syntactically present UUID. A real paid gate
 * must still load and validate the corresponding fresh, exact-scope receipt.
 * The name intentionally says `ReceiptId`: true is not authorization.
 */
export function generationSelectionSnapshotHasReceiptId(snapshot) {
  const present = readGenerationSelectionSnapshot(snapshot);
  if (present.state !== "present") return false;
  return RECEIPT_ID_PATTERN.test(
    present.snapshot.provider_readiness_receipt_id,
  );
}
