/*
 * ContentEngine Desktop v4.2 · single-chrome stability coordinator.
 *
 * Presentation only. It does not call business APIs, submit forms, read
 * credentials or clone native controls. The module removes duplicate window
 * chrome, keeps one contextual navigation layer and makes route mounting
 * deterministic without a document-wide MutationObserver.
 */

const BUILD = "20260803.os4.2.1";
const ROUTE_RESEARCH = Object.freeze({
  route: "/workspace/research",
  label: "Разбор товара",
  description: "Товар, факты и безопасная гипотеза",
  icon: "search",
});
const SECONDARY_DOCK_ROUTES = new Set([
  "/workspace/tasks",
  "/workspace/payouts",
]);

const DEDICATED_SURFACES = [
  ".review-desktop-os",
  ".generation-os-shell",
  ".media-finder-shell",
  ".work-stage-shell",
  ".tasks-desk-shell",
  ".publishing-os-shell",
  ".results-ledger-shell",
  ".academy-os-window",
  ".academy-course-os-window--v2",
  ".workspace-board",
  ".ce-v4-home",
].join(",");

const LOCAL_TOPBARS = [
  ".review-os-topbar",
  ".generation-os-topbar",
  ".media-finder-topbar",
  ".work-stage-topbar",
  ".tasks-desk-topbar",
  ".publishing-os-topbar",
  ".results-os-topbar",
  ".payout-ledger-topbar",
  ".academy-os-topbar",
  ".academy-v2-topbar",
].join(",");

const LOCAL_DOCKS = [
  ".generation-os-step-dock",
  ".review-os-step-dock",
  ".review-result-dock",
  ".academy-v2-dock",
  ".academy-os-dock",
  ".publishing-os-dock",
  ".work-stage-tabs",
  ".tasks-desk-tabs",
  ".results-os-tabs",
  ".payout-ledger-tabs",
].join(",");

const DUPLICATE_GLOBAL_CHROME = [
  ".ce-mac-dock",
  ".workspace-task-dock",
  ".workspace-deckbar",
  ".learning-command-bar",
  ".workspace-contextbar",
  ".workspace-context-bar",
].join(",");

const WINDOW_CONTROLS = [
  "[class*='window-controls']",
  ".review-os-window-controls",
  ".generation-os-window-controls",
].join(",");

const runtime = {
  queued: false,
  timers: new Set(),
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
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
}

function isVisible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function currentPage() {
  return qa(
    ".workspace-main .page-wrap, .workspace-main .learning-page, "
      + "#main-content > .page-wrap, #main-content > .learning-page",
  ).filter(isVisible).at(-1) || q(".workspace-main") || q("#main-content");
}

function nodeDepth(node) {
  let depth = 0;
  let cursor = node;
  while (cursor?.parentElement) {
    depth += 1;
    cursor = cursor.parentElement;
  }
  return depth;
}

function icon(name, size = 20) {
  const apiIcon = window.ContentEngineDesktopV4?.icon;
  if (typeof apiIcon === "function") return apiIcon(name, size);
  return create("span", "ce-v4-stability-fallback-icon", "⌕");
}

function makeResearchDockItem() {
  const link = create("a", "ce-v4-dock__item ce-v4-dock__extra");
  link.href = `#${ROUTE_RESEARCH.route}`;
  link.dataset.ceV4Route = ROUTE_RESEARCH.route;
  link.setAttribute("aria-label", ROUTE_RESEARCH.label);
  link.append(create("span", "ce-v4-dock__tooltip", ROUTE_RESEARCH.label));
  const tile = create("span", "ce-v4-dock__tile");
  tile.append(icon(ROUTE_RESEARCH.icon, 22));
  link.append(tile, create("i"));
  return link;
}

function ensureResearchDockItem() {
  const glass = q(".ce-v4-dock__glass");
  if (!glass || q(`[data-ce-v4-route="${ROUTE_RESEARCH.route}"]`, glass)) return;
  const finder = q('[data-ce-v4-route="/workspace/board"]', glass);
  if (finder) finder.after(makeResearchDockItem());
  else glass.prepend(makeResearchDockItem());
}

function makeResearchMissionCard(number) {
  const button = create("button", "ce-v4-mission-card ce-v4-mission-card--extra");
  button.type = "button";
  button.dataset.route = ROUTE_RESEARCH.route;
  button.dataset.search = `${ROUTE_RESEARCH.label} ${ROUTE_RESEARCH.description}`
    .toLocaleLowerCase("ru-RU");
  button.append(create(
    "span",
    "ce-v4-mission-card__number",
    String(number).padStart(2, "0"),
  ));
  const copy = create("span");
  const tile = create("span", "ce-v4-mission-card__icon");
  tile.append(icon(ROUTE_RESEARCH.icon, 22));
  copy.append(
    tile,
    create("strong", "", ROUTE_RESEARCH.label),
    create("small", "", ROUTE_RESEARCH.description),
  );
  button.append(copy, icon("right", 18));
  button.addEventListener("click", () => {
    window.ContentEngineDesktopV4?.navigate?.(ROUTE_RESEARCH.route);
  });
  return button;
}

function ensureResearchMissionCard() {
  const grid = q(".ce-v4-mission__grid");
  if (!grid || q(`[data-route="${ROUTE_RESEARCH.route}"]`, grid)) return;
  const number = qa(":scope > .ce-v4-mission-card", grid).length + 1;
  grid.append(makeResearchMissionCard(number));
}

function activeSurface(page) {
  if (!page) return null;
  const candidates = qa(DEDICATED_SURFACES, page).filter(isVisible);
  if (page.matches?.(DEDICATED_SURFACES) && isVisible(page)) candidates.push(page);
  return candidates.sort((left, right) => nodeDepth(left) - nodeDepth(right)).at(-1) || page;
}

function hideDuplicateGlobalChrome() {
  qa(DUPLICATE_GLOBAL_CHROME).forEach((node) => {
    if (node.closest(".ce-v4-dock, .ce-v4-menubar")) return;
    node.hidden = true;
    node.setAttribute("aria-hidden", "true");
    node.dataset.ceV4RetiredChrome = "true";
  });
}

function normalizeGlobalDock() {
  qa(".ce-v4-dock [data-ce-v4-route]").forEach((node) => {
    const secondary = SECONDARY_DOCK_ROUTES.has(node.dataset.ceV4Route || "");
    node.hidden = secondary;
    node.setAttribute("aria-hidden", secondary ? "true" : "false");
    node.dataset.ceV4SecondaryDock = secondary ? "true" : "false";
  });
}

function normalizeTopbars(page) {
  const topbars = qa(LOCAL_TOPBARS, page).filter(isVisible);
  if (!topbars.length) return null;

  const ranked = topbars.map((bar) => ({
    bar,
    controls: qa("button, a, [role='tab'], [role='switch']", bar)
      .filter((node) => !node.matches("[data-ce-open-mission]"))
      .length,
    depth: nodeDepth(bar),
  })).sort((left, right) => {
    if (left.controls !== right.controls) return right.controls - left.controls;
    return right.depth - left.depth;
  });

  const primary = ranked[0]?.bar || null;
  topbars.forEach((bar) => {
    const active = bar === primary;
    bar.dataset.ceV4Contextbar = active ? "primary" : "secondary";
    bar.setAttribute("aria-hidden", active ? "false" : "true");
    qa(WINDOW_CONTROLS, bar).forEach((node) => {
      node.hidden = true;
      node.setAttribute("aria-hidden", "true");
    });
    qa("[data-ce-open-mission]", bar).forEach((node) => {
      node.hidden = true;
      node.setAttribute("aria-hidden", "true");
    });
    qa("[class*='mode-switch'], [role='tablist'], [role='group']", bar)
      .forEach((node) => { node.dataset.ceV4ConnectedMenu = "true"; });
  });
  return primary;
}

function isolateSurface(page, surface, primaryTopbar) {
  if (!page) return;
  const dedicated = surface && surface !== page;
  page.classList.toggle("ce-v4-native-surface", !dedicated);
  [...page.children].forEach((child) => {
    delete child.dataset.ceV4SurfaceHost;
  });
  page.classList.remove("ce-v4-single-surface");
  if (!dedicated) return;

  const surfaceHost = [...page.children].find((child) => (
    child === surface || child.contains(surface)
  ));
  if (!surfaceHost) return;
  const topbarHost = primaryTopbar
    ? [...page.children].find((child) => (
      child === primaryTopbar || child.contains(primaryTopbar)
    ))
    : null;

  [...page.children].forEach((child) => {
    const keep = child === surfaceHost || child === topbarHost;
    child.dataset.ceV4SurfaceHost = keep ? "true" : "false";
  });
  page.classList.add("ce-v4-single-surface");
}

function normalizeLocalDocks(surface) {
  qa(LOCAL_DOCKS, surface).filter(isVisible).forEach((dock) => {
    dock.dataset.ceV4LocalDock = "true";
    dock.style.removeProperty("transform");
    dock.style.removeProperty("inset");
    dock.style.removeProperty("left");
    dock.style.removeProperty("right");
    dock.style.removeProperty("bottom");
    dock.style.removeProperty("top");
  });
}

function updateRouteChrome() {
  const route = routePath();
  document.body.dataset.ceV4Stable = "true";
  document.body.dataset.ceV4Route = route;
  const location = q(".ce-v4-menubar__location strong");
  if (location && route === ROUTE_RESEARCH.route) {
    location.textContent = ROUTE_RESEARCH.label;
  }
  qa("[data-ce-v4-route]").forEach((node) => {
    const expected = node.dataset.ceV4Route;
    const active = expected === route
      || (expected === "/workspace/board" && route === "/workspace/media")
      || (expected === "/workspace/work" && route === "/workspace/tasks")
      || (expected === "/workspace/stats" && route === "/workspace/payouts")
      || (expected === "/learn" && route.startsWith("/learn/"));
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-current", active ? "page" : "false");
  });
}

function cancelChromeAnimations() {
  if (typeof document.getAnimations !== "function") return;
  document.getAnimations().forEach((animation) => {
    const target = animation.effect?.target;
    if (!(target instanceof Element)) return;
    if (target.matches(
      ".ce-v4-dock, .ce-v4-dock__item, .ce-v4-menubar, .ce-v4-page, "
        + ".review-os-topbar, .generation-os-topbar, .academy-v2-topbar",
    )) {
      animation.cancel();
    }
  });
}

function mount() {
  const page = currentPage();
  const surface = activeSurface(page);
  ensureResearchDockItem();
  ensureResearchMissionCard();
  hideDuplicateGlobalChrome();
  normalizeGlobalDock();
  const primaryTopbar = page ? normalizeTopbars(page) : null;
  isolateSurface(page, surface, primaryTopbar);
  if (surface) {
    surface.dataset.ceV4PrimarySurface = "true";
    normalizeLocalDocks(surface);
  }
  updateRouteChrome();
  cancelChromeAnimations();
}

function clearTimers() {
  runtime.timers.forEach((timer) => window.clearTimeout(timer));
  runtime.timers.clear();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
  clearTimers();
  [80, 220, 520].forEach((delay) => {
    const timer = window.setTimeout(() => {
      runtime.timers.delete(timer);
      mount();
    }, delay);
    runtime.timers.add(timer);
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
window.addEventListener("pageshow", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineDesktopV4Stability = Object.freeze({
  build: BUILD,
  schedule,
  route: routePath,
});
