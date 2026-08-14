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
  GENERATION_STRATEGY_CATALOG_VERSION,
  generationStrategyCatalogEntry,
  RUNWAY_RECIPE_PRICING_VERSION,
  RUNWAY_RECIPE_VERSION,
  validateGenerationStrategySelection,
} from "./generation-strategy-catalog.js";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256 = /^[0-9a-f]{64}$/u;
const TASK_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const SAFE_CODE = /^[a-z][a-z0-9_]{1,95}$/u;
const PROVIDER_PATHS = Object.freeze({
  viral_avatar_ugc: "/v1/recipes/product_ugc",
  viral_product_swap: "/v1/recipes/product_swap",
  viral_rebuild: "/v1/recipes/product_ad",
});
const RECIPES = Object.freeze({
  viral_avatar_ugc: "product_ugc",
  viral_product_swap: "product_swap",
  viral_rebuild: "product_ad",
});
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

function strategyIdentity(strategyId, recipe) {
  if (RECIPES[strategyId] !== recipe) return false;
  const entry = generationStrategyCatalogEntry(strategyId);
  return entry?.provider === "runway" && entry.recipe === recipe &&
    entry.recipe_version === RUNWAY_RECIPE_VERSION &&
    entry.pricing_version === RUNWAY_RECIPE_PRICING_VERSION &&
    entry.server?.provider_path === PROVIDER_PATHS[strategyId];
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
    strategyIdentity(value.strategy_id, value.recipe) &&
    value.catalog_version === GENERATION_STRATEGY_CATALOG_VERSION &&
    value.recipe_version === RUNWAY_RECIPE_VERSION &&
    value.pricing_version === RUNWAY_RECIPE_PRICING_VERSION &&
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
  if (
    value.strategyVersion !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.recipeVersion !== RUNWAY_RECIPE_VERSION ||
    value.strategyId !== expectedStrategy.strategy_id ||
    value.recipe !== expectedStrategy.recipe ||
    !strategyIdentity(value.strategyId, value.recipe) ||
    !integer(value.durationSeconds, 4, 15) || typeof value.audio !== "boolean"
  ) return null;
  const swap = value.recipe === "product_swap";
  if (swap) {
    if (
      value.ratio !== null ||
      !new Set(["720p", "1080p"]).has(value.resolution) ||
      value.userConcept !== null || value.userConceptHash !== null ||
      !(
        value.productInfo === null || text(value.productInfo, 1, 2_500)
      ) || !(
        value.productInfoHash === null || hash(value.productInfoHash)
      )
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
    const expectedFields = strategyId === "viral_avatar_ugc"
      ? { avatar_image: "characterImage", product_image: "productImage" }
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
    ? counts.get("avatar_image") === 1 && counts.get("product_image") === 1 &&
      value.length === 2
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
    !strategyIdentity(receipt.strategy_id, receipt.recipe) ||
    receipt.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    receipt.recipe_version !== RUNWAY_RECIPE_VERSION ||
    receipt.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
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
    value.version !== "generation-strategy-provider-policy-response-v1" ||
    !record(value.execution_capabilities) ||
    !exact(value.execution_capabilities, [expected.strategyId]) ||
    !exact(value.execution_capabilities[expected.strategyId], [
      "enabled",
      "catalog_version",
      "strategy_id",
      "provider",
      "recipe",
      "recipe_version",
      "provider_path",
      "pricing_version",
    ])
  ) return null;
  const capability = value.execution_capabilities[expected.strategyId];
  if (
    typeof capability.enabled !== "boolean" ||
    capability.strategy_id !== expected.strategyId ||
    !strategyIdentity(capability.strategy_id, capability.recipe) ||
    capability.provider !== "runway" ||
    capability.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    capability.recipe_version !== RUNWAY_RECIPE_VERSION ||
    capability.provider_path !== PROVIDER_PATHS[expected.strategyId] ||
    capability.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
    !exact(value.context, [
      "strategy_id",
      "provider",
      "recipe",
      "binding_id",
      "binding_hash",
      "provider_readiness_receipt_id",
      "provider_readiness_receipt_hash",
      "catalog_version",
      "recipe_version",
      "pricing_version",
    ]) || value.context.strategy_id !== expected.strategyId ||
    value.context.provider !== "runway" ||
    value.context.recipe !== capability.recipe ||
    value.context.binding_id !== expected.bindingId ||
    value.context.binding_hash !== expected.bindingHash ||
    value.context.provider_readiness_receipt_id !== expected.receiptId ||
    value.context.provider_readiness_receipt_hash !== expected.receiptHash ||
    value.context.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.context.recipe_version !== RUNWAY_RECIPE_VERSION ||
    value.context.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
    !exact(value.checks, [
      "strategy_binding_current",
      "generation_spec_approved",
      "provider_readiness_receipt_current",
      "provider_readiness_receipt_unconsumed",
      "sql_provider_configuration_enabled",
      "start_path_integrated",
    ]) ||
    Object.values(value.checks).some((item) => typeof item !== "boolean") ||
    !Array.isArray(value.blockers) ||
    value.blockers.some((item) =>
      typeof item !== "string" || !SAFE_CODE.test(item)
    ) ||
    typeof value.launch_enabled !== "boolean" ||
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
  return { launchEnabled: value.launch_enabled, blockers: [...value.blockers] };
}

export function readGenerationStrategyStartClaim(value, expected) {
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
    !strategyIdentity(value.strategy?.strategy_id, value.job.model_identity) ||
    !integer(value.job.duration_seconds, 4, 15) ||
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
  if (context === null || assets === null) return null;
  return { ...value, recipe_context: context, asset_context: assets };
}

export function readGenerationStrategyDispatchAttempt(value, expected) {
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
    !exact(value.attempt, [
      "id",
      "attempt_hash",
      "dispatch_token",
      "claim_id",
      "claim_hash",
      "generation_job_id",
      "reserved_at",
    ]) || !uuid(value.attempt.id) || !hash(value.attempt.attempt_hash) ||
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
  if (context === null || assets === null) return null;
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
    return Object.freeze({
      outcome: "ambiguous",
      provider_post_started: true,
      provider_http_status: null,
      provider_task_id: null,
      failure_code: "provider_submission_ambiguous",
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

function safeStatusSelection(value, strategy) {
  const validated = validateGenerationStrategySelection(value);
  return validated.ok === true &&
      validated.strategy_id === strategy.strategy_id &&
      validated.recipe === strategy.recipe &&
      validated.recipe_version === strategy.recipe_version &&
      validated.pricing_version === strategy.pricing_version
    ? validated
    : null;
}

function safeStatusPrice(value, strategy, selection) {
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
    value.provider !== "runway" || value.recipe !== strategy.recipe ||
    value.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
    value.recipe_version !== RUNWAY_RECIPE_VERSION ||
    value.duration_seconds !== selection.output.duration_seconds ||
    value.audio !== selection.output.audio ||
    value.resolution !== selection.output.resolution ||
    value.ratio !==
      (strategy.recipe === "product_swap"
        ? "source"
        : selection.output.ratio) ||
    value.input_mode !== ({
        product_ugc: "character_and_product_images",
        product_swap: "video_and_product_images",
        product_ad: "product_images",
      })[strategy.recipe] ||
    !integer(value.estimated_credits, 1, 1_000_000) ||
    value.estimated_credits !== selection.estimated_credits ||
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

function safeStatusError(value) {
  if (value === null) return null;
  return exact(value, ["code", "provider_billing_outcome"]) &&
      typeof value.code === "string" && SAFE_CODE.test(value.code) &&
      value.provider_billing_outcome === "unknown"
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
  const error = safeStatusError(value.error);
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
      value.job.provider_task_id === null)
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

export const GENERATION_STRATEGY_EDGE_CONTRACT = Object.freeze({
  catalogVersion: GENERATION_STRATEGY_CATALOG_VERSION,
  recipeVersion: RUNWAY_RECIPE_VERSION,
  pricingVersion: RUNWAY_RECIPE_PRICING_VERSION,
  recipes: RECIPES,
  providerPaths: PROVIDER_PATHS,
});
