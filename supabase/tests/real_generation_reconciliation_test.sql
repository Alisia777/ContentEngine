begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

create or replace function pg_temp.create_starting_real_job(
  p_job_id uuid,
  p_batch_id uuid,
  p_task_id uuid,
  p_organization_id uuid,
  p_product_id uuid,
  p_requested_by uuid,
  p_assigned_to uuid,
  p_key_suffix text,
  p_starting_at timestamptz default now() - interval '30 seconds'
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
     or p_starting_at is null then
    raise exception using
      errcode = '22023',
      message = 'real_generation_reconciliation_fixture_invalid';
  end if;

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name,
    mode, allow_real_spend, status, total_requested, total_created,
    input, request_hash, idempotency_key,
    provider, model, duration_seconds, audio,
    estimated_cost_minor, estimated_credits, currency
  ) values (
    p_batch_id,
    p_organization_id,
    p_product_id,
    p_requested_by,
    left('Reconciliation fixture ' || p_key_suffix, 180),
    'real',
    true,
    'starting',
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
    encode(
      extensions.digest('batch:' || p_key_suffix, 'sha256'),
      'hex'
    ),
    'reconcile-batch-' || p_key_suffix,
    'runway',
    'gen4_turbo',
    5,
    false,
    25,
    25,
    'USD'
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key
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
    0,
    'starting',
    jsonb_build_object(
      'sku', 'RECONCILIATION-SKU',
      'product_name', 'Reconciliation product',
      'prompt_text', 'A safe five second product video.',
      'format', '9:16',
      'ratio', '720:1280',
      'audio', false,
      'input_object_name',
        p_organization_id::text || '/' || p_requested_by::text ||
          '/uploads/reconciliation.webp',
      'output_object_name',
        p_organization_id::text || '/' || p_assigned_to::text ||
          '/generated/' || p_job_id::text || '.mp4',
      'review_task_id', p_task_id,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', 'wildberries',
      'destination_ref', 'wb-reconciliation-fixture',
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    jsonb_build_object('starting_at', p_starting_at),
    encode(
      extensions.digest('job:' || p_key_suffix, 'sha256'),
      'hex'
    ),
    'reconcile-job-' || p_key_suffix
  );

  insert into content_factory.creator_tasks (
    id, organization_id, assignee_id, created_by, product_id,
    generation_job_id, task_type, title, instructions,
    status, priority, payout_minor, result, idempotency_key
  ) values (
    p_task_id,
    p_organization_id,
    p_assigned_to,
    p_requested_by,
    p_product_id,
    p_job_id,
    'video_review',
    'Review reconciliation fixture ' || p_key_suffix,
    'Review only after the paid generation reaches a reviewable state.',
    'blocked',
    2,
    1200,
    jsonb_build_object(
      'generation_status', 'starting',
      'review_required', true,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'audio', false,
      'estimated_cost_minor', 25,
      'estimated_credits', 25,
      'currency', 'USD'
    ),
    'reconcile-task-' || p_key_suffix
  );
end;
$fixture$;

-- TEST-ONLY refreshed-course gate. Production authorization accepts only a
-- completed server-style attempt whose question counts match the active module
-- and whose idempotency key is namespaced as course-check:.
create or replace function pg_temp.grant_refreshed_course_gate(
  p_organization_id uuid,
  p_profile_id uuid,
  p_key_prefix text
)
returns void
language plpgsql
set search_path = ''
as $course_gate_fixture$
#variable_conflict use_variable
declare
  module_row record;
  attempt_id_value uuid;
  answers_value jsonb;
begin
  if p_organization_id is null
     or p_profile_id is null
     or p_key_prefix !~ '^[a-z0-9_-]{4,80}$' then
    raise exception using
      errcode = '22023',
      message = 'test_course_gate_fixture_invalid';
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
        message = 'test_course_gate_fixture_invalid';
    end if;

    insert into content_factory.training_attempts (
      organization_id,
      profile_id,
      module_code,
      status,
      score,
      correct_count,
      answered_count,
      question_count,
      passed,
      answers,
      request_hash,
      idempotency_key
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
    on conflict (organization_id, profile_id, idempotency_key) do update set
      module_code = excluded.module_code,
      status = excluded.status,
      score = excluded.score,
      correct_count = excluded.correct_count,
      answered_count = excluded.answered_count,
      question_count = excluded.question_count,
      passed = excluded.passed,
      answers = excluded.answers,
      request_hash = excluded.request_hash,
      completed_at = now()
    returning id into attempt_id_value;

    insert into content_factory.training_certifications (
      organization_id,
      profile_id,
      module_code,
      attempt_id,
      status
    ) values (
      p_organization_id,
      p_profile_id,
      module_row.code,
      attempt_id_value,
      'passed'
    )
    on conflict on constraint training_certifications_org_profile_module_uq
    do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;
  end loop;
end;
$course_gate_fixture$;

select no_plan();

select ok(
  has_function_privilege(
    'service_role',
    'public.system_mark_real_generation_reconciliation_required(jsonb)',
    'execute'
  ),
  'service role may mark an ambiguous paid provider submission'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_mark_real_generation_reconciliation_required(jsonb)',
    'execute'
  ),
  'authenticated sessions cannot mark system reconciliation state'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_reconcile_real_generation(jsonb)',
    'execute'
  ),
  'service role may persist a verified manual reconciliation'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_reconcile_real_generation(jsonb)',
    'execute'
  ),
  'authenticated sessions cannot bypass the reconciliation verifier'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_real_generation_reconciliation_context(jsonb)',
    'execute'
  ),
  'authenticated managers may request safe reconciliation context'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.creator_real_generation_reconciliation_context(jsonb)',
    'execute'
  ),
  'anonymous sessions cannot inspect reconciliation context'
);
select has_trigger(
  'content_factory',
  'generation_jobs',
  'a_generation_jobs_reconciliation_freeze_guard',
  'paid generation jobs have an authoritative reconciliation freeze trigger'
);
select has_trigger(
  'content_factory',
  'generation_jobs',
  'b_generation_jobs_reconciliation_transition_guard',
  'unresolved paid jobs have an authoritative transition guard'
);
select has_index(
  'content_factory',
  'generation_jobs',
  'generation_jobs_reconciliation_freeze_idx',
  'unresolved organization freezes have a bounded lookup index'
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
  extensions.crypt(
    'test-only-password',
    extensions.gen_salt('bf')
  ),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name),
  now(),
  now()
from (values
  (
    '97000000-0000-4000-8000-000000000001',
    'reconcile-owner@example.test',
    'Reconciliation Owner'
  ),
  (
    '97000000-0000-4000-8000-000000000002',
    'reconcile-admin@example.test',
    'Reconciliation Admin'
  ),
  (
    '97000000-0000-4000-8000-000000000003',
    'reconcile-operator@example.test',
    'Reconciliation Operator'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    '97100000-0000-4000-8000-000000000001',
    'Generation Reconciliation',
    'generation-reconciliation',
    'active'
  ),
  (
    '97100000-0000-4000-8000-000000000002',
    'Generation Reconciliation Other',
    'generation-reconciliation-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'owner',
    'active'
  ),
  (
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'admin',
    'active'
  ),
  (
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000003',
    'operator',
    'active'
  ),
  (
    '97100000-0000-4000-8000-000000000002',
    '97000000-0000-4000-8000-000000000001',
    'owner',
    'active'
  );

do $training_gate_fixture$
declare
  attempt_id_value uuid;
  question_count_value integer;
begin
  select module.question_count
    into question_count_value
  from content_factory.training_modules module
  where module.code = 'operator_final_exam'
    and module.module_type = 'exam'
    and module.is_active;

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'operator_final_exam',
    'completed',
    1,
    question_count_value,
    question_count_value,
    question_count_value,
    true,
    '{}'::jsonb,
    content_factory_private.json_hash(jsonb_build_object(
      'profile_id', '97000000-0000-4000-8000-000000000001',
      'exam', 'operator_final_exam'
    )),
    'reconciliation-owner-final-exam-0001'
  )
  returning id into attempt_id_value;

  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'operator_final_exam',
    attempt_id_value,
    'passed'
  );

  perform pg_temp.grant_refreshed_course_gate(
    '97100000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'reconciliation-owner'
  );
end;
$training_gate_fixture$;

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    '97200000-0000-4000-8000-000000000001',
    '97100000-0000-4000-8000-000000000001',
    'RECONCILIATION-SKU',
    'Reconciliation product',
    'active',
    '{"brand":"ALTEA"}'::jsonb,
    '97000000-0000-4000-8000-000000000001'
  ),
  (
    '97200000-0000-4000-8000-000000000002',
    '97100000-0000-4000-8000-000000000002',
    'RECONCILIATION-SKU-OTHER',
    'Other organization product',
    'active',
    '{"brand":"ALTEA"}'::jsonb,
    '97000000-0000-4000-8000-000000000001'
  );

select lives_ok(
  $$select pg_temp.create_starting_real_job(
    '97300000-0000-4000-8000-000000000002',
    '97300000-0000-4000-8000-000000000001',
    '97300000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000003',
    'first-job'
  )$$,
  'a valid starting paid job can be created before a freeze'
);

select lives_ok(
  $$select pg_temp.create_starting_real_job(
    '97500000-0000-4000-8000-000000000002',
    '97500000-0000-4000-8000-000000000001',
    '97500000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'legacy-job'
  )$$,
  'a second pre-incident paid job models a legacy concurrent start'
);

create temporary table reconciliation_test_context (
  first_mark jsonb,
  first_mark_replay jsonb,
  legacy_mark jsonb,
  no_submission_payload jsonb,
  no_submission_result jsonb,
  legacy_no_submission_payload jsonb,
  legacy_no_submission_result jsonb,
  second_mark jsonb,
  attach_payload jsonb,
  attach_result jsonb
) on commit drop;

insert into reconciliation_test_context (first_mark)
values (public.system_mark_real_generation_reconciliation_required(
  jsonb_build_object(
    'job_id', '97300000-0000-4000-8000-000000000002',
    'reason_code', 'provider_create_timeout'
  )
));

select is(
  (select first_mark ->> 'marked' from reconciliation_test_context),
  'true',
  'an ambiguous provider create is durably marked'
);
select matches(
  (
    select first_mark #>> '{job,reconciliation_incident_id}'
    from reconciliation_test_context
  ),
  '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
  'the mark assigns a durable incident id'
);
select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97300000-0000-4000-8000-000000000002'
  ),
  'starting:0:true',
  'marking preserves zero cost and the non-terminal starting state'
);
select is(
  (
    select status || ':' || (result ->> 'generation_submission_state')
    from content_factory.creator_tasks
    where id = '97300000-0000-4000-8000-000000000003'
  ),
  'blocked:unknown',
  'the linked human review stays blocked while submission is unknown'
);
select is(
  (
    select properties ->> 'automatic_provider_retry_allowed'
    from content_factory.factory_events
    where event_name = 'real_generation_reconciliation_required'
      and entity_id = '97300000-0000-4000-8000-000000000002'
  ),
  'false',
  'the incident audit record explicitly forbids automatic provider retry'
);

update reconciliation_test_context
set first_mark_replay =
  public.system_mark_real_generation_reconciliation_required(
    jsonb_build_object(
      'job_id', '97300000-0000-4000-8000-000000000002',
      'reason_code', 'provider_create_timeout'
    )
  );

select is(
  (
    select first_mark_replay ->> 'marked'
    from reconciliation_test_context
  ),
  'false',
  'repeating the same mark is idempotent'
);
select is(
  (
    select first_mark_replay #>> '{job,reconciliation_incident_id}'
    from reconciliation_test_context
  ),
  (
    select first_mark #>> '{job,reconciliation_incident_id}'
    from reconciliation_test_context
  ),
  'an idempotent mark preserves the original incident id'
);

select throws_ok(
  $$select public.system_update_real_generation(jsonb_build_object(
    'job_id', '97300000-0000-4000-8000-000000000002',
    'status', 'submitted',
    'provider_task_id', 'runway_task_bypass_001'
  ))$$,
  '55000',
  'real_generation_reconciliation_required',
  'the legacy provider updater cannot bypass an unresolved incident'
);
select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      coalesce(output ->> 'provider_task_id', 'none') || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97300000-0000-4000-8000-000000000002'
  ),
  'starting:0:none:true',
  'a rejected legacy transition leaves the job reconcilable and frozen'
);

update content_factory.generation_jobs
set output = jsonb_set(
  output,
  '{reconciliation_required}',
  to_jsonb('false'::text)
)
where id = '97300000-0000-4000-8000-000000000002';

select throws_ok(
  $$select pg_temp.create_starting_real_job(
    '97400000-0000-4000-8000-000000000002',
    '97400000-0000-4000-8000-000000000001',
    '97400000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'second-job'
  )$$,
  '55000',
  'real_generation_reconciliation_required',
  'a malformed string false marker still freezes a fresh paid insert'
);
select throws_ok(
  $$update content_factory.generation_jobs
    set output = jsonb_set(
      output,
      '{reconciliation_required}',
      'false'::jsonb
    )
    where id = '97300000-0000-4000-8000-000000000002'$$,
  '55000',
  'real_generation_reconciliation_required',
  'a malformed unresolved marker cannot be cleared by a direct update'
);
select is(
  (
    select jsonb_typeof(output -> 'reconciliation_required') || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97300000-0000-4000-8000-000000000002'
  ),
  'string:false',
  'the rejected direct clear preserves the fail-closed malformed marker'
);

update reconciliation_test_context
set legacy_mark =
  public.system_mark_real_generation_reconciliation_required(
    jsonb_build_object(
      'job_id', '97500000-0000-4000-8000-000000000002',
      'reason_code', 'provider_create_http_unknown'
    )
  );

select is(
  (
    select legacy_mark ->> 'marked'
    from reconciliation_test_context
  ),
  'true',
  'a second legacy ambiguous job receives its own unresolved incident'
);

select throws_ok(
  $$select pg_temp.create_starting_real_job(
    '97400000-0000-4000-8000-000000000002',
    '97400000-0000-4000-8000-000000000001',
    '97400000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'second-job'
  )$$,
  '55000',
  'real_generation_reconciliation_required',
  'an unresolved incident freezes every new paid job in the organization'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_jobs
    where id = '97400000-0000-4000-8000-000000000002'
  ),
  0,
  'a rejected paid job leaves no partial generation row'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_batches
    where id = '97400000-0000-4000-8000-000000000001'
  ),
  0,
  'a rejected paid job leaves no partial generation batch'
);
select is(
  (
    select count(*)::integer
    from content_factory.creator_tasks
    where id = '97400000-0000-4000-8000-000000000003'
  ),
  0,
  'a rejected paid job leaves no partial review task'
);

select lives_ok(
  $$select pg_temp.create_starting_real_job(
    '97600000-0000-4000-8000-000000000002',
    '97600000-0000-4000-8000-000000000001',
    '97600000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000002',
    '97200000-0000-4000-8000-000000000002',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    'other-org'
  )$$,
  'an unresolved incident in one organization does not freeze another'
);

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '97000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select is(
  public.creator_real_generation_status(jsonb_build_object(
    'organization_id', '97100000-0000-4000-8000-000000000001',
    'job_id', '97300000-0000-4000-8000-000000000002'
  )) #>> '{job,reconciliation_required}',
  'true',
  'status surfaces a malformed fail-closed marker as unresolved'
);
select is(
  public.creator_real_generation_status(jsonb_build_object(
    'organization_id', '97100000-0000-4000-8000-000000000001',
    'job_id', '97300000-0000-4000-8000-000000000002'
  )) #>> '{job,can_reconcile}',
  'true',
  'an owner can recover a malformed unresolved marker'
);

select is(
  public.creator_real_generation_reconciliation_context(
    jsonb_build_object(
      'organization_id', '97100000-0000-4000-8000-000000000001',
      'job_id', '97300000-0000-4000-8000-000000000002'
    )
  ) ->> 'actor_role',
  'owner',
  'an active owner receives safe context for malformed unresolved state'
);

update content_factory.generation_jobs
set output = jsonb_set(
  output,
  '{reconciliation_required_at}',
  to_jsonb(now() - interval '3 minutes')
)
where id = '97300000-0000-4000-8000-000000000002';

update reconciliation_test_context
set no_submission_payload = jsonb_build_object(
  'job_id', '97300000-0000-4000-8000-000000000002',
  'actor_id', '97000000-0000-4000-8000-000000000001',
  'incident_id', (
    first_mark #>> '{job,reconciliation_incident_id}'
  ),
  'idempotency_key', 'reconcile-no-submission-0001',
  'resolution', 'confirm_no_submission',
  'evidence_reference', 'runway-dashboard:no-task:0001',
  'reason',
    'Runway dashboard and account activity show that no task was submitted.'
);

update reconciliation_test_context
set no_submission_result =
  public.system_reconcile_real_generation(no_submission_payload);

select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      (output ->> 'failure_code') || ':' ||
      (output ->> 'submission_state')
    from content_factory.generation_jobs
    where id = '97300000-0000-4000-8000-000000000002'
  ),
  'failed:0:provider_submission_not_found:confirmed_not_submitted',
  'reconciliation normalizes the malformed marker and closes at zero cost'
);
select is(
  (
    select status
    from content_factory.generation_batches
    where id = '97300000-0000-4000-8000-000000000001'
  ),
  'failed',
  'verified no-submission closes the generation batch'
);
select is(
  (
    select status || ':' || (result ->> 'review_required')
    from content_factory.creator_tasks
    where id = '97300000-0000-4000-8000-000000000003'
  ),
  'cancelled:false',
  'verified no-submission cancels the unreleasable review task'
);
select is(
  (
    select no_submission_result #>> '{job,reconciliation_resolution}'
    from reconciliation_test_context
  ),
  'confirm_no_submission',
  'the no-submission result records the exact resolution'
);
select is(
  (
    select public.system_reconcile_real_generation(
      no_submission_payload
    ) ->> 'replayed'
    from reconciliation_test_context
  ),
  'true',
  'an identical no-submission resolution replays idempotently'
);

select is(
  (
    select count(*)::integer
    from content_factory.generation_jobs
    where organization_id = '97100000-0000-4000-8000-000000000001'
      and mode = 'real'
      and allow_real_spend
      and output ? 'reconciliation_required'
      and output -> 'reconciliation_required'
        is distinct from 'false'::jsonb
  ),
  1,
  'resolving one of two legacy incidents leaves the other freeze active'
);
select throws_ok(
  $$select pg_temp.create_starting_real_job(
    '97400000-0000-4000-8000-000000000002',
    '97400000-0000-4000-8000-000000000001',
    '97400000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'second-job'
  )$$,
  '55000',
  'real_generation_reconciliation_required',
  'reconciling one legacy job cannot release another unresolved incident'
);

update content_factory.generation_jobs
set output = jsonb_set(
  output,
  '{reconciliation_required_at}',
  to_jsonb(now() - interval '3 minutes')
)
where id = '97500000-0000-4000-8000-000000000002';

update reconciliation_test_context
set legacy_no_submission_payload = jsonb_build_object(
  'job_id', '97500000-0000-4000-8000-000000000002',
  'actor_id', '97000000-0000-4000-8000-000000000001',
  'incident_id', legacy_mark #>> '{job,reconciliation_incident_id}',
  'idempotency_key', 'reconcile-legacy-no-submission-0001',
  'resolution', 'confirm_no_submission',
  'evidence_reference', 'runway-dashboard:no-task:legacy-0001',
  'reason',
    'Runway account activity confirms the second legacy request was absent.'
);

update reconciliation_test_context
set legacy_no_submission_result =
  public.system_reconcile_real_generation(legacy_no_submission_payload);

select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97500000-0000-4000-8000-000000000002'
  ),
  'failed:0:false',
  'the second legacy incident must be reconciled independently'
);

select lives_ok(
  $$select pg_temp.create_starting_real_job(
    '97400000-0000-4000-8000-000000000002',
    '97400000-0000-4000-8000-000000000001',
    '97400000-0000-4000-8000-000000000003',
    '97100000-0000-4000-8000-000000000001',
    '97200000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000001',
    '97000000-0000-4000-8000-000000000002',
    'second-job'
  )$$,
  'resolving the incident lifts the organization spend freeze'
);

update reconciliation_test_context
set second_mark =
  public.system_mark_real_generation_reconciliation_required(
    jsonb_build_object(
      'job_id', '97400000-0000-4000-8000-000000000002',
      'reason_code', 'provider_create_response_unknown'
    )
  );

select throws_ok(
  $$select public.system_reconcile_real_generation(jsonb_build_object(
    'job_id', '97400000-0000-4000-8000-000000000002',
    'actor_id', '97000000-0000-4000-8000-000000000002',
    'incident_id', (
      select second_mark #>> '{job,reconciliation_incident_id}'
      from reconciliation_test_context
    ),
    'idempotency_key', 'reconcile-attach-too-early-0001',
    'resolution', 'attach_existing_task',
    'provider_task_id', 'runway_task_reconcile_001',
    'provider_task_created_at', (
      select (output ->> 'starting_at')::timestamptz -
        interval '5 minutes'
      from content_factory.generation_jobs
      where id = '97400000-0000-4000-8000-000000000002'
    ),
    'provider_status', 'RUNNING',
    'evidence_reference', 'runway-dashboard:task:0001',
    'reason',
      'The provider task exists but this deliberately supplied time is unsafe.'
  ))$$,
  '55000',
  'real_generation_reconciliation_task_time_mismatch',
  'an unrelated provider task outside the creation window cannot be attached'
);
select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      coalesce(output ->> 'provider_task_id', 'none') || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97400000-0000-4000-8000-000000000002'
  ),
  'starting:0:none:true',
  'a rejected attachment leaves the paid job frozen and uncharged'
);

update reconciliation_test_context
set attach_payload = jsonb_build_object(
  'job_id', '97400000-0000-4000-8000-000000000002',
  'actor_id', '97000000-0000-4000-8000-000000000002',
  'incident_id', second_mark #>> '{job,reconciliation_incident_id}',
  'idempotency_key', 'reconcile-attach-existing-0001',
  'resolution', 'attach_existing_task',
  'provider_task_id', 'runway_task_reconcile_001',
  'provider_task_created_at', (
    select (output ->> 'starting_at')::timestamptz
    from content_factory.generation_jobs
    where id = '97400000-0000-4000-8000-000000000002'
  ),
  'provider_status', 'RUNNING',
  'evidence_reference', 'runway-dashboard:task:0001',
  'reason',
    'Runway task details match the exact start window and account activity.'
);

update reconciliation_test_context
set attach_result =
  public.system_reconcile_real_generation(attach_payload);

select is(
  (
    select status || ':' || actual_cost_minor::text || ':' ||
      (output ->> 'provider_task_id') || ':' ||
      (output ->> 'submission_state') || ':' ||
      (output ->> 'reconciliation_required')
    from content_factory.generation_jobs
    where id = '97400000-0000-4000-8000-000000000002'
  ),
  'submitted:25:runway_task_reconcile_001:confirmed_submitted:false',
  'a time-bound verified provider task is attached with the fixed actual cost'
);
select is(
  (
    select status
    from content_factory.generation_batches
    where id = '97400000-0000-4000-8000-000000000001'
  ),
  'submitted',
  'attaching the existing provider task advances the batch'
);
select is(
  (
    select status || ':' || (result ->> 'generation_submission_state')
    from content_factory.creator_tasks
    where id = '97400000-0000-4000-8000-000000000003'
  ),
  'blocked:confirmed_submitted',
  'attachment keeps human review blocked until provider completion'
);
select is(
  (
    select public.system_reconcile_real_generation(
      attach_payload
    ) ->> 'replayed'
    from reconciliation_test_context
  ),
  'true',
  'an identical attachment resolution replays idempotently'
);
select throws_ok(
  $$select public.system_reconcile_real_generation(jsonb_build_object(
    'job_id', '97400000-0000-4000-8000-000000000002',
    'actor_id', '97000000-0000-4000-8000-000000000002',
    'incident_id', (
      select second_mark #>> '{job,reconciliation_incident_id}'
      from reconciliation_test_context
    ),
    'idempotency_key', 'reconcile-conflicting-resolution-0001',
    'resolution', 'confirm_no_submission',
    'evidence_reference', 'runway-dashboard:no-task:conflict',
    'reason',
      'A resolved provider task cannot later be changed to no submission.'
  ))$$,
  '23505',
  'real_generation_reconciliation_already_resolved',
  'a resolved incident cannot be changed to a conflicting outcome'
);
select is(
  (
    select properties ->> 'automatic_provider_retry_used'
    from content_factory.factory_events
    where event_name = 'real_generation_reconciled_existing_task'
      and entity_id = '97400000-0000-4000-8000-000000000002'
  ),
  'false',
  'successful reconciliation records that no automatic provider retry ran'
);

select * from finish();
rollback;
