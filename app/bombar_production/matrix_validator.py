from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from app.bombar_launch.matrix_importer import REQUIRED_HEADERS, SUPPORTED_HEADERS, BombarMatrixImporter
from app.bombar_production.errors import BombarProductionDataError
from app.bombar_production.types import BombarMatrixRowValidation, BombarMatrixValidationResult


FACTORY_CSV_HEADERS = [
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
]


class BombarMatrixValidator:
    def validate_path(self, path: str | Path) -> BombarMatrixValidationResult:
        file_path = Path(path)
        if not file_path.exists():
            raise BombarProductionDataError(f"Bombar matrix not found: {file_path}")
        suffix = file_path.suffix.lower()
        if suffix == ".xlsx":
            headers, rows = self._read_xlsx(file_path)
        else:
            headers, rows = self._read_csv(file_path)
        return self.validate_rows(rows, source_file=file_path.as_posix(), file_type=suffix.lstrip(".") or "csv", headers=headers)

    def validate_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        source_file: str,
        file_type: str = "csv",
        headers: list[str] | None = None,
    ) -> BombarMatrixValidationResult:
        observed_headers = [self._normalize(header) for header in (headers or []) if self._normalize(header)]
        if not observed_headers and rows:
            observed_headers = sorted({self._normalize(key) for row in rows for key in row})
        unsupported_headers = sorted({header for header in observed_headers if header not in SUPPORTED_HEADERS})
        file_errors = [
            f"missing_header:{header}"
            for header in REQUIRED_HEADERS
            if header not in observed_headers
        ]
        file_warnings = [f"unsupported_header:{header}" for header in unsupported_headers]
        seen_skus: set[str] = set()
        row_results: list[BombarMatrixRowValidation] = []
        for index, raw in enumerate(rows, start=2):
            row = {self._normalize(key): value for key, value in raw.items()}
            sku = self._text(row.get("sku"))
            product_name = self._text(row.get("product_name"))
            errors = [
                f"missing_required:{header}"
                for header in REQUIRED_HEADERS
                if not self._text(row.get(header))
            ]
            warnings = []
            if sku and sku in seen_skus:
                errors.append(f"duplicate_sku:{sku}")
            if sku:
                seen_skus.add(sku)
            photo_refs = [self._text(row.get(key)) for key in ["photo_1", "photo_2", "photo_3"]]
            has_photo = any(photo_refs)
            has_price = self._float(row.get("price")) is not None
            has_stock = self._int(row.get("stock_qty")) is not None
            if not has_photo:
                warnings.append("missing_photo")
            if not has_price:
                warnings.append("missing_price")
            if not has_stock:
                warnings.append("missing_stock")
            if not self._text(row.get("product_url")):
                warnings.append("missing_product_url")
            if not self._float(row.get("margin")):
                warnings.append("missing_margin")
            row_results.append(
                BombarMatrixRowValidation(
                    row_number=index,
                    sku=sku,
                    product_name=product_name,
                    has_photo=has_photo,
                    has_price=has_price,
                    has_stock=has_stock,
                    errors=errors,
                    warnings=warnings,
                    normalized=row,
                    status="blocked" if errors else "valid",
                )
            )
        errors = [*file_errors]
        warnings = [*file_warnings]
        for row in row_results:
            errors.extend(f"row_{row.row_number}:{error}" for error in row.errors)
            warnings.extend(f"row_{row.row_number}:{warning}" for warning in row.warnings)
        return BombarMatrixValidationResult(
            source_file=source_file,
            file_type=file_type,
            required_headers=list(REQUIRED_HEADERS),
            supported_headers=sorted(SUPPORTED_HEADERS),
            observed_headers=observed_headers,
            unsupported_headers=unsupported_headers,
            row_count=len(row_results),
            valid_row_count=sum(1 for row in row_results if not row.errors),
            blocked_row_count=sum(1 for row in row_results if row.errors),
            missing_required_count=sum(1 for row in row_results if any(error.startswith("missing_required") for error in row.errors)),
            duplicate_sku_count=sum(1 for row in row_results if any(error.startswith("duplicate_sku") for error in row.errors)),
            missing_photo_count=sum(1 for row in row_results if not row.has_photo),
            missing_price_count=sum(1 for row in row_results if not row.has_price),
            missing_stock_count=sum(1 for row in row_results if not row.has_stock),
            errors=list(dict.fromkeys(errors)),
            warnings=list(dict.fromkeys(warnings)),
            rows=row_results,
        )

    def write_factory_csv(self, validation: BombarMatrixValidationResult, path: str | Path) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FACTORY_CSV_HEADERS)
            writer.writeheader()
            for row in validation.rows:
                if row.errors:
                    continue
                normalized = row.normalized
                writer.writerow({header: self._csv_value(normalized.get(header)) for header in FACTORY_CSV_HEADERS})
        return output_path

    def _read_csv(self, path: Path) -> tuple[list[str], list[dict[str, Any]]]:
        text = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return list(reader.fieldnames or []), rows

    def _read_xlsx(self, path: Path) -> tuple[list[str], list[dict[str, Any]]]:
        rows = BombarMatrixImporter._xlsx_rows(path.read_bytes())
        if not rows:
            return [], []
        headers = [self._normalize(value) for value in rows[0]]
        dict_rows = [
            {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            for row in rows[1:]
            if any(str(value).strip() for value in row)
        ]
        return headers, dict_rows

    @staticmethod
    def _normalize(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _text(value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        return text or None

    @staticmethod
    def _csv_value(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _float(value: Any) -> float | None:
        text = str(value).replace(",", ".").strip() if value is not None else ""
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @classmethod
    def _int(cls, value: Any) -> int | None:
        number = cls._float(value)
        return int(number) if number is not None else None
