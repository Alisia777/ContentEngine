from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class BatchActionPreview(BaseModel):
    action_id: int
    campaign_id: int
    product_id: int | None = None
    sku: str | None = None
    content_run_id: int | None = None
    action_type: str
    status: str
    safe_to_execute: bool
    reason: str | None = None
    blockers: list[str] = Field(default_factory=list)
    skip_reason: str | None = None


class BatchSelectionResult(BaseModel):
    campaign_id: int
    action_type: str | None = None
    selected_actions: list[BatchActionPreview] = Field(default_factory=list)
    skipped_actions: list[BatchActionPreview] = Field(default_factory=list)
    safe_action_count: int = 0
    skipped_count: int = 0


class BatchRunResult(BaseModel):
    batch_run_id: int
    campaign_id: int
    status: str
    action_type: str | None = None
    dry_run: bool = True
    selected_action_ids: list[int] = Field(default_factory=list)
    total_selected: int = 0
    total_executed: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchReport(BaseModel):
    batch_run: BatchRunResult
    items: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    summary_csv: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
