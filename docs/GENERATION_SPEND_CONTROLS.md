# Runway generation spend controls

The production database treats every real Runway request as a monetary
operation. Job-count quotas remain useful for load control, but they are not a
money limit. Migration `202607170002_generation_spend_budgets.sql` adds the
authoritative organization money gate; follow-on migration
`202607170003_generation_campaign_budgets.sql` adds mandatory campaign
attribution and campaign-level limits without rewriting the ledger.

## Safety model

- `mock` batches and jobs are unchanged and never create spend events.
- A private platform control is the global emergency stop. Only
  `service_role` can call `system_update_generation_spend_control`.
- Every organization needs an explicit policy with an enabled flag, daily,
  monthly and per-request limits, currency `USD`, IANA timezone, version and
  change reason.
- Every paid batch and job is bound to one organization campaign. Existing
  organizations receive one `default` campaign; owners/admins can create named
  campaigns for products or projects. Mock jobs remain campaign-optional.
- A paid reservation must fit both the organization policy and the selected
  campaign policy. Both decisions use the same organization advisory lock, so
  concurrent requests cannot spend the same remaining capacity.
- Organizations that existed when the migration was applied receive the
  conservative rollout policy: `$25/day`, `$100/month`, `$5/request`.
- An organization created later has no policy and is fail-closed. An owner or
  admin creates version `1` by sending `expected_version: 0` to
  `creator_update_generation_spend_policy`.
- A paid job and its `reserved` ledger event are committed in the same
  transaction. If a limit check fails, the job insert also rolls back.
- The database rechecks the global stop, organization switch, current limits,
  unresolved reconciliation incidents and the active reservation on the
  authoritative `queued -> starting` transition. The Edge Function therefore
  cannot perform a provider POST after a database rejection.

Organization policy changes do not rewrite an existing reservation. A pause
blocks its start; after a deliberate resume, the job may start only if the
current monetary limits still cover total reserved plus committed capacity.
The accounting timezone becomes immutable as soon as the organization has any
ledger event, including fully settled or released work. Otherwise a timezone
change at a day or month boundary could reinterpret immutable ledger periods
and incorrectly reopen guarded capacity.

## Append-only ledger

`content_factory.generation_spend_ledger` records one immutable event of each
applicable type per `generation_job_id`:

| Event | Reserved delta | Committed delta | Meaning |
| --- | ---: | ---: | --- |
| `reserved` | `+estimate` | `0` | Capacity held when the paid job is created |
| `settled` | `-estimate` | `+accounted cost` | Provider submission was confirmed |
| `released` | `-estimate` | `0` | A definitive failure happened before submission |
| `frozen` | `0` | `0` | Provider-create outcome is ambiguous and needs reconciliation |

Updates and deletes raise `generation_spend_ledger_append_only`. An ambiguous
provider response never releases capacity. Reconciliation either settles the
existing provider task or releases it only after an owner/admin confirms that
no submission exists.

`committed_minor` is the portal's accounted provider SKU estimate. It must not
be described as a reconciled Runway invoice amount until a provider billing
export or billing API is integrated.

## Browser RPCs

`creator_generation_spend_overview({ organization_id? })` is read-only for
active owner/admin/producer/operator members. Its stable response contract is:

```json
{
  "ok": true,
  "organization_id": "uuid",
  "currency": "USD",
  "blocker_code": null,
  "policy": {
    "paid_generation_enabled": true,
    "daily_limit_minor": 2500,
    "monthly_limit_minor": 10000,
    "per_request_limit_minor": 500,
    "timezone": "Europe/Moscow",
    "version": 1,
    "reason": "...",
    "updated_at": "...",
    "updated_by": "uuid-or-null"
  },
  "usage": {
    "day": {
      "period_start": "...",
      "period_end": "...",
      "reserved_minor": 0,
      "committed_minor": 0,
      "remaining_minor": 2500
    },
    "month": {
      "period_start": "...",
      "period_end": "...",
      "reserved_minor": 0,
      "committed_minor": 0,
      "remaining_minor": 10000
    }
  },
  "campaigns": [
    {
      "id": "uuid",
      "name": "Основная кампания",
      "kind": "default",
      "status": "active",
      "enabled": true,
      "blocker_code": null,
      "policy": {
        "paid_generation_enabled": true,
        "daily_limit_minor": 2500,
        "monthly_limit_minor": 10000,
        "per_request_limit_minor": 500,
        "version": 1
      },
      "usage": {
        "day": { "reserved_minor": 0, "committed_minor": 0, "remaining_minor": 2500 },
        "month": { "reserved_minor": 0, "committed_minor": 0, "remaining_minor": 10000 }
      }
    }
  ]
}
```

`creator_update_generation_spend_policy` is owner/admin only and requires all
policy fields, `expected_version` and `idempotency_key`. Exact retries return
the stored response; reused keys with different data fail. Stale versions raise
`generation_budget_policy_changed`.

`creator_create_generation_campaign` and
`creator_update_generation_campaign_spend_policy` are owner/admin-only,
idempotent mutations. Campaign policies cannot exceed the current
organization limits. Policy updates use `expected_version`; stale writes fail
with `generation_campaign_budget_policy_changed`.

The browser requires an explicit `campaign_id` for every real Runway start,
and the Edge Function validates it as a UUID before forwarding the request to
`creator_start_real_generation`. The database remains the authority: it binds
the batch and job, rejects inactive/paused campaigns, and rechecks capacity on
both reservation and `queued -> starting`.

Stable paid-generation blocker codes are:

- `paid_generation_paused`
- `paid_generation_policy_missing`
- `generation_daily_budget_exceeded`
- `generation_monthly_budget_exceeded`
- `generation_per_request_budget_exceeded`
- `generation_budget_reservation_invalid`
- `generation_budget_policy_changed`
- `paid_generation_campaign_required`
- `paid_generation_campaign_not_active`
- `paid_generation_campaign_policy_missing`
- `paid_generation_campaign_paused`
- `generation_campaign_daily_budget_exceeded`
- `generation_campaign_monthly_budget_exceeded`
- `generation_campaign_per_request_budget_exceeded`
- `generation_campaign_budget_policy_changed`
- `real_generation_reconciliation_required`

## Platform emergency stop

The service call uses optimistic versioning and records a mandatory reason and
operator identity:

```sql
select public.system_update_generation_spend_control(jsonb_build_object(
  'paid_generation_enabled', false,
  'expected_version', 1,
  'reason', 'Emergency pause while provider billing is investigated.',
  'changed_by', 'deployment incident INC-1234'
));
```

The emergency stop blocks new reservations and provider starts. It does not
interrupt status polling or storage of a task that was already submitted.

## Current boundary

These migrations implement platform, organization and campaign Runway
budgets. The ledger still records guarded SKU estimates rather than reconciled
provider invoices. Unified Runway/OpenAI invoice import and reconciliation is
separate follow-up work. Campaign budgets and unified Runway/OpenAI invoice reconciliation
remain distinct controls; no UI should describe committed estimates as settled provider
invoices.
