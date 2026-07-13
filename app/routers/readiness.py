from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.readiness import ApplicationReadinessService


router = APIRouter(tags=["health"])


@router.get("/ready", include_in_schema=False)
def ready() -> JSONResponse:
    result = ApplicationReadinessService().check()
    return JSONResponse(result.payload(), status_code=200 if result.ready else 503)
