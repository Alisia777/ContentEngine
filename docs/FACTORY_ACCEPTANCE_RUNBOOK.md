# Factory Acceptance Runbook

Use this runbook after a prompt-only Factory OS launch.

## Acceptance Checks

- `paid_calls_made` is `0`;
- prompt packs are created or blockers explain why not;
- unsafe actions remain blocked;
- publishing packages are not auto-approved;
- distribution is planned only from approved packages;
- performance metrics are imported only from CSV;
- scaling recommendations are proposed or queued as safe action items;
- next manual actions are visible in `/factory-os`.

## Manual Next Steps

Typical next manual actions:

- attach and approve product references;
- review prompt-ready outputs;
- create or approve publishing packages only after human review;
- add destination capacity if distribution is blocked;
- import performance metrics after publication;
- review scaling recommendations before acting.

Paid real video generation and live publishing stay outside prompt-only acceptance.
