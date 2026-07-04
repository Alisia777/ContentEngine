from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.enums import WorkflowStatus
from app.intelligence.errors import MissingGeneratorDataError, ProviderConfigurationError
from app.intelligence.types import GeneratedScriptOutput, ScriptBriefOutput
from app.intelligence.validators import validate_script_claim_refs
from app.providers.mock_llm import MockLLMProvider
from app.providers.openai_llm import OpenAILLMProvider


class GeneratorScriptService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def generate_from_brief(self, script_brief_id: int, provider_name: str | None = None) -> models.ScriptJob:
        brief_record = self.db.get(models.ScriptBrief, script_brief_id)
        if not brief_record:
            raise MissingGeneratorDataError(f"ScriptBrief {script_brief_id} not found.")
        brief = ScriptBriefOutput.model_validate(brief_record.brief_json)
        provider = self._provider(provider_name or self.settings.llm_provider)
        script = provider.generate_script(brief)
        validate_script_claim_refs(script, brief)
        product = self.db.get(models.Product, brief_record.product_id)
        if not product:
            raise MissingGeneratorDataError(f"Product {brief_record.product_id} not found.")
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        )
        template = self.db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
        if not brand_guide or not template:
            raise MissingGeneratorDataError("Brand guide and creative template are required for ScriptJob persistence.")

        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status=WorkflowStatus.script_generated.value,
            input_payload_json={"script_brief_id": brief_record.id, "brief": brief.model_dump(mode="json")},
            output_script_json=script.model_dump(mode="json"),
            validation_report_json={"valid": True, "source_refs_checked": True},
            llm_provider=provider.provider_name,
            llm_model=provider.model,
            llm_request_json=getattr(provider, "last_request_json", {"brief": brief.model_dump(mode="json")}),
            llm_response_json=getattr(provider, "last_response_json", script.model_dump(mode="json")),
        )
        self.db.add(script_job)
        self.db.flush()
        variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=1,
            creative_angle=script.creative_angle,
            hook=script.hook,
            key_message=script.key_message,
            final_cta=script.final_cta,
            full_script_json=script.model_dump(mode="json"),
            status=WorkflowStatus.script_generated.value,
        )
        self.db.add(variant)
        self.db.flush()
        for scene in script.scenes:
            self.db.add(
                models.Scene(
                    script_variant_id=variant.id,
                    scene_number=scene.scene_number,
                    time_start=scene.time_start,
                    time_end=scene.time_end,
                    visual_description=scene.visual_description,
                    voiceover=scene.voiceover,
                    caption=scene.caption,
                    video_prompt=scene.video_prompt,
                    negative_prompt=scene.negative_prompt,
                    source_fields_json=scene.claim_refs,
                )
            )
        self.db.commit()
        self.db.refresh(script_job)
        return script_job

    def _provider(self, provider_name: str):
        if provider_name == "mock":
            return MockLLMProvider()
        if provider_name == "openai":
            return OpenAILLMProvider()
        raise ProviderConfigurationError(f"Unsupported LLM provider: {provider_name}")
