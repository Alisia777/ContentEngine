from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
MIGRATION = (
    ROOT / "supabase" / "migrations" / "202607310100_workspace_trash.sql"
).read_text(encoding="utf-8")
FIX = (
    ROOT / "supabase" / "migrations" / "202607310101_workspace_trash_contract_fixes.sql"
).read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
ALIAS = (APP / "workspace-os-v4-trash-rpc-alias.js").read_text(encoding="utf-8")
SCRIPT = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
STYLES = (APP / "workspace-os-v4-context-trash.css").read_text(encoding="utf-8")


def test_workspace_trash_is_server_backed_and_reversible() -> None:
    for marker in (
        "content_factory.workspace_trash_items",
        "content_factory.workspace_storage_cleanup_queue",
        "status in ('trashed', 'purged')",
        "original_folder_id",
        "original_position",
        "original_status",
        "creator_workspace_trash_browser",
        "creator_trash_workspace_items",
        "creator_restore_workspace_items",
        "creator_purge_workspace_items",
        "creator_complete_workspace_storage_cleanup",
        "workspace_items_trashed",
        "workspace_items_restored",
        "workspace_items_purged",
        "workspace_trash_emptied",
    ):
        assert marker in MIGRATION

    assert "delete from content_factory.workspace_media_locations" in MIGRATION
    assert "delete from content_factory.workspace_task_locations" in MIGRATION
    assert "insert into content_factory.workspace_media_locations" in MIGRATION
    assert "insert into content_factory.workspace_task_locations" in MIGRATION
    assert "set status = 'deleted'" in MIGRATION
    assert "set status = 'cancelled'" in MIGRATION


def test_workspace_trash_contract_is_fail_closed_and_role_scoped() -> None:
    for marker in (
        "alter table content_factory.workspace_trash_items enable row level security",
        "alter table content_factory.workspace_storage_cleanup_queue enable row level security",
        "revoke all on content_factory.workspace_trash_items",
        "revoke all on content_factory.workspace_storage_cleanup_queue",
        "array['owner', 'admin', 'producer', 'reviewer', 'operator']",
        "array['owner', 'admin', 'producer']",
        "array['owner', 'admin']",
        "workspace_item_access_denied",
        "workspace_empty_trash_access_denied",
        "begin_command",
        "finish_command",
        "idempotency_key",
    ):
        assert marker in MIGRATION

    for rpc in (
        "creator_workspace_trash_browser",
        "creator_trash_workspace_items",
        "creator_restore_workspace_items",
        "creator_purge_workspace_items",
        "creator_complete_workspace_storage_cleanup",
    ):
        assert f"revoke all on function public.{rpc}(jsonb)" in MIGRATION
        assert f"grant execute on function public.{rpc}(jsonb)" in MIGRATION

    assert "revoke execute on all functions in schema content_factory_private" in FIX
    assert "require_workspace_item_array(jsonb, integer)" in FIX


def test_conflict_targets_use_named_primary_keys_after_migration() -> None:
    for marker in (
        "workspace_media_locations_pkey",
        "workspace_task_locations_pkey",
        "workspace_storage_cleanup_queue_pkey",
        "pg_get_functiondef",
        "workspace_restore_conflict_target_fix_failed",
        "workspace_purge_conflict_target_fix_failed",
    ):
        assert marker in FIX


def test_trash_uses_a_dedicated_system_rpc_namespace() -> None:
    for marker in (
        "rename to workspace_trash_browser",
        "rename to workspace_trash_items",
        "rename to workspace_restore_items",
        "rename to workspace_purge_items",
        "rename to workspace_complete_storage_cleanup",
    ):
        assert marker in FIX

    for source, destination in (
        ("creator_workspace_trash_browser", "workspace_trash_browser"),
        ("creator_trash_workspace_items", "workspace_trash_items"),
        ("creator_restore_workspace_items", "workspace_restore_items"),
        ("creator_purge_workspace_items", "workspace_purge_items"),
        (
            "creator_complete_workspace_storage_cleanup",
            "workspace_complete_storage_cleanup",
        ),
    ):
        assert source in ALIAS
        assert destination in ALIAS
    assert "CreatorApi.prototype.call" in ALIAS
    assert "CreatorApi.prototype.mutate" in ALIAS
    assert "Symbol.for" in ALIAS
    for source in (ALIAS, SCRIPT):
        assert '"./supabase-api.js?v=20260805.os4.21"' in source
        assert "supabase-api.js?v=20260729.2" not in source


def test_permanent_media_delete_requires_a_purge_receipt() -> None:
    for marker in (
        "content_factory.storage_trash_delete_allowed",
        "workspace_storage_cleanup_queue",
        "queue.status = 'pending'",
        "media.status = 'deleted'",
        "content_factory.storage_object_is_unregistered",
        "content_factory.storage_trash_delete_allowed",
        "storage_cleanup",
    ):
        assert marker in MIGRATION

    # The browser can remove only an object already marked for purge. The row
    # and audit tombstone remain server-side even after private bytes are gone.
    assert "drop policy if exists contentengine_private_delete" in MIGRATION
    assert "create policy contentengine_private_delete" in MIGRATION


def test_context_actions_cover_files_tasks_folders_and_empty_surfaces() -> None:
    for marker in (
        'document.addEventListener("contextmenu"',
        'document.addEventListener("pointerdown"',
        "560",
        "finderItemActions",
        "taskActions",
        "folderActions",
        "emptySurfaceActions",
        "contextActions",
        "Открыть",
        "Переместить в папку…",
        "Скопировать ID",
        "Переместить в Корзину",
        "Новая папка внутри",
        "Переименовать",
        "Архивировать пустую папку",
    ):
        assert marker in SCRIPT


def test_inline_trash_surface_supports_restore_purge_empty_and_safe_previews() -> None:
    for marker in (
        "createTrashSurface",
            'openWorkspaceRoute("/workspace/board?view=trash")',
        "ensureTrashSurface",
        "Корзина",
        "Восстановить",
        "Удалить окончательно…",
        "Очистить Корзину…",
        'phrase: "ОЧИСТИТЬ"',
        "restoreTrashItems",
        "purgeTrashItems",
        "emptyTrash",
        "hydrateTrashPreviews",
        "createSignedUrl",
        ".storage.from(bucket).remove",
        "showUndoToast",
        'label: "Вернуть"',
        "Shift+Delete",
        "Delete — в Корзину · Shift+Delete — окончательно только внутри Корзины",
        "TRASH_PAGE_SIZE",
        "next_cursor",
    ):
        assert marker in SCRIPT


def test_trash_ui_uses_narrow_rpc_boundary_and_safe_dynamic_dom() -> None:
    for marker in (
        'import { CreatorApi } from "./supabase-api.js',
        "api.bootstrap",
        "api.commitBootstrapContext",
        "api.call(RPC.browser",
        "api.mutate(functionName",
        "creator_workspace_trash_browser",
        "creator_trash_workspace_items",
        "creator_restore_workspace_items",
        "creator_purge_workspace_items",
        "creator_complete_workspace_storage_cleanup",
    ):
        assert marker in SCRIPT

    for source in (SCRIPT, ALIAS):
        for forbidden in (
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "DOMParser",
            "createContextualFragment",
            "cloneNode",
            "requestSubmit",
            "service_role",
            "sb_secret_",
        ):
            assert forbidden not in source


def test_context_trash_loads_in_the_current_core_and_static_stability_order() -> None:
    for marker in (
        "workspace-os-v4-context-trash.css?v=${BUILD}",
        "workspace-os-v4-flow.css?v=${BUILD}",
        "workspace-os-v4-stability.css?v=${BUILD}",
        "workspace-os-v4-motion.css?v=${BUILD}",
        "workspace-os-v4.js?v=${BUILD}",
        "workspace-os-v4-trash-rpc-alias.js?v=${BUILD}",
        "workspace-os-v4-context-trash.js?v=${BUILD}",
    ):
        assert marker in LOADER

    assert LOADER.index("workspace-os-v4-context-trash.css?v=${BUILD}") < LOADER.index(
        "workspace-os-v4-stability.css?v=${BUILD}"
    )
    assert LOADER.index("workspace-os-v4.js?v=${BUILD}") < LOADER.index(
        "workspace-os-v4-trash-rpc-alias.js?v=${BUILD}"
    ) < LOADER.index(
        "workspace-os-v4-context-trash.js?v=${BUILD}"
    )
    for retired_controller in (
        "workspace-os-v4-stability.js",
        "workspace-os-v4-surface-guard.js",
        "workspace-os-v4-operations.js",
    ):
        assert retired_controller not in LOADER


def test_context_trash_styles_are_desktop_mobile_and_accessibility_aware() -> None:
    for marker in (
        ".ce-v4-context-menu",
        ".ce-v4-system-toast",
        ".ce-v4-trash-dock__badge",
        ".ce-v4-trash-surface",
        ".ce-v4-trash-grid",
        ".ce-v4-trash-item",
        ".ce-v4-trash-preview",
        ".ce-v4-trash-confirm",
        "@media (max-width: 680px)",
        "@media (max-height: 680px)",
        "@media (prefers-reduced-motion: reduce)",
        "content-visibility: auto",
    ):
        assert marker in STYLES

    for forbidden in (
        ".ce-v4-trash-backdrop",
        ".ce-v4-trash-preview-backdrop",
        ".ce-v4-confirm-backdrop",
        "body.ce-v4-trash-open .ce-v4-dock",
    ):
        assert forbidden not in STYLES

    assert STYLES.count("{") == STYLES.count("}")


def test_context_trash_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    for filename in (
        "workspace-os-v4-trash-rpc-alias.js",
        "workspace-os-v4-context-trash.js",
    ):
        subprocess.run(
            [node, "--check", str(APP / filename)],
            check=True,
            capture_output=True,
            text=True,
        )
