from __future__ import annotations

from sqlalchemy.orm import Session

from app.destination_control_tower.tower_service import TowerService
from app.destination_control_tower.types import DestinationControlReport


class DestinationControlReportService:
    def __init__(self, db: Session):
        self.db = db

    def build(self, campaign_id: int) -> DestinationControlReport:
        service = TowerService(self.db)
        snapshot = service.latest_or_refresh(campaign_id)
        rows = service.rows(campaign_id)
        lines = [
            f"# Destination Control Tower Campaign {campaign_id}",
            "",
            f"- Total destinations: {snapshot.total_destinations}",
            f"- Setup needed: {snapshot.setup_needed_count}",
            f"- Ready: {snapshot.ready_count}",
            f"- Connected: {snapshot.connected_count}",
            f"- Metrics synced: {snapshot.metrics_synced_count}",
            f"- No metrics: {snapshot.no_metrics_count}",
            f"- Low performance: {snapshot.low_performance_count}",
            f"- Capacity gap: {snapshot.capacity_gap}",
            "",
            "| Platform | Destination | Readiness | Connection | Publishing | Metrics | Performance | Next action |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row.platform,
                        row.handle or row.name or "-",
                        row.readiness_status,
                        row.connection_status,
                        row.publishing_status,
                        row.metrics_status,
                        row.performance_status,
                        row.next_action or "-",
                    ]
                )
                + " |"
            )
        return DestinationControlReport(snapshot=snapshot, rows=rows, markdown="\n".join(lines))
