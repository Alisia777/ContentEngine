#!/usr/bin/env python3
"""Provision one limited Supabase member without exposing a temporary password.

The protected GitHub production environment supplies the Management API token
and a short-lived temporary password secret. The script creates only a
confirmed, explicitly limited identity and attaches it to the reviewed
ContentEngine organization through a dedicated service-role-only RPC.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import re
from typing import Any, Callable, Protocol

from scripts.bootstrap_supabase_owner import (
    OWNER_ORGANIZATION_SLUG,
    OwnerBootstrapError,
    SupabaseAuthClient,
    SupabaseManagementClient,
    _rows_from_response,
    _sql_literal,
    _validated_email,
    _validated_uuid,
)


MEMBER_PROVISION_MARKER = "contentengine_github_member_provisioned"
ALLOWED_MEMBER_ROLES = frozenset({"trainee", "viewer"})


class MemberProvisionError(RuntimeError):
    """A non-sensitive member-provisioning failure safe for Actions logs."""


@dataclass(frozen=True)
class ProvisioningAuthority:
    organization_id: str
    invited_by: str


@dataclass(frozen=True)
class MemberState:
    user_id: str | None
    email_confirmed: bool = False
    auth_active: bool = True
    signed_in: bool = False
    app_metadata: dict[str, Any] | None = None
    membership_count: int = 0
    membership_role: str | None = None
    membership_status: str | None = None


@dataclass(frozen=True)
class MemberProvisionResult:
    identity_status: str
    membership_status: str
    role: str


class ManagementClient(Protocol):
    def execute(self, sql: str, *, read_only: bool = False) -> Any: ...

    def get_server_key(self) -> str: ...


class MemberAuthClient(Protocol):
    def create_confirmed_user_with_password(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        app_metadata: dict[str, Any],
    ) -> None: ...

    def claim_confirmed_user_with_password(
        self,
        *,
        user_id: str,
        display_name: str,
        password: str,
        app_metadata: dict[str, Any],
    ) -> None: ...


def _validated_display_name(value: str) -> str:
    display_name = str(value or "").strip()
    if (
        not 1 <= len(display_name) <= 120
        or any(ord(character) < 32 for character in display_name)
    ):
        raise MemberProvisionError("Member display name is invalid")
    return display_name


def _validated_temp_password(value: str) -> str:
    password = str(value or "")
    if (
        not 14 <= len(password) <= 128
        or re.search(r"[a-z]", password) is None
        or re.search(r"[A-Z]", password) is None
        or re.search(r"[0-9]", password) is None
        or any(character in password for character in ("\r", "\n", "\x00"))
    ):
        raise MemberProvisionError(
            "SUPABASE_MEMBER_TEMP_PASSWORD does not meet the required policy"
        )
    return password


def read_provisioning_authority(
    client: ManagementClient,
) -> ProvisioningAuthority:
    organization_slug = _sql_literal(OWNER_ORGANIZATION_SLUG)
    payload = client.execute(
        f"""
select
  organization.id::text as organization_id,
  membership.profile_id::text as invited_by
from content_factory.organizations organization
join content_factory.memberships membership
  on membership.organization_id = organization.id
join content_factory.profiles profile
  on profile.id = membership.profile_id
join auth.users owner_auth
  on owner_auth.id = membership.profile_id
where organization.slug = {organization_slug}
  and organization.status = 'active'
  and membership.status = 'active'
  and membership.role = 'owner'
  and profile.status = 'active'
  and owner_auth.email_confirmed_at is not null
  and owner_auth.deleted_at is null
  and (owner_auth.banned_until is null or owner_auth.banned_until <= now())
order by membership.created_at, membership.id
limit 1
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise MemberProvisionError(
            "An active owner is required for member provisioning"
        )
    return ProvisioningAuthority(
        organization_id=_validated_uuid(rows[0].get("organization_id")),
        invited_by=_validated_uuid(rows[0].get("invited_by")),
    )


def read_member_state(
    client: ManagementClient,
    *,
    email: str,
    organization_id: str,
) -> MemberState:
    normalized_email = _validated_email(email)
    validated_organization_id = _validated_uuid(organization_id)
    payload = client.execute(
        f"""
select
  auth_user.id::text as user_id,
  auth_user.email_confirmed_at is not null as email_confirmed,
  (
    auth_user.deleted_at is null
    and (auth_user.banned_until is null or auth_user.banned_until <= now())
  ) as auth_active,
  auth_user.last_sign_in_at is not null as signed_in,
  coalesce(auth_user.raw_app_meta_data, '{{}}'::jsonb) as app_metadata,
  (
    select count(*)::integer
    from content_factory.memberships membership
    where membership.profile_id = auth_user.id
  ) as membership_count,
  target_membership.role as membership_role,
  target_membership.status as membership_status
from auth.users auth_user
left join content_factory.memberships target_membership
  on target_membership.profile_id = auth_user.id
 and target_membership.organization_id = {_sql_literal(validated_organization_id)}::uuid
where lower(auth_user.email) = {_sql_literal(normalized_email)}
order by auth_user.created_at, auth_user.id
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if not rows:
        return MemberState(user_id=None, app_metadata={})
    if len(rows) != 1:
        raise MemberProvisionError("Supabase member identity is ambiguous")
    row = rows[0]
    if (
        not isinstance(row.get("email_confirmed"), bool)
        or not isinstance(row.get("auth_active"), bool)
        or not isinstance(row.get("signed_in"), bool)
    ):
        raise MemberProvisionError("Supabase member state response was invalid")
    app_metadata = row.get("app_metadata")
    if not isinstance(app_metadata, dict):
        raise MemberProvisionError("Supabase member metadata was invalid")
    membership_count = row.get("membership_count")
    if isinstance(membership_count, bool) or not isinstance(membership_count, int):
        raise MemberProvisionError("Supabase member state response was invalid")
    membership_role = row.get("membership_role")
    membership_status = row.get("membership_status")
    if membership_role is not None and not isinstance(membership_role, str):
        raise MemberProvisionError("Supabase member state response was invalid")
    if membership_status is not None and not isinstance(membership_status, str):
        raise MemberProvisionError("Supabase member state response was invalid")
    return MemberState(
        user_id=_validated_uuid(row.get("user_id")),
        email_confirmed=row["email_confirmed"],
        auth_active=row["auth_active"],
        signed_in=row["signed_in"],
        app_metadata=dict(app_metadata),
        membership_count=membership_count,
        membership_role=membership_role,
        membership_status=membership_status,
    )


def initialize_member_membership(
    client: ManagementClient,
    *,
    authority: ProvisioningAuthority,
    user_id: str,
    role: str,
) -> None:
    validated_user_id = _validated_uuid(user_id)
    client.execute(
        f"""
select public.system_provision_limited_member(jsonb_build_object(
  'organization_id', {_sql_literal(authority.organization_id)}::uuid,
  'user_id', {_sql_literal(validated_user_id)}::uuid,
  'provisioned_by', {_sql_literal(authority.invited_by)}::uuid,
  'role', {_sql_literal(role)}
)) as result
""".strip()
    )


def provision_member(
    *,
    management_client: ManagementClient,
    auth_client_factory: Callable[[str], MemberAuthClient],
    email: str,
    display_name: str,
    temporary_password: str,
    role: str,
    claim_existing: bool = False,
) -> MemberProvisionResult:
    normalized_email = _validated_email(email)
    validated_display_name = _validated_display_name(display_name)
    validated_password = _validated_temp_password(temporary_password)
    normalized_role = str(role or "").strip().casefold()
    if normalized_role not in ALLOWED_MEMBER_ROLES:
        raise MemberProvisionError("Member role must be trainee or viewer")
    authority = read_provisioning_authority(management_client)
    state = read_member_state(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
    )
    identity_status = "existing"

    auth_client: MemberAuthClient | None = None

    def require_auth_client() -> MemberAuthClient:
        nonlocal auth_client
        if auth_client is None:
            auth_client = auth_client_factory(management_client.get_server_key())
        return auth_client

    if state.user_id is None:
        require_auth_client().create_confirmed_user_with_password(
            email=normalized_email,
            display_name=validated_display_name,
            password=validated_password,
            app_metadata={MEMBER_PROVISION_MARKER: True},
        )
        identity_status = "created"
        state = read_member_state(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
        )
        if (
            state.user_id is None
            or not state.email_confirmed
            or not state.auth_active
        ):
            raise MemberProvisionError("Supabase member identity was not created")
    elif not state.email_confirmed:
        raise MemberProvisionError(
            "Pre-existing Supabase member email is not confirmed; manual review required"
        )
    elif not state.auth_active:
        raise MemberProvisionError(
            "Pre-existing Supabase member identity is not active"
        )

    if (state.app_metadata or {}).get(MEMBER_PROVISION_MARKER) is not True:
        if not claim_existing:
            raise MemberProvisionError(
                "Pre-existing Supabase member is not owned by this provisioning flow"
            )
        if state.signed_in:
            raise MemberProvisionError(
                "Pre-existing Supabase member has already signed in"
            )
        if state.membership_count != 0:
            raise MemberProvisionError(
                "Pre-existing Supabase member already belongs to an organization"
            )
        metadata = dict(state.app_metadata or {})
        if any(str(key).startswith("contentengine_") for key in metadata):
            raise MemberProvisionError(
                "Pre-existing Supabase member has conflicting provisioning metadata"
            )
        metadata[MEMBER_PROVISION_MARKER] = True
        original_user_id = state.user_id
        require_auth_client().claim_confirmed_user_with_password(
            user_id=original_user_id,
            display_name=validated_display_name,
            password=validated_password,
            app_metadata=metadata,
        )
        identity_status = "claimed"
        state = read_member_state(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
        )
        if (
            state.user_id != original_user_id
            or not state.email_confirmed
            or not state.auth_active
            or (state.app_metadata or {}).get(MEMBER_PROVISION_MARKER) is not True
        ):
            raise MemberProvisionError("Supabase member identity claim was not verified")

    if state.membership_role is not None:
        if state.membership_status != "active":
            raise MemberProvisionError(
                "Pre-existing Supabase member membership is not active"
            )
        if state.membership_role != normalized_role:
            raise MemberProvisionError(
                "Pre-existing Supabase member has an unexpected role"
            )
        return MemberProvisionResult(
            identity_status=identity_status,
            membership_status="existing",
            role=state.membership_role,
        )
    if state.membership_count != 0:
        raise MemberProvisionError(
            "Pre-existing Supabase member belongs to another organization"
        )

    initialize_member_membership(
        management_client,
        authority=authority,
        user_id=state.user_id,
        role=normalized_role,
    )
    state = read_member_state(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
    )
    if (
        state.membership_status != "active"
        or state.membership_role != normalized_role
    ):
        raise MemberProvisionError("Supabase member membership was not initialized")
    return MemberProvisionResult(
        identity_status=identity_status,
        membership_status="created",
        role=state.membership_role,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision one limited Supabase ContentEngine member",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=sorted(ALLOWED_MEMBER_ROLES), required=True)
    parser.add_argument(
        "--claim-existing",
        action="store_true",
        help="Claim only an unsigned-in, membership-free existing Auth identity",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    temporary_password = os.environ.get("SUPABASE_MEMBER_TEMP_PASSWORD", "")
    if os.environ.get("GITHUB_ACTIONS") == "true" and temporary_password:
        print(f"::add-mask::{temporary_password}", flush=True)
    try:
        project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
        access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
        management_client = SupabaseManagementClient(
            project_ref=project_ref,
            access_token=access_token,
        )
        result = provision_member(
            management_client=management_client,
            auth_client_factory=lambda server_key: SupabaseAuthClient(
                project_ref=project_ref,
                server_key=server_key,
                publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
            ),
            email=args.email,
            display_name=args.display_name,
            temporary_password=temporary_password,
            role=args.role,
            claim_existing=args.claim_existing,
        )
    except (MemberProvisionError, OwnerBootstrapError) as exc:
        print(f"Supabase member provisioning stopped: {exc}", file=os.sys.stderr)
        return 1
    except Exception:
        print(
            "Supabase member provisioning stopped: unexpected internal failure",
            file=os.sys.stderr,
        )
        return 1

    print(
        "Supabase member provisioning complete: "
        f"identity={result.identity_status} "
        f"membership={result.membership_status} "
        f"role={result.role}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
