from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_control_tower.destination_state_aggregator import DestinationStateAggregator
from app.destination_control_tower.errors import DestinationControlTowerDataError
from app.destination_control_tower.next_action_service import DestinationControlNextActionService
from app.destination_control_tower.types import DestinationControlRowResult, DestinationControlSnapshotResult
from app.launch_operations import DestinationCapacityService


class TowerService:
    def __init__(self, db: Session):
        self.db = db
        self.next_actions = DestinationControlNextActionService()

    def refresh(self, campaign_id: int) -> DestinationControlSnapshotResult:
        campaign = self._campaign(campaign_id)
        capacity = DestinationCapacityService(self.db).refresh(campaign.id)
        states = DestinationStateAggregator(self.db).aggregate(campaign.id)
        snapshot = models.DestinationControlSnapshot(
            campaign_id=campaign.id,
            total_destinations=sum(1 for state in states if state.destination_id is not None),
            setup_needed_count=sum(1 for state in states if state.setup_status in {"setup_needed", "needs_manual_setup"}),
            ready_count=sum(1 for state in states if state.readiness_status == "ready"),
            connected_count=sum(1 for state in states if state.connection_status == "connected"),
            metrics_synced_count=sum(1 for state in states if state.metrics_status == "synced"),
            no_metrics_count=sum(1 for state in states if state.metrics_status == "no_metrics"),
            low_performance_count=sum(1 for state in states if state.performance_status == "weak"),
            paused_count=sum(1 for state in states if state.readiness_status == "paused"),
            capacity_total=capacity.weekly_capacity,
            capacity_used=max(0, capacity.required_slots - capacity.capacity_gap),
            capacity_gap=capacity.capacity_gap,
            blockers_json=list(capacity.blockers or []),
            next_actions_json=[],
        )
        self.db.add(snapshot)
        self.db.flush()
        row_actions: list[dict] = []
        for state in states:
            row = models.DestinationControlRow(
                snapshot_id=snapshot.id,
                destination_id=state.destination_id,
                platform=state.platform,
                name=state.name,
                handle=state.handle,
                setup_status=state.setup_status,
                readiness_status=state.readiness_status,
                connection_status=state.connection_status,
                publishing_status=state.publishing_status,
                metrics_status=state.metrics_status,
                performance_status=state.performance_status,
                warmup_phase=state.warmup_phase,
                daily_capacity_remaining=state.daily_capacity_remaining,
                weekly_capacity_remaining=state.weekly_capacity_remaining,
                last_post_url=state.last_post_url,
                last_sync_at=state.last_sync_at,
                blockers_json=state.blockers,
            )
            row.next_action = self.next_actions.choose(row)
            if row.next_action != "monitor":
                row_actions.append(
                    {
                        "destination_id": row.destination_id,
                        "platform": row.platform,
                        "action": row.next_action,
                        "safe": True,
                        "manual": row.next_action
                        in {
                            "complete_destination_setup",
                            "add_connection",
                            "import_metrics",
                            "activate_destination",
                            "increase_capacity",
                            "investigate_low_performance",
                        },
                    }
                )
            self.db.add(row)
        if capacity.capacity_gap:
            row_actions.append({"action": "increase_capacity", "reason": "campaign_capacity_gap", "safe": True, "manual": True})
        snapshot.next_actions_json = row_actions
        self.db.commit()
        self.db.refresh(snapshot)
        return self._snapshot_result(snapshot)

    def latest_or_refresh(self, campaign_id: int) -> DestinationControlSnapshotResult:
        snapshot = self.db.scalar(
            select(models.DestinationControlSnapshot)
            .where(models.DestinationControlSnapshot.campaign_id == campaign_id)
            .order_by(models.DestinationControlSnapshot.id.desc())
        )
        if not snapshot:
            return self.refresh(campaign_id)
        return self._snapshot_result(snapshot)

    def rows(self, campaign_id: int) -> list[DestinationControlRowResult]:
        snapshot = self._latest_snapshot(campaign_id)
        rows = self.db.scalars(
            select(models.DestinationControlRow)
            .where(models.DestinationControlRow.snapshot_id == snapshot.id)
            .order_by(models.DestinationControlRow.platform, models.DestinationControlRow.id)
        ).all()
        return [self._row_result(row) for row in rows]

    def apply_action(self, row_id: int) -> dict:
        row = self.db.get(models.DestinationControlRow, row_id)
        if not row:
            raise DestinationControlTowerDataError(f"DestinationControlRow {row_id} not found.")
        return {
            "row_id": row.id,
            "destination_id": row.destination_id,
            "action": row.next_action,
            "status": "queued_manual_review" if row.next_action != "monitor" else "no_action_required",
            "safe": True,
        }

    def _latest_snapshot(self, campaign_id: int) -> models.DestinationControlSnapshot:
        snapshot = self.db.scalar(
            select(models.DestinationControlSnapshot)
            .where(models.DestinationControlSnapshot.campaign_id == campaign_id)
            .order_by(models.DestinationControlSnapshot.id.desc())
        )
        if not snapshot:
            self.refresh(campaign_id)
            snapshot = self.db.scalar(
                select(models.DestinationControlSnapshot)
                .where(models.DestinationControlSnapshot.campaign_id == campaign_id)
                .order_by(models.DestinationControlSnapshot.id.desc())
            )
        return snapshot

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise DestinationControlTowerDataError(f"Campaign {campaign_id} not found.")
        return campaign

    @staticmethod
    def _snapshot_result(snapshot: models.DestinationControlSnapshot) -> DestinationControlSnapshotResult:
        return DestinationControlSnapshotResult(
            snapshot_id=snapshot.id,
            campaign_id=snapshot.campaign_id,
            total_destinations=snapshot.total_destinations,
            setup_needed_count=snapshot.setup_needed_count,
            ready_count=snapshot.ready_count,
            connected_count=snapshot.connected_count,
            metrics_synced_count=snapshot.metrics_synced_count,
            no_metrics_count=snapshot.no_metrics_count,
            low_performance_count=snapshot.low_performance_count,
            paused_count=snapshot.paused_count,
            capacity_total=snapshot.capacity_total,
            capacity_used=snapshot.capacity_used,
            capacity_gap=snapshot.capacity_gap,
            blockers=snapshot.blockers_json or [],
            next_actions=snapshot.next_actions_json or [],
            generated_at=snapshot.created_at,
        )

    @staticmethod
    def _row_result(row: models.DestinationControlRow) -> DestinationControlRowResult:
        return DestinationControlRowResult(
            row_id=row.id,
            snapshot_id=row.snapshot_id,
            destination_id=row.destination_id,
            platform=row.platform,
            name=row.name,
            handle=row.handle,
            setup_status=row.setup_status,
            readiness_status=row.readiness_status,
            connection_status=row.connection_status,
            publishing_status=row.publishing_status,
            metrics_status=row.metrics_status,
            performance_status=row.performance_status,
            warmup_phase=row.warmup_phase,
            daily_capacity_remaining=row.daily_capacity_remaining,
            weekly_capacity_remaining=row.weekly_capacity_remaining,
            last_post_url=row.last_post_url,
            last_sync_at=row.last_sync_at,
            blockers=row.blockers_json or [],
            next_action=row.next_action,
        )
