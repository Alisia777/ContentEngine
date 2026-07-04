from __future__ import annotations

from app.creative.types import CreativeSpec, CreativeSpecValidationReport


MEDICAL_TERMS = {"cure", "treat", "treatment", "medical", "heal", "леч", "лечение"}


class CreativeSpecValidator:
    def validate(self, spec: CreativeSpec, forbidden_words: list[str] | None = None, forbidden_claims: list[str] | None = None) -> CreativeSpecValidationReport:
        errors: list[str] = []
        warnings = list(spec.warnings)
        forbidden_words = [word.lower() for word in (forbidden_words or []) if word]
        forbidden_claims = [claim.lower() for claim in (forbidden_claims or []) if claim]
        text = self._all_text(spec).lower()

        if spec.format in {"short_video", "short_form_ad"} and spec.first_frame_spec.product_visible_by_second > 1.5:
            errors.append("Product must appear in the first 1.5 seconds for short-form ads.")
        if not spec.first_frame_spec.visual_hook or not spec.first_frame_spec.text_overlay:
            errors.append("First frame must include both visual hook and text hook.")
        for scene in spec.scene_plan:
            if not scene.caption:
                errors.append(f"Scene {scene.scene_number} is missing caption.")
            if not scene.role:
                errors.append(f"Scene {scene.scene_number} is missing scene role.")
            if spec.allowed_claim_refs and scene.role != "cta" and not scene.claim_refs:
                errors.append(f"Scene {scene.scene_number} uses a claim without claim_refs.")
            for ref in scene.claim_refs:
                if ref not in spec.allowed_claim_refs:
                    errors.append(f"Scene {scene.scene_number} has unsupported claim ref: {ref}")
        for word in forbidden_words:
            if word and word in text:
                errors.append(f"Forbidden word used: {word}")
        for claim in forbidden_claims:
            if claim and claim in text:
                errors.append(f"Forbidden claim used: {claim}")
        if any(term in text for term in MEDICAL_TERMS):
            allowed_text = " ".join(claim.claim.lower() for claim in spec.allowed_claims)
            if not any(term in allowed_text for term in MEDICAL_TERMS):
                errors.append("Medical or treatment claim detected without explicit allowed source.")
        if not spec.cta:
            errors.append("CTA exists check failed.")
        if sum(scene.duration_seconds for scene in spec.scene_plan) != spec.duration_seconds:
            errors.append("Creative spec duration must equal the sum of scene durations.")
        if not spec.product_display_rules:
            errors.append("Product display rules must be explicit.")
        if not spec.quality_rubric.items:
            errors.append("Quality rubric must exist.")
        return CreativeSpecValidationReport(valid=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def _all_text(spec: CreativeSpec) -> str:
        values = [
            spec.hook_text,
            spec.viewer_promise,
            spec.first_frame_spec.visual_hook,
            spec.first_frame_spec.text_overlay,
            spec.cta,
            *spec.must_include,
        ]
        for scene in spec.scene_plan:
            values.extend([scene.visual, scene.caption, scene.voiceover, scene.product_display])
        return " ".join(value for value in values if value)
