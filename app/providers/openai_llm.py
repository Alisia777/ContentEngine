from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import ValidationError

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
        schema = self._strict_json_schema(GeneratedScriptOutput.model_json_schema())
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You generate marketplace product video scripts as strict JSON. "
                        "Use only allowed claims. Every claim_ref must exactly match either an allowed "
                        "claim source_key or source_type:source_key from the provided allowed_claims."
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
        try:
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=90,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderConfigurationError(
                "OpenAI structured script request failed with HTTP "
                f"{exc.response.status_code}: {self._safe_response_excerpt(exc.response)}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderConfigurationError(f"OpenAI structured script request failed: {exc}") from exc
        data = response.json()
        self.last_response_json = data
        text = self._extract_text(data)
        try:
            return GeneratedScriptOutput.model_validate_json(text)
        except ValidationError as exc:
            raise ProviderConfigurationError("OpenAI structured output did not match the script schema.") from exc

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        if data.get("output_text"):
            return data["output_text"]
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
        raise ProviderConfigurationError("OpenAI response did not contain structured output text.")

    @staticmethod
    def _safe_response_excerpt(response: httpx.Response) -> str:
        text = response.text.replace("\n", " ").strip()
        return text[:500] if text else "no response body"

    @classmethod
    def _strict_json_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(schema)
        cls._normalize_schema_node(normalized)
        return normalized

    @classmethod
    def _normalize_schema_node(cls, node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                cls._normalize_schema_node(item)
            return
        if not isinstance(node, dict):
            return

        node.pop("default", None)
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["additionalProperties"] = False
            node["required"] = list(properties.keys())
            for value in properties.values():
                cls._normalize_schema_node(value)

        for key in ("$defs", "definitions"):
            values = node.get(key)
            if isinstance(values, dict):
                for value in values.values():
                    cls._normalize_schema_node(value)

        for key in ("anyOf", "allOf", "oneOf", "prefixItems"):
            cls._normalize_schema_node(node.get(key))

        cls._normalize_schema_node(node.get("items"))
