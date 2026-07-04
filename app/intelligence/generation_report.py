from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings


class GenerationReportWriter:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def write(
        self,
        video_job: models.VideoJob,
        *,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> Path:
        report = self.build(video_job, warnings=warnings or [], errors=errors or [])
        report_dir = self.settings.media_root / "generation_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"{video_job.id}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def build(
        self,
        video_job: models.VideoJob,
        *,
        warnings: list[str],
        errors: list[str],
    ) -> dict[str, Any]:
        variant = video_job.script_variant
        script_job = variant.script_job
        product = script_job.product
        prompt_pack = self._prompt_pack(video_job)
        script_brief = self._script_brief(script_job, prompt_pack)
        intelligence_pack_id = script_brief.intelligence_pack_id if script_brief else None

        report_warnings = list(warnings)
        if script_brief:
            report_warnings.extend(script_brief.safety_warnings_json or [])
            report_warnings.extend(script_brief.missing_data_json or [])
            if script_brief.intelligence_pack:
                report_warnings.extend(script_brief.intelligence_pack.warnings_json or [])

        return {
            "product_id": product.id,
            "sku": product.sku,
            "intelligence_pack_id": intelligence_pack_id,
            "script_brief_id": script_brief.id if script_brief else None,
            "script_job_id": script_job.id,
            "prompt_pack_id": prompt_pack.id if prompt_pack else None,
            "video_job_id": video_job.id,
            "llm_provider": script_job.llm_provider,
            "llm_model": script_job.llm_model,
            "video_provider": video_job.provider,
            "provider_job_ids": [
                clip.provider_job_id for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.provider_job_id
            ],
            "local_output_paths": [
                clip.clip_path for clip in sorted(video_job.clips, key=lambda item: item.id) if clip.clip_path
            ],
            "final_video_path": video_job.output_video_path,
            "warnings": sorted(set(report_warnings)),
            "errors": errors or ([video_job.error_message] if video_job.error_message else []),
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _prompt_pack(self, video_job: models.VideoJob) -> models.PromptPack | None:
        return self.db.scalar(
            select(models.PromptPack)
            .where(models.PromptPack.script_variant_id == video_job.script_variant_id)
            .order_by(models.PromptPack.id.desc())
        )

    def _script_brief(
        self,
        script_job: models.ScriptJob,
        prompt_pack: models.PromptPack | None,
    ) -> models.ScriptBrief | None:
        if prompt_pack and prompt_pack.script_brief:
            return prompt_pack.script_brief
        script_brief_id = (script_job.input_payload_json or {}).get("script_brief_id")
        if script_brief_id:
            return self.db.get(models.ScriptBrief, script_brief_id)
        return None
