const RESEARCH_PREFILL_GATE = "research_prefill";
const RESEARCH_PREFILL_NOTICE_ID = "product-research-prefill-notice";

const RESEARCH_PREFILL_TEXT_FIELDS = Object.freeze({
  product_name: 180,
  sku: 120,
  category_name: 160,
  research_focus: 200,
  marketplace_url: 2048,
  competitor_references: 650,
  known_facts: 500,
});

const RESEARCH_PREFILL_CATEGORIES = new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);

const RESEARCH_PREFILL_PLATFORMS = new Set([
  "instagram",
  "youtube",
  "vk",
  "wildberries",
  "ozon",
]);

const RESEARCH_PREFILL_OBJECTIVES = new Set([
  "conversion",
  "awareness",
  "ugc",
  "education",
]);

function boundedText(value, maximumLength) {
  return String(value || "").trim().slice(0, maximumLength);
}

function hashParameters(hash) {
  const value = String(hash || "");
  const queryIndex = value.indexOf("?");
  if (queryIndex < 0) return null;
  const query = value.slice(queryIndex + 1).split("#", 1)[0];
  return new URLSearchParams(query);
}

export function isYoutubeResearchReference(value) {
  try {
    const url = new URL(String(value || ""));
    if (url.protocol !== "https:") return false;
    const hostname = url.hostname.toLowerCase();
    if (hostname === "youtu.be") return Boolean(url.pathname.slice(1));
    if (!["youtube.com", "www.youtube.com", "m.youtube.com"].includes(hostname)) {
      return false;
    }
    return url.pathname.startsWith("/shorts/")
      || url.pathname === "/watch"
      || url.pathname.startsWith("/embed/")
      || url.pathname.startsWith("/live/");
  } catch {
    return false;
  }
}

export function researchPrefillFromHash(hash = "") {
  const params = hashParameters(hash);
  if (!params || params.get(RESEARCH_PREFILL_GATE) !== "1") return null;

  const values = {};
  Object.entries(RESEARCH_PREFILL_TEXT_FIELDS).forEach(([name, maximumLength]) => {
    const value = boundedText(params.get(name), maximumLength);
    if (value) values[name] = value;
  });

  if (
    values.marketplace_url
    && !values.marketplace_url.toLowerCase().startsWith("https://")
  ) {
    delete values.marketplace_url;
  }

  const productCategory = boundedText(params.get("product_category"), 32).toLowerCase();
  if (RESEARCH_PREFILL_CATEGORIES.has(productCategory)) {
    values.product_category = productCategory;
  }

  const objective = boundedText(params.get("objective"), 32).toLowerCase();
  if (RESEARCH_PREFILL_OBJECTIVES.has(objective)) {
    values.objective = objective;
  }

  const platforms = [
    ...params.getAll("platform"),
    ...params.getAll("platforms").flatMap((value) => String(value || "").split(",")),
  ].map((value) => boundedText(value, 32).toLowerCase())
    .filter((value) => RESEARCH_PREFILL_PLATFORMS.has(value));
  if (platforms.length) values.platforms = [...new Set(platforms)].slice(0, 8);

  return values;
}

function dispatchControlEvents(control) {
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
}

function setNamedValue(form, name, value) {
  const control = form.elements.namedItem(name);
  if (!control || typeof control.value === "undefined") return false;
  control.value = value;
  dispatchControlEvents(control);
  return true;
}

function setPlatforms(form, platforms) {
  const selected = new Set(platforms);
  form.querySelectorAll('input[name="platforms"]').forEach((control) => {
    control.checked = selected.has(control.value);
    dispatchControlEvents(control);
  });
}

function requireFreshPaidConfirmation(form) {
  ["paid_analysis_ack", "human_review_ack"].forEach((name) => {
    const control = form.elements.namedItem(name);
    if (!control || typeof control.checked !== "boolean") return;
    control.checked = false;
    dispatchControlEvents(control);
  });
}

function addYoutubeReferenceNotice(form) {
  if (form.querySelector(`#${RESEARCH_PREFILL_NOTICE_ID}`)) return;
  const notice = document.createElement("div");
  notice.id = RESEARCH_PREFILL_NOTICE_ID;
  notice.className = "alert alert-info product-research-reference-notice";
  notice.setAttribute("role", "status");

  const icon = document.createElement("strong");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "▶";

  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = "YouTube Shorts добавлен как публичный референс. ";
  copy.append(title, document.createTextNode(
    "Исследование разберёт хук, демонстрацию, структуру кадров и доказательства. После завершения выводы появятся во входящих выбранной категории ИИ-центра.",
  ));
  notice.append(icon, copy);

  const heading = form.querySelector(".product-research-card-heading");
  if (heading) heading.insertAdjacentElement("afterend", notice);
  else form.prepend(notice);
}

function relabelReferenceField(form, youtubeReference) {
  const control = form.elements.namedItem("marketplace_url");
  const label = control?.closest?.("label");
  const title = label?.querySelector?.(":scope > span");
  const hint = label?.querySelector?.("small");
  if (!title) return;
  title.textContent = youtubeReference
    ? "Публичный YouTube Shorts / ссылка на товар"
    : "Публичная ссылка на товар или референс";
  if (hint) {
    hint.textContent = "Разрешены публичные HTTPS-ссылки: YouTube Shorts/watch/youtu.be, карточка товара или страница конкурента. Ссылки из личных кабинетов сюда не вставляйте.";
  }
}

export function applyResearchPrefill({
  hash = typeof window !== "undefined" ? window.location.hash : "",
  root = typeof document !== "undefined" ? document : null,
} = {}) {
  if (!root) return false;
  const values = researchPrefillFromHash(hash);
  if (!values) return false;
  const form = root.querySelector("#product-research-start-form");
  if (!form) return false;

  const signature = String(hash || "");
  if (form.dataset.researchPrefillSignature === signature) return true;

  Object.entries(RESEARCH_PREFILL_TEXT_FIELDS).forEach(([name]) => {
    if (Object.prototype.hasOwnProperty.call(values, name)) {
      setNamedValue(form, name, values[name]);
    }
  });
  if (values.product_category) {
    setNamedValue(form, "product_category", values.product_category);
  }
  if (values.objective) setNamedValue(form, "objective", values.objective);
  if (values.platforms?.length) setPlatforms(form, values.platforms);

  const youtubeReference = isYoutubeResearchReference(values.marketplace_url);
  relabelReferenceField(form, youtubeReference);
  if (youtubeReference) addYoutubeReferenceNotice(form);

  requireFreshPaidConfirmation(form);
  form.dataset.researchPrefillSignature = signature;
  return true;
}

let activeObserver = null;
let observerTimeout = 0;

function scheduleResearchPrefill() {
  if (typeof document === "undefined") return;
  activeObserver?.disconnect();
  if (observerTimeout) window.clearTimeout(observerTimeout);

  if (applyResearchPrefill()) return;
  activeObserver = new MutationObserver(() => {
    if (!applyResearchPrefill()) return;
    activeObserver?.disconnect();
    activeObserver = null;
    if (observerTimeout) window.clearTimeout(observerTimeout);
    observerTimeout = 0;
  });
  activeObserver.observe(document.documentElement, { childList: true, subtree: true });
  observerTimeout = window.setTimeout(() => {
    activeObserver?.disconnect();
    activeObserver = null;
    observerTimeout = 0;
  }, 20_000);
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.addEventListener("hashchange", scheduleResearchPrefill);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleResearchPrefill, { once: true });
  } else {
    scheduleResearchPrefill();
  }
}
