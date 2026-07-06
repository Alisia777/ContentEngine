from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.metrics_collector import DestinationMetricsCollector
from app.destination_connectors.types import DestinationMetricSyncResult


class CSVMetricsImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_csv_text(
        self,
        csv_text: str,
        *,
        connection: models.DestinationConnection | None = None,
        campaign_id: int | None = None,
        source_file: str = "destination_metrics.csv",
    ) -> DestinationMetricSyncResult:
        rows = [dict(row) for row in csv.DictReader(io.StringIO(csv_text))]
        for row in rows:
            row.setdefault("source_file", source_file)
        return DestinationMetricsCollector(self.db).import_rows(
            rows,
            connection=connection,
            campaign_id=campaign_id,
            source="csv",
        )
