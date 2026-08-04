import { type SupabaseContext, withSupabase } from "npm:@supabase/server@1.3.0";
// @deno-types="https://cdn.sheetjs.com/xlsx-0.20.3/package/types/index.d.ts"
import * as XLSX from "https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const STORAGE_BUCKET = "contentengine-knowledge";
const SCHEMA_VERSION = "ai_historical_cases.v1";
const MAX_REQUEST_BYTES = 4_096;
const MAX_SOURCE_BYTES = 26_214_400;
const MAX_RESPONSE_QUARANTINE = 100;
const MAX_SHEETS = 64;
const MAX_ROWS = 5_000;
const MAX_COLUMNS = 100;
const MAX_TOTAL_CELLS = 250_000;
const MAX_CELL_TEXT = 32_767;
const MAX_CSV_CELL_TEXT = 500;
const MAX_FORMULA_TEXT = 2_048;
const MAX_ZIP_ENTRIES = 2_048;
const MAX_ZIP_ENTRY_BYTES = 52_428_800;
const MAX_ZIP_UNCOMPRESSED_BYTES = 209_715_200;
const MAX_ZIP_CENTRAL_BYTES = 4_194_304;
const MAX_BATCH_SIZE = 100;
const MAX_PERIOD_DAYS = 3_660;
const MILLISECONDS_PER_DAY = 86_400_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}$/u;
const SAFE_SKU_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/+()-]{0,119}$/u;
const CHANNEL_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,59}$/u;
const METRIC_KEY_PATTERN = /^[a-z][a-z0-9_]{0,39}$/u;
const FORMULA_INJECTION_PATTERN = /^\s*[=+@-]/u;
const URL_LIKE_PATTERN = /(?:https?:\/\/|www\.)/iu;
const DANGEROUS_FORMULA_PATTERN =
  /(?:\[[^\]]*\]|WEBSERVICE\s*\(|HYPERLINK\s*\(|RTD\s*\(|DDE\s*\(|INDIRECT\s*\(|OFFSET\s*\(|NOW\s*\(|TODAY\s*\(|RAND\s*\(|RANDBETWEEN\s*\()/iu;

const PRODUCT_CATEGORIES = new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
const OUTCOMES = new Set(["good", "bad", "review"]);
const OUTCOME_DIMENSIONS = new Set([
  "overall",
  "sales",
  "orders",
  "conversion",
  "buyout",
  "engagement",
  "cart_to_order",
  "visit_to_cart",
  "visit_to_order",
  "sale_per_view",
  "revenue",
  "profitability",
  "ad_efficiency",
  "funnel",
  "attribution",
  "creative_angle",
  "data_quality",
  "other",
  "overall_performance",
  "organic_growth",
  "advertising_efficiency",
  "product_card_conversion",
  "inventory",
  "evidence_sufficiency",
  "purchase_transition",
  "content_conversion",
  "product_mapping",
  "attribution_window",
]);
const CREATIVE_ANGLES = new Set([
  "product_focus",
  "trust_builder",
  "demonstration",
  "comparison",
  "objection_handling",
  "curiosity_gap",
]);
const PLATFORMS = new Set([
  "wildberries",
  "ozon",
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "other",
]);

type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

type ContentEngineDatabase = {
  public: {
    Tables: Record<string, never>;
    Views: Record<string, never>;
    Functions: {
      creator_authorize_ai_historical_case_import: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_import_ai_historical_case_batch: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

export type ProductCategory =
  | "cosmetics"
  | "baa"
  | "sports_food"
  | "food"
  | "household"
  | "apparel"
  | "electronics"
  | "other";

type HistoricalCase = {
  external_case_id: string;
  product_category: ProductCategory;
  product_sku?: string;
  marketplace_sku?: string;
  product_title: string;
  brand: string;
  platform: string;
  channel: string;
  period_start: string;
  period_end: string;
  outcome: "good" | "bad" | "review";
  outcome_dimension: string;
  status_label: string;
  metrics: Record<string, number>;
  confidence: number;
  creative_angle?: string;
  provenance: { sheet: string; row: number; row_hash: string };
};

type QuarantineItem = {
  sheet: string;
  row: number;
  code: string;
};

type ParseResult = {
  adapter: "harley_effect_content_v1" | "qeep_funnel_v1" | "canonical_v1";
  parserVersion: string;
  cases: HistoricalCase[];
  quarantine: QuarantineItem[];
  warnings: Record<string, number>;
};

type SourceReceipt = {
  sourceId: string;
  productCategory: ProductCategory;
  bucket: string;
  objectKey: string;
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  clientSha256: string;
};

type ImportRequest = {
  organizationId: string;
  sourceId: string;
  productCategory: ProductCategory;
  adapter: "auto" | ParseResult["adapter"];
  commit: boolean;
  idempotencyKey: string;
};

type Cell = { v?: unknown; f?: string; t?: string };
type Row = Array<Cell | undefined>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): boolean {
  const allowedSet = new Set(allowed);
  return Object.keys(value).every((key) => allowedSet.has(key));
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code < 32 || code === 127) return true;
  }
  return false;
}

function boundedText(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return typeof value === "string" && value === value.trim() &&
    value.length >= minimum && value.length <= maximum &&
    !hasControlCharacter(value) && !URL_LIKE_PATTERN.test(value) &&
    !FORMULA_INJECTION_PATTERN.test(value);
}

function responseHeaders(request: Request): Headers {
  const headers = new Headers({
    "access-control-allow-headers":
      "authorization, apikey, content-type, x-client-info",
    "access-control-allow-methods": "POST, OPTIONS",
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    vary: "Origin",
    "x-content-type-options": "nosniff",
  });
  if (request.headers.get("origin") === PUBLIC_APP_ORIGIN) {
    headers.set("access-control-allow-origin", PUBLIC_APP_ORIGIN);
  }
  return headers;
}

function json(request: Request, body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(request),
  });
}

async function readBoundedRequest(request: Request): Promise<unknown> {
  if (request.body === null) throw new Error("invalid_json");
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_REQUEST_BYTES) {
        await reader.cancel();
        throw new Error("request_too_large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("invalid_json");
  }
}

function readImportRequest(value: unknown): ImportRequest | null {
  if (
    !isRecord(value) ||
    !hasOnlyKeys(value, [
      "action",
      "organization_id",
      "source_id",
      "product_category",
      "adapter",
      "commit",
      "idempotency_key",
    ]) || value.action !== "parse_and_import" ||
    typeof value.organization_id !== "string" ||
    !UUID_PATTERN.test(value.organization_id) ||
    typeof value.source_id !== "string" ||
    !UUID_PATTERN.test(value.source_id) ||
    typeof value.product_category !== "string" ||
    !PRODUCT_CATEGORIES.has(value.product_category) ||
    ![
      "auto",
      "harley_effect_content_v1",
      "qeep_funnel_v1",
      "canonical_v1",
    ].includes(String(value.adapter ?? "auto")) ||
    typeof value.commit !== "boolean" ||
    typeof value.idempotency_key !== "string" ||
    !UUID_PATTERN.test(value.idempotency_key)
  ) return null;
  return {
    organizationId: value.organization_id,
    sourceId: value.source_id,
    productCategory: value.product_category as ProductCategory,
    adapter: String(value.adapter ?? "auto") as ImportRequest["adapter"],
    commit: value.commit,
    idempotencyKey: value.idempotency_key,
  };
}

function stableJson(value: unknown): string {
  const walk = (node: unknown): unknown => {
    if (Array.isArray(node)) return node.map(walk);
    if (!isRecord(node)) return node;
    return Object.fromEntries(
      Object.keys(node).sort().map((key) => [key, walk(node[key])]),
    );
  };
  return JSON.stringify(walk(value));
}

export async function sha256Hex(value: Uint8Array | string): Promise<string> {
  const bytes = typeof value === "string"
    ? new TextEncoder().encode(value)
    : value;
  const stableBytes = Uint8Array.from(bytes);
  const digest = await crypto.subtle.digest(
    "SHA-256",
    stableBytes.buffer as ArrayBuffer,
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function jsonHash(value: unknown): Promise<string> {
  return await sha256Hex(stableJson(value));
}

function u16(view: DataView, offset: number): number {
  return view.getUint16(offset, true);
}

function u32(view: DataView, offset: number): number {
  return view.getUint32(offset, true);
}

export type ZipPreflight = {
  entryCount: number;
  totalUncompressedBytes: number;
};

export function preflightXlsx(bytes: Uint8Array): ZipPreflight {
  if (bytes.byteLength < 22 || bytes.byteLength > MAX_SOURCE_BYTES) {
    throw new Error("source_size_invalid");
  }
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  const earliest = Math.max(0, bytes.byteLength - 65_557);
  for (let offset = bytes.byteLength - 22; offset >= earliest; offset -= 1) {
    if (u32(view, offset) === 0x06054b50) {
      eocd = offset;
      break;
    }
  }
  if (eocd < 0) throw new Error("xlsx_zip_invalid");
  const disk = u16(view, eocd + 4);
  const centralDisk = u16(view, eocd + 6);
  const entriesOnDisk = u16(view, eocd + 8);
  const entryCount = u16(view, eocd + 10);
  const centralSize = u32(view, eocd + 12);
  const centralOffset = u32(view, eocd + 16);
  const commentLength = u16(view, eocd + 20);
  if (
    disk !== 0 || centralDisk !== 0 || entriesOnDisk !== entryCount ||
    entryCount < 1 || entryCount > MAX_ZIP_ENTRIES || entryCount === 0xffff ||
    centralSize > MAX_ZIP_CENTRAL_BYTES || centralOffset === 0xffffffff ||
    centralOffset + centralSize > eocd ||
    eocd + 22 + commentLength !== bytes.byteLength
  ) throw new Error("xlsx_zip_invalid");

  const decoder = new TextDecoder("utf-8", { fatal: true });
  const names = new Set<string>();
  let cursor = centralOffset;
  let totalUncompressedBytes = 0;
  for (let index = 0; index < entryCount; index += 1) {
    if (cursor + 46 > eocd || u32(view, cursor) !== 0x02014b50) {
      throw new Error("xlsx_zip_invalid");
    }
    const flags = u16(view, cursor + 8);
    const compression = u16(view, cursor + 10);
    const compressed = u32(view, cursor + 20);
    const uncompressed = u32(view, cursor + 24);
    const nameLength = u16(view, cursor + 28);
    const extraLength = u16(view, cursor + 30);
    const entryCommentLength = u16(view, cursor + 32);
    const localOffset = u32(view, cursor + 42);
    const next = cursor + 46 + nameLength + extraLength + entryCommentLength;
    if (
      next > eocd || nameLength < 1 || (flags & 0x0001) !== 0 ||
      (flags & 0x0040) !== 0 || ![0, 8].includes(compression) ||
      compressed === 0xffffffff || uncompressed === 0xffffffff ||
      localOffset === 0xffffffff || uncompressed > MAX_ZIP_ENTRY_BYTES
    ) throw new Error("xlsx_zip_unsafe");
    let name: string;
    try {
      name = decoder.decode(
        bytes.subarray(cursor + 46, cursor + 46 + nameLength),
      );
    } catch {
      throw new Error("xlsx_zip_invalid");
    }
    const normalized = name.replaceAll("\\", "/");
    const lower = normalized.toLocaleLowerCase("en-US");
    if (
      name !== normalized || normalized.startsWith("/") ||
      normalized.split("/").some((part) => part === ".." || part === ".") ||
      hasControlCharacter(normalized) || names.has(lower) ||
      lower.includes("vbaproject") || lower.startsWith("xl/macrosheets/") ||
      lower.startsWith("xl/externallinks/") || lower === "xl/connections.xml" ||
      lower === "encryptioninfo" || lower === "encryptedpackage" ||
      lower.endsWith(".bin")
    ) throw new Error("xlsx_zip_unsafe");
    names.add(lower);
    totalUncompressedBytes += uncompressed;
    if (
      totalUncompressedBytes > MAX_ZIP_UNCOMPRESSED_BYTES ||
      (compressed === 0 && uncompressed > 0) ||
      (compressed > 0 && uncompressed / compressed > 1_000)
    ) throw new Error("xlsx_zip_unsafe");
    cursor = next;
  }
  if (
    cursor !== centralOffset + centralSize ||
    !names.has("[content_types].xml") || !names.has("xl/workbook.xml")
  ) throw new Error("xlsx_zip_invalid");
  return { entryCount, totalUncompressedBytes };
}

type Workbook = ReturnType<typeof XLSX.read>;
type Worksheet = Workbook["Sheets"][string];

function workbookFromXlsx(bytes: Uint8Array): Workbook {
  preflightXlsx(bytes);
  let workbook: Workbook;
  try {
    workbook = XLSX.read(bytes, {
      type: "array",
      cellDates: false,
      cellFormula: true,
      cellHTML: false,
      cellNF: false,
      cellStyles: false,
      cellText: false,
      bookVBA: false,
      WTF: true,
    });
  } catch {
    throw new Error("xlsx_parse_failed");
  }
  if (
    !Array.isArray(workbook.SheetNames) || workbook.SheetNames.length < 1 ||
    workbook.SheetNames.length > MAX_SHEETS ||
    new Set(workbook.SheetNames).size !== workbook.SheetNames.length
  ) throw new Error("xlsx_structure_invalid");

  let totalCells = 0;
  for (const sheetName of workbook.SheetNames) {
    if (
      !boundedText(sheetName, 1, 100) ||
      !isRecord(workbook.Sheets[sheetName])
    ) throw new Error("xlsx_structure_invalid");
    const sheet = workbook.Sheets[sheetName];
    const reference = sheet["!ref"];
    if (reference === undefined) continue;
    if (typeof reference !== "string" || reference.length > 40) {
      throw new Error("xlsx_structure_invalid");
    }
    let range: ReturnType<typeof XLSX.utils.decode_range>;
    try {
      range = XLSX.utils.decode_range(reference);
    } catch {
      throw new Error("xlsx_structure_invalid");
    }
    const rowCount = range.e.r - range.s.r + 1;
    const columnCount = range.e.c - range.s.c + 1;
    if (
      rowCount < 1 || rowCount > MAX_ROWS || columnCount < 1 ||
      columnCount > MAX_COLUMNS
    ) throw new Error("xlsx_dimensions_exceeded");
    totalCells += rowCount * columnCount;
    if (totalCells > MAX_TOTAL_CELLS) {
      throw new Error("xlsx_dimensions_exceeded");
    }
    for (let row = range.s.r; row <= range.e.r; row += 1) {
      for (let column = range.s.c; column <= range.e.c; column += 1) {
        const address = XLSX.utils.encode_cell({ r: row, c: column });
        const cell = sheet[address] as Cell | undefined;
        if (!cell) continue;
        if (
          cell.v !== undefined && cell.v !== null &&
          !["string", "number", "boolean"].includes(typeof cell.v) &&
          !(cell.v instanceof Date)
        ) throw new Error("xlsx_cell_type_invalid");
        if (typeof cell.v === "string" && cell.v.length > MAX_CELL_TEXT) {
          throw new Error("xlsx_cell_too_long");
        }
        if (cell.f !== undefined) {
          if (
            typeof cell.f !== "string" || cell.f.length < 1 ||
            cell.f.length > MAX_FORMULA_TEXT ||
            DANGEROUS_FORMULA_PATTERN.test(cell.f)
          ) throw new Error("xlsx_formula_unsafe");
          if (cell.v === undefined || cell.v === null) {
            throw new Error("xlsx_formula_cache_missing");
          }
        }
      }
    }
  }
  return workbook;
}

function readSheetRows(
  workbook: Workbook,
  sheetName: string,
  maximumRows = MAX_ROWS,
  maximumColumns = MAX_COLUMNS,
): Row[] {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) throw new Error("required_sheet_missing");
  const reference = sheet["!ref"];
  if (typeof reference !== "string") throw new Error("required_sheet_empty");
  const range = XLSX.utils.decode_range(reference);
  const rowCount = range.e.r - range.s.r + 1;
  const columnCount = range.e.c - range.s.c + 1;
  if (rowCount > maximumRows || columnCount > maximumColumns) {
    throw new Error("sheet_dimensions_exceeded");
  }
  const rows: Row[] = [];
  for (let row = range.s.r; row <= range.e.r; row += 1) {
    const values: Row = [];
    for (let column = range.s.c; column <= range.e.c; column += 1) {
      values.push(
        sheet[XLSX.utils.encode_cell({ r: row, c: column })] as
          | Cell
          | undefined,
      );
    }
    rows.push(values);
  }
  return rows;
}

function cachedCellValue(
  cell: Cell | undefined,
  formulaPolicy: "forbid" | "cached" | "qeep_reference",
  warnings: Record<string, number>,
): unknown {
  if (!cell) return null;
  if (cell.f !== undefined) {
    if (formulaPolicy === "forbid") throw new Error("formula_in_source_field");
    if (
      formulaPolicy === "qeep_reference" &&
      !/^=?'SKU_итог'![A-Z]{1,2}[1-9][0-9]{0,4}$/u.test(cell.f)
    ) throw new Error("formula_reference_unexpected");
    if (cell.v === undefined || cell.v === null) {
      throw new Error("formula_cache_missing");
    }
    warnings.formula_cached_only = (warnings.formula_cached_only ?? 0) + 1;
  }
  return cell.v ?? null;
}

function requiredCellText(
  cell: Cell | undefined,
  formulaPolicy: "forbid" | "cached" | "qeep_reference",
  warnings: Record<string, number>,
  maximum = 180,
): string {
  const value = cachedCellValue(cell, formulaPolicy, warnings);
  const text = typeof value === "number" && Number.isSafeInteger(value)
    ? String(value)
    : value;
  if (!boundedText(text, 1, maximum)) throw new Error("text_cell_invalid");
  return text;
}

function requiredNumber(
  cell: Cell | undefined,
  formulaPolicy: "forbid" | "cached" | "qeep_reference",
  warnings: Record<string, number>,
  minimum = 0,
  maximum = 1_000_000_000_000,
): number {
  const value = cachedCellValue(cell, formulaPolicy, warnings);
  if (
    typeof value !== "number" || !Number.isFinite(value) ||
    value < minimum || value > maximum
  ) throw new Error("numeric_cell_invalid");
  return value;
}

function optionalNumber(
  cell: Cell | undefined,
  formulaPolicy: "forbid" | "cached" | "qeep_reference",
  warnings: Record<string, number>,
  minimum = 0,
  maximum = 1_000_000_000_000,
): number | null {
  const value = cachedCellValue(cell, formulaPolicy, warnings);
  if (value === null || value === "") return null;
  if (
    typeof value !== "number" || !Number.isFinite(value) ||
    value < minimum || value > maximum
  ) throw new Error("numeric_cell_invalid");
  return value;
}

function excelDate(value: unknown): string | null {
  if (value instanceof Date && Number.isFinite(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  if (typeof value === "string") {
    if (
      /^\d{4}-\d{2}-\d{2}$/u.test(value) && !Number.isNaN(Date.parse(value))
    ) {
      return value;
    }
    const match = /^(\d{2})\.(\d{2})\.(\d{4})$/u.exec(value);
    if (match) return `${match[3]}-${match[2]}-${match[1]}`;
    return null;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    const parsed = XLSX.SSF.parse_date_code(value);
    if (!parsed) return null;
    const year = String(parsed.y).padStart(4, "0");
    const month = String(parsed.m).padStart(2, "0");
    const day = String(parsed.d).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }
  return null;
}

function headerMap(row: Row, expected: readonly string[]): Map<string, number> {
  const result = new Map<string, number>();
  row.forEach((cell, index) => {
    if (typeof cell?.v === "string") result.set(cell.v.trim(), index);
  });
  if (expected.some((header) => !result.has(header))) {
    throw new Error("sheet_headers_invalid");
  }
  return result;
}

function approximately(
  left: number,
  right: number,
  tolerance = 0.000001,
): boolean {
  return Math.abs(left - right) <=
    Math.max(tolerance, Math.abs(right) * tolerance);
}

function ratio(numerator: number, denominator: number): number {
  return denominator === 0 ? 0 : numerator / denominator;
}

function isoDateMilliseconds(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value) || value.startsWith("0000-")) {
    return null;
  }
  const parsed = Date.parse(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(parsed)) return null;
  return new Date(parsed).toISOString().slice(0, 10) === value ? parsed : null;
}

function periodIsValid(periodStart: string, periodEnd: string): boolean {
  const start = isoDateMilliseconds(periodStart);
  const end = isoDateMilliseconds(periodEnd);
  return start !== null && end !== null && end >= start &&
    (end - start) / MILLISECONDS_PER_DAY <= MAX_PERIOD_DAYS;
}

function safeExternalPart(value: string): string {
  const result = value
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/[^a-z0-9._-]+/gu, "-")
    .replace(/^-+|-+$/gu, "")
    .slice(0, 70);
  if (!result) throw new Error("external_case_identity_invalid");
  return result;
}

function validateMetrics(metrics: Record<string, number>): void {
  const entries = Object.entries(metrics);
  if (entries.length < 1 || entries.length > 20) {
    throw new Error("case_metrics_invalid");
  }
  for (const [key, value] of entries) {
    if (
      !METRIC_KEY_PATTERN.test(key) || !Number.isFinite(value) ||
      Math.abs(value) > 1_000_000_000_000
    ) throw new Error("case_metrics_invalid");
  }
}

function validateHistoricalCase(value: HistoricalCase): void {
  if (
    !SAFE_ID_PATTERN.test(value.external_case_id) ||
    !PRODUCT_CATEGORIES.has(value.product_category) ||
    (value.product_sku !== undefined &&
      !SAFE_SKU_PATTERN.test(value.product_sku)) ||
    (value.marketplace_sku !== undefined &&
      !SAFE_SKU_PATTERN.test(value.marketplace_sku)) ||
    !boundedText(value.product_title, 2, 180) ||
    !boundedText(value.brand, 1, 100) ||
    !boundedText(value.platform, 1, 40) || !PLATFORMS.has(value.platform) ||
    !CHANNEL_PATTERN.test(value.channel) ||
    !periodIsValid(value.period_start, value.period_end) ||
    !OUTCOMES.has(value.outcome) ||
    !OUTCOME_DIMENSIONS.has(value.outcome_dimension) ||
    !boundedText(value.status_label, 1, 80) ||
    !Number.isFinite(value.confidence) || value.confidence < 0 ||
    value.confidence > 1 ||
    (value.creative_angle !== undefined &&
      !CREATIVE_ANGLES.has(value.creative_angle)) ||
    !boundedText(value.provenance.sheet, 1, 100) ||
    !Number.isSafeInteger(value.provenance.row) || value.provenance.row < 1 ||
    value.provenance.row > 1_000_000 ||
    !SHA256_PATTERN.test(value.provenance.row_hash)
  ) throw new Error("normalized_case_invalid");
  validateMetrics(value.metrics);
}

function addQuarantine(
  quarantine: QuarantineItem[],
  sheet: string,
  row: number,
  error: unknown,
): void {
  const candidate = error instanceof Error ? error.message : "row_invalid";
  const code = /^[a-z0-9_]{3,80}$/u.test(candidate) ? candidate : "row_invalid";
  quarantine.push({ sheet, row, code });
}

function harleyCreativeAngle(value: string): string | undefined {
  const normalized = value.toLocaleLowerCase("ru-RU");
  if (
    normalized.includes("эксперт") || normalized.includes("обучающ") ||
    normalized.includes("личный опыт") || normalized.includes("шпаргал")
  ) return "trust_builder";
  if (
    normalized.includes("инструк") || normalized.includes("до/после") ||
    normalized.includes("рутин") || normalized.includes("результат")
  ) return "demonstration";
  if (
    normalized.includes("короткая рекомендация") ||
    normalized.includes("прямая товарная рекомендация")
  ) return "product_focus";
  if (
    normalized.includes("скрытая проблема") ||
    normalized.includes("проблема → решение")
  ) return "objection_handling";
  if (
    normalized.includes("сторителлинг") ||
    normalized.includes("эмоциональная история") ||
    normalized.includes("развлекательный")
  ) return "curiosity_gap";
  return undefined;
}

export async function parseHarleyWorkbook(
  workbook: Workbook,
  productCategory: ProductCategory = "other",
): Promise<ParseResult> {
  const sheetName = "Эффект_контента";
  const rows = readSheetRows(workbook, sheetName, 500, 50);
  if (rows.length < 7) throw new Error("harley_sheet_invalid");
  const expectedHeaders = [
    "Instagram",
    "Дата поста",
    "WW-код",
    "Базовый SKU",
    "Товар",
    "Контентный угол",
    "Контент ↔ товар",
    "Статус окна",
    "Просмотры",
    "В избранное",
    "В корзину",
    "Заказы КЗ",
    "Продажи КЗ",
    "Корзина / просмотр",
    "Заказ / просмотр",
    "Продажа / просмотр",
    "% выкупа",
    "Продаж / 1000 просмотров",
    "Продаж / день",
    "Оценка контента",
  ] as const;
  const headers = headerMap(rows[5], expectedHeaders);
  const warnings: Record<string, number> = {};
  const quarantine: QuarantineItem[] = [];
  const cases: HistoricalCase[] = [];
  const minimumViews = requiredNumber(
    rows[3][1],
    "forbid",
    warnings,
    1,
    1_000_000,
  );
  const salesQ3 = requiredNumber(rows[3][4], "cached", warnings, 0, 1_000_000);
  const medianSalePerView = requiredNumber(
    rows[3][7],
    "cached",
    warnings,
    0,
    1,
  );
  if (minimumViews !== 30) throw new Error("harley_thresholds_invalid");
  const at = (
    row: Row,
    name: typeof expectedHeaders[number],
  ): Cell | undefined => row[headers.get(name) as number];

  for (let rowIndex = 6; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    if (
      !row.some((cell) =>
        cell?.v !== undefined && cell.v !== null && cell.v !== ""
      )
    ) {
      continue;
    }
    const sourceRow = rowIndex + 1;
    try {
      const handle = requiredCellText(
        at(row, "Instagram"),
        "forbid",
        warnings,
        80,
      );
      const postDateValue = cachedCellValue(
        at(row, "Дата поста"),
        "forbid",
        warnings,
      );
      const postDate = excelDate(postDateValue);
      if (postDate === null) throw new Error("post_date_invalid");
      const marketplaceSku = requiredCellText(
        at(row, "WW-код"),
        "forbid",
        warnings,
        80,
      );
      const productSku = requiredCellText(
        at(row, "Базовый SKU"),
        "forbid",
        warnings,
        160,
      );
      const productTitle = requiredCellText(
        at(row, "Товар"),
        "forbid",
        warnings,
        180,
      );
      const sourceCreativeAngle = requiredCellText(
        at(row, "Контентный угол"),
        "forbid",
        warnings,
        180,
      );
      const mapping = requiredCellText(
        at(row, "Контент ↔ товар"),
        "forbid",
        warnings,
        12,
      );
      const windowStatus = requiredCellText(
        at(row, "Статус окна"),
        "forbid",
        warnings,
        80,
      );
      const views = optionalNumber(at(row, "Просмотры"), "forbid", warnings);
      const favorites = optionalNumber(
        at(row, "В избранное"),
        "forbid",
        warnings,
      );
      const carts = optionalNumber(at(row, "В корзину"), "forbid", warnings);
      const orders = optionalNumber(at(row, "Заказы КЗ"), "forbid", warnings);
      const sales = optionalNumber(at(row, "Продажи КЗ"), "forbid", warnings);
      const cachedStatus = requiredCellText(
        at(row, "Оценка контента"),
        "cached",
        warnings,
        80,
      );

      if (
        [views, favorites, carts, orders, sales].some((value) =>
          value !== null && !Number.isSafeInteger(value)
        ) ||
        (orders !== null && carts !== null && orders > carts) ||
        (sales !== null && orders !== null && sales > orders)
      ) throw new Error("harley_funnel_invariant_failed");

      let outcome: HistoricalCase["outcome"];
      let outcomeDimension: string;
      let expectedStatus: string;
      let confidence: number;
      if (mapping !== "Да") {
        outcome = "review";
        outcomeDimension = "product_mapping";
        expectedStatus = "Проверить сопоставление";
        confidence = 0.2;
      } else if (windowStatus !== "Сопоставимо") {
        outcome = "review";
        outcomeDimension = "attribution_window";
        expectedStatus = "Вне окна июня";
        confidence = 0.35;
      } else if (
        views === null || carts === null || orders === null || sales === null
      ) {
        throw new Error("harley_metrics_missing");
      } else if (views < minimumViews) {
        outcome = "review";
        outcomeDimension = "evidence_sufficiency";
        expectedStatus = "Недостаточно охвата";
        confidence = 0.45;
      } else if (sales >= salesQ3) {
        outcome = "good";
        outcomeDimension = "overall_performance";
        expectedStatus = "Лидер";
        confidence = 0.95;
      } else if (sales === 0 && carts > 0) {
        outcome = "bad";
        outcomeDimension = "purchase_transition";
        expectedStatus = "Интерес без продажи";
        confidence = 0.9;
      } else if (ratio(sales, views) >= medianSalePerView) {
        outcome = "good";
        outcomeDimension = "content_conversion";
        expectedStatus = "Эффективный";
        confidence = 0.85;
      } else {
        outcome = "bad";
        outcomeDimension = "content_conversion";
        expectedStatus = "Ниже медианы";
        confidence = 0.55;
      }
      if (cachedStatus !== expectedStatus) {
        throw new Error("harley_status_mismatch");
      }

      const comparable = views !== null && carts !== null && orders !== null &&
        sales !== null;
      const metrics: Record<string, number> = {
        has_comparable_metrics: comparable ? 1 : 0,
      };
      if (comparable) {
        const comparableViews = views as number;
        const comparableCarts = carts as number;
        const comparableOrders = orders as number;
        const comparableSales = sales as number;
        const derived = {
          cart_per_view: ratio(comparableCarts, comparableViews),
          order_per_view: ratio(comparableOrders, comparableViews),
          sale_per_view: ratio(comparableSales, comparableViews),
          buyout_rate: ratio(comparableSales, comparableOrders),
        };
        const cachedDerived = [
          optionalNumber(
            at(row, "Корзина / просмотр"),
            "cached",
            warnings,
            0,
            1,
          ),
          optionalNumber(at(row, "Заказ / просмотр"), "cached", warnings, 0, 1),
          optionalNumber(
            at(row, "Продажа / просмотр"),
            "cached",
            warnings,
            0,
            1,
          ),
          optionalNumber(at(row, "% выкупа"), "cached", warnings, 0, 1),
        ];
        const expectedDerived = [
          derived.cart_per_view,
          derived.order_per_view,
          derived.sale_per_view,
          comparableOrders === 0 ? null : derived.buyout_rate,
        ];
        for (let index = 0; index < cachedDerived.length; index += 1) {
          if (
            cachedDerived[index] !== null && expectedDerived[index] !== null &&
            !approximately(
              cachedDerived[index] as number,
              expectedDerived[index] as number,
            )
          ) throw new Error("harley_metric_mismatch");
        }
        Object.assign(metrics, {
          views: comparableViews,
          favorites: favorites ?? 0,
          carts: comparableCarts,
          orders: comparableOrders,
          sales: comparableSales,
          refusals: comparableOrders - comparableSales,
          ...derived,
          sales_per_1000_views: derived.sale_per_view * 1_000,
        });
      }

      const rowHash = await jsonHash({
        sheet: sheetName,
        row: sourceRow,
        handle,
        post_date: postDate,
        product_sku: productSku,
        marketplace_sku: marketplaceSku,
        product_title: productTitle,
        mapping,
        window_status: windowStatus,
        status: expectedStatus,
        metrics,
      });
      const creativeAngle = harleyCreativeAngle(sourceCreativeAngle);
      const historicalCase: HistoricalCase = {
        external_case_id: `harley:instagram:${safeExternalPart(handle)}:${
          safeExternalPart(marketplaceSku)
        }:${postDate}`,
        product_category: productCategory,
        product_sku: productSku,
        marketplace_sku: marketplaceSku,
        product_title: productTitle,
        brand: "Harley",
        platform: "wildberries",
        channel: "instagram",
        period_start: "2026-06-01",
        period_end: "2026-06-30",
        outcome,
        outcome_dimension: outcomeDimension,
        status_label: expectedStatus,
        metrics,
        confidence,
        provenance: { sheet: sheetName, row: sourceRow, row_hash: rowHash },
      };
      if (creativeAngle !== undefined) {
        historicalCase.creative_angle = creativeAngle;
      }
      validateHistoricalCase(historicalCase);
      cases.push(historicalCase);
    } catch (error) {
      addQuarantine(quarantine, sheetName, sourceRow, error);
    }
  }
  if (cases.length + quarantine.length < 1) {
    throw new Error("harley_cases_empty");
  }
  return {
    adapter: "harley_effect_content_v1",
    parserVersion: "creator-ai-case-import-harley-effect-content-v1",
    cases,
    quarantine,
    warnings,
  };
}

const QEEP_SPORTS_CATEGORIES = new Set([
  "Аминокислоты",
  "Бустеры тестостерона",
  "Жиросжигатели",
  "Жиросжигатель",
  "Изотоники",
  "Изотоник",
  "Креатины",
  "Креатин моногидрат",
  "L-карнитины",
  "L-карнитин",
  "Моно аминокислота спортивная",
  "Средства для повышения тестостерона",
]);
const QEEP_COSMETICS_CATEGORIES = new Set([
  "Маски косметические",
  "Маска косметическая",
  "Сыворотки",
  "Кремы",
  "Гели",
  "Пудры",
  "Тоники",
  "Средства для удаления кутикулы",
  "Масла",
  "Крем для ухода за кожей",
  "Спрей для укладки волос",
  "Пилинг",
  "Сыворотка для волос",
  "Средство от растяжек",
  "Сыворотка для ухода за кожей",
  "Пенка для волос",
  "Средство солнцезащитное",
  "Средство для умывания",
  "Тоник для ухода за кожей",
  "Средство для удаления кутикулы",
  "Средство для душа",
]);
const QEEP_BAA_CATEGORIES = new Set([
  "БАДы",
  "Комплексные пищевые добавки",
  "Добавки для суставов и связок",
  "Травяные сборы",
  "Спирулина",
  "Витамины",
  "БАД для ускорения обмена веществ",
  "БАД жирные кислоты",
  "БАД пробиотик",
  "БАД для печени",
  "Пищевая добавка",
  "БАД успокоительный",
  "Препарат для суставов и связок",
  "БАД от паразитов",
  "БАД для поддержания здоровья волос, ногтей и кожи",
  "БАД для головного мозга",
  "БАД для вен и сосудов",
  "БАД для снижения веса",
]);

export function qeepProductCategory(value: string): ProductCategory | null {
  if (QEEP_SPORTS_CATEGORIES.has(value)) return "sports_food";
  if (QEEP_COSMETICS_CATEGORIES.has(value)) return "cosmetics";
  if (QEEP_BAA_CATEGORIES.has(value)) return "baa";
  if (value === "Какао") return "food";
  return null;
}

type QeepThreshold = {
  medianCr: number;
  medianDrr: number;
  q75Revenue: number;
  q75Visits: number;
  medianBuyout: number;
  medianRevenue: number;
  minimumData: number;
};

type QeepStatusMetrics = {
  visits: number;
  orders: number;
  sales: number;
  revenue: number;
  visitToOrderRate: number;
  buyoutRate: number;
  adSpend: number;
  drr: number;
  marginRate: number;
  organicShare: number;
  stockDays: number | null;
};

export function qeepExpectedStatus(
  metrics: QeepStatusMetrics,
  threshold: QeepThreshold,
): string {
  if (metrics.orders < threshold.minimumData) return "Мало данных";
  if (
    metrics.stockDays !== null && metrics.sales > 0 && metrics.stockDays < 14
  ) return "Риск OOS";
  if (
    metrics.orders >= 100 &&
    metrics.buyoutRate < threshold.medianBuyout * 0.9
  ) return "Чинить выкуп";
  if (
    metrics.adSpend > 0 &&
    metrics.drr > Math.max(0.2, threshold.medianDrr * 1.5)
  ) return "Оптимизировать рекламу";
  if (
    metrics.revenue >= threshold.q75Revenue &&
    metrics.visitToOrderRate >= threshold.medianCr && metrics.marginRate >= 0.15
  ) return "Суперзвезда";
  if (
    metrics.visits >= threshold.q75Visits &&
    metrics.visitToOrderRate < threshold.medianCr * 0.7
  ) return "Чинить карточку";
  if (
    metrics.revenue >= threshold.medianRevenue && metrics.organicShare >= 0.8
  ) return "Масштабировать";
  return "Наблюдать";
}

function qeepOutcome(status: string): {
  outcome: HistoricalCase["outcome"];
  dimension: string;
  confidence: number;
} | null {
  switch (status) {
    case "Суперзвезда":
      return {
        outcome: "good",
        dimension: "overall_performance",
        confidence: 0.95,
      };
    case "Масштабировать":
      return { outcome: "good", dimension: "organic_growth", confidence: 0.9 };
    case "Чинить выкуп":
      return { outcome: "bad", dimension: "buyout", confidence: 0.95 };
    case "Оптимизировать рекламу":
      return {
        outcome: "bad",
        dimension: "advertising_efficiency",
        confidence: 0.9,
      };
    case "Чинить карточку":
      return {
        outcome: "bad",
        dimension: "product_card_conversion",
        confidence: 0.9,
      };
    case "Риск OOS":
      return { outcome: "review", dimension: "inventory", confidence: 0.8 };
    case "Наблюдать":
      return {
        outcome: "review",
        dimension: "evidence_sufficiency",
        confidence: 0.55,
      };
    case "Мало данных":
      return {
        outcome: "review",
        dimension: "evidence_sufficiency",
        confidence: 0.35,
      };
    default:
      return null;
  }
}

function qeepThresholds(
  workbook: Workbook,
  warnings: Record<string, number>,
): Record<"WB" | "Ozon", QeepThreshold> {
  const rows = readSheetRows(workbook, "Пороги", 100, 20);
  if (rows.length < 8) throw new Error("qeep_thresholds_missing");
  const expected = [
    "Канал",
    "Медиана CR визит→заказ",
    "Медиана ДРР",
    "Q75 выручки, ₽",
    "Q75 визитов",
    "Медиана выкупа",
    "Медиана выручки, ₽",
    "Минимум данных",
  ] as const;
  const headers = headerMap(rows[5], expected);
  const at = (row: Row, name: typeof expected[number]): Cell | undefined =>
    row[headers.get(name) as number];
  const result = {} as Record<"WB" | "Ozon", QeepThreshold>;
  for (const row of rows.slice(6, 8)) {
    const channel = requiredCellText(at(row, "Канал"), "forbid", warnings, 8);
    if (channel !== "WB" && channel !== "Ozon") {
      throw new Error("qeep_thresholds_invalid");
    }
    const threshold = {
      medianCr: requiredNumber(
        at(row, "Медиана CR визит→заказ"),
        "cached",
        warnings,
        0,
        1,
      ),
      medianDrr: requiredNumber(
        at(row, "Медиана ДРР"),
        "cached",
        warnings,
        0,
        10,
      ),
      q75Revenue: requiredNumber(at(row, "Q75 выручки, ₽"), "cached", warnings),
      q75Visits: requiredNumber(at(row, "Q75 визитов"), "cached", warnings),
      medianBuyout: requiredNumber(
        at(row, "Медиана выкупа"),
        "cached",
        warnings,
        0,
        1,
      ),
      medianRevenue: requiredNumber(
        at(row, "Медиана выручки, ₽"),
        "cached",
        warnings,
      ),
      minimumData: requiredNumber(
        at(row, "Минимум данных"),
        "cached",
        warnings,
        1,
        1_000_000,
      ),
    };
    if (
      !Number.isSafeInteger(threshold.minimumData) ||
      threshold.minimumData !== 30
    ) {
      throw new Error("qeep_thresholds_invalid");
    }
    result[channel] = threshold;
  }
  if (!result.WB || !result.Ozon) throw new Error("qeep_thresholds_invalid");
  return result;
}

type QeepProjection = {
  sourceRow: number;
  visits: number;
  orders: number;
  sales: number;
  status: string;
};

function qeepProjectionMismatches(
  workbook: Workbook,
  sourceRows: Map<string, QeepProjection>,
  warnings: Record<string, number>,
): Set<string> {
  const mismatches = new Set<string>();
  let projectedCount = 0;
  for (
    const [sheetName, channel] of [
      ["WB_воронка", "WB"],
      ["Ozon_воронка", "Ozon"],
    ] as const
  ) {
    const rows = readSheetRows(workbook, sheetName, 500, 25);
    if (rows.length < 7) throw new Error("qeep_projection_missing");
    const expected = [
      "Артикул",
      "SKU МП",
      "Визиты",
      "Заказы",
      "Продажи",
      "Статус",
    ] as const;
    const headers = headerMap(rows[5], expected);
    const at = (row: Row, name: typeof expected[number]): Cell | undefined =>
      row[headers.get(name) as number];
    for (let rowIndex = 6; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex];
      if (
        !row.some((cell) =>
          cell?.v !== undefined && cell.v !== null && cell.v !== ""
        )
      ) {
        continue;
      }
      projectedCount += 1;
      const sku = requiredCellText(
        at(row, "Артикул"),
        "qeep_reference",
        warnings,
        160,
      );
      const marketplaceSku = requiredCellText(
        at(row, "SKU МП"),
        "qeep_reference",
        warnings,
        160,
      );
      const key = `${channel}:${sku}:${marketplaceSku}`;
      const source = sourceRows.get(key);
      if (!source) {
        mismatches.add(key);
        continue;
      }
      const visits = requiredNumber(
        at(row, "Визиты"),
        "qeep_reference",
        warnings,
      );
      const orders = requiredNumber(
        at(row, "Заказы"),
        "qeep_reference",
        warnings,
      );
      const sales = requiredNumber(
        at(row, "Продажи"),
        "qeep_reference",
        warnings,
      );
      const status = requiredCellText(
        at(row, "Статус"),
        "qeep_reference",
        warnings,
        80,
      );
      if (
        visits !== source.visits || orders !== source.orders ||
        sales !== source.sales || status !== source.status
      ) mismatches.add(key);
    }
  }
  warnings.qeep_projection_rows = projectedCount;
  warnings.qeep_normalized_projection_rows = sourceRows.size;
  if (projectedCount !== sourceRows.size) {
    throw new Error("qeep_projection_count_mismatch");
  }
  return mismatches;
}

export async function parseQeepWorkbook(
  workbook: Workbook,
): Promise<ParseResult> {
  const sheetName = "SKU_итог";
  const rows = readSheetRows(workbook, sheetName, 1_000, 50);
  if (rows.length < 2) throw new Error("qeep_sheet_invalid");
  const expected = [
    "Канал",
    "Артикул поставщика",
    "SKU МП",
    "Категория",
    "Товар",
    "Визиты карточки",
    "Корзины",
    "Заказы, шт",
    "Продажи/выкупы, шт",
    "Выручка, ₽",
    "CV визит→корзина",
    "CV корзина→заказ",
    "CR визит→заказ",
    "Выкуп, %",
    "Расход РК, ₽",
    "ДРР, %",
    "Органические клики",
    "Доля органики, %",
    "Маржа после РК, ₽",
    "Маржа после РК, %",
    "Остаток, шт",
    "Запас, дней",
    "КЗ просмотры",
    "КЗ заказы",
    "КЗ продажи",
    "Статус",
  ] as const;
  const headers = headerMap(rows[0], expected);
  const at = (row: Row, name: typeof expected[number]): Cell | undefined =>
    row[headers.get(name) as number];
  const warnings: Record<string, number> = {};
  const quarantine: QuarantineItem[] = [];
  const cases: HistoricalCase[] = [];
  const thresholds = qeepThresholds(workbook, warnings);
  const projections = new Map<string, QeepProjection>();
  const caseByProjection = new Map<string, HistoricalCase>();

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    if (
      !row.some((cell) =>
        cell?.v !== undefined && cell.v !== null && cell.v !== ""
      )
    ) {
      continue;
    }
    const sourceRow = rowIndex + 1;
    try {
      const channel = requiredCellText(at(row, "Канал"), "forbid", warnings, 8);
      if (channel !== "WB" && channel !== "Ozon") {
        throw new Error("qeep_channel_invalid");
      }
      const productSku = requiredCellText(
        at(row, "Артикул поставщика"),
        "forbid",
        warnings,
        160,
      );
      const marketplaceSku = requiredCellText(
        at(row, "SKU МП"),
        "forbid",
        warnings,
        160,
      );
      const sourceCategory = requiredCellText(
        at(row, "Категория"),
        "forbid",
        warnings,
        160,
      );
      const productCategory = qeepProductCategory(sourceCategory);
      if (productCategory === null) {
        throw new Error("product_category_review_required");
      }
      const productTitle = requiredCellText(
        at(row, "Товар"),
        "forbid",
        warnings,
        180,
      );
      const visits = requiredNumber(
        at(row, "Визиты карточки"),
        "forbid",
        warnings,
      );
      const carts = requiredNumber(at(row, "Корзины"), "forbid", warnings);
      const orders = requiredNumber(at(row, "Заказы, шт"), "forbid", warnings);
      const sales = requiredNumber(
        at(row, "Продажи/выкупы, шт"),
        "forbid",
        warnings,
      );
      const revenue = requiredNumber(
        at(row, "Выручка, ₽"),
        "forbid",
        warnings,
        -1_000_000_000_000,
      );
      const visitToCartRate = requiredNumber(
        at(row, "CV визит→корзина"),
        "cached",
        warnings,
        0,
        1,
      );
      const cartToOrderRate = requiredNumber(
        at(row, "CV корзина→заказ"),
        "cached",
        warnings,
        0,
        1,
      );
      const visitToOrderRate = requiredNumber(
        at(row, "CR визит→заказ"),
        "cached",
        warnings,
        0,
        1,
      );
      const buyoutRate = requiredNumber(
        at(row, "Выкуп, %"),
        "cached",
        warnings,
        0,
        10,
      );
      const adSpend = requiredNumber(
        at(row, "Расход РК, ₽"),
        "forbid",
        warnings,
      );
      const drr = requiredNumber(
        at(row, "ДРР, %"),
        "cached",
        warnings,
        -100,
        100,
      );
      const organicClicks = requiredNumber(
        at(row, "Органические клики"),
        "forbid",
        warnings,
        -1_000_000_000_000,
      );
      const organicShare = requiredNumber(
        at(row, "Доля органики, %"),
        "cached",
        warnings,
        -100,
        100,
      );
      const margin = requiredNumber(
        at(row, "Маржа после РК, ₽"),
        "cached",
        warnings,
        -1_000_000_000_000,
      );
      const marginRate = requiredNumber(
        at(row, "Маржа после РК, %"),
        "cached",
        warnings,
        -100,
        100,
      );
      const stock = optionalNumber(at(row, "Остаток, шт"), "forbid", warnings);
      const stockDays = optionalNumber(
        at(row, "Запас, дней"),
        "cached",
        warnings,
      );
      const kzViews = requiredNumber(
        at(row, "КЗ просмотры"),
        "forbid",
        warnings,
      );
      const kzOrders = requiredNumber(at(row, "КЗ заказы"), "forbid", warnings);
      const kzSales = requiredNumber(at(row, "КЗ продажи"), "forbid", warnings);
      const cachedStatus = requiredCellText(
        at(row, "Статус"),
        "cached",
        warnings,
        80,
      );
      if (
        ![
          visits,
          carts,
          orders,
          sales,
          organicClicks,
          kzViews,
          kzOrders,
          kzSales,
        ]
          .every(Number.isSafeInteger) ||
        carts > visits || orders > carts ||
        organicClicks > visits || kzOrders > kzViews ||
        kzSales > kzOrders
      ) throw new Error("qeep_funnel_invariant_failed");
      if (sales > orders) {
        warnings.sales_exceed_period_orders =
          (warnings.sales_exceed_period_orders ?? 0) + 1;
      }
      const expectedRates = [
        ratio(carts, visits),
        ratio(orders, carts),
        ratio(orders, visits),
        ratio(sales, orders),
        ratio(adSpend, revenue),
        ratio(organicClicks, visits),
        ratio(margin, revenue),
      ];
      const cachedRates = [
        visitToCartRate,
        cartToOrderRate,
        visitToOrderRate,
        buyoutRate,
        drr,
        organicShare,
        marginRate,
      ];
      if (
        cachedRates.some((value, index) =>
          !approximately(value, expectedRates[index], 0.00001)
        )
      ) throw new Error("qeep_metric_mismatch");
      const statusMetrics: QeepStatusMetrics = {
        visits,
        orders,
        sales,
        revenue,
        visitToOrderRate,
        buyoutRate,
        adSpend,
        drr,
        marginRate,
        organicShare,
        stockDays,
      };
      const expectedStatus = qeepExpectedStatus(
        statusMetrics,
        thresholds[channel],
      );
      if (cachedStatus !== expectedStatus) {
        throw new Error("qeep_status_mismatch");
      }
      const classification = qeepOutcome(expectedStatus);
      if (classification === null) throw new Error("qeep_status_unknown");
      const metrics = {
        visits,
        carts,
        orders,
        sales,
        revenue,
        visit_to_cart_rate: visitToCartRate,
        cart_to_order_rate: cartToOrderRate,
        visit_to_order_rate: visitToOrderRate,
        buyout_rate: buyoutRate,
        ad_spend: adSpend,
        drr,
        organic_clicks: organicClicks,
        organic_share: organicShare,
        margin,
        margin_rate: marginRate,
        ...(stock === null ? {} : { stock }),
        ...(stockDays === null ? {} : { stock_days: stockDays }),
        kz_views: kzViews,
        kz_orders: kzOrders,
        kz_sales: kzSales,
      };
      const rowHash = await jsonHash({
        sheet: sheetName,
        row: sourceRow,
        channel,
        product_sku: productSku,
        marketplace_sku: marketplaceSku,
        source_category: sourceCategory,
        product_title: productTitle,
        status: expectedStatus,
        metrics,
      });
      const platform = channel === "WB" ? "wildberries" : "ozon";
      const historicalCase: HistoricalCase = {
        external_case_id: `qeep:${platform}:${safeExternalPart(productSku)}:${
          safeExternalPart(marketplaceSku)
        }:2026-05-01_2026-07-29`,
        product_category: productCategory,
        product_sku: productSku,
        marketplace_sku: marketplaceSku,
        product_title: productTitle,
        brand: "QEEP",
        platform,
        channel: "marketplace_funnel",
        period_start: "2026-05-01",
        period_end: "2026-07-29",
        outcome: classification.outcome,
        outcome_dimension: classification.dimension,
        status_label: expectedStatus,
        metrics,
        confidence: classification.confidence,
        provenance: { sheet: sheetName, row: sourceRow, row_hash: rowHash },
      };
      validateHistoricalCase(historicalCase);
      const projectionKey = `${channel}:${productSku}:${marketplaceSku}`;
      if (projections.has(projectionKey)) {
        throw new Error("qeep_duplicate_sku_channel");
      }
      projections.set(projectionKey, {
        sourceRow,
        visits,
        orders,
        sales,
        status: expectedStatus,
      });
      caseByProjection.set(projectionKey, historicalCase);
      cases.push(historicalCase);
    } catch (error) {
      addQuarantine(quarantine, sheetName, sourceRow, error);
    }
  }
  if (cases.length + quarantine.length < 1) throw new Error("qeep_cases_empty");
  const projectionMismatches = qeepProjectionMismatches(
    workbook,
    projections,
    warnings,
  );
  if (projectionMismatches.size > 0) {
    for (const key of projectionMismatches) {
      const historicalCase = caseByProjection.get(key);
      if (historicalCase) {
        addQuarantine(
          quarantine,
          historicalCase.provenance.sheet,
          historicalCase.provenance.row,
          new Error("qeep_projection_mismatch"),
        );
      }
    }
  }
  const safeCases = cases.filter((historicalCase) =>
    !projectionMismatches.has(
      `${
        historicalCase.platform === "wildberries" ? "WB" : "Ozon"
      }:${historicalCase.product_sku}:${historicalCase.marketplace_sku}`,
    )
  );
  return {
    adapter: "qeep_funnel_v1",
    parserVersion: "creator-ai-case-import-qeep-funnel-v1",
    cases: safeCases,
    quarantine,
    warnings,
  };
}

const CANONICAL_REQUIRED_HEADERS = [
  "external_case_id",
  "product_category",
  "product_title",
  "brand",
  "platform",
  "channel",
  "period_start",
  "period_end",
  "outcome",
  "outcome_dimension",
  "status_label",
  "confidence",
] as const;
const CANONICAL_OPTIONAL_HEADERS = new Set([
  "product_sku",
  "marketplace_sku",
  "creative_angle",
]);

function detectCsvDelimiter(text: string): "," | ";" | "\t" {
  const sample = text.slice(0, 8_192);
  const counts = new Map<"," | ";" | "\t", number>([
    [",", 0],
    [";", 0],
    ["\t", 0],
  ]);
  let quoted = false;
  for (let index = 0; index < sample.length; index += 1) {
    const character = sample[index];
    if (character === '"') {
      if (quoted && sample[index + 1] === '"') index += 1;
      else quoted = !quoted;
      continue;
    }
    if (!quoted && (character === "\r" || character === "\n")) break;
    if (!quoted && counts.has(character as "," | ";" | "\t")) {
      const delimiter = character as "," | ";" | "\t";
      counts.set(delimiter, (counts.get(delimiter) ?? 0) + 1);
    }
  }
  const sorted = [...counts.entries()].sort((left, right) =>
    right[1] - left[1]
  );
  if (sorted[0][1] < 1 || sorted[0][1] === sorted[1][1]) {
    throw new Error("csv_delimiter_invalid");
  }
  return sorted[0][0];
}

export function parseCsvMatrix(bytes: Uint8Array): string[][] {
  if (bytes.byteLength < 2 || bytes.byteLength > MAX_SOURCE_BYTES) {
    throw new Error("source_size_invalid");
  }
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new Error("csv_utf8_required");
  }
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  if (text.includes("\u0000")) throw new Error("csv_control_character");
  const delimiter = detectCsvDelimiter(text);
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          cell += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        cell += character;
      }
    } else if (character === '"') {
      if (cell.length !== 0) throw new Error("csv_quote_invalid");
      quoted = true;
    } else if (character === delimiter) {
      row.push(cell);
      cell = "";
    } else if (character === "\r" || character === "\n") {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      if (rows.length > MAX_ROWS) throw new Error("csv_rows_exceeded");
    } else {
      cell += character;
    }
    if (cell.length > MAX_CSV_CELL_TEXT) throw new Error("csv_cell_too_long");
  }
  if (quoted) throw new Error("csv_quote_invalid");
  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }
  while (
    rows.length > 0 && rows[rows.length - 1].every((value) => value === "")
  ) {
    rows.pop();
  }
  if (rows.length < 2) throw new Error("csv_rows_missing");
  const width = rows[0].length;
  if (
    width < 2 || width > MAX_COLUMNS ||
    rows.some((item) => item.length !== width)
  ) {
    throw new Error("csv_columns_invalid");
  }
  return rows;
}

function canonicalPlainText(
  value: string,
  maximum: number,
  minimum = 1,
): string {
  if (!boundedText(value, minimum, maximum)) {
    throw new Error("canonical_text_invalid");
  }
  return value;
}

function canonicalIdentifier(
  value: string,
  optional = false,
): string | undefined {
  if (optional && value === "") return undefined;
  if (!SAFE_ID_PATTERN.test(value)) {
    throw new Error("canonical_identifier_invalid");
  }
  return value;
}

function canonicalSku(value: string): string | undefined {
  if (value === "") return undefined;
  if (!SAFE_SKU_PATTERN.test(value)) {
    throw new Error("canonical_sku_invalid");
  }
  return value;
}

function canonicalChannel(value: string): string {
  if (!CHANNEL_PATTERN.test(value)) {
    throw new Error("canonical_channel_invalid");
  }
  return value;
}

function canonicalNumber(value: string): number {
  if (!/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$/u.test(value)) {
    throw new Error("canonical_number_invalid");
  }
  const number = Number(value);
  if (!Number.isFinite(number) || Math.abs(number) > 1_000_000_000_000) {
    throw new Error("canonical_number_invalid");
  }
  return number;
}

async function parseCanonicalMatrix(
  matrix: string[][],
  sheetName: string,
): Promise<ParseResult> {
  const headers = matrix[0];
  if (
    headers.some((header) => header !== header.trim() || header === "") ||
    new Set(headers).size !== headers.length
  ) throw new Error("canonical_headers_invalid");
  const headerSet = new Set(headers);
  if (CANONICAL_REQUIRED_HEADERS.some((header) => !headerSet.has(header))) {
    throw new Error("canonical_headers_invalid");
  }
  const metricHeaders = headers.filter((header) =>
    header.startsWith("metric_")
  );
  if (
    metricHeaders.length < 1 || metricHeaders.length > 20 ||
    metricHeaders.some((header) => !METRIC_KEY_PATTERN.test(header.slice(7))) ||
    headers.some((header) =>
      !CANONICAL_REQUIRED_HEADERS.includes(
        header as typeof CANONICAL_REQUIRED_HEADERS[number],
      ) && !CANONICAL_OPTIONAL_HEADERS.has(header) &&
      !header.startsWith("metric_")
    )
  ) throw new Error("canonical_headers_invalid");
  const positions = new Map(headers.map((header, index) => [header, index]));
  const cases: HistoricalCase[] = [];
  const quarantine: QuarantineItem[] = [];
  for (let rowIndex = 1; rowIndex < matrix.length; rowIndex += 1) {
    const row = matrix[rowIndex];
    if (row.every((value) => value === "")) continue;
    const sourceRow = rowIndex + 1;
    const value = (key: string): string =>
      row[positions.get(key) as number] ?? "";
    try {
      const productCategory = value("product_category") as ProductCategory;
      const platform = value("platform");
      const outcome = value("outcome") as HistoricalCase["outcome"];
      const outcomeDimension = value("outcome_dimension");
      const creativeAngle = positions.has("creative_angle")
        ? value("creative_angle")
        : "";
      if (
        !PRODUCT_CATEGORIES.has(productCategory) || !PLATFORMS.has(platform) ||
        !OUTCOMES.has(outcome) || !OUTCOME_DIMENSIONS.has(outcomeDimension) ||
        (creativeAngle !== "" && !CREATIVE_ANGLES.has(creativeAngle))
      ) throw new Error("canonical_enum_invalid");
      const periodStart = value("period_start");
      const periodEnd = value("period_end");
      if (
        !/^\d{4}-\d{2}-\d{2}$/u.test(periodStart) ||
        !/^\d{4}-\d{2}-\d{2}$/u.test(periodEnd) ||
        !periodIsValid(periodStart, periodEnd)
      ) throw new Error("canonical_period_invalid");
      const confidence = canonicalNumber(value("confidence"));
      if (confidence < 0 || confidence > 1) {
        throw new Error("canonical_confidence_invalid");
      }
      const metrics = Object.fromEntries(
        metricHeaders.map((
          header,
        ) => [header.slice(7), canonicalNumber(value(header))]),
      );
      const productSku = positions.has("product_sku")
        ? canonicalSku(value("product_sku"))
        : undefined;
      const marketplaceSku = positions.has("marketplace_sku")
        ? canonicalSku(value("marketplace_sku"))
        : undefined;
      const rowHash = await jsonHash({
        sheet: sheetName,
        row: sourceRow,
        values: row,
      });
      const historicalCase: HistoricalCase = {
        external_case_id: canonicalIdentifier(
          value("external_case_id"),
        ) as string,
        product_category: productCategory,
        ...(productSku === undefined ? {} : { product_sku: productSku }),
        ...(marketplaceSku === undefined
          ? {}
          : { marketplace_sku: marketplaceSku }),
        product_title: canonicalPlainText(value("product_title"), 180, 2),
        brand: canonicalPlainText(value("brand"), 100),
        platform,
        channel: canonicalChannel(value("channel")),
        period_start: periodStart,
        period_end: periodEnd,
        outcome,
        outcome_dimension: outcomeDimension,
        status_label: canonicalPlainText(value("status_label"), 80),
        metrics,
        confidence,
        ...(creativeAngle === "" ? {} : { creative_angle: creativeAngle }),
        provenance: { sheet: sheetName, row: sourceRow, row_hash: rowHash },
      };
      validateHistoricalCase(historicalCase);
      cases.push(historicalCase);
    } catch (error) {
      addQuarantine(quarantine, sheetName, sourceRow, error);
    }
  }
  if (cases.length + quarantine.length < 1) {
    throw new Error("canonical_cases_empty");
  }
  return {
    adapter: "canonical_v1",
    parserVersion: "creator-ai-case-import-canonical-v1",
    cases,
    quarantine,
    warnings: {},
  };
}

export async function parseCanonicalCsv(
  bytes: Uint8Array,
): Promise<ParseResult> {
  return await parseCanonicalMatrix(parseCsvMatrix(bytes), "CSV");
}

async function parseCanonicalWorkbook(
  workbook: Workbook,
): Promise<ParseResult> {
  const sheetName = workbook.SheetNames.includes("AI_cases")
    ? "AI_cases"
    : workbook.SheetNames[0];
  const rows = readSheetRows(workbook, sheetName, MAX_ROWS, MAX_COLUMNS);
  const matrix = rows.map((row) =>
    row.map((cell) => {
      if (cell?.f !== undefined) throw new Error("canonical_formula_forbidden");
      const value = cell?.v;
      if (value === undefined || value === null) return "";
      if (!["string", "number", "boolean"].includes(typeof value)) {
        throw new Error("canonical_cell_invalid");
      }
      return String(value);
    })
  );
  return await parseCanonicalMatrix(matrix, sheetName);
}

export function readSourceReceipt(
  value: unknown,
  requestPayload: ImportRequest,
  actorProfileId: string,
): SourceReceipt | null {
  if (
    !isRecord(value) || value.ok !== true ||
    value.organization_id !== requestPayload.organizationId ||
    value.actor_profile_id !== actorProfileId ||
    value.server_parser_authorized !== true ||
    value.bounded_source_receipt !== true ||
    !isRecord(value.source)
  ) return null;
  const source = value.source;
  const sizeBytes = Number(source.size_bytes);
  if (
    source.source_id !== requestPayload.sourceId ||
    source.product_category !== requestPayload.productCategory ||
    source.rights_confirmed !== true || source.bucket_id !== STORAGE_BUCKET ||
    typeof source.object_name !== "string" || source.object_name.length < 10 ||
    source.object_name.length > 1_000 || source.object_name.includes("\\") ||
    source.object_name.split("/").some((part) => part === "..") ||
    typeof source.original_filename !== "string" ||
    source.original_filename !== source.original_filename.trim() ||
    source.original_filename.length < 1 ||
    source.original_filename.length > 240 ||
    source.original_filename.includes("/") ||
    source.original_filename.includes("\\") ||
    typeof source.mime_type !== "string" || source.mime_type.length > 160 ||
    !Number.isSafeInteger(sizeBytes) || sizeBytes < 1 ||
    sizeBytes > MAX_SOURCE_BYTES ||
    typeof source.sha256 !== "string" ||
    !SHA256_PATTERN.test(source.sha256)
  ) return null;
  const lowerName = source.original_filename.toLocaleLowerCase("en-US");
  const mimeType = source.mime_type.toLocaleLowerCase("en-US");
  if (
    !(
      (lowerName.endsWith(".xlsx") &&
        mimeType ===
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") ||
      (lowerName.endsWith(".csv") && mimeType === "text/csv")
    )
  ) return null;
  return {
    sourceId: requestPayload.sourceId,
    productCategory: requestPayload.productCategory,
    bucket: STORAGE_BUCKET,
    objectKey: source.object_name,
    originalFilename: source.original_filename,
    mimeType,
    sizeBytes,
    clientSha256: source.sha256,
  };
}

export async function authorizedSource(
  context: SupabaseContext<ContentEngineDatabase>,
  payload: ImportRequest,
): Promise<SourceReceipt | null> {
  const actorProfileId = context.userClaims?.id;
  if (
    typeof actorProfileId !== "string" || !UUID_PATTERN.test(actorProfileId)
  ) return null;
  try {
    const { data, error } = await context.supabaseAdmin.rpc(
      "creator_authorize_ai_historical_case_import",
      {
        p_payload: {
          organization_id: payload.organizationId,
          actor_profile_id: actorProfileId,
          source_id: payload.sourceId,
          product_category: payload.productCategory,
        },
      },
    );
    if (error !== null) {
      const errorCode = isRecord(error) && typeof error.code === "string"
        ? error.code
        : "";
      if (errorCode === "42501" || errorCode === "P0002") return null;
      throw new Error("source_authorization_unavailable");
    }
    const receipt = readSourceReceipt(data, payload, actorProfileId);
    if (receipt === null) {
      throw new Error("source_authorization_receipt_invalid");
    }
    return receipt;
  } catch {
    throw new Error("source_authorization_unavailable");
  }
}

export async function downloadSource(
  context: SupabaseContext<ContentEngineDatabase>,
  source: SourceReceipt,
): Promise<{ bytes: Uint8Array; serverSha256: string }> {
  let blob: Blob | null = null;
  try {
    const { data, error } = await context.supabaseAdmin.storage.from(
      source.bucket,
    )
      .download(source.objectKey);
    if (error === null && data instanceof Blob) blob = data;
  } catch {
    blob = null;
  }
  if (
    blob === null || blob.size !== source.sizeBytes ||
    blob.size > MAX_SOURCE_BYTES
  ) {
    throw new Error("source_download_failed");
  }
  const bytes = new Uint8Array(await blob.arrayBuffer());
  if (bytes.byteLength !== source.sizeBytes) {
    throw new Error("source_download_failed");
  }
  const serverSha256 = await sha256Hex(bytes);
  if (serverSha256 !== source.clientSha256) {
    throw new Error("source_sha256_mismatch");
  }
  return { bytes, serverSha256 };
}

async function parseSource(
  source: SourceReceipt,
  bytes: Uint8Array,
  requestedAdapter: ImportRequest["adapter"],
): Promise<ParseResult> {
  if (source.originalFilename.toLocaleLowerCase("en-US").endsWith(".csv")) {
    if (
      requestedAdapter !== "auto" && requestedAdapter !== "canonical_v1"
    ) throw new Error("adapter_source_mismatch");
    return await parseCanonicalCsv(bytes);
  }
  const workbook = workbookFromXlsx(bytes);
  let adapter = requestedAdapter;
  if (adapter === "auto") {
    if (workbook.SheetNames.includes("Эффект_контента")) {
      adapter = "harley_effect_content_v1";
    } else if (
      workbook.SheetNames.includes("SKU_итог") &&
      workbook.SheetNames.includes("WB_воронка") &&
      workbook.SheetNames.includes("Ozon_воронка") &&
      workbook.SheetNames.includes("Пороги")
    ) {
      adapter = "qeep_funnel_v1";
    } else if (workbook.SheetNames.includes("AI_cases")) {
      adapter = "canonical_v1";
    } else {
      throw new Error("adapter_not_detected");
    }
  }
  if (adapter === "harley_effect_content_v1") {
    return await parseHarleyWorkbook(workbook, source.productCategory);
  }
  if (adapter === "qeep_funnel_v1") {
    return await parseQeepWorkbook(workbook);
  }
  if (adapter === "canonical_v1") return await parseCanonicalWorkbook(workbook);
  throw new Error("adapter_source_mismatch");
}

export async function parseHistoricalCaseBytes(
  bytes: Uint8Array,
  originalFilename: string,
  adapter: ImportRequest["adapter"] = "auto",
  productCategory: ProductCategory = "other",
): Promise<ParseResult> {
  if (
    originalFilename !== originalFilename.trim() ||
    originalFilename.includes("/") || originalFilename.includes("\\") ||
    originalFilename.length < 1 || originalFilename.length > 240
  ) throw new Error("source_filename_invalid");
  const lower = originalFilename.toLocaleLowerCase("en-US");
  if (!lower.endsWith(".xlsx") && !lower.endsWith(".csv")) {
    throw new Error("source_filename_invalid");
  }
  return await parseSource(
    {
      sourceId: "00000000-0000-4000-8000-000000000000",
      productCategory,
      bucket: STORAGE_BUCKET,
      objectKey: "test/object",
      originalFilename,
      mimeType: lower.endsWith(".xlsx")
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "text/csv",
      sizeBytes: bytes.byteLength,
      clientSha256: "0".repeat(64),
    },
    bytes,
    adapter,
  );
}

function outcomeCounts(
  cases: readonly HistoricalCase[],
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const historicalCase of cases) {
    result[historicalCase.outcome] = (result[historicalCase.outcome] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort());
}

function categoryCounts(
  cases: readonly HistoricalCase[],
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const historicalCase of cases) {
    result[historicalCase.product_category] =
      (result[historicalCase.product_category] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort());
}

type BatchBuildInput = {
  organizationId: string;
  actorProfileId: string;
  sourceId: string;
  productCategory: ProductCategory;
  originalFilename: string;
  sourceSha256: string;
  parserVersion: string;
  cases: HistoricalCase[];
  requestIdempotencyKey: string;
  parsedRowCount?: number;
  parserQuarantineSummary?: Record<string, number>;
};

export async function buildHistoricalCaseBatchPayloads(
  input: BatchBuildInput,
): Promise<{ manifestSha256: string; payloads: Record<string, Json>[] }> {
  const parserQuarantineSummary = input.parserQuarantineSummary ?? {};
  const quarantineEntries = Object.entries(parserQuarantineSummary);
  const parserQuarantinedRowCount = quarantineEntries.reduce(
    (total, [, count]) => total + count,
    0,
  );
  const parsedRowCount = input.parsedRowCount ??
    input.cases.length + parserQuarantinedRowCount;
  if (
    !UUID_PATTERN.test(input.organizationId) ||
    !UUID_PATTERN.test(input.actorProfileId) ||
    !UUID_PATTERN.test(input.sourceId) ||
    !UUID_PATTERN.test(input.requestIdempotencyKey) ||
    !PRODUCT_CATEGORIES.has(input.productCategory) ||
    !SHA256_PATTERN.test(input.sourceSha256) || input.cases.length > 10_000 ||
    input.originalFilename.length < 1 || input.originalFilename.length > 240 ||
    input.parserVersion.length < 1 || input.parserVersion.length > 80 ||
    !Number.isSafeInteger(parsedRowCount) ||
    parsedRowCount < input.cases.length ||
    parsedRowCount !== input.cases.length + parserQuarantinedRowCount ||
    quarantineEntries.length > 30 ||
    quarantineEntries.some(([code, count]) =>
      !/^[a-z][a-z0-9_]{0,47}$/u.test(code) || !Number.isSafeInteger(count) ||
      count < 1 || count > 10_000
    ) || stableJson(parserQuarantineSummary).length > 4_096
  ) throw new Error("batch_input_invalid");
  const duplicateIds = input.cases.filter((historicalCase, index, values) =>
    values.findIndex((candidate) =>
      candidate.external_case_id === historicalCase.external_case_id
    ) !== index
  );
  if (duplicateIds.length > 0) throw new Error("normalized_cases_invalid");
  for (const historicalCase of input.cases) {
    validateHistoricalCase(historicalCase);
  }
  const manifest = {
    schema_version: SCHEMA_VERSION,
    product_category: input.productCategory,
    original_filename: input.originalFilename,
    source_sha256: input.sourceSha256,
    parser_version: input.parserVersion,
    parsed_row_count: parsedRowCount,
    parser_quarantine_summary: parserQuarantineSummary,
    cases: input.cases,
  };
  const manifestSha256 = await jsonHash(manifest);
  const chunks: HistoricalCase[][] = [];
  for (let index = 0; index < input.cases.length; index += MAX_BATCH_SIZE) {
    chunks.push(input.cases.slice(index, index + MAX_BATCH_SIZE));
  }
  if (chunks.length === 0 && parsedRowCount > 0) chunks.push([]);
  const payloads = chunks.map((cases, index) => {
    const assignedQuarantineCount = index === 0 ? parserQuarantinedRowCount : 0;
    const assignedQuarantineSummary = index === 0
      ? parserQuarantineSummary
      : {};
    return {
      organization_id: input.organizationId,
      actor_profile_id: input.actorProfileId,
      source_id: input.sourceId,
      schema_version: SCHEMA_VERSION,
      product_category: input.productCategory,
      original_filename: input.originalFilename,
      source_sha256: input.sourceSha256,
      parser_version: input.parserVersion,
      manifest_sha256: manifestSha256,
      idempotency_key: `ai-historical:${input.requestIdempotencyKey}:${
        manifestSha256.slice(0, 16)
      }:${index + 1}/${chunks.length}`,
      batch_index: index + 1,
      batch_count: chunks.length,
      cases,
      parsed_row_count: cases.length + assignedQuarantineCount,
      parser_quarantined_row_count: assignedQuarantineCount,
      parser_quarantine_summary: assignedQuarantineSummary,
    };
  });
  return { manifestSha256, payloads };
}

export async function importCases(
  context: SupabaseContext<ContentEngineDatabase>,
  payload: ImportRequest,
  source: SourceReceipt,
  serverSha256: string,
  parsed: ParseResult,
): Promise<{
  manifestSha256: string;
  plannedBatches: number;
  acceptedBatches: number;
  importedCases: number;
  matchedCases: number;
  databaseQuarantinedCases: number;
  parserRejectedAll: boolean;
  authoritativeBatch: Json | null;
  batchPersisted: boolean;
  snapshot: Json | null;
}> {
  const actorProfileId = context.userClaims?.id;
  if (
    typeof actorProfileId !== "string" || !UUID_PATTERN.test(actorProfileId)
  ) {
    throw new Error("historical_case_actor_context_invalid");
  }
  const built = await buildHistoricalCaseBatchPayloads({
    organizationId: payload.organizationId,
    actorProfileId,
    sourceId: source.sourceId,
    productCategory: source.productCategory,
    originalFilename: source.originalFilename,
    sourceSha256: serverSha256,
    parserVersion: parsed.parserVersion,
    cases: parsed.cases,
    requestIdempotencyKey: payload.idempotencyKey,
    parsedRowCount: parsed.cases.length + parsed.quarantine.length,
    parserQuarantineSummary: Object.fromEntries(
      [...new Set(parsed.quarantine.map((item) => item.code))]
        .sort()
        .map((code) => [
          code,
          parsed.quarantine.filter((item) => item.code === code).length,
        ]),
    ),
  });
  if (!payload.commit) {
    return {
      manifestSha256: built.manifestSha256,
      plannedBatches: built.payloads.length,
      acceptedBatches: 0,
      importedCases: 0,
      matchedCases: 0,
      databaseQuarantinedCases: 0,
      parserRejectedAll: false,
      authoritativeBatch: null,
      batchPersisted: false,
      snapshot: null,
    };
  }
  if (built.payloads.length < 1) throw new Error("no_importable_cases");
  let snapshot: Json | null = null;
  let importedCases = 0;
  let matchedCases = 0;
  let databaseQuarantinedCases = 0;
  let parserRejectedAll = false;
  let authoritativeBatch: Json | null = null;
  let batchPersisted = false;
  let acceptedBatches = 0;
  for (const batchPayload of built.payloads) {
    let data: unknown = null;
    let rpcError: unknown = null;
    try {
      const response = await context.supabaseAdmin.rpc(
        "creator_import_ai_historical_case_batch",
        { p_payload: batchPayload as Json },
      );
      data = response.data;
      rpcError = response.error;
    } catch {
      throw new Error("historical_case_import_unavailable");
    }
    const allRejectedAccepted = parsed.cases.length === 0 && isRecord(data) &&
      data.ok === false && data.status === "parser_rejected_all";
    if (
      rpcError !== null || !isRecord(data) ||
      (data.ok !== true && !allRejectedAccepted)
    ) {
      throw new Error("historical_case_import_rejected");
    }
    if (!isRecord(data.batch)) {
      throw new Error("historical_case_import_response_invalid");
    }
    const caseCount = Number(data.batch.case_count);
    const matchedCaseCount = Number(data.batch.matched_case_count);
    const quarantinedCaseCount = Number(data.batch.quarantined_case_count);
    const parsedRowCount = Number(data.batch.parsed_row_count);
    const parserQuarantinedRowCount = Number(
      data.batch.parser_quarantined_row_count,
    );
    if (
      !Number.isSafeInteger(caseCount) || caseCount < 0 ||
      !Number.isSafeInteger(matchedCaseCount) || matchedCaseCount < 0 ||
      !Number.isSafeInteger(quarantinedCaseCount) || quarantinedCaseCount < 0 ||
      !Number.isSafeInteger(parsedRowCount) || parsedRowCount < 1 ||
      !Number.isSafeInteger(parserQuarantinedRowCount) ||
      parserQuarantinedRowCount < 0 ||
      matchedCaseCount + quarantinedCaseCount !== caseCount ||
      !Array.isArray(batchPayload.cases) ||
      caseCount !== batchPayload.cases.length ||
      parsedRowCount !== Number(batchPayload.parsed_row_count) ||
      parserQuarantinedRowCount !==
        Number(batchPayload.parser_quarantined_row_count) ||
      !isRecord(data.batch.parser_quarantine_summary) ||
      stableJson(data.batch.parser_quarantine_summary) !==
        stableJson(batchPayload.parser_quarantine_summary) ||
      data.batch_persisted !== true ||
      typeof data.replayed !== "boolean" ||
      (allRejectedAccepted &&
        (caseCount !== 0 || matchedCaseCount !== 0 ||
          quarantinedCaseCount !== 0 || data.retryable !== true))
    ) throw new Error("historical_case_import_response_invalid");
    if (data.replayed === false) {
      acceptedBatches += 1;
      importedCases += caseCount;
      matchedCases += matchedCaseCount;
      databaseQuarantinedCases += quarantinedCaseCount;
    }
    parserRejectedAll ||= allRejectedAccepted;
    authoritativeBatch = data.batch as Json;
    batchPersisted = true;
    if (!isRecord(data.snapshot)) {
      throw new Error("historical_case_import_response_invalid");
    }
    snapshot = data.snapshot as Json;
  }
  return {
    manifestSha256: built.manifestSha256,
    plannedBatches: built.payloads.length,
    acceptedBatches,
    importedCases,
    matchedCases,
    databaseQuarantinedCases,
    parserRejectedAll,
    authoritativeBatch,
    batchPersisted,
    snapshot,
  };
}

export async function handleCreatorAiCaseImport(
  request: Request,
  context: SupabaseContext<ContentEngineDatabase>,
): Promise<Response> {
  if (request.method !== "POST") {
    return json(request, { ok: false, code: "method_not_allowed" }, 405);
  }
  if (request.headers.get("origin") !== PUBLIC_APP_ORIGIN) {
    return json(request, { ok: false, code: "origin_not_allowed" }, 403);
  }
  const contentType = (request.headers.get("content-type") ?? "")
    .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
  if (contentType !== "application/json") {
    return json(request, { ok: false, code: "content_type_invalid" }, 415);
  }
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_REQUEST_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  let requestValue: unknown;
  try {
    requestValue = await readBoundedRequest(request);
  } catch (error) {
    const code = error instanceof Error && error.message === "request_too_large"
      ? "request_too_large"
      : "invalid_json";
    return json(
      request,
      { ok: false, code },
      code === "request_too_large" ? 413 : 400,
    );
  }
  const payload = readImportRequest(requestValue);
  if (payload === null) {
    return json(
      request,
      { ok: false, code: "ai_case_import_payload_invalid" },
      400,
    );
  }
  let source: SourceReceipt | null;
  try {
    source = await authorizedSource(context, payload);
  } catch {
    return json(
      request,
      {
        ok: false,
        code: "source_authorization_unavailable",
        retryable: true,
      },
      503,
    );
  }
  if (source === null) {
    return json(
      request,
      { ok: false, code: "ai_case_source_access_denied" },
      403,
    );
  }
  try {
    const { bytes, serverSha256 } = await downloadSource(context, source);
    const parsed = await parseSource(source, bytes, payload.adapter);
    const imported = await importCases(
      context,
      payload,
      source,
      serverSha256,
      parsed,
    );
    const parsedCount = parsed.cases.length + parsed.quarantine.length;
    const importedCount = imported.importedCases;
    const totalQuarantined = parsed.quarantine.length +
      imported.databaseQuarantinedCases;
    const parserQuarantineSummary = Object.fromEntries(
      [...new Set(parsed.quarantine.map((item) => item.code))]
        .sort()
        .map((code) => [
          code,
          parsed.quarantine.filter((item) => item.code === code).length,
        ]),
    );
    const commonResponse = {
      version: "creator-ai-case-import-v1",
      source_id: source.sourceId,
      source_sha256: serverSha256,
      adapter: parsed.adapter,
      parser_version: parsed.parserVersion,
      manifest_sha256: imported.manifestSha256,
      mode: payload.commit ? "commit" : "dry_run",
      parsed: parsedCount,
      imported: importedCount,
      quarantined: totalQuarantined,
      parser_quarantined: parsed.quarantine.length,
      parser_quarantine_summary: parserQuarantineSummary,
      database_quarantined: imported.databaseQuarantinedCases,
      matched: imported.matchedCases,
      errors: parsed.quarantine.length,
      per_category: categoryCounts(parsed.cases),
      per_outcome: outcomeCounts(parsed.cases),
      warnings: parsed.warnings,
      quarantine: parsed.quarantine.slice(0, MAX_RESPONSE_QUARANTINE),
      quarantine_truncated: parsed.quarantine.length > MAX_RESPONSE_QUARANTINE,
      snapshot: imported.snapshot,
    };
    if (payload.commit && imported.parserRejectedAll) {
      return json(request, {
        ok: false,
        status: "parser_rejected_all",
        retryable: true,
        batch_persisted: imported.batchPersisted,
        ...commonResponse,
        batch: imported.authoritativeBatch,
        import_status: "parser_rejected",
      });
    }
    const batchStatus = payload.commit ? "completed" : "preview";
    return json(request, {
      ok: true,
      ...commonResponse,
      batch: {
        status: batchStatus,
        planned: imported.plannedBatches,
        accepted: imported.acceptedBatches,
      },
      import_status: batchStatus,
    });
  } catch (error) {
    const candidate = error instanceof Error
      ? error.message
      : "ai_case_import_failed";
    const code = /^[a-z0-9_]{3,80}$/u.test(candidate)
      ? candidate
      : "ai_case_import_failed";
    const clientError = [
      "source_sha256_mismatch",
      "source_size_invalid",
      "xlsx_zip_invalid",
      "xlsx_zip_unsafe",
      "xlsx_parse_failed",
      "xlsx_structure_invalid",
      "xlsx_dimensions_exceeded",
      "xlsx_formula_unsafe",
      "xlsx_formula_cache_missing",
      "adapter_not_detected",
      "adapter_source_mismatch",
      "canonical_headers_invalid",
      "canonical_formula_forbidden",
      "canonical_cell_invalid",
      "canonical_cases_empty",
      "no_importable_cases",
    ].includes(code);
    return json(request, { ok: false, code }, clientError ? 422 : 503);
  }
}

const CREATOR_AI_CASE_IMPORT_OPTIONS = {
  auth: "user",
  cors: {
    "Access-Control-Allow-Headers":
      "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Origin": PUBLIC_APP_ORIGIN,
    Vary: "Origin",
  },
} as const;

const creatorAiCaseImport = withSupabase<ContentEngineDatabase>(
  CREATOR_AI_CASE_IMPORT_OPTIONS,
  handleCreatorAiCaseImport,
);

export default {
  fetch(request: Request): Promise<Response> | Response {
    if (request.method === "OPTIONS") {
      if (request.headers.get("origin") !== PUBLIC_APP_ORIGIN) {
        return json(request, { ok: false, code: "origin_not_allowed" }, 403);
      }
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }
    return creatorAiCaseImport(request);
  },
};
