from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.content_factory.types import ContentStatsImportResult


class ContentStatsImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_csv_text(self, csv_text: str) -> ContentStatsImportResult:
        reader = csv.DictReader(io.StringIO(csv_text))
        imported = 0
        errors: list[str] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                metric = self._metric_from_row(row)
                self.db.add(metric)
                imported += 1
            except (TypeError, ValueError) as exc:
                errors.append(f"row {row_number}: {exc}")
        self.db.commit()
        return ContentStatsImportResult(
            imported_count=imported,
            error_count=len(errors),
            errors=errors,
            imported_at=datetime.now(UTC),
        )

    def _metric_from_row(self, row: dict[str, str]) -> models.ContentPerformanceMetric:
        platform = (row.get("platform") or "").strip()
        if not platform:
            raise ValueError("platform is required")
        sku = (row.get("sku") or "").strip() or None
        product_id = self._int(row.get("product_id"))
        if not product_id and sku:
            product = self.db.scalar(select(models.Product).where(models.Product.sku == sku))
            product_id = product.id if product else None
        views = self._int(row.get("views"))
        impressions = self._int(row.get("impressions"))
        clicks = self._int(row.get("clicks"))
        orders = self._int(row.get("orders"))
        ctr = self._float(row.get("ctr"))
        if ctr is None and clicks is not None:
            denominator = impressions or views or 0
            ctr = round(clicks / denominator, 4) if denominator else None
        conversion_rate = self._float(row.get("conversion_rate"))
        if conversion_rate is None and orders is not None and clicks:
            conversion_rate = round(orders / clicks, 4)
        return models.ContentPerformanceMetric(
            content_run_id=self._int(row.get("content_run_id")),
            product_id=product_id,
            sku=sku,
            platform=platform,
            creative_variant_id=self._int(row.get("creative_variant_id")),
            video_job_id=self._int(row.get("video_job_id")),
            metric_date=self._date(row.get("metric_date")),
            impressions=impressions,
            views=views,
            clicks=clicks,
            orders=orders,
            revenue=self._float(row.get("revenue")),
            spend=self._float(row.get("spend")),
            ctr=ctr,
            conversion_rate=conversion_rate,
            watch_time_seconds=self._float(row.get("watch_time_seconds")),
            retention_rate=self._float(row.get("retention_rate")),
            status="imported",
            raw_json=dict(row),
        )

    @staticmethod
    def _int(value: str | None) -> int | None:
        value = (value or "").strip()
        return int(value) if value else None

    @staticmethod
    def _float(value: str | None) -> float | None:
        value = (value or "").strip().replace(",", ".")
        return float(value) if value else None

    @staticmethod
    def _date(value: str | None) -> date | None:
        value = (value or "").strip()
        return date.fromisoformat(value) if value else None
