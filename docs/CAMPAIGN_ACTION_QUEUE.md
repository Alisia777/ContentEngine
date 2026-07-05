# Campaign Action Queue

Campaign Action Queue turns campaign state into deduplicated operator actions.

The queue is intentionally conservative. It prepares the operator for scale, but it does not bypass review, payment, publishing, account, or platform gates.

## Model

`CampaignActionQueueItem` stores:

- campaign ID;
- optional product ID and SKU;
- optional content run ID;
- action type;
- priority;
- status;
- reason;
- blockers;
- `safe_to_execute`;
- `requires_human`.

## Action Types

Current MVP action types:

- `add_reference`: human task; product reference is missing before real generation.
- `run_prompt_only`: safe automated task; builds prompt-only content through CampaignRunner.
- `human_review`: human task; prompt-ready content needs review and approved output.
- `run_real_smoke`: paid task; blocked unless an explicit spend gate is passed.
- `create_publishing_package`: publishing task; blocked without approved video/package readiness.
- `schedule_distribution`: publishing task; blocked while distribution plan readiness is missing.

## Deduplication

Open and blocked actions are deduplicated by:

- campaign ID;
- action type;
- SKU;
- content run ID.

Refreshing the queue updates the existing item instead of creating repeated rows for the same SKU/content-run/action combination.

## Execution Rules

- Paid actions are blocked unless `allow_paid=true`.
- Publishing actions are blocked until approved package state exists.
- Unsafe actions are returned as blocked with `unsafe_action_requires_human`.
- Safe prompt-only execution delegates to Campaign Autopilot and keeps paid provider calls disabled.

## Operator Flow

```text
Refresh campaign execution
-> inspect blockers
-> inspect queue
-> execute safe actions
-> resolve human tasks after operator work
-> refresh again
-> export report
```

This queue is the bridge from campaign-scale planning to controlled execution for 40 SKU, 120 owned destinations, and 300-350 generated assets.
