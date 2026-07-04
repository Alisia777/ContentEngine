from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


JsonDict = dict[str, Any]
JsonList = list[Any]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    sku: str
    brand: str
    marketplace: str | None = None
    title: str
    description: str | None = None
    category: str | None = None
    attributes_json: JsonDict = Field(default_factory=dict)
    benefits_json: JsonList = Field(default_factory=list)
    images_json: JsonList = Field(default_factory=list)
    reviews_json: JsonList = Field(default_factory=list)
    restrictions_json: JsonList = Field(default_factory=list)
    product_url: str | None = None


class ProductRead(ProductCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class BrandGuideCreate(BaseModel):
    brand: str
    tone_of_voice: str | None = None
    visual_style: str | None = None
    forbidden_words_json: JsonList = Field(default_factory=list)
    forbidden_claims_json: JsonList = Field(default_factory=list)
    required_disclaimers_json: JsonList = Field(default_factory=list)
    allowed_cta_json: JsonList = Field(default_factory=list)


class BrandGuideRead(BrandGuideCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class CreativeTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    format: str = "short_video"
    duration_seconds: int = 15
    aspect_ratio: str = "9:16"
    structure_json: JsonList = Field(default_factory=list)
    hook_formula: str | None = None
    cta: str | None = None
    platform_fit_json: JsonList = Field(default_factory=list)


class CreativeTemplateRead(CreativeTemplateCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ScriptGenerateRequest(BaseModel):
    product_id: int
    template_id: int
    brand_guide_id: int


class ScriptJobRead(OrmModel):
    id: int
    product_id: int
    template_id: int
    brand_guide_id: int
    status: str
    input_payload_json: JsonDict
    output_script_json: JsonDict
    validation_report_json: JsonDict
    created_at: datetime
    updated_at: datetime


class ScriptVariantRead(OrmModel):
    id: int
    script_job_id: int
    variant_number: int
    creative_angle: str | None
    hook: str | None
    key_message: str | None
    final_cta: str | None
    full_script_json: JsonDict
    status: str
    created_at: datetime
    updated_at: datetime


class SceneRead(OrmModel):
    id: int
    script_variant_id: int
    scene_number: int
    time_start: float
    time_end: float
    visual_description: str | None
    voiceover: str | None
    caption: str | None
    video_prompt: str | None
    negative_prompt: str | None
    source_fields_json: JsonList
    created_at: datetime


class ReviewCreate(BaseModel):
    entity_type: str
    entity_id: int
    reviewer_name: str = "admin"
    status: str
    comment: str | None = None
    rejection_reason: str | None = None


class ReviewRead(ReviewCreate, OrmModel):
    id: int
    created_at: datetime


class VideoJobCreate(BaseModel):
    script_variant_id: int
    provider: str = "mock"


class VideoJobRead(OrmModel):
    id: int
    script_variant_id: int
    provider: str
    status: str
    aspect_ratio: str
    duration_seconds: int
    output_video_path: str | None
    preview_path: str | None
    error_message: str | None
    cost_estimate: float
    created_at: datetime
    updated_at: datetime


class VideoClipRead(OrmModel):
    id: int
    video_job_id: int
    scene_id: int
    provider_job_id: str | None
    status: str
    clip_path: str | None
    raw_response_json: JsonDict
    created_at: datetime
    updated_at: datetime


class PublishingAccountCreate(BaseModel):
    brand: str
    platform: str
    account_name: str
    account_handle: str | None = None
    account_url: str | None = None
    owner_name: str | None = None
    auth_status: str = "manual_upload_required"
    warmup_status: str = "new"
    warmup_phase: str = "phase_0_setup"
    daily_publish_limit: int = 1
    weekly_publish_limit: int = 3
    allowed_formats_json: JsonList = Field(default_factory=list)
    notes: str | None = None


class PublishingAccountPatch(BaseModel):
    brand: str | None = None
    platform: str | None = None
    account_name: str | None = None
    account_handle: str | None = None
    account_url: str | None = None
    owner_name: str | None = None
    auth_status: str | None = None
    warmup_status: str | None = None
    warmup_phase: str | None = None
    daily_publish_limit: int | None = None
    weekly_publish_limit: int | None = None
    allowed_formats_json: JsonList | None = None
    notes: str | None = None


class PublishingAccountRead(PublishingAccountCreate, OrmModel):
    id: int
    created_at: datetime
    updated_at: datetime


class WarmupRuleCreate(BaseModel):
    phase: str
    day_from: int = 1
    day_to: int = 7
    max_posts_per_day: int = 1
    max_posts_per_week: int = 3
    allowed_content_types_json: JsonList = Field(default_factory=list)
    requires_manual_approval: bool = True
    notes: str | None = None


class WarmupRuleRead(WarmupRuleCreate, OrmModel):
    id: int
    warmup_plan_id: int


class WarmupPlanCreate(BaseModel):
    account_id: int | None = None
    name: str
    status: str = "active"
    current_phase: str = "phase_1_soft_start"
    rules_json: JsonList = Field(default_factory=list)
    rules: list[WarmupRuleCreate] = Field(default_factory=list)


class WarmupPlanRead(OrmModel):
    id: int
    account_id: int | None
    name: str
    status: str
    start_date: datetime
    current_phase: str
    rules_json: JsonList
    created_at: datetime
    updated_at: datetime


class PublishingPackageCreate(BaseModel):
    video_job_id: int
    target_platform: str


class PublishingPackageRead(OrmModel):
    id: int
    video_job_id: int
    product_id: int
    brand: str
    target_platform: str
    title: str
    description: str | None
    hashtags_json: JsonList
    cta: str | None
    product_url: str | None
    utm_url: str | None
    cover_image_path: str | None
    video_file_path: str | None
    metadata_json: JsonDict
    ai_generated_flag: bool
    status: str
    created_at: datetime
    updated_at: datetime


class PublishingScheduleRequest(BaseModel):
    publishing_package_id: int
    account_id: int
    scheduled_at: datetime
    provider: str = "mock"
    manual_override: bool = False
    operator_name: str | None = None


class ManualUploadRequest(BaseModel):
    provider_post_url: str
    operator_name: str = "operator"


class PublishingJobRead(OrmModel):
    id: int
    publishing_package_id: int
    account_id: int
    scheduled_at: datetime
    status: str
    provider: str
    provider_post_id: str | None
    provider_post_url: str | None
    manual_upload_required: bool
    operator_name: str | None
    error_message: str | None
    raw_response_json: JsonDict
    created_at: datetime
    updated_at: datetime


class PublishAnalyticsRead(OrmModel):
    id: int
    publishing_job_id: int
    collected_at: datetime
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    clicks: int
    ctr: float
    raw_metrics_json: JsonDict


class ExportCreate(BaseModel):
    video_job_id: int
    destination: str = "local"

