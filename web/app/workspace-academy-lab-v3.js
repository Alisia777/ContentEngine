/*
 * ContentEngine Academy Lab v3.
 * Pairs existing lessons with their real safe simulators/practice blocks in a
 * split workspace. Original lesson, assessment and completion controls remain
 * authoritative and are moved, never cloned.
 */

const core = window.ContentEngineOSV3;
if (!core) throw new Error("ContentEngineOSV3 core must load before Academy Lab");

const {
  q, qa, elementFrom, icon, compact, escapeMarkup, routePath, enableSplit,
  remember, readMemory, animateIn, registerAdapter, registerCommand,
} = core;

const COURSE_DESTINATIONS = Object.freeze({
  factory_basics: { label: "Моя работа", route: "/workspace/work" },
  video_quality: { label: "Проверка контента", route: "/workspace/review" },
  publishing_funnel: { label: "Публикации", route: "/workspace/placement" },
  security_wb: { label: "Материалы", route: "/workspace/media" },
});

const runtime = {
  page: null,
  courseCode: "",
};

function courseCode(page) {
  return String(
    page?.dataset.courseCode
      || q("[data-course-lesson-player]", page)?.dataset.courseCode
      || q("[data-training-course]", page)?.dataset.trainingCourse
      || "",
  ).trim();
}

function directChildren(node) {
  return [...(node?.children || [])];
}

function isInteractiveNode(node) {
  if (!(node instanceof Element)) return false;
  if (node.matches("form, #course-check, .training-practical-card, .training-platform-simulator, [data-training-walkthrough], [data-training-course]")) return true;
  return Boolean(node.querySelector("form, #course-check, .training-practical-card, .training-platform-simulator, [data-training-walkthrough], [data-training-course]"));
}

function labHint(panel) {
  const title = compact(q("h1, h2, h3, strong", panel)?.textContent || "Практический шаг", 90);
  return `
    <div class="academy-lab-hint">
      <span>${icon("learn", 22)}</span>
      <div><small>ЛАБОРАТОРИЯ</small><strong>${escapeMarkup(title)}</strong><p>Сначала прочитайте задачу слева, затем выполните действие в безопасном тренажёре справа.</p></div>
    </div>`;
}

function setupLabPanel(panel, index, code) {
  if (!panel || panel.dataset.academyLabReady === "true") return false;
  const children = directChildren(panel);
  const interactive = children.filter(isInteractiveNode);
  const explanation = children.filter((node) => !interactive.includes(node));
  if (!interactive.length || !explanation.length) return false;
  panel.dataset.academyLabReady = "true";
  panel.classList.add("academy-lab-panel");
  const shell = elementFrom(`
    <section class="academy-lab-shell">
      <article class="academy-lab-theory"></article>
      <article class="academy-lab-practice"><div class="academy-lab-practice__scroll"></div></article>
    </section>`);
  panel.append(shell);
  const theory = q(".academy-lab-theory", shell);
  const practice = q(".academy-lab-practice__scroll", shell);
  theory.insertAdjacentHTML("afterbegin", labHint(panel));
  explanation.forEach((node) => theory.append(node));
  interactive.forEach((node) => practice.append(node));
  const destination = COURSE_DESTINATIONS[code];
  if (destination) {
    practice.insertAdjacentHTML("beforeend", `
      <div class="academy-lab-real-link">
        <span>${icon("work", 18)}</span>
        <div><small>ПОСЛЕ ТРЕНИРОВКИ</small><strong>Открыть настоящий рабочий стол</strong><p>Боевой раздел использует те же визуальные шаги, но уже сохраняет рабочий результат.</p></div>
        <a href="#${destination.route}">${escapeMarkup(destination.label)} →</a>
      </div>`);
  }
  enableSplit(shell, theory, q(".academy-lab-practice", shell), `academy:${code}:${index}`);
  return true;
}

function addLabToolbar(page, code) {
  let toolbar = q(":scope > .academy-lab-toolbar", page);
  if (toolbar) return toolbar;
  const destination = COURSE_DESTINATIONS[code];
  toolbar = elementFrom(`
    <header class="academy-lab-toolbar">
      <div><small>CONTENTENGINE ACADEMY</small><strong>Урок + безопасная практика</strong></div>
      <div>
        <button type="button" data-academy-lab-toggle>${icon("split", 17)}<span>Split View</span></button>
        ${destination ? `<a href="#${destination.route}">${icon("work", 17)}<span>${escapeMarkup(destination.label)}</span></a>` : ""}
        <button type="button" data-ce-open-mission>${icon("grid", 17)}</button>
      </div>
    </header>`);
  const anchor = q(":scope > .academy-course-os-topbar, :scope > .academy-v2-topbar, :scope > header", page) || page.firstElementChild;
  anchor?.after?.(toolbar);
  toolbar.addEventListener("click", (event) => {
    if (!(event.target instanceof Element) || !event.target.closest("[data-academy-lab-toggle]")) return;
    const collapsed = page.classList.toggle("academy-lab-collapsed");
    remember({ academyLabCollapsed: collapsed });
  });
  return toolbar;
}

function mountAcademyLab() {
  const route = routePath();
  if (!route.startsWith("/learn/")) {
    document.body.classList.remove("contentengine-academy-lab-open");
    runtime.page = null;
    return;
  }
  const page = q(".course-page, .academy-course-desktop-os, .academy-course-os-window--v2")?.closest?.(".learning-page, .page-wrap, #main-content") || q(".course-page");
  if (!page) return;
  runtime.page = page;
  runtime.courseCode = courseCode(page);
  document.body.classList.add("contentengine-academy-lab-open");
  page.classList.add("academy-lab-page");
  addLabToolbar(page, runtime.courseCode);
  const panels = qa(".academy-v2-panel, [data-ce-os-panel], [data-course-lesson]", page);
  let count = 0;
  panels.forEach((panel, index) => { if (setupLabPanel(panel, index, runtime.courseCode)) count += 1; });
  page.dataset.academyLabCount = String(count);
  page.classList.toggle("academy-lab-collapsed", readMemory().academyLabCollapsed === true);
}

registerCommand({
  id: "academy-lab",
  title: "Открыть Академию-лабораторию",
  subtitle: "Урок и безопасный тренажёр рядом",
  icon: "learn",
  keywords: "академия лаборатория обучение тренажер",
  run() { window.location.hash = "/learn"; },
});
registerAdapter("academy-lab-v3", mountAcademyLab);

document.addEventListener("keydown", (event) => {
  if (routePath().startsWith("/learn/") && event.shiftKey && event.key.toLowerCase() === "s" && !event.metaKey && !event.ctrlKey) {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest("input, textarea, select, button, [contenteditable='true']")) return;
    event.preventDefault();
    const page = runtime.page;
    if (!page) return;
    const collapsed = page.classList.toggle("academy-lab-collapsed");
    remember({ academyLabCollapsed: collapsed });
  }
}, true);
