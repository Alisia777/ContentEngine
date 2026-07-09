from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.intelligence.safety import provider_key_status
from app.smoke_readiness.blocker_service import SmokeReadinessBlockerService
from app.smoke_readiness.errors import SmokeReadinessError
from app.smoke_readiness.types import SmokeReadinessBlockerOutput, SmokeReadinessReport, SmokeReadinessRunOutput


class ReadinessReportService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, run_id: int) -> models.SmokeReadinessRun:
        run = self.db.get(models.SmokeReadinessRun, run_id)
        if not run:
            raise SmokeReadinessError(f"SmokeReadinessRun {run_id} not found.")
        return run

    def latest(self) -> models.SmokeReadinessRun | None:
        return self.db.scalar(select(models.SmokeReadinessRun).order_by(models.SmokeReadinessRun.id.desc()))

    def output(self, run: models.SmokeReadinessRun) -> SmokeReadinessRunOutput:
        blockers = self._blocker_outputs(run)
        report = self.report(run, blockers=blockers)
        return SmokeReadinessRunOutput(
            id=run.id,
            status=run.status,
            product_id=run.product_id,
            sku=run.sku,
            one_video_render_plan_id=run.one_video_render_plan_id,
            prompt_pack_id=run.prompt_pack_id,
            engine_audit_run_id=run.engine_audit_run_id,
            control_room_snapshot_id=run.control_room_snapshot_id,
            blockers=blockers,
            next_actions=run.next_actions_json or [],
            report=report,
        )

    def report(
        self,
        run: models.SmokeReadinessRun,
        *,
        blockers: list[SmokeReadinessBlockerOutput] | None = None,
    ) -> SmokeReadinessReport:
        facts = run.report_json or {}
        status = provider_key_status()
        settings = get_settings()
        blockers = blockers if blockers is not None else self._blocker_outputs(run)
        plan = self.db.get(models.OneVideoRenderPlan, run.one_video_render_plan_id) if run.one_video_render_plan_id else None
        audit_run = self.db.get(models.EngineAuditRun, run.engine_audit_run_id) if run.engine_audit_run_id else None
        snapshot = self.db.get(models.ControlRoomSnapshot, run.control_room_snapshot_id) if run.control_room_snapshot_id else None
        final_decision = facts.get("final_decision") or self._final_decision(blockers)
        return SmokeReadinessReport(
            run_id=run.id,
            status=run.status,
            final_decision=final_decision,
            auth_mode={
                "auth_required": settings.auth_required,
                "public_pilot_mode": settings.public_pilot_mode,
            },
            spend_gate_status={
                "allow_real_spend": bool(status["allow_real_spend"]),
                "public_pilot_real_spend_default_enabled": settings.public_pilot_real_spend_default_enabled,
            },
            generation_mode=str(status["generation_mode"]),
            runway_key_configured=bool(status["runway_api_secret_configured"]),
            runway_key_value="[redacted]",
            runway_credits_confirmed=bool(facts.get("runway_credits_confirmed", False)),
            requested_plan_id=facts.get("requested_plan_id"),
            requested_plan_exists=bool(facts.get("requested_plan_exists", False)),
            rebuilt_plan_id=facts.get("rebuilt_plan_id"),
            product_id=run.product_id,
            sku=run.sku,
            one_video_render_plan_id=run.one_video_render_plan_id,
            prompt_pack_id=run.prompt_pack_id,
            reference_policy_status=facts.get("reference_policy_status") or self._reference_policy(plan),
            scene_policy_status=facts.get("scene_policy_status") or self._scene_policy(plan),
            prompt_only_status=facts.get("prompt_only_status", "not_run"),
            mvp_scorecard=facts.get("mvp_scorecard") or ((plan.prompt_preview_json or {}).get("mvp_scorecard") if plan else {}),
            engine_audit_latest_score=audit_run.total_score if audit_run else None,
            engine_audit_run_id=run.engine_audit_run_id,
            control_room_snapshot_id=run.control_room_snapshot_id,
            control_room_next_action=self._control_next_action(snapshot),
            blockers=blockers,
            next_actions=run.next_actions_json or [],
        )

    def _blocker_outputs(self, run: models.SmokeReadinessRun) -> list[SmokeReadinessBlockerOutput]:
        if run.blockers:
            return [SmokeReadinessBlockerService.from_model(blocker) for blocker in run.blockers]
        return [SmokeReadinessBlockerOutput.model_validate(item) for item in (run.blockers_json or [])]

    @staticmethod
    def _reference_policy(plan: models.OneVideoRenderPlan | None) -> dict:
        if not plan:
            return {"status": "unknown"}
        policy = plan.product_scene_policy_json or {}
        ref_policy = policy.get("reference_policy") or {}
        readiness = policy.get("reference_readiness") or {}
        return {
            "status": ref_policy.get("status") or readiness.get("status") or "unknown",
            "mass_generation_safety_status": ref_policy.get("mass_generation_safety_status"),
            "approved_reference_count": ref_policy.get("approved_reference_count"),
            "blockers": list(dict.fromkeys([*(ref_policy.get("blockers") or []), *(readiness.get("blockers") or [])])),
            "warnings": list(dict.fromkeys([*(ref_policy.get("warnings") or []), *(readiness.get("warnings") or [])])),
        }

    @staticmethod
    def _scene_policy(plan: models.OneVideoRenderPlan | None) -> dict:
        if not plan:
            return {"status": "unknown"}
        policy = plan.product_scene_policy_json or {}
        return {
            "wrapper_reference_count": policy.get("wrapper_reference_count", 0),
            "edible_reference_count": policy.get("edible_reference_count", 0),
            "wrapper_scene_allowed": policy.get("wrapper_scene_allowed", False),
            "bite_scene_allowed": policy.get("bite_scene_allowed", False),
            "texture_macro_allowed": policy.get("texture_macro_allowed", False),
            "packshot_overlay_required": policy.get("packshot_overlay_required", True),
            "end_card_required": policy.get("end_card_required", True),
            "blocked_scene_types": policy.get("blocked_scene_types") or [],
            "allowed_scene_types": policy.get("allowed_scene_types") or [],
        }

    @staticmethod
    def _control_next_action(snapshot: models.ControlRoomSnapshot | None) -> str | None:
        if not snapshot:
            return None
        actions = snapshot.next_actions_json or []
        if not actions:
            return None
        first = actions[0]
        return first.get("action_type") or first.get("target_module")

    @staticmethod
    def _final_decision(blockers: list[SmokeReadinessBlockerOutput]) -> str:
        types = {blocker.blocker_type for blocker in blockers}
        if "missing_plan" in types:
            return "blocked_by_missing_plan"
        if types.intersection({"missing_product", "product_seed_required"}):
            return "blocked_by_missing_plan"
        if types.intersection({"spend_gate_off", "generation_mode_not_real", "runway_key_missing"}):
            return "blocked_by_spend_gate"
        if types.intersection({"missing_refs", "missing_references", "reference_policy_blocked"}):
            return "blocked_by_missing_references"
        if "runway_credits_unconfirmed" in types:
            return "blocked_by_runway_credits_unconfirmed"
        if "prompt_only_failed" in types:
            return "blocked_by_missing_plan"
        return "ready_for_paid_smoke"
