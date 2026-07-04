from __future__ import annotations

from pathlib import Path

from app import models
from app.config import get_settings


class ArtifactManager:
    def __init__(self):
        self.settings = get_settings()

    def generation_report_path(self, video_job: models.VideoJob | None) -> Path | None:
        if not video_job:
            return None
        return self.settings.media_root / "generation_reports" / f"{video_job.id}.json"

    @staticmethod
    def file_exists_and_non_empty(path: str | None) -> tuple[bool, bool]:
        if not path:
            return False, False
        file_path = Path(path)
        exists = file_path.exists()
        return exists, exists and file_path.stat().st_size > 0
