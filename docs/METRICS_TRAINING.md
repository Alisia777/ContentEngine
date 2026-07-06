# Metrics Training

Metrics Basics explains how platform statistics become usable ContentEngine data.

## Collection Sources

Metrics may come from:

- official connectors when OAuth/token access is valid;
- CSV/manual platform reports;
- tracking clicks from `/r/{slug}`;
- marketplace reports for orders and revenue;
- partner slot reports.

## CSV Rule

Social metric rows must include one of:

- `posted_url`;
- `tracking_slug`;
- `publishing_task_id`.

Rows without those fields stay unmatched with a warning. This prevents unsafe matching by SKU alone.

## Normalized Columns

```text
platform, destination_id, posted_url, tracking_slug, campaign_id, product_id, sku,
creative_variant_id, participant_id, period_start, period_end, views, reach,
impressions, engagements, likes, comments, shares, saves, clicks, orders, revenue,
spend, watch_time_seconds, retention_rate, source_type, match_confidence, warnings
```

## Certification Questions

- What happens if CSV has no `posted_url` and no `tracking_slug`? Correct answer: unmatched warning.
- What captures clicks? Correct answer: `tracking_link`.
