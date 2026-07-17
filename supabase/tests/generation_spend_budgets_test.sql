begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.create_budget_job(p_ordinal integer)
returns uuid
language plpgsql
set search_path = ''
as $fixture$
declare
  organization_id_value constant uuid :=
    'a1000000-0000-4000-8000-000000000001';
  owner_id_value constant uuid :=
    'a1100000-0000-4000-8000-000000000001';
  product_id_value constant uuid :=
    'a1200000-0000-4000-8000-000000000001';
  batch_id_value uuid := (
    'b1000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  job_id_value uuid := (
    'c1000000-0000-4000-8000-' || lpad(p_ordinal::text, 12, '0')
  )::uuid;
  key_suffix text := lpad(p_ordinal::text, 4, '0');
begin
  if p_ordinal not between 1 and 9999 then
    raise exception using errcode = '22023', message = 'budget_fixture_invalid';
  end if;

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
    'Spend budget batch ' || key_suffix,
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
    encode(extensions.digest('budget-batch:' || key_suffix, 'sha256'), 'hex'),
    'spend-budget-batch-' || key_suffix,
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
      'sku', 'SPEND-BUDGET-SKU',
      'product_name', 'Spend budget product',
      'prompt_text', 'A safe five second product demonstration.',
      'format', '9:16',
      'ratio', '720:1280',
      'audio', false,
      'input_object_name',
        organization_id_value::text || '/' || owner_id_value::text ||
          '/uploads/budget-source.webp',
      'output_object_name',
        organization_id_value::text || '/' || owner_id_value::text ||
          '/generated/' || job_id_value::text || '.mp4',
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', 'wildberries',
      'destination_ref', 'wb-spend-budget-' || key_suffix,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    '{}'::jsonb,
    encode(extensions.digest('budget-job:' || key_suffix, 'sha256'), 'hex'),
    'spend-budget-job-' || key_suffix
  );

  return job_id_value;
end;
$fixture$;

select plan(50);

select has_table(
  'content_factory', 'generation_spend_policies',
  'organization spend policies are durable'
);
select has_table(
  'content_factory', 'generation_spend_ledger',
  'paid generation reservations use a durable ledger'
);
select has_table(
  'content_factory_private', 'generation_spend_platform_control',
  'the global paid-generation circuit breaker is private'
);
select has_trigger(
  'content_factory', 'generation_jobs', 'generation_spend_reservation',
  'paid jobs reserve budget atomically after insertion'
);
select has_trigger(
  'content_factory', 'generation_jobs', 'c_generation_spend_start_guard',
  'queued to starting has an authoritative server-side recheck'
);
select has_trigger(
  'content_factory', 'generation_jobs', 'generation_spend_lifecycle',
  'provider state changes drive settlement and release events'
);
select has_trigger(
  'content_factory', 'generation_spend_ledger',
  'generation_spend_ledger_append_only_guard',
  'the spend ledger is append-only'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_generation_spend_overview(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_generation_spend_overview(jsonb)',
    'execute'
  ),
  'only authenticated browser sessions may read spend snapshots'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_update_generation_spend_policy(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.creator_update_generation_spend_policy(jsonb)',
    'execute'
  ),
  'only authenticated browser sessions reach the owner/admin policy RPC'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_update_generation_spend_control(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'authenticated',
    'public.system_update_generation_spend_control(jsonb)',
    'execute'
  ) and not has_function_privilege(
    'anon',
    'public.system_update_generation_spend_control(jsonb)',
    'execute'
  ),
  'only service_role may change the platform circuit breaker'
);
select ok(
  not has_table_privilege(
    'authenticated', 'content_factory.generation_spend_policies', 'select'
  ) and not has_table_privilege(
    'authenticated', 'content_factory.generation_spend_ledger', 'select'
  ),
  'browser roles cannot bypass the narrow spend RPCs'
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
    'a1100000-0000-4000-8000-000000000001',
    'spend-owner@example.test',
    'Spend Owner'
  ),
  (
    'a1100000-0000-4000-8000-000000000002',
    'spend-admin@example.test',
    'Spend Admin'
  ),
  (
    'a1100000-0000-4000-8000-000000000003',
    'spend-operator@example.test',
    'Spend Operator'
  )
) as fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'a1000000-0000-4000-8000-000000000001',
  'Spend Budget Test',
  'spend-budget-test',
  'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    'a1000000-0000-4000-8000-000000000001',
    'a1100000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'a1000000-0000-4000-8000-000000000001',
    'a1100000-0000-4000-8000-000000000002',
    'admin', 'active'
  ),
  (
    'a1000000-0000-4000-8000-000000000001',
    'a1100000-0000-4000-8000-000000000003',
    'operator', 'active'
  );
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  'a1200000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'SPEND-BUDGET-SKU',
  'Spend budget product',
  'active',
  'a1100000-0000-4000-8000-000000000001'
);

create temporary table spend_test_context (
  name text primary key,
  payload jsonb,
  job_id uuid
) on commit drop;
grant select, insert, update on spend_test_context to authenticated;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'a1100000-0000-4000-8000-000000000001',
    true
  );
end;
$$;
set local role authenticated;

insert into spend_test_context (name, payload)
values (
  'missing_policy',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (select payload ->> 'blocker_code' from spend_test_context
   where name = 'missing_policy'),
  'paid_generation_policy_missing',
  'a new organization is fail-closed until an owner creates a policy'
);
select is(
  (select payload #>> '{policy,version}' from spend_test_context
   where name = 'missing_policy'),
  '0',
  'the missing-policy snapshot exposes expected_version zero'
);

reset role;
select throws_ok(
  $$select pg_temp.create_budget_job(1)$$,
  '55000',
  'paid_generation_policy_missing',
  'a paid job cannot be inserted while the organization policy is missing'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'a1100000-0000-4000-8000-000000000003',
    true
  );
end;
$$;
set local role authenticated;
select throws_ok(
  $$select public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Operator must not manage organization spend policy.',
    'expected_version', 0,
    'idempotency_key', 'spend-policy-operator-denied-0001'
  ))$$,
  '42501',
  'role_not_allowed',
  'operators cannot change organization spend limits'
);

reset role;
do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'a1100000-0000-4000-8000-000000000001',
    true
  );
end;
$$;
set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'policy_v1',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Enable guarded paid generation for the test organization.',
    'expected_version', 0,
    'idempotency_key', 'spend-policy-create-0001'
  ))
);
select is(
  (select payload #>> '{policy,version}' from spend_test_context
   where name = 'policy_v1'),
  '1',
  'expected version zero creates the first explicit organization policy'
);
select is(
  (select payload #>> '{policy,daily_limit_minor}' from spend_test_context
   where name = 'policy_v1'),
  '50',
  'the update RPC returns the canonical policy snapshot'
);
select is(
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Enable guarded paid generation for the test organization.',
    'expected_version', 0,
    'idempotency_key', 'spend-policy-create-0001'
  )) #>> '{policy,version}',
  '1',
  'an exact policy command replay is idempotent'
);
select throws_ok(
  $$select public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', false,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Different command payload under a reused key is forbidden.',
    'expected_version', 0,
    'idempotency_key', 'spend-policy-create-0001'
  ))$$,
  '23505',
  'idempotency_key_conflict',
  'a reused policy idempotency key rejects a different payload'
);
select throws_ok(
  $$select public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'A stale expected version must never overwrite current limits.',
    'expected_version', 0,
    'idempotency_key', 'spend-policy-stale-0001'
  ))$$,
  '40001',
  'generation_budget_policy_changed',
  'optimistic versioning prevents lost policy updates'
);

reset role;
update content_factory.generation_spend_policies
set per_request_limit_minor = 24
where organization_id = 'a1000000-0000-4000-8000-000000000001';
select throws_ok(
  $$select pg_temp.create_budget_job(10)$$,
  '54000',
  'generation_per_request_budget_exceeded',
  'a paid job above the per-request money limit rolls back before provider work'
);
update content_factory.generation_spend_policies
set per_request_limit_minor = 25
where organization_id = 'a1000000-0000-4000-8000-000000000001';
insert into spend_test_context (name, job_id)
values ('job_1', pg_temp.create_budget_job(1));
select is(
  (
    select event_type || ':' || reserved_delta_minor::text
    from content_factory.generation_spend_ledger
    where generation_job_id = (
      select job_id from spend_test_context where name = 'job_1'
    )
  ),
  'reserved:25',
  'a paid job and its monetary reservation commit atomically'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'after_reserve',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (select payload #>> '{usage,day,reserved_minor}' from spend_test_context
   where name = 'after_reserve'),
  '25',
  'the day snapshot distinguishes reserved money from committed estimates'
);
select is(
  (select payload #>> '{usage,day,remaining_minor}' from spend_test_context
   where name = 'after_reserve'),
  '25',
  'the day snapshot reports the remaining guarded capacity'
);

insert into spend_test_context (name, payload)
values (
  'policy_disabled',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', false,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Pause paid starts while retaining every existing reservation.',
    'expected_version', 1,
    'idempotency_key', 'spend-policy-disable-0001'
  ))
);
select is(
  (select payload ->> 'blocker_code' from spend_test_context
   where name = 'policy_disabled'),
  'paid_generation_paused',
  'the organization switch is visible as an explicit blocker'
);

reset role;
select throws_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'c1000000-0000-4000-8000-000000000001'$$,
  '42501',
  'paid_generation_paused',
  'disabling the policy blocks the authoritative queued-to-starting transition'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'policy_v3',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Resume guarded paid starts after the administrative pause.',
    'expected_version', 2,
    'idempotency_key', 'spend-policy-enable-0001'
  ))
);
reset role;

select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'c1000000-0000-4000-8000-000000000001'$$,
  'a queued paid job with an active reservation may be claimed'
);
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'submitted',
        actual_cost_minor = 25,
        output = output || jsonb_build_object(
          'provider_task_id', 'runway-spend-budget-0001',
          'submitted_at', now(),
          'actual_cost_minor', 25,
          'currency', 'USD'
        )
    where id = 'c1000000-0000-4000-8000-000000000001'$$,
  'a confirmed provider submission settles its reservation'
);
select is(
  (
    select string_agg(
      event_type || ':' || reserved_delta_minor::text || ':' ||
        committed_delta_minor::text,
      ',' order by id
    )
    from content_factory.generation_spend_ledger
    where generation_job_id =
      'c1000000-0000-4000-8000-000000000001'
  ),
  'reserved:25:0,settled:-25:25',
  'settlement preserves an append-only reservation-to-commit audit trail'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'after_settle',
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001'
  ))
);
select is(
  (select payload #>> '{usage,day,reserved_minor}' from spend_test_context
   where name = 'after_settle'),
  '0',
  'settled work no longer appears as reserved'
);
select is(
  (select payload #>> '{usage,day,committed_minor}' from spend_test_context
   where name = 'after_settle'),
  '25',
  'settled work is reported as an accounted provider SKU estimate'
);
reset role;

insert into spend_test_context (name, job_id)
values ('job_2', pg_temp.create_budget_job(2));
update content_factory.generation_jobs
set status = 'starting',
    output = output || jsonb_build_object('starting_at', now())
where id = 'c1000000-0000-4000-8000-000000000002';
select lives_ok(
  $$update content_factory.generation_jobs
    set status = 'failed',
        output = output || jsonb_build_object(
          'failure_code', 'provider_request_rejected',
          'failed_at', now(),
          'actual_cost_minor', 0,
          'currency', 'USD'
        )
    where id = 'c1000000-0000-4000-8000-000000000002'$$,
  'a definitive pre-submission failure releases reserved capacity'
);
select is(
  (
    select string_agg(event_type, ',' order by id)
    from content_factory.generation_spend_ledger
    where generation_job_id =
      'c1000000-0000-4000-8000-000000000002'
  ),
  'reserved,released',
  'release remains an append-only event rather than rewriting the reservation'
);

set local role authenticated;
select throws_ok(
  $$select public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'UTC',
    'reason', 'Historical spend must keep its original accounting timezone.',
    'expected_version', 3,
    'idempotency_key', 'spend-policy-timezone-immutable-0001'
  ))$$,
  '55000',
  'generation_budget_policy_changed',
  'accounting timezone is immutable even after every reservation is settled or released'
);
reset role;

insert into spend_test_context (name, job_id)
values ('job_3', pg_temp.create_budget_job(3));
select throws_ok(
  $$select pg_temp.create_budget_job(4)$$,
  '54000',
  'generation_daily_budget_exceeded',
  'atomic reservation rejects a job that would exceed the daily money limit'
);
select is(
  (
    select count(*)::text
    from content_factory.generation_jobs
    where id = 'c1000000-0000-4000-8000-000000000004'
  ),
  '0',
  'a rejected reservation rolls back the paid job itself'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'policy_v4',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 25,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Lower the daily limit to verify the pre-provider recheck.',
    'expected_version', 3,
    'idempotency_key', 'spend-policy-lower-0001'
  ))
);
reset role;
select throws_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'c1000000-0000-4000-8000-000000000003'$$,
  '54000',
  'generation_daily_budget_exceeded',
  'a lowered limit is rechecked immediately before the provider claim'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'policy_v5',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 50,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Restore the guarded daily limit after the recheck test.',
    'expected_version', 4,
    'idempotency_key', 'spend-policy-restore-0001'
  ))
);
reset role;
update content_factory.generation_jobs
set status = 'starting',
    output = output || jsonb_build_object('starting_at', now())
where id = 'c1000000-0000-4000-8000-000000000003';

select throws_ok(
  $$update content_factory.generation_spend_ledger
    set reason_code = 'tampered'
    where generation_job_id =
      'c1000000-0000-4000-8000-000000000001'
      and event_type = 'reserved'$$,
  '55000',
  'generation_spend_ledger_append_only',
  'even trusted SQL cannot rewrite a ledger event'
);
select throws_ok(
  $$delete from content_factory.generation_spend_ledger
    where generation_job_id =
      'c1000000-0000-4000-8000-000000000002'
      and event_type = 'released'$$,
  '55000',
  'generation_spend_ledger_append_only',
  'even trusted SQL cannot delete a ledger event'
);

set local role authenticated;
insert into spend_test_context (name, payload)
values (
  'policy_v6',
  public.creator_update_generation_spend_policy(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001',
    'paid_generation_enabled', true,
    'daily_limit_minor', 100,
    'monthly_limit_minor', 100,
    'per_request_limit_minor', 25,
    'timezone', 'Europe/Moscow',
    'reason', 'Raise the daily ceiling to isolate the calendar-month limit.',
    'expected_version', 5,
    'idempotency_key', 'spend-policy-monthly-limit-0001'
  ))
);
reset role;

-- Seed a committed event on another day in the same accounting month. This
-- keeps current-day usage below its limit while the month reaches its own
-- ceiling, including on the first or last calendar day of a month.
insert into content_factory.generation_batches (
  id, organization_id, product_id, created_by, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key,
  provider, model, duration_seconds, audio,
  estimated_cost_minor, estimated_credits, currency
)
values (
  'd1000000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'a1200000-0000-4000-8000-000000000001',
  'a1100000-0000-4000-8000-000000000001',
  'Historical accounting fixture',
  'mock', false, 'mock_ready', 1, 1,
  '{}'::jsonb,
  encode(extensions.digest('historical-budget-batch', 'sha256'), 'hex'),
  'historical-budget-batch-0001',
  'mock', 'mock', 0, false, 0, 0, 'USD'
);
insert into content_factory.generation_jobs (
  id, organization_id, product_id, batch_id, ordinal,
  requested_by, assigned_to, mode, provider, allow_real_spend,
  estimated_cost_minor, actual_cost_minor, status,
  input, output, request_hash, idempotency_key
)
values (
  'd2000000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'a1200000-0000-4000-8000-000000000001',
  'd1000000-0000-4000-8000-000000000001',
  1,
  'a1100000-0000-4000-8000-000000000001',
  'a1100000-0000-4000-8000-000000000001',
  'mock', 'mock', false, 0, 0, 'mock_ready',
  '{}'::jsonb, '{}'::jsonb,
  encode(extensions.digest('historical-budget-job', 'sha256'), 'hex'),
  'historical-budget-job-0001'
);
with accounting_dates as (
  select
    (clock_timestamp() at time zone 'Europe/Moscow')::date as current_day,
    date_trunc(
      'month',
      (clock_timestamp() at time zone 'Europe/Moscow')::date
    )::date as current_month
), historical_dates as (
  select
    case
      when current_day > current_month then current_month
      else current_day + 1
    end as budget_day,
    current_month as budget_month
  from accounting_dates
)
insert into content_factory.generation_spend_ledger (
  organization_id, generation_job_id, event_type,
  estimated_cost_minor, actual_cost_minor,
  reserved_delta_minor, committed_delta_minor, currency,
  budget_day, budget_month, policy_version, reason_code, metadata
)
select
  'a1000000-0000-4000-8000-000000000001',
  'd2000000-0000-4000-8000-000000000001',
  event.event_type,
  25,
  event.actual_cost_minor,
  event.reserved_delta_minor,
  event.committed_delta_minor,
  'USD',
  historical_dates.budget_day,
  historical_dates.budget_month,
  6,
  event.reason_code,
  jsonb_build_object('fixture', 'historical_monthly_usage')
from historical_dates
cross join (values
  ('reserved', 0::bigint, 25::bigint, 0::bigint, 'historical_reserved'),
  ('settled', 25::bigint, -25::bigint, 25::bigint, 'historical_settled')
) as event(
  event_type, actual_cost_minor, reserved_delta_minor,
  committed_delta_minor, reason_code
);

insert into spend_test_context (name, job_id)
values ('job_4', pg_temp.create_budget_job(4));
select throws_ok(
  $$select pg_temp.create_budget_job(5)$$,
  '54000',
  'generation_monthly_budget_exceeded',
  'the month limit rejects a job while the separate day limit still has room'
);

select lives_ok(
  $$select public.system_update_generation_spend_control(jsonb_build_object(
    'paid_generation_enabled', false,
    'expected_version', 1,
    'reason', 'Emergency stop test for all Runway paid provider starts.',
    'changed_by', 'pgTAP generation spend test'
  ))$$,
  'service-side control can activate the global emergency stop'
);
select throws_ok(
  $$update content_factory.generation_jobs
    set status = 'starting',
        output = output || jsonb_build_object('starting_at', now())
    where id = 'c1000000-0000-4000-8000-000000000004'$$,
  '42501',
  'paid_generation_paused',
  'the global stop blocks a queued job that reserved money before the pause'
);
select throws_ok(
  $$select pg_temp.create_budget_job(5)$$,
  '42501',
  'paid_generation_paused',
  'the global stop rejects a new paid job before any provider work'
);
select is(
  (
    select count(*)::text
    from content_factory.generation_jobs
    where id = 'c1000000-0000-4000-8000-000000000005'
  ),
  '0',
  'a global-stop rejection rolls back the paid job insert atomically'
);
set local role authenticated;
select is(
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001'
  )) ->> 'blocker_code',
  'paid_generation_paused',
  'the global emergency stop has precedence in the canonical snapshot'
);
reset role;
select lives_ok(
  $$select public.system_update_generation_spend_control(jsonb_build_object(
    'paid_generation_enabled', true,
    'expected_version', 2,
    'reason', 'Restore guarded Runway paid generation after the stop test.',
    'changed_by', 'pgTAP generation spend test'
  ))$$,
  'service-side control can restore the guarded global switch'
);
select throws_ok(
  $$select public.system_update_generation_spend_control(jsonb_build_object(
    'paid_generation_enabled', false,
    'expected_version', 1,
    'reason', 'A stale emergency-stop version must never overwrite state.',
    'changed_by', 'pgTAP generation spend test'
  ))$$,
  '40001',
  'generation_budget_policy_changed',
  'the platform circuit breaker uses optimistic versioning'
);

-- Keep the unresolved-incident scenario last. The reconciliation freeze is
-- organization-wide by design, so marking it earlier would prevent the later
-- monthly-limit and global-stop fixtures from creating their paid jobs.
select lives_ok(
  $$update content_factory.generation_jobs
    set output = output || jsonb_build_object(
      'reconciliation_required', true,
      'reconciliation_incident_id',
        'a1300000-0000-4000-8000-000000000001',
      'reconciliation_reason_code', 'provider_create_timeout',
      'reconciliation_required_at', now()
    )
    where id = 'c1000000-0000-4000-8000-000000000003'$$,
  'an ambiguous provider create outcome freezes rather than releases the reserve'
);
select is(
  (
    select string_agg(event_type, ',' order by id)
    from content_factory.generation_spend_ledger
    where generation_job_id =
      'c1000000-0000-4000-8000-000000000003'
  ),
  'reserved,frozen',
  'the ambiguous reservation remains visible and frozen for reconciliation'
);

set local role authenticated;
select is(
  public.creator_generation_spend_overview(jsonb_build_object(
    'organization_id', 'a1000000-0000-4000-8000-000000000001'
  )) ->> 'blocker_code',
  'real_generation_reconciliation_required',
  'the spend snapshot exposes the organization-wide reconciliation freeze'
);
reset role;

select * from finish();
rollback;
