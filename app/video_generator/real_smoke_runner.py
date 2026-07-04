from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.assets.readiness_checker import ProductReferenceReadinessChecker
from app.config import get_settings
from app.creative.types import CreativeSpec
from app.intelligence.errors import ProviderConfigurationError
from app.intelligence.video_generator import GeneratorVideoService
from app.video_generator.artifact_manager import ArtifactManager
from app.video_generator.errors import VideoGeneratorDataError
from app.video_generator.generator import VideoGenerator
from app.video_generator.types import RealSmokeRunOutput


SUCCESS_STATUSES = {"video_generated", "provider_succeeded", "completed", "complete", "succeeded", "success", "done"}
SECRET_KEYS = {"api_key", "key", "token", "signature", "sig", "secret", "authorization", "x-amz-signature", "x-amz-security-token"}


class RealSmokeRunner:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.artifacts = ArtifactManager()

    def run_from_variant(
        self,
        creative_variant_id: int,
        provider: str = "runway",
        max_scenes: int = 1,
        full_video: bool = False,
        allow_real_spend: bool = False,
    ) -> RealSmokeRunOutput:
        self._preflight_environment(provider, allow_real_spend=allow_real_spend)
        if max_scenes is None:
            max_scenes = 1
        if not full_video:
            max_scenes = max(1, min(max_scenes, 1))

        creative_variant = self._preflight_variant(creative_variant_id)
        spec = CreativeSpec.model_validate(creative_variant.creative_spec.spec_json)
        readiness = ProductReferenceReadinessChecker(self.db).check(spec.product_id, provider=provider)
        if readiness.status != "ready" or not readiness.real_generation_allowed:
            raise ProviderConfigurationError(
                "Product reference readiness must be ready before real smoke: "
                + ", ".join(readiness.blockers or ["not ready"])
            )
        prompt_variant = VideoGenerator(self.db).build_prompt_pack_from_variant(creative_variant_id, provider=provider)
        prompt_pack = prompt_variant.prompt_pack
        if not prompt_pack:
            raise VideoGeneratorDataError("PromptPack could not be built from selected variant.")
        if (prompt_variant.prompt_pack_json or {}).get("reference_readiness_status") != "ready":
            raise ProviderConfigurationError("PromptPack does not include a ready product reference bundle.")

        service = GeneratorVideoService(self.db)
        video_job = service.create_video_job_from_prompt_pack(
            prompt_pack.id,
            provider,
            max_scenes=max_scenes,
            full_video=full_video,
            apply_safety_limits=True,
        )
        prompt_variant.video_job_id = video_job.id
        prompt_variant.status = video_job.status
        self.db.commit()

        warnings: list[str] = list((prompt_variant.prompt_pack_json or {}).get("warnings") or [])
        errors: list[str] = []
        review = None
        report_path = None
        local_paths: list[str] = []
        try:
            video_job = service.start_provider_jobs(video_job, explicit_real_run=True)
            service.poll_until_complete(video_job)
            local_paths = service.download_outputs(video_job)
            video_job = service.assemble(video_job)
            prompt_variant.local_output_paths_json = local_paths
            prompt_variant.final_video_path = video_job.output_video_path
            prompt_variant.status = video_job.status
            report_path = self.write_variant_generation_report(
                prompt_variant,
                video_job,
                quality_review_id=None,
                warnings=warnings,
                errors=errors,
            )
            review = self._create_quality_review(prompt_variant, video_job, status="needs_human_review")
            report_path = self.write_variant_generation_report(
                prompt_variant,
                video_job,
                quality_review_id=review.id,
                warnings=warnings,
                errors=errors,
            )
            self.db.commit()
        except Exception as exc:
            errors.append(str(exc))
            video_job.error_message = str(exc)
            video_job.status = "provider_failed"
            prompt_variant.status = "failed_generation"
            report_path = self.write_variant_generation_report(
                prompt_variant,
                video_job,
                quality_review_id=None,
                warnings=warnings,
                errors=errors,
            )
            review = self._create_quality_review(prompt_variant, video_job, status="failed_generation")
            report_path = self.write_variant_generation_report(
                prompt_variant,
                video_job,
                quality_review_id=review.id,
                warnings=warnings,
                errors=errors,
            )
            self.db.commit()
            raise

        return self._output(prompt_variant, video_job, report_path=report_path, quality_review_id=review.id, warnings=warnings, errors=errors)

    def poll(self, video_job_id: int) -> RealSmokeRunOutput:
        video_job, generation_variant = self._job_and_variant(video_job_id)
        status = GeneratorVideoService(self.db).provider_status(video_job)
        generation_variant.status = status["status"]
        self.db.commit()
        return self._output(generation_variant, video_job, warnings=[], errors=[])

    def download(self, video_job_id: int) -> RealSmokeRunOutput:
        video_job, generation_variant = self._job_and_variant(video_job_id)
        paths = GeneratorVideoService(self.db).download_outputs(video_job)
        generation_variant.local_output_paths_json = paths
        generation_variant.status = "downloaded"
        self.db.commit()
        return self._output(generation_variant, video_job, warnings=[], errors=[])

    def score(self, video_job_id: int) -> RealSmokeRunOutput:
        video_job, generation_variant = self._job_and_variant(video_job_id)
        review = self._create_quality_review(generation_variant, video_job, status=self._review_status(video_job))
        report_path = self.write_variant_generation_report(
            generation_variant,
            video_job,
            quality_review_id=review.id,
            warnings=[],
            errors=[video_job.error_message] if video_job.error_message else [],
        )
        self.db.commit()
        return self._output(generation_variant, video_job, report_path=report_path, quality_review_id=review.id, warnings=[], errors=[])

    def output_for_video_job(self, video_job_id: int) -> RealSmokeRunOutput:
        video_job, generation_variant = self._job_and_variant(video_job_id)
        return self._output(generation_variant, video_job, warnings=[], errors=[video_job.error_message] if video_job.error_message else [])

    def write_variant_generation_report(
        self,
        generation_variant: models.VideoGenerationVariant,
        video_job: models.VideoJob,
        *,
        quality_review_id: int | None,
        warnings: list[str],
        errors: list[str],
    ) -> str:
        prompt_pack = generation_variant.prompt_pack
        creative_variant = generation_variant.creative_variant
        spec_record = generation_variant.creative_spec
        product = spec_record.product
        provider_job_ids = [clip.provider_job_id for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.provider_job_id]
        provider_responses = [clip.raw_response_json for clip in sorted(video_job.clips, key=lambda item: item.id)]
        prompt_pack_json = prompt_pack.prompt_pack_json if prompt_pack else generation_variant.prompt_pack_json
        report = {
            "run_type": "real_one_scene_smoke",
            "product_id": product.id,
            "sku": product.sku,
            "creative_spec_id": spec_record.id,
            "creative_variant_id": creative_variant.id if creative_variant else generation_variant.creative_variant_id,
            "prompt_pack_id": prompt_pack.id if prompt_pack else generation_variant.prompt_pack_id,
            "video_job_id": video_job.id,
            "provider": video_job.provider,
            "provider_job_ids": provider_job_ids,
            "reference_bundle_id": prompt_pack_json.get("reference_bundle_id") if prompt_pack_json else None,
            "reference_asset_ids": (prompt_pack_json.get("provider_reference_bundle") or {}).get("reference_asset_ids", []),
            "primary_reference_asset_id": prompt_pack_json.get("primary_reference_asset") if prompt_pack_json else None,
            "prompt_summary": self._prompt_summary(prompt_pack_json or {}),
            "provider_request_json": prompt_pack.provider_payload_json if prompt_pack else generation_variant.provider_payload_json,
            "provider_response_json": provider_responses,
            "local_output_paths": [clip.clip_path for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.clip_path],
            "final_video_path": video_job.output_video_path,
            "quality_review_id": quality_review_id,
            "warnings": list(dict.fromkeys(warnings)),
            "errors": list(dict.fromkeys([error for error in errors if error])),
            "created_at": datetime.now(UTC).isoformat(),
        }
        report_dir = self.settings.media_root / "generation_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"variant_{generation_variant.creative_variant_id}_video_{video_job.id}.json"
        path.write_text(json.dumps(self._scrub(report), ensure_ascii=False, indent=2), encoding="utf-8")
        return path.as_posix()

    def _preflight_environment(self, provider: str, *, allow_real_spend: bool) -> None:
        if self.settings.generation_mode != "real":
            raise ProviderConfigurationError("Real smoke requires QVF_GENERATION_MODE=real.")
        if not self.settings.allow_real_spend:
            raise ProviderConfigurationError("Real smoke requires QVF_ALLOW_REAL_SPEND=true.")
        if not allow_real_spend:
            raise ProviderConfigurationError("Real smoke requires explicit allow_real_spend=true.")
        if provider != "runway":
            raise ProviderConfigurationError("Sprint 07 real smoke supports runway only.")
        selected_provider = provider or self.settings.video_provider
        if selected_provider != "runway":
            raise ProviderConfigurationError("QVF_VIDEO_PROVIDER or request provider must be runway.")
        if not os.getenv("RUNWAYML_API_SECRET"):
            raise ProviderConfigurationError("RUNWAYML_API_SECRET is missing.")

    def _preflight_variant(self, creative_variant_id: int) -> models.CreativeVariant:
        creative_variant = self.db.get(models.CreativeVariant, creative_variant_id)
        if not creative_variant:
            raise VideoGeneratorDataError(f"CreativeVariant {creative_variant_id} not found.")
        selected_id = creative_variant.variant_set.selected_variant_id
        if creative_variant.status != "selected" and selected_id != creative_variant.id:
            raise ProviderConfigurationError("CreativeVariant must be selected before real smoke.")
        return creative_variant

    def _create_quality_review(
        self,
        generation_variant: models.VideoGenerationVariant,
        video_job: models.VideoJob,
        *,
        status: str,
    ) -> models.VideoQualityReview:
        prompt_pack = generation_variant.prompt_pack_json or {}
        spec = CreativeSpec.model_validate(generation_variant.creative_spec.spec_json)
        scene_prompts = prompt_pack.get("scene_prompts") or []
        output_exists, output_non_empty = self.artifacts.file_exists_and_non_empty(video_job.output_video_path)
        checks = [
            self._check("provider_status_successful", video_job.status in SUCCESS_STATUSES),
            self._check("output_file_exists", output_exists),
            self._check("output_file_non_empty", output_non_empty),
            self._check("generation_report_exists", bool(self._variant_report_path(generation_variant, video_job).exists())),
            self._check("first_frame_requirements_exist", bool(prompt_pack.get("selected_first_frame") or (scene_prompts and scene_prompts[0].get("first_frame_requirements")))),
            self._check("approved_reference_image_included", bool(prompt_pack.get("reference_bundle_id") and prompt_pack.get("reference_images"))),
            self._check("captions_exist", all(scene.get("caption_text") or scene.get("prompt_text") for scene in scene_prompts)),
            self._check("cta_exists", bool(prompt_pack.get("selected_cta") or spec.cta)),
            self._check("forbidden_claims_not_used", not self._forbidden_claims_used(spec, generation_variant.creative_variant)),
        ]
        passed = sum(1 for check in checks if check["passed"])
        score = round(passed / len(checks), 3) if checks else 0
        review_json = {
            "score": score,
            "status": status,
            "checks": checks,
            "notes": ["Metadata-only score. No computer vision or visual product identity verification was performed."],
        }
        review = models.VideoQualityReview(
            creative_spec_id=generation_variant.creative_spec_id,
            video_generation_variant_id=generation_variant.id,
            video_job_id=video_job.id,
            status=status,
            score=score,
            review_json=review_json,
            warnings_json=prompt_pack.get("warnings") or [],
        )
        generation_variant.quality_score_json = review_json
        self.db.add(review)
        self.db.flush()
        return review

    @staticmethod
    def _check(key: str, passed: bool) -> dict:
        return {"key": key, "passed": bool(passed), "check_type": "metadata"}

    def _output(
        self,
        generation_variant: models.VideoGenerationVariant,
        video_job: models.VideoJob,
        *,
        report_path: str | None = None,
        quality_review_id: int | None = None,
        warnings: list[str],
        errors: list[str],
    ) -> RealSmokeRunOutput:
        product = generation_variant.creative_spec.product
        prompt_pack = generation_variant.prompt_pack_json or {}
        review = (
            self.db.get(models.VideoQualityReview, quality_review_id)
            if quality_review_id
            else self._latest_quality_review(generation_variant.id)
        )
        return RealSmokeRunOutput(
            status=video_job.status,
            product_id=product.id,
            sku=product.sku,
            creative_spec_id=generation_variant.creative_spec_id,
            creative_variant_id=generation_variant.creative_variant_id or 0,
            prompt_pack_id=generation_variant.prompt_pack_id or 0,
            video_job_id=video_job.id,
            provider=video_job.provider,
            provider_job_ids=[clip.provider_job_id for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.provider_job_id],
            reference_bundle_id=prompt_pack.get("reference_bundle_id"),
            local_output_paths=generation_variant.local_output_paths_json or [clip.clip_path for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.clip_path],
            final_video_path=generation_variant.final_video_path or video_job.output_video_path,
            generation_report_path=report_path or self._existing_report_path(generation_variant, video_job),
            quality_review_id=quality_review_id or (review.id if review else None),
            quality_score=review.score if review else None,
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys([error for error in errors if error])),
        )

    def _job_and_variant(self, video_job_id: int) -> tuple[models.VideoJob, models.VideoGenerationVariant]:
        video_job = self.db.get(models.VideoJob, video_job_id)
        if not video_job:
            raise VideoGeneratorDataError(f"VideoJob {video_job_id} not found.")
        generation_variant = self.db.scalar(
            select(models.VideoGenerationVariant).where(models.VideoGenerationVariant.video_job_id == video_job_id)
        )
        if not generation_variant:
            raise VideoGeneratorDataError(f"VideoGenerationVariant for VideoJob {video_job_id} not found.")
        return video_job, generation_variant

    def _variant_report_path(self, generation_variant: models.VideoGenerationVariant, video_job: models.VideoJob) -> Path:
        return self.settings.media_root / "generation_reports" / f"variant_{generation_variant.creative_variant_id}_video_{video_job.id}.json"

    def _existing_report_path(self, generation_variant: models.VideoGenerationVariant, video_job: models.VideoJob) -> str | None:
        variant_path = self._variant_report_path(generation_variant, video_job)
        if variant_path.exists():
            return variant_path.as_posix()
        default_path = self.settings.media_root / "generation_reports" / f"{video_job.id}.json"
        return default_path.as_posix() if default_path.exists() else None

    def _latest_quality_review(self, generation_variant_id: int) -> models.VideoQualityReview | None:
        review = self.db.scalar(
            select(models.VideoQualityReview)
            .where(models.VideoQualityReview.video_generation_variant_id == generation_variant_id)
            .order_by(models.VideoQualityReview.id.desc())
        )
        return review

    @staticmethod
    def _review_status(video_job: models.VideoJob) -> str:
        if video_job.status in SUCCESS_STATUSES:
            return "needs_human_review"
        if video_job.status in {"provider_failed", "failed", "error"}:
            return "failed_generation"
        return "needs_regeneration"

    @staticmethod
    def _prompt_summary(prompt_pack_json: dict[str, Any]) -> dict[str, Any]:
        scenes = prompt_pack_json.get("scene_prompts") or []
        return {
            "scene_count": len(scenes),
            "first_scene_prompt": scenes[0].get("prompt_text")[:500] if scenes else None,
            "selected_cta": prompt_pack_json.get("selected_cta"),
            "overlay_text": prompt_pack_json.get("overlay_text"),
            "reference_images_count": len(prompt_pack_json.get("reference_images") or []),
        }

    @staticmethod
    def _forbidden_claims_used(spec: CreativeSpec, creative_variant: models.CreativeVariant | None) -> bool:
        values = [spec.hook_text, spec.viewer_promise]
        if creative_variant:
            values.extend([creative_variant.hook_text, creative_variant.cta_framing or "", creative_variant.visual_style or ""])
            for scene in creative_variant.scene_plan_json or []:
                values.extend([scene.get("visual", ""), scene.get("caption", ""), scene.get("voiceover", "")])
        text = " ".join(value for value in values if value).lower()
        allowed = " ".join(claim.claim.lower() for claim in spec.allowed_claims)
        risky = ["cure", "treatment", "medical treatment", "guaranteed result"]
        return any(term in text and term not in allowed for term in risky)

    @classmethod
    def _scrub(cls, value: Any) -> Any:
        if isinstance(value, dict):
            clean = {}
            for key, item in value.items():
                if any(secret in key.lower() for secret in SECRET_KEYS):
                    clean[key] = "[redacted]"
                else:
                    clean[key] = cls._scrub(item)
            return clean
        if isinstance(value, list):
            return [cls._scrub(item) for item in value]
        if isinstance(value, str):
            return cls._scrub_url(value)
        return value

    @staticmethod
    def _scrub_url(value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.query:
            return value
        safe_query = [
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if not any(secret in key.lower() for secret in SECRET_KEYS)
        ]
        return urlunparse(parsed._replace(query=urlencode(safe_query), fragment=""))
