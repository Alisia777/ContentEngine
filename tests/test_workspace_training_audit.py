from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]

APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web/app/catalog.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
WORKSPACE_VIEW = (ROOT / "web/app/workspace-board-view.js").read_text(encoding="utf-8")
WORKSPACE_STYLES = (ROOT / "web/app/workspace-board.css").read_text(encoding="utf-8")
TRAINING_VIEW = (ROOT / "web/app/training-interactive.js").read_text(encoding="utf-8")
TRAINING_STYLES = (ROOT / "web/app/training-interactive.css").read_text(
    encoding="utf-8"
)
WORKSPACE_SQL = (
    ROOT / "supabase/migrations/202607160001_workspace_folders.sql"
).read_text(encoding="utf-8")
TRAINING_SQL = (
    ROOT / "supabase/migrations/202607160002_training_interactive_walkthroughs.sql"
).read_text(encoding="utf-8")
AUDIT = (ROOT / "docs/PORTAL_WORKSPACE_TRAINING_AUDIT.md").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_workspace_release_floor_is_wired_end_to_end() -> None:
    assert '["board", "Рабочий стол"' in CATALOG
    assert 'from "./workspace-board-view.js?' in APP
    assert "workspaceBoardMarkup(board" in APP
    assert 'section === "board"' in APP
    assert "state.api.workspaceBrowser(" in APP

    required_actions = (
        "select-workspace-folder",
        "open-workspace-item",
        "close-workspace-item",
        "move-workspace-item",
        "archive-workspace-folder",
        "reset-workspace-filters",
        "show-more-workspace-items",
    )
    for action in required_actions:
        assert f'data-action="{action}"' in WORKSPACE_VIEW
        assert f'action === "{action}"' in APP

    for form_id in (
        "workspace-folder-create-form",
        "workspace-folder-edit-form",
        "workspace-board-filter-form",
    ):
        assert f'id="{form_id}"' in WORKSPACE_VIEW
        assert f'form.id === "{form_id}"' in APP

    assert 'document.addEventListener("dragstart", handleDragStart)' in APP
    assert 'document.addEventListener("drop", handleDrop)' in APP
    assert 'document.addEventListener("dragend", handleDragEnd)' in APP
    assert "data-workspace-drop-folder" in WORKSPACE_VIEW
    assert "data-workspace-drag-item" in WORKSPACE_VIEW
    assert 'draggable="${busy ? "false" : "true"}"' in WORKSPACE_VIEW
    assert "await state.api.moveWorkspaceItems(" in APP
    assert 'options.folder_id = null' in APP
    assert 'hasOwnProperty.call(options, "folder_id")' in API
    assert "payload.folder_id = folderId && folderId !== \"root\"" in API
    assert "capabilities.manageFolders" in WORKSPACE_VIEW
    assert "rawCapabilities.manage_folders === true" in WORKSPACE_VIEW
    assert "rawCapabilities.move_items === true" in WORKSPACE_VIEW
    assert "Создавать, переименовывать и архивировать папки может руководитель" in WORKSPACE_VIEW
    assert "workspaceBoardQuerySignature()" in APP
    assert "WORKSPACE_BOARD_MEMORY_CAP = 300" in APP
    assert "visibleItemLimit" in WORKSPACE_VIEW
    assert "sectionRequestId === state.sections.board.requestId" in APP
    assert "querySignature === workspaceBoardQuerySignature()" in APP
    assert "OPERATIONAL_WORKSPACE_ROLES.has(role)" in APP
    assert "Экзамен сдан — рабочую роль назначает руководитель" in APP
    assert "Роль назначает руководитель" in APP
    assert "учебная смена остаётся дополнительной тренировкой" in APP

    # Drag-and-drop must not be the only interaction model.
    assert "доступная замена drag-and-drop" in WORKSPACE_VIEW.lower()
    assert WORKSPACE_VIEW.count('data-action="move-workspace-item"') >= 1
    assert 'event.key === "Escape"' in APP


def test_workspace_persistence_security_and_scaling_primitives_are_server_owned() -> (
    None
):
    for rpc in (
        "creator_workspace_browser",
        "creator_create_workspace_folder",
        "creator_update_workspace_folder",
        "creator_move_workspace_items",
    ):
        assert f'"{rpc}"' in API
        assert f"function public.{rpc}(" in WORKSPACE_SQL
        assert f"revoke all on function public.{rpc}(jsonb)" in WORKSPACE_SQL
        assert f"grant execute on function public.{rpc}(jsonb)" in WORKSPACE_SQL

    for table in (
        "workspace_folders",
        "workspace_media_locations",
        "workspace_task_locations",
    ):
        assert f"create table if not exists content_factory.{table}" in WORKSPACE_SQL
        assert (
            f"alter table content_factory.{table} enable row level security"
            in WORKSPACE_SQL
        )
        assert f"revoke all on content_factory.{table}" in WORKSPACE_SQL

    assert WORKSPACE_SQL.count("security definer") >= 7
    assert WORKSPACE_SQL.count("set search_path = ''") >= 7
    assert WORKSPACE_SQL.count("begin_command(") >= 3
    assert WORKSPACE_SQL.count("finish_command(") >= 3
    assert WORKSPACE_SQL.count("emit_event(") >= 3
    assert "pg_advisory_xact_lock" in WORKSPACE_SQL
    assert "for update of location" in WORKSPACE_SQL.lower()
    assert "workspace_folder_version_conflict" in WORKSPACE_SQL
    assert "workspace_folder_depth_exceeded" in WORKSPACE_SQL
    assert "workspace_folder_not_empty" in WORKSPACE_SQL
    assert "workspace_item_access_denied" in WORKSPACE_SQL
    assert "or media.id::text ilike" in WORKSPACE_SQL
    assert "or task.id::text ilike" in WORKSPACE_SQL
    assert "product.current_wb_article" in WORKSPACE_SQL

    assert "limit page_size + 1" in WORKSPACE_SQL
    assert "'cap', 100" in WORKSPACE_SQL
    assert "workspace_media_locations_folder_idx" in WORKSPACE_SQL
    assert "workspace_task_locations_folder_idx" in WORKSPACE_SQL
    assert "active_folder_count >= 500" in WORKSPACE_SQL
    assert "total_folder_count >= 5000" in WORKSPACE_SQL

    # Moving an object is logical organization, never a Storage rename.
    assert "update content_factory.media_objects" not in WORKSPACE_SQL.lower()
    assert "set object_name" not in WORKSPACE_SQL.lower()


def test_training_interactive_release_floor_is_present_and_non_blocking() -> None:
    assert 'from "./training-interactive.js?' in APP
    assert "trainingInteractiveMarkup(course.code" in APP
    assert "restoreTrainingWalkthroughState(course.code)" in APP
    assert "window.sessionStorage.setItem" in APP
    assert "stopAllTrainingWalkthroughs()" in APP

    for export_name in (
        "normalizeInteractiveWalkthroughs",
        "trainingInteractiveMarkup",
        "setTrainingWalkthroughStep",
        "stopTrainingWalkthrough",
        "trainingWalkthroughStorageKey",
    ):
        assert f"export function {export_name}(" in TRAINING_VIEW

    assert TRAINING_SQL.count('"video_url":') == 8
    assert TRAINING_SQL.count('"poster_url":') == 8
    for course_code in (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    ):
        assert f"'{course_code}'" in TRAINING_SQL

    assert 'data-action="training-walkthrough-play"' in TRAINING_VIEW
    assert 'data-action="training-walkthrough-previous"' in TRAINING_VIEW
    assert 'data-action="training-walkthrough-next"' in TRAINING_VIEW
    assert 'data-action="training-walkthrough-reset"' in TRAINING_VIEW
    assert 'role="progressbar"' in TRAINING_VIEW
    assert 'aria-live="polite"' in TRAINING_VIEW
    assert "<details" in TRAINING_VIEW and "<summary>" in TRAINING_VIEW
    assert "data-training-check" in TRAINING_VIEW
    assert "<iframe" not in TRAINING_VIEW
    assert " autoplay" not in TRAINING_VIEW.lower()
    assert 'controls preload="none" playsinline' in TRAINING_VIEW
    assert 'aria-label="Учебное видео:' in TRAINING_VIEW
    assert 'kind="captions"' in TRAINING_VIEW
    assert "!web/app/assets/training/*.mp4" in GITIGNORE
    assert (ROOT / "web/app/assets/training/ugc_bloody_peel_8s.mp4").stat().st_size > 1_000_000
    assert (ROOT / "web/app/assets/training/ugc_bombbar_pro_8s.mp4").stat().st_size > 1_000_000

    # The walkthrough content must not weaken the server-side course gate.
    forbidden_gate_changes = (
        "training_answer_keys",
        "training_certifications",
        "creator_complete_module",
        "creator_submit_course_check",
        "grant execute",
    )
    lowered = TRAINING_SQL.lower()
    for token in forbidden_gate_changes:
        assert token not in lowered


def test_mobile_accessibility_and_browser_security_floor_is_explicit() -> None:
    for styles in (WORKSPACE_STYLES, TRAINING_STYLES):
        assert "min-height: 44px" in styles
        assert ":focus-visible" in styles
        assert "@media (prefers-reduced-motion: reduce)" in styles
        assert "@media (forced-colors: active)" in styles
    assert "--ti-on-primary: var(--portal-action-ink, #ffffff)" in TRAINING_STYLES
    assert TRAINING_STYLES.count("color: var(--ti-on-primary)") >= 4

    for breakpoint in ("1320px", "900px", "680px", "420px"):
        assert breakpoint in WORKSPACE_STYLES

    assert 'aria-busy="' in WORKSPACE_VIEW
    assert 'role="alert"' in WORKSPACE_VIEW
    assert 'aria-current="page"' in WORKSPACE_VIEW
    assert 'role="status"' in WORKSPACE_VIEW
    assert 'aria-controls="workspace-board-item-drawer"' in WORKSPACE_VIEW

    csp_match = re.search(
        r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"',
        INDEX,
    )
    assert csp_match
    csp = csp_match.group(1)
    assert "object-src 'none'" in csp
    assert "frame-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "media-src 'self' blob: https://*.supabase.co" in csp


def test_audit_keeps_open_release_risks_visible() -> None:
    required_risks = (
        "P1-WS-01",
        "P1-WS-02",
        "P1-TR-01",
        "P2-PERF-01",
    )
    for risk in required_risks:
        assert risk in AUDIT

    assert "supabase test db" in AUDIT
    assert "axe/Lighthouse" in AUDIT
    assert "100 000" in AUDIT
    assert "Gate A" in AUDIT
    assert "Gate B" in AUDIT
    assert "Gate C" in AUDIT
