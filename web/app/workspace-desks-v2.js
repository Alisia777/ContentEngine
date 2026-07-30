/*
 * Workspace Desks v2
 * One context = one desk. Progressive UI only: no API calls, no permission
 * changes, no cloning of forms and no changes to app-owned training/work state.
 */

const STATE_KEY = "contentengine.workspace-desks.v2";
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
const DESK_PREFIXES = ["/workspace/", "/learn"];
const TYPING_SELECTOR = "input, textarea, select, [contenteditable='true']";
const SURFACE_SELECTOR = ".card, .home-next-action, .workspace-page-intro, .generation-launch-card, .content-review-workspace, .product-research-workspace";
const SURFACE_EXCLUSIONS = ".metric-card, .home-metric-card, .home-guidance-card, .alert, .skeleton-stack, .workspace-initial-loading, .learning-hero, .learning-command-bar, .workspace-direction, .notification-drawer, .generation-archive-summary";
const ENTER_CLASSES = ["workspace-deck-enter-forward", "workspace-deck-enter-backward", "workspace-deck-enter-neutral"];

const runtime = {
  shell: null,
  shellController: null,
  desks: [],
  route: routePath(),
  mountedRoute: "",
  direction: "neutral",
  overlay: null,
  overlayReturnFocus: null,
  focusedCard: null,
  focusMeta: null,
  mountQueued: false,
  scrollTimer: 0,
  lastScrollY: window.scrollY,
  wheelLockUntil: 0,
  stored: readStoredState(),
};

const $ = (selector, root = document) => root?.querySelector?.(selector) || null;
const $$ = (selector, root = document) => [...(root?.querySelectorAll?.(selector) || [])];

function closestTarget(event, selector) {
  return event.target instanceof Element ? event.target.closest(selector) : null;
}

function sessionStore() {
  try { return window.sessionStorage; } catch { return null; }
}

function readStoredState() {
  try {
    const parsed = JSON.parse(sessionStore()?.getItem(STATE_KEY) || "null");
    return {
      scroll: parsed?.scroll && typeof parsed.scroll === "object" ? parsed.scroll : {},
      recent: Array.isArray(parsed?.recent) ? parsed.recent.slice(0, 12) : [],
    };
  } catch {
    return { scroll: {}, recent: [] };
  }
}

function persistStoredState() {
  try { sessionStore()?.setItem(STATE_KEY, JSON.stringify(runtime.stored)); } catch { /* optional enhancement */ }
}

function schedulePersist() {
  window.clearTimeout(runtime.scrollTimer);
  runtime.scrollTimer = window.setTimeout(persistStoredState, 180);
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function hashRoute(href) {
  const value = String(href || "");
  if (!value.startsWith("#/")) return "";
  return value.slice(1).split("?")[0].replace(/\/$/, "") || "/";
}

function isDeskRoute(route) {
  return DESK_PREFIXES.some((prefix) => String(route || "").startsWith(prefix));
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compact(value, limit = 90) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function scheduleMount() {
  if (runtime.mountQueued) return;
  runtime.mountQueued = true;
  window.requestAnimationFrame(() => {
    runtime.mountQueued = false;
    mount();
  });
}

function announce(message) {
  let region = $(".workspace-desk-live-region");
  if (!region) {
    region = elementFrom('<div class="workspace-desk-live-region" aria-live="polite" aria-atomic="true"></div>');
    document.body.append(region);
  }
  region.textContent = "";
  window.setTimeout(() => { region.textContent = message; }, 24);
}

function saveScroll(route = runtime.route, value = runtime.lastScrollY, immediate = false) {
  if (!isDeskRoute(route)) return;
  runtime.stored.scroll[route] = Math.max(0, Math.round(Number(value) || 0));
  if (immediate) persistStoredState(); else schedulePersist();
}

function rememberRoute(route) {
  if (!isDeskRoute(route)) return;
  runtime.stored.recent = [route, ...runtime.stored.recent.filter((item) => item !== route)].slice(0, 12);
  schedulePersist();
}

function collectDesks(shell) {
  const nav = $(".sidebar .workspace-nav", shell);
  if (!nav) return [];
  const desks = [];
  const seen = new Set();
  let group = "Рабочие столы";

  [...nav.children].forEach((node) => {
    if (node.classList?.contains("nav-caption")) {
      group = compact(node.textContent, 42) || group;
      return;
    }
    if (!(node instanceof HTMLAnchorElement)) return;
    const route = hashRoute(node.getAttribute("href"));
    if (!isDeskRoute(route) || seen.has(route)) return;
    seen.add(route);
    const spans = $$("span", node);
    desks.push({
      route,
      label: compact($(".nav-link-copy strong", node)?.textContent || spans.at(-1)?.textContent || node.textContent, 64) || "Рабочий стол",
      hint: compact($(".nav-link-copy small", node)?.textContent || (route === "/learn" ? "Инструкции, тренажёры и допуск" : "Отдельный рабочий контекст"), 90),
      icon: compact($(".nav-stage-number, .nav-icon", node)?.textContent || String(desks.length + 1).padStart(2, "0"), 4),
      group,
    });
  });

  const route = routePath();
  if (isDeskRoute(route) && !seen.has(route)) {
    const learningBase = route.startsWith("/learn/") ? desks.findIndex((desk) => desk.route === "/learn") : -1;
    desks.splice(learningBase >= 0 ? learningBase + 1 : desks.length, 0, {
      route,
      label: compact(document.title.split("·")[0], 64) || "Текущий стол",
      hint: route.startsWith("/learn/") ? "Учебный модуль" : "Текущий рабочий контекст",
      icon: String(Math.max(1, learningBase + 2)).padStart(2, "0"),
      group: route.startsWith("/learn/") ? "Обучение" : "Рабочие столы",
    });
  }
  return desks;
}

function indexOfRoute(route, desks = runtime.desks) {
  const exact = desks.findIndex((desk) => desk.route === route);
  if (exact >= 0) return exact;
  if (route.startsWith("/learn/")) return desks.findIndex((desk) => desk.route === "/learn");
  return -1;
}

function activeDescriptor() {
  const index = indexOfRoute(routePath());
  return {
    index,
    desk: runtime.desks[index] || {
      route: routePath(), label: "Текущий стол", hint: "Рабочий контекст", icon: "•", group: "Кабинет",
    },
  };
}

function calculateDirection(fromRoute, toRoute) {
  const from = indexOfRoute(fromRoute);
  const to = indexOfRoute(toRoute);
  if (from < 0 || to < 0 || from === to) return "neutral";
  return to > from ? "forward" : "backward";
}

function prepareNavigation(targetRoute) {
  saveScroll(runtime.route, runtime.lastScrollY, true);
  runtime.direction = calculateDirection(runtime.route, targetRoute);
}

function goTo(route) {
  if (!route || route === routePath()) {
    closeOverview();
    return;
  }
  closeFocus(false);
  prepareNavigation(route);
  closeOverview(false);
  window.location.hash = route;
}

function goRelative(delta) {
  const { index } = activeDescriptor();
  const target = index >= 0 ? runtime.desks[index + delta] : null;
  if (target) goTo(target.route);
}

function focusRoot() {
  return $("#workspace-content", runtime.shell) || $(".learning-page", runtime.shell) || $("#main-content", runtime.shell);
}

function surfaceTitle(surface) {
  return compact($("h1, h2, h3, legend, strong", surface)?.textContent || "Рабочая задача", 90);
}

function surfaceHint(surface) {
  return compact($("p:not(.eyebrow), .muted, small", surface)?.textContent || "Откройте задачу на весь экран и работайте без отвлечений.", 110);
}

function canFocus(surface) {
  if (!(surface instanceof HTMLElement) || surface.matches(SURFACE_EXCLUSIONS)) return false;
  if (surface.closest(".workspace-overview, .notification-drawer")) return false;
  const parent = surface.parentElement?.closest(SURFACE_SELECTOR);
  if (parent && focusRoot()?.contains(parent)) return false;
  if (!$("h1, h2, h3, legend, form, table, video, .workspace-board", surface)) return false;
  const rect = surface.getBoundingClientRect();
  return Boolean($("form, table, video, .workspace-board, .content-review-workspace", surface)) || rect.height >= 180;
}

function decorateSurfaces() {
  const root = focusRoot();
  if (!root) return;
  const token = routePath().replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "desk";
  $$(SURFACE_SELECTOR, root).filter(canFocus).forEach((surface, index) => {
    surface.dataset.workspaceFocusable = "true";
    surface.classList.add("workspace-focusable-card");
    if (!surface.id) surface.id = `workspace-focus-${token}-${index + 1}`;
    if ($(':scope > .desk-focus-button', surface)) return;
    surface.append(elementFrom(`
      <button class="desk-focus-button" type="button" data-workspace-focus-card="${escapeMarkup(surface.id)}" aria-label="Развернуть задачу «${escapeMarkup(surfaceTitle(surface))}» на весь стол">
        <span class="desk-focus-button__icon" aria-hidden="true">⛶</span><span class="desk-focus-button__label">На весь стол</span>
      </button>
    `));
  });
}

function focusableSurfaces() {
  return $$('[data-workspace-focusable="true"]', focusRoot()).filter((surface) => surface.isConnected);
}

function primarySurface() {
  const surfaces = focusableSurfaces();
  return surfaces.find((surface) => surface.matches(".home-next-action, [data-workspace-primary]"))
    || surfaces.find((surface) => $("form", surface))
    || surfaces[0]
    || null;
}

function neighborMarkup(desk, direction) {
  const disabled = !desk;
  const side = direction < 0 ? "Предыдущий" : "Следующий";
  return `
    <button class="workspace-deck-neighbor" type="button" data-deck-nav="${direction}" ${disabled ? "disabled" : ""} aria-label="${disabled ? "Другого стола нет" : `${side} стол: ${escapeMarkup(desk.label)}`}">
      ${direction < 0 ? '<span class="workspace-deck-neighbor__arrow" aria-hidden="true">←</span>' : ""}
      <span class="workspace-deck-neighbor__copy"><small>${side} стол</small><strong>${escapeMarkup(desk?.label || "Край пространства")}</strong></span>
      ${direction > 0 ? '<span class="workspace-deck-neighbor__arrow" aria-hidden="true">→</span>' : ""}
    </button>
  `;
}

function renderDeckbar() {
  let bar = $(".workspace-deckbar", runtime.shell);
  if (!bar) {
    bar = document.createElement("section");
    bar.className = "workspace-deckbar";
    bar.setAttribute("aria-label", "Переключение рабочих столов");
    $("#main-content", runtime.shell)?.before(bar);
  }

  const { index, desk } = activeDescriptor();
  const previous = index > 0 ? runtime.desks[index - 1] : null;
  const next = index >= 0 && index < runtime.desks.length - 1 ? runtime.desks[index + 1] : null;
  const total = Math.max(1, runtime.desks.length);
  const position = index >= 0 ? index + 1 : 1;
  const hasFocus = Boolean(primarySurface());
  const signature = JSON.stringify({ route: routePath(), desks: runtime.desks, hasFocus });
  if (bar.dataset.deckSignature === signature) return;
  bar.dataset.deckSignature = signature;
  bar.innerHTML = `
    <div class="workspace-deck-rail">
      ${neighborMarkup(previous, -1)}
      <div class="workspace-deck-current" aria-current="page">
        <span class="workspace-deck-current__number" aria-hidden="true">${escapeMarkup(desk.icon || String(position).padStart(2, "0"))}</span>
        <span class="workspace-deck-current__copy"><small>${escapeMarkup(desk.group)}</small><strong>${escapeMarkup(desk.label)}</strong><span>${escapeMarkup(desk.hint)}</span></span>
        <span class="workspace-deck-current__position" aria-label="Стол ${position} из ${total}">${position}/${total}</span>
      </div>
      ${neighborMarkup(next, 1)}
    </div>
    <div class="workspace-deck-actions">
      <button class="workspace-deck-action" type="button" data-deck-action="overview" aria-label="Показать все рабочие столы"><span class="workspace-deck-action__icon" aria-hidden="true">▦</span><span class="workspace-deck-action__label">Все столы</span></button>
      <button class="workspace-deck-action" type="button" data-deck-action="focus" ${hasFocus ? "" : "disabled"} aria-label="Развернуть главную задачу на весь стол"><span class="workspace-deck-action__icon" aria-hidden="true">⛶</span><span class="workspace-deck-action__label">Фокус</span><kbd>F</kbd></button>
      <button class="workspace-deck-action" type="button" data-deck-action="palette" aria-label="Быстрый поиск рабочего стола"><span class="workspace-deck-action__icon" aria-hidden="true">⌕</span><span class="workspace-deck-action__label">Найти</span><kbd>⌘K</kbd></button>
    </div>
  `;
}

function animateRoute(changed) {
  if (!changed) return;
  const target = $("#workspace-content", runtime.shell) || $("#main-content > .page-wrap", runtime.shell) || $("#main-content", runtime.shell);
  if (!target) return;
  target.classList.remove(...ENTER_CLASSES);
  void target.offsetWidth;
  const className = runtime.direction === "forward"
    ? "workspace-deck-enter-forward"
    : runtime.direction === "backward"
      ? "workspace-deck-enter-backward"
      : "workspace-deck-enter-neutral";
  target.classList.add(className);
  window.setTimeout(() => target.classList.remove(className), 560);
  runtime.direction = "neutral";
}

function restoreScroll(route) {
  if (window.location.hash.includes("?")) return;
  const value = Number(runtime.stored.scroll[route]);
  if (!Number.isFinite(value) || value < 24) return;
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
    window.scrollTo({ top: value, left: 0, behavior: "auto" });
    runtime.lastScrollY = value;
  }));
}

function openFocus(surface) {
  if (!surface?.isConnected) return;
  closeOverview(false);
  closeFocus(false);
  const title = surfaceTitle(surface);
  const chrome = elementFrom(`
    <div class="workspace-focus-chrome">
      <span class="workspace-focus-chrome__copy"><small>Фокус · один стол</small><strong>${escapeMarkup(title)}</strong></span>
      <button class="workspace-focus-close" type="button" data-workspace-focus-close><span aria-hidden="true">×</span> Вернуть в кабинет</button>
    </div>
  `);
  const backdrop = elementFrom('<div class="workspace-focus-backdrop" data-workspace-focus-backdrop aria-hidden="true"></div>');
  runtime.focusMeta = {
    previousFocus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
    previousRole: surface.getAttribute("role"),
    previousModal: surface.getAttribute("aria-modal"),
    previousLabel: surface.getAttribute("aria-label"),
    chrome,
    backdrop,
    scrollY: window.scrollY,
  };
  runtime.focusedCard = surface;
  surface.prepend(chrome);
  surface.classList.add("workspace-task-focused");
  surface.setAttribute("role", "dialog");
  surface.setAttribute("aria-modal", "true");
  surface.setAttribute("aria-label", title);
  document.body.append(backdrop);
  document.body.classList.add("workspace-focus-mode");
  $("[data-workspace-focus-close]", chrome)?.focus({ preventScroll: true });
  announce(`Фокус открыт: ${title}`);
}

function restoreAttribute(element, name, value) {
  if (value === null) element.removeAttribute(name); else element.setAttribute(name, value);
}

function closeFocus(restoreFocus = true) {
  const surface = runtime.focusedCard;
  const meta = runtime.focusMeta;
  if (!surface || !meta) {
    document.body.classList.remove("workspace-focus-mode");
    $(".workspace-focus-backdrop")?.remove();
    runtime.focusedCard = null;
    runtime.focusMeta = null;
    return;
  }
  meta.chrome.remove();
  meta.backdrop.remove();
  surface.classList.remove("workspace-task-focused");
  restoreAttribute(surface, "role", meta.previousRole);
  restoreAttribute(surface, "aria-modal", meta.previousModal);
  restoreAttribute(surface, "aria-label", meta.previousLabel);
  document.body.classList.remove("workspace-focus-mode");
  runtime.focusedCard = null;
  runtime.focusMeta = null;
  window.scrollTo({ top: meta.scrollY, left: 0, behavior: "auto" });
  if (restoreFocus && meta.previousFocus?.isConnected) meta.previousFocus.focus({ preventScroll: true });
  announce("Фокус закрыт. Вы вернулись на рабочий стол.");
}

function deskCardMarkup(desk, index) {
  const current = routePath();
  const active = desk.route === current || (current.startsWith("/learn/") && desk.route === "/learn");
  const keywords = `${desk.label} ${desk.hint} ${desk.group}`.toLocaleLowerCase("ru-RU");
  return `
    <button class="workspace-overview-card${active ? " is-active" : ""}" type="button" data-overview-route="${escapeMarkup(desk.route)}" data-overview-keywords="${escapeMarkup(keywords)}">
      <span class="workspace-overview-card__top"><span class="workspace-overview-card__number" aria-hidden="true">${escapeMarkup(desk.icon || String(index + 1).padStart(2, "0"))}</span><span class="workspace-overview-card__group">${escapeMarkup(desk.group)}</span></span>
      <span class="workspace-overview-card__preview" aria-hidden="true"></span>
      <span class="workspace-overview-card__copy"><strong>${escapeMarkup(desk.label)}</strong><small>${escapeMarkup(desk.hint)}</small></span>
    </button>
  `;
}

function taskCardMarkup(surface, index) {
  const title = surfaceTitle(surface);
  const hint = surfaceHint(surface);
  return `
    <button class="workspace-overview-card workspace-overview-task" type="button" data-overview-focus-id="${escapeMarkup(surface.id)}" data-overview-keywords="${escapeMarkup(`${title} ${hint}`.toLocaleLowerCase("ru-RU"))}">
      <span class="workspace-overview-card__top"><span class="workspace-overview-card__number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span><span class="workspace-overview-card__group">Задача на этом столе</span></span>
      <span class="workspace-overview-card__copy"><strong>${escapeMarkup(title)}</strong><small>${escapeMarkup(hint)}</small></span>
    </button>
  `;
}

function openOverview(focusSearch = false) {
  if (!runtime.shell) return;
  closeOverview(false);
  runtime.overlayReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const tasks = focusableSurfaces();
  runtime.overlay = elementFrom(`
    <div class="workspace-overview-backdrop" data-workspace-overview-backdrop>
      <section class="workspace-overview" role="dialog" aria-modal="true" aria-labelledby="workspace-overview-title">
        <header class="workspace-overview__header">
          <div><p>Mission Control · кабинет</p><h2 id="workspace-overview-title">Ваши рабочие столы</h2><span>Каждый стол хранит свой контекст и место прокрутки. Выберите направление или разверните одну задачу без лишнего шума.</span></div>
          <button class="workspace-overview__close" type="button" data-overview-close aria-label="Закрыть обзор">×</button>
        </header>
        <label class="workspace-overview__search"><span class="sr-only">Найти рабочий стол или задачу</span><input type="search" data-overview-search autocomplete="off" placeholder="Найти стол, этап или задачу…" /><kbd>⌘K</kbd></label>
        <div class="workspace-overview__body">
          <section class="workspace-overview__section">
            <div class="workspace-overview__section-head"><strong>Все пространства</strong><span>${runtime.desks.length} рабочих столов</span></div>
            <div class="workspace-overview__grid">${runtime.desks.map(deskCardMarkup).join("")}</div>
          </section>
          ${tasks.length ? `<section class="workspace-overview__section"><div class="workspace-overview__section-head"><strong>Задачи на текущем столе</strong><span>${tasks.length} можно развернуть в фокус</span></div><div class="workspace-overview__grid">${tasks.map(taskCardMarkup).join("")}</div></section>` : ""}
        </div>
        <footer class="workspace-overview__footer"><div class="workspace-overview__shortcuts"><span><kbd>⌘K</kbd> поиск</span><span><kbd>Alt⇧←/→</kbd> соседний стол</span><span><kbd>F</kbd> фокус</span><span><kbd>Esc</kbd> закрыть</span></div><span>На телефоне столы перелистываются горизонтальным свайпом.</span></footer>
      </section>
    </div>
  `);
  document.body.append(runtime.overlay);
  document.body.style.overflow = "hidden";
  const input = $("[data-overview-search]", runtime.overlay);
  input?.addEventListener("input", () => {
    const query = String(input.value || "").trim().toLocaleLowerCase("ru-RU");
    $$('[data-overview-keywords]', runtime.overlay).forEach((card) => {
      card.hidden = Boolean(query) && !String(card.dataset.overviewKeywords || "").includes(query);
    });
  });
  if (focusSearch) input?.focus({ preventScroll: true });
  else $("[data-overview-route].is-active, [data-overview-route], [data-overview-close]", runtime.overlay)?.focus({ preventScroll: true });
}

function closeOverview(restoreFocus = true) {
  if (!runtime.overlay) return;
  runtime.overlay.remove();
  runtime.overlay = null;
  if (!runtime.focusedCard) document.body.style.removeProperty("overflow");
  if (restoreFocus && runtime.overlayReturnFocus?.isConnected) runtime.overlayReturnFocus.focus({ preventScroll: true });
  runtime.overlayReturnFocus = null;
}

function focusableInside(container) {
  return $$("button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex='-1'])", container)
    .filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
}

function trapTab(event, container) {
  if (event.key !== "Tab" || !container) return;
  const items = focusableInside(container);
  if (!items.length) return;
  if (event.shiftKey && document.activeElement === items[0]) {
    event.preventDefault();
    items.at(-1).focus();
  } else if (!event.shiftKey && document.activeElement === items.at(-1)) {
    event.preventDefault();
    items[0].focus();
  }
}

function bindGestures(signal) {
  const main = $("#main-content", runtime.shell);
  if (!main) return;
  let start = null;
  main.addEventListener("pointerdown", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (event.pointerType !== "touch" || target?.closest(`${TYPING_SELECTOR}, button, a, .table-wrap, .data-table-wrap`)) return;
    start = { x: event.clientX, y: event.clientY, id: event.pointerId };
  }, { passive: true, signal });
  main.addEventListener("pointerup", (event) => {
    if (!start || event.pointerId !== start.id) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    start = null;
    if (Math.abs(dx) >= 82 && Math.abs(dx) > Math.abs(dy) * 1.35) goRelative(dx < 0 ? 1 : -1);
  }, { passive: true, signal });
  main.addEventListener("pointercancel", () => { start = null; }, { passive: true, signal });
  main.addEventListener("wheel", (event) => {
    if (!event.altKey || Math.abs(event.deltaX) < 36 || Math.abs(event.deltaX) < Math.abs(event.deltaY) || Date.now() < runtime.wheelLockUntil) return;
    event.preventDefault();
    runtime.wheelLockUntil = Date.now() + 720;
    goRelative(event.deltaX > 0 ? 1 : -1);
  }, { passive: false, signal });
}

function cleanShell() {
  runtime.shellController?.abort();
  runtime.shellController = null;
  runtime.shell = null;
  runtime.desks = [];
  closeFocus(false);
  closeOverview(false);
}

function mount() {
  const shell = $(".workspace-shell");
  const route = routePath();
  if (!shell || !isDeskRoute(route)) {
    if (runtime.shell) cleanShell();
    return;
  }
  if (shell !== runtime.shell) {
    runtime.shellController?.abort();
    runtime.shell = shell;
    runtime.shellController = new AbortController();
    shell.classList.add("workspace-desks-enabled");
    bindGestures(runtime.shellController.signal);
  }
  decorateSurfaces();
  runtime.desks = collectDesks(shell);
  renderDeckbar();
  const changed = route !== runtime.mountedRoute;
  animateRoute(changed);
  if (changed) {
    rememberRoute(route);
    restoreScroll(route);
    announce(`Открыт рабочий стол: ${activeDescriptor().desk.label}`);
    runtime.mountedRoute = route;
  }
}

function handleClick(event) {
  const overviewClose = closestTarget(event, "[data-overview-close]");
  if (runtime.overlay && (event.target === runtime.overlay || overviewClose)) {
    closeOverview();
    return;
  }
  const overviewRoute = closestTarget(event, "[data-overview-route]");
  if (overviewRoute) {
    goTo(overviewRoute.dataset.overviewRoute || "");
    return;
  }
  const overviewTask = closestTarget(event, "[data-overview-focus-id]");
  if (overviewTask) {
    const surface = document.getElementById(overviewTask.dataset.overviewFocusId || "");
    closeOverview(false);
    openFocus(surface);
    return;
  }
  if (closestTarget(event, "[data-workspace-focus-close], [data-workspace-focus-backdrop]")) {
    closeFocus();
    return;
  }
  const relative = closestTarget(event, "[data-deck-nav]");
  if (relative) {
    goRelative(Number(relative.dataset.deckNav) || 0);
    return;
  }
  const action = closestTarget(event, "[data-deck-action]");
  if (action) {
    if (action.dataset.deckAction === "overview") openOverview(false);
    if (action.dataset.deckAction === "palette") openOverview(true);
    if (action.dataset.deckAction === "focus") openFocus(primarySurface());
    return;
  }
  const focusButton = closestTarget(event, "[data-workspace-focus-card]");
  if (focusButton) {
    openFocus(document.getElementById(focusButton.dataset.workspaceFocusCard || ""));
    return;
  }
  const anchor = closestTarget(event, "a[href^='#/']");
  const targetRoute = anchor ? hashRoute(anchor.getAttribute("href")) : "";
  if (isDeskRoute(targetRoute)) prepareNavigation(targetRoute);
}

function handleKeydown(event) {
  if (runtime.overlay) {
    if (event.key === "Escape") { event.preventDefault(); closeOverview(); return; }
    trapTab(event, $(".workspace-overview", runtime.overlay));
    return;
  }
  if (runtime.focusedCard) {
    if (event.key === "Escape") { event.preventDefault(); closeFocus(); return; }
    trapTab(event, runtime.focusedCard);
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openOverview(true);
    return;
  }
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest(TYPING_SELECTOR) || !runtime.shell) return;
  if (event.altKey && event.shiftKey && event.key === "ArrowLeft") { event.preventDefault(); goRelative(-1); return; }
  if (event.altKey && event.shiftKey && event.key === "ArrowRight") { event.preventDefault(); goRelative(1); return; }
  if (!event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "f") { event.preventDefault(); openFocus(primarySurface()); return; }
  if (event.altKey && /^[1-9]$/.test(event.key)) {
    const desk = runtime.desks[Number(event.key) - 1];
    if (desk) { event.preventDefault(); goTo(desk.route); }
  }
}

function handleHashchange() {
  saveScroll(runtime.route, runtime.lastScrollY, true);
  const next = routePath();
  if (runtime.direction === "neutral") runtime.direction = calculateDirection(runtime.route, next);
  runtime.route = next;
  closeFocus(false);
  closeOverview(false);
  scheduleMount();
}

function handleScroll() {
  runtime.lastScrollY = window.scrollY;
  saveScroll(runtime.route, runtime.lastScrollY, false);
}

const app = $("#app");
if (app) new MutationObserver(scheduleMount).observe(app, { childList: true, subtree: true });
document.addEventListener("click", handleClick, true);
document.addEventListener("keydown", handleKeydown);
window.addEventListener("hashchange", handleHashchange, { passive: true });
window.addEventListener("scroll", handleScroll, { passive: true });
window.addEventListener("beforeunload", () => saveScroll(runtime.route, runtime.lastScrollY, true));
scheduleMount();
