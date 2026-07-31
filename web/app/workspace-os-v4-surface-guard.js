/* ContentEngine Desktop v4 · keeps local window chrome with the active surface. */

const LOCAL_CHROME = [
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

let queued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function isVisible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function currentPage() {
  return qa(".workspace-main .page-wrap, .workspace-main .learning-page, #main-content > .page-wrap, #main-content > .learning-page")
    .filter(isVisible).at(-1) || q(".workspace-main") || q("#main-content");
}

function preserveLocalChrome() {
  const page = currentPage();
  if (!page) return;
  const hasDedicatedSurface = page.matches?.(DEDICATED_SURFACES) || Boolean(q(DEDICATED_SURFACES, page));
  page.classList.toggle("ce-v4-native-surface", !hasDedicatedSurface);
  if (!page.classList.contains("ce-v4-single-surface")) return;
  [...page.children].forEach((child) => {
    if (child.matches?.(LOCAL_CHROME) || q(LOCAL_CHROME, child)) {
      child.dataset.ceV4SurfaceHost = "true";
    }
  });
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    preserveLocalChrome();
  });
}

new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineDesktopV4SurfaceGuard = Object.freeze({ schedule });
