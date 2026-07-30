/*
 * Academy Desktop OS v2
 * Rebuilds an already enhanced course page into a complete spatial route:
 * overview -> one lesson at a time -> practice and assessment. Existing lesson,
 * assessment and completion controls remain the original DOM nodes.
 */

const ACADEMY_PREFIX = "/learn/";
const STORAGE_PREFIX = "contentengine.academy-course-os.v2";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const runtime = {
  queued: false,
  page: null,
  window: null,
  panels: [],
  nav: null,
  groups: [],
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

function compact(value, limit = 74) {
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

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function panelTitle(node, fallback) {
  return compact(q("h1, h2, h3, .eyebrow, strong", node)?.textContent || fallback, 74);
}

function storageKey() {
  return `${STORAGE_PREFIX}:${routePath()}`;
}

function restoreIndex() {
  try { return Math.max(0, Number(window.sessionStorage.getItem(storageKey())) || 0); }
  catch { return 0; }
}

function persistIndex(index) {
  try { window.sessionStorage.setItem(storageKey(), String(index)); }
  catch { /* optional enhancement */ }
}

function animatePanel(previous, next, direction) {
  if (!next || REDUCED_MOTION.matches || typeof next.animate !== "function") return;
  previous?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 34}px,0,0) scale(.985)` },
  ], { duration: 170, easing: "ease-out" });
  next.animate([
    { opacity: 0, filter: "blur(5px)", transform: `translate3d(${direction * 48}px,0,0) scale(.978)` },
    { opacity: 1, filter: "blur(0)", transform: "translate3d(0,0,0) scale(1.004)" },
    { opacity: 1, filter: "none", transform: "translate3d(0,0,0) scale(1)" },
  ], { duration: 520, easing: SPRING });
}

function openNativeLesson(panel) {
  const lesson = q("[data-course-lesson]", panel);
  const details = q("[data-course-lesson-details]", lesson);
  if (!lesson || !details?.hidden) return;
  q('[data-action="training-lesson-toggle"]', lesson)?.click();
}

function setActive(index, focus = false) {
  if (!runtime.panels.length) return;
  const resolved = Math.max(0, Math.min(runtime.panels.length - 1, Number(index) || 0));
  const previous = runtime.panels.find((panel) => panel.classList.contains("is-active"));
  const previousIndex = previous ? runtime.panels.indexOf(previous) : resolved;
  runtime.panels.forEach((panel, panelIndex) => {
    const active = panelIndex === resolved;
    panel.classList.toggle("is-active", active);
    panel.setAttribute("aria-hidden", active ? "false" : "true");
    panel.inert = !active;
  });
  qa("[data-academy-v2-index]", runtime.nav).forEach((button) => {
    const active = Number(button.dataset.academyV2Index) === resolved;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "step" : "false");
  });
  const group = runtime.groups[resolved];
  q("[data-academy-v2-title]", runtime.window).textContent = group?.label || "Курс";
  q("[data-academy-v2-position]", runtime.window).textContent = `${resolved + 1} / ${runtime.panels.length}`;
  runtime.window.style.setProperty("--academy-v2-progress", `${((resolved + 1) / runtime.panels.length) * 100}%`);
  if (previous !== runtime.panels[resolved]) animatePanel(previous, runtime.panels[resolved], resolved >= previousIndex ? 1 : -1);
  openNativeLesson(runtime.panels[resolved]);
  persistIndex(resolved);
  if (focus) q("button, a, input, select, textarea", runtime.panels[resolved])?.focus({ preventScroll: true });
}

function collectCourseGroups(page) {
  const oldWindow = q(":scope > .academy-course-os-window", page);
  const layout = q(":scope > .course-layout", page);
  if (!oldWindow || !layout) return null;
  const main = layout.firstElementChild;
  const lessonStack = q(".lesson-stack", layout);
  const completion = q(".course-completion-card", layout);
  const lessons = qa("[data-course-lesson]", oldWindow)
    .sort((left, right) => Number(left.dataset.lessonIndex || 0) - Number(right.dataset.lessonIndex || 0));
  if (!main || !lessonStack || lessons.length < 2) return null;

  const directOverview = [...page.children].filter((node) => node !== oldWindow && node !== layout);
  const beforeLessons = [];
  const afterLessons = [];
  let passedStack = false;
  [...main.children].forEach((node) => {
    if (node === lessonStack) {
      passedStack = true;
      return;
    }
    (passedStack ? afterLessons : beforeLessons).push(node);
  });

  const groups = [{
    key: "overview",
    label: "Обзор курса",
    shortLabel: "Обзор",
    nodes: [...directOverview, ...beforeLessons],
  }];
  lessons.forEach((lesson, index) => groups.push({
    key: `lesson-${index + 1}`,
    label: panelTitle(lesson, `Урок ${index + 1}`),
    shortLabel: `Урок ${index + 1}`,
    nodes: [lesson],
  }));
  const practiceNodes = [...afterLessons];
  if (completion) practiceNodes.push(completion);
  qa(".lesson-group-heading", lessonStack).forEach((heading) => practiceNodes.unshift(heading));
  if (practiceNodes.length) groups.push({
    key: "practice",
    label: "Практика и аттестация",
    shortLabel: "Практика",
    nodes: practiceNodes,
  });
  return { groups, oldWindow, layout };
}

function rebuildCourse(page) {
  if (page.dataset.academyOsV2Ready === "true") return;
  const source = collectCourseGroups(page);
  if (!source) return;
  page.dataset.academyOsV2Ready = "true";
  page.classList.add("academy-course-desktop-os-v2");

  const courseTitle = compact(q(":scope > .course-hero h1", page)?.textContent || document.title, 96);
  const windowEl = elementFrom(`
    <section class="academy-course-os-window academy-course-os-window--v2" aria-label="Курс ${escapeMarkup(courseTitle)}">
      <header class="academy-os-topbar academy-v2-topbar">
        <div class="review-os-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
        <div><small>ContentEngine Academy · ${escapeMarkup(courseTitle)}</small><strong data-academy-v2-title>Обзор курса</strong></div>
        <span class="academy-v2-position" data-academy-v2-position></span>
      </header>
      <div class="academy-v2-progress" aria-hidden="true"><span></span></div>
      <div class="academy-course-os-panels academy-v2-panels"></div>
      <nav class="academy-course-os-dock academy-v2-dock" aria-label="Пространства курса"></nav>
    </section>`);
  const panelHost = q(".academy-v2-panels", windowEl);
  const nav = q(".academy-v2-dock", windowEl);

  source.groups.forEach((group, index) => {
    const panel = document.createElement("section");
    panel.className = `academy-course-os-panel academy-v2-panel academy-v2-panel--${group.key}`;
    panel.dataset.academyV2Panel = group.key;
    group.nodes.filter(Boolean).forEach((node) => panel.append(node));
    panelHost.append(panel);
    nav.insertAdjacentHTML("beforeend", `
      <button type="button" data-academy-v2-index="${index}" aria-label="${escapeMarkup(group.label)}">
        <span>${group.key.startsWith("lesson-") ? index : group.key === "practice" ? "✓" : "◎"}</span>
        <small>${escapeMarkup(group.shortLabel)}</small>
      </button>`);
  });

  source.oldWindow.before(windowEl);
  source.oldWindow.remove();
  source.layout.remove();
  runtime.page = page;
  runtime.window = windowEl;
  runtime.panels = qa(":scope > .academy-v2-panel", panelHost);
  runtime.nav = nav;
  runtime.groups = source.groups;
  nav.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-academy-v2-index]") : null;
    if (button) setActive(Number(button.dataset.academyV2Index), true);
  });
  setActive(Math.min(restoreIndex(), runtime.panels.length - 1));
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    const path = routePath();
    const page = q(".learning-page.course-page");
    if (!path.startsWith(ACADEMY_PREFIX) || !page) {
      runtime.page = null;
      runtime.window = null;
      runtime.panels = [];
      runtime.nav = null;
      runtime.groups = [];
      return;
    }
    rebuildCourse(page);
  });
}

function handleCourseAction(event) {
  if (!runtime.window || !runtime.page?.isConnected) return;
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  const lessonControl = target.closest('[data-action="training-lesson-open"][data-lesson-index], [data-action="training-lesson-understood"][data-lesson-index]');
  if (lessonControl) {
    const lessonIndex = Math.max(0, Number(lessonControl.dataset.lessonIndex) || 0);
    window.setTimeout(() => setActive(lessonIndex + 1), 0);
    return;
  }
  const assessment = target.closest('[data-action="scroll-to"][data-target="course-check"]');
  if (assessment) window.setTimeout(() => setActive(runtime.panels.length - 1), 0);
}

const observer = new MutationObserver(scheduleMount);
observer.observe(q("#app") || document.body, { childList: true, subtree: true });
document.addEventListener("click", handleCourseAction, true);
window.addEventListener("hashchange", scheduleMount, { passive: true });
scheduleMount();
