export const CONTENT_GENERATION_HANDOFF_VERSION = 2;
export const CONTENT_GENERATION_PROMPT_LIMIT = 1_200;
export const SEEDANCE_SPOKEN_WORD_LIMIT = 22;
export const CONTENT_GENERATION_PRODUCT_REFERENCE_TAG = "ProductReference";
export const GENERATION_LEARNING_COMPILER_VERSION = "safe-brief-v7";
export const GENERATION_REPAIR_COMPILER_VERSION = "review-repair-v1";

const HANDOFF_MAX_AGE_MS = 24 * 60 * 60 * 1_000;
const REAL_GEN4_MODE = "real_gen4";
const REAL_SEEDANCE_MODE = "real_seedance";
const REAL_PHOTO_MODE = "real_photo";
const GENERATED_TEXT_GUARD =
  "Без сгенерированных надписей, субтитров и декоративного текста.";
const PRODUCT_INTERACTION_PREFIX = "Масштаб и действие:";
const COUNTERTOP_PRODUCT_PATTERN =
  /(?:пароварк|мультиварк|аэрогрил|духовк|микроволнов|кофемашин|кофеварк|электрогрил|тостер|соковыжимал|хлебопеч|кухонн\p{L}*\s+комбайн|стационарн\p{L}*\s+блендер|steamer|air\s*fryer|microwave|coffee\s*machine|countertop\s*appliance)/iu;
const INSTALLED_PRODUCT_PATTERN =
  /(?:холодильник|морозильник|стиральн\p{L}*\s+машин|сушильн\p{L}*\s+машин|посудомоеч|телевизор|матрас|диван|кресл|стол\b|шкаф|комод|пылесос|кондиционер|обогревател|велосипед|самокат|коляск|refrigerator|washing\s*machine|dishwasher|television|mattress|sofa|wardrobe|vacuum)/iu;
const VIDEO_DURATION_OPTIONS = Object.freeze({
  [REAL_GEN4_MODE]: Object.freeze([2, 5, 8, 10]),
  [REAL_SEEDANCE_MODE]: Object.freeze([4, 8, 12, 15]),
});
const SAFE_SCENARIO_INTENT_LIMIT = 400;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const EXPLICIT_SPOKEN_LINE_PATTERN =
  /(^|[.!?…]\s+)((?:(?:герой|блогер|ведущ(?:ий|ая)|человек)\s+(?:говорит|произносит|рассказывает)|реплика\s+героя(?:\s+дословно)?))\s*:\s*[«“"]([^»”"]{2,500})[»”"]\s*[.!?…]?/iu;

export function contentGenerationDurationSeconds(mode, value = null) {
  const normalizedMode = normalizeMode(mode);
  if (normalizedMode === REAL_PHOTO_MODE) return 0;
  const allowed = VIDEO_DURATION_OPTIONS[normalizedMode] || [];
  const duration = Number(value);
  if (Number.isInteger(duration) && allowed.includes(duration)) {
    return duration;
  }
  return normalizedMode === REAL_GEN4_MODE ? 5 : 8;
}

export function seedanceSpokenWordLimit(durationSeconds = 8) {
  const duration = contentGenerationDurationSeconds(
    REAL_SEEDANCE_MODE,
    durationSeconds,
  );
  return Math.max(
    10,
    Math.min(42, Math.floor(duration * SEEDANCE_SPOKEN_WORD_LIMIT / 8)),
  );
}

export function createContentGenerationHandoff(
  record,
  scenarioIndex,
  now = Date.now(),
  { projectId = "" } = {},
) {
  if (record?.approved !== true) {
    throw new Error("Сначала утвердите ТЗ и сценарии после ручной проверки.");
  }
  const scenarios = Array.isArray(record?.scenarios) ? record.scenarios : [];
  const normalizedIndex = Number(scenarioIndex);
  const scenario = scenarios[normalizedIndex];
  if (!Number.isInteger(normalizedIndex) || normalizedIndex < 0 || !scenario) {
    throw new Error("Выбранный сценарий не найден. Обновите исследование.");
  }

  const productName = cleanText(record?.productName);
  const sku = cleanText(record?.sku);
  const researchId = cleanText(record?.id);
  const draftId = cleanText(record?.draftId);
  const normalizedProjectId = cleanText(projectId || record?.project_id || record?.projectId).toLowerCase();
  if (!productName || !sku || !researchId || !draftId || !UUID_PATTERN.test(normalizedProjectId)) {
    throw new Error("У утверждённого ТЗ не хватает связи с товаром или исследованием.");
  }

  const brief = record?.brief && typeof record.brief === "object"
    ? record.brief
    : {};
  return {
    version: CONTENT_GENERATION_HANDOFF_VERSION,
    createdAt: Number(now),
    projectId: normalizedProjectId,
    researchId,
    draftId,
    productName,
    sku,
    sourceIds: uniqueStrings(record?.sourceIds, 24),
    scenario: {
      position: normalizedIndex + 1,
      title: cleanText(scenario.title) || `Сценарий ${normalizedIndex + 1}`,
      platform: normalizePlatform(scenario.platform),
      recommendedGenerationMode: normalizeRecommendedGenerationMode(
        scenario.recommendedGenerationMode
          || scenario.recommended_generation_mode
          || scenario.generationMode
          || scenario.generation_mode,
      ),
      generationModeReason: cleanText(
        scenario.generationModeReason
          || scenario.generation_mode_reason,
      ).slice(0, 400),
      hook: cleanText(scenario.hook),
      spokenScript: cleanText(scenario.script || scenario.spokenScript),
      shotList: cleanMultiline(scenario.shotList || scenario.shot_list),
      taskTitle: cleanText(scenario.taskTitle || scenario.task_title),
    },
    creativeBrief: {
      targetAudience: cleanText(brief.targetAudience || brief.target_audience),
      keyMessage: cleanText(brief.keyMessage || brief.key_message),
      proofPoints: lines(brief.proofPoints || brief.proof_points, 8),
      avoidClaims: lines(brief.avoidClaims || brief.avoid_claims, 8),
      visualDirection: cleanText(brief.visualDirection || brief.visual_direction),
      cta: cleanText(brief.cta),
    },
  };
}

export function parseContentGenerationHandoff(serialized, now = Date.now()) {
  if (typeof serialized !== "string" || serialized.length < 2 || serialized.length > 40_000) {
    return null;
  }
  let value;
  try {
    value = JSON.parse(serialized);
  } catch {
    return null;
  }
  if (!validHandoff(value, now)) return null;
  return value;
}

export function compileContentGenerationPrompt(
  handoff,
  mode,
  learningPolicy = null,
  repairPolicy = null,
  durationSeconds = null,
  productCategory = "",
) {
  if (!validHandoff(handoff, handoff?.createdAt)) {
    return result("", [{
      code: "handoff_invalid",
      message: "Связь со сценарием повреждена. Вернитесь в разбор товара.",
    }], []);
  }

  const normalizedMode = normalizeMode(mode);
  if (normalizedMode === REAL_PHOTO_MODE) {
    const visualDirection = photoScenarioVisualDirection(handoff);
    return compileSafeGenerationBrief({
      mode: normalizedMode,
      productName: handoff.productName,
      sku: handoff.sku,
      visualDirection,
      avoidClaims: handoff.creativeBrief?.avoidClaims,
      learningPolicy,
      repairPolicy,
      durationSeconds: 0,
      productCategory,
    });
  }
  const seedance = normalizedMode === REAL_SEEDANCE_MODE;
  const gen4 = normalizedMode === REAL_GEN4_MODE;
  const normalizedDuration = contentGenerationDurationSeconds(
    normalizedMode,
    durationSeconds,
  );
  const spokenWordLimit = seedanceSpokenWordLimit(normalizedDuration);
  const scenario = handoff.scenario;
  const brief = handoff.creativeBrief;
  const shotLimit = seedance
    ? normalizedDuration >= 12 ? 3 : 2
    : normalizedDuration >= 8 ? 2 : 1;
  const shotLines = lines(scenario.shotList, shotLimit);
  const interaction = inferProductInteractionProfile({
    productName: handoff.productName,
    productCategory,
  });
  const rawAction = shotLines.join(" Затем ");
  const action = generationActionFitsProduct(rawAction, interaction)
    ? rawAction
    : interaction.videoAction;
  const spokenWords = words(scenario.spokenScript).length;
  const blockers = [];
  const warnings = [];

  if (!scenario.hook) {
    blockers.push({
      code: "hook_missing",
      message: "В сценарии нет хука первых секунд.",
    });
  }
  if (!action) {
    blockers.push({
      code: "shot_plan_missing",
      message: "Добавьте хотя бы один понятный кадр или действие.",
    });
  }
  if (seedance && !scenario.spokenScript) {
    blockers.push({
      code: "spoken_script_missing",
      message: `Для ${normalizedDuration}-секундного ролика с голосом нужна точная реплика героя.`,
    });
  }
  if (seedance && spokenWords > spokenWordLimit) {
    blockers.push({
      code: "spoken_script_too_long",
      message: `Реплика содержит ${spokenWords} слов. Для ${normalizedDuration} секунд оставьте не больше ${spokenWordLimit}.`,
    });
  }
  if (!brief.proofPoints.length) {
    warnings.push({
      code: "proof_points_missing",
      message: "Подтверждённые доказательства не перечислены — промпт запрещает добавлять новые свойства.",
    });
  }
  if (!brief.avoidClaims.length) {
    warnings.push({
      code: "avoid_claims_missing",
      message: "Стоп-формулировки не заполнены. Проверьте обещания вручную.",
    });
  }
  if (gen4 && scenario.spokenScript) {
    warnings.push({
      code: "audio_ignored",
      message: "Режим Gen4 создаёт ролик без речи; реплика останется только смысловым ориентиром.",
    });
  }
  if (shotLines.length > shotLimit) {
    warnings.push({
      code: "shot_plan_dense",
      message: `Для ${normalizedDuration} секунд лучше оставить не больше ${shotLimit} ${shotLimit === 1 ? "действия" : "действий"}.`,
    });
  }

  const spokenLine = seedance
    ? spokenWords <= spokenWordLimit
      ? `Реплика героя дословно: «${scenario.spokenScript}»`
      : `Реплика героя дословно: «[СОКРАТИТЕ РЕПЛИКУ ДО ${spokenWordLimit} СЛОВ]»`
    : "Без речи, дикторского текста и сгенерированных надписей.";
  const promptLines = [
    required(`Создай один непрерывный вертикальный ${seedance ? "UGC-" : ""}ролик длительностью ${normalizedDuration} секунд.`),
    required(`Точный товар: ${handoff.productName}, артикул ${handoff.sku}.`),
    optional(`Хук: ${scenario.hook}.`),
    required(`Действие в кадре: ${action || "[ДОБАВЬТЕ ОДНО ПОНЯТНОЕ ДЕЙСТВИЕ]"}.`),
    required(interaction.requirement),
    required(spokenLine),
    required(seedance ? GENERATED_TEXT_GUARD : ""),
    optional(brief.visualDirection ? `Визуальное направление: ${brief.visualDirection}.` : ""),
    optional(brief.keyMessage ? `Главная мысль: ${brief.keyMessage}.` : ""),
    optional(brief.proofPoints.length ? `Разрешённые доказательства: ${brief.proofPoints.join("; ")}.` : ""),
    optional(brief.cta ? `CTA: ${brief.cta}.` : ""),
    required("С первого кадра показывай именно этот товар. Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений."),
    required("Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара."),
    optional(brief.avoidClaims.length ? `Не использовать: ${brief.avoidClaims.join("; ")}.` : ""),
    required(generationLearningDirection(
      learningPolicy,
      normalizedMode,
      repairPolicy,
    )),
  ];
  const prompt = fitPrompt(promptLines, CONTENT_GENERATION_PROMPT_LIMIT);
  if (!prompt) {
    blockers.push({
      code: "prompt_too_long",
      message: "Даже обязательная часть промпта длиннее лимита. Сократите название товара или реплику.",
    });
  }

  const inspection = inspectContentGenerationPrompt(prompt, normalizedMode, {
    productName: handoff.productName,
    avoidClaims: brief.avoidClaims,
    durationSeconds: normalizedDuration,
    productCategory,
  });
  for (const blocker of inspection.blockers) {
    if (!blockers.some((item) => item.code === blocker.code)) blockers.push(blocker);
  }
  for (const warning of inspection.warnings) {
    if (!warnings.some((item) => item.code === warning.code)) warnings.push(warning);
  }
  return result(prompt, blockers, warnings, {
    durationSeconds: normalizedDuration,
    spokenWords,
    mode: normalizedMode,
  });
}

export function compileSafeGenerationBrief({
  mode,
  productName,
  sku,
  scenarioIntent = "",
  visualDirection = "",
  avoidClaims = [],
  learningPolicy = null,
  repairPolicy = null,
  durationSeconds: requestedDurationSeconds = null,
  productCategory = "",
} = {}) {
  const normalizedMode = normalizeMode(mode);
  const exactProductName = cleanText(productName);
  const exactSku = cleanText(sku);
  const rawScenarioIntent = cleanText(scenarioIntent).slice(0, 1_200);
  const explicitSpokenLine = extractExplicitSpokenLine(rawScenarioIntent);
  const safeScenarioIntent = truncateScenarioIntent(
    removeExplicitSpokenLine(rawScenarioIntent),
    SAFE_SCENARIO_INTENT_LIMIT,
  );
  const safeVisualDirection = cleanText(visualDirection);
  const safeAvoidClaims = uniqueStrings(avoidClaims, 8);
  const learningDirection = generationLearningDirection(
    learningPolicy,
    normalizedMode,
    repairPolicy,
  );
  const interaction = inferProductInteractionProfile({
    productName: exactProductName,
    productCategory,
  });
  const blockers = [];
  const warnings = [];

  if (!exactProductName) {
    blockers.push({
      code: "product_identity_missing",
      message: "Выберите проверенный исходник с точным названием товара.",
    });
  }
  if (!exactSku) {
    blockers.push({
      code: "product_sku_missing",
      message: "Выберите проверенный исходник с точным артикулом.",
    });
  }
  if (!exactProductName || !exactSku) {
    return result("", blockers, warnings, {
      durationSeconds: normalizedMode === REAL_PHOTO_MODE
        ? 0
        : contentGenerationDurationSeconds(
          normalizedMode,
          requestedDurationSeconds,
        ),
      spokenWords: 0,
      mode: normalizedMode,
    });
  }

  const identityLine = `Точный товар: ${exactProductName}, артикул ${exactSku}.`;
  const productLock = "Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.";
  const claimGuard = "Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.";
  let promptLines;
  let durationSeconds;
  let spokenWords = 0;

  if (normalizedMode === REAL_PHOTO_MODE) {
    durationSeconds = 0;
    promptLines = [
      required("Создай одно квадратное товарное фото 2048 × 2048."),
      required(`Используй @${CONTENT_GENERATION_PRODUCT_REFERENCE_TAG} как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали. ${identityLine}`),
      optional("Студийное фото: один товар целиком по центру, нейтральный фон, мягкий свет, естественная тень, высокая детализация."),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      optional("Товар — единственный главный объект; оставь безопасные поля по краям."),
      required(productLock),
      required(claimGuard),
      required("Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса."),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  } else if (normalizedMode === REAL_GEN4_MODE) {
    durationSeconds = contentGenerationDurationSeconds(
      normalizedMode,
      requestedDurationSeconds,
    );
    promptLines = [
      required(`Создай один непрерывный вертикальный ролик длительностью ${durationSeconds} секунд.`),
      required(identityLine),
      optional(
        safeScenarioIntent
          ? `Замысел пользователя (только без конфликта с ограничениями ниже): ${withTerminalPunctuation(safeScenarioIntent)}`
          : interaction.gen4Action,
      ),
      required(interaction.requirement),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      required("Без речи, дикторского текста и сгенерированных надписей."),
      required(productLock),
      required(claimGuard),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  } else {
    durationSeconds = contentGenerationDurationSeconds(
      normalizedMode,
      requestedDurationSeconds,
    );
    const spokenLine = safeScenarioSpokenLine({
      scenarioIntent: rawScenarioIntent,
      explicitSpokenLine,
      productName: exactProductName,
      fallback: interaction.spokenLine,
      durationSeconds,
    });
    spokenWords = words(spokenLine).length;
    promptLines = [
      required(`Создай один непрерывный вертикальный UGC-ролик длительностью ${durationSeconds} секунд.`),
      required(identityLine),
      optional(
        safeScenarioIntent
          ? `Замысел пользователя (только без конфликта с ограничениями ниже): ${withTerminalPunctuation(safeScenarioIntent)}`
          : interaction.videoAction,
      ),
      required(interaction.requirement),
      required(`Реплика героя дословно: «${spokenLine}»`),
      required(GENERATED_TEXT_GUARD),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      required(productLock),
      required(claimGuard),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  }

  const prompt = fitPrompt(promptLines, CONTENT_GENERATION_PROMPT_LIMIT);
  if (!prompt) {
    blockers.push({
      code: "prompt_too_long",
      message: "Точное название товара слишком длинное для безопасного промпта.",
    });
  }
  const inspection = inspectContentGenerationPrompt(prompt, normalizedMode, {
    productName: exactProductName,
    avoidClaims: safeAvoidClaims,
    durationSeconds,
    productCategory,
  });
  for (const blocker of inspection.blockers) {
    if (!blockers.some((item) => item.code === blocker.code)) blockers.push(blocker);
  }
  return result(prompt, blockers, warnings, {
    durationSeconds,
    spokenWords,
    mode: normalizedMode,
    learningApplied: Boolean(learningDirection),
  });
}

export function inferGenerationCreativeSignals({
  hook = "",
  shotList = "",
  visualDirection = "",
} = {}) {
  const combined = cleanText(`${hook} ${shotList} ${visualDirection}`);
  const lowered = combined.toLocaleLowerCase("ru-RU");
  const hookPatterns = [];
  if (hook.includes("?")) hookPatterns.push("question_led");
  if (/(?:^|[^\p{L}\p{N}_])(?:why|почему|зачем)(?=$|[^\p{L}\p{N}_])/iu.test(lowered)) {
    hookPatterns.push("why_explanation");
  }
  if (/(?:^|[^\p{L}\p{N}_])(?:before|до покупки|перед покупкой)(?=$|[^\p{L}\p{N}_])/iu.test(lowered)) {
    hookPatterns.push("before_buying");
  }
  if (/(?:^|[^\p{L}\p{N}_])(?:compare|versus|vs|сравн\p{L}*|дешев\p{L}*)/iu.test(lowered)) {
    hookPatterns.push("comparison");
  }
  if (/(?:^|[^\p{L}\p{N}_])(?:watch|show|see|смотр\p{L}*|покаж\p{L}*)/iu.test(lowered)) {
    hookPatterns.push("demonstration");
  }
  if (/(?:^|[^\p{L}\p{N}_])(?:i|my|я|мой|моя|мне)(?=$|[^\p{L}\p{N}_])/iu.test(lowered)) {
    hookPatterns.push("first_person");
  }
  if (
    /\d/u.test(combined)
    || /(?:^|[^\p{L}\p{N}_])(?:one|один|одна|три|three)(?=$|[^\p{L}\p{N}_])/iu.test(lowered)
  ) {
    hookPatterns.push("numbered");
  }
  if (cleanText(hook).length > 0 && cleanText(hook).length <= 72) {
    hookPatterns.push("concise");
  }

  let creativeAngle = "product_focus";
  if (hookPatterns.includes("comparison")) creativeAngle = "comparison";
  else if (
    hookPatterns.includes("before_buying")
    || hookPatterns.includes("why_explanation")
  ) creativeAngle = "objection_handling";
  else if (hookPatterns.includes("demonstration")) creativeAngle = "demonstration";
  else if (hookPatterns.includes("question_led")) creativeAngle = "curiosity_gap";
  else if (/(?:^|[^\p{L}\p{N}_])(?:честн\p{L}*|довер\p{L}*|спокойн\p{L}*|реальн\p{L}*|trust)/iu.test(lowered)) {
    creativeAngle = "trust_builder";
  }
  return {
    creativeAngle,
    hookPatterns: [...new Set(hookPatterns)].slice(0, 8),
  };
}

export function normalizeGenerationLearningPolicy(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const allowedAngles = new Set([
    "product_focus",
    "trust_builder",
    "demonstration",
    "comparison",
    "objection_handling",
    "curiosity_gap",
  ]);
  const allowedPatterns = new Set([
    "question_led",
    "why_explanation",
    "before_buying",
    "comparison",
    "demonstration",
    "first_person",
    "numbered",
    "concise",
  ]);
  const allowedQualityGuards = new Set([
    "product_fidelity",
    "technical_stability",
    "audio_quality",
    "speech_fidelity",
    "hook_clarity",
    "visual_quality",
    "trust",
    "platform_fit",
  ]);
  const rawQualityGuardCodes = policyField(
    value,
    "quality_guard_codes",
    "qualityGuardCodes",
  ) ?? [];
  const qualityGuardCodesValid = Array.isArray(rawQualityGuardCodes)
    && rawQualityGuardCodes.length <= 3
    && new Set(rawQualityGuardCodes).size === rawQualityGuardCodes.length
    && rawQualityGuardCodes.every((code) => typeof code === "string");
  const qualityGuardCodes = qualityGuardCodesValid
    ? rawQualityGuardCodes.filter((code) => allowedQualityGuards.has(code))
    : [];
  const rawQualityGuardVariants = policyField(
    value,
    "quality_guard_variants",
    "qualityGuardVariants",
  );
  const qualityGuardVariants = {};
  let qualityGuardVariantsValid = qualityGuardCodesValid;
  if (rawQualityGuardVariants === undefined) {
    for (const code of qualityGuardCodes) qualityGuardVariants[code] = 1;
  } else if (
    rawQualityGuardVariants
    && typeof rawQualityGuardVariants === "object"
    && !Array.isArray(rawQualityGuardVariants)
    && Object.keys(rawQualityGuardVariants).length
      === qualityGuardCodes.length
    && Object.keys(rawQualityGuardVariants).every((code) =>
      qualityGuardCodes.includes(code)
      && [1, 2].includes(rawQualityGuardVariants[code])
    )
  ) {
    for (const code of qualityGuardCodes) {
      qualityGuardVariants[code] = rawQualityGuardVariants[code];
    }
  } else {
    qualityGuardVariantsValid = false;
  }
  const qualityGuardEffectivenessStatusValue = cleanText(policyField(
    value,
    "quality_guard_effectiveness_status",
    "qualityGuardEffectivenessStatus",
  ));
  const qualityGuardEffectivenessStatus = new Set([
    "clear",
    "not_applicable",
    "variant_2",
    "cooldown",
    "control_pending_review",
    "control_revalidation",
  ]).has(qualityGuardEffectivenessStatusValue)
    ? qualityGuardEffectivenessStatusValue
    : "clear";
  const preferredAngle = cleanText(policyField(
    value,
    "preferred_angle",
    "preferredAngle",
  ));
  const policyHash = cleanText(policyField(
    value,
    "policy_hash",
    "policyHash",
  ));
  const generationAllowed = policyField(
    value,
    "generation_allowed",
    "generationAllowed",
  ) !== false;
  const productCategory = cleanText(policyField(
    value,
    "product_category",
    "productCategory",
  ));
  const categoryEvidenceCountValue = Number(policyField(
    value,
    "category_evidence_count",
    "categoryEvidenceCount",
  ));
  const selectionMode = [
    "performance",
    "quality",
    "bounded_exploration",
  ].includes(
    cleanText(policyField(value, "selection_mode", "selectionMode")),
  )
    ? cleanText(policyField(value, "selection_mode", "selectionMode"))
    : "performance";
  const applied = value.applied === true
    && generationAllowed
    && qualityGuardVariantsValid
    && ["medium", "high"].includes(value.confidence)
    && allowedAngles.has(preferredAngle)
    && /^[0-9a-f]{64}$/u.test(policyHash);
  return {
    version: cleanText(value.version),
    applied,
    generationAllowed,
    productCategory,
    categoryEvidenceCount: Number.isInteger(categoryEvidenceCountValue)
      ? Math.max(0, categoryEvidenceCountValue)
      : 0,
    categoryColdStart: policyField(
      value,
      "category_cold_start",
      "categoryColdStart",
    ) === true,
    confidence: ["none", "low", "medium", "high"].includes(value.confidence)
      ? value.confidence
      : "none",
    evidenceCount: Number.isInteger(Number(policyField(
      value,
      "evidence_count",
      "evidenceCount",
    )))
      ? Math.max(0, Number(policyField(
        value,
        "evidence_count",
        "evidenceCount",
      )))
      : 0,
    preferredAngle: applied ? preferredAngle : "",
    avoidAngle: allowedAngles.has(cleanText(policyField(
      value,
      "avoid_angle",
      "avoidAngle",
    )))
      ? cleanText(policyField(value, "avoid_angle", "avoidAngle"))
      : "",
    preferredHookPatterns: uniqueStrings(
      policyField(
        value,
        "preferred_hook_patterns",
        "preferredHookPatterns",
      ),
      4,
    ).filter((pattern) => allowedPatterns.has(pattern)),
    qualityGuardCodes: applied ? qualityGuardCodes : [],
    qualityGuardVariants: qualityGuardVariantsValid
      ? qualityGuardVariants
      : {},
    qualityGuardEffectivenessStatus,
    qualityGuardEvidenceCount: Number.isInteger(
      Number(policyField(
        value,
        "quality_guard_evidence_count",
        "qualityGuardEvidenceCount",
      )),
    )
      ? Math.max(0, Number(policyField(
        value,
        "quality_guard_evidence_count",
        "qualityGuardEvidenceCount",
      )))
      : 0,
    qualityGuardConfidence: ["none", "low", "medium", "high"].includes(
      policyField(
        value,
        "quality_guard_confidence",
        "qualityGuardConfidence",
      ),
    )
      ? policyField(
        value,
        "quality_guard_confidence",
        "qualityGuardConfidence",
      )
      : "none",
    selectionMode,
    reasonCodes: uniqueStrings(policyField(
      value,
      "reason_codes",
      "reasonCodes",
    ), 8),
    scope: cleanText(policyField(value, "scope", "scope")),
    policyHash,
  };
}

export function normalizeGenerationRepairPolicy(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
  const hashPattern = /^[0-9a-f]{64}$/u;
  const allowedModels = new Set([
    "gen4_turbo",
    "seedance2_fast",
    "seedream5_lite",
  ]);
  const allowedPlatforms = new Set([
    "tiktok",
    "youtube",
    "vk",
    "telegram",
    "wildberries",
  ]);
  const allowedGuardCodes = new Set([
    "product_fidelity",
    "technical_stability",
    "audio_quality",
    "speech_fidelity",
    "hook_clarity",
    "visual_quality",
    "trust",
    "platform_fit",
  ]);
  const version = cleanText(value.version);
  const sourceReviewId = cleanText(policyField(
    value,
    "source_review_id",
    "sourceReviewId",
  ));
  const sourceGenerationJobId = cleanText(policyField(
    value,
    "source_generation_job_id",
    "sourceGenerationJobId",
  ));
  const sourceMediaId = cleanText(policyField(
    value,
    "source_media_id",
    "sourceMediaId",
  ));
  const inputMediaId = cleanText(policyField(
    value,
    "input_media_id",
    "inputMediaId",
  ));
  const productId = cleanText(policyField(
    value,
    "product_id",
    "productId",
  ));
  const model = cleanText(value.model);
  const platform = cleanText(value.platform).toLowerCase();
  const destinationRef = cleanText(policyField(
    value,
    "destination_ref",
    "destinationRef",
  ));
  const policyHash = cleanText(policyField(
    value,
    "policy_hash",
    "policyHash",
  ));
  const sourceReviewCompletionHash = cleanText(policyField(
    value,
    "source_review_completion_hash",
    "sourceReviewCompletionHash",
  ));
  const sourceMediaSha256 = cleanText(policyField(
    value,
    "source_media_sha256",
    "sourceMediaSha256",
  ));
  const guardCodes = uniqueStrings(policyField(
    value,
    "guard_codes",
    "guardCodes",
  ), 3).filter((code) => allowedGuardCodes.has(code));
  const scoreSource = policyField(value, "score_snapshot", "scoreSnapshot");
  const scoreSnapshot = {};
  for (const code of [
    "technical",
    "product_fidelity",
    "hook_clarity",
    "visual_quality",
    "trust",
    "platform_fit",
  ]) {
    const score = Number(scoreSource?.[code]);
    if (Number.isInteger(score) && score >= 0 && score <= 100) {
      scoreSnapshot[code] = score;
    }
  }
  const applied = value.applied === true
    && version === GENERATION_REPAIR_COMPILER_VERSION
    && [
      sourceReviewId,
      sourceGenerationJobId,
      sourceMediaId,
      inputMediaId,
      productId,
    ].every((id) => uuidPattern.test(id))
    && allowedModels.has(model)
    && allowedPlatforms.has(platform)
    && destinationRef.length >= 2
    && destinationRef.length <= 240
    && guardCodes.length >= 1
    && guardCodes.length <= 3
    && (
      model === "seedance2_fast"
      || !guardCodes.some((code) => [
        "audio_quality",
        "speech_fidelity",
      ].includes(code))
    )
    && Object.keys(scoreSnapshot).length === 6
    && hashPattern.test(policyHash)
    && hashPattern.test(sourceReviewCompletionHash)
    && hashPattern.test(sourceMediaSha256);
  return {
    version,
    applied,
    sourceReviewId: applied ? sourceReviewId : "",
    sourceGenerationJobId: applied ? sourceGenerationJobId : "",
    sourceMediaId: applied ? sourceMediaId : "",
    inputMediaId: applied ? inputMediaId : "",
    productId: applied ? productId : "",
    model: applied ? model : "",
    platform: applied ? platform : "",
    destinationRef: applied ? destinationRef : "",
    guardCodes: applied ? guardCodes : [],
    scoreSnapshot: applied ? scoreSnapshot : {},
    sourceReviewCompletionHash: applied ? sourceReviewCompletionHash : "",
    sourceMediaSha256: applied ? sourceMediaSha256 : "",
    policyHash: applied ? policyHash : "",
    reasonCodes: uniqueStrings(policyField(
      value,
      "reason_codes",
      "reasonCodes",
    ), 8),
  };
}

function policyField(value, wireName, normalizedName) {
  const hasWireValue = Object.hasOwn(value, wireName);
  const hasNormalizedValue = Object.hasOwn(value, normalizedName);
  if (hasWireValue && hasNormalizedValue) {
    const wireValue = value[wireName];
    const normalizedValue = value[normalizedName];
    if (JSON.stringify(wireValue) !== JSON.stringify(normalizedValue)) {
      return undefined;
    }
  }
  if (hasWireValue) return value[wireName];
  return hasNormalizedValue ? value[normalizedName] : undefined;
}

function generationLearningDirection(value, mode, repairValue = null) {
  const policy = normalizeGenerationLearningPolicy(value);
  const repairPolicy = normalizeGenerationRepairPolicy(repairValue);
  if (!policy?.applied && !repairPolicy?.applied) return "";
  const photoDirections = {
    product_focus: "Обученный ракурс: товар целиком, строгий фокус.",
    trust_builder: "Обученный ракурс: естественная предметная подача.",
    demonstration: "Обученный ракурс: одна видимая деталь товара.",
    comparison: "Обученный ракурс: ясный масштаб без второго товара.",
    objection_handling: "Обученный ракурс: упаковка и проверяемые детали.",
    curiosity_gap: "Обученный ракурс: выразительная деталь при видимом целом товаре.",
  };
  const videoDirections = {
    product_focus: "Обученное направление: товар главный во всех кадрах.",
    trust_builder: "Обученное направление: естественная подача без преувеличений.",
    demonstration: "Обученное направление: одно видимое действие с товаром.",
    comparison: "Обученное направление: сравнение без второго товара и обещаний.",
    objection_handling: "Обученное направление: одна проверяемая деталь товара.",
    curiosity_gap: "Обученное направление: заметная деталь, затем товар целиком.",
  };
  const angleDirection = !policy?.applied
    ? ""
    : mode === REAL_PHOTO_MODE
    ? photoDirections[policy.preferredAngle] || ""
    : videoDirections[policy.preferredAngle] || "";
  const hookDirections = {
    question_led: "Структурный hook: визуальный вопрос сразу раскрывается точным товаром.",
    why_explanation: "Структурный hook: видимая причина рассмотреть товар, без утверждений.",
    before_buying: "Структурный hook: спокойная проверка товара перед выбором.",
    comparison: "Структурный hook: сравнение без второго товара, цифр и обещаний.",
    demonstration: "Структурный hook: одно простое действие с товаром.",
    first_person: "Структурный hook: от первого лица; товар целиком и в фокусе.",
    numbered: "Структурный hook: один понятный шаг без цифр и надписей.",
    concise: "Структурный hook: простой первый кадр сразу показывает товар.",
  };
  const hookDirection = !policy?.applied || mode === REAL_PHOTO_MODE
    ? ""
    : hookDirections[policy.preferredHookPatterns[0]] || "";
  const photoQualityGuards = {
    product_fidelity: {
      1: "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
      2: "QA+: один товар строго по исходнику; не изменять ни одну букву, край, цвет или пропорцию упаковки.",
    },
    technical_stability: {
      1: "QA: резкий товар, ровный свет, без пересвета и размытия.",
      2: "QA+: нейтральный ровный свет; весь товар резкий, без бликов, шума и размытия.",
    },
    hook_clarity: {
      1: "QA: товар считывается первым.",
      2: "QA+: товар занимает главный визуальный акцент и считывается без второго объекта.",
    },
    visual_quality: {
      1: "QA: чистые края без дублей, деформаций и AI-артефактов.",
      2: "QA+: цельный чистый силуэт; никаких лишних деталей, дублей, швов и AI-артефактов.",
    },
    trust: {
      1: "QA: естественные материалы, свет и масштаб.",
      2: "QA+: реалистичные материалы, масштаб и тени как в предметной съёмке.",
    },
    platform_fit: {
      1: "QA: мастер 1:1, безопасные поля.",
      2: "QA+: квадрат 1:1; упаковка целиком внутри безопасных полей.",
    },
  };
  const videoQualityGuards = {
    product_fidelity: {
      1: "QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.",
      2: "QA+: один точный товар по исходнику; упаковка, этикетка, текст, цвет и пропорции неизменны в каждом кадре.",
    },
    technical_stability: {
      1: "QA: стабильный проход без чёрных кадров, скачков и мерцания.",
      2: "QA+: один непрерывный стабильный проход; без скачков, чёрных кадров, морфинга и мерцания.",
    },
    audio_quality: {
      1: "QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.",
      2: "QA+: непрерывная разборчивая дорожка; без тишины, клиппинга, шума и рассинхронизации.",
    },
    speech_fidelity: {
      1: "QA: реплика произносится дословно, без пропусков, замен и новых слов.",
      2: "QA+: произнести только точную реплику дословно; без пропусков, замен, повторов и новых слов.",
    },
    hook_clarity: {
      1: "QA: точный товар и одно действие видны в первые 2 секунды.",
      2: "QA+: точный товар — главный объект первого кадра; одно действие начинается в первые 2 секунды.",
    },
    visual_quality: {
      1: "QA: руки, лицо и фактуры без деформаций, дублей и мерцания.",
      2: "QA+: постоянные руки, лицо, упаковка и фактуры; без деформаций, дублей, швов и мерцания.",
    },
    trust: {
      1: "QA: естественная подача без гиперболы и новых обещаний.",
      2: "QA+: естественный свет, материалы и движение; без гиперболы, постановочного эффекта и новых обещаний.",
    },
    platform_fit: {
      1: "QA: мастер 9:16; товар и лицо в безопасных полях.",
      2: "QA+: вертикальный мастер 9:16; товар и лицо целиком остаются в безопасных полях.",
    },
  };
  const qualityGuardCodes = [...new Set([
    ...(policy?.applied ? policy.qualityGuardCodes : []),
    ...(repairPolicy?.applied ? repairPolicy.guardCodes : []),
  ])];
  const qualityDirections = qualityGuardCodes.map((code) => {
    const guardVariant = policy?.applied
      && policy.qualityGuardCodes.includes(code)
      ? policy.qualityGuardVariants[code] || 1
      : 1;
    return mode === REAL_PHOTO_MODE
      ? photoQualityGuards[code]?.[guardVariant]
      : ["audio_quality", "speech_fidelity"].includes(code)
        && mode !== REAL_SEEDANCE_MODE
      ? undefined
      : videoQualityGuards[code]?.[guardVariant];
  }).filter(Boolean);
  return [angleDirection, hookDirection, ...qualityDirections]
    .filter(Boolean)
    .join(" ");
}

export function inspectContentGenerationPrompt(
  prompt,
  mode,
  {
    productName = "",
    productCategory = "",
    avoidClaims = [],
    durationSeconds = null,
  } = {},
) {
  const promptLines = String(prompt ?? "").split(/\r?\n/u).map(cleanText).filter(Boolean);
  const normalized = cleanText(prompt);
  const normalizedMode = normalizeMode(mode);
  const normalizedDuration = contentGenerationDurationSeconds(
    normalizedMode,
    durationSeconds,
  );
  const blockers = [];
  const warnings = [];
  if (!normalized) {
    blockers.push({ code: "prompt_missing", message: "Промпт для генерации пуст." });
    return result(normalized, blockers, warnings);
  }
  if (normalized.length > CONTENT_GENERATION_PROMPT_LIMIT) {
    blockers.push({
      code: "prompt_too_long",
      message: `Промпт длиннее ${CONTENT_GENERATION_PROMPT_LIMIT} символов.`,
    });
  }
  if (productName && !normalized.toLocaleLowerCase("ru-RU").includes(
    cleanText(productName).toLocaleLowerCase("ru-RU"),
  )) {
    blockers.push({
      code: "product_identity_missing",
      message: "Верните в промпт точное название выбранного товара.",
    });
  }
  if (!normalized.includes("Сохрани форму, цвет, упаковку, этикетку и пропорции")) {
    blockers.push({
      code: "product_lock_missing",
      message: "Верните обязательную защиту формы и упаковки товара.",
    });
  }
  if (!normalized.includes("Не добавляй новые свойства, результаты, медицинские обещания")) {
    blockers.push({
      code: "claim_guard_missing",
      message: "Верните запрет на новые свойства и неподтверждённые обещания.",
    });
  }
  const claimSurface = promptLines
    .filter((line) => !/^не использовать\s*:/iu.test(line))
    .join(" ")
    .toLocaleLowerCase("ru-RU");
  const conflictingClaims = uniqueStrings(avoidClaims, 8).filter((claim) =>
    claimSurface.includes(claim.toLocaleLowerCase("ru-RU"))
  );
  if (conflictingClaims.length) {
    blockers.push({
      code: "forbidden_claim_present",
      message: `Удалите запрещённую формулировку: ${conflictingClaims.join("; ")}.`,
    });
  }
  if (normalizedMode === REAL_PHOTO_MODE) {
    if (!normalized.includes("Создай одно квадратное товарное фото 2048 × 2048")) {
      blockers.push({
        code: "photo_output_guard_missing",
        message: "Верните точный формат одного квадратного товарного фото 2048 × 2048.",
      });
    }
    if (!normalized.includes(
      `Используй @${CONTENT_GENERATION_PRODUCT_REFERENCE_TAG} как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали`,
    )) {
      blockers.push({
        code: "photo_reference_guard_missing",
        message: "Верните указание использовать главный кадр и дополнительные ракурсы только как референсы того же товара.",
      });
    }
    if (/(?:ролик[^.]{0,100}секунд|Реплика героя дословно)/iu.test(normalized)) {
      blockers.push({
        code: "photo_video_instructions_present",
        message: "Удалите из задания для фото длительность, ролик и реплику героя.",
      });
    }
  } else if (normalizedMode === REAL_SEEDANCE_MODE) {
    const interaction = inferProductInteractionProfile({
      productName,
      productCategory,
    });
    if (!normalized.includes(interaction.requirement)) {
      blockers.push({
        code: "product_interaction_guard_missing",
        message: "Верните безопасное действие с учётом реального размера товара.",
      });
    }
    if (!normalized.includes(
      `Создай один непрерывный вертикальный UGC-ролик длительностью ${normalizedDuration} секунд`,
    )) {
      blockers.push({
        code: "seedance_output_guard_missing",
        message: `Верните точный формат одного вертикального UGC-ролика на ${normalizedDuration} секунд.`,
      });
    }
    const match = /Реплика героя дословно:\s*«([^»]+)»/u.exec(normalized);
    if (!match) {
      blockers.push({
        code: "spoken_script_missing",
        message: "Укажите одну точную реплику в строке «Реплика героя дословно».",
      });
    } else {
      const spokenWords = words(match[1]).length;
      const spokenWordLimit = seedanceSpokenWordLimit(normalizedDuration);
      if (match[1].includes("[СОКРАТИТЕ") || spokenWords > spokenWordLimit) {
        blockers.push({
          code: "spoken_script_too_long",
          message: `Для ${normalizedDuration} секунд оставьте в точной реплике не больше ${spokenWordLimit} слов.`,
        });
      }
    }
    if (!normalized.includes(GENERATED_TEXT_GUARD)) {
      blockers.push({
        code: "generated_text_guard_missing",
        message: "Для Seedance верните запрет на сгенерированные надписи и субтитры.",
      });
    }
  } else {
    const interaction = inferProductInteractionProfile({
      productName,
      productCategory,
    });
    if (!normalized.includes(interaction.requirement)) {
      blockers.push({
        code: "product_interaction_guard_missing",
        message: "Верните безопасное действие с учётом реального размера товара.",
      });
    }
    if (!normalized.includes(
      `Создай один непрерывный вертикальный ролик длительностью ${normalizedDuration} секунд`,
    )) {
      blockers.push({
        code: "gen4_output_guard_missing",
        message: `Верните точный формат одного вертикального ролика Gen4 на ${normalizedDuration} секунд.`,
      });
    }
    if (!normalized.includes("Без речи, дикторского текста и сгенерированных надписей")) {
      blockers.push({
        code: "silent_mode_guard_missing",
        message: "Для 5-секундного Gen4 верните явный режим без речи и новых надписей.",
      });
    }
  }
  return result(normalized, blockers, warnings, { mode: normalizedMode });
}

export function inferProductInteractionProfile({
  productName = "",
  productCategory = "",
} = {}) {
  const normalizedName = cleanText(productName);
  const searchValue = normalizedName.toLocaleLowerCase("ru-RU");
  const category = cleanText(productCategory).toLocaleLowerCase("ru-RU");
  if (COUNTERTOP_PRODUCT_PATTERN.test(searchValue)) {
    const spokenSubject = countertopProductSpeechSubject(searchValue);
    return {
      kind: "countertop_appliance",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} товар показан целиком в естественном размере на устойчивой столешнице; герой взаимодействует с крышкой, панелью управления и готовым результатом.`,
      videoAction:
        "С первого кадра точный товар целиком стоит на устойчивой столешнице. Герой открывает крышку или рабочую часть, показывает управление и готовый результат; камера переходит от общего плана к деталям.",
      gen4Action:
        "С первого кадра показывай именно этот товар целиком на устойчивой столешнице. Камера спокойно переходит от общего плана к рабочей части и управлению; естественный размер товара сохраняется.",
      spokenLine:
        `Показываю, как работает ${spokenSubject}: управление, процесс и готовый результат.`,
    };
  }
  if (INSTALLED_PRODUCT_PATTERN.test(searchValue)) {
    return {
      kind: "installed_or_large",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} товар показан целиком в естественном размере на месте использования; герой взаимодействует с управлением или рабочей частью.`,
      videoAction:
        "С первого кадра точный товар виден целиком на месте использования. Герой показывает управление, рабочую часть и одну проверяемую функцию; камера переходит от общего плана к детали.",
      gen4Action:
        "С первого кадра показывай именно этот товар целиком на месте использования. Камера делает один спокойный проход от общего вида к рабочей детали, сохраняя естественный масштаб.",
      spokenLine:
        `Вот ${normalizedName || "товар"} на месте: масштаб, управление и рабочая деталь.`,
    };
  }
  if (category === "apparel") {
    return {
      kind: "wearable",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} товар показан надетым или разложенным в естественном масштабе; камера переходит от общего вида к материалу и деталям.`,
      videoAction:
        "С первого кадра точный товар виден целиком в естественном масштабе. Герой показывает посадку или материал, затем камера приближается к одной детали.",
      gen4Action:
        "С первого кадра показывай именно этот товар целиком в естественном масштабе. Один спокойный проход камеры переходит от общего вида к фактуре или детали.",
      spokenLine:
        "Показываю товар целиком, затем посадку и одну важную деталь крупно.",
    };
  }
  if (category === "cosmetics") {
    return {
      kind: "cosmetics",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} точная упаковка показана на столе или в руках на уровне корпуса; в кадре только дозатор, текстура и подтверждённые детали без демонстрации эффекта на лице.`,
      videoAction:
        "С первого кадра точная упаковка видна целиком на столе или в руках на уровне корпуса. Герой показывает дозатор, текстуру на тыльной стороне ладони или одну деталь упаковки без нанесения на лицо.",
      gen4Action:
        "С первого кадра показывай точную упаковку целиком на столе. Камера спокойно приближается к дозатору, текстуре или одной проверяемой детали.",
      spokenLine:
        "Показываю упаковку, дозатор и текстуру без обещаний результата.",
    };
  }
  if (category === "baa") {
    return {
      kind: "supplement",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} упаковка БАДа показана целиком на столе; в кадре этикетка и форма выпуска без сцены приёма и медицинских обещаний.`,
      videoAction:
        "С первого кадра точная упаковка БАДа целиком стоит на столе. Герой поворачивает её этикеткой к камере и показывает форму выпуска рядом с упаковкой, не принимая продукт.",
      gen4Action:
        "С первого кадра показывай точную упаковку БАДа целиком на столе. Камера спокойно приближается к этикетке и форме выпуска без сцены употребления.",
      spokenLine:
        "Показываю точную упаковку и форму выпуска; сведения проверяйте на этикетке.",
    };
  }
  if (category === "sports_food") {
    return {
      kind: "sports_food",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} точная упаковка спортивного питания показана на столе рядом с мерной порцией; в кадре только продукт и подтверждённые детали этикетки.`,
      videoAction:
        "С первого кадра точная упаковка целиком стоит на столе. Герой открывает крышку, показывает мерную ложку или готовую порцию рядом и возвращает упаковку этикеткой к камере.",
      gen4Action:
        "С первого кадра показывай точную упаковку целиком на столе. Камера спокойно переходит к крышке, мерной ложке и одной проверяемой детали этикетки.",
      spokenLine:
        "Показываю упаковку, мерную порцию и детали на этикетке без обещаний.",
    };
  }
  if (category === "food") {
    return {
      kind: "food",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} точная упаковка еды или напитка показана на столе рядом с естественной порцией; камера показывает фактуру без выдуманных свойств.`,
      videoAction:
        "С первого кадра точная упаковка целиком стоит на столе. Герой открывает её или сервирует одну естественную порцию рядом, затем показывает упаковку и фактуру продукта.",
      gen4Action:
        "С первого кадра показывай точную упаковку целиком на столе. Камера спокойно приближается к открытой упаковке, порции и фактуре продукта.",
      spokenLine:
        "Показываю упаковку, порцию и фактуру; состав проверяйте на этикетке.",
    };
  }
  if (category === "household") {
    return {
      kind: "household_cold_start",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} товар для дома показан целиком в естественном размере на устойчивой поверхности; герой демонстрирует одну видимую рабочую часть и понятное безопасное действие.`,
      videoAction:
        "С первого кадра точный товар для дома целиком стоит на устойчивой поверхности. Герой показывает одну рабочую часть и одно безопасное действие, не поднимая крупный корпус.",
      gen4Action:
        "С первого кадра показывай точный товар для дома целиком на устойчивой поверхности. Камера спокойно приближается к одной рабочей части.",
      spokenLine:
        "Показываю товар в реальном масштабе и одну рабочую деталь.",
    };
  }
  if (category === "electronics") {
    return {
      kind: "electronics",
      requirement:
        `${PRODUCT_INTERACTION_PREFIX} устройство показано целиком на столе или рабочем месте; камера переходит к интерфейсу, управлению и видимым разъёмам без выдуманных функций.`,
      videoAction:
        "С первого кадра точное устройство целиком стоит на рабочем месте. Герой показывает включение, один элемент управления и разъём или экран без изменения масштаба.",
      gen4Action:
        "С первого кадра показывай точное устройство целиком на рабочем месте. Камера спокойно приближается к управлению, экрану или разъёму.",
      spokenLine:
        "Показываю устройство, управление и одну проверяемую деталь.",
    };
  }
  return {
    kind: category === "other" ? "other_cold_start" : "unclassified_cold_start",
    requirement:
      `${PRODUCT_INTERACTION_PREFIX} товар целиком в естественном масштабе на устойчивой поверхности; камера показывает только видимые детали.`,
    videoAction:
      "С первого кадра точный товар целиком стоит на нейтральной устойчивой поверхности. Без человека: камера спокойно приближается к одной видимой детали, не меняя форму и масштаб товара.",
    gen4Action:
      "С первого кадра показывай именно этот товар целиком на нейтральной устойчивой поверхности. Без человека: один спокойный проход камеры приближается к одной видимой детали.",
    spokenLine:
      "Показываю точный товар целиком и одну видимую деталь без предположений.",
  };
}

function countertopProductSpeechSubject(value) {
  if (/(?:пароварк|steamer)/iu.test(value)) return "пароварка";
  if (/мультиварк/iu.test(value)) return "мультиварка";
  if (/(?:аэрогрил|air\s*fryer)/iu.test(value)) return "аэрогриль";
  if (/(?:кофемашин|coffee\s*machine)/iu.test(value)) return "кофемашина";
  if (/кофеварк/iu.test(value)) return "кофеварка";
  if (/микроволнов|microwave/iu.test(value)) return "микроволновая печь";
  if (/тостер/iu.test(value)) return "тостер";
  if (/соковыжимал/iu.test(value)) return "соковыжималка";
  if (/хлебопеч/iu.test(value)) return "хлебопечь";
  if (/блендер/iu.test(value)) return "блендер";
  if (/комбайн/iu.test(value)) return "кухонный комбайн";
  return "кухонный прибор";
}

function generationActionFitsProduct(action, interaction) {
  const normalized = cleanText(action);
  if (!normalized) return false;
  if (/(?:у|рядом\s+с|возле)\s+лиц|к\s+лицу|поднос\p{L}*\s+к\s+(?:камер|лиц)/iu.test(normalized)) {
    return false;
  }
  if (
    ["countertop_appliance", "installed_or_large"].includes(interaction.kind)
    && /(?:держ\p{L}*\s+(?:в\s+рук|товар)|подним\p{L}*\s+(?:корпус|товар)|бер\p{L}*\s+в\s+рук)/iu.test(normalized)
  ) {
    return false;
  }
  return true;
}

function validHandoff(value, now = Date.now()) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  if (value.version !== CONTENT_GENERATION_HANDOFF_VERSION) return false;
  const createdAt = Number(value.createdAt);
  const current = Number(now);
  if (
    !Number.isFinite(createdAt) || !Number.isFinite(current) ||
    createdAt > current + 60_000 || current - createdAt > HANDOFF_MAX_AGE_MS
  ) return false;
  if (
    !cleanText(value.researchId) || !cleanText(value.draftId) ||
    !cleanText(value.productName) || !cleanText(value.sku) ||
    !UUID_PATTERN.test(cleanText(value.projectId).toLowerCase())
  ) return false;
  if (!value.scenario || typeof value.scenario !== "object") return false;
  if (!Number.isInteger(value.scenario.position) || value.scenario.position < 1 || value.scenario.position > 3) {
    return false;
  }
  if (!cleanText(value.scenario.title)) return false;
  if (
    value.scenario.recommendedGenerationMode
    && !normalizeRecommendedGenerationMode(
      value.scenario.recommendedGenerationMode,
    )
  ) return false;
  if (cleanText(value.scenario.generationModeReason).length > 400) {
    return false;
  }
  if (
    !value.creativeBrief || typeof value.creativeBrief !== "object" ||
    Array.isArray(value.creativeBrief) ||
    !Array.isArray(value.creativeBrief.proofPoints) ||
    !Array.isArray(value.creativeBrief.avoidClaims)
  ) return false;
  return true;
}

function fitPrompt(items, maximum) {
  const active = items.filter((item) => item.text);
  const render = () => active.map((item) => item.text).join("\n");
  while (render().length > maximum) {
    const index = active.map((item) => item.required).lastIndexOf(false);
    if (index < 0) return "";
    active.splice(index, 1);
  }
  return render();
}

function required(text) {
  return { text: cleanText(text), required: true };
}

function optional(text) {
  return { text: cleanText(text), required: false };
}

function result(prompt, blockers, warnings, details = {}) {
  return {
    prompt,
    ready: blockers.length === 0,
    blockers,
    warnings,
    ...details,
  };
}

function words(value) {
  return cleanText(value).match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || [];
}

function safeScenarioSpokenLine({
  scenarioIntent = "",
  explicitSpokenLine = "",
  productName = "",
  fallback = "",
  durationSeconds = 8,
} = {}) {
  const normalizedIntent = cleanText(scenarioIntent).toLocaleLowerCase("ru-RU");
  const normalizedProduct = cleanText(productName).toLocaleLowerCase("ru-RU");
  const exactLine = cleanText(explicitSpokenLine)
    || extractExplicitSpokenLine(scenarioIntent);
  let candidate = exactLine || cleanText(fallback);
  if (
    !exactLine &&
    /(?:пароварк|steamer)/iu.test(normalizedProduct)
    && /(?:готов\p{L}*\s+на\s+пар|без\s+жарк|лишн\p{L}*\s+масл|лосос)/iu.test(normalizedIntent)
  ) {
    candidate = /лосос/iu.test(normalizedIntent)
      ? "Готовлю лосось с овощами на пару: без жарки и лишнего масла, равномерно и удобно."
      : "Готовлю на пару без жарки и лишнего масла: равномерно, просто и удобно.";
  }
  const maximum = seedanceSpokenWordLimit(durationSeconds);
  return words(candidate).length <= maximum
    ? candidate
    : words(candidate).slice(0, maximum).join(" ");
}

function extractExplicitSpokenLine(value) {
  const match = EXPLICIT_SPOKEN_LINE_PATTERN.exec(cleanText(value));
  return cleanText(match?.[3]);
}

function removeExplicitSpokenLine(value) {
  return cleanText(value)
    .replace(EXPLICIT_SPOKEN_LINE_PATTERN, "$1")
    .replace(/\s+([.!?…])/gu, "$1")
    .trim();
}

function truncateScenarioIntent(value, maximum) {
  const normalized = cleanText(value);
  const limit = Math.max(1, Number(maximum) || 1);
  if (normalized.length <= limit) return normalized;

  const candidate = normalized.slice(0, limit + 1);
  let sentenceEnd = -1;
  for (const match of candidate.matchAll(/[.!?…](?=\s|$)/gu)) {
    sentenceEnd = match.index;
  }
  if (sentenceEnd >= Math.floor(limit * 0.45)) {
    return candidate.slice(0, sentenceEnd + 1).trim();
  }

  const wordBoundary = candidate.slice(0, limit).search(/\s+\S*$/u);
  const wholeWords = wordBoundary > 0
    ? candidate.slice(0, wordBoundary).trim()
    : candidate.slice(0, limit).trim();
  return `${wholeWords.replace(/[,:;–—-]+$/u, "")}…`;
}

function lines(value, maximum) {
  const source = Array.isArray(value) ? value : String(value || "").split(/\r?\n/u);
  return source.map(cleanText).filter(Boolean).slice(0, maximum);
}

function uniqueStrings(value, maximum) {
  const source = Array.isArray(value) ? value : [];
  return [...new Set(source.map(cleanText).filter(Boolean))].slice(0, maximum);
}

function cleanText(value) {
  return String(value ?? "").replace(/\s+/gu, " ").trim();
}

function withTerminalPunctuation(value) {
  const normalized = cleanText(value);
  return /[.!?…]$/u.test(normalized) ? normalized : `${normalized}.`;
}

function cleanMultiline(value) {
  return String(value ?? "")
    .split(/\r?\n/u)
    .map(cleanText)
    .filter(Boolean)
    .join("\n");
}

function photoScenarioVisualDirection(handoff) {
  const sharedDirection = cleanText(
    handoff?.creativeBrief?.visualDirection,
  ).slice(0, 240);
  const composition = lines(handoff?.scenario?.shotList, 3)
    .map((line) => cleanPhotoCompositionLine(line))
    .filter(Boolean);
  const scenarioDirection = composition.length
    ? `Композиция одного кадра: ${composition.map((line, index) =>
      `${index + 1}) ${line}`
    ).join("; ")}`
    : "";
  return [sharedDirection, scenarioDirection]
    .filter(Boolean)
    .join(". ")
    .slice(0, 620);
}

function cleanPhotoCompositionLine(value) {
  return cleanText(value)
    .replace(/^(?:один кадр|\d+(?:[.,]\d+)?(?:\s*[-–—]\s*\d+(?:[.,]\d+)?)?\s*(?:с|секунд[а-я]*)?)\s*:\s*/iu, "")
    .replace(/\s+Голос:\s*[^.]*\.?/giu, " ")
    .replace(/\s+Текст:\s*[^.]*\.?/giu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 220);
}

function normalizeMode(value) {
  if (value === REAL_PHOTO_MODE) return REAL_PHOTO_MODE;
  return value === REAL_GEN4_MODE ? REAL_GEN4_MODE : REAL_SEEDANCE_MODE;
}

function normalizeRecommendedGenerationMode(value) {
  return [REAL_PHOTO_MODE, REAL_GEN4_MODE, REAL_SEEDANCE_MODE].includes(value)
    ? value
    : "";
}

function normalizePlatform(value) {
  const normalized = cleanText(value).toLocaleLowerCase("ru-RU");
  if (normalized.includes("youtube")) return "youtube";
  if (normalized.includes("vk") || normalized.includes("вк")) return "vk";
  if (normalized.includes("tiktok") || normalized.includes("тик")) return "tiktok";
  if (normalized.includes("telegram")) return "telegram";
  if (normalized.includes("wildberries")) return "wildberries";
  return "instagram";
}
