from __future__ import annotations

from app import models


class BloggerPersonaBuilder:
    def build(self, product: models.Product, *, platform: str = "Instagram Reels") -> dict:
        text = " ".join([product.brand, product.title, product.category or "", product.description or ""]).lower()
        sporty = any(marker in text for marker in ["protein", "sport", "fitness", "bar", "bombbar", "snack"])
        if sporty:
            return {
                "persona": "sporty UGC creator",
                "age_range": "25-30",
                "why_credible": "Uses compact snacks around training, work, and active daily routines.",
                "tone": "first-person, energetic, friendly, specific, not announcer-like",
                "setting": "post-workout locker area, gym cafe, kitchen counter, or walk-and-talk after training",
                "platform": platform,
            }
        return {
            "persona": "practical everyday creator",
            "age_range": "25-35",
            "why_credible": "Shows products through real use cases and personal routine.",
            "tone": "first-person, calm, useful, specific, not announcer-like",
            "setting": "home, desk, kitchen, or quick errand routine",
            "platform": platform,
        }
