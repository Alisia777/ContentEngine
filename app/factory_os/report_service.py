from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_execution import ActionQueueService, ExecutionStateService
from app.factory_os.errors import FactoryOSDataError
from app.factory_os.types import FactoryAcceptanceReport


class FactoryAcceptanceReportService:
    def __init__(self, db: Session):
        self.db = db

    def build(self, campaign_id: int) -> FactoryAcceptanceReport:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise FactoryOSDataError(f"Campaign {campaign_id} not found.")
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        campaign_products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id)
        ).all()
        content_runs = self._content_runs(campaign_products, product_ids)
        snapshot = ExecutionStateService(self.db).latest_snapshot(campaign.id)
        actions = ActionQueueService(self.db).list_actions(campaign.id, include_done=True)
        latest_batch = self._latest_batch(campaign.id)
        latest_plan = self._latest_plan(campaign.id)
        blockers = self._blockers(campaign_products, snapshot.blockers, latest_plan)
        packages = self._packages(product_ids)
        performance_metric_count = self._count(models.CampaignPerformanceMetric, campaign_id=campaign.id)
        recommendation_count = self._count(models.CampaignScalingRecommendation, campaign_id=campaign.id)
        paid_calls = self._paid_calls(campaign.id)
        unsafe_blocked = sum(1 for action in actions if not action.safe_to_execute and action.status in {"open", "blocked"})
        return FactoryAcceptanceReport(
            campaign_id=campaign.id,
            total_sku=len(product_ids),
            target_videos=campaign.target_video_count,
            target_destinations=campaign.target_destination_count,
            content_runs_created=len(content_runs),
            prompt_packs_created=len({run.prompt_pack_id for run in content_runs if run.prompt_pack_id}),
            blockers=blockers,
            batch_actions_executed=latest_batch.total_executed if latest_batch else 0,
            publishing_packages_draft=sum(1 for package in packages if package.review_status != "approved"),
            publishing_packages_approved=sum(1 for package in packages if package.review_status == "approved"),
            distribution_plan_status=latest_plan.status if latest_plan else "missing",
            performance_metrics_imported=performance_metric_count,
            recommendations_generated=recommendation_count,
            paid_calls_made=paid_calls,
            unsafe_actions_blocked=unsafe_blocked,
            generated_artifacts_paths=[
                f"/campaign-autopilot?campaign_id={campaign.id}",
                f"/campaign-execution?campaign_id={campaign.id}",
                f"/campaign-batch?campaign_id={campaign.id}",
                f"/campaign-performance?campaign_id={campaign.id}",
                f"/factory-os?campaign_id={campaign.id}",
            ],
            next_manual_actions=snapshot.next_actions[:20],
            summary={
                "campaign_status": campaign.status,
                "latest_snapshot_status": snapshot.status,
                "latest_batch_id": latest_batch.id if latest_batch else None,
                "latest_distribution_plan_id": latest_plan.id if latest_plan else None,
                "paid_provider_policy": "blocked_in_prompt_only_acceptance",
                "publishing_policy": "approved_packages_only",
            },
        )

    def _content_runs(self, campaign_products: list[models.CampaignProduct], product_ids: list[int]) -> list[models.ContentRun]:
        ids = {int(run_id) for item in campaign_products for run_id in (item.content_run_ids_json or [])}
        if ids:
            return self.db.scalars(select(models.ContentRun).where(models.ContentRun.id.in_(ids))).all()
        if not product_ids:
            return []
        return self.db.scalars(select(models.ContentRun).where(models.ContentRun.product_id.in_(product_ids))).all()

    def _latest_batch(self, campaign_id: int) -> models.CampaignBatchRun | None:
        return self.db.scalar(
            select(models.CampaignBatchRun)
            .where(models.CampaignBatchRun.campaign_id == campaign_id)
            .order_by(models.CampaignBatchRun.id.desc())
        )

    def _latest_plan(self, campaign_id: int) -> models.CampaignDistributionPlan | None:
        return self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign_id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )

    def _packages(self, product_ids: list[int]) -> list[models.PublishingPackage]:
        if not product_ids:
            return []
        return self.db.scalars(select(models.PublishingPackage).where(models.PublishingPackage.product_id.in_(product_ids))).all()

    def _count(self, model: type, **filters) -> int:
        query = select(model)
        for field, value in filters.items():
            query = query.where(getattr(model, field) == value)
        return len(self.db.scalars(query).all())

    def _paid_calls(self, campaign_id: int) -> int:
        batch_ids = [
            batch.id
            for batch in self.db.scalars(
                select(models.CampaignBatchRun).where(models.CampaignBatchRun.campaign_id == campaign_id)
            ).all()
        ]
        if not batch_ids:
            return 0
        return len(
            self.db.scalars(
                select(models.CampaignBatchItem).where(
                    models.CampaignBatchItem.batch_run_id.in_(batch_ids),
                    models.CampaignBatchItem.action_type == "run_real_smoke",
                    models.CampaignBatchItem.status == "done",
                )
            ).all()
        )

    @staticmethod
    def _blockers(
        campaign_products: list[models.CampaignProduct],
        snapshot_blockers: list[dict],
        latest_plan: models.CampaignDistributionPlan | None,
    ) -> list[dict]:
        blockers = list(snapshot_blockers or [])
        if latest_plan:
            blockers.extend({"blocker": blocker, "source": "distribution_plan"} for blocker in (latest_plan.blockers_json or []))
        for product in campaign_products:
            blockers.extend({"sku": product.sku, "blocker": blocker, "source": "campaign_product"} for blocker in (product.blockers_json or []))
        deduped = []
        seen = set()
        for blocker in blockers:
            key = (blocker.get("sku"), blocker.get("blocker"), blocker.get("source"))
            if key not in seen:
                seen.add(key)
                deduped.append(blocker)
        return deduped
