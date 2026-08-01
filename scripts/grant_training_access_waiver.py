#!/usr/bin/env python3
"""Grant one audited ContentEngine training waiver and send password recovery.

The target identity must already be an active, confirmed member of the reviewed
production organization with role ``trainee`` or ``operator``.  The helper
never manufactures course attempts or certifications: it calls the dedicated
service-only waiver RPC, verifies the resulting operator membership and active
waiver, and optionally sends the standard Supabase recovery email so the
employee can choose their own password.
"""

from __future__ import annotations

import argparse
import os
import sys

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
from scripts.provision_supabase_member import (
    MemberProvisionError,
    ProvisioningAuthority,
    read_member_state,
)


DEFAULT_REASON = (
    "По решению владельца сотрудник допущен к рабочему кабинету без "
    "прохождения итогового теста."
)


class TrainingWaiverError(RuntimeError):
    """A non-sensitive training-waiver failure safe for Actions logs."""


def _validated_reason(value: str) -> str:
    reason = " ".join(str(value or "").split())
    if not 10 <= len(reason) <= 1000:
        raise TrainingWaiverError("Training waiver reason is invalid")
    return reason


def read_training_waiver_authority(
    client: SupabaseManagementClient,
) -> ProvisioningAuthority:
    """Return one active owner, or an active admin when no owner exists."""

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
join auth.users manager_auth
  on manager_auth.id = membership.profile_id
where organization.slug = {organization_slug}
  and organization.status = 'active'
  and membership.status = 'active'
  and membership.role in ('owner', 'admin')
  and profile.status = 'active'
  and manager_auth.email_confirmed_at is not null
  and manager_auth.deleted_at is null
  and (
    manager_auth.banned_until is null
    or manager_auth.banned_until <= now()
  )
order by
  case membership.role when 'owner' then 0 else 1 end,
  membership.created_at,
  membership.id
limit 1
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise TrainingWaiverError(
            "An active owner or admin is required for employee provisioning"
        )
    return ProvisioningAuthority(
        organization_id=_validated_uuid(rows[0].get("organization_id")),
        invited_by=_validated_uuid(rows[0].get("invited_by")),
    )


def _verify_training_waiver(
    client: SupabaseManagementClient,
    *,
    organization_id: str,
    user_id: str,
) -> None:
    payload = client.execute(
        f"""
select
  membership.role,
  membership.status as membership_status,
  waiver.status as waiver_status,
  waiver.scope
from content_factory.memberships membership
join content_factory.training_access_waivers waiver
  on waiver.organization_id = membership.organization_id
 and waiver.profile_id = membership.profile_id
where membership.organization_id = {_sql_literal(organization_id)}::uuid
  and membership.profile_id = {_sql_literal(user_id)}::uuid
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise TrainingWaiverError("Training waiver verification is ambiguous")
    row = rows[0]
    if (
        row.get("role") != "operator"
        or row.get("membership_status") != "active"
        or row.get("waiver_status") != "active"
        or row.get("scope") != "workspace_generation"
    ):
        raise TrainingWaiverError("Training waiver verification failed")


def grant_training_access_waiver(
    *,
    management_client: SupabaseManagementClient,
    email: str,
    reason: str,
    send_recovery: bool,
    publishable_key: str,
) -> tuple[str, str]:
    normalized_email = _validated_email(email)
    normalized_reason = _validated_reason(reason)
    authority = read_training_waiver_authority(management_client)
    state = read_member_state(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
    )
    if state.user_id is None:
        raise TrainingWaiverError("Target member identity does not exist")
    user_id = _validated_uuid(state.user_id)
    if not state.email_confirmed or not state.auth_active:
        raise TrainingWaiverError("Target member identity is not active and confirmed")
    if state.membership_status != "active":
        raise TrainingWaiverError("Target member membership is not active")
    if state.membership_role not in {"trainee", "operator"}:
        raise TrainingWaiverError("Target member role cannot receive a training waiver")

    idempotency_key = (
        f"github-training-waiver:{authority.organization_id}:{user_id}:v1"
    )
    management_client.execute(
        f"""
select public.system_set_training_access_waiver(jsonb_build_object(
  'organization_id', {_sql_literal(authority.organization_id)}::uuid,
  'user_id', {_sql_literal(user_id)}::uuid,
  'changed_by', {_sql_literal(authority.invited_by)}::uuid,
  'action', 'grant',
  'reason', {_sql_literal(normalized_reason)},
  'role', 'operator',
  'idempotency_key', {_sql_literal(idempotency_key)}
)) as result
""".strip()
    )
    _verify_training_waiver(
        management_client,
        organization_id=authority.organization_id,
        user_id=user_id,
    )

    recovery_status = "not_requested"
    if send_recovery:
        server_key = management_client.get_server_key()
        auth_client = SupabaseAuthClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            server_key=server_key,
            publishable_key=publishable_key,
        )
        auth_client.send_password_recovery(email=normalized_email)
        recovery_status = "requested"

    return "operator", recovery_status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grant one audited ContentEngine training access waiver",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--reason", default=DEFAULT_REASON)
    parser.add_argument("--send-recovery", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        management_client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        role, recovery = grant_training_access_waiver(
            management_client=management_client,
            email=args.email,
            reason=args.reason,
            send_recovery=args.send_recovery,
            publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
        )
    except (
        TrainingWaiverError,
        MemberProvisionError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Training waiver stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Training waiver stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    print(
        "Training waiver complete: "
        f"membership_role={role} waiver=active recovery={recovery}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
