from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from app import models
from app.assets.asset_kit_builder import AssetKitBuilder
from app.creative.types import CreativeSpec
from app.variants.errors import VariantDataError
from app.variants.first_frame_builder import FirstFrameBuilder
from app.variants.types import CreativeVariantOutput, FirstFrameOptionOutput


class CreativeVariantBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build_set(
        self,
        creative_spec_id: int,
        *,
        count: int = 5,
        asset_kit_id: int | None = None,
    ) -> models.CreativeVariantSet:
        spec_record = self.db.get(models.VideoCreativeSpecRecord, creative_spec_id)
        if not spec_record:
            raise VariantDataError(f"VideoCreativeSpecRecord {creative_spec_id} not found.")
        spec = CreativeSpec.model_validate(spec_record.spec_json)
        asset_kit = self._asset_kit(spec_record.product_id, asset_kit_id)
        first_frames = self._first_frames(spec_record.id, asset_kit.id if asset_kit else None)
        outputs = self._outputs(spec, asset_kit, first_frames, max(1, min(count, 12)))
        variant_set = models.CreativeVariantSet(
            creative_spec_id=spec_record.id,
            asset_kit_id=asset_kit.id if asset_kit else None,
            status="ready",
            variant_count=len(outputs),
            variants_json=[output.model_dump(mode="json") for output in outputs],
            warnings_json=asset_kit.warnings_json if asset_kit else ["No asset kit available."],
        )
        self.db.add(variant_set)
        self.db.flush()
        records = []
        for index, output in enumerate(outputs, start=1):
            first_frame_record = first_frames[(index - 1) % len(first_frames)]
            record = models.CreativeVariant(
                creative_variant_set_id=variant_set.id,
                creative_spec_id=spec_record.id,
                first_frame_option_id=first_frame_record.id,
                variant_number=index,
                status="ready",
                hook_text=output.hook_text,
                first_frame_json=output.first_frame.model_dump(mode="json"),
                scene_plan_json=output.scene_plan,
                pacing_json=output.scene_pacing,
                cta_framing=output.cta_framing,
                visual_style=output.visual_style,
                product_reveal_timing=output.product_reveal_timing,
                asset_refs_json=output.asset_refs,
                risk_flags_json=output.risk_flags,
            )
            self.db.add(record)
            records.append(record)
        self.db.commit()
        self.db.refresh(variant_set)
        return variant_set

    def _asset_kit(self, product_id: int, asset_kit_id: int | None) -> models.ProductAssetKit:
        if asset_kit_id:
            kit = self.db.get(models.ProductAssetKit, asset_kit_id)
            if not kit:
                raise VariantDataError(f"ProductAssetKit {asset_kit_id} not found.")
            return kit
        return (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        ) or AssetKitBuilder(self.db).build_for_product(product_id)

    def _first_frames(self, creative_spec_id: int, asset_kit_id: int | None) -> list[models.FirstFrameOption]:
        frames = (
            self.db.query(models.FirstFrameOption)
            .filter(models.FirstFrameOption.creative_spec_id == creative_spec_id)
            .order_by(models.FirstFrameOption.id.desc())
            .limit(3)
            .all()
        )
        if len(frames) >= 3:
            return list(reversed(frames))
        return FirstFrameBuilder(self.db).build_options(creative_spec_id, asset_kit_id=asset_kit_id)

    def _outputs(
        self,
        spec: CreativeSpec,
        asset_kit: models.ProductAssetKit,
        first_frames: list[models.FirstFrameOption],
        count: int,
    ) -> list[CreativeVariantOutput]:
        pacing_options = [
            {"name": "fast_hook", "first_scene_seconds": 2, "middle": "proof-led", "cta_seconds": 3},
            {"name": "proof_first", "first_scene_seconds": 3, "middle": "claim-ref proof", "cta_seconds": 2},
            {"name": "objection_answer", "first_scene_seconds": 3, "middle": "buyer doubt answer", "cta_seconds": 3},
            {"name": "use_case_demo", "first_scene_seconds": 4, "middle": "usage sequence", "cta_seconds": 2},
            {"name": "value_compare", "first_scene_seconds": 2, "middle": "value explanation", "cta_seconds": 3},
        ]
        ctas = [
            spec.cta,
            "Open the product card to compare details",
            "Check whether this fits your routine",
        ]
        styles = [
            spec.visual_style,
            "Clean product-first UGC with readable captions.",
            "Marketplace proof demo with stable closeups.",
        ]
        asset_refs = [asset.get("source_ref") for asset in asset_kit.assets_json if asset.get("source_ref")]
        outputs = []
        for index in range(count):
            first_frame = FirstFrameOptionOutput.model_validate(first_frames[index % len(first_frames)].option_json)
            scenes = self._scene_plan(spec, first_frame, pacing_options[index % len(pacing_options)])
            risks = list(first_frame.risk_flags)
            if not asset_refs:
                risks.append("missing_product_reference_assets")
            outputs.append(
                CreativeVariantOutput(
                    hook_text=first_frame.hook_text,
                    first_frame=first_frame,
                    scene_plan=scenes,
                    scene_pacing=pacing_options[index % len(pacing_options)],
                    cta_framing=ctas[index % len(ctas)],
                    visual_style=styles[index % len(styles)],
                    product_reveal_timing=first_frame.product_visible_by_second,
                    asset_refs=asset_refs,
                    risk_flags=list(dict.fromkeys(risks)),
                )
            )
        return outputs

    @staticmethod
    def _scene_plan(spec: CreativeSpec, first_frame: FirstFrameOptionOutput, pacing: dict) -> list[dict]:
        scenes = [scene.model_dump(mode="json") for scene in spec.scene_plan]
        if not scenes:
            return []
        scenes = deepcopy(scenes)
        scenes[0]["visual"] = first_frame.visual_concept
        scenes[0]["caption"] = first_frame.text_overlay
        scenes[0]["voiceover"] = first_frame.hook_text
        scenes[0]["product_display"] = first_frame.product_placement
        scenes[0]["camera_motion"] = first_frame.camera_motion
        scenes[0]["composition"] = first_frame.composition
        scenes[0]["duration_seconds"] = pacing["first_scene_seconds"]
        total = sum(scene["duration_seconds"] for scene in scenes)
        delta = spec.duration_seconds - total
        scenes[-1]["duration_seconds"] = max(1, scenes[-1]["duration_seconds"] + delta)
        starts_at = 0
        for scene in scenes:
            scene["starts_at"] = starts_at
            starts_at += scene["duration_seconds"]
        return scenes
