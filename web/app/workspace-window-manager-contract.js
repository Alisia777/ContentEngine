/*
 * Workspace window manager contract v4.8.
 *
 * This module is deliberately limited to deterministic state transitions.
 * Rendering, navigation, persistence transports and business operations belong
 * to their existing owners and must consume this contract from the outside.
 */

export const WORKSPACE_WINDOW_MANAGER_CONTRACT_VERSION = "4.8";

export const WORKSPACE_WINDOW_MANAGER_ACTIONS = Object.freeze([
  "open",
  "focus",
  "close",
  "minimize",
  "restore",
  "move",
  "resize",
  "toggleZoom",
  "switchSpace",
]);

export const WORKSPACE_WINDOW_DEFAULT_BOUNDS = Object.freeze({
  width: 1440,
  height: 900,
});

export const WORKSPACE_WINDOW_MIN_SIZE = Object.freeze({
  width: 320,
  height: 220,
});

const DEFAULT_SPACE_ID = "space:main";
const DEFAULT_WINDOW_SIZE = Object.freeze({ width: 920, height: 680 });
const MAX_WINDOWS = 128;
// Every accepted window may legitimately belong to its own project Space,
// plus the global main Space. A smaller cap would silently mix projects.
const MAX_SPACES = MAX_WINDOWS + 1;
const MAX_SELECTION_IDS = 64;
const MAX_SCROLL_OFFSET = 100_000_000;
const MAX_SAFE_DIMENSION = 100_000;
const SAFE_KEY = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$/u;
const SECRETISH_VALUE = /^(?:bearer\s|secret[-_:]|token[-_:]|[spr]k[-_])/iu;

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function owns(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function finiteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function integerBetween(value, fallback, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, Math.round(finiteNumber(value, fallback))));
}

function safeKey(value, fallback = "") {
  const candidate = typeof value === "string" ? value.trim() : "";
  if (!candidate || !SAFE_KEY.test(candidate) || SECRETISH_VALUE.test(candidate)) return fallback;
  return candidate;
}

function normalizeBounds(raw) {
  const source = isRecord(raw) ? raw : {};
  return {
    width: integerBetween(
      source.width,
      WORKSPACE_WINDOW_DEFAULT_BOUNDS.width,
      1,
      MAX_SAFE_DIMENSION,
    ),
    height: integerBetween(
      source.height,
      WORKSPACE_WINDOW_DEFAULT_BOUNDS.height,
      1,
      MAX_SAFE_DIMENSION,
    ),
  };
}

function normalizeProjectContext(raw) {
  if (!isRecord(raw)) return null;
  const organizationId = safeKey(raw.organizationId ?? raw.organization_id);
  const projectId = safeKey(raw.projectId ?? raw.project_id);
  if (!organizationId && !projectId) return null;
  return {
    organizationId,
    projectId,
  };
}

function normalizeSelection(raw) {
  if (typeof raw === "string") {
    const id = safeKey(raw);
    return id ? { id } : null;
  }
  if (Array.isArray(raw)) {
    const ids = [...new Set(raw.map((value) => safeKey(value)).filter(Boolean))]
      .slice(0, MAX_SELECTION_IDS);
    return ids.length ? { ids } : null;
  }
  if (!isRecord(raw)) return null;

  const selection = {};
  const kind = safeKey(raw.kind);
  const id = safeKey(raw.id);
  const tabId = safeKey(raw.tabId ?? raw.tab_id);
  const viewId = safeKey(raw.viewId ?? raw.view_id);
  const ids = Array.isArray(raw.ids)
    ? [...new Set(raw.ids.map((value) => safeKey(value)).filter(Boolean))]
      .slice(0, MAX_SELECTION_IDS)
    : [];
  if (kind) selection.kind = kind;
  if (id) selection.id = id;
  if (ids.length) selection.ids = ids;
  if (tabId) selection.tabId = tabId;
  if (viewId) selection.viewId = viewId;
  return Object.keys(selection).length ? selection : null;
}

function normalizeScroll(raw) {
  const source = isRecord(raw) ? raw : {};
  return {
    top: integerBetween(source.top, 0, 0, MAX_SCROLL_OFFSET),
    left: integerBetween(source.left, 0, 0, MAX_SCROLL_OFFSET),
  };
}

function geometryParts(raw) {
  const source = isRecord(raw) ? raw : {};
  const position = isRecord(source.position) ? source.position : source;
  const size = isRecord(source.size) ? source.size : source;
  return { position, size };
}

export function clampWorkspaceWindowGeometry(raw = {}, rawBounds = {}) {
  const bounds = normalizeBounds(rawBounds);
  const { position, size } = geometryParts(raw);
  const minimumWidth = Math.min(WORKSPACE_WINDOW_MIN_SIZE.width, bounds.width);
  const minimumHeight = Math.min(WORKSPACE_WINDOW_MIN_SIZE.height, bounds.height);
  const width = integerBetween(
    size.width,
    Math.min(DEFAULT_WINDOW_SIZE.width, bounds.width),
    minimumWidth,
    bounds.width,
  );
  const height = integerBetween(
    size.height,
    Math.min(DEFAULT_WINDOW_SIZE.height, bounds.height),
    minimumHeight,
    bounds.height,
  );
  return {
    position: {
      x: integerBetween(position.x, 0, 0, Math.max(0, bounds.width - width)),
      y: integerBetween(position.y, 0, 0, Math.max(0, bounds.height - height)),
    },
    size: { width, height },
  };
}

function normalizeWindow(raw, bounds, index = 0) {
  if (!isRecord(raw)) return null;
  const appId = safeKey(raw.appId ?? raw.app_id);
  const windowId = safeKey(raw.windowId ?? raw.window_id);
  const spaceId = safeKey(raw.spaceId ?? raw.space_id, DEFAULT_SPACE_ID);
  if (!appId || !windowId) return null;
  const geometry = clampWorkspaceWindowGeometry(raw, bounds);
  return {
    appId,
    windowId,
    spaceId,
    position: geometry.position,
    size: geometry.size,
    zIndex: integerBetween(raw.zIndex ?? raw.z_index, index + 1, 1, 1_000_000),
    minimized: raw.minimized === true,
    zoomed: raw.zoomed === true,
    projectContext: normalizeProjectContext(raw.projectContext ?? raw.project_context),
    selection: normalizeSelection(raw.selection),
    scroll: normalizeScroll(raw.scroll),
  };
}

function compactZOrder(windows) {
  return windows
    .map((item, index) => ({ item, index }))
    .sort((left, right) => (
      left.item.zIndex - right.item.zIndex
      || left.index - right.index
      || left.item.windowId.localeCompare(right.item.windowId)
    ))
    .map(({ item }, index) => ({ ...item, zIndex: index + 1 }));
}

function topVisibleWindowId(windows, spaceId) {
  return windows
    .filter((item) => item.spaceId === spaceId && !item.minimized)
    .sort((left, right) => right.zIndex - left.zIndex)[0]?.windowId || null;
}

function normalizedSpaceIds(rawSpaces, windows, requestedActiveSpaceId) {
  const ids = [];
  const add = (value) => {
    const id = safeKey(value);
    if (id && !ids.includes(id) && ids.length < MAX_SPACES) ids.push(id);
  };
  if (Array.isArray(rawSpaces)) rawSpaces.forEach((space) => add(space?.spaceId ?? space?.space_id));
  windows.forEach((item) => add(item.spaceId));
  add(requestedActiveSpaceId);
  add(DEFAULT_SPACE_ID);
  return ids.length ? ids : [DEFAULT_SPACE_ID];
}

function normalizeSpaces(rawSpaces, windows, activeSpaceCandidate) {
  const candidates = new Map();
  if (Array.isArray(rawSpaces)) {
    rawSpaces.forEach((raw) => {
      if (!isRecord(raw)) return;
      const spaceId = safeKey(raw.spaceId ?? raw.space_id);
      if (!spaceId || candidates.has(spaceId)) return;
      candidates.set(spaceId, safeKey(raw.activeWindowId ?? raw.active_window_id));
    });
  }

  const spaceIds = normalizedSpaceIds(rawSpaces, windows, activeSpaceCandidate);
  const spaces = spaceIds.map((spaceId) => {
    const windowIds = windows
      .filter((item) => item.spaceId === spaceId)
      .sort((left, right) => left.zIndex - right.zIndex)
      .map((item) => item.windowId);
    const activeCandidate = candidates.get(spaceId) || "";
    const activeWindow = windows.find((item) => (
      item.windowId === activeCandidate
      && item.spaceId === spaceId
      && !item.minimized
    ));
    return {
      spaceId,
      windowIds,
      activeWindowId: activeWindow?.windowId || topVisibleWindowId(windows, spaceId),
    };
  });
  const requested = safeKey(activeSpaceCandidate);
  const activeSpaceId = spaces.some((space) => space.spaceId === requested)
    ? requested
    : spaces[0].spaceId;
  return { spaces, activeSpaceId };
}

export function createWorkspaceWindowManagerState(seed = {}) {
  const source = isRecord(seed) ? seed : {};
  const bounds = normalizeBounds(source.bounds);
  const seen = new Set();
  const normalizedWindows = (Array.isArray(source.windows) ? source.windows : [])
    .slice(0, MAX_WINDOWS)
    .map((raw, index) => normalizeWindow(raw, bounds, index))
    .filter((item) => {
      if (!item || seen.has(item.windowId)) return false;
      seen.add(item.windowId);
      return true;
    });
  const windows = compactZOrder(normalizedWindows);
  const normalizedSpaces = normalizeSpaces(source.spaces, windows, source.activeSpaceId);
  return {
    version: WORKSPACE_WINDOW_MANAGER_CONTRACT_VERSION,
    bounds,
    activeSpaceId: normalizedSpaces.activeSpaceId,
    spaces: normalizedSpaces.spaces,
    windows,
  };
}

function nextZIndex(state) {
  return state.windows.reduce((maximum, item) => Math.max(maximum, item.zIndex), 0) + 1;
}

function spaceWithActiveWindow(spaces, spaceId, activeWindowId) {
  return spaces.map((space) => (
    space.spaceId === spaceId ? { ...space, activeWindowId } : space
  ));
}

function ensureSpace(spaces, spaceId) {
  if (spaces.some((space) => space.spaceId === spaceId)) return spaces;
  if (spaces.length >= MAX_SPACES) return spaces;
  return [...spaces, { spaceId, windowIds: [], activeWindowId: null }];
}

function rebuildState(state, windows, spaces = state.spaces, activeSpaceId = state.activeSpaceId) {
  return createWorkspaceWindowManagerState({
    version: WORKSPACE_WINDOW_MANAGER_CONTRACT_VERSION,
    bounds: state.bounds,
    activeSpaceId,
    spaces,
    windows,
  });
}

function actionPayload(action) {
  return isRecord(action?.window) ? action.window : action;
}

function mergeSafeMemory(item, payload) {
  if (!isRecord(payload)) return item;
  const update = {};
  if (owns(payload, "selection")) update.selection = normalizeSelection(payload.selection);
  if (owns(payload, "scroll")) update.scroll = normalizeScroll(payload.scroll);
  return Object.keys(update).length ? { ...item, ...update } : item;
}

function focusWindow(state, windowId, payload = {}) {
  const target = state.windows.find((item) => item.windowId === windowId);
  if (!target) return state;
  const windows = state.windows.map((item) => (
    item.windowId === windowId
      ? mergeSafeMemory({ ...item, minimized: false, zIndex: nextZIndex(state) }, payload)
      : item
  ));
  const spaces = spaceWithActiveWindow(state.spaces, target.spaceId, windowId);
  return rebuildState(state, windows, spaces, target.spaceId);
}

function reduceOpen(state, action) {
  const payload = actionPayload(action);
  const appId = safeKey(payload.appId ?? payload.app_id);
  const windowId = safeKey(payload.windowId ?? payload.window_id);
  if (!appId || !windowId) return state;
  const existing = state.windows.find((item) => item.windowId === windowId);
  if (existing) return focusWindow(state, windowId, payload);
  if (state.windows.length >= MAX_WINDOWS) return state;

  let spaceId = safeKey(payload.spaceId ?? payload.space_id, state.activeSpaceId);
  let spaces = ensureSpace(state.spaces, spaceId);
  // Never place a window in another project's Space when capacity is reached.
  if (!spaces.some((space) => space.spaceId === spaceId)) return state;
  const ordinal = state.windows.filter((item) => item.spaceId === spaceId).length;
  const fallbackPosition = 32 + (ordinal % 8) * 28;
  const rawWindow = {
    ...payload,
    appId,
    windowId,
    spaceId,
    position: isRecord(payload.position)
      ? payload.position
      : { x: fallbackPosition, y: fallbackPosition },
    zIndex: nextZIndex(state),
    minimized: false,
  };
  const created = normalizeWindow(rawWindow, state.bounds, state.windows.length);
  if (!created) return state;
  spaces = spaceWithActiveWindow(spaces, spaceId, windowId);
  return rebuildState(state, [...state.windows, created], spaces, spaceId);
}

function reduceClose(state, action) {
  const windowId = safeKey(action.windowId ?? action.window_id);
  const target = state.windows.find((item) => item.windowId === windowId);
  if (!target) return state;
  const windows = state.windows.filter((item) => item.windowId !== windowId);
  const spaces = state.spaces.map((space) => (
    space.spaceId === target.spaceId
      ? { ...space, activeWindowId: topVisibleWindowId(windows, target.spaceId) }
      : space
  ));
  return rebuildState(state, windows, spaces);
}

function reduceMinimize(state, action) {
  const windowId = safeKey(action.windowId ?? action.window_id);
  const target = state.windows.find((item) => item.windowId === windowId);
  if (!target || target.minimized) return state;
  const windows = state.windows.map((item) => (
    item.windowId === windowId ? mergeSafeMemory({ ...item, minimized: true }, action) : item
  ));
  const spaces = state.spaces.map((space) => (
    space.spaceId === target.spaceId && space.activeWindowId === windowId
      ? { ...space, activeWindowId: topVisibleWindowId(windows, target.spaceId) }
      : space
  ));
  return rebuildState(state, windows, spaces);
}

function reduceGeometry(state, action, dimension) {
  const windowId = safeKey(action.windowId ?? action.window_id);
  const target = state.windows.find((item) => item.windowId === windowId);
  if (!target) return state;
  const requested = dimension === "position"
    ? { position: action.position, size: target.size }
    : { position: target.position, size: action.size };
  const geometry = clampWorkspaceWindowGeometry(requested, state.bounds);
  const windows = state.windows.map((item) => (
    item.windowId === windowId
      ? mergeSafeMemory({ ...item, ...geometry, zoomed: false }, action)
      : item
  ));
  return rebuildState(state, windows);
}

function reduceToggleZoom(state, action) {
  const windowId = safeKey(action.windowId ?? action.window_id);
  const target = state.windows.find((item) => item.windowId === windowId);
  if (!target) return state;
  const windows = state.windows.map((item) => (
    item.windowId === windowId
      ? mergeSafeMemory({
        ...item,
        minimized: false,
        zoomed: !item.zoomed,
        zIndex: nextZIndex(state),
      }, action)
      : item
  ));
  const spaces = spaceWithActiveWindow(state.spaces, target.spaceId, windowId);
  return rebuildState(state, windows, spaces, target.spaceId);
}

function reduceSwitchSpace(state, action) {
  const requested = safeKey(action.spaceId ?? action.space_id);
  if (!requested) return state;
  const spaces = ensureSpace(state.spaces, requested);
  if (!spaces.some((space) => space.spaceId === requested)) return state;
  return rebuildState(state, state.windows, spaces, requested);
}

export function workspaceWindowManagerReducer(rawState, rawAction = {}) {
  const action = isRecord(rawAction) ? rawAction : {};
  const stateSeed = isRecord(rawState) ? rawState : {};
  const state = createWorkspaceWindowManagerState({
    ...stateSeed,
    bounds: owns(action, "bounds") ? action.bounds : stateSeed.bounds,
  });
  switch (action.type) {
    case "open":
      return reduceOpen(state, action);
    case "focus":
      return focusWindow(state, safeKey(action.windowId ?? action.window_id), action);
    case "close":
      return reduceClose(state, action);
    case "minimize":
      return reduceMinimize(state, action);
    case "restore":
      return focusWindow(state, safeKey(action.windowId ?? action.window_id), action);
    case "move":
      return reduceGeometry(state, action, "position");
    case "resize":
      return reduceGeometry(state, action, "size");
    case "toggleZoom":
      return reduceToggleZoom(state, action);
    case "switchSpace":
      return reduceSwitchSpace(state, action);
    default:
      return state;
  }
}

export function serializeWorkspaceWindowManagerState(rawState) {
  const state = createWorkspaceWindowManagerState(rawState);
  return {
    version: WORKSPACE_WINDOW_MANAGER_CONTRACT_VERSION,
    bounds: {
      width: state.bounds.width,
      height: state.bounds.height,
    },
    activeSpaceId: state.activeSpaceId,
    spaces: state.spaces.map((space) => ({
      spaceId: space.spaceId,
      windowIds: [...space.windowIds],
      activeWindowId: space.activeWindowId,
    })),
    windows: state.windows.map((item) => ({
      appId: item.appId,
      windowId: item.windowId,
      spaceId: item.spaceId,
      position: { x: item.position.x, y: item.position.y },
      size: { width: item.size.width, height: item.size.height },
      zIndex: item.zIndex,
      minimized: item.minimized,
      zoomed: item.zoomed,
      projectContext: item.projectContext
        ? {
          organizationId: item.projectContext.organizationId,
          projectId: item.projectContext.projectId,
        }
        : null,
      selection: item.selection
        ? {
          ...(item.selection.kind ? { kind: item.selection.kind } : {}),
          ...(item.selection.id ? { id: item.selection.id } : {}),
          ...(item.selection.ids ? { ids: [...item.selection.ids] } : {}),
          ...(item.selection.tabId ? { tabId: item.selection.tabId } : {}),
          ...(item.selection.viewId ? { viewId: item.selection.viewId } : {}),
        }
        : null,
      scroll: { top: item.scroll.top, left: item.scroll.left },
    })),
  };
}

export function deserializeWorkspaceWindowManagerState(serialized) {
  if (typeof serialized !== "string") return createWorkspaceWindowManagerState(serialized);
  if (!serialized || serialized.length > 1_000_000) return createWorkspaceWindowManagerState();
  try {
    return createWorkspaceWindowManagerState(JSON.parse(serialized));
  } catch {
    return createWorkspaceWindowManagerState();
  }
}
