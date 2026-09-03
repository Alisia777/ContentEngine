/*
 * Live child-document bootstrap for a ContentEngine application window.
 *
 * The regular Desktop v4 core still owns route adapters and their helpers. The
 * child marker tells that core to mount only the route surface; parent chrome,
 * Dock state, Mission Control and window geometry stay in the parent document.
 */

import {
  CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
  CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
  createContentEngineEmbeddedWindowEvent,
  normalizeContentEngineEmbeddedWindowRoute,
  readContentEngineEmbeddedWindowCommand,
  readContentEngineEmbeddedWindowRequest,
} from "./workspace-embedded-window-contract.js?v=20260826.rebuild-clean.60";

const BUILD = "20260826.rebuild-clean.60";

function embeddedRequest(windowLike = globalThis.window) {
  if (!windowLike) return null;
  const request = readContentEngineEmbeddedWindowRequest(windowLike.location);
  if (!request) return null;
  try {
    if (windowLike.self === windowLike.top || windowLike.parent === windowLike) return null;
    if (
      windowLike.parent.location.origin !== windowLike.location.origin
      || windowLike.top.location.origin !== windowLike.location.origin
    ) return null;
  } catch {
    return null;
  }
  return request;
}

export function contentEngineEmbeddedWindowRequest(windowLike = globalThis.window) {
  return embeddedRequest(windowLike);
}

export function installContentEngineEmbeddedWindowRuntime(options = {}) {
  const request = options.request || embeddedRequest();
  if (!request) return null;
  if (window.ContentEngineEmbeddedWindow?.windowId === request.windowId) {
    return window.ContentEngineEmbeddedWindow;
  }

  const route = typeof options.route === "function"
    ? options.route
    : () => String(window.location.hash || "#/workspace/home").replace(/^#/u, "").split("?")[0];
  const actionKey = typeof options.actionKey === "function" ? options.actionKey : route;
  let focusFrame = 0;
  let announcedReady = false;

  const normalizedRoutePath = (value = route()) => (
    normalizeContentEngineEmbeddedWindowRoute(value)?.split("?")[0] || "/workspace/home"
  );

  const setBodyMode = () => {
    document.documentElement.dataset.contentengineOs = "v4";
    document.documentElement.dataset.ceWindowChild = "true";
    document.documentElement.dataset.ceWindowId = request.windowId;
    document.body?.classList.add("contentengine-desktop-v4", "contentengine-window-child");
    if (document.body) {
      document.body.dataset.ceV4Stable = "true";
      document.body.dataset.ceWindowChild = "true";
      document.body.dataset.ceWindowId = request.windowId;
    }
  };

  const postStatus = (eventName, value = route(), details = {}) => {
    const message = createContentEngineEmbeddedWindowEvent(eventName, {
      ...details,
      windowId: request.windowId,
      route: normalizedRoutePath(value),
    });
    window.parent.postMessage(message, window.location.origin);
    return message;
  };

  const markLoading = (value = route()) => {
    const path = normalizedRoutePath(value);
    document.documentElement.dataset.ceWindowRoute = path;
    document.documentElement.dataset.ceWindowChildReady = "false";
    delete document.documentElement.dataset.ceWindowChildFailed;
    if (document.body) {
      document.body.dataset.ceWindowRoute = path;
      document.body.dataset.ceWindowChildReady = "false";
      delete document.body.dataset.ceWindowChildFailed;
    }
  };

  const markReady = (value = route()) => {
    const path = normalizedRoutePath(value);
    document.documentElement.dataset.ceWindowRoute = path;
    document.documentElement.dataset.ceWindowChildReady = "true";
    delete document.documentElement.dataset.ceWindowChildFailed;
    if (document.body) {
      document.body.dataset.ceWindowRoute = path;
      document.body.dataset.ceWindowChildReady = "true";
      delete document.body.dataset.ceWindowChildFailed;
    }
    const eventName = announcedReady ? "route" : "ready";
    announcedReady = true;
    return postStatus(eventName, path);
  };

  const markFailed = (value = route()) => {
    const path = normalizedRoutePath(value);
    document.documentElement.dataset.ceWindowRoute = path;
    document.documentElement.dataset.ceWindowChildReady = "false";
    document.documentElement.dataset.ceWindowChildFailed = "true";
    if (document.body) {
      document.body.dataset.ceWindowRoute = path;
      document.body.dataset.ceWindowChildReady = "false";
      document.body.dataset.ceWindowChildFailed = "true";
    }
    return postStatus("failed", path);
  };

  const navigate = (destination) => {
    const normalized = normalizeContentEngineEmbeddedWindowRoute(destination);
    if (!normalized) return false;
    const hash = `#${normalized}`;
    if (window.location.hash === hash) {
      void window.ContentEngineDesktopV4Loader?.load?.();
      return true;
    }
    window.location.hash = hash;
    return true;
  };

  const requestShortcut = (shortcut) => postStatus("shortcut", route(), { shortcut });

  const embeddedApi = Object.freeze({
    build: BUILD,
    version: CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
    messageType: CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
    windowId: request.windowId,
    route,
    actionKey,
    navigate,
    flush: () => window.ContentEngineDesktopV4?.flush?.() || Promise.resolve(),
    markLoading,
    markReady,
    markFailed,
    requestShortcut,
    requestMount: () => window.ContentEngineDesktopV4?.requestMount?.(),
  });

  window.CONTENTENGINE_DESKTOP_V4 = true;
  window.CONTENTENGINE_EMBEDDED_WINDOW = true;
  window.ContentEngineEmbeddedWindow = embeddedApi;
  setBodyMode();
  markLoading();

  const announceFocus = () => {
    if (focusFrame) return;
    focusFrame = window.requestAnimationFrame(() => {
      focusFrame = 0;
      postStatus("focus");
    });
  };

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin || event.source !== window.parent) return;
    const command = readContentEngineEmbeddedWindowCommand(event.data, request.windowId);
    if (command) navigate(command.route);
  });
  document.addEventListener("pointerdown", announceFocus, true);
  document.addEventListener("focusin", announceFocus, true);
  window.addEventListener("focus", announceFocus);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      setBodyMode();
      markLoading();
    }, { once: true });
  }

  return embeddedApi;
}
