from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.destination_setup.errors import DestinationSetupDataError
from app.destination_setup.types import DestinationSetupReadinessResult


class DestinationSetupReadinessService:
    def __init__(self, db: Session):
        self.db = db

    def task_readiness(self, task_id: int) -> DestinationSetupReadinessResult:
        task = self.db.get(models.DestinationSetupTask, task_id)
        if not task:
            raise DestinationSetupDataError(f"Destination setup task {task_id} not found.")
        blockers = []
        warnings = []
        if task.status not in {"completed_pending_destination", "destination_created"}:
            blockers.append("Setup task must be completed by an operator before destination activation.")
        if not task.final_account_url and not task.final_handle:
            blockers.append("Final account URL or handle is required.")
        if task.platform in {"Instagram Reels", "TikTok", "YouTube Shorts"}:
            warnings.append("Official API/OAuth should be connected before API-mode publishing.")
        return DestinationSetupReadinessResult(
            task_id=task.id,
            ready=not blockers,
            status="ready" if not blockers else "blocked",
            blockers=blockers,
            warnings=warnings,
        )
