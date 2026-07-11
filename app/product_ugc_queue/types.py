from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app import models


@dataclass(frozen=True)
class EnqueueResult:
    job: models.ProductUGCGenerationJob
    created: bool


@dataclass(frozen=True)
class FailureDisposition:
    job: models.ProductUGCGenerationJob
    will_retry: bool
    quarantined: bool


@dataclass(frozen=True)
class ReconciliationResult:
    released_for_retry: int = 0
    terminal_failures: int = 0
    quarantined: int = 0
    recovered_drafts: int = 0


@dataclass(frozen=True)
class QuarantineReconciliationResult:
    job: models.ProductUGCGenerationJob
    reconciliation: models.ProductUGCQueueReconciliation
    created: bool


QueueSummary = dict[str, Any]
QueueOperationalHealth = dict[str, Any]
