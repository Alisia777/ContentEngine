from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.intelligence.errors import MissingGeneratorDataError
from app.intelligence.types import CreativeIntelligencePack, ScriptBriefOutput


class ScriptBriefBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(self, intelligence_pack: CreativeIntelligencePack) -> ScriptBriefOutput:
        angle = intelligence_pack.recommended_creative_angles[0] if intelligence_pack.recommended_creative_angles else "value_explanation"
        must_avoid = ["medical claims", "guaranteed result", "cure/treatment language"] + intelligence_pack.warnings
        if intelligence_pack.stock_risk:
            must_avoid.append("aggressive demand generation")
        return ScriptBriefOutput(
            sku=intelligence_pack.sku,
            product_title=intelligence_pack.product_title,
            objective=intelligence_pack.recommended_objective,
            creative_angle=angle,
            target_audience="Marketplace shoppers comparing options and checking product fit.",
            reasoning_summary=intelligence_pack.reasoning_summary,
            allowed_claims=intelligence_pack.allowed_claims,
            buyer_objections=intelligence_pack.buyer_objections,
            buyer_language=intelligence_pack.buyer_language,
            must_include=[fact.fact for fact in intelligence_pack.product_facts[:3]],
            must_avoid=list(dict.fromkeys(must_avoid)),
            visual_direction=[
                "show product clearly in first frame",
                "use realistic product context",
                "keep captions readable",
            ],
            missing_data=intelligence_pack.missing_data,
            safety_warnings=intelligence_pack.warnings,
        )

    def build_from_record(self, intelligence_pack_id: int) -> models.ScriptBrief:
        record = self.db.get(models.CreativeIntelligencePackRecord, intelligence_pack_id)
        if not record:
            raise MissingGeneratorDataError(f"CreativeIntelligencePackRecord {intelligence_pack_id} not found.")
        output = self.build(CreativeIntelligencePack.model_validate(record.pack_json))
        brief = models.ScriptBrief(
            product_id=record.product_id,
            intelligence_pack_id=record.id,
            status="ready",
            objective=output.objective,
            creative_angle=output.creative_angle,
            target_audience=output.target_audience,
            brief_json=output.model_dump(mode="json"),
            allowed_claims_json=[claim.model_dump(mode="json") for claim in output.allowed_claims],
            missing_data_json=output.missing_data,
            safety_warnings_json=output.safety_warnings,
        )
        self.db.add(brief)
        self.db.commit()
        self.db.refresh(brief)
        return brief

