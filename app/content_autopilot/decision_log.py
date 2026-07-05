from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app import models
from app.content_autopilot.types import AutopilotDecisionResult, AutopilotExecutionResult


class DecisionLog:
    def __init__(self, db: Session):
        self.db = db

    def record(self, decision: AutopilotDecisionResult) -> models.AutopilotDecision:
        record = models.AutopilotDecision(
            product_id=decision.product_id,
            sku=decision.sku,
            content_run_id=decision.content_run_id,
            decision_type=decision.decision_type,
            recommended_action=decision.recommended_action,
            confidence_score=decision.confidence_score,
            status=decision.status,
            blockers_json=decision.blockers,
            reasons_json=decision.reasons,
            inputs_json=decision.inputs,
            outputs_json=decision.outputs,
            human_review_required=decision.human_review_required,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_execution(self, decision: models.AutopilotDecision, result: AutopilotExecutionResult) -> models.AutopilotDecision:
        decision.status = result.status
        decision.outputs_json = result.outputs
        decision.blockers_json = list(dict.fromkeys([*(decision.blockers_json or []), *result.blockers]))
        if result.executed:
            decision.executed_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(decision)
        return decision
