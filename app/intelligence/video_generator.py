from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.enums import WorkflowStatus
from app.intelligence.generation_report import GenerationReportWriter
from app.intelligence.errors import MissingGeneratorDataError, ProviderConfigurationError
from app.intelligence.safety import bounded_scene_count, require_real_video_allowed
from app.intelligence.types import PromptPackOutput, PromptSceneOutput
from app.providers.gemini_video import GeminiVideoProvider
from app.providers.mock_video import MockGeneratorVideoProvider
from app.providers.runway_video import RunwayVideoProvider
from app.services.video_assembly import VideoAssemblyService


SUCCESS_STATUSES = {"completed", "complete", "succeeded", "success", "done", "provider_succeeded"}
FAILURE_STATUSES = {"failed", "failure", "cancelled", "canceled", "errored", "error"}


class GeneratorVideoService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.assembly = VideoAssemblyService()

    def create_video_job_from_prompt_pack(
        self,
        prompt_pack_id: int,
        provider_name: str | None = None,
        *,
        max_scenes: int | None = None,
        full_video: bool = True,
        apply_safety_limits: bool = False,
    ) -> models.VideoJob:
        prompt_pack = self.db.get(models.PromptPack, prompt_pack_id)
        if not prompt_pack:
            raise MissingGeneratorDataError(f"PromptPack {prompt_pack_id} not found.")
        if not prompt_pack.script_variant_id:
            raise MissingGeneratorDataError("PromptPack must reference a script variant before video generation.")
        output = PromptPackOutput.model_validate(prompt_pack.prompt_pack_json)
        selected_prompts = self._selected_scene_prompts(
            output,
            max_scenes=max_scenes,
            full_video=full_video,
            apply_safety_limits=apply_safety_limits,
        )
        if not selected_prompts:
            raise MissingGeneratorDataError("PromptPack does not contain any scene prompts.")
        provider = provider_name or output.provider or self.settings.video_provider
        duration_seconds = sum(scene.duration_seconds for scene in selected_prompts)
        video_job = models.VideoJob(
            script_variant_id=prompt_pack.script_variant_id,
            provider=provider,
            status="provider_job_queued",
            aspect_ratio=output.aspect_ratio,
            duration_seconds=duration_seconds,
            cost_estimate=0,
            error_message=None,
        )
        self.db.add(video_job)
        self.db.flush()
        scenes = {scene.scene_number: scene for scene in video_job.script_variant.scenes}
        for prompt_scene in selected_prompts:
            scene = scenes.get(prompt_scene.scene_number)
            if not scene:
                continue
            self.db.add(
                models.VideoClip(
                    video_job_id=video_job.id,
                    scene_id=scene.id,
                    provider_job_id=None,
                    status="provider_job_queued",
                    raw_response_json={
                        "prompt_pack_id": prompt_pack.id,
                        "scene_number": prompt_scene.scene_number,
                        "duration_seconds": prompt_scene.duration_seconds,
                    },
                )
            )
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def start_provider_jobs(self, video_job: models.VideoJob, *, explicit_real_run: bool = False) -> models.VideoJob:
        require_real_video_allowed(video_job.provider, explicit_real_run)
        provider = self._provider(video_job.provider)
        output = self._prompt_pack_output_for_job(video_job)
        prompt_by_scene = {scene.scene_number: scene for scene in output.scene_prompts}
        for clip in sorted(video_job.clips, key=lambda item: item.scene.scene_number):
            if clip.provider_job_id:
                continue
            prompt_scene = prompt_by_scene.get(clip.scene.scene_number) or self._prompt_scene_from_clip(clip)
            one_scene_pack = PromptPackOutput(
                provider=video_job.provider,
                aspect_ratio=video_job.aspect_ratio,
                duration_seconds=prompt_scene.duration_seconds,
                scene_prompts=[prompt_scene],
            )
            provider_job = provider.create_generation(one_scene_pack)
            clip.provider_job_id = provider_job.provider_job_id
            clip.status = provider_job.status
            clip.raw_response_json = {
                **provider_job.raw_response,
                "requested_duration_seconds": prompt_scene.duration_seconds,
            }
        video_job.status = "provider_jobs_created"
        video_job.error_message = None
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def status(self, video_job: models.VideoJob) -> dict:
        return self.provider_status(video_job)

    def provider_status(self, video_job: models.VideoJob) -> dict:
        if not video_job.clips:
            return {"status": video_job.status, "provider": video_job.provider, "provider_jobs": []}
        provider = self._provider(video_job.provider)
        provider_jobs = []
        for clip in sorted(video_job.clips, key=lambda item: item.scene.scene_number):
            if not clip.provider_job_id:
                provider_jobs.append(
                    {
                        "scene_number": clip.scene.scene_number,
                        "provider_job_id": None,
                        "status": clip.status,
                    }
                )
                continue
            provider_status = provider.get_status(clip.provider_job_id)
            clip.status = provider_status.status
            requested_duration = (clip.raw_response_json or {}).get("requested_duration_seconds")
            clip.raw_response_json = {
                **provider_status.raw_response,
                **({"requested_duration_seconds": requested_duration} if requested_duration else {}),
            }
            provider_jobs.append(
                {
                    "scene_number": clip.scene.scene_number,
                    "provider_job_id": clip.provider_job_id,
                    "status": provider_status.status,
                    "raw_response": provider_status.raw_response,
                }
            )
        video_job.status = self._aggregate_status([item["status"] for item in provider_jobs])
        if video_job.status == "provider_failed":
            video_job.error_message = "At least one provider task failed."
        self.db.commit()
        return {
            "status": video_job.status,
            "provider": video_job.provider,
            "provider_jobs": provider_jobs,
        }

    def poll_until_complete(
        self,
        video_job: models.VideoJob,
        *,
        timeout_seconds: int | None = None,
        poll_interval_seconds: int = 5,
    ) -> dict:
        timeout = timeout_seconds if timeout_seconds is not None else self.settings.max_provider_poll_seconds
        deadline = time.monotonic() + max(0, timeout)
        while True:
            status = self.provider_status(video_job)
            if status["status"] in {"provider_succeeded", "provider_failed"}:
                return status
            if time.monotonic() >= deadline:
                video_job.status = "provider_poll_timeout"
                video_job.error_message = f"Provider polling exceeded {timeout} seconds."
                self.db.commit()
                raise ProviderConfigurationError(video_job.error_message)
            time.sleep(max(1, poll_interval_seconds))

    def download_outputs(self, video_job: models.VideoJob) -> list[str]:
        provider = self._provider(video_job.provider)
        target_dir = self.settings.media_root / "provider" / video_job.provider / f"video_job_{video_job.id}"
        local_paths = []
        for clip in sorted(video_job.clips, key=lambda item: item.scene.scene_number):
            if not clip.provider_job_id:
                raise MissingGeneratorDataError("Video job has a clip without a provider job id.")
            if video_job.provider == "mock":
                path = self.assembly.create_mock_clip(
                    video_job.id,
                    clip.scene.scene_number,
                    max(
                        1,
                        int((clip.raw_response_json or {}).get("requested_duration_seconds") or 0)
                        or int(clip.scene.time_end - clip.scene.time_start),
                    ),
                    clip.scene.caption or "",
                    clip.scene.video_prompt or "",
                )
                clip.clip_path = path
                local_paths.append(path)
                clip.status = "downloaded"
                continue
            paths = provider.download_outputs(clip.provider_job_id, target_dir)
            if not paths:
                raise MissingGeneratorDataError("Provider did not return any downloadable output paths.")
            clip.clip_path = paths[0].as_posix()
            clip.status = "downloaded"
            local_paths.append(clip.clip_path)
        video_job.status = "downloaded"
        self.db.commit()
        return local_paths

    def assemble(self, video_job: models.VideoJob) -> models.VideoJob:
        clips = sorted(video_job.clips, key=lambda item: item.scene.scene_number)
        clip_paths = [clip.clip_path for clip in clips if clip.clip_path]
        if not clip_paths:
            raise MissingGeneratorDataError("Video job has no downloaded clip paths to assemble.")
        output_path, preview_path = self.assembly.assemble(
            video_job.id,
            clip_paths,
            video_job.script_variant.final_cta or "Open the product card",
            [clip.scene.caption or "" for clip in clips],
        )
        video_job.output_video_path = output_path
        video_job.preview_path = preview_path
        video_job.status = WorkflowStatus.video_generated.value
        self.db.commit()
        self.db.refresh(video_job)
        self.write_generation_report(video_job)
        return video_job

    def write_generation_report(
        self,
        video_job: models.VideoJob,
        *,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> str:
        return GenerationReportWriter(self.db).write(video_job, warnings=warnings, errors=errors).as_posix()

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

    def _prompt_pack_output_for_job(self, video_job: models.VideoJob) -> PromptPackOutput:
        prompt_pack = self.db.scalar(
            select(models.PromptPack)
            .where(models.PromptPack.script_variant_id == video_job.script_variant_id)
            .order_by(models.PromptPack.id.desc())
        )
        if prompt_pack:
            output = PromptPackOutput.model_validate(prompt_pack.prompt_pack_json)
            return PromptPackOutput(
                provider=video_job.provider,
                aspect_ratio=output.aspect_ratio,
                duration_seconds=output.duration_seconds,
                scene_prompts=output.scene_prompts,
            )
        return PromptPackOutput(
            provider=video_job.provider,
            aspect_ratio=video_job.aspect_ratio,
            duration_seconds=video_job.duration_seconds,
            scene_prompts=[self._prompt_scene_from_clip(clip) for clip in video_job.clips],
        )

    def _selected_scene_prompts(
        self,
        output: PromptPackOutput,
        *,
        max_scenes: int | None,
        full_video: bool,
        apply_safety_limits: bool,
    ) -> list[PromptSceneOutput]:
        scenes = output.scene_prompts
        if not scenes:
            return []
        if apply_safety_limits:
            count = bounded_scene_count(max_scenes, full_video=full_video, available=len(scenes))
            max_seconds = max(1, self.settings.max_video_seconds_per_run)
        else:
            count = len(scenes) if max_scenes is None else max(1, min(max_scenes, len(scenes)))
            max_seconds = None

        selected = []
        total_seconds = 0
        for scene in scenes[:count]:
            duration = scene.duration_seconds
            if max_seconds is not None:
                remaining = max_seconds - total_seconds
                if remaining <= 0:
                    break
                duration = max(1, min(scene.duration_seconds, remaining))
            selected.append(scene.model_copy(update={"duration_seconds": duration}))
            total_seconds += duration
        return selected

    @staticmethod
    def _prompt_scene_from_clip(clip: models.VideoClip) -> PromptSceneOutput:
        return PromptSceneOutput(
            scene_number=clip.scene.scene_number,
            duration_seconds=max(1, int(clip.scene.time_end - clip.scene.time_start)),
            prompt_text=clip.scene.video_prompt or clip.scene.visual_description or "",
            negative_prompt=clip.scene.negative_prompt or "distorted product, unsupported claims, low quality",
        )

    @staticmethod
    def _aggregate_status(statuses: list[str]) -> str:
        normalized = {status.lower() for status in statuses if status}
        if normalized and normalized.issubset(SUCCESS_STATUSES):
            return "provider_succeeded"
        if normalized.intersection(FAILURE_STATUSES):
            return "provider_failed"
        return "provider_running"
