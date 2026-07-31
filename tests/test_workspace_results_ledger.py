from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-results-ledger.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-results-ledger.css").read_text(encoding="utf-8")


def test_results_ledger_assets_load_in_os_v3() -> None:
    assert './workspace-results-ledger.css?v=20260731.1' in INDEX
    assert './workspace-results-ledger.js?v=20260731.1' in INDEX
    assert INDEX.index('./workspace-work-stage-manager.css') < INDEX.index('./workspace-results-ledger.css')
    assert INDEX.index('./workspace-work-stage-manager.js') < INDEX.index('./workspace-results-ledger.js')


def test_native_stats_and_payout_anchors_exist() -> None:
    for marker in (
        'id="manual-metric-form"',
        'class="metrics-grid',
        'function statsTable',
        'function renderPayoutsSection',
        'function payoutsTable',
        'payout-reject-form',
        'payout-paid-form',
    ):
        assert marker in APP


def test_results_have_overview_compare_snapshot_and_history_spaces() -> None:
    for marker in (
        'data-results-ledger-panel="overview"',
        'data-results-ledger-panel="compare"',
        'data-results-ledger-panel="snapshot"',
        'data-results-ledger-panel="history"',
        'createComparison',
        'Сравнение строится только по уже сохранённым снимкам',
        'Что переносим дальше',
        'Открыть следующую генерацию',
    ):
        assert marker in SCRIPT


def test_payout_ledger_has_summary_ledger_and_actionable_issues() -> None:
    for marker in (
        'data-results-ledger-panel="summary"',
        'data-results-ledger-panel="ledger"',
        'data-results-ledger-panel="issues"',
        'payoutIssues',
        'Требуют решения',
        'штатную форму решения',
        'results-ledger-target',
    ):
        assert marker in SCRIPT or marker in CSS


def test_native_forms_and_tables_are_moved_not_reimplemented() -> None:
    for marker in (
        'overview.append(metrics)',
        'snapshot.append(snapshotCard)',
        'history.append(historyCard)',
        'append(ledgerCard)',
    ):
        assert marker in SCRIPT
    assert 'cloneNode' not in SCRIPT
    assert 'fetch(' not in SCRIPT
    assert 'XMLHttpRequest' not in SCRIPT
    assert '.api.' not in SCRIPT


def test_results_ledger_is_full_screen_responsive_and_reduced_motion_safe() -> None:
    for marker in (
        'body.contentengine-results-os-open .workspace-shell > .sidebar',
        'body.contentengine-payout-ledger-open .workspace-shell > .sidebar',
        '.results-os-comparison',
        '.payout-ledger-issues',
        '@media (max-width: 650px)',
        '@media (max-height: 760px)',
        '@media (prefers-reduced-motion: reduce)',
    ):
        assert marker in CSS


def test_results_ledger_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-results-ledger.js")],
        check=True,
        capture_output=True,
        text=True,
    )


def test_results_ledger_css_is_balanced() -> None:
    assert CSS.count("{") == CSS.count("}")
