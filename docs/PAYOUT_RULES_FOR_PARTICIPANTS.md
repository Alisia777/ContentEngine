# Payout Rules For Participants

Payouts are ledger entries, not automatic payments.

## Inputs

- assignment;
- submission;
- publishing task;
- final URL;
- metrics;
- payout rule.

## Rule Types

- `per_video`
- `per_approved_post`
- `per_published_post`
- `cpa`
- `revenue_share`
- `hybrid`

## Statuses

- `pending`: calculated, not yet approved.
- `approved`: reviewed internally.
- `payable`: ready for manual payment workflow.
- `paid`: operator marked as paid.
- `disputed`: needs review.
- `rejected`: excluded from payment.

`per_published_post` requires a publishing task with `final_url`. CPA and revenue-share rules require attributed metrics.
