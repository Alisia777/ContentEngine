from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DestinationSetupRequirementResult(BaseModel):
    id: int
    campaign_id: int
    platform: str
    required_count: int = 0
    existing_ready_count: int = 0
    capacity_gap: int = 0
    reason: str
    status: str
    created_at: datetime
    updated_at: datetime


class DestinationProfilePackResult(BaseModel):
    id: int
    campaign_id: int
    platform: str
    sku_focus: list[dict[str, Any]] = Field(default_factory=list)
    theme: str
    suggested_name: str
    suggested_handle: str
    bio_text: str | None = None
    avatar_prompt: str | None = None
    avatar_asset_path: str | None = None
    content_pillars: list[str] = Field(default_factory=list)
    first_posts: list[dict[str, Any]] = Field(default_factory=list)
    posting_rules: list[dict[str, Any] | str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime


class DestinationSetupTaskResult(BaseModel):
    id: int
    campaign_id: int
    profile_pack_id: int
    platform: str
    status: str
    owner_name: str | None = None
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    final_account_url: str | None = None
    final_handle: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class DestinationSetupReadinessResult(BaseModel):
    task_id: int
    ready: bool
    status: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
