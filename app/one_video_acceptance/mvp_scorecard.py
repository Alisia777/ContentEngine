from __future__ import annotations

from app.one_video_acceptance.types import MVPScorecardItem, MVPScorecardOutput, OneVideoScene, ProductScenePolicyOutput


class MVPScorecardBuilder:
    def build_for_plan(self, policy: ProductScenePolicyOutput, scenes: list[OneVideoScene], *, human_review_recorded: bool = False) -> MVPScorecardOutput:
        roles = {scene.role for scene in scenes}
        proof_scene = next((scene for scene in scenes if scene.role == "proof_use_case"), None)
        cta_scene = next((scene for scene in scenes if scene.role == "cta_end_card"), None)
        identity_ready = policy.current_asset_tier in {"tier_2", "tier_3", "tier_4"}
        interaction_ready = policy.tasting_scene_allowed if policy.product_profile == "food_snack" else policy.interaction_scene_allowed
        sensitive_interaction_blocked = not interaction_ready and bool(policy.blocked_scene_types)
        items = [
            MVPScorecardItem(
                key="product_identity_stable",
                label="Product identity stable",
                weight=20,
                score=18 if identity_ready and policy.end_card_required else 14 if policy.packshot_overlay_required else 8,
                notes="Exact SKU identity is protected by the Product Asset Contract plus packshot/end-card lock.",
            ),
            MVPScorecardItem(
                key="product_interaction_stable",
                label="Product interaction stable",
                weight=20,
                score=20 if interaction_ready else 12 if sensitive_interaction_blocked else 8,
                notes=f"The {policy.interaction_mode} interaction is reference-gated; unsafe or unsupported actions remain blocked.",
            ),
            MVPScorecardItem(
                key="scene_policy_followed",
                label="Scene policy followed",
                weight=15,
                score=15 if proof_scene and (interaction_ready or sensitive_interaction_blocked) else 12,
                notes="Unsupported interaction is replaced with an approved insert, overlay or creator reaction.",
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
                notes="Proof is category-appropriate and limited by approved use-case references.",
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
