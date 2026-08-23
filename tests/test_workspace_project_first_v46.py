"""Focused contracts for the project-first Desktop v4.7 reset.

These tests intentionally check user-visible architecture instead of exact copy,
build hashes, helper names, or incidental markup ordering.  The contract is:
one persistent Dock, a project chooser as the first screen, one guided action at
a time, and no full-page blink while route data is loading.
"""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"


def _read(name: str) -> str:
    return (APP_DIR / name).read_text(encoding="utf-8")


CORE = _read("workspace-os-v4.js")
LOADER = _read("workspace-os-v4-loader.js")
CORE_CSS = _read("workspace-os-v4.css")
FLOW_CSS = _read("workspace-os-v4-flow.css")
FINDER_CSS = _read("workspace-os-v4-finder.css")
FINDER = _read("workspace-os-v4-finder.js")
CONTEXT_TRASH = _read("workspace-os-v4-context-trash.js")
MOTION_CSS = _read("workspace-os-v4-motion.css")
APP = _read("app.js")
BOARD = _read("workspace-board-view.js")


def _between(source: str, start: str, end: str) -> str:
    """Return a stable semantic region without depending on line numbers."""

    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _function(source: str, declaration: str) -> str:
    """Extract a JS function with balanced braces."""

    start = source.index(declaration)
    opening = source.index("{", start)
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unbalanced JavaScript function: {declaration}")


def _css_rules(source: str) -> list[tuple[str, str]]:
    """Return ordinary CSS rules; enough for the non-nested selectors below."""

    return [
        (match.group(1).strip(), match.group(2))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", source, flags=re.DOTALL)
        if not match.group(1).lstrip().startswith("@")
    ]


def _route_asset_sources() -> tuple[str, list[str]]:
    manifest = _between(LOADER, "const ROUTE_ASSETS", "function routePath")
    names = sorted(set(re.findall(r"([A-Za-z0-9._-]+\.js)(?:\?[^`\"']*)?", manifest)))
    missing = [name for name in names if not (APP_DIR / name).is_file()]
    assert not missing, f"Route adapter manifest references missing modules: {missing}"
    return manifest, [_read(name) for name in names]


def test_global_chrome_does_not_repeat_the_dock_as_a_flowbar_or_location_title() -> None:
    # The Dock is the only global route switcher.  A contextual project progress
    # strip may live inside the active work surface, but must not be appended to
    # document.body as a second six-route navigation bar.
    for duplicate in (
        "function ensureFlowbar",
        'create("nav", "ce-v4-flowbar")',
        "dataCeV4FlowRoute",
        "data-ce-v4-flow-route",
        "ce-v4-menubar__location",
    ):
        assert duplicate not in CORE

    mount = _function(CORE, "function mount()")
    assert "ensureDock()" in mount
    assert "ensureFlowbar" not in mount
    assert "ceV4ProjectProgress" in CORE or "data-ce-v4-project-progress" in CORE


def test_dock_always_exposes_plain_labels_and_labelled_hover_tooltips() -> None:
    routes = _between(CORE, "const ROUTES", "const SECONDARY_ROUTES")
    for label in (
        "Проекты",
        "Файлы",
        "Создать",
        "Проверить",
        "Опубликовать",
        "Результаты",
        "Исследования",
        "ИИ-центр",
    ):
        assert f'label: "{label}"' in routes

    dock = _function(CORE, "function ensureDock()")
    assert 'create("span", "ce-v4-dock__label", item.label)' in dock
    tooltip_calls = re.findall(
        r'create\("span",\s*"ce-v4-dock__tooltip",\s*([^\n;]+)',
        dock,
    )
    assert tooltip_calls, "Every Dock item needs a textual hover/focus tooltip"
    assert "item.label" in tooltip_calls[0], "The tooltip must say what the icon is, not only describe it"
    assert "Корзина" in dock[dock.index("ce-v4-trash-dock") :], "Trash tooltip must also name the item"
    assert ".ce-v4-dock__item[hidden] { display: none !important; }" in CORE_CSS

    tooltip_rules = [
        (selector, body)
        for selector, body in _css_rules(CORE_CSS)
        if ".ce-v4-dock__tooltip" in selector
    ]
    assert any(":hover" in selector and "opacity: 1" in body for selector, body in tooltip_rules)
    assert any(":focus-visible" in selector and "opacity: 1" in body for selector, body in tooltip_rules)


def test_home_is_a_project_chooser_driven_by_server_projects() -> None:
    mount = _function(CORE, "function mountHome()")
    markup = _function(APP, "function homeProjectSwitcherMarkup(")
    assert "data-ce-v4-project-home" in markup
    assert "data-ce-v4-project-id" in markup
    assert "home-project-create-form" in markup
    assert "projectFlow.projects" in markup
    assert "project.next_action" in markup
    assert "exactProjectNextActionRoute" in markup
    assert "project_id" in markup

    # Core is only the compositor: it promotes the native project chooser to
    # the single v4 surface instead of rebuilding or duplicating its markup.
    assert 'q("[data-ce-v4-project-home]", page)' in mount
    assert "dataset.ceV4Surface" in mount
    assert "home-project-create-form" not in mount

    # Project selection is server-catalog driven. Finder cannot be used as an
    # unscoped fallback because its v4.7 API correctly requires project_id.
    assert "const projects = projectFlow.projects" in markup
    assert "board.folders" not in markup


def test_degraded_board_never_silently_erases_projects_and_permissions() -> None:
    fallback = _function(APP, "async function loadWorkspaceBoardFallback()")
    combined = f"{APP}\n{BOARD}"

    preserves_folder_state = (
        not re.search(r"\bfolders\s*:\s*\[\s*\]", fallback)
        and re.search(r"(?:workspaceBoard|sections\.board|cached|previous)[^\n]{0,160}folders", fallback)
    )
    preserves_capability = (
        "manage_folders: false" not in fallback
        and re.search(r"manage_folders\s*:", fallback)
    )
    honest_retry = (
        re.search(r'data-action=["\'](?:retry|refresh)[^"\']*(?:folder|workspace|board)', combined, re.IGNORECASE)
        and re.search(r"(?:degraded|folders? unavailable|папк[^\n]{0,80}недоступ)", combined, re.IGNORECASE)
    )

    assert (preserves_folder_state and preserves_capability) or honest_retry, (
        "Folder RPC degradation must preserve known folders and the real role capability, "
        "or render an explicit retry control instead of an empty, permissionless Finder"
    )


def test_primary_workspace_surface_uses_the_available_width() -> None:
    page_rules = [
        body
        for selector, body in _css_rules(FLOW_CSS)
        if ".ce-v4-page:not(.ce-v4-home-page)" in selector and ">" not in selector
    ]
    assert page_rules, "The main non-home work surface needs an explicit geometry rule"
    geometry = "\n".join(page_rules)
    assert re.search(r"\bwidth\s*:\s*100%", geometry)
    assert re.search(r"\bmax-width\s*:\s*(?:none|100%)", geometry)

    surface_css = "\n".join((CORE_CSS, FLOW_CSS, FINDER_CSS))
    assert not re.search(r"(?:width|max-width)\s*:\s*min\(\s*1500px", surface_css)


def test_loading_keeps_the_existing_page_readable_and_geometrically_stable() -> None:
    loading_page_rules = [
        body
        for selector, body in _css_rules(MOTION_CSS)
        if 'data-ce-v4-loading="true"' in selector and ".ce-v4-page" in selector
    ]
    assert loading_page_rules, "Loading needs an explicit stable-page rule"
    loading_page_css = "\n".join(loading_page_rules)

    opacities = [float(value) for value in re.findall(r"\bopacity\s*:\s*(0?\.\d+|1(?:\.0+)?)", loading_page_css)]
    assert opacities and min(opacities) >= 0.94
    assert not re.search(r"\bscale(?:3d|X|Y)?\s*\(", loading_page_css, re.IGNORECASE), (
        "Async refresh must not zoom the whole page"
    )


def test_generation_and_review_have_dedicated_guided_route_adapters() -> None:
    manifest, route_sources = _route_asset_sources()
    assert '"/workspace/generation"' in manifest
    assert '"/workspace/review"' in manifest
    assert "workspace-os-v4-generation-guided.js" in manifest
    assert "workspace-os-v4-review-guided.js" in manifest
    assert "workspace-os-v4-generation-guided.css" in manifest
    assert "workspace-os-v4-review-guided.css" in manifest

    guided = "\n".join(route_sources)
    assert "/workspace/generation" in guided
    assert "/workspace/review" in guided


def test_each_guided_step_has_one_visible_panel_and_one_primary_action() -> None:
    _route_asset_sources()
    expected = {
        "generation": APP_DIR / "workspace-os-v4-generation-guided.js",
        "review": APP_DIR / "workspace-os-v4-review-guided.js",
    }
    missing = [path.name for path in expected.values() if not path.is_file()]
    assert not missing, f"Guided route modules are missing: {missing}"

    for name, path in expected.items():
        source = path.read_text(encoding="utf-8")
        assert re.search(
            r"(?:data-(?:ce-v4-)?(?:generation-|review-)?(?:guided-)?step|dataset\.[A-Za-z0-9]*Step)",
            source,
        )
        assert re.search(
            r"(?:data-(?:ce-v4-)?(?:generation-|review-)?(?:guided-)?panel|dataset\.[A-Za-z0-9]*Panel)",
            source,
        )
        assert "aria-current" in source
        assert re.search(r"\b(?:hidden|inert)\b", source), f"{name} must hide and deactivate non-current panels"
        if name == "generation":
            # Back is always secondary; Continue and the real submit are
            # mutually exclusive primaries at the step boundary.
            assert '"btn btn-secondary ce-v4-generation-guided__back"' in source
            assert re.search(r"next\.hidden\s*=\s*index\s*===\s*STEPS\.length\s*-\s*1", source)
            assert re.search(r"submit\.hidden\s*=\s*index\s*!==\s*STEPS\.length\s*-\s*1", source)
            assert 'node.id === "real-generation-confirmation"' in source
            mode_start = source.index('node.id === "generation-draft-status"')
            mode_end = source.index(') return "mode";', mode_start)
            assert "real_spend_confirmation" not in source[mode_start:mode_end]
        else:
            assert 'data-primary-action", "true"' in source or 'data-primary-action="true"' in source
            assert re.search(
                r"(?:primary[^\n]{0,100}(?:length|slice|index)|(?:length|index)[^\n]{0,100}primary)",
                source,
                re.IGNORECASE,
            ), f"{name} must enforce one primary action in the current step"


def test_finder_uses_one_surface_for_list_preview_context_actions_and_trash() -> None:
    assert re.search(
        r"workspace-board__layout[^{}]*\{[^{}]*grid-template-columns:\s*minmax\([^;]+\)\s+minmax\([^;]+\)\s*!important",
        FINDER_CSS,
        flags=re.DOTALL,
    )
    drawer_rule = next(
        body for selector, body in _css_rules(FINDER_CSS)
        if selector.strip() == "body.ce-v4-finder-route .workspace-board__drawer"
    )
    assert "display: none !important" in drawer_rule
    assert "is-quicklook-inline" in FINDER_CSS
    assert "handleBoardItemSelection" in FINDER
    assert "openSelected: (control = null) =>" in FINDER
    assert "return openQuickLook(selectedCard());" in FINDER
    assert 'if (action === "finder-quicklook")' in APP
    assert "void window.ContentEngineFinderV4?.openSelected?.(control)" in APP
    assert "void openQuickLook(current)" in FINDER
    assert "else openCanonicalCard(current)" in FINDER
    assert 'document.body.dataset.ceV4FinderMode === "organize"' in CONTEXT_TRASH
    for action in ("Переместить в папку", "Переместить в Корзину"):
        assert action in CONTEXT_TRASH


def test_review_decision_hands_the_user_to_the_real_next_stage() -> None:
    decision = _function(APP, "async function submitContentReviewDecision(")
    assert re.search(r'resolvedDecision\s*===\s*"needs_changes"[\s\S]+?flowHandoff\(', decision)
    assert "const freshFlow = await loadProjectFlow({ silent: true, force: true })" in decision
    assert "const exactNext = exactProjectNextActionRoute(freshFlow, projectId)" in decision
    assert 'exactNext.startsWith("/workspace/generation?")' in decision
    assert re.search(r'resolvedDecision\s*===\s*"approved"[\s\S]+?flowHandoff\(', decision)
    assert "/workspace/placement?view=next&placement=" in decision
    assert "content_review_exact_placement_missing" in decision

    progress = _function(CORE, "function syncProjectProgress()")
    for route in ("/workspace/board", "/workspace/generation", "/workspace/review", "/workspace/placement", "/workspace/stats"):
        assert route in CORE
    assert "href" in progress and "aria-current" in progress


def test_mobile_menubar_keeps_search_without_horizontal_page_overflow() -> None:
    mobile = CORE_CSS[CORE_CSS.index("@media (max-width: 680px)") :]
    assert re.search(
        r"\.ce-v4-menubar\s*\{[^{}]*grid-template-columns:\s*minmax\(104px,\s*auto\)\s+minmax\(88px,\s*1fr\)\s+auto",
        mobile,
        flags=re.DOTALL,
    )
    assert re.search(r"\.ce-v4-menubar__search\s*\{[^{}]*min-width:\s*0", mobile, flags=re.DOTALL)
    assert "[data-ce-v4-refresh]" in mobile
    assert "[data-ce-v4-fullscreen]" in mobile
    assert re.search(r"\.home-project-grid\s*\{[^{}]*grid-template-columns:\s*1fr", mobile, flags=re.DOTALL)
