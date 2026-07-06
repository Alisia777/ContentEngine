from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


class FunnelService:
    def __init__(self, db: Session):
        self.db = db

    def build_snapshot(
        self,
        *,
        campaign_id: int | None,
        product_id: int | None,
        sku: str | None,
        creative_variant_id: int | None,
        destination_id: int | None,
        participant_id: int | None,
        period_start: date | None,
        period_end: date | None,
        views: int,
        reach: int,
        impressions: int,
        likes: int,
        comments: int,
        shares: int,
        saves: int,
        clicks: int,
        orders: int,
        revenue: float,
        returns_count: int = 0,
        raw: dict[str, Any] | None = None,
        platform: str | None = None,
        posted_url: str | None = None,
        publishing_task_id: int | None = None,
        spend: float | None = None,
    ) -> models.FunnelSnapshot:
        engagements = likes + comments + shares + saves
        snapshot = models.FunnelSnapshot(
            campaign_id=campaign_id,
            product_id=product_id,
            sku=sku,
            creative_variant_id=creative_variant_id,
            destination_id=destination_id,
            participant_id=participant_id,
            period_start=period_start,
            period_end=period_end,
            views=views,
            reach=reach,
            impressions=impressions,
            engagements=engagements,
            clicks=clicks,
            orders=orders,
            revenue=round(revenue, 2),
            returns_count=returns_count,
            ctr=self._ratio(clicks, views),
            conversion_rate=self._ratio(orders, clicks),
            revenue_per_view=self._ratio(revenue, views),
            revenue_per_click=self._ratio(revenue, clicks),
            raw_json=raw or {},
        )
        self.db.add(snapshot)
        self.db.flush()
        if campaign_id:
            self._upsert_campaign_metric(
                snapshot,
                platform=platform or "other",
                posted_url=posted_url,
                publishing_task_id=publishing_task_id,
                likes=likes,
                comments=comments,
                shares=shares,
                saves=saves,
                spend=spend,
            )
        self.db.commit()
        self.db.refresh(snapshot)
        self._refresh_participant(snapshot)
        return snapshot

    def campaign_funnel(self, campaign_id: int) -> dict[str, Any]:
        snapshots = self.db.scalars(
            select(models.FunnelSnapshot)
            .where(models.FunnelSnapshot.campaign_id == campaign_id)
            .order_by(models.FunnelSnapshot.id)
        ).all()
        totals = {
            "views": sum(item.views or 0 for item in snapshots),
            "reach": sum(item.reach or 0 for item in snapshots),
            "impressions": sum(item.impressions or 0 for item in snapshots),
            "engagements": sum(item.engagements or 0 for item in snapshots),
            "clicks": sum(item.clicks or 0 for item in snapshots),
            "orders": sum(item.orders or 0 for item in snapshots),
            "revenue": round(sum(item.revenue or 0 for item in snapshots), 2),
        }
        totals["ctr"] = self._ratio(totals["clicks"], totals["views"])
        totals["conversion_rate"] = self._ratio(totals["orders"], totals["clicks"])
        totals["revenue_per_view"] = self._ratio(totals["revenue"], totals["views"])
        totals["revenue_per_click"] = self._ratio(totals["revenue"], totals["clicks"])
        return {
            "campaign_id": campaign_id,
            "snapshot_count": len(snapshots),
            "totals": totals,
            "snapshots": [self.snapshot_payload(item) for item in snapshots],
        }

    def unmatched_rows(self, campaign_id: int | None = None) -> list[dict[str, Any]]:
        query = select(models.MetricsIntakeBatch).order_by(models.MetricsIntakeBatch.id.desc())
        if campaign_id:
            query = query.where(models.MetricsIntakeBatch.campaign_id == campaign_id)
        rows: list[dict[str, Any]] = []
        for batch in self.db.scalars(query).all():
            for row in batch.unmatched_rows_json or []:
                rows.append({"batch_id": batch.id, **row})
        return rows

    @staticmethod
    def snapshot_payload(snapshot: models.FunnelSnapshot) -> dict[str, Any]:
        return {
            "id": snapshot.id,
            "campaign_id": snapshot.campaign_id,
            "product_id": snapshot.product_id,
            "sku": snapshot.sku,
            "creative_variant_id": snapshot.creative_variant_id,
            "destination_id": snapshot.destination_id,
            "participant_id": snapshot.participant_id,
            "period_start": snapshot.period_start.isoformat() if snapshot.period_start else None,
            "period_end": snapshot.period_end.isoformat() if snapshot.period_end else None,
            "views": snapshot.views,
            "reach": snapshot.reach,
            "impressions": snapshot.impressions,
            "engagements": snapshot.engagements,
            "clicks": snapshot.clicks,
            "orders": snapshot.orders,
            "revenue": snapshot.revenue,
            "ctr": snapshot.ctr,
            "conversion_rate": snapshot.conversion_rate,
            "revenue_per_view": snapshot.revenue_per_view,
            "revenue_per_click": snapshot.revenue_per_click,
        }

    def _upsert_campaign_metric(
        self,
        snapshot: models.FunnelSnapshot,
        *,
        platform: str,
        posted_url: str | None,
        publishing_task_id: int | None,
        likes: int,
        comments: int,
        shares: int,
        saves: int,
        spend: float | None,
    ) -> None:
        existing = self.db.scalar(
            select(models.CampaignPerformanceMetric).where(
                models.CampaignPerformanceMetric.campaign_id == snapshot.campaign_id,
                models.CampaignPerformanceMetric.platform == platform,
                models.CampaignPerformanceMetric.posted_url == posted_url,
                models.CampaignPerformanceMetric.period_start == snapshot.period_start,
                models.CampaignPerformanceMetric.period_end == snapshot.period_end,
            )
        )
        metric = existing or models.CampaignPerformanceMetric(campaign_id=snapshot.campaign_id, platform=platform)
        metric.product_id = snapshot.product_id
        metric.sku = snapshot.sku
        metric.creative_variant_id = snapshot.creative_variant_id
        metric.publishing_task_id = publishing_task_id
        metric.destination_id = snapshot.destination_id
        metric.platform = platform
        metric.posted_url = posted_url
        metric.period_start = snapshot.period_start
        metric.period_end = snapshot.period_end
        metric.views = snapshot.views
        metric.likes = likes
        metric.comments = comments
        metric.shares = shares
        metric.saves = saves
        metric.clicks = snapshot.clicks
        metric.orders = snapshot.orders
        metric.revenue = snapshot.revenue
        metric.spend = spend
        metric.ctr = snapshot.ctr
        metric.conversion_rate = snapshot.conversion_rate
        metric.engagement_rate = self._ratio(snapshot.engagements, snapshot.views)
        metric.cost_per_view = self._ratio(spend, snapshot.views)
        metric.cost_per_click = self._ratio(spend, snapshot.clicks)
        metric.cost_per_order = self._ratio(spend, snapshot.orders)
        metric.raw_json = {**(snapshot.raw_json or {}), "funnel_snapshot_id": snapshot.id}
        if not existing:
            self.db.add(metric)

    def _refresh_participant(self, snapshot: models.FunnelSnapshot) -> None:
        if not snapshot.participant_id or not snapshot.campaign_id:
            return
        try:
            from app.participant_portal.participant_metrics_service import ParticipantMetricsService

            ParticipantMetricsService(self.db).refresh(snapshot.participant_id, campaign_id=snapshot.campaign_id)
        except Exception:
            # Metrics intake should not fail because downstream dashboards are not ready.
            self.db.rollback()

    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round(float(numerator) / float(denominator), 4)
