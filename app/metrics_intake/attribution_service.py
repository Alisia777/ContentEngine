from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.errors import MetricsIntakeDataError
from app.metrics_intake.funnel_service import FunnelService
from app.metrics_intake.types import AttributionResult


class AttributionService:
    def __init__(self, db: Session):
        self.db = db

    def attribute_batch(self, batch_id: int) -> AttributionResult:
        batch = self.db.get(models.MetricsIntakeBatch, batch_id)
        if not batch:
            raise MetricsIntakeDataError(f"Metrics intake batch {batch_id} not found.")
        matched = 0
        unmatched: list[dict[str, Any]] = []
        warnings = list(batch.warnings_json or [])
        destination_metric_ids: list[int] = []
        funnel_snapshot_ids: list[int] = []
        for row in batch.rows_json or []:
            match = self._match(row, default_campaign_id=batch.campaign_id)
            if not match["matched"]:
                row_copy = dict(row)
                row_copy["warning"] = match["reason"]
                unmatched.append(row_copy)
                warnings.append(f"row_{row.get('_row_number', '?')}:{match['reason']}")
                continue
            metric = self._upsert_destination_metric(row, match, batch)
            destination_metric_ids.append(metric.id)
            snapshot = self._create_funnel_snapshot(row, match, metric, batch)
            funnel_snapshot_ids.append(snapshot.id)
            matched += 1

        batch.matched_count = matched
        batch.unmatched_count = len(unmatched)
        batch.warning_count = len(warnings)
        batch.warnings_json = warnings
        batch.unmatched_rows_json = unmatched
        batch.status = "attributed"
        if unmatched and matched:
            batch.status = "partial"
        elif unmatched and not matched:
            batch.status = "unmatched"
        self.db.commit()
        self.db.refresh(batch)
        return AttributionResult(
            batch_id=batch.id,
            status=batch.status,
            matched_count=batch.matched_count,
            unmatched_count=batch.unmatched_count,
            warning_count=batch.warning_count,
            destination_metric_ids=destination_metric_ids,
            funnel_snapshot_ids=funnel_snapshot_ids,
            unmatched_rows=unmatched,
        )

    def _match(self, row: dict[str, Any], *, default_campaign_id: int | None) -> dict[str, Any]:
        task = self._task_by_id(row.get("publishing_task_id"))
        link = None
        match_method = "publishing_task_id" if task else None
        if not task:
            link = self._tracking_link(row.get("tracking_slug"))
            task = link.publishing_task if link else None
            if link:
                match_method = "tracking_slug"
        if not task:
            task = self._task_by_url(row.get("posted_url"))
            if task:
                match_method = "final_url"
        destination = task.destination if task else None
        if not destination:
            destination = self._destination_by_handle(row.get("destination_handle"), row.get("platform"))
        product = self._product(row.get("sku"))
        if task and task.publishing_package:
            product = task.publishing_package.product or product
        if not task and destination and product:
            task = self._task_by_destination_sku(destination.id, product.sku)
            if task:
                match_method = "destination_sku_period"
        assignment = self._assignment(task.id if task else None, destination.id if destination else None)
        campaign_id = (
            self._int(row.get("campaign_id"))
            or default_campaign_id
            or (link.campaign_id if link else None)
            or (assignment.campaign_id if assignment else None)
        )
        if not campaign_id and product:
            campaign_id = self._campaign_by_product(product.id)
        if not destination and link:
            destination = link.destination
        if not product and link and link.product_id:
            product = self.db.get(models.Product, link.product_id)
        participant_id = (
            self._int(row.get("participant_id"))
            or (link.participant_id if link else None)
            or (assignment.participant_id if assignment else None)
            or self._participant_for_destination(destination.id if destination else None)
        )
        creative_variant_id = (
            self._int(row.get("creative_variant_id"))
            or (link.creative_variant_id if link else None)
            or (task.publishing_package.creative_variant_id if task and task.publishing_package else None)
        )
        if not task and not link and not (destination and product and campaign_id):
            return {"matched": False, "reason": "unmatched_metrics_row"}
        return {
            "matched": True,
            "tracking_link": link,
            "task": task,
            "destination": destination,
            "product": product,
            "campaign_id": campaign_id,
            "participant_id": participant_id,
            "creative_variant_id": creative_variant_id,
            "match_method": match_method or "manual_mapping",
            "match_confidence": self._match_confidence(match_method),
        }

    def _upsert_destination_metric(
        self,
        row: dict[str, Any],
        match: dict[str, Any],
        batch: models.MetricsIntakeBatch,
    ) -> models.DestinationPostMetric:
        task: models.PublishingTask | None = match["task"]
        link: models.TrackingLink | None = match["tracking_link"]
        destination: models.PublishingDestination | None = match["destination"]
        product: models.Product | None = match["product"]
        platform = self._text(row.get("platform")) or (task.platform if task else (destination.platform if destination else "other"))
        posted_url = self._text(row.get("posted_url")) or (task.final_url if task else None)
        period_start = self._date(row.get("period_start"))
        period_end = self._date(row.get("period_end"))
        existing = self._existing_metric(platform, posted_url, period_start, period_end, destination.id if destination else None)
        metric = existing or models.DestinationPostMetric(platform=platform, posted_url=posted_url)
        views = self._int(row.get("views")) or 0
        clicks = self._int(row.get("clicks")) or self._click_count(link.id if link else None, period_start, period_end)
        orders = self._int(row.get("orders")) or 0
        likes = self._int(row.get("likes")) or 0
        comments = self._int(row.get("comments")) or 0
        shares = self._int(row.get("shares")) or 0
        saves = self._int(row.get("saves")) or 0
        spend = self._float(row.get("spend"))
        metric.destination_id = destination.id if destination else None
        metric.connection_id = batch.source.connection_id if batch.source else None
        metric.campaign_id = match["campaign_id"]
        metric.publishing_task_id = task.id if task else (link.publishing_task_id if link else None)
        metric.product_id = product.id if product else (link.product_id if link else None)
        metric.sku = self._text(row.get("sku")) or (product.sku if product else (link.sku if link else None))
        metric.platform = platform
        metric.posted_url = posted_url
        metric.provider_post_id = self._text(row.get("provider_post_id")) or None
        metric.period_start = period_start
        metric.period_end = period_end
        metric.views = views
        metric.likes = likes
        metric.comments = comments
        metric.shares = shares
        metric.saves = saves
        metric.clicks = clicks
        metric.orders = orders
        metric.revenue = self._float(row.get("revenue")) or 0
        metric.spend = spend
        metric.engagement_rate = self._ratio(likes + comments + shares + saves, views)
        metric.ctr = self._ratio(clicks, views)
        metric.conversion_rate = self._ratio(orders, clicks)
        metric.raw_json = {
            **dict(row),
            "source": "metrics_intake",
            "batch_id": batch.id,
            "tracking_link_id": link.id if link else None,
            "match_method": match["match_method"],
            "match_confidence": match["match_confidence"],
            "source_type": batch.source_type,
            "warnings": row.get("warnings") or [],
            "reach": self._int(row.get("reach")) or 0,
            "impressions": self._int(row.get("impressions")) or 0,
        }
        metric.raw_json["match_confidence"] = match["match_confidence"]
        if not existing:
            self.db.add(metric)
            self.db.flush()
        return metric

    def _create_funnel_snapshot(
        self,
        row: dict[str, Any],
        match: dict[str, Any],
        metric: models.DestinationPostMetric,
        batch: models.MetricsIntakeBatch,
    ) -> models.FunnelSnapshot:
        return FunnelService(self.db).build_snapshot(
            campaign_id=metric.campaign_id,
            product_id=metric.product_id,
            sku=metric.sku,
            creative_variant_id=match["creative_variant_id"],
            destination_id=metric.destination_id,
            participant_id=match["participant_id"],
            period_start=metric.period_start,
            period_end=metric.period_end,
            views=metric.views or 0,
            reach=self._int(row.get("reach")) or 0,
            impressions=self._int(row.get("impressions")) or 0,
            likes=metric.likes or 0,
            comments=metric.comments or 0,
            shares=metric.shares or 0,
            saves=metric.saves or 0,
            clicks=metric.clicks or 0,
            orders=metric.orders or 0,
            revenue=metric.revenue or 0,
            returns_count=self._int(row.get("returns_count")) or 0,
            raw={
                "metrics_intake_batch_id": batch.id,
                "destination_metric_id": metric.id,
                "match_method": match["match_method"],
                "match_confidence": match["match_confidence"],
                "source_type": batch.source_type,
                **dict(row),
            },
            platform=metric.platform,
            posted_url=metric.posted_url,
            publishing_task_id=metric.publishing_task_id,
            spend=metric.spend,
        )

    def _task_by_id(self, value: Any) -> models.PublishingTask | None:
        task_id = self._int(value)
        return self.db.get(models.PublishingTask, task_id) if task_id else None

    def _tracking_link(self, slug: Any) -> models.TrackingLink | None:
        text = self._text(slug)
        if not text:
            return None
        return self.db.scalar(select(models.TrackingLink).where(models.TrackingLink.slug == text))

    def _task_by_url(self, posted_url: Any) -> models.PublishingTask | None:
        text = self._text(posted_url)
        if not text:
            return None
        return self.db.scalar(select(models.PublishingTask).where(models.PublishingTask.final_url == text))

    def _destination_by_handle(self, handle: Any, platform: Any) -> models.PublishingDestination | None:
        text = self._text(handle)
        if not text:
            return None
        query = select(models.PublishingDestination).where(
            or_(models.PublishingDestination.handle == text, models.PublishingDestination.name == text)
        )
        platform_text = self._text(platform)
        if platform_text:
            query = query.where(models.PublishingDestination.platform == platform_text)
        return self.db.scalar(query.order_by(models.PublishingDestination.id.desc()))

    def _product(self, sku: Any) -> models.Product | None:
        text = self._text(sku)
        if not text:
            return None
        return self.db.scalar(select(models.Product).where(models.Product.sku == text))

    def _task_by_destination_sku(self, destination_id: int, sku: str) -> models.PublishingTask | None:
        tasks = self.db.scalars(
            select(models.PublishingTask)
            .where(models.PublishingTask.destination_id == destination_id)
            .order_by(models.PublishingTask.id.desc())
        ).all()
        for task in tasks:
            package = task.publishing_package
            if package and package.product and package.product.sku == sku:
                return task
        return None

    def _assignment(self, task_id: int | None, destination_id: int | None) -> models.ParticipantAssignment | None:
        if task_id:
            assignment = self.db.scalar(
                select(models.ParticipantAssignment)
                .where(models.ParticipantAssignment.publishing_task_id == task_id)
                .order_by(models.ParticipantAssignment.id.desc())
            )
            if assignment:
                return assignment
        if destination_id:
            link = self.db.scalar(
                select(models.ParticipantDestinationLink)
                .where(
                    models.ParticipantDestinationLink.destination_id == destination_id,
                    models.ParticipantDestinationLink.status == "active",
                )
                .order_by(models.ParticipantDestinationLink.id.desc())
            )
            if link:
                return self.db.scalar(
                    select(models.ParticipantAssignment)
                    .where(models.ParticipantAssignment.participant_id == link.participant_id)
                    .order_by(models.ParticipantAssignment.id.desc())
                )
        return None

    def _participant_for_destination(self, destination_id: int | None) -> int | None:
        if not destination_id:
            return None
        link = self.db.scalar(
            select(models.ParticipantDestinationLink)
            .where(
                models.ParticipantDestinationLink.destination_id == destination_id,
                models.ParticipantDestinationLink.status == "active",
            )
            .order_by(models.ParticipantDestinationLink.id.desc())
        )
        return link.participant_id if link else None

    def _campaign_by_product(self, product_id: int) -> int | None:
        for campaign in self.db.scalars(select(models.Campaign).order_by(models.Campaign.id.desc())).all():
            if product_id in (campaign.product_ids_json or []):
                return campaign.id
        return None

    def _click_count(self, tracking_link_id: int | None, period_start: date | None, period_end: date | None) -> int:
        if not tracking_link_id:
            return 0
        query = select(models.TrackingClick).where(models.TrackingClick.tracking_link_id == tracking_link_id)
        if period_start:
            query = query.where(models.TrackingClick.clicked_at >= period_start)
        if period_end:
            query = query.where(models.TrackingClick.clicked_at <= period_end)
        return len(self.db.scalars(query).all())

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

    @staticmethod
    def _match_confidence(match_method: str | None) -> float:
        if match_method in {"publishing_task_id", "tracking_slug"}:
            return 1.0
        if match_method == "final_url":
            return 0.95
        if match_method == "destination_sku_period":
            return 0.65
        return 0.5
