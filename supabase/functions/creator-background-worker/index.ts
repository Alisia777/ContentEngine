import { withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  INTERNAL_WORKER_SECRET_HEADER,
  isInternalWorkerAuthorized,
} from "../_shared/internal-worker-auth.ts";
const MAX_BODY_BYTES = 1_024;
const MAX_LIMIT_PER_QUEUE = 6;
const MAX_TOTAL_DISPATCHES = 8;
const MAX_RESEARCH_POLL_LIMIT = 4;
const DEFAULT_GENERATION_LIMIT = 4;
const DEFAULT_RESEARCH_LIMIT = 1;
const DEFAULT_REVIEW_LIMIT = 1;
const DEFAULT_YOUTUBE_LIMIT = 1;
const LEASE_RECONCILE_LIMIT = 50;
const NOTIFICATION_OUTBOX_LIMIT = 12;
const STORAGE_CLEANUP_LIMIT = 6;
const WATCHLIST_REFRESH_PROPOSAL_LIMIT = 50;
const YOUTUBE_OBSERVATION_ANALYSIS_LIMIT = 6;
const WORKER_LEASE_SECONDS = 210;
const DISPATCH_TIMEOUT_MS = 135_000;
const RESPONSE_BODY_LIMIT = 65_536;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const IMAGE_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

type QueueRow = {
  id: string;
  organization_id?: string;
  project_id?: string;
  status?: string;
  media_object_id?: string;
  recipient_id?: string;
  evidence_set_id?: string | null;
  next_attempt_at?: string | null;
};

type StartingWatchdogSummary = {
  selected: number;
  marked: number;
  failed: number;
};

type StorageCleanupRow = {
  id: string;
  organization_id: string;
  generation_job_id: string;
  bucket_id: string;
  object_name: string;
  status: string;
  attempt_count: number;
};

type StorageCleanupSummary = {
  selected: number;
  completed: number;
  retried: number;
  deadLetter: number;
  failed: number;
};

type MediaRow = {
  id: string;
  mime_type: string;
  status: string;
};

type Database = {
  public: {
    Tables: Record<string, never>;
    Views: Record<string, never>;
    Functions: Record<string, {
      Args: { p_payload: Json };
      Returns: Json;
    }>;
  };
  content_factory: {
    Tables: {
      generation_jobs: {
        Row: {
          id: string;
          organization_id: string;
          project_id: string;
          status: string;
          mode: string;
          provider: string;
          requested_by: string;
          provider_next_poll_at: string | null;
          updated_at: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
      generation_storage_cleanup_queue: {
        Row: StorageCleanupRow & {
          next_attempt_at: string;
          lease_token: string | null;
          processing_started_at: string | null;
          last_error_code: string | null;
          completed_at: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, never>;
        Update: {
          status?: string;
          attempt_count?: number;
          next_attempt_at?: string;
          lease_token?: string | null;
          processing_started_at?: string | null;
          last_error_code?: string | null;
          completed_at?: string | null;
        };
        Relationships: [];
      };
      product_research_runs: {
        Row: {
          id: string;
          organization_id: string;
          project_id: string;
          created_by: string;
          status: string;
          created_at: string;
          updated_at: string;
        };
        Insert: Record<string, never>;
        Update: { updated_at?: string };
        Relationships: [];
      };
      content_review_runs: {
        Row: {
          id: string;
          organization_id: string;
          project_id: string;
          media_object_id: string;
          requested_by: string;
          status: string;
          created_at: string;
          evidence_set_id: string | null;
          next_attempt_at: string | null;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
      media_objects: {
        Row: {
          id: string;
          mime_type: string;
          status: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
  };
};

type WorkerPayload = {
  generation_limit: number;
  research_limit: number;
  review_limit: number;
  youtube_limit: number;
};

type DispatchKind = "generation" | "research" | "review" | "youtube";

type DispatchTarget = {
  kind: DispatchKind;
  functionName:
    | "creator-generate"
    | "creator-product-research"
    | "creator-content-review"
    | "creator-research-ingestion";
  body: Record<string, Json>;
  organizationId: string;
  recipientId: string;
  entityId: string;
};

type DispatchOutcome = {
  kind: DispatchKind;
  ok: boolean;
  terminal: boolean;
  status: string | null;
  errorCode: string | null;
  organizationId: string;
  recipientId: string;
  entityId: string;
};

type WorkerRunLease = {
  id: string;
  leaseToken: string;
};

type WorkerBeginResult = {
  acquired: boolean;
  run: WorkerRunLease | null;
};

type PollRecordSummary = {
  recorded: number;
  failed: number;
};

type NotificationOutboxItem = {
  id: string;
  leaseToken: string;
  payload: Record<string, Json>;
};

type NotificationOutboxSummary = {
  claimed: number;
  delivered: number;
  failed: number;
  unresolved: number;
  pending: number;
  delivering: number;
  deadLetter: number;
  due: number;
  ok: boolean;
};

type LeaseReconciliation = {
  research: number;
  review: number;
};

type WatchlistRefreshProposalSummary = {
  ok: boolean;
  selected: number;
  created: number;
  existing: number;
  due: number;
  code?: string;
};

type AutomaticYoutubeIngestion = {
  ingestionId: string;
  organizationId: string;
  requestedBy: string;
};

type AutomaticYoutubeCollectionSummary = {
  ok: boolean;
  selected: number;
  claimed: number;
  expired: number;
  ingestions: AutomaticYoutubeIngestion[];
  code?: string;
};

export type YoutubeObservationAnalysisSummary = {
  ok: boolean;
  selected: number;
  completed: number;
  failed: number;
  items: Json[];
  external_call_started: false;
  provider_attempt_count: 0;
  cost_minor: 0;
  automatic_retry_started: false;
  code?: string;
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "cache-control": "no-store",
      "content-type": "application/json; charset=utf-8",
      "x-content-type-options": "nosniff",
    },
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isQueueRow(
  value: unknown,
  organizationRequired = false,
): value is QueueRow {
  if (!isRecord(value) || !isUuid(value.id)) return false;
  return !organizationRequired || isUuid(value.organization_id);
}

function isMediaRow(value: unknown): value is MediaRow {
  return isRecord(value) && isUuid(value.id) &&
    typeof value.mime_type === "string" &&
    typeof value.status === "string";
}

function isStorageCleanupRow(value: unknown): value is StorageCleanupRow {
  return isRecord(value) && isUuid(value.id) &&
    isUuid(value.organization_id) && isUuid(value.generation_job_id) &&
    value.bucket_id === "contentengine-private" &&
    typeof value.object_name === "string" &&
    value.object_name.startsWith(`${value.organization_id}/`) &&
    value.object_name.includes("/generated/") &&
    (
      value.object_name.endsWith(`/${value.generation_job_id}.mp4`) ||
      value.object_name.endsWith(`/${value.generation_job_id}.png`)
    ) &&
    !value.object_name.split("/").includes("..") &&
    value.status === "pending" && Number.isSafeInteger(value.attempt_count) &&
    Number(value.attempt_count) >= 0 && Number(value.attempt_count) <= 5;
}

function isMissingStorageObjectError(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const status = value.statusCode ?? value.status;
  if (status === 404 || status === "404") return true;
  const code = typeof value.code === "string" ? value.code.toLowerCase() : "";
  const message = typeof value.message === "string"
    ? value.message.toLowerCase()
    : "";
  return code === "not_found" || code === "notfound" ||
    message.includes("not found") || message.includes("does not exist");
}

function boundedInteger(
  value: unknown,
  fallback: number,
): number | null {
  if (value === undefined) return fallback;
  return Number.isSafeInteger(value) && Number(value) >= 0 &&
      Number(value) <= MAX_LIMIT_PER_QUEUE
    ? Number(value)
    : null;
}

export function readPayload(value: unknown): WorkerPayload | null {
  if (value === null || value === undefined) {
    return {
      generation_limit: DEFAULT_GENERATION_LIMIT,
      research_limit: DEFAULT_RESEARCH_LIMIT,
      review_limit: DEFAULT_REVIEW_LIMIT,
      youtube_limit: DEFAULT_YOUTUBE_LIMIT,
    };
  }
  if (!isRecord(value)) return null;
  const allowed = new Set([
    "generation_limit",
    "research_limit",
    "review_limit",
    "youtube_limit",
  ]);
  if (!Object.keys(value).every((key) => allowed.has(key))) return null;
  const generation = boundedInteger(
    value.generation_limit,
    DEFAULT_GENERATION_LIMIT,
  );
  const research = boundedInteger(
    value.research_limit,
    DEFAULT_RESEARCH_LIMIT,
  );
  const review = boundedInteger(
    value.review_limit,
    DEFAULT_REVIEW_LIMIT,
  );
  // Existing explicit operational payloads predate automatic source
  // collection. Missing youtube_limit therefore remains provider-free; the
  // empty/default worker request opts into one bounded collection.
  const youtube = boundedInteger(value.youtube_limit, 0);
  if (
    generation === null || research === null || review === null ||
    youtube === null ||
    generation + research + review + youtube > MAX_TOTAL_DISPATCHES
  ) return null;
  return {
    generation_limit: generation,
    research_limit: research,
    review_limit: review,
    youtube_limit: youtube,
  };
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

async function readBoundedBody(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
): Promise<Uint8Array> {
  if (body === null) return new Uint8Array();
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maximum) throw new Error("body_too_large");
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

function workerSecret(): string | null {
  const value = Deno.env.get("CONTENTENGINE_WORKER_SECRET") ?? "";
  if (
    value.length < 32 || value.length > 512 || value !== value.trim() ||
    hasControlCharacter(value)
  ) return null;
  return value;
}

function serviceRoleKey(): string | null {
  const value = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (
    value.length < 32 || value.length > 4_096 || value !== value.trim() ||
    hasControlCharacter(value)
  ) return null;
  return value;
}

function supabaseOrigin(): string | null {
  const value = Deno.env.get("SUPABASE_URL") ?? "";
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" || url.username !== "" ||
      url.password !== "" || url.port !== "" ||
      !/^[a-z0-9]{20}\.supabase\.co$/u.test(url.hostname) ||
      url.pathname !== "/"
    ) return null;
    return url.origin;
  } catch {
    return null;
  }
}

async function fetchWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

function dispatchStatus(value: unknown): string | null {
  if (!isRecord(value) || value.ok !== true) return null;
  const envelope = isRecord(value.job)
    ? value.job
    : isRecord(value.run)
    ? value.run
    : isRecord(value.ingestion)
    ? value.ingestion
    : null;
  return envelope !== null && typeof envelope.status === "string"
    ? envelope.status
    : null;
}

function dispatchErrorCode(value: unknown, httpStatus: number): string {
  if (
    isRecord(value) && typeof value.code === "string" &&
    /^[a-z][a-z0-9_]{2,99}$/u.test(value.code)
  ) {
    return value.code;
  }
  if (httpStatus >= 400 && httpStatus <= 599) {
    return `dispatch_http_${httpStatus}`;
  }
  return "dispatch_response_invalid";
}

function isTerminal(kind: DispatchKind, status: string | null): boolean {
  if (status === null) return false;
  return kind === "generation"
    ? new Set(["succeeded", "failed", "cancelled"]).has(status)
    : new Set(["completed", "failed", "cancelled"]).has(status);
}

async function dispatch(
  target: DispatchTarget,
  origin: string,
  serviceKey: string,
  secret: string,
): Promise<DispatchOutcome> {
  const identity = {
    organizationId: target.organizationId,
    recipientId: target.recipientId,
    entityId: target.entityId,
  };
  try {
    const response = await fetchWithTimeout(
      `${origin}/functions/v1/${target.functionName}`,
      {
        method: "POST",
        redirect: "manual",
        headers: {
          apikey: serviceKey,
          authorization: `Bearer ${serviceKey}`,
          "content-type": "application/json",
          [INTERNAL_WORKER_HEADER]: "1",
          [INTERNAL_WORKER_SECRET_HEADER]: secret,
        },
        body: JSON.stringify(target.body),
      },
      DISPATCH_TIMEOUT_MS,
    );
    const bytes = await readBoundedBody(response.body, RESPONSE_BODY_LIMIT);
    let value: unknown;
    try {
      value = JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(bytes),
      );
    } catch {
      return {
        kind: target.kind,
        ok: false,
        terminal: false,
        status: null,
        errorCode: response.ok
          ? "dispatch_response_invalid"
          : `dispatch_http_${response.status}`,
        ...identity,
      };
    }
    if (!response.ok) {
      return {
        kind: target.kind,
        ok: false,
        terminal: false,
        status: null,
        errorCode: dispatchErrorCode(value, response.status),
        ...identity,
      };
    }
    const status = dispatchStatus(value);
    return {
      kind: target.kind,
      ok: status !== null,
      terminal: isTerminal(target.kind, status),
      status,
      errorCode: status === null
        ? dispatchErrorCode(value, response.status)
        : null,
      ...identity,
    };
  } catch {
    return {
      kind: target.kind,
      ok: false,
      terminal: false,
      status: null,
      errorCode: "dispatch_network_error",
      ...identity,
    };
  }
}

function safeCount(value: unknown): number | null {
  return Number.isSafeInteger(value) && Number(value) >= 0
    ? Number(value)
    : null;
}

function readWatchlistRefreshProposalSummary(
  value: unknown,
): WatchlistRefreshProposalSummary | null {
  if (!isRecord(value) || value.ok !== true) return null;
  const selected = safeCount(value.selected);
  const created = safeCount(value.created);
  const existing = safeCount(value.existing);
  const due = safeCount(value.due);
  if (
    selected === null || created === null || existing === null ||
    due === null ||
    selected > WATCHLIST_REFRESH_PROPOSAL_LIMIT ||
    created > selected || existing > due
  ) return null;
  return { ok: true, selected, created, existing, due };
}

export function readAutomaticYoutubeCollectionSummary(
  value: unknown,
  limit: number,
): AutomaticYoutubeCollectionSummary | null {
  if (
    !Number.isSafeInteger(limit) || limit < 1 || limit > MAX_LIMIT_PER_QUEUE
  ) {
    return null;
  }
  const expectedKeys = new Set([
    "ok",
    "selected",
    "claimed",
    "expired",
    "items",
    "external_call_started",
    "automatic_retry_started",
  ]);
  if (
    !isRecord(value) || Object.keys(value).length !== expectedKeys.size ||
    !Object.keys(value).every((key) => expectedKeys.has(key)) ||
    value.ok !== true ||
    value.external_call_started !== false ||
    value.automatic_retry_started !== false ||
    !Array.isArray(value.items) || value.items.length > limit
  ) return null;
  const selected = safeCount(value.selected);
  const claimed = safeCount(value.claimed);
  const expired = safeCount(value.expired);
  if (
    selected === null || claimed === null || expired === null ||
    selected > limit || claimed > selected || claimed !== value.items.length ||
    expired > 100
  ) return null;
  const ingestions: AutomaticYoutubeIngestion[] = [];
  for (const item of value.items) {
    if (
      !isRecord(item) || Object.keys(item).length !== 8 ||
      !isUuid(item.ingestion_id) || !isUuid(item.organization_id) ||
      !isUuid(item.requested_by) || item.status !== "processing" ||
      item.mode !== "category_refresh" ||
      item.provider_key !== "youtube_data_api_v3" ||
      item.max_http_requests !== 2 || item.max_quota_units !== 2
    ) return null;
    ingestions.push({
      ingestionId: item.ingestion_id,
      organizationId: item.organization_id,
      requestedBy: item.requested_by,
    });
  }
  return {
    ok: true,
    selected,
    claimed,
    expired,
    ingestions,
  };
}

export function readYoutubeObservationAnalysisSummary(
  value: unknown,
  limit = YOUTUBE_OBSERVATION_ANALYSIS_LIMIT,
): YoutubeObservationAnalysisSummary | null {
  if (
    !Number.isSafeInteger(limit) || limit < 1 ||
    limit > YOUTUBE_OBSERVATION_ANALYSIS_LIMIT
  ) return null;
  const expectedKeys = new Set([
    "ok",
    "selected",
    "completed",
    "failed",
    "items",
    "external_call_started",
    "provider_attempt_count",
    "cost_minor",
    "automatic_retry_started",
  ]);
  if (
    !isRecord(value) || Object.keys(value).length !== expectedKeys.size ||
    !Object.keys(value).every((key) => expectedKeys.has(key)) ||
    value.ok !== true || value.external_call_started !== false ||
    value.provider_attempt_count !== 0 ||
    value.cost_minor !== 0 ||
    value.automatic_retry_started !== false || !Array.isArray(value.items) ||
    value.items.length > limit
  ) return null;
  const selected = safeCount(value.selected);
  const completed = safeCount(value.completed);
  const failed = safeCount(value.failed);
  if (
    selected === null || completed === null || failed === null ||
    selected > limit || completed + failed !== selected ||
    value.items.length !== selected
  ) return null;
  const jobIds = new Set<string>();
  let completedItems = 0;
  let failedItems = 0;
  const allowedErrorCodes = new Set([
    "analysis_input_changed",
    "analysis_evidence_expired",
    "analysis_parser_failed",
  ]);
  for (const item of value.items) {
    if (!isRecord(item) || !isUuid(item.job_id) || !isUuid(item.ingestion_id)) {
      return null;
    }
    if (jobIds.has(item.job_id)) return null;
    jobIds.add(item.job_id);
    if (item.status === "completed") {
      if (
        Object.keys(item).length !== 4 ||
        !Number.isSafeInteger(item.parsed_count) ||
        (item.parsed_count as number) < 0 ||
        (item.parsed_count as number) > 25
      ) return null;
      completedItems += 1;
      continue;
    }
    if (
      item.status !== "failed" || Object.keys(item).length !== 4 ||
      typeof item.error_code !== "string" ||
      !allowedErrorCodes.has(item.error_code)
    ) return null;
    failedItems += 1;
  }
  if (completedItems !== completed || failedItems !== failed) return null;
  let serializedItems = "";
  try {
    serializedItems = JSON.stringify(value.items);
  } catch {
    return null;
  }
  if (serializedItems.length > 32_768) return null;
  return {
    ok: true,
    selected,
    completed,
    failed,
    items: value.items as Json[],
    external_call_started: false,
    provider_attempt_count: 0,
    cost_minor: 0,
    automatic_retry_started: false,
  };
}

function youtubeObservationAnalysisFailure(
  code = "youtube_observation_analysis_failed",
): YoutubeObservationAnalysisSummary {
  return {
    ok: false,
    selected: 0,
    completed: 0,
    failed: 0,
    items: [],
    external_call_started: false,
    provider_attempt_count: 0,
    cost_minor: 0,
    automatic_retry_started: false,
    code,
  };
}

export function youtubeObservationAnalysisHasFailure(
  summary: YoutubeObservationAnalysisSummary,
): boolean {
  return !summary.ok || summary.failed > 0;
}

function readLeaseReconciliation(value: unknown): LeaseReconciliation | null {
  if (!isRecord(value) || value.ok !== true || !isRecord(value.expired)) {
    return null;
  }
  const research = safeCount(value.expired.research);
  const review = safeCount(value.expired.review);
  return research === null || review === null ? null : { research, review };
}

function isNotificationPayload(
  value: unknown,
): value is Record<string, Json> {
  if (!isRecord(value) || JSON.stringify(value).length > 49_152) return false;
  const expected = new Set([
    "organization_id",
    "recipient_id",
    "kind",
    "severity",
    "title",
    "body",
    "deep_link",
    "entity_type",
    "entity_id",
    "properties",
    "idempotency_key",
  ]);
  return Object.keys(value).length === expected.size &&
    Object.keys(value).every((key) => expected.has(key)) &&
    isUuid(value.organization_id) &&
    isUuid(value.recipient_id) &&
    typeof value.kind === "string" &&
    typeof value.severity === "string" &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.deep_link === "string" &&
    typeof value.entity_type === "string" &&
    typeof value.entity_id === "string" &&
    isRecord(value.properties) &&
    typeof value.idempotency_key === "string";
}

function readNotificationOutboxItems(
  value: unknown,
): NotificationOutboxItem[] | null {
  if (
    !isRecord(value) || value.ok !== true || !Array.isArray(value.items) ||
    value.items.length > NOTIFICATION_OUTBOX_LIMIT
  ) return null;
  const items: NotificationOutboxItem[] = [];
  for (const candidate of value.items) {
    if (
      !isRecord(candidate) || !isUuid(candidate.id) ||
      !isUuid(candidate.lease_token) ||
      !isNotificationPayload(candidate.payload)
    ) return null;
    items.push({
      id: candidate.id,
      leaseToken: candidate.lease_token,
      payload: candidate.payload,
    });
  }
  return items;
}

function readNotificationHealth(
  value: unknown,
):
  | Omit<
    NotificationOutboxSummary,
    "claimed" | "delivered" | "failed" | "ok"
  >
  | null {
  if (!isRecord(value) || value.ok !== true) return null;
  const unresolved = safeCount(value.unresolved);
  const pending = safeCount(value.pending);
  const delivering = safeCount(value.delivering);
  const deadLetter = safeCount(value.failed);
  const due = safeCount(value.due);
  if (
    unresolved === null || pending === null || delivering === null ||
    deadLetter === null || due === null ||
    unresolved !== pending + delivering + deadLetter
  ) return null;
  return { unresolved, pending, delivering, deadLetter, due };
}

function readWorkerBegin(value: unknown): WorkerBeginResult | null {
  if (
    !isRecord(value) || value.ok !== true || typeof value.acquired !== "boolean"
  ) {
    return null;
  }
  if (!value.acquired) return { acquired: false, run: null };
  if (
    !isRecord(value.run) || !isUuid(value.run.id) ||
    !isUuid(value.run.lease_token)
  ) return null;
  return {
    acquired: true,
    run: { id: value.run.id, leaseToken: value.run.lease_token },
  };
}

async function beginBackgroundWorker(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
): Promise<WorkerBeginResult | null> {
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_begin_background_worker",
      {
        p_payload: {
          trigger_source: "edge",
          lease_seconds: WORKER_LEASE_SECONDS,
        },
      },
    );
    return error === null ? readWorkerBegin(data) : null;
  } catch {
    return null;
  }
}

async function heartbeatBackgroundWorker(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  run: WorkerRunLease,
): Promise<boolean> {
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_heartbeat_background_worker",
      {
        p_payload: {
          run_id: run.id,
          lease_token: run.leaseToken,
          lease_seconds: WORKER_LEASE_SECONDS,
        },
      },
    );
    return error === null && isRecord(data) && data.ok === true &&
      isRecord(data.run) && data.run.id === run.id;
  } catch {
    return false;
  }
}

async function finishBackgroundWorker(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  run: WorkerRunLease,
  status: "completed" | "failed",
  summary: Record<string, Json>,
  errorCode?: string,
): Promise<boolean> {
  const payload: Record<string, Json> = {
    run_id: run.id,
    lease_token: run.leaseToken,
    status,
    summary,
  };
  if (status === "failed") {
    const candidate = errorCode ?? "";
    payload.error_code = /^[a-z][a-z0-9_]{2,99}$/u.test(candidate)
      ? candidate
      : "background_batch_incomplete";
  }
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_finish_background_worker",
      { p_payload: payload },
    );
    return error === null && isRecord(data) && data.ok === true;
  } catch {
    return false;
  }
}

async function recordGenerationPollOutcomes(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  run: WorkerRunLease,
  outcomes: DispatchOutcome[],
): Promise<PollRecordSummary> {
  let recorded = 0;
  let failed = 0;
  for (const outcome of outcomes) {
    if (outcome.kind !== "generation") continue;
    const state = outcome.ok
      ? outcome.terminal ? "success_terminal" : "success_pending"
      : "failed";
    const payload: Record<string, Json> = {
      run_id: run.id,
      lease_token: run.leaseToken,
      job_id: outcome.entityId,
      outcome: state,
    };
    if (state === "failed") {
      payload.error_code = outcome.errorCode ??
        "generation_poll_dispatch_failed";
    }
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_record_generation_poll_outcome",
        { p_payload: payload },
      );
      if (error === null && isRecord(data) && data.ok === true) recorded += 1;
      else failed += 1;
    } catch {
      failed += 1;
    }
  }
  return { recorded, failed };
}

async function reconcileStaleStartingJobs(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  rows: QueueRow[],
): Promise<StartingWatchdogSummary> {
  let marked = 0;
  let failed = 0;
  for (const row of rows) {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_mark_real_generation_reconciliation_required",
        {
          p_payload: {
            job_id: row.id,
            reason_code: "provider_create_state_stale",
          },
        },
      );
      if (error !== null || !isRecord(data) || data.ok !== true) {
        failed += 1;
      } else if (data.marked === true) {
        marked += 1;
      }
    } catch {
      failed += 1;
    }
  }
  return { selected: rows.length, marked, failed };
}

async function reconcileExpiredLeases(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
): Promise<LeaseReconciliation | null> {
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_reconcile_background_leases",
      { p_payload: { limit: LEASE_RECONCILE_LIMIT } },
    );
    return error === null ? readLeaseReconciliation(data) : null;
  } catch {
    return null;
  }
}

async function proposeDueResearchRefreshes(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
): Promise<WatchlistRefreshProposalSummary> {
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_propose_due_research_refreshes",
      { p_payload: { limit: WATCHLIST_REFRESH_PROPOSAL_LIMIT } },
    );
    const parsed = error === null
      ? readWatchlistRefreshProposalSummary(data)
      : null;
    return parsed ?? {
      ok: false,
      selected: 0,
      created: 0,
      existing: 0,
      due: 0,
      code: "research_refresh_proposal_failed",
    };
  } catch {
    return {
      ok: false,
      selected: 0,
      created: 0,
      existing: 0,
      due: 0,
      code: "research_refresh_proposal_failed",
    };
  }
}

async function prepareAutomaticYoutubeCollection(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  limit: number,
): Promise<AutomaticYoutubeCollectionSummary> {
  if (limit === 0) {
    return {
      ok: true,
      selected: 0,
      claimed: 0,
      expired: 0,
      ingestions: [],
    };
  }
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_claim_due_research_youtube_collection",
      { p_payload: { limit } },
    );
    const parsed = error === null
      ? readAutomaticYoutubeCollectionSummary(data, limit)
      : null;
    if (parsed !== null) return parsed;
  } catch {
    // Fall through to one bounded, secret-free failure summary.
  }
  return {
    ok: false,
    selected: 0,
    claimed: 0,
    expired: 0,
    ingestions: [],
    code: "youtube_collection_claim_failed",
  };
}

export async function processDueYoutubeObservationAnalysis(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  limit = YOUTUBE_OBSERVATION_ANALYSIS_LIMIT,
): Promise<YoutubeObservationAnalysisSummary> {
  if (
    !Number.isSafeInteger(limit) || limit < 1 ||
    limit > YOUTUBE_OBSERVATION_ANALYSIS_LIMIT
  ) {
    return youtubeObservationAnalysisFailure(
      "youtube_observation_analysis_limit_invalid",
    );
  }
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_process_due_research_youtube_observation_analysis",
      { p_payload: { limit } },
    );
    const parsed = error === null
      ? readYoutubeObservationAnalysisSummary(data, limit)
      : null;
    return parsed ?? youtubeObservationAnalysisFailure();
  } catch {
    return youtubeObservationAnalysisFailure();
  }
}

async function completeNotificationOutbox(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
  item: NotificationOutboxItem,
  delivered: boolean,
): Promise<boolean> {
  const completion: Record<string, Json> = {
    outbox_id: item.id,
    lease_token: item.leaseToken,
    delivered,
  };
  if (!delivered) completion.error_code = "notification_emit_failed";
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_complete_notification_outbox",
      { p_payload: completion },
    );
    return error === null && isRecord(data) && data.ok === true;
  } catch {
    return false;
  }
}

async function deliverNotificationOutbox(
  supabaseAdmin: {
    rpc: (
      name: string,
      args: { p_payload: Json },
    ) => PromiseLike<{ data: unknown; error: unknown }>;
  },
): Promise<NotificationOutboxSummary> {
  let items: NotificationOutboxItem[] | null = null;
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_claim_notification_outbox",
      { p_payload: { limit: NOTIFICATION_OUTBOX_LIMIT } },
    );
    if (error === null) items = readNotificationOutboxItems(data);
  } catch {
    items = null;
  }
  if (items === null) {
    return {
      claimed: 0,
      delivered: 0,
      failed: 1,
      unresolved: 1,
      pending: 0,
      delivering: 0,
      deadLetter: 0,
      due: 0,
      ok: false,
    };
  }

  let deliveredCount = 0;
  let failedCount = 0;
  for (const item of items) {
    let emitted = false;
    try {
      const { error } = await supabaseAdmin.rpc(
        "system_emit_notification",
        { p_payload: item.payload },
      );
      emitted = error === null;
    } catch {
      emitted = false;
    }
    const completed = await completeNotificationOutbox(
      supabaseAdmin,
      item,
      emitted,
    );
    if (emitted && completed) deliveredCount += 1;
    else failedCount += 1;
  }

  let health: ReturnType<typeof readNotificationHealth> = null;
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_notification_outbox_health",
      { p_payload: {} },
    );
    if (error === null) health = readNotificationHealth(data);
  } catch {
    health = null;
  }
  if (health === null) {
    return {
      claimed: items.length,
      delivered: deliveredCount,
      failed: failedCount + 1,
      unresolved: Math.max(1, items.length - deliveredCount),
      pending: 0,
      delivering: 0,
      deadLetter: 0,
      due: 0,
      ok: false,
    };
  }
  return {
    claimed: items.length,
    delivered: deliveredCount,
    failed: failedCount,
    ...health,
    ok: failedCount === 0 && health.unresolved === 0,
  };
}

const creatorBackgroundWorker = withSupabase<Database>({
  auth: "none",
  cors: false,
}, async (request, context) => {
  if (request.method !== "POST") {
    return json({ ok: false, code: "method_not_allowed" }, 405);
  }
  if (
    context.authMode !== "none" ||
    !(await isInternalWorkerAuthorized(request))
  ) {
    return json({ ok: false, code: "authentication_required" }, 401);
  }
  const supabaseAdmin = context.supabaseAdmin;
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLocaleLowerCase("en-US").startsWith("application/json")) {
    return json({ ok: false, code: "content_type_invalid" }, 415);
  }
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json({ ok: false, code: "request_too_large" }, 413);
  }

  let rawBody: Uint8Array;
  try {
    rawBody = await readBoundedBody(request.body, MAX_BODY_BYTES);
  } catch {
    return json({ ok: false, code: "request_too_large" }, 413);
  }
  let body: unknown = null;
  if (rawBody.byteLength > 0) {
    try {
      body = JSON.parse(
        new TextDecoder("utf-8", { fatal: true }).decode(rawBody),
      );
    } catch {
      return json({ ok: false, code: "invalid_json" }, 400);
    }
  }
  const payload = readPayload(body);
  if (payload === null) {
    return json({ ok: false, code: "invalid_payload" }, 400);
  }

  const secret = workerSecret();
  const serviceKey = serviceRoleKey();
  const origin = supabaseOrigin();
  if (secret === null || serviceKey === null || origin === null) {
    return json({ ok: false, code: "worker_configuration_error" }, 503);
  }

  const cleanupGeneratedStorage = async (): Promise<StorageCleanupSummary> => {
    const summary: StorageCleanupSummary = {
      selected: 0,
      completed: 0,
      retried: 0,
      deadLetter: 0,
      failed: 0,
    };
    const now = new Date();
    const nowIso = now.toISOString();
    const staleBeforeIso = new Date(now.getTime() - 15 * 60_000).toISOString();

    // A killed Edge invocation must not strand a cleanup row forever. The
    // global worker lease serializes healthy runs; the row lease makes this
    // recovery safe even if two invocations briefly overlap.
    try {
      const { error } = await supabaseAdmin
        .schema("content_factory")
        .from("generation_storage_cleanup_queue")
        .update({
          status: "pending",
          next_attempt_at: nowIso,
          lease_token: null,
          processing_started_at: null,
          last_error_code: "cleanup_lease_expired",
          completed_at: null,
        })
        .eq("status", "processing")
        .lt("processing_started_at", staleBeforeIso);
      if (error !== null) summary.failed += 1;
    } catch {
      summary.failed += 1;
    }

    let rows: StorageCleanupRow[] | null = null;
    try {
      const { data, error } = await supabaseAdmin
        .schema("content_factory")
        .from("generation_storage_cleanup_queue")
        .select(
          "id, organization_id, generation_job_id, bucket_id, object_name, status, attempt_count",
        )
        .eq("status", "pending")
        .lte("next_attempt_at", nowIso)
        .order("next_attempt_at", { ascending: true })
        .order("created_at", { ascending: true })
        .limit(STORAGE_CLEANUP_LIMIT);
      if (error === null && Array.isArray(data)) {
        rows = data.filter(isStorageCleanupRow);
        if (rows.length !== data.length) summary.failed += 1;
      }
    } catch {
      rows = null;
    }
    if (rows === null) {
      summary.failed += 1;
      return summary;
    }
    summary.selected = rows.length;

    for (const row of rows) {
      const leaseToken = crypto.randomUUID();
      // Five is a saturation counter, not a terminal retry budget. Cleanup is
      // idempotent, so a missing object or a completion-write loss must remain
      // recoverable indefinitely while the capacity reservation stays active.
      const attemptCount = Math.min(5, row.attempt_count + 1);
      let claimed = false;
      try {
        const { data, error } = await supabaseAdmin
          .schema("content_factory")
          .from("generation_storage_cleanup_queue")
          .update({
            status: "processing",
            attempt_count: attemptCount,
            lease_token: leaseToken,
            processing_started_at: nowIso,
            last_error_code: null,
            completed_at: null,
          })
          .eq("id", row.id)
          .eq("status", "pending")
          .eq("attempt_count", row.attempt_count)
          .select("id")
          .maybeSingle();
        claimed = error === null && isRecord(data) && data.id === row.id;
      } catch {
        claimed = false;
      }
      if (!claimed) {
        summary.failed += 1;
        continue;
      }

      let removed = false;
      try {
        const { error } = await supabaseAdmin.storage
          .from(row.bucket_id)
          .remove([row.object_name]);
        removed = error === null || isMissingStorageObjectError(error);
      } catch (error) {
        removed = isMissingStorageObjectError(error);
      }

      if (removed) {
        let completed = false;
        try {
          const { data, error } = await supabaseAdmin
            .schema("content_factory")
            .from("generation_storage_cleanup_queue")
            .update({
              status: "completed",
              lease_token: null,
              processing_started_at: null,
              completed_at: new Date().toISOString(),
              last_error_code: null,
            })
            .eq("id", row.id)
            .eq("status", "processing")
            .eq("lease_token", leaseToken)
            .select("id")
            .maybeSingle();
          completed = error === null && isRecord(data) && data.id === row.id;
        } catch {
          completed = false;
        }
        if (completed) summary.completed += 1;
        else summary.failed += 1;
        continue;
      }

      const delaySeconds = Math.min(3_600, 60 * (2 ** (attemptCount - 1)));
      let rescheduled = false;
      try {
        const { data, error } = await supabaseAdmin
          .schema("content_factory")
          .from("generation_storage_cleanup_queue")
          .update({
            status: "pending",
            next_attempt_at: new Date(Date.now() + delaySeconds * 1_000)
              .toISOString(),
            lease_token: null,
            processing_started_at: null,
            completed_at: null,
            last_error_code: "storage_cleanup_failed",
          })
          .eq("id", row.id)
          .eq("status", "processing")
          .eq("lease_token", leaseToken)
          .select("id")
          .maybeSingle();
        rescheduled = error === null && isRecord(data) && data.id === row.id;
      } catch {
        rescheduled = false;
      }
      if (!rescheduled) summary.failed += 1;
      else summary.retried += 1;
    }
    return summary;
  };

  const begun = await beginBackgroundWorker(supabaseAdmin);
  if (begun === null) {
    return json({ ok: false, code: "worker_lease_unavailable" }, 503);
  }
  if (!begun.acquired || begun.run === null) {
    return json({
      ok: true,
      code: "worker_already_running",
      selected: { generation: 0, research: 0, review: 0, youtube: 0 },
      completed: { generation: 0, research: 0, review: 0, youtube: 0 },
      pending: { generation: 0, research: 0, review: 0, youtube: 0 },
      failed: { generation: 0, research: 0, review: 0, youtube: 0 },
      youtube_collection: {
        selected: 0,
        expired: 0,
        claimed: 0,
      },
      youtube_analysis: {
        ok: true,
        selected: 0,
        completed: 0,
        failed: 0,
        items: [],
        external_call_started: false,
        provider_attempt_count: 0,
        cost_minor: 0,
        automatic_retry_started: false,
      },
      storage_cleanup: {
        selected: 0,
        completed: 0,
        retried: 0,
        deadLetter: 0,
        failed: 0,
      },
      notification: {
        claimed: 0,
        delivered: 0,
        failed: 0,
        unresolved: 0,
        pending: 0,
        delivering: 0,
        deadLetter: 0,
        due: 0,
        ok: true,
      },
    });
  }
  const workerRun = begun.run;

  try {
    const reconciliation = await reconcileExpiredLeases(supabaseAdmin);
    if (reconciliation === null) {
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        { stage: "lease_reconciliation" },
        "lease_reconciliation_failed",
      );
      return json({
        ok: false,
        code: "lease_reconciliation_failed",
      }, 503);
    }
    // This provider-free RPC only records that a human should consider a
    // refresh. It must never create a queued product_research_run: queued rows
    // below are dispatched to the paid research provider automatically.
    const watchlistRefresh = await proposeDueResearchRefreshes(supabaseAdmin);

    const queueNow = new Date().toISOString();
    const generationQuery = supabaseAdmin
      .schema("content_factory")
      .from("generation_jobs")
      .select(
        "id, organization_id, project_id, requested_by, status, mode, provider, provider_next_poll_at, updated_at",
      )
      .eq("mode", "real")
      .eq("provider", "runway")
      .in("status", ["starting", "submitted", "processing"])
      .lte("provider_next_poll_at", queueNow)
      .order("provider_next_poll_at", { ascending: true })
      .order("updated_at", { ascending: true })
      .limit(payload.generation_limit);
    const researchQuery = supabaseAdmin
      .schema("content_factory")
      .from("product_research_runs")
      .select("id, organization_id, project_id, created_by, status, created_at")
      // Queued rows own the one paid POST.
      .eq("status", "queued")
      .order("created_at", { ascending: true })
      .limit(payload.research_limit);
    const researchProcessingQuery = supabaseAdmin
      .schema("content_factory")
      .from("product_research_runs")
      .select(
        "id, organization_id, project_id, created_by, status, created_at, updated_at",
      )
      // Poll the least-recently touched active responses first. The worker
      // advances updated_at below before HTTP, so every tick rotates fairly
      // even when one OpenAI response remains pending for the full window.
      .eq("status", "processing")
      .order("updated_at", { ascending: true })
      .order("created_at", { ascending: true })
      .limit(payload.research_limit > 0 ? MAX_RESEARCH_POLL_LIMIT : 0);
    const reviewCandidateLimit = Math.min(
      MAX_LIMIT_PER_QUEUE * 3,
      Math.max(payload.review_limit * 3, MAX_LIMIT_PER_QUEUE),
    );
    const reviewQuery = supabaseAdmin
      .schema("content_factory")
      .from("content_review_runs")
      .select(
        "id, organization_id, project_id, requested_by, media_object_id, status, created_at, evidence_set_id, next_attempt_at",
      )
      .eq("status", "queued")
      // A null due time means an attempt already owns the row. Re-dispatching
      // it only creates observers and can starve genuinely due reviews.
      .lte("next_attempt_at", queueNow)
      .order("next_attempt_at", { ascending: true, nullsFirst: true })
      .order("created_at", { ascending: true })
      .limit(reviewCandidateLimit);

    const [
      generationResult,
      researchResult,
      researchProcessingResult,
      reviewResult,
    ] = await Promise.all([
      generationQuery,
      researchQuery,
      researchProcessingQuery,
      reviewQuery,
    ]);
    if (
      generationResult.error || researchResult.error ||
      researchProcessingResult.error || reviewResult.error ||
      !Array.isArray(generationResult.data) ||
      !Array.isArray(researchResult.data) ||
      !Array.isArray(researchProcessingResult.data) ||
      !Array.isArray(reviewResult.data)
    ) {
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        { stage: "queue_read" },
        "queue_read_failed",
      );
      return json({ ok: false, code: "queue_read_failed" }, 503);
    }

    const generationCandidates = generationResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.project_id) &&
      isUuid(row.requested_by)
    ).map((row) => ({
      ...row,
      recipient_id: row.requested_by,
    }));
    const staleStartingRows = generationCandidates.filter((row) =>
      row.status === "starting"
    );
    const generationRows = generationCandidates.filter((row) =>
      row.status === "submitted" || row.status === "processing"
    );
    // A stale starting row represents an ambiguous provider POST. The durable
    // watchdog only freezes it for explicit reconciliation; it never calls the
    // generation Edge Function and therefore cannot issue a duplicate POST.
    const startingWatchdog = await reconcileStaleStartingJobs(
      supabaseAdmin,
      staleStartingRows,
    );
    const researchProcessingCandidates = researchProcessingResult.data.filter((
      row,
    ) =>
      isQueueRow(row, true) && isUuid(row.project_id) && isUuid(row.created_by)
    );
    let researchProcessingRows = researchProcessingCandidates.slice(0, 0);
    if (researchProcessingCandidates.length > 0) {
      const processingIds = researchProcessingCandidates.map((row) => row.id);
      const pollDispatchedAt = new Date().toISOString();
      const marked = await supabaseAdmin
        .schema("content_factory")
        .from("product_research_runs")
        .update({ updated_at: pollDispatchedAt })
        .in("id", processingIds)
        .eq("status", "processing")
        .select(
          "id, organization_id, project_id, created_by, status, created_at, updated_at",
        );
      if (marked.error || !Array.isArray(marked.data)) {
        await finishBackgroundWorker(
          supabaseAdmin,
          workerRun,
          "failed",
          { stage: "research_poll_rotation" },
          "queue_read_failed",
        );
        return json({ ok: false, code: "queue_read_failed" }, 503);
      }
      researchProcessingRows = marked.data.filter((row) =>
        isQueueRow(row, true) && isUuid(row.project_id) &&
        isUuid(row.created_by)
      );
    }
    // Existing paid responses own the research capacity. Do not launch new
    // queued POSTs while the configured polling capacity is already occupied.
    const queuedResearchCapacity = researchProcessingRows.length === 0
      ? payload.research_limit
      : 0;
    const researchQueuedRows = researchResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.project_id) && isUuid(row.created_by)
    ).slice(0, queuedResearchCapacity);
    const researchRows = [
      ...researchProcessingRows,
      ...researchQueuedRows,
    ].map((row) => ({
      ...row,
      recipient_id: row.created_by,
    }));
    const reviewRows = reviewResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.project_id) &&
      isUuid(row.media_object_id) &&
      isUuid(row.requested_by)
    ).map((row) => ({
      ...row,
      recipient_id: row.requested_by,
    }));

    let mediaRows: MediaRow[] = [];
    const mediaIds = reviewRows.map((row) => row.media_object_id as string);
    if (mediaIds.length > 0) {
      const mediaResult = await supabaseAdmin
        .schema("content_factory")
        .from("media_objects")
        .select("id, mime_type, status")
        .in("id", mediaIds);
      if (mediaResult.error || !Array.isArray(mediaResult.data)) {
        await finishBackgroundWorker(
          supabaseAdmin,
          workerRun,
          "failed",
          { stage: "media_queue_read" },
          "queue_read_failed",
        );
        return json({ ok: false, code: "queue_read_failed" }, 503);
      }
      mediaRows = mediaResult.data.filter(isMediaRow);
    }
    const mediaById = new Map(mediaRows.map((row) => [row.id, row]));
    const eligibleReviews = reviewRows.filter((row) => {
      const media = mediaById.get(row.media_object_id as string);
      if (!media) return false;
      // Still dispatch supported media that became stale/unready after queueing:
      // the claim RPC terminal-cancels it before any provider marker. Dropping
      // those oldest rows here could starve every valid review behind them.
      if (IMAGE_MIME_TYPES.has(media.mime_type)) return true;
      return media.mime_type === "video/mp4" && isUuid(row.evidence_set_id);
    });
    const autonomousReviews = eligibleReviews.slice(0, payload.review_limit);
    const legacyMissingEvidence = reviewRows.filter((row) => {
      const media = mediaById.get(row.media_object_id as string);
      return media?.status === "ready" && media.mime_type === "video/mp4" &&
        !isUuid(row.evidence_set_id);
    }).length;
    const unsupportedOrUnready = Math.max(
      0,
      reviewRows.length - eligibleReviews.length - legacyMissingEvidence,
    );

    if (!(await heartbeatBackgroundWorker(supabaseAdmin, workerRun))) {
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        { stage: "before_youtube_claim" },
        "worker_heartbeat_failed",
      );
      return json({ ok: false, code: "worker_heartbeat_failed" }, 503);
    }
    // This RPC may recover never-claimed queued work, then atomically claims
    // each returned row before HTTP. From this point on, a lost response must
    // expire to failed and can never cause a later automatic dispatch.
    const youtubeCollection = await prepareAutomaticYoutubeCollection(
      supabaseAdmin,
      payload.youtube_limit,
    );

    // Preserve the global eight-dispatch ceiling. Trim only unclaimed work,
    // never a YouTube ingestion already claimed by the database workflow.
    const dispatchGenerationRows = [...generationRows];
    const dispatchResearchRows = [...researchRows];
    const dispatchReviewRows = [...autonomousReviews];
    const dispatchCount = () =>
      dispatchGenerationRows.length + dispatchResearchRows.length +
      dispatchReviewRows.length + youtubeCollection.ingestions.length;
    while (dispatchCount() > MAX_TOTAL_DISPATCHES) {
      if (dispatchGenerationRows.length > 1) {
        dispatchGenerationRows.pop();
      } else if (dispatchReviewRows.length > 1) {
        dispatchReviewRows.pop();
      } else if (dispatchGenerationRows.length > 0) {
        dispatchGenerationRows.pop();
      } else if (dispatchReviewRows.length > 0) {
        dispatchReviewRows.pop();
      } else {
        const queuedIndex = dispatchResearchRows.findLastIndex((row) =>
          row.status === "queued"
        );
        if (queuedIndex < 0) break;
        dispatchResearchRows.splice(queuedIndex, 1);
      }
    }

    const targets: DispatchTarget[] = [
      ...dispatchGenerationRows.map((row): DispatchTarget => ({
        kind: "generation",
        functionName: "creator-generate",
        body: {
          action: "status",
          organization_id: row.organization_id as string,
          project_id: row.project_id as string,
          job_id: row.id,
        },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
      ...dispatchResearchRows.map((row): DispatchTarget => ({
        kind: "research",
        functionName: "creator-product-research",
        body: {
          action: row.status === "processing" ? "status" : "analyze",
          research_id: row.id,
          project_id: row.project_id as string,
        },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
      ...dispatchReviewRows.map((row): DispatchTarget => ({
        kind: "review",
        functionName: "creator-content-review",
        body: {
          action: "analyze",
          review_id: row.id,
          project_id: row.project_id as string,
        },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
      ...youtubeCollection.ingestions.map((row): DispatchTarget => ({
        kind: "youtube",
        functionName: "creator-research-ingestion",
        body: { action: "ingest", ingestion_id: row.ingestionId },
        organizationId: row.organizationId,
        recipientId: row.requestedBy,
        entityId: row.ingestionId,
      })),
    ];

    const outcomes = await Promise.all(
      targets.map((target) => dispatch(target, origin, serviceKey, secret)),
    );
    // Persist external polling outcomes before any additional local work. A
    // repeated external poll must never be caused by a later analysis timeout.
    const pollRecords = await recordGenerationPollOutcomes(
      supabaseAdmin,
      workerRun,
      outcomes,
    );
    if (!(await heartbeatBackgroundWorker(supabaseAdmin, workerRun))) {
      const heartbeatSummary = {
        stage: "before_youtube_analysis",
        poll_records: pollRecords,
      };
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        heartbeatSummary,
        "worker_heartbeat_failed",
      );
      return json(
        { ok: false, code: "worker_heartbeat_failed", ...heartbeatSummary },
        503,
      );
    }
    // Analysis is a bounded, deterministic database mutation. It deliberately
    // runs only after all YouTube HTTP dispatches have settled, is not a
    // DispatchTarget, consumes none of the provider cap, and never requeues an
    // ingestion or starts an external retry.
    const youtubeAnalysis = await processDueYoutubeObservationAnalysis(
      supabaseAdmin,
      YOUTUBE_OBSERVATION_ANALYSIS_LIMIT,
    );
    const kinds: DispatchKind[] = [
      "generation",
      "research",
      "review",
      "youtube",
    ];
    const selected = Object.fromEntries(
      kinds.map((kind) => [
        kind,
        targets.filter((target) => target.kind === kind).length,
      ]),
    ) as Record<DispatchKind, number>;
    const completed = Object.fromEntries(
      kinds.map((kind) => [
        kind,
        outcomes.filter((outcome) => outcome.kind === kind && outcome.terminal)
          .length,
      ]),
    ) as Record<DispatchKind, number>;
    const failed = Object.fromEntries(
      kinds.map((kind) => [
        kind,
        outcomes.filter((outcome) => outcome.kind === kind && !outcome.ok)
          .length,
      ]),
    ) as Record<DispatchKind, number>;
    const pending = Object.fromEntries(
      kinds.map((kind) => [
        kind,
        outcomes.filter((outcome) =>
          outcome.kind === kind && outcome.ok && !outcome.terminal
        ).length,
      ]),
    ) as Record<DispatchKind, number>;
    const summary: Record<string, Json> = {
      selected,
      completed,
      pending,
      failed,
      generation_poll_records: pollRecords,
      starting_watchdog: startingWatchdog,
      review_queue_health: {
        due_candidates: reviewRows.length,
        eligible: eligibleReviews.length,
        selected: dispatchReviewRows.length,
        legacy_missing_evidence: legacyMissingEvidence,
        unready_or_unsupported: unsupportedOrUnready,
      },
      expired_leases: {
        research: reconciliation.research,
        review: reconciliation.review,
      },
      research_refresh_proposals: watchlistRefresh,
      youtube_collection: {
        selected: youtubeCollection.selected,
        expired: youtubeCollection.expired,
        claimed: youtubeCollection.claimed,
      },
      youtube_analysis: youtubeAnalysis,
    };
    if (!(await heartbeatBackgroundWorker(supabaseAdmin, workerRun))) {
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        summary,
        "worker_heartbeat_failed",
      );
      return json(
        { ok: false, code: "worker_heartbeat_failed", ...summary },
        503,
      );
    }
    const storageCleanup = await cleanupGeneratedStorage();
    summary.storage_cleanup = storageCleanup;
    const notification = await deliverNotificationOutbox(supabaseAdmin);
    const hasFailure = Object.values(failed).some((count) => count > 0) ||
      pollRecords.failed > 0 || startingWatchdog.failed > 0 ||
      storageCleanup.failed > 0 || !notification.ok || !watchlistRefresh.ok ||
      !youtubeCollection.ok ||
      youtubeObservationAnalysisHasFailure(youtubeAnalysis);
    const fullSummary: Record<string, Json> = { ...summary, notification };
    const finished = await finishBackgroundWorker(
      supabaseAdmin,
      workerRun,
      hasFailure ? "failed" : "completed",
      fullSummary,
      hasFailure ? "background_batch_incomplete" : undefined,
    );
    if (!finished) {
      return json({
        ok: false,
        code: "worker_finish_failed",
        ...summary,
        notification,
      }, 503);
    }
    return json({
      ok: !hasFailure,
      code: hasFailure ? "background_batch_incomplete" : undefined,
      ...summary,
      notification,
    }, hasFailure ? 502 : 200);
  } catch {
    await finishBackgroundWorker(
      supabaseAdmin,
      workerRun,
      "failed",
      { stage: "unhandled" },
      "background_worker_unhandled_error",
    );
    return json({
      ok: false,
      code: "background_worker_unhandled_error",
    }, 503);
  }
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    return creatorBackgroundWorker(request);
  },
};
