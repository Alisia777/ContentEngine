from __future__ import annotations

from random import Random
from uuid import uuid4


class MockUploadProvider:
    def validate_package(self, publishing_package: dict, account: dict) -> dict:
        errors = []
        if not publishing_package.get("video_file_path"):
            errors.append("Video file path is missing")
        if publishing_package.get("brand") != account.get("brand"):
            errors.append("Package brand does not match account brand")
        return {"valid": not errors, "errors": errors}

    def upload_or_schedule(self, publishing_job: dict) -> dict:
        post_id = f"mock-post-{uuid4().hex[:10]}"
        return {
            "status": "published",
            "transition_history": ["queued", "uploading", "published"],
            "provider_post_id": post_id,
            "provider_post_url": f"https://mock.social/posts/{post_id}",
            "message": "MockUploadProvider published the package locally.",
        }

    def get_status(self, provider_post_id: str) -> dict:
        return {"provider_post_id": provider_post_id, "status": "published"}

    def collect_analytics(self, provider_post_id: str) -> dict:
        seed = sum(ord(char) for char in provider_post_id)
        rng = Random(seed)
        views = rng.randint(800, 5000)
        clicks = rng.randint(20, 260)
        return {
            "views": views,
            "likes": rng.randint(30, 600),
            "comments": rng.randint(1, 80),
            "shares": rng.randint(2, 160),
            "saves": rng.randint(5, 220),
            "clicks": clicks,
            "ctr": round(clicks / views, 4),
            "raw_metrics_json": {"provider": "mock", "provider_post_id": provider_post_id},
        }

