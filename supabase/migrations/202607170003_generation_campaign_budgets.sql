begin;

-- A campaign is a durable accounting dimension.  Products, batches, review
-- tasks and workspace folders are intentionally not used as substitutes: a
-- campaign can span products and its identity must not move with UI layout.
create table if not exists content_factory.generation_campaigns (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null
    references content_factory.organizations(id) on delete cascade,
  name text not null check (
    length(btrim(name)) between 2 and 160
    and name !~ '[[:cntrl:]]'
  ),
  kind text not null default 'managed'
    check (kind in ('default', 'managed')),
  status text not null default 'active'
    check (status in ('draft', 'active', 'paused', 'completed', 'archived')),
  version bigint not null default 1 check (version >= 1),
  created_by uuid,
  updated_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (organization_id, created_by)
    references content_factory.memberships(organization_id, profile_id),
  foreign key (organization_id, updated_by)
    references content_factory.memberships(organization_id, profile_id),
  unique (organization_id, id),
  check (
    (kind = 'default' and created_by is null)
    or (kind = 'managed' and created_by is not null)
  )
);

create unique index if not exists generation_campaigns_default_org_uq
  on content_factory.generation_campaigns (organization_id)
  where kind = 'default';
create index if not exists generation_campaigns_org_status_idx
  on content_factory.generation_campaigns (
    organization_id, status, updated_at desc, id
  );

create table if not exists content_factory.generation_campaign_spend_policies (
  organization_id uuid not null,
  campaign_id uuid not null,
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
  version bigint not null default 1 check (version >= 1),
  reason text not null check (
    length(btrim(reason)) between 8 and 500
    and reason !~ '[[:cntrl:]]'
  ),
  updated_by uuid references content_factory.profiles(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (organization_id, campaign_id),
  foreign key (organization_id, campaign_id)
    references content_factory.generation_campaigns(organization_id, id)
    on delete restrict,
  check (per_request_limit_minor <= daily_limit_minor),
  check (daily_limit_minor <= monthly_limit_minor)
);

alter table content_factory.generation_campaigns enable row level security;
alter table content_factory.generation_campaign_spend_policies
  enable row level security;
revoke all on content_factory.generation_campaigns
  from public, anon, authenticated;
revoke all on content_factory.generation_campaign_spend_policies
  from public, anon, authenticated;
grant all on content_factory.generation_campaigns to service_role;
grant all on content_factory.generation_campaign_spend_policies to service_role;

-- Every organization receives one durable compatibility campaign.  It keeps
-- already queued jobs attributable without silently weakening organization
-- limits.  Named campaigns can then be added by owners/admins.
insert into content_factory.generation_campaigns (
  organization_id, name, kind, status, created_by, updated_by
)
select
  organization.id,
  'Основная кампания',
  'default',
  'active',
  null,
  null
from content_factory.organizations organization
on conflict (organization_id) where kind = 'default' do nothing;

insert into content_factory.generation_campaign_spend_policies (
  organization_id, campaign_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, version, reason, updated_by
)
select
  campaign.organization_id,
  campaign.id,
  organization_policy.paid_generation_enabled,
  organization_policy.daily_limit_minor,
  organization_policy.monthly_limit_minor,
  organization_policy.per_request_limit_minor,
  'USD',
  1,
  'Compatibility campaign inherits the guarded organization rollout limits.',
  organization_policy.updated_by
from content_factory.generation_campaigns campaign
join content_factory.generation_spend_policies organization_policy
  on organization_policy.organization_id = campaign.organization_id
where campaign.kind = 'default'
on conflict (organization_id, campaign_id) do nothing;

create or replace function content_factory_private.initialize_generation_campaign()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.generation_campaigns (
    organization_id, name, kind, status, created_by, updated_by
  ) values (
    new.id, 'Основная кампания', 'default', 'active', null, null
  )
  on conflict (organization_id) where kind = 'default' do nothing;
  return new;
end;
$$;

drop trigger if exists initialize_generation_campaign
  on content_factory.organizations;
create trigger initialize_generation_campaign
after insert on content_factory.organizations
for each row execute function
  content_factory_private.initialize_generation_campaign();

create or replace function content_factory_private.initialize_default_campaign_policy()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into content_factory.generation_campaign_spend_policies (
    organization_id, campaign_id, paid_generation_enabled,
    daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
    currency, version, reason, updated_by
  )
  select
    new.organization_id,
    campaign.id,
    new.paid_generation_enabled,
    new.daily_limit_minor,
    new.monthly_limit_minor,
    new.per_request_limit_minor,
    'USD',
    1,
    'Default campaign initialized from guarded organization limits.',
    new.updated_by
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = new.organization_id
    and campaign.kind = 'default'
  on conflict (organization_id, campaign_id) do nothing;
  return new;
end;
$$;

drop trigger if exists initialize_default_campaign_policy
  on content_factory.generation_spend_policies;
create trigger initialize_default_campaign_policy
after insert on content_factory.generation_spend_policies
for each row execute function
  content_factory_private.initialize_default_campaign_policy();

alter table content_factory.generation_batches
  add column if not exists campaign_id uuid;
alter table content_factory.generation_jobs
  add column if not exists campaign_id uuid;

update content_factory.generation_batches batch
set campaign_id = campaign.id
from content_factory.generation_campaigns campaign
where batch.organization_id = campaign.organization_id
  and campaign.kind = 'default'
  and batch.mode = 'real'
  and batch.allow_real_spend
  and batch.campaign_id is null;

update content_factory.generation_jobs job
set campaign_id = campaign.id
from content_factory.generation_campaigns campaign
where job.organization_id = campaign.organization_id
  and campaign.kind = 'default'
  and job.mode = 'real'
  and job.allow_real_spend
  and job.campaign_id is null;

alter table content_factory.generation_batches
  drop constraint if exists generation_batches_campaign_fk,
  drop constraint if exists generation_batches_paid_campaign_check,
  add constraint generation_batches_campaign_fk
    foreign key (organization_id, campaign_id)
    references content_factory.generation_campaigns(organization_id, id)
    on delete restrict,
  add constraint generation_batches_paid_campaign_check check (
    mode <> 'real' or not allow_real_spend or campaign_id is not null
  );

alter table content_factory.generation_jobs
  drop constraint if exists generation_jobs_campaign_fk,
  drop constraint if exists generation_jobs_paid_campaign_check,
  add constraint generation_jobs_campaign_fk
    foreign key (organization_id, campaign_id)
    references content_factory.generation_campaigns(organization_id, id)
    on delete restrict,
  add constraint generation_jobs_paid_campaign_check check (
    mode <> 'real' or not allow_real_spend or campaign_id is not null
  );

create index if not exists generation_batches_campaign_idx
  on content_factory.generation_batches (
    organization_id, campaign_id, created_at desc, id
  ) where campaign_id is not null;
create index if not exists generation_jobs_campaign_idx
  on content_factory.generation_jobs (
    organization_id, campaign_id, status, created_at desc, id
  ) where campaign_id is not null;

create or replace function content_factory_private.bind_paid_generation_campaign()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  campaign_id_value uuid;
  configured_campaign text;
  campaign_row content_factory.generation_campaigns%rowtype;
  batch_campaign_id uuid;
begin
  if new.mode <> 'real' or not new.allow_real_spend then
    return new;
  end if;

  campaign_id_value := new.campaign_id;
  if campaign_id_value is null then
    configured_campaign := nullif(
      current_setting('content_factory.generation_campaign_id', true),
      ''
    );
    if configured_campaign is not null then
      begin
        campaign_id_value := configured_campaign::uuid;
      exception when invalid_text_representation then
        raise exception using
          errcode = '22023',
          message = 'paid_generation_campaign_required';
      end;
    end if;
  end if;
  if campaign_id_value is null then
    select campaign.id into campaign_id_value
    from content_factory.generation_campaigns campaign
    where campaign.organization_id = new.organization_id
      and campaign.kind = 'default';
  end if;
  if campaign_id_value is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;

  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = new.organization_id
    and campaign.id = campaign_id_value
  for key share;
  if campaign_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;
  if campaign_row.status <> 'active' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_not_active';
  end if;
  new.campaign_id := campaign_id_value;

  if tg_table_name = 'generation_jobs' then
    select batch.campaign_id into batch_campaign_id
    from content_factory.generation_batches batch
    where batch.organization_id = new.organization_id
      and batch.id = new.batch_id;
    if batch_campaign_id is distinct from campaign_id_value then
      raise exception using
        errcode = '55000',
        message = 'generation_campaign_binding_invalid';
    end if;
  end if;
  return new;
end;
$$;

drop trigger if exists a_bind_paid_generation_campaign
  on content_factory.generation_batches;
create trigger a_bind_paid_generation_campaign
before insert on content_factory.generation_batches
for each row execute function
  content_factory_private.bind_paid_generation_campaign();

drop trigger if exists a_bind_paid_generation_campaign
  on content_factory.generation_jobs;
create trigger a_bind_paid_generation_campaign
before insert on content_factory.generation_jobs
for each row execute function
  content_factory_private.bind_paid_generation_campaign();

create or replace function content_factory_private.guard_paid_campaign_identity()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (
    old.mode = 'real' and old.allow_real_spend
    or new.mode = 'real' and new.allow_real_spend
  ) and new.campaign_id is distinct from old.campaign_id then
    raise exception using
      errcode = '55000',
      message = 'generation_spend_reservation_identity_immutable';
  end if;
  return new;
end;
$$;

drop trigger if exists a_guard_paid_campaign_identity
  on content_factory.generation_batches;
create trigger a_guard_paid_campaign_identity
before update of campaign_id on content_factory.generation_batches
for each row execute function
  content_factory_private.guard_paid_campaign_identity();

drop trigger if exists a_guard_paid_campaign_identity
  on content_factory.generation_jobs;
create trigger a_guard_paid_campaign_identity
before update of campaign_id on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_paid_campaign_identity();

create or replace function content_factory_private.reserve_generation_campaign_spend()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_policy content_factory.generation_spend_policies%rowtype;
  campaign_row content_factory.generation_campaigns%rowtype;
  campaign_policy content_factory.generation_campaign_spend_policies%rowtype;
  budget_day_value date;
  budget_month_value date;
  day_reserved_minor bigint;
  day_committed_minor bigint;
  month_reserved_minor bigint;
  month_committed_minor bigint;
begin
  if new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  if new.campaign_id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;

  -- This is deliberately the same lock used by the organization reservation
  -- trigger and both policy writers.  Organization and campaign decisions are
  -- therefore one serializable money decision, without a second lock order.
  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );

  select policy.* into organization_policy
  from content_factory.generation_spend_policies policy
  where policy.organization_id = new.organization_id
  for update;
  if organization_policy.organization_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;

  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = new.organization_id
    and campaign.id = new.campaign_id
  for update;
  if campaign_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;
  if campaign_row.status <> 'active' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_not_active';
  end if;

  select policy.* into campaign_policy
  from content_factory.generation_campaign_spend_policies policy
  where policy.organization_id = new.organization_id
    and policy.campaign_id = new.campaign_id
  for update;
  if campaign_policy.campaign_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_campaign_policy_missing';
  end if;
  if not campaign_policy.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_paused';
  end if;
  if new.estimated_cost_minor > campaign_policy.per_request_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_per_request_budget_exceeded';
  end if;

  budget_day_value := (
    clock_timestamp() at time zone organization_policy.timezone
  )::date;
  budget_month_value := date_trunc('month', budget_day_value)::date;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into day_reserved_minor, day_committed_minor
  from content_factory.generation_spend_ledger ledger
  join content_factory.generation_jobs job
    on job.organization_id = ledger.organization_id
   and job.id = ledger.generation_job_id
  where ledger.organization_id = new.organization_id
    and job.campaign_id = new.campaign_id
    and ledger.budget_day = budget_day_value;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into month_reserved_minor, month_committed_minor
  from content_factory.generation_spend_ledger ledger
  join content_factory.generation_jobs job
    on job.organization_id = ledger.organization_id
   and job.id = ledger.generation_job_id
  where ledger.organization_id = new.organization_id
    and job.campaign_id = new.campaign_id
    and ledger.budget_month = budget_month_value;

  if day_reserved_minor + day_committed_minor + new.estimated_cost_minor
       > campaign_policy.daily_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_daily_budget_exceeded';
  end if;
  if month_reserved_minor + month_committed_minor + new.estimated_cost_minor
       > campaign_policy.monthly_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_monthly_budget_exceeded';
  end if;

  new.input := jsonb_set(
    jsonb_set(
      new.input,
      '{campaign_id}',
      to_jsonb(new.campaign_id::text),
      true
    ),
    '{campaign_policy_version}',
    to_jsonb(campaign_policy.version),
    true
  );
  return new;
end;
$$;

-- The campaign guard is BEFORE INSERT.  It acquires the organization money
-- lock, checks campaign capacity and annotates immutable job input.  The
-- existing AFTER INSERT organization trigger then reuses the same xact lock
-- and appends the single authoritative reservation ledger event.
drop trigger if exists b_generation_campaign_spend_reservation
  on content_factory.generation_jobs;
create trigger b_generation_campaign_spend_reservation
before insert on content_factory.generation_jobs
for each row execute function
  content_factory_private.reserve_generation_campaign_spend();

create or replace function content_factory_private.guard_generation_campaign_spend_start()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  campaign_row content_factory.generation_campaigns%rowtype;
  campaign_policy content_factory.generation_campaign_spend_policies%rowtype;
  reservation_row content_factory.generation_spend_ledger%rowtype;
  day_reserved_minor bigint;
  day_committed_minor bigint;
  month_reserved_minor bigint;
  month_committed_minor bigint;
begin
  if old.status <> 'queued' or new.status <> 'starting'
     or new.mode <> 'real' or new.provider <> 'runway'
     or not new.allow_real_spend then
    return new;
  end if;
  if new.campaign_id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(new.organization_id::text),
    hashtext('generation_spend_budget')
  );

  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = new.organization_id
    and campaign.id = new.campaign_id
  for update;
  if campaign_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;
  if campaign_row.status <> 'active' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_not_active';
  end if;

  select policy.* into campaign_policy
  from content_factory.generation_campaign_spend_policies policy
  where policy.organization_id = new.organization_id
    and policy.campaign_id = new.campaign_id
  for update;
  if campaign_policy.campaign_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_campaign_policy_missing';
  end if;
  if not campaign_policy.paid_generation_enabled then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_paused';
  end if;
  if new.estimated_cost_minor > campaign_policy.per_request_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_per_request_budget_exceeded';
  end if;

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

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into day_reserved_minor, day_committed_minor
  from content_factory.generation_spend_ledger ledger
  join content_factory.generation_jobs job
    on job.organization_id = ledger.organization_id
   and job.id = ledger.generation_job_id
  where ledger.organization_id = new.organization_id
    and job.campaign_id = new.campaign_id
    and ledger.budget_day = reservation_row.budget_day;

  select
    coalesce(sum(ledger.reserved_delta_minor), 0)::bigint,
    coalesce(sum(ledger.committed_delta_minor), 0)::bigint
  into month_reserved_minor, month_committed_minor
  from content_factory.generation_spend_ledger ledger
  join content_factory.generation_jobs job
    on job.organization_id = ledger.organization_id
   and job.id = ledger.generation_job_id
  where ledger.organization_id = new.organization_id
    and job.campaign_id = new.campaign_id
    and ledger.budget_month = reservation_row.budget_month;

  if day_reserved_minor + day_committed_minor
       > campaign_policy.daily_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_daily_budget_exceeded';
  end if;
  if month_reserved_minor + month_committed_minor
       > campaign_policy.monthly_limit_minor then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_monthly_budget_exceeded';
  end if;
  return new;
end;
$$;

-- Alphabetically before c_generation_spend_start_guard from 202607170002;
-- both checks complete before the service-role claim can expose a Runway POST.
drop trigger if exists b_generation_campaign_spend_start_guard
  on content_factory.generation_jobs;
create trigger b_generation_campaign_spend_start_guard
before update of status, campaign_id, mode, provider, allow_real_spend,
  organization_id, estimated_cost_minor
on content_factory.generation_jobs
for each row execute function
  content_factory_private.guard_generation_campaign_spend_start();

create or replace function content_factory_private.generation_campaign_spend_overview(
  organization_id_value uuid
)
returns jsonb
language sql
security definer
stable
set search_path = ''
as $$
  with configuration as (
    select
      coalesce(organization_policy.timezone, 'UTC') as timezone,
      (now() at time zone coalesce(organization_policy.timezone, 'UTC'))::date
        as budget_day,
      date_trunc(
        'month',
        (now() at time zone coalesce(organization_policy.timezone, 'UTC'))::date
      )::date as budget_month
    from (select 1) singleton
    left join content_factory.generation_spend_policies organization_policy
      on organization_policy.organization_id = organization_id_value
  ),
  usage_by_campaign as (
    select
      job.campaign_id,
      coalesce(sum(ledger.reserved_delta_minor) filter (
        where ledger.budget_day = configuration.budget_day
      ), 0)::bigint as day_reserved_minor,
      coalesce(sum(ledger.committed_delta_minor) filter (
        where ledger.budget_day = configuration.budget_day
      ), 0)::bigint as day_committed_minor,
      coalesce(sum(ledger.reserved_delta_minor) filter (
        where ledger.budget_month = configuration.budget_month
      ), 0)::bigint as month_reserved_minor,
      coalesce(sum(ledger.committed_delta_minor) filter (
        where ledger.budget_month = configuration.budget_month
      ), 0)::bigint as month_committed_minor
    from configuration
    join content_factory.generation_spend_ledger ledger
      on ledger.organization_id = organization_id_value
    join content_factory.generation_jobs job
      on job.organization_id = ledger.organization_id
     and job.id = ledger.generation_job_id
    where job.campaign_id is not null
    group by job.campaign_id
  ),
  campaign_rows as (
    select
      campaign.id,
      campaign.name,
      campaign.kind,
      campaign.status,
      campaign.version as campaign_version,
      campaign.updated_at as campaign_updated_at,
      policy.paid_generation_enabled,
      policy.daily_limit_minor,
      policy.monthly_limit_minor,
      policy.per_request_limit_minor,
      policy.version as policy_version,
      policy.reason,
      policy.updated_at as policy_updated_at,
      coalesce(usage.day_reserved_minor, 0)::bigint as day_reserved_minor,
      coalesce(usage.day_committed_minor, 0)::bigint as day_committed_minor,
      coalesce(usage.month_reserved_minor, 0)::bigint as month_reserved_minor,
      coalesce(usage.month_committed_minor, 0)::bigint
        as month_committed_minor
    from content_factory.generation_campaigns campaign
    left join content_factory.generation_campaign_spend_policies policy
      on policy.organization_id = campaign.organization_id
     and policy.campaign_id = campaign.id
    left join usage_by_campaign usage on usage.campaign_id = campaign.id
    where campaign.organization_id = organization_id_value
      and campaign.status <> 'archived'
  )
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', campaign.id,
        'campaign_id', campaign.id,
        'name', campaign.name,
        'campaign_name', campaign.name,
        'kind', campaign.kind,
        'status', campaign.status,
        'enabled', campaign.status = 'active'
          and coalesce(campaign.paid_generation_enabled, false),
        'blocker_code', case
          when campaign.status <> 'active'
            then 'paid_generation_campaign_not_active'
          when campaign.policy_version is null
            then 'paid_generation_campaign_policy_missing'
          when not campaign.paid_generation_enabled
            then 'paid_generation_campaign_paused'
          when campaign.day_reserved_minor + campaign.day_committed_minor
                 >= campaign.daily_limit_minor
            then 'generation_campaign_daily_budget_exceeded'
          when campaign.month_reserved_minor + campaign.month_committed_minor
                 >= campaign.monthly_limit_minor
            then 'generation_campaign_monthly_budget_exceeded'
          else null
        end,
        'policy', jsonb_build_object(
          'paid_generation_enabled', coalesce(
            campaign.paid_generation_enabled, false
          ),
          'daily_limit_minor', coalesce(campaign.daily_limit_minor, 0),
          'monthly_limit_minor', coalesce(campaign.monthly_limit_minor, 0),
          'per_request_limit_minor', coalesce(
            campaign.per_request_limit_minor, 0
          ),
          'version', coalesce(campaign.policy_version, 0),
          'reason', coalesce(
            campaign.reason, 'paid_generation_campaign_policy_missing'
          ),
          'updated_at', campaign.policy_updated_at
        ),
        'usage', jsonb_build_object(
          'day', jsonb_build_object(
            'reserved_minor', greatest(campaign.day_reserved_minor, 0),
            'committed_minor', campaign.day_committed_minor,
            'remaining_minor', greatest(
              coalesce(campaign.daily_limit_minor, 0)
                - campaign.day_reserved_minor
                - campaign.day_committed_minor,
              0
            )
          ),
          'month', jsonb_build_object(
            'reserved_minor', greatest(campaign.month_reserved_minor, 0),
            'committed_minor', campaign.month_committed_minor,
            'remaining_minor', greatest(
              coalesce(campaign.monthly_limit_minor, 0)
                - campaign.month_reserved_minor
                - campaign.month_committed_minor,
              0
            )
          )
        ),
        -- Compatibility fields consumed by the first manager table.
        'reserved_minor', greatest(campaign.month_reserved_minor, 0),
        'committed_minor', campaign.month_committed_minor,
        'remaining_minor', least(
          greatest(
            coalesce(campaign.daily_limit_minor, 0)
              - campaign.day_reserved_minor
              - campaign.day_committed_minor,
            0
          ),
          greatest(
            coalesce(campaign.monthly_limit_minor, 0)
              - campaign.month_reserved_minor
              - campaign.month_committed_minor,
            0
          )
        ),
        'version', campaign.campaign_version,
        'updated_at', campaign.campaign_updated_at
      )
      order by
        case when campaign.kind = 'default' then 0 else 1 end,
        lower(campaign.name),
        campaign.id
    ),
    '[]'::jsonb
  )
  from campaign_rows campaign;
$$;

-- Preserve the deployed organization implementation and compose campaign
-- detail around it.  Existing RPCs and policy mutations call the original
-- name dynamically, so they automatically return the richer overview.
alter function content_factory_private.generation_spend_overview(uuid)
  rename to generation_spend_organization_overview;

create or replace function content_factory_private.generation_spend_overview(
  organization_id_value uuid
)
returns jsonb
language sql
security definer
stable
set search_path = ''
as $$
  select
    content_factory_private.generation_spend_organization_overview(
      organization_id_value
    ) || jsonb_build_object(
      'campaigns',
      content_factory_private.generation_campaign_spend_overview(
        organization_id_value
      )
    );
$$;

create or replace function public.creator_start_real_generation(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  campaign_id_value uuid;
  campaign_row content_factory.generation_campaigns%rowtype;
  result jsonb;
  job_id_value uuid;
  stored_campaign_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  if p_payload ? 'campaign_id' then
    campaign_id_value := content_factory_private.require_uuid(
      p_payload,
      'campaign_id'
    );
  else
    -- Compatibility for already deployed clients: omission is bound to the
    -- one immutable organization default, never to an unaccounted NULL.  The
    -- updated portal requires an explicit selector for every new real launch.
    select campaign.id into campaign_id_value
    from content_factory.generation_campaigns campaign
    where campaign.organization_id = organization_id
      and campaign.kind = 'default';
  end if;
  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = organization_id
    and campaign.id = campaign_id_value;
  if campaign_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'paid_generation_campaign_required';
  end if;
  if campaign_row.status <> 'active' then
    raise exception using
      errcode = '42501',
      message = 'paid_generation_campaign_not_active';
  end if;

  perform set_config(
    'content_factory.generation_campaign_id',
    campaign_id_value::text,
    true
  );

  if p_payload ->> 'model' = 'seedance2_fast' then
    result := content_factory_private.creator_start_seedance2_fast_8s(
      p_payload - 'campaign_id'
    );
  elsif p_payload ->> 'model' = 'gen4_turbo' then
    if p_payload ? 'audio'
       and p_payload -> 'audio' is distinct from 'false'::jsonb then
      raise exception using
        errcode = '42501',
        message = 'real_generation_spend_confirmation_required';
    end if;
    result := content_factory_private.creator_start_gen4_turbo_5s(
      p_payload - 'audio' - 'campaign_id'
    );
    result := jsonb_set(result, '{job,audio}', 'false'::jsonb, true);
    result := jsonb_set(result, '{job,estimated_credits}', '25'::jsonb, true);
  else
    raise exception using
      errcode = '42501',
      message = 'real_generation_spend_confirmation_required';
  end if;

  begin
    job_id_value := (result #>> '{job,id}')::uuid;
  exception when invalid_text_representation or null_value_not_allowed then
    raise exception using
      errcode = '55000',
      message = 'generation_campaign_binding_invalid';
  end;
  select job.campaign_id into stored_campaign_id
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value;
  -- The older private command hash cannot include the wrapper-only field.
  -- This check makes a replay with the same idempotency key but another
  -- campaign fail instead of misreporting or reattributing the paid job.
  if stored_campaign_id is distinct from campaign_id_value then
    raise exception using
      errcode = '23505',
      message = 'idempotency_key_conflict';
  end if;

  result := jsonb_set(
    result,
    '{job,campaign_id}',
    to_jsonb(campaign_id_value::text),
    true
  );
  result := jsonb_set(
    result,
    '{job,campaign_name}',
    to_jsonb(campaign_row.name),
    true
  );
  result := jsonb_set(
    result,
    '{batch,campaign_id}',
    to_jsonb(campaign_id_value::text),
    true
  );
  return result;
end;
$$;

create or replace function public.creator_create_generation_campaign(
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
  name_value text;
  enabled_value boolean;
  daily_limit_value bigint;
  monthly_limit_value bigint;
  per_request_limit_value bigint;
  reason_value text;
  request_payload jsonb;
  replay jsonb;
  organization_policy content_factory.generation_spend_policies%rowtype;
  campaign_row content_factory.generation_campaigns%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'name',
    'paid_generation_enabled', 'daily_limit_minor',
    'monthly_limit_minor', 'per_request_limit_minor', 'reason'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'name'
       and p_payload ? 'paid_generation_enabled'
       and p_payload ? 'daily_limit_minor'
       and p_payload ? 'monthly_limit_minor'
       and p_payload ? 'per_request_limit_minor'
       and p_payload ? 'reason'
       and p_payload ? 'idempotency_key'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin']
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  name_value := content_factory_private.require_text(
    p_payload, 'name', 2, 160
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 8, 500
  );
  if p_payload -> 'paid_generation_enabled'
       not in ('true'::jsonb, 'false'::jsonb)
     or jsonb_typeof(p_payload -> 'daily_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'daily_limit_minor', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'monthly_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'monthly_limit_minor', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'per_request_limit_minor') <> 'number'
     or coalesce(p_payload ->> 'per_request_limit_minor', '') !~ '^[0-9]+$'
     or reason_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end if;
  begin
    daily_limit_value := (p_payload ->> 'daily_limit_minor')::bigint;
    monthly_limit_value := (p_payload ->> 'monthly_limit_minor')::bigint;
    per_request_limit_value :=
      (p_payload ->> 'per_request_limit_minor')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end;
  enabled_value := (p_payload ->> 'paid_generation_enabled')::boolean;
  if daily_limit_value not between 1 and 1000000000000
     or monthly_limit_value not between 1 and 1000000000000
     or per_request_limit_value not between 1 and 1000000000000
     or per_request_limit_value > daily_limit_value
     or daily_limit_value > monthly_limit_value then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_generation_campaign',
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
  select policy.* into organization_policy
  from content_factory.generation_spend_policies policy
  where policy.organization_id = organization_id
  for update;
  if organization_policy.organization_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;
  if daily_limit_value > organization_policy.daily_limit_minor
     or monthly_limit_value > organization_policy.monthly_limit_minor
     or per_request_limit_value > organization_policy.per_request_limit_minor
  then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end if;
  if (
    select count(*)
    from content_factory.generation_campaigns campaign
    where campaign.organization_id = organization_id
      and campaign.status <> 'archived'
  ) >= 100 then
    raise exception using
      errcode = '54000',
      message = 'generation_campaign_quota_exceeded';
  end if;

  insert into content_factory.generation_campaigns (
    organization_id, name, kind, status, version, created_by, updated_by
  ) values (
    organization_id, btrim(name_value), 'managed', 'active', 1,
    user_id, user_id
  ) returning * into campaign_row;
  insert into content_factory.generation_campaign_spend_policies (
    organization_id, campaign_id, paid_generation_enabled,
    daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
    currency, version, reason, updated_by
  ) values (
    organization_id, campaign_row.id, enabled_value,
    daily_limit_value, monthly_limit_value, per_request_limit_value,
    'USD', 1, reason_value, user_id
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'generation_campaign_created',
    'generation_campaign',
    campaign_row.id::text,
    jsonb_build_object(
      'name', campaign_row.name,
      'paid_generation_enabled', enabled_value,
      'daily_limit_minor', daily_limit_value,
      'monthly_limit_minor', monthly_limit_value,
      'per_request_limit_minor', per_request_limit_value,
      'currency', 'USD',
      'reason', reason_value
    ),
    'generation-campaign-created:' || campaign_row.id::text
  );
  result := jsonb_build_object(
    'ok', true,
    'campaign', jsonb_build_object(
      'id', campaign_row.id,
      'name', campaign_row.name,
      'status', campaign_row.status,
      'version', campaign_row.version
    ),
    'overview', content_factory_private.generation_spend_overview(
      organization_id
    )
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_create_generation_campaign',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_update_generation_campaign_spend_policy(
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
  campaign_id_value uuid;
  idempotency_key_value text;
  expected_version_value bigint;
  enabled_value boolean;
  daily_limit_value bigint;
  monthly_limit_value bigint;
  per_request_limit_value bigint;
  reason_value text;
  request_payload jsonb;
  replay jsonb;
  organization_policy content_factory.generation_spend_policies%rowtype;
  campaign_row content_factory.generation_campaigns%rowtype;
  policy_row content_factory.generation_campaign_spend_policies%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'campaign_id', 'idempotency_key',
    'paid_generation_enabled', 'daily_limit_minor',
    'monthly_limit_minor', 'per_request_limit_minor',
    'expected_version', 'reason'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'campaign_id'
       and p_payload ? 'paid_generation_enabled'
       and p_payload ? 'daily_limit_minor'
       and p_payload ? 'monthly_limit_minor'
       and p_payload ? 'per_request_limit_minor'
       and p_payload ? 'expected_version'
       and p_payload ? 'reason'
       and p_payload ? 'idempotency_key'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    array['owner', 'admin']
  );
  campaign_id_value := content_factory_private.require_uuid(
    p_payload, 'campaign_id'
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  reason_value := content_factory_private.require_text(
    p_payload, 'reason', 8, 500
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
     or coalesce(p_payload ->> 'per_request_limit_minor', '') !~ '^[0-9]+$'
     or reason_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
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
      message = 'generation_campaign_policy_values_invalid';
  end;
  enabled_value := (p_payload ->> 'paid_generation_enabled')::boolean;
  if expected_version_value < 1
     or daily_limit_value not between 1 and 1000000000000
     or monthly_limit_value not between 1 and 1000000000000
     or per_request_limit_value not between 1 and 1000000000000
     or per_request_limit_value > daily_limit_value
     or daily_limit_value > monthly_limit_value then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_update_generation_campaign_spend_policy',
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
  select campaign.* into campaign_row
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = organization_id
    and campaign.id = campaign_id_value
    and campaign.status <> 'archived'
  for update;
  if campaign_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'generation_campaign_not_found';
  end if;
  select policy.* into organization_policy
  from content_factory.generation_spend_policies policy
  where policy.organization_id = organization_id
  for update;
  if organization_policy.organization_id is null then
    raise exception using
      errcode = '55000',
      message = 'paid_generation_policy_missing';
  end if;
  if daily_limit_value > organization_policy.daily_limit_minor
     or monthly_limit_value > organization_policy.monthly_limit_minor
     or per_request_limit_value > organization_policy.per_request_limit_minor
  then
    raise exception using
      errcode = '22023',
      message = 'generation_campaign_policy_values_invalid';
  end if;
  select policy.* into policy_row
  from content_factory.generation_campaign_spend_policies policy
  where policy.organization_id = organization_id
    and policy.campaign_id = campaign_id_value
  for update;
  if policy_row.campaign_id is null
     or policy_row.version <> expected_version_value then
    raise exception using
      errcode = '40001',
      message = 'generation_campaign_budget_policy_changed';
  end if;
  update content_factory.generation_campaign_spend_policies policy
  set paid_generation_enabled = enabled_value,
      daily_limit_minor = daily_limit_value,
      monthly_limit_minor = monthly_limit_value,
      per_request_limit_minor = per_request_limit_value,
      version = policy.version + 1,
      reason = reason_value,
      updated_by = user_id,
      updated_at = now()
  where policy.organization_id = organization_id
    and policy.campaign_id = campaign_id_value
  returning * into policy_row;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'generation_campaign_spend_policy_updated',
    'generation_campaign',
    campaign_id_value::text,
    jsonb_build_object(
      'paid_generation_enabled', policy_row.paid_generation_enabled,
      'daily_limit_minor', policy_row.daily_limit_minor,
      'monthly_limit_minor', policy_row.monthly_limit_minor,
      'per_request_limit_minor', policy_row.per_request_limit_minor,
      'currency', 'USD',
      'version', policy_row.version,
      'reason', policy_row.reason
    ),
    'generation-campaign-policy:' || campaign_id_value::text || ':' ||
      policy_row.version::text
  );
  result := content_factory_private.generation_spend_overview(organization_id);
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_update_generation_campaign_spend_policy',
    idempotency_key_value,
    request_payload,
    result
  );
end;
$$;

-- Keep campaign attribution in every authenticated status response.  The
-- Edge Function validates and returns these fields for the initial start and
-- all later polls, so a UI cannot silently detach a paid job from its budget.
create or replace function public.creator_real_generation_status(
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
  actor_role text;
  job_id_value uuid;
  job_row content_factory.generation_jobs%rowtype;
  campaign_name_value text;
  manager_scope boolean;
  reconciliation_required_value boolean;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'job_id']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'real_generation_status_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  manager_scope := actor_role in ('owner', 'admin', 'producer');
  job_id_value := content_factory_private.require_uuid(p_payload, 'job_id');

  select job.* into job_row
  from content_factory.generation_jobs job
  where job.organization_id = organization_id
    and job.id = job_id_value
    and job.mode = 'real'
    and job.provider = 'runway'
    and (
      manager_scope
      or job.requested_by = user_id
      or job.assigned_to = user_id
    );
  if job_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'real_generation_not_found';
  end if;
  if job_row.campaign_id is null then
    raise exception using
      errcode = '55000',
      message = 'generation_campaign_binding_invalid';
  end if;
  select campaign.name into campaign_name_value
  from content_factory.generation_campaigns campaign
  where campaign.organization_id = job_row.organization_id
    and campaign.id = job_row.campaign_id;
  if campaign_name_value is null then
    raise exception using
      errcode = '55000',
      message = 'generation_campaign_binding_invalid';
  end if;

  reconciliation_required_value :=
    content_factory_private.real_generation_reconciliation_unresolved(
      job_row.output
    );

  return jsonb_build_object(
    'ok', true,
    'job', jsonb_build_object(
      'id', job_row.id,
      'batch_id', job_row.batch_id,
      'campaign_id', job_row.campaign_id,
      'campaign_name', campaign_name_value,
      'status', job_row.status,
      'provider', job_row.provider,
      'provider_task_id', job_row.output ->> 'provider_task_id',
      'model', job_row.input ->> 'model',
      'duration_seconds', (job_row.input ->> 'duration_seconds')::integer,
      'audio', coalesce((job_row.input ->> 'audio')::boolean, false),
      'ratio', job_row.input ->> 'ratio',
      'estimated_cost_minor', job_row.estimated_cost_minor,
      'estimated_credits',
        (job_row.input #>> '{billing,estimated_credits}')::bigint,
      'actual_cost_minor', job_row.actual_cost_minor,
      'output_object_name', job_row.input ->> 'output_object_name',
      'output_media_id', job_row.output ->> 'output_media_id',
      'failure_code', job_row.output ->> 'failure_code',
      'submission_state', job_row.output ->> 'submission_state',
      'reconciliation_required', reconciliation_required_value,
      'reconciliation_incident_id',
        job_row.output ->> 'reconciliation_incident_id',
      'reconciliation_required_at',
        job_row.output ->> 'reconciliation_required_at',
      'reconciliation_reason_code',
        job_row.output ->> 'reconciliation_reason_code',
      'reconciliation_resolution',
        job_row.output ->> 'reconciliation_resolution',
      'can_reconcile',
        actor_role in ('owner', 'admin')
        and reconciliation_required_value
        and job_row.status = 'starting',
      'updated_at', job_row.updated_at
    )
  );
end;
$$;

revoke all on function content_factory_private.initialize_generation_campaign()
  from public, anon, authenticated;
revoke all on function content_factory_private.initialize_default_campaign_policy()
  from public, anon, authenticated;
revoke all on function content_factory_private.bind_paid_generation_campaign()
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_paid_campaign_identity()
  from public, anon, authenticated;
revoke all on function content_factory_private.reserve_generation_campaign_spend()
  from public, anon, authenticated;
revoke all on function content_factory_private.guard_generation_campaign_spend_start()
  from public, anon, authenticated;
revoke all on function content_factory_private.generation_campaign_spend_overview(uuid)
  from public, anon, authenticated;
revoke all on function content_factory_private.generation_spend_organization_overview(uuid)
  from public, anon, authenticated;
revoke all on function content_factory_private.generation_spend_overview(uuid)
  from public, anon, authenticated;

revoke all on function public.creator_start_real_generation(jsonb)
  from public, anon;
grant execute on function public.creator_start_real_generation(jsonb)
  to authenticated;
revoke all on function public.creator_real_generation_status(jsonb)
  from public, anon;
grant execute on function public.creator_real_generation_status(jsonb)
  to authenticated;
revoke all on function public.creator_create_generation_campaign(jsonb)
  from public, anon;
grant execute on function public.creator_create_generation_campaign(jsonb)
  to authenticated;
revoke all on function public.creator_update_generation_campaign_spend_policy(jsonb)
  from public, anon;
grant execute on function public.creator_update_generation_campaign_spend_policy(jsonb)
  to authenticated;

commit;
