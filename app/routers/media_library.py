from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select
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
MEDIA_FOLDERS = (
    {
        "slug": "all",
        "label": "Все материалы",
        "detail": "Вся доступная библиотека",
        "kinds": None,
    },
    {
        "slug": "generated",
        "label": "Готовые видео",
        "detail": "Результаты генерации и мастер-файлы",
        "kinds": ("provider_output", "master_video"),
    },
    {
        "slug": "references",
        "label": "Исходники",
        "detail": "Фото товара и референсы креатора",
        "kinds": ("product_reference", "creator_reference"),
    },
    {
        "slug": "previews",
        "label": "Обложки и превью",
        "detail": "Быстрый просмотр материалов",
        "kinds": ("video_preview", "thumbnail"),
    },
    {
        "slug": "quality",
        "label": "Проверка качества",
        "detail": "Кадры, контакт-листы и отчёты",
        "kinds": ("quality_frame", "contact_sheet", "generation_report"),
    },
    {
        "slug": "publishing",
        "label": "Для размещения",
        "detail": "Подготовленные экспортные файлы",
        "kinds": ("publishing_export",),
    },
)
MEDIA_FOLDER_BY_SLUG = {item["slug"]: item for item in MEDIA_FOLDERS}
MEDIA_PAGE_SIZE = 60


def _file_count_label(value: int) -> str:
    count = max(int(value), 0)
    if count % 10 == 1 and count % 100 != 11:
        noun = "файл"
    elif count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        noun = "файла"
    else:
        noun = "файлов"
    return f"{count} {noun}"


def get_media_artifact_service(db: Session = Depends(get_db)) -> MediaArtifactService:
    return MediaArtifactService(db, get_storage_backends())


@router.get("/media-library", response_class=HTMLResponse)
def media_library_page(
    request: Request,
    product_id: int | None = None,
    creator_id: int | None = None,
    kind: str | None = None,
    folder: str = "all",
    include_archived: bool = False,
    page: int = Query(1, ge=1, le=10_000),
    package_id: int | None = None,
    reviewed: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
    service: MediaArtifactService = Depends(get_media_artifact_service),
) -> HTMLResponse:
    team_media_access = str(user.role).casefold() in {"owner", "admin"}
    if not team_media_access and creator_id not in {None, user.profile.id}:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter")
    selected_folder = str(folder or "all").strip().lower()
    folder_definition = MEDIA_FOLDER_BY_SLUG.get(selected_folder)
    if folder_definition is None:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter")
    selected_kind = str(kind or "").strip().lower()
    folder_kinds = folder_definition["kinds"]
    if selected_kind and folder_kinds is not None and selected_kind not in folder_kinds:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter")
    effective_kinds = (selected_kind,) if selected_kind else folder_kinds
    try:
        total_artifacts = service.count_owned(
            organization_id=user.organization.id,
            product_id=product_id,
            created_by_user_profile_id=creator_id,
            kinds=effective_kinds,
            include_archived=include_archived,
            visible_to_user_profile_id=(None if team_media_access else user.profile.id),
        )
        artifact_page = service.list_owned(
            organization_id=user.organization.id,
            product_id=product_id,
            created_by_user_profile_id=creator_id,
            kinds=effective_kinds,
            include_archived=include_archived,
            limit=MEDIA_PAGE_SIZE + 1,
            offset=(page - 1) * MEDIA_PAGE_SIZE,
            visible_to_user_profile_id=(None if team_media_access else user.profile.id),
        )
    except MediaArtifactError as exc:
        raise HTTPException(status_code=400, detail="invalid_media_library_filter") from exc
    has_next_page = len(artifact_page) > MEDIA_PAGE_SIZE
    artifacts = artifact_page[:MEDIA_PAGE_SIZE]

    def library_url(*, target_page: int, target_folder: str = selected_folder, keep_kind: bool = True) -> str:
        parameters: list[tuple[str, str]] = [
            ("folder", target_folder),
            ("include_archived", "true" if include_archived else "false"),
            ("page", str(target_page)),
        ]
        if product_id is not None:
            parameters.append(("product_id", str(product_id)))
        if team_media_access and creator_id is not None:
            parameters.append(("creator_id", str(creator_id)))
        if keep_kind and selected_kind:
            parameters.append(("kind", selected_kind))
        return f"/media-library?{urlencode(parameters)}"

    folder_views = [
        {
            **item,
            "selected": item["slug"] == selected_folder,
            "url": library_url(
                target_page=1,
                target_folder=str(item["slug"]),
                keep_kind=False,
            ),
        }
        for item in MEDIA_FOLDERS
    ]
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
    draft_ids = {
        artifact.product_ugc_recipe_draft_id
        for artifact in artifacts
        if artifact.product_ugc_recipe_draft_id is not None
    }
    draft_map = {
        draft.id: draft
        for draft in (
            db.scalars(
                select(models.ProductUGCRecipeDraft).where(
                    models.ProductUGCRecipeDraft.id.in_(draft_ids)
                )
            ).all()
            if draft_ids
            else []
        )
    }
    approved_task_artifact_ids = {
        task.media_artifact_id
        for task in (
            db.scalars(
                select(models.CreatorTask).where(
                    models.CreatorTask.organization_id == user.organization.id,
                    models.CreatorTask.media_artifact_id.in_(
                        [artifact.id for artifact in artifacts]
                    ),
                    models.CreatorTask.task_type == "review_generated_video",
                    models.CreatorTask.status == "done",
                )
            ).all()
            if artifacts
            else []
        )
        if task.media_artifact_id is not None
        and dict(task.result_json or {}).get("review_decision") == "approve"
        and dict(task.result_json or {}).get("media_artifact_public_id")
        == next(
            (
                artifact.public_id
                for artifact in artifacts
                if artifact.id == task.media_artifact_id
            ),
            None,
        )
    }
    ready_video_counts = {
        draft_id: (int(count), int(artifact_id))
        for draft_id, count, artifact_id in (
            db.execute(
                select(
                    models.MediaArtifact.product_ugc_recipe_draft_id,
                    func.count(models.MediaArtifact.id),
                    func.min(models.MediaArtifact.id),
                )
                .where(
                    models.MediaArtifact.organization_id == user.organization.id,
                    models.MediaArtifact.product_ugc_recipe_draft_id.in_(draft_ids),
                    models.MediaArtifact.kind.in_(PUBLISHABLE_MEDIA_ARTIFACT_KINDS),
                    models.MediaArtifact.mime_type.like("video/%"),
                    models.MediaArtifact.size_bytes > 0,
                    models.MediaArtifact.status == "ready",
                    models.MediaArtifact.archived_at.is_(None),
                    models.MediaArtifact.delete_requested_at.is_(None),
                    models.MediaArtifact.deleted_at.is_(None),
                )
                .group_by(models.MediaArtifact.product_ugc_recipe_draft_id)
            ).all()
            if draft_ids
            else []
        )
    }

    def product_ugc_review_ready(artifact: models.MediaArtifact) -> bool:
        if artifact.product_ugc_recipe_draft_id is None:
            return True
        draft = draft_map.get(artifact.product_ugc_recipe_draft_id)
        if (
            draft is None
            or draft.human_review_status != "approved"
            or draft.publishing_readiness != "ready_for_publishing_package"
            or bool(draft.blockers_json)
            or ready_video_counts.get(draft.id) != (1, artifact.id)
            or str((artifact.metadata_json or {}).get("provider_task_id") or "")
            != str(draft.provider_task_id or "")
        ):
            return False
        approved_identity = dict(draft.creative_inputs_json or {}).get(
            "approved_media_artifact_v1"
        )
        marker_matches = bool(
            isinstance(approved_identity, dict)
            and approved_identity.get("media_artifact_id") == artifact.id
            and approved_identity.get("public_id") == artifact.public_id
            and approved_identity.get("sha256") == artifact.sha256
        )
        return marker_matches or artifact.id in approved_task_artifact_ids
    can_approve = (
        str(user.role).casefold() in PublishingPackageService.ARTIFACT_APPROVER_ROLES
    )
    views = [
        {
            "artifact": artifact,
            "product": product_map.get(artifact.product_id),
            "creator": creator_map.get(
                (
                    draft_map.get(artifact.product_ugc_recipe_draft_id).assigned_to_user_profile_id
                    if draft_map.get(artifact.product_ugc_recipe_draft_id) is not None
                    else None
                )
                or artifact.created_by_user_profile_id
            ),
            "is_video": artifact.mime_type.startswith("video/"),
            "is_image": artifact.mime_type.startswith("image/"),
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
                and product_ugc_review_ready(artifact)
            ),
            "package_blocker": (
                "Сначала одобрите именно этот результат после новой успешной генерации."
                if artifact.product_ugc_recipe_draft_id is not None
                and not product_ugc_review_ready(artifact)
                else None
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
    reviewed_artifact = next(
        (
            artifact
            for artifact in artifacts
            if reviewed and artifact.public_id == reviewed
            and product_ugc_review_ready(artifact)
        ),
        None,
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
            "selected_kind": selected_kind,
            "selected_folder": selected_folder,
            "media_folders": folder_views,
            "include_archived": include_archived,
            "page": page,
            "total_artifacts": total_artifacts,
            "artifact_count_label": _file_count_label(total_artifacts),
            "page_start": ((page - 1) * MEDIA_PAGE_SIZE + 1 if artifacts else 0),
            "page_end": ((page - 1) * MEDIA_PAGE_SIZE + len(artifacts)),
            "previous_page_url": (
                library_url(target_page=page - 1) if page > 1 else None
            ),
            "next_page_url": (
                library_url(target_page=page + 1) if has_next_page else None
            ),
            "created_package": created_package,
            "reviewed_artifact": reviewed_artifact,
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
