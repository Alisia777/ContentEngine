from __future__ import annotations

from app import models


class ProofRequirementBuilder:
    def build(self, product: models.Product, demand: models.DemandHypothesisRecord | None, review_summary: dict) -> list[dict]:
        hypothesis = demand.hypothesis_json if demand else {}
        proof_items: list[dict] = []
        for claim in hypothesis.get("proof_required") or []:
            proof_items.append(
                {
                    "proof_type": "source_backed_claim",
                    "proof": claim,
                    "scene_use": "support product reason without overclaiming",
                }
            )
        proof_items.append(
            {
                "proof_type": "product_identity",
                "proof": "show exact approved packshot or reference-backed product, never redrawn packaging",
                "scene_use": "pack-in-hand, packshot overlay, or end card",
            }
        )
        proof_items.append(
            {
                "proof_type": "texture_or_use_case",
                "proof": self._texture_or_use_case(product),
                "scene_use": "show real use, portion, texture, or scale",
            }
        )
        objections = review_summary.get("buyer_objections") or hypothesis.get("buyer_language") or []
        if objections:
            proof_items.append(
                {
                    "proof_type": "objection_answer",
                    "proof": str(objections[0]),
                    "scene_use": "address the main buyer doubt in creator language",
                }
            )
        return proof_items

    @staticmethod
    def _texture_or_use_case(product: models.Product) -> str:
        category = (product.category or "").lower()
        if "snack" in category or "bar" in product.title.lower() or "cookie" in product.title.lower():
            return "show pack size, unwrapped piece, bite/texture, and easy carry moment"
        if "beauty" in category or "skin" in product.title.lower():
            return "show texture, application amount, and safe routine context"
        return f"show how {product.title} is used in a realistic buyer situation"
