from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
GUARD = (APP / "workspace-os-v4-surface-guard.js").read_text(encoding="utf-8")


def test_surface_guard_loads_after_the_core_and_continuity_polish() -> None:
    for marker in (
        'workspace-os-v4.js?v=${BUILD}',
        'workspace-os-v4-polish.js?v=${BUILD}',
        'workspace-os-v4-surface-guard.js?v=${BUILD}',
    ):
        assert marker in LOADER
    assert LOADER.index('workspace-os-v4.js?v=${BUILD}') < LOADER.index('workspace-os-v4-polish.js?v=${BUILD}')
    assert LOADER.index('workspace-os-v4-polish.js?v=${BUILD}') < LOADER.index('workspace-os-v4-surface-guard.js?v=${BUILD}')


def test_surface_guard_preserves_local_route_tabs_without_business_actions() -> None:
    for marker in (
        '.generation-os-topbar',
        '.tasks-desk-topbar',
        '.publishing-os-topbar',
        '.results-os-topbar',
        '.academy-v2-topbar',
        'data.ceV4SurfaceHost = "true"',
        'ce-v4-single-surface',
    ):
        assert marker in GUARD
    for forbidden in (
        'fetch(',
        'XMLHttpRequest',
        'requestSubmit',
        'cloneNode',
        'innerHTML',
        'data-action="transition-task"',
    ):
        assert forbidden not in GUARD


def test_surface_guard_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-surface-guard.js")],
        check=True,
        capture_output=True,
        text=True,
    )
