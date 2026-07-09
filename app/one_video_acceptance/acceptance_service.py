from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.intelligence.errors import ProviderConfigurationError
from app.one_video_acceptance.bombbar_render_plan import BombbarOneVideoRenderPlanner
from app.one_video_acceptance.errors import OneVideoAcceptanceDataError
from app.one_video_acceptance.mvp_scorecard import MVPScorecardBuilder
from app.one_video_acceptance.prompt_specializer import BombbarPromptSpecializer
from app.one_video_acceptance.types import OneVideoRenderResultOutput, OneVideoScene, ProductScenePolicyOutput
from app.output_acceptance import AcceptanceReviewService, FrameExtractor, OutputAcceptanceError
from app.video_generator.generator import VideoGenerator
from app.video_generator.real_smoke_runner import RealSmokeRunner


class OneVideoAcceptanceService:
    def __init__(self, db: Session):
        self.db = db
        self.planner = BombbarOneVideoRenderPlanner(db)
        self.specializer = BombbarPromptSpecializer()

    def build_plan(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        duration_seconds: int = 15,
        provider: str = "runway",
    ) -> models.OneVideoRenderPlan:
        return self.planner.build(
            product_id,
            platform=platform,
            duration_seconds=duration_seconds,
            provider=provider,
        )

    def prompt_only(self, plan_id: int, *, provider: str = "runway") -> models.OneVideoRenderPlan:
        plan = self.planner.get(plan_id)
        if not plan.creative_variant_id:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderPlan {plan.id} has no selected CreativeVariant.")
        generation_variant = VideoGenerator(self.db).build_prompt_pack_from_variant(plan.creative_variant_id, provider=provider)
        self.specializer.apply_to_generation_variant(plan, generation_variant)
        plan.prompt_pack_id = generation_variant.prompt_pack_id
        plan.video_generation_variant_id = generation_variant.id
        plan.prompt_preview_json = {
            **(plan.prompt_preview_json or {}),
            "prompt_pack_id": generation_variant.prompt_pack_id,
            "video_generation_variant_id": generation_variant.id,
            "prompt_pack": generation_variant.prompt_pack_json,
        }
        plan.status = "prompt_only_ready"
        if plan.director_prompt_pack:
            plan.director_prompt_pack.prompt_pack_id = generation_variant.prompt_pack_id
            plan.director_prompt_pack.provider_prompt_json = plan.prompt_preview_json
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def run_real(
        self,
        plan_id: int,
        *,
        provider: str = "runway",
        real_run: bool = False,
        max_scenes: int = 1,
    ) -> models.OneVideoRenderResult:
        plan = self.planner.get(plan_id)
        if not real_run:
            raise ProviderConfigurationError("One-video paid smoke requires explicit --real-run.")
        if plan.blockers_json:
            raise ProviderConfigurationError("One-video render plan has blockers: " + ", ".join(plan.blockers_json))
        if not plan.creative_variant_id:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderPlan {plan.id} has no selected CreativeVariant.")

        result = models.OneVideoRenderResult(
            plan_id=plan.id,
            product_id=plan.product_id,
            creative_variant_id=plan.creative_variant_id,
            provider=provider,
            status="real_run_started",
            max_scenes=max_scenes,
            human_review_status="needs_human_review",
            warnings_json=plan.warnings_json or [],
        )
        self.db.add(result)
        self.db.flush()
        try:
            output = RealSmokeRunner(self.db).run_from_variant(
                plan.creative_variant_id,
                provider=provider,
                max_scenes=max_scenes,
                full_video=False,
                allow_real_spend=True,
            )
            generation_variant = self._generation_variant_for_video_job(output.video_job_id)
            video_job = self.db.get(models.VideoJob, output.video_job_id) if output.video_job_id else None
            if generation_variant:
                self.specializer.apply_to_generation_variant(plan, generation_variant)
                plan.prompt_pack_id = generation_variant.prompt_pack_id
                plan.video_generation_variant_id = generation_variant.id
                result.video_generation_variant_id = generation_variant.id
            result.prompt_pack_id = output.prompt_pack_id or plan.prompt_pack_id
            result.video_job_id = output.video_job_id
            result.status = output.status
            result.provider_job_ids_json = output.provider_job_ids
            result.local_output_paths_json = output.local_output_paths
            result.final_video_path = output.final_video_path
            result.generation_report_path = output.generation_report_path
            result.result_json = output.model_dump(mode="json")
            result.errors_json = output.errors
            result.warnings_json = list(dict.fromkeys((result.warnings_json or []) + output.warnings))
            plan.status = "real_run_completed_needs_review"
            if plan.director_prompt_pack and result.prompt_pack_id:
                plan.director_prompt_pack.prompt_pack_id = result.prompt_pack_id
            if video_job:
                self._extract_frames_if_possible(video_job.id, result)
                acceptance = self._create_initial_output_acceptance(plan, video_job.id)
                result.output_acceptance_id = acceptance.id
                result.human_review_status = acceptance.status
            self.db.commit()
            self.db.refresh(result)
            return result
        except Exception as exc:
            if self._is_provider_credit_error(exc):
                result.status = "blocked_by_runway_credits"
                result.human_review_status = "blocked"
                result.result_json = {
                    **(result.result_json or {}),
                    "blocker": "blocked_by_runway_credits",
                    "next_action": "add_runway_credits_then_rerun_one_scene_real_smoke",
                    "provider": provider,
                }
                plan.status = "real_run_blocked_by_runway_credits"
            else:
                result.status = "failed_generation"
                plan.status = "real_run_failed"
            result.errors_json = list(dict.fromkeys([*(result.errors_json or []), str(exc)]))
            self.db.commit()
            self.db.refresh(result)
            if self._is_provider_credit_error(exc):
                return result
            raise

    def review(self, result_id: int, *, status: str, notes: str | None = None) -> models.OneVideoRenderResult:
        result = self.get_result(result_id)
        plan = self.planner.get(result.plan_id)
        result.human_review_status = status
        result.human_review_notes = notes
        result.status = status
        blockers = self._blockers_from_review(status, notes)
        acceptance = self._upsert_manual_acceptance(result, plan, status=status, notes=notes, blockers=blockers)
        result.output_acceptance_id = acceptance.id
        scorecard = MVPScorecardBuilder().build_for_plan(
            ProductScenePolicyOutput.model_validate(plan.product_scene_policy_json or {}),
            [OneVideoScene.model_validate(scene) for scene in plan.scene_plan_json or []],
            human_review_recorded=True,
        )
        result.result_json = {
            **(result.result_json or {}),
            "manual_review_status": status,
            "manual_review_notes": notes,
            "manual_review_blockers": blockers,
            "mvp_scorecard": scorecard.model_dump(mode="json"),
        }
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_result(self, result_id: int) -> models.OneVideoRenderResult:
        result = self.db.get(models.OneVideoRenderResult, result_id)
        if not result:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderResult {result_id} not found.")
        return result

    def latest_result(self, plan_id: int | None = None) -> models.OneVideoRenderResult | None:
        query = select(models.OneVideoRenderResult).order_by(models.OneVideoRenderResult.id.desc())
        if plan_id:
            query = query.where(models.OneVideoRenderResult.plan_id == plan_id)
        return self.db.scalar(query)

    def list_results(self, plan_id: int | None = None, limit: int = 20) -> list[models.OneVideoRenderResult]:
        query = select(models.OneVideoRenderResult).order_by(models.OneVideoRenderResult.id.desc()).limit(limit)
        if plan_id:
            query = query.where(models.OneVideoRenderResult.plan_id == plan_id)
        return list(self.db.scalars(query))

    @staticmethod
    def as_result_output(result: models.OneVideoRenderResult) -> OneVideoRenderResultOutput:
        return OneVideoRenderResultOutput(
            id=result.id,
            plan_id=result.plan_id,
            product_id=result.product_id,
            creative_variant_id=result.creative_variant_id,
            video_generation_variant_id=result.video_generation_variant_id,
            prompt_pack_id=result.prompt_pack_id,
            video_job_id=result.video_job_id,
            output_acceptance_id=result.output_acceptance_id,
            provider=result.provider,
            status=result.status,
            max_scenes=result.max_scenes,
            provider_job_ids=result.provider_job_ids_json or [],
            local_output_paths=result.local_output_paths_json or [],
            final_video_path=result.final_video_path,
            generation_report_path=result.generation_report_path,
            human_review_status=result.human_review_status,
            human_review_notes=result.human_review_notes,
            result=result.result_json or {},
            errors=result.errors_json or [],
            warnings=result.warnings_json or [],
        )

    def _generation_variant_for_video_job(self, video_job_id: int | None) -> models.VideoGenerationVariant | None:
        if not video_job_id:
            return None
        return self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.video_job_id == video_job_id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )

    def _extract_frames_if_possible(self, video_job_id: int, result: models.OneVideoRenderResult) -> None:
        try:
            FrameExtractor(self.db).extract(video_job_id, max_frames=5)
        except OutputAcceptanceError as exc:
            result.warnings_json = list(dict.fromkeys([*(result.warnings_json or []), f"frame_extraction_skipped:{exc}"]))

    def _create_initial_output_acceptance(self, plan: models.OneVideoRenderPlan, video_job_id: int) -> models.VideoOutputAcceptance:
        if not plan.ai_production_brief_id:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderPlan {plan.id} has no AIProductionBrief.")
        return AcceptanceReviewService(self.db).review(
            video_job_id=video_job_id,
            ai_production_brief_id=plan.ai_production_brief_id,
            director_prompt_pack_id=plan.director_prompt_pack_id,
            decision="needs_human_review",
            product_identity_status="needs_review",
            packaging_status="needs_review",
            geometry_status="needs_review",
            blogger_authenticity_status="needs_review",
            scene_match_status="needs_review",
            proof_moment_status="needs_review",
            cta_status="needs_review",
            reviewer_notes="Auto-created after one-video real smoke. Manual visual review required; no auto-approval.",
        )

    def _upsert_manual_acceptance(
        self,
        result: models.OneVideoRenderResult,
        plan: models.OneVideoRenderPlan,
        *,
        status: str,
        notes: str | None,
        blockers: list[str],
    ) -> models.VideoOutputAcceptance:
        if not result.video_job_id:
            raise OneVideoAcceptanceDataError("Cannot create output acceptance review before a video_job_id exists.")
        if not plan.ai_production_brief_id:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderPlan {plan.id} has no AIProductionBrief.")
        acceptance = self.db.get(models.VideoOutputAcceptance, result.output_acceptance_id) if result.output_acceptance_id else None
        if not acceptance:
            acceptance = models.VideoOutputAcceptance(
                video_job_id=result.video_job_id,
                ai_production_brief_id=plan.ai_production_brief_id,
                director_prompt_pack_id=plan.director_prompt_pack_id,
            )
            self.db.add(acceptance)
            self.db.flush()
        pass_status = "pass" if status == "approved" else "needs_review"
        fail_status = "fail" if status in {"needs_regeneration", "rejected"} else pass_status
        acceptance.status = status
        acceptance.product_identity_status = fail_status
        acceptance.packaging_status = fail_status
        acceptance.geometry_status = fail_status if "geometry_drift" in blockers else pass_status
        acceptance.blogger_authenticity_status = pass_status
        acceptance.scene_match_status = fail_status if status != "approved" else "pass"
        acceptance.proof_moment_status = pass_status if status == "approved" else "needs_review"
        acceptance.cta_status = pass_status if status == "approved" else "needs_review"
        acceptance.publishing_readiness = "ready" if status == "approved" and not blockers else "blocked"
        acceptance.score = 100 if status == "approved" else max(0, 70 - 10 * len(blockers))
        acceptance.blockers_json = blockers
        acceptance.required_fixes_json = self._fixes_from_blockers(blockers)
        acceptance.reviewer_notes = notes
        return acceptance

    @staticmethod
    def _blockers_from_review(status: str, notes: str | None) -> list[str]:
        blockers = []
        normalized = (notes or "").lower()
        if status in {"needs_regeneration", "rejected"}:
            blockers.append("manual_review_requires_regeneration")
        if "wrapper" in normalized or "упаков" in normalized or "label" in normalized or "logo" in normalized:
            blockers.append("packaging_drift")
        if "muesli" in normalized or "granola" in normalized or "мюсли" in normalized or "гранол" in normalized:
            blockers.append("edible_product_drift")
        if "geometry" in normalized or "пропорц" in normalized or "deform" in normalized:
            blockers.append("geometry_drift")
        return list(dict.fromkeys(blockers))

    @staticmethod
    def _fixes_from_blockers(blockers: list[str]) -> list[str]:
        fixes = []
        if "packaging_drift" in blockers:
            fixes.append("switch_to_packshot_overlay_or_end_card")
        if "edible_product_drift" in blockers:
            fixes.append("block_bite_scene_until_edible_refs_ready")
        if "geometry_drift" in blockers:
            fixes.append("regenerate_with_geometry_feedback")
        if "manual_review_requires_regeneration" in blockers:
            fixes.append("request_regeneration")
        return list(dict.fromkeys(fixes))

    @staticmethod
    def _is_provider_credit_error(exc: Exception) -> bool:
        normalized = str(exc).lower()
        credit_markers = [
            "do not have enough credits",
            "not have enough credits",
            "not enough credits",
            "insufficient credits",
            "runway credits",
            "no credits",
        ]
        return any(marker in normalized for marker in credit_markers)
