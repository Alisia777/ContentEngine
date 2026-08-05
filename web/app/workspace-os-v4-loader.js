/*
 * ContentEngine Desktop v4.19 route loader.
 *
 * Keeps one global desktop controller alive and loads heavy route adapters only
 * when their workspace is opened. Same-origin assets only; no API calls and no
 * business mutations. Legacy polish/surface observers are deliberately retired
 * in favour of one deterministic stability coordinator.
 */

import { workspaceActionKey } from "./workspace-action-key.js?v=20260805.os4.19";

const BUILD = "20260805.os4.19";
const loadedStyles = new Set();
const loadedModules = new Map();
let queued = false;
let routeEpoch = 0;
let lastScheduledActionKey = "";
let corePromise = null;
let retryPromise = null;

window.CONTENTENGINE_DESKTOP_V4 = true;

const ROUTE_ASSETS = Object.freeze({
  aiLearning: Object.freeze({
    match: (route) => route === "/workspace/ai",
    styles: [`ai-learning-control-room.css?v=${BUILD}`],
    modules: [],
  }),
  finder: Object.freeze({
    match: (route) => route === "/workspace/board",
    styles: [`workspace-os-v4-finder.css?v=${BUILD}`],
    modules: [`workspace-os-v4-finder.js?v=${BUILD}`],
  }),
  generation: Object.freeze({
    match: (route) => route === "/workspace/generation",
    styles: [`workspace-os-v4-generation-guided.css?v=${BUILD}`],
    modules: [`workspace-os-v4-generation-guided.js?v=${BUILD}`],
  }),
  review: Object.freeze({
    match: (route) => route === "/workspace/review",
    styles: [`workspace-os-v4-review-guided.css?v=${BUILD}`],
    modules: [`workspace-os-v4-review-guided.js?v=${BUILD}`],
  }),
  operations: Object.freeze({
    match: (route) => ["/workspace/tasks", "/workspace/review", "/workspace/placement", "/workspace/stats"].includes(route),
    styles: [`workspace-os-v4-operations.css?v=${BUILD}`],
    modules: [],
  }),
});

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
}

function isManagedRoute(route = routePath()) {
  return route.startsWith("/workspace/");
}

function setLoading(active, route = routePath()) {
  if (!isManagedRoute(route)) {
    clearRouteFailure();
    delete document.documentElement.dataset.ceV4Loading;
    delete document.documentElement.dataset.ceV4Ready;
    delete document.documentElement.dataset.ceV4Failed;
    return;
  }
  if (active) {
    clearRouteFailure();
    const entering = document.querySelector("#main-content.route-enter");
    entering?.querySelector("#workspace-content")?.classList.remove("ce-v4-content-reveal");
    document.documentElement.dataset.ceV4Loading = "true";
    delete document.documentElement.dataset.ceV4Ready;
    delete document.documentElement.dataset.ceV4Failed;
    return;
  }
  delete document.documentElement.dataset.ceV4Loading;
  delete document.documentElement.dataset.ceV4Failed;
  document.documentElement.dataset.ceV4Ready = "true";
}

function armRouteEnterCleanup(route, actionKey, epoch) {
  const main = document.querySelector("#main-content.route-enter");
  const page = main?.querySelector(".ce-v4-page");
  if (!main) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!page || reduced) {
    if (epoch === routeEpoch && route === routePath() && actionKey === workspaceActionKey()) main.classList.remove("route-enter");
    return;
  }

  let timeout = 0;
  const finish = (event) => {
    if (event && (event.target !== page || event.animationName !== "ce-v4-route-enter")) return;
    page.removeEventListener("animationend", finish);
    window.clearTimeout(timeout);
    if (epoch === routeEpoch && route === routePath() && actionKey === workspaceActionKey()) main.classList.remove("route-enter");
  };
  page.addEventListener("animationend", finish);
  timeout = window.setTimeout(finish, 450);
}

function clearRouteFailure() {
  document.querySelectorAll("[data-route-loader-failure]").forEach((node) => node.remove());
}

function renderRouteFailure(route = routePath()) {
  clearRouteFailure();
  const host = document.querySelector("#main-content") || document.querySelector("#workspace-content");
  if (!(host instanceof HTMLElement)) return null;
  const failure = document.createElement("section");
  failure.className = "ce-v4-route-load-failure card card-pad";
  failure.dataset.routeLoaderFailure = "true";
  failure.dataset.route = route;
  failure.setAttribute("role", "alert");
  failure.setAttribute("aria-live", "assertive");
  failure.tabIndex = -1;

  const title = document.createElement("h2");
  title.textContent = "Не удалось открыть раздел";
  const description = document.createElement("p");
  description.textContent = "Рабочий стол сохранён. Проверьте соединение и повторите попытку.";
  const retryButton = document.createElement("button");
  retryButton.type = "button";
  retryButton.className = "btn btn-primary";
  retryButton.dataset.routeLoaderRetry = "true";
  retryButton.textContent = "Повторить";
  failure.append(title, description, retryButton);
  host.prepend(failure);
  window.requestAnimationFrame(() => failure.focus({ preventScroll: true }));
  return failure;
}

function setFailed(route = routePath(), error = null) {
  if (!isManagedRoute(route) || route !== routePath()) return;
  delete document.documentElement.dataset.ceV4Loading;
  delete document.documentElement.dataset.ceV4Ready;
  document.documentElement.dataset.ceV4Failed = "true";
  renderRouteFailure(route);
  window.dispatchEvent(new CustomEvent("contentengine:v4-route-failed", {
    detail: Object.freeze({ route, build: BUILD, retryable: true, reason: error ? "asset-load" : "unknown" }),
  }));
}

function absoluteAsset(relative) {
  return new URL(relative, import.meta.url).href;
}

function ensureStyle(relative) {
  const href = absoluteAsset(relative);
  if (loadedStyles.has(href) || document.querySelector(`link[data-ce-v4-style="${CSS.escape(href)}"]`)) {
    loadedStyles.add(href);
    return Promise.resolve();
  }
  loadedStyles.add(href);
  return new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.dataset.ceV4Style = href;
    link.addEventListener("load", resolve, { once: true });
    link.addEventListener("error", () => {
      loadedStyles.delete(href);
      link.remove();
      reject(new Error(`ContentEngine stylesheet unavailable: ${relative}`));
    }, { once: true });
    document.head.append(link);
  });
}

function ensureModule(relative) {
  const href = absoluteAsset(relative);
  if (!loadedModules.has(href)) {
    loadedModules.set(href, import(href).catch((error) => {
      loadedModules.delete(href);
      console.warn("ContentEngine route module unavailable", relative, error);
      throw error;
    }));
  }
  return loadedModules.get(href);
}

function reconcileStaleLoad(epoch) {
  if (epoch === routeEpoch) schedule();
  return false;
}

async function loadRoute(route = routePath(), actionKey = workspaceActionKey()) {
  const epoch = ++routeEpoch;
  setLoading(true, route);
  ensureCore();
  await corePromise;
  const matches = Object.values(ROUTE_ASSETS).filter((entry) => entry.match(route));
  const styles = [...new Set(matches.flatMap((entry) => entry.styles))];
  const modules = [...new Set(matches.flatMap((entry) => entry.modules))];
  await Promise.all(styles.map(ensureStyle));
  for (const modulePath of modules) {
    await ensureModule(modulePath);
    if (epoch !== routeEpoch || actionKey !== workspaceActionKey()) return reconcileStaleLoad(epoch);
  }
  if (epoch !== routeEpoch || route !== routePath() || actionKey !== workspaceActionKey()) {
    return reconcileStaleLoad(epoch);
  }
  await window.ContentEngineDesktopV4?.flush?.();
  if (epoch !== routeEpoch || route !== routePath() || actionKey !== workspaceActionKey()) {
    return reconcileStaleLoad(epoch);
  }
  armRouteEnterCleanup(route, actionKey, epoch);
  setLoading(false, route);
  window.dispatchEvent(new CustomEvent("contentengine:v4-route-ready", {
    detail: Object.freeze({ route, actionKey, build: BUILD }),
  }));
  return true;
}

function ensureCore() {
  if (corePromise) return corePromise;
  corePromise = (async () => {
    await Promise.all([
      ensureStyle(`workspace-os-v4-polish.css?v=${BUILD}`),
      ensureStyle(`workspace-os-v4-context-trash.css?v=${BUILD}`),
      ensureStyle(`workspace-os-v4-flow.css?v=${BUILD}`),
      ensureStyle(`workspace-os-v4-stability.css?v=${BUILD}`),
      ensureStyle(`workspace-os-v4-motion.css?v=${BUILD}`),
    ]);
    await ensureModule(`workspace-os-v4.js?v=${BUILD}`);
    await ensureModule(`workspace-os-v4-trash-rpc-alias.js?v=${BUILD}`);
    await ensureModule(`workspace-os-v4-context-trash.js?v=${BUILD}`);
  })().catch((error) => {
    corePromise = null;
    throw error;
  });
  return corePromise;
}

function retry() {
  if (retryPromise) return retryPromise;
  const route = routePath();
  const actionKey = workspaceActionKey();
  const control = document.querySelector("[data-route-loader-retry]");
  if (control instanceof HTMLButtonElement) {
    control.disabled = true;
    control.textContent = "Повторяем…";
  }
  retryPromise = loadRoute(route, actionKey)
    .catch((error) => {
      setFailed(route, error);
      console.error("ContentEngine Desktop v4.19 route retry failed", error);
      return false;
    })
    .finally(() => {
      retryPromise = null;
    });
  return retryPromise;
}

function loadCurrentRoute() {
  const route = routePath();
  const actionKey = workspaceActionKey();
  return loadRoute(route, actionKey).catch((error) => {
    if (route === routePath() && actionKey === workspaceActionKey()) {
      setFailed(route, error);
    }
    console.error("ContentEngine Desktop v4.19 current route failed to load", error);
    return false;
  });
}

function handleRouteLoaderRetry(event) {
  const target = event.target instanceof Element ? event.target.closest("[data-route-loader-retry]") : null;
  if (!target) return;
  event.preventDefault();
  void retry();
}

function schedule() {
  const route = routePath();
  const actionKey = workspaceActionKey();
  const sameAction = actionKey === lastScheduledActionKey;
  lastScheduledActionKey = actionKey;
  if (
    sameAction
    && isManagedRoute(route)
    && document.documentElement.dataset.ceV4Loading !== "true"
  ) {
    window.queueMicrotask(() => {
      void window.ContentEngineDesktopV4?.flush?.();
    });
    return;
  }
  setLoading(isManagedRoute(route), route);
  if (queued) return;
  queued = true;
  window.queueMicrotask(() => {
    queued = false;
    const scheduledRoute = routePath();
    const scheduledActionKey = workspaceActionKey();
    void loadRoute(scheduledRoute, scheduledActionKey).catch((error) => {
      if (scheduledRoute === routePath() && scheduledActionKey === workspaceActionKey()) {
        setFailed(scheduledRoute, error);
      }
      console.error("ContentEngine Desktop v4.19 route failed to start", error);
    });
  });
}

window.addEventListener("hashchange", schedule, { passive: true });
document.addEventListener("click", handleRouteLoaderRetry);
schedule();

window.ContentEngineDesktopV4Loader = Object.freeze({
  build: BUILD,
  route: routePath,
  actionKey: workspaceActionKey,
  load: () => loadCurrentRoute(),
  retry: () => retry(),
});
