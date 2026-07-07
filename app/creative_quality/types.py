from __future__ import annotations

from pydantic import BaseModel


class CreativeQualityComponentScore(BaseModel):
    key: str
    label: str
    score: float
    max_score: int
    passed: bool


class CreativeQualityScoreOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    product_strategy_spec_id: int | None = None
    blogger_meaning_spec_id: int | None = None
    ugc_script_id: int | None = None
    creative_variant_id: int | None = None
    prompt_pack_id: int | None = None
    status: str
    total_score: float
    breakdown: list[CreativeQualityComponentScore]
    reasons: list[str]
    required_fixes: list[str]


class CreativeQualityGateStatus(BaseModel):
    product_id: int
    sku: str
    ugc_script_id: int | None = None
    quality_score_id: int | None = None
    status: str
    real_smoke_allowed: bool
    next_action: str
    blockers: list[str]
    warnings: list[str]
    reference_policy: dict
    creative_quality_score: dict | None = None
    rewrite_request_id: int | None = None


class CreativeRewriteBuildResult(BaseModel):
    rewrite_request_id: int
    source_ugc_script_id: int
    new_ugc_script_id: int
    status: str
    required_fixes: list[str]
    before_lines: list[str]
    after_lines: list[str]
