/* Task context shelf and parking dialog. */

import {
  PRODUCTIVITY_PENDING_KEY,
  addEvent,
  announce,
  compact,
  elementFrom,
  escapeMarkup,
  formatDate,
  isParkedDue,
  liveLinks,
  mutateTask,
  q,
  routePath,
  schedulePersist,
  sessionStore,
  state,
  surfaceByKey,
  taskTone,
  touchOrder,
  unparkTask,
} from "./workspace-task-productivity-core.js?v=20260826.rebuild-clean.60";

const ui = {
  panel: null,
  panelBackdrop: null,
  parkDialog: null,
  parkBackdrop: null,
  returnFocus: null,
  noteTimer: 0,
};

function metaMarkup(label, value) {
  if (!value) return "";
  return `<span class="workspace-context-meta__item"><small>${escapeMarkup(label)}</small><strong>${escapeMarkup(value)}</strong></span>`;
}

function eventLabel(type) {
  return {
    pinned: "Закреплено",
    unpinned: "Откреплено",
    parked: "Припарковано",
    unparked: "Возвращено",
    opened: "Открыто",
    note: "Заметка обновлена",
  }[type] || "Изменено";
}

function historyMarkup(task) {
  const events = [...(task.events || [])].reverse().slice(0, 8);
  if (!events.length) return '<p class="workspace-context-empty">Локальная история появится после закрепления, парковки или открытия задачи.</p>';
  return `<ol class="workspace-context-history">${events.map((event) => `
    <li><span aria-hidden="true"></span><div><strong>${escapeMarkup(eventLabel(event.type))}</strong><p>${escapeMarkup(event.label)}</p><time>${escapeMarkup(formatDate(event.at))}</time></div></li>
  `).join("")}</ol>`;
}

function linksMarkup(surface) {
  const links = liveLinks(surface);
  if (!links.length) return '<p class="workspace-context-empty">На текущем экране нет открытых ссылок на материалы.</p>';
  return `<div class="workspace-context-links">${links.map((link) => `<a href="${escapeMarkup(link.href)}" target="_blank" rel="noopener noreferrer">${escapeMarkup(link.label)} <span aria-hidden="true">↗</span></a>`).join("")}</div>`;
}

export function renderContextPanel(key, focusPanel = true) {
  const task = state.tasks.get(key);
  if (!task) return;
  closeParkDialog(false);
  state.selectedKey = key;
  const liveSurface = surfaceByKey(key);
  if (!ui.panel) {
    ui.returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    ui.panelBackdrop = elementFrom('<div class="workspace-context-backdrop" data-productivity-context-close aria-hidden="true"></div>');
    ui.panel = document.createElement("aside");
    ui.panel.className = "workspace-context-panel";
    ui.panel.setAttribute("role", "dialog");
    ui.panel.setAttribute("aria-modal", "false");
    ui.panel.setAttribute("aria-labelledby", "workspace-context-title");
    document.body.append(ui.panelBackdrop, ui.panel);
    document.body.classList.add("workspace-context-open");
  }
  const tone = taskTone(task);
  const parking = task.parked
    ? `<div class="workspace-context-parking" data-tone="${escapeMarkup(tone)}"><span aria-hidden="true">${isParkedDue(task) ? "!" : "◷"}</span><div><small>${isParkedDue(task) ? "Пора вернуться" : "Задача припаркована"}</small><strong>${escapeMarkup(task.parked.reason)}</strong>${task.parked.returnAt ? `<p>Вернуться: ${escapeMarkup(formatDate(task.parked.returnAt))}</p>` : ""}${task.parked.note ? `<p>${escapeMarkup(task.parked.note)}</p>` : ""}</div></div>`
    : "";
  ui.panel.innerHTML = `
    <header class="workspace-context-panel__header">
      <div><p>Контекст задачи</p><h2 id="workspace-context-title">${escapeMarkup(task.title)}</h2></div>
      <button type="button" data-productivity-context-close aria-label="Закрыть контекст">×</button>
    </header>
    <div class="workspace-context-panel__body">
      <div class="workspace-context-status" data-tone="${escapeMarkup(tone)}"><span aria-hidden="true"></span><strong>${escapeMarkup(task.statusLabel)}</strong><small>${escapeMarkup(task.route.replace("/workspace/", "").replace("/learn", "Обучение") || "Кабинет")}</small></div>
      <p class="workspace-context-lead">${escapeMarkup(task.hint)}</p>
      ${parking}
      <section class="workspace-context-block workspace-context-block--accent">
        <p class="workspace-context-kicker">Сейчас</p>
        <h3>${escapeMarkup(task.nextAction || "Откройте задачу и проверьте следующий доступный шаг")}</h3>
        ${task.readyWhen ? `<div class="workspace-context-ready"><small>Готово, когда</small><strong>${escapeMarkup(task.readyWhen)}</strong></div>` : ""}
      </section>
      <div class="workspace-context-meta">
        ${metaMarkup("Ответственный", task.owner)}
        ${metaMarkup("Срок", task.deadline)}
        ${metaMarkup("Материалы", task.materialCount ? `${task.materialCount}` : "")}
        ${metaMarkup("Обновлено", formatDate(task.updatedAt))}
      </div>
      <section class="workspace-context-block">
        <div class="workspace-context-block__head"><div><p class="workspace-context-kicker">Рабочая заметка</p><h3>Что нельзя потерять</h3></div><span>Только в этой вкладке</span></div>
        <textarea data-productivity-note="${escapeMarkup(task.key)}" rows="4" maxlength="2000" placeholder="Решение, вопрос, зависимость или следующий шаг…">${escapeMarkup(task.note)}</textarea>
      </section>
      <section class="workspace-context-block">
        <div class="workspace-context-block__head"><div><p class="workspace-context-kicker">Материалы</p><h3>Ссылки текущей задачи</h3></div><span>${liveSurface ? "С экрана" : "Откройте задачу"}</span></div>
        ${linksMarkup(liveSurface)}
      </section>
      <section class="workspace-context-block">
        <div class="workspace-context-block__head"><div><p class="workspace-context-kicker">Локальная история</p><h3>Последние решения</h3></div></div>
        ${historyMarkup(task)}
      </section>
    </div>
    <footer class="workspace-context-panel__footer">
      <button class="workspace-context-button workspace-context-button--primary" type="button" data-productivity-open="${escapeMarkup(task.key)}">Открыть задачу <span aria-hidden="true">→</span></button>
      <button class="workspace-context-button" type="button" data-productivity-pin="${escapeMarkup(task.key)}">${task.pinned ? "Открепить" : "Закрепить"}</button>
      <button class="workspace-context-button" type="button" data-productivity-park="${escapeMarkup(task.key)}">${task.parked ? "Вернуть" : "Припарковать"}</button>
      <button class="workspace-context-button workspace-context-button--icon" type="button" data-productivity-copy="${escapeMarkup(task.key)}" title="Скопировать ссылку на задачу" aria-label="Скопировать ссылку на задачу">⧉</button>
    </footer>
  `;
  if (focusPanel) q("[data-productivity-context-close]", ui.panel)?.focus({ preventScroll: true });
}

export function closeContextPanel(restoreFocus = true) {
  ui.panel?.remove();
  ui.panelBackdrop?.remove();
  ui.panel = null;
  ui.panelBackdrop = null;
  state.selectedKey = "";
  document.body.classList.remove("workspace-context-open");
  if (restoreFocus && ui.returnFocus?.isConnected) ui.returnFocus.focus({ preventScroll: true });
  ui.returnFocus = null;
}

function parkMarkup(task) {
  const currentReason = task.parked?.reason || "Жду ответ";
  const reasons = ["Жду ответ", "Жду файл", "Жду генерацию", "Нужна правка другого сотрудника", "Вернуться позже"];
  const date = task.parked?.returnAt ? new Date(task.parked.returnAt) : null;
  const dateValue = date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 16) : "";
  return `
    <section class="workspace-park-dialog" role="dialog" aria-modal="true" aria-labelledby="workspace-park-title">
      <header><div><p>Снять с оперативной памяти</p><h2 id="workspace-park-title">Припарковать задачу</h2></div><button type="button" data-productivity-park-close aria-label="Закрыть">×</button></header>
      <form data-productivity-park-form="${escapeMarkup(task.key)}">
        <p class="workspace-park-dialog__task">${escapeMarkup(task.title)}</p>
        <fieldset><legend>Почему задача ждёт</legend>${reasons.map((reason) => `<label><input type="radio" name="reason" value="${escapeMarkup(reason)}" ${reason === currentReason ? "checked" : ""} /><span>${escapeMarkup(reason)}</span></label>`).join("")}</fieldset>
        <label class="workspace-park-field"><span>Когда вернуть в активные</span><input type="datetime-local" name="return_at" value="${escapeMarkup(dateValue)}" /></label>
        <label class="workspace-park-field"><span>Что ждём или что проверить потом</span><textarea name="note" rows="3" maxlength="500" placeholder="Например: Мария должна прислать исходник без водяного знака">${escapeMarkup(task.parked?.note || "")}</textarea></label>
        <div class="workspace-park-actions"><button type="button" data-productivity-park-close>Отмена</button><button type="submit">Припарковать</button></div>
      </form>
    </section>
  `;
}

export function openParkDialog(key) {
  const task = state.tasks.get(key);
  if (!task) return;
  if (task.parked) {
    unparkTask(task);
    return;
  }
  closeParkDialog(false);
  ui.returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : ui.returnFocus;
  ui.parkBackdrop = elementFrom('<div class="workspace-park-backdrop" data-productivity-park-close></div>');
  ui.parkDialog = elementFrom(parkMarkup(task));
  document.body.append(ui.parkBackdrop, ui.parkDialog);
  document.body.classList.add("workspace-park-open");
  q("input[name='reason']:checked", ui.parkDialog)?.focus({ preventScroll: true });
}

export function closeParkDialog(restoreFocus = true) {
  ui.parkDialog?.remove();
  ui.parkBackdrop?.remove();
  ui.parkDialog = null;
  ui.parkBackdrop = null;
  document.body.classList.remove("workspace-park-open");
  if (restoreFocus && ui.returnFocus?.isConnected) ui.returnFocus.focus({ preventScroll: true });
}

export function submitParkDialog(form) {
  const task = state.tasks.get(form.dataset.productivityParkForm || "");
  if (!task) return;
  const values = new FormData(form);
  const raw = String(values.get("return_at") || "").trim();
  const date = raw ? new Date(raw) : null;
  const returnAt = date && !Number.isNaN(date.getTime()) ? date.toISOString() : "";
  task.pinned = true;
  task.parked = {
    reason: String(values.get("reason") || "Ожидание"),
    returnAt,
    note: String(values.get("note") || "").trim().slice(0, 500),
    parkedAt: Date.now(),
  };
  addEvent(task, "parked", `${task.parked.reason}${returnAt ? ` · до ${formatDate(returnAt)}` : ""}`);
  state.tasks.set(task.key, task);
  touchOrder(task.key);
  schedulePersist();
  closeParkDialog(false);
  document.dispatchEvent(new CustomEvent("contentengine:productivity-changed", { detail: { key: task.key } }));
  if (ui.panel) renderContextPanel(task.key, false);
  announce(`Задача припаркована: ${task.title}`);
}

export function openTask(key, focus = true) {
  const task = state.tasks.get(key);
  if (!task) return;
  addEvent(task, "opened", "Задача открыта из Dock или контекстной панели");
  touchOrder(key);
  schedulePersist();
  if (task.route !== routePath()) {
    try { sessionStore()?.setItem(PRODUCTIVITY_PENDING_KEY, JSON.stringify({ key, focus, at: Date.now() })); } catch { /* optional */ }
    closeContextPanel(false);
    window.location.hash = task.route;
    return;
  }
  const surface = surfaceByKey(key);
  if (!surface) {
    announce("Задача пока не найдена на этом столе. Обновите раздел или снимите фильтр.");
    return;
  }
  const button = q(":scope > [data-workspace-focus-card]", surface);
  if (focus && button) button.click();
  else surface.scrollIntoView({ behavior: "smooth", block: "center" });
  closeContextPanel(false);
}

export function copyTaskLink(task) {
  const url = new URL(window.location.href);
  url.hash = `${task.route}?deskTask=${encodeURIComponent(task.key)}`;
  const operation = navigator.clipboard?.writeText?.(url.href);
  if (operation?.then) operation.then(() => announce("Ссылка на задачу скопирована.")).catch(() => announce(url.href));
  else announce(url.href);
}

export function consumePendingTask(deepLinkKey = "") {
  let pending = null;
  try { pending = JSON.parse(sessionStore()?.getItem(PRODUCTIVITY_PENDING_KEY) || "null"); } catch { pending = null; }
  if (deepLinkKey) pending = { key: deepLinkKey, focus: true, at: Date.now() };
  if (!pending?.key || Date.now() - Number(pending.at || 0) > 60_000) return;
  const task = state.tasks.get(pending.key);
  if (!task || task.route !== routePath() || !surfaceByKey(pending.key)) return;
  try { sessionStore()?.removeItem(PRODUCTIVITY_PENDING_KEY); } catch { /* optional */ }
  window.requestAnimationFrame(() => openTask(pending.key, pending.focus !== false));
}

export function handlePanelInput(event) {
  const textarea = event.target instanceof HTMLTextAreaElement ? event.target.closest("[data-productivity-note]") : null;
  if (!textarea) return false;
  const task = state.tasks.get(textarea.dataset.productivityNote || "");
  if (!task) return true;
  task.note = String(textarea.value || "").slice(0, 2000);
  task.updatedAt = Date.now();
  state.tasks.set(task.key, task);
  window.clearTimeout(ui.noteTimer);
  ui.noteTimer = window.setTimeout(schedulePersist, 260);
  return true;
}

export function handlePanelChange(event) {
  const textarea = event.target instanceof HTMLTextAreaElement ? event.target.closest("[data-productivity-note]") : null;
  if (!textarea) return false;
  const task = state.tasks.get(textarea.dataset.productivityNote || "");
  if (task) {
    addEvent(task, "note", task.note ? "Рабочая заметка сохранена" : "Рабочая заметка очищена");
    schedulePersist();
  }
  return true;
}

export function panelIsOpen() { return Boolean(ui.panel); }
export function parkIsOpen() { return Boolean(ui.parkDialog); }
export function panelElement() { return ui.panel; }
export function parkElement() { return ui.parkDialog; }
