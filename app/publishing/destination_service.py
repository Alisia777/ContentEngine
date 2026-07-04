from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.publishing.errors import PublishingError
from app.publishing.types import PublishingReadiness


class PublishingDestinationService:
    VALID_STATUSES = {"draft", "active", "paused", "disabled"}
    VALID_POSTING_MODES = {"manual", "api", "disabled"}
    VALID_AUTH_STATUSES = {"manual_only", "not_configured", "token_valid", "token_expired", "needs_review"}

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        brand: str,
        platform: str,
        name: str,
        handle: str | None = None,
        url: str | None = None,
        owner_name: str | None = None,
        status: str = "active",
        posting_mode: str = "manual",
        auth_status: str | None = None,
        allowed_formats: list[str] | None = None,
        daily_limit: int = 1,
        weekly_limit: int = 3,
        notes: str | None = None,
    ) -> models.PublishingDestination:
        self._validate_values(status, posting_mode, auth_status or self._default_auth_status(posting_mode))
        destination = models.PublishingDestination(
            brand=brand,
            platform=platform,
            name=name,
            handle=handle,
            url=url,
            owner_name=owner_name,
            status=status,
            posting_mode=posting_mode,
            auth_status=auth_status or self._default_auth_status(posting_mode),
            allowed_formats_json=allowed_formats or ["vertical_video"],
            daily_limit=daily_limit,
            weekly_limit=weekly_limit,
            notes=notes,
        )
        self.db.add(destination)
        self.db.commit()
        self.db.refresh(destination)
        return destination

    def list(self) -> list[models.PublishingDestination]:
        return self.db.scalars(select(models.PublishingDestination).order_by(models.PublishingDestination.platform)).all()

    def get(self, destination_id: int) -> models.PublishingDestination:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise PublishingError("Publishing destination not found.")
        return destination

    def update(self, destination_id: int, **values) -> models.PublishingDestination:
        destination = self.get(destination_id)
        for field, value in values.items():
            if value is not None:
                setattr(destination, field, value)
        self._validate_values(destination.status, destination.posting_mode, destination.auth_status)
        self.db.commit()
        self.db.refresh(destination)
        return destination

    def readiness(self, destination: models.PublishingDestination) -> PublishingReadiness:
        blockers: list[str] = []
        warnings: list[str] = []
        if destination.status != "active":
            blockers.append(f"Destination must be active; current status is {destination.status}.")
        if destination.posting_mode == "disabled":
            blockers.append("Posting mode is disabled.")
        if destination.posting_mode == "manual":
            if destination.auth_status not in {"manual_only", "not_configured", "needs_review"}:
                warnings.append(f"Manual destination has non-manual auth status: {destination.auth_status}.")
        if destination.posting_mode == "api" and destination.auth_status != "token_valid":
            blockers.append("API posting requires configured valid platform credentials.")
        if destination.daily_limit < 1:
            blockers.append("Daily limit must be at least 1.")
        if destination.weekly_limit < 1:
            blockers.append("Weekly limit must be at least 1.")
        return PublishingReadiness(
            ready=not blockers,
            status="ready" if not blockers else "blocked",
            blockers=blockers,
            warnings=warnings,
        )

    def _validate_values(self, status: str, posting_mode: str, auth_status: str) -> None:
        if status not in self.VALID_STATUSES:
            raise PublishingError(f"Invalid destination status: {status}.")
        if posting_mode not in self.VALID_POSTING_MODES:
            raise PublishingError(f"Invalid posting mode: {posting_mode}.")
        if auth_status not in self.VALID_AUTH_STATUSES:
            raise PublishingError(f"Invalid auth status: {auth_status}.")

    @staticmethod
    def _default_auth_status(posting_mode: str) -> str:
        if posting_mode == "manual":
            return "manual_only"
        if posting_mode == "api":
            return "not_configured"
        return "not_configured"
