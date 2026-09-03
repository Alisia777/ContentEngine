/*
 * Pure orchestration contract for an exact ten-source generation queue.
 *
 * The queue owns no DOM, network, storage, clock, randomness, provider, model,
 * or recipe authority. Each row delegates its paid-handshake state to the
 * frozen generation-strategy runtime. Request keys are supplied by the caller,
 * kept independent per row, and never included in safe/review projections.
 */

import {
  GENERATION_STRATEGY_RUNTIME_ACTIONS,
  createGenerationStrategyRuntimeState,
  generationStrategyRuntimeSafeProjection,
  invalidateGenerationStrategyRuntimeState,
  reduceGenerationStrategyRuntimeState,
} from "./generation-strategy-runtime.js?v=20260826.rebuild-clean.60";

export const GENERATION_STRATEGY_QUEUE_VERSION = "2026-08-14.v1";
export const GENERATION_STRATEGY_QUEUE_SIZE = 10;
// «Создание» с 26.08 идёт с ОДНИМ референсом, «десятка хитов» осталась для
// массового режима. Жёсткий размер 10 делал очередь одного ролика
// непостроимой (боевой прогон 29.08): контракт принимает оба размера, а
// согласованность внутри одного значения по-прежнему обязательна.
export const GENERATION_STRATEGY_QUEUE_SIZES = Object.freeze(new Set([1, 10]));
export const GENERATION_STRATEGY_QUEUE_FREE_MAX_CONCURRENCY = 3;
export const GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY = 1;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/u;
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const REQUEST_KEY_NAMES = Object.freeze([
  "probe",
  "bind",
  "preflight",
  "start",
]);
const QUEUE_KEYS = Object.freeze([
  "version",
  "revision",
  "source_order",
  "rows",
]);
const ROW_KEYS = Object.freeze([
  "source_media_id",
  "idempotency_keys",
  "runtime_state",
]);
class QueueContractError extends Error {
  constructor(code, field) {
    super(code);
    this.name = "QueueContractError";
    this.code = code;
    this.field = field;
  }
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactObject(value, keys, field) {
  if (!isPlainObject(value)) {
    throw new QueueContractError("object_required", field);
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length ||
    actual.some((key, index) => key !== expected[index])
  ) {
    throw new QueueContractError("object_keys_mismatch", field);
  }
  return value;
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  if (value instanceof Map) {
    for (const child of value.values()) deepFreeze(child);
  } else {
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return Object.freeze(value);
}

function immutableMap(entries) {
  const map = new Map(entries);
  const rejectMutation = () => {
    throw new TypeError("generation_strategy_queue_map_is_read_only");
  };
  Object.defineProperties(map, {
    set: { value: rejectMutation, enumerable: false },
    delete: { value: rejectMutation, enumerable: false },
    clear: { value: rejectMutation, enumerable: false },
  });
  for (const value of map.values()) deepFreeze(value);
  return Object.freeze(map);
}

function exactUuid(value, field) {
  if (
    typeof value !== "string" ||
    !UUID_PATTERN.test(value) ||
    value === ZERO_UUID
  ) {
    throw new QueueContractError("uuid_invalid", field);
  }
  return value;
}

function exactIdempotencyKey(value, field) {
  if (
    typeof value !== "string" ||
    value.trim() !== value ||
    !IDEMPOTENCY_PATTERN.test(value)
  ) {
    throw new QueueContractError("idempotency_key_invalid", field);
  }
  return value;
}

function normalizeRequestKeys(value, field) {
  const source = exactObject(value, REQUEST_KEY_NAMES, field);
  return deepFreeze(Object.fromEntries(REQUEST_KEY_NAMES.map((name) => [
    name,
    exactIdempotencyKey(source[name], `${field}.${name}`),
  ])));
}

function queueSuccess(queue) {
  return Object.freeze({ ok: true, queue, error: null });
}

function valueSuccess(key, value) {
  return Object.freeze({ ok: true, [key]: value, error: null });
}

function queueFailure(error, fallbackCode, fallbackField) {
  const known = error instanceof QueueContractError;
  return deepFreeze({
    ok: false,
    queue: null,
    error: {
      code: known ? error.code : fallbackCode,
      field: known ? error.field : fallbackField,
    },
  });
}

function valueFailure(key, error, fallbackCode, fallbackField) {
  const known = error instanceof QueueContractError;
  return deepFreeze({
    ok: false,
    [key]: null,
    error: {
      code: known ? error.code : fallbackCode,
      field: known ? error.field : fallbackField,
    },
  });
}

function runtimeProjectionOrThrow(state, field) {
  const projection = generationStrategyRuntimeSafeProjection(state);
  if (!projection) {
    throw new QueueContractError("runtime_state_invalid", field);
  }
  return projection;
}

function authorityIdentity(state) {
  return {
    fingerprint: state.fingerprint,
    binding_id: state.bind?.binding?.id || null,
    binding_hash: state.bind?.binding?.binding_hash || null,
    receipt_id: state.preflight?.receipt?.id || null,
    receipt_hash: state.preflight?.receipt?.receipt_hash || null,
    start_context_fingerprint: state.start_context_fingerprint,
  };
}

function authorityCollision(first, second) {
  const left = authorityIdentity(first);
  const right = authorityIdentity(second);
  return Object.keys(left).some((key) =>
    left[key] !== null && left[key] === right[key]
  );
}

function validQueue(value) {
  if (!isPlainObject(value)) return false;
  const actualKeys = Object.keys(value).sort();
  const expectedKeys = [...QUEUE_KEYS].sort();
  if (
    actualKeys.length !== expectedKeys.length ||
    actualKeys.some((key, index) => key !== expectedKeys[index]) ||
    value.version !== GENERATION_STRATEGY_QUEUE_VERSION ||
    !Number.isSafeInteger(value.revision) ||
    value.revision < 0 ||
    !Array.isArray(value.source_order) ||
    !GENERATION_STRATEGY_QUEUE_SIZES.has(value.source_order.length) ||
    new Set(value.source_order).size !== value.source_order.length ||
    !(value.rows instanceof Map) ||
    value.rows.size !== value.source_order.length ||
    !Object.isFrozen(value) ||
    !Object.isFrozen(value.source_order) ||
    !Object.isFrozen(value.rows)
  ) return false;

  const allRequestKeys = new Set();
  const runtimeStates = new Set();
  const authorityStates = [];
  const mapIds = [...value.rows.keys()];
  for (let index = 0; index < value.source_order.length; index += 1) {
    const sourceMediaId = value.source_order[index];
    if (
      !UUID_PATTERN.test(sourceMediaId) ||
      sourceMediaId === ZERO_UUID ||
      mapIds[index] !== sourceMediaId
    ) return false;
    const row = value.rows.get(sourceMediaId);
    if (!isPlainObject(row)) return false;
    const rowKeys = Object.keys(row).sort();
    const expectedRowKeys = [...ROW_KEYS].sort();
    if (
      rowKeys.length !== expectedRowKeys.length ||
      rowKeys.some((key, keyIndex) => key !== expectedRowKeys[keyIndex]) ||
      row.source_media_id !== sourceMediaId ||
      !Object.isFrozen(row) ||
      runtimeStates.has(row.runtime_state) ||
      !generationStrategyRuntimeSafeProjection(row.runtime_state)
    ) return false;
    runtimeStates.add(row.runtime_state);
    authorityStates.push(row.runtime_state);
    if (!isPlainObject(row.idempotency_keys) || !Object.isFrozen(row.idempotency_keys)) {
      return false;
    }
    const requestKeyNames = Object.keys(row.idempotency_keys).sort();
    const expectedRequestKeyNames = [...REQUEST_KEY_NAMES].sort();
    if (
      requestKeyNames.length !== expectedRequestKeyNames.length ||
      requestKeyNames.some((key, keyIndex) =>
        key !== expectedRequestKeyNames[keyIndex]
      )
    ) return false;
    for (const name of REQUEST_KEY_NAMES) {
      const requestKey = row.idempotency_keys[name];
      if (
        typeof requestKey !== "string" ||
        !IDEMPOTENCY_PATTERN.test(requestKey) ||
        allRequestKeys.has(requestKey)
      ) return false;
      allRequestKeys.add(requestKey);
    }
  }
  for (let index = 0; index < authorityStates.length; index += 1) {
    for (let other = index + 1; other < authorityStates.length; other += 1) {
      if (authorityCollision(authorityStates[index], authorityStates[other])) {
        return false;
      }
    }
  }
  return true;
}

function buildQueue(revision, sourceMediaIds, rows) {
  return Object.freeze({
    version: GENERATION_STRATEGY_QUEUE_VERSION,
    revision,
    source_order: deepFreeze([...sourceMediaIds]),
    rows: immutableMap(rows),
  });
}

export function createGenerationStrategyQueue(entries) {
  try {
    if (
      !Array.isArray(entries) ||
      !GENERATION_STRATEGY_QUEUE_SIZES.has(entries.length)
    ) {
      throw new QueueContractError("queue_size_invalid", "entries");
    }
    const sourceMediaIds = [];
    const seenMediaIds = new Set();
    const seenRequestKeys = new Set();
    const rows = [];
    entries.forEach((entry, index) => {
      const field = `entries[${index}]`;
      const source = exactObject(
        entry,
        ["source_media_id", "idempotency_keys"],
        field,
      );
      const sourceMediaId = exactUuid(
        source.source_media_id,
        `${field}.source_media_id`,
      );
      if (seenMediaIds.has(sourceMediaId)) {
        throw new QueueContractError(
          "source_media_id_duplicate",
          `${field}.source_media_id`,
        );
      }
      seenMediaIds.add(sourceMediaId);
      const requestKeys = normalizeRequestKeys(
        source.idempotency_keys,
        `${field}.idempotency_keys`,
      );
      for (const name of REQUEST_KEY_NAMES) {
        const requestKey = requestKeys[name];
        if (seenRequestKeys.has(requestKey)) {
          throw new QueueContractError(
            "idempotency_key_duplicate",
            `${field}.idempotency_keys.${name}`,
          );
        }
        seenRequestKeys.add(requestKey);
      }
      const runtimeState = createGenerationStrategyRuntimeState();
      sourceMediaIds.push(sourceMediaId);
      rows.push([sourceMediaId, deepFreeze({
        source_media_id: sourceMediaId,
        idempotency_keys: requestKeys,
        runtime_state: runtimeState,
      })]);
    });
    const queue = buildQueue(0, sourceMediaIds, rows);
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    return queueSuccess(queue);
  } catch (error) {
    return queueFailure(error, "queue_create_invalid", "entries");
  }
}

function actionMatchesSource(action, sourceMediaId) {
  if (
    !isPlainObject(action) ||
    ![
      GENERATION_STRATEGY_RUNTIME_ACTIONS.select,
      GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
    ].includes(action.type)
  ) return true;
  const assets = action.context?.generation_strategy?.assets;
  if (!Array.isArray(assets)) return false;
  const sources = assets.filter((asset) =>
    isPlainObject(asset) && asset.role === "source_video"
  );
  return sources.length === 1 && sources[0].media_id === sourceMediaId;
}

function withUpdatedRow(queue, sourceMediaId, runtimeState) {
  const currentRow = queue.rows.get(sourceMediaId);
  const nextRows = [...queue.rows.entries()].map(([mediaId, row]) => [
    mediaId,
    mediaId === sourceMediaId
      ? deepFreeze({ ...currentRow, runtime_state: runtimeState })
      : row,
  ]);
  return buildQueue(
    queue.revision + 1,
    queue.source_order,
    nextRows,
  );
}

function invalidateCandidate(state, reason) {
  return invalidateGenerationStrategyRuntimeState(state, reason);
}

export function updateGenerationStrategyQueueRow(queue, sourceMediaId, action) {
  try {
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    const mediaId = exactUuid(sourceMediaId, "source_media_id");
    const row = queue.rows.get(mediaId);
    if (!row) {
      throw new QueueContractError("queue_row_unknown", "source_media_id");
    }
    let nextState;
    if (!actionMatchesSource(action, mediaId)) {
      nextState = invalidateCandidate(
        row.runtime_state,
        "queue_source_context_changed",
      );
    } else if (
      isPlainObject(action) &&
      action.type === GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested &&
      action.idempotency_key !== row.idempotency_keys.start
    ) {
      nextState = invalidateCandidate(
        row.runtime_state,
        "queue_start_key_mismatch",
      );
    } else {
      nextState = reduceGenerationStrategyRuntimeState(row.runtime_state, action);
    }
    runtimeProjectionOrThrow(nextState, "action");
    if ([...queue.rows.entries()].some(([otherMediaId, otherRow]) =>
      otherMediaId !== mediaId &&
      authorityCollision(nextState, otherRow.runtime_state)
    )) {
      nextState = invalidateCandidate(nextState, "queue_authority_collision");
    }
    const nextQueue = withUpdatedRow(queue, mediaId, nextState);
    if (!validQueue(nextQueue)) {
      throw new QueueContractError("queue_update_invalid", "queue");
    }
    return queueSuccess(nextQueue);
  } catch (error) {
    return queueFailure(error, "queue_update_invalid", "queue");
  }
}

export function invalidateGenerationStrategyQueueRow(
  queue,
  sourceMediaId,
  reason = "generation_strategy_queue_row_changed",
) {
  try {
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    const mediaId = exactUuid(sourceMediaId, "source_media_id");
    const row = queue.rows.get(mediaId);
    if (!row) {
      throw new QueueContractError("queue_row_unknown", "source_media_id");
    }
    if (typeof reason !== "string" || !/^[a-z0-9][a-z0-9_.-]{0,127}$/u.test(reason)) {
      throw new QueueContractError("invalidation_reason_invalid", "reason");
    }
    const nextQueue = withUpdatedRow(
      queue,
      mediaId,
      invalidateCandidate(row.runtime_state, reason),
    );
    if (!validQueue(nextQueue)) {
      throw new QueueContractError("queue_invalidation_invalid", "queue");
    }
    return queueSuccess(nextQueue);
  } catch (error) {
    return queueFailure(error, "queue_invalidation_invalid", "queue");
  }
}

function sanitizedRuntimeProjection(state) {
  const projection = runtimeProjectionOrThrow(state, "runtime_state");
  const price = projection.price === null ? null : {
    price_hash: projection.price.price_hash,
    strategy_id: projection.price.strategy_id,
    recipe: projection.price.recipe,
    duration_seconds: projection.price.duration_seconds,
    resolution: projection.price.resolution,
    ratio: projection.price.ratio,
    audio: projection.price.audio,
    estimated_credits: projection.price.estimated_credits,
    estimated_cost_minor: projection.price.estimated_cost_minor,
    estimated_cost_usd: projection.price.estimated_cost_usd,
    currency: projection.price.currency,
  };
  return deepFreeze({
    version: projection.version,
    phase: projection.phase,
    fingerprint: projection.fingerprint,
    identity: projection.identity,
    binding: projection.binding,
    price,
    readiness: projection.readiness,
    campaign_id: projection.campaign_id,
    start_context_fingerprint: projection.start_context_fingerprint,
    job: projection.job,
    reconciliation: projection.reconciliation,
    output: projection.output,
    error: projection.error,
    can_preflight: projection.can_preflight,
    can_confirm: projection.can_confirm,
    can_start: projection.can_start,
    start_reserved: projection.start_reserved,
    can_poll: projection.can_poll,
  });
}

export function generationStrategyQueueSafeProjection(queue) {
  if (!validQueue(queue)) return null;
  return deepFreeze({
    version: GENERATION_STRATEGY_QUEUE_VERSION,
    revision: queue.revision,
    row_count: queue.source_order.length,
    rows: queue.source_order.map((sourceMediaId) => ({
      source_media_id: sourceMediaId,
      runtime: sanitizedRuntimeProjection(
        queue.rows.get(sourceMediaId).runtime_state,
      ),
    })),
  });
}

function reviewMatches(priorReview, currentProjection) {
  if (priorReview === null || !isPlainObject(priorReview)) return false;
  if (
    priorReview.version !== GENERATION_STRATEGY_QUEUE_VERSION ||
    priorReview.display_only !== true ||
    priorReview.confirmation !== false ||
    priorReview.queue_revision !== currentProjection.revision ||
    !Array.isArray(priorReview.rows) ||
    priorReview.rows.length !== currentProjection.rows.length
  ) return false;
  return priorReview.rows.every((priorRow, index) => {
    const currentRow = currentProjection.rows[index];
    return isPlainObject(priorRow) &&
      priorRow.source_media_id === currentRow.source_media_id &&
      priorRow.runtime?.fingerprint === currentRow.runtime.fingerprint &&
      priorRow.runtime?.binding?.id === currentRow.runtime.binding?.id &&
      priorRow.runtime?.price?.price_hash === currentRow.runtime.price?.price_hash &&
      priorRow.runtime?.readiness?.receipt_id ===
        currentRow.runtime.readiness?.receipt_id;
  });
}

export function generationStrategyQueueAggregateReview(queue, priorReview = null) {
  try {
    const projection = generationStrategyQueueSafeProjection(queue);
    if (!projection) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    const ready = projection.rows.every(({ runtime }) =>
      runtime.phase === "preflight_ready" &&
      runtime.fingerprint !== null &&
      runtime.binding !== null &&
      runtime.price !== null &&
      Number.isSafeInteger(runtime.price.estimated_cost_minor) &&
      runtime.price.estimated_cost_minor > 0 &&
      runtime.readiness?.ready === true &&
      runtime.readiness.launch_enabled === true
    );
    const currencies = new Set(projection.rows.map(({ runtime }) =>
      runtime.price?.currency || null
    ));
    const oneCurrency = ready && currencies.size === 1 && !currencies.has(null);
    const total = oneCurrency
      ? projection.rows.reduce(
        (sum, { runtime }) => sum + runtime.price.estimated_cost_minor,
        0,
      )
      : null;
    if (total !== null && !Number.isSafeInteger(total)) {
      throw new QueueContractError("queue_total_invalid", "review.total");
    }
    const review = deepFreeze({
      version: GENERATION_STRATEGY_QUEUE_VERSION,
      display_only: true,
      confirmation: false,
      queue_revision: projection.revision,
      prior_review_current: ready && reviewMatches(priorReview, projection),
      ready: ready && oneCurrency,
      server_priced: ready && oneCurrency,
      row_count: projection.rows.length,
      currency: oneCurrency ? [...currencies][0] : null,
      total_estimated_cost_minor: oneCurrency ? total : null,
      rows: projection.rows,
    });
    return valueSuccess("review", review);
  } catch (error) {
    return valueFailure(
      "review",
      error,
      "queue_review_invalid",
      "queue",
    );
  }
}

function normalizeProbeIds(queue, sourceMediaIds) {
  if (!Array.isArray(sourceMediaIds)) {
    throw new QueueContractError("probe_ids_invalid", "probe_sources");
  }
  const seen = new Set();
  return new Set(sourceMediaIds.map((sourceMediaId, index) => {
    const mediaId = exactUuid(
      sourceMediaId,
      `probe_sources[${index}]`,
    );
    if (!queue.rows.has(mediaId)) {
      throw new QueueContractError(
        "queue_row_unknown",
        `probe_sources[${index}]`,
      );
    }
    if (seen.has(mediaId)) {
      throw new QueueContractError(
        "probe_source_media_id_duplicate",
        `probe_sources[${index}]`,
      );
    }
    seen.add(mediaId);
    return mediaId;
  }));
}

export function planGenerationStrategyQueueFreeWork(
  queue,
  probeSourceMediaIds = [],
  maxConcurrency = GENERATION_STRATEGY_QUEUE_FREE_MAX_CONCURRENCY,
) {
  try {
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    if (
      !Number.isSafeInteger(maxConcurrency) ||
      maxConcurrency < 1 ||
      maxConcurrency > GENERATION_STRATEGY_QUEUE_FREE_MAX_CONCURRENCY
    ) {
      throw new QueueContractError(
        "free_concurrency_invalid",
        "max_concurrency",
      );
    }
    const probeIds = normalizeProbeIds(queue, probeSourceMediaIds);
    const items = [];
    for (const sourceMediaId of queue.source_order) {
      if (items.length >= maxConcurrency) break;
      const row = queue.rows.get(sourceMediaId);
      const state = row.runtime_state;
      let work = null;
      if (state.phase === "idle" && probeIds.has(sourceMediaId)) {
        work = "probe";
      } else if (state.phase === "selected") {
        work = "bind";
      } else if (state.phase === "bound") {
        work = "preflight";
      }
      if (work === null) continue;
      items.push(deepFreeze({
        source_media_id: sourceMediaId,
        work,
        runtime_fingerprint: state.fingerprint,
        idempotency_key: row.idempotency_keys[work],
      }));
    }
    const plan = deepFreeze({
      version: GENERATION_STRATEGY_QUEUE_VERSION,
      max_concurrency: maxConcurrency,
      paid_start_allowed: false,
      items,
    });
    return valueSuccess("plan", plan);
  } catch (error) {
    return valueFailure(
      "plan",
      error,
      "queue_free_plan_invalid",
      "queue",
    );
  }
}

function sequentialStartPlan(queue) {
  const inFlight = queue.source_order.find((sourceMediaId) =>
    queue.rows.get(sourceMediaId).runtime_state.phase === "start_once"
  );
  if (inFlight) {
    return deepFreeze({
      version: GENERATION_STRATEGY_QUEUE_VERSION,
      max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
      state: "blocked",
      blocker: "start_once_in_flight",
      blocking_source_media_id: inFlight,
      next: null,
    });
  }
  const reconciliationBlocked = queue.source_order.find((sourceMediaId) => {
    const status = queue.rows.get(sourceMediaId).runtime_state.status;
    // Ambiguous dispatch keeps the queue frozen only while the incident is
    // unresolved: a reconciliation record with required === false is the
    // owner/admin verdict that settles the sole paid POST for this row.
    return status?.reconciliation?.required === true ||
      (status?.dispatch?.outcome === "ambiguous" &&
        status?.reconciliation?.required !== false);
  });
  if (reconciliationBlocked) {
    return deepFreeze({
      version: GENERATION_STRATEGY_QUEUE_VERSION,
      max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
      state: "blocked",
      blocker: "reconciliation_required",
      blocking_source_media_id: reconciliationBlocked,
      next: null,
    });
  }
  for (const sourceMediaId of queue.source_order) {
    const row = queue.rows.get(sourceMediaId);
    const state = row.runtime_state;
    if (state.phase === "invalid") continue;
    if (state.phase === "status") {
      continue;
    }
    if (state.phase === "human_confirmed") {
      return deepFreeze({
        version: GENERATION_STRATEGY_QUEUE_VERSION,
        max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
        state: "ready",
        blocker: null,
        blocking_source_media_id: null,
        next: {
          source_media_id: sourceMediaId,
          runtime_fingerprint: state.fingerprint,
          start_context_fingerprint: state.start_context_fingerprint,
          campaign_id: state.campaign_id,
          idempotency_key: row.idempotency_keys.start,
        },
      });
    }
    return deepFreeze({
      version: GENERATION_STRATEGY_QUEUE_VERSION,
      max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
      state: "blocked",
      blocker: "row_not_human_confirmed",
      blocking_source_media_id: sourceMediaId,
      next: null,
    });
  }
  return deepFreeze({
    version: GENERATION_STRATEGY_QUEUE_VERSION,
    max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
    state: "complete",
    blocker: null,
    blocking_source_media_id: null,
    next: null,
  });
}

export function planGenerationStrategyQueueSequentialStarts(queue) {
  try {
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    return valueSuccess("plan", sequentialStartPlan(queue));
  } catch (error) {
    return valueFailure(
      "plan",
      error,
      "queue_start_plan_invalid",
      "queue",
    );
  }
}

export function advanceGenerationStrategyQueueSequentialStarts(queue, priorPlan) {
  try {
    if (!validQueue(queue)) {
      throw new QueueContractError("queue_invalid", "queue");
    }
    if (!isPlainObject(priorPlan) || priorPlan.version !== GENERATION_STRATEGY_QUEUE_VERSION) {
      throw new QueueContractError("prior_plan_invalid", "prior_plan");
    }
    if (priorPlan.next !== null) {
      const sourceMediaId = exactUuid(
        priorPlan.next?.source_media_id,
        "prior_plan.next.source_media_id",
      );
      const row = queue.rows.get(sourceMediaId);
      if (!row) {
        throw new QueueContractError(
          "prior_plan_row_unknown",
          "prior_plan.next.source_media_id",
        );
      }
      if (row.runtime_state.phase === "human_confirmed") {
        const blocked = deepFreeze({
          version: GENERATION_STRATEGY_QUEUE_VERSION,
          max_concurrency: GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
          state: "blocked",
          blocker: "previous_start_not_reserved",
          blocking_source_media_id: sourceMediaId,
          next: null,
        });
        return valueSuccess("plan", blocked);
      }
    }
    return valueSuccess("plan", sequentialStartPlan(queue));
  } catch (error) {
    return valueFailure(
      "plan",
      error,
      "queue_start_advance_invalid",
      "queue",
    );
  }
}
