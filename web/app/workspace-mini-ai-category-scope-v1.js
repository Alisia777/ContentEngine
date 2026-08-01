/*
 * Keeps the mini-AI learning category separate from broad compliance labels.
 *
 * A compliance category such as "electronics" is useful for legal/QA rules but
 * is too broad for performance learning. This adapter remembers a narrow key
 * per SKU/platform/model and prevents the desk from silently falling back to
 * the native compliance category.
 */

const ROUTE = "/workspace/generation";
const FORM_SELECTOR = "#mock-batch-form";
const DESK_SELECTOR = "[data-mini-ai-desk-v3]";
const INPUT_SELECTOR = '[name="mini_ai_learning_category"]';
const POINTER_KEY = "contentengine.mini-ai-learning-category-pointer.v1";
const BROAD_CATEGORIES = new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
let queued = false;
let observer = null;

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function normalize(value) {
  return String(value || "")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("ru-RU");
}

function readPointers() {
  try {
    const value = JSON.parse(window.localStorage.getItem(POINTER_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function writePointers(value) {
  try {
    window.localStorage.setItem(POINTER_KEY, JSON.stringify(value));
  } catch {
    // The operator can still enter the category for the current page.
  }
}

function baseScope(form) {
  return [
    String(
      window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
        || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
        || window.location.host,
    ).trim(),
    String(form?.elements?.sku?.value || "").trim(),
    String(form?.elements?.platform?.value || "").trim().toLowerCase(),
    String(form?.elements?.generation_mode?.value || "").trim(),
  ].join("|");
}

function validCategory(value) {
  const category = normalize(value);
  return (
    /^[a-z0-9][a-z0-9_-]{2,119}$/u.test(category)
    && !BROAD_CATEGORIES.has(category)
  );
}

function warningFor(input) {
  const field = input.closest(".mini-ai-field");
  if (!field) return null;
  let warning = field.querySelector("[data-mini-ai-category-warning]");
  if (!warning) {
    warning = document.createElement("small");
    warning.className = "mini-ai-field__hint mini-ai-category-warning";
    warning.dataset.miniAiCategoryWarning = "true";
    warning.hidden = true;
    field.append(warning);
  }
  return warning;
}

function rejectBroadOrEmpty(input, rawValue) {
  const category = normalize(rawValue);
  const warning = warningFor(input);
  if (!category) {
    // A single whitespace is visually empty but truthy before the desk trims
    // it, so its fallback to the broad native compliance category is disabled.
    input.value = " ";
    input.setCustomValidity("Укажите узкую категорию обучения.");
    if (warning) {
      warning.textContent = "Укажите отдельную узкую категорию, например car_audio_amplifier.";
      warning.hidden = false;
    }
    return "";
  }
  if (BROAD_CATEGORIES.has(category)) {
    input.value = " ";
    input.setCustomValidity("Compliance-категория слишком широка для обучения.");
    if (warning) {
      warning.textContent = `«${category}» слишком широко. Нужен ключ уровня товара: car_audio_amplifier, hair_styling или pet_care.`;
      warning.hidden = false;
    }
    return "";
  }
  if (!validCategory(category)) {
    input.setCustomValidity("Используйте 3–120 латинских символов, цифр, - или _.");
    if (warning) {
      warning.textContent = "Формат: 3–120 латинских символов, цифр, дефисов или подчёркиваний.";
      warning.hidden = false;
    }
    return "";
  }
  input.value = category;
  input.setCustomValidity("");
  if (warning) warning.hidden = true;
  return category;
}

function persistCurrent(form, input) {
  const category = rejectBroadOrEmpty(input, input.value);
  if (!category) return;
  const pointers = readPointers();
  pointers[baseScope(form)] = category;
  writePointers(pointers);
}

function restore(form, input) {
  const pointers = readPointers();
  const remembered = normalize(pointers[baseScope(form)] || "");
  const current = normalize(input.value);
  const candidate = validCategory(remembered)
    ? remembered
    : validCategory(current)
      ? current
      : "";
  rejectBroadOrEmpty(input, candidate || " ");
  if (candidate) {
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function bind(form, input) {
  if (input.dataset.miniAiCategoryScopeBound === "true") return;
  input.dataset.miniAiCategoryScopeBound = "true";
  input.addEventListener("input", () => persistCurrent(form, input), { passive: true });
  input.addEventListener("change", () => persistCurrent(form, input), { passive: true });
  form.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
    if (!["sku", "platform", "generation_mode"].includes(target.name)) return;
    const current = normalize(input.value);
    if (validCategory(current)) {
      const pointers = readPointers();
      pointers[baseScope(form)] = current;
      writePointers(pointers);
    } else {
      restore(form, input);
    }
  }, { passive: true });
  restore(form, input);
  // The desk may have rendered once with the broad native category. Trigger one
  // idempotent route refresh after the narrow pointer is restored.
  window.queueMicrotask(() => {
    window.dispatchEvent(new CustomEvent("contentengine:v4-route-ready", {
      detail: Object.freeze({
        route: ROUTE,
        source: "mini-ai-category-scope",
      }),
    }));
  });
}

function mount() {
  if (routePath() !== ROUTE) return;
  const form = document.querySelector(FORM_SELECTOR);
  const desk = document.querySelector(DESK_SELECTOR);
  const input = desk?.querySelector(INPUT_SELECTOR);
  if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLInputElement)) return;
  bind(form, input);
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    mount();
  });
}

function start() {
  schedule();
  if (observer) return;
  observer = new MutationObserver((records) => {
    if (records.some((record) => [...record.addedNodes].some((item) =>
      item instanceof Element
      && (item.matches(DESK_SELECTOR) || item.querySelector?.(DESK_SELECTOR))
    ))) schedule();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}
