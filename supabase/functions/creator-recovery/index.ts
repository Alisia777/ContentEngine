import { withSupabase } from "npm:@supabase/server@1.3.0";

const PUBLIC_APP_URL = new URL("https://alisia777.github.io/ContentEngine/");
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const RECOVERY_REDIRECT_URL = new URL("?auth=recovery", PUBLIC_APP_URL).href;
const MAX_BODY_BYTES = 4_096;
const PROVIDER_TIMEOUT_MS = 15_000;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const RECEIPT_TOKEN_PATTERN = /^rr1_[A-Za-z0-9_-]{43}$/u;
const PUBLIC_ACCEPTED_MESSAGE =
  "\u0415\u0441\u043b\u0438 \u0430\u0434\u0440\u0435\u0441 \u0437\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u043d, \u0437\u0430\u043f\u0440\u043e\u0441 \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f \u043f\u0440\u0438\u043d\u044f\u0442. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0432\u0445\u043e\u0434\u044f\u0449\u0438\u0435 \u0438 \u043f\u0430\u043f\u043a\u0443 \u00ab\u0421\u043f\u0430\u043c\u00bb.";

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
      system_reserve_public_recovery_receipt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_finalize_public_recovery_receipt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_read_public_recovery_receipt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

function responseHeaders(request: Request): Headers {
  const origin = request.headers.get("origin") ?? "";
  const headers = new Headers({
    "access-control-allow-headers":
      "authorization, apikey, content-type, x-client-info",
    "access-control-allow-methods": "POST, OPTIONS",
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    vary: "Origin",
    "x-content-type-options": "nosniff",
  });
  if (origin === PUBLIC_APP_ORIGIN) {
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

function stringOrNull(value: unknown, maxLength = 256): string | null {
  if (
    typeof value !== "string" || value.length < 1 || value.length > maxLength
  ) {
    return null;
  }
  return value;
}

function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLocaleLowerCase("en-US");
  if (email.length < 3 || email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return null;
  }
  return email;
}

function numberOr(value: unknown, fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(0, Math.ceil(value));
}

function receiptProjection(
  value: Record<string, unknown>,
  fallbackRetryAfter: number,
): {
  status: "accepted" | "failed" | "provider_outcome_unknown";
  requested_at: string | null;
  retry_not_before: string | null;
  retry_after_seconds: number;
  expires_at: string | null;
  delivery_confirmed: false;
} {
  const rawStatus = stringOrNull(value.status, 64);
  const status = rawStatus === "accepted" || rawStatus === "failed" ||
      rawStatus === "provider_outcome_unknown"
    ? rawStatus
    : "provider_outcome_unknown";
  return {
    status,
    requested_at: stringOrNull(value.requested_at, 64),
    retry_not_before: stringOrNull(value.retry_not_before, 64),
    retry_after_seconds: numberOr(
      value.retry_after_seconds,
      fallbackRetryAfter,
    ),
    expires_at: stringOrNull(value.expires_at, 64),
    delivery_confirmed: false,
  };
}

async function readBoundedStream(
  stream: ReadableStream<Uint8Array> | null,
  limit: number,
): Promise<Uint8Array> {
  if (stream === null) return new Uint8Array();
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) throw new RangeError("request_too_large");
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

function validSupabaseOrigin(value: string): string | null {
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" || url.username !== "" ||
      url.password !== "" || url.search !== "" || url.hash !== ""
    ) {
      return null;
    }
    return url.origin;
  } catch {
    return null;
  }
}

function configuration(): {
  origin: string;
  anonKey: string;
  serviceRoleKey: string;
} | null {
  const origin = validSupabaseOrigin(Deno.env.get("SUPABASE_URL") ?? "");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")?.trim() ?? "";
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")?.trim() ??
    "";
  if (
    origin === null || anonKey.length < 32 || anonKey.length > 4_096 ||
    serviceRoleKey.length < 32 || serviceRoleKey.length > 4_096
  ) {
    return null;
  }
  return { origin, anonKey, serviceRoleKey };
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_")
    .replaceAll("=", "");
}

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function hashReceiptToken(token: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(token),
  );
  return hex(new Uint8Array(digest));
}

async function receiptMaterial(
  requestId: string,
  serviceRoleKey: string,
): Promise<{ token: string; hash: string }> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(serviceRoleKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`contentengine-recovery-receipt:v1:${requestId}`),
  );
  const token = `rr1_${base64Url(new Uint8Array(signature))}`;
  return { token, hash: await hashReceiptToken(token) };
}

async function fetchWithTimeout(
  input: string,
  init: RequestInit,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROVIDER_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

const creatorRecovery = withSupabase<ContentEngineDatabase>({
  auth: "none",
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
  const requestOrigin = request.headers.get("origin");
  if (requestOrigin && requestOrigin !== PUBLIC_APP_ORIGIN) {
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

  let bodyBytes: Uint8Array;
  try {
    bodyBytes = await readBoundedStream(request.body, MAX_BODY_BYTES);
  } catch {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  let payload: unknown;
  try {
    payload = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(bodyBytes),
    );
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }
  if (!isRecord(payload)) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }

  const runtime = configuration();
  if (runtime === null) {
    return json(request, { ok: false, code: "recovery_unavailable" }, 503);
  }
  const action = payload.action;

  if (action === "status") {
    const allowedKeys = new Set(["action", "receipt_token"]);
    if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
      return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
    }
    const receiptToken = stringOrNull(payload.receipt_token, 128);
    if (receiptToken === null || !RECEIPT_TOKEN_PATTERN.test(receiptToken)) {
      return json(request, { ok: false, code: "receipt_invalid" }, 400);
    }
    const receiptHash = await hashReceiptToken(receiptToken);
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_read_public_recovery_receipt",
      { p_payload: { receipt_hash: receiptHash } },
    );
    if (error || !isRecord(data)) {
      return json(request, { ok: false, code: "recovery_unavailable" }, 503);
    }
    if (data.found !== true) {
      return json(request, { ok: false, code: "receipt_not_found" }, 404);
    }
    return json(request, {
      ok: true,
      accepted: true,
      action: "status",
      request_id: stringOrNull(data.request_id, 64),
      receipt_token: receiptToken,
      message: PUBLIC_ACCEPTED_MESSAGE,
      receipt: receiptProjection(data, 0),
    });
  }

  if (action !== "request") {
    return json(request, { ok: false, code: "action_invalid" }, 400);
  }
  const allowedKeys = new Set(["action", "email", "request_id"]);
  if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
    return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
  }
  const email = normalizeEmail(payload.email);
  const suppliedRequestId = stringOrNull(payload.request_id, 64);
  if (email === null) {
    return json(request, { ok: false, code: "email_invalid" }, 400);
  }
  if (suppliedRequestId === null || !UUID_PATTERN.test(suppliedRequestId)) {
    return json(request, { ok: false, code: "request_id_invalid" }, 400);
  }
  const requestId = suppliedRequestId.toLocaleLowerCase("en-US");

  const receipt = await receiptMaterial(requestId, runtime.serviceRoleKey);
  const { data: reserveData, error: reserveError } = await context.supabaseAdmin
    .rpc("system_reserve_public_recovery_receipt", {
      p_payload: {
        request_id: requestId,
        receipt_hash: receipt.hash,
        email,
      },
    });
  if (reserveError || !isRecord(reserveData)) {
    return json(request, { ok: false, code: "recovery_unavailable" }, 503);
  }

  if (reserveData.ok !== true) {
    return json(request, { ok: false, code: "recovery_unavailable" }, 503);
  }

  let receiptData: Record<string, unknown> = reserveData;
  let finalizeSucceeded = reserveData.dispatch_required !== true;
  if (reserveData.dispatch_required === true) {
    let finalStatus: "accepted" | "failed" | "provider_outcome_unknown";
    let reasonCode: string;
    try {
      const providerResponse = await fetchWithTimeout(
        `${runtime.origin}/auth/v1/recover?redirect_to=${
          encodeURIComponent(RECOVERY_REDIRECT_URL)
        }`,
        {
          method: "POST",
          headers: {
            apikey: runtime.anonKey,
            authorization: `Bearer ${runtime.anonKey}`,
            "content-type": "application/json; charset=utf-8",
            "x-client-info": "contentengine-creator-recovery/1.0",
          },
          body: JSON.stringify({ email }),
        },
      );
      finalStatus = providerResponse.ok ? "accepted" : "failed";
      reasonCode = providerResponse.ok
        ? "recovery_request_accepted"
        : providerResponse.status === 429
        ? "email_rate_limited"
        : providerResponse.status >= 500
        ? "recovery_provider_unavailable"
        : "recovery_request_rejected";
    } catch {
      // The provider may have accepted the one-time operation before the
      // connection failed.  Never retry the POST for this request_id.
      finalStatus = "provider_outcome_unknown";
      reasonCode = "recovery_provider_outcome_unknown";
    }
    const { data: finalizeData, error: finalizeError } = await context
      .supabaseAdmin.rpc(
        "system_finalize_public_recovery_receipt",
        {
          p_payload: {
            request_id: requestId,
            receipt_hash: receipt.hash,
            status: finalStatus,
            reason_code: reasonCode,
          },
        },
      );
    finalizeSucceeded = finalizeError === null && isRecord(finalizeData) &&
      finalizeData.ok === true && finalizeData.found === true;
    if (!finalizeSucceeded) {
      receiptData = {
        ...reserveData,
        status: "provider_outcome_unknown",
      };
    }
  }

  const { data: statusData, error: statusError } = await context.supabaseAdmin
    .rpc("system_read_public_recovery_receipt", {
      p_payload: { receipt_hash: receipt.hash },
    });
  if (
    statusError === null && isRecord(statusData) && statusData.found === true
  ) {
    receiptData = statusData;
  } else if (!finalizeSucceeded) {
    receiptData = {
      ...receiptData,
      status: "provider_outcome_unknown",
    };
  }

  // This public projection is deliberately identical for a registered and an
  // unregistered address.  It is an acceptance receipt, never delivery proof.
  return json(request, {
    ok: true,
    accepted: true,
    action: "request",
    request_id: requestId,
    receipt_token: receipt.token,
    message: PUBLIC_ACCEPTED_MESSAGE,
    receipt: receiptProjection(receiptData, 600),
  }, 202);
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }
    return creatorRecovery(request);
  },
};
