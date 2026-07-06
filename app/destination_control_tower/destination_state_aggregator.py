from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_performance import CampaignPerformanceScorer
from app.destination_crm import DestinationReadinessService


CONNECTED_AUTH = {"manual_only", "bot_ready", "oauth_ready", "token_valid", "api_ready"}
READY_CONNECTION_STATUSES = {"connected"}
PUBLISHED_STATUSES = {"published", "published_manual", "manual_uploaded", "done"}
OPEN_SETUP_STATUSES = {"needs_manual_setup", "open", "draft", "in_progress", "blocked"}


@dataclass
class AggregatedDestinationState:
    destination_id: int | None
    platform: str
    name: str | None
    handle: str | None
    setup_status: str
    readiness_status: str
    connection_status: str
    publishing_status: str
    metrics_status: str
    performance_status: str
    warmup_phase: str | None
    daily_capacity_remaining: int
    weekly_capacity_remaining: int
    last_post_url: str | None
    last_sync_at: object | None
    blockers: list[dict]


class DestinationStateAggregator:
    def __init__(self, db: Session):
        self.db = db

    def aggregate(self, campaign_id: int) -> list[AggregatedDestinationState]:
        campaign = self._campaign(campaign_id)
        destinations = self.db.scalars(
            select(models.PublishingDestination)
            .where(models.PublishingDestination.brand == campaign.brand)
            .order_by(models.PublishingDestination.platform, models.PublishingDestination.id)
        ).all()
        rows = [self._destination_state(campaign, destination) for destination in destinations]
        rows.extend(self._setup_task_states(campaign, destinations))
        missing_count = max(0, campaign.target_destination_count - len(rows))
        for index in range(missing_count):
            rows.append(
                AggregatedDestinationState(
                    destination_id=None,
                    platform="TBD",
                    name=f"Destination slot {index + 1}",
                    handle=None,
                    setup_status="setup_needed",
                    readiness_status="unknown",
                    connection_status="no_connection",
                    publishing_status="no_posts",
                    metrics_status="no_metrics",
                    performance_status="unknown",
                    warmup_phase=None,
                    daily_capacity_remaining=0,
                    weekly_capacity_remaining=0,
                    last_post_url=None,
                    last_sync_at=None,
                    blockers=[{"blocker": "setup_needed", "source": "destination_control_tower"}],
                )
            )
        return rows

    def _destination_state(self, campaign: models.Campaign, destination: models.PublishingDestination) -> AggregatedDestinationState:
        readiness = DestinationReadinessService(self.db).latest_or_refresh(destination.id, campaign_id=campaign.id)
        connection = self._latest_connection(destination.id)
        last_task = self._latest_task(destination.id)
        last_sync = self._latest_sync(destination.id, campaign.id)
        metrics = self._metrics(destination.id, campaign.id)
        has_final_url = bool(last_task and last_task.final_url)
        blockers = list(readiness.blockers or [])
        if destination.status in {"paused", "disabled"}:
            blockers.append({"blocker": f"destination_{destination.status}", "source": "destination_control_tower"})
        if not connection:
            blockers.append({"blocker": "no_connection", "source": "destination_control_tower"})
        if has_final_url and not metrics:
            blockers.append({"blocker": "no_metrics", "source": "destination_control_tower"})
        performance_status = self._performance_status(campaign.id, destination.id, metrics)
        if performance_status == "weak":
            blockers.append({"blocker": "low_performance", "source": "destination_control_tower"})
        return AggregatedDestinationState(
            destination_id=destination.id,
            platform=destination.platform,
            name=destination.name,
            handle=destination.handle,
            setup_status="complete" if destination.status in {"active", "ready"} else destination.status,
            readiness_status="paused" if destination.status in {"paused", "disabled"} else readiness.status,
            connection_status=self._connection_status(connection),
            publishing_status=self._publishing_status(last_task),
            metrics_status=self._metrics_status(metrics, has_final_url, last_sync),
            performance_status=performance_status,
            warmup_phase=readiness.warmup_phase,
            daily_capacity_remaining=readiness.remaining_daily_capacity,
            weekly_capacity_remaining=readiness.remaining_weekly_capacity,
            last_post_url=last_task.final_url if last_task else None,
            last_sync_at=(connection.last_sync_at if connection else None) or (last_sync.created_at if last_sync else None),
            blockers=blockers,
        )

    def _setup_task_states(
        self,
        campaign: models.Campaign,
        destinations: list[models.PublishingDestination],
    ) -> list[AggregatedDestinationState]:
        destination_handles = {destination.handle for destination in destinations if destination.handle}
        tasks = self.db.scalars(
            select(models.DestinationSetupTask)
            .where(models.DestinationSetupTask.campaign_id == campaign.id)
            .order_by(models.DestinationSetupTask.id)
        ).all()
        rows = []
        for task in tasks:
            if task.final_handle and task.final_handle in destination_handles:
                continue
            if task.status not in OPEN_SETUP_STATUSES:
                continue
            rows.append(
                AggregatedDestinationState(
                    destination_id=None,
                    platform=task.platform,
                    name=task.profile_pack.suggested_name if task.profile_pack else "Pending destination",
                    handle=task.final_handle,
                    setup_status=task.status,
                    readiness_status="unknown",
                    connection_status="no_connection",
                    publishing_status="no_posts",
                    metrics_status="no_metrics",
                    performance_status="unknown",
                    warmup_phase=None,
                    daily_capacity_remaining=0,
                    weekly_capacity_remaining=0,
                    last_post_url=None,
                    last_sync_at=None,
                    blockers=[{"blocker": "setup_task_open", "task_id": task.id, "source": "destination_control_tower"}],
                )
            )
        return rows

    def _latest_connection(self, destination_id: int) -> models.DestinationConnection | None:
        return self.db.scalar(
            select(models.DestinationConnection)
            .where(models.DestinationConnection.destination_id == destination_id)
            .order_by(models.DestinationConnection.id.desc())
        )

    def _latest_task(self, destination_id: int) -> models.PublishingTask | None:
        return self.db.scalar(
            select(models.PublishingTask)
            .where(models.PublishingTask.destination_id == destination_id)
            .order_by(models.PublishingTask.scheduled_at.desc(), models.PublishingTask.id.desc())
        )

    def _latest_sync(self, destination_id: int, campaign_id: int) -> models.DestinationMetricSync | None:
        return self.db.scalar(
            select(models.DestinationMetricSync)
            .where(
                models.DestinationMetricSync.destination_id == destination_id,
                models.DestinationMetricSync.campaign_id == campaign_id,
            )
            .order_by(models.DestinationMetricSync.id.desc())
        )

    def _metrics(self, destination_id: int, campaign_id: int) -> list[models.DestinationPostMetric]:
        return self.db.scalars(
            select(models.DestinationPostMetric).where(
                models.DestinationPostMetric.destination_id == destination_id,
                models.DestinationPostMetric.campaign_id == campaign_id,
            )
        ).all()

    def _performance_status(
        self,
        campaign_id: int,
        destination_id: int,
        metrics: list[models.DestinationPostMetric],
    ) -> str:
        score = self.db.scalar(
            select(models.CampaignPerformanceScore).where(
                models.CampaignPerformanceScore.campaign_id == campaign_id,
                models.CampaignPerformanceScore.entity_type == "destination",
                models.CampaignPerformanceScore.entity_id == str(destination_id),
            )
        )
        if not score and metrics:
            CampaignPerformanceScorer(self.db).latest_scores(campaign_id)
            score = self.db.scalar(
                select(models.CampaignPerformanceScore).where(
                    models.CampaignPerformanceScore.campaign_id == campaign_id,
                    models.CampaignPerformanceScore.entity_type == "destination",
                    models.CampaignPerformanceScore.entity_id == str(destination_id),
                )
            )
        if score:
            return score.status
        if metrics:
            total_views = sum(metric.views or 0 for metric in metrics)
            total_clicks = sum(metric.clicks or 0 for metric in metrics)
            if total_views >= 1000 and total_clicks <= 5:
                return "weak"
            return "neutral"
        return "unknown"

    @staticmethod
    def _connection_status(connection: models.DestinationConnection | None) -> str:
        if not connection:
            return "no_connection"
        if connection.status in READY_CONNECTION_STATUSES and connection.auth_status in CONNECTED_AUTH:
            return "connected"
        return connection.status

    @staticmethod
    def _publishing_status(task: models.PublishingTask | None) -> str:
        if not task:
            return "no_posts"
        if task.status in PUBLISHED_STATUSES or task.final_url:
            return "published"
        return task.status

    @staticmethod
    def _metrics_status(
        metrics: list[models.DestinationPostMetric],
        has_final_url: bool,
        last_sync: models.DestinationMetricSync | None,
    ) -> str:
        if metrics:
            return "synced"
        if has_final_url:
            return "no_metrics"
        if last_sync:
            return "sync_needed"
        return "no_metrics"

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            from app.destination_control_tower.errors import DestinationControlTowerDataError

            raise DestinationControlTowerDataError(f"Campaign {campaign_id} not found.")
        return campaign
