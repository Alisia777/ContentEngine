/*
 * Exact YouTube research-source -> uploaded MP4 browser handoff.
 *
 * This module owns only short-lived browser state. Server ACLs and the
 * append-only source/media attachment remain authoritative. Binding the
 * handoff to the current organization, user, tab session and project prevents
 * a copied/stale media URL from silently attaching an upload to another
 * research source.
 */

export const EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY =
  "contentengine.research.youtube.upload-handoff.v1";
export const EXACT_YOUTUBE_MEDIA_HANDOFF_MAX_AGE_MS = 4 * 60 * 60 * 1_000;

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const YOUTUBE_URL_PATTERN =
  /^https:\/\/youtube[.]com\/watch[?]v=[A-Za-z0-9_-]{11}$/u;

function uuid(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return UUID_PATTERN.test(normalized) ? normalized : "";
}

function clean(value, limit = 1_000) {
  return String(value ?? "").trim().slice(0, limit);
}

function sourceIdentityText(value, limit) {
  const normalized = String(value ?? "").replace(/\s+/gu, " ").trim();
  return normalized.length <= limit ? normalized : "";
}

function identity(input = {}) {
  return {
    organization_id: uuid(input.organization_id ?? input.organizationId),
    user_id: uuid(input.user_id ?? input.userId),
    session_id: uuid(input.session_id ?? input.sessionId),
    project_id: uuid(input.project_id ?? input.projectId),
    source_id: uuid(input.source_id ?? input.sourceId),
  };
}

function identityComplete(value) {
  return Object.values(value).every(Boolean);
}

function safeParse(storage) {
  try {
    const raw = storage?.getItem?.(EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : null;
  } catch {
    return null;
  }
}

function normalizedProgress(value, expectedIdentity) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const objectKey = clean(value.object_key, 1_000);
  const filename = clean(value.original_filename, 255);
  const mimeType = clean(value.mime_type, 160).toLowerCase();
  const sha256 = clean(value.sha256, 64).toLowerCase();
  const sizeBytes = Number(value.size_bytes);
  const mediaId = uuid(value.media_id);
  const expectedPrefix = `${expectedIdentity.organization_id}/${expectedIdentity.user_id}/`;
  if (
    !objectKey.startsWith(expectedPrefix)
    || objectKey.includes("../")
    || !filename
    || mimeType !== "video/mp4"
    || !SHA256_PATTERN.test(sha256)
    || !Number.isInteger(sizeBytes)
    || sizeBytes < 1
  ) return null;
  return {
    object_key: objectKey,
    original_filename: filename,
    mime_type: mimeType,
    sha256,
    size_bytes: sizeBytes,
    ...(mediaId ? { media_id: mediaId } : {}),
  };
}

export function writeExactYoutubeMediaHandoff(storage, input = {}) {
  const exactIdentity = identity(input);
  const canonicalUrl = clean(input.canonical_url ?? input.canonicalUrl, 300);
  const productName = sourceIdentityText(
    input.product_name ?? input.productName,
    300,
  );
  const productSku = sourceIdentityText(
    input.product_sku ?? input.productSku,
    160,
  );
  if (!identityComplete(exactIdentity)) return false;
  if (canonicalUrl && !YOUTUBE_URL_PATTERN.test(canonicalUrl)) return false;
  const requestedAt = clean(input.requested_at ?? input.requestedAt, 64)
    || new Date().toISOString();
  if (!Number.isFinite(Date.parse(requestedAt))) return false;
  const existing = safeParse(storage);
  const existingIdentity = identity(existing || {});
  const preservedProgress = identityComplete(existingIdentity)
    && Object.entries(exactIdentity).every(
      ([key, value]) => existingIdentity[key] === value,
    )
    ? normalizedProgress(existing?.progress, exactIdentity)
    : null;
  try {
    storage?.setItem?.(
      EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        ...exactIdentity,
        canonical_url: canonicalUrl,
        product_name: productName,
        product_sku: productSku,
        requested_at: requestedAt,
        ...(preservedProgress ? { progress: preservedProgress } : {}),
      }),
    );
    return true;
  } catch {
    return false;
  }
}

export function readExactYoutubeMediaHandoff(
  storage,
  expected = {},
  { now = Date.now(), maxAgeMs = EXACT_YOUTUBE_MEDIA_HANDOFF_MAX_AGE_MS } = {},
) {
  const expectedIdentity = identity(expected);
  if (!identityComplete(expectedIdentity)) {
    return { ok: false, code: "handoff_context_invalid" };
  }
  const parsed = safeParse(storage);
  if (!parsed) return { ok: false, code: "handoff_missing" };
  const storedIdentity = identity(parsed);
  if (
    !identityComplete(storedIdentity)
    || Object.entries(expectedIdentity).some(
      ([key, value]) => storedIdentity[key] !== value,
    )
  ) return { ok: false, code: "handoff_scope_mismatch" };
  const requestedAt = Date.parse(clean(parsed.requested_at, 64));
  const age = Number(now) - requestedAt;
  if (
    !Number.isFinite(requestedAt)
    || !Number.isFinite(age)
    || age < -60_000
    || age > Math.max(60_000, Number(maxAgeMs) || 0)
  ) return { ok: false, code: "handoff_expired" };
  const canonicalUrl = clean(parsed.canonical_url, 300);
  if (canonicalUrl && !YOUTUBE_URL_PATTERN.test(canonicalUrl)) {
    return { ok: false, code: "handoff_payload_invalid" };
  }
  const productName = sourceIdentityText(parsed.product_name, 300);
  const productSku = sourceIdentityText(parsed.product_sku, 160);
  if (
    clean(parsed.product_name, 301) !== productName
    || clean(parsed.product_sku, 161) !== productSku
  ) return { ok: false, code: "handoff_payload_invalid" };
  const progress = parsed.progress === undefined
    ? null
    : normalizedProgress(parsed.progress, expectedIdentity);
  if (parsed.progress !== undefined && progress === null) {
    return { ok: false, code: "handoff_payload_invalid" };
  }
  return {
    ok: true,
    code: "ok",
    handoff: {
      version: 1,
      ...expectedIdentity,
      canonical_url: canonicalUrl,
      product_name: productName,
      product_sku: productSku,
      requested_at: new Date(requestedAt).toISOString(),
      ...(progress ? { progress } : {}),
    },
  };
}

export function updateExactYoutubeMediaHandoffProgress(
  storage,
  expected,
  progress,
) {
  const current = readExactYoutubeMediaHandoff(storage, expected);
  if (!current.ok) return current;
  const normalized = normalizedProgress(progress, identity(expected));
  if (!normalized) return { ok: false, code: "handoff_progress_invalid" };
  try {
    storage?.setItem?.(
      EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY,
      JSON.stringify({ ...current.handoff, progress: normalized }),
    );
    return {
      ok: true,
      code: "ok",
      handoff: { ...current.handoff, progress: normalized },
    };
  } catch {
    return { ok: false, code: "handoff_storage_unavailable" };
  }
}

export function clearExactYoutubeMediaHandoff(storage, expected) {
  const current = readExactYoutubeMediaHandoff(storage, expected);
  if (!current.ok) return false;
  try {
    storage?.removeItem?.(EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function exactYoutubeRegisteredMediaId(response) {
  const source = response?.data && typeof response.data === "object"
    && !Array.isArray(response.data)
    ? response.data
    : response;
  const mediaId = uuid(source?.media?.id || source?.media?.public_id);
  return source?.ok === true && mediaId ? mediaId : "";
}

export function exactYoutubeResearchEvidenceRoute({
  project_id: projectIdSnake,
  projectId = "",
  source_id: sourceIdSnake,
  sourceId = "",
  media_id: mediaIdSnake,
  mediaId = "",
  attachment_id: attachmentIdSnake,
  attachmentId = "",
  product_name: productNameSnake,
  productName = "",
  product_sku: productSkuSnake,
  productSku = "",
} = {}) {
  const ids = {
    project_id: uuid(projectIdSnake || projectId),
    youtube_source: uuid(sourceIdSnake || sourceId),
    media: uuid(mediaIdSnake || mediaId),
    attachment: uuid(attachmentIdSnake || attachmentId),
  };
  if (Object.values(ids).some((value) => !value)) return "";
  const query = new URLSearchParams({
    view: "new",
    media: ids.media,
    project_id: ids.project_id,
    youtube_source: ids.youtube_source,
    attachment: ids.attachment,
    purpose: "exact_youtube_research",
  });
  const exactProductName = sourceIdentityText(
    productNameSnake ?? productName,
    180,
  );
  const exactProductSku = sourceIdentityText(productSkuSnake ?? productSku, 120);
  if (exactProductName) query.set("product_name", exactProductName);
  if (exactProductSku) query.set("product_sku", exactProductSku);
  return `/workspace/review?${query.toString()}`;
}

export function isExactYoutubeMp4(file) {
  if (!file) return false;
  return String(file.type || "").trim().toLowerCase() === "video/mp4"
    && String(file.name || "").trim().toLowerCase().endsWith(".mp4")
    && Number.isInteger(Number(file.size))
    && Number(file.size) > 0;
}
