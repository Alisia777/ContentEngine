from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.output_acceptance.contact_sheet_service import ContactSheetService
from app.output_acceptance.errors import OutputAcceptanceDataError
from app.output_acceptance.types import FrameExtractionOutput


class FrameExtractor:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    @property
    def ffmpeg_path(self) -> str | None:
        return shutil.which("ffmpeg")

    def extract(self, video_job_id: int, *, max_frames: int = 5) -> models.FrameExtractionResult:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise OutputAcceptanceDataError(f"VideoJob {video_job_id} not found.")
        if not video_job.output_video_path:
            raise OutputAcceptanceDataError(f"VideoJob {video_job_id} has no output_video_path.")
        video_path = Path(video_job.output_video_path)
        output_dir = self.settings.media_root / "output_acceptance" / f"video_job_{video_job.id}"
        frame_dir = output_dir / "frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        frame_paths = self._extract_with_ffmpeg(video_path, frame_dir, max_frames, warnings)
        if not frame_paths:
            frame_paths = self._create_synthetic_frames(video_job, video_path, frame_dir, max_frames)
            warnings.append("synthetic_frames_used_no_cv")
        contact_sheet_path = ContactSheetService().build(frame_paths, output_dir / "contact_sheet.png")
        result = models.FrameExtractionResult(
            video_job_id=video_job.id,
            status="created",
            frame_paths_json=frame_paths,
            contact_sheet_path=contact_sheet_path,
            duration_seconds=float(video_job.duration_seconds or 0),
            fps=round(len(frame_paths) / max(float(video_job.duration_seconds or len(frame_paths)), 1.0), 3),
            warnings_json=warnings,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def latest_for_video_job(self, video_job_id: int) -> models.FrameExtractionResult | None:
        return self.db.scalar(
            select(models.FrameExtractionResult)
            .where(models.FrameExtractionResult.video_job_id == video_job_id)
            .order_by(models.FrameExtractionResult.id.desc())
        )

    @staticmethod
    def as_output(result: models.FrameExtractionResult) -> FrameExtractionOutput:
        return FrameExtractionOutput(
            id=result.id,
            video_job_id=result.video_job_id,
            status=result.status,
            frame_paths=result.frame_paths_json or [],
            contact_sheet_path=result.contact_sheet_path,
            duration_seconds=result.duration_seconds,
            fps=result.fps,
            warnings=result.warnings_json or [],
        )

    def _extract_with_ffmpeg(self, video_path: Path, frame_dir: Path, max_frames: int, warnings: list[str]) -> list[str]:
        if not self.ffmpeg_path or not video_path.exists():
            if not video_path.exists():
                warnings.append("video_file_missing_synthetic_frames_used")
            return []
        pattern = frame_dir / "frame_%02d.png"
        try:
            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-y",
                    "-i",
                    str(video_path),
                    "-vf",
                    f"fps=1/{max(max_frames, 1)}",
                    "-frames:v",
                    str(max_frames),
                    str(pattern),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            warnings.append("ffmpeg_extract_failed_synthetic_frames_used")
            return []
        return [path.as_posix() for path in sorted(frame_dir.glob("frame_*.png"))[:max_frames]]

    @staticmethod
    def _create_synthetic_frames(
        video_job: models.VideoJob,
        video_path: Path,
        frame_dir: Path,
        max_frames: int,
    ) -> list[str]:
        colors = [(14, 116, 144), (22, 101, 52), (133, 77, 14), (127, 29, 29), (49, 46, 129)]
        frame_paths: list[str] = []
        for index in range(1, max_frames + 1):
            image = Image.new("RGB", (360, 640), colors[(index - 1) % len(colors)])
            draw = ImageDraw.Draw(image)
            draw.rectangle((24, 24, 336, 616), outline=(255, 255, 255), width=3)
            draw.text((42, 72), f"Video job #{video_job.id}", fill=(255, 255, 255))
            draw.text((42, 112), f"Frame {index}", fill=(255, 255, 255))
            draw.text((42, 152), video_path.name[:36], fill=(255, 255, 255))
            draw.text((42, 548), "Synthetic review frame", fill=(255, 255, 255))
            frame_path = frame_dir / f"synthetic_frame_{index:02d}.png"
            image.save(frame_path)
            frame_paths.append(frame_path.as_posix())
        return frame_paths
