# Campaign Performance Loop

Campaign Performance Loop is the v0.9 feedback layer for campaign scaling decisions.

It uses manual CSV metrics and existing publishing task final URLs. It does not scrape platforms, call external APIs, auto-publish, bypass approvals, run paid providers, or create external accounts.

## Workflow

```text
Published content / final URLs
-> manual performance metrics CSV
-> campaign aggregation
-> SKU / variant / hook / destination / platform scores
-> scale / pause / regenerate recommendations
-> safe action queue items
-> dashboard and report
```

## UI

Open `/campaign-performance`.

Sections:

- Import Metrics;
- Campaign Summary;
- SKU Performance;
- Variant / Hook Performance;
- Destination Performance;
- Recommendations;
- Export Report.

## CLI

```bash
python scripts/import_campaign_performance.py --campaign-id 1 --csv sample_data/campaign_performance.csv
python scripts/campaign_performance_summary.py --campaign-id 1
python scripts/campaign_performance_recommendations.py --campaign-id 1
python scripts/campaign_performance_report.py --campaign-id 1
python scripts/campaign_performance_report.py --campaign-id 1 --format csv
```

## Recommendations

The MVP creates recommendations for:

- `scale_variant`;
- `pause_variant`;
- `regenerate_variant`;
- `change_destination`;
- `increase_distribution`;
- `import_performance_stats`.

Recommendations can be accepted or rejected. Safe draft actions can be queued, but nothing is auto-published and no paid provider call is executed.
