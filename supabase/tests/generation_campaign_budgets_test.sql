begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.create_campaign_job(
  p_ordinal integer,
  p_campaign_id uuid
)
returns uuid
language plpgsql
set search_path = ''
as $fixture$
declare
  organization_id_value constant uuid :=
    'e1000000-0000-4000-8000-000000000001';
  owner_id_value constant uuid :=
    'e1100000-0000-4000-8000-000000000001';
  product_id_value constant uuid :=
    'e1200000-0000-4000-8000-000000000001';
  batch_id_value uuid := (
    'e2000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  job_id_value uuid := (
    'e3000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  key_suffix text := lpad(p_ordinal::text, 4, '0');
begin
  if p_ordinal not between 1 and 9999 then
    raise exception using
      errcode = '22023', message = 'campaign_budget_fixture_invalid';
  end if;

  perform set_config(
    'content_factory.generation_campaign_id',
    coalesce(p_campaign_id::text, ''),
    true
  );

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key,
    provider, model, duration_seconds, audio,
    estimated_cost_minor, estimated_credits, currency
  ) values (
    batch_id_value,
    organization_id_value,
    product_id_value,
    owner_id_value,
    'Campaign budget batch ' || key_suffix,
    'real', true, 'queued', 1, 0,
    jsonb_build_object(
      'job_id', job_id_value,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'audio', false,
      'format', '9:16',
      'ratio', '720:1280',
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    encode(
      extensions.digest('campaign-budget-batch:' || key_suffix, 'sha256'),
      'hex'
    ),
    'campaign-budget-batch-' || key_suffix,
    'runway', 'gen4_turbo', 5, false, 25, 25, 'USD'
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key
  ) values (
    job_id_value,
    organization_id_value,
    product_id_value,
    batch_id_value,
    1,
    owner_id_value,
    owner_id_value,
    'real', 'runway', true, 25, 0, 'queued',
    jsonb_build_object(
      'sku', 'CAMPAIGN-BUDGET-SKU',
      'product_name', 'Campaign budget product',
      'prompt_text', 'A safe five second product demonstration.',
      'format', '9:16',
      'ratio', '720:1280',
      'audio', false,
      'input_object_name',
        organization_id_value::text || '/' || owner_id_value::text ||
          '/uploads/campaign-budget-source.webp',
      'output_object_name',
        organization_id_value::text || '/' || owner_id_value::text ||
          '/generated/' || job_id_value::text || '.mp4',
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', 'wildberries',
      'destination_ref', 'wb-campaign-budget-' || key_suffix,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    '{}'::jsonb,
    encode(
      extensions.digest('campaign-budget-job:' || key_suffix, 'sha256'),
      'hex'
    ),
    'campaign-budget-job-' || key_suffix
  );

  perform set_config('content_factory.generation_campaign_id', '', true);
  return job_id_value;
end;
$fixture$;

create or replace function pg_temp.seed_historical_campaign_commit(
  p_ordinal integer,
  p_campaign_id uuid
)
returns uuid
language plpgsql
set search_path = ''
as $fixture$
declare
  organization_id_value constant uuid :=
    'e1000000-0000-4000-8000-000000000001';
  owner_id_value constant uuid :=
    'e1100000-0000-4000-8000-000000000001';
  product_id_value constant uuid :=
    'e1200000-0000-4000-8000-000000000001';
  batch_id_value uuid := (
    'e4000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  job_id_value uuid := (
    'e5000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  key_suffix text := lpad(p_ordinal::text, 4, '0');
  current_day_value date :=
    (clock_timestamp() at time zone 'Europe/Moscow')::date;
  current_month_value date := date_trunc(
    'month',
    (clock_timestamp() at time zone 'Europe/Moscow')::date
  )::date;
  historical_day_value date;
begin
  historical_day_value := case
    when current_day_value > current_month_value then current_month_value
    else current_day_value + 1
  end;

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key,
    provider, model, duration_seconds, audio,
    estimated_cost_minor, estimated_credits, currency, campaign_id
  ) values (
    batch_id_value,
    organization_id_value,
    product_id_value,
    owner_id_value,
    'Historical campaign accounting ' || key_suffix,
    'mock', false, 'mock_ready', 1, 1,
    '{}'::jsonb,
    encode(
      extensions.digest('campaign-history-batch:' || key_suffix, 'sha256'),
      'hex'
    ),
    'campaign-history-batch-' || key_suffix,
    'mock', 'mock', 0, false, 0, 0, 'USD', p_campaign_id
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key, campaign_id
  ) values (
    job_id_value,
    organization_id_value,
    product_id_value,
    batch_id_value,
    1,
    owner_id_value,
    owner_id_value,
    'mock', 'mock', false, 0, 0, 'mock_ready',
    '{}'::jsonb,
    '{}'::jsonb,
    encode(
      extensions.digest('campaign-history-job:' || key_suffix, 'sha256'),
      'hex'
    ),
    'campaign-history-job-' || key_suffix,
    p_campaign_id
  );

  insert into content_factory.generation_spend_ledger (
    organization_id, generation_job_id, event_type,
    estimated_cost_minor, actual_cost_minor,
    reserved_delta_minor, committed_delta_minor, currency,
    budget_day, budget_month, policy_version, reason_code, metadata
  )
  select
    organization_id_value,
    job_id_value,
    event.event_type,
    25,
    event.actual_cost_minor,
    event.reserved_delta_minor,
    event.committed_delta_minor,
    'USD',
    historical_day_value,
    current_month_value,
    1,
    event.reason_code,
    jsonb_build_object('fixture', 'historical_campaign_commit')
  from (values
    ('reserved', 0::bigint, 25::bigint, 0::bigint, 'historical_reserved'),
    ('settled', 25::bigint, -25::bigint, 25::bigint, 'historical_settled')
  ) as event(
    event_type, actual_cost_minor, reserved_delta_minor,
    committed_delta_minor, reason_code
  );

  return job_id_value;
end;
$fixture$;

select plan(54);

select has_table(
  'content_factory', 'generation_campaigns',
  'generation campaigns are a durable accounting dimension'
);
select has_table(
  'content_factory', 'generation_campaign_spend_policies',
  'each campaign has its own guarded spend policy'
);
select has_trigger(
  'content_factory', 'organizations', 'initialize_generation_campaign',
  'new organizations receive a durable default campaign'
);
select has_trigger(
  'content_factory', 'generation_jobs',
  'b_generation_campaign_spend_reservation',
  'campaign capacity is checked before the authoritative reservation append'
);
select has_trigger(
  'content_factory', 'generation_jobs',
  'b_generation_campaign_spend_start_guard',
  'campaign capacity is rechecked before provider claim'
);
select has_trigger(
  'content_factory', 'generation_batches', 'a_bind_paid_generation_campaign',
  'paid batches are bound to a campaign before insertion'
);
select has_trigger(
  'content_factory', 'generation_jobs', 'a_bind_paid_generation_campaign',
  'paid jobs are bound to their batch campaign before insertion'
);
select has_trigger(
  'content_factory', 'generation_batches', 'a_guard_paid_campaign_identity',
  'paid batch campaign identity is immutable'
);
select has_trigger(
  'content_factory', 'generation_jobs', 'a_guard_paid_campaign_identity',
  'paid job campaign identity is immutable'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_create_generation_campaign(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_create_generation_campaign(jsonb)',
    'execute'
  ),
  'only authenticated sessions reach the campaign creation RPC'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_update_generation_campaign_spend_policy(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_update_generation_campaign_spend_policy(jsonb)',
    'execute'
  ),
  'only authenticated sessions reach the campaign policy RPC'
);
select ok(
  not has_table_privilege(
    'authenticated', 'content_factory.generation_campaigns', 'select'
  ) and not has_table_privilege(
    'authenticated',
    'content_factory.generation_campaign_spend_policies',
    'select'
  ),
  'browser roles cannot bypass campaign RPCs through direct table reads'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select
  fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    'e1100000-0000-4000-8000-000000000001',
    'campaign-owner@example.test',
    'Campaign Owner'
  ),
  (
    'e1100000-0000-4000-8000-000000000002',
    'campaign-operator@example.test',
    'Campaign Operator'
  )
) as fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'e1000000-0000-4000-8000-000000000001',
  'Campaign Budget Test',
  'campaign-budget-test',
  'active'
);

select is(
  (
    select count(*)::text
    from content_factory.generation_campaigns
    where organization_id = 'e1000000-0000-4000-8000-000000000001'
      and kind = 'default'
      and status = 'active'
  ),
  '1',
  'organization creation backfills exactly one active default campaign'
);
select is(
  (
    select count(*)::text
    from content_factory.generation_campaign_spend_policies
    where organization_id = 'e1000000-0000-4000-8000-000000000001'
  ),
  '0',
  'default campaign remains fail-closed until organization policy exists'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    'e1000000-0000-4000-8000-000000000001',
    'e1100000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'e1000000-0000-4000-8000-000000000001',
    'e1100000-0000-4000-8000-000000000002',
    'operator', 'active'
  );

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  'e1200000-0000-4000-8000-000000000001',
  'e1000000-0000-4000-8000-000000000001',
  'CAMPAIGN-BUDGET-SKU',
  'Campaign budget product',
  'active',
  'e1100000-0000-4000-8000-000000000001'
);

create temporary table campaign_test_context (
  name text primary key,
  payload jsonb,
  campaign_id uuid,
  job_id uuid
) on commit drop;
grant select, insert, update on campaign_test_context to authenticated;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'e1100000-0000-4000-8000-000000000001',
    true
  );
end;
$$;
set local role authenticated;

insert into campaign_test_context (name, payload)
values (
  'organization_policy',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 500,
    'monthly_limit_minor', 1000,
    'per_request_limit_minor', 232,
    'timezone', 'Europe/Moscow',
    'reason', 'Enable a roomy organization envelope for campaign regression.',
    'expected_version', 0,
    'idempotency_key', 'campaign-org-policy-create-0001'
  ))
);
select is(
  (
    select payload #>> '{policy,version}'
    from campaign_test_context where name = 'organization_policy'
  ),
  '1',
  'owner can create the organization envelope required by campaign policies'
);

reset role;
select is(
  (
    select
      paid_generation_enabled::text || ':' ||
      daily_limit_minor::text || ':' || monthly_limit_minor::text || ':' ||
      policy.per_request_limit_minor::text || ':' || policy.version::text
    from content_factory.generation_campaign_spend_policies policy
    join content_factory.generation_campaigns campaign
      on campaign.organization_id = policy.organization_id
     and campaign.id = policy.campaign_id
    where campaign.organization_id =
      'e1000000-0000-4000-8000-000000000001'
      and campaign.kind = 'default'
  ),
  'true:500:1000:232:1',
  'the default campaign policy is backfilled from the organization envelope'
);

set local role authenticated;
insert into campaign_test_context (name, payload, campaign_id)
select 'aggregate_a', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Aggregate campaign A',
    'paid_generation_enabled', true,
    'daily_limit_minor', 100,
    'monthly_limit_minor', 200,
    'per_request_limit_minor', 25,
    'reason', 'First campaign used to verify organization aggregation.',
    'idempotency_key', 'campaign-create-aggregate-a-0001'
  )) as response
) command;
insert into campaign_test_context (name, payload, campaign_id)
select 'aggregate_b', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Aggregate campaign B',
    'paid_generation_enabled', true,
    'daily_limit_minor', 100,
    'monthly_limit_minor', 200,
    'per_request_limit_minor', 25,
    'reason', 'Second campaign used to verify organization aggregation.',
    'idempotency_key', 'campaign-create-aggregate-b-0001'
  )) as response
) command;
insert into campaign_test_context (name, payload, campaign_id)
select 'lifecycle', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Lifecycle campaign',
    'paid_generation_enabled', true,
    'daily_limit_minor', 25,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'reason', 'Verify release restores and settlement consumes capacity.',
    'idempotency_key', 'campaign-create-lifecycle-0001'
  )) as response
) command;
insert into campaign_test_context (name, payload, campaign_id)
select 'per_request', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Per request campaign',
    'paid_generation_enabled', true,
    'daily_limit_minor', 100,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 24,
    'reason', 'Verify a campaign can reject while organization still allows.',
    'idempotency_key', 'campaign-create-per-request-0001'
  )) as response
) command;
insert into campaign_test_context (name, payload, campaign_id)
select 'monthly', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Monthly campaign',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 50,
    'per_request_limit_minor', 25,
    'reason', 'Verify calendar month capacity independently of current day.',
    'idempotency_key', 'campaign-create-monthly-0001'
  )) as response
) command;
insert into campaign_test_context (name, payload, campaign_id)
select 'paused', response, (response #>> '{campaign,id}')::uuid
from (
  select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Paused campaign',
    'paid_generation_enabled', false,
    'daily_limit_minor', 100,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'reason', 'Verify campaign pause fails closed before any paid provider work.',
    'idempotency_key', 'campaign-create-paused-0001'
  )) as response
) command;

select ok(
  (
    select campaign_id is not null
    from campaign_test_context where name = 'aggregate_a'
  ),
  'owner creates a named campaign and receives its durable identity'
);
reset role;
select is(
  (
    select
      policy.paid_generation_enabled::text || ':' ||
      policy.daily_limit_minor::text || ':' ||
      policy.monthly_limit_minor::text || ':' ||
      policy.per_request_limit_minor::text || ':' || policy.version::text
    from content_factory.generation_campaign_spend_policies policy
    where policy.campaign_id = (
      select campaign_id from campaign_test_context where name = 'aggregate_a'
    )
  ),
  'true:100:200:25:1',
  'campaign creation persists the owner-approved policy atomically'
);

insert into content_factory.generation_campaigns (
  id, organization_id, name, kind, status, created_by, updated_by
) values (
  'e6000000-0000-4000-8000-000000000001',
  'e1000000-0000-4000-8000-000000000001',
  'Missing policy campaign',
  'managed',
  'active',
  'e1100000-0000-4000-8000-000000000001',
  'e1100000-0000-4000-8000-000000000001'
);
insert into campaign_test_context (name, campaign_id)
values ('missing_policy', 'e6000000-0000-4000-8000-000000000001');

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'e1100000-0000-4000-8000-000000000002',
    true
  );
end;
$$;
set local role authenticated;
select throws_ok(
  $$select public.creator_create_generation_campaign(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001',
    'name', 'Operator denied campaign',
    'paid_generation_enabled', true,
    'daily_limit_minor', 25,
    'monthly_limit_minor', 25,
    'per_request_limit_minor', 25,
    'reason', 'Operators must not allocate campaign money.',
    'idempotency_key', 'campaign-operator-create-denied-0001'
  ))$$,
  '42501',
  'role_not_allowed',
  'operator cannot create a campaign policy'
);
select throws_ok(
  $$select public.creator_update_generation_campaign_spend_policy(
    jsonb_build_object(
      'organization_id', 'e1000000-0000-4000-8000-000000000001',
      'campaign_id', (
        select campaign_id from campaign_test_context where name = 'aggregate_a'
      ),
      'paid_generation_enabled', true,
      'daily_limit_minor', 100,
      'monthly_limit_minor', 200,
      'per_request_limit_minor', 25,
      'expected_version', 1,
      'reason', 'Operators must not mutate campaign money.',
      'idempotency_key', 'campaign-operator-update-denied-0001'
    )
  )$$,
  '42501',
  'role_not_allowed',
  'operator cannot update a campaign policy'
);

reset role;
do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'e1100000-0000-4000-8000-000000000001',
    true
  );
end;
$$;
set local role authenticated;
select lives_ok(
  $$select public.creator_update_generation_campaign_spend_policy(
    jsonb_build_object(
      'organization_id', 'e1000000-0000-4000-8000-000000000001',
      'campaign_id', (
        select campaign_id from campaign_test_context where name = 'aggregate_a'
      ),
      'paid_generation_enabled', true,
      'daily_limit_minor', 100,
      'monthly_limit_minor', 200,
      'per_request_limit_minor', 25,
      'expected_version', 1,
      'reason', 'Owner confirms the aggregate campaign budget.',
      'idempotency_key', 'campaign-owner-update-aggregate-a-0001'
    )
  )$$,
  'owner can update a campaign policy with the current version'
);
reset role;
select is(
  (
    select version::text
    from content_factory.generation_campaign_spend_policies
    where campaign_id = (
      select campaign_id from campaign_test_context where name = 'aggregate_a'
    )
  ),
  '2',
  'successful campaign policy mutation increments its CAS version'
);
set local role authenticated;
select throws_ok(
  $$select public.creator_update_generation_campaign_spend_policy(
    jsonb_build_object(
      'organization_id', 'e1000000-0000-4000-8000-000000000001',
      'campaign_id', (
        select campaign_id from campaign_test_context where name = 'aggregate_a'
      ),
      'paid_generation_enabled', true,
      'daily_limit_minor', 100,
      'monthly_limit_minor', 200,
      'per_request_limit_minor', 25,
      'expected_version', 1,
      'reason', 'A stale campaign policy must never overwrite current limits.',
      'idempotency_key', 'campaign-owner-stale-aggregate-a-0001'
    )
  )$$,
  '40001',
  'generation_campaign_budget_policy_changed',
  'stale campaign expected_version fails closed'
);
reset role;

select lives_ok(
  $$select pg_temp.create_campaign_job(
    1,
    (select campaign_id from campaign_test_context where name = 'aggregate_a')
  )$$,
  'first campaign reserves against both campaign and organization envelopes'
);
select lives_ok(
  $$select pg_temp.create_campaign_job(
    2,
    (select campaign_id from campaign_test_context where name = 'aggregate_b')
  )$$,
  'second campaign reserves independently inside the same organization'
);
select is(
  (
    select count(*)::text
    from (
      select batch.campaign_id
      from content_factory.generation_batches batch
      where batch.id = 'e2000000-0000-4000-8000-000000000001'
      union all
      select job.campaign_id
      from content_factory.generation_jobs job
      where job.id = 'e3000000-0000-4000-8000-000000000001'
    ) bound
    where bound.campaign_id = (
      select campaign_id from campaign_test_context where name = 'aggregate_a'
    )
  ),
  '2',
  'paid batch and job bind to the exact selected campaign'
);

set local role authenticated;
insert into campaign_test_context (name, payload)
values (
  'aggregate_overview',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (
    select payload #>> '{usage,day,reserved_minor}'
    from campaign_test_context where name = 'aggregate_overview'
  ),
  '50',
  'organization overview aggregates reservations across two campaigns'
);
select is(
  (
    select campaign #>> '{usage,day,reserved_minor}'
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'aggregate_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'aggregate_a'
      )
  ),
  '25',
  'first campaign overview keeps its own reservation attribution'
);
select is(
  (
    select campaign #>> '{usage,day,reserved_minor}'
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'aggregate_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'aggregate_b'
      )
  ),
  '25',
  'second campaign overview keeps its own reservation attribution'
);
reset role;

select lives_ok(
  $$select pg_temp.create_campaign_job(20, null)$$,
  'legacy paid insertion without an explicit selector binds to the default campaign'
);
select is(
  (
    select count(*)::text
    from (
      select batch.campaign_id
      from content_factory.generation_batches batch
      where batch.id = 'e2000000-0000-4000-8000-000000000020'
      union all
      select job.campaign_id
      from content_factory.generation_jobs job
      where job.id = 'e3000000-0000-4000-8000-000000000020'
    ) bound
    where bound.campaign_id = (
      select id from content_factory.generation_campaigns
      where organization_id = 'e1000000-0000-4000-8000-000000000001'
        and kind = 'default'
    )
  ),
  '2',
  'default binding leaves no paid batch or job unattributed'
);

select throws_ok(
  $$select pg_temp.create_campaign_job(
    10,
    (select campaign_id from campaign_test_context where name = 'missing_policy')
  )$$,
  '55000',
  'paid_generation_campaign_policy_missing',
  'a campaign without a policy fails closed before reservation'
);
select throws_ok(
  $$select pg_temp.create_campaign_job(
    11,
    (select campaign_id from campaign_test_context where name = 'paused')
  )$$,
  '42501',
  'paid_generation_campaign_paused',
  'a paused campaign fails closed before reservation'
);
select throws_ok(
  $$select pg_temp.create_campaign_job(
    12,
    (select campaign_id from campaign_test_context where name = 'per_request')
  )$$,
  '54000',
  'generation_campaign_per_request_budget_exceeded',
  'campaign per-request limit rejects while the organization still allows'
);

select lives_ok(
  $$select pg_temp.create_campaign_job(
    3,
    (select campaign_id from campaign_test_context where name = 'lifecycle')
  )$$,
  'lifecycle campaign reserves its only daily slot'
);
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'e3000000-0000-4000-8000-000000000003'$$,
  'campaign reservation survives authoritative queued-to-starting recheck'
);
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'failed',
        output = output || jsonb_build_object(
          'failure_code', 'provider_request_rejected',
          'failed_at', now(),
          'actual_cost_minor', 0,
          'currency', 'USD'
        )
    where id = 'e3000000-0000-4000-8000-000000000003'$$,
  'definitive pre-submission failure releases campaign capacity'
);
select is(
  (
    select string_agg(event_type, ',' order by id)
    from content_factory.generation_spend_ledger
    where generation_job_id = 'e3000000-0000-4000-8000-000000000003'
  ),
  'reserved,released',
  'release is append-only and preserves campaign attribution through the job'
);
select lives_ok(
  $$select pg_temp.create_campaign_job(
    4,
    (select campaign_id from campaign_test_context where name = 'lifecycle')
  )$$,
  'released capacity is available to the next job in the same campaign'
);
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'e3000000-0000-4000-8000-000000000004'$$,
  'replacement job passes the immediate pre-provider campaign recheck'
);
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'submitted',
        actual_cost_minor = 25,
        output = output || jsonb_build_object(
          'provider_task_id', 'runway-campaign-budget-0004',
          'submitted_at', now(),
          'actual_cost_minor', 25,
          'currency', 'USD'
        )
    where id = 'e3000000-0000-4000-8000-000000000004'$$,
  'confirmed submission settles against the selected campaign'
);
select is(
  (
    select string_agg(event_type, ',' order by id)
    from content_factory.generation_spend_ledger
    where generation_job_id = 'e3000000-0000-4000-8000-000000000004'
  ),
  'reserved,settled',
  'settlement consumes capacity without rewriting the reservation'
);

set local role authenticated;
insert into campaign_test_context (name, payload)
values (
  'lifecycle_overview',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (
    select
      (campaign #>> '{usage,day,reserved_minor}') || ':' ||
      (campaign #>> '{usage,day,committed_minor}')
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'lifecycle_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'lifecycle'
      )
  ),
  '0:25',
  'campaign overview distinguishes released reserve from settled consumption'
);
reset role;
select throws_ok(
  $$select pg_temp.create_campaign_job(
    5,
    (select campaign_id from campaign_test_context where name = 'lifecycle')
  )$$,
  '54000',
  'generation_campaign_daily_budget_exceeded',
  'campaign daily limit rejects while organization capacity remains'
);
select throws_ok(
  $$update content_factory.generation_jobs
    set campaign_id = (
      select campaign_id from campaign_test_context where name = 'aggregate_b'
    )
    where id = 'e3000000-0000-4000-8000-000000000004'$$,
  '55000',
  'generation_spend_reservation_identity_immutable',
  'settled paid job cannot be reattributed to another campaign'
);
select throws_ok(
  $$update content_factory.generation_batches
    set campaign_id = (
      select campaign_id from campaign_test_context where name = 'aggregate_b'
    )
    where id = 'e2000000-0000-4000-8000-000000000004'$$,
  '55000',
  'generation_spend_reservation_identity_immutable',
  'paid batch cannot be reattributed to another campaign'
);

select lives_ok(
  $$select pg_temp.seed_historical_campaign_commit(
    1,
    (select campaign_id from campaign_test_context where name = 'monthly')
  )$$,
  'historical committed usage is attributed to its campaign through the job'
);
select lives_ok(
  $$select pg_temp.create_campaign_job(
    13,
    (select campaign_id from campaign_test_context where name = 'monthly')
  )$$,
  'monthly campaign still has current-day capacity for one reservation'
);
select throws_ok(
  $$select pg_temp.create_campaign_job(
    14,
    (select campaign_id from campaign_test_context where name = 'monthly')
  )$$,
  '54000',
  'generation_campaign_monthly_budget_exceeded',
  'campaign month limit rejects while its separate day limit still has room'
);

set local role authenticated;
insert into campaign_test_context (name, payload)
values (
  'final_overview',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'e1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (
    select
      (campaign #>> '{usage,day,reserved_minor}') || ':' ||
      (campaign #>> '{usage,month,reserved_minor}') || ':' ||
      (campaign #>> '{usage,month,committed_minor}') || ':' ||
      (campaign #>> '{usage,month,remaining_minor}')
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'final_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'monthly'
      )
  ),
  '25:25:25:0',
  'month blocker is campaign-scoped while current-day usage remains below 50'
);
select is(
  (
    select campaign ->> 'blocker_code'
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'final_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'missing_policy'
      )
  ),
  'paid_generation_campaign_policy_missing',
  'overview exposes a missing campaign policy as an explicit blocker'
);
select is(
  (
    select campaign ->> 'blocker_code'
    from campaign_test_context context,
      lateral jsonb_array_elements(context.payload -> 'campaigns') campaign
    where context.name = 'final_overview'
      and campaign ->> 'id' = (
        select campaign_id::text from campaign_test_context
        where name = 'paused'
      )
  ),
  'paid_generation_campaign_paused',
  'overview exposes a paused campaign as an explicit blocker'
);
select is(
  (
    select jsonb_array_length(payload -> 'campaigns')::text
    from campaign_test_context where name = 'final_overview'
  ),
  '8',
  'overview returns default, managed and fail-closed campaign records together'
);
select ok(
  (
    select (payload #>> '{usage,day,remaining_minor}')::bigint > 25
      and (payload #>> '{usage,month,remaining_minor}')::bigint > 25
    from campaign_test_context where name = 'final_overview'
  ),
  'organization envelope still has room after campaign-specific rejections'
);
reset role;

select * from finish();
rollback;
