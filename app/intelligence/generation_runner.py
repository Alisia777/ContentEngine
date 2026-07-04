from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.intelligence.errors import IntelligenceError, ProviderConfigurationError
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.video_generator import GeneratorVideoService


@dataclass
class GeneratorRunArtifacts:
    pack: models.CreativeIntelligencePackRecord
    brief: models.ScriptBrief
    script_job: models.ScriptJob
    variant: models.ScriptVariant
    prompt_pack: models.PromptPack
    video_job: models.VideoJob | None = None
    provider_status: dict | None = None
    local_output_paths: list[str] | None = None
    report_path: str | None = None


class GeneratorRunService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def build_prompt_pack_only(
        self,
        *,
        product_id: int,
        llm_provider: str | None = None,
        video_provider: str | None = None,
    ) -> GeneratorRunArtifacts:
        pack = CreativeIntelligenceBuilder(self.db).build_for_product(product_id)
        brief = ScriptBriefBuilder(self.db).build_from_record(pack.id)
        script_job = GeneratorScriptService(self.db).generate_from_brief(brief.id, llm_provider)
        variant = sorted(script_job.variants, key=lambda item: item.variant_number)[0]
        prompt_provider = video_provider or self.settings.video_provider
        prompt_pack = PromptPackBuilder(self.db).build_for_script(variant.id, prompt_provider, brief.id)
        return GeneratorRunArtifacts(
            pack=pack,
            brief=brief,
            script_job=script_job,
            variant=variant,
            prompt_pack=prompt_pack,
        )

    def run_real(
        self,
        *,
        product_id: int,
        llm_provider: str | None = None,
        video_provider: str | None = None,
        confirm_real_spend: bool = False,
        max_scenes: int | None = None,
        full_video: bool = False,
    ) -> GeneratorRunArtifacts:
        selected_video_provider = video_provider or self.settings.video_provider
        video_service = GeneratorVideoService(self.db)
        video_service.preflight_provider(selected_video_provider, explicit_real_run=confirm_real_spend)
        artifacts = self.build_prompt_pack_only(
            product_id=product_id,
            llm_provider=llm_provider,
            video_provider=selected_video_provider,
        )
        video_job = video_service.create_video_job_from_prompt_pack(
            artifacts.prompt_pack.id,
            selected_video_provider,
            max_scenes=max_scenes,
            full_video=full_video,
            apply_safety_limits=True,
        )
        artifacts.video_job = video_job
        try:
            video_job = video_service.start_provider_jobs(video_job, explicit_real_run=confirm_real_spend)
            artifacts.provider_status = video_service.poll_until_complete(video_job)
            artifacts.local_output_paths = video_service.download_outputs(video_job)
            artifacts.video_job = video_service.assemble(video_job)
            artifacts.report_path = video_service.write_generation_report(artifacts.video_job)
            return artifacts
        except Exception as exc:
            video_job.error_message = str(exc)
            self.db.commit()
            artifacts.report_path = video_service.write_generation_report(video_job, errors=[str(exc)])
            if isinstance(exc, IntelligenceError):
                raise
            raise ProviderConfigurationError(f"Real generation failed: {exc}") from exc
