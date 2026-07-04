from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app import models


def get_or_create(db, model, lookup: dict, defaults: dict):
    instance = db.scalar(select(model).filter_by(**lookup))
    if instance:
        return instance
    instance = model(**lookup, **defaults)
    db.add(instance)
    db.flush()
    return instance


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        products = [
            {
                "sku": "ALT-SERUM-001",
                "brand": "Altea",
                "marketplace": "Ozon",
                "title": "Altea Glow Serum",
                "description": "Lightweight facial serum for a fresh daily skincare routine.",
                "category": "Beauty",
                "attributes_json": {"volume": "30 ml", "texture": "light serum"},
                "benefits_json": ["helps skin feel hydrated", "fits morning routine"],
                "images_json": ["/media/mock/serum.jpg"],
                "reviews_json": [{"rating": 5, "text": "Nice texture"}],
                "restrictions_json": ["No medical claims"],
                "product_url": "https://example.com/products/alt-serum-001",
            },
            {
                "sku": "ALT-BOTTLE-002",
                "brand": "Altea",
                "marketplace": "Wildberries",
                "title": "Altea Steel Water Bottle",
                "description": "Reusable steel bottle for work, gym, and commute.",
                "category": "Home",
                "attributes_json": {"capacity": "600 ml", "material": "steel"},
                "benefits_json": ["keeps drinks at hand", "durable daily carry"],
                "images_json": ["/media/mock/bottle.jpg"],
                "reviews_json": [{"rating": 4, "text": "Easy to carry"}],
                "restrictions_json": [],
                "product_url": "https://example.com/products/alt-bottle-002",
            },
            {
                "sku": "ALT-ORGANIZER-003",
                "brand": "Altea",
                "marketplace": "Ozon",
                "title": "Altea Desk Organizer",
                "description": "Compact organizer for stationery and small office items.",
                "category": "Office",
                "attributes_json": {"sections": 5, "color": "graphite"},
                "benefits_json": ["reduces desk clutter", "keeps essentials visible"],
                "images_json": ["/media/mock/organizer.jpg"],
                "reviews_json": [{"rating": 5, "text": "Desk looks cleaner"}],
                "restrictions_json": [],
                "product_url": "https://example.com/products/alt-organizer-003",
            },
        ]
        for product in products:
            sku = product.pop("sku")
            get_or_create(db, models.Product, {"sku": sku}, product)

        guides = [
            {
                "brand": "Altea",
                "tone_of_voice": "Clear, helpful, marketplace-native, no hype.",
                "visual_style": "Soft light, realistic product usage, clean backgrounds.",
                "forbidden_words_json": ["guaranteed", "miracle", "cure"],
                "forbidden_claims_json": ["medical treatment", "instant result"],
                "required_disclaimers_json": ["AI-assisted creative"],
                "allowed_cta_json": ["Learn more in the product card", "Open the product page"],
            },
            {
                "brand": "Qharisma",
                "tone_of_voice": "Operational, precise, and premium.",
                "visual_style": "Modern production workflow visuals.",
                "forbidden_words_json": ["fake", "spam"],
                "forbidden_claims_json": ["platform bypass"],
                "required_disclaimers_json": ["Internal production use"],
                "allowed_cta_json": ["Review package", "Schedule content"],
            },
        ]
        for guide in guides:
            brand = guide.pop("brand")
            get_or_create(db, models.BrandGuide, {"brand": brand}, guide)

        template_payloads = [
            ("problem_solution_cta", "Problem, product benefit, usage, CTA"),
            ("feature_stack", "Fast feature walkthrough with captions"),
            ("review_angle", "Review-inspired proof points with source references"),
            ("before_after_routine", "Routine shift without exaggerated claims"),
            ("marketplace_short", "Direct product-card traffic video"),
        ]
        for name, description in template_payloads:
            get_or_create(
                db,
                models.CreativeTemplate,
                {"name": name},
                {
                    "description": description,
                    "format": "short_video",
                    "duration_seconds": 15,
                    "aspect_ratio": "9:16",
                    "structure_json": ["hook", "benefit", "usage", "cta"],
                    "hook_formula": "Name a familiar problem, then show the product in context.",
                    "cta": "Learn more in the product card",
                    "platform_fit_json": ["instagram_reels", "tiktok", "youtube_shorts", "telegram"],
                },
            )

        accounts = [
            ("Altea", "Instagram Reels", "Altea Instagram", "@altea.store", "SMM Lead", "warming", "phase_1_soft_start", 1, 3),
            ("Altea", "TikTok", "Altea TikTok", "@altea.shop", "SMM Lead", "warming", "phase_1_soft_start", 1, 3),
            ("Altea", "YouTube Shorts", "Altea YouTube Shorts", "@altea", "Video Lead", "active", "phase_2_regular_posting", 2, 7),
            ("Altea", "Telegram", "Altea Telegram", "@altea_channel", "Content Ops", "active", "phase_2_regular_posting", 3, 10),
            ("Altea", "WB/Ozon", "Altea WB/Ozon marketplace media placeholder", "seller-media", "Marketplace Lead", "new", "phase_0_setup", 1, 2),
        ]
        for brand, platform, name, handle, owner, status, phase, daily, weekly in accounts:
            get_or_create(
                db,
                models.PublishingAccount,
                {"account_name": name},
                {
                    "brand": brand,
                    "platform": platform,
                    "account_handle": handle,
                    "account_url": f"https://example.com/{handle.strip('@')}",
                    "owner_name": owner,
                    "auth_status": "mock_ready" if platform in {"Telegram", "YouTube Shorts"} else "manual_upload_required",
                    "warmup_status": status,
                    "warmup_phase": phase,
                    "daily_publish_limit": daily,
                    "weekly_publish_limit": weekly,
                    "allowed_formats_json": ["vertical_video", "captioned_short"],
                    "notes": "Owned account. Scheduling must respect warm-up limits.",
                },
            )

        plan_defs = [
            (
                "conservative_new_account",
                "phase_1_soft_start",
                [
                    ("phase_1_soft_start", 1, 7, 1, 3),
                    ("phase_2_regular_posting", 8, 30, 2, 7),
                ],
            ),
            (
                "regular_brand_account",
                "phase_2_regular_posting",
                [
                    ("phase_2_regular_posting", 1, 14, 2, 7),
                    ("phase_3_scaled_posting", 15, 45, 3, 12),
                ],
            ),
        ]
        for name, phase, rules in plan_defs:
            plan = get_or_create(
                db,
                models.WarmupPlan,
                {"name": name},
                {"current_phase": phase, "status": "active", "rules_json": [r[0] for r in rules]},
            )
            if not plan.rules:
                for rule_phase, day_from, day_to, daily, weekly in rules:
                    db.add(
                        models.WarmupRule(
                            warmup_plan_id=plan.id,
                            phase=rule_phase,
                            day_from=day_from,
                            day_to=day_to,
                            max_posts_per_day=daily,
                            max_posts_per_week=weekly,
                            allowed_content_types_json=["vertical_video", "captioned_short"],
                            requires_manual_approval=True,
                            notes="Gradual, transparent publishing only.",
                        )
                    )

        db.commit()


if __name__ == "__main__":
    seed()
    print("Seed data ready.")

