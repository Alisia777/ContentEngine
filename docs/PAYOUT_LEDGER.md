# Payout Ledger

v1.7 adds a payout ledger, not payment execution.

Supported rule types:

- `per_video`
- `per_published_post`
- `per_approved_post`
- `cpa`
- `revenue_share`
- `hybrid`

Ledger statuses:

- `pending`
- `approved`
- `payable`
- `paid`
- `rejected`
- `disputed`

Payments are made manually outside the system. ContentEngine records the calculated ledger entry, reason, period, status, and manual `mark-paid` action. Raw payout or bank secrets are not stored or rendered.
