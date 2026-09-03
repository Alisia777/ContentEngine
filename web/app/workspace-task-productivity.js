/* Active task Dock, Mission Control enrichment and productivity controls. */

import {
  PRODUCTIVITY_TASK_SELECTOR,
  PRODUCTIVITY_TYPING_SELECTOR,
  PRODUCTIVITY_WIP_LIMIT,
  activeDockTasks,
  announce,
  currentTask,
  elementFrom,
  escapeMarkup,
  isProductivityRoute,
  parkedTasks,
  persistMemory,
  pinTask,
  q,
  qa,
  routePath,
  routeQuery,
  scanTasks,
  schedulePersist,
  state,
  taskTone,
} from "./workspace-task-productivity-core.js?v=20260826.rebuild-clean.60";
import {
  closeContextPanel,
  closeParkDialog,
  consumePendingTask,
  copyTaskLink,
  handlePanelChange,
  handlePanelInput,
  openParkDialog,
  openTask,
  panelElement,
  panelIsOpen,
  parkElement,
  parkIsOpen,
  renderContextPanel,
  submitParkDialog,
} from "./workspace-task-productivity-panel.js?v=20260826.rebuild-clean.60";

function chipMarkup(task) {
  const parked = task.parked && taskTone(task) !== "return";
  return `
    <div class="workspace-task-dock__chip" data-tone="${escapeMarkup(taskTone(task))}" data-task-chip-key="${escapeMarkup(task.key)}">
      <button class="workspace-task-dock__select" type="button" data-productivity-context="${escapeMarkup(task.key)}" title="Открыть контекст задачи">
        <span class="workspace-task-dock__dot" aria-hidden="true"></span>
        <span class="workspace-task-dock__copy"><strong>${escapeMarkup(task.title)}</strong><small>${escapeMarkup(parked ? task.parked.reason : task.statusLabel)}</small></span>
      </button>
      <button class="workspace-task-dock__open" type="button" data-productivity-open="${escapeMarkup(task.key)}" aria-label="Открыть задачу ${escapeMarkup(task.title)}">↗</button>
    </div>
  `;
}

function renderDock() {
  if (!state.shell) return;
  let dock = q(".workspace-task-dock", state.shell);
  if (!dock) {
    dock = document.createElement("aside");
    dock.className = "workspace-task-dock";
    dock.setAttribute("aria-label", "Dock активных задач");
    state.shell.append(dock);
  }
  state.dock = dock;
  const tasks = activeDockTasks();
  const waiting = parkedTasks();
  const pinnedCount = [...state.tasks.values()].filter((task) => task.pinned && !task.parked).length;
  const first = scanTasks()[0]?.task || null;
  const signature = JSON.stringify({
    tasks: tasks.map((task) => [task.key, task.updatedAt, taskTone(task)]),
    waiting: waiting.map((task) => [task.key, task.updatedAt]),
    pinnedCount,
    collapsed: state.memory.dockCollapsed,
    first: first?.key || "",
  });
  if (dock.dataset.productivitySignature === signature) return;
  dock.dataset.productivitySignature = signature;
  dock.classList.toggle("is-collapsed", state.memory.dockCollapsed);
  dock.innerHTML = `
    <div class="workspace-task-dock__bar">
      <button class="workspace-task-dock__summary" type="button" data-productivity-dock-toggle aria-expanded="${state.memory.dockCollapsed ? "false" : "true"}">
        <span class="workspace-task-dock__mark" aria-hidden="true">◆</span>
        <span><small>Активные задачи</small><strong>${pinnedCount || tasks.length} / ${PRODUCTIVITY_WIP_LIMIT}</strong></span>
        ${pinnedCount > PRODUCTIVITY_WIP_LIMIT ? '<em>Перегруз</em>' : ""}
      </button>
      <div class="workspace-task-dock__tasks">${tasks.map(chipMarkup).join("") || '<span class="workspace-task-dock__empty">Закрепите задачу — она останется под рукой</span>'}</div>
      <div class="workspace-task-dock__actions">
        ${first && !first.pinned ? `<button type="button" data-productivity-pin="${escapeMarkup(first.key)}" title="Закрепить текущую задачу">＋</button>` : ""}
        <button type="button" data-productivity-open-overview title="Открыть Mission Control">▦</button>
        ${waiting.length ? `<button type="button" data-productivity-waiting title="Показать ожидающие задачи">◷<span>${waiting.length}</span></button>` : ""}
      </div>
    </div>
  `;
}

function decorateTasks(descriptors = scanTasks()) {
  for (const { task, surface } of descriptors) {
    let actions = q(":scope > .workspace-task-quick-actions", surface);
    if (!actions) {
      actions = elementFrom('<div class="workspace-task-quick-actions" aria-label="Быстрые действия задачи"></div>');
      surface.append(actions);
    }
    const signature = `${task.key}:${task.pinned}:${Boolean(task.parked)}:${task.updatedAt}`;
    if (actions.dataset.productivitySignature === signature) continue;
    actions.dataset.productivitySignature = signature;
    actions.innerHTML = `
      <button class="workspace-task-quick-action" type="button" data-productivity-context="${escapeMarkup(task.key)}" title="Контекст задачи" aria-label="Открыть контекст задачи">☰</button>
      <button class="workspace-task-quick-action${task.pinned ? " is-active" : ""}" type="button" data-productivity-pin="${escapeMarkup(task.key)}" title="${task.pinned ? "Открепить" : "Закрепить в Dock"}" aria-label="${task.pinned ? "Открепить задачу" : "Закрепить задачу в Dock"}">${task.pinned ? "◆" : "◇"}</button>
      <button class="workspace-task-quick-action${task.parked ? " is-parked" : ""}" type="button" data-productivity-park="${escapeMarkup(task.key)}" title="${task.parked ? "Вернуть в работу" : "Припарковать"}" aria-label="${task.parked ? "Вернуть задачу в работу" : "Припарковать задачу"}">${task.parked ? "▶" : "◷"}</button>
    `;
  }
}

function enhanceMissionControl() {
  const overlay = document.querySelector(".workspace-overview");
  if (!overlay) return;
  const body = q(".workspace-overview__body", overlay);
  if (!body) return;
  const active = [...state.tasks.values()].filter((task) => task.pinned || task.parked)
    .sort((left, right) => Number(right.updatedAt || 0) - Number(left.updatedAt || 0));
  const signature = active.map((task) => `${task.key}:${task.updatedAt}:${taskTone(task)}`).join("|");
  let section = q("[data-productivity-overview-section]", body);
  if (!active.length) {
    section?.remove();
  } else {
    if (!section) {
      section = document.createElement("section");
      section.className = "workspace-overview__section workspace-overview__section--productivity";
      section.dataset.productivityOverviewSection = "true";
      body.prepend(section);
    }
    if (section.dataset.productivitySignature !== signature) {
      section.dataset.productivitySignature = signature;
      section.innerHTML = `
        <div class="workspace-overview__section-head"><strong>Оперативное внимание</strong><span>${active.filter((task) => task.pinned && !task.parked).length} активных · ${active.filter((task) => task.parked).length} ждут</span></div>
        <div class="workspace-overview__grid">${active.map((task, index) => `
          <article class="workspace-overview-card workspace-overview-productivity" data-tone="${escapeMarkup(taskTone(task))}" data-overview-keywords="${escapeMarkup(`${task.title} ${task.hint} ${task.statusLabel} ${task.parked?.reason || ""}`.toLocaleLowerCase("ru-RU"))}">
            <span class="workspace-overview-card__top"><span class="workspace-overview-card__number" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span><span class="workspace-overview-card__group">${task.parked ? "Ожидание" : "Dock"}</span></span>
            <span class="workspace-overview-card__copy"><strong>${escapeMarkup(task.title)}</strong><small>${escapeMarkup(task.parked?.reason || task.statusLabel)}</small></span>
            <span class="workspace-overview-productivity__actions"><button type="button" data-productivity-context="${escapeMarkup(task.key)}">Контекст</button><button type="button" data-productivity-open="${escapeMarkup(task.key)}">Открыть →</button></span>
          </article>
        `).join("")}</div>
      `;
    }
  }

  qa("[data-overview-focus-id]", overlay).forEach((card) => {
    const surface = document.getElementById(card.dataset.overviewFocusId || "");
    const task = state.tasks.get(surface?.dataset?.productivityTaskKey || "");
    let badge = q(".workspace-overview-task-state", card);
    if (!task) { badge?.remove(); return; }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "workspace-overview-task-state";
      q(".workspace-overview-card__copy", card)?.append(badge);
    }
    badge.dataset.tone = taskTone(task);
    badge.textContent = task.parked ? task.parked.reason : task.pinned ? "В Dock" : task.statusLabel;
  });

  qa("[data-overview-route]", overlay).forEach((card) => {
    const count = [...state.tasks.values()].filter((task) => task.route === card.dataset.overviewRoute && (task.pinned || task.parked)).length;
    let badge = q(".workspace-overview-route-count", card);
    if (!count) { badge?.remove(); return; }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "workspace-overview-route-count";
      q(".workspace-overview-card__top", card)?.append(badge);
    }
    badge.textContent = String(count);
  });
}

function render() {
  if (!state.shell) return;
  const descriptors = scanTasks();
  decorateTasks(descriptors);
  renderDock();
  enhanceMissionControl();
  consumePendingTask(routeQuery().get("deskTask") || "");
  if (panelIsOpen() && state.selectedKey) renderContextPanel(state.selectedKey, false);
}

function scheduleMount() {
  if (state.mountQueued) return;
  state.mountQueued = true;
  window.requestAnimationFrame(() => {
    state.mountQueued = false;
    const shell = document.querySelector(".workspace-shell");
    if (!shell || !isProductivityRoute(routePath())) {
      state.dock?.remove();
      state.dock = null;
      state.shell = null;
      closeContextPanel(false);
      closeParkDialog(false);
      return;
    }
    state.shell = shell;
    shell.classList.add("workspace-productivity-enabled");
    render();
  });
}

function trapTab(event, container) {
  if (event.key !== "Tab" || !container) return;
  const items = qa("button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])", container)
    .filter((item) => !item.hidden && item.getAttribute("aria-hidden") !== "true");
  if (!items.length) return;
  if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1).focus(); }
  if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); }
}

function handleClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-productivity-context-close]")) { closeContextPanel(); return; }
  if (target.closest("[data-productivity-park-close]")) { closeParkDialog(); return; }
  const context = target.closest("[data-productivity-context]");
  if (context) { event.preventDefault(); renderContextPanel(context.dataset.productivityContext || ""); return; }
  const open = target.closest("[data-productivity-open]");
  if (open) { event.preventDefault(); openTask(open.dataset.productivityOpen || ""); return; }
  const pin = target.closest("[data-productivity-pin]");
  if (pin) {
    event.preventDefault();
    const task = state.tasks.get(pin.dataset.productivityPin || "");
    if (task) pinTask(task);
    return;
  }
  const park = target.closest("[data-productivity-park]");
  if (park) { event.preventDefault(); openParkDialog(park.dataset.productivityPark || ""); return; }
  const copy = target.closest("[data-productivity-copy]");
  if (copy) {
    event.preventDefault();
    const task = state.tasks.get(copy.dataset.productivityCopy || "");
    if (task) copyTaskLink(task);
    return;
  }
  if (target.closest("[data-productivity-open-overview]")) {
    document.querySelector('[data-deck-action="overview"]')?.click();
    return;
  }
  if (target.closest("[data-productivity-waiting]")) {
    document.querySelector('[data-deck-action="overview"]')?.click();
    window.setTimeout(() => q("[data-productivity-overview-section]")?.scrollIntoView({ behavior: "smooth", block: "start" }), 40);
    return;
  }
  if (target.closest("[data-productivity-dock-toggle]")) {
    state.memory.dockCollapsed = !state.memory.dockCollapsed;
    schedulePersist();
    renderDock();
  }
}

function handleInput(event) {
  if (handlePanelInput(event)) renderDock();
}

function handleChange(event) {
  handlePanelChange(event);
}

function handleSubmit(event) {
  const form = event.target instanceof HTMLFormElement ? event.target.closest("[data-productivity-park-form]") : null;
  if (!form) return;
  event.preventDefault();
  submitParkDialog(form);
}

function handleKeydown(event) {
  if (parkIsOpen()) {
    event.stopImmediatePropagation();
    if (event.key === "Escape") { event.preventDefault(); closeParkDialog(); return; }
    trapTab(event, parkElement());
    return;
  }
  if (panelIsOpen()) {
    event.stopImmediatePropagation();
    if (event.key === "Escape") { event.preventDefault(); closeContextPanel(); return; }
    trapTab(event, panelElement());
    return;
  }
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest(PRODUCTIVITY_TYPING_SELECTOR)) return;
  const task = currentTask();
  if (!task) return;
  if (!event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "c") {
    event.preventDefault(); renderContextPanel(task.key); return;
  }
  if (!event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "p") {
    event.preventDefault(); pinTask(task); return;
  }
  if (!event.metaKey && !event.ctrlKey && !event.altKey && event.shiftKey && event.key.toLowerCase() === "p") {
    event.preventDefault(); openParkDialog(task.key); return;
  }
  if (event.altKey && !event.metaKey && !event.ctrlKey && event.key.toLowerCase() === "d") {
    event.preventDefault(); q(".workspace-task-dock__summary")?.focus({ preventScroll: true });
  }
}

const app = document.querySelector("#app");
if (app) new MutationObserver(scheduleMount).observe(app, { childList: true, subtree: true });
document.addEventListener("contentengine:productivity-changed", scheduleMount);
document.addEventListener("click", handleClick, true);
document.addEventListener("input", handleInput, true);
document.addEventListener("change", handleChange, true);
document.addEventListener("submit", handleSubmit, true);
document.addEventListener("keydown", handleKeydown, true);
window.addEventListener("hashchange", () => {
  closeContextPanel(false);
  closeParkDialog(false);
  scheduleMount();
}, { passive: true });
window.addEventListener("beforeunload", persistMemory);
window.setInterval(scheduleMount, 60_000);
scheduleMount();
