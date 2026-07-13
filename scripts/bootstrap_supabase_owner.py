#!/usr/bin/env python3
"""Provision the first Supabase-native ContentEngine owner safely.

The GitHub production environment supplies a Supabase Management API token and
the owner email.  A server API key is revealed only to this process, used for
Auth Admin calls, and never written to disk or included in diagnostics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import re
from typing import Any, Callable, Protocol
from urllib import error, parse, request
from uuid import UUID


EXPECTED_PROJECT_REF = "iyckwryrucqrxwlowxow"
MANAGEMENT_API_ORIGIN = "https://api.supabase.com"
PUBLIC_APP_URL = "https://alisia777.github.io/ContentEngine/"
OWNER_RECOVERY_REDIRECT = f"{PUBLIC_APP_URL}auth/accept/"
OWNER_IDEMPOTENCY_KEY = "github-production-owner-v1"
OWNER_ORGANIZATION_NAME = "ALTEA Content Factory"
OWNER_ORGANIZATION_SLUG = "altea-content-factory"
OWNER_RECOVERY_MARKER = "contentengine_owner_recovery_sent"
MAX_RESPONSE_BYTES = 1_048_576
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}"
)


class OwnerBootstrapError(RuntimeError):
    """A non-sensitive owner-bootstrap failure safe for Actions logs."""


@dataclass(frozen=True)
class OwnerState:
    user_id: str | None
    email_confirmed: bool = False
    signed_in: bool = False
    owner_active: bool = False
    app_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class OwnerBootstrapResult:
    identity_status: str
    membership_status: str
    recovery_status: str


class ManagementClient(Protocol):
    def execute(self, sql: str, *, read_only: bool = False) -> Any: ...

    def get_server_key(self) -> str: ...


class AuthClient(Protocol):
    def create_confirmed_user(self, *, email: str, display_name: str) -> None: ...

    def send_password_recovery(self, *, email: str) -> None: ...

    def update_app_metadata(self, user_id: str, metadata: dict[str, Any]) -> None: ...


def _validated_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or ".." in email or EMAIL_PATTERN.fullmatch(email) is None:
        raise OwnerBootstrapError("SUPABASE_OWNER_EMAIL is invalid")
    return email


def _validated_uuid(value: Any) -> str:
    try:
        parsed = UUID(str(value or ""))
    except (ValueError, TypeError, AttributeError) as exc:
        raise OwnerBootstrapError("Supabase returned an invalid owner identity") from exc
    return str(parsed)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _read_json_response(response: Any) -> Any:
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise OwnerBootstrapError("Supabase response was too large")
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OwnerBootstrapError("Supabase returned an invalid response") from None


def _http_json(
    *,
    opener: Callable[..., Any],
    url: str,
    method: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout_seconds: int = 60,
) -> Any:
    body = None
    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    api_request = request.Request(
        url,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with opener(api_request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", 200))
            response_payload = _read_json_response(response)
    except error.HTTPError as exc:
        status = int(exc.code)
        try:
            exc.close()
        finally:
            raise OwnerBootstrapError(
                f"Supabase owner bootstrap request failed (HTTP {status})"
            ) from None
    except (error.URLError, TimeoutError, OSError):
        raise OwnerBootstrapError("Supabase owner bootstrap request failed") from None
    if status < 200 or status >= 300:
        raise OwnerBootstrapError(
            f"Supabase owner bootstrap request failed (HTTP {status})"
        )
    return response_payload


def _rows_from_response(payload: Any) -> list[dict[str, Any]]:
    rows = payload
    if isinstance(payload, dict):
        for key in ("result", "data"):
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise OwnerBootstrapError("Supabase owner state response was invalid")
    return rows


class SupabaseManagementClient:
    def __init__(
        self,
        *,
        project_ref: str,
        access_token: str,
        opener: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = 60,
    ) -> None:
        if project_ref != EXPECTED_PROJECT_REF:
            raise OwnerBootstrapError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if not str(access_token or "").strip():
            raise OwnerBootstrapError("SUPABASE_ACCESS_TOKEN is required")
        self._project_ref = project_ref
        self._access_token = access_token.strip()
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "User-Agent": "ContentEngine-Owner-Bootstrap/1",
        }

    def execute(self, sql: str, *, read_only: bool = False) -> Any:
        return _http_json(
            opener=self._opener,
            url=(
                f"{MANAGEMENT_API_ORIGIN}/v1/projects/{self._project_ref}"
                "/database/query"
            ),
            method="POST",
            headers=self._headers,
            payload={"query": sql, "read_only": read_only},
            timeout_seconds=self._timeout_seconds,
        )

    def get_server_key(self) -> str:
        payload = _http_json(
            opener=self._opener,
            url=(
                f"{MANAGEMENT_API_ORIGIN}/v1/projects/{self._project_ref}"
                "/api-keys?reveal=true"
            ),
            method="GET",
            headers=self._headers,
            timeout_seconds=self._timeout_seconds,
        )
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise OwnerBootstrapError("Supabase API-key response was invalid")
        secret_keys = [
            str(item.get("api_key") or "").strip()
            for item in payload
            if str(item.get("type") or "").casefold() == "secret"
            and isinstance(item.get("secret_jwt_template"), dict)
            and str(item["secret_jwt_template"].get("role") or "").casefold()
            == "service_role"
            and str(item.get("api_key") or "").strip()
        ]
        legacy_keys = [
            str(item.get("api_key") or "").strip()
            for item in payload
            if str(item.get("name") or "").casefold() == "service_role"
            and str(item.get("api_key") or "").strip()
        ]
        candidates = secret_keys if secret_keys else legacy_keys
        if len(candidates) != 1 or re.fullmatch(
            r"[A-Za-z0-9._-]{20,}", candidates[0]
        ) is None:
            raise OwnerBootstrapError(
                "Exactly one revealed Supabase service-role server key is required"
            )
        server_key = candidates[0]
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::add-mask::{server_key}", flush=True)
        return server_key


class SupabaseAuthClient:
    def __init__(
        self,
        *,
        project_ref: str,
        server_key: str,
        publishable_key: str,
        opener: Callable[..., Any] = request.urlopen,
        timeout_seconds: int = 60,
    ) -> None:
        if project_ref != EXPECTED_PROJECT_REF:
            raise OwnerBootstrapError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if not str(server_key or "").strip():
            raise OwnerBootstrapError("Supabase server key is unavailable")
        if not str(publishable_key or "").startswith("sb_publishable_"):
            raise OwnerBootstrapError(
                "SUPABASE_PUBLISHABLE_KEY must be a browser-safe publishable key"
            )
        self._origin = f"https://{project_ref}.supabase.co"
        self._server_key = server_key.strip()
        self._publishable_key = publishable_key.strip()
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def _admin_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self._server_key,
            "User-Agent": "ContentEngine-Owner-Bootstrap/1",
        }
        # New sb_secret_* keys are opaque and must never be parsed as JWTs.
        # Legacy service_role keys still require the Bearer header.
        if not self._server_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self._server_key}"
        return headers

    def _admin_request(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any],
    ) -> Any:
        return _http_json(
            opener=self._opener,
            url=f"{self._origin}{path}",
            method=method,
            headers=self._admin_headers,
            payload=payload,
            timeout_seconds=self._timeout_seconds,
        )

    def create_confirmed_user(self, *, email: str, display_name: str) -> None:
        self._admin_request(
            "/auth/v1/admin/users",
            method="POST",
            payload={
                "email": email,
                "email_confirm": True,
                "user_metadata": {"display_name": display_name},
                "app_metadata": {"contentengine_bootstrap_owner": True},
            },
        )

    def send_password_recovery(self, *, email: str) -> None:
        redirect = parse.quote(OWNER_RECOVERY_REDIRECT, safe="")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "apikey": self._publishable_key,
            "User-Agent": "ContentEngine-Owner-Bootstrap/1",
        }
        _http_json(
            opener=self._opener,
            url=f"{self._origin}/auth/v1/recover?redirect_to={redirect}",
            method="POST",
            headers=headers,
            payload={"email": email},
            timeout_seconds=self._timeout_seconds,
        )

    def update_app_metadata(self, user_id: str, metadata: dict[str, Any]) -> None:
        validated = _validated_uuid(user_id)
        self._admin_request(
            f"/auth/v1/admin/users/{validated}",
            method="PUT",
            payload={"app_metadata": metadata},
        )


def read_owner_state(client: ManagementClient, *, email: str) -> OwnerState:
    normalized_email = _validated_email(email)
    email_literal = _sql_literal(normalized_email)
    payload = client.execute(
        f"""
select
  auth_user.id::text as user_id,
  auth_user.email_confirmed_at is not null as email_confirmed,
  auth_user.last_sign_in_at is not null as signed_in,
  coalesce(auth_user.raw_app_meta_data, '{{}}'::jsonb) as app_metadata,
  exists (
    select 1
    from content_factory.profiles profile
    join content_factory.memberships membership
      on membership.profile_id = profile.id
    join content_factory.organizations organization
      on organization.id = membership.organization_id
    where profile.id = auth_user.id
      and profile.status = 'active'
      and membership.status = 'active'
      and membership.role = 'owner'
      and organization.status = 'active'
  ) as owner_active
from auth.users auth_user
where lower(auth_user.email) = {email_literal}
  and auth_user.deleted_at is null
order by auth_user.created_at, auth_user.id
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if not rows:
        return OwnerState(user_id=None, app_metadata={})
    if len(rows) != 1:
        raise OwnerBootstrapError("Supabase owner identity is ambiguous")
    row = rows[0]
    app_metadata = row.get("app_metadata")
    if app_metadata is None:
        app_metadata = {}
    if not isinstance(app_metadata, dict):
        raise OwnerBootstrapError("Supabase owner metadata was invalid")
    for field in ("email_confirmed", "signed_in", "owner_active"):
        if not isinstance(row.get(field), bool):
            raise OwnerBootstrapError("Supabase owner state response was invalid")
    return OwnerState(
        user_id=_validated_uuid(row.get("user_id")),
        email_confirmed=row["email_confirmed"],
        signed_in=row["signed_in"],
        owner_active=row["owner_active"],
        app_metadata=dict(app_metadata),
    )


def initialize_owner_membership(
    client: ManagementClient,
    *,
    user_id: str,
) -> None:
    validated_user_id = _validated_uuid(user_id)
    client.execute(
        f"""
select public.system_initialize_owner(jsonb_build_object(
  'user_id', {_sql_literal(validated_user_id)}::uuid,
  'idempotency_key', {_sql_literal(OWNER_IDEMPOTENCY_KEY)},
  'organization_name', {_sql_literal(OWNER_ORGANIZATION_NAME)},
  'organization_slug', {_sql_literal(OWNER_ORGANIZATION_SLUG)}
)) as result
""".strip()
    )


def bootstrap_owner(
    *,
    management_client: ManagementClient,
    auth_client_factory: Callable[[str], AuthClient],
    email: str,
    display_name: str,
) -> OwnerBootstrapResult:
    normalized_email = _validated_email(email)
    state = read_owner_state(management_client, email=normalized_email)
    identity_status = "existing"
    auth_client: AuthClient | None = None

    def require_auth_client() -> AuthClient:
        nonlocal auth_client
        if auth_client is None:
            auth_client = auth_client_factory(management_client.get_server_key())
        return auth_client

    if state.user_id is None:
        require_auth_client().create_confirmed_user(
            email=normalized_email,
            display_name=display_name,
        )
        identity_status = "created"
        state = read_owner_state(management_client, email=normalized_email)
        if state.user_id is None:
            raise OwnerBootstrapError("Supabase owner identity was not created")
        if not state.email_confirmed:
            raise OwnerBootstrapError("New Supabase owner email was not confirmed")
    elif not state.email_confirmed:
        # Public signup may have drifted before the production Auth config was
        # applied.  Confirming an existing identity here could grant an
        # attacker-selected password owner access without mailbox proof.
        raise OwnerBootstrapError(
            "Pre-existing Supabase owner email is not confirmed; manual review required"
        )

    membership_status = "existing"
    if not state.owner_active:
        initialize_owner_membership(management_client, user_id=state.user_id)
        membership_status = "created"
        state = read_owner_state(management_client, email=normalized_email)
        if not state.owner_active:
            raise OwnerBootstrapError("Supabase owner membership was not initialized")

    metadata = dict(state.app_metadata or {})
    recovery_status = "not_required"
    if not state.signed_in and metadata.get(OWNER_RECOVERY_MARKER) is not True:
        client = require_auth_client()
        client.send_password_recovery(email=normalized_email)
        metadata[OWNER_RECOVERY_MARKER] = True
        client.update_app_metadata(state.user_id, metadata)
        recovery_status = "sent"

    return OwnerBootstrapResult(
        identity_status=identity_status,
        membership_status=membership_status,
        recovery_status=recovery_status,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the first Supabase-native ContentEngine owner",
    )
    parser.add_argument("--display-name", default="Alisia777")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
        access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
        publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        owner_email = os.environ.get("SUPABASE_OWNER_EMAIL", "")
        management_client = SupabaseManagementClient(
            project_ref=project_ref,
            access_token=access_token,
        )
        result = bootstrap_owner(
            management_client=management_client,
            auth_client_factory=lambda server_key: SupabaseAuthClient(
                project_ref=project_ref,
                server_key=server_key,
                publishable_key=publishable_key,
            ),
            email=owner_email,
            display_name=args.display_name,
        )
    except OwnerBootstrapError as exc:
        print(f"Supabase owner bootstrap stopped: {exc}", file=os.sys.stderr)
        return 1
    except Exception:
        print(
            "Supabase owner bootstrap stopped: unexpected internal failure",
            file=os.sys.stderr,
        )
        return 1

    print(
        "Supabase owner bootstrap complete: "
        f"identity={result.identity_status} "
        f"membership={result.membership_status} "
        f"recovery={result.recovery_status}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
