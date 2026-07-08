function respectReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function initPetals() {
  if (respectReducedMotion()) return;
  const field = document.querySelector("[data-petal-field]");
  if (!field) return;
  const petals = [
    { x: "5vw", y: "25vh", size: 54, duration: 22, delay: -3, opacity: 0.78 },
    { x: "30vw", y: "14vh", size: 62, duration: 27, delay: -8, opacity: 0.84 },
    { x: "66vw", y: "11vh", size: 48, duration: 24, delay: -5, opacity: 0.74 },
    { x: "82vw", y: "73vh", size: 58, duration: 29, delay: -12, opacity: 0.76 },
    { x: "38vw", y: "80vh", size: 44, duration: 23, delay: -10, opacity: 0.66 },
    { x: "92vw", y: "38vh", size: 34, duration: 21, delay: -2, opacity: 0.58 },
  ];
  field.innerHTML = "";
  petals.forEach((petal, index) => {
    const node = document.createElement("span");
    node.className = "altea-petal";
    node.style.setProperty("--x", petal.x);
    node.style.setProperty("--y", petal.y);
    node.style.setProperty("--size", `${petal.size}px`);
    node.style.setProperty("--duration", `${petal.duration}s`);
    node.style.setProperty("--delay", `${petal.delay}s`);
    node.style.setProperty("--opacity", petal.opacity);
    node.style.setProperty("--rotate", `${index * 29 - 18}deg`);
    node.style.setProperty("--drift-x", index % 2 ? "-7vw" : "9vw");
    field.appendChild(node);
  });
}

function initSplashProgress() {
  const progress = document.querySelector("[data-splash-progress]");
  if (!progress) return;
  const track = progress.querySelector(".altea-progress__track span");
  const steps = [...progress.querySelectorAll("li")];
  const next = document.querySelector("[data-splash-next]");
  const advance = (stage) => {
    track.style.setProperty("--progress", `${stage * 50}%`);
    steps.forEach((step, index) => {
      step.classList.toggle("is-complete", index < stage);
      step.classList.toggle("is-active", index === stage);
    });
    if (stage >= steps.length - 1) {
      window.setTimeout(() => next?.classList.add("is-visible"), 600);
    }
  };
  [0, 1, 2].forEach((stage) => window.setTimeout(() => advance(stage), 500 + stage * 900));
}

function initLoginInteractions() {
  const form = document.querySelector("[data-login-form]");
  if (!form) return;
  const toggle = form.querySelector("[data-toggle-password]");
  const input = form.querySelector("[data-password-input]");
  toggle?.addEventListener("click", () => {
    input.type = input.type === "password" ? "text" : "password";
    toggle.setAttribute("aria-label", input.type === "password" ? "Показать пароль" : "Скрыть пароль");
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    document.body.classList.add("is-transitioning");
    window.setTimeout(() => {
      window.location.href = "/altea-motion/auth-loading";
    }, respectReducedMotion() ? 10 : 260);
  });
}

function initAuthLoading() {
  const holder = document.querySelector("[data-auth-loading]");
  if (!holder) return;
  const steps = [...holder.querySelectorAll("[data-auth-steps] li")];
  const advance = (stage) => {
    steps.forEach((step, index) => {
      step.classList.toggle("is-complete", index < stage);
      step.classList.toggle("is-active", index === stage);
    });
  };
  [0, 1, 2].forEach((stage) => window.setTimeout(() => advance(stage), 450 + stage * 900));
  window.setTimeout(() => {
    window.location.href = "/altea-motion/dashboard-loading";
  }, respectReducedMotion() ? 60 : 3400);
}

function initDashboardLoading() {
  if (!document.querySelector("[data-dashboard-loading]")) return;
  window.setTimeout(() => {
    window.location.href = "/altea-motion/dashboard";
  }, respectReducedMotion() ? 60 : 2600);
}

function initDashboardReveal() {
  const reveal = [...document.querySelectorAll(".altea-dashboard .altea-reveal")];
  reveal.forEach((node, index) => {
    node.style.animationDelay = `${Math.min(index * 55, 520)}ms`;
  });
}

function initChartDraw() {
  const chart = document.querySelector(".altea-chart__line");
  if (!chart || respectReducedMotion()) return;
  const length = chart.getTotalLength ? chart.getTotalLength() : 1000;
  chart.style.strokeDasharray = length;
  chart.style.strokeDashoffset = length;
}

document.addEventListener("DOMContentLoaded", () => {
  initPetals();
  initSplashProgress();
  initLoginInteractions();
  initAuthLoading();
  initDashboardLoading();
  initDashboardReveal();
  initChartDraw();
});
