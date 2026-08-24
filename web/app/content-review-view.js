const ACTIVE_STATUSES = new Set(["queued", "starting", "processing", "running"]);
const READY_STATUSES = new Set(["completed", "succeeded", "ready"]);
const FAILED_STATUSES = new Set(["failed", "cancelled"]);
const MAX_FINDINGS = 80;
const MAX_RECOMMENDATIONS = 40;
const MAX_FRAME_CHARACTERS = 330_000;
const MAX_TOTAL_FRAME_CHARACTERS = 1_650_000;
const FRAME_SAMPLE_SIZE = 48;
const MAX_AUDIO_SOURCE_BYTES = 52_428_800;
const AUDIO_ANALYSIS_TIMEOUT_MS = 20_000;
const AUDIO_SILENCE_DBFS = -50;
const MAX_AUDIO_ANALYSIS_SAMPLES = 480_000;
const MAX_AUDIO_SILENCE_WINDOWS = 2_000;
const MIN_TEMPORAL_SCAN_FRAMES = 12;
const MAX_TEMPORAL_SCAN_FRAMES = 24;
const TEMPORAL_SCAN_FRAMES_PER_SECOND = 4;
const TEMPORAL_SCAN_MIN_COVERAGE = 0.9;
const TEMPORAL_SCAN_TIMEOUT_MS = 30_000;
const TEMPORAL_BLACK_LUMA = 16;
const TEMPORAL_FROZEN_DIFFERENCE = 0.015;
const TIMELINE_ATLAS_MAX_DIMENSION = 1_280;
const TIMELINE_ATLAS_GAP = 2;
const TIMELINE_ATLAS_LABEL_HEIGHT = 18;
const TIMELINE_ATLAS_DENSE_MAX_DURATION_SECONDS = 10;
const TIMELINE_ATLAS_DENSE_MAX_GAP_SECONDS = 0.5;
const CONTINUITY_SCAN_MAX_DURATION_SECONDS = 15;
const CONTINUITY_SCAN_MAX_FRAMES = 3_600;
const CONTINUITY_SCAN_TIMEOUT_PADDING_MS = 10_000;
const CONTINUITY_SCAN_MIN_COVERAGE = 0.8;
const CONTINUITY_SCAN_MAX_GAP_SECONDS = 0.5;
const CONTINUITY_DUPLICATE_DIFFERENCE = 0.0015;
const CONTINUITY_DENSE_SEEK_SAMPLES_PER_SECOND = 10;
const CONTINUITY_DENSE_SEEK_MIN_SAMPLES = 16;
const CONTINUITY_DENSE_SEEK_MAX_SAMPLES = 151;
const CONTINUITY_DENSE_SEEK_TIMEOUT_MS = 45_000;
const CONTINUITY_DENSE_SEEK_MAX_TARGET_DRIFT_SECONDS = 0.02;
const CONTINUITY_DENSE_SEEK_MAX_GAP_SECONDS = 0.125;
const CONTINUITY_DENSE_SEEK_FALLBACK_REASONS = new Set([
  "rvfc_unavailable",
  "rvfc_coverage_unreliable",
  "rvfc_max_gap_unreliable",
  "rvfc_missed_frames",
]);
const CONTENT_REVIEW_DECISION_VIDEO_MAX_HEIGHT = 420;
export const MAX_CONTENT_REVIEW_IMAGE_SELECTION = 5;
export const GENERATED_VIDEO_SOUND_ISSUE_CODES = Object.freeze([
  "slurred_words",
  "wrong_words",
  "foreign_accent",
  "numbers_units",
  "wrong_voice_tone",
  "lip_sync",
  "noise_clipping",
  "silence_dropout",
  "unexpected_audio",
  "other",
]);
const GENERATED_VIDEO_SOUND_ISSUE_CODE_SET = new Set(
  GENERATED_VIDEO_SOUND_ISSUE_CODES,
);
const GENERATED_VIDEO_SOUND_ISSUE_LABELS = Object.freeze({
  slurred_words: "Слова или окончания проглочены",
  wrong_words: "Слова заменены, добавлены или произнесены неверно",
  foreign_accent: "Нежелательный акцент или неестественное произношение",
  numbers_units: "Искажены числа, градусы, единицы или названия",
  wrong_voice_tone: "Не тот дикторский тон, темп или характер голоса",
  lip_sync: "Речь не совпадает с движением губ или действием",
  noise_clipping: "Шум, перегруз, треск или неприятная громкость",
  silence_dropout: "Провалы, обрывы или неожиданная тишина",
  unexpected_audio: "В немом режиме неожиданно появились речь, музыка или шум",
  other: "Другая проблема звука",
});
const GENERATED_VIDEO_SOUND_CLEAR_CONFIRMATIONS = Object.freeze([
  "spokenScriptHeardExactlyConfirmed",
  "dictionClearConfirmed",
  "voiceStyleConfirmed",
  "audioSyncConfirmed",
]);

export function validateGeneratedVideoSoundAssessment(
  value,
  { audioExpected = true, decision = "" } = {},
) {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
  const status = String(source.status || "").trim().toLowerCase();
  const issueCodes = [...new Set(
    (Array.isArray(source.issueCodes) ? source.issueCodes : [])
      .map((item) => String(item || "").trim().toLowerCase())
      .filter((item) => GENERATED_VIDEO_SOUND_ISSUE_CODE_SET.has(item)),
  )];
  const approval = ["approved", "approve_with_context"].includes(
    String(decision || "").trim().toLowerCase(),
  );
  if (audioExpected === false) {
    if (status === "issues_found") {
      if (!issueCodes.includes("unexpected_audio")) {
        return { valid: false, code: "sound_unexpected_audio_code_required" };
      }
      if (String(source.note || "").trim().length < 5) {
        return { valid: false, code: "sound_issue_note_required" };
      }
      if (source.silenceExpectedConfirmed === true) {
        return { valid: false, code: "sound_silent_issue_conflict" };
      }
      if (approval) {
        return { valid: false, code: "sound_issues_block_approval" };
      }
      return { valid: true, code: "sound_issues_recorded" };
    }
    if (status !== "silent_expected" || source.silenceExpectedConfirmed !== true) {
      return { valid: false, code: "sound_silence_confirmation_required" };
    }
    if (issueCodes.length > 0) {
      return { valid: false, code: "sound_silent_issue_conflict" };
    }
    return { valid: true, code: "sound_silent_confirmed" };
  }
  if (status === "issues_found") {
    if (issueCodes.length < 1) {
      return { valid: false, code: "sound_issue_code_required" };
    }
    if (String(source.note || "").trim().length < 5) {
      return { valid: false, code: "sound_issue_note_required" };
    }
    if (approval) {
      return { valid: false, code: "sound_issues_block_approval" };
    }
    return { valid: true, code: "sound_issues_recorded" };
  }
  if (status !== "clear") {
    return { valid: false, code: "sound_assessment_required" };
  }
  if (issueCodes.length > 0) {
    return { valid: false, code: "sound_clear_issue_conflict" };
  }
  if (GENERATED_VIDEO_SOUND_CLEAR_CONFIRMATIONS.some(
    (key) => source[key] !== true,
  )) {
    return { valid: false, code: "sound_clear_confirmation_required" };
  }
  return { valid: true, code: "sound_clear_confirmed" };
}
const GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES = new Set([
  "CONTEXT.GENERATED_PROVENANCE",
  "AD.MARKING.LABEL",
  "AD.MARKING.ADVERTISER",
  "AD.MARKING.ERID",
  "AD.ORD_ACK",
  "PUBLISHER.RKN_10K",
  "RIGHTS.MEDIA",
  "PERSON.IMAGE_RELEASE",
  "PERSON.PRESENCE_UNRESOLVED",
  "CLAIM.OUTPUT_NOT_CONFIRMED",
  "YOUTUBE.AI_DISCLOSURE",
  "BAA.DISCLAIMER",
]);
const GENERATED_VIDEO_CONTEXT_RESOLVABLE_CODES = new Set([
  ...GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES,
  "ACCESSIBILITY.CAPTIONS",
]);

const PLATFORM_LABELS = Object.freeze({
  instagram: "Instagram",
  youtube: "YouTube",
  vk: "VK",
  tiktok: "TikTok",
  telegram: "Telegram",
  wildberries: "Wildberries",
  other: "Другая площадка",
});

const PLATFORM_SAFE_ZONE_GUIDES = Object.freeze({
  instagram: Object.freeze({
    label: "Instagram Reels",
    sourceUrl: "https://www.facebook.com/business/ads/facebook-instagram-reels-ads",
  }),
  tiktok: Object.freeze({
    label: "TikTok",
    sourceUrl: "https://ads.tiktok.com/help/article/tiktok-interactive-add-on-download-card-ad-specifications?lang=en",
  }),
  youtube: Object.freeze({
    label: "YouTube Shorts",
    sourceUrl: "https://support.google.com/youtube/answer/16215842",
  }),
  vk: Object.freeze({
    label: "VK Клипы",
    sourceUrl: "",
  }),
});

const CONTENT_KIND_LABELS = Object.freeze({
  unknown: "Статус ещё не определён",
  informational: "Информационный / редакционный материал",
  advertising: "Реклама",
});

const PRODUCT_CATEGORY_LABELS = Object.freeze({
  cosmetics: "Косметика и уход",
  baa: "БАД — зарегистрированный БАД",
  sports_food: "Протеин и спортивное питание",
  food: "Еда и напитки",
  household: "Товары для дома",
  apparel: "Одежда и аксессуары",
  electronics: "Электроника",
  other: "Другая категория",
});

const COMPLIANCE_META = Object.freeze({
  block: Object.freeze({
    label: "Публикация заблокирована",
    short: "Блок",
    tone: "block",
    description: "Есть критические риски. Исправьте их и запустите новую проверку.",
  }),
  human_review: Object.freeze({
    label: "Нужно решение человека",
    short: "Проверить",
    tone: "review",
    description: "Автоматическая проверка не может безопасно принять финальное решение.",
  }),
  pass_with_warnings: Object.freeze({
    label: "Можно рассматривать к публикации",
    short: "Предупреждения",
    tone: "warning",
    description: "Критических блокеров не найдено, но замечания нужно прочитать до публикации.",
  }),
  pass: Object.freeze({
    label: "Критических рисков не найдено",
    short: "Пройдено",
    tone: "pass",
    description: "Финальное решение всё равно принимает ответственный участник команды.",
  }),
});

const SOURCE_LABELS = Object.freeze({
  none: "Внутренняя проверка качества",
  ad_law_38fz: "Федеральный закон № 38-ФЗ «О рекламе»",
  ad_definition_1087: "Критерии отнесения информации к рекламе, постановление № 1087",
  restricted_resources_72fz: "Федеральный закон № 72-ФЗ об ограничении рекламы на отдельных ресурсах",
  erid_order_68: "Приказ Роскомнадзора № 68 о присвоении идентификатора рекламы",
  ord_rules_974: "Правила передачи сведений об интернет-рекламе через ОРД",
  publisher_registry_238: "Требования к каналам с аудиторией более 10 000 подписчиков",
  personal_data_152fz: "Федеральный закон № 152-ФЗ «О персональных данных»",
  image_rights_152_1: "Статья 152.1 ГК РФ об охране изображения гражданина",
  cosmetics_tr_ts_009: "ТР ТС 009/2011 о безопасности парфюмерно-косметической продукции",
  food_label_tr_ts_022: "ТР ТС 022/2011 о маркировке пищевой продукции",
  youtube_synthetic: "Правила YouTube о раскрытии синтетического и изменённого контента",
});

const SOURCE_URLS = Object.freeze({
  ad_law_38fz: "https://government.ru/docs/all/98086/",
  ad_definition_1087: "https://publication.pravo.gov.ru/document/0001202507250057",
  restricted_resources_72fz: "https://publication.pravo.gov.ru/document/0001202504070018",
  erid_order_68: "https://publication.pravo.gov.ru/document/0001202504140029",
  ord_rules_974: "https://publication.pravo.gov.ru/document/0001202205300041",
  publisher_registry_238: "https://publication.pravo.gov.ru/document/0001202412300041",
  personal_data_152fz: "https://government.ru/docs/all/98196/",
  image_rights_152_1: "https://government.ru/docs/all/95825/?page=18",
  cosmetics_tr_ts_009: "https://eec.eaeunion.org/comission/department/deptexreg/tr/bezopParfum.php",
  food_label_tr_ts_022: "https://eec.eaeunion.org/comission/department/deptexreg/tr/PischevkaMarkirovka.php",
  youtube_synthetic: "https://support.google.com/youtube/answer/14328491",
});

export function contentReviewStatusKind(value) {
  const status = String(value || "queued").trim().toLowerCase();
  if (ACTIVE_STATUSES.has(status)) return "active";
  if (READY_STATUSES.has(status)) return "ready";
  if (FAILED_STATUSES.has(status)) return "failed";
  return "unknown";
}

export function contentReviewIsBusy(phase, run) {
  return [
    "preparing",
    "saving_evidence",
    "queueing",
    "starting",
    "refreshing",
    "deciding",
  ].includes(phase) || Boolean(
    run && contentReviewStatusKind(run.status) === "active",
  );
}

export function normalizeContentReviewCatalog(raw) {
  const source = unwrap(raw);
  const media = arrayFrom(source, "media", "media_items", "artifacts")
    .map(normalizeMedia)
    .filter((item) => item.id && item.supported);
  const mediaById = new Map(media.map((item) => [item.id, item]));
  const rulesetVersion = text(source.ruleset_version || source.rulesetVersion || source.ruleset?.version, 180);
  const runs = arrayFrom(source, "runs", "recent_reviews", "reviews", "history", "items")
    .map((item) => normalizeContentReviewRun(item, null, mediaById))
    .map((item) => ({ ...item, rulesetVersion: item.rulesetVersion || rulesetVersion }))
    .filter((item) => item.id)
    .sort((left, right) => dateValue(right.createdAt) - dateValue(left.createdAt));
  return {
    media,
    runs,
    rulesetVersion,
  };
}

export function normalizeContentReviewRun(raw, previous = null, mediaById = null) {
  const envelope = unwrap(raw);
  const source = objectFrom(envelope.run) || objectFrom(envelope.review) || envelope;
  const rawResult = source.result || envelope.result || source.result_summary || envelope.result_summary;
  const result = rawResult ? normalizeResult(rawResult) : previous?.result || normalizeResult(null);
  const topLevelInput = source.media_id || source.platform || source.content_kind || source.product_category
    ? {
        media_id: source.media_id,
        platform: source.platform,
        content_kind: source.content_kind,
        product_category: source.product_category,
      }
    : null;
  const input = objectFrom(source.input)
    || objectFrom(source.request)
    || topLevelInput
    || previous?.input
    || {};
  const decisionSource = objectFrom(envelope.decision) || objectFrom(source.decision) || previous?.decision || null;
  const soundAssessmentSource = objectFrom(envelope.sound_assessment)
    || objectFrom(envelope.soundAssessment)
    || objectFrom(source.sound_assessment)
    || objectFrom(source.soundAssessment)
    || objectFrom(decisionSource?.sound_assessment)
    || objectFrom(decisionSource?.soundAssessment)
    || previous?.soundAssessment
    || null;
  const assignmentSource = objectFrom(
    source.independent_assignment
    || source.independentAssignment
    || envelope.independentAssignment
    || envelope.independent_assignment,
  );
  const repairNextActionSource = objectFrom(
    source.repair_next_action
    || envelope.repair_next_action,
  );
  const mediaSource = objectFrom(envelope.media) || objectFrom(source.media);
  const mediaId = text(
    source.media_id || input.media_id || mediaSource?.id || previous?.mediaId,
    180,
  );
  const catalogMedia = mediaById instanceof Map ? mediaById.get(mediaId) : null;
  const normalizedMedia = mediaSource ? normalizeMedia(mediaSource) : null;
  const media = normalizedMedia
    ? {
        ...(previous?.media || catalogMedia || {}),
        ...normalizedMedia,
        url: normalizedMedia.url || previous?.media?.url || catalogMedia?.url || "",
      }
    : catalogMedia || previous?.media || null;
  return {
    id: text(source.id || source.review_id || envelope.review_id || previous?.id, 180),
    status: text(source.status || previous?.status || "queued", 40).toLowerCase(),
    mediaId,
    media,
    mediaIsStale: Boolean(source.media_is_stale ?? source.mediaIsStale ?? previous?.mediaIsStale),
    input: normalizeInput(input),
    result,
    summaryOnly: Boolean(!source.result && !envelope.result && (source.result_summary || envelope.result_summary)),
    moderation: objectFrom(source.moderation) || objectFrom(envelope.moderation) || previous?.moderation || null,
    decision: decisionSource ? normalizeDecision(decisionSource) : null,
    soundAssessment: soundAssessmentSource
      ? normalizeSoundAssessment(soundAssessmentSource)
      : null,
    soundRecoveryEligible: (
      envelope.sound_recovery_eligible
      ?? envelope.soundRecoveryEligible
      ?? source.sound_recovery_eligible
      ?? source.soundRecoveryEligible
      ?? previous?.soundRecoveryEligible
    ) === true,
    independentAssignment: assignmentSource
      ? normalizeIndependentAssignment(assignmentSource)
      : previous?.independentAssignment || null,
    repairNextAction: repairNextActionSource
      ? normalizeGenerationRepairNextAction(repairNextActionSource)
      : previous?.repairNextAction || null,
    rulesetVersion: text(
      source.ruleset_version || source.rulesetVersion
      || envelope.ruleset_version || envelope.rulesetVersion
      || result.rulesetVersion || previous?.rulesetVersion,
      180,
    ),
    failureMessage: text(
      source.failure_message || source.failureMessage
      || source.error_message || source.errorMessage
      || envelope.failure_message || envelope.failureMessage
      || previous?.failureMessage,
      1000,
    ),
    version: positiveInteger(source.version || source.lock_version || previous?.version, 1),
    createdAt: source.created_at || source.createdAt || previous?.createdAt || null,
    updatedAt: source.updated_at || source.updatedAt || previous?.updatedAt || null,
    completedAt: source.completed_at || source.completedAt
      || source.finished_at || source.finishedAt
      || previous?.completedAt || null,
  };
}

function normalizeIndependentAssignment(raw) {
  const status = text(raw.status, 40).toLowerCase();
  if (!["unassigned", "assigned", "completed", "cancelled"].includes(status)) {
    return null;
  }
  return {
    status,
    assignedToMe: (raw.assigned_to_me ?? raw.assignedToMe) === true,
    decisionEligible: (raw.decision_eligible ?? raw.decisionEligible) === true,
    assignedAt: raw.assigned_at || raw.assignedAt || null,
    completedAt: raw.completed_at || raw.completedAt || null,
  };
}

export function contentReviewDecisionAllowed(role, run = null) {
  const normalizedRole = String(role || "").trim().toLowerCase();
  if (["owner", "admin", "producer", "reviewer"].includes(normalizedRole)) {
    return true;
  }
  if (normalizedRole !== "operator") return false;
  const assignment = run?.independentAssignment;
  return assignment?.status === "assigned"
    && assignment.assignedToMe === true
    && assignment.decisionEligible === true;
}

function normalizeGenerationRepairNextAction(raw) {
  const status = text(raw.status, 40).toLowerCase();
  if (!["available", "started", "in_progress", "succeeded", "failed"].includes(status)) {
    return null;
  }
  return {
    status,
    canPrepare: raw.can_prepare === true,
    startedAt: raw.started_at || null,
  };
}

export function contentReviewHasBlockers(run) {
  if (!run) return false;
  if (run.result.complianceStatus === "block") return true;
  if (run.result.blockersCount > 0) return true;
  return run.result.findings.some((item) => item.severity === "blocker");
}

export function generatedImageApprovalContextReady(run) {
  if (run?.media?.kind !== "generated_image") return true;
  const input = run.input || {};
  const researchClaimsBound = input.generationClaimEvidence?.status === "bound";
  return Boolean(
    input.generationJobId
    && ["tiktok", "youtube", "vk", "telegram", "wildberries"].includes(input.platform)
    && input.contentKind === "advertising"
    && input.aiGenerated
    && input.externalAiProcessingConfirmed
    && input.adLabelConfirmed
    && input.ordConfirmed
    && input.advertiserName.length >= 2
    && input.erid.length >= 6
    && input.rightsConfirmed
    && (input.claimsVerified || researchClaimsBound)
    && input.productCategoryVerified
    && input.productCategorySource === "product_metadata"
    && (input.platform !== "youtube" || input.aiDisclosureConfirmed)
    && (input.productCategory !== "baa" || input.mandatoryWarningConfirmed)
    && (!input.audienceOver10000 || input.rknRegistered)
  );
}

export function generatedImageContextCanApprove(run) {
  if (
    run?.media?.kind !== "generated_image"
    || generatedImageApprovalContextReady(run)
    || !run?.result
  ) return false;
  const blockers = run.result.findings.filter((item) => item.severity === "blocker");
  return blockers.length === run.result.blockersCount
    && blockers.every((item) => GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES.has(item.code));
}

export function generatedMediaApprovalContextReady(run) {
  if (run?.media?.kind === "generated_image") {
    return generatedImageApprovalContextReady(run);
  }
  if (run?.media?.kind !== "generated_video") return true;
  const input = run.input || {};
  const researchClaimsBound = input.generationClaimEvidence?.status === "bound";
  const captionsRequired = true;
  return Boolean(
    input.generationJobId
    && ["tiktok", "youtube", "vk", "telegram", "wildberries"].includes(input.platform)
    && input.contentKind === "advertising"
    && input.aiGenerated
    && input.adLabelConfirmed
    && input.ordConfirmed
    && input.advertiserName.length >= 2
    && input.erid.length >= 6
    && input.rightsConfirmed
    && (input.claimsVerified || researchClaimsBound)
    && (!captionsRequired || input.captionsConfirmed)
    && input.productCategoryVerified
    && input.productCategorySource === "product_metadata"
    && (input.platform !== "youtube" || input.aiDisclosureConfirmed)
    && (input.productCategory !== "baa" || input.mandatoryWarningConfirmed)
    && (!input.audienceOver10000 || input.rknRegistered)
  );
}

export function generatedMediaContextCanApprove(run) {
  const kind = run?.media?.kind;
  if (
    !["generated_image", "generated_video"].includes(kind)
    || generatedMediaApprovalContextReady(run)
    || !run?.result
  ) return false;
  const codes = kind === "generated_video"
    ? GENERATED_VIDEO_CONTEXT_RESOLVABLE_CODES
    : GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES;
  const blockers = run.result.findings.filter((item) => item.severity === "blocker");
  return blockers.length === run.result.blockersCount
    && blockers.every((item) => codes.has(item.code));
}

export function generatedMediaPostContextRequiredRiskCodes(run) {
  const codes = run?.media?.kind === "generated_video"
    ? GENERATED_VIDEO_CONTEXT_RESOLVABLE_CODES
    : GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES;
  const remaining = (run?.result?.findings || []).filter(
    (item) => !codes.has(item.code),
  );
  const required = [...new Set(
    remaining
      .filter((item) => item.code && (item.severity === "blocker" || item.severity === "high" || item.humanReviewRequired))
      .map((item) => item.code),
  )];
  if (
    run?.media?.kind !== "generated_video"
    &&
    !required.length
    && remaining.some((item) => item.severity === "medium")
  ) {
    return ["general_human_review"];
  }
  return required;
}

export function generatedImagePostContextRequiredRiskCodes(run) {
  const remaining = (run?.result?.findings || []).filter(
    (item) => !GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES.has(item.code),
  );
  const required = [...new Set(
    remaining
      .filter((item) => item.code && (item.severity === "blocker" || item.severity === "high" || item.humanReviewRequired))
      .map((item) => item.code),
  )];
  if (
    !required.length
    && remaining.some((item) => item.severity === "medium")
  ) {
    return ["general_human_review"];
  }
  return required;
}

export function contentReviewRequiredRiskCodes(run) {
  if (!run?.result) return [];
  const required = [...new Set(
    run.result.findings
      .filter((item) => item.code && (item.severity === "high" || item.humanReviewRequired))
      .map((item) => item.code),
  )];
  if (!required.length && run.result.complianceStatus === "human_review") {
    return ["general_human_review"];
  }
  return required;
}

export function contentReviewWorkspaceMarkup({
  catalog,
  currentRun = null,
  phase = "idle",
  error = "",
  notice = "",
  canDecide = false,
  view = "",
  restorePlacement = false,
} = {}) {
  const normalized = catalog || { media: [], runs: [] };
  const selected = currentRun
    ? normalizeContentReviewRun(currentRun)
    : normalized.runs.find((item) => contentReviewStatusKind(item.status) === "active")
      || normalized.runs[0]
      || null;
  const busy = contentReviewIsBusy(phase, null);
  const activeView = ["new", "current", "history"].includes(view)
    ? view
    : currentRun
      ? "current"
      : "new";
  const activeMediaIds = new Set(
    normalized.runs
      .filter((item) => contentReviewStatusKind(item.status) === "active")
      .map((item) => item.mediaId)
      .filter(Boolean),
  );
  const viewMeta = {
    new: {
      eyebrow: "Проверка · действие 1 из 2",
      title: "Подготовьте одну проверку",
      description: "Портал покажет только текущий подпункт. После запуска форма сменится результатом — без второго окна. Это фильтр рисков, а не автоматическая юридическая экспертиза.",
    },
    current: {
      eyebrow: "Проверка · действие 2 из 2",
      title: "Проверьте результат и примите решение",
      description: "После одобрения портал плавно откроет следующий этап — «Опубликовать».",
    },
    history: {
      eyebrow: "Проверка · архив",
      title: "Ранее проверенные материалы",
      description: "История отделена от текущего действия и ничего не открывает поверх рабочего экрана.",
    },
  }[activeView];
  return `
    <section class="content-review-stage-head" aria-labelledby="content-review-stage-title">
      <div>
        <p class="eyebrow">${escapeHtml(viewMeta.eyebrow)}</p>
        <h2 id="content-review-stage-title">${escapeHtml(viewMeta.title)}</h2>
        <p>${escapeHtml(viewMeta.description)}</p>
      </div>
      <span class="content-review-stage-head__rule">Одно окно · одно действие</span>
    </section>
    ${notice ? messageMarkup(notice, "success") : ""}
    ${error ? messageMarkup(error, "danger") : ""}
    <div class="content-review-single-action" data-content-review-action="${activeView}">
      ${activeView === "history"
        ? reviewHistoryMarkup(normalized.runs, selected?.id)
        : activeView === "current" || busy
          ? `<section class="content-review-output" aria-live="polite">${reviewCurrentMarkup(selected, { phase, canDecide, restorePlacement })}</section>`
          : reviewFormMarkup(normalized.media, busy, activeMediaIds)}
    </div>
  `;
}

export function readContentReviewForm(form) {
  const values = new FormData(form);
  const mediaIds = [...new Set(
    values.getAll("media_id").map((value) => text(value, 180)).filter(Boolean),
  )];
  return {
    media_ids: mediaIds,
    media_id: mediaIds[0] || "",
    platform: stringValue(values, "platform"),
    content_kind: stringValue(values, "content_kind"),
    product_category: stringValue(values, "product_category"),
    caption_text: stringValue(values, "caption_text"),
    script_text: stringValue(values, "script_text"),
    advertiser_name: stringValue(values, "advertiser_name"),
    erid: stringValue(values, "erid"),
    rights_confirmed: values.get("rights_confirmed") === "yes",
    claims_verified: values.get("claims_verified") === "yes",
    ad_label_confirmed: values.get("ad_label_confirmed") === "yes",
    ord_confirmed: values.get("ord_confirmed") === "yes",
    audience_over_10000: values.get("audience_over_10000") === "yes",
    rkn_registered: values.get("rkn_registered") === "yes",
    people_present: stringValue(values, "people_present") || "unknown",
    person_consent_confirmed: values.get("person_consent_confirmed") === "yes",
    external_ai_processing_confirmed: values.get("external_ai_processing_confirmed") === "yes",
    ai_generated: values.get("ai_generated") === "yes",
    ai_disclosure_confirmed: values.get("ai_disclosure_confirmed") === "yes",
    captions_confirmed: values.get("captions_confirmed") === "yes",
    mandatory_warning_confirmed: values.get("mandatory_warning_confirmed") === "yes",
  };
}

export function readContentReviewDecision(form, submitter) {
  const values = new FormData(form);
  return {
    decision: text(submitter?.value || submitter?.dataset?.decision || "", 40),
    reason: stringValue(values, "reason"),
    resolvedRecommendationCodes: values.getAll("resolved_recommendation_codes").map((value) => text(value, 120)).filter(Boolean),
    riskAcknowledgements: values.getAll("risk_acknowledgements").map((value) => text(value, 120)).filter(Boolean),
    mediaWatchedConfirmed: values.get("media_watched_confirmed") === "yes",
    soundAssessment: {
      status: stringValue(values, "sound_status").toLowerCase(),
      issueCodes: values.getAll("sound_issue_codes")
        .map((value) => text(value, 80).toLowerCase())
        .filter((value) => GENERATED_VIDEO_SOUND_ISSUE_CODE_SET.has(value)),
      spokenScriptHeardExactlyConfirmed:
        values.get("spoken_script_heard_exactly_confirmed") === "yes",
      dictionClearConfirmed:
        values.get("diction_clear_confirmed") === "yes",
      voiceStyleConfirmed:
        values.get("voice_style_confirmed") === "yes",
      audioSyncConfirmed:
        values.get("audio_sync_confirmed") === "yes",
      silenceExpectedConfirmed:
        values.get("silence_expected_confirmed") === "yes",
      note: stringValue(values, "sound_note"),
    },
    generatedPhotoContext: {
      productCategory: stringValue(values, "release_product_category"),
      advertiserName: stringValue(values, "release_advertiser_name"),
      erid: stringValue(values, "release_erid"),
      peoplePresent: stringValue(values, "release_people_present"),
      adLabelConfirmed: values.get("release_ad_label_confirmed") === "yes",
      ordConfirmed: values.get("release_ord_confirmed") === "yes",
      rightsConfirmed: values.get("release_rights_confirmed") === "yes",
      claimsVerified: values.get("release_claims_verified") === "yes",
      captionsConfirmed: values.get("release_captions_confirmed") === "yes",
      captionsRequired: form.dataset.releaseCaptionsRequired === "true",
      personConsentConfirmed: values.get("release_person_consent_confirmed") === "yes",
      aiDisclosureConfirmed: values.get("release_ai_disclosure_confirmed") === "yes",
      mandatoryWarningConfirmed: values.get("release_mandatory_warning_confirmed") === "yes",
      audienceOver10000: values.get("release_audience_over_10000") === "yes",
      rknRegistered: values.get("release_rkn_registered") === "yes",
    },
  };
}

export function syncContentReviewFormVisibility(form) {
  if (!form) return;
  const advertising = String(form.elements.content_kind?.value || "unknown") === "advertising";
  const baa = String(form.elements.product_category?.value || "other") === "baa";
  const peopleMayBePresent = String(form.elements.people_present?.value || "unknown") !== "no";
  const selectedVideo = Array.from(
    form.querySelectorAll('input[name="media_id"]:checked'),
  ).some((item) => item.dataset.mediaType === "video");
  const aiGenerated = form.elements.ai_generated?.checked === true;
  const largeAudience = form.elements.audience_over_10000?.checked === true;
  toggleConditional(form, "[data-review-advertising]", advertising);
  toggleConditional(form, "[data-review-baa]", baa);
  toggleConditional(form, "[data-review-person-consent]", peopleMayBePresent);
  toggleConditional(form, "[data-review-external-ai]", peopleMayBePresent || selectedVideo);
  toggleConditional(form, "[data-review-ai-disclosure]", aiGenerated);
  toggleConditional(form, "[data-review-rkn]", largeAudience);
}

const CONTENT_REVIEW_WIZARD_STEPS = Object.freeze([
  "выберите один MP4 или до пяти фото",
  "укажите площадку и контекст публикации",
  "подтвердите права, факты и обязательные реквизиты",
  "проверьте итог и запустите проверку",
]);

const CONTENT_REVIEW_WIZARD_HEADINGS = Object.freeze([
  Object.freeze({ title: "Какой файл проверяем?", description: "Выберите один MP4 или до пяти фото одного товара. Остальные поля появятся после выбора." }),
  Object.freeze({ title: "Где и как это опубликуем?", description: "Укажите площадку, тип материала и товар. Неизвестный рекламный статус можно честно оставить неизвестным." }),
  Object.freeze({ title: "Что точно подтверждено?", description: "Отметьте только факты, которые человек действительно проверил: права, обещания, титры и обязательные реквизиты." }),
  Object.freeze({ title: "Запустить одну проверку?", description: "Проверьте итог. После запуска эта форма сменится экраном результата — второе окно не откроется." }),
]);

function syncContentReviewWizardMediaCount(form) {
  const count = form.querySelector("[data-content-review-media-count]");
  if (!count) return;
  const selected = Array.from(
    form.querySelectorAll('input[name="media_id"]:not(:disabled):checked'),
  );
  count.textContent = selected.length
    ? selected[0]?.dataset.mediaType === "video"
      ? "Выбран 1 MP4"
      : `Выбрано ${selected.length} из ${MAX_CONTENT_REVIEW_IMAGE_SELECTION}`
    : "Ничего не выбрано";
}

function scrollContentReviewWizardToStart(form) {
  const owner = form.closest("#main-content");
  const behavior = prefersReducedMotion() ? "auto" : "smooth";
  if (owner instanceof HTMLElement) {
    const ownerRect = owner.getBoundingClientRect();
    const formRect = form.getBoundingClientRect();
    const top = owner.scrollTop + formRect.top - ownerRect.top - 12;
    owner.scrollTo({ top: Math.max(0, top), behavior });
    return;
  }
  form.scrollIntoView({ block: "start", behavior });
}

export function hydrateContentReviewWizard(form, { focus = false } = {}) {
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-content-review-wizard]")) return false;
  if (form.dataset.reviewWizardBound !== "true") {
    form.dataset.reviewWizardBound = "true";
    form.addEventListener("click", (event) => {
      const control = event.target.closest?.('[data-action="content-review-wizard-step"]');
      if (!(control instanceof HTMLButtonElement) || !form.contains(control)) return;
      event.preventDefault();
      setContentReviewWizardStep(form, Number(control.dataset.reviewStep), { focus: true });
    });
    form.addEventListener("change", (event) => {
      const control = event.target;
      if (control instanceof HTMLInputElement && control.name === "media_id") {
        syncContentReviewWizardMediaCount(form);
      }
    });
  }
  syncContentReviewWizardMediaCount(form);
  return setContentReviewWizardStep(form, Number(form.dataset.reviewStep) || 1, {
    focus,
    validate: false,
  });
}

export function setContentReviewWizardStep(form, requestedStep, {
  focus = true,
  validate = true,
} = {}) {
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-content-review-wizard]")) return false;
  const currentStep = Math.max(1, Math.min(CONTENT_REVIEW_WIZARD_STEPS.length, Number(form.dataset.reviewStep) || 1));
  const nextStep = Math.max(1, Math.min(CONTENT_REVIEW_WIZARD_STEPS.length, Number(requestedStep) || 1));
  const status = form.querySelector("[data-review-wizard-status]");
  if (validate && nextStep > currentStep) {
    for (let step = currentStep; step < nextStep; step += 1) {
      const validation = validateContentReviewWizardStep(form, step);
      if (!validation.ok) {
        if (status) {
          status.textContent = validation.message;
          status.dataset.tone = "danger";
        }
        validation.control?.focus?.({ preventScroll: true });
        validation.control?.scrollIntoView?.({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
        return false;
      }
    }
  }
  form.dataset.reviewStep = String(nextStep);
  form.querySelectorAll("[data-review-wizard-panel]").forEach((panel) => {
    const active = Number(panel.dataset.reviewWizardPanel) === nextStep;
    panel.classList.toggle("is-current", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });
  form.querySelectorAll('.content-review-wizard [data-action="content-review-wizard-step"]').forEach((control) => {
    const step = Number(control.dataset.reviewStep);
    control.classList.toggle("is-current", step === nextStep);
    control.classList.toggle("is-complete", step < nextStep);
    if (step === nextStep) control.setAttribute("aria-current", "step");
    else control.removeAttribute("aria-current");
  });
  const marker = form.querySelector(".content-review-step");
  if (marker) marker.textContent = String(nextStep).padStart(2, "0");
  const heading = CONTENT_REVIEW_WIZARD_HEADINGS[nextStep - 1];
  const title = form.querySelector("[data-review-wizard-title]");
  const description = form.querySelector("[data-review-wizard-description]");
  if (title) title.textContent = heading.title;
  if (description) description.textContent = heading.description;
  if (status) {
    status.textContent = `Шаг ${nextStep} из ${CONTENT_REVIEW_WIZARD_STEPS.length} · ${CONTENT_REVIEW_WIZARD_STEPS[nextStep - 1]}.`;
    delete status.dataset.tone;
  }
  const panel = form.querySelector(`[data-review-wizard-panel="${nextStep}"]`);
  if (focus && panel) {
    panel.setAttribute("tabindex", "-1");
    requestAnimationFrame(() => {
      scrollContentReviewWizardToStart(form);
      panel.focus({ preventScroll: true });
    });
  }
  form.dispatchEvent(new CustomEvent("content-review:wizard-step", {
    bubbles: true,
    detail: { step: nextStep, total: CONTENT_REVIEW_WIZARD_STEPS.length },
  }));
  return true;
}

function validateContentReviewWizardStep(form, step) {
  if (step === 1) {
    const controls = Array.from(form.querySelectorAll('input[name="media_id"]:not(:disabled)'));
    if (!controls.some((control) => control.checked)) {
      return {
        ok: false,
        message: "Сначала выберите файл. Дальше портал откроет только контекст публикации.",
        control: controls[0] || null,
      };
    }
  }
  if (step === 2) {
    for (const name of ["platform", "content_kind", "product_category"]) {
      const control = form.elements.namedItem(name);
      if (!String(control?.value || "").trim()) {
        return { ok: false, message: "Заполните три поля контекста, чтобы перейти к подтверждениям.", control };
      }
    }
  }
  if (step === 3) {
    const requiredChecks = ["rights_confirmed", "claims_verified", "captions_confirmed"];
    const missing = requiredChecks
      .map((name) => form.elements.namedItem(name))
      .find((control) => control instanceof HTMLInputElement && !control.checked);
    if (missing) {
      return {
        ok: false,
        message: "Подтвердите права, факты и титры. Без этих трёх пунктов проверку запускать нельзя.",
        control: missing,
      };
    }
    const advertising = String(form.elements.namedItem("content_kind")?.value || "") === "advertising";
    if (advertising) {
      for (const name of ["advertiser_name", "erid"]) {
        const control = form.elements.namedItem(name);
        if (!String(control?.value || "").trim()) {
          return { ok: false, message: "Для рекламы укажите рекламодателя и ERID.", control };
        }
      }
    }
  }
  return { ok: true, message: "", control: null };
}

function prefersReducedMotion() {
  return globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
}

export async function captureContentReviewEvidence(media, { onProgress } = {}) {
  const source = normalizeMedia(media || {});
  if (!source.id || !source.url || !source.supported) {
    throw userError("Для выбранного материала нет свежей защищённой ссылки. Обновите раздел и выберите файл ещё раз.");
  }
  if (source.isVideo) {
    return captureVideoEvidence(source, onProgress);
  }
  return captureImageEvidence(source, onProgress);
}

export function resolveContentReviewMediaSelection(media, selectedIds) {
  const catalog = Array.isArray(media) ? media : [];
  const ids = [...new Set(
    (Array.isArray(selectedIds) ? selectedIds : [])
      .map((value) => text(value, 180))
      .filter(Boolean),
  )];
  if (!ids.length) {
    return {
      ok: false,
      code: "content_review_media_required",
      message: "Выберите хотя бы одно фото или один MP4.",
      items: [],
      mediaIds: [],
    };
  }
  if (ids.length > MAX_CONTENT_REVIEW_IMAGE_SELECTION) {
    return {
      ok: false,
      code: "content_review_media_limit",
      message: `Можно выбрать не более ${MAX_CONTENT_REVIEW_IMAGE_SELECTION} фото одного товара.`,
      items: [],
      mediaIds: ids,
    };
  }
  const byId = new Map(catalog.map((item) => [String(item?.id || ""), item]));
  const items = ids.map((id) => byId.get(id)).filter(Boolean);
  if (items.length !== ids.length || items.some((item) => !item.supported)) {
    return {
      ok: false,
      code: "content_review_media_stale",
      message: "Один из выбранных файлов больше недоступен. Обновите раздел и выберите файлы снова.",
      items: [],
      mediaIds: ids,
    };
  }
  const videos = items.filter((item) => item.isVideo);
  if (videos.length) {
    if (items.length !== 1) {
      return {
        ok: false,
        code: "content_review_video_single_only",
        message: "MP4 проверяется отдельно. Для пакетной проверки выберите только фотографии.",
        items: [],
        mediaIds: ids,
      };
    }
    return { ok: true, code: "ok", message: "", items, mediaIds: ids };
  }
  if (items.length > 1) {
    const productIds = items.map((item) => String(item.productId || "").trim());
    if (productIds.some((value) => !value) || new Set(productIds).size !== 1) {
      return {
        ok: false,
        code: "content_review_product_mismatch",
        message: "Пакетная проверка принимает только фото одного привязанного товара. Не смешивайте разные артикулы.",
        items: [],
        mediaIds: ids,
      };
    }
  }
  return { ok: true, code: "ok", message: "", items, mediaIds: ids };
}

export function syncContentReviewSafeZoneStage(media, { clear = false } = {}) {
  if (!(media instanceof HTMLVideoElement)) return false;
  const stage = media.closest("[data-content-review-safe-zone-stage]");
  if (!(stage instanceof HTMLElement)) return false;
  const clearGeometry = () => {
    stage.style.removeProperty("--content-review-exact-video-width");
    stage.style.removeProperty("--content-review-exact-video-ratio");
    delete stage.dataset.contentReviewSafeZoneGeometry;
  };
  if (
    clear
    || !Number.isFinite(media.videoWidth)
    || !Number.isFinite(media.videoHeight)
    || media.videoWidth <= 0
    || media.videoHeight <= 0
  ) {
    clearGeometry();
    return false;
  }
  const ratio = media.videoWidth / media.videoHeight;
  const boundedWidth = Math.max(
    1,
    Math.min(1280, CONTENT_REVIEW_DECISION_VIDEO_MAX_HEIGHT * ratio),
  );
  stage.style.setProperty(
    "--content-review-exact-video-width",
    `${round(boundedWidth, 3)}px`,
  );
  stage.style.setProperty(
    "--content-review-exact-video-ratio",
    `${media.videoWidth} / ${media.videoHeight}`,
  );
  stage.dataset.contentReviewSafeZoneGeometry = "ready";
  return true;
}

export async function buildContentReviewFrameFiles(evidence) {
  const frames = Array.isArray(evidence?.frames) ? evidence.frames : [];
  const metrics = evidence?.technical_metrics;
  const sourceType = String(metrics?.source_type || "").toLowerCase();
  const expectedCount = sourceType === "video"
    ? frames.length === 5
    : sourceType === "image"
      ? frames.length === 1
      : false;
  if (!expectedCount) {
    throw userError("Не удалось подготовить полный набор контрольных кадров.");
  }
  const sampledAt = Array.isArray(metrics?.sampled_at_seconds)
    ? metrics.sampled_at_seconds
    : [];
  const files = [];
  for (let index = 0; index < frames.length; index += 1) {
    const blob = jpegDataUriToBlob(frames[index]);
    const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    const sha256 = Array.from(
      new Uint8Array(digest),
      (byte) => byte.toString(16).padStart(2, "0"),
    ).join("");
    const timecode = Number(sampledAt[index] ?? 0);
    files.push({
      blob,
      sha256,
      sizeBytes: blob.size,
      timecodeSeconds: Number.isFinite(timecode) && timecode >= 0
        ? round(timecode, 3)
        : 0,
    });
  }
  return files;
}

function jpegDataUriToBlob(value) {
  const encoded = String(value || "");
  const match = /^data:image\/jpeg;base64,([a-z0-9+/=]+)$/iu.exec(encoded);
  if (!match || encoded.length < 100 || encoded.length > MAX_FRAME_CHARACTERS) {
    throw userError("Контрольный кадр имеет небезопасный формат или слишком большой размер.");
  }
  let binary;
  try {
    binary = atob(match[1]);
  } catch {
    throw userError("Контрольный кадр повреждён. Подготовьте выборку ещё раз.");
  }
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], { type: "image/jpeg" });
  if (blob.size < 128 || blob.size > 250_000) {
    throw userError("Контрольный кадр имеет недопустимый размер.");
  }
  return blob;
}

function reviewFormMarkup(media, busy, activeMediaIds = new Set()) {
  const supported = media.filter((item) => item.supported);
  return `
    <form id="content-review-form" class="card content-review-form" novalidate aria-busy="${busy ? "true" : "false"}" data-content-review-wizard data-review-step="1">
      <div class="content-review-form__header">
        <span class="content-review-step">01</span>
        <div><p class="eyebrow">Новая проверка</p><h2 data-review-wizard-title>Какой файл проверяем?</h2><p data-review-wizard-description>Выберите один MP4 или до пяти фото одного товара. Остальные поля появятся после выбора.</p></div>
      </div>
      <nav class="content-review-wizard" aria-label="Подпункты новой проверки">
        <button type="button" class="is-current" data-action="content-review-wizard-step" data-review-step="1" aria-current="step"><span>1</span><strong>Файл</strong></button>
        <button type="button" data-action="content-review-wizard-step" data-review-step="2"><span>2</span><strong>Контекст</strong></button>
        <button type="button" data-action="content-review-wizard-step" data-review-step="3"><span>3</span><strong>Подтверждения</strong></button>
        <button type="button" data-action="content-review-wizard-step" data-review-step="4"><span>4</span><strong>Запуск</strong></button>
      </nav>
      <p class="content-review-wizard__status" data-review-wizard-status role="status" aria-live="polite">Шаг 1 из 4 · выберите один MP4 или до пяти фото.</p>
      <section class="content-review-wizard__panel is-current" data-review-wizard-panel="1" aria-label="Шаг 1. Выбор файла">
      <fieldset class="content-review-fieldset">
        <legend>1. Файлы из материалов *</legend>
        ${supported.length
          ? `<div class="content-review-media-selection-status"><span>До 5 фото одного товара — каждый ракурс получит отдельный результат. MP4 проверяется по одному.</span><strong data-content-review-media-count aria-live="polite">Ничего не выбрано</strong></div><div class="content-review-media-grid">${supported.slice(0, 30).map((item, index) => reviewMediaOptionMarkup(item, index, activeMediaIds)).join("")}</div>`
          : `<div class="content-review-empty"><span aria-hidden="true">▧</span><div><strong>Нет подходящих файлов</strong><p>Загрузите JPG, PNG, WEBP или MP4 в разделе «Материалы», затем обновите эту страницу.</p><a href="#/workspace/media">Открыть материалы →</a></div></div>`}
      </fieldset>
        <div class="content-review-wizard__actions">
          <span>Выберите материал — остальные поля пока не отвлекают.</span>
          <button class="btn" type="button" data-action="content-review-wizard-step" data-review-step="2">Дальше: контекст →</button>
        </div>
      </section>
      <section class="content-review-wizard__panel" data-review-wizard-panel="2" aria-label="Шаг 2. Контекст публикации">
      <fieldset class="content-review-fieldset">
        <legend>2. Контекст публикации *</legend>
        <div class="content-review-form-grid">
          <label class="field"><span>Площадка</span><select name="platform" required>${Object.entries(PLATFORM_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select></label>
          <label class="field"><span>Статус материала</span><select name="content_kind" required>${Object.entries(CONTENT_KIND_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select><small class="field-hint">«Неизвестно» — безопасный выбор, если руководитель ещё не решил.</small></label>
          <label class="field field-wide"><span>Категория товара</span><select name="product_category" required>${Object.entries(PRODUCT_CATEGORY_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select></label>
          <label class="field field-wide"><span>Подпись к публикации</span><textarea name="caption_text" maxlength="6000" rows="4" placeholder="Текст поста, CTA, хэштеги и обязательные пометки"></textarea></label>
          <label class="field field-wide"><span>Реплика / сценарий ролика</span><textarea name="script_text" maxlength="6000" rows="5" placeholder="Что произносит блогер или что написано крупным текстом в кадре"></textarea><small class="field-hint">Для сгенерированного видео точная реплика подставляется из задания. При отдельном явном подтверждении сервер расшифрует речь и сравнит её со сценарием; человек всё равно прослушивает файл.</small></label>
        </div>
      </fieldset>
        <div class="content-review-wizard__actions">
          <button class="btn btn-secondary" type="button" data-action="content-review-wizard-step" data-review-step="1">← Назад</button>
          <button class="btn" type="button" data-action="content-review-wizard-step" data-review-step="3">Дальше: подтверждения →</button>
        </div>
      </section>
      <section class="content-review-wizard__panel" data-review-wizard-panel="3" aria-label="Шаг 3. Подтверждения">
      <fieldset class="content-review-fieldset">
        <legend>3. Права, люди и доказательства *</legend>
        <div class="content-review-confirmations">
          ${checkMarkup("rights_confirmed", "У команды есть право использовать файл, музыку, логотипы и графику", "Без подтверждения прав проверка не должна вести к публикации.")}
          ${checkMarkup("claims_verified", "Я вручную сверил(а) свойства, цены, скидки и результаты с документом или карточкой товара", "Для генерации из approved research сервер автоматически привяжет safe/forbidden claims. Эта галочка остаётся ручным подтверждением именно итогового файла.")}
          ${checkMarkup("captions_confirmed", "Титры и крупный текст проверены вручную", "Нет обрезанных слов, ошибок, чужого бренда и нечитаемых обещаний.")}
          <label class="field content-review-select-row"><span>Есть узнаваемые люди?</span><select name="people_present" required><option value="unknown">Не проверено</option><option value="no">Нет</option><option value="yes">Да</option></select></label>
          <div data-review-person-consent hidden>
            ${checkMarkup("person_consent_confirmed", "Согласие узнаваемых людей на съёмку и публикацию подтверждено", "Особенно важно для сотрудников, покупателей и несовершеннолетних.")}
          </div>
          <div data-review-external-ai hidden>
            ${checkMarkup("external_ai_processing_confirmed", "Подтверждено законное основание и необходимое информирование для передачи материалов внешнему AI-провайдеру", "Для видео со сценарием это явное разрешение передать исходный MP4 в OpenAI Transcriptions; без него отправляются только допустимые контрольные кадры, а речь проверяется человеком.")}
          </div>
          ${checkMarkup("ai_generated", "Изображение, голос или видео созданы / существенно изменены ИИ", "Отметьте фактическое использование ИИ; это не оценка качества.")}
          <div data-review-ai-disclosure hidden>${checkMarkup("ai_disclosure_confirmed", "Необходимость пометки об ИИ проверена для площадки и задачи", "Если пометка нужна, она уже предусмотрена в файле или подписи.")}</div>
        </div>
      </fieldset>
      <fieldset class="content-review-fieldset" data-review-advertising hidden>
        <legend>4. Рекламные реквизиты</legend>
        <div class="content-review-form-grid">
          <label class="field"><span>Рекламодатель *</span><input name="advertiser_name" maxlength="240" placeholder="Юрлицо / ИП из задачи" /></label>
          <label class="field"><span>ERID *</span><input name="erid" maxlength="180" autocomplete="off" placeholder="Идентификатор рекламы" /></label>
        </div>
        <div class="content-review-confirmations">
          ${checkMarkup("ad_label_confirmed", "Пометка «Реклама» и данные рекламодателя предусмотрены", "Бирка соцсети сама по себе не заменяет обязательные реквизиты.")}
          ${checkMarkup("ord_confirmed", "Передача сведений через ОРД подтверждена ответственным", "Портал фиксирует подтверждение, но не регистрирует рекламу автоматически.")}
        </div>
      </fieldset>
      <fieldset class="content-review-fieldset">
        <legend>5. Канал и обязательные предупреждения</legend>
        <div class="content-review-confirmations">
          ${checkMarkup("audience_over_10000", "Аудитория канала превышает 10 000 подписчиков", "Отметьте только если это действительно так.")}
          <div data-review-rkn hidden>${checkMarkup("rkn_registered", "Статус канала в перечне Роскомнадзора проверен", "Если применимо к выбранному каналу и публикации.")}</div>
          <div data-review-baa hidden>${checkMarkup("mandatory_warning_confirmed", "Обязательное предупреждение для категории проверено", "Для БАД нельзя создавать впечатление, что продукт является лекарством или лечит заболевания.")}</div>
        </div>
      </fieldset>
        <div class="content-review-wizard__actions">
          <button class="btn btn-secondary" type="button" data-action="content-review-wizard-step" data-review-step="2">← Назад</button>
          <button class="btn" type="button" data-action="content-review-wizard-step" data-review-step="4">Проверить перед запуском →</button>
        </div>
      </section>
      <section class="content-review-wizard__panel" data-review-wizard-panel="4" aria-label="Шаг 4. Запуск проверки">
      <div class="content-review-submit">
        <div><strong>Что будет отправлено</strong><p>Для каждого фото: текст формы, технические числа и один сжатый контрольный кадр. Для MP4: четыре контрольных кадра и один хронологический атлас из 12–24 мини-кадров. Исходный MP4 передаётся в OpenAI Transcriptions только при отмеченном подтверждении выше, наличии сценария, нормальной локальной аудиодорожки и размере до 25 МБ; полный текст расшифровки не сохраняется.</p><small class="field-hint" data-content-review-draft-status role="status" aria-live="polite">Черновик сохраняется в этом браузере.</small></div>
        <button class="btn" type="submit" ${supported.length && !busy ? "" : "disabled"}>${busy ? "Файлы ставятся в очередь…" : "Проверить выбранные файлы"}</button>
      </div>
        <div class="content-review-wizard__actions content-review-wizard__actions--back">
          <button class="btn btn-secondary" type="button" data-action="content-review-wizard-step" data-review-step="3">← Исправить подтверждения</button>
        </div>
      </section>
    </form>
  `;
}

function reviewCurrentMarkup(run, { phase, canDecide, restorePlacement = false }) {
  if (phase === "preparing") {
    return progressMarkup("Готовим техническую проверку", "Для фото считываем точный кадр и его параметры. Для MP4 готовим четыре контрольных кадра, атлас таймлайна и уровни звука. На этом шаге исходный MP4 не передаётся.", 1);
  }
  if (phase === "saving_evidence") {
    return progressMarkup("Сохраняем evidence", "Кадры загружаются в защищённую папку и фиксируются до запуска проверки.", 2);
  }
  if (phase === "queueing" || phase === "starting") {
    return progressMarkup("Ставим в фоновую очередь", "Evidence уже сохранён. Создаём неизменяемую проверку, которую сервер продолжит без открытой вкладки.", 3);
  }
  if (phase === "refreshing") {
    return progressMarkup(
      "Обновляем точную версию проверки",
      "Получаем свежий статус и новую короткоживущую ссылку именно на проверенный файл. Решение появится после сверки.",
      3,
    );
  }
  if (!run) {
    return `
      <div class="card content-review-welcome">
        <span class="content-review-welcome__seal" aria-hidden="true">A</span>
        <p class="eyebrow">Результат появится здесь</p>
        <h2>Сначала выберите материал слева</h2>
        <p>Вы получите две независимые оценки: качество ролика и статус рисков. Высокий балл качества не отменяет юридический блокер.</p>
        <div class="content-review-welcome__split"><span><b>0–100</b>Качество и понятность</span><span><b>3 статуса</b>Блок · проверка · предупреждения</span></div>
      </div>`;
  }
  const kind = contentReviewStatusKind(run.status);
  if (kind === "active" || phase === "processing") {
    const durableCopy = run.media?.isVideo
      ? "Evidence сохранён. Можно закрыть вкладку: сервер продолжит проверку содержания и сообщит о результате."
      : "Точный исходник сохранён. Можно закрыть вкладку: сервер продолжит проверку и сообщит о результате.";
    return progressMarkup("Проверка в фоновой очереди", durableCopy, 3, run);
  }
  if (kind === "failed") {
    return `
      <div class="card content-review-failed" role="alert">
        <span aria-hidden="true">!</span><p class="eyebrow">Проверка не завершена</p>
        <h2>Материал не получил решения</h2>
        <p>${escapeHtml(run.failureMessage || "Сервис временно не смог обработать кадры. Исходный файл не потерян — запустите новую проверку позже.")}</p>
        <button class="btn btn-secondary btn-small" type="button" data-action="refresh-content-review" data-review-id="${escapeHtml(run.id)}">Проверить статус</button>
      </div>`;
  }
  return reviewResultMarkup(run, canDecide, { restorePlacement });
}

function reviewResultMarkup(run, canDecide, { restorePlacement = false } = {}) {
  const result = run.result;
  const compliance = COMPLIANCE_META[result.complianceStatus] || COMPLIANCE_META.human_review;
  const blockers = contentReviewHasBlockers(run);
  const assignment = run.independentAssignment;
  const assignmentBlockReason = assignment && !assignment.decisionEligible
    ? "independent_reviewer_required"
      : assignment?.status === "assigned" && !assignment.assignedToMe
        ? "assigned_to_another_reviewer"
      : assignment && ["unassigned", "cancelled"].includes(assignment.status)
        ? "independent_reviewer_assignment_required"
        : assignment?.status === "completed" && !run.decision
          ? "independent_review_completed"
      : "";
  const routedCanDecide = canDecide && !assignmentBlockReason;
  return `
    <article class="content-review-result" data-review-result-id="${escapeHtml(run.id)}">
      ${assignment?.status === "assigned" && assignment.assignedToMe
        ? messageMarkup("Эта независимая проверка назначена вам. Просмотрите точный файл и сохраните одно финальное решение.", "success")
        : ""}
      <header class="card content-review-result__header">
        <div><p class="eyebrow">Проверка завершена</p><h2>${escapeHtml(run.media?.name || "Материал")}</h2><p>${escapeHtml(PLATFORM_LABELS[run.input.platform] || run.input.platform || "Площадка не указана")} · ${escapeHtml(CONTENT_KIND_LABELS[run.input.contentKind] || run.input.contentKind || "Статус не указан")}</p></div>
        ${reviewSummaryPosterMarkup(run)}
        <span class="content-review-result__date">${formatDate(run.completedAt || run.updatedAt || run.createdAt)}</span>
      </header>
      ${routedCanDecide ? "" : reviewReadonlyMediaMarkup(run)}
      <div class="content-review-score-grid">
        <section class="card content-review-quality" style="--review-score:${result.overallScore}">
          <div class="content-review-score-ring"><strong>${result.overallScore}</strong><small>из 100</small></div>
          <div><p class="eyebrow">Качество контента</p><h3>${qualityLabel(result.overallScore)}</h3><p>Баллы помогают расставить приоритеты, но не гарантируют просмотры или продажи.</p></div>
        </section>
        <section class="card content-review-compliance is-${compliance.tone}">
          <span class="content-review-compliance__icon" aria-hidden="true">${compliance.tone === "block" ? "!" : compliance.tone === "pass" ? "✓" : "◇"}</span>
          <div><p class="eyebrow">Риски и соответствие</p><h3>${escapeHtml(compliance.label)}</h3><p>${escapeHtml(compliance.description)}</p><small>${result.blockersCount} блокеров · ${result.warningsCount} предупреждений</small></div>
        </section>
      </div>
      ${scoreBreakdownMarkup(result.scores)}
      ${comparisonMarkup(result.comparison)}
      ${claimEvidenceMarkup(run.input.generationClaimEvidence)}
      ${speechAnalysisMarkup(result.speechAnalysis)}
      ${result.strengths.length ? `<section class="card content-review-strengths"><p class="eyebrow">Что уже работает</p><ul>${result.strengths.map((item) => `<li><span aria-hidden="true">✓</span>${escapeHtml(item)}</li>`).join("")}</ul></section>` : ""}
      ${findingsMarkup(result.findings)}
      ${recommendationsMarkup(result.recommendations)}
      ${reviewDecisionMarkup(run, {
        canDecide: routedCanDecide,
        blockers,
        assignmentBlockReason,
        restorePlacement,
      })}
      ${rulesetMarkup(run)}
    </article>
  `;
}

function reviewSummaryPosterMarkup(run) {
  const media = run?.media || {};
  const isVideo = media.isVideo === true || media.kind === "generated_video";
  const mediaAvailable = Boolean(media.url)
    && run.mediaIsStale !== true
    && (!media.status || media.status === "ready");
  const mediaName = media.name || (isVideo ? "Проверяемый MP4" : "Проверяемое изображение");
  const kindLabel = isVideo ? "Проверяемый MP4" : "Проверяемое изображение";
  const stateLabel = mediaAvailable
    ? isVideo
      ? "Ключевой кадр появится из точного player"
      : "Миниатюра появится из точного файла"
    : run.mediaIsStale
      ? "Версия файла изменилась — обновите проверку"
      : "Защищённый файл временно недоступен";
  return `
    <figure class="content-review-summary-poster is-${isVideo ? "video" : "image"} ${mediaAvailable ? "" : "is-unavailable"}"
            data-content-review-summary-poster
            data-summary-poster-state="${mediaAvailable ? "loading" : "unavailable"}"
            data-media-kind="${isVideo ? "video" : "image"}"
            aria-label="Неинтерактивная визуальная сводка: ${escapeHtml(mediaName)}">
      <canvas class="content-review-summary-poster__canvas" width="640" height="360" aria-hidden="true"></canvas>
      <span class="content-review-summary-poster__placeholder" aria-hidden="true">
        <i></i><b>${isVideo ? "▶" : "◇"}</b><u></u>
      </span>
      <figcaption>
        <small>${kindLabel}</small>
        <strong>Визуальная сводка</strong>
        <span data-content-review-summary-poster-label>${escapeHtml(stateLabel)}</span>
      </figcaption>
    </figure>`;
}

function reviewReadonlyMediaMarkup(run) {
  const media = run?.media || {};
  const mediaUrl = String(media.url || "");
  const mediaAvailable = Boolean(mediaUrl)
    && run.mediaIsStale !== true
    && (!media.status || media.status === "ready");
  if (!mediaAvailable) {
    return `
      <section class="card content-review-decision-preview content-review-readonly-preview">
        <div><strong>Точная версия файла временно недоступна</strong><small>Обновите проверку: решение и публикация останутся заблокированы, пока портал не получит свежую защищённую ссылку.</small></div>
      </section>`;
  }
  const isVideo = media.isVideo === true || media.kind === "generated_video";
  const mediaName = media.name || (isVideo ? "review-video.mp4" : "review-image.png");
  const exactMedia = isVideo
    ? `<video class="content-review-decision-preview__media" src="${escapeHtml(mediaUrl)}" controls preload="metadata" playsinline aria-label="Точный проверяемый MP4 ${escapeHtml(mediaName)}"></video>`
    : `<img class="content-review-decision-preview__media" src="${escapeHtml(mediaUrl)}" alt="Точный проверяемый файл ${escapeHtml(mediaName)}" />`;
  return `
    <section class="card content-review-decision-preview content-review-readonly-preview" aria-label="Точный проверяемый файл">
      <div><strong>${isVideo ? "Просмотрите точный MP4 со звуком" : "Осмотрите точное изображение"}</strong><small>${isVideo ? "Результат AI — только подсказка. Воспроизведите ролик целиком, проверьте речь, звук, титры и товар до любого решения." : "Результат AI — только подсказка. Проверьте товар, этикетку, надписи и композицию в полном размере."}</small></div>
      ${exactMedia}
      <div class="content-review-readonly-preview__actions">
        ${isVideo ? `<button class="btn btn-small" type="button" data-action="download-content-review-media" data-review-id="${escapeHtml(run.id)}">Скачать MP4</button>` : ""}
      </div>
    </section>`;
}

function scoreBreakdownMarkup(scores) {
  const entries = Object.entries(scores);
  if (!entries.length) return "";
  return `
    <section class="card content-review-breakdown">
      <div><p class="eyebrow">Почему такой балл</p><h3>Разбор по направлениям</h3></div>
      <div class="content-review-bars">${entries.map(([key, value]) => `
        <div class="content-review-bar"><span><b>${escapeHtml(scoreLabel(key))}</b><strong>${value}</strong></span><i aria-hidden="true"><u style="width:${value}%"></u></i></div>
      `).join("")}</div>
    </section>`;
}

function comparisonMarkup(comparison) {
  if (!comparison || (comparison.delta === null && !comparison.summary)) return "";
  const delta = comparison.delta;
  const tone = delta === null ? "neutral" : delta > 0 ? "positive" : delta < 0 ? "negative" : "neutral";
  return `
    <section class="card content-review-comparison is-${tone}">
      <span aria-hidden="true">${delta === null ? "↔" : delta > 0 ? "↗" : delta < 0 ? "↘" : "→"}</span>
      <div><p class="eyebrow">Сравнение с прошлой проверкой</p><h3>${delta === null ? "История собирается" : `${delta > 0 ? "+" : ""}${delta} баллов`}</h3><p>${escapeHtml(comparison.summary || "Сравниваются проверки этого же материала и контекста.")}</p></div>
    </section>`;
}

function claimEvidenceMarkup(evidence) {
  if (!evidence) return "";
  const bound = evidence.status === "bound";
  const title = bound
    ? `${evidence.safeClaimCount} разрешённых · ${evidence.forbiddenClaimCount} запрещённых`
    : evidence.status === "invalid"
      ? "Связь исследования отклонена"
      : "Подтверждённое исследование не привязано";
  const copy = bound
    ? "Сервер сохранил immutable snapshot approved AI research для этого generation job. Он подтверждает базу задания, но итоговый файл всё равно нужно осмотреть и прослушать."
    : "Ручная галочка не заменяет server-bound источники. Сверьте claims самостоятельно либо создайте новую генерацию из одобренного AI research.";
  return `
    <section class="card content-review-comparison is-${bound ? "positive" : "neutral"}">
      <span aria-hidden="true">${bound ? "✓" : "◇"}</span>
      <div><p class="eyebrow">Claims и исследование товара</p><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p>${evidence.evidenceHash ? `<small>Evidence ${escapeHtml(evidence.evidenceHash.slice(0, 12))}… · источник ${escapeHtml(evidence.source)}</small>` : ""}</div>
    </section>`;
}

function speechAnalysisMarkup(analysis) {
  if (!analysis || analysis.status === "not_applicable") return "";
  if (analysis.status === "completed") {
    const similarity = Math.round((analysis.similarityRatio ?? 0) * 100);
    const coverage = Math.round((analysis.coverageRatio ?? 0) * 100);
    const confidence = analysis.transcriptionConfidence === null
      ? "не предоставлена"
      : `${Math.round(analysis.transcriptionConfidence * 100)}%`;
    return `
      <section class="card content-review-comparison is-${similarity >= 75 ? "positive" : similarity >= 45 ? "neutral" : "negative"}">
        <span aria-hidden="true">◉</span>
        <div><p class="eyebrow">Сверка речи со сценарием</p><h3>${similarity}% сходства · ${coverage}% покрытия</h3><p>${analysis.transcriptExcerpt ? `Распознано: «${escapeHtml(analysis.transcriptExcerpt)}»` : "Провайдер не распознал слов в дорожке."}</p><small>${analysis.expectedWordCount} слов в сценарии · ${analysis.transcriptWordCount} распознано · уверенность ${escapeHtml(confidence)}. Полная расшифровка не сохраняется; решение требует прослушивания.</small></div>
      </section>`;
  }
  const copy = {
    not_requested: "Исходный MP4 не передавался на транскрипцию: явное подтверждение не отмечено.",
    skipped_no_script: "Транскрипция не запускалась: нет точной реплики для доказательной сверки.",
    skipped_audio_unavailable: "Транскрипция не запускалась: локальный анализ не подтвердил пригодную речевую дорожку.",
    skipped_file_too_large: "Транскрипция не запускалась: файл превышает безопасный предел 25 МБ или 90 секунд.",
    unavailable: "Запрос транскрипции не дал подтверждённого результата и автоматически не повторялся.",
  }[analysis.status] || "Автоматическая сверка речи недоступна.";
  return `
    <section class="card content-review-comparison is-neutral">
      <span aria-hidden="true">◇</span>
      <div><p class="eyebrow">Сверка речи со сценарием</p><h3>Нужно прослушивание человеком</h3><p>${escapeHtml(copy)}</p></div>
    </section>`;
}

function findingsMarkup(findings) {
  if (!findings.length) {
    return `<section class="card content-review-findings"><p class="eyebrow">Найденные риски</p><div class="content-review-clear"><span aria-hidden="true">✓</span><div><strong>Явных замечаний не найдено</strong><p>Это не отменяет просмотра ролика и решения ответственного человека.</p></div></div></section>`;
  }
  const order = { blocker: 0, high: 1, medium: 2, low: 3, info: 4 };
  const sorted = [...findings].sort((left, right) => (order[left.severity] ?? 9) - (order[right.severity] ?? 9));
  return `
    <section class="card content-review-findings">
      <div class="content-review-section-heading"><div><p class="eyebrow">Что нельзя пропустить</p><h3>Риски и замечания</h3></div><span>${sorted.length}</span></div>
      <div class="content-review-finding-list">${sorted.map(findingMarkup).join("")}</div>
    </section>`;
}

function findingMarkup(item) {
  const source = item.sourceKey ? SOURCE_LABELS[item.sourceKey] || item.sourceKey : "";
  const sourceUrl = Object.prototype.hasOwnProperty.call(SOURCE_URLS, item.sourceKey)
    ? SOURCE_URLS[item.sourceKey]
    : "";
  const sourceMarkup = sourceUrl
    ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Источник правила: ${escapeHtml(source)}</a>`
    : source
      ? `<span>Источник правила: ${escapeHtml(source)}</span>`
      : "";
  return `
    <article class="content-review-finding is-${escapeHtml(item.severity)}">
      <div class="content-review-finding__top"><span>${escapeHtml(severityLabel(item.severity))}</span><small>${escapeHtml(categoryLabel(item.category))}${item.timecode ? ` · ${escapeHtml(item.timecode)}` : ""}</small></div>
      <h4>${escapeHtml(item.title)}</h4>
      <p>${escapeHtml(item.detail)}</p>
      ${item.action ? `<div class="content-review-action"><strong>Что сделать</strong><p>${escapeHtml(item.action)}</p></div>` : ""}
      <footer>${sourceMarkup}${item.humanReviewRequired ? "<b>Нужно решение человека</b>" : ""}</footer>
    </article>`;
}

function recommendationsMarkup(items) {
  if (!items.length) return "";
  return `
    <section class="card content-review-recommendations">
      <div class="content-review-section-heading"><div><p class="eyebrow">Следующий монтаж</p><h3>Что улучшить по приоритету</h3></div><span>${items.length}</span></div>
      <ol>${items.map((item, index) => `
        <li class="is-${escapeHtml(item.priority)}"><span>${String(index + 1).padStart(2, "0")}</span><div><small>${escapeHtml(priorityLabel(item.priority))} · ${escapeHtml(categoryLabel(item.category))}</small><h4>${escapeHtml(item.title)}</h4><p>${escapeHtml(item.detail)}</p>${item.action ? `<strong>Действие: ${escapeHtml(item.action)}</strong>` : ""}${item.measurement ? `<em>Проверка результата: ${escapeHtml(item.measurement)}</em>` : ""}</div></li>
      `).join("")}</ol>
    </section>`;
}

function generatedContextApprovalMarkup(run) {
  const video = run.media?.kind === "generated_video";
  const selectedCategory = PRODUCT_CATEGORY_LABELS[run.input.productCategory]
    ? run.input.productCategory
    : "other";
  const categoryOptions = Object.entries(PRODUCT_CATEGORY_LABELS)
    .map(([value, label]) => `<option value="${value}" ${value === selectedCategory ? "selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
  return `
    <fieldset class="content-review-fieldset content-review-context-approval" data-generated-media-context>
      <legend>Реквизиты для этого точного ${video ? "MP4" : "PNG"}</legend>
      <p>${video ? "MP4, звук и evidence повторно не отправляются внешнему AI. Сервер наследует уже готовую оценку и неизменяемо добавляет только эти подтверждения." : "Изображение повторно не отправляется внешнему AI. Сервер наследует уже готовую визуальную оценку и неизменяемо добавляет только эти подтверждения."}</p>
      <div class="content-review-form-grid">
        <label class="field field-wide"><span>Категория товара *</span><select name="release_product_category">${categoryOptions}</select></label>
        <label class="field"><span>Рекламодатель *</span><input name="release_advertiser_name" minlength="2" maxlength="240" placeholder="Юрлицо / ИП из задачи" /></label>
        <label class="field"><span>ERID *</span><input name="release_erid" minlength="6" maxlength="180" autocomplete="off" placeholder="Идентификатор именно этого креатива" /></label>
        <label class="field field-wide"><span>Есть узнаваемые люди?</span><select name="release_people_present"><option value="">Выберите после осмотра</option><option value="no">Нет</option><option value="yes">Да</option></select></label>
      </div>
      <div class="content-review-confirmations">
        ${checkMarkup("release_ad_label_confirmed", "Пометка «Реклама» и сведения о рекламодателе предусмотрены", "Подтверждение относится к этому точному креативу.")}
        ${checkMarkup("release_ord_confirmed", "ERID и передача сведений через ОРД проверены", "Портал не регистрирует рекламу автоматически.")}
        ${checkMarkup("release_rights_confirmed", "Права на товар, логотипы, исходник и графику подтверждены", "Без прав автоматическое одобрение контекста невозможно.")}
        ${checkMarkup("release_claims_verified", `Все надписи и обещания на итоговом ${video ? "MP4" : "PNG"} сверены с товаром и approved research`, "Это подтверждение итогового файла, а не только задания генерации.")}
        ${video ? checkMarkup("release_captions_confirmed", "Титры и субтитры итогового MP4 проверены вручную", "Звук и дикция фиксируются отдельной неизменяемой оценкой ниже; здесь подтвердите только читаемость текста в кадре.") : ""}
        ${checkMarkup("release_person_consent_confirmed", "Если в кадре есть узнаваемые люди, их согласие подтверждено", "Для варианта «Нет» сервер не требует эту отметку.")}
        ${checkMarkup("release_ai_disclosure_confirmed", "Для YouTube проверена необходимая пометка синтетического контента", "Для других площадок отметка сохраняется как дополнительное подтверждение.")}
        ${checkMarkup("release_mandatory_warning_confirmed", "Для БАД предусмотрено обязательное предупреждение", "Для других категорий отметка не обязательна.")}
        ${checkMarkup("release_audience_over_10000", "Аудитория канала превышает 10 000", "Отметьте только если это действительно так.")}
        ${checkMarkup("release_rkn_registered", "Если аудитория больше 10 000, канал проверен в перечне Роскомнадзора", "Для меньшей аудитории отметка не обязательна.")}
      </div>
    </fieldset>`;
}

function soundAssessmentStatusLabel(status) {
  return {
    clear: "Звук принят",
    issues_found: "Найдены ошибки звука",
    silent_expected: "Ожидаемая тишина подтверждена",
  }[status] || "Звук не оценён";
}

function soundAssessmentSummaryMarkup(run) {
  if (run.media?.kind !== "generated_video") return "";
  const assessment = run.soundAssessment;
  if (!assessment) {
    return `
      <section class="content-review-sound-summary is-legacy">
        <strong>${run.soundRecoveryEligible ? "Звук: требуется повторное подтверждение" : "Звук: нет отдельной записи"}</strong>
        <p>${run.soundRecoveryEligible ? "Неизменяемое решение сохранено, но отдельная оценка звука отсутствует. Тот же сотрудник может заново прослушать точный MP4 и дописать только звуковую историю." : "Отдельная оценка дикции не найдена. Само решение не считается подтверждением качества звука."}</p>
      </section>`;
  }
  const issues = assessment.issueCodes
    .map((code) => GENERATED_VIDEO_SOUND_ISSUE_LABELS[code] || code);
  const tone = assessment.status === "issues_found" ? "issues" : "clear";
  return `
    <section class="content-review-sound-summary is-${tone}">
      <strong>${escapeHtml(soundAssessmentStatusLabel(assessment.status))}</strong>
      ${issues.length ? `<ul>${issues.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${assessment.note ? `<p>${escapeHtml(assessment.note)}</p>` : ""}
      <small>${escapeHtml(assessment.assessedBy || "Ответственный проверяющий")} · ${formatDate(assessment.assessedAt)}</small>
    </section>`;
}

function soundAssessmentRecoveryMarkup(run) {
  if (
    run.media?.kind !== "generated_video"
    || !run.decision
    || run.soundAssessment
    || run.soundRecoveryEligible !== true
  ) return "";
  const mediaAvailable = Boolean(run.media?.url)
    && run.mediaIsStale !== true
    && (!run.media?.status || run.media.status === "ready");
  const unavailableMessage = run.mediaIsStale
    ? "Файл изменился после решения. Звуковую историю этой версии восстанавливать нельзя."
    : "Точная защищённая версия MP4 сейчас недоступна. Обновите статус проверки.";
  const exactVideo = `<video class="content-review-decision-preview__media" data-content-review-exact-media data-media-kind="video" src="${escapeHtml(run.media?.url || "")}" controls preload="metadata" playsinline></video>`;
  const exactPreview = mediaAvailable
    ? platformSafeZoneVideoMarkup(run.input?.platform, exactVideo)
    : `<div class="content-review-decision-preview__missing">${escapeHtml(unavailableMessage)}</div>`;
  return `
    <form class="card content-review-decision-form content-review-sound-recovery-form" data-review-id="${escapeHtml(run.id)}" data-exact-media-state="${mediaAvailable ? "loading" : "unavailable"}" novalidate>
      <div>
        <p class="eyebrow">Восстановление истории звука</p>
        <h3>Заново прослушайте точный MP4</h3>
        <p>Решение «${escapeHtml(decisionLabel(run.decision.decision))}» останется неизменным. Портал добавит только пропущенную оценку звука от того же сотрудника и не запустит повторное решение или ремонт.</p>
      </div>
      <section class="content-review-decision-preview">
        <div><strong>Прослушайте именно этот файл от 00:00 до конца</strong><small>Без перемотки, ускорения и выключения громкости. После окончания отдельно отметьте дикцию и каждую найденную ошибку.</small></div>
        ${exactPreview}
        <p class="content-review-decision-preview__state ${mediaAvailable ? "" : "is-error"}" data-content-review-media-state role="status">${mediaAvailable ? "Загружаем метаданные MP4. Затем прослушайте файл целиком с включённым звуком." : escapeHtml(unavailableMessage)}</p>
      </section>
      <label class="content-review-check content-review-watch-confirmation"><input type="checkbox" name="media_watched_confirmed" value="yes" required disabled /><span><strong>Я подтверждаю, что заново прослушал(а) именно этот защищённый MP4 до конца</strong><small>Поле откроется только после непрерывного воспроизведения с включённым звуком и скоростью 1×.</small></span></label>
      ${generatedVideoSoundAssessmentMarkup(run)}
      <div class="content-review-decision-actions">
        <button class="btn btn-primary" type="submit" data-sound-recovery-submit disabled>Добавить оценку звука</button>
      </div>
    </form>`;
}

function generatedVideoSoundAssessmentMarkup(run) {
  if (run.media?.kind !== "generated_video") return "";
  const audioExpected = run.media?.audioExpected !== false;
  const spokenScript = text(
    run.media?.spokenScript || run.input?.scriptText,
    6000,
  );
  if (!audioExpected) {
    return `
      <fieldset class="content-review-sound-assessment" data-content-review-sound-assessment data-audio-expected="false">
        <legend>Обязательная оценка звука</legend>
        <p>Этот режим должен дать немой ролик. Прослушайте файл с включённой громкостью: неожиданную речь, музыку или шум нужно сохранить как ошибку и вернуть на доработку.</p>
        <label class="field"><span>Результат прослушивания *</span><select name="sound_status" required><option value="">Выберите после полного прослушивания</option><option value="silent_expected">Ожидаемая тишина подтверждена</option><option value="issues_found">Слышен неожиданный звук — только на доработку или отклонить</option></select></label>
        ${checkMarkup("silence_expected_confirmed", "Подтверждаю ожидаемую тишину во всём ролике", "Прослушайте файл с включённой громкостью: речь, музыка, шум и провалы отсутствуют.")}
        <fieldset class="content-review-sound-issues">
          <legend>Если слышен неожиданный звук — отметьте проблему</legend>
          ${GENERATED_VIDEO_SOUND_ISSUE_CODES.map((code) => `<label><input type="checkbox" name="sound_issue_codes" value="${escapeHtml(code)}" /><span>${escapeHtml(GENERATED_VIDEO_SOUND_ISSUE_LABELS[code])}</span></label>`).join("")}
        </fieldset>
        <label class="field"><span>Что именно слышно</span><textarea name="sound_note" maxlength="1000" rows="2" placeholder="Например: на 00:04 появилась чужая речь и треск"></textarea><small class="field-hint">Для ошибки немого режима обязательно отметьте «неожиданно появились речь, музыка или шум» и опишите момент.</small></label>
      </fieldset>`;
  }
  return `
    <fieldset class="content-review-sound-assessment" data-content-review-sound-assessment data-audio-expected="true">
      <legend>Обязательная оценка дикции и звука</legend>
      <p>Автоматический уровень громкости не доказывает разборчивость. Сначала прослушайте весь ролик без перемотки и без ускорения, затем зафиксируйте результат.</p>
      ${spokenScript ? `<blockquote><small>Ожидаемая реплика дословно</small><strong>«${escapeHtml(spokenScript)}»</strong></blockquote>` : `<div class="content-review-sound-warning">Точная реплика не найдена в данных проверки. Одобрение звука невозможно — верните ролик на доработку.</div>`}
      <label class="field"><span>Результат прослушивания *</span><select name="sound_status" required><option value="">Выберите после полного прослушивания</option><option value="clear">Звук чистый — можно рассматривать к одобрению</option><option value="issues_found">Есть ошибки — только на доработку или отклонить</option></select></label>
      <div class="content-review-sound-confirmations">
        ${checkMarkup("spoken_script_heard_exactly_confirmed", "Каждое слово реплики услышано дословно", "Нет замен, добавлений, «товарищки», «воть», растянутых окончаний и потерянных слов.")}
        ${checkMarkup("diction_clear_confirmed", "Дикция и окончания полностью разборчивы", "Слова не съедаются; произношение естественное, без нежелательного акцента.")}
        ${checkMarkup("voice_style_confirmed", "Темп и дикторский тон соответствуют заданию", "Голос не режет слух, не тараторит и не меняет заданный характер подачи.")}
        ${checkMarkup("audio_sync_confirmed", "Синхронизация, числа и единицы произнесены корректно", "Проверьте градусы, секунды, названия режимов, таймер и совпадение речи с кадром.")}
      </div>
      <fieldset class="content-review-sound-issues">
        <legend>Если есть ошибка — отметьте каждую найденную</legend>
        ${GENERATED_VIDEO_SOUND_ISSUE_CODES.map((code) => `<label><input type="checkbox" name="sound_issue_codes" value="${escapeHtml(code)}" /><span>${escapeHtml(GENERATED_VIDEO_SOUND_ISSUE_LABELS[code])}</span></label>`).join("")}
      </fieldset>
      <label class="field"><span>Что именно слышно</span><textarea name="sound_note" maxlength="1000" rows="2" placeholder="Например: «товарищки воть пароваркаа»; на 00:03 съедено окончание"></textarea><small class="field-hint">При выборе «Есть ошибки» укажите не меньше 5 символов. Запись попадёт в неизменяемую историю QA.</small></label>
    </fieldset>`;
}

function reviewDecisionMarkup(
  run,
  { canDecide, blockers, assignmentBlockReason = "", restorePlacement = false },
) {
  if (run.decision) {
    return `
      <section class="card content-review-decision is-recorded">
        <span aria-hidden="true">⌁</span>
        <div><p class="eyebrow">Неизменяемое решение человека</p><h3>${escapeHtml(decisionLabel(run.decision.decision))}</h3><p>${escapeHtml(run.decision.reason || "Причина не указана.")}</p><small>${escapeHtml(run.decision.decidedBy || "Ответственный участник")} · ${formatDate(run.decision.decidedAt)}</small>${soundAssessmentSummaryMarkup(run)}</div>
      </section>
      ${soundAssessmentRecoveryMarkup(run)}
      ${restorePlacement && run.decision.decision === "approved" ? `
        <section class="card content-review-next-action">
          <div>
            <p class="eyebrow">Следующий шаг</p>
            <h3>Создать публикацию для этого материала</h3>
            <p>Решение уже сохранено. Портал восстановит недостающую задачу и откроет её в этом же окне.</p>
          </div>
          <button class="btn btn-primary" type="button"
                  data-action="restore-project-placement"
                  data-review-id="${escapeHtml(run.id)}">Восстановить публикацию</button>
        </section>` : ""}
      ${generationRepairNextActionMarkup(run)}`;
  }
  if (!canDecide) {
    if (assignmentBlockReason === "independent_reviewer_required") {
      return messageMarkup(
        "Вы участвовали в создании этого результата. Финальное решение назначается другому руководителю, продюсеру или проверяющему.",
        "info",
      );
    }
    if (assignmentBlockReason === "assigned_to_another_reviewer") {
      return messageMarkup(
        "Независимый QA уже назначен другому участнику. После его решения статус обновится автоматически.",
        "info",
      );
    }
    if (assignmentBlockReason === "independent_reviewer_assignment_required") {
      return messageMarkup(
        "Пока нет другого участника с действующим допуском для независимого QA. Решение безопасно заблокировано; после появления подходящего проверяющего назначение создастся автоматически.",
        "info",
      );
    }
    if (assignmentBlockReason === "independent_review_completed") {
      return messageMarkup(
        "Независимый QA уже завершён через подтверждение точного контекста результата. Повторное решение не требуется.",
        "success",
      );
    }
    return messageMarkup("Результат готов. Зафиксировать финальное решение может руководитель, продюсер или проверяющий.", "info");
  }
  const generatedContextReady = generatedMediaApprovalContextReady(run);
  const generatedImageContextReady = generatedContextReady;
  const contextApprovalAvailable = generatedMediaContextCanApprove(run);
  const contextCodes = run.media?.kind === "generated_video"
    ? GENERATED_VIDEO_CONTEXT_RESOLVABLE_CODES
    : GENERATED_IMAGE_CONTEXT_RESOLVABLE_CODES;
  const decisionFindings = contextApprovalAvailable
    ? run.result.findings.filter((item) => !contextCodes.has(item.code))
    : run.result.findings;
  const riskItems = [...new Map(
    decisionFindings
      .filter((item) => item.code && (item.humanReviewRequired || ["high", "medium"].includes(item.severity)))
      .map((item) => [item.code, item]),
  ).values()];
  const requiredRiskCodes = new Set(
    contextApprovalAvailable
      ? generatedMediaPostContextRequiredRiskCodes(run)
      : contentReviewRequiredRiskCodes(run),
  );
  const fallbackRisk = requiredRiskCodes.has("general_human_review") && !riskItems.length
    ? [{ code: "general_human_review", title: "Результат требует отдельного решения человека" }]
    : [];
  const recommendationItems = run.result.recommendations.filter((item) => (
    item.code
    && (
      !contextApprovalAvailable
      || !item.code.startsWith("FIX.")
      || !contextCodes.has(item.code.slice(4))
    )
  ));
  const approvalBlocked = blockers || !generatedContextReady;
  const mediaAvailable = Boolean(run.media?.url)
    && run.mediaIsStale !== true
    && (!run.media?.status || run.media.status === "ready");
  const unavailableMessage = run.mediaIsStale
    ? "Файл изменился после анализа. Для этой версии нельзя фиксировать решение — запустите новую проверку."
    : "Точная защищённая версия файла сейчас недоступна. Обновите статус, прежде чем принимать решение.";
  const exactVideo = `<video class="content-review-decision-preview__media" data-content-review-exact-media data-media-kind="video" src="${escapeHtml(run.media?.url || "")}" controls preload="metadata" playsinline></video>`;
  const exactPreview = mediaAvailable
    ? run.media.isVideo
      ? platformSafeZoneVideoMarkup(run.input?.platform, exactVideo)
      : `<img class="content-review-decision-preview__media" data-content-review-exact-media data-media-kind="image" src="${escapeHtml(run.media.url)}" alt="${escapeHtml(run.media.name || "Проверяемый материал")}" />`
    : `<div class="content-review-decision-preview__missing">${escapeHtml(unavailableMessage)}</div>`;
  const previewTitle = run.media?.isVideo
    ? "Просмотрите именно этот файл целиком"
    : "Осмотрите именно это изображение в полном размере";
  const previewCopy = run.media?.isVideo
    ? "Кадры ИИ — вспомогательная выборка. Браузер фиксирует загрузку файла и окончание воспроизведения, но подтверждение звука, титров и смысла всё равно даёт человек."
    : "Проверка ИИ вспомогательная. Человек отдельно подтверждает товар, этикетку, композицию, рекламные реквизиты и отсутствие выдуманных деталей.";
  const confirmationTitle = run.media?.isVideo
    ? "Я подтверждаю, что лично просмотрел(а) именно этот защищённый файл до конца и проверил(а) звук и субтитры"
    : "Я подтверждаю, что лично осмотрел(а) именно этот защищённый PNG в полном размере и проверил(а) товар, этикетку и все надписи";
  const confirmationCopy = run.media?.isVideo
    ? "Это подтверждение пользователя, а не автоматическое доказательство качества. Поле откроется только после непрерывного воспроизведения от 00:00 до конца с включённым звуком и без ускорения."
    : "Это подтверждение пользователя, а не автоматическое доказательство качества. Поле откроется только после успешной загрузки неизменённого изображения.";
  return `
    <form class="card content-review-decision-form" data-review-id="${escapeHtml(run.id)}" data-exact-media-state="${mediaAvailable ? "loading" : "unavailable"}" data-release-context-ready="${generatedImageContextReady ? "true" : "false"}" data-context-approval-ready="${contextApprovalAvailable ? "true" : "false"}" data-release-captions-required="${run.media?.kind === "generated_video" ? "true" : "false"}" novalidate>
      <div><p class="eyebrow">Финальное решение человека</p><h3>${contextApprovalAvailable ? "Добавьте контекст и одобрите без повторного AI" : approvalBlocked ? (blockers ? "Одобрение недоступно из-за замечаний к материалу" : "Сначала подтвердите рекламный контекст") : "Зафиксируйте результат проверки"}</h3><p>${contextApprovalAvailable ? `Автоматическая проверка уже готова. Заполните реквизиты один раз: сервер создаст неизменяемое дополнение, сохранит решение и публикационную задачу без повторной отправки ${run.media?.kind === "generated_video" ? "MP4, звука или evidence" : "PNG"} провайдеру.` : !generatedContextReady ? "Кроме отсутствующего рекламного контекста остались замечания к самому материалу. Исправьте контент через «На доработку»; повторная AI-проверка понадобится только для нового файла." : "После сохранения решение нельзя переписать. Для исправленной версии запустите новую проверку."}</p></div>
      <section class="content-review-decision-preview">
        <div><strong>${previewTitle}</strong><small>${previewCopy}</small></div>
        ${exactPreview}
        <p class="content-review-decision-preview__state ${mediaAvailable ? "" : "is-error"}" data-content-review-media-state role="status">${mediaAvailable ? (run.media.isVideo ? "Загружаем метаданные MP4. Затем прослушайте файл от 00:00 до конца с включённым звуком." : "Проверяем доступность изображения.") : escapeHtml(unavailableMessage)}</p>
      </section>
      <label class="content-review-check content-review-watch-confirmation"><input type="checkbox" name="media_watched_confirmed" value="yes" required disabled /><span><strong>${confirmationTitle}</strong><small>${confirmationCopy}</small></span></label>
      ${generatedVideoSoundAssessmentMarkup(run)}
      ${contextApprovalAvailable ? generatedContextApprovalMarkup(run) : ""}
      ${riskItems.length || fallbackRisk.length ? `
        <fieldset class="content-review-decision-checks">
          <legend>Риски, которые проверены лично</legend>
          ${[...riskItems, ...fallbackRisk].map((item) => `<label><input type="checkbox" name="risk_acknowledgements" value="${escapeHtml(item.code)}" ${requiredRiskCodes.has(item.code) ? 'data-required-risk="true"' : ""} /><span>${escapeHtml(item.title)}${requiredRiskCodes.has(item.code) ? " · обязательно для одобрения" : ""}</span></label>`).join("")}
        </fieldset>
      ` : ""}
      ${recommendationItems.length ? `
        <fieldset class="content-review-decision-checks">
          <legend>Рекомендации, уже применённые в этой версии</legend>
          ${recommendationItems.map((item) => `<label><input type="checkbox" name="resolved_recommendation_codes" value="${escapeHtml(item.code)}" /><span>${escapeHtml(item.title)}</span></label>`).join("")}
        </fieldset>
      ` : ""}
      <label class="field"><span>Почему принято такое решение *</span><textarea name="reason" required minlength="10" maxlength="2000" rows="3" placeholder="Что проверено, что нужно исправить или почему материал отклонён"></textarea></label>
      <div class="content-review-decision-actions">
        ${approvalBlocked ? "" : `<button class="btn" type="submit" name="decision" value="approved" data-review-decision-submit disabled>Одобрить</button>`}
        ${contextApprovalAvailable ? `<button class="btn" type="submit" name="decision" value="approve_with_context" data-review-decision-submit disabled>Подтвердить контекст и одобрить</button>` : ""}
        <button class="btn btn-secondary" type="submit" name="decision" value="needs_changes" data-review-decision-submit disabled>На доработку</button>
        <button class="btn btn-ghost" type="submit" name="decision" value="rejected" data-review-decision-submit disabled>Отклонить</button>
      </div>
    </form>`;
}

function platformSafeZoneVideoMarkup(platform, videoMarkup) {
  const normalizedPlatform = String(platform || "").trim().toLowerCase();
  const guide = PLATFORM_SAFE_ZONE_GUIDES[normalizedPlatform];
  if (!guide) return videoMarkup;
  const sourceLink = guide.sourceUrl
    ? `<a href="${escapeHtml(guide.sourceUrl)}" target="_blank" rel="noopener noreferrer">Официальная справка площадки ↗</a>`
    : "";
  return `
    <div class="content-review-safe-zone" data-safe-zone-platform="${escapeHtml(normalizedPlatform)}">
      <div class="content-review-safe-zone__toolbar">
        <label><input type="checkbox" data-content-review-safe-zone-toggle checked /><span>Показывать зоны риска интерфейса</span></label>
        ${sourceLink}
      </div>
      <div class="content-review-safe-zone__stage" data-content-review-safe-zone-stage>
        ${videoMarkup}
        <div class="content-review-safe-zone__overlay" aria-hidden="true">
          <span class="content-review-safe-zone__risk is-top"></span>
          <span class="content-review-safe-zone__risk is-right"></span>
          <span class="content-review-safe-zone__risk is-bottom"></span>
          <span class="content-review-safe-zone__risk is-left"></span>
          <span class="content-review-safe-zone__frame"><b>Ключевой товар, лицо и текст — внутри</b></span>
        </div>
      </div>
      <small class="content-review-safe-zone__note"><strong>${escapeHtml(guide.label)}:</strong> это консервативный индикатор риска, а не точный шаблон публикации. Элементы интерфейса, подпись и CTA меняются — перед выпуском проверьте ролик в нативном предпросмотре площадки.</small>
    </div>`;
}

function generationRepairNextActionMarkup(run) {
  const action = run?.repairNextAction;
  if (!action) return "";
  if (action.status === "available") {
    return `
      <section class="card content-review-decision">
        <span aria-hidden="true">↻</span>
        <div>
          <p class="eyebrow">Точное исправление</p>
          <h3>Доработка после QA готова</h3>
          <p>${action.canPrepare
            ? "Сервер заново соберёт безопасное repair-ТЗ из числовых оценок этого решения. Исходник, модель и площадка будут восстановлены; цену всё равно нужно подтвердить отдельно."
            : "Исправление доступно создателю результата или руководителю. Текст комментария проверяющего в промпт не копируется."}</p>
          ${action.canPrepare
            ? `<button class="btn btn-secondary btn-small" type="button" data-action="prepare-generation-repair" data-review-id="${escapeHtml(run.id)}">Подготовить исправление</button>`
            : ""}
        </div>
      </section>`;
  }
  if (["started", "in_progress"].includes(action.status)) {
    return messageMarkup(
      "Исправление уже запущено. Не создавайте повторный платный запуск — дождитесь готового файла или точной ошибки.",
      "info",
    );
  }
  if (action.status === "succeeded") {
    return messageMarkup(
      "Исправленный файл уже создан и проходит собственный независимый QA.",
      "success",
    );
  }
  return messageMarkup(
    "Исправляющий запуск завершился ошибкой. Откройте создание контента и разберите точный статус; не повторяйте оплату автоматически.",
    "danger",
  );
}

function rulesetMarkup(run) {
  const sourceKeys = [...new Set(run.result.findings.map((item) => item.sourceKey).filter(Boolean))];
  return `
    <details class="card content-review-ruleset">
      <summary><span><strong>Версия правил и пределы проверки</strong><small>${escapeHtml(run.rulesetVersion || "Версия не указана сервером")}</small></span><i aria-hidden="true">+</i></summary>
      <div>
        <p>Проверка ищет признаки риска по кадрам и введённому тексту. При явном разрешении она может передать ограниченный MP4 в OpenAI Transcriptions и сравнить распознанную речь со сценарием, но ASR не подтверждает музыку, интонацию, факты и юридический смысл, не заменяет юриста и полного прослушивания человеком.</p>
        ${sourceKeys.length ? `<ul>${sourceKeys.map((key) => `<li>${escapeHtml(SOURCE_LABELS[key] || key)}</li>`).join("")}</ul>` : "<p>Источники конкретных правил отображаются у замечаний, когда сервер их указал.</p>"}
      </div>
    </details>`;
}

function reviewHistoryMarkup(runs, selectedId) {
  return `
    <section class="content-review-history" aria-labelledby="content-review-history-title">
      <div class="content-review-history__heading"><div><p class="eyebrow">Неизменяемая история</p><h2 id="content-review-history-title">Предыдущие проверки</h2><p>Новая версия создаёт новую запись — старый результат и решение не переписываются.</p></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-section" data-section="review">Обновить</button></div>
      ${runs.length ? `<div class="content-review-history__list">${runs.slice(0, 50).map((run) => historyCardMarkup(run, run.id === selectedId)).join("")}</div>` : `<div class="card content-review-history__empty"><span aria-hidden="true">◇</span><div><strong>История начнётся после первой проверки</strong><p>Здесь будут видны версии, изменения балла и решения ответственных.</p></div></div>`}
    </section>`;
}

function historyCardMarkup(run, active) {
  const kind = contentReviewStatusKind(run.status);
  const result = run.result;
  const compliance = COMPLIANCE_META[result.complianceStatus] || COMPLIANCE_META.human_review;
  const soundLabel = run.media?.kind === "generated_video"
    ? run.soundAssessment
      ? soundAssessmentStatusLabel(run.soundAssessment.status)
      : "Звук не зафиксирован"
    : "";
  return `
    <button class="card content-review-history-card ${active ? "is-active" : ""}" type="button" data-action="open-content-review" data-review-id="${escapeHtml(run.id)}" aria-pressed="${active ? "true" : "false"}">
      <span class="content-review-history-card__score">${kind === "ready" ? result.overallScore : kind === "active" ? "…" : "!"}</span>
      <span><small>${formatDate(run.createdAt)} · ${escapeHtml(PLATFORM_LABELS[run.input.platform] || run.input.platform || "—")}</small><strong>${escapeHtml(run.media?.name || "Материал")}</strong><em>${kind === "ready" ? escapeHtml(compliance.short) : kind === "active" ? "Проверяется" : "Ошибка"}${soundLabel ? ` · ${escapeHtml(soundLabel)}` : ""}</em></span>
      <i aria-hidden="true">→</i>
    </button>`;
}

function progressMarkup(title, description, step, run = null) {
  return `
    <div class="card content-review-progress" role="status">
      <div class="content-review-orbit" aria-hidden="true"><span></span><b>A</b></div>
      <p class="eyebrow">Шаг ${step} из 3</p><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p>
      <div class="content-review-progress__line" aria-hidden="true"><span style="width:${Math.min(100, step * 33.34)}%"></span></div>
      ${run?.id ? `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-content-review" data-review-id="${escapeHtml(run.id)}">Проверить сейчас</button>` : ""}
    </div>`;
}

function reviewMediaOptionMarkup(item, index, activeMediaIds) {
  const active = activeMediaIds instanceof Set && activeMediaIds.has(item.id);
  const preview = item.url
    ? item.isVideo
      ? `<video src="${escapeHtml(item.url)}" preload="metadata" muted playsinline></video><i aria-hidden="true">▶</i>`
      : `<img src="${escapeHtml(item.url)}" alt="" loading="lazy" />`
    : `<span aria-hidden="true">${item.isVideo ? "▶" : "▧"}</span>`;
  return `
    <label class="content-review-media-option ${active ? "is-disabled" : ""}" ${active ? 'aria-disabled="true"' : ""}>
      <input type="checkbox" name="media_id" value="${escapeHtml(item.id)}" data-media-type="${item.isVideo ? "video" : "image"}" data-product-id="${escapeHtml(item.productId)}" ${active ? "disabled" : ""} />
      <span class="content-review-media-option__preview">${preview}</span>
      <span><strong>${escapeHtml(item.name)}</strong><small>${item.isVideo ? "MP4-видео" : "Изображение"} · ${formatBytes(item.sizeBytes)}</small>${active ? "<em>Уже проверяется</em>" : ""}</span>
      <b aria-hidden="true">✓</b>
    </label>`;
}

function checkMarkup(name, title, hint) {
  return `<label class="content-review-check"><input type="checkbox" name="${escapeHtml(name)}" value="yes" /><span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(hint)}</small></span></label>`;
}

function toggleConditional(form, selector, visible) {
  form.querySelectorAll(selector).forEach((element) => {
    element.hidden = !visible;
    element.querySelectorAll("input, select, textarea").forEach((control) => {
      if (!visible && control.type === "checkbox") control.checked = false;
    });
  });
}

async function captureImageEvidence(media, onProgress) {
  onProgress?.({ stage: "image", completed: 0, total: 1 });
  const image = await loadImage(media.url);
  const canvas = drawSource(image, image.naturalWidth, image.naturalHeight);
  const frame = encodeCanvasBounded(canvas);
  const sample = sampleCanvas(canvas);
  onProgress?.({ stage: "image", completed: 1, total: 1 });
  return {
    frames: [frame],
    technical_metrics: {
      browser_preflight: true,
      source_type: "image",
      mime_type: media.mimeType,
      width: image.naturalWidth,
      height: image.naturalHeight,
      aspect_ratio: roundedRatio(image.naturalWidth, image.naturalHeight),
      orientation: orientation(image.naturalWidth, image.naturalHeight),
      frame_count: 1,
      frame_luminance: [sample.mean],
      frame_contrast: [sample.contrast],
      black_frame_ratio: sample.mean < 16 ? 1 : 0,
      frozen_frame_suspected: false,
      sampling_strategy: "single_still",
      raw_video_sent: false,
    },
  };
}

async function captureVideoEvidence(media, onProgress) {
  const video = document.createElement("video");
  video.crossOrigin = "anonymous";
  video.preload = "auto";
  video.muted = true;
  video.playsInline = true;
  try {
    await loadVideoMetadata(video, media.url);
    const width = Number(video.videoWidth);
    const height = Number(video.videoHeight);
    const sourceDuration = Number(video.duration);
    if (!width || !height || !Number.isFinite(sourceDuration) || sourceDuration < 0.01 || sourceDuration > 3_600) {
      throw userError("MP4 имеет неподдерживаемые параметры. Проверьте, что файл открывается, длиннее 0,01 секунды и не длиннее одного часа.");
    }
    const duration = round(sourceDuration, 3);
    const audioMetricsPromise = captureVideoAudioMetrics(media, duration);
    const targets = sampleTimes(duration);
    const frames = [];
    const samples = [];
    for (let index = 0; index < targets.length; index += 1) {
      onProgress?.({ stage: "video", completed: index, total: targets.length });
      await seekVideo(video, targets[index]);
      const canvas = drawSource(video, width, height);
      frames.push(encodeCanvasBounded(canvas));
      samples.push(sampleCanvas(canvas));
    }
    const differences = [];
    for (let index = 1; index < samples.length; index += 1) {
      differences.push(frameDifference(samples[index - 1].pixels, samples[index].pixels));
    }
    const frozenFrameRatio = differences.length
      ? round(differences.filter((value) => value < 0.015).length / differences.length, 3)
      : 0;
    const temporalEvidence = await captureVideoTemporalEvidence(
      video,
      duration,
      width,
      height,
      onProgress,
    );
    const continuityMetrics = await captureVideoContinuityMetrics(
      video,
      duration,
      onProgress,
    );
    frames.push(temporalEvidence.atlas);
    const sampledAtSeconds = [
      ...targets,
      temporalEvidence.metrics.timeline_atlas_last_second,
    ];
    const totalCharacters = frames.reduce((sum, frame) => sum + frame.length, 0);
    if (frames.length !== 5 || totalCharacters > MAX_TOTAL_FRAME_CHARACTERS) {
      throw userError("Не удалось подготовить безопасную выборку кадров и атлас. Обновите страницу и повторите проверку.");
    }
    const audioMetrics = await audioMetricsPromise;
    onProgress?.({ stage: "video", completed: targets.length, total: targets.length });
    return {
      frames,
      technical_metrics: {
        browser_preflight: true,
        source_type: "video",
        mime_type: media.mimeType,
        duration_seconds: round(duration, 3),
        width,
        height,
        aspect_ratio: roundedRatio(width, height),
        orientation: orientation(width, height),
        frame_count: frames.length,
        sampled_at_seconds: sampledAtSeconds.map((value) => round(value, 3)),
        frame_luminance: samples.map((sample) => sample.mean),
        frame_contrast: samples.map((sample) => sample.contrast),
        adjacent_frame_difference: differences,
        black_frame_ratio: round(samples.filter((sample) => sample.mean < 16).length / samples.length, 3),
        frozen_frame_ratio: frozenFrameRatio,
        frozen_frame_suspected: frozenFrameRatio >= 0.8,
        vertical_9_16_delta: round(Math.abs(width / height - 9 / 16), 4),
        sampling_strategy: "four_control_frames_plus_timeline_atlas_v1",
        raw_video_sent: false,
        speech_transcription_notice_version: "openai_mp4_v1",
        ...temporalEvidence.metrics,
        ...continuityMetrics,
        ...audioMetrics,
      },
    };
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
}

async function captureVideoTemporalEvidence(
  video,
  duration,
  sourceWidth,
  sourceHeight,
  onProgress,
) {
  const targets = temporalScanTimes(duration);
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_SAMPLE_SIZE;
  canvas.height = FRAME_SAMPLE_SIZE;
  const context = canvas.getContext("2d", {
    alpha: false,
    willReadFrequently: true,
  });
  if (!context) {
    throw userError("Браузер не поддерживает локальный скан таймлайна.");
  }
  const layout = timelineAtlasLayout(
    targets.length,
    sourceWidth,
    sourceHeight,
  );
  const atlasCanvas = document.createElement("canvas");
  atlasCanvas.width = layout.width;
  atlasCanvas.height = layout.height;
  const atlasContext = atlasCanvas.getContext("2d", { alpha: false });
  if (!atlasContext) {
    throw userError("Браузер не поддерживает подготовку атласа таймлайна.");
  }
  atlasContext.fillStyle = "#111827";
  atlasContext.fillRect(0, 0, atlasCanvas.width, atlasCanvas.height);
  atlasContext.font = "12px system-ui, sans-serif";
  atlasContext.textBaseline = "middle";
  const deadline = Date.now() + TEMPORAL_SCAN_TIMEOUT_MS;
  const samples = [];
  for (let index = 0; index < targets.length; index += 1) {
    onProgress?.({
      stage: "temporal_scan",
      completed: index,
      total: targets.length,
    });
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) {
      throw userError("Локальный скан таймлайна превысил лимит времени.");
    }
    await seekVideo(video, targets[index], Math.min(10_000, remainingMs));
    context.drawImage(
      video,
      0,
      0,
      FRAME_SAMPLE_SIZE,
      FRAME_SAMPLE_SIZE,
    );
    samples.push(sampleCanvas(canvas));
    const column = index % layout.columns;
    const row = Math.floor(index / layout.columns);
    const x = column * (layout.tileWidth + TIMELINE_ATLAS_GAP);
    const y = row * (layout.tileHeight + TIMELINE_ATLAS_GAP);
    const imageHeight = layout.tileHeight - TIMELINE_ATLAS_LABEL_HEIGHT;
    atlasContext.drawImage(
      video,
      x,
      y,
      layout.tileWidth,
      imageHeight,
    );
    atlasContext.fillStyle = "#111827";
    atlasContext.fillRect(
      x,
      y + imageHeight,
      layout.tileWidth,
      TIMELINE_ATLAS_LABEL_HEIGHT,
    );
    atlasContext.fillStyle = "#ffffff";
    atlasContext.fillText(
      `${index + 1} · ${round(targets[index], 2)}s`,
      x + 4,
      y + imageHeight + TIMELINE_ATLAS_LABEL_HEIGHT / 2,
      Math.max(1, layout.tileWidth - 8),
    );
  }
  onProgress?.({
    stage: "temporal_scan",
    completed: targets.length,
    total: targets.length,
  });
  return {
    atlas: encodeCanvasBounded(atlasCanvas),
    metrics: {
      ...analyzeTemporalVideoSamples(samples, targets, duration),
      ...analyzeTimelineAtlas(
        targets,
        duration,
        layout.columns,
        layout.rows,
      ),
    },
  };
}

export function analyzeTemporalVideoSamples(
  samples,
  sampledAtSeconds,
  durationSeconds,
) {
  const duration = Number(durationSeconds);
  if (
    !Array.isArray(samples)
    || !Array.isArray(sampledAtSeconds)
    || samples.length !== sampledAtSeconds.length
    || samples.length < MIN_TEMPORAL_SCAN_FRAMES
    || samples.length > MAX_TEMPORAL_SCAN_FRAMES
    || !Number.isFinite(duration)
    || duration <= 0
    || duration > 3_600
  ) {
    throw userError("Локальный скан таймлайна имеет неверный размер.");
  }
  const times = sampledAtSeconds.map(Number);
  const validTimes = times.every((value, index) =>
    Number.isFinite(value)
    && value >= 0
    && value <= duration
    && (index === 0 || value > times[index - 1])
  );
  const validSamples = samples.every((sample) =>
    Number.isFinite(Number(sample?.mean))
    && Number(sample.mean) >= 0
    && Number(sample.mean) <= 255
    && sample?.pixels instanceof Uint8Array
    && sample.pixels.length > 0
  );
  if (!validTimes || !validSamples) {
    throw userError("Локальный скан таймлайна содержит повреждённые точки.");
  }
  const coverage = (times.at(-1) - times[0]) / duration;
  if (coverage < TEMPORAL_SCAN_MIN_COVERAGE || coverage > 1) {
    throw userError("Локальный скан не покрывает достаточную часть ролика.");
  }
  const differences = [];
  for (let index = 1; index < samples.length; index += 1) {
    differences.push(
      frameDifference(samples[index - 1].pixels, samples[index].pixels),
    );
  }
  const meanDifference = differences.length
    ? differences.reduce((sum, value) => sum + value, 0) /
      differences.length
    : 0;
  return {
    temporal_scan_status: "completed",
    temporal_scan_strategy: "uniform_full_duration_v1",
    temporal_scan_frame_count: samples.length,
    temporal_scan_first_second: round(times[0], 3),
    temporal_scan_last_second: round(times.at(-1), 3),
    temporal_scan_coverage_ratio: round(coverage, 4),
    temporal_black_frame_ratio: round(
      samples.filter((sample) => sample.mean < TEMPORAL_BLACK_LUMA).length /
        samples.length,
      4,
    ),
    temporal_frozen_transition_ratio: round(
      differences.filter((value) => value < TEMPORAL_FROZEN_DIFFERENCE)
        .length / differences.length,
      4,
    ),
    temporal_mean_frame_difference: round(meanDifference, 4),
  };
}

async function captureVideoContinuityMetrics(video, duration, onProgress) {
  if (round(duration, 3) > CONTINUITY_SCAN_MAX_DURATION_SECONDS) {
    return {
      continuity_scan_status: "not_applicable",
      continuity_scan_strategy: "browser_presented_frames_v1",
      continuity_scan_not_applicable_reason: "duration_above_short_video_limit",
      continuity_scan_duration_limit_seconds:
        CONTINUITY_SCAN_MAX_DURATION_SECONDS,
    };
  }
  if (typeof video.requestVideoFrameCallback !== "function") {
    return captureVideoDenseSeekContinuityMetrics(
      video,
      duration,
      onProgress,
      "rvfc_unavailable",
    );
  }
  try {
    return await captureBrowserPresentedFrameContinuityMetrics(
      video,
      duration,
      onProgress,
    );
  } catch (error) {
    const fallbackReason = continuityDenseSeekFallbackReason(error);
    if (!fallbackReason) throw error;
    return captureVideoDenseSeekContinuityMetrics(
      video,
      duration,
      onProgress,
      fallbackReason,
    );
  }
}

async function captureBrowserPresentedFrameContinuityMetrics(
  video,
  duration,
  onProgress,
) {
  await seekVideo(video, 0);
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_SAMPLE_SIZE;
  canvas.height = FRAME_SAMPLE_SIZE;
  const context = canvas.getContext("2d", {
    alpha: false,
    willReadFrequently: true,
  });
  if (!context) {
    throw userError("Браузер не поддерживает локальный контроль кадров.");
  }
  const samples = [];
  const mediaTimes = [];
  const presentedFrames = [];
  const timeoutMs = Math.ceil(duration * 1_000) +
    CONTINUITY_SCAN_TIMEOUT_PADDING_MS;
  const previousPlaybackRate = video.playbackRate;
  video.playbackRate = 1;
  try {
    await new Promise((resolve, reject) => {
      let callbackId = 0;
      let settled = false;
      const cleanup = () => {
        window.clearTimeout(timer);
        video.removeEventListener("ended", onEnded);
        video.removeEventListener("error", onError);
        if (
          callbackId &&
          typeof video.cancelVideoFrameCallback === "function"
        ) {
          video.cancelVideoFrameCallback(callbackId);
        }
      };
      const finish = (handler) => {
        if (settled) return;
        settled = true;
        cleanup();
        handler();
      };
      const onEnded = () => finish(resolve);
      const onError = () => finish(() => reject(
        userError("Не удалось локально проиграть короткий MP4 по кадрам."),
      ));
      const timer = window.setTimeout(() => finish(() => reject(
        userError("Покадровый локальный контроль MP4 превысил лимит времени."),
      )), timeoutMs);
      const onFrame = (_now, metadata) => {
        if (settled) return;
        try {
          if (samples.length >= CONTINUITY_SCAN_MAX_FRAMES) {
            finish(() => reject(
              userError("Короткий MP4 содержит слишком много кадров для безопасного локального контроля."),
            ));
            return;
          }
          context.drawImage(
            video,
            0,
            0,
            FRAME_SAMPLE_SIZE,
            FRAME_SAMPLE_SIZE,
          );
          samples.push(sampleCanvasContext(context));
          mediaTimes.push(Number(metadata?.mediaTime));
          presentedFrames.push(Number(metadata?.presentedFrames));
          onProgress?.({
            stage: "continuity_scan",
            completed: Math.min(
              Math.ceil(duration * 10),
              Math.max(
                1,
                Math.ceil(Number(metadata?.mediaTime || 0) * 10),
              ),
            ),
            total: Math.max(1, Math.ceil(duration * 10)),
          });
          callbackId = video.requestVideoFrameCallback(onFrame);
        } catch (error) {
          finish(() => reject(
            error instanceof Error
              ? error
              : userError("Не удалось измерить один из кадров короткого MP4."),
          ));
        }
      };
      video.addEventListener("ended", onEnded, { once: true });
      video.addEventListener("error", onError, { once: true });
      callbackId = video.requestVideoFrameCallback(onFrame);
      video.play().catch(onError);
    });
  } finally {
    video.pause();
    video.playbackRate = previousPlaybackRate;
  }
  return analyzeVideoContinuitySamples(
    samples,
    mediaTimes,
    presentedFrames,
    duration,
  );
}

export function continuityDenseSeekFallbackReason(error) {
  const reason = String(error?.continuityFallbackReason || "");
  return CONTINUITY_DENSE_SEEK_FALLBACK_REASONS.has(reason) ? reason : "";
}

export function denseSeekContinuityTargets(durationSeconds) {
  const duration = Number(durationSeconds);
  if (
    !Number.isFinite(duration)
    || duration <= 0
    || duration > CONTINUITY_SCAN_MAX_DURATION_SECONDS + 0.001
  ) {
    throw userError("Плотный локальный контроль имеет неверную длительность.");
  }
  const sampleCount = Math.min(
    CONTINUITY_DENSE_SEEK_MAX_SAMPLES,
    Math.max(
      CONTINUITY_DENSE_SEEK_MIN_SAMPLES,
      Math.ceil(
        duration * CONTINUITY_DENSE_SEEK_SAMPLES_PER_SECOND,
      ) + 1,
    ),
  );
  const endpointMargin = Math.min(0.01, duration * 0.01);
  const first = endpointMargin;
  const last = duration - endpointMargin;
  const span = last - first;
  if (!(span > 0)) {
    throw userError("Плотный локальный контроль не получил безопасный диапазон.");
  }
  return Array.from({ length: sampleCount }, (_value, index) => (
    first + span * index / (sampleCount - 1)
  ));
}

async function captureVideoDenseSeekContinuityMetrics(
  video,
  duration,
  onProgress,
  fallbackReason,
) {
  if (!CONTINUITY_DENSE_SEEK_FALLBACK_REASONS.has(fallbackReason)) {
    throw userError("Плотный локальный контроль нельзя запускать для этой ошибки.");
  }
  const targets = denseSeekContinuityTargets(duration);
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_SAMPLE_SIZE;
  canvas.height = FRAME_SAMPLE_SIZE;
  const context = canvas.getContext("2d", {
    alpha: false,
    willReadFrequently: true,
  });
  if (!context) {
    throw userError("Браузер не поддерживает плотный локальный контроль кадров.");
  }
  const samples = [];
  const actualTimes = [];
  const deadline = Date.now() + CONTINUITY_DENSE_SEEK_TIMEOUT_MS;
  video.pause();
  for (let index = 0; index < targets.length; index += 1) {
    const remainingMs = deadline - Date.now();
    if (remainingMs <= 0) {
      throw userError("Плотный локальный контроль MP4 превысил лимит времени.");
    }
    await seekDenseContinuityTarget(
      video,
      targets[index],
      Math.min(5_000, remainingMs),
    );
    const actualTime = Number(video.currentTime);
    if (
      !Number.isFinite(actualTime)
      || Math.abs(actualTime - targets[index]) >
        CONTINUITY_DENSE_SEEK_MAX_TARGET_DRIFT_SECONDS
    ) {
      throw userError("Браузер отклонился от точек плотного локального контроля.");
    }
    try {
      context.drawImage(
        video,
        0,
        0,
        FRAME_SAMPLE_SIZE,
        FRAME_SAMPLE_SIZE,
      );
      samples.push(sampleCanvasContext(context));
    } catch (error) {
      throw error instanceof Error
        ? error
        : userError("Не удалось измерить точку плотного локального контроля.");
    }
    actualTimes.push(actualTime);
    onProgress?.({
      stage: "continuity_dense_seek",
      completed: index + 1,
      total: targets.length,
    });
  }
  return analyzeDenseSeekContinuitySamples(
    samples,
    actualTimes,
    duration,
    fallbackReason,
  );
}

async function seekDenseContinuityTarget(video, seconds, timeoutMs) {
  if (
    Math.abs(Number(video.currentTime || 0) - seconds) < 0.0001
    && video.readyState >= 2
  ) return;
  const wait = waitForEvent(
    video,
    "seeked",
    timeoutMs,
    "Не удалось считать точку плотного локального контроля MP4.",
  );
  video.currentTime = seconds;
  await wait;
}

export function analyzeDenseSeekContinuitySamples(
  samples,
  actualTimes,
  durationSeconds,
  fallbackReason,
) {
  const duration = Number(durationSeconds);
  const targets = denseSeekContinuityTargets(duration);
  if (
    !CONTINUITY_DENSE_SEEK_FALLBACK_REASONS.has(fallbackReason)
    || !Array.isArray(samples)
    || !Array.isArray(actualTimes)
    || samples.length !== targets.length
    || actualTimes.length !== targets.length
  ) {
    throw userError("Плотный локальный контроль имеет неверный размер.");
  }
  const times = actualTimes.map(Number);
  const validTimes = times.every((value, index) => (
    Number.isFinite(value)
    && value >= 0
    && value <= duration
    && (index === 0 || value > times[index - 1])
    && Math.abs(value - targets[index]) <=
      CONTINUITY_DENSE_SEEK_MAX_TARGET_DRIFT_SECONDS
  ));
  const validSamples = samples.every((sample) => (
    Number.isFinite(Number(sample?.mean))
    && Number(sample.mean) >= 0
    && Number(sample.mean) <= 255
    && sample?.pixels instanceof Uint8Array
    && sample.pixels.length > 0
  ));
  if (!validTimes || !validSamples) {
    throw userError("Плотный локальный контроль содержит повреждённые данные.");
  }
  const coverage = (times.at(-1) - times[0]) / duration;
  const gaps = [
    times[0],
    duration - times.at(-1),
    ...times.slice(1).map((value, index) => value - times[index]),
  ];
  const maxGap = Math.max(...gaps);
  const maxTargetDrift = Math.max(
    ...times.map((value, index) => Math.abs(value - targets[index])),
  );
  if (
    coverage < 0.98
    || coverage > 1
    || maxGap > CONTINUITY_DENSE_SEEK_MAX_GAP_SECONDS
    || maxTargetDrift > CONTINUITY_DENSE_SEEK_MAX_TARGET_DRIFT_SECONDS
  ) {
    throw userError("Плотный локальный контроль не покрыл короткий ролик.");
  }
  const differences = samples.slice(1).map((sample, index) => (
    frameDifference(samples[index].pixels, sample.pixels)
  ));
  const blackFlags = samples.map(
    (sample) => sample.mean < TEMPORAL_BLACK_LUMA,
  );
  const duplicateFlags = differences.map(
    (value) => value < CONTINUITY_DUPLICATE_DIFFERENCE,
  );
  const meanDifference = differences.reduce(
    (sum, value) => sum + value,
    0,
  ) / differences.length;
  return {
    continuity_scan_status: "completed",
    continuity_scan_strategy: "browser_dense_seek_v2",
    continuity_scan_sample_count: samples.length,
    continuity_scan_target_fps: CONTINUITY_DENSE_SEEK_SAMPLES_PER_SECOND,
    continuity_scan_target_max_drift_seconds: round(maxTargetDrift, 4),
    continuity_scan_fallback_reason: fallbackReason,
    continuity_scan_first_second: round(times[0], 4),
    continuity_scan_last_second: round(times.at(-1), 4),
    continuity_scan_coverage_ratio: round(coverage, 4),
    continuity_scan_max_gap_seconds: round(maxGap, 4),
    continuity_black_frame_ratio: round(
      blackFlags.filter(Boolean).length / blackFlags.length,
      4,
    ),
    continuity_longest_black_run_seconds: round(
      longestBooleanSampleRun(blackFlags, times, duration),
      4,
    ),
    continuity_duplicate_transition_ratio: round(
      duplicateFlags.filter(Boolean).length / duplicateFlags.length,
      4,
    ),
    continuity_longest_duplicate_run_seconds: round(
      longestBooleanTransitionRun(duplicateFlags, times, duration),
      4,
    ),
    continuity_mean_frame_difference: round(meanDifference, 4),
    continuity_raw_frames_persisted: false,
  };
}

export function analyzeVideoContinuitySamples(
  samples,
  mediaTimes,
  presentedFrames,
  durationSeconds,
) {
  const duration = Number(durationSeconds);
  if (
    !Array.isArray(samples)
    || !Array.isArray(mediaTimes)
    || !Array.isArray(presentedFrames)
    || samples.length !== mediaTimes.length
    || samples.length !== presentedFrames.length
    || samples.length < 2
    || samples.length > CONTINUITY_SCAN_MAX_FRAMES
    || !Number.isFinite(duration)
    || duration <= 0
    || duration > CONTINUITY_SCAN_MAX_DURATION_SECONDS + 0.001
  ) {
    throw userError("Покадровый локальный контроль имеет неверный размер.");
  }
  const times = mediaTimes.map(Number);
  const frameNumbers = presentedFrames.map(Number);
  const validTimes = times.every((value, index) =>
    Number.isFinite(value)
    && value >= 0
    && value <= duration
    && (index === 0 || value > times[index - 1])
  );
  const validFrameNumbers = frameNumbers.every((value, index) =>
    Number.isInteger(value)
    && value >= 1
    && (index === 0 || value > frameNumbers[index - 1])
  );
  const validSamples = samples.every((sample) =>
    Number.isFinite(Number(sample?.mean))
    && Number(sample.mean) >= 0
    && Number(sample.mean) <= 255
    && sample?.pixels instanceof Uint8Array
    && sample.pixels.length > 0
  );
  if (!validTimes || !validFrameNumbers || !validSamples) {
    throw userError("Покадровый локальный контроль содержит повреждённые данные.");
  }
  const coverage = (times.at(-1) - times[0]) / duration;
  const gaps = [
    times[0],
    duration - times.at(-1),
    ...times.slice(1).map((value, index) => value - times[index]),
  ];
  const maxGap = Math.max(...gaps);
  if (coverage < CONTINUITY_SCAN_MIN_COVERAGE || coverage > 1) {
    throw continuityReliabilityError(
      "Покадровый локальный контроль не покрыл достаточную часть короткого ролика.",
      "rvfc_coverage_unreliable",
    );
  }
  if (maxGap > CONTINUITY_SCAN_MAX_GAP_SECONDS) {
    throw continuityReliabilityError(
      "Покадровый локальный контроль оставил слишком большой разрыв между кадрами.",
      "rvfc_max_gap_unreliable",
    );
  }
  const differences = samples.slice(1).map((sample, index) =>
    frameDifference(samples[index].pixels, sample.pixels)
  );
  const blackFlags = samples.map(
    (sample) => sample.mean < TEMPORAL_BLACK_LUMA,
  );
  const duplicateFlags = differences.map(
    (value) => value < CONTINUITY_DUPLICATE_DIFFERENCE,
  );
  const callbackCount = samples.length;
  const presentedFrameCount = frameNumbers.at(-1) - frameNumbers[0] + 1;
  const missedFrameCount = Math.max(0, presentedFrameCount - callbackCount);
  if (missedFrameCount !== 0) {
    throw continuityReliabilityError(
      "Браузер пропустил показанный кадр во время локального контроля. Повторите проверку в активной вкладке.",
      "rvfc_missed_frames",
    );
  }
  const meanDifference = differences.reduce(
    (sum, value) => sum + value,
    0,
  ) / differences.length;
  return {
    continuity_scan_status: "completed",
    continuity_scan_strategy: "browser_presented_frames_v1",
    continuity_scan_callback_count: callbackCount,
    continuity_scan_presented_frame_count: presentedFrameCount,
    continuity_scan_missed_frame_count: missedFrameCount,
    continuity_scan_first_second: round(times[0], 4),
    continuity_scan_last_second: round(times.at(-1), 4),
    continuity_scan_coverage_ratio: round(coverage, 4),
    continuity_scan_max_gap_seconds: round(maxGap, 4),
    continuity_black_frame_ratio: round(
      blackFlags.filter(Boolean).length / blackFlags.length,
      4,
    ),
    continuity_longest_black_run_seconds: round(
      longestBooleanSampleRun(blackFlags, times, duration),
      4,
    ),
    continuity_duplicate_transition_ratio: round(
      duplicateFlags.filter(Boolean).length / duplicateFlags.length,
      4,
    ),
    continuity_longest_duplicate_run_seconds: round(
      longestBooleanTransitionRun(duplicateFlags, times, duration),
      4,
    ),
    continuity_mean_frame_difference: round(meanDifference, 4),
    continuity_raw_frames_persisted: false,
  };
}

function continuityReliabilityError(message, fallbackReason) {
  const error = userError(message);
  error.continuityFallbackReason = fallbackReason;
  return error;
}

function longestBooleanSampleRun(flags, times, duration) {
  let start = null;
  let longest = 0;
  for (let index = 0; index < flags.length; index += 1) {
    if (flags[index] && start === null) start = times[index];
    if (!flags[index] && start !== null) {
      longest = Math.max(longest, times[index] - start);
      start = null;
    }
  }
  if (start !== null) longest = Math.max(longest, duration - start);
  return longest;
}

function longestBooleanTransitionRun(flags, times, duration) {
  let start = null;
  let longest = 0;
  for (let index = 0; index < flags.length; index += 1) {
    if (flags[index] && start === null) start = times[index];
    if (!flags[index] && start !== null) {
      longest = Math.max(longest, times[index] - start);
      start = null;
    }
  }
  if (start !== null) longest = Math.max(longest, duration - start);
  return longest;
}

function temporalScanTimes(duration) {
  const count = Math.max(
    MIN_TEMPORAL_SCAN_FRAMES,
    Math.min(
      MAX_TEMPORAL_SCAN_FRAMES,
      Math.ceil(duration * TEMPORAL_SCAN_FRAMES_PER_SECOND),
    ),
  );
  const inset = Math.min(0.02, duration * 0.01);
  const first = inset;
  const last = Math.max(first, duration - inset);
  return Array.from(
    { length: count },
    (_, index) => first + (last - first) * index / (count - 1),
  );
}

export function analyzeTimelineAtlas(
  sampledAtSeconds,
  durationSeconds,
  columns,
  rows,
) {
  const duration = Number(durationSeconds);
  const times = Array.isArray(sampledAtSeconds)
    ? sampledAtSeconds.map(Number)
    : [];
  const columnCount = Number(columns);
  const rowCount = Number(rows);
  const validTimes = times.length >= MIN_TEMPORAL_SCAN_FRAMES
    && times.length <= MAX_TEMPORAL_SCAN_FRAMES
    && times.every((value, index) =>
      Number.isFinite(value)
      && value >= 0
      && value <= duration
      && (index === 0 || value > times[index - 1])
    );
  if (
    !Number.isFinite(duration)
    || duration <= 0
    || duration > 3_600
    || !validTimes
    || !Number.isInteger(columnCount)
    || !Number.isInteger(rowCount)
    || columnCount < 2
    || columnCount > 8
    || rowCount < 2
    || rowCount > 8
    || columnCount * rowCount < times.length
    || columnCount * (rowCount - 1) >= times.length
  ) {
    throw userError("Атлас таймлайна имеет неверный контракт.");
  }
  const gaps = [
    times[0],
    duration - times.at(-1),
    ...times.slice(1).map((value, index) => value - times[index]),
  ];
  const coverage = (times.at(-1) - times[0]) / duration;
  const maxGap = Math.max(...gaps);
  return {
    timeline_atlas_status: "completed",
    timeline_atlas_version: "dense_full_duration_v1",
    timeline_atlas_frame_ordinal: 5,
    timeline_atlas_frame_count: times.length,
    timeline_atlas_first_second: round(times[0], 3),
    timeline_atlas_last_second: round(times.at(-1), 3),
    timeline_atlas_coverage_ratio: round(coverage, 4),
    timeline_atlas_max_gap_seconds: round(maxGap, 4),
    timeline_atlas_sample_rate_fps: round(times.length / duration, 4),
    timeline_atlas_columns: columnCount,
    timeline_atlas_rows: rowCount,
    timeline_atlas_order: "row_major_chronological",
    timeline_atlas_dense_short_video:
      duration <= TIMELINE_ATLAS_DENSE_MAX_DURATION_SECONDS
      && coverage >= TEMPORAL_SCAN_MIN_COVERAGE
      && maxGap <= TIMELINE_ATLAS_DENSE_MAX_GAP_SECONDS,
  };
}

function timelineAtlasLayout(frameCount, sourceWidth, sourceHeight) {
  const aspectRatio = sourceWidth / sourceHeight;
  const columns = Math.max(
    2,
    Math.ceil(frameCount / 8),
    Math.min(
      8,
      Math.ceil(Math.sqrt(1.2 * frameCount / aspectRatio)),
    ),
  );
  const rows = Math.ceil(frameCount / columns);
  const widthBound = Math.floor(
    (
      TIMELINE_ATLAS_MAX_DIMENSION -
      TIMELINE_ATLAS_GAP * (columns - 1)
    ) / columns,
  );
  const tileHeightBound = Math.floor(
    (
      TIMELINE_ATLAS_MAX_DIMENSION -
      TIMELINE_ATLAS_GAP * (rows - 1)
    ) / rows,
  );
  const imageHeightBound = tileHeightBound - TIMELINE_ATLAS_LABEL_HEIGHT;
  const tileWidth = Math.min(
    240,
    widthBound,
    Math.floor(imageHeightBound * aspectRatio),
  );
  if (tileWidth < 16 || imageHeightBound < 16) {
    throw userError("Пропорции MP4 не позволяют безопасно собрать атлас таймлайна.");
  }
  const tileHeight = Math.round(tileWidth / aspectRatio) +
    TIMELINE_ATLAS_LABEL_HEIGHT;
  return {
    columns,
    rows,
    tileWidth,
    tileHeight,
    width: columns * tileWidth + (columns - 1) * TIMELINE_ATLAS_GAP,
    height: rows * tileHeight + (rows - 1) * TIMELINE_ATLAS_GAP,
  };
}

async function captureVideoAudioMetrics(media, videoDurationSeconds) {
  const unavailable = {
    audio_expected: typeof media.audioExpected === "boolean"
      ? media.audioExpected
      : null,
    audio_analyzed: false,
    audio_analysis_status: "unavailable",
  };
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (typeof AudioContextClass !== "function") return unavailable;

  const controller = new AbortController();
  let rejectTimeout;
  const timeout = new Promise((_, reject) => {
    rejectTimeout = reject;
  });
  const timer = window.setTimeout(() => {
    controller.abort();
    rejectTimeout(userError("Локальная проверка звука превысила лимит времени."));
  }, AUDIO_ANALYSIS_TIMEOUT_MS);
  let context;
  try {
    return await Promise.race([
      (async () => {
        const response = await fetch(media.url, {
          method: "GET",
          cache: "no-store",
          credentials: "omit",
          redirect: "error",
          referrerPolicy: "no-referrer",
          signal: controller.signal,
        });
        const mimeType = String(response.headers.get("content-type") || "")
          .split(";", 1)[0]
          .trim()
          .toLowerCase();
        if (!response.ok || mimeType !== "video/mp4") {
          await response.body?.cancel();
          return unavailable;
        }
        const bytes = await readResponseArrayBufferBounded(
          response,
          MAX_AUDIO_SOURCE_BYTES,
        );
        context = new AudioContextClass();
        const decoded = await context.decodeAudioData(bytes);
        return analyzeDecodedAudioBuffer(decoded, {
          expectedAudio: media.audioExpected,
          videoDurationSeconds,
        });
      })(),
      timeout,
    ]);
  } catch {
    return unavailable;
  } finally {
    window.clearTimeout(timer);
    if (context && typeof context.close === "function") {
      await context.close().catch(() => {});
    }
  }
}

async function readResponseArrayBufferBounded(response, maxBytes) {
  const contentLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(contentLength) && contentLength > maxBytes) {
    await response.body?.cancel();
    throw userError("MP4 слишком большой для локальной проверки звука.");
  }
  if (!response.body || typeof response.body.getReader !== "function") {
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > maxBytes) {
      throw userError("MP4 слишком большой для локальной проверки звука.");
    }
    return bytes;
  }

  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!(value instanceof Uint8Array)) {
        throw userError("Не удалось безопасно прочитать звук MP4.");
      }
      total += value.byteLength;
      if (total > maxBytes) {
        await reader.cancel();
        throw userError("MP4 слишком большой для локальной проверки звука.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const combined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return combined.buffer;
}

export function analyzeDecodedAudioBuffer(
  audioBuffer,
  { expectedAudio = null, videoDurationSeconds = null } = {},
) {
  const channelCount = Number(audioBuffer?.numberOfChannels);
  const sampleRate = Number(audioBuffer?.sampleRate);
  const frameCount = Number(audioBuffer?.length);
  const duration = Number(audioBuffer?.duration);
  if (
    !Number.isInteger(channelCount)
    || channelCount < 1
    || channelCount > 32
    || !Number.isFinite(sampleRate)
    || sampleRate < 8_000
    || sampleRate > 384_000
    || !Number.isInteger(frameCount)
    || frameCount < 1
    || !Number.isFinite(duration)
    || duration <= 0
    || duration > 3_600
    || typeof audioBuffer?.getChannelData !== "function"
  ) {
    throw userError("Звуковая дорожка имеет неподдерживаемые параметры.");
  }

  const channels = [];
  for (let channel = 0; channel < channelCount; channel += 1) {
    const samples = audioBuffer.getChannelData(channel);
    if (!(samples instanceof Float32Array) || samples.length !== frameCount) {
      throw userError("Не удалось прочитать звуковую дорожку MP4.");
    }
    channels.push(samples);
  }

  const sampleStride = Math.max(
    1,
    Math.ceil(frameCount / MAX_AUDIO_ANALYSIS_SAMPLES),
  );
  let sumSquares = 0;
  let peak = 0;
  let clipped = 0;
  let analyzedSamples = 0;
  for (let frame = 0; frame < frameCount; frame += sampleStride) {
    for (const channel of channels) {
      const value = Math.max(-1, Math.min(1, Number(channel[frame]) || 0));
      const absolute = Math.abs(value);
      sumSquares += value * value;
      peak = Math.max(peak, absolute);
      if (absolute >= 0.99) clipped += 1;
      analyzedSamples += 1;
    }
  }
  const rms = analyzedSamples ? Math.sqrt(sumSquares / analyzedSamples) : 0;

  const silenceWindowFrames = Math.max(
    1,
    Math.ceil(sampleRate * 0.02),
    Math.ceil(frameCount / MAX_AUDIO_SILENCE_WINDOWS),
  );
  let silentWindows = 0;
  let totalWindows = 0;
  for (
    let start = 0;
    start < frameCount;
    start += silenceWindowFrames
  ) {
    const end = Math.min(frameCount, start + silenceWindowFrames);
    const windowStride = Math.max(1, Math.ceil((end - start) / 256));
    let windowSquares = 0;
    let windowSamples = 0;
    for (let frame = start; frame < end; frame += windowStride) {
      for (const channel of channels) {
        const value = Math.max(-1, Math.min(1, Number(channel[frame]) || 0));
        windowSquares += value * value;
        windowSamples += 1;
      }
    }
    const windowRms = windowSamples
      ? Math.sqrt(windowSquares / windowSamples)
      : 0;
    if (amplitudeDbfs(windowRms) <= AUDIO_SILENCE_DBFS) silentWindows += 1;
    totalWindows += 1;
  }

  const safeVideoDuration = Number(videoDurationSeconds);
  return {
    audio_expected: typeof expectedAudio === "boolean" ? expectedAudio : null,
    audio_analyzed: true,
    audio_analysis_status: "completed",
    audio_channel_count: channelCount,
    audio_sample_rate_hz: Math.round(sampleRate),
    audio_duration_seconds: round(duration, 3),
    audio_video_duration_delta_seconds: Number.isFinite(safeVideoDuration)
      ? round(Math.abs(duration - safeVideoDuration), 3)
      : null,
    audio_peak_dbfs: round(amplitudeDbfs(peak), 2),
    audio_rms_dbfs: round(amplitudeDbfs(rms), 2),
    audio_silence_ratio: round(
      totalWindows ? silentWindows / totalWindows : 1,
      4,
    ),
    audio_clipping_ratio: round(
      analyzedSamples ? clipped / analyzedSamples : 0,
      6,
    ),
  };
}

function amplitudeDbfs(value) {
  const amplitude = Math.max(0, Number(value) || 0);
  return Math.max(-160, Math.min(0, 20 * Math.log10(Math.max(amplitude, 1e-8))));
}

function sampleTimes(duration) {
  const safeEnd = Math.max(0, duration - Math.min(0.05, duration / 20));
  if (safeEnd < 2.05) {
    return [0.05, 0.3, 0.58, 0.82]
      .map((fraction) => Math.min(safeEnd, Math.max(0, duration * fraction)));
  }
  return [
    0.2,
    1,
    2,
    Math.max(2.2, duration * 0.72),
  ].map((seconds) => Math.min(safeEnd, Math.max(0, seconds)));
}

async function seekVideo(video, seconds, timeoutMs = 10_000) {
  if (Math.abs(Number(video.currentTime || 0) - seconds) < 0.01 && video.readyState >= 2) return;
  const wait = waitForEvent(video, "seeked", timeoutMs, "Не удалось считать один из кадров MP4.");
  video.currentTime = seconds;
  await wait;
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const timer = window.setTimeout(() => reject(userError("Изображение загружается слишком долго. Обновите защищённую ссылку и повторите.")), 15_000);
    image.crossOrigin = "anonymous";
    image.onload = () => {
      window.clearTimeout(timer);
      if (!image.naturalWidth || !image.naturalHeight) reject(userError("Не удалось прочитать изображение."));
      else resolve(image);
    };
    image.onerror = () => {
      window.clearTimeout(timer);
      reject(userError("Не удалось открыть изображение для проверки. Обновите раздел и повторите."));
    };
    image.src = url;
  });
}

function waitForEvent(target, eventName, timeoutMs, message) {
  return new Promise((resolve, reject) => {
    let timer;
    const cleanup = () => {
      window.clearTimeout(timer);
      target.removeEventListener(eventName, onSuccess);
      target.removeEventListener("error", onError);
    };
    const onSuccess = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(userError(message));
    };
    target.addEventListener(eventName, onSuccess, { once: true });
    target.addEventListener("error", onError, { once: true });
    timer = window.setTimeout(onError, timeoutMs);
  });
}

function loadVideoMetadata(video, url, timeoutMs = 15_000) {
  return new Promise((resolve, reject) => {
    let settled = false;
    let timer = 0;
    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeEventListener("loadedmetadata", onSuccess);
      video.removeEventListener("error", onError);
    };
    const onSuccess = () => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve();
    };
    const onError = () => {
      if (settled) return;
      settled = true;
      const mediaErrorCode = Number(video.error?.code) || 0;
      const networkState = Number(video.networkState) || 0;
      const readyState = Number(video.readyState) || 0;
      cleanup();
      reject(userError(
        `Не удалось прочитать параметры MP4 (media=${mediaErrorCode}, network=${networkState}, ready=${readyState}).`,
      ));
    };
    video.addEventListener("loadedmetadata", onSuccess, { once: true });
    video.addEventListener("error", onError, { once: true });
    timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(userError("Чтение параметров MP4 заняло больше 15 секунд."));
    }, timeoutMs);
    video.src = url;
    video.load();
    if (video.readyState >= 1) window.queueMicrotask(onSuccess);
  });
}

function drawSource(source, sourceWidth, sourceHeight) {
  const maxDimension = 720;
  const scale = Math.min(1, maxDimension / Math.max(sourceWidth, sourceHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sourceWidth * scale));
  canvas.height = Math.max(1, Math.round(sourceHeight * scale));
  const context = canvas.getContext("2d", { alpha: false, willReadFrequently: true });
  if (!context) throw userError("Браузер не поддерживает безопасное чтение кадров.");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
}

function encodeCanvasBounded(sourceCanvas) {
  let canvas = sourceCanvas;
  for (let iteration = 0; iteration < 5; iteration += 1) {
    for (const quality of [0.78, 0.68, 0.58, 0.48]) {
      let encoded;
      try {
        encoded = canvas.toDataURL("image/jpeg", quality);
      } catch {
        throw userError("Браузер заблокировал чтение кадра. Обновите защищённую ссылку и повторите.");
      }
      if (encoded.length <= MAX_FRAME_CHARACTERS) return encoded;
    }
    const smaller = document.createElement("canvas");
    smaller.width = Math.max(160, Math.round(canvas.width * 0.8));
    smaller.height = Math.max(160, Math.round(canvas.height * 0.8));
    const context = smaller.getContext("2d", { alpha: false });
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, smaller.width, smaller.height);
    context.drawImage(canvas, 0, 0, smaller.width, smaller.height);
    canvas = smaller;
  }
  throw userError("Кадр слишком большой для безопасной проверки. Уменьшите разрешение файла.");
}

function sampleCanvas(sourceCanvas) {
  const canvas = document.createElement("canvas");
  canvas.width = FRAME_SAMPLE_SIZE;
  canvas.height = FRAME_SAMPLE_SIZE;
  const context = canvas.getContext("2d", { alpha: false, willReadFrequently: true });
  if (!context) throw userError("Браузер не поддерживает техническую проверку кадров.");
  try {
    context.drawImage(sourceCanvas, 0, 0, FRAME_SAMPLE_SIZE, FRAME_SAMPLE_SIZE);
    return sampleCanvasContext(context);
  } catch {
    throw userError("Браузер заблокировал техническое чтение кадра. Обновите защищённую ссылку.");
  }
}

function sampleCanvasContext(context) {
  const data = context.getImageData(
    0,
    0,
    FRAME_SAMPLE_SIZE,
    FRAME_SAMPLE_SIZE,
  ).data;
  const pixels = new Uint8Array(FRAME_SAMPLE_SIZE * FRAME_SAMPLE_SIZE);
  let total = 0;
  for (let index = 0, pixel = 0; index < data.length; index += 4, pixel += 1) {
    const luma = Math.round(data[index] * 0.2126 + data[index + 1] * 0.7152 + data[index + 2] * 0.0722);
    pixels[pixel] = luma;
    total += luma;
  }
  const mean = total / pixels.length;
  let variance = 0;
  pixels.forEach((value) => {
    variance += (value - mean) ** 2;
  });
  return {
    mean: round(mean, 2),
    contrast: round(Math.sqrt(variance / pixels.length), 2),
    pixels,
  };
}

function frameDifference(left, right) {
  if (!left?.length || left.length !== right?.length) return 1;
  let total = 0;
  for (let index = 0; index < left.length; index += 1) total += Math.abs(left[index] - right[index]);
  return round(total / left.length / 255, 4);
}

function normalizeResult(raw) {
  const source = objectFrom(raw) || {};
  const complianceStatus = normalizeComplianceStatus(source.compliance_status || source.complianceStatus);
  const findings = arrayValue(source.findings).slice(0, MAX_FINDINGS).map(normalizeFinding);
  const recommendations = deduplicateRecommendations(
    findings,
    arrayValue(source.recommendations).slice(0, MAX_RECOMMENDATIONS).map(normalizeRecommendation),
  );
  return {
    overallScore: score(source.overall_score ?? source.overallScore),
    scores: normalizeScores(source.scores),
    complianceStatus,
    blockersCount: nonNegativeInteger(source.blockers_count ?? source.blockersCount),
    warningsCount: nonNegativeInteger(source.warnings_count ?? source.warningsCount),
    strengths: stringList(source.strengths, 20, 500),
    findings,
    recommendations,
    comparison: normalizeComparison(source.comparison),
    speechAnalysis: normalizeSpeechAnalysis(source.speech_analysis || source.speechAnalysis),
    rulesetVersion: text(source.ruleset_version || source.rulesetVersion, 180),
  };
}

function deduplicateRecommendations(findings, recommendations) {
  const findingTitles = new Set(findings.map((item) => normalizedTitle(item.title)).filter(Boolean));
  const seen = new Set();
  return recommendations.filter((item) => {
    const key = normalizedTitle(item.title);
    if (!key || findingTitles.has(key) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizedTitle(value) {
  return text(value, 500).toLocaleLowerCase("ru-RU").replace(/\s+/gu, " ").trim();
}

function normalizeInput(raw) {
  const source = objectFrom(raw) || {};
  return {
    mediaId: text(source.media_id || source.mediaId, 180),
    platform: text(source.platform, 40).toLowerCase(),
    contentKind: text(source.content_kind || source.contentKind, 40).toLowerCase(),
    productCategory: text(source.product_category || source.productCategory, 60).toLowerCase(),
    captionText: text(source.caption_text || source.captionText, 6000),
    scriptText: text(source.script_text || source.scriptText, 6000),
    advertiserName: text(source.advertiser_name || source.advertiserName, 240),
    erid: text(source.erid, 180),
    technicalMetrics: objectFrom(source.technical_metrics) || objectFrom(source.technicalMetrics) || {},
    generationJobId: text(source.generation_job_id || source.generationJobId, 180),
    productCategoryVerified: Boolean(source.product_category_verified ?? source.productCategoryVerified),
    productCategorySource: text(source.product_category_source || source.productCategorySource, 80).toLowerCase(),
    aiGenerated: Boolean(source.ai_generated ?? source.aiGenerated),
    externalAiProcessingConfirmed: Boolean(source.external_ai_processing_confirmed ?? source.externalAiProcessingConfirmed),
    captionsConfirmed: Boolean(source.captions_confirmed ?? source.captionsConfirmed),
    adLabelConfirmed: Boolean(source.ad_label_confirmed ?? source.adLabelConfirmed),
    ordConfirmed: Boolean(source.ord_confirmed ?? source.ordConfirmed),
    rightsConfirmed: Boolean(source.rights_confirmed ?? source.rightsConfirmed),
    claimsVerified: Boolean(source.claims_verified ?? source.claimsVerified),
    generationClaimEvidence: normalizeGenerationClaimEvidence(
      source.generation_claim_evidence || source.generationClaimEvidence,
    ),
    aiDisclosureConfirmed: Boolean(source.ai_disclosure_confirmed ?? source.aiDisclosureConfirmed),
    mandatoryWarningConfirmed: Boolean(source.mandatory_warning_confirmed ?? source.mandatoryWarningConfirmed),
    audienceOver10000: Boolean(source.audience_over_10000 ?? source.audienceOver10000),
    rknRegistered: Boolean(source.rkn_registered ?? source.rknRegistered),
  };
}

function normalizeGenerationClaimEvidence(raw) {
  const source = objectFrom(raw);
  if (!source) return null;
  const status = text(source.status, 40).toLowerCase();
  const evidenceSource = text(source.source, 80).toLowerCase();
  if (
    !["bound", "unavailable", "invalid"].includes(status)
    || ![
      "approved_research",
      "baseline",
      "performance_learning",
      "untracked",
    ].includes(evidenceSource)
  ) return null;
  return {
    status,
    source: evidenceSource,
    generationJobId: text(source.generation_job_id || source.generationJobId, 180),
    creativeBriefDraftId: text(source.creative_brief_draft_id || source.creativeBriefDraftId, 180),
    safeClaimCount: nonNegativeInteger(source.safe_claim_count ?? source.safeClaimCount),
    forbiddenClaimCount: nonNegativeInteger(source.forbidden_claim_count ?? source.forbiddenClaimCount),
    evidenceHash: text(source.evidence_hash || source.evidenceHash, 64),
  };
}

function normalizeFinding(raw) {
  const source = objectFrom(raw) || {};
  const severity = ["blocker", "high", "medium", "low", "info"].includes(String(source.severity))
    ? String(source.severity)
    : "medium";
  return {
    code: text(source.code, 120),
    category: text(source.category, 80),
    severity,
    title: text(source.title || "Требует проверки", 300),
    detail: text(source.detail, 1600),
    action: text(source.action, 1200),
    evidence: objectFrom(source.evidence) || null,
    confidence: finiteOrNull(source.confidence),
    humanReviewRequired: Boolean(source.human_review_required ?? source.humanReviewRequired),
    sourceKey: text(source.source_key || source.sourceKey, 120),
    stage: text(source.stage, 120),
    timecode: text(source.timecode, 40),
  };
}

function normalizeRecommendation(raw) {
  const source = objectFrom(raw) || {};
  const priority = ["high", "medium", "low"].includes(String(source.priority))
    ? String(source.priority)
    : "medium";
  return {
    code: text(source.code, 120),
    category: text(source.category, 80),
    priority,
    title: text(source.title || "Улучшить материал", 300),
    detail: text(source.detail, 1600),
    action: text(source.action, 1200),
    measurement: text(source.measurement, 800),
    confidence: finiteOrNull(source.confidence),
  };
}

function normalizeComparison(raw) {
  const source = objectFrom(raw);
  if (!source) return null;
  return {
    previousScore: finiteOrNull(source.previous_score ?? source.previousScore),
    delta: finiteOrNull(source.delta),
    summary: text(source.summary, 1200),
  };
}

function normalizeSpeechAnalysis(raw) {
  const source = objectFrom(raw);
  if (!source) return null;
  const allowedStatuses = new Set([
    "not_applicable",
    "not_requested",
    "skipped_no_script",
    "skipped_audio_unavailable",
    "skipped_file_too_large",
    "unavailable",
    "completed",
  ]);
  const status = text(source.status, 80).toLowerCase();
  return {
    status: allowedStatuses.has(status) ? status : "unavailable",
    consentConfirmed: Boolean(source.consent_confirmed ?? source.consentConfirmed),
    model: text(source.model, 120),
    transcriptSha256: text(source.transcript_sha256 || source.transcriptSha256, 64),
    transcriptExcerpt: text(source.transcript_excerpt || source.transcriptExcerpt, 1200),
    expectedWordCount: nonNegativeInteger(source.expected_word_count ?? source.expectedWordCount),
    transcriptWordCount: nonNegativeInteger(source.transcript_word_count ?? source.transcriptWordCount),
    matchedWordCount: finiteOrNull(source.matched_word_count ?? source.matchedWordCount),
    coverageRatio: finiteOrNull(source.coverage_ratio ?? source.coverageRatio),
    precisionRatio: finiteOrNull(source.precision_ratio ?? source.precisionRatio),
    similarityRatio: finiteOrNull(source.similarity_ratio ?? source.similarityRatio),
    wordErrorRate: finiteOrNull(source.word_error_rate ?? source.wordErrorRate),
    transcriptionConfidence: finiteOrNull(source.transcription_confidence ?? source.transcriptionConfidence),
  };
}

function normalizeDecision(raw) {
  return {
    decision: text(raw.decision || raw.status, 40),
    reason: text(raw.comment || raw.reason || raw.notes, 2000),
    decidedBy: text(raw.decided_by_name || raw.reviewer_name || raw.decided_by, 240),
    decidedAt: raw.decided_at || raw.created_at || null,
  };
}

function normalizeSoundAssessment(raw) {
  const source = objectFrom(raw) || {};
  const status = text(source.status, 40).toLowerCase();
  if (!["clear", "issues_found", "silent_expected"].includes(status)) {
    return null;
  }
  const issueCodes = stringList(
    source.issue_codes || source.issueCodes,
    GENERATED_VIDEO_SOUND_ISSUE_CODES.length,
    80,
  ).map((code) => code.toLowerCase())
    .filter((code) => GENERATED_VIDEO_SOUND_ISSUE_CODE_SET.has(code));
  return {
    id: text(source.id, 180),
    status,
    issueCodes: [...new Set(issueCodes)],
    spokenScriptHeardExactlyConfirmed: Boolean(
      source.spoken_script_heard_exactly_confirmed
      ?? source.spokenScriptHeardExactlyConfirmed,
    ),
    dictionClearConfirmed: Boolean(
      source.diction_clear_confirmed ?? source.dictionClearConfirmed,
    ),
    voiceStyleConfirmed: Boolean(
      source.voice_style_confirmed ?? source.voiceStyleConfirmed,
    ),
    audioSyncConfirmed: Boolean(
      source.audio_sync_confirmed ?? source.audioSyncConfirmed,
    ),
    silenceExpectedConfirmed: Boolean(
      source.silence_expected_confirmed ?? source.silenceExpectedConfirmed,
    ),
    note: text(source.note, 1000),
    assessedBy: text(
      source.assessed_by_name || source.assessedByName
      || source.assessed_by || source.assessedBy,
      240,
    ),
    assessedAt: source.assessed_at || source.assessedAt
      || source.created_at || source.createdAt || null,
  };
}

function normalizeMedia(raw) {
  const metadata = objectFrom(raw.metadata) || {};
  const mimeType = text(
    raw.mime_type || raw.mimeType || raw.content_type || raw.contentType,
    120,
  ).toLowerCase();
  const kind = text(raw.kind || metadata.kind, 80).toLowerCase();
  const isVideo = mimeType === "video/mp4" || kind === "source_video" || kind === "generated_video";
  const isImage = mimeType.startsWith("image/") || ["product_photo", "packshot", "creator_reference"].includes(kind);
  const url = safeMediaUrl(
    raw.signed_url || raw.signedUrl
    || raw.access_url || raw.accessUrl
    || raw.preview_url || raw.previewUrl
    || raw.url,
  );
  const model = text(metadata.model || raw.generationModel, 120).toLowerCase();
  const audioExpected = typeof raw.audioExpected === "boolean"
    ? raw.audioExpected
    : typeof metadata.audio === "boolean"
      ? metadata.audio
    : model === "gen4_turbo"
      ? false
      : null;
  return {
    id: text(raw.public_id || raw.id || raw.media_id, 180),
    productId: text(raw.product_id || raw.productId || metadata.product_id, 180),
    productCategory: text(
      raw.product_category
      || metadata.content_review_category
      || metadata.product_category,
      60,
    ).toLowerCase(),
    platform: text(
      raw.platform
      || metadata.platform
      || metadata.generation_platform,
      40,
    ).toLowerCase(),
    generationJobId: text(
      raw.generation_job_id || metadata.generation_job_id,
      180,
    ).toLowerCase(),
    name: text(raw.original_filename || raw.originalFilename || raw.name || metadata.original_filename || metadata.filename || metadata.name || "Материал", 300),
    mimeType,
    kind,
    isVideo,
    isImage,
    supported: isVideo || isImage,
    url,
    objectName: text(
      raw.object_name || raw.objectName || raw.object_key || raw.objectKey,
      600,
    ),
    status: text(raw.status, 40).toLowerCase(),
    lifecycleStage: text(raw.lifecycle_stage || raw.lifecycleStage, 40).toLowerCase(),
    artifactClass: text(raw.artifact_class || raw.artifactClass, 40).toLowerCase(),
    ownerId: text(raw.owner_id || raw.ownerId, 180),
    ownerName: text(raw.owner_name || raw.ownerName, 200),
    createdAt: text(raw.created_at || raw.createdAt, 60),
    sha256: text(raw.sha256, 180),
    sizeBytes: nonNegativeInteger(raw.size_bytes ?? raw.sizeBytes),
    generationModel: model,
    audioExpected,
    spokenScript: text(
      raw.spoken_script || raw.spokenScript
      || metadata.spoken_script || metadata.review_script_text,
      6000,
    ),
  };
}

function normalizeScores(raw) {
  const source = objectFrom(raw) || {};
  const entries = Object.entries(source)
    .filter(([key, value]) => key && Number.isFinite(Number(value)))
    .slice(0, 12);
  return Object.fromEntries(entries.map(([key, value]) => [text(key, 80), score(value)]));
}

function normalizeComplianceStatus(value) {
  const normalized = String(value || "human_review").toLowerCase();
  if (normalized === "review") return "human_review";
  if (normalized === "warn") return "pass_with_warnings";
  return COMPLIANCE_META[normalized] ? normalized : "human_review";
}

function qualityLabel(value) {
  if (value >= 85) return "Сильная основа";
  if (value >= 70) return "Хорошо, но есть точки роста";
  if (value >= 50) return "Нужна заметная доработка";
  return "Слабая готовность к публикации";
}

function scoreLabel(value) {
  const labels = {
    technical: "Техника",
    technical_quality: "Техника",
    visual: "Визуал",
    visual_quality: "Визуал",
    hook: "Первые секунды",
    clarity: "Понятность",
    product_fidelity: "Точность товара",
    claims: "Доказательность",
    platform_readiness: "Готовность площадки",
    trust: "Доверие",
    accessibility: "Доступность",
  };
  return labels[String(value || "").toLowerCase()] || String(value || "Оценка").replaceAll("_", " ");
}

function categoryLabel(value) {
  const labels = {
    quality: "Качество",
    technical: "Техника",
    hook: "Первые секунды",
    product: "Товар",
    claims: "Обещания",
    legal: "Право",
    advertising: "Реклама",
    platform: "Площадка",
    rights: "Права",
    people: "Люди",
    accessibility: "Доступность",
  };
  return labels[String(value || "").toLowerCase()] || String(value || "Проверка").replaceAll("_", " ");
}

function severityLabel(value) {
  return {
    blocker: "Блокер",
    high: "Высокий риск",
    medium: "Проверить",
    low: "Низкий риск",
    info: "Информация",
  }[value] || "Проверить";
}

function priorityLabel(value) {
  return { high: "Сначала", medium: "Следом", low: "При возможности" }[value] || "Следом";
}

function decisionLabel(value) {
  return {
    approved: "Одобрено человеком",
    needs_changes: "Возвращено на доработку",
    rejected: "Отклонено",
  }[String(value || "")] || "Решение сохранено";
}

function messageMarkup(message, tone) {
  return `<div class="content-review-message is-${escapeHtml(tone)}" role="${tone === "danger" ? "alert" : "status"}"><span aria-hidden="true">${tone === "danger" ? "!" : tone === "success" ? "✓" : "i"}</span><p>${escapeHtml(message)}</p></div>`;
}

function safeMediaUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.startsWith("blob:")) return raw;
  try {
    const url = new URL(raw, window.location.href);
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function orientation(width, height) {
  if (height > width) return "portrait";
  if (width > height) return "landscape";
  return "square";
}

function roundedRatio(width, height) {
  return height ? round(width / height, 4) : 0;
}

function score(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
}

function positiveInteger(value, fallback) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

function nonNegativeInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? Math.floor(number) : 0;
}

function finiteOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? round(number, 2) : null;
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(Number(value) * factor) / factor;
}

function dateValue(value) {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDate(value) {
  if (!value) return "Дата не указана";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Дата не указана";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes <= 0) return "размер не указан";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 ** 2).toFixed(1)} МБ`;
}

function stringValue(values, key) {
  return String(values.get(key) || "").trim();
}

function stringList(value, limit, itemLimit) {
  return arrayValue(value)
    .map((item) => text(item, itemLimit))
    .filter(Boolean)
    .slice(0, limit);
}

function text(value, limit = 1000) {
  return String(value ?? "").trim().slice(0, limit);
}

function objectFrom(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function arrayFrom(source, ...keys) {
  for (const key of keys) {
    if (Array.isArray(source?.[key])) return source[key];
  }
  return [];
}

function unwrap(raw) {
  const source = objectFrom(raw) || {};
  return objectFrom(source.data) || source;
}

function userError(message) {
  const error = new Error(message);
  error.name = "ContentReviewEvidenceError";
  error.isUserSafe = true;
  return error;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}
