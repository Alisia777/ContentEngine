from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.intelligence.errors import ProviderConfigurationError
from app.runway_recipes.errors import RunwayRecipeError
from app.runway_recipes.product_ugc_service import ProductUGCRecipeService
from app.runway_recipes.provider import RunwayRecipeProvider
from app.runway_recipes.types import ProductUGCRecipeRunOutput


SUCCESS_STATUSES = {"SUCCEEDED", "SUCCESS", "COMPLETED", "COMPLETE", "DONE"}
FAILURE_STATUSES = {"FAILED", "FAILURE", "CANCELLED", "CANCELED", "ERROR"}


class ProductUGCRecipeRunner:
    def __init__(
        self,
        db: Session,
        *,
        provider_factory: Callable[[], RunwayRecipeProvider] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.db = db
        self.settings = get_settings()
        self.provider_factory = provider_factory or RunwayRecipeProvider
        self.sleep = sleep

    def validate_preflight(self, draft_id: int, *, real_run: bool = False):
        self._preflight(real_run=real_run)
        service = ProductUGCRecipeService(self.db)
        draft = service.get(draft_id)
        service.provider_request(draft)
        return service.output(draft)

    def run(
        self,
        draft_id: int,
        *,
        real_run: bool = False,
        preclaimed: bool = False,
    ) -> ProductUGCRecipeRunOutput:
        draft = None
        errors: list[str] = []
        try:
            self._preflight(real_run=real_run)
            service = ProductUGCRecipeService(self.db)
            draft = service.get(draft_id)
            if preclaimed:
                if draft.status != "provider_launching":
                    raise RunwayRecipeError("Product UGC draft was not reserved by the paid UI action.")
            else:
                claimed = self.db.execute(
                    update(type(draft))
                    .where(type(draft).id == draft.id, type(draft).status == "ready_for_paid_preflight")
                    .values(status="provider_launching", provider_status="SUBMITTING")
                )
                if claimed.rowcount != 1:
                    raise RunwayRecipeError("Product UGC draft is already running or is not paid-run ready.")
                self.db.commit()
                self.db.refresh(draft)
            request = service.provider_request(draft)
            provider = self.provider_factory()
            target_dir = self.settings.media_root / "provider" / "runway_product_ugc" / f"draft_{draft.id}"
            task = provider.create_product_ugc(request)
            draft.provider_task_id = task.provider_job_id
            draft.provider_status = task.status
            draft.status = "provider_submitted"
            self.db.commit()
            self._poll(provider, draft)
            paths = provider.download_outputs(task.provider_job_id, target_dir)
            if not paths or any(not path.exists() or path.stat().st_size <= 0 for path in paths):
                raise RunwayRecipeError("Runway Product UGC output was not downloaded or is empty.")
            draft.local_output_paths_json = [path.as_posix() for path in paths]
            draft.status = "generated_needs_human_review"
            draft.provider_status = "SUCCEEDED"
            draft.human_review_status = "needs_human_review"
            draft.publishing_readiness = "blocked"
        except Exception as exc:
            errors.append(self._safe_error(exc))
            if draft is not None:
                draft.status = "provider_failed"
                draft.provider_status = draft.provider_status or "FAILED"
                draft.human_review_status = "needs_human_review"
                draft.publishing_readiness = "blocked"
                warnings = list(draft.warnings_json or [])
                warnings.append(f"Provider run failed: {errors[-1]}")
                draft.warnings_json = warnings
                draft.generation_report_path = self._write_report(draft, errors=errors)
                self.db.commit()
            raise
        draft.generation_report_path = self._write_report(draft, errors=errors)
        self.db.commit()
        self.db.refresh(draft)
        return self.output(draft)

    def output(self, draft) -> ProductUGCRecipeRunOutput:
        return ProductUGCRecipeRunOutput(
            draft_id=draft.id,
            status=draft.status,
            provider_task_id=draft.provider_task_id,
            provider_status=draft.provider_status,
            local_output_paths=draft.local_output_paths_json or [],
            generation_report_path=draft.generation_report_path,
            human_review_status=draft.human_review_status,
            publishing_readiness=draft.publishing_readiness,
        )

    def _poll(self, provider: RunwayRecipeProvider, draft) -> None:
        deadline = time.monotonic() + self.settings.max_provider_poll_seconds
        while time.monotonic() < deadline:
            status = provider.get_status(draft.provider_task_id)
            normalized = status.status.upper()
            draft.provider_status = normalized
            self.db.commit()
            if normalized in SUCCESS_STATUSES:
                return
            if normalized in FAILURE_STATUSES:
                raise RunwayRecipeError(f"Runway Product UGC task ended with status {normalized}.")
            self.sleep(3)
        raise RunwayRecipeError("Runway Product UGC task timed out before completion.")

    def _preflight(self, *, real_run: bool) -> None:
        if not real_run:
            raise ProviderConfigurationError("Product UGC Recipe requires explicit --real-run.")
        if self.settings.generation_mode != "real":
            raise ProviderConfigurationError("Product UGC Recipe requires QVF_GENERATION_MODE=real.")
        if not self.settings.allow_real_spend:
            raise ProviderConfigurationError("Product UGC Recipe requires QVF_ALLOW_REAL_SPEND=true.")
        if not os.getenv("RUNWAYML_API_SECRET"):
            raise ProviderConfigurationError("RUNWAYML_API_SECRET is missing.")

    def _write_report(self, draft, *, errors: list[str]) -> str:
        report = {
            "run_type": "runway_product_ugc_recipe",
            "recipe_version": draft.recipe_version,
            "draft_id": draft.id,
            "product_id": draft.product_id,
            "sku": draft.sku,
            "variant_key": draft.variant_key,
            "provider": "runway",
            "provider_task_id": draft.provider_task_id,
            "provider_status": draft.provider_status,
            "product_asset_ids": draft.product_asset_ids_json or [],
            "primary_product_asset_id": draft.primary_product_asset_id,
            "payload_preview": draft.provider_payload_preview_json or {},
            "local_output_paths": draft.local_output_paths_json or [],
            "human_review_status": draft.human_review_status,
            "publishing_readiness": "blocked",
            "errors": errors,
            "created_at": datetime.now(UTC).isoformat(),
        }
        report_dir = self.settings.media_root / "generation_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"product_ugc_recipe_draft_{draft.id}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path.as_posix()

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        message = str(exc).replace("\n", " ").strip()
        message = re.sub(r"Bearer\s+\S+", "Bearer [redacted]", message, flags=re.IGNORECASE)
        message = re.sub(r"key_[A-Za-z0-9_-]+", "[redacted-key]", message)
        message = re.sub(r"data:[^;\s]+;base64,[A-Za-z0-9+/=]+", "data:[redacted]", message)
        message = re.sub(r"(https?://[^\s\"']+)\?[^\s\"']+", r"\1?[redacted]", message)
        return (message or exc.__class__.__name__)[:800]
