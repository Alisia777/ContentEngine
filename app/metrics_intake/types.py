from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricsSourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str
    platform: str
    status: str
    connection_id: int | None = None
    settings_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TrackingLinkView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    target_url: str
    campaign_id: int | None = None
    publishing_task_id: int | None = None
    destination_id: int | None = None
    product_id: int | None = None
    sku: str | None = None
    creative_variant_id: int | None = None
    participant_id: int | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class MetricsBatchResult(BaseModel):
    batch_id: int
    source_id: int | None = None
    campaign_id: int | None = None
    source_type: str
    status: str
    imported_count: int
    matched_count: int
    unmatched_count: int
    warning_count: int
    error_count: int
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AttributionResult(BaseModel):
    batch_id: int
    status: str
    matched_count: int
    unmatched_count: int
    warning_count: int
    destination_metric_ids: list[int] = Field(default_factory=list)
    funnel_snapshot_ids: list[int] = Field(default_factory=list)
    unmatched_rows: list[dict[str, Any]] = Field(default_factory=list)


class FunnelSnapshotResult(BaseModel):
    snapshot_id: int
    campaign_id: int | None = None
    product_id: int | None = None
    sku: str | None = None
    creative_variant_id: int | None = None
    destination_id: int | None = None
    participant_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    views: int
    reach: int
    impressions: int
    engagements: int
    clicks: int
    orders: int
    revenue: float
    returns_count: int
    ctr: float | None = None
    conversion_rate: float | None = None
    revenue_per_view: float | None = None
    revenue_per_click: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
