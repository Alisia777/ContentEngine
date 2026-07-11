from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.public_pilot.auth import PublicPilotUser, get_current_public_user
from app.runway_recipes import ProductUGCRecipeService, RunwayRecipeError


router = APIRouter(prefix="/api/public-pilot", tags=["public-pilot-api"])


@router.get("/product-ugc/{draft_id}")
def get_owned_product_ugc_status(
    draft_id: int,
    db: Session = Depends(get_db),
    user: PublicPilotUser = Depends(get_current_public_user),
) -> dict[str, object]:
    try:
        service = ProductUGCRecipeService(db)
        draft = service.get(draft_id)
    except RunwayRecipeError as exc:
        raise HTTPException(status_code=404, detail="product_ugc_draft_not_found") from exc
    if draft.product.organization_id != user.organization.id:
        raise HTTPException(status_code=404, detail="product_ugc_draft_not_found")
    return service.output(draft).model_dump(mode="json")
