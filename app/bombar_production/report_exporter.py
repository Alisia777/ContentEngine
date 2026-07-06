from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.bombar_production.types import BombarProductionDryRunResult


class BombarProductionReportExporter:
    def export(self, report: BombarProductionDryRunResult, reports_dir: str | Path = "reports") -> dict[str, str]:
        output_dir = Path(reports_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        campaign_id = report.campaign_id
        paths = {
            "json": output_dir / f"bombar_readiness_{campaign_id}.json",
            "readiness_csv": output_dir / f"bombar_readiness_{campaign_id}.csv",
            "blockers_csv": output_dir / f"bombar_blockers_{campaign_id}.csv",
            "next_actions_csv": output_dir / f"bombar_next_actions_{campaign_id}.csv",
            "xlsx": output_dir / f"bombar_readiness_{campaign_id}.xlsx",
        }
        report.report_paths = {key: path.as_posix() for key, path in paths.items()}
        paths["json"].write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_readiness_csv(report, paths["readiness_csv"])
        self._write_blockers_csv(report, paths["blockers_csv"])
        self._write_next_actions_csv(report, paths["next_actions_csv"])
        self._write_xlsx(report, paths["xlsx"])
        return report.report_paths

    def _write_readiness_csv(self, report: BombarProductionDryRunResult, path: Path) -> None:
        fieldnames = [
            "sku",
            "status",
            "product_name",
            "product_id",
            "has_photo",
            "has_reference",
            "has_price",
            "has_stock",
            "content_run_count",
            "prompt_pack_count",
            "approved_package_count",
            "blockers",
            "next_actions",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in report.sku_readiness:
                writer.writerow(
                    {
                        "sku": row.sku,
                        "status": row.status,
                        "product_name": row.product_name or "",
                        "product_id": row.product_id or "",
                        "has_photo": row.has_photo,
                        "has_reference": row.has_reference,
                        "has_price": row.has_price,
                        "has_stock": row.has_stock,
                        "content_run_count": row.content_run_count,
                        "prompt_pack_count": row.prompt_pack_count,
                        "approved_package_count": row.approved_package_count,
                        "blockers": self._compact(row.blockers),
                        "next_actions": self._compact(row.next_actions),
                    }
                )

    def _write_blockers_csv(self, report: BombarProductionDryRunResult, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["sku", "source", "blocker"])
            writer.writeheader()
            for sku, blockers in sorted(report.blockers_by_sku.items()):
                for blocker in blockers:
                    writer.writerow({"sku": sku, "source": blocker.get("source", ""), "blocker": blocker.get("blocker", "")})
            for blocker in report.distribution_blockers:
                writer.writerow({"sku": blocker.get("sku", "campaign"), "source": blocker.get("source", "distribution"), "blocker": blocker.get("blocker", "")})

    def _write_next_actions_csv(self, report: BombarProductionDryRunResult, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["scope", "sku", "action", "reason", "count"])
            writer.writeheader()
            for action in report.next_actions:
                writer.writerow(
                    {
                        "scope": action.get("scope", "campaign"),
                        "sku": action.get("sku", ""),
                        "action": action.get("action", ""),
                        "reason": action.get("reason", ""),
                        "count": action.get("count", ""),
                    }
                )
            for row in report.sku_readiness:
                for action in row.next_actions:
                    writer.writerow(
                        {
                            "scope": "sku",
                            "sku": row.sku,
                            "action": action.get("action", ""),
                            "reason": action.get("reason", ""),
                            "count": action.get("count", ""),
                        }
                    )

    def _write_xlsx(self, report: BombarProductionDryRunResult, path: Path) -> None:
        sheets = {
            "Summary": self._summary_rows(report),
            "Readiness": self._readiness_rows(report),
            "Blockers": self._blocker_rows(report),
            "Next Actions": self._next_action_rows(report),
        }
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types_xml(len(sheets)))
            archive.writestr("_rels/.rels", self._root_rels_xml())
            archive.writestr("xl/workbook.xml", self._workbook_xml(list(sheets)))
            archive.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels_xml(len(sheets)))
            for index, rows in enumerate(sheets.values(), start=1):
                archive.writestr(f"xl/worksheets/sheet{index}.xml", self._worksheet_xml(rows))

    def _summary_rows(self, report: BombarProductionDryRunResult) -> list[list[Any]]:
        return [
            ["metric", "value"],
            ["campaign_id", report.campaign_id],
            ["imported_sku_count", report.imported_sku_count],
            ["ready_sku_count", report.ready_sku_count],
            ["blocked_sku_count", report.blocked_sku_count],
            ["prompt_pack_count", report.prompt_pack_count],
            ["missing_references_count", report.missing_references_count],
            ["missing_price_count", report.missing_price_count],
            ["missing_stock_count", report.missing_stock_count],
            ["approved_package_count", report.approved_package_count],
            ["paid_calls_made", report.paid_calls_made],
        ]

    def _readiness_rows(self, report: BombarProductionDryRunResult) -> list[list[Any]]:
        rows = [[
            "sku",
            "status",
            "product_name",
            "has_reference",
            "has_price",
            "has_stock",
            "prompt_pack_count",
            "approved_package_count",
        ]]
        rows.extend(
            [
                row.sku,
                row.status,
                row.product_name or "",
                row.has_reference,
                row.has_price,
                row.has_stock,
                row.prompt_pack_count,
                row.approved_package_count,
            ]
            for row in report.sku_readiness
        )
        return rows

    def _blocker_rows(self, report: BombarProductionDryRunResult) -> list[list[Any]]:
        rows = [["sku", "source", "blocker"]]
        for sku, blockers in sorted(report.blockers_by_sku.items()):
            rows.extend([sku, blocker.get("source", ""), blocker.get("blocker", "")] for blocker in blockers)
        rows.extend(["campaign", blocker.get("source", "distribution"), blocker.get("blocker", "")] for blocker in report.distribution_blockers)
        return rows

    def _next_action_rows(self, report: BombarProductionDryRunResult) -> list[list[Any]]:
        rows = [["scope", "sku", "action", "reason", "count"]]
        rows.extend(
            [
                action.get("scope", "campaign"),
                action.get("sku", ""),
                action.get("action", ""),
                action.get("reason", ""),
                action.get("count", ""),
            ]
            for action in report.next_actions
        )
        for row in report.sku_readiness:
            rows.extend(["sku", row.sku, action.get("action", ""), action.get("reason", ""), ""] for action in row.next_actions)
        return rows

    @staticmethod
    def _compact(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _worksheet_xml(rows: list[list[Any]]) -> str:
        body = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for column_index, value in enumerate(row):
                ref = f"{BombarProductionReportExporter._column_name(column_index)}{row_index}"
                if isinstance(value, bool):
                    cells.append(f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>')
                elif isinstance(value, int | float):
                    cells.append(f'<c r="{ref}"><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
            body.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(body)}</sheetData></worksheet>'
        )

    @staticmethod
    def _column_name(index: int) -> str:
        name = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    @staticmethod
    def _content_types_xml(sheet_count: int) -> str:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index in range(1, sheet_count + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            f"{overrides}</Types>"
        )

    @staticmethod
    def _root_rels_xml() -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        )

    @staticmethod
    def _workbook_xml(sheet_names: list[str]) -> str:
        sheets = "".join(
            f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
            for index, name in enumerate(sheet_names, start=1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{sheets}</sheets></workbook>"
        )

    @staticmethod
    def _workbook_rels_xml(sheet_count: int) -> str:
        rels = "".join(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, sheet_count + 1)
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{rels}</Relationships>"
        )
