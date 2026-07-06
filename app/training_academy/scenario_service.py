from __future__ import annotations

from typing import Any

from app.training_academy.academy_catalog import SCENARIO_SIMULATORS
from app.training_academy.errors import TrainingAcademyDataError
from app.training_academy.quiz_service import _normalize_answer


class ScenarioService:
    def list_scenarios(self) -> list[dict[str, Any]]:
        return SCENARIO_SIMULATORS

    def get(self, scenario_code: str) -> dict[str, Any]:
        for scenario in SCENARIO_SIMULATORS:
            if scenario["code"] == scenario_code:
                return scenario
        raise TrainingAcademyDataError(f"Training scenario {scenario_code} not found.")

    def evaluate(self, scenario_code: str, answers: dict[str, Any]) -> dict[str, Any]:
        scenario = self.get(scenario_code)
        missing: list[str] = []
        failures: list[dict[str, str]] = []
        normalized_answers = {key: _normalize_answer(value) for key, value in answers.items()}
        required = scenario.get("required_answers", {})
        any_of_keys = {key for group in scenario.get("any_of", []) for key in group}
        for key, expected_values in required.items():
            actual = normalized_answers.get(key)
            if not actual:
                if key in any_of_keys:
                    continue
                missing.append(key)
                failures.append({"field": key, "reason": scenario.get("failure_reasons", {}).get(key, "Required answer is missing.")})
                continue
            expected = {_normalize_answer(value) for value in expected_values}
            if actual not in expected:
                failures.append({"field": key, "reason": scenario.get("failure_reasons", {}).get(key, "Answer does not satisfy scenario rule.")})
        for any_group in scenario.get("any_of", []):
            if not any(normalized_answers.get(key) in {_normalize_answer(value) for value in required.get(key, [])} for key in any_group):
                failures.append({"field": "/".join(any_group), "reason": "At least one traceability field from this group is required."})
        passed = not failures
        return {
            "scenario_code": scenario_code,
            "status": "passed" if passed else "failed",
            "passed": passed,
            "missing": missing,
            "failures": failures,
        }
