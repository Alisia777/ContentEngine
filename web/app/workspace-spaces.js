const WORKSPACE_SPACES_VERSION = "2026-07-30.1";
const WORKSPACE_FOCUS_KEY = "contentengine.workspace-spaces.focus.v1";
const WORKSPACE_AUTO_ADVANCE_KEY = "contentengine.workspace-spaces.auto-advance.v1";
const WORKSPACE_STATUS_KEY = "contentengine.workspace-spaces.status.v1";
const WORKSPACE_SUPPORT_KEY_PREFIX = "contentengine.workspace-spaces.support.v1";

const CORE_SPACE_ORDER = Object.freeze([
  "home",
  "media",
  "generation",
  "review",
  "tasks",
  "placement",
  "stats",
  "payouts",
]);

const SPACE_META = Object.freeze({
  home: Object.freeze({ step: "00", label: "Сегодня", short: "Сегодня", objective: "Одна главная задача на текущую смену", icon: "⌂" }),
  media: Object.freeze({ step: "01", label: "Материалы", short: "Файлы", objective: "Подготовить точные исходники товара", icon: "FL" }),
  generation: Object.freeze({ step: "02", label: "Создание контента", short: "Генератор", objective: "Создать один проверяемый результат", icon: "AI" }),
  review: Object.freeze({ step: "03", label: "Проверка контента", short: "Проверка", objective: "Принять одно доказуемое решение QA", icon: "QA" }),
  tasks: Object.freeze({ step: "04", label: "Задачи", short: "Задачи", objective: "Закрыть один следующий рабочий шаг", icon: "TK" }),
  placement: Object.freeze({ step: "05", label: "Публикации", short: "Публикация", objective: "Разместить одобренный материал и сохранить ссылку", icon: "UP" }),
  stats: Object.freeze({ step: "06", label: "Результаты", short: "Метрики", objective: "Зафиксировать фактический результат", icon: "AN" }),
  payouts: Object.freeze({ step: "07", label: "Выплаты", short: "Выплаты", objective: "Сверить и завершить денежный цикл", icon: "₽" }),
  work: Object.freeze({ step: "W", label: "Моя работа", short: "Моя работа", objective: "Видеть личную очередь без лишнего шума", icon: "●" }),
  board: Object.freeze({ step: "B", label: "Рабочий стол", short: "Папки", objective: "Разложить файлы и задачи по рабочим папкам", icon: "▦" }),
  research: Object.freeze({ step: "R", label: "Разбор товара", short: "Исследование", objective: "Собрать точное ТЗ до генерации", icon: "⌕" }),
  feedback: Object.freeze({ step: "+", label: "Помощь и идеи", short: "Помощь", objective: "Зафиксировать вопрос или улучшение", icon: "+" }),
  team: Object.freeze({ step: "T", label: "Команда", short: "Команда", objective: "Управлять доступами и ролями", icon: "◎" }),
});

const AUTO_ADVANCE_FORMS = Object.freeze([
  Object.freeze({ selector: "#media-upload-form", target: "generation", label: "Исходники готовы" }),
  Object.freeze({ selector: "#mock-batch-form", target: "home", label: "Запуск принят" }),
  Object.freeze({ selector: ".content-review-decision-form", target: "home", label: "Решение QA сохранено" }),
  Object.freeze({ selector: ".placement-form", target: "stats", label: "Публикация подтверждена" }),
  Object.freeze({ selector: "#manual-metric-form", target: "payouts", label: "Метрики сохранены" }),
  Object.freeze({ selector: ".payout-paid-form", target: "home", label: "Цикл выплаты завершён" }),
]);

const appRoot = document.querySelector("#app");
const toastRegion = document.querySelector("#toast-region");
const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
let enhancementQueued = false;
let activeShell = null;
let navigationWaiter = null;
let pendingNavigation = null;
let pendingAdvance = null;
let autoAdvanceTimer = 0;
let wheelDelta = 0;
let wheelResetTimer = 0;
let pointerStart = null;
let navigationLocked = false;

function readSession(key, fallback = "") {
  try {
    return window.sessionStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeSession(key, value) {
  try {
    window.sessionStorage.setItem(key, String(value));
  } catch {
    // Productivity preferences are optional and never block the workspace.
  }
}

function removeSession(key) {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Best-effort cleanup.
  }
}

function workspaceRoute() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  const path = raw.split("?", 1)[0].replace(/\/+$/, "");
  const match = path.match(/^\/workspace\/([^/]+)/);
  return {
    path,
    section: match ? decodeURIComponent(match[1]) : "",
  };
}

function workspaceHref(section) {
  return `#/workspace/${section}`;
}

function textOf(node) {
  return String(node?.textContent || "").replace(/\s+/g, " ").trim();
}

function element(tag, className = "", attributes = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  Object.entries(attributes).forEach(([name, value]) => {
    if (value === null || value === undefined || value === false) return;
    node.setAttribute(name, value === true ? "" : String(value));
  });
  return node;
}

function sectionFromHref(href) {
  const match = String(href || "").match(/^#\/workspace\/([^/?]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function metaFor(section, fallbackLabel = "") {
  const source = SPACE_META[section] || {};
  return {
    step: source.step || "•",
    label: source.label || fallbackLabel || "Рабочий стол",
    short: source.short || source.label || fallbackLabel || "Стол",
    objective: source.objective || "Выполнить одну текущую рабочую задачу",
    icon: source.icon || "•",
  };
}

function accessibleWorkspaceLinks(shell) {
  const links = [...shell.querySelectorAll('.sidebar a[href^="#/workspace/"]')];
  const seen = new Set();
  return links.map((link) => {
    const href = link.getAttribute("href") || "";
    const section = sectionFromHref(href);
    if (!section || seen.has(section)) return null;
    seen.add(section);
    const label = textOf(link.querySelector(".nav-link-copy strong")) || textOf(link);
    return { section, href, label, source: link };
  }).filter(Boolean);
}

function accessibleUtilityLinks(shell) {
  const workspaceLinks = accessibleWorkspaceLinks(shell)
    .filter((item) => !CORE_SPACE_ORDER.includes(item.section));
  const knowledgeLinks = [...shell.querySelectorAll('.sidebar a[href^="#/learn"]')]
    .map((link) => ({
      section: "",
      href: link.getAttribute("href") || "",
      label: textOf(link),
      source: link,
    }));
  return [...workspaceLinks, ...knowledgeLinks].filter((item, index, values) => (
    item.href && values.findIndex((candidate) => candidate.href === item.href) === index
  ));
}

function visibleCoreSpaces(shell) {
  const accessible = new Map(accessibleWorkspaceLinks(shell).map((item) => [item.section, item]));
  return CORE_SPACE_ORDER.map((section) => (
    accessible.get(section)
    || (section === shell.dataset.workspaceSection
      ? { section, href: workspaceHref(section), label: metaFor(section).label, source: null }
      : null)
  )).filter(Boolean);
}

function readSpaceStatuses() {
  try {
    const raw = JSON.parse(readSession(WORKSPACE_STATUS_KEY, "{}"));
    return raw && typeof raw === "object" ? raw : {};
  } catch {
    return {};
  }
}

function captureHomeStatuses(content) {
  const values = {};
  content.querySelectorAll('.home-flow-list a[href^="#/workspace/"]').forEach((link) => {
    const section = sectionFromHref(link.getAttribute("href"));
    const value = textOf(link.querySelector("em"));
    if (section && value) values[section] = value;
  });
  if (Object.keys(values).length) writeSession(WORKSPACE_STATUS_KEY, JSON.stringify(values));
}

function taskNodeForContent(content) {
  return content.querySelector(".home-next-action")
    || content.querySelector(".workspace-direction")
    || null;
}

function taskCopy(content, taskNode, section) {
  const pageTitle = textOf(content.querySelector("h1"));
  const title = textOf(taskNode?.querySelector("h2")) || pageTitle || metaFor(section).label;
  const step = textOf(taskNode?.querySelector(".home-next-action-main span"))
    || textOf(taskNode?.querySelector(".workspace-direction-heading .eyebrow"))
    || "Текущая задача";
  const doneWhen = textOf(taskNode?.querySelector(".home-next-action-proof span:first-child strong"))
    || textOf(taskNode?.querySelector(".workspace-direction-steps li:nth-child(2) strong"))
    || "Результат сохранён в портале";
  const nextLink = taskNode?.querySelector('.direction-next-link[href], a.btn[href], a[href^="#/workspace/"]');
  return {
    title,
    step,
    doneWhen,
    nextHref: nextLink?.getAttribute("href") || "",
  };
}

function nextCoreSpace(shell, direction = 1) {
  const spaces = visibleCoreSpaces(shell);
  if (!spaces.length) return null;
  const current = shell.dataset.workspaceSection;
  const index = Math.max(0, spaces.findIndex((item) => item.section === current));
  const nextIndex = (index + direction + spaces.length) % spaces.length;
  return spaces[nextIndex];
}

function createSpaceThumb(item, activeSection, statuses) {
  const meta = metaFor(item.section, item.label);
  const button = element("button", "wos-space-thumb", {
    type: "button",
    role: "tab",
    "data-wos-href": item.href,
    "data-wos-section": item.section,
    "aria-selected": item.section === activeSection ? "true" : "false",
    "aria-label": `${meta.label}. ${meta.objective}`,
  });
  if (item.section === activeSection) button.classList.add("is-active");
  const preview = element("span", "wos-space-thumb__preview", { "aria-hidden": "true" });
  preview.innerHTML = '<i></i><i></i><i></i><b></b>';
  const copy = element("span", "wos-space-thumb__copy");
  const step = element("small");
  step.textContent = `СТОЛ ${meta.step}`;
  const title = element("strong");
  title.textContent = meta.short;
  const status = element("em");
  status.textContent = statuses[item.section] || meta.objective;
  copy.append(step, title, status);
  button.append(preview, copy);
  return button;
}

function createSpaceStrip(shell) {
  const strip = element("section", "wos-space-strip", {
    role: "tablist",
    "aria-label": "Рабочие столы производственного цикла",
  });
  const label = element("div", "wos-space-strip__label");
  label.innerHTML = '<span>Рабочие столы</span><strong>Одна задача · один стол</strong><small>Свайп или Alt + Shift + ← →</small>';
  const viewport = element("div", "wos-space-strip__viewport");
  const statuses = readSpaceStatuses();
  visibleCoreSpaces(shell).forEach((item) => viewport.append(createSpaceThumb(
    item,
    shell.dataset.workspaceSection,
    statuses,
  )));
  strip.append(label, viewport);
  return strip;
}

function createContextControl(label, action, icon, pressed = null) {
  const button = element("button", "wos-context-control", {
    type: "button",
    "data-wos-action": action,
    title: label,
    "aria-label": label,
  });
  if (pressed !== null) button.setAttribute("aria-pressed", String(pressed));
  const mark = element("span", "wos-context-control__mark", { "aria-hidden": "true" });
  mark.textContent = icon;
  const copy = element("span", "wos-context-control__copy");
  copy.textContent = label;
  button.append(mark, copy);
  return button;
}

function focusModeEnabled() {
  return readSession(WORKSPACE_FOCUS_KEY, "false") === "true";
}

function autoAdvanceEnabled() {
  return readSession(WORKSPACE_AUTO_ADVANCE_KEY, "true") !== "false";
}

function applyFocusMode(shell, enabled, { persist = true } = {}) {
  document.documentElement.dataset.workspaceFocus = enabled ? "true" : "false";
  shell.classList.toggle("is-focus-mode", enabled);
  shell.querySelectorAll('[data-wos-action="toggle-focus"]').forEach((button) => {
    button.setAttribute("aria-pressed", String(enabled));
    button.classList.toggle("is-active", enabled);
  });
  const supportBody = shell.querySelector(".wos-support-body");
  const supportToggle = shell.querySelector('[data-wos-action="toggle-support"]');
  if (supportBody) supportBody.hidden = enabled;
  if (supportToggle) supportToggle.setAttribute("aria-expanded", String(!enabled));
  if (persist) writeSession(WORKSPACE_FOCUS_KEY, String(enabled));
}

function applyAutoAdvance(shell, enabled, { persist = true } = {}) {
  shell.querySelectorAll('[data-wos-action="toggle-auto-advance"]').forEach((button) => {
    button.setAttribute("aria-pressed", String(enabled));
    button.classList.toggle("is-active", enabled);
  });
  if (persist) writeSession(WORKSPACE_AUTO_ADVANCE_KEY, String(enabled));
}

function enhanceContextBar(shell) {
  const bar = shell.querySelector(".workspace-contextbar");
  if (!bar || bar.dataset.wosEnhanced === "true") return;
  bar.dataset.wosEnhanced = "true";
  const controls = element("div", "wos-context-controls");
  controls.append(
    createContextControl("Все приложения", "toggle-library", "⌘"),
    createContextControl("Фокус на одной задаче", "toggle-focus", "◎", focusModeEnabled()),
    createContextControl("Автопереход после завершения", "toggle-auto-advance", "→", autoAdvanceEnabled()),
    createContextControl("Быстрый переход", "open-command", "K"),
  );
  bar.prepend(controls);
}

function createTaskStage(shell, content) {
  const section = shell.dataset.workspaceSection;
  const meta = metaFor(section);
  const taskNode = taskNodeForContent(content);
  const copy = taskCopy(content, taskNode, section);
  taskNode?.remove();

  const stage = element("section", "wos-task-stage", {
    "aria-labelledby": "wos-task-title",
    "data-wos-space-stage": section,
  });
  const header = element("header", "wos-task-stage__header");
  const identity = element("div", "wos-task-stage__identity");
  const number = element("span", "wos-task-stage__number", { "aria-hidden": "true" });
  number.textContent = meta.step;
  const identityCopy = element("div");
  const eyebrow = element("p", "eyebrow");
  eyebrow.textContent = `${copy.step} · ${meta.label}`;
  const title = element("h1", "wos-task-stage__title", { id: "wos-task-title" });
  title.textContent = copy.title;
  const objective = element("p", "wos-task-stage__objective");
  objective.textContent = meta.objective;
  identityCopy.append(eyebrow, title, objective);
  identity.append(number, identityCopy);

  const actions = element("div", "wos-task-stage__actions");
  const previous = nextCoreSpace(shell, -1);
  const next = copy.nextHref ? { href: copy.nextHref } : nextCoreSpace(shell, 1);
  if (previous) {
    const button = element("button", "wos-stage-arrow", {
      type: "button",
      "data-wos-href": previous.href,
      "aria-label": "Предыдущий рабочий стол",
      title: "Предыдущий стол",
    });
    button.textContent = "←";
    actions.append(button);
  }
  if (next?.href) {
    const button = element("button", "wos-stage-next", {
      type: "button",
      "data-wos-href": next.href,
    });
    const nextSection = sectionFromHref(next.href);
    button.innerHTML = '<span>Следующий стол</span><strong data-wos-next-label></strong><i aria-hidden="true">→</i>';
    button.querySelector("[data-wos-next-label]").textContent = metaFor(nextSection).short || "Продолжить";
    actions.append(button);
  }
  header.append(identity, actions);

  const result = element("div", "wos-task-stage__done");
  result.innerHTML = '<span aria-hidden="true">✓</span><div><small>Готово, когда</small><strong></strong></div>';
  result.querySelector("strong").textContent = copy.doneWhen;

  const slot = element("div", "wos-task-stage__slot");
  if (taskNode) {
    taskNode.classList.add("wos-primary-task");
    slot.append(taskNode);
  } else {
    const fallback = element("article", "wos-task-fallback");
    fallback.innerHTML = '<span aria-hidden="true">◎</span><div><strong></strong><p></p></div>';
    fallback.querySelector("strong").textContent = copy.title;
    fallback.querySelector("p").textContent = "Все необходимые файлы, формы и история находятся в рабочей области этого стола ниже.";
    slot.append(fallback);
  }
  stage.append(header, result, slot);
  return stage;
}

function supportStorageKey(section) {
  return `${WORKSPACE_SUPPORT_KEY_PREFIX}:${section}`;
}

function createSupportArea(shell, content, originalNodes) {
  const section = shell.dataset.workspaceSection;
  const bar = element("div", "wos-support-bar");
  const toggle = element("button", "wos-support-toggle", {
    type: "button",
    "data-wos-action": "toggle-support",
    "aria-expanded": "true",
  });
  toggle.innerHTML = '<span aria-hidden="true">▦</span><div><strong>Файлы и инструменты этого стола</strong><small>Формы, история, таблицы и вторичные действия</small></div><i aria-hidden="true">⌄</i>';
  const state = element("span", "wos-draft-state", { "data-wos-draft-state": "" });
  state.innerHTML = '<i></i><span>Все изменения сохранены</span>';
  bar.append(toggle, state);

  const body = element("section", "wos-support-body", {
    "aria-label": "Рабочая область текущего стола",
  });
  originalNodes.forEach((node) => body.append(node));
  const collapsed = readSession(supportStorageKey(section), "false") === "true";
  body.hidden = collapsed || focusModeEnabled();
  toggle.setAttribute("aria-expanded", String(!body.hidden));
  content.append(bar, body);
}

function enhanceWorkspaceContent(shell) {
  const content = shell.querySelector("#workspace-content");
  if (!content || content.dataset.wosEnhanced === "true") return;
  content.dataset.wosEnhanced = "true";
  content.classList.add("wos-space-content");
  if (shell.dataset.workspaceSection === "home") captureHomeStatuses(content);
  const taskStage = createTaskStage(shell, content);
  const originalNodes = [...content.childNodes];
  content.replaceChildren(taskStage);
  createSupportArea(shell, content, originalNodes);
  updateDraftState(shell);
}

function createSidebarBackdrop(shell) {
  if (shell.querySelector(".wos-library-backdrop")) return;
  const backdrop = element("button", "wos-library-backdrop", {
    type: "button",
    "data-wos-action": "close-library",
    "aria-label": "Закрыть библиотеку приложений",
  });
  shell.append(backdrop);
  const sidebar = shell.querySelector(".sidebar");
  if (sidebar && !sidebar.querySelector(".wos-sidebar-close")) {
    const close = element("button", "wos-sidebar-close", {
      type: "button",
      "data-wos-action": "close-library",
      "aria-label": "Закрыть библиотеку приложений",
    });
    close.textContent = "×";
    sidebar.prepend(close);
  }
}

function setLibraryOpen(shell, open) {
  document.body.classList.toggle("wos-library-open", open);
  const main = shell.querySelector(".workspace-main");
  const sidebar = shell.querySelector(".sidebar");
  if (main) main.toggleAttribute("inert", open);
  if (sidebar) sidebar.setAttribute("aria-hidden", String(!open));
  if (open) window.queueMicrotask(() => sidebar?.querySelector("a, button")?.focus());
}

function dockItem(label, icon, href = "", action = "") {
  const item = element(href ? "a" : "button", "wos-dock-item", href
    ? { href, "data-wos-dock-href": href, title: label, "aria-label": label }
    : { type: "button", "data-wos-action": action, title: label, "aria-label": label });
  const mark = element("span", "wos-dock-item__icon", { "aria-hidden": "true" });
  mark.textContent = icon;
  const copy = element("span", "wos-dock-item__label");
  copy.textContent = label;
  item.append(mark, copy);
  return item;
}

function createDock(shell) {
  if (shell.querySelector(".wos-dock")) return;
  const dock = element("nav", "wos-dock", { "aria-label": "Док рабочих инструментов" });
  const leading = element("div", "wos-dock__leading");
  leading.append(
    dockItem("Все приложения", "⌘", "", "toggle-library"),
    dockItem("Быстрый переход", "K", "", "open-command"),
  );
  const apps = element("div", "wos-dock__apps");
  accessibleUtilityLinks(shell).forEach((item) => {
    const section = sectionFromHref(item.href);
    const meta = metaFor(section, item.label);
    apps.append(dockItem(item.label, meta.icon || item.label.slice(0, 1), item.href));
  });
  const trailing = element("div", "wos-dock__trailing");
  trailing.append(dockItem("Уведомления", "!", "", "notifications"));
  dock.append(leading, apps, trailing);
  shell.append(dock);
}

function createCommandPalette(shell) {
  if (shell.querySelector(".wos-command-layer")) return;
  const layer = element("div", "wos-command-layer", {
    hidden: true,
    "data-wos-command-layer": "",
  });
  const backdrop = element("button", "wos-command-backdrop", {
    type: "button",
    "data-wos-action": "close-command",
    "aria-label": "Закрыть быстрый переход",
  });
  const dialog = element("section", "wos-command", {
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "wos-command-title",
  });
  const header = element("header", "wos-command__header");
  header.innerHTML = '<span aria-hidden="true">⌘</span><div><small>Быстрый переход</small><h2 id="wos-command-title">Открыть стол или инструмент</h2></div><kbd>Esc</kbd>';
  const search = element("input", "wos-command__search", {
    type: "search",
    placeholder: "Например: генератор, файлы, выплаты…",
    "aria-label": "Поиск рабочего стола или инструмента",
    "data-wos-command-search": "",
  });
  const list = element("div", "wos-command__list", {
    role: "listbox",
    "data-wos-command-list": "",
  });
  const items = [
    ...visibleCoreSpaces(shell),
    ...accessibleUtilityLinks(shell),
  ];
  items.forEach((item) => {
    const section = item.section || sectionFromHref(item.href);
    const meta = metaFor(section, item.label);
    const button = element("button", "wos-command__item", {
      type: "button",
      role: "option",
      "data-wos-href": item.href,
      "data-wos-command-text": `${item.label} ${meta.objective}`.toLowerCase(),
    });
    const mark = element("span", "wos-command__item-mark", { "aria-hidden": "true" });
    mark.textContent = meta.icon;
    const copy = element("span", "wos-command__item-copy");
    const title = element("strong");
    title.textContent = item.label;
    const note = element("small");
    note.textContent = meta.objective;
    copy.append(title, note);
    const key = element("kbd");
    key.textContent = meta.step;
    button.append(mark, copy, key);
    list.append(button);
  });
  dialog.append(header, search, list);
  layer.append(backdrop, dialog);
  shell.append(layer);
}

function setCommandOpen(shell, open) {
  const layer = shell.querySelector("[data-wos-command-layer]");
  if (!layer) return;
  layer.hidden = !open;
  document.body.classList.toggle("wos-command-open", open);
  shell.querySelector(".workspace-main")?.toggleAttribute("inert", open);
  shell.querySelector(".sidebar")?.toggleAttribute("inert", open);
  if (open) {
    const search = layer.querySelector("[data-wos-command-search]");
    if (search) {
      search.value = "";
      filterCommands(layer, "");
      window.queueMicrotask(() => search.focus());
    }
  }
}

function filterCommands(layer, value) {
  const query = String(value || "").trim().toLowerCase();
  layer.querySelectorAll("[data-wos-command-text]").forEach((item) => {
    item.hidden = Boolean(query && !item.dataset.wosCommandText.includes(query));
  });
}

function createNavigationGuard(shell) {
  if (shell.querySelector(".wos-guard-layer")) return;
  const layer = element("div", "wos-guard-layer", {
    hidden: true,
    "data-wos-guard-layer": "",
  });
  const backdrop = element("button", "wos-command-backdrop", {
    type: "button",
    "data-wos-action": "cancel-navigation",
    "aria-label": "Остаться на текущем столе",
  });
  const dialog = element("section", "wos-guard", {
    role: "dialog",
    "aria-modal": "true",
    "aria-labelledby": "wos-guard-title",
  });
  dialog.innerHTML = `
    <span class="wos-guard__mark" aria-hidden="true">!</span>
    <div><p class="eyebrow">Незавершённый стол</p><h2 id="wos-guard-title">На этом столе есть несохранённые изменения</h2><p>Сохраните форму или останьтесь здесь. Переход без сохранения может потерять введённые поля и выбранные файлы.</p></div>
    <div class="wos-guard__actions"><button type="button" class="btn btn-secondary" data-wos-action="cancel-navigation">Остаться</button><button type="button" class="btn" data-wos-action="force-navigation">Перейти без сохранения</button></div>
  `;
  layer.append(backdrop, dialog);
  shell.append(layer);
}

function setGuardOpen(shell, open) {
  const layer = shell.querySelector("[data-wos-guard-layer]");
  if (!layer) return;
  layer.hidden = !open;
  document.body.classList.toggle("wos-guard-open", open);
  shell.querySelector(".workspace-main")?.toggleAttribute("inert", open);
  shell.querySelector(".sidebar")?.toggleAttribute("inert", open);
  if (open) window.queueMicrotask(() => layer.querySelector('[data-wos-action="cancel-navigation"]')?.focus());
}

function dirtyForm(shell = activeShell) {
  return shell?.querySelector('#workspace-content form[data-dirty="true"]') || null;
}

function updateDraftState(shell = activeShell) {
  if (!shell) return;
  const dirty = Boolean(dirtyForm(shell));
  const state = shell.querySelector("[data-wos-draft-state]");
  if (!state) return;
  state.classList.toggle("is-dirty", dirty);
  const copy = state.querySelector("span");
  if (copy) copy.textContent = dirty ? "Есть несохранённые изменения" : "Все изменения сохранены";
}

function navigationDirection(current, target) {
  const currentIndex = CORE_SPACE_ORDER.indexOf(current);
  const targetIndex = CORE_SPACE_ORDER.indexOf(target);
  if (currentIndex < 0 || targetIndex < 0 || currentIndex === targetIndex) return "depth";
  return targetIndex > currentIndex ? "forward" : "backward";
}

function waitForWorkspaceSection(section) {
  return new Promise((resolve) => {
    const timer = window.setTimeout(() => {
      if (navigationWaiter?.resolve === resolve) navigationWaiter = null;
      resolve();
    }, 2200);
    navigationWaiter = {
      section,
      resolve: () => {
        window.clearTimeout(timer);
        navigationWaiter = null;
        resolve();
      },
    };
  });
}

async function performNavigation(href, { bypassDirty = false } = {}) {
  if (navigationLocked) return;
  const targetSection = sectionFromHref(href);
  if (!targetSection) {
    closeWorkspaceOverlays();
    window.location.hash = String(href).replace(/^#/, "");
    return;
  }
  const current = workspaceRoute().section;
  if (current === targetSection) {
    closeWorkspaceOverlays();
    window.location.hash = String(href).replace(/^#/, "");
    return;
  }
  if (!bypassDirty && dirtyForm()) {
    pendingNavigation = href;
    setGuardOpen(activeShell, true);
    return;
  }

  navigationLocked = true;
  pendingNavigation = null;
  closeWorkspaceOverlays();
  const direction = navigationDirection(current, targetSection);
  document.documentElement.dataset.workspaceSpaceDirection = direction;
  const update = async () => {
    const waiting = waitForWorkspaceSection(targetSection);
    window.location.hash = String(href).replace(/^#/, "");
    await waiting;
  };

  try {
    if (!reducedMotion?.matches && typeof document.startViewTransition === "function") {
      const transition = document.startViewTransition(update);
      await transition.finished;
    } else {
      activeShell?.classList.add(`is-leaving-${direction}`);
      await new Promise((resolve) => window.setTimeout(resolve, reducedMotion?.matches ? 10 : 170));
      await update();
    }
  } finally {
    navigationLocked = false;
    window.setTimeout(() => delete document.documentElement.dataset.workspaceSpaceDirection, 50);
  }
}

function requestNavigation(href) {
  void performNavigation(href);
}

function closeWorkspaceOverlays() {
  if (!activeShell) return;
  setLibraryOpen(activeShell, false);
  setCommandOpen(activeShell, false);
  setGuardOpen(activeShell, false);
}

function cycleSpace(direction) {
  if (!activeShell || navigationLocked) return;
  const next = nextCoreSpace(activeShell, direction);
  if (next) requestNavigation(next.href);
}

function swipeBlocked(target) {
  return Boolean(target?.closest?.(
    'input, textarea, select, [contenteditable="true"], .table-wrap, .workspace-board, .wos-space-strip__viewport, .wos-dock__apps, [data-horizontal-scroll]',
  ));
}

function handleWheel(event) {
  if (!activeShell || swipeBlocked(event.target)) return;
  if (Math.abs(event.deltaX) < 28 || Math.abs(event.deltaX) < Math.abs(event.deltaY) * 1.2) return;
  wheelDelta += event.deltaX;
  window.clearTimeout(wheelResetTimer);
  wheelResetTimer = window.setTimeout(() => { wheelDelta = 0; }, 260);
  if (Math.abs(wheelDelta) < 120) return;
  event.preventDefault();
  const direction = wheelDelta > 0 ? 1 : -1;
  wheelDelta = 0;
  cycleSpace(direction);
}

function handlePointerDown(event) {
  if (!activeShell || !["touch", "pen"].includes(event.pointerType) || swipeBlocked(event.target)) return;
  pointerStart = { x: event.clientX, y: event.clientY, at: Date.now() };
}

function handlePointerUp(event) {
  if (!pointerStart || !activeShell) return;
  const deltaX = event.clientX - pointerStart.x;
  const deltaY = event.clientY - pointerStart.y;
  const duration = Date.now() - pointerStart.at;
  pointerStart = null;
  if (duration > 900 || Math.abs(deltaX) < 72 || Math.abs(deltaX) < Math.abs(deltaY) * 1.4) return;
  cycleSpace(deltaX < 0 ? 1 : -1);
}

function autoAdvanceRule(form) {
  return AUTO_ADVANCE_FORMS.find((rule) => form.matches(rule.selector)) || null;
}

function setPendingAdvance(rule) {
  if (!rule || !autoAdvanceEnabled()) return;
  pendingAdvance = {
    ...rule,
    startedAt: Date.now(),
  };
}

function clearPendingAdvance() {
  pendingAdvance = null;
}

function showAutoAdvance(targetSection, label) {
  window.clearTimeout(autoAdvanceTimer);
  document.querySelector(".wos-auto-advance")?.remove();
  const overlay = element("section", "wos-auto-advance", {
    role: "status",
    "aria-live": "assertive",
  });
  overlay.innerHTML = `
    <div class="wos-auto-advance__mark" aria-hidden="true">✓</div>
    <div><p class="eyebrow">Задача завершена</p><h2></h2><p>Переключаем рабочий стол без потери маршрута.</p></div>
    <button type="button" data-wos-action="cancel-auto-advance">Остаться здесь</button>
    <div class="wos-auto-advance__line" aria-hidden="true"><span></span></div>
  `;
  overlay.querySelector("h2").textContent = `${label}. Следующий стол — «${metaFor(targetSection).short}»`;
  document.body.append(overlay);
  requestAnimationFrame(() => overlay.classList.add("is-visible"));
  autoAdvanceTimer = window.setTimeout(() => {
    overlay.classList.remove("is-visible");
    void performNavigation(workspaceHref(targetSection), { bypassDirty: true });
    window.setTimeout(() => overlay.remove(), 420);
  }, reducedMotion?.matches ? 120 : 1800);
}

function observeToasts() {
  if (!toastRegion) return;
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (!(node instanceof HTMLElement) || !node.classList.contains("toast")) return;
      if (node.classList.contains("error")) {
        clearPendingAdvance();
        return;
      }
      if (!node.classList.contains("success") || !pendingAdvance) return;
      if (Date.now() - pendingAdvance.startedAt > 5 * 60_000) {
        clearPendingAdvance();
        return;
      }
      const next = pendingAdvance;
      clearPendingAdvance();
      showAutoAdvance(next.target, next.label);
    }));
  });
  observer.observe(toastRegion, { childList: true });
}

function createShellChrome(shell) {
  if (!shell.querySelector(".wos-space-strip")) {
    const contextBar = shell.querySelector(".workspace-contextbar");
    const strip = createSpaceStrip(shell);
    if (contextBar) contextBar.after(strip);
    else shell.querySelector(".workspace-main")?.prepend(strip);
  }
  enhanceContextBar(shell);
  createSidebarBackdrop(shell);
  createDock(shell);
  createCommandPalette(shell);
  createNavigationGuard(shell);
}

function enhanceWorkspaceShell(shell) {
  if (!shell) return;
  const newShell = activeShell !== shell;
  activeShell = shell;
  shell.classList.add("wos-enhanced");
  shell.dataset.wosVersion = WORKSPACE_SPACES_VERSION;
  document.documentElement.dataset.workspaceSpaces = "active";
  createShellChrome(shell);
  enhanceWorkspaceContent(shell);
  applyFocusMode(shell, focusModeEnabled(), { persist: false });
  applyAutoAdvance(shell, autoAdvanceEnabled(), { persist: false });
  setLibraryOpen(shell, false);

  if (newShell) {
    requestAnimationFrame(() => shell.classList.add("is-space-ready"));
  }
  if (navigationWaiter?.section === shell.dataset.workspaceSection) {
    requestAnimationFrame(() => navigationWaiter?.resolve());
  }
}

function cleanupWorkspaceMode() {
  if (workspaceRoute().section) return;
  activeShell = null;
  delete document.documentElement.dataset.workspaceSpaces;
  delete document.documentElement.dataset.workspaceFocus;
  document.body.classList.remove("wos-library-open", "wos-command-open", "wos-guard-open");
}

function enhanceCurrentWorkspace() {
  enhancementQueued = false;
  const shell = appRoot?.querySelector(".workspace-shell");
  if (shell) enhanceWorkspaceShell(shell);
  else cleanupWorkspaceMode();
}

function scheduleEnhancement() {
  if (enhancementQueued) return;
  enhancementQueued = true;
  requestAnimationFrame(enhanceCurrentWorkspace);
}

function handleWorkspaceAction(control) {
  const action = control.dataset.wosAction;
  if (!action || !activeShell) return false;
  if (action === "toggle-library") setLibraryOpen(activeShell, !document.body.classList.contains("wos-library-open"));
  else if (action === "close-library") setLibraryOpen(activeShell, false);
  else if (action === "toggle-focus") applyFocusMode(activeShell, !focusModeEnabled());
  else if (action === "toggle-auto-advance") applyAutoAdvance(activeShell, !autoAdvanceEnabled());
  else if (action === "open-command") setCommandOpen(activeShell, true);
  else if (action === "close-command") setCommandOpen(activeShell, false);
  else if (action === "toggle-support") {
    const body = activeShell.querySelector(".wos-support-body");
    if (body) {
      body.hidden = !body.hidden;
      control.setAttribute("aria-expanded", String(!body.hidden));
      writeSession(supportStorageKey(activeShell.dataset.workspaceSection), String(body.hidden));
    }
  } else if (action === "cancel-navigation") {
    pendingNavigation = null;
    setGuardOpen(activeShell, false);
  } else if (action === "force-navigation") {
    const href = pendingNavigation;
    pendingNavigation = null;
    setGuardOpen(activeShell, false);
    if (href) void performNavigation(href, { bypassDirty: true });
  } else if (action === "notifications") {
    activeShell.querySelector(".workspace-notification-nav")?.click();
  } else if (action === "cancel-auto-advance") {
    window.clearTimeout(autoAdvanceTimer);
    document.querySelector(".wos-auto-advance")?.remove();
  } else return false;
  return true;
}

document.addEventListener("click", (event) => {
  const actionControl = event.target.closest?.("[data-wos-action]");
  if (actionControl && handleWorkspaceAction(actionControl)) {
    event.preventDefault();
    return;
  }

  const hrefControl = event.target.closest?.("[data-wos-href]");
  if (hrefControl) {
    event.preventDefault();
    requestNavigation(hrefControl.dataset.wosHref);
    return;
  }

  const link = event.target.closest?.('a[href^="#/workspace/"]');
  if (
    activeShell
    && link
    && !event.defaultPrevented
    && !event.metaKey
    && !event.ctrlKey
    && !event.shiftKey
    && !event.altKey
    && !link.hasAttribute("download")
    && !link.target
  ) {
    const targetSection = sectionFromHref(link.getAttribute("href"));
    if (targetSection && targetSection !== workspaceRoute().section) {
      event.preventDefault();
      requestNavigation(link.getAttribute("href"));
    }
  }

  const taskDone = event.target.closest?.('[data-action="transition-task"][data-status="done"]');
  if (taskDone) setPendingAdvance({ target: "home", label: "Задача закрыта" });
}, true);

document.addEventListener("submit", (event) => {
  if (!(event.target instanceof HTMLFormElement)) return;
  const rule = autoAdvanceRule(event.target);
  if (rule) setPendingAdvance(rule);
}, true);

document.addEventListener("input", (event) => {
  if (event.target.closest?.("#workspace-content")) window.queueMicrotask(() => updateDraftState());
  if (event.target.matches?.("[data-wos-command-search]")) {
    filterCommands(event.target.closest("[data-wos-command-layer]"), event.target.value);
  }
}, true);

document.addEventListener("change", (event) => {
  if (event.target.closest?.("#workspace-content")) window.queueMicrotask(() => updateDraftState());
}, true);

document.addEventListener("keydown", (event) => {
  const typing = event.target.matches?.("input, textarea, select, [contenteditable='true']");
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    if (!activeShell) return;
    event.preventDefault();
    setCommandOpen(activeShell, true);
    return;
  }
  if (event.key === "Escape" && activeShell) {
    if (document.body.classList.contains("wos-command-open")) {
      event.preventDefault();
      setCommandOpen(activeShell, false);
      return;
    }
    if (document.body.classList.contains("wos-guard-open")) {
      event.preventDefault();
      pendingNavigation = null;
      setGuardOpen(activeShell, false);
      return;
    }
    if (document.body.classList.contains("wos-library-open")) {
      event.preventDefault();
      setLibraryOpen(activeShell, false);
      return;
    }
  }
  if (!typing && event.altKey && event.shiftKey && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    event.preventDefault();
    cycleSpace(event.key === "ArrowRight" ? 1 : -1);
  }
  if (!typing && !event.metaKey && !event.ctrlKey && !event.altKey && event.key.toLowerCase() === "f" && activeShell) {
    event.preventDefault();
    applyFocusMode(activeShell, !focusModeEnabled());
  }
  if (event.key === "Enter" && event.target.matches?.(".wos-command__item")) {
    event.preventDefault();
    requestNavigation(event.target.dataset.wosHref);
  }
});

document.addEventListener("wheel", handleWheel, { passive: false });
document.addEventListener("pointerdown", handlePointerDown, { passive: true });
document.addEventListener("pointerup", handlePointerUp, { passive: true });
window.addEventListener("hashchange", scheduleEnhancement);

const appObserver = new MutationObserver(scheduleEnhancement);
if (appRoot) appObserver.observe(appRoot, { childList: true, subtree: true });
observeToasts();
scheduleEnhancement();
