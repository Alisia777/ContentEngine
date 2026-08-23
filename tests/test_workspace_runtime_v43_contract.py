from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
APP_JS = (APP / "app.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CONTEXT_TRASH = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
FINDER = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
CORE_CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
STABILITY_CSS = (APP / "workspace-os-v4-stability.css").read_text(encoding="utf-8")
INTERFACE_CSS = (APP / "interface-system.css").read_text(encoding="utf-8")
DOM_PATCH = (APP / "workspace-dom-patch.js").read_text(encoding="utf-8")
GENERATION_SPEND = (APP / "generation-spend-view.js").read_text(encoding="utf-8")
MANAGER_DASHBOARD = (APP / "manager-dashboard-view.js").read_text(encoding="utf-8")
DOM_PATCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_dom_patch_harness.html"
).read_text(encoding="utf-8")
DESKTOP_FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_v43_harness.html"
).read_text(encoding="utf-8")
FINDER_PATCH_FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_finder_patch_harness.html"
).read_text(encoding="utf-8")
SCROLL_ORDER_FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_scroll_order_harness.html"
).read_text(encoding="utf-8")
ROUTE_MOTION_FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_route_motion_harness.html"
).read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_v49_loader_has_three_script_adapters_and_one_shared_operations_style() -> None:
    assert 'const BUILD = "20260823.copy-engines.41"' in LOADER
    route_assets = _between(
        LOADER,
        "const ROUTE_ASSETS = Object.freeze({",
        "\n});\n\nfunction routePath",
    )
    route_keys = re.findall(
        r"^  ([a-z][a-z0-9_]*): Object\.freeze",
        route_assets,
        flags=re.MULTILINE,
    )
    assert route_keys == ["finder", "generation", "review", "operations"]
    assert 'styles: [`workspace-os-v4-operations.css?v=${BUILD}`]' in route_assets
    assert "modules: []" in route_assets

    loaded_scripts = set(re.findall(r"(workspace[-a-z0-9]+\.js)\?v=", LOADER))
    assert loaded_scripts == {
        "workspace-action-key.js",
        "workspace-embedded-window-runtime.js",
        "workspace-os-v4.js",
        "workspace-os-v4-trash-rpc-alias.js",
        "workspace-os-v4-context-trash.js",
        "workspace-os-v4-finder.js",
        "workspace-os-v4-generation-guided.js",
        "workspace-os-v4-review-guided.js",
    }

    for retired_decorator in (
        "workspace-os-v4-stability.js",
        "workspace-os-v4-operations.js",
        "workspace-ui-bug-checkin.js",
        "workspace-desktop-os.js",
        "workspace-generation-os.js",
        "workspace-generation-learning-advisor.js",
        "workspace-media-finder.js",
        "workspace-publishing-os.js",
        "workspace-work-stage-manager.js",
        "workspace-results-ledger.js",
        "workspace-academy-os-v2.js",
        "workspace-academy-lab-v3.js",
        "workspace-os-v3-native-bridge.js",
    ):
        assert retired_decorator not in LOADER


def test_loader_waits_for_core_css_and_the_latest_coordinated_mount() -> None:
    load_route = _between(LOADER, "async function loadRoute(", "\nfunction schedule(")
    assert load_route.index("await corePromise") < load_route.index(
        "await Promise.all(styles.map(ensureStyle))"
    )
    assert load_route.index("await Promise.all(styles.map(ensureStyle))") < load_route.index(
        "await ensureModule(modulePath)"
    )
    assert load_route.index("await ensureModule(modulePath)") < load_route.index(
        "await window.ContentEngineDesktopV4?.flush?.()"
    )
    assert "const epoch = ++routeEpoch" in load_route
    assert load_route.count("epoch !== routeEpoch") >= 3
    assert load_route.count("route !== routePath()") >= 2

    set_loading = _between(LOADER, "function setLoading(", "\nfunction absoluteAsset(")
    for gate in (
        'document.documentElement.dataset.ceV4Loading = "true"',
        'delete document.documentElement.dataset.ceV4Loading',
        'delete document.documentElement.dataset.ceV4Ready',
        'document.documentElement.dataset.ceV4Ready = "true"',
    ):
        assert gate in set_loading


def test_active_graph_has_one_dom_observer_and_no_delayed_stability_remounts() -> None:
    active_sources = (LOADER, CORE, CONTEXT_TRASH, FINDER)
    assert sum(source.count("new MutationObserver") for source in active_sources) == 1
    assert CORE.count("new MutationObserver") == 1
    assert "new MutationObserver" not in CONTEXT_TRASH
    assert "new MutationObserver" not in FINDER
    assert "[80, 220, 520]" not in "\n".join(active_sources)

    assert 'registerAdapter("context-trash", mount, { priority: 900 })' in CONTEXT_TRASH
    assert 'registerAdapter("finder-board", mount, { priority: 100 })' in FINDER
    for adapter in (CONTEXT_TRASH, FINDER):
        assert 'addEventListener("hashchange"' not in adapter
        assert "contentengine:v4-route-ready" not in adapter
        assert 'addEventListener("DOMContentLoaded"' not in adapter


def test_core_exposes_one_frame_mount_coordinator() -> None:
    for marker in (
        "function registerAdapter(",
        "function scheduleMount(",
        "function flush(",
        "registerAdapter,",
        "requestMount: scheduleMount,",
        "flush,",
    ):
        assert marker in CORE

    schedule_mount = _between(CORE, "function scheduleMount(", "\nfunction observeWorkspace(")
    assert schedule_mount.count("requestAnimationFrame") == 1
    assert "window.requestAnimationFrame(runMount)" in schedule_mount
    assert "requestAnimationFrame(()" not in schedule_mount
    assert "requestAnimationFrame" not in _between(
        CORE,
        "function runMount(",
        "\nfunction registerAdapter(",
    )


def test_dock_geometry_is_stable_and_home_uses_the_native_project_chooser() -> None:
    ensure_dock = _between(CORE, "function ensureDock(", "\nfunction updateDock(")
    begin_reorder = _between(
        CORE,
        "function beginDockPointerReorder(",
        "\nfunction moveDockPointerReorder(",
    )
    move_reorder = _between(
        CORE,
        "function moveDockPointerReorder(",
        "\nfunction finishDockPointerReorder(",
    )
    assert 'dock.addEventListener("pointermove", moveDockPointerReorder)' in ensure_dock
    assert "if (event.button !== 0) return" in begin_reorder
    assert "const pendingEdit = !dockEditing()" in begin_reorder
    assert "if (drag.pendingEdit)" in move_reorder
    assert "openDockEditor({ focus: false })" in move_reorder
    assert "const drag = runtime.dockPointerReorder" in move_reorder
    assert "if (!drag || drag.pointerId !== event.pointerId) return" in move_reorder
    assert "candidate.getBoundingClientRect()" in move_reorder

    home = _between(CORE, "function mountHome(", "\nfunction projectContext(")
    project_markup = _between(
        APP_JS,
        "function homeProjectSwitcherMarkup(",
        "\nfunction renderHomeSection(",
    )
    assert 'q("[data-ce-v4-project-home]", page)' in home
    assert "projects.dataset.ceV4Surface = \"true\"" in home
    assert "home-project-create-form" not in home
    assert "data-ce-v4-project-home" in project_markup
    assert "data-ce-v4-project-id" in project_markup
    assert "home-project-create-form" in project_markup
    assert "projectFlow.projects" in project_markup
    assert "project.next_action" in project_markup
    assert "exactProjectNextActionRoute" in project_markup
    assert 'href="#${escapeHtml(nextRoute)}"' in project_markup
    assert "const projects = projectFlow.projects" in project_markup
    assert "board.folders" not in project_markup
    for retired_home_control in (
        "ce-v4-home__secondary",
        "ce-v4-home__rail",
        "ce-v4-stage",
        "data-ce-v4-stage",
    ):
        assert retired_home_control not in home


def test_route_scroll_is_restored_once_before_the_mount_frame_paints() -> None:
    restore = _between(CORE, "function restoreScroll(", "\nfunction governVideo(")
    assert "requestAnimationFrame" not in restore
    assert "saved?.windowY" in restore
    assert "saved?.nested" in restore
    assert "if (runtime.restoredRoute === route) return" not in restore
    assert "runtime.restoredScrollNodes.has(node)" in restore
    assert "runtime.restoredScrollNodes.add(node)" in restore
    assert "node.scrollTop = Math.max(0, Number(point?.top) || 0)" in restore
    assert "node.scrollLeft = Math.max(0, Number(point?.left) || 0)" in restore

    handle = _between(CORE, "function handleHashChange(", "\nfunction handleKeydown(")
    assert handle.index("window.clearTimeout(runtime.scrollTimer)") < handle.index(
        "const previousActionKey = runtime.actionKey"
    )
    assert "runtime.preNavigationActionKey === previousActionKey" in handle
    assert "captureScroll(runtime.route, previousActionKey)" in handle
    assert "runtime.restoredScrollNodes = new WeakSet()" in handle
    assert 'window.addEventListener("hashchange", handleHashChange, { capture: true, passive: true })' in CORE


def test_same_route_dom_patch_preserves_live_surfaces_and_stable_records() -> None:
    assert 'import { patchWorkspaceContent } from "./workspace-dom-patch.js?v=20260823.copy-engines.41"' in APP_JS
    for marker in (
        "const WORKSPACE_PATCH_KEY_ATTRIBUTES",
        '"data-workspace-item-key"',
        '"data-generation-job-id"',
        '"data-review-result-id"',
        '"data-placement-id"',
        '"data-member-id"',
        '"data-research-id"',
        '"data-incident-id"',
        "function uniqueKeyedNodes(",
        "function reviewMediaIdentity(",
        "function mediaSourceSignature(",
        "current.isEqualNode(next)",
        'current.type !== "file"',
        "if (sourceChanged) current.load()",
        "current instanceof HTMLDetailsElement",
    ):
        assert marker in DOM_PATCH

    for runtime_surface in (
        '".ce-v4-home"',
        '".ce-v4-finder-toolbar"',
        '".ce-v4-folder-search"',
        '".ce-v4-finder-kind"',
    ):
        assert runtime_surface in DOM_PATCH

    public_patch = _between(
        DOM_PATCH,
        "export function patchWorkspaceContent(",
        "\n}",
    )
    assert "parseWorkspaceMarkup(markup)" in public_patch
    assert "patchChildren(container, parseWorkspaceMarkup(markup))" in public_patch
    assert "container.innerHTML" not in public_patch

    assert '<article class="card media-card" data-media-id=' in APP_JS
    assert '<tr data-member-id=' in APP_JS
    assert '<tr data-campaign-id=' in GENERATION_SPEND
    assert 'class="manager-member-row" data-member-id=' in MANAGER_DASHBOARD
    assert 'class="manager-invite-row" data-invite-email=' in MANAGER_DASHBOARD


def test_same_route_patch_recoordinates_runtime_state_after_one_dom_pass() -> None:
    same_route = _between(
        APP_JS,
        "if (existingShell?.dataset.workspaceSection === section && existingContent) {",
        "\n  if (\n    window.CONTENTENGINE_DESKTOP_V4 === true",
    )
    assert same_route.count("patchWorkspaceContent(existingContent, content)") == 1
    assert same_route.count("window.ContentEngineDesktopV4?.requestMount?.()") == 2
    assert "const sameAction = previousActionKey === nextActionKey" in same_route
    assert "if (!sameAction)" in same_route
    assert "resetWorkspaceRouteEntry(existingContent, section)" in same_route
    assert "existingContent.innerHTML" not in same_route

    assert "const contentReviewDecisionMediaBindings = new WeakMap()" in APP_JS
    media_binding = _between(
        APP_JS,
        "function bindContentReviewDecisionMedia()",
        "\nfunction contentReviewExactMediaReady(",
    )
    assert "existingBinding?.media === media" in media_binding
    assert "existingBinding?.identity === bindingIdentity" in media_binding
    assert 'form.dataset.mediaBinding = "true"' in media_binding

    finder_mount = _between(FINDER, "function mount()", "\ndocument.addEventListener(\"keydown\"")
    assert "sortCards(sortValue);" in finder_mount
    assert 'filterFolders(q(\'#workspace-board-filter-form input[name="query"]\', board)?.value || "")' in finder_mount
    assert "runtime.sortedBoard !== board" not in finder_mount
    annotate = _between(FINDER, "function annotateCards()", "\nfunction applyView()")
    assert 'card.dataset.ceV4FinderAnnotated === "true") return' not in annotate
    assert "card.tabIndex = -1" in annotate


def test_live_browser_harnesses_cover_identity_motion_and_runtime_resets() -> None:
    for marker in (
        "reviewFormIdentity",
        "reviewVideoIdentity",
        "reviewProofPreserved",
        "changedReviewFormIdentity",
        "changedReviewProofReset",
        "researchEntityIsolation",
        "detailsState",
        "fileIdentity",
    ):
        assert marker in DOM_PATCH_FIXTURE

    assert 'await import("../../web/app/workspace-os-v4.js")' in DESKTOP_FIXTURE
    for marker in (
        "shellSame",
        "menubarSame",
        "dockSame",
        "launchClass",
        "launchAnimation",
        "reducedMotion",
        "fullscreenEntered",
        "fullscreenEnteredViewport",
    ):
        assert marker in DESKTOP_FIXTURE

    for marker in (
        "capturedTop === 137",
        "restoredTop === 137",
        "preservedLiveTop === 83",
    ):
        assert marker in SCROLL_ORDER_FIXTURE

    for marker in (
        'main.className = "route-enter"',
        'content.classList.add("ce-v4-content-reveal")',
        'contentengine:v4-route-ready',
        'workspace-os-v4-loader.js',
    ):
        assert marker in ROUTE_MOTION_FIXTURE

    for marker in (
        'await import("../../web/app/workspace-os-v4-finder.js")',
        "toolbarIdentity",
        "searchIdentity",
        "sortedOrder",
        "cardTabIndex",
        "folderFilter",
    ):
        assert marker in FINDER_PATCH_FIXTURE


def test_dom_reconciler_sanitizes_markup_before_adopting_nodes() -> None:
    patch = _between(
        DOM_PATCH,
        "export function patchWorkspaceContent(",
        "\n}",
    )
    assert "parseWorkspaceMarkup(markup)" in patch
    assert "innerHTML" not in patch
    assert 'import "https://cdn.jsdelivr.net/npm/dompurify@3.4.13/dist/purify.min.js"' in DOM_PATCH
    assert 'DOMPurify.sanitize(String(markup || ""), {' in DOM_PATCH
    assert "RETURN_DOM_FRAGMENT: true" in DOM_PATCH
    assert "BLOCKED_MARKUP_ELEMENTS" in DOM_PATCH
    assert 'FORBID_ATTR: ["srcdoc", "srcset"]' in DOM_PATCH
    assert "hardenWorkspaceMarkup(fragment)" in DOM_PATCH
    assert "escapeHtmlAttribute(query)" in FINDER_PATCH_FIXTURE
    assert "unsafeScriptNotExecuted" in DOM_PATCH_FIXTURE
    assert "unsafeScriptRemoved" in DOM_PATCH_FIXTURE
    assert "unsafeEventsRemoved" in DOM_PATCH_FIXTURE
    assert "unsafeUrlsRemoved" in DOM_PATCH_FIXTURE


def test_desktop_owns_the_viewport_and_workspace_window_body_owns_scrolling() -> None:
    body_rule = _between(
        CORE_CSS,
        "body.contentengine-desktop-v4 {\n  box-sizing: border-box;",
        "\n}\n\nbody.contentengine-desktop-v4 .workspace-shell",
    )
    assert "height: 100vh" in body_rule
    assert "height: 100svh" in body_rule
    assert "overflow: hidden !important" in body_rule

    main_scroll = _between(
        CORE_CSS,
        "body.contentengine-desktop-v4 #main-content {",
        "\n}\n\nbody.contentengine-desktop-v4 .ce-v4-page",
    )
    for marker in (
        "height: 100% !important",
        "min-height: 0 !important",
        "overflow: hidden !important",
        "overscroll-behavior: contain",
        "scrollbar-gutter: stable",
    ):
        assert marker in main_scroll

    window_scroll = _between(
        CORE_CSS,
        ".ce-v4-window__body {",
        "\n}\n\n.ce-v4-window__body > #workspace-content",
    )
    assert "overflow-x: hidden" in window_scroll
    assert "overflow-y: auto" in window_scroll
    assert "overscroll-behavior: contain" in window_scroll
    assert "scrollbar-gutter: stable" in window_scroll

    shell_contract = _between(
        STABILITY_CSS,
        "/* The desktop shell owns the viewport; #main-content owns route scrolling. */",
        "/* Late route assets still contain 100dvh contracts; cap their window to this shell. */",
    )
    assert "overflow: hidden !important" in shell_contract
    assert "[data-ce-v4-window-body]" in shell_contract
    assert "overflow-y: auto !important" in shell_contract


def test_persistent_chrome_disables_live_blur_on_safari() -> None:
    persistent_glass = _between(
        STABILITY_CSS,
        "/* Persistent glass is almost opaque: Safari no longer recomposites live blur. */",
        "/* One calm menubar. Tiny system captions are no longer microscopic. */",
    )
    for selector in (
        ".ce-v4-menubar",
        ".ce-v4-dock__glass",
        ".workspace-contextbar",
        '[data-ce-v4-contextbar="primary"]',
    ):
        assert selector in persistent_glass
    assert "backdrop-filter: none !important" in persistent_glass
    assert "-webkit-backdrop-filter: none !important" in persistent_glass


def test_route_transition_gate_keeps_the_shell_anchored_before_motion_css_loads() -> None:
    loading_gate = _between(
        INTERFACE_CSS,
        'html[data-ce-v4-loading="true"] body.contentengine-desktop-v4 .workspace-main',
        "\n\n.workspace-contextbar {",
    )
    for marker in (
        'html[data-ce-v4-ready="true"]',
        "opacity: 1",
        "transform: none",
        "transition: none",
        "pointer-events: none",
    ):
        assert marker in loading_gate
    assert "opacity: 0" not in loading_gate
    assert "translate3d" not in loading_gate
    assert "blur(" not in loading_gate
    assert "scale(" not in loading_gate


def test_short_desktop_login_is_a_single_viewport_action() -> None:
    short_login = INTERFACE_CSS[INTERFACE_CSS.index(
        "@media (min-width: 821px) and (max-height: 800px)"
    ):]
    for marker in (
        ".auth-layout",
        "height: 100svh",
        "overflow: hidden",
        ".auth-steps",
        "display: none",
        ".auth-card",
    ):
        assert marker in short_login
