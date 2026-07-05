from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_performance.errors import CampaignPerformanceDataError
from app.campaign_performance.types import PerformanceImportResult


class CampaignMetricsImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_csv_text(self, campaign_id: int, csv_text: str, *, source_file: str = "campaign_performance.csv") -> PerformanceImportResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignPerformanceDataError(f"Campaign {campaign_id} not found.")
        record = models.CampaignPerformanceImport(campaign_id=campaign_id, source_file=source_file, status="importing")
        self.db.add(record)
        self.db.flush()
        imported = 0
        warnings: list[str] = []
        errors: list[str] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for row_number, row in enumerate(reader, start=2):
            try:
                metric, row_warnings = self._metric_from_row(campaign, row)
                self.db.add(metric)
                self._mirror_content_metric(metric)
                imported += 1
                warnings.extend(f"row_{row_number}:{warning}" for warning in row_warnings)
            except (TypeError, ValueError) as exc:
                errors.append(f"row_{row_number}:{exc}")
        record.imported_count = imported
        record.error_count = len(errors)
        record.warnings_json = warnings
        record.errors_json = errors
        record.status = "imported_with_warnings" if warnings else "imported"
        if errors and not imported:
            record.status = "failed"
        elif errors:
            record.status = "imported_with_errors"
        self.db.commit()
        self.db.refresh(record)
        return PerformanceImportResult(
            import_id=record.id,
            campaign_id=campaign_id,
            status=record.status,
            imported_count=imported,
            error_count=len(errors),
            warnings=warnings,
            errors=errors,
        )

    def _metric_from_row(self, campaign: models.Campaign, row: dict[str, str]) -> tuple[models.CampaignPerformanceMetric, list[str]]:
        warnings: list[str] = []
        sku = self._text(row.get("sku")) or None
        platform = self._text(row.get("platform"))
        posted_url = self._text(row.get("posted_url")) or None
        if not platform:
            raise ValueError("platform is required")
        task = self._task_by_url(posted_url)
        if posted_url and not task:
            warnings.append("posted_url_not_matched_to_task")
        package = task.publishing_package if task else None
        destination = task.destination if task else self._destination_by_name(row.get("destination_name"))
        product = self.db.scalar(select(models.Product).where(models.Product.sku == sku)) if sku else None
        product_id = package.product_id if package else (product.id if product else None)
        if sku and not product_id:
            warnings.append("sku_not_matched_to_product")
        content_run_id = self._content_run_id(product_id, self._int(row.get("creative_variant_id")))
        views = self._int(row.get("views"))
        clicks = self._int(row.get("clicks"))
        orders = self._int(row.get("orders"))
        for metric_name, metric_value in [("views", views), ("clicks", clicks), ("orders", orders)]:
            if metric_value is None:
                warnings.append(f"missing_{metric_name}")
        likes = self._int(row.get("likes")) or 0
        comments = self._int(row.get("comments")) or 0
        shares = self._int(row.get("shares")) or 0
        saves = self._int(row.get("saves")) or 0
        revenue = self._float(row.get("revenue"))
        spend = self._float(row.get("spend"))
        ctr = self._ratio(clicks, views)
        conversion_rate = self._ratio(orders, clicks)
        engagement_rate = self._ratio(likes + comments + shares + saves, views)
        return (
            models.CampaignPerformanceMetric(
                campaign_id=campaign.id,
                product_id=product_id,
                sku=sku,
                content_run_id=content_run_id,
                creative_variant_id=self._int(row.get("creative_variant_id")) or (package.creative_variant_id if package else None),
                publishing_task_id=task.id if task else None,
                destination_id=destination.id if destination else None,
                platform=platform,
                posted_url=posted_url,
                period_start=self._date(row.get("period_start")),
                period_end=self._date(row.get("period_end")),
                views=views,
                likes=likes,
                comments=comments,
                shares=shares,
                saves=saves,
                clicks=clicks,
                orders=orders,
                revenue=revenue,
                spend=spend,
                ctr=ctr,
                conversion_rate=conversion_rate,
                engagement_rate=engagement_rate,
                cost_per_view=self._ratio(spend, views),
                cost_per_click=self._ratio(spend, clicks),
                cost_per_order=self._ratio(spend, orders),
                raw_json={**dict(row), "warnings": warnings},
            ),
            warnings,
        )

    def _mirror_content_metric(self, metric: models.CampaignPerformanceMetric) -> None:
        self.db.add(
            models.ContentPerformanceMetric(
                content_run_id=metric.content_run_id,
                product_id=metric.product_id,
                sku=metric.sku,
                platform=metric.platform,
                creative_variant_id=metric.creative_variant_id,
                metric_date=metric.period_end,
                views=metric.views,
                clicks=metric.clicks,
                orders=metric.orders,
                revenue=metric.revenue,
                spend=metric.spend,
                ctr=metric.ctr,
                conversion_rate=metric.conversion_rate,
                status="imported_from_campaign_performance",
                raw_json=metric.raw_json,
            )
        )

    def _task_by_url(self, posted_url: str | None) -> models.PublishingTask | None:
        if not posted_url:
            return None
        return self.db.scalar(select(models.PublishingTask).where(models.PublishingTask.final_url == posted_url))

    def _destination_by_name(self, value: str | None) -> models.PublishingDestination | None:
        name = self._text(value)
        if not name:
            return None
        return self.db.scalar(select(models.PublishingDestination).where(models.PublishingDestination.name == name))

    def _content_run_id(self, product_id: int | None, creative_variant_id: int | None) -> int | None:
        query = select(models.ContentRun).order_by(models.ContentRun.id.desc())
        if creative_variant_id:
            run = self.db.scalar(query.where(models.ContentRun.selected_variant_id == creative_variant_id))
            if run:
                return run.id
        if product_id:
            run = self.db.scalar(query.where(models.ContentRun.product_id == product_id))
            return run.id if run else None
        return None

    @staticmethod
    def _text(value: str | None) -> str:
        return (value or "").strip()

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

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)
