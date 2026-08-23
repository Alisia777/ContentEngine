/*
 * ContentEngine embedded workspace window contract.
 *
 * This module is deliberately pure: it does not inspect browser storage,
 * authentication state or the DOM. The desktop shell and focused source tests
 * can therefore share one URL/message vocabulary without sharing runtime state.
 */

export const CONTENTENGINE_EMBEDDED_WINDOW_VERSION = 1;
export const CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE = "contentengine:embedded-window";
export const CONTENTENGINE_EMBEDDED_WINDOW_QUERY = "ce_window";
export const CONTENTENGINE_EMBEDDED_WINDOW_ID_QUERY = "ce_window_id";

const WINDOW_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,95}$/u;
const WORKSPACE_PATH_PATTERN = /^\/workspace\/[a-z][a-z0-9-]{0,63}$/u;
const CHILD_EVENTS = new Set(["ready", "route", "failed", "focus", "shortcut"]);
const CHILD_SHORTCUTS = new Set(["search"]);

function text(value) {
  return typeof value === "string" ? value.trim() : "";
}

export function normalizeContentEngineEmbeddedWindowId(value) {
  const candidate = text(value);
  return WINDOW_ID_PATTERN.test(candidate) ? candidate : "";
}

export function normalizeContentEngineEmbeddedWindowRoute(value) {
  const candidate = text(value).replace(/^#/u, "");
  if (
    !candidate.startsWith("/")
    || candidate.startsWith("//")
    || candidate.includes("\\")
    || candidate.length > 2048
  ) return "";

  let parsed;
  try {
    parsed = new URL(candidate, "https://contentengine.invalid/");
  } catch {
    return "";
  }
  if (parsed.origin !== "https://contentengine.invalid" || !WORKSPACE_PATH_PATTERN.test(parsed.pathname)) return "";
  if (parsed.hash || parsed.username) return "";
  return `${parsed.pathname}${parsed.search}`;
}

export function createContentEngineEmbeddedWindowUrl(route, options = {}) {
  const normalizedRoute = normalizeContentEngineEmbeddedWindowRoute(route) || "/workspace/home";
  const windowId = normalizeContentEngineEmbeddedWindowId(options.windowId);
  if (!windowId) throw new TypeError("Embedded ContentEngine window requires a safe windowId");

  const baseUrl = text(options.baseUrl)
    || (typeof globalThis.location?.href === "string" ? globalThis.location.href : "");
  if (!baseUrl) throw new TypeError("Embedded ContentEngine window requires a baseUrl outside the browser");

  const url = new URL("./index.html", baseUrl);
  url.search = "";
  url.hash = "";
  url.searchParams.set(CONTENTENGINE_EMBEDDED_WINDOW_QUERY, "1");
  url.searchParams.set(CONTENTENGINE_EMBEDDED_WINDOW_ID_QUERY, windowId);
  url.hash = `#${normalizedRoute}`;
  return url.href;
}

export function readContentEngineEmbeddedWindowRequest(locationLike) {
  const rawSearch = typeof locationLike?.search === "string" ? locationLike.search : "";
  const query = new URLSearchParams(rawSearch);
  const modes = query.getAll(CONTENTENGINE_EMBEDDED_WINDOW_QUERY);
  const ids = query.getAll(CONTENTENGINE_EMBEDDED_WINDOW_ID_QUERY);
  if (modes.length !== 1 || modes[0] !== "1" || ids.length !== 1) return null;
  const windowId = normalizeContentEngineEmbeddedWindowId(ids[0]);
  if (!windowId || windowId !== ids[0]) return null;
  return Object.freeze({
    version: CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
    windowId,
  });
}

export function readContentEngineEmbeddedWindowCommand(value, expectedWindowId = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (
    value.type !== CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE
    || value.version !== CONTENTENGINE_EMBEDDED_WINDOW_VERSION
    || value.command !== "navigate"
  ) return null;
  const windowId = normalizeContentEngineEmbeddedWindowId(value.windowId);
  const expected = normalizeContentEngineEmbeddedWindowId(expectedWindowId);
  const route = normalizeContentEngineEmbeddedWindowRoute(value.route);
  if (!windowId || (expected && windowId !== expected) || !route) return null;
  return Object.freeze({ command: "navigate", windowId, route });
}

export function createContentEngineEmbeddedWindowEvent(eventName, details = {}) {
  const event = text(eventName);
  const windowId = normalizeContentEngineEmbeddedWindowId(details.windowId);
  const route = normalizeContentEngineEmbeddedWindowRoute(details.route)?.split("?")[0] || "";
  if (!CHILD_EVENTS.has(event) || !windowId || !route) {
    throw new TypeError("Invalid embedded ContentEngine window event");
  }
  const message = {
    type: CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE,
    version: CONTENTENGINE_EMBEDDED_WINDOW_VERSION,
    event,
    windowId,
    route,
  };
  if (event === "shortcut") {
    const shortcut = text(details.shortcut);
    if (!CHILD_SHORTCUTS.has(shortcut)) throw new TypeError("Invalid embedded ContentEngine shortcut");
    message.shortcut = shortcut;
  }
  return Object.freeze(message);
}

export function readContentEngineEmbeddedWindowEvent(value, expectedWindowId = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  if (
    value.type !== CONTENTENGINE_EMBEDDED_WINDOW_MESSAGE
    || value.version !== CONTENTENGINE_EMBEDDED_WINDOW_VERSION
    || !CHILD_EVENTS.has(value.event)
  ) return null;
  const windowId = normalizeContentEngineEmbeddedWindowId(value.windowId);
  const expected = normalizeContentEngineEmbeddedWindowId(expectedWindowId);
  const route = normalizeContentEngineEmbeddedWindowRoute(value.route)?.split("?")[0] || "";
  if (!windowId || (expected && windowId !== expected) || !route) return null;
  const result = { event: value.event, windowId, route };
  if (value.event === "shortcut") {
    const shortcut = text(value.shortcut);
    if (!CHILD_SHORTCUTS.has(shortcut)) return null;
    result.shortcut = shortcut;
  }
  return Object.freeze(result);
}
