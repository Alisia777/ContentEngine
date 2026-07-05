from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot import CampaignRunner
from app.campaign_execution.errors import CampaignExecutionDataError
from app.campaign_execution.types import ActionExecutionResult, ActionQueueItemResult


PAID_ACTIONS = {"run_real_smoke"}
PUBLISHING_ACTIONS = {"create_publishing_package", "approve_publishing_package", "schedule_distribution"}


class ActionQueueService:
    def __init__(self, db: Session):
        self.db = db

    def refresh_actions(self, campaign_id: int) -> list[ActionQueueItemResult]:
        campaign = self._campaign(campaign_id)
        campaign_products = self.db.scalars(
            select(models.CampaignProduct)
            .where(models.CampaignProduct.campaign_id == campaign.id)
            .order_by(models.CampaignProduct.id)
        ).all()
        for item in campaign_products:
            product = self.db.get(models.Product, item.product_id)
            if not product:
                continue
            if not product.images_json or any("reference" in blocker for blocker in item.blockers_json or []):
                self._upsert(
                    campaign_id=campaign.id,
                    product_id=product.id,
                    sku=item.sku,
                    content_run_id=None,
                    action_type="add_reference",
                    priority=10,
                    reason="Approved product reference is required before real video generation.",
                    blockers=["missing_reference"],
                    safe_to_execute=False,
                    requires_human=True,
                )
            for content_run_id in item.content_run_ids_json or []:
                run = self.db.get(models.ContentRun, int(content_run_id))
                if not run:
                    continue
                if not run.prompt_pack_id:
                    self._upsert(
                        campaign_id=campaign.id,
                        product_id=product.id,
                        sku=item.sku,
                        content_run_id=run.id,
                        action_type="run_prompt_only",
                        priority=20,
                        reason="Content run has no prompt pack yet.",
                        blockers=run.blockers_json or [],
                        safe_to_execute=True,
                        requires_human=False,
                    )
                if run.prompt_pack_id and not run.video_job_id:
                    self._upsert(
                        campaign_id=campaign.id,
                        product_id=product.id,
                        sku=item.sku,
                        content_run_id=run.id,
                        action_type="human_review",
                        priority=30,
                        reason="Prompt-ready content needs video output and human review before publishing.",
                        blockers=run.blockers_json or [],
                        safe_to_execute=False,
                        requires_human=True,
                    )
                if run.status == "ready_for_real_smoke" or (run.run_json or {}).get("real_smoke_eligible"):
                    self._upsert(
                        campaign_id=campaign.id,
                        product_id=product.id,
                        sku=item.sku,
                        content_run_id=run.id,
                        action_type="run_real_smoke",
                        priority=40,
                        reason="Real smoke is paid and requires explicit spend gates.",
                        blockers=list(dict.fromkeys(["paid_provider_gate", *(run.blockers_json or [])])),
                        safe_to_execute=False,
                        requires_human=False,
                    )
        self._publishing_actions(campaign)
        self.db.commit()
        return self.list_actions(campaign_id)

    def list_actions(self, campaign_id: int, *, include_done: bool = False) -> list[ActionQueueItemResult]:
        self._campaign(campaign_id)
        query = (
            select(models.CampaignActionQueueItem)
            .where(models.CampaignActionQueueItem.campaign_id == campaign_id)
            .order_by(models.CampaignActionQueueItem.priority, models.CampaignActionQueueItem.id)
        )
        if not include_done:
            query = query.where(models.CampaignActionQueueItem.status.in_(["open", "blocked"]))
        return [self._result(item) for item in self.db.scalars(query).all()]

    def execute(self, action_id: int, *, allow_paid: bool = False) -> ActionExecutionResult:
        action = self._action(action_id)
        blockers = list(action.blockers_json or [])
        if action.action_type in PAID_ACTIONS and not allow_paid:
            blockers = list(dict.fromkeys([*blockers, "paid_action_requires_gate"]))
            action.blockers_json = blockers
            action.status = "blocked"
            self.db.commit()
            return ActionExecutionResult(
                action_id=action.id,
                status=action.status,
                executed=False,
                message="Paid action blocked without explicit gate.",
                artifacts={"blockers": blockers},
            )
        if action.action_type in PUBLISHING_ACTIONS and not self._publishing_allowed(action):
            blockers = list(dict.fromkeys([*blockers, "approved_video_required"]))
            action.blockers_json = blockers
            action.status = "blocked"
            self.db.commit()
            return ActionExecutionResult(
                action_id=action.id,
                status=action.status,
                executed=False,
                message="Publishing action blocked until an approved video/package exists.",
                artifacts={"blockers": blockers},
            )
        if not action.safe_to_execute:
            blockers = list(dict.fromkeys([*blockers, "unsafe_action_requires_human"]))
            action.blockers_json = blockers
            action.status = "blocked"
            self.db.commit()
            return ActionExecutionResult(
                action_id=action.id,
                status=action.status,
                executed=False,
                message="Action requires human handling.",
                artifacts={"blockers": blockers},
            )
        if action.action_type == "run_prompt_only":
            result = CampaignRunner(self.db).run_prompt_only_for_ready_items(action.campaign_id)
            action.status = "done"
            self.db.commit()
            return ActionExecutionResult(
                action_id=action.id,
                status=action.status,
                executed=True,
                message="Prompt-only run completed through CampaignRunner.",
                artifacts=result.model_dump(mode="json"),
            )
        action.status = "resolved"
        self.db.commit()
        return ActionExecutionResult(
            action_id=action.id,
            status=action.status,
            executed=True,
            message="Safe action resolved.",
        )

    def resolve(self, action_id: int) -> ActionQueueItemResult:
        action = self._action(action_id)
        action.status = "resolved"
        self.db.commit()
        self.db.refresh(action)
        return self._result(action)

    def _publishing_actions(self, campaign: models.Campaign) -> None:
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        if not product_ids:
            return
        approved = self.db.scalars(
            select(models.PublishingPackage)
            .where(
                models.PublishingPackage.product_id.in_(product_ids),
                models.PublishingPackage.review_status == "approved",
                models.PublishingPackage.status.in_(["approved", "ready", "scheduled", "published"]),
            )
        ).all()
        if not approved:
            self._upsert(
                campaign_id=campaign.id,
                product_id=None,
                sku=None,
                content_run_id=None,
                action_type="create_publishing_package",
                priority=60,
                reason="No approved publishing packages exist for campaign products.",
                blockers=["approved_video_required"],
                safe_to_execute=False,
                requires_human=True,
            )
            return
        latest_plan = self.db.scalar(
            select(models.CampaignDistributionPlan)
            .where(models.CampaignDistributionPlan.campaign_id == campaign.id)
            .order_by(models.CampaignDistributionPlan.id.desc())
        )
        if not latest_plan or latest_plan.blockers_json:
            self._upsert(
                campaign_id=campaign.id,
                product_id=None,
                sku=None,
                content_run_id=None,
                action_type="schedule_distribution",
                priority=70,
                reason="Distribution is not ready or still has blockers.",
                blockers=(latest_plan.blockers_json if latest_plan else ["no_distribution_plan"]),
                safe_to_execute=False,
                requires_human=True,
            )

    def _upsert(
        self,
        *,
        campaign_id: int,
        product_id: int | None,
        sku: str | None,
        content_run_id: int | None,
        action_type: str,
        priority: int,
        reason: str,
        blockers: list[str],
        safe_to_execute: bool,
        requires_human: bool,
    ) -> models.CampaignActionQueueItem:
        query = select(models.CampaignActionQueueItem).where(
            models.CampaignActionQueueItem.campaign_id == campaign_id,
            models.CampaignActionQueueItem.action_type == action_type,
            models.CampaignActionQueueItem.status.in_(["open", "blocked"]),
        )
        if content_run_id is None:
            query = query.where(models.CampaignActionQueueItem.content_run_id.is_(None))
        else:
            query = query.where(models.CampaignActionQueueItem.content_run_id == content_run_id)
        if sku is None:
            query = query.where(models.CampaignActionQueueItem.sku.is_(None))
        else:
            query = query.where(models.CampaignActionQueueItem.sku == sku)
        item = self.db.scalar(query.order_by(models.CampaignActionQueueItem.id.desc()))
        if not item:
            item = models.CampaignActionQueueItem(
                campaign_id=campaign_id,
                product_id=product_id,
                sku=sku,
                content_run_id=content_run_id,
                action_type=action_type,
            )
            self.db.add(item)
        item.priority = priority
        item.reason = reason
        item.blockers_json = list(dict.fromkeys(blockers))
        item.safe_to_execute = safe_to_execute
        item.requires_human = requires_human
        if item.status not in {"open", "blocked"}:
            item.status = "open"
        self.db.flush()
        return item

    def _publishing_allowed(self, action: models.CampaignActionQueueItem) -> bool:
        campaign = self._campaign(action.campaign_id)
        product_ids = [int(product_id) for product_id in (campaign.product_ids_json or [])]
        if not product_ids:
            return False
        return bool(
            self.db.scalar(
                select(models.PublishingPackage)
                .where(
                    models.PublishingPackage.product_id.in_(product_ids),
                    models.PublishingPackage.review_status == "approved",
                    models.PublishingPackage.status.in_(["approved", "ready", "scheduled", "published"]),
                )
                .order_by(models.PublishingPackage.id.desc())
            )
        )

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignExecutionDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _action(self, action_id: int) -> models.CampaignActionQueueItem:
        action = self.db.get(models.CampaignActionQueueItem, action_id)
        if not action:
            raise CampaignExecutionDataError(f"CampaignActionQueueItem {action_id} not found.")
        return action

    @staticmethod
    def _result(item: models.CampaignActionQueueItem) -> ActionQueueItemResult:
        return ActionQueueItemResult(
            action_id=item.id,
            campaign_id=item.campaign_id,
            product_id=item.product_id,
            sku=item.sku,
            content_run_id=item.content_run_id,
            action_type=item.action_type,
            priority=item.priority,
            status=item.status,
            reason=item.reason,
            blockers=item.blockers_json or [],
            safe_to_execute=item.safe_to_execute,
            requires_human=item.requires_human,
        )
