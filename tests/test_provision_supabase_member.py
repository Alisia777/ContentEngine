from __future__ import annotations

from dataclasses import replace

import pytest

from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    MemberProvisionError,
    MemberState,
    ProvisioningAuthority,
    provision_member,
)


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
MEMBER_ID = "33333333-3333-4333-8333-333333333333"
MEMBER_EMAIL = "guest@example.com"
TEMP_PASSWORD = "StrongTemporary42Password"


class FakeManagement:
    def __init__(self, state: MemberState) -> None:
        self.state = state
        self.server_key_calls = 0
        self.queries: list[dict[str, object]] = []

    def execute(self, sql: str, *, read_only: bool = False):
        self.queries.append({"sql": sql, "read_only": read_only})
        if "from content_factory.organizations organization" in sql:
            return [
                {
                    "organization_id": ORGANIZATION_ID,
                    "invited_by": OWNER_ID,
                }
            ]
        if "from auth.users auth_user" in sql:
            if self.state.user_id is None:
                return []
            return [
                {
                    "user_id": self.state.user_id,
                    "email_confirmed": self.state.email_confirmed,
                    "auth_active": self.state.auth_active,
                    "signed_in": self.state.signed_in,
                    "app_metadata": dict(self.state.app_metadata or {}),
                    "membership_count": self.state.membership_count,
                    "membership_role": self.state.membership_role,
                    "membership_status": self.state.membership_status,
                }
            ]
        if "system_provision_limited_member" in sql:
            role = "viewer" if "'role', 'viewer'" in sql else "trainee"
            self.state = replace(
                self.state,
                membership_count=1,
                membership_role=role,
                membership_status="active",
            )
            return [{"result": {"ok": True, "role": role}}]
        raise AssertionError("unexpected management query")

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return "sb_secret_member_provision_test_key"


class FakeAuth:
    def __init__(self, management: FakeManagement) -> None:
        self.management = management
        self.calls: list[dict[str, object]] = []

    def create_confirmed_user_with_password(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        app_metadata: dict[str, object],
    ) -> None:
        self.calls.append(
            {
                "email": email,
                "display_name": display_name,
                "password": password,
                "app_metadata": dict(app_metadata),
            }
        )
        self.management.state = MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            app_metadata=dict(app_metadata),
        )

    def claim_confirmed_user_with_password(
        self,
        *,
        user_id: str,
        display_name: str,
        password: str,
        app_metadata: dict[str, object],
    ) -> None:
        self.calls.append(
            {
                "claim_user_id": user_id,
                "display_name": display_name,
                "password": password,
                "app_metadata": dict(app_metadata),
            }
        )
        self.management.state = replace(
            self.management.state,
            app_metadata=dict(app_metadata),
        )


def _factory(auth: FakeAuth, captured_keys: list[str]):
    def build(server_key: str):
        captured_keys.append(server_key)
        return auth

    return build


@pytest.mark.parametrize("role", ["viewer", "trainee"])
def test_fresh_member_is_created_confirmed_with_exact_limited_role(role: str) -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))
    auth = FakeAuth(management)
    keys: list[str] = []

    result = provision_member(
        management_client=management,
        auth_client_factory=_factory(auth, keys),
        email=MEMBER_EMAIL,
        display_name="Guest",
        temporary_password=TEMP_PASSWORD,
        role=role,
    )

    assert result.identity_status == "created"
    assert result.membership_status == "created"
    assert result.role == role
    assert keys == ["sb_secret_member_provision_test_key"]
    assert auth.calls == [
        {
            "email": MEMBER_EMAIL,
            "display_name": "Guest",
            "password": TEMP_PASSWORD,
            "app_metadata": {MEMBER_PROVISION_MARKER: True},
        }
    ]
    assert management.state.membership_role == role


def test_completed_member_replay_never_resets_password_or_reveals_key() -> None:
    management = FakeManagement(
        MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            app_metadata={MEMBER_PROVISION_MARKER: True},
            membership_count=1,
            membership_role="viewer",
            membership_status="active",
        )
    )
    auth = FakeAuth(management)

    result = provision_member(
        management_client=management,
        auth_client_factory=_factory(auth, []),
        email=MEMBER_EMAIL,
        display_name="Guest",
        temporary_password=TEMP_PASSWORD,
        role="viewer",
    )

    assert result.identity_status == "existing"
    assert result.membership_status == "existing"
    assert auth.calls == []
    assert management.server_key_calls == 0


def test_marked_identity_can_resume_after_membership_failure() -> None:
    management = FakeManagement(
        MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            app_metadata={MEMBER_PROVISION_MARKER: True},
        )
    )
    auth = FakeAuth(management)

    result = provision_member(
        management_client=management,
        auth_client_factory=_factory(auth, []),
        email=MEMBER_EMAIL,
        display_name="Guest",
        temporary_password=TEMP_PASSWORD,
        role="viewer",
    )

    assert result.identity_status == "existing"
    assert result.membership_status == "created"
    assert auth.calls == []
    assert management.server_key_calls == 0


def test_explicit_claim_recovers_unsigned_in_membership_free_identity() -> None:
    management = FakeManagement(
        MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            signed_in=False,
            app_metadata={"provider": "email", "providers": ["email"]},
        )
    )
    auth = FakeAuth(management)

    result = provision_member(
        management_client=management,
        auth_client_factory=_factory(auth, []),
        email=MEMBER_EMAIL,
        display_name="Guest",
        temporary_password=TEMP_PASSWORD,
        role="viewer",
        claim_existing=True,
    )

    assert result.identity_status == "claimed"
    assert result.membership_status == "created"
    assert auth.calls == [{
        "claim_user_id": MEMBER_ID,
        "display_name": "Guest",
        "password": TEMP_PASSWORD,
        "app_metadata": {
            "provider": "email",
            "providers": ["email"],
            MEMBER_PROVISION_MARKER: True,
        },
    }]


def test_explicit_reset_recovers_signed_in_membership_free_identity() -> None:
    management = FakeManagement(
        MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            signed_in=True,
            app_metadata={"provider": "email", "providers": ["email"]},
        )
    )
    auth = FakeAuth(management)

    result = provision_member(
        management_client=management,
        auth_client_factory=_factory(auth, []),
        email=MEMBER_EMAIL,
        display_name="Guest",
        temporary_password=TEMP_PASSWORD,
        role="viewer",
        claim_existing=True,
        reset_signed_in=True,
    )

    assert result.identity_status == "reset"
    assert result.membership_status == "created"
    assert management.state.membership_role == "viewer"
    assert auth.calls[0]["claim_user_id"] == MEMBER_ID
    assert auth.calls[0]["password"] == TEMP_PASSWORD


@pytest.mark.parametrize(
    "state, message",
    [
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                signed_in=True,
                app_metadata={},
            ),
            "already signed in",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                membership_count=1,
                app_metadata={},
            ),
            "belongs to an organization",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                app_metadata={"contentengine_bootstrap_owner": True},
            ),
            "conflicting provisioning metadata",
        ),
    ],
)
def test_explicit_claim_still_fails_closed_for_used_identity(
    state: MemberState,
    message: str,
) -> None:
    management = FakeManagement(state)
    auth = FakeAuth(management)

    with pytest.raises(MemberProvisionError, match=message):
        provision_member(
            management_client=management,
            auth_client_factory=_factory(auth, []),
            email=MEMBER_EMAIL,
            display_name="Guest",
            temporary_password=TEMP_PASSWORD,
            role="viewer",
            claim_existing=True,
        )

    assert auth.calls == []


@pytest.mark.parametrize(
    "state, message",
    [
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=False,
                app_metadata={MEMBER_PROVISION_MARKER: True},
            ),
            "not confirmed",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                auth_active=False,
                app_metadata={MEMBER_PROVISION_MARKER: True},
            ),
            "identity is not active",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                app_metadata={},
            ),
            "not owned",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                app_metadata={MEMBER_PROVISION_MARKER: True},
                membership_count=1,
            ),
            "another organization",
        ),
        (
            MemberState(
                user_id=MEMBER_ID,
                email_confirmed=True,
                app_metadata={MEMBER_PROVISION_MARKER: True},
                membership_count=1,
                membership_role="trainee",
                membership_status="active",
            ),
            "unexpected role",
        ),
    ],
)
def test_preexisting_identity_conflicts_fail_closed(
    state: MemberState,
    message: str,
) -> None:
    management = FakeManagement(state)
    auth = FakeAuth(management)

    with pytest.raises(MemberProvisionError, match=message):
        provision_member(
            management_client=management,
            auth_client_factory=_factory(auth, []),
            email=MEMBER_EMAIL,
            display_name="Guest",
            temporary_password=TEMP_PASSWORD,
            role="viewer",
        )

    assert auth.calls == []
    assert not any(
        "system_provision_limited_member" in str(query["sql"])
        for query in management.queries
    )


@pytest.mark.parametrize(
    "password",
    ["", "shortA1", "alllowercase123456", "ALLUPPERCASE123456", "NoDigitsHereLong"],
)
def test_temporary_password_is_rejected_before_remote_calls(password: str) -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))

    with pytest.raises(MemberProvisionError, match="PASSWORD"):
        provision_member(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build auth client"),
            email=MEMBER_EMAIL,
            display_name="Guest",
            temporary_password=password,
            role="viewer",
        )

    assert management.queries == []


def test_privileged_or_unknown_roles_are_rejected_before_remote_calls() -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))

    with pytest.raises(MemberProvisionError, match="trainee or viewer"):
        provision_member(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build auth client"),
            email=MEMBER_EMAIL,
            display_name="Guest",
            temporary_password=TEMP_PASSWORD,
            role="owner",
        )

    assert management.queries == []


def test_authority_value_type_is_explicit() -> None:
    authority = ProvisioningAuthority(
        organization_id=ORGANIZATION_ID,
        invited_by=OWNER_ID,
    )

    assert authority.organization_id == ORGANIZATION_ID
