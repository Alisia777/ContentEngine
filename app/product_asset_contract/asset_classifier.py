from __future__ import annotations

import re
import unicodedata

from app import models
from app.product_asset_contract.types import AssetClassification


CONTRACT_FAMILIES = {
    "front_packshot": "identity",
    "angled_wrapper": "identity",
    "angled_product": "identity",
    "label_closeup": "identity",
    "wrapper_in_hand": "handling",
    "wrapper_on_table": "handling",
    "product_in_hand": "handling",
    "product_on_surface": "handling",
    "scale_context": "geometry",
    "semi_open_wrapper": "use_case",
    "wrapper_plus_product": "proof",
    "whole_unwrapped_product": "use_case",
    "cutaway_product": "proof",
    "bitten_product": "interaction",
    "product_near_mouth": "interaction",
    "texture_macro": "proof",
    "opening_video_reference": "interaction",
    "use_video_reference": "interaction",
    "dispenser_closeup": "proof",
    "texture_swatch": "proof",
    "application_demo": "interaction",
    "application_area": "use_case",
    "front_view": "identity",
    "back_view": "identity",
    "detail_closeup": "proof",
    "on_body": "use_case",
    "movement_reference": "interaction",
    "application_context": "use_case",
    "result_context": "proof",
    "style_reference": "style",
    "lifestyle_reference": "lifestyle",
    "unknown": "unknown",
}

DIRECT_TYPE_MAP = {
    "packshot": "front_packshot",
    "product_packshot": "front_packshot",
    "label_closeup": "label_closeup",
    "packaging_closeup": "label_closeup",
    "label": "label_closeup",
    "cutaway": "cutaway_product",
    "slice": "cutaway_product",
    "sliced": "cutaway_product",
    "unwrapped": "whole_unwrapped_product",
    "bite": "bitten_product",
    "bitten": "bitten_product",
    "texture": "texture_macro",
    "macro": "texture_macro",
    "style": "style_reference",
    "creator_style": "style_reference",
    "ugc_style": "style_reference",
    "moodboard": "style_reference",
    "lifestyle": "lifestyle_reference",
    "context": "lifestyle_reference",
    "use_case": "application_context",
}

KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("product_near_mouth", ("near mouth", "at mouth", "у рта", "возле рта")),
    ("bitten_product", ("bitten", "bite mark", "надкушен", "укус")),
    ("semi_open_wrapper", ("semi open", "semi-open", "opened wrapper", "приоткрыт", "открытая упаковка")),
    ("opening_video_reference", ("opening video", "removing product video", "unboxing video", "видео открытия")),
    ("movement_reference", ("movement", "walking", "turning", "движение", "в движении")),
    ("application_demo", ("application demo", "applying", "нанесение", "применение", "использование")),
    ("application_area", ("application area", "on skin", "на коже", "зона нанесения")),
    ("dispenser_closeup", ("dispenser", "pump closeup", "дозатор", "помпа")),
    ("texture_swatch", ("swatch", "texture smear", "свотч", "мазок текстуры")),
    ("on_body", ("on body", "worn", "try on", "на модели", "примерка")),
    ("back_view", ("back view", "вид сзади")),
    ("front_view", ("front view", "вид спереди")),
    ("detail_closeup", ("detail closeup", "fabric detail", "деталь крупно", "шов")),
    ("wrapper_plus_product", ("beside wrapper", "with wrapper", "рядом с упаковкой", "упаковка и продукт")),
    ("cutaway_product", ("cutaway", "cross section", "sliced", "разрез", "срез")),
    ("whole_unwrapped_product", ("whole unwrapped", "unwrapped product", "без упаковки", "распакованный")),
    ("texture_macro", ("texture macro", "macro texture", "макро текстур", "текстура крупно")),
    ("wrapper_in_hand", ("wrapper in hand", "package in hand", "упаковка в руке")),
    ("product_in_hand", ("product in hand", "holding product", "товар в руке")),
    ("wrapper_on_table", ("wrapper on table", "package on table", "упаковка на столе")),
    ("product_on_surface", ("product on table", "product on surface", "товар на столе")),
    ("scale_context", ("scale context", "size reference", "масштаб", "размер в руке")),
    ("angled_wrapper", ("angled wrapper", "wrapper angle", "упаковка под углом")),
    ("angled_product", ("angled product", "three quarter", "3/4 view", "товар под углом")),
    ("label_closeup", ("label closeup", "packaging closeup", "этикетка", "лейбл")),
    ("front_packshot", ("front packshot", "packshot", "фронт", "вид спереди упаковки")),
    ("style_reference", ("style reference", "moodboard", "ugc style", "стиль", "вайб")),
    ("lifestyle_reference", ("lifestyle", "setting", "creator reference", "контекст", "обстановка")),
    ("application_context", ("use case", "application context", "сценарий использования")),
    ("result_context", ("result context", "finished result", "результат использования")),
)


def normalize_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    normalized = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE).strip("-")
    return normalized or None


class ProductAssetClassifier:
    def classify(self, asset: models.ProductAsset, *, expected_variant_key: str | None = None) -> AssetClassification:
        metadata = asset.metadata_json or {}
        explicit_type = str(metadata.get("contract_type") or metadata.get("asset_contract_type") or "").strip().lower()
        evidence: list[str] = []
        if explicit_type in CONTRACT_FAMILIES:
            contract_type = explicit_type
            evidence.append("metadata.contract_type")
        else:
            contract_type = self._contract_type(asset)
            evidence.append("asset_metadata_and_label_classifier")

        family = CONTRACT_FAMILIES.get(contract_type, "unknown")
        asset_variant = normalize_key(metadata.get("variant_key") or metadata.get("flavor") or metadata.get("model_variant"))
        expected_variant = normalize_key(expected_variant_key)
        if family in {"style", "lifestyle"}:
            variant_status = "shared_non_identity"
            eligible = True
        elif not expected_variant:
            variant_status = "product_id_boundary"
            eligible = True
        elif asset_variant == expected_variant:
            variant_status = "matched"
            eligible = True
        elif asset_variant:
            variant_status = "mismatch"
            eligible = False
        elif self._text_matches_expected(asset, expected_variant):
            variant_status = "matched_from_label"
            eligible = True
        else:
            variant_status = "unverified"
            eligible = False

        if asset.review_status != "approved":
            eligible = False
            evidence.append(f"review_status:{asset.review_status}")
        return AssetClassification(
            asset_id=asset.id,
            contract_type=contract_type,
            family=family,
            eligible=eligible,
            variant_key=asset_variant,
            expected_variant_key=expected_variant,
            variant_status=variant_status,
            evidence=evidence,
        )

    def _contract_type(self, asset: models.ProductAsset) -> str:
        direct = DIRECT_TYPE_MAP.get((asset.asset_type or "").lower())
        text = self._asset_text(asset)
        for contract_type, keywords in KEYWORD_RULES:
            if any(keyword in text for keyword in keywords):
                return contract_type
        if direct:
            return direct
        if (asset.mime_type or "").startswith("video/") or (asset.extension or "").lower() in {".mp4", ".mov", ".webm"}:
            return "use_video_reference"
        return "unknown"

    @staticmethod
    def _asset_text(asset: models.ProductAsset) -> str:
        return " ".join(
            str(value or "")
            for value in [
                asset.asset_type,
                asset.asset_role,
                asset.manual_label,
                asset.filename,
                asset.source_ref,
                asset.review_notes,
                asset.metadata_json,
            ]
        ).lower()

    def _text_matches_expected(self, asset: models.ProductAsset, expected_variant: str) -> bool:
        tokens = [token for token in expected_variant.split("-") if len(token) >= 3]
        text_key = normalize_key(self._asset_text(asset)) or ""
        return bool(tokens) and all(token in text_key for token in tokens)
