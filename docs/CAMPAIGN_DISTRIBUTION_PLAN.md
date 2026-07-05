# Campaign Distribution Plan

Distribution planning takes approved publishing packages and available destinations, then creates calendar tasks while respecting destination limits.

Inputs:

- campaign products;
- approved publishing packages;
- available destinations;
- target destination count;
- date range.

Rules:

- Only packages with `review_status=approved` and ready/approved/scheduled/published status can be scheduled.
- Unapproved video packages are blocked.
- Destinations cannot exceed daily or weekly limits.
- Tasks are spread across destinations.
- SKU coverage is preferred by ordering packages by product.
- Blockers are created when approved packages or destination capacity are insufficient.

The plan creates normal `PublishingTask` rows for approved packages only. Prompt-only content remains review backlog until a real video exists and is human-approved.
