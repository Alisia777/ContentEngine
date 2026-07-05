from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.bombar_launch.errors import BombarLaunchDataError
from app.bombar_launch.types import BombarDashboard
from app.campaign_autopilot.campaign_runner import CampaignRunner
from app.campaign_autopilot.campaign_state_service import CampaignStateService
from app.campaign_autopilot.errors import CampaignAutopilotDataError


class LaunchDashboardService:
    def __init__(self, db: Session):
        self.db = db

    def dashboard(self, campaign_id: int) -> BombarDashboard:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise BombarLaunchDataError(f"Campaign {campaign_id} not found.")
        try:
            state = CampaignStateService(self.db).inspect_campaign(campaign.id)
            report = CampaignRunner(self.db).generate_campaign_report(campaign.id)
        except CampaignAutopilotDataError as exc:
            raise BombarLaunchDataError(str(exc)) from exc
        packs = self.db.scalars(
            select(models.DestinationSetupPack).where(models.DestinationSetupPack.campaign_id == campaign.id)
        ).all()
        latest_plan = self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign.id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )
        next_actions = self._next_actions(campaign, state.model_dump(mode="json"), len(packs), latest_plan)
        return BombarDashboard(
            campaign_id=campaign.id,
            linked_campaign_id=campaign.id,
            campaign_status=campaign.status,
            ready_sku=int(state.sku_coverage.get("with_prompt_ready", 0)),
            blocked_sku=sum(1 for item in state.next_actions_by_sku if item.get("status") == "blocked"),
            needs_reference=state.missing_references,
            needs_review=state.needs_human_review,
            ready_for_publishing=state.publishing_ready_count,
            destination_packs=len(packs),
            publishing_tasks=latest_plan.scheduled_slots if latest_plan else 0,
            top_blockers=state.blockers_by_type,
            next_actions=next_actions,
            campaign_state=state.model_dump(mode="json"),
            campaign_report=report.model_dump(mode="json"),
        )

    @staticmethod
    def _next_actions(
        campaign: models.Campaign,
        state: dict,
        destination_pack_count: int,
        latest_plan: models.CampaignDistributionPlan | None,
    ) -> list[dict]:
        actions = []
        if state.get("prompt_ready_count", 0) == 0:
            actions.append({"action": "prepare_content", "reason": "No prompt-ready content exists for this campaign."})
        if destination_pack_count < campaign.target_destination_count:
            actions.append({"action": "generate_destination_packs", "reason": "Destination setup capacity is incomplete."})
        if state.get("needs_human_review", 0):
            actions.append({"action": "human_review", "reason": "Prompt-ready items need approved videos before publishing."})
        if not latest_plan:
            actions.append({"action": "generate_distribution_plan", "reason": "No generic campaign distribution plan exists yet."})
        if not actions:
            actions.append({"action": "monitor_performance", "reason": "Campaign has a generic plan; import final URLs and stats next."})
        return actions
