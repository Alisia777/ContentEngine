const REAL_GENERATION_MODES = new Set([
  "real_photo",
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
const GENERATION_LEARNING_RETRY_DELAYS_MS = Object.freeze([
  1_000,
  3_000,
]);
const GENERATION_PREFLIGHT_TRANSIENT_ERROR_CODES = new Set([
  "ui_timeout",
  "generation_unavailable",
  "real_generation_request_failed",
  "real_generation_response_invalid",
  "provider_request_failed",
  "provider_response_invalid",
  "provider_preflight_invalid",
]);
const GENERATION_PREFLIGHT_RETRY_DELAYS_MS = Object.freeze([
  1_500,
  4_000,
]);
const SEEDANCE_SPOKEN_WORD_LIMIT = 22;
export const MAX_REAL_GENERATION_REFERENCES = 5;

export function chooseInitialGenerationMedia(items, {
  real = false,
  expectedSku = "",
  expectedProductName = "",
} = {}) {
  const exactSku = String(expectedSku || "").trim();
  const exactProductName = String(expectedProductName || "").trim();
  const expectedProductRequired = Boolean(exactSku || exactProductName);
  if (expectedProductRequired && !(exactSku && exactProductName)) return "";
  const candidates = (Array.isArray(items) ? items : [])
    .map((item) => ({
      id: String(item?.public_id || item?.id || "").trim(),
      sku: String(item?.sku || "").trim(),
      productName: String(item?.product_name || "").trim(),
      paidReady: item?.identity_verified === true
        && item?.rights_confirmed === true
        && Boolean(String(item?.sku || "").trim())
        && Boolean(String(item?.product_name || "").trim()),
    }))
    .filter((item) => (
      item.id
      && (!real || item.paidReady)
      && (!expectedProductRequired || (
        item.sku === exactSku && item.productName === exactProductName
      ))
    ));
  return candidates.length === 1 ? candidates[0].id : "";
}

export function resolveGenerationMediaSelection(items, {
  real = false,
  primaryMediaId = "",
  maxReferences = MAX_REAL_GENERATION_REFERENCES,
} = {}) {
  const selected = (Array.isArray(items) ? items : [])
    .filter((item) => item?.selected === true && item?.disabled !== true)
    .map((item) => ({
      id: String(item?.id || item?.public_id || "").trim(),
      productId: String(item?.productId || item?.product_id || "").trim().toLowerCase(),
      sku: String(item?.sku || "").trim(),
      productName: String(item?.productName || item?.product_name || "").trim(),
      paidReady: item?.paidReady === true || (
        item?.identity_verified === true
        && item?.rights_confirmed === true
      ),
    }))
    .filter((item) => item.id);
  const limit = Math.max(1, Math.min(
    MAX_REAL_GENERATION_REFERENCES,
    Number(maxReferences) || MAX_REAL_GENERATION_REFERENCES,
  ));
  if (!real) {
    const [first] = selected;
    const identityConsistent = Boolean(first) && !selected.some((item) => (
      item.sku !== first.sku
      || item.productName !== first.productName
      || (
        first.productId
        && item.productId
        && item.productId !== first.productId
      )
    ));
    return {
      valid: selected.length > 0,
      code: selected.length ? "" : "media_required",
      mediaIds: selected.map((item) => item.id),
      primaryMediaId: first?.id || "",
      identityConsistent,
      productId: identityConsistent
        && selected.every((item) => item.productId === first.productId)
        ? first.productId
        : "",
      sku: identityConsistent ? first.sku : "",
      productName: identityConsistent ? first.productName : "",
    };
  }
  if (!selected.length) {
    return {
      valid: false,
      code: "media_required",
      mediaIds: [],
      primaryMediaId: "",
      identityConsistent: false,
      productId: "",
      sku: "",
      productName: "",
    };
  }
  if (selected.length > limit) {
    return {
      valid: false,
      code: "too_many_references",
      mediaIds: selected.map((item) => item.id),
      primaryMediaId: "",
      identityConsistent: false,
      productId: "",
      sku: "",
      productName: "",
    };
  }
  if (selected.some((item) =>
    !item.paidReady || !item.sku || !item.productName
  )) {
    return {
      valid: false,
      code: "media_not_paid_ready",
      mediaIds: selected.map((item) => item.id),
      primaryMediaId: "",
      identityConsistent: false,
      productId: "",
      sku: "",
      productName: "",
    };
  }
  const [{ productId, sku, productName }] = selected;
  if (selected.some((item) =>
    item.sku !== sku
    || item.productName !== productName
    || (productId && item.productId && item.productId !== productId)
  )) {
    return {
      valid: false,
      code: "mixed_product_references",
      mediaIds: selected.map((item) => item.id),
      primaryMediaId: "",
      identityConsistent: false,
      productId: "",
      sku: "",
      productName: "",
    };
  }
  const requestedPrimary = String(primaryMediaId || "").trim();
  const primary = selected.find((item) => item.id === requestedPrimary)
    || selected[0];
  return {
    valid: true,
    code: "",
    mediaIds: [
      primary.id,
      ...selected.filter((item) => item.id !== primary.id)
        .map((item) => item.id),
    ],
    primaryMediaId: primary.id,
    identityConsistent: true,
    productId: selected.every((item) => item.productId === productId)
      ? productId
      : "",
    sku,
    productName,
  };
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
  const requestedMode = REAL_GENERATION_MODES.has(
      String(scenario.recommendedGenerationMode || ""),
    )
    ? String(scenario.recommendedGenerationMode)
    : "";
  const spokenWords = String(scenario.spokenScript || "")
    .match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu)?.length || 0;
  const seedanceSpeechFits = spokenWords > 0
    && spokenWords <= SEEDANCE_SPOKEN_WORD_LIMIT;
  const recommendedMode = requestedMode === "real_photo"
    ? "real_photo"
    : requestedMode === "real_gen4"
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
      recommendedMode === "real_photo"
        ? "Сценарий состоит из одного статичного товарного кадра без человека и речи."
        : recommendedMode === "real_seedance"
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

export function generationLearningRetryDelay(attempt) {
  const normalizedAttempt = Number(attempt);
  if (
    !Number.isSafeInteger(normalizedAttempt)
    || normalizedAttempt < 1
  ) return null;
  return GENERATION_LEARNING_RETRY_DELAYS_MS[
    normalizedAttempt - 1
  ] ?? null;
}

export function generationPreflightRetryDelay({
  attempt = 0,
  errorCode = "",
} = {}) {
  const normalizedAttempt = Number(attempt);
  const normalizedErrorCode = String(errorCode || "").trim();
  if (
    !Number.isSafeInteger(normalizedAttempt)
    || normalizedAttempt < 1
    || !GENERATION_PREFLIGHT_TRANSIENT_ERROR_CODES.has(
      normalizedErrorCode,
    )
  ) return null;
  return GENERATION_PREFLIGHT_RETRY_DELAYS_MS[
    normalizedAttempt - 1
  ] ?? null;
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
