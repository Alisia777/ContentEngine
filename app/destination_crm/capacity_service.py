from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_crm.errors import DestinationCRMDataError
from app.destination_crm.readiness_service import DestinationReadinessService
from app.destination_crm.types import DestinationCampaignCapacityResult


class DestinationCRMCampaignCapacityService:
    def __init__(self, db: Session):
        self.db = db

    def calculate(self, campaign_id: int) -> DestinationCampaignCapacityResult:
        campaign = self._campaign(campaign_id)
        destinations = self.db.scalars(
            select(models.PublishingDestination)
            .where(models.PublishingDestination.brand == campaign.brand)
            .order_by(models.PublishingDestination.id)
        ).all()
        readiness = [DestinationReadinessService(self.db).refresh(destination.id, campaign_id=campaign.id) for destination in destinations]
        ready = [item for item in readiness if item.status == "ready"]
        active = [destination for destination in destinations if destination.status == "active"]
        paused = [destination for destination in destinations if destination.status == "paused"]
        available_daily = sum(item.remaining_daily_capacity for item in ready)
        available_weekly = sum(item.remaining_weekly_capacity for item in ready)
        capacity_gap = max(0, campaign.target_video_count - available_weekly)
        blockers = []
        warnings = []
        if len(ready) < campaign.target_destination_count:
            blockers.append(
                {
                    "blocker": "destination_ready_count_below_target",
                    "ready_destinations": len(ready),
                    "target_destinations": campaign.target_destination_count,
                }
            )
        if capacity_gap:
            blockers.append(
                {
                    "blocker": "capacity_gap",
                    "required_slots": campaign.target_video_count,
                    "available_weekly_capacity": available_weekly,
                    "capacity_gap": capacity_gap,
                }
            )
        if paused:
            warnings.append({"warning": "paused_destinations_not_counted", "count": len(paused)})
        return DestinationCampaignCapacityResult(
            campaign_id=campaign.id,
            total_destinations=len(destinations),
            active_destinations=len(active),
            ready_destinations=len(ready),
            manual_ready_destinations=sum(1 for item in ready if item.manual_ready),
            api_ready_destinations=sum(1 for item in ready if item.api_ready),
            paused_destinations=len(paused),
            blocked_destinations=sum(1 for item in readiness if item.status != "ready"),
            required_slots=campaign.target_video_count,
            available_daily_capacity=available_daily,
            available_weekly_capacity=available_weekly,
            capacity_gap=capacity_gap,
            blockers=blockers,
            warnings=warnings,
            destinations=readiness,
        )

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationCRMDataError(f"Campaign {campaign_id} not found.")
        return campaign
