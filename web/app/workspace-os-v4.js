/*
 * ContentEngine Desktop v4.
 *
 * One web workspace and one Dock with several independently managed live
 * application windows. Each visible window owns one same-origin child document,
 * so its forms, scroll and route remain independent without cloning business
 * DOM or transporting credentials. This module never calls business APIs.
 */

import { isWorkspaceActionKey, workspaceActionKey } from "./workspace-action-key.js?v=20260826.rebuild-clean.60";
import {
  createWorkspaceWindowManagerState,
  workspaceWindowManagerReducer,
} from "./workspace-window-manager-contract.js?v=20260826.rebuild-clean.60";
import {
  WORKSPACE_DOCK_PIN_HOVER_MS,
  WORKSPACE_DOCK_PREFERENCE_VERSION,
  allocateWorkspaceDockShortcutId,
  computeWorkspaceDockPresentation,
  createWorkspaceDockState,
  normalizeWorkspaceDockExternalTarget,
  selectWorkspaceDockShortcut,
  workspaceDockReducer,
} from "./workspace-dock-contract.js?v=20260826.rebuild-clean.60";
import {
  WORKSPACE_INTERNAL_APP_TABS,
  WORKSPACE_INTERNAL_SPACES,
  resolveWorkspaceCommand,
} from "./workspace-command-registry.js?v=20260826.rebuild-clean.60";
import {
  countWorkspaceNotificationItems,
  evaluateWorkspaceNotificationAction,
  filterWorkspaceNotificationItems,
  formatWorkspaceNotificationBadge,
  normalizeWorkspaceNotificationFeed,
} from "./workspace-notification-contract.js?v=20260826.rebuild-clean.60";
import {
  CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
  CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
  createContentEngineEmbeddedWindowUrl,
  readContentEngineEmbeddedWindowEvent,
} from "./workspace-embedded-window-contract.js?v=20260826.rebuild-clean.60";

const BUILD = "20260826.rebuild-clean.60";
const STORAGE_KEY = "contentengine.desktop-v4.v1";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const PROJECT_CONTEXT_KEY = "contentengine.desktop-v4.project";
const DOCK_PREFERENCE_STORAGE_PREFIX = "contentengine.desktop-v4.dock";
const DESKTOP_SHORTCUT_STORAGE_PREFIX = "contentengine.desktop-v4.shortcuts.v1";
const PROJECT_COVER_STORAGE_PREFIX = "contentengine.desktop-v4.project-covers.v1";
const CLOSE_TRANSIENTS_EVENT = "contentengine:v4-close-transients";
const WINDOW_GEOMETRY_EVENT = "contentengine:workspace-window-geometry";
const NOTIFICATION_FEED_SNAPSHOT_ID = "workspace-notification-feed-snapshot";
const NOTIFICATION_FEED_SCHEMA = "contentengine-notification-feed-v4.9.1";
const NOTIFICATION_RUNTIME_REQUEST_EVENT =
  "contentengine:notification-center-request-v491";
const NOTIFICATION_RUNTIME_RESPONSE_EVENT =
  "contentengine:notification-center-response-v491";
const NOTIFICATION_RUNTIME_VERSION = "4.9.1";
const WINDOW_SNAP_EDGE = 34;
const IS_EMBEDDED_WORKSPACE_WINDOW = window.CONTENTENGINE_EMBEDDED_WINDOW === true
  || document.documentElement.dataset.ceWindowChild === "true";
const SVG_NS = "http://www.w3.org/2000/svg";
const XLINK_NS = "http://www.w3.org/1999/xlink";
const DOCK_SPRITE = new URL("./assets/workspace_dock_icon_sprite_v4_7_1.svg?v=20260826.rebuild-clean.60", import.meta.url).href;
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const DOCK_INTERNAL_POLICY = Object.freeze({
  spaces: WORKSPACE_INTERNAL_SPACES,
  apps: WORKSPACE_INTERNAL_APP_TABS,
  defaultSpace: "bombbar",
});

const NOTIFICATION_FILTERS = Object.freeze([
  Object.freeze({ key: "all", label: "Все" }),
  Object.freeze({ key: "unread", label: "Непрочитанные" }),
  Object.freeze({ key: "action_required", label: "Нужно действие" }),
]);
const NOTIFICATION_TYPE_LABELS = Object.freeze({
  action_required: "Нужно решение",
  mention: "Упоминание",
  assignment: "Назначение",
  process_complete: "Процесс завершён",
  warning: "Предупреждение",
  error: "Ошибка",
  access_change: "Доступ",
  system_info: "Система",
});
const NOTIFICATION_ACTION_REASONS = Object.freeze({
  action_key_required: "Для этого события не указан точный переход.",
  expiry_recheck_required: "Срок события нужно перепроверить на сервере.",
  external_command_validation_required: "Точная команда ещё не подтверждена текущим владельцем раздела.",
  notification_recheck_required: "Текущее состояние события ещё не подтверждено.",
  permission_denied: "Доступ к объекту отозван.",
  permission_recheck_required: "Доступ нужно перепроверить.",
  process_id_required: "Точный процесс не указан.",
  recipient_recheck_required: "Получателя нужно перепроверить.",
  stale_notification: "Состояние объекта изменилось. Откройте актуальную версию.",
  stale_target: "Состояние объекта изменилось. Откройте актуальную версию.",
  target_recheck_required: "Точный объект нужно перепроверить.",
  unknown_action: "Действие недоступно в этой версии интерфейса.",
  wrong_recipient: "Это уведомление предназначено другому сотруднику.",
  action_validation_on_open: "Доступ и точная цель будут перепроверены перед переходом.",
  auth_session_required: "Сессия завершилась. Войдите снова; уведомление осталось непрочитанным.",
  expired: "Срок действия уведомления истёк. Оно осталось непрочитанным.",
  feed_schema_mismatch: "Сервер вернул неподдерживаемый формат уведомлений.",
  legacy_action_unsupported: "Старое уведомление нельзя открыть без точной современной цели.",
  notification_action_target_unsupported: "Для этого типа события пока нет точного безопасного перехода.",
  notification_center_scope_changed: "Пользователь, роль или организация изменились. Откройте панель заново.",
  notification_command_destination_invalid: "Точный рабочий раздел не подтверждён.",
  notification_command_failed: "Рабочий раздел не подтвердил переход. Уведомление осталось непрочитанным.",
  notification_read_state_unsupported: "Состояние прочтения этого события больше не поддерживается.",
  notification_request_failed: "Не удалось обновить уведомления. Ничего не отмечено прочитанным.",
  notification_request_timeout: "Сервер уведомлений не ответил вовремя. Ничего не отмечено прочитанным.",
  notification_unavailable: "Уведомление больше недоступно текущему пользователю.",
  target_ambiguous: "Сервер нашёл несколько целей и отказался выбирать за вас.",
});
const NOTIFICATION_SOURCE_TONES = Object.freeze({
  ai: "amethyst",
  create: "champagne",
  finder: "platinum",
  processes: "sapphire",
  publish: "cyan",
  research: "sapphire",
  results: "emerald",
  review: "ruby",
  system: "platinum",
});

/*
 * The Dock is the primary workspace switcher. Research and governed AI
 * learning sit beside the production flow; infrequent tools stay in the menu.
 */
const ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/home", label: "Проекты", icon: "home", dockIcon: "ce-dock-finder", appLabel: "Рабочий стол", accent: "#98A9BD", description: "Выберите рабочий стол или создайте новый" }),
  Object.freeze({ route: "/workspace/board", label: "Файлы", icon: "folder", dockIcon: "ce-dock-finder", appLabel: "Finder", accent: "#98A9BD", description: "Папки, видео, поиск и исходники" }),
  Object.freeze({ route: "/workspace/generation", label: "Создать", icon: "spark", dockIcon: "ce-dock-create", appLabel: "Создать", accent: "#D7AD59", description: "Один ролик или фото за запуск" }),
  Object.freeze({ route: "/workspace/review", label: "Проверить", icon: "check", dockIcon: "ce-dock-review", appLabel: "Проверить", accent: "#C84C65", description: "Качество, риски и одно решение" }),
  Object.freeze({ route: "/workspace/placement", label: "Опубликовать", icon: "upload", dockIcon: "ce-dock-publish", appLabel: "Публикация", accent: "#38D2E8", description: "Один пост — один маршрут" }),
  Object.freeze({ route: "/workspace/stats", label: "Результаты", icon: "chart", dockIcon: "ce-dock-results", appLabel: "Результаты", accent: "#39D99E", description: "Метрики и следующая гипотеза" }),
  Object.freeze({ route: "/workspace/passports", label: "Паспорта", icon: "chart", dockIcon: "ce-dock-passports", appLabel: "Паспорта", accent: "#5FB0FF", description: "Паспорт ролика: от исходника до метрик и денег" }),
  Object.freeze({ route: "/workspace/hypotheses", label: "Гипотезы", icon: "spark", dockIcon: "ce-dock-hypotheses", appLabel: "Гипотезы", accent: "#C77DFF", description: "Идея → версии → тест → человеческий вывод" }),
  Object.freeze({ route: "/workspace/research", label: "Исследования", icon: "search", dockIcon: "ce-dock-research", appLabel: "Исследования", accent: "#4A8FFF", description: "Факты, источники и сценарии" }),
  Object.freeze({ route: "/workspace/ai", label: "ИИ-центр", icon: "spark", dockIcon: "ce-dock-ai", appLabel: "ИИ-центр", accent: "#976BFF", description: "Знания категорий и обратная связь" }),
]);

const SECONDARY_ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/team", label: "Команда", icon: "work", dockIcon: "ce-dock-settings", appLabel: "Команда", accent: "#8894A3", description: "Доступы и участники" }),
  Object.freeze({ route: "/workspace/feedback", label: "Помощь", icon: "tasks", dockIcon: "ce-dock-settings", appLabel: "Помощь", accent: "#8894A3", description: "Сообщить о препятствии" }),
]);

const CONTEXT_ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/tasks", label: "Задача", icon: "tasks", dockIcon: "ce-dock-processes", appLabel: "Процессы", accent: "#5D82FF", description: "Одно назначенное действие внутри текущего этапа" }),
  Object.freeze({ route: "/workspace/work", label: "Моя работа", icon: "work", dockIcon: "ce-dock-processes", appLabel: "Моя работа", accent: "#5D82FF", description: "Личная очередь и уведомления" }),
]);
const ALL_ROUTES = Object.freeze([...ROUTES, ...SECONDARY_ROUTES, ...CONTEXT_ROUTES]);
const DOCK_APPS = Object.freeze([
  Object.freeze({ key: "finder", route: "/workspace/board", label: "Finder", dockIcon: "ce-dock-finder", description: "Проекты, папки, файлы и источники" }),
  Object.freeze({ key: "research", route: "/workspace/research", label: "Исследования", dockIcon: "ce-dock-research", description: "Факты, источники и сценарии" }),
  Object.freeze({ key: "ai", route: "/workspace/ai", label: "ИИ-центр", dockIcon: "ce-dock-ai", description: "Знания категорий и обратная связь" }),
  Object.freeze({ key: "create", route: "/workspace/generation", label: "Создать", dockIcon: "ce-dock-create", description: "Один ролик или фото за запуск" }),
  Object.freeze({ key: "review", route: "/workspace/review", label: "Проверить", dockIcon: "ce-dock-review", description: "Качество, риски и одно решение" }),
  Object.freeze({ key: "publish", route: "/workspace/placement", label: "Опубликовать", dockIcon: "ce-dock-publish", description: "Один пост — один маршрут" }),
  Object.freeze({ key: "results", route: "/workspace/stats", label: "Результаты", dockIcon: "ce-dock-results", description: "Метрики и следующая гипотеза" }),
  Object.freeze({ key: "passports", route: "/workspace/passports", label: "Паспорта", dockIcon: "ce-dock-passports", description: "Паспорт ролика: от исходника до метрик и денег" }),
  Object.freeze({ key: "hypotheses", route: "/workspace/hypotheses", label: "Гипотезы", dockIcon: "ce-dock-hypotheses", description: "Идея → версии → тест → человеческий вывод" }),
  Object.freeze({ key: "processes", route: "/workspace/work", label: "Процессы", dockIcon: "ce-dock-processes", description: "Личная очередь и рабочие действия" }),
  Object.freeze({ key: "settings", route: "/workspace/team", label: "Команда", dockIcon: "ce-dock-settings", description: "Доступы и участники" }),
]);
const DOCK_CANONICAL_ORDER = Object.freeze([
  "finder",
  "research",
  "ai",
  "create",
  "review",
  "publish",
  "results",
  "passports",
  "hypotheses",
  "processes",
  "settings",
  "trash",
]);
const DOCK_ITEMS = Object.freeze([
  ...DOCK_APPS,
  Object.freeze({ key: "trash", label: "Корзина", dockIcon: "ce-dock-trash", description: "Удалённые файлы и папки", kind: "trash" }),
]);
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
const PROJECT_COVER_OPTIONS = Object.freeze([
  Object.freeze({ key: "auto", label: "Автовыбор", detail: "Разные обложки по порядку проектов" }),
  Object.freeze({ key: "campaign", label: "Кампания", detail: "Автомобиль · тёплый запуск" }),
  Object.freeze({ key: "digital", label: "Digital", detail: "Наушники · неоновый продукт" }),
  Object.freeze({ key: "product", label: "Продукт", detail: "Предметная премиальная съёмка" }),
  Object.freeze({ key: "editorial", label: "История", detail: "Камера · editorial и travel" }),
]);
const ROLE_GATED_ROUTES = new Set(["/workspace/research", "/workspace/ai", "/workspace/team"]);
const PROJECT_REQUIRED_ROUTES = new Set([
  "/workspace/board",
  "/workspace/media",
  "/workspace/generation",
  "/workspace/review",
  "/workspace/tasks",
  "/workspace/placement",
  "/workspace/stats",
  "/workspace/passports",
  "/workspace/hypotheses",
  "/workspace/payouts",
  "/workspace/research",
  "/workspace/work",
]);
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
  info: ["M12 11v6", "M12 7h.01", "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z"],
  alert: ["M12 4 3 20h18L12 4Z", "M12 9v5", "M12 17h.01"],
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
  dockState: createWorkspaceDockState(
    { order: DOCK_CANONICAL_ORDER, shortcuts: {} },
    { internalPolicy: DOCK_INTERNAL_POLICY },
  ),
  dockPresentation: null,
  dockScope: null,
  dockStorageKey: "",
  dockPreferenceLoaded: false,
  dockStorageWrites: 0,
  dockResolvedTargets: new Map(),
  dockResolutionEpoch: 0,
  dockLibraryCandidates: new Map(),
  dockPinZoneTimer: 0,
  dockDraggedFile: null,
  dockEditor: null,
  dockLibrary: null,
  dockEditorReturnFocus: null,
  dockLibraryReturnFocus: null,
  dockPointerReorder: null,
  dockSuppressClickUntil: 0,
  dockLastCommitEffects: [],
  notificationPanel: null,
  notificationFilter: "all",
  notificationReturnFocus: null,
  notificationFeed: null,
  notificationFeedSignature: "",
  notificationFeedIssue: "feed_unavailable",
  notificationActionContexts: Object.freeze({}),
  notificationServerCounts: null,
  notificationLoadedFilter: "",
  notificationPendingRequests: new Map(),
  notificationRequestSequence: 0,
  notificationActionFailures: new Map(),
  notificationLastError: "",
  notificationActionNavigationHash: "",
  notificationInitialLoadRequested: false,
  desktop: null,
  desktopShortcutsEditing: false,
  desktopShortcutDrag: null,
  desktopSuppressClickUntil: 0,
  windowShell: null,
  windowShells: new Map(),
  windowSurfaces: new Map(),
  windowSnapshots: new Map(),
  windowRoute: "",
  activeWindowId: "",
  windowManagerState: createWorkspaceWindowManagerState(),
  windowRoutes: new Map(),
  windowDrag: null,
  windowGeometryTouched: new Set(),
  windowZoomClicks: new Map(),
  windowSnapMemory: new Map(),
  windowSnapPreview: null,
  windowSnapAssist: null,
  windowSnapResizeFrame: 0,
  windowResizeObserver: null,
  windowResizeObservers: new Map(),
  syncingWindowGeometry: false,
  mission: null,
  spotlight: null,
  spotlightRecords: [],
  spotlightIndex: 0,
  projectCover: null,
  modalContexts: new Map(),
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

function dockIcon(symbol, size = 52) {
  const svg = document.createElementNS(SVG_NS, "svg");
  const href = `${DOCK_SPRITE}#${symbol || "ce-dock-finder"}`;
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 64 64");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  svg.classList.add("ce-v4-dock-glyph");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", href);
  use.setAttributeNS(XLINK_NS, "href", href);
  svg.append(use);
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

function workspaceDesktopRoute(route = window.location.hash || "#/workspace/home") {
  const { path, query } = routeParts(route);
  const view = String(query.get("view") || "").trim().toLowerCase();
  return path === "/workspace/home" && (!view || view === "desktop");
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

function workspaceRouteRequiresProject(route) {
  const { path, query } = routeParts(route);
  if (
    path === "/workspace/work"
    && String(query.get("view") || "").trim().toLowerCase() === "notifications"
  ) return false;
  return PROJECT_REQUIRED_ROUTES.has(path);
}

function projectChooserMode() {
  if (routePath() !== "/workspace/home") return false;
  const values = routeQuery().getAll("project_id");
  return values.length !== 1 || !PROJECT_ID_PATTERN.test(String(values[0] || "").trim().toLowerCase());
}

function focusProjectChoiceTarget(attempt = 0) {
  const target = q('[data-action="retry-project-flow"]')
    || q("[data-ce-v4-project-id]")
    || q("#home-projects-title");
  if (target instanceof HTMLElement) {
    if (!target.matches("button, a, input, select, textarea, [tabindex]")) target.tabIndex = -1;
    target.focus({ preventScroll: false });
    target.scrollIntoView?.({ block: "center", inline: "nearest", behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });
    return true;
  }
  if (attempt < 5) window.setTimeout(() => focusProjectChoiceTarget(attempt + 1), 80 * (attempt + 1));
  return false;
}

function explainProjectRequired(destination = "") {
  const label = routeRecord(routeParts(destination).path)?.label || "Раздел";
  showSystemToast(
    `${label}: сначала выберите проект. Нажмите на карточку проекта — раздел откроется с его данными.`,
    "warning",
  );
  if (routePath() !== "/workspace/home") {
    window.location.hash = "#/workspace/home";
    window.setTimeout(() => focusProjectChoiceTarget(), 0);
    return;
  }
  window.queueMicrotask(() => focusProjectChoiceTarget());
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
  if (workspaceRouteRequiresProject(requested) && !requestedProjectId && !currentProjectId) {
    explainProjectRequired(requested);
    return "/workspace/home";
  }
  const destination = settings.preserveProject === false
    ? routeWithProject(requested, requestedProjectId || "")
    : routeWithProject(requested, requestedProjectId || currentProjectId);
  captureCurrentAction();
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  closeTransientOverlays(true);
  window.location.hash = `#${destination}`;
  return destination;
}

function navigatePrimaryRoute(route) {
  const requested = String(route || "/workspace/home");
  if (routeParts(requested).path === "/workspace/home") {
    return navigate("/workspace/home", { preserveProject: false });
  }
  return navigate(requested);
}

function focusFinderSearch(query = "") {
  const value = String(query || "").trim();
  if (value) storage("session")?.setItem(FINDER_QUERY_KEY, value);
  if (routePath() !== "/workspace/board") {
    const destination = navigate("/workspace/board");
    if (routeParts(destination).path !== "/workspace/board") return;
  }
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

function notificationScopeId(value) {
  if (typeof value !== "string") return "";
  const candidate = value.trim();
  return candidate
    && candidate === value
    && candidate.length <= 256
    && !/[\u0000-\u0020\u007F]/u.test(candidate)
      ? candidate
      : "";
}

function notificationRecipientContext(rawRecipient) {
  if (!rawRecipient || typeof rawRecipient !== "object" || Array.isArray(rawRecipient)) return null;
  const organizationId = notificationScopeId(
    rawRecipient.organizationId ?? rawRecipient.organization_id,
  );
  const userId = notificationScopeId(rawRecipient.userId ?? rawRecipient.user_id);
  if (!organizationId || !userId) return null;
  const roleIds = [];
  const candidates = rawRecipient.roleIds ?? rawRecipient.role_ids ?? [];
  (Array.isArray(candidates) ? candidates : [candidates]).forEach((value) => {
    const roleId = notificationScopeId(value);
    if (roleId && !roleIds.includes(roleId)) roleIds.push(roleId);
  });
  return Object.freeze({ organizationId, userId, roleIds: Object.freeze(roleIds) });
}

function notificationFixtureMode() {
  return document.documentElement.dataset.ceV4NotificationFixture === "true";
}

function normalizedNotificationProjectionCount(value) {
  const count = Number(value);
  return Number.isInteger(count) && count >= 0 && count <= 10_000_000 ? count : null;
}

function acceptNotificationCenterProjection(rawProjection, expectedFilter) {
  if (!rawProjection || typeof rawProjection !== "object" || Array.isArray(rawProjection)) {
    return { ok: false, reason: "feed_invalid" };
  }
  const recipient = notificationRecipientContext({
    organizationId: rawProjection.organization_id,
    userId: rawProjection.recipient_user_id,
    roleIds: rawProjection.active_role_ids,
  });
  const filter = String(rawProjection.filter || "");
  const countsSource = rawProjection.counts;
  const meta = rawProjection._meta;
  if (
    !recipient
    || filter !== expectedFilter
    || !NOTIFICATION_FILTERS.some((item) => item.key === filter)
    || !Array.isArray(rawProjection.items)
    || rawProjection.items.length > 100
    || !countsSource
    || typeof countsSource !== "object"
    || Array.isArray(countsSource)
    || meta?.contract_version !== "4.9.1"
    || meta?.read_state_version !== "contentengine-notification-read-v4.9.1"
  ) return { ok: false, reason: "feed_schema_mismatch" };
  const counts = {
    all: normalizedNotificationProjectionCount(countsSource.all),
    unread: normalizedNotificationProjectionCount(countsSource.unread),
    actionRequired: normalizedNotificationProjectionCount(countsSource.action_required),
    mentions: normalizedNotificationProjectionCount(countsSource.mentions),
    processes: normalizedNotificationProjectionCount(countsSource.processes),
    system: normalizedNotificationProjectionCount(countsSource.system),
  };
  if (Object.values(counts).some((value) => value === null)) {
    return { ok: false, reason: "feed_schema_mismatch" };
  }
  const readNotificationIds = rawProjection.items
    .filter((item) => typeof item?.read_at === "string" && Number.isFinite(Date.parse(item.read_at)))
    .map((item) => String(item.notification_id || ""));
  const now = new Date().toISOString();
  const feed = normalizeWorkspaceNotificationFeed(rawProjection.items, {
    recipient,
    now,
    readState: {
      version: "contentengine-notification-read-v4.9.1",
      scope: recipient,
      readNotificationIds,
    },
  });
  if (!feed.readStateAccepted) return { ok: false, reason: "read_state_unavailable" };
  runtime.notificationFeed = Object.freeze({ ...feed, recipient, now });
  runtime.notificationFeedSignature = "server-projection";
  runtime.notificationFeedIssue = "";
  runtime.notificationServerCounts = Object.freeze(counts);
  runtime.notificationLoadedFilter = filter;
  runtime.notificationActionContexts = Object.freeze({});
  window.queueMicrotask(() => {
    if (!hasAuthenticatedWorkspace()) return;
    updateMenubar();
  });
  return { ok: true, reason: "" };
}

function notificationFeedSnapshot() {
  const source = document.getElementById(NOTIFICATION_FEED_SNAPSHOT_ID);
  const serialized = String(source?.textContent || "").trim();
  if (!serialized) {
    return {
      signature: "",
      feed: null,
      issue: "feed_unavailable",
      actionContexts: Object.freeze({}),
    };
  }
  let raw;
  try {
    raw = JSON.parse(serialized);
  } catch {
    return {
      signature: serialized,
      feed: null,
      issue: "feed_invalid",
      actionContexts: Object.freeze({}),
    };
  }
  const recipient = notificationRecipientContext(raw?.recipient);
  const parsedNow = Date.parse(String(raw?.now || ""));
  if (
    !raw
    || typeof raw !== "object"
    || Array.isArray(raw)
    || raw.schemaVersion !== NOTIFICATION_FEED_SCHEMA
    || !Array.isArray(raw.events)
    || !recipient
    || !Number.isFinite(parsedNow)
  ) {
    return {
      signature: serialized,
      feed: null,
      issue: "feed_schema_mismatch",
      actionContexts: Object.freeze({}),
    };
  }
  const now = new Date(parsedNow).toISOString();
  const feed = normalizeWorkspaceNotificationFeed(raw.events, {
    recipient,
    readState: raw.readState,
    now,
  });
  if (!feed.readStateAccepted) {
    return {
      signature: serialized,
      feed,
      issue: "read_state_unavailable",
      actionContexts: Object.freeze({}),
    };
  }
  const rawContexts = raw.actionContextByNotificationId;
  const actionContexts = {};
  if (rawContexts && typeof rawContexts === "object" && !Array.isArray(rawContexts)) {
    feed.items.forEach((item) => {
      const id = item.notification.notificationId;
      const candidate = rawContexts[id];
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return;
      const recordState = ["current", "stale", "missing", "unknown"].includes(candidate.recordState)
        ? candidate.recordState
        : "unknown";
      const permissionState = ["allowed", "denied", "revoked", "unknown"].includes(candidate.permissionState)
        ? candidate.permissionState
        : "unknown";
      const targetState = ["current", "stale", "missing", "revoked", "unknown"].includes(candidate.targetState)
        ? candidate.targetState
        : "unknown";
      actionContexts[id] = Object.freeze({ recordState, permissionState, targetState });
    });
  }
  return {
    signature: serialized,
    feed: Object.freeze({ ...feed, recipient, now }),
    issue: "",
    actionContexts: Object.freeze(actionContexts),
  };
}

function syncNotificationFeed() {
  if (!notificationFixtureMode()) return;
  const next = notificationFeedSnapshot();
  if (runtime.notificationFeedSignature === next.signature && runtime.notificationFeedIssue === next.issue) return;
  runtime.notificationFeedSignature = next.signature;
  runtime.notificationFeed = next.feed;
  runtime.notificationFeedIssue = next.issue;
  runtime.notificationActionContexts = next.actionContexts;
}

function notificationPending(kind, notificationId = "") {
  return [...runtime.notificationPendingRequests.values()].some((request) => (
    request.kind === kind
    && (!notificationId || request.notificationId === notificationId)
  ));
}

function notificationOpenRequestPending() {
  return notificationPending("open");
}

function requestNotificationRuntime(kind, detail = {}) {
  if (notificationFixtureMode() || !hasAuthenticatedWorkspace()) return false;
  const requestId = `notification:${Date.now().toString(36)}:${(++runtime.notificationRequestSequence).toString(36)}`;
  const filter = String(detail.filter || runtime.notificationFilter || "all");
  const notificationId = String(detail.notification?.notificationId || "");
  const request = {
    requestId,
    kind,
    filter,
    notificationId,
    timer: 0,
  };
  request.timer = window.setTimeout(() => {
    if (!runtime.notificationPendingRequests.has(requestId)) return;
    runtime.notificationPendingRequests.delete(requestId);
    if (kind === "refresh" && !runtime.notificationFeed) {
      runtime.notificationFeedIssue = "notification_request_timeout";
    }
    if (kind === "open" && notificationId) {
      runtime.notificationActionFailures.set(notificationId, "notification_request_timeout");
    }
    runtime.notificationLastError = "notification_request_timeout";
    syncNotificationCenter();
  }, 20_000);
  runtime.notificationPendingRequests.set(requestId, request);
  if (kind === "refresh" && !runtime.notificationFeed) {
    runtime.notificationFeedIssue = "feed_loading";
  }
  runtime.notificationLastError = "";
  document.dispatchEvent(new CustomEvent(NOTIFICATION_RUNTIME_REQUEST_EVENT, {
    detail: Object.freeze({
      version: NOTIFICATION_RUNTIME_VERSION,
      requestId,
      kind,
      filter,
      ...detail,
    }),
  }));
  syncNotificationCenter();
  return true;
}

function requestNotificationCenterProjection(filter = runtime.notificationFilter, options = {}) {
  const normalizedFilter = NOTIFICATION_FILTERS.some((item) => item.key === filter)
    ? filter
    : "all";
  if (
    notificationFixtureMode()
    || notificationPending("refresh")
    || (
      options.force !== true
      && runtime.notificationLoadedFilter === normalizedFilter
      && runtime.notificationFeed
      && !runtime.notificationFeedIssue
    )
  ) return false;
  return requestNotificationRuntime("refresh", { filter: normalizedFilter });
}

function requestNotificationVisibleRead(notificationIds) {
  const ids = [...new Set((notificationIds || []).map((value) => String(value || "")))]
    .filter(Boolean)
    .slice(0, 100);
  if (!ids.length || notificationPending("mark_read")) return false;
  return requestNotificationRuntime("mark_read", {
    filter: runtime.notificationFilter,
    notificationIds: Object.freeze(ids),
  });
}

function requestNotificationOpen(item) {
  const notification = item?.notification;
  if (!notification || notificationPending("open", notification.notificationId)) return false;
  runtime.notificationActionFailures.delete(notification.notificationId);
  return requestNotificationRuntime("open", {
    filter: runtime.notificationFilter,
    notification: Object.freeze({
      notificationId: notification.notificationId,
      actionKey: notification.actionKey || "",
      projectId: notification.projectId || "",
      objectId: notification.objectId || "",
      processId: notification.processId || "",
    }),
  });
}

function applyNotificationReadIds(notificationIds) {
  if (!runtime.notificationFeed?.items) return false;
  const ids = new Set(notificationIds || []);
  let changed = 0;
  const items = runtime.notificationFeed.items.map((item) => {
    if (!ids.has(item.notification.notificationId) || item.read) return item;
    changed += 1;
    return Object.freeze({ ...item, read: true, unread: false });
  });
  if (!changed) return false;
  runtime.notificationFeed = Object.freeze({ ...runtime.notificationFeed, items: Object.freeze(items) });
  if (runtime.notificationServerCounts) {
    runtime.notificationServerCounts = Object.freeze({
      ...runtime.notificationServerCounts,
      unread: Math.max(0, runtime.notificationServerCounts.unread - changed),
    });
  }
  syncNotificationCenter();
  window.queueMicrotask(() => {
    if (!hasAuthenticatedWorkspace()) return;
    updateMenubar();
  });
  return true;
}

function handleNotificationRuntimeResponse(event) {
  const detail = event?.detail;
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return;
  const requestId = String(detail.requestId || "");
  const pending = runtime.notificationPendingRequests.get(requestId);
  if (
    !pending
    || detail.version !== NOTIFICATION_RUNTIME_VERSION
    || detail.kind !== pending.kind
    || detail.filter !== pending.filter
  ) return;
  window.clearTimeout(pending.timer);
  runtime.notificationPendingRequests.delete(requestId);

  if (detail.ok === true) {
    let acceptedProjection = false;
    let projectionFailure = "feed_schema_mismatch";
    if (detail.projection) {
      const accepted = acceptNotificationCenterProjection(
        detail.projection,
        pending.filter,
      );
      acceptedProjection = accepted.ok;
      projectionFailure = accepted.reason || projectionFailure;
    }
    if (pending.kind === "refresh" && !acceptedProjection) {
      runtime.notificationFeedIssue = projectionFailure;
      runtime.notificationLastError = projectionFailure;
      syncNotificationCenter();
      return;
    }
    const readIds = Array.isArray(detail.notificationIds)
      ? detail.notificationIds.map((value) => String(value || ""))
      : [];
    if (!acceptedProjection && readIds.length) applyNotificationReadIds(readIds);
    readIds.forEach((id) => runtime.notificationActionFailures.delete(id));
    runtime.notificationLastError = "";
    if (acceptedProjection) syncNotificationCenter();
    if (pending.kind === "open") {
      // The router changes the hash before the authoritative read RPC finishes.
      // Keep a panel that the person reopens during that narrow async boundary.
      runtime.notificationActionNavigationHash = window.location.hash;
      closeNotificationCenter(false);
    }
  } else {
    const reason = /^[a-z][a-z0-9_]{2,95}$/u.test(String(detail.reason || ""))
      ? String(detail.reason)
      : "notification_request_failed";
    runtime.notificationLastError = reason;
    if (pending.kind === "refresh" && !runtime.notificationFeed) {
      runtime.notificationFeedIssue = reason;
    }
    if (pending.kind === "open" && pending.notificationId) {
      runtime.notificationActionFailures.set(pending.notificationId, reason);
      if (!notificationCenterOpen()) openNotificationCenter(null, { focus: false, refresh: false });
    }
    showSystemToast(notificationReasonCopy(reason), "error");
  }
  syncNotificationCenter();
}

function notificationFeedCounts() {
  if (runtime.notificationServerCounts && !notificationFixtureMode()) {
    return runtime.notificationServerCounts;
  }
  return runtime.notificationFeed?.items
    ? countWorkspaceNotificationItems(runtime.notificationFeed.items)
    : Object.freeze({ all: 0, unread: 0, actionRequired: 0 });
}

function notificationUnreadCount() {
  syncNotificationFeed();
  if (runtime.notificationFeed && !runtime.notificationFeedIssue) {
    return notificationFeedCounts().unread;
  }
  return projectFlowSnapshot().unread;
}

function notificationSourceTone(sourceSection) {
  const source = String(sourceSection || "").trim().toLocaleLowerCase("ru-RU");
  if (/(?:^|\s)(?:ai|ии)(?:\s|$)|ии[-‑ ]?центр/u.test(source)) return NOTIFICATION_SOURCE_TONES.ai;
  if (/исслед/u.test(source)) return NOTIFICATION_SOURCE_TONES.research;
  if (/созд|генерац/u.test(source)) return NOTIFICATION_SOURCE_TONES.create;
  if (/провер|review/u.test(source)) return NOTIFICATION_SOURCE_TONES.review;
  if (/публи|publish/u.test(source)) return NOTIFICATION_SOURCE_TONES.publish;
  if (/результ|result/u.test(source)) return NOTIFICATION_SOURCE_TONES.results;
  if (/процесс|process/u.test(source)) return NOTIFICATION_SOURCE_TONES.processes;
  if (/finder|файл/u.test(source)) return NOTIFICATION_SOURCE_TONES.finder;
  return NOTIFICATION_SOURCE_TONES.system;
}

function notificationSeverityIcon(severity) {
  if (severity === "success") return "check";
  if (severity === "warning" || severity === "danger") return "alert";
  return "info";
}

function notificationDateLabel(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "Время не указано";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function notificationActionPresentation(item) {
  if (item.action.state === "none") return item.action;
  if (item.action.state === "blocked") return item.action;
  const id = item.notification.notificationId;
  const failure = runtime.notificationActionFailures.get(id);
  if (failure) return Object.freeze({ ...item.action, state: "blocked", reason: failure });
  if (!notificationFixtureMode()) return item.action;
  const context = runtime.notificationActionContexts[id] || {
    recordState: "unknown",
    permissionState: "unknown",
    targetState: "unknown",
  };
  return evaluateWorkspaceNotificationAction(item.notification, {
    recipient: runtime.notificationFeed?.recipient,
    now: runtime.notificationFeed?.now,
    recordState: context.recordState,
    permissionState: context.permissionState,
    targetState: context.targetState,
  });
}

function notificationReasonCopy(reason) {
  return NOTIFICATION_ACTION_REASONS[reason]
    || "Точное действие сейчас недоступно. Уведомление останется непрочитанным.";
}

function notificationItemNode(item) {
  const notification = item.notification;
  const action = notificationActionPresentation(item);
  const actionReason = action.state === "inert"
    ? "action_validation_on_open"
    : action.reason;
  const fixture = notificationFixtureMode();
  const readPending = notificationPending("mark_read");
  const openPending = notificationPending("open", notification.notificationId);
  const article = create("article", `ce-v4-notification-item${item.unread ? " is-unread" : " is-read"}`);
  article.dataset.ceV4NotificationId = notification.notificationId;
  article.dataset.ceV4NotificationSeverity = notification.severity;
  article.dataset.ceV4NotificationSourceTone = notificationSourceTone(notification.sourceSection);
  article.dataset.ceV4NotificationActionState = action.state;

  const severity = create("span", "ce-v4-notification-item__severity");
  severity.setAttribute("aria-label", `Важность: ${notification.severity}`);
  severity.append(icon(notificationSeverityIcon(notification.severity), 18));

  const content = create("div", "ce-v4-notification-item__content");
  const meta = create("div", "ce-v4-notification-item__meta");
  const source = create("span", "ce-v4-notification-item__source", notification.sourceSection);
  const time = create("time", "", notificationDateLabel(notification.createdAt));
  time.dateTime = notification.createdAt;
  meta.append(source, time);
  const title = create("h3", "", notification.title);
  const body = create("p", "ce-v4-notification-item__body", notification.body);
  const chips = create("div", "ce-v4-notification-item__chips");
  chips.append(create(
    "span",
    "ce-v4-notification-item__chip",
    NOTIFICATION_TYPE_LABELS[notification.type] || "Событие",
  ));
  if (notification.requiresAction) {
    chips.append(create("span", "ce-v4-notification-item__chip is-action", "Нужно действие"));
  }
  content.append(meta, title, body, chips);

  const controls = create("div", "ce-v4-notification-item__controls");
  if (item.unread) {
    const read = create("button", "ce-v4-notification-item__button", "Прочитать");
    read.type = "button";
    read.dataset.ceV4NotificationRead = notification.notificationId;
    read.disabled = fixture || readPending;
    read.title = fixture
      ? "Fixture не изменяет серверное состояние."
      : readPending
        ? "Сохраняем отметку прочтения…"
        : "Отметить это уведомление прочитанным";
    read.setAttribute("aria-label", `Прочитать «${compact(notification.title, 90)}»`);
    controls.append(read);
  }
  if (notification.actionKey || notification.requiresAction) {
    const open = create("button", "ce-v4-notification-item__button is-primary", "Открыть");
    open.type = "button";
    open.dataset.ceV4NotificationOpen = notification.notificationId;
    open.dataset.ceV4NotificationActionKey = action.actionKey || notification.actionKey || "";
    open.disabled = fixture || openPending || action.state !== "inert";
    open.title = notificationReasonCopy(actionReason);
    open.setAttribute("aria-describedby", `ce-v4-notification-reason-${notification.notificationId}`);
    controls.append(open);
  }
  if (controls.childElementCount) content.append(controls);

  const reason = create("p", "ce-v4-notification-item__reason");
  reason.id = `ce-v4-notification-reason-${notification.notificationId}`;
  reason.textContent = action.state === "none"
    ? item.unread
      ? fixture
        ? "Fixture показывает состояние без серверной мутации."
        : "Прочтение сохранится только для вашей учётной записи."
      : "Прочитано."
    : notificationReasonCopy(actionReason);
  if (/stale|missing|revoked/u.test(String(actionReason || ""))) article.classList.add("is-stale");
  content.append(reason);
  article.append(severity, content);
  return article;
}

function notificationEmptyNode(filter) {
  const empty = create("div", "ce-v4-notification-empty");
  const mark = create("span", "ce-v4-notification-empty__mark");
  mark.append(icon("bell", 24));
  const title = filter === "action_required"
    ? "Решений, ожидающих вас, нет"
    : filter === "unread"
      ? "Все уведомления прочитаны"
      : "Здесь пока тихо";
  const copy = filter === "action_required"
    ? "События, где нужен ваш выбор, появятся здесь."
    : "Новые рабочие события появятся в этой панели.";
  empty.append(mark, create("strong", "", title), create("p", "", copy));
  return empty;
}

function notificationFeedIssueCopy(issue) {
  if (issue === "feed_loading") {
    return "Обновляем ваши уведомления…";
  }
  if (issue === "notification_request_timeout") {
    return "Сервер уведомлений не ответил вовремя. Ничего не отмечено прочитанным.";
  }
  if (issue === "feed_invalid" || issue === "feed_schema_mismatch") {
    return "Список скрыт: источник не прошёл проверку формата v4.9.1.";
  }
  if (issue === "read_state_unavailable") {
    return "Статус прочтения не подтверждён для текущего сотрудника. События показаны без возможности изменения.";
  }
  return "Список событий ещё не передан в системную панель. Счётчик доступен, но строки не подменяются демонстрационными данными.";
}

function ensureNotificationCenter() {
  if (runtime.notificationPanel?.isConnected) return runtime.notificationPanel;
  qa("[data-ce-v4-notification-panel]").forEach((node) => node.remove());
  const panel = create("aside", "ce-v4-notification-panel");
  panel.id = "ce-v4-notification-panel";
  panel.dataset.ceV4NotificationPanel = "true";
  panel.hidden = true;
  panel.tabIndex = -1;
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "false");
  panel.setAttribute("aria-labelledby", "ce-v4-notification-title");

  const header = create("header", "ce-v4-notification-panel__header");
  const heading = create("div", "ce-v4-notification-panel__heading");
  const title = create("h2", "", "Уведомления");
  title.id = "ce-v4-notification-title";
  const summary = create("p", "", "0 непрочитанных");
  summary.dataset.ceV4NotificationSummary = "true";
  heading.append(title, summary);
  const headerActions = create("div", "ce-v4-notification-panel__header-actions");
  const markAll = create("button", "ce-v4-notification-panel__mark-all", "Прочитать всё");
  markAll.type = "button";
  markAll.dataset.ceV4NotificationMarkAll = "true";
  markAll.disabled = true;
  markAll.title = "Серверная отметка прочтения ещё не подключена к системной панели.";
  const close = iconButton("ce-v4-notification-panel__close", "Закрыть уведомления", "close");
  close.dataset.ceV4NotificationClose = "true";
  headerActions.append(markAll, close);
  header.append(heading, headerActions);

  const tabs = create("div", "ce-v4-notification-panel__filters");
  tabs.dataset.ceV4NotificationFilters = "true";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Фильтр уведомлений");
  NOTIFICATION_FILTERS.forEach((filter, index) => {
    const tab = create("button", "ce-v4-notification-panel__filter", filter.label);
    tab.type = "button";
    tab.id = `ce-v4-notification-filter-${filter.key}`;
    tab.dataset.ceV4NotificationFilter = filter.key;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", "ce-v4-notification-list");
    tab.setAttribute("aria-selected", String(index === 0));
    tab.tabIndex = index === 0 ? 0 : -1;
    tabs.append(tab);
  });

  const status = create("p", "ce-v4-notification-panel__status");
  status.dataset.ceV4NotificationStatus = "true";
  status.setAttribute("role", "status");
  const list = create("div", "ce-v4-notification-panel__list");
  list.id = "ce-v4-notification-list";
  list.dataset.ceV4NotificationList = "true";
  list.setAttribute("role", "tabpanel");
  list.setAttribute("aria-labelledby", "ce-v4-notification-filter-all");
  panel.append(header, tabs, status, list);
  document.body.append(panel);
  runtime.notificationPanel = panel;

  panel.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-notification-close]")) {
      closeNotificationCenter(true);
      return;
    }
    if (target?.closest("[data-ce-v4-notification-mark-all]")) {
      const visibleUnreadIds = visibleNotificationItems()
        .filter((item) => item.unread)
        .map((item) => item.notification.notificationId);
      requestNotificationVisibleRead(visibleUnreadIds);
      return;
    }
    const read = target?.closest("[data-ce-v4-notification-read]");
    if (read instanceof HTMLButtonElement) {
      requestNotificationVisibleRead([read.dataset.ceV4NotificationRead || ""]);
      return;
    }
    const open = target?.closest("[data-ce-v4-notification-open]");
    if (open instanceof HTMLButtonElement) {
      const notificationId = open.dataset.ceV4NotificationOpen || "";
      const item = runtime.notificationFeed?.items?.find(
        (candidate) => candidate.notification.notificationId === notificationId,
      );
      requestNotificationOpen(item);
      return;
    }
    const filter = target?.closest("[data-ce-v4-notification-filter]");
    if (filter instanceof HTMLButtonElement) {
      runtime.notificationFilter = filter.dataset.ceV4NotificationFilter || "all";
      syncNotificationCenter();
      requestNotificationCenterProjection(runtime.notificationFilter);
      safeFocus(q(`[data-ce-v4-notification-filter="${runtime.notificationFilter}"]`, panel));
    }
  });
  tabs.addEventListener("keydown", handleNotificationFilterKeydown);
  return panel;
}

function visibleNotificationItems() {
  if (!runtime.notificationFeed?.items) return [];
  if (
    !notificationFixtureMode()
    && runtime.notificationLoadedFilter !== runtime.notificationFilter
  ) return [];
  return filterWorkspaceNotificationItems(
    runtime.notificationFeed.items,
    runtime.notificationFilter,
  );
}

function syncNotificationCenter() {
  syncNotificationFeed();
  const panel = ensureNotificationCenter();
  const counts = notificationFeedCounts();
  const aggregateUnread = notificationUnreadCount();
  panel.dataset.ceV4NotificationFeedState = runtime.notificationFeedIssue || "ready";
  panel.dataset.ceV4NotificationUnread = String(aggregateUnread);
  const summary = q("[data-ce-v4-notification-summary]", panel);
  if (summary) summary.textContent = `${aggregateUnread} непрочитанных`;
  const markAll = q("[data-ce-v4-notification-mark-all]", panel);
  const visibleItems = visibleNotificationItems();
  const visibleUnreadCount = visibleItems.filter((item) => item.unread).length;
  if (markAll instanceof HTMLButtonElement) {
    markAll.disabled = notificationFixtureMode()
      || !visibleUnreadCount
      || notificationPending("mark_read");
    markAll.setAttribute("aria-label", visibleUnreadCount
      ? `Прочитать все видимые · ${visibleUnreadCount}`
      : "Все уведомления прочитаны");
  }
  qa("[data-ce-v4-notification-filter]", panel).forEach((tab) => {
    const key = tab.dataset.ceV4NotificationFilter || "all";
    const selected = key === runtime.notificationFilter;
    const count = key === "action_required" ? counts.actionRequired : counts[key] || 0;
    const label = NOTIFICATION_FILTERS.find((item) => item.key === key)?.label || "Все";
    tab.textContent = `${label} · ${count}`;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  });
  const selectedTab = q(`[data-ce-v4-notification-filter="${runtime.notificationFilter}"]`, panel);
  const list = q("[data-ce-v4-notification-list]", panel);
  if (list) list.setAttribute("aria-labelledby", selectedTab?.id || "ce-v4-notification-filter-all");

  const status = q("[data-ce-v4-notification-status]", panel);
  const rejectedCount = runtime.notificationFeed?.rejected?.length || 0;
  if (status) {
    status.hidden = !runtime.notificationFeedIssue
      && !runtime.notificationLastError
      && rejectedCount === 0;
    status.textContent = runtime.notificationLastError
      ? notificationReasonCopy(runtime.notificationLastError)
      : runtime.notificationFeedIssue
      ? notificationFeedIssueCopy(runtime.notificationFeedIssue)
      : rejectedCount
        ? `${rejectedCount} событий скрыто: данные не прошли проверку безопасности.`
        : "";
  }
  if (!list) return panel;
  list.replaceChildren(...(
    visibleItems.length
      ? visibleItems.map(notificationItemNode)
      : [notificationEmptyNode(runtime.notificationFilter)]
  ));
  return panel;
}

function handleNotificationFilterKeydown(event) {
  const target = event.target instanceof Element
    ? event.target.closest("[data-ce-v4-notification-filter]")
    : null;
  if (!(target instanceof HTMLButtonElement)) return;
  const tabs = qa("[data-ce-v4-notification-filter]", runtime.notificationPanel);
  const current = Math.max(0, tabs.indexOf(target));
  let next = current;
  if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
  else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = tabs.length - 1;
  else return;
  event.preventDefault();
  const tab = tabs[next];
  runtime.notificationFilter = tab.dataset.ceV4NotificationFilter || "all";
  syncNotificationCenter();
  requestNotificationCenterProjection(runtime.notificationFilter);
  safeFocus(q(`[data-ce-v4-notification-filter="${runtime.notificationFilter}"]`, runtime.notificationPanel));
}

function notificationCenterOpen() {
  return Boolean(runtime.notificationPanel?.isConnected && !runtime.notificationPanel.hidden);
}

function openNotificationCenter(opener = null, { focus = true, refresh = true } = {}) {
  closeProjectMenu();
  closeToolsMenu();
  closeDockMore();
  closeDockLibrary(false);
  const panel = syncNotificationCenter();
  runtime.notificationReturnFocus = opener instanceof HTMLElement
    ? opener
    : q("[data-ce-v4-notifications]", runtime.menubar);
  panel.hidden = false;
  document.body.classList.add("ce-v4-notification-open");
  const trigger = q("[data-ce-v4-notifications]", runtime.menubar);
  trigger?.setAttribute("aria-expanded", "true");
  trigger?.setAttribute("aria-pressed", "true");
  trigger?.classList.add("is-active");
  if (refresh) requestNotificationCenterProjection(runtime.notificationFilter, { force: true });
  if (focus) window.queueMicrotask(() => safeFocus(
    q(`[data-ce-v4-notification-filter="${runtime.notificationFilter}"]`, panel)
      || q("[data-ce-v4-notification-close]", panel),
  ));
  return panel;
}

function closeNotificationCenter(restoreFocus = false) {
  const panel = runtime.notificationPanel;
  if (!panel?.isConnected || panel.hidden) return false;
  panel.hidden = true;
  document.body.classList.remove("ce-v4-notification-open");
  const trigger = q("[data-ce-v4-notifications]", runtime.menubar);
  trigger?.setAttribute("aria-expanded", "false");
  trigger?.setAttribute("aria-pressed", "false");
  trigger?.classList.remove("is-active");
  if (restoreFocus) {
    const requestedTarget = runtime.notificationReturnFocus?.isConnected
      ? runtime.notificationReturnFocus
      : null;
    const returnTarget = requestedTarget?.getClientRects?.().length
      ? requestedTarget
      : trigger;
    safeFocus(returnTarget);
  }
  runtime.notificationReturnFocus = null;
  return true;
}

function toggleNotificationCenter(opener = null) {
  if (notificationCenterOpen()) return closeNotificationCenter(true);
  openNotificationCenter(opener);
  return true;
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
  const items = qa(
    "[data-ce-v4-project-option], [data-ce-v4-create-project], [data-ce-v4-all-projects]",
    menu,
  );
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
  const current = items.indexOf(target?.closest?.(
    "[data-ce-v4-project-option], [data-ce-v4-create-project], [data-ce-v4-all-projects]",
  ));
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

function projectMonogram(value) {
  const words = String(value || "CE")
    .trim()
    .split(/\s+/u)
    .filter((word) => /[\p{L}\p{N}]/u.test(word));
  const firstGlyph = (word) => Array.from(word || "").find((glyph) => /[\p{L}\p{N}]/u.test(glyph)) || "";
  const letters = words.length > 1
    ? words.slice(0, 2).map(firstGlyph)
    : Array.from(words[0] || "CE").filter((glyph) => /[\p{L}\p{N}]/u.test(glyph)).slice(0, 2);
  return letters.join("").toLocaleUpperCase("ru-RU") || "CE";
}

function projectSelectionRoute(project) {
  const nextAction = normalizeProjectNextAction(project?.nextAction, project?.id);
  if (nextAction?.route) return nextAction.route;
  const query = new URLSearchParams({ project_id: project.id });
  if (project.rootFolderId) query.set("folder", project.rootFolderId);
  return `/workspace/board?${query.toString()}`;
}

function workspaceCanCreateProject() {
  const workspaceRole = String(
    q(".workspace-shell[data-workspace-role]")?.dataset.workspaceRole || "",
  ).trim().toLowerCase();
  return ["owner", "admin", "producer"].includes(workspaceRole);
}

function syncProjectSwitcher(snapshot = projectFlowSnapshot()) {
  const { trigger, menu } = projectMenuParts();
  if (!trigger || !menu) return;
  const canCreateProject = workspaceCanCreateProject();
  const triggerName = q("[data-ce-v4-project-name]", trigger);
  const triggerMeta = q("[data-ce-v4-project-meta]", trigger);
  if (triggerName) triggerName.textContent = snapshot.id ? snapshot.name : "Выбрать проект";
  if (triggerMeta) triggerMeta.textContent = snapshot.id ? "Проект" : "Рабочее пространство";
  trigger.setAttribute("aria-label", snapshot.id ? `Текущий проект: ${snapshot.name}. Выбрать другой` : "Выбрать проект");
  trigger.title = snapshot.id ? `Проект: ${snapshot.name}` : "Выбрать проект";

  const signature = JSON.stringify({
    id: snapshot.id,
    nextAction: snapshot.nextAction?.route || "",
    canCreateProject,
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
  if (canCreateProject) {
    const createProject = create(
      "button",
      "ce-v4-project-menu__command ce-v4-project-menu__create",
      "＋ Новый проект",
    );
    createProject.type = "button";
    createProject.dataset.ceV4CreateProject = "true";
    createProject.setAttribute("role", "menuitem");
    fragment.append(createProject);
  }
  const allProjects = create(
    "button",
    "ce-v4-project-menu__command ce-v4-project-menu__all",
    "Все проекты",
  );
  allProjects.type = "button";
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
  identity.append(create("span", "ce-v4-menubar__mark", "CE"));
  const identityCopy = create("span");
  const activeApp = create("strong", "", "Рабочий стол");
  activeApp.dataset.ceV4ActiveApp = "true";
  identityCopy.append(activeApp, create("small", "", "ContentEngine"));
  identity.append(identityCopy);
  const start = create("div", "ce-v4-menubar__start");
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
  start.append(identity, projectSwitcher);

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
  notifications.setAttribute("aria-haspopup", "dialog");
  notifications.setAttribute("aria-controls", "ce-v4-notification-panel");
  notifications.setAttribute("aria-expanded", "false");
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
    if (target?.closest("[data-ce-v4-create-project]")) {
      event.preventDefault();
      closeProjectMenu();
      navigate("/workspace/home?view=new", { preserveProject: false });
      return;
    }
    if (target?.closest("[data-ce-v4-all-projects]")) {
      event.preventDefault();
      closeProjectMenu();
      navigate("/workspace/home?view=projects", { preserveProject: false });
      return;
    }
    if (target?.closest("[data-ce-v4-refresh]")) refreshWorkspace();
    if (target?.closest("[data-ce-v4-fullscreen]")) void toggleFullscreen();
    const notificationControl = target?.closest("[data-ce-v4-notifications]");
    if (notificationControl) toggleNotificationCenter(notificationControl);
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

function closeDockMore(restoreFocus = false) {
  const dock = runtime.dock;
  const menu = q("[data-ce-v4-dock-more-menu]", dock);
  const trigger = q("[data-ce-v4-dock-more]", dock);
  if (!menu || !trigger) return;
  const wasOpen = !menu.hidden;
  menu.hidden = true;
  trigger.setAttribute("aria-expanded", "false");
  if (restoreFocus && wasOpen) safeFocus(trigger);
}

function toggleDockMore() {
  const menu = q("[data-ce-v4-dock-more-menu]", runtime.dock);
  const trigger = q("[data-ce-v4-dock-more]", runtime.dock);
  if (!menu || !trigger || trigger.hidden) return;
  const opening = menu.hidden;
  closeProjectMenu();
  closeToolsMenu();
  menu.hidden = !opening;
  trigger.setAttribute("aria-expanded", String(opening));
  if (opening) safeFocus(q("[data-ce-v4-more-key]", menu));
}

function validDockScope(rawScope) {
  const organizationId = String(rawScope?.organizationId || "").trim().toLowerCase();
  const userId = String(rawScope?.userId || "").trim().toLowerCase();
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
  return uuid.test(organizationId) && uuid.test(userId)
    ? Object.freeze({ organizationId, userId })
    : null;
}

function currentDockScope() {
  const bridge = window.ContentEngineWorkspaceRuntime;
  if (!bridge || typeof bridge.getDockScope !== "function") return null;
  try { return validDockScope(bridge.getDockScope()); }
  catch { return null; }
}

function dockScopesEqual(left, right) {
  return Boolean(
    left
    && right
    && left.organizationId === right.organizationId
    && left.userId === right.userId,
  );
}

function dockPreferenceStorageKey(scope) {
  return `${DOCK_PREFERENCE_STORAGE_PREFIX}.${WORKSPACE_DOCK_PREFERENCE_VERSION}`
    + `:${encodeURIComponent(scope.organizationId)}:${encodeURIComponent(scope.userId)}`;
}

function resetDockPreferenceRuntime() {
  window.clearTimeout(runtime.dockPinZoneTimer);
  runtime.dockPinZoneTimer = 0;
  runtime.dockScope = null;
  runtime.dockStorageKey = "";
  runtime.dockPreferenceLoaded = false;
  runtime.dockStorageWrites = 0;
  runtime.dockResolvedTargets.clear();
  runtime.dockLibraryCandidates.clear();
  runtime.dockResolutionEpoch += 1;
  runtime.dockDraggedFile = null;
  runtime.dockState = createWorkspaceDockState(
    { order: DOCK_CANONICAL_ORDER, shortcuts: {} },
    { internalPolicy: DOCK_INTERNAL_POLICY },
  );
}

function loadDockPreferenceForAuthenticatedScope(options = {}) {
  const scope = currentDockScope();
  if (!scope) {
    if (runtime.dockPreferenceLoaded || runtime.dockScope) resetDockPreferenceRuntime();
    if (runtime.dock) runtime.dock.dataset.ceV4DockPersistence = "identity-required";
    return false;
  }
  if (
    options.force !== true
    && runtime.dockPreferenceLoaded
    && dockScopesEqual(scope, runtime.dockScope)
  ) return true;

  const storageKey = dockPreferenceStorageKey(scope);
  let rawPreference = "";
  let storageReadable = true;
  try { rawPreference = window.localStorage.getItem(storageKey) || ""; }
  catch { storageReadable = false; }
  if (runtime.dockPreferenceLoaded || runtime.dockDraggedFile) resetDockPinZone();
  runtime.dockScope = scope;
  runtime.dockStorageKey = storageKey;
  runtime.dockPreferenceLoaded = true;
  runtime.dockStorageWrites = 0;
  runtime.dockResolvedTargets.clear();
  runtime.dockLibraryCandidates.clear();
  runtime.dockResolutionEpoch += 1;
  runtime.dockState = createWorkspaceDockState(rawPreference, {
    scope,
    internalPolicy: DOCK_INTERNAL_POLICY,
  });
  if (runtime.dock) {
    runtime.dock.dataset.ceV4DockPersistence = storageReadable
      ? "authenticated-local"
      : "storage-unavailable";
    runtime.dock.dataset.ceV4DockStorageWrites = "0";
  }
  return true;
}

function persistDockPreference(effect) {
  if (effect?.type !== "persist_preference" || effect.reason !== "edit_done") return false;
  const scope = currentDockScope();
  if (
    !runtime.dockPreferenceLoaded
    || !dockScopesEqual(scope, runtime.dockScope)
    || runtime.dockStorageKey !== dockPreferenceStorageKey(scope)
    || !dockScopesEqual(effect.preference?.scope, scope)
  ) return false;
  try {
    window.localStorage.setItem(runtime.dockStorageKey, JSON.stringify(effect.preference));
    runtime.dockStorageWrites += 1;
    if (runtime.dock) {
      runtime.dock.dataset.ceV4DockPersistence = "authenticated-local";
      runtime.dock.dataset.ceV4DockStorageWrites = String(runtime.dockStorageWrites);
    }
    return true;
  } catch {
    if (runtime.dock) runtime.dock.dataset.ceV4DockPersistence = "storage-unavailable";
    return false;
  }
}

function dockShortcutDescriptor(key) {
  return runtime.dockState?.preference?.shortcuts?.[String(key || "")] || null;
}

function dockShortcutLabel(descriptor, resolution = null) {
  const fallback = descriptor?.type === "file_shortcut"
    ? "Файл"
    : descriptor?.type === "internal_link_shortcut"
      ? "Ссылка ContentEngine"
      : "Ссылка";
  if (resolution?.label) return String(resolution.label).slice(0, 160);
  if (descriptor?.labelOverride) return String(descriptor.labelOverride).slice(0, 160);
  if (descriptor?.type === "external_link_shortcut") {
    try { return new URL(descriptor.canonicalTarget).hostname; }
    catch { return fallback; }
  }
  return fallback;
}

function dockShortcutIcon(descriptor, resolution = null) {
  if (descriptor?.type === "external_link_shortcut") return "ce-dock-settings";
  if (resolution?.targetType === "folder" || resolution?.targetType === "project") return "ce-dock-finder";
  return "ce-dock-finder";
}

function dockRecord(key) {
  const standard = DOCK_ITEMS.find((item) => item.key === key);
  if (standard) return standard;
  const descriptor = dockShortcutDescriptor(key);
  if (!descriptor) return null;
  const resolution = runtime.dockResolvedTargets.get(descriptor.shortcutId) || null;
  return {
    key: descriptor.shortcutId,
    kind: "shortcut",
    shortcutType: descriptor.type,
    descriptor,
    label: dockShortcutLabel(descriptor, resolution),
    description: descriptor.type === "external_link_shortcut"
      ? "Внешняя HTTPS‑ссылка"
      : resolution?.state === "live" ? "Проверено по текущим правам" : "Проверка доступа при открытии",
    dockIcon: dockShortcutIcon(descriptor, resolution),
  };
}

function activeDockKey(route = window.location.hash || routePath()) {
  const path = routeParts(route).path;
  if (path === "/workspace/home") return workspaceDesktopRoute(route) ? "" : "finder";
  if (["/workspace/board", "/workspace/media"].includes(path)) return "finder";
  if (["/workspace/stats", "/workspace/payouts"].includes(path)) return "results";
  if (path === "/workspace/research") return "research";
  if (path === "/workspace/ai") return "ai";
  if (path === "/workspace/generation") return "create";
  if (path === "/workspace/review") return "review";
  if (path === "/workspace/placement") return "publish";
  if (["/workspace/tasks", "/workspace/work"].includes(path)) return "processes";
  if (path === "/workspace/team") return "settings";
  return "";
}

function dockDestination(record, snapshot = projectFlowSnapshot()) {
  if (!record || record.kind === "trash") return "";
  const context = projectContext(snapshot);
  if (record.key === "finder") {
    return snapshot.id ? projectRoute("/workspace/board", context) : "/workspace/home?view=projects";
  }
  const stage = stageForRoute(record.route, snapshot);
  return stage?.destination || projectRoute(record.route, context);
}

function dockPresentationCapacity() {
  const narrowFootprint = window.innerWidth <= 360 ? 44 : 55;
  const chromeAllowance = window.innerWidth <= 360 ? 28 : 36;
  const measured = Math.floor(Math.max(0, window.innerWidth - chromeAllowance) / narrowFootprint);
  return Math.max(6, Math.min(DOCK_CANONICAL_ORDER.length, measured));
}

function dockUnavailableMessage(record) {
  return `${record?.label || "Раздел"}: раздел недоступен для вашей роли. Обратитесь к владельцу рабочего пространства.`;
}

function runningDockAppIds(activeKey = activeDockKey()) {
  const running = new Set(
    [...runtime.windowRoutes.values()].map((route) => activeDockKey(route)).filter(Boolean),
  );
  if (activeKey) running.add(activeKey);
  return [...running];
}

function dockEditing() {
  return Boolean(runtime.dockState?.editSession);
}

function dockItemLocked(key, activeKey = activeDockKey()) {
  const item = runtime.dockState?.catalog?.[key];
  return Boolean(item?.protected || item?.kind === "trash" || key === activeKey);
}

function dockItemNode(key) {
  return qa("[data-ce-v4-dock-key]", runtime.dock)
    .find((node) => node.dataset.ceV4DockKey === key) || null;
}

function createDockShortcutNode(descriptor) {
  const button = create("button", "ce-v4-dock__item ce-v4-dock__shortcut");
  button.type = "button";
  button.dataset.ceV4DockKey = descriptor.shortcutId;
  button.dataset.ceV4DockShortcut = descriptor.type;
  const tooltip = create("span", "ce-v4-dock__tooltip");
  const tile = create("span", "ce-v4-dock__tile");
  const glyph = create("span", "ce-v4-dock__shortcut-icon");
  glyph.dataset.ceV4DockShortcutIcon = "true";
  const editMarker = create("span", "ce-v4-dock__edit-marker");
  editMarker.dataset.ceV4DockEditMarker = "true";
  editMarker.hidden = true;
  editMarker.setAttribute("aria-hidden", "true");
  tile.append(glyph, editMarker);
  const label = create("span", "ce-v4-dock__label");
  label.dataset.ceV4DockShortcutLabel = "true";
  const running = create("i", "ce-v4-dock__running");
  running.setAttribute("aria-hidden", "true");
  button.append(tooltip, tile, label, running);
  return button;
}

function ensureDynamicDockItems() {
  const glass = q(".ce-v4-dock__glass", runtime.dock);
  if (!glass) return;
  const shortcuts = runtime.dockState?.preference?.shortcuts || {};
  qa("[data-ce-v4-dock-shortcut]", glass).forEach((node) => {
    if (!shortcuts[String(node.dataset.ceV4DockKey || "")]) node.remove();
  });
  Object.values(shortcuts).forEach((descriptor) => {
    if (dockItemNode(descriptor.shortcutId)) return;
    glass.append(createDockShortcutNode(descriptor));
  });
}

function resolveDockShortcutDescriptor(descriptor, options = {}) {
  if (!descriptor?.shortcutId) return;
  if (descriptor.type === "external_link_shortcut") {
    const normalized = normalizeWorkspaceDockExternalTarget(descriptor.canonicalTarget);
    runtime.dockResolvedTargets.set(descriptor.shortcutId, normalized.ok
      ? Object.freeze({
        state: "live",
        targetType: "external",
        label: descriptor.labelOverride || normalized.hostname,
        canonicalTarget: normalized.canonicalTarget,
      })
      : Object.freeze({ state: "unavailable", reason: normalized.error }));
    return;
  }
  if (!runtime.dockPreferenceLoaded || !dockScopesEqual(runtime.dockScope, currentDockScope())) return;
  if (runtime.dockResolvedTargets.has(descriptor.shortcutId) && options.force !== true) return;
  const bridge = window.ContentEngineWorkspaceRuntime;
  if (typeof bridge?.resolveDockShortcut !== "function") {
    runtime.dockResolvedTargets.set(
      descriptor.shortcutId,
      Object.freeze({ state: "unavailable", reason: "dock_resolver_unavailable" }),
    );
    return;
  }
  const epoch = runtime.dockResolutionEpoch;
  const scope = runtime.dockScope;
  runtime.dockResolvedTargets.set(descriptor.shortcutId, Object.freeze({ state: "checking" }));
  void Promise.resolve(bridge.resolveDockShortcut(Object.freeze({ ...descriptor })))
    .then((resolution) => {
      if (
        epoch !== runtime.dockResolutionEpoch
        || !dockScopesEqual(scope, currentDockScope())
        || !dockShortcutDescriptor(descriptor.shortcutId)
      ) return;
      const state = ["live", "trashed", "unavailable"].includes(resolution?.state)
        ? resolution.state
        : "unavailable";
      runtime.dockResolvedTargets.set(
        descriptor.shortcutId,
        Object.freeze({ ...resolution, state }),
      );
      updateDock();
    })
    .catch(() => {
      if (epoch !== runtime.dockResolutionEpoch || !dockShortcutDescriptor(descriptor.shortcutId)) return;
      runtime.dockResolvedTargets.set(
        descriptor.shortcutId,
        Object.freeze({ state: "unavailable", reason: "dock_resolver_failed" }),
      );
      updateDock();
    });
}

function refreshDockShortcutResolutions(options = {}) {
  Object.values(runtime.dockState?.preference?.shortcuts || {})
    .forEach((descriptor) => resolveDockShortcutDescriptor(descriptor, options));
}

function activeDockShortcutId(activeKey) {
  const finder = window.ContentEngineFinderV4;
  const quickLookObjectId = typeof finder?.quickLookObjectId === "function"
    ? finder.quickLookObjectId()
    : "";
  const finderSelectionObjectId = typeof finder?.selectedObjectId === "function"
    ? finder.selectedObjectId()
    : "";
  const route = routeParts(window.location.hash || routePath());
  const folderId = String(route.query.get("folder") || "").trim();
  return selectWorkspaceDockShortcut(runtime.dockState, {
    activeAppId: activeKey,
    quickLookObjectId,
    finderSelectionObjectId,
    activeInternalTarget: folderId ? `contentengine://folder/${encodeURIComponent(folderId)}` : "",
  }, DOCK_INTERNAL_POLICY) || "";
}

function announceDock(message) {
  const live = q("[data-ce-v4-dock-live]", runtime.dock);
  if (!live) return;
  live.textContent = "";
  window.requestAnimationFrame(() => {
    if (live.isConnected) live.textContent = String(message || "");
  });
}

function consumeDockTransition(action) {
  const next = workspaceDockReducer(runtime.dockState, action);
  const effects = Array.isArray(next.effects) ? [...next.effects] : [];
  runtime.dockState = { ...next, effects: [] };
  effects.forEach((effect) => {
    if (effect.type === "persist_preference") {
      effect.persisted = persistDockPreference(effect);
    }
    if (effect.type === "suppress_open") runtime.dockSuppressClickUntil = performance.now() + 260;
    if (effect.type === "announce") {
      const label = dockRecord(effect.key)?.label || "Элемент Dock";
      const messages = {
        dock_item_taken: `${label} взято для перемещения`,
        dock_item_dropped: `${label} размещено`,
        dock_item_moved: `${label} перемещено`,
        dock_move_cancelled: "Перемещение отменено",
      };
      announceDock(messages[effect.messageKey] || label);
    }
  });
  return effects;
}

function dockShortcutDedupeKey(descriptor) {
  if (descriptor?.type === "file_shortcut") return `file:${descriptor.objectId}`;
  if (descriptor?.type === "internal_link_shortcut") return `internal:${descriptor.canonicalTarget}`;
  if (descriptor?.type === "external_link_shortcut") return `external:${descriptor.canonicalTarget}`;
  return "";
}

function dockPinnedShortcutForCandidate(descriptor) {
  const key = dockShortcutDedupeKey(descriptor);
  if (!key) return null;
  return Object.values(runtime.dockState.preference.shortcuts)
    .find((item) => dockShortcutDedupeKey(item) === key) || null;
}

function dockLibrarySnapshot() {
  const bridge = window.ContentEngineWorkspaceRuntime;
  if (typeof bridge?.getDockLibrarySnapshot !== "function") return null;
  try {
    const snapshot = bridge.getDockLibrarySnapshot();
    return snapshot && dockScopesEqual(snapshot.scope, runtime.dockScope) ? snapshot : null;
  } catch { return null; }
}

function dockLibraryDescriptors(tab, snapshot) {
  if (!snapshot) return [];
  if (tab === "projects") {
    return [
      ...(snapshot.projects || []).map((project) => ({
        type: "internal_link_shortcut",
        canonicalTarget: `contentengine://folder/${encodeURIComponent(project.rootFolderId || project.id)}`,
        sectionKey: project.id,
        labelOverride: project.name,
        libraryKind: "project",
      })),
      ...(snapshot.folders || []).filter((folder) => folder.kind !== "project").map((folder) => ({
        type: "internal_link_shortcut",
        canonicalTarget: `contentengine://folder/${encodeURIComponent(folder.id)}`,
        sectionKey: folder.projectId,
        labelOverride: folder.name,
        libraryKind: "folder",
      })),
    ];
  }
  if (tab === "files") {
    return (snapshot.files || []).map((file) => ({
      type: "file_shortcut",
      objectId: file.id,
      sectionKey: file.projectId,
      labelOverride: file.name,
      libraryKind: "file",
    }));
  }
  return [];
}

function allocateDockShortcutDescriptor(candidate) {
  const shortcutId = allocateWorkspaceDockShortcutId(
    candidate.type,
    Object.keys(runtime.dockState.preference.shortcuts),
    [nativeDockGestureId()],
  );
  if (!shortcutId) return null;
  const descriptor = {
    shortcutId,
    type: candidate.type,
    createdAt: new Date().toISOString(),
  };
  ["objectId", "canonicalTarget", "labelOverride", "sectionKey"].forEach((field) => {
    if (candidate[field]) descriptor[field] = candidate[field];
  });
  return descriptor;
}

function addDockLibraryCandidate(candidate, options = {}) {
  if (!dockEditing() || !candidate) return false;
  const pinned = dockPinnedShortcutForCandidate(candidate);
  if (pinned) {
    consumeDockTransition({ type: "unpin", key: pinned.shortcutId });
  } else {
    const shortcut = allocateDockShortcutDescriptor(candidate);
    if (!shortcut) return false;
    consumeDockTransition({ type: "addShortcut", shortcut });
    if (runtime.dockState.issues.length) {
      showSystemToast(
        runtime.dockState.issues.includes("shortcut_limit_exceeded")
          ? "Достигнут лимит ярлыков этого типа в Dock."
          : "Этот ярлык уже добавлен или не прошёл проверку.",
        "warning",
      );
      return false;
    }
    resolveDockShortcutDescriptor(shortcut);
  }
  updateDock();
  renderDockLibraryContent();
  if (options.announce !== false) announceDock(pinned ? "Ярлык убран из Dock" : "Ярлык добавлен в Dock");
  return true;
}

function renderDockLibraryContent() {
  const library = runtime.dockLibrary;
  if (!library?.isConnected) return;
  const selected = String(library.dataset.ceV4DockLibraryActiveTab || "apps");
  const tabs = qa("[data-ce-v4-dock-library-tab]", library);
  tabs.forEach((tab) => {
    const active = tab.dataset.ceV4DockLibraryTab === selected;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  const panel = q("[data-ce-v4-dock-library-panel]", library);
  if (!panel) return;
  panel.setAttribute("aria-labelledby", `ce-v4-dock-library-tab-${selected}`);
  panel.replaceChildren();
  if (selected !== "apps") {
    const snapshot = dockLibrarySnapshot();
    if (selected === "smart") {
      const empty = create("div", "ce-v4-dock-library__pending");
      empty.append(
        create("strong", "", "Умные папки пока не поддерживают точный ярлык"),
        create("p", "", "Dock не создаёт вымышленные папки: здесь появятся только объекты из авторитетного каталога."),
      );
      panel.append(empty);
      return;
    }
    const candidates = dockLibraryDescriptors(selected, snapshot);
    runtime.dockLibraryCandidates.clear();
    const grid = create("div", "ce-v4-dock-library__grid");
    candidates.forEach((candidate, index) => {
      const candidateKey = `candidate-${index}`;
      runtime.dockLibraryCandidates.set(candidateKey, Object.freeze({ ...candidate }));
      const pinned = dockPinnedShortcutForCandidate(candidate);
      const button = create("button", "ce-v4-dock-library__card");
      button.type = "button";
      button.dataset.ceV4DockLibraryCandidate = candidateKey;
      button.classList.toggle("is-pinned", Boolean(pinned));
      const tile = create("span", "ce-v4-dock-library__tile");
      tile.append(dockIcon("ce-dock-finder", 42));
      const marker = create(
        "span",
        `ce-v4-dock-library__marker ${pinned ? "is-remove" : "is-add"}`,
        pinned ? "−" : "+",
      );
      marker.setAttribute("aria-hidden", "true");
      tile.append(marker);
      const kind = candidate.libraryKind === "project"
        ? "Проект"
        : candidate.libraryKind === "folder" ? "Папка" : "Файл";
      const state = pinned ? "Убрать из Dock" : "Добавить в Dock";
      const copy = create("span", "ce-v4-dock-library__copy");
      copy.append(create("strong", "", candidate.labelOverride || kind), create("small", "", `${kind} · ${state}`));
      button.setAttribute("aria-label", `${candidate.labelOverride || kind}. ${state}`);
      button.append(tile, copy);
      grid.append(button);
    });
    if (candidates.length) panel.append(grid);
    else {
      const empty = create("div", "ce-v4-dock-library__pending");
      empty.append(
        create("strong", "", snapshot ? "В текущем контексте нет доступных объектов" : "Нужен подтверждённый проект"),
        create("p", "", "Откройте проект: Library покажет только реально доступные объекты с текущими правами."),
      );
      panel.append(empty);
    }
    if (selected === "files") {
      const form = create("form", "ce-v4-dock-library__external");
      form.dataset.ceV4DockExternalForm = "true";
      const label = create("label", "", "Безопасная HTTPS‑ссылка");
      const input = create("input");
      input.type = "url";
      input.required = true;
      input.placeholder = "https://example.com/page";
      input.autocomplete = "url";
      input.dataset.ceV4DockExternalUrl = "true";
      label.append(input);
      const submit = create("button", "ce-v4-dock-editor__button", "Добавить ссылку");
      submit.type = "submit";
      form.append(label, submit);
      panel.append(form);
    }
    return;
  }

  const activeKey = activeDockKey();
  const order = runtime.dockState.preference.order;
  const grid = create("div", "ce-v4-dock-library__grid");
  DOCK_APPS.forEach((record) => {
    const pinned = order.includes(record.key);
    const locked = dockItemLocked(record.key, activeKey);
    const authorized = routeIsAuthorized(record.route);
    const unavailableToAdd = !authorized && !pinned;
    const button = create("button", "ce-v4-dock-library__card");
    button.type = "button";
    button.dataset.ceV4DockLibraryApp = record.key;
    button.disabled = locked || unavailableToAdd;
    button.classList.toggle("is-pinned", pinned);
    button.classList.toggle("is-locked", locked);
    button.classList.toggle("is-unavailable", !authorized);
    const tile = create("span", "ce-v4-dock-library__tile");
    tile.append(dockIcon(record.dockIcon, 42));
    const marker = create(
      "span",
      `ce-v4-dock-library__marker ${locked ? "is-lock" : pinned ? "is-remove" : "is-add"}`,
      locked ? "•" : pinned ? "−" : "+",
    );
    marker.setAttribute("aria-hidden", "true");
    tile.append(marker);
    const copy = create("span", "ce-v4-dock-library__copy");
    const state = locked
      ? record.key === activeKey ? "Активное приложение закреплено" : "Обязательный элемент"
      : !authorized ? "Недоступно для вашей роли"
      : pinned ? "Убрать из Dock" : "Добавить в Dock";
    copy.append(create("strong", "", record.label), create("small", "", state));
    button.setAttribute("aria-label", `${record.label}. ${state}`);
    button.append(tile, copy);
    grid.append(button);
  });
  panel.append(grid);
}

function setDockLibraryTab(key, options = {}) {
  const library = runtime.dockLibrary;
  const tabs = qa("[data-ce-v4-dock-library-tab]", library);
  const selected = tabs.find((tab) => tab.dataset.ceV4DockLibraryTab === key) || tabs[0];
  if (!selected) return;
  library.dataset.ceV4DockLibraryActiveTab = selected.dataset.ceV4DockLibraryTab;
  renderDockLibraryContent();
  if (options.focus) safeFocus(selected);
}

function closeDockLibrary(restoreFocus = false) {
  const library = runtime.dockLibrary;
  if (!library || library.hidden) return false;
  library.hidden = true;
  library.setAttribute("aria-hidden", "true");
  if (restoreFocus) safeFocus(runtime.dockLibraryReturnFocus);
  runtime.dockLibraryReturnFocus = null;
  return true;
}

function openDockLibrary(opener) {
  const library = runtime.dockLibrary;
  if (!dockEditing() || !library) return false;
  closeDockMore();
  runtime.dockLibraryReturnFocus = opener instanceof HTMLElement
    ? opener
    : q("[data-ce-v4-dock-library-open]", runtime.dockEditor);
  library.hidden = false;
  library.removeAttribute("aria-hidden");
  setDockLibraryTab("apps");
  safeFocus(q('[data-ce-v4-dock-library-tab][aria-selected="true"]', library));
  return true;
}

function syncDockEditorPresentation() {
  const dock = runtime.dock;
  const editor = runtime.dockEditor;
  const trigger = q("[data-ce-v4-dock-edit-entry]", dock);
  if (!dock || !editor || !trigger) return;
  const editing = dockEditing();
  dock.classList.toggle("is-editing", editing);
  dock.dataset.ceV4DockEditing = String(editing);
  if (!runtime.dockPreferenceLoaded) {
    dock.dataset.ceV4DockPersistence = currentDockScope()
      ? "loading"
      : "identity-required";
  }
  editor.hidden = !editing;
  trigger.setAttribute("aria-expanded", String(editing));
  const activeKey = activeDockKey();
  qa("[data-ce-v4-dock-key]", dock).forEach((item) => {
    const key = String(item.dataset.ceV4DockKey || "");
    const record = dockRecord(key);
    const marker = q("[data-ce-v4-dock-edit-marker]", item);
    if (!record || !marker) return;
    const locked = dockItemLocked(key, activeKey);
    marker.hidden = !editing;
    marker.classList.toggle("is-lock", locked);
    marker.classList.toggle("is-remove", !locked);
    marker.textContent = locked ? "•" : "−";
    marker.title = locked
      ? key === activeKey ? "Активное приложение остаётся в Dock" : "Обязательный элемент Dock"
      : `Убрать ${record.label} из Dock`;
    item.classList.toggle("is-edit-locked", editing && locked);
    item.classList.toggle("is-edit-removable", editing && !locked);
    item.setAttribute("aria-grabbed", String(Boolean(runtime.dockState.keyboardMove?.key === key)));
    if (editing) {
      item.setAttribute(
        "aria-label",
        locked
          ? `${record.label}. Закреплено: ${marker.title}`
          : `${record.label}. Нажмите, чтобы убрать; пробел — взять или положить при перемещении`,
      );
    }
  });
  if (editing && !runtime.dockLibrary?.hidden) renderDockLibraryContent();
}

function openDockEditor(options = {}) {
  const trigger = q("[data-ce-v4-dock-edit-entry]", runtime.dock);
  if (!trigger) return false;
  if (!loadDockPreferenceForAuthenticatedScope()) {
    showSystemToast("Настройка Dock доступна после подтверждения профиля и организации.", "warning");
    return false;
  }
  closeDockMore();
  closeProjectMenu();
  closeToolsMenu();
  if (!dockEditing()) runtime.dockEditorReturnFocus = trigger;
  consumeDockTransition({ type: "enterEdit" });
  updateDock();
  if (options.focus !== false) safeFocus(q("[data-ce-v4-dock-library-open]", runtime.dockEditor));
  return true;
}

function cancelDockEditor(options = {}) {
  if (!dockEditing()) return false;
  closeDockLibrary(false);
  const effects = consumeDockTransition({ type: "cancelEdit" });
  runtime.dock.dataset.ceV4DockLastCancelEffects = String(effects.length);
  updateDock();
  announceDock("Изменения отменены. Dock возвращён к состоянию до настройки.");
  if (options.restoreFocus !== false) safeFocus(runtime.dockEditorReturnFocus);
  runtime.dockEditorReturnFocus = null;
  return true;
}

function finishDockEditor(options = {}) {
  if (!dockEditing()) return false;
  closeDockLibrary(false);
  const effects = consumeDockTransition({ type: "doneEdit" });
  runtime.dockLastCommitEffects = effects;
  runtime.dock.dataset.ceV4DockLastDoneEffects = String(effects.length);
  updateDock();
  const persistEffect = effects.find((effect) => effect.type === "persist_preference");
  if (persistEffect) {
    showSystemToast(
      persistEffect.persisted
        ? "Dock сохранён для текущего профиля и организации."
        : "Dock применён, но браузер не разрешил сохранить настройку.",
      persistEffect.persisted ? "success" : "warning",
    );
  }
  if (options.restoreFocus !== false) safeFocus(runtime.dockEditorReturnFocus);
  runtime.dockEditorReturnFocus = null;
  return true;
}

function mutateDockApp(key, options = {}) {
  const record = dockRecord(key);
  if (!dockEditing() || !record || record.kind === "trash") return false;
  if (dockItemLocked(key)) {
    announceDock(`${record.label} остаётся в Dock`);
    return false;
  }
  const pinned = runtime.dockState.preference.order.includes(key);
  const action = pinned ? { type: "unpin", key } : { type: "pinApp", key };
  consumeDockTransition(action);
  updateDock();
  const focus = options.focus === "library"
    ? q(`[data-ce-v4-dock-library-app="${key}"]`, runtime.dockLibrary)
    : dockItemNode(key);
  window.requestAnimationFrame(() => safeFocus(focus));
  return true;
}

function beginDockPointerReorder(event) {
  if (event.button !== 0) return;
  const item = event.target instanceof Element ? event.target.closest("[data-ce-v4-dock-key]") : null;
  const key = String(item?.dataset.ceV4DockKey || "");
  const pendingEdit = !dockEditing();
  if (!(item instanceof HTMLElement) || (!pendingEdit && dockItemLocked(key))) return;
  runtime.dockPointerReorder = {
    pointerId: event.pointerId,
    key,
    startX: event.clientX,
    startY: event.clientY,
    movement: 0,
    pendingEdit,
    targetKey: "",
    targetHalf: "before",
  };
  try { item.setPointerCapture?.(event.pointerId); }
  catch { /* Synthetic and cancelled pointers may not be capturable. */ }
}

function moveDockPointerReorder(event) {
  const drag = runtime.dockPointerReorder;
  if (!drag || drag.pointerId !== event.pointerId) return;
  drag.movement = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
  if (drag.movement < 6) return;
  if (drag.pendingEdit) {
    if (!openDockEditor({ focus: false }) || dockItemLocked(drag.key)) {
      runtime.dockPointerReorder = null;
      return;
    }
    drag.pendingEdit = false;
  }
  const candidates = qa("[data-ce-v4-dock-key]", runtime.dock)
    .filter((item) => !item.hidden && item.dataset.ceV4DockKey !== drag.key);
  let target = null;
  let distance = Infinity;
  candidates.forEach((candidate) => {
    const rect = candidate.getBoundingClientRect();
    const candidateDistance = Math.abs(event.clientX - (rect.left + rect.width / 2));
    if (candidateDistance < distance) {
      distance = candidateDistance;
      target = candidate;
    }
  });
  candidates.forEach((candidate) => candidate.classList.toggle("is-reorder-target", candidate === target));
  if (target) {
    const rect = target.getBoundingClientRect();
    drag.targetKey = target.dataset.ceV4DockKey;
    drag.targetHalf = event.clientX >= rect.left + rect.width / 2 ? "after" : "before";
  }
  event.preventDefault();
}

function finishDockPointerReorder(event, cancelled = false) {
  const drag = runtime.dockPointerReorder;
  if (!drag || drag.pointerId !== event.pointerId) return;
  runtime.dockPointerReorder = null;
  qa("[data-ce-v4-dock-key]", runtime.dock)
    .forEach((item) => item.classList.remove("is-reorder-target"));
  if (cancelled || drag.movement < 6 || !drag.targetKey) return;
  consumeDockTransition({
    type: "pointerReorder",
    sourceKey: drag.key,
    targetKey: drag.targetKey,
    targetHalf: drag.targetHalf,
    movementPx: drag.movement,
  });
  updateDock();
  window.requestAnimationFrame(() => safeFocus(dockItemNode(drag.key)));
  event.preventDefault();
}

function dockContextAction(rawKey, action) {
  const key = String(rawKey || "");
  if (action === "customize") return openDockEditor();
  if (!key || !openDockEditor({ focus: false })) return false;
  if (action === "remove") return mutateDockApp(key);
  if (!["left", "right"].includes(action) || dockItemLocked(key)) return false;
  const order = runtime.dockState.preference.order;
  const index = order.indexOf(key);
  const targetIndex = index + (action === "left" ? -1 : 1);
  const targetKey = order[targetIndex];
  if (index < 0 || !targetKey || targetKey === "trash") return false;
  consumeDockTransition({
    type: "pointerReorder",
    sourceKey: key,
    targetKey,
    targetHalf: action === "left" ? "before" : "after",
    movementPx: 12,
  });
  updateDock();
  return true;
}

function handleDockEditorKeydown(event) {
  if (!dockEditing()) return;
  const item = event.target instanceof Element ? event.target.closest("[data-ce-v4-dock-key]") : null;
  const key = String(item?.dataset.ceV4DockKey || "");
  if (!(item instanceof HTMLElement) || dockItemLocked(key)) return;
  let action = null;
  if (event.code === "Space") action = { type: "keyboardTakeOrDrop", key };
  else if (runtime.dockState.keyboardMove?.key === key && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
    action = { type: "keyboardMove", command: event.key };
  } else if (!runtime.dockState.keyboardMove && ["Delete", "Backspace"].includes(event.key)) {
    action = { type: "keyboardDelete", key };
  }
  if (!action) return;
  event.preventDefault();
  event.stopPropagation();
  consumeDockTransition(action);
  updateDock();
  window.requestAnimationFrame(() => safeFocus(dockItemNode(key)));
}

function handleDockLibraryKeydown(event) {
  const tab = event.target instanceof Element
    ? event.target.closest("[data-ce-v4-dock-library-tab]")
    : null;
  if (!(tab instanceof HTMLElement)) return;
  const tabs = qa("[data-ce-v4-dock-library-tab]", runtime.dockLibrary);
  const index = tabs.indexOf(tab);
  if (index < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? tabs.length - 1
      : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  setDockLibraryTab(tabs[next].dataset.ceV4DockLibraryTab, { focus: true });
}

function syncDockPresentation(activeKey = activeDockKey()) {
  const dock = runtime.dock;
  if (!dock) return null;
  ensureDynamicDockItems();
  const selectedShortcutId = activeDockShortcutId(activeKey);
  const presentation = computeWorkspaceDockPresentation(runtime.dockState, {
    activeAppId: activeKey,
    runningAppIds: runningDockAppIds(activeKey),
    selectedShortcutId,
    capacity: dockPresentationCapacity(),
  });
  runtime.dockPresentation = presentation;
  dock.dataset.ceV4DockCapacity = String(presentation.capacity);
  dock.dataset.ceV4DockVisibleCount = String(presentation.visibleKeys.length);
  dock.dataset.ceV4DockOverflow = String(presentation.overflow);
  const visibleKeys = new Set(presentation.visibleKeys.filter((key) => key !== "__more__"));
  qa("[data-ce-v4-dock-key]", dock).forEach((item) => {
    item.hidden = !visibleKeys.has(String(item.dataset.ceV4DockKey || ""));
  });

  const more = q("[data-ce-v4-dock-more]", dock);
  const menu = q("[data-ce-v4-dock-more-menu]", dock);
  const separator = q(".ce-v4-trash-separator", dock);
  const glass = q(".ce-v4-dock__glass", dock);
  if (!more || !menu) return presentation;
  more.hidden = !presentation.overflow;
  if (separator) separator.hidden = !visibleKeys.has("trash");
  if (!presentation.overflow) closeDockMore();

  if (glass) {
    const orderedKeys = [...runtime.dockState.preference.order];
    if (activeKey && !orderedKeys.includes(activeKey)) {
      const trashIndex = orderedKeys.indexOf("trash");
      orderedKeys.splice(trashIndex < 0 ? orderedKeys.length : trashIndex, 0, activeKey);
    }
    const orderedSet = new Set(orderedKeys);
    orderedKeys.forEach((key) => {
      if (key === "trash") {
        const pinZone = q("[data-ce-v4-dock-pin-zone]", glass);
        if (pinZone) glass.append(pinZone);
        glass.append(more);
        if (separator) glass.append(separator);
      }
      const node = dockItemNode(key);
      if (node) glass.append(node);
    });
    qa("[data-ce-v4-dock-key]", glass)
      .filter((node) => !orderedSet.has(String(node.dataset.ceV4DockKey || "")))
      .forEach((node) => glass.append(node));
    glass.append(menu);
  }

  const signature = JSON.stringify([
    dockEditing(),
    presentation.hiddenKeys,
    runtime.dockState.preference.order,
    [...runtime.dockResolvedTargets.entries()].map(([key, value]) => [key, value?.state, value?.label]),
  ]);
  if (menu.dataset.ceV4DockSignature === signature) return presentation;
  const fragment = document.createDocumentFragment();
  presentation.hiddenKeys.forEach((key) => {
    const record = dockRecord(key);
    if (!record || record.kind === "trash") return;
    const button = create("button", "ce-v4-dock-more-menu__item");
    button.type = "button";
    button.dataset.ceV4MoreKey = record.key;
    button.setAttribute("role", "menuitem");
    const resolution = runtime.dockResolvedTargets.get(key);
    const authorized = record.kind === "shortcut"
      ? record.shortcutType === "external_link_shortcut" || resolution?.state === "live"
      : routeIsAuthorized(record.route);
    if (!authorized) button.setAttribute("aria-disabled", "true");
    button.append(dockIcon(record.dockIcon, 30));
    const copy = create("span", "ce-v4-dock-more-menu__copy");
    copy.append(
      create("strong", "", record.label),
      create(
        "small",
        "",
        dockEditing()
          ? "Нажмите, чтобы убрать из Dock"
          : authorized ? record.description : "Недоступно для вашей роли",
      ),
    );
    button.append(copy);
    fragment.append(button);
  });
  menu.replaceChildren(fragment);
  menu.dataset.ceV4DockSignature = signature;
  return presentation;
}

function animateDockLaunch(node) {
  if (!(node instanceof HTMLElement)) return;
  node.classList.remove("is-launching");
  window.requestAnimationFrame(() => {
    if (!node.isConnected) return;
    node.classList.add("is-launching");
    window.setTimeout(() => node.classList.remove("is-launching"), 420);
  });
}

function nativeDockGestureId() {
  try { return window.crypto.randomUUID(); }
  catch { return ""; }
}

function openExternalDockShortcut(descriptor) {
  const normalized = normalizeWorkspaceDockExternalTarget(descriptor?.canonicalTarget);
  if (!normalized.ok) {
    showSystemToast("Ссылка заблокирована политикой безопасности Dock.", "warning");
    return false;
  }
  const opened = window.open(normalized.canonicalTarget, "_blank", "noopener,noreferrer");
  if (opened) opened.opener = null;
  else showSystemToast("Браузер заблокировал открытие ссылки в новой вкладке.", "warning");
  return Boolean(opened);
}

async function executeDynamicDockShortcut(record, event) {
  const descriptor = record?.descriptor;
  if (!descriptor) return false;
  const scope = currentDockScope();
  if (!scope || !dockScopesEqual(scope, runtime.dockScope)) {
    showSystemToast("Контекст профиля изменился. Dock будет загружен заново.", "warning");
    loadDockPreferenceForAuthenticatedScope({ force: true });
    updateDock();
    return false;
  }
  if (descriptor.type === "external_link_shortcut") return openExternalDockShortcut(descriptor);
  const bridge = window.ContentEngineWorkspaceRuntime;
  const gestureId = nativeDockGestureId();
  if (
    !gestureId
    || typeof bridge?.resolveDockShortcut !== "function"
    || typeof bridge?.executeDockCommand !== "function"
  ) {
    showSystemToast("Не удалось подтвердить текущий профиль для открытия ярлыка.", "warning");
    return false;
  }
  const node = event?.target instanceof Element
    ? event.target.closest("[data-ce-v4-dock-key], [data-ce-v4-more-key]")
    : dockItemNode(descriptor.shortcutId);
  node?.setAttribute?.("aria-busy", "true");
  let resolution;
  try { resolution = await bridge.resolveDockShortcut(Object.freeze({ ...descriptor })); }
  catch { resolution = null; }
  node?.removeAttribute?.("aria-busy");
  if (
    !dockScopesEqual(scope, currentDockScope())
    || dockShortcutDescriptor(descriptor.shortcutId) !== descriptor
    || resolution?.state !== "live"
  ) {
    runtime.dockResolvedTargets.set(
      descriptor.shortcutId,
      Object.freeze({ ...(resolution || {}), state: "unavailable" }),
    );
    updateDock();
    showSystemToast("Ярлык недоступен по текущим правам или объект больше не существует.", "warning");
    return false;
  }
  runtime.dockResolvedTargets.set(descriptor.shortcutId, Object.freeze({ ...resolution }));
  const target = descriptor.type === "file_shortcut"
    ? Object.freeze({ kind: "object", objectRef: Object.freeze({ type: "file", id: descriptor.objectId }) })
    : Object.freeze({ kind: "internal", canonicalTarget: descriptor.canonicalTarget });
  const actionKey = descriptor.type === "file_shortcut" ? "object.open" : "internal-target.open";
  const command = resolveWorkspaceCommand({
    gestureId,
    source: "dock",
    actionKey,
    target,
    authority: resolution.authority,
  });
  if (!command.ok) {
    showSystemToast("Dock не выполнил команду: проверка доступа не завершена.", "warning");
    return false;
  }
  animateDockLaunch(node || dockItemNode(descriptor.shortcutId));
  const executed = bridge.executeDockCommand(command.envelope, {
    scope,
    projectId: descriptor.sectionKey,
  }) === true;
  if (!executed) showSystemToast("Команда Dock отменена: контекст рабочего пространства изменился.", "warning");
  return executed;
}

function activateDockKey(rawKey, event) {
  const key = String(rawKey || "");
  const record = dockRecord(key);
  if (!record) return false;
  event?.preventDefault?.();
  if (dockEditing()) {
    if (performance.now() < runtime.dockSuppressClickUntil) return false;
    closeDockMore();
    return mutateDockApp(key);
  }
  if (record.kind === "trash") return false;
  if (record.kind === "shortcut") {
    closeDockMore();
    void executeDynamicDockShortcut(record, event);
    return true;
  }
  closeDockMore();
  if (!routeIsAuthorized(record.route)) {
    showSystemToast(dockUnavailableMessage(record), "warning");
    return false;
  }

  const snapshot = projectFlowSnapshot();
  const destination = dockDestination(record, snapshot);
  const opensProjectCatalog = routeParts(destination).path === "/workspace/home";
  if (workspaceRouteRequiresProject(destination) && !snapshot.id) {
    explainProjectRequired(destination);
    return false;
  }
  const stage = stageForRoute(record.route, snapshot);
  if (stageLocked(stage, snapshot)) {
    openRequiredStage(stage, snapshot);
    return false;
  }
  if (
    destination
    && routeMatches(routePath(), routeParts(destination).path)
    && runtime.windowShell?.classList.contains("is-minimized")
  ) {
    restoreWorkspaceWindow({ focus: true });
    return false;
  }
  if (!destination || (!opensProjectCatalog && routeMatches(routePath(), routeParts(destination).path))) {
    return false;
  }
  const clicked = event?.target instanceof Element
    ? event.target.closest("[data-ce-v4-dock-key], [data-ce-v4-more-key]")
    : null;
  animateDockLaunch(clicked || q(`[data-ce-v4-dock-key="${key}"]`, runtime.dock));
  navigatePrimaryRoute(destination);
  return true;
}

function dockDraggedFileFromEvent(event) {
  const handle = event.target instanceof Element
    ? event.target.closest("[data-workspace-drag-item]")
    : null;
  const card = handle?.closest(".workspace-board__item");
  const objectId = String(handle?.dataset.entityId || card?.dataset.entityId || "").trim().toLowerCase();
  const entityType = String(handle?.dataset.entityType || card?.dataset.entityType || "").trim().toLowerCase();
  const projectId = String(
    card?.closest("[data-project-id]")?.dataset.projectId
      || q("[data-project-flow-root]")?.dataset.projectId
      || projectFlowSnapshot().id
      || "",
  ).trim().toLowerCase();
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
  if (entityType !== "media" || !uuid.test(objectId) || !uuid.test(projectId)) return null;
  return Object.freeze({
    objectId,
    projectId,
    labelOverride: String(q(".workspace-board__item-copy strong", card)?.textContent || "Файл")
      .trim().slice(0, 160) || "Файл",
  });
}

async function pinDockFileCandidate(rawCandidate, options = {}) {
  const candidate = rawCandidate && typeof rawCandidate === "object" ? rawCandidate : {};
  const scope = currentDockScope();
  const gestureId = String(options.gestureId || nativeDockGestureId());
  const bridge = window.ContentEngineWorkspaceRuntime;
  if (
    !scope
    || !gestureId
    || typeof bridge?.resolveDockShortcut !== "function"
  ) return false;
  const descriptor = {
    shortcutId: `file-shortcut:${gestureId}`,
    type: "file_shortcut",
    objectId: String(candidate.objectId || "").trim().toLowerCase(),
    sectionKey: String(candidate.projectId || "").trim().toLowerCase(),
    labelOverride: String(candidate.labelOverride || "Файл").trim().slice(0, 160) || "Файл",
    createdAt: new Date().toISOString(),
  };
  let resolution;
  try { resolution = await bridge.resolveDockShortcut(Object.freeze({ ...descriptor })); }
  catch { return false; }
  if (!dockScopesEqual(scope, currentDockScope()) || resolution?.state !== "live") {
    showSystemToast("Файл нельзя закрепить: текущий доступ не подтверждён.", "warning");
    return false;
  }
  const command = resolveWorkspaceCommand({
    gestureId,
    source: ["quick_look", "finder", "toolbar"].includes(options.source) ? options.source : "dock",
    actionKey: "dock.pin-file-shortcut",
    target: { kind: "object", objectRef: { type: "file", id: descriptor.objectId } },
    authority: resolution.authority,
  });
  if (!command.ok || !loadDockPreferenceForAuthenticatedScope()) return false;
  if (!dockEditing() && !openDockEditor({ focus: false })) return false;
  return addDockLibraryCandidate({
    type: descriptor.type,
    objectId: descriptor.objectId,
    sectionKey: descriptor.sectionKey,
    labelOverride: resolution.label || descriptor.labelOverride,
    libraryKind: "file",
  });
}

function resetDockPinZone(options = {}) {
  window.clearTimeout(runtime.dockPinZoneTimer);
  runtime.dockPinZoneTimer = 0;
  if (options.stateReset !== false) consumeDockTransition({ type: "pinZoneLeave" });
  const zone = q("[data-ce-v4-dock-pin-zone]", runtime.dock);
  if (zone) {
    zone.hidden = true;
    zone.classList.remove("is-arming", "is-ready");
    zone.dataset.ceV4DockPinPhase = "idle";
  }
  runtime.dockDraggedFile = null;
}

function handleDockFileDragStart(event) {
  const dragged = dockDraggedFileFromEvent(event);
  if (!dragged || !loadDockPreferenceForAuthenticatedScope()) return;
  runtime.dockDraggedFile = dragged;
  consumeDockTransition({ type: "pinZoneLeave" });
  const zone = q("[data-ce-v4-dock-pin-zone]", runtime.dock);
  if (zone) {
    zone.hidden = false;
    zone.dataset.ceV4DockPinPhase = "idle";
  }
}

function handleDockPinZoneEnter(event) {
  const dragged = runtime.dockDraggedFile;
  if (!dragged) return;
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "link";
  const now = performance.now();
  consumeDockTransition({
    type: "pinZoneEnter",
    surface: "empty_shelf",
    dragKind: "file",
    objectId: dragged.objectId,
    now,
  });
  const zone = event.currentTarget;
  zone.classList.add("is-arming");
  zone.dataset.ceV4DockPinPhase = runtime.dockState.pinZone.phase;
  window.clearTimeout(runtime.dockPinZoneTimer);
  runtime.dockPinZoneTimer = window.setTimeout(() => {
    consumeDockTransition({
      type: "pinZoneTick",
      now: performance.now(),
    });
    if (runtime.dockState.pinZone.phase === "ready" && zone.isConnected) {
      zone.classList.remove("is-arming");
      zone.classList.add("is-ready");
      zone.dataset.ceV4DockPinPhase = "ready";
      announceDock("Отпустите файл, чтобы добавить ярлык в Dock");
    }
  }, WORKSPACE_DOCK_PIN_HOVER_MS);
}

function handleDockPinZoneLeave(event) {
  if (event.currentTarget.contains(event.relatedTarget)) return;
  window.clearTimeout(runtime.dockPinZoneTimer);
  runtime.dockPinZoneTimer = 0;
  consumeDockTransition({ type: "pinZoneLeave" });
  event.currentTarget.classList.remove("is-arming", "is-ready");
  event.currentTarget.dataset.ceV4DockPinPhase = "idle";
}

function handleDockPinZoneDrop(event) {
  const dragged = runtime.dockDraggedFile;
  if (!dragged) return;
  event.preventDefault();
  event.stopPropagation();
  const effects = consumeDockTransition({
    type: "pinZoneDrop",
    surface: "pin_zone",
    dragKind: "file",
    objectId: dragged.objectId,
  });
  const classification = effects.find((effect) => effect.type === "dock_drop_intent")
    ?.classification || { kind: "none" };
  const gestureId = nativeDockGestureId();
  resetDockPinZone({ stateReset: false });
  if (classification.kind !== "pin_shortcut" || !gestureId) return;
  void pinDockFileCandidate(dragged, { source: "dock", gestureId });
}

function ensureDock() {
  if (runtime.dock?.isConnected) return runtime.dock;
  const dock = create("nav", "ce-v4-dock");
  dock.setAttribute("aria-label", "Основные разделы ContentEngine");
  const glass = create("div", "ce-v4-dock__glass");
  DOCK_APPS.forEach((item, index) => {
    const link = create("a", "ce-v4-dock__item");
    const shortcut = `⌥${Math.min(index + 1, 9)}`;
    link.href = `#${item.route}`;
    link.dataset.ceV4DockKey = item.key;
    link.dataset.ceV4Route = item.route;
    link.setAttribute("aria-label", `${item.label}. ${item.description}. ${shortcut}`);
    link.title = `${item.label} — ${item.description}`;
    link.append(create("span", "ce-v4-dock__tooltip", `${item.label} · ${item.description} · ${shortcut}`));
    const tile = create("span", "ce-v4-dock__tile");
    const count = create("span", "ce-v4-dock__count", "0");
    count.dataset.ceV4DockCount = "true";
    count.hidden = true;
    count.setAttribute("aria-hidden", "true");
    const editMarker = create("span", "ce-v4-dock__edit-marker");
    editMarker.dataset.ceV4DockEditMarker = "true";
    editMarker.hidden = true;
    editMarker.setAttribute("aria-hidden", "true");
    tile.append(dockIcon(item.dockIcon, 52), count, editMarker);
    const running = create("i", "ce-v4-dock__running");
    running.setAttribute("aria-hidden", "true");
    const stage = create("span", "ce-v4-dock__stage");
    stage.hidden = true;
    stage.setAttribute("aria-hidden", "true");
    link.append(tile, create("span", "ce-v4-dock__label", item.label), running, stage);
    glass.append(link);
  });
  const more = create("button", "ce-v4-dock__item ce-v4-dock__more");
  more.type = "button";
  more.hidden = true;
  more.dataset.ceV4DockMore = "true";
  more.setAttribute("aria-label", "Ещё разделы");
  more.setAttribute("aria-haspopup", "menu");
  more.setAttribute("aria-expanded", "false");
  more.title = "Ещё разделы";
  more.append(create("span", "ce-v4-dock__tooltip", "Ещё разделы"));
  const moreTile = create("span", "ce-v4-dock__tile ce-v4-dock__more-tile");
  moreTile.append(create("span", "ce-v4-dock__ellipsis", "•••"));
  more.append(moreTile, create("span", "ce-v4-dock__label", "Ещё"));
  const moreMenu = create("div", "ce-v4-dock-more-menu");
  moreMenu.hidden = true;
  moreMenu.dataset.ceV4DockMoreMenu = "true";
  moreMenu.setAttribute("role", "menu");
  moreMenu.setAttribute("aria-label", "Другие разделы ContentEngine");
  const pinZone = create("span", "ce-v4-dock__pin-zone", "Закрепить файл");
  pinZone.hidden = true;
  pinZone.dataset.ceV4DockPinZone = "true";
  pinZone.dataset.ceV4DockPinPhase = "idle";
  pinZone.setAttribute("aria-hidden", "true");
  const separator = create("span", "ce-v4-dock__separator ce-v4-trash-separator");
  const trash = create("button", "ce-v4-dock__item ce-v4-dock__utility ce-v4-trash-dock");
  trash.type = "button";
  trash.dataset.ceV4DockKey = "trash";
  trash.setAttribute("aria-label", "Корзина");
  trash.title = "Корзина — удалённые файлы и папки";
  trash.append(create("span", "ce-v4-dock__tooltip", "Корзина · удалённые файлы и папки"));
  const trashTile = create("span", "ce-v4-dock__tile");
  const trashEditMarker = create("span", "ce-v4-dock__edit-marker is-lock", "•");
  trashEditMarker.dataset.ceV4DockEditMarker = "true";
  trashEditMarker.hidden = true;
  trashEditMarker.setAttribute("aria-hidden", "true");
  trashTile.append(dockIcon("ce-dock-trash", 52), trashEditMarker);
  const trashRunning = create("i", "ce-v4-dock__running");
  trashRunning.setAttribute("aria-hidden", "true");
  trash.append(trashTile, create("span", "ce-v4-dock__label", "Корзина"), trashRunning);
  glass.append(pinZone, more, separator, trash, moreMenu);

  const editEntry = create("button", "ce-v4-dock__edit-entry", "Настроить Dock");
  editEntry.type = "button";
  editEntry.dataset.ceV4DockEditEntry = "true";
  editEntry.setAttribute("aria-expanded", "false");
  editEntry.setAttribute("aria-controls", "ce-v4-dock-editor");

  const editor = create("section", "ce-v4-dock-editor");
  editor.id = "ce-v4-dock-editor";
  editor.dataset.ceV4DockEditor = "true";
  editor.hidden = true;
  editor.setAttribute("aria-label", "Настройка Dock");
  const editorCopy = create("span", "ce-v4-dock-editor__copy");
  editorCopy.append(
    create("strong", "", "Настройка Dock"),
    create("small", "", "Изменения сохраняются только после «Готово» · «Отмена» вернёт точный снимок"),
  );
  const editorActions = create("span", "ce-v4-dock-editor__actions");
  const libraryOpen = create("button", "ce-v4-dock-editor__button", "Библиотека");
  libraryOpen.type = "button";
  libraryOpen.dataset.ceV4DockLibraryOpen = "true";
  libraryOpen.setAttribute("aria-haspopup", "dialog");
  const cancel = create("button", "ce-v4-dock-editor__button", "Отмена");
  cancel.type = "button";
  cancel.dataset.ceV4DockEditCancel = "true";
  const done = create("button", "ce-v4-dock-editor__button is-primary", "Готово");
  done.type = "button";
  done.dataset.ceV4DockEditDone = "true";
  editorActions.append(libraryOpen, cancel, done);
  editor.append(editorCopy, editorActions);

  const library = create("section", "ce-v4-dock-library");
  library.dataset.ceV4DockLibrary = "true";
  library.dataset.ceV4DockLibraryActiveTab = "apps";
  library.hidden = true;
  library.setAttribute("role", "dialog");
  library.setAttribute("aria-modal", "false");
  library.setAttribute("aria-hidden", "true");
  library.setAttribute("aria-labelledby", "ce-v4-dock-library-title");
  const libraryHeader = create("header", "ce-v4-dock-library__header");
  const libraryHeading = create("span");
  const libraryTitle = create("h2", "", "Добавить в Dock");
  libraryTitle.id = "ce-v4-dock-library-title";
  libraryHeading.append(
    libraryTitle,
    create("p", "", "Приложения можно добавить, убрать и затем разместить в нужном порядке."),
  );
  const libraryClose = create("button", "ce-v4-dock-library__close", "Закрыть");
  libraryClose.type = "button";
  libraryClose.dataset.ceV4DockLibraryClose = "true";
  libraryHeader.append(libraryHeading, libraryClose);
  const tablist = create("div", "ce-v4-dock-library__tabs");
  tablist.setAttribute("role", "tablist");
  tablist.setAttribute("aria-label", "Разделы библиотеки Dock");
  [
    ["apps", "Приложения"],
    ["projects", "Проекты"],
    ["smart", "Умные папки"],
    ["files", "Файлы и ссылки"],
  ].forEach(([key, label], index) => {
    const tab = create("button", "ce-v4-dock-library__tab", label);
    tab.type = "button";
    tab.dataset.ceV4DockLibraryTab = key;
    tab.id = `ce-v4-dock-library-tab-${key}`;
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-controls", "ce-v4-dock-library-panel");
    tab.setAttribute("aria-selected", String(index === 0));
    tab.tabIndex = index === 0 ? 0 : -1;
    tablist.append(tab);
  });
  const libraryPanel = create("div", "ce-v4-dock-library__panel");
  libraryPanel.id = "ce-v4-dock-library-panel";
  libraryPanel.dataset.ceV4DockLibraryPanel = "true";
  libraryPanel.setAttribute("role", "tabpanel");
  libraryPanel.setAttribute("aria-labelledby", "ce-v4-dock-library-tab-apps");
  library.append(libraryHeader, tablist, libraryPanel);
  const live = create("span", "ce-v4-dock__live");
  live.dataset.ceV4DockLive = "true";
  live.setAttribute("aria-live", "polite");
  live.setAttribute("aria-atomic", "true");
  dock.append(glass, editEntry, editor, library, live);
  document.body.append(dock);
  runtime.dock = dock;
  runtime.dockEditor = editor;
  runtime.dockLibrary = library;
  dock.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-dock-edit-entry]")) {
      event.preventDefault();
      openDockEditor();
      return;
    }
    const libraryOpenButton = target?.closest("[data-ce-v4-dock-library-open]");
    if (libraryOpenButton instanceof HTMLElement) {
      event.preventDefault();
      openDockLibrary(libraryOpenButton);
      return;
    }
    if (target?.closest("[data-ce-v4-dock-library-close]")) {
      event.preventDefault();
      closeDockLibrary(true);
      return;
    }
    const libraryTab = target?.closest("[data-ce-v4-dock-library-tab]")?.dataset.ceV4DockLibraryTab;
    if (libraryTab) {
      event.preventDefault();
      setDockLibraryTab(libraryTab, { focus: true });
      return;
    }
    const libraryApp = target?.closest("[data-ce-v4-dock-library-app]")?.dataset.ceV4DockLibraryApp;
    if (libraryApp) {
      event.preventDefault();
      mutateDockApp(libraryApp, { focus: "library" });
      return;
    }
    const libraryCandidate = target?.closest("[data-ce-v4-dock-library-candidate]")
      ?.dataset.ceV4DockLibraryCandidate;
    if (libraryCandidate) {
      event.preventDefault();
      addDockLibraryCandidate(runtime.dockLibraryCandidates.get(libraryCandidate));
      return;
    }
    if (target?.closest("[data-ce-v4-dock-edit-cancel]")) {
      event.preventDefault();
      cancelDockEditor();
      return;
    }
    if (target?.closest("[data-ce-v4-dock-edit-done]")) {
      event.preventDefault();
      finishDockEditor();
      return;
    }
    const overflowKey = target?.closest("[data-ce-v4-more-key]")?.dataset.ceV4MoreKey;
    if (overflowKey) {
      activateDockKey(overflowKey, event);
      return;
    }
    const item = target?.closest(".ce-v4-dock__item");
    if (!(item instanceof HTMLElement)) return;
    if (item.dataset.ceV4DockMore === "true") {
      event.preventDefault();
      event.stopPropagation();
      toggleDockMore();
      return;
    }
    activateDockKey(item.dataset.ceV4DockKey, event);
  });
  dock.addEventListener("pointerdown", beginDockPointerReorder);
  dock.addEventListener("pointermove", moveDockPointerReorder);
  dock.addEventListener("pointerup", (event) => finishDockPointerReorder(event));
  dock.addEventListener("pointercancel", (event) => finishDockPointerReorder(event, true));
  dock.addEventListener("keydown", handleDockEditorKeydown);
  library.addEventListener("keydown", handleDockLibraryKeydown);
  pinZone.addEventListener("dragenter", handleDockPinZoneEnter);
  pinZone.addEventListener("dragover", (event) => {
    if (!runtime.dockDraggedFile) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "link";
  });
  pinZone.addEventListener("dragleave", handleDockPinZoneLeave);
  pinZone.addEventListener("drop", handleDockPinZoneDrop);
  library.addEventListener("submit", (event) => {
    const form = event.target instanceof Element
      ? event.target.closest("[data-ce-v4-dock-external-form]")
      : null;
    if (!(form instanceof HTMLFormElement)) return;
    event.preventDefault();
    const input = q("[data-ce-v4-dock-external-url]", form);
    const normalized = normalizeWorkspaceDockExternalTarget(input?.value || "");
    if (!normalized.ok) {
      input?.setCustomValidity?.("Разрешена только безопасная HTTPS‑ссылка без секретов и токенов.");
      input?.reportValidity?.();
      return;
    }
    input.setCustomValidity("");
    if (addDockLibraryCandidate({
      type: "external_link_shortcut",
      canonicalTarget: normalized.canonicalTarget,
      labelOverride: normalized.hostname,
      libraryKind: "external",
    })) input.value = "";
  });
  return dock;
}

function updateDock() {
  const keyWindow = workspaceDesktopRoute() ? null : currentWorkspaceWindow();
  const keyWindowRoute = keyWindow ? routeForWorkspaceWindow(keyWindow) : "";
  const route = keyWindowRoute ? routeParts(keyWindowRoute).path : routePath();
  const snapshot = projectFlowSnapshot();
  const context = projectContext(snapshot);
  const activeKey = activeDockKey(keyWindowRoute || window.location.hash || route);
  refreshDockShortcutResolutions();
  const presentation = syncDockPresentation(activeKey);
  const presentationByKey = new Map((presentation?.items || []).map((item) => [item.key, item]));
  const shortcutIndexByKey = new Map(
    (presentation?.items || [])
      .map((item) => DOCK_APPS.find((candidate) => candidate.key === item.key))
      .filter((item) => item && routeIsAuthorized(item.route))
      .map((item, index) => [item.key, index]),
  );
  qa("[data-ce-v4-dock-key]", runtime.dock).forEach((item) => {
    const key = String(item.dataset.ceV4DockKey || "");
    const record = dockRecord(key);
    if (!record || record.kind === "trash") return;
    if (record.kind === "shortcut") {
      const resolution = runtime.dockResolvedTargets.get(key) || { state: "checking" };
      const presentationItem = presentationByKey.get(key);
      const selected = presentationItem?.selected === true;
      const available = record.shortcutType === "external_link_shortcut"
        ? resolution.state === "live"
        : resolution.state === "live";
      const stateText = resolution.state === "checking"
        ? "Проверяем текущий доступ"
        : resolution.state === "trashed"
          ? "Объект находится в Корзине"
          : available
            ? record.description
            : "Недоступно по текущим правам или состоянию объекта";
      const semantic = [record.label, stateText].filter(Boolean).join(" · ");
      item.classList.toggle("is-active", selected);
      item.classList.toggle("is-selected", selected);
      item.classList.toggle("is-running", false);
      item.classList.toggle("is-unavailable", !available);
      item.classList.toggle("is-checking", resolution.state === "checking");
      item.dataset.ceV4DockAvailability = available ? "available" : resolution.state;
      item.setAttribute("aria-current", selected ? "true" : "false");
      if (available) item.removeAttribute("aria-disabled");
      else item.setAttribute("aria-disabled", "true");
      const glyph = q("[data-ce-v4-dock-shortcut-icon]", item);
      if (glyph && glyph.dataset.ceV4DockIcon !== record.dockIcon) {
        glyph.dataset.ceV4DockIcon = record.dockIcon;
        glyph.replaceChildren(dockIcon(record.dockIcon, 52));
      }
      const label = q("[data-ce-v4-dock-shortcut-label]", item);
      if (label) label.textContent = record.label;
      const tooltip = q(".ce-v4-dock__tooltip", item);
      if (tooltip) tooltip.textContent = semantic;
      item.title = semantic;
      item.setAttribute("aria-label", semantic);
      return;
    }
    const authorized = routeIsAuthorized(record.route);
    const active = key === activeKey;
    const stage = stageForRoute(record.route, snapshot);
    const hasStageState = Boolean(snapshot.hasFlow && stage && stage.state !== "unknown");
    const locked = stageLocked(stage, snapshot);
    const projectRequired = workspaceRouteRequiresProject(record.route) && !snapshot.id && key !== "finder";
    const destination = dockDestination(record, snapshot) || projectRoute(record.route, context);
    item.href = `#${destination}`;
    item.classList.toggle("is-active", active);
    item.classList.toggle("is-running", Boolean(presentationByKey.get(key)?.running));
    item.classList.toggle("is-unavailable", !authorized);
    item.classList.toggle("is-project-required", projectRequired);
    ["done", "current", "blocked", "future"].forEach((state) => {
      item.classList.toggle(`is-stage-${state}`, hasStageState && stage.state === state);
    });
    item.dataset.ceV4StageState = hasStageState ? stage.state : "unknown";
    item.setAttribute("aria-current", active ? "page" : "false");
    if (locked || !authorized) item.setAttribute("aria-disabled", "true");
    else item.removeAttribute("aria-disabled");
    item.dataset.ceV4DockAvailability = authorized ? "available" : "role_blocked";
    const count = q("[data-ce-v4-dock-count]", item);
    const stageMarker = q(".ce-v4-dock__stage", item);
    if (stageMarker) {
      stageMarker.hidden = !hasStageState;
      stageMarker.dataset.state = hasStageState ? stage.state : "unknown";
    }
    const showCount = Boolean(stage && Number.isFinite(stage.count) && stage.count > 0);
    if (count) {
      count.hidden = !showCount;
      count.textContent = showCount ? (stage.count > 99 ? "99+" : String(stage.count)) : "0";
    }
    const stateText = !authorized
      ? "Недоступно для вашей роли"
      : projectRequired
      ? "Сначала выберите проект"
      : hasStageState ? PROJECT_STAGE_STATE_LABELS[stage.state] : "";
    const countText = stage && Number.isFinite(stage.count) ? `${stage.count} ${stage.countLabel}` : "";
    const reasonText = locked && stage.reason ? stage.reason : "";
    const shortcutIndex = shortcutIndexByKey.get(key);
    const shortcut = Number.isInteger(shortcutIndex) ? `⌥${shortcutIndex + 1}` : "";
    const semantic = !authorized
      ? dockUnavailableMessage(record)
      : projectRequired
      ? `${record?.label || "Раздел"} — нужен проект. Нажмите, чтобы перейти к выбору проекта`
      : [record?.label, stateText, countText, reasonText, record?.description, shortcut].filter(Boolean).join(" · ");
    const tooltip = q(".ce-v4-dock__tooltip", item);
    if (tooltip) tooltip.textContent = semantic;
    item.title = semantic;
    item.setAttribute("aria-label", semantic);
  });
  syncDockEditorPresentation();
}

function updateMenubar() {
  const snapshot = projectFlowSnapshot();
  const keyWindow = workspaceDesktopRoute() ? null : currentWorkspaceWindow();
  const keyRoute = keyWindow ? routeForWorkspaceWindow(keyWindow) : routePath();
  const chrome = routeRecord(routeParts(keyRoute).path);
  syncProjectSwitcher(snapshot);
  syncToolsMenu();
  const activeApp = q("[data-ce-v4-active-app]", runtime.menubar);
  if (activeApp) activeApp.textContent = chrome.appLabel || chrome.label;
  qa("[data-ce-v4-tools-route]", runtime.menubar).forEach((link) => {
    const active = routeParts(keyRoute).path === link.dataset.ceV4ToolsRoute;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const notifications = q("[data-ce-v4-notifications]", runtime.menubar);
  if (notifications) {
    const active = notificationCenterOpen();
    const unread = notificationUnreadCount();
    const destination = routeWithProject("/workspace/work?view=notifications", snapshot.id);
    notifications.dataset.ceV4Notifications = destination;
    notifications.classList.toggle("is-active", active);
    notifications.setAttribute("aria-pressed", String(active));
    notifications.setAttribute("aria-expanded", String(active));
    const badge = q("[data-ce-v4-notification-badge]", notifications);
    const badgeState = formatWorkspaceNotificationBadge(unread);
    if (badge) {
      badge.hidden = badgeState.hidden;
      badge.textContent = badgeState.text || "0";
    }
    const label = badgeState.ariaLabel;
    notifications.setAttribute("aria-label", label);
    notifications.title = label;
  }
}

function workspaceWindowRecord(route = routePath()) {
  const record = routeRecord(route);
  return {
    appLabel: record.appLabel || record.label || "ContentEngine",
    title: record.label || "Рабочее пространство",
    accent: record.accent || "#98A9BD",
    dockIcon: record.dockIcon || "ce-dock-finder",
  };
}

function windowControl(action, label, className) {
  const button = create("button", className);
  button.type = "button";
  button.dataset.ceV4WindowAction = action;
  button.setAttribute("aria-label", label);
  button.title = label;
  return button;
}

function workspaceWindowBounds() {
  const host = q("#main-content");
  return {
    width: Math.max(1, Math.round(host?.clientWidth || window.innerWidth || 1440)),
    height: Math.max(1, Math.round(host?.clientHeight || window.innerHeight || 900)),
  };
}

function workspaceWindowId(route = routePath(), snapshot = projectFlowSnapshot()) {
  const path = routeRecord(route).route.replace(/^\/workspace\//u, "") || "home";
  const project = String(snapshot?.id || "global").replace(/[^A-Za-z0-9_.:@-]/gu, "-");
  return `window:${path}:${project}`;
}

function defaultWorkspaceWindowGeometry(route = routePath()) {
  const bounds = workspaceWindowBounds();
  const canonical = routeRecord(route).route;
  const wideSurface = ["/workspace/board", "/workspace/review", "/workspace/stats", "/workspace/placement"]
    .includes(canonical);
  const horizontalInset = bounds.width >= 2400
    ? Math.max(180, Math.round(bounds.width * (wideSurface ? 0.08 : 0.11)))
    : bounds.width >= 1720
      ? Math.max(88, Math.round(bounds.width * (wideSurface ? 0.06 : 0.09)))
      : bounds.width >= 980
        ? Math.max(48, Math.round(bounds.width * (wideSurface ? 0.06 : 0.09)))
        : 16;
  const verticalInset = bounds.height >= 1080
    ? Math.max(54, Math.round(bounds.height * 0.05))
    : bounds.height >= 720
      ? Math.max(38, Math.round(bounds.height * 0.055))
      : 16;
  const routeMaximum = wideSurface ? 2480 : 2140;
  const width = Math.max(320, Math.min(routeMaximum, bounds.width - horizontalInset * 2));
  const height = Math.max(220, Math.min(1080, bounds.height - verticalInset * 2));
  const ordinal = runtime.windowManagerState.windows
    .filter((item) => item.spaceId === runtime.windowManagerState.activeSpaceId).length;
  const cascade = Math.min(ordinal, 5) * (bounds.width >= 1400 ? 42 : 30);
  return {
    position: {
      x: Math.max(0, Math.min(bounds.width - width, Math.round((bounds.width - width) / 2) + cascade)),
      y: Math.max(0, Math.min(bounds.height - height, Math.round((bounds.height - height) / 2) + cascade)),
    },
    size: { width, height },
  };
}

/*
 * A new window opens as a cascade ON TOP of the previous one: the ordinal
 * offset in defaultWorkspaceWindowGeometry keeps the older window's titlebar
 * peeking out at the top-left, so the operator sees where they came from.
 * The old auto-tiling of the first two windows (side-by-side 50/50) squeezed
 * both surfaces and was removed by the owner's decision on 27.08.2026 —
 * windows are never auto-arranged; their geometry belongs to the operator.
 */
function reduceWorkspaceWindow(action) {
  runtime.windowManagerState = workspaceWindowManagerReducer(runtime.windowManagerState, {
    ...action,
    bounds: workspaceWindowBounds(),
  });
  return runtime.windowManagerState;
}

function currentWorkspaceWindow(windowId = runtime.activeWindowId) {
  return runtime.windowManagerState.windows.find((item) => item.windowId === windowId) || null;
}

function topVisibleWorkspaceWindow(spaceId = runtime.windowManagerState.activeSpaceId, exceptWindowId = "") {
  return runtime.windowManagerState.windows
    .filter((item) => item.spaceId === spaceId && !item.minimized && item.windowId !== exceptWindowId)
    .sort((left, right) => right.zIndex - left.zIndex)[0] || null;
}

function visibleWorkspaceWindows(spaceId = runtime.windowManagerState.activeSpaceId) {
  return runtime.windowManagerState.windows
    .filter((item) => item.spaceId === spaceId && !item.minimized)
    .sort((left, right) => right.zIndex - left.zIndex);
}

function workspaceSnapGeometry(index = 0, count = 2) {
  const bounds = workspaceWindowBounds();
  const margin = 8;
  const gap = 12;
  const columns = Math.max(1, Math.min(3, Math.round(count) || 1));
  const slot = Math.max(0, Math.min(columns - 1, Math.round(index) || 0));
  const width = Math.max(280, Math.floor((bounds.width - margin * 2 - gap * (columns - 1)) / columns));
  const height = Math.max(220, bounds.height - margin * 2);
  return {
    position: { x: margin + slot * (width + gap), y: margin },
    size: { width, height },
  };
}

function workspaceSnapCandidate(event) {
  const host = q("#main-content");
  if (!host || window.innerWidth <= 850) return "";
  const rect = host.getBoundingClientRect();
  const withinX = event.clientX >= rect.left - WINDOW_SNAP_EDGE
    && event.clientX <= rect.right + WINDOW_SNAP_EDGE;
  const withinY = event.clientY >= rect.top - WINDOW_SNAP_EDGE
    && event.clientY <= rect.bottom + WINDOW_SNAP_EDGE;
  if (!withinX || !withinY) return "";
  if (event.clientY <= rect.top + WINDOW_SNAP_EDGE) return "top";
  if (event.clientX <= rect.left + WINDOW_SNAP_EDGE) return "left";
  if (event.clientX >= rect.right - WINDOW_SNAP_EDGE) return "right";
  return "";
}

function workspaceSnapPreviewGeometry(target) {
  if (target === "left") return workspaceSnapGeometry(0, 2);
  if (target === "right") return workspaceSnapGeometry(1, 2);
  if (target === "top") return workspaceSnapGeometry(0, 1);
  return null;
}

function clearWorkspaceSnapPreview() {
  runtime.windowSnapPreview?.remove();
  runtime.windowSnapPreview = null;
}

function showWorkspaceSnapPreview(target, windowId) {
  const geometry = workspaceSnapPreviewGeometry(target);
  const host = q("#main-content");
  if (!geometry || !host) {
    clearWorkspaceSnapPreview();
    return;
  }
  let preview = runtime.windowSnapPreview;
  if (!preview?.isConnected) {
    preview = create("div", "ce-v4-window-snap-preview");
    preview.setAttribute("aria-hidden", "true");
    host.append(preview);
    runtime.windowSnapPreview = preview;
  }
  const record = currentWorkspaceWindow(windowId);
  if (!record) {
    clearWorkspaceSnapPreview();
    return;
  }
  const accent = workspaceWindowRecord(routeParts(routeForWorkspaceWindow(record)).path).accent;
  preview.dataset.ceV4WindowSnapPreview = target;
  preview.style.setProperty("--ce-v4-window-accent", accent);
  preview.style.left = `${geometry.position.x}px`;
  preview.style.top = `${geometry.position.y}px`;
  preview.style.width = `${geometry.size.width}px`;
  preview.style.height = `${geometry.size.height}px`;
}

function rememberWorkspaceWindowGeometry(windowRecord, details = {}) {
  const previous = runtime.windowSnapMemory.get(windowRecord.windowId);
  runtime.windowSnapMemory.set(windowRecord.windowId, {
    restore: previous?.restore || {
      position: { ...windowRecord.position },
      size: { ...windowRecord.size },
    },
    count: details.count,
    index: details.index,
    slot: details.slot,
  });
}

function applyWorkspaceSnap(windowId, details = {}, options = {}) {
  const windowRecord = currentWorkspaceWindow(windowId);
  if (!windowRecord) return false;
  const count = Math.max(1, Math.min(3, Math.round(details.count) || 2));
  const index = Math.max(0, Math.min(count - 1, Math.round(details.index) || 0));
  const geometry = workspaceSnapGeometry(index, count);
  rememberWorkspaceWindowGeometry(windowRecord, {
    count,
    index,
    slot: details.slot || (count === 2 ? (index ? "right" : "left") : `column-${index + 1}`),
  });
  reduceWorkspaceWindow({ type: "resize", windowId, size: geometry.size });
  reduceWorkspaceWindow({ type: "move", windowId, position: geometry.position });
  runtime.windowGeometryTouched.add(windowId);
  if (options.sync !== false) {
    focusWorkspaceWindowShell(windowId);
  }
  return true;
}

function tileWorkspaceWindows(anchorWindowId, count) {
  const anchor = currentWorkspaceWindow(anchorWindowId);
  if (!anchor) return false;
  const requested = Math.max(2, Math.min(3, Math.round(count) || 2));
  const candidates = visibleWorkspaceWindows(anchor.spaceId);
  const windows = [anchor, ...candidates.filter((item) => item.windowId !== anchorWindowId)].slice(0, requested);
  if (windows.length < requested) return false;
  windows.forEach((windowRecord, index) => {
    applyWorkspaceSnap(windowRecord.windowId, {
      count: requested,
      index,
      slot: requested === 2 ? (index ? "right" : "left") : `column-${index + 1}`,
    }, { sync: false });
  });
  focusWorkspaceWindowShell(anchorWindowId);
  return true;
}

function closeWorkspaceSnapAssist(options = {}) {
  const assist = runtime.windowSnapAssist;
  if (!assist) return;
  const windowId = assist.dataset.ceV4WindowSnapAssist || "";
  assist.remove();
  runtime.windowSnapAssist = null;
  if (options.restoreFocus) {
    const surface = runtime.windowSurfaces.get(windowId);
    window.requestAnimationFrame(() => surface?.focus?.({ preventScroll: true }));
  }
}

function snapLayoutGlyph(count) {
  const glyph = create("span", "ce-v4-window-snap-assist__glyph");
  glyph.setAttribute("aria-hidden", "true");
  for (let index = 0; index < count; index += 1) glyph.append(create("i"));
  return glyph;
}

function openWorkspaceSnapAssist(windowId) {
  const anchor = currentWorkspaceWindow(windowId);
  const host = q("#main-content");
  if (!anchor || !host) return false;
  closeWorkspaceSnapAssist();
  const visible = visibleWorkspaceWindows(anchor.spaceId);
  const canTileTwo = visible.length >= 2;
  const canTileThree = visible.length >= 3 && workspaceWindowBounds().width >= 1020;
  const assist = create("section", "ce-v4-window-snap-assist");
  assist.dataset.ceV4WindowSnapAssist = windowId;
  assist.setAttribute("role", "dialog");
  assist.setAttribute("aria-modal", "false");
  assist.setAttribute("aria-labelledby", "ce-v4-window-snap-assist-title");
  const copy = create("div", "ce-v4-window-snap-assist__copy");
  const title = create("strong", "", "Как закрепить окно?");
  title.id = "ce-v4-window-snap-assist-title";
  copy.append(title, create("small", "", "Выберите раскладку. Все окна останутся рабочими."));
  const close = windowControl("snap-close", "Закрыть выбор раскладки", "ce-v4-window-snap-assist__close");
  close.textContent = "×";
  const choices = create("div", "ce-v4-window-snap-assist__choices");
  [
    { key: "full", label: "Полный экран", count: 1, enabled: true },
    { key: "two", label: "2 окна", count: 2, enabled: canTileTwo },
    { key: "three", label: "3 окна", count: 3, enabled: canTileThree },
  ].forEach((option) => {
    const button = create("button", "ce-v4-window-snap-assist__choice");
    button.type = "button";
    button.dataset.ceV4WindowSnapLayout = option.key;
    button.disabled = !option.enabled;
    button.append(snapLayoutGlyph(option.count), create("span", "", option.label));
    if (!option.enabled) button.title = option.count === 3
      ? "Откройте три окна и используйте экран шире 1020 px"
      : "Сначала откройте второе окно";
    choices.append(button);
  });
  assist.append(copy, close, choices);
  assist.addEventListener("click", (event) => {
    const button = event.target instanceof Element
      ? event.target.closest("[data-ce-v4-window-snap-layout], [data-ce-v4-window-action='snap-close']")
      : null;
    if (!(button instanceof HTMLButtonElement)) return;
    const layout = button.dataset.ceV4WindowSnapLayout || "";
    if (layout === "full") toggleWorkspaceWindowZoom(true, windowId);
    else if (layout === "two") tileWorkspaceWindows(windowId, 2);
    else if (layout === "three") tileWorkspaceWindows(windowId, 3);
    closeWorkspaceSnapAssist({ restoreFocus: layout === "" });
  });
  host.append(assist);
  runtime.windowSnapAssist = assist;
  window.requestAnimationFrame(() => safeFocus(q(".ce-v4-window-snap-assist__choice:not(:disabled)", assist)));
  return true;
}

function reflowWorkspaceSnappedWindows() {
  if (!runtime.windowSnapMemory.size || workspaceDesktopRoute()) return false;
  let changed = false;
  runtime.windowSnapMemory.forEach((snap, windowId) => {
    const record = currentWorkspaceWindow(windowId);
    if (!record || record.zoomed || !Number.isInteger(snap?.count) || !Number.isInteger(snap?.index)) return;
    const geometry = workspaceSnapGeometry(snap.index, snap.count);
    reduceWorkspaceWindow({ type: "resize", windowId, size: geometry.size });
    reduceWorkspaceWindow({ type: "move", windowId, position: geometry.position });
    changed = true;
  });
  if (changed) syncWorkspaceWindowState();
  return changed;
}

function moveWorkspaceContent(content, destination) {
  if (!content || !destination || content.parentElement === destination) return;
  const focused = document.activeElement instanceof HTMLElement && content.contains(document.activeElement)
    ? document.activeElement
    : null;
  const selection = focused instanceof HTMLInputElement || focused instanceof HTMLTextAreaElement
    ? {
        start: focused.selectionStart,
        end: focused.selectionEnd,
        direction: focused.selectionDirection,
      }
    : null;
  destination.append(content);
  if (focused?.isConnected) {
    safeFocus(focused);
    if (selection && selection.start !== null && selection.end !== null) {
      focused.setSelectionRange(selection.start, selection.end, selection.direction || "none");
    }
  }
}

/*
 * The business renderer owns one live #workspace-content node. A stale legacy
 * scaffold must never remain behind a window because it would also leave a
 * second form and a second submit surface in the document. Prefer the node
 * already owned by the active window, otherwise the direct workspace node,
 * and remove only duplicate scaffolds without reading or replaying form data.
 */
function enforceSingleWorkspaceContent(host = q("#main-content")) {
  const contents = qa("#workspace-content");
  if (contents.length < 2) return contents[0] || null;
  const activeShell = runtime.windowShells.get(runtime.activeWindowId);
  const canonical = contents.find((node) => activeShell?.contains(node))
    || contents.find((node) => node.parentElement === host)
    || contents.find((node) => node.closest(".workspace-shell[data-workspace-section]"))
    || contents[0];
  contents.forEach((node) => {
    if (node === canonical) return;
    node.setAttribute("aria-hidden", "true");
    node.setAttribute("inert", "");
    node.remove();
  });
  return canonical;
}

function syncWorkspaceDesktopExposure(desktopMode) {
  const desktop = runtime.desktop;
  if (!desktop?.isConnected) return;
  desktop.hidden = !desktopMode;
  desktop.classList.toggle("is-obscured", !desktopMode);
  if (desktopMode) {
    desktop.removeAttribute("aria-hidden");
    desktop.removeAttribute("inert");
  } else {
    desktop.setAttribute("aria-hidden", "true");
    desktop.setAttribute("inert", "");
  }
}

function parkWorkspaceContent() {
  const host = q("#main-content");
  const content = q("#workspace-content");
  if (host && content && content.parentElement !== host) moveWorkspaceContent(content, host);
  return setWorkspaceContentParked(true);
}

function workspaceWindowProjectLabel(windowRecord, snapshot = projectFlowSnapshot()) {
  const projectId = String(windowRecord?.projectContext?.projectId || "");
  if (!projectId) return "Все проекты";
  return snapshot.projects.find((item) => item.id === projectId)?.name
    || (snapshot.id === projectId ? snapshot.name : "Проект");
}

function syncWorkspaceWindowChrome(shell, windowRecord) {
  if (!shell || !windowRecord) return;
  const rememberedRoute = routeForWorkspaceWindow(windowRecord);
  const path = routeParts(rememberedRoute).path;
  const record = workspaceWindowRecord(path);
  const projectLabel = workspaceWindowProjectLabel(windowRecord);
  shell.dataset.ceV4WindowId = windowRecord.windowId;
  shell.dataset.ceV4WindowRoute = path;
  shell.dataset.ceV4WindowApp = record.appLabel;
  shell.style.setProperty("--ce-v4-window-accent", record.accent);
  shell.setAttribute("aria-label", `${record.appLabel}: ${record.title}`);
  const glyph = q("[data-ce-v4-window-glyph] use", shell);
  if (glyph) {
    const href = `${DOCK_SPRITE}#${record.dockIcon}`;
    glyph.setAttribute("href", href);
    glyph.setAttributeNS(XLINK_NS, "href", href);
  }
  const title = q("[data-ce-v4-window-title]", shell);
  if (title) title.textContent = record.title;
  const app = q("[data-ce-v4-window-app]", shell);
  if (app) app.textContent = record.appLabel;
  const project = q("[data-ce-v4-window-project]", shell);
  if (project) {
    project.textContent = projectLabel;
    project.title = projectLabel === "Все проекты" ? "Проект не выбран" : `Проект: ${projectLabel}`;
  }
}

function workspaceWindowSnapshotKind(path) {
  if (path === "/workspace/board" || path === "/workspace/media") return "finder";
  if (path === "/workspace/stats" || path === "/workspace/payouts") return "stats";
  if (path === "/workspace/review") return "review";
  if (path === "/workspace/generation") return "generation";
  if (path === "/workspace/ai" || path === "/workspace/research") return "ai";
  return "default";
}

function workspaceWindowSnapshotText(node, limit = 96) {
  if (!(node instanceof Element) || !isVisible(node)) return "";
  if (node.matches("input,textarea,select,option,button,a,video,audio,iframe,canvas")) return "";
  if (node.closest('form,[hidden],[aria-hidden="true"],dialog,[role="dialog"]')) return "";
  if (node.querySelector("form,input,textarea,select,video,audio,iframe,canvas")) return "";
  return compact(node.textContent, limit);
}

function firstWorkspaceWindowSnapshotText(root, selectors, limit = 96) {
  for (const selector of selectors) {
    for (const node of qa(selector, root)) {
      const text = workspaceWindowSnapshotText(node, limit);
      if (text) return text;
    }
  }
  return "";
}

function workspaceWindowSnapshotPair(node) {
  if (!(node instanceof Element)) return null;
  if (node.matches("form,button,a,input,textarea,select") || node.querySelector("form,input,textarea,select")) return null;
  const primary = firstWorkspaceWindowSnapshotText(
    node,
    [":scope > h2", ":scope > h3", ":scope > h4", ":scope > strong", "h2", "h3", "h4", "strong", "b", "dt"],
    88,
  ) || workspaceWindowSnapshotText(node, 88);
  if (!primary) return null;
  const secondary = firstWorkspaceWindowSnapshotText(
    node,
    [":scope > p", ":scope > small", ":scope > span", "p", "small", "dd", ".muted"],
    112,
  );
  return Object.freeze({
    primary,
    secondary: secondary && secondary !== primary ? secondary : "",
  });
}

function workspaceWindowSnapshotItems(root, selectors, limit) {
  const seen = new Set();
  const items = [];
  selectors.forEach((selector) => {
    qa(selector, root).forEach((node) => {
      const item = workspaceWindowSnapshotPair(node);
      if (!item) return;
      const signature = `${item.primary}\n${item.secondary}`;
      if (seen.has(signature)) return;
      seen.add(signature);
      items.push(item);
    });
  });
  return items.slice(0, limit);
}

function workspaceWindowSnapshotSelectors(kind) {
  const routeSelectors = {
    finder: {
      metrics: [".workspace-board__collection-meta", ".workspace-board__sidebar-head"],
      rows: [".workspace-board__item-copy", ".workspace-board__folder-row"],
    },
    stats: {
      metrics: [".stats-live-card", ".metrics-grid > *", ".stats-overview-panel > article"],
      rows: [".stats-live-table tbody tr", ".results-ledger-panel tbody tr", ".stats-live-results article"],
    },
    review: {
      metrics: [".content-review-quality", ".content-review-compliance", ".content-review-breakdown"],
      rows: [".content-review-finding", ".content-review-recommendations li", ".content-review-strengths li"],
    },
    generation: {
      metrics: [".generation-launch-card", ".generation-product-identity", ".generation-cost"],
      rows: [".ce-v4-generation-guided__step", ".generation-strategy-spec-review__row", ".generation-model-record"],
    },
    ai: {
      metrics: [".ai-learning-signal-state", ".ai-learning-metric-grid > *", ".ai-learning-readiness-card"],
      rows: [".ai-learning-gap", ".ai-learning-teaching-card", ".ai-learning-source", ".fixture-card", ".fixture-tabs > span"],
    },
    default: {
      metrics: [".metrics-grid > *", ".card"],
      rows: ["tbody tr", "article", "li"],
    },
  };
  return routeSelectors[kind] || routeSelectors.default;
}

function captureWorkspaceWindowSnapshot(windowRecord, content) {
  if (!windowRecord?.windowId || !(content instanceof HTMLElement)) return false;
  const route = routeForWorkspaceWindow(windowRecord);
  const path = routeParts(route).path;
  if (windowRecord.windowId !== runtime.activeWindowId || path !== routePath() || workspaceDesktopRoute()) return false;
  const page = q(".ce-v4-page", content) || content.firstElementChild;
  if (!(page instanceof Element)) return false;
  if (q('[aria-busy="true"], [data-loading="true"], .is-loading, .skeleton', page)) return false;
  const kind = workspaceWindowSnapshotKind(path);
  const selectors = workspaceWindowSnapshotSelectors(kind);
  const observedTitle = firstWorkspaceWindowSnapshotText(
    page,
    [".workspace-board__collection-head h2", ".content-review-result__header h2", ".ai-learning-hero h1", ".generation-launch-card h2", "h1", "h2"],
    96,
  );
  const title = observedTitle || workspaceWindowRecord(path).title;
  const subtitle = firstWorkspaceWindowSnapshotText(
    page,
    [".workspace-board__sidebar-head p", ".content-review-result__header p", ".ai-learning-hero p", ".generation-launch-card p", "header p", ".eyebrow"],
    116,
  );
  const metrics = workspaceWindowSnapshotItems(page, selectors.metrics, 4).slice(0, 4);
  const rows = workspaceWindowSnapshotItems(page, selectors.rows, 5).slice(0, 5);
  if (!observedTitle && !subtitle && !metrics.length && !rows.length) return false;
  const snapshot = Object.freeze({
    route,
    actionKey: workspaceActionKey(route),
    kind,
    title,
    subtitle,
    metrics: Object.freeze(metrics),
    rows: Object.freeze(rows),
    capturedAt: Date.now(),
  });
  runtime.windowSnapshots.set(windowRecord.windowId, snapshot);
  return true;
}

function workspaceWindowSnapshotBlock(item, className = "ce-v4-window__snapshot-block") {
  const block = create("span", className);
  block.append(
    create("span", `${className}__label`, item?.primary || ""),
    create("span", `${className}__value`, item?.secondary || ""),
  );
  return block;
}

function renderWorkspaceWindowSnapshot(snapshot, record) {
  const preview = create("span", "ce-v4-window__snapshot");
  preview.dataset.ceV4WindowSnapshot = "true";
  preview.dataset.ceV4WindowSnapshotKind = snapshot?.kind || "default";
  preview.dataset.ceV4WindowSnapshotRoute = snapshot?.route || record.route;
  preview.dataset.ceV4WindowSnapshotState = snapshot ? "captured" : "fallback";
  preview.setAttribute("aria-hidden", "true");

  const head = create("span", "ce-v4-window__snapshot-head");
  head.append(
    create("span", "ce-v4-window__snapshot-kicker", snapshot?.subtitle || record.appLabel),
    create("span", "ce-v4-window__snapshot-title", snapshot?.title || record.title),
  );
  const layout = create("span", "ce-v4-window__snapshot-layout");
  const sidebar = create("span", "ce-v4-window__snapshot-sidebar");
  const main = create("span", "ce-v4-window__snapshot-main");
  const grid = create("span", "ce-v4-window__snapshot-grid");
  const inspector = create("span", "ce-v4-window__snapshot-inspector");
  const metrics = snapshot?.metrics || [];
  const rows = snapshot?.rows || [];

  (metrics.length ? metrics : [{}, {}, {}]).forEach((item) => {
    grid.append(workspaceWindowSnapshotBlock(item));
  });
  (rows.length ? rows : [{}, {}, {}, {}]).forEach((item) => {
    main.append(workspaceWindowSnapshotBlock(item, "ce-v4-window__snapshot-row"));
  });
  [...metrics.slice(0, 2), ...rows.slice(0, 1)].forEach((item) => {
    sidebar.append(workspaceWindowSnapshotBlock(item));
  });
  if (!sidebar.childElementCount) [{}, {}, {}].forEach((item) => sidebar.append(workspaceWindowSnapshotBlock(item)));
  [...rows.slice(0, 2), ...metrics.slice(0, 1)].forEach((item) => {
    inspector.append(workspaceWindowSnapshotBlock(item));
  });
  if (!inspector.childElementCount) [{}, {}, {}].forEach((item) => inspector.append(workspaceWindowSnapshotBlock(item)));
  main.prepend(grid);
  layout.append(sidebar, main, inspector);
  preview.append(head, layout);
  return preview;
}

function workspaceWindowPlaceholder(windowRecord) {
  const route = routeForWorkspaceWindow(windowRecord);
  const chrome = workspaceWindowRecord(routeParts(route).path);
  const snapshot = runtime.windowSnapshots.get(windowRecord.windowId) || null;
  const record = { ...chrome, route };
  const button = create(
    "button",
    `ce-v4-window__placeholder${snapshot ? " ce-v4-window__placeholder--snapshot" : ""}`,
  );
  button.type = "button";
  button.dataset.ceV4WindowAction = "focus";
  button.setAttribute(
    "aria-label",
    snapshot
      ? `Открыть окно «${chrome.title}». Показан последний статический вид`
      : `Открыть окно «${chrome.title}»`,
  );
  if (snapshot) {
    const cue = create("span", "ce-v4-window__snapshot-cue");
    cue.append(
      create("span", "ce-v4-window__snapshot-cue-mark", "↗"),
      create("span", "ce-v4-window__snapshot-cue-title", chrome.title),
      create("span", "ce-v4-window__snapshot-cue-copy", "Последний вид · откроется для продолжения"),
    );
    button.append(renderWorkspaceWindowSnapshot(snapshot, record), cue);
    return button;
  }
  button.append(
    dockIcon(chrome.dockIcon, 58),
    create("strong", "", chrome.title),
    create("small", "", "Нажмите, чтобы сделать окно активным"),
  );
  return button;
}

function syncWorkspaceWindowSnapshot(body, windowRecord) {
  if (!body || !windowRecord) return;
  const snapshot = runtime.windowSnapshots.get(windowRecord.windowId);
  const snapshotSignature = snapshot
    ? `${windowRecord.windowId}:${snapshot.route}:${snapshot.capturedAt}`
    : `${windowRecord.windowId}:${routeForWorkspaceWindow(windowRecord)}:fallback`;
  if (body.dataset.ceV4WindowSnapshotSignature === snapshotSignature && body.firstElementChild) return;
  body.replaceChildren(workspaceWindowPlaceholder(windowRecord));
  body.dataset.ceV4WindowSnapshotSignature = snapshotSignature;
}

function ensureWorkspaceWindowSurface(body, windowRecord) {
  if (!body || !windowRecord?.windowId) return null;
  let frame = runtime.windowSurfaces.get(windowRecord.windowId) || null;
  if (!(frame instanceof HTMLIFrameElement) || !frame.isConnected) {
    frame = create("iframe", "ce-v4-window__surface");
    frame.dataset.ceV4WindowSurface = "true";
    frame.dataset.ceV4WindowId = windowRecord.windowId;
    frame.dataset.ceV4WindowReady = "false";
    frame.loading = "eager";
    frame.referrerPolicy = "strict-origin";
    frame.tabIndex = 0;
    frame.src = createContentEngineEmbeddedWindowUrl(routeForWorkspaceWindow(windowRecord), {
      baseUrl: import.meta.url,
      windowId: windowRecord.windowId,
    });
    frame.addEventListener("load", () => {
      frame.dataset.ceV4WindowLoaded = "true";
    });
    frame.addEventListener("error", () => {
      frame.dataset.ceV4WindowReady = "false";
      frame.dataset.ceV4WindowFailed = "true";
    });
    runtime.windowSurfaces.set(windowRecord.windowId, frame);
  }
  const chrome = workspaceWindowRecord(routeParts(routeForWorkspaceWindow(windowRecord)).path);
  frame.title = `${chrome.appLabel}: ${chrome.title} — рабочее окно`;
  if (frame.parentElement !== body || body.childElementCount !== 1) body.replaceChildren(frame);
  body.classList.add("has-live-surface");
  delete body.dataset.ceV4WindowSnapshotSignature;
  return frame;
}

function workspaceWindowSurfaceForSource(source) {
  let match = null;
  runtime.windowSurfaces.forEach((frame, windowId) => {
    if (!match && frame?.contentWindow === source) match = { frame, windowId };
  });
  return match;
}

function handleWorkspaceWindowSurfaceMessage(event) {
  if (IS_EMBEDDED_WORKSPACE_WINDOW || event.origin !== window.location.origin) return;
  const match = workspaceWindowSurfaceForSource(event.source);
  if (!match) return;
  const message = readContentEngineEmbeddedWindowEvent(event.data, match.windowId);
  if (!message || message.windowId !== match.windowId) return;
  const { frame, windowId } = match;
  const windowRecord = currentWorkspaceWindow(windowId);
  if (!windowRecord) return;
  frame.dataset.ceV4WindowReady = String(message.event === "ready" || message.event === "route" || message.event === "focus");
  frame.classList.toggle("is-ready", frame.dataset.ceV4WindowReady === "true");
  if (message.event === "failed") frame.dataset.ceV4WindowFailed = "true";
  else delete frame.dataset.ceV4WindowFailed;
  if (message.event === "ready" || message.event === "route") {
    runtime.windowRoutes.set(
      windowId,
      routeWithProject(message.route, windowRecord.projectContext?.projectId || ""),
    );
    syncWorkspaceWindowChrome(runtime.windowShells.get(windowId), windowRecord);
  }
  if (message.event === "focus") {
    if (runtime.activeWindowId !== windowId) {
      focusWorkspaceWindowShell(windowId, { focusSurface: false });
    }
  }
  if (message.event === "shortcut" && message.shortcut === "search") {
    if (runtime.activeWindowId !== windowId) {
      focusWorkspaceWindowShell(windowId, { focusSurface: false });
    }
    const search = q(".ce-v4-menubar__search input", runtime.menubar);
    safeFocus(search);
    search?.select?.();
  }
}

function postWorkspaceWindowSurfaceCommand(windowId, command, details = {}) {
  const frame = runtime.windowSurfaces.get(windowId);
  const windowRecord = currentWorkspaceWindow(windowId);
  if (!(frame instanceof HTMLIFrameElement) || !frame.contentWindow || !windowRecord) return false;
  if (command !== "navigate") return false;
  frame.contentWindow.postMessage({
    type: CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
    version: CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
    command,
    windowId,
    route: String(details.route || routeForWorkspaceWindow(windowRecord)),
  }, window.location.origin);
  return true;
}

function createWorkspaceWindowShell(windowId) {
  const host = q("#main-content");
  if (!host) return null;
  const shell = create("section", "ce-v4-window");
  shell.dataset.ceV4Window = "true";
  shell.dataset.ceV4WindowId = windowId;
  shell.tabIndex = -1;
  const titlebar = create("header", "ce-v4-window__titlebar");
  titlebar.dataset.ceV4WindowTitlebar = "true";
  const traffic = create("div", "ce-v4-window__traffic");
  traffic.setAttribute("role", "group");
  traffic.setAttribute("aria-label", "Управление окном");
  const close = windowControl("close", "Закрыть окно", "ce-v4-window__close");
  const minimize = windowControl("minimize", "Свернуть окно в Dock", "ce-v4-window__minimize");
  const zoom = windowControl("zoom", "Развернуть окно", "ce-v4-window__zoom");
  zoom.setAttribute("aria-pressed", "false");
  traffic.append(close, minimize, zoom);
  const heading = create("div", "ce-v4-window__heading");
  const glyph = dockIcon("ce-dock-finder", 24);
  glyph.dataset.ceV4WindowGlyph = "true";
  const headingCopy = create("span", "ce-v4-window__heading-copy");
  const app = create("small", "", "Рабочий стол");
  app.dataset.ceV4WindowApp = "true";
  const title = create("strong", "", "Проекты");
  title.dataset.ceV4WindowTitle = "true";
  headingCopy.append(app, title);
  heading.append(glyph, headingCopy);
  const actions = create("div", "ce-v4-window__actions");
  const project = create("span", "ce-v4-window__project", "Все проекты");
  project.dataset.ceV4WindowProject = "true";
  const desktop = iconButton("ce-v4-window__desktop", "Вернуться на рабочий стол", "home");
  desktop.dataset.ceV4WindowAction = "desktop";
  desktop.append(create("span", "ce-v4-window__desktop-label", "Рабочий стол"));
  const mission = iconButton("ce-v4-window__mission", "Показать окна и рабочие столы", "grid");
  mission.dataset.ceV4WindowAction = "mission";
  actions.append(project, desktop, mission);
  titlebar.append(traffic, heading, actions);
  const body = create("div", "ce-v4-window__body");
  body.dataset.ceV4WindowBody = "true";
  shell.append(titlebar, body);
  host.append(shell);
  runtime.windowShells.set(windowId, shell);
  shell.addEventListener("click", (event) => {
    const actionTarget = event.target instanceof Element
      ? event.target.closest("[data-ce-v4-window-action]")
      : null;
    const action = actionTarget?.dataset.ceV4WindowAction;
    if (action === "close") closeWorkspaceWindow(windowId);
    else if (action === "minimize") minimizeWorkspaceWindow(windowId);
    else if (action === "zoom") handleWorkspaceWindowZoomClick(windowId);
    else if (action === "desktop") showWorkspaceDesktop();
    else if (action === "mission") openMission();
    else if (action === "focus" || runtime.activeWindowId !== windowId || workspaceDesktopRoute()) {
      activateWorkspaceWindow(windowId, { focus: true });
    }
  });
  zoom.addEventListener("dblclick", (event) => {
    event.preventDefault();
    event.stopPropagation();
    clearWorkspaceWindowZoomClick(windowId);
    toggleWorkspaceWindowZoom(true, windowId);
  });
  titlebar.addEventListener("dblclick", (event) => {
    if (event.target instanceof Element && event.target.closest("button, a, input, select, textarea")) return;
    if (runtime.activeWindowId !== windowId || workspaceDesktopRoute()) activateWorkspaceWindow(windowId);
    else toggleWorkspaceWindowZoom(undefined, windowId);
  });
  titlebar.addEventListener("pointerdown", beginWorkspaceWindowDrag);
  observeWorkspaceWindowGeometry(shell, windowId);
  return shell;
}

function handleWorkspaceWindowZoomClick(windowId) {
  const now = performance.now();
  const pending = runtime.windowZoomClicks.get(windowId);
  if (pending && now - pending.startedAt <= 460) {
    window.clearTimeout(pending.timer);
    runtime.windowZoomClicks.delete(windowId);
    return toggleWorkspaceWindowZoom(true, windowId);
  }
  if (pending) window.clearTimeout(pending.timer);
  const timer = window.setTimeout(() => {
    const current = runtime.windowZoomClicks.get(windowId);
    if (!current || current.timer !== timer) return;
    runtime.windowZoomClicks.delete(windowId);
    toggleWorkspaceWindowZoom(undefined, windowId);
  }, 260);
  runtime.windowZoomClicks.set(windowId, { startedAt: now, timer });
  return false;
}

function clearWorkspaceWindowZoomClick(windowId) {
  const pending = runtime.windowZoomClicks.get(windowId);
  if (pending) window.clearTimeout(pending.timer);
  runtime.windowZoomClicks.delete(windowId);
}

function syncWorkspaceWindowState() {
  const host = q("#main-content");
  const content = enforceSingleWorkspaceContent(host);
  if (!host || !content) return;
  const state = runtime.windowManagerState;
  const desktopMode = workspaceDesktopRoute();
  syncWorkspaceDesktopExposure(desktopMode);
  const activeSpaceId = state.activeSpaceId;
  const keyWindow = desktopMode ? null : currentWorkspaceWindow();

  /* The parent renderer remains a parked, inert routing coordinator. Every
     application window owns a persistent child document instead of borrowing
     this single DOM node. */
  parkWorkspaceContent();
  state.windows.forEach((windowRecord) => {
    const shell = runtime.windowShells.get(windowRecord.windowId)?.isConnected
      ? runtime.windowShells.get(windowRecord.windowId)
      : createWorkspaceWindowShell(windowRecord.windowId);
    syncWorkspaceWindowChrome(shell, windowRecord);
    ensureWorkspaceWindowSurface(q("[data-ce-v4-window-body]", shell), windowRecord);
  });

  const liveIds = new Set(state.windows.map((item) => item.windowId));
  runtime.windowShells.forEach((shell, windowId) => {
    if (liveIds.has(windowId)) return;
    runtime.windowResizeObservers.get(windowId)?.disconnect();
    runtime.windowResizeObservers.delete(windowId);
    runtime.windowSurfaces.delete(windowId);
    runtime.windowSnapshots.delete(windowId);
    shell.remove();
    runtime.windowShells.delete(windowId);
  });
  runtime.windowSurfaces.forEach((frame, windowId) => {
    if (liveIds.has(windowId)) return;
    frame.remove();
    runtime.windowSurfaces.delete(windowId);
  });

  runtime.syncingWindowGeometry = true;
  state.windows.forEach((windowRecord) => {
    const shell = runtime.windowShells.get(windowRecord.windowId);
    if (!shell) return;
    const inActiveSpace = windowRecord.spaceId === activeSpaceId;
    const minimized = Boolean(windowRecord.minimized);
    const zoomed = Boolean(windowRecord.zoomed);
    const snap = runtime.windowSnapMemory.get(windowRecord.windowId) || null;
    const visible = !desktopMode && inActiveSpace && !minimized;
    const active = Boolean(keyWindow && keyWindow.windowId === windowRecord.windowId);
    shell.hidden = !visible;
    shell.classList.toggle("is-minimized", minimized);
    shell.classList.toggle("is-zoomed", zoomed);
    /* Every visible application is live/active. The key-window marker only
       describes keyboard focus and z-order; it never disables its siblings. */
    shell.classList.toggle("is-active", visible);
    shell.classList.toggle("is-key-window", active);
    shell.classList.toggle("is-live", visible);
    shell.classList.toggle("is-snapped", Boolean(snap && !zoomed));
    shell.classList.remove("is-inactive");
    shell.classList.toggle("is-other-space", !inActiveSpace);
    shell.dataset.ceV4WindowActive = String(active);
    shell.dataset.ceV4WindowLive = String(visible);
    if (snap && !zoomed) shell.dataset.ceV4WindowSnap = snap.slot || "snapped";
    else delete shell.dataset.ceV4WindowSnap;
    shell.style.zIndex = String(20 + windowRecord.zIndex);
    if (!visible) {
      shell.setAttribute("aria-hidden", "true");
      shell.setAttribute("inert", "");
    } else {
      shell.removeAttribute("aria-hidden");
      shell.removeAttribute("inert");
    }
    const control = q('[data-ce-v4-window-action="zoom"]', shell);
    if (control) {
      control.setAttribute("aria-pressed", String(zoomed));
      control.setAttribute("aria-label", zoomed ? "Вернуть размер окна" : "Развернуть окно");
      control.title = zoomed ? "Вернуть размер окна" : "Развернуть окно";
    }
    if (zoomed) {
      shell.style.removeProperty("left");
      shell.style.removeProperty("top");
      shell.style.removeProperty("width");
      shell.style.removeProperty("height");
    } else {
      shell.style.left = `${windowRecord.position.x}px`;
      shell.style.top = `${windowRecord.position.y}px`;
      shell.style.width = `${windowRecord.size.width}px`;
      shell.style.height = `${windowRecord.size.height}px`;
    }
    const surface = runtime.windowSurfaces.get(windowRecord.windowId);
    if (surface) {
      surface.tabIndex = visible ? 0 : -1;
      surface.setAttribute("aria-hidden", String(!visible));
      surface.style.pointerEvents = visible ? "auto" : "none";
    }
  });
  runtime.windowShell = keyWindow ? runtime.windowShells.get(keyWindow.windowId) || null : null;
  document.body.classList.toggle(
    "ce-v4-window-minimized",
    state.windows.some((item) => item.spaceId === activeSpaceId)
      && !state.windows.some((item) => item.spaceId === activeSpaceId && !item.minimized),
  );
  if (keyWindow) {
    const chrome = workspaceWindowRecord(routeParts(routeForWorkspaceWindow(keyWindow)).path);
    document.body.dataset.ceV4ActiveApp = chrome.appLabel;
  } else {
    document.body.dataset.ceV4ActiveApp = "Рабочий стол";
  }
  window.requestAnimationFrame(() => {
    runtime.syncingWindowGeometry = false;
    document.dispatchEvent(new CustomEvent(WINDOW_GEOMETRY_EVENT));
  });
}

function stopWorkspaceWindowDragTracking() {
  window.removeEventListener("pointermove", moveWorkspaceWindow, true);
  window.removeEventListener("pointerup", endWorkspaceWindowDrag, true);
  window.removeEventListener("pointercancel", cancelWorkspaceWindowDrag, true);
}

function cancelWorkspaceWindowDrag(event) {
  endWorkspaceWindowDrag(event, true);
}

function beginWorkspaceWindowDrag(event) {
  const shell = event.currentTarget?.closest?.("[data-ce-v4-window-id]");
  const windowId = String(shell?.dataset.ceV4WindowId || "");
  if (
    event.button !== 0
    || window.innerWidth <= 850
    || runtime.windowDrag
    || currentWorkspaceWindow(windowId)?.zoomed
    || (event.target instanceof Element && event.target.closest("button, a, input, select, textarea"))
  ) return;
  closeWorkspaceSnapAssist();
  runtime.windowSnapMemory.delete(windowId);
  const pendingActivation = runtime.activeWindowId !== windowId || workspaceDesktopRoute();
  /* Raise an inactive window immediately, but keep the original business DOM
     in its current owner until pointer-up triggers the route activation. */
  reduceWorkspaceWindow({ type: "focus", windowId });
  syncWorkspaceWindowState();
  const state = currentWorkspaceWindow(windowId);
  if (!state) return;
  runtime.windowDrag = {
    pointerId: event.pointerId,
    windowId,
    pendingActivation,
    previousActiveWindowId: runtime.activeWindowId,
    moved: false,
    snapTarget: "",
    startX: event.clientX,
    startY: event.clientY,
    originX: state.position.x,
    originY: state.position.y,
    captureTarget: event.currentTarget,
  };
  try { event.currentTarget.setPointerCapture?.(event.pointerId); }
  catch { /* Synthetic or cancelled pointers may not be capturable. */ }
  window.addEventListener("pointermove", moveWorkspaceWindow, true);
  window.addEventListener("pointerup", endWorkspaceWindowDrag, true);
  window.addEventListener("pointercancel", cancelWorkspaceWindowDrag, true);
  shell?.classList.add("is-dragging");
  event.preventDefault();
}

function moveWorkspaceWindow(event) {
  const drag = runtime.windowDrag;
  if (!drag || drag.pointerId !== event.pointerId || !drag.windowId) return;
  if (!drag.moved && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) >= 2) {
    drag.moved = true;
    runtime.windowGeometryTouched.add(drag.windowId);
  }
  drag.snapTarget = workspaceSnapCandidate(event);
  if (drag.snapTarget) showWorkspaceSnapPreview(drag.snapTarget, drag.windowId);
  else clearWorkspaceSnapPreview();
  reduceWorkspaceWindow({
    type: "move",
    windowId: drag.windowId,
    position: {
      x: drag.originX + event.clientX - drag.startX,
      y: drag.originY + event.clientY - drag.startY,
    },
  });
  syncWorkspaceWindowState();
}

function endWorkspaceWindowDrag(event, cancelled = false) {
  const drag = runtime.windowDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  stopWorkspaceWindowDragTracking();
  try { drag.captureTarget?.releasePointerCapture?.(event.pointerId); }
  catch { /* The pointer may already have been released by the browser. */ }
  runtime.windowShells.get(drag.windowId)?.classList.remove("is-dragging");
  const snapTarget = drag.snapTarget;
  clearWorkspaceSnapPreview();
  runtime.windowDrag = null;
  if (cancelled && drag.pendingActivation && currentWorkspaceWindow(drag.previousActiveWindowId)) {
    reduceWorkspaceWindow({ type: "focus", windowId: drag.previousActiveWindowId });
    syncWorkspaceWindowState();
  } else if (!cancelled && snapTarget === "left") {
    applyWorkspaceSnap(drag.windowId, { count: 2, index: 0, slot: "left" });
  } else if (!cancelled && snapTarget === "right") {
    applyWorkspaceSnap(drag.windowId, { count: 2, index: 1, slot: "right" });
  } else if (!cancelled && snapTarget === "top") {
    focusWorkspaceWindowShell(drag.windowId);
    openWorkspaceSnapAssist(drag.windowId);
  } else if (!cancelled && drag.pendingActivation) {
    activateWorkspaceWindow(drag.windowId, { focus: !drag.moved });
  }
}

function observeWorkspaceWindowGeometry(shell, windowId) {
  if (typeof ResizeObserver !== "function") return;
  runtime.windowResizeObservers.get(windowId)?.disconnect();
  const observer = new ResizeObserver((entries) => {
    if (
      runtime.syncingWindowGeometry
      || window.innerWidth <= 850
      || shell.classList.contains("is-zoomed")
      || shell.classList.contains("is-minimized")
      || !windowId
    ) return;
    const entry = entries.at(-1);
    if (!entry) return;
    const rect = shell.getBoundingClientRect();
    const width = Math.round(rect.width || shell.offsetWidth);
    const height = Math.round(rect.height || shell.offsetHeight);
    const state = currentWorkspaceWindow(windowId);
    if (!state || (Math.abs(state.size.width - width) < 2 && Math.abs(state.size.height - height) < 2)) return;
    runtime.windowSnapMemory.delete(windowId);
    runtime.windowGeometryTouched.add(windowId);
    reduceWorkspaceWindow({ type: "resize", windowId, size: { width, height } });
    syncWorkspaceWindowState();
  });
  observer.observe(shell);
  runtime.windowResizeObservers.set(windowId, observer);
  runtime.windowResizeObserver = observer;
}

function focusWorkspaceWindowShell(windowId, options = {}) {
  const windowRecord = currentWorkspaceWindow(windowId);
  if (!windowRecord) return false;
  reduceWorkspaceWindow({ type: "switchSpace", spaceId: windowRecord.spaceId });
  reduceWorkspaceWindow({ type: "restore", windowId });
  reduceWorkspaceWindow({ type: "focus", windowId });
  runtime.activeWindowId = windowId;
  syncWorkspaceWindowState();
  updateDock();
  updateMenubar();
  if (options.focusSurface) {
    const frame = runtime.windowSurfaces.get(windowId);
    window.requestAnimationFrame(() => frame?.focus?.({ preventScroll: true }));
  }
  return true;
}

function restoreWorkspaceWindow(options = {}) {
  const windowId = String(options.windowId || runtime.activeWindowId || "");
  const shell = runtime.windowShells.get(windowId) || runtime.windowShell;
  if (!shell?.isConnected) return false;
  const record = currentWorkspaceWindow(windowId);
  if (workspaceDesktopRoute() && record) {
    navigate(routeForWorkspaceWindow(record));
    return true;
  }
  return focusWorkspaceWindowShell(windowId, { focusSurface: Boolean(options.focus) });
}

function minimizeWorkspaceWindow(windowId = runtime.activeWindowId) {
  const shell = runtime.windowShells.get(windowId) || runtime.windowShell;
  if (!shell?.isConnected || shell.classList.contains("is-minimized")) return;
  if (shell.dataset.ceV4Minimizing === "true") return;
  if (runtime.windowSnapAssist?.dataset.ceV4WindowSnapAssist === windowId) closeWorkspaceSnapAssist();
  shell.dataset.ceV4Minimizing = "true";
  shell.classList.add("is-minimizing");
  const finish = () => {
    delete shell.dataset.ceV4Minimizing;
    shell.classList.remove("is-minimizing");
    reduceWorkspaceWindow({ type: "minimize", windowId });
    if (runtime.activeWindowId === windowId) {
      const next = topVisibleWorkspaceWindow(currentWorkspaceWindow(windowId)?.spaceId, windowId);
      if (next) {
        focusWorkspaceWindowShell(next.windowId);
      } else {
        navigate("/workspace/home");
      }
    } else syncWorkspaceWindowState();
    safeFocus(q(".ce-v4-dock__item.is-active", runtime.dock) || q(".ce-v4-dock__item", runtime.dock));
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 220);
}

function toggleWorkspaceWindowZoom(force, windowId = runtime.activeWindowId) {
  const shell = runtime.windowShells.get(windowId) || runtime.windowShell;
  if (!shell?.isConnected) return false;
  const current = currentWorkspaceWindow(windowId);
  const requested = typeof force === "boolean" ? force : !current?.zoomed;
  if (current && current.zoomed !== requested) {
    reduceWorkspaceWindow({ type: "toggleZoom", windowId });
  }
  runtime.activeWindowId = windowId;
  syncWorkspaceWindowState();
  return requested;
}

function activateWorkspaceWindow(windowId, options = {}) {
  const windowRecord = currentWorkspaceWindow(windowId);
  if (!windowRecord) return false;
  const destination = routeForWorkspaceWindow(windowRecord);
  if (workspaceDesktopRoute()) {
    navigate(destination);
    return true;
  }
  return focusWorkspaceWindowShell(windowId, { focusSurface: Boolean(options.focus) });
}

function showWorkspaceDesktop() {
  navigate("/workspace/home", { preserveProject: false });
}

function closeWorkspaceWindow(windowId = runtime.activeWindowId) {
  if (!windowId) return;
  const closing = currentWorkspaceWindow(windowId);
  const wasActive = runtime.activeWindowId === windowId;
  runtime.windowRoutes.delete(windowId);
  runtime.windowSurfaces.delete(windowId);
  runtime.windowSnapshots.delete(windowId);
  clearWorkspaceWindowZoomClick(windowId);
  runtime.windowSnapMemory.delete(windowId);
  runtime.windowGeometryTouched.delete(windowId);
  if (runtime.windowSnapAssist?.dataset.ceV4WindowSnapAssist === windowId) closeWorkspaceSnapAssist();
  reduceWorkspaceWindow({ type: "close", windowId });
  if (!wasActive) {
    syncWorkspaceWindowState();
    return;
  }
  const next = topVisibleWorkspaceWindow(closing?.spaceId);
  if (next) {
    runtime.activeWindowId = next.windowId;
    const destination = routeForWorkspaceWindow(next);
    if (workspaceActionKey(destination) === workspaceActionKey() && !workspaceDesktopRoute()) {
      syncWorkspaceWindowState();
    } else navigate(destination);
    return;
  }
  runtime.activeWindowId = "";
  navigate("/workspace/home");
}

function setWorkspaceContentParked(parked) {
  const content = enforceSingleWorkspaceContent();
  if (!content) return null;
  if (parked) {
    content.dataset.ceV4DesktopParked = "true";
    content.setAttribute("aria-hidden", "true");
    content.setAttribute("inert", "");
  } else if (content.dataset.ceV4DesktopParked === "true") {
    delete content.dataset.ceV4DesktopParked;
    content.removeAttribute("aria-hidden");
    content.removeAttribute("inert");
  }
  return content;
}

function updateWorkspaceWindow() {
  const route = routePath();
  const snapshot = projectFlowSnapshot();
  const routeChanged = runtime.windowRoute && runtime.windowRoute !== route;
  const windowId = workspaceWindowId(route, snapshot);
  const previousActiveWindowId = runtime.activeWindowId;
  runtime.windowRoute = route;
  if (routeChanged || !runtime.windowRoutes.has(windowId)) {
    runtime.windowRoutes.set(windowId, String(window.location.hash || `#${route}`).replace(/^#/, ""));
  }
  const existing = runtime.windowManagerState.windows.some((item) => item.windowId === windowId);
  let shouldActivateRouteWindow = !currentWorkspaceWindow(previousActiveWindowId) || routeChanged;
  if (!existing) {
    const spaceId = snapshot.id ? `space:project:${snapshot.id}` : "space:main";
    reduceWorkspaceWindow({
      type: "open",
      window: {
        appId: `app:${routeRecord(route).route.replace(/^\/workspace\//u, "") || "home"}`,
        windowId,
        spaceId,
        projectContext: snapshot.id ? { projectId: snapshot.id } : null,
        ...defaultWorkspaceWindowGeometry(route),
      },
    });
    shouldActivateRouteWindow = true;
  } else {
    const existingWindow = runtime.windowManagerState.windows.find((item) => item.windowId === windowId);
    if (routeChanged || existingWindow?.minimized) {
      reduceWorkspaceWindow({ type: "focus", windowId });
      shouldActivateRouteWindow = true;
    }
  }
  runtime.activeWindowId = shouldActivateRouteWindow ? windowId : previousActiveWindowId;
  syncWorkspaceWindowState();
}

function ensureWorkspaceWindow() {
  const host = q("#main-content");
  const content = enforceSingleWorkspaceContent(host);
  if (!host || !content) return null;
  updateWorkspaceWindow();
  return runtime.windowShell;
}

function removeWorkspaceWindow() {
  const host = q("#main-content");
  const content = enforceSingleWorkspaceContent(host);
  if (host && content && content.parentElement !== host) moveWorkspaceContent(content, host);
  runtime.windowShells.forEach((shell) => shell.remove());
  runtime.windowShells.clear();
  runtime.windowSurfaces.forEach((frame) => frame.remove());
  runtime.windowSurfaces.clear();
  runtime.windowSnapshots.clear();
  runtime.windowResizeObservers.forEach((observer) => observer.disconnect());
  runtime.windowResizeObservers.clear();
  runtime.windowResizeObserver?.disconnect();
  runtime.windowResizeObserver = null;
  stopWorkspaceWindowDragTracking();
  clearWorkspaceSnapPreview();
  closeWorkspaceSnapAssist();
  window.cancelAnimationFrame(runtime.windowSnapResizeFrame);
  runtime.windowSnapResizeFrame = 0;
  runtime.windowDrag = null;
  runtime.windowGeometryTouched.clear();
  runtime.windowZoomClicks.forEach((_, windowId) => clearWorkspaceWindowZoomClick(windowId));
  runtime.windowSnapMemory.clear();
  runtime.windowShell = null;
  runtime.windowRoute = "";
  runtime.activeWindowId = "";
  runtime.windowRoutes.clear();
  runtime.windowManagerState = createWorkspaceWindowManagerState();
  document.body.classList.remove("ce-v4-window-minimized");
  document.body.removeAttribute("data-ce-v4-active-app");
}

function desktopMetric(title, value, detail) {
  const card = create("article", "ce-v4-desktop-widget");
  card.append(
    create("strong", "ce-v4-desktop-widget__title", title),
    create("span", "ce-v4-desktop-widget__value", value),
    create("small", "ce-v4-desktop-widget__detail", detail),
  );
  return card;
}

function projectCoverPreferenceKey() {
  const scope = currentDockScope();
  const identity = scope
    ? `${encodeURIComponent(scope.organizationId)}:${encodeURIComponent(scope.userId)}`
    : "authenticated-workspace";
  return `${PROJECT_COVER_STORAGE_PREFIX}:${identity}`;
}

function readProjectCoverPreferences() {
  const fallback = {};
  const raw = readJson(storage("local"), projectCoverPreferenceKey(), fallback);
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return fallback;
  const allowed = new Set(PROJECT_COVER_OPTIONS.map((option) => option.key).filter((key) => key !== "auto"));
  return Object.fromEntries(Object.entries(raw)
    .map(([projectId, cover]) => [String(projectId || "").trim(), String(cover || "").trim()])
    .filter(([projectId, cover]) => projectId && projectId.length <= 180 && allowed.has(cover))
    .slice(0, 120));
}

function projectCoverFor(projectId) {
  return readProjectCoverPreferences()[String(projectId || "").trim()] || "auto";
}

function writeProjectCoverPreference(projectId, cover) {
  const id = String(projectId || "").trim();
  const nextCover = String(cover || "auto").trim();
  if (!id || !PROJECT_COVER_OPTIONS.some((option) => option.key === nextCover)) return false;
  const preferences = readProjectCoverPreferences();
  if (nextCover === "auto") delete preferences[id];
  else preferences[id] = nextCover;
  writeJson(storage("local"), projectCoverPreferenceKey(), preferences);
  applyProjectCoverPreferences();
  return true;
}

function applyProjectCoverPreferences(root = document) {
  qa(".home-project-card[data-ce-v4-project-id], .ce-v4-desktop-project[data-ce-v4-project-id]", root).forEach((card) => {
    const cover = projectCoverFor(card.dataset.ceV4ProjectId);
    if (cover === "auto") card.removeAttribute("data-ce-v4-project-cover");
    else card.dataset.ceV4ProjectCover = cover;
    const name = card.dataset.ceV4ProjectName || q(".home-project-card__copy strong, .ce-v4-desktop-project__copy strong", card)?.textContent || "Проект";
    card.title = `${compact(name, 80)} · открыть проект; правой кнопкой — выбрать обложку`;
  });
}

function openProjectCoverPicker(rawProjectId, rawTitle = "Проект", trigger = null) {
  const projectId = String(rawProjectId || "").trim();
  if (!projectId) return false;
  if (runtime.projectCover) closeElementOverlay("projectCover", true);
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  const title = compact(rawTitle || "Проект", 100);
  const { backdrop, dialog } = overlayBase("ce-v4-project-cover-picker", `Обложка проекта ${title}`);
  const header = create("header", "ce-v4-project-cover-picker__header");
  const copy = create("div", "ce-v4-project-cover-picker__heading");
  copy.append(
    create("small", "ce-v4-eyebrow", "ВИЗУАЛ ПРОЕКТА"),
    create("h1", "", `Обложка · ${title}`),
    create("p", "", "Выберите сцену, по которой проект будет узнаваем на рабочем столе. Это меняет только оформление, не файлы проекта."),
  );
  const close = iconButton("", "Закрыть", "close");
  close.dataset.ceV4Close = "true";
  header.append(copy, close);

  const current = projectCoverFor(projectId);
  const grid = create("div", "ce-v4-project-cover-picker__grid");
  grid.setAttribute("role", "radiogroup");
  grid.setAttribute("aria-label", "Доступные обложки");
  PROJECT_COVER_OPTIONS.forEach((option) => {
    const button = create("button", "ce-v4-project-cover-choice");
    button.type = "button";
    button.dataset.ceV4ProjectCoverChoice = option.key;
    button.dataset.cover = option.key;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(option.key === current));
    button.classList.toggle("is-selected", option.key === current);
    const preview = create("span", "ce-v4-project-cover-choice__preview");
    preview.dataset.cover = option.key;
    preview.setAttribute("aria-hidden", "true");
    const choiceCopy = create("span", "ce-v4-project-cover-choice__copy");
    choiceCopy.append(create("strong", "", option.label), create("small", "", option.detail));
    const check = create("span", "ce-v4-project-cover-choice__check", option.key === current ? "✓" : "");
    check.setAttribute("aria-hidden", "true");
    button.append(preview, choiceCopy, check);
    grid.append(button);
  });

  const footer = create("footer", "ce-v4-project-cover-picker__footer");
  footer.append(
    create("p", "", "Выбор сохраняется отдельно для текущего пользователя и проекта."),
    (() => {
      const done = create("button", "ce-v4-project-cover-picker__done", "Готово");
      done.type = "button";
      done.dataset.ceV4Close = "true";
      return done;
    })(),
  );
  dialog.append(header, grid, footer);
  document.body.append(backdrop);
  runtime.projectCover = backdrop;
  document.body.classList.add("ce-v4-projectCover-open");
  activateElementOverlay("projectCover", backdrop);
  const modalContext = runtime.modalContexts.get("projectCover");
  if (modalContext && trigger instanceof HTMLElement) modalContext.opener = trigger;

  const syncChoice = (cover) => {
    qa("[data-ce-v4-project-cover-choice]", grid).forEach((button) => {
      const selected = button.dataset.ceV4ProjectCoverChoice === cover;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-checked", String(selected));
      const check = q(".ce-v4-project-cover-choice__check", button);
      if (check) check.textContent = selected ? "✓" : "";
    });
  };
  backdrop.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (event.target === backdrop || target?.closest("[data-ce-v4-close]")) {
      closeElementOverlay("projectCover");
      return;
    }
    const choice = target?.closest("[data-ce-v4-project-cover-choice]");
    if (!choice) return;
    const cover = String(choice.dataset.ceV4ProjectCoverChoice || "auto");
    if (!writeProjectCoverPreference(projectId, cover)) return;
    syncChoice(cover);
    showSystemToast(`Обложка проекта «${title}» обновлена.`, "success");
  });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeElementOverlay("projectCover");
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
    const choices = qa("[data-ce-v4-project-cover-choice]", grid);
    const active = choices.indexOf(document.activeElement);
    const delta = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
    const next = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1 : (Math.max(0, active) + delta + choices.length) % choices.length;
    event.preventDefault();
    safeFocus(choices[next]);
  });
  safeFocus(q('[data-ce-v4-project-cover-choice][aria-checked="true"]', grid) || q("button", grid));
  animate(dialog, [{ opacity: 0, transform: "translateY(12px) scale(.985)" }, { opacity: 1, transform: "translateY(0) scale(1)" }], 190);
  return true;
}

function desktopShortcutPreferenceKey(snapshot = projectFlowSnapshot()) {
  const scope = currentDockScope();
  const identity = scope
    ? `${encodeURIComponent(scope.organizationId)}:${encodeURIComponent(scope.userId)}`
    : "authenticated-workspace";
  const projectId = String(snapshot.id || "all-projects").replace(/[^A-Za-z0-9_.:@-]/gu, "-");
  return `${DESKTOP_SHORTCUT_STORAGE_PREFIX}:${identity}:${projectId}`;
}

function readDesktopShortcutPreference(snapshot = projectFlowSnapshot()) {
  const fallback = { order: [], hidden: [] };
  try {
    const raw = JSON.parse(window.localStorage.getItem(desktopShortcutPreferenceKey(snapshot)) || "null");
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return fallback;
    const clean = (values) => [...new Set((Array.isArray(values) ? values : [])
      .map((value) => String(value || "").trim())
      .filter((value) => /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$/u.test(value)))]
      .slice(0, 48);
    return { order: clean(raw.order), hidden: clean(raw.hidden) };
  } catch {
    return fallback;
  }
}

function writeDesktopShortcutPreference(preference, snapshot = projectFlowSnapshot()) {
  try {
    window.localStorage.setItem(desktopShortcutPreferenceKey(snapshot), JSON.stringify({
      order: [...new Set(preference.order || [])].slice(0, 48),
      hidden: [...new Set(preference.hidden || [])].slice(0, 48),
    }));
    if (runtime.desktop) runtime.desktop.dataset.ceV4DesktopSignature = "";
    return true;
  } catch {
    showSystemToast("Браузер не разрешил сохранить расположение ярлыков.", "warning");
    return false;
  }
}

function desktopShortcutRecordsInPreferenceOrder(records, snapshot = projectFlowSnapshot()) {
  const preference = readDesktopShortcutPreference(snapshot);
  const byKey = new Map(records.map((record) => [record.key, record]));
  const ordered = [];
  preference.order.forEach((key) => {
    const record = byKey.get(key);
    if (record && !preference.hidden.includes(key)) {
      ordered.push(record);
      byKey.delete(key);
    }
  });
  records.forEach((record) => {
    if (byKey.has(record.key) && !preference.hidden.includes(record.key)) {
      ordered.push(record);
      byKey.delete(record.key);
    }
  });
  return ordered;
}

function desktopShortcutAction(rawKey, action) {
  const key = String(rawKey || "");
  const snapshot = projectFlowSnapshot();
  const preference = readDesktopShortcutPreference(snapshot);
  const order = [...preference.order];
  const hidden = [...preference.hidden];
  const currentNodes = qa("[data-ce-v4-desktop-key]", runtime.desktop);
  const visibleKeys = currentNodes.map((item) => String(item.dataset.ceV4DesktopKey || "")).filter(Boolean);
  if (!order.length) order.push(...visibleKeys);
  const index = order.indexOf(key);
  if (action === "hide" && key) {
    if (!hidden.includes(key)) hidden.push(key);
    showSystemToast("Ярлык убран с рабочего стола. Данные не удалены.", "success");
  } else if (["left", "right"].includes(action) && index >= 0) {
    const targetIndex = Math.max(0, Math.min(order.length - 1, index + (action === "left" ? -1 : 1)));
    order.splice(index, 1);
    order.splice(targetIndex, 0, key);
  } else if (action === "reset") {
    order.splice(0);
    hidden.splice(0);
    showSystemToast("Стандартный набор ярлыков восстановлен.", "success");
  } else if (action === "edit") {
    runtime.desktopShortcutsEditing = true;
    runtime.desktop?.classList.add("is-shortcut-editing");
    if (runtime.desktop) runtime.desktop.dataset.ceV4DesktopSignature = "";
    updateWorkspaceDesktop();
    return true;
  } else return false;
  writeDesktopShortcutPreference({ order, hidden }, snapshot);
  updateWorkspaceDesktop();
  return true;
}

function beginDesktopShortcutDrag(event) {
  if (event.button !== 0) return;
  const item = event.target instanceof Element ? event.target.closest("[data-ce-v4-desktop-key]") : null;
  if (!(item instanceof HTMLElement)) return;
  runtime.desktopShortcutDrag = {
    pointerId: event.pointerId,
    item,
    startX: event.clientX,
    startY: event.clientY,
    moved: false,
  };
  try { item.setPointerCapture?.(event.pointerId); }
  catch { /* A cancelled synthetic pointer may not be capturable. */ }
}

function moveDesktopShortcutDrag(event) {
  const drag = runtime.desktopShortcutDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  if (!drag.moved && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) < 7) return;
  drag.moved = true;
  drag.item.classList.add("is-dragging");
  const nav = drag.item.closest(".ce-v4-desktop-shortcuts");
  const candidates = qa("[data-ce-v4-desktop-key]", nav).filter((item) => item !== drag.item);
  const target = candidates
    .map((item) => {
      const rect = item.getBoundingClientRect();
      return { item, distance: Math.hypot(event.clientX - (rect.left + rect.width / 2), event.clientY - (rect.top + rect.height / 2)) };
    })
    .sort((left, right) => left.distance - right.distance)[0]?.item;
  if (target) {
    const rect = target.getBoundingClientRect();
    const after = event.clientY > rect.top + rect.height / 2
      || (Math.abs(event.clientY - (rect.top + rect.height / 2)) < rect.height * .35 && event.clientX > rect.left + rect.width / 2);
    nav.insertBefore(drag.item, after ? target.nextSibling : target);
  }
  event.preventDefault();
}

function finishDesktopShortcutDrag(event, cancelled = false) {
  const drag = runtime.desktopShortcutDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  runtime.desktopShortcutDrag = null;
  drag.item.classList.remove("is-dragging");
  if (cancelled || !drag.moved) return;
  const snapshot = projectFlowSnapshot();
  const preference = readDesktopShortcutPreference(snapshot);
  const order = qa("[data-ce-v4-desktop-key]", drag.item.closest(".ce-v4-desktop-shortcuts"))
    .map((item) => String(item.dataset.ceV4DesktopKey || ""))
    .filter(Boolean);
  writeDesktopShortcutPreference({ order, hidden: preference.hidden }, snapshot);
  runtime.desktopSuppressClickUntil = performance.now() + 260;
  event.preventDefault();
}

function desktopShortcut({ key, label, detail, route, icon: iconName, count = null, accent = "#98A9BD", stageCode = "" }) {
  const link = create("a", "ce-v4-desktop-shortcut");
  link.href = `#${route}`;
  link.dataset.ceV4DesktopKey = key;
  link.draggable = false;
  if (stageCode) link.dataset.ceV4DesktopStage = stageCode;
  link.style.setProperty("--ce-v4-shortcut-accent", accent);
  link.setAttribute("aria-label", detail ? `${label}. ${detail}` : label);
  link.title = detail ? `${label} — ${detail}` : label;
  const tile = create("span", "ce-v4-desktop-shortcut__tile");
  tile.append(dockIcon(iconName, 64));
  const marker = create("span", "ce-v4-desktop-shortcut__marker");
  marker.setAttribute("aria-hidden", "true");
  tile.append(marker);
  if (Number.isFinite(Number(count)) && Number(count) > 0) {
    const badge = create("span", "ce-v4-desktop-shortcut__count", Number(count) > 99 ? "99+" : String(Math.trunc(Number(count))));
    badge.setAttribute("aria-hidden", "true");
    tile.append(badge);
  }
  const copy = create("span", "ce-v4-desktop-shortcut__copy");
  copy.append(create("strong", "", label));
  if (detail) copy.append(create("small", "", detail));
  link.append(tile, copy);
  return link;
}

function desktopProjectPreview(project, index = 0) {
  const progress = Math.max(0, Math.min(100, Number(project?.progress || 0)));
  const link = create("a", "ce-v4-desktop-project");
  link.href = `#${projectSelectionRoute(project)}`;
  link.dataset.ceV4ProjectId = String(project?.id || "");
  link.dataset.ceV4ProjectName = String(project?.name || "Проект");
  link.style.setProperty("--ce-v4-project-order", String(index));
  link.setAttribute("aria-label", `${project?.name || "Проект"}. ${projectStageLabel(project)}. Готовность ${progress}%`);
  const visual = create("span", "ce-v4-desktop-project__visual");
  visual.setAttribute("aria-hidden", "true");
  visual.append(create("span", "ce-v4-desktop-project__monogram", projectMonogram(project?.name || "CE")));
  const copy = create("span", "ce-v4-desktop-project__copy");
  copy.append(
    create("small", "", projectStageLabel(project)),
    create("strong", "", compact(project?.name || "Проект", 70)),
  );
  const meter = create("span", "ce-v4-desktop-project__meter");
  const fill = create("i");
  fill.style.width = `${progress}%`;
  meter.append(fill);
  const meta = create("span", "ce-v4-desktop-project__meta");
  meta.append(create("small", "", progress > 0 ? `${progress}% готово` : "Готов к старту"), create("b", "", "Открыть →"));
  copy.append(meter, meta);
  link.append(visual, copy);
  return link;
}

function desktopCommandCenter(snapshot) {
  const section = create("section", "ce-v4-desktop-command");
  section.setAttribute("aria-labelledby", "ce-v4-desktop-command-title");
  const head = create("header", "ce-v4-desktop-command__head");
  const copy = create("div");
  copy.append(
    create("small", "ce-v4-eyebrow", snapshot.id ? `ПРОЕКТ · ${compact(snapshot.name, 58)}` : "ЛИЧНОЕ РАБОЧЕЕ ПРОСТРАНСТВО"),
    create("h1", "", snapshot.id ? "Продолжите производственную цепочку" : "Добро пожаловать в Контент‑завод"),
    create("p", "", snapshot.id
      ? "Файлы, создание, проверка, публикация и результаты остаются в одном контексте проекта."
      : "Выберите проект — система покажет точный следующий шаг и сохранит контекст всей истории."),
  );
  copy.querySelector("h1").id = "ce-v4-desktop-command-title";
  const allProjects = create("a", "ce-v4-desktop-command__all", "Все проекты");
  allProjects.href = "#/workspace/home?view=projects";
  head.append(copy, allProjects);

  const search = create("button", "ce-v4-desktop-command__search");
  search.type = "button";
  search.setAttribute("aria-label", "Найти проект, файл, SKU или задачу");
  search.append(icon("search", 20), create("span", "", "Найти проект, файл, SKU или задачу"), create("kbd", "", "Ctrl K"));
  search.addEventListener("click", () => openSpotlight());

  const projectGrid = create("div", "ce-v4-desktop-command__projects");
  const canCreateProject = workspaceCanCreateProject();
  if (snapshot.projects.length) {
    snapshot.projects.slice(0, 3).forEach((project, index) => projectGrid.append(desktopProjectPreview(project, index)));
  } else {
    const empty = create(canCreateProject ? "a" : "div", "ce-v4-desktop-project ce-v4-desktop-project--empty");
    if (canCreateProject) empty.href = "#/workspace/home?view=new";
    else empty.setAttribute("aria-label", "Доступных проектов пока нет. Создание проекта доступно руководителю.");
    empty.append(
      create("span", "ce-v4-desktop-project__empty-mark", canCreateProject ? "+" : "◇"),
      create("strong", "", canCreateProject ? "Создать первый проект" : "Проектов пока нет"),
      create("small", "", canCreateProject ? "Начать с файлов и цели" : "Запросите доступ у руководителя"),
    );
    projectGrid.append(empty);
  }

  if (canCreateProject) {
    const createProject = create("a", "ce-v4-desktop-command__create");
    createProject.href = "#/workspace/home?view=new";
    createProject.append(create("span", "", "+"), create("strong", "", "Новый проект"), create("small", "", "Отдельная история и производственный путь"));
    projectGrid.append(createProject);
  }
  section.append(head, search, projectGrid);
  return section;
}

function desktopAssistant(snapshot) {
  const aside = create("aside", "ce-v4-desktop-assistant");
  aside.setAttribute("aria-labelledby", "ce-v4-desktop-assistant-title");
  const head = create("header", "ce-v4-desktop-assistant__head");
  const mark = create("span", "ce-v4-desktop-assistant__mark");
  mark.append(icon("spark", 20));
  const title = create("div");
  title.append(create("small", "", "ИИ‑ЦЕНТР · РЕКОМЕНДАЦИЯ"), create("h2", "", "ИИ предлагает. Человек решает."));
  title.querySelector("h2").id = "ce-v4-desktop-assistant-title";
  head.append(mark, title);
  const description = create("p", "", "Рекомендация приходит из ИИ‑центра как редактируемый черновик. Ваши правки сохраняются и применяются только после явного подтверждения.");
  const rules = create("ol", "ce-v4-desktop-assistant__rules");
  [
    ["1", "Получить рекомендацию", "Источник, аргументы и ограничения видимы"],
    ["2", "Поправить вручную", "ИИ не перезаписывает решение человека"],
    ["3", "Подтвердить применение", "Без подтверждения рабочая версия не меняется"],
  ].forEach(([number, label, detail]) => {
    const item = create("li");
    const itemCopy = create("span");
    itemCopy.append(create("strong", "", label), create("small", "", detail));
    item.append(create("b", "", number), itemCopy);
    rules.append(item);
  });
  const aiAuthorized = routeIsAuthorized("/workspace/ai");
  const action = create(
    snapshot.id && !aiAuthorized ? "button" : "a",
    "ce-v4-desktop-assistant__action",
    snapshot.id ? (aiAuthorized ? "Открыть ИИ‑центр" : "ИИ‑центр недоступен для роли") : "Сначала выбрать проект",
  );
  if (action instanceof HTMLAnchorElement) {
    action.href = `#${snapshot.id ? routeWithProject("/workspace/ai", snapshot.id) : "/workspace/home?view=projects"}`;
  } else {
    action.type = "button";
    action.disabled = true;
    action.title = "Обратитесь к владельцу рабочего пространства";
  }
  aside.append(head, description, rules, action);
  return aside;
}

function updateWorkspaceDesktop() {
  const desktop = runtime.desktop;
  if (!desktop?.isConnected) return;
  const snapshot = projectFlowSnapshot();
  const selected = snapshot.projects.find((item) => item.id === snapshot.id) || null;
  const activeStages = snapshot.stages.filter((stage) => ["current", "blocked"].includes(stage.state));
  const activeStageCounts = activeStages
    .map((stage) => stage.count)
    .filter((count) => Number.isFinite(Number(count)));
  const processCount = activeStageCounts.reduce((total, count) => total + Number(count), 0);
  const doneCount = snapshot.stages.filter((stage) => stage.state === "done").length;
  const attentionCount = snapshot.stages.filter((stage) => stage.state === "blocked").length;
  const reviewStage = snapshot.stages.find((stage) => stage.code === "review");
  const shortcutPreference = readDesktopShortcutPreference(snapshot);
  const signature = JSON.stringify({
    id: snapshot.id,
    name: snapshot.name,
    unread: snapshot.unread,
    projects: snapshot.projects.map((item) => [item.id, item.name, item.progress, item.currentStage]),
    stages: snapshot.stages.map((item) => [item.code, item.state, item.count]),
    shortcutPreference,
    shortcutEditing: runtime.desktopShortcutsEditing,
  });
  if (desktop.dataset.ceV4DesktopSignature === signature) return;
  desktop.dataset.ceV4DesktopSignature = signature;

  const widgets = create("aside", "ce-v4-desktop-widgets");
  widgets.setAttribute("aria-label", "Сводка рабочего пространства");
  const pulseValue = selected?.progress > 0 ? `${selected.progress}%` : `${doneCount}/${snapshot.stages.length}`;
  widgets.append(
    desktopMetric(
      snapshot.id ? `Пульс · ${snapshot.name}` : "Пульс проектов",
      pulseValue,
      snapshot.id ? "готовность производственного пути" : `${snapshot.projects.length} доступных проектов`,
    ),
    desktopMetric(
      "Процессы",
      activeStageCounts.length ? String(processCount) : "—",
      activeStageCounts.length ? "активных объектов в работе" : "появятся после выбора проекта",
    ),
    desktopMetric(
      "Нужны решения",
      reviewStage?.count !== null
        && reviewStage?.count !== undefined
        && Number.isFinite(Number(reviewStage.count))
        ? String(reviewStage.count)
        : attentionCount > 0 ? String(attentionCount) : "—",
      attentionCount > 0 ? `${attentionCount} этапов требуют внимания` : "в очереди проверки · блокировок нет",
    ),
  );

  const shortcuts = create("nav", "ce-v4-desktop-shortcuts");
  shortcuts.setAttribute("aria-label", "Объекты рабочего стола");
  const shortcutRecords = [];
  if (snapshot.id) {
    shortcutRecords.push(
      {
        key: "project-root",
        label: snapshot.name,
        detail: selected ? projectStageLabel(selected) : "Рабочая папка проекта",
        route: routeWithProject("/workspace/board", snapshot.id),
        icon: "ce-dock-finder",
        accent: "#39D99E",
      },
      {
        key: "review",
        label: "Нужны решения",
        detail: "Проверка материалов человеком",
        route: routeWithProject("/workspace/review?view=current", snapshot.id),
        icon: "ce-dock-review",
        count: reviewStage?.count,
        accent: "#C84C65",
        stageCode: "review",
      },
      {
        key: "materials",
        label: "Материалы",
        detail: "Файлы и исходники проекта",
        route: routeWithProject("/workspace/board", snapshot.id),
        icon: "ce-dock-finder",
        count: snapshot.stages.find((stage) => stage.code === "files")?.count,
        accent: "#4A8FFF",
        stageCode: "files",
      },
      {
        key: "inbox",
        label: "Входящие",
        detail: "Личная очередь сотрудника",
        route: routeWithProject("/workspace/work?view=queue", snapshot.id),
        icon: "ce-dock-processes",
        accent: "#98A9BD",
      },
    );
  } else {
    snapshot.projects.slice(0, 4).forEach((project) => {
      shortcutRecords.push({
        key: `project-${project.id}`,
        label: project.name,
        detail: projectStageLabel(project),
        route: projectSelectionRoute(project),
        icon: "ce-dock-finder",
        accent: "#39D99E",
      });
    });
    shortcutRecords.push({
      key: "notifications",
      label: "Уведомления",
      detail: "События рабочего пространства",
      route: "/workspace/work?view=notifications",
      icon: "ce-dock-processes",
      count: snapshot.unread,
      accent: "#D7AD59",
    });
  }
  desktopShortcutRecordsInPreferenceOrder(shortcutRecords, snapshot)
    .forEach((record) => shortcuts.append(desktopShortcut(record)));
  const shortcutSettings = create(
    "button",
    "ce-v4-desktop-shortcuts__settings",
    runtime.desktopShortcutsEditing ? "Готово" : "Настроить ярлыки",
  );
  shortcutSettings.type = "button";
  shortcutSettings.dataset.ceV4DesktopShortcutSettings = "true";
  shortcutSettings.setAttribute("aria-pressed", String(runtime.desktopShortcutsEditing));
  shortcutSettings.title = runtime.desktopShortcutsEditing
    ? "Сохранить расположение ярлыков"
    : "Перетащите ярлыки или настройте их состав";
  shortcuts.append(shortcutSettings);
  desktop.replaceChildren(widgets, shortcuts);
  desktop.classList.toggle("is-shortcut-editing", runtime.desktopShortcutsEditing);
  desktop.append(desktopCommandCenter(snapshot), desktopAssistant(snapshot));
}

function ensureWorkspaceDesktop() {
  const host = q("#main-content");
  if (!host) return null;
  let desktop = runtime.desktop?.isConnected
    ? runtime.desktop
    : q(":scope > [data-ce-v4-desktop]", host);
  if (!desktop) {
    desktop = create("section", "ce-v4-desktop");
    desktop.dataset.ceV4Desktop = "true";
    desktop.setAttribute("aria-label", "Рабочий стол ContentEngine");
    desktop.addEventListener("click", (event) => {
      const settings = event.target instanceof Element
        ? event.target.closest("[data-ce-v4-desktop-shortcut-settings]")
        : null;
      if (settings) {
        runtime.desktopShortcutsEditing = !runtime.desktopShortcutsEditing;
        desktop.dataset.ceV4DesktopSignature = "";
        updateWorkspaceDesktop();
        showSystemToast(
          runtime.desktopShortcutsEditing
            ? "Перетаскивайте ярлыки. Нажмите ×, чтобы убрать ярлык без удаления данных."
            : "Расположение ярлыков сохранено.",
          "success",
        );
        return;
      }
      const shortcut = event.target instanceof Element
        ? event.target.closest("[data-ce-v4-desktop-key]")
        : null;
      if (shortcut && performance.now() < runtime.desktopSuppressClickUntil) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      if (
        shortcut
        && runtime.desktopShortcutsEditing
        && event.target instanceof Element
        && event.target.closest(".ce-v4-desktop-shortcut__marker")
      ) {
        event.preventDefault();
        event.stopPropagation();
        desktopShortcutAction(shortcut.dataset.ceV4DesktopKey, "hide");
        return;
      }
      const target = event.target instanceof Element
        ? event.target.closest("[data-ce-v4-desktop-stage]")
        : null;
      if (!(target instanceof HTMLAnchorElement)) return;
      const snapshot = projectFlowSnapshot();
      const stage = snapshot.stages.find((item) => (
        item.code === target.dataset.ceV4DesktopStage
      ));
      if (!stageLocked(stage, snapshot)) return;
      event.preventDefault();
      openRequiredStage(stage, snapshot);
    });
    desktop.addEventListener("pointerdown", beginDesktopShortcutDrag);
    desktop.addEventListener("pointermove", moveDesktopShortcutDrag);
    desktop.addEventListener("pointerup", (event) => finishDesktopShortcutDrag(event));
    desktop.addEventListener("pointercancel", (event) => finishDesktopShortcutDrag(event, true));
    host.prepend(desktop);
  }
  runtime.desktop = desktop;
  updateWorkspaceDesktop();
  return desktop;
}

function removeWorkspaceDesktop() {
  runtime.desktop?.remove();
  runtime.desktop = null;
}

function mountHome() {
  if (routePath() !== "/workspace/home") return;
  const page = currentPage();
  if (!page) return;
  q(":scope > .ce-v4-home", page)?.remove();
  const projects = q("[data-ce-v4-project-home]", page);
  page.classList.add("ce-v4-home-page");
  page.classList.toggle("ce-v4-project-home", Boolean(projects));
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

  const chooserMode = projectChooserMode();
  const stored = chooserMode ? null : storedProjectContext();
  const queryProjectId = String(routeQuery().get("project_id") || "").trim();
  const rootProjectId = String(root?.dataset.projectId || root?.dataset.workspaceProjectId || "").trim();
  const rawProjectId = String(raw.project_id || rawProject?.id || "").trim();
  const id = chooserMode ? "" : queryProjectId || rootProjectId || rawProjectId || stored?.id || "";
  const nextAction = normalizeProjectNextAction(rawNextAction, id);
  const catalogProject = projects.find((item) => item.id === id) || null;
  const rootProjectName = rootProjectId === id ? root?.dataset.projectName : "";
  const storedProjectName = stored?.id === id ? stored.name : "";
  const name = compact(catalogProject?.name || rootProjectName || rawProject?.name || storedProjectName || "Проект", 80);
  const rootFolderId = id
    ? String(catalogProject?.rootFolderId || rawProject?.rootFolderId || stored?.rootFolderId || id).trim()
    : "";
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
    const reasonCode = String(match?.reason_code || "");
    const reason = reasonCode === "content_approval_required"
      ? "Проверку выполняете вы: откройте готовый материал и выберите «Одобрить», «На доработку» или «Отклонить»."
      : compact(match?.reason || match?.reason_text || "", 180);
    return {
      ...item,
      state,
      count: stageCount(match, counts, item),
      reason,
      reasonCode,
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
  // «Результаты» — экран наблюдения, а не производственный шаг: воронка и
  // пустые состояния говорят правду и без публикаций. Запирать его «Сначала
  // подтвердите публикацию» значило прятать сам смысл экрана (25.08,
  // владелица: «ты бы просто сделала, чтобы форма результатов открывалась»).
  if (stage.code === "stats") return false;
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

function openRequiredStage(stage, snapshot = projectFlowSnapshot()) {
  const required = snapshot.stages.find((item) => item.state === "current")
    || snapshot.stages.find((item) => item.state === "blocked")
    || null;
  const destination = String(
    snapshot.nextAction?.route || required?.destination || "",
  ).trim();
  if (!destination) {
    explainLockedStage(stage);
    return;
  }
  const targetLabel = required?.label || "текущий шаг";
  const explanation = stage?.reason
    || "Сначала завершите текущее действие проекта.";
  showSystemToast(`${explanation} Открываю: ${targetLabel}.`, "warning");
  if (workspaceActionKey(destination) !== workspaceActionKey()) {
    navigatePrimaryRoute(destination);
  }
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
      openRequiredStage(stage, currentSnapshot);
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
  dialog.tabIndex = -1;
  backdrop.append(dialog);
  return { backdrop, dialog };
}

function modalFocusable(root) {
  return qa(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    root,
  ).filter((node) => !node.hidden && !node.closest("[hidden], [inert]") && isVisible(node));
}

function activateElementOverlay(name, backdrop) {
  const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const inerted = [q("#app"), runtime.menubar, runtime.dock]
    .filter((node, index, nodes) => node?.isConnected && nodes.indexOf(node) === index)
    .map((node) => ({ node, wasInert: node.inert === true }));
  inerted.forEach(({ node }) => { node.inert = true; });
  runtime.modalContexts.set(name, { opener, inerted });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = modalFocusable(backdrop);
    if (!focusable.length) {
      event.preventDefault();
      safeFocus(q('[role="dialog"]', backdrop));
      return;
    }
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      safeFocus(last);
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      safeFocus(first);
    }
  });
}

function releaseElementOverlay(name) {
  const context = runtime.modalContexts.get(name);
  if (!context) return;
  context.inerted.forEach(({ node, wasInert }) => {
    if (node?.isConnected) node.inert = wasInert;
  });
  runtime.modalContexts.delete(name);
  if (context.opener?.isConnected && !context.opener.closest("[inert]")) safeFocus(context.opener);
}

function closeElementOverlay(name, immediate = false) {
  const overlay = runtime[name];
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    runtime[name] = null;
    document.body.classList.remove(`ce-v4-${name}-open`);
    releaseElementOverlay(name);
  };
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function closeTransientOverlays(immediate = false) {
  clearWorkspaceSnapPreview();
  closeWorkspaceSnapAssist();
  closeProjectMenu();
  closeToolsMenu();
  closeDockMore();
  closeDockLibrary(false);
  closeNotificationCenter(false);
  if (runtime.mission) closeElementOverlay("mission", immediate);
  if (runtime.spotlight) closeElementOverlay("spotlight", immediate);
  if (runtime.projectCover) closeElementOverlay("projectCover", immediate);
  if (runtime.zen) closeZen(immediate);
}

function routeForWorkspaceWindow(record) {
  const remembered = runtime.windowRoutes.get(record.windowId);
  if (remembered) return remembered;
  const section = String(record.appId || "app:home").replace(/^app:/u, "") || "home";
  const base = `/workspace/${section}`;
  return routeWithProject(base, record.projectContext?.projectId || "");
}

function missionSpaceRecords(snapshot = projectFlowSnapshot()) {
  const records = snapshot.projects.map((project) => ({
    spaceId: `space:project:${project.id}`,
    project,
    label: project.name,
    detail: projectStageLabel(project),
  }));
  if (snapshot.id && !records.some((item) => item.project.id === snapshot.id)) {
    records.unshift({
      spaceId: `space:project:${snapshot.id}`,
      project: { id: snapshot.id, name: snapshot.name, rootFolderId: snapshot.rootFolderId },
      label: snapshot.name,
      detail: "Текущий проект",
    });
  }
  const hasMainWindows = runtime.windowManagerState.windows.some((item) => item.spaceId === "space:main");
  if (!records.length || hasMainWindows) {
    records.unshift({
      spaceId: "space:main",
      project: null,
      label: "Все проекты",
      detail: "Общий рабочий стол",
    });
  }
  return records;
}

function openMission() {
  if (runtime.mission) return;
  document.dispatchEvent(new CustomEvent(CLOSE_TRANSIENTS_EVENT, { detail: { source: "core" } }));
  const snapshot = projectFlowSnapshot();
  const spaces = missionSpaceRecords(snapshot);
  let selectedSpaceId = spaces.some((item) => item.spaceId === runtime.windowManagerState.activeSpaceId)
    ? runtime.windowManagerState.activeSpaceId
    : spaces[0]?.spaceId || "space:main";
  const { backdrop, dialog } = overlayBase("ce-v4-mission", "Окна и пространства");
  const header = create("header", "ce-v4-overlay-header");
  const copy = create("div");
  copy.append(
    create("small", "ce-v4-eyebrow", "MISSION CONTROL"),
    create("h1", "", "Окна и пространства"),
    create("p", "", "Один проект — одно пространство. Откройте существующее окно или вернитесь в проект без потери его контекста."),
  );
  const close = iconButton("", "Закрыть", "close");
  close.dataset.ceV4Close = "true";
  header.append(copy, close);

  const spaceList = create("div", "ce-v4-mission__spaces");
  spaceList.setAttribute("role", "tablist");
  spaceList.setAttribute("aria-label", "Пространства проектов");
  spaces.forEach((space) => {
    const button = create("button", "ce-v4-mission-space");
    button.type = "button";
    button.dataset.ceV4MissionSpace = space.spaceId;
    button.setAttribute("role", "tab");
    const preview = create("span", "ce-v4-mission-space__preview");
    preview.append(dockIcon(space.project ? "ce-dock-finder" : "ce-dock-processes", 34));
    const label = create("span", "ce-v4-mission-space__copy");
    label.append(create("strong", "", space.label), create("small", "", space.detail));
    button.append(preview, label);
    spaceList.append(button);
  });

  const search = create("label", "ce-v4-mission__search");
  search.append(icon("search", 18));
  const input = create("input");
  input.type = "search";
  input.placeholder = "Найти открытое окно";
  input.setAttribute("aria-label", "Найти открытое окно");
  search.append(input);
  const grid = create("div", "ce-v4-mission__grid");

  const renderWindows = () => {
    qa("[data-ce-v4-mission-space]", spaceList).forEach((button) => {
      const selected = button.dataset.ceV4MissionSpace === selectedSpaceId;
      button.classList.toggle("is-selected", selected);
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    });
    const windows = runtime.windowManagerState.windows
      .filter((item) => item.spaceId === selectedSpaceId)
      .sort((left, right) => right.zIndex - left.zIndex);
    const needle = input.value.trim().toLocaleLowerCase("ru-RU");
    const fragment = document.createDocumentFragment();
    windows.forEach((windowRecord) => {
      const route = routeForWorkspaceWindow(windowRecord);
      const chrome = workspaceWindowRecord(routeParts(route).path);
      const searchable = `${chrome.appLabel} ${chrome.title} ${route}`.toLocaleLowerCase("ru-RU");
      if (needle && !searchable.includes(needle)) return;
      const button = create("button", "ce-v4-mission-window");
      button.type = "button";
      button.dataset.ceV4MissionWindow = windowRecord.windowId;
      button.classList.toggle("is-active", windowRecord.windowId === runtime.activeWindowId);
      button.style.setProperty("--ce-v4-window-accent", chrome.accent);
      const titlebar = create("span", "ce-v4-mission-window__titlebar");
      titlebar.append(dockIcon(chrome.dockIcon, 24), create("strong", "", chrome.appLabel));
      const status = create("small", "", windowRecord.minimized ? "Свернуто" : windowRecord.zoomed ? "Развернуто" : "Открыто");
      titlebar.append(status);
      const canvas = create("span", "ce-v4-mission-window__canvas");
      canvas.append(dockIcon(chrome.dockIcon, 52), create("strong", "", chrome.title), create("small", "", route));
      button.append(titlebar, canvas);
      fragment.append(button);
    });
    if (!fragment.childNodes.length) {
      const empty = create("button", "ce-v4-mission-empty");
      empty.type = "button";
      empty.dataset.ceV4MissionOpenSpace = selectedSpaceId;
      const selected = spaces.find((item) => item.spaceId === selectedSpaceId);
      empty.append(
        dockIcon(selected?.project ? "ce-dock-finder" : "ce-dock-processes", 48),
        create("strong", "", needle ? "Окна не найдены" : "В этом пространстве нет открытых окон"),
        create("small", "", needle ? "Измените запрос или откройте проект" : "Открыть проект и создать его первое окно"),
      );
      fragment.append(empty);
    }
    grid.replaceChildren(fragment);
  };

  dialog.append(header, spaceList, search, grid);
  document.body.append(backdrop);
  runtime.mission = backdrop;
  document.body.classList.add("ce-v4-mission-open");
  activateElementOverlay("mission", backdrop);
  renderWindows();
  backdrop.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (event.target === backdrop || target?.closest("[data-ce-v4-close]")) {
      closeElementOverlay("mission");
      return;
    }
    const spaceButton = target?.closest("[data-ce-v4-mission-space]");
    if (spaceButton) {
      selectedSpaceId = spaceButton.dataset.ceV4MissionSpace;
      input.value = "";
      renderWindows();
      return;
    }
    const windowButton = target?.closest("[data-ce-v4-mission-window]");
    if (windowButton) {
      const windowId = windowButton.dataset.ceV4MissionWindow;
      const windowRecord = runtime.windowManagerState.windows.find((item) => item.windowId === windowId);
      if (!windowRecord) return;
      closeElementOverlay("mission", true);
      activateWorkspaceWindow(windowId, { focus: true });
      return;
    }
    const openSpace = target?.closest("[data-ce-v4-mission-open-space]")?.dataset.ceV4MissionOpenSpace;
    if (openSpace) {
      const space = spaces.find((item) => item.spaceId === openSpace);
      reduceWorkspaceWindow({ type: "switchSpace", spaceId: openSpace });
      closeElementOverlay("mission", true);
      if (space?.project) navigate(projectSelectionRoute(space.project));
      else navigatePrimaryRoute("/workspace/home");
    }
  });
  input.addEventListener("input", renderWindows);
  spaceList.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = qa("[data-ce-v4-mission-space]", spaceList);
    const current = buttons.findIndex((button) => button.dataset.ceV4MissionSpace === selectedSpaceId);
    const next = event.key === "Home"
      ? 0
      : event.key === "End"
        ? buttons.length - 1
        : (Math.max(0, current) + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    event.preventDefault();
    selectedSpaceId = buttons[next]?.dataset.ceV4MissionSpace || selectedSpaceId;
    input.value = "";
    renderWindows();
    safeFocus(buttons[next]);
  });
  backdrop.addEventListener("keydown", (event) => { if (event.key === "Escape") closeElementOverlay("mission"); });
  safeFocus(q('[data-ce-v4-mission-space][aria-selected="true"]', spaceList) || input);
  animate(dialog, [{ opacity: 0, transform: "translateY(10px)" }, { opacity: 1, transform: "translateY(0)" }], 200);
}

function spotlightRecords(query = "") {
  const records = authorizedRoutes(ALL_ROUTES).map((item) => ({
    title: item.label,
    subtitle: item.description,
    icon: item.icon,
    keywords: `${item.label} ${item.description}`.toLocaleLowerCase("ru-RU"),
    run: () => navigatePrimaryRoute(item.route),
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
  activateElementOverlay("spotlight", backdrop);
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
  activateElementOverlay("zen", backdrop);
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
    releaseElementOverlay("zen");
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
  const windowBody = q("[data-ce-v4-window-body]");
  return [windowBody, main, ...qa(
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
  captureWorkspaceWindowSnapshot(currentWorkspaceWindow(), q("#workspace-content"));
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

function mountEmbeddedWorkspaceWindow() {
  document.documentElement.dataset.contentengineOs = "v4";
  document.documentElement.dataset.ceWindowChild = "true";
  document.body.classList.add("contentengine-desktop-v4", "contentengine-window-child");
  document.body.dataset.ceV4Stable = "true";
  document.body.removeAttribute("data-ce-v4-desktop-home");
  cleanLegacyChrome();
  qa(".ce-v4-menubar, .ce-v4-dock, [data-ce-v4-desktop], [data-ce-v4-window]")
    .forEach((node) => node.remove());
  runtime.menubar = null;
  runtime.dock = null;
  runtime.desktop = null;
  runtime.windowShell = null;
  runtime.windowShells.clear();
  runtime.windowSurfaces.clear();
  setWorkspaceContentParked(false);
}

function mount() {
  const route = routePath();
  if (!isWorkspaceRoute(route) || !hasAuthenticatedWorkspace()) {
    closeTransientOverlays(true);
    closeNotificationCenter(false);
    runtime.notificationPanel?.remove();
    runtime.notificationPanel = null;
    runtime.notificationReturnFocus = null;
    runtime.notificationFeed = null;
    runtime.notificationFeedSignature = "";
    runtime.notificationFeedIssue = "feed_unavailable";
    runtime.notificationActionContexts = Object.freeze({});
    runtime.notificationServerCounts = null;
    runtime.notificationLoadedFilter = "";
    runtime.notificationPendingRequests.forEach((request) => window.clearTimeout(request.timer));
    runtime.notificationPendingRequests.clear();
    runtime.notificationActionFailures.clear();
    runtime.notificationLastError = "";
    runtime.notificationActionNavigationHash = "";
    runtime.notificationInitialLoadRequested = false;
    removeWorkspaceWindow();
    removeWorkspaceDesktop();
    runtime.menubar?.remove();
    runtime.dock?.remove();
    runtime.menubar = null;
    runtime.dock = null;
    runtime.dockEditor = null;
    runtime.dockLibrary = null;
    runtime.dockEditorReturnFocus = null;
    runtime.dockLibraryReturnFocus = null;
    runtime.dockPointerReorder = null;
    resetDockPreferenceRuntime();
    document.body.classList.remove("contentengine-desktop-v4");
    document.body.classList.remove("ce-v4-notification-open");
    document.body.removeAttribute("data-ce-v4-stable");
    document.body.removeAttribute("data-ce-v4-desktop-home");
    document.documentElement.removeAttribute("data-contentengine-os");
    return;
  }
  if (IS_EMBEDDED_WORKSPACE_WINDOW) {
    mountEmbeddedWorkspaceWindow();
    return;
  }
  document.documentElement.dataset.contentengineOs = "v4";
  document.body.classList.add("contentengine-desktop-v4");
  document.body.dataset.ceV4Stable = "true";
  cleanLegacyChrome();
  loadDockPreferenceForAuthenticatedScope();
  ensureMenubar();
  ensureDock();
  ensureWorkspaceDesktop();
  if (workspaceDesktopRoute()) {
    document.body.dataset.ceV4DesktopHome = "true";
    parkWorkspaceContent();
    syncWorkspaceWindowState();
  } else {
    document.body.removeAttribute("data-ce-v4-desktop-home");
    setWorkspaceContentParked(false);
    ensureWorkspaceWindow();
  }
  updateWorkspaceDesktop();
  updateMenubar();
  if (!notificationFixtureMode() && !runtime.notificationInitialLoadRequested) {
    runtime.notificationInitialLoadRequested = true;
    requestNotificationCenterProjection(runtime.notificationFilter, { force: true });
  }
  if (notificationCenterOpen()) {
    syncNotificationCenter();
    requestNotificationCenterProjection(runtime.notificationFilter);
  }
  updateDock();
  mountHome();
  applyProjectCoverPreferences();
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

// Страж смеси сборок. Кэш браузера умеет собрать вкладку из модулей двух эпох
// (боевой случай 25.08.2026: списки «Создания» рисовал один экземпляр guided,
// клики перехватывал второй с пустым состоянием — галки «не работали», секции
// двоились, док пустел). Событие ловит workspace-build-guard и форсирует
// баннер перезагрузки.
function reportMixedBuildEpoch(scope, held, incoming) {
  console.error(
    `ContentEngine mixed build detected: ${scope} держит ${held}, пришёл ${incoming}`,
  );
  try {
    window.dispatchEvent(new CustomEvent("contentengine:mixed-build-detected", {
      detail: { scope, held, incoming },
    }));
  } catch { /* событие — лучшая попытка; консоль уже сказала главное */ }
}

function registerAdapter(name, adapterMount, options = {}) {
  if (!name || typeof adapterMount !== "function") throw new TypeError("Desktop adapter requires a name and mount function");
  const epoch = typeof options.epoch === "string" && options.epoch
    ? options.epoch
    : BUILD;
  const existing = runtime.adapters.get(name);
  if (existing && existing.epoch !== epoch) {
    // Первый владелец имени остаётся: его рендер и его слушатели согласованы
    // между собой. Молчаливая замена отдала бы клики экземпляру чужой эпохи.
    reportMixedBuildEpoch(`adapter:${name}`, existing.epoch, epoch);
    return () => {};
  }
  runtime.adapters.set(name, {
    name,
    mount: adapterMount,
    priority: Number.isFinite(options.priority) ? options.priority : 100,
    epoch,
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
  const notificationActionNavigation = runtime.notificationActionNavigationHash;
  runtime.notificationActionNavigationHash = "";
  const keepNotificationPanelOpen = notificationOpenRequestPending() || (
    notificationCenterOpen()
    && Boolean(notificationActionNavigation)
    && notificationActionNavigation === window.location.hash
  );
  if (keepNotificationPanelOpen) {
    closeProjectMenu();
    closeToolsMenu();
    closeDockMore();
    closeDockLibrary(false);
    if (runtime.mission) closeElementOverlay("mission", true);
    if (runtime.spotlight) closeElementOverlay("spotlight", true);
    if (runtime.zen) closeZen(true);
  } else {
    closeTransientOverlays(true);
  }
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
    if (IS_EMBEDDED_WORKSPACE_WINDOW) {
      event.preventDefault();
      event.stopImmediatePropagation();
      window.ContentEngineEmbeddedWindow?.requestShortcut?.("search");
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    const search = q(".ce-v4-menubar__search input", runtime.menubar);
    safeFocus(search);
    search?.select?.();
    return;
  }
  if (event.key === "Escape") {
    if (q(".ce-v4-context-menu")) return;
    if (runtime.windowSnapAssist) {
      event.preventDefault();
      closeWorkspaceSnapAssist({ restoreFocus: true });
      return;
    }
    if (runtime.dockState.keyboardMove) {
      event.preventDefault();
      const key = runtime.dockState.keyboardMove.key;
      consumeDockTransition({ type: "keyboardCancelMove" });
      updateDock();
      window.requestAnimationFrame(() => safeFocus(dockItemNode(key)));
      return;
    }
    if (runtime.dockLibrary && !runtime.dockLibrary.hidden) {
      event.preventDefault();
      closeDockLibrary(true);
      return;
    }
    const dockMore = q("[data-ce-v4-dock-more-menu]", runtime.dock);
    if (dockMore && !dockMore.hidden) {
      event.preventDefault();
      closeDockMore(true);
    }
    else if (runtime.projectCover) closeElementOverlay("projectCover");
    else if (runtime.spotlight) closeElementOverlay("spotlight");
    else if (runtime.mission) closeElementOverlay("mission");
    else if (runtime.zen) closeZen();
    else if (notificationCenterOpen()) {
      event.preventDefault();
      closeNotificationCenter(true);
    }
    else if (dockEditing()) cancelDockEditor({ restoreFocus: true });
    return;
  }
  if (!editing && hasAuthenticatedWorkspace() && event.altKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code)) {
    const item = qa(".ce-v4-dock__item[data-ce-v4-dock-key]", runtime.dock)
      .filter((node) => {
        const record = DOCK_APPS.find((candidate) => candidate.key === node.dataset.ceV4DockKey);
        return Boolean(record && routeIsAuthorized(record.route) && isVisible(node));
      })[Number(event.code.slice(-1)) - 1];
    if (item) activateDockKey(item.dataset.ceV4DockKey, event);
  }
}

function handleScroll() {
  window.clearTimeout(runtime.scrollTimer);
  runtime.scrollTimer = window.setTimeout(() => captureScroll(routePath(), workspaceActionKey()), 180);
}

function handleWorkspaceResize() {
  window.cancelAnimationFrame(runtime.windowSnapResizeFrame);
  runtime.windowSnapResizeFrame = window.requestAnimationFrame(() => {
    runtime.windowSnapResizeFrame = 0;
    reflowWorkspaceSnappedWindows();
    scheduleMount();
  });
}

function handlePointerDown(event) {
  const target = event.target instanceof Element ? event.target : null;
  const path = typeof event.composedPath === "function" ? event.composedPath() : [];
  const notificationTrigger = q("[data-ce-v4-notifications]", runtime.menubar);
  if (runtime.windowSnapAssist && !path.includes(runtime.windowSnapAssist)) closeWorkspaceSnapAssist();
  if (
    notificationCenterOpen()
    && !path.includes(runtime.notificationPanel)
    && !path.includes(notificationTrigger)
  ) closeNotificationCenter(false);
  if (!target?.closest(".ce-v4-project-switcher")) closeProjectMenu();
  if (!target?.closest(".ce-v4-menubar__tools")) closeToolsMenu();
  if (!target?.closest("[data-ce-v4-dock-more], [data-ce-v4-dock-more-menu]")) closeDockMore();
}

function handleNotificationRouteLink(event) {
  if (!isWorkspaceRoute() || !hasAuthenticatedWorkspace()) return;
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = event.target instanceof Element ? event.target : null;
  const link = target?.closest('a[href^="#/workspace/work"]');
  if (!(link instanceof HTMLAnchorElement) || !link.closest(".workspace-shell")) return;
  const href = String(link.getAttribute("href") || "").replace(/^#/u, "");
  const { path, query } = routeParts(href);
  if (path !== "/workspace/work" || query.get("view") !== "notifications") return;
  event.preventDefault();
  event.stopImmediatePropagation();
  openNotificationCenter(link);
}

function handleWorkspaceSnapshotRouteLink(event) {
  if (!isWorkspaceRoute() || !hasAuthenticatedWorkspace()) return;
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = event.target instanceof Element ? event.target : null;
  const link = target?.closest('a[href^="#/workspace/"]');
  if (!(link instanceof HTMLAnchorElement)) return;
  captureWorkspaceWindowSnapshot(currentWorkspaceWindow(), q("#workspace-content"));
}

function bindScrollOwner() {
  [q("#main-content"), ...qa("[data-ce-v4-window-body]")].filter(Boolean).forEach((owner) => {
    if (owner.dataset.ceV4ScrollBound === "true") return;
    owner.dataset.ceV4ScrollBound = "true";
    owner.addEventListener("scroll", handleScroll, { passive: true });
  });
}

window.addEventListener("hashchange", handleHashChange, { capture: true, passive: true });
window.addEventListener("scroll", handleScroll, { passive: true });
window.addEventListener("resize", handleWorkspaceResize, { passive: true });
document.addEventListener(CLOSE_TRANSIENTS_EVENT, (event) => {
  if (event.detail?.source !== "core") closeTransientOverlays(true);
});
document.addEventListener("keydown", handleKeydown, true);
document.addEventListener("pointerdown", handlePointerDown, true);
document.addEventListener("click", handleWorkspaceSnapshotRouteLink, true);
document.addEventListener("click", handleNotificationRouteLink, true);
document.addEventListener("dragstart", handleDockFileDragStart, true);
document.addEventListener("dragend", resetDockPinZone, true);
document.addEventListener("drop", (event) => {
  if (!event.target?.closest?.("[data-ce-v4-dock-pin-zone]")) resetDockPinZone();
}, true);
document.addEventListener("contentengine:v4-handoff", (event) => {
  void handoff(event.detail?.route, event.detail || {});
});
document.addEventListener("contentengine:workspace-shell-updated", scheduleMount);
window.addEventListener("contentengine:workspace-runtime-ready", scheduleMount);
window.addEventListener("message", handleWorkspaceWindowSurfaceMessage);
document.addEventListener("contentengine:notifications-updated", scheduleMount);
document.addEventListener(
  NOTIFICATION_RUNTIME_RESPONSE_EVENT,
  handleNotificationRuntimeResponse,
);
observeWorkspace();
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();

// Рабочим столом владеет ПЕРВАЯ загрузившаяся эпоха: перезапись глобала второй
// сборкой оставила бы слушатели первой без реестра. Смесь только объявляется —
// дальше баннер build-guard доводит вкладку до перезагрузки.
const desktopEpochHeld = window.ContentEngineDesktopV4;
if (
  desktopEpochHeld
  && typeof desktopEpochHeld === "object"
  && typeof desktopEpochHeld.build === "string"
  && desktopEpochHeld.build !== BUILD
) {
  reportMixedBuildEpoch("workspace-os-v4", desktopEpochHeld.build, BUILD);
}
window.ContentEngineDesktopV4 = desktopEpochHeld
  && typeof desktopEpochHeld === "object"
  && typeof desktopEpochHeld.build === "string"
  && desktopEpochHeld.build !== BUILD
  ? desktopEpochHeld
  : Object.freeze({
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
  openDockEditor,
  finishDockEditor,
  dockContextAction,
  desktopShortcutAction,
  openProjectCoverPicker,
  windowContextAction: (windowId, action) => {
    if (action === "focus" || action === "restore") return activateWorkspaceWindow(windowId, { focus: true });
    if (action === "minimize") return minimizeWorkspaceWindow(windowId);
    if (action === "zoom") return toggleWorkspaceWindowZoom(undefined, windowId);
    if (action === "close") return closeWorkspaceWindow(windowId);
    return false;
  },
  openMission,
  windowState: () => runtime.windowManagerState,
  refreshDockPreferences: () => {
    loadDockPreferenceForAuthenticatedScope({ force: true });
    updateDock();
    return runtime.dockState.preference;
  },
  pinDockFileShortcut: (raw = {}) => {
    const objectId = String(raw.objectId || "").trim().toLowerCase();
    const projectId = String(raw.projectId || "").trim().toLowerCase();
    const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
    if (!uuid.test(objectId) || !uuid.test(projectId)) return false;
    void pinDockFileCandidate({
      objectId,
      projectId,
      labelOverride: String(raw.labelOverride || "Файл").trim().slice(0, 160) || "Файл",
    }, { source: "quick_look" });
    return true;
  },
  acceptsDockFileDrag: (objectId) => Boolean(
    runtime.dockPreferenceLoaded
    && dockScopesEqual(runtime.dockScope, currentDockScope())
    && runtime.dockDraggedFile?.objectId === String(objectId || "").trim().toLowerCase()
  ),
});
