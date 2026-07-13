from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Iterator, Mapping
from uuid import uuid4

from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import MediaArtifactError
from app.media_storage.factory import get_storage_backends
from app.media_storage.service import MediaArtifactService
from app.runway_recipes.errors import RunwayRecipeError


MAX_RECIPE_INPUT_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class MaterializedRecipeInputs:
    character_path: Path | None
    product_path: Path | None


class ProductUGCRecipeInputMaterializer:
    """Materialize tenant-owned immutable inputs for one initial provider submit."""

    def __init__(
        self,
        db: Session,
        *,
        backends: Mapping[str, StorageBackend] | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.backends = dict(backends) if backends is not None else None

    @contextmanager
    def materialize(
        self,
        draft: models.ProductUGCRecipeDraft,
        *,
        organization_id: int,
        generation_job_id: int,
    ) -> Iterator[MaterializedRecipeInputs]:
        product = self.db.get(models.Product, draft.product_id)
        product_asset = (
            self.db.get(models.ProductAsset, draft.primary_product_asset_id)
            if draft.primary_product_asset_id is not None
            else None
        )
        if product is None:
            raise RunwayRecipeError("Recipe product is missing.")

        character_artifact_id = draft.character_media_artifact_id
        product_artifact_id = product_asset.media_artifact_id if product_asset else None
        has_any_artifact = bool(character_artifact_id or product_artifact_id)
        has_both_artifacts = bool(character_artifact_id and product_artifact_id)
        production = self.settings.runtime_profile == "production"
        legacy_unscoped = (
            not production
            and not has_any_artifact
            and product.organization_id is None
        )
        if product.organization_id != int(organization_id) and not legacy_unscoped:
            raise RunwayRecipeError("Recipe product is outside the generation organization.")
        if not production and not has_any_artifact:
            # Preserve legacy development/test behavior, including historical
            # fixtures whose provider request is supplied by a test adapter.
            yield MaterializedRecipeInputs(character_path=None, product_path=None)
            return
        if product_asset is None or product_asset.product_id != draft.product_id:
            raise RunwayRecipeError("Recipe product reference is missing or outside the product scope.")
        if (production or has_any_artifact) and not has_both_artifacts:
            raise RunwayRecipeError(
                "Both creator and product inputs must be durable private artifacts before paid generation."
            )

        backends = self.backends if self.backends is not None else get_storage_backends()
        service = MediaArtifactService(self.db, backends)
        try:
            character_artifact, character_bytes = service.read_worker_input(
                int(character_artifact_id),
                organization_id=organization_id,
                product_id=draft.product_id,
                expected_kind="creator_reference",
                max_size_bytes=MAX_RECIPE_INPUT_BYTES,
            )
            product_artifact, product_bytes = service.read_worker_input(
                int(product_artifact_id),
                organization_id=organization_id,
                product_id=draft.product_id,
                expected_kind="product_reference",
                max_size_bytes=MAX_RECIPE_INPUT_BYTES,
            )
        except MediaArtifactError as exc:
            raise RunwayRecipeError("Private recipe input failed ownership or integrity checks.") from exc
        if production and (
            character_artifact.backend_name == "local"
            or product_artifact.backend_name == "local"
        ):
            raise RunwayRecipeError("Local recipe input storage is forbidden in production.")

        scratch = (
            self.settings.media_root
            / "worker_scratch"
            / f"product_ugc_job_{int(generation_job_id)}_{uuid4().hex}"
        )
        try:
            scratch.mkdir(parents=True, exist_ok=False)
            character_path = scratch / self._scratch_name(
                "creator",
                character_artifact.original_filename,
                character_artifact.mime_type,
            )
            product_path = scratch / self._scratch_name(
                "product",
                product_artifact.original_filename,
                product_artifact.mime_type,
            )
            character_path.write_bytes(character_bytes)
            product_path.write_bytes(product_bytes)
            yield MaterializedRecipeInputs(
                character_path=character_path,
                product_path=product_path,
            )
        finally:
            if scratch.exists():
                shutil.rmtree(scratch)

    @staticmethod
    def _scratch_name(prefix: str, original_filename: str | None, mime_type: str) -> str:
        suffix = Path(original_filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }.get(str(mime_type).lower(), ".img")
        return f"{prefix}{suffix}"
