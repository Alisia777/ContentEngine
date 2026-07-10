from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.interface_productization import InterfaceProductizationError, MVPLaunchWizardService, MVPWorkspaceService
from app.product_asset_contract import ProductAssetClassifier
from app.product_asset_contract.reference_requirement_service import product_profile, product_variant_key
from app.public_pilot.access import PublicPilotAccessService
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.public_pilot.control_room import PublicPilotControlRoomService
from app.public_pilot.gate_matrix import ACTION_LABELS, PublicPilotGateMatrix, TRAINING_ATTEMPT
from app.runway_recipes import ProductImageUpload, ProductUGCRecipeService, RunwayRecipeError
from app.ui import templates

router = APIRouter(tags=["public-pilot"])


def _media_url(source_ref: str) -> str | None:
    path = Path(source_ref)
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        relative = path.resolve().relative_to(get_settings().media_root.resolve())
    except (OSError, ValueError):
        return None
    return "/media/" + relative.as_posix()


@router.get("/login", response_class=HTMLResponse)
def public_login(request: Request, error: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        "public_login.html",
        {"request": request, "page_title": "ALTEA Public Pilot Login", "error": error},
    )


@router.post("/login")
def public_login_submit(email: str = Form(...), password: str = Form(...)) -> RedirectResponse:
    settings = get_settings()
    if not settings.auth_required:
        return RedirectResponse("/control-room", status_code=303)
    if not settings.supabase_url:
        return RedirectResponse("/login?error=supabase_not_configured", status_code=303)
    if not password:
        return RedirectResponse("/login?error=password_required", status_code=303)
    # Real Supabase password exchange is intentionally not performed in tests/local acceptance.
    return RedirectResponse("/login?error=oauth_exchange_not_configured_locally", status_code=303)


@router.post("/logout")
def public_logout() -> RedirectResponse:
    settings = get_settings()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response


@router.get("/control-room", response_class=HTMLResponse)
def control_room(
    request: Request,
    role: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    context = PublicPilotControlRoomService(db).context(user, role=role)
    return templates.TemplateResponse(
        "public_control_room.html",
        {"request": request, "page_title": "ALTEA Control Room", **context},
    )


@router.get("/workbench", response_class=HTMLResponse)
def mvp_workbench(
    request: Request,
    tab: str = "product",
    role: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    selected_role = role or (user.role if user.role in {"owner", "admin", "reviewer", "operator"} else "owner")
    service = MVPWorkspaceService(db)
    snapshot = service.output(service.build(role=selected_role))
    allowed_tabs = {item.key for item in snapshot.module_links}
    selected_tab = tab if tab in allowed_tabs else "product"
    return templates.TemplateResponse(
        "public_workbench.html",
        {
            "request": request,
            "page_title": "ALTEA Рабочая область",
            "user": user,
            "role": selected_role,
            "workspace": snapshot,
            "selected_tab": selected_tab,
        },
    )


@router.get("/mvp-launch", response_class=HTMLResponse)
def mvp_launch(
    request: Request,
    run_id: int | None = None,
    product_id: int | None = None,
    recipe_draft_id: int | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    service = MVPLaunchWizardService(db)
    run_output = None
    if run_id:
        try:
            run_output = service.output(service.get(run_id))
        except InterfaceProductizationError as exc:
            error = str(exc)
    products = list(db.scalars(select(models.Product).order_by(models.Product.id.desc()).limit(50)))
    recipe_service = ProductUGCRecipeService(db)
    recipe_draft = None
    selected_product = db.get(models.Product, product_id) if product_id else None
    if recipe_draft_id:
        try:
            recipe_record = recipe_service.get(recipe_draft_id)
            recipe_draft = recipe_service.output(recipe_record)
            selected_product = recipe_record.product
        except RunwayRecipeError as exc:
            error = str(exc)
    assets = []
    if selected_product:
        classifier = ProductAssetClassifier()
        expected_variant = product_variant_key(selected_product)
        for asset in db.scalars(
            select(models.ProductAsset)
            .where(models.ProductAsset.product_id == selected_product.id)
            .order_by(models.ProductAsset.is_primary_reference.desc(), models.ProductAsset.id.desc())
        ):
            classification = classifier.classify(asset, expected_variant_key=expected_variant)
            assets.append(
                {
                    "id": asset.id,
                    "filename": asset.filename or Path(asset.source_ref).name,
                    "contract_type": classification.contract_type,
                    "review_status": asset.review_status,
                    "variant_status": classification.variant_status,
                    "is_primary": asset.is_primary_reference,
                    "media_url": _media_url(asset.source_ref) if asset.source_type == "local" else asset.source_ref,
                }
            )
    selected_profile = product_profile(selected_product) if selected_product else None
    selected_variant = product_variant_key(selected_product) if selected_product else None
    return templates.TemplateResponse(
        "public_mvp_launch.html",
        {
            "request": request,
            "page_title": "ContentEngine · Product UGC",
            "user": user,
            "role": user.role,
            "run": run_output,
            "products": products,
            "selected_product": selected_product,
            "selected_profile": selected_profile,
            "selected_variant": selected_variant,
            "product_assets": assets,
            "recipe_draft": recipe_draft,
            "default_product_info": recipe_service.default_product_info(selected_product, selected_variant) if selected_product else "",
            "error": error,
        },
    )


@router.post("/mvp-launch/product-ugc-draft")
async def product_ugc_recipe_draft(
    product_id: int = Form(...),
    variant_key: str = Form(...),
    existing_asset_ids: list[int] = Form([]),
    primary_asset_id: int | None = Form(None),
    front_image: UploadFile | None = File(None),
    angle_image: UploadFile | None = File(None),
    scale_image: UploadFile | None = File(None),
    proof_image: UploadFile | None = File(None),
    character_image: UploadFile = File(...),
    product_info: str = Form(""),
    task: str = Form(...),
    creator_profile: str = Form(...),
    setting: str = Form(...),
    hook: str = Form(...),
    product_action: str = Form(...),
    proof_moment: str = Form(...),
    spoken_message: str = Form(""),
    cta: str = Form(...),
    forbidden_visuals: str = Form(""),
    interaction_mode: str = Form("presentation"),
    platform: str = Form("Instagram Reels"),
    duration: int = Form(15),
    ratio: str = Form("720:1280"),
    audio_enabled: bool = Form(False),
    likeness_consent: bool = Form(False),
    exact_variant_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user
    product = db.get(models.Product, product_id)
    if not product:
        return RedirectResponse(f"/mvp-launch?error={quote('Товар не найден')}", status_code=303)
    proof_type = {
        "food_snack": "cutaway_product",
        "cosmetic": "application_demo",
        "apparel": "on_body",
        "household": "application_demo",
        "general": "application_context",
    }[product_profile(product)]
    upload_specs = [
        ("Главный вид", front_image, "front_packshot", True),
        ("Второй ракурс", angle_image, "angled_product", False),
        ("Масштаб / в руке", scale_image, "product_in_hand", False),
        ("Доказательство применения", proof_image, proof_type, False),
    ]
    uploads: list[ProductImageUpload] = []
    for slot, upload, contract_type, primary in upload_specs:
        if upload and upload.filename:
            uploads.append(
                ProductImageUpload(
                    slot=slot,
                    filename=upload.filename,
                    content=await upload.read(),
                    contract_type=contract_type,
                    primary=primary,
                )
            )
    try:
        draft = ProductUGCRecipeService(db).create_draft(
            product_id=product_id,
            variant_key=variant_key,
            character_filename=character_image.filename or "creator.png",
            character_content=await character_image.read(),
            existing_asset_ids=existing_asset_ids,
            primary_asset_id=primary_asset_id,
            product_uploads=uploads,
            product_info=product_info,
            task=task,
            creator_profile=creator_profile,
            setting=setting,
            hook=hook,
            product_action=product_action,
            proof_moment=proof_moment,
            spoken_message=spoken_message,
            cta=cta,
            forbidden_visuals=forbidden_visuals,
            interaction_mode=interaction_mode,
            platform=platform,
            duration=duration,
            ratio=ratio,
            audio=audio_enabled,
            likeness_consent=likeness_consent,
            exact_variant_confirmed=exact_variant_confirmed,
        )
    except RunwayRecipeError as exc:
        return RedirectResponse(
            f"/mvp-launch?product_id={product_id}&error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(
        f"/mvp-launch?product_id={product_id}&recipe_draft_id={draft.id}",
        status_code=303,
    )


@router.post("/mvp-launch/start")
def mvp_launch_start(
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user
    run = MVPLaunchWizardService(db).start(product_id=product_id, sku=sku or None)
    return RedirectResponse(f"/mvp-launch?run_id={run.id}", status_code=303)


@router.post("/mvp-launch/{run_id}/next")
def mvp_launch_next(
    run_id: int,
    product_id: int | None = Form(None),
    sku: str | None = Form(None),
    runway_credits_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> RedirectResponse:
    del user
    try:
        MVPLaunchWizardService(db).advance(
            run_id,
            product_id=product_id,
            sku=sku or None,
            runway_credits_confirmed=runway_credits_confirmed,
        )
    except InterfaceProductizationError:
        return RedirectResponse("/mvp-launch?error=run_not_found", status_code=303)
    return RedirectResponse(f"/mvp-launch?run_id={run_id}", status_code=303)


@router.get("/settings/access", response_class=HTMLResponse)
def settings_access(
    request: Request,
    user: PublicPilotUser = Depends(get_current_public_user),
) -> HTMLResponse:
    settings = get_settings()
    matrix_service = PublicPilotGateMatrix(strict_training=settings.public_pilot_strict_training_gates)
    return templates.TemplateResponse(
        "settings_access.html",
        {
            "request": request,
            "page_title": "Access Gates",
            "user": user,
            "roles": matrix_service.matrix().get("settings_view", {}).keys(),
            "matrix": matrix_service.matrix(),
            "summary": matrix_service.summary(),
            "action_labels": ACTION_LABELS,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_redirect() -> RedirectResponse:
    return RedirectResponse("/settings/access", status_code=302)


@router.post("/control-room/training/{module_code}/submit")
def complete_training(
    module_code: str,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
):
    service = PublicPilotAccessService(db)
    service.require_action(
        user_profile_id=user.profile.id,
        organization_id=user.organization.id,
        role=user.role,
        action=TRAINING_ATTEMPT,
        payload={"module_code": module_code},
    )
    try:
        cert = service.grant_certification(user.profile.id, module_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"module_code": module_code, "certification_id": cert.id, "status": cert.status}

