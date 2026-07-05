from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models
from app.video_generator.errors import VideoGeneratorDataError
from app.video_generator.scene_regenerator import SceneRegenerator


ALLOWED_REGENERATION_REASONS = {
    "product_geometry_mismatch",
    "product_identity_mismatch",
    "scene_quality_issue",
    "claim_mismatch",
    "other",
}


class RegenerationRequestService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        video_job_id: int,
        scene_number: int,
        reason: str,
        feedback: str,
    ) -> models.SceneRegenerationRequest:
        if reason not in ALLOWED_REGENERATION_REASONS:
            allowed = ", ".join(sorted(ALLOWED_REGENERATION_REASONS))
            raise VideoGeneratorDataError(f"Unsupported regeneration reason '{reason}'. Allowed: {allowed}.")
        generation_variant = self._generation_variant_for_video_job(video_job_id)
        self._scene_for_number(generation_variant, scene_number)
        request = models.SceneRegenerationRequest(
            video_job_id=video_job_id,
            video_generation_variant_id=generation_variant.id,
            creative_spec_id=generation_variant.creative_spec_id,
            scene_number=scene_number,
            reason=reason,
            feedback=feedback,
            status="requested",
            request_json={
                "video_job_id": video_job_id,
                "video_generation_variant_id": generation_variant.id,
                "scene_number": scene_number,
                "reason": reason,
                "feedback": feedback,
            },
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def build_prompt_only(self, regeneration_request_id: int) -> models.SceneRegenerationRequest:
        request = self.db.get(models.SceneRegenerationRequest, regeneration_request_id)
        if not request:
            raise VideoGeneratorDataError(f"SceneRegenerationRequest {regeneration_request_id} not found.")
        generation_variant = request.generation_variant
        changed_scene = SceneRegenerator(self.db).regenerate_scene(
            generation_variant,
            request.scene_number,
            reason=request.reason,
            feedback=request.feedback,
            regeneration_request_id=request.id,
        )
        request.status = "prompt_ready"
        request.prompt_only_output_json = {
            "regeneration_request_id": request.id,
            "generation_variant_id": generation_variant.id,
            "prompt_pack_id": generation_variant.prompt_pack_id,
            "scene_number": request.scene_number,
            "reason": request.reason,
            "scene_prompt": changed_scene,
        }
        flag_modified(request, "prompt_only_output_json")
        self.db.commit()
        self.db.refresh(request)
        return request

    def _generation_variant_for_video_job(self, video_job_id: int) -> models.VideoGenerationVariant:
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.video_job_id == video_job_id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )
        if not generation_variant:
            raise VideoGeneratorDataError(f"No VideoGenerationVariant is linked to VideoJob {video_job_id}.")
        return generation_variant

    @staticmethod
    def _scene_for_number(generation_variant: models.VideoGenerationVariant, scene_number: int) -> dict:
        for scene in generation_variant.prompt_pack_json.get("scene_prompts") or []:
            if int(scene.get("scene_number") or 0) == scene_number:
                return scene
        raise VideoGeneratorDataError(f"Scene {scene_number} not found in generation variant {generation_variant.id}.")
