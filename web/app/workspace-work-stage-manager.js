/*
 * ContentEngine Work Stage Manager + Tasks Desk.
 * Moves existing work/task DOM into spatial desktop layouts without replacing
 * the server-backed filters, links, forms or transition actions.
 */

const WORK_ROUTE = "/workspace/work";
const TASKS_ROUTE = "/workspace/tasks";
const STATE_KEY = "contentengine.work-stage.v3";
const INTENT_KEY = "contentengine.os-v3.work-intent";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const ICONS = Object.freeze({
  now: '<path d="M12 3v9l5 3"/><circle cx="12" cy="12" r="9"/>',
  waiting: '<path d="M7 3h10v4a5 5 0 0 1-2 4 5 5 0 0 1 2 4v6H7v-6a5 5 0 0 1 2-4 5 5 0 0 1-2-4V3Z"/><path d="M9 7h6M9 17h6"/>',
  next: '<path d="M5 12h13"/><path d="m14 7 5 5-5 5"/>',
  filter: '<path d="M4 5h16l-6 7v6l-4 2v-8L4 5Z"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  task: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  handoff: '<path d="M4 12h13"/><path d="m13 7 5 5-5 5"/><path d="M4 5v14"/>',
  capsule: '<path d="M8 3h8a5 5 0 0 1 0 10H8A5 5 0 0 1 8 3Z"/><path d="m8 13 8-10"/>',
});

const runtime = {
  queued: false,
  workPage: null,
  taskPage: null,
  workShell: null,
  taskShell: null,
  controlsOpen: false,
  selectedWorkId: "",
  selectedTaskId: "",
  memory: readMemory(),
};

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

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.task}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function compact(value, limit = 100) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function readMemory() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STATE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function remember(patch) {
  runtime.memory = { ...runtime.memory, ...patch };
  try { window.localStorage.setItem(STATE_KEY, JSON.stringify(runtime.memory)); } catch { /* optional */ }
}

function workItemId(item, index = 0) {
  return String(item?.dataset?.workItemId || `work-${index}`);
}

function taskId(card, index = 0) {
  return String(card?.dataset?.taskId || `task-${index}`);
}

function workFacts(item) {
  const title = compact(q(".my-work-item-copy h3, h3, strong", item)?.textContent || "Работа", 130);
  const status = compact(q(".my-work-status, .badge", item)?.textContent || "", 80);
  const type = compact(q(".my-work-item-meta > span:first-child", item)?.textContent || item.dataset.workItemType || "Задача", 60);
  const text = `${status} ${item.textContent}`.toLocaleLowerCase("ru-RU");
  const blocker = item.dataset.workItemBlocker === "true" || /блокер|ошибка|отклонено|просрочено/u.test(text);
  const overdue = item.classList.contains("my-work-item--overdue") || /просрочено/u.test(text);
  const waiting = /жд[её]т|ожидани|очеред|обрабатыва|проверки|pending|queued|processing|scheduled/u.test(text) && !blocker;
  const actionRequired = item.dataset.workItemActionRequired === "true" || blocker || overdue;
  const lane = actionRequired ? "now" : waiting ? "waiting" : "next";
  return { title, status, type, blocker, overdue, waiting, actionRequired, lane };
}

function taskFacts(card) {
  const title = compact(q(".task-top h3, h3, strong", card)?.textContent || "Задача", 130);
  const status = compact(q(".task-top .badge, .badge", card)?.textContent || "", 70);
  const text = `${status} ${card.textContent}`.toLocaleLowerCase("ru-RU");
  return {
    title,
    status,
    blocker: /блок|ошиб|отклон|просроч/u.test(text),
    complete: /готово|заверш|выполн|отмен/u.test(text) && !q("[data-action='transition-task']", card),
  };
}

function createWorkTopbar() {
  return elementFrom(`
    <header class="work-stage-topbar">
      <div class="work-stage-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="work-stage-title"><small>ContentEngine · Stage Manager</small><strong>Моя работа</strong></div>
      <div class="work-stage-actions">
        <button type="button" data-work-stage-controls>${icon("filter", 17)}<span>Фильтры</span></button>
        <button type="button" data-action="toggle-work-notifications">${icon("bell", 17)}<span>События</span></button>
        <button type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 18)}</button>
      </div>
    </header>`);
}

function createWorkShell() {
  return elementFrom(`
    <section class="work-stage-shell" aria-label="Stage Manager работы">
      <header class="work-stage-summary">
        <div><small>ВНИМАНИЕ, А НЕ ЕЩЁ ОДИН КАНБАН</small><h1>Что движется сейчас</h1><p>Активная работа, ожидания и следующая очередь разложены отдельно. Блокер не прячется среди спокойных задач.</p></div>
        <div class="work-stage-summary-metrics">
          <button type="button" data-work-stage-jump="now"><small>Сейчас</small><strong data-work-stage-count="now">0</strong></button>
          <button type="button" data-work-stage-jump="waiting"><small>Жду</small><strong data-work-stage-count="waiting">0</strong></button>
          <button type="button" data-work-stage-jump="next"><small>Дальше</small><strong data-work-stage-count="next">0</strong></button>
          <button type="button" data-work-stage-jump="blocked"><small>Блокеры</small><strong data-work-stage-count="blocked">0</strong></button>
        </div>
      </header>
      <div class="work-stage-lanes">
        <section class="work-stage-lane work-stage-lane--now" data-work-stage-lane="now"><header><span>${icon("now", 18)}</span><div><small>СЕЙЧАС</small><strong>Требует решения</strong></div></header><div data-work-stage-items="now"></div></section>
        <section class="work-stage-lane work-stage-lane--waiting" data-work-stage-lane="waiting"><header><span>${icon("waiting", 18)}</span><div><small>ЖДУ</small><strong>Не держать в голове</strong></div></header><div data-work-stage-items="waiting"></div></section>
        <section class="work-stage-lane work-stage-lane--next" data-work-stage-lane="next"><header><span>${icon("next", 18)}</span><div><small>ДАЛЬШЕ</small><strong>Очередь без тревоги</strong></div></header><div data-work-stage-items="next"></div></section>
      </div>
      <aside class="work-stage-controls" aria-hidden="true"><header><div><small>УПРАВЛЕНИЕ ОЧЕРЕДЬЮ</small><strong>Фильтры и представления</strong></div><button type="button" data-work-stage-controls-close aria-label="Закрыть">×</button></header><div data-work-stage-controls-body></div></aside>
      <button class="work-stage-controls-backdrop" type="button" data-work-stage-controls-close aria-label="Закрыть фильтры" hidden></button>
    </section>`);
}

function mountWork() {
  if (routePath() !== WORK_ROUTE) {
    document.body.classList.remove("contentengine-work-stage-open");
    runtime.workPage = null;
    runtime.workShell = null;
    return;
  }
  const page = q(".my-work-page");
  const queue = q(".my-work-queue", page);
  const items = qa(":scope > .my-work-item", queue);
  if (!page || !queue) return;
  document.body.classList.add("contentengine-work-stage-open");
  runtime.workPage = page;
  if (page.dataset.workStageReady === "true") return;
  page.dataset.workStageReady = "true";
  page.classList.add("work-stage-page");
  const topbar = createWorkTopbar();
  const shell = createWorkShell();
  runtime.workShell = shell;
  const hero = q(":scope > .my-work-hero", page);
  hero?.before(topbar, shell);

  const controlsBody = q("[data-work-stage-controls-body]", shell);
  const sidebar = q(":scope > .my-work-layout > .my-work-sidebar", page);
  const filter = q("#my-work-filter-form", page);
  if (sidebar) controlsBody.append(sidebar);
  if (filter) controlsBody.append(filter);

  const laneCounts = { now: 0, waiting: 0, next: 0, blocked: 0 };
  items.forEach((item, index) => {
    const facts = workFacts(item);
    const id = workItemId(item, index);
    item.dataset.workStageLane = facts.lane;
    item.dataset.workStageId = id;
    item.classList.add("work-stage-item");
    item.tabIndex = 0;
    q(`[data-work-stage-items='${facts.lane}']`, shell)?.append(item);
    laneCounts[facts.lane] += 1;
    if (facts.blocker) laneCounts.blocked += 1;
  });
  Object.entries(laneCounts).forEach(([lane, value]) => {
    const target = q(`[data-work-stage-count='${lane}']`, shell);
    if (target) target.textContent = String(value);
  });
  q(".my-work-layout", page)?.remove();
  hero?.remove();
  q(":scope > .my-work-summary", page)?.remove();
  q(":scope > .my-work-queue", page)?.remove();

  const select = (item, { focus = false } = {}) => {
    if (!item) return;
    qa(".work-stage-item", shell).forEach((candidate) => candidate.classList.toggle("is-selected", candidate === item));
    runtime.selectedWorkId = item.dataset.workStageId || "";
    remember({ selectedWorkId: runtime.selectedWorkId });
    if (focus) item.focus({ preventScroll: true });
  };
  const preferred = qa(".work-stage-item", shell).find((item) => item.dataset.workStageId === runtime.memory.selectedWorkId)
    || q("[data-work-stage-items='now'] .work-stage-item", shell)
    || q(".work-stage-item", shell);
  select(preferred);

  shell.addEventListener("click", (event) => {
    const item = event.target instanceof Element ? event.target.closest(".work-stage-item") : null;
    if (item && !event.target.closest("a, button, input, select, textarea")) select(item);
    const jump = event.target instanceof Element ? event.target.closest("[data-work-stage-jump]") : null;
    if (jump) {
      const lane = jump.dataset.workStageJump === "blocked" ? "now" : jump.dataset.workStageJump;
      q(`[data-work-stage-lane='${lane}']`, shell)?.scrollIntoView({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "nearest", inline: "center" });
    }
    if (event.target instanceof Element && event.target.closest("[data-work-stage-controls-close]")) setControlsOpen(false);
  });
  topbar.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-work-stage-controls]")) setControlsOpen(!runtime.controlsOpen);
  });

  const intent = readIntent();
  if (intent?.filter === "blocked") {
    qa(".work-stage-item", shell).forEach((item) => { item.hidden = !workFacts(item).blocker; });
  }
  if (intent?.lane && ["now", "waiting", "next"].includes(intent.lane)) {
    window.setTimeout(() => q(`[data-work-stage-lane='${intent.lane}']`, shell)?.scrollIntoView({ inline: "center", behavior: REDUCED_MOTION.matches ? "auto" : "smooth" }), 80);
  }
  clearIntent();
  dispatchSnapshot(laneCounts);
}

function readIntent() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(INTENT_KEY) || "null");
    return value && Date.now() - Number(value.at || 0) < 60000 ? value : null;
  } catch {
    return null;
  }
}

function clearIntent() {
  try { window.sessionStorage.removeItem(INTENT_KEY); } catch { /* optional */ }
}

function dispatchSnapshot(counts) {
  const detail = {
    now: Number(counts.now || 0),
    waiting: Number(counts.waiting || 0),
    next: Number(counts.next || 0),
    blockers: Number(counts.blocked || 0),
    drafts: qa(".workspace-draft-indicator, .workspace-overview-draft").length,
  };
  window.dispatchEvent(new CustomEvent("contentengine:os-v3-work-snapshot", { detail }));
}

function setControlsOpen(open) {
  runtime.controlsOpen = Boolean(open);
  const shell = runtime.workShell;
  if (!shell) return;
  const controls = q(".work-stage-controls", shell);
  const backdrop = q(".work-stage-controls-backdrop", shell);
  shell.classList.toggle("controls-open", runtime.controlsOpen);
  controls.setAttribute("aria-hidden", runtime.controlsOpen ? "false" : "true");
  backdrop.hidden = !runtime.controlsOpen;
  if (runtime.controlsOpen) q("input, select, button", controls)?.focus({ preventScroll: true });
}

function createTaskTopbar() {
  return elementFrom(`
    <header class="tasks-desk-topbar">
      <div class="tasks-desk-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="tasks-desk-title"><small>ContentEngine · Tasks</small><strong data-tasks-desk-title>Задачи</strong></div>
      <div class="tasks-desk-actions"><button type="button" data-tasks-desk-handoff>${icon("handoff", 17)}<span>Передать</span></button><button type="button" data-tasks-desk-capsule>${icon("capsule", 17)}<span>Капсула</span></button><button type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 18)}</button></div>
    </header>`);
}

function createTaskShell() {
  return elementFrom(`
    <section class="tasks-desk-shell" aria-label="Рабочий стол задач">
      <aside class="tasks-desk-sidebar"><header><small>ОЧЕРЕДЬ</small><strong>Назначенная работа</strong><span data-tasks-desk-count></span></header><div class="tasks-desk-list" role="listbox"></div></aside>
      <main class="tasks-desk-main"><div class="tasks-desk-stage"></div><footer class="tasks-desk-footer"><button type="button" data-tasks-desk-prev>${icon("left", 18)}<span>Предыдущая</span></button><div><small>Задача</small><strong data-tasks-desk-position></strong></div><button type="button" data-tasks-desk-next><span>Следующая</span>${icon("right", 18)}</button></footer></main>
    </section>`);
}

function buildTaskList() {
  const list = q(".tasks-desk-list", runtime.taskShell);
  if (!list) return;
  const cards = qa(".task-card", runtime.taskShell);
  list.innerHTML = cards.map((card, index) => {
    const facts = taskFacts(card);
    const id = taskId(card, index);
    return `<button type="button" class="tasks-desk-list-item${id === runtime.selectedTaskId ? " is-active" : ""}" data-tasks-desk-id="${escapeMarkup(id)}"><span>${icon("task", 18)}</span><span><strong>${escapeMarkup(facts.title)}</strong><small>${escapeMarkup(facts.status || (facts.complete ? "Готово" : "В работе"))}</small></span><i data-tone="${facts.blocker ? "danger" : facts.complete ? "success" : "warning"}"></i></button>`;
  }).join("");
  q("[data-tasks-desk-count]", runtime.taskShell).textContent = `${cards.length} задач`;
}

function selectTask(id, { focus = false } = {}) {
  const cards = qa(".task-card", runtime.taskShell);
  const card = cards.find((item, index) => taskId(item, index) === String(id)) || cards[0];
  if (!card) return;
  const previous = cards.find((item) => item.classList.contains("is-selected"));
  runtime.selectedTaskId = taskId(card, cards.indexOf(card));
  cards.forEach((item) => {
    const active = item === card;
    item.classList.toggle("is-selected", active);
    item.hidden = !active;
    item.inert = !active;
    item.setAttribute("aria-hidden", active ? "false" : "true");
  });
  const index = cards.indexOf(card);
  q("[data-tasks-desk-position]", runtime.taskShell).textContent = `${index + 1} / ${cards.length}`;
  q("[data-tasks-desk-prev]", runtime.taskShell).disabled = index <= 0;
  q("[data-tasks-desk-next]", runtime.taskShell).disabled = index >= cards.length - 1;
  q("[data-tasks-desk-title]", runtime.taskPage).textContent = taskFacts(card).title;
  remember({ selectedTaskId: runtime.selectedTaskId });
  buildTaskList();
  if (previous !== card && !REDUCED_MOTION.matches && typeof card.animate === "function") {
    card.animate([
      { opacity: 0, transform: `translate3d(${index >= cards.indexOf(previous) ? 44 : -44}px,0,0) scale(.98)`, filter: "blur(5px)" },
      { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "blur(0)" },
    ], { duration: 470, easing: SPRING });
  }
  if (focus) q("button, a, input, textarea, select", card)?.focus({ preventScroll: true });
}

function mountTasks() {
  if (routePath() !== TASKS_ROUTE) {
    document.body.classList.remove("contentengine-tasks-desk-open");
    runtime.taskPage = null;
    runtime.taskShell = null;
    return;
  }
  const list = q(".task-list");
  const page = list?.closest?.(".page-wrap");
  const cards = qa(":scope > .task-card", list);
  if (!page || !cards.length) return;
  document.body.classList.add("contentengine-tasks-desk-open");
  runtime.taskPage = page;
  if (page.dataset.tasksDeskReady === "true") return;
  page.dataset.tasksDeskReady = "true";
  page.classList.add("tasks-desk-page");
  const topbar = createTaskTopbar();
  const shell = createTaskShell();
  runtime.taskShell = shell;
  const anchor = q(":scope > .page-header", page) || page.firstElementChild;
  anchor?.after?.(topbar, shell);
  const stage = q(".tasks-desk-stage", shell);
  cards.forEach((card) => {
    card.classList.add("tasks-desk-card");
    stage.append(card);
  });
  list.remove();
  runtime.selectedTaskId = String(runtime.memory.selectedTaskId || taskId(cards[0], 0));
  buildTaskList();
  selectTask(runtime.selectedTaskId);

  q(".tasks-desk-list", shell).addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-tasks-desk-id]") : null;
    if (button) selectTask(button.dataset.tasksDeskId, { focus: true });
  });
  q(".tasks-desk-footer", shell).addEventListener("click", (event) => {
    const current = qa(".task-card", shell).findIndex((card) => card.classList.contains("is-selected"));
    if (event.target instanceof Element && event.target.closest("[data-tasks-desk-prev]")) selectTask(taskId(cards[current - 1], current - 1), { focus: true });
    if (event.target instanceof Element && event.target.closest("[data-tasks-desk-next]")) selectTask(taskId(cards[current + 1], current + 1), { focus: true });
  });
  topbar.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-tasks-desk-handoff]")) window.ContentEngineOSV3?.openHandoff?.();
    if (event.target instanceof Element && event.target.closest("[data-tasks-desk-capsule]")) window.ContentEngineOSV3?.openCapsule?.();
  });
}

function handleKeydown(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  if (routePath() === TASKS_ROUTE && runtime.taskShell && event.altKey && !event.shiftKey) {
    const cards = qa(".task-card", runtime.taskShell);
    const current = cards.findIndex((card) => card.classList.contains("is-selected"));
    if (event.key === "ArrowLeft" && current > 0) {
      event.preventDefault();
      selectTask(taskId(cards[current - 1], current - 1), { focus: true });
    }
    if (event.key === "ArrowRight" && current < cards.length - 1) {
      event.preventDefault();
      selectTask(taskId(cards[current + 1], current + 1), { focus: true });
    }
  }
  if (routePath() === WORK_ROUTE && runtime.controlsOpen && event.key === "Escape") {
    event.preventDefault();
    setControlsOpen(false);
  }
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mountWork();
    mountTasks();
  });
}

new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleKeydown);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
