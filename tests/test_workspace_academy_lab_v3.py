from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
ACADEMY_V2 = (APP_DIR / "workspace-academy-os-v2.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-academy-lab-v3.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-academy-lab-v3.css").read_text(encoding="utf-8")


def test_academy_lab_assets_load_after_academy_os_v2() -> None:
    assert './workspace-academy-lab-v3.css?v=20260731.1' in INDEX
    assert './workspace-academy-lab-v3.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-academy-os-v2.css') < INDEX.index('./workspace-academy-lab-v3.css')
    assert INDEX.index('./workspace-academy-os-v2.js') < INDEX.index('./workspace-academy-lab-v3.js')


def test_academy_v2_exposes_original_lesson_and_practice_spaces() -> None:
    for marker in (
        'academy-v2-panel',
        'data-course-lesson',
        'Практика и аттестация',
        'group.nodes.filter(Boolean).forEach((node) => panel.append(node))',
    ):
        assert marker in ACADEMY_V2


def test_lab_places_explanation_and_practice_side_by_side() -> None:
    for marker in (
        'Academy Lab v3',
        'academy-lab-open-button',
        'ACADEMY LAB',
        'ОБЪЯСНЕНИЕ',
        'ПРАКТИКА',
        'candidateSimulator',
        'candidateLesson',
        'data-academy-lab-lesson',
        'data-academy-lab-practice',
        'academy-lab-ratio',
    ):
        assert marker in SCRIPT or marker in CSS


def test_lab_moves_native_dom_and_restores_it() -> None:
    for marker in (
        'moveNode',
        'placeholder = document.createComment',
        'target.append(node)',
        'restoreNodes',
        'placeholder.before(node)',
        'closeLab',
    ):
        assert marker in SCRIPT
    assert 'cloneNode' not in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT


def test_lab_has_safe_fallback_and_handoff() -> None:
    for marker in (
        'БЕЗОПАСНАЯ ЛАБОРАТОРИЯ',
        'боевые API вызываются только штатными кнопками',
        'data-academy-lab-open-practice',
        'window.ContentEngineOSV3?.openHandoff',
    ):
        assert marker in SCRIPT


def test_lab_is_responsive_low_height_and_reduced_motion_safe() -> None:
    for marker in (
        '.academy-lab-body',
        '@media (max-width: 900px)',
        '@media (max-width: 620px)',
        '@media (max-height: 720px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_academy_lab_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-academy-lab-v3.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_academy_lab_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
