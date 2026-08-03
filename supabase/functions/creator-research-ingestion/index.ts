import { type SupabaseContext, withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  isInternalWorkerAuthorized,
  isInternalWorkerRequest,
} from "../_shared/internal-worker-auth.ts";
import {
  buildYoutubeSearchUrl,
  buildYoutubeVideosUrl,
  jsonHash,
  readBoundedJsonResponse,
  readYoutubeSearchResponse,
  readYoutubeVideosResponse,
  YOUTUBE_ADAPTER_VERSION,
  YOUTUBE_INGESTION_VERSION,
  YOUTUBE_PROVIDER_KEY,
  type YoutubeFailureCode,
  youtubeFailureForHttp,
  youtubeRequestHash,
} from "../_shared/youtube-data-api-v3.ts";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const MAX_BODY_BYTES = 4_096;
const YOUTUBE_TIMEOUT_MS = 15_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const INGESTION_STATUSES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
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
      creator_claim_research_youtube_ingestion: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_read_automatic_research_youtube_ingestion: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_research_youtube_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_begin_research_youtube_transport: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_begin_automatic_research_youtube_transport: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_research_youtube_transport: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_complete_research_youtube_ingestion: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

type IngestRequest = {
  action: "ingest";
  ingestionId: string;
};

export type YoutubeIngestionClaim = {
  id: string;
  mode: "manual_canary" | "category_refresh";
  providerKey: typeof YOUTUBE_PROVIDER_KEY;
  adapterVersion: typeof YOUTUBE_ADAPTER_VERSION;
  queryText: string;
  regionCode: string | null;
  relevanceLanguage: string | null;
  publishedAfter: string | null;
  maxResults: number;
  maxHttpRequests: 1 | 2;
  maxQuotaUnits: 1 | 2;
  requestHash: string;
};

type BeginTransportPayload = {
  ingestion_id: string;
  request_ordinal: 1 | 2;
  request_kind: "search.list" | "videos.list";
  quota_bucket: "search_queries" | "default";
  quota_units: 1;
  request_hash: string;
};

type RecordTransportPayload = {
  transport_id: string;
  status: "ready" | "degraded" | "blocked" | "unknown";
  checked_at: string;
  failure_code?: string;
  response_hash?: string;
  item_count?: number;
};

type TransportPermit = {
  transportId: string;
  externalCallAllowed: boolean;
};

export type YoutubeIngestionDependencies = {
  apiKey: string;
  fetcher: typeof fetch;
  now: () => Date;
  beginTransport: (
    payload: BeginTransportPayload,
  ) => Promise<TransportPermit | null>;
  recordTransport: (payload: RecordTransportPayload) => Promise<void>;
};

export type YoutubeIngestionExecution = {
  completion: Record<string, Json>;
  externalRequestCount: number;
};

type ProviderFetchResult =
  | {
    ok: true;
    value: unknown;
    responseHash: string;
    transportId: string;
  }
  | {
    ok: false;
    code: string;
    transportId?: string;
  };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
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
    !hasControlCharacter(value);
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
      if (total > MAX_BODY_BYTES) {
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

function readRequestPayload(value: unknown): IngestRequest | null {
  if (
    !isRecord(value) || Object.keys(value).length !== 2 ||
    value.action !== "ingest" || !isUuid(value.ingestion_id)
  ) return null;
  return { action: "ingest", ingestionId: value.ingestion_id };
}

function readStatusEnvelope(
  value: unknown,
  ingestionId: string,
): { data: Json; status: string } | null {
  if (
    !isRecord(value) || value.ok !== true ||
    value.version !== YOUTUBE_INGESTION_VERSION ||
    !isRecord(value.ingestion) || value.ingestion.id !== ingestionId ||
    typeof value.ingestion.status !== "string" ||
    !INGESTION_STATUSES.has(value.ingestion.status)
  ) return null;
  return { data: value as Json, status: value.ingestion.status };
}

export function readYoutubeIngestionClaim(
  value: unknown,
  expectedId: string,
): {
  claimed: boolean;
  status: "processing" | "completed" | "failed";
  ingestion: YoutubeIngestionClaim;
} | null {
  if (
    !isRecord(value) || value.ok !== true ||
    typeof value.claimed !== "boolean" || !isRecord(value.ingestion) ||
    value.ingestion.id !== expectedId ||
    (value.claimed && value.ingestion.status !== "processing") ||
    (!value.claimed &&
      !["processing", "completed", "failed"].includes(
        String(value.ingestion.status),
      ))
  ) return null;
  const source = value.ingestion;
  const mode = source.mode;
  const maxResults = Number(source.max_results);
  const maxHttpRequests = Number(source.max_http_requests);
  const maxQuotaUnits = Number(source.max_quota_units);
  const nullableText = (
    item: unknown,
    maximum: number,
  ): string | null | false =>
    item === null ? null : boundedText(item, 1, maximum) ? item : false;
  const regionCode = nullableText(source.region_code, 2);
  const relevanceLanguage = nullableText(source.relevance_language, 32);
  const publishedAfter = nullableText(source.published_after, 40);
  if (
    (mode !== "manual_canary" && mode !== "category_refresh") ||
    source.provider_key !== YOUTUBE_PROVIDER_KEY ||
    source.adapter_version !== YOUTUBE_ADAPTER_VERSION ||
    !boundedText(source.query_text, 2, 200) ||
    regionCode === false || relevanceLanguage === false ||
    publishedAfter === false || !Number.isSafeInteger(maxResults) ||
    !Number.isSafeInteger(maxHttpRequests) ||
    !Number.isSafeInteger(maxQuotaUnits) ||
    typeof source.request_hash !== "string" ||
    !SHA256_PATTERN.test(source.request_hash) ||
    (mode === "manual_canary" &&
      (maxResults !== 1 || maxHttpRequests !== 2 || maxQuotaUnits !== 2)) ||
    (mode === "category_refresh" &&
      (maxResults < 1 || maxResults > 25 || maxHttpRequests !== 2 ||
        maxQuotaUnits !== 2))
  ) return null;
  return {
    claimed: value.claimed,
    status: source.status as "processing" | "completed" | "failed",
    ingestion: {
      id: expectedId,
      mode,
      providerKey: YOUTUBE_PROVIDER_KEY,
      adapterVersion: YOUTUBE_ADAPTER_VERSION,
      queryText: source.query_text,
      regionCode,
      relevanceLanguage,
      publishedAfter,
      maxResults,
      maxHttpRequests: maxHttpRequests as 1 | 2,
      maxQuotaUnits: maxQuotaUnits as 1 | 2,
      requestHash: source.request_hash,
    },
  };
}

export function readAuthorizedYoutubeIngestionClaim(
  value: unknown,
  expectedId: string,
): {
  claimed: boolean;
  status: "processing" | "completed" | "failed";
  ingestion: YoutubeIngestionClaim;
} | null {
  if (!isRecord(value) || value.invoke_authorized !== true) return null;
  return readYoutubeIngestionClaim(value, expectedId);
}

export function readAutomaticYoutubeIngestionClaim(
  value: unknown,
  expectedId: string,
): {
  claimed: boolean;
  status: "processing" | "completed" | "failed";
  ingestion: YoutubeIngestionClaim;
} | null {
  if (
    !isRecord(value) || value.automatic_dispatch_authorized !== true ||
    value.claimed !== false
  ) return null;
  const claim = readYoutubeIngestionClaim(value, expectedId);
  if (
    claim?.ingestion.mode !== "category_refresh" ||
    claim.status !== "processing"
  ) return null;
  const ingestion = isRecord(value.ingestion) ? value.ingestion : null;
  const leaseExpiresAt = typeof ingestion?.lease_expires_at === "string"
    ? Date.parse(ingestion.lease_expires_at)
    : Number.NaN;
  const now = Date.now();
  if (
    !Number.isFinite(leaseExpiresAt) || leaseExpiresAt <= now
  ) return null;
  return claim;
}

function completionFailure(
  claim: YoutubeIngestionClaim,
  observedAt: string,
  code: string,
): Record<string, Json> {
  const messages: Record<string, string> = {
    provider_configuration_error:
      "Официальный YouTube Data API временно не настроен.",
    provider_authentication_failed:
      "YouTube Data API отклонил серверный ключ приложения.",
    provider_quota_exhausted: "Доступная квота YouTube Data API исчерпана.",
    provider_rate_limited:
      "YouTube Data API временно ограничил частоту запросов.",
    provider_request_rejected: "YouTube Data API отклонил разрешённый запрос.",
    provider_response_invalid:
      "YouTube Data API вернул ответ с неподтверждённой структурой.",
    provider_outcome_unknown:
      "Сетевой исход запроса к YouTube неизвестен; автоматического повтора нет.",
    provider_unavailable: "YouTube Data API временно недоступен.",
  };
  return {
    version: YOUTUBE_INGESTION_VERSION,
    ingestion_id: claim.id,
    status: "failed",
    error_code: code,
    error_message: messages[code] ?? messages.provider_response_invalid,
    observed_at: observedAt,
  };
}

function transportStatusForFailure(
  code: YoutubeFailureCode | "provider_response_invalid",
): "degraded" | "blocked" {
  return [
      "provider_authentication_failed",
      "provider_quota_exhausted",
      "provider_request_rejected",
    ].includes(code)
    ? "blocked"
    : "degraded";
}

async function fetchWithTimeout(
  fetcher: typeof fetch,
  url: URL,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), YOUTUBE_TIMEOUT_MS);
  try {
    return await fetcher(url, {
      method: "GET",
      cache: "no-store",
      redirect: "manual",
      signal: controller.signal,
      headers: { accept: "application/json" },
      referrerPolicy: "no-referrer",
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function safeRecordTransport(
  dependencies: YoutubeIngestionDependencies,
  payload: RecordTransportPayload,
): Promise<boolean> {
  try {
    await dependencies.recordTransport(payload);
    return true;
  } catch {
    return false;
  }
}

async function performProviderFetch(
  claim: YoutubeIngestionClaim,
  dependencies: YoutubeIngestionDependencies,
  url: URL,
  ordinal: 1 | 2,
  requestKind: "search.list" | "videos.list",
  quotaBucket: "search_queries" | "default",
  checkedAt: string,
): Promise<ProviderFetchResult> {
  const requestHash = await youtubeRequestHash(url);
  let permit: TransportPermit | null = null;
  try {
    permit = await dependencies.beginTransport({
      ingestion_id: claim.id,
      request_ordinal: ordinal,
      request_kind: requestKind,
      quota_bucket: quotaBucket,
      quota_units: 1,
      request_hash: requestHash,
    });
  } catch {
    permit = null;
  }
  if (!permit?.externalCallAllowed || !isUuid(permit.transportId)) {
    return { ok: false, code: "provider_configuration_error" };
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(dependencies.fetcher, url);
  } catch {
    await safeRecordTransport(dependencies, {
      transport_id: permit.transportId,
      status: "unknown",
      checked_at: checkedAt,
      failure_code: "provider_outcome_unknown",
    });
    return {
      ok: false,
      code: "provider_outcome_unknown",
      transportId: permit.transportId,
    };
  }

  let responseValue: unknown;
  try {
    responseValue = await readBoundedJsonResponse(response);
  } catch {
    if (!response.ok) {
      const failureCode = youtubeFailureForHttp(response.status);
      const recorded = await safeRecordTransport(dependencies, {
        transport_id: permit.transportId,
        status: transportStatusForFailure(failureCode),
        checked_at: checkedAt,
        failure_code: failureCode,
      });
      return {
        ok: false,
        code: recorded ? failureCode : "provider_outcome_unknown",
        transportId: permit.transportId,
      };
    }
    const recorded = await safeRecordTransport(dependencies, {
      transport_id: permit.transportId,
      status: "degraded",
      checked_at: checkedAt,
      failure_code: "provider_response_invalid",
    });
    return {
      ok: false,
      code: recorded ? "provider_response_invalid" : "provider_outcome_unknown",
      transportId: permit.transportId,
    };
  }
  const responseHash = await jsonHash(responseValue);
  if (!response.ok) {
    const failureCode = youtubeFailureForHttp(response.status, responseValue);
    const recorded = await safeRecordTransport(dependencies, {
      transport_id: permit.transportId,
      status: transportStatusForFailure(failureCode),
      checked_at: checkedAt,
      failure_code: failureCode,
      response_hash: responseHash,
    });
    return {
      ok: false,
      code: recorded ? failureCode : "provider_outcome_unknown",
      transportId: permit.transportId,
    };
  }
  return {
    ok: true,
    value: responseValue,
    responseHash,
    transportId: permit.transportId,
  };
}

export async function executeYoutubeIngestion(
  claim: YoutubeIngestionClaim,
  dependencies: YoutubeIngestionDependencies,
): Promise<YoutubeIngestionExecution> {
  const observedAt = dependencies.now().toISOString();
  let externalRequestCount = 0;
  let searchUrl: URL;
  try {
    searchUrl = buildYoutubeSearchUrl(
      {
        queryText: claim.queryText,
        maxResults: claim.maxResults,
        regionCode: claim.regionCode,
        relevanceLanguage: claim.relevanceLanguage,
        publishedAfter: claim.publishedAfter,
        order: claim.mode === "manual_canary" ? "relevance" : "date",
      },
      dependencies.apiKey,
      new Date(observedAt),
    );
  } catch {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_configuration_error",
      ),
      externalRequestCount,
    };
  }

  const search = await performProviderFetch(
    claim,
    dependencies,
    searchUrl,
    1,
    "search.list",
    "search_queries",
    observedAt,
  );
  if (search.transportId) externalRequestCount += 1;
  if (!search.ok) {
    return {
      completion: completionFailure(claim, observedAt, search.code),
      externalRequestCount,
    };
  }

  let searchResult;
  try {
    searchResult = await readYoutubeSearchResponse(
      search.value,
      claim.maxResults,
    );
  } catch {
    const recorded = await safeRecordTransport(dependencies, {
      transport_id: search.transportId,
      status: "degraded",
      checked_at: observedAt,
      failure_code: "provider_response_invalid",
      response_hash: search.responseHash,
    });
    return {
      completion: completionFailure(
        claim,
        observedAt,
        recorded ? "provider_response_invalid" : "provider_outcome_unknown",
      ),
      externalRequestCount,
    };
  }
  const searchReceiptRecorded = await safeRecordTransport(dependencies, {
    transport_id: search.transportId,
    status: "ready",
    checked_at: observedAt,
    response_hash: searchResult.responseHash,
    item_count: searchResult.itemCount,
  });
  if (!searchReceiptRecorded) {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_outcome_unknown",
      ),
      externalRequestCount,
    };
  }

  const searchSummary: Record<string, Json> = {
    response_hash: searchResult.responseHash,
    item_count: searchResult.itemCount,
  };
  if (claim.mode === "manual_canary" && searchResult.videoIds.length !== 1) {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_response_invalid",
      ),
      externalRequestCount,
    };
  }

  if (searchResult.videoIds.length === 0) {
    return {
      completion: {
        version: YOUTUBE_INGESTION_VERSION,
        ingestion_id: claim.id,
        status: "completed",
        provider_key: claim.providerKey,
        adapter_version: claim.adapterVersion,
        observed_at: observedAt,
        search: searchSummary,
        videos: null,
        observations: [],
      },
      externalRequestCount,
    };
  }

  let videosUrl: URL;
  try {
    videosUrl = buildYoutubeVideosUrl(
      searchResult.videoIds,
      dependencies.apiKey,
    );
  } catch {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_response_invalid",
      ),
      externalRequestCount,
    };
  }
  const videos = await performProviderFetch(
    claim,
    dependencies,
    videosUrl,
    2,
    "videos.list",
    "default",
    observedAt,
  );
  if (videos.transportId) externalRequestCount += 1;
  if (!videos.ok) {
    return {
      completion: completionFailure(claim, observedAt, videos.code),
      externalRequestCount,
    };
  }

  let videosResult;
  try {
    videosResult = await readYoutubeVideosResponse(
      videos.value,
      searchResult.videoIds,
      observedAt,
    );
  } catch {
    const recorded = await safeRecordTransport(dependencies, {
      transport_id: videos.transportId,
      status: "degraded",
      checked_at: observedAt,
      failure_code: "provider_response_invalid",
      response_hash: videos.responseHash,
    });
    return {
      completion: completionFailure(
        claim,
        observedAt,
        recorded ? "provider_response_invalid" : "provider_outcome_unknown",
      ),
      externalRequestCount,
    };
  }
  const videosReceiptRecorded = await safeRecordTransport(dependencies, {
    transport_id: videos.transportId,
    status: "ready",
    checked_at: observedAt,
    response_hash: videosResult.responseHash,
    item_count: videosResult.itemCount,
  });
  if (!videosReceiptRecorded) {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_outcome_unknown",
      ),
      externalRequestCount,
    };
  }
  if (
    claim.mode === "manual_canary" &&
    (videosResult.itemCount !== 1 || videosResult.missingVideoCount !== 0)
  ) {
    return {
      completion: completionFailure(
        claim,
        observedAt,
        "provider_response_invalid",
      ),
      externalRequestCount,
    };
  }
  const videosSummary: Record<string, Json> = {
    response_hash: videosResult.responseHash,
    item_count: videosResult.itemCount,
  };
  return {
    completion: {
      version: YOUTUBE_INGESTION_VERSION,
      ingestion_id: claim.id,
      status: "completed",
      provider_key: claim.providerKey,
      adapter_version: claim.adapterVersion,
      observed_at: observedAt,
      search: searchSummary,
      videos: videosSummary,
      ...(claim.mode === "manual_canary"
        ? {
          canary: {
            request_kind: "videos.list",
            response_hash: videosResult.responseHash,
            item_count: videosResult.itemCount,
            checked_at: observedAt,
          },
          observations: [] as Json[],
        }
        : {
          observations: videosResult.observations as unknown as Json[],
        }),
    },
    externalRequestCount,
  };
}

function readTransportPermit(
  value: unknown,
  expected: BeginTransportPayload,
): TransportPermit | null {
  if (
    !isRecord(value) || value.ok !== true || !isUuid(value.transport_id) ||
    typeof value.external_call_allowed !== "boolean" ||
    value.provider_key !== YOUTUBE_PROVIDER_KEY ||
    value.adapter_version !== YOUTUBE_ADAPTER_VERSION ||
    value.request_ordinal !== expected.request_ordinal ||
    value.request_kind !== expected.request_kind
  ) return null;
  return {
    transportId: value.transport_id,
    externalCallAllowed: value.external_call_allowed,
  };
}

function youtubeSecret(): string {
  return (Deno.env.get("YOUTUBE_DATA_API_KEY") ?? "").trim();
}

async function handleCreatorResearchIngestion(
  request: Request,
  context: SupabaseContext<ContentEngineDatabase>,
  internalWorker: boolean,
): Promise<Response> {
  if (internalWorker && !(await isInternalWorkerAuthorized(request))) {
    return json(request, { ok: false, code: "authentication_required" }, 401);
  }
  if (request.method !== "POST") {
    return json(request, { ok: false, code: "method_not_allowed" }, 405);
  }
  if (
    (!internalWorker && request.headers.get("origin") !== PUBLIC_APP_ORIGIN) ||
    (internalWorker && request.headers.get("origin") !== null)
  ) {
    return json(request, { ok: false, code: "origin_not_allowed" }, 403);
  }
  if (
    internalWorker && request.headers.get(INTERNAL_WORKER_HEADER) !== "1"
  ) {
    return json(request, { ok: false, code: "worker_request_required" }, 403);
  }
  if (!internalWorker && !context.userClaims?.id) {
    return json(request, { ok: false, code: "authentication_required" }, 401);
  }
  const contentType = request.headers.get("content-type") ?? "";
  const mediaType = contentType.split(";", 1)[0].trim().toLocaleLowerCase(
    "en-US",
  );
  if (mediaType !== "application/json") {
    return json(request, { ok: false, code: "content_type_invalid" }, 415);
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }

  let body: unknown;
  try {
    body = await readBoundedRequest(request);
  } catch (error) {
    return json(
      request,
      {
        ok: false,
        code: error instanceof Error && error.message === "request_too_large"
          ? "request_too_large"
          : "invalid_json",
      },
      error instanceof Error && error.message === "request_too_large"
        ? 413
        : 400,
    );
  }
  const payload = readRequestPayload(body);
  if (payload === null) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }

  const readStatus = async (): Promise<
    { data: Json; status: string } | null
  > => {
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_research_youtube_status",
        { p_payload: { ingestion_id: payload.ingestionId } },
      );
      return error === null
        ? readStatusEnvelope(data, payload.ingestionId)
        : null;
    } catch {
      return null;
    }
  };
  if (!internalWorker) {
    const current = await readStatus();
    if (current === null) {
      return json(request, { ok: false, code: "ingestion_rejected" }, 403);
    }
    if (current.status !== "queued") {
      return json(
        request,
        current.data,
        current.status === "processing" ? 202 : 200,
      );
    }
  }

  let claim: {
    claimed: boolean;
    status: "processing" | "completed" | "failed";
    ingestion: YoutubeIngestionClaim;
  } | null = null;
  try {
    const client = internalWorker ? context.supabaseAdmin : context.supabase;
    const rpcName = internalWorker
      ? "system_read_automatic_research_youtube_ingestion"
      : "creator_claim_research_youtube_ingestion";
    const { data, error } = await client.rpc(
      rpcName,
      { p_payload: { ingestion_id: payload.ingestionId } },
    );
    if (error === null) {
      claim = internalWorker
        ? readAutomaticYoutubeIngestionClaim(data, payload.ingestionId)
        : readAuthorizedYoutubeIngestionClaim(data, payload.ingestionId);
    }
  } catch {
    claim = null;
  }
  if (claim === null) {
    return json(request, { ok: false, code: "ingestion_rejected" }, 403);
  }
  if (!claim.claimed) {
    if (internalWorker) {
      if (claim.status !== "processing") {
        return json(request, { ok: false, code: "ingestion_rejected" }, 403);
      }
      // The durable background worker claims before HTTP dispatch. A lost
      // dispatch response therefore leaves a processing lease that expires to
      // failed and can never be automatically selected again.
    } else {
      const status = await readStatus();
      return status === null
        ? json(request, { ok: false, code: "ingestion_unavailable" }, 503)
        : json(
          request,
          status.data,
          status.status === "processing" ? 202 : 200,
        );
    }
  }

  const beginTransport = async (
    transportPayload: BeginTransportPayload,
  ): Promise<TransportPermit | null> => {
    try {
      const rpcName = internalWorker
        ? "system_begin_automatic_research_youtube_transport"
        : "system_begin_research_youtube_transport";
      const { data, error } = await context.supabaseAdmin.rpc(
        rpcName,
        { p_payload: transportPayload },
      );
      return error === null
        ? readTransportPermit(data, transportPayload)
        : null;
    } catch {
      return null;
    }
  };
  const recordTransport = async (
    transportPayload: RecordTransportPayload,
  ): Promise<void> => {
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_record_research_youtube_transport",
      { p_payload: transportPayload },
    );
    if (
      error || !isRecord(data) || data.ok !== true ||
      !isUuid(data.receipt_id)
    ) {
      throw new Error("youtube_transport_receipt_failed");
    }
  };

  const execution = await executeYoutubeIngestion(claim.ingestion, {
    apiKey: youtubeSecret(),
    fetcher: fetch,
    now: () => new Date(),
    beginTransport,
    recordTransport,
  });
  let completionResult: Json | null = null;
  try {
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_complete_research_youtube_ingestion",
      { p_payload: execution.completion },
    );
    if (
      error || !isRecord(data) || data.ok !== true ||
      data.version !== YOUTUBE_INGESTION_VERSION ||
      !isRecord(data.ingestion) ||
      data.ingestion.id !== payload.ingestionId ||
      !["completed", "failed"].includes(String(data.ingestion.status))
    ) {
      return json(request, { ok: false, code: "ingestion_unavailable" }, 503);
    }
    completionResult = data as Json;
  } catch {
    return json(request, { ok: false, code: "ingestion_unavailable" }, 503);
  }
  if (internalWorker) return json(request, completionResult);
  const completed = await readStatus();
  return completed === null
    ? json(request, { ok: false, code: "ingestion_unavailable" }, 503)
    : json(request, completed.data);
}

const CREATOR_RESEARCH_INGESTION_USER_OPTIONS = {
  auth: "user",
  cors: {
    "Access-Control-Allow-Headers":
      "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Origin": PUBLIC_APP_ORIGIN,
    Vary: "Origin",
  },
} as const;

const CREATOR_RESEARCH_INGESTION_WORKER_OPTIONS = {
  auth: "none",
  cors: false,
} as const;

const creatorResearchIngestion = withSupabase<ContentEngineDatabase>(
  CREATOR_RESEARCH_INGESTION_USER_OPTIONS,
  (request, context) => handleCreatorResearchIngestion(request, context, false),
);
const creatorResearchIngestionWorker = withSupabase<ContentEngineDatabase>(
  CREATOR_RESEARCH_INGESTION_WORKER_OPTIONS,
  (request, context) => handleCreatorResearchIngestion(request, context, true),
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
    if (isInternalWorkerRequest(request)) {
      return creatorResearchIngestionWorker(request);
    }
    return creatorResearchIngestion(request);
  },
};
