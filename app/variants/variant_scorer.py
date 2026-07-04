from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.creative.types import CreativeSpec
from app.intelligence.types import CreativeIntelligencePack
from app.variants.errors import VariantDataError
from app.variants.types import VariantScoreResult


class VariantScorer:
    def __init__(self, db: Session):
        self.db = db

    def score_set(self, variant_set_id: int) -> models.CreativeVariantSet:
        variant_set = self.db.get(models.CreativeVariantSet, variant_set_id)
        if not variant_set:
            raise VariantDataError(f"CreativeVariantSet {variant_set_id} not found.")
        for variant in variant_set.variants:
            self.score_variant(variant)
        scores = [variant.score_json for variant in variant_set.variants if variant.score_json]
        variant_set.score_summary_json = {
            "scores": [{"creative_variant_id": variant.id, **variant.score_json} for variant in variant_set.variants],
            "metadata_only": True,
        }
        variant_set.status = "scored"
        self.db.commit()
        self.db.refresh(variant_set)
        return variant_set

    def score_variant(self, variant: models.CreativeVariant) -> VariantScoreResult:
        spec_record = variant.creative_spec
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        pack = self._pack(spec_record)
        dimensions = {
            "hook_strength": self._hook_strength(variant.hook_text, pack),
            "first_frame_clarity": self._first_frame_clarity(variant),
            "product_visibility": 1.0 if variant.product_reveal_timing <= 1.0 else 0.35,
            "claim_safety": self._claim_safety(variant, spec),
            "asset_readiness": self._asset_readiness(variant, variant.variant_set.asset_kit),
            "platform_fit": 0.9 if spec.platform.lower() in {"instagram reels", "tiktok", "youtube shorts"} else 0.7,
            "cta_clarity": 0.9 if variant.cta_framing and len(variant.cta_framing) <= 80 else 0.55,
        }
        risk_flags = list(variant.risk_flags_json or [])
        if variant.product_reveal_timing > 1.0:
            risk_flags.append("product_not_visible_in_first_second")
        if dimensions["asset_readiness"] < 0.5:
            risk_flags.append("missing_product_reference_assets")
        if dimensions["claim_safety"] < 1:
            risk_flags.append("forbidden_or_medical_claim_risk")
        if dimensions["hook_strength"] < 0.5:
            risk_flags.append("vague_hook")
        risk_penalty = min(0.35, 0.07 * len(set(risk_flags)))
        dimensions["risk_penalty"] = round(risk_penalty, 3)
        positive = sum(value for key, value in dimensions.items() if key != "risk_penalty") / 7
        score = max(0, min(100, round((positive - risk_penalty) * 100, 2)))
        critical_risks = {
            "product_not_visible_in_first_second",
            "forbidden_or_medical_claim_risk",
            "missing_product_reference_assets",
            "packshot_missing_for_product_accuracy",
        }
        safe = score >= 60 and not critical_risks.intersection(risk_flags)
        result = VariantScoreResult(
            score=score,
            safe=safe,
            dimensions={key: round(value, 3) for key, value in dimensions.items()},
            risk_flags=list(dict.fromkeys(risk_flags)),
            notes=["Metadata/rules-based score. No visual inspection or computer vision was performed."],
        )
        variant.score_json = result.model_dump(mode="json")
        variant.risk_flags_json = result.risk_flags
        variant.status = "safe" if safe else "needs_review"
        return result

    def _pack(self, spec_record: models.VideoCreativeSpecRecord) -> CreativeIntelligencePack | None:
        if not spec_record.intelligence_pack:
            return None
        return CreativeIntelligencePack.model_validate(spec_record.intelligence_pack.pack_json)

    @staticmethod
    def _hook_strength(hook_text: str, pack: CreativeIntelligencePack | None) -> float:
        text = hook_text.lower()
        score = 0.55
        if any(token in text for token in ["why", "see", "detail", "before", "watch", "one "]):
            score += 0.2
        if len(hook_text) <= 72:
            score += 0.1
        if pack and "low_ctr" in pack.performance_flags and any(token in text for token in ["miss", "see", "scroll", "detail", "benefit"]):
            score += 0.18
        if pack:
            buyer_language = " ".join(pack.buyer_language).lower()
            if buyer_language and any(word in text for word in buyer_language.split()[:8]):
                score += 0.08
        return min(1.0, score)

    @staticmethod
    def _first_frame_clarity(variant: models.CreativeVariant) -> float:
        first_frame = variant.first_frame_json or {}
        overlay = first_frame.get("text_overlay") or ""
        score = 0.55
        if first_frame.get("visual_concept") and first_frame.get("product_placement"):
            score += 0.2
        if 0 < len(overlay) <= 56:
            score += 0.2
        elif len(overlay) <= 72:
            score += 0.1
        return min(1.0, score)

    @staticmethod
    def _claim_safety(variant: models.CreativeVariant, spec: CreativeSpec) -> float:
        values = [variant.hook_text, variant.cta_framing or "", variant.visual_style or ""]
        for scene in variant.scene_plan_json or []:
            values.extend([scene.get("visual", ""), scene.get("caption", ""), scene.get("voiceover", "")])
        text = " ".join(values).lower()
        allowed = " ".join(claim.claim.lower() for claim in spec.allowed_claims)
        risky = ["cure", "medical treatment", "treatment", "guaranteed result"]
        return 0.2 if any(term in text and term not in allowed for term in risky) else 1.0

    @staticmethod
    def _asset_readiness(variant: models.CreativeVariant, asset_kit: models.ProductAssetKit | None) -> float:
        if not variant.asset_refs_json:
            return 0.2
        if not asset_kit:
            return 0.45
        missing = set(asset_kit.missing_assets_json or [])
        if "packshot" in missing:
            return 0.45
        if missing:
            return 0.75
        return 1.0
