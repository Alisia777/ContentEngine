from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-spatial-close.js").read_text(encoding="utf-8")
POLISH = (APP_DIR / "workspace-spatial-motion-polish.css").read_text(encoding="utf-8")


def test_spatial_close_controller_loads_after_the_main_motion_layer() -> None:
    assert './workspace-spatial-close.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-spatial-motion.js") < INDEX.index("./workspace-spatial-close.js")


def test_spatial_close_covers_all_workspace_window_types() -> None:
    for marker in (
        "[data-overview-close]",
        "[data-workspace-focus-close]",
        "[data-productivity-context-close]",
        "[data-productivity-park-close]",
        "workspace-spatial-closing",
        "event.isTrusted",
        "event.stopImmediatePropagation()",
    ):
        assert marker in SCRIPT

    for marker in (
        "spatial-mission-window-close",
        "spatial-focus-window-close",
        "spatial-sheet-close",
        "spatial-dialog-close",
        "spatial-overlay-close",
    ):
        assert marker in POLISH


def test_spatial_close_is_progressive_and_never_touches_backend_state() -> None:
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "sessionStorage" not in SCRIPT
    assert "localStorage" not in SCRIPT
    assert "cloneNode" not in SCRIPT
    assert "REDUCED_MOTION.matches" in SCRIPT


def test_spatial_close_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-spatial-close.js")],
        check=True,
        capture_output=True,
        text=True,
    )
