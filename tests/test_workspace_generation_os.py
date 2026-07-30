from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-generation-os.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-generation-os.css").read_text(encoding="utf-8")


def test_generation_os_assets_load_after_the_existing_desktop_layer() -> None:
    assert './workspace-generation-os.css?v=20260731.1' in INDEX
    assert './workspace-generation-os.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-desktop-os.css') < INDEX.index('./workspace-generation-os.css')
    assert INDEX.index('./workspace-desktop-os-polish.js') < INDEX.index('./workspace-generation-os.js')


def test_generation_os_anchors_match_the_native_generation_screen() -> None:
    for marker in (
        'id="mock-batch-form"',
        'generation-workspace-layout',
        'generation-launch-card',
        'generation-archive-card',
        'id="generation-submit"',
        'id="generation-archive-filter-form"',
    ):
        assert marker in APP


def test_generation_is_recomposed_into_real_spaces() -> None:
    for marker in (
        'const GENERATION_ROUTE = "/workspace/generation"',
        'data-generation-os-space="launch"',
        'data-generation-os-space="queue"',
        'data-generation-os-space="aliases"',
        'Новый запуск',
        'Очередь и архив',
        'Один шаг — один рабочий стол',
        'layout?.remove()',
        'q(\'[data-generation-os-space="launch"]\', workbench).append(launch)',
        'q(\'[data-generation-os-space="queue"]\', workbench).append(archive)',
    ):
        assert marker in SCRIPT


def test_generation_form_has_six_task_desks_and_keeps_native_nodes() -> None:
    for marker in (
        'Режим и бюджет',
        'Точный товар',
        'Площадка и команда',
        'Замысел',
        'Исходники',
        'Проверка и запуск',
        'groups.get(currentKey)',
        '.append(node)',
        'panel.inert = !active',
        'reportValidity',
        'data-generation-step-prev',
        'data-generation-step-next',
    ):
        assert marker in SCRIPT
    assert "cloneNode" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT


def test_generation_archive_keeps_native_filtering_and_adds_fast_attention() -> None:
    for marker in (
        'data-generation-queue-status="active"',
        'data-generation-queue-status="ready"',
        'data-generation-queue-status="issue"',
        'select[name="status"]',
        'filter.requestSubmit',
    ):
        assert marker in SCRIPT


def test_generation_geometry_is_full_screen_responsive_and_accessible() -> None:
    for marker in (
        'body.contentengine-generation-os-open .workspace-shell > .sidebar',
        '.generation-os-workbench',
        '.generation-os-form-body',
        '.generation-os-step-dock',
        '.generation-os-panel.is-active',
        '@media (max-width: 820px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
        'animation-duration: 0.01ms !important',
    ):
        assert marker in CSS


def test_generation_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-generation-os.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_generation_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
