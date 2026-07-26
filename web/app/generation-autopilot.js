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
