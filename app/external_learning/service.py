"""Public facade for deterministic external performance learning."""

from __future__ import annotations

from ._common import LearningPolicyError, safe_log_business_value
from .creative import (
    aggregate_feature_prior,
    mark_harly_attribution_state,
    select_successful_creatives,
)
from .duration import choose_duration_plan
from .experiments import build_category_experiment_plan
from .funnel import map_funnel_decision

__all__ = [
    "LearningPolicyError",
    "aggregate_feature_prior",
    "build_category_experiment_plan",
    "choose_duration_plan",
    "map_funnel_decision",
    "mark_harly_attribution_state",
    "safe_log_business_value",
    "select_successful_creatives",
]
