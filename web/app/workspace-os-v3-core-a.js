/*
 * ContentEngine OS v3 core.
 * Shared desktop primitives for the production-loop adapters. Presentation and
 * local workspace memory only: no business API calls, no form cloning and no
 * authority changes.
 */

const V3_STATE_KEY = "contentengine.os-v3.ui.v1";
const V3_RECENT_KEY = "contentengine.os-v3.recent.v1";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const SAFE_ROUTE = /^\/(?:workspace(?:\/[a-z0-9_-]+)?|learn(?:\/[a-z0-9_-]+)?)$/iu;
const ENTITY_SELECTOR = [
  ".my-work-item[data-work-item-id]",
  ".task-card[data-task-id]",
  ".placement-card[data-placement-id]",
  ".media-card",
  "tr[data-payout-id]",
  "[data-review-result-id]",
  "[data-generation-job-id]",
].join(",");

const ICONS = Object.freeze({
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  work: '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M8 6V4h8v2M3 11h18M9 11v2h6v-2"/>',
  product: '<path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/>',
  publish: '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6h14v-6"/>',
  stats: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  money: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 15h4"/><circle cx="16" cy="14" r="2"/>',
  learn: '<path d="m3 6 9-3 9 3-9 3-9-3Z"/><path d="M6 8v6c3 2 9 2 12 0V8M21 6v7"/>',
  task: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  pin: '<path d="m14 4 6 6-3 1-4 4-1 4-7-7 4-1 4-4 1-3Z"/><path d="m5 19 4-4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  warning: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/>',
  command: '<path d="M9 8V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V8Z"/>',
  split: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M12 4v16"/>',
  undo: '<path d="M9 7 4 12l5 5"/><path d="M5 12h8a6 6 0 0 1 6 6"/>',
  handoff: '<path d="M4 12h12"/><path d="m12 6 6 6-6 6"/><circle cx="5" cy="5" r="2"/>',
  note: '<path d="M5 3h11l3 3v15H5V3Z"/><path d="M14 3v5h5M8 12h8M8 16h6"/>',
  frame: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m8 14 3-3 5 5M15 9h.01"/>',
});

const runtime = {
  queued: false,
  overlay: null,
  spotlight: null,
  capsule: null,
  rail: null,
  undo: null,
  objects: new Map(),
  commands: new Map(),
  adapters: new Map(),
  memory: readJson(window.localStorage, V3_STATE_KEY, {}),
  recent: readJson(window.sessionStorage, V3_RECENT_KEY, []),
  channel: null,
  foreignPresence: new Map(),
  currentEntityKey: "",
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = String(markup || "").trim();
  return template.content.firstElementChild;
}

function icon(name, size = 20) {
  const body = ICONS[name] || ICONS.grid;
  return `<svg class="ce-v3-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
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

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
  return SAFE_ROUTE.test(path) ? path : "/workspace/home";
}

function routeFromHref(value) {
  const raw = String(value || "");
  if (!raw.startsWith("#/")) return "";
  const path = raw.slice(1).split("?")[0].replace(/\/$/, "") || "/";
  return SAFE_ROUTE.test(path) ? path : "";
}

function readJson(storage, key, fallback) {
  try {
    const parsed = JSON.parse(storage?.getItem(key) || "null");
    return parsed === null ? fallback : parsed;
  } catch {
    return fallback;
  }
}

function writeJson(storage, key, value) {
  try { storage?.setItem(key, JSON.stringify(value)); } catch { /* optional memory */ }
}

function remember(patch) {
  runtime.memory = { ...runtime.memory, ...patch };
  writeJson(window.localStorage, V3_STATE_KEY, runtime.memory);
}

function dispatch(name, detail = {}) {
  document.dispatchEvent(new CustomEvent(name, { detail }));
}

function animateIn(node, direction = 1) {
  if (!node || REDUCED_MOTION.matches || typeof node.animate !== "function") return;
  node.animate([
    { opacity: 0, transform: `translate3d(${direction * 28}px,8px,0) scale(.985)`, filter: "blur(4px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 480, easing: SPRING });
}

function animateOut(node, direction = -1) {
  if (!node || REDUCED_MOTION.matches || typeof node.animate !== "function") return Promise.resolve();
  return node.animate([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${direction * 22}px,4px,0) scale(.985)`, filter: "blur(3px)" },
  ], { duration: 190, easing: "ease-out" }).finished.catch(() => {});
}

function safeTitle(node) {
  return compact(
    q("h1, h2, h3, strong, .my-work-item-copy h3, .media-info > strong", node)?.textContent
      || node.getAttribute("aria-label")
      || "Рабочий объект",
    140,
  );
}

function entityKind(node) {
  if (node.matches(".my-work-item")) return node.dataset.workItemType || "work";
  if (node.matches(".task-card")) return "task";
  if (node.matches(".placement-card")) return "placement";
  if (node.matches(".media-card")) return "media";
  if (node.matches("tr[data-payout-id]")) return routePath() === "/workspace/stats" ? "stats" : "payout";
  if (node.matches("[data-review-result-id]")) return "review";
  if (node.matches("[data-generation-job-id]")) return "generation";
  return "work";
}

function entityId(node, index = 0) {
  return String(
    node.dataset.workItemId
      || node.dataset.taskId
      || node.dataset.placementId
      || node.dataset.payoutId
      || node.dataset.reviewResultId
      || node.dataset.generationJobId
      || node.dataset.mediaFinderIndex
      || node.id
      || `${routePath()}:${index}`,
  ).trim();
}

function statusText(node) {
  return compact(
    q(".status-badge, .badge, .my-work-status, .my-work-overdue", node)?.textContent
      || (node.dataset.workItemBlocker === "true" ? "Блокер" : ""),
    70,
  );
}

function subtitleText(node) {
  return compact(
    q("p, small, .my-work-item-meta, .media-info > small", node)?.textContent || statusText(node),
    160,
  );
}

function routeIcon(route, kind = "") {
  if (/placement|publish/.test(route) || kind === "placement") return "publish";
  if (/stats/.test(route) || kind === "stats") return "stats";
  if (/payout/.test(route) || kind === "payout") return "money";
  if (/learn/.test(route)) return "learn";
  if (/task|work/.test(route) || kind === "task") return "task";
  if (/media/.test(route) || kind === "media") return "product";
  return "work";
}

function objectFromNode(node, index = 0) {
  const route = routePath();
  const kind = entityKind(node);
  const id = entityId(node, index);
  const title = safeTitle(node);
  const subtitle = subtitleText(node);
  const status = statusText(node);
  const blocked = node.dataset.workItemBlocker === "true" || /блокер|ошибк|отклон/u.test(`${status} ${subtitle}`.toLocaleLowerCase("ru-RU"));
  const action = q("a[href^='#/'], a[href^='http'], button[data-action]", node);
  const href = action?.tagName === "A" ? action.getAttribute("href") || `#${route}` : `#${route}`;
  const key = `${kind}:${id}`;
  return { key, id, kind, route, title, subtitle, status, blocked, href, node };
}

function registerObject(object) {
  if (!object?.key || !object?.title) return null;
  runtime.objects.set(object.key, object);
  return object;
}

function scanObjects() {
  const connected = new Set();
  qa(ENTITY_SELECTOR).forEach((node, index) => {
    const object = registerObject(objectFromNode(node, index));
    if (!object) return;
    connected.add(object.key);
    node.dataset.ceV3ObjectKey = object.key;
    if (!q(":scope > .ce-v3-object-button", node) && !node.matches("tr")) {
      const button = elementFrom(`<button class="ce-v3-object-button" type="button" aria-label="Открыть рабочую капсулу">${icon("product", 15)}<span>Капсула</span></button>`);
      button.dataset.ceV3OpenObject = object.key;
      node.append(button);
    }
  });
  for (const [key, object] of runtime.objects) {
    if (!object.node?.isConnected && !runtime.recent.some((entry) => entry.key === key)) runtime.objects.delete(key);
  }
  refreshStageRail();
  augmentMissionControl();
}

function touchRecent(object) {
  const sanitized = {
    key: object.key,
    id: object.id,
    kind: object.kind,
    route: object.route,
    title: object.title,
    subtitle: object.subtitle,
    status: object.status,
    blocked: object.blocked,
    href: object.href,
    at: Date.now(),
  };
  runtime.recent = [sanitized, ...runtime.recent.filter((entry) => entry.key !== sanitized.key)].slice(0, 8);
  writeJson(window.sessionStorage, V3_RECENT_KEY, runtime.recent);
  refreshStageRail();
}

function routeLabel(route) {
  const anchor = qa('.sidebar a[href^="#/"]').find((item) => routeFromHref(item.getAttribute("href")) === route);
  return compact(q("strong", anchor)?.textContent || anchor?.textContent || route.split("/").at(-1) || "Раздел", 48);
}

function capsuleLinks(object) {
  const links = [
    ["Материалы", "/workspace/media", "product"],
    ["Генерация", "/workspace/generation", "work"],
    ["Проверка", "/workspace/review", "task"],
    ["Публикации", "/workspace/placement", "publish"],
    ["Результаты", "/workspace/stats", "stats"],
    ["Выплаты", "/workspace/payouts", "money"],
  ];
  return links.map(([label, route, iconName]) => `
    <a href="#${route}" data-ce-v3-capsule-route="${route}">${icon(iconName, 18)}<span>${label}</span>${object.route === route ? "<i>сейчас</i>" : ""}</a>
  `).join("");
}

function closeCapsule({ restoreFocus = true, immediate = false } = {}) {
  const overlay = runtime.capsule;
  if (!overlay) return;
  const trigger = overlay._trigger;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    if (runtime.capsule === overlay) {
      runtime.capsule = null;
      document.body.classList.remove("ce-v3-capsule-open");
    }
    if (restoreFocus) trigger?.focus?.({ preventScroll: true });
  };
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 230);
}

function openObjectCapsule(key, trigger = document.activeElement) {
  const object = runtime.objects.get(key) || runtime.recent.find((entry) => entry.key === key);
  if (!object) return;
  closeSpotlight({ restoreFocus: false });
  closeCapsule({ restoreFocus: false, immediate: true });
  touchRecent(object);
  runtime.currentEntityKey = object.key;
  broadcastPresence(object.key, object.title);
  const overlay = elementFrom(`
    <div class="ce-v3-capsule-backdrop">
      <section class="ce-v3-capsule" role="dialog" aria-modal="true" aria-labelledby="ce-v3-capsule-title">
        <header>
          <div class="ce-v3-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
          <div><small>${escapeMarkup(routeLabel(object.route))} · ${escapeMarkup(object.kind)}</small><strong id="ce-v3-capsule-title">${escapeMarkup(object.title)}</strong></div>
          <button type="button" data-ce-v3-close-capsule aria-label="Закрыть">${icon("close", 19)}</button>
        </header>
        <div class="ce-v3-capsule__hero">
          <span class="ce-v3-capsule__icon">${icon(routeIcon(object.route, object.kind), 30)}</span>
          <div><small>Текущий контекст</small><strong>${escapeMarkup(object.status || "Рабочий объект")}</strong><p>${escapeMarkup(object.subtitle || "Откройте нужный этап производственного цикла.")}</p></div>
        </div>
        <nav class="ce-v3-capsule__routes" aria-label="Контур объекта">${capsuleLinks(object)}</nav>
        <div class="ce-v3-capsule__attention">
          <article><small>Состояние</small><strong>${object.blocked ? "Есть блокер" : object.status || "В работе"}</strong></article>
          <article><small>Последнее место</small><strong>${escapeMarkup(routeLabel(object.route))}</strong></article>
          <article><small>Память</small><strong>Состояние сохранено</strong></article>
        </div>
        <div class="ce-v3-capsule__actions">
          <a class="ce-v3-primary" href="${escapeMarkup(object.href || `#${object.route}`)}">Продолжить работу</a>
          <button type="button" data-ce-v3-local-action="handoff" data-entity-key="${escapeMarkup(object.key)}">${icon("handoff", 17)} Передать контекст</button>
          <button type="button" data-ce-v3-local-action="note" data-entity-key="${escapeMarkup(object.key)}">${icon("note", 17)} Заметка</button>
        </div>
        <div class="ce-v3-presence" data-ce-v3-presence-for="${escapeMarkup(object.key)}" hidden>${icon("warning", 16)} <span>Этот объект открыт в другой вкладке.</span></div>
      </section>
    </div>`);
  overlay._trigger = trigger;
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || event.target instanceof Element && event.target.closest("[data-ce-v3-close-capsule]")) closeCapsule();
  });
  document.body.append(overlay);
  runtime.capsule = overlay;
  document.body.classList.add("ce-v3-capsule-open");
  animateIn(q(".ce-v3-capsule", overlay));
  q("[data-ce-v3-close-capsule]", overlay)?.focus({ preventScroll: true });
  syncPresenceUi();
  dispatch("contentengine:os-v3-object-opened", { object });
}

function collectRoutes() {
  const routes = new Map();
  qa('.sidebar a[href^="#/"]').forEach((anchor) => {
    const route = routeFromHref(anchor.getAttribute("href"));
    if (!route || routes.has(route)) return;
    const title = compact(q("strong", anchor)?.textContent || anchor.textContent, 80);
    if (!title) return;
    routes.set(route, { id: `route:${route}`, kind: "route", title, subtitle: "Открыть рабочее пространство", route, href: `#${route}` });
  });
  if (!routes.has("/learn")) routes.set("/learn", { id: "route:/learn", kind: "route", title: "Академия", subtitle: "Обучение и практика", route: "/learn", href: "#/learn" });
  return [...routes.values()];
}
