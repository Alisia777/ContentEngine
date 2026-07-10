from __future__ import annotations

import base64
import json
import mimetypes
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app import models
from app.assets import ProductAssetStorage
from app.config import get_settings
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

PROFILE_ACTION_LABELS = {
    "food_snack": "пробует продукт",
    "cosmetic": "наносит продукт",
    "apparel": "примеряет продукт",
    "household": "демонстрирует работу продукта",
    "general": "показывает реальное применение продукта",
}


@dataclass(frozen=True)
class ProductImageUpload:
    slot: str
    filename: str
    content: bytes
    contract_type: str
    primary: bool = False


class ProductUGCRecipeService:
    """Builds the official Runway Product UGC request behind local quality gates."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.classifier = ProductAssetClassifier()
        self._gate_rows: list[tuple[str, str, str]] = []

    def create_draft(
        self,
        *,
        product_id: int,
        variant_key: str | None,
        character_filename: str,
        character_content: bytes,
        existing_asset_ids: list[int] | None = None,
        primary_asset_id: int | None = None,
        product_uploads: list[ProductImageUpload] | None = None,
        product_info: str | None = None,
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
        exact_variant_confirmed: bool = False,
    ) -> models.ProductUGCRecipeDraft:
        product = self.db.get(models.Product, product_id)
        if not product:
            raise RunwayRecipeError(f"Product {product_id} not found.")
        self.validate_image(character_filename, character_content, label="Фото блогера")
        uploads = list(product_uploads or [])
        for upload in uploads:
            self.validate_image(upload.filename, upload.content, label=f"Фото товара: {upload.slot}")

        expected_variant = normalize_key(variant_key) or product_variant_key(product)
        assets = self._selected_existing_assets(product.id, existing_asset_ids or [])
        storage = ProductAssetStorage(self.db)
        for upload in uploads:
            asset = storage.upload_file(
                product.id,
                filename=upload.filename,
                content=upload.content,
                asset_type=upload.contract_type,
                manual_label=f"Product UGC · {upload.slot}",
                is_primary_reference=upload.primary,
            )
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
        }
        rendered_product_info = (product_info or "").strip() or self.default_product_info(product, expected_variant)
        user_concept = self.build_user_concept(product, creative_inputs, expected_variant, language=language)
        character_path = self._save_character_image(character_filename, character_content)

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
            sku=product.sku,
            variant_key=expected_variant,
            status=status,
            recipe_version=RECIPE_VERSION,
            platform=platform,
            language=language,
            character_image_path=character_path.as_posix(),
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
        draft.provider_payload_preview_json = self._payload_preview(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

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
            publishing_readiness=draft.publishing_readiness,
        )

    def provider_request(self, draft: models.ProductUGCRecipeDraft) -> ProductUGCRecipeRequest:
        if draft.status != "ready_for_paid_preflight" or draft.blockers_json:
            raise RunwayRecipeError("Product UGC draft is blocked; fix every preflight gate before a provider call.")
        character_path = Path(draft.character_image_path)
        product_asset = self.db.get(models.ProductAsset, draft.primary_product_asset_id)
        if not character_path.exists() or not product_asset:
            raise RunwayRecipeError("Recipe media is missing.")
        return ProductUGCRecipeRequest(
            version=draft.recipe_version,
            character_image=RecipeImageInput(uri=self._asset_uri(character_path.as_posix(), "local")),
            product_image=RecipeImageInput(uri=self._asset_uri(product_asset.source_ref, product_asset.source_type)),
            product_info=draft.product_info,
            user_concept=draft.user_concept,
            duration=draft.duration_seconds,
            ratio=draft.ratio,
            audio=draft.audio_enabled,
        )

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
        variants_ok = bool(expected_variant) and all(
            item.variant_status in {"matched", "matched_from_label"} for item in classified if item.family not in {"style", "lifestyle"}
        )
        self._gate(blockers, "exact_variant", variants_ok, "Один exact variant", f"Variant: {expected_variant or 'не указан'}.")
        self._gate(blockers, "variant_confirmation", exact_variant_confirmed, "Подтверждение SKU", "Оператор сверил все фото с одним SKU/вариантом.")
        self._gate(blockers, "primary_product_image", primary is not None, "Главное product image", "Один front/primary reference должен быть выбран.")
        primary_classification = self.classifier.classify(primary, expected_variant_key=expected_variant) if primary else None
        primary_is_front = bool(
            primary_classification
            and primary_classification.contract_type in {"front_packshot", "front_view"}
            and primary_classification.eligible
        )
        self._gate(blockers, "primary_is_front", primary_is_front, "Главное фото — front", "В Runway уходит только подтверждённый главный вид товара.")
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
        self._gate(blockers, "likeness_consent", likeness_consent, "Согласие на образ блогера", "Есть право использовать лицо и образ человека.")

        brief_ok = all(
            str(creative_inputs.get(key) or "").strip()
            for key in ["task", "creator_profile", "setting", "hook", "product_action", "proof_moment", "cta"]
        )
        if audio:
            brief_ok = brief_ok and bool(str(creative_inputs.get("spoken_message") or "").strip())
        self._gate(blockers, "creative_brief", brief_ok, "Задание заполнено", "Хук, действие, proof, реплика и CTA не должны быть пустыми.")
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
        keywords = {
            "food_snack": ("проб", "куса", "ест ", "съед", "вкус", "разрез", "открыва", "bite", "taste", "eat"),
            "cosmetic": ("нанос", "апплик", "свотч", "на губ", "на кож", "apply", "swatch"),
            "apparel": ("пример", "надева", "носит", "посадк", "try on", "wear"),
            "household": ("примен", "использ", "включ", "работ", "очища", "use", "operate"),
            "general": ("примен", "использ", "демонстрирует работу", "включ", "use", "operate"),
        }
        return any(token in normalized for token in keywords[profile])

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
