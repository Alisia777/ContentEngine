// @deno-types="https://cdn.sheetjs.com/xlsx-0.20.3/package/types/index.d.ts"
import * as XLSX from "https://cdn.sheetjs.com/xlsx-0.20.3/package/xlsx.mjs";
import {
  authorizedSource,
  buildHistoricalCaseBatchPayloads,
  downloadSource,
  handleCreatorAiCaseImport,
  importCases,
  parseCanonicalCsv,
  parseCsvMatrix,
  parseHistoricalCaseBytes,
  preflightXlsx,
  qeepExpectedStatus,
  qeepProductCategory,
  readSourceReceipt,
} from "./index.ts";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertEquals(
  actual: unknown,
  expected: unknown,
  message: string,
): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${message}: ${JSON.stringify(actual)} !== ${JSON.stringify(expected)}`,
    );
  }
}

async function assertRejects(
  operation: () => Promise<unknown> | unknown,
  code: string,
): Promise<void> {
  try {
    await operation();
  } catch (error) {
    assert(error instanceof Error, "expected Error");
    assertEquals(error.message, code, "error code");
    return;
  }
  throw new Error(`expected rejection ${code}`);
}

const HEADERS = [
  "external_case_id",
  "product_category",
  "product_sku",
  "marketplace_sku",
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
  "creative_angle",
  "metric_orders",
  "metric_margin",
];

function canonicalCsv(overrides: Record<string, string> = {}): Uint8Array {
  const values: Record<string, string> = {
    external_case_id: "fixture:wildberries:sku-1:2026-07-29",
    product_category: "baa",
    product_sku: "sku-1",
    marketplace_sku: "500000001",
    product_title: "Fixture product",
    brand: "Fixture Brand",
    platform: "wildberries",
    channel: "marketplace_funnel",
    period_start: "2026-05-01",
    period_end: "2026-07-29",
    outcome: "good",
    outcome_dimension: "overall_performance",
    status_label: "Reviewed fixture status",
    confidence: "0.95",
    creative_angle: "product_focus",
    metric_orders: "101",
    metric_margin: "-10.5",
    ...overrides,
  };
  const escape = (value: string) =>
    /[",\r\n]/u.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
  return new TextEncoder().encode(
    `${HEADERS.join(",")}\r\n${
      HEADERS.map((header) => escape(values[header])).join(",")
    }\r\n`,
  );
}

function xlsxBytes(rows: unknown[][], sheetName = "AI_cases"): Uint8Array {
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(
    workbook,
    XLSX.utils.aoa_to_sheet(rows),
    sheetName,
  );
  return new Uint8Array(
    XLSX.write(workbook, { type: "array", bookType: "xlsx" }) as ArrayBuffer,
  );
}

const HARLEY_HEADERS = [
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
];

function harleyBadCaseBytes(): Uint8Array {
  return xlsxBytes(
    [
      [],
      [],
      [],
      [null, 30, null, null, 2, null, null, 0.01],
      [],
      HARLEY_HEADERS,
      [
        "fixture",
        "2026-06-15",
        "500000001",
        "SKU-1",
        "Fixture cream",
        "Прямая товарная рекомендация",
        "Да",
        "Сопоставимо",
        100,
        2,
        10,
        5,
        0,
        0.1,
        0.05,
        0,
        0,
        0,
        0,
        "Интерес без продажи",
      ],
    ],
    "Эффект_контента",
  );
}

Deno.test("canonical CSV accepts only bounded structured fields", async () => {
  const parsed = await parseCanonicalCsv(canonicalCsv());

  assertEquals(parsed.cases.length, 1, "one case parsed");
  assertEquals(parsed.quarantine.length, 0, "nothing quarantined");
  assertEquals(
    parsed.cases[0].metrics,
    { orders: 101, margin: -10.5 },
    "metrics",
  );
  assertEquals(parsed.cases[0].provenance.sheet, "CSV", "CSV provenance");
  assert(
    /^[0-9a-f]{64}$/u.test(parsed.cases[0].provenance.row_hash),
    "row hash",
  );
});

Deno.test("canonical CSV quarantines formula injection as data", async () => {
  const parsed = await parseCanonicalCsv(
    canonicalCsv({ product_title: "=WEBSERVICE(1)" }),
  );

  assertEquals(parsed.cases.length, 0, "unsafe row not normalized");
  assertEquals(
    parsed.quarantine[0].code,
    "canonical_text_invalid",
    "safe code",
  );
});

Deno.test("canonical row parity violations are quarantined before batch import", async () => {
  const fixtures: Array<{
    overrides: Record<string, string>;
    code: string;
  }> = [
    {
      overrides: { product_sku: `s${"x".repeat(120)}` },
      code: "canonical_sku_invalid",
    },
    {
      overrides: { channel: `c${"x".repeat(60)}` },
      code: "canonical_channel_invalid",
    },
    {
      overrides: { product_title: "x" },
      code: "canonical_text_invalid",
    },
    {
      overrides: { period_start: "2000-01-01", period_end: "2011-01-01" },
      code: "canonical_period_invalid",
    },
  ];
  for (const fixture of fixtures) {
    const parsed = await parseCanonicalCsv(canonicalCsv(fixture.overrides));
    assertEquals(parsed.cases.length, 0, "invalid row is not normalized");
    assertEquals(parsed.quarantine.length, 1, "invalid row is quarantined");
    assertEquals(
      parsed.quarantine[0].code,
      fixture.code,
      "bounded reason code",
    );
  }
});

Deno.test("canonical parity accepts bounded SKU/channel and 40-char metric key", async () => {
  const metricKey = "m".repeat(40);
  const csv = new TextDecoder().decode(canonicalCsv({
    product_sku: `s${"x".repeat(119)}`,
    channel: `c${"x".repeat(59)}`,
  })).replace("metric_orders", `metric_${metricKey}`);
  const parsed = await parseCanonicalCsv(new TextEncoder().encode(csv));

  assertEquals(parsed.quarantine, [], "boundary row accepted");
  assertEquals(parsed.cases.length, 1, "one bounded row");
  assertEquals(
    Object.keys(parsed.cases[0].metrics)[0],
    metricKey,
    "metric key",
  );
});

Deno.test("CSV parser is RFC4180 bounded and preserves quoted commas", () => {
  const matrix = parseCsvMatrix(
    new TextEncoder().encode('a,b\r\n1,"two, values"\r\n'),
  );
  assertEquals(matrix, [["a", "b"], ["1", "two, values"]], "matrix");
});

Deno.test("QEEP source categories are exact and unknown values fail closed", () => {
  assertEquals(qeepProductCategory("БАДы"), "baa", "BAA mapping");
  assertEquals(
    qeepProductCategory("Аминокислоты"),
    "sports_food",
    "sports mapping",
  );
  assertEquals(qeepProductCategory("Кремы"), "cosmetics", "cosmetics mapping");
  assertEquals(qeepProductCategory("Какао"), "food", "food mapping");
  assertEquals(qeepProductCategory("Almost БАДы"), null, "no fuzzy guessing");
});

Deno.test("QEEP status derivation preserves workbook priority", () => {
  const threshold = {
    medianCr: 0.05,
    medianDrr: 0.2,
    q75Revenue: 1_000_000,
    q75Visits: 100_000,
    medianBuyout: 0.8,
    medianRevenue: 500_000,
    minimumData: 30,
  };
  const base = {
    visits: 200_000,
    orders: 1_000,
    sales: 900,
    revenue: 2_000_000,
    visitToOrderRate: 0.06,
    buyoutRate: 0.9,
    adSpend: 100_000,
    drr: 0.05,
    marginRate: 0.3,
    organicShare: 0.85,
    stockDays: 30,
  };
  assertEquals(qeepExpectedStatus(base, threshold), "Суперзвезда", "star");
  assertEquals(
    qeepExpectedStatus({ ...base, orders: 29 }, threshold),
    "Мало данных",
    "minimum data has priority",
  );
  assertEquals(
    qeepExpectedStatus({ ...base, stockDays: 10 }, threshold),
    "Риск OOS",
    "stock risk has priority",
  );
  assertEquals(
    qeepExpectedStatus({ ...base, buyoutRate: 0.6 }, threshold),
    "Чинить выкуп",
    "buyout failure",
  );
  assertEquals(
    qeepExpectedStatus({ ...base, drr: 0.31 }, threshold),
    "Оптимизировать рекламу",
    "advertising failure",
  );
});

Deno.test("XLSX ZIP preflight accepts normal workbooks and rejects encryption flags", () => {
  const bytes = xlsxBytes([["a", "b"], [1, 2]]);
  const result = preflightXlsx(bytes);
  assert(result.entryCount > 1, "normal workbook has entries");
  const unsafe = Uint8Array.from(bytes);
  const view = new DataView(unsafe.buffer);
  let central = -1;
  for (let index = 0; index <= unsafe.length - 4; index += 1) {
    if (view.getUint32(index, true) === 0x02014b50) {
      central = index;
      break;
    }
  }
  assert(central >= 0, "central directory located");
  view.setUint16(central + 8, view.getUint16(central + 8, true) | 1, true);
  let code = "";
  try {
    preflightXlsx(unsafe);
  } catch (error) {
    code = error instanceof Error ? error.message : "";
  }
  assertEquals(code, "xlsx_zip_unsafe", "encrypted entry rejected");
});

Deno.test("canonical XLSX never accepts cached formula cells", async () => {
  const rows = [
    HEADERS,
    HEADERS.map((header) => {
      const matrix = parseCsvMatrix(canonicalCsv());
      return matrix[1][HEADERS.indexOf(header)];
    }),
  ];
  const workbook = XLSX.utils.book_new();
  const sheet = XLSX.utils.aoa_to_sheet(rows);
  sheet.A2 = {
    t: "s",
    f: '"fixture:wildberries:sku-1:2026-07-29"',
    v: "fixture:wildberries:sku-1:2026-07-29",
  };
  XLSX.utils.book_append_sheet(workbook, sheet, "AI_cases");
  const bytes = new Uint8Array(
    XLSX.write(workbook, { type: "array", bookType: "xlsx" }) as ArrayBuffer,
  );

  await assertRejects(
    () => parseHistoricalCaseBytes(bytes, "canonical.xlsx", "canonical_v1"),
    "canonical_formula_forbidden",
  );
});

Deno.test("Harley bad evidence retains selected category and bounded creative angle", async () => {
  const parsed = await parseHistoricalCaseBytes(
    harleyBadCaseBytes(),
    "harley.xlsx",
    "harley_effect_content_v1",
    "cosmetics",
  );

  assertEquals(parsed.quarantine, [], "fixture parses without quarantine");
  assertEquals(parsed.cases.length, 1, "one Harley case");
  assertEquals(
    parsed.cases[0].product_category,
    "cosmetics",
    "source category",
  );
  assertEquals(parsed.cases[0].outcome, "bad", "bad outcome");
  assertEquals(
    parsed.cases[0].creative_angle,
    "product_focus",
    "bad feedback can become avoid evidence after confirmation",
  );
});

Deno.test("batch payloads split at 100 and have stable idempotency", async () => {
  const base = (index: number) => ({
    external_case_id: `fixture:wb:sku-${index}:2026-07-29`,
    product_category: "baa" as const,
    product_sku: `sku-${index}`,
    marketplace_sku: String(500_000_000 + index),
    product_title: `Fixture product ${index}`,
    brand: "Fixture Brand",
    platform: "wildberries",
    channel: "marketplace_funnel",
    period_start: "2026-05-01",
    period_end: "2026-07-29",
    outcome: "good" as const,
    outcome_dimension: "overall_performance",
    status_label: "Fixture reviewed status",
    metrics: { orders: 100 + index },
    confidence: 0.9,
    provenance: {
      sheet: "Fixture",
      row: index + 1,
      row_hash: index.toString(16).padStart(64, "0"),
    },
  });
  const input = {
    organizationId: "10000000-0000-4000-8000-000000000001",
    actorProfileId: "40000000-0000-4000-8000-000000000004",
    sourceId: "20000000-0000-4000-8000-000000000002",
    productCategory: "baa" as const,
    originalFilename: "fixture.xlsx",
    sourceSha256: "a".repeat(64),
    parserVersion: "fixture-parser-v1",
    cases: Array.from({ length: 201 }, (_, index) => base(index + 1)),
    requestIdempotencyKey: "30000000-0000-4000-8000-000000000003",
    parsedRowCount: 203,
    parserQuarantineSummary: { row_invalid: 2 },
  };

  const first = await buildHistoricalCaseBatchPayloads(input);
  const second = await buildHistoricalCaseBatchPayloads(structuredClone(input));
  const changedParserReceipt = await buildHistoricalCaseBatchPayloads({
    ...structuredClone(input),
    parserQuarantineSummary: { formula_forbidden: 2 },
  });

  assertEquals(first, second, "build is deterministic");
  assert(
    first.manifestSha256 !== changedParserReceipt.manifestSha256,
    "parser quarantine receipt is part of immutable manifest identity",
  );
  assertEquals(
    first.payloads.map((payload) =>
      Array.isArray(payload.cases) ? payload.cases.length : -1
    ),
    [100, 100, 1],
    "split",
  );
  assertEquals(
    first.payloads.map((payload) => payload.parsed_row_count),
    [102, 100, 1],
    "each chunk has bounded, non-duplicated lineage",
  );
  assertEquals(
    first.payloads.map((payload) => payload.parser_quarantined_row_count),
    [2, 0, 0],
    "parser quarantine is assigned once",
  );
  assertEquals(
    new Set(first.payloads.map((payload) => payload.idempotency_key)).size,
    3,
    "idempotency per batch",
  );
  assert(
    first.payloads.every((payload) =>
      payload.actor_profile_id === input.actorProfileId
    ),
    "service-role RPC payload carries authenticated actor context",
  );
});

Deno.test("all-rejected parser result remains auditable without fake cases", async () => {
  const built = await buildHistoricalCaseBatchPayloads({
    organizationId: "10000000-0000-4000-8000-000000000001",
    actorProfileId: "40000000-0000-4000-8000-000000000004",
    sourceId: "20000000-0000-4000-8000-000000000002",
    productCategory: "other",
    originalFilename: "fixture.csv",
    sourceSha256: "b".repeat(64),
    parserVersion: "fixture-parser-v1",
    cases: [],
    requestIdempotencyKey: "30000000-0000-4000-8000-000000000003",
    parsedRowCount: 2,
    parserQuarantineSummary: { canonical_text_invalid: 2 },
  });

  assertEquals(built.payloads.length, 1, "one rejection receipt batch");
  assertEquals(built.payloads[0].cases, [], "no invented cases");
  assertEquals(built.payloads[0].parsed_row_count, 2, "parsed count");
  assertEquals(
    built.payloads[0].parser_quarantined_row_count,
    2,
    "quarantine count",
  );
});

Deno.test("exact source authorization and download stay on the admin boundary", async () => {
  const organizationId = "10000000-0000-4000-8000-000000000001";
  const actorProfileId = "40000000-0000-4000-8000-000000000004";
  const sourceId = "20000000-0000-4000-8000-000000000002";
  const bytes = new TextEncoder().encode("bounded historical case fixture");
  const sha256 = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  ).map((value) => value.toString(16).padStart(2, "0")).join("");
  const request = {
    organizationId,
    sourceId,
    productCategory: "baa" as const,
    adapter: "auto" as const,
    commit: true,
    idempotencyKey: "30000000-0000-4000-8000-000000000003",
  };
  const receipt = {
    ok: true,
    organization_id: organizationId,
    actor_profile_id: actorProfileId,
    server_parser_authorized: true,
    bounded_source_receipt: true,
    source: {
      source_id: sourceId,
      product_category: "baa",
      bucket_id: "contentengine-knowledge",
      object_name: "org/knowledge/fixture.xlsx",
      original_filename: "fixture.xlsx",
      mime_type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      size_bytes: bytes.byteLength,
      sha256,
      rights_confirmed: true,
      event_cursor: 7,
    },
  };
  let userClientCalls = 0;
  let authorizationCalls = 0;
  let adminDownloads = 0;
  const context = {
    userClaims: { id: actorProfileId },
    supabase: {
      rpc: () => {
        userClientCalls += 1;
        throw new Error("authorization must not use user RPC");
      },
      storage: {
        from: () => {
          userClientCalls += 1;
          throw new Error("download must not use user storage");
        },
      },
    },
    supabaseAdmin: {
      rpc: (name: string, args: { p_payload: Record<string, unknown> }) => {
        authorizationCalls += 1;
        assertEquals(
          name,
          "creator_authorize_ai_historical_case_import",
          "exact authorization RPC",
        );
        assertEquals(args.p_payload, {
          organization_id: organizationId,
          actor_profile_id: actorProfileId,
          source_id: sourceId,
          product_category: "baa",
        }, "authorization scope");
        return Promise.resolve({ data: receipt, error: null });
      },
      storage: {
        from: (bucket: string) => {
          assertEquals(bucket, "contentengine-knowledge", "bounded bucket");
          return {
            download: (objectName: string) => {
              adminDownloads += 1;
              assertEquals(
                objectName,
                "org/knowledge/fixture.xlsx",
                "authorized object",
              );
              return Promise.resolve({ data: new Blob([bytes]), error: null });
            },
          };
        },
      },
    },
  } as unknown as Parameters<typeof authorizedSource>[0];

  assertEquals(
    readSourceReceipt(receipt, request, actorProfileId)?.sourceId,
    sourceId,
    "bounded receipt accepted",
  );
  assertEquals(
    readSourceReceipt(
      {
        ...receipt,
        category_detail: { knowledge_sources: [receipt.source] },
        source: undefined,
      },
      request,
      actorProfileId,
    ),
    null,
    "legacy paginated snapshot rejected",
  );
  const source = await authorizedSource(context, request);
  assert(source !== null, "exact source authorized");
  const downloaded = await downloadSource(context, source);
  assertEquals(downloaded.serverSha256, sha256, "server digest verified");
  assertEquals(userClientCalls, 0, "user client boundary");
  assertEquals(authorizationCalls, 1, "one exact authorization");
  assertEquals(adminDownloads, 1, "one admin download");

  const unavailableContext = {
    ...context,
    supabaseAdmin: {
      rpc: () => Promise.resolve({ data: null, error: { code: "XX000" } }),
    },
  } as unknown as Parameters<typeof authorizedSource>[0];
  await assertRejects(
    () => authorizedSource(unavailableContext, request),
    "source_authorization_unavailable",
  );

  const deniedContext = {
    ...context,
    supabaseAdmin: {
      rpc: () => Promise.resolve({ data: null, error: { code: "42501" } }),
    },
  } as unknown as Parameters<typeof authorizedSource>[0];
  assertEquals(
    await authorizedSource(deniedContext, request),
    null,
    "scoped authorization denial remains a 403 path",
  );
});

Deno.test("authorization infrastructure failure is retryable, not a false denial", async () => {
  const requestBody = {
    organization_id: "10000000-0000-4000-8000-000000000001",
    action: "parse_and_import",
    product_category: "baa",
    source_id: "20000000-0000-4000-8000-000000000002",
    adapter: "auto",
    commit: true,
    idempotency_key: "30000000-0000-4000-8000-000000000003",
  };
  const makeRequest = () =>
    new Request(
      "https://fixture.supabase.co/functions/v1/creator-ai-case-import",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          origin: "https://alisia777.github.io",
        },
        body: JSON.stringify(requestBody),
      },
    );
  const contextFor = (code: string) =>
    ({
      userClaims: { id: "40000000-0000-4000-8000-000000000004" },
      supabaseAdmin: {
        rpc: () => Promise.resolve({ data: null, error: { code } }),
      },
    }) as unknown as Parameters<typeof handleCreatorAiCaseImport>[1];

  const unavailable = await handleCreatorAiCaseImport(
    makeRequest(),
    contextFor("XX000"),
  );
  assertEquals(unavailable.status, 503, "infrastructure status");
  assertEquals(await unavailable.json(), {
    ok: false,
    code: "source_authorization_unavailable",
    retryable: true,
  }, "retryable receipt");

  const denied = await handleCreatorAiCaseImport(
    makeRequest(),
    contextFor("42501"),
  );
  assertEquals(denied.status, 403, "real scope denial status");
  assertEquals(await denied.json(), {
    ok: false,
    code: "ai_case_source_access_denied",
  }, "denial receipt");
});

Deno.test("normalized import uses only admin RPC and binds authenticated actor", async () => {
  const actorProfileId = "40000000-0000-4000-8000-000000000004";
  let userRpcCalls = 0;
  let adminRpcCalls = 0;
  let replayed = false;
  const capturedPayloads: Record<string, unknown>[] = [];
  const context = {
    userClaims: { id: actorProfileId },
    supabase: {
      rpc: () => {
        userRpcCalls += 1;
        throw new Error("normalized import must not use the user client");
      },
    },
    supabaseAdmin: {
      rpc: (
        name: string,
        args: { p_payload: Record<string, unknown> },
      ) => {
        adminRpcCalls += 1;
        assertEquals(
          name,
          "creator_import_ai_historical_case_batch",
          "normalized RPC",
        );
        capturedPayloads.push(args.p_payload);
        const cases = args.p_payload.cases as unknown[];
        return Promise.resolve({
          error: null,
          data: {
            ok: true,
            status: "completed",
            replayed,
            batch_persisted: true,
            batch: {
              case_count: cases.length,
              matched_case_count: cases.length,
              quarantined_case_count: 0,
              parsed_row_count: args.p_payload.parsed_row_count,
              parser_quarantined_row_count:
                args.p_payload.parser_quarantined_row_count,
              parser_quarantine_summary:
                args.p_payload.parser_quarantine_summary,
            },
            snapshot: { ok: true },
          },
        });
      },
    },
  } as unknown as Parameters<typeof importCases>[0];
  const normalizedCase = {
    external_case_id: "fixture:wb:sku-1:2026-07-29",
    product_category: "baa" as const,
    product_sku: "sku-1",
    marketplace_sku: "500000001",
    product_title: "Fixture product",
    brand: "Fixture Brand",
    platform: "wildberries",
    channel: "marketplace_funnel",
    period_start: "2026-05-01",
    period_end: "2026-07-29",
    outcome: "good" as const,
    outcome_dimension: "overall_performance",
    status_label: "Fixture reviewed status",
    metrics: { orders: 101 },
    confidence: 0.9,
    provenance: {
      sheet: "Fixture",
      row: 2,
      row_hash: "c".repeat(64),
    },
  };

  const request = {
    organizationId: "10000000-0000-4000-8000-000000000001",
    sourceId: "20000000-0000-4000-8000-000000000002",
    productCategory: "baa" as const,
    adapter: "auto" as const,
    commit: true,
    idempotencyKey: "30000000-0000-4000-8000-000000000003",
  };
  const source = {
    sourceId: "20000000-0000-4000-8000-000000000002",
    productCategory: "baa" as const,
    bucket: "contentengine-knowledge",
    objectKey: "fixture/source.xlsx",
    originalFilename: "fixture.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    sizeBytes: 100,
    clientSha256: "a".repeat(64),
  };
  const parsed = {
    adapter: "canonical_v1" as const,
    parserVersion: "fixture-parser-v1",
    cases: [normalizedCase],
    quarantine: [],
    warnings: {},
  };
  const result = await importCases(
    context,
    request,
    source,
    "a".repeat(64),
    parsed,
  );
  replayed = true;
  const replayResult = await importCases(
    context,
    request,
    source,
    "a".repeat(64),
    parsed,
  );

  assertEquals(userRpcCalls, 0, "user client cannot call normalized RPC");
  assertEquals(adminRpcCalls, 2, "admin client performs normalized RPC");
  assertEquals(capturedPayloads.length, 2, "payload captured");
  assertEquals(
    capturedPayloads[0].actor_profile_id,
    actorProfileId,
    "authenticated actor propagated",
  );
  assertEquals(result.importedCases, 1, "authoritative import receipt");
  assertEquals(result.acceptedBatches, 1, "fresh batch accepted");
  assertEquals(replayResult.importedCases, 0, "replay is not a new insert");
  assertEquals(replayResult.acceptedBatches, 0, "replay is not re-accepted");
});
