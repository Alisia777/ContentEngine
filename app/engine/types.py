from typing import Any

from pydantic import BaseModel, Field


class EngineStepResult(BaseModel):
    step_name: str
    status: str
    entity_type: str | None = None
    entity_id: int | None = None
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class EngineRunResult(BaseModel):
    status: str
    product_id: int | None = None
    script_job_id: int | None = None
    script_variant_id: int | None = None
    video_job_id: int | None = None
    publishing_package_id: int | None = None
    publishing_job_id: int | None = None
    analytics_id: int | None = None
    steps: list[EngineStepResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

