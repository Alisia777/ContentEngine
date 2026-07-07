from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.creative_quality.script_rewriter import ScriptRewriter
from app.creative_quality.ugc_quality_scorer import UGCQualityScorer
from app.creative_workbench.errors import CreativeWorkbenchDataError
from app.creative_workbench.types import RewriteWorkflowOutput
from app.creative_workbench.workbench_service import WorkbenchService


class RewriteWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.scorer = UGCQualityScorer(db)

    def rewrite(self, session_id: int, *, feedback: str | None = None) -> RewriteWorkflowOutput:
        service = WorkbenchService(self.db)
        session = service.get(session_id)
        if not session.creative_quality_score_id:
            if not session.ugc_script_id:
                raise CreativeWorkbenchDataError("Workbench session is missing UGCAdScript.")
            score = self.scorer.score_script(session.ugc_script_id, prompt_pack_id=session.prompt_pack_id)
            session.creative_quality_score_id = score.id
            self.db.commit()
        previous_score = session.creative_quality_score
        request = ScriptRewriter(self.db).create_request(session.creative_quality_score_id, feedback=feedback)
        result = ScriptRewriter(self.db).build(request.id)
        new_score = self.scorer.score_script(result.new_ugc_script_id, prompt_pack_id=session.prompt_pack_id)
        new_script = self.db.get(models.UGCAdScript, result.new_ugc_script_id)
        if not new_script:
            raise CreativeWorkbenchDataError(f"UGCAdScript {result.new_ugc_script_id} not found after rewrite.")
        session.ugc_script_id = result.new_ugc_script_id
        session.creative_quality_score_id = new_score.id
        session.blogger_meaning_spec_id = new_script.blogger_meaning_spec_id
        self.db.commit()
        service.refresh(session.id)
        return RewriteWorkflowOutput(
            session_id=session.id,
            rewrite_request_id=result.rewrite_request_id,
            source_ugc_script_id=result.source_ugc_script_id,
            new_ugc_script_id=result.new_ugc_script_id,
            before_lines=result.before_lines,
            after_lines=result.after_lines,
            previous_score=self.scorer.as_output(previous_score).model_dump(mode="json") if previous_score else None,
            new_score=self.scorer.as_output(new_score).model_dump(mode="json"),
            status=result.status,
        )
