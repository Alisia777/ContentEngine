# Durable video content review

Updated: 2026-07-17

The MP4 review path is server-owned after the browser has persisted its
evidence. Closing or refreshing the portal does not cancel a queued review and
does not authorize a second provider request.

## User-visible flow

1. The browser samples four or five JPEG frames from the selected MP4.
2. It records exact object names, byte sizes, SHA-256 hashes, timecodes and the
   bounded technical metrics in a local recovery draft.
3. The private objects are uploaded with `upsert: false` and committed as one
   immutable evidence set.
4. Only committed evidence can be bound to a video review run.
5. The native background worker claims the run and continues after the tab is
   closed.
6. The manager dashboard shows queued, processing, due, retry-wait,
   dead-letter, outcome-unknown and oldest-queue-age values.

If the commit response is lost, the next submit replays the exact same manifest,
metrics and idempotency key. It does not upload the frames again and does not
create a new evidence set.

## Paid-call safety

Each run has at most three pre-dispatch attempts. A claim stays queued until a
transactional dispatch marker changes the attempt to `dispatching` and the run
to `processing`.

- failures before that marker can retry with bounded backoff;
- only the caller that acquired a new marker may make the provider POST;
- an idempotent replay of the marker is observation-only;
- a timeout after the marker is `outcome_unknown` and is never posted again;
- completion is fenced by review ID, attempt ID and lease token;
- the provider request ID is journaled when it is available.

The provider idempotency key remains a final defence, not the primary concurrency
control.

## Evidence integrity

The database validates organization and owner path, frame count, JPEG MIME,
stored byte size, source-media SHA snapshot and an immutable manifest. The Edge
worker downloads the committed private objects and independently validates JPEG
magic bytes, actual byte count and SHA-256 before any provider marker. The
technical metrics used by the review must exactly match the committed evidence
metrics.

Committed frames are protected from creator-side cleanup. A future retention
slice must add an audited service-role purge and tombstone workflow; deleting
immutable evidence directly is intentionally forbidden.

## Recovery states

- `claimed`: safe pre-provider lease; it may retry after expiry.
- `dispatching`: provider POST ownership has been recorded; no retry is allowed.
- `retry_wait`: bounded backoff before the next safe claim.
- `completed`: the exact fenced attempt wrote a terminal result.
- `dead_letter`: three safe pre-dispatch attempts were exhausted.
- `outcome_unknown`: dispatch began but its final provider outcome is not
  provable; manual reconciliation is required.

The manager health counters for `dead_letter` and `outcome_unknown` are
cumulative (`terminal_scope=all_time`) until an explicit incident-acknowledgment
workflow is added.

## Deployment and verification

The production workflow applies migrations, deploys the Edge Functions and then
publishes the versioned Pages bundle. MP4 review should be treated as briefly
unavailable during that rolling window: the new database fails old inline-frame
submissions closed, so no paid request or half-created durable run is produced.

Repository gates:

```text
supabase db lint --local --level error
supabase test db
deno fmt --check supabase/functions/creator-content-review
deno lint supabase/functions/creator-content-review/index.ts
deno check supabase/functions/creator-content-review/index.ts
python -m pytest -q -p scripts.pytest_shard_plugin
```

Provider-free smoke tests must not call OpenAI or Runway. A real canary is a
separate, explicitly approved operation with a confirmed budget.

## Remaining adjacent work

- auditable evidence retention, legal hold and purge;
- a unified Runway/OpenAI reservation and invoice-reconciliation ledger;
- audio transcription, speech/script agreement and full-timeline OCR;
- external incident alerts and a restore drill;
- a maintenance/feature flag for completely seamless rolling protocol changes.
