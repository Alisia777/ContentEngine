/*
 * Pure accessible view contract for the exact-count generation queue.
 *
 * Размер очереди берётся из GENERATION_STRATEGY_QUEUE_SIZES ({1, 10}): с 26.08
 * «Создание» ходит одним референс-хитом, десятка осталась массовым режимом.
 *
 * Inputs are already-safe projections. This module normalizes them into a
 * compact display model and deterministic escaped markup. It has no DOM,
 * network, storage, clock, randomness, or execution authority.
 */

import {
  GENERATION_STRATEGY_SOURCE_COUNT,
  GENERATION_STRATEGY_SOURCE_PICKER_VERSION,
} from "./generation-strategy-source-picker.js?v=20260826.rebuild-clean.60";
import {
  GENERATION_STRATEGY_QUEUE_SIZE,
  GENERATION_STRATEGY_QUEUE_SIZES,
  GENERATION_STRATEGY_QUEUE_VERSION,
} from "./generation-strategy-queue.js?v=20260826.rebuild-clean.60";

export const GENERATION_STRATEGY_QUEUE_VIEW_VERSION =
  "generation-strategy-queue-view-v1";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const CODE_PATTERN = /^[a-z0-9][a-z0-9_.-]{0,127}$/u;
const STRATEGY_IDS = Object.freeze(new Set([
  "viral_avatar_ugc",
  "viral_product_swap",
  "viral_rebuild",
]));
const RUNTIME_PHASES = Object.freeze(new Set([
  "idle",
  "selected",
  "bound",
  "preflight_ready",
  "human_confirmed",
  "start_once",
  "status",
  "invalid",
]));
const JOB_STATUSES = Object.freeze(new Set([
  "queued",
  "starting",
  "submitted",
  "processing",
  "succeeded",
  "failed",
  "cancelled",
]));
const SOURCE_TOP_KEYS = Object.freeze([
  "version",
  "strategy_id",
  "revision",
  "selected_count",
  "required_count",
  "exact_required_selected",
  "exactly_ten_selected",
  "all_selected_ready",
  "selected",
  "probe_required_source_ids",
  "error",
]);
const SOURCE_ROW_KEYS = Object.freeze([
  "position",
  "source_media_id",
  "filename",
  "duration_seconds",
  "ready",
  "probe_required",
  "blocking_codes",
]);
const QUEUE_TOP_KEYS = Object.freeze([
  "version",
  "revision",
  "row_count",
  "rows",
]);
const QUEUE_ROW_KEYS = Object.freeze(["source_media_id", "runtime"]);
const RUNTIME_KEYS = Object.freeze([
  "version",
  "phase",
  "fingerprint",
  "identity",
  "binding",
  "price",
  "readiness",
  "campaign_id",
  "start_context_fingerprint",
  "job",
  "reconciliation",
  "output",
  "error",
  "can_preflight",
  "can_confirm",
  "can_start",
  "start_reserved",
  "can_poll",
]);
const REVIEW_KEYS = Object.freeze([
  "version",
  "display_only",
  "confirmation",
  "queue_revision",
  "prior_review_current",
  "ready",
  "server_priced",
  "row_count",
  "currency",
  "total_estimated_cost_minor",
  "rows",
]);
const PHASE_LABELS = Object.freeze({
  empty: "Ролик не выбран",
  source_ready: "Источник выбран",
  probe_required: "Нужна проверка MP4",
  queue_stale: "Состав очереди изменился",
  idle: "Ожидает настройки",
  selected: "Выбор зафиксирован",
  bound: "Ассеты проверены сервером",
  preflight_ready: "Бесплатная проверка готова",
  human_confirmed: "Платный старт подтверждён отдельно",
  start_once: "Платный старт отправляется",
  status: "Задача создана",
  invalid: "Нужно подготовить заново",
});
const JOB_LABELS = Object.freeze({
  queued: "В очереди",
  starting: "Запускается",
  submitted: "Передано в генерацию",
  processing: "Генерируется",
  succeeded: "Готово — нужна проверка",
  failed: "Завершилось с ошибкой",
  cancelled: "Отменено",
});
// Тексты, зависящие от размера очереди. Ветка 10 — байт-в-байт прежние
// строки: при десятке вывод обязан не измениться ни на символ.
const QUEUE_SIZE_COPY = Object.freeze({
  10: Object.freeze({
    eyebrow: "10 копий выбранных механик",
    heading: "Очередь из десяти роликов",
    review_title: "Обзор точных десяти",
    review_button: "Проверить точные десять",
    remove_button: "Убрать из десяти",
    total_pending:
      "появится, когда бесплатная проверка будет готова для всех десяти роликов",
    stale_notice:
      "Состав выбранных роликов изменился. Бесплатно подготовьте точные десять заново.",
    stale_readiness: "Подготовьте обновлённый состав из десяти роликов",
    sequential:
      "Каждый из 10 роликов запускается отдельным платным запросом; старты выполняются последовательно.",
  }),
  1: Object.freeze({
    eyebrow: "Одна копия выбранной механики",
    heading: "Очередь из одного ролика",
    review_title: "Обзор единственного ролика",
    review_button: "Проверить единственный ролик",
    remove_button: "Убрать из очереди",
    total_pending:
      "появится, когда бесплатная проверка будет готова для этого ролика",
    stale_notice:
      "Выбранный ролик изменился. Бесплатно подготовьте его заново.",
    stale_readiness: "Подготовьте обновлённый ролик заново",
    sequential:
      "Единственный ролик запускается отдельным платным запросом; старт выполняется один раз.",
  }),
});

const BUTTON_CLASS =
  "generation-strategy-queue-view__action generation-strategy-queue-view__min-44";

class ViewContractError extends Error {}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactObject(value, keys) {
  if (!isPlainObject(value)) throw new ViewContractError("object_required");
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length ||
    actual.some((key, index) => key !== expected[index])
  ) throw new ViewContractError("object_keys_mismatch");
  return value;
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
}

function exactUuid(value) {
  if (typeof value !== "string" || !UUID_PATTERN.test(value)) {
    throw new ViewContractError("uuid_invalid");
  }
  return value;
}

function exactCode(value) {
  if (typeof value !== "string" || !CODE_PATTERN.test(value)) {
    throw new ViewContractError("code_invalid");
  }
  return value;
}

function exactBoolean(value) {
  if (typeof value !== "boolean") throw new ViewContractError("boolean_invalid");
  return value;
}

function safeInteger(value, min = 0, max = Number.MAX_SAFE_INTEGER) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new ViewContractError("integer_invalid");
  }
  return value;
}

function safeFilename(value) {
  if (
    typeof value !== "string" ||
    value.trim() !== value ||
    !value ||
    value.length > 255 ||
    /[\u0000-\u001f\u007f]/u.test(value)
  ) throw new ViewContractError("filename_invalid");
  return value;
}

function nullableErrorCode(value) {
  if (value === null) return null;
  return exactCode(value);
}

function normalizeSourceProjection(raw) {
  const source = exactObject(raw, SOURCE_TOP_KEYS);
  if (
    source.version !== GENERATION_STRATEGY_SOURCE_PICKER_VERSION ||
    !STRATEGY_IDS.has(source.strategy_id)
  ) throw new ViewContractError("source_projection_invalid");
  const revision = safeInteger(source.revision);
  // Размер валиден только когда он есть и в контракте очереди, и в таблице
  // текстов: расхождение SIZES и QUEUE_SIZE_COPY обязано закрываться отказом
  // модели, а не TypeError на copy.* посреди рендера.
  if (
    !GENERATION_STRATEGY_QUEUE_SIZES.has(source.required_count) ||
    !Object.hasOwn(QUEUE_SIZE_COPY, source.required_count)
  ) {
    throw new ViewContractError("source_count_invalid");
  }
  const requiredCount = source.required_count;
  const selectedCount = safeInteger(
    source.selected_count,
    0,
    requiredCount,
  );
  if (
    !Array.isArray(source.selected) ||
    source.selected.length !== selectedCount ||
    !Array.isArray(source.probe_required_source_ids)
  ) throw new ViewContractError("source_count_invalid");
  const seen = new Set();
  const selected = source.selected.map((rawRow, index) => {
    const row = exactObject(rawRow, SOURCE_ROW_KEYS);
    const sourceMediaId = exactUuid(row.source_media_id);
    if (seen.has(sourceMediaId) || row.position !== index + 1) {
      throw new ViewContractError("source_order_invalid");
    }
    seen.add(sourceMediaId);
    const ready = exactBoolean(row.ready);
    const probeRequired = exactBoolean(row.probe_required);
    if (ready === probeRequired || !Array.isArray(row.blocking_codes)) {
      throw new ViewContractError("source_readiness_invalid");
    }
    const blockingCodes = row.blocking_codes.map(exactCode);
    if (
      (ready && blockingCodes.length !== 0) ||
      (probeRequired && (
        blockingCodes.length !== 1 ||
        blockingCodes[0] !== "server_duration_probe_required"
      ))
    ) throw new ViewContractError("source_blockers_invalid");
    let durationSeconds = null;
    if (row.duration_seconds !== null) {
      if (
        typeof row.duration_seconds !== "number" ||
        !Number.isFinite(row.duration_seconds) ||
        row.duration_seconds <= 0 ||
        row.duration_seconds > 3_600
      ) throw new ViewContractError("source_duration_invalid");
      durationSeconds = row.duration_seconds;
    }
    return deepFreeze({
      position: index + 1,
      source_media_id: sourceMediaId,
      filename: safeFilename(row.filename),
      duration_seconds: durationSeconds,
      ready,
      probe_required: probeRequired,
    });
  });
  const probeIds = source.probe_required_source_ids.map(exactUuid);
  const expectedProbeIds = selected
    .filter((row) => row.probe_required)
    .map((row) => row.source_media_id);
  if (
    JSON.stringify(probeIds) !== JSON.stringify(expectedProbeIds) ||
    source.exact_required_selected !== (selectedCount === requiredCount) ||
    source.exactly_ten_selected !== (
      requiredCount === GENERATION_STRATEGY_SOURCE_COUNT &&
      selectedCount === requiredCount
    ) ||
    source.all_selected_ready !== (
      selectedCount === requiredCount &&
      expectedProbeIds.length === 0
    )
  ) throw new ViewContractError("source_projection_mismatch");
  return deepFreeze({
    strategy_id: source.strategy_id,
    revision,
    selected_count: selectedCount,
    required_count: requiredCount,
    exact_required_selected: source.exact_required_selected,
    exactly_ten_selected: source.exactly_ten_selected,
    all_selected_ready: source.all_selected_ready,
    selected,
    error_code: nullableErrorCode(source.error),
  });
}

function normalizePrice(raw) {
  if (raw === null) return null;
  if (!isPlainObject(raw)) throw new ViewContractError("price_invalid");
  const costMinor = safeInteger(raw.estimated_cost_minor, 1, 1_000_000);
  if (
    raw.currency !== "USD" ||
    typeof raw.estimated_cost_usd !== "string" ||
    !/^\d{1,7}\.\d{2}$/u.test(raw.estimated_cost_usd) ||
    raw.estimated_cost_usd !== (costMinor / 100).toFixed(2)
  ) throw new ViewContractError("price_invalid");
  return deepFreeze({
    estimated_cost_minor: costMinor,
    currency: "USD",
  });
}

function normalizeJob(raw) {
  if (raw === null) return null;
  if (!isPlainObject(raw) || !JOB_STATUSES.has(raw.status)) {
    throw new ViewContractError("job_invalid");
  }
  return deepFreeze({ status: raw.status });
}

function normalizeRuntimeError(raw) {
  if (raw === null) return null;
  if (!isPlainObject(raw)) throw new ViewContractError("runtime_error_invalid");
  return exactCode(raw.code);
}

function normalizeRuntime(raw) {
  const runtime = exactObject(raw, RUNTIME_KEYS);
  if (
    runtime.version !== GENERATION_STRATEGY_QUEUE_VERSION ||
    !RUNTIME_PHASES.has(runtime.phase)
  ) {
    throw new ViewContractError("runtime_phase_invalid");
  }
  const phase = runtime.phase;
  const price = normalizePrice(runtime.price);
  const job = normalizeJob(runtime.job);
  const readinessReady = runtime.readiness === null
    ? false
    : exactBoolean(runtime.readiness?.ready);
  const launchEnabled = runtime.readiness === null
    ? false
    : exactBoolean(runtime.readiness?.launch_enabled);
  const reconciliationRequired = runtime.reconciliation === null
    ? false
    : exactBoolean(runtime.reconciliation?.required);
  const canPreflight = exactBoolean(runtime.can_preflight);
  const canConfirm = exactBoolean(runtime.can_confirm);
  const canStart = exactBoolean(runtime.can_start);
  const startReserved = exactBoolean(runtime.start_reserved);
  const canPoll = exactBoolean(runtime.can_poll);
  const priceRequired = [
    "bound",
    "preflight_ready",
    "human_confirmed",
    "start_once",
    "status",
  ].includes(phase);
  const readinessRequired = [
    "preflight_ready",
    "human_confirmed",
    "start_once",
    "status",
  ].includes(phase);
  const expectedCanPoll = phase === "status" &&
    ["submitted", "processing"].includes(job?.status);
  if (
    canPreflight !== (phase === "bound") ||
    canConfirm !== (phase === "preflight_ready") ||
    canStart !== (phase === "human_confirmed") ||
    startReserved !== (phase === "start_once") ||
    canPoll !== expectedCanPoll ||
    (phase === "status") !== (job !== null) ||
    priceRequired !== (price !== null) ||
    readinessRequired !== (runtime.readiness !== null) ||
    (readinessRequired && (!readinessReady || !launchEnabled)) ||
    (reconciliationRequired && phase !== "status")
  ) throw new ViewContractError("runtime_state_mismatch");
  return deepFreeze({
    phase,
    price,
    free_ready: readinessReady && launchEnabled,
    job_status: job?.status || null,
    reconciliation_required: reconciliationRequired,
    error_code: normalizeRuntimeError(runtime.error),
    can_preflight: canPreflight,
    can_confirm: canConfirm,
    can_start: canStart,
    start_reserved: startReserved,
    can_poll: canPoll,
  });
}

function normalizeQueueRow(raw) {
  const row = exactObject(raw, QUEUE_ROW_KEYS);
  return deepFreeze({
    source_media_id: exactUuid(row.source_media_id),
    runtime: normalizeRuntime(row.runtime),
  });
}

function normalizeQueueProjection(raw) {
  const queue = exactObject(raw, QUEUE_TOP_KEYS);
  if (
    queue.version !== GENERATION_STRATEGY_QUEUE_VERSION ||
    !GENERATION_STRATEGY_QUEUE_SIZES.has(queue.row_count) ||
    !Array.isArray(queue.rows) ||
    queue.rows.length !== queue.row_count
  ) throw new ViewContractError("queue_projection_invalid");
  const rows = queue.rows.map(normalizeQueueRow);
  if (new Set(rows.map((row) => row.source_media_id)).size !== rows.length) {
    throw new ViewContractError("queue_sources_duplicate");
  }
  return deepFreeze({
    revision: safeInteger(queue.revision),
    rows,
  });
}

function normalizeReview(raw) {
  const review = exactObject(raw, REVIEW_KEYS);
  if (
    review.version !== GENERATION_STRATEGY_QUEUE_VERSION ||
    !Array.isArray(review.rows) ||
    !GENERATION_STRATEGY_QUEUE_SIZES.has(review.row_count) ||
    review.rows.length !== review.row_count
  ) throw new ViewContractError("review_invalid");
  const rows = review.rows.map(normalizeQueueRow);
  const unique = new Set(rows.map((row) => row.source_media_id)).size === rows.length;
  const displayOnly = exactBoolean(review.display_only);
  const confirmation = exactBoolean(review.confirmation);
  const ready = exactBoolean(review.ready);
  const serverPriced = exactBoolean(review.server_priced);
  exactBoolean(review.prior_review_current);
  safeInteger(review.queue_revision);
  const eligibleFlags = displayOnly && !confirmation && ready && serverPriced;
  let totalMinor = null;
  let currency = null;
  if (eligibleFlags) {
    totalMinor = safeInteger(review.total_estimated_cost_minor, 1, 10_000_000);
    if (review.currency !== "USD") throw new ViewContractError("review_currency_invalid");
    currency = "USD";
  } else if (
    review.total_estimated_cost_minor !== null ||
    review.currency !== null
  ) {
    return deepFreeze({ eligible: false, rows, total_minor: null, currency: null });
  }
  const rowPricesReady = rows.every((row) =>
    row.runtime.phase === "preflight_ready" &&
    row.runtime.free_ready &&
    row.runtime.price?.currency === currency
  );
  const rowTotal = rowPricesReady
    ? rows.reduce(
      (sum, row) => sum + row.runtime.price.estimated_cost_minor,
      0,
    )
    : null;
  return deepFreeze({
    eligible: eligibleFlags && unique && rowPricesReady && rowTotal === totalMinor,
    rows,
    total_minor: totalMinor,
    currency,
  });
}

function optionalProjection(raw, normalizer) {
  if (raw === null || raw === undefined) return { value: null, invalid: false };
  try {
    return { value: normalizer(raw), invalid: false };
  } catch {
    return { value: null, invalid: true };
  }
}

function formatDuration(value) {
  if (value === null) return null;
  const canonical = Number.isInteger(value)
    ? String(value)
    : value.toFixed(2).replace(/0+$/u, "").replace(/\.$/u, "");
  return canonical.replace(".", ",");
}

function formatMoney(minor, currency) {
  return `${(minor / 100).toFixed(2).replace(".", ",")} ${currency}`;
}

function durationText(source) {
  if (source.probe_required) {
    return "Нужна бесплатная серверная проверка длительности MP4";
  }
  const duration = formatDuration(source.duration_seconds);
  return duration === null
    ? "Для этой стратегии серверная длительность не требуется"
    : `Проверено сервером: ${duration} с`;
}

function freeReadinessText(source, runtime, queueMatchesSelection, copy) {
  if (source.probe_required) {
    return "Сначала бесплатно проверьте точный MP4";
  }
  if (!queueMatchesSelection) {
    return copy.stale_readiness;
  }
  if (runtime === null) return "Готов к бесплатной подготовке";
  if (runtime.phase === "idle") return "Ожидает выбора параметров";
  if (runtime.phase === "selected") return "Можно бесплатно привязать ассеты";
  if (runtime.phase === "bound") return "Можно выполнить бесплатную проверку";
  if (runtime.phase === "invalid") return "Нужно повторить бесплатную подготовку";
  return "Бесплатная проверка пройдена";
}

function runtimeErrorText(runtime) {
  if (runtime === null) return null;
  if (runtime.phase === "invalid") {
    return "Контекст этого ролика изменился. Повторите бесплатную подготовку только для этой строки.";
  }
  if (["failed", "cancelled"].includes(runtime.job_status)) {
    return "Эта генерация завершилась отдельно; остальные ролики продолжают работу.";
  }
  if (runtime.error_code !== null) {
    return "Для этой строки зафиксирована ошибка. Остальные строки не затронуты.";
  }
  return null;
}

function selectedPhase(source, runtime, queueMatchesSelection) {
  if (source.probe_required) return "probe_required";
  if (!queueMatchesSelection) return "queue_stale";
  return runtime?.phase || "source_ready";
}

function emptyRow(position) {
  return deepFreeze({
    position,
    selected: false,
    source_media_id: null,
    filename: "Ролик не выбран",
    duration_text: "Выберите исходный хит в списке источников",
    probe_required: false,
    phase: "empty",
    phase_text: PHASE_LABELS.empty,
    free_readiness_text: "Ожидает выбора источника",
    price_text: null,
    job_status: null,
    job_status_text: null,
    error_text: null,
    can_toggle: false,
    can_probe: false,
  });
}

function selectedRow(source, runtime, queueMatchesSelection, copy) {
  const phase = selectedPhase(source, runtime, queueMatchesSelection);
  const toggleLocked = runtime !== null && [
    "human_confirmed",
    "start_once",
    "status",
  ].includes(runtime.phase);
  return deepFreeze({
    position: source.position,
    selected: true,
    source_media_id: source.source_media_id,
    filename: source.filename,
    duration_text: durationText(source),
    probe_required: source.probe_required,
    phase,
    phase_text: PHASE_LABELS[phase],
    free_readiness_text: freeReadinessText(
      source,
      runtime,
      queueMatchesSelection,
      copy,
    ),
    price_text: runtime?.price
      ? formatMoney(
        runtime.price.estimated_cost_minor,
        runtime.price.currency,
      )
      : null,
    job_status: runtime?.job_status || null,
    job_status_text: runtime?.job_status
      ? JOB_LABELS[runtime.job_status]
      : null,
    error_text: runtimeErrorText(runtime),
    can_toggle: !toggleLocked,
    can_probe: source.probe_required && !toggleLocked,
  });
}

function reviewMatchesSources(review, source, queue) {
  if (
    !review?.eligible ||
    !source.exact_required_selected ||
    !source.all_selected_ready
  ) return false;
  const sourceIds = source.selected.map((row) => row.source_media_id);
  const reviewIds = review.rows.map((row) => row.source_media_id);
  if (JSON.stringify(sourceIds) !== JSON.stringify(reviewIds)) return false;
  if (queue === null) return true;
  return queue.rows.every((row, index) => {
    const reviewRow = review.rows[index];
    return row.source_media_id === reviewRow.source_media_id &&
      row.runtime.price !== null &&
      reviewRow.runtime.price !== null &&
      row.runtime.price.estimated_cost_minor ===
        reviewRow.runtime.price.estimated_cost_minor &&
      row.runtime.price.currency === reviewRow.runtime.price.currency;
  });
}

export function createGenerationStrategyQueueViewModel(
  sourcePickerProjection,
  queueSafeProjection = null,
  aggregateReview = null,
) {
  let source;
  try {
    source = normalizeSourceProjection(sourcePickerProjection);
  } catch {
    return null;
  }
  // normalizeSourceProjection гарантирует размер из GENERATION_STRATEGY_QUEUE_SIZES.
  const copy = QUEUE_SIZE_COPY[source.required_count];
  const queueResult = optionalProjection(
    queueSafeProjection,
    normalizeQueueProjection,
  );
  const reviewResult = optionalProjection(aggregateReview, normalizeReview);
  const queue = queueResult.value;
  const review = reviewResult.value;
  const queueMatchesSelection = queue !== null &&
    source.exact_required_selected &&
    queue.rows.length === source.selected.length &&
    queue.rows.every((row, index) =>
      row.source_media_id === source.selected[index]?.source_media_id
    );
  const rows = Array.from(
    { length: source.required_count },
    (_, index) => {
      const selected = source.selected[index];
      if (!selected) return emptyRow(index + 1);
      const runtime = queueMatchesSelection ? queue.rows[index].runtime : null;
      return selectedRow(selected, runtime, queueMatchesSelection || queue === null, copy);
    },
  );
  const queueAllowsReview = queueSafeProjection === null ||
    queueSafeProjection === undefined ||
    queueMatchesSelection;
  const reviewVisible = queueAllowsReview && reviewMatchesSources(
    review,
    source,
    queueMatchesSelection ? queue : null,
  );
  const queueRuntimes = queueMatchesSelection
    ? queue.rows.map((row) => row.runtime)
    : [];
  const paidStatePresent = queueRuntimes.some((runtime) => [
    "human_confirmed",
    "start_once",
    "status",
  ].includes(runtime.phase));
  const canPrepareFree = source.exact_required_selected &&
    source.all_selected_ready &&
    !paidStatePresent && (
      queue === null ||
      !queueMatchesSelection ||
      queueRuntimes.some((runtime) => [
        "idle",
        "selected",
        "bound",
        "invalid",
      ].includes(runtime.phase))
    );
  const canReviewExactTen = queueMatchesSelection &&
    queueRuntimes.every((runtime) =>
      runtime.phase === "preflight_ready" && runtime.free_ready
    );
  const paidStartBlocked = queueRuntimes.some((runtime) =>
    runtime.start_reserved || runtime.reconciliation_required
  );
  const paidPhasesSafe = GENERATION_STRATEGY_QUEUE_SIZES.has(queueRuntimes.length) &&
    queueRuntimes.every((runtime) => [
      "human_confirmed",
      "status",
      "invalid",
    ].includes(runtime.phase));
  const canStartSequentially = queueMatchesSelection &&
    reviewVisible &&
    paidPhasesSafe &&
    !paidStartBlocked &&
    queueRuntimes.some((runtime) => runtime.can_start);
  let notice = null;
  if (source.error_code !== null) {
    notice = "Список источников требует внимания. Проверьте выбранные ролики.";
  } else if (queueResult.invalid) {
    notice = "Безопасные данные очереди не прошли проверку. Обновите экран.";
  } else if (queue !== null && !queueMatchesSelection) {
    notice = copy.stale_notice;
  } else if (reviewResult.invalid) {
    notice = "Обзор стоимости устарел или повреждён. Получите новый бесплатный обзор.";
  }
  return deepFreeze({
    version: GENERATION_STRATEGY_QUEUE_VIEW_VERSION,
    strategy_id: source.strategy_id,
    selection_count_text: `${source.selected_count} из ${source.required_count}`,
    selected_count: source.selected_count,
    required_count: source.required_count,
    exact_required_selected: source.exact_required_selected,
    exactly_ten_selected: source.exactly_ten_selected,
    all_selected_ready: source.all_selected_ready,
    queue_matches_selection: queueMatchesSelection,
    rows,
    aggregate: {
      visible: reviewVisible,
      display_only: true,
      confirmation: false,
      total_text: reviewVisible
        ? formatMoney(review.total_minor, review.currency)
        : null,
    },
    controls: {
      can_prepare_free: canPrepareFree,
      can_review_exact_ten: canReviewExactTen,
      can_start_sequentially: canStartSequentially,
    },
    notice,
    scope_copy: {
      sequential: copy.sequential,
      isolation:
        "Ошибка одного ролика не останавливает статусы и результаты остальных.",
      advisory:
        "Советник по нескольким нейросетям остаётся только рекомендацией и ничего не применяет автоматически.",
      untouched:
        "«Задумки» и «ИИ-центр» эта очередь не изменяет.",
    },
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buttonDisabled(enabled) {
  return enabled ? ' aria-disabled="false"' : ' disabled aria-disabled="true"';
}

function rowMarkup(row, requiredCount, copy) {
  const rowId = `generation-strategy-queue-row-${row.position}`;
  const sourceAttribute = row.source_media_id === null
    ? ""
    : ` data-source-media-id="${escapeHtml(row.source_media_id)}"`;
  const price = row.price_text === null
    ? "Цена появится после бесплатной проверки"
    : `Точная цена: ${escapeHtml(row.price_text)}`;
  const job = row.job_status_text === null
    ? "Задача ещё не создана"
    : `Статус задачи: ${escapeHtml(row.job_status_text)}`;
  const error = row.error_text === null
    ? ""
    : `<p class="generation-strategy-queue-view__error" role="alert">${
      escapeHtml(row.error_text)
    }</p>`;
  const actions = row.selected
    ? `<div class="generation-strategy-queue-view__row-actions">
        <button type="button" class="${BUTTON_CLASS}" data-action="toggle-generation-strategy-source" aria-label="Убрать ролик ${row.position} из ${requiredCount}: ${escapeHtml(row.filename)}"${
          sourceAttribute
        }${buttonDisabled(row.can_toggle)}>${copy.remove_button}</button>
        <button type="button" class="${BUTTON_CLASS}" data-action="probe-generation-strategy-media" aria-label="Проверить MP4 для ролика ${row.position} из ${requiredCount}: ${escapeHtml(row.filename)}"${
          sourceAttribute
        }${buttonDisabled(row.can_probe)}>Проверить MP4 бесплатно</button>
      </div>`
    : "";
  return `<li class="generation-strategy-queue-view__row" data-position="${row.position}">
    <article aria-labelledby="${rowId}">
      <p class="generation-strategy-queue-view__position">Ролик ${row.position} из ${requiredCount}</p>
      <h3 id="${rowId}">${escapeHtml(row.filename)}</h3>
      <p>${escapeHtml(row.duration_text)}</p>
      <dl>
        <div><dt>Этап</dt><dd>${escapeHtml(row.phase_text)}</dd></div>
        <div><dt>Бесплатная готовность</dt><dd>${escapeHtml(row.free_readiness_text)}</dd></div>
        <div><dt>Стоимость</dt><dd>${price}</dd></div>
        <div><dt>Результат</dt><dd>${job}</dd></div>
      </dl>
      ${error}${actions}
    </article>
  </li>`;
}

export function renderGenerationStrategyQueueView(
  sourcePickerProjection,
  queueSafeProjection = null,
  aggregateReview = null,
) {
  const view = createGenerationStrategyQueueViewModel(
    sourcePickerProjection,
    queueSafeProjection,
    aggregateReview,
  );
  if (!view) return "";
  const copy = QUEUE_SIZE_COPY[view.required_count];
  const notice = view.notice === null
    ? ""
    : `<p class="generation-strategy-queue-view__notice" role="alert">${
      escapeHtml(view.notice)
    }</p>`;
  const total = view.aggregate.visible
    ? `<strong>${escapeHtml(view.aggregate.total_text)}</strong>`
    : copy.total_pending;
  return `<section class="generation-strategy-queue-view" aria-labelledby="generation-strategy-queue-title">
  <header>
    <p class="generation-strategy-queue-view__eyebrow">${copy.eyebrow}</p>
    <h2 id="generation-strategy-queue-title">${copy.heading}</h2>
    <p role="status" aria-live="polite">Выбрано: ${escapeHtml(view.selection_count_text)}</p>
    ${notice}
  </header>
  <ol class="generation-strategy-queue-view__rows">
    ${view.rows.map((row) => rowMarkup(row, view.required_count, copy)).join("\n    ")}
  </ol>
  <section class="generation-strategy-queue-view__review" aria-labelledby="generation-strategy-queue-review-title">
    <h3 id="generation-strategy-queue-review-title">${copy.review_title}</h3>
    <p>Итоговая серверная стоимость: ${total}.</p>
    <p>Обзор показывает цену и не является подтверждением платного запуска.</p>
  </section>
  <div class="generation-strategy-queue-view__controls" aria-label="Действия с очередью">
    <button type="button" class="${BUTTON_CLASS}" data-action="prepare-generation-strategy-queue-free"${
      buttonDisabled(view.controls.can_prepare_free)
    }>Подготовить бесплатно</button>
    <button type="button" class="${BUTTON_CLASS}" data-action="review-generation-strategy-exact-ten"${
      buttonDisabled(view.controls.can_review_exact_ten)
    }>${copy.review_button}</button>
    <button type="button" class="${BUTTON_CLASS}" data-action="start-generation-strategy-sequentially"${
      buttonDisabled(view.controls.can_start_sequentially)
    }>Запускать последовательно</button>
  </div>
  <aside class="generation-strategy-queue-view__scope" aria-label="Правила запуска">
    <p>${escapeHtml(view.scope_copy.sequential)}</p>
    <p>${escapeHtml(view.scope_copy.isolation)}</p>
    <p>${escapeHtml(view.scope_copy.advisory)}</p>
    <p>${escapeHtml(view.scope_copy.untouched)}</p>
  </aside>
</section>`;
}
