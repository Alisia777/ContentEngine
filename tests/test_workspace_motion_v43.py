from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
LOADER = (APP_DIR / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
MOTION = (APP_DIR / "workspace-os-v4-motion.css").read_text(encoding="utf-8")
INTERFACE = (APP_DIR / "interface-system.css").read_text(encoding="utf-8")
CONTEXT = (APP_DIR / "workspace-os-v4-context-trash.js").read_text(
    encoding="utf-8"
)
CONTEXT_CSS = (APP_DIR / "workspace-os-v4-context-trash.css").read_text(
    encoding="utf-8"
)
FINDER = (APP_DIR / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
FINDER_CSS = (APP_DIR / "workspace-os-v4-finder.css").read_text(
    encoding="utf-8"
)
CORE_CSS = (APP_DIR / "workspace-os-v4.css").read_text(encoding="utf-8")
STABILITY = (APP_DIR / "workspace-os-v4-stability.css").read_text(encoding="utf-8")
HARNESS = (ROOT / "tests" / "fixtures" / "workspace_v43_harness.html").read_text(
    encoding="utf-8"
)


def test_motion_layer_is_loaded_after_the_stability_contract() -> None:
    stability = "workspace-os-v4-stability.css?v=${BUILD}"
    motion = "workspace-os-v4-motion.css?v=${BUILD}"
    assert stability in LOADER
    assert motion in LOADER
    assert LOADER.index(stability) < LOADER.index(motion)


def test_same_action_refresh_skips_the_route_gate_but_query_actions_do_not() -> None:
    assert 'let lastScheduledActionKey = "";' in LOADER
    assert "const actionKey = workspaceActionKey();" in LOADER
    assert "const sameAction = actionKey === lastScheduledActionKey;" in LOADER
    assert "lastScheduledActionKey = actionKey;" in LOADER
    assert "if (sameAction && isManagedRoute(route))" in LOADER
    same_route_guard = LOADER.index("if (sameAction && isManagedRoute(route))")
    loading_gate = LOADER.index("setLoading(isManagedRoute(route), route)")
    assert same_route_guard < loading_gate


def test_route_motion_keeps_the_desktop_chrome_stable() -> None:
    for token in (
        "--ce-motion-fast: 140ms",
        "--ce-motion-base: 210ms",
        "--ce-motion-route: 260ms",
        "--ce-motion-ease:",
    ):
        assert token in MOTION
    assert 'data-ce-v4-loading="true"' in MOTION
    assert ".workspace-main" in MOTION
    assert "opacity: 1 !important" in MOTION
    assert "#main-content.route-enter .ce-v4-page" in MOTION
    loading_selector = (
        'html[data-ce-v4-loading="true"] body.contentengine-desktop-v4 '
        '#main-content .ce-v4-page {'
    )
    loading_rule = MOTION[
        MOTION.index(loading_selector) : MOTION.index("\n}", MOTION.index(loading_selector))
    ]
    assert "opacity: .96 !important" in loading_rule
    assert "transform: none !important" in loading_rule
    assert "scale(" not in loading_rule
    assert "body:not(.contentengine-desktop-v4) .route-enter" in INTERFACE
    eager_loading = INTERFACE[
        INTERFACE.index('html[data-ce-v4-loading="true"] body.contentengine-desktop-v4 .workspace-main {') :
        INTERFACE.index("\n}", INTERFACE.index('html[data-ce-v4-loading="true"] body.contentengine-desktop-v4 .workspace-main {'))
    ]
    eager_ready = INTERFACE[
        INTERFACE.index('html[data-ce-v4-ready="true"] body.contentengine-desktop-v4 .workspace-main {') :
        INTERFACE.index("\n}", INTERFACE.index('html[data-ce-v4-ready="true"] body.contentengine-desktop-v4 .workspace-main {'))
    ]
    for eager_gate in (eager_loading, eager_ready):
        assert "opacity: 1" in eager_gate
        assert "transform: none" in eager_gate
        assert "transition: none" in eager_gate
    assert "ce-v4-route-progress" not in MOTION
    assert "transition: all" not in MOTION
    assert "backdrop-filter: none !important" in MOTION
    assert "ce-v4-dock-launch" in MOTION
    assert ".ce-v4-dock__item.is-launching .ce-v4-dock__tile" in MOTION
    assert "workspace-os-v4-motion.css" in HARNESS


def test_route_enter_is_one_animation_and_is_released_after_it_finishes() -> None:
    assert 'entering?.querySelector("#workspace-content")?.classList.remove("ce-v4-content-reveal")' in LOADER
    assert "function armRouteEnterCleanup(route, actionKey, epoch)" in LOADER
    assert 'event.animationName !== "ce-v4-route-enter"' in LOADER
    assert 'main.classList.remove("route-enter")' in LOADER
    assert "window.setTimeout(finish, 450)" in LOADER
    load_route = LOADER[LOADER.index("async function loadRoute(") : LOADER.index("\nfunction schedule(")]
    assert load_route.index("armRouteEnterCleanup(route, actionKey, epoch)") < load_route.index("setLoading(false, route)")


def test_menubar_has_mac_traffic_lights_and_real_fullscreen_control() -> None:
    menubar = CORE[CORE.index("function ensureMenubar(") : CORE.index("\nfunction updateClock(")]
    for marker in (
        'create("div", "ce-v4-menubar__start")',
        'create("span", "ce-v4-traffic")',
        'fullscreen.dataset.ceV4Fullscreen = "true"',
        "void toggleFullscreen()",
    ):
        assert marker in menubar
    assert "function toggleFullscreen()" in CORE
    assert "function fullscreenMode()" in CORE
    assert "function fullscreenSupported()" in CORE
    assert "document.exitFullscreen" in CORE
    assert "document.webkitExitFullscreen" in CORE
    assert "document.documentElement.requestFullscreen" in CORE
    assert "document.documentElement.webkitRequestFullscreen" in CORE
    assert 'if (standard) return "standard"' in CORE
    assert 'if (webkit) return "webkit"' in CORE
    assert 'else if (mode === "standard")' in CORE
    assert 'else if (mode === "webkit")' in CORE
    assert 'aria-pressed' in CORE
    assert "control.hidden = !supported" in CORE
    assert "Браузер не разрешил полноэкранный режим" in CORE
    assert ".ce-v4-menubar__start" in CORE_CSS


def test_persistent_menubar_does_not_retain_a_webkit_transform_layer() -> None:
    selector = 'body.contentengine-desktop-v4[data-ce-v4-stable="true"] .ce-v4-menubar {'
    start = MOTION.index(selector)
    rule = MOTION[start : MOTION.index("\n}", start)]
    assert "ce-v4-menubar-enter" in rule
    assert " both" not in rule
    assert "forwards" not in rule


def test_dock_magnification_moves_only_tiles_and_has_accessible_fallbacks() -> None:
    assert "transform-origin: 50% 100%" in STABILITY
    assert "@media (hover: hover) and (pointer: fine)" in STABILITY
    assert "@supports selector(.ce-v4-dock__item:has(" in STABILITY
    assert "@supports not selector(.ce-v4-dock__item:has(" in STABILITY
    for scale in ("scale(1.025)", "scale(1.055)", "scale(1.1)"):
        assert scale in STABILITY
    assert ".ce-v4-dock__item:focus-visible .ce-v4-dock__tile" in STABILITY
    assert ".ce-v4-dock__item:hover .ce-v4-dock__tile" in STABILITY
    assert ".ce-v4-dock__item:hover {" not in STABILITY
    reduced = MOTION[MOTION.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".ce-v4-dock__glass:is(:hover, :focus-within) .ce-v4-dock__tile" in reduced
    assert "transform: none !important" in reduced


def test_fullscreen_layout_does_not_reserve_a_second_body_scrollbar_gutter() -> None:
    stable_body = STABILITY[
        STABILITY.index('body.contentengine-desktop-v4[data-ce-v4-stable="true"] {') :
        STABILITY.index("\n}", STABILITY.index('body.contentengine-desktop-v4[data-ce-v4-stable="true"] {'))
    ]
    assert "scrollbar-gutter: auto" in stable_body
    assert "scrollbar-gutter: stable" in STABILITY


def test_motion_has_reduced_motion_and_mobile_dock_fallbacks() -> None:
    assert "@media (prefers-reduced-motion: reduce)" in MOTION
    assert "@media (max-width: 680px)" in MOTION
    assert ".ce-v4-menubar__location" not in CORE
    search_rule_start = CORE_CSS.index(".ce-v4-menubar__search {")
    search_rule = CORE_CSS[search_rule_start : CORE_CSS.index("\n}", search_rule_start)]
    assert "display: grid" in search_rule
    assert "width: 100%" in search_rule
    assert "overflow-x: auto !important" in MOTION
    assert "scroll-snap-type: x proximity" in MOTION
    mobile = MOTION[MOTION.index("@media (max-width: 680px)") : MOTION.index("@media (prefers-reduced-motion: reduce)")]
    reduced = MOTION[MOTION.index("@media (prefers-reduced-motion: reduce)") :]
    assert 'body.contentengine-desktop-v4[data-ce-v4-stable="true"] .ce-v4-dock__glass' in mobile
    assert 'body.contentengine-desktop-v4[data-ce-v4-stable="true"] .ce-v4-menubar' in reduced
    assert "glass.scrollTo" in CORE
    assert 'behavior: REDUCED_MOTION.matches ? "auto" : "smooth"' in CORE


def test_workspace_rerender_skips_unchanged_markup_and_reveals_loaded_content_once() -> None:
    assert "function workspaceContentSignature(section, content)" in APP
    assert "existingContent.dataset.ceV4RenderSignature === contentSignature" in APP
    assert "existingContent.innerHTML = content" in APP
    assert "existingContent.dataset.ceV4InitialLoading" in APP
    assert "revealWorkspaceContent(existingContent)" in APP
    assert ".ce-v4-content-reveal" in MOTION


def test_keyboard_search_opens_finder_without_a_spotlight_subwindow() -> None:
    handler = CORE[CORE.index("function handleKeydown(") : CORE.index("\nfunction handleScroll(")]
    search = CORE[CORE.index("function focusFinderSearch(") : CORE.index("\nfunction fullscreenElement(")]
    assert 'q(".ce-v4-menubar__search input", runtime.menubar)' in handler
    assert "safeFocus(search)" in handler
    assert "search?.select?.()" in handler
    assert "focusFinderSearch(query)" in search
    assert 'navigate("/workspace/board")' in search
    assert "openSpotlight();" not in handler


def test_context_menu_preserves_native_editing_without_modal_layers() -> None:
    assert "function prefersNativeContextMenu(target)" in CONTEXT
    for selector in (
        "input",
        "textarea",
        "select",
        "[contenteditable='true']",
        "a[href]",
        "video",
    ):
        assert selector in CONTEXT
    assert "if (prefersNativeContextMenu(event.target)) return;" in CONTEXT
    assert "if (handleMenuKeyboard(event)) return;" in CONTEXT
    assert "function trapDialogFocus(event, root)" not in CONTEXT
    assert "function syncModalInert()" not in CONTEXT
    assert 'toggleAttribute("inert"' not in CONTEXT
    assert "aria-modal" not in CONTEXT
    assert 'window.location.hash = "#/workspace/board?view=trash"' in CONTEXT
    assert "runtime.suppressClickUntil = Date.now() + 800" in CONTEXT


def test_trash_selection_updates_one_card_without_rebuilding_the_grid() -> None:
    selection = CONTEXT[
        CONTEXT.index("function handleTrashBodyClick(") :
        CONTEXT.index("\nfunction handleTrashBodyContextMenu(")
    ]
    assert "setTrashCardSelection" in selection
    assert "renderTrashItems()" not in selection
    assert 'card.setAttribute("aria-selected", String(selected))' in CONTEXT
    assert "function handleTrashBodyKeydown(event)" in CONTEXT
    assert "width: 38px" in CONTEXT_CSS


def test_finder_reconciles_sort_without_unnecessary_dom_moves_and_stabilizes_scroll() -> None:
    assert "sortCards(sortValue);" in FINDER
    assert "ordered.some((card, index) => current[index] !== card)" in FINDER
    assert 'filterFolders(q(".ce-v4-folder-search input", board)?.value || "")' in FINDER
    assert "document.createDocumentFragment()" in FINDER
    assert "scrollbar-gutter: stable" in FINDER_CSS
    assert "contain-intrinsic-size: 210px 66px" in FINDER_CSS
    assert "--ce-v4-dim: #91847c" in CORE_CSS
