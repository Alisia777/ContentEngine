#!/usr/bin/env python3
"""Reset the reviewed production owner's Supabase password once.

This utility is intentionally narrow: it accepts only protected environment
variables, verifies the exact production project and owner relationship through
the Supabase Management API, and then atomically changes the matching Auth
user's password while adding a protected one-shot marker to preserved app
metadata. It never prints the email, password, access token, or server key.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import unicodedata
from typing import Any, Callable, Protocol
from urllib import request

from scripts.bootstrap_supabase_owner import (
    EXPECTED_PROJECT_REF,
    OWNER_ORGANIZATION_SLUG,
    OwnerBootstrapError,
    SupabaseManagementClient,
    _http_json,
    _rows_from_response,
    _sql_literal,
    _validated_email,
    _validated_uuid,
)


MIN_PASSWORD_LENGTH = 18
MAX_PASSWORD_LENGTH = 128
ONE_SHOT_MARKER = "contentengine_owner_password_reset_once_20260714"
PASSWORD_CHANGE_REQUIRED_MARKER = "contentengine_password_change_required"
PASSWORD_CHANGE_COMPLETED_MARKER = "contentengine_password_change_completed"


class OwnerPasswordResetError(RuntimeError):
    """A non-sensitive owner-password-reset failure safe for CI logs."""


@dataclass(frozen=True)
class OwnerResetAuthority:
    user_id: str
    active_owner_membership_count: int
    app_metadata: dict[str, Any]


class ManagementClient(Protocol):
    def execute(self, sql: str, *, read_only: bool = False) -> Any: ...

    def get_server_key(self) -> str: ...


class PasswordAuthClient(Protocol):
    def update_password_once(
        self,
        *,
        user_id: str,
        password: str,
        app_metadata: dict[str, Any],
    ) -> None: ...


def _validated_owner_password(value: str) -> str:
    password = str(value or "")
    if (
        not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH
        or re.search(r"[a-z]", password) is None
        or re.search(r"[A-Z]", password) is None
        or re.search(r"[0-9]", password) is None
        or any(unicodedata.category(character) == "Cc" for character in password)
    ):
        raise OwnerPasswordResetError(
            "SUPABASE_OWNER_TEMP_PASSWORD does not meet the required policy"
        )
    return password


def read_owner_reset_authority(
    client: ManagementClient,
    *,
    email: str,
) -> OwnerResetAuthority:
    """Resolve one active, confirmed Auth user with one exact owner membership."""

    normalized_email = _validated_email(email)
    payload = client.execute(
        f"""
select
  auth_user.id::text as user_id,
  auth_user.email_confirmed_at is not null as email_confirmed,
  coalesce(auth_user.raw_app_meta_data, '{{}}'::jsonb) as app_metadata,
  (
    auth_user.deleted_at is null
    and (auth_user.banned_until is null or auth_user.banned_until <= now())
  ) as auth_active,
  (
    select count(*)::integer
    from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id = membership.organization_id
    join content_factory.profiles profile
      on profile.id = membership.profile_id
    where membership.profile_id = auth_user.id
      and membership.status = 'active'
      and membership.role = 'owner'
      and organization.slug = {_sql_literal(OWNER_ORGANIZATION_SLUG)}
      and organization.status = 'active'
      and profile.status = 'active'
  ) as active_owner_membership_count
from auth.users auth_user
where lower(auth_user.email) = {_sql_literal(normalized_email)}
order by auth_user.created_at, auth_user.id
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise OwnerPasswordResetError(
            "Exactly one Supabase owner identity is required"
        )

    row = rows[0]
    if not isinstance(row.get("email_confirmed"), bool) or not isinstance(
        row.get("auth_active"), bool
    ):
        raise OwnerPasswordResetError("Supabase owner state response was invalid")
    membership_count = row.get("active_owner_membership_count")
    if isinstance(membership_count, bool) or not isinstance(membership_count, int):
        raise OwnerPasswordResetError("Supabase owner state response was invalid")
    if not row["email_confirmed"]:
        raise OwnerPasswordResetError("Supabase owner identity is not confirmed")
    if not row["auth_active"]:
        raise OwnerPasswordResetError("Supabase owner identity is not active")
    if membership_count != 1:
        raise OwnerPasswordResetError(
            "Exactly one active production owner membership is required"
        )
    app_metadata = row.get("app_metadata")
    if not isinstance(app_metadata, dict):
        raise OwnerPasswordResetError("Supabase owner metadata was invalid")
    if ONE_SHOT_MARKER in app_metadata:
        raise OwnerPasswordResetError(
            "Production owner password reset was already completed"
        )
    try:
        user_id = _validated_uuid(row.get("user_id"))
    except OwnerBootstrapError as exc:
        raise OwnerPasswordResetError(
            "Supabase owner state response was invalid"
        ) from exc
    return OwnerResetAuthority(
        user_id=user_id,
        active_owner_membership_count=membership_count,
        app_metadata=dict(app_metadata),
    )


class SupabaseOwnerPasswordAuthClient:
    """Minimal Auth Admin client for the atomic one-shot owner reset."""

    def __init__(
        self,
        *,
        project_ref: str,
        server_key: str,
        opener: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = 60,
    ) -> None:
        if project_ref != EXPECTED_PROJECT_REF:
            raise OwnerPasswordResetError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if not str(server_key or "").strip():
            raise OwnerPasswordResetError("Supabase server key is unavailable")
        self._origin = f"https://{project_ref}.supabase.co"
        self._server_key = server_key.strip()
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self._server_key,
            "User-Agent": "ContentEngine-Owner-Password-Reset/1",
        }
        if not self._server_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._server_key}"
        return headers

    def update_password_once(
        self,
        *,
        user_id: str,
        password: str,
        app_metadata: dict[str, Any],
    ) -> None:
        validated_user_id = _validated_uuid(user_id)
        validated_password = _validated_owner_password(password)
        if not isinstance(app_metadata, dict) or ONE_SHOT_MARKER in app_metadata:
            raise OwnerPasswordResetError("Supabase owner metadata was invalid")
        marked_metadata = dict(app_metadata)
        marked_metadata[ONE_SHOT_MARKER] = True
        marked_metadata[PASSWORD_CHANGE_REQUIRED_MARKER] = True
        marked_metadata.pop(PASSWORD_CHANGE_COMPLETED_MARKER, None)
        payload = _http_json(
            opener=self._opener,
            url=f"{self._origin}/auth/v1/admin/users/{validated_user_id}",
            method="PUT",
            headers=self._headers,
            payload={
                "password": validated_password,
                "app_metadata": marked_metadata,
            },
            timeout_seconds=self._timeout_seconds,
        )
        if not isinstance(payload, dict):
            raise OwnerPasswordResetError("Supabase Auth update response was invalid")
        try:
            response_user_id = _validated_uuid(payload.get("id"))
        except OwnerBootstrapError as exc:
            raise OwnerPasswordResetError(
                "Supabase Auth update response was invalid"
            ) from exc
        if response_user_id != validated_user_id:
            raise OwnerPasswordResetError(
                "Supabase Auth updated an unexpected identity"
            )


def reset_owner_password(
    *,
    management_client: ManagementClient,
    auth_client_factory: Callable[[str], PasswordAuthClient],
    email: str,
    temporary_password: str,
) -> None:
    normalized_email = _validated_email(email)
    validated_password = _validated_owner_password(temporary_password)
    authority = read_owner_reset_authority(
        management_client,
        email=normalized_email,
    )
    server_key = management_client.get_server_key()
    auth_client_factory(server_key).update_password_once(
        user_id=authority.user_id,
        password=validated_password,
        app_metadata=authority.app_metadata,
    )


def _github_actions_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    owner_email = os.environ.get("SUPABASE_OWNER_EMAIL", "")
    temporary_password = os.environ.get("SUPABASE_OWNER_TEMP_PASSWORD", "")
    try:
        # Validate before emitting an Actions command so control characters can
        # never be used to inject workflow commands.
        normalized_email = _validated_email(owner_email)
        validated_password = _validated_owner_password(temporary_password)
        if project_ref != EXPECTED_PROJECT_REF:
            raise OwnerPasswordResetError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(
                f"::add-mask::{_github_actions_escape(validated_password)}",
                flush=True,
            )
            print(f"::add-mask::{_github_actions_escape(normalized_email)}", flush=True)

        management_client = SupabaseManagementClient(
            project_ref=project_ref,
            access_token=access_token,
        )
        reset_owner_password(
            management_client=management_client,
            auth_client_factory=lambda server_key: SupabaseOwnerPasswordAuthClient(
                project_ref=project_ref,
                server_key=server_key,
            ),
            email=normalized_email,
            temporary_password=validated_password,
        )
    except (OwnerPasswordResetError, OwnerBootstrapError) as exc:
        print(f"Supabase owner password reset stopped: {exc}", file=os.sys.stderr)
        return 1
    except Exception:
        print(
            "Supabase owner password reset stopped: unexpected internal failure",
            file=os.sys.stderr,
        )
        return 1

    print("Supabase owner password reset complete: owner=*** status=updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
