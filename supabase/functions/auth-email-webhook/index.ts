import { withSupabase } from "npm:@supabase/server@1.3.0";

const MAX_BODY_BYTES = 262_144;
const MAX_SIGNATURE_HEADER_BYTES = 2_048;
const MAX_CLOCK_SKEW_SECONDS = 300;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;
const SVIX_ID_PATTERN = /^[A-Za-z0-9_-]{1,128}$/u;
const PROVIDER_MESSAGE_ID_PATTERN = /^[A-Za-z0-9._:-]{1,200}$/u;
const DELIVERY_EVENT_MAP = new Map<string, string>([
  ["email.sent", "accepted_unconfirmed"],
  ["email.delivered", "delivered"],
  ["email.delivery_delayed", "deferred"],
  ["email.failed", "failed"],
  ["email.bounced", "bounced"],
  ["email.suppressed", "suppressed"],
  ["email.complained", "complained"],
]);
const CORRELATION_STATUSES = new Set(["exact", "ambiguous", "unmatched"]);

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
      system_ingest_auth_email_delivery_event: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

type VerifiedSvixRequest = {
  providerEventId: string;
  timestamp: number;
};

function responseHeaders(): HeadersInit {
  return {
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "x-content-type-options": "nosniff",
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLocaleLowerCase("en-US");
  if (email.length < 3 || email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return null;
  }
  return email;
}

function parseEventTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64) return null;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return null;
  return new Date(timestamp).toISOString();
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

function decodeBase64(value: string): Uint8Array | null {
  try {
    const normalized = value.replaceAll("-", "+").replaceAll("_", "/");
    const padded = normalized.padEnd(
      normalized.length + ((4 - normalized.length % 4) % 4),
      "=",
    );
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  } catch {
    return null;
  }
}

function readSigningSecret(): Uint8Array | null {
  const configured = Deno.env.get("RESEND_WEBHOOK_SECRET")?.trim() ?? "";
  if (
    configured.length < 24 || configured.length > 512 ||
    !configured.startsWith("whsec_")
  ) {
    return null;
  }
  const decoded = decodeBase64(configured.slice("whsec_".length));
  if (decoded === null || decoded.byteLength < 16 || decoded.byteLength > 128) {
    return null;
  }
  return decoded;
}

function timingSafeEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.byteLength !== right.byteLength) return false;
  let difference = 0;
  for (let index = 0; index < left.byteLength; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

async function verifySvixSignature(
  request: Request,
  rawBody: Uint8Array,
): Promise<VerifiedSvixRequest | null> {
  const providerEventId = request.headers.get("svix-id") ?? "";
  const rawTimestamp = request.headers.get("svix-timestamp") ?? "";
  const rawSignatures = request.headers.get("svix-signature") ?? "";
  if (
    !SVIX_ID_PATTERN.test(providerEventId) ||
    rawTimestamp.length < 1 || rawTimestamp.length > 16 ||
    rawSignatures.length < 1 ||
    new TextEncoder().encode(rawSignatures).byteLength >
      MAX_SIGNATURE_HEADER_BYTES
  ) {
    return null;
  }
  const timestamp = Number(rawTimestamp);
  const now = Math.floor(Date.now() / 1_000);
  if (
    !Number.isSafeInteger(timestamp) ||
    Math.abs(now - timestamp) > MAX_CLOCK_SKEW_SECONDS
  ) {
    return null;
  }
  const secret = readSigningSecret();
  if (secret === null) return null;

  const prefix = new TextEncoder().encode(
    `${providerEventId}.${rawTimestamp}.`,
  );
  const signedContent = new Uint8Array(prefix.byteLength + rawBody.byteLength);
  signedContent.set(prefix, 0);
  signedContent.set(rawBody, prefix.byteLength);
  const keyBytes = Uint8Array.from(secret);
  const key = await crypto.subtle.importKey(
    "raw",
    keyBytes.buffer,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const expected = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, signedContent),
  );
  const candidates = rawSignatures
    .split(/\s+/u)
    .filter((entry) => entry.startsWith("v1,"))
    .map((entry) => decodeBase64(entry.slice(3)))
    .filter((entry): entry is Uint8Array => entry !== null);
  if (!candidates.some((candidate) => timingSafeEqual(expected, candidate))) {
    return null;
  }
  return { providerEventId, timestamp };
}

function eventRecipient(data: Record<string, unknown>): string | null {
  const values = Array.isArray(data.to) ? data.to : [data.to];
  const recipients = Array.from(
    new Set(values.flatMap((value) => {
      const email = normalizeEmail(value);
      return email === null ? [] : [email];
    })),
  );
  return recipients.length === 1 ? recipients[0] : null;
}

const authEmailWebhook = withSupabase<ContentEngineDatabase>({
  auth: "none",
  cors: false,
}, async (request, context) => {
  if (request.method !== "POST") {
    return json({ ok: false, code: "method_not_allowed" }, 405);
  }
  if (request.headers.get("origin") !== null) {
    return json({ ok: false, code: "origin_not_allowed" }, 403);
  }
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.toLocaleLowerCase("en-US").startsWith("application/json")) {
    return json({ ok: false, code: "content_type_invalid" }, 415);
  }
  if (readSigningSecret() === null) {
    return json({ ok: false, code: "webhook_not_configured" }, 503);
  }
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json({ ok: false, code: "request_too_large" }, 413);
  }

  let rawBody: Uint8Array;
  try {
    rawBody = await readBoundedStream(request.body, MAX_BODY_BYTES);
  } catch {
    return json({ ok: false, code: "request_too_large" }, 413);
  }
  const verified = await verifySvixSignature(request, rawBody);
  if (verified === null) {
    return json({ ok: false, code: "signature_invalid" }, 401);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(rawBody),
    );
  } catch {
    return json({ ok: false, code: "invalid_json" }, 400);
  }
  if (!isRecord(payload) || !isRecord(payload.data)) {
    return json({ ok: false, code: "event_invalid" }, 400);
  }
  const eventType = typeof payload.type === "string" ? payload.type : "";
  const deliveryStatus = DELIVERY_EVENT_MAP.get(eventType);
  if (deliveryStatus === undefined) {
    return json({ ok: true, ignored: true }, 202);
  }
  const providerMessageId = typeof payload.data.email_id === "string" &&
      PROVIDER_MESSAGE_ID_PATTERN.test(payload.data.email_id)
    ? payload.data.email_id
    : null;
  const recipient = eventRecipient(payload.data);
  const eventCreatedAt = parseEventTimestamp(payload.created_at);
  if (
    providerMessageId === null || recipient === null ||
    eventCreatedAt === null
  ) {
    return json({ ok: false, code: "event_fields_invalid" }, 400);
  }

  const { data, error } = await context.supabaseAdmin.rpc(
    "system_ingest_auth_email_delivery_event",
    {
      p_payload: {
        provider: "resend",
        provider_event_id: verified.providerEventId,
        provider_message_id: providerMessageId,
        event_type: eventType,
        delivery_status: deliveryStatus,
        recipient,
        event_created_at: eventCreatedAt,
      },
    },
  );
  if (error || !isRecord(data)) {
    return json({ ok: false, code: "delivery_event_store_failed" }, 503);
  }
  const correlationStatus = typeof data.correlation_status === "string" &&
      CORRELATION_STATUSES.has(data.correlation_status)
    ? data.correlation_status
    : "unmatched";
  return json({
    ok: true,
    inserted: data.inserted === true,
    correlation_status: correlationStatus,
    delivery_projected: data.delivery_projected === true,
  });
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    return authEmailWebhook(request);
  },
};
