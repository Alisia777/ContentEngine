from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.campaign_state_service import CampaignStateService
from app.campaign_autopilot.errors import CampaignAutopilotDataError
from app.campaign_autopilot.target_allocator import TargetAllocator
from app.campaign_autopilot.types import CampaignPrepareResult, CampaignReport
from app.content_factory import ContentRunOrchestrator
from app.content_factory.errors import ContentFactoryError


class CampaignRunner:
    def __init__(self, db: Session):
        self.db = db

    def prepare_campaign(self, campaign_id: int) -> CampaignPrepareResult:
        campaign = self._campaign(campaign_id)
        TargetAllocator(self.db).allocate(campaign.id)
        campaign.status = "preparing"
        campaign_products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        campaign_run = models.CampaignRun(
            campaign_id=campaign.id,
            status="running",
            total_products=len(campaign_products),
            total_target_videos=campaign.target_video_count,
            summary_json={"stage": "prepare_campaign"},
        )
        self.db.add(campaign_run)
        self.db.commit()
        orchestrator = ContentRunOrchestrator(self.db)
        product_results = []
        all_blockers: list[str] = []
        for item in campaign_products:
            runs_per_sku = min(2, max(1, item.target_prompt_count))
            variant_count = max(1, math.ceil(item.target_prompt_count / runs_per_sku))
            created_ids = list(item.content_run_ids_json or [])
            for _ in range(max(0, runs_per_sku - len(created_ids))):
                try:
                    result = orchestrator.prepare_content_run(item.product_id, "Instagram Reels", 15, variant_count)
                    created_ids.append(result.id)
                    all_blockers.extend(f"{item.sku}:{blocker}" for blocker in result.blockers)
                    if not result.prompt_pack_id and self._missing_reference_product(item.product_id):
                        fallback = self._fallback_prompt_ready_run(
                            item,
                            "; ".join(result.blockers) or "content autopilot returned no prompt pack",
                            variant_count,
                        )
                        created_ids.append(fallback.id)
                        item.blockers_json = list(
                            dict.fromkeys([*(item.blockers_json or []), "missing_reference_blocks_real_video"])
                        )
                except ContentFactoryError as exc:
                    fallback = self._fallback_prompt_ready_run(item, str(exc), variant_count)
                    created_ids.append(fallback.id)
                    blocker = "missing_reference_blocks_real_video"
                    item.blockers_json = list(dict.fromkeys([*(item.blockers_json or []), blocker, str(exc)]))
                    all_blockers.append(f"{item.sku}:{blocker}")
                    break
            item.content_run_ids_json = created_ids
            product_results.append({"sku": item.sku, "content_run_ids": created_ids, "blockers": item.blockers_json or []})
        state = CampaignStateService(self.db).inspect_campaign(campaign.id)
        campaign_run.status = "blocked" if state.blocked_count else "ready_for_review"
        campaign_run.total_content_runs = sum(len(item["content_run_ids"]) for item in product_results)
        campaign_run.total_prompt_ready = state.prompt_ready_count
        campaign_run.total_real_smoke_ready = state.real_smoke_ready_count
        campaign_run.total_needs_review = state.needs_human_review
        campaign_run.total_blocked = state.blocked_count
        campaign_run.total_approved = state.publishing_ready_count
        campaign_run.total_publishing_ready = state.publishing_ready_count
        campaign_run.summary_json = {
            "state": state.model_dump(mode="json"),
            "paid_provider_calls": False,
            "products": product_results,
        }
        campaign.status = "blocked" if state.blocked_count else "ready_for_review"
        self.db.commit()
        self.db.refresh(campaign_run)
        return CampaignPrepareResult(
            campaign_id=campaign.id,
            campaign_run_id=campaign_run.id,
            status=campaign_run.status,
            total_products=campaign_run.total_products,
            total_content_runs=campaign_run.total_content_runs,
            total_prompt_ready=campaign_run.total_prompt_ready,
            total_blocked=campaign_run.total_blocked,
            blockers=list(dict.fromkeys(all_blockers)),
            products=product_results,
        )

    def run_prompt_only_for_ready_items(self, campaign_id: int) -> CampaignPrepareResult:
        campaign = self._campaign(campaign_id)
        orchestrator = ContentRunOrchestrator(self.db)
        campaign_products = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        blockers: list[str] = []
        ran = []
        for item in campaign_products:
            for content_run_id in item.content_run_ids_json or []:
                run = self.db.get(models.ContentRun, content_run_id)
                if not run or not run.selected_variant_id:
                    continue
                if run.video_job_id:
                    continue
                if run.status not in {"ready_for_real_smoke", "prompt_ready", "blocked"} and not run.prompt_pack_id:
                    continue
                try:
                    result = orchestrator.run_prompt_only(run.id)
                    ran.append({"sku": item.sku, "content_run_id": result.id, "prompt_pack_id": result.prompt_pack_id})
                    blockers.extend(f"{item.sku}:{blocker}" for blocker in result.blockers)
                except ContentFactoryError as exc:
                    blockers.append(f"{item.sku}:{exc}")
        state = CampaignStateService(self.db).inspect_campaign(campaign.id)
        campaign_run = models.CampaignRun(
            campaign_id=campaign.id,
            status="prompt_only_complete",
            total_products=len(campaign_products),
            total_target_videos=campaign.target_video_count,
            total_content_runs=sum(len(item.content_run_ids_json or []) for item in campaign_products),
            total_prompt_ready=state.prompt_ready_count,
            total_real_smoke_ready=state.real_smoke_ready_count,
            total_needs_review=state.needs_human_review,
            total_blocked=state.blocked_count,
            total_approved=state.publishing_ready_count,
            total_publishing_ready=state.publishing_ready_count,
            summary_json={"prompt_only_runs": ran, "paid_provider_calls": False},
        )
        self.db.add(campaign_run)
        self.db.commit()
        return CampaignPrepareResult(
            campaign_id=campaign.id,
            campaign_run_id=campaign_run.id,
            status=campaign_run.status,
            total_products=campaign_run.total_products,
            total_content_runs=campaign_run.total_content_runs,
            total_prompt_ready=campaign_run.total_prompt_ready,
            total_blocked=campaign_run.total_blocked,
            blockers=list(dict.fromkeys(blockers)),
            products=ran,
        )

    def inspect_campaign(self, campaign_id: int):
        return CampaignStateService(self.db).inspect_campaign(campaign_id)

    def generate_campaign_report(self, campaign_id: int) -> CampaignReport:
        from app.campaign_autopilot.campaign_distribution_planner import CampaignDistributionPlanner
        from app.campaign_autopilot.campaign_performance_service import CampaignPerformanceService

        state = CampaignStateService(self.db).inspect_campaign(campaign_id)
        plan = CampaignDistributionPlanner(self.db).latest_plan(campaign_id)
        performance = CampaignPerformanceService(self.db).summarize(campaign_id)
        next_actions = []
        for item in state.next_actions_by_sku[:20]:
            for action in item.get("next_actions", []):
                next_actions.append({"sku": item["sku"], **action})
        return CampaignReport(
            campaign_id=campaign_id,
            state=state,
            performance=performance,
            distribution_plan=plan or {},
            next_actions=next_actions,
        )

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise CampaignAutopilotDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _fallback_prompt_ready_run(
        self,
        item: models.CampaignProduct,
        error: str,
        variant_count: int,
    ) -> models.ContentRun:
        product = self.db.get(models.Product, item.product_id)
        if not product:
            raise CampaignAutopilotDataError(f"Product {item.product_id} not found.")
        pack = models.CreativeIntelligencePackRecord(
            product_id=product.id,
            sku=product.sku,
            status="ready",
            pack_json={
                "source": "campaign_autopilot_fallback",
                "product_title": product.title,
                "objective": "prompt_only_reference_pending",
            },
            source_summary_json={"product": product.id, "fallback_reason": error},
            warnings_json=["reference_required_before_real_video"],
        )
        self.db.add(pack)
        self.db.flush()
        brief = models.ScriptBrief(
            product_id=product.id,
            intelligence_pack_id=pack.id,
            status="ready",
            objective="campaign_prompt_only",
            creative_angle="product_explanation",
            target_audience="campaign audience",
            brief_json={
                "safe_promise": "Show source-backed product facts without visual identity claims.",
                "missing_reference": not bool(product.images_json),
            },
            allowed_claims_json=product.benefits_json or [],
            missing_data_json=["approved_product_reference"],
            safety_warnings_json=["real video generation blocked until approved primary reference exists"],
        )
        self.db.add(brief)
        self.db.flush()
        scene = {
            "scene_number": 1,
            "prompt": f"Create a prompt-only plan for {product.title}. Keep the product reference pending and avoid inventing packaging details.",
            "caption": f"{product.title}: product facts first.",
            "cta": "Open the product card",
        }
        prompt_pack = models.PromptPack(
            script_brief_id=brief.id,
            status="ready",
            prompt_pack_json={
                "provider": "runway",
                "campaign_autopilot_fallback": True,
                "reference_required_before_real_video": True,
                "product_id": product.id,
                "sku": product.sku,
            },
            scene_prompts_json=[scene],
            negative_prompts_json=["do not invent packaging", "do not claim visual identity verification"],
            provider_payload_json={"build_prompts_only": True, "paid_provider_call": False},
        )
        self.db.add(prompt_pack)
        self.db.flush()
        content_run = models.ContentRun(
            product_id=product.id,
            platform="Instagram Reels",
            duration_seconds=15,
            variant_count=variant_count,
            status="prompt_ready",
            prompt_pack_id=prompt_pack.id,
            run_json={
                "stage": "campaign_autopilot_fallback_prompt_only",
                "safe_promise": "Prompt-only plan is ready; real video waits for approved references.",
                "reference_readiness": {"status": "blocked", "blockers": ["approved_product_reference_required"]},
                "real_smoke_eligible": False,
                "human_review_required": True,
                "next_action": "attach_reference",
            },
            blockers_json=["missing_reference_blocks_real_video", error],
            next_actions_json=[{"action": "attach_reference", "reason": "Approved product reference is required before real video."}],
            warnings_json=["fallback_prompt_pack_created_without_provider_call"],
        )
        self.db.add(content_run)
        self.db.commit()
        self.db.refresh(content_run)
        return content_run

    def _missing_reference_product(self, product_id: int) -> bool:
        product = self.db.get(models.Product, product_id)
        return not bool(product and product.images_json)
