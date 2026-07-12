from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.media_storage import (
    LocalStorage,
    MediaArtifactError,
    MediaArtifactOwnershipError,
    MediaArtifactService,
    MediaArtifactStateError,
    get_storage_backends,
)
from app.public_pilot.auth import (
    PublicPilotUser,
    form_csrf_token,
    get_current_public_user,
    require_form_csrf,
)
from app.publishing import PublishingPackageService
from app.publishing.errors import (
    PublishingAuthorizationError,
    PublishingSourceNotFound,
    PublishingSourceStateError,
)
from app.publishing.types import PUBLISHABLE_MEDIA_ARTIFACT_KINDS
from app.ui import templates


router = APIRouter(tags=["media-library"])


def get_media_artifact_service(db: Session = Depends(get_db)) -> MediaArtifactService:
    return MediaArtifactService(db, get_storage_backends())


@router.get("/media-library", response_class=HTMLResponse)
def media_library_page(
    request: Request,
    product_id: int | None = None,
    creator_id: int | None = None,
    kind: str | None = None,
    include_archived: bool = True,
    package_id: int | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: MediaArtifactService = Depends(get_media_artifact_service),
) -> HTMLResponse:
    team_media_access = str(user.role).casefold() in {"owner", "admin"}
    if not team_media_access and creator_id not in {None, user.profile.id}:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter")
    try:
        artifacts = service.list_owned(
            organization_id=user.organization.id,
            product_id=product_id,
            created_by_user_profile_id=creator_id,
            kind=kind or None,
            include_archived=include_archived,
            limit=200,
            visible_to_user_profile_id=(None if team_media_access else user.profile.id),
        )
    except MediaArtifactError as exc:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter") from exc
    products = list(
        db.scalars(
            select(models.Product)
            .where(models.Product.organization_id == user.organization.id)
            .order_by(models.Product.title, models.Product.id)
        )
    )
    creators = (
        list(
            db.scalars(
                select(models.UserProfile)
                .join(models.Membership, models.Membership.user_profile_id == models.UserProfile.id)
                .where(
                    models.Membership.organization_id == user.organization.id,
                    models.Membership.status == "active",
                )
                .order_by(models.UserProfile.display_name, models.UserProfile.email)
            )
        )
        if team_media_access
        else [user.profile]
    )
    product_map = {item.id: item for item in products}
    creator_map = {item.id: item for item in creators}
    can_approve = (
        str(user.role).casefold() in PublishingPackageService.ARTIFACT_APPROVER_ROLES
    )
    views = [
        {
            "artifact": artifact,
            "product": product_map.get(artifact.product_id),
            "creator": creator_map.get(artifact.created_by_user_profile_id),
            "is_video": artifact.mime_type.startswith("video/"),
            "size_mb": round(float(artifact.size_bytes or 0) / 1_048_576, 2),
            "can_create_package": (
                can_approve
                and artifact.status == "ready"
                and artifact.archived_at is None
                and artifact.delete_requested_at is None
                and artifact.deleted_at is None
                and artifact.product_id is not None
                and artifact.kind in PUBLISHABLE_MEDIA_ARTIFACT_KINDS
                and artifact.mime_type.startswith("video/")
            ),
        }
        for artifact in artifacts
    ]
    created_package = (
        db.scalar(
            select(models.PublishingPackage).where(
                models.PublishingPackage.id == package_id,
                models.PublishingPackage.organization_id == user.organization.id,
            )
        )
        if package_id is not None
        else None
    )
    return templates.TemplateResponse(
        request,
        "media_library.html",
        {
            "request": request,
            "page_title": "Контент ИИ Завод · Библиотека",
            "active_page": "media-library",
            "user": user,
            "role": user.role,
            "form_csrf_token": form_csrf_token(request),
            "artifact_views": views,
            "products": products,
            "creators": creators,
            "selected_product_id": product_id,
            "selected_creator_id": creator_id,
            "selected_kind": kind or "",
            "include_archived": include_archived,
            "created_package": created_package,
            "team_media_access": team_media_access,
        },
    )


@router.post("/media-library/{public_id}/publishing-package")
def create_media_artifact_publishing_package(
    public_id: str,
    request: Request,
    platform: str = Form(...),
    confirm_human_review: bool = Form(False),
    csrf_token: str = Form(""),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: MediaArtifactService = Depends(get_media_artifact_service),
) -> RedirectResponse:
    require_form_csrf(request, csrf_token)
    try:
        service.require_view_access(
            public_id,
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            allow_team_scope=str(user.role).casefold() in {"owner", "admin"},
        )
    except (MediaArtifactOwnershipError, MediaArtifactStateError) as exc:
        raise HTTPException(status_code=404, detail="media_artifact_not_found") from exc
    try:
        package = PublishingPackageService(db).create_from_media_artifact(
            public_id=public_id,
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            platform=platform,
            confirm_human_review=confirm_human_review,
        )
    except PublishingSourceNotFound as exc:
        raise HTTPException(status_code=404, detail="media_artifact_not_found") from exc
    except PublishingAuthorizationError as exc:
        raise HTTPException(status_code=403, detail="publishing_approval_role_required") from exc
    except PublishingSourceStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/media-library?package_id={package.id}", status_code=303)


@router.get("/media-library/{public_id}/access")
def media_artifact_access(
    public_id: str,
    download: bool = False,
    expires_seconds: int = Query(300, ge=30, le=900),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: MediaArtifactService = Depends(get_media_artifact_service),
) -> RedirectResponse:
    try:
        signed_url = service.signed_get_url(
            public_id,
            organization_id=user.organization.id,
            actor_user_profile_id=user.profile.id,
            expires_seconds=expires_seconds,
            download=download,
            allow_team_scope=str(user.role).casefold() in {"owner", "admin"},
        )
    except (MediaArtifactOwnershipError, MediaArtifactStateError) as exc:
        # Cross-tenant, missing, corrupt, and deleted artifacts are intentionally
        # indistinguishable at the HTTP boundary.
        raise HTTPException(status_code=404, detail="media_artifact_not_found") from exc
    return RedirectResponse(
        signed_url,
        status_code=307,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/media-library/local/{bucket}/{object_key:path}", include_in_schema=False)
def local_signed_media_access(
    bucket: str,
    object_key: str,
    expires: int,
    disposition: str,
    signature: str,
) -> FileResponse:
    backends = get_storage_backends()
    backend = backends.get("local")
    if not isinstance(backend, LocalStorage) or backend.bucket != bucket:
        raise HTTPException(status_code=404, detail="media_artifact_not_found")
    try:
        valid = backend.validate_signed_get(
            object_key,
            expires_at=expires,
            disposition=disposition,
            signature=signature,
        )
        if not valid:
            raise HTTPException(status_code=404, detail="media_artifact_not_found")
        path = backend.path_for_key(object_key)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=404, detail="media_artifact_not_found") from exc
    return FileResponse(
        path,
        media_type=None,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )
