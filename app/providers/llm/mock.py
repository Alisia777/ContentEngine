import json
from typing import Any


class MockLLMClient:
    """Deterministic script generator for the local MVP."""

    def generate_script(self, input_payload: dict) -> dict:
        product = input_payload["product"]
        brand_rules = input_payload["brand_rules"]
        template = input_payload["template"]
        benefits = product.get("benefits_json") or []
        first_benefit = benefits[0] if benefits else "needs_data"
        title = product.get("title") or "Product"
        category = product.get("category") or "everyday routine"
        cta_options = brand_rules.get("allowed_cta_json") or []
        cta = template.get("cta") or (cta_options[0] if cta_options else "Learn more in the product card")
        duration = int(template.get("duration_seconds") or 15)
        aspect_ratio = template.get("aspect_ratio") or "9:16"

        scene_duration = max(3, duration // 4)
        scenes = [
            {
                "scene_number": 1,
                "time_range": f"0-{scene_duration}s",
                "visual": f"Clean vertical opener showing {title} in a real {category} context.",
                "voiceover": f"Need a clearer way to show what {title} is for?",
                "caption": f"{title}: clear product story",
                "video_prompt": f"Vertical {aspect_ratio} realistic product lifestyle opener, soft light, clean marketplace ad style, show {title}",
                "negative_prompt": "distorted product, fake medical claims, low quality, misleading before-after",
                "source_fields": ["product.title", "product.category"],
            },
            {
                "scene_number": 2,
                "time_range": f"{scene_duration}-{scene_duration * 2}s",
                "visual": "Close product detail shot with a simple benefit caption.",
                "voiceover": first_benefit if first_benefit != "needs_data" else "Add a verified product benefit before publishing.",
                "caption": first_benefit if first_benefit != "needs_data" else "Benefit needs data",
                "video_prompt": f"Vertical {aspect_ratio} close product detail scene, highlight verified benefit, neutral background",
                "negative_prompt": "unsupported claims, exaggerated results, medical claims, distorted packaging",
                "source_fields": ["product.benefits_json"] if first_benefit != "needs_data" else ["needs_data.product.benefits_json"],
            },
            {
                "scene_number": 3,
                "time_range": f"{scene_duration * 2}-{scene_duration * 3}s",
                "visual": "Usage moment with the product framed clearly and naturally.",
                "voiceover": f"Built for {category.lower()} buyers who want a straightforward choice.",
                "caption": f"Made for {category}",
                "video_prompt": f"Vertical {aspect_ratio} realistic usage scene, product centered, human hands optional, no text artifacts",
                "negative_prompt": "fake platform UI, unreadable labels, off-brand colors, low quality",
                "source_fields": ["product.category", "product.description"],
            },
            {
                "scene_number": 4,
                "time_range": f"{scene_duration * 3}-{duration}s",
                "visual": "CTA end card with product and marketplace-safe copy.",
                "voiceover": cta,
                "caption": cta,
                "video_prompt": f"Vertical {aspect_ratio} clean CTA product end card, marketplace link style, simple brand-safe composition",
                "negative_prompt": "spammy CTA, fake discounts, platform bypass language, low quality",
                "source_fields": ["brand.allowed_cta_json", "product.product_url"],
            },
        ]

        script = {
            "creative_angle": template.get("name") or "problem_solution_cta",
            "duration_seconds": duration,
            "aspect_ratio": aspect_ratio,
            "hook": f"Can shoppers understand {title} in the first three seconds?",
            "key_message": first_benefit if first_benefit != "needs_data" else "needs_data",
            "final_cta": cta,
            "scenes": scenes,
            "review_checks": [
                "No forbidden claims",
                "CTA present",
                "Captions present",
                "Every product claim references a source field",
                "Product not distorted",
            ],
        }
        return script

    def validate_script(self, script_json: dict, product_data: dict, brand_rules: dict) -> dict:
        text = json.dumps(script_json, ensure_ascii=False).lower()
        forbidden_terms = list(brand_rules.get("forbidden_words_json") or []) + list(
            brand_rules.get("forbidden_claims_json") or []
        )
        errors = []
        warnings = []
        checks = []

        for term in forbidden_terms:
            if term and term.lower() in text:
                errors.append(f"Forbidden term or claim found: {term}")
        checks.append({"name": "No forbidden claims", "passed": not errors})

        if not script_json.get("final_cta"):
            errors.append("Final CTA is missing")
        checks.append({"name": "CTA present", "passed": bool(script_json.get("final_cta"))})

        scenes = script_json.get("scenes") or []
        if not scenes:
            errors.append("At least one scene is required")
        for scene in scenes:
            if not scene.get("caption"):
                errors.append(f"Scene {scene.get('scene_number')} caption is missing")
            source_fields = scene.get("source_fields") or []
            if not source_fields:
                errors.append(f"Scene {scene.get('scene_number')} has no source fields")
            for source in source_fields:
                if str(source).startswith("needs_data"):
                    warnings.append(f"Scene {scene.get('scene_number')} needs verified data for {source}")
        checks.append({"name": "Captions present", "passed": all(scene.get("caption") for scene in scenes)})
        checks.append({"name": "Source fields present", "passed": all(scene.get("source_fields") for scene in scenes)})

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "source_policy": "Claims must reference product, brand, or needs_data fields.",
        }

