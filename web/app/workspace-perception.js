/*
 * ContentEngine perception pass.
 * Progressive presentation layer: semantic Mission Control previews, a single
 * "Now" action, unified SVG controls, density preferences, auto-hide Dock,
 * truthful form feedback and shared-element opening motion.
 *
 * This module never calls application APIs and never reads or stores form
 * values. Existing routes, permissions, forms and business logic remain the
 * source of truth.
 */

const PERCEPTION_DENSITY_KEY = "contentengine.perception.density.v1";
const PERCEPTION_COACH_KEY = "contentengine.perception.coach.v1";
const PRODUCTIVITY_STORAGE_KEY = "contentengine.workspace-productivity.v1";
const ROUTE_PREFIXES = ["/workspace/", "/learn"];
const DENSITY_ORDER = ["calm", "work", "dense"];
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const SECRET_FIELD_PATTERN = /(password|secret|token|api.?key|otp|one.?time|authorization|credential)/i;

const ICON_PATHS = {
  overview: '<rect x="3" y="4" width="7" height="6" rx="1.5"/><rect x="14" y="4" width="7" height="6" rx="1.5"/><rect x="3" y="14" width="7" height="6" rx="1.5"/><rect x="14" y="14" width="7" height="6" rx="1.5"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/><path d="m3 8 6-6M21 8l-6-6M3 16l6 6M21 16l-6 6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  arrowLeft: '<path d="m15 18-6-6 6-6"/>',
  arrowRight: '<path d="m9 18 6-6-6-6"/>',
  arrowUpRight: '<path d="M7 17 17 7M8 7h9v9"/>',
  pin: '<path d="m9 4 6 0 1 5 3 3H5l3-3 1-5Z"/><path d="M12 12v9"/>',
  unpin: '<path d="M6 3 21 18M9 4h6l1 5 3 3H9M12 15v6"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M14 4v16M6.5 8h4M6.5 12h4M6.5 16h3"/>',
  copy: '<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  stack: '<rect x="4" y="5" width="16" height="14" rx="3"/><path d="M8 2h8M8 22h8"/>',
  layout: '<rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16M9 10h12"/>',
  play: '<path d="m9 7 8 5-8 5V7Z"/>',
  pause: '<path d="M9 7v10M15 7v10"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  alert: '<path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  loader: '<path d="M20 12a8 8 0 1 1-2.34-5.66"/>',
  file: '<path d="M7 3h7l4 4v14H7V3Z"/><path d="M14 3v5h5"/>',
  folder: '<path d="M3 7h7l2 2h9v10H3V7Z"/>',
  spark: '<path d="m12 3 1.4 4.6L18 9l-4.6 1.4L12 15l-1.4-4.6L6 9l4.6-1.4L12 3Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>',
  review: '<rect x="4" y="3" width="16" height="18" rx="2.5"/><path d="M8 8h8M8 12h5M8 16h4"/><path d="m15 16 1.5 1.5L20 14"/>',
  chart: '<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>',
  wallet: '<path d="M4 6h14v14H4V6Z"/><path d="M4 9h16v8h-5a3 3 0 0 1 0-6h5M15 14h.01"/>',
  academy: '<path d="m3 9 9-5 9 5-9 5-9-5Z"/><path d="M7 12v5c3 2 7 2 10 0v-5M21 9v6"/>',
  home: '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/>',
  task: '<rect x="5" y="3" width="14" height="18" rx="2.5"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  density: '<path d="M4 6h16M4 12h16M4 18h16"/><path d="M7 4v4M12 10v4M17 16v4"/>',
  chevronUp: '<path d="m7 14 5-5 5 5"/>',
  chevronDown: '<path d="m7 10 5 5 5-5"/>',
  pencil: '<path d="m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z"/><path d="m13.5 7 3.5 3.5"/>',
};

const runtime = {
  mountQueued: false,
  pointerFrame: 0,
  pointerEvent: null,
  dockHideTimer: 0,
  sharedSource: null,
  coachTimer: 0,
};

const q = (selector, root = document) => root?.querySelector?.(selector) || null;
const qa = (selector, root = document) => [...(root?.querySelectorAll?.(selector) || [])];

function storage(type = "local") {
  try { return type === "session" ? window.sessionStorage : window.localStorage; } catch { return null; }
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?")[0] || "/";
  return (`/${path}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function isWorkspaceRoute(route = routePath()) {
  return ROUTE_PREFIXES.some((prefix) => String(route || "").startsWith(prefix));
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compact(value, limit = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function icon(name, size = 18) {
  const paths = ICON_PATHS[name] || ICON_PATHS.info;
  return `<svg class="workspace-system-icon" width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function announce(message) {
  let region = q(".workspace-perception-live-region");
  if (!region) {
    region = elementFrom('<div class="workspace-perception-live-region" aria-live="polite" aria-atomic="true"></div>');
    document.body.append(region);
  }
  region.textContent = "";
  window.setTimeout(() => { region.textContent = String(message || ""); }, 24);
}

function densityMode() {
  const value = storage("local")?.getItem(PERCEPTION_DENSITY_KEY) || "work";
  return DENSITY_ORDER.includes(value) ? value : "work";
}

function densityLabel(mode = densityMode()) {
  return { calm: "Спокойно", work: "Рабоче", dense: "Плотно" }[mode] || "Рабоче";
}

function applyDensity(mode = densityMode(), persist = false) {
  const next = DENSITY_ORDER.includes(mode) ? mode : "work";
  document.documentElement.dataset.workspaceDensity = next;
  if (persist) {
    try { storage("local")?.setItem(PERCEPTION_DENSITY_KEY, next); } catch { /* optional preference */ }
  }
  qa("[data-perception-density]").forEach((button) => {
    button.dataset.mode = next;
    button.setAttribute("aria-label", `Плотность интерфейса: ${densityLabel(next)}. Нажмите, чтобы изменить.`);
    const label = q(".workspace-perception-density__label", button);
    if (label) label.textContent = densityLabel(next);
  });
}

function cycleDensity() {
  const current = densityMode();
  const next = DENSITY_ORDER[(DENSITY_ORDER.indexOf(current) + 1) % DENSITY_ORDER.length];
  applyDensity(next, true);
  announce(`Плотность интерфейса: ${densityLabel(next)}`);
}

function ensureDensityControl() {
  const actions = q(".workspace-deck-actions");
  if (!actions || q("[data-perception-density]", actions)) return;
  const button = elementFrom(`
    <button class="workspace-deck-action workspace-perception-density" type="button" data-perception-density data-mode="${escapeMarkup(densityMode())}" aria-label="Плотность интерфейса: ${escapeMarkup(densityLabel())}. Нажмите, чтобы изменить.">
      <span class="workspace-deck-action__icon" aria-hidden="true">${icon("density", 17)}</span>
      <span class="workspace-perception-density__label">${escapeMarkup(densityLabel())}</span>
    </button>
  `);
  const palette = q('[data-deck-action="palette"]', actions);
  if (palette) actions.insertBefore(button, palette);
  else actions.append(button);
}

function setIconContainer(element, name, size = 18) {
  if (!(element instanceof Element)) return;
  const signature = `${name}:${size}`;
  if (element.dataset.perceptionIcon === signature) return;
  element.dataset.perceptionIcon = signature;
  element.innerHTML = icon(name, size);
}

function setIconOnlyButton(button, name, size = 18) {
  if (!(button instanceof HTMLButtonElement)) return;
  const signature = `${name}:${size}`;
  if (button.dataset.perceptionIconOnly === signature) return;
  button.dataset.perceptionIconOnly = signature;
  button.innerHTML = icon(name, size);
}

function setIconButtonPreserveChildren(button, name, size = 18, preserveText = false) {
  if (!(button instanceof HTMLButtonElement)) return;
  const signature = `${name}:${size}:${preserveText}`;
  if (button.dataset.perceptionIconPreserve === signature) return;
  button.dataset.perceptionIconPreserve = signature;
  const textNodes = [...button.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE);
  const directText = textNodes.map((node) => node.textContent || "").join(" " ).replace(/\s+/g, " " ).trim();
  textNodes.forEach((node) => node.remove());
  let glyph = q(":scope > .workspace-button-leading-icon", button);
  if (!glyph) {
    glyph = document.createElement("span");
    glyph.className = "workspace-button-leading-icon";
    glyph.setAttribute("aria-hidden", "true");
    button.prepend(glyph);
  }
  setIconContainer(glyph, name, size);
  if (preserveText && directText) {
    let label = q(":scope > .workspace-button-label", button);
    if (!label) {
      label = document.createElement("span");
      label.className = "workspace-button-label";
      glyph.insertAdjacentElement("afterend", label);
    }
    label.textContent = directText;
  }
}

function decorateIcons() {
  const containers = [
    ['[data-deck-action="overview"] .workspace-deck-action__icon', "overview", 17],
    ['[data-deck-action="focus"] .workspace-deck-action__icon', "expand", 17],
    ['[data-deck-action="palette"] .workspace-deck-action__icon', "search", 17],
    [".desk-focus-button__icon", "expand", 17],
    [".workspace-task-dock__mark", "stack", 17],
  ];
  containers.forEach(([selector, name, size]) => qa(selector).forEach((element) => setIconContainer(element, name, size)));

  qa(".workspace-deck-neighbor[data-deck-nav='-1'] .workspace-deck-neighbor__arrow").forEach((element) => setIconContainer(element, "arrowLeft", 18));
  qa(".workspace-deck-neighbor[data-deck-nav='1'] .workspace-deck-neighbor__arrow").forEach((element) => setIconContainer(element, "arrowRight", 18));
  qa(".workspace-task-carousel__button[data-task-desk-nav='-1'] > span").forEach((element) => setIconContainer(element, "arrowLeft", 16));
  qa(".workspace-task-carousel__button[data-task-desk-nav='1'] > span").forEach((element) => setIconContainer(element, "arrowRight", 16));

  const iconButtons = [
    ['.workspace-task-quick-action[data-productivity-context]', "panel", 16],
    ['.workspace-task-quick-action[data-productivity-pin]:not(.is-active)', "pin", 16],
    ['.workspace-task-quick-action[data-productivity-pin].is-active', "unpin", 16],
    ['.workspace-task-quick-action[data-productivity-park]:not(.is-parked)', "clock", 16],
    ['.workspace-task-quick-action[data-productivity-park].is-parked', "play", 16],
    ['.workspace-task-dock__open', "arrowUpRight", 17],
    ['.workspace-task-dock__actions [data-productivity-open-overview]', "overview", 18],
    ['.workspace-context-button--icon[data-productivity-copy]', "copy", 17],
    ['.workspace-overview__close', "close", 19],
    ['.workspace-context-panel__header [data-productivity-context-close]', "close", 18],
    ['.workspace-park-dialog header [data-productivity-park-close]', "close", 18],
  ];
  iconButtons.forEach(([selector, name, size]) => qa(selector).forEach((button) => setIconOnlyButton(button, name, size)));

  qa(".workspace-task-dock__actions [data-productivity-waiting]").forEach((button) => setIconButtonPreserveChildren(button, "clock", 18));
  qa(".workspace-context-panel__footer [data-productivity-open]").forEach((button) => setIconButtonPreserveChildren(button, "arrowRight", 16, true));
  qa(".workspace-context-panel__footer [data-productivity-pin]").forEach((button) => {
    const active = /откреп/i.test(button.textContent || "");
    setIconButtonPreserveChildren(button, active ? "unpin" : "pin", 16, true);
  });
  qa(".workspace-context-panel__footer [data-productivity-park]").forEach((button) => {
    const active = /вернуть/i.test(button.textContent || "");
    setIconButtonPreserveChildren(button, active ? "play" : "clock", 16, true);
  });

  qa(".workspace-focus-close").forEach((button) => {
    const first = button.firstElementChild;
    if (first) setIconContainer(first, "close", 17);
  });
}

function readProductivityMemory() {
  try {
    const parsed = JSON.parse(storage("session")?.getItem(PRODUCTIVITY_STORAGE_KEY) || "{}");
    return parsed?.tasks && typeof parsed.tasks === "object" ? Object.values(parsed.tasks) : [];
  } catch {
    return [];
  }
}

function taskTone(task) {
  if (task?.parked) {
    const returnAt = task.parked.returnAt ? new Date(task.parked.returnAt).getTime() : 0;
    if (returnAt && returnAt <= Date.now()) return "return";
    return "waiting";
  }
  return ["blocked", "waiting", "done", "draft"].includes(task?.status) ? task.status : "active";
}

function routeIcon(route) {
  const path = String(route || "").toLowerCase();
  if (path === "/workspace/home" || path.endsWith("/home")) return "home";
  if (/material|folder|source|library/.test(path)) return "folder";
  if (/research|product/.test(path)) return "search";
  if (/generat|create|content/.test(path)) return "spark";
  if (/review|check|moder/.test(path)) return "review";
  if (/task|work|board/.test(path)) return "task";
  if (/placement|publish|account/.test(path)) return "arrowUpRight";
  if (/result|analytic|report|metric/.test(path)) return "chart";
  if (/payout|pay|finance/.test(path)) return "wallet";
  if (path.startsWith("/learn")) return "academy";
  return "layout";
}

function toneLabel(tone) {
  return {
    blocked: "Требует решения",
    waiting: "В ожидании",
    return: "Пора вернуться",
    done: "Готово",
    draft: "Черновик",
    active: "В работе",
  }[tone] || "Рабочее пространство";
}

function tasksForRoute(route, tasks) {
  return tasks
    .filter((task) => String(task?.route || "").replace(/\/$/, "") === String(route || "").replace(/\/$/, ""))
    .sort((left, right) => Number(right?.updatedAt || 0) - Number(left?.updatedAt || 0));
}

function primaryTaskForRoute(route, tasks) {
  const matches = tasksForRoute(route, tasks);
  return matches.find((task) => task.pinned && !task.parked)
    || matches.find((task) => task.parked)
    || matches[0]
    || null;
}

function semanticPreviewMarkup(route, task, count, fallbackTitle, fallbackHint) {
  const tone = task ? taskTone(task) : "neutral";
  const title = compact(task?.title || fallbackTitle || "Рабочее пространство", 70);
  const status = task ? toneLabel(tone) : "Пространство готово";
  const hint = compact(
    task?.parked?.reason
      || task?.nextAction
      || task?.statusLabel
      || fallbackHint
      || "Откройте стол, чтобы продолжить работу.",
    86,
  );
  return `
    <span class="workspace-semantic-preview__icon" aria-hidden="true">${icon(routeIcon(route), 22)}</span>
    <span class="workspace-semantic-preview__copy">
      <small>${escapeMarkup(status)}</small>
      <strong>${escapeMarkup(title)}</strong>
      <em>${escapeMarkup(hint)}</em>
    </span>
    ${count ? `<span class="workspace-semantic-preview__count" aria-label="${count} активных задач">${count}</span>` : ""}
  `;
}

function decorateMissionControlPreviews() {
  const overlay = q(".workspace-overview");
  if (!overlay) return;
  const tasks = readProductivityMemory();
  qa("[data-overview-route]", overlay).forEach((card) => {
    const route = String(card.dataset.overviewRoute || "");
    const matches = tasksForRoute(route, tasks).filter((task) => task.pinned || task.parked || task.status === "blocked");
    const primary = primaryTaskForRoute(route, tasks);
    const preview = q(".workspace-overview-card__preview", card);
    if (!preview) return;
    const title = q(".workspace-overview-card__copy strong", card)?.textContent || "Рабочий стол";
    const hint = q(".workspace-overview-card__copy small", card)?.textContent || "";
    const signature = JSON.stringify([route, primary?.key || "", primary?.updatedAt || 0, matches.length, title, hint]);
    if (preview.dataset.perceptionPreview === signature) return;
    preview.dataset.perceptionPreview = signature;
    preview.classList.add("workspace-semantic-preview");
    preview.dataset.tone = primary ? taskTone(primary) : "neutral";
    preview.innerHTML = semanticPreviewMarkup(route, primary, matches.length, title, hint);
  });
}

function focusRoot() {
  return q("#workspace-content") || q(".learning-page") || q("#main-content");
}

function primarySurface(root = focusRoot()) {
  if (!root) return null;
  const surfaces = qa('[data-workspace-focusable="true"]', root).filter((surface) => surface.isConnected);
  return surfaces.find((surface) => surface.matches(".home-next-action, [data-workspace-primary]"))
    || surfaces.find((surface) => q("form", surface))
    || surfaces.find((surface) => !surface.closest(".workspace-perception-now"))
    || null;
}

function surfaceTitle(surface) {
  return compact(q("h1, h2, h3, legend, .card-header strong, strong", surface)?.textContent || "Рабочая задача", 100);
}

function surfaceHint(surface) {
  return compact(q("p:not(.eyebrow), .muted, .tiny, small", surface)?.textContent || "Откройте задачу и продолжите работу.", 180);
}

function surfaceStatus(surface) {
  const candidate = q("[data-status], .status-pill, .badge, .pill", surface);
  const text = compact(candidate?.dataset?.status || candidate?.textContent || "В работе", 60);
  const lowered = text.toLocaleLowerCase("ru-RU");
  if (/блок|ошиб|отклон|доработ|просроч/.test(lowered)) return { tone: "blocked", label: text };
  if (/жд[её]т|ожидан|очеред|обработ|генерац|провер/.test(lowered)) return { tone: "waiting", label: text };
  if (/готов|заверш|одобрен|выплачен/.test(lowered)) return { tone: "done", label: text };
  if (/чернов/.test(lowered)) return { tone: "draft", label: text };
  return { tone: "active", label: text || "В работе" };
}

function surfaceNextAction(surface) {
  const control = q(
    ".btn:not([disabled]):not([aria-disabled='true']), button:not([disabled]):not(.desk-focus-button):not(.workspace-task-quick-action), a.btn:not([aria-disabled='true'])",
    surface,
  );
  return compact(control?.textContent || "Открыть задачу", 90);
}

function markNativeNow(root) {
  const native = q(".home-next-action, .learning-now, [data-workspace-primary]", root);
  if (!native) return false;
  native.classList.add("workspace-now-native");
  return true;
}

function ensureNowCard() {
  const root = focusRoot();
  if (!root || q(".workspace-perception-now", root)) return;
  if (markNativeNow(root)) return;
  const surface = primarySurface(root);
  if (!surface || !surface.id) return;
  const title = surfaceTitle(surface);
  const hint = surfaceHint(surface);
  const status = surfaceStatus(surface);
  const next = surfaceNextAction(surface);
  const taskKey = String(surface.dataset.productivityTaskKey || "");
  const card = elementFrom(`
    <section class="workspace-perception-now" data-tone="${escapeMarkup(status.tone)}" aria-labelledby="workspace-perception-now-title">
      <span class="workspace-perception-now__glyph" aria-hidden="true">${icon("spark", 20)}</span>
      <div class="workspace-perception-now__copy">
        <p>Сейчас</p>
        <h2 id="workspace-perception-now-title">${escapeMarkup(title)}</h2>
        <span>${escapeMarkup(hint)}</span>
      </div>
      <div class="workspace-perception-now__status"><small>${escapeMarkup(status.label)}</small><strong>${escapeMarkup(next)}</strong></div>
      <div class="workspace-perception-now__actions">
        ${taskKey ? `<button type="button" data-perception-open-context="${escapeMarkup(taskKey)}">${icon("panel", 17)}<span>Контекст</span></button>` : ""}
        <button class="workspace-perception-now__primary" type="button" data-perception-open-task="${escapeMarkup(surface.id)}"><span>Открыть задачу</span>${icon("arrowRight", 17)}</button>
      </div>
    </section>
  `);
  const anchor = q(".workspace-page-intro, .page-header, .home-hero, .learning-hero", root);
  if (anchor?.parentElement) anchor.insertAdjacentElement("afterend", card);
  else root.prepend(card);
}

function classifyState(element) {
  if (element.matches(".workspace-initial-loading, .skeleton-stack, [aria-busy='true']")) return "loading";
  if (element.matches(".empty-state, .workspace-empty-state, [data-empty-state]")) return "empty";
  const text = String(element.textContent || "").toLocaleLowerCase("ru-RU");
  if (/ошиб|не удалось|failed|error|отклон|недоступ/.test(text)) return "error";
  if (/вниман|предупреж|риск|warning|проверь/.test(text)) return "warning";
  if (/готов|успеш|сохран|выполн|success/.test(text)) return "success";
  if (/пуст|нет данных|ничего не найдено/.test(text)) return "empty";
  return "info";
}

function stateIconName(state) {
  return { loading: "loader", error: "alert", warning: "alert", success: "check", empty: "folder", info: "info" }[state] || "info";
}

function decorateSystemStates() {
  const selectors = [
    ".alert",
    "[role='alert']",
    ".empty-state",
    ".workspace-empty-state",
    "[data-empty-state]",
    ".workspace-initial-loading",
    ".skeleton-stack",
    "[aria-busy='true']",
  ].join(",");
  qa(selectors).forEach((element) => {
    if (element.closest(".workspace-overview, .workspace-context-panel, .workspace-park-dialog")) return;
    const state = classifyState(element);
    element.dataset.perceptionState = state;
    if (element.matches("button, [role='button'], input, select, textarea")) return;
    if (state === "loading" && element.matches(".skeleton-stack")) return;
    let glyph = q(":scope > .workspace-state-glyph", element);
    if (!glyph) {
      glyph = document.createElement("span");
      glyph.className = "workspace-state-glyph";
      glyph.setAttribute("aria-hidden", "true");
      element.prepend(glyph);
    }
    setIconContainer(glyph, stateIconName(state), 18);
  });
}

function safeField(field) {
  if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement)) return false;
  const type = String(field.getAttribute("type") || "").toLowerCase();
  const identity = `${field.name || ""} ${field.id || ""} ${field.autocomplete || ""}`;
  return !["password", "hidden", "submit", "button", "reset", "file"].includes(type) && !SECRET_FIELD_PATTERN.test(identity);
}

function ensureFormStatus(form) {
  if (!(form instanceof HTMLFormElement) || form.closest(".workspace-overview, .workspace-context-panel, .workspace-park-dialog")) return null;
  let output = q(":scope > .workspace-form-status", form);
  if (!output) {
    output = elementFrom(`<output class="workspace-form-status" aria-live="polite" hidden>${icon("pencil", 15)}<span>Изменения в форме</span></output>`);
    form.prepend(output);
  }
  return output;
}

function setFormStatus(form, state, message) {
  const output = ensureFormStatus(form);
  if (!output) return;
  output.hidden = false;
  output.dataset.state = state;
  output.innerHTML = `${icon(state === "sending" ? "loader" : state === "reset" ? "check" : "pencil", 15)}<span>${escapeMarkup(message)}</span>`;
}

function handleFormInput(event) {
  const field = event.target;
  if (!safeField(field)) return;
  const form = field.closest("form");
  if (!form) return;
  form.dataset.perceptionDirty = "true";
  setFormStatus(form, "dirty", "Изменения в форме — отправьте, когда будете готовы");
}

function handleFormSubmit(event) {
  const form = event.target instanceof HTMLFormElement ? event.target : null;
  if (!form || form.closest(".workspace-overview, .workspace-context-panel, .workspace-park-dialog")) return;
  setFormStatus(form, "sending", "Отправка запущена…");
}

function handleFormReset(event) {
  const form = event.target instanceof HTMLFormElement ? event.target : null;
  if (!form) return;
  delete form.dataset.perceptionDirty;
  setFormStatus(form, "reset", "Форма очищена");
  window.setTimeout(() => {
    const output = q(":scope > .workspace-form-status", form);
    if (output && output.dataset.state === "reset") output.hidden = true;
  }, 1800);
}

function captureSharedSource(event) {
  if (REDUCED_MOTION.matches) return;
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  const focus = target.closest("[data-workspace-focus-card]");
  const context = target.closest("[data-productivity-context]");
  const park = target.closest("[data-productivity-park]");
  const overview = target.closest('[data-deck-action="overview"], [data-productivity-open-overview]');
  const trigger = focus || context || park || overview;
  if (!trigger) return;
  const source = focus?.closest('[data-workspace-focusable="true"]') || context?.closest(".workspace-task-dock__chip, .workspace-focusable-card") || park?.closest(".workspace-focusable-card, .workspace-context-panel") || overview;
  if (!(source instanceof Element)) return;
  const rect = source.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  runtime.sharedSource = {
    type: focus ? "focus" : context ? "context" : park ? "park" : "overview",
    id: focus?.dataset.workspaceFocusCard || context?.dataset.productivityContext || park?.dataset.productivityPark || "overview",
    rect: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
    radius: getComputedStyle(source).borderRadius || "18px",
    at: Date.now(),
  };
}

function sharedTarget(source) {
  if (!source || Date.now() - source.at > 1400) return null;
  if (source.type === "focus") return q(".workspace-task-focused");
  if (source.type === "context") return q(".workspace-context-panel");
  if (source.type === "park") return q(".workspace-park-dialog");
  if (source.type === "overview") return q(".workspace-overview");
  return null;
}

function animateSharedTarget() {
  const source = runtime.sharedSource;
  const target = sharedTarget(source);
  if (!(target instanceof HTMLElement) || target.dataset.perceptionSharedOpening === "true") return;
  const rect = target.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  target.dataset.perceptionSharedOpening = "true";
  runtime.sharedSource = null;
  if (typeof target.animate !== "function") {
    delete target.dataset.perceptionSharedOpening;
    return;
  }
  const dx = source.rect.left - rect.left;
  const dy = source.rect.top - rect.top;
  const sx = Math.max(0.06, Math.min(1.4, source.rect.width / rect.width));
  const sy = Math.max(0.06, Math.min(1.4, source.rect.height / rect.height));
  target.classList.add("workspace-perception-shared-opening");
  const animation = target.animate([
    {
      opacity: 0.45,
      transform: `translate3d(${dx}px, ${dy}px, 0) scale(${sx}, ${sy})`,
      borderRadius: source.radius,
      filter: "blur(5px) saturate(.78)",
    },
    {
      opacity: 1,
      transform: "translate3d(0, 0, 0) scale(1)",
      borderRadius: getComputedStyle(target).borderRadius,
      filter: "blur(0) saturate(1)",
    },
  ], {
    duration: source.type === "overview" ? 560 : 480,
    easing: "cubic-bezier(.16, 1, .3, 1)",
    fill: "both",
  });
  animation.finished.catch(() => undefined).finally(() => {
    target.classList.remove("workspace-perception-shared-opening");
    delete target.dataset.perceptionSharedOpening;
    animation.cancel();
  });
}

function dockNeedsAttention() {
  return Boolean(q(".workspace-task-dock__chip[data-tone='return'], .workspace-task-dock__chip[data-tone='blocked']"));
}

function revealDock(reason = "pointer") {
  window.clearTimeout(runtime.dockHideTimer);
  document.body.classList.add("workspace-dock-peek");
  document.body.dataset.dockRevealReason = reason;
}

function hideDockSoon(delay = 820) {
  window.clearTimeout(runtime.dockHideTimer);
  runtime.dockHideTimer = window.setTimeout(() => {
    if (dockNeedsAttention() || q(".workspace-task-dock:focus-within") || document.body.classList.contains("workspace-context-open")) return;
    document.body.classList.remove("workspace-dock-peek");
    delete document.body.dataset.dockRevealReason;
  }, delay);
}

function updateDockProximity(event) {
  runtime.pointerFrame = 0;
  if (!FINE_POINTER.matches || REDUCED_MOTION.matches || !isWorkspaceRoute()) {
    document.body.classList.remove("workspace-dock-autohidden", "workspace-dock-peek");
    return;
  }
  const dock = q(".workspace-task-dock");
  if (!dock) return;
  document.body.classList.add("workspace-dock-autohidden");
  const target = event?.target instanceof Element ? event.target : null;
  const nearBottom = event ? window.innerHeight - event.clientY <= 118 : false;
  const inside = Boolean(target?.closest(".workspace-task-dock"));
  if (nearBottom || inside || dockNeedsAttention() || q(".workspace-task-dock:focus-within")) revealDock(inside ? "dock" : "edge");
  else hideDockSoon(520);
}

function handlePointerMove(event) {
  runtime.pointerEvent = event;
  if (runtime.pointerFrame) return;
  runtime.pointerFrame = window.requestAnimationFrame(() => updateDockProximity(runtime.pointerEvent));
}

function ensureCoach() {
  if (!isWorkspaceRoute() || !q(".workspace-shell") || q(".workspace-perception-coach")) return;
  if (storage("local")?.getItem(PERCEPTION_COACH_KEY) === "seen") return;
  window.clearTimeout(runtime.coachTimer);
  runtime.coachTimer = window.setTimeout(() => {
    if (!isWorkspaceRoute() || q(".workspace-perception-coach")) return;
    const coach = elementFrom(`
      <aside class="workspace-perception-coach" role="dialog" aria-labelledby="workspace-perception-coach-title">
        <button class="workspace-perception-coach__close" type="button" data-perception-coach-dismiss aria-label="Закрыть подсказку">${icon("close", 17)}</button>
        <div class="workspace-perception-coach__mark" aria-hidden="true">${icon("overview", 22)}</div>
        <div class="workspace-perception-coach__copy">
          <p>Рабочие пространства готовы</p>
          <h2 id="workspace-perception-coach-title">Двигайтесь между столами, не теряя контекст</h2>
          <ul>
            <li>${icon("arrowLeft", 15)}<span>Свайп или <kbd>Alt⇧←/→</kbd> — соседний стол</span></li>
            <li>${icon("search", 15)}<span><kbd>⌘/Ctrl K</kbd> — Mission Control и поиск</span></li>
            <li>${icon("expand", 15)}<span><kbd>F</kbd> — одна задача на весь стол</span></li>
          </ul>
        </div>
        <div class="workspace-perception-coach__actions">
          <button type="button" data-perception-coach-dismiss>Понятно</button>
          <button class="is-primary" type="button" data-perception-coach-overview>Открыть обзор</button>
        </div>
      </aside>
    `);
    document.body.append(coach);
  }, 900);
}

function dismissCoach() {
  try { storage("local")?.setItem(PERCEPTION_COACH_KEY, "seen"); } catch { /* optional preference */ }
  const coach = q(".workspace-perception-coach");
  if (!coach) return;
  coach.classList.add("is-closing");
  window.setTimeout(() => coach.remove(), REDUCED_MOTION.matches ? 0 : 220);
}

function openTaskFromNow(id) {
  const surface = document.getElementById(id);
  if (!surface) return;
  const focus = q(":scope > [data-workspace-focus-card]", surface);
  if (focus) focus.click();
  else surface.scrollIntoView({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "center" });
}

function openContextFromNow(key) {
  if (!key) return;
  const selector = `[data-productivity-context="${CSS.escape(key)}"]`;
  q(selector)?.click();
}

function handleClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-perception-density]")) { event.preventDefault(); cycleDensity(); return; }
  const task = target.closest("[data-perception-open-task]");
  if (task) { event.preventDefault(); openTaskFromNow(task.dataset.perceptionOpenTask || ""); return; }
  const context = target.closest("[data-perception-open-context]");
  if (context) { event.preventDefault(); openContextFromNow(context.dataset.perceptionOpenContext || ""); return; }
  if (target.closest("[data-perception-coach-dismiss]")) { event.preventDefault(); dismissCoach(); return; }
  if (target.closest("[data-perception-coach-overview]")) {
    event.preventDefault();
    dismissCoach();
    window.setTimeout(() => q('[data-deck-action="overview"]')?.click(), 60);
  }
}

function decorate() {
  runtime.mountQueued = false;
  const ready = Boolean(q(".workspace-shell")) && isWorkspaceRoute();
  document.documentElement.classList.toggle("workspace-perception-ready", ready);
  if (!ready) {
    document.body.classList.remove("workspace-dock-autohidden", "workspace-dock-peek");
    return;
  }
  applyDensity(densityMode(), false);
  ensureDensityControl();
  decorateIcons();
  decorateSystemStates();
  ensureNowCard();
  decorateMissionControlPreviews();
  animateSharedTarget();
  ensureCoach();
  updateDockProximity(null);
}

function scheduleDecorate() {
  if (runtime.mountQueued) return;
  runtime.mountQueued = true;
  window.requestAnimationFrame(decorate);
}

const observer = new MutationObserver(scheduleDecorate);
observer.observe(q("#app") || document.body, { childList: true, subtree: true });
observer.observe(document.body, { childList: true, subtree: true });

window.addEventListener("pointerdown", captureSharedSource, true);
window.addEventListener("pointermove", handlePointerMove, { passive: true });
document.addEventListener("focusin", (event) => {
  if (event.target instanceof Element && event.target.closest(".workspace-task-dock")) revealDock("keyboard");
});
document.addEventListener("focusout", (event) => {
  const next = event.relatedTarget instanceof Element ? event.relatedTarget : null;
  if (!next?.closest(".workspace-task-dock")) hideDockSoon(420);
});
document.addEventListener("click", handleClick, true);
document.addEventListener("input", handleFormInput, true);
document.addEventListener("change", handleFormInput, true);
document.addEventListener("submit", handleFormSubmit, true);
document.addEventListener("reset", handleFormReset, true);
window.addEventListener("hashchange", scheduleDecorate, { passive: true });
REDUCED_MOTION.addEventListener?.("change", scheduleDecorate);
FINE_POINTER.addEventListener?.("change", scheduleDecorate);

scheduleDecorate();
