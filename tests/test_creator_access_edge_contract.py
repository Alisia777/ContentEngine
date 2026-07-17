from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = (
    ROOT / "supabase" / "functions" / "creator-access" / "index.ts"
).read_text(encoding="utf-8")


def test_creator_access_is_authenticated_origin_scoped_and_exact_email_only() -> None:
    assert 'auth: "user"' in EDGE
    assert 'const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin' in EDGE
    assert 'requestOrigin !== PUBLIC_APP_ORIGIN' in EDGE
    assert 'action !== "inspect" && action !== "repair"' in EDGE
    assert 'new Set(["action", "email"])' in EDGE
    assert 'new Set(["action", "email", "request_id"])' in EDGE
    assert "normalizeEmail(payload.email)" in EDGE


def test_access_decision_is_server_scoped_to_certified_manager_and_organization() -> None:
    assert '.rpc("creator_bootstrap"' in EDGE
    assert 'new Set(["owner", "admin"])' in EDGE
    assert '"final_exam_required"' in EDGE
    assert '"team_management_forbidden"' in EDGE
    assert '"creator_account_access_status"' in EDGE
    assert "organization_id: bootstrap.organizationId" in EDGE


def test_recovery_has_durable_reserve_finalize_and_never_claims_delivery() -> None:
    assert '"system_reserve_auth_email_attempt"' in EDGE
    assert '"system_finalize_auth_email_attempt"' in EDGE
    assert "/auth/v1/recover?redirect_to=" in EDGE
    assert 'deliveryStatus: "accepted_unconfirmed"' in EDGE
    assert "delivery_confirmed: false" in EDGE
    assert 'provider: "supabase_auth"' not in EDGE
    assert "provider_message_id" not in EDGE


def test_unknown_provider_outcome_stays_pending_and_cannot_trigger_an_immediate_duplicate() -> None:
    recovery_section = EDGE.split(
        '`${runtime.origin}/auth/v1/recover?redirect_to=', maxsplit=1
    )[1].split("if (!providerResponse.ok)", maxsplit=1)[0]
    assert 'outcome: "provider_outcome_pending"' in recovery_section
    assert "retry_after_seconds: 600" in recovery_section
    assert "finalizeAttempt" not in recovery_section
    assert 'status: "failed"' not in recovery_section


def test_invitation_reuses_creator_invite_without_double_reservation() -> None:
    invite_section = EDGE.split(
        "// creator-invite owns the durable invite reservation",
        maxsplit=1,
    )[1]
    assert "/functions/v1/creator-invite" in invite_section
    assert "system_reserve_auth_email_attempt" not in invite_section
    assert 'body: JSON.stringify({ emails: [email] })' in invite_section
    assert '"membership_connected_recovery_requested"' in invite_section


def test_terminal_delivery_states_are_understood_by_the_access_contract() -> None:
    for state in (
        "unknown",
        "accepted_unconfirmed",
        "deferred",
        "delivered",
        "failed",
        "bounced",
        "suppressed",
        "complained",
    ):
        assert f'"{state}"' in EDGE


def test_edge_response_never_exposes_auth_or_provider_secrets() -> None:
    forbidden_response_fields = (
        "action_link",
        "hashed_token",
        "confirmation_token",
        "service_role_key",
        "password",
        "profile_id",
    )
    response_region = EDGE[EDGE.index("const creatorAccess") :]
    for field in forbidden_response_fields:
        assert f'"{field}"' not in response_region
