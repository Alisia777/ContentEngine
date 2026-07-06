from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParticipantDashboard(BaseModel):
    participant_id: int
    display_name: str
    role: str
    status: str
    setup_steps: list[dict[str, Any]] = Field(default_factory=list)
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    destinations: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    payouts: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class ParticipantMetricResult(BaseModel):
    snapshot_id: int
    participant_id: int
    campaign_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    assignments_total: int
    submitted_total: int
    approved_total: int
    rejected_total: int
    published_total: int
    views_total: int
    clicks_total: int
    orders_total: int
    revenue_total: float
    engagement_rate: float | None = None
    approval_rate: float | None = None
    payout_total: float
    raw: dict[str, Any] = Field(default_factory=dict)


class ParticipantProfileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    role: str
    email: str | None = None
    telegram_handle: str | None = None
    status: str
    platforms_json: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
