from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import models
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.video_generator import GeneratorVideoService
from app.video_generator.errors import VideoGeneratorDataError
from app.video_generator.product_identity import (
    ProductIdentityService,
    corrections_from_feedback,
    identity_negative_prompt,
    identity_prompt_rules,
    identity_spec_payload,
)


class VideoRegenerationService:
    def __init__(self, db: Session):
        self.db = db

    def request(
        self,
        *,
        video_job_id: int,
        scene_number: int,
        reason: str,
        human_feedback: str,
    ) -> models.VideoRegenerationRequest:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise VideoGeneratorDataError(f"VideoJob {video_job_id} not found.")
        generation_variant = self._generation_variant(video_job_id)
        corrections = corrections_from_feedback(human_feedback)
        review = self._latest_review(generation_variant.id)
        if review:
            review.human_visual_status = "fail"
            review.human_rejection_reason = human_feedback
            review.identity_mismatch_flags_json = corrections["identity_mismatch_flags"]
            review.requires_regeneration = True
            review.review_json = {
                **(review.review_json or {}),
                "human_visual_status": "fail",
                "human_rejection_reason": human_feedback,
                "identity_mismatch_flags": corrections["identity_mismatch_flags"],
                "requires_regeneration": True,
            }
            flag_modified(review, "review_json")
        request = models.VideoRegenerationRequest(
            video_job_id=video_job.id,
            creative_variant_id=generation_variant.creative_variant_id,
            video_generation_variant_id=generation_variant.id,
            scene_number=scene_number,
            reason=reason,
            human_feedback=human_feedback,
            identity_corrections_json=corrections,
            status="requested",
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def build_prompt_pack(self, regeneration_request_id: int, *, provider: str = "runway") -> models.VideoRegenerationRequest:
        request = self._request(regeneration_request_id)
        generation_variant = request.generation_variant
        if not generation_variant or not generation_variant.prompt_pack:
            raise VideoGeneratorDataError("Regeneration request must reference a prompt-backed generation variant.")
        prompt_pack_json = deepcopy(generation_variant.prompt_pack_json or {})
        scene_prompts = deepcopy(prompt_pack_json.get("scene_prompts") or [])
        product = generation_variant.creative_spec.product
        primary_reference_asset_id = prompt_pack_json.get("primary_reference_asset")
        identity_spec = ProductIdentityService(self.db).get_or_create(
            product,
            primary_reference_asset_id=primary_reference_asset_id,
            product_lock_mode=prompt_pack_json.get("product_lock_mode") or "reference_i2v",
        )
        identity_payload = identity_spec_payload(identity_spec)
        identity_rules = identity_prompt_rules(identity_spec)
        identity_negative = identity_negative_prompt(identity_spec)
        prompt_pack_json["product_identity_spec"] = identity_payload
        prompt_pack_json["product_lock_mode"] = identity_spec.product_lock_mode
        reference_images = prompt_pack_json.get("reference_images") or []
        if identity_spec.product_lock_mode == "packshot_overlay" and reference_images:
            prompt_pack_json["packshot_overlay_asset"] = reference_images[0]
        if identity_spec.product_lock_mode in {"end_card_packshot", "packshot_overlay", "no_product_generation"} and reference_images:
            prompt_pack_json["end_card_packshot_asset"] = reference_images[0]
        changed = None
        correction_text = self._correction_text(request)
        for scene in scene_prompts:
            scene["prompt_text"] = self._append_once(
                scene.get("prompt_text", ""),
                " Product identity lock rules: " + "; ".join(identity_rules),
            )
            scene["negative_prompt"] = self._append_negative(scene.get("negative_prompt", ""), identity_negative)
            scene["safety_constraints"] = list(
                dict.fromkeys((scene.get("safety_constraints") or []) + identity_rules)
            )
            if int(scene.get("scene_number") or 0) == request.scene_number:
                scene["prompt_text"] = (
                    scene.get("prompt_text", "")
                    + " Regeneration request: product identity mismatch was rejected by human review. "
                    + correction_text
                )
                scene["negative_prompt"] = self._append_negative(scene.get("negative_prompt", ""), identity_negative)
                scene["human_feedback"] = request.human_feedback
                scene["identity_corrections"] = request.identity_corrections_json
                scene["regenerated_from_video_job_id"] = request.video_job_id
                scene["regenerated_at"] = datetime.now(UTC).isoformat()
                changed = scene
                break
        if not changed:
            raise VideoGeneratorDataError(f"Scene {request.scene_number} not found in prompt pack.")
        prompt_pack_json["scene_prompts"] = scene_prompts
        prompt_pack_json["regeneration_request_id"] = request.id
        prompt_pack_json["regeneration_feedback"] = request.human_feedback
        prompt_pack_json["identity_corrections"] = request.identity_corrections_json
        provider_payload = {
            **(generation_variant.prompt_pack.provider_payload_json or generation_variant.provider_payload_json or {}),
            "provider": provider,
            "regeneration_request_id": request.id,
            "product_identity_spec": identity_payload,
            "product_lock_mode": identity_spec.product_lock_mode,
            "packshot_overlay_asset": prompt_pack_json.get("packshot_overlay_asset"),
            "end_card_packshot_asset": prompt_pack_json.get("end_card_packshot_asset"),
            "identity_corrections": request.identity_corrections_json,
            "scenes": scene_prompts,
        }
        new_pack = models.PromptPack(
            script_brief_id=generation_variant.prompt_pack.script_brief_id,
            script_variant_id=generation_variant.prompt_pack.script_variant_id,
            status="ready",
            prompt_pack_json=prompt_pack_json,
            scene_prompts_json=scene_prompts,
            negative_prompts_json=[
                {"scene_number": scene["scene_number"], "negative_prompt": scene.get("negative_prompt", "")}
                for scene in scene_prompts
            ],
            provider_payload_json=provider_payload,
        )
        self.db.add(new_pack)
        self.db.flush()
        new_variant = models.VideoGenerationVariant(
            creative_spec_id=generation_variant.creative_spec_id,
            creative_variant_id=generation_variant.creative_variant_id,
            prompt_pack_id=new_pack.id,
            script_variant_id=generation_variant.script_variant_id,
            provider=provider,
            status="prompt_pack_ready",
            prompt_pack_json=prompt_pack_json,
            provider_payload_json=provider_payload,
        )
        self.db.add(new_variant)
        request.new_prompt_pack_id = new_pack.id
        request.status = "prompt_pack_ready"
        self.db.commit()
        self.db.refresh(request)
        return request

    def run_real(
        self,
        regeneration_request_id: int,
        *,
        provider: str = "runway",
        explicit_real_run: bool = False,
        max_scenes: int = 1,
    ) -> models.VideoRegenerationRequest:
        if not explicit_real_run:
            raise ProviderConfigurationError("Regeneration real run requires explicit --real-run.")
        request = self._request(regeneration_request_id)
        if not request.new_prompt_pack_id:
            request = self.build_prompt_pack(regeneration_request_id, provider=provider)
        service = GeneratorVideoService(self.db)
        service.preflight_provider(provider, explicit_real_run=True)
        video_job = self.db.get(models.VideoJob, request.new_video_job_id) if request.new_video_job_id else None
        if not video_job or any(clip.provider_job_id for clip in video_job.clips):
            video_job = service.create_video_job_from_prompt_pack(
                request.new_prompt_pack_id,
                provider,
                max_scenes=max_scenes,
                full_video=False,
                apply_safety_limits=True,
            )
            request.new_video_job_id = video_job.id
            request.status = "provider_job_queued"
            self.db.commit()
        self._new_generation_variant(request).video_job_id = video_job.id
        self._new_generation_variant(request).status = video_job.status
        self.db.commit()
        video_job = service.start_provider_jobs(video_job, explicit_real_run=True)
        self._new_generation_variant(request).status = video_job.status
        request.status = video_job.status
        self.db.commit()
        self.db.refresh(request)
        return request

    def _generation_variant(self, video_job_id: int) -> models.VideoGenerationVariant:
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.video_job_id == video_job_id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )
        if not generation_variant:
            raise VideoGeneratorDataError(f"VideoGenerationVariant for VideoJob {video_job_id} not found.")
        return generation_variant

    def _request(self, regeneration_request_id: int) -> models.VideoRegenerationRequest:
        request = self.db.get(models.VideoRegenerationRequest, regeneration_request_id)
        if not request:
            raise VideoGeneratorDataError(f"VideoRegenerationRequest {regeneration_request_id} not found.")
        return request

    def _new_generation_variant(self, request: models.VideoRegenerationRequest) -> models.VideoGenerationVariant:
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.prompt_pack_id == request.new_prompt_pack_id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )
        if not generation_variant:
            raise VideoGeneratorDataError("Regeneration request has no regenerated VideoGenerationVariant.")
        return generation_variant

    def _latest_review(self, generation_variant_id: int) -> models.VideoQualityReview | None:
        return self.db.scalar(
            select(models.VideoQualityReview)
            .where(models.VideoQualityReview.video_generation_variant_id == generation_variant_id)
            .order_by(models.VideoQualityReview.id.desc())
        )

    @staticmethod
    def _correction_text(request: models.VideoRegenerationRequest) -> str:
        corrections = request.identity_corrections_json or {}
        required = corrections.get("required_corrections") or []
        return (
            f"Human feedback: {request.human_feedback}. "
            f"Identity corrections: {'; '.join(required)}. "
            "Use the approved primary reference as the product anchor and do not invent packaging details."
        )

    @staticmethod
    def _append_once(text: str, addition: str) -> str:
        if not addition.strip() or addition.strip() in text:
            return text
        return text + addition

    @staticmethod
    def _append_negative(text: str, addition: str) -> str:
        parts = [part.strip() for part in (text + ", " + addition).split(",") if part.strip()]
        return ", ".join(dict.fromkeys(parts))
