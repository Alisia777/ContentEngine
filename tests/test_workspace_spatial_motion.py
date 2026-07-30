from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-spatial-motion.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-spatial-motion.css").read_text(encoding="utf-8")


def test_spatial_motion_assets_load_after_workspace_productivity() -> None:
    assert './workspace-spatial-motion.css?v=20260730.1' in INDEX
    assert './workspace-spatial-motion.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-task-productivity-responsive.css") < INDEX.index("./workspace-spatial-motion.css")
    assert INDEX.index("./workspace-task-productivity.js") < INDEX.index("./workspace-spatial-motion.js")


def test_spatial_navigation_uses_view_transitions_with_a_safe_fallback() -> None:
    for marker in (
        'const SPATIAL_SURFACE_NAME = "content-engine-space"',
        'typeof document.startViewTransition === "function"',
        "createRouteWaiter(target, previousSurface)",
        "workspace-view-transition-active",
        "fallbackExit(previousSurface, direction)",
        'document.dispatchEvent(new CustomEvent("contentengine:spatial-route-settled"',
    ):
        assert marker in SCRIPT

    for marker in (
        "::view-transition-old(content-engine-space)",
        "::view-transition-new(content-engine-space)",
        "spatial-space-new-forward",
        "spatial-space-new-backward",
        "spatial-fallback-enter-forward",
        "spatial-fallback-enter-backward",
    ):
        assert marker in CSS


def test_spatial_layer_supports_rubber_band_touch_and_trackpad_navigation() -> None:
    for marker in (
        'event.pointerType !== "touch"',
        "SWIPE_THRESHOLD_PX",
        "workspace-spatial-scrubbing",
        "workspace-spatial-snapback",
        "applyScrub(dx, target)",
        "event.altKey",
        "WHEEL_THRESHOLD_PX",
        "workspace-space-peek",
    ):
        assert marker in SCRIPT or marker in CSS


def test_dock_has_proximity_magnification_and_attention_feedback() -> None:
    for marker in (
        "DOCK_ITEM_SELECTOR",
        "updateDockMagnification",
        'item.style.setProperty("--dock-scale"',
        'item.style.setProperty("--dock-lift"',
        "workspace-dock-attention",
        "syncDockAttention",
    ):
        assert marker in SCRIPT

    for marker in (
        "var(--dock-scale, 1)",
        "var(--dock-lift, 0px)",
        "spatial-dock-enter",
        "spatial-dock-attention",
        "backdrop-filter: blur(30px)",
    ):
        assert marker in CSS


def test_mission_control_and_focus_have_depth_without_cloning_app_state() -> None:
    for marker in (
        "workspace-mission-control-open",
        "spatial-mission-window-in",
        "spatial-mission-card-in",
        "workspace-spatial-tilt",
        "spatial-focus-window-in",
        "spatial-sheet-in",
    ):
        assert marker in CSS or marker in SCRIPT

    assert "cloneNode" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "localStorage" not in SCRIPT


def test_spatial_motion_is_accessible_and_respects_system_preferences() -> None:
    for marker in (
        'const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)"',
        "reducedMotion.matches",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
        "@media (hover: none), (pointer: coarse)",
        "touch-action: pan-y",
    ):
        assert marker in SCRIPT or marker in CSS


def test_spatial_motion_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-spatial-motion.js")],
        check=True,
        capture_output=True,
        text=True,
    )
