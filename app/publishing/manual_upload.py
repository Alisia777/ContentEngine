from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.publishing.errors import PublishingError


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
        task.status = "published_manual"
        task.final_url = final_url
        task.operator_name = operator_name
        task.error_message = None
        task.raw_response_json = {
            **(task.raw_response_json or {}),
            "published_manual": {
                "operator_name": operator_name,
                "final_url": final_url,
            },
        }
        self.db.commit()
        self.db.refresh(task)
        return task

    @staticmethod
    def payload(task: models.PublishingTask) -> dict:
        package = task.publishing_package
        destination = task.destination
        return {
            "video_file_path": package.video_file_path,
            "title": package.title,
            "description": package.description,
            "hashtags": package.hashtags_json,
            "cta": package.cta,
            "destination": {
                "platform": destination.platform,
                "name": destination.name,
                "handle": destination.handle,
                "url": destination.url,
            },
            "scheduled_at": task.scheduled_at.isoformat(),
        }
