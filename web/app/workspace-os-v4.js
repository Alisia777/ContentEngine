/*
 * ContentEngine Desktop v4.
 *
 * One web workspace, one Dock, one visible action. This module composes the
 * already permission-checked DOM. It never calls business APIs, submits forms,
 * reads secrets or clones file inputs.
 */

const BUILD = "20260731.os4.0";
const STORAGE_KEY = "contentengine.desktop-v4.v1";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const WORK_SNAPSHOT_KEY = "contentengine.os-v3.work-snapshot.v1";
const SVG_NS = "http://www.w3.org/2000/svg";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/home", label: "Сегодня", icon: "home", description: "Один следующий шаг без шума" }),
  Object.freeze({ route: "/workspace/board", label: "Finder", icon: "folder", description: "Папки, материалы и задачи" }),
  Object.freeze({ route: "/workspace/generation", label: "Создание", icon: "spark", description: "Один запуск за раз" }),
  Object.freeze({ route: "/workspace/review", label: "Проверка", icon: "check", description: "Качество, риски и решение" }),
  Object.freeze({ route: "/workspace/work", label: "Моя работа", icon: "work", description: "Сейчас, жду и дальше" }),
  Object.freeze({ route: "/workspace/tasks", label: "Задачи", icon: "tasks", description: "Назначенная работа и источник" }),
  Object.freeze({ route: "/workspace/placement", label: "Публикации", icon: "upload", description: "Один пост — один маршрут" }),
  Object.freeze({ route: "/workspace/stats", label: "Результаты", icon: "chart", description: "Цифры и следующая гипотеза" }),
  Object.freeze({ route: "/workspace/payouts", label: "Выплаты", icon: "money", description: "Основание, решение и перевод" }),
  Object.freeze({ route: "/learn", label: "Академия", icon: "academy", description: "Урок и безопасная практика" }),
]);

const STAGES = Object.freeze([
  Object.freeze({ number: "01", label: "Материалы", route: "/workspace/board", description: "Соберите точный товар, исходники и референсы." }),
  Object.freeze({ number: "02", label: "Создание", route: "/workspace/generation", description: "Подготовьте один проверяемый запуск." }),
  Object.freeze({ number: "03", label: "Проверка", route: "/workspace/review", description: "Проверьте качество, товар и риски." }),
  Object.freeze({ number: "04", label: "Задачи", route: "/workspace/tasks", description: "Закройте решение, которое требует человека." }),
  Object.freeze({ number: "05", label: "Публикации", route: "/workspace/placement", description: "Разместите материал и сохраните ссылку." }),
  Object.freeze({ number: "06", label: "Результаты", route: "/workspace/stats", description: "Зафиксируйте цифры и вывод." }),
  Object.freeze({ number: "07", label: "Выплаты", route: "/workspace/payouts", description: "Проверьте основание и статус начисления." }),
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
  academy: ["m3 6 9-3 9 3-9 3-9-3Z", "M6 8v6c3 2 9 2 12 0V8M21 6v7"],
  grid: ["M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z", "m16 16 4 4"],
  focus: ["M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"],
  close: ["m6 6 12 12M18 6 6 18"],
  left: ["m15 18-6-6 6-6"],
  right: ["m9 18 6-6-6-6"],
  clock: ["M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z", "M12 8v5l3 2"],
});

const runtime = {
  route: routePath(),
  queued: false,
  menubar: null,
  dock: null,
  dockFrame: 0,
  dockEvent: null,
  mission: null,
  spotlight: null,
  spotlightRecords: [],
  spotlightIndex: 0,
  zen: null,
  videoObserver: null,
  observedVideos: new WeakSet(),
  clockTimer: 0,
  scrollTimer: 0,
  restoredRoute: "",
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

function routeMatches(route, expected) {
  return expected === "/learn" ? route === "/learn" || route.startsWith("/learn/") : route === expected;
}

function routeRecord(route = routePath()) {
  return ROUTES.find((item) => routeMatches(route, item.route)) || ROUTES[0];
}

function isWorkspaceRoute(route = routePath()) {
  return route.startsWith("/workspace/") || route === "/learn" || route.startsWith("/learn/");
}

function navigate(route) {
  closeTransientOverlays(true);
  window.location.hash = `#${route || "/workspace/home"}`;
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

  const location = create("div", "ce-v4-menubar__location");
  location.append(create("small", "", "РАБОЧЕЕ ПРОСТРАНСТВО"), create("strong", "", "Сегодня"));
  const actions = create("div", "ce-v4-menubar__actions");
  const mission = iconButton("", "Рабочие столы", "grid");
  mission.dataset.ceV4Mission = "true";
  const focus = iconButton("", "Фокус — на весь экран", "focus");
  focus.dataset.ceV4Focus = "true";
  const search = iconButton("", "Spotlight — поиск", "search");
  search.dataset.ceV4Spotlight = "true";
  const clock = create("time", "ce-v4-menubar__clock");
  actions.append(mission, focus, search, clock);
  bar.append(identity, location, actions);
  document.body.append(bar);
  runtime.menubar = bar;
  bar.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-home]")) navigate("/workspace/home");
    if (target?.closest("[data-ce-v4-mission]")) openMission();
    if (target?.closest("[data-ce-v4-focus]")) toggleZen();
    if (target?.closest("[data-ce-v4-spotlight]")) openSpotlight();
  });
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

function ensureDock() {
  if (runtime.dock?.isConnected) return runtime.dock;
  const dock = create("nav", "ce-v4-dock");
  dock.setAttribute("aria-label", "Приложения ContentEngine");
  const glass = create("div", "ce-v4-dock__glass");
  ROUTES.forEach((item, index) => {
    const link = create("a", "ce-v4-dock__item");
    link.href = `#${item.route}`;
    link.dataset.ceV4Route = item.route;
    link.setAttribute("aria-label", item.label);
    link.append(create("span", "ce-v4-dock__tooltip", `${item.label} · ⌥${Math.min(index + 1, 9)}`));
    const tile = create("span", "ce-v4-dock__tile");
    tile.append(icon(item.icon, 22));
    link.append(tile, create("i"));
    glass.append(link);
  });
  glass.append(create("span", "ce-v4-dock__separator"));
  const mission = iconButton("ce-v4-dock__item ce-v4-dock__utility", "Рабочие столы", "grid");
  mission.dataset.ceV4Mission = "true";
  const search = iconButton("ce-v4-dock__item ce-v4-dock__utility", "Spotlight", "search");
  search.dataset.ceV4Spotlight = "true";
  [mission, search].forEach((button) => {
    const tile = create("span", "ce-v4-dock__tile");
    while (button.firstChild) tile.append(button.firstChild);
    button.append(tile);
    glass.append(button);
  });
  dock.append(glass);
  document.body.append(dock);
  runtime.dock = dock;
  glass.addEventListener("pointermove", handleDockMove, { passive: true });
  glass.addEventListener("pointerleave", resetDock);
  glass.addEventListener("focusout", (event) => {
    if (!(event.relatedTarget instanceof Node) || !glass.contains(event.relatedTarget)) resetDock();
  });
  dock.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("[data-ce-v4-mission]")) openMission();
    if (target?.closest("[data-ce-v4-spotlight]")) openSpotlight();
  });
  return dock;
}

function updateDock() {
  const route = routePath();
  qa("[data-ce-v4-route]", runtime.dock).forEach((item) => {
    const active = routeMatches(route, item.dataset.ceV4Route);
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
}

function resetDock() {
  qa(".ce-v4-dock__item", runtime.dock).forEach((item) => {
    item.style.removeProperty("--ce-v4-scale");
    item.style.removeProperty("--ce-v4-lift");
    item.style.removeProperty("--ce-v4-z");
  });
}

function handleDockMove(event) {
  runtime.dockEvent = event;
  if (runtime.dockFrame) return;
  runtime.dockFrame = window.requestAnimationFrame(() => {
    runtime.dockFrame = 0;
    if (!FINE_POINTER.matches || REDUCED_MOTION.matches) return resetDock();
    qa(".ce-v4-dock__item", runtime.dock).forEach((item) => {
      const rect = item.getBoundingClientRect();
      const distance = Math.abs(runtime.dockEvent.clientX - (rect.left + rect.width / 2));
      const influence = Math.max(0, 1 - distance / 132);
      const eased = influence * influence * (3 - 2 * influence);
      item.style.setProperty("--ce-v4-scale", String(1 + eased * 0.34));
      item.style.setProperty("--ce-v4-lift", `${-eased * 13}px`);
      item.style.setProperty("--ce-v4-z", String(2 + Math.round(eased * 10)));
    });
  });
}

function updateMenubar() {
  const item = routeRecord();
  const location = q(".ce-v4-menubar__location strong", runtime.menubar);
  if (location) location.textContent = item.label;
}

function nextAction() {
  const snapshot = readJson(storage("session"), WORK_SNAPSHOT_KEY, null);
  const candidates = [
    [".my-work-item[data-work-item-priority='blocked'], .my-work-item.is-blocked", "/workspace/work", "Разобрать блокер"],
    [".task-card:not([hidden])", "/workspace/tasks", "Открыть назначенную задачу"],
    [".content-review-progress, .content-review-result", "/workspace/review", "Продолжить проверку"],
    ["[data-generation-job-id]", "/workspace/generation", "Открыть генерацию"],
    [".placement-card:not([hidden])", "/workspace/placement", "Продолжить публикацию"],
  ];
  for (const [selector, route, fallback] of candidates) {
    const node = q(selector);
    if (!node) continue;
    return {
      title: compact(q("h2, h3, strong", node)?.textContent || fallback, 110),
      description: compact(q("p, small, .muted", node)?.textContent || routeRecord(route).description, 190),
      route,
      action: fallback,
    };
  }
  if (Number(snapshot?.blockers || 0) > 0) return { title: `${snapshot.blockers} блокера требуют решения`, description: "Откройте Мою работу и снимите один стоп-фактор.", route: "/workspace/work", action: "Открыть блокеры" };
  if (Number(snapshot?.now || 0) > 0) return { title: `${snapshot.now} задач сейчас`, description: "Выберите одну работу и завершите её до следующей.", route: "/workspace/work", action: "Открыть Мою работу" };
  return { title: "Откройте Мою работу", description: "Система соберёт то, что требует решения сейчас, и уберёт ожидающее в отдельный контур.", route: "/workspace/work", action: "Начать работу" };
}

function mountHome() {
  if (routePath() !== "/workspace/home") return;
  const page = currentPage();
  if (!page) return;
  let shell = q(":scope > .ce-v4-home", page);
  if (!shell) {
    page.classList.add("ce-v4-home-page");
    shell = create("section", "ce-v4-home");
    shell.dataset.ceV4Surface = "true";
    const main = create("section", "ce-v4-home__main");
    const eyebrow = create("small", "ce-v4-eyebrow", "ОДИН ЭКРАН · ОДНО ДЕЙСТВИЕ");
    const title = create("h1", "ce-v4-home__title");
    const description = create("p", "ce-v4-home__description");
    const action = create("button", "ce-v4-primary-action");
    action.type = "button";
    action.dataset.ceV4HomeAction = "true";
    action.append(create("span"), icon("right", 18));
    const secondary = create("button", "ce-v4-secondary-action", "Открыть все столы");
    secondary.type = "button";
    secondary.dataset.ceV4Mission = "true";
    const copy = create("div", "ce-v4-home__copy");
    copy.append(eyebrow, title, description, create("div", "ce-v4-home__actions"));
    q(".ce-v4-home__actions", copy).append(action, secondary);
    main.append(copy);

    const route = create("aside", "ce-v4-home__route");
    route.append(create("small", "ce-v4-eyebrow", "ПРОИЗВОДСТВЕННЫЙ МАРШРУТ"), create("h2", "", "От исходника до выплаты"));
    const rail = create("div", "ce-v4-stage-rail");
    STAGES.forEach((stage) => {
      const button = create("button", "ce-v4-stage");
      button.type = "button";
      button.dataset.ceV4Stage = stage.route;
      button.append(create("b", "", stage.number));
      const stageCopy = create("span");
      stageCopy.append(create("strong", "", stage.label), create("small", "", stage.description));
      button.append(stageCopy, icon("right", 16));
      rail.append(button);
    });
    route.append(rail);
    shell.append(main, route);
    page.prepend(shell);
    shell.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target : null;
      const stage = target?.closest("[data-ce-v4-stage]");
      if (stage) navigate(stage.dataset.ceV4Stage);
      if (target?.closest("[data-ce-v4-mission]")) openMission();
      if (target?.closest("[data-ce-v4-home-action]")) navigate(q("[data-ce-v4-home-action]", shell)?.dataset.route || "/workspace/work");
    });
  }
  const action = nextAction();
  q(".ce-v4-home__title", shell).textContent = action.title;
  q(".ce-v4-home__description", shell).textContent = action.description;
  const button = q("[data-ce-v4-home-action]", shell);
  button.dataset.route = action.route;
  q("span", button).textContent = action.action;
  qa("[data-ce-v4-stage]", shell).forEach((stage) => stage.classList.toggle("has-attention", stage.dataset.ceV4Stage === action.route));
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
  if (runtime.mission) closeElementOverlay("mission", immediate);
  if (runtime.spotlight) closeElementOverlay("spotlight", immediate);
  if (runtime.zen) closeZen(immediate);
}

function openMission() {
  if (runtime.mission) return;
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
  ROUTES.forEach((item, index) => {
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
  animate(dialog, [{ opacity: 0, transform: "translateY(20px) scale(.975)" }, { opacity: 1, transform: "translateY(0) scale(1)" }], 420);
}

function spotlightRecords(query = "") {
  const records = ROUTES.map((item) => ({
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
  animate(dialog, [{ opacity: 0, transform: "translateY(-18px) scale(.97)" }, { opacity: 1, transform: "translateY(0) scale(1)" }], 360);
}

function zenSurface() {
  return qa(
    ".review-desktop-os, .generation-os-shell, .media-finder-shell, .work-stage-shell, .tasks-desk-shell, "
      + ".publishing-os-shell, .results-ledger-shell, .academy-os-window, .academy-course-os-window--v2, .workspace-board, .page-wrap",
  ).filter(isVisible).at(-1) || currentPage();
}

function openZen() {
  if (runtime.zen) return;
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
  animate(dialog, [{ opacity: 0, transform: "scale(.975) translateY(14px)" }, { opacity: 1, transform: "scale(1) translateY(0)" }], 420);
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
  return qa(
    ".workspace-board__content, .workspace-board__sidebar, .generation-os-panels, .review-os-workbench, "
      + ".work-stage-items, .tasks-desk-list, .tasks-desk-main, .publishing-os-list, .publishing-os-panels, "
      + ".results-ledger-panels, .academy-v2-panels, .academy-os-panels, [data-ce-v4-scroll]",
    page,
  ).filter(isVisible).slice(0, 12);
}

function scrollKey(node, index) {
  return (node.dataset.ceV4ScrollKey || node.id || [...node.classList].slice(0, 2).join(".") || `scroll-${index}`).slice(0, 120);
}

function captureScroll(route = runtime.route) {
  if (!isWorkspaceRoute(route)) return;
  const nested = {};
  scrollContainers().forEach((node, index) => { nested[scrollKey(node, index)] = { top: Math.round(node.scrollTop || 0), left: Math.round(node.scrollLeft || 0) }; });
  const states = { ...(runtime.state.scroll || {}) };
  states[route] = { windowY: Math.round(window.scrollY || 0), nested, at: Date.now() };
  remember({ scroll: states });
}

function restoreScroll(route = routePath()) {
  if (runtime.restoredRoute === route) return;
  const saved = runtime.state.scroll?.[route];
  if (!saved) { runtime.restoredRoute = route; return; }
  runtime.restoredRoute = route;
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: Math.max(0, Number(saved.windowY) || 0), behavior: "auto" });
    scrollContainers().forEach((node, index) => {
      const point = saved.nested?.[scrollKey(node, index)];
      if (!point) return;
      node.scrollTop = Math.max(0, Number(point.top) || 0);
      node.scrollLeft = Math.max(0, Number(point.left) || 0);
    });
  });
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
      + ".publishing-os-shell, .results-ledger-shell, .academy-os-window, .academy-course-os-window--v2, .workspace-board, .ce-v4-home",
    page,
  ).filter(isVisible).at(-1);
  qa("[data-ce-v4-surface]", page).forEach((node) => { if (node !== surface && !node.classList.contains("ce-v4-home")) node.removeAttribute("data-ce-v4-surface"); });
  if (surface) surface.dataset.ceV4Surface = "true";
}

function mount() {
  const route = routePath();
  if (!isWorkspaceRoute(route)) {
    runtime.menubar?.remove();
    runtime.dock?.remove();
    runtime.menubar = null;
    runtime.dock = null;
    document.body.classList.remove("contentengine-desktop-v4");
    return;
  }
  document.documentElement.dataset.contentengineOs = "v4";
  document.body.classList.add("contentengine-desktop-v4");
  cleanLegacyChrome();
  ensureMenubar();
  ensureDock();
  updateMenubar();
  updateDock();
  mountHome();
  setupVideoGovernor();
  markSurface();
  restoreScroll(route);
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => { runtime.queued = false; mount(); }));
}

function handleHashChange() {
  captureScroll(runtime.route);
  closeTransientOverlays(true);
  runtime.route = routePath();
  runtime.restoredRoute = "";
  scheduleMount();
}

function handleKeydown(event) {
  const target = event.target instanceof Element ? event.target : null;
  const editing = Boolean(target?.closest("input, textarea, select, [contenteditable='true']"));
  if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (runtime.spotlight) closeElementOverlay("spotlight"); else openSpotlight();
    return;
  }
  if (event.ctrlKey && event.key === "ArrowUp" && !editing) { event.preventDefault(); openMission(); return; }
  if (event.key === "Escape") {
    if (runtime.spotlight) closeElementOverlay("spotlight");
    else if (runtime.mission) closeElementOverlay("mission");
    else if (runtime.zen) closeZen();
    return;
  }
  if (!editing && event.key.toLocaleLowerCase() === "f" && !event.metaKey && !event.ctrlKey && !event.altKey) { event.preventDefault(); toggleZen(); return; }
  if (!editing && event.altKey && !event.shiftKey && /^Digit[1-9]$/.test(event.code)) {
    const item = ROUTES[Number(event.code.slice(-1)) - 1];
    if (item) { event.preventDefault(); navigate(item.route); }
  }
}

function handleScroll() {
  window.clearTimeout(runtime.scrollTimer);
  runtime.scrollTimer = window.setTimeout(() => captureScroll(routePath()), 180);
}

new MutationObserver(scheduleMount).observe(q("#app") || document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", handleHashChange, { passive: true });
window.addEventListener("contentengine:v4-route-ready", scheduleMount);
window.addEventListener("scroll", handleScroll, { passive: true });
document.addEventListener("keydown", handleKeydown, true);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();

window.ContentEngineDesktopV4 = Object.freeze({
  build: BUILD,
  routes: ROUTES,
  route: routePath,
  navigate,
  openMission,
  openSpotlight,
  openZen,
  closeZen,
  icon,
  create,
  scheduleMount,
});
