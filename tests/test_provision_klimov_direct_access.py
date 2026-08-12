from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import scripts.provision_klimov_direct_access as direct
from scripts.adopt_klimov_partial_onboarding import PartialAdoptionSnapshot
from scripts.provision_supabase_member import (
    PASSWORD_CHANGE_COMPLETED_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    PASSWORD_DISPATCH_ID_MARKER,
    MemberProvisionError,
    PasswordDispatch,
    ProvisioningAuthority,
)


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/provision-klimov-direct-access-once.yml"
MIGRATION = ROOT / "supabase/migrations/202608120004_direct_employee_access.sql"

ORGANIZATION_ID = direct.EXPECTED_ORGANIZATION_ID
OWNER_ID = direct.EXPECTED_OWNER_ID
USER_ID = direct.EXPECTED_USER_ID
MEMBERSHIP_ID = direct.EXPECTED_MEMBERSHIP_ID
IDENTITY_ID = direct.EXPECTED_IDENTITY_ID
WAIVER_ID = "55555555-5555-4555-8555-555555555555"
EMAIL = direct.EXPECTED_EMAIL
OWNER_EMAIL = "owner@example.com"
DISPLAY_NAME = "\u0412. \u041a\u043b\u0438\u043c\u043e\u0432"
TEMPORARY_PASSWORD = "TemporaryKlimov77!"
CHANGED_TEMPORARY_PASSWORD = "DifferentTemporary88!"
DISPATCH_ID = "klimov-direct-access-v1"
AUTHORITY = ProvisioningAuthority(ORGANIZATION_ID, OWNER_ID)


@pytest.fixture(autouse=True)
def _exact_invited_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        direct,
        "_classify_provenance",
        lambda _snapshot: direct.CLASS_INVITED_PROVENANCE,
    )


def _base_app_metadata() -> dict[str, Any]:
    return {
        "provider": "email",
        "providers": ["email"],
        PASSWORD_CHANGE_REQUIRED_MARKER: True,
        PASSWORD_CHANGE_COMPLETED_MARKER: False,
    }


def _direct_app_metadata() -> dict[str, Any]:
    return {
        **_base_app_metadata(),
        direct.DIRECT_ACCESS_MARKER: True,
        PASSWORD_CHANGE_COMPLETED_MARKER: False,
        PASSWORD_DISPATCH_ID_MARKER: DISPATCH_ID,
    }


def _raw_metadata(*, verified: bool = False) -> dict[str, Any]:
    metadata = {
        "invited_by": OWNER_ID,
        "intended_role": "trainee",
        "organization_id": ORGANIZATION_ID,
    }
    if verified:
        metadata["email_verified"] = True
    return metadata


def _auth_boundary(
    **changes: Any,
) -> direct.AuthCredentialBoundary:
    boundary = direct.AuthCredentialBoundary(
        session_count=0,
        refresh_token_count=0,
        mfa_factor_count=0,
        identity_count=1,
        identity_id=IDENTITY_ID,
        identity_user_id=USER_ID,
        identity_provider="email",
        identity_email=EMAIL,
        identity_email_verified=False,
        identity_phone_verified=False,
        identity_data={
            "sub": USER_ID,
            "email": EMAIL,
            "email_verified": False,
            "phone_verified": False,
        },
    )
    return replace(boundary, **changes)


def _dispatch_state(
    status: str = "",
    *,
    account_slot: str = direct.ACCOUNT_SLOT,
) -> direct.DispatchState | None:
    if not status:
        return None
    return direct.DispatchState(status=status, account_slot=account_slot)


def _snapshot(**changes: Any) -> PartialAdoptionSnapshot:
    snapshot = PartialAdoptionSnapshot(
        auth_match_count=1,
        user_id=USER_ID,
        auth_email=EMAIL,
        auth_created_at=direct.EXPECTED_CREATED_AT,
        auth_created_in_source_window=True,
        email_confirmed=False,
        auth_active=True,
        signed_in=False,
        no_encrypted_password=True,
        app_metadata=_base_app_metadata(),
        raw_user_meta_data=_raw_metadata(),
        auth_display_name="",
        auth_provider="email",
        auth_providers=("email",),
        profile_id=USER_ID,
        profile_email=EMAIL,
        profile_display_name="",
        profile_status="active",
        organization_id=ORGANIZATION_ID,
        organization_slug="altea-content-factory",
        organization_status="active",
        authority_id=OWNER_ID,
        authority_email=OWNER_EMAIL,
        authority_auth_email=OWNER_EMAIL,
        authority_is_active_owner=True,
        membership_id=MEMBERSHIP_ID,
        membership_organization_id=ORGANIZATION_ID,
        membership_profile_id=USER_ID,
        membership_role="trainee",
        membership_status="active",
        membership_permissions=(),
        membership_created_at="2026-08-11 19:20:00+00",
        membership_updated_at="2026-08-11 19:20:00+00",
        membership_count=1,
        waiver_count=0,
        waiver_id="",
        waiver_organization_id="",
        waiver_profile_id="",
        waiver_status="",
        waiver_scope="",
        waiver_previous_role="",
        waiver_granted_role="",
        waiver_grant_reason="",
        waiver_granted_by="",
        training_attempt_count=0,
        training_certification_count=0,
        project_membership_count=0,
        provenance_events=(),
        provenance_receipts=(),
    )
    return replace(snapshot, **changes)


def _identity_applied() -> PartialAdoptionSnapshot:
    return _snapshot(
        email_confirmed=True,
        no_encrypted_password=False,
        app_metadata=_direct_app_metadata(),
        raw_user_meta_data=_raw_metadata(verified=True),
    )


def _complete(*, reason: str = direct.DEFAULT_REASON) -> PartialAdoptionSnapshot:
    return _identity_applied().__class__(
        **{
            **_identity_applied().__dict__,
            "profile_display_name": DISPLAY_NAME,
            "membership_role": "operator",
            "waiver_count": 1,
            "waiver_id": WAIVER_ID,
            "waiver_organization_id": ORGANIZATION_ID,
            "waiver_profile_id": USER_ID,
            "waiver_status": "active",
            "waiver_scope": "workspace_generation",
            "waiver_previous_role": "trainee",
            "waiver_granted_role": "operator",
            "waiver_grant_reason": reason,
            "waiver_granted_by": OWNER_ID,
            "project_membership_count": 3,
        }
    )


class RecordingAuth:
    def __init__(self, responses: list[Any] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def _admin_request(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any],
    ) -> Any:
        self.calls.append({"path": path, "method": method, "payload": payload})
        if self.responses:
            return self.responses.pop(0)
        return {"id": USER_ID}


class RecordingManagement:
    def __init__(self) -> None:
        self.server_key_calls = 0
        self.queries: list[tuple[str, bool]] = []

    def execute(self, sql: str, *, read_only: bool = False) -> Any:
        self.queries.append((sql, read_only))
        raise AssertionError("unexpected management query")

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return "sb_secret_test_service_role_key"


def test_auth_password_update_is_exact_and_preserves_user_metadata_by_omission() -> None:
    auth = RecordingAuth([{"id": USER_ID}])
    metadata = _direct_app_metadata()

    direct._apply_temporary_password(
        auth,
        user_id=USER_ID,
        password=TEMPORARY_PASSWORD,
        app_metadata=metadata,
    )

    assert auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{USER_ID}",
            "method": "PUT",
            "payload": {
                "password": TEMPORARY_PASSWORD,
                "email_confirm": True,
                "app_metadata": metadata,
            },
        }
    ]
    assert "user_metadata" not in auth.calls[0]["payload"]
    assert auth.calls[0]["payload"]["app_metadata"] == {
        "provider": "email",
        "providers": ["email"],
        PASSWORD_CHANGE_REQUIRED_MARKER: True,
        PASSWORD_CHANGE_COMPLETED_MARKER: False,
        direct.DIRECT_ACCESS_MARKER: True,
        PASSWORD_DISPATCH_ID_MARKER: DISPATCH_ID,
    }


def test_one_off_boundary_is_pinned_to_exact_live_identity_and_invite_provenance() -> None:
    assert direct.EXPECTED_EMAIL == "v.klimov1313@gmail.com"
    assert direct.EXPECTED_USER_ID == "995dcb24-bc8b-4737-b5a6-8dd61e3e0e82"
    assert direct.EXPECTED_MEMBERSHIP_ID == "6ad92ac2-412e-4673-919b-cf26da699c7b"
    assert direct.EXPECTED_ORGANIZATION_ID == "df147614-a4ef-4e66-8b79-1b89f5481ddf"
    assert direct.EXPECTED_OWNER_ID == "05876b51-19e9-4118-a04b-6987642b147e"
    assert direct.EXPECTED_IDENTITY_ID == "d43611f4-4a43-49b1-94bb-829017780fd5"
    assert direct.EXPECTED_CREATED_AT == "2026-08-11 18:31:57.031658+00"
    assert direct.ALLOWED_PROVENANCE == frozenset(
        {direct.CLASS_INVITED_PROVENANCE}
    )


def test_auth_transition_preserves_unknown_metadata_and_only_allows_verification() -> None:
    before = _raw_metadata(verified=False)
    after = _raw_metadata(verified=True)

    assert direct._confirmation_metadata_transition_valid(before, after)
    assert direct._matches_auth_transition(
        _snapshot(raw_user_meta_data=before),
        _identity_applied(),
        expected_metadata=_direct_app_metadata(),
    )

    changed_opaque = _raw_metadata(verified=True)
    changed_opaque["opaque_nested"] = {"source": "replaced"}
    assert not direct._confirmation_metadata_transition_valid(before, changed_opaque)
    added_opaque = {**after, "new_unreviewed_key": True}
    assert not direct._confirmation_metadata_transition_valid(before, added_opaque)


def test_rpc_uses_service_endpoint_exact_payload_and_verifies_all_project_counts() -> None:
    auth = RecordingAuth(
        [
            {
                "ok": True,
                "organization_id": ORGANIZATION_ID,
                "user_id": USER_ID,
                "role": "operator",
                "waiver_active": True,
                "active_project_count": 3,
                "active_project_membership_count": 3,
                "projects_granted_or_reactivated": 3,
            }
        ]
    )

    result = direct._finalize_database_access(
        auth,
        authority=AUTHORITY,
        user_id=USER_ID,
        display_name=DISPLAY_NAME,
        reason=direct.DEFAULT_REASON,
        password_dispatch_id=DISPATCH_ID,
    )

    assert result["active_project_count"] == 3
    assert auth.calls == [
        {
            "path": "/rest/v1/rpc/system_admin_finalize_employee_access",
            "method": "POST",
            "payload": {
                "p_payload": {
                    "organization_id": ORGANIZATION_ID,
                    "user_id": USER_ID,
                    "changed_by": OWNER_ID,
                    "display_name": DISPLAY_NAME,
                    "reason": direct.DEFAULT_REASON,
                    "idempotency_key": (
                        f"{direct.FINALIZE_IDEMPOTENCY_PREFIX}:"
                        f"{ORGANIZATION_ID}:{USER_ID}"
                    ),
                    "password_dispatch_id": DISPATCH_ID,
                }
            },
        }
    ]


def test_rpc_rejects_incomplete_project_coverage() -> None:
    auth = RecordingAuth(
        [
            {
                "ok": True,
                "organization_id": ORGANIZATION_ID,
                "user_id": USER_ID,
                "role": "operator",
                "waiver_active": True,
                "active_project_count": 3,
                "active_project_membership_count": 2,
            }
        ]
    )

    with pytest.raises(direct.KlimovDirectAccessError, match="coverage"):
        direct._finalize_database_access(
            auth,
            authority=AUTHORITY,
            user_id=USER_ID,
            display_name=DISPLAY_NAME,
            reason=direct.DEFAULT_REASON,
            password_dispatch_id=DISPATCH_ID,
        )


@pytest.mark.parametrize(
    "unsafe_change",
    [
        {"auth_match_count": 2},
        {"signed_in": True},
        {"auth_active": False},
        {"membership_role": "admin"},
        {"membership_permissions": ("unexpected",)},
        {"project_membership_count": 1},
        {"training_attempt_count": 1},
        {"app_metadata": {"provider": "email", "providers": ["email"]}},
        {"email_confirmed": True},
    ],
)
def test_unsafe_preflight_states_fail_before_secret_or_auth_mutation(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_change: dict[str, Any],
) -> None:
    management = RecordingManagement()
    snapshot = _snapshot(**unsafe_change)
    monkeypatch.setattr(direct, "_read_exact_owner_authority", lambda *_a, **_k: AUTHORITY)
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(3, 0),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: None,
    )

    with pytest.raises(direct.KlimovDirectAccessError):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build auth client"),
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert management.server_key_calls == 0
    assert management.queries == []


@pytest.mark.parametrize(
    "boundary_change",
    [
        {"session_count": 1},
        {"refresh_token_count": 1},
        {"mfa_factor_count": 1},
        {"identity_count": 2},
        {"identity_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
        {"identity_user_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"},
        {"identity_provider": "github"},
        {"identity_email": "other@example.com"},
        {"identity_email_verified": True},
        {"identity_phone_verified": True},
        {
            "identity_data": {
                "sub": USER_ID,
                "email": EMAIL,
                "email_verified": False,
                "phone_verified": False,
                "unexpected": True,
            }
        },
    ],
)
def test_auth_credential_boundary_mismatch_fails_before_secret_or_mutation(
    monkeypatch: pytest.MonkeyPatch,
    boundary_change: dict[str, Any],
) -> None:
    management = RecordingManagement()
    snapshot = _snapshot()
    monkeypatch.setattr(
        direct,
        "_read_exact_owner_authority",
        lambda *_a, **_k: AUTHORITY,
    )
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(3, 0),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(**boundary_change),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: None,
    )

    with pytest.raises(direct.KlimovDirectAccessError, match="credential boundary"):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build auth client"),
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert management.server_key_calls == 0
    assert management.queries == []


@pytest.mark.parametrize(
    ("phase", "state"),
    [
        (direct.PHASE_NEEDS_PASSWORD, _dispatch_state("identity_applied")),
        (direct.PHASE_IDENTITY_APPLIED, None),
        (direct.PHASE_IDENTITY_APPLIED, _dispatch_state("completed")),
        (direct.PHASE_IDENTITY_APPLIED, _dispatch_state("failed")),
        (direct.PHASE_COMPLETE, None),
        (direct.PHASE_COMPLETE, _dispatch_state("reserved")),
        (direct.PHASE_COMPLETE, _dispatch_state("failed")),
        (
            direct.PHASE_IDENTITY_APPLIED,
            _dispatch_state("identity_applied", account_slot="guest"),
        ),
    ],
)
def test_dispatch_state_must_exactly_match_saga_phase(
    phase: str,
    state: direct.DispatchState | None,
) -> None:
    with pytest.raises(direct.KlimovDirectAccessError, match="dispatch"):
        direct._validate_dispatch_for_phase(state, phase=phase)


@pytest.mark.parametrize(
    ("phase", "state"),
    [
        (direct.PHASE_NEEDS_PASSWORD, None),
        (direct.PHASE_NEEDS_PASSWORD, _dispatch_state("reserved")),
        (direct.PHASE_IDENTITY_APPLIED, _dispatch_state("reserved")),
        (direct.PHASE_IDENTITY_APPLIED, _dispatch_state("identity_applied")),
        (direct.PHASE_COMPLETE, _dispatch_state("identity_applied")),
        (direct.PHASE_COMPLETE, _dispatch_state("completed")),
    ],
)
def test_dispatch_state_accepts_only_reviewed_phase_transitions(
    phase: str,
    state: direct.DispatchState | None,
) -> None:
    direct._validate_dispatch_for_phase(state, phase=phase)


def test_dispatch_binding_verification_uses_exact_hmacs_without_raw_secrets() -> None:
    class BindingManagement:
        def __init__(self) -> None:
            self.queries: list[tuple[str, bool]] = []

        def execute(self, sql: str, *, read_only: bool = False) -> Any:
            self.queries.append((sql, read_only))
            return [{"dispatch_record_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"}]

    management = BindingManagement()
    server_key = "sb_secret_test_service_role_key"
    direct._verify_password_dispatch_binding(
        management,
        dispatch=PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
        email=EMAIL,
        password=TEMPORARY_PASSWORD,
        server_key=server_key,
        allowed_statuses=frozenset({"reserved", "identity_applied"}),
    )

    assert len(management.queries) == 1
    sql, read_only = management.queries[0]
    assert read_only is True
    assert DISPATCH_ID in sql
    assert "account_slot = 'klimov'" in sql
    assert "status in ('identity_applied', 'reserved')" in sql
    assert direct._keyed_fingerprint(
        server_key,
        "member-email",
        EMAIL,
    ) in sql
    assert direct._keyed_fingerprint(
        server_key,
        "member-temp-password",
        TEMPORARY_PASSWORD,
    ) in sql
    assert EMAIL not in sql
    assert TEMPORARY_PASSWORD not in sql
    assert server_key not in sql


@pytest.mark.parametrize(
    "allowed_statuses",
    [frozenset(), frozenset({"failed"}), frozenset({"reserved", "failed"})],
)
def test_dispatch_binding_rejects_unreviewed_status_sets_without_query(
    allowed_statuses: frozenset[str],
) -> None:
    management = RecordingManagement()

    with pytest.raises(MemberProvisionError, match="status is invalid"):
        direct._verify_password_dispatch_binding(
            management,
            dispatch=PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
            email=EMAIL,
            password=TEMPORARY_PASSWORD,
            server_key="sb_secret_test_service_role_key",
            allowed_statuses=allowed_statuses,
        )

    assert management.queries == []


def test_completed_database_phase_reconciles_open_password_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = RecordingManagement()
    completed = _complete()
    transitions: list[tuple[str, str]] = []
    resume_calls: list[PasswordDispatch] = []
    verification_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(direct, "_read_exact_owner_authority", lambda *_a, **_k: AUTHORITY)
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: completed)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(3, 3),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state("identity_applied"),
    )

    def verify_binding(
        _client: Any,
        **kwargs: Any,
    ) -> None:
        verification_calls.append(dict(kwargs))

    monkeypatch.setattr(
        direct,
        "_verify_password_dispatch_binding",
        verify_binding,
    )

    def resume(_client: Any, *, dispatch: PasswordDispatch) -> PasswordDispatch:
        resume_calls.append(dispatch)
        return dispatch

    monkeypatch.setattr(direct, "_resume_password_dispatch", resume)
    monkeypatch.setattr(
        direct,
        "_transition_password_dispatch",
        lambda _client, *, dispatch, from_status, to_status: transitions.append(
            (from_status, to_status)
        ),
    )

    result = direct.provision_klimov_direct_access(
        management_client=management,
        auth_client_factory=lambda _key: pytest.fail("completed phase needs no auth"),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        temporary_password=TEMPORARY_PASSWORD,
        password_dispatch_id=DISPATCH_ID,
    )

    assert result.identity_status == "existing"
    assert management.server_key_calls == 1
    assert verification_calls == [
        {
            "dispatch": PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
            "email": EMAIL,
            "password": TEMPORARY_PASSWORD,
            "server_key": "sb_secret_test_service_role_key",
            "allowed_statuses": frozenset({"identity_applied", "completed"}),
        }
    ]
    assert resume_calls == [PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT)]
    assert transitions == [("identity_applied", "completed")]


def test_password_dispatch_reservation_fails_before_auth_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = RecordingManagement()
    auth = RecordingAuth()
    snapshot = _snapshot()
    monkeypatch.setattr(direct, "_read_exact_owner_authority", lambda *_a, **_k: AUTHORITY)
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(3, 0),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        direct,
        "_reserve_password_dispatch",
        lambda *_a, **_k: (_ for _ in ()).throw(
            MemberProvisionError("dispatch already used")
        ),
    )

    with pytest.raises(MemberProvisionError, match="already used"):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: auth,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert auth.calls == []


def test_fresh_saga_reserves_sets_password_finalizes_and_completes_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = RecordingManagement()
    state = {
        "snapshot": _snapshot(),
        "coverage": direct.ProjectCoverage(3, 0),
        "dispatch_status": "",
    }
    transitions: list[tuple[str, str]] = []
    reservations: list[PasswordDispatch] = []

    class SagaAuth(RecordingAuth):
        def _admin_request(
            self,
            path: str,
            *,
            method: str,
            payload: dict[str, Any],
        ) -> Any:
            self.calls.append({"path": path, "method": method, "payload": payload})
            if path.startswith("/auth/v1/admin/users/"):
                state["snapshot"] = _identity_applied()
                return {"id": USER_ID}
            assert path == "/rest/v1/rpc/system_admin_finalize_employee_access"
            state["snapshot"] = _complete()
            state["coverage"] = direct.ProjectCoverage(3, 3)
            return {
                "ok": True,
                "organization_id": ORGANIZATION_ID,
                "user_id": USER_ID,
                "role": "operator",
                "waiver_active": True,
                "active_project_count": 3,
                "active_project_membership_count": 3,
                "projects_granted_or_reactivated": 3,
            }

    auth = SagaAuth()
    monkeypatch.setattr(direct, "_read_exact_owner_authority", lambda *_a, **_k: AUTHORITY)
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: state["snapshot"])
    monkeypatch.setattr(direct, "_read_project_coverage", lambda *_a, **_k: state["coverage"])
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state(state["dispatch_status"]),
    )
    monkeypatch.setattr(
        direct,
        "_reserve_password_dispatch",
        lambda _client, *, dispatch, **_kwargs: (
            reservations.append(dispatch),
            state.__setitem__("dispatch_status", "reserved"),
        ),
    )
    monkeypatch.setattr(
        direct,
        "_transition_password_dispatch",
        lambda _client, *, dispatch, from_status, to_status: (
            transitions.append((from_status, to_status)),
            state.__setitem__("dispatch_status", to_status),
        ),
    )

    result = direct.provision_klimov_direct_access(
        management_client=management,
        auth_client_factory=lambda key: auth
        if key == "sb_secret_test_service_role_key"
        else pytest.fail("unexpected key"),
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        temporary_password=TEMPORARY_PASSWORD,
        password_dispatch_id=DISPATCH_ID,
    )

    assert result == direct.DirectAccessResult(
        phase=direct.PHASE_COMPLETE,
        identity_status="password_set",
        membership_role="operator",
        active_projects=3,
    )
    assert reservations == [PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT)]
    assert transitions == [
        ("reserved", "identity_applied"),
        ("identity_applied", "completed"),
    ]
    assert [call["path"] for call in auth.calls] == [
        f"/auth/v1/admin/users/{USER_ID}",
        "/rest/v1/rpc/system_admin_finalize_employee_access",
    ]


@pytest.mark.parametrize(
    ("initial_dispatch_status", "expected_transitions"),
    [
        ("identity_applied", [("identity_applied", "completed")]),
        (
            "reserved",
            [
                ("reserved", "identity_applied"),
                ("identity_applied", "completed"),
            ],
        ),
    ],
)
def test_identity_applied_saga_resumes_without_password_reset(
    monkeypatch: pytest.MonkeyPatch,
    initial_dispatch_status: str,
    expected_transitions: list[tuple[str, str]],
) -> None:
    management = RecordingManagement()
    state = {
        "snapshot": _identity_applied(),
        "coverage": direct.ProjectCoverage(2, 0),
        "dispatch_status": initial_dispatch_status,
    }
    transitions: list[tuple[str, str]] = []
    resume_calls: list[PasswordDispatch] = []
    verification_calls: list[dict[str, Any]] = []

    class ResumeAuth(RecordingAuth):
        def _admin_request(
            self,
            path: str,
            *,
            method: str,
            payload: dict[str, Any],
        ) -> Any:
            self.calls.append({"path": path, "method": method, "payload": payload})
            assert path == "/rest/v1/rpc/system_admin_finalize_employee_access"
            state["snapshot"] = _complete()
            state["snapshot"] = replace(state["snapshot"], project_membership_count=2)
            state["coverage"] = direct.ProjectCoverage(2, 2)
            return {
                "ok": True,
                "organization_id": ORGANIZATION_ID,
                "user_id": USER_ID,
                "role": "operator",
                "waiver_active": True,
                "active_project_count": 2,
                "active_project_membership_count": 2,
                "projects_granted_or_reactivated": 2,
            }

    auth = ResumeAuth()
    monkeypatch.setattr(direct, "_read_exact_owner_authority", lambda *_a, **_k: AUTHORITY)
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: state["snapshot"])
    monkeypatch.setattr(direct, "_read_project_coverage", lambda *_a, **_k: state["coverage"])
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state(state["dispatch_status"]),
    )

    def verify_binding(
        _client: Any,
        **kwargs: Any,
    ) -> None:
        verification_calls.append(dict(kwargs))

    monkeypatch.setattr(
        direct,
        "_verify_password_dispatch_binding",
        verify_binding,
    )

    def resume(_client: Any, *, dispatch: PasswordDispatch) -> PasswordDispatch:
        resume_calls.append(dispatch)
        if state["dispatch_status"] == "reserved":
            transitions.append(("reserved", "identity_applied"))
            state["dispatch_status"] = "identity_applied"
        return dispatch

    monkeypatch.setattr(direct, "_resume_password_dispatch", resume)
    monkeypatch.setattr(
        direct,
        "_transition_password_dispatch",
        lambda _client, *, dispatch, from_status, to_status: (
            transitions.append((from_status, to_status)),
            state.__setitem__("dispatch_status", to_status),
        ),
    )
    monkeypatch.setattr(
        direct,
        "_reserve_password_dispatch",
        lambda *_a, **_k: pytest.fail("resume must not reserve a new password"),
    )

    result = direct.provision_klimov_direct_access(
        management_client=management,
        auth_client_factory=lambda _key: auth,
        email=EMAIL,
        display_name=DISPLAY_NAME,
        owner_email=OWNER_EMAIL,
        temporary_password=TEMPORARY_PASSWORD,
        password_dispatch_id=DISPATCH_ID,
    )

    assert result.identity_status == "password_existing"
    assert resume_calls == [PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT)]
    assert verification_calls == [
        {
            "dispatch": PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
            "email": EMAIL,
            "password": TEMPORARY_PASSWORD,
            "server_key": "sb_secret_test_service_role_key",
            "allowed_statuses": frozenset({"reserved", "identity_applied"}),
        }
    ]
    assert transitions == expected_transitions
    assert [call["path"] for call in auth.calls] == [
        "/rest/v1/rpc/system_admin_finalize_employee_access"
    ]


@pytest.mark.parametrize("dispatch_status", ["reserved", "identity_applied"])
def test_identity_applied_retry_rejects_changed_temporary_password_before_resume(
    monkeypatch: pytest.MonkeyPatch,
    dispatch_status: str,
) -> None:
    management = RecordingManagement()
    snapshot = _identity_applied()
    auth = RecordingAuth()
    verification_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        direct,
        "_read_exact_owner_authority",
        lambda *_a, **_k: AUTHORITY,
    )
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(2, 0),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state(dispatch_status),
    )

    def reject_changed_binding(
        _client: Any,
        *,
        dispatch: PasswordDispatch,
        email: str,
        password: str,
        server_key: str,
        allowed_statuses: frozenset[str],
    ) -> None:
        verification_calls.append(
            {
                "dispatch": dispatch,
                "email": email,
                "password": password,
                "server_key": server_key,
                "allowed_statuses": allowed_statuses,
            }
        )
        raise MemberProvisionError(
            "Member password dispatch credential binding does not match"
        )

    # `raising=False` keeps this regression executable before the helper lands:
    # without an actual production call to it, the test proceeds to the
    # forbidden resume assertion below and fails.
    monkeypatch.setattr(
        direct,
        "_verify_password_dispatch_binding",
        reject_changed_binding,
        raising=False,
    )
    monkeypatch.setattr(
        direct,
        "_resume_password_dispatch",
        lambda *_a, **_k: pytest.fail(
            "changed temporary password must fail before dispatch resume"
        ),
    )

    with pytest.raises(
        MemberProvisionError,
        match="credential binding does not match",
    ):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: auth,
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=CHANGED_TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert verification_calls == [
        {
            "dispatch": PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
            "email": EMAIL,
            "password": CHANGED_TEMPORARY_PASSWORD,
            "server_key": "sb_secret_test_service_role_key",
            "allowed_statuses": frozenset({"reserved", "identity_applied"}),
        }
    ]
    assert management.server_key_calls == 1
    assert auth.calls == []


@pytest.mark.parametrize("dispatch_status", ["identity_applied", "completed"])
def test_completed_retry_rejects_changed_temporary_password_before_success(
    monkeypatch: pytest.MonkeyPatch,
    dispatch_status: str,
) -> None:
    management = RecordingManagement()
    snapshot = _complete()
    verification_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        direct,
        "_read_exact_owner_authority",
        lambda *_a, **_k: AUTHORITY,
    )
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(3, 3),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state(dispatch_status),
    )

    def reject_changed_binding(
        _client: Any,
        **kwargs: Any,
    ) -> None:
        verification_calls.append(dict(kwargs))
        raise MemberProvisionError(
            "Member password dispatch credential binding does not match"
        )

    monkeypatch.setattr(
        direct,
        "_verify_password_dispatch_binding",
        reject_changed_binding,
    )
    monkeypatch.setattr(
        direct,
        "_resume_password_dispatch",
        lambda *_a, **_k: pytest.fail(
            "changed temporary password must fail before completed resume"
        ),
    )

    with pytest.raises(
        MemberProvisionError,
        match="credential binding does not match",
    ):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail(
                "complete phase must not build Auth client"
            ),
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=CHANGED_TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert verification_calls == [
        {
            "dispatch": PasswordDispatch(DISPATCH_ID, direct.ACCOUNT_SLOT),
            "email": EMAIL,
            "password": CHANGED_TEMPORARY_PASSWORD,
            "server_key": "sb_secret_test_service_role_key",
            "allowed_statuses": frozenset({"identity_applied", "completed"}),
        }
    ]
    assert management.server_key_calls == 1


def test_identity_applied_marker_must_match_requested_dispatch_before_secret_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    different_dispatch_id = "klimov-direct-access-different-v1"
    snapshot = replace(
        _identity_applied(),
        app_metadata={
            **_direct_app_metadata(),
            PASSWORD_DISPATCH_ID_MARKER: different_dispatch_id,
        },
    )
    management = RecordingManagement()
    monkeypatch.setattr(
        direct,
        "_read_exact_owner_authority",
        lambda *_a, **_k: AUTHORITY,
    )
    monkeypatch.setattr(direct, "_read_snapshot", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(
        direct,
        "_read_project_coverage",
        lambda *_a, **_k: direct.ProjectCoverage(2, 0),
    )
    monkeypatch.setattr(
        direct,
        "_read_auth_credential_boundary",
        lambda *_a, **_k: _auth_boundary(),
    )
    monkeypatch.setattr(
        direct,
        "_read_dispatch_state",
        lambda *_a, **_k: _dispatch_state("identity_applied"),
    )

    with pytest.raises(
        direct.KlimovDirectAccessError,
        match="does not match the requested saga",
    ):
        direct.provision_klimov_direct_access(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build Auth client"),
            email=EMAIL,
            display_name=DISPLAY_NAME,
            owner_email=OWNER_EMAIL,
            temporary_password=TEMPORARY_PASSWORD,
            password_dispatch_id=DISPATCH_ID,
        )

    assert management.server_key_calls == 0


def test_workflow_is_manual_exact_main_production_and_has_no_mail_or_recovery() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    flat = " ".join(source.lower().split())

    assert source.startswith("name: Provision Klimov direct access once\n")
    assert "workflow_dispatch:" in source
    assert "PROVISION_KLIMOV_TEMP_PASSWORD_OPERATOR_ALL_PROJECTS_ONCE" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "ref: ${{ github.sha }}" in source
    assert "environment: production" in source
    assert "permissions:\n  contents: read" in source
    assert "cancel-in-progress: false" in source
    assert "SUPABASE_MEMBER_KLIMOV_TEMP_PASSWORD" in source
    assert "CONTENTENGINE_MEMBER_DISPATCH_PASSWORD" in source
    assert "::add-mask::$CONTENTENGINE_MEMBER_DISPATCH_PASSWORD" not in source
    python_source = (
        ROOT / "scripts/provision_klimov_direct_access.py"
    ).read_text(encoding="utf-8")
    assert "_github_actions_escape(validated_password)" in python_source
    assert "::add-mask::{_github_actions_escape(validated_password)}" in python_source
    assert "python -m scripts.provision_klimov_direct_access" in source
    assert "--password-dispatch-id=\"klimov-direct-access-v1\"" in source
    assert "smtp_" not in flat
    assert "/auth/v1/recover" not in flat
    assert "send_password_recovery" not in flat
    assert "sendgrid" not in flat
    assert "mailgun" not in flat
    assert "pull_request:" not in source
    assert "push:" not in source
    assert "schedule:" not in source


def test_sql_rpc_is_service_only_locked_atomic_idempotent_and_grants_all_projects() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    flat = " ".join(source.lower().split())

    assert "security definer" in flat
    assert "set search_path = ''" in flat
    assert "coalesce(auth.role(), '') <> 'service_role'" in flat
    assert "message = 'service_role_required'" in flat
    assert (
        "revoke all on function public.system_admin_finalize_employee_access(jsonb) "
        "from public, anon, authenticated, service_role"
    ) in flat
    assert (
        "grant execute on function public.system_admin_finalize_employee_access(jsonb) "
        "to service_role"
    ) in flat

    lock_at = flat.index("content_factory_private.lock_admin_member")
    command_at = flat.index("content_factory_private.begin_command")
    waiver_at = flat.index("public.system_set_training_access_waiver")
    project_insert_at = flat.index(
        "insert into content_factory.workspace_project_memberships"
    )
    finish_at = flat.index("content_factory_private.finish_command")
    assert lock_at < command_at < waiver_at < project_insert_at < finish_at

    assert "'action', 'grant'" in flat
    assert "'role', 'operator'" in flat
    assert "'password_dispatch_id'" in flat
    assert "password_dispatch_id_value !~ '^[a-za-z0-9._:-]+$'" in flat
    assert "auth_user.raw_app_meta_data" in flat
    assert (
        "nullif(btrim(coalesce(auth_user.encrypted_password, '')), '') is not null"
        in flat
    )
    assert "lower(auth_user.email) = 'v.klimov1313@gmail.com'" in flat
    assert (
        "auth_user.created_at = timestamptz '2026-08-11 18:31:57.031658+00'"
        in flat
    )
    assert "auth_user.last_sign_in_at is null" in flat
    assert "auth_user.raw_user_meta_data = jsonb_build_object(" in flat
    assert "'invited_by', changed_by_id::text" in flat
    assert "'intended_role', 'trainee'" in flat
    assert "'organization_id', organization_id::text" in flat
    assert "'email_verified', true" in flat
    assert "auth_user.raw_app_meta_data = jsonb_build_object(" in flat
    assert "'provider', 'email'" in flat
    assert "'providers', jsonb_build_array('email')" in flat
    assert "'contentengine_password_change_required', true" in flat
    assert "'contentengine_password_change_completed', false" in flat
    assert (
        "'contentengine_password_dispatch_id', password_dispatch_id_value"
        in flat
    )
    assert "'contentengine_klimov_direct_access_v1', true" in flat
    assert "from content_factory.member_password_dispatches dispatch" in flat
    assert "dispatch.account_slot = 'klimov'" in flat
    assert "dispatch.status in ('identity_applied', 'completed')" in flat
    assert "employee_password_dispatch_not_applied" in flat
    assert "waiver.scope = 'workspace_generation'" in flat
    assert "waiver.previous_role = 'trainee'" in flat
    assert "waiver.grant_reason = reason_value" in flat
    assert "waiver.granted_by = changed_by_id" in flat
    assert "project.kind = 'project'" in flat
    assert "project.status = 'active'" in flat
    assert "on conflict on constraint workspace_project_memberships_pkey" in flat
    assert "where project_member.status = 'revoked'" in flat
    assert "active_project_count <> active_project_membership_count" in flat
    assert "employee_access_project_memberships_incomplete" in flat
    assert "content_factory_private.emit_event" in flat
    assert "admin_employee_access_finalized" in flat
    assert "idempotency_key_value" in flat
    assert "notify pgrst, 'reload schema'" in flat
    assert "update auth.users" not in flat
    assert "insert into auth.users" not in flat
