import { withSupabase } from "npm:@supabase/server@1.3.0";

const PUBLIC_APP_URL = new URL("https://alisia777.github.io/ContentEngine/");
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const MAX_BODY_BYTES = 2_048;
const PASSWORD_CHANGE_REQUIRED_MARKER =
  "contentengine_password_change_required";
const PASSWORD_CHANGE_COMPLETED_MARKER =
  "contentengine_password_change_completed";
const PASSWORD_CHANGE_COMPLETED_AT_MARKER =
  "contentengine_password_change_completed_at";
const LEGACY_REQUIRED_MARKERS = [
  "contentengine_github_member_provisioned",
  "contentengine_owner_password_reset_once_20260714",
] as const;

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

function validPassword(value: unknown): value is string {
  if (typeof value !== "string" || value.length < 10 || value.length > 128) {
    return false;
  }
  if (!/[a-z]/u.test(value) || !/[A-Z]/u.test(value) || !/[0-9]/u.test(value)) {
    return false;
  }
  return !Array.from(value).some((character) => /\p{Cc}/u.test(character));
}

function passwordChangeRequired(metadata: Record<string, unknown>): boolean {
  if (metadata[PASSWORD_CHANGE_REQUIRED_MARKER] === true) return true;
  if (metadata[PASSWORD_CHANGE_COMPLETED_MARKER] === true) return false;
  return LEGACY_REQUIRED_MARKERS.some((marker) => metadata[marker] === true);
}

const setPassword = withSupabase({
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
  if (!isRecord(payload) || !validPassword(payload.password)) {
    return json(request, { ok: false, code: "password_policy_invalid" }, 400);
  }

  const userId = context.userClaims?.id;
  if (!userId) {
    return json(request, { ok: false, code: "session_required" }, 401);
  }
  const { data: currentData, error: currentError } = await context.supabaseAdmin
    .auth.admin.getUserById(userId);
  const currentUser = currentData?.user;
  if (currentError || !currentUser || currentUser.id !== userId) {
    return json(request, { ok: false, code: "account_unavailable" }, 403);
  }
  const metadata = isRecord(currentUser.app_metadata)
    ? { ...currentUser.app_metadata }
    : {};
  if (!passwordChangeRequired(metadata)) {
    return json(
      request,
      { ok: false, code: "password_change_not_required" },
      409,
    );
  }

  metadata[PASSWORD_CHANGE_REQUIRED_MARKER] = false;
  metadata[PASSWORD_CHANGE_COMPLETED_MARKER] = true;
  metadata[PASSWORD_CHANGE_COMPLETED_AT_MARKER] = new Date().toISOString();
  const { data: updatedData, error: updateError } = await context.supabaseAdmin
    .auth.admin.updateUserById(userId, {
      password: payload.password,
      app_metadata: metadata,
    });
  const updatedUser = updatedData?.user;
  if (updateError || !updatedUser || updatedUser.id !== userId) {
    return json(request, { ok: false, code: "password_update_failed" }, 502);
  }

  return json(request, {
    ok: true,
    password_change_required: false,
    app_metadata: updatedUser.app_metadata ?? metadata,
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
    return setPassword(request);
  },
};
