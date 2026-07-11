# Durable Product UGC queue: operations

Paid Product UGC generation is handled by a durable database queue. A web
request may help process the first attempt, but production readiness requires a
continuously supervised worker.

## Supervised launch

The repository includes a separate `product-ugc-worker` service with
`restart: unless-stopped` and a database-backed health check:

```bash
docker compose up --build app product-ugc-worker
docker compose ps
```

The worker command is:

```bash
python scripts/run_product_ugc_queue_worker.py \
  --poll-seconds 2 \
  --lease-seconds 300 \
  --stale-after-seconds 300
```

For an external supervisor, use the read-only readiness check:

```bash
python scripts/run_product_ugc_queue_worker.py \
  --health-check \
  --healthy-within-seconds 120
```

It exits `0` only when a recent durable worker heartbeat exists. It never
leases or processes a generation job. The novice workbench and
`GET /api/factory-dashboard` expose the same secret-free state, ready-job
count, stale leases, and queue lag as `generation_queue_operations`.
An ephemeral web background attempt is recorded for job safety but is not
counted as supervised readiness; only the long-running worker can make
`worker_ready=true`.

Use PostgreSQL for multi-instance production. The bundled SQLite compose setup
is suitable for one-host pilot operation, not horizontal worker scaling.

## Ambiguous provider submission

If the paid provider request may have been accepted but its task id was not
saved, the job is quarantined. Automatic and ordinary manual retries remain
forbidden. An active organization owner or admin must inspect the provider
console and choose exactly one resolution:

1. **Existing task found.** Copy the verified `provider_task_id`, enter a
   non-secret audit/support reference and a reason. The worker will only poll
   and download that existing task; it cannot issue a new provider submit.
2. **No submission exists.** Enter the provider audit/support reference and a
   reason, then explicitly confirm that the provider has no matching task. The
   immutable evidence record is committed before the spend guard is cleared.
   One new attempt is then allowed, and active owner/admin spend authority is
   checked again immediately before the provider POST.

Every resolution is organization-scoped, owner/admin-only, idempotent, audited,
and stored in the append-only `product_ugc_queue_reconciliations` table. Updates
and deletes are blocked by ORM guards and database triggers. Never paste API
keys, bearer tokens, signed URLs, cookies, or provider credentials into the
evidence fields.

## Readiness interpretation

- `worker_ready=false`: generation capacity is not confirmed; restore the
  supervised worker before promising a launch time.
- `queue_lag_seconds>0`: at least one ready job is overdue for a worker lease.
- `stale_leases>0`: a worker disappeared while holding work; the normal stale
  reconciliation loop will release, terminalize, or quarantine it according to
  the at-most-once spend guard.
- `reconciliation_required=true` on a job: do not use ordinary retry; perform
  the provider-console workflow above.
