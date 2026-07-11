from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import uuid

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.output_acceptance.contact_sheet_service import ContactSheetService
from app.output_acceptance.errors import OutputAcceptanceDataError
from app.output_acceptance.types import FrameExtractionOutput
from app.system_tools import resolve_ffmpeg, resolve_ffprobe


class FrameExtractor:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    @property
    def ffmpeg_path(self) -> str | None:
        return resolve_ffmpeg(self.settings).path

    @property
    def ffprobe_path(self) -> str | None:
        return resolve_ffprobe(self.settings).path

    def extract(self, video_job_id: int, *, max_frames: int = 5) -> models.FrameExtractionResult:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise OutputAcceptanceDataError(f"VideoJob {video_job_id} not found.")
        if not video_job.output_video_path:
            raise OutputAcceptanceDataError(f"VideoJob {video_job_id} has no output_video_path.")
        video_path = Path(video_job.output_video_path)
        desired_frames = self._desired_frame_count(max_frames)
        source_before = self._stable_source_fingerprint(video_path)
        extraction_key = uuid.uuid4().hex
        output_dir = (
            self.settings.media_root
            / "output_acceptance"
            / f"video_job_{video_job.id}"
            / f"extraction_{extraction_key}"
        )
        frame_dir = output_dir / "frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        frame_paths = self._extract_with_ffmpeg(
            video_path,
            frame_dir,
            desired_frames,
            warnings,
            duration_hint=float(video_job.duration_seconds or 0),
        )
        source_after = self._stable_source_fingerprint(video_path)
        if source_before != source_after:
            raise OutputAcceptanceDataError(
                "Source video changed during frame extraction; no evidence was recorded."
            )
        if not frame_paths:
            frame_paths = self._create_synthetic_frames(
                video_job,
                video_path,
                frame_dir,
                desired_frames,
            )
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
            extraction_key=extraction_key,
            source_video_sha256=(source_before[0] if source_before else None),
            source_video_size_bytes=(source_before[1] if source_before else None),
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

    def _extract_with_ffmpeg(
        self,
        video_path: Path,
        frame_dir: Path,
        max_frames: int,
        warnings: list[str],
        *,
        duration_hint: float = 0,
    ) -> list[str]:
        if not self.ffmpeg_path or not video_path.exists():
            if not video_path.exists():
                warnings.append("video_file_missing_synthetic_frames_used")
            return []
        pattern = frame_dir / "frame_%02d.png"
        desired_frames = self._desired_frame_count(max_frames)
        sample_duration = max(
            float(self._video_duration_hint(video_path) or duration_hint or 1.0),
            1.0,
        )
        sample_rate = desired_frames / sample_duration
        try:
            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-y",
                    "-i",
                    str(video_path),
                    "-vf",
                    f"fps={sample_rate:.8f}",
                    "-frames:v",
                    str(desired_frames),
                    str(pattern),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=90,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            OSError,
        ):
            warnings.append("ffmpeg_extract_failed_synthetic_frames_used")
            return []
        paths = [
            path.as_posix()
            for path in sorted(frame_dir.glob("frame_*.png"))[:desired_frames]
        ]
        if len(paths) < 2:
            warnings.append("ffmpeg_extract_incomplete")
        return paths

    @staticmethod
    def _desired_frame_count(value: int) -> int:
        if isinstance(value, bool):
            raise OutputAcceptanceDataError("max_frames must be an integer from 2 to 30.")
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise OutputAcceptanceDataError(
                "max_frames must be an integer from 2 to 30."
            ) from exc
        return min(max(parsed, 2), 30)

    def _video_duration_hint(self, video_path: Path) -> float | None:
        """Read duration with ffprobe when available; failure remains fail-closed."""

        ffprobe = self.ffprobe_path
        if not ffprobe:
            return None
        try:
            completed = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
            duration = float((completed.stdout or "").strip())
            return duration if duration > 0 else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, OSError):
            return None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _stable_source_fingerprint(cls, path: Path) -> tuple[str, int] | None:
        if not path.is_file():
            return None
        try:
            before = path.stat()
            digest = cls._sha256(path)
            after = path.stat()
        except OSError as exc:
            raise OutputAcceptanceDataError(
                "Source video could not be fingerprinted for frame extraction."
            ) from exc
        if (
            before.st_size,
            before.st_mtime_ns,
            getattr(before, "st_ino", None),
        ) != (
            after.st_size,
            after.st_mtime_ns,
            getattr(after, "st_ino", None),
        ):
            raise OutputAcceptanceDataError(
                "Source video changed while it was being fingerprinted."
            )
        return digest, after.st_size

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
