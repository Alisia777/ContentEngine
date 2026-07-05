from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.content_factory.readiness import (
    content_run_prompt_pack,
    control_loop_readiness,
    generation_report_exists,
    latest_quality_review,
    product_geometry_mismatch_detected,
)
from app.content_factory.types import AIReviewResult
from app.video_generator.artifact_manager import ArtifactManager


REVIEW_MANAGED_BLOCKERS = {
    "prompt_pack_missing",
    "reference_readiness_unknown",
    "product_identity_constraints_missing",
    "geometry_lock_missing",
    "product_geometry_mismatch",
    "video_output_missing",
    "generation_report_missing",
    "quality_review_missing",
}


class AIContentReviewService:
    def __init__(self, db: Session):
        self.db = db

    def review(self, content_run: models.ContentRun) -> models.AIContentReview:
        result = self.evaluate(content_run)
        review = models.AIContentReview(
            content_run_id=content_run.id,
            status=result.status,
            score=result.score,
            human_review_required=result.human_review_required,
            review_json=result.model_dump(mode="json"),
            blockers_json=result.blockers,
            warnings_json=result.warnings,
        )
        self.db.add(review)
        self.db.flush()
        content_run.latest_ai_review_id = review.id
        existing_blockers = [
            blocker
            for blocker in (content_run.blockers_json or [])
            if blocker not in REVIEW_MANAGED_BLOCKERS and not blocker.startswith("reference:")
        ]
        content_run.blockers_json = list(dict.fromkeys([*existing_blockers, *result.blockers]))
        readiness = control_loop_readiness(self.db, content_run)
        content_run.run_json = {
            **(content_run.run_json or {}),
            **readiness,
            "review_status": result.status,
            "human_review_required": result.human_review_required,
        }
        if result.status == "blocked":
            content_run.status = "blocked"
        elif result.status == "needs_regeneration":
            content_run.status = "needs_regeneration"
        elif result.human_review_required:
            content_run.status = "needs_human_review"
        self.db.commit()
        self.db.refresh(review)
        return review

    def evaluate(self, content_run: models.ContentRun) -> AIReviewResult:
        run = content_run.run_json or {}
        prompt_pack = content_run_prompt_pack(content_run)
        control_readiness = control_loop_readiness(self.db, content_run)
        readiness = control_readiness["reference_readiness"]
        identity = control_readiness["product_identity_readiness"]
        geometry = control_readiness["geometry_readiness"]
        publishing = control_readiness["publishing_readiness"]
        video_job = content_run.video_job
        quality_review = latest_quality_review(self.db, content_run)
        output_exists, output_non_empty = ArtifactManager.file_exists_and_non_empty(
            video_job.output_video_path if video_job else None
        )
        report_exists = generation_report_exists(content_run)
        video_generated = bool(content_run.video_job_id)
        checks = [
            self._check("demand_hypothesis_created", bool(content_run.demand_hypothesis_id)),
            self._check("demand_buyer_need_exists", bool(run.get("buyer_need"))),
            self._check("safe_promise_exists", bool(run.get("safe_promise"))),
            self._check("creative_spec_created", bool(content_run.creative_spec_id)),
            self._check("selected_variant_created", bool(content_run.selected_variant_id)),
            self._check("prompt_pack_created", bool(content_run.prompt_pack_id)),
            self._check("reference_readiness_known", bool(readiness.get("status"))),
            self._check("prompt_has_scene_prompts", bool(prompt_pack.get("scene_prompts"))),
            self._check("product_identity_constraints_present", identity["status"] == "ready"),
            self._check("product_geometry_rules_present", geometry["geometry_rules_present"]),
            self._check("product_scale_rules_present", geometry["scale_rules_present"]),
            self._check(
                "negative_prompt_blocks_size_proportion_drift",
                geometry["negative_prompt_blocks_geometry_drift"],
            ),
            self._check("video_output_exists_if_generated", not video_generated or output_exists),
            self._check("video_output_non_empty_if_generated", not video_generated or output_non_empty),
            self._check("generation_report_exists_if_generated", not video_generated or report_exists),
            self._check("quality_review_status_known_if_generated", not video_generated or bool(quality_review)),
            self._check("publishing_package_readiness_known", bool(publishing.get("status"))),
        ]
        blockers = []
        if not content_run.prompt_pack_id:
            blockers.append("prompt_pack_missing")
        if readiness.get("status") not in {"ready", "blocked", "missing"}:
            blockers.append("reference_readiness_unknown")
        if readiness.get("status") != "ready":
            blockers.extend(f"reference:{item}" for item in readiness.get("blockers") or [])
        blockers.extend(identity["blockers"])
        blockers.extend(geometry["blockers"])
        if video_generated and not output_exists:
            blockers.append("video_output_missing")
        if video_generated and not report_exists:
            blockers.append("generation_report_missing")
        if video_generated and not quality_review:
            blockers.append("quality_review_missing")
        if product_geometry_mismatch_detected(self.db, content_run):
            blockers.append("product_geometry_mismatch")

        passed = sum(1 for check in checks if check["passed"])
        score = round(passed / len(checks), 3) if checks else 0
        unique_blockers = list(dict.fromkeys(blockers))
        if "product_geometry_mismatch" in unique_blockers:
            status = "needs_regeneration"
        elif not content_run.prompt_pack_id or "geometry_lock_missing" in unique_blockers:
            status = "blocked"
        else:
            status = "needs_human_review"
        warnings = list(content_run.warnings_json or [])
        notes = [
            "Rules-based AI review only.",
            "No computer vision inspection was performed.",
            "Visual product identity, packaging geometry, and output quality require human review.",
        ]
        return AIReviewResult(
            status=status,
            score=score,
            human_review_required=True,
            checks=checks,
            blockers=unique_blockers,
            warnings=list(dict.fromkeys(warnings)),
            notes=notes,
        )

    @staticmethod
    def _check(key: str, passed: bool) -> dict:
        return {"key": key, "passed": bool(passed), "check_type": "metadata"}
