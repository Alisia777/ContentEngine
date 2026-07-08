from __future__ import annotations

from app.one_video_acceptance.types import MVPScorecardItem, MVPScorecardOutput, OneVideoScene, ProductScenePolicyOutput


class MVPScorecardBuilder:
    def build_for_plan(self, policy: ProductScenePolicyOutput, scenes: list[OneVideoScene], *, human_review_recorded: bool = False) -> MVPScorecardOutput:
        roles = {scene.role for scene in scenes}
        proof_scene = next((scene for scene in scenes if scene.role == "proof_use_case"), None)
        cta_scene = next((scene for scene in scenes if scene.role == "cta_end_card"), None)
        items = [
            MVPScorecardItem(
                key="product_identity_stable",
                label="Product identity stable",
                weight=20,
                score=18 if policy.wrapper_reference_count >= 2 and policy.end_card_required else 14,
                notes="Wrapper identity is protected by wrapper refs plus packshot/end-card lock.",
            ),
            MVPScorecardItem(
                key="edible_identity_stable",
                label="Edible identity stable",
                weight=20,
                score=20 if policy.edible_kit_ready else 12 if not policy.bite_scene_allowed and not policy.texture_macro_allowed else 8,
                notes="Weak edible kit is acceptable only because bite/macro scenes are blocked or downgraded.",
            ),
            MVPScorecardItem(
                key="scene_policy_followed",
                label="Scene policy followed",
                weight=15,
                score=15 if proof_scene and "bite scene" in " ".join(proof_scene.must_avoid).lower() else 12,
                notes="Unsafe scenes are replaced with approved cutaway insert / reaction.",
            ),
            MVPScorecardItem(
                key="blogger_meaning_clear",
                label="Blogger meaning clear",
                weight=15,
                score=15 if {"hook", "personal_context", "product_reason"}.issubset(roles) else 8,
                notes="The arc contains hook, personal context and product reason.",
            ),
            MVPScorecardItem(
                key="proof_moment_present",
                label="Proof moment present",
                weight=10,
                score=10 if proof_scene else 0,
                notes="Proof is a controlled cutaway insert when edible kit is weak.",
            ),
            MVPScorecardItem(
                key="cta_end_card_present",
                label="CTA/end card present",
                weight=10,
                score=10 if cta_scene and policy.end_card_required else 5,
                notes="End card / packshot lock is required before publishing.",
            ),
            MVPScorecardItem(
                key="human_review_recorded",
                label="Human review recorded",
                weight=10,
                score=10 if human_review_recorded else 0,
                notes="Real output cannot become publishing-ready without human review.",
            ),
        ]
        total = sum(item.score for item in items)
        return MVPScorecardOutput(total_score=total, max_score=sum(item.weight for item in items), verdict=self._verdict(total), items=items)

    @staticmethod
    def _verdict(total: int) -> str:
        if total >= 90:
            return "quality_mvp_success"
        if total >= 75:
            return "usable_with_fixes"
        if total >= 60:
            return "use_as_background_or_needs_regeneration"
        return "reject"
