export const CONTENT_GENERATION_HANDOFF_VERSION = 5;
export const CONTENT_GENERATION_PROMPT_LIMIT = 1_200;
export const SEEDANCE_SPOKEN_WORD_LIMIT = 22;
export const CONTENT_GENERATION_PRODUCT_REFERENCE_TAG = "ProductReference";
export const GENERATION_LEARNING_COMPILER_VERSION = "safe-brief-v7";
export const GENERATION_REPAIR_COMPILER_VERSION = "review-repair-v1";
export const GENERATION_VIDEO_REFERENCE_PROMPT_MARKER =
  "GenerationVideoReference/operator-summary:";
export const GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER =
  "ИИ исходный ролик не просматривал.";
export const GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE =
  "generation_video_reference_marker_invalid";
export const AI_RESEARCH_PROVIDER_FRAGMENT_VERSION =
  "ai-research-provider-fragment-v1";
export const AI_RESEARCH_PROVIDER_FRAGMENT_MARKER = "AIResearchSelection/v1";
export const AI_RESEARCH_HUMAN_INTENT_MARKER = "AIResearchHumanIntent/v1";

const HANDOFF_MAX_AGE_MS = 24 * 60 * 60 * 1_000;
const REAL_GEN4_MODE = "real_gen4";
const REAL_SEEDANCE_MODE = "real_seedance";
const REAL_PHOTO_MODE = "real_photo";
const GENERATED_TEXT_GUARD =
  "Без сгенерированных надписей, субтитров и декоративного текста.";
export const SEEDANCE_RUSSIAN_DICTION_GUARD =
  "Русская дикция: чётко, без акцента/лишних гласных; все слова/окончания; числа/градусы/названия точно; чёткие паузы.";
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
const AI_RESEARCH_PROVIDER_FRAGMENT_LIMIT = 240;
const AI_RESEARCH_HUMAN_INTENT_LIMIT = 150;
const AI_RESEARCH_BRIEF_SECTION_PATTERN = /^(ТОВАР|КОНЦЕПЦИЯ|ХУК|КЛЮЧЕВОЕ СООБЩЕНИЕ|АУДИТОРИЯ|РЕПЛИКА \/ СЮЖЕТ|КАДРЫ|ВИЗУАЛ|CTA|ДОКАЗАТЕЛЬСТВА|НЕ ОБЕЩАТЬ \/ УЧЕСТЬ):[ \t\f\v]*(.*)$/iu;
const AI_RESEARCH_HUMAN_SECTION_KEYS = Object.freeze([
  ["КОНЦЕПЦИЯ", "C", 16],
  ["ХУК", "H", 16],
  ["CTA", "CTA", 24],
  ["ДОКАЗАТЕЛЬСТВА", "P", 16],
  ["НЕ ОБЕЩАТЬ / УЧЕСТЬ", "A", 20],
]);
const AI_RESEARCH_SPOKEN_SECTION = "РЕПЛИКА / СЮЖЕТ";
const AI_RESEARCH_SPOKEN_SECTION_TOKEN_PATTERN =
  /РЕПЛИКА\p{White_Space}*\/\p{White_Space}*СЮЖЕТ\p{White_Space}*:/iu;
const AI_RESEARCH_SPOKEN_SECTION_TOKEN_GLOBAL_PATTERN =
  /РЕПЛИКА\p{White_Space}*\/\p{White_Space}*СЮЖЕТ\p{White_Space}*:/giu;
const AI_RESEARCH_SPOKEN_WRAPPER_PATTERN =
  /(?:^|[.!?…]\p{White_Space}+)(?:(?:герой|блогер|ведущ(?:ий|ая)|человек)\p{White_Space}+(?:говорит|произносит|рассказывает)|реплика\p{White_Space}+героя(?:\p{White_Space}+дословно)?)\p{White_Space}*:/iu;
const PROMPT_SPOKEN_DIRECTIVE_PATTERN =
  /(?:(?:(?:герой|блогер|ведущ(?:ий|ая)|человек)\p{White_Space}+(?:говорит|произносит|рассказывает)|реплика\p{White_Space}+героя(?:\p{White_Space}+дословно)?)\p{White_Space}*:|РЕПЛИКА\p{White_Space}*\/\p{White_Space}*СЮЖЕТ\p{White_Space}*:)/giu;
const AI_RESEARCH_SPOKEN_CONTROL_PATTERN = /[\u0000-\u001f\u007f-\u009f]/u;
const AI_RESEARCH_RAW_UNSAFE_CONTROL_PATTERN =
  /[\u0000-\u0009\u000b\u000c\u000e-\u001f\u007f-\u009f]/u;
const AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN =
  /\p{Default_Ignorable_Code_Point}/u;
const AI_RESEARCH_SPOKEN_NON_ASCII_WHITESPACE_PATTERN = /[^\S ]/u;
const AI_RESEARCH_SPOKEN_QUOTATION_MARK_PATTERN = /\p{Quotation_Mark}/u;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const EXPLICIT_SPOKEN_LINE_PATTERN =
  /(^|[.!?…]\s+)((?:(?:герой|блогер|ведущ(?:ий|ая)|человек)\s+(?:говорит|произносит|рассказывает)|реплика\s+героя(?:\s+дословно)?))\s*:\s*[«“"]([^»”"]{2,500})[»”"]\s*[.!?…]?/iu;
const EXTERNAL_REFERENCE_PATTERN =
  /(?:\b(?:https?|ftp|file|data|mailto|javascript|blob|ipfs|s3|gs|tel|urn):(?=\/\/|\S)|(?:^|[^\p{L}\p{N}_-])www\.|(?:^|[^\p{L}\p{N}_-])(?:\d{1,3}\.){3}\d{1,3}(?=[:/?#]|$|[^\p{L}\p{N}_.-])|(?:^|[^\p{L}\p{N}_-])(?:[\p{L}\p{N}-]+\.)+(?:com|org|net|edu|gov|io|ai|app|dev|co|me|tv|info|biz|xyz|online|site|shop|store|tech|ru|рф|su|ua|by|kz|[a-z]{2}|xn--[a-z0-9-]{2,59})(?=[:/?#]|$|[^\p{L}\p{N}_-])|(?:^|[^\p{L}\p{N}_-])(?:[\p{L}\p{N}-]+\.)+[\p{L}a-z]{2,24}(?=[:/?#]))/iu;
const RESEARCH_CATEGORY_MATURITIES = new Set([
  "emerging", "growing", "established", "saturated", "unknown",
]);
const RESEARCH_COMPETITOR_COVERAGES = new Set([
  "none", "limited", "sufficient",
]);
const RESEARCH_CATEGORY_STRUCTURAL_SIGNALS = new Set([
  "hook.problem_first",
  "hook.result_first",
  "format.single_action_demo",
  "format.step_by_step",
  "format.comparison",
  "format.unboxing",
  "format.creator_explainer",
  "proof.product_in_use",
  "proof.before_after",
  "proof.social_proof",
  "offer.bundle",
  "offer.price_anchor",
  "channel.marketplace_native_video",
  "channel.short_vertical_video",
]);

export function inspectGenerationVideoReferencePromptFragment(value = "") {
  const fragment = cleanText(value);
  if (!fragment) {
    return { present: false, ready: true, code: "", fragment: "" };
  }
  const prefix = `${GENERATION_VIDEO_REFERENCE_PROMPT_MARKER} `;
  const suffix = `. ${GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER}`;
  const markerCount = fragment.split(
    GENERATION_VIDEO_REFERENCE_PROMPT_MARKER,
  ).length - 1;
  const mechanicsSummary = fragment.startsWith(prefix)
    && fragment.endsWith(suffix)
    ? fragment.slice(prefix.length, -suffix.length)
    : "";
  const canonicalFragment = mechanicsSummary
    ? `${prefix}${mechanicsSummary}${suffix}`
    : "";
  const ready = markerCount === 1
    && mechanicsSummary.length >= 20
    && mechanicsSummary.length <= 360
    && !EXTERNAL_REFERENCE_PATTERN.test(mechanicsSummary)
    && !mechanicsSummary.includes(GENERATION_VIDEO_REFERENCE_PROMPT_MARKER)
    && fragment === canonicalFragment;
  return {
    present: true,
    ready,
    code: ready ? "" : GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE,
    fragment,
    mechanics_summary: mechanicsSummary,
    marker_count: markerCount,
  };
}

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

export function contentGenerationPromptLimit(mode) {
  return normalizeMode(mode) === REAL_GEN4_MODE
    ? 1_000
    : CONTENT_GENERATION_PROMPT_LIMIT;
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

function exactSpokenWordLimit(durationSeconds) {
  const duration = Number(durationSeconds);
  return Math.max(
    10,
    Math.min(42, Math.floor(duration * SEEDANCE_SPOKEN_WORD_LIMIT / 8)),
  );
}

function normalizeGenerationPromptSelection(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const provider = cleanText(value.provider).toLowerCase();
  const model = cleanText(value.model);
  const format = cleanText(value.format);
  const durationSeconds = Number(value.durationSeconds);
  const promptLimit = Number(value.promptLimit);
  const identity = `${provider}:${model}`;
  if (
    !new Set(["runway", "google"]).has(provider)
    || !new Set([
      "runway:gen4.5",
      "runway:seedance2_mini",
      "runway:veo3.1_fast",
      "runway:gemini_omni_flash",
      "google:veo-3.1-lite-generate-preview",
    ]).has(identity)
    || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(model)
    || !/^\d{1,4}:\d{1,4}$/u.test(format)
    || !Number.isSafeInteger(durationSeconds)
    || durationSeconds < 1
    || durationSeconds > 60
    || !Number.isSafeInteger(promptLimit)
    || promptLimit < 1
    || promptLimit > 100_000
    || typeof value.audio !== "boolean"
  ) return null;
  return Object.freeze({
    provider,
    model,
    format,
    durationSeconds,
    promptLimit,
    audio: value.audio,
  });
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
  const researchDecision = generationResearchDecision(
    record?.stageCorrections
      || brief.stageCorrections
      || brief.human_stage_corrections,
  );
  const researchGuidanceStatus = cleanText(record?.guidance?.status);
  if (
    researchGuidanceStatus
    && researchGuidanceStatus !== "ready_for_brief"
    && !researchDecision
  ) {
    throw new Error("Сначала зафиксируйте решение по пробелам исследования.");
  }
  const scenarioPlatform = normalizePlatform(scenario.platform);
  if (!scenarioPlatform) {
    throw new Error(
      "Исследование Ozon можно утвердить и передать в задачи, но платная автогенерация для Ozon пока не подключена.",
    );
  }
  const requiresResearchCategoryRule = hasModernResearchCategoryAnalysis(record);
  return {
    version: CONTENT_GENERATION_HANDOFF_VERSION,
    createdAt: Number(now),
    projectId: normalizedProjectId,
    researchId,
    draftId,
    productName,
    sku,
    sourceIds: uniqueStrings(record?.sourceIds, 24),
    researchGuidanceStatus,
    researchDecision,
    requiresResearchCategoryRule,
    researchCategoryBinding: normalizedResearchCategoryBinding(
      record,
      requiresResearchCategoryRule,
    ),
    researchCategoryPolicy: requiresResearchCategoryRule
      ? boundedResearchCategoryPolicy(record?.rawBrief)
      : null,
    scenario: {
      position: normalizedIndex + 1,
      title: cleanText(scenario.title) || `Сценарий ${normalizedIndex + 1}`,
      platform: scenarioPlatform,
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

  if (
    handoff.requiresResearchCategoryRule
    && !handoff.researchCategoryBinding
  ) {
    return result("", [{
      code: "research_category_binding_required",
      message: "Обновите привязку категории из утверждённого исследования перед генерацией.",
    }], []);
  }

  const normalizedMode = normalizeMode(mode);
  const researchCategoryRule = generationResearchCategorySignal(handoff);
  const researchCategoryRuleFragment = generationResearchCategoryRuleFragment(
    researchCategoryRule,
  );
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
      researchDecision: handoff.researchDecision,
      researchCategoryRule,
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
  const researchDecision = cleanResearchDecision(handoff.researchDecision);
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
    required(researchDecision
      ? `Решение пользователя после исследования — имеет приоритет над исходным сценарием: ${researchDecision}.`
      : ""),
    required(researchCategoryRuleFragment),
    optional(`Хук: ${scenario.hook}.`),
    required(`Действие в кадре: ${action || "[ДОБАВЬТЕ ОДНО ПОНЯТНОЕ ДЕЙСТВИЕ]"}.`),
    required(interaction.requirement),
    required(spokenLine),
    required(
      seedance && /\p{Script=Cyrillic}/u.test(scenario.spokenScript)
        ? SEEDANCE_RUSSIAN_DICTION_GUARD
        : "",
    ),
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
      Boolean(researchCategoryRuleFragment),
    )),
  ];
  const prompt = fitPrompt(promptLines, contentGenerationPromptLimit(normalizedMode));
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
    researchCategoryRuleRequired: handoff.requiresResearchCategoryRule,
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

export function normalizeAiResearchProviderPromptFragment(value) {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
  const version = String(
    source.provider_prompt_fragment_version
      || source.providerPromptFragmentVersion
      || source.fragmentVersion
      || "",
  );
  const fragment = String(
    source.provider_prompt_fragment
      || source.providerPromptFragment
      || source.fragment
      || "",
  );
  const fragmentHash = String(
    source.provider_prompt_fragment_hash
      || source.providerPromptFragmentHash
      || source.fragmentHash
      || "",
  );
  if (
    version !== AI_RESEARCH_PROVIDER_FRAGMENT_VERSION
    || !fragment
    || textCodePointLength(fragment) > AI_RESEARCH_PROVIDER_FRAGMENT_LIMIT
    || cleanAiResearchHumanText(fragment) !== fragment
    || !fragment.startsWith(`${AI_RESEARCH_PROVIDER_FRAGMENT_MARKER} `)
    || countCaseInsensitive(fragment, AI_RESEARCH_PROVIDER_FRAGMENT_MARKER) !== 1
    || countCaseInsensitive(fragment, AI_RESEARCH_HUMAN_INTENT_MARKER) !== 0
    || !/^[0-9a-f]{64}$/u.test(fragmentHash)
  ) return null;
  return { version, fragment, fragmentHash };
}

export function compileAiResearchHumanIntent({
  currentBrief = "",
} = {}) {
  const currentRaw = trimAsciiWhitespace(currentBrief);
  if (
    !currentRaw
    || countCaseInsensitive(currentRaw, AI_RESEARCH_PROVIDER_FRAGMENT_MARKER) > 0
    || countCaseInsensitive(currentRaw, AI_RESEARCH_HUMAN_INTENT_MARKER) > 0
  ) {
    return {
      ready: false,
      line: "",
      changedSections: [],
      code: "ai_research_human_intent_invalid",
    };
  }
  const currentSections = aiResearchBriefSections(currentRaw);
  const fields = AI_RESEARCH_HUMAN_SECTION_KEYS.map(
    ([section, key, limit]) => ({
      section,
      key,
      limit,
      value: cleanAiResearchHumanText(currentSections?.[section]),
    }),
  );
  if (fields.some((field) => !field.value)) {
    return {
      ready: false,
      line: "",
      changedSections: fields.filter((field) => field.value)
        .map((field) => field.section),
      code: "ai_research_human_intent_invalid",
    };
  }
  const body = fields.map((field) => (
    `${field.key}=${boundedAiResearchText(field.value, field.limit)}`
  )).join("|");
  const line = `${AI_RESEARCH_HUMAN_INTENT_MARKER} ${body}`;
  if (textCodePointLength(line) > AI_RESEARCH_HUMAN_INTENT_LIMIT) {
    return {
      ready: false,
      line: "",
      changedSections: fields.map((field) => field.section),
      code: "ai_research_prompt_budget_exceeded",
    };
  }
  return {
    ready: true,
    line,
    changedSections: fields.map((field) => field.section),
  };
}

function compileAiResearchSpokenIntent({
  currentBrief = "",
  durationSeconds = 8,
  exactDuration = false,
} = {}) {
  const exactDurationValue = Number(durationSeconds);
  const normalizedDuration = exactDuration
    && Number.isSafeInteger(exactDurationValue)
    && exactDurationValue > 0
    && exactDurationValue <= 60
    ? exactDurationValue
    : contentGenerationDurationSeconds(REAL_SEEDANCE_MODE, durationSeconds);
  const wordLimit = exactDuration
    ? exactSpokenWordLimit(normalizedDuration)
    : seedanceSpokenWordLimit(normalizedDuration);
  const currentRaw = String(currentBrief ?? "");
  const sections = aiResearchBriefSections(currentRaw, { strictSpoken: true });
  const sectionValue = cleanAiResearchHumanText(
    sections?.[AI_RESEARCH_SPOKEN_SECTION],
  );
  const spokenSectionCount = (
    currentRaw.match(
      AI_RESEARCH_SPOKEN_SECTION_TOKEN_GLOBAL_PATTERN,
    ) || []
  ).length;
  const line = cleanText(sectionValue);
  const spokenWords = words(line).length;
  if (
    !sections
    || sections.__spokenUnsafe === true
    || AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN.test(currentRaw)
    || spokenSectionCount !== 1
    || !line
    || AI_RESEARCH_SPOKEN_SECTION_TOKEN_PATTERN.test(sectionValue)
    || AI_RESEARCH_SPOKEN_WRAPPER_PATTERN.test(sectionValue)
    || AI_RESEARCH_SPOKEN_CONTROL_PATTERN.test(sectionValue)
    || AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN.test(sectionValue)
    || AI_RESEARCH_SPOKEN_NON_ASCII_WHITESPACE_PATTERN.test(sectionValue)
    || AI_RESEARCH_SPOKEN_QUOTATION_MARK_PATTERN.test(sectionValue)
    || spokenWords < 1
  ) {
    return {
      ready: false,
      line: "",
      spokenWords: 0,
      wordLimit,
      durationSeconds: normalizedDuration,
      code: "ai_research_spoken_script_invalid",
    };
  }
  if (spokenWords > wordLimit) {
    return {
      ready: false,
      line: "",
      spokenWords,
      wordLimit,
      durationSeconds: normalizedDuration,
      code: "ai_research_spoken_script_too_long",
    };
  }
  return {
    ready: true,
    line,
    spokenWords,
    wordLimit,
    durationSeconds: normalizedDuration,
    code: "",
  };
}

export function compileSafeGenerationBrief({
  mode,
  productName,
  sku,
  scenarioIntent = "",
  visualDirection = "",
  avoidClaims = [],
  researchDecision = "",
  learningPolicy = null,
  repairPolicy = null,
  generationReferenceFragment = "",
  durationSeconds: requestedDurationSeconds = null,
  productCategory = "",
  researchCategoryRule = null,
  selectedRecommendation = null,
  generationSelection = null,
} = {}) {
  const normalizedMode = normalizeMode(mode);
  const exactGenerationSelection = normalizeGenerationPromptSelection(
    generationSelection,
  );
  const generatedAudio = exactGenerationSelection
    ? exactGenerationSelection.audio
    : normalizedMode === REAL_SEEDANCE_MODE;
  const exactDuration = exactGenerationSelection?.durationSeconds ?? null;
  const exactProductName = cleanText(productName);
  const exactSku = cleanText(sku);
  const rawScenarioIntent = cleanText(scenarioIntent).slice(0, 1_200);
  const explicitSpokenLine = extractExplicitSpokenLine(rawScenarioIntent);
  const safeScenarioIntent = truncateScenarioIntent(
    removeExplicitSpokenLine(rawScenarioIntent),
    SAFE_SCENARIO_INTENT_LIMIT,
  );
  const selectedRecommendationRequired = selectedRecommendation?.required === true;
  const selectedProviderFragment = selectedRecommendationRequired
    ? normalizeAiResearchProviderPromptFragment(selectedRecommendation)
    : null;
  const selectedHumanIntent = selectedRecommendationRequired
    ? compileAiResearchHumanIntent({
        currentBrief: selectedRecommendation?.currentBrief,
      })
    : { ready: true, line: "", changedSections: [] };
  const selectedSpokenIntent = selectedRecommendationRequired
    && generatedAudio
    ? compileAiResearchSpokenIntent({
        currentBrief: selectedRecommendation?.currentBrief,
        durationSeconds: exactDuration ?? contentGenerationDurationSeconds(
          REAL_SEEDANCE_MODE,
          requestedDurationSeconds,
        ),
        exactDuration: exactGenerationSelection !== null,
      })
    : { ready: true, line: "", spokenWords: 0 };
  const promptScenarioIntent = selectedRecommendationRequired
    ? ""
    : safeScenarioIntent;
  const safeVisualDirection = cleanText(visualDirection);
  const safeAvoidClaims = uniqueStrings(avoidClaims, 8);
  const safeResearchDecision = cleanResearchDecision(researchDecision);
  const safeGenerationReferenceFragment = cleanText(
    generationReferenceFragment,
  ).slice(0, 520);
  const generationReferenceInspection =
    inspectGenerationVideoReferencePromptFragment(
      safeGenerationReferenceFragment,
    );
  const researchCategoryRuleFragment = generationResearchCategoryRuleFragment(
    researchCategoryRule,
  );
  const learningDirection = generationLearningDirection(
    learningPolicy,
    normalizedMode,
    repairPolicy,
    Boolean(researchCategoryRuleFragment),
  );
  const interaction = inferProductInteractionProfile({
    productName: exactProductName,
    productCategory,
  });
  const blockers = [];
  const warnings = [];

  if (
    countCaseInsensitive(rawScenarioIntent, AI_RESEARCH_PROVIDER_FRAGMENT_MARKER) > 0
    || countCaseInsensitive(rawScenarioIntent, AI_RESEARCH_HUMAN_INTENT_MARKER) > 0
  ) {
    blockers.push({
      code: "ai_research_prompt_reserved_marker_invalid",
      message: "Служебные маркеры рекомендации ИИ‑центра нельзя добавлять в замысел вручную.",
    });
  }
  if (selectedRecommendationRequired && !selectedProviderFragment) {
    blockers.push({
      code: "ai_research_prompt_binding_invalid",
      message: "Сервер не подтвердил обязательный фрагмент выбранной рекомендации ИИ‑центра.",
    });
  }
  if (selectedRecommendationRequired && !selectedHumanIntent.ready) {
    blockers.push({
      code: selectedHumanIntent.code || "ai_research_human_intent_invalid",
      message: "Ручные правки рекомендации не удалось безопасно уместить в технический prompt.",
    });
  }
  if (
    selectedRecommendationRequired
    && generatedAudio
    && !selectedSpokenIntent.ready
  ) {
    blockers.push({
      code: selectedSpokenIntent.code || "ai_research_spoken_script_invalid",
      message: selectedSpokenIntent.code === "ai_research_spoken_script_too_long"
        ? `Реплика выбранного варианта длиннее лимита для ${selectedSpokenIntent.durationSeconds} секунд. Сократите поле «РЕПЛИКА / СЮЖЕТ» до ${selectedSpokenIntent.wordLimit} слов.`
        : "В выбранном варианте ИИ‑центра нет одной безопасной точной реплики. Проверьте поле «РЕПЛИКА / СЮЖЕТ».",
    });
  }
  if (
    selectedRecommendationRequired
    && selectedProviderFragment
    && selectedHumanIntent.ready
    && textCodePointLength(selectedProviderFragment.fragment)
      + textCodePointLength(selectedHumanIntent.line) > 390
  ) {
    blockers.push({
      code: "ai_research_prompt_budget_exceeded",
      message: "Выбранная рекомендация и ручная правка превышают безопасный лимит provider prompt.",
    });
  }

  if (
    safeGenerationReferenceFragment
    && EXTERNAL_REFERENCE_PATTERN.test(safeGenerationReferenceFragment)
  ) {
    blockers.push({
      code: "generation_reference_url_forbidden",
      message: "URL видеореференса хранится только в lineage; в генератор передаётся описание механики.",
    });
  }
  if (!generationReferenceInspection.ready) {
    blockers.push({
      code: GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE,
      message: "Служебная строка видеореференса повреждена или добавлена вручную. Обновите авто-ТЗ.",
    });
  }
  if (normalizedMode === REAL_PHOTO_MODE && safeGenerationReferenceFragment) {
    blockers.push({
      code: "generation_video_reference_mode_invalid",
      message: "Видеореференс можно привязать только к генерации видео.",
    });
  }

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
        : exactDuration ?? contentGenerationDurationSeconds(
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
      requiredVerbatim(selectedProviderFragment?.fragment || ""),
      requiredVerbatim(selectedHumanIntent.line),
      required(safeResearchDecision
        ? `Решение пользователя после исследования — имеет приоритет: ${safeResearchDecision}.`
        : ""),
      required(researchCategoryRuleFragment),
      optional("Студийное фото: один товар целиком по центру, нейтральный фон, мягкий свет, естественная тень, высокая детализация."),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      optional("Товар — единственный главный объект; оставь безопасные поля по краям."),
      required(productLock),
      required(claimGuard),
      required("Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса."),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  } else if (!generatedAudio) {
    durationSeconds = exactDuration ?? contentGenerationDurationSeconds(
      normalizedMode,
      requestedDurationSeconds,
    );
    promptLines = [
      required(exactGenerationSelection
        ? `Создай один непрерывный ролик длительностью ${durationSeconds} секунд с соотношением сторон ${exactGenerationSelection.format}.`
        : `Создай один непрерывный вертикальный ролик длительностью ${durationSeconds} секунд.`),
      required(identityLine),
      requiredVerbatim(selectedProviderFragment?.fragment || ""),
      requiredVerbatim(selectedHumanIntent.line),
      required(safeResearchDecision
        ? `Решение пользователя после исследования — имеет приоритет: ${safeResearchDecision}.`
        : ""),
      required(researchCategoryRuleFragment),
      required(safeGenerationReferenceFragment),
      optional(
        promptScenarioIntent
          ? `Замысел пользователя (только без конфликта с ограничениями ниже): ${withTerminalPunctuation(promptScenarioIntent)}`
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
    durationSeconds = exactDuration ?? contentGenerationDurationSeconds(
      normalizedMode,
      requestedDurationSeconds,
    );
    const spokenLine = selectedRecommendationRequired
      ? selectedSpokenIntent.line
      : safeScenarioSpokenLine({
          scenarioIntent: rawScenarioIntent,
          explicitSpokenLine,
          productName: exactProductName,
          fallback: interaction.spokenLine,
          durationSeconds,
          exactDuration: exactGenerationSelection !== null,
        });
    spokenWords = words(spokenLine).length;
    promptLines = [
      required(exactGenerationSelection
        ? `Создай один непрерывный UGC-ролик длительностью ${durationSeconds} секунд с соотношением сторон ${exactGenerationSelection.format}.`
        : `Создай один непрерывный вертикальный UGC-ролик длительностью ${durationSeconds} секунд.`),
      required(identityLine),
      requiredVerbatim(selectedProviderFragment?.fragment || ""),
      requiredVerbatim(selectedHumanIntent.line),
      required(safeResearchDecision
        ? `Решение пользователя после исследования — имеет приоритет: ${safeResearchDecision}.`
        : ""),
      required(researchCategoryRuleFragment),
      required(safeGenerationReferenceFragment),
      optional(
        promptScenarioIntent
          ? `Замысел пользователя (только без конфликта с ограничениями ниже): ${withTerminalPunctuation(promptScenarioIntent)}`
          : interaction.videoAction,
      ),
      required(interaction.requirement),
      required(spokenLine
        ? `Реплика героя дословно: «${spokenLine}»`
        : ""),
      required(
        /\p{Script=Cyrillic}/u.test(spokenLine)
          ? SEEDANCE_RUSSIAN_DICTION_GUARD
          : "",
      ),
      required(GENERATED_TEXT_GUARD),
      required(learningDirection),
      optional(safeVisualDirection ? `Визуальное направление: ${safeVisualDirection}.` : ""),
      required(productLock),
      required(claimGuard),
      optional(safeAvoidClaims.length ? `Не использовать: ${safeAvoidClaims.join("; ")}.` : ""),
    ];
  }

  const prompt = fitPrompt(
    promptLines,
    exactGenerationSelection?.promptLimit
      ?? contentGenerationPromptLimit(normalizedMode),
  );
  if (!prompt) {
    blockers.push({
      code: selectedRecommendationRequired
        ? "ai_research_prompt_budget_exceeded"
        : "prompt_too_long",
      message: selectedRecommendationRequired
        ? "Выбранная рекомендация и обязательные ограничения не помещаются в лимит модели. Платный запуск остановлен."
        : "Точное название товара слишком длинное для безопасного промпта.",
    });
  }
  if (prompt) {
    const providerMarkerCount = countCaseInsensitive(
      prompt,
      AI_RESEARCH_PROVIDER_FRAGMENT_MARKER,
    );
    const humanMarkerCount = countCaseInsensitive(
      prompt,
      AI_RESEARCH_HUMAN_INTENT_MARKER,
    );
    if (selectedRecommendationRequired && (
      providerMarkerCount !== 1
        || !prompt.includes(selectedProviderFragment?.fragment || "")
        || humanMarkerCount !== 1
        || !prompt.includes(selectedHumanIntent.line)
    )) {
      blockers.push({
        code: "ai_research_prompt_binding_invalid",
        message: "Технический prompt потерял обязательную связь с выбранной рекомендацией ИИ‑центра.",
      });
    }
    if (
      selectedRecommendationRequired
      && generatedAudio
      && selectedSpokenIntent.ready
    ) {
      const expectedSpokenLine =
        `Реплика героя дословно: «${selectedSpokenIntent.line}»`;
      const actualSpokenLine =
        /Реплика героя дословно:\s*«([^»]+)»/u.exec(prompt)?.[1] || "";
      const spokenDirectiveCount = (
        prompt.match(PROMPT_SPOKEN_DIRECTIVE_PATTERN) || []
      ).length;
      if (
        actualSpokenLine !== selectedSpokenIntent.line
        || spokenDirectiveCount !== 1
        || prompt.split(expectedSpokenLine).length - 1 !== 1
        || AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN.test(prompt)
      ) {
        blockers.push({
          code: "ai_research_prompt_binding_invalid",
          message: "Технический prompt потерял точную реплику выбранного варианта ИИ‑центра.",
        });
      }
    }
    if (
      !selectedRecommendationRequired
      && (providerMarkerCount !== 0 || humanMarkerCount !== 0)
    ) {
      blockers.push({
        code: "ai_research_prompt_reserved_marker_invalid",
        message: "Служебные маркеры рекомендации ИИ‑центра нельзя добавлять в prompt вручную.",
      });
    }
  }
  const inspection = inspectContentGenerationPrompt(prompt, normalizedMode, {
    productName: exactProductName,
    avoidClaims: safeAvoidClaims,
    durationSeconds,
    productCategory,
    researchCategoryRuleRequired: Boolean(researchCategoryRuleFragment),
    generationReferenceFragment: generationReferenceInspection.ready
      ? generationReferenceInspection.fragment
      : "",
    generationSelection: exactGenerationSelection,
  });
  for (const blocker of inspection.blockers) {
    if (!blockers.some((item) => item.code === blocker.code)) blockers.push(blocker);
  }
  return result(prompt, blockers, warnings, {
    durationSeconds,
    spokenWords,
    mode: normalizedMode,
    learningApplied: Boolean(learningDirection),
    selectedRecommendationApplied: selectedRecommendationRequired
      && Boolean(selectedProviderFragment),
    selectedRecommendationFragment:
      selectedProviderFragment?.fragment || "",
    selectedRecommendationFragmentHash:
      selectedProviderFragment?.fragmentHash || "",
    selectedRecommendationHumanIntent: selectedHumanIntent.line,
    selectedRecommendationSpokenLine: selectedSpokenIntent.line,
  });
}

export function inferGenerationCreativeSignals({
  hook = "",
  shotList = "",
} = {}) {
  const normalizedHook = cleanText(hook);
  const combined = cleanText(`${normalizedHook} ${shotList}`);
  const lowered = combined.toLocaleLowerCase("ru-RU");
  const hookPatterns = [];
  if (normalizedHook.includes("?")) hookPatterns.push("question_led");
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
  const hookCodePointLength = [...normalizedHook].length;
  if (hookCodePointLength > 0 && hookCodePointLength <= 72) {
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

export function generationResearchCategorySignal(handoff) {
  if (
    handoff?.requiresResearchCategoryRule !== true
    || !validResearchCategoryBinding(handoff?.researchCategoryBinding)
    || !validResearchCategoryPolicy(handoff?.researchCategoryPolicy)
  ) return null;
  return {
    ...inferGenerationCreativeSignals({
    hook: handoff?.scenario?.hook,
    shotList: handoff?.scenario?.shotList,
    }),
    categoryMaturity: handoff.researchCategoryPolicy.categoryMaturity,
    competitorCoverage: handoff.researchCategoryPolicy.competitorCoverage,
    primarySignal: handoff.researchCategoryPolicy.primarySignal,
  };
}

/**
 * A provider-visible, server-verifiable rule derived only from the bounded
 * structure of an approved research scenario plus bounded category maturity,
 * competitor coverage and an allowlisted structural trend key. Raw captions,
 * competitor copy, URLs and arbitrary research prose can never enter it.
 */
export function generationResearchCategoryRuleFragment(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const allowedAngles = new Set([
    "product_focus",
    "trust_builder",
    "demonstration",
    "comparison",
    "objection_handling",
    "curiosity_gap",
  ]);
  const allowedHooks = new Set([
    "question_led",
    "why_explanation",
    "before_buying",
    "comparison",
    "demonstration",
    "first_person",
    "numbered",
    "concise",
  ]);
  const creativeAngle = cleanText(
    value.creativeAngle || value.creative_angle,
  ).toLowerCase();
  const categoryMaturity = cleanText(
    value.categoryMaturity || value.category_maturity,
  ).toLowerCase();
  const competitorCoverage = cleanText(
    value.competitorCoverage || value.competitor_coverage,
  ).toLowerCase();
  const primarySignal = cleanText(
    value.primarySignal || value.primary_signal,
  ).toLowerCase();
  const hooks = Array.isArray(value.hookPatterns || value.hook_patterns)
    ? (value.hookPatterns || value.hook_patterns)
      .map((item) => cleanText(item).toLowerCase())
      .filter(Boolean)
    : [];
  if (
    !allowedAngles.has(creativeAngle)
    || !RESEARCH_CATEGORY_MATURITIES.has(categoryMaturity)
    || !RESEARCH_COMPETITOR_COVERAGES.has(competitorCoverage)
    || (
      primarySignal !== "none"
      && !RESEARCH_CATEGORY_STRUCTURAL_SIGNALS.has(primarySignal)
    )
    || hooks.length > 8
    || new Set(hooks).size !== hooks.length
    || hooks.some((hook) => !allowedHooks.has(hook))
  ) return "";
  return `ResearchCategoryRule/v2 category_maturity=${categoryMaturity} competitor_coverage=${competitorCoverage} primary_signal=${primarySignal} creative_angle=${creativeAngle} primary_hook=${hooks[0] || "none"}.`;
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
  const advisoryGenerationAllowed = policyField(
    value,
    "advisory_generation_allowed",
    "advisoryGenerationAllowed",
  );
  const generationAllowed = advisoryGenerationAllowed === undefined
    ? policyField(value, "generation_allowed", "generationAllowed") !== false
    : advisoryGenerationAllowed !== false;
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

function generationLearningDirection(
  value,
  mode,
  repairValue = null,
  researchCategoryRuleApplied = false,
) {
  // Until the immutable spec has an explicit quality-guard-only provenance,
  // a research category rule owns the entire learned prompt surface.  This
  // keeps the stored creative signal identical to what the provider sees.
  const policy = researchCategoryRuleApplied
    ? null
    : normalizeGenerationLearningPolicy(value);
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
  const angleDirection = !policy?.applied || researchCategoryRuleApplied
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
  const hookDirection = !policy?.applied
    || researchCategoryRuleApplied
    || mode === REAL_PHOTO_MODE
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

function compactGenerationLearningDirection(value) {
  let direction = cleanText(value);
  if (!direction) return "";
  const qualityFragments = [];
  const qualityReplacements = [
    ["QA: точная геометрия, этикетка, текст, цвет и пропорции.", "точны геометрия/этикетка/текст/цвет/пропорции"],
    ["QA: резкий товар, ровный свет, без пересвета и размытия.", "товар резкий; свет ровный; без пересвета/размытия"],
    ["QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.", "товар точен"],
    ["QA: стабильный проход без чёрных кадров, скачков и мерцания.", "без чёрных кадров/скачков/мерцания"],
    ["QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.", "речь чистая/слышна; без тишины/клиппинга/рассинхрона"],
    ["QA: реплика произносится дословно, без пропусков, замен и новых слов.", "реплика дословно; без пропусков/замен/новых слов"],
    ["QA: точный товар и одно действие видны в первые 2 секунды.", "товар+действие видны в первые 2 с"],
    ["QA: руки, лицо и фактуры без деформаций, дублей и мерцания.", "руки/лицо/фактуры без деформаций/дублей"],
    ["QA: естественная подача без гиперболы и новых обещаний.", "естественно; без гиперболы/новых обещаний"],
    ["QA: мастер 9:16; товар и лицо в безопасных полях.", "9:16; товар/лицо в безопасных полях"],
  ];
  for (const [fullText, compactText] of qualityReplacements) {
    if (!direction.includes(fullText)) continue;
    direction = direction.replace(fullText, "");
    qualityFragments.push(compactText);
  }
  direction = cleanText(direction)
    .replace("Обученное направление: одно видимое действие с товаром.", "Обучен: действие.")
    .replace("Структурный hook: одно простое действие с товаром.", "")
    .replace("Обученное направление: заметная деталь, затем товар целиком.", "Обучен: деталь→товар;")
    .replace("Структурный hook: сравнение без второго товара, цифр и обещаний.", "hook: сравнение без 2-го товара/цифр/обещаний.");
  return cleanText([
    direction,
    qualityFragments.length ? `QA: ${qualityFragments.join("; ")}.` : "",
  ].filter(Boolean).join(" "));
}

export function inspectContentGenerationPrompt(
  prompt,
  mode,
  {
    productName = "",
    productCategory = "",
    avoidClaims = [],
    durationSeconds = null,
    researchCategoryRuleRequired = false,
    generationReferenceFragment = "",
    generationSelection = null,
  } = {},
) {
  const promptLines = String(prompt ?? "").split(/\r?\n/u).map(cleanText).filter(Boolean);
  const normalized = cleanText(prompt);
  const normalizedMode = normalizeMode(mode);
  const exactGenerationSelection = normalizeGenerationPromptSelection(
    generationSelection,
  );
  const normalizedDuration = exactGenerationSelection?.durationSeconds
    ?? contentGenerationDurationSeconds(normalizedMode, durationSeconds);
  const blockers = [];
  const warnings = [];
  if (!normalized) {
    blockers.push({ code: "prompt_missing", message: "Промпт для генерации пуст." });
    return result(normalized, blockers, warnings);
  }
  const promptLimit = exactGenerationSelection?.promptLimit
    ?? contentGenerationPromptLimit(normalizedMode);
  if (normalized.length > promptLimit) {
    blockers.push({
      code: "prompt_too_long",
      message: `Техническое ТЗ длиннее лимита модели (${promptLimit} символов).`,
    });
  }
  if (EXTERNAL_REFERENCE_PATTERN.test(normalized)) {
    blockers.push({
      code: "external_url_forbidden",
      message: "Удалите URL из задания: источники остаются в исследовании, а не передаются генератору.",
    });
  }
  const expectedReference = inspectGenerationVideoReferencePromptFragment(
    generationReferenceFragment,
  );
  const expectedReferenceMarkerCount = expectedReference.present
    && expectedReference.ready ? 1 : 0;
  const actualReferenceMarkerCount = normalized.split(
    GENERATION_VIDEO_REFERENCE_PROMPT_MARKER,
  ).length - 1;
  const exactReferenceFragmentCount = expectedReferenceMarkerCount === 1
    ? normalized.split(expectedReference.fragment).length - 1
    : 0;
  if (
    !expectedReference.ready
    || actualReferenceMarkerCount !== expectedReferenceMarkerCount
    || (expectedReferenceMarkerCount === 1 && exactReferenceFragmentCount !== 1)
  ) {
    blockers.push({
      code: GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE,
      message: "Служебная строка видеореференса должна добавляться системой ровно один раз.",
    });
  }
  const researchCategoryRuleTokenCount = (
    normalized.match(/researchcategoryrule\//giu) || []
  ).length;
  if (
    researchCategoryRuleRequired
      ? researchCategoryRuleTokenCount !== 1
      : researchCategoryRuleTokenCount !== 0
  ) {
    blockers.push({
      code: "research_category_rule_token_invalid",
      message: "Обновите сценарий: служебное правило категории должно добавляться системой ровно один раз.",
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
  } else if (exactGenerationSelection?.audio === true
    || (!exactGenerationSelection && normalizedMode === REAL_SEEDANCE_MODE)) {
    if (AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN.test(String(prompt ?? ""))) {
      blockers.push({
        code: "spoken_prompt_ambiguous",
        message: "Удалите невидимые управляющие символы из задания и реплики.",
      });
    }
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
    const expectedOutput = exactGenerationSelection
      ? `Создай один непрерывный UGC-ролик длительностью ${normalizedDuration} секунд с соотношением сторон ${exactGenerationSelection.format}.`
      : `Создай один непрерывный вертикальный UGC-ролик длительностью ${normalizedDuration} секунд`;
    if (!normalized.includes(expectedOutput)) {
      blockers.push({
        code: "seedance_output_guard_missing",
        message: exactGenerationSelection
          ? `Верните точные длительность ${normalizedDuration} секунд и соотношение сторон ${exactGenerationSelection.format}.`
          : `Верните точный формат одного вертикального UGC-ролика на ${normalizedDuration} секунд.`,
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
      const spokenWordLimit = exactGenerationSelection
        ? exactSpokenWordLimit(normalizedDuration)
        : seedanceSpokenWordLimit(normalizedDuration);
      if (match[1].includes("[СОКРАТИТЕ") || spokenWords > spokenWordLimit) {
        blockers.push({
          code: "spoken_script_too_long",
          message: `Для ${normalizedDuration} секунд оставьте в точной реплике не больше ${spokenWordLimit} слов.`,
        });
      }
      if (
        /\p{Script=Cyrillic}/u.test(match[1])
        && !normalized.includes(SEEDANCE_RUSSIAN_DICTION_GUARD)
      ) {
        blockers.push({
          code: "russian_diction_guard_missing",
          message: "Верните обязательное требование к русской дикции, окончаниям, числам и паузам.",
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
    const expectedOutput = exactGenerationSelection
      ? `Создай один непрерывный ролик длительностью ${normalizedDuration} секунд с соотношением сторон ${exactGenerationSelection.format}.`
      : `Создай один непрерывный вертикальный ролик длительностью ${normalizedDuration} секунд`;
    if (!normalized.includes(expectedOutput)) {
      blockers.push({
        code: "gen4_output_guard_missing",
        message: exactGenerationSelection
          ? `Верните точные длительность ${normalizedDuration} секунд и соотношение сторон ${exactGenerationSelection.format}.`
          : `Верните точный формат одного вертикального ролика Gen4 на ${normalizedDuration} секунд.`,
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
    typeof value.requiresResearchCategoryRule !== "boolean"
    || (
      !value.requiresResearchCategoryRule
      && (
        value.researchCategoryBinding !== null
        || value.researchCategoryPolicy !== null
      )
    )
    || (
      value.requiresResearchCategoryRule
      && !validResearchCategoryPolicy(value.researchCategoryPolicy)
    )
  ) return false;
  if (
    value.researchCategoryBinding !== null
    && !validResearchCategoryBinding(value.researchCategoryBinding)
  ) return false;
  if (
    !cleanText(value.researchId) || !cleanText(value.draftId) ||
    !cleanText(value.productName) || !cleanText(value.sku) ||
    !UUID_PATTERN.test(cleanText(value.projectId).toLowerCase())
  ) return false;
  const guidanceStatus = cleanText(value.researchGuidanceStatus);
  const researchDecision = cleanText(value.researchDecision);
  if (
    researchDecision.length > 420 || /https?:\/\//iu.test(researchDecision) ||
    (guidanceStatus && ![
      "ready_for_brief",
      "needs_more_evidence",
      "needs_user_decision",
    ].includes(guidanceStatus)) ||
    (guidanceStatus && guidanceStatus !== "ready_for_brief" && !researchDecision)
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

function hasModernResearchCategoryAnalysis(record) {
  if (record?.hasCategoryAnalysis === true) return true;
  const source = record?.rawBrief?.category_analysis;
  return Boolean(
    source
    && typeof source === "object"
    && !Array.isArray(source),
  );
}

function boundedResearchCategoryPolicy(rawBrief) {
  const brief = rawBrief && typeof rawBrief === "object" && !Array.isArray(rawBrief)
    ? rawBrief
    : {};
  const category = brief.category_analysis;
  const competitors = brief.competitor_analysis;
  const trends = brief.trend_analysis;
  const categoryMaturity = RESEARCH_CATEGORY_MATURITIES.has(
    cleanText(category?.maturity).toLowerCase(),
  ) ? cleanText(category.maturity).toLowerCase() : "unknown";
  const competitorCoverage = RESEARCH_COMPETITOR_COVERAGES.has(
    cleanText(competitors?.coverage).toLowerCase(),
  ) ? cleanText(competitors.coverage).toLowerCase() : "none";
  const primaryTrend = trends?.signal_catalog_version === "structural_v1"
    && Array.isArray(trends?.signals)
    ? trends.signals.find((signal) => {
      const signalKey = cleanText(signal?.signal_key).toLowerCase();
      return RESEARCH_CATEGORY_STRUCTURAL_SIGNALS.has(signalKey)
        && signal?.recommended_use === "test"
        && ["medium", "high"].includes(cleanText(signal?.confidence).toLowerCase())
        && ["emerging", "growing", "stable", "declining"].includes(
          cleanText(signal?.direction).toLowerCase(),
        );
    })
    : null;
  return {
    categoryMaturity,
    competitorCoverage,
    primarySignal: cleanText(primaryTrend?.signal_key).toLowerCase() || "none",
  };
}

function validResearchCategoryPolicy(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const keys = Object.keys(value);
  return keys.length === 3
    && keys.every((key) => [
      "categoryMaturity", "competitorCoverage", "primarySignal",
    ].includes(key))
    && RESEARCH_CATEGORY_MATURITIES.has(value.categoryMaturity)
    && RESEARCH_COMPETITOR_COVERAGES.has(value.competitorCoverage)
    && (
      value.primarySignal === "none"
      || RESEARCH_CATEGORY_STRUCTURAL_SIGNALS.has(value.primarySignal)
    );
}

function normalizedResearchCategoryBinding(record, required = false) {
  if (!required) return null;
  const source = record?.marketRegistry?.currentBinding;
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return null;
  }
  const value = {
    categoryId: cleanText(source.categoryId || source.category_id).toLowerCase(),
    bindingId: cleanText(source.bindingId || source.binding_id).toLowerCase(),
    bindingVersion: Number(source.bindingVersion || source.binding_version),
    sourceRunId: cleanText(source.sourceRunId || source.source_run_id).toLowerCase(),
    sourceDraftId: cleanText(source.sourceDraftId || source.source_draft_id).toLowerCase(),
    candidateHash: cleanText(source.candidateHash || source.candidate_hash).toLowerCase(),
  };
  return validResearchCategoryBinding(value) ? value : null;
}

function validResearchCategoryBinding(value) {
  return Boolean(
    value
    && typeof value === "object"
    && !Array.isArray(value)
    && UUID_PATTERN.test(cleanText(value.categoryId).toLowerCase())
    && UUID_PATTERN.test(cleanText(value.bindingId).toLowerCase())
    && Number.isInteger(Number(value.bindingVersion))
    && Number(value.bindingVersion) >= 1
    && Number(value.bindingVersion) <= 100_000
    && UUID_PATTERN.test(cleanText(value.sourceRunId).toLowerCase())
    && UUID_PATTERN.test(cleanText(value.sourceDraftId).toLowerCase())
    && /^[0-9a-f]{64}$/u.test(cleanText(value.candidateHash).toLowerCase())
  );
}

function fitPrompt(items, maximum) {
  const active = items.filter((item) => item.text);
  const render = () => active.map((item) => item.text).join("\n");
  while (render().length > maximum) {
    const index = active.map((item) => item.required).lastIndexOf(false);
    if (index < 0) break;
    active.splice(index, 1);
  }
  if (render().length <= maximum) return render();
  for (const item of active) {
    if (!item.compactText || item.compactText.length >= item.text.length) continue;
    item.text = item.compactText;
    if (render().length <= maximum) return render();
  }
  return "";
}

function required(text) {
  const normalized = cleanText(text);
  return {
    text: normalized,
    compactText: compactGenerationLearningDirection(normalized),
    required: true,
  };
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
  exactDuration = false,
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
  const maximum = exactDuration
    ? exactSpokenWordLimit(durationSeconds)
    : seedanceSpokenWordLimit(durationSeconds);
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

function requiredVerbatim(text) {
  const verbatim = String(text ?? "");
  return {
    text: cleanAiResearchHumanText(verbatim) === verbatim ? verbatim : "",
    compactText: "",
    required: true,
  };
}

function aiResearchBriefSections(value, { strictSpoken = false } = {}) {
  const sections = {};
  const seen = new Set();
  const uniqueSections = new Set([
    ...AI_RESEARCH_HUMAN_SECTION_KEYS.map(([section]) => section),
    ...(strictSpoken ? [AI_RESEARCH_SPOKEN_SECTION] : []),
  ]);
  const rawValue = String(value || "");
  if (
    strictSpoken
    && AI_RESEARCH_RAW_UNSAFE_CONTROL_PATTERN.test(rawValue)
  ) {
    sections.__spokenUnsafe = true;
  }
  let active = "";
  rawValue.replace(/\r\n?/gu, "\n").split("\n").forEach((rawLine) => {
    const line = strictSpoken
      ? String(rawLine || "")
        .replace(/^\p{White_Space}+/gu, "")
        .replace(/\p{White_Space}+$/gu, "")
      : String(rawLine || "")
        .replace(/^ +/gu, "")
        .replace(/ +$/gu, "");
    if (!line) return;
    const heading = AI_RESEARCH_BRIEF_SECTION_PATTERN.exec(line);
    if (heading) {
      active = heading[1].toLocaleUpperCase("ru-RU");
      if (uniqueSections.has(active) && seen.has(active)) {
        sections.__invalid = true;
        return;
      }
      if (uniqueSections.has(active)) seen.add(active);
      if (
        strictSpoken
        && active === AI_RESEARCH_SPOKEN_SECTION
        && unsafeAiResearchSpokenRawText(rawLine)
      ) {
        sections.__spokenUnsafe = true;
      }
      const inline = cleanAiResearchHumanText(heading[2]);
      if (inline) sections[active] = inline;
      return;
    }
    if (!active) return;
    if (
      strictSpoken
      && active === AI_RESEARCH_SPOKEN_SECTION
      && unsafeAiResearchSpokenRawText(rawLine)
    ) {
      sections.__spokenUnsafe = true;
    }
    sections[active] = cleanAiResearchHumanText(
      `${sections[active] || ""} ${line}`,
    );
  });
  return sections.__invalid === true ? null : sections;
}

function unsafeAiResearchSpokenRawText(value) {
  const raw = String(value ?? "");
  return AI_RESEARCH_SPOKEN_CONTROL_PATTERN.test(raw)
    || AI_RESEARCH_DEFAULT_IGNORABLE_PATTERN.test(raw)
    || AI_RESEARCH_SPOKEN_NON_ASCII_WHITESPACE_PATTERN.test(raw)
    || AI_RESEARCH_SPOKEN_QUOTATION_MARK_PATTERN.test(raw);
}

function boundedAiResearchText(value, maximum) {
  const normalized = cleanAiResearchHumanText(value).replace(/\|/gu, "/");
  const limit = Math.max(1, Number(maximum) || 1);
  const codePoints = Array.from(normalized);
  if (codePoints.length <= limit) return normalized;
  if (limit === 1) return "…";
  return `${codePoints.slice(0, limit - 1).join("").replace(/ +$/gu, "")}…`;
}

function textCodePointLength(value) {
  return Array.from(String(value ?? "")).length;
}

function countCaseInsensitive(value, marker) {
  return String(value ?? "").toLocaleLowerCase("en-US")
    .split(String(marker || "").toLocaleLowerCase("en-US")).length - 1;
}

function trimAsciiWhitespace(value) {
  return String(value ?? "")
    .replace(/^[ \t\r\n\f\v]+/gu, "")
    .replace(/[ \t\r\n\f\v]+$/gu, "");
}

function cleanAiResearchHumanText(value) {
  return trimAsciiWhitespace(
    String(value ?? "").replace(/[ \t\r\n\f\v]+/gu, " "),
  );
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

function generationResearchDecision(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const entries = [
    ["Решение", value.strategy, 3],
    ["Конкуренты", value.competitors, 1],
    ["Тренды", value.trends, 1],
    ["Категория", value.category, 1],
    ["Источники", value.sources, 1],
  ].flatMap(([label, rawValue, weight]) => {
    const text = cleanResearchDecision(rawValue);
    return text ? [{ label, text, weight: Number(weight), budget: 0 }] : [];
  });
  if (!entries.length) return "";

  const overhead = entries.reduce(
    (total, entry) => total + entry.label.length + 2,
    Math.max(0, entries.length - 1) * 2,
  );
  let remaining = Math.max(0, 420 - overhead);
  const guaranteed = Math.min(48, Math.floor(remaining / entries.length));
  for (const entry of entries) {
    entry.budget = Math.min(entry.text.length, guaranteed);
    remaining -= entry.budget;
  }
  while (remaining > 0) {
    const expandable = entries.filter((entry) => entry.budget < entry.text.length);
    if (!expandable.length) break;
    const totalWeight = expandable.reduce((total, entry) => total + entry.weight, 0);
    let progressed = false;
    for (const entry of expandable) {
      const share = Math.max(1, Math.floor(remaining * entry.weight / totalWeight));
      const grant = Math.min(share, entry.text.length - entry.budget, remaining);
      if (grant < 1) continue;
      entry.budget += grant;
      remaining -= grant;
      progressed = true;
      if (remaining < 1) break;
    }
    if (!progressed) break;
  }

  const parts = entries.map((entry) => {
    const text = entry.text.length <= entry.budget
      ? entry.text
      : `${entry.text.slice(0, Math.max(1, entry.budget - 1)).trimEnd()}…`;
    return `${entry.label}: ${text}`;
  });
  return cleanResearchDecision(parts.join("; "));
}

function cleanResearchDecision(value) {
  const withoutUrls = cleanText(value).replace(
    /https?:\/\/[^\s]+/giu,
    "[ссылка исключена из промпта]",
  );
  return truncateScenarioIntent(withoutUrls, 420);
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
  if (normalized.includes("ozon") || normalized.includes("озон")) return "";
  if (normalized.includes("youtube")) return "youtube";
  if (normalized.includes("vk") || normalized.includes("вк")) return "vk";
  if (normalized.includes("tiktok") || normalized.includes("тик")) return "tiktok";
  if (normalized.includes("telegram")) return "telegram";
  if (normalized.includes("wildberries")) return "wildberries";
  return "instagram";
}
