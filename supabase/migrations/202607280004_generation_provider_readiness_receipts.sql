begin;

-- Provider readiness is free to check but used to live only in one browser
-- tab.  Persist a bounded, append-only receipt containing safe booleans only:
-- never the provider key, balance, quota counters or raw provider response.
create table if not exists
  content_factory.generation_provider_readiness_receipts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    provider text not null check (provider = 'runway'),
    model text not null check (
      model in ('gen4_turbo', 'seedance2_fast', 'seedream5_lite')
    ),
    ready boolean not null,
    estimated_credits integer not null,
    balance_sufficient boolean not null,
    model_available boolean not null,
    daily_quota_available boolean not null,
    failure_code text check (
      failure_code is null
      or failure_code in (
        'provider_configuration_error',
        'provider_authentication_failed',
        'provider_credits_unavailable',
        'provider_rate_limited',
        'provider_request_rejected',
        'provider_request_failed',
        'provider_response_invalid'
      )
    ),
    learning_gate_version text not null check (
      learning_gate_version ~
        '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]v[0-9]+$'
    ),
    checked_by uuid not null,
    checked_at timestamptz not null,
    expires_at timestamptz not null,
    receipt_hash text not null check (
      receipt_hash ~ '^[0-9a-f]{64}$'
    ),
    foreign key (organization_id, checked_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      estimated_credits = case model
        when 'gen4_turbo' then 25
        when 'seedance2_fast' then 232
        when 'seedream5_lite' then 4
      end
    ),
    check (
      ready = (
        balance_sufficient
        and model_available
        and daily_quota_available
      )
    ),
    check (
      (ready and failure_code is null)
      or (not ready and failure_code is not null)
    ),
    check (expires_at = checked_at + interval '15 minutes'),
    unique (organization_id, receipt_hash)
  );

create index if not exists
  generation_provider_readiness_receipts_latest_idx
  on content_factory.generation_provider_readiness_receipts (
    organization_id,
    provider,
    model,
    checked_at desc,
    id desc
  );

alter table content_factory.generation_provider_readiness_receipts
  enable row level security;
revoke all on content_factory.generation_provider_readiness_receipts
  from public, anon, authenticated;
grant all on content_factory.generation_provider_readiness_receipts
  to service_role;

create or replace function
  content_factory_private
    .guard_generation_provider_readiness_receipt_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_provider_readiness_receipt_append_only';
end;
$$;

drop trigger if exists generation_provider_readiness_receipt_append_only
  on content_factory.generation_provider_readiness_receipts;
create trigger generation_provider_readiness_receipt_append_only
before update or delete
  on content_factory.generation_provider_readiness_receipts
for each row execute function
  content_factory_private
    .guard_generation_provider_readiness_receipt_append_only();

revoke all on function
  content_factory_private
    .guard_generation_provider_readiness_receipt_append_only()
  from public, anon, authenticated, service_role;

-- Only the trusted Edge function can create a receipt.  It passes the
-- authenticated member identity explicitly because the service-role client
-- intentionally has no end-user auth.uid().
create or replace function
  public.system_record_generation_provider_readiness(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  checked_by_value uuid;
  provider_value text;
  model_value text;
  ready_value boolean;
  estimated_credits_value integer;
  balance_sufficient_value boolean;
  model_available_value boolean;
  daily_quota_available_value boolean;
  failure_code_value text;
  learning_gate_version_value text;
  checked_at_value timestamptz;
  expires_at_value timestamptz;
  receipt_body jsonb;
  receipt_hash_value text;
  receipt_id uuid;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id',
    'checked_by',
    'provider',
    'model',
    'ready',
    'estimated_credits',
    'balance_sufficient',
    'model_available',
    'daily_quota_available',
    'failure_code',
    'learning_gate_version'
  ]::text[] <> '{}'::jsonb
     or not (
       p_payload ? 'organization_id'
       and p_payload ? 'checked_by'
       and p_payload ? 'provider'
       and p_payload ? 'model'
       and p_payload ? 'ready'
       and p_payload ? 'estimated_credits'
       and p_payload ? 'balance_sufficient'
       and p_payload ? 'model_available'
       and p_payload ? 'daily_quota_available'
       and p_payload ? 'failure_code'
       and p_payload ? 'learning_gate_version'
     )
     or jsonb_typeof(p_payload -> 'ready') <> 'boolean'
     or jsonb_typeof(p_payload -> 'estimated_credits') <> 'number'
     or coalesce(p_payload ->> 'estimated_credits', '') !~ '^[0-9]+$'
     or jsonb_typeof(p_payload -> 'balance_sufficient') <> 'boolean'
     or jsonb_typeof(p_payload -> 'model_available') <> 'boolean'
     or jsonb_typeof(p_payload -> 'daily_quota_available') <> 'boolean'
     or jsonb_typeof(p_payload -> 'failure_code')
          not in ('string', 'null') then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end if;

  organization_id :=
    content_factory_private.require_uuid(p_payload, 'organization_id');
  checked_by_value :=
    content_factory_private.require_uuid(p_payload, 'checked_by');
  provider_value :=
    lower(btrim(coalesce(p_payload ->> 'provider', '')));
  model_value :=
    lower(btrim(coalesce(p_payload ->> 'model', '')));
  learning_gate_version_value :=
    btrim(coalesce(p_payload ->> 'learning_gate_version', ''));
  ready_value := (p_payload ->> 'ready')::boolean;
  balance_sufficient_value :=
    (p_payload ->> 'balance_sufficient')::boolean;
  model_available_value :=
    (p_payload ->> 'model_available')::boolean;
  daily_quota_available_value :=
    (p_payload ->> 'daily_quota_available')::boolean;
  begin
    estimated_credits_value :=
      (p_payload ->> 'estimated_credits')::integer;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end;
  failure_code_value := nullif(
    btrim(coalesce(p_payload ->> 'failure_code', '')),
    ''
  );

  if provider_value <> 'runway'
     or model_value not in (
       'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
     )
     or (
       model_value = 'gen4_turbo'
       and estimated_credits_value <> 25
     )
     or (
       model_value = 'seedance2_fast'
       and estimated_credits_value <> 232
     )
     or (
       model_value = 'seedream5_lite'
       and estimated_credits_value <> 4
     )
     or learning_gate_version_value !~
       '^[0-9]{4}-[0-9]{2}-[0-9]{2}[.]v[0-9]+$'
     or ready_value is distinct from (
       balance_sufficient_value
       and model_available_value
       and daily_quota_available_value
     )
     or (
       ready_value
       and failure_code_value is not null
     )
     or (
       not ready_value
       and failure_code_value not in (
         'provider_configuration_error',
         'provider_authentication_failed',
         'provider_credits_unavailable',
         'provider_rate_limited',
         'provider_request_rejected',
         'provider_request_failed',
         'provider_response_invalid'
       )
     )
     or not exists (
       select 1
       from content_factory.memberships membership
       where membership.organization_id = organization_id
         and membership.profile_id = checked_by_value
         and membership.status = 'active'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_provider_readiness_receipt_invalid';
  end if;

  checked_at_value := clock_timestamp();
  expires_at_value := checked_at_value + interval '15 minutes';
  receipt_body := jsonb_build_object(
    'version', 'generation-provider-readiness-receipt-v1',
    'organization_id', organization_id,
    'provider', provider_value,
    'model', model_value,
    'ready', ready_value,
    'estimated_credits', estimated_credits_value,
    'balance_sufficient', balance_sufficient_value,
    'model_available', model_available_value,
    'daily_quota_available', daily_quota_available_value,
    'failure_code', failure_code_value,
    'learning_gate_version', learning_gate_version_value,
    'checked_at', checked_at_value,
    'expires_at', expires_at_value
  );
  receipt_hash_value :=
    content_factory_private.json_hash(receipt_body);

  insert into content_factory.generation_provider_readiness_receipts (
    organization_id,
    provider,
    model,
    ready,
    estimated_credits,
    balance_sufficient,
    model_available,
    daily_quota_available,
    failure_code,
    learning_gate_version,
    checked_by,
    checked_at,
    expires_at,
    receipt_hash
  ) values (
    organization_id,
    provider_value,
    model_value,
    ready_value,
    estimated_credits_value,
    balance_sufficient_value,
    model_available_value,
    daily_quota_available_value,
    failure_code_value,
    learning_gate_version_value,
    checked_by_value,
    checked_at_value,
    expires_at_value,
    receipt_hash_value
  )
  returning id into receipt_id;

  return receipt_body || jsonb_build_object(
    'receipt_id', receipt_id,
    'receipt_hash', receipt_hash_value,
    'status', case when ready_value then 'ready' else 'blocked' end,
    'fresh', true
  );
end;
$$;

revoke all on function
  public.system_record_generation_provider_readiness(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_record_generation_provider_readiness(jsonb)
  to service_role;

-- Return one bounded, public-safe latest receipt per production SKU.  The
-- browser can restore informational readiness after reload, but the paid path
-- still performs a new provider GET immediately before every provider POST.
create or replace function
  content_factory_private.generation_provider_readiness(
    p_organization_id uuid,
    p_evaluated_at timestamptz default now()
  )
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with models(model, estimated_credits, position) as (
    values
      ('seedream5_lite'::text, 4, 1),
      ('gen4_turbo'::text, 25, 2),
      ('seedance2_fast'::text, 232, 3)
  ),
  latest as (
    select
      model.model,
      model.estimated_credits,
      model.position,
      receipt.id as receipt_id,
      receipt.ready,
      receipt.balance_sufficient,
      receipt.model_available,
      receipt.daily_quota_available,
      receipt.failure_code,
      receipt.learning_gate_version,
      receipt.checked_at,
      receipt.expires_at,
      receipt.receipt_hash
    from models model
    left join lateral (
      select candidate.*
      from content_factory.generation_provider_readiness_receipts candidate
      where candidate.organization_id = p_organization_id
        and candidate.provider = 'runway'
        and candidate.model = model.model
      order by candidate.checked_at desc, candidate.id desc
      limit 1
    ) receipt on true
  )
  select coalesce(
    jsonb_agg(
      jsonb_strip_nulls(jsonb_build_object(
        'provider', 'runway',
        'model', model,
        'receipt_version',
          'generation-provider-readiness-receipt-v1',
        'status', case
          when receipt_id is null then 'unknown'
          when expires_at <= p_evaluated_at then 'stale'
          when ready then 'ready'
          else 'blocked'
        end,
        'ready', coalesce(
          ready and expires_at > p_evaluated_at,
          false
        ),
        'fresh', coalesce(expires_at > p_evaluated_at, false),
        'estimated_credits', estimated_credits,
        'balance_sufficient', balance_sufficient,
        'model_available', model_available,
        'daily_quota_available', daily_quota_available,
        'failure_code', failure_code,
        'reason_code', case
          when receipt_id is null then 'provider_readiness_receipt_missing'
          when expires_at <= p_evaluated_at
            then 'provider_readiness_receipt_stale'
          when ready then 'provider_ready'
          else failure_code
        end,
        'learning_gate_version', learning_gate_version,
        'checked_at', checked_at,
        'expires_at', expires_at,
        'receipt_id', receipt_id,
        'receipt_hash', receipt_hash
      ))
      order by position
    ),
    '[]'::jsonb
  )
  from latest;
$$;

revoke all on function
  content_factory_private.generation_provider_readiness(uuid, timestamptz)
  from public, anon, authenticated, service_role;

-- Add receipts to the already membership-scoped spend overview so opening the
-- generation page needs no extra RPC and no provider call merely to restore
-- the latest safe state.
alter function public.creator_generation_spend_overview(jsonb)
  set schema content_factory_private;
alter function
  content_factory_private.creator_generation_spend_overview(jsonb)
  rename to creator_generation_spend_overview_pre_provider_readiness_v1;

revoke all on function
  content_factory_private
    .creator_generation_spend_overview_pre_provider_readiness_v1(jsonb)
  from public, anon, authenticated, service_role;

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
  overview_value jsonb;
  organization_id uuid;
begin
  overview_value := content_factory_private
    .creator_generation_spend_overview_pre_provider_readiness_v1(p_payload);
  organization_id :=
    content_factory_private.require_uuid(
      overview_value,
      'organization_id'
    );
  return overview_value || jsonb_build_object(
    'provider_readiness_version',
      'generation-provider-readiness-v1',
    'provider_readiness_evaluated_at', now(),
    'provider_readiness',
      content_factory_private.generation_provider_readiness(
        organization_id,
        now()
      )
  );
end;
$$;

revoke all on function public.creator_generation_spend_overview(jsonb)
  from public, anon;
grant execute on function public.creator_generation_spend_overview(jsonb)
  to authenticated;

notify pgrst, 'reload schema';

commit;
