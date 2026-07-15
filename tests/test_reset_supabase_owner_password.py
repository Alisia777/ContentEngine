from __future__ import annotations

from io import BytesIO
import json

import pytest

import scripts.reset_supabase_owner_password as reset_module
from scripts.bootstrap_supabase_owner import EXPECTED_PROJECT_REF
from scripts.reset_supabase_owner_password import (
    ONE_SHOT_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    OwnerPasswordResetError,
    SupabaseOwnerPasswordAuthClient,
    _github_actions_escape,
    _validated_owner_password,
    read_owner_reset_authority,
    reset_owner_password,
)


OWNER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"
OWNER_EMAIL = "owner@example.com"
TEMP_PASSWORD = "OneTimeOwnerPass42!"
SERVER_KEY = "sb_secret_service_role_secret_must_not_leak"


def _owner_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "user_id": OWNER_ID,
        "email_confirmed": True,
        "auth_active": True,
        "active_owner_membership_count": 1,
        "app_metadata": {"existing": "preserved"},
    }
    row.update(overrides)
    return row


class FakeManagement:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.queries: list[tuple[str, bool]] = []
        self.server_key_calls = 0

    def execute(self, sql: str, *, read_only: bool = False):
        self.queries.append((sql, read_only))
        return [dict(row) for row in self.rows]

    def get_server_key(self) -> str:
        self.server_key_calls += 1
        return SERVER_KEY


class FakeAuth:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def update_password_once(
        self,
        *,
        user_id: str,
        password: str,
        app_metadata: dict[str, object],
    ) -> None:
        self.calls.append(
            {
                "user_id": user_id,
                "password": password,
                "app_metadata": dict(app_metadata),
            }
        )


class FakeResponse:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.status = status
        self._body = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class RecordingOpener:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[object, int]] = []

    def __call__(self, api_request, timeout: int):
        self.requests.append((api_request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def test_reset_verifies_exact_authority_before_atomic_one_shot_update() -> None:
    management = FakeManagement([_owner_row()])
    auth = FakeAuth()
    captured_keys: list[str] = []

    def auth_factory(server_key: str) -> FakeAuth:
        captured_keys.append(server_key)
        return auth

    reset_owner_password(
        management_client=management,
        auth_client_factory=auth_factory,
        email=OWNER_EMAIL.upper(),
        temporary_password=TEMP_PASSWORD,
    )

    assert captured_keys == [SERVER_KEY]
    assert management.server_key_calls == 1
    assert auth.calls == [
        {
            "user_id": OWNER_ID,
            "password": TEMP_PASSWORD,
            "app_metadata": {"existing": "preserved"},
        }
    ]
    assert len(management.queries) == 1
    sql, read_only = management.queries[0]
    assert read_only is True
    assert "from auth.users auth_user" in sql
    assert "lower(auth_user.email) = 'owner@example.com'" in sql
    assert "organization.slug = 'altea-content-factory'" in sql
    assert "membership.role = 'owner'" in sql
    assert "membership.status = 'active'" in sql
    assert "organization.status = 'active'" in sql
    assert "profile.status = 'active'" in sql
    assert "limit 2" in sql


@pytest.mark.parametrize("rows", [[], [_owner_row(), _owner_row(user_id=OTHER_ID)]])
def test_reset_fails_closed_when_auth_identity_is_missing_or_ambiguous(
    rows: list[dict[str, object]],
) -> None:
    management = FakeManagement(rows)
    auth = FakeAuth()

    with pytest.raises(
        OwnerPasswordResetError,
        match="Exactly one Supabase owner identity is required",
    ):
        reset_owner_password(
            management_client=management,
            auth_client_factory=lambda _: auth,
            email=OWNER_EMAIL,
            temporary_password=TEMP_PASSWORD,
        )

    assert management.server_key_calls == 0
    assert auth.calls == []


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (_owner_row(email_confirmed=False), "identity is not confirmed"),
        (_owner_row(auth_active=False), "identity is not active"),
        (
            _owner_row(active_owner_membership_count=0),
            "Exactly one active production owner membership is required",
        ),
        (
            _owner_row(active_owner_membership_count=2),
            "Exactly one active production owner membership is required",
        ),
    ],
)
def test_reset_rejects_unconfirmed_inactive_or_wrong_membership(
    row: dict[str, object],
    message: str,
) -> None:
    management = FakeManagement([row])
    auth = FakeAuth()

    with pytest.raises(OwnerPasswordResetError, match=message):
        reset_owner_password(
            management_client=management,
            auth_client_factory=lambda _: auth,
            email=OWNER_EMAIL,
            temporary_password=TEMP_PASSWORD,
        )

    assert management.server_key_calls == 0
    assert auth.calls == []


def test_reset_is_permanently_blocked_after_one_shot_marker() -> None:
    management = FakeManagement(
        [_owner_row(app_metadata={ONE_SHOT_MARKER: True, "existing": "preserved"})]
    )
    auth = FakeAuth()

    with pytest.raises(
        OwnerPasswordResetError,
        match="password reset was already completed",
    ):
        reset_owner_password(
            management_client=management,
            auth_client_factory=lambda _: auth,
            email=OWNER_EMAIL,
            temporary_password=TEMP_PASSWORD,
        )

    assert management.server_key_calls == 0
    assert auth.calls == []


@pytest.mark.parametrize(
    "row",
    [
        _owner_row(email_confirmed="true"),
        _owner_row(auth_active=1),
        _owner_row(active_owner_membership_count=True),
        _owner_row(active_owner_membership_count="1"),
        _owner_row(app_metadata=[]),
        _owner_row(user_id="not-a-uuid"),
    ],
)
def test_authority_parser_rejects_invalid_management_sql_results(
    row: dict[str, object],
) -> None:
    with pytest.raises(OwnerPasswordResetError):
        read_owner_reset_authority(FakeManagement([row]), email=OWNER_EMAIL)


@pytest.mark.parametrize(
    "password",
    [
        "Aa1" + "x" * 14,
        "Aa1" + "x" * 126,
        "ALLUPPERCASE12345678",
        "alllowercase12345678",
        "NoDigitsInThisPassword",
        "ValidPassword123456\n",
        "ValidPassword123456\x7f",
        "ValidPassword123456\x00",
    ],
)
def test_password_policy_rejects_invalid_passwords(password: str) -> None:
    with pytest.raises(
        OwnerPasswordResetError,
        match="SUPABASE_OWNER_TEMP_PASSWORD does not meet the required policy",
    ):
        _validated_owner_password(password)


def test_password_policy_accepts_boundaries_and_required_character_classes() -> None:
    minimum = "Aa1" + "x" * 15
    maximum = "Aa1" + "x" * 125

    assert len(minimum) == 18
    assert len(maximum) == 128
    assert _validated_owner_password(minimum) == minimum
    assert _validated_owner_password(maximum) == maximum


def test_auth_admin_transport_atomically_sets_password_and_one_shot_marker() -> None:
    opener = RecordingOpener([FakeResponse({"id": OWNER_ID})])
    client = SupabaseOwnerPasswordAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=SERVER_KEY,
        opener=opener,
    )

    client.update_password_once(
        user_id=OWNER_ID,
        password=TEMP_PASSWORD,
        app_metadata={"existing": "preserved"},
    )

    assert len(opener.requests) == 1
    api_request, timeout = opener.requests[0]
    assert timeout == 60
    assert api_request.method == "PUT"
    assert api_request.full_url == (
        f"https://{EXPECTED_PROJECT_REF}.supabase.co/auth/v1/admin/users/{OWNER_ID}"
    )
    assert json.loads(api_request.data) == {
        "password": TEMP_PASSWORD,
        "app_metadata": {
            "existing": "preserved",
            ONE_SHOT_MARKER: True,
            PASSWORD_CHANGE_REQUIRED_MARKER: True,
        },
    }
    assert api_request.get_header("Apikey") == SERVER_KEY
    assert api_request.get_header("Authorization") is None
    assert OWNER_EMAIL not in api_request.data.decode("utf-8")
    assert "user_metadata" not in api_request.data.decode("utf-8")


def test_auth_admin_transport_rejects_an_unexpected_response_identity() -> None:
    opener = RecordingOpener([FakeResponse({"id": OTHER_ID})])
    client = SupabaseOwnerPasswordAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=SERVER_KEY,
        opener=opener,
    )

    with pytest.raises(
        OwnerPasswordResetError,
        match="Supabase Auth updated an unexpected identity",
    ):
        client.update_password_once(
            user_id=OWNER_ID,
            password=TEMP_PASSWORD,
            app_metadata={"existing": "preserved"},
        )


def test_auth_admin_transport_uses_bearer_only_for_legacy_service_role_key() -> None:
    legacy_key = "eyJlegacy.service_role.jwt_value_long_enough"
    opener = RecordingOpener([FakeResponse({"id": OWNER_ID})])
    client = SupabaseOwnerPasswordAuthClient(
        project_ref=EXPECTED_PROJECT_REF,
        server_key=legacy_key,
        opener=opener,
    )

    client.update_password_once(
        user_id=OWNER_ID,
        password=TEMP_PASSWORD,
        app_metadata={"existing": "preserved"},
    )

    api_request = opener.requests[0][0]
    assert api_request.get_header("Authorization") == f"Bearer {legacy_key}"
    assert api_request.get_header("Apikey") == legacy_key


def test_main_masks_password_and_email_in_actions_and_logs_only_masked_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []

    class MainFakeManagement:
        def __init__(self, *, project_ref: str, access_token: str) -> None:
            calls.append(
                {
                    "client_project_ref": project_ref,
                    "access_token_received": bool(access_token),
                }
            )

    def fake_reset(**kwargs: object) -> None:
        calls.append(
            {
                "email_received": kwargs["email"] == OWNER_EMAIL,
                "password_received": kwargs["temporary_password"] == TEMP_PASSWORD,
            }
        )

    monkeypatch.setattr(reset_module, "SupabaseManagementClient", MainFakeManagement)
    monkeypatch.setattr(reset_module, "reset_owner_password", fake_reset)
    monkeypatch.setenv("SUPABASE_PROJECT_REF", EXPECTED_PROJECT_REF)
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "management-secret")
    monkeypatch.setenv("SUPABASE_OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("SUPABASE_OWNER_TEMP_PASSWORD", TEMP_PASSWORD)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    assert reset_module.main() == 0

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines == [
        f"::add-mask::{TEMP_PASSWORD}",
        f"::add-mask::{OWNER_EMAIL}",
        "Supabase owner password reset complete: owner=*** status=updated.",
    ]
    assert captured.err == ""
    assert calls == [
        {
            "client_project_ref": EXPECTED_PROJECT_REF,
            "access_token_received": True,
        },
        {"email_received": True, "password_received": True},
    ]


def test_actions_mask_escapes_workflow_command_metacharacters() -> None:
    assert _github_actions_escape("Owner%Password42") == "Owner%25Password42"
    assert _github_actions_escape("line\r\n") == "line%0D%0A"


def test_main_rejects_wrong_project_before_any_client_or_network_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_client(**_: object):
        raise AssertionError("client must not be created")

    monkeypatch.setattr(reset_module, "SupabaseManagementClient", forbidden_client)
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "wrong-project")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "management-secret")
    monkeypatch.setenv("SUPABASE_OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("SUPABASE_OWNER_TEMP_PASSWORD", TEMP_PASSWORD)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    assert reset_module.main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert OWNER_EMAIL not in captured.err
    assert TEMP_PASSWORD not in captured.err
    assert "reviewed production project" in captured.err
