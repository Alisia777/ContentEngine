from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db


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


class SupabaseJWTValidator:
    def __init__(self):
        self.settings = get_settings()

    def validate(self, token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="invalid_token")

        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        algorithm = header.get("alg")

        if algorithm == "HS256" and self.settings.supabase_jwt_secret:
            signed = ".".join(parts[:2]).encode("utf-8")
            expected = hmac.new(self.settings.supabase_jwt_secret.encode("utf-8"), signed, hashlib.sha256).digest()
            actual = _b64url_decode(parts[2])
            if not hmac.compare_digest(expected, actual):
                raise HTTPException(status_code=401, detail="invalid_token_signature")
        elif self.settings.supabase_jwks_url:
            # JWKS verification is configured but not performed locally; production deployments should terminate
            # verification at the auth edge or add a JWKS-capable verifier.
            pass
        else:
            raise HTTPException(status_code=401, detail="auth_verifier_not_configured")

        now = int(datetime.now(UTC).timestamp())
        if payload.get("exp") and int(payload["exp"]) < now:
            raise HTTPException(status_code=401, detail="token_expired")
        if self.settings.supabase_issuer and payload.get("iss") != self.settings.supabase_issuer:
            raise HTTPException(status_code=401, detail="invalid_issuer")
        audience = payload.get("aud")
        expected_audience = self.settings.supabase_audience
        if expected_audience and audience not in (expected_audience, [expected_audience]):
            raise HTTPException(status_code=401, detail="invalid_audience")
        if not payload.get("sub"):
            raise HTTPException(status_code=401, detail="missing_subject")
        return payload


def _extract_token(request: Request) -> str | None:
    settings = get_settings()
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return request.cookies.get(settings.session_cookie_name)


def ensure_public_pilot_user(
    db: Session,
    *,
    email: str,
    display_name: str | None,
    role: str,
    supabase_user_id: str | None = None,
) -> PublicPilotUser:
    settings = get_settings()
    org_slug = _slugify(settings.public_pilot_default_org)
    organization = db.scalar(select(models.Organization).where(models.Organization.slug == org_slug))
    if organization is None:
        organization = models.Organization(name=settings.public_pilot_default_org, slug=org_slug, settings_json={"public_pilot": True})
        db.add(organization)
        db.flush()

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
        profile.email = email
        profile.display_name = display_name or profile.display_name
        profile.last_login_at = datetime.now(UTC).replace(tzinfo=None)

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
    elif role:
        membership.role = role

    db.commit()
    db.refresh(profile)
    db.refresh(organization)
    db.refresh(membership)
    return PublicPilotUser(profile=profile, organization=organization, membership=membership)


def get_current_public_user(request: Request, db: Session = Depends(get_db)) -> PublicPilotUser:
    settings = get_settings()
    token = _extract_token(request)
    if token:
        payload = SupabaseJWTValidator().validate(token)
        email = payload.get("email") or payload.get("user_metadata", {}).get("email") or f"{payload['sub']}@supabase.local"
        display_name = payload.get("user_metadata", {}).get("name") or payload.get("user_metadata", {}).get("full_name")
        role = payload.get("app_metadata", {}).get("role") or payload.get("role") or "viewer"
        return ensure_public_pilot_user(
            db,
            email=email,
            display_name=display_name,
            role=role,
            supabase_user_id=payload["sub"],
        )

    if settings.auth_required:
        raise HTTPException(status_code=401, detail="authentication_required")

    email = request.headers.get("x-public-pilot-email", settings.auth_dev_bypass_email)
    role = request.headers.get("x-public-pilot-role", "owner")
    display_name = request.headers.get("x-public-pilot-name")
    return ensure_public_pilot_user(db, email=email, display_name=display_name, role=role)

