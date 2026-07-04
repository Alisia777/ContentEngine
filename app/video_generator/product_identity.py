from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


PRODUCT_LOCK_MODES = {"reference_i2v", "packshot_overlay", "end_card_packshot", "no_product_generation"}

DEFAULT_PACKAGING_RULES = [
    "Use the approved primary reference image as the exact product reference.",
    "Do not redesign packaging.",
    "Do not change bottle shape.",
    "Do not invent new label graphics.",
    "If label text cannot be preserved, keep the label clean and do not invent fake text.",
]
DEFAULT_LABEL_RULES = [
    "Do not change label color.",
    "Preserve white label if the approved reference has a white label.",
    "Preserve red drip elements if present in the approved reference.",
    "Do not invent fake brand text or fake claims on the label.",
]
DEFAULT_COLOR_RULES = [
    "Do not change cap color.",
    "Do not change label color.",
    "Preserve the product liquid color from the approved reference.",
]
DEFAULT_CAP_RULES = [
    "Do not change cap color.",
    "Do not change cap/dropper shape.",
    "Do not render a black cap if the approved reference cap is not black.",
]
DEFAULT_FORBIDDEN_TRANSFORMATIONS = [
    "wrong cap color",
    "black cap if reference cap is not black",
    "red label if reference label is white",
    "redesigned packaging",
    "fake brand text",
    "distorted logo",
    "different bottle shape",
    "different product",
    "invented label graphics",
]


class ProductIdentityService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(
        self,
        product: models.Product,
        *,
        primary_reference_asset_id: int | None,
        product_lock_mode: str = "reference_i2v",
    ) -> models.ProductIdentitySpec:
        if product_lock_mode not in PRODUCT_LOCK_MODES:
            raise ValueError(f"Unsupported product_lock_mode: {product_lock_mode}")
        spec = self.db.scalar(
            select(models.ProductIdentitySpec)
            .where(models.ProductIdentitySpec.product_id == product.id)
            .order_by(models.ProductIdentitySpec.id.desc())
        )
        if spec:
            if primary_reference_asset_id and spec.primary_reference_asset_id != primary_reference_asset_id:
                spec.primary_reference_asset_id = primary_reference_asset_id
            if not spec.product_lock_mode:
                spec.product_lock_mode = product_lock_mode
            return spec
        spec = models.ProductIdentitySpec(
            product_id=product.id,
            sku=product.sku,
            primary_reference_asset_id=primary_reference_asset_id,
            product_lock_mode=product_lock_mode,
            packaging_must_match_json=list(DEFAULT_PACKAGING_RULES),
            label_requirements_json=list(DEFAULT_LABEL_RULES),
            color_requirements_json=list(DEFAULT_COLOR_RULES),
            cap_requirements_json=list(DEFAULT_CAP_RULES),
            forbidden_transformations_json=list(DEFAULT_FORBIDDEN_TRANSFORMATIONS),
            human_review_notes=(
                "Metadata-only identity constraints. A human reviewer must still approve or reject visual product identity."
            ),
        )
        self.db.add(spec)
        self.db.flush()
        return spec


def identity_spec_payload(spec: models.ProductIdentitySpec | None) -> dict:
    if not spec:
        return {}
    return {
        "id": spec.id,
        "product_id": spec.product_id,
        "sku": spec.sku,
        "primary_reference_asset_id": spec.primary_reference_asset_id,
        "product_lock_mode": spec.product_lock_mode,
        "packaging_must_match": spec.packaging_must_match_json or [],
        "label_requirements": spec.label_requirements_json or [],
        "color_requirements": spec.color_requirements_json or [],
        "cap_requirements": spec.cap_requirements_json or [],
        "forbidden_transformations": spec.forbidden_transformations_json or [],
        "human_review_notes": spec.human_review_notes,
    }


def identity_prompt_rules(spec: models.ProductIdentitySpec | None) -> list[str]:
    if not spec:
        return []
    mode_rules = {
        "reference_i2v": [
            "Use the approved primary reference image as the exact product reference.",
            "Product identity still requires human visual review after generation.",
        ],
        "packshot_overlay": [
            "Generate only the background, motion, and lifestyle context; the real approved packshot will be composited as an overlay.",
            "Do not ask the provider to redraw the exact product packaging.",
        ],
        "end_card_packshot": [
            "The final packshot/end card must use the real approved product asset, not a generated product.",
        ],
        "no_product_generation": [
            "Do not generate the product itself; generate context/background/human-use staging only.",
            "The product appears only through real asset overlay or packshot card.",
        ],
    }
    rules = [
        *mode_rules.get(spec.product_lock_mode, []),
        *(spec.packaging_must_match_json or []),
        *(spec.label_requirements_json or []),
        *(spec.color_requirements_json or []),
        *(spec.cap_requirements_json or []),
    ]
    return list(dict.fromkeys(rule for rule in rules if rule))


def identity_negative_prompt(spec: models.ProductIdentitySpec | None) -> str:
    if not spec:
        return ""
    return ", ".join(dict.fromkeys(spec.forbidden_transformations_json or DEFAULT_FORBIDDEN_TRANSFORMATIONS))


def corrections_from_feedback(feedback: str) -> dict:
    text = feedback.lower()
    flags = []
    if "cap" in text or "крыш" in text or "dropper" in text or "пипет" in text:
        flags.append("cap_color_or_dropper_mismatch")
    if "label" in text or "этикет" in text:
        flags.append("label_mismatch")
    if "red" in text or "красн" in text:
        flags.append("wrong_label_or_color")
    if "black" in text or "черн" in text or "чёрн" in text:
        flags.append("wrong_cap_color")
    if "packag" in text or "упаков" in text:
        flags.append("packaging_redesign")
    return {
        "feedback": feedback,
        "identity_mismatch_flags": list(dict.fromkeys(flags or ["product_identity_mismatch"])),
        "required_corrections": [
            "Keep the approved reference packaging.",
            "Do not change cap/dropper color or shape.",
            "Do not change label color.",
            "Do not invent label graphics or fake text.",
        ],
    }
