/* ContentEngine Desktop v4 · system continuity and route polish. */

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const EXTRA_ROUTES = Object.freeze([
  Object.freeze({ route: "/workspace/research", label: "Разбор товара", description: "Товар, факты и безопасная гипотеза", icon: "search" }),
]);

const runtime = {
  queued: false,
  route: routePath(),
  animatedRoute: "",
  navigationTimer: 0,
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

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function isVisible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function currentPage() {
  return qa(".workspace-main .page-wrap, .workspace-main .learning-page, #main-content > .page-wrap, #main-content > .learning-page")
    .filter(isVisible).at(-1) || q(".workspace-main") || q("#main-content");
}

function routeLabel(route = routePath()) {
  if (route === "/workspace/media") return "Finder · загрузка";
  const extra = EXTRA_ROUTES.find((item) => item.route === route);
  if (extra) return extra.label;
  return q(".ce-v4-menubar__location strong")?.textContent || "Рабочее пространство";
}

function routeIndex(route) {
  const known = [
    "/workspace/home",
    "/workspace/board",
    "/workspace/research",
    "/workspace/generation",
    "/workspace/review",
    "/workspace/work",
    "/workspace/tasks",
    "/workspace/placement",
    "/workspace/stats",
    "/workspace/payouts",
    "/learn",
  ];
  if (route === "/workspace/media") return known.indexOf("/workspace/board");
  if (route.startsWith("/learn/")) return known.indexOf("/learn");
  return Math.max(0, known.indexOf(route));
}

function makeDockItem(item) {
  const api = window.ContentEngineDesktopV4;
  const link = create("a", "ce-v4-dock__item ce-v4-dock__extra");
  link.href = `#${item.route}`;
  link.dataset.ceV4Route = item.route;
  link.setAttribute("aria-label", item.label);
  link.append(create("span", "ce-v4-dock__tooltip", item.label));
  const tile = create("span", "ce-v4-dock__tile");
  tile.append(api?.icon?.(item.icon, 22) || create("span", "", "⌕"));
  link.append(tile, create("i"));
  return link;
}

function ensureExtraDockRoutes() {
  const glass = q(".ce-v4-dock__glass");
  if (!glass) return;
  EXTRA_ROUTES.forEach((item) => {
    if (q(`[data-ce-v4-route="${item.route}"]`, glass)) return;
    const anchor = q('[data-ce-v4-route="/workspace/board"]', glass);
    anchor?.after(makeDockItem(item));
  });
}

function updateSystemChrome() {
  const route = routePath();
  document.body.dataset.ceV4Route = route;
  const label = q(".ce-v4-menubar__location strong");
  if (route === "/workspace/media" || EXTRA_ROUTES.some((item) => item.route === route)) {
    if (label) label.textContent = routeLabel(route);
  }
  qa("[data-ce-v4-route]").forEach((item) => {
    const expected = item.dataset.ceV4Route;
    const active = expected === route || (expected === "/workspace/board" && route === "/workspace/media");
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-current", active ? "page" : "false");
  });
}

function makeMissionCard(item, index) {
  const api = window.ContentEngineDesktopV4;
  const button = create("button", "ce-v4-mission-card ce-v4-mission-card--extra");
  button.type = "button";
  button.dataset.route = item.route;
  button.dataset.search = `${item.label} ${item.description}`.toLocaleLowerCase("ru-RU");
  button.append(create("span", "ce-v4-mission-card__number", String(index).padStart(2, "0")));
  const copy = create("span");
  const tile = create("span", "ce-v4-mission-card__icon");
  tile.append(api?.icon?.(item.icon, 22) || create("span", "", "⌕"));
  copy.append(tile, create("strong", "", item.label), create("small", "", item.description));
  button.append(copy, api?.icon?.("right", 18) || create("span", "", "→"));
  return button;
}

function ensureExtraMissionRoutes() {
  const grid = q(".ce-v4-mission__grid");
  if (!grid) return;
  EXTRA_ROUTES.forEach((item, index) => {
    if (q(`[data-route="${item.route}"]`, grid)) return;
    const card = makeMissionCard(item, 11 + index);
    grid.append(card);
    card.addEventListener("click", () => transitionTo(item.route));
  });
}

function surfaceCandidates(page) {
  return qa(
    ".review-desktop-os, .generation-os-shell, .media-finder-shell, .work-stage-shell, .tasks-desk-shell, "
      + ".publishing-os-shell, .results-ledger-shell, .academy-os-window, .academy-course-os-window--v2, .workspace-board, .ce-v4-home",
    page,
  ).filter(isVisible);
}

function isolateSurface() {
  const page = currentPage();
  if (!page) return;
  const surface = surfaceCandidates(page).at(-1);
  [...page.children].forEach((child) => {
    delete child.dataset.ceV4SurfaceHost;
  });
  page.classList.remove("ce-v4-single-surface");
  if (!surface || surface === page) return;
  const host = [...page.children].find((child) => child === surface || child.contains(surface));
  if (!host) return;
  [...page.children].forEach((child) => {
    child.dataset.ceV4SurfaceHost = child === host ? "true" : "false";
  });
  page.classList.add("ce-v4-single-surface");
}

function animateRouteIn() {
  const route = routePath();
  if (runtime.animatedRoute === route || REDUCED_MOTION.matches) return;
  const page = currentPage();
  if (!page || typeof page.animate !== "function") return;
  const direction = routeIndex(route) >= routeIndex(runtime.route) ? 1 : -1;
  runtime.animatedRoute = route;
  page.animate([
    { opacity: 0, transform: `translate3d(${direction * 34}px,0,0) scale(.988)`, filter: "blur(5px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.002)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 440, easing: SPRING });
}

function transitionTo(route) {
  const next = String(route || "");
  if (!next || next === routePath()) return;
  window.clearTimeout(runtime.navigationTimer);
  const page = currentPage();
  const direction = routeIndex(next) >= routeIndex(routePath()) ? 1 : -1;
  const finish = () => window.ContentEngineDesktopV4?.navigate?.(next);
  if (!page || REDUCED_MOTION.matches || typeof page.animate !== "function") return finish();
  const animation = page.animate([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: .18, transform: `translate3d(${-direction * 28}px,0,0) scale(.992)`, filter: "blur(3px)" },
  ], { duration: 145, easing: "ease-out", fill: "forwards" });
  animation.finished.then(finish).catch(finish);
  runtime.navigationTimer = window.setTimeout(finish, 190);
}

function interceptDockNavigation() {
  if (document.documentElement.dataset.ceV4PolishBound === "true") return;
  document.documentElement.dataset.ceV4PolishBound = "true";
  document.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const link = target?.closest?.(".ce-v4-dock a[data-ce-v4-route]");
    if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    transitionTo(link.dataset.ceV4Route);
  }, true);
}

function mount() {
  ensureExtraDockRoutes();
  ensureExtraMissionRoutes();
  updateSystemChrome();
  isolateSurface();
  animateRouteIn();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  }));
}

function handleHashChange() {
  runtime.route = routePath();
  runtime.animatedRoute = "";
  schedule();
}

interceptDockNavigation();
new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", handleHashChange, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineDesktopV4Polish = Object.freeze({ transitionTo, schedule });
