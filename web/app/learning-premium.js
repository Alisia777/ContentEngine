/*
 * Learning Premium Experience v3
 * Progressive enhancement for the learning home. It never writes training state,
 * calls an API, changes access rules or replaces actions created by app.js.
 */

const LEARNING_HOME_SELECTOR = ".learning-page:not(.course-page)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";

let currentRoot = null;
let currentAbortController = null;
let mountQueued = false;

function isLearningHomeRoute() {
  const raw = String(window.location.hash || "#/learn");
  const path = raw.replace(/^#/, "").split("?")[0].replace(/\/$/, "") || "/";
  return path === "/learn";
}

function queueMount() {
  if (mountQueued) return;
  mountQueued = true;
  window.requestAnimationFrame(() => {
    mountQueued = false;
    mountLearningPremiumExperience();
  });
}

function cleanupCurrentMount() {
  currentAbortController?.abort();
  currentAbortController = null;
  currentRoot = null;
  document.querySelector(".learning-premium-scroll-progress")?.remove();
}

function createElement(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function addHeroAtmosphere(root) {
  const hero = root.querySelector(".learning-hero");
  if (!hero || hero.querySelector(".learning-premium-hero-canvas")) return;

  const canvas = createElement(`
    <div class="learning-premium-hero-canvas" aria-hidden="true">
      <span class="learning-premium-orbit learning-premium-orbit--one"></span>
      <span class="learning-premium-orbit learning-premium-orbit--two"></span>
      <span class="learning-premium-scan"></span>
    </div>
  `);
  hero.prepend(canvas);

  const copy = hero.querySelector(".learning-hero-copy");
  const actions = copy?.querySelector(".learning-hero-actions");
  if (copy && actions && !copy.querySelector(".learning-premium-hero-facts")) {
    const facts = createElement(`
      <div class="learning-premium-hero-facts" aria-label="Как устроено обучение">
        <span>6 этапов допуска</span>
        <span>Один главный шаг за раз</span>
        <span>Прогресс сохраняется</span>
      </div>
    `);
    copy.insertBefore(facts, actions);
  }
}

function sectionLabel(element, fallback) {
  return String(
    element?.querySelector("h1, h2, h3")?.textContent
    || fallback
    || "Раздел",
  ).trim();
}

function prepareSections(root) {
  const sections = [
    { id: "learning-next", label: "Сейчас", element: root.querySelector(".learning-now") },
    { id: "learning-role", label: "Моя роль", element: root.querySelector(".learning-track-picker") },
    { id: "learning-safety", label: "Стоп-правила", element: root.querySelector(".learning-safety-gate") },
    { id: "work-map", label: "Карта работы", element: root.querySelector("#work-map") },
    { id: "learning-courses", label: "Курсы", element: root.querySelector(".course-grid") },
    { id: "learning-assessment", label: "Допуск", element: root.querySelector(".learning-assessment-grid") || root.querySelector(".training-practical-card") },
  ].filter((item) => item.element);

  sections.forEach((item) => {
    item.element.id = item.id;
    item.element.dataset.learningPremiumSection = item.id;
    item.title = sectionLabel(item.element, item.label);
  });

  return sections;
}

function groupAssessmentCards(root) {
  if (root.querySelector(".learning-assessment-grid")) return;
  const practical = root.querySelector(".training-practical-card");
  const exam = [...root.querySelectorAll(".premium-exam-card")]
    .find((card) => !card.classList.contains("training-practical-card"));
  if (!practical || !exam) return;

  const wrapper = document.createElement("div");
  wrapper.className = "learning-assessment-grid";
  wrapper.id = "learning-assessment";
  wrapper.dataset.learningPremiumSection = "learning-assessment";
  practical.before(wrapper);
  wrapper.append(practical, exam);
}

function groupOptionalCards(root) {
  if (root.querySelector(".learning-option-grid")) return;
  const optionalHeading = root.querySelector(".learning-section-heading--optional");
  if (!optionalHeading) return;
  const cards = [];
  let sibling = optionalHeading.nextElementSibling;
  while (sibling && cards.length < 2) {
    if (sibling.matches(".first-shift-invite")) cards.push(sibling);
    sibling = sibling.nextElementSibling;
  }
  if (!cards.length) return;

  const wrapper = document.createElement("div");
  wrapper.className = "learning-option-grid";
  optionalHeading.after(wrapper);
  cards.forEach((card) => wrapper.append(card));
}

function progressValue(root) {
  const strong = root.querySelector(".learning-passport-head strong");
  const value = Number.parseInt(String(strong?.textContent || "0").replace(/\D/g, ""), 10);
  return Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0;
}

function addCommandBar(root, sections) {
  if (root.querySelector(".learning-command-bar")) return root.querySelector(".learning-command-bar");
  const hero = root.querySelector(".learning-hero");
  if (!hero) return null;

  const progress = progressValue(root);
  const nextTitle = String(root.querySelector(".learning-now h2")?.textContent || "Продолжить обучение").trim();
  const bar = createElement(`
    <nav class="learning-command-bar" aria-label="Быстрая навигация по академии">
      <div class="learning-command-progress" style="--progress:${progress}" aria-label="Прогресс обучения ${progress}%">
        <strong data-learning-premium-progress>${progress}%</strong>
        <small>готово</small>
      </div>
      <div class="learning-command-links">
        ${sections.map((section, index) => `
          <button class="learning-command-link${index === 0 ? " is-active" : ""}" type="button" data-learning-scroll-target="${section.id}">
            ${section.label}
          </button>
        `).join("")}
      </div>
      <div class="learning-command-status" aria-live="polite">
        <small>Главный шаг</small>
        <strong>${escapeMarkup(nextTitle)}</strong>
      </div>
    </nav>
  `);
  hero.after(bar);
  return bar;
}

function escapeMarkup(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function addScrollProgress(root, signal) {
  document.querySelector(".learning-premium-scroll-progress")?.remove();
  const progress = createElement('<div class="learning-premium-scroll-progress" aria-hidden="true"><span></span></div>');
  document.body.append(progress);

  let frame = 0;
  const update = () => {
    frame = 0;
    if (!root.isConnected) return;
    const rect = root.getBoundingClientRect();
    const start = window.scrollY + rect.top;
    const total = Math.max(1, root.scrollHeight - window.innerHeight * 0.68);
    const value = Math.min(1, Math.max(0, (window.scrollY - start + 60) / total));
    progress.style.setProperty("--learning-scroll", value.toFixed(4));
  };
  const requestUpdate = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(update);
  };

  window.addEventListener("scroll", requestUpdate, { passive: true, signal });
  window.addEventListener("resize", requestUpdate, { passive: true, signal });
  update();
}

function bindCommandBar(bar, sections, signal) {
  if (!bar) return;
  const links = [...bar.querySelectorAll("[data-learning-scroll-target]")];
  const reduced = window.matchMedia(REDUCED_MOTION_QUERY).matches;

  links.forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.learningScrollTarget || "");
      target?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    }, { signal });
  });

  if (!("IntersectionObserver" in window)) return;
  const sectionById = new Map(sections.map((section) => [section.id, section.element]));
  const visible = new Map();
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => visible.set(entry.target.id, entry.intersectionRatio));
    const active = [...visible.entries()]
      .filter(([, ratio]) => ratio > 0)
      .sort((a, b) => b[1] - a[1])[0]?.[0];
    if (!active) return;
    links.forEach((link) => link.classList.toggle("is-active", link.dataset.learningScrollTarget === active));
  }, { rootMargin: "-18% 0px -58% 0px", threshold: [0, 0.18, 0.45, 0.72] });

  sectionById.forEach((element) => observer.observe(element));
  signal.addEventListener("abort", () => observer.disconnect(), { once: true });
}

function bindReveal(root, signal) {
  const candidates = [
    ...root.querySelectorAll(":scope > .card, :scope > .learning-section-heading, :scope > .course-grid, :scope > .learning-assessment-grid, :scope > .learning-option-grid"),
  ].filter((element) => !element.classList.contains("learning-hero") && !element.classList.contains("learning-command-bar"));

  candidates.forEach((element, index) => {
    element.dataset.premiumReveal = "true";
    element.style.setProperty("--reveal-delay", `${Math.min(index, 6) * 45}ms`);
  });

  if (window.matchMedia(REDUCED_MOTION_QUERY).matches || !("IntersectionObserver" in window)) {
    candidates.forEach((element) => element.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

  candidates.forEach((element) => observer.observe(element));
  signal.addEventListener("abort", () => observer.disconnect(), { once: true });
}

function bindPointerDepth(root, signal) {
  if (!window.matchMedia(FINE_POINTER_QUERY).matches || window.matchMedia(REDUCED_MOTION_QUERY).matches) return;
  const targets = [root.querySelector(".learning-hero"), ...root.querySelectorAll(".course-card")].filter(Boolean);

  targets.forEach((target) => {
    let frame = 0;
    let lastEvent = null;
    const update = () => {
      frame = 0;
      if (!lastEvent || !target.isConnected) return;
      const rect = target.getBoundingClientRect();
      const x = Math.min(1, Math.max(0, (lastEvent.clientX - rect.left) / rect.width));
      const y = Math.min(1, Math.max(0, (lastEvent.clientY - rect.top) / rect.height));
      target.style.setProperty("--pointer-x", `${(x * 100).toFixed(1)}%`);
      target.style.setProperty("--pointer-y", `${(y * 100).toFixed(1)}%`);
      if (target.classList.contains("course-card")) {
        target.style.setProperty("--tilt-y", `${((x - 0.5) * 3.2).toFixed(2)}deg`);
        target.style.setProperty("--tilt-x", `${((0.5 - y) * 2.6).toFixed(2)}deg`);
      }
      const passport = target.classList.contains("learning-hero") ? target.querySelector(".learning-passport") : null;
      if (passport) {
        passport.style.setProperty("--tilt-y", `${((x - 0.5) * 2.2).toFixed(2)}deg`);
        passport.style.setProperty("--tilt-x", `${((0.5 - y) * 1.8).toFixed(2)}deg`);
      }
    };
    const onMove = (event) => {
      lastEvent = event;
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    const onLeave = () => {
      target.style.setProperty("--pointer-x", "50%");
      target.style.setProperty("--pointer-y", "0%");
      target.style.setProperty("--tilt-x", "0deg");
      target.style.setProperty("--tilt-y", "0deg");
      const passport = target.querySelector?.(".learning-passport");
      passport?.style.setProperty("--tilt-x", "0deg");
      passport?.style.setProperty("--tilt-y", "0deg");
    };
    target.addEventListener("pointermove", onMove, { passive: true, signal });
    target.addEventListener("pointerleave", onLeave, { passive: true, signal });
  });
}

function bindDetailsMotion(root, signal) {
  if (window.matchMedia(REDUCED_MOTION_QUERY).matches) return;
  root.querySelectorAll(".learning-safety-gate details").forEach((details) => {
    details.addEventListener("toggle", () => {
      if (!details.open) return;
      const body = details.querySelector("p");
      body?.animate(
        [
          { opacity: 0, transform: "translateY(-6px)" },
          { opacity: 1, transform: "translateY(0)" },
        ],
        { duration: 260, easing: "cubic-bezier(0.16, 1, 0.3, 1)" },
      );
    }, { signal });
  });
}

function mountLearningPremiumExperience() {
  if (!isLearningHomeRoute()) {
    if (currentRoot) cleanupCurrentMount();
    return;
  }

  const root = document.querySelector(LEARNING_HOME_SELECTOR);
  if (!root || root === currentRoot) return;
  cleanupCurrentMount();

  currentRoot = root;
  currentAbortController = new AbortController();
  const { signal } = currentAbortController;
  root.classList.add("learning-premium-v3");
  root.dataset.learningPremiumMounted = "true";

  addHeroAtmosphere(root);
  groupAssessmentCards(root);
  groupOptionalCards(root);
  const sections = prepareSections(root);
  const commandBar = addCommandBar(root, sections);

  bindCommandBar(commandBar, sections, signal);
  bindReveal(root, signal);
  bindPointerDepth(root, signal);
  bindDetailsMotion(root, signal);
  addScrollProgress(root, signal);
}

const appRoot = document.querySelector("#app");
if (appRoot) {
  const observer = new MutationObserver(queueMount);
  observer.observe(appRoot, { childList: true, subtree: true });
}

window.addEventListener("hashchange", queueMount, { passive: true });
window.addEventListener("popstate", queueMount, { passive: true });
queueMount();
