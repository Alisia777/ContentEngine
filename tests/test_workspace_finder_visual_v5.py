from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLES = (ROOT / "web" / "app" / "workspace-os-v4-finder.css").read_text(encoding="utf-8")


def _visual_layer() -> str:
    marker = "/* Finder visual language v5"
    assert marker in STYLES
    return STYLES.split(marker, 1)[1]


def test_finder_has_an_independent_ice_navy_visual_language() -> None:
    visual = _visual_layer()
    for token in (
        "--ce-v4-finder-ice: #73e8ff",
        "--ce-v4-finder-navy: #07111f",
        "--ce-v4-finder-ice-line",
        "body.ce-v4-finder-route .workspace-board",
        "body.ce-v4-finder-route .workspace-board__sidebar",
        "body.ce-v4-finder-route .workspace-board__drawer",
    ):
        assert token in visual


def test_finder_file_cards_are_media_first_and_have_clear_states() -> None:
    visual = _visual_layer()
    for token in (
        "grid-template-rows: 146px 80px",
        ".workspace-board__item-preview img",
        ".workspace-board__item:hover",
        ".workspace-board__item:is(.is-selected, .is-multi-selected)",
        ".workspace-board__item:focus-within",
        '[data-status="processing"]',
        '[data-status="blocked"]',
        '[data-entity-type="generation"]',
        '[data-entity-type="research"]',
        '[data-entity-kind*="video" i]',
        '[data-entity-kind*="audio" i]',
        '[data-entity-kind*="document" i]',
        '[data-entity-kind*="logo" i]',
    ):
        assert token in visual


def test_grid_list_columns_empty_and_loading_keep_distinct_visual_contracts() -> None:
    visual = _visual_layer()
    for token in (
        '[data-ce-v4-finder-view="list"] .workspace-board__item',
        '[data-ce-v4-finder-view="columns"] .workspace-board__item',
        ".ce-v4-finder-column__row.is-current",
        ".workspace-board__drawer-preview",
        ".workspace-board__empty",
        '.workspace-board[aria-busy="true"]::before',
        "@keyframes ce-v4-finder-loading",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert token in visual


def test_mobile_grid_sizing_does_not_override_list_or_column_rows() -> None:
    visual = _visual_layer()
    mobile = visual.split("@container ce-v4-finder-host (max-width: 760px)", 1)[1]
    mobile = mobile.split("@media (prefers-reduced-motion: reduce)", 1)[0]
    assert '[data-ce-v4-finder-view="grid"] .workspace-board__item' in mobile
    assert '[data-ce-v4-finder-view="grid"] .workspace-board__item-open' in mobile
    assert "body.ce-v4-finder-route .workspace-board__item {\n    min-height" not in mobile
