/*
 * ContentEngine Research reference recovery.
 *
 * Fixes a narrow but common user failure: YouTube can cite the same video as
 * /shorts/, /watch?v= or youtu.be. Reference verification must receive one
 * canonical identity before the existing analysis action runs. The module does
 * not call an API, submit a form automatically, bypass a safety decision or
 * mark a competitor video as approved training data.
 */

const ROUTE = "/workspace/research";
const BUILD = "20260805.reference-recovery.1";
const YOUTUBE_ID = /^[A-Za-z0-9_-]{6,20}$/u;
const timers = new Set();
let queued = false;

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

function youtubeVideoId(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  const host = url.hostname.toLowerCase().replace(/^www\./u, "");
  let candidate = "";
  if (host === "youtu.be") {
    candidate = url.pathname.split("/").filter(Boolean)[0] || "";
  } else if (
    host === "youtube.com"
    || host === "m.youtube.com"
    || host === "music.youtube.com"
  ) {
    candidate = url.searchParams.get("v") || "";
    if (!candidate) {
      const parts = url.pathname.split("/").filter(Boolean);
      if (["shorts", "embed", "live"].includes(parts[0] || "")) {
        candidate = parts[1] || "";
      }
    }
  }
  candidate = candidate.trim();
  return YOUTUBE_ID.test(candidate) ? candidate : "";
}

function canonicalReferenceUrl(value) {
  const raw = String(value || "").trim();
  const videoId = youtubeVideoId(raw);
  if (videoId) return `https://www.youtube.com/watch?v=${videoId}`;
  let url;
  try {
    url = new URL(raw);
  } catch {
    return raw;
  }
  for (const key of [...url.searchParams.keys()]) {
    if (/^(utm_|fbclid$|gclid$|igshid$|si$|feature$)/iu.test(key)) {
      url.searchParams.delete(key);
    }
  }
  url.hash = "";
  return url.toString();
}

function canonicalizeText(value) {
  return String(value || "").replace(
    /https?:\/\/(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:shorts|watch|embed|live)\/??[^\s<>'\"]*|youtu\.be\/[^\s<>'\"]+)/giu,
    (match) => canonicalReferenceUrl(match),
  );
}

function referenceFields(root = document) {
  return qa("input[type='url'], textarea, input[type='text']", root).filter((field) => {
    const context = `${field.name || ""} ${field.id || ""} ${field.placeholder || ""} ${field.getAttribute("aria-label") || ""}`
      .toLocaleLowerCase("ru-RU");
    return /url|link|ссыл|референс|пример|source/iu.test(context)
      || /youtube\.com\/shorts|youtu\.be\//iu.test(String(field.value || ""));
  });
}

function normalizeField(field) {
  if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement)) return false;
  const next = canonicalizeText(field.value);
  if (next === field.value) return false;
  field.value = next;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  field.dataset.ceReferenceCanonicalized = "true";
  return true;
}

function researchForms() {
  return qa("form").filter((form) => {
    const context = `${form.id || ""} ${form.className || ""} ${form.textContent || ""}`
      .toLocaleLowerCase("ru-RU");
    return /research|исслед|референс|пример|визуальн/iu.test(context);
  });
}

function broadCategory(form) {
  const field = q("[name='product_category'], [name='category'], [data-product-category]", form);
  return String(field?.value || field?.dataset?.productCategory || "")
    .trim()
    .toLowerCase();
}

function ensureLearningCategory(form) {
  let hidden = q("input[name='learning_category_key']", form);
  if (!hidden) {
    hidden = create("input");
    hidden.type = "hidden";
    hidden.name = "learning_category_key";
    form.append(hidden);
  }
  const saved = String(form.dataset.ceLearningCategory || hidden.value || "").trim();
  const broad = broadCategory(form);
  if (!saved || saved === "electronics") {
    hidden.value = broad === "electronics" || !broad ? "air_fryer" : saved;
  }
  form.dataset.ceLearningCategory = hidden.value;
  return hidden;
}

function ensureCategoryControl(form) {
  if (q(".ce-reference-category", form)) return;
  const reference = referenceFields(form)[0];
  if (!reference) return;
  const hidden = ensureLearningCategory(form);
  const label = create("label", "ce-reference-category");
  label.append(create("span", "", "Категория обучения"));
  const select = create("select");
  select.setAttribute("aria-label", "Узкая категория обучения");
  [
    ["air_fryer", "Аэрогрили"],
    ["hair_dryer", "Фены"],
    ["robot_vacuum", "Роботы-пылесосы"],
    ["other_electronics", "Другая электроника"],
  ].forEach(([value, labelText]) => {
    const option = create("option", "", labelText);
    option.value = value;
    select.append(option);
  });
  select.value = hidden.value || "air_fryer";
  select.addEventListener("change", () => {
    hidden.value = select.value;
    form.dataset.ceLearningCategory = select.value;
  });
  label.append(select, create(
    "small",
    "",
    "Электроника слишком широкая для обучения. Пример аэрогриля сохраняется в отдельный контур air_fryer.",
  ));
  reference.closest("label, .field, .form-field, .input-group")?.after(label)
    || reference.after(label);
}

function analysisButtons(form) {
  return qa("button, [role='button']", form).filter((button) => {
    const text = String(button.textContent || "").trim();
    return /разобрать|анализ|проверить|исследовать|запустить/iu.test(text)
      && !/сохранить|утвердить|опубликовать/iu.test(text);
  });
}

function retryAnalysis(form) {
  const changed = referenceFields(form).some(normalizeField);
  ensureLearningCategory(form);
  const button = analysisButtons(form)[0];
  if (!button || button.disabled) return;
  if (!changed) {
    referenceFields(form).forEach((field) => {
      field.dataset.ceReferenceCanonicalized = "true";
    });
  }
  button.click();
}

function unusableResults() {
  return qa("section, article, aside, div").filter((node) => {
    if (node.children.length > 30) return false;
    return /результат нельзя использовать/iu.test(String(node.textContent || ""));
  });
}

function ensureRecovery(result) {
  if (q(":scope > .ce-reference-recovery", result)) return;
  const form = result.closest("form") || researchForms()[0];
  if (!form) return;
  const youtube = referenceFields(form).some((field) => youtubeVideoId(field.value));
  if (!youtube) return;
  const recovery = create("aside", "ce-reference-recovery");
  recovery.append(
    create("strong", "", "Повторить с канонической ссылкой YouTube"),
    create(
      "p",
      "",
      "Shorts и watch — один ролик, но прежняя проверка могла считать их разными источниками. Ссылка будет приведена к watch?v= без обхода остальных проверок.",
    ),
  );
  const button = create("button", "", "Исправить ссылку и повторить анализ");
  button.type = "button";
  button.addEventListener("click", () => retryAnalysis(form));
  recovery.append(button);
  result.append(recovery);
}

function bindForm(form) {
  if (form.dataset.ceReferenceRecoveryBound === "true") return;
  form.dataset.ceReferenceRecoveryBound = "true";
  ensureCategoryControl(form);
  referenceFields(form).forEach((field) => {
    field.addEventListener("paste", () => window.setTimeout(() => normalizeField(field), 0));
    field.addEventListener("change", () => normalizeField(field));
    normalizeField(field);
  });
  form.addEventListener("submit", () => {
    referenceFields(form).forEach(normalizeField);
    ensureLearningCategory(form);
  }, true);
  analysisButtons(form).forEach((button) => {
    button.addEventListener("click", () => {
      referenceFields(form).forEach(normalizeField);
      ensureLearningCategory(form);
    }, true);
  });
}

function mount() {
  if (routePath() !== ROUTE) return;
  researchForms().forEach(bindForm);
  unusableResults().forEach(ensureRecovery);
}

function clearTimers() {
  timers.forEach((timer) => window.clearTimeout(timer));
  timers.clear();
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    mount();
  });
  clearTimers();
  [80, 240, 600, 1200].forEach((delay) => {
    const timer = window.setTimeout(() => {
      timers.delete(timer);
      mount();
    }, delay);
    timers.add(timer);
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
window.addEventListener("pageshow", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineResearchReferenceRecovery = Object.freeze({
  build: BUILD,
  youtubeVideoId,
  canonicalReferenceUrl,
  canonicalizeText,
  schedule,
});
