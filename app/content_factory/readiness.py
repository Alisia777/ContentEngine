from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.creative.product_geometry import GEOMETRY_NEGATIVE_TERMS
from app.video_generator.artifact_manager import ArtifactManager


QUALITY_APPROVED_STATUSES = {"approved", "human_approved"}
PROVIDER_SUCCESS_STATUSES = {"video_generated", "provider_succeeded", "completed", "complete", "succeeded", "success", "done"}
GEOMETRY_MISMATCH_MARKERS = {
    "product_geometry_mismatch",
    "geometry mismatch",
    "size/proportion drift",
    "size/proportions drift",
    "wrong proportions",
    "changed product size",
    "product scale mismatch",
}


def content_run_prompt_pack(content_run: models.ContentRun) -> dict[str, Any]:
    run = content_run.run_json or {}
    if isinstance(run.get("prompt_pack"), dict) and run["prompt_pack"]:
        return run["prompt_pack"]
    if content_run.generation_variant and content_run.generation_variant.prompt_pack_json:
        return content_run.generation_variant.prompt_pack_json
    if content_run.prompt_pack and content_run.prompt_pack.prompt_pack_json:
        return content_run.prompt_pack.prompt_pack_json
    return {}


def reference_readiness(content_run: models.ContentRun, prompt_pack: dict[str, Any] | None = None) -> dict[str, Any]:
    run = content_run.run_json or {}
    existing = run.get("reference_readiness") if isinstance(run.get("reference_readiness"), dict) else {}
    prompt_pack = prompt_pack or content_run_prompt_pack(content_run)
    status = existing.get("status") or prompt_pack.get("reference_readiness_status") or "unknown"
    blockers = list(existing.get("blockers") or [])
    warnings = list(existing.get("warnings") or [])
    return {
        "status": status,
        "ready": status == "ready",
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "reference_images_count": len(prompt_pack.get("reference_images") or []),
        "reference_bundle_id": prompt_pack.get("reference_bundle_id"),
        "primary_reference_asset": prompt_pack.get("primary_reference_asset"),
    }


def product_identity_readiness(prompt_pack: dict[str, Any]) -> dict[str, Any]:
    accuracy_rules = prompt_pack.get("product_accuracy_rules") or []
    scene_text = " ".join(
        str(value)
        for scene in prompt_pack.get("scene_prompts") or []
        for value in [
            scene.get("prompt_text"),
            " ".join(scene.get("safety_constraints") or []),
        ]
        if value
    ).lower()
    rules_present = bool(accuracy_rules) or "product accuracy rules" in scene_text or "do not alter product" in scene_text
    blockers = [] if rules_present else ["product_identity_constraints_missing"]
    return {
        "status": "ready" if rules_present else "blocked",
        "rules_present": rules_present,
        "blockers": blockers,
        "rules_count": len(accuracy_rules),
    }


def geometry_readiness(prompt_pack: dict[str, Any]) -> dict[str, Any]:
    scenes = prompt_pack.get("scene_prompts") or []
    top_geometry_rules = prompt_pack.get("product_geometry_rules") or {}
    top_scale_rules = prompt_pack.get("product_scale_rules") or {}
    geometry_spec = prompt_pack.get("product_geometry_spec") or {}
    scene_geometry_rules_present = any(scene.get("product_geometry_rules") for scene in scenes)
    scene_scale_rules_present = any(scene.get("product_scale_rules") for scene in scenes)
    negative_text = " ".join(
        str(value)
        for scene in scenes
        for value in [scene.get("negative_prompt")]
        if value
    ).lower()
    matched_negative_terms = [term for term in GEOMETRY_NEGATIVE_TERMS if term in negative_text]
    negative_prompt_blocks_geometry_drift = len(matched_negative_terms) == len(GEOMETRY_NEGATIVE_TERMS)
    geometry_lock_present = bool(
        geometry_spec.get("geometry_lock_enabled")
        or top_geometry_rules
        or top_scale_rules
        or scene_geometry_rules_present
        or scene_scale_rules_present
    )
    geometry_rules_present = bool(top_geometry_rules or scene_geometry_rules_present)
    scale_rules_present = bool(top_scale_rules or scene_scale_rules_present)
    missing_fields = []
    if not geometry_lock_present:
        missing_fields.append("product_geometry_spec")
    if not geometry_rules_present:
        missing_fields.append("product_geometry_rules")
    if not scale_rules_present:
        missing_fields.append("product_scale_rules")
    if not negative_prompt_blocks_geometry_drift:
        missing_fields.append("negative_prompt_size_proportion_drift_blockers")
    blockers = ["geometry_lock_missing"] if missing_fields else []
    return {
        "status": "ready" if not blockers else "blocked",
        "geometry_lock_present": geometry_lock_present,
        "geometry_rules_present": geometry_rules_present,
        "scale_rules_present": scale_rules_present,
        "negative_prompt_blocks_geometry_drift": negative_prompt_blocks_geometry_drift,
        "matched_negative_terms": matched_negative_terms,
        "missing_fields": missing_fields,
        "blockers": blockers,
    }


def publishing_readiness(db: Session, content_run: models.ContentRun) -> dict[str, Any]:
    video_job = content_run.video_job
    latest_review = latest_quality_review(db, content_run)
    package = latest_publishing_package(db, content_run)
    if not video_job:
        return {
            "status": "not_started",
            "ready": False,
            "blockers": ["video_not_generated"],
            "video_job_id": None,
            "quality_review_status": None,
            "publishing_package_id": None,
        }

    output_exists, output_non_empty = ArtifactManager.file_exists_and_non_empty(video_job.output_video_path)
    review_status = latest_review.status if latest_review else None
    if not output_exists or not output_non_empty:
        status = "blocked"
        blockers = ["video_output_missing"]
    elif not latest_review or review_status not in QUALITY_APPROVED_STATUSES:
        status = "needs_human_review"
        blockers = ["human_review_required"]
    elif package and package.status == "approved":
        status = "ready"
        blockers = []
    elif package:
        status = "needs_publishing_package_approval"
        blockers = ["publishing_package_not_approved"]
    else:
        status = "needs_publishing_package"
        blockers = ["publishing_package_missing"]
    return {
        "status": status,
        "ready": status == "ready",
        "blockers": blockers,
        "video_job_id": video_job.id,
        "video_status": video_job.status,
        "output_video_path": video_job.output_video_path,
        "output_file_exists": output_exists,
        "output_file_non_empty": output_non_empty,
        "provider_status_successful": video_job.status in PROVIDER_SUCCESS_STATUSES,
        "quality_review_id": latest_review.id if latest_review else None,
        "quality_review_status": review_status,
        "publishing_package_id": package.id if package else None,
        "publishing_package_status": package.status if package else None,
    }


def control_loop_readiness(db: Session, content_run: models.ContentRun) -> dict[str, Any]:
    prompt_pack = content_run_prompt_pack(content_run)
    identity = product_identity_readiness(prompt_pack)
    geometry = geometry_readiness(prompt_pack)
    publishing = publishing_readiness(db, content_run)
    return {
        "reference_readiness": reference_readiness(content_run, prompt_pack),
        "product_identity_readiness": identity,
        "geometry_readiness": geometry,
        "publishing_readiness": publishing,
        "product_identity_blockers": identity["blockers"],
        "geometry_scale_blockers": geometry["blockers"],
        "publishing_blockers": publishing["blockers"],
    }


def latest_quality_review(db: Session, content_run: models.ContentRun) -> models.VideoQualityReview | None:
    query = select(models.VideoQualityReview).order_by(models.VideoQualityReview.id.desc())
    if content_run.video_job_id:
        review = db.scalar(query.where(models.VideoQualityReview.video_job_id == content_run.video_job_id))
        if review:
            return review
    if content_run.generation_variant_id:
        return db.scalar(
            query.where(models.VideoQualityReview.video_generation_variant_id == content_run.generation_variant_id)
        )
    return None


def latest_publishing_package(db: Session, content_run: models.ContentRun) -> models.PublishingPackage | None:
    if not content_run.video_job_id:
        return None
    return db.scalar(
        select(models.PublishingPackage)
        .where(models.PublishingPackage.video_job_id == content_run.video_job_id)
        .order_by(models.PublishingPackage.id.desc())
    )


def generation_report_exists(content_run: models.ContentRun) -> bool:
    if not content_run.video_job:
        return False
    settings = get_settings()
    paths = [settings.media_root / "generation_reports" / f"{content_run.video_job_id}.json"]
    if content_run.generation_variant and content_run.generation_variant.creative_variant_id:
        paths.append(
            settings.media_root
            / "generation_reports"
            / f"variant_{content_run.generation_variant.creative_variant_id}_video_{content_run.video_job_id}.json"
        )
    return any(path.exists() for path in paths)


def product_geometry_mismatch_detected(db: Session, content_run: models.ContentRun) -> bool:
    values: list[Any] = []
    review = latest_quality_review(db, content_run)
    if review:
        values.extend([review.status, review.review_json, review.warnings_json])
    if content_run.video_job_id:
        requests = db.scalars(
            select(models.SceneRegenerationRequest).where(
                models.SceneRegenerationRequest.video_job_id == content_run.video_job_id
            )
        ).all()
        values.extend(requests)
    if content_run.generation_variant_id:
        requests = db.scalars(
            select(models.SceneRegenerationRequest).where(
                models.SceneRegenerationRequest.video_generation_variant_id == content_run.generation_variant_id
            )
        ).all()
        values.extend(requests)
    text = _json_text(values)
    return any(marker in text for marker in GEOMETRY_MISMATCH_MARKERS)


def _json_text(value: Any) -> str:
    def default(item: Any) -> Any:
        if isinstance(item, Path):
            return item.as_posix()
        if isinstance(item, models.SceneRegenerationRequest):
            return {
                "reason": item.reason,
                "feedback": item.feedback,
                "status": item.status,
                "request_json": item.request_json,
            }
        return str(item)

    return json.dumps(value, default=default, ensure_ascii=False).lower()
