"""High-level orchestration facade for the controllable mini-AI."""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Iterable

from app.external_learning import CreativeObservation

from .evaluator import evaluate_mass_generation
from .rulebook import rulebook_ru, rules_for_preset
from .safe_planner import build_mass_generation_plan
from .schema import (
    ArmOutcome,
    ExperimentDimension,
    MassGenerationPlan,
    MiniAiConclusion,
    MiniAiContext,
    MiniAiDecision,
)


class MiniAiController:
    """Plan one bounded question, evaluate it and prepare the next cycle."""

    def rules(self, context: MiniAiContext) -> str:
        return rulebook_ru(rules_for_preset(context.risk_preset))

    def plan(
        self,
        context: MiniAiContext,
        observations: Iterable[CreativeObservation] = (),
    ) -> MassGenerationPlan:
        return build_mass_generation_plan(context, observations)

    def conclude(
        self,
        plan: MassGenerationPlan,
        outcomes: Iterable[ArmOutcome],
    ) -> MiniAiConclusion:
        return evaluate_mass_generation(plan, outcomes)

    def next_context(
        self,
        plan: MassGenerationPlan,
        conclusion: MiniAiConclusion,
    ) -> MiniAiContext:
        """Create the next bounded context without silently scaling spend."""

        if conclusion.decision not in {
            MiniAiDecision.PROMOTE_WITH_CONTROL,
            MiniAiDecision.KEEP_CONTROL,
            MiniAiDecision.COLLECT_MORE,
        }:
            raise ValueError("conclusion_not_ready_for_next_cycle")
        winner = next(
            (
                arm
                for arm in plan.arms
                if arm.arm_id == conclusion.winner_arm_id
            ),
            None,
        )
        requested_dimension = conclusion.next_dimension
        if requested_dimension is ExperimentDimension.AUTO:
            requested_dimension = plan.dimension
        promoted = (
            winner is not None
            and conclusion.decision is MiniAiDecision.PROMOTE_WITH_CONTROL
        )
        return replace(
            plan.context,
            requested_dimension=requested_dimension,
            approved_winner_angle=(
                winner.creative_angle
                if promoted
                else plan.context.approved_winner_angle
            ),
            approved_winner_duration=(
                winner.duration_seconds
                if promoted
                else plan.context.approved_winner_duration
            ),
            # Once this exact category has produced a human-confirmable winner,
            # the next cycle is no longer a foreign-category cold start.
            category_is_new=False if promoted else plan.context.category_is_new,
            # A new cycle still requires a fresh explicit batch and budget choice.
            requested_batch_size=plan.context.requested_batch_size,
        )

    @staticmethod
    def audit_snapshot(
        plan: MassGenerationPlan,
        conclusion: MiniAiConclusion | None = None,
    ) -> dict[str, object]:
        """Return a JSON-safe, reproducible audit snapshot."""

        payload: dict[str, object] = {
            "schema_version": "mini-ai-control-plane.v1",
            "plan": asdict(plan),
        }
        if conclusion is not None:
            payload["conclusion"] = asdict(conclusion)
        return payload
