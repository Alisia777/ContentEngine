from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import ProviderVideoJob, ProviderVideoStatus
from app.runway_recipes.types import ProductUGCRecipeRequest


class RunwayRecipeProvider:
    provider_name = "runway_product_ugc_recipe"
    endpoint = "https://api.dev.runwayml.com/v1/recipes/product_ugc"
    api_version = "2024-11-06"

    def __init__(self, api_secret: str | None = None, *, client: httpx.Client | None = None):
        self.api_secret = api_secret or os.getenv("RUNWAYML_API_SECRET")
        self.client = client
        if not self.api_secret:
            raise ProviderConfigurationError("Runway Product UGC Recipe requires RUNWAYML_API_SECRET.")

    def create_product_ugc(self, request: ProductUGCRecipeRequest) -> ProviderVideoJob:
        settings = get_settings()
        if settings.generation_mode != "real":
            raise ProviderConfigurationError("Runway recipe call is blocked: QVF_GENERATION_MODE must be real.")
        if not settings.allow_real_spend:
            raise ProviderConfigurationError("Runway recipe call is blocked: QVF_ALLOW_REAL_SPEND must be true.")
        payload = request.model_dump(mode="json", by_alias=True)
        response = self._request("POST", self.endpoint, json=payload, timeout=120)
        data = response.json()
        provider_job_id = str(data.get("id") or data.get("task_id") or data.get("uuid") or "")
        if not provider_job_id:
            raise ProviderConfigurationError("Runway Product UGC response did not include a task id.")
        return ProviderVideoJob(
            provider=self.provider_name,
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "queued"),
            raw_response=self._safe_task_metadata(data),
        )

    def get_status(self, provider_job_id: str) -> ProviderVideoStatus:
        data = self._get_task_raw(provider_job_id)
        return ProviderVideoStatus(
            provider_job_id=provider_job_id,
            status=str(data.get("status") or "unknown"),
            raw_response=self._safe_task_metadata(data),
        )

    def download_outputs(self, provider_job_id: str, target_dir: Path) -> list[Path]:
        data = self._get_task_raw(provider_job_id)
        outputs = data.get("output") or data.get("outputs") or []
        if isinstance(outputs, str):
            outputs = [outputs]
        if not outputs:
            raise ProviderConfigurationError("Runway Product UGC task has no output yet.")
        target_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index, url in enumerate(outputs):
            response = self._request("GET", str(url), timeout=180, include_auth=False)
            path = target_dir / f"{provider_job_id}_{index}.mp4"
            path.write_bytes(response.content)
            paths.append(path)
        return paths

    def _get_task_raw(self, provider_job_id: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"https://api.dev.runwayml.com/v1/tasks/{provider_job_id}",
            timeout=60,
        )
        return response.json()

    def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: int,
        include_auth: bool = True,
    ) -> httpx.Response:
        headers = {"X-Runway-Version": self.api_version}
        if include_auth:
            headers["Authorization"] = f"Bearer {self.api_secret}"
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            if self.client:
                response = self.client.request(method, url, headers=headers, json=json, timeout=timeout)
            else:
                response = httpx.request(method, url, headers=headers, json=json, timeout=timeout)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise ProviderConfigurationError(
                f"Runway Product UGC request failed with HTTP {exc.response.status_code}: "
                f"{self._safe_response_excerpt(exc.response)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConfigurationError(f"Runway Product UGC request failed: {exc}") from exc

    @staticmethod
    def _safe_task_metadata(data: dict[str, Any]) -> dict[str, Any]:
        outputs = data.get("output") or data.get("outputs") or []
        output_count = 1 if isinstance(outputs, str) else len(outputs)
        return {
            "id": data.get("id") or data.get("task_id") or data.get("uuid"),
            "status": data.get("status"),
            "failure": data.get("failure") or data.get("failureCode"),
            "failure_code": data.get("failureCode"),
            "output_count": output_count,
        }

    @staticmethod
    def _safe_response_excerpt(response: httpx.Response) -> str:
        text = response.text.replace("\n", " ").strip()
        text = re.sub(r"(https?://[^\s\"']+)\?[^\s\"']+", r"\1?[redacted]", text)
        return text[:500] if text else "no response body"
