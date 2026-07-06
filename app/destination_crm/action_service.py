from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_crm.capacity_service import DestinationCRMCampaignCapacityService
from app.destination_crm.readiness_service import DestinationReadinessService
from app.destination_crm.types import DestinationCRMAction


class DestinationCRMActionService:
    def __init__(self, db: Session):
        self.db = db

    def list_actions(self, *, campaign_id: int | None = None) -> list[DestinationCRMAction]:
        actions: list[DestinationCRMAction] = []
        if campaign_id is not None:
            capacity = DestinationCRMCampaignCapacityService(self.db).calculate(campaign_id)
            for blocker in capacity.blockers:
                actions.append(
                    DestinationCRMAction(
                        campaign_id=campaign_id,
                        action_type="capacity",
                        action="add_or_activate_destinations",
                        priority=20,
                        reason=blocker.get("blocker", "capacity_blocker"),
                        blockers=[blocker],
                    )
                )
        snapshots = DestinationReadinessService(self.db).list_latest(campaign_id=campaign_id)
        for snapshot in snapshots:
            for action in snapshot.next_actions:
                actions.append(
                    DestinationCRMAction(
                        destination_id=snapshot.destination_id,
                        campaign_id=snapshot.campaign_id,
                        action_type="readiness",
                        action=action.get("action", "review_destination"),
                        priority=30,
                        reason=action.get("reason", snapshot.status),
                        blockers=snapshot.blockers,
                    )
                )
        return sorted(actions, key=lambda item: item.priority)

    def overview(self) -> dict:
        destinations = self.db.scalars(select(models.PublishingDestination)).all()
        snapshots = DestinationReadinessService(self.db).list_latest()
        return {
            "total": len(destinations),
            "active": sum(1 for destination in destinations if destination.status == "active"),
            "ready": sum(1 for snapshot in snapshots if snapshot.status == "ready"),
            "manual_ready": sum(1 for snapshot in snapshots if snapshot.manual_ready and snapshot.status == "ready"),
            "api_ready": sum(1 for snapshot in snapshots if snapshot.api_ready and snapshot.status == "ready"),
            "paused": sum(1 for destination in destinations if destination.status == "paused"),
            "blocked": sum(1 for snapshot in snapshots if snapshot.status != "ready"),
        }
