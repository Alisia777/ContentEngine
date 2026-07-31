from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-academy-lab-v3.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-academy-lab-v3.css").read_text(encoding="utf-8")


def test_academy_lab_assets_load_after_academy_os_and_core() -> None:
    assert './workspace-academy-lab-v3.css?v=20260731.1' in INDEX
    assert './workspace-academy-lab-v3.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-academy-os-v2.css') < INDEX.index('./workspace-academy-lab-v3.css')
    assert INDEX.index('./workspace-os-v3-core-b.js') < INDEX.index('./workspace-academy-lab-v3.js')
    assert INDEX.index('./workspace-collaboration-v3.js') < INDEX.index('./workspace-academy-lab-v3.js')


def test_academy_lab_pairs_original_lesson_and_practice_nodes() -> None:
    for marker in (
        'Урок + безопасная практика',
        'academy-lab-theory',
        'academy-lab-practice',
        'interactive.forEach((node) => practice.append(node))',
        'explanation.forEach((node) => theory.append(node))',
        'enableSplit(shell, theory',
        'Открыть настоящий рабочий стол',
        'event.shiftKey',
        'event.key.toLowerCase() === "s"',
    ):
        assert marker in SCRIPT
    assert "cloneNode" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT


def test_academy_lab_keeps_safe_training_targets() -> None:
    for marker in (
        '#course-check',
        '.training-practical-card',
        '.training-platform-simulator',
        '[data-training-walkthrough]',
        '[data-training-course]',
        'publishing_funnel',
        '/workspace/placement',
        'video_quality',
        '/workspace/review',
    ):
        assert marker in SCRIPT


def test_academy_lab_is_responsive_and_reduced_motion_safe() -> None:
    for marker in (
        '.academy-lab-toolbar',
        '.academy-lab-shell',
        '.academy-lab-real-link',
        '.academy-lab-page.academy-lab-collapsed',
        '@media (max-width: 980px)',
        '@media (max-width: 720px)',
        '@media (max-height: 760px)',
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
