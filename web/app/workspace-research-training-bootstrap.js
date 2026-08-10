/*
 * ContentEngine · lazy bootstrap for the governed research learning flow.
 *
 * Desktop v4 keeps its small, audited route-loader contract. This classic
 * self-script waits until that loader declares the current route ready, then
 * dynamically imports only the research/AI/recommendation assets needed by the
 * route. No provider request, research run or paid call is started here.
 */

(() => {
  "use strict";

  const BUILD = "20260810.research.27";
  const SCRIPT_URL = document.currentScript?.src || window.location.href;
  const BASE_URL = new URL(".", SCRIPT_URL);
  const loadedStyles = new Map();
  const loadedModules = new Map();
  const decoratedApis = new WeakSet();
  let epoch = 0;
  let queued = false;

  const RPC_ALIASES = Object.freeze({
    creator_ai_research_training_queue:
      "contentengine_ai_research_training_queue",
    creator_decide_ai_research_training:
      "contentengine_decide_ai_research_training",
    creator_generation_research_recommendations:
      "contentengine_generation_research_recommendations",
  });

  const ROUTES = Object.freeze([
    Object.freeze({
      match: (route) => route === "/workspace/research",
      styles: [
        "workspace-research-video-intake.css",
        "workspace-research-failure-recovery.css",
      ],
      modules: [
        "workspace-research-video-intake.js",
        "workspace-research-failure-recovery.js",
      ],
      requiresRpcAliases: false,
    }),
    Object.freeze({
      match: (route) => route === "/workspace/media",
      styles: ["workspace-research-failure-recovery.css"],
      modules: ["workspace-research-failure-recovery.js"],
      requiresRpcAliases: false,
    }),
    Object.freeze({
      match: (route) => route === "/workspace/ai",
      styles: [
        "workspace-ai-research-training.css",
        "workspace-ai-exact-youtube-sources.css",
        "workspace-research-failure-recovery.css",
      ],
      modules: [
        "workspace-ai-research-training.js",
        "workspace-ai-exact-youtube-sources.js",
        "workspace-research-failure-recovery.js",
      ],
      requiresRpcAliases: true,
    }),
    Object.freeze({
      match: (route) => route === "/workspace/generation",
      styles: ["workspace-generation-research-recommendations.css"],
      modules: ["workspace-generation-research-recommendations.js"],
      requiresRpcAliases: true,
    }),
  ]);

  function routePath() {
    const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
    return (`/${raw.split("?")[0] || ""}`)
      .replace(/\/{2,}/gu, "/")
      .replace(/\/$/u, "") || "/";
  }

  function assetUrl(file) {
    return new URL(`${file}?v=${BUILD}`, BASE_URL).href;
  }

  function ensureStyle(file) {
    const href = assetUrl(file);
    if (loadedStyles.has(href)) return loadedStyles.get(href);
    const existing = [...document.querySelectorAll('link[rel="stylesheet"]')]
      .find((link) => link.href === href);
    if (existing) {
      const ready = Promise.resolve();
      loadedStyles.set(href, ready);
      return ready;
    }
    const promise = new Promise((resolve, reject) => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = href;
      link.dataset.researchLearningStyle = file;
      link.addEventListener("load", resolve, { once: true });
      link.addEventListener("error", () => {
        loadedStyles.delete(href);
        link.remove();
        reject(new Error(`Research learning stylesheet unavailable: ${file}`));
      }, { once: true });
      document.head.append(link);
    });
    loadedStyles.set(href, promise);
    return promise;
  }

  function ensureModule(file) {
    const href = assetUrl(file);
    if (!loadedModules.has(href)) {
      loadedModules.set(href, import(href).catch((error) => {
        loadedModules.delete(href);
        throw error;
      }));
    }
    return loadedModules.get(href);
  }

  async function installRpcAliases() {
    let api = window.ContentEngineWorkspaceRuntime?.getApi?.();
    if (api && typeof api.then === "function") api = await api;
    if (!api || typeof api.call !== "function") return false;
    if (decoratedApis.has(api)) return true;

    const originalCall = api.call.bind(api);
    const bridgedCall = function bridgedResearchLearningCall(
      functionName,
      payload = {},
    ) {
      const exactName = RPC_ALIASES[functionName] || functionName;
      return originalCall(exactName, payload);
    };

    try {
      Object.defineProperty(api, "call", {
        configurable: true,
        enumerable: false,
        writable: true,
        value: bridgedCall,
      });
    } catch {
      try {
        api.call = bridgedCall;
      } catch {
        return false;
      }
    }
    decoratedApis.add(api);
    return true;
  }

  async function loadCurrentRoute() {
    const route = routePath();
    const currentEpoch = ++epoch;
    const matches = ROUTES.filter((entry) => entry.match(route));
    if (!matches.length) return;
    const styles = [...new Set(matches.flatMap((entry) => entry.styles))];
    const modules = [...new Set(matches.flatMap((entry) => entry.modules))];
    const requiresRpcAliases = matches.some(
      (entry) => entry.requiresRpcAliases === true,
    );
    try {
      if (requiresRpcAliases && !await installRpcAliases()) {
        throw new Error("Research learning API bridge is unavailable");
      }
      await Promise.all(styles.map(ensureStyle));
      for (const moduleName of modules) {
        await ensureModule(moduleName);
        if (currentEpoch !== epoch || route !== routePath()) return;
      }
      await window.ContentEngineDesktopV4?.flush?.();
    } catch (error) {
      console.warn("Research learning route extension unavailable", route, error);
      window.dispatchEvent(new CustomEvent("contentengine:research-learning-failed", {
        detail: Object.freeze({ route, build: BUILD }),
      }));
    }
  }

  function schedule() {
    if (queued) return;
    queued = true;
    window.queueMicrotask(() => {
      queued = false;
      void loadCurrentRoute();
    });
  }

  window.addEventListener("contentengine:v4-route-ready", schedule);
  if (document.documentElement.dataset.ceV4Ready === "true") {
    schedule();
  }

  window.ContentEngineResearchLearningBootstrap = Object.freeze({
    build: BUILD,
    route: routePath,
    load: loadCurrentRoute,
    rpcAliases: RPC_ALIASES,
  });
})();
