const YOUTUBE_ID = /^[A-Za-z0-9_-]{6,20}$/u;

export function youtubeVideoId(value) {
  let url;
  try {
    url = new URL(String(value || "").trim());
  } catch {
    return "";
  }
  const host = url.hostname.toLowerCase().replace(/^www\./u, "");
  let candidate = "";
  if (host === "youtu.be") {
    candidate = url.pathname.split("/").filter(Boolean)[0] || "";
  } else if (host === "youtube.com" || host === "m.youtube.com") {
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "shorts" || parts[0] === "embed" || parts[0] === "live") {
      candidate = parts[1] || "";
    } else if (url.pathname === "/watch") {
      candidate = url.searchParams.get("v") || "";
    }
  }
  return YOUTUBE_ID.test(candidate) ? candidate : "";
}

export function canonicalYoutubeUrl(value) {
  const id = youtubeVideoId(value);
  return id ? `https://www.youtube.com/watch?v=${id}` : "";
}

export function sameYoutubeVideo(left, right) {
  const leftId = youtubeVideoId(left);
  return Boolean(leftId && leftId === youtubeVideoId(right));
}
