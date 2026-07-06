from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_crm.errors import DestinationCRMDataError
from app.destination_crm.types import DestinationHealthResult


FAILED_TASK_STATUSES = {"failed", "error", "upload_failed"}
POSTED_TASK_STATUSES = {"published", "done", "manual_uploaded"}


class DestinationHealthService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, destination_id: int) -> DestinationHealthResult:
        destination = self._destination(destination_id)
        tasks = self.db.scalars(
            select(models.PublishingTask)
            .where(models.PublishingTask.destination_id == destination.id)
            .order_by(models.PublishingTask.scheduled_at.desc(), models.PublishingTask.id.desc())
        ).all()
        metrics = self.db.scalars(
            select(models.CampaignPerformanceMetric)
            .where(models.CampaignPerformanceMetric.destination_id == destination.id)
            .order_by(models.CampaignPerformanceMetric.id.desc())
        ).all()
        posted = [task for task in tasks if task.status in POSTED_TASK_STATUSES or task.final_url]
        failed = [task for task in tasks if task.status in FAILED_TASK_STATUSES or task.error_message]
        last_task = posted[0] if posted else None
        avg_views = self._avg([metric.views for metric in metrics if metric.views is not None])
        avg_engagement = self._avg([metric.engagement_rate for metric in metrics if metric.engagement_rate is not None])
        blockers = []
        if failed:
            blockers.append({"blocker": "failed_publishing_tasks", "count": len(failed)})
        if not posted:
            blockers.append({"blocker": "no_posts_recorded"})
        record = models.DestinationHealthCheck(
            destination_id=destination.id,
            status="needs_attention" if blockers else "healthy",
            last_posted_at=last_task.scheduled_at if last_task else None,
            last_final_url=last_task.final_url if last_task else None,
            recent_task_count=len(tasks),
            failed_task_count=len(failed),
            avg_views=avg_views,
            avg_engagement_rate=avg_engagement,
            blockers_json=blockers,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._result(record)

    def refresh_campaign(self, campaign_id: int) -> list[DestinationHealthResult]:
        campaign = self._campaign(campaign_id)
        destinations = self.db.scalars(
            select(models.PublishingDestination)
            .where(models.PublishingDestination.brand == campaign.brand)
            .order_by(models.PublishingDestination.id)
        ).all()
        return [self.refresh(destination.id) for destination in destinations]

    def latest_for_destination(self, destination_id: int) -> DestinationHealthResult | None:
        record = self.db.scalar(
            select(models.DestinationHealthCheck)
            .where(models.DestinationHealthCheck.destination_id == destination_id)
            .order_by(models.DestinationHealthCheck.id.desc())
        )
        return self._result(record) if record else None

    def _destination(self, destination_id: int) -> models.PublishingDestination:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise DestinationCRMDataError(f"Destination {destination_id} not found.")
        return destination

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationCRMDataError(f"Campaign {campaign_id} not found.")
        return campaign

    @staticmethod
    def _avg(values: list[float | int]) -> float:
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    @staticmethod
    def _result(record: models.DestinationHealthCheck) -> DestinationHealthResult:
        return DestinationHealthResult(
            id=record.id,
            destination_id=record.destination_id,
            status=record.status,
            last_posted_at=record.last_posted_at,
            last_final_url=record.last_final_url,
            recent_task_count=record.recent_task_count,
            failed_task_count=record.failed_task_count,
            avg_views=record.avg_views,
            avg_engagement_rate=record.avg_engagement_rate,
            blockers=record.blockers_json or [],
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
