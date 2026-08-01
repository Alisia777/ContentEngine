/*
 * Deterministic ContentEngine mini-AI control plane.
 *
 * This module has no network, storage or provider side effects. It plans one
 * bounded experiment and evaluates structured outcomes. Raw URLs, captions,
 * free model prose and product claims are deliberately absent.
 */

export const MINI_AI_RULES_VERSION = "mini-ai-rulebook-v1";

export const MINI_AI_RULES = Object.freeze({
  minimumBatchSize: 4,
  maximumBatchSize: 12,
  maximumArms: 3,
  minimumControlShare: 0.20,
  minimumObservationsPerArm: 3,
  minimumTotalObservations: 6,
  minimumRelativeUplift: 0.15,
  minimumOrdersPerDayGap: 0.25,
  minimumSalesPerDayGapMinor: 500,
  minimumConversionGap: 0.03,
  minimumQaGap: 0.10,
  minimumCostPerOrderImprovement: 0.15,
  minimumQaRate: 0.70,
  maximumFailureRate: 0.30,
  winnerAllocation: 0.70,
  controlAllocation: 0.30,
  pauseOnFirstProductMismatch: true,
  viewsCanSelectWinner: false,
  crossCategoryTransferAllowed: false,
  humanApprovalRequiredForScale: true,
});

export const MINI_AI_RULEBOOK_RU = Object.freeze([
  "Один цикл — один вопрос: меняется только один главный фактор.",
  "SKU, категория, площадка, исходники, свойства и claims не меняются между вариантами.",
  "Новая категория не наследует winner чужой категории.",
  "Контроль сохраняется даже после появления winner.",
  "Восемь секунд — один arm, а не универсальный ответ.",
  "Winner выбирают заказы, продажи, конверсия, стоимость заказа и QA — не просмотры.",
  "Нет зрелых данных — нет вывода.",
  "Подмена товара или критический QA-блокер ставит очередь на паузу.",
  "Один пакет — не больше 12 последовательных запусков.",
  "Масштабирование требует подтверждения человека.",
]);

const MODEL_SPECS = Object.freeze({
  real_gen4: Object.freeze({
    providerModel: "gen4_turbo",
    allowedDurations: Object.freeze([2, 5, 8, 10]),
    coldStartDurations: Object.freeze([5, 8]),
    costMinorPerSecond: 5,
  }),
  real_seedance: Object.freeze({
    providerModel: "seedance2_fast",
    allowedDurations: Object.freeze([4, 8, 12, 15]),
    coldStartDurations: Object.freeze([8, 12]),
    costMinorPerSecond: 29,
  }),
});

const ANGLES = Object.freeze({
  demonstration: Object.freeze({
    label: "Контроль · понятная демонстрация",
    instruction: "С первого кадра покажи точный товар и одно понятное действие. Не добавляй драматизацию, неподтверждённые свойства или чужие бренды.",
  }),
  product_focus: Object.freeze({
    label: "Товар в центре",
    instruction: "С первого кадра точный товар занимает главный план. Покажи форму, упаковку и одну проверяемую деталь без лишнего сюжета.",
  }),
  problem_first: Object.freeze({
    label: "Проблема в первом кадре",
    instruction: "Начни с одной узнаваемой бытовой проблемы без преувеличения, затем покажи точный товар как способ действия, а не как обещание результата.",
  }),
  result_first: Object.freeze({
    label: "Проверяемый результат первым",
    instruction: "Начни с наблюдаемого и проверяемого результата использования, затем покажи точный товар и действие, которое к нему привело.",
  }),
  trust_builder: Object.freeze({
    label: "Доверительная подача",
    instruction: "Используй спокойную естественную подачу: точный товар, реальный масштаб, один честный аргумент и отсутствие агрессивных обещаний.",
  }),
});

const PROOF_TYPES = Object.freeze({
  product_detail: Object.freeze({
    label: "Контроль · деталь товара",
    instruction: "Доказательство: крупно покажи одну подтверждённую деталь товара или упаковки.",
  }),
  usage_demo: Object.freeze({
    label: "Демонстрация использования",
    instruction: "Доказательство: покажи одно реальное действие с товаром без обещания эффекта.",
  }),
  feature_closeup: Object.freeze({
    label: "Подтверждённая функция крупно",
    instruction: "Доказательство: покажи одну подтверждённую функцию крупным планом и верни товар целиком в кадр.",
  }),
});

const CTA_STYLES = Object.freeze({
  soft_action: Object.freeze({
    label: "Контроль · мягкий CTA",
    instruction: "CTA: предложи спокойно посмотреть товар или сохранить ролик без давления.",
  }),
  direct_action: Object.freeze({
    label: "Прямой CTA",
    instruction: "CTA: один прямой призыв перейти к товару без срочности и ложного дефицита.",
  }),
  no_cta: Object.freeze({
    label: "Без CTA",
    instruction: "CTA отсутствует: ролик заканчивается товаром и проверяемым действием.",
  }),
});

const FUNNEL_BLOCKS = Object.freeze({
  supply: "Сначала восстановите наличие и поставку.",
  expectation: "Сначала устраните разрыв между обещанием и реальным товаром.",
  advertising: "Сначала исправьте рекламу и распределение трафика.",
  measurement: "Сначала соберите измеримый базовый контроль.",
});

function clean(value, limit = 160) {
  return String(value || "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function stableHash(value) {
  const text = JSON.stringify(value, Object.keys(value).sort());
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function modelSpec(mode) {
  return MODEL_SPECS[String(mode || "")] || null;
}

function requestedCostMinor(mode, durationSeconds) {
  const spec = modelSpec(mode);
  if (!spec || !spec.allowedDurations.includes(Number(durationSeconds))) return null;
  return Number(durationSeconds) * spec.costMinorPerSecond;
}

function allocateCounts(batchSize, allocations) {
  const raw = allocations.map((value) => batchSize * value);
  const counts = raw.map((value) => Math.max(1, Math.floor(value)));
  while (counts.reduce((sum, value) => sum + value, 0) > batchSize) {
    const candidates = counts
      .map((value, index) => ({ value, index }))
      .filter((item) => item.value > 1);
    if (!candidates.length) throw new Error("batch_too_small_for_arms");
    candidates.sort((left, right) => (raw[left.index] - counts[left.index]) - (raw[right.index] - counts[right.index]));
    counts[candidates[0].index] -= 1;
  }
  while (counts.reduce((sum, value) => sum + value, 0) < batchSize) {
    const index = raw
      .map((value, position) => ({ position, remainder: value - counts[position] }))
      .sort((left, right) => right.remainder - left.remainder)[0].position;
    counts[index] += 1;
  }
  return counts;
}

function resolveDimension(context) {
  if (["creative_angle", "duration", "proof_type", "cta_style"].includes(context.requestedDimension)) {
    return context.requestedDimension;
  }
  if (context.categoryIsNew || !context.approvedWinnerAngle) return "creative_angle";
  if (!Number.isInteger(context.approvedWinnerDuration)) return "duration";
  return "proof_type";
}

function angleValues(context) {
  const winner = context.categoryIsNew ? "" : clean(context.approvedWinnerAngle, 80);
  if (winner && winner !== "demonstration" && ANGLES[winner]) {
    const challenger = ["problem_first", "result_first", "product_focus", "trust_builder"]
      .find((value) => ![winner, "demonstration"].includes(value));
    return [
      { value: winner, control: false, allocation: 0.50 },
      { value: "demonstration", control: true, allocation: 0.25 },
      { value: challenger, control: false, allocation: 0.25 },
    ];
  }
  return [
    { value: "demonstration", control: true, allocation: 0.34 },
    { value: "problem_first", control: false, allocation: 0.33 },
    { value: "result_first", control: false, allocation: 0.33 },
  ];
}

function durationValues(context, spec) {
  const policy = context.durationPolicy;
  if (
    policy
    && policy.source === "creator_generation_experiment_policy"
    && /^[0-9a-f]{64}$/u.test(String(policy.policyHash || ""))
    && Array.isArray(policy.arms)
  ) {
    const arms = policy.arms
      .map((arm) => ({
        value: Number(arm?.seconds),
        control: arm?.control === true,
        allocation: Number(arm?.allocation),
      }))
      .filter((arm) =>
        spec.allowedDurations.includes(arm.value)
        && Number.isFinite(arm.allocation)
        && arm.allocation > 0
        && arm.allocation <= 1
      );
    if (arms.length >= 2 && Math.abs(arms.reduce((sum, arm) => sum + arm.allocation, 0) - 1) < 0.001) {
      return arms.slice(0, 3);
    }
  }
  return spec.coldStartDurations.map((seconds, index) => ({
    value: seconds,
    control: index === 0,
    allocation: 1 / spec.coldStartDurations.length,
  }));
}

function planBlock(context, code, message) {
  return Object.freeze({
    version: "mini-ai-plan.v1",
    planId: `blocked-${stableHash({ context, code })}`,
    executable: false,
    dimension: "auto",
    batchSize: 0,
    estimatedCostMinor: 0,
    arms: Object.freeze([]),
    blockers: Object.freeze([message]),
    reasonCodes: Object.freeze([code]),
    context: Object.freeze({ ...context }),
  });
}

function armFromValue(context, dimension, item, count, batchSize, ordinal) {
  const spec = modelSpec(context.mode);
  let durationSeconds = Number(context.approvedWinnerDuration);
  if (!spec.allowedDurations.includes(durationSeconds)) durationSeconds = spec.coldStartDurations[0];
  let creativeAngle = context.categoryIsNew ? "demonstration" : clean(context.approvedWinnerAngle, 80) || "demonstration";
  let hookType = creativeAngle;
  let proofType = "product_detail";
  let ctaStyle = "soft_action";
  let definition;
  if (dimension === "creative_angle") {
    creativeAngle = item.value;
    hookType = item.value;
    definition = ANGLES[item.value] || ANGLES.demonstration;
  } else if (dimension === "duration") {
    durationSeconds = Number(item.value);
    definition = {
      label: `${durationSeconds} секунд`,
      instruction: `Длительность теста: ${durationSeconds} секунд. Сохрани тот же сценарный угол, товар, доказательство и CTA; не добавляй новые сцены только ради времени.`,
    };
  } else if (dimension === "proof_type") {
    proofType = item.value;
    definition = PROOF_TYPES[item.value];
  } else {
    ctaStyle = item.value;
    definition = CTA_STYLES[item.value];
  }
  return Object.freeze({
    armId: `arm-${stableHash({ sku: context.sku, category: context.learningCategoryKey, dimension, value: item.value, ordinal })}`,
    label: definition.label,
    control: item.control === true,
    allocation: count / batchSize,
    plannedCount: count,
    durationSeconds,
    creativeAngle,
    hookType,
    proofType,
    ctaStyle,
    instruction: definition.instruction,
  });
}

export function normalizeMiniAiContext(value = {}) {
  const mode = clean(value.mode, 40);
  const spec = modelSpec(mode);
  const context = {
    organizationKey: clean(value.organizationKey, 160),
    learningCategoryKey: clean(value.learningCategoryKey, 120),
    sku: clean(value.sku, 120),
    platform: clean(value.platform, 80).toLowerCase(),
    mode,
    providerModel: spec?.providerModel || "",
    objective: ["orders", "sales", "conversion", "qa_acceptance", "cost_per_order"].includes(value.objective)
      ? value.objective
      : "orders",
    riskPreset: ["conservative", "balanced", "exploratory"].includes(value.riskPreset)
      ? value.riskPreset
      : "balanced",
    requestedDimension: ["auto", "creative_angle", "duration", "proof_type", "cta_style"].includes(value.requestedDimension)
      ? value.requestedDimension
      : "auto",
    requestedBatchSize: Number(value.requestedBatchSize),
    unitCostMinor: Number(value.unitCostMinor),
    maxBudgetMinor: Number(value.maxBudgetMinor),
    funnelDecision: clean(value.funnelDecision, 40) || "observe",
    categoryIsNew: value.categoryIsNew === true,
    approvedWinnerAngle: clean(value.approvedWinnerAngle, 80),
    approvedWinnerDuration: Number.isInteger(Number(value.approvedWinnerDuration))
      ? Number(value.approvedWinnerDuration)
      : null,
    durationPolicy: value.durationPolicy && typeof value.durationPolicy === "object"
      ? value.durationPolicy
      : null,
  };
  return Object.freeze(context);
}

export function buildMiniAiPlan(rawContext) {
  const context = normalizeMiniAiContext(rawContext);
  const spec = modelSpec(context.mode);
  if (!spec) return planBlock(context, "video_mode_required", "Выберите Gen‑4 Turbo или Seedance 2 Fast.");
  if (!context.learningCategoryKey || !context.sku || !context.platform) {
    return planBlock(context, "exact_scope_required", "Выберите точную категорию, SKU и площадку.");
  }
  if (FUNNEL_BLOCKS[context.funnelDecision]) {
    return planBlock(context, `funnel_${context.funnelDecision}`, FUNNEL_BLOCKS[context.funnelDecision]);
  }
  const batchSize = Math.min(MINI_AI_RULES.maximumBatchSize, Math.max(0, Math.floor(context.requestedBatchSize || 0)));
  const dimension = resolveDimension(context);
  let values;
  if (dimension === "creative_angle") values = angleValues(context);
  else if (dimension === "duration") values = durationValues(context, spec);
  else if (dimension === "proof_type") {
    values = [
      { value: "product_detail", control: true, allocation: 0.34 },
      { value: "usage_demo", control: false, allocation: 0.33 },
      { value: "feature_closeup", control: false, allocation: 0.33 },
    ];
  } else {
    values = [
      { value: "soft_action", control: true, allocation: 0.34 },
      { value: "direct_action", control: false, allocation: 0.33 },
      { value: "no_cta", control: false, allocation: 0.33 },
    ];
  }
  const minimum = Math.max(MINI_AI_RULES.minimumBatchSize, values.length * 2);
  if (batchSize < minimum) {
    return planBlock(context, "batch_too_small", `Для ${values.length} вариантов нужно минимум ${minimum} запусков.`);
  }
  const counts = allocateCounts(batchSize, values.map((item) => item.allocation));
  const arms = values.map((item, index) => armFromValue(context, dimension, item, counts[index], batchSize, index));
  const estimatedCostMinor = arms.reduce(
    (sum, arm) => sum + arm.plannedCount * requestedCostMinor(context.mode, arm.durationSeconds),
    0,
  );
  if (context.maxBudgetMinor > 0 && estimatedCostMinor > context.maxBudgetMinor) {
    return planBlock(context, "batch_budget_exceeded", "Стоимость пакета выше заданного лимита.");
  }
  const control = arms.find((arm) => arm.control);
  if (!control || control.allocation < MINI_AI_RULES.minimumControlShare) {
    return planBlock(context, "control_share_invalid", "Контрольная группа получила слишком маленькую долю.");
  }
  return Object.freeze({
    version: "mini-ai-plan.v1",
    planId: `mini-ai-${stableHash({ context, dimension, arms })}`,
    executable: true,
    dimension,
    batchSize,
    estimatedCostMinor,
    arms: Object.freeze(arms),
    blockers: Object.freeze([]),
    warnings: Object.freeze([
      "Вывод появится только после QA, публикации и зрелых метрик.",
      "Winner не масштабируется без подтверждения человека.",
    ]),
    reasonCodes: Object.freeze([
      "one_question_one_cycle",
      "views_never_define_winner",
      context.categoryIsNew ? "new_category_isolated" : "matched_scope_only",
      "control_retained",
    ]),
    context,
  });
}

function armSummary(armId, outcomes, objective) {
  const completed = outcomes.filter((item) => ["succeeded", "failed", "cancelled"].includes(item.state));
  const succeeded = outcomes.filter((item) => item.state === "succeeded");
  const eligible = outcomes.filter((item) =>
    item.state === "succeeded"
    && item.qaState === "approved"
    && item.productFidelityOk !== false
    && item.criticalBlocker !== true
    && item.published === true
    && item.metricsMature === true
    && Number.isFinite(Number(item.orders))
  );
  const qaDecided = succeeded.filter((item) => ["approved", "needs_changes", "rejected"].includes(item.qaState));
  const orders = eligible.reduce((sum, item) => sum + Math.max(0, Number(item.orders) || 0), 0);
  const carts = eligible.reduce((sum, item) => sum + Math.max(0, Number(item.carts) || 0), 0);
  const salesMinor = eligible.reduce((sum, item) => sum + Math.max(0, Number(item.salesMinor) || 0), 0);
  const spendMinor = eligible.reduce((sum, item) => sum + Math.max(0, Number(item.spendMinor) || 0), 0);
  const days = eligible.reduce((sum, item) => sum + Math.max(1, Number(item.attributionDays) || 1), 0);
  const approved = succeeded.filter((item) => item.qaState === "approved").length;
  const ordersPerDay = orders / Math.max(1, days);
  const conversion = orders / Math.max(1, carts);
  const salesPerDayMinor = salesMinor / Math.max(1, days);
  const qaRate = approved / Math.max(1, qaDecided.length);
  const costPerOrderMinor = orders > 0 ? spendMinor / orders : null;
  const objectiveValue = {
    orders: ordersPerDay,
    sales: salesPerDayMinor,
    conversion,
    qa_acceptance: qaRate,
    cost_per_order: costPerOrderMinor === null ? Number.NEGATIVE_INFINITY : -costPerOrderMinor,
  }[objective];
  return Object.freeze({
    armId,
    completed: completed.length,
    eligible: eligible.length,
    approved,
    failed: outcomes.filter((item) => ["failed", "cancelled"].includes(item.state)).length,
    criticalBlockers: outcomes.filter((item) => item.criticalBlocker === true).length,
    productMismatches: outcomes.filter((item) => item.productFidelityOk === false).length,
    orders,
    carts,
    salesMinor,
    spendMinor,
    attributionDays: days,
    views: eligible.reduce((sum, item) => sum + Math.max(0, Number(item.views) || 0), 0),
    ordersPerDay,
    conversion,
    salesPerDayMinor,
    qaRate,
    costPerOrderMinor,
    objectiveValue,
  });
}

function primaryMetric(summary, objective) {
  return {
    orders: summary.ordersPerDay,
    sales: summary.salesPerDayMinor,
    conversion: summary.conversion,
    qa_acceptance: summary.qaRate,
    cost_per_order: summary.costPerOrderMinor ?? Number.POSITIVE_INFINITY,
  }[objective];
}

function gap(challenger, control, objective) {
  const winnerValue = primaryMetric(challenger, objective);
  const controlValue = primaryMetric(control, objective);
  if (objective === "cost_per_order") {
    if (!Number.isFinite(winnerValue) || !Number.isFinite(controlValue) || controlValue <= 0) return { absolute: 0, relative: 0, better: false };
    const absolute = controlValue - winnerValue;
    return { absolute, relative: absolute / controlValue, better: absolute > 0 };
  }
  const absolute = winnerValue - controlValue;
  const denominator = Math.abs(controlValue) > 1e-9 ? Math.abs(controlValue) : 1;
  return { absolute, relative: absolute / denominator, better: absolute > 0 };
}

export function evaluateMiniAiPlan(plan, outcomes = []) {
  if (!plan?.executable) {
    return Object.freeze({
      decision: "blocked",
      confidence: "low",
      summary: "Пакет заблокирован правилами.",
      nextAction: plan?.blockers?.[0] || "Исправьте контекст.",
      winnerArmId: null,
      evidence: Object.freeze([]),
    });
  }
  const armIds = new Set(plan.arms.map((arm) => arm.armId));
  const source = outcomes.map((item, index) => ({
    outcomeId: clean(item.outcomeId || `outcome-${index}`, 120),
    jobId: clean(item.jobId || `job-${index}`, 120),
    armId: clean(item.armId, 80),
    state: clean(item.state, 40) || "queued",
    qaState: clean(item.qaState, 40) || "pending",
    productFidelityOk: item.productFidelityOk !== false,
    criticalBlocker: item.criticalBlocker === true,
    published: item.published === true,
    metricsMature: item.metricsMature === true,
    orders: Number(item.orders),
    carts: Number(item.carts),
    salesMinor: Number(item.salesMinor),
    spendMinor: Number(item.spendMinor),
    attributionDays: Number(item.attributionDays) || 1,
    views: Number(item.views),
  }));
  if (source.some((item) => !armIds.has(item.armId))) throw new Error("outcome_arm_not_in_plan");
  if (new Set(source.map((item) => item.jobId)).size !== source.length) throw new Error("duplicate_generation_job");
  const summaries = plan.arms.map((arm) => armSummary(
    arm.armId,
    source.filter((item) => item.armId === arm.armId),
    plan.context.objective,
  ));
  const mismatches = summaries.reduce((sum, item) => sum + item.productMismatches, 0);
  const critical = summaries.reduce((sum, item) => sum + item.criticalBlockers, 0);
  if (mismatches || critical) {
    return Object.freeze({
      decision: "pause_quality",
      confidence: "high",
      summary: mismatches
        ? "Очередь остановлена: обнаружена подмена или искажение точного товара."
        : "Очередь остановлена из-за критического QA-блокера.",
      nextAction: "Исправьте общий шаблон и начните новый маленький контрольный пакет.",
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze([`Подмен товара: ${mismatches}; критических блокеров: ${critical}.`]),
    });
  }
  const completed = summaries.reduce((sum, item) => sum + item.completed, 0);
  const failed = summaries.reduce((sum, item) => sum + item.failed, 0);
  if (completed >= MINI_AI_RULES.minimumTotalObservations && failed / Math.max(1, completed) > MINI_AI_RULES.maximumFailureRate) {
    return Object.freeze({
      decision: "pause_technical",
      confidence: "high",
      summary: "Техническая доля ошибок слишком высока; креативы сравнивать нельзя.",
      nextAction: "Исправьте провайдера, исходники или технический контракт запуска.",
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze([`Ошибок: ${failed} из ${completed}.`]),
    });
  }
  if (!source.length) {
    return Object.freeze({
      decision: "collect_more",
      confidence: "low",
      summary: "План готов, но результатов ещё нет.",
      nextAction: "Запустите очередь и дождитесь QA, публикации и зрелых метрик.",
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze([]),
    });
  }
  if (source.some((item) => item.state === "succeeded" && !(item.qaState === "approved" && item.published && item.metricsMature))) {
    return Object.freeze({
      decision: "wait_metrics",
      confidence: "low",
      summary: "Ролики созданы, но полный цикл измерения ещё не завершён.",
      nextAction: "Дождитесь QA, публикации и окна атрибуции. Не выбирайте winner по просмотрам.",
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze(["Просмотры не участвуют в выборе winner."]),
    });
  }
  if (summaries.some((item) => item.eligible < MINI_AI_RULES.minimumObservationsPerArm)) {
    return Object.freeze({
      decision: "collect_more",
      confidence: "low",
      summary: "Выборка слишком мала для честного вывода.",
      nextAction: `Доберите минимум ${MINI_AI_RULES.minimumObservationsPerArm} зрелых результата на каждый вариант.`,
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze([]),
    });
  }
  if (summaries.some((item) => item.qaRate < MINI_AI_RULES.minimumQaRate)) {
    return Object.freeze({
      decision: "pause_quality",
      confidence: "medium",
      summary: "Пакет не прошёл минимальный уровень качества.",
      nextAction: "Исправьте общий шаблон и повторите маленький контрольный пакет.",
      winnerArmId: null,
      summaries: Object.freeze(summaries),
      evidence: Object.freeze(summaries.map((item) => `${item.armId}: QA ${Math.round(item.qaRate * 100)}%`)),
    });
  }
  const controlArm = plan.arms.find((arm) => arm.control);
  const control = summaries.find((item) => item.armId === controlArm.armId);
  const challengers = summaries.filter((item) => item.armId !== control.armId);
  challengers.sort((left, right) => right.objectiveValue - left.objectiveValue);
  const challenger = challengers[0];
  const difference = gap(challenger, control, plan.context.objective);
  const absoluteRequired = {
    orders: MINI_AI_RULES.minimumOrdersPerDayGap,
    sales: MINI_AI_RULES.minimumSalesPerDayGapMinor,
    conversion: MINI_AI_RULES.minimumConversionGap,
    qa_acceptance: MINI_AI_RULES.minimumQaGap,
    cost_per_order: 0,
  }[plan.context.objective];
  const relativeRequired = plan.context.objective === "cost_per_order"
    ? MINI_AI_RULES.minimumCostPerOrderImprovement
    : MINI_AI_RULES.minimumRelativeUplift;
  const clear = difference.better
    && difference.absolute >= absoluteRequired
    && difference.relative >= relativeRequired
    && challenger.qaRate + 0.05 >= control.qaRate;
  const evidence = Object.freeze([
    `Контроль: ${primaryMetric(control, plan.context.objective).toFixed(3)}; QA ${Math.round(control.qaRate * 100)}%.`,
    `Challenger: ${primaryMetric(challenger, plan.context.objective).toFixed(3)}; QA ${Math.round(challenger.qaRate * 100)}%.`,
    `Разница: ${difference.absolute.toFixed(3)} (${Math.round(difference.relative * 100)}%).`,
    "Просмотры не использовались для выбора winner.",
  ]);
  if (clear) {
    return Object.freeze({
      decision: "promote_with_control",
      confidence: Math.min(control.eligible, challenger.eligible) >= 6 ? "high" : "medium",
      summary: "Есть устойчивый challenger по бизнес-метрике без ухудшения QA.",
      nextAction: "После подтверждения человеком дайте winner 70%, а контролю 30%; затем проверяйте следующий фактор.",
      winnerArmId: challenger.armId,
      controlArmId: control.armId,
      allocations: Object.freeze({ [challenger.armId]: 0.70, [control.armId]: 0.30 }),
      summaries: Object.freeze(summaries),
      evidence,
    });
  }
  if (control.objectiveValue >= challenger.objectiveValue || !difference.better) {
    return Object.freeze({
      decision: "keep_control",
      confidence: "medium",
      summary: "Ни одна гипотеза не превзошла контроль достаточно уверенно.",
      nextAction: "Оставьте контроль основным и назначьте новую ограниченную гипотезу.",
      winnerArmId: control.armId,
      controlArmId: control.armId,
      allocations: Object.freeze({ [control.armId]: 0.80, [challenger.armId]: 0.20 }),
      summaries: Object.freeze(summaries),
      evidence,
    });
  }
  return Object.freeze({
    decision: "collect_more",
    confidence: "low",
    summary: "Challenger выглядит лучше, но разрыв ещё не прошёл пороги устойчивости.",
    nextAction: "Продолжите тот же matched-тест и не меняйте остальные факторы.",
    winnerArmId: null,
    controlArmId: control.armId,
    summaries: Object.freeze(summaries),
    evidence,
  });
}

export function miniAiEstimatedCostUsd(plan) {
  return Number(plan?.estimatedCostMinor || 0) / 100;
}
