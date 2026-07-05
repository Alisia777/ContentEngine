from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class BombarImportResult(BaseModel):
    import_id: int
    source_file: str
    status: str
    imported_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BombarCampaignResult(BaseModel):
    campaign_id: int
    linked_campaign_id: int
    name: str
    brand: str
    status: str
    product_ids: list[int] = Field(default_factory=list)
    target_video_count: int
    target_destination_count: int


class DestinationSetupPackResult(BaseModel):
    pack_id: int
    campaign_id: int
    sku: str | None
    destination_type: str
    platform: str
    suggested_name: str
    suggested_handle: str
    status: str
    content_pillars: list[str] = Field(default_factory=list)
    first_posts: list[dict[str, Any]] = Field(default_factory=list)
    setup_checklist: list[str] = Field(default_factory=list)


class DistributionPlanResult(BaseModel):
    plan_id: int
    campaign_id: int
    status: str
    total_products: int
    total_video_targets: int
    total_destinations: int
    total_tasks: int
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    plan: dict[str, Any] = Field(default_factory=dict)


class BombarDashboard(BaseModel):
    campaign_id: int
    linked_campaign_id: int
    campaign_status: str
    ready_sku: int = 0
    blocked_sku: int = 0
    needs_reference: int = 0
    needs_review: int = 0
    ready_for_publishing: int = 0
    destination_packs: int = 0
    publishing_tasks: int = 0
    top_blockers: list[dict[str, Any]] = Field(default_factory=list)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    campaign_state: dict[str, Any] = Field(default_factory=dict)
    campaign_report: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
