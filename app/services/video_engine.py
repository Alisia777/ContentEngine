from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.enums import WorkflowStatus
from app.providers.video import MockVideoProvider
from app.services.video_assembly import VideoAssemblyService


class VideoEngine:
    def __init__(
        self,
        db: Session,
        provider: MockVideoProvider | None = None,
        assembly: VideoAssemblyService | None = None,
    ):
        self.db = db
        self.provider = provider or MockVideoProvider()
        self.assembly = assembly or VideoAssemblyService()

    def create_job(self, script_variant_id: int, provider: str = "mock") -> models.VideoJob:
        variant = self.db.get(models.ScriptVariant, script_variant_id)
        if not variant:
            raise ValueError("Script variant not found")
        if variant.status != WorkflowStatus.script_approved.value:
            raise ValueError("Script variant must be approved before video generation")
        video_job = models.VideoJob(
            script_variant_id=variant.id,
            provider=provider,
            status=WorkflowStatus.video_generation_queued.value,
            aspect_ratio=variant.full_script_json.get("aspect_ratio", "9:16"),
            duration_seconds=variant.full_script_json.get("duration_seconds", 15),
            cost_estimate=0,
        )
        self.db.add(video_job)
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def run(self, video_job: models.VideoJob) -> models.VideoJob:
        variant = video_job.script_variant
        for clip in list(video_job.clips):
            self.db.delete(clip)
        self.db.flush()

        for scene in sorted(variant.scenes, key=lambda item: item.scene_number):
            duration = max(1, int(scene.time_end - scene.time_start))
            raw_response = self.provider.generate_clip(
                scene.video_prompt or "",
                scene.negative_prompt or "",
                variant.script_job.product.images_json or [],
                video_job.aspect_ratio,
                duration,
            )
            clip_path = self.assembly.create_mock_clip(
                video_job_id=video_job.id,
                scene_number=scene.scene_number,
                duration_seconds=duration,
                caption=scene.caption or "",
                prompt=scene.video_prompt or "",
            )
            self.db.add(
                models.VideoClip(
                    video_job_id=video_job.id,
                    scene_id=scene.id,
                    provider_job_id=raw_response["provider_job_id"],
                    status=WorkflowStatus.video_generated.value,
                    clip_path=clip_path,
                    raw_response_json=raw_response,
                )
            )

        self.db.commit()
        return self.assemble(video_job)

    def assemble(self, video_job: models.VideoJob) -> models.VideoJob:
        clips = sorted(video_job.clips, key=lambda item: item.scene.scene_number)
        captions = [clip.scene.caption or "" for clip in clips]
        output_path, preview_path = self.assembly.assemble(
            video_job.id,
            [clip.clip_path for clip in clips if clip.clip_path],
            video_job.script_variant.final_cta or "Learn more in the product card",
            captions,
        )
        video_job.output_video_path = output_path
        video_job.preview_path = preview_path
        video_job.status = WorkflowStatus.video_generated.value
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def regenerate_clip(self, clip: models.VideoClip) -> models.VideoClip:
        scene = clip.scene
        duration = max(1, int(scene.time_end - scene.time_start))
        raw_response = self.provider.generate_clip(
            scene.video_prompt or "",
            scene.negative_prompt or "",
            clip.video_job.script_variant.script_job.product.images_json or [],
            clip.video_job.aspect_ratio,
            duration,
        )
        clip.provider_job_id = raw_response["provider_job_id"]
        clip.status = WorkflowStatus.video_generated.value
        clip.clip_path = self.assembly.create_mock_clip(
            clip.video_job_id,
            scene.scene_number,
            duration,
            scene.caption or "",
            scene.video_prompt or "",
        )
        clip.raw_response_json = raw_response
        self.db.commit()
        self.db.refresh(clip)
        return clip

    def approve_video(self, video_job: models.VideoJob, reviewer_name: str = "admin") -> models.VideoJob:
        video_job.status = WorkflowStatus.video_approved.value
        self.db.add(
            models.Review(
                entity_type="video_job",
                entity_id=video_job.id,
                reviewer_name=reviewer_name,
                status="approved",
                comment="Video approved for publishing package generation.",
            )
        )
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

    def reject_video(self, video_job: models.VideoJob, reason: str = "Needs revision") -> models.VideoJob:
        video_job.status = "rejected"
        self.db.add(
            models.Review(
                entity_type="video_job",
                entity_id=video_job.id,
                reviewer_name="admin",
                status="rejected",
                rejection_reason=reason,
            )
        )
        self.db.commit()
        self.db.refresh(video_job)
        return video_job

