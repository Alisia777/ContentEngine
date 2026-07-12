from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import Response

from app.config import Settings, get_settings


class SupabaseAuthError(RuntimeError):
    """A secret-free, user-safe failure from the Supabase Auth boundary."""

    def __init__(self, code: str, *, status_code: int = 401):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class SupabaseSessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class SupabaseAuthClient:
    """Small async client for the official GoTrue/Supabase Auth REST API."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.settings.supabase_url and self.settings.supabase_publishable_key)

    async def exchange_password(self, *, email: str, password: str) -> SupabaseSessionTokens:
        return await self._token_request(
            grant_type="password",
            payload={"email": email.strip(), "password": password},
            failure_code="invalid_credentials",
        )

    async def refresh_session(self, refresh_token: str) -> SupabaseSessionTokens:
        if not refresh_token.strip():
            raise SupabaseAuthError("invalid_refresh_token")
        return await self._token_request(
            grant_type="refresh_token",
            payload={"refresh_token": refresh_token},
            failure_code="invalid_refresh_token",
        )

    async def verify_otp(
        self,
        *,
        token_hash: str,
        verification_type: str,
    ) -> SupabaseSessionTokens:
        """Exchange one invite TokenHash for a browser session.

        The public server-rendered flow deliberately supports only invitations;
        signup, recovery, email-change, and magic-link actions require their own
        explicit UX and threat model.
        """

        if verification_type != "invite":
            raise SupabaseAuthError("invalid_invite_type", status_code=400)
        normalized_hash = str(token_hash or "").strip()
        if (
            not 8 <= len(normalized_hash) <= 2_048
            or any(ord(character) < 33 or ord(character) > 126 for character in normalized_hash)
        ):
            raise SupabaseAuthError("invalid_or_expired_invite")
        response = await self._request(
            "POST",
            "/auth/v1/verify",
            json={"token_hash": normalized_hash, "type": "invite"},
        )
        if response.status_code >= 400:
            self._raise_response_error(
                response,
                client_error="invalid_or_expired_invite",
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseAuthError("invalid_auth_response", status_code=503) from exc
        return self._parse_tokens(data)

    async def verify_invite(self, *, token_hash: str) -> SupabaseSessionTokens:
        return await self.verify_otp(
            token_hash=token_hash,
            verification_type="invite",
        )

    async def update_password(self, *, access_token: str, password: str) -> None:
        """Set the current Supabase user's password without exposing either secret."""

        if not isinstance(access_token, str) or access_token.count(".") != 2:
            raise SupabaseAuthError("invalid_session")
        if not isinstance(password, str) or not 12 <= len(password) <= 1_024:
            raise SupabaseAuthError("password_policy_violation", status_code=400)
        response = await self._request(
            "PUT",
            "/auth/v1/user",
            headers={"authorization": f"Bearer {access_token}"},
            json={"password": password},
        )
        if not 200 <= response.status_code < 300:
            if response.status_code in {401, 403}:
                raise SupabaseAuthError("invalid_session")
            self._raise_response_error(
                response,
                client_error="password_update_rejected",
                client_status_code=400,
            )

    async def revoke(self, access_token: str) -> None:
        """Revoke the current Supabase session; callers may treat failure as best-effort."""

        if not self.configured or not access_token.strip():
            return
        response = await self._request(
            "POST",
            "/auth/v1/logout",
            params={"scope": "local"},
            headers={"authorization": f"Bearer {access_token}"},
        )
        if response.status_code in {200, 204, 401, 403}:
            return
        if response.status_code == 429:
            raise SupabaseAuthError("auth_rate_limited", status_code=429)
        raise SupabaseAuthError("auth_unavailable", status_code=503)

    async def _token_request(
        self,
        *,
        grant_type: str,
        payload: dict[str, str],
        failure_code: str,
    ) -> SupabaseSessionTokens:
        response = await self._request(
            "POST",
            "/auth/v1/token",
            params={"grant_type": grant_type},
            json=payload,
        )
        if response.status_code >= 400:
            if response.status_code in {400, 401, 403, 422}:
                raise SupabaseAuthError(failure_code)
            if response.status_code == 429:
                raise SupabaseAuthError("auth_rate_limited", status_code=429)
            raise SupabaseAuthError("auth_unavailable", status_code=503)
        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseAuthError("invalid_auth_response", status_code=503) from exc
        return self._parse_tokens(data)

    @staticmethod
    def _raise_response_error(
        response: httpx.Response,
        *,
        client_error: str,
        client_status_code: int = 401,
    ) -> None:
        """Map only HTTP status, never a provider body that may contain secrets."""

        if response.status_code in {400, 401, 403, 422}:
            raise SupabaseAuthError(client_error, status_code=client_status_code)
        if response.status_code == 429:
            raise SupabaseAuthError("auth_rate_limited", status_code=429)
        raise SupabaseAuthError("auth_unavailable", status_code=503)

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self.configured:
            raise SupabaseAuthError("auth_not_configured", status_code=503)
        base_url = str(self.settings.supabase_url).rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise SupabaseAuthError("auth_endpoint_must_use_https", status_code=503)
        headers = {
            "apikey": str(self.settings.supabase_publishable_key),
            "accept": "application/json",
            "content-type": "application/json",
            **kwargs.pop("headers", {}),
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.supabase_auth_timeout_seconds,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                return await client.request(
                    method,
                    f"{base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SupabaseAuthError("auth_unavailable", status_code=503) from exc

    @staticmethod
    def _parse_tokens(data: Any) -> SupabaseSessionTokens:
        if not isinstance(data, dict):
            raise SupabaseAuthError("invalid_auth_response", status_code=503)
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        if not isinstance(access_token, str) or access_token.count(".") != 2:
            raise SupabaseAuthError("invalid_auth_response", status_code=503)
        if not isinstance(refresh_token, str) or len(refresh_token.strip()) < 12:
            raise SupabaseAuthError("invalid_auth_response", status_code=503)
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise SupabaseAuthError("invalid_auth_response", status_code=503)
        return SupabaseSessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=max(30, min(int(expires_in), 86_400)),
            token_type=str(data.get("token_type") or "bearer").lower(),
        )


def set_supabase_session_cookies(response: Response, tokens: SupabaseSessionTokens) -> None:
    settings = get_settings()
    common = {
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        settings.session_cookie_name,
        tokens.access_token,
        max_age=tokens.expires_in,
        **common,
    )
    response.set_cookie(
        settings.session_refresh_cookie_name,
        tokens.refresh_token,
        max_age=settings.session_refresh_cookie_max_age_seconds,
        **common,
    )


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    for name in {settings.session_cookie_name, settings.session_refresh_cookie_name}:
        response.delete_cookie(
            name,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite=settings.session_cookie_samesite,
        )
