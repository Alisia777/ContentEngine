import { type SupabaseContext, withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  isInternalWorkerAuthorized,
  isInternalWorkerRequest,
} from "../_shared/internal-worker-auth.ts";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses";
const OPENAI_MODERATIONS_URL = "https://api.openai.com/v1/moderations";
const STORAGE_BUCKET = "contentengine-private";
const RULESET_VERSION = "ru-content-compliance-2026-07-16.1";
const MAX_BODY_BYTES = 4_096;
const MAX_PROVIDER_JSON_BYTES = 1_572_864;
const OPENAI_TIMEOUT_MS = 110_000;
const SIGNED_IMAGE_TTL_SECONDS = 900;
const MIN_VIDEO_FRAMES = 4;
const MAX_VIDEO_FRAMES = 5;
const MAX_FRAME_BYTES = 524_288;
const MAX_TOTAL_FRAME_BYTES = 2_359_296;
const MAX_OUTPUT_TOKENS = 10_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const RUN_STATUSES = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
  "cancelled",
]);
const SOURCE_KEYS = new Set([
  "none",
  "ad_law_38fz",
  "ad_definition_1087",
  "restricted_resources_72fz",
  "erid_order_68",
  "ord_rules_974",
  "publisher_registry_238",
  "personal_data_152fz",
  "image_rights_152_1",
  "cosmetics_tr_ts_009",
  "food_label_tr_ts_022",
  "youtube_synthetic",
]);
const LEGAL_SOURCE_URLS: Readonly<Record<string, string>> = Object.freeze({
  ad_law_38fz: "https://government.ru/docs/all/98086/",
  ad_definition_1087:
    "https://publication.pravo.gov.ru/document/0001202507250057",
  restricted_resources_72fz:
    "https://publication.pravo.gov.ru/document/0001202504070018",
  erid_order_68: "https://publication.pravo.gov.ru/document/0001202504140029",
  ord_rules_974: "https://publication.pravo.gov.ru/document/0001202205300041",
  publisher_registry_238:
    "https://publication.pravo.gov.ru/document/0001202412300041",
  personal_data_152fz: "https://government.ru/docs/all/98196/",
  image_rights_152_1: "https://government.ru/docs/all/95825/?page=18",
  cosmetics_tr_ts_009:
    "https://eec.eaeunion.org/comission/department/deptexreg/tr/bezopParfum.php",
  food_label_tr_ts_022:
    "https://eec.eaeunion.org/comission/department/deptexreg/tr/PischevkaMarkirovka.php",
  youtube_synthetic: "https://support.google.com/youtube/answer/14328491",
});
const PROVIDER_FAILURE_CODES = new Set([
  "provider_configuration_error",
  "provider_authentication_failed",
  "provider_rate_limited",
  "provider_request_rejected",
  "provider_response_invalid",
  "provider_outcome_unknown",
  "provider_unavailable",
  "image_access_failed",
  "input_validation_failed",
  "external_ai_processing_basis_required",
  "internal_error",
]);
const UNKNOWN_PROVIDER_OUTCOME_MESSAGE =
  "Провайдер мог принять платный запрос, но результат не подтверждён. Автоматического повтора нет: создайте новую проверку только после сверки истории.";

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
      creator_content_review_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_claim_content_review: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_begin_content_review_provider_dispatch: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_release_content_review_attempt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_complete_content_review: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
  content_factory: {
    Tables: {
      content_review_runs: {
        Row: {
          id: string;
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

type AnalyzePayload = {
  action: "analyze";
  review_id: string;
};

type ReviewAttempt = {
  id: string;
  leaseToken: string;
  attemptNo: number;
  providerIdempotencyKey: string;
};

type ReviewEvidenceFrame = {
  objectName: string;
  sha256: string;
  sizeBytes: number;
  timecodeSeconds: number;
};

type ReviewEvidence = {
  manifestHash: string;
  frames: ReviewEvidenceFrame[];
};

type ReviewMedia = {
  id: string;
  objectName: string;
  mimeType: string;
  sha256: string;
  sizeBytes: number;
  status: "ready";
  snapshotMatches: true;
  metadata: Record<string, Json>;
};

type ReviewRun = {
  id: string;
  organizationId: string;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  requestedBy: string;
  input: Record<string, Json>;
  media: ReviewMedia;
  parentResult: Record<string, Json> | null;
};

type Finding = {
  code: string;
  category: string;
  severity: "blocker" | "high" | "medium" | "low" | "info";
  title: string;
  detail: string;
  action: string;
  evidence: Record<string, Json>;
  confidence: number;
  human_review_required: boolean;
  source_key: string;
  stage: string;
  timecode: string | null;
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

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function hasForbiddenControl(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code === 0x7f) return true;
    if (code <= 0x1f && code !== 0x09 && code !== 0x0a && code !== 0x0d) {
      return true;
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
    !hasForbiddenControl(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
): boolean {
  return Object.keys(value).every((key) => allowed.has(key));
}

function readRequestPayload(value: unknown): AnalyzePayload | null {
  if (!isRecord(value)) return null;
  if (
    !hasOnlyKeys(value, new Set(["action", "review_id"])) ||
    value.action !== "analyze" || !isUuid(value.review_id)
  ) return null;
  return {
    action: "analyze",
    review_id: value.review_id,
  };
}

function readJsonRecord(
  value: unknown,
  maximum = 262_144,
): Record<string, Json> | null {
  if (!isRecord(value) || JSON.stringify(value).length > maximum) return null;
  return value as Record<string, Json>;
}

function readMedia(value: unknown): ReviewMedia | null {
  if (!isRecord(value)) return null;
  const metadata = readJsonRecord(value.metadata, 32_768);
  if (
    !isUuid(value.id) || !isBoundedText(value.object_name, 10, 1_000) ||
    !isBoundedText(value.mime_type, 3, 160) ||
    !["image/jpeg", "image/png", "image/webp", "video/mp4"].includes(
      value.mime_type,
    ) ||
    typeof value.sha256 !== "string" ||
    !/^[0-9a-f]{64}$/u.test(value.sha256) ||
    !Number.isSafeInteger(value.size_bytes) || Number(value.size_bytes) < 1 ||
    Number(value.size_bytes) > 52_428_800 ||
    value.status !== "ready" || value.snapshot_matches !== true ||
    metadata === null
  ) return null;
  return {
    id: value.id,
    objectName: value.object_name,
    mimeType: value.mime_type,
    sha256: value.sha256,
    sizeBytes: Number(value.size_bytes),
    status: "ready",
    snapshotMatches: true,
    metadata,
  };
}

function readRun(value: unknown): ReviewRun | null {
  if (!isRecord(value)) return null;
  const media = readMedia(value.media);
  const input = readJsonRecord(value.input);
  const parentResult = value.parent_result === null ||
      value.parent_result === undefined
    ? null
    : readJsonRecord(value.parent_result);
  if (
    !isUuid(value.id) || !isUuid(value.organization_id) ||
    !isUuid(value.requested_by) ||
    typeof value.status !== "string" || !RUN_STATUSES.has(value.status) ||
    media === null || input === null ||
    (value.parent_result !== null && value.parent_result !== undefined &&
      parentResult === null)
  ) return null;
  return {
    id: value.id,
    organizationId: value.organization_id,
    status: value.status as ReviewRun["status"],
    requestedBy: value.requested_by,
    input,
    media,
    parentResult,
  };
}

function readAttempt(value: unknown): ReviewAttempt | null {
  if (
    !isRecord(value) || !isUuid(value.id) || !isUuid(value.lease_token) ||
    !Number.isSafeInteger(value.attempt_no) || Number(value.attempt_no) < 1 ||
    Number(value.attempt_no) > 1_000 ||
    !isBoundedText(value.provider_idempotency_key, 8, 180)
  ) return null;
  return {
    id: value.id,
    leaseToken: value.lease_token,
    attemptNo: Number(value.attempt_no),
    providerIdempotencyKey: value.provider_idempotency_key,
  };
}

function readEvidenceFrame(value: unknown): ReviewEvidenceFrame | null {
  if (
    !isRecord(value) || !isBoundedText(value.object_name, 10, 1_000) ||
    value.object_name.startsWith("/") || value.object_name.includes("\\") ||
    value.object_name.split("/").some((part) =>
      part === "" || part === "." || part === ".."
    ) ||
    typeof value.sha256 !== "string" || !SHA256_PATTERN.test(value.sha256) ||
    !Number.isSafeInteger(value.size_bytes) || Number(value.size_bytes) < 128 ||
    Number(value.size_bytes) > MAX_FRAME_BYTES ||
    typeof value.timecode_seconds !== "number" ||
    !Number.isFinite(value.timecode_seconds) || value.timecode_seconds < 0 ||
    value.timecode_seconds > 3_600
  ) return null;
  return {
    objectName: value.object_name,
    sha256: value.sha256,
    sizeBytes: Number(value.size_bytes),
    timecodeSeconds: Number(value.timecode_seconds),
  };
}

function readEvidence(value: unknown): ReviewEvidence | null {
  if (
    !isRecord(value) || typeof value.manifest_hash !== "string" ||
    !SHA256_PATTERN.test(value.manifest_hash) || !Array.isArray(value.frames) ||
    value.frames.length < MIN_VIDEO_FRAMES ||
    value.frames.length > MAX_VIDEO_FRAMES
  ) return null;
  const frames: ReviewEvidenceFrame[] = [];
  const objectNames = new Set<string>();
  let totalBytes = 0;
  let lastTimecode = -1;
  for (const candidate of value.frames) {
    const frame = readEvidenceFrame(candidate);
    if (
      frame === null || objectNames.has(frame.objectName) ||
      frame.timecodeSeconds <= lastTimecode
    ) return null;
    totalBytes += frame.sizeBytes;
    if (totalBytes > MAX_TOTAL_FRAME_BYTES) return null;
    objectNames.add(frame.objectName);
    lastTimecode = frame.timecodeSeconds;
    frames.push(frame);
  }
  return { manifestHash: value.manifest_hash, frames };
}

function readClaimEnvelope(
  value: unknown,
): {
  claimed: boolean;
  run: ReviewRun;
  attempt: ReviewAttempt | null;
  evidence: ReviewEvidence | null;
} | null {
  if (
    !isRecord(value) || value.ok !== true ||
    typeof value.claimed !== "boolean"
  ) return null;
  const run = readRun(value.run);
  const attempt = value.attempt === null || value.attempt === undefined
    ? null
    : readAttempt(value.attempt);
  const evidence = value.evidence === null || value.evidence === undefined
    ? null
    : readEvidence(value.evidence);
  if (run === null || (value.claimed === true && attempt === null)) return null;
  if (
    run.media.mimeType === "video/mp4" && value.claimed === true &&
    evidence === null
  ) return null;
  return { claimed: value.claimed, run, attempt, evidence };
}

async function readBoundedStream(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
): Promise<Uint8Array<ArrayBuffer>> {
  if (body === null) throw new Error("body_missing");
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
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const size = Number(declared);
    if (
      !Number.isSafeInteger(size) || size < 0 || size > MAX_PROVIDER_JSON_BYTES
    ) throw new Error("provider_response_invalid");
  }
  const bytes = await readBoundedStream(response.body, MAX_PROVIDER_JSON_BYTES);
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("provider_response_invalid");
  }
}

function openAiSecret(): string | null {
  const value = Deno.env.get("OPENAI_API_KEY") ?? "";
  if (
    value.length < 20 || value.length > 512 || value !== value.trim() ||
    hasForbiddenControl(value)
  ) return null;
  return value;
}

function openAiModel(): string {
  const configured = Deno.env.get("OPENAI_CONTENT_REVIEW_MODEL") ??
    Deno.env.get("QVF_OPENAI_MODEL") ?? "gpt-5.5";
  return /^[A-Za-z0-9][A-Za-z0-9._:-]{1,79}$/u.test(configured) &&
      !hasForbiddenControl(configured)
    ? configured
    : "gpt-5.5";
}

function validateSignedStorageUrl(value: unknown): string | null {
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
    ) return null;
    return actual.href;
  } catch {
    return null;
  }
}

async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) =>
    value.toString(16).padStart(2, "0")
  ).join("");
}

function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8 &&
    bytes[2] === 0xff && bytes[bytes.length - 2] === 0xff &&
    bytes[bytes.length - 1] === 0xd9;
}

function jpegDataUrl(bytes: Uint8Array): string {
  const chunks: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += 32_768) {
    chunks.push(
      String.fromCharCode(...bytes.subarray(offset, offset + 32_768)),
    );
  }
  return `data:image/jpeg;base64,${btoa(chunks.join(""))}`;
}

function providerRequestId(
  response: Response,
  providerValue?: unknown,
): string | null {
  const candidates = [
    response.headers.get("x-request-id"),
    isRecord(providerValue) ? providerValue.id : null,
  ];
  for (const candidate of candidates) {
    if (
      typeof candidate === "string" && candidate.length >= 3 &&
      candidate.length <= 240 &&
      /^[A-Za-z0-9][A-Za-z0-9._:-]*$/u.test(candidate)
    ) return candidate;
  }
  return null;
}

function strictObject(properties: Record<string, Json>): Json {
  return {
    type: "object",
    additionalProperties: false,
    required: Object.keys(properties),
    properties,
  };
}

function nullableStringSchema(maxLength: number): Json {
  return {
    anyOf: [
      { type: "string", maxLength },
      { type: "null" },
    ],
  };
}

const FINDING_SCHEMA = strictObject({
  code: { type: "string", maxLength: 100 },
  category: {
    type: "string",
    enum: [
      "quality",
      "legal",
      "claim",
      "platform",
      "rights",
      "privacy",
      "safety",
      "technical",
      "accessibility",
    ],
  },
  severity: {
    type: "string",
    enum: ["blocker", "high", "medium", "low", "info"],
  },
  title: { type: "string", maxLength: 240 },
  detail: { type: "string", maxLength: 1_200 },
  action: { type: "string", maxLength: 1_000 },
  evidence: { type: "string", maxLength: 1_000 },
  confidence: { type: "number", minimum: 0, maximum: 1 },
  human_review_required: { type: "boolean" },
  source_key: { type: "string", enum: [...SOURCE_KEYS] },
  stage: {
    type: "string",
    enum: ["script", "image", "video", "caption", "publish"],
  },
  timecode: nullableStringSchema(64),
});

const RECOMMENDATION_SCHEMA = strictObject({
  code: { type: "string", maxLength: 100 },
  category: {
    type: "string",
    enum: [
      "hook",
      "clarity",
      "product",
      "visual",
      "audio",
      "trust",
      "platform",
      "accessibility",
      "compliance",
    ],
  },
  priority: { type: "string", enum: ["high", "medium", "low"] },
  title: { type: "string", maxLength: 240 },
  detail: { type: "string", maxLength: 1_000 },
  action: { type: "string", maxLength: 1_000 },
  measurement: { type: "string", maxLength: 600 },
  confidence: { type: "number", minimum: 0, maximum: 1 },
});

const REVIEW_SCHEMA = strictObject({
  summary: { type: "string", maxLength: 2_000 },
  overall_score: { type: "integer", minimum: 0, maximum: 100 },
  scores: strictObject({
    technical: { type: "integer", minimum: 0, maximum: 100 },
    product_fidelity: { type: "integer", minimum: 0, maximum: 100 },
    hook_clarity: { type: "integer", minimum: 0, maximum: 100 },
    visual_quality: { type: "integer", minimum: 0, maximum: 100 },
    trust: { type: "integer", minimum: 0, maximum: 100 },
    platform_fit: { type: "integer", minimum: 0, maximum: 100 },
    accessibility: { type: "integer", minimum: 0, maximum: 100 },
  }),
  ad_probability: { type: "number", minimum: 0, maximum: 1 },
  ad_classification_summary: { type: "string", maxLength: 1_000 },
  strengths: {
    type: "array",
    minItems: 1,
    maxItems: 8,
    items: { type: "string", maxLength: 500 },
  },
  findings: {
    type: "array",
    minItems: 0,
    maxItems: 24,
    items: FINDING_SCHEMA,
  },
  recommendations: {
    type: "array",
    minItems: 1,
    maxItems: 12,
    items: RECOMMENDATION_SCHEMA,
  },
  comparison: strictObject({
    previous_score: {
      anyOf: [
        { type: "integer", minimum: 0, maximum: 100 },
        { type: "null" },
      ],
    },
    delta: {
      anyOf: [
        { type: "integer", minimum: -100, maximum: 100 },
        { type: "null" },
      ],
    },
    summary: { type: "string", maxLength: 1_000 },
  }),
  limitations: {
    type: "array",
    minItems: 1,
    maxItems: 10,
    items: { type: "string", maxLength: 600 },
  },
});

function schemaForResponsesApi(): Json {
  const schema = structuredClone(REVIEW_SCHEMA);
  const stripUnsupportedStringBounds = (node: Json): void => {
    if (Array.isArray(node)) {
      node.forEach(stripUnsupportedStringBounds);
      return;
    }
    if (node === null || typeof node !== "object") return;
    delete node.minLength;
    delete node.maxLength;
    Object.values(node).forEach((value) => {
      if (value !== undefined) stripUnsupportedStringBounds(value);
    });
  };
  stripUnsupportedStringBounds(schema);
  return schema;
}

const REVIEW_INSTRUCTIONS = `
Ты — старший редактор UGC, специалист по контролю качества и первичному
комплаенс-скринингу российского товарного контента. Отвечай только по-русски
и строго по JSON-схеме. Ты не даёшь юридическое заключение и не обещаешь
вирусность, просмотры или продажи.

Разделяй две независимые вещи:
1. overall_score и scores — только качество контента;
2. findings — риски публикации. Высокий quality score никогда не отменяет blocker.

Проверяй: понятность первых двух секунд, демонстрацию точного товара, сохранность
упаковки/логотипа/надписей между кадрами, естественность человека и рук,
визуальные AI-артефакты, темп, читаемость, доверие, формат площадки, субтитры,
соответствие текста и визуала, персональные данные и небезопасное применение.

Классификация рекламы — только риск. Товар в центре, крупная упаковка, призыв
купить, артикул, промокод, цена, скидка, ссылка, договор или KPI повышают риск.
Не предлагай маскировать рекламу или обходить маркировку. При спорной границе
ставь human_review_required=true.

Для косметики, еды, протеина и БАД блокируй неподтверждённые лечебные обещания,
гарантии результата и перенос характеристик с другого SKU. Для кислотного
пилинга отдельно проверяй область глаз/губ, повреждённую кожу, время выдержки
и соответствие инструкции. Для протеина сверяй вкус/SKU, белок, BCAA, массу
и число порций; не принимай «быстрый рост мышц» и «гарантированное восстановление».

source_key выбирай только из заданного enum. Если конкретная правовая норма
не нужна или не установлена по кадрам, используй none. AI-обнаружение
правового риска с confidence ниже 0.9 должно требовать человека.

Из видео переданы выборочные кадры, а не полный поток. Аудио не распознано:
оценивай речь только по script_text/caption_text и всегда указывай это
ограничение. Не утверждай, что проверил музыку, весь звук или каждый кадр.
`;

function promptForRun(run: ReviewRun): string {
  const payload = {
    ruleset_version: RULESET_VERSION,
    media: {
      mime_type: run.media.mimeType,
      sha256: run.media.sha256,
      size_bytes: run.media.sizeBytes,
      kind: run.media.metadata.kind ?? null,
      original_filename: run.media.metadata.original_filename ?? null,
    },
    review_input: run.input,
    previous_review_result: run.parentResult,
    legal_source_keys: LEGAL_SOURCE_URLS,
    requested_at: new Date().toISOString(),
  };
  const serialized = JSON.stringify(payload);
  if (new TextEncoder().encode(serialized).byteLength > 240_000) {
    throw new Error("input_too_large");
  }
  return serialized;
}

function openAiRequestBody(run: ReviewRun, imageUrls: string[]): Json {
  const content: Json[] = [
    { type: "input_text", text: promptForRun(run) },
    ...imageUrls.map((imageUrl) => ({
      type: "input_image",
      image_url: imageUrl,
      detail: "high",
    })),
  ];
  return {
    model: openAiModel(),
    instructions: REVIEW_INSTRUCTIONS.trim(),
    input: [{ role: "user", content }],
    text: {
      verbosity: "medium",
      format: {
        type: "json_schema",
        name: "creator_content_review",
        description:
          "Independent content quality score, compliance screening, evidence-backed findings and actionable recommendations.",
        strict: true,
        schema: schemaForResponsesApi(),
      },
    },
    max_output_tokens: MAX_OUTPUT_TOKENS,
    store: false,
  };
}

function moderationRequestBody(run: ReviewRun, imageUrls: string[]): Json {
  const text = [
    String(run.input.caption_text ?? ""),
    String(run.input.script_text ?? ""),
  ].filter(Boolean).join("\n");
  const input: Json[] = [];
  if (text) input.push({ type: "text", text: text.slice(0, 20_000) });
  imageUrls.forEach((url) => {
    input.push({ type: "image_url", image_url: { url } });
  });
  return {
    model: "omni-moderation-latest",
    input: input.length ? input : [{ type: "text", text: "empty content" }],
  };
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

function providerFailureForHttp(status: number): string {
  if (status === 401 || status === 403) return "provider_authentication_failed";
  if (status === 408 || status >= 500) return "provider_outcome_unknown";
  if (status === 429) return "provider_rate_limited";
  if (status >= 400 && status < 500) return "provider_request_rejected";
  return "provider_unavailable";
}

function extractOutputText(value: unknown): string | null {
  if (!isRecord(value) || value.status !== "completed") return null;
  if (
    typeof value.output_text === "string" && value.output_text.length >= 2 &&
    value.output_text.length <= 500_000
  ) return value.output_text;
  if (!Array.isArray(value.output)) return null;
  for (const item of value.output) {
    if (!isRecord(item) || !Array.isArray(item.content)) continue;
    for (const content of item.content) {
      if (
        isRecord(content) &&
        ["output_text", "text"].includes(String(content.type)) &&
        typeof content.text === "string" && content.text.length >= 2 &&
        content.text.length <= 500_000
      ) return content.text;
    }
  }
  return null;
}

function finiteInteger(
  value: unknown,
  minimum: number,
  maximum: number,
): boolean {
  return Number.isSafeInteger(value) && Number(value) >= minimum &&
    Number(value) <= maximum;
}

function finiteNumber(
  value: unknown,
  minimum: number,
  maximum: number,
): boolean {
  return typeof value === "number" && Number.isFinite(value) &&
    value >= minimum && value <= maximum;
}

function textArray(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string[] {
  return Array.isArray(value) && value.length >= minimum &&
    value.length <= maximum &&
    value.every((item) => isBoundedText(item, 1, 1_200));
}

function readModelFinding(value: unknown): Finding | null {
  if (!isRecord(value)) return null;
  const sourceKey = String(value.source_key ?? "none");
  const severity = String(value.severity ?? "");
  if (
    !isBoundedText(value.code, 2, 100) ||
    !isBoundedText(value.category, 2, 40) ||
    !["blocker", "high", "medium", "low", "info"].includes(severity) ||
    !isBoundedText(value.title, 3, 240) ||
    !isBoundedText(value.detail, 3, 1_200) ||
    !isBoundedText(value.action, 3, 1_000) ||
    !isBoundedText(value.evidence, 1, 1_000) ||
    !finiteNumber(value.confidence, 0, 1) ||
    typeof value.human_review_required !== "boolean" ||
    !SOURCE_KEYS.has(sourceKey) ||
    !isBoundedText(value.stage, 3, 20) ||
    (value.timecode !== null &&
      !isBoundedText(value.timecode, 1, 64))
  ) return null;
  let safeSeverity = severity as Finding["severity"];
  if (
    safeSeverity === "blocker" &&
    (Number(value.confidence) < 0.9 ||
      (["legal", "claim"].includes(String(value.category)) &&
        sourceKey === "none"))
  ) safeSeverity = "high";
  const evidence: Record<string, Json> = {
    observed: value.evidence,
  };
  if (sourceKey !== "none") {
    evidence.legal_source_url = LEGAL_SOURCE_URLS[sourceKey] ?? null;
  }
  return {
    code: value.code,
    category: value.category,
    severity: safeSeverity,
    title: value.title,
    detail: value.detail,
    action: value.action,
    evidence,
    confidence: Number(value.confidence),
    human_review_required: value.human_review_required === true ||
      safeSeverity === "high",
    source_key: sourceKey,
    stage: value.stage,
    timecode: value.timecode === null ? null : String(value.timecode),
  };
}

function readModelResult(value: unknown): Record<string, Json> | null {
  if (!isRecord(value)) return null;
  const scores = value.scores;
  const comparison = value.comparison;
  if (
    !isBoundedText(value.summary, 10, 2_000) ||
    !finiteInteger(value.overall_score, 0, 100) ||
    !isRecord(scores) ||
    ![
      "technical",
      "product_fidelity",
      "hook_clarity",
      "visual_quality",
      "trust",
      "platform_fit",
      "accessibility",
    ].every((key) => finiteInteger(scores[key], 0, 100)) ||
    !finiteNumber(value.ad_probability, 0, 1) ||
    !isBoundedText(value.ad_classification_summary, 3, 1_000) ||
    !textArray(value.strengths, 1, 8) ||
    !Array.isArray(value.findings) || value.findings.length > 24 ||
    !Array.isArray(value.recommendations) ||
    value.recommendations.length < 1 || value.recommendations.length > 12 ||
    !isRecord(comparison) ||
    !isBoundedText(comparison.summary, 1, 1_000) ||
    (comparison.previous_score !== null &&
      !finiteInteger(comparison.previous_score, 0, 100)) ||
    (comparison.delta !== null &&
      !finiteInteger(comparison.delta, -100, 100)) ||
    !textArray(value.limitations, 1, 10)
  ) return null;
  const findings: Finding[] = [];
  for (const item of value.findings) {
    const finding = readModelFinding(item);
    if (finding === null) return null;
    findings.push(finding);
  }
  const recommendations: Record<string, Json>[] = [];
  for (const item of value.recommendations) {
    if (
      !isRecord(item) || !isBoundedText(item.code, 2, 100) ||
      !isBoundedText(item.category, 2, 40) ||
      !["high", "medium", "low"].includes(String(item.priority)) ||
      !isBoundedText(item.title, 3, 240) ||
      !isBoundedText(item.detail, 3, 1_000) ||
      !isBoundedText(item.action, 3, 1_000) ||
      !isBoundedText(item.measurement, 3, 600) ||
      !finiteNumber(item.confidence, 0, 1)
    ) return null;
    recommendations.push(item as Record<string, Json>);
  }
  return {
    summary: value.summary as string,
    overall_score: value.overall_score as number,
    scores: scores as Record<string, Json>,
    ad_probability: value.ad_probability as number,
    ad_classification_summary: value.ad_classification_summary as string,
    strengths: value.strengths as string[],
    findings: findings as unknown as Json[],
    recommendations,
    comparison: comparison as Record<string, Json>,
    limitations: value.limitations as string[],
  };
}

function boolInput(input: Record<string, Json>, key: string): boolean {
  return input[key] === true;
}

function stringInput(input: Record<string, Json>, key: string): string {
  return typeof input[key] === "string" ? String(input[key]).trim() : "";
}

function numericMetric(
  metrics: Record<string, Json>,
  key: string,
): number | null {
  const value = metrics[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function makeFinding(
  code: string,
  category: string,
  severity: Finding["severity"],
  title: string,
  detail: string,
  action: string,
  options: {
    evidence?: Record<string, Json>;
    confidence?: number;
    human?: boolean;
    sourceKey?: string;
    stage?: string;
    timecode?: string | null;
  } = {},
): Finding {
  const sourceKey = SOURCE_KEYS.has(options.sourceKey ?? "")
    ? String(options.sourceKey)
    : "none";
  const evidence = { ...(options.evidence ?? {}) };
  if (sourceKey !== "none") {
    evidence.legal_source_url = LEGAL_SOURCE_URLS[sourceKey] ?? null;
  }
  return {
    code,
    category,
    severity,
    title,
    detail,
    action,
    evidence,
    confidence: Math.max(0, Math.min(1, options.confidence ?? 1)),
    human_review_required: options.human === true || severity === "high",
    source_key: sourceKey,
    stage: options.stage ?? "publish",
    timecode: options.timecode ?? null,
  };
}

function deterministicFindings(run: ReviewRun, frameCount: number): Finding[] {
  const input = run.input;
  const metrics = isRecord(input.technical_metrics)
    ? input.technical_metrics as Record<string, Json>
    : {};
  const findings: Finding[] = [];
  const add = (finding: Finding): void => {
    if (!findings.some((item) => item.code === finding.code)) {
      findings.push(finding);
    }
  };
  const platform = stringInput(input, "platform");
  const contentKind = stringInput(input, "content_kind");
  const category = stringInput(input, "product_category");
  const script = stringInput(input, "script_text");
  const caption = stringInput(input, "caption_text");
  const combinedText = `${script}\n${caption}`.toLocaleLowerCase("ru-RU");

  if (
    run.media.metadata.kind === "generated_video" && (
      input.product_category_verified !== true ||
      stringInput(input, "product_category_source") !== "product_metadata" ||
      contentKind !== "advertising" ||
      input.ai_generated !== true ||
      !isUuid(input.generation_job_id)
    )
  ) {
    add(makeFinding(
      "CONTEXT.GENERATED_PROVENANCE",
      "legal",
      "blocker",
      "Контекст сгенерированного ролика не подтверждён сервером",
      "Площадка, категория товара, рекламный статус или AI-происхождение не связаны с исходным заданием генерации.",
      "Не публикуйте ролик. Создайте новую проверку из карточки точного задания и товара.",
      { human: true, stage: "publish" },
    ));
  }

  if (contentKind === "unknown" || contentKind === "") {
    add(makeFinding(
      "AD.STATUS_UNRESOLVED",
      "legal",
      "high",
      "Не определён рекламный статус",
      "По одному слову или отсутствию слова «купить» нельзя надёжно отличить личную рекомендацию от рекламы.",
      "Руководитель должен оценить весь материал, отношения с продавцом, ТЗ, оплату, ссылку и призыв к действию.",
      {
        human: true,
        sourceKey: "ad_definition_1087",
        stage: "publish",
      },
    ));
  }

  if (contentKind === "advertising") {
    if (platform === "instagram" || platform === "facebook") {
      add(makeFinding(
        "PLATFORM.RESTRICTED_RESOURCE",
        "legal",
        "blocker",
        "Рекламу на этой площадке публиковать нельзя",
        "Материал заявлен рекламой и направлен на ресурс, для которого действует запрет рекламы в РФ.",
        "Не маскируйте рекламу под рекомендацию. Выберите разрешённую площадку и заново проведите проверку.",
        {
          sourceKey: "restricted_resources_72fz",
          stage: "publish",
        },
      ));
    }
    if (!boolInput(input, "ad_label_confirmed")) {
      add(makeFinding(
        "AD.MARKING.LABEL",
        "legal",
        "blocker",
        "Нет подтверждения пометки «Реклама»",
        "Для интернет-рекламы одного интерфейсного бейджа площадки недостаточно.",
        "Добавьте и визуально проверьте обязательную пометку до публикации.",
        { sourceKey: "ad_law_38fz", stage: "publish" },
      ));
    }
    if (stringInput(input, "advertiser_name").length < 2) {
      add(makeFinding(
        "AD.MARKING.ADVERTISER",
        "legal",
        "blocker",
        "Не указан рекламодатель",
        "В карточке проверки отсутствуют сведения о рекламодателе или ссылка на них.",
        "Получите точные реквизиты у руководителя и повторите проверку.",
        { sourceKey: "ad_law_38fz", stage: "publish" },
      ));
    }
    if (stringInput(input, "erid").length < 6) {
      add(makeFinding(
        "AD.MARKING.ERID",
        "legal",
        "blocker",
        "Нет идентификатора рекламы",
        "ERID не указан или выглядит неполным.",
        "Получите токен ОРД именно для этого креатива и договора.",
        { sourceKey: "erid_order_68", stage: "publish" },
      ));
    }
    if (!boolInput(input, "ord_confirmed")) {
      add(makeFinding(
        "AD.ORD_ACK",
        "legal",
        "blocker",
        "Постановка рекламы на учёт не подтверждена",
        "Наличие похожей строки ERID не доказывает её связь с креативом и ОРД.",
        "Сверьте токен, договор и подтверждение ОРД до экспорта.",
        { sourceKey: "ord_rules_974", stage: "publish" },
      ));
    }
    if (
      boolInput(input, "audience_over_10000") &&
      !boolInput(input, "rkn_registered")
    ) {
      add(makeFinding(
        "PUBLISHER.RKN_10K",
        "legal",
        "blocker",
        "Крупная страница не подтверждена в перечне Роскомнадзора",
        "Для страницы с аудиторией более 10 тысяч нет подтверждения регистрации.",
        "Проверьте страницу в перечне и сохраните подтверждение в задаче.",
        { sourceKey: "publisher_registry_238", stage: "publish" },
      ));
    }
    if (
      ["youtube", "telegram"].includes(platform)
    ) {
      add(makeFinding(
        "PLATFORM.CURRENT_STATUS_REVIEW",
        "platform",
        "high",
        "Нужна актуальная проверка статуса площадки",
        "Правоприменение для ограниченных ресурсов меняется; автоматический модуль не заменяет решение ответственного на дату публикации.",
        "Перед публикацией сверьте свежие официальные разъяснения и решение руководителя.",
        {
          human: true,
          sourceKey: "restricted_resources_72fz",
          stage: "publish",
        },
      ));
    }
  }

  if (!boolInput(input, "rights_confirmed")) {
    add(makeFinding(
      "RIGHTS.MEDIA",
      "rights",
      "blocker",
      "Права на материалы не подтверждены",
      "Нет подтверждения прав на исходники, музыку, фото, видео или товарные элементы.",
      "Получите лицензию/разрешение и сохраните доказательство до публикации.",
      { human: true, stage: "publish" },
    ));
  }

  const peoplePresent = stringInput(input, "people_present");
  if (
    peoplePresent === "yes" && !boolInput(input, "person_consent_confirmed")
  ) {
    add(makeFinding(
      "PERSON.IMAGE_RELEASE",
      "rights",
      "blocker",
      "Нет согласия человека в кадре",
      "Для узнаваемого человека не подтверждены съёмка, коммерческое использование и распространение изображения.",
      "Получите отдельное согласие либо замените кадры.",
      {
        human: true,
        sourceKey: "image_rights_152_1",
        stage: "video",
      },
    ));
  } else if (peoplePresent === "unknown" || peoplePresent === "") {
    add(makeFinding(
      "PERSON.PRESENCE_UNRESOLVED",
      "privacy",
      "high",
      "Люди и персональные данные требуют ручной сверки",
      "Автор не подтвердил, есть ли в материале узнаваемые люди, документы, экраны или контакты.",
      "Просмотрите весь ролик покадрово и зафиксируйте согласия.",
      {
        human: true,
        sourceKey: "personal_data_152fz",
        stage: "video",
      },
    ));
  }

  if (!boolInput(input, "claims_verified")) {
    add(makeFinding(
      "CLAIM.SOURCE_NOT_CONFIRMED",
      "claim",
      "high",
      "Факты о товаре не сверены с разрешённым источником",
      "Состав, цифры, цена, эффект и способ применения могут относиться к другому SKU или устареть.",
      "Сверьте каждое утверждение с этикеткой, документами производителя и актуальной карточкой.",
      { human: true, stage: "script" },
    ));
  }

  if (
    boolInput(input, "ai_generated") && platform === "youtube" &&
    !boolInput(input, "ai_disclosure_confirmed")
  ) {
    add(makeFinding(
      "YOUTUBE.AI_DISCLOSURE",
      "platform",
      "blocker",
      "Не подтверждено раскрытие синтетического контента",
      "Реалистичный AI-блогер или изменённая сцена для YouTube требуют отметки altered content.",
      "Включите раскрытие синтетического контента при загрузке и сохраните подтверждение.",
      { sourceKey: "youtube_synthetic", stage: "publish" },
    ));
  }

  if (script.length >= 10 && !boolInput(input, "captions_confirmed")) {
    add(makeFinding(
      "ACCESSIBILITY.CAPTIONS",
      "accessibility",
      "medium",
      "Субтитры не подтверждены",
      "В ролике есть речь по сценарию, но читаемые субтитры не отмечены.",
      "Добавьте субтитры, проверьте синхронизацию и безопасные поля интерфейса.",
      { stage: "video" },
    ));
  }

  if (
    category === "baa" && contentKind === "advertising" &&
    !boolInput(input, "mandatory_warning_confirmed")
  ) {
    add(makeFinding(
      "BAA.DISCLAIMER",
      "legal",
      "blocker",
      "Не подтверждено обязательное предупреждение для БАД",
      "Для рекламного ролика БАД не отмечено предупреждение «Не является лекарственным средством» с требуемой длительностью и площадью.",
      "Добавьте предупреждение по действующим требованиям и измерьте его время и площадь в кадре.",
      { sourceKey: "ad_law_38fz", stage: "video" },
    ));
  }

  const therapeuticPattern =
    /\b(лечит|вылечит|излечивает|избавляет от (акне|дерматита|розацеа|болезн)|восстанавливает сустав|нормализует давление|лечебн)\b/iu;
  const guaranteePattern =
    /\b(100\s*%|гарантированн|без побочн|безопасн[оаяые]* для всех|навсегда|мгновенный результат)\b/iu;
  const musclePattern =
    /\b(быстр(ый|ого) рост мышц|гарантированн\w* восстановлен|сжигает жир|заменяет полноценное питание)\b/iu;
  if (
    therapeuticPattern.test(combinedText) || musclePattern.test(combinedText)
  ) {
    add(makeFinding(
      "CLAIM.THERAPEUTIC_NONMEDICAL",
      "claim",
      "blocker",
      "Обнаружено лечебное или физиологическое обещание",
      "Текст приписывает косметике, еде, протеину или БАД лечебный/гарантированный эффект.",
      "Удалите обещание и используйте только дословно подтверждённое свойство конкретного SKU.",
      {
        sourceKey: category === "cosmetics"
          ? "cosmetics_tr_ts_009"
          : "food_label_tr_ts_022",
        stage: script ? "script" : "caption",
      },
    ));
  }
  if (guaranteePattern.test(combinedText)) {
    add(makeFinding(
      "CLAIM.GUARANTEE",
      "claim",
      "blocker",
      "Обнаружена гарантия результата или абсолютной безопасности",
      "Абсолютная формулировка создаёт недоказуемое ожидание результата.",
      "Удалите гарантию и опишите проверяемую характеристику без универсального обещания.",
      { sourceKey: "ad_law_38fz", stage: script ? "script" : "caption" },
    ));
  }

  const width = numericMetric(metrics, "width");
  const height = numericMetric(metrics, "height");
  const duration = numericMetric(metrics, "duration_seconds");
  const blackRatio = numericMetric(metrics, "black_frame_ratio");
  const frozenRatio = numericMetric(metrics, "frozen_frame_ratio");
  if (run.media.mimeType === "video/mp4") {
    add(makeFinding(
      "SCOPE.BROWSER_FRAMES_ADVISORY",
      "quality",
      "info",
      "Контрольные кадры являются вспомогательной выборкой",
      "Автоматический анализ видит ограниченную выборку кадров из браузера, а не декодирует весь точный MP4 на сервере.",
      "Перед решением полностью воспроизведите защищённый исходник, проверьте монтаж, звук, титры и отсутствие подмены файла.",
      { human: true, confidence: 1, stage: "video" },
    ));
    if (frameCount < MIN_VIDEO_FRAMES) {
      add(makeFinding(
        "TECH.FRAMES_INCOMPLETE",
        "technical",
        "high",
        "Не удалось получить достаточно контрольных кадров",
        "Выборка слишком мала для устойчивой визуальной проверки.",
        "Откройте исходный MP4, убедитесь, что он воспроизводится, и запустите новую проверку.",
        { human: true, stage: "video" },
      ));
    }
    if (width === null || height === null || duration === null) {
      add(makeFinding(
        "TECH.METADATA_MISSING",
        "technical",
        "high",
        "Технические параметры видео не подтверждены",
        "Портал не получил длительность или размер кадра.",
        "Проверьте декодирование MP4 вручную и повторите анализ.",
        { human: true, stage: "video" },
      ));
    } else {
      const verticalPlatform = ["instagram", "youtube", "vk", "tiktok"]
        .includes(
          platform,
        );
      if (verticalPlatform && width / height > 0.72) {
        add(makeFinding(
          "TECH.ASPECT_RATIO",
          "technical",
          "medium",
          "Формат не похож на вертикальный 9:16",
          `Получено ${Math.round(width)}×${
            Math.round(height)
          } для вертикальной площадки.`,
          "Подготовьте вертикальный мастер 9:16 и проверьте безопасные поля.",
          {
            evidence: { width, height },
            stage: "video",
          },
        ));
      }
      if (verticalPlatform && (width < 720 || height < 1_280)) {
        add(makeFinding(
          "TECH.RESOLUTION_LOW",
          "technical",
          "medium",
          "Разрешение ниже рабочего минимума",
          `Получено ${Math.round(width)}×${Math.round(height)}.`,
          "Экспортируйте не ниже 720×1280, лучше 1080×1920.",
          { evidence: { width, height }, stage: "video" },
        ));
      }
      if (duration < 3 || duration > 90) {
        add(makeFinding(
          "TECH.DURATION",
          "platform",
          "medium",
          "Длительность требует сверки с форматом",
          `Портал определил ${duration.toFixed(1)} сек.`,
          "Сверьте длительность с задачей и ограничениями выбранного формата.",
          { evidence: { duration_seconds: duration }, stage: "video" },
        ));
      }
    }
    if (blackRatio !== null && blackRatio >= 0.25) {
      add(makeFinding(
        "TECH.BLACK_FRAMES",
        "technical",
        "blocker",
        "Слишком много почти чёрных кадров",
        `Доля проблемных контрольных кадров: ${Math.round(blackRatio * 100)}%.`,
        "Пересоберите видео и проверьте декодирование всего файла.",
        { evidence: { black_frame_ratio: blackRatio }, stage: "video" },
      ));
    }
    if (frozenRatio !== null && frozenRatio >= 0.8) {
      add(makeFinding(
        "TECH.FROZEN_VIDEO",
        "technical",
        "high",
        "Видео похоже на статичный или зависший кадр",
        `Сходство контрольных кадров: ${Math.round(frozenRatio * 100)}%.`,
        "Проверьте весь ролик и повторите экспорт, если движение потеряно.",
        {
          evidence: { frozen_frame_ratio: frozenRatio },
          human: true,
          stage: "video",
        },
      ));
    }
    add(makeFinding(
      "SCOPE.AUDIO_MANUAL_REVIEW",
      "quality",
      "info",
      "Звук нужно прослушать вручную",
      "Автоматическая проверка анализирует контрольные кадры и введённый текст, но не расшифровывает весь звук MP4.",
      "Прослушайте реплику, музыку, клиппинг и совпадение субтитров перед решением.",
      { human: true, confidence: 1, stage: "video" },
    ));
  }
  return findings;
}

function readModeration(value: unknown): Record<string, Json> {
  if (
    !isRecord(value) || !Array.isArray(value.results) || !value.results.length
  ) {
    return { status: "unavailable", flagged: false, categories: [] };
  }
  const result = value.results[0];
  if (!isRecord(result)) {
    return { status: "unavailable", flagged: false, categories: [] };
  }
  const categories: string[] = [];
  if (isRecord(result.categories)) {
    Object.entries(result.categories).forEach(([key, flagged]) => {
      if (flagged === true && key.length <= 80) categories.push(key);
    });
  }
  return {
    status: "completed",
    flagged: result.flagged === true,
    categories,
  };
}

function mergeReviewResult(
  run: ReviewRun,
  modelResult: Record<string, Json>,
  moderation: Record<string, Json>,
  frameCount: number,
): Record<string, Json> {
  const findings = [
    ...deterministicFindings(run, frameCount),
    ...((modelResult.findings as unknown as Finding[]) ?? []),
  ];
  const adProbability = Number(modelResult.ad_probability);
  if (
    Number.isFinite(adProbability) && adProbability >= 0.65 &&
    stringInput(run.input, "content_kind") !== "advertising"
  ) {
    findings.push(makeFinding(
      "AD.CLASSIFICATION_CONFLICT",
      "legal",
      "high",
      "Признаки рекламы расходятся с заявленным статусом",
      `Модель оценила вероятность рекламного характера в ${
        Math.round(adProbability * 100)
      }%, хотя материал не заявлен рекламой.`,
      "Не пытайтесь обходить маркировку. Перед публикацией руководитель должен квалифицировать весь контекст, а при рекламе добавить требуемые сведения и ERID.",
      { human: true, sourceKey: "ad_definition_1087", stage: "publish" },
    ));
  }
  if (moderation.status === "unavailable") {
    findings.push(makeFinding(
      "SAFETY.MODERATION_UNAVAILABLE",
      "safety",
      "high",
      "Автоматическая проверка чувствительного контента недоступна",
      "Специализированный классификатор безопасности не вернул подтверждённый результат.",
      "Проверяющий должен вручную исключить насилие, сексуальный контент, ненависть, самоповреждение и опасные сцены.",
      { human: true, stage: "video" },
    ));
  } else if (moderation.flagged === true) {
    findings.push(makeFinding(
      "SAFETY.MODERATION",
      "safety",
      "blocker",
      "Классификатор безопасности обнаружил риск",
      "Категории: " +
        ((moderation.categories as string[]) ?? []).slice(0, 8).join(", "),
      "Не публикуйте материал до ручного разбора и замены проблемных фрагментов.",
      {
        evidence: {
          categories: (moderation.categories as string[]) ?? [],
        },
        human: true,
        stage: "video",
      },
    ));
  }

  const deduplicated = new Map<string, Finding>();
  for (const finding of findings) {
    const existing = deduplicated.get(finding.code);
    const ranks = { blocker: 5, high: 4, medium: 3, low: 2, info: 1 };
    if (!existing || ranks[finding.severity] > ranks[existing.severity]) {
      deduplicated.set(finding.code, finding);
    }
  }
  const finalFindings = [...deduplicated.values()].slice(0, 40);
  const blockers = finalFindings.filter((item) => item.severity === "blocker");
  const warnings = finalFindings.filter((item) =>
    ["high", "medium"].includes(item.severity)
  );
  const complianceStatus = blockers.length ? "block" : warnings.length ||
      finalFindings.some((item) => item.human_review_required)
    ? "human_review"
    : "pass_with_warnings";

  const recommendations = [
    ...((modelResult.recommendations as Record<string, Json>[]) ?? []),
  ];
  for (const finding of finalFindings) {
    const code = `FIX.${finding.code}`.slice(0, 100);
    if (recommendations.some((item) => item.code === code)) continue;
    recommendations.push({
      code,
      category: ["legal", "claim", "rights", "privacy", "safety"].includes(
          finding.category,
        )
        ? "compliance"
        : finding.category === "technical"
        ? "visual"
        : "clarity",
      priority: ["blocker", "high"].includes(finding.severity)
        ? "high"
        : finding.severity === "medium"
        ? "medium"
        : "low",
      title: finding.title,
      detail: finding.detail,
      action: finding.action,
      measurement: finding.severity === "blocker"
        ? "Повторная проверка не содержит этого blocker"
        : "Проверяющий подтвердил исправление в новой версии",
      confidence: finding.confidence,
    });
  }

  const previousScore = run.parentResult &&
      finiteInteger(run.parentResult.overall_score, 0, 100)
    ? Number(run.parentResult.overall_score)
    : null;
  const currentScore = Number(modelResult.overall_score);
  const comparison = previousScore === null
    ? {
      previous_score: null,
      delta: null,
      summary:
        "Это первая связанная проверка; сравнение появится после новой версии.",
    }
    : {
      previous_score: previousScore,
      delta: currentScore - previousScore,
      summary: currentScore > previousScore
        ? `Оценка качества выросла на ${currentScore - previousScore} п.`
        : currentScore < previousScore
        ? `Оценка качества снизилась на ${previousScore - currentScore} п.`
        : "Оценка качества не изменилась; сравните конкретные замечания.",
    };

  return {
    overall_score: currentScore,
    scores: modelResult.scores as Record<string, Json>,
    ad_probability: adProbability,
    ad_classification_summary: String(modelResult.ad_classification_summary),
    compliance_status: complianceStatus,
    blockers_count: blockers.length,
    warnings_count: warnings.length,
    strengths: modelResult.strengths as string[],
    findings: finalFindings as unknown as Json[],
    recommendations: recommendations.slice(0, 24),
    comparison,
    limitations: modelResult.limitations as string[],
  };
}

function readPublicStatusEnvelope(
  value: unknown,
  expectedId: string,
): { data: Json; status: ReviewRun["status"] } | null {
  if (
    !isRecord(value) || value.ok !== true || !isRecord(value.run) ||
    value.run.id !== expectedId || typeof value.run.status !== "string" ||
    !RUN_STATUSES.has(value.run.status)
  ) return null;
  return {
    data: value as Json,
    status: value.run.status as ReviewRun["status"],
  };
}

const CREATOR_CONTENT_REVIEW_USER_OPTIONS = {
  auth: "user",
  cors: {
    "Access-Control-Allow-Headers":
      "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Origin": PUBLIC_APP_ORIGIN,
    Vary: "Origin",
  },
} as const;

const CREATOR_CONTENT_REVIEW_WORKER_OPTIONS = {
  auth: "none",
  cors: false,
} as const;

async function handleCreatorContentReview(
  request: Request,
  context: SupabaseContext<ContentEngineDatabase>,
  internalWorker: boolean,
): Promise<Response> {
  if (internalWorker && !(await isInternalWorkerAuthorized(request))) {
    return json(request, { ok: false, code: "authentication_required" }, 401);
  }
  const supabaseAdmin = context.supabaseAdmin;
  if (request.method !== "POST") {
    return json(request, { ok: false, code: "method_not_allowed" }, 405);
  }
  if (
    (!internalWorker &&
      request.headers.get("origin") !== PUBLIC_APP_ORIGIN) ||
    (internalWorker && request.headers.get("origin") !== null)
  ) {
    return json(request, { ok: false, code: "origin_not_allowed" }, 403);
  }
  if (
    internalWorker &&
    request.headers.get(INTERNAL_WORKER_HEADER) !== "1"
  ) {
    return json(
      request,
      { ok: false, code: "worker_request_required" },
      403,
    );
  }
  const contentType = request.headers.get("content-type") ?? "";
  if (
    !contentType.toLocaleLowerCase("en-US").startsWith("application/json")
  ) {
    return json(request, { ok: false, code: "content_type_invalid" }, 415);
  }
  const contentLength = Number(
    request.headers.get("content-length") ?? "0",
  );
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  if (!internalWorker && !context.userClaims?.id) {
    return json(
      request,
      { ok: false, code: "authentication_required" },
      401,
    );
  }

  let body: unknown;
  try {
    const bytes = await readBoundedStream(request.body, MAX_BODY_BYTES);
    body = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    );
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }
  const payload = readRequestPayload(body);
  if (payload === null) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }

  const readCurrentStatus = async (): Promise<
    { data: Json; status: ReviewRun["status"] } | null
  > => {
    if (internalWorker) {
      try {
        const { data, error } = await supabaseAdmin
          .schema("content_factory")
          .from("content_review_runs")
          .select("id, status")
          .eq("id", payload.review_id)
          .maybeSingle();
        if (error || data === null) return null;
        return readPublicStatusEnvelope({
          ok: true,
          run: { id: data.id, status: data.status },
        }, payload.review_id);
      } catch {
        return null;
      }
    }
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_content_review_status",
        { p_payload: { review_id: payload.review_id } },
      );
      if (error) return null;
      return readPublicStatusEnvelope(data, payload.review_id);
    } catch {
      return null;
    }
  };
  const complete = async (
    completionPayload: Record<string, Json>,
  ): Promise<boolean> => {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const { data, error } = await supabaseAdmin.rpc(
          "system_complete_content_review",
          { p_payload: completionPayload },
        );
        if (error === null && isRecord(data) && data.ok === true) {
          return true;
        }
      } catch {
        // Idempotent completion retry; the provider call is never repeated.
      }
    }
    return false;
  };
  const release = async (
    attempt: ReviewAttempt,
    code: string,
    message: string,
  ): Promise<boolean> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_release_content_review_attempt",
        {
          p_payload: {
            review_id: payload.review_id,
            attempt_id: attempt.id,
            lease_token: attempt.leaseToken,
            error_code: code,
            error_message: message.slice(0, 2_000),
            retryable: true,
          },
        },
      );
      return error === null && isRecord(data) && data.ok === true;
    } catch {
      return false;
    }
  };
  const beginProviderDispatch = async (
    attempt: ReviewAttempt,
  ): Promise<"acquired" | "already_started" | "failed"> => {
    for (let rpcAttempt = 0; rpcAttempt < 2; rpcAttempt += 1) {
      try {
        const { data, error } = await supabaseAdmin.rpc(
          "system_begin_content_review_provider_dispatch",
          {
            p_payload: {
              review_id: payload.review_id,
              attempt_id: attempt.id,
              lease_token: attempt.leaseToken,
            },
          },
        );
        if (
          error === null && isRecord(data) && data.ok === true &&
          data.provider_dispatch_started === true
        ) {
          return data.idempotent === true ? "already_started" : "acquired";
        }
      } catch {
        // The marker RPC is idempotent for this attempt and lease.
      }
    }
    return "failed";
  };
  const refreshedResponse = async (): Promise<Response> => {
    const current = await readCurrentStatus();
    return current === null
      ? json(
        request,
        { ok: false, code: "content_review_unavailable" },
        503,
      )
      : json(
        request,
        current.data,
        current.status === "processing" ? 202 : 200,
      );
  };

  const authorized = await readCurrentStatus();
  if (authorized === null) {
    return json(
      request,
      { ok: false, code: "content_review_rejected" },
      403,
    );
  }
  if (authorized.status !== "queued") {
    return json(
      request,
      authorized.data,
      authorized.status === "processing" ? 202 : 200,
    );
  }

  let activeAttempt: ReviewAttempt | null = null;
  let providerDispatchStarted = false;
  let activeProviderRequestId: string | null = null;
  const fail = async (code: string, message: string): Promise<Response> => {
    if (activeAttempt === null) {
      return json(
        request,
        { ok: false, code: "content_review_unavailable" },
        503,
      );
    }
    if (!providerDispatchStarted) {
      if (!(await release(activeAttempt, code, message))) {
        return json(
          request,
          { ok: false, code: "content_review_unavailable" },
          503,
        );
      }
      return await refreshedResponse();
    }
    const completionPayload: Record<string, Json> = {
      review_id: payload.review_id,
      attempt_id: activeAttempt.id,
      lease_token: activeAttempt.leaseToken,
      status: "failed",
      error_code: PROVIDER_FAILURE_CODES.has(code) ? code : "internal_error",
      error_message: message.slice(0, 2_000),
    };
    if (activeProviderRequestId !== null) {
      completionPayload.provider_request_id = activeProviderRequestId;
    }
    if (!(await complete(completionPayload))) {
      return json(
        request,
        { ok: false, code: "content_review_unavailable" },
        503,
      );
    }
    return await refreshedResponse();
  };

  let claim: ReturnType<typeof readClaimEnvelope> = null;
  try {
    const { data, error } = await supabaseAdmin.rpc(
      "system_claim_content_review",
      { p_payload: { review_id: payload.review_id } },
    );
    if (!error) claim = readClaimEnvelope(data);
  } catch {
    claim = null;
  }
  if (claim === null || claim.run.id !== payload.review_id) {
    return await refreshedResponse();
  }
  if (!claim.claimed) {
    const current = await readCurrentStatus();
    return current === null
      ? json(
        request,
        { ok: false, code: "content_review_unavailable" },
        503,
      )
      : json(
        request,
        current.data,
        current.status === "processing" ? 202 : 200,
      );
  }
  if (claim.attempt === null) {
    return json(
      request,
      { ok: false, code: "content_review_unavailable" },
      503,
    );
  }
  const attempt = claim.attempt;
  activeAttempt = attempt;
  if (claim.run.status !== "queued" && claim.run.status !== "processing") {
    return await fail(
      "internal_error",
      "Не удалось зафиксировать запуск проверки.",
    );
  }
  if (
    claim.run.media.mimeType === "video/mp4" &&
    (claim.evidence === null ||
      claim.evidence.frames.length < MIN_VIDEO_FRAMES ||
      claim.evidence.frames.length > MAX_VIDEO_FRAMES)
  ) {
    return await fail(
      "input_validation_failed",
      `Для видео нужны минимум ${MIN_VIDEO_FRAMES} контрольных кадра.`,
    );
  }

  if (
    stringInput(claim.run.input, "people_present") !== "no" &&
    !boolInput(claim.run.input, "external_ai_processing_confirmed")
  ) {
    return await fail(
      "external_ai_processing_basis_required",
      "Контрольные кадры с узнаваемыми людьми не отправлены внешнему AI-провайдеру. Подтвердите законное основание и информирование либо используйте ручную проверку.",
    );
  }

  const apiKey = openAiSecret();
  if (apiKey === null) {
    return await fail(
      "provider_configuration_error",
      "Сервис проверки временно не настроен.",
    );
  }

  const imageUrls: string[] = [];
  if (claim.run.media.mimeType.startsWith("image/")) {
    try {
      const { data, error } = await supabaseAdmin.storage.from(
        STORAGE_BUCKET,
      ).createSignedUrl(
        claim.run.media.objectName,
        SIGNED_IMAGE_TTL_SECONDS,
      );
      const signedUrl = error
        ? null
        : validateSignedStorageUrl(data?.signedUrl);
      if (signedUrl === null) {
        return await fail(
          "image_access_failed",
          "Не удалось безопасно открыть изображение.",
        );
      }
      imageUrls.push(signedUrl);
    } catch {
      return await fail(
        "image_access_failed",
        "Не удалось безопасно открыть изображение.",
      );
    }
  } else {
    const evidence = claim.evidence;
    if (evidence === null) {
      return await fail(
        "input_validation_failed",
        "Сохранённый набор контрольных кадров недоступен.",
      );
    }
    let actualTotalBytes = 0;
    for (const frame of evidence.frames) {
      if (!frame.objectName.startsWith(`${claim.run.organizationId}/`)) {
        return await fail(
          "input_validation_failed",
          "Контрольный кадр не принадлежит рабочему пространству проверки.",
        );
      }
      try {
        const { data: frameBlob, error: downloadError } = await supabaseAdmin
          .storage.from(STORAGE_BUCKET).download(frame.objectName);
        const normalizedMime = frameBlob?.type.toLowerCase().trim() ?? "";
        if (
          downloadError || frameBlob === null ||
          normalizedMime !== "image/jpeg" ||
          frameBlob.size !== frame.sizeBytes ||
          frameBlob.size < 128 || frameBlob.size > MAX_FRAME_BYTES
        ) {
          return await fail(
            "image_access_failed",
            "Один из сохранённых контрольных кадров недоступен или изменён.",
          );
        }
        actualTotalBytes += frameBlob.size;
        if (actualTotalBytes > MAX_TOTAL_FRAME_BYTES) {
          return await fail(
            "input_validation_failed",
            "Общий размер контрольных кадров превышает безопасный предел.",
          );
        }
        const frameBytes = new Uint8Array(await frameBlob.arrayBuffer());
        if (
          frameBytes.byteLength !== frame.sizeBytes || !isJpeg(frameBytes) ||
          (await sha256Hex(frameBytes)) !== frame.sha256
        ) {
          return await fail(
            "input_validation_failed",
            "Контрольный кадр повреждён или не совпадает с зафиксированным хешем.",
          );
        }
        imageUrls.push(jpegDataUrl(frameBytes));
      } catch {
        return await fail(
          "image_access_failed",
          "Не удалось проверить сохранённый контрольный кадр.",
        );
      }
    }
  }
  if (!imageUrls.length) {
    return await fail(
      "input_validation_failed",
      "Для визуальной проверки нет контрольных изображений.",
    );
  }

  const model = openAiModel();
  let providerBody: string;
  let moderationBody: string;
  try {
    providerBody = JSON.stringify(openAiRequestBody(claim.run, imageUrls));
    moderationBody = JSON.stringify(
      moderationRequestBody(claim.run, imageUrls),
    );
  } catch {
    return await fail(
      "input_validation_failed",
      "Не удалось безопасно подготовить запрос проверки.",
    );
  }
  const dispatchState = await beginProviderDispatch(attempt);
  if (dispatchState === "failed") {
    return await fail(
      "internal_error",
      "Не удалось зафиксировать отправку запроса провайдеру.",
    );
  }
  if (dispatchState === "already_started") {
    // Another browser/worker invocation owns the irreversible provider POST.
    // Observers must never repeat it, even though the provider idempotency key
    // is also present as a final line of defence.
    return await refreshedResponse();
  }
  providerDispatchStarted = true;
  const providerPromise = fetchWithTimeout(
    OPENAI_RESPONSES_URL,
    {
      method: "POST",
      redirect: "manual",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
        "idempotency-key": attempt.providerIdempotencyKey,
        "X-Client-Request-Id": attempt.id,
      },
      body: providerBody,
    },
    OPENAI_TIMEOUT_MS,
  );
  const moderationPromise = fetchWithTimeout(
    OPENAI_MODERATIONS_URL,
    {
      method: "POST",
      redirect: "manual",
      headers: {
        authorization: `Bearer ${apiKey}`,
        "content-type": "application/json",
      },
      body: moderationBody,
    },
    OPENAI_TIMEOUT_MS,
  );

  let moderation: Record<string, Json> = {
    status: "unavailable",
    flagged: false,
    categories: [],
  };
  const [providerSettled, moderationSettled] = await Promise.allSettled([
    providerPromise,
    moderationPromise,
  ]);
  if (providerSettled.status === "rejected") {
    return await fail(
      "provider_outcome_unknown",
      UNKNOWN_PROVIDER_OUTCOME_MESSAGE,
    );
  }
  const providerResponse = providerSettled.value;
  activeProviderRequestId = providerRequestId(providerResponse);
  if (moderationSettled.status === "fulfilled") {
    const moderationResponse = moderationSettled.value;
    if (moderationResponse.ok) {
      try {
        moderation = readModeration(
          await readProviderJson(moderationResponse),
        );
      } catch {
        moderation = {
          status: "unavailable",
          flagged: false,
          categories: [],
        };
      }
    } else {
      await moderationResponse.body?.cancel();
    }
  }

  if (!providerResponse.ok) {
    const failureCode = providerFailureForHttp(providerResponse.status);
    await providerResponse.body?.cancel();
    return await fail(
      failureCode,
      failureCode === "provider_outcome_unknown"
        ? UNKNOWN_PROVIDER_OUTCOME_MESSAGE
        : "Сервис проверки отклонил запрос.",
    );
  }
  let providerValue: unknown;
  try {
    providerValue = await readProviderJson(providerResponse);
  } catch {
    return await fail(
      "provider_response_invalid",
      "Сервис проверки вернул неполный результат.",
    );
  }
  activeProviderRequestId = providerRequestId(
    providerResponse,
    providerValue,
  );
  const outputText = extractOutputText(providerValue);
  if (outputText === null) {
    return await fail(
      "provider_response_invalid",
      "Сервис проверки не вернул структурированный ответ.",
    );
  }
  let outputValue: unknown;
  try {
    outputValue = JSON.parse(outputText);
  } catch {
    return await fail(
      "provider_response_invalid",
      "Сервис проверки вернул результат в неверном формате.",
    );
  }
  const modelResult = readModelResult(outputValue);
  if (modelResult === null) {
    return await fail(
      "provider_response_invalid",
      "Структура рекомендаций не прошла проверку.",
    );
  }
  const result = mergeReviewResult(
    claim.run,
    modelResult,
    moderation,
    imageUrls.length,
  );
  const completionPayload: Record<string, Json> = {
    review_id: claim.run.id,
    attempt_id: attempt.id,
    lease_token: attempt.leaseToken,
    status: "completed",
    result,
    moderation,
    ruleset_version: RULESET_VERSION,
    model_provider: "openai",
    model_version: model,
  };
  if (activeProviderRequestId !== null) {
    completionPayload.provider_request_id = activeProviderRequestId;
  }
  if (!(await complete(completionPayload))) {
    return json(
      request,
      { ok: false, code: "content_review_unavailable" },
      503,
    );
  }
  const completed = await readCurrentStatus();
  return completed === null
    ? json(request, { ok: false, code: "content_review_unavailable" }, 503)
    : json(request, completed.data);
}

const creatorContentReview = withSupabase<ContentEngineDatabase>(
  CREATOR_CONTENT_REVIEW_USER_OPTIONS,
  (request, context) => handleCreatorContentReview(request, context, false),
);
const creatorContentReviewWorker = withSupabase<ContentEngineDatabase>(
  CREATOR_CONTENT_REVIEW_WORKER_OPTIONS,
  (request, context) => handleCreatorContentReview(request, context, true),
);

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
    if (isInternalWorkerRequest(request)) {
      return creatorContentReviewWorker(request);
    }
    return creatorContentReview(request);
  },
};
