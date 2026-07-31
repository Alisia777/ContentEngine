/*
 * Publishing Desktop OS.
 * Re-composes native placement cards into one-publication/one-workspace flows.
 * Existing forms, tracking links and submit handlers remain authoritative.
 */

const PUBLISHING_ROUTES = new Set(["/workspace/placement", "/workspace/placements"]);
const STATE_KEY = "contentengine.publishing-os.v3";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const ICONS = Object.freeze({
  publish: '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6h14v-6"/>',
  brief: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  proof: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 13h6"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
});

const STEP_META = Object.freeze([
  ["brief", "Задание", "brief"],
  ["tracking", "Ссылка", "link"],
  ["compliance", "Проверка", "check"],
  ["publish", "Подтверждение", "proof"],
]);

const runtime = {
  queued: false,
  page: null,
  shell: null,
  cards: [],
  activeId: "",
  step: 0,
  filter: "active",
  memory: readMemory(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.publish}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
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

function readMemory() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STATE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function remember(patch) {
  runtime.memory = { ...runtime.memory, ...patch };
  try { window.localStorage.setItem(STATE_KEY, JSON.stringify(runtime.memory)); } catch { /* optional */ }
}

function cardId(card, index = 0) {
  return String(card?.dataset?.placementId || `placement-${index}`);
}

function cardFacts(card) {
  const title = compact(q(".placement-top h3, h3, strong", card)?.textContent || "Публикация", 130);
  const platform = compact(q(".placement-top .eyebrow, .eyebrow", card)?.textContent || "Площадка", 60);
  const status = compact(q(".placement-top .badge, .badge", card)?.textContent || "", 60);
  const complete = !q(".placement-form", card)
    || /опубликован|подтвержден|завершен|готово/iu.test(`${status} ${card.textContent}`);
  const issue = /блок|ошиб|отклон|нельзя|нет решения/iu.test(`${status} ${card.textContent}`);
  return { title, platform, status, complete, issue };
}

function createTopbar() {
  return elementFrom(`
    <header class="publishing-os-topbar">
      <div class="publishing-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="publishing-os-title"><small>ContentEngine · Publishing</small><strong data-publishing-current-title>Рабочий стол публикации</strong></div>
      <div class="publishing-os-filters" role="group" aria-label="Фильтр публикаций">
        <button type="button" data-publishing-filter="active">Сейчас</button>
        <button type="button" data-publishing-filter="completed">Готовые</button>
        <button type="button" data-publishing-filter="all">Все</button>
      </div>
      <button class="publishing-os-mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 18)}</button>
    </header>`);
}

function createShell() {
  return elementFrom(`
    <section class="publishing-os-shell" aria-label="Публикации">
      <aside class="publishing-os-sidebar">
        <header><small>ПУБЛИКАЦИИ</small><strong>Очередь площадок</strong><span data-publishing-count></span></header>
        <div class="publishing-os-list" role="listbox" aria-label="Список публикаций"></div>
      </aside>
      <main class="publishing-os-main">
        <section class="publishing-os-preview" aria-label="Предпросмотр публикации">
          <div class="publishing-os-device">
            <header><span data-publishing-preview-platform>Площадка</span><i></i></header>
            <div class="publishing-os-device-stage">
              <span>${icon("publish", 34)}</span>
              <strong data-publishing-preview-title>Публикация</strong>
              <small data-publishing-preview-status>Подготовка</small>
            </div>
            <footer><i></i><i></i><i></i></footer>
          </div>
          <div class="publishing-os-preview-copy"><small>ПРЕДПРОСМОТР</small><strong>Один пост — один маршрут</strong><p>Сначала площадка и ссылка, затем правовая проверка и только после этого подтверждение публикации.</p></div>
        </section>
        <section class="publishing-os-workspace">
          <div class="publishing-os-panels"></div>
          <div class="publishing-os-empty" hidden><strong>В этом фильтре ничего нет</strong><p>Переключите «Сейчас / Готовые / Все».</p></div>
        </section>
      </main>
    </section>`);
}

function groupingFor(node) {
  if (node.matches(".placement-top")) return "brief";
  if (node.matches(".tracking-link-form, .callout")) return "tracking";
  if (node.matches(".placement-form")) return "publish";
  const text = String(node.textContent || "");
  if (node.matches(".checklist") || /реклам|провер|блокер|историю проверки/iu.test(text)) return "compliance";
  if (/публикация подтверждена|ссылка сохранена|закрыта/iu.test(text)) return "publish";
  return "compliance";
}

function validatePanel(panel) {
  const controls = qa("input, select, textarea", panel).filter((control) => !control.disabled && !control.hidden);
  const invalid = controls.find((control) => typeof control.checkValidity === "function" && !control.checkValidity());
  if (!invalid) return true;
  invalid.reportValidity?.();
  invalid.focus?.({ preventScroll: true });
  return false;
}

function animatePanel(outgoing, incoming, direction) {
  if (!incoming || REDUCED_MOTION.matches || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 30}px,0,0) scale(.988)` },
  ], { duration: 170, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 44}px,0,0) scale(.978)`, filter: "blur(5px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 490, easing: SPRING });
}

function setCardStep(card, index, { focus = false, validate = false } = {}) {
  const panels = qa(":scope > .publishing-os-step-panels > [data-publishing-step]", card);
  if (!panels.length) return;
  const currentIndex = Math.max(0, panels.findIndex((panel) => panel.classList.contains("is-active")));
  if (validate && index > currentIndex && !validatePanel(panels[currentIndex])) return;
  const next = Math.max(0, Math.min(panels.length - 1, Number(index) || 0));
  const outgoing = panels[currentIndex];
  const incoming = panels[next];
  panels.forEach((panel, panelIndex) => {
    const active = panelIndex === next;
    panel.classList.toggle("is-active", active);
    panel.hidden = !active;
    panel.inert = !active;
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });
  qa("[data-publishing-step-index]", card).forEach((button) => {
    const active = Number(button.dataset.publishingStepIndex) === next;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "step" : "false");
  });
  q("[data-publishing-step-position]", card).textContent = `${next + 1} / ${panels.length}`;
  q("[data-publishing-step-prev]", card).disabled = next <= 0;
  q("[data-publishing-step-next]", card).hidden = next >= panels.length - 1;
  card.style.setProperty("--publishing-step-progress", `${((next + 1) / panels.length) * 100}%`);
  runtime.step = next;
  remember({ step: next, activeId: cardId(card) });
  if (outgoing !== incoming) animatePanel(outgoing, incoming, next >= currentIndex ? 1 : -1);
  if (focus) q("input, select, textarea, button, a", incoming)?.focus({ preventScroll: true });
}

function setupCard(card, index) {
  if (card.dataset.publishingOsReady === "true") return;
  card.dataset.publishingOsReady = "true";
  card.classList.add("publishing-os-card");
  const direct = [...card.children];
  const groups = new Map(STEP_META.map(([key]) => [key, []]));
  direct.forEach((node) => groups.get(groupingFor(node))?.push(node));

  const nav = elementFrom('<nav class="publishing-os-step-dock" aria-label="Этапы публикации"></nav>');
  const panels = elementFrom('<div class="publishing-os-step-panels"></div>');
  const footer = elementFrom(`
    <footer class="publishing-os-footer">
      <button type="button" data-publishing-step-prev>${icon("left", 18)}<span>Назад</span></button>
      <div><small>Этап</small><strong data-publishing-step-position>1 / ${STEP_META.length}</strong></div>
      <button type="button" data-publishing-step-next><span>Далее</span>${icon("right", 18)}</button>
    </footer>`);

  STEP_META.forEach(([key, label, iconName], stepIndex) => {
    const button = elementFrom(`<button type="button" data-publishing-step-index="${stepIndex}" aria-label="${escapeMarkup(label)}"><span>${icon(iconName, 17)}</span><small>${escapeMarkup(label)}</small></button>`);
    nav.append(button);
    const panel = document.createElement("section");
    panel.className = "publishing-os-step-panel";
    panel.dataset.publishingStep = key;
    (groups.get(key) || []).forEach((node) => panel.append(node));
    if (!panel.children.length) {
      panel.innerHTML = `<div class="publishing-os-step-empty"><strong>${escapeMarkup(label)}</strong><p>Для этой публикации отдельное действие не требуется.</p></div>`;
    }
    panels.append(panel);
  });

  card.append(nav, panels, footer);
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-publishing-step-index]") : null;
    if (button) setCardStep(card, Number(button.dataset.publishingStepIndex), { focus: true, validate: true });
  });
  footer.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("[data-publishing-step-prev]")) setCardStep(card, runtime.step - 1, { focus: true });
    if (event.target.closest("[data-publishing-step-next]")) setCardStep(card, runtime.step + 1, { focus: true, validate: true });
  });
  setCardStep(card, Math.min(Number(runtime.memory.step) || 0, STEP_META.length - 1));
}

function buildSidebar() {
  const list = q(".publishing-os-list", runtime.shell);
  if (!list) return;
  const cards = runtime.cards.filter((card) => !card.hidden);
  list.innerHTML = cards.map((card, index) => {
    const facts = cardFacts(card);
    const id = cardId(card, index);
    return `
      <button type="button" class="publishing-os-list-item${id === runtime.activeId ? " is-active" : ""}" data-publishing-card-id="${escapeMarkup(id)}" role="option" aria-selected="${id === runtime.activeId ? "true" : "false"}">
        <span>${icon("publish", 18)}</span>
        <span><strong>${escapeMarkup(facts.title)}</strong><small>${escapeMarkup(facts.platform)} · ${escapeMarkup(facts.status || (facts.complete ? "Готово" : "В работе"))}</small></span>
        <i data-tone="${facts.issue ? "danger" : facts.complete ? "success" : "warning"}"></i>
      </button>`;
  }).join("");
  q("[data-publishing-count]", runtime.shell).textContent = `${cards.length} из ${runtime.cards.length}`;
}

function updatePreview(card) {
  const facts = cardFacts(card);
  q("[data-publishing-preview-platform]", runtime.shell).textContent = facts.platform;
  q("[data-publishing-preview-title]", runtime.shell).textContent = facts.title;
  q("[data-publishing-preview-status]", runtime.shell).textContent = facts.status || (facts.complete ? "Опубликовано" : "Подготовка");
  q("[data-publishing-current-title]", runtime.page).textContent = facts.title;
  q(".publishing-os-device", runtime.shell)?.setAttribute("data-tone", facts.issue ? "danger" : facts.complete ? "success" : "active");
}

function selectCard(id, { focus = false } = {}) {
  const card = runtime.cards.find((item, index) => cardId(item, index) === String(id))
    || runtime.cards.find((item) => !item.hidden);
  if (!card || card.hidden) return;
  runtime.activeId = cardId(card, runtime.cards.indexOf(card));
  runtime.cards.forEach((item) => {
    const active = item === card;
    item.classList.toggle("is-selected", active);
    item.hidden = !active;
    item.inert = !active;
    item.setAttribute("aria-hidden", active ? "false" : "true");
  });
  remember({ activeId: runtime.activeId });
  buildSidebar();
  updatePreview(card);
  setCardStep(card, Math.min(Number(runtime.memory.step) || 0, STEP_META.length - 1));
  if (focus) q("button, input, select, textarea, a", card)?.focus({ preventScroll: true });
}

function applyFilter(filter) {
  const resolved = ["active", "completed", "all"].includes(filter) ? filter : "active";
  runtime.filter = resolved;
  runtime.cards.forEach((card) => {
    const facts = cardFacts(card);
    card.dataset.publishingFilterHidden = resolved === "all" || (resolved === "active" ? !facts.complete : facts.complete) ? "false" : "true";
  });
  const candidates = runtime.cards.filter((card) => card.dataset.publishingFilterHidden !== "true");
  runtime.cards.forEach((card) => { card.hidden = true; card.inert = true; });
  qa("[data-publishing-filter]", runtime.page).forEach((button) => button.classList.toggle("is-active", button.dataset.publishingFilter === resolved));
  remember({ filter: resolved });
  const selected = candidates.find((card, index) => cardId(card, index) === runtime.activeId) || candidates[0];
  q(".publishing-os-empty", runtime.shell).hidden = Boolean(selected);
  if (selected) {
    selected.dataset.publishingFilterHidden = "false";
    selectCard(cardId(selected, runtime.cards.indexOf(selected)));
  } else {
    runtime.activeId = "";
    buildSidebar();
  }
}

function mountPublishing() {
  if (!PUBLISHING_ROUTES.has(routePath())) {
    document.body.classList.remove("contentengine-publishing-os-open");
    runtime.page = null;
    runtime.shell = null;
    runtime.cards = [];
    return;
  }
  const list = q(".placement-list");
  const page = list?.closest?.(".page-wrap");
  const cards = qa(":scope > .placement-card", list);
  if (!page || !cards.length) return;
  document.body.classList.add("contentengine-publishing-os-open");
  runtime.page = page;
  if (page.dataset.publishingOsReady === "true") return;
  page.dataset.publishingOsReady = "true";
  page.classList.add("publishing-os-page");
  const topbar = createTopbar();
  const shell = createShell();
  runtime.shell = shell;
  const anchor = q(":scope > .page-header", page) || page.firstElementChild;
  anchor?.after?.(topbar, shell);
  const panelHost = q(".publishing-os-panels", shell);
  runtime.cards = cards;
  cards.forEach((card, index) => {
    setupCard(card, index);
    panelHost.append(card);
  });
  list.remove();
  const originalAlerts = qa(":scope > .alert", page);
  originalAlerts.forEach((alert) => {
    alert.classList.add("publishing-os-global-alert");
    q(".publishing-os-preview-copy", shell)?.append(alert);
  });

  topbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-publishing-filter]") : null;
    if (button) applyFilter(button.dataset.publishingFilter);
  });
  q(".publishing-os-list", shell).addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-publishing-card-id]") : null;
    if (button) selectCard(button.dataset.publishingCardId, { focus: true });
  });
  runtime.activeId = String(runtime.memory.activeId || cardId(cards[0], 0));
  applyFilter(String(runtime.memory.filter || "active"));
}

function handleKeydown(event) {
  if (!PUBLISHING_ROUTES.has(routePath()) || !runtime.page) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  if (event.altKey && !event.shiftKey && event.key === "ArrowLeft") {
    event.preventDefault();
    const card = runtime.cards.find((item) => item.classList.contains("is-selected"));
    if (card) setCardStep(card, runtime.step - 1, { focus: true });
  }
  if (event.altKey && !event.shiftKey && event.key === "ArrowRight") {
    event.preventDefault();
    const card = runtime.cards.find((item) => item.classList.contains("is-selected"));
    if (card) setCardStep(card, runtime.step + 1, { focus: true, validate: true });
  }
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mountPublishing();
  });
}

new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleKeydown);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
