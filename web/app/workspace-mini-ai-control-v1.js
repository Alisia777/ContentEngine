/*
 * ContentEngine mini-AI mass-generation desk.
 *
 * The desk plans a bounded experiment, prepares one native generation form at
 * a time and waits for a new durable job before moving on. It never calls the
 * provider or Supabase directly. Existing server budget, identity, learning,
 * QA and idempotency guards remain authoritative.
 */

import {
  MINI_AI_RULEBOOK_RU,
  buildMiniAiPlan,
  evaluateMiniAiPlan,
  miniAiEstimatedCostUsd,
} from "./mini-ai-control-plane-v1.js?v=20260801.1";

const ROUTE = "/workspace/generation";
const FORM_SELECTOR = "#mock-batch-form";
const STORAGE_KEY = "contentengine.mini-ai-control.v1";
const MAX_BRIEF_LENGTH = 1_200;
const JOB_WAIT_MS = 120_000;
const POLL_MS = 500;
const TABS = Object.freeze(["setup", "plan", "queue", "conclusion"]);

const runtime = {
  queued: false,
  form: null,
  panel: null,
  activeTab: "setup",
  executionPromise: null,
  observer: null,
};

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(label, action, className = "btn btn-secondary btn-small") {
  const node = el("button", className, label);
  node.type = "button";
  node.dataset.miniAiAction = action;
  return node;
}

function field(label, control, hint = "") {
  const wrapper = el("label", "mini-ai-field");
  wrapper.append(el("span", "mini-ai-field__label", label), control);
  if (hint) wrapper.append(el("small", "mini-ai-field__hint", hint));
  return wrapper;
}

function selectControl(name, options) {
  const control = el("select", "mini-ai-control");
  control.name = name;
  for (const [value, label] of options) {
    const option = el("option", "", label);
    option.value = value;
    control.append(option);
  }
  return control;
}

function numberControl(name, value, min, max, step = 1) {
  const control = el("input", "mini-ai-control");
  control.type = "number";
  control.name = name;
  control.value = String(value);
  control.min = String(min);
  control.max = String(max);
  control.step = String(step);
  return control;
}

function textControl(name, value = "", placeholder = "") {
  const control = el("input", "mini-ai-control");
  control.type = "text";
  control.name = name;
  control.value = value;
  control.placeholder = placeholder;
  control.autocomplete = "off";
  return control;
}

function readStore() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function writeStore(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // The desk still works for the current page; durable server jobs remain authoritative.
  }
}

function contextScope(form = runtime.form) {
  const organization = String(
    window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
      || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
      || window.location.host,
  ).trim();
  const category = String(
    runtime.panel?.querySelector('[name="mini_ai_learning_category"]')?.value
      || form?.elements?.product_category?.value
      || "",
  ).trim().toLowerCase();
  const sku = String(form?.elements?.sku?.value || "").trim();
  const platform = String(form?.elements?.platform?.value || "").trim().toLowerCase();
  const mode = String(form?.elements?.generation_mode?.value || "").trim();
  return [organization, category, sku, platform, mode].join("|");
}

function scopedState(form = runtime.form) {
  const store = readStore();
  const scope = contextScope(form);
  return store[scope] && typeof store[scope] === "object"
    ? store[scope]
    : {};
}

function saveScopedState(patch, form = runtime.form) {
  const store = readStore();
  const scope = contextScope(form);
  store[scope] = { ...(store[scope] || {}), ...patch, updatedAt: Date.now() };
  writeStore(store);
  return store[scope];
}

function currentJobIds() {
  return new Set(
    [...document.querySelectorAll("[data-generation-job-id]")]
      .map((node) => String(node.dataset.generationJobId || "").trim())
      .filter(Boolean),
  );
}

function compact(value, limit = 160) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function modeCostMinor(mode, duration) {
  if (mode === "real_gen4") return Number(duration) * 5;
  if (mode === "real_seedance") return Number(duration) * 29;
  return 0;
}

function modeLabel(mode) {
  return {
    real_gen4: "Gen‑4 Turbo",
    real_seedance: "Seedance 2 Fast",
  }[mode] || "Выберите видеорежим";
}

function formContext(form) {
  const categoryControl = runtime.panel?.querySelector('[name="mini_ai_learning_category"]');
  const mode = String(form.elements.generation_mode?.value || "").trim();
  const duration = Number(form.elements.duration_seconds?.value || 0);
  const maxBudgetUsd = Number(
    runtime.panel?.querySelector('[name="mini_ai_budget_usd"]')?.value || 0,
  );
  return {
    organizationKey: String(
      window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
        || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
        || window.location.host,
    ).trim(),
    learningCategoryKey: String(
      categoryControl?.value || form.elements.product_category?.value || "",
    ).trim().toLowerCase(),
    sku: String(form.elements.sku?.value || "").trim(),
    platform: String(form.elements.platform?.value || "").trim().toLowerCase(),
    mode,
    objective: String(
      runtime.panel?.querySelector('[name="mini_ai_objective"]')?.value || "orders",
    ),
    riskPreset: String(
      runtime.panel?.querySelector('[name="mini_ai_risk"]')?.value || "balanced",
    ),
    requestedDimension: String(
      runtime.panel?.querySelector('[name="mini_ai_dimension"]')?.value || "auto",
    ),
    requestedBatchSize: Number(
      runtime.panel?.querySelector('[name="mini_ai_batch_size"]')?.value || 6,
    ),
    unitCostMinor: modeCostMinor(mode, duration),
    maxBudgetMinor: Number.isFinite(maxBudgetUsd) && maxBudgetUsd > 0
      ? Math.round(maxBudgetUsd * 100)
      : 0,
    funnelDecision: String(
      runtime.panel?.querySelector('[name="mini_ai_funnel"]')?.value || "creative",
    ),
    categoryIsNew: runtime.panel?.querySelector('[name="mini_ai_new_category"]')?.checked === true,
    approvedWinnerAngle: String(
      runtime.panel?.querySelector('[name="mini_ai_winner_angle"]')?.value || "",
    ).trim(),
    approvedWinnerDuration: Number(
      runtime.panel?.querySelector('[name="mini_ai_winner_duration"]')?.value || 0,
    ) || null,
    durationPolicy: readDurationPolicy(form),
  };
}

function readDurationPolicy(form) {
  const raw = String(form.dataset.generationExperimentPolicy || "").trim();
  if (!raw || raw.length > 8_000) return null;
  try {
    const value = JSON.parse(raw);
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

function baseBrief(form) {
  const value = String(form.elements.brief?.value || "").trim();
  return value;
}

function briefFingerprint(value) {
  let hash = 2166136261;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function buildTasks(plan) {
  const tasks = [];
  let remaining = plan.arms.map((arm) => arm.plannedCount);
  let ordinal = 0;
  while (remaining.some((value) => value > 0)) {
    plan.arms.forEach((arm, index) => {
      if (remaining[index] <= 0) return;
      ordinal += 1;
      tasks.push({
        taskId: `${plan.planId}-${String(ordinal).padStart(2, "0")}`,
        armId: arm.armId,
        status: "pending",
        jobId: "",
        startedAt: null,
        completedAt: null,
        error: "",
      });
      remaining[index] -= 1;
    });
  }
  return tasks;
}

function buildPanel(form) {
  const panel = el("section", "mini-ai-desk");
  panel.dataset.miniAiDesk = "true";
  panel.setAttribute("aria-label", "Мини-ИИ массовой генерации");

  const head = el("div", "mini-ai-desk__head");
  const title = el("div", "mini-ai-desk__title");
  title.append(
    el("span", "mini-ai-desk__eyebrow", "УПРАВЛЯЕМЫЙ МИНИ‑ИИ"),
    el("strong", "", "Массовый тест без размножения одной ошибки"),
    el(
      "small",
      "",
      "План → последовательный запуск → QA → метрики → объяснимый вывод.",
    ),
  );
  const status = el("span", "mini-ai-desk__status", "Настройте вопрос");
  status.dataset.miniAiStatus = "true";
  head.append(title, status);

  const nav = el("div", "mini-ai-desk__nav");
  const tabLabels = {
    setup: "1 · Задача",
    plan: "2 · План",
    queue: "3 · Запуск",
    conclusion: "4 · Вывод",
  };
  for (const key of TABS) {
    const control = button(tabLabels[key], `tab:${key}`, "mini-ai-tab");
    control.dataset.miniAiTab = key;
    nav.append(control);
  }

  const setup = buildSetupSpace(form);
  const plan = el("div", "mini-ai-space");
  plan.dataset.miniAiSpace = "plan";
  const queue = el("div", "mini-ai-space");
  queue.dataset.miniAiSpace = "queue";
  const conclusion = el("div", "mini-ai-space");
  conclusion.dataset.miniAiSpace = "conclusion";

  const rules = el("details", "mini-ai-rules");
  rules.append(el("summary", "", "Свод правил мини‑ИИ"));
  const list = el("ol", "mini-ai-rules__list");
  MINI_AI_RULEBOOK_RU.forEach((item) => list.append(el("li", "", item)));
  rules.append(list);

  panel.append(head, nav, setup, plan, queue, conclusion, rules);
  panel.addEventListener("click", handlePanelClick);
  panel.addEventListener("input", schedule, { passive: true });
  panel.addEventListener("change", schedule, { passive: true });

  const anchor = form.querySelector("[data-generation-duration-advisor]")
    || form.querySelector("#generation-duration-field")
    || form.querySelector("#generation-brief-assist")
    || form.firstElementChild;
  anchor?.after(panel);
  return panel;
}

function buildSetupSpace(form) {
  const space = el("div", "mini-ai-space");
  space.dataset.miniAiSpace = "setup";
  const intro = el("p", "mini-ai-space__intro", "Сначала выберите один вопрос. Мини‑ИИ не смешивает длительность, хук и CTA в одном тесте.");
  const grid = el("div", "mini-ai-setup-grid");

  const category = textControl(
    "mini_ai_learning_category",
    String(form.elements.product_category?.value || "").trim().toLowerCase(),
    "например: car_audio_amplifier",
  );
  grid.append(field("Категория обучения *", category, "Более узкая, чем compliance-категория. История не переезжает между категориями."));

  grid.append(field("Цель", selectControl("mini_ai_objective", [
    ["orders", "Заказы в день"],
    ["sales", "Продажи в день"],
    ["conversion", "Конверсия корзина → заказ"],
    ["qa_acceptance", "Принятие QA"],
    ["cost_per_order", "Стоимость заказа"],
  ])));

  grid.append(field("Что тестируем", selectControl("mini_ai_dimension", [
    ["auto", "Мини‑ИИ выберет один следующий вопрос"],
    ["creative_angle", "Сценарный угол / хук"],
    ["duration", "Длительность"],
    ["proof_type", "Тип доказательства"],
    ["cta_style", "CTA"],
  ])));

  grid.append(field("Профиль риска", selectControl("mini_ai_risk", [
    ["conservative", "Консервативный"],
    ["balanced", "Сбалансированный"],
    ["exploratory", "Исследовательский"],
  ])));

  grid.append(field("Размер пакета", selectControl("mini_ai_batch_size", [
    ["4", "4 запуска"],
    ["6", "6 запусков"],
    ["8", "8 запусков"],
    ["9", "9 запусков"],
    ["12", "12 запусков"],
  ]), "Для трёх вариантов нужно минимум 6 запусков."));

  grid.append(field("Лимит пакета, $", numberControl("mini_ai_budget_usd", 20, 1, 1_000, 0.01), "Серверные лимиты кампании всё равно остаются главными."));

  grid.append(field("Что говорит воронка", selectControl("mini_ai_funnel", [
    ["creative", "Контент / первый экран — тест нужен"],
    ["scale", "Можно масштабировать с контролем"],
    ["observe", "Наблюдать, но допустим bounded-тест"],
    ["supply", "Риск OOS / поставка"],
    ["expectation", "Чинить выкуп / ожидание"],
    ["advertising", "Оптимизировать рекламу"],
    ["measurement", "Мало данных"],
  ])));

  const newCategory = el("input");
  newCategory.type = "checkbox";
  newCategory.name = "mini_ai_new_category";
  newCategory.checked = true;
  const newCategoryLabel = el("label", "mini-ai-check");
  newCategoryLabel.append(newCategory, el("span", "", "Новая категория: не переносить старого winner"));
  grid.append(newCategoryLabel);

  const advanced = el("details", "mini-ai-advanced");
  advanced.append(el("summary", "", "Уже подтверждённый winner — необязательно"));
  const advancedGrid = el("div", "mini-ai-setup-grid");
  advancedGrid.append(field("Winner-угол", selectControl("mini_ai_winner_angle", [
    ["", "Нет подтверждённого winner"],
    ["demonstration", "Демонстрация"],
    ["product_focus", "Товар в центре"],
    ["problem_first", "Проблема первой"],
    ["result_first", "Результат первым"],
    ["trust_builder", "Доверительная подача"],
  ])));
  advancedGrid.append(field("Winner-длительность", selectControl("mini_ai_winner_duration", [
    ["", "Не подтверждена"],
    ["2", "2 секунды"],
    ["4", "4 секунды"],
    ["5", "5 секунд"],
    ["8", "8 секунд"],
    ["10", "10 секунд"],
    ["12", "12 секунд"],
    ["15", "15 секунд"],
  ])));
  advanced.append(advancedGrid);

  const footer = el("div", "mini-ai-space__footer");
  footer.append(button("Собрать управляемый план", "build-plan", "btn btn-primary"));
  space.append(intro, grid, advanced, footer);
  return space;
}

function setTab(key) {
  const resolved = TABS.includes(key) ? key : "setup";
  runtime.activeTab = resolved;
  runtime.panel?.querySelectorAll("[data-mini-ai-tab]").forEach((node) => {
    const active = node.dataset.miniAiTab === resolved;
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-pressed", String(active));
  });
  runtime.panel?.querySelectorAll("[data-mini-ai-space]").forEach((node) => {
    const active = node.dataset.miniAiSpace === resolved;
    node.classList.toggle("is-active", active);
    node.hidden = !active;
  });
  const state = scopedState();
  saveScopedState({ ...state, activeTab: resolved });
}

function statusCopy(value, tone = "idle") {
  const node = runtime.panel?.querySelector("[data-mini-ai-status]");
  if (!node) return;
  node.textContent = value;
  node.dataset.tone = tone;
}

function renderPlan() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="plan"]');
  if (!space) return;
  space.replaceChildren();
  const state = scopedState();
  const plan = state.plan;
  if (!plan) {
    space.append(
      el("p", "mini-ai-empty", "Сначала соберите план на первом шаге."),
      button("К задаче", "tab:setup"),
    );
    return;
  }
  const summary = el("div", "mini-ai-plan-summary");
  summary.append(
    el("span", "mini-ai-kicker", plan.executable ? "ПЛАН ГОТОВ" : "ПЛАН ОСТАНОВЛЕН"),
    el("strong", "", plan.executable
      ? `${plan.batchSize} запусков · ${dimensionLabel(plan.dimension)}`
      : plan.blockers?.[0] || "Нужно исправить контекст"),
    el("small", "", plan.executable
      ? `${modeLabel(plan.context.mode)} · оценка $${miniAiEstimatedCostUsd(plan).toFixed(2)} · один вопрос за цикл`
      : "Мини‑ИИ не будет запускать массовую генерацию не тем рычагом."),
  );
  space.append(summary);
  if (!plan.executable) {
    space.append(button("Исправить задачу", "tab:setup", "btn btn-primary"));
    return;
  }
  const arms = el("div", "mini-ai-arms");
  plan.arms.forEach((arm, index) => {
    const card = el("article", "mini-ai-arm");
    if (arm.control) card.classList.add("is-control");
    card.append(
      el("span", "mini-ai-arm__index", arm.control ? "CONTROL" : `ARM ${index + 1}`),
      el("strong", "", arm.label),
      el("p", "", arm.instruction),
      el("small", "", `${arm.plannedCount} запусков · ${arm.durationSeconds} сек. · ${Math.round(arm.allocation * 100)}%`),
    );
    arms.append(card);
  });
  const warnings = el("ul", "mini-ai-warnings");
  (plan.warnings || []).forEach((item) => warnings.append(el("li", "", item)));
  const footer = el("div", "mini-ai-space__footer");
  footer.append(
    button("Назад", "tab:setup"),
    button("Подготовить очередь", "prepare-queue", "btn btn-primary"),
  );
  space.append(arms, warnings, footer);
}

function renderQueue() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="queue"]');
  if (!space) return;
  space.replaceChildren();
  const state = scopedState();
  const plan = state.plan;
  const execution = state.execution;
  if (!plan?.executable) {
    space.append(el("p", "mini-ai-empty", "Сначала нужен исполнимый план."), button("К плану", "tab:plan"));
    return;
  }
  if (!execution?.tasks?.length) {
    const prompt = el("div", "mini-ai-confirm");
    prompt.append(
      el("strong", "", "Подтвердите весь пакет один раз"),
      el("p", "", `Максимальная оценка: $${miniAiEstimatedCostUsd(plan).toFixed(2)}. Запуски идут строго по одному; при неизвестном исходе очередь остановится.`),
    );
    const typed = textControl("mini_ai_confirmation", "", `ЗАПУСТИТЬ ${plan.batchSize}`);
    const autopilot = el("input");
    autopilot.type = "checkbox";
    autopilot.name = "mini_ai_autopilot";
    const autopilotLabel = el("label", "mini-ai-check");
    autopilotLabel.append(autopilot, el("span", "", "Автопилот: после подтверждённого job запускать следующий arm"));
    const acknowledge = el("input");
    acknowledge.type = "checkbox";
    acknowledge.name = "mini_ai_acknowledge";
    const acknowledgeLabel = el("label", "mini-ai-check");
    acknowledgeLabel.append(
      acknowledge,
      el("span", "", "Подтверждаю общий лимит и понимаю, что каждый запуск платный"),
    );
    prompt.append(
      field("Введите подтверждение", typed),
      autopilotLabel,
      acknowledgeLabel,
      button("Создать очередь", "confirm-queue", "btn btn-primary"),
    );
    space.append(prompt, button("Назад", "tab:plan"));
    return;
  }

  const progress = el("div", "mini-ai-queue-head");
  const completed = execution.tasks.filter((item) => ["queued", "failed", "unknown"].includes(item.status)).length;
  progress.append(
    el("strong", "", `Очередь ${completed} / ${execution.tasks.length}`),
    el("small", "", execution.status === "running"
      ? "В работе один запуск. Следующий не стартует, пока job не появится в очереди."
      : execution.status === "completed"
        ? "Все запуски отправлены. Переходите к QA и метрикам."
        : "Очередь на паузе — можно безопасно продолжить."),
  );
  const bar = el("div", "mini-ai-progress");
  bar.style.setProperty("--mini-ai-progress", `${(completed / execution.tasks.length) * 100}%`);
  progress.append(bar);

  const list = el("div", "mini-ai-queue-list");
  execution.tasks.forEach((task, index) => {
    const arm = plan.arms.find((item) => item.armId === task.armId);
    const row = el("article", "mini-ai-queue-item");
    row.dataset.state = task.status;
    row.append(
      el("span", "mini-ai-queue-item__number", String(index + 1)),
      el("strong", "", arm?.label || task.armId),
      el("small", "", task.jobId
        ? `job ${task.jobId}`
        : task.error || queueStatusLabel(task.status)),
      el("span", "mini-ai-queue-item__status", queueStatusLabel(task.status)),
    );
    list.append(row);
  });
  const footer = el("div", "mini-ai-space__footer");
  const pending = execution.tasks.some((item) => item.status === "pending");
  if (pending && execution.status !== "running") {
    footer.append(button("Запустить следующий", "run-next", "btn btn-primary"));
  }
  if (execution.status === "running") footer.append(button("Поставить на паузу", "pause-queue"));
  if (execution.status === "paused" && pending) footer.append(button("Продолжить", "resume-queue"));
  if (!pending && execution.tasks.every((item) => item.status === "queued")) {
    footer.append(button("Перейти к выводу", "tab:conclusion", "btn btn-primary"));
  }
  footer.append(button("Сбросить локальную очередь", "reset-queue", "btn btn-ghost btn-small"));
  space.append(progress, list, footer);
}

function renderConclusion() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="conclusion"]');
  if (!space) return;
  space.replaceChildren();
  const state = scopedState();
  const plan = state.plan;
  if (!plan?.executable) {
    space.append(el("p", "mini-ai-empty", "Сначала соберите и выполните план."));
    return;
  }
  const intro = el("p", "mini-ai-space__intro", "Введите агрегированные результаты после независимого QA и зрелого окна атрибуции. Просмотры сохраняются только для диагностики.");
  const resultGrid = el("div", "mini-ai-result-grid");
  const savedResults = state.results && typeof state.results === "object" ? state.results : {};
  plan.arms.forEach((arm) => {
    const value = savedResults[arm.armId] || {};
    const card = el("article", "mini-ai-result-card");
    card.dataset.armId = arm.armId;
    card.append(
      el("span", "mini-ai-arm__index", arm.control ? "CONTROL" : "HYPOTHESIS"),
      el("strong", "", arm.label),
    );
    const grid = el("div", "mini-ai-result-fields");
    const controls = [
      ["eligible", "Зрелых результатов", value.eligible ?? 0, 0, 50, 1],
      ["failed", "Тех. ошибок", value.failed ?? 0, 0, 50, 1],
      ["qaRejected", "Не прошли QA", value.qaRejected ?? 0, 0, 50, 1],
      ["critical", "Критических блокеров", value.critical ?? 0, 0, 50, 1],
      ["mismatch", "Подмен товара", value.mismatch ?? 0, 0, 50, 1],
      ["orders", "Заказы", value.orders ?? 0, 0, 1_000_000, 1],
      ["carts", "Корзины", value.carts ?? 0, 0, 1_000_000, 1],
      ["salesRub", "Продажи, ₽", value.salesRub ?? 0, 0, 1_000_000_000, 0.01],
      ["spendRub", "Расход, ₽", value.spendRub ?? 0, 0, 1_000_000_000, 0.01],
      ["days", "Сумма дней атрибуции", value.days ?? 1, 1, 10_000, 1],
      ["views", "Просмотры · диагностика", value.views ?? 0, 0, 1_000_000_000, 1],
    ];
    controls.forEach(([name, label, initial, min, max, step]) => {
      const control = numberControl(`mini_ai_result_${name}`, initial, min, max, step);
      control.dataset.resultField = name;
      control.dataset.armId = arm.armId;
      grid.append(field(label, control));
    });
    card.append(grid);
    resultGrid.append(card);
  });
  const conclusion = state.conclusion;
  const output = el("div", "mini-ai-conclusion-output");
  output.dataset.miniAiConclusionOutput = "true";
  if (conclusion) renderConclusionOutput(output, conclusion, plan);
  const footer = el("div", "mini-ai-space__footer");
  footer.append(
    button("Сохранить результаты", "save-results"),
    button("Сделать вывод", "evaluate", "btn btn-primary"),
  );
  space.append(intro, resultGrid, footer, output);
}

function dimensionLabel(value) {
  return {
    creative_angle: "сценарный угол",
    duration: "длительность",
    proof_type: "тип доказательства",
    cta_style: "CTA",
  }[value] || value;
}

function queueStatusLabel(value) {
  return {
    pending: "ожидает",
    running: "отправляется",
    queued: "job создан",
    failed: "ошибка",
    unknown: "исход не подтверждён",
  }[value] || value;
}

function buildPlanFromForm() {
  const form = runtime.form;
  if (!form) return;
  const context = formContext(form);
  const plan = buildMiniAiPlan(context);
  const brief = baseBrief(form);
  const state = {
    plan,
    baseBrief: brief,
    baseBriefFingerprint: briefFingerprint(brief),
    execution: null,
    results: {},
    conclusion: null,
    activeTab: "plan",
  };
  saveScopedState(state, form);
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab("plan");
  statusCopy(plan.executable ? "План готов" : "Нужна правка", plan.executable ? "ready" : "warning");
}

function confirmQueue() {
  const state = scopedState();
  const plan = state.plan;
  if (!plan?.executable) return;
  const typed = String(
    runtime.panel?.querySelector('[name="mini_ai_confirmation"]')?.value || "",
  ).trim().toUpperCase();
  const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
  const acknowledged = runtime.panel?.querySelector('[name="mini_ai_acknowledge"]')?.checked === true;
  if (typed !== expected || !acknowledged) {
    statusCopy(`Введите «${expected}» и подтвердите лимит`, "warning");
    return;
  }
  const autopilot = runtime.panel?.querySelector('[name="mini_ai_autopilot"]')?.checked === true;
  const execution = {
    status: "paused",
    autopilot,
    tasks: buildTasks(plan),
    currentTaskId: "",
    startedAt: null,
  };
  saveScopedState({ execution, activeTab: "queue" });
  renderQueue();
  setTab("queue");
  statusCopy("Очередь готова", "ready");
  if (autopilot) void runNextTask();
}

function nativeContextMatches(plan, form) {
  const current = formContext(form);
  return (
    current.learningCategoryKey === plan.context.learningCategoryKey
    && current.sku === plan.context.sku
    && current.platform === plan.context.platform
    && current.mode === plan.context.mode
  );
}

function replaceDurationInBrief(value, seconds) {
  const text = String(value || "").trim();
  return text.replace(
    /(длительностью\s+)\d+(\s+секунд)/giu,
    `$1${seconds}$2`,
  );
}

function spokenWordCount(value) {
  const match = String(value || "").match(/Реплика героя дословно:\s*«([^»]+)»/iu);
  if (!match) return 0;
  return (match[1].match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || []).length;
}

function armBrief(base, arm, mode) {
  let value = replaceDurationInBrief(base, arm.durationSeconds);
  value = `${value}\n${arm.instruction}`.trim();
  if (value.length > MAX_BRIEF_LENGTH) {
    throw new Error(`ТЗ вместе с arm длиннее ${MAX_BRIEF_LENGTH} символов. Сократите базовый сценарий.`);
  }
  if (mode === "real_seedance") {
    const limit = Math.max(10, Math.min(42, Math.floor(arm.durationSeconds * 22 / 8)));
    const words = spokenWordCount(value);
    if (words > limit) {
      throw new Error(`Реплика содержит ${words} слов; для ${arm.durationSeconds} секунд разрешено не больше ${limit}.`);
    }
  }
  return value;
}

function dispatch(control) {
  control?.dispatchEvent(new Event("input", { bubbles: true }));
  control?.dispatchEvent(new Event("change", { bubbles: true }));
}

function waitFrame() {
  return new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
}

async function prepareNativeForm(form, plan, arm, base) {
  const duration = form.elements.duration_seconds;
  const brief = form.elements.brief;
  const count = form.elements.count;
  const confirmation = form.elements.real_spend_confirmation;
  if (!(duration instanceof HTMLSelectElement) || !(brief instanceof HTMLTextAreaElement || brief instanceof HTMLInputElement)) {
    throw new Error("Форма генерации не содержит длительность или ТЗ.");
  }
  duration.value = String(arm.durationSeconds);
  dispatch(duration);
  await waitFrame();
  brief.value = armBrief(base, arm, plan.context.mode);
  dispatch(brief);
  if (count instanceof HTMLInputElement || count instanceof HTMLSelectElement) {
    count.value = "1";
    dispatch(count);
  }
  await waitFrame();
  if (!(confirmation instanceof HTMLInputElement)) {
    throw new Error("Не найдено подтверждение платного запуска.");
  }
  confirmation.checked = true;
  dispatch(confirmation);
  await waitFrame();
  if (!form.checkValidity()) {
    form.reportValidity();
    throw new Error("Заполните обязательные поля штатной формы перед запуском пакета.");
  }
}

function waitForNewJob(before) {
  const startedAt = Date.now();
  return new Promise((resolve) => {
    const timer = window.setInterval(() => {
      const current = currentJobIds();
      const created = [...current].find((value) => !before.has(value));
      if (created) {
        window.clearInterval(timer);
        resolve(created);
        return;
      }
      if (Date.now() - startedAt >= JOB_WAIT_MS) {
        window.clearInterval(timer);
        resolve("");
      }
    }, POLL_MS);
  });
}

async function runNextTask() {
  if (runtime.executionPromise) return runtime.executionPromise;
  runtime.executionPromise = (async () => {
    let state = scopedState();
    const plan = state.plan;
    const execution = state.execution;
    if (!plan?.executable || !execution?.tasks?.length) return;
    if (execution.status === "running") return;
    const taskIndex = execution.tasks.findIndex((item) => item.status === "pending");
    if (taskIndex < 0) {
      execution.status = "completed";
      saveScopedState({ execution });
      renderQueue();
      statusCopy("Пакет отправлен", "ready");
      return;
    }
    const form = document.querySelector(FORM_SELECTOR);
    if (!(form instanceof HTMLFormElement)) {
      statusCopy("Форма генерации временно недоступна", "warning");
      return;
    }
    if (!nativeContextMatches(plan, form)) {
      execution.status = "paused";
      execution.tasks[taskIndex].error = "Контекст SKU, категории, площадки или модели изменился.";
      saveScopedState({ execution });
      renderQueue();
      statusCopy("Контекст изменился — очередь на паузе", "warning");
      return;
    }
    if (form.dataset.busy === "true") {
      statusCopy("Штатная форма занята другим запуском", "warning");
      return;
    }
    const task = execution.tasks[taskIndex];
    const arm = plan.arms.find((item) => item.armId === task.armId);
    if (!arm) throw new Error("Arm очереди не найден в плане.");
    execution.status = "running";
    execution.currentTaskId = task.taskId;
    execution.startedAt ||= Date.now();
    task.status = "running";
    task.startedAt = Date.now();
    saveScopedState({ execution });
    renderQueue();
    statusCopy(`Запускаем ${taskIndex + 1} из ${execution.tasks.length}`, "running");
    const before = currentJobIds();
    try {
      await prepareNativeForm(form, plan, arm, String(state.baseBrief || ""));
      const submit = form.querySelector("#generation-submit, button[type='submit']");
      if (!(submit instanceof HTMLElement)) throw new Error("Не найдена штатная кнопка запуска.");
      form.requestSubmit(submit);
      const jobId = await waitForNewJob(before);
      state = scopedState();
      const freshExecution = state.execution;
      const freshTask = freshExecution?.tasks?.find((item) => item.taskId === task.taskId);
      if (!freshTask) return;
      if (!jobId) {
        freshTask.status = "unknown";
        freshTask.error = "Job не появился за две минуты. Не повторяйте оплату — сначала проверьте штатную очередь.";
        freshExecution.status = "paused";
        saveScopedState({ execution: freshExecution });
        renderQueue();
        statusCopy("Исход запуска не подтверждён", "warning");
        return;
      }
      freshTask.status = "queued";
      freshTask.jobId = jobId;
      freshTask.completedAt = Date.now();
      freshExecution.currentTaskId = "";
      freshExecution.status = freshExecution.tasks.some((item) => item.status === "pending")
        ? "paused"
        : "completed";
      saveScopedState({ execution: freshExecution });
      renderQueue();
      statusCopy(`Job ${compact(jobId, 18)} создан`, "ready");
      if (freshExecution.autopilot && freshExecution.status !== "completed") {
        await new Promise((resolve) => window.setTimeout(resolve, 1_500));
        freshExecution.status = "paused";
        saveScopedState({ execution: freshExecution });
        await runNextTask();
      }
    } catch (error) {
      state = scopedState();
      const freshExecution = state.execution;
      const freshTask = freshExecution?.tasks?.find((item) => item.taskId === task.taskId);
      if (freshTask) {
        freshTask.status = "failed";
        freshTask.error = String(error?.message || "Запуск остановлен.");
      }
      if (freshExecution) freshExecution.status = "paused";
      saveScopedState({ execution: freshExecution });
      renderQueue();
      statusCopy(String(error?.message || "Запуск остановлен"), "warning");
    }
  })().finally(() => {
    runtime.executionPromise = null;
  });
  return runtime.executionPromise;
}

function collectResultValues() {
  const result = {};
  runtime.panel?.querySelectorAll("[data-result-field][data-arm-id]").forEach((control) => {
    const armId = control.dataset.armId;
    const name = control.dataset.resultField;
    if (!armId || !name) return;
    result[armId] ||= {};
    result[armId][name] = Number(control.value || 0);
  });
  return result;
}

function aggregateOutcomes(plan, results) {
  const outcomes = [];
  plan.arms.forEach((arm) => {
    const value = results[arm.armId] || {};
    const eligible = Math.max(0, Math.floor(value.eligible || 0));
    const failed = Math.max(0, Math.floor(value.failed || 0));
    const rejected = Math.max(0, Math.floor(value.qaRejected || 0));
    const total = Math.max(eligible + failed + rejected, arm.plannedCount);
    const distribute = (amount, index, count) => {
      if (!count) return 0;
      const base = Math.floor(amount / count);
      return base + (index < amount % count ? 1 : 0);
    };
    const salesMinor = Math.round(Math.max(0, Number(value.salesRub || 0)) * 100);
    const spendMinor = Math.round(Math.max(0, Number(value.spendRub || 0)) * 100);
    const orders = Math.max(0, Math.floor(value.orders || 0));
    const carts = Math.max(orders, Math.floor(value.carts || 0));
    const days = Math.max(1, Math.floor(value.days || eligible || 1));
    const views = Math.max(0, Math.floor(value.views || 0));
    for (let index = 0; index < total; index += 1) {
      let state = "queued";
      let qaState = "pending";
      let published = false;
      let metricsMature = false;
      if (index < eligible) {
        state = "succeeded";
        qaState = "approved";
        published = true;
        metricsMature = true;
      } else if (index < eligible + rejected) {
        state = "succeeded";
        qaState = "rejected";
      } else if (index < eligible + rejected + failed) {
        state = "failed";
      }
      outcomes.push({
        outcomeId: `${plan.planId}-${arm.armId}-${index + 1}`,
        jobId: `manual-${arm.armId}-${index + 1}`,
        armId: arm.armId,
        state,
        qaState,
        productFidelityOk: index >= Math.floor(value.mismatch || 0),
        criticalBlocker: index < Math.floor(value.critical || 0),
        published,
        metricsMature,
        orders: index < eligible ? distribute(orders, index, eligible) : null,
        carts: index < eligible ? distribute(carts, index, eligible) : null,
        salesMinor: index < eligible ? distribute(salesMinor, index, eligible) : null,
        spendMinor: index < eligible ? distribute(spendMinor, index, eligible) : null,
        attributionDays: index < eligible ? Math.max(1, distribute(days, index, eligible)) : 1,
        views: index < eligible ? distribute(views, index, eligible) : null,
      });
    }
  });
  return outcomes;
}

function evaluateCurrent() {
  const state = scopedState();
  const plan = state.plan;
  if (!plan?.executable) return;
  const results = collectResultValues();
  const outcomes = aggregateOutcomes(plan, results);
  const conclusion = evaluateMiniAiPlan(plan, outcomes);
  saveScopedState({ results, conclusion });
  renderConclusion();
  statusCopy(conclusion.decision === "promote_with_control" ? "Winner найден" : "Вывод готов", "ready");
}

function saveResults() {
  saveScopedState({ results: collectResultValues(), conclusion: null });
  statusCopy("Результаты сохранены локально", "ready");
}

function renderConclusionOutput(output, conclusion, plan) {
  output.replaceChildren();
  output.dataset.decision = conclusion.decision;
  const winner = plan.arms.find((arm) => arm.armId === conclusion.winnerArmId);
  output.append(
    el("span", "mini-ai-kicker", conclusion.decision.toUpperCase()),
    el("strong", "", conclusion.summary),
    el("p", "", conclusion.nextAction),
  );
  if (winner) output.append(el("p", "mini-ai-winner", `Выбранный arm: ${winner.label}`));
  if (conclusion.evidence?.length) {
    const list = el("ul", "mini-ai-evidence");
    conclusion.evidence.forEach((item) => list.append(el("li", "", item)));
    output.append(list);
  }
  output.append(el("small", "", `Уверенность: ${conclusion.confidence}. Наблюдение не считается причинным доказательством.`));
}

function resetQueue() {
  const state = scopedState();
  saveScopedState({ execution: null, conclusion: null, results: state.results || {} });
  renderQueue();
  statusCopy("Локальная очередь сброшена", "idle");
}

function handlePanelClick(event) {
  const target = event.target instanceof Element
    ? event.target.closest("[data-mini-ai-action]")
    : null;
  if (!(target instanceof HTMLElement)) return;
  const action = String(target.dataset.miniAiAction || "");
  if (action.startsWith("tab:")) {
    setTab(action.slice(4));
    return;
  }
  if (action === "build-plan") buildPlanFromForm();
  else if (action === "prepare-queue") {
    renderQueue();
    setTab("queue");
  } else if (action === "confirm-queue") confirmQueue();
  else if (action === "run-next" || action === "resume-queue") void runNextTask();
  else if (action === "pause-queue") {
    const state = scopedState();
    if (state.execution) state.execution.autopilot = false;
    saveScopedState({ execution: state.execution });
    statusCopy("Автопилот выключен; текущий запрос не отменяется", "warning");
    renderQueue();
  } else if (action === "reset-queue") resetQueue();
  else if (action === "save-results") saveResults();
  else if (action === "evaluate") evaluateCurrent();
}

function syncPanel(form) {
  const category = runtime.panel?.querySelector('[name="mini_ai_learning_category"]');
  if (category && !category.dataset.touched) {
    category.value = String(form.elements.product_category?.value || "").trim().toLowerCase();
  }
  const categoryListener = category;
  if (categoryListener && !categoryListener.dataset.bound) {
    categoryListener.dataset.bound = "true";
    categoryListener.addEventListener("input", () => {
      categoryListener.dataset.touched = "true";
    }, { passive: true });
  }
  const saved = scopedState(form);
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab(saved.activeTab || runtime.activeTab || "setup");
  const plan = saved.plan;
  if (plan?.executable) statusCopy("План сохранён", "ready");
}

function mount() {
  if (routePath() !== ROUTE) return;
  const form = document.querySelector(FORM_SELECTOR);
  if (!(form instanceof HTMLFormElement)) return;
  if (runtime.form !== form || !document.contains(runtime.panel)) {
    runtime.observer?.disconnect();
    runtime.form = form;
    runtime.panel = form.querySelector("[data-mini-ai-desk]") || buildPanel(form);
    runtime.observer = new MutationObserver(schedule);
    runtime.observer.observe(form, { childList: true, subtree: true });
  }
  syncPanel(form);
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
window.addEventListener("contentengine:v4-route-ready", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}
