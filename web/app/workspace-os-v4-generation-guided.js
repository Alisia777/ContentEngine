import {
  GENERATION_MODEL_RECOMMENDATION_ACTIONS,
  createGenerationModelRecommendationState,
  generationModelRecommendationReducer,
} from "./generation-model-recommendation.js?v=20260826.rebuild-clean.60";
import { normalizeGenerationModelAcceptance } from "./generation-model-acceptance-view.js?v=20260826.rebuild-clean.60";
import {
  GENERATION_STRATEGY_SELECT_ACTION,
  createGenerationStrategyViewState,
  generationStrategyViewMarkup,
  reduceGenerationStrategyViewState,
  selectedGenerationStrategySummary,
  validateSelectedGenerationStrategyDraft,
} from "./generation-strategy-view.js?v=20260826.rebuild-clean.60";
import {
  generationStrategyAssetEligibility,
  mergeGenerationStrategyAssetPages,
  normalizeGenerationStrategyAssetCandidates,
} from "./generation-strategy-assets.js?v=20260826.rebuild-clean.60";
import {
  GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS,
  createGenerationStrategySourcePicker,
  generationStrategyRequiredSourceCount,
  generationStrategySourceCountModes,
  generationStrategySourcePickerProjection,
  reduceGenerationStrategySourcePicker,
} from "./generation-strategy-source-picker.js?v=20260826.rebuild-clean.60";
import { resolveGenerationModelVisual } from "./generation-model-visuals-v1.js?v=20260826.rebuild-clean.60";

/*
 * ContentEngine Desktop v4 · guided generation.
 *
 * This adapter only re-composes the existing #mock-batch-form. Every original
 * control (including the real submit button) stays inside the same form, so
 * FormData, delegated business handlers, draft persistence and paid-launch
 * safeguards keep their original contract.
 */

const ROUTE = "/workspace/generation";
const SESSION_KEY = "contentengine.desktop.v4.generation-guided.v2";
const STEP_ATTRIBUTE = "data-ce-v4-generation-step";
const SESSION_ATTRIBUTE = "data-ce-v4-generation-session";
const FORM_BINDING_KEY = Symbol.for(
  "contentengine.generation-guided.form-binding.v1",
);
// Эпоха модуля — литерал текущего штампа: массовый рестамп обновляет её вместе
// со всеми пинами. По ней стражи отличают легитимный ремоунт того же кода от
// второго экземпляра из смешанного кэша (боевой случай 25.08.2026).
const GUIDED_EPOCH = "20260826.rebuild-clean.60";
const STRATEGY_REPEAT_MEDIA_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const PRODUCT_SWAP_REPEAT_MEDIA_LIMIT = 10;
const strategyRepeatProductOrigins = new WeakMap();

const STEPS = Object.freeze([
  {
    key: "mode",
    label: "Модель ИИ",
    hint: "Сравните модели по результату, длине, входным условиям и цене. ИИ-центр рекомендует, но окончательный выбор всегда делает человек.",
  },
  {
    key: "product",
    label: "Товар",
    hint: "Укажите точный артикул, название и категорию товара.",
  },
  {
    key: "destination",
    label: "Куда и кому",
    hint: "Выберите площадку, назначение, исполнителя и формат результата.",
  },
  {
    key: "brief",
    label: "Замысел",
    hint: "Опишите один понятный сюжет. Портал добавит технические ограничения сам.",
  },
  {
    key: "media",
    label: "Исходники",
    hint: "Выберите исходный MP4, аватара или исходный товар — только те роли, которые нужны выбранной стратегии.",
  },
  {
    key: "launch",
    label: "Проверка и запуск",
    hint: "Сверьте короткое резюме и только затем запустите создание.",
  },
]);

const runtime = {
  form: null,
  catalog: null,
  catalogSignals: null,
  catalogStatus: "idle",
  catalogRequest: 0,
  catalogRetryCount: 0,
  recommendationState: null,
  applyingModel: false,
  modelFilter: "relevant",
  externalSelectionActive: false,
  repeatSettings: null,
  pendingRepeatSettings: null,
  strategyCatalog: null,
  strategyCatalogStatus: "idle",
  strategyCatalogRequest: 0,
  strategyCatalogRetryCount: 0,
  strategyState: null,
  pendingStrategyRestore: null,
  strategyAssetPage: null,
  strategyAssetProjectId: "",
  strategyAssetStatus: "idle",
  strategyAssetError: "",
  strategyAssetRequest: 0,
  // A freshly uploaded MP4 is already registered and attached on the server,
  // but the read-only asset catalog may still be stale (or temporarily fail).
  // Keep only that exact server-issued UUID here so the compact handoff can
  // materialize the real source picker without inventing a paid authority.
  strategyRegisteredSourceProjectId: "",
  strategyRegisteredSources: new Map(),
  strategySourcePicker: null,
  strategyMechanicsDrafts: new Map(),
  strategyViewRoots: new WeakSet(),
  intakeHandoff: null,
  intakeHandoffProjectId: "",
};

const LEGACY_MODEL_BY_MODE = Object.freeze({
  real_photo: Object.freeze({ provider: "runway", model: "seedream5_lite" }),
  real_gen4: Object.freeze({ provider: "runway", model: "gen4_turbo" }),
  real_seedance: Object.freeze({ provider: "runway", model: "seedance2_fast" }),
});

const LEGACY_MODE_BY_MODEL = Object.freeze(
  Object.fromEntries(
    Object.entries(LEGACY_MODEL_BY_MODE).map(([mode, identity]) => [
      `${identity.provider}:${identity.model}`,
      mode,
    ]),
  ),
);

const MODEL_COPY = Object.freeze({
  readiness_unverified: "Техническая готовность проверится перед запуском",
  estimate_missing: "Стоимость будет подтверждена сервером до оплаты",
  budget_estimate_missing: "Нужна серверная оценка стоимости",
  organization_feature_disabled: "Нужен доступ организации",
  sql_authority_parity_pending: "Серверный безопасный запуск этой модели ещё проходит проверку",
  premium_model_launch_unsupported: "Премиальная модель пока доступна только для сравнения",
  strategy_contour_launch_only:
    "Запускается из форм стратегий («Создание»), а не из этой формы",
  direct_google_disabled: "Прямой запуск Google пока отключён; модель доступна только для сравнения",
  model_disabled: "Модель пока отключена",
  content_kind_mismatch: "Не подходит для выбранного результата",
  duration_not_supported: "Не поддерживает выбранную длительность",
  no_compatible_model: "Для текущих условий нет полностью совместимой модели",
  content_kind_unsupported: "Не подходит для выбранного типа результата",
  duration_unsupported: "Не поддерживает выбранную длительность",
  duration_resolution_unsupported: "Эта длительность недоступна в выбранном разрешении",
  input_mode_unsupported: "Не поддерживает выбранный тип исходника",
  reference_images_unsupported: "Не принимает выбранные фото",
  reference_image_count_unsupported: "Слишком много исходных фото",
  audio_unsupported: "Не создаёт требуемый звук",
  spoken_dialogue_unsupported: "Не подходит для речи или диалога",
  cost_estimate_required: "Нужна новая серверная оценка стоимости",
  budget_exceeded: "Не укладывается в текущий лимит",
  provider_not_ready: "Провайдер сейчас не готов",
  model_not_ready: "Модель сейчас не готова",
  launch_route_pending: "Безопасный маршрут запуска ещё подключается",
  selection_required: "Сначала выберите модель",
  ratio_unsupported: "Не поддерживает текущее соотношение сторон",
  resolution_unsupported: "Не поддерживает текущее разрешение",
  reference_video_unsupported: "Не принимает видео как исходник",
  first_frame_unsupported: "Не принимает главный кадр",
  last_frame_unsupported: "Не принимает финальный кадр",
  last_frame_duration_unsupported: "Финальный кадр доступен только для указанной моделью длительности",
});

const MODEL_REASON_COPY = Object.freeze({
  content_kind_match: "подходит для выбранного типа результата",
  input_mode_match: "работает с текущим типом исходника",
  duration_supported: "поддерживает выбранную длительность",
  ratio_supported: "подходит для текущего формата кадра",
  resolution_supported: "поддерживает выбранное разрешение",
  audio_supported: "может создать звук вместе с роликом",
  spoken_dialogue_supported: "подходит для речи и диалога",
  reference_images_supported: "принимает выбранные ракурсы товара",
  reference_video_supported: "принимает готовое видео как исходник",
  first_frame_supported: "точный главный кадр можно зафиксировать",
  last_frame_supported: "можно зафиксировать финальный кадр",
  within_budget: "укладывается в текущий лимит кампании",
  accepted_output_evidence: "есть принятый реальный результат и независимая проверка",
  research_recommendation_match: "совпадает с утверждённой рекомендацией исследования",
  performance_recommendation_match: "подтверждается результатами прошлого контента",
  intent_fast_draft_fit: "подходит для быстрого черновика",
  intent_economy_fit: "экономно использует бюджет",
  intent_premium_quality_fit: "подходит для сложного финального визуала",
  intent_audio_fit: "подходит для сцены со звуком",
  intent_dialogue_fit: "подходит для UGC с речью",
  intent_source_video_fit: "подходит для вариации готового видео",
  intent_product_reference_fit: "сохраняет связь с точным кадром товара",
  provider_model_ready: "предварительная техническая готовность подтверждена",
});

const MODEL_WARNING_COPY = Object.freeze({
  readiness_unknown: "техническая готовность ещё не проверена",
  cost_estimate_unavailable: "точную цену должен подтвердить сервер",
  model_unproven: "модель ещё не принята по реальному результату",
  acceptance_stale: "прежнее подтверждение качества устарело",
  accepted_output_not_compatible: "принятый ранее результат не совпадает с текущими условиями",
  experimental_model: "модель пока экспериментальная",
  preview_model: "модель находится в preview",
  no_compatible_model: "для текущих условий нет полностью совместимой модели",
});

const SELECTION_SOURCE_COPY = Object.freeze({
  manual: "Выбрано вручную",
  accepted_recommendation: "Технический подбор принят",
  system_recommendation: "Системный технический подбор",
  form_default: "Текущий режим формы",
});

const QUALITY_LABELS = Object.freeze({
  economy: "Экономно",
  balanced: "Сбалансировано",
  premium: "Лучшее качество",
});

const SPEED_LABELS = Object.freeze({
  fast: "быстро",
  normal: "обычно",
  slow: "медленнее",
});

const COST_TIER_LABELS = Object.freeze({
  economy: "низкая стоимость",
  balanced: "средняя стоимость",
  premium: "высокая стоимость",
});

const MODEL_FILTERS = Object.freeze([
  ["relevant", "Для вас"],
  ["all", "Все модели"],
  ["economy", "Экономно"],
  ["balanced", "Сбалансировано"],
  ["premium", "Лучшее качество"],
  ["experimental", "Экспериментально"],
]);

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function element(tagName, className = "", text = "") {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function modelKey(value) {
  const provider = String(value?.provider || "").trim();
  const model = String(value?.model || "").trim();
  return provider && model ? `${provider}:${model}` : "";
}

function modelIdentityForMode(mode) {
  const identity = LEGACY_MODEL_BY_MODE[String(mode || "").trim()];
  return identity ? { ...identity } : null;
}

function modeForModel(value, form = null) {
  const legacy = LEGACY_MODE_BY_MODEL[modelKey(value)];
  if (legacy) return legacy;
  if (value?.contentKind === "photo") return "real_photo";
  if (value?.contentKind !== "video") return "";
  const exactAudio = modelKey(value) === modelKey(selectedModelForForm(form))
    ? String(form?.elements?.generation_audio?.value || "")
    : "";
  const audio = exactAudio === "true"
    ? true
    : exactAudio === "false"
      ? false
      : value?.selectionDefaults?.audio === true;
  return audio ? "real_seedance" : "real_gen4";
}

function canonicalSelectionSource(state = runtime.recommendationState) {
  const source = String(state?.selectionSource || "").trim();
  if (source === "alternative_after_block") return "alternative_after_block";
  if (source !== "accepted_recommendation") return "manual_choice";
  const provenance = String(
    state?.recommendation?.source
      || state?.recommendation?.provenance
      || runtime.catalogSignals?.recommendation_source
      || "",
  ).trim().toLowerCase();
  if (provenance.includes("research")) return "research_recommendation";
  if (provenance.includes("performance")) return "performance_recommendation";
  return "system_recommendation";
}

function modelCanUseExistingLaunch(form, model) {
  const mode = modeForModel(model, form);
  const select = form?.elements?.generation_mode;
  return Boolean(
    model?.enabled === true
    && model?.executionSupported === true
    && model?.launchEnabled === true
    && mode
    && select instanceof HTMLSelectElement
    && [...select.options].some((option) => option.value === mode && !option.disabled),
  );
}

function modelContentKind(form) {
  const mode = String(form?.elements?.generation_mode?.value || "");
  if (mode === "real_photo") return "photo";
  if (["real_seedance", "real_gen4"].includes(mode)) return "video";
  return null;
}

function selectedModelForForm(form) {
  const provider = String(form?.elements?.generation_provider?.value || "").trim();
  const model = String(form?.elements?.generation_model_id?.value || "").trim();
  if (provider && model) return { provider, model };
  return modelIdentityForMode(form?.elements?.generation_mode?.value);
}

function acceptanceSignals() {
  const snapshot = window.ContentEngineWorkspaceRuntime?.getGenerationModelAcceptance?.();
  const normalized = snapshot?.normalized
    || normalizeGenerationModelAcceptance(snapshot?.data, runtime.catalog);
  return Object.fromEntries(
    normalized.models.map((item) => [
      modelKey(item),
      Object.freeze({
        status: item.status,
        reasonCode: item.reasonCode,
        nextActionCode: item.nextActionCode,
        successfulRuns: item.successfulRuns,
        reviewedRuns: item.reviewedRuns,
        acceptedRuns: item.acceptedRuns,
        pendingReviewRuns: item.pendingReviewRuns,
        evidence: item.evidence,
        pendingReview: item.pendingReview,
      }),
    ]),
  );
}

function signalRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function exactSignal(map, identity) {
  const key = typeof identity === "string" ? identity : modelKey(identity);
  return key && Object.prototype.hasOwnProperty.call(signalRecord(map), key)
    ? map[key]
    : undefined;
}

function exactProviderSignal(map, provider) {
  const key = String(provider || "").trim();
  return key && Object.prototype.hasOwnProperty.call(signalRecord(map), key)
    ? map[key]
    : undefined;
}

function preflightSignal(form, identity) {
  if (modelKey(identity) !== modelKey(selectedModelForForm(form))) return undefined;
  const status = q("#runway-readiness-status", form);
  if (!status) return undefined;
  if (status.dataset.status === "ready") {
    return { ready: true, status: "fresh", freshness: "fresh" };
  }
  if (status.dataset.status === "error") {
    return { ready: false, status: "not_ready", reasonCode: "provider_not_ready" };
  }
  return undefined;
}

function modelContext(form) {
  const mode = String(form?.elements?.generation_mode?.value || "");
  const repeated = runtime.repeatSettings;
  const repeatedModel = repeated
    ? runtime.catalog?.models?.find((entry) => modelKey(entry) === modelKey(repeated))
    : null;
  const contentKind = repeatedModel?.contentKind || modelContentKind(form);
  const rawDuration = Number(form?.elements?.duration_seconds?.value || 0);
  const selectedMedia = qa('input[name="media_id"]:checked:not(:disabled)', form).length;
  const format = String(form?.elements?.format?.value || "").trim();
  const brief = String(form?.elements?.brief?.value || "").trim().toLowerCase();
  const speechRequested = /(?:реплик|говорит|речь|диалог|голос|озвуч)/u.test(brief);
  const personRequested = speechRequested || /(?:\bugc\b|блогер|человек|герой|лицо)/u.test(brief);
  const sourceVideoRequested = repeated?.inputMode === "video" || Boolean(
    String(form?.elements?.generation_reference_url?.value || "").trim(),
  );
  const currentIdentity = selectedModelForForm(form);
  const currentModelKey = modelKey(currentIdentity);
  const referenceBundle = [
    "runway:seedream5_lite",
    "runway:seedance2_fast",
    "runway:seedance2_mini",
  ].includes(currentModelKey);
  const selectedAudio = String(form?.elements?.generation_audio?.value || "");
  const selectedResolution = String(form?.elements?.generation_resolution?.value || "").trim();
  const selectedLastFrame = form?.elements?.generation_last_frame?.checked === true;
  const currentPreflight = preflightSignal(form, currentIdentity);
  const readiness = { ...signalRecord(runtime.catalogSignals?.readiness) };
  if (currentPreflight && currentIdentity) readiness[modelKey(currentIdentity)] = currentPreflight;
  (runtime.catalog?.models || []).forEach((model) => {
    if (!modelCanUseExistingLaunch(form, model)) {
      readiness[modelKey(model)] = {
        ready: false,
        status: "blocked",
        reasonCode: "launch_route_pending",
      };
    }
  });
  const intents = contentKind === "photo"
    ? ["product_image"]
    : contentKind === "video" && sourceVideoRequested
      ? ["source_video_variation"]
      : contentKind === "video" && speechRequested
        ? ["ugc", "dialogue"]
        : contentKind === "video" && personRequested
          ? ["ugc"]
          : contentKind === "video"
            ? ["product_motion"]
            : [];
  return {
    contentKind,
    intents,
    inputMode: repeated?.inputMode || (selectedMedia > 0 ? "image" : "text"),
    referenceImageCount: repeated?.referenceCount !== null
      && repeated?.referenceCount !== undefined
      && Number.isInteger(Number(repeated.referenceCount))
      ? Math.max(0, Number(repeated.referenceCount))
      : referenceBundle
        ? selectedMedia
        : 0,
    referenceVideo: repeated?.inputMode === "video",
    firstFrame: typeof repeated?.firstFrame === "boolean"
      ? repeated.firstFrame
      : contentKind === "video" && selectedMedia > 0 && !referenceBundle,
    lastFrame: typeof repeated?.lastFrame === "boolean"
      ? repeated.lastFrame
      : selectedLastFrame,
    durationSeconds: contentKind === "photo"
      ? 0
      : Number.isFinite(Number(repeated?.durationSeconds)) && Number(repeated.durationSeconds) > 0
        ? Number(repeated.durationSeconds)
        : Number.isFinite(rawDuration) && rawDuration > 0
        ? rawDuration
        : null,
    ratio: /^\d+:\d+$/u.test(String(repeated?.ratio || ""))
      ? String(repeated.ratio)
      : /^\d+:\d+$/u.test(format)
      ? format
      : contentKind === "photo"
        ? "1:1"
        : null,
    resolution: repeated?.resolution
      ? String(repeated.resolution)
      : selectedResolution
        ? selectedResolution
      : contentKind === "photo" ? "2k" : contentKind === "video" ? "720p" : null,
    audio: speechRequested
      ? true
      : typeof repeated?.audio === "boolean"
        ? repeated.audio
        : selectedAudio === "true"
          ? true
          : selectedAudio === "false"
            ? false
            : null,
    spokenDialogue: repeated?.spokenDialogue === true || speechRequested,
    estimatedCosts: signalRecord(runtime.catalogSignals?.estimatedCosts),
    readiness,
    providerReadiness: signalRecord(runtime.catalogSignals?.providerReadiness),
    acceptance: {
      ...acceptanceSignals(),
      ...signalRecord(runtime.catalogSignals?.acceptance),
    },
    researchRecommendations: runtime.catalogSignals?.researchRecommendations || [],
    performanceRecommendations: runtime.catalogSignals?.performanceRecommendations || [],
    effectiveBudgetMinor: runtime.catalogSignals?.effectiveBudgetMinor ?? null,
    currency: runtime.catalogSignals?.currency || "USD",
  };
}

function recommendationReason(codes = []) {
  const visible = codes
    .map((code) => MODEL_REASON_COPY[String(code || "")] || MODEL_COPY[String(code || "")])
    .filter(Boolean);
  return visible[0] || "Подходит по формату и ограничениям текущего запуска";
}

function translatedList(codes = [], dictionary = MODEL_REASON_COPY, fallbackDictionary = MODEL_COPY) {
  return [...new Set(
    (Array.isArray(codes) ? codes : [])
      .map((code) => dictionary[String(code || "")] || fallbackDictionary[String(code || "")])
      .filter(Boolean),
  )];
}

function plainCatalogCopy(value, fallback) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text || fallback;
}

function firstCatalogCopy(values, fallback) {
  return plainCatalogCopy(Array.isArray(values) ? values[0] : "", fallback);
}

function modelInputSummary(model) {
  const parts = [];
  if (model.inputModes?.includes("image")) {
    const imageOnly = model.inputModes.length === 1;
    parts.push(imageOnly
      ? "Нужно фото"
      : model.maxReferenceImages > 0
        ? `Можно до ${model.maxReferenceImages} фото`
        : "Фото можно добавить");
  }
  if (model.inputModes?.includes("video")) parts.push("Принимает готовое видео");
  if (model.inputModes?.includes("text")) parts.push("Можно без исходника");
  return parts.join(" · ") || "Требования к исходнику уточняются";
}

function modelOutputSummary(model) {
  if (model.contentKind === "photo") {
    return `${(model.allowedResolutions || []).join("/") || "фото"} · ${(model.allowedRatios || []).join(", ")} · без звука`;
  }
  const duration = Array.isArray(model.allowedDurations) && model.allowedDurations.length
    ? `${Math.min(...model.allowedDurations)}–${Math.max(...model.allowedDurations)} сек.`
    : "длительность уточняется";
  const audio = model.supportsSpokenDialogue
    ? "с речью"
    : model.supportsGeneratedAudio
      ? "со звуком"
      : "без звука";
  const resolutions = (model.allowedResolutions || []).join("/");
  const allowedRatios = Array.isArray(model.allowedRatios) ? model.allowedRatios : [];
  const ratios = allowedRatios.length > 3
    ? `${allowedRatios.slice(0, 3).join(", ")} +${allowedRatios.length - 3}`
    : allowedRatios.join(", ");
  return [duration, ratios ? `форматы ${ratios}` : "", resolutions, audio].filter(Boolean).join(" · ");
}

function modelCandidate(state, model) {
  const key = modelKey(model);
  const candidates = [
    state?.recommendation?.recommended,
    ...(state?.recommendation?.alternatives || []),
    ...(state?.recommendation?.unavailable || []),
  ];
  return candidates.find((candidate) => modelKey(candidate) === key) || null;
}

function modelUnavailableCodes(state, model) {
  const candidate = modelCandidate(state, model);
  return Array.isArray(candidate?.unavailableReasonCodes)
    ? candidate.unavailableReasonCodes
    : [];
}

function acceptanceStatus(state, model) {
  const signal = exactSignal(state?.context?.acceptance, model);
  if (signal === true) return "accepted";
  if (typeof signal === "string") return signal.trim().toLowerCase();
  return String(signal?.status || "").trim().toLowerCase();
}

function modelQualityState(model, executable, state) {
  if (!executable || model.enabled !== true) return "Недоступно";
  if (model.lifecycle === "experimental" || model.lifecycle === "preview") {
    return "Экспериментально";
  }
  if (["accepted", "approved", "verified"].includes(acceptanceStatus(state, model))) {
    return "Проверено";
  }
  return "Нужна перепроверка";
}

function currentFormEstimateMinor(form, model) {
  if (modelKey(model) !== modelKey(selectedModelForForm(form))) return null;
  const receipt = window.ContentEngineWorkspaceRuntime
    ?.getGenerationProviderReadiness?.();
  const minor = Number(receipt?.estimated_cost_minor);
  return receipt?.ready === true && Number.isSafeInteger(minor) && minor >= 0
    ? minor
    : null;
}

function formatMinor(value, currency = "USD") {
  const minor = Number(value);
  if (!Number.isFinite(minor) || minor < 0) return "";
  if (String(currency || "USD").toUpperCase() === "USD") return `$${(minor / 100).toFixed(2)}`;
  return `${(minor / 100).toFixed(2)} ${String(currency).toUpperCase()}`;
}

function modelCostPresentation(form, model, state) {
  const candidate = modelCandidate(state, model);
  if (
    candidate?.estimatedCostMinor !== null
    && candidate?.estimatedCostMinor !== undefined
    && Number.isFinite(Number(candidate.estimatedCostMinor))
  ) {
    return {
      text: `${formatMinor(candidate.estimatedCostMinor, state?.context?.currency)} · оценка сервера`,
      minor: Number(candidate.estimatedCostMinor),
      source: "server",
    };
  }
  const formEstimate = currentFormEstimateMinor(form, model);
  if (formEstimate !== null) {
    return {
      text: `около ${formatMinor(formEstimate)} · сервер подтвердит до оплаты`,
      minor: formEstimate,
      source: "server_preflight",
    };
  }
  return {
    text: "рассчитает сервер после выбора параметров",
    minor: null,
    source: "missing",
  };
}

function signalReadiness(value) {
  if (value === true) return "ready";
  if (value === false) return "blocked";
  if (typeof value === "string") {
    const status = value.trim().toLowerCase();
    if (["ready", "fresh", "available"].includes(status)) return "ready";
    if (["blocked", "disabled", "down", "not_ready", "offline", "unavailable"].includes(status)) return "blocked";
    return "unknown";
  }
  if (!value || typeof value !== "object") return "unknown";
  if (value.ready === true || value.available === true || ["ready", "fresh"].includes(String(value.status || "").toLowerCase())) return "ready";
  if (value.ready === false || value.available === false || ["blocked", "disabled", "down", "not_ready", "offline", "unavailable"].includes(String(value.status || "").toLowerCase())) return "blocked";
  return "unknown";
}

function modelReadinessPresentation(form, model, state, executable) {
  if (!executable) {
    return { state: "blocked", text: "Маршрут запуска ещё не подключён" };
  }
  const modelSignal = exactSignal(state?.context?.readiness, model) ?? preflightSignal(form, model);
  const providerSignal = exactProviderSignal(state?.context?.providerReadiness, model.provider);
  const exact = signalReadiness(modelSignal);
  const provider = signalReadiness(providerSignal);
  if (exact === "blocked" || provider === "blocked") {
    return { state: "blocked", text: "Техническая готовность не подтверждена" };
  }
  if (exact === "ready" && (provider === "ready" || provider === "unknown")) {
    return { state: "ready", text: "Предварительно готово · перед оплатой проверится снова" };
  }
  return { state: "unknown", text: "Проверится бесплатно перед платным запуском" };
}

function numberedHeading(number, title, hint = "", level = 4) {
  const header = element("header", "ce-v4-model-section-heading");
  header.append(
    element("span", "ce-v4-model-section-heading__number", String(number).padStart(2, "0")),
    element("div", "ce-v4-model-section-heading__copy"),
  );
  const copy = q(".ce-v4-model-section-heading__copy", header);
  copy.append(element(level === 5 ? "h5" : "h4", "", title));
  if (hint) copy.append(element("p", "", hint));
  return header;
}

function createContentKindChooser() {
  const section = element("section", "ce-v4-model-kind");
  section.dataset.ceV4ModelKind = "";
  section.append(numberedHeading(
    1,
    "Что создаём?",
    "Сначала выберите результат. Точную модель можно выбрать ниже.",
  ));
  const choices = element("div", "ce-v4-model-kind__choices");
  choices.setAttribute("role", "group");
  choices.setAttribute("aria-label", "Тип результата");
  [
    ["video", "Видео", "Товар в движении, UGC, речь или вариация"],
    ["photo", "Фото товара", "Точный кадр по фото или тексту"],
  ].forEach(([kind, title, hint]) => {
    const button = element("button", "ce-v4-model-kind__choice");
    button.type = "button";
    button.dataset.ceV4ContentKind = kind;
    button.setAttribute("aria-pressed", "false");
    button.append(element("strong", "", title), element("small", "", hint));
    choices.append(button);
  });
  section.append(choices);
  return section;
}

function createBudgetMarker() {
  const marker = element("section", "ce-v4-model-budget-marker");
  marker.dataset.ceV4ModelBudgetMarker = "";
  marker.append(numberedHeading(
    4,
    "Кампания и бюджет",
    "Здесь собраны длительность, кампания, доступный лимит и отдельное согласие на оплату.",
  ));
  return marker;
}

function createSelectionSummary() {
  const section = element("section", "ce-v4-model-selection-summary");
  section.dataset.ceV4ModelSelectionSummary = "";
  section.setAttribute("aria-labelledby", "ce-v4-model-selection-summary-title");
  const heading = numberedHeading(
    5,
    "Точный выбор",
    "Сверьте модель и параметры. Это резюме ничего не запускает.",
  );
  q("h4", heading).id = "ce-v4-model-selection-summary-title";
  const body = element("div", "ce-v4-model-selection-summary__body");
  body.dataset.ceV4ModelSelectionSummaryBody = "";
  section.append(heading, body);
  return section;
}

function hiddenExactControl(name) {
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.dataset.ceV4ExactModelControl = "true";
  return input;
}

function createExactModelSettings() {
  const section = element("section", "ce-v4-model-exact-settings");
  section.dataset.ceV4ModelExactSettings = "";
  section.dataset.provider = "";
  section.dataset.model = "";
  section.dataset.contentKind = "";
  section.dataset.profileState = "empty";
  section.hidden = true;
  [
    "generation_provider",
    "generation_model_id",
    "generation_input_mode",
    "generation_content_kind",
    "generation_prompt_limit",
    "generation_catalog_version",
    "generation_pricing_version",
    "generation_selection_source",
    "generation_launch_enabled",
  ].forEach((name) => section.append(hiddenExactControl(name)));

  const header = element("header", "ce-v4-model-exact-settings__header");
  const headerCopy = element("div", "ce-v4-model-exact-settings__header-copy");
  headerCopy.append(
    element("p", "ce-v4-model-exact-settings__eyebrow", "ПРОФИЛЬ ВЫБРАННОЙ МОДЕЛИ"),
    element("h4", "ce-v4-model-exact-settings__title", "Модель не выбрана"),
  );
  const authority = element(
    "span",
    "ce-v4-model-exact-settings__authority",
    "Авторитет: серверный каталог",
  );
  const visualSlot = element("div", "ce-v4-model-exact-settings__visual-slot");
  visualSlot.dataset.ceV4ModelExactVisual = "";
  visualSlot.hidden = true;
  visualSlot.setAttribute("aria-hidden", "true");
  header.append(headerCopy, visualSlot, authority);

  const grid = element("div", "ce-v4-model-exact-settings__grid");
  const resolutionField = element("label", "field");
  resolutionField.append(element("span", "", "Разрешение"));
  const resolution = document.createElement("select");
  resolution.name = "generation_resolution";
  resolution.required = true;
  resolutionField.append(resolution, element("small", "field-hint", "Доступные варианты задаёт выбранная модель."));

  const audioField = element("label", "field");
  audioField.append(element("span", "", "Звук"));
  const audio = document.createElement("select");
  audio.name = "generation_audio";
  audio.required = true;
  audioField.append(audio, element("small", "field-hint", "Если звук обязателен для модели, переключатель будет зафиксирован."));

  const lastFrame = element("label", "option ce-v4-model-exact-settings__last-frame");
  const lastFrameInput = document.createElement("input");
  lastFrameInput.type = "checkbox";
  lastFrameInput.name = "generation_last_frame";
  lastFrame.append(
    lastFrameInput,
    element("span", "", "Использовать второе выбранное фото как точный финальный кадр"),
  );
  grid.append(resolutionField, audioField, lastFrame);
  const capabilityStatus = element(
    "p",
    "ce-v4-model-exact-settings__status",
    "Параметры проверяются по точным возможностям выбранной модели.",
  );
  capabilityStatus.dataset.ceV4ModelCapabilityStatus = "";
  capabilityStatus.setAttribute("role", "status");
  section.append(header, grid, capabilityStatus);
  return section;
}

function replaceOptions(control, values, selectedValue, label = (value) => String(value)) {
  if (!(control instanceof HTMLSelectElement)) return "";
  const unique = [...new Set((Array.isArray(values) ? values : []).map(String).filter(Boolean))];
  const selected = unique.includes(String(selectedValue || ""))
    ? String(selectedValue)
    : unique[0] || "";
  control.replaceChildren(...unique.map((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label(value);
    option.selected = value === selected;
    return option;
  }));
  return selected;
}

function exactDefaults(model) {
  const defaults = model?.selectionDefaults && typeof model.selectionDefaults === "object"
    ? model.selectionDefaults
    : {};
  return {
    inputMode: String(defaults.inputMode || "image"),
    durationSeconds: Number(defaults.durationSeconds),
    format: String(defaults.format || model?.allowedRatios?.[0] || ""),
    resolution: String(defaults.resolution || model?.allowedResolutions?.[0] || ""),
    audio: defaults.audio === true,
    lastFrame: defaults.lastFrame === true,
  };
}

function imageCapability(model) {
  const capability = model?.inputCapabilities?.image;
  return capability && typeof capability === "object" && !Array.isArray(capability)
    ? capability
    : null;
}

function exactCapabilityOptions(model, { resolution = "", lastFrame = false } = {}) {
  const capability = imageCapability(model);
  const allowedRatios = Array.isArray(capability?.allowedRatios)
    ? capability.allowedRatios
    : model?.allowedRatios;
  const allowedResolutions = Array.isArray(capability?.allowedResolutions)
    ? capability.allowedResolutions
    : model?.allowedResolutions;
  const resolutionDurations = capability?.allowedDurationsByResolution?.[resolution];
  let allowedDurations = Array.isArray(resolutionDurations)
    ? resolutionDurations
    : model?.allowedDurations;
  const lastFrameDuration = Number(capability?.lastFrameDurationSeconds);
  if (lastFrame && Number.isSafeInteger(lastFrameDuration)) {
    allowedDurations = (Array.isArray(allowedDurations) ? allowedDurations : [])
      .filter((value) => Number(value) === lastFrameDuration);
  }
  return {
    capability,
    allowedRatios: Array.isArray(allowedRatios) ? allowedRatios : [],
    allowedResolutions: Array.isArray(allowedResolutions) ? allowedResolutions : [],
    allowedDurations: Array.isArray(allowedDurations) ? allowedDurations : [],
    lastFrameSupported: capability?.supportsLastFrame === true
      && model?.lastFrameSupported === true,
    lastFrameDuration: Number.isSafeInteger(lastFrameDuration)
      ? lastFrameDuration
      : null,
  };
}

function syncExactModelControls(form, model, { emit = false } = {}) {
  const section = q("[data-ce-v4-model-exact-settings]", form);
  if (!section) return false;
  if (!model) {
    section.dataset.provider = "";
    section.dataset.model = "";
    section.dataset.contentKind = "";
    section.dataset.profileState = "empty";
    delete section.dataset.modelFamily;
    delete section.dataset.visualTone;
    delete section.dataset.generationModelForm;
    section.removeAttribute("aria-label");
    const title = q(".ce-v4-model-exact-settings__title", section);
    const authority = q(".ce-v4-model-exact-settings__authority", section);
    const visualSlot = q("[data-ce-v4-model-exact-visual]", section);
    if (title) title.textContent = "Модель не выбрана";
    if (authority) authority.textContent = "Авторитет: серверный каталог";
    if (visualSlot) {
      visualSlot.replaceChildren();
      visualSlot.hidden = true;
    }
    section.hidden = true;
    qa("[data-ce-v4-exact-model-control]", section).forEach((control) => { control.value = ""; });
    const brief = form.elements?.brief;
    if (brief instanceof HTMLTextAreaElement) {
      brief.maxLength = selectedStrategyRow() ? 800 : 1_200;
      brief.setCustomValidity("");
      delete brief.dataset.generationStrategyForm;
      delete brief.dataset.generationModelForm;
      delete brief.dataset.generationModelPromptLimit;
    }
    return false;
  }
  const previousKey = `${form.elements?.generation_provider?.value || ""}:${form.elements?.generation_model_id?.value || ""}`;
  const nextKey = modelKey(model);
  const sameModel = previousKey === nextKey;
  const defaults = exactDefaults(model);
  section.dataset.provider = String(model.provider || "");
  section.dataset.model = String(model.model || "");
  section.dataset.contentKind = String(model.contentKind || "");
  section.dataset.profileState = "ready";
  section.dataset.generationModelForm = nextKey;
  section.setAttribute(
    "aria-label",
    `Точные параметры модели ${String(model.publicLabel || model.model || nextKey)}`,
  );
  const profileTitle = q(".ce-v4-model-exact-settings__title", section);
  const profileAuthority = q(".ce-v4-model-exact-settings__authority", section);
  const profileVisualSlot = q("[data-ce-v4-model-exact-visual]", section);
  if (profileTitle) {
    profileTitle.textContent = String(model.publicLabel || model.model || "Выбранная модель");
  }
  if (profileAuthority) {
    const catalogVersion = String(runtime.catalog?.version || "").trim();
    profileAuthority.textContent = catalogVersion
      ? `Авторитет: серверный каталог · ${catalogVersion}`
      : "Авторитет: серверный каталог";
  }
  if (profileVisualSlot) {
    profileVisualSlot.replaceChildren();
    const profileVisual = modelVisualNode(model, { featured: true });
    if (profileVisual) {
      profileVisual.classList.add("ce-v4-model-exact-settings__visual-frame");
      section.dataset.modelFamily = profileVisual.dataset.family || "";
      section.dataset.visualTone = profileVisual.dataset.tone || "";
      profileVisualSlot.append(profileVisual);
      profileVisualSlot.hidden = false;
    } else {
      delete section.dataset.modelFamily;
      delete section.dataset.visualTone;
      profileVisualSlot.hidden = true;
    }
  }
  const setHidden = (name, value) => {
    const control = form.elements?.[name];
    if (control instanceof HTMLInputElement) control.value = String(value ?? "");
  };
  setHidden("generation_provider", model.provider);
  setHidden("generation_model_id", model.model);
  setHidden("generation_input_mode", defaults.inputMode);
  setHidden("generation_content_kind", model.contentKind);
  setHidden("generation_prompt_limit", Number(model.promptLimit || 0));
  setHidden("generation_catalog_version", runtime.catalog?.version || "");
  setHidden("generation_pricing_version", model.pricingVersion || "");
  setHidden("generation_selection_source", canonicalSelectionSource());
  setHidden("generation_launch_enabled", modelCanUseExistingLaunch(form, model) ? "true" : "false");
  const promptLimit = Number(model.promptLimit);
  const exactPromptLimit = Number.isSafeInteger(promptLimit) && promptLimit > 0
    ? promptLimit
    : 1_200;
  const brief = form.elements?.brief;
  if (brief instanceof HTMLTextAreaElement) {
    brief.maxLength = exactPromptLimit;
    delete brief.dataset.generationStrategyForm;
    brief.dataset.generationModelForm = nextKey;
    brief.dataset.generationModelPromptLimit = String(exactPromptLimit);
  }

  const resolutionControl = form.elements?.generation_resolution;
  const lastFrameControl = form.elements?.generation_last_frame;
  const requestedResolution = sameModel
    ? resolutionControl?.value
    : defaults.resolution;
  const baseCapability = exactCapabilityOptions(model, {
    resolution: requestedResolution,
    lastFrame: sameModel && lastFrameControl?.checked === true,
  });
  const selectedResolution = replaceOptions(
    resolutionControl,
    baseCapability.allowedResolutions,
    requestedResolution,
  );
  const selectedLastFrame = baseCapability.lastFrameSupported
    && (sameModel ? lastFrameControl?.checked === true : defaults.lastFrame);
  const capability = exactCapabilityOptions(model, {
    resolution: selectedResolution,
    lastFrame: selectedLastFrame,
  });
  const duration = form.elements?.duration_seconds;
  if (duration instanceof HTMLSelectElement) {
    replaceOptions(
      duration,
      capability.allowedDurations,
      sameModel ? duration.value : defaults.durationSeconds,
      (value) => model.contentKind === "photo" ? "Статичное фото" : `${value} секунд`,
    );
  }
  const format = form.elements?.format;
  if (format instanceof HTMLSelectElement) {
    replaceOptions(
      format,
      capability.allowedRatios,
      sameModel ? format.value : defaults.format,
    );
  }
  const audioModes = Array.isArray(model.audioModes) && model.audioModes.length
    ? model.audioModes.map((value) => value === true)
    : [defaults.audio];
  replaceOptions(
    form.elements?.generation_audio,
    audioModes.map(String),
    sameModel ? form.elements?.generation_audio?.value : String(defaults.audio),
    (value) => value === "true" ? "Со звуком" : "Без сгенерированного звука",
  );
  if (form.elements?.generation_audio instanceof HTMLSelectElement) {
    form.elements.generation_audio.disabled = false;
    form.elements.generation_audio.setAttribute(
      "aria-disabled",
      audioModes.length === 1 ? "true" : "false",
    );
  }
  const lastFrame = lastFrameControl;
  const lastFrameField = lastFrame?.closest?.("label");
  if (lastFrame instanceof HTMLInputElement) {
    lastFrame.checked = selectedLastFrame;
    lastFrame.disabled = !capability.lastFrameSupported;
    if (lastFrameField) lastFrameField.hidden = !capability.lastFrameSupported;
  }
  const capabilityStatus = q("[data-ce-v4-model-capability-status]", section);
  if (capabilityStatus) {
    const noExactCombination = model.contentKind !== "photo"
      && capability.allowedDurations.length === 0;
    const promptLength = brief instanceof HTMLTextAreaElement
      ? String(brief.value || "").length
      : 0;
    const promptTooLong = promptLength > exactPromptLimit;
    const profileBlocked = noExactCombination || promptTooLong;
    section.dataset.profileState = profileBlocked ? "blocked" : "ready";
    capabilityStatus.dataset.state = profileBlocked ? "blocked" : "ready";
    capabilityStatus.textContent = promptTooLong
      ? `Инструкция содержит ${promptLength} знаков при лимите ${exactPromptLimit}. Сократите текст — запуск заблокирован.`
      : noExactCombination
      ? "Для этого сочетания разрешения и финального кадра нет допустимой длительности. Измените параметры — запуск заблокирован."
      : capability.lastFrameDuration !== null && selectedLastFrame
        ? `Финальный кадр требует точную длительность ${capability.lastFrameDuration} секунд.`
        : `Показаны только сочетания параметров, разрешённые выбранной моделью. Лимит инструкции — ${exactPromptLimit} знаков.`;
    if (brief instanceof HTMLTextAreaElement) {
      brief.setCustomValidity(
        promptTooLong
          ? `Сократите инструкцию до ${exactPromptLimit} знаков для выбранной модели.`
          : "",
      );
    }
  }
  section.hidden = false;
  if (emit) {
    form.elements.generation_model_id?.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return true;
}

function createModelAdvisor() {
  const section = element("section", "ce-v4-model-advisor");
  section.dataset.ceV4ModelAdvisor = "";
  section.setAttribute("aria-labelledby", "ce-v4-model-advisor-title");

  const header = element("header", "ce-v4-model-advisor__header");
  const copy = element("div", "ce-v4-model-advisor__copy");
  const eyebrow = element("p", "ce-v4-model-advisor__eyebrow", "ТЕХНИЧЕСКИЙ ПОДБОР · РЕШЕНИЕ ЧЕЛОВЕКА");
  const title = element("h4", "", "Технический подбор модели");
  title.id = "ce-v4-model-advisor-title";
  copy.append(
    eyebrow,
    title,
    element(
      "p",
      "",
      "Система сравнивает совместимость, качество, скорость и бюджет по серверному каталогу. Это технический совет: ручной выбор никогда не будет заменён автоматически.",
    ),
  );
  const badge = element("span", "ce-v4-model-advisor__authority", "Вы решаете");
  header.append(copy, badge);

  const status = element("p", "ce-v4-model-advisor__status", "Загружаем доступные модели…");
  status.dataset.ceV4ModelAdvisorStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const recommendation = element("div", "ce-v4-model-advisor__recommendation");
  recommendation.dataset.ceV4ModelRecommendation = "";
  recommendation.hidden = true;

  const recommendationSection = element("section", "ce-v4-model-advisor__section");
  recommendationSection.append(numberedHeading(
    2,
    "Технический подбор модели",
    "Показываем причины, компромисс, цену и готовность до любой оплаты.",
    5,
  ), recommendation);

  const catalogSection = element("section", "ce-v4-model-advisor__section");
  catalogSection.append(numberedHeading(
    3,
    "Модели",
    "Выберите карточку мышью или клавиатурой. Недоступные модели остаются видимы с точной причиной.",
    5,
  ));
  const filters = element("div", "ce-v4-model-advisor__filters");
  filters.dataset.ceV4ModelFilters = "";
  filters.setAttribute("role", "toolbar");
  filters.setAttribute("aria-label", "Показать модели по классу");
  MODEL_FILTERS.forEach(([key, label]) => {
    const button = element("button", "ce-v4-model-advisor__filter", label);
    button.type = "button";
    button.dataset.ceV4ModelFilter = key;
    button.setAttribute("aria-pressed", key === "relevant" ? "true" : "false");
    filters.append(button);
  });
  const list = element("div", "ce-v4-model-advisor__grid");
  list.dataset.ceV4ModelGrid = "";
  list.setAttribute("role", "radiogroup");
  list.setAttribute("aria-label", "Модель генерации");
  catalogSection.append(filters, list);

  section.append(header, status, recommendationSection, catalogSection);
  return section;
}

function ensureModelAdvisor(form) {
  let advisor = q("[data-ce-v4-model-advisor]", form);
  const modeControl = form.elements?.generation_mode;
  const modeField = modeControl?.closest?.("label, .field");
  if (modeField && !q("[data-ce-v4-model-kind]", form)) {
    modeField.before(createContentKindChooser());
    modeField.classList.add("ce-v4-model-native-mode");
  }
  if (!advisor) {
    advisor = createModelAdvisor();
    if (modeField?.parentElement) modeField.after(advisor);
    else contentFor(form, "mode")?.prepend(advisor);
  }
  let exactSettings = q("[data-ce-v4-model-exact-settings]", form);
  if (!exactSettings) {
    exactSettings = createExactModelSettings();
    advisor.after(exactSettings);
  }
  const modeContent = contentFor(form, "mode");
  if (advisor && !q("[data-ce-v4-model-budget-marker]", form)) {
    exactSettings.after(createBudgetMarker());
  }
  if (modeContent && !q("[data-ce-v4-model-selection-summary]", form)) {
    modeContent.append(createSelectionSummary());
  }
  return advisor;
}

function extractedStrategyCatalog(catalog) {
  return {
    version: catalog?.strategyCatalogVersion,
    recipe_version: catalog?.strategyRecipeVersion,
    pricing_version: catalog?.strategyPricingVersion,
    strategies: catalog?.strategies,
  };
}

function generationStrategyCatalogFailure(error) {
  const rawCode = typeof error?.code === "string" ? error.code.trim() : "";
  const code = /^[a-z0-9_]{3,96}$/u.test(rawCode)
    ? rawCode
    : "catalog_unavailable";
  const rawField = typeof error?.field === "string" ? error.field.trim() : "";
  const field = rawField && rawField.length <= 500 &&
      /^[a-z0-9_.\[\]-]+$/u.test(rawField)
    ? rawField
    : "catalog";
  const rawMessage = typeof error?.message === "string" ? error.message : "";
  const message = rawMessage
    .replace(/[\u0000-\u001f\u007f]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 300) || "Catalog request failed";
  return Object.freeze({ code, field, message });
}

function selectedStrategyRow() {
  const strategyId = runtime.strategyState?.selected_strategy_id;
  if (!strategyId) return null;
  return runtime.strategyState?.catalog?.strategies?.find(
    (entry) => entry.strategy_id === strategyId,
  ) || null;
}

const STRATEGY_ASSET_CONTROL_BY_ROLE = Object.freeze({
  source_video: "generation_strategy_source_video_id",
  avatar_image: "generation_strategy_avatar_media_id",
  original_product_image: "generation_strategy_original_product_media_id",
});

// Фото товара — единственная роль, которая собирается чекбоксами, а не селектом,
// поэтому её нет в STRATEGY_ASSET_CONTROL_BY_ROLE. Имя роли зависит от стратегии:
// «Копия» заменяет товар (new_product_image), остальные его показывают
// (product_image).
const STRATEGY_PRODUCT_ROLES = Object.freeze([
  "new_product_image",
  "product_image",
]);

function strategyProductRole(row) {
  const roleIds = new Set((row?.asset_roles || []).map((role) => role.role));
  return STRATEGY_PRODUCT_ROLES.find((role) => roleIds.has(role)) || "";
}

// Маршрут — часть готовности, а не деталь исполнения. У стратегии без единого
// включённого маршрута сервер запуск не подпишет, поэтому зелёная отметка
// обещала бы то, чего не будет.
//
// Отсутствие САМОГО поля publishedRoutes — это «сервер не публикует реестр», а
// не «маршрутов нет»: поле каталога необязательное, и старая версия сервера его
// не отдаёт вовсе. Решать по маршрутам в этом случае нельзя — иначе на первом же
// таком ответе заблокировали бы и работающую «Копию».
function strategyRouteUnavailable(publishedRoutes, strategyId) {
  if (!publishedRoutes || typeof publishedRoutes !== "object") return false;
  const routes = publishedRoutes[strategyId];
  if (!Array.isArray(routes)) return true;
  return !routes.some((route) => route?.enabled === true);
}

// Роль, которую форма собрать не умеет, — это не «необязательная роль», а пробел
// формы. Раньше такие роли молча выпадали из проверки: фильтр требовал записи в
// карте контролов, а роли товара собираются чекбоксами и в карту не попадают.
// Молчание здесь означало зелёное «готово» и отказ сервера после всей подготовки.
function strategyUnsupportedRequiredRoles(assetRoles) {
  return (assetRoles || []).filter((role) => (
    role?.role !== "source_video"
    && !STRATEGY_ASSET_CONTROL_BY_ROLE[role?.role]
    && !STRATEGY_PRODUCT_ROLES.includes(role?.role)
    && Number(role?.min_count) > 0
  ));
}

// Какие фото товара реально уйдут в наряд. Один источник правды для сборщика
// ассетов и для расчёта готовности: пока проверка готовности считала иначе (а
// точнее — не считала вовсе), модуль показывал «готово» там, где сервер отказал
// бы по составу ассетов.
//
// Во время setFormBusy все контролы выключены, поэтому смотрим на исходное
// состояние — иначе выбранные фото «исчезали» бы из точного контекста прямо во
// время привязки.
function strategySelectedProductInputs(form) {
  const busyLocked = form?.dataset?.busy === "true";
  return qa('input[name="media_id"]:checked', form).filter((input) => {
    const effectivelyDisabled = busyLocked
      ? input.dataset.wasDisabled === "true"
      : input.disabled;
    return !effectivelyDisabled;
  });
}

const STRATEGY_ASSET_EMPTY_COPY = Object.freeze({
  source_video: "Выберите сохранённый MP4 с подтверждёнными правами",
  avatar_image: "Выберите creator reference с согласием на внешность",
  original_product_image: "Выберите creator reference исходного товара",
});

const STRATEGY_ASSET_BLOCKER_COPY = Object.freeze({
  server_duration_probe_required: "нужна бесплатная серверная проверка длительности MP4",
  target_product_identity_required: "нет проверенной привязки к товару",
  strategy_role_not_eligible: "файл не подходит для этой роли",
  asset_contract_invalid: "сервер не подтвердил пригодность файла",
});

const STRATEGY_MECHANICS_FIELDS = Object.freeze([
  Object.freeze({
    key: "hook",
    label: "Хук в первые секунды",
    hint: "20–160 знаков: что сразу останавливает внимание.",
    min: 20,
    max: 160,
  }),
  Object.freeze({
    key: "beat_sequence",
    label: "Последовательность битов",
    hint: "2–6 разных шагов, один шаг в строке (12–120 знаков).",
    min: 25,
    max: 725,
    multiline: true,
  }),
  Object.freeze({
    key: "pacing",
    label: "Темп и ритм",
    hint: "8–100 знаков.",
    min: 8,
    max: 100,
  }),
  Object.freeze({
    key: "camera_language",
    label: "Камера и движение",
    hint: "8–100 знаков.",
    min: 8,
    max: 100,
  }),
  Object.freeze({
    key: "composition",
    label: "Композиция и место товара",
    hint: "8–100 знаков.",
    min: 8,
    max: 100,
  }),
  Object.freeze({
    key: "audio_pattern",
    label: "Рисунок звука",
    hint: "8–100 знаков: тишина, речь, акценты, ритм.",
    min: 8,
    max: 100,
  }),
  Object.freeze({
    key: "cta_pattern",
    label: "Финал и призыв к действию",
    hint: "8–100 знаков: чем ролик заканчивается и что зритель должен сделать. Например: «финальный кадр с тарелкой и призыв попробовать дома».",
    min: 8,
    max: 100,
  }),
]);

// Стандартная заготовка механики «Создания»: нейтральная операторика без
// продающих обещаний. Оператор видит поля заполненными, правит под ролик, а
// точный prompt читает и одобряет перед оплатой (владелец 25.08.2026: «форма
// как Копия» — шесть пустых обязательных полей превращали экран в космолёт).
const STRATEGY_MECHANICS_DEFAULTS = Object.freeze({
  hook: "Товар появляется в кадре с первой секунды — крупно и чётко.",
  beat_sequence: "Крупный план товара с плавным движением камеры.\nТовар в использовании: главная польза видна без слов.\nФинальный акцент на товаре целиком.",
  pacing: "Быстрый ритм коротких сцен без пауз.",
  camera_language: "Плавные наезды и крупные планы товара.",
  composition: "Товар в центре внимания каждой сцены.",
  audio_pattern: "Ритмичный фон без речи, акценты на сменах сцен.",
  cta_pattern: "Финальный кадр товара и призыв забрать свой.",
});

function strategyMechanicsDraft(sourceMediaId) {
  const existing = runtime.strategyMechanicsDrafts.get(sourceMediaId);
  if (existing) return existing;
  return Object.fromEntries(STRATEGY_MECHANICS_FIELDS.map(({ key }) => [
    key,
    STRATEGY_MECHANICS_DEFAULTS[key] || "",
  ]));
}

function strategySourceCandidates() {
  const candidates = Array.isArray(runtime.strategyAssetPage?.assets)
    ? runtime.strategyAssetPage.assets
    : [];
  if (!runtime.strategyRegisteredSources.size) return candidates;
  // The overlay contains facts returned by successful register/attach/probe
  // calls. It wins over a catalog page captured just before those calls; a
  // later authoritative page with the verified duration removes the overlay.
  const byId = new Map(candidates.map((candidate) => [candidate.id, candidate]));
  runtime.strategyRegisteredSources.forEach((candidate, mediaId) => {
    byId.set(mediaId, candidate);
  });
  return [...byId.values()];
}

function registeredSourceCandidate(value, previous = null) {
  const mediaId = String(value?.media_id || value?.id || "")
    .trim().toLowerCase();
  if (!STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(mediaId)) return null;
  const filename = String(value?.filename || previous?.filename || "Загруженный ролик")
    .trim();
  if (
    !filename
    || filename.length > 255
    || /[\u0000-\u001f\u007f]/u.test(filename)
  ) return null;
  const requestedDuration = value?.duration_seconds === null
    || value?.duration_seconds === undefined
    ? previous?.duration_seconds ?? null
    : value.duration_seconds;
  const numericDuration = requestedDuration === null || requestedDuration === undefined
    ? null
    : Number(requestedDuration);
  if (
    numericDuration !== null
    && (!Number.isFinite(numericDuration) || numericDuration <= 0 || numericDuration > 3_600)
  ) return null;
  const duration = numericDuration === null ? null : numericDuration;
  const ready = duration !== null;
  return Object.freeze({
    id: mediaId,
    kind: "source_video",
    mime_type: "video/mp4",
    duration_seconds: duration,
    status: "ready",
    rights_confirmed: true,
    filename,
    exact_youtube_attached: false,
    direct_mp4_attached: true,
    eligible: ready,
    // Прямой MP4 — исходник обеих одноисходниковых стратегий. До 23.08.2026
    // оверлей объявлял его только для «Копии», и «Дуэт» не видел только что
    // загруженный ролик в списке исходников: «Выбрано 0 из 1» сразу после
    // успешной загрузки.
    eligible_strategy_roles: Object.freeze(ready
      ? [
        Object.freeze({ strategy_id: "viral_product_swap", role: "source_video" }),
        Object.freeze({ strategy_id: "viral_avatar_ugc", role: "source_video" }),
      ]
      : []),
    blocking_codes_by_strategy: Object.freeze({
      viral_avatar_ugc: Object.freeze(ready
        ? []
        : ["server_duration_probe_required"]),
      viral_product_swap: Object.freeze(ready
        ? []
        : ["server_duration_probe_required"]),
      viral_rebuild: Object.freeze([]),
    }),
  });
}

function upsertRegisteredStrategySource(value) {
  const projectId = generationStrategyProjectId();
  if (!STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(projectId)) return null;
  if (runtime.strategyRegisteredSourceProjectId !== projectId) {
    runtime.strategyRegisteredSourceProjectId = projectId;
    runtime.strategyRegisteredSources.clear();
  }
  const mediaId = String(value?.media_id || value?.id || "")
    .trim().toLowerCase();
  const candidate = registeredSourceCandidate(
    value,
    runtime.strategyRegisteredSources.get(mediaId),
  );
  if (!candidate) return null;
  runtime.strategyRegisteredSources.set(candidate.id, candidate);
  return candidate;
}

// A catalog row may lag behind the direct-MP4 attachment RPC: it can already
// know the duration while still omitting the attachment/role facts required by
// the source picker. Such a partial row must not evict the project-scoped
// handoff overlay, otherwise the same registered MP4 immediately becomes
// "0 из 1". The catalog wins only when it independently proves the complete
// Product Swap source contract; the paid preflight still revalidates it.
function catalogConfirmsRegisteredStrategySource(catalogSource, mediaId) {
  if (
    !catalogSource
    || catalogSource.id !== mediaId
    || catalogSource.kind !== "source_video"
    || catalogSource.mime_type !== "video/mp4"
    || catalogSource.status !== "ready"
    || catalogSource.rights_confirmed !== true
    || (
      catalogSource.exact_youtube_attached !== true
      && catalogSource.direct_mp4_attached !== true
    )
    || !Number.isFinite(catalogSource.duration_seconds)
  ) return false;
  return generationStrategyAssetEligibility(
    catalogSource,
    "viral_product_swap",
    "source_video",
  ).eligible === true;
}

function registeredSourceFromHiddenHandoff(form) {
  const read = (name) => String(form?.elements?.[name]?.value || "");
  if (!read("generation_intake_version").trim()) return null;
  if (read("generation_intake_route").trim() !== "copy_video") return null;
  const sourceMediaId = read("generation_intake_source_media_id")
    .trim().toLowerCase();
  if (!STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(sourceMediaId)) return null;
  let assets;
  try {
    assets = JSON.parse(read("generation_strategy_prefill_assets") || "[]");
  } catch {
    return null;
  }
  if (!Array.isArray(assets)) return null;
  const sources = assets.filter((asset) => asset?.role === "source_video");
  if (
    sources.length !== 1
    || String(sources[0]?.media_id || "").trim().toLowerCase() !== sourceMediaId
  ) return null;
  const topDurationRaw = read("generation_intake_source_duration_seconds").trim();
  const assetDurationRaw = sources[0]?.duration_seconds;
  const topDuration = topDurationRaw ? Number(topDurationRaw) : null;
  const assetDuration = assetDurationRaw === null || assetDurationRaw === undefined
    || String(assetDurationRaw).trim() === ""
    ? null
    : Number(assetDurationRaw);
  const duration = Number.isFinite(topDuration)
    && Number.isFinite(assetDuration)
    && topDuration > 0
    && assetDuration > 0
    && topDuration <= 3_600
    && assetDuration <= 3_600
    && Math.ceil(topDuration) === Math.ceil(assetDuration)
    ? assetDuration
    : null;
  return Object.freeze({
    media_id: sourceMediaId,
    filename: "Загруженный ролик",
    duration_seconds: duration,
  });
}

function registeredSourceFromIntakeHandoff(handoff) {
  if (!handoff || handoff.route !== "copy_video") return null;
  const sourceMediaId = String(handoff.source_media_id || "")
    .trim().toLowerCase();
  if (!STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(sourceMediaId)) return null;
  const sources = Array.isArray(handoff.assets)
    ? handoff.assets.filter((asset) => asset?.role === "source_video")
    : [];
  if (
    sources.length !== 1
    || String(sources[0]?.media_id || "").trim().toLowerCase() !== sourceMediaId
  ) return null;
  const topDuration = handoff.source_duration_seconds;
  const assetDuration = sources[0]?.duration_seconds;
  const duration = Number.isFinite(topDuration)
    && Number.isFinite(assetDuration)
    && topDuration > 0
    && assetDuration > 0
    && topDuration <= 3_600
    && assetDuration <= 3_600
    && Math.ceil(topDuration) === Math.ceil(assetDuration)
    ? assetDuration
    : null;
  return Object.freeze({
    media_id: sourceMediaId,
    filename: "Загруженный ролик",
    duration_seconds: duration,
  });
}

function hydrateRegisteredSourceFromHiddenHandoff(form) {
  // A patch-render can replace the entire form after persistHandoff wrote its
  // hidden inputs. The same project-scoped handoff is also stored in session;
  // use it only when the live form no longer carries the exact paired fields.
  const source = registeredSourceFromHiddenHandoff(form)
    || registeredSourceFromIntakeHandoff(runtime.intakeHandoff);
  if (!source) return false;
  const catalogSource = runtime.strategyAssetPage?.assets?.find(
    (asset) => asset?.id === source.media_id,
  );
  if (catalogConfirmsRegisteredStrategySource(catalogSource, source.media_id)) {
    runtime.strategyRegisteredSources.delete(source.media_id);
    return true;
  }
  return Boolean(upsertRegisteredStrategySource(source));
}

function materializeRegisteredStrategySource(form, value) {
  if (!form?.isConnected) return false;
  const candidate = upsertRegisteredStrategySource(value);
  if (!candidate) return false;
  syncStrategyAssetCandidates(form);
  return true;
}

function confirmRegisteredStrategySourceProbe(form, value) {
  if (!form?.isConnected) return false;
  const mediaId = String(value?.media_id || value?.id || "")
    .trim().toLowerCase();
  const previous = runtime.strategyRegisteredSources.get(mediaId);
  if (!previous) return false;
  const candidate = registeredSourceCandidate({
    media_id: mediaId,
    filename: previous.filename,
    duration_seconds: value?.duration_seconds,
  }, previous);
  if (!candidate || candidate.duration_seconds === null) return false;
  runtime.strategyRegisteredSources.set(mediaId, candidate);
  syncStrategyAssetCandidates(form);
  return true;
}

function syncStrategySourcePickerState(strategyId, { reset = false } = {}) {
  const candidates = strategySourceCandidates();
  if (
    reset
    || !runtime.strategySourcePicker
    || runtime.strategySourcePicker.strategy_id !== strategyId
  ) {
    runtime.strategySourcePicker = createGenerationStrategySourcePicker(
      strategyId,
      candidates,
    );
    runtime.strategyMechanicsDrafts.clear();
    return runtime.strategySourcePicker;
  }
  runtime.strategySourcePicker = reduceGenerationStrategySourcePicker(
    runtime.strategySourcePicker,
    {
      type: GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.replaceCandidates,
      strategy_id: strategyId,
      candidates,
    },
  );
  const retained = new Set(
    runtime.strategySourcePicker?.selected_source_ids || [],
  );
  for (const mediaId of runtime.strategyMechanicsDrafts.keys()) {
    if (!retained.has(mediaId)) runtime.strategyMechanicsDrafts.delete(mediaId);
  }
  return runtime.strategySourcePicker;
}

// Разбор механики референса не нужен только «Копии»: она правит сам ролик,
// и сцена доезжает до провайдера целиком. «Дуэту» разбор НУЖЕН (миграция
// 202608220006): модель ведущего исходное видео не получает, и всё, что он
// скажет о ролике, приходит текстом — разбор и есть материал для речи.
const MECHANICS_FREE_STRATEGIES = new Set(["viral_product_swap"]);

function strategyMechanicsEditor(source, strategyId, position, requiredCount) {
  const article = element("article", "generation-strategy-source-review");
  article.dataset.generationStrategySourceReview = source.source_media_id;
  const details = document.createElement("details");
  details.open = position === 1;
  const summary = document.createElement("summary");
  summary.textContent = `${position}. ${source.filename}`;
  details.append(summary);
  const copy = element(
    "p",
    "muted tiny",
    strategyId === "viral_product_swap"
      ? "Этот MP4 передаётся в recipe как исходная сцена. Движение, кадр и тайминг сохраняются в пределах возможностей сервиса; текстовый пересказ не подменяет видео."
      : strategyId === "viral_avatar_ugc"
        ? "Этот MP4 остаётся нетронутым фоном дуэта: ведущий проекта комментирует его из угла кадра."
        : "Этот MP4 остаётся референсом механики: мы создадим новый ролик с вашими ассетами, а не копию кадр в кадр.",
  );
  details.append(copy);
  if (!MECHANICS_FREE_STRATEGIES.has(strategyId)) {
    const draft = strategyMechanicsDraft(source.source_media_id);
    const fields = element("div", "generation-strategy-mechanics-grid");
    STRATEGY_MECHANICS_FIELDS.forEach((field) => {
      const label = element("label", "field");
      label.append(element("span", "", field.label));
      const control = document.createElement("textarea");
      control.rows = field.multiline ? 4 : 2;
      control.required = true;
      control.minLength = field.min;
      control.maxLength = field.max;
      control.value = String(draft[field.key] || "");
      control.dataset.generationStrategyMechanicsField = field.key;
      control.dataset.generationStrategySourceMediaId = source.source_media_id;
      control.name = `generation_strategy_mechanics_${position}_${field.key}`;
      control.setAttribute(
        "aria-label",
        `${field.label} · ролик ${position} из ${requiredCount} · ${source.filename}`,
      );
      label.append(control, element("small", "field-hint", field.hint));
      fields.append(label);
    });
    details.append(fields);
  }
  article.append(details);
  return article;
}

function renderStrategySourcePicker(form, { reset = false } = {}) {
  const root = q("[data-generation-strategy-source-picker]", form);
  const reviews = q("[data-generation-strategy-source-reviews]", form);
  const row = selectedStrategyRow();
  if (!root || !row) return null;
  const picker = syncStrategySourcePickerState(row.strategy_id, { reset });
  const projection = generationStrategySourcePickerProjection(picker);
  root.replaceChildren();
  if (!projection) return null;

  const header = element("div", "generation-strategy-source-picker__header");
  const sourceCopy = row.strategy_id === "viral_product_swap"
    ? "Один MP4 станет исходной сценой Product Swap."
    : row.strategy_id === "viral_avatar_ugc"
      ? "Один MP4 станет фоном дуэта с ведущим."
    : projection.required_count === 1
      ? "Один MP4 станет референсом нового ролика."
      : `Порядок станет порядком ${projection.required_count} независимых роликов.`;
  header.append(
    element(
      "strong",
      "",
      `Выбрано ${projection.selected_count} из ${projection.required_count}`,
    ),
    element("span", "muted tiny", sourceCopy),
  );
  // Массовый режим M1 — только у «Создания»: требование живёт в состоянии
  // пикера, дефолт одиночный (боевой режим 26–29.08), пакет включается этим
  // явным переключателем. Под платным замком режим не меняется: смена
  // ревизии пикера снесла бы очередь с живой платной историей.
  const batchModes = generationStrategySourceCountModes(row.strategy_id);
  if (batchModes.length > 1) {
    const modeBlock = element(
      "div",
      "generation-strategy-source-picker__batch-mode",
    );
    const paidLocked = form.dataset.generationStrategyPaidLocked === "true";
    batchModes.forEach((mode) => {
      const label = element("label", "option");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "generation_strategy_batch_mode";
      input.value = String(mode);
      input.checked = projection.required_count === mode;
      input.disabled = paidLocked;
      input.dataset.generationStrategyBatchMode = String(mode);
      const caption = mode === 1
        ? "Один ролик"
        : `Пакет из ${mode} референс-хитов`;
      const hint = mode === 1
        ? "Одно ТЗ, одна цена, один платный запуск."
        : `${mode} отдельных ТЗ и цен; старты идут строго по одному, каждый со своим подтверждением сервера.`;
      // Тот же паттерн, что у чекбоксов кандидатов ниже: подсказка живёт
      // ВНУТРИ текстового span — три ребёнка в строке label распирали форму
      // на 320/390 (геометрический контракт трёх стратегий).
      const text = element("span", "");
      text.append(
        element("strong", "", caption),
        element("small", "muted", hint),
      );
      label.append(input, text);
      modeBlock.append(label);
    });
    header.append(modeBlock);
  }
  const options = element("div", "generation-strategy-source-picker__options");
  const selectedIds = new Set(projection.selected.map((item) => item.source_media_id));
  picker.candidates.forEach((candidate) => {
    const label = element("label", "option generation-strategy-source-picker__option");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "generation_strategy_source_selection";
    input.value = candidate.id;
    input.checked = selectedIds.has(candidate.id);
    input.disabled =
      !input.checked && projection.selected_count >= projection.required_count;
    input.dataset.generationStrategySourceToggle = candidate.id;
    input.setAttribute("aria-label", `Выбрать ${candidate.filename}`);
    const position = projection.selected.find(
      (item) => item.source_media_id === candidate.id,
    )?.position;
    const text = element("span", "");
    text.append(
      element("strong", "", position ? `${position}. ${candidate.filename}` : candidate.filename),
      element(
        "small",
        "muted",
        candidate.probe_required
          ? "Нужна бесплатная проверка MP4"
          : `${candidate.duration_seconds ?? "—"} с · сервером проверен`,
      ),
    );
    label.append(input, text);
    options.append(label);
  });
  root.append(header, options);
  if (!picker.candidates.length) {
    root.append(element(
      "p",
      "muted tiny",
      "Нет доступных зарегистрированных MP4 с подтверждёнными правами.",
    ));
  }

  if (reviews) {
    reviews.replaceChildren(...projection.selected.map((source) => (
      strategyMechanicsEditor(
        source,
        row.strategy_id,
        source.position,
        projection.required_count,
      )
    )));
  }
  form.dataset.generationStrategySourceCount = String(projection.selected_count);
  form.dataset.generationStrategySourcesReady = projection.all_selected_ready
    ? "true"
    : "false";
  return projection;
}

function generationStrategyProjectId() {
  const runtimeContext = window.ContentEngineWorkspaceRuntime
    ?.getGenerationContext?.();
  const fromRuntime = String(runtimeContext?.project_id || "")
    .trim().toLowerCase();
  if (fromRuntime) return fromRuntime;
  const raw = String(window.location.hash || "").replace(/^#/, "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  return String(new URLSearchParams(query).get("project_id") || "")
    .trim().toLowerCase();
}

function strategyAssetDescription(asset, blockers = []) {
  const product = asset.product_identity
    ? `${asset.product_identity.sku} · ${asset.product_identity.product_name}`
    : "";
  const duration = Number.isFinite(asset.duration_seconds)
    ? `${asset.duration_seconds} с · длительность проверена сервером`
    : "";
  const blockerCopy = blockers
    .map((code) => STRATEGY_ASSET_BLOCKER_COPY[code] || code)
    .join(", ");
  return [asset.filename, product, duration, blockerCopy]
    .filter(Boolean)
    .join(" · ");
}

function strategyAssetProbeOnly(blockers, role) {
  return role === "source_video"
    && blockers.length === 1
    && blockers[0] === "server_duration_probe_required";
}

function replaceStrategyAssetCandidates(form, strategyId, role, { reset = false } = {}) {
  const controlName = STRATEGY_ASSET_CONTROL_BY_ROLE[role];
  const control = form.elements?.[controlName];
  if (!(control instanceof HTMLSelectElement)) return;
  const previous = reset ? "" : String(control.value || "");
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = STRATEGY_ASSET_EMPTY_COPY[role] || "Выберите исходник";
  const options = (runtime.strategyAssetPage?.assets || [])
    .map((asset) => {
      const eligibility = generationStrategyAssetEligibility(
        asset,
        strategyId,
        role,
      );
      const probeOnly = strategyAssetProbeOnly(eligibility.blockers, role);
      const roleKnown = asset.eligible_strategy_roles?.some((entry) => (
        entry.strategy_id === strategyId && entry.role === role
      ));
      if (!eligibility.eligible && !probeOnly && !roleKnown) return null;
      const option = document.createElement("option");
      option.value = asset.id;
      option.textContent = strategyAssetDescription(asset, eligibility.blockers);
      option.disabled = !eligibility.eligible && !probeOnly;
      option.dataset.mediaKind = asset.kind;
      option.dataset.durationSeconds = Number.isFinite(asset.duration_seconds)
        ? String(asset.duration_seconds)
        : "";
      option.dataset.serverDurationVerified = Number.isFinite(asset.duration_seconds)
        ? "true"
        : "false";
      option.dataset.probeRequired = probeOnly ? "true" : "false";
      option.dataset.strategyRoleEligible = eligibility.eligible ? "true" : "false";
      option.dataset.blockingCodes = eligibility.blockers.join(",");
      return option;
    })
    .filter(Boolean);
  control.replaceChildren(placeholder, ...options);
  const reusable = options.find((option) => (
    option.value === previous && !option.disabled
  ));
  control.value = reusable?.value || "";
}

function syncStrategyAssetCandidates(form, { reset = false } = {}) {
  // The compact route persists the exact registered source UUID in hidden
  // handoff fields before native controls are rebound. Rehydrate that server-
  // issued source on every sync so a form remount or a failed/stale catalog
  // response cannot turn an already attached MP4 into "0 из 1".
  const diagnosticSource = registeredSourceFromHiddenHandoff(form)
    || registeredSourceFromIntakeHandoff(runtime.intakeHandoff);
  const diagnosticProjectId = generationStrategyProjectId();
  hydrateRegisteredSourceFromHiddenHandoff(form);
  if (form?.dataset) {
    form.dataset.generationStrategyHandoffSource = diagnosticSource?.media_id || "";
    form.dataset.generationStrategyRuntimeProject = diagnosticProjectId;
    form.dataset.generationStrategyOverlayProject =
      runtime.strategyRegisteredSourceProjectId || "";
    form.dataset.generationStrategyOverlayCount = String(
      runtime.strategyRegisteredSources.size,
    );
    const diagnosticOverlay = diagnosticSource
      ? runtime.strategyRegisteredSources.get(diagnosticSource.media_id)
      : null;
    form.dataset.generationStrategyOverlayContract = diagnosticOverlay
      ? [
          diagnosticOverlay.kind,
          diagnosticOverlay.mime_type,
          diagnosticOverlay.status,
          diagnosticOverlay.rights_confirmed === true ? "rights" : "no-rights",
          diagnosticOverlay.direct_mp4_attached === true ? "direct" : "no-direct",
          diagnosticOverlay.eligible === true ? "eligible" : "probe",
          Number.isFinite(diagnosticOverlay.duration_seconds)
            ? String(diagnosticOverlay.duration_seconds)
            : "no-duration",
          String(diagnosticOverlay.eligible_strategy_roles?.length || 0),
          (diagnosticOverlay.blocking_codes_by_strategy?.viral_product_swap || [])
            .join(",") || "no-blockers",
        ].join("|")
      : "absent";
    const diagnosticCatalogSource = runtime.strategyAssetPage?.assets?.find(
      (asset) => asset?.id === diagnosticSource?.media_id,
    );
    form.dataset.generationStrategyCatalogSource = diagnosticCatalogSource
      ? catalogConfirmsRegisteredStrategySource(
          diagnosticCatalogSource,
          diagnosticSource?.media_id || "",
        )
        ? "complete"
        : "partial"
      : "absent";
  }
  const row = selectedStrategyRow();
  const status = q("[data-generation-strategy-assets-status]", form);
  const more = q("[data-generation-strategy-assets-load-more]", form);
  const refresh = q("[data-generation-strategy-assets-refresh]", form);
  const probe = q('[data-action="probe-generation-strategy-media"]', form);
  if (more instanceof HTMLButtonElement) {
    more.hidden = runtime.strategyAssetPage?._meta?.has_more !== true;
    more.disabled = runtime.strategyAssetStatus === "loading";
  }
  if (refresh instanceof HTMLButtonElement) {
    refresh.disabled = runtime.strategyAssetStatus === "loading";
  }
  if (probe instanceof HTMLButtonElement) {
    probe.hidden = true;
    probe.disabled = true;
    delete probe.dataset.mediaId;
    delete probe.dataset.mediaIds;
  }
  if (!row) return;
  for (const role of row.asset_roles) {
    if (
      role.role !== "source_video"
      && STRATEGY_ASSET_CONTROL_BY_ROLE[role.role]
    ) {
      replaceStrategyAssetCandidates(form, row.strategy_id, role.role, { reset });
    }
  }
  const sourceProjection = renderStrategySourcePicker(form, { reset });
  if (form?.dataset) {
    form.dataset.generationStrategyPickerCandidateCount = String(
      runtime.strategySourcePicker?.candidates?.length || 0,
    );
    form.dataset.generationStrategyPickerStrategy =
      runtime.strategySourcePicker?.strategy_id || "";
  }
  // A compact upload can be safely probed even while the broader read-only
  // catalog is refreshing or temporarily unavailable: register + direct-MP4
  // attachment already completed, and the probe endpoint revalidates the
  // exact UUID without starting a provider or charging money.
  if (probe instanceof HTMLButtonElement) {
    const probeIds = sourceProjection?.probe_required_source_ids || [];
    const probeRequired = probeIds.length > 0;
    probe.hidden = !probeRequired;
    probe.disabled = !probeRequired || runtime.strategyAssetStatus === "loading";
    probe.textContent = probeIds.length > 1
      ? `Проверить ${probeIds.length} MP4 бесплатно`
      : "Проверить длительность MP4 бесплатно";
    probe.dataset.mediaIds = probeIds.join(",");
    if (probeIds.length) probe.dataset.mediaId = probeIds[0];
  }
  if (!status) return;
  if (runtime.strategyAssetStatus === "loading") {
    setStrategyModuleState(form, "loading");
    status.dataset.state = "loading";
    status.textContent = "Проверяем доступные исходники проекта. Файлы никуда не отправляются.";
    return;
  }
  if (runtime.strategyAssetStatus === "error") {
    setStrategyModuleState(form, "blocked");
    status.dataset.state = "warning";
    status.textContent = sourceProjection?.probe_required_source_ids?.length
      ? "Загруженный MP4 выбран. Общий список проекта временно недоступен, но бесплатная серверная проверка этого ролика доступна."
      : sourceProjection?.all_selected_ready
        ? "Загруженный MP4 выбран и проверен. Общий список проекта временно недоступен; платный запуск всё равно пройдёт отдельную серверную проверку."
        : "Не удалось получить серверный список исходников. Платный запуск заблокирован; обновите список.";
    return;
  }
  if (!runtime.strategyAssetPage) {
    setStrategyModuleState(form, "blocked");
    status.dataset.state = "pending";
    status.textContent = "Загрузите серверный список исходников. Браузер не подставляет локальные файлы как платную авторизацию.";
    return;
  }
  // Раньше «готово» решалось только полнотой файлов и про маршруты не знало
  // ничего. Разбор условия — в strategyRouteUnavailable.
  if (strategyRouteUnavailable(
    runtime.strategyCatalog?.strategyProviderRoutes,
    row.strategy_id,
  )) {
    setStrategyModuleState(form, "blocked");
    status.dataset.state = "warning";
    status.textContent = "У этой стратегии нет ни одного проверенного маршрута генерации. Подготовка и платный запуск недоступны, пока маршрут не заведён.";
    return;
  }
  const requiredOwnedRoles = row.asset_roles
    .filter((role) => (
      role.role !== "source_video"
      && STRATEGY_ASSET_CONTROL_BY_ROLE[role.role]
    ));
  const unsupportedRoles = strategyUnsupportedRequiredRoles(row.asset_roles);
  if (unsupportedRoles.length) {
    setStrategyModuleState(form, "blocked");
    status.dataset.state = "warning";
    status.textContent = `Форма не умеет собрать обязательную роль: ${
      unsupportedRoles.map((role) => role.role).join(", ")
    }. Это пробел формы, а не ваш: запуск заблокирован, чтобы сервер не отказал уже после подготовки.`;
    return;
  }
  const missing = requiredOwnedRoles.filter((role) => {
    const control = form.elements?.[STRATEGY_ASSET_CONTROL_BY_ROLE[role.role]];
    return !(control instanceof HTMLSelectElement)
      || ![...control.options].some((option) => !option.disabled && option.value);
  });
  // Фото товара собираются чекбоксами и потому в карту контролов не попадают —
  // до этой правки готовность их не проверяла вовсе.
  const productRoleId = strategyProductRole(row);
  const productRole = productRoleId
    ? row.asset_roles.find((role) => role.role === productRoleId)
    : null;
  const productMinimum = Number(productRole?.min_count || 0);
  const productSelected = productRole
    ? strategySelectedProductInputs(form).length
    : 0;
  const productShort = Boolean(productRole) && productSelected < productMinimum;
  if (sourceProjection?.probe_required_source_ids?.length) {
    setStrategyModuleState(form, "blocked");
    status.dataset.state = "warning";
    status.textContent = `Для ${sourceProjection.probe_required_source_ids.length} выбранных MP4 нужна бесплатная серверная проверка длительности. До неё подготовка и платный запуск недоступны.`;
    return;
  }
  const sourceCount = sourceProjection?.selected_count || 0;
  const requiredCount = sourceProjection?.required_count
    || generationStrategyRequiredSourceCount(row.strategy_id);
  const incompleteSources = sourceCount !== requiredCount;
  const notReady = missing.length || incompleteSources || productShort;
  setStrategyModuleState(form, notReady ? "blocked" : "ready");
  status.dataset.state = notReady ? "warning" : "ready";
  status.textContent = missing.length
    ? "Для одной из обязательных ролей нет подходящего серверно подтверждённого файла. Добавьте исходник в Материалы или загрузите следующую страницу."
    : productShort
      ? `Выберите фотографии товара: нужно минимум ${productMinimum}, сейчас ${productSelected}.`
    : incompleteSources
      ? `Выберите ровно ${requiredCount} MP4: сейчас ${sourceCount} из ${requiredCount}. Порядок выбора будет сохранён в очереди.`
      : requiredCount === 1
        ? "Исходный MP4 выбран и проверен сервером. Выбор ещё не запускает провайдера и не списывает средств."
        : `Ровно ${requiredCount} MP4 выбраны и проверены сервером. Каждый станет отдельным роликом; выбор ещё не запускает провайдера и не списывает средств.`;
}

async function loadGenerationStrategyAssets(form, { append = false } = {}) {
  const projectId = generationStrategyProjectId();
  if (!projectId || !form?.isConnected) return false;
  if (form.dataset.generationStrategyPaidLocked === "true") return false;
  const selectedAuthorityBefore = JSON.stringify(
    generationStrategySourcePickerProjection(runtime.strategySourcePicker)
      ?.selected || [],
  );
  const api = window.ContentEngineWorkspaceRuntime?.getApi?.();
  if (!api || typeof api.generationStrategyAssetCandidates !== "function") {
    runtime.strategyAssetStatus = "error";
    runtime.strategyAssetError = "generation_strategy_asset_candidates_unavailable";
    syncStrategyAssetCandidates(form);
    return false;
  }
  if (runtime.strategyAssetProjectId !== projectId) {
    runtime.strategyAssetRequest += 1;
    runtime.strategyAssetProjectId = projectId;
    runtime.strategyAssetPage = null;
    runtime.strategyAssetStatus = "idle";
    runtime.strategyAssetError = "";
    append = false;
  }
  if (runtime.strategyAssetStatus === "loading") return false;
  const cursor = append ? runtime.strategyAssetPage?._meta?.next_cursor : null;
  if (append && !cursor) return false;
  const request = ++runtime.strategyAssetRequest;
  runtime.strategyAssetStatus = "loading";
  runtime.strategyAssetError = "";
  syncStrategyAssetCandidates(form);
  try {
    const response = await api.generationStrategyAssetCandidates({
      projectId,
      kind: "all",
      pageSize: 100,
      ...(cursor ? { cursor } : {}),
    });
    const normalized = normalizeGenerationStrategyAssetCandidates(
      response?.data ?? response,
      { projectId, kind: "all", productId: null },
    );
    if (
      request !== runtime.strategyAssetRequest
      || runtime.strategyAssetProjectId !== projectId
      || !form.isConnected
    ) return false;
    if (!normalized.ok) {
      throw new Error(`generation_strategy_assets_${normalized.error.code}`);
    }
    runtime.strategyAssetPage = append
      ? mergeGenerationStrategyAssetPages(
          runtime.strategyAssetPage,
          normalized.page,
        )
      : normalized.page;
    // Once the catalog catches up, discard the temporary handoff overlay.
    // Keep a just-probed duration only when this response is the older
    // pre-probe snapshot (duration is still null); the next fresh page wins.
    const catalogById = new Map(
      (runtime.strategyAssetPage?.assets || []).map((asset) => [asset.id, asset]),
    );
    runtime.strategyRegisteredSources.forEach((candidate, mediaId) => {
      const catalogCandidate = catalogById.get(mediaId);
      if (!catalogCandidate) return;
      if (catalogConfirmsRegisteredStrategySource(catalogCandidate, mediaId)) {
        runtime.strategyRegisteredSources.delete(mediaId);
      }
    });
    runtime.strategyAssetStatus = "ready";
    runtime.strategyAssetError = "";
    syncStrategyAssetCandidates(form);
    const nextSourceProjection = generationStrategySourcePickerProjection(
      runtime.strategySourcePicker,
    );
    if (JSON.stringify(nextSourceProjection?.selected || []) !== selectedAuthorityBefore) {
      form.dispatchEvent(new CustomEvent(
        "contentengine:generation-strategy-sources-changed",
        { bubbles: true, detail: nextSourceProjection },
      ));
    }
    const pendingRestore = runtime.pendingStrategyRestore;
    if (pendingRestore?.form === form) {
      window.queueMicrotask(() => {
        if (form.isConnected && runtime.pendingStrategyRestore === pendingRestore) {
          applyStrategyRestore(form, pendingRestore.values);
        }
      });
    }
    scheduleSync(form);
    return true;
  } catch (error) {
    if (request !== runtime.strategyAssetRequest || !form.isConnected) return false;
    runtime.strategyAssetStatus = "error";
    runtime.strategyAssetError = String(error?.code || error?.message || "error");
    syncStrategyAssetCandidates(form);
    scheduleSync(form);
    return false;
  }
}

function generationStrategyRepeatProductFailure(code) {
  return Object.freeze({
    ok: false,
    code,
    product_id: "",
    primary_media_id: "",
    media_ids: Object.freeze([]),
    assets: Object.freeze([]),
  });
}

// Repeat IDs come from a read-only server snapshot, but IDs alone never make a
// browser card paid-ready. Resolve every ID again through the strictly
// normalized candidate catalog and preserve that server-owned product identity
// for the ordinary media controls. The resulting order is the immutable repeat
// order; its first item is the primary product photo.
function generationStrategyRepeatProductPlan(
  page,
  requestedMediaIds,
  expectedProductId,
) {
  const productId = String(expectedProductId || "").trim().toLowerCase();
  if (!STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(productId)) {
    return generationStrategyRepeatProductFailure("repeat_product_identity_invalid");
  }
  if (
    !Array.isArray(requestedMediaIds)
    || requestedMediaIds.length < 1
    || requestedMediaIds.length > PRODUCT_SWAP_REPEAT_MEDIA_LIMIT
    || requestedMediaIds.some((value) => typeof value !== "string")
  ) {
    return generationStrategyRepeatProductFailure("repeat_product_ids_invalid");
  }
  const mediaIds = requestedMediaIds.map(
    (value) => String(value).trim().toLowerCase(),
  );
  if (
    mediaIds.some((mediaId) => !STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(mediaId))
    || new Set(mediaIds).size !== mediaIds.length
  ) {
    return generationStrategyRepeatProductFailure("repeat_product_ids_invalid");
  }
  if (
    !page
    || page.version !== "generation-strategy-asset-candidates-response-v1"
    || !STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(String(page.project_id || ""))
    || !Array.isArray(page.assets)
    || page.contract?.read_only !== true
    || page.contract?.object_names_returned !== false
    || page.contract?.hashes_returned !== false
    || page.contract?.signed_urls_returned !== false
    || !Object.isFrozen(page)
    || !Object.isFrozen(page.assets)
  ) {
    return generationStrategyRepeatProductFailure("repeat_product_catalog_invalid");
  }
  const byId = new Map(page.assets.map((asset) => [asset?.id, asset]));
  const assets = [];
  for (const mediaId of mediaIds) {
    const asset = byId.get(mediaId);
    if (!asset) {
      return generationStrategyRepeatProductFailure("repeat_product_asset_missing");
    }
    const identity = asset.product_identity;
    const eligibility = generationStrategyAssetEligibility(
      asset,
      "viral_product_swap",
      "new_product_image",
    );
    if (
      !Object.isFrozen(asset)
      || !["product_photo", "packshot"].includes(asset.kind)
      || asset.project_id !== page.project_id
      || asset.status !== "ready"
      || asset.rights_confirmed !== true
      || asset.product_id !== productId
      || !identity
      || identity.identity_verified !== true
      || identity.product_id !== productId
      || !String(identity.sku || "").trim()
      || !String(identity.product_name || "").trim()
      || eligibility.eligible !== true
    ) {
      return generationStrategyRepeatProductFailure("repeat_product_asset_invalid");
    }
    const firstIdentity = assets[0]?.product_identity;
    if (
      firstIdentity
      && (
        identity.product_id !== firstIdentity.product_id
        || identity.sku !== firstIdentity.sku
        || identity.product_name !== firstIdentity.product_name
      )
    ) {
      return generationStrategyRepeatProductFailure("repeat_product_identity_mismatch");
    }
    assets.push(asset);
  }
  return Object.freeze({
    ok: true,
    code: "",
    product_id: productId,
    primary_media_id: mediaIds[0],
    media_ids: Object.freeze([...mediaIds]),
    assets: Object.freeze([...assets]),
  });
}

function clearStrategyRepeatProductOptions(form) {
  const host = q("[data-generation-strategy-repeat-products]", form);
  if (!(host instanceof HTMLElement)) return;
  qa("[data-generation-strategy-repeat-moved]", host).forEach((option) => {
    const origin = strategyRepeatProductOrigins.get(option);
    strategyRepeatProductOrigins.delete(option);
    delete option.dataset.generationStrategyRepeatMoved;
    if (origin?.isConnected) origin.replaceWith(option);
    else option.remove();
  });
  const generatedFieldset = host.closest(
    "[data-generation-strategy-repeat-product-fieldset]",
  );
  host.remove();
  if (generatedFieldset instanceof HTMLElement) generatedFieldset.remove();
}

function strategyRepeatProductHost(form) {
  const nativeInput = q('input[name="media_id"]', form);
  let list = nativeInput?.closest?.(".option-list") || null;
  if (!(list instanceof HTMLElement)) {
    const fieldset = element("fieldset");
    fieldset.dataset.generationStrategyRepeatProductFieldset = "true";
    fieldset.style.cssText = "border:0; padding:0; margin:0";
    fieldset.append(
      element("legend", "field-label", "Фото и ракурсы выбранного товара *"),
      element(
        "p",
        "muted tiny",
        "Архивные фото повторного запуска заново подтверждены сервером.",
      ),
    );
    list = element("div", "option-list");
    list.style.marginTop = "8px";
    fieldset.append(list);
    (contentFor(form, "media") || form).append(fieldset);
  }
  const host = element("div", "generation-strategy-repeat-products");
  host.dataset.generationStrategyRepeatProducts = "true";
  host.style.display = "contents";
  list.prepend(host);
  return host;
}

function strategyRepeatNativeProductOption(form, asset) {
  const identity = asset.product_identity;
  return qa('input[name="media_id"]', form)
    .map((input) => ({ input, option: input.closest(".generation-media-option") }))
    .find(({ input, option }) => {
      if (!(input instanceof HTMLInputElement) || !(option instanceof HTMLElement)) {
        return false;
      }
      const primary = qa('input[name="primary_media_id"]', option).find(
        (radio) => radio.value === asset.id,
      );
      return !input.disabled
        && primary instanceof HTMLInputElement
        && !primary.disabled
        && input.value === asset.id
        && option.dataset.paidReady === "true"
        && input.dataset.mediaIdentityVerified === "true"
        && input.dataset.mediaRightsConfirmed === "true"
        && input.dataset.mediaProductId === identity.product_id
        && input.dataset.mediaSku === identity.sku
        && input.dataset.mediaProductName === identity.product_name;
    })?.option || null;
}

function strategyRepeatSyntheticProductOption(asset) {
  const identity = asset.product_identity;
  const option = element("div", "option generation-media-option");
  option.dataset.paidReady = "true";
  option.dataset.generationStrategyRepeatSynthetic = "true";
  const selectLabel = element("label", "generation-media-option__select");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.name = "media_id";
  input.value = asset.id;
  input.dataset.mediaIdentityVerified = "true";
  input.dataset.mediaRightsConfirmed = "true";
  input.dataset.mediaProductId = identity.product_id;
  input.dataset.mediaSku = identity.sku;
  input.dataset.mediaProductName = identity.product_name;
  const copy = element("span");
  copy.append(
    element("strong", "", asset.filename),
    document.createElement("br"),
    element(
      "small",
      "muted",
      `фото товара · ${identity.sku} · ${identity.product_name} · подтверждено сервером`,
    ),
  );
  selectLabel.append(input, copy);
  const primaryLabel = element("label", "generation-media-option__primary");
  const primary = document.createElement("input");
  primary.type = "radio";
  primary.name = "primary_media_id";
  primary.value = asset.id;
  primaryLabel.append(primary, element("span", "", "Главное фото"));
  option.append(selectLabel, primaryLabel);
  return option;
}

function materializeStrategyRepeatProductPlan(form, plan) {
  if (!plan?.ok || !Array.isArray(plan.assets) || !plan.assets.length) return false;
  clearStrategyRepeatProductOptions(form);
  const host = strategyRepeatProductHost(form);
  if (!(host instanceof HTMLElement)) return false;
  qa('input[name="media_id"]', form).forEach((input) => {
    input.checked = false;
  });
  qa('input[name="primary_media_id"]', form).forEach((input) => {
    input.checked = false;
  });
  const selectedInputs = [];
  const primaryInputs = [];
  for (const asset of plan.assets) {
    let option = strategyRepeatNativeProductOption(form, asset);
    if (option) {
      const origin = document.createComment("generation-strategy-repeat-origin");
      option.before(origin);
      strategyRepeatProductOrigins.set(option, origin);
      option.dataset.generationStrategyRepeatMoved = "true";
    } else {
      option = strategyRepeatSyntheticProductOption(asset);
    }
    host.append(option);
    const input = q('input[name="media_id"]', option);
    const primary = q('input[name="primary_media_id"]', option);
    if (!(input instanceof HTMLInputElement) || !(primary instanceof HTMLInputElement)) {
      clearStrategyRepeatProductOptions(form);
      return false;
    }
    selectedInputs.push(input);
    primaryInputs.push(primary);
  }
  selectedInputs.forEach((input) => {
    input.checked = true;
  });
  primaryInputs.forEach((input, index) => {
    input.checked = index === 0 && input.value === plan.primary_media_id;
  });
  const exactOrder = qa('input[name="media_id"]:checked:not(:disabled)', host)
    .map((input) => String(input.value || "").trim().toLowerCase());
  const exactPrimary = String(
    q('input[name="primary_media_id"]:checked:not(:disabled)', host)?.value || "",
  ).trim().toLowerCase();
  if (
    JSON.stringify(exactOrder) !== JSON.stringify(plan.media_ids)
    || exactPrimary !== plan.primary_media_id
  ) {
    clearStrategyRepeatProductOptions(form);
    return false;
  }
  // Reuse the ordinary delegated handlers so SKU/name and readiness are
  // recomputed from these server-derived datasets, not from stale form text.
  selectedInputs[0].dispatchEvent(new Event("change", { bubbles: true }));
  primaryInputs[0].dispatchEvent(new Event("change", { bubbles: true }));
  const settledOrder = qa('input[name="media_id"]:checked:not(:disabled)', host)
    .map((input) => String(input.value || "").trim().toLowerCase());
  const settledPrimary = String(
    q('input[name="primary_media_id"]:checked:not(:disabled)', host)?.value || "",
  ).trim().toLowerCase();
  if (
    JSON.stringify(settledOrder) !== JSON.stringify(plan.media_ids)
    || settledPrimary !== plan.primary_media_id
  ) {
    // The ordinary paid-media guard (including its existing 1–5 cap) has the
    // final word. Never report a successful repeat restore after it rejects a
    // server snapshot that no longer fits the current form contract.
    clearStrategyRepeatProductOptions(form);
    return false;
  }
  return true;
}

function replaceStrategyOptions(control, values, selectedValue, emptyLabel) {
  if (!(control instanceof HTMLSelectElement)) return "";
  const normalized = [...new Set((Array.isArray(values) ? values : [])
    .map((value) => String(value || "").trim())
    .filter(Boolean))];
  const current = normalized.includes(String(selectedValue || ""))
    ? String(selectedValue)
    : normalized[0] || "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = emptyLabel;
  empty.selected = !current;
  control.replaceChildren(empty, ...normalized.map((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = value === current;
    return option;
  }));
  return current;
}

function resetStrategyForm(form) {
  clearStrategyRepeatProductOptions(form);
  const fieldset = q("#generation-strategy-assets", form);
  if (fieldset instanceof HTMLFieldSetElement) {
    fieldset.hidden = true;
    fieldset.disabled = true;
    delete fieldset.dataset.generationStrategyModule;
    delete fieldset.dataset.generationStrategyForm;
    fieldset.dataset.state = "idle";
    fieldset.removeAttribute("aria-label");
  }
  [
    "generation_strategy_id",
    "generation_strategy_version",
    "generation_strategy_recipe_version",
    "generation_strategy_source_basis",
    "generation_strategy_duration_seconds",
    "generation_strategy_ratio",
    "generation_strategy_resolution",
    "generation_strategy_audio",
    "generation_strategy_source_video_id",
    "generation_strategy_avatar_media_id",
    "generation_strategy_original_product_media_id",
  ].forEach((name) => {
    const control = form.elements?.[name];
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      control.value = "";
    }
  });
  q("[data-generation-strategy-attestations]", form)?.replaceChildren();
  q("[data-generation-strategy-source-picker]", form)?.replaceChildren();
  q("[data-generation-strategy-source-reviews]", form)?.replaceChildren();
  runtime.strategySourcePicker = null;
  runtime.strategyMechanicsDrafts.clear();
  delete form.dataset.generationStrategySourceCount;
  delete form.dataset.generationStrategySourcesReady;
}

function setStrategyModuleState(form, state) {
  const fieldset = q("#generation-strategy-assets", form);
  if (!(fieldset instanceof HTMLFieldSetElement)) return;
  fieldset.dataset.state = ["idle", "editing", "blocked", "ready", "loading"]
    .includes(state)
    ? state
    : "editing";
}

function strategyAttestationsMatch(root, row) {
  if (!(root instanceof HTMLElement)) return false;
  if (root.dataset.generationStrategyId !== row.strategy_id) return false;
  const inputs = qa("input[data-generation-strategy-attestation]", root);
  if (inputs.length !== row.required_attestations.length) return false;
  return row.required_attestations.every((attestation, index) => {
    const input = inputs[index];
    const label = input.closest("label");
    const copy = q(":scope > span", label);
    return input instanceof HTMLInputElement
      && input.type === "checkbox"
      && input.dataset.generationStrategyAttestation === attestation.id
      && input.name === `generation_strategy_attestation_${attestation.id}`
      && input.value === "true"
      && input.required
      && String(copy?.textContent || "").trim() === attestation.public_label;
  });
}

function syncStrategyAttestations(root, row, { reset = false } = {}) {
  if (!(root instanceof HTMLElement)) return;
  if (!reset && strategyAttestationsMatch(root, row)) return;
  root.replaceChildren(...row.required_attestations.map((attestation) => {
    const label = element("label", "option generation-strategy-attestation");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = `generation_strategy_attestation_${attestation.id}`;
    input.value = "true";
    input.required = true;
    input.dataset.generationStrategyAttestation = attestation.id;
    const copy = element("span", "", attestation.public_label);
    label.append(input, copy);
    return label;
  }));
  root.dataset.generationStrategyId = row.strategy_id;
}

function clearStrategyAttestations(form) {
  qa("#generation-strategy-assets input[data-generation-strategy-attestation]", form)
    .forEach((input) => {
      input.checked = false;
    });
}

function isStrategyAssetAuthorityControl(control) {
  if (!(control instanceof HTMLInputElement || control instanceof HTMLSelectElement)) {
    return false;
  }
  const name = String(control.name || "");
  return name === "media_id"
    || name === "primary_media_id"
    || /^generation_strategy_.+_media_id$/u.test(name);
}

function syncStrategyBriefValidity(form, strategySelected = Boolean(selectedStrategyRow())) {
  const brief = form.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return;
  if (strategySelected) {
    const strategyId = String(selectedStrategyRow()?.strategy_id || "");
    brief.dataset.generationStrategyForm = strategyId;
    delete brief.dataset.generationModelForm;
    delete brief.dataset.generationModelPromptLimit;
    brief.setCustomValidity(
      String(brief.value || "").length > 800
        ? "Сократите инструкцию до 800 знаков для выбранной стратегии."
        : "",
    );
    return;
  }
  delete brief.dataset.generationStrategyForm;
  brief.setCustomValidity("");
}

function syncLegacyModelVisibility(form, strategySelected) {
  const targets = [
    q("[data-ce-v4-model-kind]", form),
    q("[data-ce-v4-model-exact-settings]", form),
    q("[data-ce-v4-model-budget-marker]", form),
    form.elements?.generation_mode?.closest?.("label, .field"),
    q("#generation-duration-field", form),
    q("#generation-video-reference", form),
    q("#generation-spec-card", form),
    form.elements?.format?.closest?.("label, .field"),
  ];
  targets.forEach((target) => {
    if (target instanceof HTMLElement) target.hidden = strategySelected;
  });
  const modeControl = form.elements?.generation_mode;
  if (modeControl instanceof HTMLSelectElement) {
    modeControl.disabled = strategySelected;
    modeControl.required = !strategySelected;
  }
  [
    form.elements?.duration_seconds,
    form.elements?.generation_reference_url,
    form.elements?.generation_reference_mechanics,
    form.elements?.generation_reference_source_access_confirmed,
    form.elements?.generation_reference_transformative_use_confirmed,
    form.elements?.format,
    form.elements?.generation_resolution,
    form.elements?.generation_audio,
  ].forEach((control) => {
    if (
      control instanceof HTMLInputElement
      || control instanceof HTMLSelectElement
      || control instanceof HTMLTextAreaElement
    ) {
      control.disabled = strategySelected;
      // Dropping `required` matters as much as disabling: these legacy controls
      // are hidden in a strategy route, and a re-render that re-enables one of
      // them makes form.reportValidity() fail on an invisible empty select, so
      // every submit dies silently with no message the operator can see.
      if (strategySelected) control.required = false;
    }
  });
  if (strategySelected) {
    const campaignField = q("#generation-campaign-field", form);
    const campaign = form.elements?.campaign_id;
    const confirmationPanel = q("#real-generation-confirmation", form);
    const confirmation = form.elements?.real_spend_confirmation;
    const count = form.elements?.count;
    if (campaignField instanceof HTMLElement) campaignField.hidden = false;
    if (campaign instanceof HTMLSelectElement) {
      campaign.disabled = false;
      campaign.required = true;
    }
    if (confirmationPanel instanceof HTMLElement) confirmationPanel.hidden = false;
    if (confirmation instanceof HTMLInputElement) {
      const confirmationReady =
        form.dataset.generationStrategyConfirmationReady === "true";
      confirmation.disabled = !confirmationReady;
      confirmation.required = confirmationReady;
      if (!confirmationReady) confirmation.checked = false;
    }
    if (count instanceof HTMLInputElement) {
      count.value = "1";
      count.max = "1";
      count.readOnly = true;
    }
  }
  const brief = form.elements?.brief;
  if (brief instanceof HTMLTextAreaElement) {
    brief.required = strategySelected || modeIsReal(form);
    brief.maxLength = strategySelected ? 800 : 1_200;
    syncStrategyBriefValidity(form, strategySelected);
  }
  // Идентичность НОВОГО товара (артикул/название/категория QA) принадлежит
  // легаси-потоку; в стратегиях товар либо называется идентификатором
  // («Дуэт» выбирает готовый из списка), либо панель «Копии» заполняет эти
  // поля сама перед регистрацией фото. Пустые required-поля здесь молча
  // валили reportValidity() на бесплатных шагах, и мастер «не отвечал» у
  // «Дуэта» с готовым товаром — при том, что заполнить их в этой панели
  // человеку просто негде.
  [
    form.elements?.sku,
    form.elements?.product_name,
    form.elements?.product_category,
  ].forEach((control) => {
    if (
      control instanceof HTMLInputElement
      || control instanceof HTMLSelectElement
    ) {
      control.required = !strategySelected;
    }
  });
  const advisor = q("[data-ce-v4-model-advisor]", form);
  if (advisor instanceof HTMLElement) {
    // При выбранной стратегии старый каталог моделей (Runway «как совет»)
    // прячется целиком: движок выбирается в каскаде реестра маршрутов той же
    // стратегии, и второй список моделей рядом только спорил бы с ним.
    advisor.hidden = strategySelected;
    advisor.dataset.strategyAdvisoryOnly = strategySelected ? "true" : "false";
  }
}

// Видимый выбор движка стратегийных маршрутов в конструкторе. Поле
// generation_intake_engine создаёт экспресс-панель; когда её каскад обслуживает
// другую стратегию (или панели нет вовсе), конструктор обязан дать выбор сам —
// иначе привязка молча уходит дефолтным маршрутом реестра.
// Зеркало ROUTE_AUTHORITY_STRATEGY интейка (generation-strategy-intake-v4.js).
const EXPRESS_ROUTE_STRATEGY = Object.freeze({
  copy_video: "viral_product_swap",
  avatar_video: "viral_avatar_ugc",
  strategy_video: "viral_rebuild",
});
// Имена как в MODEL_PUBLIC_LABELS интейка — держать в ногу при новых движках.
const GUIDED_ENGINE_LABELS = Object.freeze({
  "fal:fal-ai/pika/v2/pikaswaps": "Pika Swaps",
  "runway:aleph2": "Runway Aleph",
  "fal:fal-ai/kling-video/o3/pro/video-to-video/edit": "Kling O3 Pro",
  "fal:fal-ai/kling-video/o3/standard/video-to-video/edit": "Kling O3 Standard",
  "fal:fal-ai/kling-video/o3/standard/image-to-video": "Kling O3 Standard",
  "fal:fal-ai/kling-video/o3/pro/image-to-video": "Kling O3 Pro",
  "fal:alibaba/happy-horse/video-edit": "Happy Horse Edit",
  "fal:bytedance/seedance-2.5/reference-to-video": "Seedance 2.5",
  "fal:minimax/h3/reference-to-video": "MiniMax H3",
  "fal:xai/grok-imagine-video/reference-to-video": "Grok Imagine",
  "fal:alibaba/happy-horse/reference-to-video": "Happy Horse",
});
const GUIDED_ENGINE_TIERS = Object.freeze({
  cheap: "Дёшево",
  medium: "Средне",
  premium: "Дорого",
});

function guidedEngineOptionLabel(route) {
  const id = `${route.provider}:${route.model_key}`;
  const name = GUIDED_ENGINE_LABELS[id]
    || String(route.model_key || "").split("/").filter(Boolean).pop()
    || id;
  const rate = Number(route.price_rate_minor);
  const price = route.price_kind === "usd_minor_per_second" && rate > 0
    ? `$${(rate / 100).toFixed(2)}/с`
    : route.price_kind === "usd_minor_per_run" && rate > 0
    ? `$${(rate / 100).toFixed(2)} за ролик`
    : "цену подтвердит сервер";
  const tier =
    GUIDED_ENGINE_TIERS[String(route.tier || "").trim().toLowerCase()] || "";
  return [name, price, tier].filter(Boolean).join(" · ");
}

// Тот же контракт, что у ensureHidden интейка: один input на форму, в корне
// формы (НЕ в fieldset — иначе disabled fieldset глушил бы поле).
function ensureStrategyEngineHidden(form) {
  const existing = form.elements?.namedItem?.("generation_intake_engine");
  if (existing instanceof HTMLInputElement) return existing;
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "generation_intake_engine";
  input.dataset.ceV4GenerationEngineHidden = "";
  form.append(input);
  return input;
}

// Запись платного контекста: события input+change ОБЯЗАНЫ пройти путь
// инвалидации app.js (handleFormActivity по имени generation_intake_engine
// сбрасывает подписанную цену и очередь). pinRatioSync=true — для программной
// записи ИЗНУТРИ syncStrategyForm: пин runtime.lastEngineForRatioSync гасит
// повторный вход handleFormEdit, потому что перефильтровку ratio сделает
// текущий же проход.
function writeStrategyEngineValue(form, value, { pinRatioSync = false } = {}) {
  const hidden = ensureStrategyEngineHidden(form);
  const next = String(value ?? "");
  if (hidden.disabled || hidden.value === next) return false;
  hidden.value = next;
  if (pinRatioSync) runtime.lastEngineForRatioSync = next;
  hidden.dispatchEvent(new Event("input", { bubbles: true }));
  hidden.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function syncStrategyEngineField(form, fieldset, row) {
  const output = q("[data-generation-strategy-output]", fieldset);
  if (!(output instanceof HTMLElement)) return;
  let field = q("[data-ce-v4-generation-engine-field]", output);
  const routes =
    (runtime.strategyCatalog?.strategyProviderRoutes?.[row.strategy_id] || [])
      .filter((route) => route?.enabled === true
        && String(route.provider || "").trim()
        && String(route.model_key || "").trim());
  // Каскад активной экспресс-панели — единственный видимый писатель поля на
  // своём экране; второй селект спорил бы с ним за одно значение. В компакт-
  // режимах интейка (вкладки «Копии»/«Дуэта», отдельный copy-экран) шелл
  // конструктора скрыт CSS — скрытый селект обязан молчать целиком: запись
  // дефолта отсюда воевала бы с applyExpressDefaults компакт-панели за одно
  // поле и на каждом раунде сбрасывала бы подписанную цену.
  const expressStrategy = EXPRESS_ROUTE_STRATEGY[
    String(form.dataset.generationIntakeV4Route || "")
  ] || null;
  const intakeCompact = ["compact", "copy"].includes(
    String(form.dataset.generationIntakeV4Mode || ""),
  );
  if (!routes.length || expressStrategy === row.strategy_id || intakeCompact) {
    if (field instanceof HTMLElement) {
      field.hidden = true;
      const select = q("select", field);
      if (select) select.disabled = true;
    }
    return;
  }
  if (!field) {
    field = element("label", "field");
    field.dataset.ceV4GenerationEngineField = "";
    const select = document.createElement("select");
    // НЕ name="generation_intake_engine": вместе со скрытым input namedItem()
    // вернул бы RadioNodeList с пустым .value — сломались бы и
    // getStrategyEngineChoice, и ensureHidden интейка.
    select.dataset.ceV4GenerationEngineSelect = "";
    field.append(
      element("span", "", "Движок генерации *"),
      select,
      element(
        "small",
        "field-hint",
        "Определяет цену и доступные форматы. Точную сумму подтвердит бесплатная серверная проверка.",
      ),
    );
    output.prepend(field);
  }
  const select = q("select[data-ce-v4-generation-engine-select]", field);
  if (!(select instanceof HTMLSelectElement)) return;
  const paidLocked = form.dataset.generationStrategyPaidLocked === "true";
  field.hidden = false;
  // Под платным замком селект — витрина подписанного значения, не орган
  // управления: свип syncGenerationStrategyPaidControlLock (app.js) глушит его
  // вместе с остальными контролами fieldset, и этот sync обязан не
  // перевключать его обратно — иначе живой селект писал бы в hidden и ронял
  // подписанную цену.
  select.disabled = paidLocked;
  // Опции перестраиваются только по смене отпечатка: панели под
  // MutationObserver, безусловная перестройка замкнула бы mount-цикл.
  // Отпечаток включает всё, из чего собирается лейбл (цена, тир), и дефолт
  // (recommended): смена цены при том же составе обязана перерисовать опции.
  const fingerprint = `${row.strategy_id}|${
    routes.map((route) => [
      `${route.provider}:${route.model_key}`,
      route.price_kind,
      route.price_rate_minor,
      route.tier,
      route.recommended === true ? "rec" : "",
    ].join("~")).join(",")
  }`;
  if (select.dataset.engineFingerprint !== fingerprint) {
    select.replaceChildren(...routes.map((route) => {
      const option = document.createElement("option");
      option.value = `${route.provider}:${route.model_key}`;
      option.textContent = guidedEngineOptionLabel(route);
      return option;
    }));
    select.dataset.engineFingerprint = fingerprint;
  }
  const hidden = ensureStrategyEngineHidden(form);
  const current = String(hidden.value || "").trim();
  const validValue = (value) => routes.some(
    (route) => `${route.provider}:${route.model_key}` === value,
  );
  const currentValid = validValue(current);
  // Под замком селект отражает ПОДПИСАННОЕ hidden-значение, а не desired:
  // маршрут мог выпасть из каталога после привязки, и показ fallback врал бы
  // о том, что реально оплачено. Выпавшему значению добавляется призрачная
  // option — disabled, чтобы после разблокировки её нельзя было выбрать.
  const ghost = select.querySelector("option[data-engine-ghost]");
  if (paidLocked && current && !currentValid) {
    if (!ghost || ghost.value !== current) {
      ghost?.remove();
      const option = document.createElement("option");
      option.value = current;
      option.disabled = true;
      option.dataset.engineGhost = "";
      const name = GUIDED_ENGINE_LABELS[current]
        || current.split(":").pop().split("/").filter(Boolean).pop()
        || current;
      option.textContent =
        `${name} · зафиксирован платной привязкой, в каталоге отсутствует`;
      select.append(option);
    }
  } else if (ghost) {
    ghost.remove();
  }
  if (paidLocked) {
    if (current && select.value !== current) select.value = current;
    return;
  }
  // Пересозданная форма теряет hidden вместе с DOM; человеческий выбор для
  // этой стратегии живёт в runtime и восстанавливается раньше дефолта.
  const remembered = runtime.guidedEngineChoice?.strategyId === row.strategy_id
      && validValue(runtime.guidedEngineChoice.value)
    ? runtime.guidedEngineChoice.value
    : null;
  const fallback = routes.find((route) => route.recommended === true)
    || routes[0];
  const desired = currentValid
    ? current
    : remembered || `${fallback.provider}:${fallback.model_key}`;
  if (!currentValid) {
    writeStrategyEngineValue(form, desired, { pinRatioSync: true });
  }
  if (select.value !== desired) select.value = desired;
}

// Разрешения, которые умеет выбранный в каскаде движок, по его уровням
// качества из реестра; null — движок не выбран или режимы неизвестны.
function strategyEngineResolutions(form, strategyId) {
  const raw = String(form?.elements?.generation_intake_engine?.value || "").trim();
  const separator = raw.indexOf(":");
  if (separator < 1) return null;
  const routes = runtime.strategyCatalog?.strategyProviderRoutes?.[strategyId];
  if (!Array.isArray(routes)) return null;
  const route = routes.find((entry) => (
    entry?.provider === raw.slice(0, separator)
    && entry?.model_key === raw.slice(separator + 1)
  ));
  const modes = Array.isArray(route?.quality_modes) ? route.quality_modes : [];
  const resolutions = new Set(
    modes.map((mode) => String(mode?.resolution || "")).filter(Boolean),
  );
  return resolutions.size ? resolutions : null;
}

function syncStrategyForm(form, { reset = false } = {}) {
  const row = selectedStrategyRow();
  const summary = selectedGenerationStrategySummary(runtime.strategyState);
  // Смена стратегии меняет и видимость легаси-однопуска: кнопка «Проверить
  // техническую готовность» с примечанием живут только вне стратегий.
  exposeProviderReadinessControl(form);
  if (!row || !summary.ok) {
    resetStrategyForm(form);
    syncLegacyModelVisibility(form, false);
    return false;
  }
  if (reset || row.strategy_id !== "viral_product_swap") {
    clearStrategyRepeatProductOptions(form);
  }

  const fieldset = q("#generation-strategy-assets", form);
  if (!(fieldset instanceof HTMLFieldSetElement)) return false;
  fieldset.hidden = false;
  fieldset.disabled = false;
  fieldset.dataset.generationStrategyModule = row.strategy_id;
  fieldset.dataset.generationStrategyForm = row.strategy_id;
  fieldset.dataset.state = "editing";
  fieldset.setAttribute(
    "aria-label",
    `Отдельная форма стратегии «${row.public_label}». Настраивается человеком.`,
  );
  syncLegacyModelVisibility(form, true);

  const setValue = (name, value) => {
    const control = form.elements?.[name];
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      control.value = String(value ?? "");
    }
  };
  setValue("generation_strategy_id", row.strategy_id);
  setValue("generation_strategy_version", runtime.strategyState.catalog.version);
  setValue("generation_strategy_recipe_version", row.recipe_version);
  setValue("generation_strategy_source_basis", "exact_source_video");

  const output = q("[data-generation-strategy-output]", fieldset);
  if (output instanceof HTMLElement) output.hidden = false;
  // Движок — первым полем грида результата: он задаёт цену и фильтр форматов.
  // Вызов до strategyEngineResolutions, чтобы дефолт успел записаться и список
  // форматов сразу фильтровался под выбранный движок.
  syncStrategyEngineField(form, fieldset, row);
  const duration = form.elements?.generation_strategy_duration_seconds;
  if (duration instanceof HTMLInputElement) {
    duration.disabled = false;
    duration.required = true;
    duration.min = String(row.output_rules.duration.min_seconds);
    duration.max = String(row.output_rules.duration.max_seconds);
    const current = Number(duration.value);
    if (
      reset
      || !Number.isSafeInteger(current)
      || current < row.output_rules.duration.min_seconds
      || current > row.output_rules.duration.max_seconds
    ) {
      duration.value = String(row.output_rules.duration.default_seconds);
    }
  }
  const ratioField = q('[data-generation-strategy-dimension="ratio"]', fieldset);
  const resolutionField = q('[data-generation-strategy-dimension="resolution"]', fieldset);
  const ratio = form.elements?.generation_strategy_ratio;
  const resolution = form.elements?.generation_strategy_resolution;
  const ratioMode = row.output_rules.dimension_field === "ratio";
  if (ratioField instanceof HTMLElement) ratioField.hidden = !ratioMode;
  if (resolutionField instanceof HTMLElement) resolutionField.hidden = ratioMode;
  if (ratio instanceof HTMLSelectElement) {
    ratio.disabled = !ratioMode;
    ratio.required = ratioMode;
    // Кадры, которых выбранный движок не делает, не предлагаются: у движков
    // fal «Создания» есть только 720p, и 1080-й кадр обернулся бы отказом в
    // цене уже после выбора. Без движка (или без сведений о его режимах)
    // список остаётся полным.
    const engineResolutions = strategyEngineResolutions(form, row.strategy_id);
    const ratios = engineResolutions
      ? row.output_rules.ratios.filter((value) => engineResolutions.has(
        String(row.output_rules.resolution_by_ratio?.[value] || ""),
      ))
      : row.output_rules.ratios;
    replaceStrategyOptions(
      ratio,
      ratios.length ? ratios : row.output_rules.ratios,
      reset ? "" : ratio.value,
      "Выберите формат",
    );
  }
  if (resolution instanceof HTMLSelectElement) {
    resolution.disabled = ratioMode;
    resolution.required = !ratioMode;
    replaceStrategyOptions(
      resolution,
      row.output_rules.resolutions,
      reset ? "" : resolution.value,
      "Выберите разрешение",
    );
  }
  const audio = form.elements?.generation_strategy_audio;
  if (audio instanceof HTMLSelectElement) {
    audio.disabled = false;
    audio.required = true;
    if (reset) audio.value = "";
  }

  const roleIds = new Set(row.asset_roles.map((role) => role.role));
  qa("[data-generation-strategy-role]", fieldset).forEach((node) => {
    const active = roleIds.has(node.dataset.generationStrategyRole);
    node.hidden = node.hasAttribute("data-generation-strategy-legacy-source")
      ? true
      : !active;
    qa("input, select", node).forEach((control) => {
      const legacySourceControl = control.name === "generation_strategy_source_video_id";
      control.disabled = legacySourceControl || !active;
      if ("required" in control) control.required = legacySourceControl ? false : active;
      if (!active && reset) {
        if (control instanceof HTMLInputElement && ["checkbox", "radio"].includes(control.type)) {
          control.checked = false;
        } else {
          control.value = "";
        }
      }
    });
  });

  const attestationRoot = q("[data-generation-strategy-attestations]", fieldset);
  syncStrategyAttestations(attestationRoot, row, { reset });
  const copy = q("[data-generation-strategy-assets-copy]", fieldset);
  if (copy) {
    const requiredCount = generationStrategyRequiredSourceCount(row.strategy_id);
    copy.textContent = row.strategy_id === "viral_product_swap"
      ? `${row.public_label}. Выберите один исходный MP4, кадр исходного товара, фото нового товара и подтвердите права. До явного подтверждения списания не будет.`
      : `${row.public_label}. Выберите ровно ${requiredCount} исходных MP4 в нужном порядке, общие ассеты товара и права. Каждый исходник получит своё ТЗ, цену и задачу; до общего явного подтверждения списания не будет.`;
  }
  syncStrategyAssetCandidates(form, { reset });
  return true;
}

function strategyAssetsForForm(form, row) {
  const assets = [];
  const addSelected = (role, control, { duration = false } = {}) => {
    if (!(control instanceof HTMLSelectElement) || !control.value) return;
    const asset = { role, media_id: String(control.value).toLowerCase() };
    if (duration) {
      const seconds = Number(control.selectedOptions?.[0]?.dataset?.durationSeconds);
      if (Number.isFinite(seconds) && seconds > 0) asset.duration_seconds = seconds;
    }
    assets.push(asset);
  };
  const roleIds = new Set(row.asset_roles.map((role) => role.role));
  if (roleIds.has("avatar_image")) {
    addSelected("avatar_image", form.elements?.generation_strategy_avatar_media_id);
  }
  if (roleIds.has("original_product_image")) {
    addSelected(
      "original_product_image",
      form.elements?.generation_strategy_original_product_media_id,
    );
  }
  const productRole = strategyProductRole(row);
  if (productRole) {
    strategySelectedProductInputs(form).forEach((input) => {
      assets.push({ role: productRole, media_id: String(input.value).toLowerCase() });
    });
  }
  return assets;
}

function generationStrategyAttestations(form, row) {
  return Object.fromEntries(row.required_attestations.map((item) => [
    item.id,
    q(`#generation-strategy-assets input[data-generation-strategy-attestation="${CSS.escape(item.id)}"]`, form)?.checked === true,
  ]));
}

function generationStrategyMechanicsSummary(sourceMediaId, strategyId) {
  if (MECHANICS_FREE_STRATEGIES.has(strategyId)) return null;
  const draft = strategyMechanicsDraft(sourceMediaId);
  return Object.freeze({
    version: "generation-strategy-mechanics-summary-v1",
    hook: String(draft.hook || "").trim(),
    beat_sequence: Object.freeze(String(draft.beat_sequence || "")
      .split(/\r?\n/u)
      .map((item) => item.trim())
      .filter(Boolean)),
    pacing: String(draft.pacing || "").trim(),
    camera_language: String(draft.camera_language || "").trim(),
    composition: String(draft.composition || "").trim(),
    audio_pattern: String(draft.audio_pattern || "").trim(),
    cta_pattern: String(draft.cta_pattern || "").trim(),
  });
}

function generationStrategySelections(form) {
  const row = selectedStrategyRow();
  const selected = selectedGenerationStrategySummary(runtime.strategyState);
  if (!row || !selected.ok) return null;
  const sourceProjection = generationStrategySourcePickerProjection(
    runtime.strategySourcePicker,
  );
  if (!sourceProjection?.all_selected_ready) return null;
  const sharedAssets = strategyAssetsForForm(form, row);
  const attestations = generationStrategyAttestations(form, row);
  const duration = Number(form.elements?.generation_strategy_duration_seconds?.value);
  const audioValue = String(form.elements?.generation_strategy_audio?.value || "");
  const sourceRole = row.asset_roles.find((role) => role.role === "source_video");
  const results = [];
  for (const source of sourceProjection.selected) {
    if (
      sourceRole?.duration_required === true
      && (!source.ready || !Number.isFinite(Number(source.duration_seconds)))
    ) return null;
    const sourceAsset = {
      role: "source_video",
      media_id: source.source_media_id,
      ...(sourceRole?.duration_required === true
        ? { duration_seconds: Number(source.duration_seconds) }
        : {}),
    };
    const assets = [sourceAsset, ...sharedAssets];
    const assetCounts = Object.fromEntries(
      row.asset_roles.map((role) => [
        role.role,
        assets.filter((asset) => asset.role === role.role).length,
      ]),
    );
    const draft = {
      duration_seconds: duration,
      audio: audioValue === "true" ? true : audioValue === "false" ? false : null,
      asset_counts: assetCounts,
      attestations,
      ...(row.output_rules.dimension_field === "ratio"
        ? { ratio: String(form.elements?.generation_strategy_ratio?.value || "") }
        : { resolution: String(form.elements?.generation_strategy_resolution?.value || "") }),
    };
    const validation = validateSelectedGenerationStrategyDraft(
      runtime.strategyState,
      draft,
    );
    if (!validation.ok) return null;
    results.push(Object.freeze({
      source_media_id: source.source_media_id,
      position: source.position,
      filename: source.filename,
      selection: Object.freeze({
        version: runtime.strategyState.catalog.version,
        strategy_id: row.strategy_id,
        recipe_version: row.recipe_version,
        duration_seconds: validation.normalized.duration_seconds,
        ...(row.output_rules.dimension_field === "ratio"
          ? { ratio: validation.normalized.ratio }
          : { resolution: validation.normalized.resolution }),
        audio: validation.normalized.audio,
        assets: Object.freeze(assets.map((asset) => Object.freeze({ ...asset }))),
        attestations: Object.freeze({ ...attestations }),
      }),
      mechanics_summary: generationStrategyMechanicsSummary(
        source.source_media_id,
        row.strategy_id,
      ),
    }));
  }
  return results.length === sourceProjection.required_count
    ? Object.freeze(results)
    : null;
}

function generationStrategySelection(form) {
  return generationStrategySelections(form)?.[0]?.selection || null;
}

function renderStrategyView(form) {
  const root = q("[data-ce-v4-generation-strategies]", form);
  if (!root) return;
  root.innerHTML = generationStrategyViewMarkup(runtime.strategyState);
  runtime.strategyViewRoots.add(root);
  syncStrategyForm(form);
}

function applyStrategyRestore(form, values) {
  const strategyId = String(values?.generation_strategy_id || "").trim();
  if (!strategyId) return false;
  if (runtime.strategyState?.catalog_status !== "ready") {
    runtime.pendingStrategyRestore = { form, values: { ...values } };
    return false;
  }
  const strategyChanged = runtime.strategyState?.selected_strategy_id !== strategyId;
  runtime.strategyState = reduceGenerationStrategyViewState(
    runtime.strategyState,
    { type: GENERATION_STRATEGY_SELECT_ACTION, strategy_id: strategyId },
  );
  if (runtime.strategyState?.selected_strategy_id !== strategyId) return false;
  const root = q("[data-ce-v4-generation-strategies]", form);
  if (root) root.innerHTML = generationStrategyViewMarkup(runtime.strategyState);
  syncStrategyForm(form, { reset: strategyChanged });
  const unresolvedAssetControls = [];
  const setValue = (name, value) => {
    const control = form.elements?.[name];
    if (!control || value === null || value === undefined || value === "") return true;
    if (control instanceof HTMLSelectElement) {
      const option = [...control.options].find(
        (candidate) => candidate.value === String(value) && !candidate.disabled,
      );
      if (!option) return false;
    }
    control.value = String(value);
    return true;
  };
  [
    "generation_strategy_duration_seconds",
    "generation_strategy_ratio",
    "generation_strategy_resolution",
    "generation_strategy_audio",
    "generation_strategy_source_video_id",
    "generation_strategy_avatar_media_id",
    "generation_strategy_original_product_media_id",
  ].forEach((name) => {
    if (!setValue(name, values[name]) && values[name]) {
      unresolvedAssetControls.push(name);
    }
  });
  const requestedProductMedia = Array.isArray(
    values.generation_strategy_product_media_ids,
  )
    ? values.generation_strategy_product_media_ids.map(
        (value) => String(value || "").trim().toLowerCase(),
      ).filter(Boolean)
    : [];
  let productMediaAvailable = false;
  let repeatProductPlan = null;
  if (strategyId === "viral_product_swap") {
    repeatProductPlan = generationStrategyRepeatProductPlan(
      runtime.strategyAssetPage,
      values.generation_strategy_product_media_ids,
      values.generation_strategy_product_id,
    );
    productMediaAvailable = repeatProductPlan.ok
      && materializeStrategyRepeatProductPlan(form, repeatProductPlan);
    if (!repeatProductPlan.ok) clearStrategyRepeatProductOptions(form);
  } else {
    // Other strategy routes retain the existing form-catalog behavior. Only
    // Product Swap repeat may materialize server candidates outside that list.
    const exactRequested = [...new Set(requestedProductMedia)];
    const availableProductMedia = new Set(
      qa('input[name="media_id"]:not(:disabled)', form).map((input) => (
        String(input.value || "").trim().toLowerCase()
      )),
    );
    productMediaAvailable = exactRequested.every((mediaId) => (
      availableProductMedia.has(mediaId)
    ));
    if (exactRequested.length && productMediaAvailable) {
      const selected = new Set(exactRequested);
      qa('input[name="media_id"]', form).forEach((input) => {
        input.checked = selected.has(String(input.value || "").trim().toLowerCase())
          && !input.disabled;
      });
      qa('input[name="primary_media_id"]', form).forEach((input) => {
        input.checked = String(input.value || "").trim().toLowerCase()
          === exactRequested[0] && !input.disabled;
      });
    }
  }
  const waitForProductCatalog = strategyId === "viral_product_swap"
    && repeatProductPlan?.ok !== true
    && [
      "repeat_product_catalog_invalid",
      "repeat_product_asset_missing",
    ].includes(repeatProductPlan?.code)
    && runtime.strategyAssetStatus !== "ready";
  const loadNextProductPage = strategyId === "viral_product_swap"
    && repeatProductPlan?.code === "repeat_product_asset_missing"
    && runtime.strategyAssetStatus === "ready"
    && runtime.strategyAssetPage?._meta?.has_more === true;
  if (
    (
      unresolvedAssetControls.length
      && runtime.strategyAssetStatus !== "ready"
    )
    || waitForProductCatalog
    || loadNextProductPage
  ) {
    runtime.pendingStrategyRestore = { form, values: { ...values } };
    if (runtime.strategyAssetStatus !== "loading") {
      void loadGenerationStrategyAssets(form, { append: loadNextProductPage });
    }
    return false;
  }
  // Draft restore intentionally never restores rights or likeness consent.
  // These confirmations belong to one exact launch and must be given again.
  qa("#generation-strategy-assets input[data-generation-strategy-attestation]", form)
    .forEach((input) => {
      input.checked = false;
    });
  runtime.pendingStrategyRestore = null;
  if (unresolvedAssetControls.length || !productMediaAvailable) {
    scheduleSync(form);
    return false;
  }
  scheduleSync(form);
  return true;
}

function ensureStrategyView(form) {
  let root = q("[data-ce-v4-generation-strategies]", form);
  if (!root) {
    root = element("div", "ce-v4-generation-strategies");
    root.dataset.ceV4GenerationStrategies = "";
    contentFor(form, "mode")?.prepend(root);
  }
  if (!runtime.strategyViewRoots.has(root)) renderStrategyView(form);
  return root;
}

function modelVisualNode(model, { recommended = false, featured = false } = {}) {
  const visual = resolveGenerationModelVisual(model?.provider, model?.model);
  if (!visual) return null;
  const frame = element(
    "span",
    featured
      ? "ce-v4-model-card__visual ce-v4-model-card__visual--featured"
      : "ce-v4-model-card__visual",
  );
  frame.dataset.family = visual.family;
  frame.dataset.tone = visual.tone;
  frame.dataset.modelVisual = visual.key;
  frame.setAttribute("aria-hidden", "true");
  const image = document.createElement("img");
  image.className = "ce-v4-model-card__image";
  image.src = visual.src;
  image.alt = "";
  image.decoding = "async";
  image.draggable = false;
  image.loading = recommended || featured ? "eager" : "lazy";
  image.style.objectPosition = visual.focal;
  frame.append(image);
  return frame;
}

function modelCard(form, model, state) {
  const key = modelKey(model);
  const recommendationKey = modelKey(state?.recommendation?.recommended);
  const strategyAdvisoryOnly = Boolean(selectedStrategyRow());
  const selectedKey = strategyAdvisoryOnly
    ? modelKey(state?.selection)
    : modeIsReal(form) || runtime.externalSelectionActive
      ? modelKey(state?.selection)
      : "";
  const executable = !strategyAdvisoryOnly && modelCanUseExistingLaunch(form, model);
  const selectable = strategyAdvisoryOnly ? model?.enabled === true : executable;
  const recommended = key === recommendationKey;
  const selected = key === selectedKey;
  const candidate = modelCandidate(state, model);
  const unavailableCodes = modelUnavailableCodes(state, model);
  const disabledReasons = translatedList(unavailableCodes);
  const policyDisabledReason = MODEL_COPY[String(model.disabledReasonCode || "")] || "";
  const primaryDisabledReason = strategyAdvisoryOnly && selectable
    ? "Можно сохранить как предпочтение для сравнения. Фактический запуск использует серверный recipe выбранной стратегии."
    : policyDisabledReason || disabledReasons[0] || "Недоступно";
  const costPresentation = modelCostPresentation(form, model, state);
  const readiness = strategyAdvisoryOnly
    ? { state: "advisory", text: "Совет; маршрут стратегии проверяет сервер" }
    : modelReadinessPresentation(form, model, state, executable);
  const qualityText = modelQualityState(model, selectable, state);

  const card = element("article", "ce-v4-model-card");
  card.dataset.provider = String(model.provider || "");
  card.dataset.model = String(model.model || "");
  card.dataset.recommended = recommended ? "true" : "false";
  card.dataset.available = selectable ? "true" : "false";
  card.dataset.lifecycle = String(model.lifecycle || "");
  card.dataset.quality = String(model.qualityTier || "");
  card.dataset.readiness = readiness.state;
  card.dataset.disabledReasonCode = String(model.disabledReasonCode || "");
  card.dataset.strategyAdvisoryOnly = strategyAdvisoryOnly ? "true" : "false";
  card.classList.toggle("is-selected", selected);
  if (!selectable) {
    card.tabIndex = 0;
    card.setAttribute("aria-disabled", "true");
  }

  const radio = document.createElement("input");
  radio.type = "radio";
  radio.name = "generation_model";
  radio.value = key;
  radio.checked = selected;
  radio.disabled = !selectable;
  radio.dataset.ceV4GenerationModel = "";
  radio.setAttribute(
    "aria-label",
    `${model.publicLabel || model.model}. ${selectable ? primaryDisabledReason : "Недоступно. " + primaryDisabledReason}`,
  );

  const top = element("span", "ce-v4-model-card__top");
  const provider = element("span", "ce-v4-model-card__provider", String(model.provider || "МОДЕЛЬ").toUpperCase());
  const flag = element(
    "span",
    recommended ? "ce-v4-model-card__flag is-recommended" : "ce-v4-model-card__flag",
    recommended && selected
      ? "Ваш выбор · системный подбор"
      : recommended
        ? "Системный подбор"
        : selected
          ? "Ваш выбор"
          : selectable
            ? strategyAdvisoryOnly ? "Можно выбрать" : "Доступна"
            : "Недоступна",
  );
  top.append(provider, flag);

  const name = element("strong", "ce-v4-model-card__name", String(model.publicLabel || model.model || "Модель"));
  const kind = model.contentKind === "photo" ? "Фото" : "Видео";
  const quality = QUALITY_LABELS[String(model.qualityTier || "")] || "";
  const speed = SPEED_LABELS[String(model.speedTier || "")] || "";
  const costTier = COST_TIER_LABELS[String(model.qualityTier || "")] || "";
  const meta = element(
    "span",
    "ce-v4-model-card__meta",
    [kind, quality, speed, costTier].filter(Boolean).join(" · "),
  );

  const fit = element("span", "ce-v4-model-card__fact");
  fit.append(
    element("b", "", "Подходит: "),
    document.createTextNode(firstCatalogCopy(model.bestFor, "для базового результата")),
  );
  const limit = element("span", "ce-v4-model-card__fact");
  limit.append(
    element("b", "", "Ограничение: "),
    document.createTextNode(firstCatalogCopy(model.avoidFor, "проверить условия перед запуском")),
  );
  const inputs = element("span", "ce-v4-model-card__fact");
  inputs.append(element("b", "", "Исходники: "), document.createTextNode(modelInputSummary(model)));
  const output = element("span", "ce-v4-model-card__fact");
  output.append(element("b", "", "Результат: "), document.createTextNode(modelOutputSummary(model)));
  const cost = element("span", "ce-v4-model-card__cost");
  cost.dataset.estimateSource = costPresentation.source;
  cost.append(element("b", "", "Цена: "), document.createTextNode(costPresentation.text));
  const readinessLine = element("span", "ce-v4-model-card__readiness");
  readinessLine.dataset.state = readiness.state;
  readinessLine.append(element("b", "", "Готовность: "), document.createTextNode(readiness.text));
  const qualityState = element(
    "span",
    "ce-v4-model-card__quality",
    qualityText,
  );
  qualityState.dataset.state = qualityText === "Проверено"
    ? "verified"
    : qualityText === "Недоступно"
      ? "blocked"
      : qualityText === "Экспериментально"
        ? "experimental"
        : "recheck";

  const copy = strategyAdvisoryOnly && selectable
    ? "Можно выбрать как предпочтение для сравнения. Этот выбор не меняет платный маршрут: генерацию выполнит серверный recipe стратегии."
    : executable
    ? recommended
      ? recommendationReason(candidate?.reasonCodes || state?.recommendation?.reasonCodes)
      : "Можно выбрать и затем отдельно подтвердить запуск"
    : policyDisabledReason
      || disabledReasons[0]
      || (model.enabled === true
        ? MODEL_COPY.launch_route_pending
        : "Пока недоступна вашей организации");
  const explanation = element("small", "ce-v4-model-card__explanation", copy);

  const choice = element("label", "ce-v4-model-card__choice");
  choice.append(radio);
  const visual = modelVisualNode(model, { recommended });
  if (visual) choice.append(visual);
  choice.append(
    top,
    name,
    meta,
    fit,
    limit,
    cost,
    readinessLine,
    qualityState,
    explanation,
  );
  const technical = element("details", "ce-v4-model-card__technical");
  technical.append(element("summary", "", "Исходники и формат"));
  const technicalBody = element("span", "ce-v4-model-card__technical-body");
  technicalBody.append(inputs, output);
  technical.append(technicalBody);
  card.append(choice, technical);
  return card;
}

function modelGroupKey(model) {
  if (["experimental", "preview"].includes(String(model.lifecycle || ""))) return "experimental";
  return ["economy", "balanced", "premium"].includes(String(model.qualityTier || ""))
    ? String(model.qualityTier)
    : "balanced";
}

function groupedModelCards(form, models, state) {
  const labels = Object.fromEntries(MODEL_FILTERS);
  if (runtime.modelFilter === "relevant" && models.length) {
    const section = element("section", "ce-v4-model-group ce-v4-model-group--relevant");
    section.dataset.modelGroup = "relevant";
    const heading = element("h6", "ce-v4-model-group__title", "Подходят сейчас");
    heading.append(element("span", "", String(models.length)));
    const list = element("div", "ce-v4-model-group__grid");
    list.append(...models.map((model) => modelCard(form, model, state)));
    section.append(heading, list);
    return [section];
  }
  const order = ["economy", "balanced", "premium", "experimental"];
  const groups = order.flatMap((groupKey) => {
    const groupModels = models.filter((model) => modelGroupKey(model) === groupKey);
    if (!groupModels.length) return [];
    const section = element("section", "ce-v4-model-group");
    section.dataset.modelGroup = groupKey;
    const heading = element("h6", "ce-v4-model-group__title", labels[groupKey]);
    heading.append(element("span", "", String(groupModels.length)));
    const list = element("div", "ce-v4-model-group__grid");
    list.append(...groupModels.map((model) => modelCard(form, model, state)));
    section.append(heading, list);
    return [section];
  });
  if (groups.length) return groups;
  const empty = element(
    "p",
    "ce-v4-model-advisor__empty-filter",
    `В разделе «${labels[runtime.modelFilter] || labels.all}» пока нет моделей. Выберите другой фильтр — текущий ручной выбор сохранён.`,
  );
  empty.setAttribute("role", "status");
  return [empty];
}

function visibleModelsForFilter(models, state, form) {
  if (runtime.modelFilter === "all") return models;
  if (runtime.modelFilter !== "relevant") {
    return models.filter((model) => modelGroupKey(model) === runtime.modelFilter);
  }

  const selectedKey = modelKey(state?.selection);
  const recommendedKey = modelKey(state?.recommendation?.recommended);
  const currentKind = state?.context?.contentKind || modelContentKind(form);
  const preferredKeys = [
    selectedKey,
    recommendedKey,
    ...(state?.recommendation?.alternatives || []).map(modelKey),
  ].filter(Boolean);
  const ranked = [
    ...preferredKeys.map((key) => models.find((model) => modelKey(model) === key)).filter(Boolean),
    ...models.filter((model) => model.contentKind === currentKind && modelCanUseExistingLaunch(form, model)),
    ...models.filter((model) => model.contentKind === currentKind),
    ...models,
  ];
  const seen = new Set();
  return ranked.filter((model) => {
    const key = modelKey(model);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 4);
}

function syncContentKindChooser(form) {
  const kind = modelContentKind(form);
  qa("[data-ce-v4-content-kind]", form).forEach((button) => {
    const active = button.dataset.ceV4ContentKind === kind;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function recommendationSource(state) {
  const reasons = state?.recommendation?.reasonCodes || [];
  if (reasons.includes("research_recommendation_match")) return "По исследованию";
  if (reasons.includes("performance_recommendation_match")) return "По результатам контента";
  return "По параметрам текущей сцены";
}

function recommendationCompromise(recommendedModel, selectedModel) {
  if (!recommendedModel) return "";
  if (selectedModel && modelKey(selectedModel) !== modelKey(recommendedModel)) {
    const selectedFit = firstCatalogCopy(selectedModel.bestFor, "вашей альтернативы");
    const recommendedLimit = firstCatalogCopy(recommendedModel.avoidFor, "точных ограничений сцены");
    return `Ваш вариант сильнее для «${selectedFit}», а рекомендованный требует учесть: ${recommendedLimit}.`;
  }
  const limitation = firstCatalogCopy(
    recommendedModel.avoidFor,
    "сцен без предварительной проверки цены и готовности",
  );
  return `Не лучший выбор для: ${limitation}.`;
}

function comparisonCell(title, model, form, state) {
  const cell = element("div", "ce-v4-model-comparison__cell");
  const cost = modelCostPresentation(form, model, state);
  cell.append(
    element("small", "", title),
    element("strong", "", String(model.publicLabel || model.model)),
    element("span", "", `${QUALITY_LABELS[model.qualityTier] || ""} · ${SPEED_LABELS[model.speedTier] || ""}`),
    element("span", "", firstCatalogCopy(model.bestFor, "Базовый результат")),
    element("span", "", `Цена: ${cost.text}`),
  );
  return cell;
}

function renderRecommendationPanel(form, recommendation, state, suggestedModel, selectedModel) {
  recommendation.replaceChildren();
  if (!suggestedModel) {
    const empty = element("div", "ce-v4-model-advisor__recommendation-empty");
    empty.append(
      element("strong", "", "Нет совместимого технического подбора"),
      element("p", "", "Текущий ручной выбор сохранён. Исправьте исходник, длительность, звук или бюджет — ничего не будет запущено автоматически."),
    );
    recommendation.append(empty);
    recommendation.hidden = false;
    recommendation.dataset.state = "blocked";
    return;
  }

  const recommendedCandidate = modelCandidate(state, suggestedModel) || state.recommendation?.recommended;
  const reasonLines = translatedList(recommendedCandidate?.reasonCodes || state.recommendation?.reasonCodes)
    .slice(0, 3);
  const warningLines = translatedList(
    recommendedCandidate?.warningCodes || state.recommendation?.warningCodes,
    MODEL_WARNING_COPY,
  );
  const strategyAdvisoryOnly = Boolean(selectedStrategyRow());
  const executable = !strategyAdvisoryOnly && modelCanUseExistingLaunch(form, suggestedModel);
  const selectable = strategyAdvisoryOnly ? suggestedModel?.enabled === true : executable;
  const cost = modelCostPresentation(form, suggestedModel, state);
  const readiness = strategyAdvisoryOnly
    ? { state: "advisory", text: "Совет; recipe стратегии проверяет сервер" }
    : modelReadinessPresentation(form, suggestedModel, state, executable);
  const sameSelection = modelKey(state.selection) === modelKey(suggestedModel)
    && (strategyAdvisoryOnly || modeIsReal(form) || runtime.externalSelectionActive);
  const accepted = sameSelection && state.selectionSource === "accepted_recommendation";

  const hero = element("div", "ce-v4-model-recommendation-hero");
  const heroVisual = modelVisualNode(suggestedModel, { recommended: true, featured: true });
  const title = element("div", "ce-v4-model-recommendation-hero__title");
  title.append(
    element("span", "ce-v4-model-recommendation-hero__source", recommendationSource(state)),
    element("small", "", `Технический подбор модели · ${String(suggestedModel.provider || "МОДЕЛЬ").toUpperCase()}`),
    element("strong", "", String(suggestedModel.publicLabel || suggestedModel.model)),
  );
  const metrics = element("div", "ce-v4-model-recommendation-hero__metrics");
  const costMetric = element("span", "");
  costMetric.append(element("small", "", "Оценка цены"), element("strong", "", cost.text));
  const readinessMetric = element("span", "");
  readinessMetric.dataset.state = readiness.state;
  readinessMetric.append(element("small", "", "Готовность"), element("strong", "", readiness.text));
  metrics.append(costMetric, readinessMetric);
  if (heroVisual) hero.append(heroVisual);
  hero.append(title, metrics);

  const reasons = element("div", "ce-v4-model-recommendation__reasons");
  reasons.append(element("strong", "", "Почему"));
  const reasonList = element("ul");
  (reasonLines.length ? reasonLines : [recommendationReason(state.recommendation?.reasonCodes)])
    .forEach((line) => reasonList.append(element("li", "", line)));
  reasons.append(reasonList);

  const compromise = element("p", "ce-v4-model-recommendation__compromise");
  compromise.append(
    element("strong", "", "Компромисс: "),
    document.createTextNode(recommendationCompromise(suggestedModel, selectedModel)),
  );

  const details = element("details", "ce-v4-model-recommendation__why");
  details.append(element("summary", "", "Почему система предлагает эту модель?"));
  const detailBody = element("div", "ce-v4-model-recommendation__why-body");
  detailBody.append(
    element("p", "", `Источник: ${recommendationSource(state)}. Каталог: ${state.recommendation?.catalogVersion || "версия не получена"}.`),
  );
  if (warningLines.length) {
    const warnings = element("ul", "ce-v4-model-recommendation__warnings");
    warningLines.forEach((line) => warnings.append(element("li", "", line)));
    detailBody.append(element("strong", "", "Что нужно учесть"), warnings);
  } else {
    detailBody.append(element("p", "", "Критических предупреждений для текущей сцены нет."));
  }
  details.append(detailBody);
  if (strategyAdvisoryOnly) {
    detailBody.append(element(
      "p",
      "ce-v4-model-recommendation__strategy-note",
      "Для выбранного сценария модели показаны как совет и сравнение. Фактический запуск использует только recipe, разрешённый сервером для этой стратегии.",
    ));
  }

  const actions = element("div", "ce-v4-model-recommendation__actions");
  const apply = element(
    "button",
    "btn btn-secondary btn-small",
    accepted ? "Технический подбор принят" : "Применить технический подбор",
  );
  apply.type = "button";
  apply.dataset.ceV4ApplyModelRecommendation = "";
  apply.disabled = !selectable || accepted;
  actions.append(apply);

  if (selectedModel && modelKey(selectedModel) !== modelKey(suggestedModel)) {
    const comparison = element("details", "ce-v4-model-comparison");
    comparison.dataset.ceV4ModelComparison = "";
    comparison.append(element("summary", "", "Сравнить с моим выбором"));
    const comparisonGrid = element("div", "ce-v4-model-comparison__grid");
    comparisonGrid.append(
      comparisonCell("Системный подбор", suggestedModel, form, state),
      comparisonCell("Вы выбрали", selectedModel, form, state),
    );
    comparison.append(comparisonGrid);
    actions.append(comparison);
  }

  recommendation.append(hero, reasons, compromise, details, actions);
  recommendation.hidden = false;
  recommendation.dataset.state = strategyAdvisoryOnly
    ? "advisory"
    : executable ? "ready" : "blocked";
}

function selectedInputText(state) {
  const context = state?.context || {};
  const input = context.inputMode === "video"
    ? "готовое видео"
    : context.inputMode === "image"
      ? "фото"
      : "текст";
  const references = Number(context.referenceImageCount || 0);
  return `${input}${references ? ` · ${references} референс` : ""}`;
}

function modelLaunchBlocker(form, state, selectedModel) {
  if (selectedStrategyRow()) return "";
  if (!modeIsReal(form) && !runtime.externalSelectionActive) return "";
  if (!selectedModel) return "Выберите модель генерации.";
  if (!modelCanUseExistingLaunch(form, selectedModel)) {
    return translatedList(modelUnavailableCodes(state, selectedModel))[0]
      || "Безопасный маршрут этой модели ещё не подключён. Выберите другую модель.";
  }
  if (state?.selectionStatus?.blocked) {
    return translatedList(state.selectionStatus.unavailableReasonCodes || state.selectionStatus.reasonCodes)[0]
      || "Модель несовместима с текущими параметрами.";
  }
  return "";
}

function syncModelLaunchGuard(form, blocker) {
  const mode = form?.elements?.generation_mode;
  if (!(mode instanceof HTMLSelectElement)) return;
  if (blocker) {
    mode.setCustomValidity(blocker);
    mode.dataset.ceV4ModelBlocker = "true";
    form.dataset.ceV4ModelSelectionBlocked = "true";
  } else {
    if (mode.dataset.ceV4ModelBlocker === "true") mode.setCustomValidity("");
    delete mode.dataset.ceV4ModelBlocker;
    delete form.dataset.ceV4ModelSelectionBlocked;
  }
}

function summaryRow(label, value) {
  const row = element("div", "ce-v4-model-selection-summary__row");
  row.append(element("dt", "", label), element("dd", "", value));
  return row;
}

function renderSelectionSummary(form, state, selectedModel) {
  const body = q("[data-ce-v4-model-selection-summary-body]", form);
  if (!body) return;
  const strategy = selectedStrategyRow();
  if (strategy) {
    syncModelLaunchGuard(form, "");
    const title = element(
      "strong",
      "ce-v4-model-selection-summary__title",
      selectedModel
        ? `Предпочтение: ${String(selectedModel.publicLabel || selectedModel.model)}`
        : "Предпочтение модели не выбрано",
    );
    const badge = element(
      "span",
      "ce-v4-model-selection-summary__badge",
      "Совет · не маршрут запуска",
    );
    badge.dataset.state = "ready";
    const head = element("div", "ce-v4-model-selection-summary__head");
    head.append(title, badge);
    const list = element("dl", "ce-v4-model-selection-summary__list");
    list.append(
      summaryRow(
        "Предпочтение для сравнения",
        selectedModel ? `${selectedModel.provider} · ${selectedModel.model}` : "—",
      ),
      summaryRow("Стратегия", strategy.public_label),
      summaryRow("Фактический запуск", "Recipe стратегии подтверждает сервер"),
    );
    body.dataset.state = "advisory";
    body.replaceChildren(
      head,
      list,
      element(
        "p",
        "ce-v4-model-selection-summary__note",
        "Выбранная модель остаётся вашим советующим предпочтением и не блокирует стратегию. Цена, recipe и платный маршрут берутся только из серверного контракта стратегии.",
      ),
    );
    return;
  }
  if (!modeIsReal(form) && !runtime.externalSelectionActive) {
    syncModelLaunchGuard(form, "");
    body.dataset.state = "dry-run";
    body.replaceChildren(
      element("strong", "ce-v4-model-selection-summary__title", "Dry-run без медиафайла и списаний"),
      element("p", "ce-v4-model-selection-summary__note", "Выберите «Видео», «Фото товара» или карточку модели, чтобы подготовить платный режим. Сам запуск не произойдёт."),
    );
    return;
  }

  const blocker = modelLaunchBlocker(form, state, selectedModel);
  syncModelLaunchGuard(form, blocker);
  const cost = selectedModel ? modelCostPresentation(form, selectedModel, state) : { text: "—" };
  const readiness = selectedModel
    ? modelReadinessPresentation(form, selectedModel, state, modelCanUseExistingLaunch(form, selectedModel))
    : { state: "blocked", text: "модель не выбрана" };
  const context = state?.context || {};
  const nativeMode = String(form.elements?.generation_mode?.value || "");
  const spokenDialogue = runtime.repeatSettings
    ? context.spokenDialogue === true
    : nativeMode === "real_seedance";
  const generatedAudio = runtime.repeatSettings
    ? context.audio === true
    : nativeMode === "real_seedance";
  const title = element(
    "strong",
    "ce-v4-model-selection-summary__title",
    selectedModel ? String(selectedModel.publicLabel || selectedModel.model) : "Модель не выбрана",
  );
  const badge = element(
    "span",
    "ce-v4-model-selection-summary__badge",
    blocker ? "Запуск заблокирован" : "Выбор зафиксирован",
  );
  badge.dataset.state = blocker ? "blocked" : "ready";
  const head = element("div", "ce-v4-model-selection-summary__head");
  head.append(title, badge);
  const list = element("dl", "ce-v4-model-selection-summary__list");
  list.append(
    summaryRow("Источник выбора", SELECTION_SOURCE_COPY[state?.selectionSource] || "Выбрано вручную"),
    summaryRow("Провайдер · модель", selectedModel ? `${selectedModel.provider} · ${selectedModel.model}` : "—"),
    summaryRow("Длительность · формат", selectedModel?.contentKind === "photo"
      ? `фото · ${context.ratio || "1:1"} · ${context.resolution || "2K"}`
      : `${context.durationSeconds || "—"} сек. · ${context.ratio || "формат уточнится"} · ${context.resolution || "разрешение уточнится"}`),
    summaryRow("Звук", spokenDialogue ? "речь и звук" : generatedAudio ? "генерируемый звук" : "без сгенерированного звука"),
    summaryRow("Исходники", selectedInputText(state)),
    summaryRow("Оценка цены", cost.text),
    summaryRow("Техническая готовность", readiness.text),
  );
  const note = element(
    "p",
    "ce-v4-model-selection-summary__note",
    blocker
      ? `${blocker} Ваш выбор остаётся видимым; деньги не спишутся.`
      : "Цена и готовность будут сверены сервером ещё раз перед явным подтверждением оплаты.",
  );
  body.dataset.state = blocker ? "blocked" : "ready";
  body.replaceChildren(head, list, note);
}

function renderModelAdvisor(form) {
  const advisor = ensureModelAdvisor(form);
  const status = q("[data-ce-v4-model-advisor-status]", advisor);
  const recommendation = q("[data-ce-v4-model-recommendation]", advisor);
  const grid = q("[data-ce-v4-model-grid]", advisor);
  if (!status || !recommendation || !grid) return;
  syncContentKindChooser(form);
  qa("[data-ce-v4-model-filter]", advisor).forEach((button) => {
    const active = button.dataset.ceV4ModelFilter === runtime.modelFilter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });

  if (!runtime.catalog || !Array.isArray(runtime.catalog.models)) {
    const failed = runtime.catalogStatus === "error";
    if (failed) {
      const retry = element(
        "button",
        "btn ce-v4-model-catalog-retry",
        "Повторить загрузку каталога",
      );
      retry.type = "button";
      retry.dataset.ceV4ModelCatalogRetry = "";
      grid.replaceChildren(retry);
    } else {
      grid.replaceChildren();
    }
    recommendation.hidden = true;
    syncModelLaunchGuard(form, "");
    const summary = q("[data-ce-v4-model-selection-summary-body]", form);
    if (summary) {
      summary.dataset.state = failed ? "blocked" : "loading";
      const summaryChildren = [
        element("strong", "ce-v4-model-selection-summary__title", failed
          ? "Каталог моделей не ответил"
          : "Загружаем точный каталог…"),
        element("p", "ce-v4-model-selection-summary__note", "Исходный режим формы сохранён. Мы не выдумываем модель, цену или готовность без ответа сервера."),
      ];
      if (failed) {
        const summaryRetry = element(
          "button",
          "btn ce-v4-model-catalog-retry",
          "Повторить загрузку каталога",
        );
        summaryRetry.type = "button";
        summaryRetry.dataset.ceV4ModelCatalogRetry = "";
        summaryChildren.push(summaryRetry);
      }
      summary.replaceChildren(...summaryChildren);
    }
    status.dataset.state = failed ? "error" : "loading";
    status.textContent = failed
      ? "Каталог моделей сейчас недоступен. Повторите загрузку — форма и платный запуск не изменены."
      : "Загружаем доступные модели…";
    return;
  }

  const currentIdentity = selectedModelForForm(form)
    || modelIdentityForMode(form.elements?.generation_mode?.value);
  const currentModel = runtime.catalog.models.find((model) => modelKey(model) === modelKey(currentIdentity));
  const strategyAdvisoryOnly = Boolean(selectedStrategyRow());
  if (currentModel && !strategyAdvisoryOnly) syncExactModelControls(form, currentModel);
  if (!runtime.recommendationState) {
    runtime.recommendationState = createGenerationModelRecommendationState({
      catalogSnapshot: runtime.catalog,
      context: modelContext(form),
      selection: currentIdentity,
      selectionSource: currentIdentity ? "form_default" : null,
      manualLock: Boolean(currentIdentity),
    });
  } else {
    runtime.recommendationState = generationModelRecommendationReducer(
      runtime.recommendationState,
      {
        type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.RECOMMEND,
        catalogSnapshot: runtime.catalog,
        context: modelContext(form),
      },
    );
  }

  const state = runtime.recommendationState;
  const models = [...runtime.catalog.models].sort((left, right) => {
    const leftKey = modelKey(left);
    const rightKey = modelKey(right);
    const recommendedKey = modelKey(state.recommendation?.recommended);
    const selectedKey = modelKey(state.selection);
    const rank = (key) => key === selectedKey ? 0 : key === recommendedKey ? 1 : 2;
    return rank(leftKey) - rank(rightKey)
      || Number(modelCanUseExistingLaunch(form, right)) - Number(modelCanUseExistingLaunch(form, left))
      || String(left.publicLabel || left.model).localeCompare(String(right.publicLabel || right.model), "ru");
  });
  const visibleModels = visibleModelsForFilter(models, state, form);
  grid.replaceChildren(...groupedModelCards(form, visibleModels, state));

  const suggested = state.recommendation?.recommended;
  const suggestedModel = runtime.catalog.models.find((model) => modelKey(model) === modelKey(suggested));
  const selectedModel = runtime.catalog.models.find((model) => modelKey(model) === modelKey(state.selection));
  if (!strategyAdvisoryOnly) syncExactModelControls(form, selectedModel);
  renderRecommendationPanel(form, recommendation, state, suggestedModel, selectedModel);
  renderSelectionSummary(form, state, selectedModel);
  const selectionActive = strategyAdvisoryOnly
    ? Boolean(selectedModel)
    : modeIsReal(form) || runtime.externalSelectionActive;
  const explicitDryRun = String(form.elements?.generation_mode?.value || "") === "mock";
  status.dataset.state = !selectionActive ? "advisory" : state.manualLock ? "manual" : "advisory";
  status.dataset.strategyAdvisoryOnly = strategyAdvisoryOnly ? "true" : "false";
  status.textContent = strategyAdvisoryOnly
    ? "Система показывает несколько технически подходящих моделей для сравнения. Для этого сценария карточки носят рекомендательный характер; платно запускается только серверно подтверждённый recipe."
    : !selectionActive
    ? explicitDryRun
      ? "Вы явно выбрали dry-run. Он создаст только задачи без медиафайла и списания."
      : "Способ создания ещё не выбран. Ни dry-run, ни платная генерация не включатся автоматически."
    : selectedModel
      ? state.manualLock
        ? `Ваш выбор: ${selectedModel.publicLabel || selectedModel.model}. Он зафиксирован: новый технический подбор не заменит его без вашей команды.`
        : `Технический подбор: ${selectedModel.publicLabel || selectedModel.model}. Применение требует вашего действия.`
      : "Выберите доступную модель. Технический подбор носит только советующий характер.";
}

// Однократная ошибка каталога больше не превращается в мёртвую страницу до
// F5: сначала автоматические повторы с нарастающей паузой, затем явная кнопка.
const CATALOG_RETRY_DELAYS_MS = Object.freeze([2_000, 5_000, 15_000]);

function scheduleCatalogRetry(kind) {
  const countKey = kind === "strategy"
    ? "strategyCatalogRetryCount"
    : "catalogRetryCount";
  const statusKey = kind === "strategy" ? "strategyCatalogStatus" : "catalogStatus";
  const attempt = runtime[countKey];
  if (attempt >= CATALOG_RETRY_DELAYS_MS.length) return;
  runtime[countKey] = attempt + 1;
  window.setTimeout(() => {
    const form = runtime.form;
    if (!form?.isConnected || runtime[statusKey] !== "error") return;
    runtime[statusKey] = "idle";
    if (kind === "strategy") void loadStrategyCatalog(form);
    else void loadModelCatalog(form);
  }, CATALOG_RETRY_DELAYS_MS[attempt]);
}

async function loadModelCatalog(form) {
  if (runtime.catalog) {
    renderModelAdvisor(form);
    return;
  }
  if (runtime.catalogStatus === "loading") return;
  const request = ++runtime.catalogRequest;
  runtime.catalogStatus = "loading";
  renderModelAdvisor(form);
  try {
    const api = window.ContentEngineWorkspaceRuntime?.getApi?.();
    if (!api || typeof api.generationModelCatalog !== "function") {
      throw new Error("generation_model_catalog_unavailable");
    }
    const response = await api.generationModelCatalog();
    const catalog = response?.catalog || response;
    if (
      request !== runtime.catalogRequest
      || !catalog
      || typeof catalog.version !== "string"
      || !Array.isArray(catalog.models)
    ) return;
    runtime.catalog = catalog;
    runtime.catalogSignals = response?.signals || response?.recommendation_context || null;
    runtime.catalogStatus = "ready";
    runtime.catalogRetryCount = 0;
    runtime.recommendationState = null;
    window.ContentEngineWorkspaceRuntime?.setGenerationModelCatalog?.(catalog);
    const targetForm = form.isConnected ? form : runtime.form;
    if (!targetForm?.isConnected) return;
    const pending = runtime.pendingRepeatSettings;
    runtime.pendingRepeatSettings = null;
    if (
      !pending
      || pending.form !== targetForm
      || !applyRepeatedSettings(targetForm, pending.detail)
    ) {
      renderModelAdvisor(targetForm);
    }
  } catch {
    if (request !== runtime.catalogRequest) return;
    runtime.catalogStatus = "error";
    scheduleCatalogRetry("model");
    const targetForm = form.isConnected ? form : runtime.form;
    if (targetForm?.isConnected) renderModelAdvisor(targetForm);
  }
}

async function loadStrategyCatalog(form) {
  if (runtime.strategyCatalog) {
    if (!runtime.strategyState) {
      runtime.strategyState = createGenerationStrategyViewState(
        extractedStrategyCatalog(runtime.strategyCatalog),
      );
    }
    renderStrategyView(form);
    return;
  }
  if (runtime.strategyCatalogStatus === "loading") return;
  const request = ++runtime.strategyCatalogRequest;
  runtime.strategyCatalogStatus = "loading";
  try {
    const api = window.ContentEngineWorkspaceRuntime?.getApi?.();
    if (!api || typeof api.generationStrategyCatalog !== "function") {
      throw new Error("generation_strategy_catalog_unavailable");
    }
    const response = await api.generationStrategyCatalog();
    const catalog = response?.catalog;
    if (request !== runtime.strategyCatalogRequest) return;
    const strategyState = createGenerationStrategyViewState(
      extractedStrategyCatalog(catalog),
    );
    if (strategyState.catalog_status !== "ready") {
      throw Object.assign(
        new Error(strategyState.catalog_error?.code || "generation_strategy_catalog_invalid"),
        strategyState.catalog_error || {},
      );
    }
    runtime.strategyCatalog = catalog;
    runtime.strategyCatalogStatus = "ready";
    runtime.strategyCatalogRetryCount = 0;
    runtime.strategyState = strategyState;
    const targetForm = form.isConnected ? form : runtime.form;
    if (!targetForm?.isConnected) return;
    renderStrategyView(targetForm);
    const pendingStrategy = runtime.pendingStrategyRestore;
    if (pendingStrategy?.form === targetForm) {
      applyStrategyRestore(targetForm, pendingStrategy.values);
    }
  } catch (error) {
    if (request !== runtime.strategyCatalogRequest) return;
    const failure = generationStrategyCatalogFailure(error);
    // Only bounded, operator-safe strings cross this diagnostic boundary. Do
    // not log the response, stack, request, session or server details.
    console.warn("generation strategy catalog load failed", {
      code: failure.code,
      message: failure.message,
    });
    runtime.strategyCatalogStatus = "error";
    scheduleCatalogRetry("strategy");
    runtime.strategyState = createGenerationStrategyViewState({
      ok: false,
      catalog: null,
      error: { code: failure.code, field: failure.field },
    });
    const targetForm = form.isConnected ? form : runtime.form;
    if (targetForm?.isConnected) renderStrategyView(targetForm);
  }
}

function routePath() {
  const apiRoute = window.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/gu, "/").replace(/\/$/u, "") || "/";
}

function generationSessionContext(form) {
  const raw = String(window.location.hash || "#/workspace/generation").replace(/^#/, "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  const projectId = String(new URLSearchParams(query).get("project_id") || "")
    .trim().toLowerCase();
  const handoffSku = String(form?.dataset?.generationHandoffSku || "")
    .trim().toLowerCase();
  const handoffProductName = String(
    form?.dataset?.generationHandoffProductName || "",
  ).replace(/\s+/gu, " ").trim().toLowerCase();
  return `${projectId}|${handoffSku}|${handoffProductName}`;
}

function readSession(form) {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(SESSION_KEY) || "{}");
    if (
      !value
      || typeof value !== "object"
      || value.context !== generationSessionContext(form)
    ) return {};
    return value;
  } catch {
    return {};
  }
}

function writeSession(form, step, maxVisited) {
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      context: generationSessionContext(form),
      step,
      maxVisited,
      updatedAt: Date.now(),
    }));
  } catch {
    // Session memory is a convenience. The guided form remains usable without it.
  }
}

function stepIndex(value) {
  if (Number.isInteger(value)) return Math.max(0, Math.min(STEPS.length - 1, value));
  const index = STEPS.findIndex((step) => step.key === String(value || ""));
  return index >= 0 ? index : 0;
}

function contains(node, selector) {
  return Boolean(node?.matches?.(selector) || node?.querySelector?.(selector));
}

function classifyNode(node, fallback = "mode") {
  if (!node) return fallback;
  if (
    node.id === "generation-submit"
    || node.id === "generation-readiness"
    || node.id === "generation-spec-card"
    || node.id === "real-generation-confirmation"
    || contains(node, "#generation-submit, #generation-readiness, #generation-spec-card, #real-generation-confirmation, [name=\"real_spend_confirmation\"]")
  ) return "launch";
  if (
    node.id === "generation-draft-status"
    || contains(node, '[name="generation_mode"], [name="duration_seconds"], [name="campaign_id"]')
    || node.matches?.("#generation-duration-field, #generation-mock-explanation, #generation-campaign-field")
  ) return "mode";
  if (
    node.id === "generation-product-identity-note"
    || contains(node, '[name="sku"], [name="product_name"], [name="product_category"]')
  ) return "product";
  if (contains(node, '[name="platform"], [name="destination_ref"], [name="assignee_id"], [name="payout_rub"], [name="count"], [name="format"]')) {
    return "destination";
  }
  if (
    node.id === "generation-brief-assist"
    || node.id === "generation-learning-status"
    || node.id === "generation-repair-status"
    || contains(node, '[name="brief"], #generation-brief-assist, #generation-learning-status, #generation-repair-status')
  ) return "brief";
  if (
    node.id === "generation-strategy-assets"
    || contains(node, '[name="media_id"], [name="primary_media_id"]')
    || contains(node, 'a[href*="/workspace/media"]')
  ) return "media";
  return fallback;
}

function createStepPanel(step, index) {
  const panel = element("section", "ce-v4-generation-guided__panel");
  panel.id = `ce-v4-generation-panel-${step.key}`;
  panel.dataset.ceV4GenerationPanel = step.key;
  panel.setAttribute("role", "region");
  panel.setAttribute("aria-labelledby", `${panel.id}-title`);

  const heading = element("h3", "ce-v4-generation-guided__panel-title", `${index + 1}. ${step.label}`);
  heading.id = `${panel.id}-title`;
  heading.tabIndex = -1;
  const hint = element("p", "ce-v4-generation-guided__panel-hint", step.hint);
  const error = element("p", "ce-v4-generation-guided__error");
  error.dataset.ceV4GenerationError = "";
  error.setAttribute("role", "alert");
  error.hidden = true;
  const content = element("div", "ce-v4-generation-guided__panel-content");
  content.dataset.ceV4GenerationContent = step.key;

  panel.append(heading, hint, error, content);
  return panel;
}

function createSummary() {
  const summary = element("div", "ce-v4-generation-guided__summary");
  summary.dataset.ceV4GenerationSummary = "";
  const intro = element("p", "ce-v4-generation-guided__summary-intro", "Проверьте пять строк. Если всё верно — запускайте.");
  const list = element("dl", "ce-v4-generation-guided__summary-list");
  [
    ["mode", "Результат"],
    ["product", "Товар"],
    ["destination", "Назначение"],
    ["brief", "Замысел"],
    ["media", "Исходники"],
  ].forEach(([key, label]) => {
    const row = element("div", "ce-v4-generation-guided__summary-row");
    row.append(
      element("dt", "", label),
      element("dd", "", "Не заполнено"),
    );
    row.querySelector("dd").dataset.ceV4GenerationSummaryValue = key;
    list.append(row);
  });
  const status = element("p", "ce-v4-generation-guided__launch-status");
  status.dataset.ceV4GenerationLaunchStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  summary.append(intro, list, status);
  return summary;
}

function createShell(form) {
  const shell = element("section", "ce-v4-generation-guided");
  shell.dataset.ceV4GenerationGuidedShell = "";

  const intro = element("header", "ce-v4-generation-guided__intro");
  const introCopy = element("div", "ce-v4-generation-guided__intro-copy");
  introCopy.append(
    element("p", "ce-v4-generation-guided__eyebrow", "ВИДЕО ПО СТРАТЕГИИ · С НУЛЯ"),
    element("h2", "", "Соберите новый ролик по своей задаче"),
    element("p", "", "Это один последовательный конструктор: модель и формат, товар, аудитория, замысел, исходники, проверка и запуск. Рекомендации ИИ-центра остаются черновиком до решения человека."),
  );
  const position = element("span", "ce-v4-generation-guided__position", `Шаг 1 из ${STEPS.length}`);
  position.dataset.ceV4GenerationPosition = "";
  position.setAttribute("aria-live", "polite");
  intro.append(introCopy, position);

  const nav = element("nav", "ce-v4-generation-guided__steps");
  nav.setAttribute("aria-label", "Этапы нового запуска");
  const stepList = element("ol");
  STEPS.forEach((step, index) => {
    const item = element("li");
    const button = element("button", "ce-v4-generation-guided__step");
    button.type = "button";
    button.dataset.ceV4GenerationTarget = step.key;
    button.setAttribute("aria-controls", `ce-v4-generation-panel-${step.key}`);
    button.setAttribute("aria-label", `${index + 1}. ${step.label}`);
    button.append(
      element("span", "ce-v4-generation-guided__step-number", String(index + 1).padStart(2, "0")),
      element("strong", "", step.label),
    );
    item.append(button);
    stepList.append(item);
  });
  nav.append(stepList);

  const meter = element("div", "ce-v4-generation-guided__meter");
  meter.setAttribute("aria-hidden", "true");
  meter.append(element("span"));

  const viewport = element("div", "ce-v4-generation-guided__viewport");
  viewport.dataset.ceV4GenerationViewport = "";
  STEPS.forEach((step, index) => viewport.append(createStepPanel(step, index)));
  q('[data-ce-v4-generation-content="launch"]', viewport)?.append(createSummary());

  const footer = element("footer", "ce-v4-generation-guided__actions");
  const back = element("button", "btn btn-secondary ce-v4-generation-guided__back", "Назад");
  back.type = "button";
  back.dataset.ceV4GenerationBack = "";
  const actionHint = element("span", "ce-v4-generation-guided__action-hint", "Заполните только поля этого шага");
  actionHint.dataset.ceV4GenerationActionHint = "";
  const next = element("button", "btn ce-v4-generation-guided__next", "Далее");
  next.type = "button";
  next.dataset.ceV4GenerationNext = "";
  footer.append(back, actionHint, next);

  shell.append(intro, nav, meter, viewport, footer);
  form.prepend(shell);
  return shell;
}

function panelFor(form, key) {
  return q(`[data-ce-v4-generation-panel="${key}"]`, form);
}

function contentFor(form, key) {
  return q(`[data-ce-v4-generation-content="${key}"]`, form);
}

function organizeOriginalNodes(form, shell, originalNodes, submit) {
  let currentKey = "mode";
  originalNodes.forEach((node) => {
    if (
      node === shell
      || node === submit
      || node.matches?.("[data-generation-intake-v4]")
    ) return;
    currentKey = classifyNode(node, currentKey);
    (contentFor(form, currentKey) || contentFor(form, "mode"))?.append(node);
  });
  const footer = q(".ce-v4-generation-guided__actions", shell);
  if (submit && footer) {
    submit.classList.add("ce-v4-generation-guided__submit");
    footer.append(submit);
  }
}

function exposeProviderReadinessControl(form) {
  const control = q('[data-action="check-runway-readiness"]', form);
  if (!(control instanceof HTMLButtonElement)) return;
  // Легаси-однопуск (Runway/фото). При выбранной стратегии запуск и цену ведёт
  // контур самой стратегии, а этот блок только путал: кнопка со старым
  // recipe и примечание «без сгенерированной речи» на экране «Создания»
  // (боевые скрины 25.08.2026). Прячем оба, пока стратегия выбрана.
  const strategySelected = Boolean(selectedStrategyRow());
  const note = q("#real-generation-note", form);
  if (note instanceof HTMLElement) note.hidden = strategySelected;
  if (strategySelected) {
    control.hidden = true;
    control.setAttribute("tabindex", "-1");
    control.setAttribute("aria-hidden", "true");
    return;
  }
  control.hidden = false;
  control.removeAttribute("tabindex");
  control.setAttribute("aria-hidden", "false");
  control.classList.add("ce-v4-generation-guided__preflight");
}

function adoptDirectChildren(form, shell) {
  const loose = [...form.children].filter((node) => (
    node !== shell
    && !node.matches?.("[data-generation-intake-v4]")
  ));
  loose.forEach((node) => {
    if (node.id === "generation-submit") {
      const current = q("#generation-submit", shell);
      node.classList.add("ce-v4-generation-guided__submit");
      if (current && current !== node) current.replaceWith(node);
      else q(".ce-v4-generation-guided__actions", shell)?.append(node);
      return;
    }
    const key = classifyNode(node, "brief");
    (contentFor(form, key) || contentFor(form, "brief"))?.append(node);
  });
}

function panelControls(panel) {
  return qa("input, select, textarea", panel).filter((control) => {
    if (control.disabled || control.type === "hidden") return false;
    let ancestor = control;
    while (ancestor && ancestor !== panel) {
      if (ancestor.hidden) return false;
      ancestor = ancestor.parentElement;
    }
    return true;
  });
}

function modeIsReal(form) {
  return ["real_photo", "real_seedance", "real_gen4"].includes(
    String(form.elements?.generation_mode?.value || ""),
  );
}

function firstInvalidControl(panel) {
  return panelControls(panel).find((control) => (
    typeof control.checkValidity === "function" && !control.checkValidity()
  )) || null;
}

function mediaSelectionValid(form, panel) {
  // Compact Product Swap физически переносит те же product-photo nodes в
  // sibling shell внутри формы. Panel-only поиск объявлял шаг пустым, хотя
  // canonical strategy selection уже видел #7 и остальные exact media IDs.
  // Только этот маршрут читает form-wide; остальные guided-стратегии сохраняют
  // прежнюю область media panel и свои собственные ограничения.
  const productSwap = runtime.strategyState?.selected_strategy_id
    === "viral_product_swap";
  const scope = productSwap ? form : panel;
  const busyLocked = form?.dataset?.busy === "true";
  const available = qa('input[name="media_id"]', scope).filter((control) => (
    !control.disabled
    || (busyLocked && control.dataset.wasDisabled === "false")
  ));
  return available.length > 0 && available.some((control) => control.checked);
}

function requiredTextControl(form, name) {
  const control = form?.elements?.[name];
  if (!(control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement)) {
    return null;
  }
  return String(control.value || "").trim() ? null : control;
}

function controlLabel(control) {
  const label = control.closest("label");
  return String(
    q(":scope > span", label)?.textContent
    || control.getAttribute("aria-label")
    || control.name
    || "обязательное поле",
  ).replace(/\s*\*\s*$/u, "").trim();
}

function clearPanelError(panel) {
  const error = q("[data-ce-v4-generation-error]", panel);
  if (!error) return;
  error.hidden = true;
  error.textContent = "";
}

function showPanelError(panel, message) {
  const error = q("[data-ce-v4-generation-error]", panel);
  if (!error) return;
  error.textContent = message;
  error.hidden = false;
}

function panelValidity(form, index) {
  const step = STEPS[index];
  const panel = panelFor(form, step.key);
  if (!panel) return { valid: true, panel: null, control: null, message: "" };
  if (step.key === "product") {
    const missingProduct = requiredTextControl(form, "sku")
      || requiredTextControl(form, "product_name");
    if (missingProduct) {
      return {
        valid: false,
        panel,
        control: missingProduct,
        message: missingProduct.name === "sku"
          ? "Укажите точный артикул товара — одного названия недостаточно."
          : "Укажите точное название товара — одного артикула недостаточно.",
      };
    }
  }
  if (step.key === "brief" && modeIsReal(form)) {
    const missingBrief = requiredTextControl(form, "brief");
    if (missingBrief) {
      return {
        valid: false,
        panel,
        control: missingBrief,
        message: "Опишите замысел ролика. Пустое описание нельзя отправить в платную генерацию.",
      };
    }
  }
  const invalid = firstInvalidControl(panel);
  if (invalid) {
    return {
      valid: false,
      panel,
      control: invalid,
      message: `Заполните поле «${controlLabel(invalid)}».`,
    };
  }
  if (step.key === "media" && !mediaSelectionValid(form, panel)) {
    return {
      valid: false,
      panel,
      control: q('input[name="media_id"]:not(:disabled), a[href*="/workspace/media"]', panel),
      message: "Выберите хотя бы один точный исходник товара. Без него нельзя создать ни dry-run задачу, ни платный результат.",
    };
  }
  if (
    step.key === "media"
    && runtime.strategyState?.selected_strategy_id
    && !generationStrategySelection(form)
  ) {
    const fieldset = q("#generation-strategy-assets", panel);
    return {
      valid: false,
      panel,
      control: firstInvalidControl(fieldset) || fieldset,
      message: "Для выбранной стратегии укажите все обязательные исходники, параметры результата и подтверждения прав.",
    };
  }
  return { valid: true, panel, control: null, message: "" };
}

function firstInvalidStepBefore(form, requestedIndex) {
  const boundary = Math.max(0, Math.min(STEPS.length - 1, stepIndex(requestedIndex)));
  for (let index = 0; index < boundary; index += 1) {
    if (!panelValidity(form, index).valid) return index;
  }
  return -1;
}

function compact(value, limit = 92) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  if (!text) return "Не заполнено";
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function selectLabel(control) {
  if (!(control instanceof HTMLSelectElement)) return "";
  return control.selectedOptions?.[0]?.textContent?.trim() || control.value || "";
}

function summaryValues(form) {
  const mode = form.elements?.generation_mode;
  const strategy = selectedStrategyRow();
  const selectedModel = runtime.catalog?.models?.find(
    (model) => modelKey(model) === modelKey(runtime.recommendationState?.selection),
  );
  const sku = compact(form.elements?.sku?.value, 36);
  const productName = compact(form.elements?.product_name?.value, 54);
  const platform = selectLabel(form.elements?.platform);
  const destination = compact(form.elements?.destination_ref?.value, 54);
  const brief = compact(form.elements?.brief?.value, 110);
  const mediaCount = qa('input[name="media_id"]:checked:not(:disabled)', form).length;
  const strategyAssets = strategy ? strategyAssetsForForm(form, strategy) : [];
  return {
    mode: compact(
      strategy
        ? strategy.public_label
        : [selectLabel(mode), selectedModel?.publicLabel].filter(Boolean).join(" · "),
      110,
    ),
    product: productName === "Не заполнено" && sku === "Не заполнено"
      ? "Не заполнено"
      : [productName, sku].filter((value) => value !== "Не заполнено").join(" · "),
    destination: [platform, destination].filter((value) => value && value !== "Не заполнено").join(" · ") || "Не заполнено",
    brief,
    media: strategy
      ? strategyAssets.length
        ? `${strategyAssets.length} точных файлов для стратегии`
        : "Не выбраны"
      : mediaCount
        ? `${mediaCount} ${mediaCount === 1 ? "исходник" : "исходника"}`
        : "Не выбраны",
  };
}

function syncSummary(form) {
  const values = summaryValues(form);
  Object.entries(values).forEach(([key, value]) => {
    const target = q(`[data-ce-v4-generation-summary-value="${key}"]`, form);
    if (target && target.textContent !== value) target.textContent = value;
  });
  const submit = q("#generation-submit", form);
  const status = q("[data-ce-v4-generation-launch-status]", form);
  if (status) {
    const ready = submit && !submit.disabled && form.dataset.busy !== "true";
    const busy = form.dataset.busy === "true";
    const preflightPhase = submit?.dataset.launchPhase === "preflight";
    const rawBlocker = String(submit?.dataset.launchBlocker || "").trim();
    const blocker = rawBlocker ? compact(rawBlocker, 240) : "";
    status.dataset.state = ready && !preflightPhase
      ? "ready"
      : busy
        ? "working"
        : "pending";
    const copy = ready && preflightPhase
      ? "Следующий шаг бесплатный: портал подготовит точное ТЗ и проверит стоимость. Генерация не запустится и деньги не спишутся."
      : ready
        ? modeIsReal(form)
          ? "Всё готово. Следующее нажатие отправит один подтверждённый платный запуск."
          : "Готов только dry-run: он создаст задачи, но не создаст видео или другой медиафайл. Для ролика вернитесь в «Режим и бюджет» и выберите платный видеорежим."
      : busy
        ? "Портал проверяет техническое ТЗ. Не нажимайте запуск повторно."
        : blocker || "Заполните обязательное поле текущего шага.";
    if (status.textContent !== copy) status.textContent = copy;
  }
}

function syncCompletion(form) {
  const current = stepIndex(form.dataset.ceV4GenerationStep);
  STEPS.forEach((step, index) => {
    const button = q(`[data-ce-v4-generation-target="${step.key}"]`, form);
    if (!button) return;
    const validity = index < STEPS.length - 1
      ? panelValidity(form, index)
      : null;
    const complete = validity
      ? validity.valid
      : Boolean(q("#generation-submit", form) && !q("#generation-submit", form).disabled);
    // Ошибка navigation-гейта — про текущее состояние, а не история. Compact
    // Product Swap может сделать media panel валидной через sibling shell;
    // после следующего sync старый generic alert обязан исчезнуть. Реальная
    // strategy-specific ошибка остаётся: invalid panel здесь не очищается.
    if (validity?.valid) clearPanelError(validity.panel);
    button.classList.toggle("is-complete", complete);
    if (index === current) button.classList.remove("is-complete");
  });
}

function scheduleSync(form) {
  window.queueMicrotask(() => {
    if (!form.isConnected) return;
    exposeProviderReadinessControl(form);
    if (runtime.catalog) renderModelAdvisor(form);
    syncSummary(form);
    syncCompletion(form);
  });
  window.requestAnimationFrame(() => {
    if (!form.isConnected) return;
    exposeProviderReadinessControl(form);
    if (runtime.catalog) renderModelAdvisor(form);
    syncSummary(form);
    syncCompletion(form);
  });
}

function setStep(form, requestedIndex, { focus = false } = {}) {
  const index = stepIndex(requestedIndex);
  const maxVisited = Math.max(
    index,
    Number(form.dataset.ceV4GenerationMaxVisited) || 0,
  );
  form.setAttribute(STEP_ATTRIBUTE, STEPS[index].key);
  form.dataset.ceV4GenerationMaxVisited = String(maxVisited);

  STEPS.forEach((step, panelIndex) => {
    const active = panelIndex === index;
    const panel = panelFor(form, step.key);
    if (panel) {
      panel.hidden = !active;
      panel.inert = !active;
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    }
    const button = q(`[data-ce-v4-generation-target="${step.key}"]`, form);
    if (button) {
      button.disabled = panelIndex > maxVisited;
      if (active) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    }
  });

  const position = q("[data-ce-v4-generation-position]", form);
  if (position) position.textContent = `Шаг ${index + 1} из ${STEPS.length}`;
  const meter = q(".ce-v4-generation-guided__meter > span", form);
  if (meter) meter.style.width = `${((index + 1) / STEPS.length) * 100}%`;

  const back = q("[data-ce-v4-generation-back]", form);
  const next = q("[data-ce-v4-generation-next]", form);
  const submit = q("#generation-submit", form);
  if (back) back.hidden = index === 0;
  if (next) next.hidden = index === STEPS.length - 1;
  if (submit) {
    submit.hidden = index !== STEPS.length - 1;
    submit.setAttribute("aria-hidden", index === STEPS.length - 1 ? "false" : "true");
  }
  const actionHint = q("[data-ce-v4-generation-action-hint]", form);
  if (actionHint) {
    actionHint.textContent = index === STEPS.length - 1
      ? "Запуск доступен только после всех обязательных проверок"
      : STEPS[index].hint;
  }

  writeSession(form, STEPS[index].key, maxVisited);
  syncSummary(form);
  syncCompletion(form);

  if (focus) {
    const panel = panelFor(form, STEPS[index].key);
    panel?.scrollTo?.({ top: 0, behavior: "auto" });
    q(".ce-v4-generation-guided__panel-title", panel)?.focus({ preventScroll: true });
  }
}

function reportInvalid(form, result, index) {
  setStep(form, index, { focus: false });
  if (result.panel) showPanelError(result.panel, result.message);
  window.requestAnimationFrame(() => {
    if (!form.isConnected) return;
    if (result.control instanceof HTMLElement) {
      result.control.focus({ preventScroll: false });
      result.control.reportValidity?.();
    } else {
      q(".ce-v4-generation-guided__panel-title", result.panel)?.focus({ preventScroll: true });
    }
  });
}

function moveTo(form, requestedIndex) {
  const current = stepIndex(form.dataset.ceV4GenerationStep);
  const target = stepIndex(requestedIndex);
  if (target > current) {
    for (let index = current; index < target; index += 1) {
      const result = panelValidity(form, index);
      if (!result.valid) {
        reportInvalid(form, result, index);
        return false;
      }
      clearPanelError(result.panel);
    }
    form.dispatchEvent(new CustomEvent(
      "contentengine:generation-guided-step-committed",
      {
        bubbles: true,
        detail: {
          from: STEPS[current].key,
          to: STEPS[target].key,
        },
      },
    ));
  }
  setStep(form, target, { focus: true });
  return true;
}

function applyModelIdentity(form, identity, {
  acceptRecommendation = false,
  preserveRepeatSettings = false,
} = {}) {
  const model = runtime.catalog?.models?.find((entry) => modelKey(entry) === modelKey(identity));
  const mode = modeForModel(model, form);
  const modeSelect = form?.elements?.generation_mode;
  if (!model || !modelCanUseExistingLaunch(form, model) || !mode || !(modeSelect instanceof HTMLSelectElement)) {
    renderModelAdvisor(form);
    return false;
  }

  runtime.recommendationState = generationModelRecommendationReducer(
    runtime.recommendationState,
    acceptRecommendation
      ? { type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.ACCEPT_RECOMMENDATION }
      : {
          type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.SELECT_MANUAL,
          selection: { provider: model.provider, model: model.model },
        },
  );
  runtime.externalSelectionActive = false;
  if (!preserveRepeatSettings) runtime.repeatSettings = null;
  syncExactModelControls(form, model);
  runtime.applyingModel = true;
  modeSelect.value = mode;
  modeSelect.dispatchEvent(new Event("change", { bubbles: true }));
  runtime.applyingModel = false;
  if (form.elements?.real_spend_confirmation?.checked) {
    form.elements.real_spend_confirmation.checked = false;
    form.elements.real_spend_confirmation.dispatchEvent(new Event("input", { bubbles: true }));
  }
  syncExactModelControls(form, model, { emit: true });
  renderModelAdvisor(form);
  scheduleSync(form);
  return true;
}

function applyStrategyAdvisoryModel(form, identity, {
  acceptRecommendation = false,
} = {}) {
  if (!selectedStrategyRow() || !runtime.recommendationState) return false;
  const model = runtime.catalog?.models?.find(
    (entry) => modelKey(entry) === modelKey(identity),
  );
  if (!model || model.enabled !== true) {
    renderModelAdvisor(form);
    return false;
  }
  runtime.recommendationState = generationModelRecommendationReducer(
    runtime.recommendationState,
    acceptRecommendation
      ? { type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.ACCEPT_RECOMMENDATION }
      : {
          type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.SELECT_MANUAL,
          selection: { provider: model.provider, model: model.model },
        },
  );
  renderModelAdvisor(form);
  return true;
}

function chooseContentKind(form, kind) {
  if (kind === "photo") {
    return applyModelIdentity(form, LEGACY_MODEL_BY_MODE.real_photo);
  }
  if (kind === "video") {
    const current = String(form.elements?.generation_mode?.value || "");
    const mode = ["real_gen4", "real_seedance"].includes(current)
      ? current
      : "real_gen4";
    return applyModelIdentity(form, LEGACY_MODEL_BY_MODE[mode]);
  }
  return false;
}

function setRepeatedNativeValue(control, value) {
  if (!control || value === undefined || value === null || value === "") return false;
  const normalized = String(value);
  if (control instanceof HTMLSelectElement) {
    const option = [...control.options].find((item) => item.value === normalized && !item.disabled);
    if (!option) return false;
  }
  if (!(control instanceof HTMLInputElement) && !(control instanceof HTMLSelectElement)) return false;
  if (control.value === normalized) return true;
  control.value = normalized;
  control.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

function refreshRepeatedSetting(form, control) {
  if (!runtime.repeatSettings || !control) return;
  const next = { ...runtime.repeatSettings };
  if (control.name === "duration_seconds") {
    const duration = Number(control.value);
    next.durationSeconds = Number.isFinite(duration) && duration > 0 ? duration : null;
  } else if (control.name === "format") {
    next.ratio = /^\d+:\d+$/u.test(String(control.value || "")) ? String(control.value) : "";
  } else if (control.name === "generation_resolution") {
    next.resolution = String(control.value || "").trim();
  } else if (control.name === "generation_audio") {
    next.audio = String(control.value || "") === "true";
  } else if (control.name === "generation_last_frame") {
    next.lastFrame = control.checked === true;
  } else if (control.name === "generation_reference_url") {
    next.inputMode = String(control.value || "").trim()
      ? "video"
      : qa('input[name="media_id"]:checked:not(:disabled)', form).length
        ? "image"
        : "text";
  } else if (control.name === "media_id") {
    const references = qa('input[name="media_id"]:checked:not(:disabled)', form).length;
    next.referenceCount = references;
    if (next.inputMode !== "video") next.inputMode = references ? "image" : "text";
  } else {
    return;
  }
  runtime.repeatSettings = Object.freeze(next);
}

function normalizeRepeatSettings(value) {
  const detail = value && typeof value === "object" ? value : {};
  return Object.freeze({
    provider: String(detail.provider || "").trim().slice(0, 80),
    model: String(detail.model || "").trim().slice(0, 120),
    durationSeconds: Number.isFinite(Number(detail.durationSeconds))
      ? Number(detail.durationSeconds)
      : null,
    ratio: String(detail.ratio || "").trim().slice(0, 24),
    resolution: String(detail.resolution || "").trim().slice(0, 24),
    audio: typeof detail.audio === "boolean" ? detail.audio : null,
    firstFrame: typeof detail.firstFrame === "boolean" ? detail.firstFrame : null,
    lastFrame: typeof detail.lastFrame === "boolean" ? detail.lastFrame : null,
    inputMode: String(detail.inputMode || "").trim().slice(0, 40),
    referenceCount: detail.referenceCount !== null
      && detail.referenceCount !== undefined
      && Number.isInteger(Number(detail.referenceCount))
      ? Math.max(0, Number(detail.referenceCount))
      : null,
  });
}

function clearRepeatPaymentAndPreflight(form) {
  const confirmation = form.elements?.real_spend_confirmation;
  if (confirmation instanceof HTMLInputElement) {
    confirmation.checked = false;
    confirmation.dispatchEvent(new Event("input", { bubbles: true }));
  }
  qa("#generation-strategy-assets input[data-generation-strategy-attestation]", form)
    .forEach((input) => {
      input.checked = false;
    });
  delete form.dataset.autoGenerationPreflightKey;
}

function applyRepeatedSettings(form, detail) {
  const model = runtime.catalog.models.find((entry) => (
    entry.provider === String(detail.provider || "").trim()
    && entry.model === String(detail.model || "").trim()
  ));
  if (!model) return false;
  runtime.modelFilter = "relevant";
  runtime.repeatSettings = Object.freeze({ ...detail, provider: model.provider, model: model.model });
  if (!runtime.recommendationState) renderModelAdvisor(form);
  runtime.recommendationState = generationModelRecommendationReducer(
    runtime.recommendationState,
    {
      type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.SELECT_MANUAL,
      selection: { provider: model.provider, model: model.model },
    },
  );
  const executable = modelCanUseExistingLaunch(form, model);
  runtime.externalSelectionActive = !executable;
  if (executable) {
    applyModelIdentity(form, model, { preserveRepeatSettings: true });
    setRepeatedNativeValue(form.elements?.duration_seconds, detail.durationSeconds);
    setRepeatedNativeValue(form.elements?.format, detail.ratio);
    setRepeatedNativeValue(form.elements?.generation_resolution, detail.resolution);
    if (typeof detail.audio === "boolean") {
      setRepeatedNativeValue(form.elements?.generation_audio, String(detail.audio));
    }
    const lastFrame = form.elements?.generation_last_frame;
    if (lastFrame instanceof HTMLInputElement) {
      lastFrame.checked = detail.lastFrame === true && !lastFrame.disabled;
      lastFrame.dispatchEvent(new Event("change", { bubbles: true }));
    }
  } else {
    syncExactModelControls(form, model, { emit: true });
  }
  clearRepeatPaymentAndPreflight(form);
  renderModelAdvisor(form);
  scheduleSync(form);
  return true;
}

function handleRepeatSettings(event) {
  const form = event.currentTarget;
  const detail = normalizeRepeatSettings(event?.detail);
  if (!detail.provider || !detail.model) return;
  event.preventDefault?.();
  clearRepeatPaymentAndPreflight(form);
  if (!runtime.catalog || !Array.isArray(runtime.catalog.models)) {
    runtime.pendingRepeatSettings = { form, detail };
    return;
  }
  runtime.pendingRepeatSettings = null;
  applyRepeatedSettings(form, detail);
}

function handleExactScope(event) {
  const form = event.currentTarget;
  const scope = event?.detail && typeof event.detail === "object"
    ? event.detail
    : null;
  const model = runtime.catalog?.models?.find((entry) => (
    entry.provider === scope?.provider && entry.model === scope?.model
  ));
  if (!model || !modelCanUseExistingLaunch(form, model)) return;
  event.preventDefault?.();
  if (!applyModelIdentity(form, model, { preserveRepeatSettings: true })) return;
  setRepeatedNativeValue(form.elements?.duration_seconds, scope.duration_seconds);
  setRepeatedNativeValue(form.elements?.format, scope.ratio || scope.format);
  setRepeatedNativeValue(form.elements?.generation_resolution, scope.resolution);
  setRepeatedNativeValue(form.elements?.generation_audio, String(scope.audio === true));
  const lastFrame = form.elements?.generation_last_frame;
  if (lastFrame instanceof HTMLInputElement) {
    lastFrame.checked = scope.last_frame === true && !lastFrame.disabled;
    lastFrame.dispatchEvent(new Event("change", { bubbles: true }));
  }
  syncExactModelControls(form, model);
  clearRepeatPaymentAndPreflight(form);
  renderModelAdvisor(form);
}

function handleStrategyRestore(event) {
  const form = event.currentTarget;
  const values = event?.detail && typeof event.detail === "object"
    ? event.detail
    : null;
  if (!values) return;
  event.preventDefault?.();
  applyStrategyRestore(form, values);
}

function handleFormClick(event) {
  if (!(event.target instanceof Element)) return;
  const form = event.currentTarget;
  // Переключатель массового режима «Создания»: требование — состояние пикера.
  // Идёт ПЕРЕД sourceToggle: у обоих есть data-атрибуты, и радио не должно
  // проваливаться в чужую ветку. Под платным замком режим не меняется.
  const batchMode = event.target.closest(
    "[data-generation-strategy-batch-mode]",
  );
  if (batchMode instanceof HTMLInputElement) {
    if (form.dataset.generationStrategyPaidLocked === "true") {
      event.preventDefault();
      return;
    }
    const requiredCount = Number(
      batchMode.dataset.generationStrategyBatchMode,
    );
    const previous = generationStrategySourcePickerProjection(
      runtime.strategySourcePicker,
    );
    if (previous?.required_count === requiredCount) return;
    runtime.strategySourcePicker = reduceGenerationStrategySourcePicker(
      runtime.strategySourcePicker,
      {
        type: GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.setRequiredCount,
        required_count: requiredCount,
      },
    );
    const next = renderStrategySourcePicker(form);
    // Смена размера пакета — смена платного контекста: подтверждения и
    // черновики механики лишних роликов не переживают сжатие.
    clearStrategyAttestations(form);
    const retained = new Set(
      (next?.selected || []).map((item) => item.source_media_id),
    );
    for (const mediaId of runtime.strategyMechanicsDrafts.keys()) {
      if (!retained.has(mediaId)) runtime.strategyMechanicsDrafts.delete(mediaId);
    }
    syncStrategyAssetCandidates(form);
    form.dispatchEvent(new CustomEvent(
      "contentengine:generation-strategy-sources-changed",
      { bubbles: true, detail: next },
    ));
    scheduleSync(form);
    return;
  }
  const sourceToggle = event.target.closest(
    "[data-generation-strategy-source-toggle], [data-action=\"toggle-generation-strategy-source\"]",
  );
  if (sourceToggle) {
    event.preventDefault();
    if (form.dataset.generationStrategyPaidLocked === "true") return;
    const sourceMediaId = String(
      sourceToggle.dataset.generationStrategySourceToggle
        || sourceToggle.dataset.sourceMediaId
        || "",
    ).trim().toLowerCase();
    const previous = generationStrategySourcePickerProjection(
      runtime.strategySourcePicker,
    );
    runtime.strategySourcePicker = reduceGenerationStrategySourcePicker(
      runtime.strategySourcePicker,
      {
        type: GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.toggle,
        source_media_id: sourceMediaId,
      },
    );
    const next = renderStrategySourcePicker(form);
    if (JSON.stringify(previous?.selected || []) !== JSON.stringify(next?.selected || [])) {
      clearStrategyAttestations(form);
    }
    if (
      previous?.selected.some((item) => item.source_media_id === sourceMediaId)
      && !next?.selected.some((item) => item.source_media_id === sourceMediaId)
    ) {
      runtime.strategyMechanicsDrafts.delete(sourceMediaId);
    }
    syncStrategyAssetCandidates(form);
    form.dispatchEvent(new CustomEvent(
      "contentengine:generation-strategy-sources-changed",
      { bubbles: true, detail: next },
    ));
    scheduleSync(form);
    return;
  }
  const strategyButton = event.target.closest(
    '[data-generation-strategy-action="SELECT"]',
  );
  if (strategyButton) {
    event.preventDefault();
    if (form.dataset.generationStrategyPaidLocked === "true") return;
    const previous = runtime.strategyState?.selected_strategy_id || "";
    runtime.strategyState = reduceGenerationStrategyViewState(
      runtime.strategyState,
      {
        type: GENERATION_STRATEGY_SELECT_ACTION,
        strategy_id: strategyButton.dataset.strategyId,
      },
    );
    const changed = previous !== runtime.strategyState?.selected_strategy_id;
    const strategyRoot = q("[data-ce-v4-generation-strategies]", form);
    if (strategyRoot) {
      strategyRoot.innerHTML = generationStrategyViewMarkup(runtime.strategyState);
    }
    if (changed) {
      syncStrategyForm(form, { reset: true });
      form.elements?.generation_strategy_id?.dispatchEvent(
        new Event("change", { bubbles: true }),
      );
      scheduleSync(form);
    } else {
      syncStrategyForm(form);
    }
    renderModelAdvisor(form);
    return;
  }
  const refreshStrategyAssets = event.target.closest(
    "[data-generation-strategy-assets-refresh]",
  );
  if (refreshStrategyAssets) {
    event.preventDefault();
    void loadGenerationStrategyAssets(form);
    return;
  }
  const modelCatalogRetry = event.target.closest("[data-ce-v4-model-catalog-retry]");
  if (modelCatalogRetry) {
    event.preventDefault();
    runtime.catalogRetryCount = 0;
    if (runtime.catalogStatus !== "loading") {
      runtime.catalogStatus = "idle";
      void loadModelCatalog(form);
    }
    return;
  }
  const strategyCatalogRetry = event.target.closest(
    "[data-generation-strategy-catalog-retry]",
  );
  if (strategyCatalogRetry) {
    event.preventDefault();
    runtime.strategyCatalogRetryCount = 0;
    if (runtime.strategyCatalogStatus !== "loading") {
      runtime.strategyCatalogStatus = "idle";
      void loadStrategyCatalog(form);
    }
    return;
  }
  const loadMoreStrategyAssets = event.target.closest(
    "[data-generation-strategy-assets-load-more]",
  );
  if (loadMoreStrategyAssets) {
    event.preventDefault();
    void loadGenerationStrategyAssets(form, { append: true });
    return;
  }
  const contentKind = event.target.closest("[data-ce-v4-content-kind]");
  if (contentKind) {
    event.preventDefault();
    chooseContentKind(form, contentKind.dataset.ceV4ContentKind);
    return;
  }
  const modelFilter = event.target.closest("[data-ce-v4-model-filter]");
  if (modelFilter) {
    event.preventDefault();
    runtime.modelFilter = MODEL_FILTERS.some(([key]) => key === modelFilter.dataset.ceV4ModelFilter)
      ? modelFilter.dataset.ceV4ModelFilter
      : "relevant";
    renderModelAdvisor(form);
    return;
  }
  const applyRecommendation = event.target.closest("[data-ce-v4-apply-model-recommendation]");
  if (applyRecommendation) {
    event.preventDefault();
    const recommended = runtime.recommendationState?.recommendation?.recommended;
    if (selectedStrategyRow()) {
      applyStrategyAdvisoryModel(form, recommended, { acceptRecommendation: true });
    } else {
      applyModelIdentity(form, recommended, { acceptRecommendation: true });
    }
    return;
  }
  const stepButton = event.target.closest("[data-ce-v4-generation-target]");
  if (stepButton) {
    event.preventDefault();
    moveTo(form, stepIndex(stepButton.dataset.ceV4GenerationTarget));
    return;
  }
  if (event.target.closest("[data-ce-v4-generation-back]")) {
    event.preventDefault();
    moveTo(form, stepIndex(form.dataset.ceV4GenerationStep) - 1);
    return;
  }
  if (event.target.closest("[data-ce-v4-generation-next]")) {
    event.preventDefault();
    moveTo(form, stepIndex(form.dataset.ceV4GenerationStep) + 1);
  }
}

function handleFormEdit(event) {
  const form = event.currentTarget;
  const control = event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement
    ? event.target
    : null;
  const mechanicsControl = event.target instanceof HTMLTextAreaElement
    ? event.target
    : null;
  if (mechanicsControl?.dataset?.generationStrategyMechanicsField) {
    const sourceMediaId = String(
      mechanicsControl.dataset.generationStrategySourceMediaId || "",
    ).trim().toLowerCase();
    const field = String(
      mechanicsControl.dataset.generationStrategyMechanicsField || "",
    );
    if (
      runtime.strategyMechanicsDrafts.has(sourceMediaId)
      || runtime.strategySourcePicker?.selected_source_ids?.includes(sourceMediaId)
    ) {
      runtime.strategyMechanicsDrafts.set(sourceMediaId, {
        ...strategyMechanicsDraft(sourceMediaId),
        [field]: mechanicsControl.value,
      });
    }
  }
  if (mechanicsControl?.name === "brief" && selectedStrategyRow()) {
    syncStrategyBriefValidity(form, true);
  }
  // Человеческий выбор в селекте конструктора уезжает в каноничное поле
  // generation_intake_engine; события на скрытом input дальше сами запускают
  // и перефильтровку ratio (ветка ниже), и сброс подписанной цены в app.js.
  if (
    control instanceof HTMLSelectElement
    && control.matches?.("[data-ce-v4-generation-engine-select]")
  ) {
    // Под замком селект и так disabled нашим sync'ом, но guided-перерендер
    // между свипом и sync'ом не должен оставлять окно, в котором человеческий
    // change долетает до writeStrategyEngineValue и роняет подписанный runtime.
    if (form.dataset.generationStrategyPaidLocked === "true") return;
    // Человеческий выбор переживает пересоздание формы: скрытый input умирает
    // вместе с DOM, и без памяти sync молча вернул бы рекомендованный дефолт —
    // то есть сменил бы цену без действия оператора.
    runtime.guidedEngineChoice = {
      strategyId: selectedStrategyRow()?.strategy_id || "",
      value: String(control.value || ""),
    };
    writeStrategyEngineValue(form, control.value);
    return;
  }
  // Смена движка в каскаде меняет набор кадров «Создания». Перерисовка идёт
  // только при НАСТОЯЩЕЙ смене значения и только для стратегии с выбором
  // кадра: у «Копии» и «Дуэта» кадр задаёт исходник, и дёргать форму там
  // незачем. Повторный вход запрещён: синхронизация сама рождает события.
  if (control?.name === "generation_intake_engine") {
    const row = selectedStrategyRow();
    const value = String(control.value || "");
    if (
      row
      && row.output_rules?.dimension_field === "ratio"
      && runtime.lastEngineForRatioSync !== value
      && !runtime.engineRatioSyncBusy
    ) {
      runtime.lastEngineForRatioSync = value;
      runtime.engineRatioSyncBusy = true;
      try {
        syncStrategyForm(form);
      } finally {
        runtime.engineRatioSyncBusy = false;
      }
    }
  }
  if (control?.matches?.('[data-ce-v4-generation-model]')) {
    const selected = runtime.catalog?.models?.find((model) => modelKey(model) === control.value);
    if (selectedStrategyRow()) applyStrategyAdvisoryModel(form, selected);
    else applyModelIdentity(form, selected);
    return;
  }
  refreshRepeatedSetting(form, control);
  if (isStrategyAssetAuthorityControl(control)) clearStrategyAttestations(form);
  if (
    control?.name?.startsWith?.("generation_strategy_")
  ) {
    delete form.dataset.autoGenerationPreflightKey;
    const confirmation = form.elements?.real_spend_confirmation;
    if (confirmation instanceof HTMLInputElement) {
      confirmation.checked = false;
      confirmation.value = "";
    }
    syncStrategyAssetCandidates(form);
  }
  if ([
    "generation_model_id",
    "generation_input_mode",
    "duration_seconds",
    "format",
    "generation_resolution",
    "generation_audio",
    "generation_last_frame",
  ].includes(control?.name)) {
    delete form.dataset.autoGenerationPreflightKey;
    const confirmation = form.elements?.real_spend_confirmation;
    if (confirmation instanceof HTMLInputElement && control?.name !== "real_spend_confirmation") {
      confirmation.checked = false;
      confirmation.value = "";
    }
    if (control?.name === "generation_audio") {
      const selected = runtime.catalog?.models?.find(
        (model) => modelKey(model) === modelKey(selectedModelForForm(form)),
      );
      const proxyMode = modeForModel(selected, form);
      const modeSelect = form.elements?.generation_mode;
      if (
        proxyMode
        && modeSelect instanceof HTMLSelectElement
        && modeSelect.value !== proxyMode
      ) {
        runtime.applyingModel = true;
        modeSelect.value = proxyMode;
        modeSelect.dispatchEvent(new Event("change", { bubbles: true }));
        runtime.applyingModel = false;
      }
    }
  }
  if (control?.name === "generation_mode" && runtime.catalog && !runtime.applyingModel) {
    runtime.externalSelectionActive = false;
    runtime.repeatSettings = null;
    const identity = modelIdentityForMode(control.value);
    runtime.recommendationState = identity
      ? generationModelRecommendationReducer(runtime.recommendationState, {
          type: GENERATION_MODEL_RECOMMENDATION_ACTIONS.SELECT_MANUAL,
          selection: identity,
        })
      : createGenerationModelRecommendationState({
          catalogSnapshot: runtime.catalog,
          context: modelContext(form),
        });
  }
  const panel = event.target instanceof Element
    ? event.target.closest("[data-ce-v4-generation-panel]")
    : null;
  clearPanelError(panel);
  scheduleSync(form);
}

function bindForm(form) {
  const existing = form[FORM_BINDING_KEY];
  if (existing?.owner === handleFormClick && existing?.controller?.signal?.aborted === false) {
    form.dataset.ceV4GenerationGuidedBound = "true";
    return;
  }
  if (
    existing
    && existing.owner !== handleFormClick
    && existing.controller?.signal?.aborted === false
  ) {
    // Живой владелец из другого экземпляра модуля: не отбираем у него клики —
    // его рендер и его состояние согласованы между собой, а у нас пусто.
    // Молчаливый перехват давал «галка не ставится»: рисовал один экземпляр,
    // клики глотал второй. Смесь лечится перезагрузкой через build-guard.
    console.error(
      "ContentEngine mixed build detected: generation-guided form binding "
      + `держит ${existing.epoch || "unknown"}, пришёл ${GUIDED_EPOCH}`,
    );
    try {
      window.dispatchEvent(new CustomEvent("contentengine:mixed-build-detected", {
        detail: {
          scope: "generation-guided:form-binding",
          held: String(existing.epoch || "unknown"),
          incoming: GUIDED_EPOCH,
        },
      }));
    } catch { /* консоль уже сообщила */ }
    return;
  }
  existing?.controller?.abort?.();
  const controller = new AbortController();
  const options = { signal: controller.signal };
  form.dataset.ceV4GenerationGuidedBound = "true";
  form.addEventListener("click", handleFormClick, options);
  form.addEventListener("input", handleFormEdit, options);
  form.addEventListener("change", handleFormEdit, options);
  form.addEventListener("contentengine:generation-repeat-settings", handleRepeatSettings, options);
  form.addEventListener("contentengine:generation-apply-exact-scope", handleExactScope, options);
  form.addEventListener("contentengine:generation-restore-strategy", handleStrategyRestore, options);
  Object.defineProperty(form, FORM_BINDING_KEY, {
    configurable: true,
    value: Object.freeze({ controller, owner: handleFormClick, epoch: GUIDED_EPOCH }),
  });
}

function setupForm(form, { initialSync = true } = {}) {
  // Intake v4 owns the route switcher and places this constructor inside the
  // selected “Видео по стратегии” panel. Search the whole form so a remount
  // adopts that one live shell instead of creating a second form underneath.
  let shell = q("[data-ce-v4-generation-guided-shell]", form);
  if (!shell) {
    const originalNodes = [...form.children];
    const submit = originalNodes.find((node) => node.id === "generation-submit")
      || q("#generation-submit", form);
    shell = createShell(form);
    organizeOriginalNodes(form, shell, originalNodes, submit);
    form.dataset.ceV4GenerationGuided = "true";
    form.setAttribute(SESSION_ATTRIBUTE, SESSION_KEY);
  } else {
    adoptDirectChildren(form, shell);
  }

  ensureStrategyView(form);
  ensureModelAdvisor(form);
  exposeProviderReadinessControl(form);
  bindForm(form);
  // Hidden handoff fields are part of the live form contract and may have been
  // written after the first adapter mount. Hydrate before the fast return too,
  // so remounting the same form cannot discard its already registered MP4.
  hydrateRegisteredSourceFromHiddenHandoff(form);
  if (!initialSync) {
    syncSummary(form);
    syncCompletion(form);
    return shell;
  }
  const saved = readSession(form);
  const initial = form.dataset.ceV4GenerationStep || saved.step || STEPS[0].key;
  const requestedIndex = stepIndex(initial);
  const invalidIndex = firstInvalidStepBefore(form, requestedIndex);
  const restoredIndex = invalidIndex >= 0 ? invalidIndex : requestedIndex;
  const restoredMax = Math.max(
    restoredIndex,
    Math.min(
      invalidIndex >= 0 ? invalidIndex : STEPS.length - 1,
      Number(form.dataset.ceV4GenerationMaxVisited || saved.maxVisited) || 0,
    ),
  );
  form.dataset.ceV4GenerationMaxVisited = String(restoredMax);
  setStep(form, restoredIndex);
  if (initialSync) scheduleSync(form);
  if (runtime.strategyCatalogStatus === "idle") void loadStrategyCatalog(form);
  if (runtime.catalogStatus === "idle") void loadModelCatalog(form);
  if (runtime.strategyAssetStatus === "idle") {
    void loadGenerationStrategyAssets(form);
  }
  consumeIntakeHandoff(form);
  return shell;
}

// --- Консьюмер handoff-контракта компактной формы (intake-v4) ---------------
// Компактные маршруты пишут handoff тремя каналами: скрытые поля
// generation_intake_* в форме, sessionStorage `generation-intake-mp4-v4:<project>`
// и событие contentengine:generation-strategy-handoff. Гид читает все три,
// предзаполняет «Замысел» после перезагрузки и показывает происхождение
// (источник-ссылку, происхождение рекомендации), чтобы данные не терялись.

const INTAKE_HANDOFF_EVENT = "contentengine:generation-strategy-handoff";
const INTAKE_HANDOFF_STORAGE_PREFIX = "generation-intake-mp4-v4:";

const INTAKE_RECOMMENDATION_SOURCE_LABELS = Object.freeze({
  ai_center: "проверенная рекомендация ИИ-центра",
  ai_center_edited: "рекомендация ИИ-центра, отредактированная сотрудником",
  ai_center_unverified: "непроверенный черновик ИИ-центра — не применён автоматически",
  operator: "текст сотрудника",
});

function intakeHandoffCanPrefillBrief(handoff) {
  const source = String(handoff?.recommendation_source || "").trim();
  // Fail closed for AI-centre drafts and unknown lineage. Only an explicitly
  // verified/edited recommendation or operator/legacy text may populate an
  // otherwise empty brief; the human can still copy an unverified draft by
  // hand after reviewing it in the AI Centre.
  return ["", "empty", "operator", "ai_center", "ai_center_edited"].includes(source);
}

function normalizeIntakeHandoff(raw) {
  if (!raw || typeof raw !== "object") return null;
  const textOf = (value, limit) => String(value ?? "").trim().slice(0, limit);
  const mediaIdOf = (value) => {
    const mediaId = String(value ?? "").trim().toLowerCase();
    return STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(mediaId) ? mediaId : "";
  };
  const durationOf = (value) => {
    if (value === null || value === undefined || String(value).trim() === "") {
      return null;
    }
    const duration = Number(value);
    return Number.isFinite(duration) && duration > 0 && duration <= 3_600
      ? duration
      : null;
  };
  const knownRoles = new Set([
    "source_video",
    "original_product_image",
    "new_product_image",
    "avatar_image",
  ]);
  const assets = [];
  const seenAssets = new Set();
  (Array.isArray(raw.assets) ? raw.assets : []).slice(0, 20).forEach((asset) => {
    const role = textOf(asset?.role, 64);
    const mediaId = mediaIdOf(asset?.media_id);
    const key = `${role}:${mediaId}`;
    if (!knownRoles.has(role) || !mediaId || seenAssets.has(key)) return;
    seenAssets.add(key);
    const duration = role === "source_video"
      ? durationOf(asset?.duration_seconds)
      : null;
    assets.push(Object.freeze({
      role,
      media_id: mediaId,
      ...(duration === null ? {} : { duration_seconds: duration }),
    }));
  });
  const sourceMediaId = mediaIdOf(raw.source_media_id);
  const sourceDuration = durationOf(raw.source_duration_seconds);
  const handoff = {
    route: textOf(raw.route, 40),
    source_media_id: sourceMediaId,
    source_duration_seconds: sourceDuration,
    source_url: textOf(raw.source_url, 1_000),
    description: textOf(raw.description, 1_200),
    recommendation_source: textOf(raw.recommendation_source, 60),
    requested_model: textOf(raw.requested_model, 160),
    assets: Object.freeze(assets),
  };
  const meaningful = handoff.source_url
    || handoff.description
    || (handoff.recommendation_source && handoff.recommendation_source !== "empty")
    || handoff.requested_model
    || handoff.assets.length > 0;
  return meaningful ? handoff : null;
}

function intakeHandoffFromHiddenFields(form) {
  const read = (name) => String(form?.elements?.[name]?.value || "");
  if (!read("generation_intake_version").trim()) return null;
  let assets = [];
  try {
    const parsed = JSON.parse(read("generation_strategy_prefill_assets") || "[]");
    if (Array.isArray(parsed)) assets = parsed;
  } catch {
    // A malformed hidden projection is ignored. The authoritative server
    // preflight still validates every UUID before any priced action.
  }
  return normalizeIntakeHandoff({
    route: read("generation_intake_route"),
    source_media_id: read("generation_intake_source_media_id"),
    source_duration_seconds: read("generation_intake_source_duration_seconds"),
    source_url: read("generation_intake_source_url"),
    description: read("generation_intake_description"),
    recommendation_source: read("generation_intake_recommendation_source"),
    requested_model: read("generation_intake_model"),
    assets,
  });
}

function intakeHandoffFromSession() {
  try {
    const hash = String(window.location.hash || "");
    const projectMatch = /[?&]project_id=([0-9a-fA-F-]{36})/u.exec(hash);
    const preferred = projectMatch
      ? `${INTAKE_HANDOFF_STORAGE_PREFIX}${projectMatch[1].toLowerCase()}`
      : "";
    const keys = [];
    for (let index = 0; index < sessionStorage.length; index += 1) {
      const key = sessionStorage.key(index);
      if (key && key.startsWith(INTAKE_HANDOFF_STORAGE_PREFIX)) keys.push(key);
    }
    const key = keys.includes(preferred)
      ? preferred
      : (!preferred && keys.length === 1 ? keys[0] : "");
    if (!key) return null;
    return normalizeIntakeHandoff(
      JSON.parse(sessionStorage.getItem(key) || "null"),
    );
  } catch {
    return null;
  }
}

function applyIntakeHandoffBrief(form, handoff) {
  const brief = form?.elements?.brief;
  if (
    brief instanceof HTMLTextAreaElement
    && handoff.description
    && intakeHandoffCanPrefillBrief(handoff)
    && !String(brief.value || "").trim()
  ) {
    brief.value = handoff.description;
    brief.dispatchEvent(new Event("input", { bubbles: true }));
    brief.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }
  return false;
}

function renderIntakeHandoffProvenance(form, handoff) {
  const content = q('[data-ce-v4-generation-content="brief"]', form);
  if (!content) return;
  const existing = q("[data-ce-v4-intake-provenance]", content);
  const recommendationLabel = handoff.recommendation_source
    && handoff.recommendation_source !== "empty"
    ? (INTAKE_RECOMMENDATION_SOURCE_LABELS[handoff.recommendation_source]
      || handoff.recommendation_source)
    : "";
  if (!handoff.source_url && !recommendationLabel && !handoff.requested_model) {
    existing?.remove();
    return;
  }
  const note = existing
    || element("p", "ce-v4-generation-guided__intake-provenance");
  note.dataset.ceV4IntakeProvenance = "";
  note.replaceChildren(element("strong", "", "Из компактной формы: "));
  const fragments = [];
  if (handoff.source_url) {
    const wrap = document.createDocumentFragment();
    wrap.append(document.createTextNode("источник ролика — "));
    if (/^https?:\/\//iu.test(handoff.source_url)) {
      const link = element("a", "", handoff.source_url);
      link.href = handoff.source_url;
      link.target = "_blank";
      link.rel = "noreferrer noopener";
      wrap.append(link);
    } else {
      wrap.append(document.createTextNode(handoff.source_url));
    }
    fragments.push(wrap);
  }
  if (recommendationLabel) {
    fragments.push(document.createTextNode(`происхождение замысла — ${recommendationLabel}`));
  }
  if (handoff.requested_model) {
    fragments.push(document.createTextNode(`запрошенная модель — ${handoff.requested_model}`));
  }
  fragments.forEach((fragment, index) => {
    if (index > 0) note.append(document.createTextNode(" · "));
    note.append(fragment);
  });
  if (note.parentElement !== content) content.prepend(note);
}

function consumeIntakeHandoff(form) {
  const handoff = intakeHandoffFromHiddenFields(form)
    || intakeHandoffFromSession()
    || runtime.intakeHandoff;
  if (!handoff) return;
  runtime.intakeHandoff = handoff;
  runtime.intakeHandoffProjectId = generationStrategyProjectId();
  // Pure state hydration only; the already scheduled form sync performs the
  // render. This also covers a full-form patch that dropped the hidden inputs.
  hydrateRegisteredSourceFromHiddenHandoff(form);
  applyIntakeHandoffBrief(form, handoff);
  renderIntakeHandoffProvenance(form, handoff);
}

window.addEventListener(INTAKE_HANDOFF_EVENT, (event) => {
  const handoff = normalizeIntakeHandoff(event?.detail);
  if (!handoff) return;
  runtime.intakeHandoff = handoff;
  runtime.intakeHandoffProjectId = generationStrategyProjectId();
  const form = runtime.form;
  if (form?.isConnected) {
    hydrateRegisteredSourceFromHiddenHandoff(form);
    applyIntakeHandoffBrief(form, handoff);
    renderIntakeHandoffProvenance(form, handoff);
  }
});

function mount() {
  if (routePath() !== ROUTE) {
    document.body.classList.remove("ce-v4-generation-guided-route");
    runtime.form = null;
    runtime.pendingRepeatSettings = null;
    runtime.strategyAssetRequest += 1;
    runtime.strategyAssetStatus = "idle";
    runtime.strategyAssetError = "";
    runtime.strategyRegisteredSourceProjectId = "";
    runtime.strategyRegisteredSources.clear();
    runtime.strategySourcePicker = null;
    runtime.strategyMechanicsDrafts.clear();
    runtime.intakeHandoff = null;
    runtime.intakeHandoffProjectId = "";
    return;
  }
  const form = q("#mock-batch-form");
  if (!form) return;
  const mountedProjectId = generationStrategyProjectId();
  if (
    runtime.strategyRegisteredSourceProjectId
    && runtime.strategyRegisteredSourceProjectId !== mountedProjectId
  ) {
    runtime.strategyRegisteredSourceProjectId = "";
    runtime.strategyRegisteredSources.clear();
  }
  if (
    runtime.intakeHandoffProjectId
    && runtime.intakeHandoffProjectId !== mountedProjectId
  ) {
    runtime.intakeHandoff = null;
    runtime.intakeHandoffProjectId = "";
  }
  const formChanged = runtime.form !== form;
  if (formChanged) {
    if (runtime.catalogStatus === "error") runtime.catalogStatus = "idle";
    if (runtime.strategyCatalogStatus === "error") {
      runtime.strategyCatalogStatus = "idle";
    }
    runtime.recommendationState = null;
    runtime.modelFilter = "relevant";
    runtime.externalSelectionActive = false;
    runtime.repeatSettings = null;
    runtime.pendingRepeatSettings = null;
    runtime.strategyAssetRequest += 1;
    runtime.strategyAssetPage = null;
    runtime.strategyAssetProjectId = "";
    runtime.strategyAssetStatus = "idle";
    runtime.strategyAssetError = "";
    runtime.strategySourcePicker = null;
    runtime.strategyMechanicsDrafts.clear();
  }
  runtime.form = form;
  document.body.classList.add("ce-v4-generation-guided-route");
  setupForm(form, { initialSync: formChanged });
}

window.ContentEngineDesktopV4.registerAdapter("generation-guided", mount, {
  priority: 180,
  epoch: GUIDED_EPOCH,
});

window.ContentEngineGenerationGuidedV4 = Object.freeze({
  mount,
  steps: STEPS,
  getStrategySelection(form = runtime.form) {
    return form?.isConnected ? generationStrategySelection(form) : null;
  },
  getStrategySelections(form = runtime.form) {
    return form?.isConnected ? generationStrategySelections(form) : null;
  },
  getStrategySourcePickerProjection(form = runtime.form) {
    if (!form?.isConnected) return null;
    return generationStrategySourcePickerProjection(runtime.strategySourcePicker);
  },
  getStrategySummary() {
    return selectedGenerationStrategySummary(runtime.strategyState);
  },
  // Движки стратегии для экрана «Копия»: сервер отдаёт их вместе с каталогом,
  // а форма показывает как «Генератор 1/2/3». Здесь только чтение — выбор
  // движка попадает в наряд отдельным полем и подписывается сервером.
  getStrategyProviderRoutes(strategyId) {
    const routes = runtime.strategyCatalog?.strategyProviderRoutes?.[strategyId];
    return Array.isArray(routes) ? routes : [];
  },
  // Движок, выбранный в каскаде. Значение живёт в поле формы, поэтому
  // читается оттуда же, откуда его видит человек. Сверка с каталогом здесь не
  // формальность: пустое, чужое или выключенное значение обязано превратиться
  // в «движок не выбран», а не уйти в привязку — тогда сервер посчитает
  // действующий маршрут, как считал до каскада, вместо отказа на ровном месте.
  //
  // Маршруты спрашиваются у ТОЙ стратегии, которая выбрана в форме, а не у
  // «Копии» литералом. Поле generation_intake_engine одно на всю форму, и до
  // этой правки движок «Копии» уезжал в привязку любой другой стратегии: у
  // неё такого маршрута в реестре нет, цена считалась бы null, а наружу шёл
  // бы общий отказ. Чужой стратегии движок теперь просто не принадлежит.
  getStrategyEngineChoice(form = runtime.form) {
    if (!form?.isConnected) return null;
    const raw = String(form.elements?.generation_intake_engine?.value || "").trim();
    const separator = raw.indexOf(":");
    if (separator < 1 || separator === raw.length - 1) return null;
    const provider = raw.slice(0, separator);
    const modelKey = raw.slice(separator + 1);
    const strategyId = String(
      form.elements?.generation_strategy_id?.value || "",
    ).trim();
    if (!strategyId) return null;
    const routes = runtime.strategyCatalog
      ?.strategyProviderRoutes?.[strategyId];
    if (!Array.isArray(routes)) return null;
    const route = routes.find((entry) => (
      entry?.provider === provider && entry?.model_key === modelKey
    ));
    return route?.enabled === true
      ? Object.freeze({ provider, model_key: modelKey })
      : null;
  },
  // Ведущий, выбранный в форме «Дуэта»: наш UUID из поля формы. Отдаётся
  // только когда выбрана стратегия дуэта — чужой стратегии ведущий не нужен,
  // и лишний ключ в контексте привязки означал бы отказ сервера.
  getDuetPresenterChoice(form = runtime.form) {
    if (!form?.isConnected) return null;
    const strategyId = String(
      form.elements?.generation_strategy_id?.value || "",
    ).trim();
    if (strategyId !== "viral_avatar_ugc") return null;
    const raw = String(
      form.elements?.generation_intake_duet_presenter_id?.value || "",
    ).trim().toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u
        .test(raw)
      ? raw
      : null;
  },
  // Ведущий и товар «Дуэта» читаются из полей формы одинаково; товар нужен
  // подготовке ТЗ (контракт PREPARE_INPUT_KEYS_WITH_PRODUCT) явным полем.
  getDuetProductChoice(form = runtime.form) {
    if (!form?.isConnected) return null;
    const strategyId = String(
      form.elements?.generation_strategy_id?.value || "",
    ).trim();
    if (strategyId !== "viral_avatar_ugc") return null;
    const raw = String(
      form.elements?.generation_intake_duet_product_id?.value || "",
    ).trim().toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u
        .test(raw)
      ? raw
      : null;
  },
  // Поля разбора механики — единый список для нативного редактора и для
  // экспресс-панели «Дуэта», чтобы подписи и пределы не разошлись.
  getStrategyMechanicsFields() {
    return STRATEGY_MECHANICS_FIELDS;
  },
  // Разбор, написанный в экспресс-панели, становится черновиком выбранного
  // исходника и значением нативных textarea: дальше его читают и ТЗ
  // (mechanics_summary), и reportValidity() мастера.
  setStrategyMechanicsDraft(form = runtime.form, sourceMediaId = "", draft = null) {
    const mediaId = String(sourceMediaId || "").trim().toLowerCase();
    if (!form?.isConnected || !STRATEGY_REPEAT_MEDIA_ID_PATTERN.test(mediaId)) return false;
    if (!draft || typeof draft !== "object") return false;
    const next = { ...strategyMechanicsDraft(mediaId) };
    STRATEGY_MECHANICS_FIELDS.forEach(({ key }) => {
      if (typeof draft[key] === "string") next[key] = draft[key];
    });
    runtime.strategyMechanicsDrafts.set(mediaId, next);
    qa(
      `textarea[data-generation-strategy-mechanics-field][data-generation-strategy-source-media-id="${mediaId}"]`,
      form,
    ).forEach((control) => {
      const key = String(control.dataset.generationStrategyMechanicsField || "");
      if (typeof next[key] === "string" && control.value !== next[key]) {
        control.value = next[key];
      }
    });
    return true;
  },
  // Товары проекта для формы «Дуэта».
  //
  // Отдельного перечня товаров в проекте нет и не заводится: товар появляется
  // ВМЕСТЕ со своей первой фотографией, поэтому список выводится из уже
  // полученной страницы ассетов. Новый серверный вызов ради того же факта был
  // бы вторым его источником — а два источника одного факта однажды разойдутся.
  //
  // Берутся только подтверждённые личности: неподтверждённая означает, что
  // сервер сам не считает связь товара с фотографией установленной, и
  // предлагать такой товар для оформления запуска нельзя.
  getProjectProducts() {
    const assets = Array.isArray(runtime.strategyAssetPage?.assets)
      ? runtime.strategyAssetPage.assets
      : [];
    const byId = new Map();
    for (const asset of assets) {
      const identity = asset?.product_identity;
      if (!identity || identity.identity_verified !== true) continue;
      const id = String(identity.product_id || "").trim().toLowerCase();
      if (!id || byId.has(id)) continue;
      byId.set(id, Object.freeze({
        product_id: id,
        sku: String(identity.sku || ""),
        product_name: String(identity.product_name || ""),
      }));
    }
    return Object.freeze([...byId.values()]);
  },
  refreshStrategyAssets(form = runtime.form) {
    if (!form?.isConnected) return Promise.resolve(false);
    return loadGenerationStrategyAssets(form);
  },
  materializeRegisteredSource(form = runtime.form, value = null) {
    return materializeRegisteredStrategySource(form, value);
  },
  confirmRegisteredSourceProbe(form = runtime.form, value = null) {
    return confirmRegisteredStrategySourceProbe(form, value);
  },
  getSelectionSnapshotMetadata(form = runtime.form) {
    const identity = selectedModelForForm(form);
    const model = runtime.catalog?.models?.find(
      (entry) => modelKey(entry) === modelKey(identity),
    );
    if (!model || !runtime.recommendationState) return null;
    const candidate = modelCandidate(runtime.recommendationState, model);
    const status = acceptanceStatus(runtime.recommendationState, model);
    const acceptanceStatusAtLaunch = ["accepted", "approved", "verified"].includes(status)
      ? "accepted"
      : ["stale", "needs_revalidation", "pending_review"].includes(status)
        ? "needs_revalidation"
        : "unproven";
    return Object.freeze({
      provider: model.provider,
      model: model.model,
      modelPublicLabel: String(model.publicLabel || model.model),
      selectionSource: canonicalSelectionSource(),
      recommendationReasonCodes: Object.freeze([...(candidate?.reasonCodes || [])]),
      recommendationWarningCodes: Object.freeze([...(candidate?.warningCodes || [])]),
      recommendationCatalogVersion: String(runtime.catalog.version || ""),
      acceptanceStatusAtLaunch,
    });
  },
  setModelCatalog(catalog) {
    if (!catalog || typeof catalog.version !== "string" || !Array.isArray(catalog.models)) return false;
    runtime.catalog = catalog;
    runtime.catalogStatus = "ready";
    runtime.recommendationState = null;
    window.ContentEngineWorkspaceRuntime?.setGenerationModelCatalog?.(catalog);
    if (runtime.form?.isConnected) {
      const pending = runtime.pendingRepeatSettings;
      runtime.pendingRepeatSettings = null;
      if (!pending || pending.form !== runtime.form || !applyRepeatedSettings(runtime.form, pending.detail)) {
        renderModelAdvisor(runtime.form);
      }
    }
    return true;
  },
  setStrategyCatalog(catalog) {
    const strategyState = createGenerationStrategyViewState(
      extractedStrategyCatalog(catalog),
    );
    if (strategyState.catalog_status !== "ready") return false;
    runtime.strategyCatalog = catalog;
    runtime.strategyCatalogStatus = "ready";
    runtime.strategyState = strategyState;
    if (runtime.form?.isConnected) {
      renderStrategyView(runtime.form);
      const pendingStrategy = runtime.pendingStrategyRestore;
      if (pendingStrategy?.form === runtime.form) {
        applyStrategyRestore(runtime.form, pendingStrategy.values);
      }
    }
    return true;
  },
  goToStep(value) {
    if (!runtime.form?.isConnected) return false;
    return moveTo(runtime.form, stepIndex(value));
  },
});

window.addEventListener("contentengine:workspace-runtime-ready", () => {
  if (
    runtime.form?.isConnected
    && !runtime.strategyCatalog
    && runtime.strategyCatalogStatus !== "loading"
  ) {
    void loadStrategyCatalog(runtime.form);
  }
  if (
    runtime.form?.isConnected
    && !runtime.catalog
    && runtime.catalogStatus !== "loading"
  ) {
    void loadModelCatalog(runtime.form);
  }
});

window.addEventListener("contentengine:generation-model-acceptance-updated", () => {
  if (runtime.form?.isConnected && runtime.catalog) renderModelAdvisor(runtime.form);
});
