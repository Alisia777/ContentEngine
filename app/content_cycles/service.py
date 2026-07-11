from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.content_cycles.errors import (
    ContentCycleConflictError,
    ContentCycleError,
    ContentCycleOwnershipError,
    ContentCycleStateError,
)
from app.content_cycles.types import ContentCycleTrace
from app.output_acceptance.types import PASS_STATUSES
from app.publishing.scheduler import PublishingScheduler
from app.visual_evidence import (
    VisualEvidenceSnapshotError,
    VisualEvidenceSnapshotService,
)


SUCCESS_PROVIDER_STATUSES = {"SUCCEEDED", "SUCCESS", "COMPLETED", "COMPLETE", "DONE"}
BLOCKING_MEDIA_MARKERS = (
    "synthetic",
    "placeholder",
    "ffmpeg_extract_failed",
    "video_file_missing",
    "provider run failed",
)


class ContentCycleService:
    """Builds one exact Product UGC -> measurement-ready manual-publish lineage.

    This service never calls a provider, publishes a post, or creates a payout.
    It only materializes local canonical records after each prior safety gate has
    passed. Legacy unscoped products and destinations are deliberately rejected.
    """

    def __init__(self, db: Session):
        self.db = db

    def start_from_product_ugc(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        product_ugc_recipe_draft_id: int,
        idempotency_key: str | None = None,
    ) -> models.ContentCycle:
        self._require_actor(organization_id, actor_user_profile_id)
        key = self._idempotency_key(idempotency_key or f"product-ugc:{product_ugc_recipe_draft_id}")

        existing_by_key = self.db.scalar(
            select(models.ContentCycle).where(
                models.ContentCycle.organization_id == organization_id,
                models.ContentCycle.idempotency_key == key,
            )
        )
        if existing_by_key:
            if existing_by_key.product_ugc_recipe_draft_id != product_ugc_recipe_draft_id:
                raise ContentCycleConflictError("Idempotency key is already bound to another Product UGC draft.")
            return existing_by_key

        existing_by_source = self.db.scalar(
            select(models.ContentCycle).where(
                models.ContentCycle.product_ugc_recipe_draft_id == product_ugc_recipe_draft_id
            )
        )
        if existing_by_source:
            if existing_by_source.organization_id != organization_id:
                raise ContentCycleOwnershipError("Product UGC draft is already owned by another organization cycle.")
            if existing_by_source.idempotency_key != key:
                raise ContentCycleConflictError("Product UGC draft is already bound to a different idempotency key.")
            return existing_by_source

        draft = self.db.get(models.ProductUGCRecipeDraft, product_ugc_recipe_draft_id)
        if not draft:
            raise ContentCycleStateError(f"ProductUGCRecipeDraft {product_ugc_recipe_draft_id} not found.")
        product = self._require_owned_product(draft.product_id, organization_id)
        output_path = self._validated_product_ugc_output(draft)

        template = models.CreativeTemplate(
            name=f"__canonical_product_ugc_draft_{draft.id}__",
            description="Internal canonical bridge for a reviewed Product UGC provider artifact.",
            format="short_video",
            duration_seconds=draft.duration_seconds,
            aspect_ratio=self._aspect_ratio(draft.ratio),
            structure_json=["reviewed_product_ugc_provider_output"],
            platform_fit_json=[draft.platform],
        )
        brand_guide = models.BrandGuide(
            brand=product.brand,
            tone_of_voice="Use the exact, human-reviewed Product UGC source without inferred claims.",
            forbidden_claims_json=list(product.restrictions_json or []),
        )
        self.db.add_all([template, brand_guide])
        self.db.flush()

        script_job = models.ScriptJob(
            product_id=product.id,
            template_id=template.id,
            brand_guide_id=brand_guide.id,
            status="script_approved",
            input_payload_json={
                "source_type": "product_ugc_recipe_draft",
                "source_id": draft.id,
                "idempotency_key": key,
            },
            output_script_json={
                "product_info": draft.product_info,
                "user_concept": draft.user_concept,
                "human_review_notes": draft.human_review_notes,
            },
            validation_report_json={"approved_source": True, "inferred_content": False},
        )
        self.db.add(script_job)
        self.db.flush()
        script_variant = models.ScriptVariant(
            script_job_id=script_job.id,
            variant_number=1,
            creative_angle="reviewed_product_ugc_source",
            key_message=draft.product_info,
            full_script_json={
                "source_type": "product_ugc_recipe_draft",
                "source_id": draft.id,
                "user_concept": draft.user_concept,
            },
            status="script_approved",
        )
        self.db.add(script_variant)
        self.db.flush()
        self.db.add(
            models.Scene(
                script_variant_id=script_variant.id,
                scene_number=1,
                time_start=0,
                time_end=float(draft.duration_seconds),
                visual_description=draft.user_concept,
                video_prompt="Imported from the exact reviewed Product UGC provider output.",
                source_fields_json=["product_ugc_recipe_draft_id", str(draft.id)],
            )
        )

        video_job = models.VideoJob(
            script_variant_id=script_variant.id,
            organization_id=organization_id,
            created_by_user_profile_id=actor_user_profile_id,
            product_id=product.id,
            source_product_ugc_draft_id=draft.id,
            provider="runway_product_ugc_recipe",
            status="video_generated",
            aspect_ratio=self._aspect_ratio(draft.ratio),
            duration_seconds=draft.duration_seconds,
            output_video_path=output_path.as_posix(),
            cost_estimate=0,
        )
        self.db.add(video_job)
        self.db.flush()

        primary_asset = draft.primary_product_asset
        asset_metadata = (
            dict(primary_asset.metadata_json or {})
            if primary_asset is not None and primary_asset.product_id == product.id
            else {}
        )
        creative_inputs = (
            draft.creative_inputs_json
            if isinstance(draft.creative_inputs_json, dict)
            else {}
        )
        required_packaging_tokens = (
            creative_inputs.get("required_packaging_tokens")
            or asset_metadata.get("required_packaging_tokens")
            or []
        )
        if isinstance(required_packaging_tokens, str):
            required_packaging_tokens = [required_packaging_tokens]
        visual_evidence_contract: dict[str, object] = {
            "ocr_required": True,
            "required_packaging_tokens": list(required_packaging_tokens),
            "reference_product_asset_id": primary_asset.id if primary_asset else None,
            "reference_product_asset_path": (
                primary_asset.source_ref
                if primary_asset is not None
                and str(primary_asset.source_type or "").casefold() == "local"
                else None
            ),
            "reference_source": (
                "operator_confirmed_packaging_tokens"
                if required_packaging_tokens
                else "owned_primary_product_asset"
            ),
        }

        brief = models.AIProductionBrief(
            product_id=product.id,
            sku=product.sku,
            status="ready_for_output_review",
            platform=draft.platform,
            format="short_video",
            one_sentence_thesis=draft.user_concept,
            viewer_takeaway=draft.product_info,
            cta="Open the tracked product link after operator review.",
            must_show_json=["exact reviewed product and packaging"],
            must_avoid_json=list(product.restrictions_json or []),
            product_identity_rules_json={
                "exact_variant_confirmed": draft.exact_variant_confirmed,
                "primary_product_asset_id": draft.primary_product_asset_id,
                "visual_evidence_contract": visual_evidence_contract,
            },
            product_lock_mode="exact_product_lock",
            scene_count=1,
            duration_seconds=draft.duration_seconds,
            failure_conditions_json=[
                "product_identity_drift",
                "packaging_drift",
                "synthetic_or_placeholder_frames",
                "missing_proof_moment",
                "missing_cta",
            ],
            brief_json={
                "source_type": "product_ugc_recipe_draft",
                "source_id": draft.id,
                "provider_task_id": draft.provider_task_id,
                "human_review_notes": draft.human_review_notes,
            },
        )
        self.db.add(brief)
        self.db.flush()
        self.db.add(
            models.SceneBlueprint(
                ai_production_brief_id=brief.id,
                scene_order=1,
                scene_role="review_exact_product_ugc_output",
                start_second=0,
                end_second=float(draft.duration_seconds),
                viewer_goal=draft.user_concept,
                visual_action="Verify the exact downloaded provider output frame by frame.",
                must_show_json=["exact product", "exact packaging", "proof moment", "clear CTA"],
                must_avoid_json=list(product.restrictions_json or []),
            )
        )

        cycle = models.ContentCycle(
            organization_id=organization_id,
            created_by_user_profile_id=actor_user_profile_id,
            product_id=product.id,
            product_ugc_recipe_draft_id=draft.id,
            video_job_id=video_job.id,
            ai_production_brief_id=brief.id,
            idempotency_key=key,
            status="needs_output_acceptance",
            trace_version=1,
        )
        self.db.add(cycle)
        self.db.add(
            models.AuditLog(
                user_profile_id=actor_user_profile_id,
                organization_id=organization_id,
                action="start_canonical_content_cycle",
                status="allowed",
                entity_type="product_ugc_recipe_draft",
                entity_id=str(draft.id),
                metadata_json={"idempotency_key": key, "video_job_id": video_job.id},
            )
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(models.ContentCycle).where(
                    models.ContentCycle.organization_id == organization_id,
                    models.ContentCycle.idempotency_key == key,
                )
            )
            if concurrent and concurrent.product_ugc_recipe_draft_id == product_ugc_recipe_draft_id:
                return concurrent
            raise ContentCycleConflictError("Canonical content cycle already exists.") from exc
        self.db.refresh(cycle)
        return cycle

    def bind_approved_output(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        content_cycle_id: int,
        output_acceptance_id: int,
    ) -> models.ContentCycle:
        self._require_actor(organization_id, actor_user_profile_id)
        cycle = self._require_cycle(content_cycle_id, organization_id)
        self._bind_approved_output(cycle, output_acceptance_id)
        self.db.add(
            models.AuditLog(
                user_profile_id=actor_user_profile_id,
                organization_id=organization_id,
                action="bind_approved_output_to_content_cycle",
                status="allowed",
                entity_type="content_cycle",
                entity_id=str(cycle.id),
                metadata_json={"output_acceptance_id": output_acceptance_id},
            )
        )
        self.db.commit()
        self.db.refresh(cycle)
        return cycle

    def prepare_manual_distribution(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        content_cycle_id: int,
        output_acceptance_id: int,
        destination_id: int,
        target_url: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> models.ContentCycle:
        self._require_actor(organization_id, actor_user_profile_id)
        cycle = self._require_cycle(content_cycle_id, organization_id)

        if cycle.status == "manual_distribution_ready":
            self._validate_completed_cycle(cycle, destination_id=destination_id, target_url=target_url)
            return cycle

        destination = self.db.get(models.PublishingDestination, destination_id)
        if not destination:
            raise ContentCycleStateError(f"PublishingDestination {destination_id} not found.")
        if destination.organization_id != organization_id:
            raise ContentCycleOwnershipError("Publishing destination is not owned by this organization.")
        if destination.posting_mode != "manual":
            raise ContentCycleStateError("Canonical bridge prepares manual distribution only; API publishing is not allowed.")

        product = self._require_owned_product(cycle.product_id, organization_id)
        video_job = self.db.get(models.VideoJob, cycle.video_job_id)
        if cycle.output_acceptance_id and cycle.output_acceptance_id != output_acceptance_id:
            raise ContentCycleConflictError("Content cycle is already bound to another output acceptance.")
        acceptance = self.db.get(models.VideoOutputAcceptance, output_acceptance_id)
        if not video_job or not acceptance:
            raise ContentCycleStateError("Canonical video job or approved output acceptance is missing.")
        self._validate_approved_acceptance(cycle, acceptance)
        if destination.brand.casefold() != product.brand.casefold():
            raise ContentCycleStateError("Publishing destination brand does not match the content-cycle product.")
        if destination.platform.casefold() != cycle.product_ugc_recipe_draft.platform.casefold():
            raise ContentCycleStateError("Publishing destination platform does not match the Product UGC draft.")

        resolved_target = self._target_url(target_url or product.product_url)
        package = models.PublishingPackage(
            video_job_id=video_job.id,
            product_id=product.id,
            brand=product.brand,
            target_platform=destination.platform,
            title=f"{product.title} | {destination.platform}",
            description=(cycle.product_ugc_recipe_draft.product_info or "").strip() or product.description,
            hashtags_json=[],
            cta="Open the tracked product link",
            product_url=product.product_url,
            video_file_path=video_job.output_video_path,
            metadata_json={
                "workflow": "canonical_product_ugc_content_cycle_v1",
                "content_cycle_id": cycle.id,
                "product_ugc_recipe_draft_id": cycle.product_ugc_recipe_draft_id,
                "video_output_acceptance_id": acceptance.id,
                "manual_distribution_only": True,
                "approval": {
                    "source": "approved_video_output_acceptance",
                    "reviewer_notes": acceptance.reviewer_notes,
                },
            },
            ai_generated_flag=True,
            review_status="approved",
            status="approved",
        )
        when = scheduled_at or models.utcnow()
        validation = PublishingScheduler(self.db).validate(package, destination, when)
        if not validation["allowed"]:
            raise ContentCycleStateError("; ".join(validation["blockers"]))

        # All fallible domain validation happens before the first insert. From
        # here onward an IntegrityError is rolled back as one atomic operation.
        self._bind_approved_output(cycle, output_acceptance_id)
        self.db.add(package)
        self.db.flush()
        cycle.publishing_package_id = package.id
        task = models.PublishingTask(
            publishing_package_id=package.id,
            destination_id=destination.id,
            platform=destination.platform,
            status="manual_upload_required",
            scheduled_at=when,
            operator_name=self._actor_label(actor_user_profile_id),
            raw_response_json={
                "content_cycle_id": cycle.id,
                "schedule_validation": validation,
                "no_external_publish_performed": True,
            },
        )
        self.db.add(task)
        self.db.flush()
        cycle.publishing_task_id = task.id

        link = models.TrackingLink(
            slug=self._tracking_slug(cycle),
            target_url=resolved_target,
            publishing_task_id=task.id,
            destination_id=destination.id,
            product_id=product.id,
            sku=product.sku,
            status="active",
        )
        self.db.add(link)
        self.db.flush()
        cycle.tracking_link_id = link.id
        cycle.destination_id = destination.id
        cycle.status = "manual_distribution_ready"
        self.db.add(
            models.Review(
                entity_type="publishing_package",
                entity_id=package.id,
                reviewer_name=self._actor_label(actor_user_profile_id),
                status="approved",
                comment=f"Approved from exact VideoOutputAcceptance {acceptance.id} in content cycle {cycle.id}.",
            )
        )
        self.db.add(
            models.AuditLog(
                user_profile_id=actor_user_profile_id,
                organization_id=organization_id,
                action="prepare_content_cycle_manual_distribution",
                status="allowed",
                entity_type="content_cycle",
                entity_id=str(cycle.id),
                metadata_json={
                    "publishing_package_id": package.id,
                    "publishing_task_id": task.id,
                    "tracking_link_id": link.id,
                    "destination_id": destination.id,
                    "external_publish": False,
                },
            )
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            refreshed = self._require_cycle(content_cycle_id, organization_id)
            if refreshed.status == "manual_distribution_ready":
                self._validate_completed_cycle(refreshed, destination_id=destination_id, target_url=target_url)
                return refreshed
            raise ContentCycleConflictError("Manual-distribution artifacts conflict with an existing cycle.") from exc
        self.db.refresh(cycle)
        return cycle

    def get_trace(
        self,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        content_cycle_id: int,
    ) -> ContentCycleTrace:
        self._require_actor(organization_id, actor_user_profile_id)
        return self.as_trace(self._require_cycle(content_cycle_id, organization_id))

    @staticmethod
    def as_trace(cycle: models.ContentCycle) -> ContentCycleTrace:
        return ContentCycleTrace(
            id=cycle.id,
            organization_id=cycle.organization_id,
            created_by_user_profile_id=cycle.created_by_user_profile_id,
            product_id=cycle.product_id,
            product_ugc_recipe_draft_id=cycle.product_ugc_recipe_draft_id,
            video_job_id=cycle.video_job_id,
            ai_production_brief_id=cycle.ai_production_brief_id,
            output_acceptance_id=cycle.output_acceptance_id,
            publishing_package_id=cycle.publishing_package_id,
            publishing_task_id=cycle.publishing_task_id,
            tracking_link_id=cycle.tracking_link_id,
            destination_id=cycle.destination_id,
            idempotency_key=cycle.idempotency_key,
            status=cycle.status,
            trace_version=cycle.trace_version,
        )

    def _bind_approved_output(self, cycle: models.ContentCycle, acceptance_id: int) -> None:
        if cycle.output_acceptance_id:
            if cycle.output_acceptance_id != acceptance_id:
                raise ContentCycleConflictError("Content cycle is already bound to another output acceptance.")
            acceptance = self.db.get(models.VideoOutputAcceptance, acceptance_id)
            self._validate_approved_acceptance(cycle, acceptance)
            return
        acceptance = self.db.get(models.VideoOutputAcceptance, acceptance_id)
        self._validate_approved_acceptance(cycle, acceptance)
        cycle.output_acceptance_id = acceptance.id
        cycle.video_job.status = "video_approved"
        cycle.status = "output_accepted"

    def _validate_approved_acceptance(
        self,
        cycle: models.ContentCycle,
        acceptance: models.VideoOutputAcceptance | None,
    ) -> None:
        if not acceptance:
            raise ContentCycleStateError("VideoOutputAcceptance not found.")
        if acceptance.video_job_id != cycle.video_job_id:
            raise ContentCycleStateError("VideoOutputAcceptance belongs to another video job.")
        if acceptance.ai_production_brief_id != cycle.ai_production_brief_id:
            raise ContentCycleStateError("VideoOutputAcceptance belongs to another production brief.")
        latest_id = self.db.scalar(
            select(models.VideoOutputAcceptance.id)
            .where(models.VideoOutputAcceptance.video_job_id == cycle.video_job_id)
            .order_by(models.VideoOutputAcceptance.id.desc())
            .limit(1)
        )
        if latest_id != acceptance.id:
            raise ContentCycleStateError("Only the latest output acceptance can be bound to a content cycle.")
        if acceptance.status != "approved" or acceptance.publishing_readiness != "ready":
            raise ContentCycleStateError("Video output is not approved and publishing-ready.")
        if acceptance.blockers_json:
            raise ContentCycleStateError("Approved output acceptance still contains blockers.")
        statuses = (
            acceptance.product_identity_status,
            acceptance.packaging_status,
            acceptance.geometry_status,
            acceptance.blogger_authenticity_status,
            acceptance.scene_match_status,
            acceptance.proof_moment_status,
            acceptance.cta_status,
        )
        if any(str(status or "").strip().lower() not in PASS_STATUSES for status in statuses):
            raise ContentCycleStateError("Every output acceptance dimension must have a passing status.")
        if not (acceptance.reviewer_notes or "").strip():
            raise ContentCycleStateError("Approved output acceptance requires explicit human reviewer notes.")

        video_job = self.db.get(models.VideoJob, cycle.video_job_id)
        if not video_job or video_job.provider.strip().lower() == "mock":
            raise ContentCycleStateError("Mock video output cannot enter a canonical publishing cycle.")
        self._require_nonempty_file(video_job.output_video_path, label="Video output")
        if self._contains_blocking_marker(video_job.output_video_path or ""):
            raise ContentCycleStateError("Synthetic or placeholder video output cannot enter a canonical cycle.")

        frame_result = self.db.scalar(
            select(models.FrameExtractionResult)
            .where(models.FrameExtractionResult.video_job_id == cycle.video_job_id)
            .order_by(models.FrameExtractionResult.id.desc())
            .limit(1)
        )
        if not frame_result or frame_result.contact_sheet_path != acceptance.contact_sheet_path:
            raise ContentCycleStateError("Approved output acceptance is not tied to the latest extracted frames.")
        self._require_nonempty_file(frame_result.contact_sheet_path, label="Contact sheet")
        if not frame_result.frame_paths_json:
            raise ContentCycleStateError("Approved output acceptance has no extracted keyframes.")
        warnings = [str(item) for item in (frame_result.warnings_json or [])]
        if any(self._contains_blocking_marker(item) for item in warnings):
            raise ContentCycleStateError("Extracted frames contain fail-closed media warnings.")
        for frame_path in frame_result.frame_paths_json or []:
            if self._contains_blocking_marker(str(frame_path)):
                raise ContentCycleStateError("Synthetic or placeholder frame cannot enter a canonical cycle.")
            self._require_nonempty_file(str(frame_path), label="Extracted frame")
        if acceptance.visual_evidence_snapshot_id is None:
            raise ContentCycleStateError(
                "Approved output acceptance is missing immutable visual evidence."
            )
        evidence_snapshot = self.db.get(
            models.VisualEvidenceSnapshot,
            acceptance.visual_evidence_snapshot_id,
        )
        if (
            evidence_snapshot is None
            or evidence_snapshot.video_job_id != cycle.video_job_id
            or evidence_snapshot.frame_extraction_result_id != frame_result.id
            or evidence_snapshot.status != "passed"
        ):
            raise ContentCycleStateError(
                "Approved output acceptance is not tied to passing visual evidence."
            )
        try:
            VisualEvidenceSnapshotService(self.db).verify_current(evidence_snapshot)
        except VisualEvidenceSnapshotError as exc:
            raise ContentCycleStateError(
                "Video or extracted frames changed after visual review."
            ) from exc

    def _validated_product_ugc_output(self, draft: models.ProductUGCRecipeDraft) -> Path:
        if draft.status != "approved" or draft.human_review_status != "approved":
            raise ContentCycleStateError("Product UGC draft must be explicitly approved by a human.")
        if draft.publishing_readiness != "ready_for_package":
            raise ContentCycleStateError("Product UGC draft is not ready for a publishing package.")
        if draft.blockers_json:
            raise ContentCycleStateError("Product UGC draft still contains blockers.")
        if not draft.exact_variant_confirmed or not draft.likeness_consent:
            raise ContentCycleStateError("Product variant and likeness consent gates must remain confirmed.")
        if not (draft.human_review_notes or "").strip():
            raise ContentCycleStateError("Product UGC approval requires explicit human review notes.")
        if not draft.provider_task_id or str(draft.provider_status or "").upper() not in SUCCESS_PROVIDER_STATUSES:
            raise ContentCycleStateError("Product UGC output must come from a successful real provider task.")
        output_paths = list(draft.local_output_paths_json or [])
        if len(output_paths) != 1:
            raise ContentCycleStateError("Canonical cycle requires exactly one unambiguous Product UGC output.")
        output_path = self._require_nonempty_file(output_paths[0], label="Product UGC output")
        values = [output_path.as_posix(), *(str(item) for item in (draft.warnings_json or []))]
        if any(self._contains_blocking_marker(item) for item in values):
            raise ContentCycleStateError("Synthetic, placeholder, or failed Product UGC output is blocked.")
        return output_path

    def _require_actor(self, organization_id: int, actor_user_profile_id: int) -> None:
        organization = self.db.get(models.Organization, organization_id)
        profile = self.db.get(models.UserProfile, actor_user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == actor_user_profile_id,
                models.Membership.status == "active",
            )
        )
        if not organization or organization.status != "active":
            raise ContentCycleOwnershipError("Organization is missing or inactive.")
        if not profile or not profile.is_active or profile.status != "active":
            raise ContentCycleOwnershipError("User profile is missing or inactive.")
        if not membership:
            raise ContentCycleOwnershipError("User is not an active member of this organization.")

    def _require_owned_product(self, product_id: int, organization_id: int) -> models.Product:
        product = self.db.get(models.Product, product_id)
        if not product or product.organization_id != organization_id:
            raise ContentCycleOwnershipError("Product is not explicitly owned by this organization.")
        return product

    def _require_cycle(self, cycle_id: int, organization_id: int) -> models.ContentCycle:
        cycle = self.db.get(models.ContentCycle, cycle_id)
        if not cycle or cycle.organization_id != organization_id:
            raise ContentCycleOwnershipError("Content cycle does not belong to this organization.")
        return cycle

    def _validate_completed_cycle(
        self,
        cycle: models.ContentCycle,
        *,
        destination_id: int,
        target_url: str | None,
    ) -> None:
        required_ids = (
            cycle.output_acceptance_id,
            cycle.publishing_package_id,
            cycle.publishing_task_id,
            cycle.tracking_link_id,
        )
        if not all(required_ids):
            raise ContentCycleStateError("Completed cycle is missing one or more canonical links.")
        if cycle.destination_id != destination_id:
            raise ContentCycleConflictError("Cycle is already prepared for another destination.")
        acceptance = self.db.get(models.VideoOutputAcceptance, cycle.output_acceptance_id)
        self._validate_approved_acceptance(cycle, acceptance)
        package = self.db.get(models.PublishingPackage, cycle.publishing_package_id)
        task = self.db.get(models.PublishingTask, cycle.publishing_task_id)
        link = self.db.get(models.TrackingLink, cycle.tracking_link_id)
        destination = self.db.get(models.PublishingDestination, cycle.destination_id)
        if not package or package.video_job_id != cycle.video_job_id or package.product_id != cycle.product_id:
            raise ContentCycleStateError("Completed cycle has a broken publishing-package lineage.")
        metadata = package.metadata_json or {}
        if (
            metadata.get("content_cycle_id") != cycle.id
            or metadata.get("video_output_acceptance_id") != cycle.output_acceptance_id
            or package.status != "approved"
            or package.review_status != "approved"
        ):
            raise ContentCycleStateError("Completed cycle package is no longer approved for this exact output.")
        if not task or task.publishing_package_id != package.id or task.destination_id != destination_id:
            raise ContentCycleStateError("Completed cycle has a broken publishing-task lineage.")
        if task.status != "manual_upload_required" or task.final_url:
            raise ContentCycleStateError("Canonical bridge expects an unpublished manual-upload task.")
        if (
            not link
            or link.publishing_task_id != task.id
            or link.destination_id != destination_id
            or link.product_id != cycle.product_id
            or link.status != "active"
        ):
            raise ContentCycleStateError("Completed cycle has a broken tracking-link lineage.")
        if not destination or destination.organization_id != cycle.organization_id:
            raise ContentCycleOwnershipError("Completed cycle destination is no longer owned by the organization.")
        if target_url and link.target_url != self._target_url(target_url):
            raise ContentCycleConflictError("Cycle is already prepared with another tracking target.")

    def _actor_label(self, user_profile_id: int) -> str:
        profile = self.db.get(models.UserProfile, user_profile_id)
        return ((profile.display_name if profile else None) or (profile.email if profile else None) or f"user:{user_profile_id}")[:160]

    @staticmethod
    def _require_nonempty_file(value: str | None, *, label: str) -> Path:
        if not value:
            raise ContentCycleStateError(f"{label} path is missing.")
        path = Path(value)
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            raise ContentCycleStateError(f"{label} must exist and be non-empty.")
        return path

    @staticmethod
    def _contains_blocking_marker(value: str) -> bool:
        normalized = value.strip().lower()
        return any(marker in normalized for marker in BLOCKING_MEDIA_MARKERS)

    @staticmethod
    def _aspect_ratio(ratio: str) -> str:
        return "9:16" if ratio in {"720:1280", "1080:1920", "9:16"} else ratio

    @staticmethod
    def _idempotency_key(value: str) -> str:
        key = (value or "").strip()
        if not key or len(key) > 160:
            raise ContentCycleError("Idempotency key must contain 1-160 characters.")
        return key

    @staticmethod
    def _target_url(value: str | None) -> str:
        target = (value or "").strip()
        parts = urlsplit(target)
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ContentCycleStateError("Tracking target must be a public HTTP(S) URL without embedded credentials.")
        return target

    @staticmethod
    def _tracking_slug(cycle: models.ContentCycle) -> str:
        digest = hashlib.sha256(
            f"{cycle.organization_id}:{cycle.id}:{cycle.idempotency_key}".encode("utf-8")
        ).hexdigest()[:12]
        return f"cc{cycle.id}-{digest}"
