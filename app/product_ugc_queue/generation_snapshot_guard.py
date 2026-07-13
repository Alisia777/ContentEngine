from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.product_ugc_queue.errors import ProductUGCSpendValidationError


GENERATION_TEMPLATE_SNAPSHOT_SCHEMA = "generation_template_snapshot_v1"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_MASS_LINEAGE_KEYS = frozenset(
    {
        "generation_template_snapshot_schema",
        "generation_template_snapshot_hash",
        "source_preview_batch_id",
        "source_batch_id",
        "source_template_draft_id",
        "estimated_credits_per_item",
        "provider_payload_sha256",
    }
)


def canonical_json_sha256(value: object) -> str:
    """Return the shared, deterministic hash used by preview and spend guard."""

    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_mass_generation_pre_spend(
    db: Session,
    job: models.ProductUGCGenerationJob,
    *,
    provider_payload: object | None,
    require_provider_payload: bool = True,
) -> None:
    """Fail closed when a mass-generation approval is stale or incomplete.

    Legacy single-item queue jobs predate snapshot lineage and intentionally do
    not enter this guard. A job is treated as mass work from durable database
    links and idempotency as well as mutable JSON metadata, so deleting one
    metadata flag cannot bypass validation.
    """

    metadata = _mapping(job.metadata_json)
    if not _is_mass_generation_job(db, job, metadata):
        return

    _require_contract_keys(metadata)
    if metadata.get("generation_template_snapshot_schema") != GENERATION_TEMPLATE_SNAPSHOT_SCHEMA:
        _reject("snapshot_schema_invalid")

    snapshot_hash = _sha256(metadata.get("generation_template_snapshot_hash"), "snapshot_hash_invalid")
    provider_hash = _sha256(metadata.get("provider_payload_sha256"), "provider_payload_hash_invalid")
    source_batch_id = _positive_int(metadata.get("source_batch_id"), "source_batch_id_invalid")
    source_template_id = _positive_int(
        metadata.get("source_template_draft_id"),
        "source_template_draft_id_invalid",
    )
    credits_per_item = _positive_int(
        metadata.get("estimated_credits_per_item"),
        "estimated_credits_per_item_invalid",
    )
    sequence = _positive_int(metadata.get("sequence"), "sequence_invalid")
    preview_batch_id = _optional_positive_int(
        metadata.get("source_preview_batch_id"),
        "source_preview_batch_id_invalid",
    )

    metadata_batch_id = _positive_int(
        metadata.get("mass_operation_batch_id"),
        "mass_operation_batch_id_invalid",
    )
    if metadata_batch_id != source_batch_id:
        _reject("source_batch_lineage_mismatch")

    # Lock order is part of the promotion/worker concurrency contract:
    # preview -> working batch -> source template -> product -> assets ->
    # artifacts -> launch draft -> creator task. Promotion also locks preview
    # before it creates/links the working batch.
    preview_batch = None
    if preview_batch_id is not None:
        preview_batch = _validate_preview_batch(
            db,
            organization_id=job.organization_id,
            preview_batch_id=preview_batch_id,
            source_template_id=source_template_id,
            snapshot_hash=snapshot_hash,
        )
    source_batch = db.scalar(
        select(models.MassOperationBatch)
        .where(
            models.MassOperationBatch.id == source_batch_id,
            models.MassOperationBatch.organization_id == job.organization_id,
            models.MassOperationBatch.operation_type == "generation",
            models.MassOperationBatch.dry_run.is_(False),
        )
        .with_for_update()
    )
    if source_batch is None:
        _reject("source_batch_invalid")
    _validate_working_results_shape(source_batch, job=job)
    parameters = _mapping(source_batch.parameters_json)
    snapshot = parameters.get("template_snapshot")
    if not isinstance(snapshot, dict):
        _reject("template_snapshot_missing")
    if snapshot.get("schema") != GENERATION_TEMPLATE_SNAPSHOT_SCHEMA:
        _reject("template_snapshot_schema_invalid")
    if canonical_json_sha256(snapshot) != snapshot_hash:
        _reject("template_snapshot_integrity_mismatch")
    if parameters.get("template_snapshot_sha256") != snapshot_hash:
        _reject("source_batch_snapshot_hash_mismatch")
    if _positive_int(parameters.get("template_draft_id"), "batch_template_draft_id_invalid") != source_template_id:
        _reject("source_template_lineage_mismatch")

    batch_preview_id = _optional_positive_int(
        parameters.get("source_dry_run_batch_id"),
        "batch_source_preview_id_invalid",
    )
    if batch_preview_id != preview_batch_id:
        _reject("source_preview_lineage_mismatch")
    if preview_batch is not None:
        _validate_preview_working_parity(
            preview_batch,
            source_batch=source_batch,
        )

    expected_draft = snapshot.get("draft")
    if not isinstance(expected_draft, dict):
        _reject("template_snapshot_draft_invalid")
    if _positive_int(expected_draft.get("id"), "snapshot_draft_id_invalid") != source_template_id:
        _reject("snapshot_source_template_mismatch")
    if _positive_int(expected_draft.get("organization_id"), "snapshot_organization_invalid") != job.organization_id:
        _reject("snapshot_organization_mismatch")
    if _positive_int(expected_draft.get("estimated_credits"), "snapshot_credits_invalid") != credits_per_item:
        _reject("snapshot_credits_mismatch")

    total_requested = int(source_batch.total_requested or 0)
    if total_requested < 1 or int(source_batch.total_accepted or 0) != total_requested:
        _reject("source_batch_acceptance_invalid")
    if sequence > total_requested:
        _reject("sequence_outside_source_batch")
    if source_batch.status not in {"queued", "running"} or source_batch.started_at is None:
        _reject("source_batch_not_launchable")
    if parameters.get("real_spend_requested") is not True:
        _reject("source_batch_real_spend_not_confirmed")
    total_credits = _nonnegative_int(parameters.get("estimated_credits"), "batch_estimated_credits_invalid")
    if total_credits != credits_per_item * total_requested:
        _reject("batch_estimated_credits_mismatch")
    runtime_credit_limit = int(get_settings().mass_generation_credit_limit)
    stored_credit_limit = _positive_int(
        parameters.get("credit_limit"),
        "batch_credit_limit_invalid",
    )
    if stored_credit_limit != runtime_credit_limit:
        _reject("batch_credit_limit_changed")
    if total_credits > runtime_credit_limit:
        _reject("batch_credit_limit_exceeded")
    confirmed_total = _nonnegative_int(
        parameters.get("confirmed_total_credits"),
        "batch_confirmed_credits_invalid",
    )
    if confirmed_total != total_credits:
        _reject("batch_confirmed_credits_mismatch")

    source_template = db.scalar(
        select(models.ProductUGCRecipeDraft)
        .where(models.ProductUGCRecipeDraft.id == source_template_id)
        .with_for_update()
    )
    if source_template is None:
        _reject("source_template_missing")
    current_snapshot = _current_template_snapshot(
        db,
        source_template,
        organization_id=job.organization_id,
    )
    if canonical_json_sha256(current_snapshot) != snapshot_hash:
        _reject("source_template_or_inputs_changed")

    launch_draft = db.scalar(
        select(models.ProductUGCRecipeDraft)
        .where(models.ProductUGCRecipeDraft.id == job.draft_id)
        .with_for_update()
    )
    if launch_draft is None:
        _reject("launch_draft_missing")
    _validate_launch_draft(
        launch_draft,
        expected_draft=expected_draft,
        source_batch_id=source_batch_id,
        sequence=sequence,
        credits_per_item=credits_per_item,
    )
    _validate_batch_task_and_result(
        db,
        job=job,
        batch=source_batch,
        launch_draft=launch_draft,
        sequence=sequence,
    )

    expected_preview = expected_draft.get("provider_payload_preview_json")
    if not isinstance(expected_preview, dict) or not expected_preview:
        _reject("snapshot_provider_payload_invalid")
    if canonical_json_sha256(expected_preview) != provider_hash:
        _reject("snapshot_provider_payload_hash_mismatch")
    current_preview = launch_draft.provider_payload_preview_json
    if not isinstance(current_preview, dict) or canonical_json_sha256(current_preview) != provider_hash:
        _reject("launch_provider_payload_preview_changed")
    if not require_provider_payload:
        return
    _validate_built_provider_payload(
        provider_payload,
        expected_preview=expected_preview,
        expected_hash=provider_hash,
    )


def _is_mass_generation_job(
    db: Session,
    job: models.ProductUGCGenerationJob,
    metadata: dict[str, Any],
) -> bool:
    if metadata.get("source") == "mass_operation":
        return True
    if any(key in metadata for key in _MASS_LINEAGE_KEYS):
        return True
    if str(job.idempotency_key or "").startswith("mass-generation:"):
        return True
    linked_task_id = db.scalar(
        select(models.CreatorTask.id)
        .where(
            models.CreatorTask.organization_id == job.organization_id,
            models.CreatorTask.product_ugc_recipe_draft_id == job.draft_id,
            models.CreatorTask.mass_operation_batch_id.is_not(None),
        )
        .limit(1)
    )
    return linked_task_id is not None


def _require_contract_keys(metadata: dict[str, Any]) -> None:
    missing = sorted(key for key in _MASS_LINEAGE_KEYS if key not in metadata)
    if missing:
        _reject("snapshot_lineage_metadata_missing")


def _validate_preview_batch(
    db: Session,
    *,
    organization_id: int,
    preview_batch_id: int,
    source_template_id: int,
    snapshot_hash: str,
) -> models.MassOperationBatch:
    preview = db.scalar(
        select(models.MassOperationBatch)
        .where(
            models.MassOperationBatch.id == preview_batch_id,
            models.MassOperationBatch.organization_id == organization_id,
            models.MassOperationBatch.operation_type == "generation",
            models.MassOperationBatch.dry_run.is_(True),
        )
        .with_for_update()
    )
    if preview is None:
        _reject("source_preview_batch_invalid")
    if (
        preview.status != "validated"
        or int(preview.total_requested or 0) < 1
        or int(preview.total_accepted or 0) != int(preview.total_requested or 0)
        or int(preview.total_failed or 0) != 0
        or bool(preview.errors_json)
        or preview.completed_at is None
    ):
        _reject("source_preview_not_clean_and_validated")
    parameters = _mapping(preview.parameters_json)
    if parameters.get("real_spend_requested") is not False:
        _reject("source_preview_spend_shape_invalid")
    if (
        _positive_int(parameters.get("quantity"), "preview_quantity_invalid")
        != int(preview.total_requested)
    ):
        _reject("source_preview_quantity_mismatch")
    if parameters.get("template_snapshot_sha256") != snapshot_hash:
        _reject("source_preview_snapshot_hash_mismatch")
    preview_snapshot = parameters.get("template_snapshot")
    if not isinstance(preview_snapshot, dict) or canonical_json_sha256(preview_snapshot) != snapshot_hash:
        _reject("source_preview_snapshot_integrity_mismatch")
    if _positive_int(parameters.get("template_draft_id"), "preview_template_draft_id_invalid") != source_template_id:
        _reject("source_preview_template_mismatch")
    return preview


def _validate_preview_working_parity(
    preview: models.MassOperationBatch,
    *,
    source_batch: models.MassOperationBatch,
) -> None:
    preview_parameters = _mapping(preview.parameters_json)
    source_parameters = _mapping(source_batch.parameters_json)
    if int(preview.total_requested or 0) != int(source_batch.total_requested or 0):
        _reject("preview_working_quantity_mismatch")
    for key in (
        "quantity",
        "estimated_credits",
        "template_draft_id",
        "template_snapshot_sha256",
        "template_snapshot",
        "assignee_user_profile_ids",
    ):
        if preview_parameters.get(key) != source_parameters.get(key):
            _reject(f"preview_working_{key}_mismatch")


def _validate_launch_draft(
    draft: models.ProductUGCRecipeDraft,
    *,
    expected_draft: dict[str, Any],
    source_batch_id: int,
    sequence: int,
    credits_per_item: int,
) -> None:
    scalar_fields = (
        "product_id",
        "sku",
        "recipe_version",
        "platform",
        "language",
        "character_image_path",
        "character_media_artifact_id",
        "character_image_filename",
        "likeness_consent",
        "exact_variant_confirmed",
        "primary_product_asset_id",
        "product_info",
        "user_concept",
        "duration_seconds",
        "ratio",
        "audio_enabled",
        "estimated_credits",
    )
    for field in scalar_fields:
        if getattr(draft, field) != expected_draft.get(field):
            _reject(f"launch_draft_{field}_changed")
    if int(draft.estimated_credits or 0) != credits_per_item:
        _reject("launch_draft_credits_mismatch")
    if deepcopy(draft.product_asset_ids_json or []) != deepcopy(
        expected_draft.get("product_asset_ids_json") or []
    ):
        _reject("launch_draft_product_assets_changed")
    if draft.status != "provider_launching" or draft.blockers_json:
        _reject("launch_draft_not_ready")
    if draft.provider_task_id:
        _reject("launch_draft_already_submitted")

    if draft.variant_key != expected_draft.get("variant_key"):
        _reject("launch_draft_variant_lineage_changed")

    expected_inputs = _mapping(deepcopy(expected_draft.get("creative_inputs_json")))
    expected_inputs.pop("gates", None)
    expected_inputs.pop("mass_batch", None)
    current_inputs = _mapping(deepcopy(draft.creative_inputs_json))
    current_inputs.pop("gates", None)
    mass_batch = current_inputs.pop("mass_batch", None)
    if current_inputs != expected_inputs:
        _reject("launch_draft_creative_inputs_changed")
    if not isinstance(mass_batch, dict):
        _reject("launch_draft_mass_lineage_missing")
    if (
        _positive_int(mass_batch.get("batch_id"), "launch_mass_batch_id_invalid")
        != source_batch_id
        or _positive_int(mass_batch.get("sequence"), "launch_mass_sequence_invalid")
        != sequence
        or _positive_int(
            mass_batch.get("assignee_user_profile_id"),
            "launch_mass_assignee_invalid",
        )
        != draft.assigned_to_user_profile_id
    ):
        _reject("launch_draft_mass_lineage_mismatch")


def _validate_batch_task_and_result(
    db: Session,
    *,
    job: models.ProductUGCGenerationJob,
    batch: models.MassOperationBatch,
    launch_draft: models.ProductUGCRecipeDraft,
    sequence: int,
) -> None:
    tasks = list(
        db.scalars(
            select(models.CreatorTask)
            .where(
                models.CreatorTask.organization_id == job.organization_id,
                models.CreatorTask.mass_operation_batch_id == batch.id,
                models.CreatorTask.product_ugc_recipe_draft_id == launch_draft.id,
                models.CreatorTask.task_type == "review_generated_video",
            )
            .with_for_update()
        ).all()
    )
    if len(tasks) != 1:
        _reject("launch_creator_task_lineage_invalid")
    task = tasks[0]
    if task.assignee_user_profile_id != launch_draft.assigned_to_user_profile_id:
        _reject("launch_creator_task_assignee_mismatch")

    matches = [
        item
        for item in (batch.results_json or [])
        if isinstance(item, dict)
        and _coerce_positive_int(item.get("generation_job_id")) == job.id
    ]
    if len(matches) != 1:
        _reject("launch_batch_result_lineage_invalid")
    result = matches[0]
    if (
        _coerce_positive_int(result.get("draft_id")) != launch_draft.id
        or _coerce_positive_int(result.get("creator_task_id")) != task.id
        or _coerce_positive_int(result.get("sequence")) != sequence
        or _coerce_positive_int(result.get("assignee_user_profile_id"))
        != launch_draft.assigned_to_user_profile_id
    ):
        _reject("launch_batch_result_lineage_mismatch")


def _validate_working_results_shape(
    batch: models.MassOperationBatch,
    *,
    job: models.ProductUGCGenerationJob,
) -> None:
    if job.requested_by_user_profile_id != batch.created_by_user_profile_id:
        _reject("source_batch_requester_mismatch")
    total_requested = int(batch.total_requested or 0)
    raw_results = list(batch.results_json or [])
    if total_requested < 1 or len(raw_results) != total_requested:
        _reject("source_batch_results_count_invalid")
    if any(not isinstance(item, dict) for item in raw_results):
        _reject("source_batch_result_shape_invalid")
    results = [dict(item) for item in raw_results]
    fields = (
        "generation_job_id",
        "draft_id",
        "creator_task_id",
    )
    sequences = [_coerce_positive_int(item.get("sequence")) for item in results]
    if sorted(value for value in sequences if value is not None) != list(
        range(1, total_requested + 1)
    ):
        _reject("source_batch_result_sequences_invalid")
    for field in fields:
        identities = [_coerce_positive_int(item.get(field)) for item in results]
        if any(value is None for value in identities) or len(set(identities)) != total_requested:
            _reject(f"source_batch_result_{field}_invalid")
    if any(
        _coerce_positive_int(item.get("assignee_user_profile_id")) is None
        for item in results
    ):
        _reject("source_batch_result_assignee_invalid")
    current_matches = [
        item
        for item in results
        if _coerce_positive_int(item.get("generation_job_id")) == job.id
    ]
    if len(current_matches) != 1:
        _reject("source_batch_current_job_result_invalid")


def _validate_built_provider_payload(
    provider_payload: object | None,
    *,
    expected_preview: dict[str, Any],
    expected_hash: str,
) -> None:
    if hasattr(provider_payload, "model_dump"):
        try:
            provider_payload = provider_payload.model_dump(mode="json", by_alias=True)
        except (TypeError, ValueError):
            _reject("provider_payload_serialization_failed")
    if not isinstance(provider_payload, Mapping):
        _reject("provider_payload_missing")
    normalized = deepcopy(dict(provider_payload))
    for image_key in ("characterImage", "productImage"):
        actual_image = normalized.get(image_key)
        expected_image = expected_preview.get(image_key)
        if not isinstance(actual_image, dict) or not isinstance(expected_image, dict):
            _reject("provider_payload_image_contract_invalid")
        actual_uri = actual_image.get("uri")
        expected_uri = expected_image.get("uri")
        if not isinstance(actual_uri, str) or not actual_uri.strip():
            _reject("provider_payload_image_uri_missing")
        if not isinstance(expected_uri, str) or not expected_uri.strip():
            _reject("provider_payload_preview_image_uri_missing")
        normalized[image_key] = deepcopy(expected_image)
    if canonical_json_sha256(normalized) != expected_hash:
        _reject("built_provider_payload_changed")


def _current_template_snapshot(
    db: Session,
    template: models.ProductUGCRecipeDraft,
    *,
    organization_id: int,
) -> dict[str, Any]:
    product = db.scalar(
        select(models.Product)
        .where(
            models.Product.id == template.product_id,
            models.Product.organization_id == organization_id,
        )
        .with_for_update()
    )
    if product is None:
        _reject("snapshot_product_missing")

    raw_asset_ids = deepcopy(template.product_asset_ids_json or [])
    referenced_asset_ids = _referenced_ids(
        [*raw_asset_ids, template.primary_product_asset_id]
    )
    assets: list[models.ProductAsset] = []
    if referenced_asset_ids:
        assets = list(
            db.scalars(
                select(models.ProductAsset)
                .where(
                    models.ProductAsset.id.in_(sorted(referenced_asset_ids)),
                    models.ProductAsset.product_id == template.product_id,
                )
                .order_by(models.ProductAsset.id)
                .with_for_update()
            ).all()
        )

    referenced_artifact_ids = _referenced_ids(
        [
            template.character_media_artifact_id,
            *(asset.media_artifact_id for asset in assets),
        ]
    )
    artifacts: list[models.MediaArtifact] = []
    if referenced_artifact_ids:
        artifacts = list(
            db.scalars(
                select(models.MediaArtifact)
                .where(
                    models.MediaArtifact.id.in_(sorted(referenced_artifact_ids)),
                    models.MediaArtifact.organization_id == organization_id,
                )
                .order_by(models.MediaArtifact.id)
                .with_for_update()
            ).all()
        )

    found_asset_ids = {int(asset.id) for asset in assets}
    found_artifact_ids = {int(artifact.id) for artifact in artifacts}
    return {
        "schema": GENERATION_TEMPLATE_SNAPSHOT_SCHEMA,
        "draft": {
            "id": int(template.id),
            "organization_id": int(organization_id),
            "product_id": int(template.product_id),
            "sku": template.sku,
            "variant_key": template.variant_key,
            "status": template.status,
            "recipe_version": template.recipe_version,
            "platform": template.platform,
            "language": template.language,
            "character_image_path": template.character_image_path,
            "character_media_artifact_id": template.character_media_artifact_id,
            "character_image_filename": template.character_image_filename,
            "likeness_consent": bool(template.likeness_consent),
            "exact_variant_confirmed": bool(template.exact_variant_confirmed),
            "product_asset_ids_json": raw_asset_ids,
            "primary_product_asset_id": template.primary_product_asset_id,
            "product_info": template.product_info,
            "user_concept": template.user_concept,
            "creative_inputs_json": deepcopy(template.creative_inputs_json or {}),
            "duration_seconds": int(template.duration_seconds),
            "ratio": template.ratio,
            "audio_enabled": bool(template.audio_enabled),
            "estimated_credits": int(template.estimated_credits or 0),
            "provider_payload_preview_json": deepcopy(
                template.provider_payload_preview_json or {}
            ),
            "blockers_json": deepcopy(template.blockers_json or []),
            "warnings_json": deepcopy(template.warnings_json or []),
        },
        "product": {
            "id": int(product.id),
            "organization_id": int(organization_id),
            "sku": product.sku,
            "brand": product.brand,
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "attributes_json": deepcopy(product.attributes_json or {}),
            "benefits_json": deepcopy(product.benefits_json or []),
            "restrictions_json": deepcopy(product.restrictions_json or []),
        },
        "product_assets": [
            {
                "id": int(asset.id),
                "product_id": int(asset.product_id),
                "asset_kit_id": int(asset.asset_kit_id),
                "media_artifact_id": asset.media_artifact_id,
                "source_ref": asset.source_ref,
                "source_type": asset.source_type,
                "asset_type": asset.asset_type,
                "asset_role": asset.asset_role,
                "filename": asset.filename,
                "extension": asset.extension,
                "mime_type": asset.mime_type,
                "width": asset.width,
                "height": asset.height,
                "exists": bool(asset.exists),
                "status": asset.status,
                "is_primary_reference": bool(asset.is_primary_reference),
                "is_safe_for_real_generation": bool(asset.is_safe_for_real_generation),
                "manual_label": asset.manual_label,
                "review_status": asset.review_status,
                "review_notes": asset.review_notes,
                "checksum": asset.checksum,
                "metadata_json": deepcopy(asset.metadata_json or {}),
            }
            for asset in assets
        ],
        "missing_product_asset_ids": sorted(referenced_asset_ids - found_asset_ids),
        "media_artifacts": [
            {
                "id": int(artifact.id),
                "public_id": artifact.public_id,
                "organization_id": int(artifact.organization_id),
                "product_id": artifact.product_id,
                "kind": artifact.kind,
                "backend_name": artifact.backend_name,
                "bucket": artifact.bucket,
                "object_key": artifact.object_key,
                "object_version": artifact.object_version,
                "etag": artifact.etag,
                "original_filename": artifact.original_filename,
                "mime_type": artifact.mime_type,
                "size_bytes": int(artifact.size_bytes),
                "sha256": artifact.sha256,
                "status": artifact.status,
                "archived_at": _snapshot_datetime(artifact.archived_at),
                "delete_requested_at": _snapshot_datetime(
                    artifact.delete_requested_at
                ),
                "deleted_at": _snapshot_datetime(artifact.deleted_at),
            }
            for artifact in artifacts
        ],
        "missing_media_artifact_ids": sorted(
            referenced_artifact_ids - found_artifact_ids
        ),
    }


def _referenced_ids(values: list[object]) -> set[int]:
    return {
        parsed
        for value in values
        if (parsed := _coerce_positive_int(value)) is not None
    }


def _snapshot_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _positive_int(value: object, code: str) -> int:
    parsed = _coerce_positive_int(value)
    if parsed is None:
        _reject(code)
    return parsed


def _nonnegative_int(value: object, code: str) -> int:
    if isinstance(value, bool):
        _reject(code)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        _reject(code)
    if parsed < 0:
        _reject(code)
    return parsed


def _optional_positive_int(value: object, code: str) -> int | None:
    if value is None:
        return None
    return _positive_int(value, code)


def _sha256(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        _reject(code)
    return value


def _reject(code: str) -> None:
    raise ProductUGCSpendValidationError(
        f"Mass generation spend validation failed: {code}. Create a new preview and launch batch."
    )
