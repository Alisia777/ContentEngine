from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.engine.errors import EngineError, EngineNotFoundError, EnginePreconditionError
from app.engine.types import EngineRunResult, EngineStepResult
from app.enums import WorkflowStatus
from app.services.analytics_service import AnalyticsService
from app.services.publishing_engine import PublishingEngine
from app.services.script_engine import ScriptEngine
from app.services.upload_service import UploadService
from app.services.video_engine import VideoEngine
from app.services.warmup_scheduler import WarmupScheduler


class VideoFactoryEngine:
    def __init__(self, db: Session):
        self.db = db

    def run_full_demo(self, product_id: int, account_id: int | None = None) -> EngineRunResult:
        result = EngineRunResult(status="running", product_id=product_id)
        try:
            product = self._require_product(product_id)
            account = self._select_account(product, account_id)

            script_step = self.generate_script(product.id)
            result.steps.append(script_step)
            result.script_job_id = script_step.entity_id

            script_job = self._require_script_job(result.script_job_id)
            variant = self._first_variant(script_job)
            ScriptEngine(self.db).approve_variant(variant, reviewer_name="demo-engine")
            result.script_variant_id = variant.id
            result.steps.append(
                self._step(
                    "approve_script_variant",
                    "ok",
                    "script_variant",
                    variant.id,
                    "Script variant auto-approved in demo mode.",
                    {"status": variant.status},
                )
            )

            video_step = self.generate_video(variant.id)
            result.steps.append(video_step)
            result.video_job_id = video_step.entity_id

            video_job = self._require_video_job(result.video_job_id)
            VideoEngine(self.db).approve_video(video_job, reviewer_name="demo-engine")
            result.steps.append(
                self._step(
                    "approve_video",
                    "ok",
                    "video_job",
                    video_job.id,
                    "Video auto-approved in demo mode.",
                    {"status": video_job.status},
                )
            )

            package = PublishingEngine(self.db).create_package(video_job.id, account.platform)
            package_step = self._step(
                "create_publishing_package",
                "ok",
                "publishing_package",
                package.id,
                f"Publishing package created for {account.platform}.",
                {"target_platform": package.target_platform, "status": package.status},
            )
            result.steps.append(package_step)
            result.publishing_package_id = package.id

            PublishingEngine(self.db).approve(package)
            result.steps.append(
                self._step(
                    "approve_publishing_package",
                    "ok",
                    "publishing_package",
                    package.id,
                    "Publishing package auto-approved in demo mode.",
                    {"status": package.status},
                )
            )

            schedule_step = self.schedule_publishing(package.id, account.id)
            result.steps.append(schedule_step)
            result.publishing_job_id = schedule_step.entity_id

            upload_step = self.run_upload(result.publishing_job_id)
            result.steps.append(upload_step)

            analytics_step = self.collect_analytics(result.publishing_job_id)
            result.steps.append(analytics_step)
            result.analytics_id = analytics_step.entity_id
            result.status = "completed"
        except EngineError as exc:
            result.status = "failed"
            result.errors.append(str(exc))
            result.steps.append(self._step("engine_error", "failed", None, None, str(exc)))
        except Exception as exc:
            result.status = "failed"
            result.errors.append(str(exc))
            result.steps.append(self._step("unexpected_error", "failed", None, None, str(exc)))
        return result

    def generate_script(self, product_id: int) -> EngineStepResult:
        product = self._require_product(product_id)
        brand_guide = self._select_brand_guide(product)
        template = self._select_template()
        script_job = ScriptEngine(self.db).generate(product.id, template.id, brand_guide.id)
        variant = self._first_variant(script_job)
        return self._step(
            "generate_script",
            "ok",
            "script_job",
            script_job.id,
            "Script generated from product, brand guide, and creative template.",
            {
                "product_id": product.id,
                "brand_guide_id": brand_guide.id,
                "template_id": template.id,
                "script_variant_id": variant.id,
                "validation": script_job.validation_report_json,
            },
        )

    def generate_video(self, script_variant_id: int) -> EngineStepResult:
        variant = self._require_script_variant(script_variant_id)
        if variant.status != WorkflowStatus.script_approved.value:
            raise EnginePreconditionError("Script variant must be approved before video generation.")
        video_job = VideoEngine(self.db).create_job(variant.id, provider="mock")
        video_job = VideoEngine(self.db).run(video_job)
        return self._step(
            "generate_video",
            "ok",
            "video_job",
            video_job.id,
            "Mock video generated and assembled.",
            {
                "status": video_job.status,
                "output_video_path": video_job.output_video_path,
                "preview_path": video_job.preview_path,
                "clip_count": len(video_job.clips),
            },
        )

    def create_publishing_package(self, video_job_id: int) -> EngineStepResult:
        video_job = self._require_video_job(video_job_id)
        if video_job.status != WorkflowStatus.video_approved.value:
            raise EnginePreconditionError("Video must be approved before package creation.")
        account = self._select_account(video_job.script_variant.script_job.product, None)
        package = PublishingEngine(self.db).create_package(video_job.id, account.platform)
        return self._step(
            "create_publishing_package",
            "ok",
            "publishing_package",
            package.id,
            f"Publishing package created for {account.platform}.",
            {"target_platform": package.target_platform, "status": package.status},
        )

    def schedule_publishing(self, package_id: int, account_id: int | None = None) -> EngineStepResult:
        package = self._require_package(package_id)
        account = self._select_account(package.product, account_id)
        scheduled_at, validation = self._find_schedule_slot(package, account)
        job = WarmupScheduler(self.db).schedule(
            package,
            account,
            scheduled_at,
            provider="mock",
            manual_override=False,
            operator_name="demo-engine",
        )
        return self._step(
            "schedule_publishing",
            "ok",
            "publishing_job",
            job.id,
            "Publishing job scheduled within warm-up limits.",
            {
                "account_id": account.id,
                "scheduled_at": job.scheduled_at.isoformat(),
                "provider": job.provider,
                "warmup_validation": validation,
            },
        )

    def run_upload(self, publishing_job_id: int) -> EngineStepResult:
        job = self._require_publishing_job(publishing_job_id)
        job = UploadService(self.db).run_job(job)
        return self._step(
            "run_upload",
            "ok" if job.status == WorkflowStatus.published.value else "needs_attention",
            "publishing_job",
            job.id,
            "Mock upload completed." if job.status == WorkflowStatus.published.value else "Upload requires attention.",
            {
                "status": job.status,
                "provider_post_id": job.provider_post_id,
                "provider_post_url": job.provider_post_url,
                "manual_upload_required": job.manual_upload_required,
            },
        )

    def collect_analytics(self, publishing_job_id: int) -> EngineStepResult:
        job = self._require_publishing_job(publishing_job_id)
        analytics = AnalyticsService(self.db).collect_for_job(job)
        return self._step(
            "collect_analytics",
            "ok",
            "publish_analytics",
            analytics.id,
            "Fake analytics collected from mock provider.",
            {
                "publishing_job_id": job.id,
                "views": analytics.views,
                "likes": analytics.likes,
                "comments": analytics.comments,
                "clicks": analytics.clicks,
                "ctr": analytics.ctr,
            },
        )

    def status_for_publishing_job(self, publishing_job_id: int) -> dict:
        job = self._require_publishing_job(publishing_job_id)
        latest_analytics = (
            self.db.scalars(
                select(models.PublishAnalytics)
                .where(models.PublishAnalytics.publishing_job_id == job.id)
                .order_by(models.PublishAnalytics.collected_at.desc())
            )
            .first()
        )
        return {
            "publishing_job_id": job.id,
            "status": job.status,
            "provider": job.provider,
            "provider_post_id": job.provider_post_id,
            "provider_post_url": job.provider_post_url,
            "manual_upload_required": job.manual_upload_required,
            "account_id": job.account_id,
            "publishing_package_id": job.publishing_package_id,
            "analytics_id": latest_analytics.id if latest_analytics else None,
            "analytics": {
                "views": latest_analytics.views,
                "likes": latest_analytics.likes,
                "comments": latest_analytics.comments,
                "clicks": latest_analytics.clicks,
                "ctr": latest_analytics.ctr,
            }
            if latest_analytics
            else None,
        }

    def _find_schedule_slot(
        self,
        package: models.PublishingPackage,
        account: models.PublishingAccount,
    ) -> tuple[datetime, dict]:
        scheduler = WarmupScheduler(self.db)
        start = datetime.now(UTC).replace(tzinfo=None, microsecond=0) + timedelta(days=1)
        for offset_days in range(0, 45):
            candidate = (start + timedelta(days=offset_days)).replace(hour=10, minute=0, second=0)
            validation = scheduler.validate_schedule(package, account, candidate)
            if validation["allowed"]:
                return candidate, validation
        raise EnginePreconditionError("No warm-up compliant publishing slot found in the next 45 days.")

    def _select_template(self) -> models.CreativeTemplate:
        template = self.db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
        if not template:
            raise EngineNotFoundError("No creative templates found. Run python scripts/seed.py first.")
        return template

    def _select_brand_guide(self, product: models.Product) -> models.BrandGuide:
        guide = self.db.scalar(
            select(models.BrandGuide)
            .where(models.BrandGuide.brand == product.brand)
            .order_by(models.BrandGuide.id)
        )
        if not guide:
            guide = self.db.scalar(select(models.BrandGuide).order_by(models.BrandGuide.id))
        if not guide:
            raise EngineNotFoundError("No brand guides found. Run python scripts/seed.py first.")
        return guide

    def _select_account(self, product: models.Product, account_id: int | None) -> models.PublishingAccount:
        if account_id is not None:
            account = self.db.get(models.PublishingAccount, account_id)
            if not account:
                raise EngineNotFoundError(f"Publishing account {account_id} not found.")
            if account.brand != product.brand:
                raise EnginePreconditionError(
                    f"Publishing account {account.id} belongs to {account.brand}, not {product.brand}."
                )
            return account

        account = self.db.scalar(
            select(models.PublishingAccount)
            .where(models.PublishingAccount.brand == product.brand)
            .order_by(models.PublishingAccount.id)
        )
        if not account:
            account = self.db.scalar(select(models.PublishingAccount).order_by(models.PublishingAccount.id))
        if not account:
            raise EngineNotFoundError("No publishing accounts found. Run python scripts/seed.py first.")
        return account

    def _require_product(self, product_id: int) -> models.Product:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise EngineNotFoundError(f"Product {product_id} not found.")
        return product

    def _require_script_job(self, script_job_id: int | None) -> models.ScriptJob:
        if script_job_id is None:
            raise EnginePreconditionError("Script job id is missing.")
        script_job = self.db.get(models.ScriptJob, script_job_id)
        if not script_job:
            raise EngineNotFoundError(f"Script job {script_job_id} not found.")
        return script_job

    def _require_script_variant(self, script_variant_id: int) -> models.ScriptVariant:
        variant = self.db.get(models.ScriptVariant, script_variant_id)
        if not variant:
            raise EngineNotFoundError(f"Script variant {script_variant_id} not found.")
        return variant

    def _require_video_job(self, video_job_id: int | None) -> models.VideoJob:
        if video_job_id is None:
            raise EnginePreconditionError("Video job id is missing.")
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise EngineNotFoundError(f"Video job {video_job_id} not found.")
        return video_job

    def _require_package(self, package_id: int) -> models.PublishingPackage:
        package = self.db.get(models.PublishingPackage, package_id)
        if not package:
            raise EngineNotFoundError(f"Publishing package {package_id} not found.")
        return package

    def _require_publishing_job(self, publishing_job_id: int | None) -> models.PublishingJob:
        if publishing_job_id is None:
            raise EnginePreconditionError("Publishing job id is missing.")
        job = self.db.get(models.PublishingJob, publishing_job_id)
        if not job:
            raise EngineNotFoundError(f"Publishing job {publishing_job_id} not found.")
        return job

    @staticmethod
    def _first_variant(script_job: models.ScriptJob) -> models.ScriptVariant:
        if not script_job.variants:
            raise EnginePreconditionError("Script job has no variants.")
        return sorted(script_job.variants, key=lambda item: item.variant_number)[0]

    @staticmethod
    def _step(
        step_name: str,
        status: str,
        entity_type: str | None,
        entity_id: int | None,
        message: str,
        data: dict | None = None,
    ) -> EngineStepResult:
        return EngineStepResult(
            step_name=step_name,
            status=status,
            entity_type=entity_type,
            entity_id=entity_id,
            message=message,
            data=data or {},
        )

