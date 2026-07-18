from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"


def _text(name: str) -> str:
    return (APP_DIR / name).read_text(encoding="utf-8")


def test_boot_watchdog_precedes_module_and_has_independent_deadlines() -> None:
    index = _text("index.html")
    watchdog = _text("boot-watchdog.js")
    app = _text("app.js")

    assert index.index("boot-watchdog.js") < index.index('type="module"')
    assert "MODULE_DEADLINE_MS" in watchdog
    assert "APP_DEADLINE_MS" in watchdog
    assert "data-boot-reload" in watchdog
    assert "CONTENTENGINE_BOOT_WATCHDOG?.moduleLoaded()" in app
    assert "CONTENTENGINE_BOOT_WATCHDOG?.ready()" in app
    assert "import(SUPABASE_SDK_URL)" in app


def test_mobile_auth_is_form_first_and_keyboard_focus_is_visible() -> None:
    styles = _text("styles.css")
    mobile = styles[styles.index("@media (max-width: 820px)") :]

    assert "min-height: 100svh" in mobile
    assert "order: -1" in mobile
    assert "input:focus-visible" in styles
    assert "outline: 3px solid #315e91" in styles


def test_notification_dialog_is_inert_and_keyboard_trapped() -> None:
    app = _text("app.js")
    view = _text("my-work-view.js")

    assert 'role="dialog" aria-modal="true"' in view
    assert 'tabindex="-1"' in view
    assert 'toggleAttribute("inert", state.myWork.notificationsOpen)' in app
    assert 'event.key === "Tab" && state.myWork.notificationsOpen' in app


def test_workspace_markup_keeps_the_initial_dom_window_bounded() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")

    module_source = _text("workspace-board-view.js")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(module_source, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import { workspaceBoardMarkup } from './subject.mjs';\n"
            "const items = Array.from({ length: 1000 }, (_, index) => ({\n"
            "  id: `item-${index}`, entity_type: 'media', title: `Item ${index}`, status: 'ready'\n"
            "}));\n"
            "const html = workspaceBoardMarkup({ items }, { visibleItemLimit: 80 });\n"
            "const cards = (html.match(/class=\"workspace-board__item /g) || []).length;\n"
            "process.stdout.write(JSON.stringify({ cards, hasMore: html.includes('show-more-workspace-items') }));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload == {"cards": 80, "hasMore": True}
