from __future__ import annotations

from app.content_autopilot.types import (
    PAID_ACTIONS,
    PUBLISHING_ACTIONS,
    SAFE_ACTIONS,
    AutopilotDecisionResult,
    ContentStateSnapshot,
)


class DecisionEngine:
    def decide(self, snapshot: ContentStateSnapshot) -> AutopilotDecisionResult:
        if not snapshot.has_demand or not snapshot.content_run_id:
            return self._decision(
                snapshot,
                "prepare_content_run",
                0.95,
                ["No complete ContentRun/demand chain exists for this SKU."],
                priority=10,
            )
        if snapshot.reference_readiness.get("status") != "ready":
            return self._decision(
                snapshot,
                "add_product_reference",
                0.92,
                ["Approved primary product reference is missing or blocked."],
                blockers=self._reference_blockers(snapshot),
                human=True,
                queue_type="human_review",
                priority=15,
            )
        if snapshot.geometry_readiness.get("status") == "blocked":
            return self._decision(
                snapshot,
                "add_geometry_lock",
                0.9,
                ["Product geometry/scale lock is missing from the prompt chain."],
                blockers=snapshot.geometry_readiness.get("blockers") or ["geometry_lock_missing"],
                human=True,
                queue_type="exception",
                priority=20,
            )
        if snapshot.has_selected_variant and not snapshot.has_prompt_pack:
            return self._decision(
                snapshot,
                "build_prompt_pack",
                0.88,
                ["Selected variant exists but prompt pack is missing."],
                priority=25,
            )
        if snapshot.identity_mismatch_detected:
            return self._decision(
                snapshot,
                "request_regeneration",
                0.9,
                ["Human review or quality metadata indicates product identity mismatch."],
                blockers=["product_identity_mismatch"],
                human=True,
                queue_type="human_review",
                priority=30,
            )
        if snapshot.geometry_mismatch_detected:
            return self._decision(
                snapshot,
                "request_geometry_regeneration",
                0.9,
                ["Human review or quality metadata indicates product size/proportion drift."],
                blockers=["product_geometry_mismatch"],
                human=True,
                queue_type="human_review",
                priority=30,
            )
        if snapshot.has_prompt_pack and not snapshot.has_video_output:
            blockers = [] if snapshot.real_smoke_gate_ready else ["paid_action_requires_explicit_gate"]
            return self._decision(
                snapshot,
                "run_real_smoke",
                0.84,
                ["Prompt pack, reference readiness, and geometry readiness are ready for one-scene smoke."],
                blockers=blockers,
                human=True,
                queue_type="paid_review",
                priority=35,
            )
        if snapshot.video_review_status in {"needs_human_review", "metadata_scored"}:
            return self._decision(
                snapshot,
                "human_review",
                0.86,
                ["Video output exists but visual identity and quality require human review."],
                human=True,
                queue_type="human_review",
                priority=40,
            )
        if snapshot.video_review_status in {"approved", "human_approved"} and not snapshot.has_publishing_package:
            return self._decision(
                snapshot,
                "create_publishing_package",
                0.82,
                ["Human-approved video can be prepared as a publishing package draft."],
                priority=45,
            )
        if snapshot.publishing_package_status == "approved" and not snapshot.has_publishing_task:
            return self._decision(
                snapshot,
                "schedule_publishing_task",
                0.8,
                ["Publishing package is approved but no publishing task is scheduled."],
                blockers=["publishing_action_requires_explicit_gate"],
                human=True,
                queue_type="publishing_approval",
                priority=50,
            )
        if snapshot.publishing_task_status in {"published_manual", "published_api"} and snapshot.performance_data_status == "missing":
            return self._decision(
                snapshot,
                "import_performance_stats",
                0.76,
                ["Published content has no attached performance metrics yet."],
                priority=60,
            )
        if snapshot.performance_strength == "strong":
            return self._decision(
                snapshot,
                "scale_variant",
                0.72,
                ["Performance is above baseline; variant is a scaling candidate."],
                queue_type="performance",
                priority=70,
            )
        if snapshot.performance_strength == "weak":
            return self._decision(
                snapshot,
                "pause_variant",
                0.72,
                ["Performance is below baseline; pause or regenerate before scaling."],
                queue_type="performance",
                priority=70,
            )
        return self._decision(
            snapshot,
            "create_queue_item",
            0.55,
            ["No safe automatic action is available; keep SKU in monitoring queue."],
            queue_type="monitoring",
            priority=90,
        )

    def _decision(
        self,
        snapshot: ContentStateSnapshot,
        action: str,
        confidence: float,
        reasons: list[str],
        *,
        blockers: list[str] | None = None,
        human: bool = False,
        queue_type: str = "autopilot",
        priority: int = 50,
    ) -> AutopilotDecisionResult:
        blockers = list(dict.fromkeys(blockers or []))
        can_execute = action in SAFE_ACTIONS and not human and not blockers
        if action in PAID_ACTIONS or action in PUBLISHING_ACTIONS:
            can_execute = False
        return AutopilotDecisionResult(
            product_id=snapshot.product_id,
            sku=snapshot.sku,
            content_run_id=snapshot.content_run_id,
            recommended_action=action,
            confidence_score=confidence,
            blockers=blockers,
            reasons=reasons,
            inputs={"snapshot": snapshot.model_dump(mode="json")},
            human_review_required=human,
            can_execute_safely=can_execute,
            queue_type=queue_type,
            priority=priority,
        )

    @staticmethod
    def _reference_blockers(snapshot: ContentStateSnapshot) -> list[str]:
        blockers = snapshot.reference_readiness.get("blockers") or []
        return [f"reference:{blocker}" for blocker in blockers] or ["reference:missing_approved_primary_reference"]
