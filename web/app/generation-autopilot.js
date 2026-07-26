const REAL_GENERATION_MODES = new Set([
  "real_photo",
  "real_gen4",
  "real_seedance",
]);

export function chooseInitialGenerationMedia(items, { real = false } = {}) {
  const candidates = (Array.isArray(items) ? items : [])
    .map((item) => ({
      id: String(item?.public_id || item?.id || "").trim(),
      paidReady: item?.identity_verified === true
        && item?.rights_confirmed === true
        && Boolean(String(item?.sku || "").trim())
        && Boolean(String(item?.product_name || "").trim()),
    }))
    .filter((item) => item.id && (!real || item.paidReady));
  return candidates.length === 1 ? candidates[0].id : "";
}

export function resolveGenerationPlatform({
  mode = "mock",
  currentPlatform = "",
  automaticPlatform = "",
} = {}) {
  const normalizedMode = String(mode || "mock").trim();
  const current = String(currentPlatform || "").trim();
  if (!REAL_GENERATION_MODES.has(normalizedMode)) {
    return {
      value: current,
      preferred: "",
      automatic: false,
    };
  }

  const preferred = normalizedMode === "real_photo"
    ? "wildberries"
    : "tiktok";
  const previousAutomatic = String(automaticPlatform || "").trim();
  const canApply = !current
    || current === "instagram"
    || Boolean(previousAutomatic && current === previousAutomatic);
  return {
    value: canApply ? preferred : current,
    preferred,
    automatic: canApply,
  };
}

export function resolveGenerationDestination({
  batches = [],
  platform = "",
  currentDestination = "",
  automaticDestination = "",
} = {}) {
  const selectedPlatform = String(platform || "").trim().toLowerCase();
  const current = String(currentDestination || "").trim();
  const previousAutomatic = String(automaticDestination || "").trim();
  const destinations = new Map();

  for (const batch of Array.isArray(batches) ? batches : []) {
    const status = String(batch?.status || "").trim().toLowerCase();
    if (["failed", "cancelled"].includes(status)) continue;
    const parameters = batch?.parameters && typeof batch.parameters === "object"
      ? batch.parameters
      : batch?.input && typeof batch.input === "object"
        ? batch.input
        : {};
    const candidatePlatform = String(
      parameters.platform || batch?.platform || "",
    ).trim().toLowerCase();
    const destination = String(
      parameters.destination_ref || parameters.destination || "",
    ).trim();
    if (
      !selectedPlatform
      || candidatePlatform !== selectedPlatform
      || destination.length < 2
      || destination.length > 240
    ) continue;
    if (!destinations.has(destination)) destinations.set(destination, destination);
  }

  const preferred = destinations.size === 1
    ? destinations.values().next().value
    : "";
  const currentIsAutomatic = Boolean(
    previousAutomatic && current === previousAutomatic,
  );
  const canApply = !current || currentIsAutomatic;
  if (preferred && canApply) {
    return {
      value: preferred,
      preferred,
      automatic: true,
      candidateCount: 1,
    };
  }
  return {
    value: currentIsAutomatic && !preferred ? "" : current,
    preferred,
    automatic: false,
    candidateCount: destinations.size,
  };
}

export function generationPreflightDecision(entry = {}, {
  force = false,
  now = Date.now(),
  readyTtlMs = 2 * 60 * 1_000,
  errorCooldownMs = 30_000,
} = {}) {
  const status = String(entry?.status || "idle");
  if (status === "loading") return "join";
  const checkedAt = Number(entry?.checkedAt) || 0;
  const age = Math.max(0, Number(now) - checkedAt);
  if (!force && status === "ready" && checkedAt > 0 && age < readyTtlMs) {
    return "reuse_ready";
  }
  if (!force && status === "error" && checkedAt > 0 && age < errorCooldownMs) {
    return "reuse_error";
  }
  return "request";
}
