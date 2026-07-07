from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.content_factory.agent_registry import ContentAgentRegistry
from app.content_factory.ai_review_service import AIContentReviewService
from app.content_factory.assignment_service import ContentAssignmentService
from app.content_factory.errors import ContentFactoryDataError
from app.content_factory.readiness import control_loop_readiness
from app.content_factory.recommendation_service import RecommendationService
from app.content_factory.types import ContentNextAction, ContentRunResult
from app.demand.errors import DemandError
from app.intelligence.errors import IntelligenceError
from app.variants.errors import VariantError
from app.video_generator.errors import VideoGeneratorError
from app.workflows.working_video_generator import WorkingVideoGenerator, WorkingVideoPrepareResult


class ContentRunOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.registry = ContentAgentRegistry(db)
        self.assignments = ContentAssignmentService(db)
        self.recommendations = RecommendationService(db)

    def prepare_content_run(
        self,
        product_id: int,
        platform: str,
        duration_seconds: int,
        variant_count: int,
    ) -> ContentRunResult:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise ContentFactoryDataError(f"Product {product_id} not found.")
        self.registry.ensure_defaults()
        content_run = models.ContentRun(
            product_id=product_id,
            platform=platform,
            duration_seconds=duration_seconds,
            variant_count=variant_count,
            status="preparing",
            run_json={"stage": "created_by_content_factory"},
        )
        self.db.add(content_run)
        self.db.commit()
        self.db.refresh(content_run)

        try:
            result = WorkingVideoGenerator(self.db).prepare(product_id, platform, duration_seconds, variant_count)
        except (DemandError, IntelligenceError, VariantError, VideoGeneratorError) as exc:
            content_run.status = "blocked"
            content_run.blockers_json = [str(exc)]
            content_run.run_json = {"error": str(exc), "stage": "prepare_failed"}
            self.db.commit()
            self.assignments.record(
                content_run=content_run,
                assignment_type="demand",
                status="blocked",
                input_json={"product_id": product_id},
                blockers=[str(exc)],
            )
            return self._result(content_run)

        self._apply_working_result(content_run, result)
        self._record_prepare_assignments(content_run, result)
        review = AIContentReviewService(self.db).review(content_run)
        self._sync_recommendations(content_run)
        self.assignments.record(
            content_run=content_run,
            assignment_type="review",
            status=review.status,
            input_json={"content_run_id": content_run.id},
            output_json=review.review_json,
            blockers=review.blockers_json,
        )
        return self._result(content_run)

    def run_prompt_only(self, content_run_id: int) -> ContentRunResult:
        content_run = self._run(content_run_id)
        if not content_run.selected_variant_id:
            raise ContentFactoryDataError("ContentRun does not have a selected variant yet.")
        result = WorkingVideoGenerator(self.db).run_prompt_only(content_run.selected_variant_id, provider="runway")
        self._apply_working_result(content_run, result, force_status="prompt_ready")
        self.assignments.record(
            content_run=content_run,
            assignment_type="video",
            status="prompt_ready",
            input_json={"content_run_id": content_run.id, "selected_variant_id": content_run.selected_variant_id},
            output_json={"generation_variant_id": content_run.generation_variant_id, "prompt_pack_id": content_run.prompt_pack_id},
        )
        self._sync_recommendations(content_run)
        return self._result(content_run)

    def run_real_smoke(
        self,
        content_run_id: int,
        *,
        provider: str = "runway",
        allow_real_spend: bool = False,
    ) -> ContentRunResult:
        content_run = self._run(content_run_id)
        if not content_run.selected_variant_id:
            raise ContentFactoryDataError("ContentRun does not have a selected variant yet.")
        output = WorkingVideoGenerator(self.db).run_real_smoke(
            content_run.selected_variant_id,
            provider=provider,
            allow_real_spend=allow_real_spend,
            max_scenes=1,
        )
        content_run.video_job_id = output.video_job_id
        content_run.status = "real_smoke_created" if output.video_job_id else "real_smoke_pending"
        content_run.run_json = {
            **(content_run.run_json or {}),
            "real_smoke": output.model_dump(mode="json"),
        }
        self.db.commit()
        review = AIContentReviewService(self.db).review(content_run)
        self.assignments.record(
            content_run=content_run,
            assignment_type="video",
            status=content_run.status,
            input_json={"content_run_id": content_run.id, "provider": provider, "max_scenes": 1},
            output_json=output.model_dump(mode="json"),
        )
        self.assignments.record(
            content_run=content_run,
            assignment_type="review",
            status=review.status,
            input_json={"content_run_id": content_run.id},
            output_json=review.review_json,
            blockers=review.blockers_json,
        )
        self._sync_recommendations(content_run)
        return self._result(content_run)

    def review(self, content_run_id: int) -> ContentRunResult:
        content_run = self._run(content_run_id)
        review = AIContentReviewService(self.db).review(content_run)
        self.assignments.record(
            content_run=content_run,
            assignment_type="review",
            status=review.status,
            input_json={"content_run_id": content_run.id},
            output_json=review.review_json,
            blockers=review.blockers_json,
        )
        self._sync_recommendations(content_run)
        return self._result(content_run)

    def recommend_next_action(self, content_run_id: int) -> list[ContentNextAction]:
        content_run = self._run(content_run_id)
        return self._sync_recommendations(content_run)

    def get(self, content_run_id: int) -> ContentRunResult:
        return self._result(self._run(content_run_id))

    def _apply_working_result(
        self,
        content_run: models.ContentRun,
        result: WorkingVideoPrepareResult,
        *,
        force_status: str | None = None,
    ) -> None:
        selected_variant = self.db.get(models.CreativeVariant, result.selected_variant_id) if result.selected_variant_id else None
        blockers = list(result.real_smoke_blockers or [])
        content_blockers = [item for item in blockers if not item.startswith("spend_gate:")]
        status = force_status
        if not status:
            status = "blocked" if content_blockers else "ready_for_real_smoke"
        content_run.status = status
        content_run.demand_hypothesis_id = result.demand_hypothesis_id
        content_run.creative_spec_id = result.creative_spec_id
        content_run.asset_kit_id = result.asset_kit_id
        content_run.creative_variant_set_id = selected_variant.creative_variant_set_id if selected_variant else None
        content_run.selected_variant_id = result.selected_variant_id
        content_run.generation_variant_id = result.generation_variant_id
        content_run.prompt_pack_id = result.prompt_pack_id
        content_run.blockers_json = blockers
        content_run.warnings_json = result.warnings
        content_run.run_json = {
            "sku": result.sku,
            "buyer_need": result.buyer_need,
            "trigger_situation": result.trigger_situation,
            "pain_point": result.pain_point,
            "objection": result.objection,
            "safe_promise": result.safe_promise,
            "source_refs": result.source_refs,
            "missing_data": result.missing_data,
            "demand_validation": result.demand_validation,
            "selected_hook": result.selected_hook,
            "selected_hook_type": result.selected_hook_type,
            "first_frame": result.first_frame,
            "reference_readiness": result.reference_readiness,
            "reference_policy": result.reference_policy,
            "selected_variant_score": result.selected_variant_score,
            "prompt_pack": result.prompt_pack,
            "real_smoke_eligible": result.real_smoke_eligible,
            "provider_status": result.provider_status,
        }
        readiness = control_loop_readiness(self.db, content_run)
        content_run.run_json = {
            **content_run.run_json,
            **readiness,
            "ai_factory_control_loop": True,
            "review_status": None,
            "human_review_required": True,
            "next_action": None,
        }
        content_run.blockers_json = list(
            dict.fromkeys(
                [
                    *blockers,
                    *readiness["product_identity_blockers"],
                    *readiness["geometry_scale_blockers"],
                ]
            )
        )
        self.db.commit()
        self.db.refresh(content_run)

    def _record_prepare_assignments(self, content_run: models.ContentRun, result: WorkingVideoPrepareResult) -> None:
        self.assignments.record(
            content_run=content_run,
            assignment_type="demand",
            status="completed",
            input_json={"product_id": content_run.product_id},
            output_json={
                "demand_hypothesis_id": result.demand_hypothesis_id,
                "buyer_need": result.buyer_need,
                "safe_promise": result.safe_promise,
            },
        )
        self.assignments.record(
            content_run=content_run,
            assignment_type="creative_brief",
            status="completed",
            input_json={"demand_hypothesis_id": result.demand_hypothesis_id},
            output_json={"creative_spec_id": result.creative_spec_id, "selected_hook": result.selected_hook},
        )
        self.assignments.record(
            content_run=content_run,
            assignment_type="variant",
            status="completed",
            input_json={"creative_spec_id": result.creative_spec_id, "variant_count": content_run.variant_count},
            output_json={
                "selected_variant_id": result.selected_variant_id,
                "first_frame": result.first_frame,
                "selected_variant_score": result.selected_variant_score,
            },
        )
        self.assignments.record(
            content_run=content_run,
            assignment_type="video",
            status="prompt_ready" if result.prompt_pack_id else "blocked",
            input_json={"selected_variant_id": result.selected_variant_id},
            output_json={"generation_variant_id": result.generation_variant_id, "prompt_pack_id": result.prompt_pack_id},
            blockers=result.real_smoke_blockers,
        )
        self.assignments.record(
            content_run=content_run,
            assignment_type="publishing_prep",
            status="waiting_for_approval",
            input_json={"content_run_id": content_run.id},
            output_json={"approval_required": True, "auto_publish": False},
        )

    def _sync_recommendations(self, content_run: models.ContentRun) -> list[ContentNextAction]:
        actions = self.recommendations.recommend(content_run)
        content_run.next_actions_json = [action.model_dump(mode="json") for action in actions]
        run_json = content_run.run_json or {}
        content_run.run_json = {
            **run_json,
            "next_action": actions[0].action if actions else None,
        }
        self.db.commit()
        self.db.refresh(content_run)
        return actions

    def _result(self, content_run: models.ContentRun) -> ContentRunResult:
        actions = [
            action if isinstance(action, ContentNextAction) else ContentNextAction.model_validate(action)
            for action in (content_run.next_actions_json or [])
        ]
        return ContentRunResult(
            id=content_run.id,
            status=content_run.status,
            product_id=content_run.product_id,
            sku=content_run.product.sku if content_run.product else None,
            platform=content_run.platform,
            duration_seconds=content_run.duration_seconds,
            variant_count=content_run.variant_count,
            demand_hypothesis_id=content_run.demand_hypothesis_id,
            creative_spec_id=content_run.creative_spec_id,
            asset_kit_id=content_run.asset_kit_id,
            creative_variant_set_id=content_run.creative_variant_set_id,
            selected_variant_id=content_run.selected_variant_id,
            generation_variant_id=content_run.generation_variant_id,
            prompt_pack_id=content_run.prompt_pack_id,
            video_job_id=content_run.video_job_id,
            ai_review_id=content_run.latest_ai_review_id,
            blockers=content_run.blockers_json or [],
            next_actions=actions,
            warnings=content_run.warnings_json or [],
            run=content_run.run_json or {},
            buyer_need=(content_run.run_json or {}).get("buyer_need"),
            safe_promise=(content_run.run_json or {}).get("safe_promise"),
            reference_readiness=(content_run.run_json or {}).get("reference_readiness") or {},
            reference_policy=(content_run.run_json or {}).get("reference_policy") or {},
            geometry_readiness=(content_run.run_json or {}).get("geometry_readiness") or {},
            product_identity_readiness=(content_run.run_json or {}).get("product_identity_readiness") or {},
            publishing_readiness=(content_run.run_json or {}).get("publishing_readiness") or {},
            ai_review_status=(content_run.run_json or {}).get("review_status"),
            human_review_required=(content_run.run_json or {}).get("human_review_required"),
            next_action=(content_run.run_json or {}).get("next_action"),
        )

    def _run(self, content_run_id: int) -> models.ContentRun:
        content_run = self.db.scalar(select(models.ContentRun).where(models.ContentRun.id == content_run_id))
        if not content_run:
            raise ContentFactoryDataError(f"ContentRun {content_run_id} not found.")
        return content_run
