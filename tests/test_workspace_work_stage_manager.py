from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
MY_WORK = (APP_DIR / "my-work-view.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-work-stage-manager.js").read_text(encoding="utf-8")
BRIDGE = (APP_DIR / "workspace-os-v3-native-bridge.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-work-stage-manager.css").read_text(encoding="utf-8")


def test_work_stage_assets_load_after_os_v3_core() -> None:
    assert './workspace-work-stage-manager.css?v=20260731.1' in INDEX
    assert './workspace-work-stage-manager.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-os-v3-core.css') < INDEX.index('./workspace-work-stage-manager.css')
    assert INDEX.index('./workspace-os-v3-native-bridge.js') < INDEX.index('./workspace-work-stage-manager.js')


def test_native_my_work_and_task_anchors_exist() -> None:
    for marker in (
        'my-work-page',
        'my-work-layout',
        'my-work-queue',
        'my-work-item',
        'data-work-item-action-required=',
        'data-work-item-blocker=',
    ):
        assert marker in MY_WORK
    for marker in (
        'task-list',
        'card task-card',
        'data-task-id=',
        'data-action="transition-task"',
    ):
        assert marker in APP


def test_my_work_is_recomposed_into_now_waiting_and_next() -> None:
    for marker in (
        'ContentEngine · Stage Manager',
        'data-work-stage-lane="now"',
        'data-work-stage-lane="waiting"',
        'data-work-stage-lane="next"',
        'СЕЙЧАС',
        'ЖДУ',
        'ДАЛЬШЕ',
        'workFacts',
        'dispatchSnapshot',
        'contentengine:os-v3-work-snapshot',
    ):
        assert marker in SCRIPT


def test_native_filters_load_more_and_notification_actions_are_preserved() -> None:
    for marker in (
        'data-action="toggle-work-notifications"',
        '#my-work-filter-form',
        'controlsBody.append(sidebar)',
        'controlsBody.append(filter)',
    ):
        assert marker in SCRIPT
    for marker in (
        'captureWorkExtras',
        'restoreWorkExtras',
        'work-stage-native-extras',
    ):
        assert marker in BRIDGE or marker in CSS


def test_tasks_are_one_task_per_desk_with_native_actions() -> None:
    for marker in (
        'ContentEngine · Tasks',
        'tasks-desk-shell',
        'tasks-desk-list',
        'tasks-desk-stage',
        'stage.append(card)',
        'selectTask',
        'data-tasks-desk-prev',
        'data-tasks-desk-next',
        'window.ContentEngineOSV3?.openHandoff',
        'window.ContentEngineOSV3?.openCapsule',
    ):
        assert marker in SCRIPT


def test_work_stage_does_not_replace_business_logic() -> None:
    assert 'cloneNode' not in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT
    assert 'data-action="transition-task"' not in SCRIPT


def test_work_stage_is_responsive_low_height_and_reduced_motion_safe() -> None:
    for marker in (
        'body.contentengine-work-stage-open .workspace-shell > .sidebar',
        'body.contentengine-tasks-desk-open .workspace-shell > .sidebar',
        '.work-stage-lanes',
        '.tasks-desk-card.task-card',
        '@media (max-width: 620px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_work_stage_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-work-stage-manager.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_work_stage_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
