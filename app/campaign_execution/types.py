from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ExecutionSnapshotResult(BaseModel):
    snapshot_id: int
    campaign_id: int
    status: str
    total_sku: int = 0
    ready_sku: int = 0
    blocked_sku: int = 0
    prompt_ready_count: int = 0
    real_smoke_ready_count: int = 0
    needs_review_count: int = 0
    approved_video_count: int = 0
    publishing_package_ready_count: int = 0
    distribution_task_ready_count: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ActionQueueItemResult(BaseModel):
    action_id: int
    campaign_id: int
    product_id: int | None = None
    sku: str | None = None
    content_run_id: int | None = None
    action_type: str
    priority: int
    status: str
    reason: str | None = None
    blockers: list[str] = Field(default_factory=list)
    safe_to_execute: bool = False
    requires_human: bool = True


class ActionExecutionResult(BaseModel):
    action_id: int
    status: str
    executed: bool = False
    message: str
    artifacts: dict[str, Any] = Field(default_factory=dict)


class ExecutionReport(BaseModel):
    campaign_id: int
    snapshot: ExecutionSnapshotResult
    actions: list[ActionQueueItemResult] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    summary_csv: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
