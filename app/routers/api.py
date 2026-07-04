import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.engine import EngineRunResult, VideoFactoryEngine
from app.engine.errors import EngineError
from app.intelligence.csv_imports import import_csv_text
from app.intelligence.errors import IntelligenceError
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.prompt_builder import PromptPackBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.script_generator import GeneratorScriptService
from app.intelligence.video_generator import GeneratorVideoService
from app.services.script_engine import ScriptEngine
from app.services.video_engine import VideoEngine
from app.services.publishing_engine import PublishingEngine
from app.services.warmup_scheduler import WarmupScheduler
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api", tags=["api"])


class EngineRunRequest(BaseModel):
    product_id: int
    account_id: int | None = None


class GeneratorProductRequest(BaseModel):
    product_id: int


class GeneratorScriptBriefRequest(BaseModel):
    intelligence_pack_id: int


class GeneratorScriptRequest(BaseModel):
    script_brief_id: int
    llm_provider: str | None = None


class GeneratorPromptPackRequest(BaseModel):
    script_variant_id: int
    provider: str = "runway"
    script_brief_id: int | None = None


class GeneratorVideoJobRequest(BaseModel):
    prompt_pack_id: int
    video_provider: str | None = None


def get_or_404(db: Session, model: type, entity_id: int):
    entity = db.get(model, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return entity


def parse_json_cell(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


@router.post("/products", response_model=schemas.ProductRead)
def create_product(payload: schemas.ProductCreate, db: Session = Depends(get_db)):
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=list[schemas.ProductRead])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(models.Product).order_by(models.Product.created_at.desc())).all()


@router.get("/products/{product_id}", response_model=schemas.ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.Product, product_id)


@router.post("/products/import-csv", response_model=list[schemas.ProductRead])
async def import_products_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text))
    products = []
    for row in rows:
        product = models.Product(
            sku=row["sku"],
            brand=row.get("brand") or "Unknown",
            marketplace=row.get("marketplace"),
            title=row.get("title") or row["sku"],
            description=row.get("description"),
            category=row.get("category"),
            attributes_json=parse_json_cell(row.get("attributes_json"), {}),
            benefits_json=parse_json_cell(row.get("benefits_json"), []),
            images_json=parse_json_cell(row.get("images_json"), []),
            reviews_json=parse_json_cell(row.get("reviews_json"), []),
            restrictions_json=parse_json_cell(row.get("restrictions_json"), []),
            product_url=row.get("product_url"),
        )
        db.add(product)
        products.append(product)
    db.commit()
    for product in products:
        db.refresh(product)
    return products


@router.post("/brand-guides", response_model=schemas.BrandGuideRead)
def create_brand_guide(payload: schemas.BrandGuideCreate, db: Session = Depends(get_db)):
    guide = models.BrandGuide(**payload.model_dump())
    db.add(guide)
    db.commit()
    db.refresh(guide)
    return guide


@router.get("/brand-guides", response_model=list[schemas.BrandGuideRead])
def list_brand_guides(db: Session = Depends(get_db)):
    return db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()


@router.post("/creative-templates", response_model=schemas.CreativeTemplateRead)
def create_creative_template(payload: schemas.CreativeTemplateCreate, db: Session = Depends(get_db)):
    template = models.CreativeTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/creative-templates", response_model=list[schemas.CreativeTemplateRead])
def list_creative_templates(db: Session = Depends(get_db)):
    return db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()


@router.post("/reviews", response_model=schemas.ReviewRead)
def create_review(payload: schemas.ReviewCreate, db: Session = Depends(get_db)):
    review = models.Review(**payload.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.post("/engine/run-demo", response_model=EngineRunResult)
def run_engine_demo(payload: EngineRunRequest, db: Session = Depends(get_db)):
    result = VideoFactoryEngine(db).run_full_demo(payload.product_id, payload.account_id)
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


@router.get("/engine/status/{publishing_job_id}")
def get_engine_status(publishing_job_id: int, db: Session = Depends(get_db)):
    try:
        return VideoFactoryEngine(db).status_for_publishing_job(publishing_job_id)
    except EngineError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generator/intelligence/build")
def build_generator_intelligence(payload: GeneratorProductRequest, db: Session = Depends(get_db)):
    try:
        record = CreativeIntelligenceBuilder(db).build_for_product(payload.product_id)
        return {"id": record.id, "status": record.status, "pack": record.pack_json, "warnings": record.warnings_json}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/intelligence/{intelligence_pack_id}")
def get_generator_intelligence(intelligence_pack_id: int, db: Session = Depends(get_db)):
    record = get_or_404(db, models.CreativeIntelligencePackRecord, intelligence_pack_id)
    return {"id": record.id, "status": record.status, "pack": record.pack_json, "warnings": record.warnings_json}


@router.post("/generator/script-briefs")
def create_generator_script_brief(payload: GeneratorScriptBriefRequest, db: Session = Depends(get_db)):
    try:
        brief = ScriptBriefBuilder(db).build_from_record(payload.intelligence_pack_id)
        return {"id": brief.id, "status": brief.status, "brief": brief.brief_json}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/script-briefs/{script_brief_id}")
def get_generator_script_brief(script_brief_id: int, db: Session = Depends(get_db)):
    brief = get_or_404(db, models.ScriptBrief, script_brief_id)
    return {"id": brief.id, "status": brief.status, "brief": brief.brief_json}


@router.post("/generator/scripts/generate")
def generate_generator_script(payload: GeneratorScriptRequest, db: Session = Depends(get_db)):
    try:
        script_job = GeneratorScriptService(db).generate_from_brief(payload.script_brief_id, payload.llm_provider)
        variant = sorted(script_job.variants, key=lambda item: item.variant_number)[0]
        return {
            "script_job_id": script_job.id,
            "script_variant_id": variant.id,
            "status": script_job.status,
            "llm_provider": script_job.llm_provider,
            "script": script_job.output_script_json,
        }
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/scripts/{script_job_id}")
def get_generator_script(script_job_id: int, db: Session = Depends(get_db)):
    script_job = get_or_404(db, models.ScriptJob, script_job_id)
    return {
        "script_job_id": script_job.id,
        "status": script_job.status,
        "llm_provider": script_job.llm_provider,
        "script": script_job.output_script_json,
        "validation": script_job.validation_report_json,
    }


@router.post("/generator/prompt-packs")
def create_generator_prompt_pack(payload: GeneratorPromptPackRequest, db: Session = Depends(get_db)):
    try:
        prompt_pack = PromptPackBuilder(db).build_for_script(
            payload.script_variant_id,
            payload.provider,
            payload.script_brief_id,
        )
        return {
            "id": prompt_pack.id,
            "status": prompt_pack.status,
            "prompt_pack": prompt_pack.prompt_pack_json,
            "provider_payload": prompt_pack.provider_payload_json,
        }
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/generator/prompt-packs/{prompt_pack_id}")
def get_generator_prompt_pack(prompt_pack_id: int, db: Session = Depends(get_db)):
    prompt_pack = get_or_404(db, models.PromptPack, prompt_pack_id)
    return {
        "id": prompt_pack.id,
        "status": prompt_pack.status,
        "prompt_pack": prompt_pack.prompt_pack_json,
        "provider_payload": prompt_pack.provider_payload_json,
    }


@router.post("/generator/video-jobs")
def create_generator_video_job(payload: GeneratorVideoJobRequest, db: Session = Depends(get_db)):
    try:
        video_job = GeneratorVideoService(db).create_video_job_from_prompt_pack(
            payload.prompt_pack_id,
            payload.video_provider,
        )
        return {"id": video_job.id, "status": video_job.status, "provider": video_job.provider}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/video-jobs/{video_job_id}/run")
def run_generator_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return GeneratorVideoService(db).status(video_job)


@router.get("/generator/video-jobs/{video_job_id}/status")
def get_generator_video_status(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return GeneratorVideoService(db).status(video_job)


@router.post("/generator/video-jobs/{video_job_id}/download")
def download_generator_video_outputs(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    try:
        return {"paths": GeneratorVideoService(db).download_outputs(video_job)}
    except IntelligenceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generator/video-jobs/{video_job_id}/assemble")
def assemble_generator_video(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    video_job = GeneratorVideoService(db).assemble(video_job)
    return {"id": video_job.id, "status": video_job.status, "output_video_path": video_job.output_video_path}


@router.post("/generator/import/{kind}")
async def import_generator_csv(kind: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if kind not in {"product_metrics", "creative_performance", "review_insights", "market_signals"}:
        raise HTTPException(status_code=404, detail="Unknown generator import type")
    text = (await file.read()).decode("utf-8-sig")
    return {"kind": kind, "imported": import_csv_text(db, kind, text)}


@router.post("/script-jobs/generate", response_model=schemas.ScriptJobRead)
def generate_script_job(payload: schemas.ScriptGenerateRequest, db: Session = Depends(get_db)):
    try:
        return ScriptEngine(db).generate(payload.product_id, payload.template_id, payload.brand_guide_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/script-jobs/{script_job_id}", response_model=schemas.ScriptJobRead)
def get_script_job(script_job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.ScriptJob, script_job_id)


@router.post("/script-jobs/{script_job_id}/validate")
def validate_script_job(script_job_id: int, db: Session = Depends(get_db)):
    script_job = get_or_404(db, models.ScriptJob, script_job_id)
    return ScriptEngine(db).validate(script_job)


@router.post("/script-variants/{variant_id}/approve", response_model=schemas.ScriptVariantRead)
def approve_script_variant(variant_id: int, db: Session = Depends(get_db)):
    variant = get_or_404(db, models.ScriptVariant, variant_id)
    return ScriptEngine(db).approve_variant(variant)


@router.post("/script-variants/{variant_id}/reject", response_model=schemas.ScriptVariantRead)
def reject_script_variant(variant_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    variant = get_or_404(db, models.ScriptVariant, variant_id)
    return ScriptEngine(db).reject_variant(variant, rejection_reason=reason)


@router.post("/video-jobs", response_model=schemas.VideoJobRead)
def create_video_job(payload: schemas.VideoJobCreate, db: Session = Depends(get_db)):
    try:
        return VideoEngine(db).create_job(payload.script_variant_id, payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/video-jobs", response_model=list[schemas.VideoJobRead])
def list_video_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(models.VideoJob).order_by(models.VideoJob.created_at.desc())).all()


@router.get("/video-jobs/{video_job_id}", response_model=schemas.VideoJobRead)
def get_video_job(video_job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.VideoJob, video_job_id)


@router.post("/video-jobs/{video_job_id}/run", response_model=schemas.VideoJobRead)
def run_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).run(video_job)


@router.post("/video-jobs/{video_job_id}/assemble", response_model=schemas.VideoJobRead)
def assemble_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).assemble(video_job)


@router.post("/video-clips/{clip_id}/regenerate", response_model=schemas.VideoClipRead)
def regenerate_video_clip(clip_id: int, db: Session = Depends(get_db)):
    clip = get_or_404(db, models.VideoClip, clip_id)
    return VideoEngine(db).regenerate_clip(clip)


@router.post("/video-jobs/{video_job_id}/approve", response_model=schemas.VideoJobRead)
def approve_video_job(video_job_id: int, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).approve_video(video_job)


@router.post("/video-jobs/{video_job_id}/reject", response_model=schemas.VideoJobRead)
def reject_video_job(video_job_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, video_job_id)
    return VideoEngine(db).reject_video(video_job, reason)


@router.post("/publishing-packages", response_model=schemas.PublishingPackageRead)
def create_publishing_package(payload: schemas.PublishingPackageCreate, db: Session = Depends(get_db)):
    try:
        return PublishingEngine(db).create_package(payload.video_job_id, payload.target_platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing-packages", response_model=list[schemas.PublishingPackageRead])
def list_publishing_packages(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all()


@router.get("/publishing-packages/{package_id}", response_model=schemas.PublishingPackageRead)
def get_publishing_package(package_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingPackage, package_id)


@router.post("/publishing-packages/{package_id}/generate-metadata", response_model=schemas.PublishingPackageRead)
def generate_publishing_metadata(package_id: int, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).regenerate_metadata(package)


@router.post("/publishing-packages/{package_id}/approve", response_model=schemas.PublishingPackageRead)
def approve_publishing_package(package_id: int, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).approve(package)


@router.post("/publishing-packages/{package_id}/reject", response_model=schemas.PublishingPackageRead)
def reject_publishing_package(package_id: int, reason: str = "Needs revision", db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, package_id)
    return PublishingEngine(db).reject(package, reason)


@router.get("/publishing-calendar", response_model=list[schemas.PublishingJobRead])
def publishing_calendar(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at)).all()


@router.post("/publishing-jobs/schedule", response_model=schemas.PublishingJobRead)
def schedule_publishing_job(payload: schemas.PublishingScheduleRequest, db: Session = Depends(get_db)):
    package = get_or_404(db, models.PublishingPackage, payload.publishing_package_id)
    account = get_or_404(db, models.PublishingAccount, payload.account_id)
    try:
        return WarmupScheduler(db).schedule(
            package,
            account,
            payload.scheduled_at,
            payload.provider,
            payload.manual_override,
            payload.operator_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/publishing-jobs", response_model=list[schemas.PublishingJobRead])
def list_publishing_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at.desc())).all()


@router.get("/publishing-jobs/{job_id}", response_model=schemas.PublishingJobRead)
def get_publishing_job(job_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingJob, job_id)


@router.post("/publishing-jobs/{job_id}/run", response_model=schemas.PublishingJobRead)
def run_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).run_job(job)


@router.post("/publishing-jobs/{job_id}/mark-manual-uploaded", response_model=schemas.PublishingJobRead)
def mark_manual_uploaded(job_id: int, payload: schemas.ManualUploadRequest, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).mark_manual_uploaded(job, payload.provider_post_url, payload.operator_name)


@router.post("/publishing-jobs/{job_id}/cancel", response_model=schemas.PublishingJobRead)
def cancel_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).cancel(job)


@router.post("/publishing-jobs/{job_id}/retry", response_model=schemas.PublishingJobRead)
def retry_publishing_job(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return UploadService(db).retry(job)


@router.post("/publishing-jobs/{job_id}/collect-analytics", response_model=schemas.PublishAnalyticsRead)
def collect_job_analytics(job_id: int, db: Session = Depends(get_db)):
    job = get_or_404(db, models.PublishingJob, job_id)
    return AnalyticsService(db).collect_for_job(job)


@router.get("/publishing-jobs/{job_id}/analytics", response_model=list[schemas.PublishAnalyticsRead])
def get_job_analytics(job_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.PublishingJob, job_id)
    return db.scalars(
        select(models.PublishAnalytics)
        .where(models.PublishAnalytics.publishing_job_id == job_id)
        .order_by(models.PublishAnalytics.collected_at.desc())
    ).all()


@router.get("/analytics/by-product/{product_id}", response_model=list[schemas.PublishAnalyticsRead])
def get_analytics_by_product(product_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.Product, product_id)
    return AnalyticsService(db).by_product(product_id)


@router.get("/analytics/by-account/{account_id}", response_model=list[schemas.PublishAnalyticsRead])
def get_analytics_by_account(account_id: int, db: Session = Depends(get_db)):
    get_or_404(db, models.PublishingAccount, account_id)
    return AnalyticsService(db).by_account(account_id)


@router.post("/exports")
def create_export(payload: schemas.ExportCreate, db: Session = Depends(get_db)):
    video_job = get_or_404(db, models.VideoJob, payload.video_job_id)
    export = models.ExportPackage(
        video_job_id=video_job.id,
        destination=payload.destination,
        video_file=video_job.output_video_path,
        preview_file=video_job.preview_path,
        title=video_job.script_variant.hook,
        description=video_job.script_variant.key_message,
        tags_json=[video_job.script_variant.creative_angle],
        metadata_json={"source": "qharisma_video_factory", "provider": video_job.provider},
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return {
        "id": export.id,
        "destination": export.destination,
        "video_file": export.video_file,
        "preview_file": export.preview_file,
    }


@router.post("/publishing-accounts", response_model=schemas.PublishingAccountRead)
def create_publishing_account(payload: schemas.PublishingAccountCreate, db: Session = Depends(get_db)):
    account = models.PublishingAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/publishing-accounts", response_model=list[schemas.PublishingAccountRead])
def list_publishing_accounts(db: Session = Depends(get_db)):
    return db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()


@router.get("/publishing-accounts/{account_id}", response_model=schemas.PublishingAccountRead)
def get_publishing_account(account_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.PublishingAccount, account_id)


@router.patch("/publishing-accounts/{account_id}", response_model=schemas.PublishingAccountRead)
def patch_publishing_account(account_id: int, payload: schemas.PublishingAccountPatch, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.post("/publishing-accounts/{account_id}/pause", response_model=schemas.PublishingAccountRead)
def pause_publishing_account(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    account.warmup_status = "paused"
    db.commit()
    db.refresh(account)
    return account


@router.post("/publishing-accounts/{account_id}/resume", response_model=schemas.PublishingAccountRead)
def resume_publishing_account(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    account.warmup_status = "warming" if account.warmup_phase != "phase_4_active_distribution" else "active"
    db.commit()
    db.refresh(account)
    return account


@router.post("/warmup-plans", response_model=schemas.WarmupPlanRead)
def create_warmup_plan(payload: schemas.WarmupPlanCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"rules"})
    plan = models.WarmupPlan(**data)
    db.add(plan)
    db.flush()
    for rule_payload in payload.rules:
        db.add(models.WarmupRule(warmup_plan_id=plan.id, **rule_payload.model_dump()))
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/warmup-plans", response_model=list[schemas.WarmupPlanRead])
def list_warmup_plans(db: Session = Depends(get_db)):
    return db.scalars(select(models.WarmupPlan).order_by(models.WarmupPlan.name)).all()


@router.get("/warmup-plans/{plan_id}", response_model=schemas.WarmupPlanRead)
def get_warmup_plan(plan_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, models.WarmupPlan, plan_id)


@router.post("/warmup-plans/{plan_id}/apply-to-account", response_model=schemas.WarmupPlanRead)
def apply_warmup_plan(plan_id: int, account_id: int, db: Session = Depends(get_db)):
    plan = get_or_404(db, models.WarmupPlan, plan_id)
    account = get_or_404(db, models.PublishingAccount, account_id)
    plan.account_id = account.id
    account.warmup_phase = plan.current_phase
    account.warmup_status = "warming"
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/publishing-accounts/{account_id}/warmup-status")
def get_warmup_status(account_id: int, db: Session = Depends(get_db)):
    account = get_or_404(db, models.PublishingAccount, account_id)
    plan = db.scalar(select(models.WarmupPlan).where(models.WarmupPlan.account_id == account.id))
    return {
        "account_id": account.id,
        "warmup_status": account.warmup_status,
        "warmup_phase": account.warmup_phase,
        "daily_publish_limit": account.daily_publish_limit,
        "weekly_publish_limit": account.weekly_publish_limit,
        "active_plan": plan.name if plan else None,
        "checked_at": datetime.now(UTC).isoformat(),
    }
