from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot import CampaignStateService
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_execution.blocker_service import BlockerService
from app.campaign_execution.errors import CampaignExecutionDataError
from app.campaign_execution.types import ExecutionSnapshotResult


class ExecutionStateService:
    def __init__(self, db: Session):
        self.db = db
        self.blockers = BlockerService(db)

    def refresh_snapshot(self, campaign_id: int) -> ExecutionSnapshotResult:
        campaign = self._campaign(campaign_id)
        try:
            campaign_state = CampaignStateService(self.db).inspect_campaign(campaign_id)
        except CampaignAutopilotDataError as exc:
            raise CampaignExecutionDataError(str(exc)) from exc
        state_json = campaign_state.model_dump(mode="json")
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        campaign_products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id)
        ).all()
        publishing_ready = self.blockers.publishing_package_ready_count(product_ids)
        distribution_ready = self.blockers.distribution_task_ready_count(campaign.id)
        blockers = self.blockers.campaign_blockers(campaign, state_json)
        next_actions = self._next_actions(campaign_products, state_json, blockers)
        total_sku = int(state_json.get("sku_coverage", {}).get("total_sku") or len(campaign_products))
        ready_sku = int(state_json.get("sku_coverage", {}).get("with_prompt_ready") or 0)
        blocked_sku = sum(1 for item in campaign_products if item.blockers_json or item.status == "blocked")
        snapshot = models.CampaignExecutionSnapshot(
            campaign_id=campaign.id,
            status="blocked" if blockers else "ready",
            total_sku=total_sku,
            ready_sku=ready_sku,
            blocked_sku=blocked_sku,
            prompt_ready_count=int(state_json.get("prompt_ready_count") or 0),
            real_smoke_ready_count=int(state_json.get("real_smoke_ready_count") or 0),
            needs_review_count=int(state_json.get("needs_human_review") or 0),
            approved_video_count=sum(item.approved_video_count for item in campaign_products),
            publishing_package_ready_count=publishing_ready,
            distribution_task_ready_count=distribution_ready,
            blockers_json=blockers,
            next_actions_json=next_actions,
        )
        self.db.add(snapshot)
        campaign.summary_json = {
            **(campaign.summary_json or {}),
            "latest_execution_snapshot": {
                "snapshot_id": None,
                "status": snapshot.status,
                "blockers": blockers,
                "next_actions": next_actions[:20],
            },
        }
        self.db.flush()
        campaign.summary_json = {
            **(campaign.summary_json or {}),
            "latest_execution_snapshot": {
                "snapshot_id": snapshot.id,
                "status": snapshot.status,
                "blockers": blockers,
                "next_actions": next_actions[:20],
            },
        }
        self.db.commit()
        self.db.refresh(snapshot)
        return self._result(snapshot)

    def latest_snapshot(self, campaign_id: int) -> ExecutionSnapshotResult:
        snapshot = self.db.scalar(
            select(models.CampaignExecutionSnapshot)
            .where(models.CampaignExecutionSnapshot.campaign_id == campaign_id)
            .order_by(models.CampaignExecutionSnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh_snapshot(campaign_id)
        return self._result(snapshot)

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignExecutionDataError(f"Campaign {campaign_id} not found.")
        return campaign

    @staticmethod
    def _next_actions(
        campaign_products: list[models.CampaignProduct],
        state_json: dict,
        blockers: list[dict],
    ) -> list[dict]:
        actions = []
        for item in state_json.get("next_actions_by_sku", []):
            sku = item.get("sku")
            for action in item.get("next_actions", []):
                actions.append({"sku": sku, **action})
        blocker_names = {item["blocker"] for item in blockers}
        if "no_approved_video" in blocker_names:
            actions.append({"action": "human_review", "reason": "Approved videos are required before publishing."})
        if "no_destinations" in blocker_names:
            actions.append({"action": "schedule_distribution", "reason": "Destination readiness is missing."})
        if "no_stats" in blocker_names:
            actions.append({"action": "import_stats", "reason": "No performance stats are linked to this campaign yet."})
        for product in campaign_products:
            for blocker in product.blockers_json or []:
                actions.append({"sku": product.sku, "action": "resolve_blocker", "reason": blocker})
        deduped = []
        seen = set()
        for action in actions:
            key = (action.get("sku"), action.get("action"), action.get("reason"))
            if key not in seen:
                seen.add(key)
                deduped.append(action)
        return deduped

    @staticmethod
    def _result(snapshot: models.CampaignExecutionSnapshot) -> ExecutionSnapshotResult:
        return ExecutionSnapshotResult(
            snapshot_id=snapshot.id,
            campaign_id=snapshot.campaign_id,
            status=snapshot.status,
            total_sku=snapshot.total_sku,
            ready_sku=snapshot.ready_sku,
            blocked_sku=snapshot.blocked_sku,
            prompt_ready_count=snapshot.prompt_ready_count,
            real_smoke_ready_count=snapshot.real_smoke_ready_count,
            needs_review_count=snapshot.needs_review_count,
            approved_video_count=snapshot.approved_video_count,
            publishing_package_ready_count=snapshot.publishing_package_ready_count,
            distribution_task_ready_count=snapshot.distribution_task_ready_count,
            blockers=snapshot.blockers_json or [],
            next_actions=snapshot.next_actions_json or [],
            generated_at=snapshot.created_at,
        )
