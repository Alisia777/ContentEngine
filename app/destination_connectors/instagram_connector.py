from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

import httpx

from app import models
from app.destination_connectors.credential_status import (
    CredentialResolver,
    CredentialStatusService,
    EnvironmentCredentialResolver,
    validate_non_secret_settings,
)
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.owned_targets import (
    non_negative_integer,
    positive_task_id,
    require_owned_published_target,
    safe_public_url,
)
from app.destination_connectors.types import CredentialCheckResult


INSTAGRAM_GRAPH_BASE_URL = "https://graph.instagram.com"
DEFAULT_INSTAGRAM_API_VERSION = "v25.0"
INSTAGRAM_REQUIRED_PERMISSIONS = (
    "instagram_business_basic",
    "instagram_business_manage_insights",
)
INSTAGRAM_MEDIA_METRICS = (
    "views",
    "plays",
    "reach",
    "likes",
    "comments",
    "shares",
    "saved",
)
_MEDIA_ID_RE = re.compile(r"^[0-9]{6,40}$")
_API_VERSION_RE = re.compile(r"^v[0-9]{1,2}\.[0-9]{1,2}$")


class InstagramInsightsTransport(Protocol):
    def query_media_insights(
        self,
        *,
        access_token: str,
        api_version: str,
        media_id: str,
        metrics: tuple[str, ...],
    ) -> dict[str, Any]: ...


class HttpxInstagramInsightsTransport:
    """Instagram Login transport; credentials are sent only as a bearer header."""

    def __init__(self, *, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds

    def query_media_insights(
        self,
        *,
        access_token: str,
        api_version: str,
        media_id: str,
        metrics: tuple[str, ...],
    ) -> dict[str, Any]:
        url = (
            f"{INSTAGRAM_GRAPH_BASE_URL}/{quote(api_version, safe='')}/"
            f"{quote(media_id, safe='')}/insights"
        )
        transport_failed = False
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = client.get(
                    url,
                    params={"metric": ",".join(metrics)},
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError:
            transport_failed = True
        if transport_failed:
            # Keep untrusted upstream text out of public and chained errors.
            raise DestinationConnectorDataError("instagram_official_api_transport_failed")
        if response.status_code in {401, 403}:
            raise DestinationConnectorDataError("instagram_official_api_authorization_failed")
        if response.status_code >= 400:
            raise DestinationConnectorDataError(
                f"instagram_official_api_request_failed_status_{response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DestinationConnectorDataError("instagram_official_api_invalid_json") from exc
        if not isinstance(payload, dict):
            raise DestinationConnectorDataError("instagram_official_api_invalid_response")
        return payload


@dataclass(frozen=True)
class InstagramMetricSnapshot:
    media_id: str
    final_url: str
    publishing_task_id: int
    metrics: dict[str, int | float]

    @property
    def external_post_id(self) -> str:
        return self.media_id


@dataclass(frozen=True)
class _InstagramTarget:
    media_id: str
    final_url: str
    publishing_task_id: int


class InstagramInsightsConnector:
    """Official Insights adapter for owned professional-account media."""

    def __init__(
        self,
        *,
        transport: InstagramInsightsTransport | None = None,
        credential_resolver: CredentialResolver | None = None,
    ):
        self.transport = transport or HttpxInstagramInsightsTransport()
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.credentials = CredentialStatusService(self.credential_resolver)

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        return self.credentials.check(connection)

    def validate_configuration(
        self,
        connection: models.DestinationConnection,
        *,
        organization_id: int,
    ) -> list[_InstagramTarget]:
        if connection.connection_type != "instagram_oauth":
            raise DestinationConnectorDataError("instagram_oauth_connection_required")
        if not connection.credential_ref:
            raise DestinationConnectorDataError("instagram_credential_reference_missing")
        if not self._resolve_credential(connection.credential_ref):
            raise DestinationConnectorDataError("instagram_credential_reference_unresolved")
        settings = validate_non_secret_settings(connection.settings_json or {})
        self._api_version(settings)
        return self._media_targets(
            connection,
            settings=settings,
            organization_id=organization_id,
        )

    def collect_metrics(
        self,
        connection: models.DestinationConnection,
        *,
        organization_id: int,
        period_start: date,
        period_end: date,
    ) -> list[InstagramMetricSnapshot]:
        if period_end < period_start:
            raise DestinationConnectorDataError("period_end_must_not_precede_period_start")
        settings = validate_non_secret_settings(connection.settings_json or {})
        targets = self.validate_configuration(connection, organization_id=organization_id)
        api_version = self._api_version(settings)
        access_token = self._resolve_credential(connection.credential_ref or "")
        if not access_token:
            raise DestinationConnectorDataError("instagram_credential_reference_unresolved")

        snapshots: list[InstagramMetricSnapshot] = []
        for target in targets:
            payload = self.transport.query_media_insights(
                access_token=access_token,
                api_version=api_version,
                media_id=target.media_id,
                metrics=INSTAGRAM_MEDIA_METRICS,
            )
            normalized = self._normalize_response(payload)
            if not normalized:
                continue
            snapshots.append(
                InstagramMetricSnapshot(
                    media_id=target.media_id,
                    final_url=target.final_url,
                    publishing_task_id=target.publishing_task_id,
                    metrics=normalized,
                )
            )
        return snapshots

    def _resolve_credential(self, credential_ref: str) -> str | None:
        try:
            return self.credential_resolver.resolve(credential_ref)
        except Exception as exc:
            raise DestinationConnectorDataError("instagram_credential_resolution_failed") from exc

    @staticmethod
    def _api_version(settings: dict[str, Any]) -> str:
        value = str(settings.get("api_version") or DEFAULT_INSTAGRAM_API_VERSION).strip()
        if not _API_VERSION_RE.fullmatch(value):
            raise DestinationConnectorDataError("instagram_api_version_is_invalid")
        return value

    @classmethod
    def _media_targets(
        cls,
        connection: models.DestinationConnection,
        *,
        settings: dict[str, Any],
        organization_id: int,
    ) -> list[_InstagramTarget]:
        if set(settings) - {"api_version", "media_map"}:
            raise DestinationConnectorDataError("instagram_settings_fields_invalid")
        raw_map = settings.get("media_map")
        if not isinstance(raw_map, dict) or not raw_map:
            raise DestinationConnectorDataError("instagram_media_map_required")
        if len(raw_map) > 50:
            raise DestinationConnectorDataError("instagram_media_map_limit_exceeded")
        targets: list[_InstagramTarget] = []
        for raw_id, raw_mapping in raw_map.items():
            media_id = str(raw_id or "").strip()
            if not _MEDIA_ID_RE.fullmatch(media_id):
                raise DestinationConnectorDataError("instagram_media_id_is_invalid")
            if not isinstance(raw_mapping, dict):
                raise DestinationConnectorDataError("instagram_media_map_entry_invalid")
            if set(raw_mapping) != {"final_url", "publishing_task_id"}:
                raise DestinationConnectorDataError("instagram_media_map_entry_fields_invalid")
            final_url = str(raw_mapping.get("final_url") or "").strip()
            task_id = positive_task_id(
                raw_mapping.get("publishing_task_id"),
                error_code="instagram_publishing_task_id_required",
            )
            cls._validate_instagram_url(final_url)
            require_owned_published_target(
                connection,
                organization_id=organization_id,
                publishing_task_id=task_id,
                final_url=final_url,
                expected_platform="instagram",
                error_prefix="instagram",
            )
            targets.append(
                _InstagramTarget(
                    media_id=media_id,
                    final_url=final_url,
                    publishing_task_id=task_id,
                )
            )
        return targets

    @staticmethod
    def _validate_instagram_url(value: str) -> None:
        canonical = safe_public_url(value, error_code="instagram_final_url_is_invalid")
        parts = urlsplit(canonical)
        if (parts.hostname or "").lower() not in {"instagram.com", "www.instagram.com"}:
            raise DestinationConnectorDataError("instagram_final_url_is_invalid")
        if not re.fullmatch(r"/(p|reel|tv)/[^/]+", parts.path.rstrip("/")):
            raise DestinationConnectorDataError("instagram_final_url_is_invalid")

    @classmethod
    def _normalize_response(cls, payload: dict[str, Any]) -> dict[str, int | float]:
        if "error" in payload:
            raise DestinationConnectorDataError("instagram_official_api_rejected_request")
        raw_data = payload.get("data")
        if not isinstance(raw_data, list):
            raise DestinationConnectorDataError("instagram_official_api_data_invalid")
        requested = set(INSTAGRAM_MEDIA_METRICS)
        raw_metrics: dict[str, int] = {}
        for item in raw_data:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise DestinationConnectorDataError("instagram_official_api_metric_shape_invalid")
            name = item["name"].strip()
            if name not in requested or name in raw_metrics:
                raise DestinationConnectorDataError(
                    "instagram_official_api_returned_unrequested_or_duplicate_metric"
                )
            raw_metrics[name] = non_negative_integer(
                cls._metric_value(item),
                error_code=f"instagram_metric_{name}_is_invalid",
            )

        normalized: dict[str, int | float] = {}
        if "views" in raw_metrics:
            normalized["views"] = raw_metrics["views"]
        elif "plays" in raw_metrics:
            normalized["views"] = raw_metrics["plays"]
        for source, target in (
            ("reach", "reach"),
            ("likes", "likes"),
            ("comments", "comments"),
            ("shares", "shares"),
            ("saved", "saves"),
        ):
            if source in raw_metrics:
                normalized[target] = raw_metrics[source]
        return normalized

    @staticmethod
    def _metric_value(item: dict[str, Any]) -> object:
        if "value" in item:
            return item["value"]
        total = item.get("total_value")
        if isinstance(total, dict) and "value" in total:
            return total["value"]
        values = item.get("values")
        if (
            isinstance(values, list)
            and len(values) == 1
            and isinstance(values[0], dict)
            and "value" in values[0]
        ):
            return values[0]["value"]
        raise DestinationConnectorDataError("instagram_official_api_metric_value_missing")
