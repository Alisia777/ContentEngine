from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.visual_evidence.types import VisualEvidenceReport


VISUAL_EVIDENCE_ALGORITHM_VERSION = "visual_evidence_v1"


class VisualEvidenceSnapshotError(ValueError):
    pass


class VisualEvidenceSnapshotService:
    """Persist and verify immutable evidence for an exact source video/extraction."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        video_job: models.VideoJob,
        frame_result: models.FrameExtractionResult,
        report: VisualEvidenceReport,
        commit: bool = True,
    ) -> models.VisualEvidenceSnapshot:
        source_sha, report_payload, frame_manifest = self._validate_current_evidence(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )
        frame_manifest_sha = self._canonical_sha(frame_manifest)
        policy_sha = self._canonical_sha(report_payload["policy"])
        report_sha = self._report_fingerprint(report_payload)
        existing = self.db.scalar(
            select(models.VisualEvidenceSnapshot).where(
                models.VisualEvidenceSnapshot.frame_extraction_result_id == frame_result.id,
                models.VisualEvidenceSnapshot.frame_manifest_sha256 == frame_manifest_sha,
                models.VisualEvidenceSnapshot.policy_sha256 == policy_sha,
                models.VisualEvidenceSnapshot.report_sha256 == report_sha,
            )
        )
        if existing:
            self.verify_current(existing, expected_report=report)
            return existing

        snapshot = models.VisualEvidenceSnapshot(
            video_job_id=video_job.id,
            frame_extraction_result_id=frame_result.id,
            source_video_sha256=source_sha,
            frame_manifest_sha256=frame_manifest_sha,
            policy_sha256=policy_sha,
            report_sha256=report_sha,
            status=report.status,
            report_json=report_payload,
        )
        self._ensure_sqlite_outer_transaction()
        try:
            # Keep a concurrent idempotent insert inside a savepoint. A unique
            # race must not roll back the outer acceptance transaction.
            with self.db.begin_nested():
                self.db.add(snapshot)
                self.db.flush()
        except IntegrityError:
            winner = self.db.scalar(
                select(models.VisualEvidenceSnapshot).where(
                    models.VisualEvidenceSnapshot.frame_extraction_result_id == frame_result.id,
                    models.VisualEvidenceSnapshot.frame_manifest_sha256 == frame_manifest_sha,
                    models.VisualEvidenceSnapshot.policy_sha256 == policy_sha,
                    models.VisualEvidenceSnapshot.report_sha256 == report_sha,
                )
            )
            if winner:
                self.verify_current(winner, expected_report=report)
                return winner
            raise
        if not commit:
            return snapshot
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise
        self.db.refresh(snapshot)
        return snapshot

    def _ensure_sqlite_outer_transaction(self) -> None:
        """Prevent a released SQLite savepoint from committing by itself.

        Python's legacy sqlite transaction mode does not emit ``BEGIN`` for
        SELECT statements. Without an explicit outer transaction, releasing the
        idempotency savepoint would make ``commit=False`` durable and break the
        snapshot+acceptance atomicity contract.
        """

        connection = self.db.connection()
        if connection.dialect.name != "sqlite":
            return
        raw_connection = getattr(connection.connection, "driver_connection", None)
        if raw_connection is None:
            raw_connection = connection.connection
        if not bool(getattr(raw_connection, "in_transaction", False)):
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    def latest_for_frame_result(
        self,
        frame_extraction_result_id: int,
    ) -> models.VisualEvidenceSnapshot | None:
        return self.db.scalar(
            select(models.VisualEvidenceSnapshot)
            .where(
                models.VisualEvidenceSnapshot.frame_extraction_result_id
                == frame_extraction_result_id
            )
            .order_by(models.VisualEvidenceSnapshot.id.desc())
        )

    def latest_for_video_job(
        self,
        video_job_id: int,
    ) -> models.VisualEvidenceSnapshot | None:
        return self.db.scalar(
            select(models.VisualEvidenceSnapshot)
            .where(models.VisualEvidenceSnapshot.video_job_id == video_job_id)
            .order_by(models.VisualEvidenceSnapshot.id.desc())
        )

    @staticmethod
    def report(snapshot: models.VisualEvidenceSnapshot) -> VisualEvidenceReport:
        try:
            return VisualEvidenceReport.model_validate(snapshot.report_json or {})
        except (TypeError, ValueError) as exc:
            raise VisualEvidenceSnapshotError("visual_evidence_report_invalid") from exc

    def verify_current(
        self,
        snapshot: models.VisualEvidenceSnapshot,
        *,
        expected_report: VisualEvidenceReport | None = None,
    ) -> None:
        video_job = self.db.get(models.VideoJob, snapshot.video_job_id)
        frame_result = self.db.get(
            models.FrameExtractionResult,
            snapshot.frame_extraction_result_id,
        )
        if not video_job or not frame_result:
            raise VisualEvidenceSnapshotError("visual_evidence_lineage_missing")
        if frame_result.video_job_id != video_job.id:
            raise VisualEvidenceSnapshotError("visual_evidence_lineage_mismatch")
        report = self.report(snapshot)
        source_sha, report_payload, frame_manifest = self._validate_current_evidence(
            video_job=video_job,
            frame_result=frame_result,
            report=report,
        )
        if source_sha != snapshot.source_video_sha256:
            raise VisualEvidenceSnapshotError("source_video_snapshot_hash_mismatch")
        if self._canonical_sha(frame_manifest) != snapshot.frame_manifest_sha256:
            raise VisualEvidenceSnapshotError("visual_evidence_frame_manifest_mismatch")
        if self._canonical_sha(report_payload["policy"]) != snapshot.policy_sha256:
            raise VisualEvidenceSnapshotError("visual_evidence_policy_mismatch")
        report_sha = self._report_fingerprint(report_payload)
        if not self._is_sha256(snapshot.report_sha256) or report_sha != snapshot.report_sha256:
            raise VisualEvidenceSnapshotError("visual_evidence_report_fingerprint_mismatch")
        if snapshot.status != report.status:
            raise VisualEvidenceSnapshotError("visual_evidence_status_mismatch")
        if expected_report is not None:
            expected_payload = expected_report.model_dump(mode="json")
            if self._report_fingerprint(expected_payload) != report_sha:
                raise VisualEvidenceSnapshotError("visual_evidence_report_replay_mismatch")

    def _validate_current_evidence(
        self,
        *,
        video_job: models.VideoJob,
        frame_result: models.FrameExtractionResult,
        report: VisualEvidenceReport,
    ) -> tuple[str, dict, list[dict]]:
        """Validate exact source and every reported frame before trusting evidence."""

        if frame_result.video_job_id != video_job.id:
            raise VisualEvidenceSnapshotError("frame_result_video_job_mismatch")
        if not str(frame_result.extraction_key or "").strip():
            raise VisualEvidenceSnapshotError("legacy_frame_extraction_missing_key")
        if not self._is_sha256(frame_result.source_video_sha256):
            raise VisualEvidenceSnapshotError("legacy_frame_extraction_missing_source_hash")
        if frame_result.source_video_size_bytes is None:
            raise VisualEvidenceSnapshotError("legacy_frame_extraction_missing_source_size")
        try:
            expected_source_size = int(frame_result.source_video_size_bytes)
        except (TypeError, ValueError) as exc:
            raise VisualEvidenceSnapshotError(
                "legacy_frame_extraction_invalid_source_size"
            ) from exc
        if expected_source_size < 0:
            raise VisualEvidenceSnapshotError("legacy_frame_extraction_invalid_source_size")

        source_path = Path(str(video_job.output_video_path or ""))
        if not source_path.is_file():
            raise VisualEvidenceSnapshotError("source_video_missing_for_evidence_snapshot")
        source_sha, source_size = self._stable_file_fingerprint(
            source_path,
            changed_error="source_video_changed_during_evidence_verification",
        )
        if (
            source_sha != str(frame_result.source_video_sha256).lower()
            or source_size != expected_source_size
        ):
            raise VisualEvidenceSnapshotError("source_video_changed_after_frame_extraction")

        report_payload = report.model_dump(mode="json")
        extraction_paths = [
            self._canonical_path(value) for value in (frame_result.frame_paths_json or [])
        ]
        reported_paths = [self._canonical_path(frame.path) for frame in report.frames]
        if len(extraction_paths) != len(set(extraction_paths)):
            raise VisualEvidenceSnapshotError("frame_extraction_contains_duplicate_paths")
        if reported_paths != extraction_paths:
            raise VisualEvidenceSnapshotError("visual_evidence_frame_path_set_mismatch")
        if report.frame_count != len(report.frames):
            raise VisualEvidenceSnapshotError("visual_evidence_frame_count_mismatch")
        if [frame.index for frame in report.frames] != list(range(1, len(report.frames) + 1)):
            raise VisualEvidenceSnapshotError("visual_evidence_frame_index_mismatch")

        frame_manifest: list[dict] = []
        for frame, canonical_path in zip(report.frames, reported_paths):
            if not self._is_sha256(frame.sha256):
                raise VisualEvidenceSnapshotError("visual_evidence_frame_hash_missing")
            path = Path(frame.path)
            if not path.is_file():
                raise VisualEvidenceSnapshotError("evidence_frame_missing")
            current_sha, _ = self._stable_file_fingerprint(
                path,
                changed_error="evidence_frame_changed_during_verification",
            )
            if current_sha != str(frame.sha256).lower():
                raise VisualEvidenceSnapshotError("evidence_frame_hash_mismatch")
            frame_manifest.append(
                {
                    "index": frame.index,
                    "path": canonical_path,
                    "sha256": current_sha,
                    "decoded": frame.decoded,
                    "blockers": list(frame.blockers),
                }
            )
        return source_sha, report_payload, frame_manifest

    @staticmethod
    def _canonical_sha(value) -> str:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def _report_fingerprint(cls, report_payload: dict) -> str:
        return cls._canonical_sha(
            {
                "algorithm_version": VISUAL_EVIDENCE_ALGORITHM_VERSION,
                "report": report_payload,
            }
        )

    @staticmethod
    def _canonical_path(value: str | Path) -> str:
        return Path(str(value)).as_posix()

    @staticmethod
    def _is_sha256(value: object) -> bool:
        return bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(value or "")))

    @classmethod
    def _stable_file_fingerprint(
        cls,
        path: Path,
        *,
        changed_error: str,
    ) -> tuple[str, int]:
        try:
            before = path.stat()
            digest = cls._sha256(path)
            after = path.stat()
        except OSError as exc:
            raise VisualEvidenceSnapshotError(changed_error) from exc
        before_identity = (
            before.st_size,
            before.st_mtime_ns,
            getattr(before, "st_ino", None),
        )
        after_identity = (
            after.st_size,
            after.st_mtime_ns,
            getattr(after, "st_ino", None),
        )
        if before_identity != after_identity:
            raise VisualEvidenceSnapshotError(changed_error)
        return digest, after.st_size

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
