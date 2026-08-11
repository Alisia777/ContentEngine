from __future__ import annotations

from dataclasses import replace

import pytest

import scripts.grant_training_access_waiver as waiver
from scripts.provision_supabase_member import MemberState, ProvisioningAuthority


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
USER_ID = "33333333-3333-4333-8333-333333333333"
MEMBERSHIP_ID = "44444444-4444-4444-8444-444444444444"
OTHER_ID = "55555555-5555-4555-8555-555555555555"
EMAIL = "employee@example.com"
PUBLISHABLE_KEY = "sb_publishable_browser_safe_test_key"
SERVER_KEY = "sb_secret_service_role_secret_must_not_leak"
REASON = "One-off reviewed employee access waiver for production operations."
AUTHORITY = ProvisioningAuthority(ORGANIZATION_ID, OWNER_ID)


def _state(role: str, **changes: object) -> MemberState:
    return replace(
        MemberState(
            user_id=USER_ID,
            email_confirmed=True,
            auth_active=True,
            signed_in=False,
            app_metadata={},
            membership_count=1,
            membership_role=role,
            membership_status="active",
        ),
        **changes,
    )


class BoundaryManagement:
    def __init__(
        self,
        membership_ids: list[str] | None = None,
        waiver_changes: dict[str, object] | None = None,
    ) -> None:
        self.membership_ids = iter(membership_ids or [MEMBERSHIP_ID, MEMBERSHIP_ID])
        self.waiver_changes = waiver_changes or {}
        self.queries: list[dict[str, object]] = []
        self.server_key_calls = 0

    def execute(self, sql: str, *, read_only: bool = False) -> list[object]:
        self.queries.append({"sql": sql, "read_only": read_only})
        if "join content_factory.training_access_waivers" in sql:
            row = {
                "membership_id": MEMBERSHIP_ID,
                "organization_id": ORGANIZATION_ID,
                "profile_id": USER_ID,
                "role": "operator",
                "membership_status": "active",
                "membership_permissions": [],
                "membership_count": 1,
                "waiver_id": OTHER_ID,
                "waiver_status": "active",
                "scope": "workspace_generation",
                "previous_role": "trainee",
                "granted_role": "operator",
                "grant_reason": REASON,
                "granted_by": OWNER_ID,
                "waiver_count": 1,
            }
            row.update(self.waiver_changes)
            return [row]
        if "as membership_count" in sql:
            membership_id = next(self.membership_ids)
            role = "trainee" if len(self.queries) == 1 else "operator"
            return [
                {
                    "membership_id": membership_id,
                    "organization_id": ORGANIZATION_ID,
                    "profile_id": USER_ID,
                    "role": role,
                    "status": "active",
                    "permissions": [],
                    "membership_count": 1,
                }
            ]
        if "system_set_training_access_waiver" in sql:
            return [{"result": {"ok": True}}]
        pytest.fail(f"unexpected waiver SQL: {sql}")

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


class RecoveryAuth:
    def __init__(self) -> None:
        self.emails: list[str] = []

    def send_password_recovery(self, *, email: str) -> None:
        self.emails.append(email)


def _install_state_reads(
    monkeypatch: pytest.MonkeyPatch,
    states: list[MemberState],
) -> None:
    iterator = iter(states)

    def read_state(
        _client: object,
        *,
        email: str,
        organization_id: str,
    ) -> MemberState:
        assert email == EMAIL
        assert organization_id == ORGANIZATION_ID
        try:
            return next(iterator)
        except StopIteration:
            pytest.fail("unexpected extra member-state read")

    monkeypatch.setattr(waiver, "read_member_state", read_state)


def _run(management: BoundaryManagement) -> tuple[str, str]:
    return waiver.grant_training_access_waiver(
        management_client=management,
        email=EMAIL,
        expected_user_id=USER_ID,
        expected_membership_id=MEMBERSHIP_ID,
        expected_organization_id=ORGANIZATION_ID,
        expected_authority_id=OWNER_ID,
        expected_pre_role="trainee",
        reason=REASON,
        send_recovery=True,
        publishable_key=PUBLISHABLE_KEY,
    )


def test_exact_boundary_is_checked_before_waiver_and_again_before_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = BoundaryManagement()
    auth = RecoveryAuth()
    authority_reads = 0

    def read_authority(_client: object) -> ProvisioningAuthority:
        nonlocal authority_reads
        authority_reads += 1
        return AUTHORITY

    monkeypatch.setattr(waiver, "read_training_waiver_authority", read_authority)
    _install_state_reads(monkeypatch, [_state("trainee"), _state("operator")])
    monkeypatch.setattr(waiver, "SupabaseAuthClient", lambda **_kwargs: auth)

    assert _run(management) == ("operator", "requested")

    assert authority_reads == 2
    assert management.server_key_calls == 1
    assert auth.emails == [EMAIL]
    boundary_queries = [
        query
        for query in management.queries
        if "as membership_count" in str(query["sql"])
        and "join content_factory.training_access_waivers"
        not in str(query["sql"])
    ]
    assert len(boundary_queries) == 2
    assert all(query["read_only"] is True for query in boundary_queries)
    assert "'role', 'operator'" in str(management.queries[1]["sql"])


@pytest.mark.parametrize(
    "partial_boundary",
    [
        {"expected_membership_id": MEMBERSHIP_ID},
        {"expected_organization_id": ORGANIZATION_ID},
        {"expected_authority_id": OWNER_ID},
        {"expected_pre_role": "trainee"},
    ],
)
def test_boundary_arguments_must_be_supplied_as_one_complete_set(
    partial_boundary: dict[str, str],
) -> None:
    management = BoundaryManagement()

    with pytest.raises(waiver.TrainingWaiverError, match="boundary is incomplete"):
        waiver.grant_training_access_waiver(
            management_client=management,
            email=EMAIL,
            expected_user_id=USER_ID,
            reason=REASON,
            send_recovery=True,
            publishable_key=PUBLISHABLE_KEY,
            **partial_boundary,
        )

    assert management.queries == []
    assert management.server_key_calls == 0


def test_changed_authority_before_recovery_blocks_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = BoundaryManagement()
    authorities = iter(
        [AUTHORITY, ProvisioningAuthority(ORGANIZATION_ID, OTHER_ID)]
    )
    monkeypatch.setattr(
        waiver,
        "read_training_waiver_authority",
        lambda _client: next(authorities),
    )
    _install_state_reads(monkeypatch, [_state("trainee")])

    with pytest.raises(
        waiver.TrainingWaiverError,
        match="authority changed before recovery",
    ):
        _run(management)

    assert management.server_key_calls == 0


def test_changed_uuid_mapping_before_recovery_blocks_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = BoundaryManagement()
    monkeypatch.setattr(
        waiver,
        "read_training_waiver_authority",
        lambda _client: AUTHORITY,
    )
    _install_state_reads(
        monkeypatch,
        [_state("trainee"), _state("operator", user_id=OTHER_ID)],
    )

    with pytest.raises(
        waiver.TrainingWaiverError,
        match="Recovery target changed",
    ):
        _run(management)

    assert management.server_key_calls == 0


def test_changed_membership_id_before_recovery_blocks_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = BoundaryManagement([MEMBERSHIP_ID, OTHER_ID])
    monkeypatch.setattr(
        waiver,
        "read_training_waiver_authority",
        lambda _client: AUTHORITY,
    )
    _install_state_reads(monkeypatch, [_state("trainee"), _state("operator")])

    with pytest.raises(
        waiver.TrainingWaiverError,
        match="membership boundary changed",
    ):
        _run(management)

    assert management.server_key_calls == 0


@pytest.mark.parametrize(
    "waiver_changes",
    [
        {"membership_permissions": ["workspace:*"]},
        {"membership_count": 2},
        {"waiver_count": 2},
        {"previous_role": "operator"},
        {"granted_by": OTHER_ID},
        {"grant_reason": "A different unreviewed reason."},
    ],
)
def test_post_waiver_boundary_mismatch_blocks_recovery(
    monkeypatch: pytest.MonkeyPatch,
    waiver_changes: dict[str, object],
) -> None:
    management = BoundaryManagement(waiver_changes=waiver_changes)
    monkeypatch.setattr(
        waiver,
        "read_training_waiver_authority",
        lambda _client: AUTHORITY,
    )
    _install_state_reads(monkeypatch, [_state("trainee")])

    with pytest.raises(
        waiver.TrainingWaiverError,
        match="boundary verification failed",
    ):
        _run(management)

    assert management.server_key_calls == 0
