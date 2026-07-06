# Bombar Production Dry Run

Bombar Production Dry Run is the v1.1 operator checkpoint for running a real-style Bombar matrix through the safe Factory OS path.

It does not add new generation logic, register external accounts, call paid providers, auto-publish, or bypass approval gates.

## Workflow

```text
Bombar CSV/XLSX matrix
-> strict matrix validation
-> Factory OS prompt-only launch
-> production readiness report
-> SKU blockers
-> next actions
-> JSON/CSV/XLSX exports
```

## CLI

```bash
python scripts/bombar_production_dry_run.py --matrix path/to/bombar_matrix.xlsx --target-videos 350 --target-destinations 120
```

The command prints the dry-run report as JSON and writes:

- `reports/bombar_readiness_{campaign_id}.json`
- `reports/bombar_readiness_{campaign_id}.csv`
- `reports/bombar_blockers_{campaign_id}.csv`
- `reports/bombar_next_actions_{campaign_id}.csv`
- `reports/bombar_readiness_{campaign_id}.xlsx`

## UI

Open `/bombar-production-dry-run`.

The page shows imported SKU count, ready/blocked SKU count, prompt packs, missing references, missing price, missing stock, paid calls, SKU readiness, blockers, next actions, and report paths.

## Safety Contract

- `paid_calls_made` must remain `0`.
- Prompt-only batch execution may run.
- Real video smoke is not started from this flow.
- Publishing remains blocked until packages are approved.
- External account registration is not part of this flow.
- Missing product photo/reference is surfaced as a production blocker.
