from __future__ import annotations

import os
from typing import Mapping
from urllib.parse import urlsplit

import httpx

from app.config import get_settings
from app.supabase_keys import resolve_supabase_server_key, server_api_key_headers
from app.team.errors import SupabaseAdminError, TeamValidationError
from app.team.types import SupabaseAdminUser


class SupabaseAuthAdminClient:
    """Minimal server-only Supabase Auth Admin REST client."""

    def __init__(
        self,
        *,
        project_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        parsed = urlsplit(project_url.rstrip("/"))
        if parsed.scheme != "https" or not parsed.netloc:
            raise TeamValidationError("Supabase project URL must use HTTPS.")
        try:
            self._server_headers = server_api_key_headers(secret_key)
        except ValueError as exc:
            raise TeamValidationError("Supabase Auth Admin secret is not configured.") from exc
        self.project_url = project_url.rstrip("/")
        self._secret_key = secret_key
        self._owns_client = client is None
        self.client = client or httpx.Client()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def find_user_by_email(self, email: str) -> SupabaseAdminUser | None:
        response = self._request(
            "GET",
            "/auth/v1/admin/users",
            params={"page": "1", "per_page": "1000"},
        )
        payload = self._json(response)
        users = payload.get("users") if isinstance(payload, dict) else None
        if not isinstance(users, list):
            raise SupabaseAdminError("Supabase user directory returned an invalid response.")
        expected = email.casefold()
        for raw_user in users:
            if isinstance(raw_user, dict) and str(raw_user.get("email") or "").casefold() == expected:
                return self._user(raw_user)
        return None

    def invite_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
        redirect_to: str | None = None,
    ) -> SupabaseAdminUser:
        body: dict[str, object] = {"email": email}
        if display_name:
            body["data"] = {"display_name": display_name}
        if redirect_to:
            body["redirect_to"] = redirect_to
        response = self._request("POST", "/auth/v1/invite", json=body)
        payload = self._json(response)
        raw_user = payload.get("user") if isinstance(payload.get("user"), dict) else payload
        return self._user(raw_user)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        url = f"{self.project_url}{path}"
        headers = {**self._server_headers, "content-type": "application/json"}
        try:
            response = self.client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Never include the response body: auth services can echo email,
            # redirect parameters, or diagnostic credentials.
            raise SupabaseAdminError(
                f"Supabase Auth Admin returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise SupabaseAdminError("Supabase Auth Admin is temporarily unavailable.") from exc
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        try:
            payload = response.json()
        except ValueError as exc:
            raise SupabaseAdminError("Supabase Auth Admin returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise SupabaseAdminError("Supabase Auth Admin returned an invalid response.")
        return payload

    @staticmethod
    def _user(payload: dict) -> SupabaseAdminUser:
        user_id = str(payload.get("id") or "").strip()
        email = str(payload.get("email") or "").strip().lower()
        metadata = payload.get("user_metadata") if isinstance(payload.get("user_metadata"), dict) else {}
        display_name = str(metadata.get("display_name") or "").strip() or None
        if not user_id or not email:
            raise SupabaseAdminError("Supabase Auth Admin response omitted user identity.")
        return SupabaseAdminUser(user_id=user_id, email=email, display_name=display_name)


def build_supabase_admin_client(
    *,
    settings=None,
    environ: Mapping[str, str] | None = None,
) -> SupabaseAuthAdminClient:
    settings = settings or get_settings()
    env = dict(os.environ if environ is None else environ)
    project_url = (
        env.get("SUPABASE_URL")
        or getattr(settings, "supabase_url", None)
        or ""
    )
    try:
        secret_key = resolve_supabase_server_key(settings=settings, environ=env)
    except ValueError as exc:
        raise SupabaseAdminError("Supabase Auth Admin configuration is invalid.") from exc
    if not project_url:
        raise SupabaseAdminError("Supabase Auth Admin is not configured.")
    try:
        return SupabaseAuthAdminClient(project_url=project_url, secret_key=secret_key)
    except TeamValidationError as exc:
        raise SupabaseAdminError("Supabase Auth Admin configuration is invalid.") from exc
