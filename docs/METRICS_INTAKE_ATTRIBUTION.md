# Metrics Intake & Attribution

v1.8 adds the data layer that connects published posts to measurable campaign, SKU, destination, participant, payout, and recommendation outcomes.

## Data Contract

Every measurable post should have:

- `PublishingTask`
- `final_url`
- `TrackingLink`
- `destination_id`
- `sku`
- `campaign_id` where available
- `participant_id` where available

The attribution flow is:

```text
final_url / tracking_slug / publishing_task_id
-> destination
-> campaign / product / SKU / variant
-> FunnelSnapshot
-> CampaignPerformanceMetric
-> ParticipantMetricSnapshot
```

## Collection Layers

1. Capture `final_url` after publication.
2. Generate first-party tracking links at `/r/{slug}`.
3. Import platform/manual/partner CSV reports.
4. Use official connectors only when authorization exists.
5. Import marketplace conversions by SKU, UTM, coupon, or period.

## CSV Columns

```csv
platform,destination_handle,posted_url,tracking_slug,sku,period_start,period_end,views,reach,impressions,likes,comments,shares,saves,clicks,orders,revenue,spend
facebook,@account,https://facebook.com/example,abc123,SKU001,2026-07-01,2026-07-07,12000,9000,15000,300,24,18,0,410,12,35000,0
```

## Normalized Schema

Every source is normalized into one metric row shape:

```text
platform
destination_id
posted_url
tracking_slug
campaign_id
product_id
sku
creative_variant_id
participant_id
period_start
period_end
views
reach
impressions
engagements
likes
comments
shares
saves
clicks
orders
revenue
spend
watch_time_seconds
retention_rate
source_type
match_confidence
warnings
```

## Platform Matrix

| Platform | Official path | Fallback | Always use |
| --- | --- | --- | --- |
| Facebook / Instagram | Meta OAuth / business assets | CSV/manual/partner report | final URL + tracking link |
| YouTube Shorts | YouTube Analytics OAuth | CSV/manual | final URL + tracking link |
| TikTok | official API/scopes when authorized | CSV/manual/partner report | final URL + tracking link |
| Telegram | bot/admin data when available | CSV/manual | final URL + tracking link |
| VK | official VK API token/permissions | CSV/manual | final URL + tracking link |
| Ozon / WB | seller API/reports | marketplace CSV | SKU + period + tracking/UTM/coupon when available |
| Partner slots | partner report | manual CSV | final URL + tracking link |

Official connectors are gated by `DestinationConnection.auth_status` and `credential_ref`. A configured source stores only the reference name, never the raw token.

## Matching Priority

Metrics rows are matched by:

1. `publishing_task_id`
2. `tracking_slug`
3. `posted_url` / final URL
4. `destination_handle + sku + period`
5. manual mapping or coupon rules in later iterations

Social rows without `posted_url`, `tracking_slug`, or `publishing_task_id` become unmatched warnings. Marketplace conversion rows may match approximately by SKU and period.

## Safety Boundaries

ContentEngine does not:

- scrape Facebook;
- use unofficial login, cookies, password flows, proxy, or anti-detect logic;
- store raw platform tokens;
- bypass OAuth or permissions;
- auto-publish;
- call real external APIs in tests.

For official access, store only a `credential_ref`; the secret itself belongs in `.env` or a secret manager.
