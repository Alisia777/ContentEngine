from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
import re

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import models
from app.publishing.destination_service import PublishingDestinationService
from app.publishing.errors import PublishingError
from app.publishing.types import PUBLISHABLE_MEDIA_ARTIFACT_KINDS


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
        if package.organization_id is not None and destination.organization_id != package.organization_id:
            blockers.append("Package and destination must belong to the same organization.")
        media_source = self._validate_media_source(package, blockers)

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
            "media_source": media_source,
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

    def bulk_schedule(
        self,
        *,
        package_ids: list[int],
        destination_ids: list[int],
        start_at: datetime,
        interval_minutes: int = 60,
        operator_name: str | None = None,
        dry_run: bool = False,
    ) -> dict:
        if not package_ids:
            raise PublishingError("At least one package id is required.")
        if not destination_ids:
            raise PublishingError("At least one destination id is required.")
        if interval_minutes < 1:
            raise PublishingError("Interval must be at least 1 minute.")

        created: list[models.PublishingTask] = []
        planned: list[dict] = []
        errors: list[dict] = []
        destinations = [self.db.get(models.PublishingDestination, destination_id) for destination_id in destination_ids]
        for index, package_id in enumerate(package_ids):
            scheduled_at = start_at + timedelta(minutes=index * interval_minutes)
            package = self.db.get(models.PublishingPackage, package_id)
            destination = destinations[index % len(destinations)]
            if not package or not destination:
                errors.append(
                    {
                        "package_id": package_id,
                        "destination_id": destination_ids[index % len(destination_ids)],
                        "scheduled_at": scheduled_at.isoformat(),
                        "error": "Package or destination not found.",
                    }
                )
                continue
            validation = self.validate(package, destination, scheduled_at)
            if not validation["allowed"]:
                errors.append(
                    {
                        "package_id": package.id,
                        "destination_id": destination.id,
                        "scheduled_at": scheduled_at.isoformat(),
                        "error": "; ".join(validation["blockers"]),
                    }
                )
                continue
            planned.append(
                {
                    "package_id": package.id,
                    "destination_id": destination.id,
                    "scheduled_at": scheduled_at.isoformat(),
                }
            )
            if not dry_run:
                task = models.PublishingTask(
                    publishing_package_id=package.id,
                    destination_id=destination.id,
                    platform=destination.platform,
                    status="scheduled",
                    scheduled_at=scheduled_at,
                    operator_name=operator_name,
                    raw_response_json={"schedule_validation": validation, "bulk_schedule": True},
                )
                self.db.add(task)
                created.append(task)
        if not dry_run:
            self.db.commit()
            for task in created:
                self.db.refresh(task)
        return {
            "dry_run": dry_run,
            "planned_count": len(planned),
            "created_count": len(created),
            "error_count": len(errors),
            "task_ids": [task.id for task in created],
            "planned": planned,
            "errors": errors,
        }

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

    def _validate_media_source(
        self,
        package: models.PublishingPackage,
        blockers: list[str],
    ) -> str:
        if package.media_artifact_id is not None:
            artifact = self.db.get(models.MediaArtifact, package.media_artifact_id)
            human_review = (package.metadata_json or {}).get("human_review")
            review_role = (
                str(human_review.get("reviewer_role") or "").casefold()
                if isinstance(human_review, dict)
                else ""
            )
            valid_review = (
                isinstance(human_review, dict)
                and human_review.get("confirmed") is True
                and review_role in {"owner", "admin", "reviewer"}
            )
            if (
                artifact is None
                or package.organization_id is None
                or artifact.organization_id != package.organization_id
                or artifact.product_id != package.product_id
                or artifact.status != "ready"
                or artifact.archived_at is not None
                or artifact.delete_requested_at is not None
                or artifact.deleted_at is not None
                or artifact.kind not in PUBLISHABLE_MEDIA_ARTIFACT_KINDS
                or not str(artifact.mime_type or "").casefold().startswith("video/")
                or int(artifact.size_bytes or 0) <= 0
                or not re.fullmatch(r"[a-f0-9]{64}", str(artifact.sha256 or "").casefold())
                or not artifact.object_key.startswith(
                    f"organizations/{int(package.organization_id or 0):08d}/"
                )
            ):
                blockers.append(
                    "Media artifact must be a ready, non-archived tenant video for this product."
                )
            if not valid_review:
                blockers.append("Media artifact package requires organization-scoped human review.")
            return "media_artifact"

        path = Path(package.video_file_path) if package.video_file_path else None
        if path is None or not path.is_file() or path.stat().st_size <= 0:
            blockers.append("Video file must exist and be non-empty.")
        return "legacy_local_file"

    @staticmethod
    def _day_window(value: datetime) -> tuple[datetime, datetime]:
        start = datetime.combine(value.date(), time.min)
        return start, start + timedelta(days=1)

    @staticmethod
    def _week_window(value: datetime) -> tuple[datetime, datetime]:
        day_start = datetime.combine(value.date(), time.min)
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
