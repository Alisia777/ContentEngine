const LEARNING_HOME_PATH = "/learn";
const PANEL_STORAGE_KEY = "contentengine.learning-workbench.panel.v1";
const FOLDER_STORAGE_KEY = "contentengine.learning-workbench.folder.v1";
const TASK_SIGNATURE_KEY = "contentengine.learning-workbench.task.v1";
const COURSE_ADVANCE_PENDING_KEY = "contentengine.learning-workbench.course-advance-pending.v1";
const FORCE_TASK_PANEL_KEY = "contentengine.learning-workbench.force-task-panel.v1";

const PANEL_DEFINITIONS = Object.freeze([
  Object.freeze({ id: "task", number: "01", label: "Текущая задача", shortLabel: "Задача", hint: "Один шаг без лишнего шума" }),
  Object.freeze({ id: "files", number: "02", label: "Рабочие папки", shortLabel: "Файлы", hint: "Маршрут, схема и правила" }),
  Object.freeze({ id: "courses", number: "03", label: "Очередь задач", shortLabel: "Обучение", hint: "Четыре производственных блока" }),
  Object.freeze({ id: "access", number: "04", label: "Допуск к работе", shortLabel: "Допуск", hint: "Пробный ролик и экзамен" }),
  Object.freeze({ id: "practice", number: "05", label: "Тренажёры", shortLabel: "Практика", hint: "Безопасная репетиция процессов" }),
]);

const FOLDER_DEFINITIONS = Object.freeze([
  Object.freeze({ id: "route", label: "Мой маршрут", meta: "Роль и персональный акцент", mark: "MR" }),
  Object.freeze({ id: "process", label: "Схема производства", meta: "От файла до выплаты", mark: "07" }),
  Object.freeze({ id: "rules", label: "Правила качества", meta: "Стоп-сигналы и безопасность", mark: "QA" }),
  Object.freeze({ id: "results", label: "Мои достижения", meta: "Пройденные блоки и навыки", mark: "XP" }),
]);

const APPLICATIONS = Object.freeze([
  Object.freeze({ id: "media", label: "Материалы", code: "FL", route: "#/workspace/media", learn: "#/learn/factory_basics", tone: "sand" }),
  Object.freeze({ id: "generation", label: "Генератор", code: "AI", route: "#/workspace/generation", learn: "#/learn/video_quality", tone: "orange" }),
  Object.freeze({ id: "review", label: "Проверка", code: "QA", route: "#/workspace/review", learn: "#/learn/video_quality", tone: "blue" }),
  Object.freeze({ id: "tasks", label: "Задачи", code: "TK", route: "#/workspace/tasks", learn: "#/learn/factory_basics", tone: "graphite" }),
  Object.freeze({ id: "placement", label: "Публикация", code: "UP", route: "#/workspace/placement", learn: "#/learn/publishing_funnel", tone: "violet" }),
  Object.freeze({ id: "stats", label: "Результаты", code: "AN", route: "#/workspace/stats", learn: "#/learn/publishing_funnel", tone: "green" }),
  Object.freeze({ id: "payouts", label: "Выплаты", code: "₽", route: "#/workspace/payouts", learn: "#/learn/security_wb", tone: "gold" }),
]);

const appRoot = document.querySelector("#app");
const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
let enhancementQueued = false;
let activeShell = null;
let advanceTimer = 0;

function normalizedPath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  const path = raw.split("?", 1)[0].replace(/\/+$/, "");
  return path || "/";
}

function isLearningHome() {
  return normalizedPath() === LEARNING_HOME_PATH;
}

function isCoursePath() {
  return /^\/learn\/[^/]+$/.test(normalizedPath())
    && !["/learn/exam", "/learn/practical", "/learn/first-shift", "/learn/account-launch"].includes(normalizedPath());
}

function readStorage(key, fallback = "") {
  try {
    return window.sessionStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    window.sessionStorage.setItem(key, String(value));
  } catch {
    // A blocked storage area must never block the learning interface.
  }
}

function removeStorage(key) {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Ignore restricted storage contexts.
  }
}

function textOf(node) {
  return String(node?.textContent || "").replace(/\s+/g, " ").trim();
}

function directChildren(root, selector) {
  return [...root.children].filter((node) => node.matches?.(selector));
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

function taskSignature(root) {
  const title = textOf(root.querySelector("#learning-now-title"));
  const step = textOf(root.querySelector(".learning-now-step strong"));
  const action = textOf(root.querySelector(".learning-now .btn"));
  return [step, title, action].filter(Boolean).join("|");
}

function workspaceIsUnlocked(root) {
  return Boolean(root.querySelector('a[href="#/workspace/home"]'));
}

function panelById(shell, panelId) {
  return shell?.querySelector(`[data-lwb-panel-view="${CSS.escape(panelId)}"]`) || null;
}

function panelDefinition(panelId) {
  return PANEL_DEFINITIONS.find((item) => item.id === panelId) || PANEL_DEFINITIONS[0];
}

function validPanelId(value) {
  return PANEL_DEFINITIONS.some((item) => item.id === value) ? value : "task";
}

function validFolderId(value) {
  return FOLDER_DEFINITIONS.some((item) => item.id === value) ? value : "route";
}

function setPanelImmediate(shell, rawPanelId, { persist = true, focus = false } = {}) {
  const panelId = validPanelId(rawPanelId);
  const definition = panelDefinition(panelId);
  shell.dataset.activePanel = panelId;

  shell.querySelectorAll("[data-lwb-panel]").forEach((button) => {
    const selected = button.dataset.lwbPanel === panelId;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    button.classList.toggle("is-active", selected);
  });

  shell.querySelectorAll("[data-lwb-panel-view]").forEach((panel) => {
    const selected = panel.dataset.lwbPanelView === panelId;
    panel.hidden = !selected;
    panel.classList.toggle("is-active", selected);
  });

  const title = shell.querySelector("[data-lwb-window-title]");
  const counter = shell.querySelector("[data-lwb-window-counter]");
  if (title) title.textContent = definition.label;
  if (counter) counter.textContent = `${definition.number} / ${String(PANEL_DEFINITIONS.length).padStart(2, "0")}`;
  if (persist) writeStorage(PANEL_STORAGE_KEY, panelId);
  if (focus) panelById(shell, panelId)?.focus({ preventScroll: true });
}

function switchPanel(shell, panelId, options = {}) {
  if (!shell || shell.dataset.activePanel === panelId) return;
  const update = () => setPanelImmediate(shell, panelId, options);
  if (!reducedMotion?.matches && typeof document.startViewTransition === "function") {
    document.startViewTransition(update);
  } else {
    shell.classList.add("is-panel-switching");
    window.setTimeout(() => {
      update();
      requestAnimationFrame(() => shell.classList.remove("is-panel-switching"));
    }, 130);
  }
}

function cyclePanel(shell, direction) {
  const current = PANEL_DEFINITIONS.findIndex((item) => item.id === shell?.dataset.activePanel);
  const safeCurrent = current >= 0 ? current : 0;
  const next = (safeCurrent + direction + PANEL_DEFINITIONS.length) % PANEL_DEFINITIONS.length;
  switchPanel(shell, PANEL_DEFINITIONS[next].id, { focus: true });
}

function setFolder(shell, rawFolderId, { persist = true } = {}) {
  const folderId = validFolderId(rawFolderId);
  shell.querySelectorAll("[data-lwb-folder]").forEach((button) => {
    const selected = button.dataset.lwbFolder === folderId;
    button.classList.toggle("is-open", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  shell.querySelectorAll("[data-lwb-folder-view]").forEach((view) => {
    const selected = view.dataset.lwbFolderView === folderId;
    view.hidden = !selected;
    view.classList.toggle("is-open", selected);
  });
  if (persist) writeStorage(FOLDER_STORAGE_KEY, folderId);
}

function applicationDockMarkup(unlocked) {
  return APPLICATIONS.map((application) => {
    const href = unlocked ? application.route : application.learn;
    const mode = unlocked ? "Открыть рабочий раздел" : "Сначала открыть учебный блок";
    return `
      <a class="lwb-app lwb-app--${application.tone}" href="${href}" data-lwb-app="${application.id}" aria-label="${application.label}. ${mode}">
        <span class="lwb-app__icon" aria-hidden="true">${application.code}</span>
        <span class="lwb-app__label">${application.label}</span>
        ${unlocked ? "" : '<span class="lwb-app__lock" aria-hidden="true">•</span>'}
      </a>
    `;
  }).join("");
}

function makeSidebar() {
  const sidebar = element("nav", "lwb-sidebar", {
    role: "tablist",
    "aria-label": "Разделы учебного рабочего стола",
    "aria-orientation": "vertical",
  });
  sidebar.innerHTML = PANEL_DEFINITIONS.map((panel) => `
    <button class="lwb-sidebar__tab" type="button" role="tab" id="lwb-tab-${panel.id}" aria-controls="lwb-panel-${panel.id}" aria-selected="false" tabindex="-1" data-lwb-panel="${panel.id}">
      <span class="lwb-sidebar__number" aria-hidden="true">${panel.number}</span>
      <span class="lwb-sidebar__copy"><strong>${panel.shortLabel}</strong><small>${panel.hint}</small></span>
    </button>
  `).join("");
  return sidebar;
}

function makeFolderDesk(folderNodes) {
  const panel = element("section", "lwb-panel lwb-files-panel", {
    id: "lwb-panel-files",
    role: "tabpanel",
    tabindex: "-1",
    "aria-labelledby": "lwb-tab-files",
    "data-lwb-panel-view": "files",
  });
  const intro = element("div", "lwb-panel-heading");
  intro.innerHTML = `
    <div><p class="eyebrow">Рабочие материалы</p><h2>Папки лежат прямо на столе</h2></div>
    <p>Откройте только нужную папку. Внутри — действующие настройки, схема процесса и ваши результаты.</p>
  `;
  panel.append(intro);

  const layout = element("div", "lwb-files-layout");
  const folders = element("div", "lwb-folder-grid", { "aria-label": "Рабочие папки" });
  folders.innerHTML = FOLDER_DEFINITIONS.map((folder) => `
    <button class="lwb-folder" type="button" data-lwb-folder="${folder.id}" aria-pressed="false">
      <span class="lwb-folder__shape" aria-hidden="true"><i>${folder.mark}</i></span>
      <span class="lwb-folder__copy"><strong>${folder.label}</strong><small>${folder.meta}</small></span>
    </button>
  `).join("");

  const viewer = element("div", "lwb-folder-viewer");
  FOLDER_DEFINITIONS.forEach((folder) => {
    const view = element("section", "lwb-folder-view", {
      "data-lwb-folder-view": folder.id,
      "aria-label": folder.label,
      hidden: true,
    });
    const node = folderNodes.get(folder.id);
    if (node) view.append(node);
    else view.innerHTML = '<div class="lwb-folder-empty"><strong>Папка пока пуста</strong><p>Материал появится после загрузки учебного каталога.</p></div>';
    viewer.append(view);
  });

  layout.append(folders, viewer);
  panel.append(layout);
  return panel;
}

function makeGenericPanel(id, title, eyebrow, description, nodes) {
  const panel = element("section", `lwb-panel lwb-panel--${id}`, {
    id: `lwb-panel-${id}`,
    role: "tabpanel",
    tabindex: "-1",
    "aria-labelledby": `lwb-tab-${id}`,
    "data-lwb-panel-view": id,
    hidden: true,
  });
  const heading = element("div", "lwb-panel-heading");
  heading.innerHTML = `
    <div><p class="eyebrow">${eyebrow}</p><h2>${title}</h2></div>
    <p>${description}</p>
  `;
  panel.append(heading);
  nodes.filter(Boolean).forEach((node) => panel.append(node));
  return panel;
}

function makeTaskPanel(hero, alerts, currentTask) {
  const panel = element("section", "lwb-panel lwb-panel--task", {
    id: "lwb-panel-task",
    role: "tabpanel",
    tabindex: "-1",
    "aria-labelledby": "lwb-tab-task",
    "data-lwb-panel-view": "task",
  });
  alerts.forEach((node) => panel.append(node));
  if (hero) panel.append(hero);
  if (currentTask) panel.append(currentTask);
  return panel;
}

function queueMarkup(passport) {
  const queue = element("aside", "lwb-queue", { "aria-label": "Очередь учебных задач" });
  const header = element("div", "lwb-queue__header");
  header.innerHTML = '<div><p class="eyebrow">Очередь задач</p><h2>Текущая смена</h2></div><span class="lwb-live"><i></i> сохранено</span>';
  queue.append(header);
  if (passport) queue.append(passport);
  const note = element("div", "lwb-queue__note");
  note.innerHTML = '<span aria-hidden="true">↳</span><p><strong>Следующий стол откроется сам.</strong> Завершите текущий блок — портал вернёт вас сюда уже с новой задачей.</p>';
  queue.append(note);
  return queue;
}

function makeWindow(panels) {
  const windowNode = element("section", "lwb-window", { "aria-label": "Рабочее окно" });
  const bar = element("header", "lwb-window__bar");
  bar.innerHTML = `
    <div class="lwb-window__controls" aria-hidden="true"><span></span><span></span><span></span></div>
    <div class="lwb-window__title"><small data-lwb-window-counter>01 / 05</small><strong data-lwb-window-title>Текущая задача</strong></div>
    <div class="lwb-window__navigation">
      <button type="button" data-lwb-prev aria-label="Предыдущий раздел">←</button>
      <button type="button" data-lwb-next aria-label="Следующий раздел">→</button>
    </div>
  `;
  const body = element("div", "lwb-window__body");
  panels.forEach((panel) => body.append(panel));
  windowNode.append(bar, body);
  return windowNode;
}

function makeMenubar(progress, taskTitle) {
  const bar = element("header", "lwb-menubar");
  bar.innerHTML = `
    <div class="lwb-menubar__brand"><span class="lwb-menubar__mark" aria-hidden="true">КИ</span><div><strong>Учебный рабочий стол</strong><small>Контент ИИ Завод</small></div></div>
    <div class="lwb-menubar__task"><span>На столе</span><strong>${taskTitle || "Текущая задача"}</strong></div>
    <div class="lwb-menubar__progress"><span>Готовность</span><strong>${progress || "0%"}</strong></div>
  `;
  return bar;
}

function makeDock(unlocked) {
  const dock = element("nav", "lwb-dock", { "aria-label": "Инструменты производства" });
  const copy = element("div", "lwb-dock__copy");
  copy.innerHTML = `<strong>${unlocked ? "Рабочие приложения" : "Приложения в учебном режиме"}</strong><small>${unlocked ? "Допуск открыт" : "Откроются полностью после допуска"}</small>`;
  const apps = element("div", "lwb-dock__apps");
  apps.innerHTML = applicationDockMarkup(unlocked);
  dock.append(copy, apps);
  return dock;
}

function showAdvanceNotice(shell, title = "Следующий стол готов", description = "Предыдущая задача закрыта. На рабочем столе уже лежит новый обязательный шаг.") {
  window.clearTimeout(advanceTimer);
  shell.querySelector(".lwb-advance-notice")?.remove();
  const notice = element("div", "lwb-advance-notice", { role: "status" });
  notice.innerHTML = `<span aria-hidden="true">✓</span><div><strong>${title}</strong><small>${description}</small></div>`;
  shell.append(notice);
  requestAnimationFrame(() => notice.classList.add("is-visible"));
  advanceTimer = window.setTimeout(() => {
    notice.classList.remove("is-visible");
    window.setTimeout(() => notice.remove(), 260);
  }, 3600);
}

function enhanceLearningHome(root) {
  if (!root || root.dataset.learningWorkbenchEnhanced === "true") return;
  document.querySelector(".lwb-course-advance")?.remove();
  root.dataset.learningWorkbenchEnhanced = "true";
  root.classList.add("learning-workbench-source");

  const signature = taskSignature(root);
  const previousSignature = readStorage(TASK_SIGNATURE_KEY);
  const forcedTaskPanel = readStorage(FORCE_TASK_PANEL_KEY) === "true";
  const taskChanged = Boolean(signature && previousSignature && signature !== previousSignature);
  if (signature) writeStorage(TASK_SIGNATURE_KEY, signature);
  removeStorage(FORCE_TASK_PANEL_KEY);

  const hero = directChildren(root, ".learning-hero")[0] || root.querySelector(".learning-hero");
  const currentTask = directChildren(root, ".learning-now")[0] || root.querySelector(".learning-now");
  const passport = hero?.querySelector(".learning-passport") || root.querySelector(".learning-passport");
  const progress = textOf(passport?.querySelector(".learning-passport-head strong"));
  const taskTitle = textOf(root.querySelector("#learning-now-title"));
  const alerts = directChildren(root, ".alert");

  const trackPicker = root.querySelector(".learning-track-picker");
  const achievementShelf = root.querySelector(".training-achievement-shelf");
  const safetyGate = root.querySelector(".learning-safety-gate");
  const workMap = root.querySelector(".work-map-section");
  const folderNodes = new Map([
    ["route", trackPicker],
    ["process", workMap],
    ["rules", safetyGate],
    ["results", achievementShelf],
  ]);

  const allHeadings = directChildren(root, ".learning-section-heading");
  const courseHeading = allHeadings.find((node) => !node.classList.contains("learning-section-heading--optional"));
  const optionalHeading = allHeadings.find((node) => node.classList.contains("learning-section-heading--optional"));
  const courseGrid = directChildren(root, ".course-grid")[0] || root.querySelector(".course-grid");
  const examCards = directChildren(root, ".premium-exam-card");
  const invitations = directChildren(root, ".first-shift-invite");
  const unlocked = workspaceIsUnlocked(root);

  if (passport) passport.remove();

  const taskPanel = makeTaskPanel(hero, alerts, currentTask);
  const filesPanel = makeFolderDesk(folderNodes);
  const coursesPanel = makeGenericPanel(
    "courses",
    "Очередь производственных задач",
    "Обучение как работа",
    "Каждый блок — отдельная задача. Откройте текущую, выполните её и вернитесь на рабочий стол: следующая появится автоматически.",
    [courseHeading, courseGrid],
  );
  const accessPanel = makeGenericPanel(
    "access",
    "Финальный допуск к рабочим приложениям",
    "Контроль качества",
    "Сначала покажите навык на пробном ролике, затем решите рабочие сценарии. Серверный статус и текущие кнопки сохранены без изменений.",
    examCards,
  );
  const practicePanel = makeGenericPanel(
    "practice",
    "Безопасные тренажёры полной смены",
    "Можно ошибаться",
    "Здесь ничего не публикуется и не списывается. Репетируйте процесс целиком или отдельно запуск аккаунтов.",
    [optionalHeading, ...invitations],
  );

  const shell = element("section", "learning-workbench", { "aria-label": "Учебный рабочий стол" });
  const menubar = makeMenubar(progress, taskTitle);
  const desktop = element("div", "lwb-desktop");
  const sidebar = makeSidebar();
  const windowNode = makeWindow([taskPanel, filesPanel, coursesPanel, accessPanel, practicePanel]);
  const queue = queueMarkup(passport);
  desktop.append(sidebar, windowNode, queue);
  const dock = makeDock(unlocked);
  shell.append(menubar, desktop, dock);

  root.replaceChildren(shell);
  activeShell = shell;
  document.documentElement.dataset.learningWorkbench = "home";

  const savedPanel = validPanelId(readStorage(PANEL_STORAGE_KEY, "task"));
  const initialPanel = taskChanged || forcedTaskPanel ? "task" : savedPanel;
  setPanelImmediate(shell, initialPanel, { persist: false });
  setFolder(shell, readStorage(FOLDER_STORAGE_KEY, "route"), { persist: false });

  if (taskChanged || forcedTaskPanel) {
    shell.classList.add("is-task-advance");
    showAdvanceNotice(shell);
    window.setTimeout(() => shell.classList.remove("is-task-advance"), 1200);
  }
}

function makeCourseChrome(root) {
  if (root.querySelector(".lwb-course-chrome")) return;
  const title = textOf(root.querySelector(".course-hero h1"));
  const status = textOf(root.querySelector(".course-hero .badge"));
  const chrome = element("header", "lwb-course-chrome");
  chrome.innerHTML = `
    <a href="#/learn" aria-label="Вернуться на учебный рабочий стол">← <span>Рабочий стол</span></a>
    <div><small>Открытая задача</small><strong>${title || "Учебный блок"}</strong></div>
    <span class="lwb-course-chrome__status"><i></i>${status || "В работе"}</span>
  `;
  root.prepend(chrome);
}

function courseIsConfirmedComplete(root) {
  const successBadge = [...root.querySelectorAll(".course-hero .badge, .course-completion-card .alert")]
    .some((node) => /курс пройден|уже пройден|пройден/i.test(textOf(node)));
  return successBadge;
}

function showCourseAdvanceOverlay(root) {
  if (root.querySelector(".lwb-course-advance")) return;
  const overlay = element("div", "lwb-course-advance", { role: "status", "aria-live": "assertive" });
  overlay.innerHTML = `
    <div class="lwb-course-advance__mark" aria-hidden="true">✓</div>
    <p class="eyebrow">Задача выполнена</p>
    <h2>Освобождаем стол для следующего этапа</h2>
    <p>Результат сохранён. Сейчас откроется новый рабочий стол с одной следующей задачей.</p>
    <div class="lwb-course-advance__line" aria-hidden="true"><span></span></div>
  `;
  document.body.append(overlay);
  requestAnimationFrame(() => overlay.classList.add("is-visible"));
}

function enhanceCoursePage(root) {
  if (!root) return;
  root.classList.add("learning-workbench-course");
  document.documentElement.dataset.learningWorkbench = "course";
  makeCourseChrome(root);

  const pending = readStorage(COURSE_ADVANCE_PENDING_KEY) === "true";
  if (!pending || !courseIsConfirmedComplete(root)) return;
  removeStorage(COURSE_ADVANCE_PENDING_KEY);
  writeStorage(FORCE_TASK_PANEL_KEY, "true");
  showCourseAdvanceOverlay(root);
  window.setTimeout(() => {
    window.location.hash = "#/learn";
  }, reducedMotion?.matches ? 120 : 1050);
}

function cleanupLearningWorkbenchState() {
  if (normalizedPath().startsWith("/learn")) return;
  activeShell = null;
  delete document.documentElement.dataset.learningWorkbench;
  document.querySelector(".lwb-course-advance")?.remove();
}

function enhanceCurrentView() {
  enhancementQueued = false;
  if (!appRoot) return;
  if (isLearningHome()) {
    const home = appRoot.querySelector(".learning-page:not(.course-page)");
    if (home) enhanceLearningHome(home);
    return;
  }
  if (isCoursePath()) {
    enhanceCoursePage(appRoot.querySelector(".course-page"));
    return;
  }
  cleanupLearningWorkbenchState();
}

function scheduleEnhancement() {
  if (enhancementQueued) return;
  enhancementQueued = true;
  requestAnimationFrame(enhanceCurrentView);
}

function handlePanelKeydown(event) {
  const tab = event.target.closest?.("[data-lwb-panel]");
  if (!tab) return;
  const keys = ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Home", "End"];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  const buttons = [...tab.closest('[role="tablist"]').querySelectorAll("[data-lwb-panel]")];
  const index = Math.max(0, buttons.indexOf(tab));
  let nextIndex = index;
  if (["ArrowDown", "ArrowRight"].includes(event.key)) nextIndex = (index + 1) % buttons.length;
  if (["ArrowUp", "ArrowLeft"].includes(event.key)) nextIndex = (index - 1 + buttons.length) % buttons.length;
  if (event.key === "Home") nextIndex = 0;
  if (event.key === "End") nextIndex = buttons.length - 1;
  buttons[nextIndex].focus();
  switchPanel(tab.closest(".learning-workbench"), buttons[nextIndex].dataset.lwbPanel);
}

document.addEventListener("click", (event) => {
  const completionButton = event.target.closest?.('[data-action="complete-course"]');
  if (completionButton && !completionButton.disabled) {
    writeStorage(COURSE_ADVANCE_PENDING_KEY, "true");
  }

  const panelButton = event.target.closest?.("[data-lwb-panel]");
  if (panelButton) {
    switchPanel(panelButton.closest(".learning-workbench"), panelButton.dataset.lwbPanel, { focus: true });
    return;
  }

  const folderButton = event.target.closest?.("[data-lwb-folder]");
  if (folderButton) {
    setFolder(folderButton.closest(".learning-workbench"), folderButton.dataset.lwbFolder);
    return;
  }

  const shell = event.target.closest?.(".learning-workbench");
  if (shell && event.target.closest?.("[data-lwb-prev]")) cyclePanel(shell, -1);
  if (shell && event.target.closest?.("[data-lwb-next]")) cyclePanel(shell, 1);
}, true);

document.addEventListener("keydown", handlePanelKeydown);
window.addEventListener("hashchange", scheduleEnhancement);

const observer = new MutationObserver(scheduleEnhancement);
if (appRoot) observer.observe(appRoot, { childList: true, subtree: true });
scheduleEnhancement();
