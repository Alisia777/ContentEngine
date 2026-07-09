from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

PUBLIC_PILOT_ROLES = ["owner", "admin", "producer", "reviewer", "operator", "trainee", "viewer"]

PROMPT_ONLY = "prompt_only"
ONE_VIDEO_REAL_RUN = "one_video_real_run"
VARIANT_REAL_SMOKE = "variant_real_smoke"
WORKING_VIDEO_REAL_SMOKE = "working_video_real_smoke"
OUTPUT_REVIEW = "output_review"
VIDEO_APPROVE = "video_approve"
VIDEO_REJECT = "video_reject"
PUBLISHING_APPROVE = "publishing_approve"
METRICS_IMPORT = "metrics_import"
TRAINING_ATTEMPT = "training_attempt"
SETTINGS_VIEW = "settings_view"

PUBLIC_PILOT_ACTIONS = [
    PROMPT_ONLY,
    ONE_VIDEO_REAL_RUN,
    VARIANT_REAL_SMOKE,
    WORKING_VIDEO_REAL_SMOKE,
    OUTPUT_REVIEW,
    VIDEO_APPROVE,
    VIDEO_REJECT,
    PUBLISHING_APPROVE,
    METRICS_IMPORT,
    TRAINING_ATTEMPT,
    SETTINGS_VIEW,
]

DANGEROUS_ACTIONS = {
    ONE_VIDEO_REAL_RUN,
    VARIANT_REAL_SMOKE,
    WORKING_VIDEO_REAL_SMOKE,
    OUTPUT_REVIEW,
    VIDEO_APPROVE,
    VIDEO_REJECT,
    PUBLISHING_APPROVE,
    METRICS_IMPORT,
}

SPEND_GATED_ACTIONS = {ONE_VIDEO_REAL_RUN, VARIANT_REAL_SMOKE, WORKING_VIDEO_REAL_SMOKE}

ROLE_ACTIONS: dict[str, set[str]] = {
    "owner": set(PUBLIC_PILOT_ACTIONS),
    "admin": set(PUBLIC_PILOT_ACTIONS),
    "producer": {PROMPT_ONLY, TRAINING_ATTEMPT},
    "reviewer": {OUTPUT_REVIEW, VIDEO_APPROVE, VIDEO_REJECT, TRAINING_ATTEMPT},
    "operator": {PUBLISHING_APPROVE, METRICS_IMPORT, TRAINING_ATTEMPT},
    "trainee": {TRAINING_ATTEMPT},
    "viewer": {TRAINING_ATTEMPT},
}

ACTION_CERTIFICATIONS = {
    OUTPUT_REVIEW: "review_qa",
    VIDEO_APPROVE: "review_qa",
    VIDEO_REJECT: "review_qa",
    PUBLISHING_APPROVE: "publishing_manual_upload",
    METRICS_IMPORT: "publishing_manual_upload",
}

ACTION_LABELS = {
    PROMPT_ONLY: "Prompt-only generation",
    ONE_VIDEO_REAL_RUN: "One-video real run",
    VARIANT_REAL_SMOKE: "Variant real smoke",
    WORKING_VIDEO_REAL_SMOKE: "Working-video real smoke",
    OUTPUT_REVIEW: "Output review",
    VIDEO_APPROVE: "Approve video",
    VIDEO_REJECT: "Reject video",
    PUBLISHING_APPROVE: "Approve publishing",
    METRICS_IMPORT: "Import metrics",
    TRAINING_ATTEMPT: "Training attempt",
    SETTINGS_VIEW: "Settings access",
}


@dataclass(frozen=True)
class GateDecision:
    action: str
    role: str
    allowed: bool
    reason: str
    required_role: str | None
    required_certification: str | None
    spend_gate_required: bool
    audit_required: bool
    missing_certification: str | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class PublicPilotGateMatrix:
    def __init__(self, *, strict_training: bool = True):
        self.strict_training = strict_training

    def evaluate(
        self,
        role: str | None,
        action: str,
        *,
        certification_codes: set[str] | None = None,
        spend_gate_confirmed: bool = False,
    ) -> GateDecision:
        normalized_role = role if role in PUBLIC_PILOT_ROLES else "viewer"
        certifications = certification_codes or set()
        required_certification = self._required_certification(normalized_role, action)
        spend_gate_required = action in SPEND_GATED_ACTIONS
        audit_required = action in DANGEROUS_ACTIONS

        if action not in PUBLIC_PILOT_ACTIONS:
            return self._decision(action, normalized_role, False, "unknown_action", None, None, spend_gate_required, audit_required)

        if action not in ROLE_ACTIONS.get(normalized_role, set()):
            return self._decision(
                action,
                normalized_role,
                False,
                f"role_{normalized_role}_cannot_{action}",
                self._roles_for_action(action),
                required_certification,
                spend_gate_required,
                audit_required,
            )

        if required_certification and required_certification not in certifications:
            return self._decision(
                action,
                normalized_role,
                False,
                "training_certification_required",
                self._roles_for_action(action),
                required_certification,
                spend_gate_required,
                audit_required,
                missing_certification=required_certification,
            )

        if spend_gate_required and not spend_gate_confirmed:
            return self._decision(
                action,
                normalized_role,
                False,
                "spend_gate_required",
                self._roles_for_action(action),
                required_certification,
                spend_gate_required,
                audit_required,
            )

        return self._decision(
            action,
            normalized_role,
            True,
            "allowed",
            self._roles_for_action(action),
            required_certification,
            spend_gate_required,
            audit_required,
        )

    def matrix(self, *, certification_codes_by_role: dict[str, set[str]] | None = None, spend_gate_confirmed: bool = False) -> dict[str, dict[str, dict[str, Any]]]:
        certs = certification_codes_by_role or {}
        return {
            action: {
                role: self.evaluate(
                    role,
                    action,
                    certification_codes=certs.get(role, set()),
                    spend_gate_confirmed=spend_gate_confirmed,
                ).model_dump()
                for role in PUBLIC_PILOT_ROLES
            }
            for action in PUBLIC_PILOT_ACTIONS
        }

    def summary(self) -> list[dict[str, Any]]:
        return [
            {
                "action": action,
                "label": ACTION_LABELS[action],
                "roles": self._roles_for_action(action),
                "required_certification": ACTION_CERTIFICATIONS.get(action),
                "spend_gate_required": action in SPEND_GATED_ACTIONS,
                "audit_required": action in DANGEROUS_ACTIONS,
            }
            for action in PUBLIC_PILOT_ACTIONS
        ]

    def _required_certification(self, role: str, action: str) -> str | None:
        if not self.strict_training:
            return None
        if role in {"owner", "admin"}:
            return None
        return ACTION_CERTIFICATIONS.get(action)

    def _roles_for_action(self, action: str) -> str | None:
        roles = [role for role, actions in ROLE_ACTIONS.items() if action in actions]
        return ", ".join(roles) if roles else None

    def _decision(
        self,
        action: str,
        role: str,
        allowed: bool,
        reason: str,
        required_role: str | None,
        required_certification: str | None,
        spend_gate_required: bool,
        audit_required: bool,
        *,
        missing_certification: str | None = None,
    ) -> GateDecision:
        return GateDecision(
            action=action,
            role=role,
            allowed=allowed,
            reason=reason,
            required_role=required_role,
            required_certification=required_certification,
            spend_gate_required=spend_gate_required,
            audit_required=audit_required,
            missing_certification=missing_certification,
        )
