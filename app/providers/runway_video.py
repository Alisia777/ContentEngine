from __future__ import annotations

import os
from pathlib import Path

import httpx

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import PromptPackOutput, ProviderVideoJob, ProviderVideoStatus


class RunwayVideoProvider:
    provider_name = "runway"

    def __init__(self, api_secret: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_secret = api_secret or os.getenv("RUNWAYML_API_SECRET")
        self.model = model or settings.runway_model
        if not self.api_secret:
            raise ProviderConfigurationError("Runway provider is selected, but RUNWAYML_API_SECRET is missing.")

    def create_generation(self, prompt_pack: PromptPackOutput) -> ProviderVideoJob:
        payload = {
            "model": self.model,
            "promptText": prompt_pack.scene_prompts[0].prompt_text if prompt_pack.scene_prompts else "",
            "ratio": get_settings().video_ratio,
            "duration": prompt_pack.scene_prompts[0].duration_seconds if prompt_pack.scene_prompts else 5,
        }
        response = httpx.post(
            "https://api.dev.runwayml.com/v1/text_to_video",
            headers={
                "Authorization": f"Bearer {self.api_secret}",
                "Content-Type": "application/json",
                "X-Runway-Version": "2024-11-06",
            },
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        provider_job_id = str(data.get("id") or data.get("task_id") or data.get("uuid"))
        if not provider_job_id:
            raise ProviderConfigurationError("Runway response did not include a provider job id.")
        return ProviderVideoJob(
            provider=self.provider_name,
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "queued"),
            raw_response=data,
        )

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        response = httpx.get(
            f"https://api.dev.runwayml.com/v1/tasks/{provider_job_id}",
            headers={"Authorization": f"Bearer {self.api_secret}", "X-Runway-Version": "2024-11-06"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return ProviderVideoStatus(
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "unknown"),
            raw_response=data,
        )

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
        status = self.get_status(provider_job_id)
        outputs = status.raw_response.get("output") or status.raw_response.get("outputs") or []
        if isinstance(outputs, str):
            outputs = [outputs]
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for index, url in enumerate(outputs):
            response = httpx.get(url, timeout=120)
            response.raise_for_status()
            path = target_dir / f"{provider_job_id}_{index}.mp4"
            path.write_bytes(response.content)
            paths.append(path)
        return paths

