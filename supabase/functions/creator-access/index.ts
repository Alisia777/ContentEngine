import { withSupabase } from "npm:@supabase/server@1.3.0";

const PUBLIC_APP_URL = new URL("https://alisia777.github.io/ContentEngine/");
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const RECOVERY_REDIRECT_URL = new URL(
  "?auth=recovery",
  PUBLIC_APP_URL,
).href;
const MAX_BODY_BYTES = 4_096;
const MAX_PROVIDER_RESPONSE_BYTES = 65_536;
const PROVIDER_TIMEOUT_MS = 15_000;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const MANAGER_ROLES = new Set(["owner", "admin"]);
const ACCOUNT_STATES = new Set([
  "ready",
  "recovery_required",
  "invite_required",
  "pending_delivery",
  "disabled",
  "unknown",
]);
const RECOMMENDED_ACTIONS = new Set([
  "none",
  "recovery",
  "invite",
  "wait",
  "manual_review",
]);
const DELIVERY_STATUSES = new Set([
  "unknown",
  "accepted_unconfirmed",
  "deferred",
  "delivered",
  "failed",
  "bounced",
  "suppressed",
  "complained",
]);
const ATTEMPT_PURPOSES = new Set(["invite", "recovery"]);
const ATTEMPT_STATUSES = new Set([
  "reserved",
  "accepted",
  "failed",
  "suppressed",
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
      creator_bootstrap: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_account_access_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_reserve_auth_email_attempt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_finalize_auth_email_attempt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

type BootstrapResult = {
  organizationId: string;
  role: string;
  workspaceOpen: boolean;
};

type AccountState =
  | "ready"
  | "recovery_required"
  | "invite_required"
  | "pending_delivery"
  | "disabled"
  | "unknown";

type RecommendedAction =
  | "none"
  | "recovery"
  | "invite"
  | "wait"
  | "manual_review";

type AccessSnapshot = {
  account_state: AccountState;
  recommended_action: RecommendedAction;
  membership: {
    exists: boolean;
    status: string | null;
    role: string | null;
  };
  identity: {
    exists: boolean;
    email_confirmed: boolean;
    disabled: boolean;
    last_sign_in_at: string | null;
  };
  delivery: {
    purpose: string | null;
    status: string | null;
    delivery_status: string | null;
    reason_code: string | null;
    requested_at: string | null;
    event_at: string | null;
  };
};

type ReservedAttempt = {
  attemptId: string;
  requestId: string;
  purpose: "invite" | "recovery";
};

type Reservation =
  | { kind: "reserved"; attempt: ReservedAttempt }
  | {
    kind: "suppressed";
    requestId: string;
    purpose: "invite" | "recovery";
    retryAfterSeconds: number;
    status: string;
    reasonCode: string;
  }
  | { kind: "unavailable" };

type InviteResult = {
  requestId: string | null;
  status: string;
  reasonCode: string;
  deliveryStatus: string;
  membershipProvisioned: boolean;
};

function responseHeaders(request: Request): HeadersInit {
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

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function stringOrNull(value: unknown, maxLength = 256): string | null {
  if (
    typeof value !== "string" || value.length < 1 ||
    value.length > maxLength
  ) {
    return null;
  }
  return value;
}

function isoDateOrNull(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64) return null;
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString() : null;
}

function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLocaleLowerCase("en-US");
  if (email.length < 3 || email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return null;
  }
  return email;
}

function readBootstrap(value: Json): BootstrapResult | null {
  if (!isRecord(value)) return null;
  const organization = asRecord(value.organization);
  const membership = asRecord(value.membership);
  const organizationId = stringOrNull(organization.id, 64);
  const role = stringOrNull(membership.role, 32);
  if (organizationId === null || role === null) return null;
  return {
    organizationId,
    role,
    workspaceOpen: value.workspace_open === true,
  };
}

function enumValue<T extends string>(
  value: unknown,
  allowed: Set<string>,
  fallback: T,
): T {
  return typeof value === "string" && allowed.has(value)
    ? value as T
    : fallback;
}

function normalizeAccessSnapshot(value: Json): AccessSnapshot | null {
  if (!isRecord(value)) return null;
  const membership = asRecord(value.membership);
  const identity = asRecord(value.identity);
  const delivery = asRecord(value.delivery);
  return {
    account_state: enumValue<AccountState>(
      value.account_state,
      ACCOUNT_STATES,
      "unknown",
    ),
    recommended_action: enumValue<RecommendedAction>(
      value.recommended_action,
      RECOMMENDED_ACTIONS,
      "manual_review",
    ),
    membership: {
      exists: membership.exists === true,
      status: stringOrNull(membership.status, 64),
      role: stringOrNull(membership.role, 32),
    },
    identity: {
      exists: identity.exists === true,
      email_confirmed: identity.email_confirmed === true,
      disabled: identity.disabled === true,
      last_sign_in_at: isoDateOrNull(identity.last_sign_in_at),
    },
    delivery: {
      purpose: enumValue<string>(
        delivery.purpose,
        ATTEMPT_PURPOSES,
        "",
      ) || null,
      status: enumValue<string>(
        delivery.status,
        ATTEMPT_STATUSES,
        "",
      ) || null,
      delivery_status: enumValue<string>(
        delivery.delivery_status,
        DELIVERY_STATUSES,
        "",
      ) || null,
      reason_code: stringOrNull(delivery.reason_code, 128),
      requested_at: isoDateOrNull(delivery.requested_at),
      event_at: isoDateOrNull(delivery.event_at),
    },
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

function configuration(): { origin: string; anonKey: string } | null {
  const origin = validSupabaseOrigin(Deno.env.get("SUPABASE_URL") ?? "");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY")?.trim() ?? "";
  if (origin === null || anonKey.length < 32 || anonKey.length > 4_096) {
    return null;
  }
  return { origin, anonKey };
}

function classifyInviteFailure(status: string, reasonCode: string): number {
  if (status === "rate_limited") return 429;
  if (status === "smtp_required") return 503;
  if (status === "pending_verification") return 202;
  if (reasonCode === "duplicate_request_suppressed") return 202;
  return 502;
}

const creatorAccess = withSupabase<ContentEngineDatabase>({
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
    payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(
      bodyBytes,
    ));
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }
  if (!isRecord(payload)) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }
  const action = payload.action;
  if (action !== "inspect" && action !== "repair") {
    return json(request, { ok: false, code: "action_invalid" }, 400);
  }
  const allowedKeys = action === "inspect"
    ? new Set(["action", "email"])
    : new Set(["action", "email", "request_id"]);
  if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
    return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
  }
  const email = normalizeEmail(payload.email);
  if (email === null) {
    return json(request, { ok: false, code: "email_invalid" }, 400);
  }
  const suppliedRequestId = payload.request_id;
  if (
    suppliedRequestId !== undefined &&
    (typeof suppliedRequestId !== "string" ||
      !UUID_PATTERN.test(suppliedRequestId))
  ) {
    return json(request, { ok: false, code: "request_id_invalid" }, 400);
  }

  const userId = context.userClaims?.id;
  if (!userId) {
    return json(request, { ok: false, code: "session_required" }, 401);
  }
  const { data: bootstrapData, error: bootstrapError } = await context.supabase
    .rpc("creator_bootstrap", { p_payload: {} });
  const bootstrap = readBootstrap(bootstrapData);
  if (bootstrapError || bootstrap === null) {
    return json(request, { ok: false, code: "workspace_unavailable" }, 403);
  }
  if (!bootstrap.workspaceOpen) {
    return json(request, { ok: false, code: "final_exam_required" }, 403);
  }
  if (!MANAGER_ROLES.has(bootstrap.role)) {
    return json(request, { ok: false, code: "team_management_forbidden" }, 403);
  }

  const readAccessStatus = async (): Promise<AccessSnapshot | null> => {
    const { data, error } = await context.supabase.rpc(
      "creator_account_access_status",
      {
        p_payload: {
          organization_id: bootstrap.organizationId,
          email,
        },
      },
    );
    if (error) return null;
    return normalizeAccessSnapshot(data);
  };

  const access = await readAccessStatus();
  if (access === null) {
    return json(request, { ok: false, code: "access_status_unavailable" }, 503);
  }
  if (action === "inspect") {
    return json(request, { ok: true, action, email, access });
  }

  const reserveAttempt = async (
    purpose: "invite" | "recovery",
    requestId: string,
  ): Promise<Reservation> => {
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_reserve_auth_email_attempt",
      {
        p_payload: {
          organization_id: bootstrap.organizationId,
          requested_by: userId,
          request_id: requestId,
          requested_at: new Date().toISOString(),
          email,
          purpose,
        },
      },
    );
    if (error || !isRecord(data)) return { kind: "unavailable" };
    const returnedRequestId = stringOrNull(data.request_id, 64) ?? requestId;
    if (data.reserved !== true) {
      const retryAfter = typeof data.retry_after_seconds === "number" &&
          Number.isFinite(data.retry_after_seconds)
        ? Math.max(0, Math.ceil(data.retry_after_seconds))
        : 60;
      return {
        kind: "suppressed",
        requestId: returnedRequestId,
        purpose,
        retryAfterSeconds: retryAfter,
        status: stringOrNull(data.status, 32) ?? "suppressed",
        reasonCode: stringOrNull(data.reason_code, 128) ??
          "duplicate_request_suppressed",
      };
    }
    const attemptId = stringOrNull(data.attempt_id, 64);
    if (attemptId === null) return { kind: "unavailable" };
    return {
      kind: "reserved",
      attempt: {
        attemptId,
        requestId: returnedRequestId,
        purpose,
      },
    };
  };

  const finalizeAttempt = async (
    attempt: ReservedAttempt,
    final: {
      status: "accepted" | "failed";
      reasonCode: string;
      deliveryStatus:
        | "unknown"
        | "accepted_unconfirmed"
        | "deferred"
        | "delivered"
        | "failed"
        | "bounced"
        | "suppressed"
        | "complained";
      membershipProvisioned: boolean;
    },
  ): Promise<boolean> => {
    const { error } = await context.supabaseAdmin.rpc(
      "system_finalize_auth_email_attempt",
      {
        p_payload: {
          attempt_id: attempt.attemptId,
          request_id: attempt.requestId,
          status: final.status,
          reason_code: final.reasonCode,
          delivery_status: final.deliveryStatus,
          membership_provisioned: final.membershipProvisioned,
        },
      },
    );
    return error === null;
  };

  const suppressedResponse = async (
    reservation: Extract<Reservation, { kind: "suppressed" }>,
    outcome = "cooldown",
    status = 429,
  ): Promise<Response> => {
    const refreshed = await readAccessStatus() ?? access;
    return json(request, {
      ok: status < 400,
      action: "repair",
      email,
      outcome,
      request_id: reservation.requestId,
      retry_after_seconds: reservation.retryAfterSeconds,
      reason_code: reservation.reasonCode,
      delivery_confirmed: false,
      access: refreshed,
    }, status);
  };

  const requestRecovery = async (
    requestId: string,
    outcome: string,
    membershipProvisioned = access.membership.exists,
  ): Promise<Response> => {
    const reservation = await reserveAttempt("recovery", requestId);
    if (reservation.kind === "unavailable") {
      return json(
        request,
        { ok: false, code: "access_journal_unavailable" },
        503,
      );
    }
    if (reservation.kind === "suppressed") {
      return await suppressedResponse(reservation);
    }
    const runtime = configuration();
    if (runtime === null) {
      await finalizeAttempt(reservation.attempt, {
        status: "failed",
        reasonCode: "auth_runtime_not_configured",
        deliveryStatus: "unknown",
        membershipProvisioned,
      });
      return json(
        request,
        { ok: false, code: "auth_runtime_not_configured" },
        503,
      );
    }

    let providerResponse: Response;
    try {
      providerResponse = await fetchWithTimeout(
        `${runtime.origin}/auth/v1/recover?redirect_to=${
          encodeURIComponent(RECOVERY_REDIRECT_URL)
        }`,
        {
          method: "POST",
          headers: {
            apikey: runtime.anonKey,
            authorization: `Bearer ${runtime.anonKey}`,
            "content-type": "application/json; charset=utf-8",
            "x-client-info": "contentengine-creator-access/1.0",
          },
          body: JSON.stringify({ email }),
        },
      );
    } catch {
      // The provider may have accepted the email before the connection failed.
      // Keep the durable attempt reserved so both the server decision and its
      // cooldown remain fail-safe against an immediate duplicate send.
      const refreshed = await readAccessStatus() ?? access;
      return json(request, {
        ok: true,
        action: "repair",
        email,
        outcome: "provider_outcome_pending",
        request_id: reservation.attempt.requestId,
        retry_after_seconds: 600,
        delivery_confirmed: false,
        access: refreshed,
      }, 202);
    }

    if (!providerResponse.ok) {
      const rateLimited = providerResponse.status === 429;
      const providerUnavailable = providerResponse.status >= 500;
      const reasonCode = rateLimited
        ? "email_rate_limited"
        : providerUnavailable
        ? "recovery_provider_unavailable"
        : "recovery_request_rejected";
      const finalized = await finalizeAttempt(reservation.attempt, {
        status: "failed",
        reasonCode,
        deliveryStatus: "unknown",
        membershipProvisioned,
      });
      if (!finalized) {
        return json(
          request,
          { ok: false, code: "access_journal_finalize_failed" },
          503,
        );
      }
      return json(request, {
        ok: false,
        code: reasonCode,
        request_id: reservation.attempt.requestId,
        delivery_confirmed: false,
      }, rateLimited ? 429 : providerUnavailable ? 503 : 502);
    }

    const finalized = await finalizeAttempt(reservation.attempt, {
      status: "accepted",
      reasonCode: "recovery_request_accepted",
      deliveryStatus: "accepted_unconfirmed",
      membershipProvisioned,
    });
    if (!finalized) {
      return json(request, {
        ok: false,
        code: "access_journal_finalize_failed",
        request_id: reservation.attempt.requestId,
        provider_outcome: "accepted_unconfirmed",
        delivery_confirmed: false,
      }, 503);
    }
    const refreshed = await readAccessStatus() ?? access;
    return json(request, {
      ok: true,
      action: "repair",
      email,
      outcome,
      request_id: reservation.attempt.requestId,
      delivery_status: "accepted_unconfirmed",
      delivery_confirmed: false,
      access: refreshed,
    });
  };

  if (access.recommended_action === "none") {
    return json(request, {
      ok: true,
      action: "repair",
      email,
      outcome: "already_ready",
      delivery_confirmed: access.delivery.delivery_status === "delivered",
      access,
    });
  }
  if (access.recommended_action === "wait") {
    return json(request, {
      ok: true,
      action: "repair",
      email,
      outcome: "pending_delivery",
      retry_after_seconds: 60,
      delivery_confirmed: access.delivery.delivery_status === "delivered",
      access,
    });
  }
  if (access.recommended_action === "manual_review") {
    return json(request, {
      ok: false,
      code: "manual_review_required",
      action: "repair",
      email,
      outcome: "manual_review",
      access,
    }, 409);
  }

  const requestId = typeof suppliedRequestId === "string"
    ? suppliedRequestId
    : crypto.randomUUID();
  if (access.recommended_action === "recovery") {
    return await requestRecovery(requestId, "recovery_requested");
  }

  // creator-invite owns the durable invite reservation and finalization. Its
  // legacy journal is mirrored into auth_email_attempts by the database, so a
  // second reservation here would create two equally plausible webhook
  // candidates and make honest delivery correlation ambiguous.
  const runtime = configuration();
  const authorization = request.headers.get("authorization") ?? "";
  if (
    runtime === null || !authorization.toLocaleLowerCase("en-US").startsWith(
      "bearer ",
    )
  ) {
    return json(
      request,
      { ok: false, code: "auth_runtime_not_configured" },
      503,
    );
  }

  let inviteResult: InviteResult | null = null;
  try {
    const inviteResponse = await fetchWithTimeout(
      `${runtime.origin}/functions/v1/creator-invite`,
      {
        method: "POST",
        headers: {
          apikey: runtime.anonKey,
          authorization,
          "content-type": "application/json; charset=utf-8",
          "x-client-info": "contentengine-creator-access/1.0",
        },
        body: JSON.stringify({ emails: [email] }),
      },
    );
    const responseBytes = await readBoundedStream(
      inviteResponse.body,
      MAX_PROVIDER_RESPONSE_BYTES,
    );
    const invitePayload = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(responseBytes),
    );
    const firstResult = isRecord(invitePayload) &&
        Array.isArray(invitePayload.results) &&
        isRecord(invitePayload.results[0])
      ? invitePayload.results[0]
      : null;
    if (firstResult !== null && normalizeEmail(firstResult.email) === email) {
      inviteResult = {
        requestId: stringOrNull(invitePayload.request_id, 64),
        status: stringOrNull(firstResult.status, 64) ?? "failed",
        reasonCode: stringOrNull(firstResult.reason_code, 128) ??
          "invite_request_failed",
        deliveryStatus: stringOrNull(firstResult.delivery_status, 64) ??
          "unknown",
        membershipProvisioned: firstResult.membership_provisioned === true,
      };
    }
  } catch {
    inviteResult = null;
  }

  if (inviteResult === null) {
    return json(request, {
      ok: false,
      code: "invite_provider_outcome_unknown",
      delivery_confirmed: false,
    }, 502);
  }

  if (
    inviteResult.status === "already_exists" &&
    inviteResult.membershipProvisioned
  ) {
    return await requestRecovery(
      crypto.randomUUID(),
      "membership_connected_recovery_requested",
      true,
    );
  }
  if (
    inviteResult.status === "invited" &&
    inviteResult.membershipProvisioned
  ) {
    const refreshed = await readAccessStatus() ?? access;
    return json(request, {
      ok: true,
      action: "repair",
      email,
      outcome: "invite_requested",
      request_id: inviteResult.requestId,
      delivery_status: "accepted_unconfirmed",
      delivery_confirmed: false,
      access: refreshed,
    });
  }

  const failureStatus = classifyInviteFailure(
    inviteResult.status,
    inviteResult.reasonCode,
  );
  const refreshed = await readAccessStatus() ?? access;
  return json(request, {
    ok: failureStatus === 202,
    code: inviteResult.reasonCode,
    action: "repair",
    email,
    outcome: failureStatus === 202
      ? "invite_pending_verification"
      : "invite_failed",
    request_id: inviteResult.requestId,
    delivery_confirmed: false,
    access: refreshed,
  }, failureStatus);
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }
    return creatorAccess(request);
  },
};
