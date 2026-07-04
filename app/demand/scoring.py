from __future__ import annotations

from app.demand.types import DemandRuleRecommendation


RULES: dict[str, DemandRuleRecommendation] = {
    "low_ctr": DemandRuleRecommendation(
        rule_key="low_ctr",
        need_type="awareness_need",
        buyer_need="Understand why this product deserves attention before scrolling past.",
        trigger_situation="The shopper sees the product card or ad but has not noticed a clear reason to care.",
        pain_point="The first impression is too generic, so the product is easy to ignore.",
        default_objection="what makes this worth opening instead of skipping?",
        recommended_hook_types=["curiosity_gap", "benefit_first_frame", "contradiction"],
        recommended_first_frame="Immediate packshot or product-in-hand frame with one overlooked benefit.",
        creative_objective="improve_clickability",
        creative_angle="awareness_hook",
    ),
    "low_conversion": DemandRuleRecommendation(
        rule_key="low_conversion",
        need_type="trust_and_clarity_need",
        buyer_need="Get enough proof and clarity to decide whether the product fits.",
        trigger_situation="The shopper is interested enough to click but hesitates before purchase.",
        pain_point="The value, use case, or proof is not yet clear enough.",
        default_objection="why should I trust this product or choose it now?",
        recommended_hook_types=["objection_handling", "trust_builder", "value_explanation"],
        recommended_first_frame="Open with the product and the main buyer doubt in readable overlay text.",
        creative_objective="improve_conversion",
        creative_angle="objection_handling",
    ),
    "high_returns": DemandRuleRecommendation(
        rule_key="high_returns",
        need_type="expectation_setting_need",
        buyer_need="Understand fit, usage, and limitations before buying.",
        trigger_situation="Buyers may be misreading what the product does or how it should be used.",
        pain_point="Wrong expectations create disappointment or returns.",
        default_objection="will it work for my exact use case?",
        recommended_hook_types=["expectation_setting", "usage_instruction", "mistake_to_avoid"],
        recommended_first_frame="Show the real use context and set the expectation in the first line.",
        creative_objective="reduce_returns",
        creative_angle="expectation_setting",
    ),
    "competitor_price_pressure": DemandRuleRecommendation(
        rule_key="competitor_price_pressure",
        need_type="comparison_value_need",
        buyer_need="Compare value without relying only on the cheapest price.",
        trigger_situation="The shopper sees a cheaper competitor and needs a reason to compare value.",
        pain_point="Price pressure can make the product look interchangeable.",
        default_objection="why not buy the cheaper alternative?",
        recommended_hook_types=["comparison", "value_explanation", "trust_builder"],
        recommended_first_frame="Show the product clearly while naming the value comparison safely.",
        creative_objective="explain_value",
        creative_angle="value_comparison",
    ),
    "stock_risk": DemandRuleRecommendation(
        rule_key="stock_risk",
        need_type="soft_education_need",
        buyer_need="Learn whether the product fits without being pushed by aggressive promo.",
        trigger_situation="Inventory risk means demand should be educated, not over-stimulated.",
        pain_point="Aggressive CTA could create demand the operation should not encourage.",
        default_objection="is this useful for my routine?",
        recommended_hook_types=["soft_education", "no_aggressive_promo", "use_case_demo"],
        recommended_first_frame="Calm product context with educational overlay, no urgency framing.",
        creative_objective="soft_education",
        creative_angle="use_case_education",
        cta_tone="soft",
    ),
    "no_strong_data": DemandRuleRecommendation(
        rule_key="no_strong_data",
        need_type="simple_use_case_introduction",
        buyer_need="Understand the basic use case and product fit.",
        trigger_situation="There is not enough performance evidence to choose a sharper angle.",
        pain_point="The product needs a clear, conservative introduction.",
        default_objection="what is this product for?",
        recommended_hook_types=["problem_solution", "use_case_demo", "simple_benefit"],
        recommended_first_frame="Show the product immediately in its simplest real use case.",
        creative_objective="introduce_product",
        creative_angle="simple_use_case",
    ),
}

PRIORITY = ["low_ctr", "low_conversion", "high_returns", "competitor_price_pressure", "stock_risk", "no_strong_data"]


def select_demand_rule(flags: list[str]) -> DemandRuleRecommendation:
    for key in PRIORITY:
        if key in flags:
            return RULES[key]
    return RULES["no_strong_data"]
