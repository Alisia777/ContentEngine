from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.output_acceptance.errors import OutputAcceptanceDataError
from app.video_generator.regeneration_requests import RegenerationRequestService


class RegenerationFeedbackBuilder:
    def __init__(self, db: Session):
        self.db = db

    def request(
        self,
        acceptance_id: int,
        *,
        reason: str | None = None,
        scene_number: int = 1,
    ) -> models.SceneRegenerationRequest:
        acceptance = self.db.get(models.VideoOutputAcceptance, acceptance_id)
        if not acceptance:
            raise OutputAcceptanceDataError(f"VideoOutputAcceptance {acceptance_id} not found.")
        selected_reason = reason or self._reason_from_blockers(acceptance.blockers_json or [])
        feedback = self._feedback(acceptance)
        request = RegenerationRequestService(self.db).create(
            video_job_id=acceptance.video_job_id,
            scene_number=scene_number,
            reason=selected_reason,
            feedback=feedback,
        )
        acceptance.status = "needs_regeneration"
        if selected_reason not in (acceptance.required_fixes_json or []):
            acceptance.required_fixes_json = list(dict.fromkeys([*(acceptance.required_fixes_json or []), selected_reason]))
        self.db.commit()
        return request

    @staticmethod
    def _reason_from_blockers(blockers: list[str]) -> str:
        if any(item in blockers for item in {"packaging_drift", "human_review_required_for_product_identity"}):
            return "product_identity_mismatch"
        if "geometry_drift" in blockers:
            return "product_geometry_mismatch"
        if "missing_proof_moment" in blockers or "cta_missing_or_unclear" in blockers:
            return "claim_mismatch"
        return "scene_quality_issue"

    @staticmethod
    def _feedback(acceptance: models.VideoOutputAcceptance) -> str:
        blockers = ", ".join(acceptance.blockers_json or []) or "output quality issue"
        fixes = ", ".join(acceptance.required_fixes_json or []) or "regenerate with stricter scene guidance"
        notes = f" Reviewer notes: {acceptance.reviewer_notes}" if acceptance.reviewer_notes else ""
        return f"Output acceptance #{acceptance.id} failed. Blockers: {blockers}. Required fixes: {fixes}.{notes}"
