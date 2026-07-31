from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-collaboration-v3.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-collaboration-v3.css").read_text(encoding="utf-8")


def test_collaboration_assets_load_after_production_loop() -> None:
    assert './workspace-collaboration-v3.css?v=20260731.1' in INDEX
    assert './workspace-collaboration-v3.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-results-ledger-v3.css') < INDEX.index('./workspace-collaboration-v3.css')
    assert INDEX.index('./workspace-payout-ledger-v3.js') < INDEX.index('./workspace-collaboration-v3.js')


def test_collaboration_is_explicitly_local_and_non_authoritative() -> None:
    for marker in (
        'contentengine.os-v3.local-context.v1',
        'только на этом устройстве',
        'Локальная память не заменяет серверное назначение',
        'window.localStorage',
        'MAX_AGE_MS',
    ):
        assert marker in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT


def test_collaboration_has_parking_decisions_frames_handoff_and_undo() -> None:
    for marker in (
        'ЖУРНАЛ РЕШЕНИЙ',
        'КОММЕНТАРИИ К КАДРУ',
        'data-local-seek-frame',
        'video.currentTime',
        'buildHandoff',
        'Скопировать передачу',
        'pushUndo',
        'action === "park"',
    ):
        assert marker in SCRIPT


def test_collaboration_has_responsive_panel_and_reduced_motion() -> None:
    for marker in (
        '.ce-v3-local-panel',
        '.ce-v3-local-section',
        '.ce-v3-frame-list',
        '.ce-v3-handoff-preview',
        '@media (max-width: 620px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_collaboration_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-collaboration-v3.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_collaboration_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
