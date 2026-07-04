from __future__ import annotations

import json
import os
from typing import Any

import httpx

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import GeneratedScriptOutput, ScriptBriefOutput


class OpenAILLMProvider:
    provider_name = "openai"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or settings.openai_model
        if not self.api_key:
            raise ProviderConfigurationError("OpenAI provider is selected, but OPENAI_API_KEY is missing.")

    def generate_script(self, brief: ScriptBriefOutput) -> GeneratedScriptOutput:
        schema = GeneratedScriptOutput.model_json_schema()
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You generate marketplace product video scripts as strict JSON. "
                        "Use only allowed claims and keep claim_refs source-backed."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(brief.model_dump(mode="json"), ensure_ascii=False),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "generated_product_video_script",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        self.last_request_json = payload
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        self.last_response_json = data
        text = self._extract_text(data)
        return GeneratedScriptOutput.model_validate_json(text)

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if data.get("output_text"):
            return data["output_text"]
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
        raise ProviderConfigurationError("OpenAI response did not contain structured output text.")
