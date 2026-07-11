from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class SocialMetricObservation:
    organization_id: int
    actor_user_profile_id: int
    source_type: str
    source_ref: str
    platform: str
    observed_at: datetime
    period_start: date
    period_end: date
    metrics: dict[str, int | float | None]
    final_url: str | None = None
    external_post_id: str | None = None
    publishing_task_id: int | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class SocialMetricIngestionResult:
    status: str
    disposition: str
    metric_id: int | None = None
    quarantine_id: int | None = None
    reason: str | None = None
    canonical_key: str | None = None
    observation_key: str | None = None
    publishing_task_id: int | None = None
    observed_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    details: dict[str, Any] = field(default_factory=dict)
