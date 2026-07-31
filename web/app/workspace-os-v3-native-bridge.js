/*
 * ContentEngine OS v3 native bridge.
 * Captures small native controls before route adapters re-compose their parent
 * containers, restores them into the new desktop geometry and repairs derived
 * navigation lists. It never calls APIs or submits forms.
 */

const runtime = {
  queued: false,
  workExtras: [],
  workExtrasCaptured: false,
  publishingSignature: "",
  workSnapshot: null,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function compact(value, limit = 100) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function captureWorkExtras() {
  if (runtime.workExtrasCaptured) return;
  const queue = q(".my-work-queue");
  if (!queue || q(".work-stage-shell")) return;
  const extras = qa(":scope > *", queue).filter((node) => !node.classList.contains("my-work-item"));
  if (!extras.length) return;
  runtime.workExtras = extras;
  runtime.workExtrasCaptured = true;
  extras.forEach((node) => node.remove());
}

function restoreWorkExtras() {
  if (!runtime.workExtras.length) return;
  const lane = q("[data-work-stage-items='next']");
  if (!lane || q(".work-stage-native-extras", lane)) return;
  const wrapper = document.createElement("footer");
  wrapper.className = "work-stage-native-extras";
  runtime.workExtras.forEach((node) => wrapper.append(node));
  lane.append(wrapper);
  runtime.workExtras = [];
}

function publishingFacts(card) {
  const title = compact(q(".placement-top h3, h3, strong", card)?.textContent || "Публикация", 110);
  const platform = compact(q(".placement-top .eyebrow, .eyebrow", card)?.textContent || "Площадка", 46);
  const status = compact(q(".placement-top .badge, .badge", card)?.textContent || "", 58);
  const text = `${status} ${card.textContent}`;
  const complete = !q(".placement-form", card) || /опубликован|подтвержден|завершен|готово/iu.test(text);
  const issue = /блок|ошиб|отклон|нельзя|нет решения/iu.test(text);
  return { title, platform, status, complete, issue };
}

function repairPublishingSidebar() {
  const shell = q(".publishing-os-shell");
  const list = q(".publishing-os-list", shell);
  if (!shell || !list) return;
  const allCards = qa(".publishing-os-panels > .placement-card", shell);
  const cards = allCards.filter((card) => card.dataset.publishingFilterHidden !== "true");
  const active = allCards.find((card) => card.classList.contains("is-selected"));
  const activeId = String(active?.dataset.placementId || "");
  const signature = JSON.stringify({
    activeId,
    cards: cards.map((card, index) => String(card.dataset.placementId || `placement-${index}`)),
  });
  if (signature === runtime.publishingSignature && list.children.length === cards.length) return;
  runtime.publishingSignature = signature;
  list.innerHTML = cards.map((card, index) => {
    const id = String(card.dataset.placementId || `placement-${index}`);
    const facts = publishingFacts(card);
    return `
      <button type="button" class="publishing-os-list-item${id === activeId ? " is-active" : ""}" data-publishing-card-id="${escapeMarkup(id)}" role="option" aria-selected="${id === activeId ? "true" : "false"}">
        <span aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6h14v-6"/></svg></span>
        <span><strong>${escapeMarkup(facts.title)}</strong><small>${escapeMarkup(facts.platform)} · ${escapeMarkup(facts.status || (facts.complete ? "Готово" : "В работе"))}</small></span>
        <i data-tone="${facts.issue ? "danger" : facts.complete ? "success" : "warning"}"></i>
      </button>`;
  }).join("");
  const count = q("[data-publishing-count]", shell);
  if (count) count.textContent = `${cards.length} из ${allCards.length}`;
}

function dockBadge(route, value, tone = "active") {
  const item = q(`.ce-mac-dock__item[data-ce-dock-route='${route}']`);
  if (!item) return;
  let badge = q(".os-v3-route-badge", item);
  const number = Math.max(0, Number(value) || 0);
  if (!number) {
    badge?.remove();
    return;
  }
  if (!badge) {
    badge = document.createElement("b");
    badge.className = "os-v3-route-badge";
    item.append(badge);
  }
  badge.dataset.tone = tone;
  badge.textContent = number > 99 ? "99+" : String(number);
  badge.setAttribute("aria-label", `${number} требуют внимания`);
}

function syncDockSnapshot() {
  const snapshot = runtime.workSnapshot;
  if (!snapshot) return;
  dockBadge("/workspace/work", Number(snapshot.now || 0) + Number(snapshot.blockers || 0), snapshot.blockers ? "danger" : "active");
  dockBadge("/workspace/tasks", snapshot.now || 0, snapshot.blockers ? "danger" : "active");
}

function mount() {
  captureWorkExtras();
  restoreWorkExtras();
  repairPublishingSidebar();
  syncDockSnapshot();
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    window.requestAnimationFrame(() => {
      runtime.queued = false;
      mount();
    });
  });
}

window.addEventListener("contentengine:os-v3-work-snapshot", (event) => {
  runtime.workSnapshot = event.detail || null;
  scheduleMount();
});
new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", () => {
  runtime.workExtrasCaptured = false;
  runtime.workExtras = [];
  runtime.publishingSignature = "";
  scheduleMount();
});
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
