from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DestinationControlRowResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_id: int
    snapshot_id: int
    destination_id: int | None = None
    platform: str
    name: str | None = None
    handle: str | None = None
    setup_status: str
    readiness_status: str
    connection_status: str
    publishing_status: str
    metrics_status: str
    performance_status: str
    warmup_phase: str | None = None
    daily_capacity_remaining: int = 0
    weekly_capacity_remaining: int = 0
    last_post_url: str | None = None
    last_sync_at: datetime | None = None
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_action: str | None = None


class DestinationControlSnapshotResult(BaseModel):
    snapshot_id: int
    campaign_id: int
    total_destinations: int
    setup_needed_count: int
    ready_count: int
    connected_count: int
    metrics_synced_count: int
    no_metrics_count: int
    low_performance_count: int
    paused_count: int
    capacity_total: int
    capacity_used: int
    capacity_gap: int
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class DestinationControlReport(BaseModel):
    snapshot: DestinationControlSnapshotResult
    rows: list[DestinationControlRowResult]
    markdown: str
