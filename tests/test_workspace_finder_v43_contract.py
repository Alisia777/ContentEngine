from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
SCRIPT = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
STYLES = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")
CONTEXT = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
INLINE_FIXTURE = ROOT / "tests" / "fixtures" / "workspace_finder_inline_v45_harness.html"


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_finder_uses_the_stable_desktop_viewport() -> None:
    board = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board {",
        "body.ce-v4-finder-route .workspace-board >",
    )
    assert "height: 100%" in board
    assert "min-height: 0" in board
    assert "position: relative" in board
    assert "grid-template-rows: minmax(0, 1fr)" in board
    assert "overflow: hidden" in board
    assert "100dvh" not in STYLES


def test_finder_sorts_and_filters_loaded_cards_by_creation_date() -> None:
    toolbar = _between(SCRIPT, "function buildToolbar()", "function buildFolderSearch()")
    date_contract = _between(SCRIPT, "function sortCards(value)", "function filterFolders(query)")
    status = _between(SCRIPT, "function syncFinderControlStatus()", "function applyMode()")
    for marker in (
        '["created_desc", "Сначала новые"]',
        '["created_asc", "Сначала старые"]',
        'create("select", "ce-v4-finder-date-filter")',
        '["all", "Все даты"]',
        '["today", "Сегодня"]',
        '["7d", "7 дней"]',
        '["30d", "30 дней"]',
        'dateFilter.setAttribute("aria-label", "Период среди загруженных объектов")',
    ):
        assert marker in toolbar
    for marker in (
        "finderCardCreatedTimestamp(left)",
        "finderCardCreatedTimestamp(right)",
        'normalizedValue === "created_desc"',
        "if (leftCreatedAt === null && rightCreatedAt !== null) return 1",
        "function dateFilterCutoff(value, now = new Date())",
        "function applyDateFilter(value)",
        "card.hidden = !matches",
        "if (!visibleKeys.has(key)) runtime.selectedKeys.delete(key)",
    ):
        assert marker in date_contract
    assert "загруженных" in status


def test_finder_contains_the_desktop_list_and_restores_document_scroll_on_mobile() -> None:
    layout = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board__layout {",
        "body.ce-v4-finder-route .workspace-board__layout > *",
    )
    content = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board__content {",
        ".ce-v4-finder-toolbar {",
    )
    grid = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board__grid {",
        'body.ce-v4-finder-route .workspace-board[data-ce-v4-finder-view="list"]',
    )
    mobile = _between(
        STYLES,
        "@container ce-v4-finder-host (max-width: 760px)",
        "@container ce-v4-finder-host (max-width: 480px)",
    )
    assert "height: 100%" in layout and "overflow: hidden" in layout
    for marker in ("display: flex", "height: 100% !important", "flex-direction: column", "overflow: hidden"):
        assert marker in content
    for marker in ("flex: 1 1 0", "overflow-y: auto", "overscroll-behavior: contain"):
        assert marker in grid
    for marker in (
        "height: auto",
        "grid-template-rows: auto",
        "overflow: visible",
        "flex: none",
        "overflow-y: visible",
    ):
        assert marker in mobile
    assert ".workspace-board__item-preview video.workspace-board__preview-frame" in STYLES
    assert "max-width: 100%" in STYLES
    assert "max-height: 100%" in STYLES


def test_wide_finder_keeps_folders_collection_and_inspector_visible_together() -> None:
    layout = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board__layout {",
        "body.ce-v4-finder-route .workspace-board__layout > *",
    )
    drawer = _between(
        STYLES,
        "body.ce-v4-finder-route .workspace-board__drawer {\n  position: sticky",
        "body.ce-v4-finder-route .workspace-board__drawer h2",
    )
    assert "minmax(220px, 260px) minmax(560px, 1fr) minmax(286px, 340px)" in layout
    assert "grid-column: 3" in drawer
    assert "position: sticky" in drawer
    assert "display: grid" in drawer
    assert "word-break: normal" in STYLES
    assert "overflow-wrap: break-word" in STYLES
    assert "overflow-wrap: anywhere" not in drawer


def test_finder_text_and_controls_remain_readable_and_clickable() -> None:
    rem_sizes = [
        float(value)
        for value in re.findall(
            r"(?:font-size|font)\s*:[^;{}]*?(\d*\.\d+)rem",
            STYLES,
        )
    ]
    assert rem_sizes
    assert min(rem_sizes) >= 0.75
    for marker in (
        "min-height: 44px",
        "font-size: 14px",
        "font-size: 13px",
        "font-size: 12px",
        ".ce-v4-quicklook-inline__controls button",
    ):
        assert marker in STYLES


def test_finder_toolbar_commands_navigate_explicitly_and_report_empty_view_state() -> None:
    toolbar = _between(SCRIPT, "function buildToolbar()", "function buildFolderSearch()")
    app_script = (APP / "app.js").read_text(encoding="utf-8")
    status = _between(SCRIPT, "function syncFinderControlStatus()", "function applyMode()")
    for marker in (
        'browse.dataset.ceV4FinderMode = "browse"',
        'organize.dataset.ceV4FinderMode = "organize"',
        'browse.dataset.action = "finder-mode"',
        'organize.dataset.action = "finder-mode"',
        'list.dataset.action = "finder-view"',
        'upload.dataset.action = "finder-upload"',
        'upload.dataset.ceV4FinderUpload = "true"',
    ):
        assert marker in toolbar
    assert "setView: (value, control = null)" in SCRIPT
    assert "window.requestAnimationFrame(settle)" in SCRIPT
    assert 'window.ContentEngineFinderV4?.setView?.(control.dataset.ceV4FinderView, control)' in app_script
    assert 'if (action === "finder-mode")' in app_script
    assert 'if (action === "finder-upload")' in app_script
    assert 'controlStatus.setAttribute("aria-live", "polite")' in toolbar
    assert 'q(".workspace-board__empty", runtime.board)' in status
    assert "Организация включена" in status
    assert "ce-v4-finder-control-status" in STYLES
    assert "ce-v4-finder-empty-mode" in STYLES
    assert '.workspace-board[data-ce-v4-finder-view="list"] [data-ce-v4-finder-view="list"]' in STYLES


def test_mobile_sidebar_has_an_accessible_toggle_and_close_contract() -> None:
    for marker in (
        'create("button", "ce-v4-finder-sidebar-toggle"',
        'toggle.setAttribute("aria-controls", sidebar.id)',
        'toggle.setAttribute("aria-expanded", "false")',
        'sidebar.setAttribute("role", "navigation")',
        'sidebar.setAttribute("aria-hidden", String(!next))',
        'runtime.board?.classList.toggle("is-sidebar-open", next)',
        'runtime.board.addEventListener("click", handleBoardFolderSelection)',
        'event.key === "Escape" && runtime.sidebarOpen',
    ):
        assert marker in SCRIPT
    for forbidden in (
        "sidebar.inert",
        'create("button", "ce-v4-finder-sidebar-backdrop")',
        "ce-v4-finder-sidebar-backdrop",
    ):
        assert forbidden not in SCRIPT
    for marker in (
        ".ce-v4-finder-sidebar-toggle",
        ".ce-v4-finder-sidebar-close",
        ".workspace-board__sidebar.is-open",
        ".workspace-board.is-sidebar-open",
        "position: static",
        "display: none",
        "display: flex",
    ):
        assert marker in STYLES
    assert "ce-v4-finder-sidebar-backdrop" not in STYLES


def test_tablet_detail_replaces_the_central_list_and_returns_inline() -> None:
    sync_detail = _between(SCRIPT, "function syncInlineDetail()", "function buildToolbar()")
    tablet = _between(
        STYLES,
        "@container ce-v4-finder-host (max-width: 1080px)",
        "@container ce-v4-finder-host (max-width: 760px)",
    )
    for marker in (
        'runtime.board.classList.toggle("is-detail-inline", active)',
        'create("header", "ce-v4-finder-detail-bar")',
        'create("button", "ce-v4-finder-detail-back"',
        'q(\'[data-action="close-workspace-item"]\', drawer)?.click()',
    ):
        assert marker in sync_detail
    for marker in (
        ".workspace-board.is-detail-inline",
        "position: static !important",
        "display: grid !important",
        ".workspace-board__content) { display: none !important; }",
        ".ce-v4-finder-detail-bar { display: grid; }",
    ):
        assert marker in tablet
    assert ".workspace-board__drawer { position: absolute" not in tablet


def test_finder_inline_surfaces_do_not_overflow_a_320px_viewport() -> None:
    for marker in (
        "container-name: ce-v4-finder-host",
        "container-type: inline-size",
        "width: 100%",
        "max-width: 100%",
        ".workspace-board__layout > * { max-width: 100%; }",
        ".ce-v4-finder-toolbar__controls { overflow-x: auto; }",
        "@container ce-v4-finder-host (max-width: 1180px)",
        "overflow-wrap: anywhere",
        "@container ce-v4-finder-host (max-width: 480px)",
        "grid-template-columns: 1fr !important",
    ):
        assert marker in STYLES
    assert 'id="workspace-content"' in INLINE_FIXTURE.read_text(encoding="utf-8")


def test_finder_toolbar_responds_to_the_real_centre_pane_width() -> None:
    assert "container-name: ce-v4-finder-content" in STYLES
    assert "@container ce-v4-finder-content (max-width: 980px)" in STYLES
    centre_query = _between(
        STYLES,
        "@container ce-v4-finder-content (max-width: 980px)",
        ".ce-v4-finder-sort,",
    )
    assert "grid-template-columns: minmax(0, 1fr)" in centre_query
    assert ".ce-v4-finder-toolbar__title" in centre_query
    assert "width: 100%" in centre_query
    assert ".ce-v4-finder-toolbar__controls" in centre_query
    assert "overflow-x: auto" in centre_query


@pytest.mark.parametrize("width", [320, 760])
def test_finder_inline_surfaces_have_no_runtime_horizontal_overflow(width: int) -> None:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for viewport QA")
    with tempfile.TemporaryDirectory(prefix="ce-finder-v45-") as profile:
        result = subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--allow-file-access-from-files",
                "--virtual-time-budget=1000",
                f"--window-size={width},568",
                f"--user-data-dir={profile}",
                "--dump-dom",
                INLINE_FIXTURE.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    assert 'data-passed="true"' in result.stdout


def test_wide_quick_look_stays_in_the_inspector_with_safari_safe_motion() -> None:
    open_quick_look = _between(
        SCRIPT,
        "async function openQuickLook(",
        "function closeQuickLook(",
    )
    close_quick_look = _between(
        SCRIPT,
        "function closeQuickLook(",
        "function navigateQuickLook(",
    )
    assert 'drawer.closest(".workspace-board")' in open_quick_look
    assert 'board.classList.add("is-quicklook-inline")' in open_quick_look
    assert 'drawer.classList.add("ce-v4-quicklook-inline")' in open_quick_look
    assert 'board.classList.remove("is-detail-inline")' in open_quick_look
    assert "duration: 190" in open_quick_look
    assert 'transform: "translate3d(0, 8px, 0)"' in open_quick_look
    assert "scale(" not in open_quick_look
    assert "dispatchEvent" not in close_quick_look
    assert "aria-modal" not in SCRIPT
    assert "ce-v4-quicklook-backdrop" not in SCRIPT
    assert ".ce-v4-quicklook-backdrop" not in STYLES
    wide_quick_look = _between(
        STYLES,
        "/* On wide surfaces Quick Look stays in the inspector",
        "@container ce-v4-finder-host (max-width: 1180px)",
    )
    for marker in (
        "grid-template-columns: minmax(220px, 260px) minmax(560px, 1fr) minmax(320px, 390px)",
        ".workspace-board.is-quicklook-inline .workspace-board__sidebar",
        "display: flex !important",
        ".workspace-board.is-quicklook-inline .workspace-board__content",
        "display: flex !important",
        ".workspace-board__drawer.ce-v4-quicklook-inline",
        "grid-column: 3",
        "position: sticky !important",
    ):
        assert marker in wide_quick_look
    assert ":is(.workspace-board__sidebar, .workspace-board__content) { display: none" not in wide_quick_look


def test_finder_separates_selection_quick_look_and_canonical_open_commands() -> None:
    for marker in (
        "window.ContentEngineFinderV4.openQuickLook(entity.node)",
        'runtime.board.addEventListener("dblclick", handleBoardDoubleClick)',
        "openCanonicalCard(card);",
        'if (event.key === " ") void openQuickLook(current);',
        "else openCanonicalCard(current);",
        'runtime.board.addEventListener("click", handleBoardItemSelection)',
    ):
        assert marker in CONTEXT or marker in SCRIPT
    double_click = _between(
        SCRIPT,
        "function handleBoardDoubleClick(",
        "function handleBoardSelectionClick(",
    )
    assert "openCanonicalCard(card)" in double_click
    assert "openQuickLook(card)" not in double_click


def test_finder_assets_parse_and_balance() -> None:
    assert STYLES.count("{") == STYLES.count("}")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-finder.js")],
        check=True,
        capture_output=True,
        text=True,
    )
