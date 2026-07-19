const MAX_COMPARISONS = 16;
const MAX_TRANSCRIPT_ITEMS = 12;
const MAX_FALLBACK_POINTS = 6;
const MAX_CHECKPOINT_OPTIONS = 5;
const ALLOWED_CAPTION_STATUSES = new Set(["verified", "draft_needs_audio_qc"]);

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const nested of Object.values(value)) deepFreeze(nested);
  return value;
}

function cleanText(value, fallback = "", limit = 1200) {
  const text = String(value ?? "").replace(/\s+/gu, " ").trim();
  return (text || fallback).slice(0, limit);
}

function cleanId(value, fallback = "item") {
  const text = String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 90);
  return text || fallback;
}

function safeMediaUrl(value) {
  const raw = String(value ?? "").trim();
  if (!raw || raw.includes("\\")) return "";
  if (raw.startsWith("/") && !raw.startsWith("//") && !raw.split("/").includes("..")) return raw;
  if (raw.startsWith("./") && !raw.split("/").includes("..")) return raw;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/gu, "&amp;")
    .replace(/</gu, "&lt;")
    .replace(/>/gu, "&gt;")
    .replace(/"/gu, "&quot;")
    .replace(/'/gu, "&#039;");
}

function videoMimeType(url) {
  const pathname = String(url || "").split(/[?#]/u, 1)[0].toLowerCase();
  return pathname.endsWith(".webm") ? "video/webm" : "video/mp4";
}

function normalizeTranscript(raw) {
  return (Array.isArray(raw) ? raw : [])
    .slice(0, MAX_TRANSCRIPT_ITEMS)
    .map((item, index) => {
      const source = typeof item === "string" ? { text: item } : item;
      if (!source || typeof source !== "object") return null;
      const text = cleanText(source.text || source.body, "", 800);
      if (!text) return null;
      return {
        time: cleanText(source.time, index ? "" : "00:00", 40),
        text,
      };
    })
    .filter(Boolean);
}

function normalizeFallback(raw, verdict) {
  const source = raw && typeof raw === "object" ? raw : {};
  const defaults = verdict === "correct"
    ? {
      symbol: "✓",
      title: "Допустимый рабочий вариант",
      description: "Сверьте признаки по текстовому разбору.",
    }
    : {
      symbol: "!",
      title: "Так делать нельзя",
      description: "Сверьте риск и способ исправления по текстовому разбору.",
    };
  const points = (Array.isArray(source.points) ? source.points : [])
    .slice(0, MAX_FALLBACK_POINTS)
    .map((point) => cleanText(point, "", 240))
    .filter(Boolean);
  return {
    symbol: cleanText(source.symbol, defaults.symbol, 12),
    title: cleanText(source.title, defaults.title, 180),
    description: cleanText(source.description, defaults.description, 600),
    points,
  };
}

function normalizeMedia(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  const videoUrl = safeMediaUrl(source.video_url ?? source.videoUrl);
  const posterUrl = safeMediaUrl(source.poster_url ?? source.posterUrl);
  const candidateCaptionsUrl = safeMediaUrl(source.captions_url ?? source.captionsUrl);
  const captionsUrl = /\.vtt(?:[?#]|$)/iu.test(candidateCaptionsUrl) ? candidateCaptionsUrl : "";
  const rawStatus = cleanText(source.captions_status ?? source.captionsStatus, "verified", 40);
  const captionsStatus = ALLOWED_CAPTION_STATUSES.has(rawStatus) ? rawStatus : "verified";
  return {
    videoUrl,
    posterUrl,
    captionsUrl,
    captionsStatus,
    durationSeconds: Math.max(1, Math.min(600, Number(source.duration_seconds ?? source.durationSeconds) || 0)),
  };
}

function normalizeSide(raw, verdict) {
  const source = raw && typeof raw === "object" ? raw : {};
  const transcript = normalizeTranscript(source.transcript);
  const media = normalizeMedia(source.media);
  const videoReady = Boolean(media.videoUrl && media.captionsUrl && transcript.length);
  return {
    verdict,
    label: cleanText(source.label, verdict === "correct" ? "Правильно" : "Ошибка", 80),
    headline: cleanText(
      source.headline || source.title,
      verdict === "correct" ? "Допустимый вариант" : "Рискованный вариант",
      220,
    ),
    reason: cleanText(source.reason, "Сверьте признаки с рабочим правилом.", 700),
    fallback: normalizeFallback(source.fallback, verdict),
    transcript,
    media,
    videoReady,
    mediaBlocked: Boolean(media.videoUrl && !videoReady),
  };
}

function normalizeCheckpoint(raw, comparisonId) {
  if (!raw || typeof raw !== "object") return null;
  const seen = new Set();
  const options = (Array.isArray(raw.options) ? raw.options : [])
    .slice(0, MAX_CHECKPOINT_OPTIONS)
    .map((option, index) => {
      if (!option || typeof option !== "object") return null;
      const id = cleanId(option.id, `option_${index + 1}`);
      const label = cleanText(option.label || option.text, "", 500);
      const feedback = cleanText(option.feedback || option.explanation, "", 700);
      if (!label || !feedback || seen.has(id)) return null;
      seen.add(id);
      const correct = option.correct === true;
      return {
        id,
        label,
        feedback,
        correct,
        critical: !correct && option.critical === true,
      };
    })
    .filter(Boolean);
  if (options.length < 3 || options.filter((option) => option.correct).length !== 1) return null;
  return {
    id: `checkpoint_${comparisonId}`,
    prompt: cleanText(raw.prompt, "Какое действие вы выберете?", 600),
    options,
  };
}

function normalizeComparison(raw, index, checkpointMap) {
  if (!raw || typeof raw !== "object") return null;
  const id = cleanId(raw.id, `comparison_${index + 1}`);
  const correct = normalizeSide(raw.correct, "correct");
  const mistake = normalizeSide(raw.mistake ?? raw.error, "mistake");
  if (!correct.transcript.length || !mistake.transcript.length) return null;
  return {
    id,
    moduleCode: cleanId(raw.module_code ?? raw.moduleCode, "course"),
    lessonId: cleanId(raw.lesson_id ?? raw.lessonId, "lesson"),
    platform: cleanText(raw.platform, "Рабочий сценарий", 100),
    title: cleanText(raw.title, `Разбор ${index + 1}`, 240),
    objective: cleanText(raw.objective, "Сравните допустимый вариант и ошибку.", 600),
    correct,
    mistake,
    checkpoint: checkpointMap.get(id) || null,
  };
}

export function normalizeTrainingMediaCatalog(raw) {
  const source = Array.isArray(raw)
    ? { comparisons: raw }
    : raw && typeof raw === "object"
      ? raw
      : {};
  const seen = new Set();
  const checkpointMap = new Map();
  for (const candidate of Array.isArray(source.checkpoints) ? source.checkpoints : []) {
    const comparisonId = cleanId(candidate?.comparison_id ?? candidate?.comparisonId, "");
    if (!comparisonId || checkpointMap.has(comparisonId)) continue;
    const checkpoint = normalizeCheckpoint(candidate, comparisonId);
    if (checkpoint) checkpointMap.set(comparisonId, checkpoint);
  }
  const comparisons = [];
  for (const [index, candidate] of (Array.isArray(source.comparisons) ? source.comparisons : [])
    .slice(0, MAX_COMPARISONS)
    .entries()) {
    const item = normalizeComparison(candidate, index, checkpointMap);
    if (!item || seen.has(item.id)) continue;
    seen.add(item.id);
    comparisons.push(item);
  }
  return deepFreeze({
    schemaVersion: Number(source.schema_version ?? source.schemaVersion) || 1,
    language: cleanText(source.language, "ru", 12),
    reviewedAt: cleanText(source.reviewed_at ?? source.reviewedAt, "", 40),
    comparisons,
  });
}

export function trainingMediaCardsForModule(raw, moduleCode) {
  const safeModuleCode = cleanId(moduleCode, "course");
  return deepFreeze(
    normalizeTrainingMediaCatalog(raw).comparisons.filter((item) => item.moduleCode === safeModuleCode),
  );
}

function fallbackMarkup(side, transcriptId) {
  return `
    <div class="training-media-side__fallback" role="img" aria-label="${escapeHtml(side.fallback.title)}. ${escapeHtml(side.fallback.description)}">
      <span class="training-media-side__symbol" aria-hidden="true">${escapeHtml(side.fallback.symbol)}</span>
      <div>
        <strong>${escapeHtml(side.fallback.title)}</strong>
        <p>${escapeHtml(side.fallback.description)}</p>
      </div>
      ${side.fallback.points.length ? `<ul aria-label="Признаки варианта">${side.fallback.points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>` : ""}
    </div>
    ${side.mediaBlocked ? `<p class="training-media-side__media-notice" role="note" aria-describedby="${escapeHtml(transcriptId)}"><strong>Видео скрыто.</strong> Для него нет полного безопасного комплекта: русской VTT-дорожки и текстового транскрипта.</p>` : ""}
  `;
}

function mediaMarkup(card, side) {
  const instanceId = `training-media-${card.id}-${side.verdict}`;
  const transcriptId = `${instanceId}-transcript`;
  const statusNotice = side.media.captionsStatus === "draft_needs_audio_qc"
    ? `<p class="training-media-side__caption-status" role="note"><span aria-hidden="true">◷</span> Русские субтитры добавлены как редакторский черновик: до итоговой аттестации требуется дословная сверка со звуком.</p>`
    : "";
  const media = side.videoReady
    ? `
      <figure class="training-media-side__figure">
        <video class="training-media-side__video" controls preload="none" playsinline crossorigin="anonymous" aria-label="Учебное видео: ${escapeHtml(side.headline)}" aria-describedby="${escapeHtml(transcriptId)}"${side.media.posterUrl ? ` poster="${escapeHtml(side.media.posterUrl)}"` : ""} data-training-media-video>
          <source src="${escapeHtml(side.media.videoUrl)}" type="${escapeHtml(videoMimeType(side.media.videoUrl))}" />
          <track kind="captions" src="${escapeHtml(side.media.captionsUrl)}" srclang="ru" label="Русские субтитры" default />
          Ваш браузер не может воспроизвести видео. Используйте визуальный и текстовый разбор ниже.
        </video>
        <figcaption>Видео запускается только вручную; звук и последний кадр входят в обязательную проверку.</figcaption>
      </figure>
      ${statusNotice}
      ${fallbackMarkup({ ...side, mediaBlocked: false }, transcriptId)}
    `
    : fallbackMarkup(side, transcriptId);
  return { instanceId, transcriptId, media };
}

function transcriptMarkup(side, transcriptId) {
  return `
    <details id="${escapeHtml(transcriptId)}" class="training-media-side__transcript">
      <summary>Текстовый разбор${side.videoReady ? " и доступная альтернатива видео" : ""}</summary>
      <ol>
        ${side.transcript.map((item) => `<li>${item.time ? `<span>${escapeHtml(item.time)}</span>` : ""}<p>${escapeHtml(item.text)}</p></li>`).join("")}
      </ol>
    </details>
  `;
}

function sideMarkup(card, side, active) {
  const { instanceId, transcriptId, media } = mediaMarkup(card, side);
  const isCorrect = side.verdict === "correct";
  return `
    <section id="${escapeHtml(instanceId)}" class="training-media-side training-media-side--${escapeHtml(side.verdict)}${active ? " is-active" : ""}" data-training-media-side="${escapeHtml(side.verdict)}" aria-labelledby="${escapeHtml(instanceId)}-title">
      <header class="training-media-side__header">
        <span class="training-media-side__verdict"><b aria-hidden="true">${isCorrect ? "✓" : "!"}</b>${escapeHtml(side.label)}</span>
        <h4 id="${escapeHtml(instanceId)}-title">${escapeHtml(side.headline)}</h4>
        <p>${escapeHtml(side.reason)}</p>
      </header>
      ${media}
      ${transcriptMarkup(side, transcriptId)}
    </section>
  `;
}

function checkpointMarkup(card) {
  if (!card.checkpoint) return "";
  const checkpointId = `training-media-${card.id}-checkpoint`;
  const feedbackId = `${checkpointId}-feedback`;
  return `
    <section class="training-media-checkpoint" data-training-media-checkpoint="${escapeHtml(card.checkpoint.id)}" data-training-media-checkpoint-state="idle" aria-labelledby="${escapeHtml(checkpointId)}-title">
      <p class="training-media-card__eyebrow">Проверочный кейс</p>
      <fieldset>
        <legend id="${escapeHtml(checkpointId)}-title">${escapeHtml(card.checkpoint.prompt)}</legend>
        <div class="training-media-checkpoint__options" role="radiogroup" aria-describedby="${escapeHtml(feedbackId)}">
          ${card.checkpoint.options.map((option, index) => {
            const optionId = `${checkpointId}-${option.id}`;
            return `
              <label for="${escapeHtml(optionId)}">
                <input id="${escapeHtml(optionId)}" type="radio" name="${escapeHtml(checkpointId)}-answer" value="${escapeHtml(option.id)}" data-training-media-checkpoint-option data-training-media-correct="${option.correct ? "true" : "false"}" data-training-media-critical="${option.critical ? "true" : "false"}" data-training-media-feedback="${escapeHtml(option.feedback)}" />
                <span><b aria-hidden="true">${String.fromCharCode(65 + index)}</b>${escapeHtml(option.label)}</span>
              </label>
            `;
          }).join("")}
        </div>
      </fieldset>
      <button class="training-media-checkpoint__submit" type="button" data-action="training-media-checkpoint-evaluate">Проверить решение</button>
      <div id="${escapeHtml(feedbackId)}" class="training-media-checkpoint__feedback" data-training-media-checkpoint-feedback role="status" aria-live="polite" aria-atomic="true" tabindex="-1">Выберите один вариант. После проверки появится причинно-следственный разбор.</div>
    </section>
  `;
}

function cardMarkup(card, index) {
  const titleId = `training-media-${card.id}-title`;
  const statusId = `training-media-${card.id}-status`;
  return `
    <article class="training-media-card" data-training-media-card="${escapeHtml(card.id)}" data-training-media-module="${escapeHtml(card.moduleCode)}" data-training-media-lesson="${escapeHtml(card.lessonId)}" data-training-media-focus="correct" aria-labelledby="${escapeHtml(titleId)}">
      <header class="training-media-card__header">
        <p class="training-media-card__eyebrow">${escapeHtml(card.platform)} · пример ${index + 1}</p>
        <h3 id="${escapeHtml(titleId)}">${escapeHtml(card.title)}</h3>
        <p>${escapeHtml(card.objective)}</p>
      </header>
      <div class="training-media-card__switch" role="group" aria-label="Выберите сторону сравнения" aria-describedby="${escapeHtml(statusId)}">
        <button type="button" data-action="training-media-focus" data-training-media-focus-value="correct" aria-pressed="true" aria-controls="training-media-${escapeHtml(card.id)}-correct"><span aria-hidden="true">✓</span> Показать правильно</button>
        <button type="button" data-action="training-media-focus" data-training-media-focus-value="mistake" aria-pressed="false" aria-controls="training-media-${escapeHtml(card.id)}-mistake"><span aria-hidden="true">!</span> Разобрать ошибку</button>
      </div>
      <p id="${escapeHtml(statusId)}" class="training-media-card__status" role="status" aria-live="polite" aria-atomic="true" data-training-media-status>В фокусе: правильный вариант. Сравните его с ошибкой рядом.</p>
      <div class="training-media-card__comparison">
        ${sideMarkup(card, card.correct, true)}
        ${sideMarkup(card, card.mistake, false)}
      </div>
      ${checkpointMarkup(card)}
    </article>
  `;
}

export function trainingMediaCardsMarkup(raw, options = {}) {
  const catalog = normalizeTrainingMediaCatalog(raw);
  const moduleCode = cleanId(options?.moduleCode, "");
  const items = moduleCode
    ? catalog.comparisons.filter((item) => item.moduleCode === moduleCode)
    : catalog.comparisons;
  if (!items.length) return "";
  const headingId = `training-media-cards-${moduleCode || "all"}-title`;
  return `
    <section class="training-media-cards" data-training-media-cards="${escapeHtml(moduleCode || "all")}" aria-labelledby="${escapeHtml(headingId)}">
      <header class="training-media-cards__header">
        <div>
          <p class="training-media-card__eyebrow">Сначала сравните — потом повторите</p>
          <h2 id="${escapeHtml(headingId)}">Как правильно / где ошибка</h2>
        </div>
        <p>Видео не запускаются автоматически. У каждого примера есть русский текстовый разбор и безопасная визуальная замена на случай недоступного файла.</p>
      </header>
      <div class="training-media-cards__list">
        ${items.map(cardMarkup).join("")}
      </div>
    </section>
  `;
}

function cardRoot(root) {
  if (!root || typeof root.querySelectorAll !== "function") return null;
  if (typeof root.matches === "function" && root.matches("[data-training-media-card]")) return root;
  return typeof root.closest === "function" ? root.closest("[data-training-media-card]") : null;
}

export function stopTrainingMedia(root) {
  if (!root || typeof root.querySelectorAll !== "function") return 0;
  const videos = Array.from(root.querySelectorAll("[data-training-media-video]"));
  for (const video of videos) {
    if (typeof video.pause === "function") video.pause();
  }
  return videos.length;
}

export function setTrainingMediaCardFocus(root, verdict = "correct") {
  const card = cardRoot(root);
  if (!card) return "";
  const selected = verdict === "mistake" ? "mistake" : "correct";
  card.dataset.trainingMediaFocus = selected;
  for (const button of card.querySelectorAll("[data-training-media-focus-value]")) {
    const active = button.dataset.trainingMediaFocusValue === selected;
    button.setAttribute("aria-pressed", String(active));
  }
  for (const side of card.querySelectorAll("[data-training-media-side]")) {
    side.classList.toggle("is-active", side.dataset.trainingMediaSide === selected);
  }
  const status = card.querySelector("[data-training-media-status]");
  if (status) {
    status.textContent = selected === "correct"
      ? "В фокусе: правильный вариант. Сравните его с ошибкой рядом."
      : "В фокусе: ошибка. Прочитайте причину и способ исправления."
  }
  stopTrainingMedia(card);
  return selected;
}

function checkpointRoot(root) {
  if (!root || typeof root.querySelectorAll !== "function") return null;
  if (typeof root.matches === "function" && root.matches("[data-training-media-checkpoint]")) return root;
  return typeof root.closest === "function" ? root.closest("[data-training-media-checkpoint]") : null;
}

export function evaluateTrainingMediaCheckpoint(root, optionId = "") {
  const checkpoint = checkpointRoot(root);
  if (!checkpoint) return { selectedId: "", correct: false, critical: false };
  const options = Array.from(checkpoint.querySelectorAll("[data-training-media-checkpoint-option]"));
  const requestedId = cleanId(optionId, "");
  const selected = requestedId
    ? options.find((option) => cleanId(option.value, "") === requestedId)
    : options.find((option) => option.checked);
  const feedback = checkpoint.querySelector("[data-training-media-checkpoint-feedback]");
  if (!selected) {
    checkpoint.dataset.trainingMediaCheckpointState = "missing";
    if (feedback) feedback.textContent = "Сначала выберите один вариант ответа.";
    return { selectedId: "", correct: false, critical: false };
  }
  const correct = selected.dataset.trainingMediaCorrect === "true";
  const critical = !correct && selected.dataset.trainingMediaCritical === "true";
  const selectedId = cleanId(selected.value, "");
  checkpoint.dataset.trainingMediaCheckpointState = correct ? "correct" : critical ? "critical" : "incorrect";
  for (const option of options) {
    const isSelected = option === selected;
    option.setAttribute("aria-invalid", String(isSelected && !correct));
    option.dataset.trainingMediaEvaluated = isSelected ? "selected" : "idle";
  }
  if (feedback) {
    const prefix = correct ? "Верно. " : critical ? "Критическая ошибка. " : "Пока неверно. ";
    feedback.textContent = `${prefix}${cleanText(selected.dataset.trainingMediaFeedback, "Сверьте решение с разбором выше.", 700)}`;
    if (typeof feedback.focus === "function") feedback.focus({ preventScroll: true });
  }
  const card = cardRoot(checkpoint);
  if (card) setTrainingMediaCardFocus(card, correct ? "correct" : "mistake");
  return { selectedId, correct, critical };
}

export function bindTrainingMediaCards(root) {
  if (!root || typeof root.addEventListener !== "function") return () => {};
  const onClick = (event) => {
    const action = typeof event.target?.closest === "function"
      ? event.target.closest('[data-action="training-media-focus"]')
      : null;
    if (!action || (typeof root.contains === "function" && !root.contains(action))) {
      const evaluateAction = typeof event.target?.closest === "function"
        ? event.target.closest('[data-action="training-media-checkpoint-evaluate"]')
        : null;
      if (!evaluateAction || (typeof root.contains === "function" && !root.contains(evaluateAction))) return;
      evaluateTrainingMediaCheckpoint(evaluateAction);
      return;
    }
    setTrainingMediaCardFocus(action, action.dataset.trainingMediaFocusValue);
  };
  root.addEventListener("click", onClick);
  return () => root.removeEventListener("click", onClick);
}
