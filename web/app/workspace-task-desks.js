/*
 * Task desks
 * Adds a previous/next task carousel to the existing full-desk focus mode.
 * It uses only public DOM controls from workspace-desks-v2.js and never touches APIs.
 */

const TASK_DESK_SELECTOR = '[data-workspace-focusable="true"]';
let syncQueued = false;

function taskDeskSurfaces() {
  return [...document.querySelectorAll(TASK_DESK_SELECTOR)].filter((surface) => surface.isConnected);
}

function focusedTaskDesk() {
  return document.querySelector(".workspace-task-focused");
}

function taskDeskTitle(surface) {
  const text = surface?.querySelector("h1, h2, h3, legend, strong")?.textContent || "Рабочая задача";
  return String(text).replace(/\s+/g, " ").trim().slice(0, 100);
}

function scheduleTaskDeskSync() {
  if (syncQueued) return;
  syncQueued = true;
  window.requestAnimationFrame(() => {
    syncQueued = false;
    syncTaskDeskCarousel();
  });
}

function taskDeskButton(direction, target, disabled) {
  const label = direction < 0 ? "Предыдущая задача" : "Следующая задача";
  const arrow = direction < 0 ? "←" : "→";
  return `
    <button class="workspace-task-carousel__button" type="button" data-task-desk-nav="${direction}" ${disabled ? "disabled" : ""} aria-label="${disabled ? `${label} отсутствует` : `${label}: ${escapeTaskDeskMarkup(taskDeskTitle(target))}`}">
      <span aria-hidden="true">${arrow}</span><small>${label}</small>
    </button>
  `;
}

function escapeTaskDeskMarkup(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function syncTaskDeskCarousel() {
  const current = focusedTaskDesk();
  if (!current) return;
  const chrome = current.querySelector(".workspace-focus-chrome");
  if (!chrome) return;
  const surfaces = taskDeskSurfaces();
  const index = surfaces.indexOf(current);
  if (index < 0) return;
  const previous = surfaces[index - 1] || null;
  const next = surfaces[index + 1] || null;
  const signature = `${index}:${surfaces.length}:${previous?.id || ""}:${next?.id || ""}`;
  let carousel = chrome.querySelector(".workspace-task-carousel");
  if (!carousel) {
    carousel = document.createElement("nav");
    carousel.className = "workspace-task-carousel";
    carousel.setAttribute("aria-label", "Переключение задач в режиме фокуса");
    const close = chrome.querySelector("[data-workspace-focus-close]");
    if (close) chrome.insertBefore(carousel, close);
    else chrome.append(carousel);
  }
  if (carousel.dataset.taskDeskSignature === signature) return;
  carousel.dataset.taskDeskSignature = signature;
  carousel.innerHTML = `
    ${taskDeskButton(-1, previous, !previous)}
    <span class="workspace-task-carousel__position"><small>Задача</small><strong>${index + 1} / ${surfaces.length}</strong></span>
    ${taskDeskButton(1, next, !next)}
  `;
}

function openTaskDesk(surface) {
  const button = surface?.querySelector(":scope > [data-workspace-focus-card]");
  button?.click();
  scheduleTaskDeskSync();
}

function switchTaskDesk(direction) {
  const current = focusedTaskDesk();
  if (!current) return;
  const surfaces = taskDeskSurfaces();
  const index = surfaces.indexOf(current);
  const target = surfaces[index + direction];
  if (!target) return;
  const close = current.querySelector("[data-workspace-focus-close]");
  close?.click();
  window.requestAnimationFrame(() => window.requestAnimationFrame(() => openTaskDesk(target)));
}

function handleTaskDeskClick(event) {
  const target = event.target instanceof Element ? event.target.closest("[data-task-desk-nav]") : null;
  if (!target) return;
  event.preventDefault();
  switchTaskDesk(Number(target.dataset.taskDeskNav) || 0);
}

function handleTaskDeskKeydown(event) {
  if (!focusedTaskDesk() || !event.altKey || event.shiftKey || event.metaKey || event.ctrlKey) return;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    switchTaskDesk(-1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    switchTaskDesk(1);
  }
}

function containsFocusChrome(node) {
  return node instanceof Element && (
    node.matches(".workspace-focus-chrome")
    || Boolean(node.querySelector(".workspace-focus-chrome"))
  );
}

if (document.body) new MutationObserver((entries) => {
  if (entries.some((entry) => [...entry.addedNodes].some(containsFocusChrome))) {
    scheduleTaskDeskSync();
  }
}).observe(document.body, { childList: true, subtree: true });

document.addEventListener("click", handleTaskDeskClick, true);
document.addEventListener("keydown", handleTaskDeskKeydown);
