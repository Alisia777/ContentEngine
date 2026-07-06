from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.participant_portal.assignment_portal_service import AssignmentPortalService
from app.participant_portal.errors import ParticipantPortalDataError


class SubmissionService:
    def __init__(self, db: Session):
        self.db = db

    def submit(
        self,
        *,
        assignment_id: int,
        file_path: str | None = None,
        external_url: str | None = None,
        final_post_url: str | None = None,
        video_job_id: int | None = None,
    ) -> models.ParticipantSubmission:
        assignment = AssignmentPortalService(self.db).get(assignment_id)
        if not file_path and not external_url and not video_job_id:
            raise ParticipantPortalDataError("Submission needs file_path, external_url, or video_job_id.")
        submission = models.ParticipantSubmission(
            participant_assignment_id=assignment.id,
            participant_id=assignment.participant_id,
            video_job_id=video_job_id,
            file_path=file_path or None,
            external_url=external_url or None,
            final_post_url=final_post_url or None,
            status="submitted",
            review_status="needs_review",
        )
        assignment.status = "submitted"
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def get(self, submission_id: int) -> models.ParticipantSubmission:
        submission = self.db.get(models.ParticipantSubmission, submission_id)
        if not submission:
            raise ParticipantPortalDataError(f"ParticipantSubmission {submission_id} not found.")
        return submission

    def review(self, submission_id: int, *, review_status: str, review_notes: str | None = None) -> models.ParticipantSubmission:
        submission = self.get(submission_id)
        submission.review_status = review_status
        submission.review_notes = review_notes or None
        submission.status = "approved" if review_status == "approved" else "rejected" if review_status == "rejected" else "needs_review"
        submission.assignment.status = submission.status
        self.db.commit()
        self.db.refresh(submission)
        return submission
