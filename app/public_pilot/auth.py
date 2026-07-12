from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import exceptions as jwt_exceptions
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.public_pilot.local_auth import LOCAL_ISSUER


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-") or "altea-beauty"


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class PublicPilotUser:
    profile: models.UserProfile
    organization: models.Organization
    membership: models.Membership

    @property
    def role(self) -> str:
        return self.membership.role


@lru_cache(maxsize=8)
def _cached_jwks_client(url: str, lifespan: int, timeout: float) -> jwt.PyJWKClient:
    """Reuse the verified JWK set while still honoring key-rotation TTLs."""

    return jwt.PyJWKClient(
        url,
        cache_keys=False,
        cache_jwk_set=True,
        lifespan=max(1, lifespan),
        timeout=max(1.0, timeout),
    )


def clear_supabase_jwks_cache() -> None:
    _cached_jwks_client.cache_clear()


class SupabaseJWTValidator:
    ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "RS256"})

    def __init__(self):
        self.settings = get_settings()

    def validate(self, token: str) -> dict[str, Any]:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("invalid token parts")
            header = json.loads(_b64url_decode(parts[0]))
            payload = json.loads(_b64url_decode(parts[1]))
        except (ValueError, TypeError, UnicodeDecodeError, binascii.Error) as exc:
            raise HTTPException(status_code=401, detail="invalid_token") from exc
        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise HTTPException(status_code=401, detail="invalid_token")
        algorithm = header.get("alg")

        local_session = payload.get("auth_source") == "local"
        signing_secret = self.settings.local_session_secret if local_session else self.settings.supabase_jwt_secret
        if algorithm == "HS256" and signing_secret:
            signed = ".".join(parts[:2]).encode("utf-8")
            expected = hmac.new(signing_secret.encode("utf-8"), signed, hashlib.sha256).digest()
            actual = _b64url_decode(parts[2])
            if not hmac.compare_digest(expected, actual):
                raise HTTPException(status_code=401, detail="invalid_token_signature")
        elif algorithm in self.ASYMMETRIC_ALGORITHMS and not local_session:
            payload = self._validate_asymmetric(token, algorithm)
        else:
            raise HTTPException(status_code=401, detail="auth_verifier_not_configured")

        self._validate_claims(payload, local_session=local_session)
        return payload

    def _validate_asymmetric(self, token: str, algorithm: str) -> dict[str, Any]:
        jwks_url = self._jwks_url()
        if not jwks_url:
            raise HTTPException(status_code=401, detail="auth_verifier_not_configured")
        issuer = self._expected_issuer()
        try:
            client = _cached_jwks_client(
                jwks_url,
                self.settings.supabase_jwks_cache_seconds,
                self.settings.supabase_auth_timeout_seconds,
            )
            signing_key = client.get_signing_key_from_jwt(token).key
            options = {"require": ["exp", "sub", "aud"]}
            return jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                audience=self.settings.supabase_audience,
                issuer=issuer,
                leeway=self.settings.supabase_jwt_clock_skew_seconds,
                options=options,
            )
        except jwt_exceptions.ExpiredSignatureError as exc:
            raise HTTPException(status_code=401, detail="token_expired") from exc
        except jwt_exceptions.PyJWKClientConnectionError as exc:
            raise HTTPException(status_code=503, detail="auth_verifier_unavailable") from exc
        except jwt_exceptions.PyJWKClientError as exc:
            raise HTTPException(status_code=401, detail="invalid_token_signature") from exc
        except jwt_exceptions.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="invalid_token") from exc

    def _validate_claims(self, payload: dict[str, Any], *, local_session: bool) -> None:
        leeway = max(0, int(self.settings.supabase_jwt_clock_skew_seconds))
        now = int(datetime.now(UTC).timestamp())
        try:
            expires_at = int(payload["exp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail="missing_expiration") from exc
        if expires_at <= now - leeway:
            raise HTTPException(status_code=401, detail="token_expired")
        not_before = payload.get("nbf")
        if not_before is not None:
            try:
                if int(not_before) > now + leeway:
                    raise HTTPException(status_code=401, detail="token_not_active")
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=401, detail="invalid_token") from exc

        if local_session and payload.get("iss") != LOCAL_ISSUER:
            raise HTTPException(status_code=401, detail="invalid_issuer")
        expected_issuer = self._expected_issuer()
        if not local_session and expected_issuer and payload.get("iss") != expected_issuer:
            raise HTTPException(status_code=401, detail="invalid_issuer")
        audience = payload.get("aud")
        expected_audience = self.settings.supabase_audience
        if expected_audience:
            audience_matches = (
                expected_audience in audience
                if isinstance(audience, (list, tuple, set))
                else audience == expected_audience
            )
            if not audience_matches:
                raise HTTPException(status_code=401, detail="invalid_audience")
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="missing_subject")

    def _jwks_url(self) -> str | None:
        if self.settings.supabase_jwks_url:
            return str(self.settings.supabase_jwks_url).strip()
        if self.settings.supabase_url:
            return f"{str(self.settings.supabase_url).rstrip('/')}/auth/v1/.well-known/jwks.json"
        return None

    def _expected_issuer(self) -> str | None:
        if self.settings.supabase_issuer:
            return str(self.settings.supabase_issuer).rstrip("/")
        if self.settings.supabase_url:
            return f"{str(self.settings.supabase_url).rstrip('/')}/auth/v1"
        return None


def _extract_token(request: Request) -> str | None:
    refreshed_token = getattr(request.state, "public_pilot_session_token", None)
    if isinstance(refreshed_token, str) and refreshed_token:
        return refreshed_token
    settings = get_settings()
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return request.cookies.get(settings.session_cookie_name)


def form_csrf_token(request: Request) -> str:
    """Derive a form token from the current signed, HttpOnly session value."""

    session_token = _extract_token(request)
    if session_token:
        return hmac.new(
            b"qvf-public-pilot-form-csrf-v1",
            session_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    return "local-development-no-auth"


def require_form_csrf(request: Request, submitted_token: str | None) -> None:
    """Fail closed for authenticated browser writes without a session-bound token."""

    if not get_settings().auth_required:
        return
    candidate = str(submitted_token or "").strip()
    if not candidate or not hmac.compare_digest(candidate, form_csrf_token(request)):
        raise HTTPException(status_code=403, detail="invalid_csrf_token")


def ensure_public_pilot_user(
    db: Session,
    *,
    email: str,
    display_name: str | None,
    role: str,
    supabase_user_id: str | None = None,
    mark_login: bool = False,
    authenticated_at: datetime | None = None,
    update_existing_role: bool = False,
    require_active_existing: bool = False,
) -> PublicPilotUser:
    settings = get_settings()
    org_slug = _slugify(settings.public_pilot_default_org)
    organization = db.scalar(select(models.Organization).where(models.Organization.slug == org_slug))
    if organization is None:
        organization = models.Organization(name=settings.public_pilot_default_org, slug=org_slug, settings_json={"public_pilot": True})
        db.add(organization)
        db.flush()
    elif require_active_existing and organization.status != "active":
        raise HTTPException(status_code=403, detail="active_membership_required")

    subject = supabase_user_id or f"local:{email}"
    profile = db.scalar(select(models.UserProfile).where(models.UserProfile.supabase_user_id == subject))
    if profile is None:
        profile = models.UserProfile(
            supabase_user_id=subject,
            email=email,
            display_name=display_name or email.split("@")[0].title(),
            status="active",
            is_active=True,
            metadata_json={"source": "public_pilot"},
        )
        db.add(profile)
        db.flush()
    else:
        if require_active_existing and (not profile.is_active or profile.status != "active"):
            raise HTTPException(status_code=403, detail="active_membership_required")
        profile.email = email
        profile.display_name = display_name or profile.display_name
    if mark_login:
        profile.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    elif authenticated_at and (profile.last_login_at is None or authenticated_at > profile.last_login_at):
        profile.last_login_at = authenticated_at

    membership = db.scalar(
        select(models.Membership).where(
            models.Membership.organization_id == organization.id,
            models.Membership.user_profile_id == profile.id,
        )
    )
    if membership is None:
        membership = models.Membership(
            organization_id=organization.id,
            user_profile_id=profile.id,
            role=role,
            status="active",
            permissions_json=[],
        )
        db.add(membership)
    elif require_active_existing and membership.status != "active":
        raise HTTPException(status_code=403, detail="active_membership_required")
    elif role and update_existing_role:
        membership.role = role

    db.commit()
    db.refresh(profile)
    db.refresh(organization)
    db.refresh(membership)
    return PublicPilotUser(profile=profile, organization=organization, membership=membership)


def active_public_pilot_user_from_payload(
    db: Session,
    payload: dict[str, Any],
) -> PublicPilotUser:
    """Resolve a token to an existing active membership without provisioning it.

    The database membership is authoritative.  In particular, a local-session
    token's embedded role must never reactivate or promote a stored membership.
    """

    settings = get_settings()
    subject = str(payload.get("sub") or "").strip()
    is_local_session = payload.get("auth_source") == "local"
    app_metadata = payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {}
    claimed_organization_slug = app_metadata.get("organization_slug")
    if not isinstance(claimed_organization_slug, str) or not claimed_organization_slug.strip():
        claimed_organization_slug = None
    profile = db.scalar(
        select(models.UserProfile).where(models.UserProfile.supabase_user_id == subject)
    )
    organization = None
    membership = None
    if profile is not None and (claimed_organization_slug or is_local_session):
        # An explicit external organization claim is authoritative and must
        # never fall back to another membership. Local recovery sessions stay
        # pinned to the configured default organization.
        organization_slug = (
            _slugify(settings.public_pilot_default_org)
            if is_local_session
            else str(claimed_organization_slug).strip()
        )
        organization = db.scalar(
            select(models.Organization).where(models.Organization.slug == organization_slug)
        )
        if organization is not None:
            membership = db.scalar(
                select(models.Membership).where(
                    models.Membership.organization_id == organization.id,
                    models.Membership.user_profile_id == profile.id,
                )
            )
    elif profile is not None:
        rows = list(
            db.execute(
                select(models.Membership, models.Organization)
                .join(
                    models.Organization,
                    models.Organization.id == models.Membership.organization_id,
                )
                .where(models.Membership.user_profile_id == profile.id)
                .order_by(models.Membership.id)
            )
        )
        default_slug = _slugify(settings.public_pilot_default_org)
        active_rows = [
            row
            for row in rows
            if row[0].status == "active" and row[1].status == "active"
        ]
        if len(active_rows) == 1:
            membership, organization = active_rows[0]
        elif len(active_rows) > 1:
            default_active_rows = [row for row in active_rows if row[1].slug == default_slug]
            if len(default_active_rows) == 1:
                membership, organization = default_active_rows[0]
        elif len(rows) == 1:
            # Retain the concrete inactive scope so the common state check
            # returns active_membership_required instead of implying no invite.
            membership, organization = rows[0]
        elif rows:
            default_rows = [row for row in rows if row[1].slug == default_slug]
            if len(default_rows) == 1:
                membership, organization = default_rows[0]
    if profile is None or organization is None or membership is None:
        detail = "active_membership_required" if is_local_session else "public_pilot_invite_required"
        raise HTTPException(status_code=403, detail=detail)
    if (
        not profile.is_active
        or profile.status != "active"
        or organization.status != "active"
        or membership.status != "active"
    ):
        raise HTTPException(status_code=403, detail="active_membership_required")
    return PublicPilotUser(profile=profile, organization=organization, membership=membership)


def get_current_public_user(request: Request, db: Session = Depends(get_db)) -> PublicPilotUser:
    settings = get_settings()
    token = _extract_token(request)
    if token:
        payload = getattr(request.state, "public_pilot_auth_payload", None)
        if not isinstance(payload, dict):
            payload = SupabaseJWTValidator().validate(token)
        email = payload.get("email") or payload.get("user_metadata", {}).get("email") or f"{payload['sub']}@supabase.local"
        display_name = payload.get("user_metadata", {}).get("name") or payload.get("user_metadata", {}).get("full_name")
        role = payload.get("app_metadata", {}).get("role") or payload.get("role") or "viewer"
        issued_at = payload.get("iat")
        authenticated_at = None
        if isinstance(issued_at, (int, float)) and not isinstance(issued_at, bool):
            authenticated_at = datetime.fromtimestamp(issued_at, UTC).replace(tzinfo=None)
        is_local_session = payload.get("auth_source") == "local"
        if (
            settings.public_pilot_mode
            or settings.auth_required
            or settings.public_pilot_invite_only
            or is_local_session
        ):
            return active_public_pilot_user_from_payload(db, payload)
        return ensure_public_pilot_user(
            db,
            email=email,
            display_name=display_name,
            role=role,
            supabase_user_id=payload["sub"],
            authenticated_at=authenticated_at,
        )

    if settings.auth_required:
        raise HTTPException(status_code=401, detail="authentication_required")

    email = request.headers.get("x-public-pilot-email", settings.auth_dev_bypass_email)
    role = request.headers.get("x-public-pilot-role", "owner")
    display_name = request.headers.get("x-public-pilot-name")
    return ensure_public_pilot_user(
        db,
        email=email,
        display_name=display_name,
        role=role,
        require_active_existing=settings.public_pilot_mode or settings.auth_required,
    )

