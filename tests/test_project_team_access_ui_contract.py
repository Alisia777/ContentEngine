"""Browser contracts for explicit per-project team access management."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index + len(start))
    return source[start_index:end_index]


def test_api_exposes_exact_project_roster_and_idempotent_mutations() -> None:
    for marker in (
        'projectMembers: "creator_project_members"',
        'grantProjectMember: "creator_grant_project_member"',
        'revokeProjectMember: "creator_revoke_project_member"',
    ):
        assert marker in API

    roster = _between(API, "  projectMembers(", "  grantProjectMember(")
    grant = _between(API, "  grantProjectMember(", "  revokeProjectMember(")
    revoke = _between(API, "  revokeProjectMember(", "  projectMedia(")
    assert "this.call(RPC.projectMembers" in roster
    assert "requiredProjectId(projectIdSnake || projectId)" in roster
    for mutation, rpc in (
        (grant, "RPC.grantProjectMember"),
        (revoke, "RPC.revokeProjectMember"),
    ):
        assert f"this.mutate({rpc}" in mutation
        assert "requiredProjectId(projectIdSnake || projectId)" in mutation
        assert "profile_id: normalizedProfileId" in mutation
        assert "if (!isUuid(normalizedProfileId))" in mutation


def test_team_ui_uses_server_catalog_and_url_as_project_authority() -> None:
    context = _between(
        APP,
        "function selectedTeamProjectAccessContext()",
        "function normalizeProjectAccessRoster(",
    )
    chooser = _between(
        APP,
        "function projectAccessMarkup(",
        "async function changeProjectMemberAccess(",
    )
    change = _between(
        APP,
        "async function changeProjectMemberAccess(",
        "function renderTeamSection(",
    )
    selector_handler = _between(APP, "function handleChange(event)", "function submitAccountAdvertisingCheck(")

    assert "normalizeProjectFlow(state.projectFlow?.data || {})" in context
    assert "routeWorkspaceProjectId()" in context
    assert "flow.project_id !== projectId" in context
    assert "flow.projects" in chooser
    assert "data-project-access-project" in chooser
    assert "project_id" in selector_handler
    assert 'navigate(`/workspace/team?' in selector_handler
    assert "scopeProject: false" in selector_handler
    assert "serverProjects.find" in selector_handler
    assert "routeProjectId !== projectId" in change
    assert "context.id !== projectId" in change


def test_team_members_are_explicit_candidates_and_never_auto_enrolled() -> None:
    candidates = _between(
        APP,
        "function teamProjectAccessCandidates(",
        "async function loadProjectMembers(",
    )
    table = _between(
        APP,
        "function projectAccessMemberTable(",
        "function projectAccessMarkup(",
    )
    change = _between(
        APP,
        "async function changeProjectMemberAccess(",
        "function renderTeamSection(",
    )

    assert "member?.profile_id || member?.user_id" in candidates
    assert "PROJECT_ACCESS_OPERATIONAL_ROLES" in table
    assert 'data-action="${hasAccess ? "revoke-project-member" : "grant-project-member"}"' in table
    assert "Новый участник команды не получает другие проекты автоматически" in APP
    assert "state.api.grantProjectMember(profileId, { projectId })" in change
    assert "state.api.revokeProjectMember(profileId, { projectId })" in change
    assert ".forEach((project" not in change
    assert "project_member_is_protected" in API


def test_project_access_state_is_request_guarded_and_cleared_on_scope_changes() -> None:
    loader = _between(
        APP,
        "async function loadProjectMembers(",
        "function projectAccessMemberRows(",
    )
    reset = _between(
        APP,
        "function resetProjectAccessState()",
        "function activateWorkspaceProject(",
    )
    activate = _between(
        APP,
        "function activateWorkspaceProject(",
        "function clearWorkspaceProjectSelection(",
    )
    clear_selection = _between(
        APP,
        "function clearWorkspaceProjectSelection(",
        "function workspaceProjectHref(",
    )
    clear_session = _between(
        APP,
        "function clearAuthenticatedState()",
        "function consumeRouteTransitionClass(",
    )

    for marker in (
        "requestEpoch === state.dataEpoch",
        "requestUserId === state.user?.id",
        "requestId === target.requestId",
        "selectedTeamProjectAccessContext()?.id === context.id",
    ):
        assert marker in loader
    assert 'state.projectAccess.status = "idle"' in reset
    assert "state.projectAccess.data = null" in reset
    assert "state.projectAccess.busyProfileId = \"\"" in reset
    assert "resetProjectAccessState();" in activate
    assert "resetProjectAccessState();" in clear_selection
    assert "resetProjectAccessState();" in clear_session


def test_project_access_errors_are_user_safe_and_protected_roles_are_not_revoked() -> None:
    for code in (
        "project_member_target_not_operational",
        "project_member_not_found",
        "project_member_is_protected",
        "project_members_response_invalid",
        "project_member_mutation_response_invalid",
    ):
        assert code in API
    assert 'if (accessAction === "revoke" && ["owner", "admin"].includes(candidate.role))' in APP
    assert "target.error = actionErrorMessage(error)" in APP
    assert "escapeHtml(target.error" not in APP  # alertMarkup performs the escaping centrally.
    assert "alertMarkup(target.error" in APP
