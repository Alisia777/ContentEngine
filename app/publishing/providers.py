from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app import models


class MockUploadProvider:
    def __init__(self, db: Session | None = None):
        self.db = db

    def upload(self, task: models.PublishingTask | dict) -> dict:
        task_id = task.id if hasattr(task, "id") else task.get("id", "local")
        post_id = f"mock-post-{uuid4().hex[:10]}"
        return {
            "status": "published_api",
            "task_id": task_id,
            "provider_post_id": post_id,
            "final_url": f"https://mock.social/posts/{post_id}",
        }
