from enum import StrEnum


class WorkflowStatus(StrEnum):
    draft = "draft"
    product_data_ready = "product_data_ready"
    script_generated = "script_generated"
    script_approved = "script_approved"
    video_generation_queued = "video_generation_queued"
    video_generated = "video_generated"
    video_approved = "video_approved"
    publishing_package_ready = "publishing_package_ready"
    scheduled = "scheduled"
    warmup_blocked = "warmup_blocked"
    upload_queued = "upload_queued"
    uploading = "uploading"
    uploaded = "uploaded"
    published = "published"
    published_manual = "published_manual"
    manual_upload_required = "manual_upload_required"
    failed = "failed"
    needs_reauth = "needs_reauth"
    archived = "archived"


class AccountStatus(StrEnum):
    new = "new"
    warming = "warming"
    active = "active"
    paused = "paused"
    limited = "limited"
    needs_reauth = "needs_reauth"
    disabled = "disabled"


class WarmupPhase(StrEnum):
    phase_0_setup = "phase_0_setup"
    phase_1_soft_start = "phase_1_soft_start"
    phase_2_regular_posting = "phase_2_regular_posting"
    phase_3_scaled_posting = "phase_3_scaled_posting"
    phase_4_active_distribution = "phase_4_active_distribution"


class ReviewStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

