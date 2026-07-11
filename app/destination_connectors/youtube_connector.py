from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit

import httpx

from app import models
from app.destination_connectors.credential_status import (
    CredentialResolver,
    CredentialStatusService,
    EnvironmentCredentialResolver,
    validate_non_secret_settings,
)
from app.destination_connectors.errors import DestinationConnectorDataError
from app.destination_connectors.types import CredentialCheckResult


YOUTUBE_ANALYTICS_REPORTS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
YOUTUBE_METRICS = (
    "views",
    "likes",
    "comments",
    "shares",
    "estimatedMinutesWatched",
    "averageViewPercentage",
)
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_CHANNEL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "key",
    "secret",
    "signature",
    "token",
}


class YouTubeAnalyticsTransport(Protocol):
    """Small injectable boundary around the official reports.query endpoint."""

    def query_report(self, *, access_token: str, params: dict[str, str | int]) -> dict[str, Any]: ...


class HttpxYouTubeAnalyticsTransport:
    """Production transport. The OAuth token is sent only in the Authorization header."""

    def __init__(self, *, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds

    def query_report(self, *, access_token: str, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = client.get(
                    YOUTUBE_ANALYTICS_REPORTS_URL,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise DestinationConnectorDataError("youtube_official_api_transport_failed") from exc

        if response.status_code in {401, 403}:
            raise DestinationConnectorDataError("youtube_official_api_authorization_failed")
        if response.status_code >= 400:
            raise DestinationConnectorDataError(
                f"youtube_official_api_request_failed_status_{response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DestinationConnectorDataError("youtube_official_api_invalid_json") from exc
        if not isinstance(payload, dict):
            raise DestinationConnectorDataError("youtube_official_api_invalid_response")
        return payload


@dataclass(frozen=True)
class YouTubeMetricSnapshot:
    video_id: str
    final_url: str
    publishing_task_id: int | None
    metrics: dict[str, int | float]

    @property
    def external_post_id(self) -> str:
        return self.video_id


@dataclass(frozen=True)
class _VideoTarget:
    video_id: str
    final_url: str
    publishing_task_id: int | None


class YouTubeAnalyticsConnector:
    """Official YouTube Analytics v2 adapter with no mock/default data path."""

    def __init__(
        self,
        *,
        transport: YouTubeAnalyticsTransport | None = None,
        credential_resolver: CredentialResolver | None = None,
    ):
        self.transport = transport or HttpxYouTubeAnalyticsTransport()
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.credentials = CredentialStatusService(self.credential_resolver)

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        return self.credentials.check(connection)

    def validate_configuration(
        self,
        connection: models.DestinationConnection,
        *,
        organization_id: int,
    ) -> list[_VideoTarget]:
        self._require_owned_youtube_connection(connection, organization_id=organization_id)
        if connection.connection_type != "youtube_oauth":
            raise DestinationConnectorDataError("youtube_oauth_connection_required")
        if not connection.credential_ref:
            raise DestinationConnectorDataError("youtube_credential_reference_missing")
        if not self._resolve_credential(connection.credential_ref):
            raise DestinationConnectorDataError("youtube_credential_reference_unresolved")
        settings = validate_non_secret_settings(connection.settings_json or {})
        return self._video_targets(settings)

    def collect_metrics(
        self,
        connection: models.DestinationConnection,
        *,
        organization_id: int,
        period_start: date,
        period_end: date,
    ) -> list[YouTubeMetricSnapshot]:
        if period_end < period_start:
            raise DestinationConnectorDataError("period_end_must_not_precede_period_start")
        targets = self.validate_configuration(connection, organization_id=organization_id)
        settings = validate_non_secret_settings(connection.settings_json or {})
        channel_id = str(settings.get("channel_id") or "MINE").strip()
        if channel_id != "MINE" and not _CHANNEL_ID_RE.fullmatch(channel_id):
            raise DestinationConnectorDataError("youtube_channel_id_is_invalid")

        access_token = self._resolve_credential(connection.credential_ref or "")
        if not access_token:
            raise DestinationConnectorDataError("youtube_credential_reference_unresolved")
        params: dict[str, str | int] = {
            "ids": "channel==MINE" if channel_id == "MINE" else f"channel=={channel_id}",
            "startDate": period_start.isoformat(),
            "endDate": period_end.isoformat(),
            "metrics": ",".join(YOUTUBE_METRICS),
            "dimensions": "video",
            "filters": "video==" + ",".join(target.video_id for target in targets),
            "maxResults": len(targets),
        }
        payload = self.transport.query_report(access_token=access_token, params=params)
        return self._normalize_response(payload, targets=targets)

    def _resolve_credential(self, credential_ref: str) -> str | None:
        try:
            return self.credential_resolver.resolve(credential_ref)
        except Exception as exc:
            raise DestinationConnectorDataError("youtube_credential_resolution_failed") from exc

    @classmethod
    def _normalize_response(
        cls,
        payload: dict[str, Any],
        *,
        targets: list[_VideoTarget],
    ) -> list[YouTubeMetricSnapshot]:
        headers = payload.get("columnHeaders")
        rows = payload.get("rows", [])
        if not isinstance(headers, list) or not headers:
            raise DestinationConnectorDataError("youtube_official_api_column_headers_missing")
        if not isinstance(rows, list):
            raise DestinationConnectorDataError("youtube_official_api_rows_invalid")

        names: list[str] = []
        for header in headers:
            if not isinstance(header, dict) or not isinstance(header.get("name"), str):
                raise DestinationConnectorDataError("youtube_official_api_column_headers_invalid")
            names.append(header["name"])
        if len(set(names)) != len(names) or "video" not in names:
            raise DestinationConnectorDataError("youtube_official_api_columns_invalid")
        expected = {"video", *YOUTUBE_METRICS}
        if set(names) != expected:
            raise DestinationConnectorDataError("youtube_official_api_columns_do_not_match_request")

        target_by_video = {target.video_id: target for target in targets}
        seen: set[str] = set()
        snapshots: list[YouTubeMetricSnapshot] = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(names):
                raise DestinationConnectorDataError("youtube_official_api_row_shape_invalid")
            values = dict(zip(names, row, strict=True))
            video_id = str(values["video"] or "").strip()
            target = target_by_video.get(video_id)
            if target is None or video_id in seen:
                raise DestinationConnectorDataError("youtube_official_api_returned_unrequested_or_duplicate_video")
            seen.add(video_id)
            metrics = {
                "views": cls._integer_metric(values["views"], "views"),
                "likes": cls._integer_metric(values["likes"], "likes"),
                "comments": cls._integer_metric(values["comments"], "comments"),
                "shares": cls._integer_metric(values["shares"], "shares"),
                "watch_time_seconds": round(
                    cls._number_metric(values["estimatedMinutesWatched"], "estimatedMinutesWatched") * 60,
                    6,
                ),
                "retention_rate": round(
                    cls._percentage_metric(values["averageViewPercentage"]) / 100,
                    6,
                ),
            }
            snapshots.append(
                YouTubeMetricSnapshot(
                    video_id=video_id,
                    final_url=target.final_url,
                    publishing_task_id=target.publishing_task_id,
                    metrics=metrics,
                )
            )
        return snapshots

    @classmethod
    def _video_targets(cls, settings: dict[str, Any]) -> list[_VideoTarget]:
        raw_video_ids = settings.get("video_ids") or []
        raw_video_map = settings.get("video_map") or {}
        if not isinstance(raw_video_ids, list) or not isinstance(raw_video_map, dict):
            raise DestinationConnectorDataError("youtube_video_ids_or_video_map_invalid")

        ordered_ids: list[str] = []
        for raw_id in [*raw_video_ids, *raw_video_map.keys()]:
            video_id = str(raw_id or "").strip()
            if not _VIDEO_ID_RE.fullmatch(video_id):
                raise DestinationConnectorDataError("youtube_video_id_is_invalid")
            if video_id not in ordered_ids:
                ordered_ids.append(video_id)
        if not ordered_ids:
            raise DestinationConnectorDataError("youtube_video_ids_required")
        # reports.query returns at most 200 rows per request. Keep one sync
        # atomic and complete until cursor-based batching is implemented.
        if len(ordered_ids) > 200:
            raise DestinationConnectorDataError("youtube_video_ids_limit_exceeded")

        targets: list[_VideoTarget] = []
        for video_id in ordered_ids:
            mapping = raw_video_map.get(video_id) or {}
            if isinstance(mapping, str):
                mapping = {"final_url": mapping}
            if not isinstance(mapping, dict):
                raise DestinationConnectorDataError("youtube_video_map_entry_invalid")
            final_url = str(mapping.get("final_url") or f"https://www.youtube.com/watch?v={video_id}").strip()
            cls._validate_youtube_url(final_url)
            task_id = mapping.get("publishing_task_id")
            if task_id is not None:
                if isinstance(task_id, bool):
                    raise DestinationConnectorDataError("publishing_task_id_must_be_positive")
                try:
                    task_id = int(task_id)
                except (TypeError, ValueError) as exc:
                    raise DestinationConnectorDataError("publishing_task_id_must_be_positive") from exc
                if task_id <= 0:
                    raise DestinationConnectorDataError("publishing_task_id_must_be_positive")
            targets.append(
                _VideoTarget(
                    video_id=video_id,
                    final_url=final_url,
                    publishing_task_id=task_id,
                )
            )
        return targets

    @staticmethod
    def _require_owned_youtube_connection(
        connection: models.DestinationConnection,
        *,
        organization_id: int,
    ) -> None:
        if isinstance(organization_id, bool) or not isinstance(organization_id, int) or organization_id <= 0:
            raise DestinationConnectorDataError("organization_id_must_be_positive")
        destination = connection.destination
        if (
            destination is None
            or destination.id != connection.destination_id
            or destination.organization_id != organization_id
        ):
            raise DestinationConnectorDataError("destination_connection_not_found_in_organization")
        destination_platform = str(destination.platform or "").strip().lower().replace(" ", "_").replace("-", "_")
        connection_platform = str(connection.platform or "").strip().lower().replace(" ", "_").replace("-", "_")
        youtube_aliases = {"youtube", "youtube_shorts", "shorts"}
        if destination_platform not in youtube_aliases or connection_platform not in youtube_aliases:
            raise DestinationConnectorDataError("youtube_destination_required")

    @staticmethod
    def _validate_youtube_url(value: str) -> None:
        try:
            parts = urlsplit(value)
            query = parse_qsl(parts.query, keep_blank_values=True)
        except ValueError as exc:
            raise DestinationConnectorDataError("youtube_final_url_is_invalid") from exc
        host = (parts.hostname or "").lower().rstrip(".")
        if (
            parts.scheme.lower() != "https"
            or parts.username
            or parts.password
            or host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
            or any(key.lower() in _SECRET_QUERY_KEYS for key, _value in query)
        ):
            raise DestinationConnectorDataError("youtube_final_url_is_invalid")

    @staticmethod
    def _number_metric(value: Any, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise DestinationConnectorDataError(f"youtube_metric_{name}_is_invalid")
        result = float(value)
        if result < 0:
            raise DestinationConnectorDataError(f"youtube_metric_{name}_is_invalid")
        return result

    @classmethod
    def _integer_metric(cls, value: Any, name: str) -> int:
        result = cls._number_metric(value, name)
        if int(result) != result:
            raise DestinationConnectorDataError(f"youtube_metric_{name}_is_invalid")
        return int(result)

    @classmethod
    def _percentage_metric(cls, value: Any) -> float:
        result = cls._number_metric(value, "averageViewPercentage")
        if result > 100:
            raise DestinationConnectorDataError("youtube_metric_averageViewPercentage_is_invalid")
        return result
