# Content Factory Stats

Performance stats close the loop after generated content is published.

CSV import:

```bash
python scripts/import_content_stats.py --csv sample_data/content_performance.csv
```

API:

- `POST /api/content-factory/stats/import-csv`
- `GET /api/content-factory/dashboard`

Supported CSV columns:

```text
content_run_id,product_id,sku,platform,creative_variant_id,video_job_id,metric_date,impressions,views,clicks,orders,revenue,spend,ctr,conversion_rate,watch_time_seconds,retention_rate
```

When `ctr` or `conversion_rate` is missing, ContentEngine derives them from clicks, views/impressions, and orders when possible.

Recommendations use imported metrics to suggest `scale_variant` for stronger content and `pause_variant` for weak content. These are recommendations only; they do not auto-publish or auto-scale accounts.
