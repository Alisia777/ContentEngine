from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
STABILITY = (APP / "workspace-os-v4-stability.js").read_text(encoding="utf-8")
STABILITY_CSS = (APP / "workspace-os-v4-stability.css").read_text(encoding="utf-8")


def test_static_stability_layer_replaces_legacy_observer_controllers() -> None:
    for marker in (
        'workspace-os-v4-polish.css?v=${BUILD}',
        'workspace-os-v4-context-trash.css?v=${BUILD}',
        'workspace-os-v4-flow.css?v=${BUILD}',
        'workspace-os-v4-stability.css?v=${BUILD}',
        'workspace-os-v4-motion.css?v=${BUILD}',
        'workspace-os-v4.js?v=${DESKTOP_CORE_BUILD}',
    ):
        assert marker in LOADER
    assert LOADER.index('workspace-os-v4-stability.css?v=${BUILD}') < LOADER.index(
        'workspace-os-v4.js?v=${DESKTOP_CORE_BUILD}'
    )
    for retired_controller in (
        'workspace-os-v4-stability.js',
        'workspace-os-v4-polish.js',
        'workspace-os-v4-surface-guard.js',
        'workspace-os-v4-operations.js',
        'workspace-ui-bug-checkin.js',
    ):
        assert retired_controller not in LOADER


def test_stability_coordinator_reduces_local_chrome_without_business_actions() -> None:
    for marker in (
        '.generation-os-topbar',
        '.tasks-desk-topbar',
        '.publishing-os-topbar',
        '.results-os-topbar',
        '.academy-v2-topbar',
        'DUPLICATE_GLOBAL_CHROME',
        'LOCAL_DOCKS',
        'dataset.ceV4Contextbar',
        'dataset.ceV4LocalDock = "true"',
        'cancelChromeAnimations',
    ):
        assert marker in STABILITY
    for forbidden in (
        'new MutationObserver',
        'fetch(',
        'XMLHttpRequest',
        'requestSubmit',
        'cloneNode',
        'innerHTML',
        'data-action="transition-task"',
    ):
        assert forbidden not in STABILITY


def test_stability_css_prevents_menu_jitter_and_tiny_controls() -> None:
    for marker in (
        '--ce-v4-control-height: 44px',
        '--ce-v4-font-control: 14px',
        '--ce-v4-scale: 1 !important',
        '--ce-v4-lift: 0px !important',
        '[data-ce-v4-contextbar="secondary"]',
        '[data-ce-v4-connected-menu="true"]',
        '[data-ce-v4-local-dock="true"]',
        'view-transition-name: none',
        'scrollbar-gutter: stable',
    ):
        assert marker in STABILITY_CSS


def test_stability_coordinator_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this environment")
    subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-stability.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_stability_stylesheet_is_balanced() -> None:
    assert STABILITY_CSS.count("{") == STABILITY_CSS.count("}")
