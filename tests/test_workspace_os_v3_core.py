from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v3-core.js").read_text(encoding="utf-8")
BRIDGE = (APP_DIR / "workspace-os-v3-native-bridge.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-os-v3-core.css").read_text(encoding="utf-8")
FINISH = (APP_DIR / "workspace-os-v3-finish.css").read_text(encoding="utf-8")


def test_os_v3_assets_load_after_v2_and_before_build_guard() -> None:
    markers = (
        './workspace-os-v3-core.css?v=20260731.1',
        './workspace-os-v3-native-bridge.js?v=20260731.1',
        './workspace-os-v3-core.js?v=20260731.1',
        './workspace-os-v3-finish.css?v=20260731.1',
    )
    for marker in markers:
        assert marker in INDEX
    assert INDEX.index('./workspace-media-finder.css') < INDEX.index('./workspace-os-v3-core.css')
    assert INDEX.index('./workspace-os-v3-finish.css') < INDEX.index('./workspace-build-guard.css')
    assert INDEX.index('./workspace-media-finder.js') < INDEX.index('./workspace-os-v3-core.js')
    assert INDEX.index('./workspace-academy-lab-v3.js') < INDEX.index('./workspace-build-guard.js')


def test_spotlight_is_a_real_command_palette() -> None:
    for marker in (
        'openSpotlight',
        'os-v3-command-palette',
        'Spotlight ContentEngine',
        'routeCommands()',
        'dynamicCommands()',
        'systemCommands()',
        'event.metaKey || event.ctrlKey',
        'openCapsule',
        'toggleSplitView',
        'Показать блокеры',
    ):
        assert marker in CORE


def test_product_capsule_split_handoff_and_frame_notes_are_present() -> None:
    for marker in (
        'РАБОЧАЯ КАПСУЛА',
        'capsuleRouteLinks',
        'SPLIT VIEW',
        'moveIntoSplit',
        'restoreSplitNodes',
        'ПЕРЕДАЧА КОНТЕКСТА',
        'insertIntoWorkField',
        'КОММЕНТАРИЙ К КАДРУ',
        'frameNoteKey',
        'pushUndo',
    ):
        assert marker in CORE


def test_core_excludes_secrets_and_does_not_touch_business_api() -> None:
    for marker in (
        'SECRET_PATTERN',
        '["password", "hidden", "file"]',
        'field instanceof HTMLInputElement',
        'server saves only via native form',
    ):
        assert marker in CORE or marker.lower() in CORE.lower()
    for script in (CORE, BRIDGE):
        assert 'fetch(' not in script
        assert 'XMLHttpRequest' not in script
        assert '.api.' not in script
        assert 'cloneNode' not in script


def test_presence_is_honest_same_browser_activity_not_fake_team_presence() -> None:
    for marker in (
        'BroadcastChannel',
        'contentengine-os-v3-presence',
        'Открыто в ${matching.length + 1} окнах',
        'Другие вкладки этого же браузера',
    ):
        assert marker in CORE
    assert 'online users' not in CORE.lower()
    assert 'supabase' not in CORE.lower()


def test_native_bridge_preserves_controls_and_repairs_publication_queue() -> None:
    for marker in (
        'captureWorkExtras',
        'restoreWorkExtras',
        'work-stage-native-extras',
        'repairPublishingSidebar',
        'publishingFilterHidden',
        'os-v3-route-badge',
    ):
        assert marker in BRIDGE or marker in FINISH


def test_os_v3_is_responsive_reduced_motion_safe_and_colour_disciplined() -> None:
    for marker in (
        '@media (max-width: 620px)',
        '@media (max-height: 720px)',
        '@media (prefers-reduced-motion: reduce)',
        'view-transition-name: ce-os-active-surface',
        '.badge-success',
        '.os-v3-route-badge',
        'content-visibility: auto',
    ):
        assert marker in CSS or marker in FINISH


def test_os_v3_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    for filename in (
        "workspace-os-v3-core.js",
        "workspace-os-v3-native-bridge.js",
    ):
        subprocess.run(
            [node, "--check", str(APP_DIR / filename)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_os_v3_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
    assert FINISH.count("{") == FINISH.count("}")
