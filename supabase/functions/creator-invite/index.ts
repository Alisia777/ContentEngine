import { withSupabase } from "npm:@supabase/server@1.3.0";

const MAX_INVITES = 50;
const MAX_CONCURRENT_INVITES = 5;
const MAX_BODY_BYTES = 32_768;
const PUBLIC_APP_URL = new URL("https://alisia777.github.io/ContentEngine/");
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;
const PASSWORD_CHANGE_REQUIRED_MARKER =
  "contentengine_password_change_required";
const PASSWORD_CHANGE_COMPLETED_MARKER =
  "contentengine_password_change_completed";
const INVITE_ATTEMPT_RPC = "system_record_invite_delivery_attempts";

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
      system_provision_invited_member: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_reconcile_invited_member: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_invite_delivery_attempts: {
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

type InviteResult = {
  email: string;
  status:
    | "invited"
    | "already_exists"
    | "rate_limited"
    | "smtp_required"
    | "pending_verification"
    | "failed";
  reason_code: string;
  delivery_status: "accepted_unconfirmed" | "not_requested" | "unknown";
  membership_provisioned: boolean;
};

type PersistenceOutcome = {
  ok: boolean;
  suppressed: string[];
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

function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLocaleLowerCase("en-US");
  if (email.length < 3 || email.length > 320 || !EMAIL_PATTERN.test(email)) {
    return null;
  }
  return email;
}

function classifyInviteFailure(
  message: string,
): Pick<InviteResult, "status" | "reason_code"> {
  const normalized = message.toLocaleLowerCase("en-US");
  if (
    normalized.includes("already registered") ||
    normalized.includes("already exists") ||
    normalized.includes("user already")
  ) {
    return {
      status: "already_exists",
      reason_code: "auth_user_already_exists",
    };
  }
  if (normalized.includes("rate limit") || normalized.includes("too many")) {
    return { status: "rate_limited", reason_code: "email_rate_limited" };
  }
  if (
    normalized.includes("email address not authorized") ||
    normalized.includes("smtp")
  ) {
    return { status: "smtp_required", reason_code: "smtp_not_configured" };
  }
  return { status: "failed", reason_code: "auth_invite_failed" };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readBootstrap(value: Json): BootstrapResult | null {
  if (!isRecord(value)) return null;
  const organization = value.organization;
  const membership = value.membership;
  if (!isRecord(organization) || !isRecord(membership)) return null;
  if (typeof organization.id !== "string" || organization.id.length === 0) {
    return null;
  }
  if (typeof membership.role !== "string" || membership.role.length === 0) {
    return null;
  }
  return {
    organizationId: organization.id,
    role: membership.role,
    workspaceOpen: value.workspace_open === true,
  };
}

const inviteCreators = withSupabase<ContentEngineDatabase>({
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

  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }

  let bodyText: string;
  try {
    bodyText = await request.text();
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }
  if (new TextEncoder().encode(bodyText).byteLength > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(bodyText);
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }

  if (!isRecord(payload)) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }

  const rawEmails = payload.emails;
  if (
    !Array.isArray(rawEmails) || rawEmails.length < 1 ||
    rawEmails.length > MAX_INVITES
  ) {
    return json(request, {
      ok: false,
      code: "invite_count_invalid",
      max: MAX_INVITES,
    }, 400);
  }

  const emails: string[] = [];
  for (const value of rawEmails) {
    const email = normalizeEmail(value);
    if (email === null) {
      return json(request, { ok: false, code: "email_invalid" }, 400);
    }
    if (!emails.includes(email)) emails.push(email);
  }

  const { data: bootstrapData, error: bootstrapError } = await context.supabase
    .rpc(
      "creator_bootstrap",
      { p_payload: {} },
    );
  const bootstrap = readBootstrap(bootstrapData);
  if (bootstrapError || !bootstrap) {
    return json(request, { ok: false, code: "workspace_unavailable" }, 403);
  }
  if (!bootstrap.workspaceOpen) {
    return json(request, { ok: false, code: "final_exam_required" }, 403);
  }
  if (!new Set(["owner", "admin"]).has(bootstrap.role)) {
    return json(request, { ok: false, code: "team_management_forbidden" }, 403);
  }

  const organizationId = bootstrap.organizationId;
  const invitedBy = context.userClaims?.id;
  if (!invitedBy) {
    return json(request, { ok: false, code: "workspace_unavailable" }, 403);
  }
  const requestId = crypto.randomUUID();
  const requestedAt = new Date().toISOString();
  const results = new Array<InviteResult>(emails.length);
  const persistencePending = new Set<number>();

  const persistResults = async (
    batch: InviteResult[],
  ): Promise<PersistenceOutcome> => {
    try {
      const { data, error } = await context.supabaseAdmin.rpc(
        INVITE_ATTEMPT_RPC,
        {
          p_payload: {
            organization_id: organizationId,
            requested_by: invitedBy,
            request_id: requestId,
            requested_at: requestedAt,
            results: batch,
          },
        },
      );
      if (error !== null) return { ok: false, suppressed: [] };
      const suppressed = isRecord(data) && Array.isArray(data.suppressed)
        ? data.suppressed.flatMap((value) => {
          const email = normalizeEmail(value);
          return email === null ? [] : [email];
        })
        : [];
      return { ok: true, suppressed };
    } catch {
      return { ok: false, suppressed: [] };
    }
  };

  // Establish the complete request ledger before any email can be sent. If the
  // function is interrupted later, every address remains visible as ambiguous
  // instead of disappearing and tempting an unsafe full-list retry.
  const pendingResults: InviteResult[] = emails.map((email) => ({
    email,
    status: "pending_verification",
    reason_code: "invite_processing_started",
    delivery_status: "unknown",
    membership_provisioned: false,
  }));
  const reservation = await persistResults(pendingResults);
  if (!reservation.ok) {
    return json(request, {
      ok: false,
      code: "invite_journal_unavailable",
      requested: emails.length,
      invited: 0,
      already_exists: 0,
      pending_verification: 0,
      failed: emails.length,
      results: [],
      request_id: requestId,
      requested_at: requestedAt,
      delivery_confirmed: false,
      persistence: "unavailable",
      role: "trainee",
      smtp_required: false,
    }, 503);
  }

  const suppressedEmails = new Set(reservation.suppressed);
  const workIndexes: number[] = [];
  for (let index = 0; index < emails.length; index += 1) {
    if (suppressedEmails.has(emails[index])) {
      results[index] = {
        email: emails[index],
        status: "pending_verification",
        reason_code: "duplicate_request_suppressed",
        delivery_status: "unknown",
        membership_provisioned: false,
      };
    } else {
      workIndexes.push(index);
    }
  }

  const deliverInvite = async (email: string): Promise<InviteResult> => {
    const { data: inviteData, error: inviteError } = await context.supabaseAdmin
      .auth.admin.inviteUserByEmail(email, {
        data: {
          organization_id: organizationId,
          intended_role: "trainee",
          invited_by: invitedBy,
        },
        redirectTo: PUBLIC_APP_URL.href,
      });

    const inviteFailure = inviteError
      ? classifyInviteFailure(inviteError.message)
      : null;
    if (inviteFailure && inviteFailure.status !== "already_exists") {
      return {
        email,
        status: inviteFailure.status,
        reason_code: inviteFailure.reason_code,
        delivery_status: "not_requested",
        membership_provisioned: false,
      };
    }

    let membershipProvisioned = false;
    let failureReason = "membership_provision_failed";
    if (inviteFailure?.status === "already_exists") {
      const { error: reconciliationError } = await context.supabaseAdmin.rpc(
        "system_reconcile_invited_member",
        {
          p_payload: {
            organization_id: organizationId,
            email,
            invited_by: invitedBy,
          },
        },
      );
      membershipProvisioned = reconciliationError === null;
      failureReason = reconciliationError === null
        ? "existing_account_connected"
        : "membership_reconcile_failed";
    } else {
      const invitedUserId = inviteData.user?.id;
      if (invitedUserId) {
        const currentMetadata = isRecord(inviteData.user?.app_metadata)
          ? inviteData.user.app_metadata
          : {};
        const { error: markerError } = await context.supabaseAdmin.auth.admin
          .updateUserById(invitedUserId, {
            app_metadata: {
              ...currentMetadata,
              [PASSWORD_CHANGE_REQUIRED_MARKER]: true,
              [PASSWORD_CHANGE_COMPLETED_MARKER]: false,
            },
          });
        if (markerError === null) {
          const { error: provisionError } = await context.supabaseAdmin.rpc(
            "system_provision_invited_member",
            {
              p_payload: {
                organization_id: organizationId,
                user_id: invitedUserId,
                invited_by: invitedBy,
                role: "trainee",
                idempotency_key: `invite:${organizationId}:${invitedUserId}`,
              },
            },
          );
          membershipProvisioned = provisionError === null;
          failureReason = provisionError === null
            ? "invite_request_accepted"
            : "membership_provision_failed";
        } else {
          failureReason = "password_marker_failed";
        }
      } else {
        failureReason = "auth_user_missing";
      }
    }

    // Do not compensate an ambiguous RPC/network failure by deleting the auth
    // user: the transaction may have committed before the response was lost.
    // Both service-role paths use stable idempotency for safe reconciliation.
    return {
      email,
      status: membershipProvisioned
        ? (inviteFailure?.status === "already_exists"
          ? "already_exists"
          : "invited")
        : "failed",
      reason_code: failureReason,
      delivery_status: inviteFailure?.status === "already_exists"
        ? "not_requested"
        : "accepted_unconfirmed",
      membership_provisioned: membershipProvisioned,
    };
  };

  // A bounded worker pool keeps the 50-address path below the sequential
  // timeout cliff without creating an unbounded SMTP burst. Each email is taken
  // from the deduplicated array exactly once; only the idempotent journal write
  // is retried, never inviteUserByEmail.
  let nextIndex = 0;
  const worker = async (): Promise<void> => {
    while (true) {
      const workIndex = nextIndex;
      nextIndex += 1;
      if (workIndex >= workIndexes.length) return;
      const index = workIndexes[workIndex];

      let result: InviteResult;
      try {
        result = await deliverInvite(emails[index]);
      } catch {
        result = {
          email: emails[index],
          status: "pending_verification",
          reason_code: "invite_processing_interrupted",
          delivery_status: "unknown",
          membership_provisioned: false,
        };
      }
      results[index] = result;
      if (!(await persistResults([result])).ok) persistencePending.add(index);
    }
  };

  await Promise.all(
    Array.from(
      { length: Math.min(MAX_CONCURRENT_INVITES, workIndexes.length) },
      () => worker(),
    ),
  );

  // One idempotent bulk retry closes transient journal gaps. The unique
  // (organization, request, email) key makes this an upsert, not a duplicate.
  if (persistencePending.size > 0) {
    const retryResults = Array.from(
      persistencePending,
      (index) => results[index],
    );
    if ((await persistResults(retryResults)).ok) persistencePending.clear();
  }

  const invited = results.filter((item) => item.status === "invited").length;
  const alreadyExists = results.filter((item) =>
    item.status === "already_exists"
  ).length;
  const pendingVerification =
    results.filter((item) => item.status === "pending_verification").length;
  const failed = results.length - invited - alreadyExists;

  return json(request, {
    ok: failed === 0,
    requested: emails.length,
    invited,
    already_exists: alreadyExists,
    pending_verification: pendingVerification,
    failed,
    results,
    request_id: requestId,
    requested_at: requestedAt,
    delivery_confirmed: false,
    persistence: persistencePending.size === 0 ? "stored" : "partial",
    persistence_pending: persistencePending.size,
    role: "trainee",
    smtp_required: results.some((item) => item.status === "smtp_required"),
  });
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }
    return inviteCreators(request);
  },
};
