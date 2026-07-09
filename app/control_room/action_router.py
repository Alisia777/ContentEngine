from __future__ import annotations


MODULE_URLS = {
    "engine_audit": "/engine-audit",
    "one_video_acceptance": "/one-video-acceptance",
    "output_acceptance": "/output-acceptance",
    "ai_brief_studio": "/ai-brief-studio",
    "product_strategy": "/product-strategy",
    "metrics_intake": "/metrics-intake",
    "participant_portal": "/participant-portal",
    "settings_access": "/settings/access",
    "publishing": "/publishing",
    "destination_control": "/destination-control",
    "campaign_execution": "/campaign-execution",
    "training": "/training-academy",
}


class ControlRoomActionRouter:
    def route(self, target_module: str, fallback_url: str | None = None) -> str:
        return MODULE_URLS.get(target_module, fallback_url or "/control-room")
