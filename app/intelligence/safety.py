from __future__ import annotations

import os
from typing import Any

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError


MOCK_VIDEO_PROVIDER = "mock"


def is_real_video_provider(provider_name: str | None) -> bool:
    return bool(provider_name and provider_name != MOCK_VIDEO_PROVIDER)


def provider_key_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "generation_mode": settings.generation_mode,
        "allow_real_spend": settings.allow_real_spend,
        "llm_provider": settings.llm_provider,
        "video_provider": settings.video_provider,
        "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "runway_api_secret_configured": bool(os.getenv("RUNWAYML_API_SECRET")),
        "max_video_seconds_per_run": settings.max_video_seconds_per_run,
        "max_scenes_per_real_run": settings.max_scenes_per_real_run,
        "max_provider_poll_seconds": settings.max_provider_poll_seconds,
    }


def require_real_video_allowed(provider_name: str, explicit_real_run: bool) -> None:
    if not is_real_video_provider(provider_name):
        return

    settings = get_settings()
    if settings.generation_mode != "real":
        raise ProviderConfigurationError(
            "Real video provider calls require QVF_GENERATION_MODE=real."
        )
    if not explicit_real_run or not settings.allow_real_spend:
        raise ProviderConfigurationError(
            "Real video generation requires QVF_ALLOW_REAL_SPEND=true and an explicit real-run action."
        )


def bounded_scene_count(requested: int | None, *, full_video: bool, available: int) -> int:
    settings = get_settings()
    if available <= 0:
        return 0
    if full_video:
        desired = requested if requested is not None else available
    else:
        desired = requested if requested is not None else settings.max_scenes_per_real_run
    desired = max(1, min(desired, available))
    if not full_video:
        desired = min(desired, max(1, settings.max_scenes_per_real_run))
    return desired
