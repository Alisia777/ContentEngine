(() => {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const precisePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  const selector = ".auth-layout";
  let previousX = null;
  let previousY = null;

  function resetScene(scene) {
    scene.style.removeProperty("--auth-kpp-shift-x");
    scene.style.removeProperty("--auth-kpp-shift-y");
    previousX = null;
    previousY = null;
  }

  function resetAllScenes() {
    document.querySelectorAll(selector).forEach(resetScene);
  }

  function followPointer(event) {
    if (reduceMotion.matches || !precisePointer.matches) return;
    if (!(event.target instanceof Element)) return;

    const scene = event.target.closest(selector);
    if (!(scene instanceof HTMLElement)) return;

    const bounds = scene.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;

    const normalizedX = Math.max(-1, Math.min(1, ((event.clientX - bounds.left) / bounds.width) * 2 - 1));
    const normalizedY = Math.max(-1, Math.min(1, ((event.clientY - bounds.top) / bounds.height) * 2 - 1));
    const shiftX = Number((-normalizedX * 8).toFixed(2));
    const shiftY = Number((-normalizedY * 5).toFixed(2));

    if (previousX === shiftX && previousY === shiftY) return;
    previousX = shiftX;
    previousY = shiftY;
    scene.style.setProperty("--auth-kpp-shift-x", `${shiftX}px`);
    scene.style.setProperty("--auth-kpp-shift-y", `${shiftY}px`);
  }

  document.addEventListener("pointermove", followPointer, { passive: true });
  document.addEventListener("pointerout", (event) => {
    if (event.relatedTarget === null) resetAllScenes();
  }, { passive: true });
  window.addEventListener("blur", resetAllScenes);
  reduceMotion.addEventListener?.("change", resetAllScenes);
  precisePointer.addEventListener?.("change", resetAllScenes);
})();
