from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.providers.upload import MockUploadProvider


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
        self.provider = MockUploadProvider()

    def collect_for_job(self, job: models.PublishingJob) -> models.PublishAnalytics:
        provider_post_id = job.provider_post_id or f"manual-{job.id}"
        metrics = self.provider.collect_analytics(provider_post_id)
        analytics = models.PublishAnalytics(
            publishing_job_id=job.id,
            views=metrics["views"],
            likes=metrics["likes"],
            comments=metrics["comments"],
            shares=metrics["shares"],
            saves=metrics["saves"],
            clicks=metrics["clicks"],
            ctr=metrics["ctr"],
            raw_metrics_json=metrics["raw_metrics_json"],
        )
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        return analytics

    def by_product(self, product_id: int) -> list[models.PublishAnalytics]:
        return self.db.scalars(
            select(models.PublishAnalytics)
            .join(models.PublishingJob)
            .join(models.PublishingPackage)
            .where(models.PublishingPackage.product_id == product_id)
            .order_by(models.PublishAnalytics.collected_at.desc())
        ).all()

    def by_account(self, account_id: int) -> list[models.PublishAnalytics]:
        return self.db.scalars(
            select(models.PublishAnalytics)
            .join(models.PublishingJob)
            .where(models.PublishingJob.account_id == account_id)
            .order_by(models.PublishAnalytics.collected_at.desc())
        ).all()

