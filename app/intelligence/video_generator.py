from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.enums import WorkflowStatus
from app.intelligence.errors import MissingGeneratorDataError, ProviderConfigurationError
from app.intelligence.types import PromptPackOutput
from app.providers.gemini_video import GeminiVideoProvider
from app.providers.mock_video import MockGeneratorVideoProvider
from app.providers.runway_video import RunwayVideoProvider
from app.services.video_assembly import VideoAssemblyService


class GeneratorVideoService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.assembly = VideoAssemblyService()

    def create_video_job_from_prompt_pack(
        self,
        prompt_pack_id: int,
        provider_name: str | None = None,
    ) -> models.VideoJob:
        prompt_pack = self.db.get(models.PromptPack, prompt_pack_id)
        if not prompt_pack:
            raise MissingGeneratorDataError(f"PromptPack {prompt_pack_id} not found.")
        if not prompt_pack.script_variant_id:
            raise MissingGeneratorDataError("PromptPack must reference a script variant before video generation.")
        output = PromptPackOutput.model_validate(prompt_pack.prompt_pack_json)
        provider = self._provider(provider_name or self.settings.video_provider)
        provider_job = provider.create_generation(output)
        video_job = models.VideoJob(
            script_variant_id=prompt_pack.script_variant_id,
            provider=provider.provider_name,
            status="provider_job_created",
            aspect_ratio=output.aspect_ratio,
            duration_seconds=output.duration_seconds,
            cost_estimate=0,
            error_message=None,
        )
        self.db.add(video_job)
        self.db.flush()
        scenes = sorted(video_job.script_variant.scenes, key=lambda scene: scene.scene_number)
        for scene in scenes:
            self.db.add(
                models.VideoClip(
                    video_job_id=video_job.id,
                    scene_id=scene.id,
                    provider_job_id=provider_job.provider_job_id,
                    status=provider_job.status,
                    raw_response_json=provider_job.raw_response,
                )
            )
        self.db.commit()
        self.db.refresh(video_job)
        if provider.provider_name == "mock":
            return self._complete_mock_video(video_job)
        return video_job

    def status(self, video_job: models.VideoJob) -> dict:
        provider_job_id = video_job.clips[0].provider_job_id if video_job.clips else None
        if not provider_job_id:
            return {"status": video_job.status, "provider": video_job.provider, "provider_job_id": None}
        provider = self._provider(video_job.provider)
        provider_status = provider.get_status(provider_job_id)
        video_job.status = provider_status.status
        for clip in video_job.clips:
            clip.status = provider_status.status
            clip.raw_response_json = provider_status.raw_response
        self.db.commit()
        return {
            "status": video_job.status,
            "provider": video_job.provider,
            "provider_job_id": provider_job_id,
            "raw_response": provider_status.raw_response,
        }

    def download_outputs(self, video_job: models.VideoJob) -> list[str]:
        provider_job_id = video_job.clips[0].provider_job_id if video_job.clips else None
        if not provider_job_id:
            raise MissingGeneratorDataError("Video job has no provider job id.")
        provider = self._provider(video_job.provider)
        target_dir = self.settings.media_root / "provider" / video_job.provider
        paths = provider.download_outputs(provider_job_id, target_dir)
        for clip, path in zip(video_job.clips, paths):
            clip.clip_path = path.as_posix()
            clip.status = "downloaded"
        self.db.commit()
        return [path.as_posix() for path in paths]

    def assemble(self, video_job: models.VideoJob) -> models.VideoJob:
        clips = sorted(video_job.clips, key=lambda item: item.scene.scene_number)
        output_path, preview_path = self.assembly.assemble(
            video_job.id,
            [clip.clip_path for clip in clips if clip.clip_path],
            video_job.script_variant.final_cta or "Open the product card",
            [clip.scene.caption or "" for clip in clips],
        )
        video_job.output_video_path = output_path
        video_job.preview_path = preview_path
        video_job.status = WorkflowStatus.video_generated.value
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def _complete_mock_video(self, video_job: models.VideoJob) -> models.VideoJob:
        for clip in video_job.clips:
            duration = max(1, int(clip.scene.time_end - clip.scene.time_start))
            clip.clip_path = self.assembly.create_mock_clip(
                video_job.id,
                clip.scene.scene_number,
                duration,
                clip.scene.caption or "",
                clip.scene.video_prompt or "",
            )
            clip.status = WorkflowStatus.video_generated.value
        self.db.commit()
        return self.assemble(video_job)

    def _provider(self, provider_name: str):
        if provider_name == "mock":
            return MockGeneratorVideoProvider()
        if provider_name == "runway":
            return RunwayVideoProvider()
        if provider_name == "gemini":
            return GeminiVideoProvider()
        raise ProviderConfigurationError(f"Unsupported video provider: {provider_name}")

