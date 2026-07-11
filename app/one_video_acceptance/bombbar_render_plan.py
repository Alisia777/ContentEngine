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
from app.one_video_acceptance.mvp_scorecard import MVPScorecardBuilder
from app.one_video_acceptance.product_scene_policy import ProductScenePolicyService
from app.one_video_acceptance.prompt_specializer import ProductUsePromptSpecializer
from app.one_video_acceptance.types import OneVideoRenderPlanOutput, OneVideoScene, ProductScenePolicyOutput


class ProductUseVideoRenderPlanner:
    def __init__(self, db: Session):
        self.db = db
        self.specializer = ProductUsePromptSpecializer()

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
            raise OneVideoAcceptanceDataError("One-video acceptance currently supports exactly 15 seconds.")

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
        scorecard = MVPScorecardBuilder().build_for_plan(policy, scenes)
        prompt_preview["mvp_scorecard"] = scorecard.model_dump(mode="json")
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
            acceptance_checklist_json=prompt_preview["quality_checklist"],
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
            mvp_scorecard=plan.prompt_preview_json.get("mvp_scorecard") if plan.prompt_preview_json else None,
            negative_prompt=plan.negative_prompt,
            acceptance_checklist=plan.acceptance_checklist_json or [],
            blockers=plan.blockers_json or [],
            warnings=plan.warnings_json or [],
        )

    def _scene_plan(self, product: models.Product, policy: ProductScenePolicyOutput) -> list[OneVideoScene]:
        if policy.product_profile != "food_snack":
            return self._generic_scene_plan(product, policy)
        common_safety = [
            "Russian voiceover only, natural speech, no robotic sales tone",
            "sporty woman 25-30 presents the product, no child-looking creator",
            "closed wrapper must stay rigid and label-accurate",
            "never make the creator bite packaging or wrapper",
            "do not show unsafe bite or macro texture when policy blocks edible scenes",
            "keep captions short and inside safe 9:16 margins",
        ]
        if policy.edible_kit_ready and policy.provider_generated_product_allowed:
            proof_visual = (
                "The creator shows an already unwrapped bite-sized piece only if it matches approved edible references, "
                "then gives a small natural reaction while the locked wrapper stays visible nearby."
            )
            proof_visibility = "Approved edible reference may appear briefly; wrapper remains visible as identity anchor."
            proof_avoid = ["generic bar texture", "wrapper bite", "invented filling"]
        elif policy.edible_kit_ready:
            proof_visual = (
                "Use the exact approved bite/use video or edible cutaway as a controlled insert, then return to the creator reaction; "
                "the provider must not redraw the wrapper, filling or bite texture."
            )
            proof_visibility = "Approved edible/use insert plus exact packshot overlay; no provider-generated SKU identity."
            proof_avoid = ["provider-generated wrapper", "provider-generated filling", "variant substitution"]
        elif policy.cutaway_proof_allowed:
            proof_visual = (
                "Show approved cutaway/reference insert as a controlled overlay, then cut back to creator reaction with coffee; "
                "no AI-generated bite, no chew close-up, no invented texture."
            )
            proof_visibility = "No generated unwrapped bar. Use approved cutaway insert, closed wrapper, packshot overlay."
            proof_avoid = ["bite scene", "chewing close-up", "AI-generated unwrapped macro", "muesli-like texture"]
        else:
            proof_visual = (
                "Keep the creator on camera in a real snack context and use only the exact approved front packshot as a static overlay; "
                "do not generate wrapper handling, an unwrapped product, a cutaway, a bite, or food texture."
            )
            proof_visibility = "Exact packshot overlay only. No provider-generated packaging or edible product."
            proof_avoid = ["generated wrapper in hand", "unwrapped product", "cutaway", "bite scene", "food macro", "invented filling"]

        generated_wrapper_allowed = policy.wrapper_scene_allowed and policy.provider_generated_packaging_allowed
        hook_visual = (
            "Creator looks into camera after a workout or walk, holding the closed product wrapper naturally at chest level."
            if generated_wrapper_allowed
            else "Creator looks into camera after a workout or walk; the product appears only as an exact static packshot overlay."
        )
        context_visual = (
            "Creator puts the closed wrapper near a coffee cup or gym bag, talking like a real buyer."
            if generated_wrapper_allowed
            else "Creator shows her coffee or gym-bag context while the exact product packshot remains a static overlay."
        )
        reason_visual = (
            "Creator presents the closed wrapper, with a packshot overlay locking all label details."
            if generated_wrapper_allowed
            else "Creator explains why the format fits her day; use only the exact approved packshot overlay for product identity."
        )

        scenes = [
            OneVideoScene(
                scene_number=1,
                role="hook",
                starts_at=0,
                duration_seconds=2,
                spoken_line="Если тоже берёшь что-то сладкое на бегу - покажу одну находку.",
                caption="Сладкое на бегу?",
                visual=hook_visual,
                product_visibility="Reference-safe closed wrapper plus overlay." if generated_wrapper_allowed else "Static approved packshot overlay only.",
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
                visual=context_visual,
                product_visibility="Reference-safe wrapper or packshot overlay only; no invented food texture.",
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
                visual=reason_visual,
                product_visibility="Reference-safe identity reveal plus packshot overlay/end-card lock for label accuracy.",
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

    def _generic_scene_plan(self, product: models.Product, policy: ProductScenePolicyOutput) -> list[OneVideoScene]:
        attributes = product.attributes_json or {}
        creator = str(attributes.get("creator_persona") or "русскоязычная блогерка 25-35 лет, похожая на реального покупателя")
        use_context = str(attributes.get("use_context") or attributes.get("application_context") or "обычная повседневная ситуация")
        safe_benefit = str((product.benefits_json or ["понятно вписывается в повседневное использование"])[0])
        interaction_copy = {
            "apply": {
                "action": "applies the product to the approved area with the reference-matched amount and motion",
                "spoken": "Покажу, как наношу средство в обычном уходе, без рекламных чудес и лишних обещаний.",
                "caption": "Как использую в уходе",
                "avoid": ["wrong application area", "invented amount", "instant skin transformation"],
            },
            "try_on": {
                "action": "shows the exact item on body, its real fit, details and reference-matched movement",
                "spoken": "Покажу, как вещь сидит и выглядит в движении, без подмены цвета или фасона.",
                "caption": "Посадка и детали в жизни",
                "avoid": ["different garment cut", "changed fabric", "impossible fit"],
            },
            "demonstrate": {
                "action": "demonstrates the approved household function and handling sequence in a real home context",
                "spoken": "Покажу, как использую товар в быту и что именно он делает в реальной ситуации.",
                "caption": "Использование в быту",
                "avoid": ["invented function", "unsafe handling", "impossible result"],
            },
            "use_case": {
                "action": "uses the exact product in its approved real-world context and sequence",
                "spoken": "Покажу реальное применение без рекламных чудес и лишних обещаний.",
                "caption": "Вот как использую",
                "avoid": ["invented application", "impossible result", "wrong product variant"],
            },
        }[policy.interaction_mode]
        application_visual = (
            f"The creator {interaction_copy['action']} for {product.title} in {use_context}, following approved references exactly."
            if policy.interaction_scene_allowed and policy.provider_generated_product_allowed
            else (
                f"Use the exact approved {policy.interaction_mode} use-video/reference insert and return to the creator reaction; "
                "the provider must not redraw the SKU or invent handling, application or function."
                if policy.interaction_scene_allowed
                else (
                    "Use an approved use-case insert and return to the creator reaction; do not invent handling, application or function."
                    if policy.use_case_scene_allowed
                    else "Keep the creator in context and show only the approved static packshot overlay; no generated product interaction."
                )
            )
        )
        product_visibility = (
            f"Approved {policy.interaction_mode} interaction insert is allowed; generated identity remains blocked."
            if policy.interaction_scene_allowed and not policy.provider_generated_product_allowed
            else (
                f"Reference-guided {policy.interaction_mode} interaction is allowed; identity remains locked."
                if policy.interaction_scene_allowed
                else "Static approved packshot overlay and approved use-case inserts only."
            )
        )
        common_safety = [
            "natural Russian first-person blogger delivery, not a studio announcer",
            f"creator profile: {creator}",
            "preserve exact SKU, label, geometry, color and scale from approved identity references",
            f"show only the approved {policy.interaction_mode} interaction supported by exact references",
            "do not invent product functions, results, claims, packaging text or usage method",
            "keep captions short and inside safe 9:16 margins",
        ]
        return [
            OneVideoScene(
                scene_number=1,
                role="hook",
                starts_at=0,
                duration_seconds=2,
                spoken_line="Покажу вещь, которая действительно вписалась в мой обычный день.",
                caption="Находка для обычного дня",
                visual=f"{creator.capitalize()} speaks directly to a phone camera in {use_context}; product identity appears only as permitted by the asset contract.",
                product_visibility="Exact packshot overlay only." if policy.current_asset_tier == "tier_1" else product_visibility,
                camera_motion="natural handheld phone movement",
                safety_constraints=common_safety,
                must_avoid=["generic substitute product", "fake label", "floating object"],
            ),
            OneVideoScene(
                scene_number=2,
                role="personal_context",
                starts_at=2,
                duration_seconds=3,
                spoken_line=f"Мне было важно понять, как это работает в ситуации: {use_context}.",
                caption="Проверяю в реальной ситуации",
                visual=f"Creator establishes the real buyer context: {use_context}. Product use is not shown unless references permit it.",
                product_visibility="No generated product use before Tier 3; packshot overlay remains exact.",
                camera_motion="one smooth contextual pan",
                safety_constraints=common_safety,
                must_avoid=["hard montage", "unrelated lifestyle stock scene"],
            ),
            OneVideoScene(
                scene_number=3,
                role="product_reason",
                starts_at=5,
                duration_seconds=3,
                spoken_line=f"Для меня главный плюс — {safe_benefit}.",
                caption="Почему оставила себе",
                visual="Creator explains one evidence-backed product reason; exact identity comes from approved references or overlay.",
                product_visibility=product_visibility,
                camera_motion="gentle push-in that stops before label distortion",
                safety_constraints=common_safety + GEOMETRY_LOCK_PROMPT_LINES,
                must_avoid=["unsupported promise", "medical claim", "label redesign"],
            ),
            OneVideoScene(
                scene_number=4,
                role="proof_use_case",
                starts_at=8,
                duration_seconds=4,
                spoken_line=interaction_copy["spoken"],
                caption=interaction_copy["caption"],
                visual=application_visual,
                product_visibility=product_visibility,
                camera_motion="continuous reference-matched action, then natural reaction",
                safety_constraints=common_safety,
                must_avoid=[*interaction_copy["avoid"], "wrong product variant"],
            ),
            OneVideoScene(
                scene_number=5,
                role="cta_end_card",
                starts_at=12,
                duration_seconds=3,
                spoken_line="Сохрани, если хочешь посмотреть этот вариант подробнее.",
                caption="Сохрани, чтобы не потерять",
                visual="End card built from the exact approved packshot, product name and short CTA.",
                product_visibility="Approved packshot/end card only; no generated label.",
                camera_motion="steady end card",
                safety_constraints=common_safety + ["end card required", "human review required"],
                must_avoid=["new package design", "unsupported claim", "auto approval"],
            ),
        ]

    def _creative_spec(
        self,
        product: models.Product,
        scenes: list[OneVideoScene],
        policy: ProductScenePolicyOutput,
        *,
        platform: str,
        duration_seconds: int,
    ) -> CreativeSpec:
        if policy.product_profile != "food_snack":
            return self._generic_creative_spec(
                product,
                scenes,
                policy,
                platform=platform,
                duration_seconds=duration_seconds,
            )
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

    def _generic_creative_spec(
        self,
        product: models.Product,
        scenes: list[OneVideoScene],
        policy: ProductScenePolicyOutput,
        *,
        platform: str,
        duration_seconds: int,
    ) -> CreativeSpec:
        source_key = "product_use_case_acceptance_brief"
        attributes = product.attributes_json or {}
        creator = str(attributes.get("creator_persona") or "русскоязычная блогерка 25-35 лет")
        use_context = str(attributes.get("use_context") or attributes.get("application_context") or "повседневное применение")
        viewer_promise = str((product.benefits_json or ["покажу товар в реальном применении без лишних обещаний"])[0])
        selected_hook = HookCandidate(
            hook_type="real_life_product_use",
            hook_text=scenes[0].spoken_line,
            viewer_promise=viewer_promise,
            rationale=f"First-person blogger context plus reference-gated {policy.interaction_mode} interaction.",
            source_flags=[source_key],
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
                claim_refs=[source_key],
                product_display=scene.product_visibility,
                camera_motion=scene.camera_motion,
                composition="vertical phone UGC with safe margins and reference-locked product identity",
                lighting="natural light appropriate to the real use context",
                emotion="calm, useful, credible buyer experience",
                cta=scene.spoken_line if scene.role == "cta_end_card" else None,
            )
            for scene in scenes
        ]
        allowed_claims = [
            AllowedClaim(claim=str(item), source_type="product_record", source_key=source_key)
            for item in (product.benefits_json or [])[:3]
        ]
        return CreativeSpec(
            product_id=product.id,
            sku=product.sku,
            product_title=product.title,
            platform=platform,
            format="short_video",
            aspect_ratio="9:16",
            duration_seconds=duration_seconds,
            creative_objective="Create one product-safe UGC candidate showing a blogger and the category-appropriate product interaction.",
            creative_angle="first_person_real_use_case",
            hook_candidates=[selected_hook],
            selected_hook=selected_hook,
            hook_type=selected_hook.hook_type,
            hook_text=selected_hook.hook_text,
            viewer_promise=selected_hook.viewer_promise,
            first_frame_spec=FirstFrameSpec(
                visual_hook=f"{creator.capitalize()} speaks to camera in a real use context.",
                text_overlay=scenes[0].caption,
                product_visible_by_second=1.0,
                product_display=scenes[0].product_visibility,
                composition="Creator upper body plus reference-safe product identity, 9:16 safe margins.",
                viewer_promise=viewer_promise,
            ),
            scene_plan=creative_scenes,
            captions=[scene.caption for scene in scenes],
            voiceover=[scene.spoken_line for scene in scenes],
            visual_style="realistic Russian UGC, phone camera, natural creator presentation and real use context",
            product_display_rules=[
                "Preserve the exact SKU, variant, label, color, geometry and scale from approved references.",
                "Do not show product handling or interaction above the current Product Asset Contract tier.",
                "Use static packshot overlay and end card whenever identity cannot be generated safely.",
                f"Show only the real intended {policy.interaction_mode} interaction supported by approved use-case references.",
            ],
            product_geometry_spec=ProductGeometrySpec(
                product_id=product.id,
                sku=product.sku,
                primary_reference_asset_id=policy.reference_readiness.get("primary_reference_asset_id"),
                human_geometry_notes="Product scale, silhouette, label and handling must match approved references.",
            ),
            product_geometry_rules=default_product_geometry_rules(),
            product_scale_rules=default_product_scale_rules(),
            product_visibility_rules=default_product_visibility_rules(),
            must_include=[creator, use_context, "first-person product reason", "reference-supported interaction or safe overlay", "CTA/end card"],
            must_avoid=["generic substitute product", "wrong SKU variant", "invented product interaction", "unsupported result", "medical or guaranteed claims"],
            allowed_claims=allowed_claims,
            allowed_claim_refs=[source_key],
            reference_images=policy.reference_readiness.get("provider_reference_bundle", {}).get("reference_images", []),
            source_map={source_key: "Product record and operator-approved use-case brief"},
            quality_rubric=QualityRubric(
                items=[
                    QualityRubricItem(key="product_identity_locked", label="Exact product variant stays locked"),
                    QualityRubricItem(key="interaction_matches_refs", label="Product interaction matches approved references"),
                    QualityRubricItem(key="blogger_meaning", label="Blogger has a credible first-person reason"),
                    QualityRubricItem(key="cta_end_card", label="CTA/end card is present"),
                ],
                notes=["Human visual review is mandatory after render."],
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
                "objective": f"controlled product-safe blogger UGC render with real {policy.interaction_mode} interaction",
                "product_profile": policy.product_profile,
                "variant_key": policy.variant_key,
            },
            source_summary_json={"operator_brief": "Product-safe blogger and use-case acceptance"},
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
        attributes = product.attributes_json or {}
        is_food = policy.product_profile == "food_snack"
        use_context = str(attributes.get("use_context") or attributes.get("application_context") or "real everyday use")
        brief = models.ScriptBrief(
            product_id=product.id,
            intelligence_pack_id=intelligence.id,
            status="one_video_plan_ready",
            objective="One controlled product-safe UGC paid smoke candidate.",
            creative_angle="sporty_real_life_snack_find" if is_food else "first_person_real_use_case",
            target_audience=(
                "Russian-speaking marketplace shopper looking for a convenient dessert-style snack."
                if is_food
                else f"Russian-speaking buyer evaluating {product.title} for {use_context}."
            ),
            brief_json={
                "product_scene_policy": policy.model_dump(mode="json"),
                "blogger_meaning": "first-person reason to show the product",
                "real_use_context": use_context,
                "interaction_mode": policy.interaction_mode,
            },
            allowed_claims_json=(
                ["convenient snack format", "dessert-style format"]
                if is_food
                else [str(item) for item in (product.benefits_json or [])[:3]]
            ),
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
        source_key = "operator_bombbar_acceptance_brief" if policy.product_profile == "food_snack" else "product_use_case_acceptance_brief"
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
                "claim_refs": [source_key],
                "provider_prompt_text": scene.provider_prompt_text,
                "negative_prompt": scene.negative_prompt,
                "safety_constraints": scene.safety_constraints,
                "scene_policy_allowed": True,
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
            visual_style=(
                "realistic Russian Wibes/Reels UGC, sporty woman 25-30, phone camera"
                if policy.product_profile == "food_snack"
                else f"realistic Russian blogger UGC, phone camera, real {policy.interaction_mode} product context"
            ),
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
        attributes = product.attributes_json or {}
        is_food = policy.product_profile == "food_snack"
        use_context = str(attributes.get("use_context") or attributes.get("application_context") or "повседневное применение")
        first_benefit = str((product.benefits_json or ["понятный сценарий реального применения"])[0])
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
            one_sentence_thesis=(
                "Sporty Russian creator presents the exact snack variant without unsafe packaging or edible generation."
                if is_food
                else f"Russian blogger presents the exact {product.title} through a credible first-person use case."
            ),
            viewer_takeaway="Convenient dessert-style snack for coffee or on the go." if is_food else first_benefit,
            buyer_situation=(
                "Busy day, workout, walk, or coffee break when there is no time for a normal meal."
                if is_food
                else use_context
            ),
            main_objection=(
                "AI may deform the wrapper, mix the flavor variant, or invent food texture."
                if is_food
                else "AI may replace the SKU, deform the product, or invent an unsupported interaction/result."
            ),
            reason_to_believe=f"Product identity and {policy.interaction_mode} interaction are limited by approved Product Asset Contract references.",
            proof_moment=(
                "Approved cutaway plus creator reaction, or bite only at Tier 4."
                if is_food
                else "Approved use-case insert plus creator reaction; no invented product behavior."
            ),
            cta=scenes[-1].spoken_line,
            must_show_json=["creator talking-head", "exact product identity", f"real {policy.interaction_mode} use-case", "CTA/end card"],
            must_say_json=[scene.spoken_line for scene in scenes],
            must_avoid_json=prompt_preview.get("scene_prompts", [{}])[0].get("must_avoid", []),
            product_identity_rules_json=policy.model_dump(mode="json"),
            product_lock_mode="packshot_overlay" if policy.packshot_overlay_required else "reference_i2v",
            reference_requirements_json=policy.reference_readiness,
            scene_count=len(scenes),
            duration_seconds=15,
            failure_conditions_json=(prompt_preview.get("quality_checklist") or [])[:4],
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
                "approved_identity_asset_ids": policy.approved_identity_asset_ids,
                "approved_use_case_asset_ids": policy.approved_use_case_asset_ids,
                "product_scene_policy": policy.model_dump(mode="json"),
                "product_asset_contract": policy.asset_contract,
            },
            overlay_instructions_json={"packshot_overlay_required": policy.packshot_overlay_required},
            end_card_instructions_json={"end_card_required": policy.end_card_required, "cta": scenes[-1].spoken_line},
            quality_checklist_json=prompt_preview.get("quality_checklist") or [],
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
                    hook_formula="First-person real-life product use situation.",
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
            "Goal: one product-safe blogger UGC render with a category-appropriate reference-supported interaction.",
            f"Product profile: {policy.product_profile}; exact variant: {policy.variant_key or 'product-id boundary'}.",
            f"Asset tier: {policy.current_asset_tier}; required: {policy.required_asset_tier}.",
            f"Interaction mode: {policy.interaction_mode}; use-case allowed: {policy.use_case_scene_allowed}; interaction allowed: {policy.interaction_scene_allowed}.",
            f"Bite scene allowed (food only): {policy.bite_scene_allowed}.",
            "",
            "## Scenes",
        ]
        lines.extend(f"- {scene.starts_at}-{scene.starts_at + scene.duration_seconds}s {scene.role}: {scene.spoken_line}" for scene in scenes)
        return "\n".join(lines)


# Backward-compatible name for existing routes, CLI commands and stored plans.
BombbarOneVideoRenderPlanner = ProductUseVideoRenderPlanner
