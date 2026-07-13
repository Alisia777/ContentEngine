from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.team import SupabaseAdminError, SupabaseAuthAdminClient, build_supabase_admin_client


BOOTSTRAP_ADVISORY_LOCK_ID = 18918490631056724
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}"
)
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class CloudOwnerBootstrapError(Exception):
    """Fail-closed bootstrap error with a non-sensitive operator code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CloudOwnerBootstrapResult:
    status: str
    identity_status: str
    organization_id: int
    user_profile_id: int
    membership_id: int


def bootstrap_cloud_owner(
    db: Session,
    *,
    email: str,
    display_name: str,
    organization_name: str,
    organization_slug: str,
    admin_client_factory: Callable[[], SupabaseAuthAdminClient] | None = None,
    alembic_config_path: Path | str = ROOT / "alembic.ini",
    require_postgresql: bool = True,
) -> CloudOwnerBootstrapResult:
    """Provision exactly one initial owner without creating or migrating tables."""

    normalized_email = _validated_email(email)
    cleaned_display_name = _validated_text(display_name, field="display_name", limit=180)
    cleaned_organization_name = _validated_text(
        organization_name,
        field="organization_name",
        limit=180,
    )
    cleaned_slug = _validated_slug(organization_slug)
    resolved_admin_client_factory = admin_client_factory or build_supabase_admin_client

    _require_database_ready(
        db,
        alembic_config_path=Path(alembic_config_path),
        require_postgresql=require_postgresql,
    )
    _acquire_bootstrap_lock(db)

    organization, profile, membership = _preflight_existing_state(
        db,
        email=normalized_email,
        organization_name=cleaned_organization_name,
        organization_slug=cleaned_slug,
    )

    client = None
    try:
        client = resolved_admin_client_factory()
        admin_user = client.find_user_by_email(normalized_email)
        if admin_user is None:
            if profile is not None:
                raise CloudOwnerBootstrapError("provider_identity_conflict")
            admin_user = client.invite_user(
                email=normalized_email,
                display_name=cleaned_display_name,
            )
            identity_status = "invited"
        else:
            identity_status = "existing"
    except SupabaseAdminError as exc:
        raise CloudOwnerBootstrapError("identity_provider_unavailable") from exc
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()

    provider_email = _provider_email(admin_user.email)
    provider_user_id = str(admin_user.user_id or "").strip()
    if (
        provider_email != normalized_email
        or not provider_user_id
        or len(provider_user_id) > 255
        or any(ord(character) < 33 or ord(character) > 126 for character in provider_user_id)
    ):
        raise CloudOwnerBootstrapError("provider_identity_conflict")

    # Re-check after the network call. Existing target rows are locked by the
    # preflight query; this second pass also closes the empty-database race.
    organization, profile, membership = _preflight_existing_state(
        db,
        email=normalized_email,
        organization_name=cleaned_organization_name,
        organization_slug=cleaned_slug,
    )

    if profile is None:
        identity_matches = list(
            db.scalars(
                select(models.UserProfile)
                .where(models.UserProfile.supabase_user_id == provider_user_id)
                .limit(2)
            )
        )
        if identity_matches:
            raise CloudOwnerBootstrapError("identity_conflict")
    else:
        if profile.supabase_user_id != provider_user_id:
            raise CloudOwnerBootstrapError("identity_conflict")
        if profile.email.casefold() != provider_email.casefold():
            raise CloudOwnerBootstrapError("email_conflict")

    created_rows = 0
    if organization is None:
        organization = models.Organization(
            name=cleaned_organization_name,
            slug=cleaned_slug,
            status="active",
            settings_json={},
        )
        db.add(organization)
        db.flush()
        created_rows += 1

    if profile is None:
        profile = models.UserProfile(
            supabase_user_id=provider_user_id,
            email=provider_email,
            display_name=cleaned_display_name,
            status="active",
            is_active=True,
            metadata_json={"provisioning_source": "cloud_owner_bootstrap"},
        )
        db.add(profile)
        db.flush()
        created_rows += 1
    else:
        profile.email = provider_email
        profile.display_name = cleaned_display_name

    if membership is None:
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role="owner",
            status="active",
            permissions_json=[],
        )
        db.add(membership)
        db.flush()
        created_rows += 1
    elif (
        membership.organization_id != organization.id
        or membership.user_profile_id != profile.id
        or membership.role != "owner"
        or membership.status != "active"
    ):
        raise CloudOwnerBootstrapError("membership_conflict")

    status = "unchanged"
    if created_rows == 3:
        status = "created"
    elif created_rows:
        status = "completed"
    return CloudOwnerBootstrapResult(
        status=status,
        identity_status=identity_status,
        organization_id=organization.id,
        user_profile_id=profile.id,
        membership_id=membership.id,
    )


def _require_database_ready(
    db: Session,
    *,
    alembic_config_path: Path,
    require_postgresql: bool,
) -> None:
    dialect = db.get_bind().dialect.name
    if require_postgresql and dialect != "postgresql":
        raise CloudOwnerBootstrapError("postgresql_required")

    config = Config(str(alembic_config_path))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    expected_heads = set(ScriptDirectory.from_config(config).get_heads())
    current_heads = set(MigrationContext.configure(db.connection()).get_current_heads())
    if not expected_heads or current_heads != expected_heads:
        raise CloudOwnerBootstrapError("alembic_head_required")


def _acquire_bootstrap_lock(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": BOOTSTRAP_ADVISORY_LOCK_ID},
        )


def _preflight_existing_state(
    db: Session,
    *,
    email: str,
    organization_name: str,
    organization_slug: str,
) -> tuple[
    models.Organization | None,
    models.UserProfile | None,
    models.Membership | None,
]:
    organizations = list(
        db.scalars(
            select(models.Organization)
            .where(models.Organization.slug == organization_slug)
            .order_by(models.Organization.id)
            .limit(2)
            .with_for_update()
        )
    )
    if len(organizations) > 1:
        raise CloudOwnerBootstrapError("organization_conflict")
    organization = organizations[0] if organizations else None
    if organization is not None and (
        organization.slug != organization_slug
        or organization.name != organization_name
        or organization.status != "active"
    ):
        raise CloudOwnerBootstrapError("organization_conflict")

    profiles = list(
        db.scalars(
            select(models.UserProfile)
            .where(func.lower(models.UserProfile.email) == email)
            .order_by(models.UserProfile.id)
            .limit(2)
            .with_for_update()
        )
    )
    if len(profiles) > 1:
        raise CloudOwnerBootstrapError("identity_conflict")
    profile = profiles[0] if profiles else None
    if profile is not None and (
        profile.email.casefold() != email.casefold()
        or not profile.is_active
        or profile.status != "active"
    ):
        raise CloudOwnerBootstrapError("email_conflict")

    if profile is not None:
        foreign_membership_query = select(func.count()).select_from(models.Membership).where(
            models.Membership.user_profile_id == profile.id
        )
        if organization is not None:
            foreign_membership_query = foreign_membership_query.where(
                models.Membership.organization_id != organization.id
            )
        if (db.scalar(foreign_membership_query) or 0) > 0:
            raise CloudOwnerBootstrapError("membership_conflict")

    memberships: list[models.Membership] = []
    if organization is not None and profile is not None:
        memberships = list(
            db.scalars(
                select(models.Membership)
                .where(
                    models.Membership.organization_id == organization.id,
                    models.Membership.user_profile_id == profile.id,
                )
                .order_by(models.Membership.id)
                .limit(2)
                .with_for_update()
            )
        )
    if len(memberships) > 1:
        raise CloudOwnerBootstrapError("membership_conflict")
    membership = memberships[0] if memberships else None
    if membership is not None and (
        membership.role != "owner" or membership.status != "active"
    ):
        raise CloudOwnerBootstrapError("membership_conflict")

    bootstrap_is_complete = (
        organization is not None and profile is not None and membership is not None
    )
    if not bootstrap_is_complete:
        organization_count = db.scalar(
            select(func.count()).select_from(models.Organization)
        ) or 0
        profile_count = db.scalar(select(func.count()).select_from(models.UserProfile)) or 0
        membership_count = db.scalar(select(func.count()).select_from(models.Membership)) or 0
        if organization_count != (1 if organization is not None else 0):
            raise CloudOwnerBootstrapError("organization_conflict")
        if profile_count != (1 if profile is not None else 0):
            raise CloudOwnerBootstrapError("identity_conflict")
        if membership_count != 0:
            raise CloudOwnerBootstrapError("membership_conflict")
    return organization, profile, membership


def _validated_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email) or ".." in email:
        raise CloudOwnerBootstrapError("invalid_email")
    return email


def _provider_email(value: str) -> str:
    try:
        return _validated_email(value)
    except CloudOwnerBootstrapError as exc:
        raise CloudOwnerBootstrapError("provider_identity_conflict") from exc


def _validated_text(value: str, *, field: str, limit: int) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if (
        not cleaned
        or len(cleaned) > limit
        or any(ord(character) < 32 or ord(character) == 127 for character in cleaned)
    ):
        raise CloudOwnerBootstrapError(f"invalid_{field}")
    return cleaned


def _validated_slug(value: str) -> str:
    slug = str(value or "").strip()
    if len(slug) > 160 or not SLUG_PATTERN.fullmatch(slug):
        raise CloudOwnerBootstrapError("invalid_organization_slug")
    return slug


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision the first cloud owner after Alembic migrations. "
            "Supabase credentials are read only from server environment variables."
        )
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--organization-name",
        "--org-name",
        dest="organization_name",
        required=True,
    )
    parser.add_argument(
        "--organization-slug",
        "--org-slug",
        dest="organization_slug",
        required=True,
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory=None,
    admin_client_factory: Callable[[], SupabaseAuthAdminClient] | None = None,
    require_postgresql: bool = True,
) -> int:
    args = _parser().parse_args(argv)
    resolved_session_factory = session_factory or SessionLocal
    resolved_admin_client_factory = admin_client_factory or build_supabase_admin_client
    try:
        with resolved_session_factory() as db:
            result = bootstrap_cloud_owner(
                db,
                email=args.email,
                display_name=args.display_name,
                organization_name=args.organization_name,
                organization_slug=args.organization_slug,
                admin_client_factory=resolved_admin_client_factory,
                require_postgresql=require_postgresql,
            )
            db.commit()
    except CloudOwnerBootstrapError as exc:
        print(f"cloud_owner_bootstrap status=failed code={exc.code}", file=sys.stderr)
        return 1
    except Exception:
        # Deliberately omit exception text and traceback: provider/database
        # exceptions can carry request headers or connection credentials.
        print("cloud_owner_bootstrap status=failed code=unexpected_error", file=sys.stderr)
        return 1

    print(
        "cloud_owner_bootstrap "
        f"status={result.status} "
        f"identity_status={result.identity_status} "
        f"organization_id={result.organization_id} "
        f"user_profile_id={result.user_profile_id} "
        f"membership_id={result.membership_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
