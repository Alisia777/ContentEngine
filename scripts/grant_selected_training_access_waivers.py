#!/usr/bin/env python3
"""Atomically grant the reviewed workspace waiver to three protected slots.

Email addresses come only from the protected GitHub production environment.
The helper resolves and validates all identities before calling one service-only
database command, so any failed target rolls the complete grant back.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import sys

from scripts.bootstrap_supabase_owner import (
    OwnerBootstrapError,
    SupabaseManagementClient,
    _rows_from_response,
    _sql_literal,
    _validated_email,
    _validated_uuid,
)
from scripts.grant_training_access_waiver import (
    TrainingWaiverError,
    _validated_reason,
    read_training_waiver_authority,
)
from scripts.provision_supabase_member import (
    MemberProvisionError,
    read_member_state,
)


DEFAULT_REASON = (
    "Owner-approved workspace access without mandatory Academy completion."
)
SELECTED_SLOTS = ("guest", "klimov", "artiukhins")


@dataclass(frozen=True)
class SelectedTarget:
    slot: str
    user_id: str
    previous_role: str
    granted_role: str


def _require_batch_migration(
    management_client: SupabaseManagementClient,
) -> None:
    payload = management_client.execute(
        """
select
  to_regprocedure(
    'public.system_grant_training_access_waiver_batch(jsonb)'
  ) is not null as batch_ready
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1 or rows[0].get("batch_ready") is not True:
        raise TrainingWaiverError(
            "Selected waiver migration is not deployed"
        )


def _selected_target(
    management_client: SupabaseManagementClient,
    *,
    slot: str,
    email: str,
    organization_id: str,
) -> SelectedTarget:
    state = read_member_state(
        management_client,
        email=email,
        organization_id=organization_id,
    )
    if state.user_id is None:
        raise TrainingWaiverError(f"Selected slot {slot} does not exist")
    if not state.email_confirmed or not state.auth_active:
        raise TrainingWaiverError(f"Selected slot {slot} is not active and confirmed")
    if state.membership_status != "active" or state.membership_role is None:
        raise TrainingWaiverError(f"Selected slot {slot} has no active membership")

    previous_role = str(state.membership_role)
    if slot == "artiukhins":
        if previous_role != "owner":
            raise TrainingWaiverError(
                "Selected slot artiukhins must be the protected owner account"
            )
        granted_role = "owner"
    else:
        if previous_role not in {"viewer", "trainee", "operator"}:
            raise TrainingWaiverError(
                f"Selected slot {slot} cannot receive workspace access"
            )
        granted_role = "operator"

    return SelectedTarget(
        slot=slot,
        user_id=_validated_uuid(state.user_id),
        previous_role=previous_role,
        granted_role=granted_role,
    )


def _verify_selected_waivers(
    management_client: SupabaseManagementClient,
    *,
    organization_id: str,
    targets: tuple[SelectedTarget, ...],
) -> None:
    target_ids = ", ".join(
        f"{_sql_literal(target.user_id)}::uuid" for target in targets
    )
    payload = management_client.execute(
        f"""
select
  membership.profile_id::text as user_id,
  membership.role,
  membership.status as membership_status,
  waiver.status as waiver_status,
  waiver.scope,
  content_factory_private.training_access_waiver_active(
    membership.organization_id,
    membership.profile_id
  ) as waiver_active
from content_factory.memberships membership
join content_factory.training_access_waivers waiver
  on waiver.organization_id = membership.organization_id
 and waiver.profile_id = membership.profile_id
where membership.organization_id = {_sql_literal(organization_id)}::uuid
  and membership.profile_id = any(array[{target_ids}])
order by membership.profile_id
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    expected = {target.user_id: target.granted_role for target in targets}
    if len(rows) != len(expected):
        raise TrainingWaiverError("Selected waiver verification is incomplete")
    for row in rows:
        user_id = _validated_uuid(row.get("user_id"))
        if (
            expected.get(user_id) != row.get("role")
            or row.get("membership_status") != "active"
            or row.get("waiver_status") != "active"
            or row.get("scope") != "workspace_generation"
            or row.get("waiver_active") is not True
        ):
            raise TrainingWaiverError("Selected waiver verification failed")


def grant_selected_training_access_waivers(
    *,
    management_client: SupabaseManagementClient,
    guest_email: str,
    klimov_email: str,
    artiukhins_email: str,
    reason: str = DEFAULT_REASON,
) -> tuple[SelectedTarget, ...]:
    normalized_emails = tuple(
        _validated_email(value)
        for value in (guest_email, klimov_email, artiukhins_email)
    )
    if len(set(normalized_emails)) != len(normalized_emails):
        raise TrainingWaiverError("Selected account emails must be distinct")

    normalized_reason = _validated_reason(reason)
    _require_batch_migration(management_client)
    authority = read_training_waiver_authority(management_client)
    targets = tuple(
        _selected_target(
            management_client,
            slot=slot,
            email=email,
            organization_id=authority.organization_id,
        )
        for slot, email in zip(SELECTED_SLOTS, normalized_emails, strict=True)
    )
    if len({target.user_id for target in targets}) != len(targets):
        raise TrainingWaiverError("Selected account identities must be distinct")

    identity_digest = hashlib.sha256(
        ":".join(target.user_id for target in targets).encode("ascii")
    ).hexdigest()[:24]
    target_payload = ",\n    ".join(
        "jsonb_build_object("
        f"'user_id', {_sql_literal(target.user_id)}::uuid, "
        f"'role', {_sql_literal(target.granted_role)}"
        ")"
        for target in targets
    )
    management_client.execute(
        f"""
select public.system_grant_training_access_waiver_batch(jsonb_build_object(
  'organization_id', {_sql_literal(authority.organization_id)}::uuid,
  'changed_by', {_sql_literal(authority.invited_by)}::uuid,
  'reason', {_sql_literal(normalized_reason)},
  'idempotency_key', {_sql_literal(f'github-selected-training-waivers:{identity_digest}:v1')},
  'targets', jsonb_build_array(
    {target_payload}
  )
)) as result
""".strip()
    )
    _verify_selected_waivers(
        management_client,
        organization_id=authority.organization_id,
        targets=targets,
    )
    return targets


def main() -> int:
    try:
        management_client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        targets = grant_selected_training_access_waivers(
            management_client=management_client,
            guest_email=os.environ.get("SUPABASE_MEMBER_GUEST_EMAIL", ""),
            klimov_email=os.environ.get("SUPABASE_MEMBER_KLIMOV_EMAIL", ""),
            artiukhins_email=os.environ.get("SUPABASE_OWNER_EMAIL", ""),
        )
    except (
        TrainingWaiverError,
        MemberProvisionError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Selected waiver stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Selected waiver stopped: unexpected internal failure", file=sys.stderr)
        return 1

    summary = ",".join(
        f"{target.slot}:{target.granted_role}" for target in targets
    )
    print(f"Selected waiver complete: {summary}; waiver=active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
