from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProductMatrixImportResult(BaseModel):
    import_id: int
    source_file: str
    status: str
    imported_count: int
    error_count: int
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CampaignResult(BaseModel):
    campaign_id: int
    name: str
    brand: str
    status: str
    source_type: str
    product_ids: list[int] = Field(default_factory=list)
    target_video_count: int
    target_destination_count: int
    strategy: dict[str, Any] = Field(default_factory=dict)


class TargetAllocationResult(BaseModel):
    campaign_id: int
    total_products: int
    total_target_videos: int
    allocations: list[dict[str, Any]] = Field(default_factory=list)


class CampaignPrepareResult(BaseModel):
    campaign_id: int
    campaign_run_id: int
    status: str
    total_products: int
    total_content_runs: int
    total_prompt_ready: int
    total_blocked: int
    blockers: list[str] = Field(default_factory=list)
    products: list[dict[str, Any]] = Field(default_factory=list)


class CampaignState(BaseModel):
    campaign_id: int
    status: str
    sku_coverage: dict[str, Any] = Field(default_factory=dict)
    prompt_ready_count: int = 0
    real_smoke_ready_count: int = 0
    blocked_count: int = 0
    blockers_by_type: list[dict[str, Any]] = Field(default_factory=list)
    missing_references: int = 0
    missing_geometry_lock: int = 0
    needs_human_review: int = 0
    publishing_ready_count: int = 0
    next_actions_by_sku: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CampaignDistributionPlanResult(BaseModel):
    plan_id: int
    campaign_id: int
    status: str
    target_destination_count: int
    total_slots: int
    scheduled_slots: int
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    plan: dict[str, Any] = Field(default_factory=dict)


class CampaignReport(BaseModel):
    campaign_id: int
    state: CampaignState
    performance: dict[str, Any] = Field(default_factory=dict)
    distribution_plan: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
