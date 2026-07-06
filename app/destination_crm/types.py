from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DestinationReadinessResult(BaseModel):
    snapshot_id: int
    destination_id: int
    campaign_id: int | None = None
    status: str
    platform: str
    posting_mode: str
    auth_status: str
    active: bool = False
    manual_ready: bool = False
    api_ready: bool = False
    warmup_phase: str
    daily_limit: int = 0
    weekly_limit: int = 0
    used_today: int = 0
    used_this_week: int = 0
    remaining_daily_capacity: int = 0
    remaining_weekly_capacity: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class DestinationWarmupPlanResult(BaseModel):
    id: int
    destination_id: int
    status: str
    start_date: datetime
    current_phase: str
    rules: list[dict[str, Any]] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class DestinationCampaignCapacityResult(BaseModel):
    campaign_id: int
    total_destinations: int = 0
    active_destinations: int = 0
    ready_destinations: int = 0
    manual_ready_destinations: int = 0
    api_ready_destinations: int = 0
    paused_destinations: int = 0
    blocked_destinations: int = 0
    required_slots: int = 0
    available_daily_capacity: int = 0
    available_weekly_capacity: int = 0
    capacity_gap: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    destinations: list[DestinationReadinessResult] = Field(default_factory=list)


class DestinationHealthResult(BaseModel):
    id: int
    destination_id: int
    status: str
    last_posted_at: datetime | None = None
    last_final_url: str | None = None
    recent_task_count: int = 0
    failed_task_count: int = 0
    avg_views: float = 0
    avg_engagement_rate: float = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DestinationCRMAction(BaseModel):
    destination_id: int | None = None
    campaign_id: int | None = None
    action_type: str
    action: str
    priority: int = 50
    reason: str
    blockers: list[dict[str, Any]] = Field(default_factory=list)
