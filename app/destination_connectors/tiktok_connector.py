from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol
from urllib.parse import urlsplit

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


TIKTOK_VIDEO_QUERY_URL = "https://open.tiktokapis.com/v2/video/query/"
TIKTOK_REQUIRED_SCOPE = "video.list"
TIKTOK_FIELDS = ("id", "view_count", "like_count", "comment_count", "share_count")
_VIDEO_ID_RE = re.compile(r"^[0-9]{6,32}$")


class TikTokDisplayTransport(Protocol):
    def query_videos(
        self,
        *,
        access_token: str,
        fields: tuple[str, ...],
        video_ids: list[str],
    ) -> dict[str, Any]: ...


class HttpxTikTokDisplayTransport:
    """Official TikTok Display API transport with bearer-only authorization."""

    def __init__(self, *, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds

    def query_videos(
        self,
        *,
        access_token: str,
        fields: tuple[str, ...],
        video_ids: list[str],
    ) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                response = client.post(
                    TIKTOK_VIDEO_QUERY_URL,
                    params={"fields": ",".join(fields)},
                    json={"filters": {"video_ids": video_ids}},
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            raise DestinationConnectorDataError("tiktok_official_api_transport_failed") from exc
        if response.status_code in {401, 403}:
            raise DestinationConnectorDataError("tiktok_official_api_authorization_failed")
        if response.status_code >= 400:
            raise DestinationConnectorDataError(
                f"tiktok_official_api_request_failed_status_{response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise DestinationConnectorDataError("tiktok_official_api_invalid_json") from exc
        if not isinstance(payload, dict):
            raise DestinationConnectorDataError("tiktok_official_api_invalid_response")
        return payload


@dataclass(frozen=True)
class TikTokMetricSnapshot:
    video_id: str
    final_url: str
    publishing_task_id: int
    metrics: dict[str, int | float]

    @property
    def external_post_id(self) -> str:
        return self.video_id


@dataclass(frozen=True)
class _TikTokTarget:
    video_id: str
    final_url: str
    publishing_task_id: int


class TikTokDisplayConnector:
    """Official Display API v2 adapter for videos owned by the OAuth user."""

    def __init__(
        self,
        *,
        transport: TikTokDisplayTransport | None = None,
        credential_resolver: CredentialResolver | None = None,
    ):
        self.transport = transport or HttpxTikTokDisplayTransport()
        self.credential_resolver = credential_resolver or EnvironmentCredentialResolver()
        self.credentials = CredentialStatusService(self.credential_resolver)

    def check(self, connection: models.DestinationConnection) -> CredentialCheckResult:
        return self.credentials.check(connection)

    def validate_configuration(
        self,
        connection: models.DestinationConnection,
        *,
        organization_id: int,
    ) -> list[_TikTokTarget]:
        if connection.connection_type != "tiktok_oauth":
            raise DestinationConnectorDataError("tiktok_oauth_connection_required")
        if not connection.credential_ref:
            raise DestinationConnectorDataError("tiktok_credential_reference_missing")
        if not self._resolve_credential(connection.credential_ref):
            raise DestinationConnectorDataError("tiktok_credential_reference_unresolved")
        settings = validate_non_secret_settings(connection.settings_json or {})
        return self._video_targets(
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
    ) -> list[TikTokMetricSnapshot]:
        if period_end < period_start:
            raise DestinationConnectorDataError("period_end_must_not_precede_period_start")
        targets = self.validate_configuration(connection, organization_id=organization_id)
        access_token = self._resolve_credential(connection.credential_ref or "")
        if not access_token:
            raise DestinationConnectorDataError("tiktok_credential_reference_unresolved")
        payload = self.transport.query_videos(
            access_token=access_token,
            fields=TIKTOK_FIELDS,
            video_ids=[target.video_id for target in targets],
        )
        return self._normalize_response(payload, targets=targets)

    def _resolve_credential(self, credential_ref: str) -> str | None:
        try:
            return self.credential_resolver.resolve(credential_ref)
        except Exception as exc:
            raise DestinationConnectorDataError("tiktok_credential_resolution_failed") from exc

    @classmethod
    def _video_targets(
        cls,
        connection: models.DestinationConnection,
        *,
        settings: dict[str, Any],
        organization_id: int,
    ) -> list[_TikTokTarget]:
        if set(settings) != {"video_map"}:
            raise DestinationConnectorDataError("tiktok_settings_fields_invalid")
        raw_map = settings.get("video_map")
        if not isinstance(raw_map, dict) or not raw_map:
            raise DestinationConnectorDataError("tiktok_video_map_required")
        if len(raw_map) > 20:
            raise DestinationConnectorDataError("tiktok_video_map_limit_exceeded")
        targets: list[_TikTokTarget] = []
        for raw_id, raw_mapping in raw_map.items():
            video_id = str(raw_id or "").strip()
            if not _VIDEO_ID_RE.fullmatch(video_id):
                raise DestinationConnectorDataError("tiktok_video_id_is_invalid")
            if not isinstance(raw_mapping, dict):
                raise DestinationConnectorDataError("tiktok_video_map_entry_invalid")
            if set(raw_mapping) != {"final_url", "publishing_task_id"}:
                raise DestinationConnectorDataError("tiktok_video_map_entry_fields_invalid")
            final_url = str(raw_mapping.get("final_url") or "").strip()
            task_id = positive_task_id(
                raw_mapping.get("publishing_task_id"),
                error_code="tiktok_publishing_task_id_required",
            )
            cls._validate_tiktok_url(final_url, video_id=video_id)
            require_owned_published_target(
                connection,
                organization_id=organization_id,
                publishing_task_id=task_id,
                final_url=final_url,
                expected_platform="tiktok",
                error_prefix="tiktok",
            )
            targets.append(
                _TikTokTarget(
                    video_id=video_id,
                    final_url=final_url,
                    publishing_task_id=task_id,
                )
            )
        return targets

    @staticmethod
    def _validate_tiktok_url(value: str, *, video_id: str) -> None:
        canonical = safe_public_url(value, error_code="tiktok_final_url_is_invalid")
        parts = urlsplit(canonical)
        if (parts.hostname or "").lower() not in {"www.tiktok.com", "m.tiktok.com"}:
            raise DestinationConnectorDataError("tiktok_final_url_is_invalid")
        if not re.fullmatch(rf"/@[^/]+/video/{re.escape(video_id)}", parts.path.rstrip("/")):
            raise DestinationConnectorDataError("tiktok_final_url_is_invalid")

    @classmethod
    def _normalize_response(
        cls,
        payload: dict[str, Any],
        *,
        targets: list[_TikTokTarget],
    ) -> list[TikTokMetricSnapshot]:
        error = payload.get("error")
        if not isinstance(error, dict) or error.get("code") != "ok":
            raise DestinationConnectorDataError("tiktok_official_api_rejected_request")
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
            raise DestinationConnectorDataError("tiktok_official_api_videos_invalid")
        videos = data["videos"]
        target_by_id = {target.video_id: target for target in targets}
        seen: set[str] = set()
        snapshots: list[TikTokMetricSnapshot] = []
        expected_fields = set(TIKTOK_FIELDS)
        for item in videos:
            if not isinstance(item, dict) or set(item) != expected_fields:
                raise DestinationConnectorDataError("tiktok_official_api_video_shape_invalid")
            video_id = str(item.get("id") or "").strip()
            target = target_by_id.get(video_id)
            if target is None or video_id in seen:
                raise DestinationConnectorDataError(
                    "tiktok_official_api_returned_unrequested_or_duplicate_video"
                )
            seen.add(video_id)
            snapshots.append(
                TikTokMetricSnapshot(
                    video_id=video_id,
                    final_url=target.final_url,
                    publishing_task_id=target.publishing_task_id,
                    metrics={
                        "views": non_negative_integer(
                            item["view_count"], error_code="tiktok_metric_view_count_is_invalid"
                        ),
                        "likes": non_negative_integer(
                            item["like_count"], error_code="tiktok_metric_like_count_is_invalid"
                        ),
                        "comments": non_negative_integer(
                            item["comment_count"], error_code="tiktok_metric_comment_count_is_invalid"
                        ),
                        "shares": non_negative_integer(
                            item["share_count"], error_code="tiktok_metric_share_count_is_invalid"
                        ),
                    },
                )
            )
        if seen != set(target_by_id):
            raise DestinationConnectorDataError("tiktok_official_api_missing_requested_video")
        return snapshots
