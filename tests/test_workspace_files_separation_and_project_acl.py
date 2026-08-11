from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608110005_workspace_files_separation_and_project_acl.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
BOARD = (ROOT / "web/app/workspace-board-view.js").read_text(encoding="utf-8")
FINDER = (ROOT / "web/app/workspace-os-v4-finder.js").read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unbalanced function: {declaration}")


def test_migration_parses_and_reloads_postgrest_after_public_rpc_replacement() -> None:
    assert len(parse_sql(SQL)) >= 25
    assert "notify pgrst, 'reload schema';" in SQL.lower()
    assert SQL.lower().rindex("notify pgrst") < SQL.lower().rindex("commit;")


def test_legacy_projects_get_exactly_the_five_durable_system_roles() -> None:
    for role in ("sources", "drafts", "review", "ready", "published"):
        assert f"('{role}'" in SQL
    assert "repair_workspace_project_system_folders" in SQL
    assert "folder.system_role is null" in SQL
    assert "lower(btrim(folder.name)) = lower(role.name)" in SQL
    assert "where not exists" in SQL.lower()
    assert "project.kind = 'project'" in SQL
    assert "project.status = 'active'" in SQL


def test_location_repair_preserves_same_project_custom_folders_only() -> None:
    repair = SQL[
        SQL.index("content_factory_private.repair_workspace_classified_media_locations(") :
        SQL.index("revoke all on function\n  content_factory_private.repair_workspace_classified_media_locations")
    ]
    assert "current_system_role is null" in repair
    assert "current_project_id is not distinct from p_project_id" in repair
    assert "workspace_project_for_folder" in repair
    assert "current_folder_id = destination_folder_id" in repair
    assert "sync_workspace_media_system_location" in repair


def test_folder_write_adapters_require_exact_project_acl_and_targets() -> None:
    for rpc in (
        "creator_create_workspace_folder",
        "creator_update_workspace_folder",
        "creator_move_workspace_items",
    ):
        declaration = f"create or replace function public.{rpc}("
        body = SQL[SQL.index(declaration) :]
        body = body[: body.index("\n$$;", body.index("as $$"))]
        assert "'project_id'" in body
        assert "project_id_required" in body
        assert "require_workspace_project_access" in body
        assert "workspace_project_for_folder" in body or rpc == "creator_move_workspace_items"
        assert "pg_advisory_xact_lock" in body

    assert SQL.count("workspace_folder_project_mismatch") >= 3
    assert SQL.count("workspace_system_folder_manual_destination_forbidden") >= 3
    assert "workspace_system_folder_read_only" in SQL


def test_move_validates_entities_without_requiring_a_preexisting_location() -> None:
    move = SQL[SQL.index("create or replace function public.creator_move_workspace_items(") :]
    validation = move[move.index("for item in") : move.index("result_value :=")]
    media_check = validation[validation.index("if item.entity_type = 'media'") : validation.index("else")]
    task_check = validation[validation.index("else") :]
    assert "from content_factory.media_objects media" in media_check
    assert "join content_factory.workspace_media_locations" not in media_check
    assert "insert into content_factory.workspace_media_locations" in validation
    assert "from content_factory.creator_tasks task" in task_check
    assert "join content_factory.workspace_task_locations" not in task_check
    assert "insert into content_factory.workspace_task_locations" in validation
    assert "on conflict (organization_id, media_object_id) do nothing" in validation
    assert "on conflict (organization_id, task_id) do nothing" in validation
    assert "media.project_id = project_id_value" in validation
    assert "task.project_id = project_id_value" in validation


def test_browser_api_and_every_runtime_callsite_send_the_exact_project() -> None:
    create = API[API.index("createWorkspaceFolder(") : API.index("\n  projectFlow(")]
    update = API[API.index("updateWorkspaceFolder(") : API.index("\n  moveWorkspaceItems(")]
    move = API[API.index("moveWorkspaceItems(") : API.index("\n  inviteAttempts(")]
    assert "project_id: requiredProjectId(projectIdSnake || projectId)" in create
    assert "project_id: requiredProjectId(changes.project_id || changes.projectId)" in update
    assert "project_id: requiredProjectId(scope.project_id || scope.projectId)" in move

    create_call = APP[APP.index("state.api.createWorkspaceFolder({") :]
    create_call = create_call[: create_call.index("});")]
    assert "projectId: currentWorkspaceProjectId()" in create_call

    for call_start in (
        "state.api.updateWorkspaceFolder(folderId, {",
        "state.api.updateWorkspaceFolder(folder.id, {",
    ):
        call = APP[APP.index(call_start) :]
        call = call[: call.index("});")]
        assert "projectId: currentWorkspaceProjectId()" in call

    item_move = APP[APP.index("await state.api.moveWorkspaceItems(") :]
    item_move = item_move[: item_move.index("\n    );")]
    assert "{ projectId: currentWorkspaceProjectId() }" in item_move
    assert "{ projectId: finderProjectId() }" in FINDER


def test_system_parent_guard_is_scoped_to_folder_create_not_item_move() -> None:
    create = _function(APP, "async function submitWorkspaceFolderCreate(form)")
    move_start = APP.index("async function moveWorkspaceBoardItem({")
    move_end = APP.index("\nasync function ", move_start + 1)
    move = APP[move_start:move_end]
    assert "folder.id === rawParentId" in create
    assert "parentFolder?.systemRole" in create
    assert "rawParentId" not in move
    assert "destinationFolder?.systemRole" in move


def test_client_preserves_provenance_and_never_offers_system_move_targets() -> None:
    assert "source.artifact_class ?? source.artifactClass" in BOARD
    assert "source.lifecycle_stage ?? source.lifecycleStage" in BOARD
    assert 'data-artifact-class="${escapeHtml(item.artifactClass)}"' in BOARD
    assert 'data-lifecycle-stage="${escapeHtml(item.lifecycleStage)}"' in BOARD
    assert "folder.status === \"active\"" in BOARD
    assert "&& !folder.systemRole" in BOARD
    assert "folder.systemRole ? 'data-system-folder=\"true\"' : \"data-workspace-drop-folder\"" in BOARD
    assert "!String(row.dataset.systemRole || \"\").trim()" in FINDER


def test_page_local_mime_smart_folders_are_retired_without_exhaustive_claims() -> None:
    assert "const SMART_FOLDER_DEFINITIONS = Object.freeze([]);" in BOARD
    for retired in (
        "smart-images",
        "Изображения и исходники",
        "smart-videos",
    ):
        assert retired not in BOARD
    assert 'partial: source?._meta?.has_more === true' in BOARD
    assert 'normalizedBoard.partial ? "загружено" : "объектов"' in BOARD
    assert "authoritative: Boolean(folder.systemRole)" in BOARD
