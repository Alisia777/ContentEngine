from __future__ import annotations

from app.creative.types import HookCandidate
from app.intelligence.types import CreativeIntelligencePack


HOOKS_BY_FLAG = {
    "low_ctr": ["curiosity_gap", "contradiction", "benefit_first_frame"],
    "low_conversion": ["objection_handling", "trust_builder", "value_explanation"],
    "high_returns": ["expectation_setting", "usage_instruction", "mistake_to_avoid"],
    "competitor_price_pressure": ["comparison", "value_explanation"],
    "stock_risk": ["soft_education", "no_aggressive_promo"],
    "paid_traffic_efficiency_risk": ["message_match", "offer_clarity"],
    "new_product": ["problem_solution", "use_case_demo", "simple_benefit"],
}


class HookStrategySelector:
    def select(self, pack: CreativeIntelligencePack) -> list[HookCandidate]:
        flags = self._flags(pack)
        hook_types = []
        for flag in flags:
            hook_types.extend(HOOKS_BY_FLAG.get(flag, []))
        if not hook_types:
            hook_types = HOOKS_BY_FLAG["new_product"]

        unique_hook_types = list(dict.fromkeys(hook_types))[:3]
        while len(unique_hook_types) < 3:
            for fallback in HOOKS_BY_FLAG["new_product"]:
                if fallback not in unique_hook_types:
                    unique_hook_types.append(fallback)
                if len(unique_hook_types) == 3:
                    break

        return [self._candidate(hook_type, pack, flags) for hook_type in unique_hook_types]

    @staticmethod
    def _flags(pack: CreativeIntelligencePack) -> list[str]:
        flags = list(pack.performance_flags or [])
        flags.extend(pack.market_risks or [])
        if pack.stock_risk and "stock_risk" not in flags:
            flags.append("stock_risk")
        if "no marketplace performance data" in pack.missing_data and "new_product" not in flags:
            flags.append("new_product")
        return flags

    @staticmethod
    def _candidate(hook_type: str, pack: CreativeIntelligencePack, flags: list[str]) -> HookCandidate:
        product = pack.product_title
        objection = pack.buyer_objections[0] if pack.buyer_objections else "why this product is worth attention"
        hook_copy = {
            "curiosity_gap": f"The one detail shoppers miss about {product}",
            "contradiction": f"Looks simple, but {product} solves a real daily friction",
            "benefit_first_frame": f"See the product benefit before the first scroll",
            "objection_handling": f"Wondering {objection}",
            "trust_builder": f"Why shoppers choose {product} for everyday use",
            "value_explanation": f"What makes {product} worth comparing",
            "expectation_setting": f"Before you buy {product}, see how it is meant to be used",
            "usage_instruction": f"Use {product} this way for the clearest result",
            "mistake_to_avoid": f"One mistake to avoid with {product}",
            "comparison": f"Cheaper is not always the same value",
            "soft_education": f"Learn where {product} fits before demand spikes",
            "no_aggressive_promo": f"A calm look at whether {product} fits your routine",
            "message_match": f"If the card made a promise, this video proves it quickly",
            "offer_clarity": f"What you get with {product}, shown plainly",
            "problem_solution": f"One everyday problem {product} is built for",
            "use_case_demo": f"Watch {product} in the exact use case",
            "simple_benefit": f"The simple reason {product} belongs in the routine",
        }
        promise = {
            "curiosity_gap": "The viewer will understand the overlooked reason to keep watching.",
            "objection_handling": "The viewer will see a direct answer to the main purchase doubt.",
            "trust_builder": "The viewer will see source-backed reassurance without inflated claims.",
            "expectation_setting": "The viewer will understand fit and usage before buying.",
            "comparison": "The viewer will compare value without unsupported competitor claims.",
        }.get(hook_type, "The viewer will understand the product fit and next action.")
        return HookCandidate(
            hook_type=hook_type,
            hook_text=hook_copy.get(hook_type, f"See {product} in context"),
            viewer_promise=promise,
            rationale=f"Selected from intelligence flags: {', '.join(flags) or 'new_product'}",
            source_flags=flags,
        )
