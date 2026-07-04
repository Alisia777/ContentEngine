from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import models
from app.publishing.destination_service import PublishingDestinationService
from app.publishing.errors import PublishingError


class PublishingScheduler:
    COUNTED_STATUSES = {"scheduled", "manual_upload_required", "published_manual", "published_api"}

    def __init__(self, db: Session):
        self.db = db

    def validate(
        self,
        package: models.PublishingPackage,
        destination: models.PublishingDestination,
        scheduled_at: datetime,
    ) -> dict:
        blockers: list[str] = []
        readiness = PublishingDestinationService(self.db).readiness(destination)
        blockers.extend(readiness.blockers)
        if package.status != "approved":
            blockers.append("PublishingPackage must be approved before scheduling.")
        if package.review_status != "approved":
            blockers.append("PublishingPackage review_status must be approved before scheduling.")
        if package.target_platform.lower() != destination.platform.lower():
            blockers.append("Package platform must match destination platform.")
        if package.brand != destination.brand:
            blockers.append("Package brand must match destination brand.")
        if not package.video_file_path or not Path(package.video_file_path).exists() or Path(package.video_file_path).stat().st_size <= 0:
            blockers.append("Video file must exist and be non-empty.")

        day_count = self._count(destination.id, self._day_window(scheduled_at))
        week_count = self._count(destination.id, self._week_window(scheduled_at))
        if day_count >= destination.daily_limit:
            blockers.append(f"Daily publishing limit reached: {day_count}/{destination.daily_limit}.")
        if week_count >= destination.weekly_limit:
            blockers.append(f"Weekly publishing limit reached: {week_count}/{destination.weekly_limit}.")
        return {
            "allowed": not blockers,
            "blockers": blockers,
            "warnings": readiness.warnings,
            "daily_count": day_count,
            "weekly_count": week_count,
            "daily_limit": destination.daily_limit,
            "weekly_limit": destination.weekly_limit,
        }

    def schedule(
        self,
        *,
        package: models.PublishingPackage,
        destination: models.PublishingDestination,
        scheduled_at: datetime,
        operator_name: str | None = None,
    ) -> models.PublishingTask:
        validation = self.validate(package, destination, scheduled_at)
        if not validation["allowed"]:
            raise PublishingError("; ".join(validation["blockers"]))
        task = models.PublishingTask(
            publishing_package_id=package.id,
            destination_id=destination.id,
            platform=destination.platform,
            status="scheduled",
            scheduled_at=scheduled_at,
            operator_name=operator_name,
            raw_response_json={"schedule_validation": validation},
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def calendar(self) -> list[models.PublishingTask]:
        return self.db.scalars(select(models.PublishingTask).order_by(models.PublishingTask.scheduled_at)).all()

    def _count(self, destination_id: int, window: tuple[datetime, datetime]) -> int:
        start, end = window
        return (
            self.db.scalar(
                select(func.count())
                .select_from(models.PublishingTask)
                .where(
                    and_(
                        models.PublishingTask.destination_id == destination_id,
                        models.PublishingTask.scheduled_at >= start,
                        models.PublishingTask.scheduled_at < end,
                        models.PublishingTask.status.in_(self.COUNTED_STATUSES),
                    )
                )
            )
            or 0
        )

    @staticmethod
    def _day_window(value: datetime) -> tuple[datetime, datetime]:
        start = datetime.combine(value.date(), time.min)
        return start, start + timedelta(days=1)

    @staticmethod
    def _week_window(value: datetime) -> tuple[datetime, datetime]:
        day_start = datetime.combine(value.date(), time.min)
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
