from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.errors import MetricsIntakeDataError
from app.metrics_intake.source_registry import MetricsSourceRegistry
from app.metrics_intake.types import MetricsBatchResult


IDENTITY_COLUMNS = {"posted_url", "tracking_slug", "publishing_task_id", "sku", "coupon_code"}


class CSVImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_csv_text(
        self,
        csv_text: str,
        *,
        source_id: int | None = None,
        campaign_id: int | None = None,
        source_type: str = "manual_csv",
        source_name: str | None = None,
    ) -> MetricsBatchResult:
        source = MetricsSourceRegistry(self.db).get(source_id) if source_id else None
        if not csv_text.strip():
            raise MetricsIntakeDataError("CSV text is empty.")
        reader = csv.DictReader(io.StringIO(csv_text))
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: list[str] = []
        for row_number, row in enumerate(reader, start=2):
            clean = {str(key or "").strip(): self._text(value) for key, value in row.items() if key}
            if not any(clean.values()):
                continue
            row_warnings = self._row_warnings(clean)
            warnings.extend(f"row_{row_number}:{warning}" for warning in row_warnings)
            clean["_row_number"] = row_number
            rows.append(clean)
        if not rows:
            errors.append("csv_has_no_data_rows")
        batch = models.MetricsIntakeBatch(
            source_id=source.id if source else None,
            campaign_id=campaign_id,
            source_type=source.source_type if source else source_type,
            status="imported" if not errors else "failed",
            imported_count=len(rows),
            warning_count=len(warnings),
            error_count=len(errors),
            warnings_json=warnings,
            errors_json=errors,
            rows_json=rows,
            unmatched_rows_json=[],
        )
        if source_name and not source:
            batch.source_type = source_type
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return self._result(batch)

    @staticmethod
    def _row_warnings(row: dict[str, str]) -> list[str]:
        warnings: list[str] = []
        if not any(row.get(column) for column in IDENTITY_COLUMNS):
            warnings.append("missing_attribution_identity")
        if not row.get("platform"):
            warnings.append("missing_platform")
        if not row.get("period_start") or not row.get("period_end"):
            warnings.append("missing_period")
        return warnings

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _result(batch: models.MetricsIntakeBatch) -> MetricsBatchResult:
        return MetricsBatchResult(
            batch_id=batch.id,
            source_id=batch.source_id,
            campaign_id=batch.campaign_id,
            source_type=batch.source_type,
            status=batch.status,
            imported_count=batch.imported_count,
            matched_count=batch.matched_count,
            unmatched_count=batch.unmatched_count,
            warning_count=batch.warning_count,
            error_count=batch.error_count,
            warnings=batch.warnings_json or [],
            errors=batch.errors_json or [],
        )
