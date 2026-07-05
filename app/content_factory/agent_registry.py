from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


DEFAULT_AGENTS = [
    {
        "agent_key": "ai_demand_agent",
        "name": "AI Demand Agent",
        "agent_type": "demand",
        "capabilities": ["select_buyer_need", "safe_promise", "demand_validation"],
    },
    {
        "agent_key": "ai_creative_brief_agent",
        "name": "AI Creative Brief Agent",
        "agent_type": "creative_brief",
        "capabilities": ["creative_spec", "source_backed_claims", "safe_brief"],
    },
    {
        "agent_key": "ai_variant_agent",
        "name": "AI Variant Agent",
        "agent_type": "variant",
        "capabilities": ["first_frame", "variant_scoring", "selected_variant"],
    },
    {
        "agent_key": "ai_video_agent",
        "name": "AI Video Agent",
        "agent_type": "video",
        "capabilities": ["prompt_pack", "real_smoke_readiness"],
    },
    {
        "agent_key": "ai_review_agent",
        "name": "AI Review Agent",
        "agent_type": "review",
        "capabilities": ["rules_review", "human_review_gate"],
    },
    {
        "agent_key": "ai_publishing_prep_agent",
        "name": "AI Publishing Prep Agent",
        "agent_type": "publishing_prep",
        "capabilities": ["publishing_readiness", "approval_gate", "package_recommendation"],
    },
    {
        "agent_key": "performance_analytics_agent",
        "name": "Performance Analytics Agent",
        "agent_type": "performance",
        "capabilities": ["stats_import", "scale_pause_recommendation"],
    },
]


class ContentAgentRegistry:
    def __init__(self, db: Session):
        self.db = db

    def ensure_defaults(self) -> list[models.ContentAgentProfile]:
        profiles = []
        for item in DEFAULT_AGENTS:
            profile = self.db.scalar(
                select(models.ContentAgentProfile).where(models.ContentAgentProfile.agent_key == item["agent_key"])
            )
            if not profile:
                profile = models.ContentAgentProfile(
                    agent_key=item["agent_key"],
                    name=item["name"],
                    agent_type=item["agent_type"],
                    status="active",
                    provider="rules",
                    capabilities_json=item["capabilities"],
                    config_json={"automated": True, "requires_human_on_exception": True},
                )
                self.db.add(profile)
            profiles.append(profile)
        self.db.commit()
        return self.list()

    def list(self) -> list[models.ContentAgentProfile]:
        return self.db.scalars(select(models.ContentAgentProfile).order_by(models.ContentAgentProfile.id)).all()

    def by_type(self, agent_type: str) -> models.ContentAgentProfile | None:
        self.ensure_defaults()
        return self.db.scalar(
            select(models.ContentAgentProfile)
            .where(models.ContentAgentProfile.agent_type == agent_type, models.ContentAgentProfile.status == "active")
            .order_by(models.ContentAgentProfile.id)
        )
