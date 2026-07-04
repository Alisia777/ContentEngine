from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.publishing.errors import PublishingError


class PublishingPackageService:
    def __init__(self, db: Session):
        self.db = db

    def create_from_video(
        self,
        *,
        video_job_id: int,
        platform: str,
        title: str | None = None,
        description: str | None = None,
        hashtags: list[str] | None = None,
        cta: str | None = None,
        cover_image_path: str | None = None,
    ) -> models.PublishingPackage:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise PublishingError("Video job not found.")
        self._validate_video_file(video_job.output_video_path)
        product = self._product_for_video(video_job)
        generation_variant = self._generation_variant_for_video(video_job.id)
        review_status = self._review_status(video_job)
        package = models.PublishingPackage(
            video_job_id=video_job.id,
            creative_variant_id=generation_variant.creative_variant_id if generation_variant else None,
            product_id=product.id,
            brand=product.brand,
            target_platform=platform,
            title=title or self._title(product, platform),
            description=description or self._description(product, platform),
            hashtags_json=hashtags or self._hashtags(product, platform),
            cta=cta or self._cta(video_job),
            product_url=product.product_url,
            utm_url=self._utm(product.product_url, platform),
            cover_image_path=cover_image_path or video_job.preview_path,
            video_file_path=video_job.output_video_path,
            metadata_json=self._metadata(video_job, generation_variant, review_status),
            ai_generated_flag=True,
            review_status=review_status,
            status="ready" if review_status == "approved" else "draft",
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def approve(
        self,
        package: models.PublishingPackage,
        *,
        reviewer_name: str = "operator",
        manual_override: bool = False,
        notes: str | None = None,
    ) -> models.PublishingPackage:
        self._validate_video_file(package.video_file_path)
        quality_status = self._review_status(package.video_job)
        if quality_status != "approved" and not manual_override:
            raise PublishingError("QualityReview is not approved; explicit manual override is required.")
        package.status = "approved"
        package.review_status = "approved"
        package.metadata_json = {
            **(package.metadata_json or {}),
            "approval": {
                "reviewer_name": reviewer_name,
                "manual_override": manual_override,
                "notes": notes,
                "source_quality_review_status": quality_status,
            },
        }
        self.db.add(
            models.Review(
                entity_type="publishing_package",
                entity_id=package.id,
                reviewer_name=reviewer_name,
                status="approved",
                comment=notes or "Publishing package approved for scheduling.",
            )
        )
        self.db.commit()
        self.db.refresh(package)
        return package

    def reject(self, package: models.PublishingPackage, reason: str, reviewer_name: str = "operator") -> models.PublishingPackage:
        package.status = "rejected"
        package.review_status = "rejected"
        self.db.add(
            models.Review(
                entity_type="publishing_package",
                entity_id=package.id,
                reviewer_name=reviewer_name,
                status="rejected",
                rejection_reason=reason,
            )
        )
        self.db.commit()
        self.db.refresh(package)
        return package

    def _product_for_video(self, video_job: models.VideoJob) -> models.Product:
        generation_variant = self._generation_variant_for_video(video_job.id)
        if generation_variant and generation_variant.creative_spec:
            return generation_variant.creative_spec.product
        if video_job.script_variant and video_job.script_variant.script_job:
            return video_job.script_variant.script_job.product
        raise PublishingError("Cannot resolve product for video job.")

    def _generation_variant_for_video(self, video_job_id: int) -> models.VideoGenerationVariant | None:
        return self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.video_job_id == video_job_id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )

    def _review_status(self, video_job: models.VideoJob) -> str:
        review = self.db.scalar(
            select(models.VideoQualityReview)
            .where(models.VideoQualityReview.video_job_id == video_job.id)
            .order_by(models.VideoQualityReview.id.desc())
        )
        if review:
            return "approved" if review.status == "approved" else "needs_review"
        return "approved" if video_job.status == "video_approved" else "needs_review"

    @staticmethod
    def _validate_video_file(video_file_path: str | None) -> None:
        if not video_file_path:
            raise PublishingError("Video file path is missing.")
        path = Path(video_file_path)
        if not path.exists() or path.stat().st_size <= 0:
            raise PublishingError("Video file must exist and be non-empty.")

    @staticmethod
    def _title(product: models.Product, platform: str) -> str:
        return f"{product.title} | {platform} video"

    @staticmethod
    def _description(product: models.Product, platform: str) -> str:
        benefit = (product.benefits_json or ["Product details in the card"])[0]
        return f"{product.title}: {benefit}. Prepared for {platform}; operator must review before publishing."

    @staticmethod
    def _hashtags(product: models.Product, platform: str) -> list[str]:
        tokens = [product.brand, product.category or "product", platform]
        return ["#" + token.replace(" ", "").replace("/", "").lower() for token in tokens if token]

    @staticmethod
    def _cta(video_job: models.VideoJob) -> str:
        variant = video_job.script_variant
        return (variant.final_cta if variant else None) or "Open the product card"

    @staticmethod
    def _utm(product_url: str | None, platform: str) -> str | None:
        if not product_url:
            return None
        parts = urlsplit(product_url)
        query = dict(parse_qsl(parts.query))
        query.update(
            {
                "utm_source": platform.lower().replace(" ", "_"),
                "utm_medium": "social_video",
                "utm_campaign": "contentengine_publishing",
            }
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @staticmethod
    def _metadata(
        video_job: models.VideoJob,
        generation_variant: models.VideoGenerationVariant | None,
        review_status: str,
    ) -> dict:
        return {
            "workflow": "safe_manual_publishing_v1",
            "video_job_status": video_job.status,
            "quality_review_status": review_status,
            "generation_variant_id": generation_variant.id if generation_variant else None,
            "safety_rules": [
                "No auto-publish before approval",
                "Manual destination/account registry only",
                "No fake engagement",
                "Final URL stored only after operator upload",
            ],
        }
