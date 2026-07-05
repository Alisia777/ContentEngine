from __future__ import annotations

from app import models


SAFE_BATCH_ACTIONS = {
    "prepare_content_run",
    "run_prompt_only",
    "build_prompt_pack",
    "create_publishing_package_draft",
    "create_regeneration_request",
    "create_distribution_task_draft",
    "export_operator_tasks_csv",
}

UNSAFE_BATCH_ACTIONS = {
    "run_real_smoke",
    "approve_publishing_package",
    "schedule_live_publishing",
    "publish",
    "manual_upload",
    "mark_published",
    "external_api_upload",
    "schedule_distribution",
    "create_publishing_package",
    "human_review",
    "add_reference",
}


class BatchSafetyGate:
    def assess(self, action: models.CampaignActionQueueItem) -> tuple[bool, str | None]:
        if action.status != "open":
            return False, f"action_status_{action.status}"
        if action.action_type in UNSAFE_BATCH_ACTIONS:
            return False, f"unsafe_action:{action.action_type}"
        if action.action_type not in SAFE_BATCH_ACTIONS:
            return False, f"unsupported_batch_action:{action.action_type}"
        if not action.safe_to_execute:
            return False, "action_not_marked_safe"
        if action.requires_human:
            return False, "human_required"
        if any("paid" in blocker or "spend_gate" in blocker for blocker in action.blockers_json or []):
            return False, "paid_or_spend_gate_blocker"
        return True, None
