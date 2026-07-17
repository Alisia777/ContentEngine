import { withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  INTERNAL_WORKER_SECRET_HEADER,
  isInternalWorkerAuthorized,
} from "../_shared/internal-worker-auth.ts";
const MAX_BODY_BYTES = 1_024;
const MAX_LIMIT_PER_QUEUE = 6;
const MAX_TOTAL_DISPATCHES = 8;
const DEFAULT_GENERATION_LIMIT = 4;
const DEFAULT_RESEARCH_LIMIT = 1;
const DEFAULT_REVIEW_LIMIT = 1;
const LEASE_RECONCILE_LIMIT = 50;
const NOTIFICATION_OUTBOX_LIMIT = 12;
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
  media_object_id?: string;
  recipient_id?: string;
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
      product_research_runs: {
        Row: {
          id: string;
          organization_id: string;
          created_by: string;
          status: string;
          created_at: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
      content_review_runs: {
        Row: {
          id: string;
          organization_id: string;
          media_object_id: string;
          requested_by: string;
          status: string;
          created_at: string;
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
};

type DispatchKind = "generation" | "research" | "review";

type DispatchTarget = {
  kind: DispatchKind;
  functionName:
    | "creator-generate"
    | "creator-product-research"
    | "creator-content-review";
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

function readPayload(value: unknown): WorkerPayload | null {
  if (value === null || value === undefined) {
    return {
      generation_limit: DEFAULT_GENERATION_LIMIT,
      research_limit: DEFAULT_RESEARCH_LIMIT,
      review_limit: DEFAULT_REVIEW_LIMIT,
    };
  }
  if (!isRecord(value)) return null;
  const allowed = new Set([
    "generation_limit",
    "research_limit",
    "review_limit",
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
  if (
    generation === null || research === null || review === null ||
    generation + research + review > MAX_TOTAL_DISPATCHES
  ) return null;
  return {
    generation_limit: generation,
    research_limit: research,
    review_limit: review,
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

  const begun = await beginBackgroundWorker(supabaseAdmin);
  if (begun === null) {
    return json({ ok: false, code: "worker_lease_unavailable" }, 503);
  }
  if (!begun.acquired || begun.run === null) {
    return json({
      ok: true,
      code: "worker_already_running",
      selected: { generation: 0, research: 0, review: 0 },
      completed: { generation: 0, research: 0, review: 0 },
      pending: { generation: 0, research: 0, review: 0 },
      failed: { generation: 0, research: 0, review: 0 },
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

    const generationQuery = supabaseAdmin
      .schema("content_factory")
      .from("generation_jobs")
      .select(
        "id, organization_id, requested_by, status, mode, provider, provider_next_poll_at, updated_at",
      )
      .eq("mode", "real")
      .eq("provider", "runway")
      .in("status", ["submitted", "processing"])
      .lte("provider_next_poll_at", new Date().toISOString())
      .order("provider_next_poll_at", { ascending: true })
      .order("updated_at", { ascending: true })
      .limit(payload.generation_limit);
    const researchQuery = supabaseAdmin
      .schema("content_factory")
      .from("product_research_runs")
      .select("id, organization_id, created_by, status, created_at")
      .eq("status", "queued")
      .order("created_at", { ascending: true })
      .limit(payload.research_limit);
    const reviewCandidateLimit = Math.min(
      MAX_LIMIT_PER_QUEUE * 3,
      Math.max(payload.review_limit * 3, payload.review_limit),
    );
    const reviewQuery = supabaseAdmin
      .schema("content_factory")
      .from("content_review_runs")
      .select(
        "id, organization_id, requested_by, media_object_id, status, created_at",
      )
      .eq("status", "queued")
      .order("created_at", { ascending: true })
      .limit(reviewCandidateLimit);

    const [generationResult, researchResult, reviewResult] = await Promise.all([
      generationQuery,
      researchQuery,
      reviewQuery,
    ]);
    if (
      generationResult.error || researchResult.error || reviewResult.error ||
      !Array.isArray(generationResult.data) ||
      !Array.isArray(researchResult.data) ||
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

    const generationRows = generationResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.requested_by)
    ).map((row) => ({
      ...row,
      recipient_id: row.requested_by,
    }));
    const researchRows = researchResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.created_by)
    ).map((row) => ({
      ...row,
      recipient_id: row.created_by,
    }));
    const reviewRows = reviewResult.data.filter((row) =>
      isQueueRow(row, true) && isUuid(row.media_object_id) &&
      isUuid(row.requested_by)
    ).map((row) => ({
      ...row,
      recipient_id: row.requested_by,
    }));

    let mediaRows: MediaRow[] = [];
    const mediaIds = reviewRows.map((row) => row.media_object_id as string);
    if (mediaIds.length > 0 && payload.review_limit > 0) {
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
    const autonomousReviews = reviewRows.filter((row) => {
      const media = mediaById.get(row.media_object_id as string);
      return media?.status === "ready" && IMAGE_MIME_TYPES.has(media.mime_type);
    }).slice(0, payload.review_limit);
    const skippedVideoReviews = reviewRows.filter((row) => {
      const media = mediaById.get(row.media_object_id as string);
      return media?.status === "ready" && media.mime_type === "video/mp4";
    }).length;

    const targets: DispatchTarget[] = [
      ...generationRows.map((row): DispatchTarget => ({
        kind: "generation",
        functionName: "creator-generate",
        body: {
          action: "status",
          organization_id: row.organization_id as string,
          job_id: row.id,
        },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
      ...researchRows.map((row): DispatchTarget => ({
        kind: "research",
        functionName: "creator-product-research",
        body: { action: "analyze", research_id: row.id },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
      ...autonomousReviews.map((row): DispatchTarget => ({
        kind: "review",
        functionName: "creator-content-review",
        body: { action: "analyze", review_id: row.id, frames: [] },
        organizationId: row.organization_id as string,
        recipientId: row.recipient_id as string,
        entityId: row.id,
      })),
    ];

    if (!(await heartbeatBackgroundWorker(supabaseAdmin, workerRun))) {
      await finishBackgroundWorker(
        supabaseAdmin,
        workerRun,
        "failed",
        { stage: "before_dispatch" },
        "worker_heartbeat_failed",
      );
      return json({ ok: false, code: "worker_heartbeat_failed" }, 503);
    }
    const outcomes = await Promise.all(
      targets.map((target) => dispatch(target, origin, serviceKey, secret)),
    );
    const pollRecords = await recordGenerationPollOutcomes(
      supabaseAdmin,
      workerRun,
      outcomes,
    );
    const kinds: DispatchKind[] = ["generation", "research", "review"];
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
      skipped_video_reviews: skippedVideoReviews,
      expired_leases: {
        research: reconciliation.research,
        review: reconciliation.review,
      },
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
    const notification = await deliverNotificationOutbox(supabaseAdmin);
    const hasFailure = Object.values(failed).some((count) => count > 0) ||
      pollRecords.failed > 0 || !notification.ok;
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
