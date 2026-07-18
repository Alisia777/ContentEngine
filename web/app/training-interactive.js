const MAX_WALKTHROUGHS = 8;
const MAX_FRAMES = 8;
const MAX_TRANSCRIPT_ITEMS = 16;
const MAX_CHECKLIST_ITEMS = 8;
const STORAGE_PREFIX = "contentengine.training-walkthrough.v1";

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

function normalizeWalkthrough(item, index) {
  if (!item || typeof item !== "object") return null;
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
  const checklist = (Array.isArray(item.checklist) ? item.checklist : [])
    .slice(0, MAX_CHECKLIST_ITEMS)
    .map((entry) => cleanText(entry, "", 300))
    .filter(Boolean);

  return {
    id: cleanId(item.id, `walkthrough_${index + 1}`),
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
        <p>Запускайте разбор вручную, двигайтесь по кадрам и отметьте итоговую самопроверку. Это учебная репетиция без рабочих действий и списаний.</p>
      </header>
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
    <article class="training-walkthrough" data-training-walkthrough="${escapeHtml(walkthrough.id)}" data-training-course="${escapeHtml(courseCode)}" data-training-step="0" data-training-step-count="${walkthrough.frames.length}" data-training-duration-seconds="${walkthrough.durationSeconds}" data-training-playing="false" aria-labelledby="${escapeHtml(titleId)}">
      <header class="training-walkthrough__heading">
        <div>
          <p class="training-interactive__eyebrow">${escapeHtml(walkthrough.eyebrow)} · разбор ${index + 1}</p>
          <h3 id="${escapeHtml(titleId)}">${escapeHtml(walkthrough.title)}</h3>
          <p>${escapeHtml(walkthrough.summary)}</p>
        </div>
        <div class="training-walkthrough__meta">
          <span>${escapeHtml(formatDuration(walkthrough.durationSeconds))}</span>
          ${walkthrough.reviewedAt ? `<span>Проверено ${escapeHtml(walkthrough.reviewedAt)}</span>` : ""}
        </div>
      </header>
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
      <div class="training-walkthrough__actions">
        <button type="button" data-action="training-walkthrough-previous" disabled><span aria-hidden="true">←</span> Назад</button>
        <button type="button" data-action="training-walkthrough-next">Следующий кадр <span aria-hidden="true">→</span></button>
        <button type="button" data-action="training-walkthrough-reset">Начать заново</button>
      </div>
      ${checklistMarkup(courseCode, walkthrough)}
      ${transcriptMarkup(walkthrough)}
    </article>
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
      ${walkthrough.checklist.map((item, index) => {
        const id = `training-check-${courseCode}-${walkthrough.id}-${index + 1}`;
        return `<label for="${escapeHtml(id)}"><input id="${escapeHtml(id)}" type="checkbox" data-training-check="${index}" /><span>${escapeHtml(item)}</span></label>`;
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
  return currentIndex;
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
