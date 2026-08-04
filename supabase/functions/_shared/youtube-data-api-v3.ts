export const YOUTUBE_DATA_API_HOST = "www.googleapis.com";
export const YOUTUBE_PROVIDER_KEY = "youtube_data_api_v3";
export const YOUTUBE_ADAPTER_VERSION = "youtube-data-api-v3-public-metadata-v1";
export const YOUTUBE_INGESTION_VERSION = "research-youtube-live-ingestion-v1";

const SEARCH_PATH = "/youtube/v3/search";
const VIDEOS_PATH = "/youtube/v3/videos";
const MAX_RESPONSE_BYTES = 524_288;
const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/u;
const CHANNEL_ID_PATTERN = /^UC[A-Za-z0-9_-]{22}$/u;
const API_KEY_PATTERN = /^[A-Za-z0-9_-]{20,256}$/u;
const LANGUAGE_PATTERN = /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/u;
const DIGITS_PATTERN = /^(?:0|[1-9][0-9]{0,29})$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export type YoutubeSearchOptions = {
  queryText: string;
  maxResults: number;
  regionCode?: string | null;
  relevanceLanguage?: string | null;
  publishedAfter?: string | null;
  order?: "date" | "relevance";
};

export type YoutubeSearchResult = {
  responseHash: string;
  etag: string;
  videoIds: string[];
  itemCount: number;
  nextPageAvailable: boolean;
};

export type YoutubeVideoObservation = {
  search_position: number;
  video_id: string;
  channel_id: string;
  title: string;
  channel_title: string;
  youtube_category_id: string;
  published_at: string;
  duration_iso8601: string;
  privacy_status: "public";
  embeddable: boolean;
  retention_expires_at: string;
  view_count: string | null;
  like_count: string | null;
  comment_count: string | null;
  observed_at: string;
};

export type YoutubeVideosResult = {
  responseHash: string;
  itemCount: number;
  missingVideoCount: number;
  observations: YoutubeVideoObservation[];
};

export type YoutubeFailureCode =
  | "provider_authentication_failed"
  | "provider_quota_exhausted"
  | "provider_rate_limited"
  | "provider_request_rejected"
  | "provider_response_invalid"
  | "provider_outcome_unknown"
  | "provider_unavailable";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: readonly string[],
): boolean {
  const allowedKeys = new Set(allowed);
  return Object.keys(value).every((key) => allowedKeys.has(key));
}

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

function boundedText(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return typeof value === "string" && value === value.trim() &&
    value.length >= minimum && value.length <= maximum &&
    !hasControlCharacter(value);
}

function requireApiKey(value: string): string {
  if (!API_KEY_PATTERN.test(value)) throw new Error("youtube_api_key_invalid");
  return value;
}

function normalizedIsoTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || value.length < 20 || value.length > 40) {
    return null;
  }
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) return null;
  return new Date(milliseconds).toISOString();
}

function pageInfoValid(value: unknown, maximum: number): boolean {
  if (
    !isRecord(value) || !hasOnlyKeys(value, [
      "totalResults",
      "resultsPerPage",
    ])
  ) return false;
  return Number.isSafeInteger(value.totalResults) &&
    Number(value.totalResults) >= 0 &&
    Number.isSafeInteger(value.resultsPerPage) &&
    Number(value.resultsPerPage) >= 0 &&
    Number(value.resultsPerPage) <= maximum;
}

function stableJson(value: unknown): string {
  const walk = (node: unknown): unknown => {
    if (Array.isArray(node)) return node.map(walk);
    if (!isRecord(node)) return node;
    return Object.fromEntries(
      Object.keys(node).sort().map((key) => [key, walk(node[key])]),
    );
  };
  return JSON.stringify(walk(value));
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function jsonHash(value: unknown): Promise<string> {
  return await sha256Hex(stableJson(value));
}

function searchDescriptor(url: URL): Record<string, Json> {
  const params = Object.fromEntries(
    [...url.searchParams.entries()]
      .filter(([key]) => key !== "key")
      .sort(([left], [right]) => left.localeCompare(right)),
  );
  return {
    version: "youtube-data-api-request-v1",
    method: "GET",
    host: url.hostname,
    path: url.pathname,
    params,
  };
}

export async function youtubeRequestHash(url: URL): Promise<string> {
  if (
    url.protocol !== "https:" || url.hostname !== YOUTUBE_DATA_API_HOST ||
    ![SEARCH_PATH, VIDEOS_PATH].includes(url.pathname) ||
    !url.searchParams.has("key")
  ) throw new Error("youtube_request_invalid");
  const result = await jsonHash(searchDescriptor(url));
  if (!SHA256_PATTERN.test(result)) throw new Error("youtube_request_invalid");
  return result;
}

export function buildYoutubeSearchUrl(
  options: YoutubeSearchOptions,
  apiKey: string,
  now = new Date(),
): URL {
  const queryText = options.queryText.trim();
  if (
    !boundedText(queryText, 2, 200) ||
    !Number.isSafeInteger(options.maxResults) ||
    options.maxResults < 1 || options.maxResults > 25
  ) throw new Error("youtube_search_options_invalid");
  const regionCode = options.regionCode?.trim().toUpperCase() || null;
  if (regionCode !== null && !/^[A-Z]{2}$/u.test(regionCode)) {
    throw new Error("youtube_search_options_invalid");
  }
  const relevanceLanguage = options.relevanceLanguage?.trim() || null;
  if (
    relevanceLanguage !== null && !LANGUAGE_PATTERN.test(relevanceLanguage)
  ) throw new Error("youtube_search_options_invalid");
  let publishedAfter: string | null = null;
  if (options.publishedAfter) {
    publishedAfter = normalizedIsoTimestamp(options.publishedAfter);
    const timestamp = publishedAfter === null
      ? NaN
      : Date.parse(publishedAfter);
    if (
      publishedAfter === null || timestamp > now.getTime() + 300_000 ||
      timestamp < now.getTime() - 366 * 86_400_000
    ) throw new Error("youtube_search_options_invalid");
  }

  const url = new URL(`https://${YOUTUBE_DATA_API_HOST}${SEARCH_PATH}`);
  url.searchParams.set("part", "snippet");
  url.searchParams.set("type", "video");
  url.searchParams.set("q", queryText);
  url.searchParams.set("maxResults", String(options.maxResults));
  url.searchParams.set("order", options.order ?? "date");
  url.searchParams.set("safeSearch", "strict");
  if (regionCode !== null) url.searchParams.set("regionCode", regionCode);
  if (relevanceLanguage !== null) {
    url.searchParams.set("relevanceLanguage", relevanceLanguage);
  }
  if (publishedAfter !== null) {
    url.searchParams.set("publishedAfter", publishedAfter);
  }
  url.searchParams.set(
    "fields",
    "kind,etag,nextPageToken,regionCode,pageInfo(totalResults,resultsPerPage),items(id(kind,videoId),snippet(publishedAt,channelId,title,channelTitle))",
  );
  url.searchParams.set("key", requireApiKey(apiKey));
  return url;
}

export function buildYoutubeVideosUrl(
  videoIds: readonly string[],
  apiKey: string,
): URL {
  const uniqueIds = [...new Set(videoIds)];
  if (
    uniqueIds.length < 1 || uniqueIds.length > 25 ||
    uniqueIds.length !== videoIds.length ||
    uniqueIds.some((videoId) => !VIDEO_ID_PATTERN.test(videoId))
  ) throw new Error("youtube_video_ids_invalid");
  const url = new URL(`https://${YOUTUBE_DATA_API_HOST}${VIDEOS_PATH}`);
  url.searchParams.set("part", "snippet,contentDetails,statistics,status");
  url.searchParams.set("id", uniqueIds.join(","));
  url.searchParams.set(
    "fields",
    "kind,etag,pageInfo(totalResults,resultsPerPage),items(id,etag,snippet(publishedAt,channelId,title,channelTitle,categoryId),contentDetails(duration),statistics(viewCount,likeCount,commentCount),status(privacyStatus,embeddable))",
  );
  url.searchParams.set("key", requireApiKey(apiKey));
  return url;
}

export async function readBoundedJsonResponse(
  response: Response,
  maximumBytes = MAX_RESPONSE_BYTES,
): Promise<unknown> {
  if (!Number.isSafeInteger(maximumBytes) || maximumBytes < 1) {
    throw new Error("youtube_response_invalid");
  }
  const mediaType = (response.headers.get("content-type") ?? "")
    .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
  if (mediaType !== "application/json") {
    await response.body?.cancel();
    throw new Error("youtube_response_invalid");
  }
  const declared = Number(response.headers.get("content-length") ?? "0");
  if (Number.isFinite(declared) && declared > maximumBytes) {
    await response.body?.cancel();
    throw new Error("youtube_response_too_large");
  }
  if (response.body === null) throw new Error("youtube_response_invalid");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maximumBytes) {
        await reader.cancel();
        throw new Error("youtube_response_too_large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const combined = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(combined),
    );
  } catch {
    throw new Error("youtube_response_invalid");
  }
}

export async function readYoutubeSearchResponse(
  value: unknown,
  maximumItems = 25,
): Promise<YoutubeSearchResult> {
  if (
    !Number.isSafeInteger(maximumItems) || maximumItems < 1 ||
    maximumItems > 25 || !isRecord(value) || !hasOnlyKeys(value, [
      "kind",
      "etag",
      "nextPageToken",
      "regionCode",
      "pageInfo",
      "items",
    ]) || value.kind !== "youtube#searchListResponse" ||
    !boundedText(value.etag, 1, 300) ||
    !pageInfoValid(value.pageInfo, maximumItems) ||
    !Array.isArray(value.items) || value.items.length > maximumItems ||
    (value.nextPageToken !== undefined &&
      !boundedText(value.nextPageToken, 1, 300)) ||
    (value.regionCode !== undefined &&
      (typeof value.regionCode !== "string" ||
        !/^[A-Z]{2}$/u.test(value.regionCode)))
  ) throw new Error("youtube_search_response_invalid");

  const videoIds: string[] = [];
  for (const item of value.items) {
    if (
      !isRecord(item) || !hasOnlyKeys(item, ["id", "snippet"]) ||
      !isRecord(item.id) ||
      !hasOnlyKeys(item.id, ["kind", "videoId"]) ||
      item.id.kind !== "youtube#video" ||
      typeof item.id.videoId !== "string" ||
      !VIDEO_ID_PATTERN.test(item.id.videoId) ||
      !isRecord(item.snippet) ||
      !hasOnlyKeys(item.snippet, [
        "publishedAt",
        "channelId",
        "title",
        "channelTitle",
      ]) || normalizedIsoTimestamp(item.snippet.publishedAt) === null ||
      typeof item.snippet.channelId !== "string" ||
      !CHANNEL_ID_PATTERN.test(item.snippet.channelId) ||
      !boundedText(item.snippet.title, 1, 300) ||
      !boundedText(item.snippet.channelTitle, 1, 160)
    ) throw new Error("youtube_search_response_invalid");
    videoIds.push(item.id.videoId);
  }
  if (new Set(videoIds).size !== videoIds.length) {
    throw new Error("youtube_search_response_invalid");
  }
  return {
    responseHash: await jsonHash(value),
    etag: value.etag,
    videoIds,
    itemCount: videoIds.length,
    nextPageAvailable: typeof value.nextPageToken === "string",
  };
}

function optionalCounter(value: unknown): string | null | undefined {
  if (value === undefined) return null;
  return typeof value === "string" && DIGITS_PATTERN.test(value)
    ? value
    : undefined;
}

export async function readYoutubeVideosResponse(
  value: unknown,
  expectedVideoIds: readonly string[],
  observedAt: string,
): Promise<YoutubeVideosResult> {
  const observedIso = normalizedIsoTimestamp(observedAt);
  const expected = new Set(expectedVideoIds);
  if (
    observedIso === null || expected.size < 1 || expected.size > 25 ||
    expected.size !== expectedVideoIds.length ||
    [...expected].some((videoId) => !VIDEO_ID_PATTERN.test(videoId)) ||
    !isRecord(value) || !hasOnlyKeys(value, [
      "kind",
      "etag",
      "pageInfo",
      "items",
    ]) || value.kind !== "youtube#videoListResponse" ||
    !boundedText(value.etag, 1, 300) || !pageInfoValid(value.pageInfo, 25) ||
    !Array.isArray(value.items) || value.items.length > 25
  ) throw new Error("youtube_videos_response_invalid");

  const retentionExpiresAt = new Date(
    Date.parse(observedIso) + 29 * 86_400_000,
  ).toISOString();
  const searchPositions = new Map(
    expectedVideoIds.map((videoId, index) => [videoId, index + 1]),
  );
  const seen = new Set<string>();
  const observations: YoutubeVideoObservation[] = [];
  for (const item of value.items) {
    if (
      !isRecord(item) || !hasOnlyKeys(item, [
        "id",
        "etag",
        "snippet",
        "contentDetails",
        "statistics",
        "status",
      ]) || typeof item.id !== "string" || !expected.has(item.id) ||
      seen.has(item.id) || !boundedText(item.etag, 1, 300) ||
      !isRecord(item.snippet) || !hasOnlyKeys(item.snippet, [
        "publishedAt",
        "channelId",
        "title",
        "channelTitle",
        "categoryId",
      ]) || normalizedIsoTimestamp(item.snippet.publishedAt) === null ||
      typeof item.snippet.channelId !== "string" ||
      !CHANNEL_ID_PATTERN.test(item.snippet.channelId) ||
      !boundedText(item.snippet.title, 1, 300) ||
      !boundedText(item.snippet.channelTitle, 1, 160) ||
      typeof item.snippet.categoryId !== "string" ||
      !/^[0-9]{1,3}$/u.test(item.snippet.categoryId) ||
      !isRecord(item.contentDetails) ||
      !hasOnlyKeys(item.contentDetails, ["duration"]) ||
      !boundedText(item.contentDetails.duration, 2, 40) ||
      !/^P(?=\d|T\d)(?:\d+D)?(?:T(?:\d+H)?(?:\d+M)?(?:\d+S)?)?$/u.test(
        item.contentDetails.duration,
      ) || !isRecord(item.statistics) ||
      !hasOnlyKeys(item.statistics, [
        "viewCount",
        "likeCount",
        "commentCount",
      ]) || !isRecord(item.status) ||
      !hasOnlyKeys(item.status, ["privacyStatus", "embeddable"]) ||
      item.status.privacyStatus !== "public" ||
      typeof item.status.embeddable !== "boolean"
    ) throw new Error("youtube_videos_response_invalid");
    const viewCount = optionalCounter(item.statistics.viewCount);
    const likeCount = optionalCounter(item.statistics.likeCount);
    const commentCount = optionalCounter(item.statistics.commentCount);
    if (
      viewCount === undefined || likeCount === undefined ||
      commentCount === undefined
    ) throw new Error("youtube_videos_response_invalid");
    const publishedAt = normalizedIsoTimestamp(
      item.snippet.publishedAt,
    ) as string;
    if (
      Date.parse(publishedAt) < Date.parse("2005-02-14T00:00:00.000Z") ||
      Date.parse(publishedAt) > Date.parse(observedIso) + 60_000
    ) throw new Error("youtube_videos_response_invalid");
    observations.push({
      search_position: searchPositions.get(item.id) as number,
      video_id: item.id,
      channel_id: item.snippet.channelId,
      title: item.snippet.title,
      channel_title: item.snippet.channelTitle,
      youtube_category_id: item.snippet.categoryId,
      published_at: publishedAt,
      duration_iso8601: item.contentDetails.duration,
      privacy_status: "public",
      embeddable: item.status.embeddable,
      retention_expires_at: retentionExpiresAt,
      view_count: viewCount,
      like_count: likeCount,
      comment_count: commentCount,
      observed_at: observedIso,
    });
    seen.add(item.id);
  }
  return {
    responseHash: await jsonHash(value),
    itemCount: observations.length,
    missingVideoCount: expected.size - observations.length,
    observations,
  };
}

function errorText(value: unknown): string {
  try {
    return stableJson(value).slice(0, 16_384).toLocaleLowerCase("en-US");
  } catch {
    return "";
  }
}

export function youtubeFailureForHttp(
  status: number,
  responseValue?: unknown,
): YoutubeFailureCode {
  const detail = errorText(responseValue);
  if (
    detail.includes("quotaexceeded") ||
    detail.includes("dailylimitexceeded") ||
    detail.includes("quota exceeded")
  ) return "provider_quota_exhausted";
  if (
    status === 429 || detail.includes("ratelimitexceeded") ||
    detail.includes("rate limit")
  ) return "provider_rate_limited";
  if (status === 401 || status === 403) {
    return "provider_authentication_failed";
  }
  if (status === 408 || status >= 500) return "provider_unavailable";
  if (status >= 300 && status < 500) return "provider_request_rejected";
  return "provider_unavailable";
}
