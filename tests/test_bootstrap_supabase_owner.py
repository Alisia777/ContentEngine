from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from urllib import error

import pytest

from scripts.bootstrap_supabase_owner import (
    EXPECTED_PROJECT_REF,
    OWNER_RECOVERY_MARKER,
    OWNER_RECOVERY_REDIRECT,
    OwnerBootstrapError,
    OwnerState,
    SupabaseAuthClient,
    SupabaseManagementClient,
    bootstrap_owner,
)


OWNER_ID = "11111111-1111-4111-8111-111111111111"
OWNER_EMAIL = "owner@example.com"
PUBLISHABLE_KEY = "sb_publishable_browser_safe_test_key"
SERVER_KEY = "sb_secret_service_role_secret_must_not_leak"


class FakeManagement:
    def __init__(self, state: OwnerState) -> None:
        self.state = state
        self.server_key_calls = 0
        self.queries: list[dict[str, object]] = []

    def execute(self, sql: str, *, read_only: bool = False):
        self.queries.append({"sql": sql, "read_only": read_only})
        if "from auth.users auth_user" in sql:
            if self.state.user_id is None:
                return []
            return [
                {
                    "user_id": self.state.user_id,
                    "email_confirmed": self.state.email_confirmed,
                    "signed_in": self.state.signed_in,
                    "owner_active": self.state.owner_active,
                    "app_metadata": dict(self.state.app_metadata or {}),
                }
            ]
        if "system_initialize_owner" in sql:
            self.state = replace(self.state, owner_active=True)
            return [{"result": {"ok": True}}]
        raise AssertionError("unexpected management query")

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


class FakeAuth:
    def __init__(self, management: FakeManagement) -> None:
        self.management = management
        self.calls: list[tuple[str, object]] = []

    def create_confirmed_user(self, *, email: str, display_name: str) -> None:
        self.calls.append(("create", (email, display_name)))
        self.management.state = OwnerState(
            user_id=OWNER_ID,
            email_confirmed=True,
            app_metadata={"contentengine_bootstrap_owner": True},
        )

    def send_password_recovery(self, *, email: str) -> None:
        self.calls.append(("recover", email))

    def update_app_metadata(self, user_id: str, metadata: dict[str, object]) -> None:
        self.calls.append(("metadata", (user_id, dict(metadata))))
        self.management.state = replace(
            self.management.state,
            app_metadata=dict(metadata),
        )


def _factory(auth: FakeAuth, captured_keys: list[str]):
    def build(server_key: str):
        captured_keys.append(server_key)
        return auth

    return build


def test_fresh_project_creates_owner_and_sends_one_password_setup_email() -> None:
    management = FakeManagement(OwnerState(user_id=None, app_metadata={}))
    auth = FakeAuth(management)
    keys: list[str] = []

    result = bootstrap_owner(
        management_client=management,
        auth_client_factory=_factory(auth, keys),
        email=OWNER_EMAIL,
        display_name="Owner",
    )

    assert result.identity_status == "created"
    assert result.membership_status == "created"
    assert result.recovery_status == "sent"
    assert keys == [SERVER_KEY]
    assert [call[0] for call in auth.calls] == ["create", "metadata", "recover", "metadata"]
    assert management.state.owner_active is True
    assert management.state.app_metadata[OWNER_RECOVERY_MARKER] is True
    assert management.state.app_metadata["contentengine_password_change_required"] is True
    assert sum(
        "system_initialize_owner" in str(query["sql"])
        for query in management.queries
    ) == 1


def test_completed_owner_is_idempotent_and_does_not_reveal_server_key() -> None:
    management = FakeManagement(
        OwnerState(
            user_id=OWNER_ID,
            email_confirmed=True,
            owner_active=True,
            app_metadata={OWNER_RECOVERY_MARKER: True},
        )
    )
    auth = FakeAuth(management)
    keys: list[str] = []

    result = bootstrap_owner(
        management_client=management,
        auth_client_factory=_factory(auth, keys),
        email=OWNER_EMAIL,
        display_name="Owner",
    )

    assert result.identity_status == "existing"
    assert result.membership_status == "existing"
    assert result.recovery_status == "not_required"
    assert keys == []
    assert auth.calls == []
    assert management.server_key_calls == 0


def test_existing_unconfirmed_identity_fails_closed_before_owner_rpc() -> None:
    management = FakeManagement(
        OwnerState(user_id=OWNER_ID, email_confirmed=False, app_metadata={})
    )
    auth = FakeAuth(management)

    with pytest.raises(OwnerBootstrapError, match="manual review required"):
        bootstrap_owner(
            management_client=management,
            auth_client_factory=_factory(auth, []),
            email=OWNER_EMAIL,
            display_name="Owner",
        )

    assert auth.calls == []
    assert management.state.owner_active is False
    assert management.server_key_calls == 0


def test_already_signed_in_owner_never_receives_automatic_recovery() -> None:
    management = FakeManagement(
        OwnerState(
            user_id=OWNER_ID,
            email_confirmed=True,
            signed_in=True,
            owner_active=False,
            app_metadata={},
        )
    )
    auth = FakeAuth(management)

    result = bootstrap_owner(
        management_client=management,
        auth_client_factory=_factory(auth, []),
        email=OWNER_EMAIL,
        display_name="Owner",
    )

    assert result.membership_status == "created"
    assert result.recovery_status == "not_required"
    assert auth.calls == []


@pytest.mark.parametrize(
    "email",
    ["", "not-an-email", "double..dot@example.com", "owner@localhost"],
)
def test_owner_email_is_validated_before_any_remote_call(email: str) -> None:
    management = FakeManagement(OwnerState(user_id=None, app_metadata={}))

    with pytest.raises(OwnerBootstrapError, match="SUPABASE_OWNER_EMAIL is invalid"):
        bootstrap_owner(
            management_client=management,
            auth_client_factory=lambda _key: pytest.fail("must not build auth client"),
            email=email,
            display_name="Owner",
        )

    assert management.queries == []


class FakeResponse:
    def __init__(self, payload, *, status: int = 200) -> None:
        self.status = status
        self._body = (
            b""
            if payload is None
            else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )

    def read(self, _limit: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RecordingOpener:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, api_request, *, timeout: int):
        self.requests.append((api_request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_management_client_prefers_new_service_role_secret_key(
    monkeypatch,
    capsys,
) -> None:
    opener = RecordingOpener(
        [
            FakeResponse(
                [
                    {"name": "anon", "api_key": "anon-key"},
                    {
                        "name": "owner-bootstrap",
                        "type": "secret",
                        "api_key": SERVER_KEY,
                        "secret_jwt_template": {"role": "service_role"},
                    },
                    {
                        "name": "service_role",
                        "type": "legacy",
                        "api_key": "legacy-service-role-secret-key",
                    },
                ]
            )
        ]
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    client = SupabaseManagementClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="management-token",
        opener=opener,
    )

    assert client.get_server_key() == SERVER_KEY
    api_request, timeout = opener.requests[0]
    assert api_request.full_url.endswith("/api-keys?reveal=true")
    assert api_request.get_method() == "GET"
    assert api_request.get_header("Authorization") == "Bearer management-token"
    assert timeout == 60
    assert capsys.readouterr().out.strip() == f"::add-mask::{SERVER_KEY}"


def test_management_client_falls_back_to_legacy_service_role_key() -> None:
    opener = RecordingOpener(
        [
            FakeResponse(
                [
                    {"name": "anon", "api_key": "anon-key-not-selected"},
                    {
                        "name": "service_role",
                        "type": "legacy",
                        "api_key": "legacy-service-role-secret-key",
                    },
                ]
            )
        ]
    )
    client = SupabaseManagementClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="management-token",
        opener=opener,
    )

    assert client.get_server_key() == "legacy-service-role-secret-key"


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [{"name": "anon", "api_key": "anon-key"}],
        [
            {"name": "service_role", "api_key": "one"},
            {"name": "service_role", "api_key": "two"},
        ],
    ],
)
def test_management_client_fails_closed_on_missing_or_ambiguous_server_key(
    payload,
) -> None:
    client = SupabaseManagementClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="management-token",
        opener=RecordingOpener([FakeResponse(payload)]),
    )

    with pytest.raises(OwnerBootstrapError, match="Exactly one revealed"):
        client.get_server_key()


def test_auth_client_uses_server_key_only_for_admin_and_publishable_for_recovery() -> None:
    opener = RecordingOpener(
        [FakeResponse({"id": OWNER_ID}), FakeResponse({}), FakeResponse({})]
    )
    client = SupabaseAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=SERVER_KEY,
        publishable_key=PUBLISHABLE_KEY,
        opener=opener,
    )

    client.create_confirmed_user(email=OWNER_EMAIL, display_name="Owner")
    client.send_password_recovery(email=OWNER_EMAIL)
    client.update_app_metadata(OWNER_ID, {OWNER_RECOVERY_MARKER: True})

    create_request = opener.requests[0][0]
    create_payload = json.loads(create_request.data)
    assert create_request.full_url.endswith("/auth/v1/admin/users")
    assert create_payload["email_confirm"] is True
    assert "password" not in create_payload
    assert create_request.get_header("Authorization") is None
    assert create_request.get_header("Apikey") == SERVER_KEY

    recovery_request = opener.requests[1][0]
    assert recovery_request.full_url.startswith(
        f"https://{EXPECTED_PROJECT_REF}.supabase.co/auth/v1/recover?redirect_to="
    )
    assert OWNER_RECOVERY_REDIRECT not in recovery_request.full_url
    assert recovery_request.get_header("Authorization") is None
    assert recovery_request.get_header("Apikey") == PUBLISHABLE_KEY
    assert SERVER_KEY not in recovery_request.full_url
    assert SERVER_KEY not in recovery_request.data.decode("utf-8")


def test_auth_client_keeps_bearer_header_for_legacy_service_role_jwt() -> None:
    legacy_key = "eyJlegacy.service_role.jwt_value_long_enough"
    opener = RecordingOpener([FakeResponse({"id": OWNER_ID})])
    client = SupabaseAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=legacy_key,
        publishable_key=PUBLISHABLE_KEY,
        opener=opener,
    )

    client.create_confirmed_user(email=OWNER_EMAIL, display_name="Owner")

    api_request = opener.requests[0][0]
    assert api_request.get_header("Authorization") == f"Bearer {legacy_key}"
    assert api_request.get_header("Apikey") == legacy_key


def test_auth_client_can_create_confirmed_member_with_temporary_password() -> None:
    opener = RecordingOpener([FakeResponse({"id": OWNER_ID})])
    client = SupabaseAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=SERVER_KEY,
        publishable_key=PUBLISHABLE_KEY,
        opener=opener,
    )

    client.create_confirmed_user_with_password(
        email=OWNER_EMAIL,
        display_name="Guest",
        password="StrongTemporary42Password",
        app_metadata={"contentengine_github_member_provisioned": True},
    )

    api_request = opener.requests[0][0]
    payload = json.loads(api_request.data)
    assert payload == {
        "email": OWNER_EMAIL,
        "password": "StrongTemporary42Password",
        "email_confirm": True,
        "user_metadata": {"display_name": "Guest"},
        "app_metadata": {"contentengine_github_member_provisioned": True},
    }
    assert api_request.get_header("Apikey") == SERVER_KEY
    assert api_request.get_header("Authorization") is None


def test_http_failures_never_include_secret_response_body() -> None:
    secret_body = b"database error containing sb_secret_service_role_secret_must_not_leak"
    failure = error.HTTPError(
        "https://api.supabase.com/v1/projects/project/api-keys",
        500,
        "server error",
        {},
        BytesIO(secret_body),
    )
    client = SupabaseManagementClient(
        project_ref=EXPECTED_PROJECT_REF,
        access_token="management-token",
        opener=RecordingOpener([failure]),
    )

    with pytest.raises(OwnerBootstrapError) as exc_info:
        client.get_server_key()

    assert SERVER_KEY not in str(exc_info.value)
