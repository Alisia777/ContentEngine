from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.errors import BloggerBriefDataError
from app.blogger_brief.types import PACKAGING_DRIFT_NEGATIVE_TERMS
from app.video_generator.generator import VideoGenerator


class PromptEnricher:
    def __init__(self, db: Session):
        self.db = db

    def build_prompt_pack_from_script(
        self,
        ugc_script_id: int,
        *,
        provider: str = "runway",
        build_prompts_only: bool = True,
    ) -> models.VideoGenerationVariant:
        script = self.db.get(models.UGCAdScript, ugc_script_id)
        if not script:
            raise BloggerBriefDataError(f"UGCAdScript {ugc_script_id} not found.")
        if not script.creative_variant_id:
            raise BloggerBriefDataError("UGCAdScript must be linked to a CreativeVariant before prompt pack generation.")
        meaning_spec = script.blogger_meaning_spec
        if not meaning_spec:
            raise BloggerBriefDataError("UGCAdScript is missing BloggerMeaningSpec.")
        variant = self.db.get(models.CreativeVariant, script.creative_variant_id)
        if not variant:
            raise BloggerBriefDataError(f"CreativeVariant {script.creative_variant_id} not found.")

        variant.scene_plan_json = self.enriched_scenes(script, meaning_spec)
        variant.risk_flags_json = list(dict.fromkeys([*(variant.risk_flags_json or []), "prompt_enriched_from_ugc_script"]))
        self.db.commit()

        generation_variant = VideoGenerator(self.db).build_prompt_pack_from_variant(variant.id, provider=provider)
        prompt_pack = generation_variant.prompt_pack
        metadata = {
            "blogger_meaning_spec_id": meaning_spec.id,
            "ugc_script_id": script.id,
            "product_lock_mode": (meaning_spec.product_lock_rules_json or {}).get("product_lock_mode"),
            "product_reference_policy": (meaning_spec.product_lock_rules_json or {}).get("policy", {}),
            "build_prompts_only": build_prompts_only,
        }
        generation_variant.prompt_pack_json = {**(generation_variant.prompt_pack_json or {}), **metadata}
        generation_variant.provider_payload_json = {**(generation_variant.provider_payload_json or {}), **metadata}
        if prompt_pack:
            prompt_pack.prompt_pack_json = {**(prompt_pack.prompt_pack_json or {}), **metadata}
            prompt_pack.provider_payload_json = {**(prompt_pack.provider_payload_json or {}), **metadata}
        self.db.commit()
        self.db.refresh(generation_variant)
        return generation_variant

    def enriched_scenes(
        self,
        script: models.UGCAdScript,
        meaning_spec: models.BloggerMeaningSpec,
    ) -> list[dict]:
        persona = meaning_spec.creator_persona_json or {}
        buyer = meaning_spec.buyer_context_json or {}
        proof = meaning_spec.proof_moment_json or {}
        lock_rules = meaning_spec.product_lock_rules_json or {}
        policy = lock_rules.get("policy") or {}
        lock_mode = lock_rules.get("product_lock_mode") or policy.get("product_lock_mode") or "no_product_generation"
        reference_count = policy.get("approved_reference_count", 0)
        do_not_generate_packaging = lock_mode in {"packshot_overlay", "end_card_packshot"}
        return [
            {
                **scene,
                "visual": scene.get("visual_direction"),
                "voiceover": scene.get("spoken_line"),
                "provider_prompt_text": self._provider_prompt(
                    scene,
                    persona=persona,
                    buyer=buyer,
                    proof=proof,
                    lock_mode=lock_mode,
                    reference_count=reference_count,
                    do_not_generate_packaging=do_not_generate_packaging,
                ),
                "negative_prompt": self.packaging_negative_prompt(),
                "safety_constraints": self._safety_constraints(lock_mode, do_not_generate_packaging),
                "product_reference_count": reference_count,
                "product_lock_mode": lock_mode,
                "blogger_meaning_spec_id": meaning_spec.id,
                "ugc_script_id": script.id,
            }
            for scene in (script.scene_script_json or [])
        ]

    @staticmethod
    def packaging_negative_prompt() -> str:
        return ", ".join(PACKAGING_DRIFT_NEGATIVE_TERMS)

    @staticmethod
    def _provider_prompt(
        scene: dict,
        *,
        persona: dict,
        buyer: dict,
        proof: dict,
        lock_mode: str,
        reference_count: int,
        do_not_generate_packaging: bool,
    ) -> str:
        packaging_instruction = (
            "Do not generate or redraw packaging; use the exact packshot as overlay/end card."
            if do_not_generate_packaging
            else "Use approved product references and preserve package geometry, logo, label, colors, and scale."
        )
        text = (
            f"Vertical realistic UGC ad. Creator persona: {persona.get('persona')} age {persona.get('age_range')}; "
            f"buyer situation: {buyer.get('buyer_situation')}; scene role: {scene.get('role')}; "
            f"emotion/intention: {scene.get('emotion')} / {scene.get('intention')}; "
            f"spoken line: {scene.get('spoken_line')}; caption: {scene.get('caption')}; "
            f"proof moment: {proof.get('proof_line')}; product lock mode: {lock_mode}; "
            f"product reference count: {reference_count}. {packaging_instruction} "
            "Keep product proportions realistic relative to hand and frame. Natural first-person creator delivery."
        )
        return text[:1000].rstrip()

    @staticmethod
    def _safety_constraints(lock_mode: str, do_not_generate_packaging: bool) -> list[str]:
        constraints = [
            "use first-person creator language",
            "preserve product identity and geometry",
            "keep provider-generated output needs_human_review",
            "do not claim visual identity verification",
        ]
        if do_not_generate_packaging:
            constraints.append("do not generate packaging; use exact packshot overlay or end card")
        else:
            constraints.append("use approved reference images for product identity")
        constraints.append(f"product_lock_mode:{lock_mode}")
        return constraints
