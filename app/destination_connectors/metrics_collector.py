from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_connectors.types import DestinationMetricSyncResult, DestinationMetricsSummary
from app.publishing.publication_identity import find_task_by_publication_url


class DestinationMetricsCollector:
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
        source: str = "manual",
    ) -> DestinationMetricSyncResult:
        sync = models.DestinationMetricSync(
            destination_id=connection.destination_id if connection else None,
            connection_id=connection.id if connection else None,
            campaign_id=campaign_id,
            status="running",
            period_start=period_start,
            period_end=period_end,
        )
        self.db.add(sync)
        self.db.flush()
        warnings: list[str] = []
        errors: list[str] = []
        imported = 0
        skipped = 0
        first_campaign_id = campaign_id
        first_destination_id = connection.destination_id if connection else None
        for row_number, row in enumerate(rows, start=2):
            try:
                metric, row_warnings, created = self._upsert_destination_metric(
                    row,
                    connection=connection,
                    default_campaign_id=campaign_id,
                    default_period_start=period_start,
                    default_period_end=period_end,
                    source=source,
                )
                if created:
                    imported += 1
                else:
                    skipped += 1
                first_campaign_id = first_campaign_id or metric.campaign_id
                first_destination_id = first_destination_id or metric.destination_id
                if metric.campaign_id:
                    self._upsert_campaign_metric(metric)
                warnings.extend(f"row_{row_number}:{warning}" for warning in row_warnings)
            except (TypeError, ValueError) as exc:
                errors.append(f"row_{row_number}:{exc}")

        sync.destination_id = first_destination_id
        sync.campaign_id = first_campaign_id
        sync.imported_count = imported
        sync.skipped_count = skipped
        sync.error_count = len(errors)
        sync.warnings_json = warnings
        sync.errors_json = errors
        sync.status = "completed"
        if warnings:
            sync.status = "partial"
        if errors and imported == 0 and skipped == 0:
            sync.status = "failed"
        elif errors:
            sync.status = "partial"
        if connection:
            connection.last_sync_at = models.utcnow()
            if sync.status != "failed":
                connection.status = "connected"
                connection.error_message = None
            else:
                connection.status = "error"
                connection.error_message = errors[0] if errors else None
        self.db.commit()
        self.db.refresh(sync)
        return DestinationMetricSyncResult(
            sync_id=sync.id,
            status=sync.status,
            destination_id=sync.destination_id,
            connection_id=sync.connection_id,
            campaign_id=sync.campaign_id,
            period_start=sync.period_start,
            period_end=sync.period_end,
            imported_count=sync.imported_count,
            skipped_count=sync.skipped_count,
            error_count=sync.error_count,
            warnings=sync.warnings_json,
            errors=sync.errors_json,
        )

    def campaign_summary(self, campaign_id: int) -> DestinationMetricsSummary:
        metrics = self.db.scalars(
            select(models.DestinationPostMetric)
            .where(models.DestinationPostMetric.campaign_id == campaign_id)
            .order_by(models.DestinationPostMetric.id)
        ).all()
        by_destination = self._group(metrics, "destination_id")
        by_platform = self._group(metrics, "platform")
        by_sku = self._group(metrics, "sku")
        missing_metrics = []
        for metric in metrics:
            missing = [name for name in ["views", "clicks", "orders"] if getattr(metric, name) is None]
            if missing:
                missing_metrics.append(
                    {
                        "metric_id": metric.id,
                        "posted_url": metric.posted_url,
                        "missing": missing,
                    }
                )
        next_actions = []
        if missing_metrics:
            next_actions.append({"action": "request_missing_metrics", "reason": "some_posts_have_incomplete_metrics"})
        if not metrics:
            next_actions.append({"action": "import_destination_metrics", "reason": "campaign_has_no_destination_metrics"})
        return DestinationMetricsSummary(
            campaign_id=campaign_id,
            metric_count=len(metrics),
            total_views=sum(metric.views or 0 for metric in metrics),
            total_clicks=sum(metric.clicks or 0 for metric in metrics),
            total_orders=sum(metric.orders or 0 for metric in metrics),
            total_revenue=round(sum(metric.revenue or 0 for metric in metrics), 2),
            total_spend=round(sum(metric.spend or 0 for metric in metrics), 2),
            missing_metrics=missing_metrics,
            by_destination=by_destination,
            by_platform=by_platform,
            by_sku=by_sku,
            next_actions=next_actions,
        )

    def _upsert_destination_metric(
        self,
        row: dict[str, Any],
        *,
        connection: models.DestinationConnection | None,
        default_campaign_id: int | None,
        default_period_start: date | None,
        default_period_end: date | None,
        source: str,
    ) -> tuple[models.DestinationPostMetric, list[str], bool]:
        warnings: list[str] = []
        posted_url = self._text(row.get("posted_url")) or None
        provider_post_id = self._text(row.get("provider_post_id")) or None
        platform = self._text(row.get("platform")) or (connection.platform if connection else "")
        if not platform:
            raise ValueError("platform is required")
        task = self._task_by_url(
            posted_url,
            platform=platform,
            destination_id=(connection.destination_id if connection else None),
        )
        if posted_url and not task:
            warnings.append("posted_url_not_matched_to_task")
        if task is not None:
            posted_url = task.final_url
        destination = task.destination if task else (connection.destination if connection else self._destination(row.get("destination_name"), platform))
        campaign_id = self._int(row.get("campaign_id")) or default_campaign_id
        if not campaign_id:
            warnings.append("missing_campaign_id")
        sku = self._text(row.get("sku")) or None
        package = task.publishing_package if task else None
        product = self.db.scalar(select(models.Product).where(models.Product.sku == sku)) if sku else None
        product_id = package.product_id if package else (product.id if product else None)
        period_start = self._date(row.get("period_start")) or default_period_start
        period_end = self._date(row.get("period_end")) or default_period_end
        views = self._int(row.get("views"))
        clicks = self._int(row.get("clicks"))
        orders = self._int(row.get("orders"))
        for name, value in [("views", views), ("clicks", clicks), ("orders", orders)]:
            if value is None:
                warnings.append(f"missing_{name}")
        likes = self._int(row.get("likes"))
        comments = self._int(row.get("comments"))
        shares = self._int(row.get("shares"))
        saves = self._int(row.get("saves"))
        engagement_rate = self._ratio(sum(value or 0 for value in [likes, comments, shares, saves]), views)
        ctr = self._ratio(clicks, views)
        conversion_rate = self._ratio(orders, clicks)
        existing = self._existing_metric(platform, posted_url, period_start, period_end, destination.id if destination else None)
        metric = existing or models.DestinationPostMetric(platform=platform, posted_url=posted_url)
        metric.destination_id = destination.id if destination else None
        metric.connection_id = connection.id if connection else metric.connection_id
        metric.campaign_id = campaign_id
        metric.publishing_task_id = task.id if task else None
        metric.product_id = product_id
        metric.sku = sku or (package.product.sku if package and package.product else None)
        metric.platform = platform
        metric.posted_url = posted_url
        metric.provider_post_id = provider_post_id
        metric.period_start = period_start
        metric.period_end = period_end
        metric.views = views
        metric.likes = likes
        metric.comments = comments
        metric.shares = shares
        metric.saves = saves
        metric.clicks = clicks
        metric.orders = orders
        metric.revenue = self._float(row.get("revenue"))
        metric.spend = self._float(row.get("spend"))
        metric.watch_time_seconds = self._float(row.get("watch_time_seconds"))
        metric.retention_rate = self._float(row.get("retention_rate"))
        metric.engagement_rate = engagement_rate
        metric.ctr = ctr
        metric.conversion_rate = conversion_rate
        metric.raw_json = {**dict(row), "source": source, "warnings": warnings}
        if not existing:
            self.db.add(metric)
            self.db.flush()
        return metric, warnings, existing is None

    def _upsert_campaign_metric(self, metric: models.DestinationPostMetric) -> None:
        existing = self.db.scalar(
            select(models.CampaignPerformanceMetric).where(
                models.CampaignPerformanceMetric.campaign_id == metric.campaign_id,
                models.CampaignPerformanceMetric.platform == metric.platform,
                models.CampaignPerformanceMetric.posted_url == metric.posted_url,
                models.CampaignPerformanceMetric.period_start == metric.period_start,
                models.CampaignPerformanceMetric.period_end == metric.period_end,
            )
        )
        campaign_metric = existing or models.CampaignPerformanceMetric(campaign_id=metric.campaign_id, platform=metric.platform)
        campaign_metric.product_id = metric.product_id
        campaign_metric.sku = metric.sku
        campaign_metric.publishing_task_id = metric.publishing_task_id
        campaign_metric.destination_id = metric.destination_id
        campaign_metric.platform = metric.platform
        campaign_metric.posted_url = metric.posted_url
        campaign_metric.period_start = metric.period_start
        campaign_metric.period_end = metric.period_end
        campaign_metric.views = metric.views
        campaign_metric.likes = metric.likes
        campaign_metric.comments = metric.comments
        campaign_metric.shares = metric.shares
        campaign_metric.saves = metric.saves
        campaign_metric.clicks = metric.clicks
        campaign_metric.orders = metric.orders
        campaign_metric.revenue = metric.revenue
        campaign_metric.spend = metric.spend
        campaign_metric.ctr = metric.ctr
        campaign_metric.conversion_rate = metric.conversion_rate
        campaign_metric.engagement_rate = metric.engagement_rate
        campaign_metric.cost_per_view = self._ratio(metric.spend, metric.views)
        campaign_metric.cost_per_click = self._ratio(metric.spend, metric.clicks)
        campaign_metric.cost_per_order = self._ratio(metric.spend, metric.orders)
        campaign_metric.raw_json = {**(metric.raw_json or {}), "destination_metric_id": metric.id}
        if not existing:
            self.db.add(campaign_metric)

    def _existing_metric(
        self,
        platform: str,
        posted_url: str | None,
        period_start: date | None,
        period_end: date | None,
        destination_id: int | None,
    ) -> models.DestinationPostMetric | None:
        query = select(models.DestinationPostMetric).where(
            models.DestinationPostMetric.platform == platform,
            models.DestinationPostMetric.posted_url == posted_url,
            models.DestinationPostMetric.period_start == period_start,
            models.DestinationPostMetric.period_end == period_end,
        )
        if destination_id:
            query = query.where(models.DestinationPostMetric.destination_id == destination_id)
        return self.db.scalar(query)

    def _task_by_url(
        self,
        posted_url: str | None,
        *,
        platform: str | None = None,
        destination_id: int | None = None,
    ) -> models.PublishingTask | None:
        return find_task_by_publication_url(
            self.db,
            posted_url,
            platform=platform,
            destination_id=destination_id,
        )

    def _destination(self, name: Any, platform: str) -> models.PublishingDestination | None:
        destination_name = self._text(name)
        if not destination_name:
            return None
        return self.db.scalar(
            select(models.PublishingDestination).where(
                models.PublishingDestination.name == destination_name,
                models.PublishingDestination.platform == platform,
            )
        )

    @staticmethod
    def _group(metrics: list[models.DestinationPostMetric], field_name: str) -> list[dict[str, Any]]:
        buckets: dict[Any, list[models.DestinationPostMetric]] = defaultdict(list)
        for metric in metrics:
            buckets[getattr(metric, field_name) or "unknown"].append(metric)
        rows = []
        for entity_id, items in buckets.items():
            rows.append(
                {
                    "entity_id": entity_id,
                    "metric_count": len(items),
                    "views": sum(item.views or 0 for item in items),
                    "clicks": sum(item.clicks or 0 for item in items),
                    "orders": sum(item.orders or 0 for item in items),
                    "revenue": round(sum(item.revenue or 0 for item in items), 2),
                    "engagement_rate": DestinationMetricsCollector._avg([item.engagement_rate for item in items]),
                    "ctr": DestinationMetricsCollector._avg([item.ctr for item in items]),
                }
            )
        return sorted(rows, key=lambda row: str(row["entity_id"]))

    @staticmethod
    def _avg(values: list[float | None]) -> float | None:
        clean = [value for value in values if value is not None]
        return round(sum(clean) / len(clean), 4) if clean else None

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _int(value: Any) -> int | None:
        text = str(value or "").strip()
        return int(float(text.replace(",", "."))) if text else None

    @staticmethod
    def _float(value: Any) -> float | None:
        text = str(value or "").strip().replace(",", ".")
        return float(text) if text else None

    @staticmethod
    def _date(value: Any) -> date | None:
        text = str(value or "").strip()
        return date.fromisoformat(text) if text else None

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)
