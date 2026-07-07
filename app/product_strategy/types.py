from __future__ import annotations

from pydantic import BaseModel, Field


class ProductStrategyStatus(BaseModel):
    product_id: int
    sku: str
    status: str
    product_strategy_spec_id: int | None = None
    offer_strategy_id: int | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ProductStrategySpecOutput(BaseModel):
    id: int
    product_id: int
    sku: str
    status: str
    buyer_segment: dict
    buyer_situation: dict
    purchase_trigger: str | None = None
    main_pain: str | None = None
    main_desire: str | None = None
    main_objection: str | None = None
    product_role: str | None = None
    category_alternative: str | None = None
    competitor_context: dict
    price_position: dict
    stock_context: dict
    offer_strategy: dict
    proof_required: list
    safe_claims: list
    forbidden_claims: list
    platform_strategy: dict
    content_angles: list
    warnings: list


class OfferStrategyOutput(BaseModel):
    id: int
    product_strategy_spec_id: int
    product_id: int
    sku: str
    status: str
    offer_type: str
    price_message: str | None = None
    discount_message: str | None = None
    value_reason: str | None = None
    competitor_response: str | None = None
    stock_warning: str | None = None
    cta_strategy: str | None = None
    warnings: list
