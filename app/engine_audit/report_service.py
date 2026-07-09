from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app import models
from app.engine_audit.errors import EngineAuditError
from app.engine_audit.scorecard_service import EngineAuditScorecardService


class EngineAuditReportService:
    def __init__(self, db: Session):
        self.db = db

    def write(self, run_id: int, *, output_dir: str | Path = "reports") -> str:
        run = self.db.get(models.EngineAuditRun, run_id)
        if not run:
            raise EngineAuditError(f"EngineAuditRun {run_id} not found.")
        output = EngineAuditScorecardService(self.db).output(run)
        payload = output.model_dump(mode="json")
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"engine_audit_{run.id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path.as_posix()
