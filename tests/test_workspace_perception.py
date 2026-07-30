from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-perception.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-perception.css").read_text(encoding="utf-8")


def test_perception_assets_load_after_spatial_motion_and_productivity() -> None:
    assert './workspace-perception.css?v=20260730.1' in INDEX
    assert './workspace-perception.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-spatial-motion-polish.css") < INDEX.index("./workspace-perception.css")
    assert INDEX.index("./workspace-spatial-close.js") < INDEX.index("./workspace-perception.js")


def test_perception_pass_is_progressive_and_backend_free() -> None:
    for marker in (
        'const PERCEPTION_DENSITY_KEY = "contentengine.perception.density.v1"',
        'const PERCEPTION_COACH_KEY = "contentengine.perception.coach.v1"',
        'new MutationObserver(scheduleDecorate)',
        'document.documentElement.classList.toggle("workspace-perception-ready", ready)',
        'requestAnimationFrame(decorate)',
    ):
        assert marker in SCRIPT

    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT


def test_perception_has_one_next_action_and_semantic_mission_control() -> None:
    for marker in (
        "workspace-perception-now",
        "data-perception-open-task",
        "data-perception-open-context",
        "workspace-semantic-preview",
        "semanticPreviewMarkup",
        "decorateMissionControlPreviews",
        "readProductivityMemory",
    ):
        assert marker in SCRIPT or marker in CSS


def test_perception_replaces_unicode_controls_with_one_svg_system() -> None:
    for marker in (
        "const ICON_PATHS",
        "workspace-system-icon",
        "setIconContainer",
        "setIconOnlyButton",
        '[data-deck-action="overview"] .workspace-deck-action__icon',
        ".workspace-task-quick-action[data-productivity-pin]",
        ".workspace-context-button--icon[data-productivity-copy]",
    ):
        assert marker in SCRIPT or marker in CSS


def test_perception_has_density_autohide_and_workspace_geometry() -> None:
    for marker in (
        'dataset.workspaceDensity = next',
        "DENSITY_ORDER",
        "workspace-dock-autohidden",
        "workspace-dock-peek",
        "updateDockProximity",
        "body.workspace-context-open .workspace-shell > .workspace-main",
        'html[data-workspace-density="calm"]',
        'html[data-workspace-density="dense"]',
    ):
        assert marker in SCRIPT or marker in CSS


def test_perception_has_truthful_states_without_reading_secret_values() -> None:
    for marker in (
        "data-perception-state",
        "workspace-state-glyph",
        "workspace-form-status",
        "Изменения в форме — отправьте, когда будете готовы",
        "Отправка запущена…",
        "SECRET_FIELD_PATTERN",
        '"password", "hidden", "submit", "button", "reset", "file"',
    ):
        assert marker in SCRIPT or marker in CSS

    assert "field.value" not in SCRIPT
    assert "FormData(" not in SCRIPT


def test_perception_shared_opening_and_first_run_coach_are_accessible() -> None:
    for marker in (
        "captureSharedSource",
        "animateSharedTarget",
        "target.animate",
        "workspace-perception-shared-opening",
        "workspace-perception-coach",
        'role="dialog"',
        "prefers-reduced-motion: reduce",
        "@media (max-width: 820px)",
    ):
        assert marker in SCRIPT or marker in CSS


def test_perception_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-perception.js")],
        check=True,
        capture_output=True,
        text=True,
    )
