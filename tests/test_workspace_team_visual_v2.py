from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-team-visual-v2.css").read_text(encoding="utf-8")


def _team_renderer() -> str:
    start = APP.index("function renderTeamSection(sectionState) {")
    end = APP.index("function managerDashboardSectionMarkup()", start)
    return APP[start:end]


def test_team_visual_layer_is_strictly_scoped_to_the_existing_route_root() -> None:
    assert 'data-team-view="${teamView}"' in _team_renderer()
    assert CSS.count("[data-team-view]") >= 60
    assert "body.contentengine-desktop-v4 .ce-v4-window__body [data-team-view]" in CSS
    assert "body.contentengine-desktop-v4 .auth" not in CSS
    assert CSS.count("{") == CSS.count("}")


def test_team_navigation_and_current_action_keep_semantic_dom_hooks() -> None:
    team = _team_renderer()

    assert 'workspaceActionSwitch("team-action-switch team-action-switch--groups"' in team
    assert '"team-action-switch team-action-switch--context"' in team
    assert 'class="card team-members-panel"' in team
    assert 'class="card card-pad project-access-panel"' in APP

    for hook in (
        ".workspace-action-guide",
        ".team-action-switch--groups",
        ".team-action-switch--context",
        ".team-members-panel",
        ".project-access-panel",
    ):
        assert hook in CSS


def test_participant_table_has_navy_ledger_statuses_and_responsive_cards() -> None:
    table = APP[APP.index("function teamMembersTable(members)") : APP.index("function teamInviteResultMarkup", APP.index("function teamMembersTable(members)"))]

    assert '<table class="data-table">' in table
    assert 'data-member-id="${escapeHtml(' in table
    assert "rgba(6, 15, 27, 0.96)" in CSS
    assert ".status-passed" in CSS
    assert ".status-pending" in CSS
    assert "@media (max-width: 760px)" in CSS
    assert 'td:nth-child(2)::before { content: "Роль"; }' in CSS
    assert 'td:nth-child(6)::before { content: "Публикации"; }' in CSS


def test_team_motion_is_subtle_and_respects_reduced_motion() -> None:
    assert "@media (prefers-reduced-motion: no-preference)" in CSS
    assert "@keyframes team-v2-enter" in CSS
    assert "@keyframes team-v2-row-enter" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert "animation: none !important" in CSS
    assert "transition-duration: 0.01ms !important" in CSS
