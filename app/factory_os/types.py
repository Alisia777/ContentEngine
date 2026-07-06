from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class FactoryHealthStatus(BaseModel):
    overall_status: str
    checks: list[dict[str, Any]] = Field(default_factory=list)
    provider_keys: dict[str, Any] = Field(default_factory=dict)
    safety_gates: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FactoryAcceptanceReport(BaseModel):
    campaign_id: int
    total_sku: int = 0
    target_videos: int = 0
    target_destinations: int = 0
    content_runs_created: int = 0
    prompt_packs_created: int = 0
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    batch_actions_executed: int = 0
    publishing_packages_draft: int = 0
    publishing_packages_approved: int = 0
    distribution_plan_status: str = "missing"
    performance_metrics_imported: int = 0
    recommendations_generated: int = 0
    paid_calls_made: int = 0
    unsafe_actions_blocked: int = 0
    generated_artifacts_paths: list[str] = Field(default_factory=list)
    next_manual_actions: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FactoryLaunchResult(BaseModel):
    campaign_id: int
    import_id: int | None = None
    status: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    acceptance_report: FactoryAcceptanceReport
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FactoryRunbook(BaseModel):
    campaign_id: int
    next_manual_steps: list[dict[str, Any]] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
