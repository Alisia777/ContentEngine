from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_setup.errors import DestinationSetupDataError
from app.destination_setup.types import DestinationSetupRequirementResult
from app.launch_operations import DestinationCapacityService


DEFAULT_WEEKLY_DESTINATION_CAPACITY = 3


class SetupRequirementService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, campaign_id: int, *, platform: str = "Instagram Reels") -> DestinationSetupRequirementResult:
        campaign = self._campaign(campaign_id)
        capacity = DestinationCapacityService(self.db).refresh(campaign.id)
        existing_ready_count = self._ready_destination_count(campaign, platform)
        destination_gap = max(0, campaign.target_destination_count - capacity.active_destinations)
        capacity_destination_gap = math.ceil(capacity.capacity_gap / DEFAULT_WEEKLY_DESTINATION_CAPACITY) if capacity.capacity_gap else 0
        required_count = max(destination_gap, capacity_destination_gap)
        reason = self._reason(capacity.blockers, destination_gap, capacity.capacity_gap)
        status = "open" if required_count else "satisfied"
        requirement = self.db.scalar(
            select(models.DestinationSetupRequirement)
            .where(
                models.DestinationSetupRequirement.campaign_id == campaign.id,
                models.DestinationSetupRequirement.platform == platform,
            )
            .order_by(models.DestinationSetupRequirement.id.desc())
        )
        if requirement:
            requirement.required_count = required_count
            requirement.existing_ready_count = existing_ready_count
            requirement.capacity_gap = capacity.capacity_gap
            requirement.reason = reason
            requirement.status = status
        else:
            requirement = models.DestinationSetupRequirement(
                campaign_id=campaign.id,
                platform=platform,
                required_count=required_count,
                existing_ready_count=existing_ready_count,
                capacity_gap=capacity.capacity_gap,
                reason=reason,
                status=status,
            )
            self.db.add(requirement)
        self.db.commit()
        self.db.refresh(requirement)
        return self._result(requirement)

    def list(self, campaign_id: int) -> list[DestinationSetupRequirementResult]:
        self._campaign(campaign_id)
        requirements = self.db.scalars(
            select(models.DestinationSetupRequirement)
            .where(models.DestinationSetupRequirement.campaign_id == campaign_id)
            .order_by(models.DestinationSetupRequirement.id.desc())
        ).all()
        return [self._result(requirement) for requirement in requirements]

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationSetupDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _ready_destination_count(self, campaign: models.Campaign, platform: str) -> int:
        destinations = self.db.scalars(
            select(models.PublishingDestination).where(
                models.PublishingDestination.brand == campaign.brand,
                models.PublishingDestination.platform == platform,
                models.PublishingDestination.status == "active",
            )
        ).all()
        return sum(1 for destination in destinations if self._is_ready_destination(destination))

    @staticmethod
    def _is_ready_destination(destination: models.PublishingDestination) -> bool:
        if destination.posting_mode == "manual":
            return destination.auth_status in {"manual_only", "not_configured", "needs_review"}
        if destination.posting_mode == "api":
            return destination.auth_status == "token_valid"
        return False

    @staticmethod
    def _reason(blockers: list[dict], destination_gap: int, capacity_gap: int) -> str:
        blocker_names = {blocker.get("blocker") for blocker in blockers}
        if "no_active_destinations" in blocker_names:
            return "no_active_destinations"
        if destination_gap:
            return "destination_gap"
        if capacity_gap:
            return "capacity_gap"
        return "no_gap"

    @staticmethod
    def _result(requirement: models.DestinationSetupRequirement) -> DestinationSetupRequirementResult:
        return DestinationSetupRequirementResult(
            id=requirement.id,
            campaign_id=requirement.campaign_id,
            platform=requirement.platform,
            required_count=requirement.required_count,
            existing_ready_count=requirement.existing_ready_count,
            capacity_gap=requirement.capacity_gap,
            reason=requirement.reason,
            status=requirement.status,
            created_at=requirement.created_at,
            updated_at=requirement.updated_at,
        )
