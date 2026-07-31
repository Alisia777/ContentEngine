/*
 * ContentEngine OS v3 production loop.
 * Re-composes Publishing, Tasks, My Work, Results and Payouts using existing
 * application DOM. Native forms, links and server-driven actions remain the
 * authoritative controls.
 */

const core = window.ContentEngineOSV3;
if (!core) throw new Error("ContentEngineOSV3 core must load before production loop");

const {
  q, qa, elementFrom, icon, compact, escapeMarkup, routePath, remember,
  readMemory, animateIn, reducedMotion, enableSplit, pushUndo, registerAdapter,
  registerCommand, openObjectCapsule,
} = core;

const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const runtime = {
  publishingPage: null,
  taskPage: null,
  workPage: null,
  statsPage: null,
  payoutsPage: null,
};

function directChildren(node) {
  return [...(node?.children || [])];
}

function statusCopy(node) {
  return compact(q(".status-badge, .badge, .my-work-status, .my-work-overdue", node)?.textContent || "", 80);
}

function titleCopy(node) {
  return compact(q("h1, h2, h3, strong", node)?.textContent || "Рабочий объект", 140);
}

function isEditableTarget(event) {
  const target = event.target instanceof Element ? event.target : null;
  return Boolean(target?.closest("input, textarea, select, button, a, video, audio, [contenteditable='true']"));
}

function springSwap(outgoing, incoming, direction = 1) {
  if (!incoming || reducedMotion() || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 26}px,0,0) scale(.985)` },
  ], { duration: 170, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 38}px,0,0) scale(.98)`, filter: "blur(4px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 460, easing: SPRING });
}

function inferTaskLane(card) {
  const text = `${statusCopy(card)} ${card.textContent}`.toLocaleLowerCase("ru-RU");
  if (/блокер|ошибка|отклон|ждёт|ожида/u.test(text)) return "waiting";
  if (/в работе|провер|отправить|продолжить|принять/u.test(text)) return "now";
  if (/заверш|готово|выполн|опублик/u.test(text)) return "done";
  return "next";
}

function inferWorkLane(card) {
  if (card.dataset.workItemBlocker === "true") return "waiting";
  const text = `${statusCopy(card)} ${card.textContent}`.toLocaleLowerCase("ru-RU");
  if (/блокер|ошибка|ждёт|ожида|просроч/u.test(text)) return "waiting";
  if (card.dataset.workItemActionRequired === "true" || /в работе|решение|провер/u.test(text)) return "now";
  if (/готово|заверш|выплач|опублик/u.test(text)) return "done";
  return "next";
}

function stageManagerShell(kind) {
  return elementFrom(`
    <section class="production-stage-manager production-stage-manager--${kind}">
      <header>
        <div class="production-stage-controls" aria-hidden="true"><i></i><i></i><i></i></div>
        <div><small>ContentEngine · Stage Manager</small><strong>${kind === "work" ? "Моя работа" : "Задачи"}</strong></div>
        <div class="production-stage-actions"><button type="button" data-stage-view="lanes" class="is-active">Поток</button><button type="button" data-stage-view="focus">Одна задача</button><button type="button" data-ce-open-mission>${icon("grid", 17)}</button></div>
      </header>
      <div class="production-stage-wip" data-stage-wip hidden></div>
      <div class="production-stage-lanes">
        <section data-stage-lane="now"><header><span></span><div><small>СЕЙЧАС</small><strong>В работе</strong></div><b>0</b></header><div></div></section>
        <section data-stage-lane="waiting"><header><span></span><div><small>ЖДУ</small><strong>Блокеры и ожидание</strong></div><b>0</b></header><div></div></section>
        <section data-stage-lane="next"><header><span></span><div><small>ДАЛЬШЕ</small><strong>Очередь</strong></div><b>0</b></header><div></div></section>
      </div>
      <div class="production-stage-focus" hidden><nav></nav><main></main><footer><button type="button" data-stage-focus-prev>${icon("left", 18)} Назад</button><strong data-stage-focus-position></strong><button type="button" data-stage-focus-next>Далее ${icon("right", 18)}</button></footer></div>
      <div class="production-stage-done" hidden><header><small>ЗАВЕРШЕНО</small><strong>История текущей выборки</strong></header><div></div></div>
    </section>`);
}

function attachLocalTools(card) {
  if (q(":scope > .production-card-tools", card)) return;
  const key = card.dataset.ceV3ObjectKey || "";
  const tools = elementFrom(`
    <div class="production-card-tools">
      <button type="button" data-ce-v3-open-object="${escapeMarkup(key)}">${icon("product", 15)}<span>Капсула</span></button>
      <button type="button" data-ce-v3-local-action="park" data-entity-key="${escapeMarkup(key)}">${icon("clock", 15)}<span>Припарковать</span></button>
      <button type="button" data-ce-v3-local-action="handoff" data-entity-key="${escapeMarkup(key)}">${icon("handoff", 15)}<span>Передать</span></button>
      <button type="button" data-stage-focus-card>${icon("split", 15)}<span>На весь стол</span></button>
    </div>`);
  card.append(tools);
}

function setupStageManager(page, source, cards, kind, laneResolver) {
  const shell = stageManagerShell(kind);
  const anchor = q(":scope > .workspace-page-intro, :scope > .my-work-hero", page) || page.firstElementChild;
  anchor?.after?.(shell);
  source.classList.add("production-stage-native-source");
  q(".production-stage-done > div", shell).append(source);
  const lanes = {
    now: q('[data-stage-lane="now"] > div', shell),
    waiting: q('[data-stage-lane="waiting"] > div', shell),
    next: q('[data-stage-lane="next"] > div', shell),
    done: q(".production-stage-done > div", shell),
  };
  cards.forEach((card, index) => {
    const lane = laneResolver(card);
    card.dataset.productionLane = lane;
    card.dataset.productionIndex = String(index);
    card.classList.add("production-stage-card");
    attachLocalTools(card);
    lanes[lane]?.append(card);
  });
  const counts = {};
  for (const lane of ["now", "waiting", "next"]) {
    counts[lane] = qa(":scope > .production-stage-card", lanes[lane]).length;
    q(`[data-stage-lane="${lane}"] b`, shell).textContent = String(counts[lane]);
  }
  const activeCount = counts.now;
  const wip = q("[data-stage-wip]", shell);
  if (activeCount > 3) {
    wip.hidden = false;
    wip.innerHTML = `${icon("warning", 17)}<span>Сейчас активны <strong>${activeCount}</strong> задач. Завершите или припаркуйте одну, чтобы не потерять контекст.</span>`;
  }
  const focusCards = cards.filter((card) => card.dataset.productionLane !== "done");
  let focusIndex = Math.max(0, Math.min(focusCards.length - 1, Number(readMemory()[`${kind}FocusIndex`]) || 0));
  let view = String(readMemory()[`${kind}View`] || "lanes");
  const focusMain = q(".production-stage-focus > main", shell);
  const focusNav = q(".production-stage-focus > nav", shell);
  focusNav.innerHTML = focusCards.map((card, index) => `<button type="button" data-stage-focus-index="${index}"><span>${icon(inferTaskLane(card) === "waiting" ? "warning" : "task", 16)}</span><strong>${escapeMarkup(titleCopy(card))}</strong><small>${escapeMarkup(statusCopy(card) || "Работа")}</small></button>`).join("");
  const parking = document.createElement("div");
  parking.className = "production-stage-focus-parking";
  parking.hidden = true;
  shell.append(parking);

  const showFocusCard = (index, focus = false) => {
    if (!focusCards.length) return;
    const resolved = Math.max(0, Math.min(focusCards.length - 1, Number(index) || 0));
    const previous = focusIndex;
    const current = focusCards[resolved];
    const outgoing = q(":scope > .production-stage-card", focusMain);
    if (outgoing && outgoing !== current) {
      const lane = outgoing.dataset.productionLane;
      lanes[lane]?.append(outgoing);
    }
    if (current.parentElement !== focusMain) focusMain.append(current);
    focusCards.forEach((card, cardIndex) => card.inert = cardIndex !== resolved && view === "focus");
    qa("[data-stage-focus-index]", focusNav).forEach((button) => button.classList.toggle("is-active", Number(button.dataset.stageFocusIndex) === resolved));
    focusIndex = resolved;
    remember({ [`${kind}FocusIndex`]: resolved });
    q("[data-stage-focus-position]", shell).textContent = `${resolved + 1} / ${focusCards.length}`;
    q("[data-stage-focus-prev]", shell).disabled = resolved <= 0;
    q("[data-stage-focus-next]", shell).disabled = resolved >= focusCards.length - 1;
    if (previous !== resolved) springSwap(outgoing, current, resolved >= previous ? 1 : -1);
    if (focus) current.focus({ preventScroll: true });
  };

  const setView = (next) => {
    const resolved = next === "focus" ? "focus" : "lanes";
    view = resolved;
    remember({ [`${kind}View`]: resolved });
    shell.dataset.stageView = resolved;
    q(".production-stage-lanes", shell).hidden = resolved !== "lanes";
    q(".production-stage-focus", shell).hidden = resolved !== "focus";
    qa("[data-stage-view]", shell).forEach((button) => button.classList.toggle("is-active", button.dataset.stageView === resolved));
    if (resolved === "focus") showFocusCard(focusIndex);
    else {
      const current = q(":scope > .production-stage-card", focusMain);
      if (current) lanes[current.dataset.productionLane]?.append(current);
      focusCards.forEach((card) => card.inert = false);
    }
  };

  shell.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const viewButton = event.target.closest("[data-stage-view]");
    if (viewButton) setView(viewButton.dataset.stageView);
    const focusButton = event.target.closest("[data-stage-focus-card]");
    if (focusButton) {
      const card = focusButton.closest(".production-stage-card");
      const index = focusCards.indexOf(card);
      if (index >= 0) {
        focusIndex = index;
        setView("focus");
      }
    }
    const navButton = event.target.closest("[data-stage-focus-index]");
    if (navButton) showFocusCard(Number(navButton.dataset.stageFocusIndex), true);
    if (event.target.closest("[data-stage-focus-prev]")) showFocusCard(focusIndex - 1, true);
    if (event.target.closest("[data-stage-focus-next]")) showFocusCard(focusIndex + 1, true);
  });
  setView(view);
  animateIn(shell);
}

function mountTasks() {
  if (routePath() !== "/workspace/tasks") {
    document.body.classList.remove("contentengine-tasks-stage-open");
    runtime.taskPage = null;
    return;
  }
  const source = q(".task-list");
  const page = source?.closest?.(".page-wrap");
  if (!page) return;
  runtime.taskPage = page;
  document.body.classList.add("contentengine-tasks-stage-open");
  if (page.dataset.tasksStageReady === "true") return;
  page.dataset.tasksStageReady = "true";
  page.classList.add("tasks-stage-page");
  setupStageManager(page, source, qa(":scope > .task-card", source), "tasks", inferTaskLane);
}

function mountMyWork() {
  if (routePath() !== "/workspace/work") {
    document.body.classList.remove("contentengine-work-stage-open");
    runtime.workPage = null;
    return;
  }
  const page = q(".my-work-page");
  const queue = q(".my-work-queue", page);
  if (!page || !queue) return;
  runtime.workPage = page;
  document.body.classList.add("contentengine-work-stage-open");
  if (page.dataset.workStageReady === "true") return;
  page.dataset.workStageReady = "true";
  page.classList.add("work-stage-page");
  const cards = qa(":scope > .my-work-item", queue);
  const filterSource = q(".my-work-layout", page);
  if (filterSource) {
    const drawer = elementFrom('<details class="production-work-filters"><summary>Фильтры, представления и уведомления</summary><div></div></details>');
    q(":scope > div", drawer).append(filterSource);
    q(":scope > .my-work-summary", page)?.after(drawer);
  }
  setupStageManager(page, queue, cards, "work", inferWorkLane);
}

registerCommand({ id: "my-work", title: "Открыть Stage Manager", subtitle: "Сейчас / Жду / Дальше", icon: "work", keywords: "моя работа stage", run() { window.location.hash = "/workspace/work"; } });
registerCommand({ id: "tasks", title: "Открыть задачи", subtitle: "Поток задач и фокус-режим", icon: "task", keywords: "задачи поток", run() { window.location.hash = "/workspace/tasks"; } });
registerAdapter("work-stage-v3", () => { mountTasks(); mountMyWork(); });
