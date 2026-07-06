from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.errors import ParticipantPortalDataError
from app.participant_portal.participant_service import ParticipantService


class OnboardingService:
    def __init__(self, db: Session):
        self.db = db

    def link_destination(
        self,
        participant_id: int,
        destination_id: int,
        *,
        relationship_type: str = "creator",
        permissions: list[str] | None = None,
    ) -> models.ParticipantDestinationLink:
        participant = ParticipantService(self.db).get(participant_id)
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise ParticipantPortalDataError(f"PublishingDestination {destination_id} not found.")
        link = self.db.scalar(
            select(models.ParticipantDestinationLink).where(
                models.ParticipantDestinationLink.participant_id == participant.id,
                models.ParticipantDestinationLink.destination_id == destination.id,
            )
        )
        if not link:
            link = models.ParticipantDestinationLink(participant_id=participant.id, destination_id=destination.id)
            self.db.add(link)
        link.relationship_type = relationship_type
        link.status = "active"
        link.permissions_json = permissions or ["view", "submit", "publish", "metrics"]
        self.db.commit()
        self.db.refresh(link)
        return link

    def destinations(self, participant_id: int) -> list[models.ParticipantDestinationLink]:
        ParticipantService(self.db).get(participant_id)
        return self.db.scalars(
            select(models.ParticipantDestinationLink)
            .where(models.ParticipantDestinationLink.participant_id == participant_id)
            .order_by(models.ParticipantDestinationLink.id)
        ).all()

    def setup_steps(self, participant_id: int) -> list[dict]:
        participant = ParticipantService(self.db).get(participant_id)
        links = self.destinations(participant_id)
        steps = []
        if not participant.platforms_json:
            steps.append({"step": "add_platforms", "status": "missing"})
        if not links:
            steps.append({"step": "link_destination", "status": "missing"})
        if not participant.email and not participant.telegram_handle:
            steps.append({"step": "add_contact", "status": "missing"})
        if not steps:
            steps.append({"step": "portal_ready", "status": "complete"})
        return steps
