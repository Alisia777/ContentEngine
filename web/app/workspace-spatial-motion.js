/*
 * ContentEngine spatial motion layer.
 * Brings macOS-like spatial behaviour to the existing workspace without
 * changing routes, permissions, forms or backend state.
 */

const SPATIAL_SURFACE_NAME = "content-engine-space";
const SPATIAL_ROUTE_PREFIXES = ["/workspace/", "/learn"];
const PRODUCTIVITY_STORAGE_KEY = "contentengine.workspace-productivity.v1";
const PRODUCTIVITY_PENDING_KEY = "contentengine.workspace-productivity.pending.v1";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";
const NAVIGATION_TIMEOUT_MS = 1100;
const SWIPE_THRESHOLD_PX = 82;
const WHEEL_THRESHOLD_PX = 78;
const INTERACTIVE_SELECTOR = [
  "button",
  "a",
  "input",
  "textarea",
  "select",
  "[contenteditable='true']",
  ".table-wrap",
  ".data-table-wrap",
  ".workspace-table-wrap",
  ".workspace-board",
  "video",
  "audio",
].join(", ");
const TILT_SELECTOR = ".workspace-overview-card, .workspace-deck-current";
const DOCK_ITEM_SELECTOR = ".workspace-task-dock__chip, .workspace-task-dock__actions > button";

const runtime = {
  navigating: false,
  queuedRoute: "",
  swipe: null,
  wheelDelta: 0,
  wheelTimer: 0,
  wheelLockUntil: 0,
  dockFrame: 0,
  dockPointerEvent: null,
  dockActive: false,
  tiltedElement: null,
  tiltFrame: 0,
  tiltPointerEvent: null,
  syncQueued: false,
  scrollFrame: 0,
  attentionSeen: new Set(),
  peek: null,
};

const reducedMotion = window.matchMedia(REDUCED_MOTION_QUERY);
const finePointer = window.matchMedia(FINE_POINTER_QUERY);

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function normalizeRoute(value) {
  const raw = String(value || "").trim().replace(/^#/, "");
  const route = raw.startsWith("/") ? raw : `/${raw}`;
  const [pathPart, ...queryParts] = route.split("?");
  const path = (`/${pathPart}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
  const query = queryParts.join("?");
  return query ? `${path}?${query}` : path;
}

function currentRoute() {
  return normalizeRoute(window.location.hash || "#/workspace/home");
}

function routePath(value = currentRoute()) {
  return normalizeRoute(value).split("?")[0];
}

function isSpatialRoute(value) {
  const path = routePath(value);
  return SPATIAL_ROUTE_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function isSpatialWorkspace() {
  return Boolean(q(".workspace-shell")) && isSpatialRoute(currentRoute());
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compact(value, limit = 72) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function motionSurface() {
  return q("#workspace-content")
    || q("#main-content > .page-wrap")
    || q("#main-content .learning-page")
    || q("#main-content");
}

function prepareMotionSurface(surface = motionSurface()) {
  if (!(surface instanceof HTMLElement)) return null;
  qa("[data-spatial-motion-surface]").forEach((item) => {
    if (item === surface) return;
    delete item.dataset.spatialMotionSurface;
    item.style.removeProperty("view-transition-name");
  });
  surface.dataset.spatialMotionSurface = "true";
  surface.classList.add("workspace-spatial-surface");
  surface.style.viewTransitionName = SPATIAL_SURFACE_NAME;
  return surface;
}

function deskRoutes() {
  const seen = new Set();
  const routes = [];
  qa(".workspace-shell .sidebar .workspace-nav a[href^='#/']").forEach((anchor) => {
    const route = normalizeRoute(anchor.getAttribute("href"));
    if (!isSpatialRoute(route) || seen.has(route)) return;
    seen.add(route);
    routes.push({
      route,
      path: routePath(route),
      label: compact(q(".nav-link-copy strong", anchor)?.textContent || anchor.textContent || "Рабочий стол"),
    });
  });
  return routes;
}

function routeIndex(value, routes = deskRoutes()) {
  const path = routePath(value);
  const exact = routes.findIndex((item) => item.path === path);
  if (exact >= 0) return exact;
  if (path.startsWith("/learn/")) return routes.findIndex((item) => item.path === "/learn");
  return -1;
}

function relativeDesk(delta) {
  const routes = deskRoutes();
  const index = routeIndex(currentRoute(), routes);
  return index >= 0 ? routes[index + delta] || null : null;
}

function routeDirection(from, to) {
  const routes = deskRoutes();
  const fromIndex = routeIndex(from, routes);
  const toIndex = routeIndex(to, routes);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return "neutral";
  return toIndex > fromIndex ? "forward" : "backward";
}

function routeLabel(route) {
  const path = routePath(route);
  return deskRoutes().find((item) => item.path === path)?.label
    || compact(document.title.split("·")[0] || "Рабочий стол");
}

function routeFromProductivityTask(key) {
  if (!key) return "";
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(PRODUCTIVITY_STORAGE_KEY) || "{}");
    const task = parsed?.tasks?.[key];
    const route = normalizeRoute(task?.route || "");
    if (!isSpatialRoute(route) || routePath(route) === routePath(currentRoute())) return "";
    window.sessionStorage.setItem(PRODUCTIVITY_PENDING_KEY, JSON.stringify({ key, focus: true, at: Date.now() }));
    const separator = route.includes("?") ? "&" : "?";
    return `${route}${separator}deskTask=${encodeURIComponent(key)}`;
  } catch {
    return "";
  }
}

function targetRouteFromClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return "";

  const relative = target.closest("[data-deck-nav]");
  if (relative) return relativeDesk(Number(relative.dataset.deckNav) || 0)?.route || "";

  const overview = target.closest("[data-overview-route]");
  if (overview) return normalizeRoute(overview.dataset.overviewRoute || "");

  const productivity = target.closest("[data-productivity-open]");
  if (productivity) return routeFromProductivityTask(productivity.dataset.productivityOpen || "");

  const anchor = target.closest("a[href^='#/']");
  if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) return "";
  return normalizeRoute(anchor.getAttribute("href") || "");
}

function createRouteWaiter(targetRoute, previousSurface) {
  const target = normalizeRoute(targetRoute);
  const app = q("#app") || document.body;
  let mutationSeen = false;
  let observer = null;
  let timer = 0;
  let resolved = false;

  return new Promise((resolve) => {
    const finish = () => {
      if (resolved) return;
      resolved = true;
      observer?.disconnect();
      window.clearTimeout(timer);
      const surface = prepareMotionSurface();
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve(surface)));
    };

    const check = () => {
      if (normalizeRoute(window.location.hash) !== target) return;
      const surface = motionSurface();
      if (!surface) return;
      if (!mutationSeen && surface === previousSurface) return;
      finish();
    };

    observer = new MutationObserver(() => {
      mutationSeen = true;
      check();
    });
    observer.observe(app, { childList: true, subtree: true });
    timer = window.setTimeout(finish, NAVIGATION_TIMEOUT_MS);
    check();
  });
}

function setSpatialDirection(direction) {
  document.documentElement.dataset.workspaceDirection = direction;
}

function clearSpatialTransitionState() {
  document.documentElement.classList.remove(
    "workspace-spatial-transitioning",
    "workspace-view-transition-active",
    "workspace-spatial-scrubbing",
    "workspace-spatial-snapback",
  );
  document.documentElement.style.removeProperty("--spatial-drag-x");
  document.documentElement.style.removeProperty("--spatial-drag-scale");
  document.documentElement.style.removeProperty("--spatial-drag-rotate");
  document.documentElement.style.removeProperty("--spatial-drag-blur");
  hidePeek();
  qa(".workspace-spatial-exit-forward, .workspace-spatial-exit-backward, .workspace-spatial-exit-neutral").forEach((surface) => {
    surface.classList.remove("workspace-spatial-exit-forward", "workspace-spatial-exit-backward", "workspace-spatial-exit-neutral");
  });
}

function fallbackExit(surface, direction) {
  if (!surface || reducedMotion.matches) return Promise.resolve();
  const className = `workspace-spatial-exit-${direction}`;
  surface.classList.add(className);
  return new Promise((resolve) => window.setTimeout(resolve, 145));
}

async function navigateSpatial(route) {
  const target = normalizeRoute(route);
  if (!isSpatialRoute(target) || target === currentRoute()) return;
  if (runtime.navigating) {
    runtime.queuedRoute = target;
    return;
  }

  runtime.navigating = true;
  const previous = currentRoute();
  const previousSurface = prepareMotionSurface();
  const direction = routeDirection(previous, target);
  setSpatialDirection(direction);
  clearScrub(false);
  document.documentElement.classList.add("workspace-spatial-transitioning");

  let updated = false;
  const update = async () => {
    if (updated) return;
    updated = true;
    const waiter = createRouteWaiter(target, previousSurface);
    window.location.hash = target;
    await waiter;
  };

  try {
    if (typeof document.startViewTransition === "function" && !reducedMotion.matches) {
      document.documentElement.classList.add("workspace-view-transition-active");
      const transition = document.startViewTransition(update);
      await transition.finished;
    } else {
      await fallbackExit(previousSurface, direction);
      await update();
    }
  } catch {
    await update();
  } finally {
    clearSpatialTransitionState();
    runtime.navigating = false;
    document.dispatchEvent(new CustomEvent("contentengine:spatial-route-settled", {
      detail: { from: previous, to: target, direction },
    }));
    const queued = runtime.queuedRoute;
    runtime.queuedRoute = "";
    if (queued && queued !== currentRoute()) void navigateSpatial(queued);
  }
}

function handleNavigationClick(event) {
  if (!isSpatialWorkspace() || event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
  const route = targetRouteFromClick(event);
  if (!route || !isSpatialRoute(route) || route === currentRoute()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  void navigateSpatial(route);
}

function shouldStartSwipe(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target || event.pointerType !== "touch" || !isSpatialWorkspace()) return false;
  if (!target.closest("#main-content")) return false;
  if (target.closest(INTERACTIVE_SELECTOR)) return false;
  if (q(".workspace-overview-backdrop") || document.body.classList.contains("workspace-focus-mode")) return false;
  return true;
}

function ensurePeek() {
  if (runtime.peek?.isConnected) return runtime.peek;
  const peek = document.createElement("div");
  peek.className = "workspace-space-peek";
  peek.setAttribute("aria-hidden", "true");
  peek.innerHTML = '<span class="workspace-space-peek__arrow"></span><span class="workspace-space-peek__copy"><small>Рабочий стол</small><strong></strong></span>';
  document.body.append(peek);
  runtime.peek = peek;
  return peek;
}

function showPeek(target, side, progress) {
  if (!target) {
    hidePeek();
    return;
  }
  const peek = ensurePeek();
  peek.dataset.side = side;
  q(".workspace-space-peek__arrow", peek).textContent = side === "right" ? "→" : "←";
  q("strong", peek).textContent = target.label || routeLabel(target.route);
  const value = Math.max(0, Math.min(1, progress));
  peek.style.setProperty("--peek-opacity", String(value * 0.98));
  peek.style.setProperty("--peek-scale", String(0.94 + value * 0.06));
  peek.style.setProperty("--peek-x", `${(side === "right" ? 1 : -1) * 18 * (1 - value)}px`);
  peek.style.setProperty("--peek-mobile-y", `${14 * (1 - value)}px`);
  peek.classList.add("is-visible");
}

function hidePeek() {
  runtime.peek?.classList.remove("is-visible");
  runtime.peek?.style.removeProperty("--peek-opacity");
  runtime.peek?.style.removeProperty("--peek-scale");
  runtime.peek?.style.removeProperty("--peek-x");
  runtime.peek?.style.removeProperty("--peek-mobile-y");
}

function applyScrub(dx, target) {
  const maxDistance = Math.min(150, window.innerWidth * 0.24);
  const edgeResistance = target ? 1 : 0.34;
  const translated = Math.max(-maxDistance, Math.min(maxDistance, dx * edgeResistance));
  const progress = Math.min(1, Math.abs(translated) / maxDistance);
  const scale = 1 - progress * 0.014;
  const rotate = Math.max(-2.2, Math.min(2.2, translated / maxDistance * -2.2));
  const blur = progress * 1.6;

  document.documentElement.classList.add("workspace-spatial-scrubbing");
  document.documentElement.style.setProperty("--spatial-drag-x", `${translated}px`);
  document.documentElement.style.setProperty("--spatial-drag-scale", String(scale));
  document.documentElement.style.setProperty("--spatial-drag-rotate", `${rotate}deg`);
  document.documentElement.style.setProperty("--spatial-drag-blur", `${blur}px`);
  showPeek(target, translated < 0 ? "right" : "left", progress);
}

function clearScrub(withSpring = true) {
  document.documentElement.classList.remove("workspace-spatial-scrubbing");
  if (!withSpring || reducedMotion.matches) {
    document.documentElement.classList.remove("workspace-spatial-snapback");
    document.documentElement.style.removeProperty("--spatial-drag-x");
    document.documentElement.style.removeProperty("--spatial-drag-scale");
    document.documentElement.style.removeProperty("--spatial-drag-rotate");
    document.documentElement.style.removeProperty("--spatial-drag-blur");
    hidePeek();
    return;
  }
  document.documentElement.classList.add("workspace-spatial-snapback");
  document.documentElement.style.setProperty("--spatial-drag-x", "0px");
  document.documentElement.style.setProperty("--spatial-drag-scale", "1");
  document.documentElement.style.setProperty("--spatial-drag-rotate", "0deg");
  document.documentElement.style.setProperty("--spatial-drag-blur", "0px");
  hidePeek();
  window.setTimeout(() => {
    document.documentElement.classList.remove("workspace-spatial-snapback");
    document.documentElement.style.removeProperty("--spatial-drag-x");
    document.documentElement.style.removeProperty("--spatial-drag-scale");
    document.documentElement.style.removeProperty("--spatial-drag-rotate");
    document.documentElement.style.removeProperty("--spatial-drag-blur");
  }, 460);
}

function handlePointerDown(event) {
  if (!shouldStartSwipe(event)) return;
  runtime.swipe = {
    id: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    lastX: event.clientX,
    lastY: event.clientY,
    axis: "",
  };
  event.stopPropagation();
}

function handlePointerMove(event) {
  const swipe = runtime.swipe;
  if (!swipe || swipe.id !== event.pointerId) return;
  swipe.lastX = event.clientX;
  swipe.lastY = event.clientY;
  const dx = swipe.lastX - swipe.startX;
  const dy = swipe.lastY - swipe.startY;
  if (!swipe.axis && Math.max(Math.abs(dx), Math.abs(dy)) >= 8) {
    swipe.axis = Math.abs(dx) > Math.abs(dy) * 1.18 ? "x" : "y";
  }
  if (swipe.axis === "y") {
    runtime.swipe = null;
    clearScrub(false);
    return;
  }
  if (swipe.axis !== "x") return;
  event.preventDefault();
  event.stopPropagation();
  const target = relativeDesk(dx < 0 ? 1 : -1);
  applyScrub(dx, target);
}

function finishSwipe(event, cancelled = false) {
  const swipe = runtime.swipe;
  if (!swipe || swipe.id !== event.pointerId) return;
  runtime.swipe = null;
  if (swipe.axis !== "x") {
    clearScrub(false);
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  const dx = swipe.lastX - swipe.startX;
  const target = relativeDesk(dx < 0 ? 1 : -1);
  if (!cancelled && target && Math.abs(dx) >= SWIPE_THRESHOLD_PX) {
    clearScrub(false);
    void navigateSpatial(target.route);
  } else {
    clearScrub(true);
  }
}

function handlePointerUp(event) {
  finishSwipe(event, false);
}

function handlePointerCancel(event) {
  finishSwipe(event, true);
}

function handleWheel(event) {
  if (!isSpatialWorkspace() || !event.altKey || event.metaKey || event.ctrlKey || event.shiftKey) return;
  if (Math.abs(event.deltaX) < 12 || Math.abs(event.deltaX) < Math.abs(event.deltaY)) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  if (Date.now() < runtime.wheelLockUntil) return;

  runtime.wheelDelta += event.deltaX;
  const destination = relativeDesk(runtime.wheelDelta > 0 ? 1 : -1);
  applyScrub(-Math.max(-120, Math.min(120, runtime.wheelDelta * 0.48)), destination);
  window.clearTimeout(runtime.wheelTimer);
  runtime.wheelTimer = window.setTimeout(() => {
    runtime.wheelDelta = 0;
    clearScrub(true);
  }, 160);

  if (Math.abs(runtime.wheelDelta) >= WHEEL_THRESHOLD_PX && destination) {
    runtime.wheelLockUntil = Date.now() + 760;
    runtime.wheelDelta = 0;
    window.clearTimeout(runtime.wheelTimer);
    clearScrub(false);
    void navigateSpatial(destination.route);
  }
}

function handleNavigationKeydown(event) {
  if (!isSpatialWorkspace()) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  if (q(".workspace-overview-backdrop") || document.body.classList.contains("workspace-focus-mode")) return;

  if (event.altKey && event.shiftKey && !event.metaKey && !event.ctrlKey && event.key === "ArrowLeft") {
    const destination = relativeDesk(-1);
    if (!destination) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void navigateSpatial(destination.route);
    return;
  }
  if (event.altKey && event.shiftKey && !event.metaKey && !event.ctrlKey && event.key === "ArrowRight") {
    const destination = relativeDesk(1);
    if (!destination) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void navigateSpatial(destination.route);
    return;
  }
  if (event.altKey && !event.shiftKey && !event.metaKey && !event.ctrlKey && /^[1-9]$/.test(event.key)) {
    const destination = deskRoutes()[Number(event.key) - 1];
    if (!destination) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void navigateSpatial(destination.route);
  }
}

function resetDockMagnification() {
  if (!runtime.dockActive) return;
  runtime.dockActive = false;
  qa(DOCK_ITEM_SELECTOR).forEach((item) => {
    item.style.removeProperty("--dock-scale");
    item.style.removeProperty("--dock-lift");
    item.style.removeProperty("--dock-z");
    item.style.removeProperty("--dock-glow");
    item.style.removeProperty("--dock-shadow");
  });
  q(".workspace-task-dock__bar")?.style.removeProperty("--dock-pointer-x");
}

function updateDockMagnification(event) {
  runtime.dockFrame = 0;
  const bar = event?.target instanceof Element ? event.target.closest(".workspace-task-dock__bar") : null;
  if (!bar || !finePointer.matches || reducedMotion.matches) {
    resetDockMagnification();
    return;
  }
  runtime.dockActive = true;
  const rect = bar.getBoundingClientRect();
  bar.style.setProperty("--dock-pointer-x", `${Math.max(0, Math.min(100, (event.clientX - rect.left) / Math.max(1, rect.width) * 100))}%`);
  qa(DOCK_ITEM_SELECTOR, bar).forEach((item) => {
    const itemRect = item.getBoundingClientRect();
    const distance = Math.abs(event.clientX - (itemRect.left + itemRect.width / 2));
    const influence = Math.max(0, 1 - distance / 175);
    const eased = influence * influence * (3 - 2 * influence);
    item.style.setProperty("--dock-scale", String(1 + eased * 0.17));
    item.style.setProperty("--dock-lift", `${-eased * 11}px`);
    item.style.setProperty("--dock-z", String(2 + Math.round(eased * 8)));
    item.style.setProperty("--dock-glow", String(eased));
    item.style.setProperty("--dock-shadow", `rgba(0, 0, 0, ${0.34 * eased})`);
  });
}

function handleDockPointerMove(event) {
  runtime.dockPointerEvent = event;
  if (runtime.dockFrame) return;
  runtime.dockFrame = window.requestAnimationFrame(() => updateDockMagnification(runtime.dockPointerEvent));
}

function resetTilt(element = runtime.tiltedElement) {
  if (!(element instanceof HTMLElement)) return;
  element.style.removeProperty("--spatial-rx");
  element.style.removeProperty("--spatial-ry");
  element.style.removeProperty("--spatial-gx");
  element.style.removeProperty("--spatial-gy");
  element.classList.remove("workspace-spatial-tilt");
  if (runtime.tiltedElement === element) runtime.tiltedElement = null;
}

function updateTilt(event) {
  runtime.tiltFrame = 0;
  if (!finePointer.matches || reducedMotion.matches) {
    resetTilt();
    return;
  }
  const element = event?.target instanceof Element ? event.target.closest(TILT_SELECTOR) : null;
  if (!(element instanceof HTMLElement)) {
    resetTilt();
    return;
  }
  if (runtime.tiltedElement && runtime.tiltedElement !== element) resetTilt(runtime.tiltedElement);
  runtime.tiltedElement = element;
  const rect = element.getBoundingClientRect();
  const nx = Math.max(-1, Math.min(1, ((event.clientX - rect.left) / Math.max(1, rect.width) - 0.5) * 2));
  const ny = Math.max(-1, Math.min(1, ((event.clientY - rect.top) / Math.max(1, rect.height) - 0.5) * 2));
  element.style.setProperty("--spatial-rx", `${ny * -1.35}deg`);
  element.style.setProperty("--spatial-ry", `${nx * 1.65}deg`);
  element.style.setProperty("--spatial-gx", `${(nx + 1) * 50}%`);
  element.style.setProperty("--spatial-gy", `${(ny + 1) * 50}%`);
  element.classList.add("workspace-spatial-tilt");
}

function handleTiltPointerMove(event) {
  runtime.tiltPointerEvent = event;
  if (runtime.tiltFrame) return;
  runtime.tiltFrame = window.requestAnimationFrame(() => updateTilt(runtime.tiltPointerEvent));
}

function syncDockAttention() {
  qa(".workspace-task-dock__chip[data-tone='return'], .workspace-task-dock__chip[data-tone='blocked']").forEach((chip) => {
    const key = `${chip.dataset.taskChipKey || "task"}:${chip.dataset.tone || "active"}`;
    if (runtime.attentionSeen.has(key)) return;
    runtime.attentionSeen.add(key);
    chip.classList.add("workspace-dock-attention");
    window.setTimeout(() => chip.classList.remove("workspace-dock-attention"), 980);
  });
}

function updateScrollDepth() {
  runtime.scrollFrame = 0;
  const shell = q(".workspace-shell.workspace-desks-enabled");
  if (!shell) return;
  const depth = Math.max(0, Math.min(1, window.scrollY / 180));
  shell.style.setProperty("--spatial-scroll-depth", String(depth));
  shell.style.setProperty("--spatial-bar-alpha", String(0.82 + depth * 0.12));
  shell.style.setProperty("--spatial-bar-blur", `${24 + depth * 10}px`);
  shell.style.setProperty("--spatial-bar-shadow", `${16 + depth * 22}px`);
}

function handleScroll() {
  if (runtime.scrollFrame) return;
  runtime.scrollFrame = window.requestAnimationFrame(updateScrollDepth);
}

function syncSpatialState() {
  runtime.syncQueued = false;
  const shell = q(".workspace-shell");
  const ready = Boolean(shell) && isSpatialRoute(currentRoute());
  document.documentElement.classList.toggle("workspace-spatial-ready", ready);
  document.body.classList.toggle("workspace-mission-control-open", Boolean(q(".workspace-overview-backdrop")));
  if (ready) {
    prepareMotionSurface();
  } else {
    qa("[data-spatial-motion-surface]").forEach((surface) => {
      delete surface.dataset.spatialMotionSurface;
      surface.classList.remove("workspace-spatial-surface");
      surface.style.removeProperty("view-transition-name");
    });
    resetDockMagnification();
    resetTilt();
  }
  syncDockAttention();
  updateScrollDepth();
}

function queueSpatialSync() {
  if (runtime.syncQueued) return;
  runtime.syncQueued = true;
  window.requestAnimationFrame(syncSpatialState);
}

const observer = new MutationObserver(queueSpatialSync);
observer.observe(q("#app") || document.body, { childList: true, subtree: true });
observer.observe(document.body, { childList: true, subtree: true });

window.addEventListener("click", handleNavigationClick, true);
window.addEventListener("keydown", handleNavigationKeydown, true);
window.addEventListener("pointerdown", handlePointerDown, true);
window.addEventListener("pointermove", handlePointerMove, { capture: true, passive: false });
window.addEventListener("pointerup", handlePointerUp, true);
window.addEventListener("pointercancel", handlePointerCancel, true);
window.addEventListener("wheel", handleWheel, { capture: true, passive: false });
window.addEventListener("scroll", handleScroll, { passive: true });
document.addEventListener("pointermove", handleDockPointerMove, { passive: true });
document.addEventListener("pointermove", handleTiltPointerMove, { passive: true });
document.addEventListener("pointerout", (event) => {
  const from = event.target instanceof Element ? event.target.closest(TILT_SELECTOR) : null;
  const to = event.relatedTarget instanceof Element ? event.relatedTarget.closest(TILT_SELECTOR) : null;
  if (from && from !== to) resetTilt(from);
  const dockFrom = event.target instanceof Element ? event.target.closest(".workspace-task-dock__bar") : null;
  const dockTo = event.relatedTarget instanceof Element ? event.relatedTarget.closest(".workspace-task-dock__bar") : null;
  if (dockFrom && dockFrom !== dockTo) resetDockMagnification();
}, { passive: true });
window.addEventListener("hashchange", queueSpatialSync, { passive: true });
reducedMotion.addEventListener?.("change", () => {
  clearSpatialTransitionState();
  resetDockMagnification();
  resetTilt();
  queueSpatialSync();
});
finePointer.addEventListener?.("change", () => {
  resetDockMagnification();
  resetTilt();
});

queueSpatialSync();
