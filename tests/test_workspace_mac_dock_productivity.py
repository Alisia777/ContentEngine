from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-mac-dock-productivity.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-mac-dock-productivity.css").read_text(encoding="utf-8")


def test_productivity_assets_load_with_the_application_dock() -> None:
    assert './workspace-mac-dock-productivity.css?v=20260730.1' in INDEX
    assert './workspace-mac-dock-productivity.js?v=20260730.1' in INDEX
    assert INDEX.index('./workspace-desktop-os.css') < INDEX.index('./workspace-mac-dock-productivity.css')
    assert INDEX.index('./workspace-desktop-os.js') < INDEX.index('./workspace-mac-dock-productivity.js')


def test_old_task_bar_is_replaced_by_route_badges() -> None:
    assert 'body.ce-os-dock-visible .workspace-task-dock' in CSS
    assert 'display: none !important' in CSS
    for marker in (
        'contentengine.workspace-productivity.v1',
        'data-ce-dock-route',
        'ce-mac-dock__badge',
        'active',
        'waiting',
        'return',
        'blocked',
    ):
        assert marker in SCRIPT or marker in CSS


def test_badges_read_only_the_existing_tab_scoped_registry() -> None:
    assert 'window.sessionStorage' in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT
    assert 'localStorage' not in SCRIPT
    assert 'cloneNode' not in SCRIPT
    assert 'new FormData' not in SCRIPT
    assert 'input.value' not in SCRIPT
    assert 'textarea.value' not in SCRIPT


def test_productivity_badges_have_reduced_motion_fallback() -> None:
    assert '@media (prefers-reduced-motion: reduce)' in CSS
    assert 'animation: none !important' in CSS
    assert '@keyframes ce-mac-dock-return' in CSS


def test_productivity_javascript_parses_when_node_is_available() -> None:
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is not installed in this test environment')
    subprocess.run(
        [node, '--check', str(APP_DIR / 'workspace-mac-dock-productivity.js')],
        check=True,
        capture_output=True,
        text=True,
    )


def test_productivity_css_is_balanced() -> None:
    assert CSS.count('{') == CSS.count('}')
