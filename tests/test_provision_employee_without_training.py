from __future__ import annotations

from dataclasses import replace

import pytest

import scripts.grant_training_access_waiver as waiver
import scripts.provision_employee_without_training as onboarding
from scripts.bootstrap_supabase_owner import OwnerBootstrapError
from scripts.grant_training_access_waiver import TrainingWaiverError
from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    MemberState,
    ProvisioningAuthority,
)


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
EMPLOYEE_ID = "33333333-3333-4333-8333-333333333333"
OTHER_ID = "44444444-4444-4444-8444-444444444444"
EMPLOYEE_EMAIL = "employee@example.com"
PUBLISHABLE_KEY = "sb_publishable_browser_safe_test_key"
SERVER_KEY = "sb_secret_service_role_secret_must_not_leak"
REASON = "Approved by the owner for operational workspace access."


def _provisioning_metadata(**extra: object) -> dict[str, object]:
    return {
        MEMBER_PROVISION_MARKER: True,
        PASSWORD_CHANGE_REQUIRED_MARKER: True,
        **extra,
    }


def _unconfirmed(**changes: object) -> MemberState:
    return replace(
        MemberState(
            user_id=EMPLOYEE_ID,
            email_confirmed=False,
            auth_active=True,
            signed_in=False,
            app_metadata=_provisioning_metadata(
                provider="email",
                providers=["email"],
            ),
            membership_count=0,
        ),
        **changes,
    )


def _confirmed_without_membership(**changes: object) -> MemberState:
    return replace(_unconfirmed(email_confirmed=True), **changes)


def _active_member(role: str = "trainee") -> MemberState:
    return replace(
        _confirmed_without_membership(),
        membership_count=1,
        membership_role=role,
        membership_status="active",
    )


class FakeManagement:
    def __init__(self) -> None:
        self.server_key_calls = 0

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


class FakeAuth:
    def __init__(self, *, update_error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.update_error = update_error

    def _admin_request(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, object],
    ) -> None:
        self.calls.append(
            {
                "path": path,
                "method": method,
                "payload": dict(payload),
            }
        )
        if method == "PUT" and self.update_error is not None:
            raise self.update_error


class Harness:
    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        states: list[MemberState],
        *,
        update_error: Exception | None = None,
    ) -> None:
        # Скрипт читает SUPABASE_PROJECT_REF из окружения, а ожидания теста
        # написаны на пустое значение. У разработчика переменная выставлена в
        # реальный проект, и тест падал не из-за кода, а из-за окружения
        # запускающего. Снимаем её на время прогона, чтобы результат не зависел
        # от того, чья машина его выполняет.
        monkeypatch.delenv("SUPABASE_PROJECT_REF", raising=False)
        self.management = FakeManagement()
        self.auth = FakeAuth(update_error=update_error)
        self.auth_builds: list[dict[str, str]] = []
        self.initializations: list[dict[str, object]] = []
        self.grants: list[dict[str, object]] = []
        self.reads = 0
        state_iterator = iter(states)

        monkeypatch.setattr(
            onboarding,
            "read_training_waiver_authority",
            lambda _client: ProvisioningAuthority(
                organization_id=ORGANIZATION_ID,
                invited_by=OWNER_ID,
            ),
        )

        def read_state(
            _client: object,
            *,
            email: str,
            organization_id: str,
        ) -> MemberState:
            assert email == EMPLOYEE_EMAIL
            assert organization_id == ORGANIZATION_ID
            self.reads += 1
            try:
                return next(state_iterator)
            except StopIteration:
                pytest.fail("unexpected extra employee state read")

        monkeypatch.setattr(onboarding, "read_member_state", read_state)

        def build_auth(**kwargs: str) -> FakeAuth:
            self.auth_builds.append(dict(kwargs))
            return self.auth

        monkeypatch.setattr(onboarding, "SupabaseAuthClient", build_auth)

        def initialize(
            _client: object,
            *,
            authority: ProvisioningAuthority,
            user_id: str,
            role: str,
        ) -> None:
            self.initializations.append(
                {
                    "authority": authority,
                    "user_id": user_id,
                    "role": role,
                }
            )

        monkeypatch.setattr(onboarding, "initialize_member_membership", initialize)

        def grant(**kwargs: object) -> tuple[str, str]:
            self.grants.append(dict(kwargs))
            return "operator", "requested"

        monkeypatch.setattr(onboarding, "grant_training_access_waiver", grant)

    def run(self) -> tuple[str, str, str]:
        return onboarding.provision_employee_without_training(
            management_client=self.management,
            email=EMPLOYEE_EMAIL,
            display_name="Employee",
            distinct_from=["owner@example.com"],
            reason=REASON,
            publishable_key=PUBLISHABLE_KEY,
        )


def test_current_unconfirmed_incident_is_confirmed_then_onboarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Harness(
        monkeypatch,
        [
            _unconfirmed(),
            _confirmed_without_membership(),
            _active_member(),
        ],
    )

    result = harness.run()

    assert result == (
        "confirmed_for_recovery",
        "created",
        "operator:requested",
    )
    assert harness.management.server_key_calls == 1
    assert harness.auth_builds == [
        {
            "project_ref": "",
            "server_key": SERVER_KEY,
            "publishable_key": PUBLISHABLE_KEY,
        }
    ]
    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{EMPLOYEE_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        }
    ]
    assert harness.initializations == [
        {
            "authority": ProvisioningAuthority(ORGANIZATION_ID, OWNER_ID),
            "user_id": EMPLOYEE_ID,
            "role": "trainee",
        }
    ]
    assert len(harness.grants) == 1
    assert harness.grants[0]["expected_user_id"] == EMPLOYEE_ID
    assert harness.grants[0]["send_recovery"] is True


def test_fresh_create_can_repair_unconfirmed_supabase_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Harness(
        monkeypatch,
        [
            MemberState(user_id=None, app_metadata={}),
            _unconfirmed(),
            _confirmed_without_membership(),
            _active_member(),
        ],
    )

    result = harness.run()

    assert result[0] == "confirmed_for_recovery"
    assert harness.management.server_key_calls == 1
    assert harness.auth.calls == [
        {
            "path": "/auth/v1/admin/users",
            "method": "POST",
            "payload": {
                "email": EMPLOYEE_EMAIL,
                "email_confirm": True,
                "user_metadata": {"display_name": "Employee"},
                "app_metadata": {
                    MEMBER_PROVISION_MARKER: True,
                    PASSWORD_CHANGE_REQUIRED_MARKER: True,
                },
            },
        },
        {
            "path": f"/auth/v1/admin/users/{EMPLOYEE_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        },
    ]
    assert len(harness.initializations) == 1
    assert len(harness.grants) == 1


def test_completed_rerun_is_idempotent_and_does_not_reveal_server_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Harness(monkeypatch, [_active_member("operator")])

    result = harness.run()

    assert result == ("existing", "existing", "operator:requested")
    assert harness.management.server_key_calls == 0
    assert harness.auth_builds == []
    assert harness.auth.calls == []
    assert harness.initializations == []
    assert len(harness.grants) == 1


@pytest.mark.parametrize(
    "unsafe_state",
    [
        _unconfirmed(app_metadata={}),
        _unconfirmed(app_metadata={MEMBER_PROVISION_MARKER: True}),
        _unconfirmed(
            app_metadata={PASSWORD_CHANGE_REQUIRED_MARKER: True},
        ),
        _unconfirmed(
            app_metadata=_provisioning_metadata(
                contentengine_bootstrap_owner=True,
            ),
        ),
        _unconfirmed(
            app_metadata=_provisioning_metadata(
                contentengine_password_change_completed=False,
            ),
        ),
        _unconfirmed(signed_in=True),
        _unconfirmed(auth_active=False),
        _unconfirmed(membership_count=1),
        _unconfirmed(membership_role="trainee"),
        _unconfirmed(membership_status="active"),
    ],
    ids=[
        "unmarked",
        "member-marker-only",
        "password-marker-only",
        "owner-marker-conflict",
        "completed-marker-conflict",
        "already-signed-in",
        "inactive",
        "membership-count",
        "membership-role",
        "membership-status",
    ],
)
def test_unsafe_unconfirmed_identity_fails_before_auth_or_recovery(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_state: MemberState,
) -> None:
    harness = Harness(monkeypatch, [unsafe_state])

    with pytest.raises(onboarding.EmployeeOnboardingError):
        harness.run()

    assert harness.management.server_key_calls == 0
    assert harness.auth_builds == []
    assert harness.auth.calls == []
    assert harness.initializations == []
    assert harness.grants == []


@pytest.mark.parametrize(
    "post_update_state",
    [
        _confirmed_without_membership(user_id=OTHER_ID),
        _unconfirmed(),
        _confirmed_without_membership(auth_active=False),
        _confirmed_without_membership(signed_in=True),
        _confirmed_without_membership(membership_count=1),
        _confirmed_without_membership(membership_role="trainee"),
        _confirmed_without_membership(membership_status="active"),
        _confirmed_without_membership(app_metadata={}),
        _confirmed_without_membership(
            app_metadata=_provisioning_metadata(
                contentengine_password_dispatch_id="dispatch-id",
            ),
        ),
    ],
    ids=[
        "uuid-changed",
        "still-unconfirmed",
        "inactive",
        "signed-in",
        "membership-count",
        "membership-role",
        "membership-status",
        "markers-lost",
        "conflicting-marker-added",
    ],
)
def test_post_update_mismatch_fails_before_membership_waiver_or_recovery(
    monkeypatch: pytest.MonkeyPatch,
    post_update_state: MemberState,
) -> None:
    harness = Harness(monkeypatch, [_unconfirmed(), post_update_state])

    with pytest.raises(
        onboarding.EmployeeOnboardingError,
        match="confirmation verification failed",
    ):
        harness.run()

    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{EMPLOYEE_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        }
    ]
    assert harness.initializations == []
    assert harness.grants == []


def test_admin_update_failure_fails_before_membership_waiver_or_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_error = OwnerBootstrapError("Supabase owner bootstrap request failed")
    harness = Harness(
        monkeypatch,
        [_unconfirmed()],
        update_error=update_error,
    )

    with pytest.raises(OwnerBootstrapError):
        harness.run()

    assert harness.auth.calls == [
        {
            "path": f"/auth/v1/admin/users/{EMPLOYEE_ID}",
            "method": "PUT",
            "payload": {"email_confirm": True},
        }
    ]
    assert harness.initializations == []
    assert harness.grants == []


def test_post_update_marker_loss_cannot_bypass_checks_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirmed_with_only_member_marker = _confirmed_without_membership(
        app_metadata={MEMBER_PROVISION_MARKER: True},
    )
    first_attempt = Harness(
        monkeypatch,
        [_unconfirmed(), confirmed_with_only_member_marker],
    )

    with pytest.raises(
        onboarding.EmployeeOnboardingError,
        match="confirmation verification failed",
    ):
        first_attempt.run()

    assert first_attempt.initializations == []
    assert first_attempt.grants == []

    retry = Harness(monkeypatch, [confirmed_with_only_member_marker])

    with pytest.raises(
        onboarding.EmployeeOnboardingError,
        match="not safe for recovery onboarding",
    ):
        retry.run()

    assert retry.management.server_key_calls == 0
    assert retry.auth.calls == []
    assert retry.initializations == []
    assert retry.grants == []


def test_second_organization_membership_blocks_waiver_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = Harness(
        monkeypatch,
        [replace(_active_member(), membership_count=2)],
    )

    with pytest.raises(
        onboarding.EmployeeOnboardingError,
        match="membership verification failed",
    ):
        harness.run()

    assert harness.management.server_key_calls == 0
    assert harness.auth.calls == []
    assert harness.initializations == []
    assert harness.grants == []


@pytest.mark.parametrize(
    "unsafe_trainee",
    [
        replace(
            _active_member(),
            app_metadata={MEMBER_PROVISION_MARKER: True},
        ),
        replace(_active_member(), signed_in=True),
    ],
    ids=["password-marker-lost", "signed-in"],
)
def test_existing_unsafe_trainee_cannot_retry_into_waiver_or_recovery(
    monkeypatch: pytest.MonkeyPatch,
    unsafe_trainee: MemberState,
) -> None:
    harness = Harness(monkeypatch, [unsafe_trainee])

    with pytest.raises(
        onboarding.EmployeeOnboardingError,
        match="Trainee membership is not safe for recovery onboarding",
    ):
        harness.run()

    assert harness.management.server_key_calls == 0
    assert harness.auth.calls == []
    assert harness.initializations == []
    assert harness.grants == []


class WaiverManagement:
    def __init__(self) -> None:
        self.queries: list[dict[str, object]] = []
        self.server_key_calls = 0

    def execute(self, sql: str, *, read_only: bool = False) -> list[object]:
        self.queries.append({"sql": sql, "read_only": read_only})
        return []

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


def test_waiver_rejects_changed_email_mapping_before_rpc_or_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    management = WaiverManagement()
    monkeypatch.setattr(
        waiver,
        "read_training_waiver_authority",
        lambda _client: ProvisioningAuthority(ORGANIZATION_ID, OWNER_ID),
    )
    monkeypatch.setattr(
        waiver,
        "read_member_state",
        lambda *_args, **_kwargs: replace(
            _active_member(),
            user_id=OTHER_ID,
        ),
    )

    with pytest.raises(
        TrainingWaiverError,
        match="identity changed during onboarding",
    ):
        waiver.grant_training_access_waiver(
            management_client=management,
            email=EMPLOYEE_EMAIL,
            expected_user_id=EMPLOYEE_ID,
            reason=REASON,
            send_recovery=True,
            publishable_key=PUBLISHABLE_KEY,
        )

    assert management.queries == []
    assert management.server_key_calls == 0
