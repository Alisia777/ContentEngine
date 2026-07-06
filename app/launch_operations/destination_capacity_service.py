from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.launch_operations.errors import LaunchOperationsDataError
from app.launch_operations.types import DestinationCapacityResult


class DestinationCapacityService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, campaign_id: int) -> DestinationCapacityResult:
        campaign = self._campaign(campaign_id)
        destinations = self.db.scalars(
            select(models.PublishingDestination)
            .where(models.PublishingDestination.brand == campaign.brand)
            .order_by(models.PublishingDestination.id)
        ).all()
        active = [destination for destination in destinations if destination.status == "active"]
        manual = [
            destination
            for destination in active
            if destination.posting_mode == "manual" and destination.auth_status in {"manual_only", "not_configured", "needs_review"}
        ]
        api_ready = [
            destination
            for destination in active
            if destination.posting_mode == "api" and destination.auth_status == "token_valid"
        ]
        capacity_destinations = [*manual, *api_ready]
        daily_capacity = sum(max(0, destination.daily_limit) for destination in capacity_destinations)
        weekly_capacity = sum(max(0, destination.weekly_limit) for destination in capacity_destinations)
        required_slots = campaign.target_video_count
        capacity_gap = max(0, required_slots - weekly_capacity)
        blockers = []
        warnings = []
        if not active:
            blockers.append({"blocker": "no_active_destinations", "source": "destination_capacity"})
        if len(active) < campaign.target_destination_count:
            blockers.append(
                {
                    "blocker": "destination_gap",
                    "source": "destination_capacity",
                    "active_destinations": len(active),
                    "target_destinations": campaign.target_destination_count,
                    "missing_destinations": max(0, campaign.target_destination_count - len(active)),
                }
            )
        if capacity_gap:
            blockers.append(
                {
                    "blocker": "capacity_gap",
                    "source": "destination_capacity",
                    "required_slots": required_slots,
                    "weekly_capacity": weekly_capacity,
                    "capacity_gap": capacity_gap,
                }
            )
        inactive = [destination for destination in destinations if destination.status != "active"]
        if inactive:
            warnings.append({"warning": "inactive_destinations_not_counted", "count": len(inactive)})
        if any(destination.posting_mode == "api" and destination.auth_status != "token_valid" for destination in active):
            warnings.append({"warning": "api_destinations_need_token_valid", "source": "destination_capacity"})
        snapshot = models.DestinationCapacitySnapshot(
            campaign_id=campaign.id,
            total_destinations=len(destinations),
            active_destinations=len(active),
            manual_destinations=len(manual),
            api_ready_destinations=len(api_ready),
            daily_capacity=daily_capacity,
            weekly_capacity=weekly_capacity,
            required_slots=required_slots,
            capacity_gap=capacity_gap,
            blockers_json=blockers,
            warnings_json=warnings,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return self._result(snapshot)

    def latest_or_refresh(self, campaign_id: int) -> DestinationCapacityResult:
        snapshot = self.db.scalar(
            select(models.DestinationCapacitySnapshot)
            .where(models.DestinationCapacitySnapshot.campaign_id == campaign_id)
            .order_by(models.DestinationCapacitySnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh(campaign_id)
        return self._result(snapshot)

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise LaunchOperationsDataError(f"Campaign {campaign_id} not found.")
        return campaign

    @staticmethod
    def _result(snapshot: models.DestinationCapacitySnapshot) -> DestinationCapacityResult:
        return DestinationCapacityResult(
            snapshot_id=snapshot.id,
            campaign_id=snapshot.campaign_id,
            total_destinations=snapshot.total_destinations,
            active_destinations=snapshot.active_destinations,
            manual_destinations=snapshot.manual_destinations,
            api_ready_destinations=snapshot.api_ready_destinations,
            daily_capacity=snapshot.daily_capacity,
            weekly_capacity=snapshot.weekly_capacity,
            required_slots=snapshot.required_slots,
            capacity_gap=snapshot.capacity_gap,
            blockers=snapshot.blockers_json or [],
            warnings=snapshot.warnings_json or [],
            generated_at=snapshot.created_at,
        )
