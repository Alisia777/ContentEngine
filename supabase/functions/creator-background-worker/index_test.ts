import { readAutomaticYoutubeCollectionSummary, readPayload } from "./index.ts";

const INGESTION_ID = "10000000-0000-4000-8000-000000000001";
const ORGANIZATION_ID = "20000000-0000-4000-8000-000000000001";
const REQUESTED_BY = "30000000-0000-4000-8000-000000000001";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertEquals<T>(actual: T, expected: T, message: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${message}: ${JSON.stringify(actual)} !== ${JSON.stringify(expected)}`,
    );
  }
}

function automaticBatch(): Record<string, unknown> {
  return {
    ok: true,
    selected: 1,
    claimed: 1,
    expired: 0,
    items: [{
      ingestion_id: INGESTION_ID,
      organization_id: ORGANIZATION_ID,
      requested_by: REQUESTED_BY,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      max_http_requests: 2,
      max_quota_units: 2,
    }],
    external_call_started: false,
    automatic_retry_started: false,
  };
}

Deno.test("worker payload keeps legacy explicit calls provider-free", () => {
  assertEquals(
    readPayload(null),
    {
      generation_limit: 4,
      research_limit: 1,
      review_limit: 1,
      youtube_limit: 1,
    },
    "the native default includes one bounded YouTube refresh",
  );
  assertEquals(
    readPayload({
      generation_limit: 0,
      research_limit: 0,
      review_limit: 0,
    }),
    {
      generation_limit: 0,
      research_limit: 0,
      review_limit: 0,
      youtube_limit: 0,
    },
    "an explicit legacy health payload does not opt into a provider call",
  );
  assert(
    readPayload({
      generation_limit: 4,
      research_limit: 1,
      review_limit: 1,
      youtube_limit: 3,
    }) === null,
    "all provider dispatches share the global cap",
  );
});

Deno.test("automatic YouTube batch parser accepts only preclaimed refreshes", () => {
  const parsed = readAutomaticYoutubeCollectionSummary(automaticBatch(), 1);
  assertEquals(
    parsed,
    {
      ok: true,
      selected: 1,
      claimed: 1,
      expired: 0,
      ingestions: [{
        ingestionId: INGESTION_ID,
        organizationId: ORGANIZATION_ID,
        requestedBy: REQUESTED_BY,
      }],
    },
    "the exact bounded SQL envelope is normalized",
  );

  const manual = automaticBatch();
  (manual.items as Array<Record<string, unknown>>)[0].mode = "manual_canary";
  assert(
    readAutomaticYoutubeCollectionSummary(manual, 1) === null,
    "manual canaries are never automatic worker targets",
  );

  const unclaimed = automaticBatch();
  unclaimed.claimed = 0;
  assert(
    readAutomaticYoutubeCollectionSummary(unclaimed, 1) === null,
    "an item without an atomic database claim is rejected",
  );

  const expanded = automaticBatch();
  expanded.debug = "must not cross the worker boundary";
  assert(
    readAutomaticYoutubeCollectionSummary(expanded, 1) === null,
    "unexpected scheduler output fails closed",
  );
});
