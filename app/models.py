from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
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

    id = Column(Integer, primary_key=True, index=True)
    script_variant_id = Column(Integer, ForeignKey("script_variants.id"), nullable=False)
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

    id = Column(Integer, primary_key=True, index=True)
    video_job_id = Column(Integer, ForeignKey("video_jobs.id"), nullable=False)
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
    status = Column(String(80), nullable=False, default="draft", index=True)

    video_job = relationship("VideoJob", back_populates="publishing_packages")
    product = relationship("Product", back_populates="publishing_packages")
    publishing_jobs = relationship("PublishingJob", back_populates="publishing_package")


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
