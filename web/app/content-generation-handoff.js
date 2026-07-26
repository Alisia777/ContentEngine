export const CONTENT_GENERATION_HANDOFF_VERSION = 1;
export const CONTENT_GENERATION_PROMPT_LIMIT = 1_200;
export const SEEDANCE_SPOKEN_WORD_LIMIT = 22;
export const CONTENT_GENERATION_PRODUCT_REFERENCE_TAG = "ProductReference";
export const GENERATION_LEARNING_COMPILER_VERSION = "safe-brief-v4";

const HANDOFF_MAX_AGE_MS = 24 * 60 * 60 * 1_000;
const REAL_GEN4_MODE = "real_gen4";
const REAL_SEEDANCE_MODE = "real_seedance";
const REAL_PHOTO_MODE = "real_photo";

export function createContentGenerationHandoff(record, scenarioIndex, now = Date.now()) {
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
  if (!productName || !sku || !researchId || !draftId) {
    throw new Error("У утверждённого ТЗ не хватает связи с товаром или исследованием.");
  }

  const brief = record?.brief && typeof record.brief === "object"
    ? record.brief
    : {};
  return {
    version: CONTENT_GENERATION_HANDOFF_VERSION,
    createdAt: Number(now),
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

export function compileContentGenerationPrompt(handoff, mode, learningPolicy = null) {
  if (!validHandoff(handoff, handoff?.createdAt)) {
    return result("", [{
      code: "handoff_invalid",
      message: "Связь со сценарием повреждена. Вернитесь в разбор товара.",
    }], []);
  }

  const normalizedMode = normalizeMode(mode);
  if (normalizedMode === REAL_PHOTO_MODE) {
    return compileSafeGenerationBrief({
      mode: normalizedMode,
      productName: handoff.productName,
      sku: handoff.sku,
      visualDirection: handoff.creativeBrief?.visualDirection,
      avoidClaims: handoff.creativeBrief?.avoidClaims,
      learningPolicy,
    });
  }
  const seedance = normalizedMode === REAL_SEEDANCE_MODE;
  const gen4 = normalizedMode === REAL_GEN4_MODE;
  const durationSeconds = gen4 ? 5 : 8;
  const scenario = handoff.scenario;
  const brief = handoff.creativeBrief;
  const shotLines = lines(scenario.shotList, seedance ? 3 : 1);
  const action = shotLines.join(" Затем ");
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
      message: "Для 8-секундного ролика с голосом нужна точная реплика героя.",
    });
  }
  if (seedance && spokenWords > SEEDANCE_SPOKEN_WORD_LIMIT) {
    blockers.push({
      code: "spoken_script_too_long",
      message: `Реплика содержит ${spokenWords} слов. Для 8 секунд оставьте не больше ${SEEDANCE_SPOKEN_WORD_LIMIT}.`,
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
  if (shotLines.length > (gen4 ? 1 : 2)) {
    warnings.push({
      code: "shot_plan_dense",
      message: `Для ${durationSeconds} секунд лучше оставить ${gen4 ? "одно действие" : "не больше двух действий"}.`,
    });
  }

  const spokenLine = seedance
    ? spokenWords <= SEEDANCE_SPOKEN_WORD_LIMIT
      ? `Реплика героя дословно: «${scenario.spokenScript}»`
      : `Реплика героя дословно: «[СОКРАТИТЕ РЕПЛИКУ ДО ${SEEDANCE_SPOKEN_WORD_LIMIT} СЛОВ]»`
    : "Без речи, дикторского текста и сгенерированных надписей.";
  const promptLines = [
    required(`Создай один непрерывный вертикальный ${seedance ? "UGC-" : ""}ролик длительностью ${durationSeconds} секунд.`),
    required(`Точный товар: ${handoff.productName}, артикул ${handoff.sku}.`),
    optional(`Хук: ${scenario.hook}.`),
    required(`Действие в кадре: ${action || "[ДОБАВЬТЕ ОДНО ПОНЯТНОЕ ДЕЙСТВИЕ]"}.`),
    required(spokenLine),
    optional(brief.visualDirection ? `Визуальное направление: ${brief.visualDirection}.` : ""),
    optional(brief.keyMessage ? `Главная мысль: ${brief.keyMessage}.` : ""),
    optional(brief.proofPoints.length ? `Разрешённые доказательства: ${brief.proofPoints.join("; ")}.` : ""),
    optional(brief.cta ? `CTA: ${brief.cta}.` : ""),
    required("С первого кадра показывай именно этот товар. Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений."),
    required("Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара."),
    optional(brief.avoidClaims.length ? `Не использовать: ${brief.avoidClaims.join("; ")}.` : ""),
    required(generationLearningDirection(learningPolicy, normalizedMode)),
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
  });
  for (const blocker of inspection.blockers) {
    if (!blockers.some((item) => item.code === blocker.code)) blockers.push(blocker);
  }
  for (const warning of inspection.warnings) {
    if (!warnings.some((item) => item.code === warning.code)) warnings.push(warning);
  }
  return result(prompt, blockers, warnings, {
    durationSeconds,
    spokenWords,
    mode: normalizedMode,
  });
}

export function compileSafeGenerationBrief({
  mode,
  productName,
  sku,
  visualDirection = "",
  avoidClaims = [],
  learningPolicy = null,
} = {}) {
  const normalizedMode = normalizeMode(mode);
  const exactProductName = cleanText(productName);
  const exactSku = cleanText(sku);
  const safeVisualDirection = cleanText(visualDirection);
  const safeAvoidClaims = uniqueStrings(avoidClaims, 8);
  const learningDirection = generationLearningDirection(
    learningPolicy,
    normalizedMode,
  );
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
        : normalizedMode === REAL_GEN4_MODE ? 5 : 8,
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
      required(`Используй @${CONTENT_GENERATION_PRODUCT_REFERENCE_TAG} как единственный точный референс товара. ${identityLine}`),
      required("Студийное фото: один товар целиком по центру, нейтральный фон, мягкий свет, естественная тень, высокая детализация."),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      required("Товар — единственный главный объект; оставь безопасные поля по краям."),
      required(productLock),
      required(claimGuard),
      required("Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса."),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  } else if (normalizedMode === REAL_GEN4_MODE) {
    durationSeconds = 5;
    promptLines = [
      required("Создай один непрерывный вертикальный ролик длительностью 5 секунд."),
      required(identityLine),
      required("С первого кадра показывай именно этот товар. Один спокойный проход камеры: медленно приблизься к неподвижной упаковке, удерживая товар целиком и в резком фокусе."),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      required("Без речи, дикторского текста и сгенерированных надписей."),
      required(productLock),
      required(claimGuard),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  } else {
    durationSeconds = 8;
    const spokenLine = "Показываю точный товар крупно: смотрите упаковку и детали, а характеристики проверяйте в карточке.";
    spokenWords = words(spokenLine).length;
    promptLines = [
      required("Создай один непрерывный вертикальный UGC-ролик длительностью 8 секунд."),
      required(identityLine),
      required("С первого кадра герой держит точный товар у лица, затем приближает упаковку к камере и возвращает в центр."),
      required(`Реплика героя дословно: «${spokenLine}»`),
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
    "hook_clarity",
    "visual_quality",
    "trust",
    "platform_fit",
  ]);
  const preferredAngle = cleanText(value.preferred_angle);
  const policyHash = cleanText(value.policy_hash);
  const selectionMode = [
    "performance",
    "quality",
    "bounded_exploration",
  ].includes(
    cleanText(value.selection_mode),
  )
    ? cleanText(value.selection_mode)
    : "performance";
  const applied = value.applied === true
    && ["medium", "high"].includes(value.confidence)
    && allowedAngles.has(preferredAngle)
    && /^[0-9a-f]{64}$/u.test(policyHash);
  return {
    version: cleanText(value.version),
    applied,
    confidence: ["none", "low", "medium", "high"].includes(value.confidence)
      ? value.confidence
      : "none",
    evidenceCount: Number.isInteger(Number(value.evidence_count))
      ? Math.max(0, Number(value.evidence_count))
      : 0,
    preferredAngle: applied ? preferredAngle : "",
    avoidAngle: allowedAngles.has(cleanText(value.avoid_angle))
      ? cleanText(value.avoid_angle)
      : "",
    preferredHookPatterns: uniqueStrings(
      value.preferred_hook_patterns,
      4,
    ).filter((pattern) => allowedPatterns.has(pattern)),
    qualityGuardCodes: applied
      ? uniqueStrings(value.quality_guard_codes, 3)
        .filter((code) => allowedQualityGuards.has(code))
      : [],
    qualityGuardEvidenceCount: Number.isInteger(
      Number(value.quality_guard_evidence_count),
    )
      ? Math.max(0, Number(value.quality_guard_evidence_count))
      : 0,
    qualityGuardConfidence: ["none", "low", "medium", "high"].includes(
      value.quality_guard_confidence,
    )
      ? value.quality_guard_confidence
      : "none",
    selectionMode,
    reasonCodes: uniqueStrings(value.reason_codes, 8),
    scope: cleanText(value.scope),
    policyHash,
  };
}

function generationLearningDirection(value, mode) {
  const policy = normalizeGenerationLearningPolicy(value);
  if (!policy?.applied) return "";
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
  const angleDirection = mode === REAL_PHOTO_MODE
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
  const hookDirection = mode === REAL_PHOTO_MODE
    ? ""
    : hookDirections[policy.preferredHookPatterns[0]] || "";
  const photoQualityGuards = {
    product_fidelity: "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
    technical_stability: "QA: резкий товар, ровный свет, без пересвета и размытия.",
    hook_clarity: "QA: товар считывается первым.",
    visual_quality: "QA: чистые края без дублей, деформаций и AI-артефактов.",
    trust: "QA: естественные материалы, свет и масштаб.",
    platform_fit: "QA: мастер 1:1, безопасные поля.",
  };
  const videoQualityGuards = {
    product_fidelity: "QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.",
    technical_stability: "QA: стабильный проход без чёрных кадров, скачков и мерцания.",
    hook_clarity: "QA: точный товар и одно действие видны в первые 2 секунды.",
    visual_quality: "QA: руки, лицо и фактуры без деформаций, дублей и мерцания.",
    trust: "QA: естественная подача без гиперболы и новых обещаний.",
    platform_fit: "QA: мастер 9:16; товар и лицо в безопасных полях.",
  };
  const qualityDirections = policy.qualityGuardCodes.map((code) => (
    mode === REAL_PHOTO_MODE
      ? photoQualityGuards[code]
      : videoQualityGuards[code]
  )).filter(Boolean);
  return [angleDirection, hookDirection, ...qualityDirections]
    .filter(Boolean)
    .join(" ");
}

export function inspectContentGenerationPrompt(
  prompt,
  mode,
  { productName = "", avoidClaims = [] } = {},
) {
  const promptLines = String(prompt ?? "").split(/\r?\n/u).map(cleanText).filter(Boolean);
  const normalized = cleanText(prompt);
  const normalizedMode = normalizeMode(mode);
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
      `Используй @${CONTENT_GENERATION_PRODUCT_REFERENCE_TAG} как единственный точный референс товара`,
    )) {
      blockers.push({
        code: "photo_reference_guard_missing",
        message: "Верните указание использовать выбранный исходник как единственный точный референс.",
      });
    }
    if (/(?:ролик[^.]{0,100}секунд|Реплика героя дословно)/iu.test(normalized)) {
      blockers.push({
        code: "photo_video_instructions_present",
        message: "Удалите из задания для фото длительность, ролик и реплику героя.",
      });
    }
  } else if (normalizedMode === REAL_SEEDANCE_MODE) {
    const match = /Реплика героя дословно:\s*«([^»]+)»/u.exec(normalized);
    if (!match) {
      blockers.push({
        code: "spoken_script_missing",
        message: "Укажите одну точную реплику в строке «Реплика героя дословно».",
      });
    } else {
      const spokenWords = words(match[1]).length;
      if (match[1].includes("[СОКРАТИТЕ") || spokenWords > SEEDANCE_SPOKEN_WORD_LIMIT) {
        blockers.push({
          code: "spoken_script_too_long",
          message: `Для 8 секунд оставьте в точной реплике не больше ${SEEDANCE_SPOKEN_WORD_LIMIT} слов.`,
        });
      }
    }
  } else if (!normalized.includes("Без речи, дикторского текста и сгенерированных надписей")) {
    blockers.push({
      code: "silent_mode_guard_missing",
      message: "Для 5-секундного Gen4 верните явный режим без речи и новых надписей.",
    });
  }
  return result(normalized, blockers, warnings, { mode: normalizedMode });
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
    !cleanText(value.productName) || !cleanText(value.sku)
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

function cleanMultiline(value) {
  return String(value ?? "")
    .split(/\r?\n/u)
    .map(cleanText)
    .filter(Boolean)
    .join("\n");
}

function normalizeMode(value) {
  if (value === REAL_PHOTO_MODE) return REAL_PHOTO_MODE;
  return value === REAL_GEN4_MODE ? REAL_GEN4_MODE : REAL_SEEDANCE_MODE;
}

function normalizeRecommendedGenerationMode(value) {
  return [REAL_GEN4_MODE, REAL_SEEDANCE_MODE].includes(value)
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
