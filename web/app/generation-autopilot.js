const REAL_GENERATION_MODES = new Set([
  "real_photo",
  "real_gen4",
  "real_seedance",
]);
const VIDEO_GENERATION_MODES = new Set([
  "real_gen4",
  "real_seedance",
]);
const GENERATION_MODE_CONTENT_KIND = Object.freeze({
  real_photo: "photo",
  real_gen4: "video",
  real_seedance: "video",
});
const GENERATION_FALLBACK_PRIORITY = Object.freeze({
  real_gen4: 0,
  real_seedance: 1,
  real_photo: 2,
});
const SEEDANCE_SPOKEN_WORD_LIMIT = 22;

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

export function resolveHandoffGenerationMode({
  handoff = null,
  availability = {},
  mockEnabled = true,
} = {}) {
  const scenario = handoff?.scenario && typeof handoff.scenario === "object"
    ? handoff.scenario
    : {};
  const requestedMode = VIDEO_GENERATION_MODES.has(
      String(scenario.recommendedGenerationMode || ""),
    )
    ? String(scenario.recommendedGenerationMode)
    : "";
  const spokenWords = String(scenario.spokenScript || "")
    .match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu)?.length || 0;
  const seedanceSpeechFits = spokenWords > 0
    && spokenWords <= SEEDANCE_SPOKEN_WORD_LIMIT;
  const recommendedMode = requestedMode === "real_gen4"
    ? "real_gen4"
    : requestedMode === "real_seedance" && seedanceSpeechFits
      ? "real_seedance"
      : seedanceSpeechFits
        ? "real_seedance"
        : "real_gen4";
  const source = requestedMode
    ? requestedMode === recommendedMode
      ? "research_recommendation"
      : "duration_constraint"
    : "provider_constraint";
  const suppliedReason = String(scenario.generationModeReason || "")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 400);
  const reason = source === "duration_constraint"
    ? `Реплика содержит ${spokenWords} слов и не помещается в лимит ${SEEDANCE_SPOKEN_WORD_LIMIT} слов для 8 секунд; выбран визуальный ролик без речи.`
    : suppliedReason || (
      recommendedMode === "real_seedance"
        ? "Короткая реплика помещается в 8 секунд."
        : "Сценарий безопасно собирается как короткий визуальный ролик без речи."
    );
  const recommendedAvailable = availability?.[recommendedMode] === true;
  if (recommendedAvailable) {
    return {
      value: recommendedMode,
      requestedMode,
      recommendedMode,
      source,
      reason,
      spokenWords,
      automatic: true,
      blocked: false,
    };
  }

  return {
    value: mockEnabled ? "mock" : recommendedMode,
    requestedMode,
    recommendedMode,
    source,
    reason,
    spokenWords,
    automatic: false,
    blocked: true,
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

export function resolveGenerationLearningFallback({
  currentMode = "",
  candidates = [],
  repairActive = false,
} = {}) {
  const normalizedCurrentMode = String(currentMode || "").trim();
  if (repairActive || !REAL_GENERATION_MODES.has(normalizedCurrentMode)) {
    return null;
  }
  const currentContentKind = GENERATION_MODE_CONTENT_KIND[
    normalizedCurrentMode
  ];
  const ranked = (Array.isArray(candidates) ? candidates : [])
    .map((candidate) => {
      const mode = String(candidate?.mode || "").trim();
      const estimatedMinor = Number(candidate?.estimatedMinor);
      if (
        !REAL_GENERATION_MODES.has(mode)
        || mode === normalizedCurrentMode
        || candidate?.available !== true
        || candidate?.generationAllowed !== true
        || !Number.isSafeInteger(estimatedMinor)
        || estimatedMinor < 0
      ) return null;
      return {
        mode,
        sameContentKind:
          GENERATION_MODE_CONTENT_KIND[mode] === currentContentKind,
        accepted: candidate?.accepted === true,
        estimatedMinor,
      };
    })
    .filter(Boolean)
    .sort((left, right) =>
      Number(right.sameContentKind) - Number(left.sameContentKind)
      || Number(right.accepted) - Number(left.accepted)
      || left.estimatedMinor - right.estimatedMinor
      || GENERATION_FALLBACK_PRIORITY[left.mode]
        - GENERATION_FALLBACK_PRIORITY[right.mode]
    );
  const selected = ranked[0];
  if (!selected) return null;
  return {
    mode: selected.mode,
    reasonCode: selected.sameContentKind
      ? "same_content_kind"
      : "safe_modality_fallback",
    accepted: selected.accepted,
    estimatedMinor: selected.estimatedMinor,
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
