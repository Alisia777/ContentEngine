/*
 * Pure, advisory model recommendation state for multi-model generation.
 *
 * Authority boundaries:
 * - The caller supplies the server-projected public catalog and cost/readiness
 *   signals. This module owns neither the catalog nor pricing.
 * - A recommendation is display advice. It cannot start generation, perform a
 *   paid action, or persist anything.
 * - Once a person chooses a model, only an explicit accept-recommendation
 *   action may replace that visible choice.
 */

export const GENERATION_MODEL_RECOMMENDATION_VERSION = "20260813.advisory.v1";

export const GENERATION_MODEL_RECOMMENDATION_ACTIONS = Object.freeze({
  RECOMMEND: "recommend",
  UPDATE_CONTEXT: "update-context",
  UPDATE_CATALOG: "update-catalog",
  SELECT_MANUAL: "select-manual",
  ACCEPT_RECOMMENDATION: "accept-recommendation",
  SET_VALIDATION: "set-validation",
});

const SCOPE_FIELDS = Object.freeze({
  contentKind: "content_kind_changed",
  inputMode: "input_changed",
  referenceImageCount: "input_changed",
  referenceVideo: "input_changed",
  firstFrame: "input_changed",
  lastFrame: "input_changed",
  durationSeconds: "duration_changed",
  ratio: "ratio_changed",
  resolution: "resolution_changed",
  audio: "audio_changed",
  spokenDialogue: "audio_changed",
});

const TERMINAL_UNREADY_STATUSES = new Set([
  "blocked",
  "disabled",
  "down",
  "not_ready",
  "offline",
  "unavailable",
]);

const ACCEPTED_STATUSES = new Set(["accepted", "approved", "verified"]);
const STALE_ACCEPTANCE_STATUSES = new Set([
  "needs_revalidation",
  "stale",
  "expired",
  "recheck",
]);

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stableClone(value) {
  if (Array.isArray(value)) {
    return value.map(stableClone);
  }
  if (!isRecord(value)) {
    return value;
  }
  const clone = {};
  Object.keys(value)
    .sort()
    .forEach((key) => {
      const entry = value[key];
      if (entry !== undefined && typeof entry !== "function") {
        clone[key] = stableClone(entry);
      }
    });
  return clone;
}

function deepFreeze(value, seen = new Set()) {
  if (!value || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  Object.getOwnPropertyNames(value).forEach((key) => deepFreeze(value[key], seen));
  return Object.freeze(value);
}

function stringValue(value) {
  if (typeof value !== "string") return "";
  return value.trim();
}

function token(value) {
  return stringValue(value).toLowerCase().replace(/[\s-]+/g, "_");
}

function finiteNumber(value) {
  const parsed = typeof value === "number"
    ? value
    : typeof value === "string" && value.trim()
      ? Number(value)
      : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function finiteInteger(value) {
  const parsed = finiteNumber(value);
  return parsed === null ? null : Math.floor(parsed);
}

function minorAmount(value) {
  const parsed = finiteNumber(value);
  return parsed === null ? null : Math.ceil(parsed);
}

function stableTextCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

function booleanOrNull(value) {
  return typeof value === "boolean" ? value : null;
}

function unique(values) {
  const result = [];
  const seen = new Set();
  values.forEach((value) => {
    const normalized = stringValue(value);
    if (normalized && !seen.has(normalized)) {
      seen.add(normalized);
      result.push(normalized);
    }
  });
  return result;
}

function tokenList(value) {
  const values = Array.isArray(value) ? value : value === undefined || value === null ? [] : [value];
  return unique(values.map(token).filter(Boolean));
}

function identityFrom(value) {
  if (!isRecord(value)) return null;
  const provider = stringValue(value.provider);
  const model = stringValue(value.model);
  if (!provider || !model) return null;
  const identity = { provider, model };
  const publicLabel = stringValue(value.publicLabel || value.label);
  if (publicLabel) identity.publicLabel = publicLabel;
  return identity;
}

function modelKey(value) {
  const identity = identityFrom(value);
  return identity ? `${identity.provider}:${identity.model}` : "";
}

function normalizeSignalMap(value) {
  const result = {};
  if (Array.isArray(value)) {
    value.forEach((entry) => {
      const key = modelKey(entry);
      if (key) result[key] = stableClone(entry);
    });
  } else if (isRecord(value)) {
    Object.keys(value)
      .sort()
      .forEach((key) => {
        result[key] = stableClone(value[key]);
      });
  }
  return result;
}

function normalizeIdentitySet(value) {
  const result = new Set();
  const entries = Array.isArray(value) ? value : value === undefined || value === null ? [] : [value];
  entries.forEach((entry) => {
    if (typeof entry === "string" && entry.includes(":")) {
      result.add(entry.trim());
      return;
    }
    const key = modelKey(entry);
    if (key) result.add(key);
  });
  return Array.from(result).sort();
}

function normalizeCatalog(snapshot) {
  const source = isRecord(snapshot) ? snapshot : {};
  const models = Array.isArray(source.models)
    ? source.models
        .filter((entry) => identityFrom(entry))
        .map((entry) => stableClone(entry))
        .sort((left, right) => stableTextCompare(modelKey(left), modelKey(right)))
    : [];
  return {
    version: stringValue(source.version) || null,
    models,
  };
}

function normalizeContext(context) {
  const source = isRecord(context) ? context : {};
  const input = isRecord(source.input) ? source.input : {};
  const explicitBudgetCandidates = [
    finiteInteger(source.budgetMinor),
    finiteInteger(source.requestBudgetMinor),
    finiteInteger(source.campaignRemainingBudgetMinor),
  ].filter((entry) => entry !== null);
  const budgetCandidates = explicitBudgetCandidates.length
    ? explicitBudgetCandidates
    : [finiteInteger(source.effectiveBudgetMinor)].filter((entry) => entry !== null);
  const inferredReferenceImageCount = Array.isArray(source.referenceImages)
    ? source.referenceImages.length
    : Array.isArray(input.referenceImages)
      ? input.referenceImages.length
      : null;

  return {
    contentKind: token(source.contentKind || source.kind) || null,
    intents: tokenList(source.intents || source.intent),
    inputMode: token(source.inputMode || input.mode || (typeof source.input === "string" ? source.input : "")) || null,
    durationSeconds: finiteNumber(source.durationSeconds ?? source.duration),
    ratio: stringValue(source.ratio || source.aspectRatio) || null,
    resolution: token(source.resolution) || null,
    audio: booleanOrNull(source.audio ?? source.generatedAudio),
    spokenDialogue: Boolean(source.spokenDialogue || source.dialogue),
    referenceImageCount:
      finiteInteger(source.referenceImageCount ?? source.referenceCount ?? input.referenceImageCount) ??
      inferredReferenceImageCount ??
      0,
    referenceVideo: Boolean(source.referenceVideo || input.referenceVideo),
    firstFrame: Boolean(source.firstFrame || input.firstFrame),
    lastFrame: Boolean(source.lastFrame || input.lastFrame),
    qualityPreference: token(source.qualityPreference || source.quality) || null,
    speedPreference: token(source.speedPreference || source.speed) || null,
    effectiveBudgetMinor: budgetCandidates.length ? Math.min(...budgetCandidates) : null,
    currency: stringValue(source.currency) || null,
    estimatedCosts: normalizeSignalMap(
      source.estimatedCosts || source.costEstimates || source.estimatedCostMinorByModel,
    ),
    readiness: normalizeSignalMap(source.readiness || source.modelReadiness),
    providerReadiness: normalizeSignalMap(source.providerReadiness),
    acceptance: normalizeSignalMap(source.acceptance || source.acceptedOutputs),
    researchRecommendations: normalizeIdentitySet(
      source.researchRecommendations || source.researchRecommendedModels || source.researchRecommendation,
    ),
    performanceRecommendations: normalizeIdentitySet(
      source.performanceRecommendations || source.performanceRecommendedModels || source.performanceRecommendation,
    ),
  };
}

function hasOwn(value, key) {
  return isRecord(value) && Object.prototype.hasOwnProperty.call(value, key);
}

function mergeContext(previous, patch) {
  const source = isRecord(patch) ? stableClone(patch) : {};
  const merged = { ...previous, ...source };

  // Alias updates must override the already-normalized canonical value.
  if (hasOwn(source, "intent") && !hasOwn(source, "intents")) merged.intents = source.intent;
  if (hasOwn(source, "kind") && !hasOwn(source, "contentKind")) merged.contentKind = source.kind;
  if (hasOwn(source, "duration") && !hasOwn(source, "durationSeconds")) {
    merged.durationSeconds = source.duration;
  }
  if (hasOwn(source, "aspectRatio") && !hasOwn(source, "ratio")) merged.ratio = source.aspectRatio;
  if (hasOwn(source, "generatedAudio") && !hasOwn(source, "audio")) merged.audio = source.generatedAudio;
  if (hasOwn(source, "dialogue") && !hasOwn(source, "spokenDialogue")) {
    merged.spokenDialogue = source.dialogue;
  }
  if (hasOwn(source, "referenceCount") && !hasOwn(source, "referenceImageCount")) {
    merged.referenceImageCount = source.referenceCount;
  }
  if (hasOwn(source, "quality") && !hasOwn(source, "qualityPreference")) {
    merged.qualityPreference = source.quality;
  }
  if (hasOwn(source, "speed") && !hasOwn(source, "speedPreference")) {
    merged.speedPreference = source.speed;
  }
  if (hasOwn(source, "costEstimates") && !hasOwn(source, "estimatedCosts")) {
    merged.estimatedCosts = source.costEstimates;
  }
  if (hasOwn(source, "modelReadiness") && !hasOwn(source, "readiness")) {
    merged.readiness = source.modelReadiness;
  }
  if (hasOwn(source, "acceptedOutputs") && !hasOwn(source, "acceptance")) {
    merged.acceptance = source.acceptedOutputs;
  }

  // An explicit budget patch replaces (and may clear) the previous effective cap.
  if (
    hasOwn(source, "budgetMinor") ||
    hasOwn(source, "requestBudgetMinor") ||
    hasOwn(source, "campaignRemainingBudgetMinor")
  ) {
    delete merged.effectiveBudgetMinor;
  }
  return normalizeContext(merged);
}

function normalizeValidation(value) {
  const source = isRecord(value) ? value : {};
  const normalizePart = (part) => {
    if (typeof part === "string") return { status: token(part) || "missing" };
    if (!isRecord(part)) return { status: "missing" };
    return {
      ...stableClone(part),
      status: token(part.status) || "missing",
    };
  };
  return {
    preflight: normalizePart(source.preflight),
    cost: normalizePart(source.cost),
    spec: normalizePart(source.spec),
    staleReasonCodes: unique(source.staleReasonCodes || []),
  };
}

function markValidationStale(validation, reasons) {
  const normalizedReasons = unique(reasons);
  if (!normalizedReasons.length) return normalizeValidation(validation);
  const previous = normalizeValidation(validation);
  const staleReasonCodes = unique([...previous.staleReasonCodes, ...normalizedReasons]);
  const stalePart = (part) => ({ ...part, status: "stale", staleReasonCodes });
  return {
    preflight: stalePart(previous.preflight),
    cost: stalePart(previous.cost),
    spec: stalePart(previous.spec),
    staleReasonCodes,
  };
}

function modelEnabled(model) {
  if (Object.prototype.hasOwnProperty.call(model, "enabled")) return model.enabled === true;
  return model.enabledByDefault === true;
}

function includesToken(list, requested) {
  if (!requested) return true;
  return tokenList(list).includes(token(requested));
}

function exactSignal(map, key) {
  return isRecord(map) && Object.prototype.hasOwnProperty.call(map, key) ? map[key] : undefined;
}

function readinessResult(signal, fallbackCode) {
  if (signal === undefined || signal === null) {
    return { ready: null, reasonCode: null, freshness: 0 };
  }
  if (signal === false) return { ready: false, reasonCode: fallbackCode, freshness: 0 };
  if (signal === true) return { ready: true, reasonCode: null, freshness: 1 };
  if (typeof signal === "string") {
    const status = token(signal);
    return {
      ready: !TERMINAL_UNREADY_STATUSES.has(status),
      reasonCode: TERMINAL_UNREADY_STATUSES.has(status) ? fallbackCode : null,
      freshness: status === "fresh" || status === "ready" ? 2 : 1,
    };
  }
  if (!isRecord(signal)) return { ready: null, reasonCode: null, freshness: 0 };
  const status = token(signal.status);
  const explicitlyUnready = signal.ready === false || signal.available === false || TERMINAL_UNREADY_STATUSES.has(status);
  const explicitlyReady = signal.ready === true || signal.available === true || status === "ready" || status === "fresh";
  return {
    ready: explicitlyUnready ? false : explicitlyReady ? true : null,
    reasonCode: explicitlyUnready ? stringValue(signal.reasonCode) || fallbackCode : null,
    freshness: token(signal.freshness) === "fresh" || status === "fresh" ? 2 : explicitlyReady ? 1 : 0,
  };
}

function costResult(signal, model) {
  if (typeof signal === "number" || typeof signal === "string") {
    return {
      estimatedCostMinor: minorAmount(signal),
      pricingVersion: stringValue(model.pricingVersion) || null,
    };
  }
  if (!isRecord(signal)) {
    return {
      estimatedCostMinor: null,
      pricingVersion: stringValue(model.pricingVersion) || null,
    };
  }
  return {
    estimatedCostMinor: minorAmount(signal.estimatedCostMinor ?? signal.costMinor ?? signal.amountMinor),
    pricingVersion: stringValue(signal.pricingVersion || model.pricingVersion) || null,
  };
}

function acceptanceResult(signal) {
  if (signal === true) return { rank: 2, status: "accepted", warningCode: null };
  if (signal === false || signal === undefined || signal === null) {
    return { rank: 0, status: "unproven", warningCode: "model_unproven" };
  }
  const status = token(isRecord(signal) ? signal.status : signal);
  const compatible = !isRecord(signal) || signal.compatible !== false;
  if (ACCEPTED_STATUSES.has(status) && compatible) {
    return { rank: 2, status: "accepted", warningCode: null };
  }
  if (STALE_ACCEPTANCE_STATUSES.has(status)) {
    return { rank: 1, status: "stale", warningCode: "acceptance_stale" };
  }
  return {
    rank: 0,
    status: "unproven",
    warningCode: compatible ? "model_unproven" : "accepted_output_not_compatible",
  };
}

function qualityMatch(model, preference) {
  if (!preference || preference === "any") return 0;
  return token(model.qualityTier) === preference ? 1 : 0;
}

function speedMatch(model, preference) {
  if (!preference || preference === "any") return 0;
  return token(model.speedTier) === preference ? 1 : 0;
}

function intentResult(model, context) {
  const reasons = [];
  let score = 0;
  let productFidelity = 0;
  const quality = token(model.qualityTier);
  const speed = token(model.speedTier);
  const inputs = tokenList(model.inputModes);
  const declaredBestFor = tokenList(model.bestFor);
  const declaredAvoidFor = tokenList(model.avoidFor);

  context.intents.forEach((intent) => {
    if (declaredBestFor.includes(intent)) {
      score += 3;
      reasons.push("intent_declared_best_for");
    }
    if (declaredAvoidFor.includes(intent)) {
      score -= 2;
      reasons.push("intent_declared_avoid");
    }
    if (["draft", "fast_draft", "exploration", "variant"].includes(intent) && speed === "fast") {
      score += 2;
      reasons.push("intent_fast_draft_fit");
    }
    if (["low_budget", "economy"].includes(intent) && quality === "economy") {
      score += 2;
      reasons.push("intent_economy_fit");
    }
    if (["premium_visual", "hero_visual", "final_quality"].includes(intent) && quality === "premium") {
      score += 3;
      productFidelity += 1;
      reasons.push("intent_premium_quality_fit");
    }
    if (["ugc", "ugc_video", "creator", "presenter", "dialogue"].includes(intent)) {
      if (model.supportsGeneratedAudio === true) {
        score += 1;
        reasons.push("intent_audio_fit");
      }
      if (model.supportsSpokenDialogue === true) {
        score += 2;
        reasons.push("intent_dialogue_fit");
      }
    }
    if (["source_video_variation", "video_to_video"].includes(intent)) {
      if (inputs.includes("video") || model.supportsReferenceVideo === true) {
        score += 3;
        reasons.push("intent_source_video_fit");
      }
    }
    if (["product_motion", "product_demo", "product_image"].includes(intent)) {
      if (inputs.includes("image") || model.supportsReferenceImages === true) {
        score += 2;
        productFidelity += 1;
        reasons.push("intent_product_reference_fit");
      }
    }
  });

  if (context.referenceImageCount > 0 && model.supportsReferenceImages === true) productFidelity += 1;
  if (context.referenceVideo && model.supportsReferenceVideo === true) productFidelity += 1;
  if (context.firstFrame && model.supportsFirstFrame === true) productFidelity += 1;
  if (context.lastFrame && model.supportsLastFrame === true) productFidelity += 1;

  return { score, productFidelity, reasonCodes: unique(reasons) };
}

function evaluateModel(model, context) {
  const key = modelKey(model);
  const unavailableReasonCodes = [];
  const reasonCodes = [];
  const warningCodes = [];

  if (!modelEnabled(model)) {
    unavailableReasonCodes.push(stringValue(model.disabledReasonCode) || "model_disabled");
  }
  if (context.contentKind && token(model.contentKind) !== context.contentKind) {
    unavailableReasonCodes.push("content_kind_unsupported");
  } else if (context.contentKind) {
    reasonCodes.push("content_kind_match");
  }
  if (context.inputMode && !includesToken(model.inputModes, context.inputMode)) {
    unavailableReasonCodes.push("input_mode_unsupported");
  } else if (context.inputMode) {
    reasonCodes.push("input_mode_match");
  }

  if (context.durationSeconds !== null) {
    const allowedDurations = (Array.isArray(model.allowedDurations) ? model.allowedDurations : [])
      .map(finiteNumber)
      .filter((entry) => entry !== null);
    const minimum = finiteNumber(model.minDurationSeconds);
    const maximum = finiteNumber(model.maxDurationSeconds);
    const allowed = allowedDurations.length
      ? allowedDurations.includes(context.durationSeconds)
      : (minimum === null || context.durationSeconds >= minimum) &&
        (maximum === null || context.durationSeconds <= maximum);
    if (!allowed) unavailableReasonCodes.push("duration_unsupported");
    else reasonCodes.push("duration_supported");
  }

  if (context.ratio) {
    if (!includesToken(model.allowedRatios || model.ratios, context.ratio)) {
      unavailableReasonCodes.push("ratio_unsupported");
    }
    else reasonCodes.push("ratio_supported");
  }
  if (context.resolution) {
    if (!includesToken(model.allowedResolutions || model.resolutions, context.resolution)) {
      unavailableReasonCodes.push("resolution_unsupported");
    }
    else reasonCodes.push("resolution_supported");
  }
  if (context.audio === true && model.supportsGeneratedAudio !== true) {
    unavailableReasonCodes.push("audio_unsupported");
  } else if (context.audio === true) {
    reasonCodes.push("audio_supported");
  }
  if (context.spokenDialogue && model.supportsSpokenDialogue !== true) {
    unavailableReasonCodes.push("spoken_dialogue_unsupported");
  } else if (context.spokenDialogue) {
    reasonCodes.push("spoken_dialogue_supported");
  }
  if (context.referenceImageCount > 0) {
    if (model.supportsReferenceImages !== true) {
      unavailableReasonCodes.push("reference_images_unsupported");
    } else {
      const maximumImages = finiteInteger(model.maxReferenceImages);
      if (maximumImages !== null && context.referenceImageCount > maximumImages) {
        unavailableReasonCodes.push("reference_image_count_unsupported");
      } else {
        reasonCodes.push("reference_images_supported");
      }
    }
  }
  if (context.referenceVideo) {
    if (model.supportsReferenceVideo !== true) unavailableReasonCodes.push("reference_video_unsupported");
    else reasonCodes.push("reference_video_supported");
  }
  if (context.firstFrame) {
    if (model.supportsFirstFrame !== true) unavailableReasonCodes.push("first_frame_unsupported");
    else reasonCodes.push("first_frame_supported");
  }
  if (context.lastFrame) {
    if (model.supportsLastFrame !== true) unavailableReasonCodes.push("last_frame_unsupported");
    else reasonCodes.push("last_frame_supported");
  }

  const providerReadiness = readinessResult(
    exactSignal(context.providerReadiness, stringValue(model.provider)),
    "provider_not_ready",
  );
  const modelReadiness = readinessResult(exactSignal(context.readiness, key), "model_not_ready");
  if (providerReadiness.ready === false) unavailableReasonCodes.push(providerReadiness.reasonCode);
  if (modelReadiness.ready === false) unavailableReasonCodes.push(modelReadiness.reasonCode);
  if (providerReadiness.ready === null || modelReadiness.ready === null) {
    warningCodes.push("readiness_unknown");
  } else {
    reasonCodes.push("provider_model_ready");
  }

  const cost = costResult(exactSignal(context.estimatedCosts, key), model);
  if (context.effectiveBudgetMinor !== null) {
    if (cost.estimatedCostMinor === null) {
      unavailableReasonCodes.push("cost_estimate_required");
    } else if (cost.estimatedCostMinor > context.effectiveBudgetMinor) {
      unavailableReasonCodes.push("budget_exceeded");
    } else {
      reasonCodes.push("within_budget");
    }
  } else if (cost.estimatedCostMinor === null) {
    warningCodes.push("cost_estimate_unavailable");
  }

  const acceptance = acceptanceResult(exactSignal(context.acceptance, key));
  if (acceptance.warningCode) warningCodes.push(acceptance.warningCode);
  else reasonCodes.push("accepted_output_evidence");

  const lifecycle = token(model.lifecycle);
  if (lifecycle === "experimental") warningCodes.push("experimental_model");
  if (lifecycle === "preview" || lifecycle === "beta") warningCodes.push("preview_model");

  const researchRank = context.researchRecommendations.includes(key) ? 1 : 0;
  const performanceRank = context.performanceRecommendations.includes(key) ? 1 : 0;
  if (researchRank) reasonCodes.push("research_recommendation_match");
  if (performanceRank) reasonCodes.push("performance_recommendation_match");

  const intent = intentResult(model, context);
  reasonCodes.push(...intent.reasonCodes);
  const qualityPreferenceMatch = qualityMatch(model, context.qualityPreference);
  const speedPreferenceMatch = speedMatch(model, context.speedPreference);
  if (qualityPreferenceMatch) reasonCodes.push("quality_preference_match");
  if (speedPreferenceMatch) reasonCodes.push("speed_preference_match");

  return {
    model,
    key,
    available: unique(unavailableReasonCodes).length === 0,
    unavailableReasonCodes: unique(unavailableReasonCodes),
    reasonCodes: unique(reasonCodes),
    warningCodes: unique(warningCodes),
    estimatedCostMinor: cost.estimatedCostMinor,
    pricingVersion: cost.pricingVersion,
    rank: {
      acceptance: acceptance.rank,
      productFidelity: intent.productFidelity,
      research: researchRank,
      performance: performanceRank,
      intent: intent.score,
      speed: speedPreferenceMatch,
      quality: qualityPreferenceMatch,
      readiness: providerReadiness.freshness + modelReadiness.freshness,
      lifecycle: lifecycle === "production" || lifecycle === "stable" ? 2 : lifecycle === "preview" ? 1 : 0,
    },
  };
}

function compareCandidates(left, right) {
  const rankKeys = [
    "acceptance",
    "productFidelity",
    "research",
    "performance",
    "intent",
  ];
  for (const key of rankKeys) {
    if (left.rank[key] !== right.rank[key]) return right.rank[key] - left.rank[key];
  }
  const leftCost = left.estimatedCostMinor === null ? Number.POSITIVE_INFINITY : left.estimatedCostMinor;
  const rightCost = right.estimatedCostMinor === null ? Number.POSITIVE_INFINITY : right.estimatedCostMinor;
  if (leftCost !== rightCost) return leftCost - rightCost;
  for (const key of ["speed", "quality", "readiness", "lifecycle"]) {
    if (left.rank[key] !== right.rank[key]) return right.rank[key] - left.rank[key];
  }
  return stableTextCompare(left.key, right.key);
}

function scoreBand(candidate) {
  if (
    candidate.warningCodes.includes("experimental_model") ||
    candidate.warningCodes.includes("model_unproven") ||
    candidate.warningCodes.includes("accepted_output_not_compatible")
  ) {
    return "experimental";
  }
  if (
    candidate.rank.acceptance === 2 &&
    (candidate.rank.intent > 0 || candidate.rank.research > 0 || candidate.rank.performance > 0)
  ) {
    return "strong";
  }
  if (candidate.reasonCodes.length) return "fit";
  return "fallback";
}

function publicCandidate(candidate) {
  const identity = identityFrom(candidate.model);
  return {
    ...identity,
    scoreBand: scoreBand(candidate),
    reasonCodes: [...candidate.reasonCodes],
    warningCodes: [...candidate.warningCodes],
    estimatedCostMinor: candidate.estimatedCostMinor,
    pricingVersion: candidate.pricingVersion,
  };
}

function publicUnavailable(candidate) {
  const identity = identityFrom(candidate.model);
  return {
    ...identity,
    unavailableReasonCodes: [...candidate.unavailableReasonCodes],
    warningCodes: [...candidate.warningCodes],
    estimatedCostMinor: candidate.estimatedCostMinor,
    pricingVersion: candidate.pricingVersion,
  };
}

export function recommendGenerationModels(catalogSnapshot, rawContext = {}) {
  const catalog = normalizeCatalog(catalogSnapshot);
  const context = normalizeContext(rawContext);
  const evaluated = catalog.models.map((model) => evaluateModel(model, context));
  const available = evaluated.filter((candidate) => candidate.available).sort(compareCandidates);
  const unavailable = evaluated
    .filter((candidate) => !candidate.available)
    .sort((left, right) => stableTextCompare(left.key, right.key));
  const recommended = available.length ? publicCandidate(available[0]) : null;
  const result = {
    catalogVersion: catalog.version,
    pricingVersion: recommended?.pricingVersion || null,
    recommended,
    alternatives: available.slice(1).map(publicCandidate),
    unavailable: unavailable.map(publicUnavailable),
    reasonCodes: recommended ? [...recommended.reasonCodes] : [],
    warningCodes: recommended ? [...recommended.warningCodes] : ["no_compatible_model"],
  };
  return deepFreeze(result);
}

function selectionFromRecommendation(recommendation) {
  return recommendation?.recommended ? identityFrom(recommendation.recommended) : null;
}

function selectionStatus(selection, catalog, context) {
  if (!selection) {
    return {
      blocked: true,
      reasonCodes: ["selection_required"],
      unavailableReasonCodes: ["selection_required"],
      explanationCodes: ["selection_required"],
      warningCodes: [],
      estimatedCostMinor: null,
      pricingVersion: null,
    };
  }
  const key = modelKey(selection);
  const model = catalog.models.find((entry) => modelKey(entry) === key);
  if (!model) {
    return {
      blocked: true,
      reasonCodes: ["model_not_in_catalog"],
      unavailableReasonCodes: ["model_not_in_catalog"],
      explanationCodes: ["model_not_in_catalog"],
      warningCodes: [],
      estimatedCostMinor: null,
      pricingVersion: null,
    };
  }
  const candidate = evaluateModel(model, context);
  const unavailableReasonCodes = candidate.available ? [] : [...candidate.unavailableReasonCodes];
  return {
    blocked: !candidate.available,
    reasonCodes: candidate.available ? [...candidate.reasonCodes] : unavailableReasonCodes,
    unavailableReasonCodes,
    explanationCodes: candidate.available ? [...candidate.warningCodes] : unavailableReasonCodes,
    warningCodes: [...candidate.warningCodes],
    estimatedCostMinor: candidate.estimatedCostMinor,
    pricingVersion: candidate.pricingVersion,
  };
}

function composeState({ catalog, context, recommendation, selection, selectionSource, manualLock, validation }) {
  const selected = selection ? stableClone(selection) : null;
  const state = {
    version: GENERATION_MODEL_RECOMMENDATION_VERSION,
    catalog,
    context,
    recommendation,
    selection: selected,
    selectionSource: selected ? selectionSource || "system_recommendation" : null,
    manualLock: Boolean(manualLock),
    selectionStatus: selectionStatus(selected, catalog, context),
    validation: normalizeValidation(validation),
  };
  return deepFreeze(state);
}

export function createGenerationModelRecommendationState(options = {}) {
  const source = isRecord(options) ? options : {};
  const catalog = normalizeCatalog(source.catalogSnapshot || source.catalog);
  const context = normalizeContext(source.context);
  const recommendation = recommendGenerationModels(catalog, context);
  const requestedSelection = identityFrom(source.selection);
  const manualLock = Boolean(source.manualLock && requestedSelection);
  const selection = requestedSelection || selectionFromRecommendation(recommendation);
  return composeState({
    catalog,
    context,
    recommendation,
    selection,
    selectionSource: requestedSelection ? stringValue(source.selectionSource) || "manual" : "system_recommendation",
    manualLock,
    validation: source.validation,
  });
}

function contextChangeReasons(previous, next) {
  const reasons = [];
  Object.entries(SCOPE_FIELDS).forEach(([field, reasonCode]) => {
    if (JSON.stringify(previous[field]) !== JSON.stringify(next[field])) reasons.push(reasonCode);
  });
  return unique(reasons);
}

function selectionChangeReasons(previous, next) {
  const reasons = [];
  if ((previous?.provider || null) !== (next?.provider || null)) reasons.push("provider_changed");
  if ((previous?.model || null) !== (next?.model || null)) reasons.push("model_changed");
  return reasons;
}

function catalogChanged(previous, next) {
  return JSON.stringify(previous) !== JSON.stringify(next);
}

function recompute(previous, { catalog, context, selection, selectionSource, manualLock, validation }) {
  const recommendation = recommendGenerationModels(catalog, context);
  const locked = previous.manualLock || Boolean(manualLock);
  const nextSelection = locked ? selection : selectionFromRecommendation(recommendation);
  const nextValidation = markValidationStale(
    validation,
    selectionChangeReasons(previous.selection, nextSelection),
  );
  return composeState({
    catalog,
    context,
    recommendation,
    selection: nextSelection,
    selectionSource: locked ? selectionSource : nextSelection ? "system_recommendation" : null,
    manualLock: locked,
    validation: nextValidation,
  });
}

export function generationModelRecommendationReducer(state, action = {}) {
  const previous = state?.version === GENERATION_MODEL_RECOMMENDATION_VERSION
    ? state
    : createGenerationModelRecommendationState();
  if (!isRecord(action)) return previous;

  switch (action.type) {
    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.RECOMMEND: {
      const suppliedCatalog = action.catalogSnapshot || action.catalog;
      const catalog = suppliedCatalog ? normalizeCatalog(suppliedCatalog) : previous.catalog;
      const suppliedContext = isRecord(action.context) ? normalizeContext(action.context) : null;
      const context = suppliedContext || (action.contextPatch
        ? mergeContext(previous.context, action.contextPatch)
        : previous.context);
      let validation = previous.validation;
      const reasons = contextChangeReasons(previous.context, context);
      if (suppliedCatalog && catalogChanged(previous.catalog, catalog)) reasons.push("catalog_changed");
      validation = markValidationStale(validation, reasons);
      return recompute(previous, {
        catalog,
        context,
        selection: previous.selection,
        selectionSource: previous.selectionSource,
        manualLock: previous.manualLock,
        validation,
      });
    }

    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.UPDATE_CONTEXT: {
      const patch = isRecord(action.patch)
        ? action.patch
        : isRecord(action.contextPatch)
          ? action.contextPatch
          : isRecord(action.context)
            ? action.context
            : {};
      const context = mergeContext(previous.context, patch);
      const validation = markValidationStale(
        previous.validation,
        contextChangeReasons(previous.context, context),
      );
      return recompute(previous, {
        catalog: previous.catalog,
        context,
        selection: previous.selection,
        selectionSource: previous.selectionSource,
        manualLock: previous.manualLock,
        validation,
      });
    }

    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.UPDATE_CATALOG: {
      const catalog = normalizeCatalog(action.catalogSnapshot || action.catalog);
      const validation = catalogChanged(previous.catalog, catalog)
        ? markValidationStale(previous.validation, ["catalog_changed"])
        : previous.validation;
      return recompute(previous, {
        catalog,
        context: previous.context,
        selection: previous.selection,
        selectionSource: previous.selectionSource,
        manualLock: previous.manualLock,
        validation,
      });
    }

    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.SELECT_MANUAL: {
      const manualSelection = identityFrom(action.selection || action);
      if (!manualSelection) return previous;
      const validation = markValidationStale(
        previous.validation,
        selectionChangeReasons(previous.selection, manualSelection),
      );
      return composeState({
        catalog: previous.catalog,
        context: previous.context,
        recommendation: previous.recommendation,
        selection: manualSelection,
        selectionSource: "manual",
        manualLock: true,
        validation,
      });
    }

    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.ACCEPT_RECOMMENDATION: {
      const accepted = selectionFromRecommendation(previous.recommendation);
      if (!accepted) return previous;
      const validation = markValidationStale(
        previous.validation,
        selectionChangeReasons(previous.selection, accepted),
      );
      return composeState({
        catalog: previous.catalog,
        context: previous.context,
        recommendation: previous.recommendation,
        selection: accepted,
        selectionSource: "accepted_recommendation",
        manualLock: true,
        validation,
      });
    }

    case GENERATION_MODEL_RECOMMENDATION_ACTIONS.SET_VALIDATION:
      return composeState({
        catalog: previous.catalog,
        context: previous.context,
        recommendation: previous.recommendation,
        selection: previous.selection,
        selectionSource: previous.selectionSource,
        manualLock: previous.manualLock,
        validation: action.validation,
      });

    default:
      return previous;
  }
}

export default Object.freeze({
  version: GENERATION_MODEL_RECOMMENDATION_VERSION,
  actions: GENERATION_MODEL_RECOMMENDATION_ACTIONS,
  recommend: recommendGenerationModels,
  createState: createGenerationModelRecommendationState,
  reducer: generationModelRecommendationReducer,
});
