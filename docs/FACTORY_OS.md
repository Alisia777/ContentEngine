# AI Content Factory Operating System

Factory OS is the v1 integration layer that connects existing modules into one prompt-only campaign workflow.

It reuses:

- Product Matrix Import;
- Campaign Autopilot;
- Campaign Execution Control;
- Campaign Batch Executor;
- Publishing foundation;
- Campaign Performance Loop.

It does not create external accounts, scrape platforms, run paid providers, auto-publish, or bypass approval gates.

## Workflow

```text
product matrix
-> campaign creation
-> content autopilot preparation
-> execution snapshot
-> safe prompt-only batch
-> distribution plan
-> optional performance CSV import
-> scaling recommendations
-> acceptance report
-> runbook
```

## CLI

```bash
python scripts/factory_health_check.py
python scripts/factory_prompt_only_launch.py --matrix sample_data/product_matrix.csv --campaign-name "Demo Launch" --target-videos 350 --target-destinations 120
python scripts/factory_acceptance_report.py --campaign-id 1
python scripts/factory_runbook.py --campaign-id 1
```

## UI

Open `/factory-os`.

The page includes system health, prompt-only launch, campaign status, acceptance report, and next manual actions.
