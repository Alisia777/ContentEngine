/* Visible Zen Mode control for ContentEngine OS v3.2. */

let queued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function topbar() {
  return q(
    ".review-os-topbar, .generation-os-topbar, .media-finder-topbar, "
      + ".publishing-os-topbar, .work-stage-topbar, .tasks-desk-topbar, "
      + ".results-os-topbar, .payout-ledger-topbar, .academy-os-topbar",
  );
}

function expandIcon() {
  return '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/><path d="m3 8 6-6M21 8l-6-6M3 16l6 6M21 16l-6 6"/></svg>';
}

function ensureZenControl() {
  queued = false;
  const bar = topbar();
  if (!bar || q("[data-os-clean-zen]", bar)) return;
  const reference = q("[data-ce-open-mission], .review-os-mission, .generation-os-mission, .media-finder-mission, .results-ledger-mission", bar);
  const button = document.createElement("button");
  button.type = "button";
  button.className = reference?.className || "review-os-mission";
  button.dataset.osCleanZen = "true";
  button.setAttribute("aria-label", "Фокус: развернуть рабочее пространство");
  button.title = "Фокус · F";
  button.innerHTML = expandIcon();
  if (reference) reference.before(button);
  else bar.append(button);
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(ensureZenControl);
}

new MutationObserver(schedule).observe(document.querySelector("#app") || document.body, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("pageshow", schedule, { passive: true });
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();
