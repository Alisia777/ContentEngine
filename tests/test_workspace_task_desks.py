from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-task-desks.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-task-desks.css").read_text(encoding="utf-8")


def test_task_desktop_assets_load_between_workspace_and_drafts() -> None:
    assert './workspace-task-desks.css?v=20260730.1' in INDEX
    assert './workspace-task-desks.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-desks-v2.js") < INDEX.index("./workspace-task-desks.js")
    assert INDEX.index("./workspace-task-desks.js") < INDEX.index("./workspace-desk-drafts.js")


def test_each_focusable_task_behaves_like_a_navigable_desk() -> None:
    for marker in (
        'const TASK_DESK_SELECTOR = \'[data-workspace-focusable="true"]\'',
        "workspace-task-carousel",
        "data-task-desk-nav",
        "Задача",
        "switchTaskDesk(direction)",
        "surfaces[index + direction]",
        "openTaskDesk(target)",
    ):
        assert marker in SCRIPT


def test_task_carousel_uses_existing_focus_controls_without_api_or_cloning() -> None:
    for marker in (
        'surface?.querySelector(":scope > [data-workspace-focus-card]")',
        'current.querySelector("[data-workspace-focus-close]")',
        "button?.click()",
        "close?.click()",
    ):
        assert marker in SCRIPT

    assert "cloneNode" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT


def test_task_carousel_has_keyboard_and_responsive_states() -> None:
    assert 'event.altKey' in SCRIPT
    assert 'event.key === "ArrowLeft"' in SCRIPT
    assert 'event.key === "ArrowRight"' in SCRIPT
    for marker in (
        ".workspace-task-carousel",
        ".workspace-task-carousel__position",
        "@media (max-width: 720px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
    ):
        assert marker in CSS


def test_task_desktop_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-task-desks.js")],
        check=True,
        capture_output=True,
        text=True,
    )
