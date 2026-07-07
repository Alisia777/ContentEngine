from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.intelligence.errors import ProviderConfigurationError


MAX_RUNWAY_PROMPT_CHARS = 1000


@dataclass(frozen=True)
class ProductUGCProfile:
    hook: str
    voiceover: str
    cta: str
    product_scale: str
    package_identity: str
    provider_prompt: str


class UGCRealismService:
    """Stores realistic UGC direction in the DB before prompt/video generation."""

    def __init__(self, db: Session):
        self.db = db

    def apply_to_variant(
        self,
        creative_variant_id: int,
        *,
        duration_seconds: int = 8,
        presenter_profile: str = "sporty_female_25_30",
        platform: str = "Instagram Reels",
    ) -> models.CreativeVariant:
        if duration_seconds < 6 or duration_seconds > 8:
            raise ProviderConfigurationError("Realistic UGC tasting videos should stay between 6 and 8 seconds.")
        variant = self.db.get(models.CreativeVariant, creative_variant_id)
        if not variant:
            raise ProviderConfigurationError(f"CreativeVariant {creative_variant_id} not found.")
        product = variant.creative_spec.product
        profile = self._product_profile(product, duration_seconds=duration_seconds, platform=platform)

        variant.hook_text = profile.hook
        variant.cta_framing = profile.cta
        variant.visual_style = (
            "Realistic vertical Instagram UGC ad: smooth one-take phone video, sporty woman age 25-30, "
            "product presentation first, edible piece tasting second, no generated text."
        )
        variant.pacing_json = self._pacing(duration_seconds)
        variant.first_frame_json = self._first_frame(profile, presenter_profile=presenter_profile)
        variant.scene_plan_json = [
            {
                "scene_number": 1,
                "role": "realistic_sporty_presenter_ugc",
                "starts_at": 0,
                "duration_seconds": duration_seconds,
                "visual": profile.provider_prompt,
                "caption": "",
                "voiceover": profile.voiceover,
                "provider_prompt_text": profile.provider_prompt,
                "negative_prompt": self._negative_prompt(),
                "safety_constraints": self._safety_constraints(),
                "claim_refs": ["product_field:description", "product_asset:approved_packshot"],
                "product_display": (
                    f"{product.title} package stays readable and separate from mouth; "
                    f"presenter bites only a separate unwrapped edible piece; {profile.product_scale}."
                ),
                "camera_motion": "smooth handheld continuous take, no cuts, no transitions",
                "composition": "9:16 sporty presenter shot, no text overlay, package readable, edible piece separate from wrapper",
                "lighting": "bright natural gym, kitchen, or post-workout creator lighting",
                "emotion": "fit, confident, friendly, tasty, believable",
                "cta": profile.cta,
            }
        ]
        variant.selection_reason = (
            "Realistic UGC contract applied from DB: sporty presenter, smooth one-take, "
            "package proof, edible-piece tasting, no generated text."
        )
        variant.risk_flags_json = list(
            dict.fromkeys(
                [
                    *(variant.risk_flags_json or []),
                    "realistic_ugc_contract",
                    "sporty_presenter_25_30",
                    "smooth_one_take",
                    "no_wrapper_biting",
                    "no_generated_text",
                ]
            )
        )
        self._update_spec(variant.creative_spec, profile, duration_seconds=duration_seconds)
        self._update_assignments(variant, profile, duration_seconds=duration_seconds, platform=platform)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def _update_spec(self, spec: models.VideoCreativeSpecRecord, profile: ProductUGCProfile, *, duration_seconds: int) -> None:
        spec.duration_seconds = duration_seconds
        spec.spec_json = {
            **(spec.spec_json or {}),
            "duration_seconds": duration_seconds,
            "ugc_realism_contract": self._contract(profile, duration_seconds=duration_seconds),
            "product_display_rules": [
                "Sporty adult woman age 25-30 presents the product as a sports nutrition snack/protein dessert.",
                "Use one continuous smooth handheld shot; avoid jump cuts, montage, and scene transitions.",
                "Show package as product proof, readable and away from mouth.",
                "Show a separate unwrapped edible piece before the bite.",
                "Presenter bites only edible product, never wrapper or packaging.",
                "Do not generate on-screen text, subtitles, floating words, or fake typography.",
                "Preserve package colors, logo, flavor cues, badges, and visible weight.",
            ],
            "product_geometry_rules": {
                "preserve_reference_silhouette": True,
                "preserve_wrapper_or_box_shape": True,
                "single_bar_not_display_box_when_tasting": True,
                "do_not_bite_wrapper": True,
                "no_generated_text": True,
                "smooth_continuous_take": True,
                "sporty_presenter_age_25_30": True,
            },
            "product_scale_rules": {
                "product_scale_relative_to_hand": profile.product_scale,
                "single_bar_is_hero_when_tasting": True,
                "do_not_make_product_oversized": True,
            },
            "product_visibility_rules": {
                "product_visible_by_second": 0.0,
                "front_pack_or_wrapper_readable": True,
                "edible_piece_visible_before_bite": True,
                "avoid_occluding_logo_flavor_or_weight": True,
                "keep_product_in_focus": True,
            },
            "must_include": [
                "sporty female presenter age 25-30",
                "smooth one-take presentation",
                "package proof before tasting",
                "separate unwrapped edible piece",
                "natural fitness creator tone",
            ],
            "must_avoid": [
                "biting wrapper",
                "package in mouth",
                "hard cuts or montage",
                "generated subtitles or fake text",
                "medical or weight-loss claims",
                "product redesign",
            ],
            "review_checklist": [
                "sporty_presenter_age_25_30",
                "one_continuous_smooth_take",
                "package_readable_and_away_from_mouth",
                "edible_piece_tasted_not_wrapper",
                "no_generated_text_overlay",
                "product_identity_preserved",
                "needs_human_review_before_publish",
            ],
        }

    def _update_assignments(
        self,
        variant: models.CreativeVariant,
        profile: ProductUGCProfile,
        *,
        duration_seconds: int,
        platform: str,
    ) -> None:
        assignments = (
            self.db.query(models.ParticipantAssignment)
            .filter(models.ParticipantAssignment.creative_variant_id == variant.id)
            .order_by(models.ParticipantAssignment.id.desc())
            .all()
        )
        for assignment in assignments:
            brief = dict(assignment.brief_json or {})
            brief.update(
                {
                    "ugc_realism_contract": self._contract(profile, duration_seconds=duration_seconds),
                    "hook_text": profile.hook,
                    "russian_voiceover": profile.voiceover,
                    "sales_cta": profile.cta,
                    "ugc_duration_seconds": duration_seconds,
                    "presenter_profile": "sporty female presenter, age 25-30, fitness lifestyle",
                    "platform": platform,
                    "shot_plan": self._pacing(duration_seconds)["beats"],
                    "corrections": [
                        "sporty woman 25-30",
                        "smooth one continuous take",
                        "no jump cuts",
                        "show package first",
                        "no wrapper biting",
                        "bite only unwrapped edible piece",
                        "never put wrapper/package in mouth",
                        "no generated text overlay",
                    ],
                }
            )
            assignment.brief_json = brief
            if assignment.status not in {"submitted", "approved", "rejected"}:
                assignment.status = "assigned"
            if assignment.content_run:
                assignment.content_run.duration_seconds = duration_seconds
                assignment.content_run.status = "ugc_realism_prompt_ready"
                run_json = dict(assignment.content_run.run_json or {})
                run_json["ugc_realism_contract"] = brief["ugc_realism_contract"]
                assignment.content_run.run_json = run_json

    @staticmethod
    def _first_frame(profile: ProductUGCProfile, *, presenter_profile: str) -> dict[str, Any]:
        return {
            "hook_text": profile.hook,
            "visual_concept": (
                "Sporty woman age 25-30 presents the package close to camera, readable, away from mouth; "
                "clean realistic phone video with no text overlay."
            ),
            "text_overlay": "",
            "product_placement": "Package in hand as proof; separate unwrapped edible piece only for tasting.",
            "camera_motion": "smooth handheld selfie micro push-in, one continuous take",
            "composition": "vertical 9:16, presenter and package visible, clean frame without generated text",
            "presenter_profile": presenter_profile,
            "required_assets": ["packshot"],
            "risk_flags": ["no_jump_cuts", "do_not_bite_wrapper", "no_generated_text"],
            "product_visible_by_second": 0.0,
            "source_flags": ["approved_packshot", "product_weight_from_package"],
        }

    @staticmethod
    def _pacing(duration_seconds: int) -> dict[str, Any]:
        return {
            "total_seconds": duration_seconds,
            "continuity": "single continuous take, no cuts or transitions",
            "beats": [
                "0-3s sporty presenter shows package close to camera, readable, away from mouth",
                "3-5s presenter explains snack/protein dessert use case in Russian, smooth camera",
                "5-6.5s separate unwrapped edible piece shown and tasted, never wrapper",
                f"6.5-{duration_seconds}s reaction, package close-up CTA gesture, no text overlay",
            ],
        }

    @staticmethod
    def _contract(profile: ProductUGCProfile, *, duration_seconds: int) -> dict[str, Any]:
        return {
            "format": "realistic_ugc_sports_nutrition_presentation",
            "duration_seconds": duration_seconds,
            "presenter": "sporty athletic woman, 25-30, fitness lifestyle",
            "continuity": "one continuous smooth handheld shot",
            "voiceover_language": "Russian",
            "voiceover": profile.voiceover,
            "cta": profile.cta,
            "package_identity": profile.package_identity,
            "product_scale": profile.product_scale,
            "must_do": [
                "present package before tasting",
                "keep package readable and away from mouth",
                "show separate unwrapped edible piece",
                "bite only edible piece",
                "use natural fitness creator energy",
            ],
            "must_not_do": [
                "bite wrapper",
                "put package in mouth",
                "use hard cuts or montage",
                "generate text overlays",
                "make medical or weight-loss claims",
                "redesign product packaging",
            ],
        }

    @staticmethod
    def _negative_prompt() -> str:
        return ", ".join(
            [
                "jump cut",
                "hard cut",
                "montage",
                "scene transition",
                "biting wrapper",
                "eating packaging",
                "package in mouth",
                "chewing wrapper",
                "wrapper in teeth",
                "on-screen text",
                "subtitles",
                "floating words",
                "misspelled text",
                "fake typography",
                "wrong logo",
                "wrong colors",
                "oversized product",
                "bottle",
                "jar",
                "tube",
                "medical claim",
                "weight loss claim",
            ]
        )

    @staticmethod
    def _safety_constraints() -> list[str]:
        return [
            "one continuous smooth take",
            "sporty presenter age 25-30",
            "package is presented but never bitten",
            "bite only a separate unwrapped edible piece",
            "no generated on-screen text",
            "preserve product identity",
            "avoid medical or weight-loss claims",
        ]

    def _product_profile(self, product: models.Product, *, duration_seconds: int, platform: str) -> ProductUGCProfile:
        text = " ".join([product.sku, product.brand, product.title, product.description or ""]).lower()
        if "dubai" in text or "mango" in text or "kunafa" in text:
            return self._profile(
                hook="Bombbar Pro Dubai: спортивный десерт манго и кунафа",
                voiceover="Это как десерт после тренировки: манго и кунафа звучат необычно, вкус яркий, формат удобно брать с собой.",
                cta="Показать упаковку в камеру и жестом предложить взять на перекус, без текста на экране.",
                product_scale="single 45 g wrapped bar is palm-sized, about 11-14 cm; display box only background",
                package_identity="black/green/yellow/orange Bombbar Pro Dubai wrapper, mango/kunafa cues, 45 g scale",
                product_name=product.title,
                duration_seconds=duration_seconds,
                platform=platform,
            )
        if "lemon" in text or "poppy" in text or "quadro" in text:
            return self._profile(
                hook="Bombbar Brownie Quadro: спортивный перекус с лимоном и маком",
                voiceover="После тренировки хочется десерт, но без лишней приторности. Лимон яркий, мак хрустит, удобно взять с собой.",
                cta="Показать упаковку в камеру и жестом предложить посмотреть вкус в карточке, без текста на экране.",
                product_scale="single 50 g wrapped bar is palm-sized, about 12-15 cm; display box only background",
                package_identity="green/yellow Bombbar wrapper, lemon/poppy flavor cues, badges, 50 g scale",
                product_name=product.title,
                duration_seconds=duration_seconds,
                platform=platform,
            )
        return self._profile(
            hook=f"{product.brand}: спортивный перекус на каждый день",
            voiceover="Удобный формат после тренировки или с собой: показываю упаковку, пробую кусочек и делюсь вкусом.",
            cta="Показать упаковку в камеру и жестом предложить посмотреть карточку товара, без текста на экране.",
            product_scale="single wrapped snack bar is palm-sized; display box only background",
            package_identity="exact wrapper, logo, flavor cues, badges, and visible weight from the reference image",
            product_name=product.title,
            duration_seconds=duration_seconds,
            platform=platform,
        )

    @staticmethod
    def _profile(
        *,
        hook: str,
        voiceover: str,
        cta: str,
        product_scale: str,
        package_identity: str,
        product_name: str,
        duration_seconds: int,
        platform: str,
    ) -> ProductUGCProfile:
        prompt = (
            f"Vertical 9:16 {platform} realistic UGC ad, {duration_seconds} seconds, one continuous smooth handheld shot, "
            "no cuts, no montage, no on-screen text. Sporty athletic adult woman presenter age 25-30 in gym top or "
            f"post-workout casual outfit presents one {product_name} package from the prompt image close to camera, "
            "readable and away from mouth. She talks in Russian like a fitness creator recommending a sports nutrition "
            "snack/protein dessert. Then she shows a separate small unwrapped edible piece in her fingers, takes one "
            "small bite only from that edible piece, never from wrapper or package, smiles and points back to the "
            f"original package. Preserve exact {package_identity}. Smooth camera, natural light, appetizing, believable."
        )
        if len(prompt) > MAX_RUNWAY_PROMPT_CHARS:
            prompt = prompt[: MAX_RUNWAY_PROMPT_CHARS - 1].rstrip()
        return ProductUGCProfile(
            hook=hook,
            voiceover=voiceover,
            cta=cta,
            product_scale=product_scale,
            package_identity=package_identity,
            provider_prompt=prompt,
        )
