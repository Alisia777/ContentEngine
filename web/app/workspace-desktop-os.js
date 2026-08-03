/*
 * ContentEngine Desktop OS
 * Real workspace composition for review and academy routes plus a macOS-like
 * application Dock. Presentation-only: no API calls, no business-state writes,
 * no cloning of forms or task content.
 */

const OS_STATE_KEY = "contentengine.desktop-os.v1";
const REVIEW_ROUTE = "/workspace/review";
const LEARN_ROUTE = "/learn";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const INTERACTIVE_SELECTOR = "input, textarea, select, button, a, video, audio, [contenteditable='true'], .table-wrap, .data-table-wrap";
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const runtime = {
  queued: false,
  route: routePath(),
  dock: null,
  dockFrame: 0,
  dockEvent: null,
  reviewPage: null,
  academyPage: null,
  memory: readMemory(),
};

const ICONS = Object.freeze({
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5.5 9.5V21h13V9.5"/><path d="M9 21v-6h6v6"/>',
  media: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 16 3.5-4 3 3 2-2 2.5 3"/><circle cx="8" cy="8.5" r="1.3"/>',
  research: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/><path d="M8 11h6M11 8v6"/>',
  generate: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m5.6 5.6 2.8 2.8m7.2 7.2 2.8 2.8m0-12.8-2.8 2.8m-7.2 7.2-2.8 2.8"/><circle cx="12" cy="12" r="3"/>',
  review: '<path d="M8 4h8M9 3h6v3H9z"/><rect x="5" y="5" width="14" height="16" rx="2"/><path d="m9 13 2 2 4-5"/>',
  work: '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M8 6V4h8v2M3 11h18M9 11v2h6v-2"/>',
  publish: '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6h14v-6"/>',
  money: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 15h4"/><circle cx="16" cy="14" r="2"/>',
  learn: '<path d="m3 6 9-3 9 3-9 3-9-3Z"/><path d="M6 8v6c3 2 9 2 12 0V8M21 6v7"/>',
  tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  chevronLeft: '<path d="m15 18-6-6 6-6"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6M12 7v5l3 2"/>',
  course: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 7h8M8 11h8M8 15h5"/>',
  practice: '<path d="M5 20h14M7 20V8l5-5 5 5v12"/><path d="M9 12h6M9 16h6"/>',
  map: '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/>',
  trophy: '<path d="M8 4h8v5a4 4 0 0 1-8 0V4Z"/><path d="M8 6H4v2a4 4 0 0 0 4 4M16 6h4v2a4 4 0 0 1-4 4M12 13v4M8 21h8M9 17h6"/>',
});

function icon(name, size = 20) {
  const body = ICONS[name] || ICONS.grid;
  return `<svg class="ce-os-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function routeFromHref(value) {
  const raw = String(value || "");
  if (!raw.startsWith("#/")) return "";
  return raw.slice(1).split("?")[0].replace(/\/$/, "") || "/";
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

function store() {
  try { return window.sessionStorage; } catch { return null; }
}

function readMemory() {
  try {
    const parsed = JSON.parse(store()?.getItem(OS_STATE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function persistMemory() {
  try { store()?.setItem(OS_STATE_KEY, JSON.stringify(runtime.memory)); } catch { /* optional */ }
}

function remember(key, value) {
  runtime.memory[key] = value;
  persistMemory();
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

function routeIcon(route) {
  if (route === "/workspace/home") return "home";
  if (/media|materials/.test(route)) return "media";
  if (/research/.test(route)) return "research";
  if (/generation|generate/.test(route)) return "generate";
  if (/review/.test(route)) return "review";
  if (/placement|publish/.test(route)) return "publish";
  if (/payout|earning/.test(route)) return "money";
  if (/work|task|board/.test(route)) return "work";
  if (route.startsWith("/learn")) return "learn";
  return "grid";
}

function collectDockItems(shell) {
  const anchors = qa('.sidebar .workspace-nav a[href^="#/"]', shell);
  const byRoute = new Map();
  anchors.forEach((anchor) => {
    const route = routeFromHref(anchor.getAttribute("href"));
    if (!route || byRoute.has(route)) return;
    const label = compact(q(".nav-link-copy strong", anchor)?.textContent || qa("span", anchor).at(-1)?.textContent || anchor.textContent, 42);
    if (!label) return;
    byRoute.set(route, { route, label, icon: routeIcon(route) });
  });
  const priority = [
    "/workspace/home", "/workspace/media", "/workspace/research",
    "/workspace/generation", "/workspace/review", "/workspace/work",
    "/workspace/placements", "/workspace/payouts", "/learn",
  ];
  const items = [];
  priority.forEach((route) => {
    const item = byRoute.get(route);
    if (item) items.push(item);
  });
  for (const item of byRoute.values()) {
    if (items.length >= 10) break;
    if (!items.some((candidate) => candidate.route === item.route)) items.push(item);
  }
  return items;
}

function dockItemMarkup(item, activeRoute) {
  const active = activeRoute === item.route || (activeRoute.startsWith("/learn/") && item.route === "/learn");
  return `
    <a class="ce-mac-dock__item${active ? " is-active" : ""}" href="#${escapeMarkup(item.route)}" data-ce-dock-route="${escapeMarkup(item.route)}" aria-label="${escapeMarkup(item.label)}">
      <span class="ce-mac-dock__tooltip">${escapeMarkup(item.label)}</span>
      <span class="ce-mac-dock__icon">${icon(item.icon, 22)}</span>
      <i aria-hidden="true"></i>
    </a>`;
}

function mountMacDock(shell) {
  const route = routePath();
  const retired = window.CONTENTENGINE_DESKTOP_V4 === true
    || route === LEARN_ROUTE
    || route.startsWith(`${LEARN_ROUTE}/`);
  if (!shell || retired) {
    qa(".ce-mac-dock").forEach((dock) => dock.remove());
    runtime.dock = null;
    document.body.classList.remove("ce-os-dock-visible");
    return;
  }
  const items = collectDockItems(shell);
  if (!items.length) return;
  let dock = q(".ce-mac-dock", shell);
  if (!dock) {
    dock = elementFrom('<nav class="ce-mac-dock" aria-label="Рабочие пространства"></nav>');
    shell.append(dock);
  }
  runtime.dock = dock;
  const activeRoute = routePath();
  const signature = JSON.stringify({ activeRoute, items });
  if (dock.dataset.signature !== signature) {
    dock.dataset.signature = signature;
    dock.innerHTML = `
      <div class="ce-mac-dock__glass">
        ${items.map((item) => dockItemMarkup(item, activeRoute)).join("")}
        <span class="ce-mac-dock__separator" aria-hidden="true"></span>
        <button class="ce-mac-dock__item ce-mac-dock__mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">
          <span class="ce-mac-dock__tooltip">Все столы</span>
          <span class="ce-mac-dock__icon">${icon("grid", 22)}</span>
        </button>
      </div>`;
  }
  document.body.classList.add("ce-os-dock-visible");
}

function resetDockMagnification() {
  const dock = runtime.dock;
  if (!dock) return;
  qa(".ce-mac-dock__item", dock).forEach((item) => {
    item.style.removeProperty("--ce-dock-scale");
    item.style.removeProperty("--ce-dock-lift");
    item.style.removeProperty("--ce-dock-z");
  });
}

function updateDockMagnification(event) {
  runtime.dockFrame = 0;
  const dock = runtime.dock;
  if (!dock || !FINE_POINTER.matches || REDUCED_MOTION.matches) {
    resetDockMagnification();
    return;
  }
  const glass = event?.target instanceof Element ? event.target.closest(".ce-mac-dock__glass") : null;
  if (!glass || !dock.contains(glass)) {
    resetDockMagnification();
    return;
  }
  qa(".ce-mac-dock__item", glass).forEach((item) => {
    const rect = item.getBoundingClientRect();
    const center = rect.left + rect.width / 2;
    const distance = Math.abs(event.clientX - center);
    const influence = Math.max(0, 1 - distance / 132);
    const eased = influence * influence * (3 - 2 * influence);
    item.style.setProperty("--ce-dock-scale", String(1 + eased * 0.34));
    item.style.setProperty("--ce-dock-lift", `${-eased * 13}px`);
    item.style.setProperty("--ce-dock-z", String(2 + Math.round(eased * 10)));
  });
}

function handleDockPointerMove(event) {
  runtime.dockEvent = event;
  if (runtime.dockFrame) return;
  runtime.dockFrame = window.requestAnimationFrame(() => updateDockMagnification(runtime.dockEvent));
}

function animateSwap(outgoing, incoming, direction = 1) {
  if (!incoming || REDUCED_MOTION.matches || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 34}px,0,0) scale(.985)` },
  ], { duration: 180, easing: "ease-out", fill: "none" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 46}px,0,0) scale(.978)`, filter: "blur(5px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.004)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 520, easing: SPRING, fill: "none" });
}

function setActivePanel(container, index, options = {}) {
  if (!container) return;
  const panels = qa(":scope > [data-ce-os-panel]", container).filter((panel) => !panel.hidden);
  if (!panels.length) return;
  const nextIndex = Math.max(0, Math.min(panels.length - 1, Number(index) || 0));
  const previous = panels.find((panel) => panel.classList.contains("is-active"));
  const previousIndex = previous ? panels.indexOf(previous) : nextIndex;
  panels.forEach((panel, panelIndex) => {
    const active = panelIndex === nextIndex;
    panel.classList.toggle("is-active", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
    panel.inert = !active;
  });
  qa("[data-ce-os-panel-index]", options.nav || document).forEach((button) => {
    const active = Number(button.dataset.ceOsPanelIndex) === nextIndex;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "step" : "false");
  });
  if (previous !== panels[nextIndex]) animateSwap(previous, panels[nextIndex], nextIndex >= previousIndex ? 1 : -1);
  if (options.memoryKey) remember(options.memoryKey, nextIndex);
  options.onChange?.(nextIndex, panels.length, panels[nextIndex]);
}

function panelLabel(panel, fallback = "Шаг") {
  return compact(q("legend, .eyebrow, h2, h3, strong", panel)?.textContent || fallback, 56);
}

function reviewMode(page) {
  return page.dataset.reviewOsMode || "new";
}

function setReviewMode(page, mode, focus = false) {
  const available = new Set(["new", "result", "history"]);
  const resolved = available.has(mode) ? mode : "new";
  const previous = reviewMode(page);
  page.dataset.reviewOsMode = resolved;
  qa("[data-review-os-mode]", page).forEach((button) => {
    const active = button.dataset.reviewOsMode === resolved;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const outgoing = q(`[data-review-os-space="${CSS.escape(previous)}"]`, page);
  const incoming = q(`[data-review-os-space="${CSS.escape(resolved)}"]`, page);
  qa("[data-review-os-space]", page).forEach((space) => {
    const active = space.dataset.reviewOsSpace === resolved;
    space.classList.toggle("is-active", active);
    space.setAttribute("aria-hidden", active ? "false" : "true");
    space.inert = !active;
  });
  if (previous !== resolved) {
    const order = ["new", "result", "history"];
    animateSwap(outgoing, incoming, order.indexOf(resolved) >= order.indexOf(previous) ? 1 : -1);
  }
  remember("reviewMode", resolved);
  if (focus) q("button, a, input, select, textarea", incoming)?.focus({ preventScroll: true });
}

function refreshFooter(form, footer, nav, page) {
  const panels = qa(":scope > [data-ce-os-panel]", form).filter((panel) => !panel.hidden);
  const index = Math.max(0, panels.findIndex((panel) => panel.classList.contains("is-active")));
  q("[data-review-form-position]", footer).textContent = `${index + 1} / ${panels.length}`;
  q("[data-review-form-prev]", footer).disabled = index <= 0;
  q("[data-review-form-next]", footer).hidden = index >= panels.length - 1;
  page.style.setProperty("--review-os-step-progress", `${((index + 1) / panels.length) * 100}%`);
  q("[data-review-os-current-title]", page).textContent = panelLabel(panels[index], "Новая проверка");
  qa("[data-ce-os-panel-index]", nav).forEach((button) => button.classList.toggle("is-active", Number(button.dataset.ceOsPanelIndex) === index));
}

function setupReviewForm(form, page) {
  if (!form || form.dataset.reviewOsReady === "true") return;
  form.dataset.reviewOsReady = "true";
  form.classList.add("review-os-form");
  q(":scope > .content-review-form__header", form)?.classList.add("review-os-form-intro");
  const submit = q(":scope > .content-review-submit", form);
  if (submit) {
    const submitPanel = document.createElement("section");
    submitPanel.className = "review-os-submit-panel";
    submitPanel.dataset.reviewSyntheticStep = "true";
    submit.before(submitPanel);
    submitPanel.append(submit);
  }
  const allPanels = qa(":scope > .content-review-fieldset, :scope > .review-os-submit-panel", form);
  allPanels.forEach((panel, index) => {
    panel.dataset.ceOsPanel = "true";
    panel.dataset.reviewFormStep = String(index);
  });
  const nav = elementFrom('<nav class="review-os-step-dock" aria-label="Этапы новой проверки"></nav>');
  const footer = elementFrom(`
    <div class="review-os-footer">
      <button type="button" data-review-form-prev>${icon("chevronLeft", 19)}<span>Назад</span></button>
      <div><small>Этап</small><strong data-review-form-position>1 / ${allPanels.length}</strong></div>
      <button type="button" data-review-form-next><span>Далее</span>${icon("chevronRight", 19)}</button>
    </div>`);
  form.prepend(nav);
  form.append(footer);
  const show = (index) => setActivePanel(form, index, {
    nav,
    memoryKey: "reviewFormStep",
    onChange() { refreshFooter(form, footer, nav, page); },
  });
  const refresh = () => {
    const panels = allPanels.filter((panel) => !panel.hidden);
    nav.innerHTML = panels.map((panel, index) => `
      <button type="button" data-ce-os-panel-index="${index}" aria-label="${escapeMarkup(panelLabel(panel, `Этап ${index + 1}`))}">
        <span>${index + 1}</span><small>${escapeMarkup(panelLabel(panel, `Этап ${index + 1}`))}</small>
      </button>`).join("");
    show(Math.min(Number(runtime.memory.reviewFormStep) || 0, Math.max(0, panels.length - 1)));
  };
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-os-panel-index]") : null;
    if (button) show(Number(button.dataset.ceOsPanelIndex));
  });
  footer.addEventListener("click", (event) => {
    const panels = qa(":scope > [data-ce-os-panel]", form).filter((panel) => !panel.hidden);
    const current = panels.findIndex((panel) => panel.classList.contains("is-active"));
    if (event.target instanceof Element && event.target.closest("[data-review-form-prev]")) show(current - 1);
    if (event.target instanceof Element && event.target.closest("[data-review-form-next]")) show(current + 1);
  });
  form.addEventListener("change", () => window.setTimeout(refresh, 0));
  refresh();
}

function resultPanelLabel(node, index) {
  if (node.classList.contains("content-review-score-grid")) return "Итог";
  if (node.classList.contains("content-review-breakdown")) return "Оценка";
  if (node.classList.contains("content-review-findings")) return "Риски";
  if (node.classList.contains("content-review-recommendations")) return "Правки";
  if (node.classList.contains("content-review-strengths")) return "Сильные стороны";
  if (node.matches("form, .content-review-decision")) return "Решение";
  if (node.classList.contains("content-review-ruleset")) return "Основание";
  return compact(q(".eyebrow, h2, h3, strong", node)?.textContent, 36) || `Раздел ${index + 1}`;
}

function setupReviewResult(article, page) {
  if (!article || article.dataset.reviewOsReady === "true") return;
  article.dataset.reviewOsReady = "true";
  article.classList.add("review-os-result");
  const direct = [...article.children];
  const header = direct.find((node) => node.classList?.contains("content-review-result__header"));
  const preview = direct.find((node) => node.classList?.contains("content-review-decision-preview"));
  const consumed = new Set([header, preview].filter(Boolean));
  const panelNodes = [];
  if (header || preview) panelNodes.push({ label: "Материал", nodes: [header, preview].filter(Boolean), icon: "media" });
  direct.forEach((node, index) => {
    if (consumed.has(node)) return;
    if (node.classList?.contains("content-review-message")) {
      if (panelNodes[0]) panelNodes[0].nodes.unshift(node);
      else panelNodes.push({ label: "Статус", nodes: [node], icon: "review" });
      return;
    }
    const label = resultPanelLabel(node, index);
    const panelIcon = /риск/i.test(label) ? "review" : /решен/i.test(label) ? "work" : /правк/i.test(label) ? "tasks" : "course";
    panelNodes.push({ label, nodes: [node], icon: panelIcon });
  });
  if (!panelNodes.length) return;
  const shell = elementFrom(`
    <div class="review-os-result-shell">
      <nav class="review-os-result-dock" aria-label="Этапы результата"></nav>
      <div class="review-os-result-panels"></div>
      <div class="review-os-footer review-os-result-footer">
        <button type="button" data-review-result-prev>${icon("chevronLeft", 19)}<span>Назад</span></button>
        <div><small>Раздел</small><strong data-review-result-position>1 / ${panelNodes.length}</strong></div>
        <button type="button" data-review-result-next><span>Далее</span>${icon("chevronRight", 19)}</button>
      </div>
    </div>`);
  const nav = q(".review-os-result-dock", shell);
  const panels = q(".review-os-result-panels", shell);
  nav.innerHTML = panelNodes.map((item, index) => `
    <button type="button" data-ce-os-panel-index="${index}" aria-label="${escapeMarkup(item.label)}">
      <span>${icon(item.icon, 18)}</span><small>${escapeMarkup(item.label)}</small>
    </button>`).join("");
  panelNodes.forEach((item, index) => {
    const panel = document.createElement("section");
    panel.className = "review-os-result-panel";
    panel.dataset.ceOsPanel = "true";
    panel.dataset.reviewResultStep = String(index);
    item.nodes.forEach((node) => panel.append(node));
    panels.append(panel);
  });
  article.append(shell);
  const footer = q(".review-os-result-footer", shell);
  const show = (index) => setActivePanel(panels, index, {
    nav,
    memoryKey: "reviewResultStep",
    onChange(current, total, panel) {
      q("[data-review-result-position]", footer).textContent = `${current + 1} / ${total}`;
      q("[data-review-result-prev]", footer).disabled = current <= 0;
      q("[data-review-result-next]", footer).disabled = current >= total - 1;
      q("[data-review-os-current-title]", page).textContent = panelLabel(panel, panelNodes[current]?.label || "Результат");
    },
  });
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-os-panel-index]") : null;
    if (button) show(Number(button.dataset.ceOsPanelIndex));
  });
  footer.addEventListener("click", (event) => {
    const current = qa(":scope > [data-ce-os-panel]", panels).findIndex((panel) => panel.classList.contains("is-active"));
    if (event.target instanceof Element && event.target.closest("[data-review-result-prev]")) show(current - 1);
    if (event.target instanceof Element && event.target.closest("[data-review-result-next]")) show(current + 1);
  });
  show(Math.min(Number(runtime.memory.reviewResultStep) || 0, panelNodes.length - 1));
}

function mountReviewDesktop() {
  const page = q(".content-review-page");
  if (!page || routePath() !== REVIEW_ROUTE) {
    runtime.reviewPage = null;
    document.body.classList.remove("contentengine-review-os-open");
    return;
  }
  runtime.reviewPage = page;
  document.body.classList.add("contentengine-review-os-open");
  page.classList.add("review-desktop-os");
  const layout = q(":scope > .content-review-layout", page);
  let topbar = q(":scope > .review-os-topbar", page);
  if (!topbar) {
    topbar = elementFrom(`
      <header class="review-os-topbar">
        <div class="review-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
        <div class="review-os-title"><small>ContentEngine · Проверка</small><strong data-review-os-current-title>Рабочий стол проверки</strong></div>
        <div class="review-os-mode-switch" role="group" aria-label="Рабочие пространства проверки">
          <button type="button" data-review-os-mode="result">Текущая проверка</button>
          <button type="button" data-review-os-mode="new">Новая проверка</button>
          <button type="button" data-review-os-mode="history">История</button>
        </div>
        <button class="review-os-mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 19)}</button>
      </header>`);
    (q(":scope > .content-review-hero", page) || layout)?.before(topbar);
  }
  let workbench = q(":scope > .review-os-workbench", page);
  if (!workbench && layout) {
    workbench = elementFrom(`
      <section class="review-os-workbench" aria-label="Рабочий стол проверки">
        <div class="review-os-progress" aria-hidden="true"><span></span></div>
        <div class="review-os-space review-os-space--result" data-review-os-space="result"></div>
        <div class="review-os-space review-os-space--new" data-review-os-space="new"></div>
        <div class="review-os-space review-os-space--history" data-review-os-space="history"></div>
      </section>`);
    layout.before(workbench);
    const form = q(".content-review-form", layout);
    const output = q(".content-review-output", layout);
    if (form) q('[data-review-os-space="new"]', workbench).append(form);
    if (output) q('[data-review-os-space="result"]', workbench).append(output);
    const history = qa(":scope > *", page).find((node) => /history/i.test(String(node.className || "")) && node !== workbench);
    if (history) q('[data-review-os-space="history"]', workbench).append(history);
    else q('[data-review-os-space="history"]', workbench).innerHTML = '<div class="review-os-empty"><strong>История проверок появится здесь</strong><p>После первой завершённой проверки можно будет вернуться к предыдущим решениям.</p></div>';
    qa(":scope > .content-review-message", page).forEach((message) => q('[data-review-os-space="result"]', workbench).prepend(message));
    layout.remove();
  }
  if (!workbench) return;
  const resultSpace = q('[data-review-os-space="result"]', workbench);
  const newSpace = q('[data-review-os-space="new"]', workbench);
  const historySpace = q('[data-review-os-space="history"]', workbench);
  const resultAvailable = Boolean(q(".content-review-result, .content-review-progress, .content-review-failed", resultSpace));
  q('[data-review-os-mode="result"]', topbar).disabled = !resultAvailable;
  q('[data-review-os-mode="history"]', topbar).disabled = !historySpace?.children.length;
  setupReviewForm(q("#content-review-form", newSpace), page);
  setupReviewResult(q(".content-review-result", resultSpace), page);
  if (topbar.dataset.reviewOsBound !== "true") {
    topbar.dataset.reviewOsBound = "true";
    topbar.addEventListener("click", (event) => {
      const button = event.target instanceof Element ? event.target.closest("[data-review-os-mode]") : null;
      if (!button || button.disabled) return;
      setReviewMode(page, button.dataset.reviewOsMode, true);
    });
  }
  const preferred = runtime.memory.reviewMode;
  setReviewMode(page, preferred === "result" && !resultAvailable ? "new" : preferred || (resultAvailable ? "result" : "new"));
}

function academyHomeGroups(page) {
  const children = [...page.children].filter((node) => !node.classList.contains("academy-os-window"));
  const groups = [
    { key: "today", label: "Сегодня", icon: "home", nodes: [] },
    { key: "courses", label: "Курсы", icon: "course", nodes: [] },
    { key: "practice", label: "Практика", icon: "practice", nodes: [] },
    { key: "map", label: "Карта работы", icon: "map", nodes: [] },
    { key: "extras", label: "Достижения", icon: "trophy", nodes: [] },
  ];
  let pendingHeading = null;
  children.forEach((node) => {
    const cls = String(node.className || "");
    if (/learning-section-heading/.test(cls)) {
      pendingHeading = node;
      return;
    }
    let target = groups[4];
    if (/learning-hero|learning-now|learning-track/.test(cls)) target = groups[0];
    else if (/course-grid/.test(cls)) target = groups[1];
    else if (/training-practical-card|premium-exam-card/.test(cls)) target = groups[2];
    else if (/work-map|learning-safety/.test(cls)) target = groups[3];
    else if (/training-achievement/.test(cls)) target = groups[4];
    if (pendingHeading) {
      target.nodes.push(pendingHeading);
      pendingHeading = null;
    }
    target.nodes.push(node);
  });
  if (pendingHeading) groups[4].nodes.push(pendingHeading);
  return groups.filter((group) => group.nodes.length);
}

function setupAcademyHome(page) {
  if (page.dataset.academyOsReady === "true") return;
  page.dataset.academyOsReady = "true";
  page.classList.add("academy-desktop-os");
  const groups = academyHomeGroups(page);
  const windowEl = elementFrom(`
    <section class="academy-os-window" aria-label="Академия ContentEngine">
      <header class="academy-os-topbar">
        <div class="review-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
        <div><small>ContentEngine Academy</small><strong data-academy-os-title>Ваш рабочий маршрут</strong></div>
        <button type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 19)}</button>
      </header>
      <div class="academy-os-panels"></div>
      <nav class="academy-os-dock" aria-label="Разделы академии"></nav>
    </section>`);
  const panels = q(".academy-os-panels", windowEl);
  const nav = q(".academy-os-dock", windowEl);
  groups.forEach((group, index) => {
    const panel = document.createElement("section");
    panel.className = `academy-os-panel academy-os-panel--${group.key}`;
    panel.dataset.ceOsPanel = "true";
    panel.dataset.academyOsKey = group.key;
    group.nodes.forEach((node) => panel.append(node));
    panels.append(panel);
    nav.insertAdjacentHTML("beforeend", `
      <button type="button" data-ce-os-panel-index="${index}" aria-label="${escapeMarkup(group.label)}">
        <span>${icon(group.icon, 20)}</span><small>${escapeMarkup(group.label)}</small>
      </button>`);
  });
  page.append(windowEl);
  const show = (index) => setActivePanel(panels, index, {
    nav,
    memoryKey: "academyHomeStep",
    onChange(current, total, panel) {
      const group = groups[current];
      q("[data-academy-os-title]", windowEl).textContent = group?.label || panelLabel(panel, "Академия");
      windowEl.style.setProperty("--academy-os-progress", `${((current + 1) / total) * 100}%`);
    },
  });
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-os-panel-index]") : null;
    if (button) show(Number(button.dataset.ceOsPanelIndex));
  });
  show(Math.min(Number(runtime.memory.academyHomeStep) || 0, groups.length - 1));
}

function setupAcademyCourse(page) {
  if (page.dataset.academyCourseOsReady === "true") return;
  const lessons = qa('[id^="lesson-"], .lesson-card, .course-lesson, .lesson-section', page)
    .filter((node) => !node.closest("[data-training-platform-simulators]") && node.parentElement);
  if (lessons.length < 2) {
    page.classList.add("academy-course-desktop-os", "academy-course-desktop-os--single");
    page.dataset.academyCourseOsReady = "true";
    return;
  }
  page.dataset.academyCourseOsReady = "true";
  page.classList.add("academy-course-desktop-os");
  const host = elementFrom(`
    <section class="academy-course-os-window">
      <header class="academy-os-topbar"><div class="review-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div><div><small>Курс</small><strong data-academy-course-title>Урок</strong></div><span data-academy-course-position></span></header>
      <div class="academy-course-os-panels"></div>
      <nav class="academy-course-os-dock" aria-label="Уроки курса"></nav>
    </section>`);
  const panels = q(".academy-course-os-panels", host);
  const nav = q(".academy-course-os-dock", host);
  lessons.forEach((lesson, index) => {
    lesson.dataset.ceOsPanel = "true";
    lesson.classList.add("academy-course-os-panel");
    panels.append(lesson);
    nav.insertAdjacentHTML("beforeend", `<button type="button" data-ce-os-panel-index="${index}" aria-label="${escapeMarkup(panelLabel(lesson, `Урок ${index + 1}`))}"><span>${index + 1}</span><small>${escapeMarkup(panelLabel(lesson, `Урок ${index + 1}`))}</small></button>`);
  });
  page.append(host);
  const show = (index) => setActivePanel(panels, index, {
    nav,
    memoryKey: `academyCourseStep:${routePath()}`,
    onChange(current, total, panel) {
      q("[data-academy-course-title]", host).textContent = panelLabel(panel, `Урок ${current + 1}`);
      q("[data-academy-course-position]", host).textContent = `${current + 1} / ${total}`;
    },
  });
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-os-panel-index]") : null;
    if (button) show(Number(button.dataset.ceOsPanelIndex));
  });
  show(Math.min(Number(runtime.memory[`academyCourseStep:${routePath()}`]) || 0, lessons.length - 1));
}

function mountAcademyDesktop() {
  const path = routePath();
  const page = q(".learning-page");
  if (!page || !path.startsWith(LEARN_ROUTE)) {
    runtime.academyPage = null;
    document.body.classList.remove("contentengine-academy-os-open");
    return;
  }
  runtime.academyPage = page;
  document.body.classList.add("contentengine-academy-os-open");
  if (path === LEARN_ROUTE && !page.classList.contains("course-page")) setupAcademyHome(page);
  else setupAcademyCourse(page);
}

function handleGlobalClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-ce-open-mission]")) {
    event.preventDefault();
    q('[data-deck-action="overview"]')?.click();
  }
}

function handleGlobalKeydown(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest(INTERACTIVE_SELECTOR)) return;
  if (routePath() === REVIEW_ROUTE && runtime.reviewPage) {
    if (event.key === "1" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); setReviewMode(runtime.reviewPage, "result", true); }
    if (event.key === "2" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); setReviewMode(runtime.reviewPage, "new", true); }
    if (event.key === "3" && (event.metaKey || event.ctrlKey)) { event.preventDefault(); setReviewMode(runtime.reviewPage, "history", true); }
  }
}

function mount() {
  runtime.route = routePath();
  const shell = q(".workspace-shell");
  mountMacDock(shell);
  mountReviewDesktop();
  mountAcademyDesktop();
}

const observer = new MutationObserver(scheduleMount);
observer.observe(q("#app") || document.body, { childList: true, subtree: true });
document.addEventListener("click", handleGlobalClick, true);
document.addEventListener("keydown", handleGlobalKeydown, true);
document.addEventListener("pointermove", handleDockPointerMove, { passive: true });
document.addEventListener("pointerout", (event) => {
  const from = event.target instanceof Element ? event.target.closest(".ce-mac-dock__glass") : null;
  const to = event.relatedTarget instanceof Element ? event.relatedTarget.closest(".ce-mac-dock__glass") : null;
  if (from && from !== to) resetDockMagnification();
}, { passive: true });
window.addEventListener("hashchange", scheduleMount, { passive: true });
REDUCED_MOTION.addEventListener?.("change", resetDockMagnification);
scheduleMount();
