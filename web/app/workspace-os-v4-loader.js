/*
 * ContentEngine Desktop v4 route loader.
 *
 * Keeps one global desktop controller alive and loads heavy route adapters only
 * when their workspace is actually opened. Same-origin assets only; no API
 * calls and no business mutations.
 */

const BUILD = "20260731.4";
const loadedStyles = new Set();
const loadedModules = new Map();
let queued = false;

window.CONTENTENGINE_DESKTOP_V4 = true;

const OPERATIONAL_ROUTES = new Set([
  "/workspace/review",
  "/workspace/tasks",
  "/workspace/placement",
  "/workspace/stats",
  "/workspace/payouts",
]);

const ROUTE_ASSETS = Object.freeze({
  finder: Object.freeze({
    match: (route) => route === "/workspace/board",
    styles: ["workspace-os-v4-finder.css?v=20260731.4"],
    modules: ["workspace-os-v4-finder.js?v=20260731.4"],
  }),
  operations: Object.freeze({
    match: (route) => OPERATIONAL_ROUTES.has(route) || route === "/learn" || route.startsWith("/learn/"),
    styles: ["workspace-os-v4-operations.css?v=20260731.4"],
    modules: ["workspace-os-v4-operations.js?v=20260731.4"],
  }),
  review: Object.freeze({
    match: (route) => route === "/workspace/review",
    styles: [
      "workspace-desktop-os.css?v=20260730.1",
      "workspace-desktop-review.css?v=20260730.1",
      "workspace-desktop-review-form.css?v=20260730.1",
      "workspace-desktop-review-result.css?v=20260730.1",
      "workspace-desktop-responsive.css?v=20260730.1",
    ],
    modules: ["workspace-desktop-os.js?v=20260730.1"],
  }),
  academy: Object.freeze({
    match: (route) => route === "/learn" || route.startsWith("/learn/"),
    styles: [
      "workspace-desktop-os.css?v=20260730.1",
      "workspace-desktop-academy.css?v=20260730.1",
      "workspace-academy-os-v2.css?v=20260730.1",
      "workspace-desktop-responsive.css?v=20260730.1",
      "workspace-academy-lab-v3.css?v=20260731.1",
    ],
    modules: [
      "workspace-desktop-os.js?v=20260730.1",
      "workspace-academy-os-v2.js?v=20260730.1",
      "workspace-academy-lab-v3.js?v=20260731.1",
    ],
  }),
  generation: Object.freeze({
    match: (route) => route === "/workspace/generation",
    styles: ["workspace-generation-os.css?v=20260731.1"],
    modules: ["workspace-generation-os.js?v=20260731.1"],
  }),
  media: Object.freeze({
    match: (route) => route === "/workspace/media",
    styles: ["workspace-media-finder.css?v=20260731.1"],
    modules: ["workspace-media-finder.js?v=20260731.1"],
  }),
  publishing: Object.freeze({
    match: (route) => route === "/workspace/placement",
    styles: ["workspace-publishing-os.css?v=20260731.1"],
    modules: [
      "workspace-publishing-os.js?v=20260731.1",
      "workspace-os-v3-native-bridge.js?v=20260731.1",
    ],
  }),
  work: Object.freeze({
    match: (route) => route === "/workspace/work" || route === "/workspace/tasks",
    styles: ["workspace-work-stage-manager.css?v=20260731.1"],
    modules: [
      "workspace-work-stage-manager.js?v=20260731.1",
      "workspace-os-v3-native-bridge.js?v=20260731.1",
    ],
  }),
  results: Object.freeze({
    match: (route) => route === "/workspace/stats" || route === "/workspace/payouts",
    styles: ["workspace-results-ledger.css?v=20260731.1"],
    modules: ["workspace-results-ledger.js?v=20260731.1"],
  }),
});

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
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
  return new Promise((resolve) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    link.dataset.ceV4Style = href;
    link.addEventListener("load", resolve, { once: true });
    link.addEventListener("error", resolve, { once: true });
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

async function loadRoute(route = routePath()) {
  const matches = Object.values(ROUTE_ASSETS).filter((entry) => entry.match(route));
  for (const entry of matches) {
    await Promise.all(entry.styles.map(ensureStyle));
    for (const modulePath of entry.modules) await ensureModule(modulePath);
  }
  window.dispatchEvent(new CustomEvent("contentengine:v4-route-ready", {
    detail: Object.freeze({ route, build: BUILD }),
  }));
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    void loadRoute();
  });
}

const corePromise = Promise.all([
  ensureModule(`workspace-os-v4.js?v=${BUILD}`),
]);

corePromise.then(schedule).catch((error) => {
  console.error("ContentEngine Desktop v4 failed to start", error);
});

window.addEventListener("hashchange", schedule, { passive: true });
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineDesktopV4Loader = Object.freeze({
  build: BUILD,
  route: routePath,
  load: () => loadRoute(),
});
