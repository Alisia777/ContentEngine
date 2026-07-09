from __future__ import annotations

from app.control_room.action_router import ControlRoomActionRouter
from app.control_room.types import ControlRoomActionOutput


class ControlRoomNextActionService:
    def __init__(self):
        self.router = ControlRoomActionRouter()

    def from_scorecard(self, *, role: str, recommendations: list[dict]) -> list[ControlRoomActionOutput]:
        actions: list[ControlRoomActionOutput] = []
        for item in recommendations[:8]:
            module = self._module_for_dimension(item.get("dimension", "engine_audit"))
            action_type = item.get("next_action") or f"review_{item.get('dimension', 'engine')}"
            requires_spend = action_type in {"confirm_runway_credits_then_one_paid_smoke", "one_paid_smoke_then_output_acceptance"}
            actions.append(
                ControlRoomActionOutput(
                    action_type=action_type,
                    role=role,
                    target_module=module,
                    target_url=self.router.route(module),
                    status="open",
                    safe_to_execute=not requires_spend,
                    requires_human=True,
                    requires_spend_gate=requires_spend,
                    reason=", ".join(item.get("why_not_10") or []),
                    payload=item,
                )
            )
        return actions

    @staticmethod
    def _module_for_dimension(dimension: str) -> str:
        return {
            "interface": "engine_audit",
            "video_quality": "output_acceptance",
            "brief_quality": "ai_brief_studio",
            "asset_readiness": "one_video_acceptance",
            "creator_clarity": "participant_portal",
            "training": "training",
            "metrics": "metrics_intake",
            "destinations": "destination_control",
            "production": "one_video_acceptance",
        }.get(dimension, "engine_audit")
