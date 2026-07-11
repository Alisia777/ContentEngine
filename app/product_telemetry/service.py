from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models


UX_EVENT_NAMES = frozenset(
    {
        "session_started",
        "page_viewed",
        "navigation_clicked",
        "primary_action_clicked",
        "help_opened",
        "validation_failed",
    }
)

MILESTONE_EVENT_NAMES = frozenset(
    {
        "onboarding_started",
        "product_selected",
        "asset_gate_passed",
        "prompt_ready",
        "generation_requested",
        "generation_succeeded",
        "generation_failed",
        "human_review_completed",
        "video_approved",
        "video_rejected",
        "publishing_package_approved",
        "publication_completed",
        "first_metric_attributed",
        "first_order_attributed",
    }
)

ALLOWED_EVENT_NAMES = UX_EVENT_NAMES | MILESTONE_EVENT_NAMES
ALLOWED_SOURCES = frozenset({"web", "server"})
SERVER_ONLY_EVENT_NAMES = frozenset(
    {
        "asset_gate_passed",
        "prompt_ready",
        "generation_succeeded",
        "generation_failed",
        "publication_completed",
        "first_metric_attributed",
        "first_order_attributed",
    }
)

MAX_PROPERTIES_INPUT_BYTES = 16 * 1024
MAX_PROPERTIES_BYTES = 8 * 1024
MAX_PROPERTY_KEYS = 40
MAX_PROPERTY_LIST_ITEMS = 25
MAX_PROPERTY_DEPTH = 4
MAX_PROPERTY_KEY_LENGTH = 64
MAX_PROPERTY_STRING_LENGTH = 500

_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", flags=re.IGNORECASE)
_LONG_OPAQUE_VALUE = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{80,}(?![A-Za-z0-9_-])")
_SENSITIVE_KEY_TOKENS = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "token",
        "jwt",
        "authorization",
        "cookie",
        "credential",
        "email",
        "phone",
        "telephone",
        "address",
    }
)
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "access_key",
        "private_key",
        "signing_key",
        "signed_url",
        "first_name",
        "last_name",
        "full_name",
        "display_name",
        "user_name",
    }
)


class TelemetryValidationError(ValueError):
    pass


class TelemetryIdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class EventRecordResult:
    event: models.FactoryEvent
    created: bool


def _json_size(value: Any) -> int:
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise TelemetryValidationError("properties must contain JSON-compatible values") from exc
    return len(encoded.encode("utf-8"))


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    if normalized in _SENSITIVE_KEYS:
        return True
    return bool(set(normalized.split("_")).intersection(_SENSITIVE_KEY_TOKENS))


def _sanitize_string(value: str) -> str:
    sanitized = _BEARER.sub("Bearer [redacted]", value)
    sanitized = _EMAIL.sub("[redacted-email]", sanitized)
    sanitized = _LONG_OPAQUE_VALUE.sub("[redacted-token]", sanitized)
    if sanitized.startswith(("http://", "https://")):
        try:
            parsed = urlsplit(sanitized)
            if parsed.query or parsed.fragment:
                sanitized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        except ValueError:
            sanitized = "[invalid-url]"
    if len(sanitized) > MAX_PROPERTY_STRING_LENGTH:
        sanitized = sanitized[: MAX_PROPERTY_STRING_LENGTH - 1] + "…"
    return sanitized


def _sanitize_value(value: Any, *, depth: int, key_counter: list[int]) -> Any:
    if depth > MAX_PROPERTY_DEPTH:
        raise TelemetryValidationError(f"properties nesting exceeds {MAX_PROPERTY_DEPTH} levels")
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TelemetryValidationError("properties cannot contain non-finite numbers")
        return value
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise TelemetryValidationError("property keys must be strings")
            key = raw_key.strip()
            if not key:
                raise TelemetryValidationError("property keys cannot be empty")
            if len(key) > MAX_PROPERTY_KEY_LENGTH:
                raise TelemetryValidationError(
                    f"property keys cannot exceed {MAX_PROPERTY_KEY_LENGTH} characters"
                )
            key_counter[0] += 1
            if key_counter[0] > MAX_PROPERTY_KEYS:
                raise TelemetryValidationError(f"properties cannot contain more than {MAX_PROPERTY_KEYS} keys")
            if key in sanitized:
                raise TelemetryValidationError("properties contain duplicate keys after normalization")
            sanitized[key] = (
                "[redacted]"
                if _is_sensitive_key(key)
                else _sanitize_value(child, depth=depth + 1, key_counter=key_counter)
            )
        return sanitized
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_PROPERTY_LIST_ITEMS:
            raise TelemetryValidationError(
                f"property lists cannot contain more than {MAX_PROPERTY_LIST_ITEMS} items"
            )
        return [_sanitize_value(item, depth=depth + 1, key_counter=key_counter) for item in value]
    raise TelemetryValidationError("properties must contain JSON-compatible values")


def sanitize_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    raw = {} if properties is None else properties
    if not isinstance(raw, dict):
        raise TelemetryValidationError("properties must be an object")
    if _json_size(raw) > MAX_PROPERTIES_INPUT_BYTES:
        raise TelemetryValidationError(
            f"properties payload cannot exceed {MAX_PROPERTIES_INPUT_BYTES} bytes"
        )
    sanitized = _sanitize_value(raw, depth=0, key_counter=[0])
    if _json_size(sanitized) > MAX_PROPERTIES_BYTES:
        raise TelemetryValidationError(f"sanitized properties cannot exceed {MAX_PROPERTIES_BYTES} bytes")
    return sanitized


def _clean_text(value: str | None, *, field: str, max_length: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise TelemetryValidationError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise TelemetryValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise TelemetryValidationError(f"{field} is required")
        return None
    if len(cleaned) > max_length:
        raise TelemetryValidationError(f"{field} cannot exceed {max_length} characters")
    return cleaned


def _clean_correlation_id(value: str | None, *, field: str, max_length: int) -> str | None:
    cleaned = _clean_text(value, field=field, max_length=max_length)
    if cleaned is not None and not _SAFE_CORRELATION_ID.fullmatch(cleaned):
        raise TelemetryValidationError(f"{field} contains unsupported characters")
    return cleaned


def _positive_id(value: int | None, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TelemetryValidationError(f"{field} must be a positive integer")
    return value


def _utc_naive(value: datetime | None, *, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class ProductTelemetryService:
    def __init__(self, db: Session):
        self.db = db

    def record_event(
        self,
        *,
        event_name: str,
        organization_id: int,
        user_profile_id: int,
        role: str,
        idempotency_key: str,
        event_version: int = 1,
        occurred_at: datetime | None = None,
        session_id: str | None = None,
        factory_run_id: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        product_id: int | None = None,
        sku: str | None = None,
        campaign_id: int | None = None,
        video_job_id: int | None = None,
        publishing_task_id: int | None = None,
        source: str = "server",
        properties: dict[str, Any] | None = None,
    ) -> EventRecordResult:
        cleaned_event_name = _clean_text(event_name, field="event_name", max_length=120, required=True)
        if cleaned_event_name not in ALLOWED_EVENT_NAMES:
            raise TelemetryValidationError(f"event_name is not allowed: {cleaned_event_name}")
        if isinstance(event_version, bool) or event_version != 1:
            raise TelemetryValidationError("only event_version=1 is supported")
        cleaned_source = _clean_text(source, field="source", max_length=80, required=True)
        if cleaned_source not in ALLOWED_SOURCES:
            raise TelemetryValidationError("source must be web or server")
        if cleaned_source == "web" and cleaned_event_name in SERVER_ONLY_EVENT_NAMES:
            raise TelemetryValidationError(f"{cleaned_event_name} is a server-only event")

        organization_id = _positive_id(organization_id, field="organization_id")
        user_profile_id = _positive_id(user_profile_id, field="user_profile_id")
        if organization_id is None or user_profile_id is None:
            raise TelemetryValidationError("organization_id and user_profile_id are required")
        cleaned_role = _clean_text(role, field="role", max_length=80, required=True)
        cleaned_key = _clean_correlation_id(idempotency_key, field="idempotency_key", max_length=160)
        if cleaned_key is None:
            raise TelemetryValidationError("idempotency_key is required")

        existing = self.db.scalar(select(models.FactoryEvent).where(models.FactoryEvent.idempotency_key == cleaned_key))
        if existing is not None:
            return self._duplicate_result(
                existing,
                event_name=cleaned_event_name,
                event_version=event_version,
                organization_id=organization_id,
                user_profile_id=user_profile_id,
            )

        received_at = datetime.now(UTC).replace(tzinfo=None)
        event = models.FactoryEvent(
            event_name=cleaned_event_name,
            event_version=event_version,
            occurred_at=_utc_naive(occurred_at, fallback=received_at),
            received_at=received_at,
            organization_id=organization_id,
            user_profile_id=user_profile_id,
            session_id=_clean_correlation_id(session_id, field="session_id", max_length=128),
            role=cleaned_role,
            factory_run_id=_clean_correlation_id(factory_run_id, field="factory_run_id", max_length=160),
            entity_type=_clean_text(entity_type, field="entity_type", max_length=120),
            entity_id=_clean_text(entity_id, field="entity_id", max_length=160),
            product_id=_positive_id(product_id, field="product_id"),
            sku=_clean_text(sku, field="sku", max_length=120),
            campaign_id=_positive_id(campaign_id, field="campaign_id"),
            video_job_id=_positive_id(video_job_id, field="video_job_id"),
            publishing_task_id=_positive_id(publishing_task_id, field="publishing_task_id"),
            source=cleaned_source,
            idempotency_key=cleaned_key,
            properties_json=sanitize_properties(properties),
        )
        self.db.add(event)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.scalar(
                select(models.FactoryEvent).where(models.FactoryEvent.idempotency_key == cleaned_key)
            )
            if existing is None:
                raise
            return self._duplicate_result(
                existing,
                event_name=cleaned_event_name,
                event_version=event_version,
                organization_id=organization_id,
                user_profile_id=user_profile_id,
            )
        self.db.refresh(event)
        return EventRecordResult(event=event, created=True)

    @staticmethod
    def _duplicate_result(
        existing: models.FactoryEvent,
        *,
        event_name: str,
        event_version: int,
        organization_id: int,
        user_profile_id: int,
    ) -> EventRecordResult:
        same_request_identity = (
            existing.event_name == event_name
            and existing.event_version == event_version
            and existing.organization_id == organization_id
            and existing.user_profile_id == user_profile_id
        )
        if not same_request_identity:
            raise TelemetryIdempotencyConflict("idempotency_key was already used by another event")
        return EventRecordResult(event=existing, created=False)
