import { withSupabase } from "npm:@supabase/server@1.3.0";

const MAX_INVITES = 50;
const MAX_BODY_BYTES = 32_768;
const PUBLIC_APP_URL = new URL("https://alisia777.github.io/ContentEngine/");
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const EMAIL_PATTERN = /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u;

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
    | "failed";
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

function classifyInviteFailure(message: string): InviteResult["status"] {
  const normalized = message.toLocaleLowerCase("en-US");
  if (
    normalized.includes("already registered") ||
    normalized.includes("already exists") ||
    normalized.includes("user already")
  ) {
    return "already_exists";
  }
  if (normalized.includes("rate limit") || normalized.includes("too many")) {
    return "rate_limited";
  }
  if (
    normalized.includes("email address not authorized") ||
    normalized.includes("smtp")
  ) {
    return "smtp_required";
  }
  return "failed";
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
  const results: InviteResult[] = [];

  // Sequential delivery avoids turning one owner action into a burst against
  // the project's SMTP provider. Supabase still enforces its configured limits.
  for (const email of emails) {
    const { data: inviteData, error: inviteError } = await context.supabaseAdmin
      .auth.admin.inviteUserByEmail(email, {
        data: {
          organization_id: organizationId,
          intended_role: "trainee",
          invited_by: invitedBy,
        },
        redirectTo: PUBLIC_APP_URL.href,
      });

    if (inviteError) {
      results.push({
        email,
        status: classifyInviteFailure(inviteError.message),
      });
      continue;
    }

    const invitedUserId = inviteData.user?.id;
    if (!invitedUserId) {
      results.push({ email, status: "failed" });
      continue;
    }

    const { error: provisionError } = await context.supabaseAdmin.rpc(
      "system_provision_invited_member",
      {
        p_payload: {
          organization_id: organizationId,
          user_id: invitedUserId,
          invited_by: invitedBy,
          role: "trainee",
          idempotency_key:
            `invite:${organizationId}:${invitedUserId}`,
        },
      },
    );

    // Do not compensate an ambiguous RPC/network failure by deleting the auth
    // user: the transaction may have committed before the response was lost.
    // The stable idempotency key makes service-role reconciliation safe.
    results.push({
      email,
      status: provisionError ? "failed" : "invited",
    });
  }

  const invited = results.filter((item) => item.status === "invited").length;
  const alreadyExists = results.filter((item) =>
    item.status === "already_exists"
  ).length;
  const failed = results.length - invited - alreadyExists;

  return json(request, {
    ok: failed === 0,
    requested: emails.length,
    invited,
    already_exists: alreadyExists,
    failed,
    results,
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
