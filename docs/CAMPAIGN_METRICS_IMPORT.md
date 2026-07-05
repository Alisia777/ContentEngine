# Campaign Metrics Import

Campaign metrics import accepts manual CSV files with one row per published content metric period.

Required practical fields:

- `sku`;
- `platform`;
- `posted_url`;
- `period_start`;
- `period_end`.

Metric fields:

- `views`;
- `likes`;
- `comments`;
- `shares`;
- `saves`;
- `clicks`;
- `orders`;
- `revenue`;
- `spend`;
- `watch_time_seconds`;
- `retention_rate`.

Missing views, clicks, or orders produce row warnings instead of failing the import.

`posted_url` is matched to `PublishingTask.final_url` when possible. If no matching task exists, the metric is still stored with a warning.

No scraping or external API credential is required.
