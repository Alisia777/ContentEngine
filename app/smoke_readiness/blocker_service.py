from __future__ import annotations

from app import models
from app.smoke_readiness.types import SmokeReadinessBlockerOutput


class SmokeReadinessBlockerService:
    @staticmethod
    def dedupe(blockers: list[SmokeReadinessBlockerOutput]) -> list[SmokeReadinessBlockerOutput]:
        seen: set[tuple[str, str]] = set()
        output: list[SmokeReadinessBlockerOutput] = []
        for blocker in blockers:
            key = (blocker.blocker_type, blocker.message)
            if key in seen:
                continue
            seen.add(key)
            output.append(blocker)
        return output

    @staticmethod
    def from_model(blocker: models.SmokeReadinessBlocker) -> SmokeReadinessBlockerOutput:
        return SmokeReadinessBlockerOutput(
            blocker_type=blocker.blocker_type,
            severity=blocker.severity,
            message=blocker.message,
            recommended_action=blocker.recommended_action,
        )

    @staticmethod
    def to_json(blockers: list[SmokeReadinessBlockerOutput]) -> list[dict]:
        return [blocker.model_dump(mode="json") for blocker in SmokeReadinessBlockerService.dedupe(blockers)]
