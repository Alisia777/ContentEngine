import { withSupabase } from "npm:@supabase/server@1.3.0";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const RUNWAY_API_ORIGIN = "https://api.dev.runwayml.com";
const RUNWAY_API_VERSION = "2024-11-06";
const RUNWAY_OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net";
const STORAGE_BUCKET = "contentengine-private";
const MAX_BODY_BYTES = 16_384;
const MAX_PROVIDER_JSON_BYTES = 65_536;
const MAX_OUTPUT_BYTES = 52_428_800;
const INPUT_URL_TTL_SECONDS = 3_600;
const OUTPUT_URL_TTL_SECONDS = 300;
const PROVIDER_TIMEOUT_MS = 20_000;
const MIN_PROVIDER_POLL_INTERVAL_MS = 5_000;
const OUTPUT_TIMEOUT_MS = 120_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/u;
const GEN4_RATIOS = new Set(["1280:720", "720:1280", "960:960"]);
const SEEDANCE_FAST_RATIO = "720:1280";
const DEFINITIVE_CREATE_HTTP_STATUSES = new Set([
  400,
  401,
  402,
  403,
  404,
  405,
  422,
  429,
]);
const JOB_STATUSES = new Set([
  "queued",
  "starting",
  "submitted",
  "processing",
  "succeeded",
  "failed",
]);
const FAILURE_CODES = new Set([
  "provider_configuration_error",
  "provider_authentication_failed",
  "provider_credits_unavailable",
  "provider_rate_limited",
  "provider_request_rejected",
  "provider_request_failed",
  "provider_task_failed",
  "provider_timeout",
  "provider_response_invalid",
  "output_download_failed",
  "output_validation_failed",
  "output_upload_failed",
  "internal_error",
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
      creator_start_real_generation: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_real_generation_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_update_real_generation: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

type CommonStartPayload = {
  action: "start";
  organization_id: string;
  idempotency_key: string;
  sku: string;
  product_name: string;
  count: 1;
  format: "9:16" | "1:1" | "16:9";
  brief: string;
  media_ids: [string];
  platform:
    | "instagram"
    | "tiktok"
    | "youtube"
    | "vk"
    | "telegram"
    | "wildberries";
  destination_ref: string;
  assignee_id?: string;
  payout_minor?: number;
  mode: "real";
  provider: "runway";
  allow_real_spend: true;
};

type StartPayload =
  & CommonStartPayload
  & (
    | {
      model: "gen4_turbo";
      duration_seconds: 5;
      audio?: false;
      spend_confirmation: "RUNWAY_GEN4_TURBO_5S_USD_0.25";
    }
    | {
      model: "seedance2_fast";
      duration_seconds: 8;
      audio: true;
      format: "9:16";
      spend_confirmation: "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32";
    }
  );

type StatusPayload = {
  action: "status";
  organization_id: string;
  job_id: string;
};

type StartJob = {
  id: string;
  batchId: string;
  status: string;
  provider: "runway";
  model: "gen4_turbo" | "seedance2_fast";
  durationSeconds: 5 | 8;
  audio: boolean;
  ratio: string;
  promptText: string;
  inputObjectName: string;
  outputObjectName: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
};

type StatusJob = {
  id: string;
  batchId: string;
  status: string;
  provider: "runway";
  providerTaskId: string | null;
  model: "gen4_turbo" | "seedance2_fast";
  durationSeconds: 5 | 8;
  audio: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
  actualCostMinor: number | null;
  outputObjectName: string;
  outputMediaId: string | null;
  failureCode: string | null;
  updatedAt: string;
};

type SafeJob = {
  id: string;
  batch_id: string;
  status: string;
  provider: "runway";
  provider_task_id: string | null;
  model: "gen4_turbo" | "seedance2_fast";
  duration_seconds: 5 | 8;
  audio: boolean;
  ratio: string;
  estimated_cost_minor: number;
  estimated_credits: number;
  actual_cost_minor: number | null;
  output_object_name: string;
  output_media_id: string | null;
  failure_code: string | null;
  updated_at: string;
};

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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
): boolean {
  return Object.keys(value).every((key) => allowed.has(key));
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isIntegerInRange(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return Number.isSafeInteger(value) &&
    (value as number) >= minimum && (value as number) <= maximum;
}

function hasForbiddenControl(
  value: string,
  allowTextWhitespace: boolean,
): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code === 0x7f) return true;
    if (code <= 0x1f) {
      const allowed = allowTextWhitespace &&
        (code === 0x09 || code === 0x0a || code === 0x0d);
      if (!allowed) return true;
    }
  }
  return false;
}

function isBoundedText(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return typeof value === "string" && value === value.trim() &&
    value.length >= minimum && value.length <= maximum &&
    !hasForbiddenControl(value, true);
}

function isObjectName(value: unknown): value is string {
  if (!isBoundedText(value, 3, 1_024)) return false;
  if (value.startsWith("/") || value.endsWith("/")) return false;
  if (value.includes("?") || value.includes("#") || value.includes("\\")) {
    return false;
  }
  return value.split("/").every((part) =>
    part.length > 0 && part !== "." && part !== ".."
  );
}

function readStartPayload(value: unknown): StartPayload | null {
  if (!isRecord(value)) return null;
  const required = new Set([
    "action",
    "organization_id",
    "idempotency_key",
    "sku",
    "product_name",
    "count",
    "format",
    "brief",
    "media_ids",
    "platform",
    "destination_ref",
    "mode",
    "provider",
    "model",
    "duration_seconds",
    "allow_real_spend",
    "spend_confirmation",
  ]);
  const allowed = new Set([
    ...required,
    "audio",
    "assignee_id",
    "payout_minor",
  ]);
  if (!hasOnlyKeys(value, allowed)) return null;
  if (![...required].every((key) => Object.hasOwn(value, key))) return null;

  const mediaIds = value.media_ids;
  const gen4Sku = value.model === "gen4_turbo" &&
    value.duration_seconds === 5 &&
    (!Object.hasOwn(value, "audio") || value.audio === false) &&
    value.spend_confirmation === "RUNWAY_GEN4_TURBO_5S_USD_0.25";
  const seedanceSku = value.model === "seedance2_fast" &&
    value.duration_seconds === 8 && value.audio === true &&
    value.format === "9:16" &&
    value.spend_confirmation ===
      "RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32";
  if (
    !Array.isArray(mediaIds) || mediaIds.length !== 1 ||
    !isUuid(mediaIds[0])
  ) {
    return null;
  }
  const formats = new Set(["9:16", "1:1", "16:9"]);
  const platforms = new Set([
    "instagram",
    "tiktok",
    "youtube",
    "vk",
    "telegram",
    "wildberries",
  ]);
  if (
    value.action !== "start" ||
    !isUuid(value.organization_id) ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    !isBoundedText(value.sku, 1, 120) ||
    !isBoundedText(value.product_name, 2, 180) ||
    value.count !== 1 ||
    typeof value.format !== "string" || !formats.has(value.format) ||
    !isBoundedText(value.brief, 1, 1_200) ||
    typeof value.platform !== "string" || !platforms.has(value.platform) ||
    !isBoundedText(value.destination_ref, 2, 240) ||
    value.mode !== "real" || value.provider !== "runway" ||
    value.allow_real_spend !== true || (!gen4Sku && !seedanceSku)
  ) {
    return null;
  }
  if (Object.hasOwn(value, "assignee_id") && !isUuid(value.assignee_id)) {
    return null;
  }
  if (
    Object.hasOwn(value, "payout_minor") &&
    !isIntegerInRange(value.payout_minor, 0, 1_000_000)
  ) {
    return null;
  }
  return value as StartPayload;
}

function readStatusPayload(value: unknown): StatusPayload | null {
  if (!isRecord(value)) return null;
  const allowed = new Set(["action", "organization_id", "job_id"]);
  if (!hasOnlyKeys(value, allowed) || Object.keys(value).length !== 3) {
    return null;
  }
  if (
    value.action !== "status" || !isUuid(value.organization_id) ||
    !isUuid(value.job_id)
  ) {
    return null;
  }
  return value as StatusPayload;
}

function rpcPayload(payload: StartPayload | StatusPayload): Json {
  const { action: _action, ...rest } = payload;
  return rest as Json;
}

function readRunwaySku(job: Record<string, unknown>): {
  model: "gen4_turbo" | "seedance2_fast";
  durationSeconds: 5 | 8;
  audio: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
} | null {
  if (
    job.model === "gen4_turbo" && job.duration_seconds === 5 &&
    job.audio === false && typeof job.ratio === "string" &&
    GEN4_RATIOS.has(job.ratio) && job.estimated_cost_minor === 25 &&
    job.estimated_credits === 25
  ) {
    return {
      model: "gen4_turbo",
      durationSeconds: 5,
      audio: false,
      ratio: job.ratio,
      estimatedCostMinor: 25,
      estimatedCredits: 25,
    };
  }
  if (
    job.model === "seedance2_fast" && job.duration_seconds === 8 &&
    job.audio === true && job.ratio === SEEDANCE_FAST_RATIO &&
    job.estimated_cost_minor === 232 && job.estimated_credits === 232
  ) {
    return {
      model: "seedance2_fast",
      durationSeconds: 8,
      audio: true,
      ratio: SEEDANCE_FAST_RATIO,
      estimatedCostMinor: 232,
      estimatedCredits: 232,
    };
  }
  return null;
}

function readStartJob(value: unknown): StartJob | null {
  if (!isRecord(value)) return null;
  const batch = value.batch;
  const job = value.job;
  if (value.ok !== true || !isRecord(batch) || !isRecord(job)) return null;
  if (!isUuid(batch.id) || typeof batch.status !== "string") return null;
  const sku = readRunwaySku(job);
  if (
    !isUuid(job.id) || !isUuid(job.batch_id) || job.batch_id !== batch.id ||
    typeof job.status !== "string" || !JOB_STATUSES.has(job.status) ||
    job.provider !== "runway" || sku === null ||
    !isBoundedText(job.prompt_text, 1, 1_200) ||
    !isObjectName(job.input_object_name) ||
    !isObjectName(job.output_object_name) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    !isIntegerInRange(job.estimated_credits, 0, 1_000_000)
  ) {
    return null;
  }
  return {
    id: job.id,
    batchId: job.batch_id,
    status: job.status,
    provider: "runway",
    model: sku.model,
    durationSeconds: sku.durationSeconds,
    audio: sku.audio,
    ratio: sku.ratio,
    promptText: job.prompt_text,
    inputObjectName: job.input_object_name,
    outputObjectName: job.output_object_name,
    estimatedCostMinor: sku.estimatedCostMinor,
    estimatedCredits: sku.estimatedCredits,
  };
}

function readStatusJob(value: unknown): StatusJob | null {
  if (!isRecord(value) || value.ok !== true || !isRecord(value.job)) {
    return null;
  }
  const job = value.job;
  const providerTaskId = job.provider_task_id;
  const actualCostMinor = job.actual_cost_minor;
  const outputMediaId = job.output_media_id;
  const failureCode = job.failure_code;
  const sku = readRunwaySku(job);
  if (
    !isUuid(job.id) || !isUuid(job.batch_id) ||
    typeof job.status !== "string" || !JOB_STATUSES.has(job.status) ||
    job.provider !== "runway" || sku === null ||
    (providerTaskId !== null && !isValidTaskId(providerTaskId)) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    !isIntegerInRange(job.estimated_credits, 0, 1_000_000) ||
    (actualCostMinor !== null &&
      !isIntegerInRange(actualCostMinor, 0, 1_000_000)) ||
    !isObjectName(job.output_object_name) ||
    (outputMediaId !== null && !isUuid(outputMediaId)) ||
    (failureCode !== null &&
      (typeof failureCode !== "string" || !FAILURE_CODES.has(failureCode))) ||
    typeof job.updated_at !== "string" ||
    !Number.isFinite(Date.parse(job.updated_at))
  ) {
    return null;
  }
  return {
    id: job.id,
    batchId: job.batch_id,
    status: job.status,
    provider: "runway",
    providerTaskId,
    model: sku.model,
    durationSeconds: sku.durationSeconds,
    audio: sku.audio,
    ratio: sku.ratio,
    estimatedCostMinor: sku.estimatedCostMinor,
    estimatedCredits: sku.estimatedCredits,
    actualCostMinor,
    outputObjectName: job.output_object_name,
    outputMediaId,
    failureCode,
    updatedAt: job.updated_at,
  };
}

function safeJob(job: StatusJob): SafeJob {
  return {
    id: job.id,
    batch_id: job.batchId,
    status: job.status,
    provider: job.provider,
    provider_task_id: job.providerTaskId,
    model: job.model,
    duration_seconds: job.durationSeconds,
    audio: job.audio,
    ratio: job.ratio,
    estimated_cost_minor: job.estimatedCostMinor,
    estimated_credits: job.estimatedCredits,
    actual_cost_minor: job.actualCostMinor,
    output_object_name: job.outputObjectName,
    output_media_id: job.outputMediaId,
    failure_code: job.failureCode,
    updated_at: job.updatedAt,
  };
}

function isValidTaskId(value: unknown): value is string {
  return typeof value === "string" && TASK_ID_PATTERN.test(value);
}

function runwaySecret(): string | null {
  const value = Deno.env.get("RUNWAYML_API_SECRET") ?? "";
  if (
    value.length < 16 || value.length > 512 || value !== value.trim() ||
    hasForbiddenControl(value, false)
  ) {
    return null;
  }
  return value;
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

async function readBoundedBytes(
  response: Response,
  maximum: number,
): Promise<Uint8Array<ArrayBuffer>> {
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const size = Number(declared);
    if (!Number.isSafeInteger(size) || size < 0 || size > maximum) {
      throw new Error("response_size_invalid");
    }
  }
  return await readBoundedStream(response.body, maximum);
}

async function readBoundedStream(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
): Promise<Uint8Array<ArrayBuffer>> {
  if (body === null) throw new Error("response_body_missing");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new Error("response_size_invalid");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const output = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

async function readProviderJson(response: Response): Promise<unknown> {
  const bytes = await readBoundedBytes(response, MAX_PROVIDER_JSON_BYTES);
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("provider_response_invalid");
  }
}

function providerFailureForHttp(status: number): string {
  if (status === 401 || status === 403) {
    return "provider_authentication_failed";
  }
  if (status === 402) return "provider_credits_unavailable";
  if (status === 429) return "provider_rate_limited";
  if (status >= 400 && status < 500) return "provider_request_rejected";
  return "provider_request_failed";
}

function providerTaskFailure(value: unknown): string {
  if (!isRecord(value) || typeof value.failureCode !== "string") {
    return "provider_task_failed";
  }
  const code = value.failureCode.toLocaleUpperCase("en-US");
  if (code.includes("CREDITS") || code.includes("PAYMENT")) {
    return "provider_credits_unavailable";
  }
  if (code.includes("RATE_LIMIT")) return "provider_rate_limited";
  return "provider_task_failed";
}

function isMp4(bytes: Uint8Array): boolean {
  return bytes.byteLength >= 12 && bytes[4] === 0x66 && bytes[5] === 0x74 &&
    bytes[6] === 0x79 && bytes[7] === 0x70;
}

async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) =>
    value.toString(16).padStart(2, "0")
  ).join("");
}

function validateRunwayOutputUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2_048) return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" || url.hostname !== RUNWAY_OUTPUT_HOST ||
      (url.port !== "" && url.port !== "443") || url.username !== "" ||
      url.password !== ""
    ) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function validateSupabaseSignedUrl(value: unknown): string | null {
  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  if (typeof value !== "string" || value.length > 4_096) return null;
  try {
    const expected = new URL(supabaseUrl);
    const actual = new URL(value);
    if (
      expected.protocol !== "https:" || actual.protocol !== "https:" ||
      actual.origin !== expected.origin || actual.username !== "" ||
      actual.password !== "" ||
      !actual.pathname.startsWith(
        `/storage/v1/object/sign/${STORAGE_BUCKET}/`,
      )
    ) {
      return null;
    }
    return actual.href;
  } catch {
    return null;
  }
}

function parseRunwayTask(
  value: unknown,
): { id: string; status: string } | null {
  if (
    !isRecord(value) || !isValidTaskId(value.id) ||
    typeof value.status !== "string"
  ) {
    return null;
  }
  return { id: value.id, status: value.status };
}

function parseCreatedRunwayTask(value: unknown): { id: string } | null {
  if (!isRecord(value) || !isValidTaskId(value.id)) return null;
  return { id: value.id };
}

const creatorGenerate = withSupabase<ContentEngineDatabase>({
  auth: "user",
  cors: {
    "Access-Control-Allow-Headers":
      "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Origin": PUBLIC_APP_ORIGIN,
    Vary: "Origin",
  },
}, async (request, context) => {
  if (request.method !== "POST") {
    return json(request, { ok: false, code: "method_not_allowed" }, 405);
  }
  if (request.headers.get("origin") !== PUBLIC_APP_ORIGIN) {
    return json(request, { ok: false, code: "origin_not_allowed" }, 403);
  }
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLocaleLowerCase("en-US").startsWith("application/json")) {
    return json(request, { ok: false, code: "content_type_invalid" }, 415);
  }
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  if (!context.userClaims?.id) {
    return json(request, { ok: false, code: "authentication_required" }, 401);
  }

  let bodyText: string;
  try {
    const bodyBytes = await readBoundedStream(request.body, MAX_BODY_BYTES);
    bodyText = new TextDecoder("utf-8", { fatal: true }).decode(bodyBytes);
  } catch {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  let body: unknown;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }

  const readCurrentStatus = async (
    organizationId: string,
    jobId: string,
  ): Promise<StatusJob | null> => {
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_real_generation_status",
        { p_payload: { organization_id: organizationId, job_id: jobId } },
      );
      if (error) return null;
      const job = readStatusJob(data);
      if (job === null || job.id !== jobId) return null;
      return job;
    } catch {
      return null;
    }
  };

  const updateSystemJob = async (
    payload: Record<string, Json>,
  ): Promise<Json | null> => {
    try {
      const { data, error } = await context.supabaseAdmin.rpc(
        "system_update_real_generation",
        { p_payload: payload },
      );
      return error ? null : data;
    } catch {
      return null;
    }
  };

  const markFailed = async (
    jobId: string,
    failureCode: string,
    providerTaskId?: string,
  ) => {
    const safeCode = FAILURE_CODES.has(failureCode)
      ? failureCode
      : "internal_error";
    const failurePayload: Record<string, Json> = {
      job_id: jobId,
      status: "failed",
      failure_code: safeCode,
    };
    if (isValidTaskId(providerTaskId)) {
      failurePayload.provider_task_id = providerTaskId;
    }
    await updateSystemJob(failurePayload);
  };

  const signOutput = async (job: StatusJob): Promise<string | null> => {
    try {
      const { data, error } = await context.supabaseAdmin.storage.from(
        STORAGE_BUCKET,
      ).createSignedUrl(job.outputObjectName, OUTPUT_URL_TTL_SECONDS);
      if (error || data === null) return null;
      return validateSupabaseSignedUrl(data.signedUrl);
    } catch {
      return null;
    }
  };

  const respondWithCurrent = async (
    organizationId: string,
    jobId: string,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    const current = await readCurrentStatus(organizationId, jobId);
    if (current === null) {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    const signedUrl = current.status === "succeeded"
      ? await signOutput(current)
      : null;
    return json(request, {
      ok: true,
      ...(batch ? { batch } : {}),
      job: safeJob(current),
      ...(signedUrl ? { signed_url: signedUrl } : {}),
    });
  };

  const respondProviderUnavailable = async (
    organizationId: string,
    jobId: string,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    const current = await readCurrentStatus(organizationId, jobId);
    return json(request, {
      ok: false,
      code: "provider_unavailable",
      ...(batch ? { batch } : {}),
      ...(current ? { job: safeJob(current) } : {}),
    }, 503);
  };

  const handleStatus = async (
    payload: StatusPayload,
    currentOverride?: StatusJob,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    let current = currentOverride ?? await readCurrentStatus(
      payload.organization_id,
      payload.job_id,
    );
    if (current === null) {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    if (current.status === "succeeded") {
      const signedUrl = await signOutput(current);
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
        ...(signedUrl ? { signed_url: signedUrl } : {}),
      });
    }
    if (current.status === "failed" || current.status === "queued") {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (current.status === "starting") {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (!isValidTaskId(current.providerTaskId)) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (
      Date.now() - Date.parse(current.updatedAt) < MIN_PROVIDER_POLL_INTERVAL_MS
    ) {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    const secret = runwaySecret();
    if (secret === null) {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerResponse: Response;
    try {
      providerResponse = await fetchWithTimeout(
        `${RUNWAY_API_ORIGIN}/v1/tasks/${current.providerTaskId}`,
        {
          method: "GET",
          redirect: "manual",
          headers: {
            authorization: `Bearer ${secret}`,
            "x-runway-version": RUNWAY_API_VERSION,
          },
        },
        PROVIDER_TIMEOUT_MS,
      );
    } catch {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }
    if (!providerResponse.ok) {
      await providerResponse.body?.cancel();
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerValue: unknown;
    try {
      providerValue = await readProviderJson(providerResponse);
    } catch {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    const providerTask = parseRunwayTask(providerValue);
    if (providerTask === null || providerTask.id !== current.providerTaskId) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (
      providerTask.status === "PENDING" || providerTask.status === "THROTTLED"
    ) {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (providerTask.status === "RUNNING") {
      const processing = await updateSystemJob({
        job_id: current.id,
        provider_task_id: current.providerTaskId,
        status: "processing",
      });
      if (processing === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      return await respondWithCurrent(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (
      providerTask.status === "FAILED" ||
      providerTask.status === "CANCELED" ||
      providerTask.status === "CANCELLED"
    ) {
      await markFailed(
        current.id,
        providerTaskFailure(providerValue),
        current.providerTaskId,
      );
      return await respondWithCurrent(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (
      providerTask.status !== "SUCCEEDED" || !isRecord(providerValue) ||
      !Array.isArray(providerValue.output)
    ) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (current.status === "submitted") {
      const processing = await updateSystemJob({
        job_id: current.id,
        provider_task_id: current.providerTaskId,
        status: "processing",
      });
      if (processing === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      const refreshed = await readCurrentStatus(
        payload.organization_id,
        payload.job_id,
      );
      if (refreshed === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      if (refreshed.status === "succeeded" || refreshed.status === "failed") {
        return await respondWithCurrent(
          payload.organization_id,
          payload.job_id,
          batch,
        );
      }
      if (
        refreshed.status !== "processing" ||
        refreshed.providerTaskId !== current.providerTaskId
      ) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(refreshed),
        }, 503);
      }
      current = refreshed;
    }
    const outputUrl = validateRunwayOutputUrl(providerValue.output[0]);
    if (outputUrl === null) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }

    let outputBytes: Uint8Array<ArrayBuffer>;
    try {
      const outputResponse = await fetchWithTimeout(
        outputUrl,
        { method: "GET", redirect: "manual" },
        OUTPUT_TIMEOUT_MS,
      );
      const mimeType = (outputResponse.headers.get("content-type") ?? "")
        .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
      if (
        !outputResponse.ok ||
        !new Set(["video/mp4", "application/mp4"]).has(mimeType)
      ) {
        await outputResponse.body?.cancel();
        return await respondProviderUnavailable(
          payload.organization_id,
          payload.job_id,
          batch,
        );
      }
      outputBytes = await readBoundedBytes(outputResponse, MAX_OUTPUT_BYTES);
    } catch {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (!isMp4(outputBytes)) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    const digest = await sha256Hex(outputBytes);
    const storage = context.supabaseAdmin.storage.from(STORAGE_BUCKET);
    const { error: uploadError } = await storage.upload(
      current.outputObjectName,
      outputBytes,
      {
        cacheControl: "31536000",
        contentType: "video/mp4",
        upsert: true,
        metadata: { sha256: digest },
      },
    );
    if (uploadError) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }

    const completed = await updateSystemJob({
      job_id: current.id,
      provider_task_id: current.providerTaskId,
      status: "succeeded",
      output_object_name: current.outputObjectName,
      mime_type: "video/mp4",
      size_bytes: outputBytes.byteLength,
      sha256: digest,
    });
    if (completed === null) {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    current = await readCurrentStatus(payload.organization_id, payload.job_id);
    if (current === null || current.status !== "succeeded") {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    const signedUrl = await signOutput(current);
    return json(request, {
      ok: true,
      ...(batch ? { batch } : {}),
      job: safeJob(current),
      ...(signedUrl ? { signed_url: signedUrl } : {}),
    });
  };

  const statusPayload = readStatusPayload(body);
  if (statusPayload !== null) return await handleStatus(statusPayload);

  const startPayload = readStartPayload(body);
  if (startPayload === null) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }
  const { data: startData, error: startError } = await context.supabase.rpc(
    "creator_start_real_generation",
    { p_payload: rpcPayload(startPayload) },
  );
  const startJob = readStartJob(startData);
  if (startError || startJob === null) {
    return json(request, { ok: false, code: "generation_rejected" }, 403);
  }
  const startRecord = startData as Record<string, unknown>;
  const startBatch = startRecord.batch as Record<string, unknown>;
  const batch = {
    id: startBatch.id as string,
    status: startBatch.status as string,
  };
  const current = await readCurrentStatus(
    startPayload.organization_id,
    startJob.id,
  );
  if (
    current === null || current.batchId !== startJob.batchId ||
    current.outputObjectName !== startJob.outputObjectName
  ) {
    return json(request, { ok: false, code: "generation_unavailable" }, 503);
  }
  const statusRequest: StatusPayload = {
    action: "status",
    organization_id: startPayload.organization_id,
    job_id: startJob.id,
  };
  if (current.status !== "queued") {
    return await handleStatus(statusRequest, current, batch);
  }

  const claimValue = await updateSystemJob({
    job_id: current.id,
    status: "starting",
  });
  if (
    !isRecord(claimValue) || claimValue.ok !== true ||
    typeof claimValue.claimed !== "boolean"
  ) {
    return json(request, { ok: false, code: "generation_unavailable" }, 503);
  }
  if (!claimValue.claimed) {
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }

  const secret = runwaySecret();
  if (secret === null) {
    await markFailed(startJob.id, "provider_configuration_error");
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const { data: signedInputData, error: signedInputError } = await context
    .supabaseAdmin.storage.from(STORAGE_BUCKET).createSignedUrl(
      startJob.inputObjectName,
      INPUT_URL_TTL_SECONDS,
    );
  const signedInputUrl = signedInputError
    ? null
    : validateSupabaseSignedUrl(signedInputData?.signedUrl);
  if (signedInputUrl === null) {
    await markFailed(startJob.id, "provider_configuration_error");
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }

  const providerRequestBody = startJob.model === "seedance2_fast"
    ? {
      model: startJob.model,
      duration: startJob.durationSeconds,
      ratio: startJob.ratio,
      promptText: startJob.promptText,
      promptImage: [{ uri: signedInputUrl }],
      audio: true,
    }
    : {
      model: startJob.model,
      duration: startJob.durationSeconds,
      ratio: startJob.ratio,
      promptText: startJob.promptText,
      promptImage: signedInputUrl,
    };

  let createResponse: Response;
  try {
    createResponse = await fetchWithTimeout(
      `${RUNWAY_API_ORIGIN}/v1/image_to_video`,
      {
        method: "POST",
        redirect: "manual",
        headers: {
          authorization: `Bearer ${secret}`,
          "content-type": "application/json",
          "x-runway-version": RUNWAY_API_VERSION,
        },
        body: JSON.stringify(providerRequestBody),
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch {
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  if (!createResponse.ok) {
    await createResponse.body?.cancel();
    if (DEFINITIVE_CREATE_HTTP_STATUSES.has(createResponse.status)) {
      await markFailed(
        startJob.id,
        providerFailureForHttp(createResponse.status),
      );
      return await respondWithCurrent(
        startPayload.organization_id,
        startJob.id,
        batch,
      );
    }
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }

  let createdValue: unknown;
  try {
    createdValue = await readProviderJson(createResponse);
  } catch {
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const providerTask = parseCreatedRunwayTask(createdValue);
  if (providerTask === null) {
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const submittedPayload: Record<string, Json> = {
    job_id: startJob.id,
    provider_task_id: providerTask.id,
    status: "submitted",
  };
  let submitted = await updateSystemJob(submittedPayload);
  if (submitted === null) {
    // Replaying the exact provider task id is safe and closes the common
    // response-loss window without ever issuing another paid provider call.
    submitted = await updateSystemJob(submittedPayload);
  }
  if (submitted === null) {
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  return await respondWithCurrent(
    startPayload.organization_id,
    startJob.id,
    batch,
  );
});

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
    return creatorGenerate(request);
  },
};
