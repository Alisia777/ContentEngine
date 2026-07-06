from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_execution import ExecutionStateService
from app.launch_operations.destination_capacity_service import DestinationCapacityService
from app.launch_operations.errors import LaunchOperationsDataError
from app.launch_operations.launch_action_planner import LaunchActionPlanner
from app.launch_operations.quality_gate_service import GENERATED_VIDEO_STATUSES, QualityGateService
from app.launch_operations.types import LaunchReadinessResult


class LaunchReadinessService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, campaign_id: int) -> LaunchReadinessResult:
        campaign = self._campaign(campaign_id)
        execution = ExecutionStateService(self.db).latest_snapshot(campaign.id)
        quality_gates = QualityGateService(self.db).refresh(campaign.id)
        capacity = DestinationCapacityService(self.db).refresh(campaign.id)
        action_plan = LaunchActionPlanner(self.db).refresh(campaign.id, quality_gates=quality_gates, capacity=capacity)
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        packages = self._packages(product_ids)
        tasks = self._distribution_tasks([package.id for package in packages])
        blockers = self._blockers(campaign, execution.blockers, quality_gates, capacity)
        warnings = self._warnings(campaign, capacity)
        real_video_count = self._real_video_count(product_ids)
        snapshot = models.LaunchReadinessSnapshot(
            campaign_id=campaign.id,
            status="blocked" if blockers else "ready",
            total_sku=execution.total_sku,
            target_videos=campaign.target_video_count,
            target_destinations=campaign.target_destination_count,
            prompt_ready_count=execution.prompt_ready_count,
            real_video_count=real_video_count,
            approved_video_count=sum(1 for gate in quality_gates if gate.publishing_allowed),
            needs_human_review_count=sum(1 for gate in quality_gates if self._needs_human_review(gate)),
            needs_regeneration_count=sum(1 for gate in quality_gates if self._has_blocker(gate, "needs_regeneration")),
            publishing_package_ready_count=sum(
                1 for package in packages if package.review_status == "approved" and package.status in {"approved", "ready", "scheduled", "published"}
            ),
            destination_total=capacity.total_destinations,
            destination_active_count=capacity.active_destinations,
            destination_capacity_total=capacity.weekly_capacity,
            distribution_task_ready_count=sum(1 for task in tasks if task.status in {"draft", "scheduled", "ready", "published"}),
            blockers_json=blockers,
            warnings_json=warnings,
            next_actions_json=action_plan.actions[:50],
        )
        self.db.add(snapshot)
        campaign.summary_json = {
            **(campaign.summary_json or {}),
            "latest_launch_readiness": {
                "status": snapshot.status,
                "blockers": blockers[:20],
                "next_actions": action_plan.actions[:20],
            },
        }
        self.db.commit()
        self.db.refresh(snapshot)
        return self._result(snapshot)

    def latest_or_refresh(self, campaign_id: int) -> LaunchReadinessResult:
        snapshot = self.db.scalar(
            select(models.LaunchReadinessSnapshot)
            .where(models.LaunchReadinessSnapshot.campaign_id == campaign_id)
            .order_by(models.LaunchReadinessSnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh(campaign_id)
        return self._result(snapshot)

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise LaunchOperationsDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(select(models.PublishingPackage).where(models.PublishingPackage.product_id.in_(product_ids))).all()

    def _distribution_tasks(self, package_ids: list[int]) -> list[models.PublishingTask]:
        if not package_ids:
            return []
        return self.db.scalars(select(models.PublishingTask).where(models.PublishingTask.publishing_package_id.in_(package_ids))).all()

    def _real_video_count(self, product_ids: list[int]) -> int:
        if not product_ids:
            return 0
        runs = self.db.scalars(select(models.ContentRun).where(models.ContentRun.product_id.in_(product_ids))).all()
        video_ids = {run.video_job_id for run in runs if run.video_job_id}
        if not video_ids:
            return 0
        jobs = self.db.scalars(select(models.VideoJob).where(models.VideoJob.id.in_(video_ids))).all()
        return sum(1 for job in jobs if job.output_video_path or job.status in GENERATED_VIDEO_STATUSES)

    def _blockers(self, campaign: models.Campaign, execution_blockers: list[dict], quality_gates, capacity) -> list[dict]:
        blockers = []
        blockers.extend({"source": "campaign_execution", **blocker} for blocker in execution_blockers)
        for gate in quality_gates:
            for blocker in gate.blockers:
                blockers.append({"source": "quality_gate", "sku": gate.sku, "video_job_id": gate.video_job_id, **blocker})
        blockers.extend(capacity.blockers)
        latest_plan = self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign.id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )
        if latest_plan:
            blockers.extend({"source": "distribution_plan", "blocker": blocker} for blocker in (latest_plan.blockers_json or []))
        else:
            blockers.append({"source": "distribution_plan", "blocker": "missing_distribution_plan"})
        return self._dedupe(blockers)

    @staticmethod
    def _warnings(campaign: models.Campaign, capacity) -> list[dict]:
        warnings = list(capacity.warnings)
        report_paths = (campaign.strategy_json or {}).get("bombar_production_report_paths")
        if report_paths:
            warnings.append({"warning": "bombar_production_dry_run_available", "report_paths": report_paths})
        return warnings

    @staticmethod
    def _needs_human_review(gate) -> bool:
        if gate.human_visual_status in {"needs_review", "pending"}:
            return True
        return any(blocker.get("blocker") in {"missing_quality_review", "needs_human_review"} for blocker in gate.blockers)

    @staticmethod
    def _has_blocker(gate, blocker_name: str) -> bool:
        return any(blocker.get("blocker") == blocker_name for blocker in gate.blockers)

    @staticmethod
    def _dedupe(blockers: list[dict]) -> list[dict]:
        deduped = []
        seen = set()
        for blocker in blockers:
            key = (blocker.get("source"), blocker.get("sku"), blocker.get("video_job_id"), blocker.get("blocker"))
            if key not in seen:
                seen.add(key)
                deduped.append(blocker)
        return deduped

    @staticmethod
    def _result(snapshot: models.LaunchReadinessSnapshot) -> LaunchReadinessResult:
        return LaunchReadinessResult(
            snapshot_id=snapshot.id,
            campaign_id=snapshot.campaign_id,
            status=snapshot.status,
            total_sku=snapshot.total_sku,
            target_videos=snapshot.target_videos,
            target_destinations=snapshot.target_destinations,
            prompt_ready_count=snapshot.prompt_ready_count,
            real_video_count=snapshot.real_video_count,
            approved_video_count=snapshot.approved_video_count,
            needs_human_review_count=snapshot.needs_human_review_count,
            needs_regeneration_count=snapshot.needs_regeneration_count,
            publishing_package_ready_count=snapshot.publishing_package_ready_count,
            destination_total=snapshot.destination_total,
            destination_active_count=snapshot.destination_active_count,
            destination_capacity_total=snapshot.destination_capacity_total,
            distribution_task_ready_count=snapshot.distribution_task_ready_count,
            blockers=snapshot.blockers_json or [],
            warnings=snapshot.warnings_json or [],
            next_actions=snapshot.next_actions_json or [],
            generated_at=snapshot.created_at,
        )
