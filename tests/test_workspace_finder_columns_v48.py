from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
FINDER = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")
FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_finder_columns_v48_harness.html"
).read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_finder_columns_uses_the_existing_selection_and_open_owner() -> None:
    assert 'const FINDER_VIEWS = new Set(["grid", "list", "columns"])' in FINDER
    toolbar = _between(FINDER, "function buildToolbar()", "\nfunction buildFolderSearch()")
    assert 'columns.dataset.ceV4FinderView = "columns"' in toolbar
    assert toolbar.count('dataset.action = "finder-view"') == 3
    assert 'columns.textContent = "Колонки"' in toolbar
    assert 'quickLook.dataset.ceV4FinderQuicklook = "true"' in toolbar
    assert "setView: (value, control = null)" in FINDER
    assert "rememberFinderView(value)" in FINDER

    selection = _between(FINDER, "function selectCard(", "\nfunction finderCardTitle(")
    assert "syncSelectionDom();" in selection
    assert "replaceChildren" not in selection
    assert "requestApplicationOpen" not in selection

    columns = _between(FINDER, "function ensureColumnsProjection()", "\nfunction refreshFinderBoard()")
    assert 'q(".workspace-board__grid", runtime.board)' in columns
    assert 'data-ce-v4-finder-column' in columns
    assert 'setAttribute("aria-hidden", "true")' in columns
    assert "grid.append(hierarchy, preview)" in columns
    assert ".cloneNode" not in columns
    assert ".click()" not in columns
    assert "getApi" not in columns
    assert "fetch(" not in columns

    canonical_open = _between(FINDER, "function requestApplicationOpen(", "\nfunction openCanonicalCard(")
    assert canonical_open.count("trigger.click()") == 1
    assert "allowApplicationOpenKey" in canonical_open
    assert FINDER.count("function handleBoardItemSelection(") == 1
    assert FINDER.count("function handleBoardDoubleClick(") == 1


def test_columns_selection_updates_read_only_projection_without_card_rerender() -> None:
    sync_columns = _between(FINDER, "function syncColumnsProjection()", "\nfunction refreshFinderBoard()")
    assert "const card = selectedCard();" in sync_columns
    assert "hierarchy.replaceChildren(hierarchyPanel)" in sync_columns
    assert "preview.replaceChildren(previewPanel)" in sync_columns
    assert "card.replaceChildren" not in sync_columns
    assert "cards().forEach" not in sync_columns
    assert 'create("button"' not in sync_columns
    assert 'create("form"' not in sync_columns
    assert 'create("input"' not in sync_columns

    selection_sync = _between(FINDER, "function syncSelectionDom()", "\nfunction clearSelection(")
    assert "syncColumnsProjection();" in selection_sync
    assert selection_sync.index("cards().forEach") < selection_sync.index("syncColumnsProjection();")

    for expected in (
        "singleClickDoesNotOpen",
        "doubleClickOpensOnce",
        "enterOpensOnce",
        "spaceOpensQuickLookOnce",
        "selectionUpdatesPreview",
        "cardIdentityAfterSelection",
        "noInteractiveProjectionClones",
    ):
        assert expected in FIXTURE


def test_finder_view_preference_is_project_and_folder_scoped_or_ephemeral() -> None:
    preference = _between(FINDER, "function normalizedFinderView(", "\nfunction requestApplicationOpen(")
    assert "function finderViewPreferenceKey()" in preference
    assert "PROJECT_QUERY_KEY" in preference
    assert "finderFolderId()" in preference
    assert 'if (!projectId) return ""' in preference
    assert "runtime.ephemeralView = view" in preference
    assert "window.localStorage.setItem(preferenceKey, view)" in preference
    assert "window.sessionStorage" not in preference

    read_state = _between(FINDER, "function readState()", "\nfunction remember(")
    assert "delete scopedState.view" in read_state
    assert 'window.localStorage.setItem(STATE_KEY, JSON.stringify(scopedState))' in read_state
    assert "remember({ view:" not in FINDER
    for expected in (
        "legacyGlobalViewRetired",
        "scopedInboxPreference",
        "scopedReviewPreference",
        "ephemeralDoesNotPersist",
    ):
        assert expected in FIXTURE


def test_columns_responsiveness_is_container_owned_with_internal_scroll() -> None:
    base = re.search(
        r'\.workspace-board\[data-ce-v4-finder-view="columns"\] \.workspace-board__grid\s*\{(?P<body>.*?)\n\}',
        FINDER_CSS,
        flags=re.DOTALL,
    )
    assert base
    body = base.group("body")
    assert "max-width: 100%" in body
    assert "overflow-x: auto" in body
    assert "overscroll-behavior-inline: contain" in body
    assert "scroll-snap-type: inline proximity" in body
    assert "minmax(280px, .82fr)" in body
    assert "minmax(230px, .88fr)" in body
    assert "minmax(270px, 1.1fr)" in body

    assert "@container ce-v4-finder-host (max-width: 760px)" in FINDER_CSS
    assert "@container ce-v4-finder-host (max-width: 480px)" in FINDER_CSS
    narrow = FINDER_CSS[FINDER_CSS.index("@container ce-v4-finder-host (max-width: 760px)") :]
    assert 'data-ce-v4-finder-view="columns"' in narrow
    assert "grid-template-columns: 270px 230px 270px !important" in narrow
    assert "@media (max-width: 760px)" not in FINDER_CSS
    assert "internalHorizontalScroll" in FIXTURE
    assert "noWorkspaceHorizontalOverflow" in FIXTURE


def test_finder_columns_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        return
    completed = subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-finder.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
