begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

-- A compact processing-job fixture derived from
-- real_generation_reconciliation_test.sql.  It deliberately creates the full
-- batch -> generation -> review-task chain so the watchdog is exercised
-- against the same paid-generation invariants as production.
create or replace function pg_temp.create_processing_real_job(
  p_job_id uuid,
  p_batch_id uuid,
  p_task_id uuid,
  p_organization_id uuid,
  p_product_id uuid,
  p_requested_by uuid,
  p_assigned_to uuid,
  p_key_suffix text,
  p_created_at timestamptz default now() - interval '5 minutes'
)
returns void
language plpgsql
set search_path = ''
as $fixture$
begin
  if p_job_id is null
     or p_batch_id is null
     or p_task_id is null
     or p_organization_id is null
     or p_product_id is null
     or p_requested_by is null
     or p_assigned_to is null
     or p_key_suffix !~ '^[a-z0-9-]{4,40}$'
     or p_created_at is null then
    raise exception using
      errcode = '22023',
      message = 'native_worker_watchdog_fixture_invalid';
  end if;

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key,
    provider, model, duration_seconds, audio,
    estimated_cost_minor, estimated_credits, currency,
    created_at, updated_at
  ) values (
    p_batch_id,
    p_organization_id,
    p_product_id,
    p_requested_by,
    left('Native worker watchdog ' || p_key_suffix, 180),
    'real',
    true,
    'processing',
    1,
    0,
    jsonb_build_object(
      'job_id', p_job_id,
      'review_task_id', p_task_id,
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
    encode(extensions.digest('native-batch:' || p_key_suffix, 'sha256'), 'hex'),
    'native-worker-batch-' || p_key_suffix,
    'runway',
    'gen4_turbo',
    5,
    false,
    25,
    25,
    'USD',
    p_created_at,
    p_created_at
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key,
    created_at, updated_at
  ) values (
    p_job_id,
    p_organization_id,
    p_product_id,
    p_batch_id,
    1,
    p_requested_by,
    p_assigned_to,
    'real',
    'runway',
    true,
    25,
    25,
    'processing',
    jsonb_build_object(
      'sku', 'NATIVE-WORKER-SKU',
      'product_name', 'Native worker watchdog product',
      'prompt_text', 'A safe five second product video.',
      'format', '9:16',
      'ratio', '720:1280',
      'audio', false,
      'input_object_name',
        p_organization_id::text || '/' || p_requested_by::text ||
          '/uploads/native-worker.webp',
      'output_object_name',
        p_organization_id::text || '/' || p_assigned_to::text ||
          '/generated/' || p_job_id::text || '.mp4',
      'review_task_id', p_task_id,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', 'wildberries',
      'destination_ref', 'wb-native-worker-fixture',
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    jsonb_build_object(
      'provider_task_id', 'runway_native_' || p_key_suffix,
      'submitted_at', p_created_at,
      'processing_at', p_created_at,
      'actual_cost_minor', 25,
      'currency', 'USD'
    ),
    encode(extensions.digest('native-job:' || p_key_suffix, 'sha256'), 'hex'),
    'native-worker-job-' || p_key_suffix,
    p_created_at,
    p_created_at
  );

  insert into content_factory.creator_tasks (
    id, organization_id, assignee_id, created_by, product_id,
    generation_job_id, task_type, title, instructions,
    status, priority, payout_minor, result, idempotency_key,
    created_at, updated_at
  ) values (
    p_task_id,
    p_organization_id,
    p_assigned_to,
    p_requested_by,
    p_product_id,
    p_job_id,
    'video_review',
    'Review native worker fixture ' || p_key_suffix,
    'Review only after the provider reaches a terminal state.',
    'blocked',
    2,
    1200,
    jsonb_build_object(
      'generation_status', 'processing',
      'review_required', true,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'audio', false,
      'estimated_cost_minor', 25,
      'estimated_credits', 25,
      'currency', 'USD'
    ),
    'native-worker-task-' || p_key_suffix,
    p_created_at,
    p_created_at
  );
end;
$fixture$;

-- Match membership_role(..., true, ...) instead of weakening the health RPC
-- for tests: every manager fixture receives the same refreshed course and
-- final-exam evidence required by production authorization.
create or replace function pg_temp.grant_native_worker_training_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $training_gate$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
  final_question_count integer;
begin
  if p_organization_id is null
     or p_profile_id is null
     or p_key_prefix !~ '^[a-z0-9_-]{4,80}$' then
    raise exception using
      errcode = '22023',
      message = 'native_worker_training_gate_fixture_invalid';
  end if;

  for module_row in
    select
      module.code,
      jsonb_array_length(
        module.content #> '{knowledge_check,questions}'
      ) as question_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
    order by module.order_index
  loop
    select coalesce(
      jsonb_object_agg(
        question.code,
        answer_key.correct_answers
        order by question.order_index
      ),
      '{}'::jsonb
    )
    into answers_value
    from content_factory.training_questions question
    join content_factory_private.training_answer_keys answer_key
      on answer_key.question_code = question.code
    where question.module_code = module_row.code
      and question.order_index between 901 and 1000
      and strpos(
        question.code,
        'course_check_' || module_row.code || '_'
      ) = 1;

    if module_row.question_count < 1
       or (select count(*) from pg_catalog.jsonb_object_keys(answers_value))
         <> module_row.question_count then
      raise exception using
        errcode = '55000',
        message = 'native_worker_training_gate_fixture_invalid';
    end if;

    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      'completed',
      1,
      module_row.question_count,
      module_row.question_count,
      module_row.question_count,
      true,
      answers_value,
      content_factory_private.json_hash(jsonb_build_object(
        'module_code', module_row.code,
        'answers', answers_value
      )),
      left(
        'course-check:' || p_key_prefix || ':' || module_row.code,
        180
      )
    )
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed'
    );
  end loop;

  select module.question_count
  into final_question_count
  from content_factory.training_modules module
  where module.code = 'operator_final_exam'
    and module.module_type = 'exam'
    and module.is_active;

  if final_question_count is null or final_question_count < 1 then
    raise exception using
      errcode = '55000',
      message = 'native_worker_training_gate_fixture_invalid';
  end if;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    'completed',
    1,
    final_question_count,
    final_question_count,
    final_question_count,
    true,
    '{}'::jsonb,
    content_factory_private.json_hash(jsonb_build_object(
      'profile_id', p_profile_id,
      'exam', 'operator_final_exam'
    )),
    left('native-health:' || p_key_prefix || ':final-exam', 180)
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    p_organization_id,
    p_profile_id,
    'operator_final_exam',
    attempt_id_value,
    'passed'
  );
end;
$training_gate$;

select no_plan();

select has_table(
  'content_factory',
  'background_worker_runs',
  'native worker executions have a durable run journal'
);
select has_column(
  'content_factory', 'background_worker_runs', 'lease_token',
  'worker runs use an unguessable lease token'
);
select has_column(
  'content_factory', 'background_worker_runs', 'lease_expires_at',
  'worker run leases have an authoritative expiry'
);
select ok(
  (
    select relation.relrowsecurity
    from pg_catalog.pg_class relation
    where relation.oid =
      'content_factory.background_worker_runs'::regclass
  ),
  'the worker run journal has RLS enabled'
);
select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.background_worker_runs',
    'select,insert,update,delete'
  ),
  'authenticated users have no direct access to worker leases or history'
);
select ok(
  not has_table_privilege(
    'anon',
    'content_factory.background_worker_runs',
    'select,insert,update,delete'
  ),
  'anonymous users have no direct access to worker leases or history'
);

select ok(
  position(
    'contentengine_background_worker_url'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0
  and position(
    'contentengine_background_worker_secret'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0
  and position(
    pg_catalog.concat('contentengine_', 'worker_url')
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) = 0
  and position(
    pg_catalog.concat('contentengine_', 'worker_secret')
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) = 0,
  'scheduler health uses only the canonical background-worker Vault aliases'
);
select ok(
  position(
    'count(*) = 1'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0
  and position(
    'job.active'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0
  and position(
    '*/2 * * * *'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0
  and position(
    'secret.decrypted_secret'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.background_scheduler_status()'::regprocedure
    )
  ) > 0,
  'scheduler readiness requires one active two-minute job and rejects embedded decrypted values'
);
select ok(
  position(
    'contentengine_background_worker_url'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.dispatch_background_worker()'::regprocedure
    )
  ) > 0
  and position(
    'contentengine_background_worker_secret'
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.dispatch_background_worker()'::regprocedure
    )
  ) > 0
  and position(
    pg_catalog.concat('contentengine_', 'worker_url')
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.dispatch_background_worker()'::regprocedure
    )
  ) = 0
  and position(
    pg_catalog.concat('contentengine_', 'worker_secret')
    in pg_catalog.pg_get_functiondef(
      'content_factory_private.dispatch_background_worker()'::regprocedure
    )
  ) = 0,
  'native dispatch reads only the canonical Vault aliases at execution time'
);

select has_column(
  'content_factory', 'generation_jobs', 'provider_poll_attempt_count',
  'generation jobs persist the total provider poll count'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_poll_failure_count',
  'generation jobs persist consecutive provider poll failures'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_last_polled_at',
  'generation jobs persist their latest provider poll time'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_last_poll_succeeded_at',
  'generation jobs persist their latest successful provider contact'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_next_poll_at',
  'generation jobs persist their next eligible provider poll time'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_last_poll_code',
  'generation jobs persist a bounded provider outcome code'
);
select has_column(
  'content_factory', 'generation_jobs', 'provider_stalled_at',
  'generation jobs persist the first durable stalled observation'
);

select ok(
  has_function_privilege(
    'service_role',
    'public.system_begin_background_worker(jsonb)',
    'execute'
  ),
  'service role may acquire the singleton background-worker lease'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_begin_background_worker(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_begin_background_worker(jsonb)',
    'execute'
  ),
  'browser roles cannot acquire the system worker lease'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_heartbeat_background_worker(jsonb)',
    'execute'
  ),
  'service role may renew an owned worker lease'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_heartbeat_background_worker(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_heartbeat_background_worker(jsonb)',
    'execute'
  ),
  'browser roles cannot renew a worker lease'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_finish_background_worker(jsonb)',
    'execute'
  ),
  'service role may finish an owned worker run'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_finish_background_worker(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_finish_background_worker(jsonb)',
    'execute'
  ),
  'browser roles cannot forge worker completion'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_record_generation_poll_outcome(jsonb)',
    'execute'
  ),
  'service role may record an owned provider poll outcome'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_record_generation_poll_outcome(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_record_generation_poll_outcome(jsonb)',
    'execute'
  ),
  'browser roles cannot forge provider health outcomes'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_background_worker_health(jsonb)',
    'execute'
  ),
  'service role may inspect global worker health'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_background_worker_health(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_background_worker_health(jsonb)',
    'execute'
  ),
  'global worker health is not exposed to browser roles'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_operational_health(jsonb)',
    'execute'
  ),
  'authenticated managers may request organization-scoped health'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.creator_operational_health(jsonb)',
    'execute'
  ),
  'anonymous callers cannot inspect organization health'
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
    'a8000000-0000-4000-8000-000000000001',
    'native-worker-owner@example.test',
    'Native Worker Owner'
  ),
  (
    'a8000000-0000-4000-8000-000000000002',
    'native-worker-admin@example.test',
    'Native Worker Admin'
  ),
  (
    'a8000000-0000-4000-8000-000000000003',
    'native-worker-operator@example.test',
    'Native Worker Operator'
  ),
  (
    'a8000000-0000-4000-8000-000000000004',
    'native-worker-other-owner@example.test',
    'Native Worker Other Owner'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    'a8100000-0000-4000-8000-000000000001',
    'Native Worker Watchdog',
    'native-worker-watchdog',
    'active'
  ),
  (
    'a8100000-0000-4000-8000-000000000002',
    'Native Worker Watchdog Other',
    'native-worker-watchdog-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  'a8100000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000001',
  'owner',
  'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  'a8100000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000002',
  'admin',
  'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  'a8100000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000003',
  'operator',
  'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  'a8100000-0000-4000-8000-000000000002',
  'a8000000-0000-4000-8000-000000000004',
  'owner',
  'active'
);

select lives_ok(
  $$select pg_temp.grant_native_worker_training_gate(
    'a8100000-0000-4000-8000-000000000001',
    'a8000000-0000-4000-8000-000000000001',
    'native-owner'
  )$$,
  'the owner fixture satisfies the authoritative training gate'
);
select lives_ok(
  $$select pg_temp.grant_native_worker_training_gate(
    'a8100000-0000-4000-8000-000000000001',
    'a8000000-0000-4000-8000-000000000002',
    'native-admin'
  )$$,
  'the administrator fixture satisfies the authoritative training gate'
);
select lives_ok(
  $$select pg_temp.grant_native_worker_training_gate(
    'a8100000-0000-4000-8000-000000000002',
    'a8000000-0000-4000-8000-000000000004',
    'native-other-owner'
  )$$,
  'the other organization owner satisfies the authoritative training gate'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    'a8200000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000001',
    'NATIVE-WORKER-1',
    'Native worker product',
    'active',
    '{"brand":"ALTEA"}'::jsonb,
    'a8000000-0000-4000-8000-000000000001'
  ),
  (
    'a8200000-0000-4000-8000-000000000002',
    'a8100000-0000-4000-8000-000000000002',
    'NATIVE-WORKER-2',
    'Native worker product in another organization',
    'active',
    '{"brand":"ALTEA"}'::jsonb,
    'a8000000-0000-4000-8000-000000000004'
  );

select lives_ok(
  $$select pg_temp.create_processing_real_job(
    'a8300000-0000-4000-8000-000000000001',
    'a8400000-0000-4000-8000-000000000001',
    'a8500000-0000-4000-8000-000000000001',
    'a8100000-0000-4000-8000-000000000001',
    'a8200000-0000-4000-8000-000000000001',
    'a8000000-0000-4000-8000-000000000001',
    'a8000000-0000-4000-8000-000000000003',
    'primary-job'
  )$$,
  'a valid processing paid job can be watched'
);

select lives_ok(
  $$select pg_temp.create_processing_real_job(
    'a8300000-0000-4000-8000-000000000002',
    'a8400000-0000-4000-8000-000000000002',
    'a8500000-0000-4000-8000-000000000002',
    'a8100000-0000-4000-8000-000000000002',
    'a8200000-0000-4000-8000-000000000002',
    'a8000000-0000-4000-8000-000000000004',
    'a8000000-0000-4000-8000-000000000004',
    'aged-job',
    now() - interval '3 hours'
  )$$,
  'an aged active job models the wall-clock stalled threshold'
);

create temporary table native_worker_results (
  name text primary key,
  payload jsonb not null
) on commit drop;

select throws_ok(
  $$select public.system_begin_background_worker(
    '{"unexpected":true}'::jsonb
  )$$,
  '22023',
  'background_worker_begin_payload_invalid',
  'worker lease acquisition rejects unrecognized input'
);

insert into native_worker_results (name, payload)
values (
  'first_begin',
  public.system_begin_background_worker(jsonb_build_object(
    'trigger_source', 'smoke',
    'lease_seconds', 120
  ))
);

select is(
  (select payload ->> 'acquired'
   from native_worker_results where name = 'first_begin'),
  'true',
  'the first scheduler invocation acquires the worker lease'
);
select matches(
  (select payload #>> '{run,id}'
   from native_worker_results where name = 'first_begin'),
  '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  'lease acquisition returns a durable run id'
);
select matches(
  (select payload #>> '{run,lease_token}'
   from native_worker_results where name = 'first_begin'),
  '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  'lease acquisition returns an unguessable ownership token'
);

select throws_ok(
  format(
    'delete from content_factory.background_worker_runs where id = %L::uuid',
    (
      select payload #>> '{run,id}'
      from native_worker_results where name = 'first_begin'
    )
  ),
  '55000',
  'background_worker_run_deletion_forbidden',
  'an active worker lease cannot be deleted'
);

insert into content_factory.background_worker_runs (
  id, lease_token, trigger_source, status,
  started_at, heartbeat_at, lease_expires_at, finished_at, summary
)
values
  (
    'a8700000-0000-4000-8000-000000000001',
    'a8800000-0000-4000-8000-000000000001',
    'smoke',
    'completed',
    now() - interval '100 days 5 minutes',
    now() - interval '100 days 4 minutes',
    now() - interval '100 days 1 minute',
    now() - interval '100 days',
    '{"fixture":"manual-retention"}'::jsonb
  ),
  (
    'a8700000-0000-4000-8000-000000000002',
    'a8800000-0000-4000-8000-000000000002',
    'smoke',
    'completed',
    now() - interval '100 days 5 minutes',
    now() - interval '100 days 4 minutes',
    now() - interval '100 days 1 minute',
    now() - interval '100 days',
    '{"fixture":"begin-retention"}'::jsonb
  );
select lives_ok(
  $$delete from content_factory.background_worker_runs
    where id = 'a8700000-0000-4000-8000-000000000001'$$,
  'terminal worker history older than ninety days may be retained or purged safely'
);
select is(
  (
    select count(*)::integer
    from content_factory.background_worker_runs
    where id = 'a8700000-0000-4000-8000-000000000001'
  ),
  0,
  'the retention guard permits deletion of an old terminal run'
);

insert into native_worker_results (name, payload)
values (
  'overlap_begin',
  public.system_begin_background_worker(jsonb_build_object(
    'trigger_source', 'manual',
    'lease_seconds', 120
  ))
);

select is(
  (select payload ->> 'acquired'
   from native_worker_results where name = 'overlap_begin'),
  'false',
  'a concurrent scheduler invocation cannot overlap the active lease'
);
select is(
  (
    select count(*)::integer
    from content_factory.background_worker_runs
    where id = 'a8700000-0000-4000-8000-000000000002'
  ),
  0,
  'begin opportunistically removes terminal worker history older than ninety days'
);
select is(
  (
    select count(*)::integer
    from content_factory.background_worker_runs
    where status = 'running'
      and lease_expires_at > now()
  ),
  1,
  'non-overlap is represented by exactly one unexpired running row'
);

insert into native_worker_results (name, payload)
select
  'heartbeat',
  public.system_heartbeat_background_worker(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'lease_seconds', 180
  ))
from native_worker_results begin_result
where begin_result.name = 'first_begin';

select is(
  (select payload ->> 'ok'
   from native_worker_results where name = 'heartbeat'),
  'true',
  'the lease owner can renew its heartbeat'
);
select throws_ok(
  format(
    'select public.system_heartbeat_background_worker(%L::jsonb)',
    jsonb_build_object(
      'run_id', (
        select payload #>> '{run,id}'
        from native_worker_results where name = 'first_begin'
      ),
      'lease_token', 'a8600000-0000-4000-8000-000000000001',
      'lease_seconds', 180
    )::text
  ),
  '55000',
  'background_worker_lease_mismatch',
  'a stale or forged token cannot renew another worker lease'
);

insert into native_worker_results (name, payload)
select
  'first_finish',
  public.system_finish_background_worker(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'status', 'completed',
    'summary', jsonb_build_object('source', 'pgtap', 'processed', 0)
  ))
from native_worker_results begin_result
where begin_result.name = 'first_begin';

select is(
  (select payload ->> 'idempotent'
   from native_worker_results where name = 'first_finish'),
  'false',
  'the first matching finish performs the terminal transition'
);
select throws_ok(
  format(
    'delete from content_factory.background_worker_runs where id = %L::uuid',
    (
      select payload #>> '{run,id}'
      from native_worker_results where name = 'first_begin'
    )
  ),
  '55000',
  'background_worker_run_deletion_forbidden',
  'fresh terminal worker history cannot be deleted before retention expiry'
);
insert into native_worker_results (name, payload)
select
  'finish_replay',
  public.system_finish_background_worker(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'status', 'completed',
    'summary', jsonb_build_object('source', 'pgtap', 'processed', 0)
  ))
from native_worker_results begin_result
where begin_result.name = 'first_begin';

select is(
  (select payload ->> 'idempotent'
   from native_worker_results where name = 'finish_replay'),
  'true',
  'an identical terminal acknowledgement is idempotent'
);
select throws_ok(
  format(
    'select public.system_finish_background_worker(%L::jsonb)',
    jsonb_build_object(
      'run_id', (
        select payload #>> '{run,id}'
        from native_worker_results where name = 'first_begin'
      ),
      'lease_token', (
        select payload #>> '{run,lease_token}'
        from native_worker_results where name = 'first_begin'
      ),
      'status', 'failed',
      'summary', jsonb_build_object('source', 'pgtap'),
      'error_code', 'conflicting_finish'
    )::text
  ),
  '55000',
  'background_worker_run_terminal_conflict',
  'a completed run cannot be rewritten to a conflicting terminal state'
);

insert into native_worker_results (name, payload)
values (
  'poll_begin',
  public.system_begin_background_worker(jsonb_build_object(
    'trigger_source', 'schedule',
    'lease_seconds', 300
  ))
);

select is(
  (select payload ->> 'acquired'
   from native_worker_results where name = 'poll_begin'),
  'true',
  'finishing a run releases the singleton lease for the next scheduler cycle'
);

select throws_ok(
  format(
    'select public.system_record_generation_poll_outcome(%L::jsonb)',
    jsonb_build_object(
      'run_id', (
        select payload #>> '{run,id}'
        from native_worker_results where name = 'poll_begin'
      ),
      'lease_token', 'a8600000-0000-4000-8000-000000000002',
      'job_id', 'a8300000-0000-4000-8000-000000000001',
      'outcome', 'failed',
      'error_code', 'provider_poll_http_503'
    )::text
  ),
  '55000',
  'background_worker_active_lease_required',
  'provider polling cannot be recorded through a forged worker lease'
);

do $five_poll_failures$
declare
  run_id_value uuid;
  lease_token_value uuid;
  attempt integer;
begin
  select
    (payload #>> '{run,id}')::uuid,
    (payload #>> '{run,lease_token}')::uuid
  into run_id_value, lease_token_value
  from native_worker_results
  where name = 'poll_begin';

  for attempt in 1..5 loop
    perform public.system_record_generation_poll_outcome(
      jsonb_build_object(
        'run_id', run_id_value,
        'lease_token', lease_token_value,
        'job_id', 'a8300000-0000-4000-8000-000000000001',
        'outcome', 'failed',
        'error_code', 'provider_poll_http_503'
      )
    );
  end loop;
end;
$five_poll_failures$;

select is(
  (
    select provider_poll_attempt_count::text || ':' ||
      provider_poll_failure_count::text
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  '5:5',
  'five failures retain both total attempts and consecutive failures'
);
select ok(
  (
    select provider_last_polled_at is not null
      and provider_last_poll_succeeded_at is null
      and provider_next_poll_at > provider_last_polled_at
      and provider_last_poll_code = 'provider_poll_http_503'
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  'a transient provider failure receives bounded retry backoff and evidence'
);
select ok(
  (
    select provider_stalled_at is not null
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  'the fifth consecutive provider failure marks the job stalled'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox outbox
    where outbox.organization_id =
        'a8100000-0000-4000-8000-000000000001'
      and outbox.entity_type = 'generation_job'
      and outbox.entity_id =
        'a8300000-0000-4000-8000-000000000001'
  ),
  1,
  'the first stalled transition creates exactly one durable notification'
);

select lives_ok(
  format(
    'select public.system_record_generation_poll_outcome(%L::jsonb)',
    jsonb_build_object(
      'run_id', (
        select payload #>> '{run,id}'
        from native_worker_results where name = 'poll_begin'
      ),
      'lease_token', (
        select payload #>> '{run,lease_token}'
        from native_worker_results where name = 'poll_begin'
      ),
      'job_id', 'a8300000-0000-4000-8000-000000000001',
      'outcome', 'failed',
      'error_code', 'provider_poll_http_503'
    )::text
  ),
  'a stalled provider job may continue to receive evidence without a paid retry'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox outbox
    where outbox.organization_id =
        'a8100000-0000-4000-8000-000000000001'
      and outbox.entity_type = 'generation_job'
      and outbox.entity_id =
        'a8300000-0000-4000-8000-000000000001'
  ),
  1,
  'additional failures cannot duplicate the stalled notification'
);

insert into native_worker_results (name, payload)
select
  'poll_recovered',
  public.system_record_generation_poll_outcome(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'job_id', 'a8300000-0000-4000-8000-000000000001',
    'outcome', 'success_pending'
  ))
from native_worker_results begin_result
where begin_result.name = 'poll_begin';

select is(
  (
    select provider_poll_failure_count::text || ':' ||
      (provider_stalled_at is null)::text
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  '0:true',
  'successful provider contact clears consecutive failures and a recent stall'
);
select ok(
  (
    select provider_last_poll_succeeded_at = provider_last_polled_at
      and provider_next_poll_at > provider_last_polled_at
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  'a successful pending response schedules the next provider poll'
);

-- The provider poll RPC records watchdog state only.  The existing generation
-- state machine remains the sole authority that makes a provider result
-- terminal; the terminal poll acknowledgement then removes it from the due
-- queue without starting another paid provider task.
select lives_ok(
  $$select public.system_update_real_generation(jsonb_build_object(
    'job_id', 'a8300000-0000-4000-8000-000000000001',
    'status', 'failed',
    'provider_task_id', 'runway_native_primary-job',
    'failure_code', 'provider_task_failed'
  ))$$,
  'the existing generation state machine persists the terminal provider result'
);

insert into native_worker_results (name, payload)
select
  'poll_terminal',
  public.system_record_generation_poll_outcome(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'job_id', 'a8300000-0000-4000-8000-000000000001',
    'outcome', 'success_terminal'
  ))
from native_worker_results begin_result
where begin_result.name = 'poll_begin';

select ok(
  (
    select provider_next_poll_at is null
      and provider_poll_failure_count = 0
      and provider_stalled_at is null
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000001'
  ),
  'a terminal provider response permanently removes the job from polling'
);

insert into native_worker_results (name, payload)
select
  'aged_pending',
  public.system_record_generation_poll_outcome(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'job_id', 'a8300000-0000-4000-8000-000000000002',
    'outcome', 'success_pending'
  ))
from native_worker_results begin_result
where begin_result.name = 'poll_begin';

select ok(
  (
    select provider_stalled_at is not null
      and provider_poll_failure_count = 0
    from content_factory.generation_jobs
    where id = 'a8300000-0000-4000-8000-000000000002'
  ),
  'a successful poll cannot hide a provider job active for more than two hours'
);
select is(
  (
    select count(*)::integer
    from content_factory.notification_outbox outbox
    where outbox.organization_id =
        'a8100000-0000-4000-8000-000000000002'
      and outbox.entity_type = 'generation_job'
      and outbox.entity_id =
        'a8300000-0000-4000-8000-000000000002'
  ),
  1,
  'the wall-clock watchdog also creates one durable stalled notification'
);

select throws_ok(
  $$select public.system_background_worker_health(
    '{"organization_id":"a8100000-0000-4000-8000-000000000001"}'::jsonb
  )$$,
  '22023',
  'background_worker_health_payload_invalid',
  'global health accepts only the intentionally empty payload'
);
insert into native_worker_results (name, payload)
values (
  'system_health',
  public.system_background_worker_health('{}'::jsonb)
);
select is(
  (select payload #>> '{generation,stalled}'
   from native_worker_results where name = 'system_health'),
  '1',
  'system health reports the single currently stalled provider job globally'
);
select is(
  (select payload #>> '{worker,running}'
   from native_worker_results where name = 'system_health'),
  'true',
  'system health reports the currently leased worker run'
);

insert into native_worker_results (name, payload)
select
  'poll_finish',
  public.system_finish_background_worker(jsonb_build_object(
    'run_id', begin_result.payload #>> '{run,id}',
    'lease_token', begin_result.payload #>> '{run,lease_token}',
    'status', 'completed',
    'summary', jsonb_build_object(
      'source', 'pgtap',
      'polls', 9,
      'stalled', 2
    )
  ))
from native_worker_results begin_result
where begin_result.name = 'poll_begin';

-- Exercise the organization health RPC under the same role used by PostgREST.
do $authenticated_claims$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'a8000000-0000-4000-8000-000000000001',
    true
  );
end;
$authenticated_claims$;
set local role authenticated;

select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001'
  )) ->> 'organization_id',
  'a8100000-0000-4000-8000-000000000001',
  'an active owner receives health only for the requested organization'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,stalled}',
  '0',
  'organization health excludes the stalled job belonging to another tenant'
);

select set_config(
  'request.jwt.claim.sub',
  'a8000000-0000-4000-8000-000000000002',
  true
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001'
  )) ->> 'organization_id',
  'a8100000-0000-4000-8000-000000000001',
  'an active administrator may inspect organization operational health'
);

select set_config(
  'request.jwt.claim.sub',
  'a8000000-0000-4000-8000-000000000004',
  true
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000002'
  )) #>> '{generation,stalled}',
  '1',
  'the other owner sees the stalled job inside that organization only'
);

select set_config(
  'request.jwt.claim.sub',
  'a8000000-0000-4000-8000-000000000003',
  true
);
select throws_ok(
  $$select public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001'
  ))$$,
  '42501',
  'role_not_allowed',
  'an operator cannot inspect organization-wide operational health'
);

select set_config(
  'request.jwt.claim.sub',
  'a8000000-0000-4000-8000-000000000001',
  true
);
select throws_ok(
  $$select public.creator_operational_health(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000002'
  ))$$,
  '42501',
  'active_membership_required',
  'a manager cannot inspect another organization health scope'
);

select * from finish();
rollback;
