from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        # Enables organization-safe composite foreign keys for newly scoped records.
        # Legacy products may remain unscoped, but security-sensitive services must
        # never attach them to an organization until ownership is explicitly set.
        UniqueConstraint("organization_id", "id", name="uq_products_organization_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    sku = Column(String(120), unique=True, nullable=False, index=True)
    brand = Column(String(120), nullable=False, index=True)
    marketplace = Column(String(120), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(120), nullable=True)
    attributes_json = Column(JSON, default=dict, nullable=False)
    benefits_json = Column(JSON, default=list, nullable=False)
    images_json = Column(JSON, default=list, nullable=False)
    reviews_json = Column(JSON, default=list, nullable=False)
    restrictions_json = Column(JSON, default=list, nullable=False)
    product_url = Column(String(500), nullable=True)

    script_jobs = relationship("ScriptJob", back_populates="product")
    publishing_packages = relationship("PublishingPackage", back_populates="product")
    creative_specs = relationship("VideoCreativeSpecRecord", back_populates="product")
    asset_kits = relationship("ProductAssetKit", back_populates="product")
    demand_hypotheses = relationship("DemandHypothesisRecord", back_populates="product")
    content_runs = relationship("ContentRun", back_populates="product")


class BrandGuide(Base, TimestampMixin):
    __tablename__ = "brand_guides"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(120), nullable=False, index=True)
    tone_of_voice = Column(Text, nullable=True)
    visual_style = Column(Text, nullable=True)
    forbidden_words_json = Column(JSON, default=list, nullable=False)
    forbidden_claims_json = Column(JSON, default=list, nullable=False)
    required_disclaimers_json = Column(JSON, default=list, nullable=False)
    allowed_cta_json = Column(JSON, default=list, nullable=False)

    script_jobs = relationship("ScriptJob", back_populates="brand_guide")


class CreativeTemplate(Base, TimestampMixin):
    __tablename__ = "creative_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    format = Column(String(80), nullable=False, default="short_video")
    duration_seconds = Column(Integer, nullable=False, default=15)
    aspect_ratio = Column(String(20), nullable=False, default="9:16")
    structure_json = Column(JSON, default=list, nullable=False)
    hook_formula = Column(Text, nullable=True)
    cta = Column(String(255), nullable=True)
    platform_fit_json = Column(JSON, default=list, nullable=False)

    script_jobs = relationship("ScriptJob", back_populates="template")


class ScriptJob(Base, TimestampMixin):
    __tablename__ = "script_jobs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("creative_templates.id"), nullable=False)
    brand_guide_id = Column(Integer, ForeignKey("brand_guides.id"), nullable=False)
    status = Column(String(80), nullable=False, default="draft", index=True)
    input_payload_json = Column(JSON, default=dict, nullable=False)
    output_script_json = Column(JSON, default=dict, nullable=False)
    validation_report_json = Column(JSON, default=dict, nullable=False)
    llm_provider = Column(String(120), nullable=True)
    llm_model = Column(String(160), nullable=True)
    llm_request_json = Column(JSON, default=dict, nullable=False)
    llm_response_json = Column(JSON, default=dict, nullable=False)

    product = relationship("Product", back_populates="script_jobs")
    template = relationship("CreativeTemplate", back_populates="script_jobs")
    brand_guide = relationship("BrandGuide", back_populates="script_jobs")
    variants = relationship("ScriptVariant", back_populates="script_job", cascade="all, delete-orphan")


class ScriptVariant(Base, TimestampMixin):
    __tablename__ = "script_variants"

    id = Column(Integer, primary_key=True, index=True)
    script_job_id = Column(Integer, ForeignKey("script_jobs.id"), nullable=False)
    variant_number = Column(Integer, nullable=False, default=1)
    creative_angle = Column(String(160), nullable=True)
    hook = Column(Text, nullable=True)
    key_message = Column(Text, nullable=True)
    final_cta = Column(Text, nullable=True)
    full_script_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(80), nullable=False, default="draft", index=True)

    script_job = relationship("ScriptJob", back_populates="variants")
    scenes = relationship("Scene", back_populates="script_variant", cascade="all, delete-orphan")
    video_jobs = relationship("VideoJob", back_populates="script_variant")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    script_variant_id = Column(Integer, ForeignKey("script_variants.id"), nullable=False)
    scene_number = Column(Integer, nullable=False)
    time_start = Column(Float, nullable=False, default=0)
    time_end = Column(Float, nullable=False, default=3)
    visual_description = Column(Text, nullable=True)
    voiceover = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    video_prompt = Column(Text, nullable=True)
    negative_prompt = Column(Text, nullable=True)
    source_fields_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    script_variant = relationship("ScriptVariant", back_populates="scenes")
    clips = relationship("VideoClip", back_populates="scene")


class VideoJob(Base, TimestampMixin):
    __tablename__ = "video_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_video_job_organization_product",
        ),
        UniqueConstraint(
            "source_product_ugc_draft_id",
            name="uq_video_job_product_ugc_source",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    script_variant_id = Column(Integer, ForeignKey("script_variants.id"), nullable=False)
    # These fields are nullable for legacy jobs. Canonical Product UGC jobs always
    # populate all four, giving the generated artifact explicit ownership and
    # source lineage without changing the old script-based workflow.
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    source_product_ugc_draft_id = Column(
        Integer,
        ForeignKey("product_ugc_recipe_drafts.id"),
        nullable=True,
        index=True,
    )
    provider = Column(String(120), nullable=False, default="mock")
    status = Column(String(80), nullable=False, default="video_generation_queued", index=True)
    aspect_ratio = Column(String(20), nullable=False, default="9:16")
    duration_seconds = Column(Integer, nullable=False, default=15)
    output_video_path = Column(String(500), nullable=True)
    preview_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    cost_estimate = Column(Float, nullable=False, default=0)

    script_variant = relationship("ScriptVariant", back_populates="video_jobs")
    clips = relationship("VideoClip", back_populates="video_job", cascade="all, delete-orphan")
    publishing_packages = relationship("PublishingPackage", back_populates="video_job")
    frame_extraction_results = relationship("FrameExtractionResult", back_populates="video_job", cascade="all, delete-orphan")
    output_acceptances = relationship("VideoOutputAcceptance", back_populates="video_job", cascade="all, delete-orphan")
    source_product_ugc_draft = relationship("ProductUGCRecipeDraft", foreign_keys=[source_product_ugc_draft_id])


class VideoClip(Base):
    __tablename__ = "video_clips"

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    provider_job_id = Column(String(160), nullable=True)
    status = Column(String(80), nullable=False, default="upload_queued", index=True)
    clip_path = Column(String(500), nullable=True)
    raw_response_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    video_job = relationship("VideoJob", back_populates="clips")
    scene = relationship("Scene", back_populates="clips")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    reviewer_name = Column(String(160), nullable=False, default="admin")
    status = Column(String(80), nullable=False, default="pending")
    comment = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class PublishingAccount(Base, TimestampMixin):
    __tablename__ = "publishing_accounts"

    id = Column(Integer, primary_key=True, index=True)
    brand = Column(String(120), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    account_name = Column(String(160), nullable=False)
    account_handle = Column(String(160), nullable=True)
    account_url = Column(String(500), nullable=True)
    owner_name = Column(String(160), nullable=True)
    auth_status = Column(String(80), nullable=False, default="manual_upload_required")
    warmup_status = Column(String(80), nullable=False, default="new", index=True)
    warmup_phase = Column(String(80), nullable=False, default="phase_0_setup", index=True)
    daily_publish_limit = Column(Integer, nullable=False, default=1)
    weekly_publish_limit = Column(Integer, nullable=False, default=3)
    allowed_formats_json = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)

    warmup_plans = relationship("WarmupPlan", back_populates="account")
    publishing_jobs = relationship("PublishingJob", back_populates="account")


class WarmupPlan(Base, TimestampMixin):
    __tablename__ = "warmup_plans"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("publishing_accounts.id"), nullable=True)
    name = Column(String(160), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="active")
    start_date = Column(DateTime, default=utcnow, nullable=False)
    current_phase = Column(String(80), nullable=False, default="phase_1_soft_start")
    rules_json = Column(JSON, default=list, nullable=False)

    account = relationship("PublishingAccount", back_populates="warmup_plans")
    rules = relationship("WarmupRule", back_populates="warmup_plan", cascade="all, delete-orphan")


class WarmupRule(Base):
    __tablename__ = "warmup_rules"

    id = Column(Integer, primary_key=True, index=True)
    warmup_plan_id = Column(Integer, ForeignKey("warmup_plans.id"), nullable=False)
    phase = Column(String(80), nullable=False, index=True)
    day_from = Column(Integer, nullable=False, default=1)
    day_to = Column(Integer, nullable=False, default=7)
    max_posts_per_day = Column(Integer, nullable=False, default=1)
    max_posts_per_week = Column(Integer, nullable=False, default=3)
    allowed_content_types_json = Column(JSON, default=list, nullable=False)
    requires_manual_approval = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    warmup_plan = relationship("WarmupPlan", back_populates="rules")


class PublishingPackage(Base, TimestampMixin):
    __tablename__ = "publishing_packages"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "media_artifact_id",
            "target_platform",
            name="uq_publishing_package_org_artifact_platform",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    # Cloud-native packages can originate from a durable MediaArtifact after
    # the worker scratch path and even the legacy VideoJob link are gone.
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True)
    media_artifact_id = Column(Integer, ForeignKey("media_artifacts.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    brand = Column(String(120), nullable=False, index=True)
    target_platform = Column(String(120), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    hashtags_json = Column(JSON, default=list, nullable=False)
    cta = Column(String(255), nullable=True)
    product_url = Column(String(500), nullable=True)
    utm_url = Column(String(500), nullable=True)
    cover_image_path = Column(String(500), nullable=True)
    video_file_path = Column(String(500), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    ai_generated_flag = Column(Boolean, default=True, nullable=False)
    review_status = Column(String(80), nullable=False, default="needs_review", index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)

    video_job = relationship("VideoJob", back_populates="publishing_packages")
    media_artifact = relationship("MediaArtifact")
    creative_variant = relationship("CreativeVariant")
    product = relationship("Product", back_populates="publishing_packages")
    publishing_jobs = relationship("PublishingJob", back_populates="publishing_package")
    publishing_tasks = relationship("PublishingTask", back_populates="publishing_package")


class PublishingDestination(Base, TimestampMixin):
    __tablename__ = "publishing_destinations"

    id = Column(Integer, primary_key=True, index=True)
    # Kept nullable for pre-auth installations. Canonical content cycles require
    # an explicitly owned destination and reject legacy unscoped rows.
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    brand = Column(String(120), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    handle = Column(String(160), nullable=True)
    url = Column(String(500), nullable=True)
    owner_name = Column(String(160), nullable=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    posting_mode = Column(String(80), nullable=False, default="manual", index=True)
    auth_status = Column(String(80), nullable=False, default="manual_only", index=True)
    allowed_formats_json = Column(JSON, default=list, nullable=False)
    daily_limit = Column(Integer, nullable=False, default=1)
    weekly_limit = Column(Integer, nullable=False, default=3)
    notes = Column(Text, nullable=True)

    publishing_tasks = relationship("PublishingTask", back_populates="destination")


class DestinationConnection(Base, TimestampMixin):
    __tablename__ = "destination_connections"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    connection_type = Column(String(80), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="not_configured", index=True)
    auth_status = Column(String(80), nullable=False, default="manual_only", index=True)
    credential_ref = Column(String(160), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    settings_json = Column(JSON, default=dict, nullable=False)

    destination = relationship("PublishingDestination")


class DestinationMetricSync(Base, TimestampMixin):
    __tablename__ = "destination_metric_syncs"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    connection_id = Column(Integer, ForeignKey("destination_connections.id"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="queued", index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    imported_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    warnings_json = Column(JSON, default=list, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)

    destination = relationship("PublishingDestination")
    connection = relationship("DestinationConnection")
    campaign = relationship("Campaign")


class DestinationPostMetric(Base):
    __tablename__ = "destination_post_metrics"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    connection_id = Column(Integer, ForeignKey("destination_connections.id"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    platform = Column(String(120), nullable=False, index=True)
    posted_url = Column(String(500), nullable=True, index=True)
    provider_post_id = Column(String(160), nullable=True, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    spend = Column(Float, nullable=True)
    watch_time_seconds = Column(Float, nullable=True)
    retention_rate = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    ctr = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    destination = relationship("PublishingDestination")
    connection = relationship("DestinationConnection")
    campaign = relationship("Campaign")
    publishing_task = relationship("PublishingTask")
    product = relationship("Product")


class DestinationConnectionAudit(Base):
    __tablename__ = "destination_connection_audits"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    connection_id = Column(Integer, ForeignKey("destination_connections.id"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    status = Column(String(80), nullable=False, index=True)
    message = Column(Text, nullable=True)
    sanitized_payload_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    destination = relationship("PublishingDestination")
    connection = relationship("DestinationConnection")


class MetricsSource(Base, TimestampMixin):
    __tablename__ = "metrics_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    source_type = Column(String(80), nullable=False, default="manual_csv", index=True)
    platform = Column(String(120), nullable=False, default="other", index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    connection_id = Column(Integer, ForeignKey("destination_connections.id"), nullable=True, index=True)
    settings_json = Column(JSON, default=dict, nullable=False)

    connection = relationship("DestinationConnection")


class TrackingLink(Base, TimestampMixin):
    __tablename__ = "tracking_links"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="active", index=True)

    campaign = relationship("Campaign")
    publishing_task = relationship("PublishingTask")
    destination = relationship("PublishingDestination")
    product = relationship("Product")
    creative_variant = relationship("CreativeVariant")
    participant = relationship("ParticipantProfile")
    clicks = relationship("TrackingClick", back_populates="tracking_link", cascade="all, delete-orphan")


class TrackingClick(Base):
    __tablename__ = "tracking_clicks"

    id = Column(Integer, primary_key=True, index=True)
    tracking_link_id = Column(Integer, ForeignKey("tracking_links.id"), nullable=False, index=True)
    clicked_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=True, index=True)
    referrer = Column(String(500), nullable=True)
    user_agent_hash = Column(String(128), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    tracking_link = relationship("TrackingLink", back_populates="clicks")
    campaign = relationship("Campaign")
    publishing_task = relationship("PublishingTask")
    destination = relationship("PublishingDestination")


class MetricsIntakeBatch(Base, TimestampMixin):
    __tablename__ = "metrics_intake_batches"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("metrics_sources.id"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    source_type = Column(String(80), nullable=False, default="manual_csv", index=True)
    status = Column(String(80), nullable=False, default="imported", index=True)
    imported_count = Column(Integer, nullable=False, default=0)
    matched_count = Column(Integer, nullable=False, default=0)
    unmatched_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    warnings_json = Column(JSON, default=list, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)
    rows_json = Column(JSON, default=list, nullable=False)
    unmatched_rows_json = Column(JSON, default=list, nullable=False)

    source = relationship("MetricsSource")
    campaign = relationship("Campaign")


class FunnelSnapshot(Base):
    __tablename__ = "funnel_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=True, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    views = Column(Integer, nullable=False, default=0)
    reach = Column(Integer, nullable=False, default=0)
    impressions = Column(Integer, nullable=False, default=0)
    engagements = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    orders = Column(Integer, nullable=False, default=0)
    revenue = Column(Float, nullable=False, default=0)
    returns_count = Column(Integer, nullable=False, default=0)
    ctr = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    revenue_per_view = Column(Float, nullable=True)
    revenue_per_click = Column(Float, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    campaign = relationship("Campaign")
    product = relationship("Product")
    creative_variant = relationship("CreativeVariant")
    destination = relationship("PublishingDestination")
    participant = relationship("ParticipantProfile")


class AttributionRule(Base, TimestampMixin):
    __tablename__ = "attribution_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    rule_type = Column(String(80), nullable=False, default="final_url", index=True)
    priority = Column(Integer, nullable=False, default=100, index=True)
    settings_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(80), nullable=False, default="active", index=True)


class PublishingTask(Base, TimestampMixin):
    __tablename__ = "publishing_tasks"

    id = Column(Integer, primary_key=True, index=True)
    publishing_package_id = Column(Integer, ForeignKey("publishing_packages.id"), nullable=False, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    scheduled_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    final_url = Column(String(500), nullable=True)
    operator_name = Column(String(160), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_response_json = Column(JSON, default=dict, nullable=False)

    publishing_package = relationship("PublishingPackage", back_populates="publishing_tasks")
    destination = relationship("PublishingDestination", back_populates="publishing_tasks")


class PublishingJob(Base, TimestampMixin):
    __tablename__ = "publishing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    publishing_package_id = Column(Integer, ForeignKey("publishing_packages.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("publishing_accounts.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    status = Column(String(80), nullable=False, default="scheduled", index=True)
    provider = Column(String(120), nullable=False, default="mock")
    provider_post_id = Column(String(160), nullable=True)
    provider_post_url = Column(String(500), nullable=True)
    manual_upload_required = Column(Boolean, default=False, nullable=False)
    operator_name = Column(String(160), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_response_json = Column(JSON, default=dict, nullable=False)

    publishing_package = relationship("PublishingPackage", back_populates="publishing_jobs")
    account = relationship("PublishingAccount", back_populates="publishing_jobs")
    analytics = relationship("PublishAnalytics", back_populates="publishing_job", cascade="all, delete-orphan")


class PublishAnalytics(Base):
    __tablename__ = "publish_analytics"

    id = Column(Integer, primary_key=True, index=True)
    publishing_job_id = Column(Integer, ForeignKey("publishing_jobs.id"), nullable=False)
    collected_at = Column(DateTime, default=utcnow, nullable=False)
    views = Column(Integer, nullable=False, default=0)
    likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)
    shares = Column(Integer, nullable=False, default=0)
    saves = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    ctr = Column(Float, nullable=False, default=0)
    raw_metrics_json = Column(JSON, default=dict, nullable=False)

    publishing_job = relationship("PublishingJob", back_populates="analytics")


class ExportPackage(Base):
    __tablename__ = "export_packages"

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False)
    destination = Column(String(160), nullable=False)
    video_file = Column(String(500), nullable=True)
    preview_file = Column(String(500), nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    tags_json = Column(JSON, default=list, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ProductMetricSnapshot(Base):
    __tablename__ = "product_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    marketplace = Column(String(120), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    views = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    add_to_cart = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    ctr = Column(Float, nullable=True)
    avg_price = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    ad_spend = Column(Float, nullable=True)
    ad_orders = Column(Integer, nullable=True)
    ad_revenue = Column(Float, nullable=True)
    stock_qty = Column(Integer, nullable=True)
    days_of_stock = Column(Float, nullable=True)
    returns_count = Column(Integer, nullable=True)
    returns_rate = Column(Float, nullable=True)
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CreativePerformanceSnapshot(Base):
    __tablename__ = "creative_performance_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("publishing_accounts.id"), nullable=True)
    video_url = Column(String(500), nullable=True)
    creative_template = Column(String(160), nullable=True)
    creative_angle = Column(String(160), nullable=True)
    hook_text = Column(Text, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    ctr = Column(Float, nullable=True)
    orders = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    watch_time_seconds = Column(Float, nullable=True)
    retention_rate = Column(Float, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ProductReviewInsight(Base):
    __tablename__ = "product_review_insights"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    marketplace = Column(String(120), nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    positive_themes_json = Column(JSON, default=list, nullable=False)
    negative_themes_json = Column(JSON, default=list, nullable=False)
    buyer_objections_json = Column(JSON, default=list, nullable=False)
    buyer_language_json = Column(JSON, default=list, nullable=False)
    source_review_count = Column(Integer, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class MarketSignal(Base):
    __tablename__ = "market_signals"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    marketplace = Column(String(120), nullable=True)
    competitor_brand = Column(String(160), nullable=True)
    competitor_product_url = Column(String(500), nullable=True)
    competitor_price = Column(Float, nullable=True)
    competitor_rating = Column(Float, nullable=True)
    competitor_reviews_count = Column(Integer, nullable=True)
    signal_type = Column(String(120), nullable=False, index=True)
    signal_strength = Column(String(80), nullable=False, default="medium")
    notes = Column(Text, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CreativeIntelligencePackRecord(Base):
    __tablename__ = "creative_intelligence_pack_records"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    sku = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="ready")
    pack_json = Column(JSON, default=dict, nullable=False)
    source_summary_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    product = relationship("Product")


class DemandHypothesisRecord(Base, TimestampMixin):
    __tablename__ = "demand_hypothesis_records"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    need_type = Column(String(120), nullable=False, index=True)
    buyer_need = Column(Text, nullable=False)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=True, index=True)
    hypothesis_json = Column(JSON, default=dict, nullable=False)
    signals_json = Column(JSON, default=dict, nullable=False)
    validation_report_json = Column(JSON, default=dict, nullable=False)
    source_summary_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product", back_populates="demand_hypotheses")
    creative_spec = relationship("VideoCreativeSpecRecord")


class ScriptBrief(Base):
    __tablename__ = "script_briefs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    intelligence_pack_id = Column(Integer, ForeignKey("creative_intelligence_pack_records.id"), nullable=False)
    status = Column(String(80), nullable=False, default="ready")
    objective = Column(String(160), nullable=False)
    creative_angle = Column(String(160), nullable=False)
    target_audience = Column(String(255), nullable=True)
    brief_json = Column(JSON, default=dict, nullable=False)
    allowed_claims_json = Column(JSON, default=list, nullable=False)
    missing_data_json = Column(JSON, default=list, nullable=False)
    safety_warnings_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    product = relationship("Product")
    intelligence_pack = relationship("CreativeIntelligencePackRecord")


class PromptPack(Base):
    __tablename__ = "prompt_packs"

    id = Column(Integer, primary_key=True, index=True)
    script_brief_id = Column(Integer, ForeignKey("script_briefs.id"), nullable=False)
    script_variant_id = Column(Integer, ForeignKey("script_variants.id"), nullable=True)
    status = Column(String(80), nullable=False, default="ready")
    prompt_pack_json = Column(JSON, default=dict, nullable=False)
    scene_prompts_json = Column(JSON, default=list, nullable=False)
    negative_prompts_json = Column(JSON, default=list, nullable=False)
    provider_payload_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    script_brief = relationship("ScriptBrief")
    script_variant = relationship("ScriptVariant")


class VideoCreativeSpecRecord(Base, TimestampMixin):
    __tablename__ = "video_creative_spec_records"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    intelligence_pack_id = Column(Integer, ForeignKey("creative_intelligence_pack_records.id"), nullable=False)
    script_brief_id = Column(Integer, ForeignKey("script_briefs.id"), nullable=False)
    platform = Column(String(120), nullable=False, index=True)
    format = Column(String(80), nullable=False, default="short_video")
    aspect_ratio = Column(String(20), nullable=False, default="9:16")
    duration_seconds = Column(Integer, nullable=False, default=15)
    status = Column(String(80), nullable=False, default="ready", index=True)
    spec_json = Column(JSON, default=dict, nullable=False)
    hook_candidates_json = Column(JSON, default=list, nullable=False)
    validation_report_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product", back_populates="creative_specs")
    intelligence_pack = relationship("CreativeIntelligencePackRecord")
    script_brief = relationship("ScriptBrief")
    generation_variants = relationship("VideoGenerationVariant", back_populates="creative_spec")
    first_frame_options = relationship("FirstFrameOption", back_populates="creative_spec")
    creative_variant_sets = relationship("CreativeVariantSet", back_populates="creative_spec")


class ProductAssetKit(Base, TimestampMixin):
    __tablename__ = "product_asset_kits"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    assets_json = Column(JSON, default=list, nullable=False)
    required_assets_json = Column(JSON, default=list, nullable=False)
    missing_assets_json = Column(JSON, default=list, nullable=False)
    validation_report_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    real_generation_allowed = Column(Boolean, default=False, nullable=False)
    override_required_assets = Column(Boolean, default=False, nullable=False)
    primary_reference_asset_id = Column(Integer, nullable=True)
    provider_reference_bundle_json = Column(JSON, default=dict, nullable=False)
    real_generation_blockers_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product", back_populates="asset_kits")
    assets = relationship("ProductAsset", back_populates="asset_kit", cascade="all, delete-orphan")
    first_frame_options = relationship("FirstFrameOption", back_populates="asset_kit")
    creative_variant_sets = relationship("CreativeVariantSet", back_populates="asset_kit")
    reference_bundles = relationship("ProductReferenceBundle", back_populates="asset_kit", cascade="all, delete-orphan")


class ProductAsset(Base, TimestampMixin):
    __tablename__ = "product_assets"
    # Production PostgreSQL adds these reverse MediaArtifact links with ALTER
    # so the existing MediaArtifact -> draft links do not form an unsortable
    # DDL cycle. SQLite create_all fixtures omit only the reverse constraints;
    # Alembic migration tests still exercise the real named FKs.
    __table_args__ = (
        ForeignKeyConstraint(
            ["media_artifact_id"],
            ["media_artifacts.id"],
            name="fk_product_assets_media_artifact",
            use_alter=True,
        ).ddl_if(dialect=("postgresql",)),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    asset_kit_id = Column(Integer, ForeignKey("product_asset_kits.id"), nullable=False, index=True)
    media_artifact_id = Column(
        Integer,
        nullable=True,
        index=True,
    )
    source_ref = Column(String(1000), nullable=False)
    source_type = Column(String(40), nullable=False, default="unknown")
    asset_type = Column(String(80), nullable=False, default="unknown", index=True)
    asset_role = Column(String(80), nullable=True)
    filename = Column(String(255), nullable=True)
    extension = Column(String(40), nullable=True)
    mime_type = Column(String(120), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    exists = Column(Boolean, default=False, nullable=False)
    status = Column(String(80), nullable=False, default="ready", index=True)
    is_primary_reference = Column(Boolean, default=False, nullable=False)
    is_safe_for_real_generation = Column(Boolean, default=False, nullable=False)
    manual_label = Column(String(255), nullable=True)
    review_status = Column(String(80), nullable=False, default="pending", index=True)
    review_notes = Column(Text, nullable=True)
    checksum = Column(String(128), nullable=True, index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    asset_kit = relationship("ProductAssetKit", back_populates="assets")
    media_artifact = relationship("MediaArtifact", foreign_keys=[media_artifact_id])


class ProductReferenceBundle(Base, TimestampMixin):
    __tablename__ = "product_reference_bundles"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    asset_kit_id = Column(Integer, ForeignKey("product_asset_kits.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    provider = Column(String(120), nullable=False, default="runway", index=True)
    primary_image_asset_id = Column(Integer, nullable=True)
    reference_asset_ids_json = Column(JSON, default=list, nullable=False)
    provider_payload_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    asset_kit = relationship("ProductAssetKit", back_populates="reference_bundles")


class ProductAssetRequirement(Base, TimestampMixin):
    __tablename__ = "product_asset_requirements"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    variant_key = Column(String(160), nullable=True, index=True)
    product_profile = Column(String(80), nullable=False, default="general", index=True)
    required_tier = Column(String(40), nullable=False, default="tier_0", index=True)
    purpose = Column(String(120), nullable=False, default="strategy", index=True)
    required_asset_types_json = Column(JSON, default=list, nullable=False)
    missing_asset_types_json = Column(JSON, default=list, nullable=False)
    status = Column(String(80), nullable=False, default="needs_assets", index=True)
    requirement_json = Column(JSON, default=dict, nullable=False)

    product = relationship("Product")


class ProductAssetTierSnapshot(Base, TimestampMixin):
    __tablename__ = "product_asset_tier_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    variant_key = Column(String(160), nullable=True, index=True)
    product_profile = Column(String(80), nullable=False, default="general", index=True)
    current_tier = Column(String(40), nullable=False, default="tier_0", index=True)
    wrapper_refs_count = Column(Integer, nullable=False, default=0)
    edible_refs_count = Column(Integer, nullable=False, default=0)
    style_refs_count = Column(Integer, nullable=False, default=0)
    lifestyle_refs_count = Column(Integer, nullable=False, default=0)
    identity_refs_count = Column(Integer, nullable=False, default=0)
    use_case_refs_count = Column(Integer, nullable=False, default=0)
    classified_assets_json = Column(JSON, default=list, nullable=False)
    variant_mismatch_asset_ids_json = Column(JSON, default=list, nullable=False)
    missing_assets_json = Column(JSON, default=list, nullable=False)
    allowed_scenes_json = Column(JSON, default=list, nullable=False)
    blocked_scenes_json = Column(JSON, default=list, nullable=False)
    permissions_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")


class FirstFrameOption(Base, TimestampMixin):
    __tablename__ = "first_frame_options"

    id = Column(Integer, primary_key=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    asset_kit_id = Column(Integer, ForeignKey("product_asset_kits.id"), nullable=True, index=True)
    option_number = Column(Integer, nullable=False, default=1)
    status = Column(String(80), nullable=False, default="ready", index=True)
    hook_text = Column(Text, nullable=False)
    visual_concept = Column(Text, nullable=False)
    text_overlay = Column(Text, nullable=False)
    product_placement = Column(Text, nullable=False)
    camera_motion = Column(Text, nullable=False)
    composition = Column(Text, nullable=False)
    product_visible_by_second = Column(Float, nullable=False, default=1.0)
    required_assets_json = Column(JSON, default=list, nullable=False)
    risk_flags_json = Column(JSON, default=list, nullable=False)
    option_json = Column(JSON, default=dict, nullable=False)

    creative_spec = relationship("VideoCreativeSpecRecord", back_populates="first_frame_options")
    asset_kit = relationship("ProductAssetKit", back_populates="first_frame_options")
    creative_variants = relationship("CreativeVariant", back_populates="first_frame_option")


class CreativeVariantSet(Base, TimestampMixin):
    __tablename__ = "creative_variant_sets"

    id = Column(Integer, primary_key=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    asset_kit_id = Column(Integer, ForeignKey("product_asset_kits.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    variant_count = Column(Integer, nullable=False, default=0)
    selected_variant_id = Column(Integer, nullable=True)
    selection_reason = Column(Text, nullable=True)
    variants_json = Column(JSON, default=list, nullable=False)
    score_summary_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    creative_spec = relationship("VideoCreativeSpecRecord", back_populates="creative_variant_sets")
    asset_kit = relationship("ProductAssetKit", back_populates="creative_variant_sets")
    variants = relationship("CreativeVariant", back_populates="variant_set", cascade="all, delete-orphan")


class CreativeVariant(Base, TimestampMixin):
    __tablename__ = "creative_variants"

    id = Column(Integer, primary_key=True, index=True)
    creative_variant_set_id = Column(Integer, ForeignKey("creative_variant_sets.id"), nullable=False, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    first_frame_option_id = Column(Integer, ForeignKey("first_frame_options.id"), nullable=True, index=True)
    variant_number = Column(Integer, nullable=False, default=1)
    status = Column(String(80), nullable=False, default="ready", index=True)
    hook_text = Column(Text, nullable=False)
    first_frame_json = Column(JSON, default=dict, nullable=False)
    scene_plan_json = Column(JSON, default=list, nullable=False)
    pacing_json = Column(JSON, default=dict, nullable=False)
    cta_framing = Column(Text, nullable=True)
    visual_style = Column(Text, nullable=True)
    product_reveal_timing = Column(Float, nullable=False, default=1.0)
    asset_refs_json = Column(JSON, default=list, nullable=False)
    score_json = Column(JSON, default=dict, nullable=False)
    risk_flags_json = Column(JSON, default=list, nullable=False)
    selection_reason = Column(Text, nullable=True)

    variant_set = relationship("CreativeVariantSet", back_populates="variants")
    creative_spec = relationship("VideoCreativeSpecRecord")
    first_frame_option = relationship("FirstFrameOption", back_populates="creative_variants")


class VideoGenerationVariant(Base, TimestampMixin):
    __tablename__ = "video_generation_variants"

    id = Column(Integer, primary_key=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True)
    script_variant_id = Column(Integer, ForeignKey("script_variants.id"), nullable=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True)
    provider = Column(String(120), nullable=False, default="mock")
    status = Column(String(80), nullable=False, default="prompt_pack_ready", index=True)
    prompt_pack_json = Column(JSON, default=dict, nullable=False)
    provider_payload_json = Column(JSON, default=dict, nullable=False)
    local_output_paths_json = Column(JSON, default=list, nullable=False)
    final_video_path = Column(String(500), nullable=True)
    quality_score_json = Column(JSON, default=dict, nullable=False)
    regeneration_log_json = Column(JSON, default=list, nullable=False)

    creative_spec = relationship("VideoCreativeSpecRecord", back_populates="generation_variants")
    creative_variant = relationship("CreativeVariant")
    prompt_pack = relationship("PromptPack")
    script_variant = relationship("ScriptVariant")
    video_job = relationship("VideoJob")
    quality_reviews = relationship("VideoQualityReview", back_populates="generation_variant")
    regeneration_requests = relationship("SceneRegenerationRequest", back_populates="generation_variant")


class VideoQualityReview(Base, TimestampMixin):
    __tablename__ = "video_quality_reviews"

    id = Column(Integer, primary_key=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    video_generation_variant_id = Column(Integer, ForeignKey("video_generation_variants.id"), nullable=False, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True)
    status = Column(String(80), nullable=False, default="metadata_scored", index=True)
    score = Column(Float, nullable=False, default=0)
    review_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    creative_spec = relationship("VideoCreativeSpecRecord")
    generation_variant = relationship("VideoGenerationVariant", back_populates="quality_reviews")
    video_job = relationship("VideoJob")


class ProductStrategySpec(Base, TimestampMixin):
    __tablename__ = "product_strategy_specs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    buyer_segment_json = Column(JSON, default=dict, nullable=False)
    buyer_situation_json = Column(JSON, default=dict, nullable=False)
    purchase_trigger = Column(Text, nullable=True)
    main_pain = Column(Text, nullable=True)
    main_desire = Column(Text, nullable=True)
    main_objection = Column(Text, nullable=True)
    product_role = Column(Text, nullable=True)
    category_alternative = Column(Text, nullable=True)
    competitor_context_json = Column(JSON, default=dict, nullable=False)
    price_position_json = Column(JSON, default=dict, nullable=False)
    stock_context_json = Column(JSON, default=dict, nullable=False)
    offer_strategy_json = Column(JSON, default=dict, nullable=False)
    proof_required_json = Column(JSON, default=list, nullable=False)
    safe_claims_json = Column(JSON, default=list, nullable=False)
    forbidden_claims_json = Column(JSON, default=list, nullable=False)
    platform_strategy_json = Column(JSON, default=dict, nullable=False)
    content_angles_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    offers = relationship("OfferStrategy", back_populates="product_strategy_spec", cascade="all, delete-orphan")


class OfferStrategy(Base, TimestampMixin):
    __tablename__ = "offer_strategies"

    id = Column(Integer, primary_key=True, index=True)
    product_strategy_spec_id = Column(Integer, ForeignKey("product_strategy_specs.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    offer_type = Column(String(120), nullable=False, default="value", index=True)
    price_message = Column(Text, nullable=True)
    discount_message = Column(Text, nullable=True)
    value_reason = Column(Text, nullable=True)
    competitor_response = Column(Text, nullable=True)
    stock_warning = Column(Text, nullable=True)
    cta_strategy = Column(Text, nullable=True)
    warnings_json = Column(JSON, default=list, nullable=False)

    product_strategy_spec = relationship("ProductStrategySpec", back_populates="offers")
    product = relationship("Product")


class BloggerMeaningSpec(Base, TimestampMixin):
    __tablename__ = "blogger_meaning_specs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    demand_hypothesis_id = Column(Integer, ForeignKey("demand_hypothesis_records.id"), nullable=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=True, index=True)
    creator_persona_json = Column(JSON, default=dict, nullable=False)
    buyer_context_json = Column(JSON, default=dict, nullable=False)
    blogger_story_json = Column(JSON, default=dict, nullable=False)
    authenticity_rules_json = Column(JSON, default=dict, nullable=False)
    scene_intent_json = Column(JSON, default=list, nullable=False)
    hook_options_json = Column(JSON, default=list, nullable=False)
    proof_moment_json = Column(JSON, default=dict, nullable=False)
    cta_json = Column(JSON, default=dict, nullable=False)
    product_lock_rules_json = Column(JSON, default=dict, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    demand_hypothesis = relationship("DemandHypothesisRecord")
    creative_spec = relationship("VideoCreativeSpecRecord")
    scripts = relationship("UGCAdScript", back_populates="blogger_meaning_spec", cascade="all, delete-orphan")


class UGCAdScript(Base, TimestampMixin):
    __tablename__ = "ugc_ad_scripts"

    id = Column(Integer, primary_key=True, index=True)
    blogger_meaning_spec_id = Column(Integer, ForeignKey("blogger_meaning_specs.id"), nullable=False, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    duration_seconds = Column(Integer, nullable=False, default=8)
    voiceover_json = Column(JSON, default=dict, nullable=False)
    captions_json = Column(JSON, default=dict, nullable=False)
    scene_script_json = Column(JSON, default=list, nullable=False)

    blogger_meaning_spec = relationship("BloggerMeaningSpec", back_populates="scripts")
    creative_variant = relationship("CreativeVariant")
    quality_scores = relationship("CreativeQualityScore", back_populates="ugc_script", cascade="all, delete-orphan")


class CreativeQualityScore(Base, TimestampMixin):
    __tablename__ = "creative_quality_scores"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    product_strategy_spec_id = Column(Integer, ForeignKey("product_strategy_specs.id"), nullable=True, index=True)
    blogger_meaning_spec_id = Column(Integer, ForeignKey("blogger_meaning_specs.id"), nullable=True, index=True)
    ugc_script_id = Column(Integer, ForeignKey("ugc_ad_scripts.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="needs_rewrite", index=True)
    total_score = Column(Float, nullable=False, default=0)
    hook_strength_score = Column(Float, nullable=False, default=0)
    personal_situation_score = Column(Float, nullable=False, default=0)
    buyer_need_clarity_score = Column(Float, nullable=False, default=0)
    product_reason_score = Column(Float, nullable=False, default=0)
    proof_moment_score = Column(Float, nullable=False, default=0)
    natural_blogger_language_score = Column(Float, nullable=False, default=0)
    cta_clarity_score = Column(Float, nullable=False, default=0)
    claims_safety_score = Column(Float, nullable=False, default=0)
    product_lock_reference_safety_score = Column(Float, nullable=False, default=0)
    scene_completeness_score = Column(Float, nullable=False, default=0)
    offer_alignment_score = Column(Float, nullable=False, default=0)
    platform_fit_score = Column(Float, nullable=False, default=0)
    reasons_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)
    breakdown_json = Column(JSON, default=dict, nullable=False)
    gate_json = Column(JSON, default=dict, nullable=False)

    product = relationship("Product")
    product_strategy_spec = relationship("ProductStrategySpec")
    blogger_meaning_spec = relationship("BloggerMeaningSpec")
    ugc_script = relationship("UGCAdScript", back_populates="quality_scores")
    creative_variant = relationship("CreativeVariant")
    prompt_pack = relationship("PromptPack")
    rewrite_requests = relationship("CreativeRewriteRequest", back_populates="quality_score", cascade="all, delete-orphan")


class CreativeRewriteRequest(Base, TimestampMixin):
    __tablename__ = "creative_rewrite_requests"

    id = Column(Integer, primary_key=True, index=True)
    creative_quality_score_id = Column(Integer, ForeignKey("creative_quality_scores.id"), nullable=False, index=True)
    ugc_script_id = Column(Integer, ForeignKey("ugc_ad_scripts.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="requested", index=True)
    reason = Column(String(160), nullable=False, default="quality_score_below_threshold")
    feedback = Column(Text, nullable=True)
    required_fixes_json = Column(JSON, default=list, nullable=False)
    before_script_json = Column(JSON, default=dict, nullable=False)
    rewrite_plan_json = Column(JSON, default=dict, nullable=False)
    new_ugc_script_id = Column(Integer, ForeignKey("ugc_ad_scripts.id"), nullable=True, index=True)

    quality_score = relationship("CreativeQualityScore", back_populates="rewrite_requests")
    ugc_script = relationship("UGCAdScript", foreign_keys=[ugc_script_id])
    new_ugc_script = relationship("UGCAdScript", foreign_keys=[new_ugc_script_id])
    product = relationship("Product")


class CreativeWorkbenchSession(Base, TimestampMixin):
    __tablename__ = "creative_workbench_sessions"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    product_strategy_spec_id = Column(Integer, ForeignKey("product_strategy_specs.id"), nullable=True, index=True)
    offer_strategy_id = Column(Integer, ForeignKey("offer_strategies.id"), nullable=True, index=True)
    blogger_meaning_spec_id = Column(Integer, ForeignKey("blogger_meaning_specs.id"), nullable=True, index=True)
    ugc_script_id = Column(Integer, ForeignKey("ugc_ad_scripts.id"), nullable=True, index=True)
    creative_quality_score_id = Column(Integer, ForeignKey("creative_quality_scores.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    summary_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    product_strategy_spec = relationship("ProductStrategySpec")
    offer_strategy = relationship("OfferStrategy")
    blogger_meaning_spec = relationship("BloggerMeaningSpec")
    ugc_script = relationship("UGCAdScript")
    creative_quality_score = relationship("CreativeQualityScore")
    prompt_pack = relationship("PromptPack")
    approvals = relationship("CreativeBriefApproval", back_populates="workbench_session", cascade="all, delete-orphan")


class CreativeBriefApproval(Base, TimestampMixin):
    __tablename__ = "creative_brief_approvals"

    id = Column(Integer, primary_key=True, index=True)
    workbench_session_id = Column(Integer, ForeignKey("creative_workbench_sessions.id"), nullable=False, index=True)
    reviewer_name = Column(String(160), nullable=False)
    status = Column(String(80), nullable=False, default="approved", index=True)
    notes = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    workbench_session = relationship("CreativeWorkbenchSession", back_populates="approvals")


class AIProductionBrief(Base, TimestampMixin):
    __tablename__ = "ai_production_briefs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    product_strategy_spec_id = Column(Integer, ForeignKey("product_strategy_specs.id"), nullable=True, index=True)
    offer_strategy_id = Column(Integer, ForeignKey("offer_strategies.id"), nullable=True, index=True)
    blogger_meaning_spec_id = Column(Integer, ForeignKey("blogger_meaning_specs.id"), nullable=True, index=True)
    ugc_script_id = Column(Integer, ForeignKey("ugc_ad_scripts.id"), nullable=True, index=True)
    creative_quality_score_id = Column(Integer, ForeignKey("creative_quality_scores.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    platform = Column(String(120), nullable=False, default="Instagram Reels")
    format = Column(String(80), nullable=False, default="short_video")
    one_sentence_thesis = Column(Text, nullable=True)
    viewer_takeaway = Column(Text, nullable=True)
    buyer_situation = Column(Text, nullable=True)
    main_objection = Column(Text, nullable=True)
    reason_to_believe = Column(Text, nullable=True)
    proof_moment = Column(Text, nullable=True)
    cta = Column(Text, nullable=True)
    must_show_json = Column(JSON, default=list, nullable=False)
    must_say_json = Column(JSON, default=list, nullable=False)
    must_avoid_json = Column(JSON, default=list, nullable=False)
    product_identity_rules_json = Column(JSON, default=dict, nullable=False)
    product_lock_mode = Column(String(80), nullable=True, index=True)
    reference_requirements_json = Column(JSON, default=dict, nullable=False)
    scene_count = Column(Integer, nullable=False, default=5)
    duration_seconds = Column(Integer, nullable=False, default=15)
    failure_conditions_json = Column(JSON, default=list, nullable=False)
    brief_json = Column(JSON, default=dict, nullable=False)
    brief_markdown = Column(Text, nullable=True)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    product_strategy_spec = relationship("ProductStrategySpec")
    offer_strategy = relationship("OfferStrategy")
    blogger_meaning_spec = relationship("BloggerMeaningSpec")
    ugc_script = relationship("UGCAdScript")
    creative_quality_score = relationship("CreativeQualityScore")
    scene_blueprints = relationship("SceneBlueprint", back_populates="ai_production_brief", cascade="all, delete-orphan")
    director_prompt_packs = relationship("DirectorPromptPack", back_populates="ai_production_brief", cascade="all, delete-orphan")
    quality_checks = relationship("BriefQualityCheck", back_populates="ai_production_brief", cascade="all, delete-orphan")


class SceneBlueprint(Base, TimestampMixin):
    __tablename__ = "scene_blueprints"

    id = Column(Integer, primary_key=True, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=False, index=True)
    scene_order = Column(Integer, nullable=False, index=True)
    scene_role = Column(String(120), nullable=False, index=True)
    start_second = Column(Float, nullable=False, default=0)
    end_second = Column(Float, nullable=False, default=0)
    viewer_goal = Column(Text, nullable=True)
    visual_action = Column(Text, nullable=True)
    spoken_line = Column(Text, nullable=True)
    onscreen_text = Column(Text, nullable=True)
    caption_text = Column(Text, nullable=True)
    product_visibility = Column(Text, nullable=True)
    camera_framing = Column(Text, nullable=True)
    broll_notes = Column(Text, nullable=True)
    transition_notes = Column(Text, nullable=True)
    must_show_json = Column(JSON, default=list, nullable=False)
    must_avoid_json = Column(JSON, default=list, nullable=False)

    ai_production_brief = relationship("AIProductionBrief", back_populates="scene_blueprints")


class DirectorPromptPack(Base, TimestampMixin):
    __tablename__ = "director_prompt_packs"

    id = Column(Integer, primary_key=True, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=False, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="ready", index=True)
    system_instruction = Column(Text, nullable=True)
    provider_prompt_json = Column(JSON, default=dict, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    asset_instructions_json = Column(JSON, default=dict, nullable=False)
    overlay_instructions_json = Column(JSON, default=dict, nullable=False)
    end_card_instructions_json = Column(JSON, default=dict, nullable=False)
    quality_checklist_json = Column(JSON, default=list, nullable=False)

    ai_production_brief = relationship("AIProductionBrief", back_populates="director_prompt_packs")
    prompt_pack = relationship("PromptPack")


class BriefQualityCheck(Base, TimestampMixin):
    __tablename__ = "brief_quality_checks"

    id = Column(Integer, primary_key=True, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    score = Column(Float, nullable=False, default=0)
    missing_fields_json = Column(JSON, default=list, nullable=False)
    weak_points_json = Column(JSON, default=list, nullable=False)
    failure_risks_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)

    ai_production_brief = relationship("AIProductionBrief", back_populates="quality_checks")


class FrameExtractionResult(Base, TimestampMixin):
    __tablename__ = "frame_extraction_results"

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="created", index=True)
    frame_paths_json = Column(JSON, default=list, nullable=False)
    contact_sheet_path = Column(String(500), nullable=True)
    duration_seconds = Column(Float, nullable=False, default=0)
    fps = Column(Float, nullable=False, default=0)
    warnings_json = Column(JSON, default=list, nullable=False)
    extraction_key = Column(String(80), nullable=True, unique=True, index=True)
    source_video_sha256 = Column(String(64), nullable=True, index=True)
    source_video_size_bytes = Column(Integer, nullable=True)

    video_job = relationship("VideoJob", back_populates="frame_extraction_results")
    visual_evidence_snapshots = relationship(
        "VisualEvidenceSnapshot",
        back_populates="frame_extraction_result",
        cascade="all, delete-orphan",
    )


class VisualEvidenceSnapshot(Base):
    """Immutable CV/OCR evidence bound to one exact extraction and source video."""

    __tablename__ = "visual_evidence_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "frame_extraction_result_id",
            "frame_manifest_sha256",
            "policy_sha256",
            "report_sha256",
            name="uq_visual_evidence_extraction_manifest_policy_report",
        ),
        CheckConstraint(
            "status IN ('passed', 'blocked')",
            name="ck_visual_evidence_snapshot_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    frame_extraction_result_id = Column(
        Integer,
        ForeignKey("frame_extraction_results.id"),
        nullable=False,
        index=True,
    )
    source_video_sha256 = Column(String(64), nullable=False, index=True)
    frame_manifest_sha256 = Column(String(64), nullable=False, index=True)
    policy_sha256 = Column(String(64), nullable=False, index=True)
    # Fingerprints the complete deterministic report envelope, including OCR
    # references/expected tokens and the evidence algorithm version.
    report_sha256 = Column(String(64), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    report_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    video_job = relationship("VideoJob")
    frame_extraction_result = relationship(
        "FrameExtractionResult",
        back_populates="visual_evidence_snapshots",
    )


class VideoOutputAcceptance(Base, TimestampMixin):
    __tablename__ = "video_output_acceptances"

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=False, index=True)
    director_prompt_pack_id = Column(Integer, ForeignKey("director_prompt_packs.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="needs_human_review", index=True)
    product_identity_status = Column(String(80), nullable=False, default="needs_review", index=True)
    packaging_status = Column(String(80), nullable=False, default="needs_review", index=True)
    geometry_status = Column(String(80), nullable=False, default="needs_review", index=True)
    blogger_authenticity_status = Column(String(80), nullable=False, default="needs_review", index=True)
    scene_match_status = Column(String(80), nullable=False, default="needs_review", index=True)
    proof_moment_status = Column(String(80), nullable=False, default="needs_review", index=True)
    cta_status = Column(String(80), nullable=False, default="needs_review", index=True)
    publishing_readiness = Column(String(80), nullable=False, default="blocked", index=True)
    score = Column(Float, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)
    contact_sheet_path = Column(String(500), nullable=True)
    keyframes_json = Column(JSON, default=list, nullable=False)
    visual_evidence_snapshot_id = Column(
        Integer,
        ForeignKey(
            "visual_evidence_snapshots.id",
            name="fk_video_output_acceptance_visual_evidence_snapshot",
        ),
        nullable=True,
        index=True,
    )
    reviewer_notes = Column(Text, nullable=True)

    video_job = relationship("VideoJob", back_populates="output_acceptances")
    ai_production_brief = relationship("AIProductionBrief")
    director_prompt_pack = relationship("DirectorPromptPack")
    visual_evidence_snapshot = relationship("VisualEvidenceSnapshot")


@event.listens_for(VisualEvidenceSnapshot, "before_update")
def _prevent_visual_evidence_update(_mapper, _connection, _target) -> None:
    raise ValueError("Visual evidence snapshots are append-only and cannot be updated.")


@event.listens_for(VisualEvidenceSnapshot, "before_delete")
def _prevent_visual_evidence_delete(_mapper, _connection, _target) -> None:
    raise ValueError("Visual evidence snapshots are append-only and cannot be deleted.")


class OneVideoRenderPlan(Base, TimestampMixin):
    __tablename__ = "one_video_render_plans"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    platform = Column(String(120), nullable=False, default="Instagram Reels", index=True)
    aspect_ratio = Column(String(20), nullable=False, default="9:16")
    duration_seconds = Column(Integer, nullable=False, default=15)
    provider = Column(String(120), nullable=False, default="runway")
    status = Column(String(80), nullable=False, default="plan_ready", index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=True, index=True)
    director_prompt_pack_id = Column(Integer, ForeignKey("director_prompt_packs.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    video_generation_variant_id = Column(Integer, ForeignKey("video_generation_variants.id"), nullable=True, index=True)
    product_scene_policy_json = Column(JSON, default=dict, nullable=False)
    scene_plan_json = Column(JSON, default=list, nullable=False)
    prompt_preview_json = Column(JSON, default=dict, nullable=False)
    negative_prompt = Column(Text, nullable=True)
    acceptance_checklist_json = Column(JSON, default=list, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product")
    creative_spec = relationship("VideoCreativeSpecRecord")
    creative_variant = relationship("CreativeVariant")
    ai_production_brief = relationship("AIProductionBrief")
    director_prompt_pack = relationship("DirectorPromptPack")
    prompt_pack = relationship("PromptPack")
    video_generation_variant = relationship("VideoGenerationVariant")
    results = relationship("OneVideoRenderResult", back_populates="plan", cascade="all, delete-orphan")


class OneVideoRenderResult(Base, TimestampMixin):
    __tablename__ = "one_video_render_results"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("one_video_render_plans.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    video_generation_variant_id = Column(Integer, ForeignKey("video_generation_variants.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    output_acceptance_id = Column(Integer, ForeignKey("video_output_acceptances.id"), nullable=True, index=True)
    provider = Column(String(120), nullable=False, default="runway")
    status = Column(String(80), nullable=False, default="created", index=True)
    max_scenes = Column(Integer, nullable=False, default=1)
    provider_job_ids_json = Column(JSON, default=list, nullable=False)
    local_output_paths_json = Column(JSON, default=list, nullable=False)
    final_video_path = Column(String(500), nullable=True)
    generation_report_path = Column(String(500), nullable=True)
    human_review_status = Column(String(80), nullable=False, default="needs_human_review", index=True)
    human_review_notes = Column(Text, nullable=True)
    result_json = Column(JSON, default=dict, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    plan = relationship("OneVideoRenderPlan", back_populates="results")
    product = relationship("Product")
    creative_variant = relationship("CreativeVariant")
    video_generation_variant = relationship("VideoGenerationVariant")
    prompt_pack = relationship("PromptPack")
    video_job = relationship("VideoJob")
    output_acceptance = relationship("VideoOutputAcceptance")


class SmokeReadinessRun(Base, TimestampMixin):
    __tablename__ = "smoke_readiness_runs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(120), nullable=False, default="started", index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    one_video_render_plan_id = Column(Integer, ForeignKey("one_video_render_plans.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    engine_audit_run_id = Column(Integer, ForeignKey("engine_audit_runs.id"), nullable=True, index=True)
    control_room_snapshot_id = Column(Integer, ForeignKey("control_room_snapshots.id"), nullable=True, index=True)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)
    report_json = Column(JSON, default=dict, nullable=False)

    product = relationship("Product")
    one_video_render_plan = relationship("OneVideoRenderPlan")
    prompt_pack = relationship("PromptPack")
    engine_audit_run = relationship("EngineAuditRun")
    control_room_snapshot = relationship("ControlRoomSnapshot")
    blockers = relationship("SmokeReadinessBlocker", back_populates="run", cascade="all, delete-orphan")


class SmokeReadinessBlocker(Base, TimestampMixin):
    __tablename__ = "smoke_readiness_blockers"

    id = Column(Integer, primary_key=True, index=True)
    smoke_readiness_run_id = Column(Integer, ForeignKey("smoke_readiness_runs.id"), nullable=False, index=True)
    blocker_type = Column(String(120), nullable=False, index=True)
    severity = Column(String(40), nullable=False, default="blocker", index=True)
    message = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)

    run = relationship("SmokeReadinessRun", back_populates="blockers")


class SceneRegenerationRequest(Base, TimestampMixin):
    __tablename__ = "scene_regeneration_requests"

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    video_generation_variant_id = Column(Integer, ForeignKey("video_generation_variants.id"), nullable=False, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=False, index=True)
    scene_number = Column(Integer, nullable=False, index=True)
    reason = Column(String(120), nullable=False, index=True)
    feedback = Column(Text, nullable=False)
    status = Column(String(80), nullable=False, default="requested", index=True)
    request_json = Column(JSON, default=dict, nullable=False)
    prompt_only_output_json = Column(JSON, default=dict, nullable=False)

    video_job = relationship("VideoJob")
    generation_variant = relationship("VideoGenerationVariant", back_populates="regeneration_requests")
    creative_spec = relationship("VideoCreativeSpecRecord")


class ContentAgentProfile(Base, TimestampMixin):
    __tablename__ = "content_agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    agent_key = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False)
    agent_type = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    provider = Column(String(120), nullable=False, default="rules")
    model_name = Column(String(160), nullable=True)
    capabilities_json = Column(JSON, default=list, nullable=False)
    config_json = Column(JSON, default=dict, nullable=False)
    notes = Column(Text, nullable=True)

    assignments = relationship("ContentAssignment", back_populates="agent_profile")


class ContentRun(Base, TimestampMixin):
    __tablename__ = "content_runs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False, default=15)
    variant_count = Column(Integer, nullable=False, default=5)
    status = Column(String(80), nullable=False, default="created", index=True)
    demand_hypothesis_id = Column(Integer, ForeignKey("demand_hypothesis_records.id"), nullable=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=True, index=True)
    asset_kit_id = Column(Integer, ForeignKey("product_asset_kits.id"), nullable=True, index=True)
    creative_variant_set_id = Column(Integer, ForeignKey("creative_variant_sets.id"), nullable=True, index=True)
    selected_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    generation_variant_id = Column(Integer, ForeignKey("video_generation_variants.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    latest_ai_review_id = Column(Integer, nullable=True, index=True)
    run_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    product = relationship("Product", back_populates="content_runs")
    demand_hypothesis = relationship("DemandHypothesisRecord")
    creative_spec = relationship("VideoCreativeSpecRecord")
    asset_kit = relationship("ProductAssetKit")
    creative_variant_set = relationship("CreativeVariantSet")
    selected_variant = relationship("CreativeVariant")
    generation_variant = relationship("VideoGenerationVariant")
    prompt_pack = relationship("PromptPack")
    video_job = relationship("VideoJob")
    assignments = relationship("ContentAssignment", back_populates="content_run", cascade="all, delete-orphan")
    ai_reviews = relationship("AIContentReview", back_populates="content_run", cascade="all, delete-orphan")
    performance_metrics = relationship("ContentPerformanceMetric", back_populates="content_run")


class ContentAssignment(Base, TimestampMixin):
    __tablename__ = "content_assignments"

    id = Column(Integer, primary_key=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=False, index=True)
    agent_profile_id = Column(Integer, ForeignKey("content_agent_profiles.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    assignment_type = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="pending", index=True)
    input_json = Column(JSON, default=dict, nullable=False)
    output_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    content_run = relationship("ContentRun", back_populates="assignments")
    agent_profile = relationship("ContentAgentProfile", back_populates="assignments")
    product = relationship("Product")


class AIContentReview(Base, TimestampMixin):
    __tablename__ = "ai_content_reviews"

    id = Column(Integer, primary_key=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="needs_human_review", index=True)
    score = Column(Float, nullable=False, default=0)
    human_review_required = Column(Boolean, default=True, nullable=False)
    review_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    content_run = relationship("ContentRun", back_populates="ai_reviews")


class ContentPerformanceMetric(Base):
    __tablename__ = "content_performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    platform = Column(String(120), nullable=False, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    metric_date = Column(Date, nullable=True, index=True)
    impressions = Column(Integer, nullable=True)
    views = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    spend = Column(Float, nullable=True)
    ctr = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    watch_time_seconds = Column(Float, nullable=True)
    retention_rate = Column(Float, nullable=True)
    status = Column(String(80), nullable=False, default="imported", index=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    content_run = relationship("ContentRun", back_populates="performance_metrics")
    product = relationship("Product")
    creative_variant = relationship("CreativeVariant")
    video_job = relationship("VideoJob")


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    brand = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    source_type = Column(String(80), nullable=False, default="manual_selection", index=True)
    product_ids_json = Column(JSON, default=list, nullable=False)
    target_video_count = Column(Integer, nullable=False, default=350)
    target_destination_count = Column(Integer, nullable=False, default=120)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    strategy_json = Column(JSON, default=dict, nullable=False)
    summary_json = Column(JSON, default=dict, nullable=False)

    products = relationship("CampaignProduct", back_populates="campaign", cascade="all, delete-orphan")
    runs = relationship("CampaignRun", back_populates="campaign", cascade="all, delete-orphan")
    distribution_plans = relationship("CampaignDistributionPlan", back_populates="campaign", cascade="all, delete-orphan")
    execution_snapshots = relationship("CampaignExecutionSnapshot", back_populates="campaign", cascade="all, delete-orphan")
    action_queue_items = relationship("CampaignActionQueueItem", back_populates="campaign", cascade="all, delete-orphan")
    batch_runs = relationship("CampaignBatchRun", back_populates="campaign", cascade="all, delete-orphan")
    performance_imports = relationship("CampaignPerformanceImport", back_populates="campaign", cascade="all, delete-orphan")
    performance_metrics = relationship("CampaignPerformanceMetric", back_populates="campaign", cascade="all, delete-orphan")
    performance_scores = relationship("CampaignPerformanceScore", back_populates="campaign", cascade="all, delete-orphan")
    scaling_recommendations = relationship("CampaignScalingRecommendation", back_populates="campaign", cascade="all, delete-orphan")


class CampaignProduct(Base, TimestampMixin):
    __tablename__ = "campaign_products"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    target_video_count = Column(Integer, nullable=False, default=0)
    target_prompt_count = Column(Integer, nullable=False, default=0)
    target_real_smoke_count = Column(Integer, nullable=False, default=0)
    content_run_ids_json = Column(JSON, default=list, nullable=False)
    approved_video_count = Column(Integer, nullable=False, default=0)
    prompt_ready_count = Column(Integer, nullable=False, default=0)
    blocked_count = Column(Integer, nullable=False, default=0)
    needs_review_count = Column(Integer, nullable=False, default=0)
    status = Column(String(80), nullable=False, default="planned", index=True)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign", back_populates="products")
    product = relationship("Product")


class CampaignRun(Base, TimestampMixin):
    __tablename__ = "campaign_runs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="created", index=True)
    total_products = Column(Integer, nullable=False, default=0)
    total_target_videos = Column(Integer, nullable=False, default=0)
    total_content_runs = Column(Integer, nullable=False, default=0)
    total_prompt_ready = Column(Integer, nullable=False, default=0)
    total_real_smoke_ready = Column(Integer, nullable=False, default=0)
    total_needs_review = Column(Integer, nullable=False, default=0)
    total_blocked = Column(Integer, nullable=False, default=0)
    total_approved = Column(Integer, nullable=False, default=0)
    total_publishing_ready = Column(Integer, nullable=False, default=0)
    summary_json = Column(JSON, default=dict, nullable=False)

    campaign = relationship("Campaign", back_populates="runs")


class CampaignDistributionPlan(Base, TimestampMixin):
    __tablename__ = "campaign_distribution_plans"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="draft", index=True)
    target_destination_count = Column(Integer, nullable=False, default=0)
    destination_ids_json = Column(JSON, default=list, nullable=False)
    publishing_package_ids_json = Column(JSON, default=list, nullable=False)
    total_slots = Column(Integer, nullable=False, default=0)
    scheduled_slots = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    plan_json = Column(JSON, default=dict, nullable=False)

    campaign = relationship("Campaign", back_populates="distribution_plans")


class ProductMatrixImport(Base, TimestampMixin):
    __tablename__ = "product_matrix_imports"

    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String(500), nullable=False)
    status = Column(String(80), nullable=False, default="imported", index=True)
    imported_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    warnings_json = Column(JSON, default=list, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)

    rows = relationship("ProductMatrixRow", back_populates="matrix_import", cascade="all, delete-orphan")


class ProductMatrixRow(Base, TimestampMixin):
    __tablename__ = "product_matrix_rows"

    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("product_matrix_imports.id"), nullable=False, index=True)
    sku = Column(String(120), nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    category = Column(String(120), nullable=True, index=True)
    price = Column(Float, nullable=True)
    stock_qty = Column(Integer, nullable=True)
    product_url = Column(String(500), nullable=True)
    photo_urls_json = Column(JSON, default=list, nullable=False)
    priority = Column(Integer, nullable=False, default=1)
    raw_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(80), nullable=False, default="imported", index=True)
    warnings_json = Column(JSON, default=list, nullable=False)

    matrix_import = relationship("ProductMatrixImport", back_populates="rows")


class DestinationSetupPack(Base, TimestampMixin):
    __tablename__ = "destination_setup_packs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    destination_type = Column(String(120), nullable=False, default="owned_media", index=True)
    platform = Column(String(120), nullable=False, default="Instagram Reels", index=True)
    suggested_name = Column(String(160), nullable=False)
    suggested_handle = Column(String(160), nullable=False)
    bio_text = Column(Text, nullable=True)
    avatar_asset_path = Column(String(500), nullable=True)
    content_pillars_json = Column(JSON, default=list, nullable=False)
    first_posts_json = Column(JSON, default=list, nullable=False)
    setup_checklist_json = Column(JSON, default=list, nullable=False)
    status = Column(String(80), nullable=False, default="needs_manual_setup", index=True)

    campaign = relationship("Campaign")
    product = relationship("Product")


class CampaignExecutionSnapshot(Base, TimestampMixin):
    __tablename__ = "campaign_execution_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="created", index=True)
    total_sku = Column(Integer, nullable=False, default=0)
    ready_sku = Column(Integer, nullable=False, default=0)
    blocked_sku = Column(Integer, nullable=False, default=0)
    prompt_ready_count = Column(Integer, nullable=False, default=0)
    real_smoke_ready_count = Column(Integer, nullable=False, default=0)
    needs_review_count = Column(Integer, nullable=False, default=0)
    approved_video_count = Column(Integer, nullable=False, default=0)
    publishing_package_ready_count = Column(Integer, nullable=False, default=0)
    distribution_task_ready_count = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign", back_populates="execution_snapshots")


class LaunchReadinessSnapshot(Base, TimestampMixin):
    __tablename__ = "launch_readiness_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    total_sku = Column(Integer, nullable=False, default=0)
    target_videos = Column(Integer, nullable=False, default=0)
    target_destinations = Column(Integer, nullable=False, default=0)
    prompt_ready_count = Column(Integer, nullable=False, default=0)
    real_video_count = Column(Integer, nullable=False, default=0)
    approved_video_count = Column(Integer, nullable=False, default=0)
    needs_human_review_count = Column(Integer, nullable=False, default=0)
    needs_regeneration_count = Column(Integer, nullable=False, default=0)
    publishing_package_ready_count = Column(Integer, nullable=False, default=0)
    destination_total = Column(Integer, nullable=False, default=0)
    destination_active_count = Column(Integer, nullable=False, default=0)
    destination_capacity_total = Column(Integer, nullable=False, default=0)
    distribution_task_ready_count = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign")


class LaunchQualityGate(Base, TimestampMixin):
    __tablename__ = "launch_quality_gates"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    quality_review_status = Column(String(80), nullable=False, default="missing", index=True)
    human_visual_status = Column(String(80), nullable=False, default="needs_review", index=True)
    product_identity_status = Column(String(80), nullable=False, default="unknown", index=True)
    geometry_status = Column(String(80), nullable=False, default="unknown", index=True)
    publishing_allowed = Column(Boolean, default=False, nullable=False, index=True)
    blockers_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign")
    video_job = relationship("VideoJob")
    creative_variant = relationship("CreativeVariant")
    product = relationship("Product")


class DestinationCapacitySnapshot(Base, TimestampMixin):
    __tablename__ = "destination_capacity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    total_destinations = Column(Integer, nullable=False, default=0)
    active_destinations = Column(Integer, nullable=False, default=0)
    manual_destinations = Column(Integer, nullable=False, default=0)
    api_ready_destinations = Column(Integer, nullable=False, default=0)
    daily_capacity = Column(Integer, nullable=False, default=0)
    weekly_capacity = Column(Integer, nullable=False, default=0)
    required_slots = Column(Integer, nullable=False, default=0)
    capacity_gap = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign")


class DestinationControlSnapshot(Base, TimestampMixin):
    __tablename__ = "destination_control_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    total_destinations = Column(Integer, nullable=False, default=0)
    setup_needed_count = Column(Integer, nullable=False, default=0)
    ready_count = Column(Integer, nullable=False, default=0)
    connected_count = Column(Integer, nullable=False, default=0)
    metrics_synced_count = Column(Integer, nullable=False, default=0)
    no_metrics_count = Column(Integer, nullable=False, default=0)
    low_performance_count = Column(Integer, nullable=False, default=0)
    paused_count = Column(Integer, nullable=False, default=0)
    capacity_total = Column(Integer, nullable=False, default=0)
    capacity_used = Column(Integer, nullable=False, default=0)
    capacity_gap = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign")
    rows = relationship("DestinationControlRow", back_populates="snapshot", cascade="all, delete-orphan")


class DestinationControlRow(Base, TimestampMixin):
    __tablename__ = "destination_control_rows"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("destination_control_snapshots.id"), nullable=False, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    platform = Column(String(120), nullable=False, index=True)
    name = Column(String(160), nullable=True)
    handle = Column(String(160), nullable=True)
    setup_status = Column(String(80), nullable=False, default="unknown", index=True)
    readiness_status = Column(String(80), nullable=False, default="unknown", index=True)
    connection_status = Column(String(80), nullable=False, default="unknown", index=True)
    publishing_status = Column(String(80), nullable=False, default="unknown", index=True)
    metrics_status = Column(String(80), nullable=False, default="unknown", index=True)
    performance_status = Column(String(80), nullable=False, default="unknown", index=True)
    warmup_phase = Column(String(80), nullable=True)
    daily_capacity_remaining = Column(Integer, nullable=False, default=0)
    weekly_capacity_remaining = Column(Integer, nullable=False, default=0)
    last_post_url = Column(String(500), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_action = Column(String(120), nullable=True, index=True)

    snapshot = relationship("DestinationControlSnapshot", back_populates="rows")
    destination = relationship("PublishingDestination")


class ParticipantProfile(Base, TimestampMixin):
    __tablename__ = "participant_profiles"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String(160), nullable=False, index=True)
    role = Column(String(80), nullable=False, default="creator", index=True)
    email = Column(String(255), nullable=True, index=True)
    telegram_handle = Column(String(160), nullable=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    platforms_json = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)

    destination_links = relationship("ParticipantDestinationLink", back_populates="participant", cascade="all, delete-orphan")
    assignments = relationship("ParticipantAssignment", back_populates="participant", cascade="all, delete-orphan")
    submissions = relationship("ParticipantSubmission", back_populates="participant", cascade="all, delete-orphan")
    payout_entries = relationship("PayoutLedgerEntry", back_populates="participant")
    training_attempts = relationship("TrainingAttempt", back_populates="participant", cascade="all, delete-orphan")
    certifications = relationship("ParticipantCertification", back_populates="participant", cascade="all, delete-orphan")


class TrainingCourse(Base, TimestampMixin):
    __tablename__ = "training_courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(120), unique=True, nullable=False, index=True)
    title = Column(String(160), nullable=False)
    role = Column(String(80), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    summary = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=100, index=True)
    learning_path_json = Column(JSON, default=list, nullable=False)
    checklist_json = Column(JSON, default=list, nullable=False)

    lessons = relationship("TrainingLesson", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("TrainingQuiz", back_populates="course", cascade="all, delete-orphan")
    attempts = relationship("TrainingAttempt", back_populates="course", cascade="all, delete-orphan")
    certifications = relationship("ParticipantCertification", back_populates="course", cascade="all, delete-orphan")


class TrainingLesson(Base, TimestampMixin):
    __tablename__ = "training_lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False, index=True)
    code = Column(String(120), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    body = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=100, index=True)
    checklist_json = Column(JSON, default=list, nullable=False)
    examples_json = Column(JSON, default=list, nullable=False)

    course = relationship("TrainingCourse", back_populates="lessons")


class TrainingQuiz(Base, TimestampMixin):
    __tablename__ = "training_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False, index=True)
    code = Column(String(120), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    passing_score = Column(Float, nullable=False, default=0.8)
    questions_json = Column(JSON, default=list, nullable=False)

    course = relationship("TrainingCourse", back_populates="quizzes")
    attempts = relationship("TrainingAttempt", back_populates="quiz", cascade="all, delete-orphan")


class TrainingAttempt(Base, TimestampMixin):
    __tablename__ = "training_attempts"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False, index=True)
    quiz_id = Column(Integer, ForeignKey("training_quizzes.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="started", index=True)
    score = Column(Float, nullable=False, default=0)
    passed = Column(Boolean, default=False, nullable=False, index=True)
    answers_json = Column(JSON, default=dict, nullable=False)
    result_json = Column(JSON, default=dict, nullable=False)

    participant = relationship("ParticipantProfile", back_populates="training_attempts")
    course = relationship("TrainingCourse", back_populates="attempts")
    quiz = relationship("TrainingQuiz", back_populates="attempts")


class ParticipantCertification(Base, TimestampMixin):
    __tablename__ = "participant_certifications"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("training_courses.id"), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey("training_attempts.id"), nullable=True, index=True)
    course_code = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="certified", index=True)
    issued_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    participant = relationship("ParticipantProfile", back_populates="certifications")
    course = relationship("TrainingCourse", back_populates="certifications")
    attempt = relationship("TrainingAttempt")


class ParticipantDestinationLink(Base, TimestampMixin):
    __tablename__ = "participant_destination_links"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    relationship_type = Column(String(80), nullable=False, default="creator", index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    permissions_json = Column(JSON, default=list, nullable=False)

    participant = relationship("ParticipantProfile", back_populates="destination_links")
    destination = relationship("PublishingDestination")


class ParticipantAssignment(Base, TimestampMixin):
    __tablename__ = "participant_assignments"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=True, index=True)
    creative_spec_id = Column(Integer, ForeignKey("video_creative_spec_records.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    prompt_pack_id = Column(Integer, ForeignKey("prompt_packs.id"), nullable=True, index=True)
    publishing_package_id = Column(Integer, ForeignKey("publishing_packages.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    assignment_type = Column(String(120), nullable=False, default="create_video", index=True)
    status = Column(String(80), nullable=False, default="assigned", index=True)
    priority = Column(Integer, nullable=False, default=5, index=True)
    due_at = Column(DateTime, nullable=True, index=True)
    brief_json = Column(JSON, default=dict, nullable=False)
    payout_rule_id = Column(Integer, ForeignKey("payout_rules.id"), nullable=True, index=True)

    participant = relationship("ParticipantProfile", back_populates="assignments")
    campaign = relationship("Campaign")
    product = relationship("Product")
    content_run = relationship("ContentRun")
    creative_spec = relationship("VideoCreativeSpecRecord")
    creative_variant = relationship("CreativeVariant")
    prompt_pack = relationship("PromptPack")
    publishing_package = relationship("PublishingPackage")
    publishing_task = relationship("PublishingTask")
    payout_rule = relationship("PayoutRule")
    submissions = relationship("ParticipantSubmission", back_populates="assignment", cascade="all, delete-orphan")


class ParticipantSubmission(Base, TimestampMixin):
    __tablename__ = "participant_submissions"

    id = Column(Integer, primary_key=True, index=True)
    participant_assignment_id = Column(Integer, ForeignKey("participant_assignments.id"), nullable=False, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    file_path = Column(String(500), nullable=True)
    external_url = Column(String(500), nullable=True)
    final_post_url = Column(String(500), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="submitted", index=True)
    review_status = Column(String(80), nullable=False, default="needs_review", index=True)
    review_notes = Column(Text, nullable=True)

    assignment = relationship("ParticipantAssignment", back_populates="submissions")
    participant = relationship("ParticipantProfile", back_populates="submissions")
    video_job = relationship("VideoJob")


class PayoutRule(Base, TimestampMixin):
    __tablename__ = "payout_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False, index=True)
    payout_type = Column(String(80), nullable=False, default="per_video", index=True)
    amount_fixed = Column(Float, nullable=True)
    currency = Column(String(20), nullable=False, default="RUB")
    percent_revenue = Column(Float, nullable=True)
    conditions_json = Column(JSON, default=dict, nullable=False)


class PayoutLedgerEntry(Base, TimestampMixin):
    __tablename__ = "payout_ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("participant_assignments.id"), nullable=True, index=True)
    submission_id = Column(Integer, ForeignKey("participant_submissions.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    payout_rule_id = Column(Integer, ForeignKey("payout_rules.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False, default=0)
    currency = Column(String(20), nullable=False, default="RUB")
    status = Column(String(80), nullable=False, default="pending", index=True)
    reason = Column(Text, nullable=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)

    participant = relationship("ParticipantProfile", back_populates="payout_entries")
    assignment = relationship("ParticipantAssignment")
    submission = relationship("ParticipantSubmission")
    publishing_task = relationship("PublishingTask")
    campaign = relationship("Campaign")
    payout_rule = relationship("PayoutRule")


class ParticipantMetricSnapshot(Base):
    __tablename__ = "participant_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participant_profiles.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    assignments_total = Column(Integer, nullable=False, default=0)
    submitted_total = Column(Integer, nullable=False, default=0)
    approved_total = Column(Integer, nullable=False, default=0)
    rejected_total = Column(Integer, nullable=False, default=0)
    published_total = Column(Integer, nullable=False, default=0)
    views_total = Column(Integer, nullable=False, default=0)
    clicks_total = Column(Integer, nullable=False, default=0)
    orders_total = Column(Integer, nullable=False, default=0)
    revenue_total = Column(Float, nullable=False, default=0)
    engagement_rate = Column(Float, nullable=True)
    approval_rate = Column(Float, nullable=True)
    payout_total = Column(Float, nullable=False, default=0)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    participant = relationship("ParticipantProfile")
    campaign = relationship("Campaign")


class DestinationSetupRequirement(Base, TimestampMixin):
    __tablename__ = "destination_setup_requirements"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, default="Instagram Reels", index=True)
    required_count = Column(Integer, nullable=False, default=0)
    existing_ready_count = Column(Integer, nullable=False, default=0)
    capacity_gap = Column(Integer, nullable=False, default=0)
    reason = Column(String(160), nullable=False, default="capacity_gap", index=True)
    status = Column(String(80), nullable=False, default="open", index=True)

    campaign = relationship("Campaign")


class DestinationProfilePack(Base, TimestampMixin):
    __tablename__ = "destination_profile_packs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, default="Instagram Reels", index=True)
    sku_focus_json = Column(JSON, default=list, nullable=False)
    theme = Column(String(160), nullable=False)
    suggested_name = Column(String(160), nullable=False)
    suggested_handle = Column(String(160), nullable=False)
    bio_text = Column(Text, nullable=True)
    avatar_prompt = Column(Text, nullable=True)
    avatar_asset_path = Column(String(500), nullable=True)
    content_pillars_json = Column(JSON, default=list, nullable=False)
    first_posts_json = Column(JSON, default=list, nullable=False)
    posting_rules_json = Column(JSON, default=list, nullable=False)
    status = Column(String(80), nullable=False, default="draft", index=True)

    campaign = relationship("Campaign")


class DestinationSetupTask(Base, TimestampMixin):
    __tablename__ = "destination_setup_tasks"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    profile_pack_id = Column(Integer, ForeignKey("destination_profile_packs.id"), nullable=False, index=True)
    platform = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="needs_manual_setup", index=True)
    owner_name = Column(String(160), nullable=True)
    checklist_json = Column(JSON, default=list, nullable=False)
    final_account_url = Column(String(500), nullable=True)
    final_handle = Column(String(160), nullable=True)
    notes = Column(Text, nullable=True)

    campaign = relationship("Campaign")
    profile_pack = relationship("DestinationProfilePack")


class DestinationReadinessSnapshot(Base, TimestampMixin):
    __tablename__ = "destination_readiness_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    platform = Column(String(120), nullable=False, index=True)
    posting_mode = Column(String(80), nullable=False, index=True)
    auth_status = Column(String(80), nullable=False, index=True)
    active = Column(Boolean, default=False, nullable=False, index=True)
    manual_ready = Column(Boolean, default=False, nullable=False, index=True)
    api_ready = Column(Boolean, default=False, nullable=False, index=True)
    warmup_phase = Column(String(80), nullable=False, default="phase_2_regular", index=True)
    daily_limit = Column(Integer, nullable=False, default=0)
    weekly_limit = Column(Integer, nullable=False, default=0)
    used_today = Column(Integer, nullable=False, default=0)
    used_this_week = Column(Integer, nullable=False, default=0)
    remaining_daily_capacity = Column(Integer, nullable=False, default=0)
    remaining_weekly_capacity = Column(Integer, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    destination = relationship("PublishingDestination")
    campaign = relationship("Campaign")


class DestinationWarmupPlan(Base, TimestampMixin):
    __tablename__ = "destination_warmup_plans"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    start_date = Column(DateTime, default=utcnow, nullable=False)
    current_phase = Column(String(80), nullable=False, default="phase_1_soft_start", index=True)
    rules_json = Column(JSON, default=list, nullable=False)
    notes = Column(Text, nullable=True)

    destination = relationship("PublishingDestination")


class DestinationHealthCheck(Base, TimestampMixin):
    __tablename__ = "destination_health_checks"

    id = Column(Integer, primary_key=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="unknown", index=True)
    last_posted_at = Column(DateTime, nullable=True)
    last_final_url = Column(String(500), nullable=True)
    recent_task_count = Column(Integer, nullable=False, default=0)
    failed_task_count = Column(Integer, nullable=False, default=0)
    avg_views = Column(Float, nullable=False, default=0)
    avg_engagement_rate = Column(Float, nullable=False, default=0)
    blockers_json = Column(JSON, default=list, nullable=False)

    destination = relationship("PublishingDestination")


class EngineAuditReport(Base, TimestampMixin):
    __tablename__ = "engine_audit_reports"

    id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String(80), nullable=False, default="global", index=True)
    scope_id = Column(Integer, nullable=True, index=True)
    status = Column(String(80), nullable=False, default="needs_work", index=True)
    overall_score = Column(Float, nullable=False, default=0)
    score_scale = Column(String(40), nullable=False, default="1_to_10")
    dimensions_json = Column(JSON, default=list, nullable=False)
    reasons_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)
    road_to_10_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)
    evidence_json = Column(JSON, default=dict, nullable=False)
    report_path = Column(String(500), nullable=True)


class EngineAuditRun(Base, TimestampMixin):
    __tablename__ = "engine_audit_runs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(80), nullable=False, default="weak", index=True)
    scope_type = Column(String(80), nullable=False, default="global", index=True)
    scope_id = Column(Integer, nullable=True, index=True)
    total_score = Column(Float, nullable=False, default=0)
    scores_json = Column(JSON, default=list, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    recommendations_json = Column(JSON, default=list, nullable=False)

    scores = relationship("EngineAuditScore", back_populates="audit_run", cascade="all, delete-orphan")


class EngineAuditScore(Base, TimestampMixin):
    __tablename__ = "engine_audit_scores"

    id = Column(Integer, primary_key=True, index=True)
    audit_run_id = Column(Integer, ForeignKey("engine_audit_runs.id"), nullable=False, index=True)
    score_type = Column(String(120), nullable=False, index=True)
    score = Column(Float, nullable=False, default=0)
    status = Column(String(80), nullable=False, default="weak", index=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    required_fixes_json = Column(JSON, default=list, nullable=False)

    audit_run = relationship("EngineAuditRun", back_populates="scores")


class ControlRoomSnapshot(Base, TimestampMixin):
    __tablename__ = "control_room_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String(80), nullable=False, default="global", index=True)
    scope_id = Column(Integer, nullable=True, index=True)
    role = Column(String(80), nullable=False, default="owner", index=True)
    overall_status = Column(String(80), nullable=False, default="weak", index=True)
    engine_audit_run_id = Column(Integer, ForeignKey("engine_audit_runs.id"), nullable=True, index=True)
    summary_json = Column(JSON, default=dict, nullable=False)
    scorecard_json = Column(JSON, default=dict, nullable=False)
    ready_items_json = Column(JSON, default=list, nullable=False)
    blocked_items_json = Column(JSON, default=list, nullable=False)
    review_queue_json = Column(JSON, default=list, nullable=False)
    safe_actions_json = Column(JSON, default=list, nullable=False)
    gated_actions_json = Column(JSON, default=list, nullable=False)
    next_actions_json = Column(JSON, default=list, nullable=False)

    engine_audit_run = relationship("EngineAuditRun")
    actions = relationship("ControlRoomAction", back_populates="snapshot", cascade="all, delete-orphan")


class ControlRoomAction(Base, TimestampMixin):
    __tablename__ = "control_room_actions"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("control_room_snapshots.id"), nullable=False, index=True)
    action_type = Column(String(120), nullable=False, index=True)
    role = Column(String(80), nullable=False, index=True)
    target_module = Column(String(120), nullable=False, index=True)
    target_url = Column(String(500), nullable=False)
    status = Column(String(80), nullable=False, default="open", index=True)
    safe_to_execute = Column(Boolean, default=True, nullable=False)
    requires_human = Column(Boolean, default=True, nullable=False)
    requires_spend_gate = Column(Boolean, default=False, nullable=False)
    reason = Column(Text, nullable=True)
    payload_json = Column(JSON, default=dict, nullable=False)

    snapshot = relationship("ControlRoomSnapshot", back_populates="actions")


class MVPWorkspaceSnapshot(Base, TimestampMixin):
    __tablename__ = "mvp_workspace_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    role = Column(String(80), nullable=False, default="owner", index=True)
    status = Column(String(80), nullable=False, default="needs_attention", index=True)
    current_step = Column(String(120), nullable=False, default="review_workspace", index=True)
    primary_action_json = Column(JSON, default=dict, nullable=False)
    secondary_actions_json = Column(JSON, default=list, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    module_links_json = Column(JSON, default=list, nullable=False)
    context_json = Column(JSON, default=dict, nullable=False)
    control_room_snapshot_id = Column(Integer, ForeignKey("control_room_snapshots.id"), nullable=True, index=True)
    smoke_readiness_run_id = Column(Integer, ForeignKey("smoke_readiness_runs.id"), nullable=True, index=True)

    control_room_snapshot = relationship("ControlRoomSnapshot")
    smoke_readiness_run = relationship("SmokeReadinessRun", foreign_keys=[smoke_readiness_run_id])


class MVPLaunchRun(Base, TimestampMixin):
    __tablename__ = "mvp_launch_runs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="started", index=True)
    current_step = Column(String(120), nullable=False, default="select_product", index=True)
    completed_steps_json = Column(JSON, default=list, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    next_action_json = Column(JSON, default=dict, nullable=False)
    context_json = Column(JSON, default=dict, nullable=False)
    one_video_render_plan_id = Column(Integer, ForeignKey("one_video_render_plans.id"), nullable=True, index=True)
    smoke_readiness_run_id = Column(Integer, ForeignKey("smoke_readiness_runs.id"), nullable=True, index=True)
    one_video_render_result_id = Column(Integer, ForeignKey("one_video_render_results.id"), nullable=True, index=True)
    output_acceptance_id = Column(Integer, ForeignKey("video_output_acceptances.id"), nullable=True, index=True)

    product = relationship("Product")
    one_video_render_plan = relationship("OneVideoRenderPlan")
    smoke_readiness_run = relationship("SmokeReadinessRun", foreign_keys=[smoke_readiness_run_id])
    one_video_render_result = relationship("OneVideoRenderResult")
    output_acceptance = relationship("VideoOutputAcceptance")


class ProductUGCRecipeDraft(Base, TimestampMixin):
    __tablename__ = "product_ugc_recipe_drafts"
    # See ProductAsset: the production FK is real and named, while SQLite ORM
    # fixtures remain droppable with PRAGMA foreign_keys=ON.
    __table_args__ = (
        ForeignKeyConstraint(
            ["character_media_artifact_id"],
            ["media_artifacts.id"],
            name="fk_ugc_drafts_character_artifact",
            use_alter=True,
        ).ddl_if(dialect=("postgresql",)),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    assigned_to_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=False, index=True)
    variant_key = Column(String(160), nullable=True, index=True)
    status = Column(String(80), nullable=False, default="blocked", index=True)
    recipe_version = Column(String(40), nullable=False, default="2026-06")
    platform = Column(String(120), nullable=False, default="Instagram Reels")
    language = Column(String(20), nullable=False, default="ru")
    # Development/test drafts may still point at an isolated local file.  A
    # production draft instead references a private immutable MediaArtifact;
    # no signed object URL is ever persisted here.
    character_image_path = Column(String(1000), nullable=True)
    character_media_artifact_id = Column(
        Integer,
        nullable=True,
        index=True,
    )
    character_image_filename = Column(String(255), nullable=False)
    likeness_consent = Column(Boolean, default=False, nullable=False)
    exact_variant_confirmed = Column(Boolean, default=False, nullable=False)
    product_asset_ids_json = Column(JSON, default=list, nullable=False)
    primary_product_asset_id = Column(Integer, ForeignKey("product_assets.id"), nullable=True, index=True)
    product_info = Column(Text, nullable=False)
    user_concept = Column(Text, nullable=False)
    creative_inputs_json = Column(JSON, default=dict, nullable=False)
    duration_seconds = Column(Integer, nullable=False, default=15)
    ratio = Column(String(20), nullable=False, default="720:1280")
    audio_enabled = Column(Boolean, default=True, nullable=False)
    estimated_credits = Column(Integer, nullable=False, default=0)
    provider_payload_preview_json = Column(JSON, default=dict, nullable=False)
    blockers_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    provider_task_id = Column(String(255), nullable=True, index=True)
    provider_status = Column(String(80), nullable=True, index=True)
    local_output_paths_json = Column(JSON, default=list, nullable=False)
    generation_report_path = Column(String(1000), nullable=True)
    human_review_status = Column(String(80), nullable=False, default="not_generated", index=True)
    publishing_readiness = Column(String(80), nullable=False, default="blocked", index=True)
    human_review_notes = Column(Text, nullable=True)

    product = relationship("Product")
    primary_product_asset = relationship("ProductAsset", foreign_keys=[primary_product_asset_id])
    character_media_artifact = relationship(
        "MediaArtifact",
        foreign_keys=[character_media_artifact_id],
    )
    generation_job = relationship(
        "ProductUGCGenerationJob",
        back_populates="draft",
        uselist=False,
    )


class ProductUGCGenerationJob(Base, TimestampMixin):
    """Durable, at-most-once paid provider work for one Product UGC draft.

    A draft has one immutable provider-spend identity. Retries happen on this
    same row and, after a provider task id is known, can only poll/download the
    existing provider task. A spend guard without a provider task id is an
    ambiguous external-submit outcome and must be quarantined, never submitted
    again automatically.
    """

    __tablename__ = "product_ugc_generation_jobs"
    __table_args__ = (
        UniqueConstraint("draft_id", name="uq_product_ugc_generation_job_draft"),
        UniqueConstraint("idempotency_key", name="uq_product_ugc_generation_job_idempotency"),
        UniqueConstraint(
            "provider",
            "provider_task_id",
            name="uq_product_ugc_generation_job_provider_task",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_product_ugc_generation_attempt_nonnegative"),
        CheckConstraint("max_attempts >= 1", name="ck_product_ugc_generation_max_attempt_positive"),
        CheckConstraint(
            "status IN ("
            "'queued', 'leased', 'provider_launching', 'provider_processing', "
            "'downloading', 'retry_wait', 'succeeded', 'failed_terminal', 'quarantined'"
            ")",
            name="ck_product_ugc_generation_status",
        ),
        Index(
            "ix_product_ugc_generation_ready",
            "status",
            "next_attempt_at",
            "lease_expires_at",
        ),
        Index(
            "ix_product_ugc_generation_org_status",
            "organization_id",
            "status",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("product_ugc_recipe_drafts.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    requested_by_user_profile_id = Column(
        Integer,
        ForeignKey("user_profiles.id"),
        nullable=True,
        index=True,
    )
    idempotency_key = Column(String(200), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="queued", index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    next_attempt_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    lease_owner = Column(String(255), nullable=True, index=True)
    lease_token = Column(String(160), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    heartbeat_at = Column(DateTime, nullable=True)

    provider = Column(String(120), nullable=False, default="runway_product_ugc_recipe", index=True)
    provider_task_id = Column(String(255), nullable=True, index=True)
    provider_status = Column(String(80), nullable=True, index=True)
    spend_guarded_at = Column(DateTime, nullable=True, index=True)
    provider_submitted_at = Column(DateTime, nullable=True)

    last_error_code = Column(String(120), nullable=True, index=True)
    last_error_message = Column(Text, nullable=True)
    terminal_reason = Column(String(160), nullable=True, index=True)
    quarantined_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    draft = relationship("ProductUGCRecipeDraft", back_populates="generation_job")
    organization = relationship("Organization")
    requested_by_user_profile = relationship("UserProfile")


class ProductUGCQueueWorkerHeartbeat(Base):
    """Liveness record for a supervised durable-generation worker.

    ``worker_key`` is a one-way fingerprint of the process identity. Hostnames,
    process ids, provider credentials, and lease tokens are deliberately not
    persisted or returned to operators.
    """

    __tablename__ = "product_ugc_queue_worker_heartbeats"
    __table_args__ = (
        UniqueConstraint("worker_key", name="uq_product_ugc_queue_worker_key"),
        CheckConstraint(
            "state IN ('starting', 'polling', 'idle', 'working', 'ready', 'error', 'stopping')",
            name="ck_product_ugc_queue_worker_state",
        ),
        CheckConstraint(
            "processed_job_count >= 0",
            name="ck_product_ugc_queue_worker_processed_nonnegative",
        ),
        Index("ix_product_ugc_queue_worker_heartbeat", "heartbeat_at", "state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    worker_key = Column(String(64), nullable=False, index=True)
    is_supervised = Column(Boolean, nullable=False, default=False, index=True)
    state = Column(String(32), nullable=False, default="starting", index=True)
    current_job_id = Column(
        Integer,
        ForeignKey("product_ugc_generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_job_id = Column(Integer, nullable=True, index=True)
    processed_job_count = Column(Integer, nullable=False, default=0)
    last_error_code = Column(String(120), nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    heartbeat_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    current_job = relationship("ProductUGCGenerationJob", foreign_keys=[current_job_id])


class ProductUGCQueueReconciliation(Base):
    """Append-only human evidence resolving an ambiguous provider submit.

    The mutable queue row can resume after reconciliation, but the exact human
    decision that allowed that transition remains immutable for audit and
    incident review.
    """

    __tablename__ = "product_ugc_queue_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_product_ugc_queue_reconciliation_idempotency",
        ),
        CheckConstraint(
            "action IN ('attach_existing_provider_task', 'confirm_no_provider_submission')",
            name="ck_product_ugc_queue_reconciliation_action",
        ),
        CheckConstraint(
            "(action = 'attach_existing_provider_task' AND provider_task_id IS NOT NULL) "
            "OR (action = 'confirm_no_provider_submission' AND provider_task_id IS NULL)",
            name="ck_product_ugc_queue_reconciliation_task_shape",
        ),
        Index(
            "ix_product_ugc_queue_reconciliation_org_job",
            "organization_id",
            "generation_job_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    generation_job_id = Column(
        Integer,
        ForeignKey("product_ugc_generation_jobs.id"),
        nullable=False,
        index=True,
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    actor_user_profile_id = Column(
        Integer,
        ForeignKey("user_profiles.id"),
        nullable=False,
        index=True,
    )
    action = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=False, index=True)
    provider_task_id = Column(String(255), nullable=True, index=True)
    quarantine_incident_key = Column(String(64), nullable=False, index=True)
    evidence_reference = Column(String(200), nullable=False)
    reason = Column(Text, nullable=False)
    evidence_sha256 = Column(String(64), nullable=False)
    job_status_before = Column(String(40), nullable=False)
    job_status_after = Column(String(40), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    generation_job = relationship("ProductUGCGenerationJob")
    organization = relationship("Organization")
    actor_user_profile = relationship("UserProfile")


@event.listens_for(ProductUGCQueueReconciliation, "before_update")
def _prevent_product_ugc_queue_reconciliation_update(_mapper, _connection, _target) -> None:
    raise ValueError("ProductUGCQueueReconciliation is append-only and cannot be updated.")


@event.listens_for(ProductUGCQueueReconciliation, "before_delete")
def _prevent_product_ugc_queue_reconciliation_delete(_mapper, _connection, _target) -> None:
    raise ValueError("ProductUGCQueueReconciliation is append-only and cannot be deleted.")


class LaunchActionPlan(Base, TimestampMixin):
    __tablename__ = "launch_action_plans"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="open", index=True)
    action_count = Column(Integer, nullable=False, default=0)
    safe_action_count = Column(Integer, nullable=False, default=0)
    human_action_count = Column(Integer, nullable=False, default=0)
    paid_action_count = Column(Integer, nullable=False, default=0)
    publishing_action_count = Column(Integer, nullable=False, default=0)
    actions_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign")


class CampaignActionQueueItem(Base, TimestampMixin):
    __tablename__ = "campaign_action_queue_items"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=True, index=True)
    action_type = Column(String(120), nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=50, index=True)
    status = Column(String(80), nullable=False, default="open", index=True)
    reason = Column(Text, nullable=True)
    blockers_json = Column(JSON, default=list, nullable=False)
    safe_to_execute = Column(Boolean, default=False, nullable=False)
    requires_human = Column(Boolean, default=True, nullable=False)

    campaign = relationship("Campaign", back_populates="action_queue_items")
    product = relationship("Product")
    content_run = relationship("ContentRun")


class CampaignBatchRun(Base, TimestampMixin):
    __tablename__ = "campaign_batch_runs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="created", index=True)
    action_type = Column(String(120), nullable=True, index=True)
    dry_run = Column(Boolean, default=True, nullable=False, index=True)
    selected_action_ids_json = Column(JSON, default=list, nullable=False)
    total_selected = Column(Integer, nullable=False, default=0)
    total_executed = Column(Integer, nullable=False, default=0)
    total_skipped = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)
    results_json = Column(JSON, default=list, nullable=False)
    warnings_json = Column(JSON, default=list, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign", back_populates="batch_runs")
    items = relationship("CampaignBatchItem", back_populates="batch_run", cascade="all, delete-orphan")


class CampaignBatchItem(Base, TimestampMixin):
    __tablename__ = "campaign_batch_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_run_id = Column(Integer, ForeignKey("campaign_batch_runs.id"), nullable=False, index=True)
    action_queue_item_id = Column(Integer, ForeignKey("campaign_action_queue_items.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    action_type = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="created", index=True)
    result_json = Column(JSON, default=dict, nullable=False)
    error_message = Column(Text, nullable=True)

    batch_run = relationship("CampaignBatchRun", back_populates="items")
    action_queue_item = relationship("CampaignActionQueueItem")
    product = relationship("Product")


class CampaignPerformanceImport(Base, TimestampMixin):
    __tablename__ = "campaign_performance_imports"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    source_file = Column(String(500), nullable=False)
    status = Column(String(80), nullable=False, default="imported", index=True)
    imported_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    warnings_json = Column(JSON, default=list, nullable=False)
    errors_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign", back_populates="performance_imports")


class CampaignPerformanceMetric(Base):
    __tablename__ = "campaign_performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    content_run_id = Column(Integer, ForeignKey("content_runs.id"), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    platform = Column(String(120), nullable=False, index=True)
    posted_url = Column(String(500), nullable=True, index=True)
    period_start = Column(Date, nullable=True, index=True)
    period_end = Column(Date, nullable=True, index=True)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    orders = Column(Integer, nullable=True)
    revenue = Column(Float, nullable=True)
    spend = Column(Float, nullable=True)
    ctr = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    cost_per_view = Column(Float, nullable=True)
    cost_per_click = Column(Float, nullable=True)
    cost_per_order = Column(Float, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    campaign = relationship("Campaign", back_populates="performance_metrics")
    product = relationship("Product")
    content_run = relationship("ContentRun")
    creative_variant = relationship("CreativeVariant")
    publishing_task = relationship("PublishingTask")
    destination = relationship("PublishingDestination")


class CampaignPerformanceScore(Base, TimestampMixin):
    __tablename__ = "campaign_performance_scores"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(String(160), nullable=True, index=True)
    score_json = Column(JSON, default=dict, nullable=False)
    status = Column(String(80), nullable=False, default="needs_data", index=True)
    recommendation = Column(Text, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)

    campaign = relationship("Campaign", back_populates="performance_scores")


class CampaignScalingRecommendation(Base, TimestampMixin):
    __tablename__ = "campaign_scaling_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    recommendation_type = Column(String(120), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    creative_variant_id = Column(Integer, ForeignKey("creative_variants.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    priority = Column(Integer, nullable=False, default=50, index=True)
    expected_impact = Column(Text, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    status = Column(String(80), nullable=False, default="proposed", index=True)

    campaign = relationship("Campaign", back_populates="scaling_recommendations")
    product = relationship("Product")
    creative_variant = relationship("CreativeVariant")
    destination = relationship("PublishingDestination")


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False)
    slug = Column(String(160), unique=True, nullable=False, index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    settings_json = Column(JSON, default=dict, nullable=False)

    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    supabase_user_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    display_name = Column(String(180), nullable=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_login_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    memberships = relationship("Membership", back_populates="user_profile", cascade="all, delete-orphan")
    public_training_attempts = relationship("UserTrainingAttempt", back_populates="user_profile", cascade="all, delete-orphan")
    public_training_certifications = relationship("TrainingCertification", back_populates="user_profile", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user_profile")


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_profile_id",
            name="uq_membership_organization_user",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    role = Column(String(80), nullable=False, default="viewer", index=True)
    status = Column(String(80), nullable=False, default="active", index=True)
    permissions_json = Column(JSON, default=list, nullable=False)

    organization = relationship("Organization", back_populates="memberships")
    user_profile = relationship("UserProfile", back_populates="memberships")


class TrainingModule(Base, TimestampMixin):
    __tablename__ = "public_training_modules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(120), unique=True, nullable=False, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=100, index=True)
    required_for_roles_json = Column(JSON, default=list, nullable=False)
    required_for_permissions_json = Column(JSON, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    lessons = relationship("PublicTrainingLesson", back_populates="module", cascade="all, delete-orphan")
    questions = relationship("TrainingQuestion", back_populates="module", cascade="all, delete-orphan")
    attempts = relationship("UserTrainingAttempt", back_populates="module", cascade="all, delete-orphan")
    certifications = relationship("TrainingCertification", back_populates="module", cascade="all, delete-orphan")


class PublicTrainingLesson(Base, TimestampMixin):
    __tablename__ = "public_training_lessons"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("public_training_modules.id"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    content_markdown = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, default=100, index=True)

    module = relationship("TrainingModule", back_populates="lessons")


class TrainingQuestion(Base, TimestampMixin):
    __tablename__ = "public_training_questions"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("public_training_modules.id"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(80), nullable=False, default="single_choice", index=True)
    options_json = Column(JSON, default=list, nullable=False)
    correct_answer_json = Column(JSON, default=list, nullable=False)
    explanation = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=100, index=True)

    module = relationship("TrainingModule", back_populates="questions")


class UserTrainingAttempt(Base, TimestampMixin):
    __tablename__ = "user_training_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey("public_training_modules.id"), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="completed", index=True)
    score = Column(Float, nullable=False, default=0)
    passed = Column(Boolean, default=False, nullable=False, index=True)
    answers_json = Column(JSON, default=dict, nullable=False)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    user_profile = relationship("UserProfile", back_populates="public_training_attempts")
    module = relationship("TrainingModule", back_populates="attempts")


class TrainingCertification(Base, TimestampMixin):
    __tablename__ = "public_training_certifications"

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    module_id = Column(Integer, ForeignKey("public_training_modules.id"), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey("user_training_attempts.id"), nullable=True, index=True)
    module_code = Column(String(120), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="passed", index=True)
    granted_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    user_profile = relationship("UserProfile", back_populates="public_training_certifications")
    module = relationship("TrainingModule", back_populates="certifications")
    attempt = relationship("UserTrainingAttempt")


class FactoryEvent(Base):
    """Immutable product event used for funnel and UX measurement."""

    __tablename__ = "factory_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_factory_events_idempotency_key"),)

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(120), nullable=False, index=True)
    event_version = Column(Integer, nullable=False, default=1)
    occurred_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    received_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    role = Column(String(80), nullable=False, index=True)
    factory_run_id = Column(String(160), nullable=True, index=True)
    entity_type = Column(String(120), nullable=True, index=True)
    entity_id = Column(String(160), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    sku = Column(String(120), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    source = Column(String(80), nullable=False, default="server", index=True)
    idempotency_key = Column(String(160), nullable=False, index=True)
    properties_json = Column(JSON, nullable=False, default=dict)


@event.listens_for(FactoryEvent, "before_update")
def _prevent_factory_event_update(_mapper, _connection, _target) -> None:
    raise ValueError("FactoryEvent is append-only and cannot be updated.")


@event.listens_for(FactoryEvent, "before_delete")
def _prevent_factory_event_delete(_mapper, _connection, _target) -> None:
    raise ValueError("FactoryEvent is append-only and cannot be deleted.")


class GenerationCostLedgerEntry(Base):
    """Immutable accounting record for real video-provider generation cost.

    Amounts are stored in the currency's minor unit (kopecks/cents), never as a
    floating-point value. Estimates and actual costs are separate immutable
    records; aggregation chooses a confirmed actual cost over an estimate for
    the same cost scope, so the two are never double-counted.
    """

    __tablename__ = "generation_cost_ledger_entries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_generation_cost_idempotency_key"),
        UniqueConstraint("supersedes_entry_id", name="uq_generation_cost_supersedes_entry"),
        UniqueConstraint(
            "organization_id",
            "video_job_id",
            "currency",
            "entry_kind",
            "cost_unit_key",
            "revision",
            name="uq_generation_cost_unit_revision",
        ),
        CheckConstraint("amount_minor >= 0", name="ck_generation_cost_amount_nonnegative"),
        CheckConstraint("revision > 0", name="ck_generation_cost_revision_positive"),
        CheckConstraint(
            "entry_kind IN ('estimated', 'actual')",
            name="ck_generation_cost_entry_kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'voided')",
            name="ck_generation_cost_status",
        ),
        CheckConstraint(
            "cost_scope IN ('provider_job', 'video_job')",
            name="ck_generation_cost_scope",
        ),
        CheckConstraint(
            "(cost_scope = 'provider_job' AND provider_job_id IS NOT NULL) "
            "OR (cost_scope = 'video_job' AND provider_job_id IS NULL)",
            name="ck_generation_cost_provider_job_scope",
        ),
        Index(
            "ix_generation_cost_org_currency_recorded",
            "organization_id",
            "currency",
            "recorded_at",
        ),
        Index(
            "ix_generation_cost_video_scope",
            "video_job_id",
            "cost_scope",
            "provider_job_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    provider_job_id = Column(String(160), nullable=True, index=True)
    provider = Column(String(120), nullable=False, index=True)
    cost_scope = Column(String(40), nullable=False, index=True)
    cost_unit_key = Column(String(220), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, index=True)
    entry_kind = Column(String(40), nullable=False, index=True)
    status = Column(String(40), nullable=False, index=True)
    source = Column(String(80), nullable=False, index=True)
    external_reference = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(160), nullable=False, index=True)
    supersedes_entry_id = Column(
        Integer,
        ForeignKey("generation_cost_ledger_entries.id"),
        nullable=True,
        index=True,
    )
    recorded_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    recorded_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    organization = relationship("Organization")
    video_job = relationship("VideoJob")
    recorded_by_user_profile = relationship("UserProfile")
    supersedes_entry = relationship("GenerationCostLedgerEntry", remote_side=[id], uselist=False)


@event.listens_for(GenerationCostLedgerEntry, "before_update")
def _prevent_generation_cost_update(_mapper, _connection, _target) -> None:
    raise ValueError("GenerationCostLedgerEntry is append-only and cannot be updated.")


@event.listens_for(GenerationCostLedgerEntry, "before_delete")
def _prevent_generation_cost_delete(_mapper, _connection, _target) -> None:
    raise ValueError("GenerationCostLedgerEntry is append-only and cannot be deleted.")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    action = Column(String(160), nullable=False, index=True)
    status = Column(String(80), nullable=False, default="allowed", index=True)
    reason = Column(Text, nullable=True)
    entity_type = Column(String(120), nullable=True, index=True)
    entity_id = Column(String(160), nullable=True, index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    user_profile = relationship("UserProfile", back_populates="audit_logs")
    organization = relationship("Organization")


class ContentCycle(Base, TimestampMixin):
    """Canonical, organization-owned lineage for one measurable content cycle.

    Every downstream identifier is stored explicitly. A consumer never has to
    infer a package or tracking link from SKU, timestamps, or "latest" rows.
    """

    __tablename__ = "content_cycles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_content_cycle_organization_product",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_content_cycle_organization_idempotency",
        ),
        UniqueConstraint(
            "product_ugc_recipe_draft_id",
            name="uq_content_cycle_product_ugc_draft",
        ),
        UniqueConstraint("video_job_id", name="uq_content_cycle_video_job"),
        UniqueConstraint("output_acceptance_id", name="uq_content_cycle_output_acceptance"),
        UniqueConstraint("publishing_package_id", name="uq_content_cycle_publishing_package"),
        UniqueConstraint("publishing_task_id", name="uq_content_cycle_publishing_task"),
        UniqueConstraint("tracking_link_id", name="uq_content_cycle_tracking_link"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    product_ugc_recipe_draft_id = Column(
        Integer,
        ForeignKey("product_ugc_recipe_drafts.id"),
        nullable=False,
        index=True,
    )
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False, index=True)
    ai_production_brief_id = Column(Integer, ForeignKey("ai_production_briefs.id"), nullable=False, index=True)
    output_acceptance_id = Column(
        Integer,
        ForeignKey("video_output_acceptances.id"),
        nullable=True,
        index=True,
    )
    publishing_package_id = Column(Integer, ForeignKey("publishing_packages.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    tracking_link_id = Column(Integer, ForeignKey("tracking_links.id"), nullable=True, index=True)
    destination_id = Column(Integer, ForeignKey("publishing_destinations.id"), nullable=True, index=True)
    idempotency_key = Column(String(160), nullable=False)
    status = Column(String(80), nullable=False, default="needs_output_acceptance", index=True)
    trace_version = Column(Integer, nullable=False, default=1)

    organization = relationship("Organization", overlaps="product")
    created_by_user_profile = relationship("UserProfile")
    product = relationship("Product", overlaps="organization")
    product_ugc_recipe_draft = relationship("ProductUGCRecipeDraft")
    video_job = relationship("VideoJob", foreign_keys=[video_job_id])
    ai_production_brief = relationship("AIProductionBrief")
    output_acceptance = relationship("VideoOutputAcceptance")
    publishing_package = relationship("PublishingPackage")
    publishing_task = relationship("PublishingTask")
    tracking_link = relationship("TrackingLink")
    destination = relationship("PublishingDestination")


class MarketplaceListing(Base, TimestampMixin):
    """An organization's explicitly owned marketplace listing."""

    __tablename__ = "marketplace_listings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_listing_organization_product",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "id",
            name="uq_listing_scope_id",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "nm_id",
            name="uq_listing_scope_nm_id",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "vendor_code",
            name="uq_listing_scope_vendor_code",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "barcode",
            name="uq_listing_scope_barcode",
        ),
        CheckConstraint(
            "nm_id IS NOT NULL OR vendor_code IS NOT NULL OR barcode IS NOT NULL",
            name="ck_listing_has_identifier",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_listing_valid_interval",
        ),
        CheckConstraint(
            "status IN ('draft', 'verified', 'quarantined', 'inactive')",
            name="ck_listing_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    marketplace = Column(String(80), nullable=False, default="wildberries", index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    nm_id = Column(String(64), nullable=True, index=True)
    vendor_code = Column(String(160), nullable=True, index=True)
    barcode = Column(String(80), nullable=True, index=True)
    listing_url = Column(String(1000), nullable=True)
    status = Column(String(40), nullable=False, default="draft", index=True)
    valid_from = Column(DateTime, nullable=False, default=utcnow, index=True)
    valid_to = Column(DateTime, nullable=True, index=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)


class ListingAlias(Base, TimestampMixin):
    """A versioned exact identifier mapping to a current owned listing."""

    __tablename__ = "listing_aliases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "canonical_listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_alias_canonical_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "current_listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_alias_current_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "alias_type",
            "alias_value",
            "valid_from",
            name="uq_alias_scope_version",
        ),
        Index(
            "uq_alias_active_scope",
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "alias_type",
            "alias_value",
            unique=True,
            sqlite_where=text("valid_to IS NULL"),
            postgresql_where=text("valid_to IS NULL"),
        ),
        CheckConstraint(
            "alias_type IN ('nm_id', 'vendor_code', 'barcode', 'legacy_ref')",
            name="ck_alias_type",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_alias_valid_interval",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    marketplace = Column(String(80), nullable=False, index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    canonical_listing_id = Column(Integer, nullable=False, index=True)
    current_listing_id = Column(Integer, nullable=False, index=True)
    alias_type = Column(String(40), nullable=False, index=True)
    alias_value = Column(String(200), nullable=False, index=True)
    valid_from = Column(DateTime, nullable=False, default=utcnow, index=True)
    valid_to = Column(DateTime, nullable=True, index=True)
    reason = Column(Text, nullable=False)
    approved_by = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)


class ReplacementHistory(Base, TimestampMixin):
    """Append-oriented history for approved changes to an alias target."""

    __tablename__ = "listing_replacement_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "canonical_listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_history_canonical_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "previous_listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_history_previous_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "current_listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_history_current_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "alias_type",
            "alias_value",
            "valid_from",
            name="uq_history_scope_version",
        ),
        Index(
            "uq_history_active_scope",
            "organization_id",
            "marketplace",
            "seller_account_ref",
            "alias_type",
            "alias_value",
            unique=True,
            sqlite_where=text("valid_to IS NULL"),
            postgresql_where=text("valid_to IS NULL"),
        ),
        CheckConstraint(
            "alias_type IN ('nm_id', 'vendor_code', 'barcode', 'legacy_ref')",
            name="ck_history_alias_type",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_history_valid_interval",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    marketplace = Column(String(80), nullable=False, index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    canonical_listing_id = Column(Integer, nullable=False, index=True)
    previous_listing_id = Column(Integer, nullable=True, index=True)
    current_listing_id = Column(Integer, nullable=False, index=True)
    alias_type = Column(String(40), nullable=False, index=True)
    alias_value = Column(String(200), nullable=False, index=True)
    valid_from = Column(DateTime, nullable=False, default=utcnow, index=True)
    valid_to = Column(DateTime, nullable=True, index=True)
    reason = Column(Text, nullable=False)
    approved_by = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)


class WildberriesAnalyticsConnection(Base, TimestampMixin):
    """Organization-owned configuration for the official WB seller API.

    ``credential_ref`` is a logical environment-secret reference.  The API key
    itself is resolved only for an outbound request and is never persisted.
    """

    __tablename__ = "wildberries_analytics_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_wb_analytics_connection_organization_id",
        ),
        UniqueConstraint(
            "organization_id",
            "seller_account_ref",
            name="uq_wb_analytics_connection_seller",
        ),
        CheckConstraint(
            "marketplace = 'wildberries'",
            name="ck_wb_analytics_connection_marketplace",
        ),
        CheckConstraint(
            "connection_type = 'wildberries_seller_analytics'",
            name="ck_wb_analytics_connection_type",
        ),
        CheckConstraint(
            "credential_ref LIKE 'env:%'",
            name="ck_wb_analytics_connection_credential_reference",
        ),
        CheckConstraint(
            "status IN ('needs_verification', 'connected', 'error', 'disabled')",
            name="ck_wb_analytics_connection_status",
        ),
        CheckConstraint(
            "auth_status IN ('credential_reference_configured', 'api_key_verified', 'credential_unavailable')",
            name="ck_wb_analytics_connection_auth_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    marketplace = Column(String(80), nullable=False, default="wildberries", index=True)
    connection_type = Column(
        String(80),
        nullable=False,
        default="wildberries_seller_analytics",
        index=True,
    )
    credential_ref = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False, default="needs_verification", index=True)
    auth_status = Column(
        String(80),
        nullable=False,
        default="credential_reference_configured",
        index=True,
    )
    last_checked_at = Column(DateTime, nullable=True)
    last_sync_at = Column(DateTime, nullable=True, index=True)
    last_error_code = Column(String(160), nullable=True)
    settings_json = Column(JSON, default=dict, nullable=False)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)

    organization = relationship("Organization")
    created_by_user_profile = relationship("UserProfile")


class WildberriesAnalyticsSyncAudit(Base):
    """Append-only outcome of one idempotent official WB API sync."""

    __tablename__ = "wildberries_analytics_sync_audits"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_wb_analytics_sync_audit_organization_id",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_wb_analytics_sync_audit_idempotency",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            [
                "wildberries_analytics_connections.organization_id",
                "wildberries_analytics_connections.id",
            ],
            name="fk_wb_analytics_sync_audit_connection_scope",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_wb_analytics_sync_audit_period",
        ),
        CheckConstraint(
            "status IN ('completed', 'completed_with_quarantine', 'failed')",
            name="ck_wb_analytics_sync_audit_status",
        ),
        CheckConstraint(
            "page_count >= 0 AND requested_nm_id_count >= 0 "
            "AND response_product_count >= 0 AND snapshot_count >= 0 "
            "AND new_snapshot_count >= 0 AND quarantine_count >= 0",
            name="ck_wb_analytics_sync_audit_counts",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    connection_id = Column(Integer, nullable=False, index=True)
    actor_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    idempotency_key = Column(String(160), nullable=False)
    request_body_sha256 = Column(String(64), nullable=False, index=True)
    response_sha256 = Column(String(64), nullable=True, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    status = Column(String(48), nullable=False, index=True)
    error_code = Column(String(160), nullable=True)
    page_count = Column(Integer, nullable=False, default=0)
    requested_nm_id_count = Column(Integer, nullable=False, default=0)
    response_product_count = Column(Integer, nullable=False, default=0)
    snapshot_count = Column(Integer, nullable=False, default=0)
    new_snapshot_count = Column(Integer, nullable=False, default=0)
    quarantine_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    organization = relationship("Organization", viewonly=True)
    connection = relationship("WildberriesAnalyticsConnection", viewonly=True)
    actor_user_profile = relationship("UserProfile", viewonly=True)


class WildberriesMetricSnapshot(Base):
    """Immutable, exact-listing daily sales-funnel observation."""

    __tablename__ = "wildberries_metric_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            [
                "wildberries_analytics_connections.organization_id",
                "wildberries_analytics_connections.id",
            ],
            name="fk_wb_metric_snapshot_connection_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "sync_audit_id"],
            [
                "wildberries_analytics_sync_audits.organization_id",
                "wildberries_analytics_sync_audits.id",
            ],
            name="fk_wb_metric_snapshot_audit_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "marketplace", "seller_account_ref", "listing_id"],
            [
                "marketplace_listings.organization_id",
                "marketplace_listings.marketplace",
                "marketplace_listings.seller_account_ref",
                "marketplace_listings.id",
            ],
            name="fk_wb_metric_snapshot_listing_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_wb_metric_snapshot_product_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "source_fingerprint",
            name="uq_wb_metric_snapshot_source_fingerprint",
        ),
        CheckConstraint(
            "marketplace = 'wildberries'",
            name="ck_wb_metric_snapshot_marketplace",
        ),
        CheckConstraint(
            "period_end >= period_start AND metric_date >= period_start AND metric_date <= period_end",
            name="ck_wb_metric_snapshot_period",
        ),
        CheckConstraint(
            "open_count >= 0 AND cart_count >= 0 AND order_count >= 0 "
            "AND order_sum_minor >= 0 AND buyout_count >= 0 AND buyout_sum_minor >= 0",
            name="ck_wb_metric_snapshot_counts",
        ),
        CheckConstraint(
            "buyout_percent >= 0 AND buyout_percent <= 100 "
            "AND add_to_cart_percent >= 0 AND add_to_cart_percent <= 100 "
            "AND cart_to_order_percent >= 0 AND cart_to_order_percent <= 100",
            name="ck_wb_metric_snapshot_percentages",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    connection_id = Column(Integer, nullable=False, index=True)
    sync_audit_id = Column(Integer, nullable=False, index=True)
    marketplace = Column(String(80), nullable=False, default="wildberries", index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    listing_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    nm_id = Column(String(64), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    open_count = Column(BigInteger, nullable=False)
    cart_count = Column(BigInteger, nullable=False)
    order_count = Column(BigInteger, nullable=False)
    order_sum_minor = Column(BigInteger, nullable=False)
    buyout_count = Column(BigInteger, nullable=False)
    buyout_sum_minor = Column(BigInteger, nullable=False)
    buyout_percent = Column(Float, nullable=False)
    add_to_cart_percent = Column(Float, nullable=False)
    cart_to_order_percent = Column(Float, nullable=False)
    source_fingerprint = Column(String(64), nullable=False, index=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    observed_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    organization = relationship("Organization", viewonly=True)
    connection = relationship("WildberriesAnalyticsConnection", viewonly=True)
    sync_audit = relationship("WildberriesAnalyticsSyncAudit", viewonly=True)
    listing = relationship("MarketplaceListing", viewonly=True)
    product = relationship("Product", viewonly=True)


class WildberriesMetricQuarantine(Base):
    """Immutable official row that could not be mapped to one owned nmID."""

    __tablename__ = "wildberries_metric_quarantine"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            [
                "wildberries_analytics_connections.organization_id",
                "wildberries_analytics_connections.id",
            ],
            name="fk_wb_metric_quarantine_connection_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "sync_audit_id"],
            [
                "wildberries_analytics_sync_audits.organization_id",
                "wildberries_analytics_sync_audits.id",
            ],
            name="fk_wb_metric_quarantine_audit_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "source_fingerprint",
            name="uq_wb_metric_quarantine_source_fingerprint",
        ),
        CheckConstraint(
            "period_end >= period_start",
            name="ck_wb_metric_quarantine_period",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    connection_id = Column(Integer, nullable=False, index=True)
    sync_audit_id = Column(Integer, nullable=False, index=True)
    seller_account_ref = Column(String(160), nullable=False, index=True)
    nm_id = Column(String(64), nullable=True, index=True)
    reason_code = Column(String(160), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    source_fingerprint = Column(String(64), nullable=False, index=True)
    raw_row_json = Column(JSON, default=dict, nullable=False)
    observed_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    organization = relationship("Organization", viewonly=True)
    connection = relationship("WildberriesAnalyticsConnection", viewonly=True)
    sync_audit = relationship("WildberriesAnalyticsSyncAudit", viewonly=True)


def _prevent_wildberries_analytics_mutation(_mapper, _connection, _target) -> None:
    raise ValueError("Wildberries analytics evidence is append-only and cannot be mutated.")


for _wildberries_append_only_model in (
    WildberriesAnalyticsSyncAudit,
    WildberriesMetricSnapshot,
    WildberriesMetricQuarantine,
):
    event.listen(
        _wildberries_append_only_model,
        "before_update",
        _prevent_wildberries_analytics_mutation,
    )
    event.listen(
        _wildberries_append_only_model,
        "before_delete",
        _prevent_wildberries_analytics_mutation,
    )


class CustomerBillingAccount(Base):
    """Immutable organization-owned root for customer billing.

    The account is intentionally separate from provider costs and participant
    payouts. Its currency is fixed at creation; a different currency requires a
    deliberately designed migration instead of silently mixing minor units.
    """

    __tablename__ = "customer_billing_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_customer_billing_account_organization"),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_customer_billing_account_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_customer_billing_account_scope_id",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended', 'closed')",
            name="ck_customer_billing_account_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    currency = Column(String(3), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="active", index=True)
    idempotency_key = Column(String(160), nullable=False)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)


class CustomerBillingSubscriptionState(Base):
    """Append-only snapshot of a customer's current plan/subscription state."""

    __tablename__ = "customer_billing_subscription_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "billing_account_id"],
            ["customer_billing_accounts.organization_id", "customer_billing_accounts.id"],
            name="fk_customer_subscription_account_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_customer_subscription_idempotency",
        ),
        UniqueConstraint(
            "billing_account_id",
            "version",
            name="uq_customer_subscription_account_version",
        ),
        UniqueConstraint(
            "previous_state_id",
            name="uq_customer_subscription_previous_state",
        ),
        CheckConstraint("version > 0", name="ck_customer_subscription_version_positive"),
        CheckConstraint(
            "status IN ('trialing', 'active', 'paused', 'cancelled', 'expired')",
            name="ck_customer_subscription_status",
        ),
        CheckConstraint(
            "billing_interval IN ('month', 'year')",
            name="ck_customer_subscription_interval",
        ),
        CheckConstraint(
            "recurring_amount_minor >= 0",
            name="ck_customer_subscription_amount_nonnegative",
        ),
        CheckConstraint(
            "included_content_cycles >= 0",
            name="ck_customer_subscription_included_nonnegative",
        ),
        CheckConstraint(
            "current_period_end IS NULL OR current_period_start IS NOT NULL",
            name="ck_customer_subscription_period_start_required",
        ),
        CheckConstraint(
            "current_period_end IS NULL OR current_period_end > current_period_start",
            name="ck_customer_subscription_period_order",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    billing_account_id = Column(Integer, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    previous_state_id = Column(
        Integer,
        ForeignKey("customer_billing_subscription_states.id"),
        nullable=True,
        index=True,
    )
    plan_code = Column(String(80), nullable=False, index=True)
    status = Column(String(40), nullable=False, index=True)
    billing_interval = Column(String(20), nullable=False)
    recurring_amount_minor = Column(Integer, nullable=False)
    included_content_cycles = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, index=True)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    effective_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    idempotency_key = Column(String(160), nullable=False)
    recorded_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    recorded_at = Column(DateTime, nullable=False, default=utcnow, index=True)


class CustomerInvoice(Base):
    """Immutable invoice header; authoritative totals come from its ledger."""

    __tablename__ = "customer_invoices"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "billing_account_id"],
            ["customer_billing_accounts.organization_id", "customer_billing_accounts.id"],
            name="fk_customer_invoice_account_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "invoice_number",
            name="uq_customer_invoice_number",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_customer_invoice_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "billing_account_id",
            "id",
            name="uq_customer_invoice_scope_id",
        ),
        CheckConstraint("period_end > period_start", name="ck_customer_invoice_period_order"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    billing_account_id = Column(Integer, nullable=False, index=True)
    subscription_state_id = Column(
        Integer,
        ForeignKey("customer_billing_subscription_states.id"),
        nullable=False,
        index=True,
    )
    invoice_number = Column(String(80), nullable=False, index=True)
    currency = Column(String(3), nullable=False, index=True)
    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)
    issued_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    due_at = Column(DateTime, nullable=False, index=True)
    idempotency_key = Column(String(160), nullable=False)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)


class CustomerBillingLedgerEntry(Base):
    """Immutable customer-facing charge, credit, or reconciled payment fact."""

    __tablename__ = "customer_billing_ledger_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "billing_account_id"],
            ["customer_billing_accounts.organization_id", "customer_billing_accounts.id"],
            name="fk_customer_billing_ledger_account_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "billing_account_id", "invoice_id"],
            [
                "customer_invoices.organization_id",
                "customer_invoices.billing_account_id",
                "customer_invoices.id",
            ],
            name="fk_customer_billing_ledger_invoice_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_customer_billing_ledger_idempotency",
        ),
        UniqueConstraint(
            "organization_id",
            "transaction_reference",
            name="uq_customer_billing_transaction_reference",
        ),
        UniqueConstraint(
            "organization_id",
            "content_cycle_id",
            "entry_kind",
            name="uq_customer_billing_cycle_charge",
        ),
        UniqueConstraint(
            "generation_cost_ledger_entry_id",
            name="uq_customer_billing_generation_cost",
        ),
        UniqueConstraint("related_entry_id", name="uq_customer_billing_credit_target"),
        CheckConstraint("amount_minor > 0", name="ck_customer_billing_amount_positive"),
        CheckConstraint(
            "entry_kind IN ('charge', 'credit', 'payment')",
            name="ck_customer_billing_entry_kind",
        ),
        CheckConstraint(
            "source IN ('content_cycle_usage', 'manual_credit', 'manual_payment')",
            name="ck_customer_billing_source",
        ),
        CheckConstraint(
            "(entry_kind = 'charge' AND source = 'content_cycle_usage' "
            "AND content_cycle_id IS NOT NULL AND generation_cost_ledger_entry_id IS NOT NULL "
            "AND related_entry_id IS NULL AND transaction_reference IS NULL) OR "
            "(entry_kind = 'credit' AND source = 'manual_credit' "
            "AND content_cycle_id IS NULL AND generation_cost_ledger_entry_id IS NULL "
            "AND related_entry_id IS NOT NULL AND transaction_reference IS NULL) OR "
            "(entry_kind = 'payment' AND source = 'manual_payment' "
            "AND content_cycle_id IS NULL AND generation_cost_ledger_entry_id IS NULL "
            "AND related_entry_id IS NULL AND transaction_reference IS NOT NULL)",
            name="ck_customer_billing_entry_shape",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    billing_account_id = Column(Integer, nullable=False, index=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    entry_kind = Column(String(20), nullable=False, index=True)
    source = Column(String(40), nullable=False, index=True)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, index=True)
    description = Column(Text, nullable=False)
    content_cycle_id = Column(Integer, ForeignKey("content_cycles.id"), nullable=True, index=True)
    generation_cost_ledger_entry_id = Column(
        Integer,
        ForeignKey("generation_cost_ledger_entries.id"),
        nullable=True,
        index=True,
    )
    related_entry_id = Column(
        Integer,
        ForeignKey("customer_billing_ledger_entries.id"),
        nullable=True,
        index=True,
    )
    transaction_reference = Column(String(160), nullable=True, index=True)
    idempotency_key = Column(String(160), nullable=False)
    recorded_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    occurred_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    recorded_at = Column(DateTime, nullable=False, default=utcnow, index=True)


class MediaArtifact(Base, TimestampMixin):
    """Tenant-owned immutable media object metadata.

    Object bytes live behind a ``StorageBackend``.  Database rows keep stable
    object coordinates and integrity metadata only; short-lived signed URLs
    are deliberately never persisted.
    """

    __tablename__ = "media_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            name="fk_media_artifact_organization_product",
        ),
        UniqueConstraint("public_id", name="uq_media_artifact_public_id"),
        UniqueConstraint(
            "backend_name",
            "bucket",
            "object_key",
            name="uq_media_artifact_storage_object",
        ),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_media_artifact_org_idempotency",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_media_artifact_size_nonnegative"),
        CheckConstraint(
            "status IN ('uploading', 'ready', 'archived', 'pending_delete', 'deleted', 'failed')",
            name="ck_media_artifact_status",
        ),
        Index(
            "ix_media_artifact_org_created",
            "organization_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_media_artifact_org_product_kind",
            "organization_id",
            "product_id",
            "kind",
        ),
        Index(
            "ix_media_artifact_retention",
            "status",
            "retention_until",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(200), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_profile_id = Column(
        Integer,
        ForeignKey("user_profiles.id"),
        nullable=False,
        index=True,
    )
    product_id = Column(Integer, nullable=True, index=True)
    product_ugc_recipe_draft_id = Column(
        Integer,
        ForeignKey("product_ugc_recipe_drafts.id"),
        nullable=True,
        index=True,
    )
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=True, index=True)

    kind = Column(String(80), nullable=False, index=True)
    backend_name = Column(String(40), nullable=False, index=True)
    bucket = Column(String(255), nullable=False)
    object_key = Column(String(1000), nullable=False)
    object_version = Column(String(255), nullable=True)
    etag = Column(String(255), nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(160), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="uploading", index=True)
    metadata_json = Column(JSON, default=dict, nullable=False)

    retention_class = Column(String(80), nullable=False, default="standard", index=True)
    retention_until = Column(DateTime, nullable=True, index=True)
    legal_hold = Column(Boolean, nullable=False, default=False, index=True)
    archived_at = Column(DateTime, nullable=True, index=True)
    delete_requested_at = Column(DateTime, nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)


class MassOperationBatch(Base, TimestampMixin):
    """Auditable bulk generation or placement request for one organization."""

    __tablename__ = "mass_operation_batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_mass_batch_org_idempotency"),
        CheckConstraint(
            "operation_type IN ('generation', 'placement')",
            name="ck_mass_batch_operation_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'validated', 'queued', 'running', 'completed', 'completed_with_errors', 'blocked')",
            name="ck_mass_batch_status",
        ),
        CheckConstraint("total_requested >= 0", name="ck_mass_batch_requested_nonnegative"),
        CheckConstraint("total_accepted >= 0", name="ck_mass_batch_accepted_nonnegative"),
        CheckConstraint("total_failed >= 0", name="ck_mass_batch_failed_nonnegative"),
        Index("ix_mass_batch_org_type_status", "organization_id", "operation_type", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    operation_type = Column(String(40), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    idempotency_key = Column(String(180), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="draft", index=True)
    dry_run = Column(Boolean, nullable=False, default=True, index=True)
    total_requested = Column(Integer, nullable=False, default=0)
    total_accepted = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)
    parameters_json = Column(JSON, nullable=False, default=dict)
    results_json = Column(JSON, nullable=False, default=list)
    errors_json = Column(JSON, nullable=False, default=list)
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)


class CreatorTask(Base, TimestampMixin):
    """One creator-visible unit of work with organization ownership."""

    __tablename__ = "creator_tasks"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_creator_task_org_idempotency"),
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'submitted', 'review', 'done', 'blocked', 'cancelled')",
            name="ck_creator_task_status",
        ),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_creator_task_priority"),
        Index("ix_creator_task_assignee_status", "organization_id", "assignee_user_profile_id", "status", "due_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    assignee_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    created_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    mass_operation_batch_id = Column(Integer, ForeignKey("mass_operation_batches.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    product_ugc_recipe_draft_id = Column(Integer, ForeignKey("product_ugc_recipe_drafts.id"), nullable=True, index=True)
    media_artifact_id = Column(Integer, ForeignKey("media_artifacts.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    task_type = Column(String(80), nullable=False, default="create_video", index=True)
    title = Column(String(240), nullable=False)
    instructions = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="todo", index=True)
    priority = Column(Integer, nullable=False, default=3, index=True)
    due_at = Column(DateTime, nullable=True, index=True)
    checklist_json = Column(JSON, nullable=False, default=list)
    result_json = Column(JSON, nullable=False, default=dict)
    blockers_json = Column(JSON, nullable=False, default=list)
    idempotency_key = Column(String(180), nullable=False, index=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class CreatorPayout(Base, TimestampMixin):
    """Creator earnings ledger; bank details remain outside ContentEngine."""

    __tablename__ = "creator_payouts"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_creator_payout_org_idempotency"),
        CheckConstraint("amount_minor >= 0", name="ck_creator_payout_amount_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'paid', 'rejected', 'cancelled')",
            name="ck_creator_payout_status",
        ),
        Index("ix_creator_payout_user_status", "organization_id", "user_profile_id", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    creator_task_id = Column(Integer, ForeignKey("creator_tasks.id"), nullable=True, index=True)
    publishing_task_id = Column(Integer, ForeignKey("publishing_tasks.id"), nullable=True, index=True)
    approved_by_user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True, index=True)
    amount_minor = Column(Integer, nullable=False, default=0)
    currency = Column(String(12), nullable=False, default="RUB")
    status = Column(String(40), nullable=False, default="pending", index=True)
    reason = Column(Text, nullable=True)
    external_payment_reference = Column(String(180), nullable=True)
    idempotency_key = Column(String(180), nullable=False, index=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)


@event.listens_for(CustomerBillingAccount, "before_update")
@event.listens_for(CustomerBillingSubscriptionState, "before_update")
@event.listens_for(CustomerInvoice, "before_update")
@event.listens_for(CustomerBillingLedgerEntry, "before_update")
def _prevent_customer_billing_update(_mapper, _connection, _target) -> None:
    raise ValueError("Customer billing records are append-only and cannot be updated.")


@event.listens_for(CustomerBillingAccount, "before_delete")
@event.listens_for(CustomerBillingSubscriptionState, "before_delete")
@event.listens_for(CustomerInvoice, "before_delete")
@event.listens_for(CustomerBillingLedgerEntry, "before_delete")
def _prevent_customer_billing_delete(_mapper, _connection, _target) -> None:
    raise ValueError("Customer billing records are append-only and cannot be deleted.")
