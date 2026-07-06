# Manual Metrics Import

Manual metrics import is the default path for platforms without a configured official connector.

Use cases:

- Instagram or TikTok while official app access is pending;
- partner placements where the operator receives a report;
- any published URL that needs quick manual performance feedback.

Import command:

```bash
python scripts/import_destination_metrics.py --csv sample_data/destination_metrics.csv
```

Optional arguments:

```bash
python scripts/import_destination_metrics.py --csv report.csv --campaign-id 1 --connection-id 3
```

After import:

```bash
python scripts/destination_metrics_summary.py --campaign-id 1
```

Review `/destination-connectors` for matched/unmatched URLs, missing metrics, recent syncs, and the campaign metrics summary.
