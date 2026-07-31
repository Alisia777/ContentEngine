from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-publishing-os.js").read_text(encoding="utf-8")
BRIDGE = (APP_DIR / "workspace-os-v3-native-bridge.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-publishing-os.css").read_text(encoding="utf-8")


def test_publishing_assets_load_inside_os_v3() -> None:
    assert './workspace-publishing-os.css?v=20260731.1' in INDEX
    assert './workspace-publishing-os.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-os-v3-core.css') < INDEX.index('./workspace-publishing-os.css')
    assert INDEX.index('./workspace-os-v3-native-bridge.js') < INDEX.index('./workspace-publishing-os.js')


def test_native_placement_anchors_exist() -> None:
    for marker in (
        'class="placement-list"',
        'class="card placement-card"',
        'class="placement-top"',
        'class="tracking-link-form',
        'class="placement-form',
        'data-placement-id=',
    ):
        assert marker in APP


def test_one_publication_becomes_one_spatial_workflow() -> None:
    for marker in (
        'const PUBLISHING_ROUTES',
        'publishing-os-shell',
        'Очередь площадок',
        'Один пост — один маршрут',
        'Задание',
        'Ссылка',
        'Проверка',
        'Подтверждение',
        'publishing-os-step-dock',
        'setCardStep',
        'validatePanel',
        'Alt',
    ):
        assert marker in SCRIPT or marker in CSS


def test_native_forms_are_moved_not_recreated_and_no_api_is_called() -> None:
    for marker in (
        'panel.append(node)',
        'panelHost.append(card)',
        'list.remove()',
        'invalid.reportValidity',
    ):
        assert marker in SCRIPT
    assert 'cloneNode' not in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT


def test_filters_preview_and_sidebar_repair_are_present() -> None:
    for marker in (
        'data-publishing-filter="active"',
        'data-publishing-filter="completed"',
        'data-publishing-filter="all"',
        'publishing-os-device',
        'publishingFilterHidden',
        'repairPublishingSidebar',
    ):
        assert marker in SCRIPT or marker in BRIDGE or marker in CSS


def test_publishing_is_full_screen_responsive_and_reduced_motion_safe() -> None:
    for marker in (
        'body.contentengine-publishing-os-open .workspace-shell > .sidebar',
        '.publishing-os-shell',
        '.publishing-os-step-panel.is-active',
        '@media (max-width: 620px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_publishing_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-publishing-os.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_publishing_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
