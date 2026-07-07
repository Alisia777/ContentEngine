from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.blogger_brief.errors import BloggerBriefDataError


class UGCAdScriptBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(
        self,
        blogger_meaning_spec_id: int,
        *,
        creative_variant_id: int | None = None,
        duration_seconds: int = 8,
    ) -> models.UGCAdScript:
        spec = self.db.get(models.BloggerMeaningSpec, blogger_meaning_spec_id)
        if not spec:
            raise BloggerBriefDataError(f"BloggerMeaningSpec {blogger_meaning_spec_id} not found.")
        variant = self.db.get(models.CreativeVariant, creative_variant_id) if creative_variant_id else None
        if creative_variant_id and not variant:
            raise BloggerBriefDataError(f"CreativeVariant {creative_variant_id} not found.")
        if not variant:
            variant = self._default_variant(spec)

        scenes = self._scene_script(spec, duration_seconds=duration_seconds)
        script = models.UGCAdScript(
            blogger_meaning_spec_id=spec.id,
            creative_variant_id=variant.id if variant else None,
            status="ready",
            duration_seconds=duration_seconds,
            voiceover_json={
                "language": "ru",
                "style": "first-person creator language",
                "lines": [scene["spoken_line"] for scene in scenes if scene.get("spoken_line")],
                "avoid": ["generic ad voice", "unsupported claims", "announcer tone"],
            },
            captions_json={
                "style": "minimal",
                "lines": [scene.get("caption", "") for scene in scenes],
                "generated_on_screen_text_allowed": False,
            },
            scene_script_json=scenes,
        )
        self.db.add(script)
        self.db.flush()
        if variant:
            self._apply_to_variant(variant, spec, script)
        self.db.commit()
        self.db.refresh(script)
        return script

    def _default_variant(self, spec: models.BloggerMeaningSpec) -> models.CreativeVariant | None:
        if spec.creative_spec_id:
            variant = self.db.scalar(
                select(models.CreativeVariant)
                .where(models.CreativeVariant.creative_spec_id == spec.creative_spec_id)
                .where(models.CreativeVariant.status == "selected")
                .order_by(models.CreativeVariant.id.desc())
            )
            if variant:
                return variant
        return self.db.scalar(
            select(models.CreativeVariant)
            .join(models.VideoCreativeSpecRecord, models.CreativeVariant.creative_spec_id == models.VideoCreativeSpecRecord.id)
            .where(models.VideoCreativeSpecRecord.product_id == spec.product_id)
            .where(models.CreativeVariant.status == "selected")
            .order_by(models.CreativeVariant.id.desc())
        )

    def _scene_script(self, spec: models.BloggerMeaningSpec, *, duration_seconds: int) -> list[dict]:
        intents = spec.scene_intent_json or []
        per_scene = max(1, duration_seconds // max(1, len(intents)))
        scenes = []
        starts_at = 0
        for index, intent in enumerate(intents, start=1):
            duration = per_scene if index < len(intents) else max(1, duration_seconds - starts_at)
            scenes.append(
                {
                    "scene_number": index,
                    "role": intent.get("role"),
                    "starts_at": starts_at,
                    "duration_seconds": duration,
                    "intention": intent.get("intention"),
                    "emotion": intent.get("emotion"),
                    "spoken_line": intent.get("spoken_line"),
                    "caption": intent.get("caption", ""),
                    "visual_direction": self._visual_direction(intent.get("role"), spec),
                    "proof_moment": spec.proof_moment_json,
                    "product_lock_mode": (spec.product_lock_rules_json or {}).get("product_lock_mode"),
                }
            )
            starts_at += duration
        return scenes

    @staticmethod
    def _visual_direction(role: str | None, spec: models.BloggerMeaningSpec) -> str:
        persona = (spec.creator_persona_json or {}).get("persona", "UGC creator")
        product_lock = (spec.product_lock_rules_json or {}).get("product_lock_mode", "no_product_generation")
        if role == "proof_demo":
            return f"{persona} shows product proof and use case; product lock mode: {product_lock}."
        if role == "cta":
            return f"{persona} finishes with a natural CTA and exact product identity."
        return f"{persona} speaks naturally in a real-life vertical UGC frame."

    @staticmethod
    def _apply_to_variant(
        variant: models.CreativeVariant,
        meaning_spec: models.BloggerMeaningSpec,
        script: models.UGCAdScript,
    ) -> None:
        variant.scene_plan_json = [
            {
                "scene_number": scene["scene_number"],
                "role": scene["role"],
                "starts_at": scene["starts_at"],
                "duration_seconds": scene["duration_seconds"],
                "visual": scene["visual_direction"],
                "caption": scene["caption"],
                "voiceover": scene["spoken_line"],
                "claim_refs": ["blogger_meaning_spec", "product_reference_policy"],
                "blogger_meaning_spec_id": meaning_spec.id,
                "ugc_script_id": script.id,
                "product_lock_mode": scene["product_lock_mode"],
                "proof_moment": scene["proof_moment"],
            }
            for scene in script.scene_script_json
        ]
        variant.risk_flags_json = list(
            dict.fromkeys(
                [
                    *(variant.risk_flags_json or []),
                    "blogger_meaning_spec",
                    "ugc_ad_script",
                    f"product_lock_mode:{(meaning_spec.product_lock_rules_json or {}).get('product_lock_mode')}",
                ]
            )
        )
        variant.selection_reason = "UGCAdScript attached: first-person creator story with product-safe lock mode."
