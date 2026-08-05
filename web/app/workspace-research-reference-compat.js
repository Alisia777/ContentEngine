/*
 * ContentEngine Research · reference compatibility bridge.
 *
 * Fixes the user-facing path for public YouTube Shorts references without
 * weakening the learning trust boundary:
 * - canonicalises Shorts / youtu.be / watch URLs to one video identity;
 * - keeps a public competitor as a structural reference candidate only;
 * - requires a narrow learning category key (air_fryer, not electronics);
 * - exposes concrete rejection reasons and a user-triggered retry;
 * - never calls a provider directly and never auto-submits a paid action.
 */

const ROUTE = "/workspace/research";
const YOUTUBE_ID = /^[A-Za-z0-9_-]{6,20}$/u;
const LEARNING_KEY = /^[a-z0-9][a-z0-9_-]{1,79}$/u;
const runtime = { queued: false, bound: new WeakSet() };

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
}

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

export function youtubeVideoId(value) {
  let url;
  try {
    url = new URL(String(value || "").trim());
  } catch {
    return "";
  }
  const host = url.hostname.toLowerCase().replace(/^www\./u, "");
  let candidate = "";
  if (host === "youtu.be") {
    candidate = url.pathname.split("/").filter(Boolean)[0] || "";
  } else if (host === "youtube.com" || host === "m.youtube.com") {
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "shorts" || parts[0] === "embed" || parts[0] === "live") {
      candidate = parts[1] || "";
    } else if (url.pathname === "/watch") {
      candidate = url.searchParams.get("v") || "";
    }
  }
  return YOUTUBE_ID.test(candidate) ? candidate : "";
}

export function canonicalYoutubeUrl(value) {
  const id = youtubeVideoId(value);
  return id ? `https://www.youtube.com/watch?v=${id}` : "";
}

export function sameYoutubeVideo(left, right) {
  const leftId = youtubeVideoId(left);
  return Boolean(leftId && leftId === youtubeVideoId(right));
}

function looksLikeReferenceField(field) {
  const key = `${field.name || ""} ${field.id || ""} ${field.placeholder || ""}`
    .toLocaleLowerCase("ru-RU");
  return /reference|example|source[_ -]?url|референ|пример|ссыл/iu.test(key);
}

function referenceFields(root = document) {
  return qa('input[type="url"], input[type="text"], textarea', root)
    .filter(looksLikeReferenceField);
}

function findReferenceForm(field) {
  return field.closest("form")
    || q("form[data-reference-intelligence]")
    || q("form.product-research-brief-form")
    || q("form", field.closest("section, article, .card") || document);
}

function ensureHidden(form, name, value) {
  let field = q(`input[type="hidden"][name="${CSS.escape(name)}"]`, form);
  if (!field) {
    field = create("input");
    field.type = "hidden";
    field.name = name;
    form.append(field);
  }
  field.value = value;
  return field;
}

function pageText() {
  return String(q("main")?.textContent || document.body.textContent || "")
    .toLocaleLowerCase("ru-RU");
}

export function inferLearningCategoryKey(text) {
  const value = String(text || "").toLocaleLowerCase("ru-RU");
  if (/аэро\s*грил|air\s*[- ]?fryer/iu.test(value)) return "air_fryer";
  return "";
}

function existingLearningKey(form) {
  const field = q(
    '[name="learning_category_key"], [data-learning-category-key], '
      + '[name="contentengine_learning_category_key"]',
    form,
  );
  const value = String(field?.value || field?.dataset?.learningCategoryKey || "")
    .trim()
    .toLowerCase();
  return LEARNING_KEY.test(value) ? value : "";
}

function addStatus(field) {
  const host = field.closest("label, .field, .form-field, .reference-intelligence-input")
    || field.parentElement;
  if (!host) return null;
  let status = q(":scope > .ce-reference-compat-status", host);
  if (!status) {
    status = create("small", "ce-reference-compat-status");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    host.append(status);
  }
  return status;
}

function setStatus(field, message, tone = "info") {
  const status = addStatus(field);
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function prepareField(field, { announce = true } = {}) {
  const raw = String(field.value || "").trim();
  if (!raw) return { changed: false, videoId: "", canonical: "", key: "" };
  const videoId = youtubeVideoId(raw);
  if (!videoId) return { changed: false, videoId: "", canonical: "", key: "" };

  const canonical = canonicalYoutubeUrl(raw);
  const changed = raw !== canonical;
  if (changed) {
    field.value = canonical;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const form = findReferenceForm(field);
  let key = form ? existingLearningKey(form) : "";
  if (!key) key = inferLearningCategoryKey(`${pageText()} ${field.value}`);
  if (form) {
    ensureHidden(form, "contentengine_reference_source_kind", "public_competitor");
    ensureHidden(form, "contentengine_reference_intent", "structural_reference");
    ensureHidden(form, "contentengine_reference_learning_mode", "candidate_after_qa");
    ensureHidden(form, "contentengine_reference_video_id", videoId);
    ensureHidden(form, "contentengine_reference_canonical_url", canonical);
    if (key) ensureHidden(form, "learning_category_key", key);
  }

  if (announce) {
    if (key) {
      setStatus(
        field,
        `YouTube Shorts распознан. Канонический ролик ${videoId}; учебная категория: ${key}. `
          + "Будет использована только механика ролика, без копирования чужого бренда, лица, музыки и текста.",
        "ok",
      );
    } else {
      setStatus(
        field,
        `YouTube Shorts распознан (${videoId}), но нужна узкая учебная категория. `
          + "Для аэрогриля укажите air_fryer, а не общую electronics.",
        "warning",
      );
    }
  }
  return { changed, videoId, canonical, key };
}

function prepareForm(form) {
  let found = false;
  let missingKey = false;
  referenceFields(form).forEach((field) => {
    const result = prepareField(field);
    if (!result.videoId) return;
    found = true;
    if (!result.key) missingKey = true;
  });
  return { found, missingKey };
}

function resultPanels() {
  return qa(
    '[data-reference-result], .reference-intelligence-result, '
      + '.product-research-reference-result, .creator-reference-result',
  );
}

function rejectionReason(panel) {
  const text = String(panel.textContent || "").toLocaleLowerCase("ru-RU");
  if (!/результат нельзя использовать|нельзя применить|not usable|cannot apply/iu.test(text)) {
    return "";
  }
  if (/citation|цитат|источник не подтвержден|не подтверждена ссылка/iu.test(text)) {
    return "Ссылка Shorts и ссылка источника могли быть одним роликом в разных форматах. Повторите анализ после канонизации URL.";
  }
  if (/категор|category|electronics/iu.test(text)) {
    return "Общая категория electronics недостаточна для обучения. Для этого товара используйте learning_category_key = air_fryer.";
  }
  if (/прав|rights|license|лиценз/iu.test(text)) {
    return "Публичный ролик конкурента нельзя активировать как готовый winner. Его можно сохранить как структурный кандидат после QA.";
  }
  return "Проверьте каноническую ссылку, узкую категорию air_fryer и режим «структурный кандидат после QA».";
}

function enhanceRejectedResults() {
  resultPanels().forEach((panel) => {
    if (panel.dataset.ceReferenceCompat === "true") return;
    const reason = rejectionReason(panel);
    if (!reason) return;
    panel.dataset.ceReferenceCompat = "true";
    const note = create("aside", "ce-reference-compat-recovery");
    note.append(
      create("strong", "", "Почему пример заблокирован"),
      create("p", "", reason),
    );
    const retry = create("button", "", "Подготовить ссылку и повторить");
    retry.type = "button";
    retry.addEventListener("click", () => {
      const field = referenceFields().find((candidate) => youtubeVideoId(candidate.value));
      if (!field) {
        note.append(create("small", "", "Поле со ссылкой YouTube не найдено. Вставьте Shorts ещё раз."));
        return;
      }
      const result = prepareField(field);
      if (!result.key) {
        note.append(create("small", "", "Для аэрогриля сначала задайте учебную категорию air_fryer."));
        field.focus({ preventScroll: false });
        return;
      }
      const form = findReferenceForm(field);
      const submit = q('button[type="submit"], input[type="submit"]', form);
      if (submit instanceof HTMLElement) {
        submit.focus({ preventScroll: false });
        setStatus(field, "Ссылка подготовлена. Нажмите штатную кнопку анализа ещё раз.", "ok");
      }
    });
    note.append(retry);
    panel.append(note);
  });
}

function bindForm(form) {
  if (runtime.bound.has(form)) return;
  runtime.bound.add(form);
  form.addEventListener("submit", (event) => {
    const state = prepareForm(form);
    if (state.found && state.missingKey) {
      event.preventDefault();
      event.stopImmediatePropagation();
      const field = referenceFields(form).find((candidate) => youtubeVideoId(candidate.value));
      setStatus(
        field,
        "Запуск остановлен: задайте узкую учебную категорию. Для аэрогриля — air_fryer.",
        "error",
      );
      field?.focus?.({ preventScroll: false });
    }
  }, true);
  form.addEventListener("input", (event) => {
    const field = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement
      ? event.target
      : null;
    if (field && looksLikeReferenceField(field) && youtubeVideoId(field.value)) {
      prepareField(field, { announce: false });
    }
  });
}

function mount() {
  if (routePath() !== ROUTE) return;
  referenceFields().forEach((field) => {
    const form = findReferenceForm(field);
    if (form) bindForm(form);
    if (youtubeVideoId(field.value)) prepareField(field);
  });
  enhanceRejectedResults();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
window.addEventListener("pageshow", schedule, { passive: true });
document.addEventListener("input", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineResearchReferenceCompat = Object.freeze({
  canonicalYoutubeUrl,
  youtubeVideoId,
  sameYoutubeVideo,
  inferLearningCategoryKey,
  schedule,
});
