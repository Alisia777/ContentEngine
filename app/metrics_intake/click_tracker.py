from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.metrics_intake.tracking_link_service import TrackingLinkService


class ClickTracker:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        slug: str,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[models.TrackingLink, models.TrackingClick]:
        link = TrackingLinkService(self.db).get_by_slug(slug)
        click = models.TrackingClick(
            tracking_link_id=link.id,
            campaign_id=link.campaign_id,
            publishing_task_id=link.publishing_task_id,
            destination_id=link.destination_id,
            sku=link.sku,
            creative_variant_id=link.creative_variant_id,
            participant_id=link.participant_id,
            referrer=(referrer or "")[:500] or None,
            user_agent_hash=self._hash(user_agent),
            metadata_json=metadata or {},
        )
        self.db.add(click)
        self.db.commit()
        self.db.refresh(click)
        return link, click

    @staticmethod
    def _hash(user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()
