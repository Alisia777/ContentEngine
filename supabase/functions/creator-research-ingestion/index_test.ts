import searchFixture from "./fixtures/search-success.json" with {
  type: "json",
};
import videosFixture from "./fixtures/videos-success.json" with {
  type: "json",
};
import {
  buildYoutubeSearchUrl,
  buildYoutubeVideosUrl,
  readYoutubeSearchResponse,
  readYoutubeVideosResponse,
  youtubeFailureForHttp,
  youtubeRequestHash,
} from "../_shared/youtube-data-api-v3.ts";
import {
  executeYoutubeIngestion,
  readAuthorizedYoutubeIngestionClaim,
  readAutomaticYoutubeIngestionClaim,
  readYoutubeIngestionClaim,
  type YoutubeIngestionClaim,
  type YoutubeIngestionDependencies,
} from "./index.ts";

const API_KEY = "sanitized_test_key_1234567890_abcd";
const INGESTION_ID = "10000000-0000-4000-8000-000000000001";
const OBSERVED_AT = "2026-08-03T10:00:00.000Z";

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

function claim(
  mode: "manual_canary" | "category_refresh" = "category_refresh",
): YoutubeIngestionClaim {
  return {
    id: INGESTION_ID,
    mode,
    providerKey: "youtube_data_api_v3",
    adapterVersion: "youtube-data-api-v3-public-metadata-v1",
    queryText: "товары для ухода за волосами",
    regionCode: "RU",
    relevanceLanguage: "ru",
    publishedAfter: "2026-07-01T00:00:00.000Z",
    maxResults: mode === "manual_canary" ? 1 : 25,
    maxHttpRequests: 2,
    maxQuotaUnits: 2,
    requestHash: "a".repeat(64),
  };
}

function response(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function dependencies(
  fetcher: typeof fetch,
  options: { allowTransport?: boolean; failReceiptAt?: number } = {},
) {
  const begins: Array<Record<string, unknown>> = [];
  const receipts: Array<Record<string, unknown>> = [];
  const value: YoutubeIngestionDependencies = {
    apiKey: API_KEY,
    fetcher,
    now: () => new Date(OBSERVED_AT),
    beginTransport: (payload) => {
      begins.push(payload);
      const ordinal = Number(payload.request_ordinal);
      return Promise.resolve({
        transportId: `20000000-0000-4000-8000-00000000000${ordinal}`,
        externalCallAllowed: options.allowTransport !== false,
      });
    },
    recordTransport: (payload) => {
      receipts.push(payload);
      if (receipts.length === options.failReceiptAt) {
        return Promise.reject(
          new Error("sanitized receipt persistence failure"),
        );
      }
      return Promise.resolve();
    },
  };
  return { value, begins, receipts };
}

Deno.test("builders are official-host bounded and hash excludes the secret", async () => {
  const first = buildYoutubeSearchUrl(
    {
      queryText: "уход за волосами",
      maxResults: 25,
      regionCode: "ru",
      relevanceLanguage: "ru",
      publishedAfter: "2026-07-01T00:00:00Z",
    },
    API_KEY,
    new Date(OBSERVED_AT),
  );
  const second = buildYoutubeSearchUrl(
    {
      queryText: "уход за волосами",
      maxResults: 25,
      regionCode: "ru",
      relevanceLanguage: "ru",
      publishedAfter: "2026-07-01T00:00:00Z",
    },
    "sanitized_alternate_key_0987654321",
    new Date(OBSERVED_AT),
  );
  assertEquals(first.protocol, "https:", "HTTPS is required");
  assertEquals(first.hostname, "www.googleapis.com", "host is allowlisted");
  assertEquals(first.pathname, "/youtube/v3/search", "path is fixed");
  assertEquals(
    first.searchParams.get("maxResults"),
    "25",
    "result cap is fixed",
  );
  assertEquals(
    first.searchParams.get("safeSearch"),
    "strict",
    "safe search is strict",
  );
  assertEquals(
    await youtubeRequestHash(first),
    await youtubeRequestHash(second),
    "request hash must not contain or depend on the API key",
  );

  const videos = buildYoutubeVideosUrl(
    ["abcDEF12345", "zyxWVU98765"],
    API_KEY,
  );
  assertEquals(videos.pathname, "/youtube/v3/videos", "videos path is fixed");
  assertEquals(
    videos.searchParams.get("id"),
    "abcDEF12345,zyxWVU98765",
    "only exact IDs are requested",
  );
  assert(
    !String(videos.searchParams.get("fields")).includes("description") &&
      !String(videos.searchParams.get("fields")).includes("tags") &&
      !String(videos.searchParams.get("fields")).includes("madeForKids"),
    "unused or high-risk raw fields must not be requested",
  );
});

Deno.test("sanitized recorded fixtures normalize only bounded public metadata", async () => {
  const search = await readYoutubeSearchResponse(searchFixture);
  assertEquals(
    search.videoIds,
    ["abcDEF12345", "zyxWVU98765"],
    "search IDs preserve provider order",
  );
  assert(search.nextPageAvailable, "pagination is observed but never followed");
  const videos = await readYoutubeVideosResponse(
    videosFixture,
    search.videoIds,
    OBSERVED_AT,
  );
  assertEquals(videos.itemCount, 2, "both fixture videos normalize");
  assertEquals(videos.missingVideoCount, 0, "no expected video is missing");
  assertEquals(
    Object.keys(videos.observations[0]),
    [
      "search_position",
      "video_id",
      "channel_id",
      "title",
      "channel_title",
      "youtube_category_id",
      "published_at",
      "duration_iso8601",
      "privacy_status",
      "embeddable",
      "retention_expires_at",
      "view_count",
      "like_count",
      "comment_count",
      "observed_at",
    ],
    "completion observations expose only the SQL contract",
  );
  assertEquals(
    videos.observations.map((item) => item.search_position),
    [1, 2],
    "search positions preserve the one-based search order",
  );
  assertEquals(
    videos.observations[0].retention_expires_at,
    "2026-09-01T10:00:00.000Z",
    "raw API data expires after 29 days with a purge buffer",
  );
  assertEquals(
    videos.observations[1].like_count,
    null,
    "provider-omitted counters remain null",
  );
  assertEquals(
    videos.observations[0].view_count,
    "12500",
    "large counters remain exact strings",
  );
  const serialized = JSON.stringify(videos.observations);
  for (
    const forbidden of ["description", "caption", "transcript", "tags"] as const
  ) {
    assert(
      !serialized.includes(forbidden),
      `${forbidden} must not be persisted`,
    );
  }
});

Deno.test("refresh performs exactly two permitted GETs without pagination", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetcher = ((
    input: string | URL | Request,
    init?: RequestInit,
  ): Promise<Response> => {
    calls.push({ url: String(input), init });
    return Promise.resolve(
      calls.length === 1 ? response(searchFixture) : response(videosFixture),
    );
  }) as typeof fetch;
  const harness = dependencies(fetcher);
  const result = await executeYoutubeIngestion(claim(), harness.value);
  assertEquals(
    result.externalRequestCount,
    2,
    "two external requests are counted",
  );
  assertEquals(calls.length, 2, "only search and details are called");
  assertEquals(harness.begins.length, 2, "each fetch has a prior permit");
  assertEquals(
    harness.begins.map((item) => item.request_kind),
    ["search.list", "videos.list"],
    "transport order is immutable",
  );
  assert(
    calls.every((call) =>
      call.init?.method === "GET" && call.init.redirect === "manual" &&
      call.init.cache === "no-store"
    ),
    "every provider call is an uncached GET with redirects disabled",
  );
  assertEquals(
    result.completion.status,
    "completed",
    "valid fixtures complete the run",
  );
  assertEquals(
    (result.completion.observations as unknown[]).length,
    2,
    "normalized observations are persisted",
  );
  assertEquals(
    (result.completion.videos as Record<string, unknown>).item_count,
    2,
    "completion binds the videos receipt count",
  );
  assert(
    typeof (result.completion.videos as Record<string, unknown>)
      .response_hash === "string",
    "completion binds the videos response hash",
  );
  assertEquals(
    harness.receipts.map((item) => item.status),
    ["ready", "ready"],
    "both actual responses receive receipts",
  );
});

Deno.test("manual canary validates one video across exactly two endpoints", async () => {
  const calls: string[] = [];
  const canaryFixture = structuredClone(searchFixture);
  canaryFixture.items = canaryFixture.items.slice(0, 1);
  canaryFixture.pageInfo.resultsPerPage = 1;
  canaryFixture.pageInfo.totalResults = 1;
  const canaryVideosFixture = structuredClone(videosFixture);
  canaryVideosFixture.items = canaryVideosFixture.items.slice(0, 1);
  canaryVideosFixture.pageInfo.resultsPerPage = 1;
  canaryVideosFixture.pageInfo.totalResults = 1;
  const fetcher = ((input: string | URL | Request) => {
    const url = new URL(String(input));
    calls.push(url.pathname);
    return Promise.resolve(
      calls.length === 1
        ? response(canaryFixture)
        : response(canaryVideosFixture),
    );
  }) as typeof fetch;
  const harness = dependencies(fetcher);
  const result = await executeYoutubeIngestion(
    claim("manual_canary"),
    harness.value,
  );
  assertEquals(
    calls,
    ["/youtube/v3/search", "/youtube/v3/videos"],
    "canary exercises search.list and videos.list once each",
  );
  assertEquals(result.externalRequestCount, 2, "canary uses exactly two calls");
  assertEquals(harness.begins.length, 2, "canary consumes two permits");
  assertEquals(
    harness.receipts.map((item) => item.status),
    ["ready", "ready"],
    "both canary endpoints have durable ready receipts",
  );
  assertEquals(
    (result.completion.observations as unknown[]).length,
    0,
    "canary never contaminates category observations",
  );
  assert(
    typeof result.completion.canary === "object",
    "canary completion contains a bounded receipt",
  );
  assertEquals(
    (result.completion.canary as Record<string, unknown>).request_kind,
    "videos.list",
    "the canary receipt proves the details endpoint completed",
  );
  assertEquals(
    (result.completion.videos as Record<string, unknown>).item_count,
    1,
    "canary completion binds exactly one videos.list item",
  );
});

Deno.test("receipt persistence failure stops before the next provider call", async () => {
  const calls: string[] = [];
  const fetcher = ((input: string | URL | Request) => {
    calls.push(new URL(String(input)).pathname);
    return Promise.resolve(response(searchFixture));
  }) as typeof fetch;
  const harness = dependencies(fetcher, { failReceiptAt: 1 });
  const result = await executeYoutubeIngestion(claim(), harness.value);
  assertEquals(
    calls,
    ["/youtube/v3/search"],
    "videos.list is forbidden after an uncertain search receipt",
  );
  assertEquals(harness.begins.length, 1, "no second permit is requested");
  assertEquals(
    result.externalRequestCount,
    1,
    "the already-issued provider call remains counted",
  );
  assertEquals(
    result.completion.error_code,
    "provider_outcome_unknown",
    "receipt uncertainty is explicit and terminal",
  );
});

Deno.test("network ambiguity is receipted once and never retried", async () => {
  let calls = 0;
  const fetcher = (() => {
    calls += 1;
    return Promise.reject(new TypeError("sanitized network failure"));
  }) as typeof fetch;
  const harness = dependencies(fetcher);
  const result = await executeYoutubeIngestion(claim(), harness.value);
  assertEquals(calls, 1, "ambiguous GET is not retried");
  assertEquals(
    result.externalRequestCount,
    1,
    "ambiguous call consumes its permit",
  );
  assertEquals(
    result.completion.error_code,
    "provider_outcome_unknown",
    "network failure stays unknown",
  );
  assertEquals(
    harness.receipts.map((item) => [item.status, item.failure_code]),
    [["unknown", "provider_outcome_unknown"]],
    "an explicit ambiguity receipt is attempted",
  );
});

Deno.test("oversized provider bodies fail closed without retry", async () => {
  let calls = 0;
  const fetcher = (() => {
    calls += 1;
    return Promise.resolve(
      new Response(JSON.stringify({ padding: "x".repeat(524_288) }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
  }) as typeof fetch;
  const harness = dependencies(fetcher);
  const result = await executeYoutubeIngestion(claim(), harness.value);
  assertEquals(calls, 1, "an oversized response is never retried");
  assertEquals(
    result.completion.error_code,
    "provider_response_invalid",
    "the bounded reader fails closed",
  );
  assertEquals(
    harness.receipts.map((item) => [item.status, item.failure_code]),
    [["degraded", "provider_response_invalid"]],
    "the rejected body is receipted without retaining it",
  );
});

Deno.test("transport refusal causes zero fetches and no fallback", async () => {
  let calls = 0;
  const fetcher = (() => {
    calls += 1;
    return Promise.resolve(response(searchFixture));
  }) as typeof fetch;
  const harness = dependencies(fetcher, { allowTransport: false });
  const result = await executeYoutubeIngestion(claim(), harness.value);
  assertEquals(calls, 0, "no HTTP call occurs without an atomic permit");
  assertEquals(result.externalRequestCount, 0, "no external call is claimed");
  assertEquals(
    result.completion.error_code,
    "provider_configuration_error",
    "permit refusal fails closed",
  );
});

Deno.test("manual redirect and quota errors fail once without fallback", async () => {
  const scenarios = [
    {
      status: 302,
      payload: undefined,
      code: "provider_request_rejected",
    },
    {
      status: 403,
      payload: {
        error: {
          code: 403,
          message: "quota exhausted",
          errors: [{ reason: "quotaExceeded" }],
        },
      },
      code: "provider_quota_exhausted",
    },
  ] as const;
  for (const scenario of scenarios) {
    let calls = 0;
    let redirect: RequestRedirect | undefined;
    const fetcher = ((
      _input: string | URL | Request,
      init?: RequestInit,
    ): Promise<Response> => {
      calls += 1;
      redirect = init?.redirect;
      return Promise.resolve(response(scenario.payload, scenario.status));
    }) as typeof fetch;
    const harness = dependencies(fetcher);
    const result = await executeYoutubeIngestion(claim(), harness.value);
    assertEquals(calls, 1, `${scenario.status} is never retried`);
    assertEquals(redirect, "manual", "redirect following is disabled");
    assertEquals(result.completion.error_code, scenario.code, "error is exact");
  }
});

Deno.test("strict validators reject extra raw fields and malformed claims", async () => {
  const unsafe = structuredClone(searchFixture) as Record<string, unknown>;
  const items = unsafe.items as Array<Record<string, unknown>>;
  (items[0].snippet as Record<string, unknown>).description =
    "raw field must fail";
  let rejected = false;
  try {
    await readYoutubeSearchResponse(unsafe);
  } catch {
    rejected = true;
  }
  assert(rejected, "unexpected provider fields fail closed");
  let overCapRejected = false;
  try {
    await readYoutubeSearchResponse(searchFixture, 1);
  } catch {
    overCapRejected = true;
  }
  assert(
    overCapRejected,
    "a provider response cannot exceed the requested result cap",
  );

  const valid = readYoutubeIngestionClaim({
    ok: true,
    claimed: true,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "уход за волосами",
      region_code: "RU",
      relevance_language: "ru",
      published_after: "2026-07-01T00:00:00.000Z",
      max_results: 25,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "b".repeat(64),
    },
  }, INGESTION_ID);
  assert(valid?.claimed === true, "exact claim contract is accepted");
  const authorizedCanary = readAuthorizedYoutubeIngestionClaim({
    ok: true,
    invoke_authorized: true,
    claimed: true,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "manual_canary",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded canary query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 1,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "c".repeat(64),
    },
  }, INGESTION_ID);
  assert(
    authorizedCanary?.claimed === true,
    "dedicated creator authorization can claim a two-endpoint canary",
  );
  const automaticRefresh = readAutomaticYoutubeIngestionClaim({
    ok: true,
    automatic_dispatch_authorized: true,
    claimed: false,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded automatic refresh query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 25,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "d".repeat(64),
      lease_expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
    },
  }, INGESTION_ID);
  assert(
    automaticRefresh?.claimed === false &&
      automaticRefresh.status === "processing",
    "an exact system marker can authorize an automatic category refresh",
  );
  const expiredAutomaticRefresh = readAutomaticYoutubeIngestionClaim({
    ok: true,
    automatic_dispatch_authorized: true,
    claimed: false,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded automatic refresh query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 25,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "d".repeat(64),
      lease_expires_at: new Date(Date.now() - 1_000).toISOString(),
    },
  }, INGESTION_ID);
  assertEquals(
    expiredAutomaticRefresh,
    null,
    "an expired automatic lease cannot authorize provider transport",
  );
  const automaticCanary = readAutomaticYoutubeIngestionClaim({
    ok: true,
    automatic_dispatch_authorized: true,
    claimed: false,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "manual_canary",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded canary query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 1,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "e".repeat(64),
    },
  }, INGESTION_ID);
  assertEquals(
    automaticCanary,
    null,
    "the internal route rejects a manual canary even with a forged marker",
  );
  const unmarkedAutomaticRefresh = readAutomaticYoutubeIngestionClaim({
    ok: true,
    claimed: true,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded automatic refresh query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 25,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "f".repeat(64),
    },
  }, INGESTION_ID);
  assertEquals(
    unmarkedAutomaticRefresh,
    null,
    "an unmarked system claim cannot authorize automatic provider work",
  );
  const unauthorizedCanary = readAuthorizedYoutubeIngestionClaim({
    ok: true,
    claimed: true,
    ingestion: {
      id: INGESTION_ID,
      status: "processing",
      mode: "manual_canary",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "bounded canary query",
      region_code: null,
      relevance_language: null,
      published_after: null,
      max_results: 1,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "c".repeat(64),
    },
  }, INGESTION_ID);
  assertEquals(
    unauthorizedCanary,
    null,
    "a claim without explicit invoke authorization fails closed",
  );
  const concurrentTerminal = readYoutubeIngestionClaim({
    ok: true,
    claimed: false,
    ingestion: {
      id: INGESTION_ID,
      status: "completed",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "СѓС…РѕРґ Р·Р° РІРѕР»РѕСЃР°РјРё",
      region_code: "RU",
      relevance_language: "ru",
      published_after: "2026-07-01T00:00:00.000Z",
      max_results: 25,
      max_http_requests: 2,
      max_quota_units: 2,
      request_hash: "b".repeat(64),
    },
  }, INGESTION_ID);
  assert(
    concurrentTerminal?.claimed === false,
    "a concurrent terminal claim is routed to the user status read",
  );
  const invalid = readYoutubeIngestionClaim({
    ok: true,
    claimed: true,
    ingestion: {
      ...valid?.ingestion,
      id: INGESTION_ID,
      status: "processing",
      mode: "category_refresh",
      provider_key: "youtube_data_api_v3",
      adapter_version: "youtube-data-api-v3-public-metadata-v1",
      query_text: "уход за волосами",
      region_code: "RU",
      relevance_language: "ru",
      published_after: null,
      max_results: 25,
      max_http_requests: 3,
      max_quota_units: 2,
      request_hash: "b".repeat(64),
    },
  }, INGESTION_ID);
  assertEquals(invalid, null, "a claim cannot authorize a third HTTP request");
});

Deno.test("HTTP classifier distinguishes quota from authentication", () => {
  assertEquals(
    youtubeFailureForHttp(403, {
      error: { errors: [{ reason: "quotaExceeded" }] },
    }),
    "provider_quota_exhausted",
    "quota is explicit",
  );
  assertEquals(
    youtubeFailureForHttp(403, { error: { reason: "keyInvalid" } }),
    "provider_authentication_failed",
    "invalid key is authentication failure",
  );
});
