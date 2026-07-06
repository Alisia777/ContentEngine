from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.participant_portal.errors import ParticipantPortalDataError
from app.participant_portal.participant_service import ParticipantService


class AssignmentPortalService:
    def __init__(self, db: Session):
        self.db = db

    def create_assignment(
        self,
        *,
        participant_id: int,
        assignment_type: str = "create_video",
        campaign_id: int | None = None,
        product_id: int | None = None,
        content_run_id: int | None = None,
        creative_variant_id: int | None = None,
        publishing_task_id: int | None = None,
        payout_rule_id: int | None = None,
        due_at: datetime | None = None,
        priority: int = 5,
    ) -> models.ParticipantAssignment:
        participant = ParticipantService(self.db).get(participant_id)
        content_run = self.db.get(models.ContentRun, content_run_id) if content_run_id else None
        creative_variant = self.db.get(models.CreativeVariant, creative_variant_id) if creative_variant_id else None
        publishing_task = self.db.get(models.PublishingTask, publishing_task_id) if publishing_task_id else None
        package = publishing_task.publishing_package if publishing_task else None
        product = self._resolve_product(product_id, content_run, package)
        brief = self.build_brief_card(
            product=product,
            content_run=content_run,
            creative_variant=creative_variant or (content_run.selected_variant if content_run else None),
            publishing_task=publishing_task,
            payout_rule_id=payout_rule_id,
        )
        assignment = models.ParticipantAssignment(
            participant_id=participant.id,
            campaign_id=campaign_id,
            product_id=product.id if product else None,
            sku=product.sku if product else None,
            content_run_id=content_run.id if content_run else None,
            creative_spec_id=content_run.creative_spec_id if content_run else None,
            creative_variant_id=brief.get("creative_variant_id"),
            prompt_pack_id=content_run.prompt_pack_id if content_run else None,
            publishing_package_id=package.id if package else None,
            publishing_task_id=publishing_task.id if publishing_task else None,
            assignment_type=assignment_type,
            status="assigned",
            priority=priority,
            due_at=due_at,
            brief_json=brief,
            payout_rule_id=payout_rule_id,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def list_assignments(self, participant_id: int) -> list[models.ParticipantAssignment]:
        ParticipantService(self.db).get(participant_id)
        return self.db.scalars(
            select(models.ParticipantAssignment)
            .where(models.ParticipantAssignment.participant_id == participant_id)
            .order_by(models.ParticipantAssignment.priority, models.ParticipantAssignment.id.desc())
        ).all()

    def get(self, assignment_id: int) -> models.ParticipantAssignment:
        assignment = self.db.get(models.ParticipantAssignment, assignment_id)
        if not assignment:
            raise ParticipantPortalDataError(f"ParticipantAssignment {assignment_id} not found.")
        return assignment

    def update(self, assignment_id: int, **values: Any) -> models.ParticipantAssignment:
        assignment = self.get(assignment_id)
        for key, value in values.items():
            if value is not None and hasattr(assignment, key):
                setattr(assignment, key, value)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def build_brief_card(
        self,
        *,
        product: models.Product | None,
        content_run: models.ContentRun | None = None,
        creative_variant: models.CreativeVariant | None = None,
        publishing_task: models.PublishingTask | None = None,
        payout_rule_id: int | None = None,
    ) -> dict[str, Any]:
        creative_spec = content_run.creative_spec if content_run else None
        demand = content_run.demand_hypothesis if content_run else None
        spec_json = creative_spec.spec_json if creative_spec else {}
        run_json = content_run.run_json if content_run else {}
        destination = publishing_task.destination if publishing_task else None
        tracking_link = self._tracking_link(publishing_task.id) if publishing_task else None
        publish_warnings = []
        if publishing_task and not tracking_link:
            publish_warnings.append("tracking_link_missing")
        if publishing_task and not publishing_task.final_url:
            publish_warnings.append("final_url_required_after_publication")
        return {
            "sku": product.sku if product else None,
            "product_title": product.title if product else None,
            "buyer_need": (demand.buyer_need if demand else None) or spec_json.get("buyer_need") or run_json.get("buyer_need"),
            "safe_promise": spec_json.get("safe_promise") or run_json.get("safe_promise"),
            "hook_text": (creative_variant.hook_text if creative_variant else None) or spec_json.get("hook") or spec_json.get("hook_text"),
            "first_frame_logic": spec_json.get("first_frame_logic") or spec_json.get("first_frame") or run_json.get("first_frame_logic"),
            "references": self._references(product, content_run),
            "product_identity_rules": spec_json.get("product_identity_rules") or spec_json.get("identity_rules") or [],
            "geometry_scale_rules": spec_json.get("geometry_scale_rules") or spec_json.get("geometry_rules") or [],
            "must_include": spec_json.get("must_include") or [],
            "must_avoid": spec_json.get("must_avoid") or [],
            "output_format": {
                "platform": destination.platform if destination else (creative_spec.platform if creative_spec else None),
                "format": creative_spec.format if creative_spec else "short_video",
                "duration_seconds": creative_spec.duration_seconds if creative_spec else None,
                "aspect_ratio": creative_spec.aspect_ratio if creative_spec else None,
            },
            "destination": {
                "destination_id": destination.id if destination else None,
                "platform": destination.platform if destination else None,
                "handle": destination.handle if destination else None,
            },
            "tracking_link": f"/r/{tracking_link.slug}" if tracking_link else None,
            "tracking_target_url": tracking_link.target_url if tracking_link else None,
            "publish_checklist": [
                "video_approved",
                "assignment_opened",
                "destination_linked",
                "tracking_link_used_in_post",
                "final_url_submitted_after_publication",
                "metrics_uploaded_with_posted_url_or_tracking_slug",
            ],
            "publish_warnings": publish_warnings,
            "review_checklist": spec_json.get("review_checklist")
            or ["product_identity_preserved", "safe_promise_only", "format_matches_destination", "no_forbidden_claims"],
            "payout_rule_id": payout_rule_id,
            "creative_variant_id": creative_variant.id if creative_variant else None,
            "content_run_id": content_run.id if content_run else None,
        }

    def _resolve_product(
        self,
        product_id: int | None,
        content_run: models.ContentRun | None,
        package: models.PublishingPackage | None,
    ) -> models.Product | None:
        if product_id:
            product = self.db.get(models.Product, product_id)
            if not product:
                raise ParticipantPortalDataError(f"Product {product_id} not found.")
            return product
        if content_run:
            return content_run.product
        if package:
            return package.product
        return None

    @staticmethod
    def _references(product: models.Product | None, content_run: models.ContentRun | None) -> list:
        if content_run and content_run.asset_kit:
            return content_run.asset_kit.provider_reference_bundle_json.get("reference_images", []) or content_run.asset_kit.assets_json
        return product.images_json if product else []

    def _tracking_link(self, publishing_task_id: int) -> models.TrackingLink | None:
        return self.db.scalar(
            select(models.TrackingLink)
            .where(models.TrackingLink.publishing_task_id == publishing_task_id)
            .order_by(models.TrackingLink.id.desc())
        )
