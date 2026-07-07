from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.errors import AssetKitError
from app.assets.reference_bundle_builder import ProviderReferenceBundleBuilder
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.blogger_brief.types import PACKAGING_DRIFT_NEGATIVE_TERMS
from app.config import get_settings
from app.creative.product_geometry import (
    GEOMETRY_LOCK_PROMPT_LINES,
    geometry_lock_prompt_text,
    geometry_negative_prompt,
)
from app.creative.types import CreativeSpec
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.types import PromptPackOutput, PromptSceneOutput
from app.intelligence.video_generator import GeneratorVideoService
from app.video_generator.errors import VideoGeneratorDataError
from app.video_generator.provider_payloads import build_provider_prompt_pack
from app.video_generator.quality_scorer import QualityScorer
from app.video_generator.scene_regenerator import SceneRegenerator


class VideoGenerator:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def build_prompt_pack_from_spec(
        self,
        creative_spec_id: int,
        *,
        provider: str | None = None,
    ) -> models.VideoGenerationVariant:
        spec_record = self._spec(creative_spec_id)
        selected_provider = provider or self.settings.video_provider
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        prompt_pack_output = build_provider_prompt_pack(spec, selected_provider, spec_record.id)
        script_variant = self._create_execution_variant(spec_record, spec)
        scene_prompts = [scene.model_dump(mode="json") for scene in prompt_pack_output.scene_prompts]
        prompt_pack_json = prompt_pack_output.model_dump(mode="json")
        prompt_pack_json["creative_spec_id"] = spec_record.id
        prompt_pack = models.PromptPack(
            script_brief_id=spec_record.script_brief_id,
            script_variant_id=script_variant.id,
            status="ready",
            prompt_pack_json=prompt_pack_json,
            scene_prompts_json=scene_prompts,
            negative_prompts_json=[
                {"scene_number": scene["scene_number"], "negative_prompt": scene["negative_prompt"]}
                for scene in scene_prompts
            ],
            provider_payload_json={
                "provider": selected_provider,
                "creative_spec_id": spec_record.id,
                "aspect_ratio": spec.aspect_ratio,
                "duration_seconds": spec.duration_seconds,
                "scenes": scene_prompts,
            },
        )
        self.db.add(prompt_pack)
        self.db.flush()
        generation_variant = models.VideoGenerationVariant(
            creative_spec_id=spec_record.id,
            prompt_pack_id=prompt_pack.id,
            script_variant_id=script_variant.id,
            provider=selected_provider,
            status="prompt_pack_ready",
            prompt_pack_json=prompt_pack_json,
            provider_payload_json=prompt_pack.provider_payload_json,
        )
        self.db.add(generation_variant)
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def build_prompt_pack_from_variant(
        self,
        creative_variant_id: int,
        *,
        provider: str | None = None,
    ) -> models.VideoGenerationVariant:
        creative_variant = self._creative_variant(creative_variant_id)
        spec_record = creative_variant.creative_spec
        selected_provider = provider or self.settings.video_provider
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        script_variant = self._create_execution_variant_from_creative_variant(spec_record, spec, creative_variant)
        first_frame = creative_variant.first_frame_json or {}
        product_identity_strict = bool((spec_record.spec_json or {}).get("product_identity_strict", True))
        reference_policy = ProductReferencePolicyService(self.db).check(
            spec.product_id,
            provider=selected_provider,
            product_identity_strict=product_identity_strict,
        )
        reference_bundle = self._reference_bundle(spec.product_id, selected_provider)
        provider_reference_bundle = reference_bundle.provider_payload_json if reference_bundle else {}
        reference_images = provider_reference_bundle.get("reference_images") or []
        reference_warnings = []
        if not reference_bundle:
            reference_warnings.append("No provider reference bundle is available for this product.")
        elif reference_bundle.status != "ready":
            reference_warnings.extend(reference_bundle.blockers_json or ["Product reference bundle is not ready."])
        variant_warnings = list(creative_variant.risk_flags_json or [])
        if reference_bundle and reference_bundle.status == "ready":
            stale_asset_risks = {"missing_packshot", "packshot_missing_for_product_accuracy", "missing_product_reference_assets"}
            variant_warnings = [warning for warning in variant_warnings if warning not in stale_asset_risks]
        scene_prompts = self._variant_scene_prompts(
            creative_variant,
            spec,
            reference_images=reference_images,
            reference_policy=reference_policy.model_dump(mode="json"),
        )
        prompt_output = PromptPackOutput(
            provider=selected_provider,
            aspect_ratio=spec.aspect_ratio,
            duration_seconds=sum(scene.duration_seconds for scene in scene_prompts),
            scene_prompts=scene_prompts,
        )
        prompt_pack_json = prompt_output.model_dump(mode="json")
        prompt_pack_json.update(
            {
                "creative_spec_id": spec_record.id,
                "creative_variant_id": creative_variant.id,
                "reference_bundle_id": reference_bundle.id if reference_bundle else None,
                "reference_readiness_status": reference_bundle.status if reference_bundle else "missing",
                "selected_first_frame": first_frame,
                "asset_references": reference_images or creative_variant.asset_refs_json,
                "reference_images": reference_images,
                "primary_reference_asset": reference_bundle.primary_image_asset_id if reference_bundle else None,
                "provider_reference_bundle": provider_reference_bundle,
                "product_reference_policy": reference_policy.model_dump(mode="json"),
                "product_identity_strict": product_identity_strict,
                "product_lock_mode": reference_policy.product_lock_mode,
                "product_reference_count": reference_policy.approved_reference_count,
                "mass_generation_safety_status": reference_policy.mass_generation_safety_status,
                "product_accuracy_rules": self._product_accuracy_rules(spec),
                "product_geometry_spec": spec.product_geometry_spec.model_dump(mode="json"),
                "product_geometry_rules": spec.product_geometry_rules,
                "product_scale_rules": spec.product_scale_rules,
                "product_visibility_rules": spec.product_visibility_rules,
                "overlay_text": first_frame.get("text_overlay"),
                "scene_pacing": creative_variant.pacing_json,
                "selected_cta": creative_variant.cta_framing,
                "variant_score": creative_variant.score_json,
                "warnings": list(dict.fromkeys(variant_warnings + reference_warnings + reference_policy.warnings)),
                "blockers": list(dict.fromkeys(reference_policy.blockers)),
                "next_actions": reference_policy.next_actions,
            }
        )
        prompt_pack = models.PromptPack(
            script_brief_id=spec_record.script_brief_id,
            script_variant_id=script_variant.id,
            status="ready",
            prompt_pack_json=prompt_pack_json,
            scene_prompts_json=[scene.model_dump(mode="json") for scene in scene_prompts],
            negative_prompts_json=[
                {"scene_number": scene.scene_number, "negative_prompt": scene.negative_prompt}
                for scene in scene_prompts
            ],
            provider_payload_json={
                "provider": selected_provider,
                "creative_spec_id": spec_record.id,
                "creative_variant_id": creative_variant.id,
                "reference_bundle_id": reference_bundle.id if reference_bundle else None,
                "reference_images": reference_images,
                "primary_reference_asset": reference_bundle.primary_image_asset_id if reference_bundle else None,
                "provider_reference_bundle": provider_reference_bundle,
                "product_reference_policy": reference_policy.model_dump(mode="json"),
                "product_identity_strict": product_identity_strict,
                "product_lock_mode": reference_policy.product_lock_mode,
                "product_reference_count": reference_policy.approved_reference_count,
                "mass_generation_safety_status": reference_policy.mass_generation_safety_status,
                "product_geometry_spec": spec.product_geometry_spec.model_dump(mode="json"),
                "product_geometry_rules": spec.product_geometry_rules,
                "product_scale_rules": spec.product_scale_rules,
                "product_visibility_rules": spec.product_visibility_rules,
                "aspect_ratio": spec.aspect_ratio,
                "duration_seconds": prompt_output.duration_seconds,
                "asset_references": reference_images or creative_variant.asset_refs_json,
                "selected_first_frame": first_frame,
                "scenes": [scene.model_dump(mode="json") for scene in scene_prompts],
            },
        )
        self.db.add(prompt_pack)
        self.db.flush()
        generation_variant = models.VideoGenerationVariant(
            creative_spec_id=spec_record.id,
            creative_variant_id=creative_variant.id,
            prompt_pack_id=prompt_pack.id,
            script_variant_id=script_variant.id,
            provider=selected_provider,
            status="prompt_pack_ready",
            prompt_pack_json=prompt_pack_json,
            provider_payload_json=prompt_pack.provider_payload_json,
        )
        self.db.add(generation_variant)
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def start_generation(
        self,
        generation_variant_id: int,
        *,
        provider: str | None = None,
        confirm_real_spend: bool = False,
        max_scenes: int | None = None,
        full_video: bool = False,
    ) -> models.VideoGenerationVariant:
        generation_variant = self._variant(generation_variant_id)
        selected_provider = provider or generation_variant.provider
        service = GeneratorVideoService(self.db)
        service.preflight_provider(selected_provider, explicit_real_run=confirm_real_spend)
        video_job = service.create_video_job_from_prompt_pack(
            generation_variant.prompt_pack_id,
            selected_provider,
            max_scenes=max_scenes,
            full_video=full_video,
            apply_safety_limits=True,
        )
        video_job = service.start_provider_jobs(video_job, explicit_real_run=confirm_real_spend)
        generation_variant.video_job_id = video_job.id
        generation_variant.provider = selected_provider
        generation_variant.status = video_job.status
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def poll(self, generation_variant_id: int) -> dict:
        generation_variant = self._variant(generation_variant_id)
        video_job = self._video_job(generation_variant)
        status = GeneratorVideoService(self.db).provider_status(video_job)
        generation_variant.status = status["status"]
        self.db.commit()
        return status

    def download(self, generation_variant_id: int) -> models.VideoGenerationVariant:
        generation_variant = self._variant(generation_variant_id)
        paths = GeneratorVideoService(self.db).download_outputs(self._video_job(generation_variant))
        generation_variant.local_output_paths_json = paths
        generation_variant.status = "downloaded"
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def assemble(self, generation_variant_id: int) -> models.VideoGenerationVariant:
        generation_variant = self._variant(generation_variant_id)
        video_job = GeneratorVideoService(self.db).assemble(self._video_job(generation_variant))
        generation_variant.final_video_path = video_job.output_video_path
        generation_variant.status = video_job.status
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def score(self, generation_variant_id: int) -> models.VideoQualityReview:
        return QualityScorer(self.db).score(self._variant(generation_variant_id))

    def regenerate_scene(
        self,
        generation_variant_id: int,
        scene_number: int,
        *,
        reason: str | None = None,
        feedback: str | None = None,
    ) -> dict:
        return SceneRegenerator(self.db).regenerate_scene(
            self._variant(generation_variant_id),
            scene_number,
            reason=reason,
            feedback=feedback,
        )

    def _create_execution_variant(self, spec_record: models.VideoCreativeSpecRecord, spec: CreativeSpec) -> models.ScriptVariant:
        product = self.db.get(models.Product, spec.product_id)
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        ) if product else None
        template = self.db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
        if not product or not brand_guide or not template:
            raise VideoGeneratorDataError("Product, brand guide, and creative template are required for spec execution.")
        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status="creative_spec_ready",
            input_payload_json={"creative_spec_id": spec_record.id},
            output_script_json=spec.model_dump(mode="json"),
            validation_report_json=spec_record.validation_report_json,
            llm_provider="creative_spec",
            llm_model="hook-driven-video-spec-v1",
            llm_request_json={"source": "VideoCreativeSpecRecord", "id": spec_record.id},
            llm_response_json=spec.model_dump(mode="json"),
        )
        self.db.add(script_job)
        self.db.flush()
        variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=1,
            creative_angle=spec.creative_angle,
            hook=spec.hook_text,
            key_message=spec.viewer_promise,
            final_cta=spec.cta,
            full_script_json=spec.model_dump(mode="json"),
            status="creative_spec_ready",
        )
        self.db.add(variant)
        self.db.flush()
        for scene in spec.scene_plan:
            self.db.add(
                models.Scene(
                    script_variant_id=variant.id,
                    scene_number=scene.scene_number,
                    time_start=scene.starts_at,
                    time_end=scene.ends_at,
                    visual_description=scene.visual,
                    voiceover=scene.voiceover,
                    caption=scene.caption,
                    video_prompt=scene.visual,
                    negative_prompt=geometry_negative_prompt(
                        "distorted product, changed packaging, unsupported claims, low quality"
                    ),
                    source_fields_json=scene.claim_refs,
                )
            )
        self.db.flush()
        return variant

    def _create_execution_variant_from_creative_variant(
        self,
        spec_record: models.VideoCreativeSpecRecord,
        spec: CreativeSpec,
        creative_variant: models.CreativeVariant,
    ) -> models.ScriptVariant:
        product = self.db.get(models.Product, spec.product_id)
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        ) if product else None
        template = self.db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
        if not product or not brand_guide or not template:
            raise VideoGeneratorDataError("Product, brand guide, and creative template are required for variant execution.")
        script_payload = {
            **spec.model_dump(mode="json"),
            "creative_variant_id": creative_variant.id,
            "selected_first_frame": creative_variant.first_frame_json,
            "scene_plan": creative_variant.scene_plan_json,
            "cta": creative_variant.cta_framing or spec.cta,
        }
        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status="creative_variant_ready",
            input_payload_json={"creative_spec_id": spec_record.id, "creative_variant_id": creative_variant.id},
            output_script_json=script_payload,
            validation_report_json=spec_record.validation_report_json,
            llm_provider="creative_variant",
            llm_model="asset-kit-variant-v1",
            llm_request_json={"source": "CreativeVariant", "id": creative_variant.id},
            llm_response_json=script_payload,
        )
        self.db.add(script_job)
        self.db.flush()
        variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=creative_variant.variant_number,
            creative_angle=spec.creative_angle,
            hook=creative_variant.hook_text,
            key_message=spec.viewer_promise,
            final_cta=creative_variant.cta_framing or spec.cta,
            full_script_json=script_payload,
            status="creative_variant_ready",
        )
        self.db.add(variant)
        self.db.flush()
        for scene in creative_variant.scene_plan_json or []:
            duration = max(1, int(scene.get("duration_seconds") or 1))
            starts_at = int(scene.get("starts_at") or 0)
            self.db.add(
                models.Scene(
                    script_variant_id=variant.id,
                    scene_number=int(scene.get("scene_number") or 1),
                    time_start=starts_at,
                    time_end=starts_at + duration,
                    visual_description=scene.get("visual"),
                    voiceover=scene.get("voiceover"),
                    caption=scene.get("caption"),
                    video_prompt=self._variant_prompt_text(creative_variant, spec, scene),
                    negative_prompt=geometry_negative_prompt(
                        "distorted product, changed packaging, fake labels, unsupported claims, "
                        "medical claims, unreadable text, low quality"
                    ),
                    source_fields_json=scene.get("claim_refs") or [],
                )
            )
        self.db.flush()
        return variant

    def _spec(self, creative_spec_id: int) -> models.VideoCreativeSpecRecord:
        spec = self.db.get(models.VideoCreativeSpecRecord, creative_spec_id)
        if not spec:
            raise VideoGeneratorDataError(f"VideoCreativeSpecRecord {creative_spec_id} not found.")
        return spec

    def _variant(self, generation_variant_id: int) -> models.VideoGenerationVariant:
        generation_variant = self.db.get(models.VideoGenerationVariant, generation_variant_id)
        if not generation_variant:
            raise VideoGeneratorDataError(f"VideoGenerationVariant {generation_variant_id} not found.")
        return generation_variant

    def _creative_variant(self, creative_variant_id: int) -> models.CreativeVariant:
        creative_variant = self.db.get(models.CreativeVariant, creative_variant_id)
        if not creative_variant:
            raise VideoGeneratorDataError(f"CreativeVariant {creative_variant_id} not found.")
        return creative_variant

    def _reference_bundle(self, product_id: int, provider: str) -> models.ProductReferenceBundle | None:
        try:
            return ProviderReferenceBundleBuilder(self.db).build(product_id, provider=provider)
        except AssetKitError:
            return None

    def _variant_scene_prompts(
        self,
        creative_variant: models.CreativeVariant,
        spec: CreativeSpec,
        *,
        reference_images: list[str] | None = None,
        reference_policy: dict | None = None,
    ) -> list[PromptSceneOutput]:
        prompts = []
        reference_policy = reference_policy or {}
        product_lock_mode = reference_policy.get("product_lock_mode", "no_product_generation")
        do_not_generate_packaging = product_lock_mode in {"packshot_overlay", "end_card_packshot"}
        for scene in creative_variant.scene_plan_json or []:
            negative_prompt = self._merge_negative_prompt(
                scene.get("negative_prompt") or geometry_negative_prompt(
                    "distorted product, changed packaging, fake labels, unsupported claims, "
                    "medical claims, unreadable text, low quality"
                )
            )
            safety_constraints = scene.get("safety_constraints") or [
                "show the selected first frame clearly",
                "do not alter product shape, packaging, color, or label",
                "use only source-backed claims",
                "keep overlay text readable and clear of packaging",
                *GEOMETRY_LOCK_PROMPT_LINES,
            ]
            safety_constraints = list(
                dict.fromkeys(
                    [
                        *safety_constraints,
                        f"product_lock_mode:{product_lock_mode}",
                        f"product_reference_count:{reference_policy.get('approved_reference_count', 0)}",
                        *(
                            ["do not generate packaging; use exact packshot overlay or end card"]
                            if do_not_generate_packaging
                            else ["use approved product references for package identity"]
                        ),
                        "provider-generated product scenes always need human review",
                    ]
                )
            )
            prompts.append(
                PromptSceneOutput(
                    scene_number=int(scene.get("scene_number") or 1),
                    duration_seconds=max(1, int(scene.get("duration_seconds") or 1)),
                    prompt_text=self._variant_prompt_text(creative_variant, spec, scene),
                    negative_prompt=negative_prompt,
                    reference_images=reference_images or creative_variant.asset_refs_json or [],
                    camera_motion=scene.get("camera_motion") or "slow product-focused movement",
                    style=creative_variant.visual_style or spec.visual_style,
                    safety_constraints=safety_constraints,
                    product_geometry_rules=spec.product_geometry_rules,
                    product_scale_rules=spec.product_scale_rules,
                    product_visibility_rules=spec.product_visibility_rules,
                )
            )
        return prompts

    @staticmethod
    def _variant_prompt_text(creative_variant: models.CreativeVariant, spec: CreativeSpec, scene: dict) -> str:
        if scene.get("provider_prompt_text"):
            return str(scene["provider_prompt_text"]).strip()
        first_frame = creative_variant.first_frame_json or {}
        first_frame_text = ""
        if int(scene.get("scene_number") or 1) == 1:
            first_frame_text = (
                f"Selected first frame: {first_frame.get('visual_concept')}. "
                f"Overlay text: {first_frame.get('text_overlay')}. "
                f"Product placement: {first_frame.get('product_placement')}. "
            )
        return (
            f"{first_frame_text}Scene role: {scene.get('role')}. {scene.get('visual')} "
            f"Caption: {scene.get('caption')}. Voiceover: {scene.get('voiceover')}. "
            f"Scene pacing: {creative_variant.pacing_json}. CTA framing: {creative_variant.cta_framing}. "
            f"Product accuracy rules: {'; '.join(VideoGenerator._product_accuracy_rules(spec))}. "
            f"Product geometry lock: {geometry_lock_prompt_text()}"
        )

    @staticmethod
    def _product_accuracy_rules(spec: CreativeSpec) -> list[str]:
        return list(dict.fromkeys(spec.product_display_rules + GEOMETRY_LOCK_PROMPT_LINES))

    @staticmethod
    def _merge_negative_prompt(existing: str) -> str:
        terms = [item.strip() for item in existing.split(",") if item.strip()]
        return ", ".join(list(dict.fromkeys([*terms, *PACKAGING_DRIFT_NEGATIVE_TERMS])))

    @staticmethod
    def _video_job(generation_variant: models.VideoGenerationVariant) -> models.VideoJob:
        if not generation_variant.video_job:
            raise ProviderConfigurationError("Video generation has not been started for this variant.")
        return generation_variant.video_job
