/*
 * ContentEngine mini-AI desk v3.
 *
 * The desk is intentionally bounded: one question, max 12 paid launches,
 * sequential native submissions, one result per arm per wave, mandatory QA
 * checkpoint between waves, then a deterministic business conclusion.
 */

import {
  MINI_AI_RULEBOOK_RU,
  buildMiniAiPlan,
  evaluateMiniAiPlan,
  miniAiEstimatedCostUsd,
} from "./mini-ai-control-plane-v2.js?v=20260801.2";

const ROUTE = "/workspace/generation";
const FORM_SELECTOR = "#mock-batch-form";
const STORAGE_KEY = "contentengine.mini-ai-control.v3";
const MAX_BRIEF = 1_200;
const JOB_WAIT_MS = 120_000;
const JOB_POLL_MS = 600;
const TABS = Object.freeze(["setup", "plan", "queue", "conclusion"]);

const runtime = {
  form: null,
  panel: null,
  running: false,
  retry: 0,
  mountTimer: 0,
  nextTimer: 0,
};

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function el(tag, className = "", text = "") {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text) value.textContent = text;
  return value;
}

function action(label, name, className = "btn btn-secondary btn-small") {
  const value = el("button", className, label);
  value.type = "button";
  value.dataset.miniAiAction = name;
  return value;
}

function select(name, values) {
  const value = el("select", "mini-ai-control");
  value.name = name;
  values.forEach(([key, label]) => {
    const option = el("option", "", label);
    option.value = key;
    value.append(option);
  });
  return value;
}

function textInput(name, initial = "", placeholder = "") {
  const value = el("input", "mini-ai-control");
  value.type = "text";
  value.name = name;
  value.value = String(initial);
  value.placeholder = placeholder;
  value.autocomplete = "off";
  return value;
}

function numberInput(name, initial, min, max, step = 1) {
  const value = el("input", "mini-ai-control");
  value.type = "number";
  value.name = name;
  value.value = String(initial);
  value.min = String(min);
  value.max = String(max);
  value.step = String(step);
  return value;
}

function field(label, control, hint = "") {
  const value = el("label", "mini-ai-field");
  value.append(el("span", "mini-ai-field__label", label), control);
  if (hint) value.append(el("small", "mini-ai-field__hint", hint));
  return value;
}

function check(name, label, checked = false) {
  const value = el("label", "mini-ai-check");
  const control = el("input");
  control.type = "checkbox";
  control.name = name;
  control.checked = checked;
  value.append(control, el("span", "", label));
  return value;
}

function normalize(value) {
  return String(value || "")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("ru-RU");
}

function compact(value, limit = 120) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function readAll() {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function writeAll(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Durable jobs remain server-owned; local recovery is an interface convenience.
  }
}

function control(name, fallback = "") {
  const value = runtime.panel?.querySelector(`[name="${CSS.escape(name)}"]`);
  if (value instanceof HTMLInputElement || value instanceof HTMLSelectElement) {
    return value.type === "checkbox" ? value.checked : value.value;
  }
  return fallback;
}

function learningCategory(form = runtime.form) {
  return String(
    control("mini_ai_learning_category")
      || form?.elements?.product_category?.value
      || "",
  ).trim().toLowerCase();
}

function scope(form = runtime.form) {
  return [
    String(
      window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
        || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
        || window.location.host,
    ).trim(),
    learningCategory(form),
    String(form?.elements?.sku?.value || "").trim(),
    String(form?.elements?.platform?.value || "").trim().toLowerCase(),
    String(form?.elements?.generation_mode?.value || "").trim(),
  ].join("|");
}

function readState(form = runtime.form) {
  const value = readAll()[scope(form)];
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function saveState(patch, form = runtime.form) {
  const all = readAll();
  const key = scope(form);
  all[key] = { ...(all[key] || {}), ...patch, updatedAt: Date.now() };
  writeAll(all);
  return all[key];
}

function status(text, tone = "idle") {
  const value = runtime.panel?.querySelector("[data-mini-ai-status]");
  if (!value) return;
  value.textContent = text;
  value.dataset.tone = tone;
}

function setTab(key, persist = true) {
  const activeKey = TABS.includes(key) ? key : "setup";
  runtime.panel?.querySelectorAll("[data-mini-ai-tab]").forEach((button) => {
    const active = button.dataset.miniAiTab === activeKey;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  runtime.panel?.querySelectorAll("[data-mini-ai-space]").forEach((space) => {
    const active = space.dataset.miniAiSpace === activeKey;
    space.hidden = !active;
    space.classList.toggle("is-active", active);
  });
  if (persist) saveState({ activeTab: activeKey });
}

function modelSpec(mode) {
  if (mode === "real_gen4") return { allowed: [2, 5, 8, 10], price: 5 };
  if (mode === "real_seedance") return { allowed: [4, 8, 12, 15], price: 29 };
  return null;
}

function signedDurationPolicy(form) {
  const raw = String(form.dataset.generationExperimentPolicy || "").trim();
  if (!raw || raw.length > 8_000) return null;
  try {
    const value = JSON.parse(raw);
    if (
      !value
      || typeof value !== "object"
      || Array.isArray(value)
      || value.source !== "creator_generation_experiment_policy"
      || !/^[0-9a-f]{64}$/u.test(String(value.policyHash || ""))
    ) return null;
    return value;
  } catch {
    return null;
  }
}

function contextFromForm(form) {
  const mode = String(form.elements.generation_mode?.value || "").trim();
  const spec = modelSpec(mode);
  const duration = Number(form.elements.duration_seconds?.value || 0);
  const budget = Number(control("mini_ai_budget_usd", 0));
  return {
    organizationKey: String(
      window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
        || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
        || window.location.host,
    ).trim(),
    learningCategoryKey: learningCategory(form),
    sku: String(form.elements.sku?.value || "").trim(),
    platform: String(form.elements.platform?.value || "").trim().toLowerCase(),
    mode,
    objective: String(control("mini_ai_objective", "orders")),
    riskPreset: "balanced",
    requestedDimension: String(control("mini_ai_dimension", "auto")),
    requestedBatchSize: Number(control("mini_ai_batch_size", 6)),
    unitCostMinor: spec?.allowed.includes(duration) ? duration * spec.price : 0,
    maxBudgetMinor: Number.isFinite(budget) && budget > 0 ? Math.round(budget * 100) : 0,
    funnelDecision: String(control("mini_ai_funnel", "creative")),
    categoryIsNew: control("mini_ai_new_category", true) === true,
    approvedWinnerAngle: String(control("mini_ai_winner_angle", "")).trim(),
    approvedWinnerDuration: Number(control("mini_ai_winner_duration", 0)) || null,
    durationPolicy: signedDurationPolicy(form),
  };
}

function validateBrief(form) {
  const brief = String(form.elements.brief?.value || "").trim();
  const sku = String(form.elements.sku?.value || "").trim();
  const name = String(form.elements.product_name?.value || "").trim();
  const normalized = normalize(brief);
  const blockers = [];
  if (brief.length < 80) blockers.push("Сначала подготовьте безопасное ТЗ длиной хотя бы 80 символов.");
  if (!sku || !name) blockers.push("Выберите точный SKU и название товара.");
  if (sku && !normalized.includes(normalize(sku))) blockers.push("ТЗ не содержит точный SKU.");
  if (name && !normalized.includes(normalize(name))) blockers.push("ТЗ не содержит точное название товара.");
  if (!normalized.includes("точный товар:")) blockers.push("Восстановите авто‑ТЗ: отсутствует строка «Точный товар:».");
  return { ready: blockers.length === 0, blockers, brief };
}

function briefHash(value) {
  let hash = 2166136261;
  const text = String(value || "");
  for (let index = 0; index < text.length; index += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(index), 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function buildSetup(form) {
  const space = el("section", "mini-ai-space");
  space.dataset.miniAiSpace = "setup";
  space.append(el(
    "p",
    "mini-ai-space__intro",
    "В одном цикле меняется только один фактор. Товар, исходники, площадка и разрешённые факты остаются неизменными.",
  ));
  const grid = el("div", "mini-ai-setup-grid");
  grid.append(
    field(
      "Категория обучения *",
      textInput(
        "mini_ai_learning_category",
        String(form.elements.product_category?.value || "").trim().toLowerCase(),
        "например: car_audio_amplifier",
      ),
      "Используйте узкую категорию. Новая категория не наследует чужой winner.",
    ),
    field("Цель", select("mini_ai_objective", [
      ["orders", "Заказы в день"],
      ["sales", "Продажи в день"],
      ["conversion", "Конверсия корзина → заказ"],
      ["qa_acceptance", "Принятие QA"],
      ["cost_per_order", "Стоимость заказа"],
    ])),
    field("Один вопрос", select("mini_ai_dimension", [
      ["auto", "Мини‑ИИ выберет следующий вопрос"],
      ["creative_angle", "Сценарный угол / хук"],
      ["duration", "Длительность"],
      ["proof_type", "Тип доказательства"],
      ["cta_style", "CTA"],
    ])),
    field(
      "Размер пакета",
      select("mini_ai_batch_size", [
        ["4", "4 запуска"],
        ["6", "6 запусков"],
        ["8", "8 запусков"],
        ["9", "9 запусков"],
        ["12", "12 запусков"],
      ]),
      "Три arm требуют минимум шесть запусков. Очередь всё равно разбита на волны.",
    ),
    field(
      "Лимит пакета, $",
      numberInput("mini_ai_budget_usd", 20, 1, 1_000, 0.01),
      "Это дополнительный стоп. Серверные лимиты кампании остаются главными.",
    ),
    field("Состояние воронки", select("mini_ai_funnel", [
      ["creative", "Контент / первый экран — тест нужен"],
      ["scale", "Можно масштабировать с контролем"],
      ["observe", "Наблюдать, bounded-тест допустим"],
      ["supply", "Риск OOS / поставка"],
      ["expectation", "Чинить выкуп / ожидание"],
      ["advertising", "Оптимизировать рекламу"],
      ["measurement", "Мало данных"],
    ])),
    check("mini_ai_new_category", "Новая категория: игнорировать старого winner", true),
  );
  const advanced = el("details", "mini-ai-advanced");
  advanced.append(el("summary", "", "Подтверждённый winner — необязательно"));
  const extra = el("div", "mini-ai-setup-grid");
  extra.append(
    field("Winner-угол", select("mini_ai_winner_angle", [
      ["", "Нет подтверждённого winner"],
      ["demonstration", "Демонстрация"],
      ["product_focus", "Товар в центре"],
      ["problem_first", "Проблема первой"],
      ["result_first", "Результат первым"],
      ["trust_builder", "Доверительная подача"],
    ])),
    field("Winner-длительность", select("mini_ai_winner_duration", [
      ["", "Не подтверждена"],
      ["2", "2 секунды"],
      ["4", "4 секунды"],
      ["5", "5 секунд"],
      ["8", "8 секунд"],
      ["10", "10 секунд"],
      ["12", "12 секунд"],
      ["15", "15 секунд"],
    ])),
  );
  advanced.append(extra);
  const footer = el("div", "mini-ai-space__footer");
  footer.append(action("Собрать управляемый план", "build-plan", "btn btn-primary"));
  space.append(grid, advanced, footer);
  return space;
}

function buildPanel(form) {
  const panel = el("section", "mini-ai-desk");
  panel.dataset.miniAiDeskV3 = "true";
  const head = el("header", "mini-ai-desk__head");
  const title = el("div", "mini-ai-desk__title");
  title.append(
    el("span", "mini-ai-desk__eyebrow", "МИНИ‑ИИ · УПРАВЛЯЕМЫЙ ЦИКЛ"),
    el("strong", "", "Массовая генерация, которая обязана сделать вывод"),
    el("small", "", "План → волна → QA‑стоп → следующая волна → метрики → решение."),
  );
  const badge = el("span", "mini-ai-desk__status", "Настройте вопрос");
  badge.dataset.miniAiStatus = "true";
  head.append(title, badge);
  const nav = el("nav", "mini-ai-desk__nav");
  const labels = { setup: "1 · Задача", plan: "2 · План", queue: "3 · Волны", conclusion: "4 · Вывод" };
  TABS.forEach((key) => {
    const button = action(labels[key], `tab:${key}`, "mini-ai-tab");
    button.dataset.miniAiTab = key;
    nav.append(button);
  });
  panel.append(head, nav, buildSetup(form));
  ["plan", "queue", "conclusion"].forEach((key) => {
    const space = el("section", "mini-ai-space");
    space.dataset.miniAiSpace = key;
    panel.append(space);
  });
  const rules = el("details", "mini-ai-rules");
  rules.append(el("summary", "", "Понятный свод правил мини‑ИИ"));
  const list = el("ol", "mini-ai-rules__list");
  MINI_AI_RULEBOOK_RU.forEach((item) => list.append(el("li", "", item)));
  rules.append(list);
  panel.append(rules);
  panel.addEventListener("click", onClick);
  panel.addEventListener("input", onChange, { passive: true });
  panel.addEventListener("change", onChange, { passive: true });
  const anchor = form.querySelector("[data-generation-duration-advisor]")
    || form.querySelector("#generation-duration-field")
    || form.querySelector("#generation-brief-assist")
    || form.firstElementChild;
  anchor?.after(panel);
  return panel;
}

function onChange(event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
  if (target.name.startsWith("mini_ai_result_")) return;
  saveState({
    settings: {
      category: String(control("mini_ai_learning_category", "")),
      objective: String(control("mini_ai_objective", "orders")),
      dimension: String(control("mini_ai_dimension", "auto")),
      batch: String(control("mini_ai_batch_size", "6")),
      budget: String(control("mini_ai_budget_usd", "20")),
      funnel: String(control("mini_ai_funnel", "creative")),
      newCategory: control("mini_ai_new_category", true) === true,
      winnerAngle: String(control("mini_ai_winner_angle", "")),
      winnerDuration: String(control("mini_ai_winner_duration", "")),
    },
  });
}

function applySettings(settings = {}) {
  const values = {
    mini_ai_learning_category: settings.category,
    mini_ai_objective: settings.objective,
    mini_ai_dimension: settings.dimension,
    mini_ai_batch_size: settings.batch,
    mini_ai_budget_usd: settings.budget,
    mini_ai_funnel: settings.funnel,
    mini_ai_winner_angle: settings.winnerAngle,
    mini_ai_winner_duration: settings.winnerDuration,
  };
  Object.entries(values).forEach(([name, value]) => {
    if (value === undefined || value === null || value === "") return;
    const target = runtime.panel?.querySelector(`[name="${CSS.escape(name)}"]`);
    if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement) {
      target.value = String(value);
    }
  });
  const newCategory = runtime.panel?.querySelector('[name="mini_ai_new_category"]');
  if (newCategory instanceof HTMLInputElement && typeof settings.newCategory === "boolean") {
    newCategory.checked = settings.newCategory;
  }
}

function dimensionLabel(value) {
  return { creative_angle: "сценарный угол", duration: "длительность", proof_type: "тип доказательства", cta_style: "CTA" }[value] || value;
}

function renderPlan() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="plan"]');
  if (!space) return;
  space.replaceChildren();
  const plan = readState().plan;
  if (!plan) {
    space.append(el("p", "mini-ai-empty", "Сначала соберите план."));
    return;
  }
  const summary = el("div", "mini-ai-plan-summary");
  summary.append(
    el("span", "mini-ai-kicker", plan.executable ? "ПЛАН ГОТОВ" : "ПЛАН ОСТАНОВЛЕН"),
    el("strong", "", plan.executable ? `${plan.batchSize} запусков · ${dimensionLabel(plan.dimension)}` : plan.blockers?.[0]),
    el("small", "", plan.executable
      ? `Оценка $${miniAiEstimatedCostUsd(plan).toFixed(2)} · по одному job за раз · проверка после каждой волны`
      : "Мини‑ИИ отказался использовать неправильный рычаг."),
  );
  space.append(summary);
  if (!plan.executable) {
    space.append(action("Вернуться к задаче", "tab:setup", "btn btn-primary"));
    return;
  }
  const cards = el("div", "mini-ai-arms");
  plan.arms.forEach((arm, index) => {
    const card = el("article", "mini-ai-arm");
    if (arm.control) card.classList.add("is-control");
    card.append(
      el("span", "mini-ai-arm__index", arm.control ? "CONTROL" : `ARM ${index + 1}`),
      el("strong", "", arm.label),
      el("p", "", arm.instruction),
      el("small", "", `${arm.plannedCount} запуска · ${arm.durationSeconds} сек. · ${Math.round(arm.allocation * 100)}%`),
    );
    cards.append(card);
  });
  const footer = el("div", "mini-ai-space__footer");
  footer.append(action("Назад", "tab:setup"), action("Подготовить волны", "prepare-queue", "btn btn-primary"));
  space.append(cards, footer);
}

function makeTasks(plan) {
  const left = plan.arms.map((arm) => arm.plannedCount);
  const tasks = [];
  let wave = 0;
  let ordinal = 0;
  while (left.some((value) => value > 0)) {
    wave += 1;
    plan.arms.forEach((arm, index) => {
      if (left[index] < 1) return;
      ordinal += 1;
      tasks.push({
        taskId: `${plan.planId}-${ordinal}`,
        armId: arm.armId,
        wave,
        status: "pending",
        jobId: "",
        error: "",
      });
      left[index] -= 1;
    });
  }
  return tasks;
}

function recoverExecution(state) {
  const execution = state.execution;
  if (!execution?.tasks?.some((task) => task.status === "running") && execution?.status !== "running") return state;
  execution.tasks.forEach((task) => {
    if (task.status !== "running") return;
    task.status = "unknown";
    task.error = "Вкладка закрылась до подтверждения job. Проверьте штатную очередь и не повторяйте оплату.";
  });
  execution.status = "paused";
  execution.autopilot = false;
  execution.currentTaskId = "";
  return saveState({ execution });
}

function activeWave(execution) {
  const pending = execution.tasks.filter((task) => task.status === "pending");
  return pending.length ? Math.min(...pending.map((task) => task.wave)) : execution.approvedWave + 1;
}

function tasksOfWave(execution, wave) {
  return execution.tasks.filter((task) => task.wave === wave);
}

function waveReady(execution, wave) {
  const tasks = tasksOfWave(execution, wave);
  return tasks.length > 0 && tasks.every((task) => task.status === "queued");
}

function queueLabel(value) {
  return { pending: "ожидает", running: "отправляется", queued: "job создан", failed: "ошибка", unknown: "исход неизвестен" }[value] || value;
}

function renderQueue() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="queue"]');
  if (!space) return;
  space.replaceChildren();
  const state = recoverExecution(readState());
  const plan = state.plan;
  const execution = state.execution;
  if (!plan?.executable) {
    space.append(el("p", "mini-ai-empty", "Сначала нужен исполнимый план."));
    return;
  }
  if (!execution?.tasks?.length) {
    const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
    const box = el("div", "mini-ai-confirm");
    box.append(
      el("strong", "", "Создать последовательную очередь"),
      el("p", "", `Верхняя оценка $${miniAiEstimatedCostUsd(plan).toFixed(2)}. После каждой волны новая оплата блокируется до QA.`),
      field("Введите подтверждение", textInput("mini_ai_confirmation", "", expected)),
      check("mini_ai_acknowledge", "Подтверждаю общий лимит и понимаю, что каждый job платный"),
      check("mini_ai_autopilot", "Автопилот только внутри волны — строго после появления предыдущего job", true),
      action("Создать очередь", "confirm-queue", "btn btn-primary"),
    );
    space.append(box);
    return;
  }
  const queued = execution.tasks.filter((task) => task.status === "queued").length;
  const head = el("div", "mini-ai-queue-head");
  head.append(
    el("strong", "", `Подтверждено job: ${queued} / ${execution.tasks.length}`),
    el("small", "", execution.status === "awaiting_qa"
      ? `Волна ${execution.awaitingWave} ждёт проверки. Следующая оплата заблокирована.`
      : execution.status === "running"
        ? "Работает один штатный запуск."
        : execution.status === "completed"
          ? "Все волны проверены и отправлены."
          : execution.status === "stopped"
            ? `Пакет остановлен: ${execution.stopReason}`
            : "Очередь на безопасной паузе."),
  );
  const bar = el("div", "mini-ai-progress");
  bar.style.setProperty("--mini-ai-progress", `${queued / execution.tasks.length * 100}%`);
  head.append(bar);
  const list = el("div", "mini-ai-queue-list");
  execution.tasks.forEach((task, index) => {
    const arm = plan.arms.find((item) => item.armId === task.armId);
    const row = el("article", "mini-ai-queue-item");
    row.dataset.state = task.status;
    row.append(
      el("span", "mini-ai-queue-item__number", String(index + 1)),
      el("strong", "", `Волна ${task.wave} · ${arm?.label || task.armId}`),
      el("small", "", task.jobId ? `job ${task.jobId}` : task.error || queueLabel(task.status)),
      el("span", "mini-ai-queue-item__status", queueLabel(task.status)),
    );
    list.append(row);
  });
  const footer = el("div", "mini-ai-space__footer");
  if (execution.status === "paused" && execution.tasks.some((task) => task.status === "pending")) {
    footer.append(action(`Запустить волну ${activeWave(execution)}`, "run-wave", "btn btn-primary"));
  } else if (execution.status === "running") {
    footer.append(action("Выключить автопилот после текущего job", "pause-autopilot"));
  } else if (execution.status === "awaiting_qa") {
    const gate = el("div", "mini-ai-wave-gate");
    gate.append(
      el("strong", "", `Проверка волны ${execution.awaitingWave}`),
      el("p", "", "Посмотрите каждый ролик. Один неверный товар или общий технический дефект должен остановить оставшийся пакет."),
      check("mini_ai_wave_product_ok", "Точный товар и упаковка сохранены во всех роликах волны"),
      check("mini_ai_wave_technical_ok", "Нет общего технического дефекта, который повторится дальше"),
      field("Подтверждение", textInput("mini_ai_wave_confirmation", "", `ПРОВЕРЕНО ${execution.awaitingWave}`)),
    );
    const gateActions = el("div", "mini-ai-space__footer");
    gateActions.append(
      action("Остановить пакет по дефекту", "stop-quality", "btn btn-danger btn-small"),
      action("Подтвердить волну и продолжить", "approve-wave", "btn btn-primary"),
    );
    gate.append(gateActions);
    footer.append(gate);
  } else if (execution.status === "completed") {
    footer.append(action("Перейти к выводу", "tab:conclusion", "btn btn-primary"));
  }
  footer.append(action("Сбросить только локальную очередь", "reset-queue", "btn btn-ghost btn-small"));
  space.append(head, list, footer);
}

function renderConclusion() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="conclusion"]');
  if (!space) return;
  space.replaceChildren();
  const state = readState();
  const plan = state.plan;
  if (!plan?.executable) {
    space.append(el("p", "mini-ai-empty", "Сначала выполните план."));
    return;
  }
  space.append(el("p", "mini-ai-space__intro", "Введите зрелые итоги после QA и окна атрибуции. Просмотры — только диагностика."));
  const saved = state.results || {};
  const grid = el("div", "mini-ai-result-grid");
  plan.arms.forEach((arm) => {
    const values = saved[arm.armId] || {};
    const card = el("article", "mini-ai-result-card");
    card.append(el("span", "mini-ai-arm__index", arm.control ? "CONTROL" : "HYPOTHESIS"), el("strong", "", arm.label));
    const fields = el("div", "mini-ai-result-fields");
    [
      ["eligible", "Зрелых результатов", values.eligible ?? 0, 0, 50, 1],
      ["failed", "Тех. ошибок", values.failed ?? 0, 0, 50, 1],
      ["qaRejected", "Не прошли QA", values.qaRejected ?? 0, 0, 50, 1],
      ["critical", "Критических блокеров", values.critical ?? 0, 0, 50, 1],
      ["mismatch", "Подмен товара", values.mismatch ?? 0, 0, 50, 1],
      ["orders", "Заказы", values.orders ?? 0, 0, 1_000_000, 1],
      ["carts", "Корзины", values.carts ?? 0, 0, 1_000_000, 1],
      ["salesRub", "Продажи, ₽", values.salesRub ?? 0, 0, 1_000_000_000, 0.01],
      ["spendRub", "Расход, ₽", values.spendRub ?? 0, 0, 1_000_000_000, 0.01],
      ["days", "Сумма дней", values.days ?? 1, 1, 10_000, 1],
      ["views", "Просмотры · диагност.", values.views ?? 0, 0, 1_000_000_000, 1],
    ].forEach(([name, label, initial, min, max, step]) => {
      const input = numberInput(`mini_ai_result_${name}`, initial, min, max, step);
      input.dataset.resultField = name;
      input.dataset.armId = arm.armId;
      fields.append(field(label, input));
    });
    card.append(fields);
    grid.append(card);
  });
  const buttons = el("div", "mini-ai-space__footer");
  buttons.append(action("Сохранить результаты", "save-results"), action("Сделать вывод", "evaluate", "btn btn-primary"));
  const output = el("div", "mini-ai-conclusion-output");
  if (state.conclusion) renderOutput(output, state.conclusion, plan);
  space.append(grid, buttons, output);
}

function renderOutput(target, conclusion, plan) {
  target.replaceChildren();
  target.dataset.decision = conclusion.decision;
  const winner = plan.arms.find((arm) => arm.armId === conclusion.winnerArmId);
  target.append(el("span", "mini-ai-kicker", conclusion.decision.toUpperCase()), el("strong", "", conclusion.summary), el("p", "", conclusion.nextAction));
  if (winner) target.append(el("p", "mini-ai-winner", `Выбранный arm: ${winner.label}`));
  if (conclusion.evidence?.length) {
    const list = el("ul", "mini-ai-evidence");
    conclusion.evidence.forEach((item) => list.append(el("li", "", item)));
    target.append(list);
  }
  target.append(el("small", "", `Уверенность: ${conclusion.confidence}. Наблюдение не объявляется причинностью.`));
  if (conclusion.decision === "promote_with_control") {
    target.append(action("Подтвердить winner и открыть следующий вопрос", "accept-winner", "btn btn-primary"));
  }
}

function renderAll() {
  const state = recoverExecution(readState());
  applySettings(state.settings || {});
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab(state.activeTab || "setup", false);
  if (state.plan?.executable) status("План сохранён", "ready");
}

function buildPlan() {
  const form = runtime.form;
  if (!(form instanceof HTMLFormElement)) return;
  const brief = validateBrief(form);
  if (!brief.ready) {
    status(brief.blockers[0], "warning");
    form.elements.brief?.focus({ preventScroll: false });
    return;
  }
  const plan = buildMiniAiPlan(contextFromForm(form));
  saveState({
    plan,
    baseBrief: brief.brief,
    baseBriefHash: briefHash(brief.brief),
    execution: null,
    results: {},
    conclusion: null,
    activeTab: "plan",
  });
  renderAll();
  setTab("plan");
  status(plan.executable ? "План готов" : "План остановлен", plan.executable ? "ready" : "warning");
}

function confirmQueue() {
  const state = readState();
  const plan = state.plan;
  if (!plan?.executable) return;
  const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
  if (String(control("mini_ai_confirmation", "")).trim().toUpperCase() !== expected || control("mini_ai_acknowledge", false) !== true) {
    status(`Введите «${expected}» и подтвердите лимит`, "warning");
    return;
  }
  saveState({
    execution: {
      status: "paused",
      autopilot: control("mini_ai_autopilot", true) === true,
      tasks: makeTasks(plan),
      approvedWave: 0,
      awaitingWave: null,
      currentTaskId: "",
      stopReason: "",
      waveReviews: [],
    },
    activeTab: "queue",
  });
  renderQueue();
  setTab("queue");
  status("Очередь готова", "ready");
}

function jobSnapshot() {
  return new Map(
    [...document.querySelectorAll("[data-generation-job-id]")]
      .map((element) => [String(element.dataset.generationJobId || "").trim(), element])
      .filter(([id]) => id),
  );
}

function newMatchingJob(before, sku, duration) {
  const targetSku = normalize(sku);
  const durationText = `${Number(duration)} секунд`;
  return [...jobSnapshot().entries()]
    .find(([id, element]) => {
      if (before.has(id)) return false;
      const text = normalize(element.textContent);
      return text.includes(targetSku) && text.includes(durationText);
    })?.[0] || "";
}

function waitForJob(before, sku, duration) {
  const started = Date.now();
  return new Promise((resolve) => {
    const timer = window.setInterval(() => {
      const id = newMatchingJob(before, sku, duration);
      if (id || Date.now() - started >= JOB_WAIT_MS) {
        window.clearInterval(timer);
        resolve(id);
      }
    }, JOB_POLL_MS);
  });
}

function dispatch(controlNode) {
  controlNode?.dispatchEvent(new Event("input", { bubbles: true }));
  controlNode?.dispatchEvent(new Event("change", { bubbles: true }));
}

function frame() {
  return new Promise((resolve) => window.requestAnimationFrame(resolve));
}

function armBrief(base, arm, mode) {
  let value = String(base || "").replace(/(длительностью\s+)\d+(\s+секунд)/giu, `$1${arm.durationSeconds}$2`);
  value = `${value}\n${arm.instruction}`.trim();
  if (value.length > MAX_BRIEF) throw new Error(`ТЗ вместе с arm длиннее ${MAX_BRIEF} символов.`);
  if (mode === "real_seedance") {
    const match = value.match(/Реплика героя дословно:\s*«([^»]+)»/iu);
    const words = match ? (match[1].match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || []).length : 0;
    const limit = Math.max(10, Math.min(42, Math.floor(arm.durationSeconds * 22 / 8)));
    if (words > limit) throw new Error(`Для ${arm.durationSeconds} секунд оставьте не больше ${limit} слов; сейчас ${words}.`);
  }
  return value;
}

async function prepareNative(form, plan, arm, base) {
  const duration = form.elements.duration_seconds;
  const brief = form.elements.brief;
  if (!(duration instanceof HTMLSelectElement)) throw new Error("Не найден выбор длительности.");
  if (!(brief instanceof HTMLTextAreaElement || brief instanceof HTMLInputElement)) throw new Error("Не найдено настоящее поле ТЗ.");
  duration.value = String(arm.durationSeconds);
  dispatch(duration);
  await frame();
  await frame();
  brief.value = armBrief(base, arm, plan.context.mode);
  dispatch(brief);
  const count = form.elements.count;
  if (count instanceof HTMLInputElement || count instanceof HTMLSelectElement) {
    count.value = "1";
    dispatch(count);
  }
  await frame();
  const confirmation = form.elements.real_spend_confirmation;
  if (!(confirmation instanceof HTMLInputElement)) throw new Error("Не найдено подтверждение платного запуска.");
  confirmation.checked = true;
  dispatch(confirmation);
  await frame();
  if (!form.checkValidity()) {
    form.reportValidity();
    throw new Error("Штатная форма не готова. Заполните обязательные поля.");
  }
}

function sameContext(plan, form) {
  const current = contextFromForm(form);
  return current.learningCategoryKey === plan.context.learningCategoryKey
    && current.sku === plan.context.sku
    && current.platform === plan.context.platform
    && current.mode === plan.context.mode;
}

function scheduleNext() {
  window.clearTimeout(runtime.nextTimer);
  runtime.nextTimer = window.setTimeout(() => {
    runtime.nextTimer = 0;
    void runNext();
  }, 1_500);
}

async function runNext() {
  if (runtime.running) return;
  runtime.running = true;
  let continueWave = false;
  try {
    let state = recoverExecution(readState());
    const plan = state.plan;
    const execution = state.execution;
    if (!plan?.executable || !execution?.tasks?.length) return;
    if (["awaiting_qa", "stopped", "completed"].includes(execution.status)) return;
    const wave = activeWave(execution);
    const task = tasksOfWave(execution, wave).find((item) => item.status === "pending");
    if (!task) {
      if (waveReady(execution, wave)) {
        execution.status = "awaiting_qa";
        execution.awaitingWave = wave;
        saveState({ execution });
        renderQueue();
        status(`Волна ${wave} ждёт QA`, "warning");
      }
      return;
    }
    const form = document.querySelector(FORM_SELECTOR);
    if (!(form instanceof HTMLFormElement)) throw new Error("Штатная форма генерации исчезла.");
    if (!sameContext(plan, form)) throw new Error("SKU, категория, площадка или модель изменились.");
    if (form.dataset.busy === "true") throw new Error("Штатная форма занята другим запуском.");
    if (state.baseBriefHash !== briefHash(state.baseBrief || "")) throw new Error("Базовое ТЗ повреждено. Соберите план заново.");
    const arm = plan.arms.find((item) => item.armId === task.armId);
    if (!arm) throw new Error("Arm отсутствует в плане.");
    execution.status = "running";
    execution.currentTaskId = task.taskId;
    task.status = "running";
    saveState({ execution });
    renderQueue();
    status(`Волна ${wave}: ${arm.label}`, "running");
    const before = new Set(jobSnapshot().keys());
    await prepareNative(form, plan, arm, state.baseBrief);
    const submit = form.querySelector("#generation-submit, button[type='submit']");
    if (!(submit instanceof HTMLElement)) throw new Error("Не найдена штатная кнопка запуска.");
    form.requestSubmit(submit);
    const jobId = await waitForJob(before, plan.context.sku, arm.durationSeconds);
    state = readState();
    const fresh = state.execution;
    const savedTask = fresh?.tasks?.find((item) => item.taskId === task.taskId);
    if (!fresh || !savedTask) return;
    fresh.currentTaskId = "";
    if (!jobId) {
      savedTask.status = "unknown";
      savedTask.error = "За две минуты не найден job с тем же SKU и длительностью. Не повторяйте оплату.";
      fresh.status = "paused";
      fresh.autopilot = false;
      saveState({ execution: fresh });
      renderQueue();
      status("Исход запуска не подтверждён", "warning");
      return;
    }
    savedTask.status = "queued";
    savedTask.jobId = jobId;
    if (waveReady(fresh, wave)) {
      fresh.status = "awaiting_qa";
      fresh.awaitingWave = wave;
    } else {
      fresh.status = "paused";
      continueWave = fresh.autopilot === true;
    }
    saveState({ execution: fresh });
    renderQueue();
    status(fresh.status === "awaiting_qa" ? `Волна ${wave} готова к проверке` : `Job ${compact(jobId, 20)} создан`, fresh.status === "awaiting_qa" ? "warning" : "ready");
  } catch (error) {
    const state = readState();
    const execution = state.execution;
    const task = execution?.tasks?.find((item) => item.taskId === execution.currentTaskId);
    if (task) {
      task.status = "failed";
      task.error = String(error?.message || "Запуск остановлен.");
    }
    if (execution) {
      execution.status = "paused";
      execution.autopilot = false;
      execution.currentTaskId = "";
      saveState({ execution });
    }
    renderQueue();
    status(String(error?.message || "Запуск остановлен"), "warning");
  } finally {
    runtime.running = false;
    if (continueWave) scheduleNext();
  }
}

function approveWave() {
  const state = readState();
  const execution = state.execution;
  const wave = Number(execution?.awaitingWave || 0);
  if (!execution || execution.status !== "awaiting_qa" || !wave) return;
  const expected = `ПРОВЕРЕНО ${wave}`;
  if (
    String(control("mini_ai_wave_confirmation", "")).trim().toUpperCase() !== expected
    || control("mini_ai_wave_product_ok", false) !== true
    || control("mini_ai_wave_technical_ok", false) !== true
  ) {
    status(`Проверьте оба условия и введите «${expected}»`, "warning");
    return;
  }
  execution.waveReviews.push({ wave, productOk: true, technicalOk: true, at: Date.now() });
  execution.approvedWave = wave;
  execution.awaitingWave = null;
  execution.status = execution.tasks.some((task) => task.status === "pending") ? "paused" : "completed";
  saveState({ execution });
  renderQueue();
  status(execution.status === "completed" ? "Все волны проверены" : `Волна ${wave} принята`, "ready");
  if (execution.status === "paused" && execution.autopilot) scheduleNext();
}

function stopQuality() {
  const state = readState();
  const execution = state.execution;
  if (!execution) return;
  execution.status = "stopped";
  execution.autopilot = false;
  execution.stopReason = `Дефект после волны ${execution.awaitingWave || execution.approvedWave + 1}`;
  saveState({ execution });
  renderQueue();
  status("Пакет остановлен по QA", "warning");
}

function resultValues() {
  const result = {};
  runtime.panel?.querySelectorAll("[data-result-field][data-arm-id]").forEach((input) => {
    const armId = input.dataset.armId;
    const name = input.dataset.resultField;
    if (!armId || !name) return;
    result[armId] ||= {};
    result[armId][name] = Number(input.value || 0);
  });
  return result;
}

function distribute(total, index, count) {
  if (!count) return 0;
  return Math.floor(total / count) + (index < total % count ? 1 : 0);
}

function makeOutcomes(plan, results) {
  const output = [];
  plan.arms.forEach((arm) => {
    const value = results[arm.armId] || {};
    const eligible = Math.max(0, Math.floor(value.eligible || 0));
    const rejected = Math.max(0, Math.floor(value.qaRejected || 0));
    const failed = Math.max(0, Math.floor(value.failed || 0));
    const total = Math.max(eligible + rejected + failed, arm.plannedCount);
    const orders = Math.max(0, Math.floor(value.orders || 0));
    const carts = Math.max(orders, Math.floor(value.carts || 0));
    const sales = Math.round(Math.max(0, Number(value.salesRub || 0)) * 100);
    const spend = Math.round(Math.max(0, Number(value.spendRub || 0)) * 100);
    const days = Math.max(1, Math.floor(value.days || eligible || 1));
    const views = Math.max(0, Math.floor(value.views || 0));
    const mismatch = Math.max(0, Math.floor(value.mismatch || 0));
    const critical = Math.max(0, Math.floor(value.critical || 0));
    for (let index = 0; index < total; index += 1) {
      const isEligible = index < eligible;
      const isRejected = index >= eligible && index < eligible + rejected;
      const isFailed = index >= eligible + rejected && index < eligible + rejected + failed;
      output.push({
        outcomeId: `${plan.planId}-${arm.armId}-${index + 1}`,
        jobId: `aggregate-${arm.armId}-${index + 1}`,
        armId: arm.armId,
        state: isEligible || isRejected ? "succeeded" : isFailed ? "failed" : "queued",
        qaState: isEligible ? "approved" : isRejected ? "rejected" : "pending",
        productFidelityOk: index >= mismatch,
        criticalBlocker: index < critical,
        published: isEligible,
        metricsMature: isEligible,
        orders: isEligible ? distribute(orders, index, eligible) : null,
        carts: isEligible ? distribute(carts, index, eligible) : null,
        salesMinor: isEligible ? distribute(sales, index, eligible) : null,
        spendMinor: isEligible ? distribute(spend, index, eligible) : null,
        attributionDays: isEligible ? Math.max(1, distribute(days, index, eligible)) : 1,
        views: isEligible ? distribute(views, index, eligible) : null,
      });
    }
  });
  return output;
}

function evaluate() {
  const state = readState();
  if (!state.plan?.executable) return;
  const results = resultValues();
  const conclusion = evaluateMiniAiPlan(state.plan, makeOutcomes(state.plan, results));
  saveState({ results, conclusion });
  renderConclusion();
  status(conclusion.decision === "promote_with_control" ? "Winner найден" : "Вывод готов", "ready");
}

function acceptWinner() {
  const state = readState();
  if (state.conclusion?.decision !== "promote_with_control") return;
  const winner = state.plan.arms.find((arm) => arm.armId === state.conclusion.winnerArmId);
  if (!winner) return;
  const next = { creative_angle: "duration", duration: "proof_type", proof_type: "cta_style", cta_style: "creative_angle" }[state.plan.dimension] || "auto";
  const settings = {
    ...(state.settings || {}),
    newCategory: false,
    winnerAngle: winner.creativeAngle,
    winnerDuration: String(winner.durationSeconds),
    dimension: next,
  };
  saveState({ settings, plan: null, execution: null, results: {}, conclusion: null, activeTab: "setup" });
  applySettings(settings);
  renderAll();
  setTab("setup");
  status("Winner принят человеком; готов следующий вопрос", "ready");
}

function onClick(event) {
  const target = event.target instanceof Element ? event.target.closest("[data-mini-ai-action]") : null;
  if (!(target instanceof HTMLElement)) return;
  const name = String(target.dataset.miniAiAction || "");
  if (name.startsWith("tab:")) setTab(name.slice(4));
  else if (name === "build-plan") buildPlan();
  else if (name === "prepare-queue") { renderQueue(); setTab("queue"); }
  else if (name === "confirm-queue") confirmQueue();
  else if (name === "run-wave") void runNext();
  else if (name === "pause-autopilot") {
    const state = readState();
    if (state.execution) {
      state.execution.autopilot = false;
      saveState({ execution: state.execution });
      renderQueue();
      status("Автопилот выключен; текущий запрос не отменяется", "warning");
    }
  }
  else if (name === "approve-wave") approveWave();
  else if (name === "stop-quality") stopQuality();
  else if (name === "reset-queue") { const state = readState(); saveState({ execution: null, conclusion: null, results: state.results || {} }); renderQueue(); }
  else if (name === "save-results") { saveState({ results: resultValues(), conclusion: null }); status("Результаты сохранены", "ready"); }
  else if (name === "evaluate") evaluate();
  else if (name === "accept-winner") acceptWinner();
}

function mount() {
  window.clearTimeout(runtime.mountTimer);
  runtime.mountTimer = 0;
  if (routePath() !== ROUTE) { runtime.retry = 0; return; }
  const form = document.querySelector(FORM_SELECTOR);
  if (!(form instanceof HTMLFormElement)) {
    if (runtime.retry < 40) {
      runtime.retry += 1;
      runtime.mountTimer = window.setTimeout(mount, 250);
    }
    return;
  }
  runtime.retry = 0;
  runtime.form = form;
  runtime.panel = form.querySelector("[data-mini-ai-desk-v3]") || buildPanel(form);
  renderAll();
}

function scheduleMount() {
  window.clearTimeout(runtime.mountTimer);
  runtime.mountTimer = window.setTimeout(mount, 0);
}

window.addEventListener("hashchange", scheduleMount, { passive: true });
window.addEventListener("contentengine:v4-route-ready", scheduleMount, { passive: true });
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
