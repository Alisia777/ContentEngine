const ACTIVE_STATUSES = new Set(["queued", "starting", "processing", "running"]);
const READY_STATUSES = new Set(["completed", "succeeded", "ready"]);
const FAILED_STATUSES = new Set(["failed", "cancelled"]);
const MAX_FINDINGS = 80;
const MAX_RECOMMENDATIONS = 40;
const MAX_FRAME_CHARACTERS = 330_000;
const MAX_TOTAL_FRAME_CHARACTERS = 1_650_000;
const FRAME_SAMPLE_SIZE = 48;

const PLATFORM_LABELS = Object.freeze({
  instagram: "Instagram",
  youtube: "YouTube",
  vk: "VK",
  tiktok: "TikTok",
  telegram: "Telegram",
  wildberries: "Wildberries",
  other: "Другая площадка",
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
  none: "Внутренняя проверка качества ALTEA",
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
    rulesetVersion: text(
      source.ruleset_version || envelope.ruleset_version || result.rulesetVersion || previous?.rulesetVersion,
      180,
    ),
    failureMessage: text(
      source.failure_message || source.error_message || envelope.failure_message || previous?.failureMessage,
      1000,
    ),
    version: positiveInteger(source.version || source.lock_version || previous?.version, 1),
    createdAt: source.created_at || previous?.createdAt || null,
    updatedAt: source.updated_at || previous?.updatedAt || null,
    completedAt: source.completed_at || source.finished_at || previous?.completedAt || null,
  };
}

export function contentReviewHasBlockers(run) {
  if (!run) return false;
  if (run.result.complianceStatus === "block") return true;
  if (run.result.blockersCount > 0) return true;
  return run.result.findings.some((item) => item.severity === "blocker");
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
} = {}) {
  const normalized = catalog || { media: [], runs: [] };
  const selected = currentRun
    ? normalizeContentReviewRun(currentRun)
    : normalized.runs.find((item) => contentReviewStatusKind(item.status) === "active")
      || normalized.runs[0]
      || null;
  const busy = ["preparing", "starting", "processing", "refreshing", "deciding"].includes(phase)
    || contentReviewStatusKind(selected?.status) === "active";
  return `
    <section class="content-review-hero" aria-labelledby="content-review-hero-title">
      <div>
        <span class="content-review-hero__mark" aria-hidden="true">✓</span>
        <p class="eyebrow">До публикации</p>
        <h2 id="content-review-hero-title">Один экран для качества и рисков</h2>
        <p>Портал проверит технические признаки, понятность ролика, товарные обещания и обязательные реквизиты. Это фильтр рисков, а не автоматическая юридическая экспертиза.</p>
      </div>
      <ol class="content-review-hero__steps" aria-label="Как проходит проверка">
        <li><span>1</span><div><strong>Выберите файл</strong><small>Точное фото или MP4 из материалов</small></div></li>
        <li><span>2</span><div><strong>Заполните контекст</strong><small>Площадка, статус публикации и подтверждения</small></div></li>
        <li><span>3</span><div><strong>Примите решение</strong><small>Исправить, отклонить или одобрить человеку</small></div></li>
      </ol>
    </section>
    ${notice ? messageMarkup(notice, "success") : ""}
    ${error ? messageMarkup(error, "danger") : ""}
    <div class="content-review-layout">
      ${reviewFormMarkup(normalized.media, busy)}
      <section class="content-review-output" aria-live="polite">
        ${reviewCurrentMarkup(selected, { phase, canDecide })}
      </section>
    </div>
    ${reviewHistoryMarkup(normalized.runs, selected?.id)}
  `;
}

export function readContentReviewForm(form) {
  const values = new FormData(form);
  return {
    media_id: stringValue(values, "media_id"),
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
  };
}

export function syncContentReviewFormVisibility(form) {
  if (!form) return;
  const advertising = String(form.elements.content_kind?.value || "unknown") === "advertising";
  const baa = String(form.elements.product_category?.value || "other") === "baa";
  const peopleMayBePresent = String(form.elements.people_present?.value || "unknown") !== "no";
  const aiGenerated = form.elements.ai_generated?.checked === true;
  const largeAudience = form.elements.audience_over_10000?.checked === true;
  toggleConditional(form, "[data-review-advertising]", advertising);
  toggleConditional(form, "[data-review-baa]", baa);
  toggleConditional(form, "[data-review-person-consent]", peopleMayBePresent);
  toggleConditional(form, "[data-review-ai-disclosure]", aiGenerated);
  toggleConditional(form, "[data-review-rkn]", largeAudience);
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

function reviewFormMarkup(media, busy) {
  const supported = media.filter((item) => item.supported);
  return `
    <form id="content-review-form" class="card content-review-form" novalidate>
      <div class="content-review-form__header">
        <span class="content-review-step">01</span>
        <div><p class="eyebrow">Новая проверка</p><h2>Что собираемся публиковать?</h2><p>Заполните только факты. Если рекламный статус неизвестен, так и укажите — портал остановит публикацию до решения.</p></div>
      </div>
      <fieldset class="content-review-fieldset">
        <legend>1. Файл из материалов *</legend>
        ${supported.length
          ? `<div class="content-review-media-grid">${supported.slice(0, 30).map(reviewMediaOptionMarkup).join("")}</div>`
          : `<div class="content-review-empty"><span aria-hidden="true">▧</span><div><strong>Нет подходящих файлов</strong><p>Загрузите JPG, PNG, WEBP или MP4 в разделе «Материалы», затем обновите эту страницу.</p><a href="#/workspace/media">Открыть материалы →</a></div></div>`}
      </fieldset>
      <fieldset class="content-review-fieldset">
        <legend>2. Контекст публикации *</legend>
        <div class="content-review-form-grid">
          <label class="field"><span>Площадка</span><select name="platform" required>${Object.entries(PLATFORM_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select></label>
          <label class="field"><span>Статус материала</span><select name="content_kind" required>${Object.entries(CONTENT_KIND_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select><small class="field-hint">«Неизвестно» — безопасный выбор, если руководитель ещё не решил.</small></label>
          <label class="field field-wide"><span>Категория товара</span><select name="product_category" required>${Object.entries(PRODUCT_CATEGORY_LABELS).map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`).join("")}</select></label>
          <label class="field field-wide"><span>Подпись к публикации</span><textarea name="caption_text" maxlength="6000" rows="4" placeholder="Текст поста, CTA, хэштеги и обязательные пометки"></textarea></label>
          <label class="field field-wide"><span>Реплика / сценарий ролика</span><textarea name="script_text" maxlength="6000" rows="5" placeholder="Что произносит блогер или что написано крупным текстом в кадре"></textarea><small class="field-hint">Для видео с речью вставьте точную реплику: браузер не отправляет звук и не заменяет прослушивание человеком.</small></label>
        </div>
      </fieldset>
      <fieldset class="content-review-fieldset">
        <legend>3. Права, люди и доказательства *</legend>
        <div class="content-review-confirmations">
          ${checkMarkup("rights_confirmed", "У команды есть право использовать файл, музыку, логотипы и графику", "Без подтверждения прав проверка не должна вести к публикации.")}
          ${checkMarkup("claims_verified", "Свойства, цены, скидки и результаты подтверждены документом или карточкой товара", "ИИ не превращает предположение в доказанный факт.")}
          ${checkMarkup("captions_confirmed", "Титры и крупный текст проверены вручную", "Нет обрезанных слов, ошибок, чужого бренда и нечитаемых обещаний.")}
          <label class="field content-review-select-row"><span>Есть узнаваемые люди?</span><select name="people_present" required><option value="unknown">Не проверено</option><option value="no">Нет</option><option value="yes">Да</option></select></label>
          <div data-review-person-consent hidden>
            ${checkMarkup("person_consent_confirmed", "Согласие узнаваемых людей на съёмку и публикацию подтверждено", "Особенно важно для сотрудников, покупателей и несовершеннолетних.")}
            ${checkMarkup("external_ai_processing_confirmed", "Подтверждено законное основание и необходимое информирование для передачи контрольных кадров внешнему AI-провайдеру", "Если в кадре есть узнаваемые люди, без этого подтверждения контрольные кадры нельзя отправлять на внешний анализ.")}
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
      <div class="content-review-submit">
        <div><strong>Что будет отправлено</strong><p>Текст формы, технические числа и до пяти сжатых кадров. Исходный MP4 и его звук в ИИ-сервис не отправляются.</p></div>
        <button class="btn" type="submit" ${supported.length && !busy ? "" : "disabled"}>${busy ? "Проверка уже выполняется…" : "Проверить качество и риски"}</button>
      </div>
    </form>
  `;
}

function reviewCurrentMarkup(run, { phase, canDecide }) {
  if (phase === "preparing") {
    return progressMarkup("Готовим безопасную выборку кадров", "Считываем формат, длительность и 4–5 точек видео. Сам MP4 никуда не отправляется.", 1);
  }
  if (phase === "starting") {
    return progressMarkup("Фиксируем вводные", "Создаём неизменяемую запись проверки и передаём только сжатые кадры.", 2);
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
    return progressMarkup("Проверяем содержание", "Отдельно оцениваем качество, обещания, права, рекламные реквизиты и правила площадки.", 3, run);
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
  return reviewResultMarkup(run, canDecide);
}

function reviewResultMarkup(run, canDecide) {
  const result = run.result;
  const compliance = COMPLIANCE_META[result.complianceStatus] || COMPLIANCE_META.human_review;
  const blockers = contentReviewHasBlockers(run);
  return `
    <article class="content-review-result" data-review-result-id="${escapeHtml(run.id)}">
      <header class="card content-review-result__header">
        <div><p class="eyebrow">Проверка завершена</p><h2>${escapeHtml(run.media?.name || "Материал")}</h2><p>${escapeHtml(PLATFORM_LABELS[run.input.platform] || run.input.platform || "Площадка не указана")} · ${escapeHtml(CONTENT_KIND_LABELS[run.input.contentKind] || run.input.contentKind || "Статус не указан")}</p></div>
        <span class="content-review-result__date">${formatDate(run.completedAt || run.updatedAt || run.createdAt)}</span>
      </header>
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
      ${result.strengths.length ? `<section class="card content-review-strengths"><p class="eyebrow">Что уже работает</p><ul>${result.strengths.map((item) => `<li><span aria-hidden="true">✓</span>${escapeHtml(item)}</li>`).join("")}</ul></section>` : ""}
      ${findingsMarkup(result.findings)}
      ${recommendationsMarkup(result.recommendations)}
      ${reviewDecisionMarkup(run, { canDecide, blockers })}
      ${rulesetMarkup(run)}
    </article>
  `;
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

function reviewDecisionMarkup(run, { canDecide, blockers }) {
  if (run.decision) {
    return `
      <section class="card content-review-decision is-recorded">
        <span aria-hidden="true">⌁</span>
        <div><p class="eyebrow">Неизменяемое решение человека</p><h3>${escapeHtml(decisionLabel(run.decision.decision))}</h3><p>${escapeHtml(run.decision.reason || "Причина не указана.")}</p><small>${escapeHtml(run.decision.decidedBy || "Ответственный участник")} · ${formatDate(run.decision.decidedAt)}</small></div>
      </section>`;
  }
  if (!canDecide) {
    return messageMarkup("Результат готов. Зафиксировать финальное решение может руководитель, продюсер или проверяющий.", "info");
  }
  const riskItems = [...new Map(
    run.result.findings
      .filter((item) => item.code && (item.humanReviewRequired || ["high", "medium"].includes(item.severity)))
      .map((item) => [item.code, item]),
  ).values()];
  const requiredRiskCodes = new Set(contentReviewRequiredRiskCodes(run));
  const fallbackRisk = requiredRiskCodes.has("general_human_review") && !riskItems.length
    ? [{ code: "general_human_review", title: "Результат требует отдельного решения человека" }]
    : [];
  const recommendationItems = run.result.recommendations.filter((item) => item.code);
  const mediaAvailable = Boolean(run.media?.url)
    && run.mediaIsStale !== true
    && (!run.media?.status || run.media.status === "ready");
  const unavailableMessage = run.mediaIsStale
    ? "Файл изменился после анализа. Для этой версии нельзя фиксировать решение — запустите новую проверку."
    : "Точная защищённая версия файла сейчас недоступна. Обновите статус, прежде чем принимать решение.";
  const exactPreview = mediaAvailable
    ? run.media.isVideo
      ? `<video class="content-review-decision-preview__media" data-content-review-exact-media data-media-kind="video" src="${escapeHtml(run.media.url)}" controls preload="metadata" playsinline></video>`
      : `<img class="content-review-decision-preview__media" data-content-review-exact-media data-media-kind="image" src="${escapeHtml(run.media.url)}" alt="${escapeHtml(run.media.name || "Проверяемый материал")}" />`
    : `<div class="content-review-decision-preview__missing">${escapeHtml(unavailableMessage)}</div>`;
  return `
    <form class="card content-review-decision-form" data-review-id="${escapeHtml(run.id)}" data-exact-media-state="${mediaAvailable ? "loading" : "unavailable"}" novalidate>
      <div><p class="eyebrow">Финальное решение человека</p><h3>${blockers ? "Одобрение недоступно из-за блокеров" : "Зафиксируйте результат проверки"}</h3><p>После сохранения решение нельзя переписать. Для исправленной версии запустите новую проверку.</p></div>
      <section class="content-review-decision-preview">
        <div><strong>Просмотрите именно этот файл целиком</strong><small>Кадры ИИ — вспомогательная выборка. Браузер фиксирует загрузку файла и окончание воспроизведения, но подтверждение звука, титров и смысла всё равно даёт человек.</small></div>
        ${exactPreview}
        <p class="content-review-decision-preview__state ${mediaAvailable ? "" : "is-error"}" data-content-review-media-state role="status">${mediaAvailable ? (run.media.isVideo ? "Загружаем метаданные MP4. Затем воспроизведите файл до события окончания." : "Проверяем доступность изображения.") : escapeHtml(unavailableMessage)}</p>
      </section>
      <label class="content-review-check content-review-watch-confirmation"><input type="checkbox" name="media_watched_confirmed" value="yes" required disabled /><span><strong>Я подтверждаю, что лично просмотрел(а) именно этот защищённый файл до конца и проверил(а) звук и субтитры</strong><small>Это подтверждение пользователя, а не автоматическое доказательство качества. Для MP4 поле откроется только после загрузки метаданных и события окончания без смены файла.</small></span></label>
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
        ${blockers ? "" : `<button class="btn" type="submit" name="decision" value="approved" data-review-decision-submit disabled>Одобрить</button>`}
        <button class="btn btn-secondary" type="submit" name="decision" value="needs_changes" data-review-decision-submit disabled>На доработку</button>
        <button class="btn btn-ghost" type="submit" name="decision" value="rejected" data-review-decision-submit disabled>Отклонить</button>
      </div>
    </form>`;
}

function rulesetMarkup(run) {
  const sourceKeys = [...new Set(run.result.findings.map((item) => item.sourceKey).filter(Boolean))];
  return `
    <details class="card content-review-ruleset">
      <summary><span><strong>Версия правил и пределы проверки</strong><small>${escapeHtml(run.rulesetVersion || "Версия не указана сервером")}</small></span><i aria-hidden="true">+</i></summary>
      <div>
        <p>Проверка ищет признаки риска по кадрам и введённому тексту. Она не слышит звук ролика, не подтверждает факты вместо документов и не заменяет юриста или решение площадки.</p>
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
  return `
    <button class="card content-review-history-card ${active ? "is-active" : ""}" type="button" data-action="open-content-review" data-review-id="${escapeHtml(run.id)}" aria-pressed="${active ? "true" : "false"}">
      <span class="content-review-history-card__score">${kind === "ready" ? result.overallScore : kind === "active" ? "…" : "!"}</span>
      <span><small>${formatDate(run.createdAt)} · ${escapeHtml(PLATFORM_LABELS[run.input.platform] || run.input.platform || "—")}</small><strong>${escapeHtml(run.media?.name || "Материал")}</strong><em>${kind === "ready" ? escapeHtml(compliance.short) : kind === "active" ? "Проверяется" : "Ошибка"}</em></span>
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

function reviewMediaOptionMarkup(item, index) {
  const preview = item.url
    ? item.isVideo
      ? `<video src="${escapeHtml(item.url)}" preload="metadata" muted playsinline></video><i aria-hidden="true">▶</i>`
      : `<img src="${escapeHtml(item.url)}" alt="" loading="lazy" />`
    : `<span aria-hidden="true">${item.isVideo ? "▶" : "▧"}</span>`;
  return `
    <label class="content-review-media-option">
      <input type="radio" name="media_id" value="${escapeHtml(item.id)}" ${index === 0 ? "required" : ""} />
      <span class="content-review-media-option__preview">${preview}</span>
      <span><strong>${escapeHtml(item.name)}</strong><small>${item.isVideo ? "MP4-видео" : "Изображение"} · ${formatBytes(item.sizeBytes)}</small></span>
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
  video.src = media.url;
  try {
    await waitForEvent(video, "loadedmetadata", 15_000, "Не удалось прочитать параметры MP4.");
    const width = Number(video.videoWidth);
    const height = Number(video.videoHeight);
    const duration = Number(video.duration);
    if (!width || !height || !Number.isFinite(duration) || duration <= 0 || duration > 3_600) {
      throw userError("MP4 имеет неподдерживаемые параметры. Проверьте, что файл открывается и не длиннее одного часа.");
    }
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
    const totalCharacters = frames.reduce((sum, frame) => sum + frame.length, 0);
    if (frames.length < 4 || frames.length > 5 || totalCharacters > MAX_TOTAL_FRAME_CHARACTERS) {
      throw userError("Не удалось подготовить безопасную выборку кадров. Обновите страницу и повторите проверку.");
    }
    const differences = [];
    for (let index = 1; index < samples.length; index += 1) {
      differences.push(frameDifference(samples[index - 1].pixels, samples[index].pixels));
    }
    const frozenFrameRatio = differences.length
      ? round(differences.filter((value) => value < 0.015).length / differences.length, 3)
      : 0;
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
        sampled_at_seconds: targets.map((value) => round(value, 3)),
        frame_luminance: samples.map((sample) => sample.mean),
        frame_contrast: samples.map((sample) => sample.contrast),
        adjacent_frame_difference: differences,
        black_frame_ratio: round(samples.filter((sample) => sample.mean < 16).length / samples.length, 3),
        frozen_frame_ratio: frozenFrameRatio,
        frozen_frame_suspected: frozenFrameRatio >= 0.8,
        vertical_9_16_delta: round(Math.abs(width / height - 9 / 16), 4),
        sampling_strategy: "early_0_2_1_2_plus_late_distribution",
        raw_video_sent: false,
        audio_analyzed: false,
      },
    };
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
}

function sampleTimes(duration) {
  const safeEnd = Math.max(0, duration - Math.min(0.05, duration / 20));
  if (safeEnd < 2.05) {
    return [0.05, 0.25, 0.5, 0.75, 0.95]
      .map((fraction) => Math.min(safeEnd, Math.max(0, duration * fraction)));
  }
  return [
    0.2,
    1,
    2,
    Math.max(2.2, duration * 0.62),
    Math.max(2.4, duration * 0.9),
  ].map((seconds) => Math.min(safeEnd, Math.max(0, seconds)));
}

async function seekVideo(video, seconds) {
  if (Math.abs(Number(video.currentTime || 0) - seconds) < 0.01 && video.readyState >= 2) return;
  const wait = waitForEvent(video, "seeked", 10_000, "Не удалось считать один из кадров MP4.");
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
  let data;
  try {
    context.drawImage(sourceCanvas, 0, 0, FRAME_SAMPLE_SIZE, FRAME_SAMPLE_SIZE);
    data = context.getImageData(0, 0, FRAME_SAMPLE_SIZE, FRAME_SAMPLE_SIZE).data;
  } catch {
    throw userError("Браузер заблокировал техническое чтение кадра. Обновите защищённую ссылку.");
  }
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
  return {
    overallScore: score(source.overall_score ?? source.overallScore),
    scores: normalizeScores(source.scores),
    complianceStatus,
    blockersCount: nonNegativeInteger(source.blockers_count ?? source.blockersCount),
    warningsCount: nonNegativeInteger(source.warnings_count ?? source.warningsCount),
    strengths: stringList(source.strengths, 20, 500),
    findings: arrayValue(source.findings).slice(0, MAX_FINDINGS).map(normalizeFinding),
    recommendations: arrayValue(source.recommendations).slice(0, MAX_RECOMMENDATIONS).map(normalizeRecommendation),
    comparison: normalizeComparison(source.comparison),
    rulesetVersion: text(source.ruleset_version || source.rulesetVersion, 180),
  };
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

function normalizeDecision(raw) {
  return {
    decision: text(raw.decision || raw.status, 40),
    reason: text(raw.comment || raw.reason || raw.notes, 2000),
    decidedBy: text(raw.decided_by_name || raw.reviewer_name || raw.decided_by, 240),
    decidedAt: raw.decided_at || raw.created_at || null,
  };
}

function normalizeMedia(raw) {
  const metadata = objectFrom(raw.metadata) || {};
  const mimeType = text(raw.mime_type || raw.content_type, 120).toLowerCase();
  const kind = text(raw.kind || metadata.kind, 80).toLowerCase();
  const isVideo = mimeType === "video/mp4" || kind === "source_video" || kind === "generated_video";
  const isImage = mimeType.startsWith("image/") || ["product_photo", "packshot", "creator_reference"].includes(kind);
  const url = safeMediaUrl(raw.signed_url || raw.access_url || raw.preview_url);
  return {
    id: text(raw.public_id || raw.id || raw.media_id, 180),
    productId: text(raw.product_id || metadata.product_id, 180),
    name: text(raw.original_filename || raw.name || metadata.original_filename || metadata.filename || metadata.name || "Материал", 300),
    mimeType,
    kind,
    isVideo,
    isImage,
    supported: isVideo || isImage,
    url,
    objectName: text(raw.object_name || raw.object_key, 600),
    status: text(raw.status, 40).toLowerCase(),
    sha256: text(raw.sha256, 180),
    sizeBytes: nonNegativeInteger(raw.size_bytes),
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
