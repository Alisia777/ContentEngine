from __future__ import annotations

import os
import re
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit

from app import models
from app.destination_connectors.catalog import OFFICIAL_CONNECTION_TYPES, connector_definition
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.types import CredentialCheckResult


_REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:-]{0,119}$")
_SENSITIVE_KEYS = ("token", "secret", "password", "authorization", "api_key", "apikey", "credential")
_FORBIDDEN_SETTING_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "cookies",
    "credential",
    "credential_ref",
    "mock_metrics",
    "password",
    "refresh_token",
    "secret",
    "session",
    "token",
}
_FORBIDDEN_KEY_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "password",
    "refresh_token",
    "session",
)
_SENSITIVE_URL_QUERY_MARKERS = (
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "credential",
    "expires",
    "key",
    "secret",
    "sig",
    "signature",
    "token",
    "x_amz_",
    "x_goog_",
)


def _unsafe_setting_key(normalized: str) -> bool:
    return (
        normalized in _FORBIDDEN_SETTING_KEYS
        or any(marker in normalized for marker in _FORBIDDEN_KEY_MARKERS)
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
    )


def _contains_sensitive_url_query(value: str) -> bool:
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return False
        for raw_key, _raw_value in parse_qsl(parts.query, keep_blank_values=True):
            key = raw_key.strip().lower().replace("-", "_")
            if any(marker in key for marker in _SENSITIVE_URL_QUERY_MARKERS):
                return True
    except ValueError:
        return False
    return False


class CredentialResolver(Protocol):
    """Resolve a logical secret reference without exposing it to persistence/UI."""

    def resolve(self, credential_ref: str) -> str | None: ...


class EnvironmentCredentialResolver:
    """Resolve ``NAME`` or ``env:NAME`` from the process environment."""

    def resolve(self, credential_ref: str) -> str | None:
        reference = validate_credential_ref(credential_ref)
        if not reference:
            return None
        environment_name = reference[4:] if reference.startswith("env:") else reference
        if not environment_name:
            raise DestinationConnectorDataError("credential_ref environment name is required.")
        value = os.getenv(environment_name)
        return value if value and value.strip() else None


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
        if lowered.endswith("credential_configured") and isinstance(value, bool):
            return value
        if any(marker in lowered for marker in _SENSITIVE_KEYS):
            return "[redacted]" if value else None
        if isinstance(value, str) and _contains_sensitive_url_query(value):
            return "[redacted_url]"
        if isinstance(value, dict):
            return {nested_key: sanitize_value(nested_key, nested_value) for nested_key, nested_value in value.items()}
        if isinstance(value, list):
            return [sanitize_value(key, item) for item in value]
        return value

    return {key: sanitize_value(key, value) for key, value in (payload or {}).items()}


def validate_non_secret_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Reject secrets and test-only metric payloads before they can reach the DB."""

    if settings is None:
        return {}
    if not isinstance(settings, dict):
        raise DestinationConnectorDataError("settings_json must be an object.")

    def validate_value(value: Any, *, path: str) -> Any:
        if isinstance(value, dict):
            clean: dict[str, Any] = {}
            for raw_key, nested in value.items():
                key = str(raw_key)
                normalized = key.strip().lower().replace("-", "_")
                if _unsafe_setting_key(normalized):
                    raise DestinationConnectorDataError(
                        "Raw credentials and mock_metrics must not be stored in destination settings."
                    )
                clean[key] = validate_value(nested, path=f"{path}.{key}")
            return clean
        if isinstance(value, list):
            return [validate_value(item, path=path) for item in value]
        if isinstance(value, str) and _contains_sensitive_url_query(value):
            raise DestinationConnectorDataError(
                "Signed URLs and credential-bearing URLs must not be stored in destination settings."
            )
        return value

    return validate_value(settings, path="settings_json")


def public_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Redact unsafe keys in pre-hardening rows instead of reflecting them."""

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for raw_key, nested in value.items():
                key = str(raw_key)
                normalized = key.strip().lower().replace("-", "_")
                if _unsafe_setting_key(normalized):
                    continue
                result[key] = clean(nested)
            return result
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, str) and _contains_sensitive_url_query(value):
            return "[redacted_url]"
        return value

    return clean(settings or {})


class CredentialStatusService:
    credential_types = {"telegram_bot", *OFFICIAL_CONNECTION_TYPES}

    def __init__(self, resolver: CredentialResolver | None = None):
        self.resolver = resolver or EnvironmentCredentialResolver()

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        if connection.connection_type in {"manual", "csv"}:
            return CredentialCheckResult(
                status="connected",
                auth_status="manual_only",
                credential_required=False,
                credential_configured=False,
                message="Use the explicit manual or CSV import flow.",
            )

        if connection.connection_type in {"instagram_stub", "tiktok_stub", "telegram_bot"}:
            return CredentialCheckResult(
                status="blocked",
                auth_status="official_adapter_unavailable",
                credential_required=connection.connection_type == "telegram_bot",
                credential_configured=False,
                message="Official metrics adapter is unavailable; use manual or CSV import.",
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
        definition = connector_definition(connection.connection_type)
        if definition is None:
            return CredentialCheckResult(
                status="blocked",
                auth_status="official_adapter_unavailable",
                credential_required=credential_required,
                credential_configured=credential_configured,
                message="Official metrics adapter is unavailable.",
            )
        if connection.status == "connected" and connection.auth_status == "oauth_verified":
            return CredentialCheckResult(
                status="connected",
                auth_status="oauth_verified",
                credential_required=True,
                credential_configured=True,
                message=(
                    f"{definition.display_name} OAuth was verified by a successful official API request."
                ),
            )
        return CredentialCheckResult(
            status="needs_verification",
            auth_status="credential_reference_configured",
            credential_required=True,
            credential_configured=True,
            message="Credential reference is configured but has not been verified by the official API.",
        )

    def is_configured(self, credential_ref: str | None) -> bool:
        if not credential_ref:
            return False
        return bool(self.resolver.resolve(credential_ref))
