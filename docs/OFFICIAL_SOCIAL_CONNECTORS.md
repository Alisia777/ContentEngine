# Official TikTok and Instagram metric connectors

The production sync boundary supports two additional official, organization-scoped
adapters. Neither adapter scrapes pages, reads browser sessions, stores a raw token,
or falls back to mock rows.

## Shared safety contract

- `DestinationConnection.credential_ref` stores only a logical environment/secret
  reference. The OAuth access token is resolved at call time.
- The token is sent only in the HTTP `Authorization: Bearer ...` header. It is not
  placed in a query string, settings, audit, result, or provider URL.
- `settings_json` rejects raw credentials, mock metrics, and credential-bearing or
  signed URLs.
- Every target must map to one confirmed-published `PublishingTask` owned through
  `organization -> destination -> task -> package -> product` before a provider
  transport is called.
- A sync requires an active organization member, explicit destination, closed
  period, timezone-aware observation time, and retry-safe `sync_key`.
- Provider values are cumulative snapshots. A newer observation replaces submitted
  fields; values are never added to the previous snapshot. Retry replay is a no-op,
  and attribution conflicts go to the existing organization-scoped quarantine.
- Readiness is `ready=true` only after a successful official API request has set
  `oauth_verified`. A configured credential reference by itself is not verification.

## TikTok Display API v2

Connection type: `tiktok_oauth`

Official request:

```text
POST https://open.tiktokapis.com/v2/video/query/
scope: video.list
fields: id,view_count,like_count,comment_count,share_count
body: {"filters":{"video_ids":[...]}}
```

The official endpoint verifies that queried video IDs belong to the OAuth user and
accepts at most 20 IDs per request. The local connector additionally requires this
strict, non-secret settings shape:

```json
{
  "video_map": {
    "7412345678901234567": {
      "final_url": "https://www.tiktok.com/@brand/video/7412345678901234567",
      "publishing_task_id": 123
    }
  }
}
```

The response must contain exactly the requested IDs and fields. Unknown, duplicate,
missing, negative, fractional, or malformed values fail the entire provider pull
before metric ingestion begins.

Official reference: [TikTok Query Videos](https://developers.tiktok.com/doc/tiktok-api-v2-video-query/).

## Instagram professional Media Insights

Connection type: `instagram_oauth`

Required permissions for Instagram Login:

- `instagram_business_basic`
- `instagram_business_manage_insights`

The account must be an Instagram professional account. Each owned media ID is read
through:

```text
GET https://graph.instagram.com/{api_version}/{media_id}/insights
metric=views,plays,reach,likes,comments,shares,saved
```

Strict settings shape:

```json
{
  "api_version": "v25.0",
  "media_map": {
    "18012345678901234": {
      "final_url": "https://www.instagram.com/reel/ExampleCode",
      "publishing_task_id": 456
    }
  }
}
```

Unavailable metrics may be omitted by the provider. `views` is canonical; `plays`
is used only when `views` is absent. `saved` maps to the normalized `saves` field.
They are never combined or summed. Provider paging URLs and raw response bodies are
discarded rather than persisted.

Official reference: [Meta's Instagram API collection — Insights](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api).

## Test boundary

Automated tests inject deterministic transports. They assert request shape,
organization isolation, strict target ownership, idempotent replay, cumulative
replacement, quarantine behavior, and redaction. Tests make no real TikTok or Meta
network request and require no provider credential.
