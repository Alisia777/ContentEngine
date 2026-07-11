from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.output_acceptance import AcceptanceReviewService, FrameExtractor
from app.output_acceptance.errors import OutputAcceptanceDataError
from app.visual_evidence import (
    ReferenceTextInput,
    VisualEvidenceService,
    VisualEvidenceSnapshotError,
    VisualEvidenceSnapshotService,
)


class FakeOCR:
    name = "fake_local_ocr"
    available = True

    def __init__(self, text: str = ""):
        self.text = text

    def extract_text(self, _image_path: Path, *, language: str, timeout_seconds: float) -> str:
        return self.text


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame(path: Path, color: tuple[int, int, int], label: str) -> Path:
    image = Image.new("RGB", (720, 1280), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 70, 670, 1210), outline=(255, 255, 255), width=12)
    draw.text((100, 140), label, fill=(255, 255, 255))
    image.save(path, format="PNG")
    return path


def _evidence_fixture(
    db: Session,
    tmp_path: Path,
) -> tuple[models.VideoJob, models.FrameExtractionResult, object, list[Path], Path]:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"exact-video-source-v1")
    frames = [
        _frame(tmp_path / "frame-1.png", (180, 20, 20), "one"),
        _frame(tmp_path / "frame-2.png", (20, 150, 40), "two"),
    ]
    video_job = models.VideoJob(
        script_variant_id=1,
        provider="runway",
        output_video_path=source.as_posix(),
        status="completed",
    )
    db.add(video_job)
    db.flush()
    frame_result = models.FrameExtractionResult(
        video_job_id=video_job.id,
        status="created",
        frame_paths_json=[path.as_posix() for path in frames],
        duration_seconds=10,
        fps=0.2,
        warnings_json=[],
        extraction_key="extraction-1",
        source_video_sha256=_sha256(source),
        source_video_size_bytes=source.stat().st_size,
    )
    db.add(frame_result)
    db.commit()
    report = VisualEvidenceService(ocr_backend=FakeOCR()).evaluate(frames)
    assert report.status == "passed"
    return video_job, frame_result, report, frames, source


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("extraction_key", None, "legacy_frame_extraction_missing_key"),
        (
            "source_video_sha256",
            None,
            "legacy_frame_extraction_missing_source_hash",
        ),
        (
            "source_video_size_bytes",
            None,
            "legacy_frame_extraction_missing_source_size",
        ),
    ],
)
def test_snapshot_rejects_legacy_extraction_without_exact_source_lineage(
    db: Session,
    tmp_path: Path,
    field: str,
    value: object,
    error: str,
):
    video_job, frame_result, report, _frames, _source = _evidence_fixture(db, tmp_path)
    setattr(frame_result, field, value)

    with pytest.raises(VisualEvidenceSnapshotError, match=error):
        VisualEvidenceSnapshotService(db).record(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )

    assert db.scalar(select(func.count()).select_from(models.VisualEvidenceSnapshot)) == 0


def test_snapshot_rejects_source_tampered_after_extraction(
    db: Session,
    tmp_path: Path,
):
    video_job, frame_result, report, _frames, source = _evidence_fixture(db, tmp_path)
    source.write_bytes(b"different-video-source")

    with pytest.raises(
        VisualEvidenceSnapshotError,
        match="source_video_changed_after_frame_extraction",
    ):
        VisualEvidenceSnapshotService(db).record(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )

    assert db.scalar(select(func.count()).select_from(models.VisualEvidenceSnapshot)) == 0


def test_snapshot_rejects_frame_tampered_after_report(
    db: Session,
    tmp_path: Path,
):
    video_job, frame_result, report, frames, _source = _evidence_fixture(db, tmp_path)
    _frame(frames[0], (1, 2, 3), "tampered")

    with pytest.raises(VisualEvidenceSnapshotError, match="evidence_frame_hash_mismatch"):
        VisualEvidenceSnapshotService(db).record(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )

    assert db.scalar(select(func.count()).select_from(models.VisualEvidenceSnapshot)) == 0


def test_snapshot_requires_report_to_cover_exact_extraction_paths(
    db: Session,
    tmp_path: Path,
):
    video_job, frame_result, report, _frames, _source = _evidence_fixture(db, tmp_path)
    report = report.model_copy(deep=True)
    report.frames = report.frames[:1]
    report.frame_count = 1

    with pytest.raises(
        VisualEvidenceSnapshotError,
        match="visual_evidence_frame_path_set_mismatch",
    ):
        VisualEvidenceSnapshotService(db).record(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )


def test_changed_ocr_contract_cannot_reuse_stale_snapshot(
    db: Session,
    tmp_path: Path,
):
    video_job, frame_result, _report, frames, _source = _evidence_fixture(db, tmp_path)
    service = VisualEvidenceSnapshotService(db)
    first_report = VisualEvidenceService(ocr_backend=FakeOCR("BOMBBAR 60G NEW")).evaluate(
        frames,
        references=[
            ReferenceTextInput(
                source_kind="operator_input",
                source_ref="operator:packaging:v1",
                required_tokens=["BOMBBAR", "60G"],
            )
        ],
    )
    second_report = VisualEvidenceService(ocr_backend=FakeOCR("BOMBBAR 60G NEW")).evaluate(
        frames,
        references=[
            ReferenceTextInput(
                source_kind="operator_input",
                source_ref="operator:packaging:v2",
                required_tokens=["BOMBBAR", "60G", "NEW"],
            )
        ],
    )

    first = service.record(
        video_job=video_job,
        frame_result=frame_result,
        report=first_report,
    )
    exact_replay = service.record(
        video_job=video_job,
        frame_result=frame_result,
        report=first_report,
    )
    second = service.record(
        video_job=video_job,
        frame_result=frame_result,
        report=second_report,
    )

    assert exact_replay.id == first.id
    assert first.report_sha256 != second.report_sha256
    assert first.id != second.id
    assert db.scalar(select(func.count()).select_from(models.VisualEvidenceSnapshot)) == 2


def test_verify_current_blocks_source_or_frame_replacement(
    db: Session,
    tmp_path: Path,
):
    video_job, frame_result, report, frames, source = _evidence_fixture(db, tmp_path)
    service = VisualEvidenceSnapshotService(db)
    snapshot = service.record(
        video_job=video_job,
        frame_result=frame_result,
        report=report,
    )

    _frame(frames[1], (4, 5, 6), "replacement")
    with pytest.raises(VisualEvidenceSnapshotError, match="evidence_frame_hash_mismatch"):
        service.verify_current(snapshot)

    _frame(frames[1], (20, 150, 40), "two")
    source.write_bytes(b"replacement-source")
    with pytest.raises(
        VisualEvidenceSnapshotError,
        match="source_video_changed_after_frame_extraction",
    ):
        service.verify_current(snapshot)


def test_acceptance_and_new_snapshot_rollback_together_on_final_verification_failure(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    video_job, _frame_result, _report, _frames, _source = _evidence_fixture(db, tmp_path)
    product = models.Product(
        sku="snapshot-atomic-sku",
        brand="Test",
        title="Atomic evidence",
    )
    db.add(product)
    db.flush()
    video_job.product_id = product.id
    brief = models.AIProductionBrief(
        product_id=product.id,
        sku=product.sku,
        product_identity_rules_json={},
        status="approved",
    )
    db.add(brief)
    db.commit()

    original_verify = VisualEvidenceSnapshotService.verify_current
    call_count = 0

    def fail_final_verify(self, snapshot, *, expected_report=None):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise VisualEvidenceSnapshotError("changed_before_commit")
        return original_verify(self, snapshot, expected_report=expected_report)

    monkeypatch.setattr(VisualEvidenceSnapshotService, "verify_current", fail_final_verify)

    with pytest.raises(OutputAcceptanceDataError):
        AcceptanceReviewService(db).review(
            video_job_id=video_job.id,
            ai_production_brief_id=brief.id,
            decision="approve",
            product_identity_status="pass",
            packaging_status="pass",
            geometry_status="pass",
            blogger_authenticity_status="pass",
            scene_match_status="pass",
            proof_moment_status="pass",
            cta_status="pass",
        )

    assert db.scalar(select(func.count()).select_from(models.VisualEvidenceSnapshot)) == 0
    assert db.scalar(select(func.count()).select_from(models.VideoOutputAcceptance)) == 0


def test_frame_extractor_rejects_source_changed_during_ffmpeg_window(
    db: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-before-ffmpeg")
    video_job = models.VideoJob(
        script_variant_id=1,
        provider="runway",
        output_video_path=source.as_posix(),
        status="completed",
    )
    db.add(video_job)
    db.commit()
    extractor = FrameExtractor(db)
    extractor.settings = SimpleNamespace(media_root=tmp_path / "media")

    def mutate_source(*_args, **_kwargs):
        source.write_bytes(b"source-after-ffmpeg")
        return []

    monkeypatch.setattr(extractor, "_extract_with_ffmpeg", mutate_source)

    with pytest.raises(OutputAcceptanceDataError, match="changed during frame extraction"):
        extractor.extract(video_job.id)

    assert db.scalar(select(func.count()).select_from(models.FrameExtractionResult)) == 0
