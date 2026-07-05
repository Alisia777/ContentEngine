# Campaign Execution Control Center

Campaign Execution Control Center is the v0.7 operator layer for running a campaign after the Campaign Autopilot and Bombar adapter have prepared campaign state.

It does not replace Campaign Autopilot. It reads the existing campaign, campaign products, content runs, publishing packages, distribution plans, and performance metrics, then exposes:

- campaign execution snapshot;
- exact blockers by type;
- safe next actions;
- SKU-level state;
- report export as JSON and summary CSV.

## UI

Open `/campaign-execution`.

The page contains:

- Campaign Overview;
- Blockers;
- Action Queue;
- SKU Table;
- Report with JSON and CSV summary.

For Bombar campaigns, the page links back to `/bombar-launch`. For all campaigns, it links to `/campaign-autopilot`.

## API

All API routes are read/safe by default, except action execution. Paid actions still require an explicit gate.

```text
GET  /api/campaign-execution/{campaign_id}/snapshot
POST /api/campaign-execution/{campaign_id}/refresh
GET  /api/campaign-execution/{campaign_id}/actions
POST /api/campaign-execution/actions/{id}/execute
POST /api/campaign-execution/actions/{id}/resolve
GET  /api/campaign-execution/{campaign_id}/report
```

## CLI

```bash
python scripts/campaign_execution_snapshot.py --campaign-id 1
python scripts/campaign_execution_refresh.py --campaign-id 1
python scripts/campaign_execution_actions.py --campaign-id 1
python scripts/campaign_execution_report.py --campaign-id 1
python scripts/campaign_execution_report.py --campaign-id 1 --format csv
```

## Snapshot

`CampaignExecutionSnapshot` stores the latest execution dashboard facts:

- total, ready, and blocked SKU counts;
- prompt-ready, real-smoke-ready, needs-review, approved-video counts;
- publishing package readiness;
- distribution task readiness;
- blocker summary;
- next actions.

## Safety Rules

- Safe actions can run by default.
- Paid actions require an explicit gate.
- Publishing actions require approved video/package state.
- Blocked SKU rows must expose exact blockers.
- Generated videos are never auto-approved by this layer.
- Tests must not call paid providers.

## Acceptance

A campaign execution checkpoint is valid when:

- snapshot refresh succeeds;
- blockers are explicit;
- action queue is deduplicated;
- paid action execution is blocked without a gate;
- publishing is blocked without approved video/package state;
- report JSON and summary CSV are available;
- `/campaign-execution` renders the operator dashboard.
