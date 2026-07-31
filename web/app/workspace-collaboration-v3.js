/*
 * ContentEngine OS v3 local collaboration layer.
 * Notes, parking, decision journal, frame comments and handoff packets are
 * device-local helpers. They never call business APIs or impersonate server
 * assignment/presence.
 */

const core = window.ContentEngineOSV3;
if (!core) throw new Error("ContentEngineOSV3 core must load before collaboration layer");

const {
  q, qa, elementFrom, icon, compact, escapeMarkup, routePath, objects,
  openObjectCapsule, pushUndo, registerAdapter, registerCommand, scheduleMount,
} = core;

const STORAGE_KEY = "contentengine.os-v3.local-context.v1";
const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const runtime = {
  panel: null,
  activeKey: "",
  memory: readMemory(),
};

function readMemory() {
  try {
    const raw = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
    const now = Date.now();
    const clean = {};
    for (const [key, value] of Object.entries(raw)) {
      if (!value || typeof value !== "object") continue;
      if (now - Number(value.updatedAt || 0) > MAX_AGE_MS) continue;
      clean[key] = value;
    }
    return clean;
  } catch {
    return {};
  }
}

function persist() {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(runtime.memory)); } catch { /* optional */ }
}

function contextFor(key) {
  const current = runtime.memory[key];
  return current && typeof current === "object" ? current : {
    note: "",
    parked: false,
    parkingReason: "",
    returnAt: "",
    decisions: [],
    frames: [],
    updatedAt: Date.now(),
  };
}

function saveContext(key, patch) {
  const previous = contextFor(key);
  runtime.memory[key] = { ...previous, ...patch, updatedAt: Date.now() };
  persist();
  applyEntityState(key);
  if (runtime.activeKey === key) renderPanelBody();
  scheduleMount();
  return previous;
}

function objectForKey(key) {
  return objects().find((object) => object.key === key) || null;
}

function formatTimestamp(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const rest = Math.floor(value % 60);
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function formatDate(value) {
  const parsed = Date.parse(String(value || ""));
  if (!Number.isFinite(parsed)) return "";
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(parsed));
}

function safeText(value, limit = 1200) {
  return compact(String(value || "").replace(/[\u0000-\u001f\u007f]/gu, " "), limit);
}

function applyEntityState(key) {
  const context = contextFor(key);
  qa(`[data-ce-v3-object-key="${CSS.escape(key)}"], [data-entity-key="${CSS.escape(key)}"]`).forEach((node) => {
    const card = node.matches?.("[data-ce-v3-object-key]") ? node : node.closest?.("[data-ce-v3-object-key]");
    card?.classList.toggle("ce-v3-parked", context.parked === true);
    card?.classList.toggle("ce-v3-has-note", Boolean(context.note || context.decisions?.length || context.frames?.length));
  });
  const object = objectForKey(key);
  object?.node?.classList.toggle("ce-v3-parked", context.parked === true);
  object?.node?.classList.toggle("ce-v3-has-note", Boolean(context.note || context.decisions?.length || context.frames?.length));
}

function applyAllStates() {
  for (const key of Object.keys(runtime.memory)) applyEntityState(key);
}

function panelMarkup(object, context) {
  const parkedCopy = context.parked
    ? `${context.parkingReason || "Ожидание"}${context.returnAt ? ` · вернуться ${formatDate(context.returnAt)}` : ""}`
    : "Задача активна";
  return `
    <div class="ce-v3-local-panel__body">
      <section class="ce-v3-local-summary">
        <span>${icon(context.parked ? "clock" : "note", 24)}</span>
        <div><small>ЛОКАЛЬНЫЙ КОНТЕКСТ</small><strong>${escapeMarkup(object?.title || "Рабочий объект")}</strong><p>${escapeMarkup(parkedCopy)}</p></div>
      </section>

      <section class="ce-v3-local-section">
        <header><div><small>ЗАМЕТКА</small><strong>Что нельзя потерять</strong></div><span>только на этом устройстве</span></header>
        <textarea data-local-note maxlength="2000" placeholder="Короткая мысль, вопрос или следующий шаг…">${escapeMarkup(context.note || "")}</textarea>
        <div class="ce-v3-local-actions"><button type="button" data-local-save-note>${icon("note", 16)} Сохранить заметку</button>${context.note ? '<button type="button" data-local-clear-note>Очистить</button>' : ""}</div>
      </section>

      <section class="ce-v3-local-section">
        <header><div><small>ПАРКОВКА</small><strong>Убрать из головы, не потерять</strong></div></header>
        <div class="ce-v3-parking-grid">
          <label><span>Причина</span><select data-local-parking-reason><option value="">Выберите</option>${["Жду ответ", "Жду файл", "Жду генерацию", "Нужна правка", "Вернуться позже"].map((reason) => `<option value="${escapeMarkup(reason)}" ${context.parkingReason === reason ? "selected" : ""}>${escapeMarkup(reason)}</option>`).join("")}</select></label>
          <label><span>Вернуться</span><input data-local-return-at type="datetime-local" value="${escapeMarkup(context.returnAt || "")}" /></label>
        </div>
        <div class="ce-v3-local-actions"><button type="button" data-local-toggle-park class="${context.parked ? "is-active" : ""}">${icon("clock", 16)} ${context.parked ? "Вернуть в работу" : "Припарковать"}</button></div>
      </section>

      <section class="ce-v3-local-section">
        <header><div><small>ЖУРНАЛ РЕШЕНИЙ</small><strong>Что решили и почему</strong></div><span>${context.decisions?.length || 0}</span></header>
        <form data-local-decision-form><input name="decision" maxlength="500" required placeholder="Например: публикуем только после подтверждения прав" /><button type="submit">Добавить</button></form>
        <div class="ce-v3-decision-list">${(context.decisions || []).length ? context.decisions.map((decision, index) => `<article><i></i><div><strong>${escapeMarkup(decision.text)}</strong><small>${escapeMarkup(formatDate(decision.at))}</small></div><button type="button" data-local-delete-decision="${index}" aria-label="Удалить">×</button></article>`).join("") : '<p class="ce-v3-local-empty">Решений пока нет.</p>'}</div>
      </section>

      <section class="ce-v3-local-section ce-v3-frame-section" ${routePath() === "/workspace/review" ? "" : "hidden"}>
        <header><div><small>КОММЕНТАРИИ К КАДРУ</small><strong>Точный момент видео</strong></div><span>${context.frames?.length || 0}</span></header>
        <form data-local-frame-form><input name="comment" maxlength="500" required placeholder="Что не так в текущем кадре?" /><button type="submit">${icon("frame", 16)} Кадр</button></form>
        <div class="ce-v3-frame-list">${(context.frames || []).length ? context.frames.map((frame, index) => `<article><button type="button" data-local-seek-frame="${frame.time}">${formatTimestamp(frame.time)}</button><div><strong>${escapeMarkup(frame.text)}</strong><small>${escapeMarkup(formatDate(frame.at))}</small></div><button type="button" data-local-delete-frame="${index}" aria-label="Удалить">×</button></article>`).join("") : '<p class="ce-v3-local-empty">Поставьте видео на паузу и сохраните точный момент.</p>'}</div>
      </section>

      <section class="ce-v3-local-section">
        <header><div><small>ПЕРЕДАЧА</small><strong>Собрать контекст одним пакетом</strong></div></header>
        <div class="ce-v3-handoff-preview" data-local-handoff-preview></div>
        <div class="ce-v3-local-actions"><button type="button" data-local-copy-handoff>${icon("handoff", 16)} Скопировать передачу</button></div>
      </section>
    </div>`;
}

function buildHandoff(object, context) {
  const lines = [
    `Задача: ${object?.title || "Рабочий объект"}`,
    `Раздел: ${object?.route || routePath()}`,
    object?.status ? `Статус: ${object.status}` : "",
    object?.subtitle ? `Контекст: ${object.subtitle}` : "",
    context.parked ? `Ожидание: ${context.parkingReason || "припарковано"}${context.returnAt ? ` до ${formatDate(context.returnAt)}` : ""}` : "",
    context.note ? `Заметка: ${context.note}` : "",
    context.decisions?.length ? "Решения:" : "",
    ...(context.decisions || []).map((decision) => `- ${decision.text}`),
    context.frames?.length ? "Комментарии к видео:" : "",
    ...(context.frames || []).map((frame) => `- ${formatTimestamp(frame.time)} — ${frame.text}`),
    `Следующий шаг: ${object?.blocked ? "снять блокер и подтвердить owner-а" : "продолжить из текущего рабочего пространства"}`,
  ].filter(Boolean);
  return lines.join("\n");
}

function renderPanelBody() {
  const panel = runtime.panel;
  const key = runtime.activeKey;
  if (!panel || !key) return;
  const object = objectForKey(key) || { key, title: key, route: routePath(), subtitle: "", status: "" };
  const context = contextFor(key);
  const host = q("[data-local-panel-body]", panel);
  host.innerHTML = panelMarkup(object, context);
  q("[data-local-handoff-preview]", panel).textContent = buildHandoff(object, context);
}

function closePanel({ restoreFocus = true } = {}) {
  const panel = runtime.panel;
  if (!panel) return;
  const trigger = panel._trigger;
  panel.classList.add("is-closing");
  const finish = () => {
    panel.remove();
    runtime.panel = null;
    runtime.activeKey = "";
    document.body.classList.remove("ce-v3-local-panel-open");
    if (restoreFocus) trigger?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 220);
}

function openPanel(key, trigger = document.activeElement) {
  if (!key) return;
  runtime.activeKey = key;
  if (runtime.panel) {
    renderPanelBody();
    return;
  }
  const panel = elementFrom(`
    <div class="ce-v3-local-panel-backdrop">
      <aside class="ce-v3-local-panel" role="dialog" aria-modal="true" aria-labelledby="ce-v3-local-panel-title">
        <header><div><small>CONTENTENGINE OS · LOCAL</small><strong id="ce-v3-local-panel-title">Контекст задачи</strong></div><button type="button" data-local-panel-close aria-label="Закрыть">${icon("close", 19)}</button></header>
        <div data-local-panel-body></div>
        <footer>${icon("warning", 15)} <span>Локальная память не заменяет серверное назначение, официальный комментарий или решение руководителя.</span></footer>
      </aside>
    </div>`);
  panel._trigger = trigger;
  panel.addEventListener("click", handlePanelClick);
  panel.addEventListener("submit", handlePanelSubmit);
  document.body.append(panel);
  runtime.panel = panel;
  document.body.classList.add("ce-v3-local-panel-open");
  renderPanelBody();
  q("[data-local-panel-close]", panel)?.focus({ preventScroll: true });
}

function currentVideo() {
  return q(".content-review-page video, [data-content-review-exact-media][src], .review-os-result video");
}

async function copyText(value) {
  const text = String(value || "");
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch { copied = false; }
    area.remove();
    return copied;
  }
}

function handlePanelClick(event) {
  if (!(event.target instanceof Element)) return;
  if (event.target === runtime.panel || event.target.closest("[data-local-panel-close]")) {
    closePanel();
    return;
  }
  const key = runtime.activeKey;
  const context = contextFor(key);
  if (event.target.closest("[data-local-save-note]")) {
    const value = safeText(q("[data-local-note]", runtime.panel)?.value, 2000);
    saveContext(key, { note: value });
    return;
  }
  if (event.target.closest("[data-local-clear-note]")) {
    const previous = context.note;
    saveContext(key, { note: "" });
    pushUndo({ label: "Заметка очищена", undo() { saveContext(key, { note: previous }); } });
    return;
  }
  if (event.target.closest("[data-local-toggle-park]")) {
    const reason = safeText(q("[data-local-parking-reason]", runtime.panel)?.value, 120);
    const returnAt = String(q("[data-local-return-at]", runtime.panel)?.value || "");
    const previous = context.parked;
    saveContext(key, { parked: !previous, parkingReason: reason, returnAt });
    pushUndo({ label: previous ? "Задача возвращена в работу" : "Задача припаркована", undo() { saveContext(key, { parked: previous }); } });
    return;
  }
  const decisionButton = event.target.closest("[data-local-delete-decision]");
  if (decisionButton) {
    const index = Number(decisionButton.dataset.localDeleteDecision);
    const decisions = [...(context.decisions || [])];
    const [removed] = decisions.splice(index, 1);
    saveContext(key, { decisions });
    if (removed) pushUndo({ label: "Решение удалено", undo() { const next = [...contextFor(key).decisions]; next.splice(index, 0, removed); saveContext(key, { decisions: next }); } });
    return;
  }
  const frameDelete = event.target.closest("[data-local-delete-frame]");
  if (frameDelete) {
    const index = Number(frameDelete.dataset.localDeleteFrame);
    const frames = [...(context.frames || [])];
    const [removed] = frames.splice(index, 1);
    saveContext(key, { frames });
    if (removed) pushUndo({ label: "Комментарий к кадру удалён", undo() { const next = [...contextFor(key).frames]; next.splice(index, 0, removed); saveContext(key, { frames: next }); } });
    return;
  }
  const seek = event.target.closest("[data-local-seek-frame]");
  if (seek) {
    const video = currentVideo();
    if (video instanceof HTMLVideoElement) {
      video.currentTime = Math.max(0, Number(seek.dataset.localSeekFrame) || 0);
      video.pause();
      video.scrollIntoView({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "center" });
    }
    return;
  }
  if (event.target.closest("[data-local-copy-handoff]")) {
    const object = objectForKey(key) || { title: key, route: routePath(), subtitle: "", status: "" };
    const text = buildHandoff(object, context);
    void copyText(text).then((copied) => {
      const button = q("[data-local-copy-handoff]", runtime.panel);
      if (!button) return;
      const original = button.innerHTML;
      button.textContent = copied ? "Передача скопирована" : "Выделите текст вручную";
      window.setTimeout(() => { if (button.isConnected) button.innerHTML = original; }, 1600);
    });
  }
}

function handlePanelSubmit(event) {
  event.preventDefault();
  const key = runtime.activeKey;
  const context = contextFor(key);
  const form = event.target;
  if (form.matches("[data-local-decision-form]")) {
    const text = safeText(new FormData(form).get("decision"), 500);
    if (!text) return;
    saveContext(key, { decisions: [...(context.decisions || []), { text, at: new Date().toISOString() }].slice(-50) });
    return;
  }
  if (form.matches("[data-local-frame-form]")) {
    const text = safeText(new FormData(form).get("comment"), 500);
    const video = currentVideo();
    if (!text || !(video instanceof HTMLVideoElement)) return;
    saveContext(key, { frames: [...(context.frames || []), { text, time: Number(video.currentTime || 0), at: new Date().toISOString() }].slice(-80) });
  }
}

function ensureReviewFrameButton() {
  if (routePath() !== "/workspace/review") return;
  const video = currentVideo();
  if (!(video instanceof HTMLVideoElement)) return;
  const host = video.closest(".content-review-decision-preview, .content-review-result__header, .review-os-result-panel") || video.parentElement;
  if (!host || q("[data-ce-v3-frame-comments]", host)) return;
  const object = objects().find((item) => item.route === "/workspace/review") || objects()[0];
  if (!object) return;
  const button = elementFrom(`<button class="ce-v3-frame-comment-button" type="button" data-ce-v3-frame-comments="${escapeMarkup(object.key)}">${icon("frame", 16)}<span>Комментарий к кадру</span></button>`);
  host.append(button);
}

function mountCollaboration() {
  applyAllStates();
  ensureReviewFrameButton();
}

function handleGlobalClick(event) {
  if (!(event.target instanceof Element)) return;
  const local = event.target.closest("[data-ce-v3-local-action]");
  if (local) {
    const key = local.dataset.entityKey || local.closest("[data-ce-v3-object-key]")?.dataset.ceV3ObjectKey || "";
    const action = local.dataset.ceV3LocalAction;
    if (action === "park") {
      const context = contextFor(key);
      const previous = context.parked;
      saveContext(key, { parked: !previous, parkingReason: context.parkingReason || "Вернуться позже" });
      pushUndo({ label: previous ? "Задача возвращена" : "Задача припаркована", undo() { saveContext(key, { parked: previous }); } });
    } else {
      openPanel(key, local);
    }
    event.preventDefault();
    return;
  }
  const frame = event.target.closest("[data-ce-v3-frame-comments]");
  if (frame) {
    openPanel(frame.dataset.ceV3FrameComments, frame);
    event.preventDefault();
  }
}

registerCommand({
  id: "local-context",
  title: "Открыть заметки и передачу",
  subtitle: "Парковка, решения, комментарии к кадру",
  icon: "note",
  keywords: "заметка передача решение кадр парковка",
  run() {
    const object = objects()[0];
    if (object) openPanel(object.key);
  },
});

registerAdapter("collaboration-v3", mountCollaboration);
document.addEventListener("click", handleGlobalClick, true);
document.addEventListener("keydown", (event) => {
  if (runtime.panel && event.key === "Escape") {
    event.preventDefault();
    closePanel();
  }
}, true);
