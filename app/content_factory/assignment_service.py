from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.content_factory.agent_registry import ContentAgentRegistry


class ContentAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.registry = ContentAgentRegistry(db)

    def record(
        self,
        *,
        content_run: models.ContentRun,
        assignment_type: str,
        status: str,
        input_json: dict | None = None,
        output_json: dict | None = None,
        blockers: list[str] | None = None,
        next_actions: list[dict] | None = None,
    ) -> models.ContentAssignment:
        profile = self.registry.by_type(assignment_type)
        assignment = models.ContentAssignment(
            content_run_id=content_run.id,
            agent_profile_id=profile.id if profile else None,
            product_id=content_run.product_id,
            assignment_type=assignment_type,
            status=status,
            input_json=input_json or {},
            output_json=output_json or {},
            blockers_json=blockers or [],
            next_actions_json=next_actions or [],
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
