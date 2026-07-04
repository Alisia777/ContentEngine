from __future__ import annotations

from app import models
from app.creative.types import FirstFrameSpec, HookCandidate
from app.demand.types import DemandHypothesis
from app.intelligence.source_mapping import product_facts
from app.intelligence.types import ContentLearning, CreativeIntelligencePack


class DemandToCreativeMapper:
    def to_intelligence_pack(self, product: models.Product, hypothesis: DemandHypothesis) -> CreativeIntelligencePack:
        facts, allowed_claims = product_facts(product)
        objective = {
            "awareness_need": "improve_clickability",
            "trust_and_clarity_need": "improve_conversion",
            "expectation_setting_need": "reduce_returns",
            "comparison_value_need": "explain_value",
            "soft_education_need": "soft_education",
        }.get(hypothesis.need_type, "introduce_product")
        return CreativeIntelligencePack(
            sku=product.sku,
            product_id=product.id,
            product_title=product.title,
            product_facts=facts,
            allowed_claims=allowed_claims,
            missing_data=hypothesis.missing_data,
            performance_flags=hypothesis.performance_flags,
            buyer_objections=[hypothesis.objection],
            buyer_language=hypothesis.buyer_language,
            content_learnings=[
                ContentLearning(
                    platform="internal",
                    creative_angle=hypothesis.need_type,
                    hook_text=hypothesis.recommended_hook_types[0] if hypothesis.recommended_hook_types else None,
                )
            ],
            market_risks=hypothesis.market_risks,
            stock_risk=hypothesis.stock_risk,
            price_positioning="competitor_cheaper" if "competitor_price_pressure" in hypothesis.market_risks else None,
            recommended_objective=objective,
            recommended_creative_angles=hypothesis.recommended_hook_types or ["simple_benefit"],
            recommended_video_formats=["9:16_short", "captioned_scene_sequence"],
            source_map={**hypothesis.source_map, "demand_hypothesis": True},
            warnings=hypothesis.unsafe_promises_blocked,
            reasoning_summary=hypothesis.reasoning,
        )

    def hook_candidates(self, hypothesis: DemandHypothesis) -> list[HookCandidate]:
        hooks = hypothesis.recommended_hook_types or ["simple_benefit", "use_case_demo", "problem_solution"]
        candidates = []
        for hook_type in hooks[:3]:
            candidates.append(
                HookCandidate(
                    hook_type=hook_type,
                    hook_text=self._hook_text(hook_type, hypothesis),
                    viewer_promise=hypothesis.safe_promise,
                    rationale=f"Demand need: {hypothesis.buyer_need}",
                    source_flags=list(dict.fromkeys(hypothesis.performance_flags + hypothesis.market_risks)),
                )
            )
        while len(candidates) < 3:
            candidates.append(
                HookCandidate(
                    hook_type="use_case_demo",
                    hook_text=f"See {hypothesis.product_title} in the real use case",
                    viewer_promise=hypothesis.safe_promise,
                    rationale="Fallback demand-safe use-case hook.",
                    source_flags=list(dict.fromkeys(hypothesis.performance_flags + hypothesis.market_risks)),
                )
            )
        return candidates

    @staticmethod
    def first_frame(product: models.Product, hypothesis: DemandHypothesis, selected_hook: HookCandidate) -> FirstFrameSpec:
        return FirstFrameSpec(
            visual_hook=f"{product.title} visible immediately. {hypothesis.recommended_first_frame}",
            text_overlay=selected_hook.hook_text[:90],
            product_visible_by_second=1.0,
            product_display="Product is visible in the first frame with packaging, shape, and label kept believable.",
            composition="Vertical 9:16, product in the center third, overlay clear of packaging.",
            viewer_promise=hypothesis.safe_promise,
        )

    @staticmethod
    def _hook_text(hook_type: str, hypothesis: DemandHypothesis) -> str:
        product = hypothesis.product_title
        if hook_type == "curiosity_gap":
            return f"The detail people miss before choosing {product}"
        if hook_type == "benefit_first_frame":
            return hypothesis.safe_promise[:90]
        if hook_type == "objection_handling":
            return f"Wondering {hypothesis.objection}"
        if hook_type == "trust_builder":
            return f"Why {product} fits this need"
        if hook_type == "value_explanation":
            return f"What makes {product} worth comparing"
        if hook_type == "expectation_setting":
            return f"Before you buy {product}, check the fit"
        if hook_type == "comparison":
            return "Cheaper is not always the same value"
        if hook_type == "soft_education":
            return f"A calm look at where {product} fits"
        return f"See {product} in the exact use case"
