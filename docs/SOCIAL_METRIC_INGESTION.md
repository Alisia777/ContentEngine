# Safe social metric ingestion (P1)

The organization-safe write boundary is `POST /api/social-metrics`.
It accepts no `organization_id` or `user_id`; both values come from the
authenticated `PublicPilotUser`.

## Observation contract

Each observation must contain:

- an explicit `source_type` and non-secret logical `source_ref`;
- a social platform;
- `external_post_id`, `final_url`, or both;
- a timezone-aware `observed_at`;
- a closed `period_start` / `period_end` interval;
- at least one non-negative metric value.

`source_type` is an explicit audited declaration, not proof that an external
credential was used. Until organization-owned connector credentials exist, the
record is marked `declared_by_authenticated_actor` rather than “verified”.

Attribution is accepted only when the post resolves to exactly one chain:

`Organization -> Product -> PublishingPackage -> published PublishingTask -> PublishingDestination`.

Unscoped legacy products and tasks owned by another organization are never
claimed or repaired automatically. Unknown, conflicting, or ambiguous identity
goes to an organization-scoped `AuditLog` quarantine without creating a metric.
Placeholder/test hosts and URLs that do not match the declared social platform
are quarantined as well, so mock publications cannot satisfy production metrics.
Product, destination, task, package target, and platform must all agree.

## Idempotency and aggregation semantics

One `DestinationPostMetric` represents one cumulative snapshot for:

`organization + publishing_task + platform + period`.

A newer `observed_at` replaces each submitted field. Values are never added to
the previous snapshot. A field older than its stored provenance is recorded as
stale and ignored.
The same observation idempotency key is a no-op; reusing it for different data
is quarantined. This prevents report retries and connector refreshes from
inflating totals.

Partial observations merge only the fields they explicitly contain. Every field
keeps its own source and `observed_at`, so a delayed orders report can update
orders without erasing newer views. Conflicting values for the same field and
timestamp are quarantined. Overlapping, non-identical periods for one post are
also quarantined instead of being summed.

The legacy table has no database unique constraints for the canonical key or
observation key. The P1 service records a server-derived ledger in `AuditLog`
and serializes writes by organization at the database level (an organization
row lock, or a SQLite write lock) plus an in-process lock. Database unique
constraints are still required before allowing any writer to bypass this service:

- `UNIQUE (organization_id, observation_key)` on an observation ledger;
- `UNIQUE (organization_id, publishing_task_id, platform, period_start, period_end)`
  on the canonical post snapshot;
- an organization-scoped quarantine table with the observation fingerprint,
  reason, resolution status, and audit actor.

Legacy `/destination-connectors`, `/metrics-intake`, `/destination-control-tower`,
and `/campaign-performance` paths predate organization ownership. They remain
available in local legacy mode but fail closed in `PUBLIC_PILOT_MODE` or
`AUTH_REQUIRED` mode. The replacement route requires an actual bearer/session
token in either strict mode; development header identity is local-mode only.

`Campaign` and `DestinationConnection` still lack direct organization ownership,
so the safe metric omits their IDs. `PublishingDestination` is retained only
after exact organization and platform checks.
