from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class LaunchQualityGateResult(BaseModel):
    gate_id: int
    campaign_id: int
    video_job_id: int | None = None
    creative_variant_id: int | None = None
    product_id: int | None = None
    sku: str | None = None
    status: str
    quality_review_status: str
    human_visual_status: str
    product_identity_status: str
    geometry_status: str
    publishing_allowed: bool = False
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    required_fixes: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DestinationCapacityResult(BaseModel):
    snapshot_id: int
    campaign_id: int
    total_destinations: int = 0
    active_destinations: int = 0
    manual_destinations: int = 0
    api_ready_destinations: int = 0
    daily_capacity: int = 0
    weekly_capacity: int = 0
    required_slots: int = 0
    capacity_gap: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LaunchActionPlanResult(BaseModel):
    plan_id: int
    campaign_id: int
    status: str
    action_count: int = 0
    safe_action_count: int = 0
    human_action_count: int = 0
    paid_action_count: int = 0
    publishing_action_count: int = 0
    actions: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LaunchReadinessResult(BaseModel):
    snapshot_id: int
    campaign_id: int
    status: str
    total_sku: int = 0
    target_videos: int = 0
    target_destinations: int = 0
    prompt_ready_count: int = 0
    real_video_count: int = 0
    approved_video_count: int = 0
    needs_human_review_count: int = 0
    needs_regeneration_count: int = 0
    publishing_package_ready_count: int = 0
    destination_total: int = 0
    destination_active_count: int = 0
    destination_capacity_total: int = 0
    distribution_task_ready_count: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LaunchOperationsReport(BaseModel):
    campaign_id: int
    readiness: LaunchReadinessResult
    quality_gates: list[LaunchQualityGateResult] = Field(default_factory=list)
    destination_capacity: DestinationCapacityResult
    action_plan: LaunchActionPlanResult
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LaunchRunbookExport(BaseModel):
    campaign_id: int
    report_paths: dict[str, str] = Field(default_factory=dict)
    action_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
