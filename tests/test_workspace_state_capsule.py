from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-state-capsule.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-state-capsule.css").read_text(encoding="utf-8")


def test_state_capsule_assets_load_after_drafts_and_before_productivity() -> None:
    assert './workspace-state-capsule.css?v=20260730.1' in INDEX
    assert './workspace-state-capsule.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-desk-drafts.css") < INDEX.index("./workspace-state-capsule.css")
    assert INDEX.index("./workspace-state-capsule.css") < INDEX.index("./workspace-task-productivity.css")
    assert INDEX.index("./workspace-desk-drafts.js") < INDEX.index("./workspace-state-capsule.js")
    assert INDEX.index("./workspace-state-capsule.js") < INDEX.index("./workspace-task-productivity.js")


def test_capsules_restore_navigation_context_not_form_content() -> None:
    for marker in (
        'const CAPSULE_STORAGE_KEY = "contentengine.workspace-capsules.v1"',
        "details",
        "scrolls",
        "videos",
        "selectedTab(root)",
        "restoreVideo(video, saved)",
        "elementFromCapsuleLocator",
        "contentengine:capsule-restored",
    ):
        assert marker in SCRIPT

    assert "field.value" not in SCRIPT
    assert "FormData" not in SCRIPT
    assert "input.files" not in SCRIPT
    assert "FileReader" not in SCRIPT


def test_capsules_are_tab_scoped_bounded_and_debounced() -> None:
    for marker in (
        "window.sessionStorage",
        "CAPSULE_MAX_AGE_MS",
        "scheduleCapsuleCapture",
        "window.setTimeout(() => captureCapsule",
        "scheduleCapsulePersist",
        "capsuleSaveTimer",
    ):
        assert marker in SCRIPT

    assert "localStorage" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT


def test_capsules_restore_expanded_sections_inner_scroll_and_video_position_safely() -> None:
    for marker in (
        'root.querySelectorAll("details")',
        "container.scrollTo",
        'video.addEventListener("loadedmetadata"',
        "video.currentTime = Math.min",
        "video.volume",
        "video.muted",
    ):
        assert marker in SCRIPT

    assert "video.play(" not in SCRIPT


def test_capsule_indicator_is_compact_responsive_and_accessible() -> None:
    for marker in (
        ".workspace-capsule-indicator",
        "Контекст сохранён ·",
        "@media (max-width: 820px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
    ):
        assert marker in SCRIPT or marker in CSS


def test_state_capsule_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-state-capsule.js")],
        check=True,
        capture_output=True,
        text=True,
    )
