from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.destination_crm.errors import DestinationCRMDataError
from app.destination_crm.types import DestinationWarmupPlanResult


WARMUP_RULES = [
    {"phase": "phase_0_setup", "max_posts_per_day": 0, "max_posts_per_week": 0, "next_phase": "phase_1_soft_start"},
    {"phase": "phase_1_soft_start", "max_posts_per_day": 1, "max_posts_per_week": 7, "next_phase": "phase_2_regular"},
    {"phase": "phase_2_regular", "max_posts_per_day": 2, "max_posts_per_week": 14, "next_phase": "phase_3_scaled"},
    {"phase": "phase_3_scaled", "max_posts_per_day": 3, "max_posts_per_week": 21, "next_phase": None},
]
DEFAULT_PHASE = "phase_2_regular"


class DestinationWarmupService:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update(
        self,
        destination_id: int,
        *,
        current_phase: str = "phase_1_soft_start",
        status: str = "active",
        notes: str | None = None,
    ) -> DestinationWarmupPlanResult:
        destination = self._destination(destination_id)
        self._validate_phase(current_phase)
        plan = self.latest(destination.id)
        if plan:
            record = self.db.get(models.DestinationWarmupPlan, plan.id)
            record.current_phase = current_phase
            record.status = status
            record.notes = notes
            record.rules_json = WARMUP_RULES
        else:
            record = models.DestinationWarmupPlan(
                destination_id=destination.id,
                status=status,
                current_phase=current_phase,
                rules_json=WARMUP_RULES,
                notes=notes,
            )
            self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._result(record)

    def latest(self, destination_id: int) -> DestinationWarmupPlanResult | None:
        record = self.db.scalar(
            select(models.DestinationWarmupPlan)
            .where(models.DestinationWarmupPlan.destination_id == destination_id)
            .order_by(models.DestinationWarmupPlan.id.desc())
        )
        return self._result(record) if record else None

    def phase_limits(self, destination_id: int) -> tuple[str, int, int]:
        plan = self.latest(destination_id)
        phase = plan.current_phase if plan and plan.status == "active" else DEFAULT_PHASE
        rule = self.rule_for_phase(phase)
        return phase, int(rule["max_posts_per_day"]), int(rule["max_posts_per_week"])

    @staticmethod
    def rule_for_phase(phase: str) -> dict:
        for rule in WARMUP_RULES:
            if rule["phase"] == phase:
                return rule
        raise DestinationCRMDataError(f"Invalid warmup phase: {phase}.")

    def _destination(self, destination_id: int) -> models.PublishingDestination:
        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise DestinationCRMDataError(f"Destination {destination_id} not found.")
        return destination

    @staticmethod
    def _validate_phase(phase: str) -> None:
        if phase not in {rule["phase"] for rule in WARMUP_RULES}:
            raise DestinationCRMDataError(f"Invalid warmup phase: {phase}.")

    @staticmethod
    def _result(record: models.DestinationWarmupPlan) -> DestinationWarmupPlanResult:
        return DestinationWarmupPlanResult(
            id=record.id,
            destination_id=record.destination_id,
            status=record.status,
            start_date=record.start_date,
            current_phase=record.current_phase,
            rules=record.rules_json or [],
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
