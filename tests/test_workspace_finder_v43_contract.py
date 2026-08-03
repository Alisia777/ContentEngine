from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
SCRIPT = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
STYLES = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")


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
        ".ce-v4-quicklook__close { display: grid; width: 42px; height: 42px",
    ):
        assert marker in STYLES


def test_mobile_sidebar_has_an_accessible_toggle_and_close_contract() -> None:
    for marker in (
        'create("button", "ce-v4-finder-sidebar-toggle"',
        'toggle.setAttribute("aria-controls", sidebar.id)',
        'toggle.setAttribute("aria-expanded", "false")',
        'sidebar.setAttribute("role", "navigation")',
        'sidebar.setAttribute("aria-hidden", String(!next))',
        "sidebar.inert = !next",
        'create("button", "ce-v4-finder-sidebar-backdrop")',
        'event.key === "Escape" && runtime.sidebarOpen',
    ):
        assert marker in SCRIPT
    for marker in (
        ".ce-v4-finder-sidebar-toggle",
        ".ce-v4-finder-sidebar-close",
        ".ce-v4-finder-sidebar-backdrop",
        ".workspace-board__sidebar.is-open",
        ".workspace-board.is-sidebar-open",
        "transform: translate3d(0, 0, 0)",
    ):
        assert marker in STYLES


def test_quick_look_is_coordinated_and_uses_safari_safe_motion() -> None:
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
    assert 'document.dispatchEvent(new CustomEvent("contentengine:v4-close-transients"' in open_quick_look
    assert "detail: Object.freeze({ except: TRANSIENT_NAME })" in open_quick_look
    assert 'document.addEventListener("contentengine:v4-close-transients"' in SCRIPT
    assert "duration: 190" in open_quick_look
    assert 'transform: "translate3d(0, 8px, 0)"' in open_quick_look
    assert "scale(" not in open_quick_look
    assert "dispatchEvent" not in close_quick_look

    backdrop = _between(STYLES, ".ce-v4-quicklook-backdrop {", ".ce-v4-quicklook {")
    assert "backdrop-filter: none" in backdrop
    assert "-webkit-backdrop-filter: none" in backdrop
    assert "blur(" not in backdrop


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
