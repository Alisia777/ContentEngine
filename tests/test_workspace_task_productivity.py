from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-task-productivity-core.js").read_text(encoding="utf-8")
PANEL = (APP_DIR / "workspace-task-productivity-panel.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-task-productivity.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-task-productivity.css").read_text(encoding="utf-8")
PANEL_CSS = (APP_DIR / "workspace-task-productivity-panel.css").read_text(encoding="utf-8")
RESPONSIVE_CSS = (APP_DIR / "workspace-task-productivity-responsive.css").read_text(encoding="utf-8")


def test_productivity_assets_load_after_existing_workspace_memory_layers() -> None:
    for marker in (
        './workspace-task-productivity.css?v=20260730.1',
        './workspace-task-productivity-panel.css?v=20260730.1',
        './workspace-task-productivity-responsive.css?v=20260730.1',
        './workspace-task-productivity.js?v=20260730.1',
    ):
        assert marker in INDEX
    assert INDEX.index("./workspace-desk-drafts.css") < INDEX.index("./workspace-task-productivity.css")
    assert INDEX.index("./workspace-desk-drafts.js") < INDEX.index("./workspace-task-productivity.js")
    assert 'from "./workspace-task-productivity-core.js?v=20260826.rebuild-clean.39"' in SCRIPT
    assert 'from "./workspace-task-productivity-panel.js?v=20260826.rebuild-clean.39"' in SCRIPT


def test_task_productivity_is_progressive_and_has_no_backend_side_effects() -> None:
    for marker in (
        'export const PRODUCTIVITY_STORAGE_KEY = "contentengine.workspace-productivity.v1"',
        'export const PRODUCTIVITY_WIP_LIMIT = 3',
        'new MutationObserver(scheduleMount)',
        'shell.classList.add("workspace-productivity-enabled")',
        'function sessionStore()',
    ):
        assert marker in CORE or marker in SCRIPT

    combined = CORE + PANEL + SCRIPT
    assert "fetch(" not in combined
    assert "XMLHttpRequest" not in combined
    assert ".api." not in combined
    assert "localStorage" not in combined


def test_active_task_dock_and_mission_control_show_real_task_attention() -> None:
    for marker in (
        "workspace-task-dock",
        "Активные задачи",
        "data-productivity-open-overview",
        "data-productivity-waiting",
        "workspace-overview__section--productivity",
        "Оперативное внимание",
        "workspace-overview-route-count",
        "workspace-overview-task-state",
    ):
        assert marker in SCRIPT or marker in CSS or marker in RESPONSIVE_CSS


def test_tasks_can_be_pinned_parked_and_returned_without_disappearing() -> None:
    for marker in (
        "export function pinTask(task",
        "export function openParkDialog(key)",
        "export function unparkTask(task)",
        "Жду ответ",
        "Жду файл",
        "Жду генерацию",
        "Нужна правка другого сотрудника",
        "Вернуться позже",
        "returnAt",
        "isParkedDue(task)",
    ):
        assert marker in CORE or marker in PANEL


def test_context_shelf_keeps_one_task_and_one_next_action_visible() -> None:
    for marker in (
        "workspace-context-panel",
        "Контекст задачи",
        "Готово, когда",
        "Что нельзя потерять",
        "Только в этой вкладке",
        "Локальная история",
        "data-productivity-note",
        "data-productivity-copy",
    ):
        assert marker in PANEL or marker in PANEL_CSS


def test_task_opening_reuses_existing_focus_surface_and_supports_deep_links() -> None:
    for marker in (
        'q(":scope > [data-workspace-focus-card]", surface)',
        "button.click()",
        "deskTask",
        "PRODUCTIVITY_PENDING_KEY",
        "surfaceByKey",
        "window.location.hash = task.route",
    ):
        assert marker in CORE or marker in PANEL or marker in SCRIPT

    assert "cloneNode" not in CORE + PANEL + SCRIPT


def test_productivity_respects_secret_boundaries_and_does_not_persist_material_urls() -> None:
    assert "sessionStorage" in CORE
    assert "export function liveLinks(surface)" in CORE
    assert "/token|signature|expires|apikey/i" in CORE
    assert "FileReader" not in CORE + PANEL + SCRIPT


def test_registry_updates_are_idempotent_and_do_not_create_observer_loops() -> None:
    assert 'updatedAt: changed ? Date.now() : Number(existing?.updatedAt || Date.now())' in CORE
    assert "actions.dataset.productivitySignature === signature" in SCRIPT
    assert "dock.dataset.productivitySignature === signature" in SCRIPT
    assert "section.dataset.productivitySignature !== signature" in SCRIPT


def test_productivity_interface_is_large_responsive_and_reduced_motion_safe() -> None:
    combined_css = CSS + PANEL_CSS + RESPONSIVE_CSS
    for marker in (
        ".workspace-task-dock",
        ".workspace-context-panel",
        ".workspace-park-dialog",
        "@media (max-width: 820px)",
        "@media (max-width: 520px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
        "--task-productivity-panel-width",
    ):
        assert marker in combined_css


@pytest.mark.parametrize(
    "filename",
    [
        "workspace-task-productivity-core.js",
        "workspace-task-productivity-panel.js",
        "workspace-task-productivity.js",
    ],
)
def test_productivity_javascript_parses_when_node_is_available(filename: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / filename)],
        check=True,
        capture_output=True,
        text=True,
    )
