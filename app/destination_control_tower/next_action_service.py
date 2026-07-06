from __future__ import annotations

from app import models


class DestinationControlNextActionService:
    def choose(self, row: models.DestinationControlRow) -> str:
        blockers = {blocker.get("blocker") for blocker in (row.blockers_json or [])}
        if row.setup_status in {"setup_needed", "needs_manual_setup"} or row.destination_id is None:
            return "complete_destination_setup"
        if row.readiness_status in {"blocked", "unknown"}:
            return "refresh_readiness"
        if row.connection_status == "no_connection":
            return "add_connection"
        if row.metrics_status == "no_metrics":
            return "import_metrics"
        if row.metrics_status == "sync_needed":
            return "sync_metrics"
        if row.performance_status == "weak":
            return "investigate_low_performance"
        if row.readiness_status == "paused":
            return "activate_destination"
        if "capacity_gap" in blockers:
            return "increase_capacity"
        if row.publishing_status == "no_posts":
            return "create_publishing_task"
        return "monitor"
