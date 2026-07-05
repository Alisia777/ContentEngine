from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.campaign_autopilot.types import ProductMatrixImportResult


REQUIRED_HEADERS = {"sku", "product_name"}
SUPPORTED_HEADERS = {
    "sku",
    "product_name",
    "category",
    "price",
    "stock_qty",
    "product_url",
    "photo_1",
    "photo_2",
    "photo_3",
    "priority",
}


class ProductMatrixImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_path(self, path: str | Path) -> ProductMatrixImportResult:
        file_path = Path(path)
        data = file_path.read_text(encoding="utf-8-sig")
        return self.import_csv_text(data, source_file=file_path.as_posix())

    def import_csv_text(self, text: str, *, source_file: str = "product_matrix.csv") -> ProductMatrixImportResult:
        rows = list(csv.DictReader(io.StringIO(text)))
        matrix_import = models.ProductMatrixImport(
            source_file=source_file,
            status="importing",
            imported_count=0,
            error_count=0,
            warnings_json=[],
            errors_json=[],
        )
        self.db.add(matrix_import)
        self.db.flush()
        warnings: list[str] = []
        errors: list[str] = []
        seen_skus: set[str] = set()
        for line_number, raw in enumerate(rows, start=2):
            row = {self._normalize(key): value for key, value in raw.items()}
            missing = [header for header in REQUIRED_HEADERS if not str(row.get(header) or "").strip()]
            if missing:
                errors.append(f"row_{line_number}:missing_required:{','.join(missing)}")
                continue
            sku = str(row["sku"]).strip()
            if sku in seen_skus:
                warning = f"row_{line_number}:duplicate_sku_skipped:{sku}"
                warnings.append(warning)
                continue
            existing = self.db.scalar(
                select(models.ProductMatrixRow)
                .where(models.ProductMatrixRow.import_id == matrix_import.id, models.ProductMatrixRow.sku == sku)
                .order_by(models.ProductMatrixRow.id.desc())
            )
            if existing:
                warnings.append(f"row_{line_number}:duplicate_sku_updated:{sku}")
            seen_skus.add(sku)
            row_warnings = self._warnings(row)
            warnings.extend(f"row_{line_number}:{warning}" for warning in row_warnings)
            photos = [
                str(row.get(key)).strip()
                for key in ["photo_1", "photo_2", "photo_3"]
                if str(row.get(key) or "").strip()
            ]
            payload = {
                "import_id": matrix_import.id,
                "sku": sku,
                "product_name": str(row["product_name"]).strip(),
                "category": self._text(row.get("category")),
                "price": self._float(row.get("price")),
                "stock_qty": self._int(row.get("stock_qty")),
                "product_url": self._text(row.get("product_url")),
                "photo_urls_json": photos,
                "priority": self._int(row.get("priority")) or 1,
                "raw_json": {"row_number": line_number, "source": {key: row.get(key) for key in sorted(SUPPORTED_HEADERS) if key in row}},
                "status": "imported_with_warnings" if row_warnings else "imported",
                "warnings_json": row_warnings,
            }
            if existing:
                for field, value in payload.items():
                    setattr(existing, field, value)
            else:
                self.db.add(models.ProductMatrixRow(**payload))
        self.db.flush()
        imported_count = self.db.query(models.ProductMatrixRow).filter_by(import_id=matrix_import.id).count()
        matrix_import.imported_count = imported_count
        matrix_import.error_count = len(errors)
        matrix_import.warnings_json = list(dict.fromkeys(warnings))
        matrix_import.errors_json = errors
        matrix_import.status = "imported_with_errors" if errors else ("imported_with_warnings" if warnings else "imported")
        self.db.commit()
        self.db.refresh(matrix_import)
        return ProductMatrixImportResult(
            import_id=matrix_import.id,
            source_file=matrix_import.source_file,
            status=matrix_import.status,
            imported_count=matrix_import.imported_count,
            error_count=matrix_import.error_count,
            warnings=matrix_import.warnings_json or [],
            errors=matrix_import.errors_json or [],
        )

    @staticmethod
    def _warnings(row: dict[str, Any]) -> list[str]:
        warnings = []
        if not any(str(row.get(key) or "").strip() for key in ["photo_1", "photo_2", "photo_3"]):
            warnings.append("missing_photo")
        if not str(row.get("price") or "").strip():
            warnings.append("missing_price")
        if not str(row.get("stock_qty") or "").strip():
            warnings.append("missing_stock")
        return warnings

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _text(value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    @staticmethod
    def _float(value: Any) -> float | None:
        text = str(value).replace(",", ".").strip() if value is not None else ""
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _int(value: Any) -> int | None:
        number = ProductMatrixImporter._float(value)
        return int(number) if number is not None else None
