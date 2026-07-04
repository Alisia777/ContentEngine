from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.creative.types import CreativeSpec
from app.video_generator.artifact_manager import ArtifactManager
from app.video_generator.types import QualityScoreResult


SUCCESS_STATUSES = {"video_generated", "provider_succeeded", "completed", "complete", "succeeded", "success", "done"}


class QualityScorer:
    def __init__(self, db: Session):
        self.db = db
        self.artifacts = ArtifactManager()

    def score(self, generation_variant: models.VideoGenerationVariant) -> models.VideoQualityReview:
        spec_record = generation_variant.creative_spec
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        video_job = generation_variant.video_job
        output_exists, output_non_empty = self.artifacts.file_exists_and_non_empty(
            video_job.output_video_path if video_job else generation_variant.final_video_path
        )
        report_path = self.artifacts.generation_report_path(video_job)
        prompt_pack = generation_variant.prompt_pack_json or {}
        scene_prompts = prompt_pack.get("scene_prompts") or []
        checks = [
            self._check("output_file_exists", output_exists),
            self._check("output_file_non_empty", output_non_empty),
            self._check("generation_report_exists", bool(report_path and report_path.exists())),
            self._check("provider_status_successful", bool(video_job and video_job.status in SUCCESS_STATUSES)),
            self._check("scene_captions_exist", all(scene.caption for scene in spec.scene_plan)),
            self._check("cta_exists", bool(spec.cta)),
            self._check(
                "reference_image_included",
                not spec.reference_images or all(scene.get("reference_images") for scene in scene_prompts),
            ),
            self._check("forbidden_claims_not_used", not self._forbidden_claims_used(spec)),
            self._check(
                "first_frame_requirements_exist",
                bool(scene_prompts and scene_prompts[0].get("first_frame_requirements")),
            ),
        ]
        passed = sum(1 for item in checks if item["passed"])
        result = QualityScoreResult(
            score=round(passed / len(checks), 3) if checks else 0,
            status="metadata_scored",
            checks=checks,
            warnings=spec.warnings,
            notes=[
                "Metadata-only score. No computer vision inspection has been performed.",
                "Product identity is not auto-approved by metadata checks.",
            ],
        )
        review_json = result.model_dump(mode="json")
        review_json.update(
            {
                "human_visual_status": "not_reviewed",
                "identity_mismatch_flags": [],
                "requires_regeneration": False,
            }
        )
        review = models.VideoQualityReview(
            creative_spec_id=spec_record.id,
            video_generation_variant_id=generation_variant.id,
            video_job_id=video_job.id if video_job else None,
            status=result.status,
            score=result.score,
            review_json=review_json,
            warnings_json=result.warnings,
        )
        generation_variant.quality_score_json = review_json
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    @staticmethod
    def _check(key: str, passed: bool) -> dict:
        return {"key": key, "passed": bool(passed), "check_type": "metadata"}

    @staticmethod
    def _forbidden_claims_used(spec: CreativeSpec) -> bool:
        values = [
            spec.hook_text,
            spec.viewer_promise,
            spec.first_frame_spec.visual_hook,
            spec.first_frame_spec.text_overlay,
        ]
        for scene in spec.scene_plan:
            values.extend([scene.visual, scene.caption, scene.voiceover])
        text = " ".join(value for value in values if value).lower()
        risky = ["cure", "treatment", "medical treatment", "guaranteed result"]
        return any(term in text and term not in " ".join(claim.claim.lower() for claim in spec.allowed_claims) for term in risky)
