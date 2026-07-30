/*
 * ContentEngine Generation Desktop OS.
 * Re-composes the existing generation DOM into one-step workspaces without
 * cloning forms, reading field values or calling business APIs.
 */

const GENERATION_ROUTE = "/workspace/generation";
const STATE_KEY = "contentengine.generation-os.v2";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const INTERACTIVE = "input, textarea, select, button, a, video, audio, [contenteditable='true']";

const STEPS = Object.freeze([
  { key: "mode", label: "Режим и бюджет", hint: "Выберите модель, кампанию и безопасный лимит запуска.", icon: "spark" },
  { key: "product", label: "Точный товар", hint: "Зафиксируйте артикул, название и категорию без догадок.", icon: "box" },
  { key: "destination", label: "Площадка и команда", hint: "Куда пойдёт результат, кто отвечает и сколько вариантов нужно.", icon: "route" },
  { key: "brief", label: "Замысел", hint: "Сценарий, движение, роль товара и ограничения результата.", icon: "script" },
  { key: "media", label: "Исходники", hint: "Выберите точные ракурсы одного товара и главное фото.", icon: "media" },
  { key: "launch", label: "Проверка и запуск", hint: "Последняя сверка перед dry-run или платным созданием.", icon: "launch" },
]);

const ICONS = Object.freeze({
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m5.6 5.6 2.8 2.8m7.2 7.2 2.8 2.8m0-12.8-2.8 2.8m-7.2 7.2-2.8 2.8"/><circle cx="12" cy="12" r="3"/>',
  box: '<path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/>',
  route: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h3a3 3 0 0 0 3-3V9a3 3 0 0 1 3-3"/>',
  script: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  media: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 16 3.5-4 3 3 2-2 2.5 3"/><circle cx="8" cy="8.5" r="1.3"/>',
  launch: '<path d="M14 4c3 1 5 3 6 6l-6 6-6-6 6-6Z"/><path d="m8 10-3 2-1 4 4-1M14 16l-2 3-4 1 1-4M13 7l4 4"/>',
  queue: '<path d="M5 7h14M5 12h14M5 17h9"/><circle cx="3" cy="7" r=".7"/><circle cx="3" cy="12" r=".7"/><circle cx="3" cy="17" r=".7"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6M12 7v5l3 2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.1-1.1"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
});

const runtime = {
  queued: false,
  page: null,
  mode: "launch",
  step: 0,
  topbar: null,
  workbench: null,
  form: null,
  panels: [],
  nav: null,
  footer: null,
  observer: null,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.grid}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function compact(value, limit = 68) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function readMemory() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(STATE_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function remember(patch) {
  const next = { ...readMemory(), ...patch };
  try { window.sessionStorage.setItem(STATE_KEY, JSON.stringify(next)); } catch { /* optional */ }
}

function animateSwap(outgoing, incoming, direction = 1) {
  if (!incoming || REDUCED_MOTION.matches || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 48}px,0,0) scale(.982)`, filter: "blur(2px)" },
  ], { duration: 190, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 72}px,0,0) scale(.97)`, filter: "blur(7px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.006)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 560, easing: SPRING });
}

function setBodyState(active) {
  document.body.classList.toggle("contentengine-generation-os-open", active);
}

function clearRuntime() {
  runtime.page = null;
  runtime.topbar = null;
  runtime.workbench = null;
  runtime.form = null;
  runtime.panels = [];
  runtime.nav = null;
  runtime.footer = null;
  setBodyState(false);
}

function modeOrder(mode) {
  return ["launch", "queue", "aliases"].indexOf(mode);
}

function setMode(mode, { focus = false } = {}) {
  const page = runtime.page;
  if (!page) return;
  const available = qa("[data-generation-os-mode]", page)
    .filter((button) => !button.disabled)
    .map((button) => button.dataset.generationOsMode);
  const resolved = available.includes(mode) ? mode : available[0] || "launch";
  const previous = runtime.mode;
  const outgoing = q(`[data-generation-os-space="${CSS.escape(previous)}"]`, page);
  const incoming = q(`[data-generation-os-space="${CSS.escape(resolved)}"]`, page);

  runtime.mode = resolved;
  page.dataset.generationOsMode = resolved;
  qa("[data-generation-os-mode]", page).forEach((button) => {
    const active = button.dataset.generationOsMode === resolved;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  qa("[data-generation-os-space]", page).forEach((space) => {
    const active = space.dataset.generationOsSpace === resolved;
    space.classList.toggle("is-active", active);
    space.setAttribute("aria-hidden", active ? "false" : "true");
    space.inert = !active;
  });
  if (previous !== resolved) animateSwap(outgoing, incoming, modeOrder(resolved) >= modeOrder(previous) ? 1 : -1);
  remember({ mode: resolved });
  if (focus) q("button, a, input, select, textarea", incoming)?.focus({ preventScroll: true });
}

function nodeContains(node, selector) {
  return node.matches?.(selector) || Boolean(node.querySelector?.(selector));
}

function stepForNode(node, currentKey) {
  if (node.id === "generation-draft-status") return "status";
  if (
    nodeContains(node, '[name="generation_mode"], [name="duration_seconds"], [name="campaign_id"], [name="real_spend_confirmation"]')
    || node.matches?.("#generation-duration-field, #generation-mock-explanation, #generation-campaign-field, #real-generation-confirmation")
    || /generation-readiness|generation-spend|generation-model/i.test(String(node.className || ""))
  ) return "mode";
  if (nodeContains(node, '[name="sku"], [name="product_name"], [name="product_category"]') || node.id === "generation-product-identity-note") return "product";
  if (nodeContains(node, '[name="platform"], [name="destination_ref"], [name="assignee_id"], [name="payout_rub"], [name="count"], [name="format"]')) return "destination";
  if (nodeContains(node, '[name="brief"]') || node.id === "generation-brief-assist" || /generation-learning|generation-repair|brief-assist/i.test(String(node.className || ""))) return "brief";
  if (nodeContains(node, '[name="media_id"], [name="primary_media_id"]')) return "media";
  if (nodeContains(node, "#generation-submit, button[type='submit']")) return "launch";
  return currentKey;
}

function panelHasInvalidRequired(panel) {
  return qa(":is(input, select, textarea)[required]:not(:disabled)", panel).some((control) => {
    if (control.closest("[hidden]")) return false;
    return typeof control.checkValidity === "function" && !control.checkValidity();
  });
}

function updateStepCompletion() {
  runtime.panels.forEach((panel, index) => {
    const button = q(`[data-generation-step-index="${index}"]`, runtime.nav);
    button?.classList.toggle("is-complete", !panelHasInvalidRequired(panel));
  });
}

function updateStepChrome(index) {
  const total = runtime.panels.length;
  const step = STEPS[index] || STEPS.at(-1);
  runtime.page?.style.setProperty("--generation-os-progress", `${((index + 1) / Math.max(1, total)) * 100}%`);
  const title = q("[data-generation-os-title]", runtime.topbar);
  if (title) title.textContent = step?.label || "Новый запуск";
  const position = q("[data-generation-step-position]", runtime.footer);
  if (position) position.textContent = `${index + 1} / ${total}`;
  const previous = q("[data-generation-step-prev]", runtime.footer);
  const next = q("[data-generation-step-next]", runtime.footer);
  if (previous) previous.disabled = index <= 0;
  if (next) next.hidden = index >= total - 1;
  updateStepCompletion();
}

function setStep(index, { focus = false, validateCurrent = false } = {}) {
  if (!runtime.form || !runtime.panels.length) return;
  const nextIndex = Math.max(0, Math.min(runtime.panels.length - 1, Number(index) || 0));
  const current = runtime.panels.findIndex((panel) => panel.classList.contains("is-active"));
  if (validateCurrent && nextIndex > current && current >= 0 && panelHasInvalidRequired(runtime.panels[current])) {
    const invalid = qa(":is(input, select, textarea)[required]:not(:disabled)", runtime.panels[current])
      .find((control) => !control.closest("[hidden]") && !control.checkValidity());
    invalid?.reportValidity?.();
    invalid?.focus?.({ preventScroll: false });
    return;
  }
  const outgoing = runtime.panels[current];
  const incoming = runtime.panels[nextIndex];
  runtime.panels.forEach((panel, panelIndex) => {
    const active = panelIndex === nextIndex;
    panel.classList.toggle("is-active", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
    panel.inert = !active;
  });
  qa("[data-generation-step-index]", runtime.nav).forEach((button) => {
    const active = Number(button.dataset.generationStepIndex) === nextIndex;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "step" : "false");
  });
  if (current !== nextIndex) animateSwap(outgoing, incoming, nextIndex >= current ? 1 : -1);
  runtime.step = nextIndex;
  remember({ step: nextIndex });
  updateStepChrome(nextIndex);
  if (focus) q(INTERACTIVE, incoming)?.focus({ preventScroll: true });
}

function buildLaunchContext(card, form) {
  let details = q(":scope > .generation-os-system-context", card);
  if (details) return details;
  const children = [...card.children];
  const formIndex = children.indexOf(form);
  const contextNodes = formIndex > 0 ? children.slice(0, formIndex) : [];
  details = elementFrom(`
    <details class="generation-os-system-context">
      <summary>${icon("spark", 17)}<span><strong>Модель, бюджет и системные ограничения</strong><small>Открывайте, когда нужно проверить лимит или источник задания.</small></span></summary>
      <div class="generation-os-system-context__body"></div>
    </details>`);
  const body = q(".generation-os-system-context__body", details);
  contextNodes.forEach((node) => body.append(node));
  card.prepend(details);
  return details;
}

function setupLaunchForm(form) {
  if (!form || form.dataset.generationOsReady === "true") return;
  form.dataset.generationOsReady = "true";
  form.classList.add("generation-os-form");
  runtime.form = form;

  const original = [...form.children];
  const status = original.find((node) => node.id === "generation-draft-status");
  const shell = elementFrom(`
    <div class="generation-os-form-shell">
      <header class="generation-os-form-head">
        <div><p>НОВЫЙ ЗАПУСК</p><h2>Один шаг — один рабочий стол</h2></div>
        <span data-generation-form-status></span>
      </header>
      <div class="generation-os-form-body">
        <nav class="generation-os-step-dock" aria-label="Этапы запуска"></nav>
        <div class="generation-os-panels"></div>
      </div>
      <footer class="generation-os-footer">
        <button type="button" data-generation-step-prev>${icon("left", 18)}<span>Назад</span></button>
        <div><small>Этап</small><strong data-generation-step-position>1 / ${STEPS.length}</strong></div>
        <button type="button" data-generation-step-next><span>Далее</span>${icon("right", 18)}</button>
      </footer>
    </div>`);
  const nav = q(".generation-os-step-dock", shell);
  const panelsHost = q(".generation-os-panels", shell);
  const statusHost = q("[data-generation-form-status]", shell);
  if (status) statusHost.append(status);

  const groups = new Map();
  STEPS.forEach((step, index) => {
    const panel = elementFrom(`
      <section class="generation-os-panel" data-generation-step="${step.key}" data-generation-step-index="${index}">
        <header><span>${String(index + 1).padStart(2, "0")}</span><div><p>${step.label}</p><small>${step.hint}</small></div></header>
        <div class="generation-os-panel__content"></div>
      </section>`);
    panelsHost.append(panel);
    groups.set(step.key, q(".generation-os-panel__content", panel));
  });

  let currentKey = "mode";
  original.forEach((node) => {
    if (node === status) return;
    const detected = stepForNode(node, currentKey);
    if (detected !== "status") currentKey = detected;
    (groups.get(currentKey) || groups.get("mode")).append(node);
  });

  nav.innerHTML = STEPS.map((step, index) => `
    <button type="button" data-generation-step-index="${index}" aria-label="${step.label}">
      <span>${icon(step.icon, 18)}</span><small>${step.label}</small><i aria-hidden="true"></i>
    </button>`).join("");

  form.append(shell);
  runtime.panels = qa(":scope > .generation-os-panel", panelsHost);
  runtime.nav = nav;
  runtime.footer = q(".generation-os-footer", shell);

  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-generation-step-index]") : null;
    if (button) setStep(Number(button.dataset.generationStepIndex), { focus: true });
  });
  runtime.footer.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("[data-generation-step-prev]")) setStep(runtime.step - 1, { focus: true });
    if (event.target.closest("[data-generation-step-next]")) setStep(runtime.step + 1, { focus: true, validateCurrent: true });
  });
  form.addEventListener("input", updateStepCompletion);
  form.addEventListener("change", () => window.setTimeout(updateStepCompletion, 0));

  const memory = readMemory();
  setStep(Math.min(Number(memory.step) || 0, runtime.panels.length - 1));
}

function setupLaunchCard(card) {
  if (!card) return;
  card.classList.add("generation-os-launch-card");
  const form = q("#mock-batch-form", card);
  if (!form) return;
  buildLaunchContext(card, form);
  setupLaunchForm(form);
  const repeat = q(":scope > .generation-repeat-panel", card);
  if (repeat) q('[data-generation-step="launch"] .generation-os-panel__content', form)?.append(repeat);
}

function setupArchive(card) {
  if (!card || card.dataset.generationArchiveOsReady === "true") return;
  card.dataset.generationArchiveOsReady = "true";
  card.classList.add("generation-os-archive-card");
  const filter = q("#generation-archive-filter-form", card);
  if (!filter) return;
  const quick = elementFrom(`
    <div class="generation-os-queue-quick" role="group" aria-label="Быстрый фильтр очереди">
      <button type="button" data-generation-queue-status="active">${icon("queue", 16)}Создаются</button>
      <button type="button" data-generation-queue-status="ready">Готовые</button>
      <button type="button" data-generation-queue-status="issue">Проблемы</button>
      <button type="button" data-generation-queue-status="all">Все</button>
    </div>`);
  filter.before(quick);
  quick.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-generation-queue-status]") : null;
    if (!button) return;
    const select = q('select[name="status"]', filter);
    if (!select) return;
    select.value = button.dataset.generationQueueStatus;
    filter.requestSubmit?.();
  });
}

function findAliasSection(page) {
  return [...page.children].find((node) => {
    if (!(node instanceof HTMLElement) || !node.matches("section")) return false;
    return Boolean(q("#wb-alias-form", node)) || /Артикулы Wildberries/iu.test(node.textContent || "");
  }) || null;
}

function createTopbar() {
  return elementFrom(`
    <header class="generation-os-topbar">
      <div class="generation-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="generation-os-title"><small>ContentEngine · Генерация</small><strong data-generation-os-title>Новый запуск</strong></div>
      <div class="generation-os-mode-switch" role="group" aria-label="Рабочие пространства генерации">
        <button type="button" data-generation-os-mode="launch">Новый запуск</button>
        <button type="button" data-generation-os-mode="queue">Очередь и архив</button>
        <button type="button" data-generation-os-mode="aliases">Артикулы</button>
      </div>
      <button class="generation-os-mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 19)}</button>
    </header>`);
}

function createWorkbench() {
  return elementFrom(`
    <section class="generation-os-workbench" aria-label="Рабочий стол генерации">
      <div class="generation-os-progress" aria-hidden="true"><span></span></div>
      <div class="generation-os-space" data-generation-os-space="launch"></div>
      <div class="generation-os-space" data-generation-os-space="queue"></div>
      <div class="generation-os-space" data-generation-os-space="aliases"></div>
    </section>`);
}

function mountGeneration() {
  if (routePath() !== GENERATION_ROUTE) {
    clearRuntime();
    return;
  }
  const form = q("#mock-batch-form");
  const page = form?.closest?.(".page-wrap");
  if (!page) {
    clearRuntime();
    return;
  }
  if (page.dataset.generationDesktopOs === "true") {
    runtime.page = page;
    setBodyState(true);
    return;
  }

  page.dataset.generationDesktopOs = "true";
  page.classList.add("generation-desktop-os");
  runtime.page = page;
  setBodyState(true);

  const layout = q(":scope > .generation-workspace-layout", page);
  const launch = q(".generation-launch-card", layout || page);
  const archive = q(".generation-archive-card", layout || page);
  const aliases = findAliasSection(page);
  const topbar = createTopbar();
  const workbench = createWorkbench();
  const anchor = q(":scope > .page-header", page) || layout || page.firstElementChild;
  anchor?.after?.(topbar, workbench);
  runtime.topbar = topbar;
  runtime.workbench = workbench;

  if (launch) q('[data-generation-os-space="launch"]', workbench).append(launch);
  if (archive) q('[data-generation-os-space="queue"]', workbench).append(archive);
  const aliasSpace = q('[data-generation-os-space="aliases"]', workbench);
  if (aliases) aliasSpace.append(aliases);
  else aliasSpace.innerHTML = '<div class="generation-os-empty"><strong>Связи артикулов не требуются для вашей роли</strong><p>Если руководитель добавит подтверждённый подменный артикул, он появится в этом пространстве.</p></div>';
  layout?.remove();

  setupLaunchCard(launch);
  setupArchive(archive);

  q('[data-generation-os-mode="aliases"]', topbar).disabled = !aliases;
  topbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-generation-os-mode]") : null;
    if (button && !button.disabled) setMode(button.dataset.generationOsMode, { focus: true });
  });

  const memory = readMemory();
  setMode(String(memory.mode || "launch"));
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mountGeneration();
  });
}

function handleKeydown(event) {
  if (!runtime.page || routePath() !== GENERATION_ROUTE) return;
  const target = event.target instanceof Element ? event.target : null;
  const editing = target?.matches?.("input, textarea, select, [contenteditable='true']");
  if (editing || !event.altKey || event.shiftKey || event.metaKey || event.ctrlKey) return;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    setStep(runtime.step - 1, { focus: true });
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    setStep(runtime.step + 1, { focus: true, validateCurrent: true });
  }
}

runtime.observer = new MutationObserver(scheduleMount);
runtime.observer.observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleKeydown);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
