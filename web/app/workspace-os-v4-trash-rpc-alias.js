import { CreatorApi } from "./supabase-api.js?v=20260729.2";

/*
 * Desktop Trash is intentionally outside the frozen creator_* RPC count.
 * Keep the UI module's semantic command names stable while routing only these
 * five exact calls to the dedicated workspace_* system namespace.
 */

const PATCH_MARK = Symbol.for("contentengine.desktop-v4.trash-rpc-alias");
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

window.ContentEngineTrashRpcNamespace = Object.freeze({
  aliases: ALIASES,
  resolve: aliasName,
});
