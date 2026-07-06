from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.launch_operations.destination_capacity_service import DestinationCapacityService
from app.launch_operations.errors import LaunchOperationsDataError
from app.launch_operations.quality_gate_service import QualityGateService
from app.launch_operations.types import DestinationCapacityResult, LaunchActionPlanResult, LaunchQualityGateResult


SAFE_ACTIONS = {
    "generate_reports",
    "run_prompt_only_batch",
    "create_draft_packages",
    "create_regeneration_requests",
    "import_destinations",
    "create_distribution_plan",
    "import_performance_stats",
}
HUMAN_ACTIONS = {
    "approve_video",
    "reject_video",
    "approve_publishing_package",
    "confirm_destination_ownership",
    "add_product_reference",
    "add_geometry_lock",
    "review_videos",
}
PAID_ACTIONS = {"run_real_smoke_for_ready_items", "paid_provider_calls", "api_upload"}
PUBLISHING_ACTIONS = {"create_publishing_tasks", "schedule_publishing", "mark_manually_uploaded", "upload_via_provider"}


class LaunchActionPlanner:
    def __init__(self, db: Session):
        self.db = db

    def refresh(
        self,
        campaign_id: int,
        *,
        quality_gates: list[LaunchQualityGateResult] | None = None,
        capacity: DestinationCapacityResult | None = None,
    ) -> LaunchActionPlanResult:
        campaign = self._campaign(campaign_id)
        quality_gates = quality_gates if quality_gates is not None else QualityGateService(self.db).list_latest(campaign_id)
        capacity = capacity or DestinationCapacityService(self.db).latest_or_refresh(campaign_id)
        actions = self._actions(campaign, quality_gates, capacity)
        plan = models.LaunchActionPlan(
            campaign_id=campaign.id,
            status="open" if actions else "ready",
            action_count=len(actions),
            safe_action_count=sum(1 for action in actions if action["action_type"] == "safe"),
            human_action_count=sum(1 for action in actions if action["action_type"] == "human"),
            paid_action_count=sum(1 for action in actions if action["action_type"] == "paid"),
            publishing_action_count=sum(1 for action in actions if action["action_type"] == "publishing"),
            actions_json=actions,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return self._result(plan)

    def latest_or_refresh(self, campaign_id: int) -> LaunchActionPlanResult:
        plan = self.db.scalar(
            select(models.LaunchActionPlan).where(models.LaunchActionPlan.campaign_id == campaign_id).order_by(models.LaunchActionPlan.id.desc())
        )
        if not plan:
            return self.refresh(campaign_id)
        return self._result(plan)

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise LaunchOperationsDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _actions(
        self,
        campaign: models.Campaign,
        quality_gates: list[LaunchQualityGateResult],
        capacity: DestinationCapacityResult,
    ) -> list[dict]:
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        content_runs = self._content_runs(product_ids)
        packages = self._packages(product_ids)
        approved_packages = [package for package in packages if package.review_status == "approved" and package.status in {"approved", "ready", "scheduled", "published"}]
        draft_packages = [package for package in packages if package.review_status != "approved"]
        tasks = self._publishing_tasks([package.id for package in approved_packages])
        recommendations = self.db.scalars(
            select(models.CampaignScalingRecommendation).where(models.CampaignScalingRecommendation.campaign_id == campaign.id)
        ).all()
        actions = [
            self._action("safe", "generate_reports", "campaign", "Refresh launch readiness and operator reports."),
        ]
        if any(not run.prompt_pack_id for run in content_runs) or not content_runs:
            actions.append(self._action("safe", "run_prompt_only_batch", "campaign", "Prompt-ready content is missing for some campaign items."))
        if any(self._has_blocker(gate, {"prompt_only_not_publishable", "video_output_missing"}) for gate in quality_gates):
            actions.append(self._action("paid", "run_real_smoke_for_ready_items", "campaign", "Real videos are missing for prompt-ready items."))
        for gate in quality_gates:
            if self._has_blocker(gate, {"missing_quality_review", "needs_human_review"}):
                actions.append(self._action("human", "review_videos", "video", "Video needs human review.", sku=gate.sku, entity_id=gate.video_job_id))
            if self._has_blocker(gate, {"needs_regeneration"}):
                actions.append(self._action("safe", "create_regeneration_requests", "video", "Regeneration should be requested.", sku=gate.sku, entity_id=gate.video_job_id))
            if self._has_blocker(gate, {"product_identity_mismatch"}):
                actions.append(self._action("human", "add_product_reference", "sku", "Product identity blocker must be fixed.", sku=gate.sku, entity_id=gate.product_id))
            if self._has_blocker(gate, {"product_geometry_mismatch"}):
                actions.append(self._action("human", "add_geometry_lock", "sku", "Geometry/scale lock blocker must be fixed.", sku=gate.sku, entity_id=gate.product_id))
        approved_video_count = sum(1 for gate in quality_gates if gate.publishing_allowed)
        if approved_video_count > len(packages):
            actions.append(self._action("safe", "create_draft_packages", "campaign", "Approved videos need draft publishing packages."))
        if draft_packages:
            actions.append(self._action("human", "approve_publishing_package", "campaign", "Draft packages need approval.", count=len(draft_packages)))
        if capacity.capacity_gap or any(blocker.get("blocker") == "destination_gap" for blocker in capacity.blockers):
            actions.append(self._action("human", "add_destinations", "campaign", "Destination capacity is below target.", count=max(capacity.capacity_gap, 1)))
            actions.append(self._action("safe", "import_destinations", "campaign", "Import owned destinations after they are prepared."))
        if approved_packages and not tasks:
            actions.append(self._action("safe", "create_distribution_plan", "campaign", "Approved packages need a distribution plan."))
            actions.append(self._action("publishing", "create_publishing_tasks", "campaign", "Approved packages need scheduled publishing tasks."))
        if not self._performance_metrics(campaign.id):
            actions.append(self._action("safe", "import_performance_stats", "campaign", "Performance stats are missing for the launch loop."))
        for recommendation in recommendations:
            if recommendation.recommendation_type == "scale" and recommendation.status == "proposed":
                actions.append(self._action("safe", "scale_variant", "recommendation", recommendation.expected_impact or "Scale recommended variant.", entity_id=recommendation.id))
            if recommendation.recommendation_type == "pause" and recommendation.status == "proposed":
                actions.append(self._action("safe", "pause_variant", "recommendation", recommendation.expected_impact or "Pause weak variant.", entity_id=recommendation.id))
        return self._dedupe(actions)

    def _content_runs(self, product_ids: list[int]) -> list[models.ContentRun]:
        if not product_ids:
            return []
        return self.db.scalars(select(models.ContentRun).where(models.ContentRun.product_id.in_(product_ids)).order_by(models.ContentRun.id)).all()

    def _packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(select(models.PublishingPackage).where(models.PublishingPackage.product_id.in_(product_ids))).all()

    def _publishing_tasks(self, package_ids: list[int]) -> list[models.PublishingTask]:
        if not package_ids:
            return []
        return self.db.scalars(select(models.PublishingTask).where(models.PublishingTask.publishing_package_id.in_(package_ids))).all()

    def _performance_metrics(self, campaign_id: int) -> list[models.CampaignPerformanceMetric]:
        return self.db.scalars(select(models.CampaignPerformanceMetric).where(models.CampaignPerformanceMetric.campaign_id == campaign_id)).all()

    @staticmethod
    def _has_blocker(gate: LaunchQualityGateResult, blockers: set[str]) -> bool:
        return any(blocker.get("blocker") in blockers for blocker in gate.blockers)

    @staticmethod
    def _action(
        action_type: str,
        action: str,
        scope: str,
        reason: str,
        *,
        sku: str | None = None,
        entity_id: int | None = None,
        count: int | None = None,
    ) -> dict:
        return {
            "action_type": action_type,
            "action": action,
            "scope": scope,
            "sku": sku,
            "entity_id": entity_id,
            "count": count,
            "reason": reason,
            "safe_to_execute": action_type == "safe",
            "requires_human": action_type == "human",
            "requires_paid": action_type == "paid",
            "is_publishing_action": action_type == "publishing" or action in PUBLISHING_ACTIONS,
        }

    @staticmethod
    def _dedupe(actions: list[dict]) -> list[dict]:
        deduped = []
        seen = set()
        for action in actions:
            key = (action.get("action_type"), action.get("action"), action.get("scope"), action.get("sku"), action.get("entity_id"))
            if key not in seen:
                seen.add(key)
                deduped.append(action)
        return deduped

    @staticmethod
    def _result(plan: models.LaunchActionPlan) -> LaunchActionPlanResult:
        return LaunchActionPlanResult(
            plan_id=plan.id,
            campaign_id=plan.campaign_id,
            status=plan.status,
            action_count=plan.action_count,
            safe_action_count=plan.safe_action_count,
            human_action_count=plan.human_action_count,
            paid_action_count=plan.paid_action_count,
            publishing_action_count=plan.publishing_action_count,
            actions=plan.actions_json or [],
            generated_at=plan.created_at,
        )
