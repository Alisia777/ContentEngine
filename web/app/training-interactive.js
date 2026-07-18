const MAX_WALKTHROUGHS = 8;
const MAX_FRAMES = 8;
const MAX_TRANSCRIPT_ITEMS = 16;
const MAX_CHECKLIST_ITEMS = 8;
const MAX_PRACTICE_OPTIONS = 6;
const STORAGE_PREFIX = "contentengine.training-walkthrough.v1";
const AUDIENCE_STORAGE_PREFIX = "contentengine.training-audience.v1";
const TRAINING_AUDIENCES = new Set(["self", "ai", "publish", "review"]);
const DEFAULT_AUDIENCE_BY_WALKTHROUGH = Object.freeze({
  first_login_route: ["self", "ai", "publish", "review"],
  material_to_review: ["ai"],
  phone_shooting_916: ["self"],
  eight_second_quality: ["self", "ai", "review"],
  publish_to_assigned_network: ["publish"],
  advertising_stop_decision: ["self", "ai", "publish", "review"],
  substitute_article_match: ["self", "ai", "publish", "review"],
  payout_status_route: ["self", "ai", "publish", "review"],
});

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const nested of Object.values(value)) deepFreeze(nested);
  return value;
}

function cleanText(value, fallback = "", limit = 1200) {
  const normalized = String(value ?? "").replace(/\s+/gu, " ").trim();
  return (normalized || fallback).slice(0, limit);
}

function cleanId(value, fallback) {
  const normalized = String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/gu, "_")
    .replace(/^_+|_+$/gu, "")
    .slice(0, 80);
  return normalized || fallback;
}

function safeMediaUrl(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  if (raw.startsWith("/") && !raw.startsWith("//")) return raw;
  if (raw.startsWith("./") && !raw.startsWith("../")) return raw;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}

function normalizeFrame(frame, index) {
  if (!frame || typeof frame !== "object") return null;
  const title = cleanText(frame.title || frame.label, `Шаг ${index + 1}`, 180);
  const body = cleanText(frame.body || frame.text || frame.description, "", 1000);
  if (!body) return null;
  return {
    id: cleanId(frame.id, `frame_${index + 1}`),
    time: cleanText(frame.time, `Шаг ${index + 1}`, 40),
    title,
    body,
    cue: cleanText(frame.cue || frame.action, "", 300),
    visualLabel: cleanText(frame.visual_label || frame.visualLabel, title, 180),
  };
}

function normalizeTranscriptItem(item, index) {
  if (typeof item === "string") {
    const text = cleanText(item, "", 1000);
    return text ? { time: "", text } : null;
  }
  if (!item || typeof item !== "object") return null;
  const text = cleanText(item.text || item.body, "", 1000);
  if (!text) return null;
  return {
    time: cleanText(item.time, index ? "" : "00:00", 40),
    text,
  };
}

function normalizeChecklistItem(item, index, walkthroughId) {
  const source = item && typeof item === "object" ? item : { text: item };
  const text = cleanText(source.text || source.label || source.title, "", 300);
  if (!text) return null;
  return {
    id: cleanId(source.id, `${walkthroughId}_check_${index + 1}`),
    text,
  };
}

function normalizePractice(raw, walkthroughIndex) {
  if (!raw || typeof raw !== "object") return null;
  const options = (Array.isArray(raw.options) ? raw.options : [])
    .slice(0, MAX_PRACTICE_OPTIONS)
    .map((option, index) => {
      if (!option || typeof option !== "object") return null;
      const label = cleanText(option.label || option.text, "", 360);
      if (!label) return null;
      return {
        id: cleanId(option.id || option.value, `option_${walkthroughIndex + 1}_${index + 1}`),
        label,
        correct: option.correct === true,
        feedback: cleanText(
          option.feedback,
          option.correct ? "Верно. Это безопасный следующий шаг." : "Попробуйте ещё раз и сверьтесь с разбором выше.",
          600,
        ),
      };
    })
    .filter(Boolean);
  if (options.length < 2 || options.filter((option) => option.correct).length !== 1) return null;
  return {
    prompt: cleanText(raw.prompt, "Какое действие вы выберете в этой ситуации?", 500),
    options,
    successMessage: cleanText(
      raw.success_message ?? raw.successMessage,
      "Решение верное. Завершите кадры и самопроверку — тренер навыка покажет следующий обязательный шаг.",
      600,
    ),
  };
}

function normalizeAudience(raw, walkthroughId) {
  const values = Array.isArray(raw) ? raw : typeof raw === "string" ? raw.split(/[\s,]+/u) : [];
  const aliases = { creator: "self", publisher: "publish" };
  const expanded = values.flatMap((value) => {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "all") return ["self", "ai", "publish", "review"];
    return [aliases[normalized] || normalized];
  });
  const normalized = [...new Set(expanded)]
    .filter((value) => TRAINING_AUDIENCES.has(value));
  return normalized.length
    ? normalized
    : [...(DEFAULT_AUDIENCE_BY_WALKTHROUGH[walkthroughId] || ["self", "ai", "publish", "review"])];
}

function normalizeWalkthrough(item, index) {
  if (!item || typeof item !== "object") return null;
  const id = cleanId(item.id, `walkthrough_${index + 1}`);
  const frames = (Array.isArray(item.frames) ? item.frames : [])
    .slice(0, MAX_FRAMES)
    .map(normalizeFrame)
    .filter(Boolean);
  if (frames.length < 2) return null;

  const transcript = (Array.isArray(item.transcript) ? item.transcript : [])
    .slice(0, MAX_TRANSCRIPT_ITEMS)
    .map(normalizeTranscriptItem)
    .filter(Boolean);
  const fallbackTranscript = frames.map((frame) => ({
    time: frame.time,
    text: `${frame.title}. ${frame.body}`,
  }));
  const checklistIds = new Map();
  const checklist = (Array.isArray(item.checklist) ? item.checklist : [])
    .slice(0, MAX_CHECKLIST_ITEMS)
    .map((entry, checklistIndex) => normalizeChecklistItem(entry, checklistIndex, id))
    .filter(Boolean)
    .map((entry, checklistIndex) => {
      const occurrence = checklistIds.get(entry.id) || 0;
      checklistIds.set(entry.id, occurrence + 1);
      if (!occurrence) return entry;
      return {
        ...entry,
        id: cleanId(`${entry.id}_${occurrence + 1}`, `${id}_check_${checklistIndex + 1}`),
      };
    });
  const practice = normalizePractice(item.practice, index);
  const fallbackDeliverable = checklist.at(-1)?.text
    || frames.at(-1)?.cue
    || frames.at(-1)?.title
    || "Понятный следующий шаг без риска для рабочей задачи.";

  return {
    id,
    eyebrow: cleanText(item.eyebrow, "Интерактивный видеоразбор", 100),
    title: cleanText(item.title, `Видеоразбор ${index + 1}`, 220),
    summary: cleanText(item.summary, "Пройдите кадры по порядку и повторите действие.", 1000),
    durationSeconds: Math.max(15, Math.min(600, Number(item.duration_seconds ?? item.durationSeconds) || 90)),
    reviewedAt: cleanText(item.reviewed_at ?? item.reviewedAt, "", 40),
    videoUrl: safeMediaUrl(item.video_url ?? item.videoUrl),
    posterUrl: safeMediaUrl(item.poster_url ?? item.posterUrl),
    captionsUrl: safeMediaUrl(item.captions_url ?? item.captionsUrl),
    frames,
    transcript: transcript.length ? transcript : fallbackTranscript,
    checklist,
    mission: cleanText(item.mission, item.summary || "Повторите безопасный рабочий маршрут по шагам.", 500),
    deliverable: cleanText(item.deliverable, fallbackDeliverable, 500),
    practice,
    audience: normalizeAudience(item.audience ?? item.tags, id),
  };
}

export function normalizeInteractiveWalkthroughs(raw) {
  const nestedSources = [
    raw?.interactive_walkthroughs,
    raw?.interactiveWalkthroughs,
    raw?.content?.interactive_walkthroughs,
    raw?.content?.interactiveWalkthroughs,
  ];
  const source = Array.isArray(raw)
    ? raw
    : nestedSources.find((candidate) => Array.isArray(candidate)) || [];
  const seen = new Set();
  const normalized = [];
  for (const [index, candidate] of source.slice(0, MAX_WALKTHROUGHS).entries()) {
    const walkthrough = normalizeWalkthrough(candidate, index);
    if (!walkthrough || seen.has(walkthrough.id)) continue;
    seen.add(walkthrough.id);
    normalized.push(walkthrough);
  }
  return deepFreeze(normalized);
}

export function trainingInteractiveMarkup(courseCode, walkthroughs) {
  const safeCourseCode = cleanId(courseCode, "course");
  const items = normalizeInteractiveWalkthroughs(walkthroughs);
  if (!items.length) return "";
  const headingId = `training-interactive-${safeCourseCode}-title`;
  return `
    <section class="training-interactive" data-training-interactive-course="${escapeHtml(safeCourseCode)}" aria-labelledby="${escapeHtml(headingId)}">
      <header class="training-interactive__header">
        <div>
          <p class="training-interactive__eyebrow">Практика перед рабочим действием</p>
          <h2 id="${escapeHtml(headingId)}">Интерактивные видеоразборы</h2>
        </div>
        <p>Запускайте разбор вручную, двигайтесь по кадрам и отметьте итоговую самопроверку. Практики выбранной роли выделяются автоматически; остальные остаются доступны для повторения.</p>
      </header>
      <div class="training-interactive__course-progress">
        <div>
          <span>Практика курса</span>
          <strong data-training-course-progress-label>0 из ${items.length} завершено</strong>
        </div>
        <div role="progressbar" aria-label="Прогресс интерактивной практики курса" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" data-training-course-progress>
          <span data-training-course-progress-fill style="width:0%"></span>
        </div>
      </div>
      <div class="training-interactive__grid">
        ${items.map((walkthrough, index) => walkthroughMarkup(safeCourseCode, walkthrough, index)).join("")}
      </div>
    </section>
  `;
}

function walkthroughMarkup(courseCode, walkthrough, index) {
  const titleId = `training-walkthrough-${courseCode}-${walkthrough.id}-title`;
  const videoId = `training-walkthrough-${courseCode}-${walkthrough.id}-video`;
  const initialPercent = Math.round(100 / walkthrough.frames.length);
  const practiceRequired = walkthrough.practice ? "true" : "false";
  const video = walkthrough.videoUrl
    ? `
      <video id="${escapeHtml(videoId)}" class="training-walkthrough__video" controls preload="none" playsinline aria-label="Учебное видео: ${escapeHtml(walkthrough.title)}"${walkthrough.posterUrl ? ` poster="${escapeHtml(walkthrough.posterUrl)}"` : ""} data-training-video>
        <source src="${escapeHtml(walkthrough.videoUrl)}" />
        ${walkthrough.captionsUrl ? `<track kind="captions" src="${escapeHtml(walkthrough.captionsUrl)}" srclang="ru" label="Русские субтитры" default />` : ""}
        Ваш браузер не может воспроизвести учебное видео. Используйте текстовый разбор ниже.
      </video>
    `
    : `
      <div class="training-walkthrough__video-placeholder" role="img" aria-label="Учебный покадровый разбор: ${escapeHtml(walkthrough.title)}">
        <span aria-hidden="true">▶</span>
        <div><small>Покадровая репетиция</small><strong>${escapeHtml(formatDuration(walkthrough.durationSeconds))}</strong></div>
      </div>
    `;
  return `
    <article class="training-walkthrough" data-training-walkthrough="${escapeHtml(walkthrough.id)}" data-training-course="${escapeHtml(courseCode)}" data-training-audience="${escapeHtml(walkthrough.audience.join(" "))}" data-training-step="0" data-training-step-count="${walkthrough.frames.length}" data-training-duration-seconds="${walkthrough.durationSeconds}" data-training-playing="false" data-training-mode="watch" data-training-practice-required="${practiceRequired}" data-training-practice-complete="false" data-training-complete="false" aria-labelledby="${escapeHtml(titleId)}">
      <header class="training-walkthrough__heading">
        <div>
          <p class="training-interactive__eyebrow">${escapeHtml(walkthrough.eyebrow)} · разбор ${index + 1}</p>
          <h3 id="${escapeHtml(titleId)}">${escapeHtml(walkthrough.title)}</h3>
          <p>${escapeHtml(walkthrough.summary)}</p>
        </div>
        <div class="training-walkthrough__meta">
          <span class="training-walkthrough__audience-badge" data-training-audience-badge>Практика курса</span>
          <span class="training-walkthrough__status" data-training-status role="status" aria-live="polite">Начните разбор</span>
          <span>${escapeHtml(formatDuration(walkthrough.durationSeconds))}</span>
          ${walkthrough.reviewedAt ? `<span>Проверено ${escapeHtml(walkthrough.reviewedAt)}</span>` : ""}
        </div>
      </header>
      <div class="training-walkthrough__brief" aria-label="Задание тренажёра">
        <div><span>Миссия</span><strong>${escapeHtml(walkthrough.mission)}</strong></div>
        <div><span>Результат</span><strong>${escapeHtml(walkthrough.deliverable)}</strong></div>
      </div>
      ${walkthrough.practice ? modeSwitcherMarkup() : ""}
      <div class="training-walkthrough__mode-panel" data-training-mode-panel="watch">
        <div class="training-walkthrough__stage">
          <div class="training-walkthrough__media">
            ${video}
            <button class="training-walkthrough__play" type="button" data-action="training-walkthrough-play" aria-pressed="false"${walkthrough.videoUrl ? ` aria-controls="${escapeHtml(videoId)}"` : ""}>
              <span aria-hidden="true">▶</span>
              ${walkthrough.videoUrl ? "Запустить видео" : "Начать покадровый разбор"}
            </button>
          </div>
          <div class="training-walkthrough__frames" aria-live="polite" aria-atomic="true">
            ${walkthrough.frames.map((frame, frameIndex) => frameMarkup(frame, frameIndex)).join("")}
          </div>
        </div>
        <div class="training-walkthrough__progress">
          <div>
            <span>Шаг <strong data-training-current-step>1</strong> из ${walkthrough.frames.length}</span>
            <span data-training-progress-label>${initialPercent}%</span>
          </div>
          <div class="training-walkthrough__progress-track" role="progressbar" aria-label="Прогресс видеоразбора" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${initialPercent}" data-training-progress>
            <span data-training-progress-fill style="width:${initialPercent}%"></span>
          </div>
        </div>
        ${timelineMarkup(walkthrough.frames)}
        <div class="training-walkthrough__actions">
          <button type="button" data-action="training-walkthrough-previous" disabled><span aria-hidden="true">←</span> Назад</button>
          <button type="button" data-action="training-walkthrough-next">Следующий кадр <span aria-hidden="true">→</span></button>
          <button type="button" data-action="training-walkthrough-reset">Повторить разбор</button>
        </div>
        ${transcriptMarkup(walkthrough)}
      </div>
      ${practiceMarkup(courseCode, walkthrough)}
      ${checklistMarkup(courseCode, walkthrough)}
    </article>
  `;
}

function modeSwitcherMarkup() {
  return `
    <div class="training-walkthrough__mode-switcher" role="group" aria-label="Режим интерактивного разбора">
      <button type="button" data-action="training-mode-select" data-training-mode-value="watch" aria-pressed="true">1. Посмотреть разбор</button>
      <button type="button" data-action="training-mode-select" data-training-mode-value="practice" aria-pressed="false">2. Решить ситуацию</button>
    </div>
  `;
}

function timelineMarkup(frames) {
  return `
    <nav class="training-walkthrough__timeline" data-training-timeline aria-label="Кадры видеоразбора. Используйте стрелки влево и вправо для навигации.">
      ${frames.map((frame, index) => `
        <button type="button" data-action="training-walkthrough-jump" data-training-step-target="${index}" aria-label="Кадр ${index + 1}: ${escapeHtml(frame.title)}" aria-current="${index === 0 ? "step" : "false"}">
          <span>${index + 1}</span><small>${escapeHtml(frame.time)}</small>
        </button>
      `).join("")}
    </nav>
  `;
}

function practiceMarkup(courseCode, walkthrough) {
  if (!walkthrough.practice) return "";
  const practiceId = `training-practice-${courseCode}-${walkthrough.id}`;
  const feedbackId = `${practiceId}-feedback`;
  return `
    <section class="training-walkthrough__practice training-walkthrough__mode-panel" data-training-practice data-training-mode-panel="practice" data-training-practice-complete="false" data-training-success-message="${escapeHtml(walkthrough.practice.successMessage)}" aria-labelledby="${escapeHtml(practiceId)}" hidden>
      <p class="training-interactive__eyebrow">Проверка решения</p>
      <h4 id="${escapeHtml(practiceId)}" tabindex="-1">${escapeHtml(walkthrough.practice.prompt)}</h4>
      <div class="training-walkthrough__practice-options" role="radiogroup" aria-labelledby="${escapeHtml(practiceId)}" aria-describedby="${escapeHtml(feedbackId)}">
        ${walkthrough.practice.options.map((option, index) => {
          const optionId = `${practiceId}-${option.id}`;
          return `
            <label for="${escapeHtml(optionId)}">
              <input id="${escapeHtml(optionId)}" type="radio" name="${escapeHtml(practiceId)}-answer" value="${escapeHtml(option.id)}" data-training-practice-option data-training-practice-correct="${option.correct ? "true" : "false"}" data-training-feedback="${escapeHtml(option.feedback)}" />
              <span><i aria-hidden="true">${String.fromCharCode(65 + index)}</i>${escapeHtml(option.label)}</span>
            </label>
          `;
        }).join("")}
      </div>
      <div id="${escapeHtml(feedbackId)}" class="training-walkthrough__practice-feedback" data-training-practice-feedback role="status" aria-live="polite" aria-atomic="true" tabindex="-1">Выберите один вариант — объяснение появится сразу.</div>
    </section>
  `;
}

function frameMarkup(frame, index) {
  return `
    <section class="training-walkthrough__frame" data-training-frame data-training-frame-id="${escapeHtml(frame.id)}" data-training-frame-index="${index}" aria-label="Кадр ${index + 1}: ${escapeHtml(frame.title)}"${index ? ' hidden aria-hidden="true"' : ' aria-hidden="false"'}>
      <div class="training-walkthrough__frame-visual" role="img" aria-label="${escapeHtml(frame.visualLabel)}">
        <span>${escapeHtml(frame.time)}</span>
        <i aria-hidden="true"></i>
        <i aria-hidden="true"></i>
        <i aria-hidden="true"></i>
      </div>
      <div class="training-walkthrough__frame-copy">
        <p class="training-interactive__eyebrow">Кадр ${index + 1}</p>
        <h4>${escapeHtml(frame.title)}</h4>
        <p>${escapeHtml(frame.body)}</p>
        ${frame.cue ? `<div class="training-walkthrough__cue"><span aria-hidden="true">↗</span><strong>${escapeHtml(frame.cue)}</strong></div>` : ""}
      </div>
    </section>
  `;
}

function checklistMarkup(courseCode, walkthrough) {
  if (!walkthrough.checklist.length) return "";
  return `
    <fieldset class="training-walkthrough__checklist">
      <legend>Самопроверка после разбора</legend>
      ${walkthrough.checklist.map((item) => {
        const id = `training-check-${courseCode}-${walkthrough.id}-${item.id}`;
        return `<label for="${escapeHtml(id)}"><input id="${escapeHtml(id)}" type="checkbox" data-training-check="${escapeHtml(item.id)}" /><span>${escapeHtml(item.text)}</span></label>`;
      }).join("")}
    </fieldset>
  `;
}

function transcriptMarkup(walkthrough) {
  return `
    <details class="training-walkthrough__transcript">
      <summary>Открыть текст видеоразбора</summary>
      <ol>
        ${walkthrough.transcript.map((item) => `<li>${item.time ? `<span>${escapeHtml(item.time)}</span>` : ""}<p>${escapeHtml(item.text)}</p></li>`).join("")}
      </ol>
    </details>
  `;
}

function walkthroughRoot(root) {
  if (!root || typeof root.querySelectorAll !== "function") return null;
  if (typeof root.matches === "function" && root.matches("[data-training-walkthrough]")) return root;
  return typeof root.querySelector === "function"
    ? root.querySelector("[data-training-walkthrough]")
    : null;
}

export function setTrainingWalkthroughStep(root, index) {
  const walkthrough = walkthroughRoot(root);
  if (!walkthrough) return -1;
  const frames = Array.from(walkthrough.querySelectorAll("[data-training-frame]"));
  if (!frames.length) return -1;
  const numericIndex = Number.isFinite(Number(index)) ? Math.trunc(Number(index)) : 0;
  const currentIndex = Math.max(0, Math.min(frames.length - 1, numericIndex));
  const percent = Math.round(((currentIndex + 1) / frames.length) * 100);

  stopTrainingWalkthrough(walkthrough);
  frames.forEach((frame, frameIndex) => {
    const active = frameIndex === currentIndex;
    frame.hidden = !active;
    frame.setAttribute?.("aria-hidden", active ? "false" : "true");
  });
  if (walkthrough.dataset) walkthrough.dataset.trainingStep = String(currentIndex);

  const current = walkthrough.querySelector?.("[data-training-current-step]");
  if (current) current.textContent = String(currentIndex + 1);
  const label = walkthrough.querySelector?.("[data-training-progress-label]");
  if (label) label.textContent = `${percent}%`;
  const progress = walkthrough.querySelector?.("[data-training-progress]");
  progress?.setAttribute?.("aria-valuenow", String(percent));
  const fill = walkthrough.querySelector?.("[data-training-progress-fill]");
  if (fill?.style) fill.style.width = `${percent}%`;

  const previous = walkthrough.querySelector?.('[data-action="training-walkthrough-previous"]');
  const next = walkthrough.querySelector?.('[data-action="training-walkthrough-next"]');
  if (previous) previous.disabled = currentIndex === 0;
  if (next) next.disabled = currentIndex === frames.length - 1;
  const timelineButtons = Array.from(walkthrough.querySelectorAll('[data-action="training-walkthrough-jump"]'));
  timelineButtons.forEach((button, buttonIndex) => {
    const active = buttonIndex === currentIndex;
    button.setAttribute?.("aria-current", active ? "step" : "false");
  });
  syncTrainingWalkthroughStatus(walkthrough);
  return currentIndex;
}

export function resetTrainingWalkthroughState(root) {
  const walkthrough = walkthroughRoot(root);
  if (!walkthrough) return { step: -1, complete: false };
  stopTrainingWalkthrough(walkthrough);
  Array.from(walkthrough.querySelectorAll?.("[data-training-check]") || []).forEach((input) => {
    input.checked = false;
  });
  Array.from(walkthrough.querySelectorAll?.("[data-training-practice-option]") || []).forEach((input) => {
    input.checked = false;
    input.setAttribute?.("aria-invalid", "false");
  });
  const practice = walkthrough.querySelector?.("[data-training-practice]");
  if (practice) {
    if (practice.dataset) practice.dataset.trainingPracticeComplete = "false";
    practice.setAttribute?.("aria-invalid", "false");
    const feedback = practice.querySelector?.("[data-training-practice-feedback]");
    if (feedback) {
      feedback.textContent = "Выберите один вариант — объяснение появится сразу.";
      if (feedback.dataset) delete feedback.dataset.trainingFeedbackStatus;
    }
  }
  if (walkthrough.dataset) {
    walkthrough.dataset.trainingPracticeComplete = "false";
    walkthrough.dataset.trainingComplete = "false";
  }
  setTrainingWalkthroughMode(walkthrough, "watch");
  const step = setTrainingWalkthroughStep(walkthrough, 0);
  const status = syncTrainingWalkthroughStatus(walkthrough);
  return { step, complete: status.complete };
}

export function setTrainingWalkthroughMode(root, mode) {
  const walkthrough = walkthroughRoot(root);
  if (!walkthrough) return "watch";
  const hasPractice = Boolean(walkthrough.querySelector?.("[data-training-practice]"));
  const nextMode = mode === "practice" && hasPractice ? "practice" : "watch";
  if (walkthrough.dataset) walkthrough.dataset.trainingMode = nextMode;
  Array.from(walkthrough.querySelectorAll("[data-training-mode-panel]")).forEach((panel) => {
    const active = panel.dataset?.trainingModePanel === nextMode;
    panel.hidden = !active;
    panel.setAttribute?.("aria-hidden", active ? "false" : "true");
  });
  Array.from(walkthrough.querySelectorAll('[data-action="training-mode-select"]')).forEach((button) => {
    const active = button.dataset?.trainingModeValue === nextMode;
    button.setAttribute?.("aria-pressed", active ? "true" : "false");
  });
  return nextMode;
}

export function evaluateTrainingPractice(root, optionId = "") {
  const walkthrough = walkthroughRoot(root);
  const practice = walkthrough?.querySelector?.("[data-training-practice]");
  if (!walkthrough || !practice) {
    return { answered: false, passed: false, selectedId: "" };
  }
  const options = Array.from(practice.querySelectorAll?.("[data-training-practice-option]") || []);
  const requestedId = String(optionId || "");
  if (requestedId) {
    options.forEach((option) => {
      option.checked = String(option.value || "") === requestedId;
    });
  }
  const selected = options.find((option) => option.checked === true) || null;
  const feedback = practice.querySelector?.("[data-training-practice-feedback]");
  if (!selected) {
    if (feedback) {
      feedback.textContent = "Сначала выберите один вариант ответа.";
      if (feedback.dataset) feedback.dataset.trainingFeedbackStatus = "empty";
    }
    practice.setAttribute?.("aria-invalid", "true");
    return { answered: false, passed: false, selectedId: "" };
  }
  const passed = selected.dataset?.trainingPracticeCorrect === "true";
  const selectedId = String(selected.value || "");
  const explanation = passed
    ? String(practice.dataset?.trainingSuccessMessage || selected.dataset?.trainingFeedback || "Верно.")
    : String(selected.dataset?.trainingFeedback || "Попробуйте ещё раз.");
  if (practice.dataset) practice.dataset.trainingPracticeComplete = passed ? "true" : "false";
  if (walkthrough.dataset) walkthrough.dataset.trainingPracticeComplete = passed ? "true" : "false";
  practice.setAttribute?.("aria-invalid", passed ? "false" : "true");
  options.forEach((option) => {
    option.setAttribute?.("aria-invalid", option.checked && !passed ? "true" : "false");
  });
  if (feedback) {
    feedback.textContent = explanation;
    if (feedback.dataset) feedback.dataset.trainingFeedbackStatus = passed ? "success" : "error";
  }
  syncTrainingWalkthroughStatus(walkthrough);
  return { answered: true, passed, selectedId };
}

export function syncTrainingWalkthroughStatus(root) {
  const walkthrough = walkthroughRoot(root);
  if (!walkthrough) {
    return { complete: false, stepComplete: false, checksComplete: false, practiceComplete: false };
  }
  const stepCount = Math.max(1, Number(walkthrough.dataset?.trainingStepCount) || 1);
  const currentStep = Math.max(0, Math.min(stepCount - 1, Number(walkthrough.dataset?.trainingStep) || 0));
  const stepComplete = currentStep === stepCount - 1;
  const checks = Array.from(walkthrough.querySelectorAll?.("[data-training-check]") || []);
  const checksComplete = !checks.length || checks.every((input) => input.checked === true);
  const practiceRequired = walkthrough.dataset?.trainingPracticeRequired === "true";
  const practiceComplete = !practiceRequired || walkthrough.dataset?.trainingPracticeComplete === "true";
  const complete = stepComplete && checksComplete && practiceComplete;
  if (walkthrough.dataset) walkthrough.dataset.trainingComplete = complete ? "true" : "false";
  walkthrough.classList?.toggle?.("is-training-complete", complete);

  const status = walkthrough.querySelector?.("[data-training-status]");
  if (status) {
    status.textContent = complete
      ? "Практика завершена"
      : !stepComplete
        ? `В работе · кадр ${currentStep + 1} из ${stepCount}`
        : !practiceComplete
          ? "Решите практическую ситуацию"
          : "Отметьте пункты самопроверки";
    if (status.dataset) status.dataset.trainingStatusValue = complete ? "complete" : "pending";
  }
  syncTrainingCourseProgress(walkthrough);
  return { complete, stepComplete, checksComplete, practiceComplete };
}

export function syncTrainingCourseProgress(root) {
  const walkthrough = walkthroughRoot(root);
  const course = walkthrough?.closest?.("[data-training-interactive-course]")
    || (root?.matches?.("[data-training-interactive-course]") ? root : null);
  if (!course) return { completed: 0, total: 0, percent: 0 };
  const walkthroughs = Array.from(course.querySelectorAll?.("[data-training-walkthrough]") || []);
  const audience = String(course.dataset?.trainingAudienceSelected || "all");
  const recommended = audience === "all"
    ? walkthroughs
    : walkthroughs.filter((item) => (
      item.dataset?.trainingMasteryRequired === "true"
      || String(item.dataset?.trainingAudience || "").split(/\s+/u).includes(audience)
    ));
  const completed = recommended.filter((item) => item.dataset?.trainingComplete === "true").length;
  const total = recommended.length;
  const completedOverall = walkthroughs.filter((item) => item.dataset?.trainingComplete === "true").length;
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const label = course.querySelector?.("[data-training-course-progress-label]");
  if (label) label.textContent = audience === "all"
    ? `${completedOverall} из ${walkthroughs.length} завершено`
    : `${completed} из ${total} в вашем акценте · ${completedOverall} из ${walkthroughs.length} всего`;
  const progress = course.querySelector?.("[data-training-course-progress]");
  progress?.setAttribute?.("aria-valuenow", String(percent));
  const fill = course.querySelector?.("[data-training-course-progress-fill]");
  if (fill?.style) fill.style.width = `${percent}%`;
  return { completed, total, percent, completedOverall, totalOverall: walkthroughs.length };
}

export function setTrainingAudience(root, audience) {
  const course = root?.matches?.("[data-training-interactive-course]")
    ? root
    : root?.closest?.("[data-training-interactive-course]");
  if (!course) return "all";
  const normalized = TRAINING_AUDIENCES.has(String(audience || "")) ? String(audience) : "all";
  if (course.dataset) course.dataset.trainingAudienceSelected = normalized;
  Array.from(course.querySelectorAll?.('[data-action="training-audience-select"]') || []).forEach((button) => {
    button.setAttribute?.("aria-pressed", button.dataset?.trainingAudienceValue === normalized ? "true" : "false");
  });
  const walkthroughs = Array.from(course.querySelectorAll?.("[data-training-walkthrough]") || []);
  let recommended = 0;
  walkthroughs.forEach((walkthrough) => {
    const audiences = String(walkthrough.dataset?.trainingAudience || "").split(/\s+/u).filter(Boolean);
    const roleMatches = normalized === "all" || audiences.includes(normalized);
    const masteryRequired = walkthrough.dataset?.trainingMasteryRequired === "true";
    const matches = roleMatches || masteryRequired;
    walkthrough.hidden = false;
    walkthrough.setAttribute?.("aria-hidden", "false");
    walkthrough.classList?.toggle?.("is-audience-recommended", matches);
    walkthrough.classList?.toggle?.("is-audience-reference", !matches);
    walkthrough.classList?.toggle?.("is-mastery-required", masteryRequired);
    const badge = walkthrough.querySelector?.("[data-training-audience-badge]");
    if (badge) badge.textContent = masteryRequired
      ? "Обязательная лаборатория курса"
      : matches ? "Ваш практический акцент" : "Дополнительная практика";
    if (matches) recommended += 1;
  });
  const labels = {
    all: "все практические разборы курса",
    self: "разборы для самостоятельной съёмки",
    ai: "разборы для генерации с ИИ",
    publish: "разборы для публикации в соцсетях",
    review: "разборы для проверки качества и рисков",
  };
  const result = course.querySelector?.("[data-training-audience-result]");
  if (result) result.textContent = normalized === "all"
    ? `Показаны ${labels[normalized]}: ${walkthroughs.length}.`
    : `Выделены ${labels[normalized]}: ${recommended} из ${walkthroughs.length}. Остальные разборы доступны как дополнительная практика.`;
  syncTrainingCourseProgress(course);
  return normalized;
}

export function stopTrainingWalkthrough(root) {
  const walkthrough = walkthroughRoot(root);
  if (!walkthrough) return 0;
  const videos = Array.from(walkthrough.querySelectorAll("[data-training-video]"));
  for (const video of videos) {
    if (typeof video.pause === "function") video.pause();
  }
  if (walkthrough.dataset) walkthrough.dataset.trainingPlaying = "false";
  const play = walkthrough.querySelector?.('[data-action="training-walkthrough-play"]');
  play?.setAttribute?.("aria-pressed", "false");
  return videos.length;
}

export function trainingWalkthroughStorageKey(userId, courseCode, walkthroughId) {
  const parts = [userId, courseCode, walkthroughId].map((value) => String(value ?? "").trim());
  if (parts.some((value) => !value)) return null;
  return `${STORAGE_PREFIX}:${parts.map((value) => encodeURIComponent(value)).join(":")}`;
}

export function trainingAudienceStorageKey(userId, courseCode) {
  const parts = [userId, courseCode].map((value) => String(value ?? "").trim());
  if (parts.some((value) => !value)) return null;
  return `${AUDIENCE_STORAGE_PREFIX}:${parts.map((value) => encodeURIComponent(value)).join(":")}`;
}

function formatDuration(durationSeconds) {
  const minutes = Math.max(1, Math.ceil(Number(durationSeconds || 0) / 60));
  return `${minutes} мин`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
