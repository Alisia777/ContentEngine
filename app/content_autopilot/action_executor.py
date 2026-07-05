from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.content_autopilot.decision_log import DecisionLog
from app.content_autopilot.errors import ContentAutopilotDataError
from app.content_autopilot.types import AutopilotExecutionResult, PAID_ACTIONS, PUBLISHING_ACTIONS
from app.content_factory import ContentRunOrchestrator
from app.publishing import PublishingPackageService
from app.video_generator.regeneration_requests import RegenerationRequestService


class ActionExecutor:
    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        decision_id: int,
        *,
        allow_paid: bool = False,
        allow_publishing: bool = False,
    ) -> AutopilotExecutionResult:
        decision = self.db.get(models.AutopilotDecision, decision_id)
        if not decision:
            raise ContentAutopilotDataError(f"AutopilotDecision {decision_id} not found.")
        action = decision.recommended_action
        if action in PAID_ACTIONS and not allow_paid:
            return self._finish(decision, "blocked", {"reason": "paid action was not explicitly allowed"}, ["paid_action_requires_explicit_gate"])
        if action in PUBLISHING_ACTIONS and not allow_publishing:
            return self._finish(
                decision,
                "blocked",
                {"reason": "publishing action was not explicitly allowed"},
                ["publishing_action_requires_explicit_gate"],
            )

        if action == "prepare_content_run":
            return self._prepare_content_run(decision)
        if action in {"run_prompt_only", "build_prompt_pack"}:
            return self._run_prompt_only(decision)
        if action == "run_real_smoke":
            return self._run_real_smoke(decision)
        if action == "create_publishing_package":
            return self._create_publishing_package(decision)
        if action in {"request_regeneration", "request_geometry_regeneration"}:
            return self._create_regeneration_request(decision)
        if action == "import_performance_stats":
            return self._import_stats_placeholder(decision)
        if action == "create_queue_item":
            return self._finish(decision, "queued", {"queued": True}, [], executed=False)
        return self._finish(decision, "blocked", {"reason": f"Action {action} is not executable by autopilot."}, ["action_not_executable"])

    def _prepare_content_run(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        result = ContentRunOrchestrator(self.db).prepare_content_run(decision.product_id, "Instagram Reels", 15, 5)
        return self._finish(
            decision,
            "executed",
            {"content_run_id": result.id, "status": result.status, "prompt_pack_id": result.prompt_pack_id},
            [],
        )

    def _run_prompt_only(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        content_run_id = decision.content_run_id
        if not content_run_id:
            return self._finish(decision, "blocked", {}, ["content_run_missing"])
        result = ContentRunOrchestrator(self.db).run_prompt_only(content_run_id)
        return self._finish(
            decision,
            "executed",
            {"content_run_id": result.id, "status": result.status, "prompt_pack_id": result.prompt_pack_id},
            [],
        )

    def _run_real_smoke(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        if not decision.content_run_id:
            return self._finish(decision, "blocked", {}, ["content_run_missing"])
        result = ContentRunOrchestrator(self.db).run_real_smoke(decision.content_run_id, provider="runway", allow_real_spend=True)
        return self._finish(
            decision,
            "executed",
            {"content_run_id": result.id, "status": result.status, "video_job_id": result.video_job_id},
            [],
        )

    def _create_publishing_package(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        content_run = self._content_run(decision)
        if not content_run.video_job_id:
            return self._finish(decision, "blocked", {}, ["video_job_missing"])
        package = PublishingPackageService(self.db).create_from_video(
            video_job_id=content_run.video_job_id,
            platform=content_run.platform,
        )
        return self._finish(
            decision,
            "executed",
            {"publishing_package_id": package.id, "status": package.status, "review_status": package.review_status},
            [],
        )

    def _create_regeneration_request(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        content_run = self._content_run(decision)
        if not content_run.video_job_id:
            return self._finish(decision, "blocked", {}, ["video_job_missing"])
        reason = "product_geometry_mismatch" if decision.recommended_action == "request_geometry_regeneration" else "product_identity_mismatch"
        existing = self.db.scalar(
            select(models.SceneRegenerationRequest)
            .where(
                models.SceneRegenerationRequest.video_job_id == content_run.video_job_id,
                models.SceneRegenerationRequest.reason == reason,
            )
            .order_by(models.SceneRegenerationRequest.id.desc())
        )
        if existing:
            return self._finish(decision, "executed", {"regeneration_request_id": existing.id, "status": existing.status}, [])
        request = RegenerationRequestService(self.db).create(
            video_job_id=content_run.video_job_id,
            scene_number=1,
            reason=reason,
            feedback=f"Autopilot request: {reason}. Keep generation safe and source-backed.",
        )
        return self._finish(decision, "executed", {"regeneration_request_id": request.id, "status": request.status}, [])

    def _import_stats_placeholder(self, decision: models.AutopilotDecision) -> AutopilotExecutionResult:
        return self._finish(
            decision,
            "executed",
            {"placeholder": True, "message": "Stats import requires operator CSV or analytics connector."},
            [],
        )

    def _content_run(self, decision: models.AutopilotDecision) -> models.ContentRun:
        if not decision.content_run_id:
            raise ContentAutopilotDataError("Decision does not reference a ContentRun.")
        content_run = self.db.get(models.ContentRun, decision.content_run_id)
        if not content_run:
            raise ContentAutopilotDataError(f"ContentRun {decision.content_run_id} not found.")
        return content_run

    def _finish(
        self,
        decision: models.AutopilotDecision,
        status: str,
        outputs: dict,
        blockers: list[str],
        *,
        executed: bool | None = None,
    ) -> AutopilotExecutionResult:
        result = AutopilotExecutionResult(
            decision_id=decision.id,
            status=status,
            action=decision.recommended_action,
            outputs=outputs,
            blockers=blockers,
            executed=status == "executed" if executed is None else executed,
        )
        DecisionLog(self.db).mark_execution(decision, result)
        return result
