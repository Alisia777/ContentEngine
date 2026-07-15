from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import scripts.provision_supabase_member as provision_module

from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    MemberProvisionError,
    MemberProvisionPlan,
    MemberState,
    ProvisioningAuthority,
    plan_member,
    provision_member,
)


ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
OWNER_ID = "22222222-2222-4222-8222-222222222222"
MEMBER_ID = "33333333-3333-4333-8333-333333333333"
MEMBER_EMAIL = "guest@example.com"
TEMP_PASSWORD = "StrongTemporary42Password"
ROOT = Path(__file__).resolve().parents[1]


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


def test_preview_of_fresh_member_is_read_only_and_needs_no_password() -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))

    plan = plan_member(
        management_client=management,
        email=MEMBER_EMAIL,
        display_name="Guest",
        role="viewer",
    )

    assert plan == MemberProvisionPlan(
        identity_action="create",
        membership_action="create",
        role="viewer",
    )
    assert plan.apply_required is True
    assert management.server_key_calls == 0
    assert len(management.queries) == 2
    assert all(query["read_only"] is True for query in management.queries)
    assert not any(
        "system_provision_limited_member" in str(query["sql"])
        for query in management.queries
    )


def test_preview_of_completed_member_is_an_idempotent_noop() -> None:
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

    plan = plan_member(
        management_client=management,
        email=MEMBER_EMAIL,
        display_name="Guest",
        role="viewer",
    )

    assert plan.identity_action == "keep"
    assert plan.membership_action == "keep"
    assert plan.apply_required is False
    assert management.server_key_calls == 0


def test_preview_can_describe_but_not_execute_an_explicit_stale_identity_reset() -> None:
    management = FakeManagement(
        MemberState(
            user_id=MEMBER_ID,
            email_confirmed=True,
            signed_in=True,
            app_metadata={"provider": "email", "providers": ["email"]},
        )
    )

    plan = plan_member(
        management_client=management,
        email=MEMBER_EMAIL,
        display_name="Guest",
        role="viewer",
        claim_existing=True,
        reset_signed_in=True,
    )

    assert plan.identity_action == "reset"
    assert plan.membership_action == "create"
    assert management.server_key_calls == 0
    assert management.state.app_metadata == {
        "provider": "email",
        "providers": ["email"],
    }


def test_second_access_must_use_a_distinct_normalized_email() -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))

    with pytest.raises(MemberProvisionError, match="distinct email"):
        plan_member(
            management_client=management,
            email="Member.One@Example.Invalid",
            display_name="V. Klimov second access",
            role="viewer",
            distinct_from=["member.one@example.invalid"],
        )

    assert management.queries == []


def test_preview_cli_does_not_require_or_read_a_temporary_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    management = FakeManagement(MemberState(user_id=None, app_metadata={}))
    monkeypatch.setattr(
        provision_module,
        "SupabaseManagementClient",
        lambda **_kwargs: management,
    )
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "iyckwryrucqrxwlowxow")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "test-management-token")
    monkeypatch.setenv("SUPABASE_MEMBER_TEMP_PASSWORD", "preview-must-not-read-this")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    exit_code = provision_module.main([
        "--email",
        MEMBER_EMAIL,
        "--display-name",
        "Guest",
        "--role",
        "viewer",
        "--dry-run",
    ])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "provisioning preview" in output
    assert "identity=create" in output
    assert "membership=create" in output
    assert "apply_required=true" in output
    assert "::add-mask::" not in output
    assert "preview-must-not-read-this" not in output
    assert management.server_key_calls == 0


def test_portal_schema_requires_distinct_email_identity_and_one_org_membership() -> None:
    core = (ROOT / "supabase/migrations/202607130001_content_factory_core.sql").read_text(
        encoding="utf-8"
    )

    assert "create unique index if not exists profiles_email_lower_uq" in core
    assert "on content_factory.profiles (lower(email))" in core
    assert "constraint memberships_org_profile_uq unique (organization_id, profile_id)" in core


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
            "app_metadata": {
                MEMBER_PROVISION_MARKER: True,
                PASSWORD_CHANGE_REQUIRED_MARKER: True,
            },
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
            PASSWORD_CHANGE_REQUIRED_MARKER: True,
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
