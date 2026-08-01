#!/usr/bin/env python3
"""Create or verify one protected employee account and waive final training.

The employee is created as a confirmed Auth identity without a temporary
password.  Supabase then sends the standard recovery link so the employee sets
their own password.  The active trainee membership is promoted to ``operator``
through the audited and reversible training-waiver RPC.
"""

from __future__ import annotations

import argparse
import os
import sys

from scripts.bootstrap_supabase_owner import (
    OwnerBootstrapError,
    SupabaseAuthClient,
    SupabaseManagementClient,
    _validated_email,
)
from scripts.grant_training_access_waiver import (
    DEFAULT_REASON,
    TrainingWaiverError,
    grant_training_access_waiver,
    read_training_waiver_authority,
)
from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    MemberProvisionError,
    _require_distinct_account_email,
    _validated_display_name,
    initialize_member_membership,
    read_member_state,
)


class EmployeeOnboardingError(RuntimeError):
    """A non-sensitive onboarding failure safe for Actions logs."""


def _create_confirmed_member_for_recovery(
    auth_client: SupabaseAuthClient,
    *,
    email: str,
    display_name: str,
) -> None:
    """Create a confirmed limited identity without manufacturing a password."""

    admin_request = getattr(auth_client, "_admin_request", None)
    if not callable(admin_request):
        raise EmployeeOnboardingError("Supabase Auth admin client is unavailable")
    admin_request(
        "/auth/v1/admin/users",
        method="POST",
        payload={
            "email": email,
            "email_confirm": True,
            "user_metadata": {"display_name": display_name},
            "app_metadata": {
                MEMBER_PROVISION_MARKER: True,
                PASSWORD_CHANGE_REQUIRED_MARKER: True,
            },
        },
    )


def provision_employee_without_training(
    *,
    management_client: SupabaseManagementClient,
    email: str,
    display_name: str,
    distinct_from: list[str],
    reason: str,
    publishable_key: str,
) -> tuple[str, str, str]:
    normalized_email = _validated_email(email)
    validated_display_name = _validated_display_name(display_name)
    _require_distinct_account_email(normalized_email, distinct_from)

    authority = read_training_waiver_authority(management_client)
    state = read_member_state(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
    )

    identity_status = "existing"
    membership_status = "existing"
    if state.user_id is None:
        server_key = management_client.get_server_key()
        auth_client = SupabaseAuthClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            server_key=server_key,
            publishable_key=publishable_key,
        )
        _create_confirmed_member_for_recovery(
            auth_client,
            email=normalized_email,
            display_name=validated_display_name,
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
        raise EmployeeOnboardingError(
            "Employee identity is not active and confirmed"
        )
    if (state.app_metadata or {}).get(MEMBER_PROVISION_MARKER) is not True:
        raise EmployeeOnboardingError(
            "Pre-existing employee identity is not owned by this provisioning flow"
        )

    if state.membership_role is None:
        if state.membership_count != 0:
            raise EmployeeOnboardingError(
                "Employee identity already belongs to another organization"
            )
        initialize_member_membership(
            management_client,
            authority=authority,
            user_id=state.user_id,
            role="trainee",
        )
        membership_status = "created"
        state = read_member_state(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
        )

    if state.membership_status != "active":
        raise EmployeeOnboardingError("Employee membership is not active")
    if state.membership_role not in {"trainee", "operator"}:
        raise EmployeeOnboardingError(
            "Employee membership has an unexpected role"
        )

    role, recovery_status = grant_training_access_waiver(
        management_client=management_client,
        email=normalized_email,
        reason=reason,
        send_recovery=True,
        publishable_key=publishable_key,
    )
    return identity_status, membership_status, f"{role}:{recovery_status}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision one employee with operator access and no final test",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--distinct-from", action="append", default=[])
    parser.add_argument("--reason", default=DEFAULT_REASON)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        management_client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        identity, membership, access = provision_employee_without_training(
            management_client=management_client,
            email=args.email,
            display_name=args.display_name,
            distinct_from=args.distinct_from,
            reason=args.reason,
            publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
        )
    except (
        EmployeeOnboardingError,
        TrainingWaiverError,
        MemberProvisionError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Employee onboarding stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Employee onboarding stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    print(
        "Employee onboarding complete: "
        f"identity={identity} membership={membership} access={access}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
