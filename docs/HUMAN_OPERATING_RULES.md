# Human Operating Rules

Every publication must be connected to ContentEngine.

Minimum traceability fields:

- `campaign_id`
- `publishing_task_id`
- `destination_id`
- `participant_id`
- `sku`
- `creative_variant_id`
- `tracking_link`
- `final_url`
- `posted_at`
- `metrics_period`

If these fields are missing, the publication is incomplete: stats will not map, payouts will not calculate correctly, and recommendations will be weak.

## Roles

Participants, creators, publishers, partners, reviewers, operators, and admins must work through assignments, destinations, publishing tasks, metrics imports, and payout ledger entries.

## Core Rules

1. Work only through an assignment.
2. Publish only approved video.
3. Use the tracking link in the post.
4. Submit the final platform URL after publication.
5. Submit statistics with `posted_url` or `tracking_slug`.
6. Payouts are calculated only from traceable assignments and metrics.
7. Anything without links and metrics is not complete.

## Forbidden

- Publishing without an assignment.
- Publishing an unapproved video.
- Replacing a tracking link with a direct product URL.
- Skipping `final_url`.
- Uploading stats without a post URL or tracking slug.
- Using another participant's destination.
- Changing the brief without approval.
- Publishing distorted product visuals.
- Calculating payments outside the payout ledger.
