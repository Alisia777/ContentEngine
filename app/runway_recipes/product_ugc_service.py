from __future__ import annotations

import base64
import json
import mimetypes
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from app import models
from app.assets import ProductAssetStorage
from app.assets.errors import AssetKitDataError
from app.config import get_settings
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import MediaArtifactError, StorageError
from app.media_storage.factory import get_storage_backends
from app.media_storage.service import MediaArtifactService
from app.product_asset_contract.asset_classifier import ProductAssetClassifier, normalize_key
from app.product_asset_contract.reference_requirement_service import product_profile, product_variant_key
from app.runway_recipes.errors import RunwayRecipeError
from app.runway_recipes.types import (
    ProductUGCRecipeDraftOutput,
    ProductUGCRecipeRequest,
    RecipeGate,
    RecipeImageInput,
)


ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024
VERTICAL_RATIOS = {"720:1280", "1080:1920"}
RECIPE_VERSION = "2026-06"

BASELINE_REFERENCE_GROUPS = (
    {"front_packshot", "front_view"},
    {"angled_wrapper", "angled_product", "back_view"},
    {"wrapper_in_hand", "wrapper_on_table", "product_in_hand", "product_on_surface", "scale_context"},
)

PROOF_TYPES = {
    "food_snack": {"whole_unwrapped_product", "cutaway_product", "bitten_product", "wrapper_plus_product"},
    "cosmetic": {"application_demo", "application_context", "application_area", "texture_swatch"},
    "apparel": {"on_body", "movement_reference"},
    "household": {"application_demo", "application_context", "result_context", "use_video_reference"},
    "general": {"application_demo", "application_context", "result_context", "use_video_reference"},
}

PROVIDER_PRODUCT_IMAGE_TYPES = {
    "food_snack": {"front_packshot", "front_view", "wrapper_plus_product", "product_on_surface"},
    "cosmetic": {"front_packshot", "front_view", "application_context", "application_demo", "product_on_surface"},
    "apparel": {"front_packshot", "front_view", "on_body", "product_on_surface"},
    "household": {"front_packshot", "front_view", "application_context", "result_context", "product_on_surface"},
    "general": {"front_packshot", "front_view", "application_context", "result_context", "product_on_surface"},
}

PROFILE_ACTION_LABELS = {
    "food_snack": "пробует продукт",
    "cosmetic": "наносит продукт",
    "apparel": "примеряет продукт",
    "household": "демонстрирует работу продукта",
    "general": "показывает реальное применение продукта",
}

FORM_PROOF_REFERENCE_OPTIONS = {
    "food_snack": {
        "cutaway_product": "Разрез / реальная начинка (без укуса)",
        "whole_unwrapped_product": "Целый продукт без упаковки",
        "bitten_product": "Надкушенный продукт для bite-сцены",
        "wrapper_plus_product": "Точная упаковка и продукт вместе",
    },
    "cosmetic": {
        "application_demo": "Нанесение точного продукта",
        "texture_swatch": "Реальный свотч / текстура",
        "application_context": "Продукт в реальном применении",
    },
    "apparel": {
        "on_body": "Товар на человеке",
        "movement_reference": "Посадка в движении",
    },
    "household": {
        "application_demo": "Реальное применение",
        "application_context": "Контекст использования",
        "result_context": "Проверяемый результат",
    },
    "general": {
        "application_demo": "Реальное применение",
        "application_context": "Контекст использования",
        "result_context": "Проверяемый результат",
    },
}

SUPPORTED_PRODUCT_UGC_PLATFORMS = {"Instagram Reels", "TikTok", "YouTube Shorts", "Wibes"}


@dataclass(frozen=True)
class ProductImageUpload:
    slot: str
    filename: str
    content: bytes
    contract_type: str
    primary: bool = False


class ProductUGCRecipeService:
    """Builds the official Runway Product UGC request behind local quality gates."""

    def __init__(
        self,
        db: Session,
        *,
        storage_backends: Mapping[str, StorageBackend] | None = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.classifier = ProductAssetClassifier()
        self._gate_rows: list[tuple[str, str, str]] = []
        self.storage_backends = (
            dict(storage_backends) if storage_backends is not None else None
        )

    def create_draft(
        self,
        *,
        product_id: int,
        variant_key: str | None,
        character_filename: str,
        character_content: bytes,
        created_by_user_profile_id: int | None = None,
        existing_asset_ids: list[int] | None = None,
        primary_asset_id: int | None = None,
        product_uploads: list[ProductImageUpload] | None = None,
        product_info: str | None = None,
        required_packaging_tokens: list[str] | str | None = None,
        task: str,
        creator_profile: str,
        setting: str,
        hook: str,
        product_action: str,
        proof_moment: str,
        spoken_message: str,
        cta: str,
        forbidden_visuals: str = "",
        interaction_mode: str = "presentation",
        platform: str = "Instagram Reels",
        language: str = "ru",
        duration: int = 15,
        ratio: str = "720:1280",
        audio: bool = True,
        likeness_consent: bool = False,
        character_product_free_confirmed: bool = False,
        exact_variant_confirmed: bool = False,
    ) -> models.ProductUGCRecipeDraft:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise RunwayRecipeError(f"Product {product_id} not found.")
        self.validate_image(character_filename, character_content, label="Фото блогера")
        uploads = list(product_uploads or [])
        for upload in uploads:
            self.validate_image(upload.filename, upload.content, label=f"Фото товара: {upload.slot}")

        catalog_variant = normalize_key(product_variant_key(product))
        requested_variant = normalize_key(variant_key)
        if catalog_variant and requested_variant and requested_variant != catalog_variant:
            raise RunwayRecipeError(
                f"Вариант формы «{requested_variant}» не совпадает с карточкой SKU «{catalog_variant}»."
            )
        expected_variant = catalog_variant or requested_variant
        if not expected_variant:
            raise RunwayRecipeError("Укажите точный вариант / вкус / цвет / модель товара.")
        if interaction_mode not in {"presentation", "use"}:
            raise RunwayRecipeError("Режим ролика должен быть presentation или use.")
        if platform not in SUPPORTED_PRODUCT_UGC_PLATFORMS:
            raise RunwayRecipeError("Выберите поддерживаемую площадку Product UGC.")
        assets = self._selected_existing_assets(product.id, existing_asset_ids or [])
        storage = ProductAssetStorage(self.db, backends=self.storage_backends)
        for upload in uploads:
            try:
                asset = storage.upload_file(
                    product.id,
                    filename=upload.filename,
                    content=upload.content,
                    asset_type=upload.contract_type,
                    manual_label=f"Product UGC · {upload.slot}",
                    is_primary_reference=upload.primary,
                    created_by_user_profile_id=created_by_user_profile_id,
                )
            except AssetKitDataError as exc:
                raise RunwayRecipeError(str(exc)) from exc
            asset = storage.update_asset(
                asset.id,
                review_status="approved" if exact_variant_confirmed else "pending",
                review_notes="Exact SKU/variant confirmed in Product UGC operator form." if exact_variant_confirmed else None,
                variant_key=expected_variant,
                contract_type=upload.contract_type,
                is_primary_reference=upload.primary,
            )
            assets.append(asset)

        unique_assets = {asset.id: asset for asset in assets}
        assets = list(unique_assets.values())
        profile = product_profile(product)
        primary = self._primary_asset(assets, primary_asset_id)
        if not primary:
            raise RunwayRecipeError("Выберите или загрузите главный front product image.")
        packaging_tokens = self._packaging_tokens(required_packaging_tokens)
        if packaging_tokens:
            primary_metadata = dict(primary.metadata_json or {})
            primary_metadata["required_packaging_tokens"] = packaging_tokens
            primary_metadata["packaging_text_source"] = "operator_confirmed"
            primary.metadata_json = primary_metadata
        creative_inputs = {
            "task": task.strip(),
            "creator_profile": creator_profile.strip(),
            "setting": setting.strip(),
            "hook": hook.strip(),
            "product_action": product_action.strip(),
            "proof_moment": proof_moment.strip(),
            "spoken_message": spoken_message.strip(),
            "cta": cta.strip(),
            "forbidden_visuals": forbidden_visuals.strip(),
            "interaction_mode": interaction_mode,
            "product_profile": profile,
            "profile_action": PROFILE_ACTION_LABELS[profile],
            "character_product_free_confirmed": character_product_free_confirmed,
            "required_packaging_tokens": packaging_tokens,
        }
        rendered_product_info = (product_info or "").strip() or self.default_product_info(product, expected_variant)
        user_concept = self.build_user_concept(product, creative_inputs, expected_variant, language=language)
        character_path, character_artifact = self._store_character_image(
            product=product,
            created_by_user_profile_id=created_by_user_profile_id,
            filename=character_filename,
            content=character_content,
        )

        gates, blockers, warnings = self._preflight(
            product=product,
            assets=assets,
            primary=primary,
            expected_variant=expected_variant,
            profile=profile,
            creative_inputs=creative_inputs,
            product_info=rendered_product_info,
            user_concept=user_concept,
            duration=duration,
            ratio=ratio,
            audio=audio,
            likeness_consent=likeness_consent,
            exact_variant_confirmed=exact_variant_confirmed,
        )
        status = "ready_for_paid_preflight" if not blockers else "blocked"
        draft = models.ProductUGCRecipeDraft(
            product_id=product.id,
            created_by_user_profile_id=created_by_user_profile_id,
            sku=product.sku,
            variant_key=expected_variant,
            status=status,
            recipe_version=RECIPE_VERSION,
            platform=platform,
            language=language,
            character_image_path=character_path.as_posix() if character_path else None,
            character_media_artifact_id=(
                character_artifact.id if character_artifact else None
            ),
            character_image_filename=ProductAssetStorage.safe_filename(character_filename),
            likeness_consent=likeness_consent,
            exact_variant_confirmed=exact_variant_confirmed,
            product_asset_ids_json=[asset.id for asset in assets],
            primary_product_asset_id=primary.id if primary else None,
            product_info=rendered_product_info[:2500],
            user_concept=user_concept[:3500],
            creative_inputs_json={**creative_inputs, "gates": [gate.model_dump(mode="json") for gate in gates]},
            duration_seconds=duration,
            ratio=ratio,
            audio_enabled=audio,
            estimated_credits=self.estimate_credits(duration, ratio),
            provider_payload_preview_json={},
            blockers_json=blockers,
            warnings_json=warnings,
        )
        self.db.add(draft)
        self.db.flush()
        if character_artifact is not None:
            character_artifact.product_ugc_recipe_draft_id = draft.id
        draft.provider_payload_preview_json = self._payload_preview(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    @staticmethod
    def _packaging_tokens(value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        raw_items = (
            re.split(r"[,;\n]+", value)
            if isinstance(value, str)
            else list(value)
        )
        tokens: list[str] = []
        for raw in raw_items:
            token = re.sub(r"\s+", " ", str(raw or "").strip())
            if not token:
                continue
            if len(token) < 2 or len(token) > 80:
                raise RunwayRecipeError(
                    "Каждая обязательная надпись упаковки должна содержать 2–80 символов."
                )
            if token.casefold() not in {item.casefold() for item in tokens}:
                tokens.append(token)
        if len(tokens) > 12:
            raise RunwayRecipeError("Укажите не более 12 ключевых надписей упаковки.")
        return tokens

    def get(self, draft_id: int) -> models.ProductUGCRecipeDraft:
        draft = self.db.get(models.ProductUGCRecipeDraft, draft_id)
        if not draft:
            raise RunwayRecipeError(f"ProductUGCRecipeDraft {draft_id} not found.")
        return draft

    def output(self, draft: models.ProductUGCRecipeDraft) -> ProductUGCRecipeDraftOutput:
        inputs = draft.creative_inputs_json or {}
        gates = [RecipeGate.model_validate(item) for item in inputs.get("gates", [])]
        return ProductUGCRecipeDraftOutput(
            id=draft.id,
            product_id=draft.product_id,
            sku=draft.sku,
            variant_key=draft.variant_key,
            status=draft.status,
            recipe_version=draft.recipe_version,
            platform=draft.platform,
            language=draft.language,
            character_image_filename=draft.character_image_filename,
            likeness_consent=draft.likeness_consent,
            exact_variant_confirmed=draft.exact_variant_confirmed,
            product_asset_ids=draft.product_asset_ids_json or [],
            primary_product_asset_id=draft.primary_product_asset_id,
            product_info=draft.product_info,
            user_concept=draft.user_concept,
            creative_inputs={key: value for key, value in inputs.items() if key != "gates"},
            duration_seconds=draft.duration_seconds,
            ratio=draft.ratio,
            audio_enabled=draft.audio_enabled,
            estimated_credits=draft.estimated_credits,
            payload_preview=draft.provider_payload_preview_json or {},
            gates=gates,
            blockers=draft.blockers_json or [],
            warnings=draft.warnings_json or [],
            provider_task_id=draft.provider_task_id,
            provider_status=draft.provider_status,
            local_output_paths=draft.local_output_paths_json or [],
            generation_report_path=draft.generation_report_path,
            human_review_status=draft.human_review_status,
            human_review_notes=draft.human_review_notes,
            publishing_readiness=draft.publishing_readiness,
        )

    def provider_request(
        self,
        draft: models.ProductUGCRecipeDraft,
        *,
        materialized_character_path: Path | None = None,
        materialized_product_path: Path | None = None,
    ) -> ProductUGCRecipeRequest:
        draft = self.refresh_preflight(draft)
        if draft.status not in {"ready_for_paid_preflight", "provider_launching"} or draft.blockers_json:
            raise RunwayRecipeError("Product UGC draft is blocked; fix every preflight gate before a provider call.")
        product_asset = self.db.get(models.ProductAsset, draft.primary_product_asset_id)
        if not product_asset:
            raise RunwayRecipeError("Recipe media is missing.")
        if materialized_character_path is not None:
            character_uri = self._asset_uri(
                materialized_character_path.as_posix(),
                "local",
            )
        else:
            if draft.character_media_artifact_id is not None:
                raise RunwayRecipeError(
                    "Private creator input must be materialized by the durable worker."
                )
            if not draft.character_image_path:
                raise RunwayRecipeError("Recipe creator image is missing.")
            character_uri = self._asset_uri(draft.character_image_path, "local")
        if materialized_product_path is not None:
            product_uri = self._asset_uri(materialized_product_path.as_posix(), "local")
        else:
            if product_asset.media_artifact_id is not None or product_asset.source_type == "media_artifact":
                raise RunwayRecipeError(
                    "Private product input must be materialized by the durable worker."
                )
            product_uri = self._asset_uri(product_asset.source_ref, product_asset.source_type)
        return ProductUGCRecipeRequest(
            version=draft.recipe_version,
            character_image=RecipeImageInput(uri=character_uri),
            product_image=RecipeImageInput(uri=product_uri),
            product_info=draft.product_info,
            user_concept=draft.user_concept,
            duration=draft.duration_seconds,
            ratio=draft.ratio,
            audio=draft.audio_enabled,
        )

    def refresh_preflight(self, draft: models.ProductUGCRecipeDraft) -> models.ProductUGCRecipeDraft:
        """Re-run current gates before any provider reservation or paid request."""
        product = self.db.get(models.Product, draft.product_id)
        if not product:
            raise RunwayRecipeError(f"Product {draft.product_id} not found.")
        assets = self._selected_existing_assets(product.id, draft.product_asset_ids_json or [])
        primary = self._primary_asset(assets, draft.primary_product_asset_id)
        creative_inputs = dict(draft.creative_inputs_json or {})
        creative_inputs.pop("gates", None)
        gates, blockers, warnings = self._preflight(
            product=product,
            assets=assets,
            primary=primary,
            expected_variant=normalize_key(draft.variant_key),
            profile=product_profile(product),
            creative_inputs=creative_inputs,
            product_info=draft.product_info,
            user_concept=draft.user_concept,
            duration=draft.duration_seconds,
            ratio=draft.ratio,
            audio=draft.audio_enabled,
            likeness_consent=draft.likeness_consent,
            exact_variant_confirmed=draft.exact_variant_confirmed,
        )
        draft.creative_inputs_json = {
            **creative_inputs,
            "gates": [gate.model_dump(mode="json") for gate in gates],
        }
        draft.blockers_json = blockers
        draft.warnings_json = warnings
        if blockers:
            draft.status = "blocked"
        elif draft.status == "blocked":
            draft.status = "ready_for_paid_preflight"
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def record_human_review(
        self,
        draft_id: int,
        *,
        status: str,
        notes: str,
    ) -> models.ProductUGCRecipeDraft:
        draft = self.get(draft_id)
        allowed = {"approved", "needs_regeneration", "rejected"}
        if status not in allowed:
            raise RunwayRecipeError(f"Unsupported Product UGC review status: {status}.")
        output_paths = [Path(path) for path in (draft.local_output_paths_json or [])]
        if not output_paths or any(not path.exists() or path.stat().st_size <= 0 for path in output_paths):
            raise RunwayRecipeError("Human review requires a downloaded, non-empty Product UGC output.")
        if not notes.strip():
            raise RunwayRecipeError("Human review notes are required.")
        draft.human_review_status = status
        draft.human_review_notes = notes.strip()
        draft.publishing_readiness = "ready_for_package" if status == "approved" else "blocked"
        draft.status = "approved" if status == "approved" else status
        self.db.commit()
        self.db.refresh(draft)
        return draft

    @staticmethod
    def validate_image(filename: str, content: bytes, *, label: str) -> None:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in ALLOWED_IMAGE_SUFFIXES:
            raise RunwayRecipeError(f"{label}: разрешены JPG, PNG и WEBP.")
        if not content:
            raise RunwayRecipeError(f"{label}: файл пустой.")
        if len(content) > MAX_IMAGE_BYTES:
            raise RunwayRecipeError(f"{label}: файл больше 15 МБ.")
        dimensions = ProductUGCRecipeService._image_dimensions(content)
        if not dimensions:
            raise RunwayRecipeError(f"{label}: файл не распознан как корректное изображение.")
        width, height = dimensions
        ratio = width / height
        if ratio < 0.4 or ratio > 4:
            raise RunwayRecipeError(f"{label}: соотношение сторон должно быть от 0.4 до 4.")

    @staticmethod
    def estimate_credits(duration: int, ratio: str) -> int:
        base, per_second = (208, 40) if ratio == "1080:1920" else (192, 36)
        return base + max(0, duration - 4) * per_second

    @staticmethod
    def default_product_info(product: models.Product, variant_key: str | None) -> str:
        attributes = product.attributes_json or {}
        lines = [
            f"{product.brand} — {product.title}",
            f"SKU: {product.sku}",
            f"Категория: {product.category or 'не указана'}",
            f"Точный вариант: {variant_key or 'единственный вариант SKU'}",
        ]
        if product.description:
            lines.append(f"Описание: {product.description.strip()}")
        if attributes:
            lines.append(f"Характеристики: {ProductUGCRecipeService._compact_value(attributes)}")
        if product.benefits_json:
            lines.append(f"Подтверждённые преимущества: {ProductUGCRecipeService._compact_value(product.benefits_json)}")
        if product.restrictions_json:
            lines.append(f"Ограничения и запрещённые обещания: {ProductUGCRecipeService._compact_value(product.restrictions_json)}")
        lines.append("Внешний вид, цвет, геометрия, логотип и маркировка должны совпадать с главным product image.")
        return "\n".join(lines)[:2500]

    @staticmethod
    def build_user_concept(
        product: models.Product,
        inputs: dict[str, Any],
        variant_key: str | None,
        *,
        language: str,
    ) -> str:
        language_label = "русском" if language == "ru" else language
        lines = [
            f"Вертикальный нативный UGC-ролик для {product.title}, точный SKU {product.sku}, вариант {variant_key or 'default'}.",
            f"Задача: {inputs['task']}",
            f"Блогер: {inputs['creator_profile']}",
            f"Ситуация: {inputs['setting']}",
            f"Хук: {inputs['hook']}",
            f"Действие с продуктом: {inputs['product_action']}",
            f"Proof moment: {inputs['proof_moment']}",
            f"Реплика на {language_label} языке: {inputs['spoken_message']}",
            f"CTA: {inputs['cta']}",
            "Съёмка выглядит как живой телефонный UGC: естественная мимика, реальные руки, правдоподобный масштаб продукта, плавное непрерывное действие.",
            "Использовать только точный товар с product image. Не менять форму, размер, цвет, материал, упаковку, этикетку, логотип или вариант продукта.",
            "Не генерировать встроенные субтитры, ценники и новый текст на упаковке; титры добавляются отдельно после рендера.",
        ]
        if inputs["product_profile"] == "food_snack":
            lines.append("Если продукт пробуют: сначала физически открыть упаковку; нельзя кусать или есть продукт через упаковку; внутренняя текстура должна совпадать с proof reference.")
        elif inputs["product_profile"] == "cosmetic":
            lines.append("Аппликатор, дозатор, оттенок и способ нанесения должны физически совпадать с proof reference; не подменять продукт другим флаконом.")
        elif inputs["product_profile"] == "apparel":
            lines.append("Посадка, длина, материал, швы и принт должны совпадать с референсами; не менять предмет одежды между кадрами.")
        elif inputs["product_profile"] in {"household", "general"}:
            lines.append("Показывать только реальный и безопасный способ применения из proof reference; не изобретать функции продукта.")
        if inputs.get("forbidden_visuals"):
            lines.append(f"Дополнительно запрещено: {inputs['forbidden_visuals']}")
        return "\n".join(lines)[:3500]

    def _preflight(
        self,
        *,
        product: models.Product,
        assets: list[models.ProductAsset],
        primary: models.ProductAsset | None,
        expected_variant: str | None,
        profile: str,
        creative_inputs: dict[str, Any],
        product_info: str,
        user_concept: str,
        duration: int,
        ratio: str,
        audio: bool,
        likeness_consent: bool,
        exact_variant_confirmed: bool,
    ) -> tuple[list[RecipeGate], list[str], list[str]]:
        self._gate_rows = []
        blockers: list[str] = []
        warnings: list[str] = [
            "Runway Product UGC receives one primary productImage; the other approved references are ContentEngine identity and review evidence.",
            "Every provider output still requires human review before publishing.",
        ]
        count_ok = 3 <= len(assets) <= 4
        self._gate(blockers, "reference_count", count_ok, "3–4 фото одного товара", f"Выбрано: {len(assets)}.")

        classified = [self.classifier.classify(asset, expected_variant_key=expected_variant) for asset in assets]
        eligible_types = {item.contract_type for item in classified if item.eligible}
        baseline_ok = all(eligible_types.intersection(group) for group in BASELINE_REFERENCE_GROUPS)
        self._gate(
            blockers,
            "reference_roles",
            baseline_ok,
            "Роли референсов",
            "Нужны главный вид, второй ракурс и масштаб/товар в руке.",
        )
        approvals_ok = all(asset.review_status == "approved" for asset in assets)
        self._gate(blockers, "approved_assets", approvals_ok, "Фото подтверждены", "Каждое фото должно быть approved.")
        catalog_variant = normalize_key(product_variant_key(product))
        variants_ok = bool(expected_variant) and (not catalog_variant or expected_variant == catalog_variant) and all(
            item.variant_status in {"matched", "matched_from_label"} for item in classified if item.family not in {"style", "lifestyle"}
        )
        self._gate(blockers, "exact_variant", variants_ok, "Один exact variant", f"Variant: {expected_variant or 'не указан'}.")
        self._gate(blockers, "variant_confirmation", exact_variant_confirmed, "Подтверждение SKU", "Оператор сверил все фото с одним SKU/вариантом.")
        self._gate(
            blockers,
            "primary_product_image",
            primary is not None,
            "Product image для Runway",
            "Выберите одно точное фото, которое лучше всего показывает товар для заданного действия.",
        )
        primary_classification = self.classifier.classify(primary, expected_variant_key=expected_variant) if primary else None
        primary_is_provider_ready = bool(
            primary_classification
            and primary_classification.contract_type in PROVIDER_PRODUCT_IMAGE_TYPES[profile]
            and primary_classification.eligible
        )
        self._gate(
            blockers,
            "provider_product_image",
            primary_is_provider_ready,
            "Product image подходит для recipe",
            "Runway получает точный front или reference-safe product/use composite; отдельный front всё равно обязателен в identity set.",
        )
        signatures = [asset.checksum or asset.source_ref for asset in assets]
        unique_refs = len(signatures) == len(set(signatures))
        self._gate(blockers, "unique_references", unique_refs, "Разные ракурсы", "Один файл нельзя загрузить несколько раз под разными ролями.")

        use_requested = creative_inputs.get("interaction_mode") == "use" or self._action_implies_use(
            profile,
            f"{creative_inputs.get('product_action', '')} {creative_inputs.get('proof_moment', '')}",
        )
        proof_ok = not use_requested or bool(eligible_types.intersection(PROOF_TYPES[profile]))
        proof_detail = (
            f"Для действия «{PROFILE_ACTION_LABELS[profile]}» нужен четвёртый category-appropriate proof reference."
            if use_requested
            else "Для презентации достаточно трёх identity/scale references."
        )
        self._gate(blockers, "use_proof", proof_ok, "Доказательство применения", proof_detail)
        if profile == "food_snack":
            bite_requested = self._food_action_requires_bite(
                f"{creative_inputs.get('product_action', '')} {creative_inputs.get('proof_moment', '')}"
            )
            bite_reference_ok = not bite_requested or "bitten_product" in eligible_types
            self._gate(
                blockers,
                "food_bite_reference",
                bite_reference_ok,
                "Укус только по отдельному референсу",
                "Укус, жевание и продукт у рта разрешены только при approved фото надкушенного продукта.",
            )
        self._gate(blockers, "likeness_consent", likeness_consent, "Согласие на образ блогера", "Есть право использовать лицо и образ человека.")
        self._gate(
            blockers,
            "character_reference_clean",
            bool(creative_inputs.get("character_product_free_confirmed")),
            "Character image без другого товара",
            "В character reference виден только человек и нейтральный контекст; чужая упаковка не может влиять на product identity.",
        )

        brief_ok = all(
            str(creative_inputs.get(key) or "").strip()
            for key in ["task", "creator_profile", "setting", "hook", "product_action", "proof_moment", "cta"]
        )
        if audio:
            brief_ok = brief_ok and bool(str(creative_inputs.get("spoken_message") or "").strip())
        self._gate(blockers, "creative_brief", brief_ok, "Задание заполнено", "Хук, действие, proof, реплика и CTA не должны быть пустыми.")
        safety_brief_ok = bool(
            str(creative_inputs.get("forbidden_visuals") or "").strip() or product.restrictions_json
        )
        self._gate(
            blockers,
            "safety_brief",
            safety_brief_ok,
            "Запреты зафиксированы",
            "Нужны запрещённые визуалы в ТЗ или ограничения в карточке товара.",
        )
        product_info_ok = 20 <= len(product_info) <= 2500
        concept_ok = 30 <= len(user_concept) <= 3500
        self._gate(blockers, "recipe_text_limits", product_info_ok and concept_ok, "Лимиты Runway", "productInfo ≤ 2500, userConcept ≤ 3500.")
        output_ok = 4 <= duration <= 15 and ratio in VERTICAL_RATIOS
        self._gate(blockers, "output_settings", output_ok, "Формат ролика", f"{duration} сек · {ratio} · audio={audio}.")

        gates = [
            RecipeGate(
                key=key,
                label=label,
                status="ready" if key not in blockers else "blocked",
                detail=detail,
            )
            for key, label, detail in self._gate_rows
        ]
        self._gate_rows = []
        return gates, blockers, warnings

    def _gate(self, blockers: list[str], key: str, ok: bool, label: str, detail: str) -> None:
        self._gate_rows.append((key, label, detail))
        if not ok:
            blockers.append(key)

    def _selected_existing_assets(self, product_id: int, asset_ids: list[int]) -> list[models.ProductAsset]:
        assets: list[models.ProductAsset] = []
        for asset_id in dict.fromkeys(asset_ids):
            asset = self.db.get(models.ProductAsset, asset_id)
            if not asset or asset.product_id != product_id:
                raise RunwayRecipeError(f"ProductAsset {asset_id} does not belong to Product {product_id}.")
            assets.append(asset)
        return assets

    @staticmethod
    def _primary_asset(assets: list[models.ProductAsset], primary_asset_id: int | None) -> models.ProductAsset | None:
        if primary_asset_id:
            explicit = next((asset for asset in assets if asset.id == primary_asset_id), None)
            if explicit:
                return explicit
        return next((asset for asset in assets if asset.is_primary_reference), None) or next(
            (
                asset
                for asset in assets
                if (asset.metadata_json or {}).get("contract_type") in {"front_packshot", "front_view"}
                or asset.asset_type in {"packshot", "front_packshot", "front_view"}
            ),
            None,
        )

    def _save_character_image(self, filename: str, content: bytes) -> Path:
        safe_name = ProductAssetStorage.safe_filename(filename)
        target_dir = self.settings.media_root / "recipe_inputs" / "characters"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{uuid4().hex}_{safe_name}"
        target.write_bytes(content)
        return target

    def _store_character_image(
        self,
        *,
        product: models.Product,
        created_by_user_profile_id: int | None,
        filename: str,
        content: bytes,
    ) -> tuple[Path | None, models.MediaArtifact | None]:
        durable = self.settings.runtime_profile == "production" or self.storage_backends is not None
        if not durable:
            return self._save_character_image(filename, content), None
        if product.organization_id is None or created_by_user_profile_id is None:
            raise RunwayRecipeError(
                "Durable creator-reference upload requires an organization and attributable user."
            )
        backends = (
            dict(self.storage_backends)
            if self.storage_backends is not None
            else get_storage_backends()
        )
        preferred = backends.get(str(self.settings.storage_backend))
        backend = preferred or (next(iter(backends.values())) if len(backends) == 1 else None)
        if backend is None:
            raise RunwayRecipeError("Private media storage backend is not configured.")
        if self.settings.runtime_profile == "production" and backend.name == "local":
            raise RunwayRecipeError("Local creator-reference storage is forbidden in production.")
        safe_name = ProductAssetStorage.safe_filename(filename)
        try:
            artifact = MediaArtifactService(self.db, backends).store_bytes(
                organization_id=product.organization_id,
                created_by_user_profile_id=created_by_user_profile_id,
                backend_name=backend.name,
                kind="creator_reference",
                content=content,
                mime_type=mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
                original_filename=safe_name,
                product_id=product.id,
                metadata={"source": "product_ugc_creator_upload"},
            )
        except (MediaArtifactError, StorageError) as exc:
            raise RunwayRecipeError("Creator reference could not be stored privately.") from exc
        return None, artifact

    @staticmethod
    def _payload_preview(draft: models.ProductUGCRecipeDraft) -> dict[str, Any]:
        return {
            "version": draft.recipe_version,
            "characterImage": {"uri": f"character-asset://draft/{draft.id}"},
            "productImage": {"uri": f"product-asset://{draft.primary_product_asset_id}"},
            "productInfo": draft.product_info,
            "userConcept": draft.user_concept,
            "duration": draft.duration_seconds,
            "ratio": draft.ratio,
            "audio": draft.audio_enabled,
        }

    @staticmethod
    def _asset_uri(source_ref: str, source_type: str) -> str:
        if source_type == "url":
            if not source_ref.lower().startswith("https://"):
                raise RunwayRecipeError("Runway recipe media URLs must use HTTPS.")
            return source_ref
        path = Path(source_ref)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists() or not path.is_file():
            raise RunwayRecipeError(f"Local recipe media is missing: {path.name}")
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _action_implies_use(profile: str, text: str) -> bool:
        normalized = text.casefold()
        normalized = re.sub(
            r"\bне\s+(?:проб[а-яёa-z-]*|кус[а-яёa-z-]*|ест[а-яёa-z-]*|съед[а-яёa-z-]*|разрез[а-яёa-z-]*|открыва[а-яёa-z-]*|нанос[а-яёa-z-]*|апплик[а-яёa-z-]*|пример[а-яёa-z-]*|надева[а-яёa-z-]*|носит[а-яёa-z-]*|примен[а-яёa-z-]*|использ[а-яёa-z-]*|включ[а-яёa-z-]*|очища[а-яёa-z-]*)",
            "",
            normalized,
        )
        keywords = {
            "food_snack": ("проб", "куса", "ест ", "съед", "вкус", "разрез", "открыва", "bite", "taste", "eat"),
            "cosmetic": ("нанос", "апплик", "свотч", "на губ", "на кож", "apply", "swatch"),
            "apparel": ("пример", "надева", "носит", "посадк", "try on", "wear"),
            "household": ("примен", "использ", "включ", "работ", "очища", "use", "operate"),
            "general": ("примен", "использ", "демонстрирует работу", "включ", "use", "operate"),
        }
        return any(token in normalized for token in keywords[profile])

    @staticmethod
    def _food_action_requires_bite(text: str) -> bool:
        normalized = text.casefold()
        normalized = re.sub(
            r"\bне\s+(?:надкус[а-яёa-z-]*|кус[а-яёa-z-]*|жев[а-яёa-z-]*|жу[а-яёa-z-]*|ест[а-яёa-z-]*|съед[а-яёa-z-]*|проб[а-яёa-z-]*|поднос[а-яёa-z-]*\s+(?:к|ко)\s+рту)",
            "",
            normalized,
        )
        return any(
            token in normalized
            for token in (
                "надкус",
                "куса",
                "укус",
                "жует",
                "жуёт",
                "ест ",
                "съед",
                "пробует",
                "у рта",
                "ко рту",
                "bite",
                "chew",
                "eats",
                "taste",
            )
        )

    @staticmethod
    def _image_dimensions(content: bytes) -> tuple[int, int] | None:
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
            width, height = struct.unpack(">II", content[16:24])
            return (width, height) if width and height else None
        if content.startswith(b"\xff\xd8"):
            index = 2
            while index + 9 < len(content):
                if content[index] != 0xFF:
                    index += 1
                    continue
                while index < len(content) and content[index] == 0xFF:
                    index += 1
                if index >= len(content):
                    break
                marker = content[index]
                index += 1
                if marker in {0xD8, 0xD9}:
                    continue
                if index + 2 > len(content):
                    break
                segment_length = int.from_bytes(content[index : index + 2], "big")
                if segment_length < 2 or index + segment_length > len(content):
                    break
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                    height = int.from_bytes(content[index + 3 : index + 5], "big")
                    width = int.from_bytes(content[index + 5 : index + 7], "big")
                    return (width, height) if width and height else None
                index += segment_length
            return None
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP" and len(content) >= 30:
            chunk = content[12:16]
            if chunk == b"VP8X":
                width = 1 + int.from_bytes(content[24:27], "little")
                height = 1 + int.from_bytes(content[27:30], "little")
                return width, height
            if chunk == b"VP8L" and len(content) >= 25 and content[20] == 0x2F:
                bits = int.from_bytes(content[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
            marker = content.find(b"\x9d\x01\x2a", 20)
            if marker >= 0 and marker + 7 <= len(content):
                width = int.from_bytes(content[marker + 3 : marker + 5], "little") & 0x3FFF
                height = int.from_bytes(content[marker + 5 : marker + 7], "little") & 0x3FFF
                return (width, height) if width and height else None
        return None

    @staticmethod
    def _compact_value(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:900]
