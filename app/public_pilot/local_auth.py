from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from app.config import get_settings


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
LOCAL_ISSUER = "contentengine-local"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def hash_local_password(password: str, *, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> str:
    if len(password) < 12:
        raise ValueError("Local auth password must contain at least 12 characters.")
    salt = salt or secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{PASSWORD_SCHEME}${iterations}${_b64url(salt)}${_b64url(digest)}"


def verify_local_password(password: str, encoded: str) -> bool:
    try:
        scheme, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        iterations = int(raw_iterations)
        salt = base64.urlsafe_b64decode(raw_salt + "=" * (-len(raw_salt) % 4))
        expected = base64.urlsafe_b64decode(raw_digest + "=" * (-len(raw_digest) % 4))
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def local_auth_configured() -> bool:
    settings = get_settings()
    return bool(settings.local_auth_email and settings.local_auth_password_hash and settings.local_session_secret)


def authenticate_local_user(email: str, password: str) -> str | None:
    settings = get_settings()
    if not local_auth_configured():
        return None
    supplied_email = email.strip().casefold()
    expected_email = str(settings.local_auth_email).strip().casefold()
    email_ok = hmac.compare_digest(supplied_email.encode("utf-8"), expected_email.encode("utf-8"))
    password_ok = verify_local_password(password, str(settings.local_auth_password_hash))
    if not email_ok or not password_ok:
        return None
    return issue_local_session(email=str(settings.local_auth_email), role="owner")


def issue_local_session(*, email: str, role: str) -> str:
    settings = get_settings()
    if not settings.local_session_secret:
        raise ValueError("QVF_LOCAL_SESSION_SECRET is not configured.")
    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT", "kid": "contentengine-local"}
    payload = {
        "sub": f"local:{email.strip().casefold()}",
        "email": email.strip().casefold(),
        "role": role,
        "auth_source": "local",
        "iss": LOCAL_ISSUER,
        "aud": settings.supabase_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.local_session_ttl_seconds)).timestamp()),
    }
    encoded_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(settings.local_session_secret.encode("utf-8"), signed, hashlib.sha256).digest()
    return f"{signed.decode('ascii')}.{_b64url(signature)}"
