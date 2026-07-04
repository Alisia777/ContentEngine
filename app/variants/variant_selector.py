from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.variants.errors import VariantDataError
from app.variants.variant_scorer import VariantScorer


class VariantSelector:
    def __init__(self, db: Session):
        self.db = db

    def select_best(self, variant_set_id: int) -> models.CreativeVariantSet:
        variant_set = self.db.get(models.CreativeVariantSet, variant_set_id)
        if not variant_set:
            raise VariantDataError(f"CreativeVariantSet {variant_set_id} not found.")
        if any(not variant.score_json for variant in variant_set.variants):
            variant_set = VariantScorer(self.db).score_set(variant_set_id)
        safe_variants = [variant for variant in variant_set.variants if (variant.score_json or {}).get("safe")]
        if not safe_variants:
            variant_set.status = "needs_review"
            variant_set.selection_reason = "All variants carry critical risk or scored below safe threshold."
            variant_set.selected_variant_id = None
            self.db.commit()
            self.db.refresh(variant_set)
            return variant_set
        selected = max(safe_variants, key=lambda variant: (variant.score_json or {}).get("score", 0))
        for variant in variant_set.variants:
            if variant.id == selected.id:
                variant.status = "selected"
                variant.selection_reason = "Highest safe metadata/rules-based score."
            elif variant.status == "selected":
                variant.status = "safe"
                variant.selection_reason = None
        variant_set.selected_variant_id = selected.id
        variant_set.status = "selected"
        variant_set.selection_reason = f"Selected variant #{selected.variant_number}: highest safe score {selected.score_json.get('score')}."
        self.db.commit()
        self.db.refresh(variant_set)
        return variant_set
