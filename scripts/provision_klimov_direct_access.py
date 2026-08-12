#!/usr/bin/env python3
"""Give the exact reviewed Klimov identity a temporary password and full access.

This is a deliberately narrow production saga for the single reviewed invited
identity.  It never sends email.  It preserves opaque Auth user metadata,
confirms the exact Auth UUID, installs a one-dispatch temporary password,
requires a password change on first login, and then calls one atomic database
RPC that grants the audited operator waiver and every currently active
workspace project.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
import re
import sys
from typing import Any, Callable, Protocol

from scripts.adopt_klimov_partial_onboarding import (
    CLASS_INVITED_PROVENANCE,
    EXPECTED_REPOSITORY,
    PartialAdoptionSnapshot,
    _classify_provenance,
    _parsed_utc,
    _read_exact_owner_authority,
    _read_snapshot,
)
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
    PASSWORD_CHANGE_COMPLETED_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    PASSWORD_DISPATCH_ID_MARKER,
    MemberProvisionError,
    PasswordDispatch,
    ProvisioningAuthority,
    _reserve_password_dispatch,
    _resume_password_dispatch,
    _transition_password_dispatch,
    _validated_display_name,
    _validated_password_dispatch,
    _validated_temp_password,
)


EXPECTED_WORKFLOW = "Provision Klimov direct access once"
EXPECTED_EMAIL = "v.klimov1313@gmail.com"
EXPECTED_USER_ID = "995dcb24-bc8b-4737-b5a6-8dd61e3e0e82"
EXPECTED_MEMBERSHIP_ID = "6ad92ac2-412e-4673-919b-cf26da699c7b"
EXPECTED_ORGANIZATION_ID = "df147614-a4ef-4e66-8b79-1b89f5481ddf"
EXPECTED_OWNER_ID = "05876b51-19e9-4118-a04b-6987642b147e"
EXPECTED_IDENTITY_ID = "d43611f4-4a43-49b1-94bb-829017780fd5"
EXPECTED_CREATED_AT = "2026-08-11 18:31:57.031658+00"
EXPECTED_CREATED_AFTER = datetime(2026, 8, 11, 18, 31, 55, tzinfo=timezone.utc)
EXPECTED_CREATED_BEFORE = datetime(2026, 8, 11, 18, 32, 0, tzinfo=timezone.utc)
DIRECT_ACCESS_MARKER = "contentengine_klimov_direct_access_v1"
DIRECT_ACCESS_MARKER_VALUE = True
ACCOUNT_SLOT = "klimov"
PHASE_NEEDS_PASSWORD = "trainee_needs_temporary_password"
PHASE_IDENTITY_APPLIED = "temporary_password_identity_applied"
PHASE_COMPLETE = "operator_all_current_projects"
FINALIZE_FUNCTION = "public.system_admin_finalize_employee_access"
FINALIZE_IDEMPOTENCY_PREFIX = "github-klimov-direct-access-v1"
DEFAULT_REASON = (
    "Owner-approved direct Klimov access with forced first-login password "
    "change and all current active projects."
)
ALLOWED_PROVENANCE = frozenset({CLASS_INVITED_PROVENANCE})
BASE_APP_METADATA_KEYS = frozenset(
    {
        "provider",
        "providers",
        PASSWORD_CHANGE_REQUIRED_MARKER,
        PASSWORD_CHANGE_COMPLETED_MARKER,
    }
)
DIRECT_APP_METADATA_KEYS = BASE_APP_METADATA_KEYS | frozenset(
    {
        DIRECT_ACCESS_MARKER,
        PASSWORD_CHANGE_COMPLETED_MARKER,
        PASSWORD_DISPATCH_ID_MARKER,
    }
)


class KlimovDirectAccessError(RuntimeError):
    """A non-sensitive direct-access failure safe for Actions logs."""


@dataclass(frozen=True)
class ProjectCoverage:
    active_projects: int
    active_assignments: int


@dataclass(frozen=True)
class AuthCredentialBoundary:
    session_count: int
    refresh_token_count: int
    mfa_factor_count: int
    identity_count: int
    identity_id: str
    identity_user_id: str
    identity_provider: str
    identity_email: str
    identity_email_verified: bool
    identity_phone_verified: bool
    identity_data: dict[str, Any]


@dataclass(frozen=True)
class DirectAccessResult:
    phase: str
    identity_status: str
    membership_role: str
    active_projects: int


@dataclass(frozen=True)
class DispatchState:
    status: str
    account_slot: str


class ManagementClient(Protocol):
    def execute(self, sql: str, *, read_only: bool = False) -> Any: ...

    def get_server_key(self) -> str: ...


class DirectAuthClient(Protocol):
    def _admin_request(
        self,
        path: str,
        *,
        method: str,
        payload: dict[str, Any],
    ) -> Any: ...


def _required_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise KlimovDirectAccessError(
            f"Direct-access state field is invalid: {field}"
        )
    return value


def _read_project_coverage(
    client: ManagementClient,
    *,
    organization_id: str,
    user_id: str,
) -> ProjectCoverage:
    validated_organization_id = _validated_uuid(organization_id)
    validated_user_id = _validated_uuid(user_id)
    payload = client.execute(
        f"""
select
  (
    select count(*)::integer
    from content_factory.workspace_folders project
    where project.organization_id =
      {_sql_literal(validated_organization_id)}::uuid
      and project.kind = 'project'
      and project.status = 'active'
  ) as active_projects,
  (
    select count(*)::integer
    from content_factory.workspace_project_memberships project_membership
    join content_factory.workspace_folders project
      on project.id = project_membership.project_id
     and project.organization_id = project_membership.organization_id
    where project_membership.organization_id =
      {_sql_literal(validated_organization_id)}::uuid
      and project_membership.profile_id =
        {_sql_literal(validated_user_id)}::uuid
      and project_membership.status = 'active'
      and project_membership.access_role = 'member'
      and project.kind = 'project'
      and project.status = 'active'
  ) as active_assignments
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise KlimovDirectAccessError("Project coverage could not be resolved")
    return ProjectCoverage(
        active_projects=_required_int(
            rows[0].get("active_projects"), field="active_projects"
        ),
        active_assignments=_required_int(
            rows[0].get("active_assignments"), field="active_assignments"
        ),
    )


def _read_dispatch_state(
    client: ManagementClient,
    *,
    dispatch: PasswordDispatch,
) -> DispatchState | None:
    payload = client.execute(
        f"""
select status, account_slot
from content_factory.member_password_dispatches
where dispatch_id = {_sql_literal(dispatch.dispatch_id)}
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if not rows:
        return None
    if len(rows) != 1:
        raise KlimovDirectAccessError("Klimov password dispatch is ambiguous")
    status = str(rows[0].get("status") or "")
    account_slot = str(rows[0].get("account_slot") or "")
    if status not in {"reserved", "identity_applied", "completed", "failed"}:
        raise KlimovDirectAccessError("Klimov password dispatch state is invalid")
    return DispatchState(status=status, account_slot=account_slot)


def _validate_dispatch_for_phase(
    state: DispatchState | None,
    *,
    phase: str,
) -> None:
    allowed: dict[str, frozenset[str | None]] = {
        PHASE_NEEDS_PASSWORD: frozenset({None, "reserved"}),
        PHASE_IDENTITY_APPLIED: frozenset({"reserved", "identity_applied"}),
        PHASE_COMPLETE: frozenset({"identity_applied", "completed"}),
    }
    status = None if state is None else state.status
    if (
        phase not in allowed
        or status not in allowed[phase]
        or (state is not None and state.account_slot != ACCOUNT_SLOT)
    ):
        raise KlimovDirectAccessError(
            "Klimov password dispatch does not match the saga phase"
        )


def _read_auth_credential_boundary(
    client: ManagementClient,
    *,
    user_id: str,
) -> AuthCredentialBoundary:
    validated_user_id = _validated_uuid(user_id)
    payload = client.execute(
        f"""
select
  (
    select count(*)::integer
    from auth.sessions session
    where session.user_id = {_sql_literal(validated_user_id)}::uuid
  ) as session_count,
  (
    select count(*)::integer
    from auth.refresh_tokens refresh_token
    where refresh_token.user_id::text = {_sql_literal(validated_user_id)}
  ) as refresh_token_count,
  (
    select count(*)::integer
    from auth.mfa_factors factor
    where factor.user_id = {_sql_literal(validated_user_id)}::uuid
  ) as mfa_factor_count,
  count(identity.id)::integer as identity_count,
  coalesce(min(identity.id::text), '') as identity_id,
  coalesce(min(identity.user_id::text), '') as identity_user_id,
  coalesce(min(identity.provider), '') as identity_provider,
  coalesce(min(identity.identity_data ->> 'email'), '') as identity_email,
  coalesce(bool_and(
    (identity.identity_data -> 'email_verified') = 'true'::jsonb
  ), false) as identity_email_verified,
  coalesce(bool_and(
    (identity.identity_data -> 'phone_verified') = 'true'::jsonb
  ), false) as identity_phone_verified,
  coalesce(
    jsonb_agg(identity.identity_data order by identity.id) -> 0,
    '{{}}'::jsonb
  ) as identity_data
from auth.identities identity
where identity.user_id = {_sql_literal(validated_user_id)}::uuid
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise KlimovDirectAccessError(
            "Klimov Auth credential boundary could not be resolved"
        )
    row = rows[0]
    email_verified = row.get("identity_email_verified")
    phone_verified = row.get("identity_phone_verified")
    identity_data = row.get("identity_data")
    if (
        not isinstance(email_verified, bool)
        or not isinstance(phone_verified, bool)
        or type(identity_data) is not dict
    ):
        raise KlimovDirectAccessError(
            "Klimov Auth credential boundary response was invalid"
        )
    return AuthCredentialBoundary(
        session_count=_required_int(row.get("session_count"), field="session_count"),
        refresh_token_count=_required_int(
            row.get("refresh_token_count"), field="refresh_token_count"
        ),
        mfa_factor_count=_required_int(
            row.get("mfa_factor_count"), field="mfa_factor_count"
        ),
        identity_count=_required_int(
            row.get("identity_count"), field="identity_count"
        ),
        identity_id=str(row.get("identity_id") or ""),
        identity_user_id=str(row.get("identity_user_id") or ""),
        identity_provider=str(row.get("identity_provider") or ""),
        identity_email=str(row.get("identity_email") or ""),
        identity_email_verified=email_verified,
        identity_phone_verified=phone_verified,
        identity_data=dict(identity_data),
    )


def _validate_auth_credential_boundary(
    boundary: AuthCredentialBoundary,
    *,
    snapshot: PartialAdoptionSnapshot,
) -> None:
    expected_identity_data = {
        "sub": EXPECTED_USER_ID,
        "email": EXPECTED_EMAIL,
        "email_verified": False,
        "phone_verified": False,
    }
    if (
        boundary.session_count != 0
        or boundary.refresh_token_count != 0
        or boundary.mfa_factor_count != 0
        or boundary.identity_count != 1
        or boundary.identity_id != EXPECTED_IDENTITY_ID
        or boundary.identity_user_id != EXPECTED_USER_ID
        or boundary.identity_provider != "email"
        or boundary.identity_email != EXPECTED_EMAIL
        or boundary.identity_email_verified
        or boundary.identity_phone_verified
        or boundary.identity_data != expected_identity_data
    ):
        raise KlimovDirectAccessError(
            "Klimov Auth credential boundary changed or is not eligible"
        )


def _base_app_metadata_valid(metadata: dict[str, Any]) -> bool:
    return (
        type(metadata) is dict
        and frozenset(metadata) == BASE_APP_METADATA_KEYS
        and metadata.get("provider") == "email"
        and metadata.get("providers") == ["email"]
        and metadata.get(PASSWORD_CHANGE_REQUIRED_MARKER) is True
        and metadata.get(PASSWORD_CHANGE_COMPLETED_MARKER) is False
    )


def _direct_app_metadata_valid(metadata: dict[str, Any]) -> bool:
    dispatch_id = metadata.get(PASSWORD_DISPATCH_ID_MARKER)
    try:
        _validated_password_dispatch(str(dispatch_id or ""), ACCOUNT_SLOT)
    except MemberProvisionError:
        return False
    return (
        type(metadata) is dict
        and frozenset(metadata) == DIRECT_APP_METADATA_KEYS
        and metadata.get("provider") == "email"
        and metadata.get("providers") == ["email"]
        and metadata.get(PASSWORD_CHANGE_REQUIRED_MARKER) is True
        and metadata.get(PASSWORD_CHANGE_COMPLETED_MARKER) is False
        and metadata.get(DIRECT_ACCESS_MARKER) is DIRECT_ACCESS_MARKER_VALUE
    )


def _expected_direct_metadata(
    metadata: dict[str, Any],
    *,
    dispatch: PasswordDispatch,
) -> dict[str, Any]:
    if not _base_app_metadata_valid(metadata):
        raise KlimovDirectAccessError(
            "Klimov Auth app metadata does not match the reviewed preflight"
        )
    expected = dict(metadata)
    expected[DIRECT_ACCESS_MARKER] = DIRECT_ACCESS_MARKER_VALUE
    expected[PASSWORD_CHANGE_COMPLETED_MARKER] = False
    expected[PASSWORD_DISPATCH_ID_MARKER] = dispatch.dispatch_id
    return expected


def _confirmation_metadata_transition_valid(
    before: dict[str, Any],
    after: dict[str, Any],
) -> bool:
    """Permit only GoTrue's optional email_verified confirmation transition."""

    if type(before) is not dict or type(after) is not dict:
        return False
    if before == after:
        return True
    before_copy = dict(before)
    after_copy = dict(after)
    missing = object()
    before_verified = before_copy.pop("email_verified", missing)
    after_verified = after_copy.pop("email_verified", missing)
    before_is_permitted = before_verified is missing or before_verified is False
    return before_copy == after_copy and before_is_permitted and after_verified is True


def _validate_common_snapshot(
    snapshot: PartialAdoptionSnapshot,
    *,
    email: str,
    display_name: str,
    owner_email: str,
    authority: ProvisioningAuthority,
) -> str:
    normalized_email = _validated_email(email)
    normalized_owner_email = _validated_email(owner_email)
    validated_display_name = _validated_display_name(display_name)
    created_at = _parsed_utc(snapshot.auth_created_at)
    expected_invite_metadata = {
        "invited_by": authority.invited_by,
        "intended_role": "trainee",
        "organization_id": authority.organization_id,
    }
    confirmed_invite_metadata = {
        **expected_invite_metadata,
        "email_verified": True,
    }
    invite_metadata_valid = (
        snapshot.raw_user_meta_data == expected_invite_metadata
        or (
            snapshot.email_confirmed
            and snapshot.raw_user_meta_data == confirmed_invite_metadata
        )
    )
    if (
        snapshot.auth_match_count != 1
        or snapshot.user_id != EXPECTED_USER_ID
        or normalized_email != EXPECTED_EMAIL
        or snapshot.auth_email != normalized_email
        or snapshot.auth_created_at != EXPECTED_CREATED_AT
        or not EXPECTED_CREATED_AFTER <= created_at < EXPECTED_CREATED_BEFORE
        or not snapshot.auth_active
        or snapshot.signed_in
        or snapshot.auth_provider != "email"
        or snapshot.auth_providers != ("email",)
        or not invite_metadata_valid
        or snapshot.profile_id != snapshot.user_id
        or snapshot.profile_email != normalized_email
        or snapshot.profile_display_name not in {"", validated_display_name}
        or snapshot.profile_status != "active"
        or snapshot.organization_id != authority.organization_id
        or authority.organization_id != EXPECTED_ORGANIZATION_ID
        or snapshot.organization_slug != OWNER_ORGANIZATION_SLUG
        or snapshot.organization_status != "active"
        or snapshot.authority_id != authority.invited_by
        or authority.invited_by != EXPECTED_OWNER_ID
        or snapshot.authority_email != normalized_owner_email
        or snapshot.authority_auth_email != normalized_owner_email
        or not snapshot.authority_is_active_owner
        or normalized_owner_email == normalized_email
        or snapshot.membership_organization_id != authority.organization_id
        or snapshot.membership_id != EXPECTED_MEMBERSHIP_ID
        or snapshot.membership_profile_id != snapshot.user_id
        or snapshot.membership_status != "active"
        or snapshot.membership_permissions != ()
        or snapshot.membership_count != 1
        or snapshot.training_attempt_count != 0
        or snapshot.training_certification_count != 0
    ):
        raise KlimovDirectAccessError(
            "Klimov state does not match the reviewed direct-access boundary"
        )
    classification = _classify_provenance(snapshot)
    if classification not in ALLOWED_PROVENANCE:
        raise KlimovDirectAccessError("Klimov provisioning provenance is invalid")
    return classification


def _waiver_is_empty(snapshot: PartialAdoptionSnapshot) -> bool:
    return (
        snapshot.waiver_id,
        snapshot.waiver_organization_id,
        snapshot.waiver_profile_id,
        snapshot.waiver_status,
        snapshot.waiver_scope,
        snapshot.waiver_previous_role,
        snapshot.waiver_granted_role,
        snapshot.waiver_grant_reason,
        snapshot.waiver_granted_by,
    ) == ("", "", "", "", "", "", "", "", "")


def _validate_phase(
    snapshot: PartialAdoptionSnapshot,
    coverage: ProjectCoverage,
    *,
    email: str,
    display_name: str,
    owner_email: str,
    authority: ProvisioningAuthority,
    reason: str,
) -> str:
    _validate_common_snapshot(
        snapshot,
        email=email,
        display_name=display_name,
        owner_email=owner_email,
        authority=authority,
    )
    trainee_database_state = (
        snapshot.membership_role == "trainee"
        and snapshot.waiver_count == 0
        and _waiver_is_empty(snapshot)
        and snapshot.project_membership_count == 0
        and coverage.active_assignments == 0
    )
    if (
        trainee_database_state
        and not snapshot.email_confirmed
        and _base_app_metadata_valid(snapshot.app_metadata)
    ):
        return PHASE_NEEDS_PASSWORD
    if (
        trainee_database_state
        and snapshot.email_confirmed
        and not snapshot.no_encrypted_password
        and _direct_app_metadata_valid(snapshot.app_metadata)
    ):
        return PHASE_IDENTITY_APPLIED
    complete_database_state = (
        snapshot.email_confirmed
        and not snapshot.no_encrypted_password
        and _direct_app_metadata_valid(snapshot.app_metadata)
        and snapshot.profile_display_name == _validated_display_name(display_name)
        and snapshot.membership_role == "operator"
        and snapshot.waiver_count == 1
        and _validated_uuid(snapshot.waiver_organization_id)
        == authority.organization_id
        and _validated_uuid(snapshot.waiver_profile_id) == snapshot.user_id
        and snapshot.waiver_status == "active"
        and snapshot.waiver_scope == "workspace_generation"
        and snapshot.waiver_previous_role == "trainee"
        and snapshot.waiver_granted_role == "operator"
        and snapshot.waiver_grant_reason == reason
        and _validated_uuid(snapshot.waiver_granted_by) == authority.invited_by
        and coverage.active_assignments == coverage.active_projects
    )
    if complete_database_state:
        return PHASE_COMPLETE
    raise KlimovDirectAccessError(
        "Klimov direct-access saga phase is not safely resumable"
    )


def _matches_auth_transition(
    before: PartialAdoptionSnapshot,
    after: PartialAdoptionSnapshot,
    *,
    expected_metadata: dict[str, Any],
) -> bool:
    if (
        not after.email_confirmed
        or after.no_encrypted_password
        or after.app_metadata != expected_metadata
        or not _confirmation_metadata_transition_valid(
            before.raw_user_meta_data,
            after.raw_user_meta_data,
        )
    ):
        return False
    normalized_after = replace(
        after,
        email_confirmed=before.email_confirmed,
        no_encrypted_password=before.no_encrypted_password,
        app_metadata=before.app_metadata,
        raw_user_meta_data=before.raw_user_meta_data,
    )
    return normalized_after == before


def _apply_temporary_password(
    auth_client: DirectAuthClient,
    *,
    user_id: str,
    password: str,
    app_metadata: dict[str, Any],
) -> None:
    validated_user_id = _validated_uuid(user_id)
    validated_password = _validated_temp_password(password)
    response = auth_client._admin_request(
        f"/auth/v1/admin/users/{validated_user_id}",
        method="PUT",
        payload={
            "password": validated_password,
            "email_confirm": True,
            "app_metadata": dict(app_metadata),
        },
    )
    if not isinstance(response, dict):
        raise KlimovDirectAccessError("Supabase Auth update response was invalid")
    try:
        response_user_id = _validated_uuid(response.get("id"))
    except OwnerBootstrapError as exc:
        raise KlimovDirectAccessError(
            "Supabase Auth update response was invalid"
        ) from exc
    if response_user_id != validated_user_id:
        raise KlimovDirectAccessError("Supabase Auth updated an unexpected identity")


def _finalize_database_access(
    auth_client: DirectAuthClient,
    *,
    authority: ProvisioningAuthority,
    user_id: str,
    display_name: str,
    reason: str,
    password_dispatch_id: str,
) -> dict[str, Any]:
    validated_user_id = _validated_uuid(user_id)
    idempotency_key = (
        f"{FINALIZE_IDEMPOTENCY_PREFIX}:"
        f"{authority.organization_id}:{validated_user_id}"
    )
    result_payload = auth_client._admin_request(
        "/rest/v1/rpc/system_admin_finalize_employee_access",
        method="POST",
        payload={
            "p_payload": {
                "organization_id": authority.organization_id,
                "user_id": validated_user_id,
                "changed_by": authority.invited_by,
                "display_name": display_name,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "password_dispatch_id": password_dispatch_id,
            }
        },
    )
    if not isinstance(result_payload, dict):
        raise KlimovDirectAccessError(
            "Direct-access database finalization response was invalid"
        )
    result = dict(result_payload)
    if (
        result.get("ok") is not True
        or result.get("organization_id") != authority.organization_id
        or result.get("user_id") != validated_user_id
        or result.get("role") != "operator"
        or result.get("waiver_active") is not True
    ):
        raise KlimovDirectAccessError(
            "Direct-access database finalization was not confirmed"
        )
    active_projects = _required_int(
        result.get("active_project_count"), field="active_project_count"
    )
    active_assignments = _required_int(
        result.get("active_project_membership_count"),
        field="active_project_membership_count",
    )
    if active_projects != active_assignments:
        raise KlimovDirectAccessError(
            "Direct-access project coverage was not confirmed"
        )
    return result


def _github_apply_context() -> None:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_WORKFLOW") != EXPECTED_WORKFLOW
        or os.environ.get("GITHUB_JOB") != "provision"
        or re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")) is None
    ):
        raise KlimovDirectAccessError(
            "Apply requires the protected Klimov direct-access workflow on main"
        )


def _github_actions_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def provision_klimov_direct_access(
    *,
    management_client: ManagementClient,
    auth_client_factory: Callable[[str], DirectAuthClient],
    email: str,
    display_name: str,
    owner_email: str,
    temporary_password: str,
    password_dispatch_id: str,
    reason: str = DEFAULT_REASON,
) -> DirectAccessResult:
    normalized_email = _validated_email(email)
    validated_display_name = _validated_display_name(display_name)
    normalized_owner_email = _validated_email(owner_email)
    requested_dispatch = _validated_password_dispatch(
        password_dispatch_id,
        ACCOUNT_SLOT,
    )
    if not 10 <= len(reason.strip()) <= 1000:
        raise KlimovDirectAccessError("Direct-access audit reason is invalid")
    authority = _read_exact_owner_authority(
        management_client,
        owner_email=normalized_owner_email,
    )
    initial = _read_snapshot(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
        authority_id=authority.invited_by,
    )
    initial_coverage = _read_project_coverage(
        management_client,
        organization_id=authority.organization_id,
        user_id=initial.user_id,
    )
    initial_auth_boundary = _read_auth_credential_boundary(
        management_client,
        user_id=initial.user_id,
    )
    _validate_auth_credential_boundary(
        initial_auth_boundary,
        snapshot=initial,
    )
    initial_phase = _validate_phase(
        initial,
        initial_coverage,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
        reason=reason,
    )
    initial_dispatch_state = _read_dispatch_state(
        management_client,
        dispatch=requested_dispatch,
    )
    _validate_dispatch_for_phase(
        initial_dispatch_state,
        phase=initial_phase,
    )
    repeated = _read_snapshot(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
        authority_id=authority.invited_by,
    )
    repeated_coverage = _read_project_coverage(
        management_client,
        organization_id=authority.organization_id,
        user_id=repeated.user_id,
    )
    repeated_auth_boundary = _read_auth_credential_boundary(
        management_client,
        user_id=repeated.user_id,
    )
    _validate_auth_credential_boundary(
        repeated_auth_boundary,
        snapshot=repeated,
    )
    repeated_phase = _validate_phase(
        repeated,
        repeated_coverage,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
        reason=reason,
    )
    repeated_dispatch_state = _read_dispatch_state(
        management_client,
        dispatch=requested_dispatch,
    )
    _validate_dispatch_for_phase(
        repeated_dispatch_state,
        phase=repeated_phase,
    )
    if (
        repeated != initial
        or repeated_coverage != initial_coverage
        or repeated_auth_boundary != initial_auth_boundary
        or repeated_dispatch_state != initial_dispatch_state
        or repeated_phase != initial_phase
    ):
        raise KlimovDirectAccessError(
            "Klimov direct-access state changed during preflight"
        )
    if initial_phase == PHASE_COMPLETE:
        completed_dispatch = _validated_password_dispatch(
            str(initial.app_metadata.get(PASSWORD_DISPATCH_ID_MARKER) or ""),
            ACCOUNT_SLOT,
        )
        resumable_dispatch = _resume_password_dispatch(
            management_client,
            dispatch=completed_dispatch,
        )
        if resumable_dispatch is not None:
            _transition_password_dispatch(
                management_client,
                dispatch=resumable_dispatch,
                from_status="identity_applied",
                to_status="completed",
            )
        return DirectAccessResult(
            phase=PHASE_COMPLETE,
            identity_status="existing",
            membership_role="operator",
            active_projects=initial_coverage.active_projects,
        )

    server_key = management_client.get_server_key()
    auth_client = auth_client_factory(server_key)
    saga_dispatch: PasswordDispatch | None = None
    current = repeated
    current_coverage = repeated_coverage
    identity_status = "existing"

    if initial_phase == PHASE_NEEDS_PASSWORD:
        password = _validated_temp_password(temporary_password)
        dispatch = requested_dispatch
        expected_metadata = _expected_direct_metadata(
            current.app_metadata,
            dispatch=dispatch,
        )
        _reserve_password_dispatch(
            management_client,
            dispatch=dispatch,
            email=normalized_email,
            password=password,
            server_key=server_key,
        )
        _apply_temporary_password(
            auth_client,
            user_id=current.user_id,
            password=password,
            app_metadata=expected_metadata,
        )
        after_auth = _read_snapshot(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
            authority_id=authority.invited_by,
        )
        after_auth_coverage = _read_project_coverage(
            management_client,
            organization_id=authority.organization_id,
            user_id=after_auth.user_id,
        )
        after_auth_boundary = _read_auth_credential_boundary(
            management_client,
            user_id=after_auth.user_id,
        )
        _validate_auth_credential_boundary(
            after_auth_boundary,
            snapshot=after_auth,
        )
        after_auth_dispatch = _read_dispatch_state(
            management_client,
            dispatch=dispatch,
        )
        _validate_dispatch_for_phase(
            after_auth_dispatch,
            phase=PHASE_IDENTITY_APPLIED,
        )
        normalized_after_auth_boundary = after_auth_boundary
        if (
            not _matches_auth_transition(
                current,
                after_auth,
                expected_metadata=expected_metadata,
            )
            or after_auth_coverage != current_coverage
            or normalized_after_auth_boundary != initial_auth_boundary
            or _validate_phase(
                after_auth,
                after_auth_coverage,
                email=normalized_email,
                display_name=validated_display_name,
                owner_email=normalized_owner_email,
                authority=authority,
                reason=reason,
            )
            != PHASE_IDENTITY_APPLIED
        ):
            raise KlimovDirectAccessError(
                "Klimov Auth password transition was not verified"
            )
        _transition_password_dispatch(
            management_client,
            dispatch=dispatch,
            from_status="reserved",
            to_status="identity_applied",
        )
        saga_dispatch = dispatch
        current = after_auth
        identity_status = "password_set"
    else:
        recorded_dispatch = _validated_password_dispatch(
            str(current.app_metadata.get(PASSWORD_DISPATCH_ID_MARKER) or ""),
            ACCOUNT_SLOT,
        )
        saga_dispatch = _resume_password_dispatch(
            management_client,
            dispatch=recorded_dispatch,
        )
        if saga_dispatch is None:
            raise KlimovDirectAccessError(
                "Klimov password dispatch is not safely resumable"
            )
        identity_status = "password_existing"

    _finalize_database_access(
        auth_client,
        authority=authority,
        user_id=current.user_id,
        display_name=validated_display_name,
        reason=reason,
        password_dispatch_id=saga_dispatch.dispatch_id,
    )
    final = _read_snapshot(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
        authority_id=authority.invited_by,
    )
    final_coverage = _read_project_coverage(
        management_client,
        organization_id=authority.organization_id,
        user_id=final.user_id,
    )
    final_auth_boundary = _read_auth_credential_boundary(
        management_client,
        user_id=final.user_id,
    )
    _validate_auth_credential_boundary(
        final_auth_boundary,
        snapshot=final,
    )
    final_dispatch_state = _read_dispatch_state(
        management_client,
        dispatch=saga_dispatch,
    )
    _validate_dispatch_for_phase(
        final_dispatch_state,
        phase=PHASE_COMPLETE,
    )
    if initial_phase == PHASE_NEEDS_PASSWORD:
        normalized_final_auth_boundary = final_auth_boundary
        if normalized_final_auth_boundary != initial_auth_boundary:
            raise KlimovDirectAccessError(
                "Klimov Auth credential boundary changed during finalization"
            )
    else:
        if final_auth_boundary != initial_auth_boundary:
            raise KlimovDirectAccessError(
                "Klimov Auth credential boundary changed during finalization"
            )
    final_phase = _validate_phase(
        final,
        final_coverage,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
        reason=reason,
    )
    if final_phase != PHASE_COMPLETE:
        raise KlimovDirectAccessError(
            "Klimov direct-access final state was not verified"
        )
    if saga_dispatch is not None:
        _transition_password_dispatch(
            management_client,
            dispatch=saga_dispatch,
            from_status="identity_applied",
            to_status="completed",
        )
    return DirectAccessResult(
        phase=final_phase,
        identity_status=identity_status,
        membership_role=final.membership_role,
        active_projects=final_coverage.active_projects,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the exact reviewed Klimov account without email",
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--password-dispatch-id", required=True)
    parser.add_argument("--reason", default=DEFAULT_REASON)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    temporary_password = os.environ.get(
        "CONTENTENGINE_MEMBER_DISPATCH_PASSWORD",
        "",
    )
    try:
        _github_apply_context()
        validated_password = _validated_temp_password(temporary_password)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(
                f"::add-mask::{_github_actions_escape(validated_password)}",
                flush=True,
            )
        project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
        publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        management_client = SupabaseManagementClient(
            project_ref=project_ref,
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )

        def auth_client_factory(server_key: str) -> SupabaseAuthClient:
            return SupabaseAuthClient(
                project_ref=project_ref,
                server_key=server_key,
                publishable_key=publishable_key,
            )

        result = provision_klimov_direct_access(
            management_client=management_client,
            auth_client_factory=auth_client_factory,
            email=args.email,
            display_name=args.display_name,
            owner_email=args.owner_email,
            temporary_password=validated_password,
            password_dispatch_id=args.password_dispatch_id,
            reason=args.reason,
        )
    except (
        KlimovDirectAccessError,
        MemberProvisionError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Klimov direct access stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Klimov direct access stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1
    print(
        "Klimov direct access complete: "
        f"phase={result.phase} identity={result.identity_status} "
        f"role={result.membership_role} projects={result.active_projects}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
