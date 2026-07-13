from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.publishing.errors import PublishingError
from app.publishing.publication_identity import (
    PublicationIdentityError,
    claim_publication_identity,
)


class ManualUploadProvider:
    def __init__(self, db: Session):
        self.db = db

    def run(self, task: models.PublishingTask) -> models.PublishingTask:
        if task.destination.posting_mode == "api" and task.destination.auth_status != "token_valid":
            task.status = "failed"
            task.error_message = "API posting requires configured valid platform credentials."
            self.db.commit()
            self.db.refresh(task)
            return task
        task.status = "manual_upload_required"
        task.raw_response_json = {
            **(task.raw_response_json or {}),
            "manual_upload": self.payload(task),
        }
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_published(self, task: models.PublishingTask, final_url: str, operator_name: str = "operator") -> models.PublishingTask:
        if not final_url:
            raise PublishingError("Final URL is required.")
        try:
            canonical_url = claim_publication_identity(
                self.db,
                task=task,
                final_url=final_url,
            )
        except PublicationIdentityError as exc:
            self.db.rollback()
            raise PublishingError(exc.code) from exc
        task.status = "published_manual"
        task.final_url = canonical_url
        task.operator_name = operator_name
        task.error_message = None
        task.raw_response_json = {
            **(task.raw_response_json or {}),
            "published_manual": {
                "operator_name": operator_name,
                "final_url": canonical_url,
            },
        }
        self.db.commit()
        self.db.refresh(task)
        return task

    def payload(self, task: models.PublishingTask) -> dict:
        package = task.publishing_package
        destination = task.destination
        artifact = (
            self.db.get(models.MediaArtifact, package.media_artifact_id)
            if package.media_artifact_id is not None
            else None
        )
        tracking_link = self.db.scalar(
            select(models.TrackingLink)
            .where(models.TrackingLink.publishing_task_id == task.id)
            .order_by(models.TrackingLink.id.desc())
        )
        warnings = []
        if not tracking_link:
            warnings.append("tracking_link_missing")
        if package.product_url and (not tracking_link or package.product_url == tracking_link.target_url):
            warnings.append("use_tracking_link_in_post_not_direct_product_url")
        return {
            # Durable cloud media is opened through the authorized route. Do
            # not expose an obsolete worker scratch path alongside it.
            "video_file_path": package.video_file_path if artifact is None else None,
            "media_artifact": (
                {
                    "public_id": artifact.public_id,
                    "download_path": f"/media-library/{artifact.public_id}/access?download=true",
                }
                if artifact is not None
                and package.organization_id == artifact.organization_id
                and package.product_id == artifact.product_id
                else None
            ),
            "title": package.title,
            "description": package.description,
            "hashtags": package.hashtags_json,
            "cta": package.cta,
            "tracking_link": f"/r/{tracking_link.slug}" if tracking_link else None,
            "tracking_target_url": tracking_link.target_url if tracking_link else None,
            "warnings": warnings,
            "destination": {
                "platform": destination.platform,
                "name": destination.name,
                "handle": destination.handle,
                "url": destination.url,
            },
            "scheduled_at": task.scheduled_at.isoformat(),
        }
