from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.creative.types import CreativeSpec
from app.intelligence.errors import ProviderConfigurationError
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

    def regenerate_scene(self, generation_variant_id: int, scene_number: int) -> dict:
        return SceneRegenerator(self.db).regenerate_scene(self._variant(generation_variant_id), scene_number)

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
                    negative_prompt="distorted product, changed packaging, unsupported claims, low quality",
                    source_fields_json=scene.claim_refs,
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

    @staticmethod
    def _video_job(generation_variant: models.VideoGenerationVariant) -> models.VideoJob:
        if not generation_variant.video_job:
            raise ProviderConfigurationError("Video generation has not been started for this variant.")
        return generation_variant.video_job
