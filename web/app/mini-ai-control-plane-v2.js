/* Canonical browser facade for the deterministic mini-AI engine. */

import {
  MINI_AI_RULEBOOK_RU,
  MINI_AI_RULES,
  MINI_AI_RULES_VERSION,
  buildMiniAiPlan as buildLegacyPlan,
  evaluateMiniAiPlan,
  miniAiEstimatedCostUsd,
  normalizeMiniAiContext,
} from "./mini-ai-control-plane-v1.js?v=20260801.1";

export {
  MINI_AI_RULEBOOK_RU,
  MINI_AI_RULES,
  MINI_AI_RULES_VERSION,
  evaluateMiniAiPlan,
  miniAiEstimatedCostUsd,
  normalizeMiniAiContext,
};

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    );
  }
  if (typeof value === "number" && !Number.isFinite(value)) return String(value);
  return value;
}

export function canonicalMiniAiHash(value) {
  const text = JSON.stringify(canonicalize(value));
  let first = 2166136261;
  let second = 2246822519;
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    first = Math.imul(first ^ code, 16777619);
    second = Math.imul(second ^ code, 3266489917);
  }
  return `${(first >>> 0).toString(16).padStart(8, "0")}${(second >>> 0).toString(16).padStart(8, "0")}`;
}

export function buildMiniAiPlan(rawContext) {
  const plan = buildLegacyPlan(rawContext);
  const identity = {
    version: plan.version,
    executable: plan.executable,
    context: plan.context,
    dimension: plan.dimension,
    batchSize: plan.batchSize,
    estimatedCostMinor: plan.estimatedCostMinor,
    arms: plan.arms,
    blockers: plan.blockers,
    reasonCodes: plan.reasonCodes,
  };
  return Object.freeze({
    ...plan,
    planId: `${plan.executable ? "mini-ai" : "blocked"}-${canonicalMiniAiHash(identity)}`,
    canonicalHash: canonicalMiniAiHash(identity),
  });
}
