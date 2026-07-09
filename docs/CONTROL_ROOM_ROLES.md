# Control Room Roles

## Owner / Founder

Sees production readiness, EngineAudit score, video quality, destination capacity, metrics coverage, payout exposure, paid smoke status, top blockers, and executive decisions.

## Content Lead

Sees products needing strategy, weak AI briefs, one-video plans, OutputAcceptance queue, regeneration requests, approved candidates, and missing product references.

## Campaign Operator

Sees campaign actions, safe batch actions, missing references, missing destinations, missing stats, blocked paid actions, and publishing readiness.

## Reviewer

Sees OutputAcceptance queue, product identity failures, packaging drift, edible identity mismatch, regeneration requests, and approve/reject/needs-regeneration links.

## Creator / Publisher

Sees assignments, missing final URLs, missing stats, training/certification blockers, payout blockers, and brief cards.

`creator` and `publisher` route to the `creator_publisher` dashboard so manual smoke URLs remain simple for operators.

## Metrics Operator

Sees unmatched rows, missing metrics, destinations without stats, funnel coverage, and CSV import actions.
