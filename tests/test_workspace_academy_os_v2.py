from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
STARTUP_ROUTE = (APP_DIR / "startup-route.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-academy-os-v2.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-academy-os-v2.css").read_text(encoding="utf-8")


def test_academy_is_a_separate_gate_not_a_workspace_shell_layer() -> None:
    active_assets = re.findall(
        r'^\s*<(?:link|script)\b[^>]*\b(?:href|src)="([^"]+)"',
        INDEX,
        flags=re.MULTILINE,
    )
    assert not any("workspace-academy-" in asset for asset in active_assets)
    assert 'return route.startsWith("/workspace/");' in LOADER
    assert 'hash.replace(/^#\\/academy/u, "#/learn")' in STARTUP_ROUTE
    assert '"/learn"' not in LOADER


def test_course_keeps_overview_lessons_practice_and_completion() -> None:
    for marker in (
        'collectCourseGroups',
        'directOverview',
        'beforeLessons',
        'afterLessons',
        'course-completion-card',
        'data-course-lesson',
        'Практика и аттестация',
        'academy-v2-panel--overview',
        'academy-v2-panel--practice',
    ):
        assert marker in SCRIPT or marker in CSS


def test_original_course_dom_remains_authoritative() -> None:
    assert 'cloneNode' not in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT
    assert 'group.nodes.filter(Boolean).forEach((node) => panel.append(node))' in SCRIPT
    assert 'panel.inert = !active' in SCRIPT


def test_course_navigation_tracks_native_lesson_controls() -> None:
    for marker in (
        'training-lesson-open',
        'training-lesson-understood',
        'data-lesson-index',
        'data-target="course-check"',
        'setActive(lessonIndex + 1)',
    ):
        assert marker in SCRIPT


def test_academy_v2_has_accessible_motion_fallbacks() -> None:
    assert 'prefers-reduced-motion: reduce' in CSS
    assert 'REDUCED_MOTION' in SCRIPT
    assert 'aria-hidden' in SCRIPT
    assert 'aria-current' in SCRIPT
    assert 'animation-duration: 0.01ms !important' in CSS


def test_academy_v2_javascript_parses_when_node_is_available() -> None:
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is not installed in this test environment')
    subprocess.run(
        [node, '--check', str(APP_DIR / 'workspace-academy-os-v2.js')],
        check=True,
        capture_output=True,
        text=True,
    )


def test_academy_v2_css_is_balanced() -> None:
    assert CSS.count('{') == CSS.count('}')
    assert '.academy-course-os-window--v2' in CSS
    assert '.academy-v2-progress > span' in CSS
