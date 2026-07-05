from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_performance.errors import CampaignPerformanceDataError
from app.campaign_performance.types import CampaignPerformanceSummary


class CampaignPerformanceAggregator:
    def __init__(self, db: Session):
        self.db = db

    def summarize(self, campaign_id: int) -> CampaignPerformanceSummary:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignPerformanceDataError(f"Campaign {campaign_id} not found.")
        metrics = self.db.scalars(
            select(models.CampaignPerformanceMetric)
            .where(models.CampaignPerformanceMetric.campaign_id == campaign_id)
            .order_by(models.CampaignPerformanceMetric.id)
        ).all()
        totals = self._totals(metrics)
        return CampaignPerformanceSummary(
            campaign_id=campaign_id,
            metric_count=len(metrics),
            total_views=totals["views"],
            total_clicks=totals["clicks"],
            total_orders=totals["orders"],
            total_revenue=totals["revenue"],
            total_spend=totals["spend"],
            avg_ctr=self._ratio(totals["clicks"], totals["views"]),
            avg_conversion_rate=self._ratio(totals["orders"], totals["clicks"]),
            avg_engagement_rate=self._ratio(totals["engagements"], totals["views"]),
            by_sku=self._group(metrics, "sku"),
            by_variant=self._group(metrics, "creative_variant_id"),
            by_destination=self._group(metrics, "destination_id"),
            by_platform=self._group(metrics, "platform"),
            published_without_metrics=self.published_without_metrics(campaign_id),
        )

    def published_without_metrics(self, campaign_id: int) -> list[dict[str, Any]]:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            return []
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        tasks = self.db.scalars(
            select(models.PublishingTask)
            .join(models.PublishingPackage)
            .where(
                models.PublishingPackage.product_id.in_(product_ids) if product_ids else False,
                models.PublishingTask.final_url.is_not(None),
            )
            .order_by(models.PublishingTask.id)
        ).all()
        metric_urls = {
            metric.posted_url
            for metric in self.db.scalars(
                select(models.CampaignPerformanceMetric).where(models.CampaignPerformanceMetric.campaign_id == campaign_id)
            ).all()
            if metric.posted_url
        }
        missing = []
        for task in tasks:
            if task.final_url not in metric_urls:
                package = task.publishing_package
                missing.append(
                    {
                        "publishing_task_id": task.id,
                        "posted_url": task.final_url,
                        "sku": package.product.sku if package and package.product else None,
                        "destination_id": task.destination_id,
                    }
                )
        return missing

    def _group(self, metrics: list[models.CampaignPerformanceMetric], field_name: str) -> list[dict[str, Any]]:
        buckets: dict[Any, list[models.CampaignPerformanceMetric]] = defaultdict(list)
        for metric in metrics:
            key = getattr(metric, field_name)
            if key is not None:
                buckets[key].append(metric)
        rows = []
        for key, bucket in buckets.items():
            totals = self._totals(bucket)
            rows.append(
                {
                    "entity_id": str(key),
                    "metric_count": len(bucket),
                    "views": totals["views"],
                    "clicks": totals["clicks"],
                    "orders": totals["orders"],
                    "revenue": totals["revenue"],
                    "spend": totals["spend"],
                    "engagement_rate": self._ratio(totals["engagements"], totals["views"]),
                    "ctr": self._ratio(totals["clicks"], totals["views"]),
                    "conversion_rate": self._ratio(totals["orders"], totals["clicks"]),
                    "cost_per_order": self._ratio(totals["spend"], totals["orders"]),
                    "revenue_per_view": self._ratio(totals["revenue"], totals["views"]),
                }
            )
        return sorted(rows, key=lambda row: (row["views"], row["orders"]), reverse=True)

    @staticmethod
    def _totals(metrics: list[models.CampaignPerformanceMetric]) -> dict[str, float]:
        return {
            "views": sum(metric.views or 0 for metric in metrics),
            "clicks": sum(metric.clicks or 0 for metric in metrics),
            "orders": sum(metric.orders or 0 for metric in metrics),
            "revenue": round(sum(metric.revenue or 0 for metric in metrics), 2),
            "spend": round(sum(metric.spend or 0 for metric in metrics), 2),
            "engagements": sum((metric.likes or 0) + (metric.comments or 0) + (metric.shares or 0) + (metric.saves or 0) for metric in metrics),
        }

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)
