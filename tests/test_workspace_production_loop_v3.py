from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
MY_WORK = (APP_DIR / "my-work-view.js").read_text(encoding="utf-8")
SCRIPT_NAMES = (
    "workspace-publishing-v3.js",
    "workspace-work-stage-v3.js",
    "workspace-results-v3.js",
    "workspace-payout-ledger-v3.js",
)
CSS_NAMES = (
    "workspace-production-base-v3.css",
    "workspace-publishing-v3.css",
    "workspace-work-stage-v3.css",
    "workspace-results-ledger-v3.css",
)
SCRIPTS = [(APP_DIR / name).read_text(encoding="utf-8") for name in SCRIPT_NAMES]
CSS_PARTS = [(APP_DIR / name).read_text(encoding="utf-8") for name in CSS_NAMES]
SCRIPT = "\n".join(SCRIPTS)
CSS = "\n".join(CSS_PARTS)


def test_production_assets_load_after_v3_core() -> None:
    for name in CSS_NAMES:
        assert f'./{name}?v=20260731.1' in INDEX
    for name in SCRIPT_NAMES:
        assert f'./{name}?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-os-v3-core-b.js') < INDEX.index('./workspace-publishing-v3.js')
    assert INDEX.index('./workspace-payout-ledger-v3.js') < INDEX.index('./workspace-collaboration-v3.js')


def test_existing_business_controls_remain_in_application() -> None:
    for marker in (
        'class="placement-list"',
        'class="card placement-card"',
        'class="task-list"',
        'class="card task-card"',
        'id="manual-metric-form"',
        'function renderPayoutsSection',
    ):
        assert marker in APP
    for marker in (
        'class="page-wrap my-work-page"',
        'class="my-work-queue"',
        'data-work-item-action-required',
        'data-work-item-blocker',
    ):
        assert marker in MY_WORK


def test_publishing_stage_results_and_ledger_are_present() -> None:
    for marker in (
        'publishing-os-window',
        'publishing-os-preview',
        'publishing-os-step-dock',
        'data-publishing-panel',
        'enableSplit(card, preview, work',
        'СЕЙЧАС',
        'ЖДУ',
        'ДАЛЬШЕ',
        'production-stage-focus',
        'results-story-card',
        'payout-ledger-window',
        'От задачи до выплаты',
    ):
        assert marker in SCRIPT


def test_production_adapters_do_not_call_transport_or_clone_forms() -> None:
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT
    assert "cloneNode" not in SCRIPT


def test_production_loop_is_responsive_and_motion_safe() -> None:
    for marker in (
        'body.contentengine-publishing-os-open',
        '.publishing-os-window',
        '.production-stage-manager',
        '.results-story-window',
        '.payout-ledger-window',
        '@media (max-width: 900px)',
        '@media (max-width: 620px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_production_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    for name in SCRIPT_NAMES:
        subprocess.run(
            [node, "--check", str(APP_DIR / name)],
            check=True,
            capture_output=True,
            text=True,
        )


def test_production_css_is_balanced() -> None:
    for css in CSS_PARTS:
        assert css.count("{") == css.count("}")
