/*
 * ContentEngine live build guard.
 * Reads a same-origin static manifest only. It never touches business APIs,
 * credentials, forms or application state.
 */

const CURRENT_BUILD = "20260826.rebuild-clean.60";
const BUILD_BADGE = "Desktop · 21.08.17";
const MANIFEST_URL = new URL("./build.json", import.meta.url);
const CHECK_INTERVAL_MS = 10 * 60 * 1000;
const VALID_BUILD_ID = /^[a-z0-9._-]{4,80}$/iu;

const runtime = {
  checking: false,
  remote: null,
  pill: null,
  pillTimer: 0,
  banner: null,
  timer: 0,
  autoReloadTimer: 0,
  autoReloadDeadline: 0,
};

// Обновление не должно рвать живую работу: занятая форма, открытый диалог или
// активный ввод откладывают автоперезапуск — остаётся видимый баннер с кнопкой.
function interfaceIsBusy() {
  try {
    if (document.querySelector(
      'form[data-dirty], form[data-busy="true"], [data-busy="true"], dialog[open]',
    )) return true;
    const active = document.activeElement;
    if (
      active instanceof HTMLElement
      && (["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)
        || active.isContentEditable)
    ) return true;
  } catch {
    return true;
  }
  return false;
}

window.CONTENTENGINE_BUILD = Object.freeze({
  id: CURRENT_BUILD,
  label: "ContentEngine Desktop v4.41 · Provider reconciliation 14",
});

function cleanBuildId(value) {
  const id = String(value || "").trim();
  return VALID_BUILD_ID.test(id) ? id : "";
}

function makeElement(tag, className, text = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function ensurePill() {
  window.clearTimeout(runtime.pillTimer);
  runtime.pillTimer = 0;
  if (runtime.pill?.isConnected) return runtime.pill;
  const pill = makeElement("button", "ce-build-pill");
  pill.type = "button";
  pill.dataset.buildId = CURRENT_BUILD;
  pill.setAttribute("aria-label", `Версия интерфейса ${CURRENT_BUILD}. Проверить обновление`);
  pill.title = `ContentEngine Desktop · ${CURRENT_BUILD}`;
  pill.append(
    makeElement("span", "ce-build-pill__dot"),
    makeElement("span", "ce-build-pill__copy", BUILD_BADGE),
  );
  pill.addEventListener("click", () => void checkForUpdate({ manual: true }));
  document.body.append(pill);
  runtime.pill = pill;
  return pill;
}

function removePill() {
  window.clearTimeout(runtime.pillTimer);
  runtime.pillTimer = 0;
  runtime.pill?.remove();
  runtime.pill = null;
}

function removeBanner() {
  runtime.banner?.remove();
  runtime.banner = null;
  document.body.classList.remove("ce-build-update-visible");
}

function reloadIntoBuild(buildId) {
  const id = cleanBuildId(buildId);
  if (!id) return;
  const url = new URL(window.location.href);
  url.searchParams.set("build", id);
  url.searchParams.set("fresh", String(Date.now()));
  window.location.replace(url.toString());
}

function cancelAutoReload() {
  window.clearTimeout(runtime.autoReloadTimer);
  runtime.autoReloadTimer = 0;
  runtime.autoReloadDeadline = 0;
}

function scheduleAutoReload(id, banner) {
  cancelAutoReload();
  const countdown = banner.querySelector("[data-build-countdown]");
  runtime.autoReloadDeadline = Date.now() + 15_000;
  const tick = () => {
    if (runtime.banner !== banner || !banner.isConnected) return cancelAutoReload();
    if (interfaceIsBusy()) {
      // Человек занят: не дёргаем. Баннер остаётся, кнопка работает.
      if (countdown) countdown.textContent = "Обновится после того, как закончите ввод, — или нажмите сейчас.";
      runtime.autoReloadDeadline = Date.now() + 15_000;
      runtime.autoReloadTimer = window.setTimeout(tick, 3_000);
      return;
    }
    const remainingMs = runtime.autoReloadDeadline - Date.now();
    if (remainingMs <= 0) {
      reloadIntoBuild(id);
      return;
    }
    if (countdown) {
      countdown.textContent = `Обновится само через ${Math.ceil(remainingMs / 1_000)} с — или нажмите сейчас.`;
    }
    runtime.autoReloadTimer = window.setTimeout(tick, 1_000);
  };
  tick();
}

function showUpdate(remote, { force = false, title = "" } = {}) {
  const id = cleanBuildId(remote?.id);
  if (!id || (id === CURRENT_BUILD && !force)) {
    removeBanner();
    cancelAutoReload();
    return;
  }
  runtime.remote = { id, label: String(remote?.label || "Новая версия ContentEngine") };
  if (runtime.banner?.isConnected) return;

  const banner = makeElement("aside", "ce-build-update");
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");

  const mark = makeElement("span", "ce-build-update__mark", "↻");
  mark.setAttribute("aria-hidden", "true");
  const copy = makeElement("div", "ce-build-update__copy");
  const countdown = makeElement("small", "", "Перезапустите интерфейс — открытые серверные задачи продолжат работу.");
  countdown.dataset.buildCountdown = "";
  copy.append(
    makeElement("strong", "", title || "Рабочее место обновилось"),
    countdown,
  );
  const action = makeElement("button", "ce-build-update__action", "Обновить");
  action.type = "button";
  action.addEventListener("click", () => reloadIntoBuild(id));
  const close = makeElement("button", "ce-build-update__close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Скрыть сообщение об обновлении");
  close.addEventListener("click", () => {
    cancelAutoReload();
    removeBanner();
  });

  banner.append(mark, copy, action, close);
  document.body.append(banner);
  runtime.banner = banner;
  document.body.classList.add("ce-build-update-visible");
  scheduleAutoReload(id, banner);
}

function flashPill(message, tone = "ok") {
  const pill = ensurePill();
  const copy = pill.querySelector(".ce-build-pill__copy");
  if (!copy) return;
  copy.textContent = message;
  pill.dataset.tone = tone;
  window.clearTimeout(runtime.pillTimer);
  runtime.pillTimer = window.setTimeout(() => {
    if (runtime.pill === pill) removePill();
  }, 1600);
}

async function checkForUpdate({ manual = false } = {}) {
  if (runtime.checking || !navigator.onLine) {
    if (manual && !navigator.onLine) flashPill("Нет сети", "warning");
    return null;
  }
  runtime.checking = true;
  const pill = manual ? ensurePill() : null;
  pill?.setAttribute("aria-busy", "true");
  try {
    const url = new URL(MANIFEST_URL);
    url.searchParams.set("t", String(Date.now()));
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`build_manifest_${response.status}`);
    const manifest = await response.json();
    const remoteId = cleanBuildId(manifest?.id);
    if (!remoteId) throw new Error("build_manifest_invalid");
    if (remoteId !== CURRENT_BUILD) {
      showUpdate(manifest);
      if (manual) removePill();
    }
    else {
      removeBanner();
      if (manual) flashPill("Актуально");
    }
    return manifest;
  } catch (error) {
    if (manual) flashPill("Проверим позже", "warning");
    console.warn("ContentEngine build check unavailable", error);
    return null;
  } finally {
    runtime.checking = false;
    pill?.removeAttribute("aria-busy");
  }
}

function start() {
  void checkForUpdate();
  runtime.timer = window.setInterval(() => {
    if (document.visibilityState === "visible") void checkForUpdate();
  }, CHECK_INTERVAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void checkForUpdate();
  });
  window.addEventListener("pageshow", () => void checkForUpdate());
}

// Смесь сборок в одной вкладке: модуль другой эпохи сообщает о себе этим
// событием (реестр адаптеров os-v4 и привязка форм guided). Рендер и клики в
// такой вкладке принадлежат разным версиям — предсказуемого поведения нет, и
// единственное честное лечение — перезагрузка. Баннер форсируется даже когда
// манифест совпадает с НАШЕЙ эпохой: чужая половина всё равно уже в памяти.
window.addEventListener("contentengine:mixed-build-detected", () => {
  void checkForUpdate().then((manifest) => {
    const id = cleanBuildId(manifest?.id) || CURRENT_BUILD;
    showUpdate(
      { id, label: "Согласование версий интерфейса" },
      { force: true, title: "Интерфейс обновился посреди работы" },
    );
  });
});

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}

window.ContentEngineBuildGuard = Object.freeze({
  id: CURRENT_BUILD,
  check: () => checkForUpdate({ manual: true }),
});
