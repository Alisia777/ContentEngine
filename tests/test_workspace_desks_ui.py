from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
DESKS_JS = (APP_DIR / "workspace-desks-v2.js").read_text(encoding="utf-8")
DESKS_CSS = (APP_DIR / "workspace-desks.css").read_text(encoding="utf-8")
RESPONSIVE_CSS = (APP_DIR / "workspace-desks-responsive.css").read_text(encoding="utf-8")
FIXES_CSS = (APP_DIR / "workspace-desks-fixes.css").read_text(encoding="utf-8")


def test_workspace_desktop_assets_are_loaded_after_the_base_application() -> None:
    for marker in (
        './workspace-desks.css?v=20260730.1',
        './workspace-desks-responsive.css?v=20260730.1',
        './workspace-desks-fixes.css?v=20260730.1',
        './workspace-desks-v2.js?v=20260730.2',
    ):
        assert marker in INDEX

    assert INDEX.index("./interface-system.css") < INDEX.index("./workspace-desks.css")
    assert INDEX.index("./app.js") < INDEX.index("./workspace-desks-v2.js")
    assert './workspace-desks.js?v=' not in INDEX


def test_workspace_controller_is_progressive_and_never_calls_the_backend() -> None:
    for marker in (
        'const STATE_KEY = "contentengine.workspace-desks.v2"',
        'new MutationObserver(scheduleMount)',
        'shell.classList.add("workspace-desks-enabled")',
        'bar.dataset.deckSignature === signature',
        'new AbortController()',
    ):
        assert marker in DESKS_JS

    assert "fetch(" not in DESKS_JS
    assert "XMLHttpRequest" not in DESKS_JS
    assert ".api." not in DESKS_JS


def test_workspace_desktops_support_mission_control_and_one_task_focus() -> None:
    for marker in (
        "workspace-overview-backdrop",
        "Mission Control · кабинет",
        "data-overview-route",
        "data-overview-focus-id",
        "workspace-task-focused",
        "data-workspace-focus-card",
        "Развернуть главную задачу на весь стол",
    ):
        assert marker in DESKS_JS or marker in DESKS_CSS


def test_workspace_desktops_preserve_context_and_have_fast_navigation() -> None:
    for marker in (
        "runtime.stored.scroll[route]",
        "restoreScroll(route)",
        "window.scrollTo({ top: value",
        "event.altKey && event.shiftKey && event.key === \"ArrowLeft\"",
        "event.altKey && event.shiftKey && event.key === \"ArrowRight\"",
        "event.pointerType !== \"touch\"",
        "Math.abs(dx) >= 82",
        "event.metaKey || event.ctrlKey",
    ):
        assert marker in DESKS_JS


def test_workspace_desktops_are_large_responsive_and_accessible() -> None:
    for marker in (
        ".workspace-deckbar",
        ".workspace-deck-current",
        ".workspace-overview__grid",
        ".workspace-task-focused",
        "font-size: clamp(2.65rem, 4.2vw, 5.4rem)",
        "@media (max-width: 820px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation-duration: 0.01ms !important",
    ):
        assert marker in DESKS_CSS or marker in RESPONSIVE_CSS

    assert "left: calc(var(--sidebar-width, 252px) + 22px) !important" in FIXES_CSS


def test_workspace_desktop_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-desks-v2.js")],
        check=True,
        capture_output=True,
        text=True,
    )
