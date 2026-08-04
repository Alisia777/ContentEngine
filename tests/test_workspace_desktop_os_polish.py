from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-desktop-os-polish.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-desktop-os-polish.css").read_text(encoding="utf-8")


def test_legacy_desktop_polish_is_not_an_active_runtime_layer() -> None:
    active_assets = re.findall(
        r'^\s*<(?:link|script)\b[^>]*\b(?:href|src)="([^"]+)"',
        INDEX,
        flags=re.MULTILINE,
    )
    assert not any("workspace-desktop-os-polish" in asset for asset in active_assets)
    assert "./workspace-os-v4.css?v=20260804.os4.8" in active_assets
    assert "./workspace-os-v4-loader.js?v=20260804.os4.8" in active_assets
    assert active_assets.index("./workspace-os-v4-loader.js?v=20260804.os4.8") < active_assets.index(
        "./workspace-build-guard.js?v=20260804.os4.8"
    )


def test_mobile_mode_switch_no_longer_overlaps_the_step_dock() -> None:
    for marker in (
        'grid-template-rows: auto auto',
        'grid-column: 1 / -1',
        'position: static',
        'height: calc(100dvh - 208px)',
        '@media (max-width: 640px)',
    ):
        assert marker in CSS


def test_active_window_title_tracks_the_visible_review_panel() -> None:
    for marker in (
        'syncReviewTitle',
        'data-review-os-current-title',
        'data-review-os-space',
        '[data-ce-os-panel].is-active',
        'История проверок',
        'MutationObserver',
    ):
        assert marker in SCRIPT


def test_polish_does_not_touch_backend_or_form_values() -> None:
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT
    assert '.value' not in SCRIPT
    assert 'cloneNode' not in SCRIPT


def test_polish_javascript_parses_when_node_is_available() -> None:
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is not installed in this test environment')
    subprocess.run(
        [node, '--check', str(APP_DIR / 'workspace-desktop-os-polish.js')],
        check=True,
        capture_output=True,
        text=True,
    )


def test_polish_css_is_balanced() -> None:
    assert CSS.count('{') == CSS.count('}')
