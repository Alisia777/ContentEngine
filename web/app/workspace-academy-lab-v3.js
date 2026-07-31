/*
 * ContentEngine Academy Lab v3.
 * Adds a reversible lesson + simulator split to the existing Academy OS.
 * Native lessons, simulators, assessments and completion controls remain the
 * same DOM nodes and keep their existing server behaviour.
 */

const COURSE_PREFIX = "/learn/";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const ICONS = Object.freeze({
  lab: '<path d="M9 3h6M10 3v5l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3"/><path d="M8 14h8"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  practice: '<path d="M5 20h14M7 20V8l5-5 5 5v12"/><path d="M9 12h6M9 16h6"/>',
  lesson: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 7h8M8 11h8M8 15h5"/>',
});

const runtime = {
  queued: false,
  page: null,
  window: null,
  lab: null,
  moved: [],
  activePanel: null,
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
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.lab}</svg>`;
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

function activePanel() {
  return q(".academy-v2-panel.is-active", runtime.window);
}

function candidateSimulator(panel) {
  return qa(
    ".training-platform-simulator, .training-practical-card, .training-practical-project, "
      + ".training-interactive, [data-training-walkthrough], #course-check-form, "
      + ".learning-assessment-grid, .course-completion-card, form",
    panel,
  ).find((node) => !node.closest("[hidden]") && !node.hidden);
}

function candidateLesson(panel, simulator) {
  const lesson = q("[data-course-lesson-details], [data-course-lesson], .course-lesson, .lesson-copy", panel);
  if (lesson && lesson !== simulator && !lesson.contains(simulator)) return lesson;
  return qa(":scope > *", panel).find((node) => node !== simulator && !node.contains(simulator)) || null;
}

function moveNode(node, target) {
  if (!(node instanceof Element) || !(target instanceof Element)) return false;
  const placeholder = document.createComment("contentengine-academy-lab-placeholder");
  node.before(placeholder);
  target.append(node);
  runtime.moved.push({ node, placeholder });
  return true;
}

function restoreNodes() {
  runtime.moved.splice(0).reverse().forEach(({ node, placeholder }) => {
    if (placeholder?.parentNode && node) placeholder.before(node);
    placeholder?.remove?.();
  });
}

function fallbackPractice(panel) {
  const title = compact(q("h1, h2, h3, strong", panel)?.textContent || "Практика урока", 100);
  return elementFrom(`
    <section class="academy-lab-fallback">
      <span>${icon("practice", 30)}</span>
      <small>БЕЗОПАСНАЯ ЛАБОРАТОРИЯ</small>
      <h2>${escapeMarkup(title)}</h2>
      <p>На этом шаге нет отдельного тренажёра. Используйте лабораторию как короткую проверку решения перед переходом к практике курса.</p>
      <ol><li>Назовите точный объект работы.</li><li>Определите стоп-условие.</li><li>Сформулируйте доказательство готовности.</li></ol>
      <button type="button" data-academy-lab-open-practice>Перейти к практике курса</button>
    </section>`);
}

function createLab(panel) {
  const title = compact(q("h1, h2, h3, strong", panel)?.textContent || "Учебная лаборатория", 110);
  return elementFrom(`
    <section class="academy-lab" role="dialog" aria-modal="false" aria-labelledby="academy-lab-title">
      <header>
        <div><small>ACADEMY LAB</small><strong id="academy-lab-title">${escapeMarkup(title)}</strong></div>
        <div class="academy-lab-mode"><button type="button" data-academy-lab-ratio="58">Урок 58%</button><button type="button" data-academy-lab-ratio="50">50 / 50</button><button type="button" data-academy-lab-ratio="42">Практика 58%</button></div>
        <button type="button" data-academy-lab-close aria-label="Закрыть лабораторию">${icon("close", 18)}</button>
      </header>
      <div class="academy-lab-body">
        <section class="academy-lab-lesson" aria-label="Объяснение"><header><span>${icon("lesson", 18)}</span><div><small>ОБЪЯСНЕНИЕ</small><strong>Что и почему</strong></div></header><div data-academy-lab-lesson></div></section>
        <div class="academy-lab-divider" aria-hidden="true"></div>
        <section class="academy-lab-practice" aria-label="Тренажёр"><header><span>${icon("practice", 18)}</span><div><small>ПРАКТИКА</small><strong>Сделать руками</strong></div></header><div data-academy-lab-practice></div></section>
      </div>
      <footer><span>Ошибаться здесь можно: боевые API вызываются только штатными кнопками существующего курса.</span><button type="button" data-academy-lab-handoff>Зафиксировать вывод</button></footer>
    </section>`);
}

function openLab() {
  if (runtime.lab) return;
  const panel = activePanel();
  if (!panel) return;
  runtime.activePanel = panel;
  const lab = createLab(panel);
  const lessonTarget = q("[data-academy-lab-lesson]", lab);
  const practiceTarget = q("[data-academy-lab-practice]", lab);
  const simulator = candidateSimulator(panel);
  const lesson = candidateLesson(panel, simulator);
  if (!moveNode(lesson, lessonTarget)) {
    lessonTarget.append(elementFrom('<div class="academy-lab-fallback-copy"><strong>Объяснение остаётся в текущем уроке</strong><p>Откройте детали урока и используйте правую часть как безопасную практику.</p></div>'));
  }
  if (!moveNode(simulator, practiceTarget)) practiceTarget.append(fallbackPractice(panel));
  panel.append(lab);
  runtime.lab = lab;
  runtime.window.classList.add("academy-lab-open");
  document.body.classList.add("contentengine-academy-lab-open");
  const ratio = Math.max(38, Math.min(62, Number(window.localStorage.getItem("contentengine.academy-lab-ratio")) || 52));
  lab.style.setProperty("--academy-lab-lesson", `${ratio}%`);
  lab.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest("[data-academy-lab-close]")) closeLab();
    const ratioButton = event.target.closest("[data-academy-lab-ratio]");
    if (ratioButton) {
      const next = Math.max(38, Math.min(62, Number(ratioButton.dataset.academyLabRatio) || 52));
      lab.style.setProperty("--academy-lab-lesson", `${next}%`);
      try { window.localStorage.setItem("contentengine.academy-lab-ratio", String(next)); } catch { /* optional */ }
    }
    if (event.target.closest("[data-academy-lab-open-practice]")) {
      closeLab();
      const buttons = qa("[data-academy-v2-index]", runtime.window);
      buttons.at(-1)?.click();
    }
    if (event.target.closest("[data-academy-lab-handoff]")) window.ContentEngineOSV3?.openHandoff?.();
  });
  lab.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeLab();
    }
  });
  if (!REDUCED_MOTION.matches && typeof lab.animate === "function") {
    lab.animate([
      { opacity: 0, transform: "translate3d(0,18px,0) scale(.978)", filter: "blur(6px)" },
      { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "blur(0)" },
    ], { duration: 440, easing: SPRING });
  }
  q("[data-academy-lab-close]", lab)?.focus({ preventScroll: true });
}

function closeLab() {
  const lab = runtime.lab;
  if (!lab) return;
  lab.classList.add("is-closing");
  const finish = () => {
    restoreNodes();
    lab.remove();
    runtime.lab = null;
    runtime.window?.classList.remove("academy-lab-open");
    document.body.classList.remove("contentengine-academy-lab-open");
    q("[data-academy-lab-open]", runtime.window)?.focus({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 230);
}

function mountButton(windowEl) {
  const topbar = q(".academy-v2-topbar", windowEl);
  if (!topbar || q("[data-academy-lab-open]", topbar)) return;
  const button = elementFrom(`<button class="academy-lab-open-button" type="button" data-academy-lab-open>${icon("lab", 17)}<span>Лаборатория</span></button>`);
  topbar.append(button);
  button.addEventListener("click", openLab);
}

function mount() {
  const path = routePath();
  const page = q(".learning-page.course-page");
  const windowEl = q(".academy-course-os-window--v2", page);
  if (!path.startsWith(COURSE_PREFIX) || !page || !windowEl) {
    if (runtime.lab) closeLab();
    runtime.page = null;
    runtime.window = null;
    return;
  }
  runtime.page = page;
  runtime.window = windowEl;
  page.classList.add("academy-lab-v3-ready");
  mountButton(windowEl);
  if (runtime.lab && runtime.activePanel !== activePanel()) closeLab();
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

new MutationObserver(scheduleMount).observe(q("#app") || document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("click", (event) => {
  if (runtime.lab && event.target instanceof Element && event.target.closest("[data-academy-v2-index]")) closeLab();
}, true);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
