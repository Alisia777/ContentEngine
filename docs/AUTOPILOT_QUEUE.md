# Autopilot Queue

`AutopilotQueueItem` turns recommendations into an operator-facing decision queue.

Queue types:

- `autopilot` - safe action waiting to be executed or monitored
- `human_review` - visual review, identity mismatch, or regeneration decision
- `paid_review` - spend-gated real smoke
- `publishing_approval` - publishing package/task approval
- `exception` - missing geometry lock or other production blockers
- `performance` - scale/pause decisions
- `monitoring` - no immediate action available

The UI at `/content-autopilot` shows:

- products checked
- ready / blocked / human review counts
- publishing-ready count
- top blockers
- next actions
- decision queue
- human review queue

Resolving a queue item marks the operator decision as handled. It does not bypass provider spend gates, publishing approval, or visual review.
