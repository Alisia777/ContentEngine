from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.public_pilot.auth import PublicPilotUser, get_current_public_user


router = APIRouter(prefix="/media", tags=["authorized-media"])


def get_active_media_user(
    user: PublicPilotUser = Depends(get_current_public_user),
) -> PublicPilotUser:
    if (
        not user.profile.is_active
        or user.profile.status != "active"
        or user.organization.status != "active"
        or user.membership.status != "active"
    ):
        raise HTTPException(status_code=403, detail="active_membership_required")
    return user


def resolve_media_file(source_ref: str | None) -> Path | None:
    """Resolve an existing regular file without ever escaping media_root.

    Stored media references are server-owned database values.  Resolving both
    the root and the candidate also prevents a symlink inside media_root from
    being used to expose a file outside it.
    """

    value = str(source_ref or "").strip()
    if not value or "\x00" in value:
        return None
    root = Path(get_settings().media_root)
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return resolved


def authorized_media_url(source_ref: str | None, route: str) -> str | None:
    """Return a scoped route only when its backing file is safe and present."""

    return route if resolve_media_file(source_ref) is not None else None


def video_output_url(video_job: models.VideoJob) -> str | None:
    return authorized_media_url(
        video_job.output_video_path,
        f"/media/video-jobs/{video_job.id}/output",
    )


def video_preview_url(video_job: models.VideoJob) -> str | None:
    return authorized_media_url(
        video_job.preview_path,
        f"/media/video-jobs/{video_job.id}/preview",
    )


def frame_contact_sheet_url(frame_result: models.FrameExtractionResult) -> str | None:
    return authorized_media_url(
        frame_result.contact_sheet_path,
        f"/media/frame-extractions/{frame_result.id}/contact-sheet",
    )


def frame_image_urls(frame_result: models.FrameExtractionResult) -> list[str]:
    urls: list[str] = []
    for index, source_ref in enumerate(frame_result.frame_paths_json or []):
        route = f"/media/frame-extractions/{frame_result.id}/frames/{index}"
        if authorized_media_url(str(source_ref), route):
            urls.append(route)
    return urls


def _not_found() -> HTTPException:
    # The same response covers an unknown id, another organization, an unsafe
    # stored path, and a missing file so callers cannot probe tenant data.
    return HTTPException(status_code=404, detail="media_not_found")


def _owned_video_job(
    db: Session,
    *,
    video_job_id: int,
    organization_id: int,
) -> models.VideoJob:
    owned_cycle = exists(
        select(models.ContentCycle.id).where(
            models.ContentCycle.video_job_id == models.VideoJob.id,
            models.ContentCycle.organization_id == organization_id,
        )
    )
    video_job = db.scalar(
        select(models.VideoJob).where(
            models.VideoJob.id == video_job_id,
            or_(
                models.VideoJob.organization_id == organization_id,
                and_(models.VideoJob.organization_id.is_(None), owned_cycle),
            ),
        )
    )
    if video_job is None:
        raise _not_found()
    return video_job


def _owned_draft(
    db: Session,
    *,
    draft_id: int,
    organization_id: int,
) -> models.ProductUGCRecipeDraft:
    draft = db.scalar(
        select(models.ProductUGCRecipeDraft)
        .join(models.Product, models.Product.id == models.ProductUGCRecipeDraft.product_id)
        .where(
            models.ProductUGCRecipeDraft.id == draft_id,
            models.Product.organization_id == organization_id,
        )
    )
    if draft is None:
        raise _not_found()
    return draft


def _file_response(source_ref: str | None) -> FileResponse:
    path = resolve_media_file(source_ref)
    if path is None:
        raise _not_found()
    return FileResponse(
        path,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _video_file_response(source_ref: str | None, request: Request) -> Response:
    path = resolve_media_file(source_ref)
    if path is None:
        raise _not_found()
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        raise _not_found() from exc
    range_header = str(request.headers.get("range") or "").strip()
    if not range_header:
        return FileResponse(
            path,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
    if match is None or file_size <= 0:
        raise HTTPException(
            status_code=416,
            detail="range_not_satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    raw_start, raw_end = match.groups()
    if not raw_start and not raw_end:
        raise HTTPException(
            status_code=416,
            detail="range_not_satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    if raw_start:
        start = int(raw_start)
        end = int(raw_end) if raw_end else file_size - 1
    else:
        suffix_length = int(raw_end)
        if suffix_length <= 0:
            raise HTTPException(
                status_code=416,
                detail="range_not_satisfiable",
                headers={"Content-Range": f"bytes */{file_size}"},
            )
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
    end = min(end, file_size - 1)
    if start < 0 or start >= file_size or end < start:
        raise HTTPException(
            status_code=416,
            detail="range_not_satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    content_length = end - start + 1

    def stream() -> Iterator[bytes]:
        remaining = content_length
        with path.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream(),
        status_code=206,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-store",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/video-jobs/{video_job_id}/output")
def authorized_video_output(
    video_job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> Response:
    video_job = _owned_video_job(
        db,
        video_job_id=video_job_id,
        organization_id=user.organization.id,
    )
    return _video_file_response(video_job.output_video_path, request)


@router.get("/video-jobs/{video_job_id}/preview")
def authorized_video_preview(
    video_job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> Response:
    video_job = _owned_video_job(
        db,
        video_job_id=video_job_id,
        organization_id=user.organization.id,
    )
    return _video_file_response(video_job.preview_path, request)


@router.get(
    "/frame-extractions/{frame_extraction_result_id}/contact-sheet",
    response_class=FileResponse,
)
def authorized_contact_sheet(
    frame_extraction_result_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    frame_result = db.get(models.FrameExtractionResult, frame_extraction_result_id)
    if frame_result is None:
        raise _not_found()
    _owned_video_job(
        db,
        video_job_id=frame_result.video_job_id,
        organization_id=user.organization.id,
    )
    return _file_response(frame_result.contact_sheet_path)


@router.get(
    "/frame-extractions/{frame_extraction_result_id}/frames/{frame_index}",
    response_class=FileResponse,
)
def authorized_extracted_frame(
    frame_extraction_result_id: int,
    frame_index: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    frame_result = db.get(models.FrameExtractionResult, frame_extraction_result_id)
    if frame_result is None:
        raise _not_found()
    _owned_video_job(
        db,
        video_job_id=frame_result.video_job_id,
        organization_id=user.organization.id,
    )
    frame_paths = list(frame_result.frame_paths_json or [])
    if frame_index < 0 or frame_index >= len(frame_paths):
        raise _not_found()
    return _file_response(str(frame_paths[frame_index]))


@router.get("/product-ugc-drafts/{draft_id}/character", response_class=FileResponse)
def authorized_draft_character(
    draft_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    draft = _owned_draft(
        db,
        draft_id=draft_id,
        organization_id=user.organization.id,
    )
    return _file_response(draft.character_image_path)


@router.get(
    "/product-ugc-drafts/{draft_id}/outputs/{output_index}",
    response_class=FileResponse,
)
def authorized_draft_output(
    draft_id: int,
    output_index: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    draft = _owned_draft(
        db,
        draft_id=draft_id,
        organization_id=user.organization.id,
    )
    output_paths = list(draft.local_output_paths_json or [])
    if output_index < 0 or output_index >= len(output_paths):
        raise _not_found()
    return _file_response(str(output_paths[output_index]))


@router.get(
    "/product-ugc-drafts/{draft_id}/generation-report",
    response_class=FileResponse,
)
def authorized_generation_report(
    draft_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    draft = _owned_draft(
        db,
        draft_id=draft_id,
        organization_id=user.organization.id,
    )
    return _file_response(draft.generation_report_path)


@router.get("/product-assets/{asset_id}/source", response_class=FileResponse)
def authorized_product_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_active_media_user),
) -> FileResponse:
    asset = db.scalar(
        select(models.ProductAsset)
        .join(models.Product, models.Product.id == models.ProductAsset.product_id)
        .where(
            models.ProductAsset.id == asset_id,
            models.ProductAsset.source_type == "local",
            models.Product.organization_id == user.organization.id,
        )
    )
    if asset is None:
        raise _not_found()
    return _file_response(asset.source_ref)
