# Metrics Collection

v1.5 normalizes destination metrics into `DestinationPostMetric` and then mirrors the same facts into `CampaignPerformanceMetric`.

Normalization rules:

- match `posted_url` to `PublishingTask.final_url` when possible;
- store unmatched URLs with a warning instead of failing the whole import;
- warn on missing `views`, `clicks`, or `orders`;
- keep imports idempotent by `platform + posted_url + period_start + period_end`;
- keep provider raw rows in `raw_json` after sanitization-oriented processing.

CSV import:

```bash
python scripts/import_destination_metrics.py --csv sample_data/destination_metrics.csv
python scripts/destination_metrics_summary.py --campaign-id 1
```

Required CSV columns:

```csv
campaign_id,destination_name,platform,posted_url,sku,period_start,period_end,views,likes,comments,shares,saves,clicks,orders,revenue,spend,watch_time_seconds,retention_rate
```

The campaign summary API is:

```text
GET /api/destination-connectors/campaigns/{campaign_id}/metrics-summary
```

Use this layer before campaign recommendations so the performance loop has current destination, platform, and SKU metrics.
