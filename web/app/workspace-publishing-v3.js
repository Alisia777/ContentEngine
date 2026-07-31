/*
 * ContentEngine OS v3 production loop.
 * Re-composes Publishing, Tasks, My Work, Results and Payouts using existing
 * application DOM. Native forms, links and server-driven actions remain the
 * authoritative controls.
 */

const core = window.ContentEngineOSV3;
if (!core) throw new Error("ContentEngineOSV3 core must load before production loop");

const {
  q, qa, elementFrom, icon, compact, escapeMarkup, routePath, remember,
  readMemory, animateIn, reducedMotion, enableSplit, pushUndo, registerAdapter,
  registerCommand, openObjectCapsule,
} = core;

const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const runtime = {
  publishingPage: null,
  taskPage: null,
  workPage: null,
  statsPage: null,
  payoutsPage: null,
};

function directChildren(node) {
  return [...(node?.children || [])];
}

function statusCopy(node) {
  return compact(q(".status-badge, .badge, .my-work-status, .my-work-overdue", node)?.textContent || "", 80);
}

function titleCopy(node) {
  return compact(q("h1, h2, h3, strong", node)?.textContent || "Рабочий объект", 140);
}

function isEditableTarget(event) {
  const target = event.target instanceof Element ? event.target : null;
  return Boolean(target?.closest("input, textarea, select, button, a, video, audio, [contenteditable='true']"));
}

function springSwap(outgoing, incoming, direction = 1) {
  if (!incoming || reducedMotion() || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 26}px,0,0) scale(.985)` },
  ], { duration: 170, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 38}px,0,0) scale(.98)`, filter: "blur(4px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 460, easing: SPRING });
}

function publishingStageLabel(index) {
  return ["Задача", "Ссылка", "Чек-лист", "Маркировка", "Подтверждение"][index] || `Шаг ${index + 1}`;
}

function createPublishingTopbar() {
  return elementFrom(`
    <header class="publishing-os-topbar">
      <div class="publishing-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="publishing-os-title"><small>ContentEngine · Publishing</small><strong data-publishing-current-title>Публикации</strong></div>
      <div class="publishing-os-actions">
        <button type="button" data-publishing-open-queue>${icon("publish", 17)}<span>Очередь</span></button>
        <button type="button" data-ce-open-mission>${icon("grid", 17)}<span>Все столы</span></button>
      </div>
    </header>`);
}

function publishingPreview(card) {
  const platform = compact(q(".placement-top .eyebrow", card)?.textContent || "Площадка", 40);
  const title = compact(q(".placement-top h3", card)?.textContent || "Публикация", 100);
  const description = compact(q(".placement-top p", card)?.textContent || "Одобренный материал готов к размещению.", 220);
  return elementFrom(`
    <aside class="publishing-os-preview" aria-label="Предпросмотр публикации">
      <div class="publishing-os-preview__device">
        <header><span>${escapeMarkup(platform)}</span><i></i></header>
        <div class="publishing-os-preview__media">
          <span>${icon("publish", 40)}</span>
          <small>ОДОБРЕННЫЙ МАТЕРИАЛ</small>
        </div>
        <div class="publishing-os-preview__copy">
          <strong>${escapeMarkup(title)}</strong>
          <p>${escapeMarkup(description)}</p>
          <div><i></i><i></i><i></i></div>
        </div>
      </div>
      <div class="publishing-os-preview__status">
        <small>Проверка перед публикацией</small>
        <strong>${escapeMarkup(statusCopy(card) || "Требуется действие")}</strong>
        <p>Площадка, ссылка, маркировка и доказательство результата проверяются отдельно.</p>
      </div>
    </aside>`);
}

function classifyPlacementNode(node) {
  if (node.classList?.contains("placement-top")) return 0;
  if (node.matches?.(".callout, .tracking-link-form")) return 1;
  if (node.classList?.contains("checklist")) return 2;
  if (node.matches?.(".placement-form")) return 4;
  if (node.matches?.(".alert") && /подтвержден|опубликован/u.test(node.textContent.toLocaleLowerCase("ru-RU"))) return 4;
  if (node.matches?.(".alert, p.tiny")) return 3;
  return 3;
}

function setupPlacementCard(card, page) {
  if (!card || card.dataset.publishingOsReady === "true") return;
  card.dataset.publishingOsReady = "true";
  card.classList.add("publishing-os-card");
  const nodes = directChildren(card).filter((node) => !node.classList.contains("ce-v3-object-button"));
  const preview = publishingPreview(card);
  const work = elementFrom(`
    <section class="publishing-os-work">
      <nav class="publishing-os-step-dock" aria-label="Шаги публикации"></nav>
      <div class="publishing-os-panels"></div>
      <footer class="publishing-os-footer">
        <button type="button" data-publishing-step-prev>${icon("left", 18)}<span>Назад</span></button>
        <div><small>Шаг</small><strong data-publishing-position>1 / 5</strong></div>
        <button type="button" data-publishing-step-next><span>Далее</span>${icon("right", 18)}</button>
      </footer>
    </section>`);
  const panels = q(".publishing-os-panels", work);
  const groups = Array.from({ length: 5 }, () => []);
  nodes.forEach((node) => groups[classifyPlacementNode(node)].push(node));
  groups.forEach((group, index) => {
    const panel = document.createElement("section");
    panel.className = "publishing-os-panel";
    panel.dataset.publishingPanel = String(index);
    panel.dataset.ceOsPanel = "true";
    if (!group.length) {
      const empty = elementFrom(`<div class="publishing-os-empty"><span>${icon(index === 4 ? "publish" : "task", 24)}</span><strong>${escapeMarkup(publishingStageLabel(index))}</strong><p>Для этой публикации дополнительных действий на шаге нет.</p></div>`);
      panel.append(empty);
    } else {
      group.forEach((node) => panel.append(node));
    }
    panels.append(panel);
  });
  const dock = q(".publishing-os-step-dock", work);
  dock.innerHTML = groups.map((_, index) => `
    <button type="button" data-publishing-step="${index}" aria-label="${escapeMarkup(publishingStageLabel(index))}">
      <span>${index + 1}</span><small>${escapeMarkup(publishingStageLabel(index))}</small>
    </button>`).join("");
  card.append(preview, work);
  enableSplit(card, preview, work, `publishing:${card.dataset.placementId || titleCopy(card)}`);

  const memory = readMemory();
  const memoryKey = `publishingStep:${card.dataset.placementId || "default"}`;
  let activeIndex = Math.max(0, Math.min(4, Number(memory[memoryKey]) || 0));
  const show = (index, focus = false) => {
    const resolved = Math.max(0, Math.min(4, Number(index) || 0));
    const outgoing = q(".publishing-os-panel.is-active", panels);
    const incoming = q(`.publishing-os-panel[data-publishing-panel="${resolved}"]`, panels);
    const previous = Number(outgoing?.dataset.publishingPanel || resolved);
    qa(".publishing-os-panel", panels).forEach((panel) => {
      const active = Number(panel.dataset.publishingPanel) === resolved;
      panel.classList.toggle("is-active", active);
      panel.hidden = !active;
      panel.inert = !active;
      panel.setAttribute("aria-hidden", String(!active));
    });
    qa("[data-publishing-step]", dock).forEach((button) => {
      const active = Number(button.dataset.publishingStep) === resolved;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-current", active ? "step" : "false");
    });
    q("[data-publishing-position]", work).textContent = `${resolved + 1} / 5`;
    q("[data-publishing-step-prev]", work).disabled = resolved === 0;
    q("[data-publishing-step-next]", work).disabled = resolved === 4;
    activeIndex = resolved;
    remember({ [memoryKey]: resolved });
    if (outgoing !== incoming) springSwap(outgoing, incoming, resolved >= previous ? 1 : -1);
    if (focus) q("button, a, input, select, textarea", incoming)?.focus({ preventScroll: true });
    q("[data-publishing-current-title]", page).textContent = `${titleCopy(card)} · ${publishingStageLabel(resolved)}`;
  };
  dock.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-publishing-step]") : null;
    if (button) show(Number(button.dataset.publishingStep), true);
  });
  q(".publishing-os-footer", work).addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("[data-publishing-step-prev]")) show(activeIndex - 1, true);
    if (event.target.closest("[data-publishing-step-next]")) show(activeIndex + 1, true);
  });
  card._publishingShowStep = show;
  card._publishingStep = () => activeIndex;
  show(activeIndex);
}

function mountPublishing() {
  if (routePath() !== "/workspace/placement") {
    document.body.classList.remove("contentengine-publishing-os-open");
    runtime.publishingPage = null;
    return;
  }
  const list = q(".placement-list");
  const page = list?.closest?.(".page-wrap");
  if (!page) return;
  runtime.publishingPage = page;
  document.body.classList.add("contentengine-publishing-os-open");
  if (page.dataset.publishingOsReady === "true") return;
  page.dataset.publishingOsReady = "true";
  page.classList.add("publishing-os-page");
  const cards = qa(":scope > .placement-card", list);
  const topbar = createPublishingTopbar();
  const windowNode = elementFrom(`
    <section class="publishing-os-window">
      <aside class="publishing-os-queue"><header><small>ОЧЕРЕДЬ</small><strong>Публикации</strong></header><nav></nav></aside>
      <main class="publishing-os-stage"></main>
    </section>`);
  const anchor = q(":scope > .workspace-page-intro", page) || page.firstElementChild;
  anchor?.after?.(topbar, windowNode);
  q(".publishing-os-stage", windowNode).append(list);
  const queue = q(".publishing-os-queue nav", windowNode);
  queue.innerHTML = cards.length ? cards.map((card, index) => `
    <button type="button" data-publishing-card="${index}">
      <span>${icon("publish", 17)}</span><div><strong>${escapeMarkup(titleCopy(card))}</strong><small>${escapeMarkup(statusCopy(card) || "Ждёт действия")}</small></div><i></i>
    </button>`).join("") : '<div class="publishing-os-queue-empty">Публикаций пока нет</div>';
  cards.forEach((card) => setupPlacementCard(card, page));
  const memory = readMemory();
  let activeCard = Math.max(0, Math.min(cards.length - 1, Number(memory.publishingCard) || 0));
  const showCard = (index, focus = false) => {
    if (!cards.length) return;
    const resolved = Math.max(0, Math.min(cards.length - 1, Number(index) || 0));
    const previous = activeCard;
    cards.forEach((card, cardIndex) => {
      const active = cardIndex === resolved;
      card.classList.toggle("is-active", active);
      card.hidden = !active;
      card.inert = !active;
    });
    qa("[data-publishing-card]", queue).forEach((button) => {
      const active = Number(button.dataset.publishingCard) === resolved;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-current", active ? "true" : "false");
    });
    activeCard = resolved;
    remember({ publishingCard: resolved });
    const card = cards[resolved];
    card._publishingShowStep?.(card._publishingStep?.() || 0);
    if (previous !== resolved) springSwap(cards[previous], card, resolved >= previous ? 1 : -1);
    if (focus) card.focus({ preventScroll: true });
  };
  queue.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-publishing-card]") : null;
    if (button) showCard(Number(button.dataset.publishingCard), true);
  });
  topbar.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-publishing-open-queue]")) {
      windowNode.classList.toggle("queue-open");
    }
  });
  page._publishingShowCard = showCard;
  page._publishingActiveCard = () => cards[activeCard];
  page._publishingCards = cards;
  showCard(activeCard);
  animateIn(windowNode);
}

registerCommand({ id: "publish", title: "Открыть публикации", subtitle: "Площадка → текст → маркировка → ссылка", icon: "publish", keywords: "публикация пост размещение", run() { window.location.hash = "/workspace/placement"; } });
registerAdapter("publishing-desktop-v3", mountPublishing);

document.addEventListener("keydown", (event) => {
  if (event.altKey && !event.metaKey && !event.ctrlKey && ["ArrowLeft", "ArrowRight"].includes(event.key) && !isEditableTarget(event)) {
    const page = runtime.publishingPage;
    if (routePath() === "/workspace/placement" && page) {
      const card = page._publishingActiveCard?.();
      if (!card) return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      if (event.shiftKey) {
        const cards = page._publishingCards || [];
        const current = cards.indexOf(card);
        page._publishingShowCard?.(current + direction, true);
      } else {
        card._publishingShowStep?.((card._publishingStep?.() || 0) + direction, true);
      }
    }
  }
}, true);
