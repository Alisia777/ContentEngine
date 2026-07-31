/* ContentEngine Desktop v4 · scalable operational workspaces. */

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const runtime = { queued: false };

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function compact(value, limit = 220) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function taskOrigin(text) {
  const value = String(text || "").toLocaleLowerCase("ru-RU");
  if (/публикац|размест|ссылк|площадк/iu.test(value)) return ["Публикации", "Создана, чтобы завершить размещение и сохранить проверяемую ссылку."];
  if (/провер|qa|риск|одобр|доработ/iu.test(value)) return ["Проверка", "Создана после проверки материала: требуется решение человека или исправление."];
  if (/генерац|ролик|изображен|контент/iu.test(value)) return ["Создание контента", "Создана производственным маршрутом после подготовки или генерации материала."];
  if (/выплат|начисл|руб|₽/iu.test(value)) return ["Выплаты", "Создана для подтверждения основания, решения или факта перевода."];
  return ["Ручная задача", "Создана участником команды. Точный автор и связанный объект появятся после серверной provenance-связи."];
}

function taskFacts(card) {
  const title = compact(q("h2, h3, strong", card)?.textContent || "Задача", 150);
  const status = compact(q(".badge, [data-status]", card)?.textContent || "", 70);
  const text = `${title} ${status} ${card.textContent}`.toLocaleLowerCase("ru-RU");
  const blocker = /блок|ошиб|отклон|просроч|нельзя/iu.test(text);
  const done = /готов|заверш|выполн|отмен/iu.test(text) && !blocker;
  return { title, status, text, blocker, done };
}

function ensureTaskOrigin(card) {
  if (q(":scope > .ce-v4-task-origin", card)) return;
  const [title, description] = taskOrigin(card.textContent);
  const origin = create("aside", "ce-v4-task-origin");
  const mark = create("span", "ce-v4-task-origin__mark", "↳");
  const copy = create("span");
  copy.append(create("small", "", "ИСТОЧНИК ЗАДАЧИ"), create("strong", "", title), create("span", "", description));
  origin.append(mark, copy);
  card.prepend(origin);
}

function filterTasks(shell, query, status) {
  const needle = query.trim().toLocaleLowerCase("ru-RU");
  const cards = qa(".task-card", shell);
  const listItems = qa(".tasks-desk-list-item", shell);
  let shown = 0;
  cards.forEach((card, index) => {
    const facts = taskFacts(card);
    const statusMatch = status === "all"
      || (status === "blocked" && facts.blocker)
      || (status === "done" && facts.done)
      || (status === "active" && !facts.blocker && !facts.done);
    const matches = statusMatch && (!needle || facts.text.includes(needle));
    card.dataset.ceV4FilterHidden = matches ? "false" : "true";
    const item = listItems[index];
    if (item) item.hidden = !matches;
    if (matches) shown += 1;
  });
  const active = listItems.find((item) => item.classList.contains("is-active") && !item.hidden);
  if (!active) listItems.find((item) => !item.hidden)?.click();
  const counter = q("[data-ce-v4-task-count]", shell);
  if (counter) counter.textContent = `${shown} из ${cards.length}`;
}

function enhanceTasks() {
  if (routePath() !== "/workspace/tasks") return;
  const shell = q(".tasks-desk-shell");
  if (!shell) return;
  shell.dataset.ceV4Surface = "true";
  qa(".task-card", shell).forEach(ensureTaskOrigin);
  const sidebar = q(".tasks-desk-sidebar", shell);
  if (!sidebar) return;
  let toolbar = q(":scope > .ce-v4-task-filter", sidebar);
  if (!toolbar) {
    toolbar = create("form", "ce-v4-task-filter");
    toolbar.setAttribute("role", "search");
    const input = create("input");
    input.type = "search";
    input.placeholder = "Найти задачу, товар или артикул";
    input.setAttribute("aria-label", "Найти задачу");
    const select = create("select");
    select.setAttribute("aria-label", "Статус задачи");
    [["all", "Все статусы"], ["active", "В работе"], ["blocked", "Блокеры"], ["done", "Готовые"]].forEach(([value, label]) => {
      const option = create("option", "", label);
      option.value = value;
      select.append(option);
    });
    const count = create("span", "", "0");
    count.dataset.ceV4TaskCount = "true";
    toolbar.append(input, select, count);
    q(":scope > header", sidebar)?.after(toolbar);
    const apply = () => filterTasks(shell, input.value, select.value);
    input.addEventListener("input", apply);
    select.addEventListener("change", apply);
    toolbar.addEventListener("submit", (event) => event.preventDefault());
  }
  const input = q('input[type="search"]', toolbar);
  const select = q("select", toolbar);
  filterTasks(shell, input?.value || "", select?.value || "all");
}

function riskCards(container) {
  return [...container.children].filter((node) => node.matches("article, .content-review-finding, .content-review-risk, .content-review-finding-card"));
}

function enhanceReview() {
  if (routePath() !== "/workspace/review") return;
  qa(".content-review-findings").forEach((container) => {
    const cards = riskCards(container);
    if (cards.length < 2 || container.dataset.ceV4RisksReady === String(cards.length)) return;
    container.dataset.ceV4RisksReady = String(cards.length);
    q(":scope > .ce-v4-risk-nav", container)?.remove();
    const nav = create("nav", "ce-v4-risk-nav");
    nav.setAttribute("aria-label", "Риски проверки");
    const previous = create("button", "", "←");
    previous.type = "button";
    previous.setAttribute("aria-label", "Предыдущий риск");
    const counter = create("strong");
    const next = create("button", "", "→");
    next.type = "button";
    next.setAttribute("aria-label", "Следующий риск");
    nav.append(previous, counter, next);
    container.prepend(nav);
    let index = 0;
    const show = (value) => {
      index = (value + cards.length) % cards.length;
      cards.forEach((card, cardIndex) => {
        const active = cardIndex === index;
        card.hidden = !active;
        card.classList.toggle("is-active", active);
      });
      counter.textContent = `Риск ${index + 1} из ${cards.length}`;
    };
    previous.addEventListener("click", () => show(index - 1));
    next.addEventListener("click", () => show(index + 1));
    show(0);
  });
}

function recoverPublishing() {
  if (routePath() !== "/workspace/placement") return;
  const shell = q(".publishing-os-shell");
  if (!shell) return;
  shell.dataset.ceV4Surface = "true";
  const cards = qa(".placement-card", shell);
  if (cards.length && cards.every((card) => card.hidden || card.dataset.publishingFilterHidden === "true")) {
    const all = q('[data-publishing-filter="all"], [data-publishing-mode="all"], [data-publishing-tab="all"]');
    all?.click?.();
    cards.forEach((card) => { card.hidden = false; delete card.dataset.publishingFilterHidden; });
  }
  if (!cards.length && !q(".ce-v4-publishing-empty", shell)) {
    const empty = create("section", "ce-v4-publishing-empty");
    empty.append(create("span", "ce-v4-publishing-empty__mark", "↥"), create("h2", "", "Публикаций пока нет"), create("p", "", "Завершите проверку материала — после неё здесь появится один маршрут публикации."));
    const link = create("a", "", "Открыть проверку");
    link.href = "#/workspace/review";
    empty.append(link);
    shell.append(empty);
  }
}

function enhanceTableSearch(route, selector, placeholder) {
  if (routePath() !== route) return;
  const shell = q(selector);
  const table = q("table", shell);
  if (!shell || !table) return;
  shell.dataset.ceV4Surface = "true";
  let toolbar = q(":scope > .ce-v4-table-search", shell);
  if (!toolbar) {
    toolbar = create("label", "ce-v4-table-search");
    const input = create("input");
    input.type = "search";
    input.placeholder = placeholder;
    input.setAttribute("aria-label", placeholder);
    const count = create("span");
    toolbar.append(input, count);
    shell.prepend(toolbar);
    input.addEventListener("input", () => applyTableSearch(shell, table, input, count));
  }
  applyTableSearch(shell, table, q("input", toolbar), q("span", toolbar));
}

function applyTableSearch(shell, table, input, count) {
  const rows = qa("tbody tr", table);
  const needle = String(input?.value || "").trim().toLocaleLowerCase("ru-RU");
  let shown = 0;
  rows.forEach((row) => {
    const matches = !needle || compact(row.textContent, 1800).toLocaleLowerCase("ru-RU").includes(needle);
    row.hidden = !matches;
    if (matches) shown += 1;
  });
  if (count) count.textContent = `${shown} из ${rows.length}`;
}

function normalizeAcademy() {
  const route = routePath();
  if (!(route === "/learn" || route.startsWith("/learn/"))) return;
  const windowNode = q(".academy-os-window, .academy-course-os-window--v2");
  if (windowNode) windowNode.dataset.ceV4Surface = "true";
  qa(".review-os-window-controls, .academy-v2-topbar .review-os-window-controls").forEach((node) => node.remove());
}

function mount() {
  enhanceTasks();
  enhanceReview();
  recoverPublishing();
  enhanceTableSearch("/workspace/stats", ".results-ledger-shell", "Поиск по результатам");
  enhanceTableSearch("/workspace/payouts", ".results-ledger-shell", "Поиск по реестру выплат");
  normalizeAcademy();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => { runtime.queued = false; mount(); });
}

new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineOperationsV4 = Object.freeze({ schedule });
