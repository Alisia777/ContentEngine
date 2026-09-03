import { CreatorApi } from "./supabase-api.js?v=20260826.rebuild-clean.60";

/*
 * Desktop Trash is intentionally outside the frozen creator_* RPC count.
 * Keep the UI module's semantic command names stable while routing only these
 * five exact calls to the dedicated workspace_* system namespace.
 */

const PATCH_MARK = Symbol.for("contentengine.desktop-v4.trash-rpc-alias");
const EVENT_GUARD_MARK = Symbol.for("contentengine.desktop-v4.context-event-guard");
const EDITABLE_SELECTOR = [
  "input",
  "textarea",
  "select",
  "option",
  "[contenteditable='true']",
  "video",
  "audio",
].join(",");
const ALIASES = Object.freeze({
  creator_workspace_trash_browser: "workspace_trash_browser",
  creator_trash_workspace_items: "workspace_trash_items",
  creator_restore_workspace_items: "workspace_restore_items",
  creator_purge_workspace_items: "workspace_purge_items",
  creator_complete_workspace_storage_cleanup: "workspace_complete_storage_cleanup",
});

function aliasName(value) {
  const name = String(value || "");
  return ALIASES[name] || name;
}

if (CreatorApi.prototype[PATCH_MARK] !== true) {
  const originalCall = CreatorApi.prototype.call;
  const originalMutate = CreatorApi.prototype.mutate;

  Object.defineProperty(CreatorApi.prototype, PATCH_MARK, {
    value: true,
    configurable: false,
    enumerable: false,
    writable: false,
  });

  CreatorApi.prototype.call = function contentEngineTrashAliasedCall(functionName, payload = {}) {
    return originalCall.call(this, aliasName(functionName), payload);
  };

  CreatorApi.prototype.mutate = function contentEngineTrashAliasedMutate(functionName, payload = {}) {
    return originalMutate.call(this, aliasName(functionName), payload);
  };
}

function dismissDetachedContextMenu() {
  const menu = document.querySelector(".ce-v4-context-menu");
  if (!menu) return;
  menu.remove();
  document.body.classList.remove("ce-v4-context-open");
}

if (window[EVENT_GUARD_MARK] !== true) {
  Object.defineProperty(window, EVENT_GUARD_MARK, {
    value: true,
    configurable: false,
    enumerable: false,
    writable: false,
  });

  // Text fields, native selects and media keep their browser context menu.
  document.addEventListener("contextmenu", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(EDITABLE_SELECTOR)) event.stopImmediatePropagation();
  }, true);

  // Escape closes only the contextual menu. It must not continue to the Trash
  // window handler and close the entire workspace in the same key press.
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !document.querySelector(".ce-v4-context-menu")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    dismissDetachedContextMenu();
  }, true);

  window.addEventListener("blur", dismissDetachedContextMenu);
  window.addEventListener("resize", dismissDetachedContextMenu, { passive: true });
  document.addEventListener("scroll", dismissDetachedContextMenu, {
    capture: true,
    passive: true,
  });
}

window.ContentEngineTrashRpcNamespace = Object.freeze({
  aliases: ALIASES,
  resolve: aliasName,
});
