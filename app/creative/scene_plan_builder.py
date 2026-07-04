from __future__ import annotations

from app.creative.types import CreativeScene, FirstFrameSpec, HookCandidate
from app.intelligence.types import AllowedClaim, CreativeIntelligencePack


class ScenePlanBuilder:
    def build(
        self,
        *,
        pack: CreativeIntelligencePack,
        selected_hook: HookCandidate,
        duration_seconds: int,
        first_frame: FirstFrameSpec,
        allowed_claims: list[AllowedClaim],
        cta: str,
    ) -> list[CreativeScene]:
        durations = self._durations(duration_seconds)
        roles = self._roles_for_hook(selected_hook.hook_type)
        claim_refs = [f"{claim.source_type}:{claim.source_key}" for claim in allowed_claims]
        primary_claim = allowed_claims[0].claim if allowed_claims else pack.reasoning_summary
        objection = pack.buyer_objections[0] if pack.buyer_objections else "what makes this useful"
        scenes = []
        starts_at = 0
        for index, duration in enumerate(durations, start=1):
            role = roles[index - 1]
            if index == 1:
                caption = first_frame.text_overlay
                voiceover = selected_hook.hook_text
                visual = first_frame.visual_hook
            elif role in {"objection", "problem"}:
                caption = objection
                voiceover = f"If you are asking {objection}, this shows the product fit."
                visual = f"Show the shopper problem around {pack.product_title} in a realistic setting."
            elif role in {"proof", "product_solution", "value"}:
                caption = primary_claim[:90]
                voiceover = primary_claim
                visual = f"Show {pack.product_title} clearly solving the use case without changing packaging."
            else:
                caption = cta
                voiceover = cta
                visual = f"Return to a clear product shot for {pack.product_title} with a simple CTA."
            scenes.append(
                CreativeScene(
                    scene_number=index,
                    role=role,
                    starts_at=starts_at,
                    duration_seconds=duration,
                    visual=visual,
                    caption=caption,
                    voiceover=voiceover,
                    claim_refs=claim_refs[:1] if role != "cta" and claim_refs else [],
                    product_display="Product is visible and not distorted; packaging, shape, and labels stay believable.",
                    camera_motion="slow push-in with stable product framing" if index == 1 else "gentle handheld movement",
                    composition="vertical 9:16, product in the central third, readable text overlay",
                    lighting="bright soft marketplace lighting",
                    emotion="curious" if index == 1 else "reassured",
                    cta=cta if role == "cta" else None,
                )
            )
            starts_at += duration
        return scenes

    @staticmethod
    def _durations(duration_seconds: int) -> list[int]:
        scene_count = 4
        base = max(1, duration_seconds // scene_count)
        durations = [base] * scene_count
        durations[-1] += max(0, duration_seconds - sum(durations))
        return durations

    @staticmethod
    def _roles_for_hook(hook_type: str) -> list[str]:
        if hook_type in {"objection_handling", "trust_builder", "value_explanation"}:
            return ["stop_scroll", "objection", "proof", "cta"]
        if hook_type in {"expectation_setting", "usage_instruction", "mistake_to_avoid"}:
            return ["stop_scroll", "usage_context", "expectation_setting", "cta"]
        return ["stop_scroll", "problem", "product_solution", "cta"]
