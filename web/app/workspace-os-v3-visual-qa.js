/*
 * ContentEngine OS v3.2 visual QA cleanup.
 *
 * One screen / one action, one global Dock, clean route isolation, scalable
 * search/folders and a lightweight interactive home. This module is built with
 * DOM APIs only: no HTML-string reinterpretation, no business API calls, no
 * native form submission and no cloning of application controls.
 */

const CLEAN_BUILD = "20260731.os3.2";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const TYPING = "input, textarea, select, [contenteditable='true']";
const SVG_NS = "http://www.w3.org/2000/svg";

const ROUTES = Object.freeze([
  { route: "/workspace/home", label: "Сегодня", hint: "Один следующий шаг", icon: "home" },
  { route: "/workspace/work", label: "Моя работа", hint: "Сейчас, жду, дальше", icon: "work" },
  { route: "/workspace/media", label: "Материалы", hint: "Папки, поиск и Quick Look", icon: "media" },
  { route: "/workspace/generation", label: "Создание", hint: "Один запуск по шагам", icon: "generate" },
  { route: "/workspace/review", label: "Проверка", hint: "Один риск и одно решение", icon: "review" },
  { route: "/workspace/tasks", label: "Задачи", hint: "Одна задача на столе", icon: "tasks" },
  { route: "/workspace/placement", label: "Публикации", hint: "Один пост — один маршрут", icon: "publish" },
  { route: "/workspace/stats", label: "Результаты", hint: "Сравнение и вывод", icon: "stats" },
  { route: "/workspace/payouts", label: "Выплаты", hint: "Основание и статус", icon: "money" },
  { route: "/learn", label: "Академия", hint: "Урок и безопасная практика", icon: "learn" },
]);

const ICONS = Object.freeze({
  home: [["path", { d: "m3 11 9-8 9 8" }], ["path", { d: "M5 10v10h14V10M9 20v-6h6v6" }]],
  work: [["rect", { x: "3", y: "6", width: "18", height: "14", rx: "3" }], ["path", { d: "M8 6V4h8v2M3 11h18M9 11v2h6v-2" }]],
  media: [["rect", { x: "3", y: "4", width: "18", height: "16", rx: "3" }], ["path", { d: "m7 16 3.5-4 3 3 2-2 2.5 3" }], ["circle", { cx: "8", cy: "8.5", r: "1.3" }]],
  generate: [["path", { d: "M12 3v4M12 17v4M3 12h4M17 12h4" }], ["circle", { cx: "12", cy: "12", r: "3" }]],
  review: [["rect", { x: "5", y: "4", width: "14", height: "17", rx: "2.5" }], ["path", { d: "M9 8h6M9 12h6M9 16h3" }], ["path", { d: "m14 16 1.5 1.5L19 14" }]],
  tasks: [["path", { d: "M9 6h11M9 12h11M9 18h11" }], ["path", { d: "m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5" }]],
  publish: [["path", { d: "M12 3v12" }], ["path", { d: "m7 8 5-5 5 5" }], ["path", { d: "M5 13v6h14v-6" }]],
  stats: [["path", { d: "M4 20V9M10 20V4M16 20v-7M22 20H2" }]],
  money: [["rect", { x: "3", y: "5", width: "18", height: "14", rx: "3" }], ["path", { d: "M7 9h10M7 15h4" }], ["circle", { cx: "16", cy: "14", r: "2" }]],
  learn: [["path", { d: "m3 7 9-4 9 4-9 4-9-4Z" }], ["path", { d: "M6 9v6c3 2 9 2 12 0V9" }]],
  grid: [["rect", { x: "3", y: "3", width: "7", height: "7", rx: "2" }], ["rect", { x: "14", y: "3", width: "7", height: "7", rx: "2" }], ["rect", { x: "3", y: "14", width: "7", height: "7", rx: "2" }], ["rect", { x: "14", y: "14", width: "7", height: "7", rx: "2" }]],
  search: [["circle", { cx: "11", cy: "11", r: "7" }], ["path", { d: "m20 20-4-4" }]],
  close: [["path", { d: "m6 6 12 12M18 6 6 18" }]],
  left: [["path", { d: "m15 18-6-6 6-6" }]],
  right: [["path", { d: "m9 18 6-6-6-6" }]],
  folder: [["path", { d: "M3 7h7l2 2h9v10H3V7Z" }]],
  info: [["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 11v6M12 7h.01" }]],
});

const runtime = {
  queued: false,
  route: routePath(),
  mission: null,
  zen: null,
  zenPlaceholder: null,
  zenClose: null,
  zenScroll: 0,
  videoObserver: null,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function routeMatches(current, target) {
  return current === target || (target === "/learn" && current.startsWith("/learn/"));
}

function compact(value, limit = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function make(tag, options = {}, children = []) {
  const element = document.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = String(options.text);
  for (const [name, value] of Object.entries(options.attrs || {})) {
    if (value !== null && value !== undefined) element.setAttribute(name, String(value));
  }
  for (const [name, value] of Object.entries(options.dataset || {})) {
    if (value !== null && value !== undefined) element.dataset[name] = String(value);
  }
  append(element, children);
  return element;
}

function append(parent, children) {
  const list = Array.isArray(children) ? children.flat(Infinity) : [children];
  list.forEach((child) => {
    if (child === null || child === undefined || child === false) return;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  });
  return parent;
}

function textNode(tag, text, className = "") {
  return make(tag, { text, className });
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
  (ICONS[name] || ICONS.info).forEach(([tag, attrs]) => {
    const child = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => child.setAttribute(key, value));
    svg.append(child);
  });
  return svg;
}

function buttonWithIcon(label, iconName, className = "") {
  const button = make("button", { className, attrs: { type: "button" } });
  append(button, [icon(iconName, 18), textNode("span", label)]);
  return button;
}

function isVisible(element) {
  if (!(element instanceof Element) || element.hidden) return false;
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function routeDescriptor(route = routePath()) {
  return ROUTES.find((item) => routeMatches(route, item.route)) || ROUTES[0];
}

function navigate(route) {
  closeMission({ restoreFocus: false });
  closeZen({ restoreFocus: false, immediate: true });
  window.location.hash = `#${String(route || "/workspace/home")}`;
}

function directChildFor(page, node) {
  let current = node;
  while (current?.parentElement && current.parentElement !== page) current = current.parentElement;
  return current?.parentElement === page ? current : null;
}

function markKeep(page, node) {
  const direct = directChildFor(page, node);
  if (direct) direct.dataset.osCleanKeep = "true";
}

function cleanPageConfig() {
  const path = routePath();
  if (path === "/workspace/review") return [".content-review-page", [".review-os-topbar", ".review-os-workbench"]];
  if (path === "/workspace/generation") return [".generation-desktop-os", [".generation-os-topbar", ".generation-os-workbench"]];
  if (path === "/workspace/media") return [".media-finder-page", [".media-finder-topbar", ".media-finder-shell"]];
  if (path === "/workspace/work") return [".work-stage-page", [".work-stage-topbar", ".work-stage-shell"]];
  if (path === "/workspace/tasks") return [".tasks-desk-page", [".tasks-desk-topbar", ".tasks-desk-shell"]];
  if (path === "/workspace/placement") return [".publishing-os-page, .page-wrap", [".publishing-os-topbar", ".publishing-os-shell"]];
  if (path === "/workspace/stats") return [".results-os-page", [".results-os-topbar", ".results-os-shell"]];
  if (path === "/workspace/payouts") return [".payout-ledger-page", [".payout-ledger-topbar", ".payout-ledger-shell"]];
  if (path.startsWith("/learn")) return [".learning-page", [".academy-os-window", ".academy-course-os-window--v2", ".academy-course-os-window"]];
  return null;
}

function isolateCurrentPage() {
  const config = cleanPageConfig();
  if (!config) return;
  const [pageSelector, keepSelectors] = config;
  const page = q(pageSelector);
  if (!page) return;
  page.classList.add("os-clean-page");
  qa(":scope > [data-os-clean-keep]", page).forEach((node) => delete node.dataset.osCleanKeep);
  keepSelectors.forEach((selector) => qa(selector, page).forEach((node) => markKeep(page, node)));
  qa(":scope > .alert-danger, :scope > .alert-warning", page).forEach((node) => { node.dataset.osCleanKeep = "true"; });
}

function homeSourceFacts(page) {
  const source = q(".home-next-action, [data-workspace-primary], .home-next-step", page);
  const action = q("a[href^='#/'], button[data-action]", source);
  const title = compact(q("h1, h2, h3, strong", source)?.textContent || "Продолжить производственный маршрут", 120);
  const hint = compact(q("p:not(.eyebrow), .muted, small", source)?.textContent || "Откройте следующий этап и завершите одно понятное действие.", 220);
  const href = action instanceof HTMLAnchorElement ? action.getAttribute("href") || "" : "";
  const route = href.startsWith("#/") ? href.slice(1).split("?")[0] : "";
  return { action, title, hint, route };
}

function buildHome(facts) {
  const home = make("section", { className: "os-clean-home", dataset: { osCleanKeep: "true" } });
  const top = make("header", { className: "os-clean-home__top" });
  const topCopy = make("div", {}, [textNode("small", "CONTENTENGINE · РАБОЧЕЕ МЕСТО"), textNode("strong", "Сегодня")]);
  const mission = buttonWithIcon("Все столы", "grid");
  mission.dataset.osCleanMission = "true";
  append(top, [topCopy, mission]);

  const body = make("main", { className: "os-clean-home__body" });
  const action = make("section", { className: "os-clean-home__action", attrs: { "aria-labelledby": "os-clean-home-title" } });
  const eyebrow = textNode("small", "ОДИН ЭКРАН · ОДНО ДЕЙСТВИЕ");
  const title = textNode("h1", facts.title);
  title.id = "os-clean-home-title";
  const hint = textNode("p", facts.hint);
  hint.dataset.osCleanHomeHint = "true";
  const primary = buttonWithIcon("Открыть следующий шаг", "right");
  primary.dataset.osCleanHomePrimary = "true";
  append(action, [eyebrow, title, hint, primary]);

  const routeAside = make("aside", { className: "os-clean-home__route", attrs: { "aria-label": "Производственный маршрут" } });
  append(routeAside, make("header", {}, [textNode("small", "МАРШРУТ"), textNode("strong", "7 этапов без свалки")]));
  const nav = make("nav");
  const productionRoutes = ROUTES.filter((item) => [
    "/workspace/media", "/workspace/generation", "/workspace/review",
    "/workspace/tasks", "/workspace/placement", "/workspace/stats", "/workspace/payouts",
  ].includes(item.route));
  productionRoutes.forEach((item, index) => {
    const button = make("button", {
      attrs: { type: "button", "aria-label": item.label },
      dataset: { osCleanStageRoute: item.route, stageIndex: index },
    }, [
      textNode("span", String(index + 1).padStart(2, "0")),
      textNode("strong", item.label),
      textNode("small", item.hint),
    ]);
    nav.append(button);
  });
  routeAside.append(nav);
  append(body, [action, routeAside]);
  append(home, [top, body]);
  return home;
}

function setupHome() {
  if (routePath() !== "/workspace/home") return;
  const page = q("#workspace-content .page-wrap, #workspace-content, .workspace-main .page-wrap");
  if (!page || q(":scope > .os-clean-home", page)) return;
  const facts = homeSourceFacts(page);
  const home = buildHome(facts);
  page.prepend(home);
  page.classList.add("os-clean-home-ready", "os-clean-page");
  qa(":scope > *", page).forEach((node) => { if (node === home) node.dataset.osCleanKeep = "true"; });

  const title = q("#os-clean-home-title", home);
  const hint = q("[data-os-clean-home-hint]", home);
  const primary = q("[data-os-clean-home-primary]", home);
  let selectedRoute = facts.route || "/workspace/work";
  const updateStage = (route) => {
    const descriptor = routeDescriptor(route);
    selectedRoute = descriptor.route;
    title.textContent = descriptor.label;
    hint.textContent = descriptor.hint;
    qa("[data-os-clean-stage-route]", home).forEach((button) => {
      const active = button.dataset.osCleanStageRoute === selectedRoute;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-current", active ? "step" : "false");
    });
    q("span", primary).textContent = `Открыть: ${descriptor.label}`;
  };
  qa("[data-os-clean-stage-route]", home).forEach((button) => {
    button.addEventListener("click", () => updateStage(button.dataset.osCleanStageRoute));
  });
  primary.addEventListener("click", () => {
    if (!selectedRoute && facts.action) facts.action.click();
    else navigate(selectedRoute || facts.route || "/workspace/work");
  });
  q("[data-os-clean-mission]", home)?.addEventListener("click", openMission);
  updateStage(selectedRoute);
}

function buildMission() {
  const backdrop = make("div", { className: "os-clean-mission-backdrop" });
  const dialog = make("section", {
    className: "os-clean-mission",
    attrs: { role: "dialog", "aria-modal": "true", "aria-labelledby": "os-clean-mission-title" },
  });
  const header = make("header");
  const copy = make("div", {}, [
    textNode("small", "MISSION CONTROL"),
    textNode("h1", "Рабочие столы"),
    textNode("p", "Откройте одно направление. Остальные не конкурируют за внимание."),
  ]);
  q("h1", copy).id = "os-clean-mission-title";
  const close = make("button", { attrs: { type: "button", "aria-label": "Закрыть" }, dataset: { osCleanMissionClose: "true" } }, [icon("close", 20)]);
  append(header, [copy, close]);

  const searchLabel = make("label", { className: "os-clean-mission__search" }, [icon("search", 18)]);
  const input = make("input", { attrs: { type: "search", placeholder: "Найти стол", autocomplete: "off" } });
  searchLabel.append(input);

  const grid = make("div", { className: "os-clean-mission__grid" });
  ROUTES.forEach((item, index) => {
    const button = make("button", {
      attrs: { type: "button" },
      dataset: {
        osCleanMissionRoute: item.route,
        keywords: `${item.label} ${item.hint}`.toLocaleLowerCase("ru-RU"),
      },
    }, [
      make("span", {}, [icon(item.icon, 24)]),
      textNode("small", String(index + 1).padStart(2, "0")),
      textNode("strong", item.label),
      textNode("p", item.hint),
    ]);
    grid.append(button);
  });
  append(dialog, [header, searchLabel, grid]);
  backdrop.append(dialog);
  return backdrop;
}

function openMission(event) {
  event?.preventDefault?.();
  if (runtime.mission) return;
  const overlay = buildMission();
  runtime.mission = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-clean-mission-open");
  const input = q("input", overlay);
  input.addEventListener("input", () => {
    const query = String(input.value || "").trim().toLocaleLowerCase("ru-RU");
    qa("[data-os-clean-mission-route]", overlay).forEach((button) => {
      button.hidden = Boolean(query) && !String(button.dataset.keywords || "").includes(query);
    });
  });
  overlay.addEventListener("click", (click) => {
    if (click.target === overlay || (click.target instanceof Element && click.target.closest("[data-os-clean-mission-close]"))) closeMission();
    const button = click.target instanceof Element ? click.target.closest("[data-os-clean-mission-route]") : null;
    if (button) navigate(button.dataset.osCleanMissionRoute);
  });
  q("[data-os-clean-mission-close]", overlay)?.focus({ preventScroll: true });
}

function closeMission({ restoreFocus = true } = {}) {
  const overlay = runtime.mission;
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    if (runtime.mission === overlay) runtime.mission = null;
    document.body.classList.remove("os-clean-mission-open");
    if (restoreFocus) q(".ce-mac-dock__mission, [data-os-clean-mission]")?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function zenSurface() {
  const path = routePath();
  const selectors = path === "/workspace/review" ? [".review-os-workbench"]
    : path === "/workspace/generation" ? [".generation-os-workbench"]
      : path === "/workspace/media" ? [".media-finder-shell"]
        : path === "/workspace/work" ? [".work-stage-shell"]
          : path === "/workspace/tasks" ? [".tasks-desk-shell"]
            : path === "/workspace/placement" ? [".publishing-os-shell"]
              : path === "/workspace/stats" ? [".results-os-shell"]
                : path === "/workspace/payouts" ? [".payout-ledger-shell"]
                  : path.startsWith("/learn") ? [".academy-course-os-window--v2", ".academy-os-window", ".academy-course-os-window"]
                    : [".os-clean-home"];
  return selectors.map((selector) => q(selector)).find((node) => isVisible(node)) || null;
}

function convertFocusButtons() {
  qa("[data-workspace-focus-card], .desk-focus-button").forEach((button) => {
    button.removeAttribute("data-workspace-focus-card");
    button.dataset.osCleanZen = "true";
    button.setAttribute("aria-label", "Развернуть текущее рабочее пространство");
    const label = q(".desk-focus-button__label", button);
    if (label) label.textContent = "Фокус";
  });
}

function rescueLegacyFocus() {
  qa(".workspace-task-focused").forEach((surface) => {
    surface.classList.remove("workspace-task-focused");
    surface.removeAttribute("aria-modal");
    q(":scope > .workspace-focus-chrome", surface)?.remove();
  });
  qa(".workspace-focus-backdrop").forEach((node) => node.remove());
  document.body.classList.remove("workspace-focus-mode");
}

function openZen(surface = zenSurface()) {
  if (!surface || runtime.zen) return;
  rescueLegacyFocus();
  const placeholder = document.createComment("contentengine-os-clean-zen");
  surface.before(placeholder);
  runtime.zen = surface;
  runtime.zenPlaceholder = placeholder;
  runtime.zenScroll = window.scrollY;
  surface.classList.add("os-clean-zen-surface");
  const close = buttonWithIcon("Вернуться", "close", "os-clean-zen-close");
  close.setAttribute("aria-label", "Закрыть фокус");
  close.addEventListener("click", () => closeZen());
  surface.prepend(close);
  runtime.zenClose = close;
  document.body.append(surface);
  document.body.classList.add("os-clean-zen-open");
  close.focus({ preventScroll: true });
}

function closeZen({ restoreFocus = true, immediate = false } = {}) {
  const surface = runtime.zen;
  if (!surface) return;
  const placeholder = runtime.zenPlaceholder;
  const close = runtime.zenClose;
  const finish = () => {
    close?.remove();
    surface.classList.remove("os-clean-zen-surface", "is-closing");
    if (placeholder?.parentNode) placeholder.before(surface);
    else surface.remove();
    placeholder?.remove?.();
    runtime.zen = null;
    runtime.zenPlaceholder = null;
    runtime.zenClose = null;
    document.body.classList.remove("os-clean-zen-open");
    window.scrollTo({ top: runtime.zenScroll, left: 0, behavior: "auto" });
    if (restoreFocus) q("[data-os-clean-zen]")?.focus?.({ preventScroll: true });
    scheduleMount();
  };
  surface.classList.add("is-closing");
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function canonicalDockRoute(anchor) {
  const href = String(anchor.getAttribute("href") || "");
  const route = href.startsWith("#/") ? href.slice(1).split("?")[0].replace(/\/$/, "") : "";
  return route.startsWith("/learn/") ? "/learn" : route;
}

function dockTool(label, iconName, className) {
  const button = make("button", { className: `ce-mac-dock__item ${className}`, attrs: { type: "button", "aria-label": label } });
  append(button, [textNode("span", label, "ce-mac-dock__tooltip"), make("span", { className: "ce-mac-dock__icon" }, [icon(iconName, 22)])]);
  return button;
}

function cleanDock() {
  const glass = q(".ce-mac-dock__glass");
  if (!glass) return;
  q(".os-v3-dock-tools", glass)?.remove();
  qa(".ce-mac-dock__separator", glass).forEach((node) => node.remove());
  const byRoute = new Map();
  qa("a.ce-mac-dock__item", glass).forEach((link) => {
    const route = canonicalDockRoute(link);
    if (!ROUTES.some((item) => item.route === route) || byRoute.has(route)) {
      link.remove();
      return;
    }
    byRoute.set(route, link);
    link.href = `#${route}`;
    const descriptor = routeDescriptor(route);
    link.setAttribute("aria-label", descriptor.label);
    const tooltip = q(".ce-mac-dock__tooltip", link);
    if (tooltip) tooltip.textContent = descriptor.label;
  });

  let mission = q(".ce-mac-dock__mission", glass);
  if (!mission) mission = dockTool("Все столы", "grid", "ce-mac-dock__mission");
  mission.dataset.osCleanMission = "true";
  ROUTES.forEach((item) => {
    const link = byRoute.get(item.route);
    if (link) glass.append(link);
  });
  glass.append(make("span", { className: "ce-mac-dock__separator os-clean-dock-separator", attrs: { "aria-hidden": "true" } }), mission);
  let search = q(".os-clean-dock-search", glass);
  if (!search) {
    search = dockTool("Поиск · ⌘K", "search", "os-clean-dock-search");
    search.addEventListener("click", () => window.ContentEngineOSV3?.openSpotlight?.());
  }
  glass.append(search);
}

function taskSource(text) {
  const value = String(text || "").toLocaleLowerCase("ru-RU");
  if (/публикац|размест|ссылка|url/u.test(value)) return "Публикации";
  if (/провер|review|qa|риск/u.test(value)) return "Проверка";
  if (/генерац|ролик|runway|seedance|создать контент/u.test(value)) return "Создание контента";
  if (/выплат|начислен/u.test(value)) return "Выплаты";
  return "Ручная задача";
}

function buildTaskFilter() {
  const filter = make("div", { className: "os-clean-task-filter" });
  const label = make("label", {}, [icon("search", 16)]);
  label.append(make("input", { attrs: { type: "search", placeholder: "Найти задачу", autocomplete: "off" } }));
  const select = make("select", { attrs: { "aria-label": "Статус задачи" } });
  [["all", "Все"], ["active", "В работе"], ["blocked", "Блокеры"], ["done", "Готовые"]].forEach(([value, labelText]) => {
    select.append(make("option", { text: labelText, attrs: { value } }));
  });
  append(filter, [label, select, make("span", { dataset: { osCleanTaskCount: "true" } })]);
  return filter;
}

function enhanceTasks() {
  const shell = q(".tasks-desk-shell");
  if (!shell) return;
  const list = q(".tasks-desk-list", shell);
  if (list && !q(".os-clean-task-filter", shell)) {
    const filter = buildTaskFilter();
    list.before(filter);
    const apply = () => {
      const query = String(q("input", filter).value || "").trim().toLocaleLowerCase("ru-RU");
      const status = q("select", filter).value;
      let visible = 0;
      qa(".tasks-desk-list-item", list).forEach((item) => {
        const text = String(item.textContent || "").toLocaleLowerCase("ru-RU");
        const tone = q("i[data-tone]", item)?.dataset.tone || "";
        const matchStatus = status === "all"
          || (status === "blocked" && tone === "danger")
          || (status === "done" && tone === "success")
          || (status === "active" && !["danger", "success"].includes(tone));
        const show = matchStatus && (!query || text.includes(query));
        item.hidden = !show;
        if (show) visible += 1;
      });
      q("[data-os-clean-task-count]", filter).textContent = `${visible} видно`;
      const active = q(".tasks-desk-list-item.is-active", list);
      if (active?.hidden) qa(".tasks-desk-list-item", list).find((item) => !item.hidden)?.click();
    };
    filter.addEventListener("input", apply);
    filter.addEventListener("change", apply);
    apply();
  }
  qa(".tasks-desk-card", shell).forEach((card) => {
    if (q(":scope > .os-clean-task-origin", card)) return;
    const source = taskSource(compact(card.textContent, 1200));
    const description = compact(q("p:not(.eyebrow), .task-description, .muted", card)?.textContent || "Выполните критерий задачи и используйте штатную кнопку смены статуса.", 190);
    const origin = make("aside", { className: "os-clean-task-origin" }, [
      textNode("small", "ИСТОЧНИК ЗАДАЧИ"),
      textNode("strong", source),
      textNode("p", description),
    ]);
    const header = q(":scope > .task-top, :scope > header", card);
    if (header) header.after(origin);
    else card.prepend(origin);
  });
}

function mediaKindLabel(kind) {
  return ({ product: "Товар", reference: "Референс", video: "Видео", image: "Без папки" })[kind] || "Без папки";
}

function enhanceMedia() {
  const page = q(".media-finder-page");
  if (!page) return;
  qa(".media-card", page).forEach((card) => {
    if (q(".os-clean-media-kind", card)) return;
    const kind = String(card.dataset.mediaFinderKind || (card.dataset.mediaFinderType === "video" ? "video" : "image"));
    const badge = textNode("span", mediaKindLabel(kind), "os-clean-media-kind");
    badge.dataset.kind = kind;
    q(".media-info", card)?.prepend(badge);
  });
  const nav = q(".media-finder-sidebar nav", page);
  if (!nav || q("[data-os-media-folder='uncategorized']", nav)) return;
  const uncategorized = make("button", { attrs: { type: "button" }, dataset: { osMediaFolder: "uncategorized" } }, [
    icon("folder", 17), textNode("span", "Без папки"), textNode("b", "0"),
  ]);
  nav.append(uncategorized);
  const applyUnsorted = () => {
    const active = page.dataset.osMediaCustomFolder === "uncategorized";
    let count = 0;
    qa(".media-card", page).forEach((card) => {
      const match = String(card.dataset.mediaFinderKind || "image") === "image";
      if (match) count += 1;
      if (active) card.hidden = !match;
    });
    q("b", uncategorized).textContent = String(count);
    uncategorized.classList.toggle("is-active", active);
  };
  uncategorized.addEventListener("click", () => {
    page.dataset.osMediaCustomFolder = "uncategorized";
    qa("[data-media-folder]", nav).forEach((item) => item.classList.remove("is-active"));
    applyUnsorted();
  });
  nav.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-media-folder]")) {
      delete page.dataset.osMediaCustomFolder;
      window.setTimeout(applyUnsorted, 0);
    }
  });
  q("[data-media-search]", page)?.addEventListener("input", () => window.setTimeout(applyUnsorted, 0));
  applyUnsorted();
}

function buildTableSearch() {
  const toolbar = make("div", { className: "os-clean-table-search" });
  const label = make("label", {}, [icon("search", 16)]);
  label.append(make("input", { attrs: { type: "search", placeholder: "Поиск по реестру", autocomplete: "off" } }));
  append(toolbar, [label, textNode("span", "")]);
  return toolbar;
}

function enhanceTableSearch() {
  qa(".results-ledger-shell, .payout-ledger-shell").forEach((shell) => {
    qa(".data-table", shell).forEach((table, index) => {
      const holder = table.closest(".table-wrap, .data-table-wrap") || table;
      if (holder.previousElementSibling?.classList?.contains("os-clean-table-search")) return;
      const toolbar = buildTableSearch();
      holder.before(toolbar);
      const rows = qa("tbody tr", table);
      const apply = () => {
        const query = String(q("input", toolbar).value || "").trim().toLocaleLowerCase("ru-RU");
        let shown = 0;
        rows.forEach((row) => {
          const match = !query || String(row.textContent || "").toLocaleLowerCase("ru-RU").includes(query);
          row.hidden = !match;
          if (match) shown += 1;
        });
        q("span", toolbar).textContent = `${shown} из ${rows.length}`;
      };
      toolbar.dataset.tableIndex = String(index);
      toolbar.addEventListener("input", apply);
      apply();
    });
  });
}

function enhanceReviewRisks() {
  qa(".content-review-findings").forEach((container) => {
    if (container.dataset.osCleanRiskNavigator === "true") return;
    const cards = qa(":scope > article, :scope > .card, :scope > .content-review-finding, :scope > .finding-card", container)
      .filter((card) => !card.matches("header"));
    if (cards.length < 4) return;
    container.dataset.osCleanRiskNavigator = "true";
    let index = 0;
    const nav = make("div", { className: "os-clean-risk-nav" });
    const previous = buttonWithIcon("Назад", "left");
    previous.dataset.riskPrev = "true";
    const position = textNode("strong", "");
    position.dataset.riskPosition = "true";
    const next = buttonWithIcon("Далее", "right");
    next.dataset.riskNext = "true";
    append(nav, [previous, position, next]);
    container.prepend(nav);
    const show = (nextIndex) => {
      index = Math.max(0, Math.min(cards.length - 1, nextIndex));
      cards.forEach((card, cardIndex) => {
        card.hidden = cardIndex !== index;
        card.classList.toggle("is-active", cardIndex === index);
      });
      position.textContent = `Риск ${index + 1} из ${cards.length}`;
      previous.disabled = index <= 0;
      next.disabled = index >= cards.length - 1;
    };
    nav.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("[data-risk-prev]")) show(index - 1);
      if (event.target instanceof Element && event.target.closest("[data-risk-next]")) show(index + 1);
    });
    show(0);
  });
}

function buildPublishingEmpty() {
  const empty = make("div", { className: "os-clean-publishing-empty" });
  append(empty, [
    make("span", {}, [icon("publish", 28)]),
    textNode("strong", "Публикаций пока нет"),
    textNode("p", "Сначала завершите проверку одного материала — после этого появится маршрут публикации."),
    make("a", { text: "Открыть проверку", attrs: { href: "#/workspace/review" } }),
  ]);
  return empty;
}

function recoverPublishing() {
  const shell = q(".publishing-os-shell");
  if (!shell) return;
  const cards = qa(".placement-card", shell);
  const visibleCards = cards.filter((card) => !card.hidden && isVisible(card));
  if (cards.length && !visibleCards.length) q("[data-publishing-filter='all']")?.click();
  const queue = q(".publishing-os-queue, .publishing-os-sidebar", shell);
  if (!cards.length && queue && !q(".os-clean-publishing-empty", shell)) {
    q(".publishing-os-stage, .publishing-os-workspace", shell)?.append(buildPublishingEmpty());
  }
}

function videoGovernor() {
  qa("video").forEach((video) => {
    video.autoplay = false;
    video.loop = false;
    video.removeAttribute("autoplay");
    video.removeAttribute("loop");
    video.playsInline = true;
    if (!video.hasAttribute("preload") || video.preload === "auto") video.preload = "metadata";
    if (!isVisible(video)) video.pause?.();
    if (runtime.videoObserver && video.dataset.osCleanObserved !== "true") {
      video.dataset.osCleanObserved = "true";
      runtime.videoObserver.observe(video);
    }
  });
}

function setupVideoGovernor() {
  if (!runtime.videoObserver && typeof IntersectionObserver === "function") {
    runtime.videoObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting || entry.intersectionRatio < 0.15) entry.target.pause?.();
      });
    }, { threshold: [0, 0.15, 0.6] });
  }
  videoGovernor();
}

function removeBrokenSplitEntryPoints() {
  q(".os-v3-dock-tools")?.remove();
  qa("[data-os-v3-capsule-split]").forEach((button) => button.remove());
  qa(".os-v3-command-palette button").forEach((button) => {
    if (/split view|два связанных рабочих объекта/iu.test(button.textContent || "")) button.remove();
  });
}

function mount() {
  document.documentElement.dataset.contentengineClean = "v3-2";
  document.body.classList.add("contentengine-os-clean");
  const route = routePath();
  if (runtime.route !== route) {
    runtime.route = route;
    closeMission({ restoreFocus: false });
    closeZen({ restoreFocus: false, immediate: true });
  }
  rescueLegacyFocus();
  setupHome();
  isolateCurrentPage();
  convertFocusButtons();
  cleanDock();
  enhanceTasks();
  enhanceMedia();
  enhanceTableSearch();
  enhanceReviewRisks();
  recoverPublishing();
  setupVideoGovernor();
  removeBrokenSplitEntryPoints();
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-os-clean-zen]")) {
    event.preventDefault();
    event.stopImmediatePropagation();
    openZen();
    return;
  }
  if (target.closest("[data-ce-open-mission], .ce-mac-dock__mission, [data-os-clean-mission]")) {
    event.preventDefault();
    openMission(event);
  }
}, true);

document.addEventListener("keydown", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest(TYPING)) return;
  if (event.key === "Escape") {
    if (runtime.zen) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeZen();
      return;
    }
    if (runtime.mission) {
      event.preventDefault();
      closeMission();
      return;
    }
  }
  if (event.key.toLocaleLowerCase("ru-RU") === "f" && !event.metaKey && !event.ctrlKey && !event.altKey) {
    const surface = zenSurface();
    if (surface) {
      event.preventDefault();
      event.stopImmediatePropagation();
      openZen(surface);
    }
  }
  if (event.altKey && event.shiftKey && event.key.toLocaleLowerCase("ru-RU") === "s") {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

document.addEventListener("play", (event) => {
  const video = event.target;
  if (!(video instanceof HTMLVideoElement)) return;
  qa("video").forEach((candidate) => {
    if (candidate !== video && !candidate.paused) candidate.pause();
  });
}, true);

new MutationObserver(scheduleMount).observe(q("#app") || document.body, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount, { passive: true });
window.addEventListener("pageshow", scheduleMount, { passive: true });
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();

window.ContentEngineVisualQA = Object.freeze({
  build: CLEAN_BUILD,
  openMission,
  openZen,
  closeZen,
  scheduleMount,
});
