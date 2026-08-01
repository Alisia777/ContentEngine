from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
INDEX = (APP / "index.html").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
STABILITY = (APP / "workspace-os-v4-stability.js").read_text(encoding="utf-8")
FINDER = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
OPERATIONS = (APP / "workspace-os-v4-operations.js").read_text(encoding="utf-8")
BUG_CHECKIN = (APP / "workspace-ui-bug-checkin.js").read_text(encoding="utf-8")
CORE_CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
POLISH_CSS = (APP / "workspace-os-v4-polish.css").read_text(encoding="utf-8")
STABILITY_CSS = (APP / "workspace-os-v4-stability.css").read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")
OPERATIONS_CSS = (APP / "workspace-os-v4-operations.css").read_text(encoding="utf-8")
BUG_CHECKIN_CSS = (APP / "workspace-ui-bug-checkin.css").read_text(encoding="utf-8")


def test_desktop_v4_2_is_the_only_eager_workspace_shell() -> None:
    assert '<link rel="stylesheet" href="./workspace-os-v4.css?v=20260801.os4.2" />' in INDEX
    assert '<script type="module" src="./workspace-os-v4-loader.js?v=20260801.os4.2"></script>' in INDEX
    assert INDEX.index('./app.js') < INDEX.index('./workspace-os-v4-loader.js')
    assert INDEX.index('./workspace-os-v4-loader.js') < INDEX.index('./workspace-build-guard.js')

    active_modules = re.findall(
        r'^\s*<script type="module" src="([^\"]+)"',
        INDEX,
        flags=re.MULTILINE,
    )
    assert active_modules == [
        './app.js?v=20260730.11',
        './workspace-os-v4-loader.js?v=20260801.os4.2',
        './workspace-build-guard.js?v=20260801.os4.2',
    ]


def test_route_loader_uses_one_stability_coordinator_and_lazy_route_adapters() -> None:
    for marker in (
        'const BUILD = "20260801.os4.2"',
        'new URL(relative, import.meta.url).href',
        'import(href)',
        'workspace-os-v4-stability.css?v=${BUILD}',
        'workspace-os-v4-stability.js?v=${BUILD}',
        'workspace-ui-bug-checkin.css?v=${BUILD}',
        'workspace-ui-bug-checkin.js?v=${BUILD}',
        'workspace-os-v4-finder.css?v=${BUILD}',
        'workspace-os-v4-finder.js?v=${BUILD}',
        'workspace-os-v4-operations.css?v=${BUILD}',
        'workspace-os-v4-operations.js?v=${BUILD}',
        'route === "/workspace/work" || route === "/workspace/tasks"',
        'workspace-generation-os.js?v=20260731.1',
        'workspace-desktop-os.js?v=20260730.1',
        'contentengine:v4-route-ready',
    ):
        assert marker in LOADER

    assert 'workspace-os-v4-polish.js' not in LOADER
    assert 'workspace-os-v4-surface-guard.js' not in LOADER
    assert 'fetch(' not in LOADER
    assert 'XMLHttpRequest' not in LOADER


def test_system_shell_has_one_dock_one_menubar_and_stable_context_chrome() -> None:
    for marker in (
        'ce-v4-menubar',
        'ce-v4-dock',
        'ОДИН ЭКРАН · ОДНО ДЕЙСТВИЕ',
        'ПРОИЗВОДСТВЕННЫЙ МАРШРУТ',
        'openMission',
        'openSpotlight',
        'openZen',
        'contentengine-v4-zen-placeholder',
        'FINDER_QUERY_KEY',
        'captureScroll',
        'restoreScroll',
        'video.autoplay = false',
        'video.loop = false',
        'IntersectionObserver',
    ):
        assert marker in CORE

    for marker in (
        'Разбор товара',
        'LOCAL_TOPBARS',
        'LOCAL_DOCKS',
        'DUPLICATE_GLOBAL_CHROME',
        'dataset.ceV4Contextbar',
        'dataset.ceV4LocalDock = "true"',
        'cancelChromeAnimations',
        'contentengine:v4-route-ready',
    ):
        assert marker in STABILITY

    for forbidden in (
        'innerHTML',
        'outerHTML',
        'insertAdjacentHTML',
        'DOMParser',
        'createContextualFragment',
        'cloneNode',
        'requestSubmit',
        'XMLHttpRequest',
    ):
        assert forbidden not in CORE
        assert forbidden not in STABILITY
    assert 'fetch(' not in CORE
    assert 'fetch(' not in STABILITY
    assert '.api.' not in CORE
    assert '.api.' not in STABILITY
    assert 'new MutationObserver' not in STABILITY


def test_finder_uses_the_real_workspace_board_and_existing_server_filter_form() -> None:
    for marker in (
        'ROUTE = "/workspace/board"',
        '.workspace-board',
        '#workspace-board-filter-form',
        'form.dispatchEvent(new Event("submit"',
        'workspace-board__folder-row',
        'Найти папку',
        'По имени',
        'По типу',
        'По статусу',
        'QUICK LOOK',
        'contentengine-v4-finder-drawer',
        'Добавить материал',
    ):
        assert marker in FINDER
    assert 'fetch(' not in FINDER
    assert 'XMLHttpRequest' not in FINDER
    assert 'cloneNode' not in FINDER
    assert 'requestSubmit' not in FINDER
    assert 'innerHTML' not in FINDER


def test_operational_workspaces_scale_without_changing_business_actions() -> None:
    for marker in (
        'Найти задачу, товар или артикул',
        'ИСТОЧНИК ЗАДАЧИ',
        'Ручная задача',
        'Риск ${index + 1} из ${cards.length}',
        'Публикаций пока нет',
        'Поиск по результатам',
        'Поиск по реестру выплат',
    ):
        assert marker in OPERATIONS
    for source in (OPERATIONS, FINDER, STABILITY):
        assert 'fetch(' not in source
        assert 'XMLHttpRequest' not in source
        assert 'requestSubmit' not in source
        assert 'data-action="transition-task"' not in source


def test_bug_checkin_is_local_diagnostic_not_a_business_client() -> None:
    for marker in (
        'contentengine_ui_bug_checkin.v1',
        'contentengine_ui_bug_report.v1',
        'Cmd/Ctrl + Shift + B',
        'Чек‑ин ошибок',
        'scanTinyControls',
        'scanTinyText',
        'scanFixedPanels',
        'empty_or_black_surface',
        'global_dock_count_invalid',
        'multiple_primary_surfaces_visible',
        'horizontal_surface_overflow',
        'navigator.clipboard.writeText',
        'Скачать JSON',
        'Файл не отправляется автоматически',
    ):
        assert marker in BUG_CHECKIN

    for forbidden in (
        'fetch(',
        'XMLHttpRequest',
        'requestSubmit',
        'document.cookie',
        'localStorage',
        'innerHTML',
        'outerHTML',
        'insertAdjacentHTML',
        'DOMParser',
        'createContextualFragment',
    ):
        assert forbidden not in BUG_CHECKIN
    assert '.api.' not in BUG_CHECKIN
    assert 'new MutationObserver' not in BUG_CHECKIN
    assert 'sessionStorage' in BUG_CHECKIN


def test_desktop_v4_2_css_has_readable_stable_responsive_geometry() -> None:
    for marker in (
        '.workspace-shell > .sidebar',
        '.ce-mac-dock',
        '.ce-v4-menubar',
        '.ce-v4-dock',
        '.ce-v4-home',
        '.ce-v4-mission-backdrop',
        '.ce-v4-spotlight-backdrop',
        '.ce-v4-zen-backdrop',
        '@media (max-width: 680px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CORE_CSS
    for marker in (
        '.ce-v4-single-surface',
        '.ce-v4-dock__extra',
        'ce-v4-mission-open',
    ):
        assert marker in POLISH_CSS
    for marker in (
        '--ce-v4-control-height: 44px',
        '--ce-v4-font-control: 14px',
        '[data-ce-v4-contextbar="primary"]',
        '[data-ce-v4-contextbar="secondary"]',
        '[data-ce-v4-connected-menu="true"]',
        '[data-ce-v4-local-dock="true"]',
        '--ce-v4-scale: 1 !important',
        'view-transition-name: none',
        'scrollbar-gutter: stable',
        '@media (max-width: 680px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in STABILITY_CSS
    for marker in (
        '.workspace-board__layout',
        'content-visibility: auto',
        '.ce-v4-folder-search',
        '.ce-v4-quicklook',
    ):
        assert marker in FINDER_CSS
    for marker in (
        '.ce-v4-task-filter',
        '.ce-v4-task-origin',
        '.ce-v4-risk-nav',
        '.ce-v4-table-search',
        '.academy-v2-dock',
    ):
        assert marker in OPERATIONS_CSS
    for marker in (
        '.ce-ui-checkin-backdrop',
        '.ce-ui-checkin',
        '.ce-ui-checkin-field',
        '.ce-ui-checkin-diagnostics',
        '.ce-ui-checkin-preview',
        '@media (max-width: 760px)',
        '@media (max-height: 720px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in BUG_CHECKIN_CSS


def test_desktop_v4_2_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    for filename in (
        "workspace-os-v4-loader.js",
        "workspace-os-v4.js",
        "workspace-os-v4-stability.js",
        "workspace-os-v4-finder.js",
        "workspace-os-v4-operations.js",
        "workspace-ui-bug-checkin.js",
    ):
        subprocess.run(
            [node, "--check", str(APP / filename)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_desktop_v4_2_stylesheets_are_balanced() -> None:
    for stylesheet in (
        CORE_CSS,
        POLISH_CSS,
        STABILITY_CSS,
        FINDER_CSS,
        OPERATIONS_CSS,
        BUG_CHECKIN_CSS,
    ):
        assert stylesheet.count("{") == stylesheet.count("}")
