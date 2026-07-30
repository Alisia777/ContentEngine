/* Final perception fixes for Desktop OS. */

let syncQueued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function compact(value, limit = 78) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function visiblePanelTitle(panel, fallback) {
  return compact(q("legend, h1, h2, h3, .eyebrow, strong", panel)?.textContent || fallback, 78);
}

function syncReviewTitle() {
  syncQueued = false;
  const page = q(".content-review-page.review-desktop-os");
  if (!page) {
    document.body.classList.remove("workspace-desktop-os-polish");
    return;
  }
  document.body.classList.add("workspace-desktop-os-polish");
  const target = q("[data-review-os-current-title]", page);
  if (!target) return;
  const mode = String(page.dataset.reviewOsMode || "new");
  if (mode === "history") {
    target.textContent = "История проверок";
    return;
  }
  const space = q(`[data-review-os-space="${mode}"]`, page);
  const panel = q("[data-ce-os-panel].is-active", space);
  target.textContent = visiblePanelTitle(panel, mode === "result" ? "Текущая проверка" : "Новая проверка");
}

function queueSync() {
  if (syncQueued) return;
  syncQueued = true;
  window.requestAnimationFrame(syncReviewTitle);
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target?.closest("[data-review-os-mode], [data-ce-os-panel-index], [data-review-form-prev], [data-review-form-next], [data-review-result-prev], [data-review-result-next]")) return;
  window.setTimeout(queueSync, 0);
});

const observer = new MutationObserver(queueSync);
observer.observe(document.querySelector("#app") || document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["class", "data-review-os-mode"] });
window.addEventListener("hashchange", queueSync, { passive: true });
queueSync();
