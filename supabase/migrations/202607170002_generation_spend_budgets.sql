begin;

-- Paid provider calls need a monetary circuit breaker in addition to the
-- existing job-count quotas.  The browser never writes these tables directly:
-- owners/admins use one narrow policy RPC and provider workers cross an
-- authoritative trigger immediately before a queued job can become starting.

create table if not exists content_factory_private.generation_spend_platform_control (
  control_key text primary key check (control_key = 'runway_paid_generation'),
  paid_generation_enabled boolean not null,
  version bigint not null check (version >= 1),
  reason text not null check (
    length(btrim(reason)) between 8 and 500
    and reason !~ '[[:cntrl:]]'
  ),
  changed_by text not null check (
    length(btrim(changed_by)) between 3 and 180
    and changed_by !~ '[[:cntrl:]]'
  ),
  updated_at timestamptz not null default now()
);

insert into content_factory_private.generation_spend_platform_control (
  control_key,
  paid_generation_enabled,
  version,
  reason,
  changed_by
)
values (
  'runway_paid_generation',
  true,
  1,
  'Initial guarded rollout; organization limits remain authoritative.',
  'migration:202607170002'
)
on conflict (control_key) do nothing;

create table if not exists content_factory.generation_spend_policies (
  organization_id uuid primary key
    references content_factory.organizations(id) on delete cascade,
  paid_generation_enabled boolean not null default false,
  daily_limit_minor bigint not null check (
    daily_limit_minor between 1 and 1000000000000
  ),
  monthly_limit_minor bigint not null check (
    monthly_limit_minor between 1 and 1000000000000
  ),
  per_request_limit_minor bigint not null check (
    per_request_limit_minor between 1 and 1000000000000
  ),
  currency text not null default 'USD' check (currency = 'USD'),
  timezone text not null check (
    length(btrim(timezone)) between 3 and 100
    and timezone !~ '[[:cntrl:]]'
  ),
  version bigint not null default 1 check (version >= 1),
  reason text not null check (
    length(btrim(reason)) between 8 and 500
    and reason !~ '[[:cntrl:]]'
  ),
  updated_by uuid references content_factory.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (per_request_limit_minor <= daily_limit_minor),
  check (daily_limit_minor <= monthly_limit_minor)
);

-- Existing organizations retain paid generation, but only inside conservative
-- limits.  Organizations created after this migration have no row and fail
-- closed until an owner/admin explicitly creates version 1 with expected 0.
insert into content_factory.generation_spend_policies (
  organization_id,
  paid_generation_enabled,
  daily_limit_minor,
  monthly_limit_minor,
  per_request_limit_minor,
  currency,
  timezone,
  version,
  reason,
  updated_by
)
select
  organization.id,
  true,
  2500,
  10000,
  500,
  'USD',
  'Europe/Moscow',
  1,
  'Conservative default for an organization existing at guarded rollout.',
  null
from content_factory.organizations organization
on conflict (organization_id) do nothing;

create table if not exists content_factory.generation_spend_ledger (
  id bigint generated always as identity primary key,
  organization_id uuid not null,
  generation_job_id uuid not null,
  event_type text not null check (
    event_type in ('reserved', 'settled', 'released', 'frozen')
  ),
  estimated_cost_minor bigint not null check (estimated_cost_minor > 0),
  actual_cost_minor bigint not null default 0 check (actual_cost_minor >= 0),
  reserved_delta_minor bigint not null,
  committed_delta_minor bigint not null default 0 check (
    committed_delta_minor >= 0
  ),
  currency text not null check (currency = 'USD'),
  budget_day date not null,
  budget_month date not null,
  policy_version bigint not null check (policy_version >= 1),
  reason_code text not null check (
    reason_code ~ '^[a-z0-9_]{3,100}$'
  ),
  metadata jsonb not null default '{}'::jsonb check (
    jsonb_typeof(metadata) = 'object'
  ),
  created_at timestamptz not null default now(),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id)
    on delete restrict,
  unique (generation_job_id, event_type),
  check (budget_month = date_trunc('month', budget_day)::date),
  check (
    (
      event_type = 'reserved'
      and reserved_delta_minor = estimated_cost_minor
      and committed_delta_minor = 0
      and actual_cost_minor = 0
    )
    or (
      event_type = 'settled'
      and reserved_delta_minor = -estimated_cost_minor
      and committed_delta_minor = actual_cost_minor
      and actual_cost_minor > 0
    )
    or (
      event_type = 'released'
      and reserved_delta_minor = -estimated_cost_minor
      and committed_delta_minor = 0
      and actual_cost_minor = 0
    )
    or (
      event_type = 'frozen'
      and reserved_delta_minor = 0
      and committed_delta_minor = 0
      and actual_cost_minor = 0
    )
  )
);

create index if not exists generation_spend_ledger_org_day_idx
  on content_factory.generation_spend_ledger (
    organization_id, budget_day, event_type, generation_job_id
  );
create index if not exists generation_spend_ledger_org_month_idx
  on content_factory.generation_spend_ledger (
    organization_id, budget_month, event_type, generation_job_id
  );

alter table content_factory.generation_spend_policies enable row level security;
alter table content_factory.generation_spend_ledger enable row level security;

revoke all on content_factory.generation_spend_policies
  from public, anon, authenticated;
revoke all on content_factory.generation_spend_ledger
  from public, anon, authenticated;
revoke all on content_factory_private.generation_spend_platform_control
  from public, anon, authenticated;
revoke all on sequence content_factory.generation_spend_ledger_id_seq
  from public, anon, authenticated;
grant all on content_factory.generation_spend_policies to service_role;
grant all on content_factory.generation_spend_ledger to service_role;
grant all on content_factory_private.generation_spend_platform_control
  to service_role;
grant all on sequence content_factory.generation_spend_ledger_id_seq
  to service_role;

create or replace function content_factory_private.generation_spend_timezone_valid(
  timezone_value text
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select exists (
    select 1
    from pg_catalog.pg_timezone_names timezone_name
    where timezone_name.name = timezone_value
  )
$$;

create or replace function content_factory_private.guard_generation_spend_ledger_append_only()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_spend_ledger_append_only';
end;
$$;

drop trigger if exists generation_spend_ledger_append_only_guard
  on content_factory.generation_spend_ledger;
create trigger generation_spend_ledger_append_only_guard
before update or delete on content_factory.generation_spend_ledger
for each row execute function
  content_factory_private.guard_generation_spend_ledger_append_only();

-- Import any paid jobs created before this migration.  This is an accounting
-- bootstrap only; future reservations always cross the atomic trigger below.
insert into content_factory.generation_spend_ledger (
  organization_id,
  generation_job_id,
  event_type,
  estimated_cost_minor,
  actual_cost_minor,
  reserved_delta_minor,
  committed_delta_minor,
  currency,
  budget_day,
  budget_month,
  policy_version,
  reason_code,
  metadata,
  created_at
)
select
  job.organization_id,
  job.id,
  'reserved',
  job.estimated_cost_minor,
  0,
  job.estimated_cost_minor,
  0,
  'USD',
  (job.created_at at time zone policy.timezone)::date,
  date_trunc(
    'month',
    (job.created_at at time zone policy.timezone)::date
  )::date,
  policy.version,
  'migration_existing_job_reserved',
  jsonb_build_object(
    'migration', '202607170002',
    'status_at_import', job.status,
    'model', job.input ->> 'model'
  ),
  job.created_at
from content_factory.generation_jobs job
join content_factory.generation_spend_policies policy
  on policy.organization_id = job.organization_id
where job.mode = 'real'
  and job.provider = 'runway'
  and job.allow_real_spend
  and job.estimated_cost_minor > 0
on conflict (generation_job_id, event_type) do nothing;

insert into content_factory.generation_spend_ledger (
  organization_id, generation_job_id, event_type,
  estimated_cost_minor, actual_cost_minor,
  reserved_delta_minor, committed_delta_minor, currency,
  budget_day, budget_month, policy_version, reason_code, metadata, created_at
)
select
  reserved.organization_id,
  reserved.generation_job_id,
  'settled',
  reserved.estimated_cost_minor,
  job.actual_cost_minor,
  -reserved.estimated_cost_minor,
  job.actual_cost_minor,
  'USD',
  reserved.budget_day,
  reserved.budget_month,
  reserved.policy_version,
  'migration_existing_job_settled',
  jsonb_build_object(
    'migration', '202607170002',
    'status_at_import', job.status
  ),
  job.updated_at
from content_factory.generation_spend_ledger reserved
join content_factory.generation_jobs job
  on job.organization_id = reserved.organization_id
 and job.id = reserved.generation_job_id
where reserved.event_type = 'reserved'
  and job.actual_cost_minor > 0
on conflict (generation_job_id, event_type) do nothing;

insert into content_factory.generation_spend_ledger (
  organization_id, generation_job_id, event_type,
  estimated_cost_minor, actual_cost_minor,
  reserved_delta_minor, committed_delta_minor, currency,
  budget_day, budget_month, policy_version, reason_code, metadata, created_at
)
select
  reserved.organization_id,
  reserved.generation_job_id,
  'released',
  reserved.estimated_cost_minor,
  0,
  -reserved.estimated_cost_minor,
  0,
  'USD',
  reserved.budget_day,
  reserved.budget_month,
  reserved.policy_version,
  'migration_existing_job_released',
  jsonb_build_object(
    'migration', '202607170002',
    'status_at_import', job.status
  ),
  job.updated_at
from content_factory.generation_spend_ledger reserved
join content_factory.generation_jobs job
  on job.organization_id = reserved.organization_id
 and job.id = reserved.generation_job_id
where reserved.event_type = 'reserved'
  and job.status in ('failed', 'cancelled')
  and job.actual_cost_minor = 0
  and not content_factory_private.real_generation_reconciliation_unresolved(
    job.output
  )
on conflict (generation_job_id, event_type) do nothing;

insert into content_factory.generation_spend_ledger (
  organization_id, generation_job_id, event_type,
  estimated_cost_minor, actual_cost_minor,
  reserved_delta_minor, committed_delta_minor, currency,
  budget_day, budget_month, policy_version, reason_code, metadata, created_at
)
select
  reserved.organization_id,
  reserved.generation_job_id,
  'frozen',
  reserved.estimated_cost_minor,
  0,
  0,
  0,
  'USD',
  reserved.budget_day,
  reserved.budget_month,
  reserved.policy_version,
  'migration_existing_job_frozen',
  jsonb_build_object(
    'migration', '202607170002',
    'incident_id', job.output ->> 'reconciliation_incident_id'
  ),
  job.updated_at
from content_factory.generation_spend_ledger reserved
join content_factory.generation_jobs job
  on job.organization_id = reserved.organization_id
 and job.id = reserved.generation_job_id
where reserved.event_type = 'reserved'
  and content_factory_private.real_generation_reconciliation_unresolved(
    job.output
  )
on conflict (generation_job_id, event_type) do nothing;

create or replace function content_factory_private.reserve_real_generation_spend()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  platform_row content_factory_private.generation_spend_platform_control%rowtype;
  policy_row content_factory.generation_spend_policies%rowtype;
  budget_day_value date;
  budget_month_value date;
  day_reserved_minor bigint;
  day_committed_minor bigint;
  month_reserved_minor bigint;
  month_committed_minor bigint;
begin
  if new.mode <> 'real' or not new.allow_real_spend then
    return new;
  end if;
  if new.provider <> 'runway'
     or new.estimated_cost_minor <= 0
     or new.input #>> '{billing,currency}' is distinct from 'USD' then
    raise exception using
      errcode = '42501',
      message = 'generation_spend_provider_contract_invalid';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );

  select control.* into platform_row
  from content_factory_private.generation_spend_platform_control control
  where control.control_key = 'runway_paid_generation'
  for update;
  if platform_row.control_key is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_paused';
  end if;
  if not platform_row.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_paused';
  end if;

  select policy.* into policy_row
  from content_factory.generation_spend_policies policy
  where policy.organization_id = new.organization_id
  for update;
  if policy_row.organization_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;
  if not policy_row.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_paused';
  end if;
  if not content_factory_private.generation_spend_timezone_valid(
    policy_row.timezone
  ) then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;
  if new.estimated_cost_minor > policy_row.per_request_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_per_request_budget_exceeded';
  end if;

  budget_day_value := (clock_timestamp() at time zone policy_row.timezone)::date;
  budget_month_value := date_trunc('month', budget_day_value)::date;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into day_reserved_minor, day_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.budget_day = budget_day_value;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into month_reserved_minor, month_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.budget_month = budget_month_value;

  if day_reserved_minor + day_committed_minor + new.estimated_cost_minor
       > policy_row.daily_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_daily_budget_exceeded';
  end if;
  if month_reserved_minor + month_committed_minor + new.estimated_cost_minor
       > policy_row.monthly_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_monthly_budget_exceeded';
  end if;

  insert into content_factory.generation_spend_ledger (
    organization_id, generation_job_id, event_type,
    estimated_cost_minor, actual_cost_minor,
    reserved_delta_minor, committed_delta_minor, currency,
    budget_day, budget_month, policy_version, reason_code, metadata
  ) values (
    new.organization_id,
    new.id,
    'reserved',
    new.estimated_cost_minor,
    0,
    new.estimated_cost_minor,
    0,
    'USD',
    budget_day_value,
    budget_month_value,
    policy_row.version,
    'paid_job_created',
    jsonb_build_object(
      'provider', new.provider,
      'model', new.input ->> 'model',
      'requested_by', new.requested_by,
      'policy_reason', policy_row.reason
    )
  );

  -- Normal browser-created jobs are queued with zero actual cost.  Trusted
  -- fixtures/importers may insert a later provider state directly; record the
  -- corresponding terminal projection in the same transaction so no paid row
  -- can exist without complete accounting.
  if content_factory_private.real_generation_reconciliation_unresolved(
    new.output
  ) then
    insert into content_factory.generation_spend_ledger (
      organization_id, generation_job_id, event_type,
      estimated_cost_minor, actual_cost_minor,
      reserved_delta_minor, committed_delta_minor, currency,
      budget_day, budget_month, policy_version, reason_code, metadata
    ) values (
      new.organization_id, new.id, 'frozen', new.estimated_cost_minor, 0,
      0, 0, 'USD', budget_day_value, budget_month_value,
      policy_row.version, 'inserted_provider_state_frozen',
      jsonb_build_object(
        'incident_id', new.output ->> 'reconciliation_incident_id'
      )
    );
  end if;
  if new.actual_cost_minor > 0 then
    insert into content_factory.generation_spend_ledger (
      organization_id, generation_job_id, event_type,
      estimated_cost_minor, actual_cost_minor,
      reserved_delta_minor, committed_delta_minor, currency,
      budget_day, budget_month, policy_version, reason_code, metadata
    ) values (
      new.organization_id, new.id, 'settled', new.estimated_cost_minor,
      new.actual_cost_minor, -new.estimated_cost_minor,
      new.actual_cost_minor, 'USD', budget_day_value, budget_month_value,
      policy_row.version, 'inserted_provider_state_settled',
      jsonb_build_object(
        'status', new.status,
        'provider_task_id', new.output ->> 'provider_task_id',
        'accounting_basis', 'provider_sku_estimate'
      )
    );
  elsif new.status in ('failed', 'cancelled')
        and not content_factory_private.real_generation_reconciliation_unresolved(
          new.output
        ) then
    insert into content_factory.generation_spend_ledger (
      organization_id, generation_job_id, event_type,
      estimated_cost_minor, actual_cost_minor,
      reserved_delta_minor, committed_delta_minor, currency,
      budget_day, budget_month, policy_version, reason_code, metadata
    ) values (
      new.organization_id, new.id, 'released', new.estimated_cost_minor, 0,
      -new.estimated_cost_minor, 0, 'USD', budget_day_value,
      budget_month_value, policy_row.version,
      'inserted_provider_state_not_submitted',
      jsonb_build_object(
        'status', new.status,
        'failure_code', new.output ->> 'failure_code'
      )
    );
  end if;

  return new;
end;
$$;

drop trigger if exists generation_spend_reservation
  on content_factory.generation_jobs;
create trigger generation_spend_reservation
after insert on content_factory.generation_jobs
for each row execute function
  content_factory_private.reserve_real_generation_spend();

create or replace function content_factory_private.guard_real_generation_spend_start()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  platform_row content_factory_private.generation_spend_platform_control%rowtype;
  policy_row content_factory.generation_spend_policies%rowtype;
  reservation_row content_factory.generation_spend_ledger%rowtype;
  day_reserved_minor bigint;
  day_committed_minor bigint;
  month_reserved_minor bigint;
  month_committed_minor bigint;
begin
  if old.mode = 'real'
     and old.provider = 'runway'
     and old.allow_real_spend then
    if new.id is distinct from old.id
       or new.organization_id is distinct from old.organization_id
       or new.provider is distinct from old.provider
       or new.mode is distinct from old.mode
       or new.allow_real_spend is distinct from old.allow_real_spend
       or new.estimated_cost_minor is distinct from old.estimated_cost_minor
       or new.input #> '{billing,currency}'
          is distinct from old.input #> '{billing,currency}' then
      raise exception using
        errcode = '55000',
        message = 'generation_spend_reservation_identity_immutable';
    end if;
  elsif new.mode = 'real' and new.allow_real_spend then
    raise exception using
      errcode = '55000',
      message = 'generation_spend_paid_job_conversion_forbidden';
  end if;

  if old.status <> 'queued'
     or new.status <> 'starting'
     or new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );

  select control.* into platform_row
  from content_factory_private.generation_spend_platform_control control
  where control.control_key = 'runway_paid_generation'
  for update;
  if platform_row.control_key is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_paused';
  end if;
  if not platform_row.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_paused';
  end if;

  select policy.* into policy_row
  from content_factory.generation_spend_policies policy
  where policy.organization_id = new.organization_id
  for update;
  if policy_row.organization_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;
  if not policy_row.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_paused';
  end if;

  select ledger.* into reservation_row
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.generation_job_id = new.id
    and ledger.event_type = 'reserved';
  if reservation_row.id is null
     or reservation_row.estimated_cost_minor <> new.estimated_cost_minor
     or reservation_row.currency <> 'USD' then
    raise exception using
      errcode = '55000',
      message = 'generation_budget_reservation_invalid';
  end if;
  if exists (
    select 1
    from content_factory.generation_spend_ledger ledger
    where ledger.generation_job_id = new.id
      and ledger.event_type in ('settled', 'released')
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_budget_reservation_invalid';
  end if;
  if exists (
    select 1
    from content_factory.generation_spend_ledger ledger
    where ledger.generation_job_id = new.id
      and ledger.event_type = 'frozen'
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_budget_reservation_invalid';
  end if;
  if exists (
    select 1
    from content_factory.generation_jobs job
    where job.organization_id = new.organization_id
      and job.mode = 'real'
      and job.provider = 'runway'
      and job.allow_real_spend
      and content_factory_private.real_generation_reconciliation_unresolved(
        job.output
      )
  ) then
    raise exception using
      errcode = '55000',
      message = 'real_generation_reconciliation_required';
  end if;
  if new.estimated_cost_minor > policy_row.per_request_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_per_request_budget_exceeded';
  end if;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into day_reserved_minor, day_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.budget_day = reservation_row.budget_day;
  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into month_reserved_minor, month_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.budget_month = reservation_row.budget_month;

  if day_reserved_minor + day_committed_minor > policy_row.daily_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_daily_budget_exceeded';
  end if;
  if month_reserved_minor + month_committed_minor
       > policy_row.monthly_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_monthly_budget_exceeded';
  end if;

  return new;
end;
$$;

drop trigger if exists c_generation_spend_start_guard
  on content_factory.generation_jobs;
create trigger c_generation_spend_start_guard
before update of
  mode, provider, allow_real_spend, organization_id,
  estimated_cost_minor, status, input
on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_real_generation_spend_start();

create or replace function content_factory_private.record_real_generation_spend_lifecycle()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  reservation_row content_factory.generation_spend_ledger%rowtype;
  has_settlement boolean;
  has_release boolean;
begin
  if new.mode <> 'real'
     or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  if new.status is not distinct from old.status
     and new.actual_cost_minor is not distinct from old.actual_cost_minor
     and new.output is not distinct from old.output then
    return new;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );
  select ledger.* into reservation_row
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = new.organization_id
    and ledger.generation_job_id = new.id
    and ledger.event_type = 'reserved';
  if reservation_row.id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_budget_reservation_invalid';
  end if;

  if content_factory_private.real_generation_reconciliation_unresolved(
    new.output
  ) then
    insert into content_factory.generation_spend_ledger (
      organization_id, generation_job_id, event_type,
      estimated_cost_minor, actual_cost_minor,
      reserved_delta_minor, committed_delta_minor, currency,
      budget_day, budget_month, policy_version, reason_code, metadata
    ) values (
      new.organization_id,
      new.id,
      'frozen',
      reservation_row.estimated_cost_minor,
      0,
      0,
      0,
      'USD',
      reservation_row.budget_day,
      reservation_row.budget_month,
      reservation_row.policy_version,
      'provider_submission_ambiguous',
      jsonb_build_object(
        'incident_id', new.output ->> 'reconciliation_incident_id',
        'reason_code', new.output ->> 'reconciliation_reason_code'
      )
    )
    on conflict (generation_job_id, event_type) do nothing;
  end if;

  select
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'settled'
    ),
    exists (
      select 1 from content_factory.generation_spend_ledger ledger
      where ledger.generation_job_id = new.id
        and ledger.event_type = 'released'
    )
  into has_settlement, has_release;

  if new.actual_cost_minor > 0 then
    if has_release then
      raise exception using
        errcode = '55000',
        message = 'generation_budget_reservation_invalid';
    end if;
    if not has_settlement then
      insert into content_factory.generation_spend_ledger (
        organization_id, generation_job_id, event_type,
        estimated_cost_minor, actual_cost_minor,
        reserved_delta_minor, committed_delta_minor, currency,
        budget_day, budget_month, policy_version, reason_code, metadata
      ) values (
        new.organization_id,
        new.id,
        'settled',
        reservation_row.estimated_cost_minor,
        new.actual_cost_minor,
        -reservation_row.estimated_cost_minor,
        new.actual_cost_minor,
        'USD',
        reservation_row.budget_day,
        reservation_row.budget_month,
        reservation_row.policy_version,
        'provider_submission_confirmed',
        jsonb_build_object(
          'status', new.status,
          'provider_task_id', new.output ->> 'provider_task_id',
          'accounting_basis', 'provider_sku_estimate'
        )
      );
    end if;
  elsif new.status in ('failed', 'cancelled')
        and not content_factory_private.real_generation_reconciliation_unresolved(
          new.output
        ) then
    if has_settlement then
      raise exception using
        errcode = '55000',
        message = 'generation_budget_reservation_invalid';
    end if;
    if not has_release then
      insert into content_factory.generation_spend_ledger (
        organization_id, generation_job_id, event_type,
        estimated_cost_minor, actual_cost_minor,
        reserved_delta_minor, committed_delta_minor, currency,
        budget_day, budget_month, policy_version, reason_code, metadata
      ) values (
        new.organization_id,
        new.id,
        'released',
        reservation_row.estimated_cost_minor,
        0,
        -reservation_row.estimated_cost_minor,
        0,
        'USD',
        reservation_row.budget_day,
        reservation_row.budget_month,
        reservation_row.policy_version,
        case
          when new.output ->> 'reconciliation_resolution'
            = 'confirm_no_submission'
            then 'reconciliation_confirmed_not_submitted'
          else 'provider_submission_not_created'
        end,
        jsonb_build_object(
          'status', new.status,
          'failure_code', new.output ->> 'failure_code'
        )
      );
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists generation_spend_lifecycle
  on content_factory.generation_jobs;
create trigger generation_spend_lifecycle
after update of status, actual_cost_minor, output
on content_factory.generation_jobs
for each row execute function
  content_factory_private.record_real_generation_spend_lifecycle();

create or replace function content_factory_private.generation_spend_overview(
  organization_id_value uuid
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  platform_row content_factory_private.generation_spend_platform_control%rowtype;
  policy_row content_factory.generation_spend_policies%rowtype;
  timezone_value text;
  day_start_value timestamptz;
  day_end_value timestamptz;
  month_start_value timestamptz;
  month_end_value timestamptz;
  budget_day_value date;
  budget_month_value date;
  day_reserved_minor bigint := 0;
  day_committed_minor bigint := 0;
  month_reserved_minor bigint := 0;
  month_committed_minor bigint := 0;
  daily_limit_value bigint := 0;
  monthly_limit_value bigint := 0;
  per_request_limit_value bigint := 0;
  blocker_code_value text;
begin
  select control.* into platform_row
  from content_factory_private.generation_spend_platform_control control
  where control.control_key = 'runway_paid_generation';
  select policy.* into policy_row
  from content_factory.generation_spend_policies policy
  where policy.organization_id = organization_id_value;

  if policy_row.organization_id is null then
    timezone_value := 'UTC';
  else
    timezone_value := policy_row.timezone;
    daily_limit_value := policy_row.daily_limit_minor;
    monthly_limit_value := policy_row.monthly_limit_minor;
    per_request_limit_value := policy_row.per_request_limit_minor;
  end if;

  budget_day_value := (now() at time zone timezone_value)::date;
  budget_month_value := date_trunc('month', budget_day_value)::date;
  day_start_value := (
    date_trunc('day', now() at time zone timezone_value)
      at time zone timezone_value
  );
  day_end_value := (
    date_trunc('day', now() at time zone timezone_value) + interval '1 day'
  ) at time zone timezone_value;
  month_start_value := (
    date_trunc('month', now() at time zone timezone_value)
      at time zone timezone_value
  );
  month_end_value := (
    date_trunc('month', now() at time zone timezone_value) + interval '1 month'
  ) at time zone timezone_value;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into day_reserved_minor, day_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.budget_day = budget_day_value;
  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into month_reserved_minor, month_committed_minor
  from content_factory.generation_spend_ledger ledger
  where ledger.organization_id = organization_id_value
    and ledger.budget_month = budget_month_value;

  blocker_code_value := case
    when platform_row.control_key is null
      then 'paid_generation_paused'
    when not platform_row.paid_generation_enabled
      then 'paid_generation_paused'
    when policy_row.organization_id is null
      then 'paid_generation_policy_missing'
    when not policy_row.paid_generation_enabled
      then 'paid_generation_paused'
    when exists (
      select 1
      from content_factory.generation_jobs job
      where job.organization_id = organization_id_value
        and job.mode = 'real'
        and job.provider = 'runway'
        and job.allow_real_spend
        and content_factory_private.real_generation_reconciliation_unresolved(
          job.output
        )
    ) then 'real_generation_reconciliation_required'
    when day_reserved_minor + day_committed_minor >= daily_limit_value
      then 'generation_daily_budget_exceeded'
    when month_reserved_minor + month_committed_minor >= monthly_limit_value
      then 'generation_monthly_budget_exceeded'
    else null
  end;

  return jsonb_build_object(
    'ok', true,
    'organization_id', organization_id_value,
    'currency', 'USD',
    'blocker_code', blocker_code_value,
    'policy', jsonb_build_object(
      'paid_generation_enabled', coalesce(
        policy_row.paid_generation_enabled,
        false
      ),
      'daily_limit_minor', daily_limit_value,
      'monthly_limit_minor', monthly_limit_value,
      'per_request_limit_minor', per_request_limit_value,
      'timezone', timezone_value,
      'version', coalesce(policy_row.version, 0),
      'reason', coalesce(
        policy_row.reason,
        'generation_spend_policy_missing'
      ),
      'updated_at', policy_row.updated_at,
      'updated_by', policy_row.updated_by
    ),
    'usage', jsonb_build_object(
      'day', jsonb_build_object(
        'period_start', day_start_value,
        'period_end', day_end_value,
        'reserved_minor', greatest(day_reserved_minor, 0),
        'committed_minor', day_committed_minor,
        'remaining_minor', greatest(
          daily_limit_value - day_reserved_minor - day_committed_minor,
          0
        )
      ),
      'month', jsonb_build_object(
        'period_start', month_start_value,
        'period_end', month_end_value,
        'reserved_minor', greatest(month_reserved_minor, 0),
        'committed_minor', month_committed_minor,
        'remaining_minor', greatest(
          monthly_limit_value - month_reserved_minor - month_committed_minor,
          0
        )
      )
    )
  );
end;
$$;

create or replace function public.creator_generation_spend_overview(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  organization_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_overview_payload_invalid';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin', 'producer', 'operator']
  );
  return content_factory_private.generation_spend_overview(organization_id);
end;
$$;

create or replace function public.creator_update_generation_spend_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  idempotency_key_value text;
  expected_version_value bigint;
  paid_generation_enabled_value boolean;
  daily_limit_value bigint;
  monthly_limit_value bigint;
  per_request_limit_value bigint;
  timezone_value text;
  reason_value text;
  request_payload jsonb;
  replay jsonb;
  policy_row content_factory.generation_spend_policies%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'paid_generation_enabled',
    'daily_limit_minor', 'monthly_limit_minor',
    'per_request_limit_minor', 'timezone', 'reason',
    'expected_version', 'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'paid_generation_enabled'
       and p_payload ? 'daily_limit_minor'
       and p_payload ? 'monthly_limit_minor'
       and p_payload ? 'per_request_limit_minor'
       and p_payload ? 'timezone'
       and p_payload ? 'reason'
       and p_payload ? 'expected_version'
       and p_payload ? 'idempotency_key'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_policy_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin']
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if p_payload -> 'paid_generation_enabled'
       not in ('true'::jsonb, 'false'::jsonb)
     or jsonb_typeof(p_payload -> 'expected_version') <> 'number'
     or coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'daily_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'daily_limit_minor', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'monthly_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'monthly_limit_minor', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'per_request_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'per_request_limit_minor', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_policy_values_invalid';
  end if;
  begin
    expected_version_value := (p_payload ->> 'expected_version')::bigint;
    daily_limit_value := (p_payload ->> 'daily_limit_minor')::bigint;
    monthly_limit_value := (p_payload ->> 'monthly_limit_minor')::bigint;
    per_request_limit_value :=
      (p_payload ->> 'per_request_limit_minor')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_policy_values_invalid';
  end;
  paid_generation_enabled_value :=
    (p_payload ->> 'paid_generation_enabled')::boolean;
  timezone_value := content_factory_private.require_text(
    p_payload,
    'timezone',
    3,
    100
  );
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    8,
    500
  );

  if expected_version_value < 0
     or daily_limit_value not between 1 and 1000000000000
     or monthly_limit_value not between 1 and 1000000000000
     or per_request_limit_value not between 1 and 1000000000000
     or per_request_limit_value > daily_limit_value
     or daily_limit_value > monthly_limit_value
     or reason_value ~ '[[:cntrl:]]'
     or not content_factory_private.generation_spend_timezone_valid(
       timezone_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_policy_values_invalid';
  end if;

  request_payload := jsonb_build_object(
    'paid_generation_enabled', paid_generation_enabled_value,
    'daily_limit_minor', daily_limit_value,
    'monthly_limit_minor', monthly_limit_value,
    'per_request_limit_minor', per_request_limit_value,
    'timezone', timezone_value,
    'reason', reason_value,
    'expected_version', expected_version_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_update_generation_spend_policy',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('generation_spend_budget')
  );
  select policy.* into policy_row
  from content_factory.generation_spend_policies policy
  where policy.organization_id = organization_id
  for update;

  if policy_row.organization_id is null then
    if expected_version_value <> 0 then
      raise exception using
        errcode = '40001',
        message = 'generation_budget_policy_changed';
    end if;
    insert into content_factory.generation_spend_policies (
      organization_id, paid_generation_enabled,
      daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
      currency, timezone, version, reason, updated_by
    ) values (
      organization_id,
      paid_generation_enabled_value,
      daily_limit_value,
      monthly_limit_value,
      per_request_limit_value,
      'USD',
      timezone_value,
      1,
      reason_value,
      user_id
    )
    returning * into policy_row;
  else
    if policy_row.version <> expected_version_value then
      raise exception using
        errcode = '40001',
        message = 'generation_budget_policy_changed';
    end if;
    -- Ledger periods are immutable accounting facts.  Reinterpreting them
    -- under a different timezone after any spend event could make committed
    -- money disappear from the current day/month and reopen guarded capacity.
    if timezone_value is distinct from policy_row.timezone
       and exists (
         select 1
         from content_factory.generation_spend_ledger ledger
         where ledger.organization_id = organization_id
       ) then
      raise exception using
        errcode = '55000',
        message = 'generation_budget_policy_changed';
    end if;
    update content_factory.generation_spend_policies policy
    set paid_generation_enabled = paid_generation_enabled_value,
        daily_limit_minor = daily_limit_value,
        monthly_limit_minor = monthly_limit_value,
        per_request_limit_minor = per_request_limit_value,
        timezone = timezone_value,
        version = policy.version + 1,
        reason = reason_value,
        updated_by = user_id,
        updated_at = now()
    where policy.organization_id = organization_id
    returning * into policy_row;
  end if;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'generation_spend_policy_updated',
    'generation_spend_policy',
    organization_id::text,
    jsonb_build_object(
      'paid_generation_enabled', policy_row.paid_generation_enabled,
      'daily_limit_minor', policy_row.daily_limit_minor,
      'monthly_limit_minor', policy_row.monthly_limit_minor,
      'per_request_limit_minor', policy_row.per_request_limit_minor,
      'currency', 'USD',
      'timezone', policy_row.timezone,
      'version', policy_row.version,
      'reason', policy_row.reason
    ),
    'generation-spend-policy:' || organization_id::text || ':' ||
      policy_row.version::text
  );

  result := content_factory_private.generation_spend_overview(organization_id);
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_update_generation_spend_policy',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

create or replace function public.system_update_generation_spend_control(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  expected_version_value bigint;
  enabled_value boolean;
  reason_value text;
  changed_by_value text;
  control_row content_factory_private.generation_spend_platform_control%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'paid_generation_enabled', 'expected_version', 'reason', 'changed_by'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'paid_generation_enabled'
       and p_payload ? 'expected_version'
       and p_payload ? 'reason'
       and p_payload ? 'changed_by'
     )
     or p_payload -> 'paid_generation_enabled'
       not in ('true'::jsonb, 'false'::jsonb)
     or jsonb_typeof(p_payload -> 'expected_version') <> 'number'
     or coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_control_payload_invalid';
  end if;
  begin
    expected_version_value := (p_payload ->> 'expected_version')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_control_payload_invalid';
  end;
  if expected_version_value < 1 then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_control_payload_invalid';
  end if;
  enabled_value := (p_payload ->> 'paid_generation_enabled')::boolean;
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 8, 500
  );
  changed_by_value := content_factory_private.require_text(
    p_payload, 'changed_by', 3, 180
  );
  if reason_value ~ '[[:cntrl:]]' or changed_by_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'generation_spend_control_payload_invalid';
  end if;

  perform pg_advisory_xact_lock(hashtext('generation_spend_platform_control'));
  select control.* into control_row
  from content_factory_private.generation_spend_platform_control control
  where control.control_key = 'runway_paid_generation'
  for update;
  if control_row.control_key is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_paused';
  end if;
  if control_row.version <> expected_version_value then
    raise exception using
      errcode = '40001',
      message = 'generation_budget_policy_changed';
  end if;

  update content_factory_private.generation_spend_platform_control control
  set paid_generation_enabled = enabled_value,
      version = control.version + 1,
      reason = reason_value,
      changed_by = changed_by_value,
      updated_at = now()
  where control.control_key = 'runway_paid_generation'
  returning * into control_row;

  return jsonb_build_object(
    'ok', true,
    'control', jsonb_build_object(
      'paid_generation_enabled', control_row.paid_generation_enabled,
      'version', control_row.version,
      'reason', control_row.reason,
      'changed_by', control_row.changed_by,
      'updated_at', control_row.updated_at
    )
  );
end;
$$;

revoke all on function
  content_factory_private.generation_spend_timezone_valid(text)
  from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_generation_spend_ledger_append_only()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.reserve_real_generation_spend()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.guard_real_generation_spend_start()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.record_real_generation_spend_lifecycle()
  from public, anon, authenticated;
revoke all on function
  content_factory_private.generation_spend_overview(uuid)
  from public, anon, authenticated;

revoke all on function public.creator_generation_spend_overview(jsonb)
  from public, anon;
grant execute on function public.creator_generation_spend_overview(jsonb)
  to authenticated;
revoke all on function public.creator_update_generation_spend_policy(jsonb)
  from public, anon;
grant execute on function public.creator_update_generation_spend_policy(jsonb)
  to authenticated;
revoke all on function public.system_update_generation_spend_control(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_update_generation_spend_control(jsonb)
  to service_role;

commit;
