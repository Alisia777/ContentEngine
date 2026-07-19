const PRACTICAL_STATUSES = new Set([
  "not_started",
  "draft",
  "submitted",
  "changes_requested",
  "approved",
  "grandfathered",
]);
const PRACTICAL_PLATFORMS = new Set(["instagram", "youtube", "vk"]);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanText(value, limit = 1000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function cleanUuid(value) {
  const normalized = cleanText(value, 80);
  return /^[0-9a-f]{8}-[0-9a-f-]{27,36}$/iu.test(normalized) ? normalized : "";
}

function safeHttpsUrl(value) {
  const raw = cleanText(value, 2048);
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) return "";
    return parsed.href;
  } catch {
    return "";
  }
}

function sourceObject(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  return raw.practical_project
    || raw.practicalProject
    || raw.project
    || raw.current
    || raw;
}

function normalizeMedia(raw) {
  const source = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  return Object.freeze({
    id: cleanUuid(source.id || source.media_id || source.mediaId),
    objectKey: cleanText(source.object_key || source.object_name || source.objectKey, 1000),
    filename: cleanText(source.original_filename || source.filename || source.name, 255),
    mimeType: cleanText(source.mime_type || source.mimeType, 160).toLowerCase(),
    sizeBytes: Math.max(0, Number(source.size_bytes || source.sizeBytes) || 0),
  });
}

export function normalizeTrainingPracticalProject(raw) {
  const source = sourceObject(raw);
  const rawStatus = cleanText(source.status || "not_started", 40).toLowerCase();
  const rawEvidenceKind = cleanText(source.evidence_kind || source.evidenceKind, 40).toLowerCase();
  const grandfathered = source.grandfathered === true
    || source.is_grandfathered === true
    || rawStatus === "grandfathered"
    || rawEvidenceKind === "grandfathered";
  const status = grandfathered
    ? "grandfathered"
    : PRACTICAL_STATUSES.has(rawStatus) ? rawStatus : "not_started";
  const rawPlatform = cleanText(source.platform, 40).toLowerCase();
  const evidenceUrl = safeHttpsUrl(source.evidence_url || source.evidenceUrl);
  const media = normalizeMedia(source.media || {
    id: source.media_id || source.mediaId,
    object_key: source.object_key || source.objectKey,
    original_filename: source.original_filename || source.filename,
    mime_type: source.mime_type || source.mimeType,
    size_bytes: source.size_bytes || source.sizeBytes,
  });
  return Object.freeze({
    id: cleanUuid(source.id),
    status,
    approved: ["approved", "grandfathered"].includes(status),
    grandfathered,
    platform: PRACTICAL_PLATFORMS.has(rawPlatform) ? rawPlatform : "",
    evidenceUrl,
    evidenceKind: media.id ? "private_file" : evidenceUrl ? "https_url" : "",
    media,
    learnerNote: cleanText(source.learner_note || source.learnerNote, 2000),
    reviewNote: cleanText(source.review_note || source.reviewNote, 2000),
    submittedAt: cleanText(source.submitted_at || source.submittedAt, 80),
    reviewedAt: cleanText(source.reviewed_at || source.reviewedAt, 80),
    reviewerName: cleanText(source.reviewer_name || source.reviewerName, 180),
    version: Math.max(0, Number(source.version) || 0),
    attemptCount: Math.max(0, Number(source.attempt_count || source.attemptCount) || 0),
    learnerName: cleanText(source.learner_name || source.learnerName || source.display_name, 180),
    learnerEmail: cleanText(source.learner_email || source.learnerEmail || source.email, 320),
  });
}

export function normalizeTrainingPracticalReviews(raw) {
  const source = Array.isArray(raw)
    ? raw
    : Array.isArray(raw?.practical_reviews)
      ? raw.practical_reviews
      : Array.isArray(raw?.practicalReviews)
        ? raw.practicalReviews
        : Array.isArray(raw?.items) ? raw.items : [];
  const seen = new Set();
  return Object.freeze(source.slice(0, 50).map(normalizeTrainingPracticalProject).filter((item) => {
    if (!item.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return ["submitted", "changes_requested", "approved"].includes(item.status);
  }));
}

export function trainingPracticalGateSnapshot(project, options = {}) {
  const normalized = normalizeTrainingPracticalProject(project);
  const coursesComplete = options.coursesComplete === true;
  const examPassed = options.examPassed === true;
  const nextStep = !coursesComplete
    ? "courses"
    : !normalized.approved
      ? normalized.status === "submitted" ? "manager_review" : "practical"
      : !examPassed ? "exam" : "done";
  return Object.freeze({
    status: normalized.status,
    approved: normalized.approved,
    readyForExam: coursesComplete && normalized.approved,
    nextStep,
    completedSteps: [coursesComplete, normalized.approved, examPassed].filter(Boolean).length,
    totalSteps: 3,
  });
}

function platformLabel(platform) {
  return { instagram: "Instagram Reels", youtube: "YouTube Shorts", vk: "VK Клипы" }[platform] || "Платформа не выбрана";
}

function statusCopy(project) {
  if (project.grandfathered) return {
    tone: "approved",
    eyebrow: "Допуск сохранён",
    title: "Пробная работа зачтена по прежнему допуску",
    body: "Ваш рабочий доступ был подтверждён до появления нового этапа. При желании загрузите свежий пример для обратной связи — доступ от этого не закроется.",
  };
  return {
    not_started: {
      tone: "new",
      eyebrow: "Практический допуск",
      title: "Покажите один пробный вертикальный ролик",
      body: "Это может быть черновик: публиковать его в соцсети не требуется. Руководитель проверит товар, кадр, текст и безопасность обещаний.",
    },
    draft: {
      tone: "new",
      eyebrow: "Черновик",
      title: "Пробная работа ещё не отправлена",
      body: "Добавьте MP4 или HTTPS-ссылку, пройдите самопроверку и отправьте материал руководителю.",
    },
    submitted: {
      tone: "waiting",
      eyebrow: "На проверке",
      title: "Руководитель получил пробную работу",
      body: "Пока материал проверяется, повторите симуляторы платформ. Повторная отправка не ускорит решение.",
    },
    changes_requested: {
      tone: "changes",
      eyebrow: "Нужна доработка",
      title: "Исправьте конкретные замечания и отправьте новую версию",
      body: "Старое решение сохранено в истории. После исправления можно передать новый файл или ссылку.",
    },
    approved: {
      tone: "approved",
      eyebrow: "Навык подтверждён",
      title: "Пробная работа принята руководителем",
      body: "Практический этап закрыт. Теперь итоговый экзамен проверит решения в нестандартных ситуациях.",
    },
  }[project.status];
}

function evidenceSummaryMarkup(project, options = {}) {
  const mediaButton = project.media.objectKey
    ? `<button class="btn btn-secondary btn-small" type="button" data-action="open-training-practical-media" data-object-key="${escapeHtml(project.media.objectKey)}">Открыть защищённый MP4</button>`
    : "";
  const link = project.evidenceUrl
    ? `<a class="btn btn-secondary btn-small" href="${escapeHtml(project.evidenceUrl)}" target="_blank" rel="noopener noreferrer">Открыть ссылку</a>`
    : "";
  if (!mediaButton && !link && !project.learnerNote) return "";
  return `
    <div class="training-practical__evidence">
      <div><span>Платформа</span><strong>${escapeHtml(platformLabel(project.platform))}</strong></div>
      ${project.media.filename ? `<div><span>Файл</span><strong>${escapeHtml(project.media.filename)}</strong></div>` : ""}
      ${project.learnerNote ? `<p>${escapeHtml(project.learnerNote)}</p>` : ""}
      <div class="inline-actions">${mediaButton}${link}${options.compact ? "" : `<small>${project.submittedAt ? `Отправлено: ${escapeHtml(project.submittedAt)}` : ""}</small>`}</div>
    </div>
  `;
}

function submissionFormMarkup(project, maxUploadBytes) {
  const resubmission = project.status === "changes_requested";
  return `
    <form id="training-practical-submit-form" class="training-practical__form" data-training-practical-form novalidate>
      <input type="hidden" name="expected_version" value="${project.version || ""}" />
      <fieldset class="training-practical__source">
        <legend>1. Откуда взять пробную работу</legend>
        <label><input type="radio" name="evidence_source" value="file" data-training-practical-source checked /><span><strong>Загрузить MP4</strong><small>Защищённая папка команды, до ${Math.max(1, Math.round(maxUploadBytes / 1048576))} МБ</small></span></label>
        <label><input type="radio" name="evidence_source" value="url" data-training-practical-source /><span><strong>Вставить HTTPS-ссылку для предварительного разбора</strong><small>Руководитель сможет вернуть комментарии, но финальный допуск выдаётся только по защищённому MP4</small></span></label>
      </fieldset>
      <div class="training-practical__source-panel" data-training-practical-source-panel="file">
        <label class="field"><span>Вертикальный ролик MP4 *</span><input name="file" type="file" accept="video/mp4" required /><small>Рекомендуется 8–30 секунд, 9:16, без личных данных в имени файла.</small></label>
      </div>
      <div class="training-practical__source-panel" data-training-practical-source-panel="url" hidden>
        <label class="field"><span>HTTPS-ссылка *</span><input name="evidence_url" type="url" inputmode="url" maxlength="2048" placeholder="https://…" /><small>Не вставляйте ссылку, содержащую пароль, токен или приватные параметры доступа.</small></label>
      </div>
      <label class="field"><span>Платформа, под которую снят ролик *</span><select name="platform" required><option value="">Выберите платформу</option><option value="instagram">Instagram Reels</option><option value="youtube">YouTube Shorts</option><option value="vk">VK Клипы</option></select></label>
      <label class="field"><span>Что вы сделали и что хотите проверить *</span><textarea name="learner_note" required minlength="20" maxlength="2000" rows="4" placeholder="Товар, замысел ролика, призыв и вопросы руководителю"></textarea></label>
      <fieldset class="training-practical__checks">
        <legend>2. Самопроверка перед отправкой</legend>
        <label><input type="checkbox" name="self_check" value="product_match" required /><span>Товар и упаковка совпадают с заданием.</span></label>
        <label><input type="checkbox" name="self_check" value="watched_full" required /><span>Я посмотрел(а) ролик полностью со звуком и без звука.</span></label>
        <label><input type="checkbox" name="self_check" value="claims_safe" required /><span>В тексте нет неподтверждённых обещаний и скрытой рекламы.</span></label>
        <label><input type="checkbox" name="rights_confirmed" required /><span>У команды есть право проверять и использовать этот материал.</span></label>
      </fieldset>
      <button class="btn" type="submit">${resubmission ? "Отправить исправленную версию" : "Передать руководителю"} <span aria-hidden="true">→</span></button>
    </form>
  `;
}

export function trainingPracticalProjectMarkup(rawProject, options = {}) {
  const project = normalizeTrainingPracticalProject(rawProject);
  const copy = statusCopy(project);
  const canSubmit = !project.approved && project.status !== "submitted";
  const maxUploadBytes = Math.max(1, Number(options.maxUploadBytes) || 52428800);
  return `
    <section id="training-practical-project" class="card training-practical training-practical--${copy.tone}" data-training-practical-project data-practical-status="${escapeHtml(project.status)}" aria-labelledby="training-practical-title">
      <header class="training-practical__header">
        <div><p class="eyebrow">${escapeHtml(copy.eyebrow)}</p><h2 id="training-practical-title">${escapeHtml(copy.title)}</h2><p>${escapeHtml(copy.body)}</p></div>
        <span class="training-practical__stamp" aria-hidden="true">${project.approved ? "✓" : project.status === "submitted" ? "…" : "06"}</span>
      </header>
      ${project.reviewNote ? `<aside class="training-practical__review-note"><strong>${project.status === "changes_requested" ? "Что исправить" : "Комментарий руководителя"}</strong><p>${escapeHtml(project.reviewNote)}</p>${project.reviewerName ? `<small>${escapeHtml(project.reviewerName)}</small>` : ""}</aside>` : ""}
      ${evidenceSummaryMarkup(project)}
      ${canSubmit ? submissionFormMarkup(project, maxUploadBytes) : ""}
      ${project.status === "submitted" ? `<div class="training-practical__waiting" role="status"><span aria-hidden="true"></span><p><strong>Ничего не потеряно.</strong> Решение появится здесь после проверки руководителем.</p><button class="btn btn-secondary btn-small" type="button" data-action="retry-bootstrap">Обновить статус</button></div>` : ""}
    </section>
  `;
}

export function trainingPracticalReviewQueueMarkup(rawReviews) {
  const reviews = normalizeTrainingPracticalReviews(rawReviews).filter((item) => item.status === "submitted");
  return `
    <section class="card training-practical-queue" aria-labelledby="training-practical-queue-title">
      <header class="card-header"><div><p class="eyebrow">Практический допуск</p><h2 id="training-practical-queue-title">Пробные работы на проверке</h2><p>Сначала полностью откройте материал, затем сохраните одно конкретное решение. Финально принять можно только защищённый MP4 — внешняя ссылка подходит для предварительного разбора.</p></div><div class="training-practical-queue__actions"><span class="badge ${reviews.length ? "badge-warning" : "badge-success"}">${reviews.length} в очереди</span><button class="btn btn-secondary btn-small" type="button" data-action="refresh-training-practical-reviews">Обновить пробные работы</button></div></header>
      ${reviews.length ? `<div class="training-practical-queue__list">${reviews.map((project) => `
        <article class="training-practical-review" data-practical-review-id="${escapeHtml(project.id)}" data-practical-evidence-kind="${escapeHtml(project.evidenceKind)}">
          <div class="training-practical-review__identity"><span aria-hidden="true">${escapeHtml((project.learnerName || project.learnerEmail || "У").slice(0, 1).toUpperCase())}</span><div><strong>${escapeHtml(project.learnerName || "Участник")}</strong><small>${escapeHtml(project.learnerEmail)}</small></div></div>
          ${evidenceSummaryMarkup(project, { compact: true })}
          <form class="training-practical-review__form" data-practical-review-id="${escapeHtml(project.id)}" data-practical-evidence-kind="${escapeHtml(project.evidenceKind)}" novalidate>
            <input type="hidden" name="expected_version" value="${project.version || ""}" />
            <label class="field"><span>Комментарий решения *</span><textarea name="review_note" required minlength="10" maxlength="2000" rows="3" placeholder="Что принято или что конкретно исправить"></textarea></label>
            <label class="acknowledgement"><input name="media_watched_confirmed" type="checkbox" required /><span>Материал просмотрен полностью; товар, кадр, текст и обещания проверены.</span></label>
            ${project.evidenceKind === "private_file" ? "" : `<p class="training-practical-review__immutable-note" role="note">Для финального принятия попросите участника загрузить MP4 в защищённую папку.</p>`}
            <div class="inline-actions"><button class="btn" type="submit" name="decision" value="approve" ${project.evidenceKind === "private_file" ? "" : "disabled aria-disabled=\"true\""}>Принять работу</button><button class="btn btn-secondary" type="submit" name="decision" value="request_changes">Вернуть на доработку</button></div>
          </form>
        </article>
      `).join("")}</div>` : `<div class="training-practical-queue__empty"><span aria-hidden="true">✓</span><div><strong>Очередь разобрана</strong><p>Новые пробные работы появятся здесь после отправки участником.</p></div></div>`}
    </section>
  `;
}

export function syncTrainingPracticalSource(form, requestedSource = "") {
  if (!form || typeof form.querySelectorAll !== "function") return "file";
  const selected = requestedSource
    || form.querySelector('[name="evidence_source"]:checked')?.value
    || "file";
  const source = selected === "url" ? "url" : "file";
  Array.from(form.querySelectorAll("[data-training-practical-source-panel]")).forEach((panel) => {
    const active = panel.dataset.trainingPracticalSourcePanel === source;
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", active ? "false" : "true");
    Array.from(panel.querySelectorAll("input, select, textarea")).forEach((input) => {
      if (input.name === "file" || input.name === "evidence_url") input.required = active;
    });
  });
  return source;
}

export function readTrainingPracticalSubmission(form) {
  const values = new FormData(form);
  const source = String(values.get("evidence_source") || "file") === "url" ? "url" : "file";
  const file = values.get("file");
  const evidenceUrl = safeHttpsUrl(values.get("evidence_url"));
  const platform = cleanText(values.get("platform"), 40).toLowerCase();
  const learnerNote = cleanText(values.get("learner_note"), 2000);
  const checks = [...new Set(values.getAll("self_check").map(String))];
  const errors = [];
  if (!PRACTICAL_PLATFORMS.has(platform)) errors.push("Выберите платформу ролика.");
  if (learnerNote.length < 20) errors.push("Опишите замысел и вопросы минимум в 20 символах.");
  if (!["product_match", "watched_full", "claims_safe"].every((item) => checks.includes(item))) errors.push("Подтвердите все три пункта самопроверки.");
  if (values.get("rights_confirmed") !== "on") errors.push("Подтвердите право команды проверять материал.");
  if (source === "url" && !evidenceUrl) errors.push("Введите безопасную HTTPS-ссылку без логина и пароля.");
  if (source === "file" && (!(file instanceof File) || file.size < 1 || file.type !== "video/mp4")) errors.push("Выберите непустой MP4-файл.");
  return Object.freeze({
    valid: errors.length === 0,
    errors: Object.freeze(errors),
    file: source === "file" ? file : null,
    payload: Object.freeze({
      platform,
      learner_note: learnerNote,
      evidence_url: source === "url" ? evidenceUrl : null,
      rights_confirmed: true,
      self_check_codes: checks,
      expected_version: Math.max(0, Number(values.get("expected_version")) || 0) || undefined,
    }),
  });
}

export function readTrainingPracticalDecision(form, submitter) {
  const values = new FormData(form);
  const decision = String(submitter?.value || values.get("decision") || "");
  const reviewNote = cleanText(values.get("review_note"), 2000);
  const errors = [];
  if (!["approve", "request_changes"].includes(decision)) errors.push("Выберите решение по пробной работе.");
  if (decision === "approve" && form.dataset.practicalEvidenceKind !== "private_file") errors.push("Финальный допуск выдаётся только по защищённому MP4. Верните ссылку на доработку и запросите файл.");
  if (reviewNote.length < 10) errors.push("Добавьте конкретный комментарий минимум в 10 символах.");
  if (values.get("media_watched_confirmed") !== "on") errors.push("Подтвердите полный просмотр материала.");
  return Object.freeze({
    valid: errors.length === 0,
    errors: Object.freeze(errors),
    payload: Object.freeze({
      project_id: cleanUuid(form.dataset.practicalReviewId),
      decision,
      review_note: reviewNote,
      media_watched_confirmed: true,
      expected_version: Math.max(0, Number(values.get("expected_version")) || 0) || undefined,
    }),
  });
}
