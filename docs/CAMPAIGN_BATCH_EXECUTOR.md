# Campaign Batch Executor

Campaign Batch Executor is the v0.8 layer on top of Campaign Execution Control Center.

It does not create a new campaign core. It uses the existing `CampaignActionQueueItem` rows and only executes actions that pass safety gates.

## Workflow

```text
CampaignExecutionSnapshot
-> ActionQueue
-> select safe actions
-> dry run
-> execute batch
-> result log
-> refreshed execution snapshot
-> report
```

## Safe Batch Actions

The initial safe action set is:

- `prepare_content_run`
- `run_prompt_only`
- `build_prompt_pack`
- `create_publishing_package_draft`
- `create_regeneration_request`
- `create_distribution_task_draft`
- `export_operator_tasks_csv`

Current integration executes `run_prompt_only` through Campaign Execution / Campaign Autopilot. Other safe action types can be recorded as controlled safe actions when they appear in the queue.

## Blocked Actions

Batch execution blocks:

- `run_real_smoke`
- paid provider calls;
- publishing approval;
- live scheduling;
- publish/manual upload;
- mark published;
- external API upload;
- human-required actions;
- unsupported action types.

## UI

Open `/campaign-batch`.

The page supports:

- campaign selection;
- action type filtering;
- safe action count;
- skipped action reasons;
- dry run;
- safe batch execution;
- latest batch runs;
- JSON and CSV report summary.

## CLI

```bash
python scripts/campaign_batch_dry_run.py --campaign-id 1 --action-type run_prompt_only
python scripts/campaign_batch_execute.py --campaign-id 1 --action-type run_prompt_only
python scripts/campaign_batch_report.py --batch-run-id 1
python scripts/campaign_batch_report.py --batch-run-id 1 --format csv
```

## Persistence

`CampaignBatchRun` stores the batch summary, selected action IDs, result log, warnings, and errors.

`CampaignBatchItem` stores per-action status and result/error data.

## Acceptance

A batch run is valid when:

- dry-run selection includes only safe open actions;
- unsafe and paid actions are skipped;
- execution persists batch run and item rows;
- execution never calls paid providers by default;
- execution refreshes campaign execution snapshot;
- CLI and UI render batch results;
- `python -m pytest` passes.
