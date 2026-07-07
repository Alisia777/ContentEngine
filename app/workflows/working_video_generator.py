from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.creative.creative_spec_builder import CreativeSpecBuilder
from app.demand.demand_hypothesis_builder import DemandHypothesisBuilder
from app.demand.demand_validator import DemandValidator
from app.demand.errors import DemandDataError
from app.demand.types import DemandHypothesis
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.safety import provider_key_status
from app.variants.creative_variant_builder import CreativeVariantBuilder
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.variant_scorer import VariantScorer
from app.variants.variant_selector import VariantSelector
from app.video_generator.generator import VideoGenerator
from app.video_generator.real_smoke_runner import RealSmokeRunner
from app.video_generator.types import RealSmokeRunOutput


class WorkingVideoPrepareResult(BaseModel):
    status: str
    product_id: int
    sku: str
    demand_hypothesis_id: int
    buyer_need: str
    trigger_situation: str
    pain_point: str
    objection: str
    safe_promise: str
    source_refs: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    demand_validation: dict[str, Any] = Field(default_factory=dict)
    creative_spec_id: int
    selected_hook: str
    selected_hook_type: str
    first_frame: dict[str, Any] = Field(default_factory=dict)
    asset_kit_id: int | None = None
    reference_readiness: dict[str, Any] = Field(default_factory=dict)
    reference_policy: dict[str, Any] = Field(default_factory=dict)
    selected_variant_id: int | None = None
    selected_variant_score: dict[str, Any] = Field(default_factory=dict)
    generation_variant_id: int | None = None
    prompt_pack_id: int | None = None
    prompt_pack: dict[str, Any] = Field(default_factory=dict)
    real_smoke_eligible: bool = False
    real_smoke_blockers: list[str] = Field(default_factory=list)
    provider_status: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class WorkingVideoGenerator:
    def __init__(self, db: Session):
        self.db = db

    def prepare(
        self,
        product_id: int,
        platform: str,
        duration_seconds: int,
        variant_count: int,
    ) -> WorkingVideoPrepareResult:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise DemandDataError(f"Product {product_id} not found.")
        demand_record = DemandHypothesisBuilder(self.db).build_for_product(product_id)
        hypothesis = DemandHypothesis.model_validate(demand_record.hypothesis_json)
        spec = CreativeSpecBuilder(self.db).build_from_demand(
            demand_record.id,
            platform=platform,
            duration_seconds=duration_seconds,
        )
        asset_kit = self._latest_asset_kit(product_id) or AssetKitBuilder(self.db).build_for_product(product_id)
        readiness = ProductReferenceReadinessChecker(self.db).check(product_id, provider="runway")
        reference_policy = ProductReferencePolicyService(self.db).check(product_id, provider="runway")
        validation = DemandValidator().validate(
            hypothesis,
            reference_readiness_status=readiness.status,
            reference_blockers=readiness.blockers,
        )
        demand_record.validation_report_json = validation.model_dump(mode="json")
        demand_record.status = validation.status
        hypothesis.validation_status = validation.status
        hypothesis.real_video_eligible = validation.real_video_eligible
        demand_record.hypothesis_json = hypothesis.model_dump(mode="json")
        self.db.commit()
        first_frames = FirstFrameBuilder(self.db).build_options(spec.id, asset_kit_id=asset_kit.id if asset_kit else None)
        variant_set = CreativeVariantBuilder(self.db).build_set(
            spec.id,
            asset_kit_id=asset_kit.id if asset_kit else None,
            count=variant_count,
        )
        VariantScorer(self.db).score_set(variant_set.id)
        variant_set = VariantSelector(self.db).select_best(variant_set.id)
        selected_variant = self.db.get(models.CreativeVariant, variant_set.selected_variant_id) if variant_set.selected_variant_id else None
        if not selected_variant:
            raise DemandDataError("No safe CreativeVariant could be selected for this product.")
        generation_variant = VideoGenerator(self.db).build_prompt_pack_from_variant(selected_variant.id, provider="runway")
        self.db.refresh(selected_variant)
        return self._result(
            product=product,
            demand_record=demand_record,
            hypothesis=hypothesis,
            spec=spec,
            first_frame=first_frames[0].option_json if first_frames else {},
            asset_kit=asset_kit,
            readiness=readiness.model_dump(mode="json"),
            reference_policy=reference_policy.model_dump(mode="json"),
            selected_variant=selected_variant,
            generation_variant=generation_variant,
            validation=validation.model_dump(mode="json"),
        )

    def run_prompt_only(self, selected_variant_id: int, *, provider: str = "runway") -> WorkingVideoPrepareResult:
        selected_variant = self._selected_variant(selected_variant_id)
        generation_variant = VideoGenerator(self.db).build_prompt_pack_from_variant(selected_variant.id, provider=provider)
        product = selected_variant.creative_spec.product
        demand_record = self._demand_for_spec(selected_variant.creative_spec_id)
        hypothesis = DemandHypothesis.model_validate(demand_record.hypothesis_json)
        readiness = ProductReferenceReadinessChecker(self.db).check(product.id, provider=provider)
        reference_policy = ProductReferencePolicyService(self.db).check(product.id, provider=provider)
        validation = DemandValidator().validate(
            hypothesis,
            reference_readiness_status=readiness.status,
            reference_blockers=readiness.blockers,
        )
        return self._result(
            product=product,
            demand_record=demand_record,
            hypothesis=hypothesis,
            spec=selected_variant.creative_spec,
            first_frame=selected_variant.first_frame_json,
            asset_kit=selected_variant.variant_set.asset_kit,
            readiness=readiness.model_dump(mode="json"),
            reference_policy=reference_policy.model_dump(mode="json"),
            selected_variant=selected_variant,
            generation_variant=generation_variant,
            validation=validation.model_dump(mode="json"),
        )

    def run_real_smoke(
        self,
        selected_variant_id: int,
        *,
        provider: str = "runway",
        allow_real_spend: bool,
        max_scenes: int = 1,
    ) -> RealSmokeRunOutput:
        self._selected_variant(selected_variant_id)
        return RealSmokeRunner(self.db).run_from_variant(
            selected_variant_id,
            provider=provider,
            max_scenes=max_scenes,
            full_video=False,
            allow_real_spend=allow_real_spend,
        )

    def status(self, selected_variant_id: int) -> WorkingVideoPrepareResult:
        selected_variant = self._selected_variant(selected_variant_id)
        product = selected_variant.creative_spec.product
        demand_record = self._demand_for_spec(selected_variant.creative_spec_id)
        hypothesis = DemandHypothesis.model_validate(demand_record.hypothesis_json)
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant)
            .where(models.VideoGenerationVariant.creative_variant_id == selected_variant.id)
            .order_by(models.VideoGenerationVariant.id.desc())
        )
        readiness = ProductReferenceReadinessChecker(self.db).check(product.id, provider="runway")
        reference_policy = ProductReferencePolicyService(self.db).check(product.id, provider="runway")
        validation = DemandValidator().validate(
            hypothesis,
            reference_readiness_status=readiness.status,
            reference_blockers=readiness.blockers,
        )
        return self._result(
            product=product,
            demand_record=demand_record,
            hypothesis=hypothesis,
            spec=selected_variant.creative_spec,
            first_frame=selected_variant.first_frame_json,
            asset_kit=selected_variant.variant_set.asset_kit,
            readiness=readiness.model_dump(mode="json"),
            reference_policy=reference_policy.model_dump(mode="json"),
            selected_variant=selected_variant,
            generation_variant=generation_variant,
            validation=validation.model_dump(mode="json"),
        )

    def _result(
        self,
        *,
        product: models.Product,
        demand_record: models.DemandHypothesisRecord,
        hypothesis: DemandHypothesis,
        spec: models.VideoCreativeSpecRecord,
        first_frame: dict,
        asset_kit: models.ProductAssetKit | None,
        readiness: dict,
        reference_policy: dict,
        selected_variant: models.CreativeVariant,
        generation_variant: models.VideoGenerationVariant | None,
        validation: dict,
    ) -> WorkingVideoPrepareResult:
        prompt_pack = generation_variant.prompt_pack_json if generation_variant else {}
        provider_status = provider_key_status()
        real_smoke_eligible = (
            validation.get("real_video_eligible") is True
            and readiness.get("status") == "ready"
            and reference_policy.get("strict_real_generation_allowed") is True
            and selected_variant.status == "selected"
            and bool(prompt_pack.get("reference_bundle_id"))
            and prompt_pack.get("product_lock_mode") == "reference_i2v"
        )
        blockers = self._real_smoke_blockers(
            validation=validation,
            readiness=readiness,
            reference_policy=reference_policy,
            selected_variant=selected_variant,
            prompt_pack=prompt_pack,
            provider_status=provider_status,
        )
        return WorkingVideoPrepareResult(
            status="ready" if selected_variant else "needs_review",
            product_id=product.id,
            sku=product.sku,
            demand_hypothesis_id=demand_record.id,
            buyer_need=hypothesis.buyer_need,
            trigger_situation=hypothesis.trigger_situation,
            pain_point=hypothesis.pain_point,
            objection=hypothesis.objection,
            safe_promise=hypothesis.safe_promise,
            source_refs=hypothesis.source_refs,
            missing_data=list(dict.fromkeys(hypothesis.missing_data + validation.get("missing_data", []))),
            demand_validation=validation,
            creative_spec_id=spec.id,
            selected_hook=selected_variant.hook_text,
            selected_hook_type=(spec.spec_json or {}).get("hook_type", ""),
            first_frame=first_frame,
            asset_kit_id=asset_kit.id if asset_kit else None,
            reference_readiness=readiness,
            reference_policy=reference_policy,
            selected_variant_id=selected_variant.id,
            selected_variant_score=selected_variant.score_json or {},
            generation_variant_id=generation_variant.id if generation_variant else None,
            prompt_pack_id=generation_variant.prompt_pack_id if generation_variant else None,
            prompt_pack=prompt_pack,
            real_smoke_eligible=real_smoke_eligible,
            real_smoke_blockers=blockers,
            provider_status=provider_status,
            warnings=list(
                dict.fromkeys(
                    (demand_record.warnings_json or [])
                    + validation.get("warnings", [])
                    + readiness.get("warnings", [])
                    + reference_policy.get("warnings", [])
                    + (prompt_pack.get("warnings") or [])
                )
            ),
        )

    @staticmethod
    def _real_smoke_blockers(
        *,
        validation: dict,
        readiness: dict,
        reference_policy: dict,
        selected_variant: models.CreativeVariant,
        prompt_pack: dict,
        provider_status: dict,
    ) -> list[str]:
        blockers = []
        if validation.get("errors"):
            blockers.extend(f"demand_error:{item}" for item in validation["errors"])
        if validation.get("missing_data") and validation.get("real_video_eligible") is not True:
            blockers.extend(f"demand_missing_data:{item}" for item in validation["missing_data"])
        if readiness.get("status") != "ready":
            reference_blockers = readiness.get("blockers") or ["product_reference_readiness_not_ready"]
            blockers.extend(f"reference:{item}" for item in reference_blockers)
        if reference_policy.get("strict_real_generation_allowed") is not True:
            policy_blockers = reference_policy.get("blockers") or ["strict_product_reference_policy_not_ready"]
            blockers.extend(f"reference_policy:{item}" for item in policy_blockers)
        if selected_variant.status != "selected":
            blockers.append("selected_variant_required")
        if not prompt_pack.get("reference_bundle_id"):
            blockers.append("prompt_pack_missing_reference_bundle")
        if prompt_pack.get("product_lock_mode") and prompt_pack.get("product_lock_mode") != "reference_i2v":
            blockers.append(f"product_lock_mode:{prompt_pack.get('product_lock_mode')}")
        if provider_status.get("generation_mode") != "real":
            blockers.append("spend_gate:QVF_GENERATION_MODE=real")
        if not provider_status.get("allow_real_spend"):
            blockers.append("spend_gate:QVF_ALLOW_REAL_SPEND=true")
        if not provider_status.get("runway_api_secret_configured"):
            blockers.append("spend_gate:RUNWAYML_API_SECRET configured")
        return list(dict.fromkeys(blockers))

    def _selected_variant(self, selected_variant_id: int) -> models.CreativeVariant:
        selected_variant = self.db.get(models.CreativeVariant, selected_variant_id)
        if not selected_variant:
            raise DemandDataError(f"CreativeVariant {selected_variant_id} not found.")
        if selected_variant.status != "selected" and selected_variant.variant_set.selected_variant_id != selected_variant.id:
            raise ProviderConfigurationError("Working video path requires a selected CreativeVariant.")
        return selected_variant

    def _demand_for_spec(self, creative_spec_id: int) -> models.DemandHypothesisRecord:
        demand_record = self.db.scalar(
            select(models.DemandHypothesisRecord)
            .where(models.DemandHypothesisRecord.creative_spec_id == creative_spec_id)
            .order_by(models.DemandHypothesisRecord.id.desc())
        )
        if not demand_record:
            raise DemandDataError(f"No DemandHypothesisRecord is linked to CreativeSpec {creative_spec_id}.")
        return demand_record

    def _latest_asset_kit(self, product_id: int) -> models.ProductAssetKit | None:
        return (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        )
