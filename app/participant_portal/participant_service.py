from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.errors import ParticipantPortalDataError


VALID_ROLES = {"creator", "publisher", "partner", "reviewer", "operator", "admin"}


class ParticipantService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        display_name: str,
        role: str = "creator",
        email: str | None = None,
        telegram_handle: str | None = None,
        platforms: list[str] | None = None,
        notes: str | None = None,
    ) -> models.ParticipantProfile:
        role = self._role(role)
        participant = models.ParticipantProfile(
            display_name=display_name.strip(),
            role=role,
            email=email or None,
            telegram_handle=telegram_handle or None,
            platforms_json=platforms or [],
            notes=notes or None,
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def get(self, participant_id: int) -> models.ParticipantProfile:
        participant = self.db.get(models.ParticipantProfile, participant_id)
        if not participant:
            raise ParticipantPortalDataError(f"ParticipantProfile {participant_id} not found.")
        return participant

    def list(self) -> list[models.ParticipantProfile]:
        return self.db.scalars(select(models.ParticipantProfile).order_by(models.ParticipantProfile.id)).all()

    def update(self, participant_id: int, **values: Any) -> models.ParticipantProfile:
        participant = self.get(participant_id)
        if "role" in values and values["role"]:
            values["role"] = self._role(values["role"])
        if "platforms" in values:
            values["platforms_json"] = values.pop("platforms") or []
        for key, value in values.items():
            if value is not None and hasattr(participant, key):
                setattr(participant, key, value)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    @staticmethod
    def _role(role: str) -> str:
        normalized = (role or "").strip()
        if normalized not in VALID_ROLES:
            raise ParticipantPortalDataError(f"Unsupported participant role: {role}")
        return normalized
