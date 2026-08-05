/*
 * ContentEngine · Research -> AI Center -> editable recommendations.
 *
 * This route adapter renders a rich, governed training queue. It never trains
 * on receipt arrival alone: the operator chooses analysis blocks and scenario
 * candidates, can edit every recommendation, and confirms one append-only
 * server decision.
 */

const ROUTE = "/workspace/ai";
const RPC_QUEUE = "creator_ai_research_training_queue";
const RPC_DECIDE = "creator_decide_ai_research_training";
const ROOT_ATTRIBUTE = "data-ai-research-training-root";
const CATEGORY_KEY = "contentengine.ai-research-training.category";
const CATEGORIES = Object.freeze([
  ["cosmetics", "Косметика и уход"],
  ["baa", "БАД"],
  ["sports_food", "Спортивное питание"],
  ["food", "Еда и напитки"],
  ["household", "Товары для дома"],
  ["apparel", "Одежда и аксессуары"],
  ["electronics", "Электроника"],
  ["other", "Другая категория"],
]);
const CATEGORY_SET = new Set(CATEGORIES.map(([value]) => value));

const runtime = {
  root: null,
  category: "other",
  loading: false,
  mutating: false,
  requestKey: "",
  mountQueued: false,
};

function routePath() {
  const apiRoute = globalThis.window?.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(globalThis.window?.location?.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const raw = String(globalThis.window?.location?.hash || "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  return new URLSearchParams(query);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function clean(value, limit = 4000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value, limit = 12) {
  return (Array.isArray(value) ? value : [])
    .slice(0, limit)
    .map((item) => {
      if (typeof item === "string") return clean(item, 600);
      if (!item || typeof item !== "object") return "";
      return clean(
        item.label || item.title || item.name || item.text || item.summary
          || item.claim || item.pain || item.objection || JSON.stringify(item),
        600,
      );
    })
    .filter(Boolean);
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function unwrap(value) {
  return object(value?.data || value);
}

function currentCategory() {
  const params = routeParams();
  const routeValue = clean(
    params.get("product_category") || params.get("category") || "",
    40,
  ).toLowerCase();
  if (CATEGORY_SET.has(routeValue)) return routeValue;
  try {
    const stored = window.sessionStorage.getItem(CATEGORY_KEY) || "";
    if (CATEGORY_SET.has(stored)) return stored;
  } catch {
    // Optional route memory.
  }
  const existing = document.querySelector(
    'select[name="product_category"], [data-ai-category-select]',
  );
  const existingValue = clean(existing?.value, 40).toLowerCase();
  return CATEGORY_SET.has(existingValue) ? existingValue : "other";
}

function rememberCategory(category) {
  try {
    window.sessionStorage.setItem(CATEGORY_KEY, category);
  } catch {
    // Optional route memory.
  }
}

function payloadWithOrganization(api, payload) {
  if (typeof api?.withOrganization === "function") {
    return api.withOrganization(payload);
  }
  if (api?.organizationId) {
    return { organization_id: api.organizationId, ...payload };
  }
  return payload;
}

async function getApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return api;
}

function idempotencyKey(prefix) {
  const uuid = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${uuid}`.slice(0, 178);
}

function setStatus(root, message, tone = "neutral") {
  const target = root.querySelector("[data-ai-research-training-status]");
  if (!target) return;
  target.textContent = message;
  target.dataset.tone = tone;
}

function addTextList(parent, values, emptyText = "Нет подтверждённых пунктов") {
  const items = list(values);
  if (!items.length) {
    parent.append(el("p", "ai-research-training__empty-copy", emptyText));
    return;
  }
  const ul = el("ul", "ai-research-training__bullets");
  items.forEach((item) => ul.append(el("li", "", item)));
  parent.append(ul);
}

function insightCard({ key, title, description, content, checked = true }) {
  const label = el("label", "ai-research-training__insight");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  checkbox.checked = checked;
  checkbox.dataset.insightKey = key;
  const body = el("span", "ai-research-training__insight-body");
  const head = el("span", "ai-research-training__insight-title");
  head.append(el("strong", "", title), el("small", "", description));
  const detail = el("span", "ai-research-training__insight-detail");
  if (typeof content === "string") detail.textContent = content;
  else if (content instanceof Node) detail.append(content);
  body.append(head, detail);
  label.append(checkbox, body);
  return label;
}

function categoryInsight(analysis) {
  const category = object(analysis.category_analysis);
  const block = el("span");
  const summary = clean(category.definition || category.summary || category.category_name, 900);
  if (summary) block.append(el("span", "", summary));
  const jobs = list(category.buyer_jobs || category.jobs, 6);
  if (jobs.length) {
    const jobsLine = el("small", "");
    jobsLine.textContent = `Задачи покупателя: ${jobs.join(" · ")}`;
    block.append(jobsLine);
  }
  return insightCard({
    key: "category",
    title: "Категория и покупатель",
    description: "Что человек пытается решить товаром",
    content: block,
    checked: Boolean(summary || jobs.length),
  });
}

function competitorInsight(analysis) {
  const competitors = object(analysis.competitor_analysis);
  const block = el("span");
  const reusable = list(
    competitors.reusable_structures || competitors.content_gaps
      || competitors.opportunities,
    6,
  );
  const saturated = list(competitors.saturated_patterns, 4);
  if (reusable.length) {
    const line = el("span");
    line.textContent = `Можно использовать: ${reusable.join(" · ")}`;
    block.append(line);
  }
  if (saturated.length) {
    const line = el("small");
    line.textContent = `Не повторять вслепую: ${saturated.join(" · ")}`;
    block.append(line);
  }
  return insightCard({
    key: "competitors",
    title: "Конкуренты и насыщенные приёмы",
    description: "Структуры для адаптации, а не копирования",
    content: block,
    checked: Boolean(reusable.length || saturated.length),
  });
}

function trendInsight(analysis) {
  const trends = object(analysis.trend_analysis);
  const signals = Array.isArray(trends.signals) ? trends.signals.slice(0, 6) : [];
  const block = el("span");
  if (signals.length) {
    const ul = el("ul", "ai-research-training__compact-list");
    signals.forEach((signal) => {
      const source = object(signal);
      const name = clean(source.name || source.signal || source.title, 260);
      const direction = clean(source.direction, 80);
      const use = clean(source.recommended_use || source.use, 240);
      if (!name && !use) return;
      ul.append(el(
        "li",
        "",
        [name, direction && `(${direction})`, use].filter(Boolean).join(" — "),
      ));
    });
    block.append(ul);
  }
  return insightCard({
    key: "trends",
    title: "Тренды и свежие сигналы",
    description: "Только подтверждённые или честно помеченные гипотезы",
    content: block,
    checked: signals.length > 0,
  });
}

function briefInsight(brief) {
  const block = el("span");
  const audience = list(brief.audience, 4);
  const pains = list(brief.pains, 4);
  const objections = list(brief.objections, 4);
  const lines = [
    audience.length ? `Аудитория: ${audience.join(" · ")}` : "",
    pains.length ? `Боли: ${pains.join(" · ")}` : "",
    objections.length ? `Возражения: ${objections.join(" · ")}` : "",
  ].filter(Boolean);
  lines.forEach((line, index) => block.append(el(index ? "small" : "span", "", line)));
  return insightCard({
    key: "brief",
    title: "Коммуникационная рамка",
    description: "Аудитория, боли, возражения и доказательства",
    content: block,
    checked: lines.length > 0,
  });
}

function shotListText(value) {
  if (typeof value === "string") return value.trim();
  if (!Array.isArray(value)) return "";
  return value.slice(0, 12).map((shot) => {
    if (typeof shot === "string") return shot.trim();
    const source = object(shot);
    const seconds = clean(source.seconds || source.time || source.duration, 60);
    const visual = clean(source.visual || source.shot || source.description, 700);
    const text = clean(source.on_screen_text || source.text, 300);
    return [seconds && `${seconds}:`, visual, text && `Текст: ${text}`]
      .filter(Boolean)
      .join(" ");
  }).filter(Boolean).join("\n");
}

function field(labelText, value, name, { textarea = false, rows = 2 } = {}) {
  const label = el("label", "field ai-research-training__edit-field");
  label.append(el("span", "", labelText));
  const control = el(textarea ? "textarea" : "input");
  control.name = name;
  control.value = String(value || "");
  if (textarea) control.rows = rows;
  control.maxLength = textarea ? 5000 : 1500;
  label.append(control);
  return label;
}

function scenarioCard(scenario, position) {
  const source = object(scenario);
  const card = el("article", "ai-research-training__scenario");
  card.dataset.scenarioPosition = String(position);
  const header = el("header", "ai-research-training__scenario-header");
  const select = el("label", "ai-research-training__scenario-select");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  checkbox.checked = position === 1;
  checkbox.dataset.scenarioSelect = String(position);
  select.append(
    checkbox,
    el("strong", "", `Рекомендация ${position}`),
  );
  const mode = clean(source.recommended_generation_mode, 80);
  header.append(select, el("span", "ai-research-training__scenario-mode", mode || "сценарий"));

  const grid = el("div", "ai-research-training__scenario-grid");
  grid.append(
    field("Название", source.title, "title"),
    field("Хук", source.hook, "hook", { textarea: true, rows: 2 }),
    field(
      "Реплика / сценарий",
      source.spoken_script || source.script,
      "spoken_script",
      { textarea: true, rows: 4 },
    ),
    field(
      "Кадры",
      shotListText(source.shot_list || source.shots),
      "shot_list",
      { textarea: true, rows: 5 },
    ),
    field("Ключевое сообщение", source.goal || source.angle, "key_message", { textarea: true, rows: 2 }),
    field("Визуальное направление", source.angle, "visual_direction", { textarea: true, rows: 2 }),
    field("CTA", source.cta, "cta", { textarea: true, rows: 2 }),
  );
  const evidence = el("div", "ai-research-training__scenario-evidence");
  const proof = list(source.proof_points, 6);
  const risks = list(source.risks, 6);
  if (proof.length) evidence.append(el("p", "", `Доказательства: ${proof.join(" · ")}`));
  if (risks.length) evidence.append(el("p", "", `Ограничения: ${risks.join(" · ")}`));
  card.append(header, grid, evidence);
  return card;
}

function sourceCard(source) {
  const item = object(source);
  const card = el("article", "ai-research-training__source");
  const url = safeUrl(item.source_url);
  const title = clean(item.title, 300) || "Источник исследования";
  const heading = url ? el("a", "", title) : el("strong", "", title);
  if (url) {
    heading.href = url;
    heading.target = "_blank";
    heading.rel = "noopener noreferrer";
  }
  const meta = el("small", "", [
    clean(item.source_type, 80),
    clean(item.trust_level, 80),
  ].filter(Boolean).join(" · "));
  card.append(heading, meta);
  const analysis = object(item.analysis);
  const summary = clean(analysis.summary, 1000);
  if (summary) card.append(el("p", "", summary));
  const signals = list(analysis.structural_signal_keys, 8);
  if (signals.length) card.append(el("small", "", `Сигналы: ${signals.join(" · ")}`));
  if (!summary && url) {
    card.append(el(
      "p",
      "ai-research-training__source-limit",
      "Ссылка сохранена. Показываем только реально доступный разбор; кадры или расшифровку не выдумываем.",
    ));
  }
  return card;
}

function receiptCard(item, canDecide) {
  const source = object(item);
  const card = el("details", "ai-research-training__receipt");
  card.open = true;
  card.dataset.receiptId = clean(source.receipt_id, 80);
  card.dataset.receiptHash = clean(source.receipt_hash, 80);

  const summary = el("summary", "ai-research-training__receipt-summary");
  const titleBox = el("span");
  titleBox.append(
    el("strong", "", clean(source.product_name, 300) || "Исследование"),
    el("small", "", [
      clean(source.project_name, 180),
      clean(source.product_sku, 100),
      `${Number(source.source_count) || 0} источников`,
    ].filter(Boolean).join(" · ")),
  );
  const state = el(
    "span",
    "ai-research-training__receipt-state",
    source.review_state === "approved_waiting_for_learning_selection"
      ? "Проверено · выберите знания"
      : "Нужен отбор",
  );
  summary.append(titleBox, state);

  const body = el("div", "ai-research-training__receipt-body");
  const sourcesSection = el("section", "ai-research-training__section");
  sourcesSection.append(el("h4", "", "1. Источники и разбор ролика"));
  const sourcesGrid = el("div", "ai-research-training__sources");
  const sources = Array.isArray(source.sources) ? source.sources : [];
  if (sources.length) sources.slice(0, 12).forEach((entry) => sourcesGrid.append(sourceCard(entry)));
  else sourcesGrid.append(el("p", "ai-research-training__empty-copy", "Источники ещё не прикреплены к завершённому разбору."));
  sourcesSection.append(sourcesGrid);

  const insightSection = el("section", "ai-research-training__section");
  insightSection.append(
    el("h4", "", "2. Что именно взять в обучение"),
    el("p", "muted", "Снимите галочку с блока, который не должен влиять на рекомендации."),
  );
  const insights = el("div", "ai-research-training__insights");
  const analysis = object(source.analysis);
  const brief = object(source.creative_brief);
  insights.append(
    categoryInsight(analysis),
    competitorInsight(analysis),
    trendInsight(analysis),
    briefInsight(brief),
  );
  insightSection.append(insights);

  const scenarioSection = el("section", "ai-research-training__section");
  scenarioSection.append(
    el("h4", "", "3. Рекомендации, которые получит генерация"),
    el("p", "muted", "Отметьте варианты и поправьте текст прямо здесь. Эти правки станут утверждённой версией."),
  );
  const scenarios = el("div", "ai-research-training__scenarios");
  const scenarioItems = Array.isArray(source.scenarios) ? source.scenarios.slice(0, 3) : [];
  if (scenarioItems.length) {
    scenarioItems.forEach((scenario, index) => scenarios.append(scenarioCard(scenario, index + 1)));
  } else {
    scenarios.append(el("p", "ai-research-training__empty-copy", "В исследовании нет пригодных сценариев. Такой результат нельзя обучить как рекомендацию."));
  }
  scenarioSection.append(scenarios);

  const controls = el("footer", "ai-research-training__controls");
  const notes = field("Комментарий к отбору (необязательно)", "", "operator_notes", { textarea: true, rows: 2 });
  notes.classList.add("ai-research-training__notes");
  const confirmation = el("label", "check-row ai-research-training__confirmation");
  const confirmationInput = el("input");
  confirmationInput.type = "checkbox";
  confirmationInput.dataset.trainingConfirmation = "true";
  confirmation.append(
    confirmationInput,
    el("span", "", "Я проверила разбор и понимаю, какие выводы станут рекомендациями ИИ."),
  );
  const actions = el("div", "ai-research-training__actions");
  const reject = el("button", "btn btn-secondary", "Не использовать");
  reject.type = "button";
  reject.dataset.trainingDecision = "reject";
  const approve = el("button", "btn", "Обучить на выбранном и сохранить рекомендации");
  approve.type = "button";
  approve.dataset.trainingDecision = "approve";
  approve.disabled = !canDecide || !scenarioItems.length;
  reject.disabled = !canDecide;
  actions.append(reject, approve);
  controls.append(notes, confirmation, actions);

  body.append(sourcesSection, insightSection, scenarioSection, controls);
  card.append(summary, body);
  return card;
}

function learnedCard(item) {
  const source = object(item);
  const card = el("article", "ai-research-training__learned-card");
  const head = el("div");
  head.append(
    el("strong", "", clean(source.product_name, 300) || "Исследование"),
    el("small", "", source.decision === "approve" ? "Используется в рекомендациях" : "Отклонено"),
  );
  const count = Array.isArray(source.recommendations) ? source.recommendations.length : 0;
  card.append(head, el("span", "", `${count} рекомендац.`));
  return card;
}

function renderSnapshot(root, snapshot) {
  const source = unwrap(snapshot);
  const queue = Array.isArray(source.queue) ? source.queue : [];
  const learned = Array.isArray(source.learned) ? source.learned : [];
  const capabilities = object(source.capabilities);
  const queueHost = root.querySelector("[data-ai-research-training-queue]");
  const historyHost = root.querySelector("[data-ai-research-training-history]");
  if (!queueHost || !historyHost) return;
  queueHost.replaceChildren();
  historyHost.replaceChildren();

  if (!queue.length) {
    const empty = el("div", "ai-research-training__empty");
    empty.append(
      el("strong", "", "В этой категории нет исследований для отбора"),
      el("p", "", "Сначала завершите анализ ролика в «Исследованиях». После этого здесь появятся источники, разбор и варианты рекомендаций."),
    );
    const link = el("a", "btn btn-secondary btn-small", "Открыть Исследования");
    link.href = "#/workspace/research";
    empty.append(link);
    queueHost.append(empty);
  } else {
    queue.forEach((item) => queueHost.append(receiptCard(item, capabilities.can_decide === true)));
  }

  if (!learned.length) {
    historyHost.append(el("p", "ai-research-training__empty-copy", "Пока нет сохранённых отборов."));
  } else {
    learned.slice(0, 12).forEach((item) => historyHost.append(learnedCard(item)));
  }

  const oldInbox = document.querySelector(".ai-learning-research-inbox");
  if (oldInbox instanceof HTMLElement) {
    oldInbox.hidden = true;
    oldInbox.dataset.replacedByResearchTraining = "true";
  }
  setStatus(
    root,
    queue.length
      ? `Найдено исследований для отбора: ${queue.length}`
      : "Очередь пуста — ждём завершённое исследование.",
    queue.length ? "ready" : "neutral",
  );
}

function buildRoot() {
  const root = el("section", "ai-research-training card card-pad");
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  const header = el("header", "ai-research-training__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "ИССЛЕДОВАНИЯ → ОБУЧЕНИЕ → РЕКОМЕНДАЦИИ"),
    el("h2", "", "Разбор исследований для ИИ"),
    el("p", "muted", "Здесь ИИ не «глотает» всё подряд. Вы видите разбор ролика, выбираете полезные выводы, правите рекомендации и только затем допускаете их в создание."),
  );
  const selectLabel = el("label", "field ai-research-training__category");
  selectLabel.append(el("span", "", "Категория обучения"));
  const select = el("select");
  select.dataset.trainingCategory = "true";
  CATEGORIES.forEach(([value, label]) => {
    const option = el("option", "", label);
    option.value = value;
    select.append(option);
  });
  selectLabel.append(select);
  header.append(copy, selectLabel);

  const status = el("p", "ai-research-training__status", "Загружаем очередь…");
  status.dataset.aiResearchTrainingStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const queue = el("div", "ai-research-training__queue");
  queue.dataset.aiResearchTrainingQueue = "true";
  const historyWrap = el("details", "ai-research-training__history");
  const historySummary = el("summary", "", "Уже отобранные исследования");
  const history = el("div", "ai-research-training__history-grid");
  history.dataset.aiResearchTrainingHistory = "true";
  historyWrap.append(historySummary, history);

  root.append(header, status, queue, historyWrap);
  root.addEventListener("change", handleChange);
  root.addEventListener("click", handleClick);
  return root;
}

function hostForRoot() {
  return document.querySelector(".ai-learning-control-room")
    || document.querySelector(".ai-learning-page")
    || document.querySelector("#workspace-content")
    || document.querySelector("#main-content");
}

function ensureRoot() {
  let root = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (root instanceof HTMLElement) return root;
  const host = hostForRoot();
  if (!(host instanceof HTMLElement)) return null;
  root = buildRoot();
  const oldInbox = host.querySelector(".ai-learning-research-inbox");
  if (oldInbox?.parentNode) oldInbox.parentNode.insertBefore(root, oldInbox);
  else {
    const header = host.querySelector(":scope > header, .ai-learning-hero");
    if (header?.nextSibling) host.insertBefore(root, header.nextSibling);
    else host.prepend(root);
  }
  return root;
}

async function load(root, category = runtime.category) {
  if (runtime.loading || routePath() !== ROUTE) return;
  runtime.loading = true;
  root.dataset.loading = "true";
  setStatus(root, "Загружаем разборы исследований…");
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_QUEUE,
      payloadWithOrganization(api, {
        product_category: category,
        limit: 30,
      }),
    );
    if (routePath() !== ROUTE || runtime.category !== category) return;
    renderSnapshot(root, response);
  } catch (error) {
    console.warn("Research training queue unavailable", error);
    setStatus(
      root,
      "Не удалось загрузить очередь. Миграция/RPC должны быть развёрнуты вместе с интерфейсом.",
      "danger",
    );
  } finally {
    runtime.loading = false;
    root.dataset.loading = "false";
  }
}

function selectedInsights(card) {
  return [...card.querySelectorAll("[data-insight-key]:checked")]
    .map((input) => input.dataset.insightKey)
    .filter((value) => ["category", "competitors", "trends", "brief"].includes(value));
}

function selectedScenarios(card) {
  return [...card.querySelectorAll("[data-scenario-select]:checked")]
    .map((input) => Number(input.dataset.scenarioSelect))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3);
}

function scenarioEdits(card, positions) {
  return positions.map((position) => {
    const scenario = card.querySelector(`[data-scenario-position="${position}"]`);
    const read = (name) => String(scenario?.querySelector(`[name="${name}"]`)?.value || "").trim();
    return {
      position,
      title: read("title"),
      hook: read("hook"),
      spoken_script: read("spoken_script"),
      shot_list: read("shot_list"),
      key_message: read("key_message"),
      visual_direction: read("visual_direction"),
      cta: read("cta"),
    };
  });
}

async function decide(card, decision) {
  if (runtime.mutating) return;
  const confirmation = card.querySelector("[data-training-confirmation]");
  if (!(confirmation instanceof HTMLInputElement) || !confirmation.checked) {
    confirmation?.focus();
    setStatus(runtime.root, "Сначала подтвердите, что вы проверили разбор.", "danger");
    return;
  }
  const insights = decision === "approve" ? selectedInsights(card) : [];
  const positions = decision === "approve" ? selectedScenarios(card) : [];
  if (decision === "approve" && (!insights.length || !positions.length)) {
    setStatus(runtime.root, "Выберите минимум один блок анализа и одну рекомендацию.", "danger");
    return;
  }
  const notes = String(card.querySelector('[name="operator_notes"]')?.value || "").trim();
  runtime.mutating = true;
  runtime.root.dataset.mutating = "true";
  setStatus(
    runtime.root,
    decision === "approve" ? "Сохраняем выбранное обучение…" : "Отклоняем исследование…",
  );
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_DECIDE,
      payloadWithOrganization(api, {
        product_category: runtime.category,
        receipt_id: card.dataset.receiptId,
        receipt_hash: card.dataset.receiptHash,
        decision,
        selected_insight_keys: insights,
        selected_scenario_positions: positions,
        edits: decision === "approve" ? scenarioEdits(card, positions) : [],
        ...(notes ? { operator_notes: notes } : {}),
        confirmation: true,
        idempotency_key: idempotencyKey("research-training"),
      }),
    );
    renderSnapshot(runtime.root, unwrap(response).snapshot || response);
    setStatus(
      runtime.root,
      decision === "approve"
        ? "Готово: выбранные выводы стали редактируемыми рекомендациями для создания."
        : "Исследование исключено из обучения.",
      "ready",
    );
  } catch (error) {
    console.warn("Research training decision failed", error);
    setStatus(
      runtime.root,
      error?.message || "Не удалось сохранить решение. Обновите страницу и повторите.",
      "danger",
    );
  } finally {
    runtime.mutating = false;
    runtime.root.dataset.mutating = "false";
  }
}

function handleChange(event) {
  const select = event.target.closest?.("[data-training-category]");
  if (!select) return;
  const category = clean(select.value, 40).toLowerCase();
  if (!CATEGORY_SET.has(category) || category === runtime.category) return;
  runtime.category = category;
  rememberCategory(category);
  void load(runtime.root, category);
}

function handleClick(event) {
  const button = event.target.closest?.("[data-training-decision]");
  if (!(button instanceof HTMLButtonElement)) return;
  event.preventDefault();
  const card = button.closest("[data-receipt-id]");
  if (!(card instanceof HTMLElement)) return;
  const decision = button.dataset.trainingDecision;
  if (!["approve", "reject"].includes(decision)) return;
  void decide(card, decision);
}

function mount() {
  if (routePath() !== ROUTE) {
    runtime.root = null;
    return;
  }
  const root = ensureRoot();
  if (!root) return;
  runtime.root = root;
  const category = currentCategory();
  const select = root.querySelector("[data-training-category]");
  if (select instanceof HTMLSelectElement) select.value = category;
  const requestKey = `${category}:${root.isConnected}`;
  runtime.category = category;
  if (runtime.requestKey !== requestKey || !root.dataset.loaded) {
    runtime.requestKey = requestKey;
    root.dataset.loaded = "true";
    void load(root, category);
  }
}

function scheduleMount() {
  if (runtime.mountQueued) return;
  runtime.mountQueued = true;
  window.queueMicrotask(() => {
    runtime.mountQueued = false;
    mount();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "ai-research-training",
      mount,
      { priority: 205 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", scheduleMount);
  window.addEventListener("hashchange", scheduleMount);
  window.queueMicrotask(scheduleMount);
}

export const AiResearchTraining = Object.freeze({ mount, load });
