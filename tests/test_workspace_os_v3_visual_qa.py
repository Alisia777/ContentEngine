from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-os-v3-visual-qa.js").read_text(encoding="utf-8")
ZEN = (APP_DIR / "workspace-os-v3-zen-control.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-os-v3-visual-qa.css").read_text(encoding="utf-8")


def test_os_v3_visual_qa_assets_are_retired_from_the_active_graph() -> None:
    active_assets = re.findall(
        r'^\s*<(?:link|script)\b[^>]*\b(?:href|src)="([^"]+)"',
        INDEX,
        flags=re.MULTILINE,
    )
    retired_names = (
        "workspace-os-v3-visual-qa.css",
        "workspace-os-v3-visual-qa.js",
        "workspace-os-v3-zen-control.js",
    )
    assert not any(any(name in asset for name in retired_names) for asset in active_assets)
    assert "./workspace-os-v4.css?v=20260812.os4.38" in active_assets
    assert active_assets.index("./workspace-os-v4-loader.js?v=20260812.os4.38.bad-context.1") < active_assets.index(
        "./workspace-build-guard.js?v=20260812.os4.38"
    )


def test_legacy_visual_layers_are_retained_as_contracts_but_not_executed() -> None:
    for marker in (
        '<!-- <script type="module" src="./workspace-desks-v2.js?v=20260730.2"></script> -->',
        '<!-- <script type="module" src="./workspace-task-productivity.js?v=20260730.1"></script> -->',
        '<!-- <script type="module" src="./workspace-perception.js?v=20260730.1"></script> -->',
        '<!-- <link rel="stylesheet" href="./workspace-desks.css?v=20260730.1" /> -->',
        '<!-- <link rel="stylesheet" href="./workspace-perception.css?v=20260730.1" /> -->',
    ):
        assert marker in INDEX


def test_one_screen_one_action_home_mission_and_zen_mode_exist() -> None:
    for marker in (
        'ОДИН ЭКРАН · ОДНО ДЕЙСТВИЕ',
        'os-clean-home__route',
        'openMission',
        'Рабочие столы',
        'openZen',
        'os-clean-zen-surface',
        'contentengine-os-clean-zen',
        'removeAttribute("data-workspace-focus-card")',
    ):
        assert marker in SCRIPT or marker in CSS
    for marker in (
        'Visible Zen Mode control',
        'data-os-clean-zen',
        'Фокус: развернуть рабочее пространство',
    ):
        assert marker in ZEN


def test_scalable_filters_folders_and_video_governor_exist() -> None:
    for marker in (
        'Найти задачу',
        'Поиск по реестру',
        'Без папки',
        'os-clean-media-kind',
        'enhanceReviewRisks',
        'Риск ${index + 1} из ${cards.length}',
        'video.autoplay = false',
        'video.loop = false',
        'IntersectionObserver',
    ):
        assert marker in SCRIPT or marker in CSS


def test_cleanup_uses_dom_apis_without_html_string_sinks() -> None:
    for marker in (
        'document.createElement(tag)',
        'document.createElementNS(SVG_NS, "svg")',
        'element.textContent = String(options.text)',
        'parent.append(child instanceof Node',
    ):
        assert marker in SCRIPT
    for forbidden in (
        '.innerHTML',
        '.outerHTML',
        'insertAdjacentHTML',
        'document.write',
        'DOMParser',
        'createContextualFragment',
    ):
        assert forbidden not in SCRIPT


def test_cleanup_keeps_business_logic_untouched() -> None:
    for source in (SCRIPT, ZEN):
        assert 'fetch(' not in source
        assert 'XMLHttpRequest' not in source
        assert '.api.' not in source
        assert 'cloneNode' not in source
        assert 'requestSubmit' not in source
        assert 'data-action="transition-task"' not in source


def test_single_navigation_clean_geometry_and_accessibility() -> None:
    for marker in (
        '.workspace-shell > .sidebar',
        '.workspace-deckbar',
        '.workspace-task-dock',
        '.os-clean-page > :not([data-os-clean-keep="true"])',
        '.ce-mac-dock',
        '.academy-v2-dock',
        '@media (max-width: 680px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_visual_qa_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    for filename in (
        "workspace-os-v3-visual-qa.js",
        "workspace-os-v3-zen-control.js",
    ):
        subprocess.run(
            [node, "--check", str(APP_DIR / filename)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_visual_qa_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
