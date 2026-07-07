from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.creative.product_geometry import (
    GEOMETRY_LOCK_PROMPT_LINES,
    default_product_geometry_rules,
    default_product_scale_rules,
    default_product_visibility_rules,
)
from app.creative.types import (
    CreativeScene,
    CreativeSpec,
    FirstFrameSpec,
    HookCandidate,
    ProductGeometrySpec,
    QualityRubric,
    QualityRubricItem,
)
from app.intelligence.types import AllowedClaim
from app.one_video_acceptance.errors import OneVideoAcceptanceDataError
from app.one_video_acceptance.product_scene_policy import ProductScenePolicyService
from app.one_video_acceptance.prompt_specializer import ACCEPTANCE_CHECKLIST, BombbarPromptSpecializer
from app.one_video_acceptance.types import OneVideoRenderPlanOutput, OneVideoScene, ProductScenePolicyOutput


class BombbarOneVideoRenderPlanner:
    def __init__(self, db: Session):
        self.db = db
        self.specializer = BombbarPromptSpecializer()

    def build(
        self,
        product_id: int,
        *,
        platform: str = "Instagram Reels",
        duration_seconds: int = 15,
        provider: str = "runway",
    ) -> models.OneVideoRenderPlan:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise OneVideoAcceptanceDataError(f"Product {product_id} not found.")
        if duration_seconds != 15:
            raise OneVideoAcceptanceDataError("Bombbar one-video acceptance currently supports exactly 15 seconds.")

        self._ensure_execution_dependencies(product)
        policy = ProductScenePolicyService(self.db).evaluate(product_id, provider=provider, label_accuracy_required=True)
        scenes = self._scene_plan(product, policy)
        prompt_preview = self.specializer.build_scene_prompts(
            product=product,
            policy=policy,
            scenes=scenes,
            platform=platform,
            provider=provider,
        )
        for scene, prompt in zip(scenes, prompt_preview["scene_prompts"], strict=True):
            scene.provider_prompt_text = prompt["prompt_text"]
            scene.negative_prompt = prompt["negative_prompt"]

        intelligence = self._create_intelligence_pack(product, policy)
        script_brief = self._create_script_brief(product, intelligence, policy)
        creative_spec = self._creative_spec(product, scenes, policy, platform=platform, duration_seconds=duration_seconds)
        spec_record = self._create_creative_spec_record(product, intelligence, script_brief, creative_spec, policy, platform)
        variant_set, selected_variant = self._create_selected_variant(spec_record, scenes, policy)
        ai_brief, director_prompt = self._create_ai_brief_and_prompt(product, spec_record, scenes, policy, prompt_preview, platform)

        plan = models.OneVideoRenderPlan(
            product_id=product.id,
            sku=product.sku,
            platform=platform,
            aspect_ratio="9:16",
            duration_seconds=duration_seconds,
            provider=provider,
            status="plan_ready" if not policy.blockers else "plan_ready_with_reference_blockers",
            creative_spec_id=spec_record.id,
            creative_variant_id=selected_variant.id,
            ai_production_brief_id=ai_brief.id,
            director_prompt_pack_id=director_prompt.id,
            product_scene_policy_json=policy.model_dump(mode="json"),
            scene_plan_json=[scene.model_dump(mode="json") for scene in scenes],
            prompt_preview_json=prompt_preview,
            negative_prompt=prompt_preview["negative_prompt"],
            acceptance_checklist_json=ACCEPTANCE_CHECKLIST,
            blockers_json=policy.blockers,
            warnings_json=policy.warnings,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get(self, plan_id: int) -> models.OneVideoRenderPlan:
        plan = self.db.get(models.OneVideoRenderPlan, plan_id)
        if not plan:
            raise OneVideoAcceptanceDataError(f"OneVideoRenderPlan {plan_id} not found.")
        return plan

    def latest(self) -> models.OneVideoRenderPlan | None:
        return self.db.scalar(select(models.OneVideoRenderPlan).order_by(models.OneVideoRenderPlan.id.desc()))

    def list_recent(self, limit: int = 20) -> list[models.OneVideoRenderPlan]:
        return list(self.db.scalars(select(models.OneVideoRenderPlan).order_by(models.OneVideoRenderPlan.id.desc()).limit(limit)))

    @staticmethod
    def as_output(plan: models.OneVideoRenderPlan) -> OneVideoRenderPlanOutput:
        return OneVideoRenderPlanOutput(
            id=plan.id,
            product_id=plan.product_id,
            sku=plan.sku,
            platform=plan.platform,
            aspect_ratio=plan.aspect_ratio,
            duration_seconds=plan.duration_seconds,
            provider=plan.provider,
            status=plan.status,
            creative_spec_id=plan.creative_spec_id,
            creative_variant_id=plan.creative_variant_id,
            ai_production_brief_id=plan.ai_production_brief_id,
            director_prompt_pack_id=plan.director_prompt_pack_id,
            prompt_pack_id=plan.prompt_pack_id,
            video_generation_variant_id=plan.video_generation_variant_id,
            product_scene_policy=ProductScenePolicyOutput.model_validate(plan.product_scene_policy_json or {}),
            scene_plan=[OneVideoScene.model_validate(scene) for scene in plan.scene_plan_json or []],
            prompt_preview=plan.prompt_preview_json or {},
            negative_prompt=plan.negative_prompt,
            acceptance_checklist=plan.acceptance_checklist_json or [],
            blockers=plan.blockers_json or [],
            warnings=plan.warnings_json or [],
        )

    def _scene_plan(self, product: models.Product, policy: ProductScenePolicyOutput) -> list[OneVideoScene]:
        common_safety = [
            "Russian voiceover only, natural speech, no robotic sales tone",
            "sporty woman 25-30 presents the product, no child-looking creator",
            "closed wrapper must stay rigid and label-accurate",
            "never make the creator bite packaging or wrapper",
            "do not show unsafe bite or macro texture when policy blocks edible scenes",
            "keep captions short and inside safe 9:16 margins",
        ]
        if policy.edible_kit_ready:
            proof_visual = (
                "The creator shows an already unwrapped bite-sized piece only if it matches approved edible references, "
                "then gives a small natural reaction while the locked wrapper stays visible nearby."
            )
            proof_visibility = "Approved edible reference may appear briefly; wrapper remains visible as identity anchor."
            proof_avoid = ["generic bar texture", "wrapper bite", "invented filling"]
        else:
            proof_visual = (
                "Show approved cutaway/reference insert as a controlled overlay, then cut back to creator reaction with coffee; "
                "no AI-generated bite, no chew close-up, no invented texture."
            )
            proof_visibility = "No generated unwrapped bar. Use approved cutaway insert, closed wrapper, packshot overlay."
            proof_avoid = ["bite scene", "chewing close-up", "AI-generated unwrapped macro", "muesli-like texture"]

        scenes = [
            OneVideoScene(
                scene_number=1,
                role="hook",
                starts_at=0,
                duration_seconds=2,
                spoken_line="Если тоже берёшь что-то сладкое на бегу - покажу одну находку.",
                caption="Сладкое на бегу?",
                visual="Creator looks into camera after a workout or walk, holding the closed Bombbar wrapper naturally at chest level.",
                product_visibility="Closed wrapper in hand, readable enough for identity, no close-up deformation.",
                camera_motion="handheld phone camera, subtle natural movement",
                safety_constraints=common_safety,
                must_avoid=["eating wrapper", "floating package", "wrapper deformation"],
            ),
            OneVideoScene(
                scene_number=2,
                role="personal_context",
                starts_at=2,
                duration_seconds=3,
                spoken_line="У меня часто бывают дни, когда нормально поесть просто некогда.",
                caption="Когда нет времени поесть",
                visual="Creator puts the closed wrapper near a coffee cup or gym bag, talking like a real buyer.",
                product_visibility="Closed wrapper or packshot overlay only; no invented food texture.",
                camera_motion="smooth handheld pan from creator to product and back",
                safety_constraints=common_safety,
                must_avoid=["hard jump cut", "fake ad studio pose"],
            ),
            OneVideoScene(
                scene_number=3,
                role="product_reason",
                starts_at=5,
                duration_seconds=3,
                spoken_line="Поэтому такой батончик удобно взять с собой - формат десертный, но на ходу.",
                caption="Десертный формат с собой",
                visual="Creator presents the closed wrapper, points to packshot overlay instead of relying on generated label text.",
                product_visibility="Wrapper reveal plus packshot overlay/end-card lock for label accuracy.",
                camera_motion="short slow push-in, then stop before label distortion",
                safety_constraints=common_safety + GEOMETRY_LOCK_PROMPT_LINES,
                must_avoid=["label redesign", "fake wrapper text", "changed logo"],
            ),
            OneVideoScene(
                scene_number=4,
                role="proof_use_case",
                starts_at=8,
                duration_seconds=4,
                spoken_line="Мне нравится, что это выглядит как десерт, а не просто сухой перекус.",
                caption="Похоже на десерт",
                visual=proof_visual,
                product_visibility=proof_visibility,
                camera_motion="soft reaction cut with one continuous movement, no abrupt montage",
                safety_constraints=common_safety,
                must_avoid=proof_avoid,
            ),
            OneVideoScene(
                scene_number=5,
                role="cta_end_card",
                starts_at=12,
                duration_seconds=3,
                spoken_line="Сохрани, если тоже ищешь быстрый перекус к кофе или с собой.",
                caption="Сохрани к кофе или в дорогу",
                visual="End card with locked packshot/reference image, product name, short CTA, and no auto-generated packaging.",
                product_visibility="Packshot overlay/end card required. Product identity is locked to approved reference.",
                camera_motion="steady end card, no label animation",
                safety_constraints=common_safety + ["end card required"],
                must_avoid=["new packaging design", "medical claim", "weight-loss promise"],
            ),
        ]
        return scenes

    def _creative_spec(
        self,
        product: models.Product,
        scenes: list[OneVideoScene],
        policy: ProductScenePolicyOutput,
        *,
        platform: str,
        duration_seconds: int,
    ) -> CreativeSpec:
        selected_hook = HookCandidate(
            hook_type="real_life_snack_find",
            hook_text=scenes[0].spoken_line,
            viewer_promise="Быстрый перекус к кофе или с собой без визуального риска для упаковки.",
            rationale="The hook is a natural first-person UGC situation and avoids unsafe product claims.",
            source_flags=["operator_bombbar_acceptance_brief"],
        )
        creative_scenes = [
            CreativeScene(
                scene_number=scene.scene_number,
                role=scene.role,
                starts_at=scene.starts_at,
                duration_seconds=scene.duration_seconds,
                visual=scene.visual,
                caption=scene.caption,
                voiceover=scene.spoken_line,
                claim_refs=["operator_bombbar_acceptance_brief"],
                product_display=scene.product_visibility,
                camera_motion=scene.camera_motion,
                composition="vertical phone UGC, creator and product visible without label distortion",
                lighting="natural indoor daylight",
                emotion="calm, useful, real buyer recommendation",
                cta=scene.spoken_line if scene.role == "cta_end_card" else None,
            )
            for scene in scenes
        ]
        return CreativeSpec(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            platform=platform,
            format="short_video",
            aspect_ratio="9:16",
            duration_seconds=duration_seconds,
            creative_objective="Create one product-safe UGC paid smoke candidate for Bombbar.",
            creative_angle="sporty_real_life_snack_find",
            hook_candidates=[selected_hook],
            selected_hook=selected_hook,
            hook_type=selected_hook.hook_type,
            hook_text=selected_hook.hook_text,
            viewer_promise=selected_hook.viewer_promise,
            first_frame_spec=FirstFrameSpec(
                visual_hook="Sporty woman holds closed Bombbar wrapper and speaks to camera.",
                text_overlay="Сладкое на бегу?",
                product_visible_by_second=1.0,
                product_display="Closed wrapper only; label locked by packshot overlay/end card.",
                composition="Creator upper body plus product, 9:16 safe margins.",
                viewer_promise=selected_hook.viewer_promise,
            ),
            scene_plan=creative_scenes,
            captions=[scene.caption for scene in scenes],
            voiceover=[scene.spoken_line for scene in scenes],
            visual_style="realistic Wibes/Reels UGC, handheld phone, natural Russian creator presentation",
            product_display_rules=[
                "Preserve exact Bombbar wrapper color, logo, label layout and proportions.",
                "Creator must never bite the packaged wrapper.",
                "If edible refs are not ready, use approved cutaway insert and reaction instead of generated bite.",
                "Use packshot overlay and end card when label accuracy matters.",
            ],
            product_geometry_spec=ProductGeometrySpec(
                product_id=product.id,
                sku=product.sku,
                primary_reference_asset_id=policy.reference_readiness.get("primary_reference_asset_id"),
                human_geometry_notes="Snack wrapper must not bend, melt, resize, or change label text in hand.",
            ),
            product_geometry_rules=default_product_geometry_rules(),
            product_scale_rules=default_product_scale_rules(),
            product_visibility_rules=default_product_visibility_rules(),
            must_include=[
                "sporty Russian-speaking woman 25-30",
                "closed wrapper in hand",
                "personal context",
                "proof/use-case moment",
                "CTA/end card",
            ],
            must_avoid=[
                "generic muesli or granola bar",
                "wrapper or logo redesign",
                "eating packaged wrapper",
                "AI-generated edible macro without references",
                "weight-loss or medical claims",
            ],
            allowed_claims=[
                AllowedClaim(claim="convenient snack format", source_type="operator_brief", source_key="bombbar_one_video"),
                AllowedClaim(claim="dessert-style format", source_type="operator_brief", source_key="bombbar_one_video"),
            ],
            allowed_claim_refs=["operator_bombbar_acceptance_brief"],
            reference_images=policy.reference_readiness.get("provider_reference_bundle", {}).get("reference_images", []),
            source_map={"operator_bombbar_acceptance_brief": "One-video acceptance prompt from operator"},
            quality_rubric=QualityRubric(
                items=[
                    QualityRubricItem(key="product_identity_locked", label="Product identity stays locked"),
                    QualityRubricItem(key="no_muesli_drift", label="No muesli/granola drift"),
                    QualityRubricItem(key="proof_moment", label="Proof/use-case moment is present"),
                    QualityRubricItem(key="cta_end_card", label="CTA/end card is present"),
                ],
                notes=["Visual identity still requires human review after render."],
            ),
            warnings=policy.warnings,
            cta=scenes[-1].spoken_line,
        )

    def _create_intelligence_pack(self, product: models.Product, policy: ProductScenePolicyOutput) -> models.CreativeIntelligencePackRecord:
        record = models.CreativeIntelligencePackRecord(
            product_id=product.id,
            sku=product.sku,
            status="one_video_plan_ready",
            pack_json={
                "source": "one_video_acceptance",
                "product_scene_policy": policy.model_dump(mode="json"),
                "objective": "controlled Bombbar UGC video render",
            },
            source_summary_json={"operator_brief": "Bombbar product-safe UGC acceptance"},
            warnings_json=policy.warnings,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _create_script_brief(
        self,
        product: models.Product,
        intelligence: models.CreativeIntelligencePackRecord,
        policy: ProductScenePolicyOutput,
    ) -> models.ScriptBrief:
        brief = models.ScriptBrief(
            product_id=product.id,
            intelligence_pack_id=intelligence.id,
            status="one_video_plan_ready",
            objective="One controlled product-safe UGC paid smoke candidate.",
            creative_angle="sporty_real_life_snack_find",
            target_audience="Russian-speaking marketplace shopper looking for a quick dessert-style snack.",
            brief_json={"product_scene_policy": policy.model_dump(mode="json")},
            allowed_claims_json=["convenient snack format", "dessert-style format"],
            missing_data_json=policy.next_actions,
            safety_warnings_json=policy.warnings,
        )
        self.db.add(brief)
        self.db.flush()
        return brief

    def _create_creative_spec_record(
        self,
        product: models.Product,
        intelligence: models.CreativeIntelligencePackRecord,
        script_brief: models.ScriptBrief,
        spec: CreativeSpec,
        policy: ProductScenePolicyOutput,
        platform: str,
    ) -> models.VideoCreativeSpecRecord:
        record = models.VideoCreativeSpecRecord(
            product_id=product.id,
            intelligence_pack_id=intelligence.id,
            script_brief_id=script_brief.id,
            platform=platform,
            format="short_video",
            aspect_ratio="9:16",
            duration_seconds=spec.duration_seconds,
            status="ready",
            spec_json={**spec.model_dump(mode="json"), "product_identity_strict": True},
            hook_candidates_json=[hook.model_dump(mode="json") for hook in spec.hook_candidates],
            validation_report_json={"valid": True, "source": "one_video_acceptance"},
            warnings_json=policy.warnings,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _create_selected_variant(
        self,
        spec_record: models.VideoCreativeSpecRecord,
        scenes: list[OneVideoScene],
        policy: ProductScenePolicyOutput,
    ) -> tuple[models.CreativeVariantSet, models.CreativeVariant]:
        variant_set = models.CreativeVariantSet(
            creative_spec_id=spec_record.id,
            asset_kit_id=self._latest_asset_kit_id(spec_record.product_id),
            status="selected",
            variant_count=1,
            variants_json=[],
            score_summary_json={"selected_for": "one_video_acceptance"},
            warnings_json=policy.warnings,
        )
        self.db.add(variant_set)
        self.db.flush()
        scene_json = [
            {
                **scene.model_dump(mode="json"),
                "role": scene.role,
                "visual": scene.visual,
                "voiceover": scene.spoken_line,
                "claim_refs": ["operator_bombbar_acceptance_brief"],
                "provider_prompt_text": scene.provider_prompt_text,
                "negative_prompt": scene.negative_prompt,
                "safety_constraints": scene.safety_constraints,
                "scene_policy_allowed": scene.role not in {"proof_use_case"} or policy.edible_kit_ready or "approved_cutaway_insert" in policy.allowed_scene_types,
            }
            for scene in scenes
        ]
        variant = models.CreativeVariant(
            creative_variant_set_id=variant_set.id,
            creative_spec_id=spec_record.id,
            variant_number=1,
            status="selected",
            hook_text=scenes[0].spoken_line,
            first_frame_json={
                "visual_concept": scenes[0].visual,
                "text_overlay": scenes[0].caption,
                "product_placement": scenes[0].product_visibility,
                "product_visible_by_second": 1.0,
            },
            scene_plan_json=scene_json,
            pacing_json={"duration_seconds": 15, "style": "smooth_ugc_no_hard_jumps"},
            cta_framing=scenes[-1].spoken_line,
            visual_style="realistic Russian Wibes/Reels UGC, sporty woman 25-30, phone camera",
            product_reveal_timing=1.0,
            asset_refs_json=policy.reference_readiness.get("provider_reference_bundle", {}).get("reference_images", []),
            score_json={"total_score": 0.92, "source": "one_video_acceptance"},
            risk_flags_json=policy.blocked_scene_types,
            selection_reason="Controlled product-safe one-video acceptance plan.",
        )
        self.db.add(variant)
        self.db.flush()
        variant_set.selected_variant_id = variant.id
        variant_set.variants_json = [variant.scene_plan_json]
        variant_set.selection_reason = variant.selection_reason
        self.db.flush()
        return variant_set, variant

    def _create_ai_brief_and_prompt(
        self,
        product: models.Product,
        spec_record: models.VideoCreativeSpecRecord,
        scenes: list[OneVideoScene],
        policy: ProductScenePolicyOutput,
        prompt_preview: dict[str, Any],
        platform: str,
    ) -> tuple[models.AIProductionBrief, models.DirectorPromptPack]:
        brief_json = {
            "product_scene_policy": policy.model_dump(mode="json"),
            "scene_plan": [scene.model_dump(mode="json") for scene in scenes],
            "prompt_preview": prompt_preview,
        }
        brief = models.AIProductionBrief(
            product_id=product.id,
            sku=product.sku,
            status="ready_for_prompt_only",
            platform=platform,
            format="short_video",
            one_sentence_thesis="Sporty Russian creator presents Bombbar as a quick dessert-style snack without unsafe product generation.",
            viewer_takeaway="This is a convenient snack to keep with coffee or on the go.",
            buyer_situation="Busy day, workout, walk, or coffee break when there is no time for a normal meal.",
            main_objection="AI may deform wrapper or invent a generic muesli texture.",
            reason_to_believe="Product is shown through approved wrapper references, controlled cutaway insert, packshot overlay and end card.",
            proof_moment="Approved cutaway insert plus creator reaction, or bite only if edible kit is ready.",
            cta=scenes[-1].spoken_line,
            must_show_json=["creator talking-head", "closed wrapper", "proof/use-case", "CTA/end card"],
            must_say_json=[scene.spoken_line for scene in scenes],
            must_avoid_json=prompt_preview.get("scene_prompts", [{}])[0].get("must_avoid", []),
            product_identity_rules_json=policy.model_dump(mode="json"),
            product_lock_mode="packshot_overlay" if policy.packshot_overlay_required else "reference_i2v",
            reference_requirements_json=policy.reference_readiness,
            scene_count=len(scenes),
            duration_seconds=15,
            failure_conditions_json=ACCEPTANCE_CHECKLIST[:3],
            brief_json=brief_json,
            brief_markdown=self._brief_markdown(product, scenes, policy),
            warnings_json=policy.warnings,
        )
        self.db.add(brief)
        self.db.flush()
        for scene in scenes:
            self.db.add(
                models.SceneBlueprint(
                    ai_production_brief_id=brief.id,
                    scene_order=scene.scene_number,
                    scene_role=scene.role,
                    start_second=scene.starts_at,
                    end_second=scene.starts_at + scene.duration_seconds,
                    viewer_goal=scene.caption,
                    visual_action=scene.visual,
                    spoken_line=scene.spoken_line,
                    onscreen_text=scene.caption,
                    caption_text=scene.caption,
                    product_visibility=scene.product_visibility,
                    camera_framing=scene.camera_motion,
                    broll_notes="Use controlled references and inserts only.",
                    transition_notes="Smooth phone-style movement; avoid hard jump cuts.",
                    must_show_json=scene.safety_constraints,
                    must_avoid_json=scene.must_avoid,
                )
            )
        director_prompt = models.DirectorPromptPack(
            ai_production_brief_id=brief.id,
            status="ready",
            system_instruction="Create a product-safe Russian UGC video prompt. Do not bypass scene policy.",
            provider_prompt_json=prompt_preview,
            negative_prompt=prompt_preview["negative_prompt"],
            asset_instructions_json={
                "approved_wrapper_asset_ids": policy.approved_wrapper_asset_ids,
                "approved_edible_asset_ids": policy.approved_edible_asset_ids,
                "product_scene_policy": policy.model_dump(mode="json"),
            },
            overlay_instructions_json={"packshot_overlay_required": policy.packshot_overlay_required},
            end_card_instructions_json={"end_card_required": policy.end_card_required, "cta": scenes[-1].spoken_line},
            quality_checklist_json=ACCEPTANCE_CHECKLIST,
        )
        self.db.add(director_prompt)
        self.db.flush()
        return brief, director_prompt

    def _ensure_execution_dependencies(self, product: models.Product) -> None:
        guide = self.db.scalar(select(models.BrandGuide).where(models.BrandGuide.brand == product.brand).order_by(models.BrandGuide.id))
        if not guide:
            self.db.add(
                models.BrandGuide(
                    brand=product.brand,
                    tone_of_voice="Natural, useful, Russian UGC, no exaggerated promises.",
                    visual_style="Realistic vertical phone video with locked product references.",
                    forbidden_words_json=["cure", "weight loss", "medical treatment"],
                    forbidden_claims_json=["medical result", "guaranteed body change"],
                    required_disclaimers_json=[],
                    allowed_cta_json=["Сохрани", "Посмотри карточку товара"],
                )
            )
        template = self.db.scalar(select(models.CreativeTemplate).order_by(models.CreativeTemplate.id))
        if not template:
            self.db.add(
                models.CreativeTemplate(
                    name="one_video_product_safe_ugc",
                    description="One controlled product-safe UGC acceptance render.",
                    format="short_video",
                    duration_seconds=15,
                    aspect_ratio="9:16",
                    structure_json=["hook", "personal_context", "product_reason", "proof_use_case", "cta_end_card"],
                    hook_formula="First-person real-life snack situation.",
                    cta="Сохрани к кофе или с собой",
                    platform_fit_json=["Instagram Reels", "Wibes", "TikTok"],
                )
            )
        self.db.commit()

    def _latest_asset_kit_id(self, product_id: int) -> int | None:
        kit = (
            self.db.query(models.ProductAssetKit)
            .filter(models.ProductAssetKit.product_id == product_id)
            .order_by(models.ProductAssetKit.id.desc())
            .first()
        )
        return kit.id if kit else None

    @staticmethod
    def _brief_markdown(product: models.Product, scenes: list[OneVideoScene], policy: ProductScenePolicyOutput) -> str:
        lines = [
            f"# One Video Acceptance: {product.title}",
            "",
            "Goal: one product-safe Bombbar UGC render candidate.",
            f"Wrapper refs: {policy.wrapper_reference_count}; edible refs: {policy.edible_reference_count}.",
            f"Bite scene allowed: {policy.bite_scene_allowed}.",
            "",
            "## Scenes",
        ]
        lines.extend(f"- {scene.starts_at}-{scene.starts_at + scene.duration_seconds}s {scene.role}: {scene.spoken_line}" for scene in scenes)
        return "\n".join(lines)
