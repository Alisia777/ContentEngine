/*
 * ContentEngine mini-AI desk v2.
 *
 * One bounded question -> one plan -> wave-gated sequential launches -> human
 * QA checkpoint -> mature metrics -> deterministic conclusion. The desk never
 * calls Supabase or a provider directly. Every paid launch still travels
 * through the native form and its server-side budget, identity, policy,
 * idempotency and QA gates.
 */

import {
  MINI_AI_RULEBOOK_RU,
  buildMiniAiPlan,
  evaluateMiniAiPlan,
  miniAiEstimatedCostUsd,
} from "./mini-ai-control-plane-v2.js?v=20260801.2";

const ROUTE = "/workspace/generation";
const FORM_SELECTOR = "#mock-batch-form";
const STORAGE_KEY = "contentengine.mini-ai-control.v2";
const MAX_BRIEF_LENGTH = 1_200;
const JOB_WAIT_MS = 120_000;
const JOB_POLL_MS = 600;
const MOUNT_RETRY_MS = 250;
const MOUNT_RETRY_LIMIT = 40;
const TABS = Object.freeze(["setup", "plan", "queue", "conclusion"]);

const runtime = {
  panel: null,
  form: null,
  activeTab: "setup",
  running: false,
  mountAttempts: 0,
  mountTimer: 0,
  nextTimer: 0,
};

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function node(tag, className = "", text = "") {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text) result.textContent = text;
  return result;
}

function actionButton(label, action, className = "btn btn-secondary btn-small") {
  const result = node("button", className, label);
  result.type = "button";
  result.dataset.miniAiAction = action;
  return result;
}

function field(label, control, hint = "") {
  const wrapper = node("label", "mini-ai-field");
  wrapper.append(node("span", "mini-ai-field__label", label), control);
  if (hint) wrapper.append(node("small", "mini-ai-field__hint", hint));
  return wrapper;
}

function selectControl(name, values) {
  const control = node("select", "mini-ai-control");
  control.name = name;
  values.forEach(([value, label]) => {
    const option = node("option", "", label);
    option.value = value;
    control.append(option);
  });
  return control;
}

function inputControl(name, value = "", placeholder = "") {
  const control = node("input", "mini-ai-control");
  control.type = "text";
  control.name = name;
  control.value = String(value);
  control.placeholder = placeholder;
  control.autocomplete = "off";
  return control;
}

function numberControl(name, value, min, max, step = 1) {
  const control = node("input", "mini-ai-control");
  control.type = "number";
  control.name = name;
  control.value = String(value);
  control.min = String(min);
  control.max = String(max);
  control.step = String(step);
  return control;
}

function checkboxControl(name, label, checked = false) {
  const wrapper = node("label", "mini-ai-check");
  const control = node("input");
  control.type = "checkbox";
  control.name = name;
  control.checked = checked;
  wrapper.append(control, node("span", "", label));
  return wrapper;
}

function compact(value, limit = 150) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function normalize(value) {
  return String(value || "")
    .replace(/\s+/gu, " ")
    .trim()
    .toLocaleLowerCase("ru-RU");
}

function readStore() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function writeStore(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // The durable provider jobs remain server-owned even if browser memory is unavailable.
  }
}

function organizationKey() {
  return String(
    window.CONTENTENGINE_CONFIG?.ORGANIZATION_ID
      || window.CONTENTENGINE_CONFIG?.ORGANIZATION_SLUG
      || window.location.host,
  ).trim();
}

function panelValue(name, fallback = "") {
  const control = runtime.panel?.querySelector(`[name="${CSS.escape(name)}"]`);
  if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
    return control.type === "checkbox" ? control.checked : control.value;
  }
  return fallback;
}

function learningCategory(form = runtime.form) {
  return String(
    panelValue("mini_ai_learning_category")
      || form?.elements?.product_category?.value
      || "",
  ).trim().toLowerCase();
}

function scopeKey(form = runtime.form) {
  return [
    organizationKey(),
    learningCategory(form),
    String(form?.elements?.sku?.value || "").trim(),
    String(form?.elements?.platform?.value || "").trim().toLowerCase(),
    String(form?.elements?.generation_mode?.value || "").trim(),
  ].join("|");
}

function currentState(form = runtime.form) {
  const value = readStore()[scopeKey(form)];
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function saveState(patch, form = runtime.form) {
  const store = readStore();
  const key = scopeKey(form);
  store[key] = {
    ...(store[key] || {}),
    ...patch,
    updatedAt: Date.now(),
  };
  writeStore(store);
  return store[key];
}

function modeSpec(mode) {
  if (mode === "real_gen4") {
    return { label: "Gen‑4 Turbo", allowed: [2, 5, 8, 10], pricePerSecond: 5 };
  }
  if (mode === "real_seedance") {
    return { label: "Seedance 2 Fast", allowed: [4, 8, 12, 15], pricePerSecond: 29 };
  }
  return null;
}

function readServerExperimentPolicy(form) {
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

function formContext(form) {
  const mode = String(form.elements.generation_mode?.value || "").trim();
  const spec = modeSpec(mode);
  const duration = Number(form.elements.duration_seconds?.value || 0);
  const maxBudgetUsd = Number(panelValue("mini_ai_budget_usd", 0));
  return {
    organizationKey: organizationKey(),
    learningCategoryKey: learningCategory(form),
    sku: String(form.elements.sku?.value || "").trim(),
    platform: String(form.elements.platform?.value || "").trim().toLowerCase(),
    mode,
    providerModel: spec ? mode : "",
    objective: String(panelValue("mini_ai_objective", "orders")),
    riskPreset: String(panelValue("mini_ai_risk", "balanced")),
    requestedDimension: String(panelValue("mini_ai_dimension", "auto")),
    requestedBatchSize: Number(panelValue("mini_ai_batch_size", 6)),
    unitCostMinor: spec?.allowed.includes(duration)
      ? duration * spec.pricePerSecond
      : 0,
    maxBudgetMinor: Number.isFinite(maxBudgetUsd) && maxBudgetUsd > 0
      ? Math.round(maxBudgetUsd * 100)
      : 0,
    funnelDecision: String(panelValue("mini_ai_funnel", "creative")),
    categoryIsNew: panelValue("mini_ai_new_category", true) === true,
    approvedWinnerAngle: String(panelValue("mini_ai_winner_angle", "")).trim(),
    approvedWinnerDuration: Number(panelValue("mini_ai_winner_duration", 0)) || null,
    durationPolicy: readServerExperimentPolicy(form),
  };
}

function baseBrief(form) {
  return String(form.elements.brief?.value || "").trim();
}

function validateBaseBrief(form) {
  const brief = baseBrief(form);
  const sku = String(form.elements.sku?.value || "").trim();
  const productName = String(form.elements.product_name?.value || "").trim();
  const normalizedBrief = normalize(brief);
  const blockers = [];
  if (brief.length < 80) blockers.push("Сначала подготовьте безопасное ТЗ длиной хотя бы 80 символов.");
  if (!sku || !productName) blockers.push("Выберите точный SKU и название товара.");
  if (sku && !normalizedBrief.includes(normalize(sku))) {
    blockers.push("ТЗ не содержит точный SKU. Восстановите авто‑ТЗ перед массовым запуском.");
  }
  if (productName && !normalizedBrief.includes(normalize(productName))) {
    blockers.push("ТЗ не содержит точное название товара.");
  }
  if (!normalizedBrief.includes("точный товар:")) {
    blockers.push("ТЗ не прошло контракт точного товара: отсутствует строка «Точный товар:».");
  }
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

function nativeContextMatches(plan, form) {
  const current = formContext(form);
  return (
    current.learningCategoryKey === plan.context.learningCategoryKey
    && current.sku === plan.context.sku
    && current.platform === plan.context.platform
    && current.mode === plan.context.mode
  );
}

function status(text, tone = "idle") {
  const target = runtime.panel?.querySelector("[data-mini-ai-status]");
  if (!target) return;
  target.textContent = text;
  target.dataset.tone = tone;
}

function setTab(key, { persist = true } = {}) {
  const resolved = TABS.includes(key) ? key : "setup";
  runtime.activeTab = resolved;
  runtime.panel?.querySelectorAll("[data-mini-ai-tab]").forEach((control) => {
    const active = control.dataset.miniAiTab === resolved;
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-pressed", String(active));
  });
  runtime.panel?.querySelectorAll("[data-mini-ai-space]").forEach((space) => {
    const active = space.dataset.miniAiSpace === resolved;
    space.hidden = !active;
    space.classList.toggle("is-active", active);
  });
  if (persist) saveState({ activeTab: resolved });
}

function buildSetupSpace(form) {
  const space = node("section", "mini-ai-space");
  space.dataset.miniAiSpace = "setup";
  space.append(node(
    "p",
    "mini-ai-space__intro",
    "Один массовый цикл отвечает только на один вопрос. Товар, площадка, исходники и claims остаются одинаковыми.",
  ));
  const grid = node("div", "mini-ai-setup-grid");
  grid.append(
    field(
      "Категория обучения *",
      inputControl(
        "mini_ai_learning_category",
        String(form.elements.product_category?.value || "").trim().toLowerCase(),
        "например: car_audio_amplifier",
      ),
      "Используйте узкую продуктовую категорию. Winner другой категории сюда не переносится.",
    ),
    field("Цель", selectControl("mini_ai_objective", [
      ["orders", "Заказы в день"],
      ["sales", "Продажи в день"],
      ["conversion", "Конверсия корзина → заказ"],
      ["qa_acceptance", "Принятие QA"],
      ["cost_per_order", "Стоимость заказа"],
    ])),
    field("Один вопрос цикла", selectControl("mini_ai_dimension", [
      ["auto", "Мини‑ИИ выберет следующий вопрос"],
      ["creative_angle", "Сценарный угол / хук"],
      ["duration", "Длительность"],
      ["proof_type", "Тип доказательства"],
      ["cta_style", "CTA"],
    ])),
    field("Профиль риска", selectControl("mini_ai_risk", [
      ["conservative", "Консервативный"],
      ["balanced", "Сбалансированный"],
      ["exploratory", "Исследовательский"],
    ])),
    field(
      "Размер пакета",
      selectControl("mini_ai_batch_size", [
        ["4", "4 запуска"],
        ["6", "6 запусков"],
        ["8", "8 запусков"],
        ["9", "9 запусков"],
        ["12", "12 запусков"],
      ]),
      "Три варианта требуют минимум шесть запусков. Пакет всё равно идёт волнами.",
    ),
    field(
      "Жёсткий лимит пакета, $",
      numberControl("mini_ai_budget_usd", 20, 1, 1_000, 0.01),
      "Это дополнительный локальный стоп. Серверные лимиты кампании остаются главными.",
    ),
    field("Что говорит воронка", selectControl("mini_ai_funnel", [
      ["creative", "Контент / первый экран — тест нужен"],
      ["scale", "Можно масштабировать с контролем"],
      ["observe", "Наблюдать, bounded-тест допустим"],
      ["supply", "Риск OOS / поставка"],
      ["expectation", "Чинить выкуп / ожидание"],
      ["advertising", "Оптимизировать рекламу"],
      ["measurement", "Мало данных"],
    ])),
    checkboxControl(
      "mini_ai_new_category",
      "Новая категория: полностью игнорировать старого winner",
      true,
    ),
  );
  const advanced = node("details", "mini-ai-advanced");
  advanced.append(node("summary", "", "Уже подтверждённый winner — необязательно"));
  const advancedGrid = node("div", "mini-ai-setup-grid");
  advancedGrid.append(
    field("Winner-угол", selectControl("mini_ai_winner_angle", [
      ["", "Нет подтверждённого winner"],
      ["demonstration", "Демонстрация"],
      ["product_focus", "Товар в центре"],
      ["problem_first", "Проблема первой"],
      ["result_first", "Результат первым"],
      ["trust_builder", "Доверительная подача"],
    ])),
    field("Winner-длительность", selectControl("mini_ai_winner_duration", [
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
  advanced.append(advancedGrid);
  const footer = node("div", "mini-ai-space__footer");
  footer.append(actionButton("Собрать управляемый план", "build-plan", "btn btn-primary"));
  space.append(grid, advanced, footer);
  return space;
}

function buildPanel(form) {
  const panel = node("section", "mini-ai-desk");
  panel.dataset.miniAiDeskV2 = "true";
  panel.setAttribute("aria-label", "Управляемый мини-ИИ массовой генерации");
  const head = node("header", "mini-ai-desk__head");
  const title = node("div", "mini-ai-desk__title");
  title.append(
    node("span", "mini-ai-desk__eyebrow", "МИНИ‑ИИ · УПРАВЛЯЕМЫЙ ЦИКЛ"),
    node("strong", "", "Не «сгенерировать много», а проверить гипотезу"),
    node("small", "", "План → волна → контроль QA → следующая волна → зрелые метрики → вывод."),
  );
  const badge = node("span", "mini-ai-desk__status", "Настройте вопрос");
  badge.dataset.miniAiStatus = "true";
  head.append(title, badge);

  const nav = node("nav", "mini-ai-desk__nav");
  const labels = {
    setup: "1 · Задача",
    plan: "2 · План",
    queue: "3 · Волны",
    conclusion: "4 · Вывод",
  };
  TABS.forEach((key) => {
    const control = actionButton(labels[key], `tab:${key}`, "mini-ai-tab");
    control.dataset.miniAiTab = key;
    nav.append(control);
  });

  panel.append(head, nav, buildSetupSpace(form));
  for (const key of ["plan", "queue", "conclusion"]) {
    const space = node("section", "mini-ai-space");
    space.dataset.miniAiSpace = key;
    panel.append(space);
  }
  const rules = node("details", "mini-ai-rules");
  rules.append(node("summary", "", "Понятный свод правил мини‑ИИ"));
  const list = node("ol", "mini-ai-rules__list");
  MINI_AI_RULEBOOK_RU.forEach((item) => list.append(node("li", "", item)));
  rules.append(list);
  panel.append(rules);
  panel.addEventListener("click", onPanelClick);
  panel.addEventListener("change", onPanelChange, { passive: true });
  panel.addEventListener("input", onPanelChange, { passive: true });

  const anchor = form.querySelector("[data-generation-duration-advisor]")
    || form.querySelector("#generation-duration-field")
    || form.querySelector("#generation-brief-assist")
    || form.firstElementChild;
  anchor?.after(panel);
  return panel;
}

function onPanelChange(event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
  if (target.name === "mini_ai_learning_category") target.dataset.touched = "true";
  if (target.name.startsWith("mini_ai_result_")) return;
  const settings = {
    learningCategory: String(panelValue("mini_ai_learning_category", "")),
    objective: String(panelValue("mini_ai_objective", "orders")),
    risk: String(panelValue("mini_ai_risk", "balanced")),
    dimension: String(panelValue("mini_ai_dimension", "auto")),
    batchSize: String(panelValue("mini_ai_batch_size", "6")),
    budgetUsd: String(panelValue("mini_ai_budget_usd", "20")),
    funnel: String(panelValue("mini_ai_funnel", "creative")),
    newCategory: panelValue("mini_ai_new_category", true) === true,
    winnerAngle: String(panelValue("mini_ai_winner_angle", "")),
    winnerDuration: String(panelValue("mini_ai_winner_duration", "")),
  };
  saveState({ settings });
}

function applySettings(settings = {}) {
  const values = {
    mini_ai_learning_category: settings.learningCategory,
    mini_ai_objective: settings.objective,
    mini_ai_risk: settings.risk,
    mini_ai_dimension: settings.dimension,
    mini_ai_batch_size: settings.batchSize,
    mini_ai_budget_usd: settings.budgetUsd,
    mini_ai_funnel: settings.funnel,
    mini_ai_winner_angle: settings.winnerAngle,
    mini_ai_winner_duration: settings.winnerDuration,
  };
  Object.entries(values).forEach(([name, value]) => {
    if (value === undefined || value === null || value === "") return;
    const control = runtime.panel?.querySelector(`[name="${CSS.escape(name)}"]`);
    if (control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
      control.value = String(value);
    }
  });
  const newCategory = runtime.panel?.querySelector('[name="mini_ai_new_category"]');
  if (newCategory instanceof HTMLInputElement && typeof settings.newCategory === "boolean") {
    newCategory.checked = settings.newCategory;
  }
}

function dimensionLabel(value) {
  return {
    creative_angle: "сценарный угол",
    duration: "длительность",
    proof_type: "тип доказательства",
    cta_style: "CTA",
  }[value] || value;
}

function renderPlan() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="plan"]');
  if (!space) return;
  space.replaceChildren();
  const state = currentState();
  const plan = state.plan;
  if (!plan) {
    space.append(node("p", "mini-ai-empty", "Сначала сформулируйте задачу и соберите план."));
    return;
  }
  const summary = node("div", "mini-ai-plan-summary");
  summary.append(
    node("span", "mini-ai-kicker", plan.executable ? "ПЛАН ГОТОВ" : "ПЛАН ОСТАНОВЛЕН"),
    node("strong", "", plan.executable
      ? `${plan.batchSize} запусков · ${dimensionLabel(plan.dimension)}`
      : plan.blockers?.[0] || "Контекст не прошёл правила"),
    node("small", "", plan.executable
      ? `Оценка $${miniAiEstimatedCostUsd(plan).toFixed(2)} · максимум одна активная оплата · волна по одному ролику каждого arm`
      : "Мини‑ИИ отказался использовать неправильный рычаг."),
  );
  space.append(summary);
  if (!plan.executable) {
    space.append(actionButton("Вернуться к задаче", "tab:setup", "btn btn-primary"));
    return;
  }
  const cards = node("div", "mini-ai-arms");
  plan.arms.forEach((arm, index) => {
    const card = node("article", "mini-ai-arm");
    if (arm.control) card.classList.add("is-control");
    card.append(
      node("span", "mini-ai-arm__index", arm.control ? "CONTROL" : `ARM ${index + 1}`),
      node("strong", "", arm.label),
      node("p", "", arm.instruction),
      node("small", "", `${arm.plannedCount} запуска · ${arm.durationSeconds} сек. · ${Math.round(arm.allocation * 100)}%`),
    );
    cards.append(card);
  });
  const warnings = node("ul", "mini-ai-warnings");
  (plan.warnings || []).forEach((item) => warnings.append(node("li", "", item)));
  const footer = node("div", "mini-ai-space__footer");
  footer.append(
    actionButton("Назад", "tab:setup"),
    actionButton("Подготовить волны", "prepare-queue", "btn btn-primary"),
  );
  space.append(cards, warnings, footer);
}

function buildTasks(plan) {
  const remaining = plan.arms.map((arm) => arm.plannedCount);
  const tasks = [];
  let wave = 0;
  let ordinal = 0;
  while (remaining.some((value) => value > 0)) {
    wave += 1;
    plan.arms.forEach((arm, index) => {
      if (remaining[index] <= 0) return;
      ordinal += 1;
      tasks.push({
        taskId: `${plan.planId}-task-${String(ordinal).padStart(2, "0")}`,
        armId: arm.armId,
        wave,
        status: "pending",
        jobId: "",
        error: "",
        startedAt: null,
        completedAt: null,
      });
      remaining[index] -= 1;
    });
  }
  return tasks;
}

function recoverInterruptedExecution(state) {
  const execution = state.execution;
  if (!execution?.tasks?.length) return state;
  const interrupted = execution.status === "running"
    || execution.tasks.some((task) => task.status === "running");
  if (!interrupted) return state;
  execution.tasks.forEach((task) => {
    if (task.status !== "running") return;
    task.status = "unknown";
    task.error = "Вкладка закрылась до подтверждения job. Не повторяйте оплату — сначала проверьте штатную очередь.";
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

function waveTasks(execution, wave) {
  return execution.tasks.filter((task) => task.wave === wave);
}

function waveCompleted(execution, wave) {
  const tasks = waveTasks(execution, wave);
  return tasks.length > 0 && tasks.every((task) => task.status === "queued");
}

function renderQueue() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="queue"]');
  if (!space) return;
  space.replaceChildren();
  let state = recoverInterruptedExecution(currentState());
  const plan = state.plan;
  const execution = state.execution;
  if (!plan?.executable) {
    space.append(node("p", "mini-ai-empty", "Сначала нужен исполнимый план."));
    return;
  }
  if (!execution?.tasks?.length) {
    const confirmation = node("div", "mini-ai-confirm");
    const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
    confirmation.append(
      node("strong", "", "Создать последовательную очередь"),
      node("p", "", `Верхняя оценка пакета: $${miniAiEstimatedCostUsd(plan).toFixed(2)}. После каждой волны очередь остановится на проверку товара и техники.`),
      field("Введите подтверждение", inputControl("mini_ai_confirmation", "", expected)),
      checkboxControl(
        "mini_ai_acknowledge",
        "Подтверждаю общий лимит и понимаю, что каждый job создаётся через штатную платную форму",
      ),
      checkboxControl(
        "mini_ai_autopilot",
        "Автопилот внутри волны: запускать следующий arm только после появления предыдущего job",
        true,
      ),
      actionButton("Создать очередь", "confirm-queue", "btn btn-primary"),
    );
    space.append(confirmation, actionButton("Назад", "tab:plan"));
    return;
  }

  const queued = execution.tasks.filter((task) => task.status === "queued").length;
  const progress = node("div", "mini-ai-queue-head");
  progress.append(
    node("strong", "", `Job подтверждены: ${queued} / ${execution.tasks.length}`),
    node("small", "", execution.status === "awaiting_qa"
      ? `Волна ${execution.awaitingWave} завершена. Следующая оплата заблокирована до проверки.`
      : execution.status === "running"
        ? "Работает ровно один штатный запуск."
        : execution.status === "completed"
          ? "Все волны проверены и отправлены."
          : execution.status === "stopped"
            ? `Пакет остановлен: ${execution.stopReason || "решение QA"}`
            : "Очередь на безопасной паузе."),
  );
  const bar = node("div", "mini-ai-progress");
  bar.style.setProperty("--mini-ai-progress", `${(queued / execution.tasks.length) * 100}%`);
  progress.append(bar);

  const list = node("div", "mini-ai-queue-list");
  execution.tasks.forEach((task, index) => {
    const arm = plan.arms.find((item) => item.armId === task.armId);
    const item = node("article", "mini-ai-queue-item");
    item.dataset.state = task.status;
    item.append(
      node("span", "mini-ai-queue-item__number", String(index + 1)),
      node("strong", "", `Волна ${task.wave} · ${arm?.label || task.armId}`),
      node("small", "", task.jobId ? `job ${task.jobId}` : task.error || queueLabel(task.status)),
      node("span", "mini-ai-queue-item__status", queueLabel(task.status)),
    );
    list.append(item);
  });

  const footer = node("div", "mini-ai-space__footer");
  if (execution.status === "awaiting_qa") {
    const gate = node("div", "mini-ai-wave-gate");
    gate.append(
      node("strong", "", `Контроль волны ${execution.awaitingWave}`),
      node("p", "", "Посмотрите все ролики волны. Один неверный товар или общий дефект должен остановить оставшийся пакет."),
      checkboxControl("mini_ai_wave_product_ok", "Точный товар и упаковка сохранены во всех роликах волны"),
      checkboxControl("mini_ai_wave_technical_ok", "Нет общего технического дефекта, который повторится дальше"),
      field("Подтверждение", inputControl("mini_ai_wave_confirmation", "", `ПРОВЕРЕНО ${execution.awaitingWave}`)),
    );
    const actions = node("div", "mini-ai-space__footer");
    actions.append(
      actionButton("Остановить пакет по дефекту", "stop-quality", "btn btn-danger btn-small"),
      actionButton("Подтвердить волну и продолжить", "approve-wave", "btn btn-primary"),
    );
    gate.append(actions);
    footer.append(gate);
  } else if (execution.status === "paused") {
    const wave = activeWave(execution);
    const hasPending = waveTasks(execution, wave).some((task) => task.status === "pending");
    if (hasPending) footer.append(actionButton(`Запустить волну ${wave}`, "run-wave", "btn btn-primary"));
  } else if (execution.status === "running") {
    footer.append(actionButton("Выключить автопилот после текущего job", "pause-autopilot"));
  } else if (execution.status === "completed") {
    footer.append(actionButton("Перейти к выводу", "tab:conclusion", "btn btn-primary"));
  }
  footer.append(actionButton("Сбросить только локальную очередь", "reset-queue", "btn btn-ghost btn-small"));
  space.append(progress, list, footer);
}

function queueLabel(value) {
  return {
    pending: "ожидает",
    running: "отправляется",
    queued: "job создан",
    unknown: "исход неизвестен",
    failed: "ошибка",
  }[value] || value;
}

function renderConclusion() {
  const space = runtime.panel?.querySelector('[data-mini-ai-space="conclusion"]');
  if (!space) return;
  space.replaceChildren();
  const state = currentState();
  const plan = state.plan;
  if (!plan?.executable) {
    space.append(node("p", "mini-ai-empty", "Сначала выполните управляемый план."));
    return;
  }
  space.append(node(
    "p",
    "mini-ai-space__intro",
    "Введите только зрелые результаты после независимого QA и окна атрибуции. Просмотры хранятся для диагностики, но winner по ним не выбирается.",
  ));
  const saved = state.results && typeof state.results === "object" ? state.results : {};
  const grid = node("div", "mini-ai-result-grid");
  plan.arms.forEach((arm) => {
    const values = saved[arm.armId] || {};
    const card = node("article", "mini-ai-result-card");
    card.dataset.armId = arm.armId;
    card.append(
      node("span", "mini-ai-arm__index", arm.control ? "CONTROL" : "HYPOTHESIS"),
      node("strong", "", arm.label),
    );
    const fields = node("div", "mini-ai-result-fields");
    const definitions = [
      ["eligible", "Зрелых результатов", values.eligible ?? 0, 0, 50, 1],
      ["failed", "Тех. ошибок", values.failed ?? 0, 0, 50, 1],
      ["qaRejected", "Не прошли QA", values.qaRejected ?? 0, 0, 50, 1],
      ["critical", "Критических блокеров", values.critical ?? 0, 0, 50, 1],
      ["mismatch", "Подмен товара", values.mismatch ?? 0, 0, 50, 1],
      ["orders", "Заказы", values.orders ?? 0, 0, 1_000_000, 1],
      ["carts", "Корзины", values.carts ?? 0, 0, 1_000_000, 1],
      ["salesRub", "Продажи, ₽", values.salesRub ?? 0, 0, 1_000_000_000, 0.01],
      ["spendRub", "Расход, ₽", values.spendRub ?? 0, 0, 1_000_000_000, 0.01],
      ["days", "Сумма дней атрибуции", values.days ?? 1, 1, 10_000, 1],
      ["views", "Просмотры · диагностика", values.views ?? 0, 0, 1_000_000_000, 1],
    ];
    definitions.forEach(([name, label, value, min, max, step]) => {
      const control = numberControl(`mini_ai_result_${name}`, value, min, max, step);
      control.dataset.resultField = name;
      control.dataset.armId = arm.armId;
      fields.append(field(label, control));
    });
    card.append(fields);
    grid.append(card);
  });
  const actions = node("div", "mini-ai-space__footer");
  actions.append(
    actionButton("Сохранить результаты", "save-results"),
    actionButton("Сделать вывод", "evaluate", "btn btn-primary"),
  );
  const output = node("div", "mini-ai-conclusion-output");
  if (state.conclusion) renderConclusionOutput(output, state.conclusion, plan);
  space.append(grid, actions, output);
}

function renderConclusionOutput(target, conclusion, plan) {
  target.replaceChildren();
  target.dataset.decision = conclusion.decision;
  const winner = plan.arms.find((arm) => arm.armId === conclusion.winnerArmId);
  target.append(
    node("span", "mini-ai-kicker", conclusion.decision.toUpperCase()),
    node("strong", "", conclusion.summary),
    node("p", "", conclusion.nextAction),
  );
  if (winner) target.append(node("p", "mini-ai-winner", `Выбранный arm: ${winner.label}`));
  if (conclusion.evidence?.length) {
    const list = node("ul", "mini-ai-evidence");
    conclusion.evidence.forEach((item) => list.append(node("li", "", item)));
    target.append(list);
  }
  target.append(node(
    "small",
    "",
    `Уверенность: ${conclusion.confidence}. Наблюдаемая разница не объявляется причинным доказательством.`,
  ));
  if (conclusion.decision === "promote_with_control") {
    target.append(actionButton(
      "Подтвердить winner и подготовить следующий вопрос",
      "accept-winner",
      "btn btn-primary",
    ));
  }
}

function restoreUi() {
  let state = recoverInterruptedExecution(currentState());
  applySettings(state.settings || {});
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab(state.activeTab || "setup", { persist: false });
  if (state.plan?.executable) status("План сохранён", "ready");
}

function buildPlan() {
  const form = runtime.form;
  if (!(form instanceof HTMLFormElement)) return;
  const brief = validateBaseBrief(form);
  if (!brief.ready) {
    status(brief.blockers[0], "warning");
    form.elements.brief?.focus({ preventScroll: false });
    return;
  }
  const plan = buildMiniAiPlan(formContext(form));
  const settings = currentState().settings || {};
  saveState({
    settings,
    plan,
    baseBrief: brief.brief,
    baseBriefHash: briefHash(brief.brief),
    execution: null,
    results: {},
    conclusion: null,
    activeTab: "plan",
  });
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab("plan");
  status(plan.executable ? "План готов" : "План остановлен", plan.executable ? "ready" : "warning");
}

function confirmQueue() {
  const state = currentState();
  const plan = state.plan;
  if (!plan?.executable) return;
  const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
  const typed = String(panelValue("mini_ai_confirmation", "")).trim().toUpperCase();
  const acknowledged = panelValue("mini_ai_acknowledge", false) === true;
  if (typed !== expected || !acknowledged) {
    status(`Введите «${expected}» и подтвердите общий лимит`, "warning");
    return;
  }
  const execution = {
    version: "mini-ai-wave-queue.v1",
    status: "paused",
    autopilot: panelValue("mini_ai_autopilot", true) === true,
    tasks: buildTasks(plan),
    approvedWave: 0,
    awaitingWave: null,
    waveReviews: [],
    currentTaskId: "",
    stopReason: "",
    startedAt: null,
  };
  saveState({ execution, activeTab: "queue" });
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

function matchingNewJob(before, sku, duration) {
  const candidates = [...jobSnapshot().entries()]
    .filter(([id]) => !before.has(id));
  const targetSku = normalize(sku);
  const durationToken = `${Number(duration)} секунд`;
  return candidates.find(([_id, element]) => {
    const text = normalize(element.textContent);
    return text.includes(targetSku) && text.includes(durationToken);
  })?.[0] || "";
}

function waitForMatchingJob(before, sku, duration) {
  const startedAt = Date.now();
  return new Promise((resolve) => {
    const timer = window.setInterval(() => {
      const id = matchingNewJob(before, sku, duration);
      if (id) {
        window.clearInterval(timer);
        resolve(id);
      } else if (Date.now() - startedAt >= JOB_WAIT_MS) {
        window.clearInterval(timer);
        resolve("");
      }
    }, JOB_POLL_MS);
  });
}

function dispatch(control) {
  control?.dispatchEvent(new Event("input", { bubbles: true }));
  control?.dispatchEvent(new Event("change", { bubbles: true }));
}

function nextFrame() {
  return new Promise((resolve) => window.requestAnimationFrame(resolve));
}

function replaceDuration(value, seconds) {
  return String(value || "").replace(
    /(длительностью\s+)\d+(\s+секунд)/giu,
    `$1${seconds}$2`,
  );
}

function spokenWords(value) {
  const match = String(value || "").match(/Реплика героя дословно:\s*«([^»]+)»/iu);
  return match ? (match[1].match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || []).length : 0;
}

function compileArmBrief(base, arm, mode) {
  const value = `${replaceDuration(base, arm.durationSeconds)}\n${arm.instruction}`.trim();
  if (value.length > MAX_BRIEF_LENGTH) {
    throw new Error(`ТЗ вместе с arm длиннее ${MAX_BRIEF_LENGTH} символов. Сократите базовое ТЗ.`);
  }
  if (mode === "real_seedance") {
    const limit = Math.max(10, Math.min(42, Math.floor(arm.durationSeconds * 22 / 8)));
    const count = spokenWords(value);
    if (count > limit) {
      throw new Error(`Для ${arm.durationSeconds} секунд оставьте не больше ${limit} слов в реплике; сейчас ${count}.`);
    }
  }
  return value;
}

async function prepareNativeForm(form, plan, arm, base) {
  const duration = form.elements.duration_seconds;
  const brief = form.elements.brief;
  const count = form.elements.count;
  if (!(duration instanceof HTMLSelectElement)) throw new Error("Не найден выбор длительности.");
  if (!(brief instanceof HTMLTextAreaElement || brief instanceof HTMLInputElement)) {
    throw new Error("Не найдено настоящее поле ТЗ.");
  }
  duration.value = String(arm.durationSeconds);
  dispatch(duration);
  await nextFrame();
  await nextFrame();
  brief.value = compileArmBrief(base, arm, plan.context.mode);
  dispatch(brief);
  if (count instanceof HTMLInputElement || count instanceof HTMLSelectElement) {
    count.value = "1";
    dispatch(count);
  }
  await nextFrame();
  const confirmation = form.elements.real_spend_confirmation;
  if (!(confirmation instanceof HTMLInputElement)) throw new Error("Не найдено подтверждение платного запуска.");
  confirmation.checked = true;
  dispatch(confirmation);
  await nextFrame();
  if (!form.checkValidity()) {
    form.reportValidity();
    throw new Error("Штатная форма не готова. Заполните обязательные поля и повторите эту волну.");
  }
}

function scheduleNextTask(delay = 1_500) {
  window.clearTimeout(runtime.nextTimer);
  runtime.nextTimer = window.setTimeout(() => {
    runtime.nextTimer = 0;
    void runNextTask();
  }, delay);
}

async function runNextTask() {
  if (runtime.running) return;
  runtime.running = true;
  let shouldContinue = false;
  try {
    let state = recoverInterruptedExecution(currentState());
    const plan = state.plan;
    const execution = state.execution;
    if (!plan?.executable || !execution?.tasks?.length) return;
    if (execution.status === "stopped" || execution.status === "awaiting_qa") return;
    const wave = activeWave(execution);
    const task = waveTasks(execution, wave).find((item) => item.status === "pending");
    if (!task) {
      if (waveCompleted(execution, wave)) {
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
    if (!nativeContextMatches(plan, form)) {
      throw new Error("SKU, категория, площадка или модель изменились. Очередь остановлена.");
    }
    if (form.dataset.busy === "true") throw new Error("Штатная форма занята другим запуском.");
    const currentBrief = validateBaseBrief(form);
    if (!currentBrief.ready) throw new Error(currentBrief.blockers[0]);
    if (state.baseBriefHash !== briefHash(state.baseBrief || "")) {
      throw new Error("Сохранённое базовое ТЗ повреждено. Соберите план заново.");
    }
    const arm = plan.arms.find((item) => item.armId === task.armId);
    if (!arm) throw new Error("Arm задачи отсутствует в плане.");
    execution.status = "running";
    execution.currentTaskId = task.taskId;
    execution.startedAt ||= Date.now();
    task.status = "running";
    task.startedAt = Date.now();
    saveState({ execution });
    renderQueue();
    status(`Волна ${wave}: ${arm.label}`, "running");

    const before = new Set(jobSnapshot().keys());
    await prepareNativeForm(form, plan, arm, String(state.baseBrief || ""));
    const submit = form.querySelector("#generation-submit, button[type='submit']");
    if (!(submit instanceof HTMLElement)) throw new Error("Не найдена штатная кнопка запуска.");
    form.requestSubmit(submit);
    const jobId = await waitForMatchingJob(
      before,
      plan.context.sku,
      arm.durationSeconds,
    );

    state = currentState();
    const fresh = state.execution;
    const savedTask = fresh?.tasks?.find((item) => item.taskId === task.taskId);
    if (!fresh || !savedTask) return;
    if (!jobId) {
      savedTask.status = "unknown";
      savedTask.error = "За две минуты не найден job с тем же SKU и длительностью. Не повторяйте оплату — проверьте штатную очередь.";
      fresh.status = "paused";
      fresh.autopilot = false;
      fresh.currentTaskId = "";
      saveState({ execution: fresh });
      renderQueue();
      status("Исход запуска не подтверждён", "warning");
      return;
    }
    savedTask.status = "queued";
    savedTask.jobId = jobId;
    savedTask.completedAt = Date.now();
    fresh.currentTaskId = "";
    if (waveCompleted(fresh, wave)) {
      fresh.status = "awaiting_qa";
      fresh.awaitingWave = wave;
    } else {
      fresh.status = "paused";
      shouldContinue = fresh.autopilot === true;
    }
    saveState({ execution: fresh });
    renderQueue();
    status(
      fresh.status === "awaiting_qa"
        ? `Волна ${wave} готова к проверке`
        : `Job ${compact(jobId, 20)} подтверждён`,
      fresh.status === "awaiting_qa" ? "warning" : "ready",
    );
  } catch (error) {
    const state = currentState();
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
    if (shouldContinue) scheduleNextTask();
  }
}

function confirmQueue() {
  const state = currentState();
  const plan = state.plan;
  if (!plan?.executable) return;
  const expected = `ЗАПУСТИТЬ ${plan.batchSize}`;
  const typed = String(panelValue("mini_ai_confirmation", "")).trim().toUpperCase();
  if (typed !== expected || panelValue("mini_ai_acknowledge", false) !== true) {
    status(`Введите «${expected}» и подтвердите лимит`, "warning");
    return;
  }
  const execution = {
    version: "mini-ai-wave-queue.v1",
    status: "paused",
    autopilot: panelValue("mini_ai_autopilot", true) === true,
    tasks: buildTasks(plan),
    approvedWave: 0,
    awaitingWave: null,
    waveReviews: [],
    currentTaskId: "",
    stopReason: "",
    startedAt: null,
  };
  saveState({ execution, activeTab: "queue" });
  renderQueue();
  setTab("queue");
  status("Очередь готова", "ready");
}

function approveWave() {
  const state = currentState();
  const execution = state.execution;
  const wave = Number(execution?.awaitingWave || 0);
  if (!execution || execution.status !== "awaiting_qa" || wave < 1) return;
  const expected = `ПРОВЕРЕНО ${wave}`;
  const typed = String(panelValue("mini_ai_wave_confirmation", "")).trim().toUpperCase();
  const productOk = panelValue("mini_ai_wave_product_ok", false) === true;
  const technicalOk = panelValue("mini_ai_wave_technical_ok", false) === true;
  if (typed !== expected || !productOk || !technicalOk) {
    status(`Проверьте оба условия и введите «${expected}»`, "warning");
    return;
  }
  execution.waveReviews.push({
    wave,
    productFidelityOk: true,
    technicalOk: true,
    confirmedAt: Date.now(),
  });
  execution.approvedWave = wave;
  execution.awaitingWave = null;
  const pending = execution.tasks.some((task) => task.status === "pending");
  execution.status = pending ? "paused" : "completed";
  saveState({ execution });
  renderQueue();
  status(
    pending ? `Волна ${wave} принята` : "Все волны проверены",
    "ready",
  );
  if (pending && execution.autopilot) scheduleNextTask();
}

function stopForQuality() {
  const state = currentState();
  const execution = state.execution;
  if (!execution) return;
  execution.status = "stopped";
  execution.autopilot = false;
  execution.stopReason = `Дефект обнаружен после волны ${execution.awaitingWave || execution.approvedWave + 1}`;
  execution.waveReviews.push({
    wave: execution.awaitingWave || execution.approvedWave + 1,
    productFidelityOk: false,
    technicalOk: false,
    confirmedAt: Date.now(),
  });
  saveState({ execution });
  renderQueue();
  status("Пакет остановлен по QA", "warning");
}

function resultValues() {
  const values = {};
  runtime.panel?.querySelectorAll("[data-result-field][data-arm-id]").forEach((control) => {
    const armId = String(control.dataset.armId || "");
    const name = String(control.dataset.resultField || "");
    if (!armId || !name) return;
    values[armId] ||= {};
    values[armId][name] = Number(control.value || 0);
  });
  return values;
}

function distribute(total, index, count) {
  if (!count) return 0;
  const base = Math.floor(total / count);
  return base + (index < total % count ? 1 : 0);
}

function outcomesFromResults(plan, results) {
  const outcomes = [];
  plan.arms.forEach((arm) => {
    const value = results[arm.armId] || {};
    const eligible = Math.max(0, Math.floor(value.eligible || 0));
    const rejected = Math.max(0, Math.floor(value.qaRejected || 0));
    const failed = Math.max(0, Math.floor(value.failed || 0));
    const total = Math.max(eligible + rejected + failed, arm.plannedCount);
    const orders = Math.max(0, Math.floor(value.orders || 0));
    const carts = Math.max(orders, Math.floor(value.carts || 0));
    const salesMinor = Math.round(Math.max(0, Number(value.salesRub || 0)) * 100);
    const spendMinor = Math.round(Math.max(0, Number(value.spendRub || 0)) * 100);
    const days = Math.max(1, Math.floor(value.days || eligible || 1));
    const views = Math.max(0, Math.floor(value.views || 0));
    const mismatch = Math.max(0, Math.floor(value.mismatch || 0));
    const critical = Math.max(0, Math.floor(value.critical || 0));
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
        jobId: `aggregate-${arm.armId}-${index + 1}`,
        armId: arm.armId,
        state,
        qaState,
        productFidelityOk: index >= mismatch,
        criticalBlocker: index < critical,
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

function saveResults() {
  saveState({ results: resultValues(), conclusion: null });
  status("Результаты сохранены локально", "ready");
}

function evaluateResults() {
  const state = currentState();
  if (!state.plan?.executable) return;
  const results = resultValues();
  const conclusion = evaluateMiniAiPlan(
    state.plan,
    outcomesFromResults(state.plan, results),
  );
  saveState({ results, conclusion });
  renderConclusion();
  status(conclusion.decision === "promote_with_control" ? "Winner найден" : "Вывод готов", "ready");
}

function acceptWinner() {
  const state = currentState();
  const plan = state.plan;
  const conclusion = state.conclusion;
  if (conclusion?.decision !== "promote_with_control") return;
  const winner = plan.arms.find((arm) => arm.armId === conclusion.winnerArmId);
  if (!winner) return;
  const nextDimension = {
    creative_angle: "duration",
    duration: "proof_type",
    proof_type: "cta_style",
    cta_style: "creative_angle",
  }[plan.dimension] || "auto";
  const settings = {
    ...(state.settings || {}),
    newCategory: false,
    winnerAngle: winner.creativeAngle,
    winnerDuration: String(winner.durationSeconds),
    dimension: nextDimension,
  };
  saveState({
    settings,
    plan: null,
    execution: null,
    results: {},
    conclusion: null,
    activeTab: "setup",
  });
  applySettings(settings);
  renderPlan();
  renderQueue();
  renderConclusion();
  setTab("setup");
  status("Winner принят человеком; готов следующий вопрос", "ready");
}

function resetQueue() {
  const state = currentState();
  saveState({ execution: null, conclusion: null, results: state.results || {} });
  renderQueue();
  status("Локальная очередь сброшена", "idle");
}

function onPanelClick(event) {
  const target = event.target instanceof Element
    ? event.target.closest("[data-mini-ai-action]")
    : null;
  if (!(target instanceof HTMLElement)) return;
  const action = String(target.dataset.miniAiAction || "");
  if (action.startsWith("tab:")) setTab(action.slice(4));
  else if (action === "build-plan") buildPlan();
  else if (action === "prepare-queue") {
    renderQueue();
    setTab("queue");
  } else if (action === "confirm-queue") confirmQueue();
  else if (action === "run-wave") {
    const state = currentState();
    if (state.execution) {
      state.execution.status = "paused";
      saveState({ execution: state.execution });
    }
    void runNextTask();
  } else if (action === "pause-autopilot") {
    const state = currentState();
    if (state.execution) {
      state.execution.autopilot = false;
      saveState({ execution: state.execution });
      renderQueue();
      status("Автопилот выключен; текущий запрос продолжает проверяться", "warning");
    }
  } else if (action === "approve-wave") approveWave();
  else if (action === "stop-quality") stopForQuality();
  else if (action === "reset-queue") resetQueue();
  else if (action === "save-results") saveResults();
  else if (action === "evaluate") evaluateResults();
  else if (action === "accept-winner") acceptWinner();
}

function mount() {
  window.clearTimeout(runtime.mountTimer);
  runtime.mountTimer = 0;
  if (routePath() !== ROUTE) {
    runtime.mountAttempts = 0;
    return;
  }
  const form = document.querySelector(FORM_SELECTOR);
  if (!(form instanceof HTMLFormElement)) {
    if (runtime.mountAttempts < MOUNT_RETRY_LIMIT) {
      runtime.mountAttempts += 1;
      runtime.mountTimer = window.setTimeout(mount, MOUNT_RETRY_MS);
    }
    return;
  }
  runtime.mountAttempts = 0;
  runtime.form = form;
  runtime.panel = form.querySelector("[data-mini-ai-desk-v2]") || buildPanel(form);
  const state = recoverInterruptedExecution(currentState(form));
  applySettings(state.settings || {});
  restoreUi();
}

function scheduleMount() {
  window.clearTimeout(runtime.mountTimer);
  runtime.mountTimer = window.setTimeout(mount, 0);
}

window.addEventListener("hashchange", scheduleMount, { passive: true });
window.addEventListener("contentengine:v4-route-ready", scheduleMount, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
} else {
  scheduleMount();
}
