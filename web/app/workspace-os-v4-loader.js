/*
 * ContentEngine Desktop v4.7 route loader.
 *
 * Keeps one global desktop controller alive and loads heavy route adapters only
 * when their workspace is opened. Same-origin assets only; no API calls and no
 * business mutations. Legacy polish/surface observers are deliberately retired
 * in favour of one deterministic stability coordinator.
 */

import { workspaceActionKey } from "./workspace-action-key.js?v=20260804.os4.7";

const BUILD = "20260804.os4.7";
const loadedStyles = new Set();
const loadedModules = new Map();
let queued = false;
let routeEpoch = 0;
let lastScheduledActionKey = "";

window.CONTENTENGINE_DESKTOP_V4 = true;

const ROUTE_ASSETS = Object.freeze({
  aiLearning: Object.freeze({
    match: (route) => route === "/workspace/ai",
    styles: ["ai-learning-control-room.css?v=20260804.3"],
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
    delete document.documentElement.dataset.ceV4Loading;
    delete document.documentElement.dataset.ceV4Ready;
    delete document.documentElement.dataset.ceV4Failed;
    return;
  }
  if (active) {
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

function setFailed(route = routePath()) {
  if (!isManagedRoute(route)) return;
  delete document.documentElement.dataset.ceV4Loading;
  delete document.documentElement.dataset.ceV4Ready;
  document.documentElement.dataset.ceV4Failed = "true";
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

async function loadRoute(route = routePath(), actionKey = workspaceActionKey()) {
  const epoch = ++routeEpoch;
  setLoading(true, route);
  await corePromise;
  const matches = Object.values(ROUTE_ASSETS).filter((entry) => entry.match(route));
  const styles = [...new Set(matches.flatMap((entry) => entry.styles))];
  const modules = [...new Set(matches.flatMap((entry) => entry.modules))];
  await Promise.all(styles.map(ensureStyle));
  for (const modulePath of modules) {
    await ensureModule(modulePath);
    if (epoch !== routeEpoch || actionKey !== workspaceActionKey()) return false;
  }
  if (epoch !== routeEpoch || route !== routePath() || actionKey !== workspaceActionKey()) return false;
  await window.ContentEngineDesktopV4?.flush?.();
  if (epoch !== routeEpoch || route !== routePath() || actionKey !== workspaceActionKey()) return false;
  armRouteEnterCleanup(route, actionKey, epoch);
  setLoading(false, route);
  window.dispatchEvent(new CustomEvent("contentengine:v4-route-ready", {
    detail: Object.freeze({ route, actionKey, build: BUILD }),
  }));
  return true;
}

function schedule() {
  const route = routePath();
  const actionKey = workspaceActionKey();
  const sameAction = actionKey === lastScheduledActionKey;
  lastScheduledActionKey = actionKey;
  if (sameAction && isManagedRoute(route)) {
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
    void loadRoute(routePath(), workspaceActionKey()).catch((error) => {
      setFailed(routePath());
      console.error("ContentEngine Desktop v4.7 route failed to start", error);
    });
  });
}

const corePromise = (async () => {
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
})();

window.addEventListener("hashchange", schedule, { passive: true });
schedule();

window.ContentEngineDesktopV4Loader = Object.freeze({
  build: BUILD,
  route: routePath,
  actionKey: workspaceActionKey,
  load: () => loadRoute(),
});
