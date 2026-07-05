from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.creative.creative_spec_validator import CreativeSpecValidator
from app.creative.hook_strategy import HookStrategySelector
from app.creative.product_geometry import (
    default_product_geometry_rules,
    default_product_scale_rules,
    default_product_visibility_rules,
)
from app.creative.quality_rubric import default_quality_rubric
from app.creative.scene_plan_builder import ScenePlanBuilder
from app.creative.types import CreativeSpec, FirstFrameSpec, ProductGeometrySpec
from app.demand.demand_to_creative_mapper import DemandToCreativeMapper
from app.demand.types import DemandHypothesis
from app.intelligence.errors import MissingGeneratorDataError
from app.intelligence.insight_builder import CreativeIntelligenceBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.types import CreativeIntelligencePack


class CreativeSpecBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_for_product(
        self,
        product_id: int,
        *,
        platform: str,
        duration_seconds: int,
        format: str = "short_video",
        aspect_ratio: str = "9:16",
    ) -> models.VideoCreativeSpecRecord:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise MissingGeneratorDataError(f"Product {product_id} not found.")
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        )
        intelligence_record = CreativeIntelligenceBuilder(self.db).build_for_product(product_id)
        script_brief = ScriptBriefBuilder(self.db).build_from_record(intelligence_record.id)
        pack = CreativeIntelligencePack.model_validate(intelligence_record.pack_json)
        hook_candidates = HookStrategySelector().select(pack)
        selected_hook = hook_candidates[0]
        allowed_claim_refs = [f"{claim.source_type}:{claim.source_key}" for claim in pack.allowed_claims]
        warnings = list(pack.warnings or [])
        reference_images = list(product.images_json or [])
        if not reference_images:
            warnings.append("No product reference images available; prompts must not hallucinate packaging.")
        product_display_rules = [
            "Show the real product in the first frame.",
            "Do not hallucinate packaging, labels, colors, or product shape.",
            "Keep product visible, well-lit, and not distorted.",
        ]
        product_geometry_spec = ProductGeometrySpec(
            product_id=product.id,
            sku=product.sku,
            primary_reference_asset_id=self._primary_reference_asset_id(product.id),
        )
        first_frame = FirstFrameSpec(
            visual_hook=f"{product.title} large in hand or on a clean surface, visible immediately.",
            text_overlay=selected_hook.hook_text[:90],
            product_visible_by_second=1.5,
            product_display=product_display_rules[0],
            composition="Product occupies the center third with readable text overlay above or beside it.",
            viewer_promise=selected_hook.viewer_promise,
        )
        cta = (brand_guide.allowed_cta_json or ["Open the product card"])[0] if brand_guide else "Open the product card"
        scenes = ScenePlanBuilder().build(
            pack=pack,
            selected_hook=selected_hook,
            duration_seconds=duration_seconds,
            first_frame=first_frame,
            allowed_claims=pack.allowed_claims,
            cta=cta,
        )
        spec = CreativeSpec(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            platform=platform,
            format=format,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            creative_objective=pack.recommended_objective,
            creative_angle=pack.recommended_creative_angles[0] if pack.recommended_creative_angles else "value_explanation",
            hook_candidates=hook_candidates,
            selected_hook=selected_hook,
            hook_type=selected_hook.hook_type,
            hook_text=selected_hook.hook_text,
            viewer_promise=selected_hook.viewer_promise,
            first_frame_spec=first_frame,
            scene_plan=scenes,
            captions=[scene.caption for scene in scenes],
            voiceover=[scene.voiceover for scene in scenes],
            visual_style=brand_guide.visual_style if brand_guide and brand_guide.visual_style else "Clean realistic marketplace product video.",
            product_display_rules=product_display_rules,
            product_geometry_spec=product_geometry_spec,
            product_geometry_rules=default_product_geometry_rules(),
            product_scale_rules=default_product_scale_rules(),
            product_visibility_rules=default_product_visibility_rules(),
            must_include=[fact.fact for fact in pack.product_facts[:3]],
            must_avoid=list(dict.fromkeys(["medical claims", "treatment claims", "guaranteed result"] + (brand_guide.forbidden_claims_json if brand_guide else []) + warnings)),
            allowed_claims=pack.allowed_claims,
            allowed_claim_refs=allowed_claim_refs,
            reference_images=reference_images,
            source_map={**pack.source_map, "creative_intelligence_pack_id": intelligence_record.id, "script_brief_id": script_brief.id},
            quality_rubric=default_quality_rubric(reference_images_required=bool(reference_images)),
            warnings=list(dict.fromkeys(warnings)),
            cta=cta,
        )
        validation = CreativeSpecValidator().validate(
            spec,
            forbidden_words=brand_guide.forbidden_words_json if brand_guide else [],
            forbidden_claims=brand_guide.forbidden_claims_json if brand_guide else [],
        )
        spec.validation_report = validation
        record = models.VideoCreativeSpecRecord(
            product_id=product.id,
            intelligence_pack_id=intelligence_record.id,
            script_brief_id=script_brief.id,
            platform=platform,
            format=format,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            status="ready" if validation.valid else "needs_revision",
            spec_json=spec.model_dump(mode="json"),
            hook_candidates_json=[candidate.model_dump(mode="json") for candidate in hook_candidates],
            validation_report_json=validation.model_dump(mode="json"),
            warnings_json=spec.warnings,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def build_from_demand(
        self,
        demand_hypothesis_id: int,
        *,
        platform: str,
        duration_seconds: int,
        format: str = "short_video",
        aspect_ratio: str = "9:16",
    ) -> models.VideoCreativeSpecRecord:
        demand_record = self.db.get(models.DemandHypothesisRecord, demand_hypothesis_id)
        if not demand_record:
            raise MissingGeneratorDataError(f"DemandHypothesisRecord {demand_hypothesis_id} not found.")
        product = self.db.get(models.Product, demand_record.product_id)
        if not product:
            raise MissingGeneratorDataError(f"Product {demand_record.product_id} not found.")
        brand_guide = self.db.scalar(
            select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id)
        )
        mapper = DemandToCreativeMapper()
        hypothesis = DemandHypothesis.model_validate(demand_record.hypothesis_json)
        pack = mapper.to_intelligence_pack(product, hypothesis)
        intelligence_record = models.CreativeIntelligencePackRecord(
            product_id=product.id,
            sku=product.sku,
            status="ready",
            pack_json=pack.model_dump(mode="json"),
            source_summary_json={**pack.source_map, "demand_hypothesis_id": demand_record.id},
            warnings_json=pack.warnings,
        )
        self.db.add(intelligence_record)
        self.db.commit()
        self.db.refresh(intelligence_record)
        script_brief = ScriptBriefBuilder(self.db).build_from_record(intelligence_record.id)
        hook_candidates = mapper.hook_candidates(hypothesis)
        selected_hook = hook_candidates[0]
        allowed_claim_refs = [f"{claim.source_type}:{claim.source_key}" for claim in pack.allowed_claims]
        warnings = list(dict.fromkeys((pack.warnings or []) + (hypothesis.missing_data or [])))
        reference_images = list(product.images_json or [])
        if not reference_images:
            warnings.append("No product reference images available; prompts must not hallucinate packaging.")
        product_display_rules = [
            "Show the real product in the first frame.",
            "Do not hallucinate packaging, labels, colors, or product shape.",
            "Keep product visible, well-lit, and not distorted.",
        ]
        product_geometry_spec = ProductGeometrySpec(
            product_id=product.id,
            sku=product.sku,
            primary_reference_asset_id=self._primary_reference_asset_id(product.id),
        )
        first_frame = mapper.first_frame(product, hypothesis, selected_hook)
        cta = (brand_guide.allowed_cta_json or ["Open the product card"])[0] if brand_guide else "Open the product card"
        if hypothesis.stock_risk:
            cta = "Check whether this fits your routine"
        scenes = ScenePlanBuilder().build(
            pack=pack,
            selected_hook=selected_hook,
            duration_seconds=duration_seconds,
            first_frame=first_frame,
            allowed_claims=pack.allowed_claims,
            cta=cta,
        )
        spec = CreativeSpec(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            platform=platform,
            format=format,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            creative_objective=pack.recommended_objective,
            creative_angle=pack.recommended_creative_angles[0] if pack.recommended_creative_angles else hypothesis.need_type,
            hook_candidates=hook_candidates,
            selected_hook=selected_hook,
            hook_type=selected_hook.hook_type,
            hook_text=selected_hook.hook_text,
            viewer_promise=selected_hook.viewer_promise,
            first_frame_spec=first_frame,
            scene_plan=scenes,
            captions=[scene.caption for scene in scenes],
            voiceover=[scene.voiceover for scene in scenes],
            visual_style=brand_guide.visual_style if brand_guide and brand_guide.visual_style else "Clean realistic marketplace product video.",
            product_display_rules=product_display_rules,
            product_geometry_spec=product_geometry_spec,
            product_geometry_rules=default_product_geometry_rules(),
            product_scale_rules=default_product_scale_rules(),
            product_visibility_rules=default_product_visibility_rules(),
            must_include=[hypothesis.safe_promise],
            must_avoid=list(
                dict.fromkeys(
                    ["medical claims", "treatment claims", "guaranteed result"]
                    + hypothesis.unsafe_promises_blocked
                    + (brand_guide.forbidden_claims_json if brand_guide else [])
                    + warnings
                )
            ),
            allowed_claims=pack.allowed_claims,
            allowed_claim_refs=allowed_claim_refs,
            reference_images=reference_images,
            source_map={
                **pack.source_map,
                "creative_intelligence_pack_id": intelligence_record.id,
                "script_brief_id": script_brief.id,
                "demand_hypothesis_id": demand_record.id,
            },
            quality_rubric=default_quality_rubric(reference_images_required=bool(reference_images)),
            warnings=list(dict.fromkeys(warnings)),
            cta=cta,
        )
        validation = CreativeSpecValidator().validate(
            spec,
            forbidden_words=brand_guide.forbidden_words_json if brand_guide else [],
            forbidden_claims=brand_guide.forbidden_claims_json if brand_guide else [],
        )
        spec.validation_report = validation
        record = models.VideoCreativeSpecRecord(
            product_id=product.id,
            intelligence_pack_id=intelligence_record.id,
            script_brief_id=script_brief.id,
            platform=platform,
            format=format,
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            status="ready" if validation.valid else "needs_revision",
            spec_json=spec.model_dump(mode="json"),
            hook_candidates_json=[candidate.model_dump(mode="json") for candidate in hook_candidates],
            validation_report_json=validation.model_dump(mode="json"),
            warnings_json=spec.warnings,
        )
        self.db.add(record)
        self.db.flush()
        demand_record.creative_spec_id = record.id
        self.db.commit()
        self.db.refresh(record)
        return record

    def _primary_reference_asset_id(self, product_id: int) -> int | None:
        asset = self.db.scalar(
            select(models.ProductAsset)
            .where(models.ProductAsset.product_id == product_id, models.ProductAsset.is_primary_reference.is_(True))
            .order_by(models.ProductAsset.id.desc())
        )
        return asset.id if asset else None
