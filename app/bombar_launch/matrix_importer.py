from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.bombar_launch.types import BombarImportResult


REQUIRED_HEADERS = ["sku", "product_name"]
SUPPORTED_HEADERS = {
    "sku",
    "product_name",
    "category",
    "price",
    "margin",
    "stock_qty",
    "product_url",
    "photo_1",
    "photo_2",
    "photo_3",
}


class BombarMatrixImporter:
    def __init__(self, db: Session):
        self.db = db

    def import_path(self, path: str | Path) -> BombarImportResult:
        file_path = Path(path)
        data = file_path.read_bytes()
        if file_path.suffix.lower() == ".xlsx":
            return self.import_xlsx_bytes(data, source_file=file_path.as_posix())
        return self.import_csv_text(data.decode("utf-8-sig"), source_file=file_path.as_posix())

    def import_csv_text(self, text: str, *, source_file: str = "bombar_matrix.csv") -> BombarImportResult:
        rows = list(csv.DictReader(io.StringIO(text)))
        return self._import_rows(rows, source_file=source_file)

    def import_xlsx_bytes(self, data: bytes, *, source_file: str = "bombar_matrix.xlsx") -> BombarImportResult:
        rows = self._xlsx_rows(data)
        if not rows:
            return self._import_rows([], source_file=source_file)
        headers = [self._normalize_header(value) for value in rows[0]]
        dict_rows = [
            {headers[index]: value for index, value in enumerate(row) if index < len(headers)}
            for row in rows[1:]
            if any(str(value).strip() for value in row)
        ]
        return self._import_rows(dict_rows, source_file=source_file)

    def _import_rows(self, rows: list[dict[str, Any]], *, source_file: str) -> BombarImportResult:
        errors: list[str] = []
        warnings: list[str] = []
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
        seen_skus: set[str] = set()

        for index, raw in enumerate(rows, start=2):
            normalized = {self._normalize_header(key): value for key, value in raw.items()}
            row_warnings = self._warnings(normalized)
            warnings.extend(f"row_{index}:{warning}" for warning in row_warnings)
            missing_required = [header for header in REQUIRED_HEADERS if not normalized.get(header)]
            if missing_required:
                errors.append(f"row_{index}:missing_required:{','.join(missing_required)}")
                continue
            sku = str(normalized["sku"]).strip()
            if sku in seen_skus:
                warnings.append(f"row_{index}:duplicate_sku_skipped:{sku}")
                continue
            seen_skus.add(sku)
            photo_urls = [
                str(normalized.get(key)).strip()
                for key in ["photo_1", "photo_2", "photo_3"]
                if normalized.get(key) and str(normalized.get(key)).strip()
            ]
            existing = self.db.scalar(
                select(models.ProductMatrixRow)
                .where(models.ProductMatrixRow.import_id == matrix_import.id, models.ProductMatrixRow.sku == sku)
                .order_by(models.ProductMatrixRow.id.desc())
            )
            payload = {
                "import_id": matrix_import.id,
                "sku": sku,
                "product_name": str(normalized["product_name"]).strip(),
                "category": self._text(normalized.get("category")),
                "price": self._float(normalized.get("price")),
                "stock_qty": self._int(normalized.get("stock_qty")),
                "product_url": self._text(normalized.get("product_url")),
                "photo_urls_json": photo_urls,
                "priority": 1,
                "raw_json": {
                    "source_adapter": "bombar_launch",
                    "row_number": index,
                    "source": {key: normalized.get(key) for key in sorted(SUPPORTED_HEADERS) if key in normalized},
                    "bombar": {"margin": self._float(normalized.get("margin"))},
                    "warnings": row_warnings,
                },
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
        matrix_import.errors_json = errors
        matrix_import.warnings_json = list(dict.fromkeys(warnings))
        matrix_import.status = "imported_with_errors" if errors else ("imported_with_warnings" if warnings else "imported")
        self.db.commit()
        self.db.refresh(matrix_import)
        return BombarImportResult(
            import_id=matrix_import.id,
            source_file=source_file,
            status=matrix_import.status,
            imported_count=imported_count,
            errors=errors,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _warnings(row: dict[str, Any]) -> list[str]:
        warnings = []
        if not any(row.get(key) for key in ["photo_1", "photo_2", "photo_3"]):
            warnings.append("missing_photo")
        if not row.get("price"):
            warnings.append("missing_price")
        if not row.get("margin"):
            warnings.append("missing_margin")
        if not row.get("stock_qty"):
            warnings.append("missing_stock")
        if not row.get("product_url"):
            warnings.append("missing_product_url")
        return warnings

    @staticmethod
    def _normalize_header(value: Any) -> str:
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
        number = BombarMatrixImporter._float(value)
        return int(number) if number is not None else None

    @staticmethod
    def _xlsx_rows(data: bytes) -> list[list[str]]:
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in root.findall("main:si", ns):
                    parts = [node.text or "" for node in item.findall(".//main:t", ns)]
                    shared.append("".join(parts))
            sheet_name = "xl/worksheets/sheet1.xml"
            root = ElementTree.fromstring(archive.read(sheet_name))
            rows: list[list[str]] = []
            for row in root.findall(".//main:row", ns):
                values: dict[int, str] = {}
                for cell in row.findall("main:c", ns):
                    ref = cell.attrib.get("r", "A1")
                    column_index = BombarMatrixImporter._column_index(ref)
                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("main:v", ns)
                    inline_node = cell.find("main:is/main:t", ns)
                    value = ""
                    if cell_type == "s" and value_node is not None:
                        value = shared[int(value_node.text or 0)]
                    elif inline_node is not None:
                        value = inline_node.text or ""
                    elif value_node is not None:
                        value = value_node.text or ""
                    values[column_index] = value
                if values:
                    max_column = max(values)
                    rows.append([values.get(index, "") for index in range(max_column + 1)])
            return rows

    @staticmethod
    def _column_index(ref: str) -> int:
        letters = "".join(char for char in ref if char.isalpha()).upper()
        index = 0
        for char in letters:
            index = index * 26 + (ord(char) - ord("A") + 1)
        return max(index - 1, 0)
