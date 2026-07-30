/*
 * ContentEngine live build guard.
 * Reads a same-origin static manifest only. It never touches business APIs,
 * credentials, forms or application state.
 */

const CURRENT_BUILD = "20260731.os2.1";
const MANIFEST_URL = new URL("./build.json", import.meta.url);
const CHECK_INTERVAL_MS = 10 * 60 * 1000;
const VALID_BUILD_ID = /^[a-z0-9._-]{4,80}$/iu;

const runtime = {
  checking: false,
  remote: null,
  pill: null,
  banner: null,
  timer: 0,
};

window.CONTENTENGINE_BUILD = Object.freeze({
  id: CURRENT_BUILD,
  label: "ContentEngine OS v2 · Generation + Finder",
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
  if (runtime.pill?.isConnected) return runtime.pill;
  const pill = makeElement("button", "ce-build-pill");
  pill.type = "button";
  pill.dataset.buildId = CURRENT_BUILD;
  pill.setAttribute("aria-label", `Версия интерфейса ${CURRENT_BUILD}. Проверить обновление`);
  pill.title = `ContentEngine OS · ${CURRENT_BUILD}`;
  pill.append(
    makeElement("span", "ce-build-pill__dot"),
    makeElement("span", "ce-build-pill__copy", `OS · ${CURRENT_BUILD.split(".").at(-1)}`),
  );
  pill.addEventListener("click", () => void checkForUpdate({ manual: true }));
  document.body.append(pill);
  runtime.pill = pill;
  return pill;
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

function showUpdate(remote) {
  const id = cleanBuildId(remote?.id);
  if (!id || id === CURRENT_BUILD) {
    removeBanner();
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
  copy.append(
    makeElement("strong", "", "Рабочее место обновилось"),
    makeElement("small", "", "Перезапустите интерфейс — открытые серверные задачи продолжат работу."),
  );
  const action = makeElement("button", "ce-build-update__action", "Обновить");
  action.type = "button";
  action.addEventListener("click", () => reloadIntoBuild(id));
  const close = makeElement("button", "ce-build-update__close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Скрыть сообщение об обновлении");
  close.addEventListener("click", removeBanner);

  banner.append(mark, copy, action, close);
  document.body.append(banner);
  runtime.banner = banner;
  document.body.classList.add("ce-build-update-visible");
}

function flashPill(message, tone = "ok") {
  const pill = ensurePill();
  const copy = pill.querySelector(".ce-build-pill__copy");
  if (!copy) return;
  const original = `OS · ${CURRENT_BUILD.split(".").at(-1)}`;
  copy.textContent = message;
  pill.dataset.tone = tone;
  window.setTimeout(() => {
    if (!pill.isConnected) return;
    copy.textContent = original;
    delete pill.dataset.tone;
  }, 1600);
}

async function checkForUpdate({ manual = false } = {}) {
  if (runtime.checking || !navigator.onLine) {
    if (manual && !navigator.onLine) flashPill("Нет сети", "warning");
    return null;
  }
  runtime.checking = true;
  ensurePill().setAttribute("aria-busy", "true");
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
    if (remoteId !== CURRENT_BUILD) showUpdate(manifest);
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
    runtime.pill?.removeAttribute("aria-busy");
  }
}

function start() {
  ensurePill();
  void checkForUpdate();
  runtime.timer = window.setInterval(() => {
    if (document.visibilityState === "visible") void checkForUpdate();
  }, CHECK_INTERVAL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void checkForUpdate();
  });
  window.addEventListener("pageshow", () => void checkForUpdate());
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}

window.ContentEngineBuildGuard = Object.freeze({
  id: CURRENT_BUILD,
  check: () => checkForUpdate({ manual: true }),
});
