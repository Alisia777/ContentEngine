from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class PerformanceImportResult(BaseModel):
    import_id: int
    campaign_id: int
    status: str
    imported_count: int = 0
    error_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CampaignPerformanceSummary(BaseModel):
    campaign_id: int
    metric_count: int = 0
    total_views: int = 0
    total_clicks: int = 0
    total_orders: int = 0
    total_revenue: float = 0
    total_spend: float = 0
    avg_ctr: float | None = None
    avg_conversion_rate: float | None = None
    avg_engagement_rate: float | None = None
    by_sku: list[dict[str, Any]] = Field(default_factory=list)
    by_variant: list[dict[str, Any]] = Field(default_factory=list)
    by_destination: list[dict[str, Any]] = Field(default_factory=list)
    by_platform: list[dict[str, Any]] = Field(default_factory=list)
    published_without_metrics: list[dict[str, Any]] = Field(default_factory=list)


class PerformanceScoreResult(BaseModel):
    score_id: int
    campaign_id: int
    entity_type: str
    entity_id: str | None = None
    status: str
    recommendation: str | None = None
    score: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class ScalingRecommendationResult(BaseModel):
    recommendation_id: int
    campaign_id: int
    recommendation_type: str
    product_id: int | None = None
    sku: str | None = None
    creative_variant_id: int | None = None
    destination_id: int | None = None
    priority: int = 50
    expected_impact: str | None = None
    reasons: list[str] = Field(default_factory=list)
    status: str = "proposed"


class CampaignPerformanceReport(BaseModel):
    campaign_id: int
    summary: CampaignPerformanceSummary
    scores: list[PerformanceScoreResult] = Field(default_factory=list)
    recommendations: list[ScalingRecommendationResult] = Field(default_factory=list)
    summary_csv: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
