import {
  processDueYoutubeObservationAnalysis,
  readAutomaticYoutubeCollectionSummary,
  readPayload,
  readYoutubeObservationAnalysisSummary,
  youtubeObservationAnalysisHasFailure,
} from "./index.ts";

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

function analysisBatch({
  completed = 1,
  failed = 0,
}: {
  completed?: number;
  failed?: number;
} = {}): Record<string, unknown> {
  const items = [
    ...Array.from({ length: completed }, (_, index) => ({
      job_id: `40000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      ingestion_id: `60000000-0000-4000-8000-${
        String(index + 1).padStart(12, "0")
      }`,
      status: "completed",
      parsed_count: 2,
    })),
    ...Array.from({ length: failed }, (_, index) => ({
      job_id: `50000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      ingestion_id: `70000000-0000-4000-8000-${
        String(index + 1).padStart(12, "0")
      }`,
      status: "failed",
      error_code: "analysis_input_changed",
    })),
  ];
  return {
    ok: true,
    selected: completed + failed,
    completed,
    failed,
    items,
    external_call_started: false,
    provider_attempt_count: 0,
    cost_minor: 0,
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

Deno.test("local YouTube analysis parser accepts only the exact zero-provider envelope", () => {
  const parsed = readYoutubeObservationAnalysisSummary(analysisBatch(), 6);
  assertEquals(
    parsed,
    analysisBatch(),
    "the exact bounded local analysis result is preserved",
  );
  assert(
    parsed !== null && !youtubeObservationAnalysisHasFailure(parsed),
    "a fully completed local batch is healthy",
  );

  const partialFailure = readYoutubeObservationAnalysisSummary(
    analysisBatch({ completed: 1, failed: 1 }),
    6,
  );
  assert(
    partialFailure !== null &&
      youtubeObservationAnalysisHasFailure(partialFailure),
    "a terminal item failure remains visible to the worker batch",
  );

  const spent = analysisBatch();
  spent.provider_attempt_count = 1;
  assert(
    readYoutubeObservationAnalysisSummary(spent, 6) === null,
    "a result claiming a provider attempt fails closed",
  );

  const retrying = analysisBatch();
  retrying.automatic_retry_started = true;
  assert(
    readYoutubeObservationAnalysisSummary(retrying, 6) === null,
    "a result claiming an automatic retry fails closed",
  );

  const charged = analysisBatch();
  charged.cost_minor = 1;
  assert(
    readYoutubeObservationAnalysisSummary(charged, 6) === null,
    "a result claiming provider cost fails closed",
  );

  const inconsistent = analysisBatch();
  inconsistent.selected = 2;
  assert(
    readYoutubeObservationAnalysisSummary(inconsistent, 6) === null,
    "counts and visible items must describe the same bounded work",
  );

  const contradictory = analysisBatch();
  (contradictory.items as Array<Record<string, unknown>>)[0].status = "failed";
  assert(
    readYoutubeObservationAnalysisSummary(contradictory, 6) === null,
    "per-item status must agree with aggregate completed and failed counts",
  );

  const malformed = analysisBatch();
  delete (malformed.items as Array<Record<string, unknown>>)[0].ingestion_id;
  assert(
    readYoutubeObservationAnalysisSummary(malformed, 6) === null,
    "every item must preserve its exact job and ingestion identity",
  );

  const duplicate = analysisBatch({ completed: 2 });
  (duplicate.items as Array<Record<string, unknown>>)[1].job_id =
    (duplicate.items as Array<Record<string, unknown>>)[0].job_id;
  assert(
    readYoutubeObservationAnalysisSummary(duplicate, 6) === null,
    "one processor response cannot report the same job twice",
  );

  const expanded = analysisBatch();
  expanded.debug = "must not cross the worker boundary";
  assert(
    readYoutubeObservationAnalysisSummary(expanded, 6) === null,
    "unexpected processor output fails closed",
  );
});

Deno.test("local YouTube analysis invokes one RPC and creates no HTTP dispatch", async () => {
  const calls: Array<Record<string, unknown>> = [];
  const result = await processDueYoutubeObservationAnalysis({
    rpc: (name, args) => {
      calls.push({ name, args });
      return Promise.resolve({
        data: analysisBatch({ completed: 1, failed: 1 }),
        error: null,
      });
    },
  }, 6);
  assertEquals(
    calls,
    [{
      name: "system_process_due_research_youtube_observation_analysis",
      args: { p_payload: { limit: 6 } },
    }],
    "the local processor performs exactly one bounded database call",
  );
  assertEquals(
    {
      ok: result.ok,
      selected: result.selected,
      completed: result.completed,
      failed: result.failed,
      external: result.external_call_started,
      providerAttempts: result.provider_attempt_count,
      costMinor: result.cost_minor,
      automaticRetry: result.automatic_retry_started,
      batchFailed: youtubeObservationAnalysisHasFailure(result),
    },
    {
      ok: true,
      selected: 2,
      completed: 1,
      failed: 1,
      external: false,
      providerAttempts: 0,
      costMinor: 0,
      automaticRetry: false,
      batchFailed: true,
    },
    "item failures are visible without provider work or ingestion retry",
  );
});

Deno.test("local YouTube analysis RPC failures are terminal for the tick", async () => {
  let calls = 0;
  const result = await processDueYoutubeObservationAnalysis({
    rpc: () => {
      calls += 1;
      return Promise.reject(new Error("sanitized local RPC failure"));
    },
  }, 6);
  assertEquals(calls, 1, "the worker never retries the local processor RPC");
  assertEquals(
    result,
    {
      ok: false,
      selected: 0,
      completed: 0,
      failed: 0,
      items: [],
      external_call_started: false,
      provider_attempt_count: 0,
      cost_minor: 0,
      automatic_retry_started: false,
      code: "youtube_observation_analysis_failed",
    },
    "a lost local result becomes an explicit batch failure without dispatch",
  );
  assert(
    youtubeObservationAnalysisHasFailure(result),
    "an unavailable local processor makes the batch incomplete",
  );
});
