from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.bombar_launch.destination_setup_planner import DestinationSetupPlanner
from app.bombar_launch.errors import BombarLaunchDataError
from app.bombar_launch.types import DistributionPlanResult
from app.campaign_autopilot.campaign_distribution_planner import CampaignDistributionPlanner
from app.campaign_autopilot.errors import CampaignAutopilotDataError


class DistributionAllocator:
    def __init__(self, db: Session):
        self.db = db

    def generate_plan(self, campaign_id: int) -> DistributionPlanResult:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise BombarLaunchDataError(f"Campaign {campaign_id} not found.")
        DestinationSetupPlanner(self.db).generate(campaign_id)
        try:
            plan = CampaignDistributionPlanner(self.db).generate_plan(campaign_id)
        except CampaignAutopilotDataError as exc:
            raise BombarLaunchDataError(str(exc)) from exc
        product_count = self.db.scalar(
            select(func.count()).select_from(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign_id)
        )
        plan_payload = {
            **(plan.plan or {}),
            "adapter": "bombar_launch",
            "delegated_to": "CampaignDistributionPlanner",
            "official_api_first": True,
            "manual_assisted_upload": True,
            "external_account_setup": False,
            "publish_policy": "approved_video_only",
        }
        return DistributionPlanResult(
            plan_id=plan.plan_id,
            campaign_id=plan.campaign_id,
            status=plan.status,
            total_products=int(product_count or 0),
            total_video_targets=campaign.target_video_count,
            total_destinations=plan.target_destination_count,
            total_tasks=plan.scheduled_slots,
            blockers=plan.blockers,
            warnings=plan.warnings,
            plan=plan_payload,
        )


def summarize_distribution_tasks(tasks: list[models.PublishingTask]) -> dict[str, Any]:
    by_destination: dict[str, int] = {}
    for task in tasks:
        key = str(task.destination_id or "unassigned")
        by_destination[key] = by_destination.get(key, 0) + 1
    return {"tasks_by_destination": by_destination}
