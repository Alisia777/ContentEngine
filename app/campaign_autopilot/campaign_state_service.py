from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_autopilot.types import CampaignState


class CampaignStateService:
    def __init__(self, db: Session):
        self.db = db

    def inspect_campaign(self, campaign_id: int) -> CampaignState:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        product_ids = [item.product_id for item in products]
        content_runs = self.db.scalars(
            select(models.ContentRun)
            .where(models.ContentRun.product_id.in_(product_ids) if product_ids else False)
            .order_by(models.ContentRun.id)
        ).all()
        packages = self.db.scalars(
            select(models.PublishingPackage)
            .where(models.PublishingPackage.product_id.in_(product_ids) if product_ids else False)
            .order_by(models.PublishingPackage.id)
        ).all()
        approved_packages = [package for package in packages if self._approved(package)]
        blockers = Counter()
        missing_references = 0
        missing_geometry_lock = 0
        needs_human_review = 0
        prompt_ready = 0
        real_smoke_ready = 0
        blocked_count = 0
        next_actions = []
        runs_by_product: dict[int, list[models.ContentRun]] = {}
        for run in content_runs:
            runs_by_product.setdefault(run.product_id, []).append(run)
            prompt_ready += 1 if run.prompt_pack_id else 0
            real_smoke_ready += 1 if (run.run_json or {}).get("real_smoke_eligible") else 0
            if (run.run_json or {}).get("human_review_required"):
                needs_human_review += 1
            run_blockers = run.blockers_json or []
            if run.status == "blocked" or run_blockers:
                blocked_count += 1
            if any("reference" in blocker for blocker in run_blockers):
                missing_references += 1
            if any("geometry" in blocker for blocker in run_blockers):
                missing_geometry_lock += 1
            for blocker in run_blockers:
                blockers[blocker] += 1
        for item in products:
            item_runs = runs_by_product.get(item.product_id, [])
            item_packages = [package for package in approved_packages if package.product_id == item.product_id]
            item.prompt_ready_count = sum(1 for run in item_runs if run.prompt_pack_id)
            item.approved_video_count = len(item_packages)
            item.blocked_count = sum(1 for run in item_runs if run.status == "blocked" or run.blockers_json)
            item.needs_review_count = sum(1 for run in item_runs if (run.run_json or {}).get("human_review_required"))
            item.content_run_ids_json = [run.id for run in item_runs]
            item.blockers_json = list(dict.fromkeys(blocker for run in item_runs for blocker in (run.blockers_json or [])))
            item.status = self._product_status(item)
            item.next_actions_json = self._next_actions_for_product(item, item_runs)
            next_actions.append({"sku": item.sku, "status": item.status, "next_actions": item.next_actions_json})
        campaign.summary_json = {
            "sku_count": len(products),
            "content_run_count": len(content_runs),
            "prompt_ready_count": prompt_ready,
            "real_smoke_ready_count": real_smoke_ready,
            "blocked_count": blocked_count,
            "needs_human_review": needs_human_review,
            "publishing_ready_count": len(approved_packages),
        }
        self.db.commit()
        return CampaignState(
            campaign_id=campaign.id,
            status=campaign.status,
            sku_coverage={
                "total_sku": len(products),
                "with_content_runs": sum(1 for item in products if item.content_run_ids_json),
                "with_prompt_ready": sum(1 for item in products if item.prompt_ready_count > 0),
                "with_approved_video": sum(1 for item in products if item.approved_video_count > 0),
            },
            prompt_ready_count=prompt_ready,
            real_smoke_ready_count=real_smoke_ready,
            blocked_count=blocked_count,
            blockers_by_type=[{"blocker": blocker, "count": count} for blocker, count in blockers.most_common()],
            missing_references=missing_references,
            missing_geometry_lock=missing_geometry_lock,
            needs_human_review=needs_human_review,
            publishing_ready_count=len(approved_packages),
            next_actions_by_sku=next_actions,
        )

    @staticmethod
    def _approved(package: models.PublishingPackage) -> bool:
        return package.review_status == "approved" and package.status in {"approved", "ready", "scheduled", "published"}

    @staticmethod
    def _product_status(item: models.CampaignProduct) -> str:
        if item.approved_video_count:
            return "publishing_ready"
        if item.prompt_ready_count:
            return "prompt_ready"
        if item.blocked_count:
            return "blocked"
        if item.needs_review_count:
            return "needs_review"
        return "planned"

    @staticmethod
    def _next_actions_for_product(item: models.CampaignProduct, runs: list[models.ContentRun]) -> list[dict]:
        if not runs:
            return [{"action": "prepare_content", "reason": "No content run exists for SKU."}]
        if item.approved_video_count:
            return [{"action": "distribution_plan", "reason": "Approved package can be scheduled."}]
        if item.prompt_ready_count:
            return [{"action": "human_review", "reason": "Prompt-ready content needs approved video before publishing."}]
        if item.blockers_json:
            if any("reference" in blocker for blocker in item.blockers_json):
                return [{"action": "attach_reference", "reason": "Reference blocker prevents real video readiness."}]
            return [{"action": "resolve_blocker", "reason": item.blockers_json[0]}]
        return [{"action": "inspect", "reason": "SKU needs state refresh."}]
