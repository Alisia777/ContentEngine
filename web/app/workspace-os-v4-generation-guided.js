import {
  GENERATION_MODEL_RECOMMENDATION_ACTIONS,
  createGenerationModelRecommendationState,
  generationModelRecommendationReducer,
} from "./generation-model-recommendation.js?v=20260814.os4.41";
import { normalizeGenerationModelAcceptance } from "./generation-model-acceptance-view.js?v=20260814.os4.41";
import {
  GENERATION_STRATEGY_SELECT_ACTION,
  createGenerationStrategyViewState,
  generationStrategyViewMarkup,
  reduceGenerationStrategyViewState,
  selectedGenerationStrategySummary,
  validateSelectedGenerationStrategyDraft,
} from "./generation-strategy-view.js?v=20260814.os4.41";
import {
  generationStrategyAssetEligibility,
  mergeGenerationStrategyAssetPages,
  normalizeGenerationStrategyAssetCandidates,
} from "./generation-strategy-assets.js?v=20260814.os4.41";
import {
  GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS,
  createGenerationStrategySourcePicker,
  generationStrategyRequiredSourceCount,
  generationStrategySourcePickerProjection,
  reduceGenerationStrategySourcePicker,
} from "./generation-strategy-source-picker.js?v=20260814.os4.41";

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

const STEPS = Object.freeze([
  {
    key: "mode",
    label: "Способ создания",
    hint: "Сравните три сценария и выберите один вручную. Исходники, сохранение сцены и цена различаются.",
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
  recommendationState: null,
  applyingModel: false,
  modelFilter: "relevant",
  externalSelectionActive: false,
  repeatSettings: null,
  pendingRepeatSettings: null,
  strategyCatalog: null,
  strategyCatalogStatus: "idle",
  strategyCatalogRequest: 0,
  strategyState: null,
  pendingStrategyRestore: null,
  strategyAssetPage: null,
  strategyAssetProjectId: "",
  strategyAssetStatus: "idle",
  strategyAssetError: "",
  strategyAssetRequest: 0,
  strategySourcePicker: null,
  strategyMechanicsDrafts: new Map(),
  strategyViewRoots: new WeakSet(),
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
  accepted_recommendation: "Рекомендация ИИ принята",
  system_recommendation: "Предложено системой",
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
    "Ниже остаются исходные поля длительности, кампании, лимита и отдельного согласия на оплату.",
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
  section.append(grid, capabilityStatus);
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
    section.hidden = true;
    qa("[data-ce-v4-exact-model-control]", section).forEach((control) => { control.value = ""; });
    return false;
  }
  const previousKey = `${form.elements?.generation_provider?.value || ""}:${form.elements?.generation_model_id?.value || ""}`;
  const nextKey = modelKey(model);
  const sameModel = previousKey === nextKey;
  const defaults = exactDefaults(model);
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
    capabilityStatus.dataset.state = noExactCombination ? "blocked" : "ready";
    capabilityStatus.textContent = noExactCombination
      ? "Для этого сочетания разрешения и финального кадра нет допустимой длительности. Измените параметры — запуск заблокирован."
      : capability.lastFrameDuration !== null && selectedLastFrame
        ? `Финальный кадр требует точную длительность ${capability.lastFrameDuration} секунд.`
        : "Показаны только сочетания параметров, разрешённые выбранной моделью.";
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
  const eyebrow = element("p", "ce-v4-model-advisor__eyebrow", "СОВЕТ ИИ · РЕШЕНИЕ ЧЕЛОВЕКА");
  const title = element("h4", "", "Модели для вашего результата");
  title.id = "ce-v4-model-advisor-title";
  copy.append(
    eyebrow,
    title,
    element(
      "p",
      "",
      "ИИ сравнивает совместимость, качество, скорость и бюджет. Это совет: ручной выбор никогда не будет заменён автоматически.",
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
    "Системная рекомендация",
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
    label: "Финал и CTA",
    hint: "8–100 знаков.",
    min: 8,
    max: 100,
  }),
]);

function strategyMechanicsDraft(sourceMediaId) {
  const existing = runtime.strategyMechanicsDrafts.get(sourceMediaId);
  if (existing) return existing;
  return Object.fromEntries(STRATEGY_MECHANICS_FIELDS.map(({ key }) => [key, ""]));
}

function strategySourceCandidates() {
  return Array.isArray(runtime.strategyAssetPage?.assets)
    ? runtime.strategyAssetPage.assets
    : [];
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
      : "Этот MP4 остаётся референсом механики: мы создадим новый ролик с вашими ассетами, а не копию кадр в кадр.",
  );
  details.append(copy);
  if (strategyId !== "viral_product_swap") {
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
  if (!status) return;
  if (runtime.strategyAssetStatus === "loading") {
    status.dataset.state = "loading";
    status.textContent = "Проверяем доступные исходники проекта. Файлы никуда не отправляются.";
    return;
  }
  if (runtime.strategyAssetStatus === "error") {
    status.dataset.state = "warning";
    status.textContent = "Не удалось получить серверный список исходников. Платный запуск заблокирован; обновите список.";
    return;
  }
  if (!runtime.strategyAssetPage) {
    status.dataset.state = "pending";
    status.textContent = "Загрузите серверный список исходников. Браузер не подставляет локальные файлы как платную авторизацию.";
    return;
  }
  const requiredOwnedRoles = row.asset_roles
    .filter((role) => (
      role.role !== "source_video"
      && STRATEGY_ASSET_CONTROL_BY_ROLE[role.role]
    ));
  const missing = requiredOwnedRoles.filter((role) => {
    const control = form.elements?.[STRATEGY_ASSET_CONTROL_BY_ROLE[role.role]];
    return !(control instanceof HTMLSelectElement)
      || ![...control.options].some((option) => !option.disabled && option.value);
  });
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
  if (sourceProjection?.probe_required_source_ids?.length) {
    status.dataset.state = "warning";
    status.textContent = `Для ${sourceProjection.probe_required_source_ids.length} выбранных MP4 нужна бесплатная серверная проверка длительности. До неё подготовка и платный запуск недоступны.`;
    return;
  }
  const sourceCount = sourceProjection?.selected_count || 0;
  const requiredCount = sourceProjection?.required_count
    || generationStrategyRequiredSourceCount(row.strategy_id);
  const incompleteSources = sourceCount !== requiredCount;
  status.dataset.state = missing.length || incompleteSources ? "warning" : "ready";
  status.textContent = missing.length
    ? "Для одной из обязательных ролей нет подходящего серверно подтверждённого файла. Добавьте исходник в Материалы или загрузите следующую страницу."
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
  const fieldset = q("#generation-strategy-assets", form);
  if (fieldset instanceof HTMLFieldSetElement) {
    fieldset.hidden = true;
    fieldset.disabled = true;
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
  ].forEach((control) => {
    if (
      control instanceof HTMLInputElement
      || control instanceof HTMLSelectElement
      || control instanceof HTMLTextAreaElement
    ) {
      control.disabled = strategySelected;
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
  }
  const advisor = q("[data-ce-v4-model-advisor]", form);
  if (advisor instanceof HTMLElement) {
    advisor.hidden = false;
    advisor.dataset.strategyAdvisoryOnly = strategySelected ? "true" : "false";
  }
}

function syncStrategyForm(form, { reset = false } = {}) {
  const row = selectedStrategyRow();
  const summary = selectedGenerationStrategySummary(runtime.strategyState);
  if (!row || !summary.ok) {
    resetStrategyForm(form);
    syncLegacyModelVisibility(form, false);
    return false;
  }

  const fieldset = q("#generation-strategy-assets", form);
  if (!(fieldset instanceof HTMLFieldSetElement)) return false;
  fieldset.hidden = false;
  fieldset.disabled = false;
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
    replaceStrategyOptions(
      ratio,
      row.output_rules.ratios,
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
  const productRole = roleIds.has("new_product_image")
    ? "new_product_image"
    : roleIds.has("product_image")
      ? "product_image"
      : "";
  if (productRole) {
    qa('input[name="media_id"]:checked:not(:disabled)', form).forEach((input) => {
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
  if (strategyId === "viral_product_swap") return null;
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
    ? [...new Set(values.generation_strategy_product_media_ids.map(
        (value) => String(value || "").trim().toLowerCase(),
      ).filter(Boolean))]
    : [];
  const availableProductMedia = new Set(
    qa('input[name="media_id"]:not(:disabled)', form).map((input) => (
      String(input.value || "").trim().toLowerCase()
    )),
  );
  const productMediaAvailable = requestedProductMedia.every((mediaId) => (
    availableProductMedia.has(mediaId)
  ));
  if (requestedProductMedia.length && productMediaAvailable) {
    const selected = new Set(requestedProductMedia);
    qa('input[name="media_id"]', form).forEach((input) => {
      input.checked = selected.has(String(input.value || "").trim().toLowerCase())
        && !input.disabled;
    });
    qa('input[name="primary_media_id"]', form).forEach((input) => {
      input.checked = String(input.value || "").trim().toLowerCase()
        === requestedProductMedia[0] && !input.disabled;
    });
  }
  if (
    unresolvedAssetControls.length
    && runtime.strategyAssetStatus !== "ready"
  ) {
    runtime.pendingStrategyRestore = { form, values: { ...values } };
    if (runtime.strategyAssetStatus !== "loading") {
      void loadGenerationStrategyAssets(form);
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
  const provider = element("span", "ce-v4-model-card__provider", String(model.provider || "ИИ").toUpperCase());
  const flag = element(
    "span",
    recommended ? "ce-v4-model-card__flag is-recommended" : "ce-v4-model-card__flag",
    recommended && selected
      ? "Ваш выбор · ИИ советует"
      : recommended
        ? "ИИ советует"
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
  choice.append(
    radio,
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
      element("strong", "", "Нет совместимой рекомендации"),
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
  const title = element("div", "ce-v4-model-recommendation-hero__title");
  title.append(
    element("span", "ce-v4-model-recommendation-hero__source", recommendationSource(state)),
    element("small", "", `Рекомендация ИИ · ${String(suggestedModel.provider || "ИИ").toUpperCase()}`),
    element("strong", "", String(suggestedModel.publicLabel || suggestedModel.model)),
  );
  const metrics = element("div", "ce-v4-model-recommendation-hero__metrics");
  const costMetric = element("span", "");
  costMetric.append(element("small", "", "Оценка цены"), element("strong", "", cost.text));
  const readinessMetric = element("span", "");
  readinessMetric.dataset.state = readiness.state;
  readinessMetric.append(element("small", "", "Готовность"), element("strong", "", readiness.text));
  metrics.append(costMetric, readinessMetric);
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
  details.append(element("summary", "", "Почему эта рекомендация?"));
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
    accepted ? "Рекомендация принята" : "Применить рекомендацию",
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
      comparisonCell("ИИ советует", suggestedModel, form, state),
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
      summaryRow("Фактический запуск", "Точный Runway recipe подтверждает сервер"),
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
    grid.replaceChildren();
    recommendation.hidden = true;
    syncModelLaunchGuard(form, "");
    const summary = q("[data-ce-v4-model-selection-summary-body]", form);
    if (summary) {
      summary.dataset.state = runtime.catalogStatus === "error" ? "blocked" : "loading";
      summary.replaceChildren(
        element("strong", "ce-v4-model-selection-summary__title", runtime.catalogStatus === "error"
          ? "Каталог моделей не ответил"
          : "Загружаем точный каталог…"),
        element("p", "ce-v4-model-selection-summary__note", "Исходный режим формы сохранён. Мы не выдумываем модель, цену или готовность без ответа сервера."),
      );
    }
    status.dataset.state = runtime.catalogStatus === "error" ? "error" : "loading";
    status.textContent = runtime.catalogStatus === "error"
      ? "Каталог моделей сейчас недоступен. Текущий режим формы сохранён; платный запуск не изменён."
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
    ? "ИИ предлагает несколько моделей для сравнения. Для этого сценария карточки носят рекомендательный характер; платно запускается только серверно подтверждённый recipe."
    : !selectionActive
    ? explicitDryRun
      ? "Вы явно выбрали dry-run. Он создаст только задачи без медиафайла и списания."
      : "Способ создания ещё не выбран. Ни dry-run, ни платная генерация не включатся автоматически."
    : selectedModel
      ? state.manualLock
        ? `Ваш выбор: ${selectedModel.publicLabel || selectedModel.model}. Он зафиксирован: новые советы ИИ не заменят его без вашей команды.`
        : `Предложение ИИ: ${selectedModel.publicLabel || selectedModel.model}. Применение требует вашего действия.`
      : "Выберите доступную модель. Рекомендация ИИ носит только советующий характер.";
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
      throw new Error("generation_strategy_catalog_invalid");
    }
    runtime.strategyCatalog = catalog;
    runtime.strategyCatalogStatus = "ready";
    runtime.strategyState = strategyState;
    const targetForm = form.isConnected ? form : runtime.form;
    if (!targetForm?.isConnected) return;
    renderStrategyView(targetForm);
    const pendingStrategy = runtime.pendingStrategyRestore;
    if (pendingStrategy?.form === targetForm) {
      applyStrategyRestore(targetForm, pendingStrategy.values);
    }
  } catch {
    if (request !== runtime.strategyCatalogRequest) return;
    runtime.strategyCatalogStatus = "error";
    runtime.strategyState = createGenerationStrategyViewState(null);
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
    element("p", "ce-v4-generation-guided__eyebrow", "ТРИ СТРАТЕГИИ ГЕНЕРАЦИИ"),
    element("h2", "", "Сначала решите, как использовать референс"),
    element("p", "", "Новый UGC с аватаром, замена товара в исходном ролике или новая реклама по его механике. Ничего не выбирается и не оплачивается автоматически."),
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
    if (node === shell || node === submit) return;
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
  control.hidden = false;
  control.removeAttribute("tabindex");
  control.setAttribute("aria-hidden", "false");
  control.classList.add("ce-v4-generation-guided__preflight");
}

function adoptDirectChildren(form, shell) {
  const loose = [...form.children].filter((node) => node !== shell);
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
  const available = qa('input[name="media_id"]:not(:disabled)', panel);
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
    const complete = index < STEPS.length - 1
      ? panelValidity(form, index).valid
      : Boolean(q("#generation-submit", form) && !q("#generation-submit", form).disabled);
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
    value: Object.freeze({ controller, owner: handleFormClick }),
  });
}

function setupForm(form, { initialSync = true } = {}) {
  let shell = q(":scope > [data-ce-v4-generation-guided-shell]", form);
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
  return shell;
}

function mount() {
  if (routePath() !== ROUTE) {
    document.body.classList.remove("ce-v4-generation-guided-route");
    runtime.form = null;
    runtime.pendingRepeatSettings = null;
    runtime.strategyAssetRequest += 1;
    runtime.strategyAssetStatus = "idle";
    runtime.strategyAssetError = "";
    runtime.strategySourcePicker = null;
    runtime.strategyMechanicsDrafts.clear();
    return;
  }
  const form = q("#mock-batch-form");
  if (!form) return;
  const formChanged = runtime.form !== form;
  if (formChanged) {
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

window.ContentEngineDesktopV4.registerAdapter("generation-guided", mount, { priority: 180 });

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
  refreshStrategyAssets(form = runtime.form) {
    if (!form?.isConnected) return Promise.resolve(false);
    return loadGenerationStrategyAssets(form);
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
