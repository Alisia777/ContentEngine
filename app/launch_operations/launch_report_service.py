from __future__ import annotations

import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.launch_operations.destination_capacity_service import DestinationCapacityService
from app.launch_operations.launch_action_planner import LaunchActionPlanner
from app.launch_operations.launch_readiness_service import LaunchReadinessService
from app.launch_operations.quality_gate_service import QualityGateService
from app.launch_operations.types import LaunchOperationsReport, LaunchRunbookExport


class LaunchReportService:
    def __init__(self, db: Session, *, reports_dir: str | Path = "reports"):
        self.db = db
        self.reports_dir = Path(reports_dir)

    def build(self, campaign_id: int, *, refresh: bool = False) -> LaunchOperationsReport:
        if refresh:
            readiness = LaunchReadinessService(self.db).refresh(campaign_id)
        else:
            readiness = LaunchReadinessService(self.db).latest_or_refresh(campaign_id)
        quality_gates = QualityGateService(self.db).list_latest(campaign_id)
        capacity = DestinationCapacityService(self.db).latest_or_refresh(campaign_id)
        action_plan = LaunchActionPlanner(self.db).latest_or_refresh(campaign_id)
        return LaunchOperationsReport(
            campaign_id=campaign_id,
            readiness=readiness,
            quality_gates=quality_gates,
            destination_capacity=capacity,
            action_plan=action_plan,
        )

    def export_runbook(self, campaign_id: int, *, reports_dir: str | Path | None = None) -> LaunchRunbookExport:
        report = self.build(campaign_id, refresh=True)
        output_dir = Path(reports_dir) if reports_dir else self.reports_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"launch_runbook_{campaign_id}.json"
        csv_path = output_dir / f"launch_runbook_{campaign_id}.csv"
        json_path.write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "action_type",
                    "action",
                    "scope",
                    "sku",
                    "entity_id",
                    "count",
                    "reason",
                    "safe_to_execute",
                    "requires_human",
                    "requires_paid",
                    "is_publishing_action",
                ],
            )
            writer.writeheader()
            for action in report.action_plan.actions:
                writer.writerow({field: action.get(field, "") for field in writer.fieldnames})
        return LaunchRunbookExport(
            campaign_id=campaign_id,
            report_paths={"json": json_path.as_posix(), "csv": csv_path.as_posix()},
            action_count=report.action_plan.action_count,
        )
