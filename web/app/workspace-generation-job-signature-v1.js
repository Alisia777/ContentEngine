/*
 * Adds a hidden, idempotent job signature to native generation rows.
 *
 * Native archive copy currently uses the compact Russian token "5 сек" while
 * the mini-AI matcher deliberately expects an unambiguous duration phrase.
 * This adapter does not read form values or call any API; it only normalizes
 * already-rendered durable job metadata in the DOM.
 */

const JOB_SELECTOR = "[data-generation-job-id]";
const SIGNATURE_ATTR = "data-mini-ai-job-signature";
const DURATION_PATTERN = /(?:^|[·|\s])(\d{1,2})\s*сек(?:\.|унд(?:а|ы|ов)?)?\b/iu;
let queued = false;

function normalizeJob(element) {
  if (!(element instanceof HTMLElement) || element.hasAttribute(SIGNATURE_ATTR)) return;
  const jobId = String(element.dataset.generationJobId || "").trim();
  if (!jobId) return;
  const match = String(element.textContent || "").match(DURATION_PATTERN);
  element.setAttribute(SIGNATURE_ATTR, "true");
  if (!match) return;
  const marker = document.createElement("span");
  marker.hidden = true;
  marker.dataset.miniAiDurationMarker = match[1];
  marker.textContent = ` ${Number(match[1])} секунд `;
  element.append(marker);
}

function scan(root = document) {
  if (root instanceof Element && root.matches(JOB_SELECTOR)) normalizeJob(root);
  root.querySelectorAll?.(JOB_SELECTOR).forEach(normalizeJob);
}

function schedule() {
  if (queued) return;
  queued = true;
  window.requestAnimationFrame(() => {
    queued = false;
    scan();
  });
}

const observer = new MutationObserver((records) => {
  if (records.some((record) => [...record.addedNodes].some((item) =>
    item instanceof Element
    && (item.matches(JOB_SELECTOR) || item.querySelector?.(JOB_SELECTOR))
  ))) schedule();
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    scan();
    observer.observe(document.body, { childList: true, subtree: true });
  }, { once: true });
} else {
  scan();
  observer.observe(document.body, { childList: true, subtree: true });
}
