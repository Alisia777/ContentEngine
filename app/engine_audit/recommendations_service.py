from __future__ import annotations

from sqlalchemy.orm import Session

from app.engine_audit.scorecard_service import EngineAuditScorecardService


class EngineAuditRecommendationsService:
    def __init__(self, db: Session):
        self.db = db

    def latest(self) -> list[dict]:
        service = EngineAuditScorecardService(self.db)
        run = service.latest()
        if not run:
            run = service.run()
        return service.output(run).recommendations
