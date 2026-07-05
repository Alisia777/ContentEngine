from __future__ import annotations

from typing import Any


GEOMETRY_LOCK_PROMPT_LINES = [
    "Keep the product the same size and proportions as the primary reference image.",
    "Preserve the bottle silhouette.",
    "Preserve height-to-width ratio.",
    "Preserve cap/dropper size and placement.",
    "Preserve label area size and placement.",
    "Keep natural cosmetic bottle scale relative to hand/table.",
    "Do not stretch, squash, shrink, enlarge, or redesign the product.",
]

GEOMETRY_NEGATIVE_TERMS = [
    "changed product size",
    "wrong proportions",
    "stretched bottle",
    "squashed bottle",
    "oversized product",
    "miniature product",
    "changed silhouette",
    "wider bottle",
    "narrower bottle",
    "taller bottle",
    "shorter bottle",
    "enlarged cap",
    "wrong cap size",
    "label area changed",
    "product scale mismatch",
]


def default_product_geometry_rules() -> dict[str, Any]:
    return {
        "preserve_reference_silhouette": True,
        "preserve_height_width_ratio": True,
        "preserve_bottle_body_shape": True,
        "preserve_cap_size_and_position": True,
        "preserve_label_size_and_position": True,
        "do_not_stretch_or_squash": True,
    }


def default_product_scale_rules() -> dict[str, Any]:
    return {
        "product_should_occupy_percent_of_frame": "25-40%",
        "product_scale_relative_to_hand": "natural cosmetic bottle scale",
        "do_not_make_product_miniature": True,
        "do_not_make_product_oversized": True,
    }


def default_product_visibility_rules() -> dict[str, Any]:
    return {
        "product_visible_by_second": 1.5,
        "product_face_label_visible": True,
        "avoid_occluding_cap_or_label": True,
        "keep_product_in_focus": True,
    }


def geometry_lock_prompt_text() -> str:
    return " ".join(GEOMETRY_LOCK_PROMPT_LINES)


def geometry_negative_prompt(existing: str | None = None) -> str:
    terms = [term.strip() for term in (existing or "").split(",") if term.strip()]
    terms.extend(GEOMETRY_NEGATIVE_TERMS)
    return ", ".join(dict.fromkeys(terms))
