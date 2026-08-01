"""Public fail-closed wrapper around the internal mass planner."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from app.external_learning import CreativeObservation

from .planner import build_mass_generation_plan as _build_mass_generation_plan
from .schema import MassGenerationPlan, MiniAiContext, MiniAiRules


def build_mass_generation_plan(
    context: MiniAiContext,
    observations: Iterable[CreativeObservation] = (),
    *,
    rules: MiniAiRules | None = None,
) -> MassGenerationPlan:
    """Build a plan while refusing winner inheritance for a new category."""

    safe_context = context
    if context.category_is_new:
        safe_context = replace(
            context,
            approved_winner_angle=None,
            approved_winner_duration=None,
        )
    return _build_mass_generation_plan(safe_context, observations, rules=rules)
