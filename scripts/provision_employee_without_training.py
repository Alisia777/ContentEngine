#!/usr/bin/env python3
"""Create or verify one protected employee account and waive final training.

The orchestration is idempotent for an account already provisioned by the
reviewed ContentEngine flow.  It creates a confirmed trainee only when needed,
promotes the active member to ``operator`` through the audited training-waiver
RPC, verifies the waiver, and sends the standard password-recovery email.
"""

from __future__ import annotations

import argparse
import os
import sys

from scripts.bootstrap_supabase_owner import (
    OwnerBootstrapError,
    SupabaseAuthClient,
    SupabaseManagementClient,
)
from scripts.grant_training_access_waiver import (
    DEFAULT_REASON,
    TrainingWaiverError,
    grant_training_access_waiver,
)
from scripts.provision_supabase_member import (
    MemberProvisionError,
    provision_member,
    read_member_state,
    read_provisioning_authority,
)


class EmployeeOnboardingError(RuntimeError):
    """A non-sensitive onboarding failure safe for Actions logs."""


def provision_employee_without_training(
    *,
    management_client: SupabaseManagementClient,
    email: str,
    display_name: str,
    temporary_password: str,
    password_dispatch_id: str,
    account_slot: str,
    distinct_from: list[str],
    reason: str,
    publishable_key: str,
) -> tuple[str, str, str]:
    authority = read_provisioning_authority(management_client)
    state = read_member_state(
        management_client,
        email=email,
        organization_id=authority.organization_id,
    )

    identity_status = "existing"
    membership_status = "existing"
    if not (
        state.user_id is not None
        and state.membership_status == "active"
        and state.membership_role == "operator"
    ):
        result = provision_member(
            management_client=management_client,
            auth_client_factory=lambda server_key: SupabaseAuthClient(
                project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
                server_key=server_key,
                publishable_key=publishable_key,
            ),
            email=email,
            display_name=display_name,
            temporary_password=temporary_password,
            password_dispatch_id=password_dispatch_id,
            account_slot=account_slot,
            role="trainee",
            claim_existing=False,
            reset_signed_in=False,
            distinct_from=distinct_from,
        )
        identity_status = result.identity_status
        membership_status = result.membership_status

    role, recovery_status = grant_training_access_waiver(
        management_client=management_client,
        email=email,
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
    parser.add_argument("--account-slot", required=True)
    parser.add_argument("--password-dispatch-id", required=True)
    parser.add_argument("--distinct-from", action="append", default=[])
    parser.add_argument("--reason", default=DEFAULT_REASON)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    temporary_password = os.environ.get(
        "CONTENTENGINE_MEMBER_DISPATCH_PASSWORD",
        "",
    )
    if os.environ.get("GITHUB_ACTIONS") == "true" and temporary_password:
        print(f"::add-mask::{temporary_password}", flush=True)
    try:
        management_client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        identity, membership, access = provision_employee_without_training(
            management_client=management_client,
            email=args.email,
            display_name=args.display_name,
            temporary_password=temporary_password,
            password_dispatch_id=args.password_dispatch_id,
            account_slot=args.account_slot,
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
