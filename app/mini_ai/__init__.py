"""Controllable mini-AI for ContentEngine mass-generation experiments."""

from .controller import MiniAiController
from .evaluator import evaluate_mass_generation
from .planner import build_mass_generation_plan
from .rulebook import DEFAULT_RULES, RULES_RU, rulebook_ru, rules_for_preset
from .schema import (
    ArmOutcome,
    ArmSummary,
    ExperimentArm,
    ExperimentDimension,
    LearningObjective,
    MassGenerationPlan,
    MiniAiConclusion,
    MiniAiContext,
    MiniAiDecision,
    MiniAiRules,
    OutcomeState,
    PlanMode,
    QaState,
    RiskPreset,
)

__all__ = [
    "ArmOutcome",
    "ArmSummary",
    "DEFAULT_RULES",
    "ExperimentArm",
    "ExperimentDimension",
    "LearningObjective",
    "MassGenerationPlan",
    "MiniAiConclusion",
    "MiniAiContext",
    "MiniAiController",
    "MiniAiDecision",
    "MiniAiRules",
    "OutcomeState",
    "PlanMode",
    "QaState",
    "RULES_RU",
    "RiskPreset",
    "build_mass_generation_plan",
    "evaluate_mass_generation",
    "rulebook_ru",
    "rules_for_preset",
]
