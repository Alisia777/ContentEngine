/*
 * ContentEngine generation learning advisor.
 *
 * Fixes the misleading "8 seconds is the model" behaviour without calling an
 * API or starting a generation. It exposes supported durations and a bounded
 * cold-start experiment. A learned plan is displayed only when another trusted
 * application layer places a server-issued policy hash on the exact form; this
 * advisor itself is never a payment or provider authority.
 */

const GENERATION_ROUTE = "/workspace/generation";
const SELECTOR = "#mock-batch-form";
const POLICY_HASH = /^[0-9a-f]{64}$/u;
const MODE_SPECS = Object.freeze({
  real_gen4: Object.freeze({
    label: "Gen‑4 Turbo",
    allowed: Object.freeze([2, 5, 8, 10]),
    coldStart: Object.freeze([5, 8]),
  }),
  real_seedance: Object.freeze({
    label: "Seedance 2 Fast",
    allowed: Object.freeze([4, 8, 12, 15]),
    coldStart: Object.freeze([8, 12]),
  }),
});

let queued = false;
let observedForm = null;
let observer = null;

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function element(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function modelSpec(form) {
  const mode = String(form.elements.generation_mode?.value || "").trim();
  return MODE_SPECS[mode] || null;
}

function readServerPolicyHint(form) {
  const raw = String(form.dataset.generationDurationPolicy || "").trim();
  if (!raw || raw.length > 4_000) return null;
  try {
    const value = JSON.parse(raw);
    if (
      !value
      || typeof value !== "object"
      || Array.isArray(value)
      || value.source !== "creator_generation_learning_policy"
      || !POLICY_HASH.test(String(value.policy_hash || ""))
      || !Array.isArray(value.arms)
    ) return null;
    const spec = modelSpec(form);
    if (!spec) return null;
    const arms = value.arms
      .map((arm) => ({
        seconds: Number(arm?.seconds),
        allocation: Number(arm?.allocation),
      }))
      .filter((arm) =>
        spec.allowed.includes(arm.seconds)
        && Number.isFinite(arm.allocation)
        && arm.allocation > 0
        && arm.allocation <= 1
      );
    if (
      arms.length < 1
      || arms.length > 4
      || new Set(arms.map((arm) => arm.seconds)).size !== arms.length
      || Math.abs(arms.reduce((sum, arm) => sum + arm.allocation, 0) - 1) > 0.001
    ) return null;
    return Object.freeze({
      mode: value.mode === "exploit" ? "exploit" : "explore",
      scope: String(value.scope || "").slice(0, 80),
      policyHash: String(value.policy_hash),
      arms: Object.freeze(arms),
    });
  } catch {
    return null;
  }
}

function dispatchSelection(control) {
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
}

function buildPanel(form) {
  const existing = form.querySelector("[data-generation-duration-advisor]");
  if (existing) return existing;
  const durationField = form.querySelector("#generation-duration-field");
  if (!durationField) return null;

  const panel = element("section", "generation-duration-advisor");
  panel.dataset.generationDurationAdvisor = "true";
  panel.setAttribute("aria-live", "polite");

  const header = element("div", "generation-duration-advisor__header");
  const copy = element("div");
  copy.append(
    element("strong", "", "Длительность — эксперимент, а не фиксированные 8 секунд"),
    element(
      "small",
      "",
      "Мини‑ИИ сравнивает только разрешённые длительности внутри той же категории, SKU и площадки.",
    ),
  );
  const state = element("span", "generation-duration-advisor__state", "Ожидаем контекст");
  state.dataset.durationAdvisorState = "true";
  header.append(copy, state);

  const message = element("p", "generation-duration-advisor__message");
  message.dataset.durationAdvisorMessage = "true";
  const arms = element("div", "generation-duration-advisor__arms");
  arms.dataset.durationAdvisorArms = "true";
  const guard = element(
    "small",
    "generation-duration-advisor__guard",
    "Чужая категория не передаёт winner. Без matched evidence остаются control и две ограниченные гипотезы.",
  );
  panel.append(header, message, arms, guard);

  // The duration field is a <label>. Interactive advisor buttons must be its
  // sibling, not invalid nested controls inside that label.
  durationField.after(panel);

  panel.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("button[data-duration-seconds]")
      : null;
    const control = form.elements.duration_seconds;
    const spec = modelSpec(form);
    if (!(button instanceof HTMLButtonElement) || !(control instanceof HTMLSelectElement) || !spec) return;
    const seconds = Number(button.dataset.durationSeconds);
    if (!spec.allowed.includes(seconds)) return;
    control.value = String(seconds);
    form.dataset.durationChosenByUser = "true";
    dispatchSelection(control);
    sync(form, panel);
  });
  return panel;
}

function renderSignature(form, spec, control, hidden) {
  return JSON.stringify({
    mode: String(form.elements.generation_mode?.value || ""),
    duration: String(control?.value || ""),
    category: String(form.elements.product_category?.value || ""),
    sku: String(form.elements.sku?.value || ""),
    policy: String(form.dataset.generationDurationPolicy || ""),
    allowed: spec?.allowed || [],
    hidden,
  });
}

function sync(form, panel = buildPanel(form)) {
  if (!panel) return;
  const spec = modelSpec(form);
  const durationField = form.querySelector("#generation-duration-field");
  const control = form.elements.duration_seconds;
  const hidden = !spec || !(control instanceof HTMLSelectElement) || durationField?.hidden === true;
  panel.hidden = hidden;
  if (hidden || !spec || !(control instanceof HTMLSelectElement)) return;

  [...control.options].forEach((option) => {
    const unavailable = !spec.allowed.includes(Number(option.value));
    if (option.hidden !== unavailable) option.hidden = unavailable;
    if (option.disabled !== unavailable) option.disabled = unavailable;
  });
  if (!spec.allowed.includes(Number(control.value))) {
    control.value = String(spec.coldStart[0]);
    dispatchSelection(control);
  }

  const signature = renderSignature(form, spec, control, false);
  if (panel.dataset.renderSignature === signature) return;
  panel.dataset.renderSignature = signature;

  const category = String(form.elements.product_category?.value || "").trim();
  const sku = String(form.elements.sku?.value || "").trim();
  const serverPolicy = readServerPolicyHint(form);
  const plan = serverPolicy?.arms || spec.coldStart.map((seconds) => ({
    seconds,
    allocation: 1 / spec.coldStart.length,
  }));
  const message = panel.querySelector("[data-duration-advisor-message]");
  const arms = panel.querySelector("[data-duration-advisor-arms]");
  const state = panel.querySelector("[data-duration-advisor-state]");

  if (state) {
    state.textContent = serverPolicy
      ? serverPolicy.mode === "exploit" ? "Server winner + control" : "Server A/B"
      : "Безопасный cold start";
    state.dataset.tone = serverPolicy ? "ready" : "explore";
  }
  if (message) {
    message.textContent = category && sku
      ? serverPolicy
        ? `${spec.label}: показан серверный план для текущего SKU. Control сохраняется, чтобы обучение не зацементировало случайность.`
        : `${spec.label}: для новой или разреженной категории сравниваем ${spec.coldStart.join(" и ")} секунд. Восемь секунд — один arm, а не обязательный результат.`
      : "Сначала выберите точный товар и категорию. До этого мини‑ИИ не переносит решения между товарами.";
  }
  if (arms) {
    arms.replaceChildren();
    plan.forEach((arm) => {
      const button = element(
        "button",
        "generation-duration-advisor__arm",
        `${arm.seconds} сек · ${Math.round(arm.allocation * 100)}%`,
      );
      button.type = "button";
      button.dataset.durationSeconds = String(arm.seconds);
      const active = Number(control.value) === arm.seconds;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
      arms.append(button);
    });
  }
}

function mount() {
  if (routePath() !== GENERATION_ROUTE) return;
  const form = document.querySelector(SELECTOR);
  if (!(form instanceof HTMLFormElement)) return;
  if (observedForm !== form) {
    observer?.disconnect();
    observedForm = form;
    observer = new MutationObserver(schedule);
    // Observe replacement of app-rendered controls. The advisor's own class,
    // hidden and data changes are attributes and therefore cannot self-loop.
    observer.observe(form, { childList: true, subtree: true });
    form.addEventListener("input", schedule, { passive: true });
    form.addEventListener("change", schedule, { passive: true });
  }
  sync(form);
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    mount();
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}
