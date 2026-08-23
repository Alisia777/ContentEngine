/*
 * ContentEngine · local presentation registry for the generation model catalog.
 *
 * Provider/model identities come from the signed server catalog.  This module
 * deliberately owns presentation only: no capability, price, availability or
 * launch decision is inferred from an image.
 */

const FAMILY_ASSETS = Object.freeze({
  seedream: new URL(
    "./assets/content-factory-model-family-seedream-v1.png",
    import.meta.url,
  ).href,
  gen4: new URL(
    "./assets/content-factory-model-family-gen4-v1.png",
    import.meta.url,
  ).href,
  seedance: new URL(
    "./assets/content-factory-model-family-seedance-v1.png",
    import.meta.url,
  ).href,
  veo: new URL(
    "./assets/content-factory-model-family-veo-v1.png",
    import.meta.url,
  ).href,
  omni: new URL(
    "./assets/content-factory-model-family-omni-v1.png",
    import.meta.url,
  ).href,
});

const MODEL_VISUALS = Object.freeze({
  "runway:seedream5_lite": Object.freeze({
    family: "seedream", tone: "amber", focal: "50% 55%",
  }),
  "runway:gen4_turbo": Object.freeze({
    family: "gen4", tone: "blue", focal: "40% 48%",
  }),
  "runway:seedance2_fast": Object.freeze({
    family: "seedance", tone: "teal", focal: "66% 48%",
  }),
  "runway:gen4.5": Object.freeze({
    family: "gen4", tone: "violet", focal: "58% 48%",
  }),
  "runway:seedance2_mini": Object.freeze({
    family: "seedance", tone: "coral", focal: "30% 48%",
  }),
  "runway:veo3.1_fast": Object.freeze({
    family: "veo", tone: "gold", focal: "65% 50%",
  }),
  "runway:gemini_omni_flash": Object.freeze({
    family: "omni", tone: "cyan", focal: "52% 48%",
  }),
  "runway:veo3.1": Object.freeze({
    family: "veo", tone: "indigo", focal: "30% 50%",
  }),
  "runway:seedance2": Object.freeze({
    family: "seedance", tone: "violet", focal: "52% 48%",
  }),
  "google:veo-3.1-lite-generate-preview": Object.freeze({
    family: "veo", tone: "emerald", focal: "78% 50%",
  }),
});

function exactModelKey(provider, model) {
  return `${String(provider || "").trim().toLowerCase()}:${String(model || "").trim().toLowerCase()}`;
}

export function resolveGenerationModelVisual(provider, model) {
  const key = exactModelKey(provider, model);
  const visual = MODEL_VISUALS[key];
  if (!visual) return null;
  return Object.freeze({
    key,
    family: visual.family,
    tone: visual.tone,
    focal: visual.focal,
    src: FAMILY_ASSETS[visual.family],
  });
}

export const GENERATION_MODEL_VISUAL_IDENTITIES = Object.freeze(
  Object.keys(MODEL_VISUALS),
);
