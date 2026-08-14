/*
 * Pure generation-provider request adapters.
 *
 * This module deliberately stops at a JSON request envelope. It never reads
 * secrets, performs I/O, dispatches a paid request, polls a task or persists
 * provider data. The caller must supply the canonical catalog entry, the
 * exact successful selection returned by validateGenerationModelSelection(),
 * and already-authorized media inputs.
 *
 * Provider sources checked for this contract (2026-08-13):
 * - Runway OpenAPI: https://docs.dev.runwayml.com/openapi.json
 * - Runway API reference: https://docs.dev.runwayml.com/api/
 * - Runway media inputs: https://docs.dev.runwayml.com/assets/inputs/
 * - Google Veo REST guide: https://ai.google.dev/gemini-api/docs/veo
 * - Google predictLongRunning: https://ai.google.dev/api/models#method:-models.predictlongrunning
 */

import {
  GENERATION_MODEL_CATALOG_VERSION,
  generationModelCatalogEntry,
} from "./generation-model-catalog.js";

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

const KNOWN_INPUT_KEYS = new Set([
  "promptText",
  "firstFrameUrl",
  "lastFrameUrl",
  "referenceImageUrls",
  "inputVideoUrl",
  "referenceVideoUrls",
  "inputVideoDurationSeconds",
  "inputVideoRatio",
  "imageInlineData",
  "lastFrameInlineData",
]);

const RUNWAY_ENDPOINTS = new Set([
  "/v1/text_to_image",
  "/v1/text_to_video",
  "/v1/image_to_video",
  "/v1/video_to_video",
]);
const SEEDANCE_MODELS = new Set([
  "seedance2",
  "seedance2_fast",
  "seedance2_mini",
]);
const PRODUCT_REFERENCE_TAG = "ProductReference";
const RUNWAY_VEO_MODELS = new Set(["veo3.1", "veo3.1_fast"]);
const GOOGLE_IMAGE_MIME_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);
const MAX_HTTPS_URL_LENGTH = 2_048;
const MAX_GOOGLE_INLINE_IMAGE_BYTES = 20 * 1024 * 1024;

export const GENERATION_PROVIDER_POLL_KINDS = Object.freeze({
  runway: "runway_task",
  google: "google_long_running_operation",
});

export class GenerationProviderAdapterError extends Error {
  constructor(code) {
    super(`generation_provider_adapter:${code}`);
    this.name = "GenerationProviderAdapterError";
    this.code = code;
  }
}

function fail(code) {
  throw new GenerationProviderAdapterError(code);
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function assertExactOwnKeys(value, allowedKeys, code) {
  const keys = Object.keys(value);
  if (keys.length !== allowedKeys.length) fail(code);
  const allowed = new Set(allowedKeys);
  if (keys.some((key) => !allowed.has(key))) fail(code);
}

function assertAllowedInputKeys(input, allowedKeys) {
  const allowed = new Set(allowedKeys);
  for (const key of Object.keys(input)) {
    if (!KNOWN_INPUT_KEYS.has(key)) fail("input_field_unknown");
    if (!allowed.has(key)) fail("input_field_incompatible");
  }
}

function assertCanonicalSelection(entry, selection) {
  if (!isPlainObject(entry)) fail("catalog_entry_invalid");
  const canonical = generationModelCatalogEntry(entry.provider, entry.model);
  if (canonical !== entry) fail("catalog_entry_not_canonical");
  if (!isPlainObject(selection)) fail("selection_invalid");
  assertExactOwnKeys(selection, EXACT_SELECTION_KEYS, "selection_not_exact");
  if (
    selection.ok !== true ||
    selection.provider !== entry.provider ||
    selection.model !== entry.model ||
    selection.catalogVersion !== GENERATION_MODEL_CATALOG_VERSION ||
    selection.pricingVersion !== entry.pricingVersion
  ) fail("selection_binding_invalid");

  const contract = entry.server?.inputContracts?.[selection.inputMode];
  if (!contract || !entry.inputModes.includes(selection.inputMode)) {
    fail("selection_input_mode_invalid");
  }
  if (
    !Number.isInteger(selection.durationSeconds) ||
    !entry.allowedDurations.includes(selection.durationSeconds)
  ) fail("selection_duration_invalid");
  if (!contract.allowedRatios.includes(selection.ratio)) {
    fail("selection_ratio_invalid");
  }
  if (!contract.allowedResolutions.includes(selection.resolution)) {
    fail("selection_resolution_invalid");
  }
  const durationsForResolution = contract.allowedDurationsByResolution?.[selection.resolution];
  if (
    Array.isArray(durationsForResolution) &&
    durationsForResolution.length > 0 &&
    !durationsForResolution.includes(selection.durationSeconds)
  ) fail("selection_resolution_duration_invalid");

  for (const key of [
    "audio",
    "spokenDialogue",
    "referenceVideo",
    "firstFrame",
    "lastFrame",
  ]) {
    if (typeof selection[key] !== "boolean") fail("selection_boolean_invalid");
  }
  if (selection.audio && !entry.supportsGeneratedAudio) fail("selection_audio_invalid");
  if (selection.spokenDialogue && !entry.supportsSpokenDialogue) {
    fail("selection_dialogue_invalid");
  }
  if (selection.spokenDialogue && !selection.audio) {
    fail("spoken_dialogue_requires_audio");
  }
  if (
    !Number.isInteger(selection.referenceImageCount) ||
    selection.referenceImageCount < 0 ||
    selection.referenceImageCount > Number(contract.maxReferenceImages || 0) ||
    (selection.referenceImageCount > 0 && !entry.supportsReferenceImages)
  ) fail("selection_reference_images_invalid");
  if (
    selection.referenceVideo &&
    (!entry.supportsReferenceVideo || contract.supportsReferenceVideo !== true)
  ) fail("selection_reference_video_invalid");
  if (
    selection.firstFrame &&
    (!entry.supportsFirstFrame || contract.supportsFirstFrame !== true)
  ) fail("selection_first_frame_invalid");
  if (
    selection.lastFrame &&
    (!entry.supportsLastFrame || contract.supportsLastFrame !== true)
  ) fail("selection_last_frame_invalid");

  const providerRatio = entry.server?.providerRatios?.[selection.resolution]?.[selection.ratio];
  if (typeof providerRatio !== "string" || !providerRatio) {
    fail("provider_ratio_missing");
  }
  return { contract, providerRatio };
}

function exactPrompt(input, entry) {
  const value = input.promptText;
  if (typeof value !== "string" || !value.trim() || value.includes("\u0000")) {
    fail("prompt_invalid");
  }
  // Runway specifies prompt bounds in UTF-16 code units. The catalog carries
  // the provider bound, so JavaScript string length is the exact comparison.
  if (value.length > entry.promptLimit) fail("prompt_too_long");
  return value;
}

function exactHttpsUrl(value, invalidCode) {
  if (
    typeof value !== "string" ||
    value !== value.trim() ||
    value.length < 13 ||
    value.length > MAX_HTTPS_URL_LENGTH ||
    !value.startsWith("https://") ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) fail(invalidCode);
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(invalidCode);
  }
  if (
    parsed.protocol !== "https:" ||
    !parsed.hostname ||
    parsed.username ||
    parsed.password ||
    parsed.hash
  ) fail(invalidCode);
  return value;
}

function exactUrlArray(input, key, expectedCount, invalidCode) {
  if (expectedCount === 0) {
    if (hasOwn(input, key)) fail("input_field_incompatible");
    return [];
  }
  const value = input[key];
  if (!Array.isArray(value) || value.length !== expectedCount) fail(invalidCode);
  return value.map((url) => exactHttpsUrl(url, invalidCode));
}

function optionalReferenceVideos(input, selection, maxCount) {
  if (!selection.referenceVideo) {
    if (hasOwn(input, "referenceVideoUrls")) fail("input_field_incompatible");
    return [];
  }
  const value = input.referenceVideoUrls;
  if (
    !Array.isArray(value) ||
    value.length < 1 ||
    value.length > maxCount
  ) fail("reference_video_urls_invalid");
  return value.map((url) => exactHttpsUrl(url, "reference_video_urls_invalid"));
}

function exactFrameUrl(input, key, selected, invalidCode) {
  if (!selected) {
    if (hasOwn(input, key)) fail("input_field_incompatible");
    return null;
  }
  if (!hasOwn(input, key)) fail(invalidCode);
  return exactHttpsUrl(input[key], invalidCode);
}

function exactInlineImage(value, invalidCode) {
  if (!isPlainObject(value)) fail(invalidCode);
  assertExactOwnKeys(value, ["mimeType", "data"], invalidCode);
  if (!GOOGLE_IMAGE_MIME_TYPES.has(value.mimeType)) fail(invalidCode);
  const data = value.data;
  if (
    typeof data !== "string" ||
    data.length < 4 ||
    data.length % 4 !== 0 ||
    !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/u.test(data)
  ) fail(invalidCode);
  const padding = data.endsWith("==") ? 2 : data.endsWith("=") ? 1 : 0;
  const decodedBytes = data.length / 4 * 3 - padding;
  if (decodedBytes < 1 || decodedBytes > MAX_GOOGLE_INLINE_IMAGE_BYTES) {
    fail(invalidCode);
  }
  return { mimeType: value.mimeType, data };
}

function exactInlineFrame(input, key, selected, invalidCode) {
  if (!selected) {
    if (hasOwn(input, key)) fail("input_field_incompatible");
    return null;
  }
  if (!hasOwn(input, key)) fail(invalidCode);
  return exactInlineImage(input[key], invalidCode);
}

function assertRunwayEndpoint(entry, selection) {
  const endpointPath = entry.server?.endpoints?.[selection.inputMode];
  if (!RUNWAY_ENDPOINTS.has(endpointPath)) fail("runway_endpoint_invalid");
  return endpointPath;
}

function runwayEnvelope(entry, selection, body) {
  return deepFreeze({
    provider: "runway",
    endpointPath: assertRunwayEndpoint(entry, selection),
    method: "POST",
    body,
    pollKind: GENERATION_PROVIDER_POLL_KINDS.runway,
  });
}

function buildSeedream(entry, selection, input, providerRatio) {
  const imageMode = selection.inputMode === "image";
  assertAllowedInputKeys(
    input,
    imageMode ? ["promptText", "referenceImageUrls"] : ["promptText"],
  );
  if (selection.durationSeconds !== 0 || selection.audio || selection.spokenDialogue) {
    fail("seedream_semantics_invalid");
  }
  if (
    selection.firstFrame ||
    selection.lastFrame ||
    selection.referenceVideo ||
    (imageMode ? selection.referenceImageCount < 1 : selection.referenceImageCount !== 0)
  ) fail("seedream_input_invalid");
  const references = exactUrlArray(
    input,
    "referenceImageUrls",
    selection.referenceImageCount,
    "reference_image_urls_invalid",
  );
  const body = {
    model: entry.model,
    promptText: exactPrompt(input, entry),
    ratio: providerRatio,
    outputFormat: "png",
    outputCount: 1,
  };
  if (references.length) {
    body.referenceImages = references.map((uri, index) => ({
      uri,
      tag: index === 0 ? PRODUCT_REFERENCE_TAG : `${PRODUCT_REFERENCE_TAG}${index + 1}`,
    }));
  }
  return runwayEnvelope(entry, selection, body);
}

function buildGen4(entry, selection, input, providerRatio) {
  const imageMode = selection.inputMode === "image";
  assertAllowedInputKeys(
    input,
    imageMode ? ["promptText", "firstFrameUrl"] : ["promptText"],
  );
  if (selection.audio || selection.spokenDialogue || selection.referenceVideo ||
      selection.referenceImageCount !== 0 || selection.lastFrame) {
    fail("gen4_semantics_invalid");
  }
  if (entry.model === "gen4_turbo" && !imageMode) fail("gen4_input_invalid");
  if (imageMode !== selection.firstFrame) fail("gen4_first_frame_invalid");
  const body = {
    model: entry.model,
    promptText: exactPrompt(input, entry),
  };
  if (imageMode) {
    body.promptImage = exactFrameUrl(
      input,
      "firstFrameUrl",
      true,
      "first_frame_url_invalid",
    );
  }
  body.ratio = providerRatio;
  body.duration = selection.durationSeconds;
  return runwayEnvelope(entry, selection, body);
}

function buildSeedance(entry, selection, input, providerRatio) {
  const allowedKeys = selection.inputMode === "text"
    ? ["promptText", "referenceImageUrls", "referenceVideoUrls"]
    : selection.inputMode === "image"
    ? ["promptText", "firstFrameUrl", "lastFrameUrl", "referenceImageUrls"]
    : ["promptText", "inputVideoUrl", "referenceImageUrls", "referenceVideoUrls"];
  assertAllowedInputKeys(input, allowedKeys);
  const references = exactUrlArray(
    input,
    "referenceImageUrls",
    selection.referenceImageCount,
    "reference_image_urls_invalid",
  );
  const body = {
    model: entry.model,
    promptText: exactPrompt(input, entry),
    audio: selection.audio,
    duration: selection.durationSeconds,
    ratio: providerRatio,
  };

  if (selection.inputMode === "image") {
    if (selection.referenceVideo) fail("seedance_image_reference_video_invalid");
    if (selection.lastFrame && !selection.firstFrame) fail("last_frame_requires_first_frame");
    if (references.length && (selection.firstFrame || selection.lastFrame)) {
      fail("seedance_keyframes_references_mixed");
    }
    const first = exactFrameUrl(
      input,
      "firstFrameUrl",
      selection.firstFrame,
      "first_frame_url_invalid",
    );
    const last = exactFrameUrl(
      input,
      "lastFrameUrl",
      selection.lastFrame,
      "last_frame_url_invalid",
    );
    if (!first && !references.length) fail("seedance_image_input_missing");
    body.promptImage = references.length
      ? references.map((uri) => ({ uri }))
      : [
        { uri: first, position: "first" },
        ...(last ? [{ uri: last, position: "last" }] : []),
      ];
  } else {
    if (selection.firstFrame || selection.lastFrame) fail("seedance_frame_mode_invalid");
    if (selection.inputMode === "video") {
      body.promptVideo = exactHttpsUrl(input.inputVideoUrl, "input_video_url_invalid");
    }
    if (references.length) body.references = references.map((uri) => ({ uri }));
    const videos = optionalReferenceVideos(
      input,
      selection,
      Number(entry.server?.maxReferenceVideos || 0),
    );
    if (videos.length) {
      body.referenceVideos = videos.map((uri) => ({ type: "video", uri }));
    }
  }
  return runwayEnvelope(entry, selection, body);
}

function buildRunwayVeo(entry, selection, input, providerRatio) {
  const imageMode = selection.inputMode === "image";
  assertAllowedInputKeys(
    input,
    imageMode
      ? ["promptText", "firstFrameUrl", "lastFrameUrl"]
      : ["promptText"],
  );
  if (selection.referenceImageCount !== 0 || selection.referenceVideo) {
    fail("runway_veo_references_invalid");
  }
  if (imageMode !== selection.firstFrame || (!imageMode && selection.lastFrame)) {
    fail("runway_veo_frames_invalid");
  }
  const body = {
    model: entry.model,
    promptText: exactPrompt(input, entry),
    ratio: providerRatio,
    audio: selection.audio,
    duration: selection.durationSeconds,
  };
  if (imageMode) {
    const first = exactFrameUrl(
      input,
      "firstFrameUrl",
      true,
      "first_frame_url_invalid",
    );
    const last = exactFrameUrl(
      input,
      "lastFrameUrl",
      selection.lastFrame,
      "last_frame_url_invalid",
    );
    body.promptImage = last
      ? [
        { uri: first, position: "first" },
        { uri: last, position: "last" },
      ]
      : first;
  }
  return runwayEnvelope(entry, selection, body);
}

function buildRunwayOmni(entry, selection, input, providerRatio) {
  const allowedKeys = selection.inputMode === "text"
    ? ["promptText"]
    : selection.inputMode === "image"
    ? ["promptText", "firstFrameUrl"]
    : [
      "promptText",
      "inputVideoUrl",
      "referenceImageUrls",
      "inputVideoDurationSeconds",
      "inputVideoRatio",
    ];
  assertAllowedInputKeys(input, allowedKeys);
  if (!selection.audio) fail("audio_is_inherent");
  if (selection.lastFrame) fail("omni_last_frame_invalid");
  const body = {
    model: entry.model,
    promptText: exactPrompt(input, entry),
  };
  if (selection.inputMode === "text") {
    if (selection.firstFrame || selection.referenceVideo || selection.referenceImageCount) {
      fail("omni_text_input_invalid");
    }
    body.ratio = providerRatio;
    body.duration = selection.durationSeconds;
  } else if (selection.inputMode === "image") {
    if (!selection.firstFrame || selection.referenceVideo || selection.referenceImageCount) {
      fail("omni_image_input_invalid");
    }
    body.promptImage = exactFrameUrl(
      input,
      "firstFrameUrl",
      true,
      "first_frame_url_invalid",
    );
    body.ratio = providerRatio;
    body.duration = selection.durationSeconds;
  } else {
    if (selection.firstFrame || !selection.referenceVideo) {
      fail("omni_video_input_invalid");
    }
    if (
      !Number.isInteger(input.inputVideoDurationSeconds) ||
      input.inputVideoDurationSeconds !== selection.durationSeconds ||
      input.inputVideoRatio !== selection.ratio
    ) fail("omni_input_video_metadata_mismatch");
    body.videoUri = exactHttpsUrl(input.inputVideoUrl, "input_video_url_invalid");
    const references = exactUrlArray(
      input,
      "referenceImageUrls",
      selection.referenceImageCount,
      "reference_image_urls_invalid",
    );
    if (references.length) body.references = references.map((uri) => ({ uri }));
  }
  return runwayEnvelope(entry, selection, body);
}

function buildRunwayRequest(entry, selection, input, providerRatio) {
  if (entry.model === "seedream5_lite") {
    return buildSeedream(entry, selection, input, providerRatio);
  }
  if (entry.model === "gen4_turbo" || entry.model === "gen4.5") {
    return buildGen4(entry, selection, input, providerRatio);
  }
  if (SEEDANCE_MODELS.has(entry.model)) {
    return buildSeedance(entry, selection, input, providerRatio);
  }
  if (RUNWAY_VEO_MODELS.has(entry.model)) {
    return buildRunwayVeo(entry, selection, input, providerRatio);
  }
  if (entry.model === "gemini_omni_flash") {
    return buildRunwayOmni(entry, selection, input, providerRatio);
  }
  fail("runway_model_adapter_missing");
}

function buildGoogleVeoLite(entry, selection, input, providerRatio) {
  const imageMode = selection.inputMode === "image";
  assertAllowedInputKeys(
    input,
    imageMode
      ? ["promptText", "imageInlineData", "lastFrameInlineData"]
      : ["promptText"],
  );
  if (!selection.audio) fail("audio_is_inherent");
  if (selection.referenceImageCount !== 0 || selection.referenceVideo) {
    fail("google_veo_references_invalid");
  }
  if (entry.server?.endpoints?.[selection.inputMode] !== "predictLongRunning") {
    fail("google_endpoint_invalid");
  }
  const instance = { prompt: exactPrompt(input, entry) };
  if (imageMode) {
    if (!selection.firstFrame) fail("google_first_frame_required");
    const image = exactInlineFrame(
      input,
      "imageInlineData",
      true,
      "image_inline_data_invalid",
    );
    const lastFrame = exactInlineFrame(
      input,
      "lastFrameInlineData",
      selection.lastFrame,
      "last_frame_inline_data_invalid",
    );
    if (lastFrame && selection.durationSeconds !== 8) {
      fail("google_last_frame_duration_invalid");
    }
    instance.image = { inlineData: image };
    if (lastFrame) instance.lastFrame = { inlineData: lastFrame };
  } else if (selection.firstFrame || selection.lastFrame) {
    fail("google_text_frames_invalid");
  }
  return deepFreeze({
    provider: "google",
    endpointPath: `/v1beta/models/${entry.model}:predictLongRunning`,
    method: "POST",
    body: {
      instances: [instance],
      parameters: {
        numberOfVideos: 1,
        aspectRatio: providerRatio,
        resolution: selection.resolution,
        durationSeconds: selection.durationSeconds,
      },
    },
    pollKind: GENERATION_PROVIDER_POLL_KINDS.google,
  });
}

/**
 * Build one inert provider request envelope from canonical, already-validated
 * inputs. Authentication headers and provider origins intentionally cannot be
 * represented by this API.
 */
export function buildGenerationProviderRequest(entry, selection, input = {}) {
  const { providerRatio } = assertCanonicalSelection(entry, selection);
  if (!isPlainObject(input)) fail("input_invalid");
  if (entry.provider === "runway") {
    return buildRunwayRequest(entry, selection, input, providerRatio);
  }
  if (
    entry.provider === "google" &&
    entry.model === "veo-3.1-lite-generate-preview"
  ) return buildGoogleVeoLite(entry, selection, input, providerRatio);
  fail("provider_adapter_missing");
}
