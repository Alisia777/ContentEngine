from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app import models
from app.enums import WorkflowStatus


class PublishingEngine:
    def __init__(self, db: Session):
        self.db = db

    def create_package(self, video_job_id: int, target_platform: str) -> models.PublishingPackage:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise ValueError("Video job not found")
        if video_job.status != WorkflowStatus.video_approved.value:
            raise ValueError("Video must be approved before creating a publishing package")
        product = video_job.script_variant.script_job.product
        package = models.PublishingPackage(
            video_job_id=video_job.id,
            product_id=product.id,
            brand=product.brand,
            target_platform=target_platform,
            title=self._title(product, target_platform),
            description=self._description(product, video_job, target_platform),
            hashtags_json=self._hashtags(product, target_platform),
            cta=video_job.script_variant.final_cta or "Learn more in the product card",
            product_url=product.product_url,
            utm_url=self._utm(product.product_url, target_platform),
            cover_image_path=video_job.preview_path,
            video_file_path=video_job.output_video_path,
            metadata_json=self._metadata(video_job, target_platform),
            ai_generated_flag=True,
            status="draft",
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def regenerate_metadata(self, package: models.PublishingPackage) -> models.PublishingPackage:
        package.title = self._title(package.product, package.target_platform)
        package.description = self._description(package.product, package.video_job, package.target_platform)
        package.hashtags_json = self._hashtags(package.product, package.target_platform)
        package.utm_url = self._utm(package.product_url, package.target_platform)
        package.metadata_json = self._metadata(package.video_job, package.target_platform)
        self.db.commit()
        self.db.refresh(package)
        return package

    def approve(self, package: models.PublishingPackage) -> models.PublishingPackage:
        package.status = WorkflowStatus.publishing_package_ready.value
        self.db.add(
            models.Review(
                entity_type="publishing_package",
                entity_id=package.id,
                reviewer_name="admin",
                status="approved",
                comment="Publishing package approved for scheduling.",
            )
        )
        self.db.commit()
        self.db.refresh(package)
        return package

    def reject(self, package: models.PublishingPackage, reason: str = "Needs revision") -> models.PublishingPackage:
        package.status = "rejected"
        self.db.add(
            models.Review(
                entity_type="publishing_package",
                entity_id=package.id,
                reviewer_name="admin",
                status="rejected",
                rejection_reason=reason,
            )
        )
        self.db.commit()
        self.db.refresh(package)
        return package

    @staticmethod
    def _title(product: models.Product, platform: str) -> str:
        platform_label = platform.replace("_", " ").title()
        return f"{product.title} | {platform_label} short"

    @staticmethod
    def _description(product: models.Product, video_job: models.VideoJob, platform: str) -> str:
        benefit = (product.benefits_json or ["See product card for details"])[0]
        return (
            f"{product.title}: {benefit}. "
            f"AI-assisted product video prepared for {platform}. "
            "All claims should be checked against product data before publishing."
        )

    @staticmethod
    def _hashtags(product: models.Product, platform: str) -> list[str]:
        tokens = [product.brand, product.category or "product", platform]
        return ["#" + token.replace(" ", "").replace("/", "").lower() for token in tokens if token]

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
                "utm_campaign": "qharisma_video_factory",
            }
        )
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @staticmethod
    def _metadata(video_job: models.VideoJob, platform: str) -> dict:
        report = video_job.script_variant.script_job.validation_report_json or {}
        return {
            "target_platform": platform,
            "brand_safety_checks": [
                "No platform-bypass behavior",
                "No fake engagement",
                "Owned/authorized account required",
                "Manual approval required before schedule",
            ],
            "claim_validation": report,
            "ai_generated_content": True,
            "video_source": "mock_provider",
        }

