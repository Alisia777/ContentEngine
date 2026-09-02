import { withSupabase } from "npm:@supabase/server@1.3.0";

// Публичный вход витрины согласования (ступень 1): клиент без auth-учётки
// открывает токен-ссылку, смотрит ролики и принимает решения. Токен — вся
// авторизация; вся логика и анти-энумерация живут в системных RPC
// (202609030010), здесь — граница HTTP: строгий разбор тела, паттерн-чек
// токена ДО похода в БД, HMAC-ключ клиента для rate-limit и подпись
// storage-URL на 900 секунд (потолок веб-слоя). Origin канонический —
// hardliver1.github.io (решение 03.09, временно до покупки домена):
// переезд = env PUBLIC_APP_URL + redeploy, без правки кода.
const PUBLIC_APP_URL = new URL(
  Deno.env.get("PUBLIC_APP_URL")?.trim() ||
    "https://hardliver1.github.io/ContentEngine/",
);
const PUBLIC_APP_ORIGIN = PUBLIC_APP_URL.origin;
const MAX_BODY_BYTES = 4_096;
const SIGNED_URL_TTL_SECONDS = 900;
const REVIEW_TOKEN_PATTERN = /^crv1_[A-Za-z0-9_-]{43}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const NOT_FOUND_MESSAGE =
  "Ссылка недействительна или устарела. Запросите новую у вашей команды.";
const RATE_LIMITED_MESSAGE =
  "Слишком много запросов. Подождите немного и обновите страницу.";

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
      system_client_review_view: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_client_review_decide: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_client_intake_upload_init: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_client_intake_submit_brief: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
};

const INTAKE_BUCKET = "contentengine-private";
const INTAKE_MIME_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
]);

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

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function hashToken(token: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(token),
  );
  return hex(new Uint8Array(digest));
}

function clientAddressMaterial(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",", 1)[0]
    ?.trim();
  for (
    const candidate of [
      request.headers.get("cf-connecting-ip")?.trim(),
      request.headers.get("x-real-ip")?.trim(),
      forwarded,
    ]
  ) {
    if (candidate && /^[0-9a-f:.]{3,64}$/iu.test(candidate)) return candidate;
  }
  return "unavailable";
}

async function clientKeyHash(
  request: Request,
  serviceRoleKey: string,
): Promise<string> {
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
    new TextEncoder().encode(
      `contentengine-client-review:v1:${clientAddressMaterial(request)}`,
    ),
  );
  return hex(new Uint8Array(signature));
}

function refusal(request: Request, value: Record<string, unknown>): Response {
  const code = stringOrNull(value.code, 64) ?? "client_review_not_found";
  if (code === "client_review_rate_limited") {
    return json(request, {
      ok: false,
      code,
      message: RATE_LIMITED_MESSAGE,
      retry_after_seconds: typeof value.retry_after_seconds === "number"
        ? value.retry_after_seconds
        : 900,
    }, 429);
  }
  return json(request, {
    ok: false,
    code: "client_review_not_found",
    message: NOT_FOUND_MESSAGE,
  }, 404);
}

const clientReview = withSupabase<ContentEngineDatabase>({
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

  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")?.trim() ??
    "";
  if (serviceRoleKey.length < 32) {
    return json(request, { ok: false, code: "review_unavailable" }, 503);
  }

  // Паттерн-чек токена ДО любого похода в БД: мусор не тратит ни журнал,
  // ни advisory-локи. Единый ответ совпадает с судьбой чужого токена.
  const token = stringOrNull(payload.token, 128);
  if (token === null || !REVIEW_TOKEN_PATTERN.test(token)) {
    return json(request, {
      ok: false,
      code: "client_review_not_found",
      message: NOT_FOUND_MESSAGE,
    }, 404);
  }
  const tokenHash = await hashToken(token);
  const callerHash = await clientKeyHash(request, serviceRoleKey);
  const action = payload.action;

  if (action === "view") {
    const allowedKeys = new Set(["action", "token"]);
    if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
      return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
    }
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_client_review_view",
      {
        p_payload: { token_hash: tokenHash, client_key_hash: callerHash },
      },
    );
    if (error !== null || !isRecord(data)) {
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    if (data.ok !== true) return refusal(request, data);

    // Подпись URL роликов: группировка по бакету, TTL 900 секунд — потолок
    // веб-слоя; страница перезапрашивает view по истечении подписи.
    const rawItems = Array.isArray(data.items) ? data.items : [];
    const byBucket = new Map<string, string[]>();
    for (const item of rawItems) {
      if (!isRecord(item)) continue;
      const bucket = stringOrNull(item.bucket_id, 128);
      const objectName = stringOrNull(item.object_name, 1024);
      if (bucket === null || objectName === null) continue;
      const list = byBucket.get(bucket) ?? [];
      list.push(objectName);
      byBucket.set(bucket, list);
    }
    const signedByPath = new Map<string, string>();
    for (const [bucket, paths] of byBucket) {
      const { data: signed, error: signError } = await context.supabaseAdmin
        .storage.from(bucket)
        .createSignedUrls(paths, SIGNED_URL_TTL_SECONDS);
      if (signError !== null || !Array.isArray(signed)) continue;
      for (const entry of signed) {
        if (
          isRecord(entry) && typeof entry.path === "string" &&
          typeof entry.signedUrl === "string"
        ) {
          signedByPath.set(`${bucket}:${entry.path}`, entry.signedUrl);
        }
      }
    }
    const items = rawItems.flatMap((item) => {
      if (!isRecord(item)) return [];
      const bucket = stringOrNull(item.bucket_id, 128) ?? "";
      const objectName = stringOrNull(item.object_name, 1024) ?? "";
      return [{
        item_id: item.item_id ?? null,
        position: item.position ?? null,
        title: stringOrNull(item.title, 256) ?? "Ролик",
        duration_seconds: item.duration_seconds ?? null,
        video_url: signedByPath.get(`${bucket}:${objectName}`) ?? null,
        last_decision: isRecord(item.last_decision)
          ? item.last_decision
          : null,
        published: isRecord(item.published) ? item.published : null,
      }];
    });

    return json(request, {
      ok: true,
      version: "client-review-view-v1",
      client_label: stringOrNull(data.client_label, 160) ?? "",
      campaign_name: stringOrNull(data.campaign_name, 256) ?? "",
      expires_at: stringOrNull(data.expires_at, 64),
      signed_url_ttl_seconds: SIGNED_URL_TTL_SECONDS,
      intake_enabled: data.intake_enabled === true,
      intake_briefs: Array.isArray(data.intake_briefs)
        ? data.intake_briefs.filter(isRecord)
        : [],
      items,
    });
  }

  if (action === "decide") {
    const allowedKeys = new Set([
      "action",
      "token",
      "item_id",
      "decision",
      "comment",
      "client_request_id",
    ]);
    if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
      return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
    }
    const itemId = stringOrNull(payload.item_id, 64);
    const requestId = stringOrNull(payload.client_request_id, 64);
    const decision = stringOrNull(payload.decision, 32);
    if (
      itemId === null || !UUID_PATTERN.test(itemId) ||
      requestId === null || !UUID_PATTERN.test(requestId) ||
      decision === null ||
      !["accepted", "returned", "publish_requested"].includes(decision)
    ) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    const comment = payload.comment === undefined || payload.comment === null
      ? null
      : stringOrNull(payload.comment, 2000);
    if (decision === "returned" && (comment === null || comment.trim().length < 3)) {
      return json(request, {
        ok: false,
        code: "client_review_comment_required",
        message: "Добавьте комментарий: что именно вернуть на доработку.",
      }, 400);
    }
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_client_review_decide",
      {
        p_payload: {
          token_hash: tokenHash,
          client_key_hash: callerHash,
          item_id: itemId,
          decision,
          comment,
          client_request_id: requestId,
        },
      },
    );
    if (error !== null || !isRecord(data)) {
      const errorMessage = error?.message ?? "";
      if (errorMessage.includes("client_review_comment")) {
        return json(request, {
          ok: false,
          code: "client_review_comment_invalid",
          message:
            "Комментарий не сохранился: сократите его до 2000 знаков и " +
            "не вставляйте пароли или ключи.",
        }, 400);
      }
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    if (data.ok !== true) return refusal(request, data);
    return json(request, {
      ok: true,
      version: "client-review-decide-v1",
      replayed: data.replayed === true,
      decision: stringOrNull(data.decision, 32),
    });
  }

  if (action === "intake_upload_init") {
    const allowedKeys = new Set([
      "action",
      "token",
      "original_filename",
      "mime_type",
      "size_bytes",
      "rights_confirmed",
      "client_request_id",
    ]);
    if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
      return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
    }
    const requestId = stringOrNull(payload.client_request_id, 64);
    const mimeType = stringOrNull(payload.mime_type, 64) ?? "";
    const sizeBytes = typeof payload.size_bytes === "number"
      ? Math.floor(payload.size_bytes)
      : 0;
    if (
      requestId === null || !UUID_PATTERN.test(requestId) ||
      !INTAKE_MIME_TYPES.has(mimeType) ||
      sizeBytes < 1 || sizeBytes > 52_428_800 ||
      payload.rights_confirmed !== true
    ) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_client_intake_upload_init",
      {
        p_payload: {
          token_hash: tokenHash,
          client_key_hash: callerHash,
          original_filename: stringOrNull(payload.original_filename, 255) ??
            "file",
          mime_type: mimeType,
          size_bytes: sizeBytes,
          rights_confirmed: true,
          client_request_id: requestId,
        },
      },
    );
    if (error !== null || !isRecord(data)) {
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    if (data.ok !== true) return refusal(request, data);
    const upload = isRecord(data.upload) ? data.upload : {};
    const objectName = stringOrNull(upload.object_name, 1024);
    if (objectName === null) {
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    // Подписанный upload-URL: файл идёт в storage напрямую, минуя edge.
    const { data: signed, error: signError } = await context.supabaseAdmin
      .storage.from(INTAKE_BUCKET)
      .createSignedUploadUrl(objectName);
    if (signError !== null || !isRecord(signed)) {
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    return json(request, {
      ok: true,
      version: "client-intake-v1",
      replayed: data.replayed === true,
      upload_id: upload.id ?? null,
      signed_url: signed.signedUrl ?? null,
      upload_token: signed.token ?? null,
      object_name: objectName,
    });
  }

  if (action === "intake_brief") {
    const allowedKeys = new Set([
      "action",
      "token",
      "brief_product",
      "brief_audience",
      "brief_tone",
      "brief_restrictions",
      "brief_wishes",
      "client_request_id",
    ]);
    if (Object.keys(payload).some((key) => !allowedKeys.has(key))) {
      return json(request, { ok: false, code: "payload_fields_invalid" }, 400);
    }
    const requestId = stringOrNull(payload.client_request_id, 64);
    if (requestId === null || !UUID_PATTERN.test(requestId)) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    const { data, error } = await context.supabaseAdmin.rpc(
      "system_client_intake_submit_brief",
      {
        p_payload: {
          token_hash: tokenHash,
          client_key_hash: callerHash,
          brief_product: stringOrNull(payload.brief_product, 180),
          brief_audience: stringOrNull(payload.brief_audience, 600),
          brief_tone: stringOrNull(payload.brief_tone, 400),
          brief_restrictions: stringOrNull(payload.brief_restrictions, 800),
          brief_wishes: stringOrNull(payload.brief_wishes, 1200),
          client_request_id: requestId,
        },
      },
    );
    if (error !== null || !isRecord(data)) {
      const message = error?.message ?? "";
      if (message.includes("client_intake_brief_invalid")) {
        return json(request, {
          ok: false,
          code: "client_intake_brief_invalid",
          message:
            "Проверьте бриф: товар (2–180), аудитория (3–600), тон (3–400) — " +
            "и не вставляйте пароли или ключи.",
        }, 400);
      }
      return json(request, { ok: false, code: "review_unavailable" }, 503);
    }
    if (data.ok !== true) return refusal(request, data);
    return json(request, {
      ok: true,
      version: "client-intake-v1",
      replayed: data.replayed === true,
      brief: isRecord(data.brief) ? data.brief : null,
    });
  }

  return json(request, { ok: false, code: "action_invalid" }, 400);
});

export default {
  fetch(request: Request): Promise<Response> | Response {
    return clientReview(request);
  },
};
