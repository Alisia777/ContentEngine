from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.output_acceptance.errors import OutputAcceptanceDataError
from app.output_acceptance.frame_extractor import FrameExtractor
from app.output_acceptance.output_quality_checker import OutputQualityChecker
from app.output_acceptance.types import OutputAcceptanceOutput
from app.visual_evidence import VisualEvidenceSnapshotError, VisualEvidenceSnapshotService


class AcceptanceReviewService:
    def __init__(
        self,
        db: Session,
        *,
        quality_checker: OutputQualityChecker | None = None,
    ):
        self.db = db
        self.quality_checker = quality_checker or OutputQualityChecker()

    def review(
        self,
        *,
        video_job_id: int,
        ai_production_brief_id: int,
        director_prompt_pack_id: int | None = None,
        decision: str = "needs_human_review",
        product_identity_status: str = "needs_review",
        packaging_status: str = "needs_review",
        geometry_status: str = "needs_review",
        blogger_authenticity_status: str = "needs_review",
        scene_match_status: str = "needs_review",
        proof_moment_status: str = "needs_review",
        cta_status: str = "needs_review",
        reviewer_notes: str | None = None,
        commit: bool = True,
    ) -> models.VideoOutputAcceptance:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise OutputAcceptanceDataError(f"VideoJob {video_job_id} not found.")
        brief = self.db.get(models.AIProductionBrief, ai_production_brief_id)
        if not brief:
            raise OutputAcceptanceDataError(f"AIProductionBrief {ai_production_brief_id} not found.")
        self._validate_lineage(video_job, brief)
        prompt = self._director_prompt(brief.id, director_prompt_pack_id)
        frame_result = FrameExtractor(self.db).latest_for_video_job(video_job.id)
        quality = self.quality_checker.check(
            video_job=video_job,
            brief=brief,
            frame_result=frame_result,
            decision=decision,
            product_identity_status=product_identity_status,
            packaging_status=packaging_status,
            geometry_status=geometry_status,
            blogger_authenticity_status=blogger_authenticity_status,
            scene_match_status=scene_match_status,
            proof_moment_status=proof_moment_status,
            cta_status=cta_status,
        )
        statuses = quality.normalized_statuses
        if frame_result is None or quality.visual_evidence is None:
            raise OutputAcceptanceDataError(
                "An immutable visual evidence snapshot is required before output review."
            )
        evidence_service = VisualEvidenceSnapshotService(self.db)
        try:
            evidence_snapshot = evidence_service.record(
                video_job=video_job,
                frame_result=frame_result,
                report=quality.visual_evidence,
                commit=False,
            )
            evidence_service.verify_current(
                evidence_snapshot,
                expected_report=quality.visual_evidence,
            )
            acceptance = models.VideoOutputAcceptance(
                video_job_id=video_job.id,
                ai_production_brief_id=brief.id,
                director_prompt_pack_id=prompt.id if prompt else None,
                status=quality.status,
                product_identity_status=statuses["product_identity_status"],
                packaging_status=statuses["packaging_status"],
                geometry_status=statuses["geometry_status"],
                blogger_authenticity_status=statuses["blogger_authenticity_status"],
                scene_match_status=statuses["scene_match_status"],
                proof_moment_status=statuses["proof_moment_status"],
                cta_status=statuses["cta_status"],
                publishing_readiness=quality.publishing_readiness,
                score=quality.score,
                blockers_json=quality.blockers,
                required_fixes_json=quality.required_fixes,
                contact_sheet_path=frame_result.contact_sheet_path,
                keyframes_json=self._keyframes(frame_result),
                visual_evidence_snapshot_id=evidence_snapshot.id,
                reviewer_notes=reviewer_notes,
            )
            self.db.add(acceptance)
            self.db.flush()
            # Recheck after both rows exist in the same transaction. This also
            # proves an idempotently replayed snapshot is byte-for-byte the
            # report that was just computed for this acceptance.
            evidence_service.verify_current(
                evidence_snapshot,
                expected_report=quality.visual_evidence,
            )
            if commit:
                self.db.commit()
        except VisualEvidenceSnapshotError as exc:
            self.db.rollback()
            raise OutputAcceptanceDataError(
                "Visual evidence changed before the review could be recorded."
            ) from exc
        except Exception:
            self.db.rollback()
            raise
        if commit:
            self.db.refresh(acceptance)
        return acceptance

    def latest_for_video_job(self, video_job_id: int) -> models.VideoOutputAcceptance | None:
        return self.db.scalar(
            select(models.VideoOutputAcceptance)
            .where(models.VideoOutputAcceptance.video_job_id == video_job_id)
            .order_by(models.VideoOutputAcceptance.id.desc())
        )

    @staticmethod
    def as_output(acceptance: models.VideoOutputAcceptance) -> OutputAcceptanceOutput:
        return OutputAcceptanceOutput(
            id=acceptance.id,
            video_job_id=acceptance.video_job_id,
            ai_production_brief_id=acceptance.ai_production_brief_id,
            director_prompt_pack_id=acceptance.director_prompt_pack_id,
            status=acceptance.status,
            product_identity_status=acceptance.product_identity_status,
            packaging_status=acceptance.packaging_status,
            geometry_status=acceptance.geometry_status,
            blogger_authenticity_status=acceptance.blogger_authenticity_status,
            scene_match_status=acceptance.scene_match_status,
            proof_moment_status=acceptance.proof_moment_status,
            cta_status=acceptance.cta_status,
            publishing_readiness=acceptance.publishing_readiness,
            score=acceptance.score,
            blockers=acceptance.blockers_json or [],
            required_fixes=acceptance.required_fixes_json or [],
            contact_sheet_path=acceptance.contact_sheet_path,
            keyframes=acceptance.keyframes_json or [],
            visual_evidence_snapshot_id=acceptance.visual_evidence_snapshot_id,
            reviewer_notes=acceptance.reviewer_notes,
        )

    def _director_prompt(self, brief_id: int, director_prompt_pack_id: int | None) -> models.DirectorPromptPack | None:
        if director_prompt_pack_id:
            prompt = self.db.get(models.DirectorPromptPack, director_prompt_pack_id)
            if not prompt:
                raise OutputAcceptanceDataError(f"DirectorPromptPack {director_prompt_pack_id} not found.")
            if prompt.ai_production_brief_id != brief_id:
                raise OutputAcceptanceDataError(
                    "DirectorPromptPack belongs to another AIProductionBrief."
                )
            return prompt
        return self.db.scalar(
            select(models.DirectorPromptPack)
            .where(models.DirectorPromptPack.ai_production_brief_id == brief_id)
            .order_by(models.DirectorPromptPack.id.desc())
        )

    def _validate_lineage(
        self,
        video_job: models.VideoJob,
        brief: models.AIProductionBrief,
    ) -> None:
        cycle = self.db.scalar(
            select(models.ContentCycle).where(
                models.ContentCycle.video_job_id == video_job.id
            )
        )
        if cycle is not None:
            if cycle.ai_production_brief_id != brief.id or cycle.product_id != brief.product_id:
                raise OutputAcceptanceDataError(
                    "VideoJob and AIProductionBrief do not belong to the same content cycle."
                )
            if video_job.organization_id != cycle.organization_id:
                raise OutputAcceptanceDataError(
                    "VideoJob organization does not match its content cycle."
                )
            return

        video_product_id = video_job.product_id
        if video_product_id is None and video_job.script_variant is not None:
            script_job = video_job.script_variant.script_job
            video_product_id = script_job.product_id if script_job is not None else None
        if video_product_id is not None and video_product_id != brief.product_id:
            raise OutputAcceptanceDataError(
                "VideoJob and AIProductionBrief belong to different products."
            )
        if video_job.organization_id is not None:
            product = self.db.get(models.Product, brief.product_id)
            if product is None or product.organization_id != video_job.organization_id:
                raise OutputAcceptanceDataError(
                    "AIProductionBrief product is outside the VideoJob organization."
                )

    @staticmethod
    def _keyframes(frame_result: models.FrameExtractionResult | None) -> list[dict]:
        if not frame_result:
            return []
        return [
            {"index": index, "path": path}
            for index, path in enumerate(frame_result.frame_paths_json or [], start=1)
        ]
