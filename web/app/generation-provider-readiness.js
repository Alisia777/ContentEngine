const PROVIDER_RECEIPT_VERSION =
  "generation-provider-readiness-receipt-v1";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const RECEIPT_TTL_MS = 15 * 60 * 1_000;
const FUTURE_SKEW_MS = 60 * 1_000;
const MODEL_CREDITS = Object.freeze({
  seedream5_lite: 4,
  gen4_turbo: 25,
  seedance2_fast: 232,
});

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function exactReadyReceipt(value, gateVersion, nowMs) {
  const item = objectValue(value);
  const model = safeText(item?.model);
  const estimatedCredits = MODEL_CREDITS[model];
  const checkedAt = safeText(item?.checked_at);
  const expiresAt = safeText(item?.expires_at);
  const checkedAtMs = Date.parse(checkedAt);
  const expiresAtMs = Date.parse(expiresAt);
  if (
    !item
    || estimatedCredits === undefined
    || item.provider !== "runway"
    || (item.status !== undefined && item.status !== "ready")
    || (
      item.reason_code !== undefined
      && item.reason_code !== "provider_ready"
    )
    || item.ready !== true
    || item.fresh !== true
    || item.balance_sufficient !== true
    || item.model_available !== true
    || item.daily_quota_available !== true
    || item.estimated_credits !== estimatedCredits
    || (
      item.failure_code !== undefined
      && item.failure_code !== null
    )
    || item.receipt_version !== PROVIDER_RECEIPT_VERSION
    || item.learning_gate_version !== gateVersion
    || !UUID_PATTERN.test(safeText(item.receipt_id))
    || !SHA256_PATTERN.test(safeText(item.receipt_hash))
    || !Number.isFinite(checkedAtMs)
    || !Number.isFinite(expiresAtMs)
    || checkedAtMs > nowMs + FUTURE_SKEW_MS
    || expiresAtMs <= nowMs
    || expiresAtMs - checkedAtMs !== RECEIPT_TTL_MS
  ) return null;
  return Object.freeze({
    provider: "runway",
    model,
    ready: true,
    estimated_credits: estimatedCredits,
    balance_sufficient: true,
    model_available: true,
    daily_quota_available: true,
    learning_gate_version: gateVersion,
    checked_at: checkedAt,
    expires_at: expiresAt,
    receipt_id: safeText(item.receipt_id),
    receipt_hash: safeText(item.receipt_hash),
    receipt_version: PROVIDER_RECEIPT_VERSION,
    fresh: true,
  });
}

export function normalizeGenerationProviderPreflight(
  value,
  {
    gateVersion = "",
    nowMs = Date.now(),
  } = {},
) {
  if (!safeText(gateVersion) || !Number.isFinite(nowMs)) return null;
  return exactReadyReceipt(value, gateVersion, nowMs);
}

export function generationProviderReadinessPreflights(
  value,
  {
    gateVersion = "",
    nowMs = Date.now(),
  } = {},
) {
  const source = objectValue(value?.data) || objectValue(value) || {};
  const rows = Array.isArray(source.provider_readiness)
    ? source.provider_readiness
    : [];
  if (!safeText(gateVersion) || !Number.isFinite(nowMs)) {
    return Object.freeze([]);
  }
  const counts = new Map();
  for (const row of rows) {
    const model = safeText(row?.model);
    if (!Object.hasOwn(MODEL_CREDITS, model)) continue;
    counts.set(model, (counts.get(model) || 0) + 1);
  }
  return Object.freeze(
    rows
      .map((row) => (
        row?.status === "ready" && row?.reason_code === "provider_ready"
          ? exactReadyReceipt(row, gateVersion, nowMs)
          : null
      ))
      .filter((receipt) => (
        receipt !== null && counts.get(receipt.model) === 1
      )),
  );
}

export const GENERATION_PROVIDER_READINESS_RECEIPT_VERSION =
  PROVIDER_RECEIPT_VERSION;
