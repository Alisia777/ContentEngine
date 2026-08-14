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
    assert "100dvh" not in STYLES


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
        "overflow-wrap: anywhere",
        "@container ce-v4-finder-host (max-width: 480px)",
        "grid-template-columns: 1fr !important",
    ):
        assert marker in STYLES
    assert 'id="workspace-content"' in INLINE_FIXTURE.read_text(encoding="utf-8")


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


def test_quick_look_replaces_finder_content_inline_with_safari_safe_motion() -> None:
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
    assert ".workspace-board.is-quicklook-inline" in STYLES


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
