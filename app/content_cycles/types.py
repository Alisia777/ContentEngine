from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentCycleTrace:
    id: int
    organization_id: int
    created_by_user_profile_id: int
    product_id: int
    product_ugc_recipe_draft_id: int
    video_job_id: int
    ai_production_brief_id: int
    output_acceptance_id: int | None
    publishing_package_id: int | None
    publishing_task_id: int | None
    tracking_link_id: int | None
    destination_id: int | None
    idempotency_key: str
    status: str
    trace_version: int

    @property
    def manual_distribution_ready(self) -> bool:
        return bool(
            self.output_acceptance_id
            and self.publishing_package_id
            and self.publishing_task_id
            and self.tracking_link_id
            and self.status == "manual_distribution_ready"
        )
