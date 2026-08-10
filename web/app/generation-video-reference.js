const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const EXTERNAL_REFERENCE_PATTERN =
  /(?:https?:\/\/|www\.|(?:youtube(?:-nocookie)?\.com|youtu\.be)(?:[\s/?#:]|$))/iu;

export const GENERATION_VIDEO_REFERENCE_ATTESTATION_VERSION =
  "generation-video-reference-v1";
export const GENERATION_VIDEO_REFERENCE_PROMPT_MARKER =
  "GenerationVideoReference/operator-summary:";
export const GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER =
  "ИИ исходный ролик не просматривал.";
export const GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE =
  "generation_video_reference_marker_invalid";

export function canonicalGenerationVideoReferenceUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  if (url.protocol !== "https:") return "";
  const host = url.hostname.toLowerCase().replace(/\.$/u, "");
  const parts = url.pathname.split("/").filter(Boolean);
  const youtubeHosts = new Set([
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtube-nocookie.com",
    "www.youtube-nocookie.com", "youtu.be",
  ]);
  if (!youtubeHosts.has(host)) return "";
  const candidate = host === "youtu.be"
    ? parts[0]
    : url.pathname === "/watch"
      ? url.searchParams.get("v")
      : ["shorts", "embed", "live"].includes(parts[0] || "")
        ? parts[1]
        : "";
  return YOUTUBE_VIDEO_ID.test(String(candidate || ""))
    ? `https://youtube.com/watch?v=${candidate}`
    : "";
}

export function normalizeGenerationVideoReference(value = {}) {
  const rawUrl = String(value.url || value.canonical_url || "").trim();
  const canonicalUrl = canonicalGenerationVideoReferenceUrl(rawUrl);
  const mechanicsSummary = String(
    value.mechanics_summary || value.mechanicsSummary || "",
  ).replace(/\s+/gu, " ").trim();
  const sourceAccessConfirmed = value.source_access_confirmed === true;
  const transformativeUseConfirmed =
    value.transformative_use_confirmed === true;
  const present = Boolean(
    rawUrl || mechanicsSummary || sourceAccessConfirmed
      || transformativeUseConfirmed,
  );
  if (!present) return { present: false, ready: true };
  let code = "";
  if (!canonicalUrl) code = "generation_video_reference_url_invalid";
  else if (
    mechanicsSummary.length < 20 || mechanicsSummary.length > 360
    || EXTERNAL_REFERENCE_PATTERN.test(mechanicsSummary)
    || mechanicsSummary.includes(GENERATION_VIDEO_REFERENCE_PROMPT_MARKER)
  ) code = "generation_video_reference_mechanics_invalid";
  else if (!sourceAccessConfirmed || !transformativeUseConfirmed) {
    code = "generation_video_reference_attestation_required";
  }
  return {
    present: true,
    ready: !code,
    code,
    video_id: canonicalUrl ? canonicalUrl.slice(-11) : "",
    canonical_url: canonicalUrl,
    mechanics_summary: mechanicsSummary,
    source_access_confirmed: sourceAccessConfirmed,
    transformative_use_confirmed: transformativeUseConfirmed,
    analysis_basis: "operator_summary",
    ai_watched: false,
    evidence_verified: false,
    attestation_version: GENERATION_VIDEO_REFERENCE_ATTESTATION_VERSION,
  };
}

export function generationVideoReferencePromptFragment(value = {}) {
  const normalized = normalizeGenerationVideoReference(value);
  if (!normalized.present) return "";
  if (!normalized.ready) return null;
  return `${GENERATION_VIDEO_REFERENCE_PROMPT_MARKER} ${normalized.mechanics_summary}. ${GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER}`;
}

export function inspectGenerationVideoReferencePromptFragment(value = "") {
  const fragment = String(value || "").replace(/\s+/gu, " ").trim();
  if (!fragment) {
    return { present: false, ready: true, code: "", fragment: "" };
  }
  const prefix = `${GENERATION_VIDEO_REFERENCE_PROMPT_MARKER} `;
  const suffix = `. ${GENERATION_VIDEO_REFERENCE_PROMPT_DISCLAIMER}`;
  const markerCount = fragment.split(
    GENERATION_VIDEO_REFERENCE_PROMPT_MARKER,
  ).length - 1;
  const mechanicsSummary = fragment.startsWith(prefix)
    && fragment.endsWith(suffix)
    ? fragment.slice(prefix.length, -suffix.length)
    : "";
  const canonicalFragment = mechanicsSummary
    ? `${prefix}${mechanicsSummary}${suffix}`
    : "";
  const ready = markerCount === 1
    && mechanicsSummary.length >= 20
    && mechanicsSummary.length <= 360
    && !EXTERNAL_REFERENCE_PATTERN.test(mechanicsSummary)
    && !mechanicsSummary.includes(GENERATION_VIDEO_REFERENCE_PROMPT_MARKER)
    && fragment === canonicalFragment;
  return {
    present: true,
    ready,
    code: ready ? "" : GENERATION_VIDEO_REFERENCE_MARKER_INVALID_CODE,
    fragment,
    mechanics_summary: mechanicsSummary,
    marker_count: markerCount,
  };
}

export function normalizeGenerationVideoReferenceContext(value = null) {
  if (value === null || value === undefined) return null;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const keys = Object.keys(value);
  const bindingId = String(value.binding_id || "").trim().toLowerCase();
  const bindingHash = String(value.binding_hash || "").trim().toLowerCase();
  if (
    keys.length !== 2
    || !keys.every((key) => ["binding_id", "binding_hash"].includes(key))
    || !UUID_PATTERN.test(bindingId)
    || !SHA256_PATTERN.test(bindingHash)
  ) return null;
  return { binding_id: bindingId, binding_hash: bindingHash };
}
