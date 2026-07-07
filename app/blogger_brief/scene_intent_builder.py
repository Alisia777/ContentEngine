from __future__ import annotations

from app.blogger_brief.types import SCENE_ROLES


class SceneIntentBuilder:
    def build(self, *, buyer_context: dict, proof_moment: dict, cta: dict, duration_seconds: int = 8) -> list[dict]:
        short = duration_seconds <= 8
        if short:
            roles = ["hook", "personal_context", "product_reason", "proof_demo", "cta"]
        else:
            roles = list(SCENE_ROLES)
        lines = {
            "hook": "I found this for the moment when I want dessert, but still want a snack that fits my routine.",
            "personal_context": buyer_context.get("trigger_situation") or "After training or between tasks, I want something quick and not messy.",
            "product_reason": "The format is easy to carry, and the product is the point of the shot, not a random prop.",
            "proof_demo": proof_moment.get("proof_line") or "I show the real pack, then a separate unwrapped piece for the taste moment.",
            "texture_or_use_case": "Close view of texture or use case, without asking AI to invent packaging.",
            "cta": cta.get("spoken_line") or "Check the product card if you want this kind of snack in your rotation.",
            "end_card": "End on the exact packshot or product card asset, not generated packaging.",
        }
        return [
            {
                "role": role,
                "intention": self._intention(role),
                "emotion": self._emotion(role),
                "spoken_line": lines[role],
                "caption": "" if role != "end_card" else cta.get("caption", ""),
            }
            for role in roles
        ]

    @staticmethod
    def _intention(role: str) -> str:
        return {
            "hook": "stop the scroll with a personal reason",
            "personal_context": "make the buyer situation recognizable",
            "product_reason": "connect the product to the situation",
            "proof_demo": "show credible product proof or use case",
            "texture_or_use_case": "show sensory detail or practical fit",
            "cta": "invite a low-pressure next action",
            "end_card": "finish with exact product identity",
        }.get(role, "support the story")

    @staticmethod
    def _emotion(role: str) -> str:
        return {
            "hook": "curious",
            "personal_context": "relatable",
            "product_reason": "confident",
            "proof_demo": "specific",
            "texture_or_use_case": "appetizing",
            "cta": "friendly",
            "end_card": "clear",
        }.get(role, "natural")
