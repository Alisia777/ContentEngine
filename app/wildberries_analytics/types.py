from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class WildberriesHistoryMetric:
    nm_id: str
    metric_date: date
    open_count: int
    cart_count: int
    order_count: int
    order_sum_minor: int
    buyout_count: int
    buyout_sum_minor: int
    buyout_percent: float
    add_to_cart_percent: float
    cart_to_order_percent: float
    product_json: dict[str, Any]
    history_json: dict[str, Any]

    def raw_row(self) -> dict[str, Any]:
        return {"product": self.product_json, "history": self.history_json}


@dataclass(frozen=True)
class WildberriesCollection:
    request_bodies: tuple[dict[str, Any], ...]
    response_payloads: tuple[dict[str, Any], ...]
    metrics: tuple[WildberriesHistoryMetric, ...]
    response_product_count: int


@dataclass(frozen=True)
class WildberriesSyncResult:
    status: str
    audit_id: int
    page_count: int
    requested_nm_id_count: int
    response_product_count: int
    snapshot_count: int
    new_snapshot_count: int
    quarantine_count: int
    replayed: bool = False
