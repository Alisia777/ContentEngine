(() => {
  "use strict";

  const MODULE_DEADLINE_MS = 15_000;
  const APP_DEADLINE_MS = 40_000;
  let moduleLoaded = false;
  let settled = false;

  const root = () => document.querySelector("#app");
  const isBootScreenVisible = () => Boolean(root()?.querySelector(".boot-screen"));

  function renderFailure(kind = "startup") {
    if (settled || !isBootScreenVisible()) return;
    const host = root();
    if (!host) return;
    settled = true;
    window.clearTimeout(moduleTimer);
    window.clearTimeout(appTimer);
    const detail = kind === "module"
      ? "Не удалось загрузить защищённый клиент портала. Проверьте соединение или блокировщик контента."
      : "Портал не ответил за ожидаемое время. Обновите страницу — повторный запуск безопасен.";
    host.innerHTML = `
      <main id="main-content" class="boot-screen boot-screen--failed" tabindex="-1" role="alert">
        <div class="boot-mark" aria-hidden="true">!</div>
        <p class="eyebrow">Безопасный запуск остановлен</p>
        <h1>Рабочее место не открылось</h1>
        <p class="muted">${detail}</p>
        <button class="btn" type="button" data-boot-reload>Обновить страницу</button>
      </main>`;
    host.querySelector("[data-boot-reload]")?.addEventListener("click", () => window.location.reload());
    host.querySelector("#main-content")?.focus();
  }

  const moduleTimer = window.setTimeout(() => {
    if (!moduleLoaded) renderFailure("module");
  }, MODULE_DEADLINE_MS);
  const appTimer = window.setTimeout(() => renderFailure("startup"), APP_DEADLINE_MS);

  window.addEventListener("error", (event) => {
    const target = event.target;
    if (!moduleLoaded && target instanceof HTMLScriptElement && target.type === "module") {
      renderFailure("module");
    }
  }, true);

  window.CONTENTENGINE_BOOT_WATCHDOG = Object.freeze({
    moduleLoaded() {
      if (settled) return;
      moduleLoaded = true;
      window.clearTimeout(moduleTimer);
    },
    ready() {
      if (settled) return;
      settled = true;
      window.clearTimeout(moduleTimer);
      window.clearTimeout(appTimer);
    },
    failed(kind = "startup") {
      renderFailure(kind);
    },
  });
})();
