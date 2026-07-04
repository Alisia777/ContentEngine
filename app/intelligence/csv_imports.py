from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models


def import_csv_path(db: Session, model_name: str, path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return import_rows(db, model_name, rows)


def import_csv_text(db: Session, model_name: str, text: str) -> int:
    rows = list(csv.DictReader(text.splitlines()))
    return import_rows(db, model_name, rows)


def import_rows(db: Session, model_name: str, rows: list[dict[str, str]]) -> int:
    model = {
        "product_metrics": models.ProductMetricSnapshot,
        "creative_performance": models.CreativePerformanceSnapshot,
        "review_insights": models.ProductReviewInsight,
        "market_signals": models.MarketSignal,
    }[model_name]
    count = 0
    for row in rows:
        payload = _coerce_row(row)
        db.add(model(**payload))
        count += 1
    db.commit()
    return count


def _coerce_row(row: dict[str, str]) -> dict[str, Any]:
    payload = {}
    raw = dict(row)
    for key, value in row.items():
        if value == "":
            payload[key] = None
        elif key.endswith("_json") or key == "raw_json":
            payload[key] = json.loads(value)
        elif key in {"period_start", "period_end"}:
            payload[key] = datetime.fromisoformat(value).date()
        elif key == "posted_at":
            payload[key] = datetime.fromisoformat(value) if value else None
        elif key in {
            "views",
            "clicks",
            "add_to_cart",
            "orders",
            "ad_orders",
            "stock_qty",
            "returns_count",
            "reviews_count",
            "competitor_reviews_count",
            "account_id",
            "likes",
            "comments",
            "shares",
            "saves",
        }:
            payload[key] = int(value)
        elif key in {
            "revenue",
            "conversion_rate",
            "ctr",
            "avg_price",
            "discount_percent",
            "ad_spend",
            "ad_revenue",
            "days_of_stock",
            "returns_rate",
            "rating",
            "watch_time_seconds",
            "retention_rate",
            "competitor_price",
            "competitor_rating",
        }:
            payload[key] = float(value)
        else:
            payload[key] = value
    if "raw_json" not in payload:
        payload["raw_json"] = raw
    return payload

