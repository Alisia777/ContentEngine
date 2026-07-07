from __future__ import annotations

import base64
import mimetypes
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
        scene = prompt_pack.scene_prompts[0] if prompt_pack.scene_prompts else None
        prompt_text = scene.prompt_text if scene else ""
        prompt_text = prompt_text[:1000]
        payload = {
            "model": self.model,
            "promptText": prompt_text,
            "ratio": get_settings().video_ratio,
            "duration": scene.duration_seconds if scene else 5,
        }
        endpoint = "https://api.dev.runwayml.com/v1/text_to_video"
        reference_image = self._local_reference_image(scene.reference_images if scene else [])
        if reference_image:
            payload["promptImage"] = self._data_uri(reference_image)
            endpoint = "https://api.dev.runwayml.com/v1/image_to_video"
        try:
            response = httpx.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_secret}",
                    "Content-Type": "application/json",
                    "X-Runway-Version": "2024-11-06",
                },
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderConfigurationError(
                f"Runway generation request failed with HTTP {exc.response.status_code}: "
                f"{self._safe_response_excerpt(exc.response)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConfigurationError(f"Runway generation request failed: {exc}") from exc
        data = response.json()
        provider_job_id = str(data.get("id") or data.get("task_id") or data.get("uuid"))
        if not provider_job_id:
            raise ProviderConfigurationError("Runway response did not include a provider job id.")
        raw_response = dict(data)
        raw_response["prompt_image_used"] = bool(reference_image)
        return ProviderVideoJob(
            provider=self.provider_name,
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "queued"),
            raw_response=raw_response,
        )

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        try:
            response = httpx.get(
                f"https://api.dev.runwayml.com/v1/tasks/{provider_job_id}",
                headers={"Authorization": f"Bearer {self.api_secret}", "X-Runway-Version": "2024-11-06"},
                timeout=60,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderConfigurationError(
                f"Runway status request failed with HTTP {exc.response.status_code}: "
                f"{self._safe_response_excerpt(exc.response)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConfigurationError(f"Runway status request failed: {exc}") from exc
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
        if not outputs:
            raise ProviderConfigurationError("Runway task has no output URLs yet. Poll until the task is complete.")
        target_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for index, url in enumerate(outputs):
            try:
                response = httpx.get(url, timeout=120)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ProviderConfigurationError(
                    f"Runway output download failed with HTTP {exc.response.status_code}: "
                    f"{self._safe_response_excerpt(exc.response)}"
                ) from exc
            except httpx.RequestError as exc:
                raise ProviderConfigurationError(f"Runway output download failed: {exc}") from exc
            path = target_dir / f"{provider_job_id}_{index}.mp4"
            path.write_bytes(response.content)
            paths.append(path)
        return paths

    @staticmethod
    def _safe_response_excerpt(response: httpx.Response) -> str:
        text = response.text.replace("\n", " ").strip()
        return text[:500] if text else "no response body"

    @staticmethod
    def _local_reference_image(reference_images: list[str]) -> Path | None:
        for reference in reference_images or []:
            path = Path(reference)
            if not path.is_absolute():
                path = Path.cwd() / path
            if path.exists() and path.is_file():
                return path
        return None

    @staticmethod
    def _data_uri(path: Path) -> str:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
