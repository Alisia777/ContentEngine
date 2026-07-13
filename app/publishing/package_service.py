from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.publishing.errors import (
    PublishingAuthorizationError,
    PublishingError,
    PublishingSourceNotFound,
    PublishingSourceStateError,
)
from app.publishing.types import PUBLISHABLE_MEDIA_ARTIFACT_KINDS


SUCCESS_PROVIDER_STATUSES = frozenset(
    {"SUCCEEDED", "SUCCESS", "COMPLETED", "COMPLETE", "DONE"}
)


class PublishingPackageService:
    ARTIFACT_APPROVER_ROLES = frozenset({"owner", "admin", "reviewer"})

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

    def create_from_media_artifact(
        self,
        *,
        public_id: str | None = None,
        media_artifact_id: int | None = None,
        organization_id: int,
        actor_user_profile_id: int,
        platform: str,
        confirm_human_review: bool,
        title: str | None = None,
        description: str | None = None,
        hashtags: list[str] | None = None,
        cta: str | None = None,
    ) -> models.PublishingPackage:
        """Approve one durable tenant video and create its package exactly once.

        This path deliberately never asks a storage backend for a signed URL.
        The package stores only the MediaArtifact foreign key and immutable
        integrity/audit facts; access capabilities remain short-lived.
        """

        membership, profile = self._require_artifact_approver(
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
        )
        if confirm_human_review is not True:
            raise PublishingSourceStateError(
                "Explicit human review confirmation is required before packaging media."
            )

        artifact_query = select(models.MediaArtifact).where(
            models.MediaArtifact.organization_id == int(organization_id)
        )
        if public_id is not None:
            artifact_query = artifact_query.where(
                models.MediaArtifact.public_id == str(public_id)
            )
        if media_artifact_id is not None:
            artifact_query = artifact_query.where(
                models.MediaArtifact.id == int(media_artifact_id)
            )
        artifact = (
            self.db.scalar(artifact_query)
            if public_id is not None or media_artifact_id is not None
            else None
        )
        if artifact is None:
            raise PublishingSourceNotFound("Media artifact was not found in this organization.")
        product, video_job = self._validate_media_artifact_source(
            artifact,
            organization_id=organization_id,
        )
        normalized_platform = self._platform(platform)

        existing = self._artifact_package(
            organization_id=organization_id,
            media_artifact_id=artifact.id,
            platform=normalized_platform,
        )
        if existing is not None:
            if existing.status != "approved" or existing.review_status != "approved":
                raise PublishingSourceStateError(
                    "A package already exists for this artifact and platform but is not approved."
                )
            return existing

        generation_variant = (
            self._generation_variant_for_video(video_job.id) if video_job is not None else None
        )
        reviewed_at = models.utcnow()
        package = models.PublishingPackage(
            organization_id=organization_id,
            video_job_id=video_job.id if video_job is not None else None,
            media_artifact_id=artifact.id,
            creative_variant_id=generation_variant.creative_variant_id if generation_variant else None,
            product_id=product.id,
            brand=product.brand,
            target_platform=normalized_platform,
            title=title or self._title(product, normalized_platform),
            description=description or self._description(product, normalized_platform),
            hashtags_json=(
                hashtags if hashtags is not None else self._hashtags(product, normalized_platform)
            ),
            cta=cta or (self._cta(video_job) if video_job is not None else "Open the product card"),
            product_url=product.product_url,
            utm_url=self._utm(product.product_url, normalized_platform),
            cover_image_path=None,
            video_file_path=None,
            metadata_json={
                "workflow": "cloud_media_artifact_publishing_v1",
                "source_media": {
                    "type": "media_artifact",
                    "media_artifact_id": artifact.id,
                    "sha256": artifact.sha256,
                    "mime_type": artifact.mime_type,
                    "size_bytes": artifact.size_bytes,
                },
                "human_review": {
                    "confirmed": True,
                    "reviewer_user_profile_id": profile.id,
                    "reviewer_role": membership.role,
                    "reviewed_at": reviewed_at.isoformat(),
                },
                "safety_rules": [
                    "Tenant-owned ready video only",
                    "Human review required",
                    "No persisted signed media URL",
                    "No auto-publish before destination validation",
                ],
            },
            ai_generated_flag=True,
            review_status="approved",
            status="approved",
        )
        self.db.add(package)
        try:
            self.db.flush()
            self.db.add(
                models.Review(
                    entity_type="publishing_package",
                    entity_id=package.id,
                    reviewer_name=profile.display_name or profile.email,
                    status="approved",
                    comment="Human reviewed the ready cloud video artifact for publishing.",
                )
            )
            self.db.commit()
            self.db.refresh(package)
            return package
        except IntegrityError:
            self.db.rollback()
            winner = self._artifact_package(
                organization_id=organization_id,
                media_artifact_id=artifact.id,
                platform=normalized_platform,
            )
            if winner is not None and winner.status == "approved" and winner.review_status == "approved":
                return winner
            raise

    def approve(
        self,
        package: models.PublishingPackage,
        *,
        reviewer_name: str = "operator",
        manual_override: bool = False,
        notes: str | None = None,
    ) -> models.PublishingPackage:
        if package.media_artifact_id is not None:
            raise PublishingAuthorizationError(
                "Media artifact packages require organization-scoped human review approval."
            )
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

    def _require_artifact_approver(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
    ) -> tuple[models.Membership, models.UserProfile]:
        organization = self.db.get(models.Organization, organization_id)
        profile = self.db.get(models.UserProfile, actor_user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == int(organization_id),
                models.Membership.user_profile_id == int(actor_user_profile_id),
                models.Membership.status == "active",
            )
        )
        if (
            organization is None
            or organization.status != "active"
            or profile is None
            or not profile.is_active
            or profile.status != "active"
            or membership is None
            or str(membership.role).casefold() not in self.ARTIFACT_APPROVER_ROLES
        ):
            raise PublishingAuthorizationError(
                "Owner, admin, or reviewer membership is required for media approval."
            )
        return membership, profile

    def _validate_media_artifact_source(
        self,
        artifact: models.MediaArtifact,
        *,
        organization_id: int,
    ) -> tuple[models.Product, models.VideoJob | None]:
        if (
            artifact.organization_id != int(organization_id)
            or artifact.status != "ready"
            or artifact.archived_at is not None
            or artifact.delete_requested_at is not None
            or artifact.deleted_at is not None
            or artifact.kind not in PUBLISHABLE_MEDIA_ARTIFACT_KINDS
            or not str(artifact.mime_type or "").casefold().startswith("video/")
            or int(artifact.size_bytes or 0) <= 0
            or not re.fullmatch(r"[a-f0-9]{64}", str(artifact.sha256 or "").casefold())
            or not artifact.object_key.startswith(
                f"organizations/{int(organization_id):08d}/"
            )
        ):
            raise PublishingSourceStateError(
                "Only a ready, non-archived video artifact can be packaged."
            )
        if artifact.product_id is None:
            raise PublishingSourceStateError("Publishing media must be linked to a product.")
        product = self.db.get(models.Product, artifact.product_id)
        if product is None or product.organization_id != int(organization_id):
            raise PublishingSourceStateError(
                "Media artifact product ownership does not match the organization."
            )
        if artifact.product_ugc_recipe_draft_id is not None:
            draft = self.db.get(
                models.ProductUGCRecipeDraft,
                artifact.product_ugc_recipe_draft_id,
            )
            self._validate_product_ugc_review_lineage(
                artifact,
                draft=draft,
                organization_id=organization_id,
                product_id=product.id,
            )
        video_job = self.db.get(models.VideoJob, artifact.video_job_id) if artifact.video_job_id else None
        if artifact.video_job_id and (
            video_job is None
            or video_job.organization_id != int(organization_id)
            or video_job.product_id != product.id
        ):
            raise PublishingSourceStateError(
                "Media artifact video lineage does not match its organization and product."
            )
        return product, video_job

    def _validate_product_ugc_review_lineage(
        self,
        artifact: models.MediaArtifact,
        *,
        draft: models.ProductUGCRecipeDraft | None,
        organization_id: int,
        product_id: int,
    ) -> None:
        """Bind packaging to the exact Product UGC bytes a human approved."""

        if (
            draft is None
            or draft.product_id != int(product_id)
            or draft.product is None
            or draft.product.organization_id != int(organization_id)
        ):
            raise PublishingSourceStateError(
                "Product UGC review lineage does not match this organization and product."
            )
        if (
            draft.human_review_status != "approved"
            or draft.publishing_readiness != "ready_for_publishing_package"
            or bool(draft.blockers_json)
        ):
            raise PublishingSourceStateError(
                "Product UGC video must be approved and ready for a publishing package."
            )
        if (
            not draft.provider_task_id
            or str(draft.provider_status or "").upper()
            not in SUCCESS_PROVIDER_STATUSES
        ):
            raise PublishingSourceStateError(
                "Product UGC package requires a successful provider generation."
            )

        ready_video_ids = list(
            self.db.scalars(
                select(models.MediaArtifact.id)
                .where(
                    models.MediaArtifact.organization_id == int(organization_id),
                    models.MediaArtifact.product_id == int(product_id),
                    models.MediaArtifact.product_ugc_recipe_draft_id == draft.id,
                    models.MediaArtifact.kind.in_(PUBLISHABLE_MEDIA_ARTIFACT_KINDS),
                    models.MediaArtifact.mime_type.like("video/%"),
                    models.MediaArtifact.size_bytes > 0,
                    models.MediaArtifact.status == "ready",
                    models.MediaArtifact.archived_at.is_(None),
                    models.MediaArtifact.delete_requested_at.is_(None),
                    models.MediaArtifact.deleted_at.is_(None),
                )
                .order_by(models.MediaArtifact.id)
                .limit(2)
            )
        )
        if ready_video_ids != [artifact.id]:
            raise PublishingSourceStateError(
                "Product UGC packaging requires exactly one reviewed ready video output."
            )

        artifact_provider_task_id = str(
            (artifact.metadata_json or {}).get("provider_task_id") or ""
        ).strip()
        if artifact_provider_task_id != str(draft.provider_task_id).strip():
            raise PublishingSourceStateError(
                "Product UGC artifact does not match the successful provider task."
            )

        creative_inputs = dict(draft.creative_inputs_json or {})
        blocked_identities = [
            item
            for item in list(creative_inputs.get("blocked_media_artifacts_v1") or [])
            if isinstance(item, dict)
        ]
        if any(
            item.get("media_artifact_id") == artifact.id
            or item.get("public_id") == artifact.public_id
            or item.get("sha256") == artifact.sha256
            for item in blocked_identities
        ):
            raise PublishingSourceStateError(
                "This exact Product UGC output was rejected; generate a new output before packaging."
            )

        approved_identity = creative_inputs.get("approved_media_artifact_v1")
        identity_matches = bool(
            isinstance(approved_identity, dict)
            and approved_identity.get("media_artifact_id") == artifact.id
            and approved_identity.get("public_id") == artifact.public_id
            and approved_identity.get("sha256") == artifact.sha256
            and str(approved_identity.get("provider_task_id") or "").strip()
            == str(draft.provider_task_id).strip()
        )
        if not identity_matches:
            approved_tasks = list(
                self.db.scalars(
                    select(models.CreatorTask).where(
                        models.CreatorTask.organization_id == int(organization_id),
                        models.CreatorTask.product_ugc_recipe_draft_id == draft.id,
                        models.CreatorTask.media_artifact_id == artifact.id,
                        models.CreatorTask.task_type == "review_generated_video",
                        models.CreatorTask.status == "done",
                    )
                )
            )
            identity_matches = any(
                dict(task.result_json or {}).get("review_decision") == "approve"
                and dict(task.result_json or {}).get("media_artifact_public_id")
                == artifact.public_id
                for task in approved_tasks
            )
        if not identity_matches:
            raise PublishingSourceStateError(
                "Product UGC package must reference the exact artifact approved by human review."
            )

    def _artifact_package(
        self,
        *,
        organization_id: int,
        media_artifact_id: int,
        platform: str,
    ) -> models.PublishingPackage | None:
        return self.db.scalar(
            select(models.PublishingPackage).where(
                models.PublishingPackage.organization_id == int(organization_id),
                models.PublishingPackage.media_artifact_id == int(media_artifact_id),
                models.PublishingPackage.target_platform == platform,
            )
        )

    @staticmethod
    def _platform(value: str) -> str:
        platform = " ".join(str(value or "").strip().casefold().split())
        if not platform or len(platform) > 120 or any(ord(character) < 32 for character in platform):
            raise PublishingSourceStateError("A valid target platform is required.")
        return platform

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
