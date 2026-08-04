/*
 * ContentEngine Desktop v4.
 *
 * One web workspace, one Dock, one visible action. This module composes the
 * already permission-checked DOM. It never calls business APIs, submits forms,
 * reads secrets or clones file inputs.
 */

import { isWorkspaceActionKey, workspaceActionKey } from "./workspace-action-key.js?v=20260804.os4.11";

const BUILD = "20260804.os4.11";
const STORAGE_KEY = "contentengine.desktop-v4.v1";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const PROJECT_CONTEXT_KEY = "contentengine.desktop-v4.project";
const CLOSE_TRANSIENTS_EVENT = "contentengine:v4-close-transients";
const SVG_NS = "http://www.w3.org/2000/svg";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

/*
 * The Dock is the primary workspace switcher. Research and governed AI
 * learning sit beside the production flow; infrequent tools stay in the menu.
 */
const ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/home", label: "Проекты", icon: "home", description: "Выберите рабочий стол или создайте новый" }),
  Object.freeze({ route: "/workspace/board", label: "Файлы", icon: "folder", description: "Папки, видео, поиск и исходники" }),
  Object.freeze({ route: "/workspace/generation", label: "Создать", icon: "spark", description: "Один ролик или фото за запуск" }),
  Object.freeze({ route: "/workspace/review", label: "Проверить", icon: "check", description: "Качество, риски и одно решение" }),
  Object.freeze({ route: "/workspace/placement", label: "Опубликовать", icon: "upload", description: "Один пост — один маршрут" }),
  Object.freeze({ route: "/workspace/stats", label: "Результаты", icon: "chart", description: "Метрики и следующая гипотеза" }),
  Object.freeze({ route: "/workspace/research", label: "Исследования", icon: "search", description: "Факты, источники и сценарии" }),
  Object.freeze({ route: "/workspace/ai", label: "ИИ-центр", icon: "spark", description: "Знания категорий и обратная связь" }),
]);

const SECONDARY_ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/team", label: "Команда", icon: "work", description: "Доступы и участники" }),
  Object.freeze({ route: "/workspace/feedback", label: "Помощь", icon: "tasks", description: "Сообщить о препятствии" }),
]);

const CONTEXT_ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/tasks", label: "Задача", icon: "tasks", description: "Одно назначенное действие внутри текущего этапа" }),
  Object.freeze({ route: "/workspace/work", label: "Моя работа", icon: "work", description: "Личная очередь и уведомления" }),
]);
const ALL_ROUTES = Object.freeze([...ROUTES, ...SECONDARY_ROUTES, ...CONTEXT_ROUTES]);
const PROJECT_FLOW = Object.freeze([
  Object.freeze({ code: "files", route: "/workspace/board", label: "Файлы", countLabel: "файлов" }),
  Object.freeze({ code: "generation", route: "/workspace/generation", label: "Создать", countLabel: "запусков" }),
  Object.freeze({ code: "review", route: "/workspace/review", label: "Проверить", countLabel: "на проверке" }),
  Object.freeze({ code: "placement", route: "/workspace/placement", label: "Опубликовать", countLabel: "к публикации" }),
  Object.freeze({ code: "stats", route: "/workspace/stats", label: "Результат", countLabel: "результатов" }),
]);
const PROJECT_STAGE_ALIASES = Object.freeze({
  board: "files",
  file: "files",
  files: "files",
  materials: "files",
  media: "files",
  create: "generation",
  generation: "generation",
  generated: "generation",
  quality: "review",
  review: "review",
  check: "review",
  publish: "placement",
  publishing: "placement",
  placement: "placement",
  result: "stats",
  results: "stats",
  metrics: "stats",
  stats: "stats",
});
const PROJECT_STAGE_STATE_LABELS = Object.freeze({
  done: "Готово",
  current: "Текущий этап",
  blocked: "Нужна помощь",
  future: "После текущего этапа",
  unknown: "Статус уточняется",
});
const ROLE_GATED_ROUTES = new Set(["/workspace/research", "/workspace/ai", "/workspace/team"]);
const PROJECT_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const NEXT_ACTION_PATHS = new Set([
  ...ALL_ROUTES.map((item) => item.route),
  "/workspace/media",
  "/workspace/payouts",
]);

const ICONS = Object.freeze({
  home: ["M3 10.5 12 3l9 7.5", "M5.5 9.5V21h13V9.5", "M9 21v-6h6v6"],
  folder: ["M3 6h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"],
  spark: ["M12 2v5M12 17v5M2 12h5M17 12h5", "m5 5 3.4 3.4m7.2 7.2L19 19m0-14-3.4 3.4m-7.2 7.2L5 19", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"],
  check: ["M8 4h8M9 3h6v3H9z", "M5 5h14v16H5z", "m9 13 2 2 4-5"],
  work: ["M3 7h18v12H3z", "M8 7V4h8v3", "M3 12h18", "M9 12v2h6v-2"],
  tasks: ["M9 6h11M9 12h11M9 18h11", "m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5"],
  upload: ["M12 3v12", "m7 8 5-5 5 5", "M5 13v6h14v-6"],
  chart: ["M4 20V10M10 20V4M16 20v-7M22 20H2"],
  money: ["M3 5h18v14H3z", "M7 9h10M7 15h4", "M16 12a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z"],
  grid: ["M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z", "m16 16 4 4"],
  refresh: ["M20 7v5h-5", "M4 17v-5h5", "M6.1 8A7 7 0 0 1 19 10M17.9 16A7 7 0 0 1 5 14"],
  bell: ["M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9Z", "M10 21h4"],
  focus: ["M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"],
  close: ["m6 6 12 12M18 6 6 18"],
  left: ["m15 18-6-6 6-6"],
  right: ["m9 18 6-6-6-6"],
  clock: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z", "M12 8v5l3 2"],
  trash: ["M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"],
});

const runtime = {
  route: routePath(),
  actionKey: workspaceActionKey(),
  queued: false,
  mounting: false,
  needsMount: false,
  observer: null,
  observerRoot: null,
  adapters: new Map(),
  flushWaiters: [],
  menubar: null,
  dock: null,
  mission: null,
  spotlight: null,
  spotlightRecords: [],
  spotlightIndex: 0,
  zen: null,
  videoObserver: null,
  observedVideos: new WeakSet(),
  clockTimer: 0,
  scrollTimer: 0,
  fullscreenListening: false,
  handoffTimer: 0,
  restoredRoute: "",
  restoredScrollNodes: new WeakSet(),
  pendingActionReset: "",
  preNavigationActionKey: "",
  state: readState(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function icon(name, size = 20) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add("ce-v4-icon");
  (ICONS[name] || ICONS.home).forEach((data) => {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", data);
    svg.append(path);
  });
  return svg;
}

function iconButton(className, label, name) {
  const button = create("button", className);
  button.type = "button";
  button.setAttribute("aria-label", label);
  button.title = label;
  button.append(icon(name));
  return button;
}

function compact(value, limit = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function isVisible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function routeQuery() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return new URLSearchParams(raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "");
}

function routeParts(route) {
  const raw = String(route || "/workspace/home").replace(/^#/, "");
  const splitAt = raw.indexOf("?");
  const path = (splitAt >= 0 ? raw.slice(0, splitAt) : raw) || "/workspace/home";
  const query = new URLSearchParams(splitAt >= 0 ? raw.slice(splitAt + 1) : "");
  return { path, query };
}

function routeWithProject(route, projectId = "") {
  const { path, query } = routeParts(route);
  const canonicalProjectId = String(projectId || "").trim();
  if (path.startsWith("/workspace/") && canonicalProjectId && !query.has("project_id")) {
    query.set("project_id", canonicalProjectId);
  }
  query.delete("project");
  const search = query.toString();
  return `${path}${search ? `?${search}` : ""}`;
}

function routeMatches(route, expected) {
  if (expected === "/workspace/home") return route === expected;
  if (expected === "/workspace/board") return route === expected || route === "/workspace/media";
  if (expected === "/workspace/stats") return route === expected || route === "/workspace/payouts";
  return route === expected;
}

function routeRecord(route = routePath()) {
  return ALL_ROUTES.find((item) => route === item.route)
    || ALL_ROUTES.find((item) => routeMatches(route, item.route))
    || ROUTES[0];
}

function isWorkspaceRoute(route = routePath()) {
  return route.startsWith("/workspace/");
}

function hasAuthenticatedWorkspace() {
  return Boolean(
    q(".workspace-shell[data-workspace-section]")
    && q("#workspace-content"),
  );
}

function navigate(route, options) {
  const settings = options || {};
  const requested = String(route || "/workspace/home");
  const requestedProjectId = routeParts(requested).query.get("project_id");
  const currentProjectId = routeQuery().get("project_id") || projectContext()?.id || "";
  const destination = settings.preserveProject === false
    ? routeWithProject(requested, requestedProjectId || "")
    : routeWithProject(requested, requestedProjectId || currentProjectId);
  captureCurrentAction();
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  closeTransientOverlays(true);
  window.location.hash = `#${destination}`;
  return destination;
}

function focusFinderSearch(query = "") {
  const value = String(query || "").trim();
  if (value) storage("session")?.setItem(FINDER_QUERY_KEY, value);
  if (routePath() !== "/workspace/board") navigate("/workspace/board");
  let attempts = 0;
  const focus = () => {
    const input = q('#workspace-board-filter-form input[name="query"]');
    if (input instanceof HTMLElement) {
      if (value && input.value !== value) input.value = value;
      input.focus({ preventScroll: true });
      if (value) input.form?.requestSubmit?.();
      return;
    }
    attempts += 1;
    if (attempts < 24) window.requestAnimationFrame(focus);
  };
  window.requestAnimationFrame(focus);
}

function runGlobalSearch(form) {
  const input = q("input[type='search']", form);
  const query = String(input?.value || "").trim();
  focusFinderSearch(query);
}

function fullscreenElement() {
  return document.fullscreenElement || document.webkitFullscreenElement || null;
}

function fullscreenMode() {
  const root = document.documentElement;
  const standard = typeof root.requestFullscreen === "function"
    && typeof document.exitFullscreen === "function"
    && document.fullscreenEnabled !== false;
  const webkit = typeof root.webkitRequestFullscreen === "function"
    && typeof document.webkitExitFullscreen === "function"
    && document.webkitFullscreenEnabled !== false;
  if (standard) return "standard";
  if (webkit) return "webkit";
  return "";
}

function fullscreenSupported() {
  return Boolean(fullscreenMode());
}

function showSystemToast(message, tone = "warning") {
  const region = q("#toast-region") || document.body;
  const toast = create("div", `ce-v4-system-toast is-${tone}`);
  toast.setAttribute("role", tone === "error" ? "alert" : "status");
  toast.append(create("span", "", message));
  region.append(toast);
  window.setTimeout(() => {
    if (!toast.isConnected) return;
    if (REDUCED_MOTION.matches) toast.remove();
    else {
      toast.classList.add("is-closing");
      window.setTimeout(() => toast.remove(), 180);
    }
  }, 4200);
}

function updateFullscreenControl() {
  const control = q("[data-ce-v4-fullscreen]", runtime.menubar);
  if (!control) return;
  const supported = fullscreenSupported();
  control.hidden = !supported;
  control.disabled = !supported;
  if (!supported) {
    const unavailable = "Полноэкранный режим недоступен в этом браузере";
    control.setAttribute("aria-label", unavailable);
    control.setAttribute("aria-pressed", "false");
    control.title = unavailable;
    return;
  }
  const active = Boolean(fullscreenElement());
  const label = active ? "Выйти из полноэкранного режима" : "Перейти в полноэкранный режим";
  control.setAttribute("aria-label", label);
  control.setAttribute("aria-pressed", String(active));
  control.title = label;
}

function toolsMenuParts() {
  const trigger = q("[data-ce-v4-tools-trigger]", runtime.menubar);
  const menu = q("[data-ce-v4-tools-menu]", runtime.menubar);
  const items = qa("[data-ce-v4-tools-route]", menu);
  return { trigger, menu, items };
}

function routeIsAuthorized(route) {
  if (!ROLE_GATED_ROUTES.has(route)) return true;
  const shell = q(".workspace-shell[data-workspace-section]");
  const declaredRoutes = String(shell?.dataset.workspaceAuthorizedRoutes || "")
    .split(/\s+/)
    .filter(Boolean);
  if (declaredRoutes.length) return declaredRoutes.includes(route);
  const navigation = q(".workspace-nav", shell);
  return qa("a[href]", navigation).some((link) => (
    String(link.getAttribute("href") || "").split("?")[0] === `#${route}`
  ));
}

function authorizedRoutes(routes) {
  return routes.filter((item) => routeIsAuthorized(item.route));
}

function createToolsMenuItem(item) {
  const link = create("a", "ce-v4-menubar__tools-item");
  link.href = `#${item.route}`;
  link.dataset.ceV4ToolsRoute = item.route;
  link.setAttribute("role", "menuitem");
  const tile = create("span", "ce-v4-menubar__tools-icon");
  tile.append(icon(item.icon, 18));
  const copy = create("span", "ce-v4-menubar__tools-copy");
  copy.append(create("strong", "", item.label), create("small", "", item.description));
  link.append(tile, copy);
  return link;
}

function syncToolsMenu() {
  const menu = q("[data-ce-v4-tools-menu]", runtime.menubar);
  if (!menu) return;
  const existing = new Map(qa("[data-ce-v4-tools-route]", menu).map((link) => [link.dataset.ceV4ToolsRoute, link]));
  authorizedRoutes(SECONDARY_ROUTES).forEach((item) => {
    const link = existing.get(item.route) || createToolsMenuItem(item);
    link.href = `#${projectRoute(item.route)}`;
    menu.append(link);
    existing.delete(item.route);
  });
  existing.forEach((link) => link.remove());
}

function closeToolsMenu(restoreFocus = false) {
  const { trigger, menu } = toolsMenuParts();
  if (!trigger || !menu) return;
  const wasOpen = !menu.hidden;
  menu.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  if (restoreFocus && wasOpen) safeFocus(trigger);
}

function openToolsMenu(focusIndex = -1) {
  const { trigger, menu, items } = toolsMenuParts();
  if (!trigger || !menu) return;
  closeProjectMenu();
  menu.hidden = false;
  trigger.setAttribute("aria-expanded", "true");
  if (focusIndex >= 0 && items.length) safeFocus(items[Math.min(focusIndex, items.length - 1)]);
}

function toggleToolsMenu() {
  const { menu } = toolsMenuParts();
  if (!menu || menu.hidden) openToolsMenu();
  else closeToolsMenu();
}

function handleToolsMenuKeydown(event) {
  const { trigger, menu, items } = toolsMenuParts();
  if (!trigger || !menu || !items.length) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target === trigger && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    openToolsMenu(event.key === "ArrowUp" ? items.length - 1 : 0);
    return;
  }
  if (menu.hidden) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeToolsMenu(true);
    return;
  }
  if (event.key === "Tab") {
    closeToolsMenu();
    return;
  }
  const current = items.indexOf(target?.closest?.("[data-ce-v4-tools-route]"));
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? items.length - 1
      : (Math.max(0, current) + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
  safeFocus(items[next]);
}

async function toggleFullscreen() {
  const mode = fullscreenMode();
  if (!mode) {
    updateFullscreenControl();
    showSystemToast("Полноэкранный режим не поддерживается этим браузером.", "warning");
    return;
  }
  try {
    if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
      await document.exitFullscreen();
    } else if (document.webkitFullscreenElement && typeof document.webkitExitFullscreen === "function") {
      await document.webkitExitFullscreen();
    } else if (mode === "standard") {
      await document.documentElement.requestFullscreen({ navigationUI: "hide" });
    } else if (mode === "webkit") {
      await document.documentElement.webkitRequestFullscreen();
    }
  } catch (error) {
    console.warn("ContentEngine fullscreen request was rejected", error);
    showSystemToast("Браузер не разрешил полноэкранный режим. Проверьте разрешения сайта.", "error");
  }
  updateFullscreenControl();
}

function refreshWorkspace() {
  const page = currentPage();
  const control = q(
    '[data-action="refresh-section"], [data-action="refresh-home"], [data-action="refresh-ai-learning"]',
    page,
  );
  if (control instanceof HTMLElement) control.click();
}

function storage(kind = "session") {
  try { return kind === "local" ? window.localStorage : window.sessionStorage; }
  catch { return null; }
}

function readJson(target, key, fallback) {
  try {
    const value = JSON.parse(target?.getItem(key) || "null");
    return value === null || value === undefined ? fallback : value;
  } catch {
    return fallback;
  }
}

function writeJson(target, key, value) {
  try { target?.setItem(key, JSON.stringify(value)); }
  catch { /* UI state is optional. */ }
}

function readState() {
  const state = readJson(storage("local"), STORAGE_KEY, {});
  return state && typeof state === "object" && !Array.isArray(state) ? state : {};
}

function remember(patch) {
  runtime.state = { ...runtime.state, ...patch };
  writeJson(storage("local"), STORAGE_KEY, runtime.state);
}

function currentPage() {
  return qa(".workspace-main .page-wrap, .workspace-main .learning-page, #main-content > .page-wrap, #main-content > .learning-page")
    .filter(isVisible).at(-1) || q(".workspace-main") || q("#main-content");
}

function safeFocus(node) {
  if (node instanceof HTMLElement) node.focus({ preventScroll: true });
}

function animate(node, frames, duration = 380) {
  if (!node || REDUCED_MOTION.matches || typeof node.animate !== "function") return;
  node.animate(frames, { duration, easing: SPRING });
}

function handoff(route, options = {}) {
  const destination = String(route || "").trim();
  if (!destination) return Promise.resolve(false);
  window.clearTimeout(runtime.handoffTimer);
  const page = currentPage();
  page?.classList.remove("ce-v4-handoff-leaving");
  document.documentElement.dataset.ceV4Handoff = "true";
  window.requestAnimationFrame(() => page?.classList.add("ce-v4-handoff-leaving"));
  if (options.message) showSystemToast(String(options.message), options.tone || "success");
  const requestedDelay = Number(options.delay);
  const delay = REDUCED_MOTION.matches
    ? 0
    : Math.max(600, Math.min(800, Number.isFinite(requestedDelay) ? requestedDelay : 700));
  return new Promise((resolve) => {
    runtime.handoffTimer = window.setTimeout(() => {
      page?.classList.remove("ce-v4-handoff-leaving");
      delete document.documentElement.dataset.ceV4Handoff;
      runtime.handoffTimer = 0;
      navigate(destination);
      resolve(true);
    }, delay);
  });
}

function projectMenuParts() {
  const trigger = q("[data-ce-v4-project-trigger]", runtime.menubar);
  const menu = q("[data-ce-v4-project-menu]", runtime.menubar);
  const items = qa("[data-ce-v4-project-option], [data-ce-v4-all-projects]", menu);
  return { trigger, menu, items };
}

function closeProjectMenu(restoreFocus = false) {
  const { trigger, menu } = projectMenuParts();
  if (!trigger || !menu) return;
  const wasOpen = !menu.hidden;
  menu.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  if (restoreFocus && wasOpen) safeFocus(trigger);
}

function openProjectMenu(focusIndex = -1) {
  const { trigger, menu, items } = projectMenuParts();
  if (!trigger || !menu) return;
  closeToolsMenu();
  menu.hidden = false;
  trigger.setAttribute("aria-expanded", "true");
  if (focusIndex >= 0 && items.length) safeFocus(items[Math.min(focusIndex, items.length - 1)]);
}

function toggleProjectMenu() {
  const { menu } = projectMenuParts();
  if (!menu || menu.hidden) openProjectMenu();
  else closeProjectMenu();
}

function handleProjectMenuKeydown(event) {
  const { trigger, menu, items } = projectMenuParts();
  if (!trigger || !menu || !items.length) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target === trigger && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
    event.preventDefault();
    openProjectMenu(event.key === "ArrowUp" ? items.length - 1 : 0);
    return;
  }
  if (menu.hidden) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeProjectMenu(true);
    return;
  }
  if (event.key === "Tab") {
    closeProjectMenu();
    return;
  }
  const current = items.indexOf(target?.closest?.("[data-ce-v4-project-option], [data-ce-v4-all-projects]"));
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? items.length - 1
      : (Math.max(0, current) + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
  safeFocus(items[next]);
}

function projectStageLabel(project) {
  const stage = PROJECT_FLOW.find((item) => item.code === project.currentStage);
  if (stage) return `Сейчас: ${stage.label}`;
  if (project.progress > 0) return `Готово на ${project.progress}%`;
  return project.status ? compact(project.status, 48) : "Открыть рабочую папку";
}

function projectSelectionRoute(project) {
  const nextAction = normalizeProjectNextAction(project?.nextAction, project?.id);
  if (nextAction?.route) return nextAction.route;
  const query = new URLSearchParams({ project_id: project.id });
  if (project.rootFolderId) query.set("folder", project.rootFolderId);
  return `/workspace/board?${query.toString()}`;
}

function syncProjectSwitcher(snapshot = projectFlowSnapshot()) {
  const { trigger, menu } = projectMenuParts();
  if (!trigger || !menu) return;
  const triggerName = q("[data-ce-v4-project-name]", trigger);
  const triggerMeta = q("[data-ce-v4-project-meta]", trigger);
  if (triggerName) triggerName.textContent = snapshot.id ? snapshot.name : "Выбрать проект";
  if (triggerMeta) triggerMeta.textContent = snapshot.id ? "Проект" : "Рабочее пространство";
  trigger.setAttribute("aria-label", snapshot.id ? `Текущий проект: ${snapshot.name}. Выбрать другой` : "Выбрать проект");
  trigger.title = snapshot.id ? `Проект: ${snapshot.name}` : "Выбрать проект";

  const signature = JSON.stringify({
    id: snapshot.id,
    nextAction: snapshot.nextAction?.route || "",
    projects: snapshot.projects.map((project) => [
      project.id,
      project.name,
      project.currentStage,
      project.progress,
      project.status,
      project.nextAction?.route || "",
    ]),
  });
  if (menu.dataset.ceV4ProjectSignature === signature) return;
  const wasOpen = !menu.hidden;
  const records = snapshot.projects.length
    ? snapshot.projects
    : snapshot.id
      ? [{ id: snapshot.id, name: snapshot.name, rootFolderId: snapshot.rootFolderId, currentStage: snapshot.currentStage, progress: 0, status: "" }]
      : [];
  const fragment = document.createDocumentFragment();
  fragment.append(create("span", "ce-v4-project-menu__eyebrow", "ПРОЕКТЫ"));
  records.forEach((project) => {
    const link = create("a", "ce-v4-project-menu__item");
    link.href = `#${projectSelectionRoute(project)}`;
    link.dataset.ceV4ProjectOption = project.id;
    link.dataset.ceV4ProjectName = project.name;
    link.dataset.ceV4ProjectRoot = project.rootFolderId || project.id;
    link.setAttribute("role", "menuitem");
    const mark = create("span", "ce-v4-project-menu__mark");
    mark.append(icon("folder", 17));
    const copy = create("span", "ce-v4-project-menu__copy");
    copy.append(create("strong", "", project.name), create("small", "", projectStageLabel(project)));
    const selected = project.id === snapshot.id;
    link.classList.toggle("is-active", selected);
    if (selected) link.setAttribute("aria-current", "true");
    link.append(mark, copy, create("span", "ce-v4-project-menu__check", selected ? "✓" : ""));
    fragment.append(link);
  });
  const allProjects = create("a", "ce-v4-project-menu__all", "Все проекты");
  allProjects.href = `#${routeWithProject("/workspace/home", snapshot.id)}`;
  allProjects.dataset.ceV4AllProjects = "true";
  allProjects.setAttribute("role", "menuitem");
  fragment.append(allProjects);
  menu.replaceChildren(fragment);
  menu.dataset.ceV4ProjectSignature = signature;
  menu.hidden = !wasOpen;
}

function ensureMenubar() {
  if (runtime.menubar?.isConnected) return runtime.menubar;
  const bar = create("header", "ce-v4-menubar");
  bar.dataset.ceV4Menubar = "true";
  const identity = create("button", "ce-v4-menubar__identity");
  identity.type = "button";
  identity.dataset.ceV4Home = "true";
  identity.append(create("span", "ce-v4-menubar__mark", "КИ"));
  const identityCopy = create("span");
  identityCopy.append(create("strong", "", "ContentEngine"), create("small", "", "рабочая система"));
  identity.append(identityCopy);
  const start = create("div", "ce-v4-menubar__start");
  const traffic = create("span", "ce-v4-traffic");
  traffic.setAttribute("aria-hidden", "true");
  traffic.append(create("i"), create("i"), create("i"));
  const projectSwitcher = create("div", "ce-v4-project-switcher");
  const projectTrigger = create("button", "ce-v4-project-switcher__trigger");
  projectTrigger.type = "button";
  projectTrigger.dataset.ceV4ProjectTrigger = "true";
  projectTrigger.setAttribute("aria-haspopup", "menu");
  projectTrigger.setAttribute("aria-expanded", "false");
  projectTrigger.setAttribute("aria-controls", "ce-v4-project-menu");
  const projectIcon = create("span", "ce-v4-project-switcher__icon");
  projectIcon.append(icon("folder", 16));
  const projectCopy = create("span", "ce-v4-project-switcher__copy");
  const projectMeta = create("small", "", "Рабочее пространство");
  projectMeta.dataset.ceV4ProjectMeta = "true";
  const projectName = create("strong", "", "Выбрать проект");
  projectName.dataset.ceV4ProjectName = "true";
  projectCopy.append(projectMeta, projectName);
  projectTrigger.append(projectIcon, projectCopy, create("span", "ce-v4-project-switcher__chevron", "⌄"));
  const projectMenu = create("nav", "ce-v4-project-menu");
  projectMenu.id = "ce-v4-project-menu";
  projectMenu.dataset.ceV4ProjectMenu = "true";
  projectMenu.hidden = true;
  projectMenu.setAttribute("role", "menu");
  projectMenu.setAttribute("aria-label", "Сменить проект");
  projectSwitcher.append(projectTrigger, projectMenu);
  start.append(traffic, identity, projectSwitcher);

  const globalSearch = create("form", "ce-v4-menubar__search");
  globalSearch.setAttribute("role", "search");
  globalSearch.append(icon("search", 16));
  const globalSearchInput = create("input");
  globalSearchInput.type = "search";
  globalSearchInput.name = "workspace_search";
  globalSearchInput.placeholder = "Найти проект, файл, SKU или задачу";
  globalSearchInput.setAttribute("aria-label", "Найти проект, файл, SKU или задачу");
  globalSearch.append(globalSearchInput, create("kbd", "", "Ctrl K"));
  const actions = create("div", "ce-v4-menubar__actions");
  const refresh = iconButton("", "Обновить текущий раздел", "refresh");
  refresh.dataset.ceV4Refresh = "true";
  const fullscreen = iconButton("", "Перейти в полноэкранный режим", "focus");
  fullscreen.dataset.ceV4Fullscreen = "true";
  fullscreen.setAttribute("aria-pressed", "false");
  const notifications = iconButton("", "Открыть уведомления", "bell");
  notifications.dataset.ceV4Notifications = "/workspace/work?view=notifications";
  notifications.setAttribute("aria-pressed", "false");
  const notificationBadge = create("span", "ce-v4-menubar__notification-badge", "0");
  notificationBadge.dataset.ceV4NotificationBadge = "true";
  notificationBadge.hidden = true;
  notificationBadge.setAttribute("aria-hidden", "true");
  notifications.append(notificationBadge);
  const tools = create("div", "ce-v4-menubar__tools");
  const toolsTrigger = iconButton("ce-v4-menubar__tools-trigger", "Другие разделы", "grid");
  toolsTrigger.dataset.ceV4ToolsTrigger = "true";
  toolsTrigger.setAttribute("aria-haspopup", "menu");
  toolsTrigger.setAttribute("aria-expanded", "false");
  toolsTrigger.setAttribute("aria-controls", "ce-v4-tools-menu");
  const toolsMenu = create("nav", "ce-v4-menubar__tools-menu");
  toolsMenu.id = "ce-v4-tools-menu";
  toolsMenu.dataset.ceV4ToolsMenu = "true";
  toolsMenu.hidden = true;
  toolsMenu.setAttribute("role", "menu");
  toolsMenu.setAttribute("aria-label", "Другие разделы");
  SECONDARY_ROUTES.forEach((item) => {
    if (!routeIsAuthorized(item.route)) return;
    const link = create("a", "ce-v4-menubar__tools-item");
    link.href = `#${item.route}`;
    link.dataset.ceV4ToolsRoute = item.route;
    link.setAttribute("role", "menuitem");
    const tile = create("span", "ce-v4-menubar__tools-icon");
    tile.append(icon(item.icon, 18));
    const copy = create("span", "ce-v4-menubar__tools-copy");
    copy.append(create("strong", "", item.label), create("small", "", item.description));
    link.append(tile, copy);
    toolsMenu.append(link);
  });
  tools.append(toolsTrigger, toolsMenu);
  const clock = create("time", "ce-v4-menubar__clock");
  actions.append(refresh, fullscreen, notifications, tools, clock);
  bar.append(start, globalSearch, actions);
  document.body.append(bar);
  runtime.menubar = bar;
  syncToolsMenu();
  bar.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-home]")) navigate("/workspace/home");
    if (target?.closest("[data-ce-v4-project-trigger]")) toggleProjectMenu();
    const projectOption = target?.closest("[data-ce-v4-project-option]");
    if (projectOption instanceof HTMLAnchorElement) {
      event.preventDefault();
      const selected = {
        id: String(projectOption.dataset.ceV4ProjectOption || ""),
        name: String(projectOption.dataset.ceV4ProjectName || "Проект"),
        rootFolderId: String(projectOption.dataset.ceV4ProjectRoot || projectOption.dataset.ceV4ProjectOption || ""),
      };
      writeJson(storage("session"), PROJECT_CONTEXT_KEY, selected);
      closeProjectMenu();
      navigate(projectOption.getAttribute("href")?.replace(/^#/, "") || projectSelectionRoute(selected));
    }
    if (target?.closest("[data-ce-v4-all-projects]")) closeProjectMenu();
    if (target?.closest("[data-ce-v4-refresh]")) refreshWorkspace();
    if (target?.closest("[data-ce-v4-fullscreen]")) void toggleFullscreen();
    const notificationControl = target?.closest("[data-ce-v4-notifications]");
    if (notificationControl) navigate(notificationControl.dataset.ceV4Notifications);
    if (target?.closest("[data-ce-v4-tools-trigger]")) toggleToolsMenu();
    if (target?.closest("[data-ce-v4-tools-route]")) closeToolsMenu();
  });
  projectSwitcher.addEventListener("keydown", handleProjectMenuKeydown);
  tools.addEventListener("keydown", handleToolsMenuKeydown);
  globalSearch.addEventListener("submit", (event) => {
    event.preventDefault();
    runGlobalSearch(globalSearch);
  });
  if (!runtime.fullscreenListening) {
    document.addEventListener("fullscreenchange", updateFullscreenControl);
    document.addEventListener("webkitfullscreenchange", updateFullscreenControl);
    runtime.fullscreenListening = true;
  }
  updateFullscreenControl();
  updateClock();
  if (!runtime.clockTimer) runtime.clockTimer = window.setInterval(updateClock, 30_000);
  return bar;
}

function updateClock() {
  const clock = q(".ce-v4-menubar__clock", runtime.menubar);
  if (!clock) return;
  const now = new Date();
  clock.dateTime = now.toISOString();
  clock.textContent = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" }).format(now);
}

function syncDockAccess() {
  if (!runtime.dock) return;
  const routeByPath = new Map(ROUTES.map((item) => [item.route, item]));
  const shortcutIndexByRoute = new Map(
    authorizedRoutes(ROUTES).map((item, index) => [item.route, index]),
  );
  qa("[data-ce-v4-route]", runtime.dock).forEach((link) => {
    const route = String(link.dataset.ceV4Route || "");
    const item = routeByPath.get(route);
    const authorized = Boolean(item && shortcutIndexByRoute.has(route));
    link.hidden = !authorized;
    if (!authorized) {
      link.setAttribute("aria-hidden", "true");
      link.removeAttribute("aria-current");
      return;
    }
    link.removeAttribute("aria-hidden");
    const shortcut = `⌥${shortcutIndexByRoute.get(route) + 1}`;
    link.setAttribute("aria-label", `${item.label}. ${item.description}. ${shortcut}`);
    const tooltip = q(".ce-v4-dock__tooltip", link);
    if (tooltip) tooltip.textContent = `${item.label} · ${item.description} · ${shortcut}`;
  });
}

function ensureDock() {
  if (runtime.dock?.isConnected) {
    syncDockAccess();
    return runtime.dock;
  }
  const dock = create("nav", "ce-v4-dock");
  dock.setAttribute("aria-label", "Основные разделы ContentEngine");
  const glass = create("div", "ce-v4-dock__glass");
  ROUTES.forEach((item, index) => {
    const link = create("a", "ce-v4-dock__item");
    const shortcut = `⌥${Math.min(index + 1, 9)}`;
    link.href = `#${item.route}`;
    link.dataset.ceV4Route = item.route;
    link.setAttribute("aria-label", `${item.label}. ${item.description}. ${shortcut}`);
    link.title = `${item.label} — ${item.description}`;
    link.append(create("span", "ce-v4-dock__tooltip", `${item.label} · ${item.description} · ${shortcut}`));
    const tile = create("span", "ce-v4-dock__tile");
    const count = create("span", "ce-v4-dock__count", "0");
    count.dataset.ceV4DockCount = "true";
    count.hidden = true;
    count.setAttribute("aria-hidden", "true");
    tile.append(icon(item.icon, 22), count);
    link.append(tile, create("span", "ce-v4-dock__label", item.label), create("i"));
    glass.append(link);
  });
  const separator = create("span", "ce-v4-dock__separator ce-v4-trash-separator");
  const trash = create("button", "ce-v4-dock__item ce-v4-dock__utility ce-v4-trash-dock");
  trash.type = "button";
  trash.setAttribute("aria-label", "Корзина");
  trash.title = "Корзина — удалённые файлы и папки";
  trash.append(create("span", "ce-v4-dock__tooltip", "Корзина · удалённые файлы и папки"));
  const trashTile = create("span", "ce-v4-dock__tile");
  trashTile.append(icon("trash", 22));
  trash.append(trashTile, create("span", "ce-v4-dock__label", "Корзина"), create("i"));
  glass.append(separator, trash);
  dock.append(glass);
  document.body.append(dock);
  dock.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const item = target?.closest(".ce-v4-dock__item");
    if (!(item instanceof HTMLElement)) return;
    const destination = String(item.dataset.ceV4Route || "");
    const snapshot = projectFlowSnapshot();
    const stage = stageForRoute(destination, snapshot);
    if (stageLocked(stage, snapshot)) {
      event.preventDefault();
      explainLockedStage(stage);
      return;
    }
    if (!destination || routeMatches(routePath(), destination)) return;
    item.classList.remove("is-launching");
    window.requestAnimationFrame(() => {
      if (!item.isConnected) return;
      item.classList.add("is-launching");
      window.setTimeout(() => item.classList.remove("is-launching"), 420);
    });
  });
  runtime.dock = dock;
  syncDockAccess();
  return dock;
}

function updateDock() {
  const route = routePath();
  const snapshot = projectFlowSnapshot();
  const context = projectContext(snapshot);
  const shortcutIndexByRoute = new Map(
    authorizedRoutes(ROUTES).map((item, index) => [item.route, index]),
  );
  const focusedStageIndex = activeProjectFlowIndex(route, snapshot);
  const dockRoute = route === "/workspace/tasks"
    ? (focusedStageIndex >= 0 ? PROJECT_FLOW[focusedStageIndex].route : "/workspace/home")
    : route;
  let activeItem = null;
  qa("[data-ce-v4-route]", runtime.dock).forEach((item, index) => {
    if (item.hidden) {
      item.classList.remove("is-active");
      item.removeAttribute("aria-current");
      return;
    }
    const active = routeMatches(dockRoute, item.dataset.ceV4Route);
    const record = ROUTES[index];
    const stage = stageForRoute(item.dataset.ceV4Route, snapshot);
    const hasStageState = Boolean(snapshot.hasFlow && stage && stage.state !== "unknown");
    const locked = stageLocked(stage, snapshot);
    const destination = stage?.destination || projectRoute(item.dataset.ceV4Route, context);
    item.href = `#${destination}`;
    item.classList.toggle("is-active", active);
    ["done", "current", "blocked", "future"].forEach((state) => {
      item.classList.toggle(`is-stage-${state}`, hasStageState && stage.state === state);
    });
    item.dataset.ceV4StageState = hasStageState ? stage.state : "unknown";
    item.setAttribute("aria-current", active ? "page" : "false");
    if (locked) item.setAttribute("aria-disabled", "true");
    else item.removeAttribute("aria-disabled");
    const count = q("[data-ce-v4-dock-count]", item);
    const showCount = Boolean(stage && Number.isFinite(stage.count) && stage.count > 0);
    if (count) {
      count.hidden = !showCount;
      count.textContent = showCount ? (stage.count > 99 ? "99+" : String(stage.count)) : "0";
    }
    const stateText = hasStageState ? PROJECT_STAGE_STATE_LABELS[stage.state] : "";
    const countText = stage && Number.isFinite(stage.count) ? `${stage.count} ${stage.countLabel}` : "";
    const reasonText = locked && stage.reason ? stage.reason : "";
    const shortcutIndex = shortcutIndexByRoute.get(item.dataset.ceV4Route);
    const shortcut = Number.isInteger(shortcutIndex) ? `⌥${shortcutIndex + 1}` : "";
    const semantic = [record?.label, stateText, countText, reasonText, record?.description, shortcut].filter(Boolean).join(" · ");
    const tooltip = q(".ce-v4-dock__tooltip", item);
    if (tooltip) tooltip.textContent = semantic;
    item.title = semantic;
    item.setAttribute("aria-label", semantic);
    if (active) activeItem = item;
  });
  const glass = q(".ce-v4-dock__glass", runtime.dock);
  if (activeItem && glass && window.innerWidth <= 900) {
    window.requestAnimationFrame(() => {
      const left = activeItem.offsetLeft - (glass.clientWidth - activeItem.offsetWidth) / 2;
      glass.scrollTo({
        left: Math.max(0, left),
        behavior: REDUCED_MOTION.matches ? "auto" : "smooth",
      });
    });
  }
}

function updateMenubar() {
  const snapshot = projectFlowSnapshot();
  syncProjectSwitcher(snapshot);
  syncToolsMenu();
  qa("[data-ce-v4-tools-route]", runtime.menubar).forEach((link) => {
    const active = routePath() === link.dataset.ceV4ToolsRoute;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const notifications = q("[data-ce-v4-notifications]", runtime.menubar);
  if (notifications) {
    const active = routePath() === "/workspace/work" && routeQuery().get("view") === "notifications";
    const destination = routeWithProject("/workspace/work?view=notifications", snapshot.id);
    notifications.dataset.ceV4Notifications = destination;
    notifications.classList.toggle("is-active", active);
    notifications.setAttribute("aria-pressed", String(active));
    const badge = q("[data-ce-v4-notification-badge]", notifications);
    if (badge) {
      badge.hidden = snapshot.unread < 1;
      badge.textContent = snapshot.unread > 99 ? "99+" : String(snapshot.unread);
    }
    const label = snapshot.unread > 0
      ? `Уведомления: ${snapshot.unread} непрочитанных`
      : "Уведомления: новых нет";
    notifications.setAttribute("aria-label", label);
    notifications.title = label;
  }
}

function mountHome() {
  if (routePath() !== "/workspace/home") return;
  const page = currentPage();
  if (!page) return;
  q(":scope > .ce-v4-home", page)?.remove();
  page.classList.add("ce-v4-home-page", "ce-v4-project-home");
  const projects = q("[data-ce-v4-project-home]", page);
  if (projects) projects.dataset.ceV4Surface = "true";
}

function storedProjectContext() {
  const value = readJson(storage("session"), PROJECT_CONTEXT_KEY, null);
  if (!value || typeof value !== "object" || !String(value.id || "").trim()) return null;
  return {
    id: String(value.id).trim(),
    name: compact(value.name || "Проект", 80),
    rootFolderId: String(value.rootFolderId || value.root_folder_id || value.id || "").trim(),
  };
}

function projectFlowRoot() {
  return q("[data-project-flow-root]") || q(".workspace-shell[data-workspace-section]");
}

function embeddedProjectFlow() {
  const script = q("#workspace-project-flow-snapshot");
  if (!script) return {};
  try {
    const value = JSON.parse(String(script.textContent || "{}"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function normalizeProjectRecord(value) {
  if (!value || typeof value !== "object") return null;
  const id = String(value.id || value.project_id || value.folder_id || "").trim();
  if (!id) return null;
  return {
    id,
    name: compact(value.name || value.project_name || value.title || "Проект", 80),
    rootFolderId: String(value.root_folder_id || value.folder_id || id).trim(),
    status: compact(value.status || "", 40),
    currentStage: normalizeStageCode(value.current_stage || value.stage || ""),
    progress: Math.max(0, Math.min(100, Number(value.progress_percent) || 0)),
    updatedAt: String(value.updated_at || ""),
    nextAction: value.next_action && typeof value.next_action === "object" ? value.next_action : null,
  };
}

function normalizeStageCode(value) {
  const raw = String(value || "").trim().toLocaleLowerCase("ru-RU");
  if (!raw) return "";
  if (raw.startsWith("/workspace/")) {
    return PROJECT_FLOW.find((item) => routeMatches(raw.split("?")[0], item.route))?.code || "";
  }
  return PROJECT_STAGE_ALIASES[raw] || raw;
}

function normalizeStageState(value) {
  const state = String(value || "").trim().toLocaleLowerCase("ru-RU");
  if (["done", "complete", "completed", "success", "published"].includes(state)) return "done";
  if (["current", "active", "in_progress", "ready", "working"].includes(state)) return "current";
  if (["blocked", "error", "needs_attention", "needs_help"].includes(state)) return "blocked";
  if (["future", "too_early", "pending", "locked", "upcoming"].includes(state)) return "future";
  return "unknown";
}

function stageCount(rawStage, counts, item) {
  const candidates = [
    rawStage?.count,
    rawStage?.items_count,
    counts?.[item.code],
    item.code === "files" ? counts?.files : undefined,
    item.code === "generation" ? counts?.generation_jobs : undefined,
    item.code === "review" ? counts?.reviews : undefined,
    item.code === "placement" ? counts?.placements : undefined,
    item.code === "stats" ? counts?.metric_snapshots : undefined,
  ];
  const found = candidates.find((candidate) => Number.isFinite(Number(candidate)));
  return found === undefined ? null : Math.max(0, Math.trunc(Number(found)));
}

function normalizeProjectNextAction(value, projectId) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const normalizedProjectId = String(projectId || "").trim().toLowerCase();
  const payloadProjectId = String(value.project_id || value.projectId || "").trim().toLowerCase();
  const stage = normalizeStageCode(value.stage || "");
  const route = String(value.route || "").trim();
  const { path, query } = routeParts(route);
  const routeProjectId = String(query.get("project_id") || "").trim().toLowerCase();
  const entityId = String(value.entity_id || value.entityId || "").trim().toLowerCase();
  if (
    !PROJECT_ID_PATTERN.test(normalizedProjectId)
    || !PROJECT_FLOW.some((item) => item.code === stage)
    || !NEXT_ACTION_PATHS.has(path)
    || (payloadProjectId && payloadProjectId !== normalizedProjectId)
    || (routeProjectId && routeProjectId !== normalizedProjectId)
    || (entityId && !PROJECT_ID_PATTERN.test(entityId))
  ) return null;
  const destination = routeWithProject(route, normalizedProjectId);
  if (!isWorkspaceActionKey(workspaceActionKey(destination))) return null;
  return {
    ...value,
    stage,
    route: destination,
    project_id: normalizedProjectId,
    entity_id: entityId,
  };
}

function projectFlowSnapshot() {
  const root = projectFlowRoot();
  const raw = embeddedProjectFlow();
  const rawNextAction = raw.next_action && typeof raw.next_action === "object" ? raw.next_action : null;
  const rawProjects = Array.isArray(raw.projects) ? raw.projects : [];
  const projects = rawProjects.map(normalizeProjectRecord).filter(Boolean);
  const rawProject = normalizeProjectRecord(raw.project);
  if (rawProject && !projects.some((item) => item.id === rawProject.id)) projects.unshift(rawProject);

  const stored = storedProjectContext();
  const queryProjectId = String(routeQuery().get("project_id") || "").trim();
  const rootProjectId = String(root?.dataset.projectId || root?.dataset.workspaceProjectId || "").trim();
  const rawProjectId = String(raw.project_id || rawProject?.id || "").trim();
  const id = queryProjectId || rootProjectId || rawProjectId || stored?.id || "";
  const nextAction = normalizeProjectNextAction(rawNextAction, id);
  const catalogProject = projects.find((item) => item.id === id) || null;
  const rootProjectName = rootProjectId === id ? root?.dataset.projectName : "";
  const storedProjectName = stored?.id === id ? stored.name : "";
  const name = compact(catalogProject?.name || rootProjectName || rawProject?.name || storedProjectName || "Проект", 80);
  const rootFolderId = String(catalogProject?.rootFolderId || rawProject?.rootFolderId || stored?.rootFolderId || id || "").trim();
  const currentStage = normalizeStageCode(
    root?.dataset.projectCurrentStage || root?.dataset.currentStage || raw.current_stage || rawProject?.currentStage || "",
  );
  const counts = raw.counts && typeof raw.counts === "object" ? raw.counts : {};
  const rawStages = Array.isArray(raw.stages) ? raw.stages : [];
  const stages = PROJECT_FLOW.map((item) => {
    const match = rawStages.find((candidate) => {
      const code = normalizeStageCode(candidate?.code || candidate?.stage || candidate?.route || "");
      return code === item.code;
    });
    const state = match
      ? normalizeStageState(match.state || match.status)
      : currentStage === item.code
        ? "current"
        : "unknown";
    return {
      ...item,
      state,
      count: stageCount(match, counts, item),
      reason: compact(match?.reason || match?.reason_text || "", 180),
      reasonCode: String(match?.reason_code || ""),
      canonicalRoute: routeWithProject(item.route, id),
      destination: routeWithProject(
        nextAction?.stage === item.code && nextAction?.route
          ? nextAction.route
          : match?.route || item.route,
        id,
      ),
      entityType: String(
        nextAction?.stage === item.code
          ? nextAction?.entity_type || match?.entity_type || ""
          : match?.entity_type || "",
      ),
      entityId: String(
        nextAction?.stage === item.code
          ? nextAction?.entity_id || match?.entity_id || ""
          : match?.entity_id || "",
      ),
    };
  });
  const unreadCandidate = root?.dataset.projectUnreadCount
    ?? root?.dataset.unreadCount
    ?? root?.dataset.workspaceUnreadCount
    ?? raw.unread_count
    ?? counts.unread
    ?? counts.notifications_unread;
  const unread = Number.isFinite(Number(unreadCandidate)) ? Math.max(0, Math.trunc(Number(unreadCandidate))) : 0;
  return {
    id,
    name,
    rootFolderId,
    projects,
    stages,
    unread,
    hasFlow: rawStages.length > 0 || Boolean(currentStage),
    currentStage,
    nextAction,
  };
}

function projectContext(snapshot = projectFlowSnapshot()) {
  if (!snapshot?.id) return null;
  return {
    id: snapshot.id,
    name: snapshot.name,
    rootFolderId: snapshot.rootFolderId || snapshot.id,
  };
}

function projectRoute(route, context = projectContext()) {
  return routeWithProject(route, context?.id || "");
}

function stageForRoute(route, snapshot = projectFlowSnapshot()) {
  const path = routeParts(route).path;
  return snapshot.stages.find((stage) => routeMatches(path, routeParts(stage.canonicalRoute).path)) || null;
}

function activeProjectFlowIndex(route = routePath(), snapshot = projectFlowSnapshot()) {
  const exactStage = normalizeStageCode(snapshot.nextAction?.stage);
  if (
    exactStage
    && workspaceActionKey() === workspaceActionKey(snapshot.nextAction.route)
  ) {
    const exact = PROJECT_FLOW.findIndex((item) => item.code === exactStage);
    if (exact >= 0) return exact;
  }
  const direct = PROJECT_FLOW.findIndex((item) => routeMatches(route, item.route));
  if (direct >= 0) return direct;
  if (route !== "/workspace/tasks") return -1;

  const requestedStage = normalizeStageCode(routeQuery().get("stage") || routeQuery().get("origin_stage"));
  const requested = PROJECT_FLOW.findIndex((item) => item.code === requestedStage);
  if (requested >= 0) return requested;

  const current = snapshot.stages.findIndex((stage) => stage.state === "current");
  if (current >= 0) return current;
  return PROJECT_FLOW.findIndex((item) => item.code === snapshot.currentStage);
}

function stageLocked(stage, snapshot = projectFlowSnapshot()) {
  if (!snapshot.hasFlow || !stage || !["blocked", "future"].includes(stage.state)) return false;
  const recovery = snapshot.nextAction;
  const exactRecovery = stage.state === "blocked"
    && normalizeStageCode(recovery?.stage) === stage.code
    && Boolean(String(recovery?.route || "").trim());
  return !exactRecovery;
}

function explainLockedStage(stage) {
  const fallback = stage?.state === "blocked"
    ? "Этот этап заблокирован. Устраните причину или обратитесь к ответственному."
    : "Сначала завершите текущий этап проекта.";
  showSystemToast(stage?.reason || fallback, stage?.state === "blocked" ? "error" : "warning");
}

function syncProjectProgress() {
  const route = routePath();
  const snapshot = projectFlowSnapshot();
  const activeIndex = activeProjectFlowIndex(route, snapshot);
  const context = projectContext(snapshot);
  const page = currentPage();
  if (!page) return;
  qa("[data-ce-v4-project-progress]").forEach((node) => {
    if (!page.contains(node)) node.remove();
  });
  let progress = q(":scope > [data-ce-v4-project-progress]", page);
  if (!context || activeIndex < 0) {
    progress?.remove();
    return;
  }
  if (!progress || progress.dataset.ceV4ProjectProgress !== context.id) {
    progress?.remove();
    progress = create("nav", "ce-v4-project-progress");
    progress.dataset.ceV4ProjectProgress = context.id;
    const heading = create("div", "ce-v4-project-progress__project");
    heading.append(create("small", "", "ПРОЕКТ"), create("strong", "", context.name));
    const list = create("ol", "ce-v4-project-progress__steps");
    PROJECT_FLOW.forEach((item, index) => {
      const entry = create("li");
      const link = create("a");
      link.href = `#${projectRoute(item.route, context)}`;
      link.dataset.ceV4ProjectStage = item.route;
      link.title = `${index + 1}. ${item.label}`;
      const marker = create("span", "ce-v4-project-progress__marker");
      const copy = create("span", "ce-v4-project-progress__copy");
      copy.append(create("strong", "", item.label), create("small", "", "Статус уточняется"));
      link.append(marker, copy);
      entry.append(link);
      list.append(entry);
    });
    progress.append(heading, list);
    progress.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target.closest("[data-ce-v4-project-stage]") : null;
      if (!(target instanceof HTMLAnchorElement)) return;
      const currentSnapshot = projectFlowSnapshot();
      const stage = stageForRoute(target.dataset.ceV4ProjectStage, currentSnapshot);
      if (!stageLocked(stage, currentSnapshot)) return;
      event.preventDefault();
      explainLockedStage(stage);
    });
    page.prepend(progress);
  }
  progress.setAttribute("aria-label", `Этапы проекта ${context.name}`);
  q(".ce-v4-project-progress__project strong", progress).textContent = context.name;
  qa("[data-ce-v4-project-stage]", progress).forEach((link, index) => {
    const stage = snapshot.stages[index];
    const state = snapshot.hasFlow ? stage?.state || "unknown" : "unknown";
    const current = state === "current";
    const complete = state === "done";
    const locked = stageLocked(stage, snapshot);
    link.href = `#${stage?.destination || projectRoute(PROJECT_FLOW[index].route, context)}`;
    link.dataset.ceV4StageState = state;
    link.classList.toggle("is-viewing", index === activeIndex);
    link.classList.toggle("is-current", current);
    link.classList.toggle("is-complete", complete);
    link.classList.toggle("is-blocked", state === "blocked");
    link.classList.toggle("is-future", state === "future");
    if (current) link.setAttribute("aria-current", "step");
    else link.removeAttribute("aria-current");
    if (locked) link.setAttribute("aria-disabled", "true");
    else link.removeAttribute("aria-disabled");
    const marker = q(".ce-v4-project-progress__marker", link);
    if (marker) marker.textContent = complete ? "✓" : state === "blocked" ? "!" : String(index + 1);
    const status = PROJECT_STAGE_STATE_LABELS[state] || PROJECT_STAGE_STATE_LABELS.unknown;
    const count = stage && Number.isFinite(stage.count) ? ` · ${stage.count} ${stage.countLabel}` : "";
    const helper = q(".ce-v4-project-progress__copy small", link);
    if (helper) helper.textContent = `${status}${count}`;
    const reason = locked && stage?.reason ? ` · ${stage.reason}` : "";
    const title = `${index + 1}. ${PROJECT_FLOW[index].label} · ${status}${count}${reason}`;
    link.title = title;
    link.setAttribute("aria-label", title);
  });
}

function overlayBase(className, label) {
  const backdrop = create("div", `${className}-backdrop`);
  const dialog = create("section", className);
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", label);
  backdrop.append(dialog);
  return { backdrop, dialog };
}

function closeElementOverlay(name, immediate = false) {
  const overlay = runtime[name];
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    runtime[name] = null;
    document.body.classList.remove(`ce-v4-${name}-open`);
  };
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function closeTransientOverlays(immediate = false) {
  closeProjectMenu();
  closeToolsMenu();
  if (runtime.mission) closeElementOverlay("mission", immediate);
  if (runtime.spotlight) closeElementOverlay("spotlight", immediate);
  if (runtime.zen) closeZen(immediate);
}

function openMission() {
  if (runtime.mission) return;
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  const { backdrop, dialog } = overlayBase("ce-v4-mission", "Рабочие столы");
  const header = create("header", "ce-v4-overlay-header");
  const copy = create("div");
  copy.append(create("small", "ce-v4-eyebrow", "MISSION CONTROL"), create("h1", "", "Рабочие столы"), create("p", "", "Выберите одно направление. Контекст текущего стола сохранится."));
  const close = iconButton("", "Закрыть", "close");
  close.dataset.ceV4Close = "true";
  header.append(copy, close);
  const search = create("label", "ce-v4-mission__search");
  search.append(icon("search", 18));
  const input = create("input");
  input.type = "search";
  input.placeholder = "Найти рабочий стол";
  input.setAttribute("aria-label", "Найти рабочий стол");
  search.append(input);
  const grid = create("div", "ce-v4-mission__grid");
  authorizedRoutes(ROUTES).forEach((item, index) => {
    const button = create("button", "ce-v4-mission-card");
    button.type = "button";
    button.dataset.route = item.route;
    button.dataset.search = `${item.label} ${item.description}`.toLocaleLowerCase("ru-RU");
    button.append(create("span", "ce-v4-mission-card__number", String(index + 1).padStart(2, "0")));
    const cardCopy = create("span");
    const tile = create("span", "ce-v4-mission-card__icon");
    tile.append(icon(item.icon, 22));
    cardCopy.append(tile, create("strong", "", item.label), create("small", "", item.description));
    button.append(cardCopy, icon("right", 18));
    grid.append(button);
  });
  dialog.append(header, search, grid);
  document.body.append(backdrop);
  runtime.mission = backdrop;
  document.body.classList.add("ce-v4-mission-open");
  backdrop.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (event.target === backdrop || target?.closest("[data-ce-v4-close]")) closeElementOverlay("mission");
    const route = target?.closest("[data-route]")?.dataset.route;
    if (route) navigate(route);
  });
  input.addEventListener("input", () => {
    const needle = input.value.trim().toLocaleLowerCase("ru-RU");
    qa("[data-search]", grid).forEach((card) => { card.hidden = Boolean(needle && !card.dataset.search.includes(needle)); });
  });
  backdrop.addEventListener("keydown", (event) => { if (event.key === "Escape") closeElementOverlay("mission"); });
  safeFocus(input);
  animate(dialog, [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "translateY(0)" }], 200);
}

function spotlightRecords(query = "") {
  const records = authorizedRoutes(ALL_ROUTES).map((item) => ({
    title: item.label,
    subtitle: item.description,
    icon: item.icon,
    keywords: `${item.label} ${item.description}`.toLocaleLowerCase("ru-RU"),
    run: () => navigate(item.route),
  }));
  qa(".workspace-board__item, .task-card, .my-work-item, .placement-card, [data-generation-job-id]").filter(isVisible).slice(0, 80).forEach((node) => {
    const title = compact(q("h2, h3, strong", node)?.textContent || node.textContent, 100);
    if (!title) return;
    records.push({
      title,
      subtitle: routeRecord().label,
      icon: "work",
      keywords: `${title} ${node.textContent}`.toLocaleLowerCase("ru-RU"),
      run: () => { node.scrollIntoView({ block: "center", behavior: REDUCED_MOTION.matches ? "auto" : "smooth" }); safeFocus(q("button, a, input, [tabindex]", node)); },
    });
  });
  const needle = query.trim().toLocaleLowerCase("ru-RU");
  if (needle) {
    records.push({
      title: `Найти «${compact(query, 70)}» в Finder`,
      subtitle: "Серверный поиск по папкам, материалам и задачам",
      icon: "search",
      keywords: needle,
      run: () => { storage("session")?.setItem(FINDER_QUERY_KEY, query.trim()); navigate("/workspace/board"); },
    });
  }
  return needle ? records.filter((item) => item.keywords.includes(needle) || item.title.toLocaleLowerCase("ru-RU").includes(needle)) : records;
}

function renderSpotlight(dialog, query = "") {
  const list = q(".ce-v4-spotlight__list", dialog);
  runtime.spotlightRecords = spotlightRecords(query).slice(0, 40);
  runtime.spotlightIndex = Math.min(runtime.spotlightIndex, Math.max(0, runtime.spotlightRecords.length - 1));
  list.replaceChildren();
  runtime.spotlightRecords.forEach((record, index) => {
    const button = create("button", `ce-v4-spotlight-result${index === runtime.spotlightIndex ? " is-active" : ""}`);
    button.type = "button";
    button.dataset.index = String(index);
    const tile = create("span", "ce-v4-spotlight-result__icon");
    tile.append(icon(record.icon, 18));
    const copy = create("span");
    copy.append(create("strong", "", record.title), create("small", "", record.subtitle));
    button.append(tile, copy, create("kbd", "", "↵"));
    list.append(button);
  });
  if (!runtime.spotlightRecords.length) list.append(create("p", "ce-v4-empty", "Ничего не найдено. Попробуйте артикул, товар, задачу или раздел."));
}

function runSpotlight(index = runtime.spotlightIndex) {
  const record = runtime.spotlightRecords[index];
  if (!record) return;
  closeElementOverlay("spotlight", true);
  record.run();
}

function openSpotlight() {
  if (runtime.spotlight) return;
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  const { backdrop, dialog } = overlayBase("ce-v4-spotlight", "Spotlight");
  const search = create("label", "ce-v4-spotlight__search");
  search.append(icon("search", 21));
  const input = create("input");
  input.type = "search";
  input.placeholder = "Стол, товар, артикул, задача или команда";
  input.setAttribute("aria-label", "Spotlight");
  search.append(input, create("kbd", "", "⌘K"));
  const list = create("div", "ce-v4-spotlight__list");
  dialog.append(search, list);
  document.body.append(backdrop);
  runtime.spotlight = backdrop;
  document.body.classList.add("ce-v4-spotlight-open");
  renderSpotlight(dialog);
  input.addEventListener("input", () => { runtime.spotlightIndex = 0; renderSpotlight(dialog, input.value); });
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) closeElementOverlay("spotlight");
    const button = event.target instanceof Element ? event.target.closest("[data-index]") : null;
    if (button) runSpotlight(Number(button.dataset.index));
  });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key === "Escape") return closeElementOverlay("spotlight");
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const total = runtime.spotlightRecords.length;
      if (!total) return;
      runtime.spotlightIndex = (runtime.spotlightIndex + (event.key === "ArrowDown" ? 1 : -1) + total) % total;
      renderSpotlight(dialog, input.value);
      q(`[data-index='${runtime.spotlightIndex}']`, dialog)?.scrollIntoView({ block: "nearest" });
    }
    if (event.key === "Enter") { event.preventDefault(); runSpotlight(); }
  });
  safeFocus(input);
  animate(dialog, [{ opacity: 0, transform: "translateY(-8px)" }, { opacity: 1, transform: "translateY(0)" }], 180);
}

function zenSurface() {
  return qa(
    ".review-desktop-os, .generation-os-shell, .media-finder-shell, .work-stage-shell, .tasks-desk-shell, "
      + ".publishing-os-shell, .results-ledger-shell, .workspace-board, .page-wrap",
  ).filter(isVisible).at(-1) || currentPage();
}

function openZen() {
  if (runtime.zen) return;
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  const surface = zenSurface();
  if (!surface || surface === document.body || surface === document.documentElement) return;
  const placeholder = document.createComment("contentengine-v4-zen-placeholder");
  surface.before(placeholder);
  const { backdrop, dialog } = overlayBase("ce-v4-zen", `Фокус: ${routeRecord().label}`);
  const header = create("header", "ce-v4-zen__header");
  const copy = create("div");
  copy.append(create("small", "ce-v4-eyebrow", "ФОКУС"), create("strong", "", routeRecord().label));
  const close = iconButton("", "Закрыть фокус", "close");
  close.dataset.ceV4ZenClose = "true";
  header.append(copy, close);
  const body = create("div", "ce-v4-zen__body");
  body.append(surface);
  dialog.append(header, body);
  document.body.append(backdrop);
  runtime.zen = { backdrop, surface, placeholder };
  document.body.classList.add("ce-v4-zen-open");
  backdrop.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-zen-close]")) closeZen();
  });
  backdrop.addEventListener("keydown", (event) => { if (event.key === "Escape") closeZen(); });
  safeFocus(close);
  animate(dialog, [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "translateY(0)" }], 200);
}

function closeZen(immediate = false) {
  const record = runtime.zen;
  if (!record) return;
  record.backdrop.classList.add("is-closing");
  const finish = () => {
    if (record.placeholder.parentNode) record.placeholder.before(record.surface);
    record.placeholder.remove();
    record.backdrop.remove();
    runtime.zen = null;
    document.body.classList.remove("ce-v4-zen-open");
  };
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 190);
}

function toggleZen() {
  if (runtime.zen) closeZen();
  else openZen();
}

function scrollContainers(page = currentPage()) {
  const main = q("#main-content");
  return [main, ...qa(
    ".workspace-board__content, .workspace-board__sidebar, [data-ce-v4-scroll]",
    page,
  )].filter((node, index, nodes) => node && nodes.indexOf(node) === index && isVisible(node)).slice(0, 12);
}

function syncSingleRouteScroll(page = currentPage()) {
  if (!page) return;
  const expandingSurfaces = qa(
    ".review-os-workbench, .generation-os-workbench, .work-stage-shell, .tasks-desk-shell, "
      + ".publishing-os-shell, .results-ledger-shell",
    page,
  );
  expandingSurfaces.forEach((node) => {
    node.dataset.ceV4PageScroll = "true";
    node.style.setProperty("height", "auto", "important");
    node.style.setProperty("min-height", "100%", "important");
    node.style.setProperty("max-height", "none", "important");
    node.style.setProperty("overflow-y", "visible", "important");
  });
  qa(
    ".ce-v4-generation-guided__panel-content, .ce-v4-review-risk-group__body, "
      + ".tasks-desk-list, .tasks-desk-main, .tasks-desk-stage, .publishing-os-list, "
      + ".publishing-os-panels, .publishing-os-step-panel, .results-ledger-panels, "
      + ".results-ledger-panel",
    page,
  ).forEach((node) => {
    node.dataset.ceV4PageScroll = "true";
    node.style.setProperty("height", "auto", "important");
    node.style.setProperty("max-height", "none", "important");
    node.style.setProperty("overflow", "visible", "important");
    node.style.setProperty("overscroll-behavior", "auto", "important");
    node.style.setProperty("scrollbar-gutter", "auto", "important");
  });
  qa(".results-ledger-panel .table-wrap", page).forEach((node) => {
    node.dataset.ceV4PageScroll = "horizontal";
    node.style.setProperty("height", "auto", "important");
    node.style.setProperty("max-height", "none", "important");
    node.style.setProperty("overflow-x", "auto", "important");
    node.style.setProperty("overflow-y", "hidden", "important");
  });
}

function scrollKey(node, index) {
  return (node.dataset.ceV4ScrollKey || node.id || [...node.classList].slice(0, 2).join(".") || `scroll-${index}`).slice(0, 120);
}

function captureScroll(route = runtime.route, actionKey = runtime.actionKey) {
  if (!isWorkspaceRoute(route) || !isWorkspaceActionKey(actionKey)) return;
  const nested = {};
  scrollContainers().forEach((node, index) => { nested[scrollKey(node, index)] = { top: Math.round(node.scrollTop || 0), left: Math.round(node.scrollLeft || 0) }; });
  const states = { ...(runtime.state.scroll || {}) };
  states[actionKey] = { windowY: Math.round(window.scrollY || 0), nested, at: Date.now() };
  remember({ scroll: states });
}

function captureCurrentAction(expectedActionKey = runtime.actionKey) {
  const expected = String(expectedActionKey || "");
  if (!expected || expected !== runtime.actionKey) return false;
  window.clearTimeout(runtime.scrollTimer);
  captureScroll(runtime.route, runtime.actionKey);
  runtime.preNavigationActionKey = runtime.actionKey;
  return true;
}

function resetActionScroll(input = window.location.hash) {
  const actionKey = workspaceActionKey(input);
  if (!isWorkspaceActionKey(actionKey)) return false;
  window.clearTimeout(runtime.scrollTimer);
  const states = { ...(runtime.state.scroll || {}) };
  delete states[actionKey];
  remember({ scroll: states });
  runtime.pendingActionReset = actionKey;
  runtime.restoredRoute = "";
  runtime.restoredScrollNodes = new WeakSet();
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  scrollContainers().forEach((node) => {
    node.scrollTop = 0;
    node.scrollLeft = 0;
  });
  const main = q("#main-content");
  if (main?.dataset.ceV4ActionEntry === actionKey) {
    delete main.dataset.ceV4ActionEntry;
  }
  const shell = q(".workspace-shell[data-workspace-section]");
  if (shell?.dataset.workspaceActionKey === actionKey) {
    shell.dataset.workspaceActionKey = "";
  }
  return true;
}

function restoreScroll(actionKey = workspaceActionKey()) {
  const main = q("#main-content");
  const appAlreadyReset = main?.dataset?.ceV4ActionEntry === actionKey;
  const pendingReset = runtime.pendingActionReset === actionKey;
  const saved = pendingReset ? null : runtime.state.scroll?.[actionKey];

  if (pendingReset && appAlreadyReset) {
    runtime.restoredRoute = actionKey;
    runtime.restoredScrollNodes = new WeakSet(scrollContainers());
    runtime.pendingActionReset = "";
    return;
  }

  if (runtime.restoredRoute !== actionKey) {
    runtime.restoredRoute = actionKey;
    runtime.restoredScrollNodes = new WeakSet();
    window.scrollTo({ top: Math.max(0, Number(saved?.windowY) || 0), behavior: "auto" });
  }
  scrollContainers().forEach((node, index) => {
    if (runtime.restoredScrollNodes.has(node)) return;
    const point = saved?.nested?.[scrollKey(node, index)];
    node.scrollTop = Math.max(0, Number(point?.top) || 0);
    node.scrollLeft = Math.max(0, Number(point?.left) || 0);
    runtime.restoredScrollNodes.add(node);
  });
  if (runtime.pendingActionReset === actionKey) runtime.pendingActionReset = "";
}

function governVideo(video) {
  if (!(video instanceof HTMLVideoElement)) return;
  video.autoplay = false;
  video.loop = false;
  video.removeAttribute("autoplay");
  video.removeAttribute("loop");
  if (!video.preload || video.preload === "auto") video.preload = "metadata";
  if (runtime.observedVideos.has(video)) return;
  runtime.observedVideos.add(video);
  video.addEventListener("play", () => qa("video").forEach((other) => { if (other !== video && !other.paused) other.pause(); }));
  runtime.videoObserver?.observe(video);
}

function setupVideoGovernor() {
  if (!runtime.videoObserver && typeof IntersectionObserver === "function") {
    runtime.videoObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting && entry.target instanceof HTMLVideoElement && !entry.target.paused) entry.target.pause();
    }), { rootMargin: "180px", threshold: 0.01 });
  }
  qa("video").forEach(governVideo);
}

function cleanLegacyChrome() {
  document.body.classList.remove("ce-os-dock-visible", "workspace-task-dock-open");
  qa(".workspace-task-dock, .workspace-deckbar").forEach((node) => node.remove());
}

function markSurface() {
  const page = currentPage();
  if (!page) return;
  page.classList.add("ce-v4-page");
  const surface = qa(
    ".review-desktop-os, .generation-os-shell, .media-finder-shell, .work-stage-shell, .tasks-desk-shell, "
      + ".publishing-os-shell, .results-ledger-shell, .workspace-board, .home-project-switcher, .ce-v4-home",
    page,
  ).filter(isVisible).at(-1);
  qa("[data-ce-v4-surface]", page).forEach((node) => { if (node !== surface && !node.classList.contains("ce-v4-home")) node.removeAttribute("data-ce-v4-surface"); });
  if (surface) surface.dataset.ceV4Surface = "true";
}

function mount() {
  const route = routePath();
  if (!isWorkspaceRoute(route) || !hasAuthenticatedWorkspace()) {
    closeTransientOverlays(true);
    runtime.menubar?.remove();
    runtime.dock?.remove();
    runtime.menubar = null;
    runtime.dock = null;
    document.body.classList.remove("contentengine-desktop-v4");
    document.body.removeAttribute("data-ce-v4-stable");
    document.documentElement.removeAttribute("data-contentengine-os");
    return;
  }
  document.documentElement.dataset.contentengineOs = "v4";
  document.body.classList.add("contentengine-desktop-v4");
  document.body.dataset.ceV4Stable = "true";
  cleanLegacyChrome();
  ensureMenubar();
  ensureDock();
  updateMenubar();
  updateDock();
  mountHome();
  syncProjectProgress();
}

function scheduleMount() {
  if (runtime.mounting) {
    runtime.needsMount = true;
    return;
  }
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(runMount);
}

function observeWorkspace() {
  const root = q("#app") || document.documentElement;
  if (!runtime.observer) runtime.observer = new MutationObserver(scheduleMount);
  runtime.observer.disconnect();
  runtime.observerRoot = root;
  runtime.observer.observe(root, {
    attributes: true,
    attributeFilter: ["data-workspace-authorized-routes"],
    childList: true,
    subtree: true,
  });
}

function runMount() {
  runtime.queued = false;
  if (runtime.mounting) {
    runtime.needsMount = true;
    return;
  }
  runtime.mounting = true;
  runtime.needsMount = false;
  runtime.observer?.disconnect();
  try {
    mount();
    [...runtime.adapters.values()]
      .sort((left, right) => left.priority - right.priority || left.name.localeCompare(right.name))
      .forEach((adapter) => {
        try { adapter.mount(); }
        catch (error) { console.error(`ContentEngine adapter ${adapter.name} failed`, error); }
      });
    setupVideoGovernor();
    syncSingleRouteScroll();
    markSurface();
    bindScrollOwner();
    restoreScroll(runtime.actionKey);
  } finally {
    runtime.mounting = false;
    observeWorkspace();
    const waiters = runtime.flushWaiters.splice(0);
    waiters.forEach((resolve) => resolve());
    if (runtime.needsMount) scheduleMount();
  }
}

function registerAdapter(name, adapterMount, options = {}) {
  if (!name || typeof adapterMount !== "function") throw new TypeError("Desktop adapter requires a name and mount function");
  runtime.adapters.set(name, {
    name,
    mount: adapterMount,
    priority: Number.isFinite(options.priority) ? options.priority : 100,
  });
  scheduleMount();
  return () => {
    runtime.adapters.delete(name);
    scheduleMount();
  };
}

function flush() {
  return new Promise((resolve) => {
    runtime.flushWaiters.push(resolve);
    scheduleMount();
  });
}

function handleHashChange() {
  window.clearTimeout(runtime.scrollTimer);
  window.clearTimeout(runtime.handoffTimer);
  runtime.handoffTimer = 0;
  currentPage()?.classList.remove("ce-v4-handoff-leaving");
  delete document.documentElement.dataset.ceV4Handoff;
  const previousActionKey = runtime.actionKey;
  if (runtime.preNavigationActionKey === previousActionKey) {
    runtime.preNavigationActionKey = "";
  } else {
    captureScroll(runtime.route, previousActionKey);
  }
  closeTransientOverlays(true);
  runtime.route = routePath();
  runtime.actionKey = workspaceActionKey();
  runtime.pendingActionReset = previousActionKey === runtime.actionKey ? "" : runtime.actionKey;
  runtime.restoredRoute = "";
  runtime.restoredScrollNodes = new WeakSet();
  scheduleMount();
}

function handleKeydown(event) {
  if (!isWorkspaceRoute() || !hasAuthenticatedWorkspace()) return;
  const target = event.target instanceof Element ? event.target : null;
  const editing = Boolean(target?.closest("input, textarea, select, [contenteditable='true']"));
  if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    event.stopImmediatePropagation();
    const search = q(".ce-v4-menubar__search input", runtime.menubar);
    safeFocus(search);
    search?.select?.();
    return;
  }
  if (event.key === "Escape") {
    if (runtime.spotlight) closeElementOverlay("spotlight");
    else if (runtime.mission) closeElementOverlay("mission");
    else if (runtime.zen) closeZen();
    return;
  }
  if (!editing && hasAuthenticatedWorkspace() && event.altKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code)) {
    const item = authorizedRoutes(ROUTES)[Number(event.code.slice(-1)) - 1];
    if (item) {
      event.preventDefault();
      const snapshot = projectFlowSnapshot();
      const stage = stageForRoute(item.route, snapshot);
      if (stageLocked(stage, snapshot)) explainLockedStage(stage);
      else navigate(item.route);
    }
  }
}

function handleScroll() {
  window.clearTimeout(runtime.scrollTimer);
  runtime.scrollTimer = window.setTimeout(() => captureScroll(routePath(), workspaceActionKey()), 180);
}

function handlePointerDown(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target?.closest(".ce-v4-project-switcher")) closeProjectMenu();
  if (!target?.closest(".ce-v4-menubar__tools")) closeToolsMenu();
}

function bindScrollOwner() {
  const owner = q("#main-content");
  if (!owner || owner.dataset.ceV4ScrollBound === "true") return;
  owner.dataset.ceV4ScrollBound = "true";
  owner.addEventListener("scroll", handleScroll, { passive: true });
}

window.addEventListener("hashchange", handleHashChange, { capture: true, passive: true });
window.addEventListener("scroll", handleScroll, { passive: true });
document.addEventListener(CLOSE_TRANSIENTS_EVENT, (event) => {
  if (event.detail?.source !== "core") closeTransientOverlays(true);
});
document.addEventListener("keydown", handleKeydown, true);
document.addEventListener("pointerdown", handlePointerDown, true);
document.addEventListener("contentengine:v4-handoff", (event) => {
  void handoff(event.detail?.route, event.detail || {});
});
document.addEventListener("contentengine:workspace-shell-updated", scheduleMount);
document.addEventListener("contentengine:notifications-updated", scheduleMount);
observeWorkspace();
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();

window.ContentEngineDesktopV4 = Object.freeze({
  build: BUILD,
  routes: ROUTES,
  route: routePath,
  actionKey: workspaceActionKey,
  navigate,
  handoff,
  icon,
  create,
  registerAdapter,
  captureCurrentAction,
  resetActionScroll,
  syncRoute: handleHashChange,
  requestMount: scheduleMount,
  flush,
  scheduleMount,
});
