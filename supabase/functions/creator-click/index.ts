import { withSupabase } from "npm:@supabase/server@1.3.0";

const SLUG_PATTERN = /^ce1_[0-9a-f]{24}$/u;
const VISITOR_TOKEN_PATTERN = /^[A-Za-z0-9_-]{16,128}$/u;
const VISITOR_COOKIE = "ce_tracking_v1";
const VISITOR_COOKIE_MAX_AGE = 31_536_000;

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
      system_record_public_tracking_click: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function boundedHeader(
  request: Request,
  name: string,
  maxLength: number,
): string {
  const value = request.headers.get(name)?.trim() ?? "";
  return value.length <= maxLength ? value : value.slice(0, maxLength);
}

function referrerOrigin(request: Request): string {
  const value = boundedHeader(request, "referer", 2_000);
  if (!value) return "";
  try {
    const url = new URL(value);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username !== "" || url.password !== ""
    ) return "";
    return url.origin.length <= 500 ? url.origin : "";
  } catch {
    return "";
  }
}

function cookieValue(request: Request, name: string): string {
  const cookie = request.headers.get("cookie") ?? "";
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) {
      const value = rest.join("=").trim();
      return VISITOR_TOKEN_PATTERN.test(value) ? value : "";
    }
  }
  return "";
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_")
    .replaceAll("=", "");
}

function visitorToken(request: Request): {
  value: string;
  created: boolean;
} {
  const existing = cookieValue(request, VISITOR_COOKIE);
  if (existing) return { value: existing, created: false };
  return {
    value: base64Url(crypto.getRandomValues(new Uint8Array(24))),
    created: true,
  };
}

function safeTarget(value: unknown): string | null {
  if (typeof value !== "string" || value.length < 12 || value.length > 2_000) {
    return null;
  }
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" || url.username !== "" ||
      url.password !== ""
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

function commonHeaders(): Headers {
  return new Headers({
    "cache-control": "private, no-store, max-age=0",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "referrer-policy": "no-referrer",
    "x-content-type-options": "nosniff",
    "x-robots-tag": "noindex, nofollow, noarchive",
  });
}

function errorResponse(status: number, code: string): Response {
  const headers = commonHeaders();
  headers.set("content-type", "application/json; charset=utf-8");
  return new Response(JSON.stringify({ ok: false, code }), {
    status,
    headers,
  });
}

const creatorClick = withSupabase<ContentEngineDatabase>({
  auth: "none",
}, async (request, context) => {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return errorResponse(405, "method_not_allowed");
  }
  const requestUrl = new URL(request.url);
  const slug = requestUrl.searchParams.get("slug")?.trim() ?? "";
  if (
    !SLUG_PATTERN.test(slug) ||
    [...requestUrl.searchParams.keys()].some((key) => key !== "slug")
  ) {
    return errorResponse(404, "tracking_link_not_found");
  }

  const visitor = visitorToken(request);
  const { data, error } = await context.supabaseAdmin.rpc(
    "system_record_public_tracking_click",
    {
      p_payload: {
        slug,
        user_agent: boundedHeader(request, "user-agent", 1_000),
        accept_language: boundedHeader(request, "accept-language", 200),
        visitor_token: visitor.value,
        referrer_origin: referrerOrigin(request),
      },
    },
  );
  if (error || !isRecord(data) || data.ok !== true) {
    return errorResponse(404, "tracking_link_not_found");
  }
  const target = safeTarget(data.target_url);
  if (target === null) {
    return errorResponse(503, "tracking_target_unavailable");
  }

  const headers = commonHeaders();
  headers.set("location", target);
  if (visitor.created) {
    headers.append(
      "set-cookie",
      `${VISITOR_COOKIE}=${visitor.value}; Max-Age=${VISITOR_COOKIE_MAX_AGE}; ` +
        "Path=/functions/v1/creator-click; Secure; HttpOnly; SameSite=Lax",
    );
  }
  return new Response(null, { status: 307, headers });
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    return creatorClick(request);
  },
};
