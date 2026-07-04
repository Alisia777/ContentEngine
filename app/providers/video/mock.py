from __future__ import annotations

from uuid import uuid4


class MockVideoProvider:
    def generate_clip(
        self,
        scene_prompt: str,
        negative_prompt: str,
        image_refs: list[str],
        aspect_ratio: str,
        duration_seconds: int,
    ) -> dict:
        return {
            "provider": "mock",
            "provider_job_id": f"mock-video-{uuid4().hex[:12]}",
            "status": "video_generated",
            "scene_prompt": scene_prompt,
            "negative_prompt": negative_prompt,
            "image_refs": image_refs,
            "aspect_ratio": aspect_ratio,
            "duration_seconds": duration_seconds,
            "cost_estimate": 0,
        }

    def get_status(self, provider_job_id: str) -> dict:
        return {"provider_job_id": provider_job_id, "status": "video_generated"}

    def download_result(self, provider_job_id: str) -> str:
        return f"mock://{provider_job_id}"

