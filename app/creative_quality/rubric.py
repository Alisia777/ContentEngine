from __future__ import annotations

from dataclasses import dataclass


PASS_THRESHOLD = 80
REWRITE_THRESHOLD = 60

REQUIRED_SCENE_ROLES = ("hook", "personal_context", "product_reason", "proof_demo", "cta")

GENERIC_AD_PHRASES = (
    "buy now",
    "order now",
    "best product",
    "unique offer",
    "limited offer",
    "must have",
    "guaranteed result",
    "works for everyone",
    "revolutionary",
    "the best choice",
    "super deal",
    "perfect for everyone",
    "купи сейчас",
    "закажи сейчас",
    "лучший продукт",
    "уникальное предложение",
    "гарантированный результат",
    "подходит всем",
)

FIRST_PERSON_MARKERS = (
    " i ",
    " i'm ",
    " i've ",
    " my ",
    " me ",
    " tried ",
    " try ",
    " use ",
    " keep ",
    " reach for ",
    " я ",
    " мне ",
    " меня ",
    " мой ",
    " моя ",
    " мои ",
    " пробую ",
    " беру ",
    " использую ",
)

UNSAFE_CLAIM_MARKERS = (
    "cure",
    "treats",
    "heals",
    "guaranteed weight loss",
    "medical result",
    "fixes acne",
    "burn fat",
    "doctor approved result",
    "лечит",
    "вылечит",
    "избавит навсегда",
    "похудение гарантировано",
    "медицинский эффект",
)


@dataclass(frozen=True)
class RubricComponent:
    key: str
    label: str
    max_score: int


RUBRIC_COMPONENTS = (
    RubricComponent("hook_strength", "Hook strength", 15),
    RubricComponent("personal_situation", "Personal situation", 15),
    RubricComponent("buyer_need_clarity", "Buyer need clarity", 15),
    RubricComponent("product_reason", "Product reason", 15),
    RubricComponent("proof_moment", "Proof moment", 10),
    RubricComponent("natural_blogger_language", "Natural blogger language", 10),
    RubricComponent("cta_clarity", "CTA clarity", 5),
    RubricComponent("claims_safety", "Claims safety", 5),
    RubricComponent("product_lock_reference_safety", "Product lock/reference safety", 5),
    RubricComponent("scene_completeness", "Scene completeness", 5),
    RubricComponent("offer_alignment", "Offer alignment", 5),
    RubricComponent("platform_fit", "Platform fit", 5),
)

COMPONENT_MAX_SCORES = {component.key: component.max_score for component in RUBRIC_COMPONENTS}
MAX_TOTAL_SCORE = sum(COMPONENT_MAX_SCORES.values())

REASON_TO_FIX = {
    "generic_ad_voice": "Rewrite lines as first-person creator speech, not announcer copy.",
    "no_personal_context": "Add a concrete personal situation for the creator.",
    "weak_hook": "Open with a specific real-life hook or buyer moment.",
    "missing_buyer_need": "Name the buyer need, pain, desire, or objection.",
    "missing_product_reason": "Explain why this exact product fits the situation.",
    "missing_proof_moment": "Add a proof/demo moment that can be filmed safely.",
    "missing_cta": "Add a low-pressure CTA tied to the product card.",
    "unsafe_claim": "Remove medical, absolute, or unsupported claims.",
    "incomplete_scene_roles": "Complete hook, context, reason, proof, and CTA scene roles.",
    "product_lock_missing": "Select a product lock mode before building provider prompts.",
    "low_reference_count": "Add approved front packshot and label/packaging closeup before strict real generation.",
    "offer_mismatch": "Align the script with the selected offer strategy.",
    "platform_mismatch": "Adapt the script to the selected platform strategy.",
    "competitor_context_missing_when_needed": "Add competitor or price context before using comparison/value framing.",
    "no_reason_to_believe": "Add a concrete proof or reason-to-believe moment.",
}
