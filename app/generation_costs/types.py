from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app import models


@dataclass(frozen=True)
class GenerationCostRecordResult:
    entry: models.GenerationCostLedgerEntry
    created: bool


@dataclass(frozen=True)
class GenerationCostAggregate:
    organization_id: int
    currency: str
    effective_entry_count: int
    estimated_cost_minor: int
    confirmed_actual_cost_minor: int
    pending_actual_cost_minor: int
    recognized_cost_minor: int
    priced_video_count: int
    generated_video_count: int
    approved_video_count: int
    organization_generated_video_count: int
    organization_approved_video_count: int
    unpriced_generated_video_count: int
    unpriced_approved_video_count: int
    cost_per_generated_video_minor: Decimal | None
    cost_per_approved_video_minor: Decimal | None
