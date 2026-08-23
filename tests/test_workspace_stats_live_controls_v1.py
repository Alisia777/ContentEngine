from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web" / "app" / "app.js"
CSS_PATH = ROOT / "web" / "app" / "workspace-os-v4-operations.css"
APP = APP_PATH.read_text(encoding="utf-8")
CSS = CSS_PATH.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source[source.index(start):source.index(end, source.index(start))]


def test_live_stats_waits_for_authoritative_section_before_rendering_values_or_form() -> None:
    render = _between(
        APP,
        "function renderStatsSection(sectionState) {",
        "\n}\n\nfunction statsTable",
    )
    assert 'const readyMarkup = `' in render
    assert "${sectionBody(sectionState, readyMarkup)}" in render
    assert render.index('id="manual-metric-form"') < render.index("sectionBody(sectionState, readyMarkup)")
    assert 'isBusyWithoutData = ["idle", "loading"]' in render


def test_live_stats_controls_filter_only_loaded_publication_fields() -> None:
    filters = _between(APP, "function statsFiltersFromRoute", "function statsRouteHref")
    for marker in (
        'state.route.query.get("period")',
        'state.route.query.get("platform")',
        'state.route.query.get("content_type")',
        'state.route.query.get("q")',
        'state.route.query.get("sort")',
        "statsRowTimestamp(item)",
        "humanMetricSource(item.source)",
    ):
        assert marker in filters
    # Content type is not invented: the selector is populated only from fields
    # that may actually be present in a publication response.
    assert "function statsRowContentType" in APP
    assert "filters.contentTypes.length ?" in APP


def test_live_stats_has_table_cards_pagination_show_more_and_row_snapshot_handoff() -> None:
    for marker in (
        'data-action="set-stats-layout" data-layout="table"',
        'data-action="set-stats-layout" data-layout="cards"',
        "function statsCards(items)",
        "function statsPagination(filters, filteredCount, currentPage)",
        "Показать ещё",
        "function statsSnapshotHref(item)",
        'view: "new"',
        "placement: statsRowId(item)",
        'data-latest-views=',
        'data-latest-clicks=',
        'data-latest-orders=',
        'data-latest-revenue-rub=',
    ):
        assert marker in APP


def test_csv_export_uses_current_loaded_rows_and_guards_spreadsheet_formulas() -> None:
    export = _between(APP, "function statsCsvCell", "function submitStatsFilters")
    assert 'listFrom(data, "publications", "items", "rows")' in export
    assert "filterStatsRows(rows, filters)" in export
    assert "new Blob([csv]" in export
    assert "URL.revokeObjectURL(url)" in export
    assert "/^[=+\\-@]/u.test(text)" in export
    assert "fetch(" not in export
    assert ".recordMetric(" not in export


def test_manual_snapshot_keeps_existing_record_metric_authority() -> None:
    submit = _between(APP, "async function submitManualMetric", "async function submitTrackingLink")
    assert "await state.api.recordMetric({" in submit
    assert "placement_id: placementId" in submit
    assert "observed_at: observedAt.toISOString()" in submit
    sync = _between(APP, "function syncManualMetricClicks", "async function submitWbAlias")
    assert "option?.dataset.latestViews" in sync
    assert "option?.dataset.latestClicks" in sync
    assert "option?.dataset.latestOrders" in sync
    assert "option?.dataset.latestRevenueRub" in sync


def test_live_stats_visual_layer_is_responsive_and_balanced() -> None:
    for marker in (
        "[data-stats-live-results]",
        ".stats-live-toolbar",
        ".stats-live-filters",
        ".stats-live-cards",
        ".stats-live-table",
        ".stats-live-pagination",
        "@media (max-width: 1080px)",
        "@media (max-width: 820px)",
    ):
        assert marker in CSS
    assert CSS.count("{") == CSS.count("}")


def test_app_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    subprocess.run(
        [node, "--check", str(APP_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )
