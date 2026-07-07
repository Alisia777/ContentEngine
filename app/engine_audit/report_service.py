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

    def write(self, report_id: int, *, output_dir: str | Path = "reports") -> str:
        report = self.db.get(models.EngineAuditReport, report_id)
        if not report:
            raise EngineAuditError(f"EngineAuditReport {report_id} not found.")
        output = EngineAuditScorecardService(self.db).output(report)
        payload = output.model_dump(mode="json")
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"engine_audit_{report.id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report.report_path = path.as_posix()
        self.db.commit()
        return report.report_path
