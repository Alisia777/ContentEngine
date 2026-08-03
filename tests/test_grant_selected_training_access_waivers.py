from __future__ import annotations

from dataclasses import replace

import pytest

from scripts.grant_training_access_waiver import TrainingWaiverError
from scripts.grant_selected_training_access_waivers import (
    SELECTED_SLOTS,
    grant_selected_training_access_waivers,
)
from scripts.provision_supabase_member import MemberState


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
GUEST_ID = "33333333-3333-4333-8333-333333333333"
KLIMOV_ID = "44444444-4444-4444-8444-444444444444"
GUEST_EMAIL = "guest@example.com"
KLIMOV_EMAIL = "klimov@example.com"
OWNER_EMAIL = "owner@example.com"


class FakeManagement:
    def __init__(
        self,
        *,
        owner_role: str = "owner",
        batch_ready: bool = True,
    ) -> None:
        self.states = {
            GUEST_EMAIL: MemberState(
                user_id=GUEST_ID,
                email_confirmed=True,
                membership_count=1,
                membership_role="viewer",
                membership_status="active",
            ),
            KLIMOV_EMAIL: MemberState(
                user_id=KLIMOV_ID,
                email_confirmed=True,
                membership_count=1,
                membership_role="viewer",
                membership_status="active",
            ),
            OWNER_EMAIL: MemberState(
                user_id=OWNER_ID,
                email_confirmed=True,
                membership_count=1,
                membership_role=owner_role,
                membership_status="active",
            ),
        }
        self.queries: list[dict[str, object]] = []
        self.granted = False
        self.batch_ready = batch_ready

    def execute(self, sql: str, *, read_only: bool = False):
        self.queries.append({"sql": sql, "read_only": read_only})
        if "to_regprocedure" in sql:
            return [{"batch_ready": self.batch_ready}]
        if "from content_factory.organizations organization" in sql:
            return [{"organization_id": ORGANIZATION_ID, "invited_by": OWNER_ID}]
        if "from auth.users auth_user" in sql:
            state = next(
                (state for email, state in self.states.items() if f"'{email}'" in sql),
                None,
            )
            if state is None:
                return []
            return [{
                "user_id": state.user_id,
                "email_confirmed": state.email_confirmed,
                "auth_active": state.auth_active,
                "signed_in": state.signed_in,
                "app_metadata": dict(state.app_metadata or {}),
                "membership_count": state.membership_count,
                "membership_role": state.membership_role,
                "membership_status": state.membership_status,
            }]
        if "system_grant_training_access_waiver_batch" in sql:
            self.granted = True
            self.states[GUEST_EMAIL] = replace(
                self.states[GUEST_EMAIL], membership_role="operator"
            )
            self.states[KLIMOV_EMAIL] = replace(
                self.states[KLIMOV_EMAIL], membership_role="operator"
            )
            return [{"result": {"ok": True, "target_count": 3}}]
        if "training_access_waiver_active" in sql:
            if not self.granted:
                return []
            return [
                {
                    "user_id": GUEST_ID,
                    "role": "operator",
                    "membership_status": "active",
                    "waiver_status": "active",
                    "scope": "workspace_generation",
                    "waiver_active": True,
                },
                {
                    "user_id": KLIMOV_ID,
                    "role": "operator",
                    "membership_status": "active",
                    "waiver_status": "active",
                    "scope": "workspace_generation",
                    "waiver_active": True,
                },
                {
                    "user_id": OWNER_ID,
                    "role": "owner",
                    "membership_status": "active",
                    "waiver_status": "active",
                    "scope": "workspace_generation",
                    "waiver_active": True,
                },
            ]
        raise AssertionError("unexpected management query")


def _grant(management: FakeManagement):
    return grant_selected_training_access_waivers(
        management_client=management,
        guest_email=GUEST_EMAIL,
        klimov_email=KLIMOV_EMAIL,
        artiukhins_email=OWNER_EMAIL,
    )


def test_selected_slots_are_granted_in_one_mutation_without_email_literals() -> None:
    management = FakeManagement()

    targets = _grant(management)

    assert tuple(target.slot for target in targets) == SELECTED_SLOTS
    assert tuple(target.previous_role for target in targets) == (
        "viewer",
        "viewer",
        "owner",
    )
    assert tuple(target.granted_role for target in targets) == (
        "operator",
        "operator",
        "owner",
    )
    mutations = [
        str(query["sql"])
        for query in management.queries
        if not query["read_only"]
        and "system_grant_training_access_waiver_batch" in str(query["sql"])
    ]
    assert len(mutations) == 1
    assert all(email not in mutations[0] for email in (
        GUEST_EMAIL,
        KLIMOV_EMAIL,
        OWNER_EMAIL,
    ))
    assert "'role', 'operator'" in mutations[0]
    assert "'role', 'owner'" in mutations[0]
    assert "training_certifications" not in mutations[0]
    assert "training_attempts" not in mutations[0]


def test_duplicate_protected_slots_fail_before_any_database_mutation() -> None:
    management = FakeManagement()

    with pytest.raises(TrainingWaiverError, match="must be distinct"):
        grant_selected_training_access_waivers(
            management_client=management,
            guest_email=GUEST_EMAIL,
            klimov_email=GUEST_EMAIL,
            artiukhins_email=OWNER_EMAIL,
        )

    assert management.queries == []


def test_missing_batch_migration_fails_before_identity_reads_or_mutation() -> None:
    management = FakeManagement(batch_ready=False)

    with pytest.raises(TrainingWaiverError, match="migration is not deployed"):
        _grant(management)

    assert len(management.queries) == 1
    assert management.queries[0]["read_only"] is True
    assert "to_regprocedure" in str(management.queries[0]["sql"])


def test_artiukhins_must_be_owner_and_is_never_demoted() -> None:
    management = FakeManagement(owner_role="viewer")

    with pytest.raises(TrainingWaiverError, match="protected owner account"):
        _grant(management)

    assert not any(
        not query["read_only"]
        and "system_grant_training_access_waiver_batch" in str(query["sql"])
        for query in management.queries
    )
