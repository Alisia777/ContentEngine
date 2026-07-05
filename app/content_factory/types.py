from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ContentNextAction(BaseModel):
    action: str
    priority: int = 50
    status: str = "recommended"
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ContentRunResult(BaseModel):
    id: int
    status: str
    product_id: int
    sku: str | None = None
    platform: str
    duration_seconds: int
    variant_count: int
    demand_hypothesis_id: int | None = None
    creative_spec_id: int | None = None
    asset_kit_id: int | None = None
    creative_variant_set_id: int | None = None
    selected_variant_id: int | None = None
    generation_variant_id: int | None = None
    prompt_pack_id: int | None = None
    video_job_id: int | None = None
    ai_review_id: int | None = None
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[ContentNextAction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    run: dict[str, Any] = Field(default_factory=dict)
    buyer_need: str | None = None
    safe_promise: str | None = None
    reference_readiness: dict[str, Any] = Field(default_factory=dict)
    geometry_readiness: dict[str, Any] = Field(default_factory=dict)
    product_identity_readiness: dict[str, Any] = Field(default_factory=dict)
    publishing_readiness: dict[str, Any] = Field(default_factory=dict)
    ai_review_status: str | None = None
    human_review_required: bool | None = None
    next_action: str | None = None


class AIReviewResult(BaseModel):
    status: str
    score: float
    human_review_required: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ContentFactoryDashboard(BaseModel):
    total_runs: int = 0
    prepared_runs: int = 0
    blocked_runs: int = 0
    prompt_ready_runs: int = 0
    real_smoke_ready_runs: int = 0
    human_review_queue: int = 0
    needs_regeneration_runs: int = 0
    geometry_mismatch_blockers: int = 0
    publishing_ready_runs: int = 0
    performance_metric_count: int = 0
    top_blockers: list[dict[str, Any]] = Field(default_factory=list)
    recent_runs: list[dict[str, Any]] = Field(default_factory=list)
    performance_summary: dict[str, Any] = Field(default_factory=dict)


class ContentPerformanceRow(BaseModel):
    content_run_id: int | None = None
    product_id: int | None = None
    sku: str | None = None
    platform: str
    creative_variant_id: int | None = None
    video_job_id: int | None = None
    metric_date: date | None = None
    impressions: int | None = None
    views: int | None = None
    clicks: int | None = None
    orders: int | None = None
    revenue: float | None = None
    spend: float | None = None
    ctr: float | None = None
    conversion_rate: float | None = None
    watch_time_seconds: float | None = None
    retention_rate: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ContentStatsImportResult(BaseModel):
    imported_count: int = 0
    error_count: int = 0
    errors: list[str] = Field(default_factory=list)
    imported_at: datetime
