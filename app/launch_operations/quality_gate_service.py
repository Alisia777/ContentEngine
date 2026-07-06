from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.launch_operations.errors import LaunchOperationsDataError
from app.launch_operations.types import LaunchQualityGateResult


APPROVED_REVIEW_STATUSES = {"approved", "human_approved"}
NEEDS_REVIEW_STATUSES = {"needs_human_review", "needs_review", "metadata_scored", "pending"}
REGENERATION_STATUSES = {"requested", "queued", "prompt_ready", "failed"}
GENERATED_VIDEO_STATUSES = {"generated", "completed", "video_generated", "video_approved", "approved", "real_smoke_created"}


class QualityGateService:
    def __init__(self, db: Session):
        self.db = db

    def refresh(self, campaign_id: int) -> list[LaunchQualityGateResult]:
        campaign = self._campaign(campaign_id)
        gates = []
        for item, product, run in self._video_runs(campaign):
            gate = self._create_gate(campaign, item, product, run)
            gates.append(gate)
        return gates

    def list_latest(self, campaign_id: int) -> list[LaunchQualityGateResult]:
        gates = self.db.scalars(
            select(models.LaunchQualityGate)
            .where(models.LaunchQualityGate.campaign_id == campaign_id)
            .order_by(models.LaunchQualityGate.id.desc())
        ).all()
        if not gates:
            return self.refresh(campaign_id)
        latest_by_video: dict[int | str, models.LaunchQualityGate] = {}
        for gate in gates:
            key: int | str = gate.video_job_id or f"gate-{gate.id}"
            latest_by_video.setdefault(key, gate)
        return [self._result(gate) for gate in sorted(latest_by_video.values(), key=lambda item: item.id)]

    def _campaign(self, campaign_id: int) -> models.Campaign:
        campaign = self.db.get(models.Campaign, campaign_id)
        if not campaign:
            raise LaunchOperationsDataError(f"Campaign {campaign_id} not found.")
        return campaign

    def _video_runs(self, campaign: models.Campaign) -> list[tuple[models.CampaignProduct, models.Product | None, models.ContentRun | None]]:
        items = self.db.scalars(
            select(models.CampaignProduct).where(models.CampaignProduct.campaign_id == campaign.id).order_by(models.CampaignProduct.id)
        ).all()
        result = []
        for item in items:
            product = self.db.get(models.Product, item.product_id)
            runs = self._content_runs(item)
            video_runs = [run for run in runs if run.video_job_id or self._generation_variant(run)]
            if video_runs:
                result.extend((item, product, run) for run in video_runs)
            else:
                result.append((item, product, None))
        return result

    def _content_runs(self, item: models.CampaignProduct) -> list[models.ContentRun]:
        run_ids = [int(run_id) for run_id in (item.content_run_ids_json or [])]
        if run_ids:
            return self.db.scalars(select(models.ContentRun).where(models.ContentRun.id.in_(run_ids)).order_by(models.ContentRun.id)).all()
        return self.db.scalars(select(models.ContentRun).where(models.ContentRun.product_id == item.product_id).order_by(models.ContentRun.id)).all()

    def _create_gate(
        self,
        campaign: models.Campaign,
        item: models.CampaignProduct,
        product: models.Product | None,
        content_run: models.ContentRun | None,
    ) -> LaunchQualityGateResult:
        generation_variant = self._generation_variant(content_run) if content_run else None
        video_job = self._video_job(content_run, generation_variant)
        review = self._latest_review(video_job, generation_variant)
        blockers = []
        required_fixes = []
        quality_review_status = review.status if review else "missing"
        human_visual_status = self._human_visual_status(review)
        product_identity_status = self._product_identity_status(review, content_run)
        geometry_status = self._geometry_status(review, content_run)

        if not video_job:
            blockers.append({"blocker": "prompt_only_not_publishable", "source": "quality_gate"})
            required_fixes.append({"action": "run_real_smoke_for_ready_items", "reason": "Prompt-only content is not a publishable video."})
        elif video_job.status not in GENERATED_VIDEO_STATUSES and not video_job.output_video_path:
            blockers.append({"blocker": "video_output_missing", "source": "quality_gate", "video_job_id": video_job.id})
            required_fixes.append({"action": "inspect_video_generation", "reason": "Video output is not generated yet."})
        if video_job and not review:
            blockers.append({"blocker": "missing_quality_review", "source": "quality_gate", "video_job_id": video_job.id})
            required_fixes.append({"action": "review_video", "reason": "Video must have a quality review before publishing."})
        if quality_review_status in NEEDS_REVIEW_STATUSES or human_visual_status in {"needs_review", "pending"}:
            blockers.append({"blocker": "needs_human_review", "source": "quality_gate"})
            required_fixes.append({"action": "approve_or_reject_video", "reason": "Human review is required."})
        if self._needs_regeneration(video_job, generation_variant, review):
            blockers.append({"blocker": "needs_regeneration", "source": "quality_gate"})
            required_fixes.append({"action": "request_regeneration", "reason": "Video quality failed or has an open regeneration request."})
        if product_identity_status in {"mismatch", "failed", "blocked"}:
            blockers.append({"blocker": "product_identity_mismatch", "source": "quality_gate"})
            required_fixes.append({"action": "attach_product_reference", "reason": "Product identity must be corrected before publishing."})
        if geometry_status in {"mismatch", "missing", "failed", "blocked"}:
            blockers.append({"blocker": "product_geometry_mismatch", "source": "quality_gate"})
            required_fixes.append({"action": "add_geometry_lock", "reason": "Geometry/scale lock must be ready before publishing."})
        blockers = self._dedupe(blockers)
        required_fixes = self._dedupe(required_fixes, key_fields=("action", "reason"))
        publishing_allowed = not blockers and quality_review_status in APPROVED_REVIEW_STATUSES
        gate = models.LaunchQualityGate(
            campaign_id=campaign.id,
            video_job_id=video_job.id if video_job else None,
            creative_variant_id=(generation_variant.creative_variant_id if generation_variant else content_run.selected_variant_id if content_run else None),
            product_id=item.product_id,
            sku=item.sku or (product.sku if product else None),
            status="allowed" if publishing_allowed else "blocked",
            quality_review_status=quality_review_status,
            human_visual_status=human_visual_status,
            product_identity_status=product_identity_status,
            geometry_status=geometry_status,
            publishing_allowed=publishing_allowed,
            blockers_json=blockers,
            required_fixes_json=required_fixes,
        )
        self.db.add(gate)
        self.db.commit()
        self.db.refresh(gate)
        return self._result(gate)

    def _video_job(
        self,
        content_run: models.ContentRun | None,
        generation_variant: models.VideoGenerationVariant | None,
    ) -> models.VideoJob | None:
        if content_run and content_run.video_job_id:
            return self.db.get(models.VideoJob, content_run.video_job_id)
        if generation_variant and generation_variant.video_job_id:
            return self.db.get(models.VideoJob, generation_variant.video_job_id)
        return None

    def _generation_variant(self, content_run: models.ContentRun | None) -> models.VideoGenerationVariant | None:
        if not content_run:
            return None
        if content_run.generation_variant_id:
            variant = self.db.get(models.VideoGenerationVariant, content_run.generation_variant_id)
            if variant:
                return variant
        if content_run.video_job_id:
            return self.db.scalar(
                select(models.VideoGenerationVariant)
                .where(models.VideoGenerationVariant.video_job_id == content_run.video_job_id)
                .order_by(models.VideoGenerationVariant.id.desc())
            )
        return None

    def _latest_review(
        self,
        video_job: models.VideoJob | None,
        generation_variant: models.VideoGenerationVariant | None,
    ) -> models.VideoQualityReview | None:
        query = select(models.VideoQualityReview)
        if video_job:
            query = query.where(models.VideoQualityReview.video_job_id == video_job.id)
        elif generation_variant:
            query = query.where(models.VideoQualityReview.video_generation_variant_id == generation_variant.id)
        else:
            return None
        return self.db.scalar(query.order_by(models.VideoQualityReview.id.desc()))

    def _needs_regeneration(
        self,
        video_job: models.VideoJob | None,
        generation_variant: models.VideoGenerationVariant | None,
        review: models.VideoQualityReview | None,
    ) -> bool:
        if review and review.status in {"needs_regeneration", "rejected", "failed"}:
            return True
        if review and (review.review_json or {}).get("needs_regeneration"):
            return True
        if not video_job and not generation_variant:
            return False
        query = select(models.SceneRegenerationRequest)
        if video_job:
            query = query.where(models.SceneRegenerationRequest.video_job_id == video_job.id)
        elif generation_variant:
            query = query.where(models.SceneRegenerationRequest.video_generation_variant_id == generation_variant.id)
        requests = self.db.scalars(query).all()
        return any(request.status in REGENERATION_STATUSES for request in requests)

    @staticmethod
    def _human_visual_status(review: models.VideoQualityReview | None) -> str:
        if not review:
            return "needs_review"
        payload = review.review_json or {}
        return payload.get("human_visual_status") or ("approved" if review.status in APPROVED_REVIEW_STATUSES else "needs_review")

    @staticmethod
    def _product_identity_status(review: models.VideoQualityReview | None, content_run: models.ContentRun | None) -> str:
        payload = review.review_json if review else {}
        status = (payload or {}).get("product_identity_status")
        if status:
            return status
        blockers = [*(content_run.blockers_json if content_run else []), *((content_run.run_json or {}).get("product_identity_blockers", []) if content_run else [])]
        if any("identity" in blocker for blocker in blockers):
            return "blocked"
        return "ready" if review and review.status in APPROVED_REVIEW_STATUSES else "unknown"

    @staticmethod
    def _geometry_status(review: models.VideoQualityReview | None, content_run: models.ContentRun | None) -> str:
        payload = review.review_json if review else {}
        status = (payload or {}).get("geometry_status") or (payload or {}).get("product_geometry_status")
        if status:
            return status
        blockers = [*(content_run.blockers_json if content_run else []), *((content_run.run_json or {}).get("geometry_scale_blockers", []) if content_run else [])]
        if any("geometry" in blocker or "scale" in blocker for blocker in blockers):
            return "missing"
        return "ready" if review and review.status in APPROVED_REVIEW_STATUSES else "unknown"

    @staticmethod
    def _dedupe(items: list[dict], *, key_fields: tuple[str, ...] = ("source", "blocker")) -> list[dict]:
        deduped = []
        seen = set()
        for item in items:
            key = tuple(item.get(field) for field in key_fields)
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    @staticmethod
    def _result(gate: models.LaunchQualityGate) -> LaunchQualityGateResult:
        return LaunchQualityGateResult(
            gate_id=gate.id,
            campaign_id=gate.campaign_id,
            video_job_id=gate.video_job_id,
            creative_variant_id=gate.creative_variant_id,
            product_id=gate.product_id,
            sku=gate.sku,
            status=gate.status,
            quality_review_status=gate.quality_review_status,
            human_visual_status=gate.human_visual_status,
            product_identity_status=gate.product_identity_status,
            geometry_status=gate.geometry_status,
            publishing_allowed=gate.publishing_allowed,
            blockers=gate.blockers_json or [],
            required_fixes=gate.required_fixes_json or [],
            generated_at=gate.created_at,
        )
