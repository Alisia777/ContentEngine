from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP_INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
ROOT_INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-build-guard.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-build-guard.css").read_text(encoding="utf-8")
MANIFEST = json.loads((APP_DIR / "build.json").read_text(encoding="utf-8"))


def test_build_id_is_consistent_across_entrypoints() -> None:
    build_id = MANIFEST["id"]
    assert build_id == "20260731.os3.1"
    assert f'content="{build_id}"' in APP_INDEX
    assert f'content="{build_id}"' in ROOT_INDEX
    assert f'const CURRENT_BUILD = "{build_id}"' in SCRIPT
    assert MANIFEST["label"] == "ContentEngine OS v3 · Full Production Loop"


def test_build_guard_assets_load_last_and_bust_the_full_os_cache() -> None:
    assert './workspace-build-guard.css?v=20260731.1' in APP_INDEX
    assert './workspace-build-guard.js?v=20260731.1' in APP_INDEX
    assert APP_INDEX.index('./workspace-generation-os.css') < APP_INDEX.index('./workspace-os-v3-core.css')
    assert APP_INDEX.index('./workspace-os-v3-finish.css') < APP_INDEX.index('./workspace-build-guard.css')
    assert APP_INDEX.index('./workspace-academy-lab-v3.js') < APP_INDEX.index('./workspace-build-guard.js')
    for marker in (
        './workspace-os-v3-core.js?v=20260731.1',
        './workspace-publishing-os.js?v=20260731.1',
        './workspace-work-stage-manager.js?v=20260731.1',
        './workspace-results-ledger.js?v=20260731.1',
        './workspace-academy-lab-v3.js?v=20260731.1',
    ):
        assert marker in APP_INDEX


def test_guard_checks_only_the_same_origin_static_manifest() -> None:
    for marker in (
        'new URL("./build.json", import.meta.url)',
        'cache: "no-store"',
        'credentials: "same-origin"',
        'url.searchParams.set("t", String(Date.now()))',
        'url.searchParams.set("build", id)',
        'window.location.replace(url.toString())',
        'window.CONTENTENGINE_BUILD',
    ):
        assert marker in SCRIPT
    assert "supabase" not in SCRIPT.lower()
    assert "/api/" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert "localStorage" not in SCRIPT
    assert "sessionStorage" not in SCRIPT


def test_build_guard_has_accessible_update_and_manual_status() -> None:
    for marker in (
        'role", "status"',
        'aria-live", "polite"',
        'Рабочее место обновилось',
        'открытые серверные задачи продолжат работу',
        'ContentEngineBuildGuard',
        '.ce-build-update',
        '.ce-build-pill',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in SCRIPT or marker in CSS


def test_build_guard_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-build-guard.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_build_guard_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
