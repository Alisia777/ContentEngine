/*
 * Canonical generation model catalog.
 *
 * This is the server-side source of truth for model identity, public
 * capabilities, provider routing and pricing. Browser code must consume the
 * allowlisted projection returned by publicGenerationModelCatalog(), never
 * import or maintain a second executable model list.
 *
 * The module is deliberately pure: no environment reads, network, storage or
 * provider calls. Organization feature flags are passed in by the caller.
 */

export const GENERATION_MODEL_CATALOG_VERSION = "2026-08-13.v1";
export const RUNWAY_PRICING_VERSION = "runway-credits-2026-08-13.v1";
export const GOOGLE_VEO_PRICING_VERSION = "google-veo-2026-08-13.v1";

export const GENERATION_MODEL_FEATURE_FLAGS = Object.freeze({
  runwayPremium: "generation_runway_premium_v1",
  googleVeoLite: "generation_google_veo_lite_v1",
});

const PUBLIC_FIELDS = Object.freeze([
  "provider",
  "model",
  "publicLabel",
  "family",
  "contentKind",
  "lifecycle",
  "enabledByDefault",
  "inputModes",
  "supportsReferenceImages",
  "maxReferenceImages",
  "supportsReferenceVideo",
  "supportsFirstFrame",
  "supportsLastFrame",
  "supportsGeneratedAudio",
  "supportsSpokenDialogue",
  "minDurationSeconds",
  "maxDurationSeconds",
  "allowedDurations",
  "allowedRatios",
  "allowedResolutions",
  "promptLimit",
  "pricingKind",
  "pricingVersion",
  "bestFor",
  "avoidFor",
  "qualityTier",
  "speedTier",
]);
const PUBLIC_INPUT_CAPABILITY_FIELDS = Object.freeze([
  "allowedRatios",
  "allowedResolutions",
  "maxReferenceImages",
  "supportsReferenceVideo",
  "supportsFirstFrame",
  "supportsLastFrame",
  "allowedDurationsByResolution",
  "lastFrameDurationSeconds",
]);

const COMMON_VIDEO_RATIOS = Object.freeze([
  "21:9",
  "16:9",
  "4:3",
  "1:1",
  "3:4",
  "9:16",
]);
const LANDSCAPE_PORTRAIT_RATIOS = Object.freeze(["16:9", "9:16"]);
const GEN4_IMAGE_RATIOS = COMMON_VIDEO_RATIOS;
const SEEDANCE_DURATIONS = Object.freeze(
  Array.from({ length: 12 }, (_, index) => index + 4),
);
const FLEXIBLE_TWO_TO_TEN = Object.freeze(
  Array.from({ length: 9 }, (_, index) => index + 2),
);
const OMNI_DURATIONS = Object.freeze(
  Array.from({ length: 8 }, (_, index) => index + 3),
);
const VEO_DURATIONS = Object.freeze([4, 6, 8]);

function frozenRatioMap(value) {
  return Object.freeze(
    Object.fromEntries(
      Object.entries(value || {}).map(([resolution, ratios]) => [
        resolution,
        Object.freeze({ ...(ratios || {}) }),
      ]),
    ),
  );
}

const SEEDREAM_PROVIDER_RATIOS = frozenRatioMap({
  "2K": {
    "1:1": "2048:2048",
    "4:3": "2304:1728",
    "3:4": "1728:2304",
    "16:9": "2848:1600",
    "9:16": "1600:2848",
    "3:2": "2496:1664",
    "2:3": "1664:2496",
    "21:9": "3136:1344",
  },
  "3K": {
    "1:1": "3072:3072",
    "4:3": "3456:2592",
    "3:4": "2592:3456",
    "16:9": "4096:2304",
    "9:16": "2304:4096",
    "3:2": "3744:2496",
    "2:3": "2496:3744",
    "21:9": "4704:2016",
  },
});
const GEN4_PROVIDER_RATIOS = frozenRatioMap({
  "720p": {
    "21:9": "1584:672",
    "16:9": "1280:720",
    "4:3": "1104:832",
    "1:1": "960:960",
    "3:4": "832:1104",
    "9:16": "720:1280",
  },
});
const SEEDANCE_PROVIDER_RATIOS = frozenRatioMap({
  "480p": {
    "21:9": "992:432",
    "16:9": "864:496",
    "4:3": "752:560",
    "1:1": "640:640",
    "3:4": "560:752",
    "9:16": "496:864",
  },
  "720p": {
    "21:9": "1470:630",
    "16:9": "1280:720",
    "4:3": "1112:834",
    "1:1": "960:960",
    "3:4": "834:1112",
    "9:16": "720:1280",
  },
  "1080p": {
    "21:9": "2206:946",
    "16:9": "1920:1080",
    "4:3": "1664:1248",
    "1:1": "1440:1440",
    "3:4": "1248:1664",
    "9:16": "1080:1920",
  },
  "4K": {
    "21:9": "3840:1646",
    "16:9": "3840:2160",
    "4:3": "3840:2880",
    "1:1": "3840:3840",
    "3:4": "2880:3840",
    "9:16": "2160:3840",
  },
});
const VEO_RUNWAY_PROVIDER_RATIOS = frozenRatioMap({
  "720p": { "16:9": "1280:720", "9:16": "720:1280" },
  "1080p": { "16:9": "1920:1080", "9:16": "1080:1920" },
});
const OMNI_PROVIDER_RATIOS = frozenRatioMap({
  "720p": { "16:9": "1280:720", "9:16": "720:1280" },
});
const GOOGLE_VEO_PROVIDER_RATIOS = frozenRatioMap({
  "720p": { "16:9": "16:9", "9:16": "9:16" },
  "1080p": { "16:9": "16:9", "9:16": "9:16" },
});

function frozenArray(value) {
  return Object.freeze([...(Array.isArray(value) ? value : [])]);
}

function frozenRecord(value) {
  return Object.freeze({ ...(value && typeof value === "object" ? value : {}) });
}

function catalogEntry(value) {
  const entry = {
    ...value,
    inputModes: frozenArray(value.inputModes),
    allowedDurations: frozenArray(value.allowedDurations),
    allowedRatios: frozenArray(value.allowedRatios),
    allowedResolutions: frozenArray(value.allowedResolutions),
    bestFor: frozenArray(value.bestFor),
    avoidFor: frozenArray(value.avoidFor),
    server: Object.freeze({
      ...value.server,
      endpoints: frozenRecord(value.server?.endpoints),
      inputContracts: Object.freeze(
        Object.fromEntries(
          Object.entries(value.server?.inputContracts || {}).map(([mode, contract]) => [
            mode,
            Object.freeze({
              ...contract,
              allowedRatios: frozenArray(contract.allowedRatios),
              allowedResolutions: frozenArray(contract.allowedResolutions),
              allowedDurationsByResolution: Object.freeze(
                Object.fromEntries(
                  Object.entries(contract.allowedDurationsByResolution || {}).map(
                    ([resolution, durations]) => [resolution, frozenArray(durations)],
                  ),
                ),
              ),
            }),
          ]),
        ),
      ),
      providerRatios: frozenRatioMap(value.server?.providerRatios),
      pricing: frozenRecord(value.server?.pricing),
    }),
  };
  return Object.freeze(entry);
}

const RAW_CATALOG = [
  catalogEntry({
    provider: "runway",
    model: "seedream5_lite",
    publicLabel: "Seedream 5 Lite",
    family: "Seedream",
    contentKind: "photo",
    lifecycle: "production",
    enabledByDefault: true,
    inputModes: ["text", "image"],
    supportsReferenceImages: true,
    maxReferenceImages: 14,
    supportsReferenceVideo: false,
    supportsFirstFrame: false,
    supportsLastFrame: false,
    supportsGeneratedAudio: false,
    supportsSpokenDialogue: false,
    minDurationSeconds: 0,
    maxDurationSeconds: 0,
    allowedDurations: [0],
    allowedRatios: ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9"],
    allowedResolutions: ["2K", "3K"],
    promptLimit: 4_000,
    pricingKind: "runway_fixed_credits_per_image",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["точное товарное фото", "несколько ракурсов одного товара"],
    avoidFor: ["видео", "сцена с речью"],
    qualityTier: "balanced",
    speedTier: "fast",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_image", image: "/v1/text_to_image" },
      inputContracts: {
        text: { allowedRatios: ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9"], allowedResolutions: ["2K", "3K"], maxReferenceImages: 0 },
        image: { allowedRatios: ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3", "21:9"], allowedResolutions: ["2K", "3K"], maxReferenceImages: 14 },
      },
      providerRatios: SEEDREAM_PROVIDER_RATIOS,
      pricing: { kind: "fixed_credits", fixedCredits: 4 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "gen4_turbo",
    publicLabel: "Gen-4 Turbo",
    family: "Gen-4",
    contentKind: "video",
    lifecycle: "production",
    enabledByDefault: true,
    inputModes: ["image"],
    supportsReferenceImages: false,
    maxReferenceImages: 0,
    supportsReferenceVideo: false,
    supportsFirstFrame: true,
    supportsLastFrame: false,
    supportsGeneratedAudio: false,
    supportsSpokenDialogue: false,
    minDurationSeconds: 2,
    maxDurationSeconds: 10,
    allowedDurations: FLEXIBLE_TWO_TO_TEN,
    allowedRatios: GEN4_IMAGE_RATIOS,
    allowedResolutions: ["720p"],
    promptLimit: 1_000,
    pricingKind: "runway_credits_per_output_second",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["экономное движение товара из готового кадра", "варианты без речи"],
    avoidFor: ["генерация без исходного фото", "сцена с речью или нативным звуком"],
    qualityTier: "economy",
    speedTier: "fast",
    server: {
      featureFlag: null,
      endpoints: { image: "/v1/image_to_video" },
      inputContracts: {
        image: { allowedRatios: GEN4_IMAGE_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 0, supportsFirstFrame: true },
      },
      providerRatios: GEN4_PROVIDER_RATIOS,
      pricing: { kind: "credits_per_output_second", creditsPerSecond: 5 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "seedance2_fast",
    publicLabel: "Seedance 2 Fast",
    family: "Seedance 2",
    contentKind: "video",
    lifecycle: "production",
    enabledByDefault: true,
    inputModes: ["text", "image", "video"],
    supportsReferenceImages: true,
    maxReferenceImages: 9,
    supportsReferenceVideo: true,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 15,
    allowedDurations: SEEDANCE_DURATIONS,
    allowedRatios: COMMON_VIDEO_RATIOS,
    allowedResolutions: ["480p", "720p"],
    promptLimit: 3_500,
    pricingKind: "runway_credits_per_output_second",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["короткий UGC с человеком и речью", "несколько референсов и нативный звук"],
    avoidFor: ["самый дешёвый немой черновик", "вывод выше 720p"],
    qualityTier: "balanced",
    speedTier: "fast",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video", video: "/v1/video_to_video" },
      inputContracts: {
        text: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: false, supportsFirstFrame: true, supportsLastFrame: true },
        video: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
      },
      providerRatios: SEEDANCE_PROVIDER_RATIOS,
      maxReferenceVideos: 3,
      pricing: { kind: "credits_per_output_second", creditsPerSecond: 29 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "gen4.5",
    publicLabel: "Gen-4.5",
    family: "Gen-4",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: true,
    inputModes: ["text", "image"],
    supportsReferenceImages: false,
    maxReferenceImages: 0,
    supportsReferenceVideo: false,
    supportsFirstFrame: true,
    supportsLastFrame: false,
    supportsGeneratedAudio: false,
    supportsSpokenDialogue: false,
    minDurationSeconds: 2,
    maxDurationSeconds: 10,
    allowedDurations: FLEXIBLE_TWO_TO_TEN,
    allowedRatios: GEN4_IMAGE_RATIOS,
    allowedResolutions: ["720p"],
    promptLimit: 1_000,
    pricingKind: "runway_credits_per_output_second",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["сложное визуальное движение без речи", "высокое качество из текста или кадра"],
    avoidFor: ["диалог и обязательный нативный звук", "самый дешёвый черновик"],
    qualityTier: "premium",
    speedTier: "normal",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video" },
      inputContracts: {
        text: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 0, supportsFirstFrame: false },
        image: { allowedRatios: GEN4_IMAGE_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 0, supportsFirstFrame: true },
      },
      providerRatios: GEN4_PROVIDER_RATIOS,
      pricing: { kind: "credits_per_output_second", creditsPerSecond: 12 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "seedance2_mini",
    publicLabel: "Seedance 2 Mini",
    family: "Seedance 2",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: true,
    inputModes: ["text", "image", "video"],
    supportsReferenceImages: true,
    maxReferenceImages: 9,
    supportsReferenceVideo: true,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 15,
    allowedDurations: SEEDANCE_DURATIONS,
    allowedRatios: COMMON_VIDEO_RATIOS,
    allowedResolutions: ["480p", "720p"],
    promptLimit: 3_500,
    pricingKind: "runway_credits_per_output_second_with_minimum",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["экономный мультимодальный черновик со звуком", "вариация готового видео"],
    avoidFor: ["максимальное качество", "короткий запрос дешевле минимального тарифа"],
    qualityTier: "economy",
    speedTier: "fast",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video", video: "/v1/video_to_video" },
      inputContracts: {
        text: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: false, supportsFirstFrame: true, supportsLastFrame: true },
        video: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
      },
      providerRatios: SEEDANCE_PROVIDER_RATIOS,
      maxReferenceVideos: 3,
      pricing: { kind: "credits_per_output_second", creditsPerSecond: 16, minimumCredits: 64 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "veo3.1_fast",
    publicLabel: "Veo 3.1 Fast",
    family: "Veo 3.1",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: true,
    inputModes: ["text", "image"],
    supportsReferenceImages: false,
    maxReferenceImages: 0,
    supportsReferenceVideo: false,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 8,
    allowedDurations: VEO_DURATIONS,
    allowedRatios: LANDSCAPE_PORTRAIT_RATIOS,
    allowedResolutions: ["720p", "1080p"],
    promptLimit: 1_000,
    pricingKind: "runway_credits_per_output_second_by_audio",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["человек, естественный звук и короткая речь", "первый и последний кадр"],
    avoidFor: ["дешёвый немой черновик", "video-to-video"],
    qualityTier: "balanced",
    speedTier: "normal",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video" },
      inputContracts: {
        text: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: true, supportsLastFrame: true },
      },
      providerRatios: VEO_RUNWAY_PROVIDER_RATIOS,
      pricing: { kind: "credits_per_output_second_by_audio", withAudio: 15, withoutAudio: 10 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "gemini_omni_flash",
    publicLabel: "Gemini Omni Flash",
    family: "Gemini Omni",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: true,
    inputModes: ["text", "image", "video"],
    supportsReferenceImages: true,
    maxReferenceImages: 5,
    supportsReferenceVideo: true,
    supportsFirstFrame: true,
    supportsLastFrame: false,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 3,
    maxDurationSeconds: 10,
    allowedDurations: OMNI_DURATIONS,
    allowedRatios: LANDSCAPE_PORTRAIT_RATIOS,
    allowedResolutions: ["720p"],
    promptLimit: 4_000,
    pricingKind: "runway_gemini_omni_by_input",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["вариация готового видео", "быстрый мультимодальный черновик"],
    avoidFor: ["1080p или 4K", "точный последний кадр"],
    qualityTier: "economy",
    speedTier: "fast",
    server: {
      featureFlag: null,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video", video: "/v1/video_to_video" },
      inputContracts: {
        text: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 0, supportsReferenceVideo: false, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 0, supportsReferenceVideo: false, supportsFirstFrame: true, supportsLastFrame: false },
        video: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p"], maxReferenceImages: 5, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
      },
      providerRatios: OMNI_PROVIDER_RATIOS,
      pricing: { kind: "gemini_omni_by_input", textCreditsPerSecond: 10, imageCreditsPerSecond: 10, imageSurchargeCredits: 1, videoCreditsPerInputSecond: 11, referenceImageCredits: 1 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "veo3.1",
    publicLabel: "Veo 3.1",
    family: "Veo 3.1",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: false,
    inputModes: ["text", "image"],
    supportsReferenceImages: false,
    maxReferenceImages: 0,
    supportsReferenceVideo: false,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 8,
    allowedDurations: VEO_DURATIONS,
    allowedRatios: LANDSCAPE_PORTRAIT_RATIOS,
    allowedResolutions: ["720p", "1080p"],
    promptLimit: 1_000,
    pricingKind: "runway_credits_per_output_second_by_audio",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["премиальная сцена со звуком", "первый и последний кадр"],
    avoidFor: ["ограниченный бюджет", "video-to-video"],
    qualityTier: "premium",
    speedTier: "slow",
    server: {
      featureFlag: GENERATION_MODEL_FEATURE_FLAGS.runwayPremium,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video" },
      inputContracts: {
        text: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: true, supportsLastFrame: true },
      },
      providerRatios: VEO_RUNWAY_PROVIDER_RATIOS,
      pricing: { kind: "credits_per_output_second_by_audio", withAudio: 40, withoutAudio: 20 },
    },
  }),
  catalogEntry({
    provider: "runway",
    model: "seedance2",
    publicLabel: "Seedance 2",
    family: "Seedance 2",
    contentKind: "video",
    lifecycle: "experimental",
    enabledByDefault: false,
    inputModes: ["text", "image", "video"],
    supportsReferenceImages: true,
    maxReferenceImages: 9,
    supportsReferenceVideo: true,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 15,
    allowedDurations: SEEDANCE_DURATIONS,
    allowedRatios: COMMON_VIDEO_RATIOS,
    allowedResolutions: ["480p", "720p", "1080p", "4K"],
    promptLimit: 3_500,
    pricingKind: "runway_credits_per_output_second_by_resolution",
    pricingVersion: RUNWAY_PRICING_VERSION,
    bestFor: ["премиальный мультимодальный ролик", "сложные референсы и речь"],
    avoidFor: ["ограниченный бюджет", "быстрый черновик"],
    qualityTier: "premium",
    speedTier: "slow",
    server: {
      featureFlag: GENERATION_MODEL_FEATURE_FLAGS.runwayPremium,
      endpoints: { text: "/v1/text_to_video", image: "/v1/image_to_video", video: "/v1/video_to_video" },
      inputContracts: {
        text: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p", "1080p", "4K"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
        image: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p", "1080p", "4K"], maxReferenceImages: 9, supportsReferenceVideo: false, supportsFirstFrame: true, supportsLastFrame: true },
        video: { allowedRatios: COMMON_VIDEO_RATIOS, allowedResolutions: ["480p", "720p", "1080p", "4K"], maxReferenceImages: 9, supportsReferenceVideo: true, supportsFirstFrame: false, supportsLastFrame: false },
      },
      providerRatios: SEEDANCE_PROVIDER_RATIOS,
      maxReferenceVideos: 3,
      pricing: { kind: "credits_per_output_second_by_resolution", rates: Object.freeze({ "480p": 36, "720p": 36, "1080p": 40, "4K": 150 }) },
    },
  }),
  catalogEntry({
    provider: "google",
    model: "veo-3.1-lite-generate-preview",
    publicLabel: "Veo 3.1 Lite",
    family: "Veo 3.1",
    contentKind: "video",
    lifecycle: "preview",
    enabledByDefault: false,
    inputModes: ["text", "image"],
    supportsReferenceImages: false,
    maxReferenceImages: 0,
    supportsReferenceVideo: false,
    supportsFirstFrame: true,
    supportsLastFrame: true,
    supportsGeneratedAudio: true,
    supportsSpokenDialogue: true,
    minDurationSeconds: 4,
    maxDurationSeconds: 8,
    allowedDurations: VEO_DURATIONS,
    allowedRatios: LANDSCAPE_PORTRAIT_RATIOS,
    allowedResolutions: ["720p", "1080p"],
    promptLimit: 1_024,
    pricingKind: "google_usd_minor_per_output_second_by_resolution",
    pricingVersion: GOOGLE_VEO_PRICING_VERSION,
    bestFor: ["недорогой ролик со звуком через прямой Google API", "массовые 720p/1080p варианты"],
    avoidFor: ["4K", "extension", "production без отдельного feature flag"],
    qualityTier: "economy",
    speedTier: "normal",
    server: {
      featureFlag: GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite,
      endpoints: { text: "predictLongRunning", image: "predictLongRunning" },
      inputContracts: {
        text: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: false, supportsLastFrame: false, allowedDurationsByResolution: { "720p": VEO_DURATIONS, "1080p": [8] } },
        image: { allowedRatios: LANDSCAPE_PORTRAIT_RATIOS, allowedResolutions: ["720p", "1080p"], maxReferenceImages: 0, supportsFirstFrame: true, supportsLastFrame: true, allowedDurationsByResolution: { "720p": VEO_DURATIONS, "1080p": [8] }, lastFrameDurationSeconds: 8 },
      },
      providerRatios: GOOGLE_VEO_PROVIDER_RATIOS,
      pricing: { kind: "usd_minor_per_output_second_by_resolution", rates: Object.freeze({ "720p": 5, "1080p": 8 }) },
    },
  }),
];

export const GENERATION_MODEL_CATALOG = Object.freeze(RAW_CATALOG);

const CATALOG_BY_KEY = new Map(
  GENERATION_MODEL_CATALOG.map((entry) => [`${entry.provider}:${entry.model}`, entry]),
);

function featureEnabled(flags, key) {
  if (!key) return true;
  return flags?.[key] === true;
}

export function generationModelCatalogEntry(provider, model) {
  return CATALOG_BY_KEY.get(`${String(provider || "").trim()}:${String(model || "").trim()}`) || null;
}

export function generationModelEnabled(entry, featureFlags = {}) {
  if (!entry || entry.lifecycle === "disabled") return false;
  if (entry.enabledByDefault) return true;
  return featureEnabled(featureFlags, entry.server?.featureFlag);
}

function publicEntry(entry, featureFlags) {
  const projected = Object.fromEntries(
    PUBLIC_FIELDS.map((key) => [key, Array.isArray(entry[key]) ? [...entry[key]] : entry[key]]),
  );
  projected.inputCapabilities = Object.freeze(
    Object.fromEntries(
      Object.entries(entry.server.inputContracts).map(([mode, contract]) => [
        mode,
        Object.freeze(
          Object.fromEntries(
            PUBLIC_INPUT_CAPABILITY_FIELDS
              .filter((key) => contract[key] !== undefined)
              .map((key) => [
                key,
                Array.isArray(contract[key])
                  ? Object.freeze([...contract[key]])
                  : key === "allowedDurationsByResolution"
                  ? Object.freeze(
                    Object.fromEntries(
                      Object.entries(contract[key] || {}).map(
                        ([resolution, durations]) => [resolution, Object.freeze([...durations])],
                      ),
                    ),
                  )
                  : contract[key],
              ]),
          ),
        ),
      ]),
    ),
  );
  projected.enabled = generationModelEnabled(entry, featureFlags);
  projected.disabledReasonCode = projected.enabled
    ? null
    : entry.lifecycle === "disabled"
    ? "model_disabled"
    : "organization_feature_disabled";
  return Object.freeze(projected);
}

export function publicGenerationModelCatalog({ featureFlags = {} } = {}) {
  return Object.freeze({
    version: GENERATION_MODEL_CATALOG_VERSION,
    models: Object.freeze(
      GENERATION_MODEL_CATALOG.map((entry) => publicEntry(entry, featureFlags)),
    ),
  });
}

function selectionFailure(code, entry = null) {
  return Object.freeze({
    ok: false,
    code,
    provider: entry?.provider || "",
    model: entry?.model || "",
    catalogVersion: GENERATION_MODEL_CATALOG_VERSION,
    pricingVersion: entry?.pricingVersion || "",
  });
}

function exactInputContract(entry, inputMode) {
  return entry.server?.inputContracts?.[inputMode] || null;
}

export function validateGenerationModelSelection(
  entry,
  selection = {},
  { featureFlags = {} } = {},
) {
  if (!entry || !CATALOG_BY_KEY.has(`${entry.provider}:${entry.model}`)) {
    return selectionFailure("model_unknown");
  }
  if (!generationModelEnabled(entry, featureFlags)) {
    return selectionFailure("model_disabled_by_organization", entry);
  }
  const inputMode = String(selection.inputMode || "").trim();
  const contract = exactInputContract(entry, inputMode);
  if (!contract || !entry.inputModes.includes(inputMode)) {
    return selectionFailure("input_mode_unsupported", entry);
  }
  const durationSeconds = Number(selection.durationSeconds);
  if (
    !Number.isInteger(durationSeconds) ||
    !entry.allowedDurations.includes(durationSeconds)
  ) return selectionFailure("duration_unsupported", entry);
  const ratio = String(selection.ratio || "").trim();
  if (!contract.allowedRatios.includes(ratio)) {
    return selectionFailure("ratio_unsupported", entry);
  }
  const resolution = String(selection.resolution || "").trim();
  if (!contract.allowedResolutions.includes(resolution)) {
    return selectionFailure("resolution_unsupported", entry);
  }
  const durationsForResolution = contract.allowedDurationsByResolution?.[resolution];
  if (
    Array.isArray(durationsForResolution) &&
    !durationsForResolution.includes(durationSeconds)
  ) return selectionFailure("duration_resolution_unsupported", entry);
  if (selection.audio === true && !entry.supportsGeneratedAudio) {
    return selectionFailure("audio_unsupported", entry);
  }
  if (selection.spokenDialogue === true && !entry.supportsSpokenDialogue) {
    return selectionFailure("spoken_dialogue_unsupported", entry);
  }
  const referenceCount = Number(selection.referenceImageCount || 0);
  const maxReferenceImages = Number.isInteger(contract.maxReferenceImages)
    ? contract.maxReferenceImages
    : entry.maxReferenceImages;
  if (
    !Number.isInteger(referenceCount) ||
    referenceCount < 0 ||
    referenceCount > maxReferenceImages ||
    (referenceCount > 0 && !entry.supportsReferenceImages)
  ) return selectionFailure("reference_image_count_unsupported", entry);
  const supportsReferenceVideo = contract.supportsReferenceVideo ?? entry.supportsReferenceVideo;
  if (selection.referenceVideo === true && !supportsReferenceVideo) {
    return selectionFailure("reference_video_unsupported", entry);
  }
  const supportsFirstFrame = contract.supportsFirstFrame ?? entry.supportsFirstFrame;
  if (selection.firstFrame === true && !supportsFirstFrame) {
    return selectionFailure("first_frame_unsupported", entry);
  }
  const supportsLastFrame = contract.supportsLastFrame ?? entry.supportsLastFrame;
  if (selection.lastFrame === true && !supportsLastFrame) {
    return selectionFailure("last_frame_unsupported", entry);
  }
  if (
    selection.lastFrame === true &&
    Number.isInteger(contract.lastFrameDurationSeconds) &&
    durationSeconds !== contract.lastFrameDurationSeconds
  ) return selectionFailure("last_frame_duration_unsupported", entry);
  return Object.freeze({
    ok: true,
    provider: entry.provider,
    model: entry.model,
    inputMode,
    durationSeconds,
    ratio,
    resolution,
    audio: selection.audio === true,
    spokenDialogue: selection.spokenDialogue === true,
    referenceImageCount: referenceCount,
    referenceVideo: selection.referenceVideo === true,
    firstFrame: selection.firstFrame === true,
    lastFrame: selection.lastFrame === true,
    catalogVersion: GENERATION_MODEL_CATALOG_VERSION,
    pricingVersion: entry.pricingVersion,
  });
}

export function estimateGenerationModelCostMinor(
  entry,
  selection = {},
  options = {},
) {
  const valid = validateGenerationModelSelection(entry, selection, options);
  if (!valid.ok) return valid;
  const pricing = entry.server.pricing;
  const duration = valid.durationSeconds;
  let estimatedCostMinor = 0;
  let estimatedCredits = null;
  if (pricing.kind === "fixed_credits") {
    estimatedCredits = pricing.fixedCredits;
  } else if (pricing.kind === "credits_per_output_second") {
    estimatedCredits = duration * pricing.creditsPerSecond;
    if (Number.isFinite(pricing.minimumCredits)) {
      estimatedCredits = Math.max(estimatedCredits, pricing.minimumCredits);
    }
  } else if (pricing.kind === "credits_per_output_second_by_audio") {
    estimatedCredits = duration * (valid.audio ? pricing.withAudio : pricing.withoutAudio);
  } else if (pricing.kind === "credits_per_output_second_by_resolution") {
    estimatedCredits = duration * Number(pricing.rates?.[valid.resolution] || 0);
  } else if (pricing.kind === "gemini_omni_by_input") {
    if (valid.inputMode === "video") {
      const inputSeconds = Number(selection.inputVideoDurationSeconds);
      if (!Number.isInteger(inputSeconds) || inputSeconds < 1 || inputSeconds > 10) {
        return selectionFailure("input_video_duration_unsupported", entry);
      }
      estimatedCredits = inputSeconds * pricing.videoCreditsPerInputSecond +
        valid.referenceImageCount * pricing.referenceImageCredits;
    } else if (valid.inputMode === "image") {
      estimatedCredits = duration * pricing.imageCreditsPerSecond + pricing.imageSurchargeCredits;
    } else {
      estimatedCredits = duration * pricing.textCreditsPerSecond;
    }
  } else if (pricing.kind === "usd_minor_per_output_second_by_resolution") {
    estimatedCostMinor = duration * Number(pricing.rates?.[valid.resolution] || 0);
  } else {
    return selectionFailure("pricing_contract_unknown", entry);
  }
  if (estimatedCredits !== null) estimatedCostMinor = Math.ceil(estimatedCredits);
  if (!Number.isSafeInteger(estimatedCostMinor) || estimatedCostMinor < 0) {
    return selectionFailure("pricing_estimate_invalid", entry);
  }
  return Object.freeze({
    ...valid,
    estimatedCostMinor,
    estimatedCredits,
  });
}

function assertCatalog() {
  const requiredFields = PUBLIC_FIELDS.filter((key) => key !== "allowedDurations");
  const keys = new Set();
  for (const entry of GENERATION_MODEL_CATALOG) {
    const key = `${entry.provider}:${entry.model}`;
    if (keys.has(key)) throw new Error(`generation_model_catalog_duplicate:${key}`);
    keys.add(key);
    if (requiredFields.some((field) => entry[field] === undefined)) {
      throw new Error(`generation_model_catalog_field_missing:${key}`);
    }
    if (!entry.allowedDurations.length || !entry.inputModes.length) {
      throw new Error(`generation_model_catalog_capability_missing:${key}`);
    }
    if (!entry.server?.pricing?.kind || !Object.keys(entry.server?.endpoints || {}).length) {
      throw new Error(`generation_model_catalog_execution_missing:${key}`);
    }
    if (entry.inputModes.some((mode) => !entry.server.inputContracts[mode])) {
      throw new Error(`generation_model_catalog_input_contract_missing:${key}`);
    }
    for (const mode of entry.inputModes) {
      const contract = entry.server.inputContracts[mode];
      for (const resolution of contract.allowedResolutions) {
        for (const ratio of contract.allowedRatios) {
          if (!entry.server.providerRatios?.[resolution]?.[ratio]) {
            throw new Error(
              `generation_model_catalog_provider_ratio_missing:${key}:${mode}:${resolution}:${ratio}`,
            );
          }
        }
      }
    }
  }
}

assertCatalog();
