from __future__ import annotations

import re
from typing import Any

from app import models


class ProfilePackBuilder:
    def build(self, product: models.Product | None, *, platform: str, index: int = 1) -> dict[str, Any]:
        title = product.title if product else "Bombar selection"
        sku = product.sku if product else f"mix-{index}"
        category = (product.category or "products") if product else "products"
        focus = self._focus(title, category)
        base = self._slug(f"{focus}-{sku}")[:24].strip("_") or f"bombar_{index}"
        handle = f"bombar_{base}_{index}"[:30].strip("_")
        account_name = f"Bombar {focus.title()} #{index}"
        cta = "Link points to the official product page or campaign storefront."
        return {
            "account_name": account_name,
            "handle_options": [
                handle,
                f"{base}_by_bombar"[:30].strip("_"),
                f"bombar_{self._slug(category)}_{index}"[:30].strip("_"),
            ],
            "bio_variants": [
                f"{title}: short product videos, source-backed facts, and no medical promises.",
                f"Bombar launch: {category}. Product-first videos, safe usage context, and clear CTA.",
                f"Bombar product video stream: {focus}. Approved references and human review before publishing.",
            ],
            "content_pillars": [
                "product_reference_first",
                "usage_context",
                "objection_handling",
                "safe_claims_only",
                "manual_review_required",
            ],
            "first_posts": self._first_posts(title, sku, platform),
            "highlights": ["Product", "How to use", "FAQ", "Reviews", "Care"],
            "link_cta_strategy": {
                "primary_cta": "Open product card",
                "secondary_cta": "Save instructions",
                "rule": cta,
            },
            "posting_rules": [
                "Publish only approved video or manual upload package.",
                "Do not repeat the same video in one destination.",
                "Respect campaign daily and weekly limits.",
                "Do not use medical, treatment, or guaranteed claims.",
            ],
            "setup_checklist": [
                "Create the owned destination manually or import a verified owned account.",
                "Apply suggested name and handle.",
                "Upload avatar/logo from the approved asset kit.",
                "Add bio and official product/storefront link.",
                "Check OAuth/api mode when the platform supports official upload.",
                "Use manual-assisted mode for platforms without official API upload.",
                "Do not publish content without human approval.",
            ],
        }

    @staticmethod
    def _first_posts(title: str, sku: str, platform: str) -> list[dict[str, str]]:
        angles = [
            ("hook", "Show the product in the first frame and name the viewer problem."),
            ("reference", "Close-up product or texture shot with prompt-pack caption."),
            ("usage", "Step-by-step usage context without risky promises."),
            ("objection", "Set expectations: gradual result, consistency, and limits."),
            ("safety", "Patch test, restrictions, and careful use."),
            ("comparison", "Explain how this SKU differs from alternatives without attacking competitors."),
            ("routine", "What to combine with and what to avoid in the routine."),
            ("faq", "Answer a frequent product-card question."),
            ("cta", "Short product video with CTA and official product link."),
        ]
        return [
            {
                "slot": str(index),
                "sku": sku,
                "platform": platform,
                "angle": angle,
                "title": f"{title}: {description}",
                "status": "planned",
            }
            for index, (angle, description) in enumerate(angles, start=1)
        ]

    @staticmethod
    def _focus(title: str, category: str) -> str:
        value = title or category or "launch"
        words = [word for word in re.split(r"\W+", value.lower()) if len(word) > 2]
        return " ".join(words[:2]) or "launch"

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^\w]+", "_", value.lower()).strip("_")
        return slug or "launch"
