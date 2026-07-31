from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPTS = [
    (APP_DIR / "workspace-os-v3-core-a.js").read_text(encoding="utf-8"),
    (APP_DIR / "workspace-os-v3-core-b.js").read_text(encoding="utf-8"),
]
SCRIPT = "\n".join(SCRIPTS)
CSS_PARTS = [
    (APP_DIR / "workspace-os-v3-core-1.css").read_text(encoding="utf-8"),
    (APP_DIR / "workspace-os-v3-core-2.css").read_text(encoding="utf-8"),
    (APP_DIR / "workspace-os-v3-core-3.css").read_text(encoding="utf-8"),
]
CSS = "\n".join(CSS_PARTS)


def test_os_v3_core_assets_load_after_existing_os_and_before_adapters() -> None:
    for marker in (
        './workspace-os-v3-core-1.css?v=20260731.1',
        './workspace-os-v3-core-2.css?v=20260731.1',
        './workspace-os-v3-core-3.css?v=20260731.1',
        './workspace-os-v3-core-a.js?v=20260731.1',
        './workspace-os-v3-core-b.js?v=20260731.1',
    ):
        assert marker in INDEX
    assert INDEX.index('./workspace-media-finder.css') < INDEX.index('./workspace-os-v3-core-1.css')
    assert INDEX.index('./workspace-os-v3-core-1.css') < INDEX.index('./workspace-production-base-v3.css')
    assert INDEX.index('./workspace-media-finder.js') < INDEX.index('./workspace-os-v3-core-a.js')
    assert INDEX.index('./workspace-os-v3-core-a.js') < INDEX.index('./workspace-os-v3-core-b.js')
    assert INDEX.index('./workspace-os-v3-core-b.js') < INDEX.index('./workspace-publishing-v3.js')


def test_os_v3_core_provides_shared_desktop_primitives() -> None:
    for marker in (
        'window.ContentEngineOSV3 = api',
        'openSpotlight',
        'openObjectCapsule',
        'enableSplit',
        'pushUndo',
        'ce-v3-mission-attention',
        'ce-v3-stage',
        'BroadcastChannel("contentengine-os-v3-presence")',
        'Этот объект открыт в другой вкладке',
        'event.metaKey || event.ctrlKey',
        'event.key.toLowerCase() === "k"',
    ):
        assert marker in SCRIPT


def test_os_v3_core_is_presentation_only() -> None:
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT
    assert "service_role" not in SCRIPT


def test_os_v3_core_has_responsive_and_accessible_motion() -> None:
    for marker in (
        '.ce-v3-spotlight',
        '.ce-v3-capsule',
        '.ce-v3-stage',
        '.ce-v3-split__handle',
        '.ce-v3-undo',
        '@media (max-width: 1100px)',
        '@media (max-width: 760px)',
        '@media (prefers-reduced-motion: reduce)',
        'animation: none !important',
    ):
        assert marker in CSS


def test_os_v3_core_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    for filename in ("workspace-os-v3-core-a.js", "workspace-os-v3-core-b.js"):
        subprocess.run(
            [node, "--check", str(APP_DIR / filename)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_os_v3_core_css_is_balanced() -> None:
    for css in CSS_PARTS:
        assert css.count("{") == css.count("}")
