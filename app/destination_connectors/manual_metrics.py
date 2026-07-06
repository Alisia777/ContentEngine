from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.metrics_collector import DestinationMetricsCollector
from app.destination_connectors.types import DestinationMetricSyncResult


class ManualMetricsCollector:
    def __init__(self, db: Session):
        self.db = db

    def import_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        connection: models.DestinationConnection | None = None,
        campaign_id: int | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> DestinationMetricSyncResult:
        return DestinationMetricsCollector(self.db).import_rows(
            rows,
            connection=connection,
            campaign_id=campaign_id,
            period_start=period_start,
            period_end=period_end,
            source="manual",
        )
