/* Task productivity core: tab-scoped registry, task extraction and state. */

export const PRODUCTIVITY_STORAGE_KEY = "contentengine.workspace-productivity.v1";
export const PRODUCTIVITY_PENDING_KEY = "contentengine.workspace-productivity.pending.v1";
export const PRODUCTIVITY_TASK_SELECTOR = '[data-workspace-focusable="true"]';
export const PRODUCTIVITY_TYPING_SELECTOR = "input, textarea, select, [contenteditable='true']";
export const PRODUCTIVITY_WIP_LIMIT = 3;
const ROUTE_PREFIXES = ["/workspace/", "/learn"];
const MAX_TASKS = 80;
const MAX_EVENTS = 20;
const STALE_MS = 24 * 60 * 60 * 1000;
const ID_ATTRIBUTES = [
  "taskId", "workspaceItemKey", "generationJobId", "reviewId", "mediaId",
  "placementId", "payoutId", "publicationId", "folderId",
];

export const state = {
  shell: null,
  tasks: new Map(),
  selectedKey: "",
  dock: null,
  mountQueued: false,
  saveTimer: 0,
  memory: readMemory(),
};

export const q = (selector, root = document) => root?.querySelector?.(selector) || null;
export const qa = (selector, root = document) => [...(root?.querySelectorAll?.(selector) || [])];

export function sessionStore() {
  try { return window.sessionStorage; } catch { return null; }
}

export function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

export function routeQuery() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return new URLSearchParams(raw.includes("?") ? raw.split("?").slice(1).join("?") : "");
}

export function isProductivityRoute(route) {
  return ROUTE_PREFIXES.some((prefix) => String(route || "").startsWith(prefix));
}

function readMemory() {
  try {
    const parsed = JSON.parse(sessionStore()?.getItem(PRODUCTIVITY_STORAGE_KEY) || "{}");
    return {
      tasks: parsed?.tasks && typeof parsed.tasks === "object" ? parsed.tasks : {},
      order: Array.isArray(parsed?.order) ? parsed.order.slice(0, MAX_TASKS) : [],
      dockCollapsed: Boolean(parsed?.dockCollapsed),
    };
  } catch {
    return { tasks: {}, order: [], dockCollapsed: false };
  }
}

export function persistMemory() {
  const tasks = Object.fromEntries(
    [...state.tasks.entries()]
      .sort(([, left], [, right]) => Number(right.updatedAt || 0) - Number(left.updatedAt || 0))
      .slice(0, MAX_TASKS),
  );
  state.memory = {
    ...state.memory,
    tasks,
    order: state.memory.order.filter((key) => tasks[key]).slice(0, MAX_TASKS),
  };
  try { sessionStore()?.setItem(PRODUCTIVITY_STORAGE_KEY, JSON.stringify(state.memory)); } catch { /* optional */ }
}

export function schedulePersist() {
  window.clearTimeout(state.saveTimer);
  state.saveTimer = window.setTimeout(persistMemory, 160);
}

function normalizeTask(key, raw) {
  return {
    key,
    route: String(raw.route || "/workspace/home"),
    surfaceId: String(raw.surfaceId || ""),
    identity: String(raw.identity || ""),
    title: String(raw.title || "Рабочая задача").slice(0, 140),
    hint: String(raw.hint || "").slice(0, 280),
    status: String(raw.status || "active"),
    statusLabel: String(raw.statusLabel || "В работе").slice(0, 80),
    nextAction: String(raw.nextAction || "").slice(0, 180),
    readyWhen: String(raw.readyWhen || "").slice(0, 240),
    owner: String(raw.owner || "").slice(0, 120),
    deadline: String(raw.deadline || "").slice(0, 120),
    materialCount: Math.max(0, Number(raw.materialCount || 0)),
    pinned: Boolean(raw.pinned),
    parked: raw.parked && typeof raw.parked === "object" ? {
      reason: String(raw.parked.reason || "Ожидание").slice(0, 100),
      returnAt: String(raw.parked.returnAt || ""),
      note: String(raw.parked.note || "").slice(0, 500),
      parkedAt: Number(raw.parked.parkedAt || Date.now()),
    } : null,
    note: String(raw.note || "").slice(0, 2000),
    events: Array.isArray(raw.events) ? raw.events.slice(-MAX_EVENTS) : [],
    lastSeen: Number(raw.lastSeen || 0),
    updatedAt: Number(raw.updatedAt || 0),
  };
}

export function restoreTasks() {
  const now = Date.now();
  for (const [key, raw] of Object.entries(state.memory.tasks || {})) {
    if (!raw || typeof raw !== "object") continue;
    if (!raw.pinned && !raw.parked && !raw.note && now - Number(raw.lastSeen || raw.updatedAt || 0) > STALE_MS) continue;
    state.tasks.set(key, normalizeTask(key, raw));
  }
}

export function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function compact(value, limit = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

export function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function hash(value) {
  let result = 2166136261;
  for (const character of String(value || "")) {
    result ^= character.charCodeAt(0);
    result = Math.imul(result, 16777619);
  }
  return (result >>> 0).toString(36);
}

function explicitIdentity(surface) {
  for (const key of ID_ATTRIBUTES) {
    const own = String(surface.dataset?.[key] || "").trim();
    if (own) return `${key}:${own}`;
    const attribute = `data-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`;
    const child = surface.querySelector(`[${attribute}]`);
    const value = String(child?.dataset?.[key] || "").trim();
    if (value) return `${key}:${value}`;
  }
  return "";
}

export function surfaceTitle(surface) {
  return compact(q("h1, h2, h3, legend, .card-header strong, strong", surface)?.textContent || "Рабочая задача", 120);
}

function surfaceHint(surface) {
  return compact(
    q("p:not(.eyebrow), .muted, .tiny, small", surface)?.textContent
      || "Откройте задачу и продолжите работу с сохранённым контекстом.",
    240,
  );
}

function identity(surface, route = routePath()) {
  const explicit = explicitIdentity(surface);
  if (explicit) return explicit;
  if (surface.id) return `surface:${surface.id}`;
  return `title:${hash(`${route}|${surfaceTitle(surface)}`)}`;
}

function statusFromText(value) {
  const text = String(value || "").toLocaleLowerCase("ru-RU");
  if (/блок|ошиб|отклон|доработ|просроч|опас|failed|rejected/.test(text)) return ["blocked", compact(value, 70) || "Блокер"];
  if (/выплачен|заверш|готово|готов|одобрен|пройден|complete|success|done/.test(text)) return ["done", compact(value, 70) || "Готово"];
  if (/жд[её]т|ожидан|очеред|обработ|генерац|проверя|queued|pending|processing|review/.test(text)) return ["waiting", compact(value, 70) || "Ожидание"];
  if (/чернов|draft/.test(text)) return ["draft", compact(value, 70) || "Черновик"];
  return ["active", compact(value, 70) || "В работе"];
}

function surfaceStatus(surface) {
  const candidate = q("[data-status], .badge, .status-pill, .pill, [aria-label*='Статус'], [aria-label*='статус']", surface);
  return statusFromText(candidate?.dataset?.status || candidate?.textContent || "В работе");
}

function nextAction(surface) {
  const control = q(
    ".btn:not([disabled]):not([aria-disabled='true']), button:not([disabled]):not(.desk-focus-button):not(.workspace-task-quick-action), a.btn:not([aria-disabled='true'])",
    surface,
  );
  return compact(control?.textContent || "", 160);
}

function textAfterLabel(surface, pattern) {
  const label = qa("small, span, strong, p, dt, dd", surface)
    .find((element) => pattern.test(String(element.textContent || "").trim()));
  if (!label) return "";
  if (label.nextElementSibling) return compact(label.nextElementSibling.textContent, 220);
  return compact(label.parentElement?.textContent?.replace(label.textContent || "", ""), 220);
}

function readyWhen(surface) {
  return textAfterLabel(surface, /готово,? когда|критерий готовности|результат/i)
    || compact(q("[data-done-when], .home-next-action-proof strong", surface)?.textContent || "", 220);
}

function owner(surface) {
  const explicit = q("[data-owner], [data-assignee], .assignee, .task-owner", surface);
  return compact(explicit?.dataset?.owner || explicit?.dataset?.assignee || explicit?.textContent || textAfterLabel(surface, /ответственн|исполнитель|owner/i), 100);
}

function deadline(surface) {
  const time = q("time[datetime], [data-deadline], [data-due-at]", surface);
  return compact(time?.textContent || time?.dataset?.deadline || time?.dataset?.dueAt || time?.getAttribute("datetime") || textAfterLabel(surface, /срок|дедлайн|до\s+\d/i), 100);
}

function materialCount(surface) {
  return qa("img, video, audio, a[href]:not([href^='#/'])", surface)
    .filter((element) => !element.closest(".workspace-task-quick-actions, .workspace-focus-chrome"))
    .length;
}

function mergeTask(existing, next) {
  const keys = ["route", "surfaceId", "identity", "title", "hint", "status", "statusLabel", "nextAction", "readyWhen", "owner", "deadline", "materialCount"];
  const changed = !existing || keys.some((key) => String(existing?.[key] ?? "") !== String(next?.[key] ?? ""));
  return normalizeTask(next.key, {
    ...existing,
    ...next,
    pinned: existing?.pinned ?? false,
    parked: existing?.parked ?? null,
    note: existing?.note || "",
    events: existing?.events || [],
    updatedAt: changed ? Date.now() : Number(existing?.updatedAt || Date.now()),
  });
}

export function scanTasks() {
  const route = routePath();
  if (!isProductivityRoute(route)) return [];
  const surfaces = qa(PRODUCTIVITY_TASK_SELECTOR)
    .filter((surface) => surface.isConnected && !surface.closest(".workspace-overview, .workspace-context-panel"));
  const descriptors = surfaces.map((surface) => {
    const taskIdentity = identity(surface, route);
    const key = `${route}|${taskIdentity}`;
    const [status, statusLabel] = surfaceStatus(surface);
    const task = mergeTask(state.tasks.get(key), {
      key,
      route,
      surfaceId: String(surface.id || ""),
      identity: taskIdentity,
      title: surfaceTitle(surface),
      hint: surfaceHint(surface),
      status,
      statusLabel,
      nextAction: nextAction(surface),
      readyWhen: readyWhen(surface),
      owner: owner(surface),
      deadline: deadline(surface),
      materialCount: materialCount(surface),
      lastSeen: Date.now(),
    });
    state.tasks.set(key, task);
    surface.dataset.productivityTaskKey = key;
    return { task, surface };
  });
  schedulePersist();
  return descriptors;
}

export function surfaceByKey(key) {
  const direct = document.querySelector(`[data-productivity-task-key="${CSS.escape(key)}"]`);
  if (direct) return direct;
  const task = state.tasks.get(key);
  if (!task) return null;
  if (task.surfaceId) {
    const byId = document.getElementById(task.surfaceId);
    if (byId) return byId;
  }
  return qa(PRODUCTIVITY_TASK_SELECTOR).find((surface) => (
    explicitIdentity(surface) === task.identity || surfaceTitle(surface) === task.title
  )) || null;
}

export function liveLinks(surface) {
  if (!surface) return [];
  const seen = new Set();
  return qa("a[href]", surface)
    .map((anchor) => ({ href: String(anchor.href || ""), label: compact(anchor.textContent || anchor.getAttribute("aria-label") || "Открыть материал", 80) }))
    .filter((item) => {
      if (!/^https?:/i.test(item.href) || seen.has(item.href)) return false;
      try {
        const url = new URL(item.href);
        if (/token|signature|expires|apikey/i.test(url.search)) return false;
      } catch { return false; }
      seen.add(item.href);
      return true;
    })
    .slice(0, 6);
}

export function addEvent(task, type, label) {
  task.events = [...(task.events || []), { at: Date.now(), type, label: compact(label, 180) }].slice(-MAX_EVENTS);
  task.updatedAt = Date.now();
}

export function touchOrder(key) {
  state.memory.order = [key, ...state.memory.order.filter((item) => item !== key)].slice(0, MAX_TASKS);
}

export function mutateTask(task, changes, type = "", label = "") {
  Object.assign(task, changes, { updatedAt: Date.now() });
  if (type) addEvent(task, type, label);
  state.tasks.set(task.key, task);
  touchOrder(task.key);
  schedulePersist();
  document.dispatchEvent(new CustomEvent("contentengine:productivity-changed", { detail: { key: task.key } }));
}

export function isParkedDue(task) {
  const value = Date.parse(task?.parked?.returnAt || "");
  return Boolean(task?.parked && Number.isFinite(value) && value <= Date.now());
}

export function taskTone(task) {
  if (task.parked && !isParkedDue(task)) return "parked";
  if (isParkedDue(task)) return "return";
  return task.status || "active";
}

export function pinTask(task, pinned = !task.pinned) {
  mutateTask(task, { pinned, parked: pinned ? task.parked : null }, pinned ? "pinned" : "unpinned", pinned ? "Задача закреплена в Dock" : "Задача убрана из Dock");
  announce(pinned ? `Задача закреплена: ${task.title}` : `Задача откреплена: ${task.title}`);
}

export function unparkTask(task) {
  mutateTask(task, { parked: null, pinned: true }, "unparked", "Задача возвращена в активную работу");
  announce(`Задача возвращена: ${task.title}`);
}

export function activeDockTasks() {
  const ordered = state.memory.order.map((key) => state.tasks.get(key)).filter(Boolean);
  const pinned = ordered.filter((task) => task.pinned && (!task.parked || isParkedDue(task)));
  if (pinned.length) return pinned.slice(0, 7);
  return scanTasks().map(({ task }) => task).slice(0, 3);
}

export function parkedTasks() {
  return [...state.tasks.values()]
    .filter((task) => task.parked && !isParkedDue(task))
    .sort((left, right) => (Date.parse(left.parked.returnAt || "") || Infinity) - (Date.parse(right.parked.returnAt || "") || Infinity));
}

export function currentTask() {
  const focused = document.querySelector(".workspace-task-focused[data-productivity-task-key]");
  if (focused) return state.tasks.get(focused.dataset.productivityTaskKey || "") || null;
  const active = document.activeElement instanceof Element ? document.activeElement.closest("[data-productivity-task-key]") : null;
  if (active) return state.tasks.get(active.dataset.productivityTaskKey || "") || null;
  return scanTasks()[0]?.task || null;
}

export function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
}

export function announce(message) {
  let region = document.querySelector(".workspace-productivity-live-region");
  if (!region) {
    region = document.createElement("div");
    region.className = "workspace-productivity-live-region";
    region.setAttribute("aria-live", "polite");
    region.setAttribute("aria-atomic", "true");
    document.body.append(region);
  }
  region.textContent = "";
  window.setTimeout(() => { region.textContent = message; }, 20);
}

restoreTasks();
