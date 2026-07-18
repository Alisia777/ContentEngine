from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.public_pilot.gate_matrix import PUBLIC_PILOT_ROLES
from app.team.errors import (
    SupabaseAdminError,
    TeamPermissionError,
    TeamStateError,
    TeamValidationError,
)
from app.team.supabase_admin import SupabaseAuthAdminClient, build_supabase_admin_client
from app.team.types import TeamInviteResult, TeamMemberView


TEAM_MANAGER_ROLES = frozenset({"owner", "admin"})
TEAM_ROLE_ALLOWLIST = frozenset(PUBLIC_PILOT_ROLES)


class TeamService:
    def __init__(
        self,
        db: Session,
        admin_client_factory: Callable[[], SupabaseAuthAdminClient] = build_supabase_admin_client,
    ) -> None:
        self.db = db
        self.admin_client_factory = admin_client_factory

    def roster(self, *, organization_id: int, actor_user_profile_id: int) -> list[TeamMemberView]:
        self._require_manager(organization_id, actor_user_profile_id)
        memberships = list(
            self.db.scalars(
                select(models.Membership)
                .options(selectinload(models.Membership.user_profile))
                .where(models.Membership.organization_id == organization_id)
                .order_by(models.Membership.status, models.Membership.role, models.Membership.id)
            )
        )
        return [
            TeamMemberView(
                membership_id=item.id,
                user_profile_id=item.user_profile_id,
                email=item.user_profile.email,
                display_name=item.user_profile.display_name,
                role=item.role,
                status=item.status,
                profile_active=bool(item.user_profile.is_active),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in memberships
        ]

    def invite_or_add(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        email: str,
        role: str,
        display_name: str | None = None,
        redirect_to: str | None = None,
    ) -> TeamInviteResult:
        # Serialize membership mutations per organization on databases that
        # support row locks. This closes duplicate-invite and last-owner races.
        actor_membership = self._require_manager(
            organization_id,
            actor_user_profile_id,
            lock_organization=True,
        )
        normalized_email = self._email(email)
        normalized_role = self._role(role)
        cleaned_name = self._display_name(display_name)
        safe_redirect = self._redirect_url(redirect_to)
        self._require_role_authority(actor_membership, normalized_role)

        preexisting_email_profiles = list(
            self.db.scalars(
                select(models.UserProfile)
                .where(func.lower(models.UserProfile.email) == normalized_email)
                .limit(2)
            )
        )
        invited = False
        invite_method = "existing_supabase_user"
        client = None
        try:
            client = self.admin_client_factory()
            admin_user = client.find_user_by_email(normalized_email)
            if admin_user is None:
                # A local email match is not proof of Auth ownership. Do not
                # send a second invite when the provider cannot bind it to a
                # stable subject; an operator must reconcile the identity.
                if preexisting_email_profiles:
                    raise TeamStateError(
                        "The local identity does not match a Supabase Auth subject."
                    )
                admin_user = client.invite_user(
                    email=normalized_email,
                    display_name=cleaned_name,
                    redirect_to=safe_redirect,
                )
                invited = True
                invite_method = "supabase_invite"
            try:
                provider_email = self._email(admin_user.email)
            except TeamValidationError as exc:
                raise SupabaseAdminError(
                    "Supabase Auth Admin returned an invalid identity."
                ) from exc
            if provider_email != normalized_email:
                raise SupabaseAdminError(
                    "Supabase Auth Admin returned a different identity."
                )
        except SupabaseAdminError:
            self._audit(
                organization_id=organization_id,
                actor_user_profile_id=actor_user_profile_id,
                action="team_member_invite",
                status="error",
                reason="supabase_admin_unavailable",
                target_profile_id=None,
                metadata={
                    "role": normalized_role,
                    "email_domain": normalized_email.rsplit("@", 1)[1],
                },
                commit=True,
            )
            raise
        finally:
            close_client = getattr(client, "close", None)
            if callable(close_client):
                close_client()

        # Resolve both keys again after the provider lookup/invite so a local
        # profile is usable only when email and provider subject identify the
        # same row. Never repair stale bindings implicitly in a team invite.
        matching_profiles = list(
            self.db.scalars(
                select(models.UserProfile)
                .where(func.lower(models.UserProfile.email) == normalized_email)
                .limit(2)
            )
        )
        if len(matching_profiles) > 1:
            raise TeamStateError("Duplicate identity records require operator reconciliation.")
        email_profile = matching_profiles[0] if matching_profiles else None
        subject_profiles = list(
            self.db.scalars(
                select(models.UserProfile)
                .where(models.UserProfile.supabase_user_id == admin_user.user_id)
                .limit(2)
            )
        )
        if len(subject_profiles) > 1:
            raise TeamStateError("Duplicate identity records require operator reconciliation.")
        subject_profile = subject_profiles[0] if subject_profiles else None

        if email_profile is not None and email_profile.supabase_user_id != admin_user.user_id:
            raise TeamStateError("The local email is bound to a different Auth subject.")
        if subject_profile is not None:
            try:
                stored_email = self._email(subject_profile.email)
            except TeamValidationError as exc:
                raise TeamStateError(
                    "The local Auth identity has an invalid email binding."
                ) from exc
            if stored_email != provider_email:
                raise TeamStateError("The local Auth subject is bound to a different email.")
        if (
            email_profile is not None
            and subject_profile is not None
            and email_profile.id != subject_profile.id
        ):
            raise TeamStateError("Local identity bindings require operator reconciliation.")

        profile = subject_profile or email_profile
        if profile is None:
            profile = models.UserProfile(
                supabase_user_id=admin_user.user_id,
                email=provider_email,
                display_name=cleaned_name or admin_user.display_name,
                status="active",
                is_active=True,
                metadata_json={"provisioning_source": invite_method},
            )
            self.db.add(profile)
            self.db.flush()
        else:
            if not profile.is_active or profile.status != "active":
                self._audit(
                    organization_id=organization_id,
                    actor_user_profile_id=actor_user_profile_id,
                    action="team_member_invite",
                    status="denied",
                    reason="target_profile_inactive",
                    target_profile_id=profile.id,
                    metadata={"role": normalized_role, "invite_method": invite_method},
                    commit=True,
                )
                raise TeamStateError(
                    "Inactive profiles must be reactivated by an identity administrator."
                )
            if cleaned_name:
                profile.display_name = cleaned_name

        matches = list(
            self.db.scalars(
                select(models.Membership).where(
                    models.Membership.organization_id == organization_id,
                    models.Membership.user_profile_id == profile.id,
                )
            )
        )
        if len(matches) > 1:
            self.db.rollback()
            raise TeamStateError("Duplicate membership records require operator reconciliation.")
        membership = matches[0] if matches else None
        created = membership is None
        previous_role = membership.role if membership is not None else None
        previous_status = membership.status if membership is not None else None
        if membership is None:
            membership = models.Membership(
                organization_id=organization_id,
                user_profile_id=profile.id,
                role=normalized_role,
                status="active",
                permissions_json=[],
            )
            self.db.add(membership)
        else:
            self._require_role_authority(
                actor_membership,
                normalized_role,
                existing_role=membership.role,
            )
            if membership.status not in {"active", "suspended"}:
                raise TeamStateError("This membership state cannot be reactivated by an invite.")
            if membership.role == "owner" and normalized_role != "owner":
                self._require_not_last_owner(organization_id, membership.id)
            membership.role = normalized_role
            membership.status = "active"
        self.db.flush()
        audit_action = (
            "team_member_invite"
            if invited
            else "team_member_add"
            if created
            else "team_membership_update"
        )
        self._audit(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action=audit_action,
            status="allowed",
            reason=(
                "member_invited"
                if invited
                else "existing_user_added"
                if created
                else "existing_membership_updated"
            ),
            target_profile_id=profile.id,
            entity_id=str(membership.id),
            metadata={
                "role": normalized_role,
                "invite_method": invite_method,
                "membership_created": created,
                "email_domain": normalized_email.rsplit("@", 1)[1],
                "previous_role": previous_role,
                "previous_status": previous_status,
            },
            commit=False,
        )
        self.db.commit()
        self.db.refresh(membership)
        return TeamInviteResult(
            user_profile_id=profile.id,
            membership_id=membership.id,
            email=profile.email,
            role=membership.role,
            invited=invited,
            membership_created=created,
        )

    def suspend_membership(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        membership_id: int,
    ) -> models.Membership:
        actor = self._require_manager(
            organization_id,
            actor_user_profile_id,
            lock_organization=True,
        )
        target = self._owned_membership(organization_id, membership_id)
        self._require_membership_manageable(actor, target)
        if target.status not in {"active", "suspended"}:
            raise TeamStateError("Only active memberships can be suspended.")
        if target.status == "suspended":
            return target
        if target.role == "owner":
            self._require_not_last_owner(organization_id, target.id)
        target.status = "suspended"
        self._audit(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action="team_membership_suspend",
            status="allowed",
            reason="membership_suspended",
            target_profile_id=target.user_profile_id,
            entity_id=str(target.id),
            metadata={"target_role": target.role},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(target)
        return target

    def reactivate_membership(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        membership_id: int,
    ) -> models.Membership:
        actor = self._require_manager(
            organization_id,
            actor_user_profile_id,
            lock_organization=True,
        )
        target = self._owned_membership(organization_id, membership_id)
        self._require_membership_manageable(actor, target)
        if target.status not in {"active", "suspended"}:
            raise TeamStateError("Only suspended memberships can be reactivated.")
        if not target.user_profile.is_active or target.user_profile.status != "active":
            raise TeamStateError("User profile is globally inactive.")
        if target.status == "active":
            return target
        target.status = "active"
        self._audit(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            action="team_membership_reactivate",
            status="allowed",
            reason="membership_reactivated",
            target_profile_id=target.user_profile_id,
            entity_id=str(target.id),
            metadata={"target_role": target.role},
            commit=False,
        )
        self.db.commit()
        self.db.refresh(target)
        return target

    def _require_manager(
        self,
        organization_id: int,
        actor_user_profile_id: int,
        *,
        lock_organization: bool = False,
    ) -> models.Membership:
        organization_query = select(models.Organization).where(
            models.Organization.id == organization_id
        )
        if lock_organization:
            organization_query = organization_query.with_for_update()
        organization = self.db.scalar(organization_query)
        actor = self.db.get(models.UserProfile, actor_user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == actor_user_profile_id,
                models.Membership.status == "active",
                models.Membership.role.in_(TEAM_MANAGER_ROLES),
            )
        )
        if (
            organization is None
            or organization.status != "active"
            or actor is None
            or not actor.is_active
            or actor.status != "active"
            or membership is None
        ):
            raise TeamPermissionError("Only an active owner or admin can manage the team.")
        return membership

    def _require_role_authority(
        self,
        actor: models.Membership,
        target_role: str,
        *,
        existing_role: str | None = None,
    ) -> None:
        if actor.role == "admin" and (
            target_role in {"owner", "admin"}
            or existing_role in {"owner", "admin"}
        ):
            raise TeamPermissionError("Admins cannot grant or change owner or admin roles.")

    def _require_membership_manageable(
        self,
        actor: models.Membership,
        target: models.Membership,
    ) -> None:
        if actor.id == target.id:
            raise TeamStateError("A manager cannot suspend or reactivate their own membership.")
        if actor.role == "admin" and target.role in {"owner", "admin"}:
            raise TeamPermissionError("Admins cannot change owner or admin membership state.")

    def _require_not_last_owner(self, organization_id: int, target_membership_id: int) -> None:
        active_owners = self.db.scalar(
            select(func.count())
            .select_from(models.Membership)
            .where(
                models.Membership.organization_id == organization_id,
                models.Membership.role == "owner",
                models.Membership.status == "active",
                models.Membership.id != target_membership_id,
            )
        ) or 0
        if active_owners < 1:
            raise TeamStateError("The last active owner cannot be removed or suspended.")

    def _owned_membership(self, organization_id: int, membership_id: int) -> models.Membership:
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.id == membership_id,
                models.Membership.organization_id == organization_id,
            )
        )
        if membership is None:
            raise TeamStateError("Membership was not found in this organization.")
        return membership

    def _audit(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        action: str,
        status: str,
        reason: str,
        target_profile_id: int | None,
        metadata: dict,
        entity_id: str | None = None,
        commit: bool,
    ) -> models.AuditLog:
        safe_metadata = {
            key: value
            for key, value in metadata.items()
            if not any(marker in key.lower() for marker in ("secret", "token", "password", "authorization", "cookie"))
        }
        if target_profile_id is not None:
            safe_metadata["target_user_profile_id"] = target_profile_id
        log = models.AuditLog(
            user_profile_id=actor_user_profile_id,
            organization_id=organization_id,
            action=action,
            status=status,
            reason=reason,
            entity_type="membership",
            entity_id=entity_id,
            metadata_json=safe_metadata,
        )
        self.db.add(log)
        if commit:
            self.db.commit()
            self.db.refresh(log)
        return log

    @staticmethod
    def _email(value: str) -> str:
        email = str(value or "").strip().lower()
        if (
            len(email) > 254
            or not re.fullmatch(
                r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]++@"
                r"(?:[A-Za-z0-9-]++\.)++[A-Za-z]{2,63}+",
                email,
            )
            or ".." in email
        ):
            raise TeamValidationError("A valid email address is required.")
        return email

    @staticmethod
    def _role(value: str) -> str:
        role = str(value or "").strip().lower()
        if role not in TEAM_ROLE_ALLOWLIST:
            raise TeamValidationError("Unknown team role.")
        return role

    @staticmethod
    def _display_name(value: str | None) -> str | None:
        name = " ".join(str(value or "").strip().split())
        if len(name) > 180:
            raise TeamValidationError("Display name is too long.")
        return name or None

    @staticmethod
    def _redirect_url(value: str | None) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        parsed = urlsplit(raw)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise TeamValidationError("Invite redirect must be a public HTTPS URL.")
        return raw
