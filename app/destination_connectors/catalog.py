from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class OfficialConnectorDefinition:
    """Public, secret-free contract for one production metrics adapter."""

    platform: str
    connection_type: str
    display_name: str
    api_product: str
    endpoint: str
    target_map_key: str
    target_id_label: str
    idempotency_prefix: str
    source_ref_prefix: str
    max_targets_per_request: int
    required_scopes: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    account_requirements: tuple[str, ...] = ()

    def public_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("required_scopes", "required_permissions", "account_requirements"):
            payload[key] = list(payload[key])
        return payload


OFFICIAL_CONNECTOR_CATALOG: dict[str, OfficialConnectorDefinition] = {
    "youtube_oauth": OfficialConnectorDefinition(
        platform="youtube",
        connection_type="youtube_oauth",
        display_name="YouTube Analytics",
        api_product="YouTube Analytics API v2 reports.query",
        endpoint="https://youtubeanalytics.googleapis.com/v2/reports",
        target_map_key="video_map",
        target_id_label="video_id",
        idempotency_prefix="yt",
        source_ref_prefix="youtube-analytics",
        max_targets_per_request=200,
        required_scopes=("https://www.googleapis.com/auth/youtube.readonly",),
    ),
    "tiktok_oauth": OfficialConnectorDefinition(
        platform="tiktok",
        connection_type="tiktok_oauth",
        display_name="TikTok Display API",
        api_product="TikTok Display API v2 Query Videos",
        endpoint="https://open.tiktokapis.com/v2/video/query/",
        target_map_key="video_map",
        target_id_label="video_id",
        idempotency_prefix="tt",
        source_ref_prefix="tiktok-display",
        max_targets_per_request=20,
        required_scopes=("video.list",),
    ),
    "instagram_oauth": OfficialConnectorDefinition(
        platform="instagram",
        connection_type="instagram_oauth",
        display_name="Instagram Insights",
        api_product="Instagram API with Instagram Login — Media Insights",
        endpoint="https://graph.instagram.com/{api_version}/{media_id}/insights",
        target_map_key="media_map",
        target_id_label="media_id",
        idempotency_prefix="ig",
        source_ref_prefix="instagram-insights",
        max_targets_per_request=50,
        required_permissions=(
            "instagram_business_basic",
            "instagram_business_manage_insights",
        ),
        account_requirements=("instagram_professional_account",),
    ),
}

OFFICIAL_CONNECTION_TYPES = frozenset(OFFICIAL_CONNECTOR_CATALOG)


def connector_definition(connection_type: str | None) -> OfficialConnectorDefinition | None:
    return OFFICIAL_CONNECTOR_CATALOG.get(str(connection_type or "").strip())


def connector_definitions_for_platform(platform: str) -> tuple[OfficialConnectorDefinition, ...]:
    normalized = str(platform or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "youtube_shorts": "youtube",
        "shorts": "youtube",
        "ig": "instagram",
        "instagram_reels": "instagram",
        "reels": "instagram",
    }
    normalized = aliases.get(normalized, normalized)
    return tuple(
        definition
        for definition in OFFICIAL_CONNECTOR_CATALOG.values()
        if definition.platform == normalized
    )
