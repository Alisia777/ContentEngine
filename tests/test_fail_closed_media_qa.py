from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QVF_DATABASE_URL", "sqlite:///./test_qharisma.db")
os.environ.setdefault("QVF_MEDIA_ROOT", "test_media")

from app.output_acceptance.frame_extractor import FrameExtractor
from app.output_acceptance.output_quality_checker import OutputQualityChecker
from app.services.video_assembly import VideoAssemblyService


class _FakeDb:
    def __init__(self, video_job: SimpleNamespace):
        self.video_job = video_job

    def get(self, _model, entity_id: int):
        return self.video_job if entity_id == self.video_job.id else None

    def add(self, _entity) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, _entity) -> None:
        pass


def _approve(frame_result, *, provider: str = "runway"):
    return OutputQualityChecker().check(
        video_job=SimpleNamespace(output_video_path="output.mp4", provider=provider),
        brief=SimpleNamespace(scene_blueprints=[{"scene_number": 1}]),
        frame_result=frame_result,
        decision="approve",
        product_identity_status="pass",
        packaging_status="pass",
        geometry_status="pass",
        blogger_authenticity_status="pass",
        scene_match_status="pass",
        proof_moment_status="pass",
        cta_status="pass",
    )


def test_text_mp4_synthetic_fallback_cannot_be_approved(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "not-a-video.mp4"
    VideoAssemblyService._write_placeholder_video(video_path, "test placeholder")
    video_job = SimpleNamespace(id=1, output_video_path=video_path.as_posix(), duration_seconds=5)
    extractor = FrameExtractor(_FakeDb(video_job))
    extractor.settings = SimpleNamespace(media_root=tmp_path)

    def fail_decode(_video_path, _frame_dir, _max_frames, warnings, **_kwargs):
        warnings.append("ffmpeg_extract_failed_synthetic_frames_used")
        return []

    monkeypatch.setattr(extractor, "_extract_with_ffmpeg", fail_decode)
    frame_result = extractor.extract(video_job.id, max_frames=1)
    quality = _approve(frame_result)

    assert "synthetic_frames_used_no_cv" in frame_result.warnings_json
    assert "synthetic_frames_used_no_cv" in quality.blockers
    assert "ffmpeg_extract_failed_synthetic_frames_used" in quality.blockers
    assert "attach_decodable_non_placeholder_video_output" in quality.required_fixes
    assert quality.status != "approved"
    assert quality.publishing_readiness == "blocked"


def test_synthetic_frame_path_is_blocked_even_if_warning_is_missing():
    frame_result = SimpleNamespace(
        contact_sheet_path="contact-sheet.png",
        frame_paths_json=["frames/synthetic_frame_01.png"],
        warnings_json=[],
    )

    quality = _approve(frame_result)

    assert "synthetic_frames_used_no_cv" in quality.blockers
    assert quality.status != "approved"
    assert quality.publishing_readiness == "blocked"


def test_placeholder_frame_path_is_blocked_even_if_warning_is_missing():
    frame_result = SimpleNamespace(
        contact_sheet_path="contact-sheet.png",
        frame_paths_json=["frames/placeholder_frame_01.png"],
        warnings_json=[],
    )

    quality = _approve(frame_result)

    assert "placeholder_frames_not_publishable" in quality.blockers
    assert quality.status != "approved"
    assert quality.publishing_readiness == "blocked"


def test_decodable_mock_demo_cannot_be_publishing_ready():
    frame_result = SimpleNamespace(
        contact_sheet_path="contact-sheet.png",
        frame_paths_json=["frames/frame_01.png"],
        warnings_json=[],
    )

    quality = _approve(frame_result, provider="mock")

    assert "mock_video_output_not_publishable" in quality.blockers
    assert "generate_or_attach_real_video_output" in quality.required_fixes
    assert quality.status != "approved"
    assert quality.publishing_readiness == "blocked"
