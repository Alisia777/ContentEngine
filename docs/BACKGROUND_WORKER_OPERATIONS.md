# Native background worker operations

## Production path

Production provider work is driven by Supabase itself:

1. Supabase Cron runs `contentengine-background-worker-v1` every two minutes.
2. The cron command uses `pg_net` to call
   `creator-background-worker`.
3. The function authenticates the request with the dedicated internal worker
   secret, obtains a database lease, and claims bounded Runway, product
   research, content-review and notification work.
4. Runway polling never repeats the paid create request. It only continues a
   task that already has a provider task ID.
5. The database stores the worker heartbeat, every worker run, generation
   poll state and durable notification delivery state.

The browser is not part of this path. Closing the portal does not pause a
submitted provider task.

## Secret boundary

The deployment job copies two values into Supabase Vault through the official
Management API:

- `contentengine_background_worker_url` — the reviewed project Edge Function
  URL;
- `contentengine_background_worker_secret` — the random 32+ character worker
  secret.

The secret is also synchronized to the Edge Function environment. It is never
committed, written to an artifact, returned by the configurator, or printed in
Actions output. The cron command reads the decrypted value only while building
the internal HTTP request.

Rotating `CONTENTENGINE_WORKER_SECRET` in the protected `production` GitHub
environment and running the deployment workflow updates both copies and
recreates the cron schedule idempotently.

## Scheduling and fallback

The GitHub `Watch background content health` workflow is not the production
timer. Its hourly run checks the authenticated Edge endpoint and notification
outbox without selecting any provider work; a manual `workflow_dispatch`
provides the same zero-provider-work smoke check. It does not validate the Cron
schedule and cannot replace the normal two-minute dispatch from Supabase Cron,
whose executions are recorded in `cron.job_run_details`.

Do not increase concurrency by adding another production timer. The database
lease intentionally permits only one active worker batch; overlapping calls
must return a non-error `already_running` result without claiming the same
work twice.

## Incident rules

- `queued` or `starting` without a provider task ID must never be retried by the
  background worker. An ambiguous paid create remains behind the existing
  reconciliation freeze.
- A submitted Runway task is polled according to its database-owned
  `next_poll_at`. Transient GET failures update poll diagnostics and backoff;
  they do not issue another paid POST.
- Pausing the platform or organization spend policy blocks new paid provider
  POSTs. It must not stop polling a Runway task that already has a provider
  task ID; doing so would hide an existing charge rather than prevent one.
- A job that exceeds the configured polling deadline is marked stalled and
  produces one deduplicated operator notification. A human checks Runway and
  completes the existing reconciliation flow.
- Terminal provider work and notification delivery are separate facts. A
  notification outbox failure does not roll a completed video back to
  processing.
- Never paste provider payloads, access tokens, recipient identifiers or
  notification bodies into an issue or workflow log.

## Release verification

After deployment, verify all of the following without reading Vault plaintext:

1. `cron.job` contains one active job named
   `contentengine-background-worker-v1` with the two-minute schedule.
2. Both named Vault rows exist.
3. A recent worker run/heartbeat appears after no more than two schedule
   intervals.
4. The manager health RPC reports `scheduler.ready=true`, a fresh worker
   heartbeat and `generation.stalled=0`.
5. A manual smoke dispatch with all queue limits set to zero returns `ok=true`,
   reports `notification.unresolved=0`, and does not call Runway or OpenAI.

If the cron job is absent, rerun the protected deployment. If cron is present
but no heartbeat appears, inspect `cron.job_run_details`, the `pg_net` response
table and the Edge Function logs in that order. Do not work around the incident
by starting another paid generation.
