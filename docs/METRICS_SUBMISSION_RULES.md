# Metrics Submission Rules

Metrics can arrive from:

- tracking link clicks;
- final URLs;
- CSV/manual reports;
- official connectors when authorized;
- marketplace reports.

## Participant CSV Format

```csv
participant_name,platform,destination_handle,posted_url,tracking_slug,sku,period_start,period_end,views,reach,impressions,likes,comments,shares,saves,clicks,orders,revenue,spend
Ivan,facebook,@health_daily,https://facebook.com/post/123,abc123,ALTEA-001,2026-07-01,2026-07-07,12000,9000,15000,300,24,18,0,410,12,35000,0
```

## Required Identity

Social rows must include at least one:

- `posted_url`
- `tracking_slug`
- `publishing_task_id`

Marketplace rows may use:

- `sku`
- `period_start`
- `period_end`
- coupon / UTM / tracking slug when available

Rows that cannot be traced are imported as unmatched warnings, not attributed metrics.
