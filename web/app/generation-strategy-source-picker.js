import {
  generationStrategyAssetEligibility,
} from "./generation-strategy-assets.js?v=20260826.rebuild-clean.60";

/*
 * Pure ordered source-video picker for a ten-output strategy run.
 *
 * The picker receives only the already-normalized public asset projection.
 * It never stores object names, URLs, hashes, prompts, attestations, prices,
 * receipts, provider identities, or launch authority. Selecting a video is
 * therefore an editing action only; it cannot start a free or paid request.
 */

export const GENERATION_STRATEGY_SOURCE_PICKER_VERSION =
  "generation-strategy-source-picker-v1";

export const GENERATION_STRATEGY_SOURCE_COUNT = 10;
// «Создание» с 26.08.2026 — ОДИН референс-хит по умолчанию: владелец просил
// форму «как Копия, только без загрузки видео». Референс провайдеру не уходит
// (forwarded_to_provider = false, buildProductAd отвергает source_video) — он
// смысловой якорь механики.
export const GENERATION_STRATEGY_SOURCE_REQUIREMENTS = Object.freeze({
  viral_avatar_ugc: 1,
  viral_product_swap: 1,
  viral_rebuild: 1,
});
// Массовый режим M1 (29.08.2026): требование — СОСТОЯНИЕ пикера, а не
// свойство стратегии. Карта режимов перечисляет допустимые размеры на
// стратегию; дефолт остаётся одиночным, пакет включается только явным
// переключателем оператора. «Копия» и «Дуэт» пакетов не имеют.
export const GENERATION_STRATEGY_SOURCE_COUNT_MODES = Object.freeze({
  viral_avatar_ugc: Object.freeze([1]),
  viral_product_swap: Object.freeze([1]),
  viral_rebuild: Object.freeze([1, GENERATION_STRATEGY_SOURCE_COUNT]),
});

export function generationStrategyRequiredSourceCount(strategyId) {
  const strategy = cleanStrategyId(strategyId);
  return strategy ? GENERATION_STRATEGY_SOURCE_REQUIREMENTS[strategy] : 0;
}

export function generationStrategySourceCountModes(strategyId) {
  const strategy = cleanStrategyId(strategyId);
  return strategy ? GENERATION_STRATEGY_SOURCE_COUNT_MODES[strategy] : Object.freeze([]);
}

export const GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS = Object.freeze({
  replaceCandidates: "REPLACE_CANDIDATES",
  toggle: "TOGGLE",
  reset: "RESET",
  setRequiredCount: "SET_REQUIRED_COUNT",
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const STRATEGY_IDS = Object.freeze(new Set([
  "viral_avatar_ugc",
  "viral_product_swap",
  "viral_rebuild",
]));

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

function cleanUuid(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return UUID_PATTERN.test(normalized) ? normalized : "";
}

function cleanStrategyId(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return STRATEGY_IDS.has(normalized) ? normalized : "";
}

function safeFilename(value) {
  const normalized = String(value || "").trim();
  if (
    !normalized
    || normalized.length > 255
    || /[\u0000-\u001f\u007f]/u.test(normalized)
  ) return "";
  return normalized;
}

function probeOnly(blockers) {
  return blockers.length === 1
    && blockers[0] === "server_duration_probe_required";
}

function normalizeCandidate(asset, strategyId) {
  const id = cleanUuid(asset?.id);
  const filename = safeFilename(asset?.filename);
  if (
    !id
    || !filename
    || asset?.kind !== "source_video"
    || asset?.mime_type !== "video/mp4"
    || asset?.status !== "ready"
    || asset?.rights_confirmed !== true
    || (
      asset?.exact_youtube_attached !== true
      && asset?.direct_mp4_attached !== true
    )
  ) return null;
  const eligibility = generationStrategyAssetEligibility(
    asset,
    strategyId,
    "source_video",
  );
  const blockers = [...eligibility.blockers];
  const needsProbe = !eligibility.eligible && probeOnly(blockers);
  if (!eligibility.eligible && !needsProbe) return null;
  const duration = asset.duration_seconds === null
    ? null
    : Number(asset.duration_seconds);
  if (
    duration !== null
    && (!Number.isFinite(duration) || duration <= 0 || duration > 3_600)
  ) return null;
  return deepFreeze({
    id,
    filename,
    duration_seconds: duration,
    ready: eligibility.eligible,
    probe_required: needsProbe,
    blocking_codes: Object.freeze(blockers),
  });
}

// Повторные загрузки одного файла дают несколько media-строк с одинаковым
// именем: список из «файла ×3», где часть копий ещё и без измеренной
// длительности, читался как поломка («задвоение форм», 25.08.2026).
// Показываем один кандидат на имя файла, выбирая лучшую копию: готовую и с
// длительностью раньше непроверенной. Остальные копии никуда не деваются —
// они остаются проверочными ассетами спенд-контура.
function candidateQuality(candidate) {
  return (candidate.ready ? 2 : 0) + (candidate.duration_seconds !== null ? 1 : 0);
}

function normalizeCandidates(candidates, strategyId) {
  if (!Array.isArray(candidates)) return [];
  const seen = new Set();
  const byFilename = new Map();
  const order = [];
  for (const asset of candidates) {
    const candidate = normalizeCandidate(asset, strategyId);
    if (!candidate || seen.has(candidate.id)) continue;
    seen.add(candidate.id);
    const existing = byFilename.get(candidate.filename);
    if (!existing) {
      byFilename.set(candidate.filename, candidate);
      order.push(candidate.filename);
    } else if (candidateQuality(candidate) > candidateQuality(existing)) {
      byFilename.set(candidate.filename, candidate);
    }
  }
  return order.map((filename) => byFilename.get(filename));
}

function pristine(strategyId, candidates = [], requiredCount) {
  return deepFreeze({
    version: GENERATION_STRATEGY_SOURCE_PICKER_VERSION,
    strategy_id: strategyId,
    revision: 0,
    required_count: requiredCount,
    candidates: Object.freeze(candidates),
    selected_source_ids: Object.freeze([]),
    error: null,
  });
}

function validState(value) {
  if (
    !value
    || typeof value !== "object"
    || value.version !== GENERATION_STRATEGY_SOURCE_PICKER_VERSION
    || !cleanStrategyId(value.strategy_id)
    || !Number.isSafeInteger(value.revision)
    || value.revision < 0
    || !Array.isArray(value.candidates)
    || !Array.isArray(value.selected_source_ids)
    || !generationStrategySourceCountModes(value.strategy_id)
      .includes(value.required_count)
    || value.selected_source_ids.length > value.required_count
    || new Set(value.selected_source_ids).size !== value.selected_source_ids.length
    || !Object.isFrozen(value)
  ) return false;
  const candidateIds = new Set(value.candidates.map((entry) => entry.id));
  return value.selected_source_ids.every((id) => (
    cleanUuid(id) === id && candidateIds.has(id)
  ));
}

function withError(state, code) {
  return deepFreeze({ ...state, error: code });
}

export function createGenerationStrategySourcePicker(
  strategyId,
  candidates = [],
  options = {},
) {
  const strategy = cleanStrategyId(strategyId);
  if (!strategy) return null;
  const modes = generationStrategySourceCountModes(strategy);
  const requested = options?.requiredCount === undefined
    ? generationStrategyRequiredSourceCount(strategy)
    : options.requiredCount;
  if (!modes.includes(requested)) return null;
  return pristine(strategy, normalizeCandidates(candidates, strategy), requested);
}

export function reduceGenerationStrategySourcePicker(state, action) {
  if (!validState(state) || !action || typeof action !== "object") return null;
  if (action.type === GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.reset) {
    if (Object.keys(action).length !== 1) return withError(state, "action_invalid");
    return deepFreeze({
      ...state,
      revision: state.revision + 1,
      selected_source_ids: Object.freeze([]),
      error: null,
    });
  }
  if (action.type === GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.replaceCandidates) {
    if (
      Object.keys(action).sort().join(",") !== "candidates,strategy_id,type"
    ) return withError(state, "action_invalid");
    const strategy = cleanStrategyId(action.strategy_id);
    if (!strategy) return withError(state, "strategy_invalid");
    const candidates = normalizeCandidates(action.candidates, strategy);
    const candidateIds = new Set(candidates.map((entry) => entry.id));
    const selected = strategy === state.strategy_id
      ? state.selected_source_ids.filter((id) => candidateIds.has(id))
      : [];
    // Требование живёт в состоянии: обновление каталога кандидатов не
    // выключает выбранный режим. Смена стратегии возвращает её дефолт.
    const requiredCount = strategy === state.strategy_id
      ? state.required_count
      : generationStrategyRequiredSourceCount(strategy);
    const changed = strategy !== state.strategy_id
      || selected.length !== state.selected_source_ids.length
      || JSON.stringify(candidates) !== JSON.stringify(state.candidates);
    return deepFreeze({
      version: GENERATION_STRATEGY_SOURCE_PICKER_VERSION,
      strategy_id: strategy,
      revision: state.revision + (changed ? 1 : 0),
      required_count: requiredCount,
      candidates: Object.freeze(candidates),
      selected_source_ids: Object.freeze(selected),
      error: null,
    });
  }
  if (action.type === GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.setRequiredCount) {
    if (
      Object.keys(action).sort().join(",") !== "required_count,type"
    ) return withError(state, "action_invalid");
    const modes = generationStrategySourceCountModes(state.strategy_id);
    if (!modes.includes(action.required_count)) {
      return withError(state, "required_count_unsupported");
    }
    if (action.required_count === state.required_count) return state;
    // Сжатие пакета до одиночного режима оставляет ПЕРВЫЙ выбранный ролик:
    // порядок выбора — часть контракта, и первый хит — самый осознанный.
    const selected = state.selected_source_ids.slice(0, action.required_count);
    return deepFreeze({
      ...state,
      revision: state.revision + 1,
      required_count: action.required_count,
      selected_source_ids: Object.freeze(selected),
      error: null,
    });
  }
  if (action.type === GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.toggle) {
    if (
      Object.keys(action).sort().join(",") !== "source_media_id,type"
    ) return withError(state, "action_invalid");
    const id = cleanUuid(action.source_media_id);
    const candidate = state.candidates.find((entry) => entry.id === id);
    if (!id || !candidate) return withError(state, "source_not_selectable");
    const currentIndex = state.selected_source_ids.indexOf(id);
    const selected = [...state.selected_source_ids];
    if (currentIndex >= 0) {
      selected.splice(currentIndex, 1);
    } else if (selected.length >= state.required_count) {
      return withError(state, "source_limit_reached");
    } else {
      selected.push(id);
    }
    return deepFreeze({
      ...state,
      revision: state.revision + 1,
      selected_source_ids: Object.freeze(selected),
      error: null,
    });
  }
  return withError(state, "action_unsupported");
}

export function generationStrategySourcePickerProjection(state) {
  if (!validState(state)) return null;
  const byId = new Map(state.candidates.map((entry) => [entry.id, entry]));
  const selected = state.selected_source_ids.map((id, index) => {
    const candidate = byId.get(id);
    return deepFreeze({
      position: index + 1,
      source_media_id: id,
      filename: candidate.filename,
      duration_seconds: candidate.duration_seconds,
      ready: candidate.ready,
      probe_required: candidate.probe_required,
      blocking_codes: Object.freeze([...candidate.blocking_codes]),
    });
  });
  const probeIds = selected
    .filter((entry) => entry.probe_required)
    .map((entry) => entry.source_media_id);
  const requiredCount = state.required_count;
  const exactRequired = selected.length === requiredCount;
  return deepFreeze({
    version: state.version,
    strategy_id: state.strategy_id,
    revision: state.revision,
    selected_count: selected.length,
    required_count: requiredCount,
    exact_required_selected: exactRequired,
    exactly_ten_selected:
      requiredCount === GENERATION_STRATEGY_SOURCE_COUNT && exactRequired,
    all_selected_ready: exactRequired && probeIds.length === 0,
    selected: Object.freeze(selected),
    probe_required_source_ids: Object.freeze(probeIds),
    error: state.error,
  });
}

export function generationStrategySourcePickerSelection(state) {
  const projection = generationStrategySourcePickerProjection(state);
  if (!projection?.all_selected_ready) return null;
  return Object.freeze(projection.selected.map((entry) => entry.source_media_id));
}
