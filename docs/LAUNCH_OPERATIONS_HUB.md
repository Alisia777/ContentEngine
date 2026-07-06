# Launch Operations Hub

Launch Operations Hub is the v1.2 control layer that combines quality, campaign scale, and destination/account readiness.

It aggregates existing campaign, quality, publishing, destination, batch, performance, Factory OS, and Bombar dry-run state. It does not register external social accounts, use proxy/anti-detect logic, bypass approvals, auto-publish, or run paid provider calls in tests.

## Workflow

```text
Campaign / Bombar campaign
-> quality readiness
-> video approval readiness
-> destination capacity
-> distribution readiness
-> launch blockers
-> launch action plan
-> operator runbook export
```

## UI

Open `/launch-operations`.

The page shows launch overview, quality gates, destination capacity, action plan, launch blockers, and runbook export controls.

## CLI

```bash
python scripts/launch_readiness.py --campaign-id 1
python scripts/launch_quality_gates.py --campaign-id 1
python scripts/launch_destination_capacity.py --campaign-id 1
python scripts/launch_action_plan.py --campaign-id 1
python scripts/export_launch_runbook.py --campaign-id 1
```

## Safety

- Prompt-only content is not treated as publishable video.
- Videos without quality review are blocked.
- Human review, regeneration, product identity, and geometry blockers prevent publishing readiness.
- Destination capacity counts only active usable destinations.
- Action plan separates safe, human, paid, and publishing actions.
