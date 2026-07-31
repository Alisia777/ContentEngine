function registerCommand(command) {
  if (!command?.id || !command?.title || typeof command.run !== "function") return;
  runtime.commands.set(command.id, command);
}

function baseCommands() {
  registerCommand({ id: "mission", title: "Открыть Mission Control", subtitle: "Все рабочие столы и оперативное внимание", icon: "grid", keywords: "столы обзор mission", run() { q("[data-ce-open-mission]")?.click(); } });
  registerCommand({ id: "blockers", title: "Показать блокеры", subtitle: "Найти задачи, которые перестали двигаться", icon: "warning", keywords: "блокеры ошибки проблемы", run() { openSpotlight("блокер"); } });
  registerCommand({ id: "next", title: "Перейти к следующей задаче", subtitle: "Первый объект, требующий действия", icon: "task", keywords: "следующая задача", run() { focusNextActionable(); } });
  registerCommand({ id: "capsule", title: "Открыть текущую рабочую капсулу", subtitle: "Материалы → генерация → проверка → публикация", icon: "product", keywords: "товар капсула объект", run() { const first = runtime.objects.values().next().value || runtime.recent[0]; if (first) openObjectCapsule(first.key); } });
  registerCommand({ id: "rail", title: "Показать или скрыть Stage Manager", subtitle: "Недавние рабочие объекты слева", icon: "work", keywords: "stage manager объекты", run() { remember({ railHidden: !runtime.memory.railHidden }); refreshStageRail(); } });
}

function searchableEntries(query = "") {
  const needle = String(query || "").trim().toLocaleLowerCase("ru-RU");
  const routes = collectRoutes();
  const objects = [...runtime.objects.values(), ...runtime.recent.filter((recent) => !runtime.objects.has(recent.key))].map((object) => ({
    ...object,
    id: object.key,
    kind: "object",
    icon: routeIcon(object.route, object.kind),
    run: () => openObjectCapsule(object.key),
  }));
  const commands = [...runtime.commands.values()].map((command) => ({ ...command, kind: "command" }));
  return [...commands, ...objects, ...routes].filter((entry) => {
    if (!needle) return true;
    const haystack = `${entry.title || ""} ${entry.subtitle || ""} ${entry.keywords || ""} ${entry.status || ""}`.toLocaleLowerCase("ru-RU");
    return haystack.includes(needle);
  }).slice(0, 28);
}

function spotlightItem(entry, index) {
  const iconName = entry.icon || routeIcon(entry.route || "", entry.kind || "");
  const badge = entry.kind === "command" ? "Команда" : entry.kind === "route" ? "Пространство" : entry.status || "Объект";
  return `
    <button type="button" class="ce-v3-spotlight__item${index === 0 ? " is-active" : ""}" data-ce-v3-result-index="${index}">
      <span>${icon(iconName, 19)}</span>
      <div><strong>${escapeMarkup(entry.title)}</strong><small>${escapeMarkup(entry.subtitle || "")}</small></div>
      <i>${escapeMarkup(badge)}</i>
    </button>`;
}

function renderSpotlightResults(query = "") {
  const overlay = runtime.spotlight;
  if (!overlay) return;
  const entries = searchableEntries(query);
  overlay._entries = entries;
  const list = q("[data-ce-v3-spotlight-results]", overlay);
  list.innerHTML = entries.length
    ? entries.map(spotlightItem).join("")
    : '<div class="ce-v3-spotlight__empty"><strong>Ничего не найдено</strong><p>Попробуйте название товара, задачу, площадку или раздел.</p></div>';
  q("[data-ce-v3-spotlight-count]", overlay).textContent = `${entries.length} результатов`;
}

function closeSpotlight({ restoreFocus = true } = {}) {
  const overlay = runtime.spotlight;
  if (!overlay) return;
  const trigger = overlay._trigger;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    runtime.spotlight = null;
    document.body.classList.remove("ce-v3-spotlight-open");
    if (restoreFocus) trigger?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 190);
}

function runSpotlightEntry(index) {
  const entry = runtime.spotlight?._entries?.[index];
  if (!entry) return;
  closeSpotlight({ restoreFocus: false });
  if (typeof entry.run === "function") entry.run();
  else if (entry.href) window.location.hash = entry.href.startsWith("#") ? entry.href.slice(1) : entry.href;
}

function openSpotlight(initialQuery = "", trigger = document.activeElement) {
  closeCapsule({ restoreFocus: false });
  if (runtime.spotlight) {
    const input = q("[data-ce-v3-spotlight-input]", runtime.spotlight);
    input.value = initialQuery;
    renderSpotlightResults(initialQuery);
    input.focus();
    return;
  }
  const overlay = elementFrom(`
    <div class="ce-v3-spotlight-backdrop">
      <section class="ce-v3-spotlight" role="dialog" aria-modal="true" aria-labelledby="ce-v3-spotlight-title">
        <header>
          <span>${icon("search", 21)}</span>
          <input id="ce-v3-spotlight-title" data-ce-v3-spotlight-input type="search" autocomplete="off" spellcheck="false" placeholder="Товар, задача, блокер или команда…" aria-label="Поиск по кабинету" />
          <kbd>Esc</kbd>
        </header>
        <div class="ce-v3-spotlight__results" data-ce-v3-spotlight-results role="listbox"></div>
        <footer><span data-ce-v3-spotlight-count></span><small><kbd>↑</kbd><kbd>↓</kbd> выбрать · <kbd>Enter</kbd> открыть</small></footer>
      </section>
    </div>`);
  overlay._trigger = trigger;
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeSpotlight();
    const item = event.target instanceof Element ? event.target.closest("[data-ce-v3-result-index]") : null;
    if (item) runSpotlightEntry(Number(item.dataset.ceV3ResultIndex));
  });
  const input = q("[data-ce-v3-spotlight-input]", overlay);
  input.value = initialQuery;
  input.addEventListener("input", () => renderSpotlightResults(input.value));
  document.body.append(overlay);
  runtime.spotlight = overlay;
  document.body.classList.add("ce-v3-spotlight-open");
  renderSpotlightResults(initialQuery);
  animateIn(q(".ce-v3-spotlight", overlay));
  input.focus({ preventScroll: true });
}

function moveSpotlightSelection(direction) {
  const overlay = runtime.spotlight;
  if (!overlay) return;
  const items = qa("[data-ce-v3-result-index]", overlay);
  if (!items.length) return;
  const current = Math.max(0, items.findIndex((item) => item.classList.contains("is-active")));
  const next = (current + direction + items.length) % items.length;
  items.forEach((item, index) => item.classList.toggle("is-active", index === next));
  items[next].scrollIntoView({ block: "nearest" });
}

function focusNextActionable() {
  const target = q('[data-work-item-action-required="true"], .task-card:not(.ce-v3-done), .placement-card');
  if (!target) return;
  target.scrollIntoView({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "center" });
  target.focus?.({ preventScroll: true });
  target.animate?.([
    { boxShadow: "0 0 0 0 rgba(232,130,69,0)" },
    { boxShadow: "0 0 0 4px rgba(232,130,69,.24)" },
    { boxShadow: "0 0 0 0 rgba(232,130,69,0)" },
  ], { duration: 720, easing: SPRING });
}

function stageRailAllowed() {
  return ["/workspace/work", "/workspace/tasks", "/workspace/placement", "/workspace/stats", "/workspace/payouts"].includes(routePath());
}

function refreshStageRail() {
  if (!stageRailAllowed() || runtime.memory.railHidden || !runtime.recent.length) {
    runtime.rail?.remove();
    runtime.rail = null;
    document.body.classList.remove("ce-v3-stage-visible");
    return;
  }
  let rail = runtime.rail;
  if (!rail?.isConnected) {
    rail = elementFrom('<aside class="ce-v3-stage" aria-label="Недавние рабочие объекты"><header><small>STAGE MANAGER</small><button type="button" data-ce-v3-hide-stage aria-label="Скрыть">×</button></header><div></div></aside>');
    document.body.append(rail);
    runtime.rail = rail;
  }
  q(":scope > div", rail).innerHTML = runtime.recent.slice(0, 6).map((object) => `
    <button type="button" data-ce-v3-open-object="${escapeMarkup(object.key)}" class="${object.blocked ? "is-blocked" : ""}">
      <span>${icon(routeIcon(object.route, object.kind), 18)}</span>
      <div><strong>${escapeMarkup(object.title)}</strong><small>${escapeMarkup(object.status || routeLabel(object.route))}</small></div>
      <i></i>
    </button>`).join("");
  document.body.classList.add("ce-v3-stage-visible");
}

function pushUndo({ label = "Действие выполнено", undo }) {
  runtime.undo?.remove();
  const bar = elementFrom(`
    <div class="ce-v3-undo" role="status" aria-live="polite">
      <span>${icon("undo", 17)}</span><strong>${escapeMarkup(label)}</strong>
      <button type="button">Отменить</button><i></i>
    </div>`);
  let closed = false;
  const finish = () => {
    if (closed) return;
    closed = true;
    bar.remove();
    if (runtime.undo === bar) runtime.undo = null;
  };
  bar.querySelector("button").addEventListener("click", () => {
    try { undo?.(); } finally { finish(); }
  });
  document.body.append(bar);
  runtime.undo = bar;
  window.setTimeout(finish, 10_000);
}

function enableSplit(container, left, right, key = routePath()) {
  if (!container || !left || !right || container.dataset.ceV3SplitReady === "true") return null;
  container.dataset.ceV3SplitReady = "true";
  container.classList.add("ce-v3-split");
  left.classList.add("ce-v3-split__primary");
  right.classList.add("ce-v3-split__secondary");
  const handle = elementFrom('<button class="ce-v3-split__handle" type="button" aria-label="Изменить ширину панелей"><span></span></button>');
  left.after(handle);
  const memoryKey = `split:${key}`;
  const initial = Math.max(35, Math.min(75, Number(runtime.memory[memoryKey]) || 64));
  container.style.setProperty("--ce-v3-split", `${initial}%`);
  let pointerId = null;
  const move = (event) => {
    if (pointerId === null || event.pointerId !== pointerId) return;
    const rect = container.getBoundingClientRect();
    const percent = Math.max(30, Math.min(78, ((event.clientX - rect.left) / Math.max(1, rect.width)) * 100));
    container.style.setProperty("--ce-v3-split", `${percent}%`);
  };
  const stop = (event) => {
    if (pointerId === null || event.pointerId !== pointerId) return;
    pointerId = null;
    handle.releasePointerCapture?.(event.pointerId);
    const value = parseFloat(container.style.getPropertyValue("--ce-v3-split")) || initial;
    remember({ [memoryKey]: value });
  };
  handle.addEventListener("pointerdown", (event) => {
    pointerId = event.pointerId;
    handle.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  });
  handle.addEventListener("pointermove", move);
  handle.addEventListener("pointerup", stop);
  handle.addEventListener("pointercancel", stop);
  return handle;
}

function initPresence() {
  if (typeof BroadcastChannel !== "function") return;
  runtime.channel = new BroadcastChannel("contentengine-os-v3-presence");
  runtime.channel.addEventListener("message", (event) => {
    const message = event.data;
    if (!message || message.type !== "presence" || !message.key) return;
    runtime.foreignPresence.set(String(message.key), Date.now());
    syncPresenceUi();
  });
  window.setInterval(() => {
    const now = Date.now();
    for (const [key, at] of runtime.foreignPresence) if (now - at > 15_000) runtime.foreignPresence.delete(key);
    syncPresenceUi();
    if (runtime.currentEntityKey) broadcastPresence(runtime.currentEntityKey, "");
  }, 5_000);
}

function broadcastPresence(key, title = "") {
  runtime.channel?.postMessage?.({ type: "presence", key, title, at: Date.now() });
}

function syncPresenceUi() {
  qa("[data-ce-v3-presence-for]").forEach((node) => {
    const active = runtime.foreignPresence.has(String(node.dataset.ceV3PresenceFor || ""));
    node.hidden = !active;
  });
}

function augmentMissionControl() {
  const overview = q(".workspace-overview, .workspace-overview-backdrop");
  if (!overview || q(".ce-v3-mission-attention", overview)) return;
  const host = q(".workspace-overview__body, .workspace-overview__panel, .workspace-overview", overview) || overview;
  const objects = [...runtime.objects.values()];
  const counts = {
    active: objects.filter((item) => !item.blocked).length,
    blocked: objects.filter((item) => item.blocked).length,
    waiting: objects.filter((item) => /жд|очеред|план/u.test(`${item.status} ${item.subtitle}`.toLocaleLowerCase("ru-RU"))).length,
    recent: runtime.recent.length,
  };
  const section = elementFrom(`
    <section class="ce-v3-mission-attention">
      <header><div><small>ОПЕРАТИВНОЕ ВНИМАНИЕ</small><strong>Что движется, ждёт или заблокировано</strong></div><button type="button" data-ce-v3-open-spotlight>${icon("search", 17)} Найти</button></header>
      <div>
        <article><span>${icon("work", 19)}</span><div><strong>${counts.active}</strong><small>активно</small></div></article>
        <article><span>${icon("clock", 19)}</span><div><strong>${counts.waiting}</strong><small>ожидают</small></div></article>
        <article class="${counts.blocked ? "is-danger" : ""}"><span>${icon("warning", 19)}</span><div><strong>${counts.blocked}</strong><small>блокеров</small></div></article>
        <article><span>${icon("product", 19)}</span><div><strong>${counts.recent}</strong><small>недавних</small></div></article>
      </div>
    </section>`);
  host.prepend(section);
}

function registerAdapter(id, mount) {
  if (!id || typeof mount !== "function") return;
  runtime.adapters.set(id, mount);
  scheduleMount();
}

function mountAdapters() {
  for (const [id, mount] of runtime.adapters) {
    try { mount({ route: routePath(), core: api }); }
    catch (error) { console.warn(`ContentEngine OS v3 adapter ${id} failed`, error); }
  }
}

function mount() {
  scanObjects();
  mountAdapters();
  refreshStageRail();
  augmentMissionControl();
  dispatch("contentengine:os-v3-mounted", { route: routePath() });
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

function handleClick(event) {
  if (!(event.target instanceof Element)) return;
  const objectButton = event.target.closest("[data-ce-v3-open-object]");
  if (objectButton) {
    event.preventDefault();
    openObjectCapsule(objectButton.dataset.ceV3OpenObject, objectButton);
    return;
  }
  if (event.target.closest("[data-ce-v3-hide-stage]")) {
    remember({ railHidden: true });
    refreshStageRail();
    return;
  }
  if (event.target.closest("[data-ce-v3-open-spotlight]")) {
    openSpotlight("", event.target.closest("button"));
  }
}

function handleKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    event.stopImmediatePropagation();
    openSpotlight();
    return;
  }
  if (runtime.spotlight) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSpotlight();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      moveSpotlightSelection(1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      moveSpotlightSelection(-1);
    } else if (event.key === "Enter") {
      const active = q("[data-ce-v3-result-index].is-active", runtime.spotlight);
      if (active) {
        event.preventDefault();
        runSpotlightEntry(Number(active.dataset.ceV3ResultIndex));
      }
    }
    return;
  }
  if (runtime.capsule && event.key === "Escape") {
    event.preventDefault();
    closeCapsule();
  }
}

const api = Object.freeze({
  q,
  qa,
  elementFrom,
  icon,
  compact,
  escapeMarkup,
  routePath,
  routeFromHref,
  remember,
  readMemory: () => ({ ...runtime.memory }),
  animateIn,
  animateOut,
  reducedMotion: () => REDUCED_MOTION.matches,
  finePointer: () => FINE_POINTER.matches,
  registerAdapter,
  registerCommand,
  registerObject,
  objects: () => [...runtime.objects.values()],
  recentObjects: () => [...runtime.recent],
  openSpotlight,
  closeSpotlight,
  openObjectCapsule,
  closeCapsule,
  pushUndo,
  enableSplit,
  scheduleMount,
  dispatch,
});

window.ContentEngineOSV3 = api;
baseCommands();
initPresence();
new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("click", handleClick, true);
document.addEventListener("keydown", handleKeydown, true);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
