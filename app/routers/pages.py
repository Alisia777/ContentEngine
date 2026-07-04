from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.script_engine import ScriptEngine
from app.services.video_engine import VideoEngine
from app.services.publishing_engine import PublishingEngine
from app.services.warmup_scheduler import WarmupScheduler
from app.services.upload_service import UploadService
from app.services.analytics_service import AnalyticsService
from app.ui import templates

router = APIRouter(tags=["pages"])


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, db: Session = Depends(get_db)):
    products = db.scalars(select(models.Product).order_by(models.Product.created_at.desc())).all()
    return templates.TemplateResponse(
        "products.html",
        {"request": request, "page_title": "Products", "products": products},
    )


@router.post("/products/create")
def create_product_form(
    sku: str = Form(...),
    brand: str = Form(...),
    title: str = Form(...),
    marketplace: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    product_url: str = Form(""),
    db: Session = Depends(get_db),
):
    db.add(
        models.Product(
            sku=sku,
            brand=brand,
            title=title,
            marketplace=marketplace or None,
            description=description or None,
            category=category or None,
            product_url=product_url or None,
            attributes_json={},
            benefits_json=[],
            images_json=[],
            reviews_json=[],
            restrictions_json=[],
        )
    )
    db.commit()
    return redirect("/products")


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail_page(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if not product:
        return redirect("/products")
    return templates.TemplateResponse(
        "product_detail.html",
        {"request": request, "page_title": product.title, "product": product},
    )


@router.get("/scripts", response_class=HTMLResponse)
def scripts_page(request: Request, db: Session = Depends(get_db)):
    script_jobs = db.scalars(select(models.ScriptJob).order_by(models.ScriptJob.created_at.desc())).all()
    return templates.TemplateResponse(
        "scripts.html",
        {"request": request, "page_title": "Scripts", "script_jobs": script_jobs},
    )


@router.get("/scripts/new", response_class=HTMLResponse)
def script_form_page(request: Request, db: Session = Depends(get_db)):
    selected_product_id = request.query_params.get("product_id")
    products = db.scalars(select(models.Product).order_by(models.Product.title)).all()
    brand_guides = db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()
    creative_templates = db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()
    return templates.TemplateResponse(
        "script_form.html",
        {
            "request": request,
            "page_title": "Create Script",
            "products": products,
            "brand_guides": brand_guides,
            "creative_templates": creative_templates,
            "selected_product_id": int(selected_product_id) if selected_product_id else None,
        },
    )


@router.post("/scripts/generate")
def generate_script_form(
    product_id: int = Form(...),
    template_id: int = Form(...),
    brand_guide_id: int = Form(...),
    db: Session = Depends(get_db),
):
    script_job = ScriptEngine(db).generate(product_id, template_id, brand_guide_id)
    return redirect(f"/scripts/{script_job.id}")


@router.get("/scripts/{script_job_id}", response_class=HTMLResponse)
def script_detail_page(script_job_id: int, request: Request, db: Session = Depends(get_db)):
    script_job = db.get(models.ScriptJob, script_job_id)
    if not script_job:
        return redirect("/scripts")
    return templates.TemplateResponse(
        "script_detail.html",
        {"request": request, "page_title": "Script Review", "script_job": script_job},
    )


@router.post("/script-variants/{variant_id}/approve-ui")
def approve_script_variant_ui(variant_id: int, db: Session = Depends(get_db)):
    variant = db.get(models.ScriptVariant, variant_id)
    if variant:
        ScriptEngine(db).approve_variant(variant)
        return redirect(f"/scripts/{variant.script_job_id}")
    return redirect("/scripts")


@router.post("/script-variants/{variant_id}/reject-ui")
def reject_script_variant_ui(
    variant_id: int,
    rejection_reason: str = Form("Needs revision"),
    db: Session = Depends(get_db),
):
    variant = db.get(models.ScriptVariant, variant_id)
    if variant:
        ScriptEngine(db).reject_variant(variant, rejection_reason=rejection_reason)
        return redirect(f"/scripts/{variant.script_job_id}")
    return redirect("/scripts")


@router.get("/videos", response_class=HTMLResponse)
def videos_page(request: Request, db: Session = Depends(get_db)):
    video_jobs = db.scalars(select(models.VideoJob).order_by(models.VideoJob.created_at.desc())).all()
    return templates.TemplateResponse(
        "videos.html",
        {"request": request, "page_title": "Videos", "video_jobs": video_jobs},
    )


@router.get("/videos/new", response_class=HTMLResponse)
def video_form_page(request: Request, db: Session = Depends(get_db)):
    selected_variant_id = request.query_params.get("variant_id")
    variants = db.scalars(
        select(models.ScriptVariant)
        .where(models.ScriptVariant.status == "script_approved")
        .order_by(models.ScriptVariant.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        "video_form.html",
        {
            "request": request,
            "page_title": "Video Generation",
            "variants": variants,
            "selected_variant_id": int(selected_variant_id) if selected_variant_id else None,
        },
    )


@router.post("/videos/create")
def create_video_form(
    script_variant_id: int = Form(...),
    provider: str = Form("mock"),
    db: Session = Depends(get_db),
):
    video_job = VideoEngine(db).create_job(script_variant_id, provider)
    return redirect(f"/videos/{video_job.id}")


@router.get("/videos/{video_job_id}", response_class=HTMLResponse)
def video_detail_page(video_job_id: int, request: Request, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if not video_job:
        return redirect("/videos")
    return templates.TemplateResponse(
        "video_detail.html",
        {"request": request, "page_title": "Video Review", "video_job": video_job},
    )


@router.post("/videos/{video_job_id}/run-ui")
def run_video_ui(video_job_id: int, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).run(video_job)
    return redirect(f"/videos/{video_job_id}")


@router.post("/videos/{video_job_id}/approve-ui")
def approve_video_ui(video_job_id: int, db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).approve_video(video_job)
    return redirect(f"/videos/{video_job_id}")


@router.post("/videos/{video_job_id}/reject-ui")
def reject_video_ui(video_job_id: int, reason: str = Form("Needs revision"), db: Session = Depends(get_db)):
    video_job = db.get(models.VideoJob, video_job_id)
    if video_job:
        VideoEngine(db).reject_video(video_job, reason)
    return redirect(f"/videos/{video_job_id}")


@router.get("/publishing-packages", response_class=HTMLResponse)
def publishing_packages_page(request: Request, db: Session = Depends(get_db)):
    packages = db.scalars(select(models.PublishingPackage).order_by(models.PublishingPackage.created_at.desc())).all()
    return templates.TemplateResponse(
        "publishing_packages.html",
        {"request": request, "page_title": "Publishing Packages", "packages": packages},
    )


@router.get("/publishing-packages/new", response_class=HTMLResponse)
def publishing_package_form_page(request: Request, db: Session = Depends(get_db)):
    selected_video_job_id = request.query_params.get("video_job_id")
    video_jobs = db.scalars(
        select(models.VideoJob)
        .where(models.VideoJob.status == "video_approved")
        .order_by(models.VideoJob.created_at.desc())
    ).all()
    return templates.TemplateResponse(
        "publishing_package_form.html",
        {
            "request": request,
            "page_title": "Create Publishing Package",
            "video_jobs": video_jobs,
            "selected_video_job_id": int(selected_video_job_id) if selected_video_job_id else None,
        },
    )


@router.post("/publishing-packages/create")
def create_publishing_package_form(
    video_job_id: int = Form(...),
    target_platform: str = Form(...),
    db: Session = Depends(get_db),
):
    package = PublishingEngine(db).create_package(video_job_id, target_platform)
    return redirect(f"/publishing-packages/{package.id}")


@router.get("/publishing-packages/{package_id}", response_class=HTMLResponse)
def publishing_package_detail_page(package_id: int, request: Request, db: Session = Depends(get_db)):
    package = db.get(models.PublishingPackage, package_id)
    if not package:
        return redirect("/publishing-packages")
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    default_time = (datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)).replace(microsecond=0).isoformat(
        timespec="minutes"
    )
    return templates.TemplateResponse(
        "publishing_package_detail.html",
        {
            "request": request,
            "page_title": "Publishing Package",
            "package": package,
            "accounts": accounts,
            "default_time": default_time,
        },
    )


@router.post("/publishing-packages/{package_id}/approve-ui")
def approve_publishing_package_ui(package_id: int, db: Session = Depends(get_db)):
    package = db.get(models.PublishingPackage, package_id)
    if package:
        PublishingEngine(db).approve(package)
    return redirect(f"/publishing-packages/{package_id}")


@router.post("/publishing-packages/{package_id}/reject-ui")
def reject_publishing_package_ui(
    package_id: int,
    reason: str = Form("Needs revision"),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, package_id)
    if package:
        PublishingEngine(db).reject(package, reason)
    return redirect(f"/publishing-packages/{package_id}")


@router.post("/publishing-jobs/schedule-ui")
def schedule_publishing_job_ui(
    publishing_package_id: int = Form(...),
    account_id: int = Form(...),
    scheduled_at: str = Form(...),
    provider: str = Form("mock"),
    manual_override: bool = Form(False),
    db: Session = Depends(get_db),
):
    package = db.get(models.PublishingPackage, publishing_package_id)
    account = db.get(models.PublishingAccount, account_id)
    if not package or not account:
        return redirect("/publishing-calendar")
    try:
        job = WarmupScheduler(db).schedule(
            package,
            account,
            datetime.fromisoformat(scheduled_at),
            provider,
            manual_override,
            "admin" if manual_override else None,
        )
        return redirect(f"/publishing-jobs/{job.id}")
    except ValueError:
        return redirect(f"/publishing-packages/{publishing_package_id}")


@router.get("/publishing-calendar", response_class=HTMLResponse)
def publishing_calendar_page(request: Request, db: Session = Depends(get_db)):
    jobs = db.scalars(select(models.PublishingJob).order_by(models.PublishingJob.scheduled_at)).all()
    return templates.TemplateResponse(
        "publishing_calendar.html",
        {"request": request, "page_title": "Publishing Calendar", "jobs": jobs},
    )


@router.get("/publishing-jobs/{job_id}", response_class=HTMLResponse)
def publishing_job_detail_page(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if not job:
        return redirect("/publishing-calendar")
    return templates.TemplateResponse(
        "publishing_job_detail.html",
        {"request": request, "page_title": "Publishing Job", "job": job},
    )


@router.post("/publishing-jobs/{job_id}/run-ui")
def run_publishing_job_ui(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if job:
        UploadService(db).run_job(job)
    return redirect(f"/publishing-jobs/{job_id}")


@router.post("/publishing-jobs/{job_id}/collect-analytics-ui")
def collect_analytics_ui(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if job:
        AnalyticsService(db).collect_for_job(job)
    return redirect(f"/publishing-jobs/{job_id}")


@router.get("/manual-upload/{job_id}", response_class=HTMLResponse)
def manual_upload_page(job_id: int, request: Request, db: Session = Depends(get_db)):
    job = db.get(models.PublishingJob, job_id)
    if not job:
        return redirect("/publishing-calendar")
    return templates.TemplateResponse(
        "manual_upload.html",
        {"request": request, "page_title": "Manual Upload", "job": job},
    )


@router.post("/manual-upload/{job_id}/complete")
def complete_manual_upload(
    job_id: int,
    provider_post_url: str = Form(...),
    operator_name: str = Form("operator"),
    db: Session = Depends(get_db),
):
    job = db.get(models.PublishingJob, job_id)
    if job:
        UploadService(db).mark_manual_uploaded(job, provider_post_url, operator_name)
    return redirect(f"/publishing-jobs/{job_id}")


@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    analytics = db.scalars(select(models.PublishAnalytics).order_by(models.PublishAnalytics.collected_at.desc())).all()
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request, "page_title": "Analytics", "analytics": analytics},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    brand_guides = db.scalars(select(models.BrandGuide).order_by(models.BrandGuide.brand)).all()
    templates_ = db.scalars(select(models.CreativeTemplate).order_by(models.CreativeTemplate.name)).all()
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "page_title": "Settings",
            "brand_guides": brand_guides,
            "creative_templates": templates_,
        },
    )


@router.get("/publishing-accounts", response_class=HTMLResponse)
def accounts_page(request: Request, db: Session = Depends(get_db)):
    accounts = db.scalars(select(models.PublishingAccount).order_by(models.PublishingAccount.platform)).all()
    return templates.TemplateResponse(
        "accounts.html",
        {"request": request, "page_title": "Publishing Accounts", "accounts": accounts},
    )


@router.get("/warmup-plans", response_class=HTMLResponse)
def warmup_plans_page(request: Request, db: Session = Depends(get_db)):
    plans = db.scalars(select(models.WarmupPlan).order_by(models.WarmupPlan.name)).all()
    return templates.TemplateResponse(
        "warmup_plans.html",
        {"request": request, "page_title": "Warm-up Plans", "plans": plans},
    )


@router.get("/ui-counts")
def ui_counts(db: Session = Depends(get_db)):
    return {
        "products": db.scalar(select(func.count()).select_from(models.Product)),
        "brand_guides": db.scalar(select(func.count()).select_from(models.BrandGuide)),
        "creative_templates": db.scalar(select(func.count()).select_from(models.CreativeTemplate)),
        "accounts": db.scalar(select(func.count()).select_from(models.PublishingAccount)),
    }
