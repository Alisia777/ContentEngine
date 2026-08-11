#!/usr/bin/env python3
"""Adopt one exact, partially-created Klimov account into protected onboarding.

This is deliberately not a generic onboarding resume.  It exists only for the
single production identity created during GitHub Actions run 31526654618 and
fails closed unless every Auth, profile, membership, training, project-access,
authority, and provenance boundary still matches the reviewed incident.

The default mode is a read-only preflight.  ``--apply`` is accepted only from
the dedicated protected GitHub Actions workflow on ``main``.  Apply mode reads
the complete snapshot a second time before revealing a server key, confirms
that exact Auth UUID with an email-confirm-only PUT, verifies the post-state,
then grants the audited waiver and sends the standard recovery email.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
import re
import sys
from typing import Any

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
from scripts.grant_training_access_waiver import (
    TrainingWaiverError,
    _verify_training_waiver,
    grant_training_access_waiver,
)
from scripts.provision_employee_without_training import (
    _has_exact_recovery_provisioning_markers,
)
from scripts.provision_supabase_member import (
    MEMBER_PROVISION_MARKER,
    PASSWORD_CHANGE_REQUIRED_MARKER,
    MemberProvisionError,
    ProvisioningAuthority,
    _validated_display_name,
)


SOURCE_CREATION_RUN_ID = "31526654618"
SOURCE_CREATED_AFTER = datetime(2026, 8, 11, 19, 12, 27, tzinfo=timezone.utc)
SOURCE_CREATED_BEFORE = datetime(2026, 8, 11, 19, 12, 31, tzinfo=timezone.utc)
SOURCE_CREATED_AFTER_SQL = "2026-08-11T19:12:27Z"
SOURCE_CREATED_BEFORE_SQL = "2026-08-11T19:12:31Z"
EXPECTED_REPOSITORY = "Alisia777/ContentEngine"
EXPECTED_WORKFLOW = "Adopt Klimov partial onboarding once"
CLASS_NO_PROVENANCE = "one_off_adoption_no_provenance"
CLASS_LIMITED_PROVENANCE = (
    "one_off_adoption_verified_limited_member_provenance"
)
CLASS_INVITED_PROVENANCE = (
    "one_off_adoption_verified_invited_member_provenance"
)
PHASE_UNCONFIRMED_TRAINEE = "unconfirmed_trainee_without_waiver"
PHASE_CONFIRMED_TRAINEE = "confirmed_trainee_without_waiver"
PHASE_CONFIRMED_OPERATOR = "confirmed_operator_with_one_off_waiver"


class KlimovPartialAdoptionError(RuntimeError):
    """A non-sensitive, fail-closed partial-adoption failure."""


@dataclass(frozen=True)
class ProvenanceEvent:
    event_id: str
    organization_id: str
    profile_id: str
    event_name: str
    source: str
    entity_type: str
    entity_id: str
    properties: dict[str, Any]
    idempotency_key: str
    occurred_at: str


@dataclass(frozen=True)
class ProvenanceReceipt:
    receipt_id: str
    organization_id: str
    actor_id: str
    command_name: str
    idempotency_key: str
    result: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class PartialAdoptionSnapshot:
    auth_match_count: int
    user_id: str
    auth_email: str
    auth_created_at: str
    auth_created_in_source_window: bool
    email_confirmed: bool
    auth_active: bool
    signed_in: bool
    no_encrypted_password: bool
    app_metadata: dict[str, Any]
    auth_display_name: str
    auth_provider: str
    auth_providers: tuple[str, ...]
    profile_id: str
    profile_email: str
    profile_display_name: str
    profile_status: str
    organization_id: str
    organization_slug: str
    organization_status: str
    authority_id: str
    authority_email: str
    authority_auth_email: str
    authority_is_active_owner: bool
    membership_id: str
    membership_organization_id: str
    membership_profile_id: str
    membership_role: str
    membership_status: str
    membership_permissions: tuple[Any, ...]
    membership_created_at: str
    membership_updated_at: str
    membership_count: int
    waiver_count: int
    waiver_id: str
    waiver_organization_id: str
    waiver_profile_id: str
    waiver_status: str
    waiver_scope: str
    waiver_previous_role: str
    waiver_granted_role: str
    waiver_grant_reason: str
    waiver_granted_by: str
    training_attempt_count: int
    training_certification_count: int
    project_membership_count: int
    provenance_events: tuple[ProvenanceEvent, ...]
    provenance_receipts: tuple[ProvenanceReceipt, ...]


@dataclass(frozen=True)
class GitHubAuditContext:
    repository: str
    run_id: str
    run_attempt: str
    actor: str
    sha: str


@dataclass(frozen=True)
class PartialAdoptionResult:
    classification: str
    phase: str
    identity_status: str
    membership_role: str
    recovery_status: str


_SAFE_FIELD_PATH = re.compile(
    r"^[a-z][a-z0-9_]*(?:\[[0-9]+\])?"
    r"(?:\.[a-z][a-z0-9_]*(?:\[[0-9]+\])?)*$"
)


def _invalid_snapshot_field(field_name: str) -> KlimovPartialAdoptionError:
    safe_field_name = (
        field_name
        if _SAFE_FIELD_PATH.fullmatch(field_name) is not None
        else "internal_field"
    )
    return KlimovPartialAdoptionError(
        f"Partial-adoption snapshot is invalid: field={safe_field_name}"
    )


def _required_int(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid_snapshot_field(field_name or key)
    return value


def _required_bool(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> bool:
    value = row.get(key)
    if not isinstance(value, bool):
        raise _invalid_snapshot_field(field_name or key)
    return value


def _required_text(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise _invalid_snapshot_field(field_name or key)
    return value


def _text(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise _invalid_snapshot_field(field_name or key)
    return value


def _required_dict(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> dict[str, Any]:
    value = row.get(key)
    if not isinstance(value, dict):
        raise _invalid_snapshot_field(field_name or key)
    return dict(value)


def _required_list(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> list[Any]:
    value = row.get(key)
    if not isinstance(value, list):
        raise _invalid_snapshot_field(field_name or key)
    return list(value)


def _required_uuid(
    row: dict[str, Any],
    key: str,
    *,
    field_name: str | None = None,
) -> str:
    try:
        return _validated_uuid(row.get(key))
    except OwnerBootstrapError:
        raise _invalid_snapshot_field(field_name or key) from None


def _parse_event(value: Any, *, index: int) -> ProvenanceEvent:
    prefix = f"provenance_events[{index}]"
    if not isinstance(value, dict):
        raise _invalid_snapshot_field(prefix)
    properties = value.get("properties")
    if not isinstance(properties, dict):
        raise _invalid_snapshot_field(f"{prefix}.properties")
    return ProvenanceEvent(
        event_id=_required_uuid(
            value, "event_id", field_name=f"{prefix}.event_id"
        ),
        organization_id=_required_uuid(
            value,
            "organization_id",
            field_name=f"{prefix}.organization_id",
        ),
        profile_id=_required_uuid(
            value, "profile_id", field_name=f"{prefix}.profile_id"
        ),
        event_name=_required_text(
            value, "event_name", field_name=f"{prefix}.event_name"
        ),
        source=_required_text(
            value, "source", field_name=f"{prefix}.source"
        ),
        entity_type=_required_text(
            value, "entity_type", field_name=f"{prefix}.entity_type"
        ),
        entity_id=_required_text(
            value, "entity_id", field_name=f"{prefix}.entity_id"
        ),
        properties=dict(properties),
        idempotency_key=_required_text(
            value,
            "idempotency_key",
            field_name=f"{prefix}.idempotency_key",
        ),
        occurred_at=_required_text(
            value, "occurred_at", field_name=f"{prefix}.occurred_at"
        ),
    )


def _parse_receipt(value: Any, *, index: int) -> ProvenanceReceipt:
    prefix = f"provenance_receipts[{index}]"
    if not isinstance(value, dict):
        raise _invalid_snapshot_field(prefix)
    result = value.get("result")
    if not isinstance(result, dict):
        raise _invalid_snapshot_field(f"{prefix}.result")
    return ProvenanceReceipt(
        receipt_id=_required_uuid(
            value, "receipt_id", field_name=f"{prefix}.receipt_id"
        ),
        organization_id=_required_uuid(
            value,
            "organization_id",
            field_name=f"{prefix}.organization_id",
        ),
        actor_id=_required_uuid(
            value, "actor_id", field_name=f"{prefix}.actor_id"
        ),
        command_name=_required_text(
            value, "command_name", field_name=f"{prefix}.command_name"
        ),
        idempotency_key=_required_text(
            value,
            "idempotency_key",
            field_name=f"{prefix}.idempotency_key",
        ),
        result=dict(result),
        created_at=_required_text(
            value, "created_at", field_name=f"{prefix}.created_at"
        ),
    )


def _read_exact_owner_authority(
    client: SupabaseManagementClient,
    *,
    owner_email: str,
) -> ProvisioningAuthority:
    normalized_owner_email = _validated_email(owner_email)
    payload = client.execute(
        f"""
select
  organization.id::text as organization_id,
  owner_membership.profile_id::text as invited_by
from auth.users owner_auth
join content_factory.profiles owner_profile
  on owner_profile.id = owner_auth.id
join content_factory.memberships owner_membership
  on owner_membership.profile_id = owner_auth.id
join content_factory.organizations organization
  on organization.id = owner_membership.organization_id
where lower(owner_auth.email) = {_sql_literal(normalized_owner_email)}
  and owner_profile.email = {_sql_literal(normalized_owner_email)}
  and owner_profile.status = 'active'
  and owner_membership.role = 'owner'
  and owner_membership.status = 'active'
  and organization.slug = {_sql_literal(OWNER_ORGANIZATION_SLUG)}
  and organization.status = 'active'
  and owner_auth.email_confirmed_at is not null
  and owner_auth.deleted_at is null
  and (
    owner_auth.banned_until is null
    or owner_auth.banned_until <= now()
  )
order by owner_auth.id
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise KlimovPartialAdoptionError(
            "Exact active production owner authority could not be resolved"
        )
    return ProvisioningAuthority(
        organization_id=_validated_uuid(rows[0].get("organization_id")),
        invited_by=_validated_uuid(rows[0].get("invited_by")),
    )


def _read_snapshot(
    client: SupabaseManagementClient,
    *,
    email: str,
    organization_id: str,
    authority_id: str,
) -> PartialAdoptionSnapshot:
    normalized_email = _validated_email(email)
    validated_organization_id = _validated_uuid(organization_id)
    validated_authority_id = _validated_uuid(authority_id)
    payload = client.execute(
        f"""
with matching_auth as (
  select
    auth_user.*,
    count(*) over ()::integer as auth_match_count
  from auth.users auth_user
  where lower(auth_user.email) = {_sql_literal(normalized_email)}
)
select
  auth_user.auth_match_count,
  auth_user.id::text as user_id,
  lower(auth_user.email) as auth_email,
  auth_user.created_at::text as auth_created_at,
  (
    auth_user.created_at >= timestamptz {_sql_literal(SOURCE_CREATED_AFTER_SQL)}
    and auth_user.created_at < timestamptz {_sql_literal(SOURCE_CREATED_BEFORE_SQL)}
  ) as auth_created_in_source_window,
  auth_user.email_confirmed_at is not null as email_confirmed,
  (
    auth_user.deleted_at is null
    and (
      auth_user.banned_until is null
      or auth_user.banned_until <= now()
    )
  ) as auth_active,
  auth_user.last_sign_in_at is not null as signed_in,
  nullif(btrim(coalesce(auth_user.encrypted_password, '')), '') is null
    as no_encrypted_password,
  coalesce(auth_user.raw_app_meta_data, '{{}}'::jsonb) as app_metadata,
  coalesce(auth_user.raw_user_meta_data ->> 'display_name', '')
    as auth_display_name,
  coalesce(auth_user.raw_app_meta_data ->> 'provider', '') as auth_provider,
  coalesce(auth_user.raw_app_meta_data -> 'providers', '[]'::jsonb)
    as auth_providers,
  coalesce(profile.id::text, '') as profile_id,
  coalesce(profile.email, '') as profile_email,
  coalesce(profile.display_name, '') as profile_display_name,
  coalesce(profile.status, '') as profile_status,
  coalesce(organization.id::text, '') as organization_id,
  coalesce(organization.slug, '') as organization_slug,
  coalesce(organization.status, '') as organization_status,
  {_sql_literal(validated_authority_id)} as authority_id,
  coalesce(authority_profile.email, '') as authority_email,
  coalesce(lower(authority_auth.email), '') as authority_auth_email,
  exists (
    select 1
    from content_factory.memberships owner_membership
    join content_factory.profiles owner_profile
      on owner_profile.id = owner_membership.profile_id
    join auth.users owner_auth
      on owner_auth.id = owner_membership.profile_id
    where owner_membership.organization_id = organization.id
      and owner_membership.profile_id = {_sql_literal(validated_authority_id)}::uuid
      and owner_membership.role = 'owner'
      and owner_membership.status = 'active'
      and owner_profile.status = 'active'
      and owner_auth.email_confirmed_at is not null
      and owner_auth.deleted_at is null
      and (
        owner_auth.banned_until is null
        or owner_auth.banned_until <= now()
      )
  ) as authority_is_active_owner,
  coalesce(membership.id::text, '') as membership_id,
  coalesce(membership.organization_id::text, '')
    as membership_organization_id,
  coalesce(membership.profile_id::text, '') as membership_profile_id,
  coalesce(membership.role, '') as membership_role,
  coalesce(membership.status, '') as membership_status,
  coalesce(membership.permissions, '[]'::jsonb) as membership_permissions,
  coalesce(membership.created_at::text, '') as membership_created_at,
  coalesce(membership.updated_at::text, '') as membership_updated_at,
  (
    select count(*)::integer
    from content_factory.memberships all_memberships
    where all_memberships.profile_id = auth_user.id
  ) as membership_count,
  (
    select count(*)::integer
    from content_factory.training_access_waivers waiver
    where waiver.profile_id = auth_user.id
  ) as waiver_count,
  coalesce(target_waiver.id::text, '') as waiver_id,
  coalesce(target_waiver.organization_id::text, '')
    as waiver_organization_id,
  coalesce(target_waiver.profile_id::text, '') as waiver_profile_id,
  coalesce(target_waiver.status, '') as waiver_status,
  coalesce(target_waiver.scope, '') as waiver_scope,
  coalesce(target_waiver.previous_role, '') as waiver_previous_role,
  coalesce(target_waiver.granted_role, '') as waiver_granted_role,
  coalesce(target_waiver.grant_reason, '') as waiver_grant_reason,
  coalesce(target_waiver.granted_by::text, '') as waiver_granted_by,
  (
    select count(*)::integer
    from content_factory.training_attempts attempt
    where attempt.profile_id = auth_user.id
  ) as training_attempt_count,
  (
    select count(*)::integer
    from content_factory.training_certifications certification
    where certification.profile_id = auth_user.id
  ) as training_certification_count,
  (
    select count(*)::integer
    from content_factory.workspace_project_memberships project_membership
    where project_membership.profile_id = auth_user.id
  ) as project_membership_count,
  coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'event_id', event.id,
        'organization_id', event.organization_id,
        'profile_id', event.profile_id,
        'event_name', event.event_name,
        'source', event.source,
        'entity_type', event.entity_type,
        'entity_id', event.entity_id,
        'properties', event.properties,
        'idempotency_key', event.idempotency_key,
        'occurred_at', event.occurred_at
      ) order by event.occurred_at, event.id
    )
    from content_factory.factory_events event
    where event.organization_id = organization.id
      and event.event_name in (
        'limited_member_provisioned',
        'member_invited_provisioned',
        'member_invite_reconciled'
      )
      and (
        (
          event.entity_type = 'membership'
          and event.entity_id = membership.id::text
        )
        or event.properties ->> 'target_user_id' = auth_user.id::text
      )
  ), '[]'::jsonb) as provenance_events,
  coalesce((
    select jsonb_agg(
      jsonb_build_object(
        'receipt_id', receipt.id,
        'organization_id', receipt.organization_id,
        'actor_id', receipt.actor_id,
        'command_name', receipt.command_name,
        'idempotency_key', receipt.idempotency_key,
        'result', receipt.result,
        'created_at', receipt.created_at
      ) order by receipt.created_at, receipt.id
    )
    from content_factory.command_receipts receipt
    where receipt.organization_id = organization.id
      and receipt.command_name in (
        'system_provision_limited_member',
        'system_provision_invited_member'
      )
      and (
        receipt.result ->> 'membership_id' = membership.id::text
        or receipt.result ->> 'user_id' = auth_user.id::text
      )
  ), '[]'::jsonb) as provenance_receipts
from matching_auth auth_user
left join content_factory.profiles profile
  on profile.id = auth_user.id
left join content_factory.organizations organization
  on organization.id = {_sql_literal(validated_organization_id)}::uuid
left join content_factory.profiles authority_profile
  on authority_profile.id = {_sql_literal(validated_authority_id)}::uuid
left join auth.users authority_auth
  on authority_auth.id = {_sql_literal(validated_authority_id)}::uuid
left join content_factory.memberships membership
  on membership.organization_id = organization.id
 and membership.profile_id = auth_user.id
left join content_factory.training_access_waivers target_waiver
  on target_waiver.organization_id = organization.id
 and target_waiver.profile_id = auth_user.id
limit 2
""".strip(),
        read_only=True,
    )
    rows = _rows_from_response(payload)
    if len(rows) != 1:
        raise KlimovPartialAdoptionError(
            "Exact partial-onboarding identity could not be resolved"
        )
    row = rows[0]
    app_metadata = _required_dict(row, "app_metadata")
    auth_providers = _required_list(row, "auth_providers")
    membership_permissions = _required_list(row, "membership_permissions")
    events = tuple(
        _parse_event(value, index=index)
        for index, value in enumerate(
            _required_list(row, "provenance_events")
        )
    )
    receipts = tuple(
        _parse_receipt(value, index=index)
        for index, value in enumerate(
            _required_list(row, "provenance_receipts")
        )
    )
    if not all(isinstance(value, str) for value in auth_providers):
        raise _invalid_snapshot_field("auth_providers")
    return PartialAdoptionSnapshot(
        auth_match_count=_required_int(row, "auth_match_count"),
        user_id=_required_uuid(row, "user_id"),
        auth_email=_required_text(row, "auth_email"),
        auth_created_at=_required_text(row, "auth_created_at"),
        auth_created_in_source_window=_required_bool(
            row, "auth_created_in_source_window"
        ),
        email_confirmed=_required_bool(row, "email_confirmed"),
        auth_active=_required_bool(row, "auth_active"),
        signed_in=_required_bool(row, "signed_in"),
        no_encrypted_password=_required_bool(row, "no_encrypted_password"),
        app_metadata=app_metadata,
        auth_display_name=_required_text(row, "auth_display_name"),
        auth_provider=_required_text(row, "auth_provider"),
        auth_providers=tuple(auth_providers),
        profile_id=_required_uuid(row, "profile_id"),
        profile_email=_required_text(row, "profile_email"),
        profile_display_name=_required_text(row, "profile_display_name"),
        profile_status=_required_text(row, "profile_status"),
        organization_id=_required_uuid(row, "organization_id"),
        organization_slug=_required_text(row, "organization_slug"),
        organization_status=_required_text(row, "organization_status"),
        authority_id=_required_uuid(row, "authority_id"),
        authority_email=_required_text(row, "authority_email"),
        authority_auth_email=_required_text(row, "authority_auth_email"),
        authority_is_active_owner=_required_bool(
            row, "authority_is_active_owner"
        ),
        membership_id=_required_uuid(row, "membership_id"),
        membership_organization_id=_required_uuid(
            row, "membership_organization_id"
        ),
        membership_profile_id=_required_uuid(row, "membership_profile_id"),
        membership_role=_required_text(row, "membership_role"),
        membership_status=_required_text(row, "membership_status"),
        membership_permissions=tuple(membership_permissions),
        membership_created_at=_required_text(row, "membership_created_at"),
        membership_updated_at=_required_text(row, "membership_updated_at"),
        membership_count=_required_int(row, "membership_count"),
        waiver_count=_required_int(row, "waiver_count"),
        waiver_id=_text(row, "waiver_id"),
        waiver_organization_id=_text(row, "waiver_organization_id"),
        waiver_profile_id=_text(row, "waiver_profile_id"),
        waiver_status=_text(row, "waiver_status"),
        waiver_scope=_text(row, "waiver_scope"),
        waiver_previous_role=_text(row, "waiver_previous_role"),
        waiver_granted_role=_text(row, "waiver_granted_role"),
        waiver_grant_reason=_text(row, "waiver_grant_reason"),
        waiver_granted_by=_text(row, "waiver_granted_by"),
        training_attempt_count=_required_int(row, "training_attempt_count"),
        training_certification_count=_required_int(
            row, "training_certification_count"
        ),
        project_membership_count=_required_int(
            row, "project_membership_count"
        ),
        provenance_events=events,
        provenance_receipts=receipts,
    )


def _parsed_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise KlimovPartialAdoptionError(
            "Partial-onboarding creation time is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise KlimovPartialAdoptionError(
            "Partial-onboarding creation time is invalid"
        )
    return parsed.astimezone(timezone.utc)


def _has_exact_contentengine_markers(metadata: dict[str, Any]) -> bool:
    allowed_keys = {
        "provider",
        "providers",
        MEMBER_PROVISION_MARKER,
        PASSWORD_CHANGE_REQUIRED_MARKER,
    }
    contentengine_keys = {
        str(key) for key in metadata if str(key).startswith("contentengine_")
    }
    return (
        set(metadata) == allowed_keys
        and contentengine_keys
        == {MEMBER_PROVISION_MARKER, PASSWORD_CHANGE_REQUIRED_MARKER}
        and _has_exact_recovery_provisioning_markers(metadata)
    )


def _classify_provenance(
    snapshot: PartialAdoptionSnapshot,
) -> str:
    events = snapshot.provenance_events
    receipts = snapshot.provenance_receipts
    if not events and not receipts:
        return CLASS_NO_PROVENANCE
    if len(events) != 1:
        raise _invalid_snapshot_field("provenance_events")
    if len(receipts) != 1:
        raise _invalid_snapshot_field("provenance_receipts")

    event = events[0]
    receipt = receipts[0]
    checks = (
        (
            event.organization_id == snapshot.organization_id,
            "provenance_events[0].organization_id",
        ),
        (
            event.profile_id == snapshot.authority_id,
            "provenance_events[0].profile_id",
        ),
        (event.source == "system", "provenance_events[0].source"),
        (
            event.entity_type == "membership",
            "provenance_events[0].entity_type",
        ),
        (
            event.entity_id == snapshot.membership_id,
            "provenance_events[0].entity_id",
        ),
        (
            receipt.organization_id == snapshot.organization_id,
            "provenance_receipts[0].organization_id",
        ),
        (
            receipt.actor_id == snapshot.authority_id,
            "provenance_receipts[0].actor_id",
        ),
        (
            event.properties.get("target_user_id") == snapshot.user_id,
            "provenance_events[0].properties.target_user_id",
        ),
        (
            event.properties.get("role") == "trainee",
            "provenance_events[0].properties.role",
        ),
        (
            receipt.result.get("ok") is True,
            "provenance_receipts[0].result.ok",
        ),
        (
            receipt.result.get("organization_id")
            == snapshot.organization_id,
            "provenance_receipts[0].result.organization_id",
        ),
        (
            receipt.result.get("user_id") == snapshot.user_id,
            "provenance_receipts[0].result.user_id",
        ),
        (
            receipt.result.get("membership_id") == snapshot.membership_id,
            "provenance_receipts[0].result.membership_id",
        ),
        (
            receipt.result.get("role") == "trainee",
            "provenance_receipts[0].result.role",
        ),
        (
            receipt.result.get("status") == "active",
            "provenance_receipts[0].result.status",
        ),
    )
    for valid, field_name in checks:
        if not valid:
            raise _invalid_snapshot_field(field_name)

    if event.event_name == "limited_member_provisioned":
        limited_checks = (
            (
                receipt.command_name == "system_provision_limited_member",
                "provenance_receipts[0].command_name",
            ),
            (
                event.idempotency_key == receipt.idempotency_key,
                "provenance_events[0].idempotency_key",
            ),
            (
                event.properties.get("already_active") is False,
                "provenance_events[0].properties.already_active",
            ),
            (
                receipt.result.get("already_active") is False,
                "provenance_receipts[0].result.already_active",
            ),
        )
        for valid, field_name in limited_checks:
            if not valid:
                raise _invalid_snapshot_field(field_name)
        return CLASS_LIMITED_PROVENANCE
    if event.event_name == "member_invited_provisioned":
        invited_checks = (
            (
                receipt.command_name == "system_provision_invited_member",
                "provenance_receipts[0].command_name",
            ),
            (
                event.idempotency_key
                == f"system-invite:{receipt.idempotency_key}",
                "provenance_events[0].idempotency_key",
            ),
            (
                "already_active" not in event.properties,
                "provenance_events[0].properties.already_active",
            ),
            (
                "already_active" not in receipt.result,
                "provenance_receipts[0].result.already_active",
            ),
        )
        for valid, field_name in invited_checks:
            if not valid:
                raise _invalid_snapshot_field(field_name)
        return CLASS_INVITED_PROVENANCE
    raise _invalid_snapshot_field("provenance_events[0].event_name")


def _matches_prior_one_off_reason(reason: str, classification: str) -> bool:
    pattern = re.compile(
        re.escape(
            "One-off Klimov partial-onboarding adoption; not a generic resume; "
            f"classification={classification}; "
            f"source_creation_run={SOURCE_CREATION_RUN_ID}; "
            f"audit={EXPECTED_REPOSITORY}/actions/runs/"
        )
        + r"(?P<run_id>[1-9][0-9]{5,20}); "
        + r"attempt=[1-9][0-9]{0,5}; "
        + r"actor=[A-Za-z0-9_.\-\[\]]{1,100}; "
        + r"sha=[0-9a-f]{40}\."
    )
    match = pattern.fullmatch(reason)
    return (
        match is not None
        and match.group("run_id") != SOURCE_CREATION_RUN_ID
    )


def _validate_snapshot(
    snapshot: PartialAdoptionSnapshot,
    *,
    email: str,
    display_name: str,
    owner_email: str,
    authority: ProvisioningAuthority,
    expected_phase: str | None = None,
) -> tuple[str, str]:
    normalized_email = _validated_email(email)
    normalized_owner_email = _validated_email(owner_email)
    validated_display_name = _validated_display_name(display_name)
    created_at = _parsed_utc(snapshot.auth_created_at)
    if (
        snapshot.auth_match_count != 1
        or snapshot.auth_email != normalized_email
        or not snapshot.auth_created_in_source_window
        or not SOURCE_CREATED_AFTER <= created_at < SOURCE_CREATED_BEFORE
        or not snapshot.auth_active
        or snapshot.signed_in
        or not snapshot.no_encrypted_password
        or not _has_exact_contentengine_markers(snapshot.app_metadata)
        or snapshot.auth_provider != "email"
        or snapshot.auth_providers != ("email",)
        or snapshot.auth_display_name != validated_display_name
        or snapshot.profile_id != snapshot.user_id
        or snapshot.profile_email != normalized_email
        or snapshot.profile_display_name != validated_display_name
        or snapshot.profile_status != "active"
        or snapshot.organization_id != authority.organization_id
        or snapshot.organization_slug != OWNER_ORGANIZATION_SLUG
        or snapshot.organization_status != "active"
        or snapshot.authority_id != authority.invited_by
        or snapshot.authority_email != normalized_owner_email
        or snapshot.authority_auth_email != normalized_owner_email
        or not snapshot.authority_is_active_owner
        or normalized_owner_email == normalized_email
        or snapshot.membership_organization_id != authority.organization_id
        or snapshot.membership_profile_id != snapshot.user_id
        or snapshot.membership_role not in {"trainee", "operator"}
        or snapshot.membership_status != "active"
        or snapshot.membership_permissions != ()
        or snapshot.membership_count != 1
        or snapshot.training_attempt_count != 0
        or snapshot.training_certification_count != 0
        or snapshot.project_membership_count != 0
    ):
        raise KlimovPartialAdoptionError(
            "Partial-onboarding state does not match the one-off adoption boundary"
        )

    classification = _classify_provenance(snapshot)
    empty_waiver = (
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
    phase: str
    if (
        snapshot.membership_role == "trainee"
        and snapshot.waiver_count == 0
        and empty_waiver
    ):
        phase = (
            PHASE_CONFIRMED_TRAINEE
            if snapshot.email_confirmed
            else PHASE_UNCONFIRMED_TRAINEE
        )
    elif (
        snapshot.email_confirmed
        and snapshot.membership_role == "operator"
        and snapshot.waiver_count == 1
        and _validated_uuid(snapshot.waiver_id)
        and _validated_uuid(snapshot.waiver_organization_id)
        == authority.organization_id
        and _validated_uuid(snapshot.waiver_profile_id) == snapshot.user_id
        and snapshot.waiver_status == "active"
        and snapshot.waiver_scope == "workspace_generation"
        and snapshot.waiver_previous_role == "trainee"
        and snapshot.waiver_granted_role == "operator"
        and _validated_uuid(snapshot.waiver_granted_by) == authority.invited_by
        and _matches_prior_one_off_reason(
            snapshot.waiver_grant_reason,
            classification,
        )
    ):
        phase = PHASE_CONFIRMED_OPERATOR
    else:
        raise KlimovPartialAdoptionError(
            "Partial-onboarding saga phase is not safely resumable"
        )
    if expected_phase is not None and phase != expected_phase:
        raise KlimovPartialAdoptionError(
            "Partial-onboarding saga changed phase unexpectedly"
        )
    return classification, phase


def _github_audit_context() -> GitHubAuditContext:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_WORKFLOW") != EXPECTED_WORKFLOW
        or os.environ.get("GITHUB_JOB") != "adopt"
    ):
        raise KlimovPartialAdoptionError(
            "Apply mode requires the protected one-off GitHub workflow on main"
        )
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
    actor = os.environ.get("GITHUB_ACTOR", "").strip()
    sha = os.environ.get("GITHUB_SHA", "").strip().lower()
    if (
        re.fullmatch(r"[1-9][0-9]{5,20}", run_id) is None
        or run_id == SOURCE_CREATION_RUN_ID
        or re.fullmatch(r"[1-9][0-9]{0,5}", run_attempt) is None
        or re.fullmatch(r"[A-Za-z0-9_.\-\[\]]{1,100}", actor) is None
        or re.fullmatch(r"[0-9a-f]{40}", sha) is None
    ):
        raise KlimovPartialAdoptionError("GitHub audit context is invalid")
    return GitHubAuditContext(
        repository=EXPECTED_REPOSITORY,
        run_id=run_id,
        run_attempt=run_attempt,
        actor=actor,
        sha=sha,
    )


def _adoption_reason(
    classification: str,
    context: GitHubAuditContext,
) -> str:
    return (
        "One-off Klimov partial-onboarding adoption; not a generic resume; "
        f"classification={classification}; "
        f"source_creation_run={SOURCE_CREATION_RUN_ID}; "
        f"audit={context.repository}/actions/runs/{context.run_id}; "
        f"attempt={context.run_attempt}; actor={context.actor}; sha={context.sha}."
    )


def _matches_waiver_transition(
    before: PartialAdoptionSnapshot,
    after: PartialAdoptionSnapshot,
) -> bool:
    return replace(
        after,
        membership_role=before.membership_role,
        membership_updated_at=before.membership_updated_at,
        waiver_count=before.waiver_count,
        waiver_id=before.waiver_id,
        waiver_organization_id=before.waiver_organization_id,
        waiver_profile_id=before.waiver_profile_id,
        waiver_status=before.waiver_status,
        waiver_scope=before.waiver_scope,
        waiver_previous_role=before.waiver_previous_role,
        waiver_granted_role=before.waiver_granted_role,
        waiver_grant_reason=before.waiver_grant_reason,
        waiver_granted_by=before.waiver_granted_by,
    ) == before


def _confirm_exact_identity(
    auth_client: SupabaseAuthClient,
    *,
    user_id: str,
) -> None:
    admin_request = getattr(auth_client, "_admin_request", None)
    if not callable(admin_request):
        raise KlimovPartialAdoptionError(
            "Supabase Auth admin client is unavailable"
        )
    # The Admin API response is not treated as authoritative.  The caller
    # immediately re-reads the exact DB snapshot and permits only the
    # confirmation bit to differ.
    admin_request(
        f"/auth/v1/admin/users/{_validated_uuid(user_id)}",
        method="PUT",
        payload={"email_confirm": True},
    )


def adopt_klimov_partial_onboarding(
    *,
    management_client: SupabaseManagementClient,
    email: str,
    display_name: str,
    owner_email: str,
    publishable_key: str,
    apply: bool,
) -> PartialAdoptionResult:
    normalized_email = _validated_email(email)
    validated_display_name = _validated_display_name(display_name)
    normalized_owner_email = _validated_email(owner_email)
    context = _github_audit_context() if apply else None
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
    classification, initial_phase = _validate_snapshot(
        initial,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
    )
    if not apply:
        return PartialAdoptionResult(
            classification=classification,
            phase=initial_phase,
            identity_status="preflight_only",
            membership_role=initial.membership_role,
            recovery_status="not_requested",
        )

    before_action = _read_snapshot(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
        authority_id=authority.invited_by,
    )
    repeated_classification, repeated_phase = _validate_snapshot(
        before_action,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
        expected_phase=initial_phase,
    )
    if (
        before_action != initial
        or repeated_classification != classification
        or repeated_phase != initial_phase
    ):
        raise KlimovPartialAdoptionError(
            "Partial-onboarding state changed before the next saga action"
        )

    if context is None:  # pragma: no cover - narrowed by apply validation above
        raise KlimovPartialAdoptionError("GitHub audit context is unavailable")
    current = before_action
    current_phase = initial_phase
    auth_client: SupabaseAuthClient | None = None
    identity_status = "confirmation_already_complete"

    if current_phase == PHASE_UNCONFIRMED_TRAINEE:
        server_key = management_client.get_server_key()
        auth_client = SupabaseAuthClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            server_key=server_key,
            publishable_key=publishable_key,
        )
        _confirm_exact_identity(auth_client, user_id=current.user_id)
        after_confirmation = _read_snapshot(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
            authority_id=authority.invited_by,
        )
        post_classification, current_phase = _validate_snapshot(
            after_confirmation,
            email=normalized_email,
            display_name=validated_display_name,
            owner_email=normalized_owner_email,
            authority=authority,
            expected_phase=PHASE_CONFIRMED_TRAINEE,
        )
        if (
            after_confirmation
            != replace(current, email_confirmed=True)
            or post_classification != classification
        ):
            raise KlimovPartialAdoptionError(
                "Auth confirmation post-verification failed"
            )
        current = after_confirmation
        identity_status = "confirmed_by_one_off_adoption"
    elif current_phase == PHASE_CONFIRMED_OPERATOR:
        identity_status = "waiver_already_complete"

    waiver_reason = (
        current.waiver_grant_reason
        if current_phase == PHASE_CONFIRMED_OPERATOR
        else _adoption_reason(classification, context)
    )
    if current_phase == PHASE_CONFIRMED_TRAINEE:
        role, helper_recovery = grant_training_access_waiver(
            management_client=management_client,
            email=normalized_email,
            expected_user_id=current.user_id,
            expected_membership_id=current.membership_id,
            expected_organization_id=authority.organization_id,
            expected_authority_id=authority.invited_by,
            expected_pre_role="trainee",
            reason=waiver_reason,
            send_recovery=False,
            publishable_key=publishable_key,
        )
        if role != "operator" or helper_recovery != "not_requested":
            raise KlimovPartialAdoptionError(
                "Training waiver helper crossed the recovery boundary"
            )
        after_waiver = _read_snapshot(
            management_client,
            email=normalized_email,
            organization_id=authority.organization_id,
            authority_id=authority.invited_by,
        )
        post_classification, current_phase = _validate_snapshot(
            after_waiver,
            email=normalized_email,
            display_name=validated_display_name,
            owner_email=normalized_owner_email,
            authority=authority,
            expected_phase=PHASE_CONFIRMED_OPERATOR,
        )
        if (
            post_classification != classification
            or after_waiver.waiver_grant_reason != waiver_reason
            or not _matches_waiver_transition(current, after_waiver)
        ):
            raise KlimovPartialAdoptionError(
                "Training waiver post-verification failed"
            )
        current = after_waiver

    if current_phase != PHASE_CONFIRMED_OPERATOR:
        raise KlimovPartialAdoptionError(
            "Partial adoption did not reach the operator phase"
        )
    _verify_training_waiver(
        management_client,
        organization_id=authority.organization_id,
        user_id=current.user_id,
        expected_membership_id=current.membership_id,
        expected_authority_id=authority.invited_by,
        expected_pre_role="trainee",
        expected_reason=waiver_reason,
    )

    if auth_client is None:
        server_key = management_client.get_server_key()
        auth_client = SupabaseAuthClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            server_key=server_key,
            publishable_key=publishable_key,
        )
    final_snapshot = _read_snapshot(
        management_client,
        email=normalized_email,
        organization_id=authority.organization_id,
        authority_id=authority.invited_by,
    )
    final_classification, final_phase = _validate_snapshot(
        final_snapshot,
        email=normalized_email,
        display_name=validated_display_name,
        owner_email=normalized_owner_email,
        authority=authority,
        expected_phase=PHASE_CONFIRMED_OPERATOR,
    )
    if (
        final_snapshot != current
        or final_classification != classification
        or final_snapshot.waiver_grant_reason != waiver_reason
    ):
        raise KlimovPartialAdoptionError(
            "Recovery target changed after final waiver verification"
        )
    auth_client.send_password_recovery(email=normalized_email)
    return PartialAdoptionResult(
        classification=classification,
        phase=final_phase,
        identity_status=identity_status,
        membership_role="operator",
        recovery_status="requested",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-off protected adoption of Klimov partial onboarding",
    )
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        management_client = SupabaseManagementClient(
            project_ref=os.environ.get("SUPABASE_PROJECT_REF", "").strip(),
            access_token=os.environ.get("SUPABASE_ACCESS_TOKEN", ""),
        )
        result = adopt_klimov_partial_onboarding(
            management_client=management_client,
            email=os.environ.get("SUPABASE_MEMBER_KLIMOV_EMAIL", ""),
            display_name=os.environ.get(
                "SUPABASE_MEMBER_KLIMOV_DISPLAY_NAME", ""
            ),
            owner_email=os.environ.get("SUPABASE_OWNER_EMAIL", ""),
            publishable_key=os.environ.get("SUPABASE_PUBLISHABLE_KEY", ""),
            apply=args.apply,
        )
    except (
        KlimovPartialAdoptionError,
        TrainingWaiverError,
        MemberProvisionError,
        OwnerBootstrapError,
    ) as exc:
        print(f"Klimov partial adoption stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Klimov partial adoption stopped: unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    print(
        "Klimov partial adoption complete: "
        f"classification={result.classification} "
        f"phase={result.phase} "
        f"identity={result.identity_status} "
        f"membership_role={result.membership_role} "
        f"recovery={result.recovery_status}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
