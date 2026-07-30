/*
 * Workspace state capsules
 * Restores UI context for every workspace/learning route without persisting
 * form values, secrets or files. State is scoped to the current browser tab.
 */

const CAPSULE_STORAGE_KEY = "contentengine.workspace-capsules.v1";
const CAPSULE_ROUTE_PREFIXES = ["/workspace/", "/learn"];
const CAPSULE_MAX_AGE_MS = 12 * 60 * 60 * 1000;
const CAPSULE_SCROLL_SELECTOR = [
  ".table-wrap",
  ".data-table-wrap",
  ".workspace-board",
  ".generation-archive",
  ".notification-list",
  "[data-workspace-scroll-memory]",
].join(", ");
const CAPSULE_TAB_SELECTOR = [
  '[role="tab"]',
  "[data-workspace-capsule-tab]",
].join(", ");
const CAPSULE_EXCLUDED_ROOT = [
  ".workspace-overview",
  ".workspace-context-panel",
  ".workspace-park-dialog",
  ".workspace-focus-chrome",
  ".notification-drawer",
].join(", ");

let capsuleRestoreQueued = false;
let capsuleSaveTimer = 0;
let capsuleCaptureTimer = 0;
let capsuleRestoring = false;
let capsuleLastRoute = capsuleRoute();
let capsuleMemory = readCapsuleMemory();

function capsuleStore() {
  try { return window.sessionStorage; } catch { return null; }
}

function capsuleRoute() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function isCapsuleRoute(route) {
  return CAPSULE_ROUTE_PREFIXES.some((prefix) => String(route || "").startsWith(prefix));
}

function capsuleRoot() {
  return document.querySelector("#workspace-content")
    || document.querySelector(".learning-page")
    || document.querySelector("#main-content");
}

function readCapsuleMemory() {
  try {
    const parsed = JSON.parse(capsuleStore()?.getItem(CAPSULE_STORAGE_KEY) || "{}");
    if (!parsed || typeof parsed !== "object") return {};
    const now = Date.now();
    return Object.fromEntries(Object.entries(parsed).filter(([, value]) => (
      value && typeof value === "object" && now - Number(value.savedAt || 0) <= CAPSULE_MAX_AGE_MS
    )));
  } catch {
    return {};
  }
}

function persistCapsuleMemory() {
  try { capsuleStore()?.setItem(CAPSULE_STORAGE_KEY, JSON.stringify(capsuleMemory)); } catch { /* optional enhancement */ }
}

function scheduleCapsulePersist() {
  window.clearTimeout(capsuleSaveTimer);
  capsuleSaveTimer = window.setTimeout(persistCapsuleMemory, 180);
}

function scheduleCapsuleCapture(delay = 220) {
  window.clearTimeout(capsuleCaptureTimer);
  capsuleCaptureTimer = window.setTimeout(() => captureCapsule(capsuleRoute()), delay);
}

function capsuleStableData(element) {
  if (!(element instanceof Element)) return "";
  const candidates = [
    "workspaceItemKey",
    "taskId",
    "generationJobId",
    "reviewId",
    "mediaId",
    "placementId",
    "payoutId",
    "section",
    "tab",
    "view",
  ];
  for (const key of candidates) {
    const value = String(element.dataset?.[key] || "").trim();
    if (value) return `${key}:${value}`;
  }
  return "";
}

function capsuleLocator(element, root = capsuleRoot()) {
  if (!(element instanceof Element) || !root?.contains(element)) return "";
  if (element.id) return `id:${element.id}`;
  const stable = capsuleStableData(element);
  if (stable) return `data:${stable}`;
  const name = String(element.getAttribute("name") || "").trim();
  if (name) return `name:${element.tagName.toLowerCase()}:${name}`;
  const role = String(element.getAttribute("role") || "").trim();
  const type = role ? `[role="${CSS.escape(role)}"]` : element.tagName.toLowerCase();
  const peers = [...root.querySelectorAll(type)].filter((item) => !item.closest(CAPSULE_EXCLUDED_ROOT));
  const index = peers.indexOf(element);
  return index >= 0 ? `index:${type}:${index}` : "";
}

function elementFromCapsuleLocator(locator, root = capsuleRoot()) {
  if (!locator || !root) return null;
  if (locator.startsWith("id:")) return document.getElementById(locator.slice(3));
  if (locator.startsWith("data:")) {
    const [key, ...parts] = locator.slice(5).split(":");
    const value = parts.join(":");
    return [...root.querySelectorAll(`[data-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}]`)]
      .find((element) => String(element.dataset?.[key] || "") === value) || null;
  }
  if (locator.startsWith("name:")) {
    const [, tag, ...parts] = locator.split(":");
    return root.querySelector(`${tag}[name="${CSS.escape(parts.join(":"))}"]`);
  }
  if (locator.startsWith("index:")) {
    const payload = locator.slice(6);
    const separator = payload.lastIndexOf(":");
    const selector = payload.slice(0, separator);
    const index = Number(payload.slice(separator + 1));
    if (!selector || !Number.isInteger(index)) return null;
    return [...root.querySelectorAll(selector)].filter((item) => !item.closest(CAPSULE_EXCLUDED_ROOT))[index] || null;
  }
  return null;
}

function selectedTab(root) {
  return [...root.querySelectorAll(CAPSULE_TAB_SELECTOR)]
    .find((tab) => !tab.closest(CAPSULE_EXCLUDED_ROOT) && (
      tab.getAttribute("aria-selected") === "true"
      || tab.getAttribute("aria-pressed") === "true"
      || tab.classList.contains("is-active")
      || tab.classList.contains("active")
    ));
}

function captureCapsule(route = capsuleRoute()) {
  if (capsuleRestoring || !isCapsuleRoute(route)) return;
  const root = capsuleRoot();
  if (!root) return;

  const details = [...root.querySelectorAll("details")]
    .filter((item) => !item.closest(CAPSULE_EXCLUDED_ROOT))
    .map((item) => ({ locator: capsuleLocator(item, root), open: item.open }))
    .filter((item) => item.locator);

  const scrolls = [...root.querySelectorAll(CAPSULE_SCROLL_SELECTOR)]
    .filter((item) => !item.closest(CAPSULE_EXCLUDED_ROOT))
    .map((item) => ({
      locator: capsuleLocator(item, root),
      top: Math.max(0, Math.round(item.scrollTop || 0)),
      left: Math.max(0, Math.round(item.scrollLeft || 0)),
    }))
    .filter((item) => item.locator && (item.top > 0 || item.left > 0));

  const videos = [...root.querySelectorAll("video")]
    .filter((item) => !item.closest(CAPSULE_EXCLUDED_ROOT))
    .map((item) => ({
      locator: capsuleLocator(item, root),
      currentTime: Number.isFinite(item.currentTime) ? Math.max(0, Math.round(item.currentTime * 10) / 10) : 0,
      volume: Number.isFinite(item.volume) ? Math.max(0, Math.min(1, item.volume)) : 1,
      muted: Boolean(item.muted),
    }))
    .filter((item) => item.locator && item.currentTime > 0);

  const tab = selectedTab(root);
  const active = document.activeElement instanceof Element && root.contains(document.activeElement)
    ? capsuleLocator(document.activeElement, root)
    : "";

  capsuleMemory[route] = {
    savedAt: Date.now(),
    details,
    scrolls,
    videos,
    tab: capsuleLocator(tab, root),
    active,
  };
  scheduleCapsulePersist();
  updateCapsuleIndicator(route);
}

function dispatchCapsuleRestored(route, restored) {
  document.dispatchEvent(new CustomEvent("contentengine:capsule-restored", {
    detail: { route, restored },
  }));
}

function restoreVideo(video, saved) {
  if (!(video instanceof HTMLVideoElement)) return;
  video.volume = Number.isFinite(saved.volume) ? saved.volume : video.volume;
  video.muted = Boolean(saved.muted);
  const setTime = () => {
    if (Number.isFinite(saved.currentTime) && saved.currentTime > 0 && video.duration) {
      video.currentTime = Math.min(saved.currentTime, Math.max(0, video.duration - 0.1));
    }
  };
  if (video.readyState >= 1) setTime();
  else video.addEventListener("loadedmetadata", setTime, { once: true });
}

function restoreCapsule(route = capsuleRoute()) {
  if (!isCapsuleRoute(route)) return;
  const saved = capsuleMemory[route];
  const root = capsuleRoot();
  if (!saved || !root || Date.now() - Number(saved.savedAt || 0) > CAPSULE_MAX_AGE_MS) {
    updateCapsuleIndicator(route);
    return;
  }

  capsuleRestoring = true;
  let restored = 0;

  for (const item of saved.details || []) {
    const details = elementFromCapsuleLocator(item.locator, root);
    if (details instanceof HTMLDetailsElement && details.open !== Boolean(item.open)) {
      details.open = Boolean(item.open);
      restored += 1;
    }
  }

  const tab = elementFromCapsuleLocator(saved.tab, root);
  if (
    tab instanceof HTMLElement
    && !tab.closest(CAPSULE_EXCLUDED_ROOT)
    && !tab.matches('[aria-selected="true"], [aria-pressed="true"], .is-active, .active')
    && tab.getAttribute("aria-disabled") !== "true"
    && !tab.hasAttribute("disabled")
  ) {
    tab.click();
    restored += 1;
  }

  for (const item of saved.scrolls || []) {
    const container = elementFromCapsuleLocator(item.locator, root);
    if (!(container instanceof HTMLElement)) continue;
    container.scrollTo({ top: Number(item.top || 0), left: Number(item.left || 0), behavior: "auto" });
    restored += 1;
  }

  for (const item of saved.videos || []) {
    const video = elementFromCapsuleLocator(item.locator, root);
    if (video instanceof HTMLVideoElement) {
      restoreVideo(video, item);
      restored += 1;
    }
  }

  const active = elementFromCapsuleLocator(saved.active, root);
  if (
    active instanceof HTMLElement
    && !document.querySelector('[aria-modal="true"]')
    && active.getAttribute("aria-hidden") !== "true"
    && !active.hasAttribute("disabled")
  ) active.focus({ preventScroll: true });

  capsuleRestoring = false;
  updateCapsuleIndicator(route);
  dispatchCapsuleRestored(route, restored);
}

function scheduleCapsuleRestore() {
  if (capsuleRestoreQueued) return;
  capsuleRestoreQueued = true;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    capsuleRestoreQueued = false;
    restoreCapsule(capsuleRoute());
  }));
}

function capsuleItemCount(route = capsuleRoute()) {
  const saved = capsuleMemory[route];
  if (!saved) return 0;
  return (saved.details || []).filter((item) => item.open).length
    + (saved.scrolls || []).length
    + (saved.videos || []).length
    + (saved.tab ? 1 : 0);
}

function setCapsuleText(element, text) {
  if (element && element.textContent !== text) element.textContent = text;
}

function updateCapsuleIndicator(route = capsuleRoute()) {
  const copy = document.querySelector(".workspace-deck-current__copy");
  if (!copy) return;
  const count = capsuleItemCount(route);
  let indicator = copy.querySelector(".workspace-capsule-indicator");
  if (!count) {
    indicator?.remove();
    return;
  }
  if (!indicator) {
    indicator = document.createElement("span");
    indicator.className = "workspace-capsule-indicator";
    copy.append(indicator);
  }
  setCapsuleText(indicator, `Контекст сохранён · ${count}`);
}

function handleCapsuleEvent(event) {
  if (capsuleRestoring) return;
  const target = event.target instanceof Element ? event.target : null;
  if (!target || target.closest(CAPSULE_EXCLUDED_ROOT)) return;
  if (
    target.matches("details, summary, video, [role='tab'], [data-workspace-capsule-tab]")
    || target.closest("details, [role='tab'], [data-workspace-capsule-tab]")
  ) {
    const delay = event.type === "timeupdate" ? 700 : 80;
    window.queueMicrotask(() => scheduleCapsuleCapture(delay));
  }
}

function handleCapsuleScroll(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.matches?.(CAPSULE_SCROLL_SELECTOR)) scheduleCapsuleCapture(180);
}

function handleCapsuleHashChange() {
  captureCapsule(capsuleLastRoute);
  capsuleLastRoute = capsuleRoute();
  scheduleCapsuleRestore();
}

const capsuleApp = document.querySelector("#app");
if (capsuleApp) new MutationObserver(() => {
  scheduleCapsuleRestore();
  window.queueMicrotask(() => updateCapsuleIndicator(capsuleRoute()));
}).observe(capsuleApp, { childList: true, subtree: true });

document.addEventListener("toggle", handleCapsuleEvent, true);
document.addEventListener("click", handleCapsuleEvent, true);
document.addEventListener("change", handleCapsuleEvent, true);
document.addEventListener("timeupdate", handleCapsuleEvent, true);
document.addEventListener("scroll", handleCapsuleScroll, true);
window.addEventListener("hashchange", handleCapsuleHashChange, { passive: true });
window.addEventListener("beforeunload", () => {
  captureCapsule(capsuleRoute());
  persistCapsuleMemory();
});
scheduleCapsuleRestore();
