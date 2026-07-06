from __future__ import annotations

import os
import re
from typing import Any

from app import models
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.types import CredentialCheckResult


_REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:-]{0,119}$")
_SENSITIVE_KEYS = ("token", "secret", "password", "authorization", "api_key", "apikey")


def validate_credential_ref(credential_ref: str | None) -> str | None:
    if credential_ref is None:
        return None
    value = credential_ref.strip()
    if not value:
        return None
    if value.startswith(("key_", "sk-")) or len(value) > 120 or not _REF_RE.match(value):
        raise DestinationConnectorDataError("credential_ref must be a secret reference name, not a raw credential.")
    return value


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    def sanitize_value(key: str, value: Any) -> Any:
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEYS):
            return "[redacted]" if value else None
        if isinstance(value, dict):
            return {nested_key: sanitize_value(nested_key, nested_value) for nested_key, nested_value in value.items()}
        if isinstance(value, list):
            return [sanitize_value(key, item) for item in value]
        return value

    return {key: sanitize_value(key, value) for key, value in (payload or {}).items()}


class CredentialStatusService:
    credential_types = {"telegram_bot", "youtube_oauth"}

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        if connection.connection_type in {"manual", "csv", "instagram_stub", "tiktok_stub"}:
            auth_status = "needs_app_review" if connection.connection_type.endswith("_stub") else "manual_only"
            return CredentialCheckResult(
                status="connected",
                auth_status=auth_status,
                credential_required=False,
                credential_configured=False,
                message="Manual or CSV metrics are available.",
            )

        credential_required = connection.connection_type in self.credential_types
        credential_configured = self.is_configured(connection.credential_ref)
        if not connection.credential_ref:
            return CredentialCheckResult(
                status="needs_auth",
                auth_status="needs_auth",
                credential_required=credential_required,
                credential_configured=False,
                message="Credential reference is required.",
            )
        if not credential_configured:
            return CredentialCheckResult(
                status="needs_auth",
                auth_status="needs_auth",
                credential_required=credential_required,
                credential_configured=False,
                message="Credential reference is set but not configured in the environment.",
            )
        if connection.connection_type == "telegram_bot":
            return CredentialCheckResult(
                status="connected",
                auth_status="bot_ready",
                credential_required=True,
                credential_configured=True,
                message="Telegram bot credential is configured.",
            )
        return CredentialCheckResult(
            status="connected",
            auth_status="oauth_ready",
            credential_required=True,
            credential_configured=True,
            message="OAuth credential reference is configured.",
        )

    @staticmethod
    def is_configured(credential_ref: str | None) -> bool:
        return bool(credential_ref and os.getenv(credential_ref))
