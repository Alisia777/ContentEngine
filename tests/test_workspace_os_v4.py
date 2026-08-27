from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
INDEX = (APP / "index.html").read_text(encoding="utf-8")
APP_SCRIPT = (APP / "app.js").read_text(encoding="utf-8")
DOM_PATCH = (APP / "workspace-dom-patch.js").read_text(encoding="utf-8")
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


def test_desktop_v4_6_is_the_only_eager_workspace_shell() -> None:
    assert "v4." + "28" not in INDEX
    assert "os4." + "28" not in INDEX
    assert '<link rel="stylesheet" href="./workspace-os-v4.css?v=20260826.rebuild-clean.28" />' in INDEX
    assert (
        '<script type="module" '
        'src="./workspace-os-v4-loader.js?v=20260826.rebuild-clean.28">'
        '</script>' in INDEX
    )
    assert INDEX.index('./workspace-os-v4-loader.js') < INDEX.index('./app.js')
    assert INDEX.index('./app.js') < INDEX.index('./workspace-build-guard.js')

    active_modules = re.findall(
        r'^\s*<script type="module" src="([^\"]+)"',
        INDEX,
        flags=re.MULTILINE,
    )
    assert active_modules == [
        './workspace-os-v4-loader.js?v=20260826.rebuild-clean.28',
        './app.js?v=20260826.rebuild-clean.28',
        './workspace-build-guard.js?v=20260826.rebuild-clean.28',
    ]


def test_route_loader_uses_current_v4_6_guided_assets_and_the_dom_patch() -> None:
    for marker in (
        'const BUILD = "20260826.rebuild-clean.28"',
        'new URL(relative, import.meta.url).href',
        'import(href)',
        'return route.startsWith("/workspace/");',
        'workspace-os-v4-polish.css?v=${BUILD}',
        'workspace-os-v4-context-trash.css?v=${BUILD}',
        'workspace-os-v4-flow.css?v=${BUILD}',
        'workspace-os-v4-stability.css?v=${BUILD}',
        'workspace-os-v4-motion.css?v=${BUILD}',
        'workspace-os-v4.js?v=${DESKTOP_CORE_BUILD}',
        'workspace-os-v4-trash-rpc-alias.js?v=${BUILD}',
        'workspace-os-v4-context-trash.js?v=${GENERATION_HOTFIX_BUILD}',
        'workspace-os-v4-finder.css?v=${BUILD}',
        'workspace-os-v4-finder.js?v=${BUILD}',
        'workspace-os-v4-generation-guided.css?v=${BUILD}',
        'workspace-os-v4-generation-guided.js?v=${GENERATION_HOTFIX_BUILD}',
        'workspace-os-v4-review-guided.css?v=${BUILD}',
        'workspace-os-v4-review-guided.js?v=${BUILD}',
        'match: (route) => route === "/workspace/board"',
        'match: (route) => route === "/workspace/generation"',
        'match: (route) => route === "/workspace/review"',
        'window.ContentEngineDesktopV4?.flush?.()',
        'contentengine:v4-route-ready',
    ):
        assert marker in LOADER

    assert LOADER.index('workspace-os-v4.js?v=${DESKTOP_CORE_BUILD}') < LOADER.index(
        'workspace-os-v4-trash-rpc-alias.js?v=${BUILD}'
    ) < LOADER.index('workspace-os-v4-context-trash.js?v=${GENERATION_HOTFIX_BUILD}')
    for retired in (
        'workspace-os-v4-stability.js',
        'workspace-os-v4-polish.js',
        'workspace-os-v4-surface-guard.js',
        'workspace-os-v4-operations.js',
        'workspace-ui-bug-checkin.js',
        'workspace-generation-os.js',
        'workspace-desktop-os.js',
        'workspace-academy-',
    ):
        assert retired not in LOADER
    assert 'fetch(' not in LOADER
    assert 'XMLHttpRequest' not in LOADER

    assert 'import { patchWorkspaceContent } from "./workspace-dom-patch.js?v=20260826.rebuild-clean.28";' in APP_SCRIPT
    assert 'patchWorkspaceContent(existingContent, content);' in APP_SCRIPT
    for marker in (
        'export function patchWorkspaceContent(container, markup)',
        'data-ce-patch-key',
        'if (current.type !== "file") current.value = next.value;',
        'runtimeOwnedNode',
    ):
        assert marker in DOM_PATCH


def test_system_shell_has_one_dock_one_menubar_and_stable_context_chrome() -> None:
    for marker in (
        'ce-v4-menubar',
        'ce-v4-dock',
        'const ROUTES = Object.freeze([',
        'const SECONDARY_ROUTES = Object.freeze([',
        'if (runtime.menubar?.isConnected) return runtime.menubar;',
        'if (runtime.dock?.isConnected) return runtime.dock;',
        'routeIsAuthorized(record.route)',
        'notifications.dataset.ceV4Notifications = "/workspace/work?view=notifications";',
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

    dock_routes = re.search(
        r'const ROUTES = Object\.freeze\(\[(.*?)\]\);\s*const SECONDARY_ROUTES',
        CORE,
        flags=re.DOTALL,
    )
    assert dock_routes is not None
    assert dock_routes.group(1).count('Object.freeze({ route: "/workspace/') == 10
    assert '/learn' not in dock_routes.group(1)
    assert CORE.count('const bar = create("header", "ce-v4-menubar");') == 1
    assert CORE.count('const dock = create("nav", "ce-v4-dock");') == 1

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
        'XMLHttpRequest',
    ):
        assert forbidden not in CORE
        assert forbidden not in STABILITY
    assert 'fetch(' not in CORE
    assert 'fetch(' not in STABILITY
    assert '.api.' not in CORE
    assert '.api.' not in STABILITY
    assert 'new MutationObserver' not in STABILITY
    finder_search = CORE[
        CORE.index("function focusFinderSearch(") : CORE.index("\nfunction fullscreenElement(")
    ]
    assert CORE.count("requestSubmit") == 1
    assert 'input.form?.requestSubmit?.()' in finder_search
    assert '#workspace-board-filter-form input[name="query"]' in finder_search
    assert "requestSubmit" not in STABILITY


def test_dock_project_guidance_is_clickable_focusable_and_never_uses_a_cross_cursor() -> None:
    activate = CORE[
        CORE.index("function activateDockKey(") : CORE.index("\nfunction ensureDock()")
    ]
    dock = CORE[
        CORE.index("function ensureDock()") : CORE.index("\nfunction updateDock()")
    ]

    assert "activateDockKey(item.dataset.ceV4DockKey, event)" in dock
    assert 'workspaceRouteRequiresProject(destination)' in activate
    assert '!snapshot.id' in activate
    assert "event?.preventDefault?.()" in activate
    assert "explainProjectRequired(destination)" in activate

    policy = CORE[
        CORE.index("function workspaceRouteRequiresProject(") :
        CORE.index("\nfunction routeMatches(")
    ]
    focus_target = policy[
        policy.index("function focusProjectChoiceTarget(") :
        policy.index("function explainProjectRequired(")
    ]
    explanation = policy[policy.index("function explainProjectRequired(") :]
    assert 'path === "/workspace/work"' in policy
    assert '=== "notifications"' in policy
    assert "PROJECT_REQUIRED_ROUTES.has(path)" in policy
    assert 'q(\'[data-action="retry-project-flow"]\')' in focus_target
    assert "focusProjectChoiceTarget" in explanation
    assert "сначала выберите проект" in explanation
    assert 'window.location.hash = "#/workspace/home"' in explanation

    update = CORE[CORE.index("function updateDock()") : CORE.index("\nfunction projectFlowRoot(")]
    assert 'item.classList.toggle("is-project-required", projectRequired)' in update
    assert 'if (locked || !authorized) item.setAttribute("aria-disabled", "true")' in update
    assert "else item.removeAttribute(\"aria-disabled\")" in update
    assert "locked || projectRequired" not in update
    assert 'item.setAttribute("aria-disabled", "true")' not in update[
        update.index("const projectRequired") : update.index("if (locked || !authorized)")
    ]
    assert "нужен проект. Нажмите, чтобы перейти к выбору проекта" in update
    assert ".ce-v4-dock__item.is-project-required" in CORE_CSS
    assert re.search(
        r'\.ce-v4-dock__item\[aria-disabled="true"\]\s*\{[^}]*cursor:\s*pointer',
        CORE_CSS,
        flags=re.DOTALL,
    )
    assert re.search(
        r'\.ce-v4-project-progress__steps\s+a\[aria-disabled="true"\]\s*\{[^}]*cursor:\s*pointer',
        CORE_CSS,
        flags=re.DOTALL,
    )
    project_guidance_css = "\n".join(
        match.group(1)
        for match in re.finditer(
            r'(?:\.ce-v4-dock__item(?:\.is-project-required)?(?:\[aria-disabled="true"\])?'
            r'|\.ce-v4-project-progress__steps\s+a\[aria-disabled="true"\])\s*\{([^}]*)\}',
            CORE_CSS,
        )
    )
    assert "cursor: not-allowed" not in project_guidance_css
    tooltip_rule = re.search(
        r"\.ce-v4-dock__tooltip\s*\{(?P<body>[^}]*)\}",
        CORE_CSS,
        flags=re.DOTALL,
    )
    assert tooltip_rule is not None
    assert re.search(r"width:\s*max-content", tooltip_rule.group("body"))
    assert re.search(r"max-width:\s*min\(", tooltip_rule.group("body"))


def test_loader_reconciles_stale_routes_and_replace_state_reloads_the_current_action() -> None:
    loader = LOADER
    load_route = loader[loader.index("async function loadRoute(") : loader.index("\nfunction ensureCore()")]
    schedule = loader[loader.index("function schedule()") : loader.index("\nwindow.addEventListener")]

    assert "function reconcileStaleLoad(epoch)" in loader
    assert load_route.count("return reconcileStaleLoad(epoch)") == 3
    assert 'document.documentElement.dataset.ceV4Loading !== "true"' in schedule
    assert "function loadCurrentRoute()" in loader
    assert "setFailed(route, error)" in loader
    assert "load: () => loadCurrentRoute()" in loader
    assert "ContentEngineDesktopV4Loader?.load?.()" in APP_SCRIPT


def test_finder_uses_the_real_workspace_board_and_existing_server_filter_form() -> None:
    for marker in (
        'ROUTE = "/workspace/board"',
        '.workspace-board',
        '#workspace-board-filter-form',
        'form.dispatchEvent(new Event("submit"',
        'workspace-board__folder-row',
        'Найти проект, папку, SKU или файл',
        'По имени',
        'По типу',
        'По статусу',
        'ФАЙЛЫ · ПРОСМОТР',
        'ce-v4-quicklook-inline',
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
        '@media (max-width: 680px)',
        '@media (max-height: 680px)',
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
