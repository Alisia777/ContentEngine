from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PublishingReadiness:
    ready: bool
    status: str
    blockers: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class PublishingCalendarItem:
    task_id: int
    package_id: int
    destination_id: int
    platform: str
    scheduled_at: datetime
    status: str
    final_url: str | None
