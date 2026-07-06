from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


NORMALIZED_METRIC_COLUMNS = [
    "platform",
    "destination_id",
    "posted_url",
    "tracking_slug",
    "campaign_id",
    "product_id",
    "sku",
    "creative_variant_id",
    "participant_id",
    "period_start",
    "period_end",
    "views",
    "reach",
    "impressions",
    "engagements",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "orders",
    "revenue",
    "spend",
    "watch_time_seconds",
    "retention_rate",
    "source_type",
    "match_confidence",
    "warnings",
]


@dataclass(frozen=True)
class PlatformMetricsConfig:
    platform: str
    official_connector_types: list[str] = field(default_factory=list)
    fallback_source_types: list[str] = field(default_factory=lambda: ["manual_csv", "partner_report"])
    required_identity_columns: list[str] = field(default_factory=lambda: ["posted_url", "tracking_slug", "publishing_task_id"])
    supported_metric_columns: list[str] = field(default_factory=list)
    conversion_source: str = "tracking_link_or_manual_csv"
    notes: str = ""


class PlatformMetricsMatrix:
    PLATFORM_ALIASES = {
        "meta": "facebook",
        "fb": "facebook",
        "facebook": "facebook",
        "instagram": "instagram",
        "ig": "instagram",
        "youtube": "youtube",
        "youtube_shorts": "youtube",
        "shorts": "youtube",
        "tiktok": "tiktok",
        "telegram": "telegram",
        "tg": "telegram",
        "vk": "vk",
        "vkontakte": "vk",
        "ozon": "ozon",
        "wildberries": "wb",
        "wb": "wb",
        "marketplace": "marketplace",
        "partner": "partner",
        "partner_slot": "partner",
        "partner_report": "partner",
    }

    CONFIGS: dict[str, PlatformMetricsConfig] = {
        "facebook": PlatformMetricsConfig(
            platform="facebook",
            official_connector_types=["meta_oauth", "facebook_page"],
            supported_metric_columns=["views", "reach", "impressions", "likes", "comments", "shares", "saves", "clicks"],
            notes="Official Meta access when authorized; otherwise CSV/manual plus tracking links.",
        ),
        "instagram": PlatformMetricsConfig(
            platform="instagram",
            official_connector_types=["meta_oauth", "instagram_business"],
            supported_metric_columns=["views", "reach", "impressions", "likes", "comments", "shares", "saves", "clicks"],
            notes="Official Meta/Instagram Business access when authorized; otherwise CSV/manual plus tracking links.",
        ),
        "youtube": PlatformMetricsConfig(
            platform="youtube",
            official_connector_types=["youtube_oauth", "youtube_analytics"],
            supported_metric_columns=["views", "likes", "comments", "shares", "clicks", "watch_time_seconds", "retention_rate"],
            notes="YouTube Analytics OAuth when authorized; otherwise CSV/manual plus tracking links.",
        ),
        "tiktok": PlatformMetricsConfig(
            platform="tiktok",
            official_connector_types=["tiktok_official_api"],
            supported_metric_columns=["views", "likes", "comments", "shares", "clicks"],
            notes="Official TikTok access only; no private login or scraping fallback.",
        ),
        "telegram": PlatformMetricsConfig(
            platform="telegram",
            official_connector_types=["telegram_bot"],
            supported_metric_columns=["views", "comments", "shares", "clicks"],
            notes="Bot/admin data when available; otherwise manual/CSV plus tracking links.",
        ),
        "vk": PlatformMetricsConfig(
            platform="vk",
            official_connector_types=["vk_api"],
            supported_metric_columns=["views", "likes", "comments", "shares", "clicks"],
            notes="Official VK API when authorized; otherwise manual/CSV plus tracking links.",
        ),
        "ozon": PlatformMetricsConfig(
            platform="ozon",
            official_connector_types=["ozon_seller_api"],
            fallback_source_types=["marketplace_csv", "manual_csv"],
            required_identity_columns=["sku", "period_start", "period_end", "coupon_code", "tracking_slug"],
            supported_metric_columns=["orders", "revenue", "spend"],
            conversion_source="marketplace_report",
            notes="Marketplace conversion source for orders/revenue/returns, not social reach.",
        ),
        "wb": PlatformMetricsConfig(
            platform="wb",
            official_connector_types=["wildberries_seller_api"],
            fallback_source_types=["marketplace_csv", "manual_csv"],
            required_identity_columns=["sku", "period_start", "period_end", "coupon_code", "tracking_slug"],
            supported_metric_columns=["orders", "revenue", "spend"],
            conversion_source="marketplace_report",
            notes="Marketplace conversion source for orders/revenue/returns, not social reach.",
        ),
        "partner": PlatformMetricsConfig(
            platform="partner",
            official_connector_types=[],
            fallback_source_types=["partner_report", "manual_csv"],
            required_identity_columns=["posted_url", "tracking_slug", "sku", "period_start", "period_end"],
            supported_metric_columns=["views", "reach", "impressions", "likes", "comments", "shares", "saves", "clicks", "orders", "revenue"],
            conversion_source="partner_report",
            notes="Partner-owned slots require final_url, tracking link, and report upload.",
        ),
        "other": PlatformMetricsConfig(
            platform="other",
            official_connector_types=[],
            supported_metric_columns=["views", "clicks", "orders", "revenue"],
            notes="Generic manual/CSV source.",
        ),
    }

    @classmethod
    def normalize_platform(cls, platform: Any) -> str:
        text = str(platform or "").strip().lower().replace(" ", "_").replace("-", "_")
        return cls.PLATFORM_ALIASES.get(text, text or "other")

    @classmethod
    def config(cls, platform: Any) -> PlatformMetricsConfig:
        normalized = cls.normalize_platform(platform)
        return cls.CONFIGS.get(normalized, cls.CONFIGS["other"])

    @classmethod
    def all_configs(cls) -> list[PlatformMetricsConfig]:
        return [cls.CONFIGS[key] for key in ["facebook", "instagram", "youtube", "tiktok", "telegram", "vk", "ozon", "wb", "partner", "other"]]

    @classmethod
    def normalize_row(cls, row: dict[str, Any], *, source_type: str) -> dict[str, Any]:
        platform = cls.normalize_platform(row.get("platform"))
        config = cls.config(platform)
        normalized: dict[str, Any] = {column: "" for column in NORMALIZED_METRIC_COLUMNS}
        for column in NORMALIZED_METRIC_COLUMNS:
            if column in row and row[column] is not None:
                normalized[column] = str(row[column]).strip()
        normalized["platform"] = platform
        normalized["source_type"] = source_type
        normalized["engagements"] = normalized.get("engagements") or cls._engagements(row)
        normalized["match_confidence"] = normalized.get("match_confidence") or ""
        warnings = list(row.get("warnings") or []) if isinstance(row.get("warnings"), list) else []
        if not any(str(row.get(column) or "").strip() for column in config.required_identity_columns):
            warnings.append("missing_platform_identity")
        if platform in {"facebook", "instagram", "youtube", "tiktok", "telegram", "vk", "partner"}:
            if not str(row.get("posted_url") or "").strip() and not str(row.get("tracking_slug") or "").strip():
                warnings.append("missing_posted_url_or_tracking_slug")
        normalized["warnings"] = warnings
        for key, value in row.items():
            if key not in normalized:
                normalized[key] = value
        return normalized

    @staticmethod
    def _engagements(row: dict[str, Any]) -> str:
        total = 0
        found = False
        for key in ["likes", "comments", "shares", "saves"]:
            text = str(row.get(key) or "").strip().replace(",", ".")
            if text:
                total += int(float(text))
                found = True
        return str(total) if found else ""
