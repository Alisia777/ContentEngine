/* Spatial close choreography for Mission Control, focus and context sheets. */

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const CLOSE_DURATION_MS = 210;

const closeRuntime = {
  closing: false,
  timer: 0,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function closeDescriptor(target) {
  if (!(target instanceof Element)) return null;

  const overview = target.closest("[data-overview-close], [data-workspace-overview-backdrop]");
  if (overview || target.matches(".workspace-overview-backdrop")) {
    const backdrop = q(".workspace-overview-backdrop");
    return backdrop ? {
      roots: [backdrop, q(".workspace-overview", backdrop)].filter(Boolean),
      trigger: q("[data-overview-close]", backdrop) || backdrop,
    } : null;
  }

  const focus = target.closest("[data-workspace-focus-close], [data-workspace-focus-backdrop]");
  if (focus || target.matches(".workspace-focus-backdrop")) {
    const surface = q(".workspace-task-focused");
    const backdrop = q(".workspace-focus-backdrop");
    const trigger = q("[data-workspace-focus-close]", surface) || backdrop;
    return trigger ? { roots: [surface, backdrop].filter(Boolean), trigger } : null;
  }

  const context = target.closest("[data-productivity-context-close]");
  if (context || target.matches(".workspace-context-backdrop")) {
    const panel = q(".workspace-context-panel");
    const backdrop = q(".workspace-context-backdrop");
    const trigger = q("[data-productivity-context-close]", panel) || backdrop;
    return trigger ? { roots: [panel, backdrop].filter(Boolean), trigger } : null;
  }

  const park = target.closest("[data-productivity-park-close]");
  if (park || target.matches(".workspace-park-backdrop")) {
    const dialog = q(".workspace-park-dialog");
    const backdrop = q(".workspace-park-backdrop");
    const trigger = q("[data-productivity-park-close]", dialog) || backdrop;
    return trigger ? { roots: [dialog, backdrop].filter(Boolean), trigger } : null;
  }

  return null;
}

function activeCloseDescriptor() {
  return closeDescriptor(
    q("[data-productivity-park-close]")
      || q("[data-productivity-context-close]")
      || q("[data-workspace-focus-close]")
      || q("[data-overview-close]"),
  );
}

function finishClose(descriptor) {
  closeRuntime.closing = false;
  closeRuntime.timer = 0;
  descriptor.trigger?.click();
}

function beginClose(descriptor) {
  if (!descriptor || closeRuntime.closing) return false;
  if (REDUCED_MOTION.matches) return false;
  closeRuntime.closing = true;
  descriptor.roots.forEach((root) => root.classList.add("workspace-spatial-closing"));
  document.body.classList.add("workspace-spatial-close-active");
  window.clearTimeout(closeRuntime.timer);
  closeRuntime.timer = window.setTimeout(() => {
    document.body.classList.remove("workspace-spatial-close-active");
    finishClose(descriptor);
  }, CLOSE_DURATION_MS);
  return true;
}

function handleCloseClick(event) {
  if (!event.isTrusted || event.defaultPrevented || event.button !== 0) return;
  const descriptor = closeDescriptor(event.target);
  if (!descriptor || !beginClose(descriptor)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function handleCloseKeydown(event) {
  if (!event.isTrusted || event.key !== "Escape" || event.defaultPrevented) return;
  const descriptor = activeCloseDescriptor();
  if (!descriptor || !beginClose(descriptor)) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function cleanupStaleCloseState() {
  if (
    !q(".workspace-overview-backdrop")
    && !q(".workspace-task-focused")
    && !q(".workspace-context-panel")
    && !q(".workspace-park-dialog")
  ) {
    closeRuntime.closing = false;
    window.clearTimeout(closeRuntime.timer);
    closeRuntime.timer = 0;
    document.body.classList.remove("workspace-spatial-close-active");
  }
}

new MutationObserver(cleanupStaleCloseState).observe(document.body, { childList: true, subtree: true });
window.addEventListener("click", handleCloseClick, true);
window.addEventListener("keydown", handleCloseKeydown, true);
REDUCED_MOTION.addEventListener?.("change", cleanupStaleCloseState);
