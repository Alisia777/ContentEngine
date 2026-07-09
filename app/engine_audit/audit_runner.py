from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.engine_audit.scorecard_service import EngineAuditScorecardService


class EngineAuditRunner:
    def __init__(self, db: Session):
        self.db = db

    def run(self, *, scope_type: str = "global", scope_id: int | None = None) -> models.EngineAuditRun:
        return EngineAuditScorecardService(self.db).run(scope_type=scope_type, scope_id=scope_id)
