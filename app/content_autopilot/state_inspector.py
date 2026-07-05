from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.content_autopilot.errors import ContentAutopilotDataError
from app.content_autopilot.types import ContentStateSnapshot
from app.content_factory.readiness import (
    control_loop_readiness,
    generation_report_exists,
    geometry_readiness,
    latest_publishing_package,
    latest_quality_review,
    product_geometry_mismatch_detected,
)
from app.intelligence.safety import provider_key_status
from app.video_generator.artifact_manager import ArtifactManager


IDENTITY_MISMATCH_MARKERS = {
    "product_identity_mismatch",
    "identity mismatch",
    "wrong product",
    "wrong packaging",
    "changed packaging",
    "fake label",
    "label mismatch",
}


class StateInspector:
    def __init__(self, db: Session):
        self.db = db

    def inspect_product(self, product_id: int) -> ContentStateSnapshot:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise ContentAutopilotDataError(f"Product {product_id} not found.")

        content_run = self._latest_content_run(product_id)
        demand = self._latest_demand(product_id)
        creative_spec = self._latest_creative_spec(product_id)
        selected_variant = self._selected_variant(content_run, creative_spec)
        generation_variant = content_run.generation_variant if content_run and content_run.generation_variant else None
        prompt_pack = generation_variant.prompt_pack_json if generation_variant else {}

        if content_run:
            readiness = control_loop_readiness(self.db, content_run)
            ref_readiness = readiness["reference_readiness"]
            geo_readiness = readiness["geometry_readiness"]
            publishing = readiness["publishing_readiness"]
        else:
            ref_readiness = self._reference_readiness(product_id)
            geo_readiness = geometry_readiness(prompt_pack)
            publishing = {
                "status": "not_started",
                "ready": False,
                "blockers": ["video_not_generated"],
            }

        video_job = content_run.video_job if content_run and content_run.video_job else None
        output_exists, output_non_empty = ArtifactManager.file_exists_and_non_empty(
            video_job.output_video_path if video_job else None
        )
        report_exists = generation_report_exists(content_run) if content_run else False
        quality_review = latest_quality_review(self.db, content_run) if content_run else None
        package = latest_publishing_package(self.db, content_run) if content_run else self._latest_package_for_product(product_id)
        task = self._latest_task(package.id) if package else None
        metric = self._latest_metric(product, content_run)
        performance_strength = self._performance_strength(metric)
        provider_status = provider_key_status()

        blockers = list(content_run.blockers_json or []) if content_run else []
        if not (content_run and content_run.demand_hypothesis_id) and not demand:
            blockers.append("demand_missing")
        if ref_readiness.get("status") != "ready":
            blockers.extend(f"reference:{item}" for item in ref_readiness.get("blockers") or [])
        if geo_readiness.get("status") == "blocked":
            blockers.extend(geo_readiness.get("blockers") or [])
        if video_job and not output_exists:
            blockers.append("video_output_missing")

        identity_mismatch = self._identity_mismatch_detected(content_run, quality_review)
        geometry_mismatch = product_geometry_mismatch_detected(self.db, content_run) if content_run else False
        if identity_mismatch:
            blockers.append("product_identity_mismatch")
        if geometry_mismatch:
            blockers.append("product_geometry_mismatch")

        human_review_required = bool(
            (content_run and (content_run.run_json or {}).get("human_review_required"))
            or (quality_review and quality_review.status in {"needs_human_review", "metadata_scored"})
            or identity_mismatch
            or geometry_mismatch
            or publishing.get("status") in {"needs_human_review", "needs_publishing_package_approval"}
        )
        snapshot = ContentStateSnapshot(
            product_id=product.id,
            sku=product.sku,
            content_run_id=content_run.id if content_run else None,
            content_run_status=content_run.status if content_run else None,
            has_demand=bool((content_run and content_run.demand_hypothesis_id) or demand),
            has_creative_spec=bool((content_run and content_run.creative_spec_id) or creative_spec),
            has_selected_variant=bool((content_run and content_run.selected_variant_id) or selected_variant),
            has_prompt_pack=bool((content_run and content_run.prompt_pack_id) or prompt_pack),
            reference_readiness=ref_readiness,
            geometry_readiness=geo_readiness,
            has_video_output=output_exists and output_non_empty,
            generation_report_exists=report_exists,
            video_job_id=video_job.id if video_job else None,
            video_status=video_job.status if video_job else None,
            video_review_status=quality_review.status if quality_review else None,
            human_review_required=human_review_required,
            publishing_readiness=publishing,
            has_publishing_package=bool(package),
            publishing_package_id=package.id if package else None,
            publishing_package_status=package.status if package else None,
            has_publishing_task=bool(task),
            publishing_task_status=task.status if task else None,
            performance_data_status="present" if metric else "missing",
            performance_strength=performance_strength,
            latest_metric_id=metric.id if metric else None,
            identity_mismatch_detected=identity_mismatch,
            geometry_mismatch_detected=geometry_mismatch,
            real_smoke_gate_ready=(
                provider_status["generation_mode"] == "real"
                and provider_status["allow_real_spend"]
                and provider_status["runway_api_secret_configured"]
            ),
            blockers=list(dict.fromkeys(blockers)),
            warnings=list(dict.fromkeys((content_run.warnings_json if content_run else []) or [])),
        )
        snapshot.available_actions = self._available_actions(snapshot)
        return snapshot

    def _reference_readiness(self, product_id: int) -> dict[str, Any]:
        try:
            readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider="runway")
            return readiness.model_dump(mode="json")
        except Exception as exc:
            return {
                "status": "blocked",
                "ready": False,
                "blockers": [str(exc)],
                "warnings": [],
            }

    def _latest_content_run(self, product_id: int) -> models.ContentRun | None:
        return self.db.scalar(
            select(models.ContentRun)
            .where(models.ContentRun.product_id == product_id)
            .order_by(models.ContentRun.id.desc())
        )

    def _latest_demand(self, product_id: int) -> models.DemandHypothesisRecord | None:
        return self.db.scalar(
            select(models.DemandHypothesisRecord)
            .where(models.DemandHypothesisRecord.product_id == product_id)
            .order_by(models.DemandHypothesisRecord.id.desc())
        )

    def _latest_creative_spec(self, product_id: int) -> models.VideoCreativeSpecRecord | None:
        return self.db.scalar(
            select(models.VideoCreativeSpecRecord)
            .where(models.VideoCreativeSpecRecord.product_id == product_id)
            .order_by(models.VideoCreativeSpecRecord.id.desc())
        )

    def _selected_variant(
        self,
        content_run: models.ContentRun | None,
        creative_spec: models.VideoCreativeSpecRecord | None,
    ) -> models.CreativeVariant | None:
        if content_run and content_run.selected_variant:
            return content_run.selected_variant
        if not creative_spec:
            return None
        selected = self.db.scalar(
            select(models.CreativeVariant)
            .where(
                models.CreativeVariant.creative_spec_id == creative_spec.id,
                models.CreativeVariant.status == "selected",
            )
            .order_by(models.CreativeVariant.id.desc())
        )
        if selected:
            return selected
        variant_set = self.db.scalar(
            select(models.CreativeVariantSet)
            .where(models.CreativeVariantSet.creative_spec_id == creative_spec.id)
            .order_by(models.CreativeVariantSet.id.desc())
        )
        return self.db.get(models.CreativeVariant, variant_set.selected_variant_id) if variant_set and variant_set.selected_variant_id else None

    def _latest_package_for_product(self, product_id: int) -> models.PublishingPackage | None:
        return self.db.scalar(
            select(models.PublishingPackage)
            .where(models.PublishingPackage.product_id == product_id)
            .order_by(models.PublishingPackage.id.desc())
        )

    def _latest_task(self, package_id: int) -> models.PublishingTask | None:
        return self.db.scalar(
            select(models.PublishingTask)
            .where(models.PublishingTask.publishing_package_id == package_id)
            .order_by(models.PublishingTask.id.desc())
        )

    def _latest_metric(
        self,
        product: models.Product,
        content_run: models.ContentRun | None,
    ) -> models.ContentPerformanceMetric | None:
        query = select(models.ContentPerformanceMetric).order_by(models.ContentPerformanceMetric.id.desc())
        if content_run:
            metric = self.db.scalar(query.where(models.ContentPerformanceMetric.content_run_id == content_run.id))
            if metric:
                return metric
        return self.db.scalar(query.where(models.ContentPerformanceMetric.sku == product.sku))

    @staticmethod
    def _performance_strength(metric: models.ContentPerformanceMetric | None) -> str:
        if not metric:
            return "unknown"
        ctr = metric.ctr or 0
        retention = metric.retention_rate or 0
        orders = metric.orders or 0
        if ctr >= 0.035 or retention >= 0.4 or orders >= 3:
            return "strong"
        if ctr > 0 and ctr < 0.01 and retention < 0.2 and orders == 0:
            return "weak"
        return "neutral"

    def _identity_mismatch_detected(
        self,
        content_run: models.ContentRun | None,
        quality_review: models.VideoQualityReview | None,
    ) -> bool:
        values: list[Any] = []
        if quality_review:
            values.extend([quality_review.status, quality_review.review_json, quality_review.warnings_json])
        if content_run:
            latest_ai_review = self.db.scalar(
                select(models.AIContentReview)
                .where(models.AIContentReview.content_run_id == content_run.id)
                .order_by(models.AIContentReview.id.desc())
            )
            if latest_ai_review:
                values.extend([latest_ai_review.status, latest_ai_review.review_json, latest_ai_review.warnings_json])
            if content_run.video_job_id:
                requests = self.db.scalars(
                    select(models.SceneRegenerationRequest).where(
                        models.SceneRegenerationRequest.video_job_id == content_run.video_job_id
                    )
                ).all()
                values.extend(requests)
        text = json.dumps(values, default=str, ensure_ascii=False).lower()
        return any(marker in text for marker in IDENTITY_MISMATCH_MARKERS)

    @staticmethod
    def _available_actions(snapshot: ContentStateSnapshot) -> list[str]:
        actions: list[str] = []
        if not snapshot.has_demand or not snapshot.content_run_id:
            actions.append("prepare_content_run")
        if snapshot.reference_readiness.get("status") != "ready":
            actions.append("add_product_reference")
        if snapshot.geometry_readiness.get("status") == "blocked":
            actions.append("add_geometry_lock")
        if snapshot.has_selected_variant and not snapshot.has_prompt_pack:
            actions.append("build_prompt_pack")
        if snapshot.has_prompt_pack and not snapshot.has_video_output:
            actions.extend(["run_prompt_only", "run_real_smoke"])
        if snapshot.video_review_status in {"needs_human_review", "metadata_scored"}:
            actions.append("human_review")
        if snapshot.identity_mismatch_detected:
            actions.append("request_regeneration")
        if snapshot.geometry_mismatch_detected:
            actions.append("request_geometry_regeneration")
        if snapshot.video_review_status in {"approved", "human_approved"} and not snapshot.has_publishing_package:
            actions.append("create_publishing_package")
        if snapshot.publishing_package_status == "approved" and not snapshot.has_publishing_task:
            actions.append("schedule_publishing_task")
        if snapshot.publishing_task_status in {"published_manual", "published_api"} and snapshot.performance_data_status == "missing":
            actions.append("import_performance_stats")
        if snapshot.performance_strength == "strong":
            actions.append("scale_variant")
        if snapshot.performance_strength == "weak":
            actions.append("pause_variant")
        return list(dict.fromkeys(actions))
