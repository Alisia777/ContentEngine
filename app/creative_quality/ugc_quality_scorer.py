from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.reference_policy import ProductReferencePolicyService
from app.creative_quality.errors import CreativeQualityDataError
from app.creative_quality.rubric import (
    COMPONENT_MAX_SCORES,
    FIRST_PERSON_MARKERS,
    GENERIC_AD_PHRASES,
    PASS_THRESHOLD,
    REASON_TO_FIX,
    REQUIRED_SCENE_ROLES,
    REWRITE_THRESHOLD,
    RUBRIC_COMPONENTS,
    UNSAFE_CLAIM_MARKERS,
)
from app.creative_quality.types import CreativeQualityComponentScore, CreativeQualityScoreOutput


class UGCQualityScorer:
    def __init__(self, db: Session):
        self.db = db

    def score_script(self, ugc_script_id: int, *, prompt_pack_id: int | None = None) -> models.CreativeQualityScore:
        script = self.db.get(models.UGCAdScript, ugc_script_id)
        if not script:
            raise CreativeQualityDataError(f"UGCAdScript {ugc_script_id} not found.")
        meaning = script.blogger_meaning_spec
        if not meaning:
            raise CreativeQualityDataError(f"UGCAdScript {ugc_script_id} is missing BloggerMeaningSpec.")
        product = self.db.get(models.Product, meaning.product_id)
        if not product:
            raise CreativeQualityDataError(f"Product {meaning.product_id} not found.")

        component_scores, reasons = self._component_scores(script, meaning)
        total_score = float(sum(component_scores.values()))
        reasons = list(dict.fromkeys(reasons))
        status = self._status(total_score, reasons)
        required_fixes = [REASON_TO_FIX[reason] for reason in reasons if reason in REASON_TO_FIX]
        breakdown = self._breakdown(component_scores)
        gate_json = self._gate_json(product.id, reasons)

        score = models.CreativeQualityScore(
            product_id=product.id,
            sku=product.sku,
            blogger_meaning_spec_id=meaning.id,
            ugc_script_id=script.id,
            creative_variant_id=script.creative_variant_id,
            prompt_pack_id=prompt_pack_id,
            status=status,
            total_score=total_score,
            hook_strength_score=component_scores["hook_strength"],
            personal_situation_score=component_scores["personal_situation"],
            buyer_need_clarity_score=component_scores["buyer_need_clarity"],
            product_reason_score=component_scores["product_reason"],
            proof_moment_score=component_scores["proof_moment"],
            natural_blogger_language_score=component_scores["natural_blogger_language"],
            cta_clarity_score=component_scores["cta_clarity"],
            claims_safety_score=component_scores["claims_safety"],
            product_lock_reference_safety_score=component_scores["product_lock_reference_safety"],
            scene_completeness_score=component_scores["scene_completeness"],
            reasons_json=reasons,
            required_fixes_json=required_fixes,
            breakdown_json=breakdown,
            gate_json=gate_json,
        )
        self.db.add(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def latest_for_script(self, ugc_script_id: int) -> models.CreativeQualityScore | None:
        return self.db.scalar(
            select(models.CreativeQualityScore)
            .where(models.CreativeQualityScore.ugc_script_id == ugc_script_id)
            .order_by(models.CreativeQualityScore.id.desc())
        )

    def as_output(self, score: models.CreativeQualityScore) -> CreativeQualityScoreOutput:
        breakdown = score.breakdown_json or self._breakdown(
            {
                "hook_strength": score.hook_strength_score,
                "personal_situation": score.personal_situation_score,
                "buyer_need_clarity": score.buyer_need_clarity_score,
                "product_reason": score.product_reason_score,
                "proof_moment": score.proof_moment_score,
                "natural_blogger_language": score.natural_blogger_language_score,
                "cta_clarity": score.cta_clarity_score,
                "claims_safety": score.claims_safety_score,
                "product_lock_reference_safety": score.product_lock_reference_safety_score,
                "scene_completeness": score.scene_completeness_score,
            }
        )
        return CreativeQualityScoreOutput(
            id=score.id,
            product_id=score.product_id,
            sku=score.sku,
            blogger_meaning_spec_id=score.blogger_meaning_spec_id,
            ugc_script_id=score.ugc_script_id,
            creative_variant_id=score.creative_variant_id,
            prompt_pack_id=score.prompt_pack_id,
            status=score.status,
            total_score=score.total_score,
            breakdown=[CreativeQualityComponentScore(**item) for item in breakdown],
            reasons=score.reasons_json or [],
            required_fixes=score.required_fixes_json or [],
        )

    def _component_scores(
        self,
        script: models.UGCAdScript,
        meaning: models.BloggerMeaningSpec,
    ) -> tuple[dict[str, float], list[str]]:
        scenes = script.scene_script_json or []
        role_to_scene = {scene.get("role"): scene for scene in scenes if scene.get("role")}
        all_text = self._all_text(script, meaning)
        reasons: list[str] = []
        scores = {key: 0.0 for key in COMPONENT_MAX_SCORES}

        hook_line = str((role_to_scene.get("hook") or {}).get("spoken_line") or "")
        if len(hook_line.strip()) >= 20 and not self._has_generic_ad_voice(hook_line):
            scores["hook_strength"] = 15
        elif hook_line.strip():
            scores["hook_strength"] = 7
            reasons.append("weak_hook")
        else:
            reasons.append("weak_hook")

        personal_line = str((role_to_scene.get("personal_context") or {}).get("spoken_line") or "")
        if personal_line and (self._has_first_person(personal_line) or self._has_personal_situation(personal_line)):
            scores["personal_situation"] = 15
        elif personal_line:
            scores["personal_situation"] = 7
            reasons.append("no_personal_context")
        else:
            reasons.append("no_personal_context")

        buyer_context = meaning.buyer_context_json or {}
        if buyer_context.get("buyer_situation") and buyer_context.get("pain_or_desire"):
            scores["buyer_need_clarity"] = 15
        elif buyer_context.get("buyer_situation") or "need" in all_text or "нужно" in all_text:
            scores["buyer_need_clarity"] = 7
            reasons.append("missing_buyer_need")
        else:
            reasons.append("missing_buyer_need")

        product_reason_line = str((role_to_scene.get("product_reason") or {}).get("spoken_line") or "")
        if product_reason_line and self._mentions_product_reason(product_reason_line):
            scores["product_reason"] = 15
        elif product_reason_line:
            scores["product_reason"] = 7
            reasons.append("missing_product_reason")
        else:
            reasons.append("missing_product_reason")

        proof_scene = role_to_scene.get("proof_demo") or {}
        proof = meaning.proof_moment_json or {}
        proof_line = str(proof_scene.get("spoken_line") or "")
        if proof_line and self._mentions_proof(proof_line):
            scores["proof_moment"] = 10
        elif proof_line:
            scores["proof_moment"] = 4
            reasons.append("missing_proof_moment")
        else:
            reasons.append("missing_proof_moment")

        if self._has_generic_ad_voice(all_text):
            scores["natural_blogger_language"] = 3
            reasons.append("generic_ad_voice")
        elif self._has_first_person(all_text):
            scores["natural_blogger_language"] = 10
        else:
            scores["natural_blogger_language"] = 5
            reasons.append("generic_ad_voice")

        cta_line = str((role_to_scene.get("cta") or {}).get("spoken_line") or (meaning.cta_json or {}).get("spoken_line") or "")
        if cta_line.strip():
            scores["cta_clarity"] = 5
        else:
            reasons.append("missing_cta")

        if self._has_unsafe_claim(all_text):
            reasons.append("unsafe_claim")
        else:
            scores["claims_safety"] = 5

        lock_score, lock_reasons = self._product_lock_score(meaning)
        scores["product_lock_reference_safety"] = lock_score
        reasons.extend(lock_reasons)

        missing_roles = [role for role in REQUIRED_SCENE_ROLES if role not in role_to_scene]
        if not missing_roles:
            scores["scene_completeness"] = 5
        else:
            reasons.append("incomplete_scene_roles")

        return scores, reasons

    def _product_lock_score(self, meaning: models.BloggerMeaningSpec) -> tuple[float, list[str]]:
        rules = meaning.product_lock_rules_json or {}
        policy = rules.get("policy") or {}
        lock_mode = rules.get("product_lock_mode") or policy.get("product_lock_mode")
        if not lock_mode:
            return 0, ["product_lock_missing"]
        reference_count = int(policy.get("approved_reference_count") or 0)
        if lock_mode == "reference_i2v" and reference_count >= 2:
            return 5, []
        if lock_mode in {"packshot_overlay", "end_card_packshot", "no_product_generation"}:
            if reference_count < 2:
                return 3, ["low_reference_count"]
            return 5, []
        return 2, ["product_lock_missing"]

    def _gate_json(self, product_id: int, reasons: list[str]) -> dict:
        try:
            policy = ProductReferencePolicyService(self.db).check(product_id)
        except Exception as exc:  # pragma: no cover - defensive only
            return {"reference_policy_error": str(exc), "quality_reasons": reasons}
        return {
            "reference_policy_status": policy.status,
            "strict_real_generation_allowed": policy.strict_real_generation_allowed,
            "product_lock_mode": policy.product_lock_mode,
            "approved_reference_count": policy.approved_reference_count,
            "quality_reasons": reasons,
        }

    @staticmethod
    def _status(total_score: float, reasons: list[str]) -> str:
        critical_reasons = {"missing_proof_moment", "missing_cta", "unsafe_claim", "incomplete_scene_roles", "product_lock_missing"}
        if total_score >= PASS_THRESHOLD:
            if critical_reasons.intersection(reasons):
                return "needs_rewrite"
            return "passed"
        if total_score >= REWRITE_THRESHOLD:
            return "needs_rewrite"
        return "blocked"

    @staticmethod
    def _breakdown(scores: dict[str, float]) -> list[dict]:
        output = []
        for component in RUBRIC_COMPONENTS:
            score = float(scores.get(component.key, 0))
            output.append(
                {
                    "key": component.key,
                    "label": component.label,
                    "score": score,
                    "max_score": component.max_score,
                    "passed": score >= component.max_score,
                }
            )
        return output

    @staticmethod
    def _all_text(script: models.UGCAdScript, meaning: models.BloggerMeaningSpec) -> str:
        scene_lines = " ".join(str(scene.get("spoken_line") or "") for scene in (script.scene_script_json or []))
        captions = " ".join(str(scene.get("caption") or "") for scene in (script.scene_script_json or []))
        voice_lines = " ".join(str(line) for line in (script.voiceover_json or {}).get("lines", []))
        meaning_bits = " ".join(
            str(value)
            for value in [
                (meaning.buyer_context_json or {}).get("buyer_situation"),
                (meaning.buyer_context_json or {}).get("pain_or_desire"),
                (meaning.proof_moment_json or {}).get("proof_line"),
                (meaning.cta_json or {}).get("spoken_line"),
            ]
            if value
        )
        return f" {scene_lines} {captions} {voice_lines} {meaning_bits} ".lower()

    @staticmethod
    def _has_first_person(text: str) -> bool:
        normalized = f" {text.lower()} "
        return any(marker in normalized for marker in FIRST_PERSON_MARKERS)

    @staticmethod
    def _has_personal_situation(text: str) -> bool:
        normalized = text.lower()
        markers = ("after training", "between tasks", "between errands", "routine", "gym", "kitchen", "when i", "после тренировки", "в рутине")
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _has_generic_ad_voice(text: str) -> bool:
        normalized = text.lower()
        return any(phrase in normalized for phrase in GENERIC_AD_PHRASES)

    @staticmethod
    def _has_unsafe_claim(text: str) -> bool:
        normalized = text.lower()
        return any(marker in normalized for marker in UNSAFE_CLAIM_MARKERS)

    @staticmethod
    def _mentions_product_reason(text: str) -> bool:
        normalized = text.lower()
        markers = (
            "why",
            "because",
            "that is why",
            "reason",
            "fits",
            "instead",
            "format",
            "carry",
            "point of the shot",
            "exact product",
            "поэтому",
            "потому",
            "подходит",
            "выбираю",
            "беру",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _mentions_proof(text: str) -> bool:
        normalized = text.lower()
        markers = (
            "show",
            "proof",
            "texture",
            "pack",
            "reference",
            "real",
            "taste",
            "try",
            "покаж",
            "проб",
            "текстур",
            "упаков",
            "реаль",
        )
        return any(marker in normalized for marker in markers)
