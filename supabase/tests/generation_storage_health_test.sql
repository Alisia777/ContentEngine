begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(31);

create or replace function pg_temp.grant_generation_health_training_gate(
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
    left('generation-health:' || p_key_prefix || ':final-exam', 180)
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

create or replace function pg_temp.create_generation_health_job(
  p_job_id uuid,
  p_batch_id uuid,
  p_organization_id uuid,
  p_product_id uuid,
  p_actor_id uuid,
  p_status text,
  p_suffix text,
  p_created_at timestamptz,
  p_next_poll_at timestamptz default null,
  p_stalled_at timestamptz default null
)
returns void
language plpgsql
set search_path = ''
as $fixture$
declare
  actual_cost_value bigint := case
    when p_status in ('submitted', 'processing') then 25
    else 0
  end;
  output_value jsonb := case
    when p_status in ('submitted', 'processing') then jsonb_build_object(
      'provider_task_id', 'runway_health_' || p_suffix,
      'submitted_at', p_created_at,
      'actual_cost_minor', 25,
      'currency', 'USD'
    )
    else '{}'::jsonb
  end;
begin
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
    p_actor_id,
    'Generation health ' || p_suffix,
    'real',
    true,
    'processing',
    1,
    0,
    jsonb_build_object(
      'job_id', p_job_id,
      'review_task_id', p_job_id,
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
    encode(extensions.digest('generation-health-batch:' || p_suffix, 'sha256'), 'hex'),
    'generation-health-batch-' || p_suffix,
    'runway', 'gen4_turbo', 5, false, 25, 25, 'USD',
    p_created_at, p_created_at
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal,
    requested_by, assigned_to, mode, provider, allow_real_spend,
    estimated_cost_minor, actual_cost_minor, status,
    input, output, request_hash, idempotency_key,
    provider_next_poll_at, provider_stalled_at,
    created_at, updated_at
  ) values (
    p_job_id,
    p_organization_id,
    p_product_id,
    p_batch_id,
    1,
    p_actor_id,
    p_actor_id,
    'real',
    'runway',
    true,
    25,
    actual_cost_value,
    p_status,
    jsonb_build_object(
      'sku', 'GENERATION-HEALTH',
      'product_name', 'Generation health fixture',
      'prompt_text', 'A safe five second product video.',
      'format', '9:16',
      'ratio', '720:1280',
      'audio', false,
      'input_object_name',
        p_organization_id::text || '/' || p_actor_id::text ||
          '/uploads/generation-health.webp',
      'output_object_name',
        p_organization_id::text || '/' || p_actor_id::text ||
          '/generated/' || p_job_id::text || '.mp4',
      'review_task_id', p_job_id,
      'provider', 'runway',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'platform', 'wildberries',
      'destination_ref', 'wb-generation-health-' || p_suffix,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'billing', jsonb_build_object(
        'currency', 'USD',
        'estimated_cost_minor', 25,
        'estimated_credits', 25
      )
    ),
    output_value,
    encode(extensions.digest('generation-health-job:' || p_suffix, 'sha256'), 'hex'),
    'generation-health-job-' || p_suffix,
    p_next_poll_at,
    p_stalled_at,
    p_created_at,
    p_created_at
  );
end;
$fixture$;

select has_function(
  'public',
  'creator_operational_health',
  array['jsonb'],
  'organization operational health RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_operational_health(jsonb)',
    'execute'
  ),
  'authenticated managers may execute operational health'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.creator_operational_health(jsonb)',
    'execute'
  ),
  'anonymous callers cannot inspect operational health'
);
select ok(
  position(
    'array[''owner'', ''admin'']'
    in pg_get_functiondef(
      'content_factory_private.creator_operational_health_storage_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'creator_operational_health_storage_v1(p_payload)'
    in pg_get_functiondef(
      'public.creator_operational_health(jsonb)'::regprocedure
    )
  ) > 0,
  'operational health retains the owner and administrator role boundary'
);
select ok(
  position(
    'media.organization_id = organization_id_value'
    in pg_get_functiondef(
      'content_factory_private.creator_operational_health_storage_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'job.organization_id = organization_id_value'
    in pg_get_functiondef(
      'content_factory_private.creator_operational_health_storage_v1(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'evidence.organization_id = organization_id_value'
    in pg_get_functiondef(
      'public.creator_operational_health(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'reservation.organization_id = organization_id_value'
    in pg_get_functiondef(
      'public.creator_operational_health(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'cleanup.organization_id = organization_id_value'
    in pg_get_functiondef(
      'public.creator_operational_health(jsonb)'::regprocedure
    )
  ) > 0,
  'generation, registered storage, evidence, reservations and cleanup are tenant scoped'
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
    'b8000000-0000-4000-8000-000000000001',
    'generation-health-owner@example.test',
    'Generation Health Owner'
  ),
  (
    'b8000000-0000-4000-8000-000000000002',
    'generation-health-admin@example.test',
    'Generation Health Admin'
  ),
  (
    'b8000000-0000-4000-8000-000000000003',
    'generation-health-operator@example.test',
    'Generation Health Operator'
  ),
  (
    'b8000000-0000-4000-8000-000000000004',
    'generation-health-other-owner@example.test',
    'Generation Health Other Owner'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    'b8100000-0000-4000-8000-000000000001',
    'Generation Health Primary',
    'generation-health-primary',
    'active'
  ),
  (
    'b8100000-0000-4000-8000-000000000002',
    'Generation Health Other',
    'generation-health-other',
    'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  (
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000002',
    'admin', 'active'
  ),
  (
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000003',
    'operator', 'active'
  ),
  (
    'b8100000-0000-4000-8000-000000000002',
    'b8000000-0000-4000-8000-000000000004',
    'owner', 'active'
  );

insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
)
values
  (
    'b8100000-0000-4000-8000-000000000001', true,
    2500, 10000, 500, 'USD', 'Europe/Moscow', 1,
    'Generation health test policy.',
    'b8000000-0000-4000-8000-000000000001'
  ),
  (
    'b8100000-0000-4000-8000-000000000002', true,
    2500, 10000, 500, 'USD', 'Europe/Moscow', 1,
    'Other generation health policy.',
    'b8000000-0000-4000-8000-000000000004'
  );

select lives_ok(
  $$select pg_temp.grant_generation_health_training_gate(
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'generation-owner'
  )$$,
  'the owner fixture satisfies the training gate'
);
select lives_ok(
  $$select pg_temp.grant_generation_health_training_gate(
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000002',
    'generation-admin'
  )$$,
  'the administrator fixture satisfies the training gate'
);
select lives_ok(
  $$select pg_temp.grant_generation_health_training_gate(
    'b8100000-0000-4000-8000-000000000002',
    'b8000000-0000-4000-8000-000000000004',
    'generation-other-owner'
  )$$,
  'the other organization owner satisfies the training gate'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
)
values
  (
    'b8200000-0000-4000-8000-000000000001',
    'b8100000-0000-4000-8000-000000000001',
    'GEN-HEALTH-1', 'Generation health product', 'active',
    '{"brand":"ALTEA"}'::jsonb,
    'b8000000-0000-4000-8000-000000000001'
  ),
  (
    'b8200000-0000-4000-8000-000000000002',
    'b8100000-0000-4000-8000-000000000002',
    'GEN-HEALTH-2', 'Other generation health product', 'active',
    '{"brand":"ALTEA"}'::jsonb,
    'b8000000-0000-4000-8000-000000000004'
  );

select pg_temp.create_generation_health_job(
  'b8400000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000001',
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'queued', 'primary-queued', now() - interval '20 minutes'
);
select pg_temp.create_generation_health_job(
  'b8400000-0000-4000-8000-000000000002',
  'b8300000-0000-4000-8000-000000000002',
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'starting', 'primary-starting', now() - interval '15 minutes'
);
select pg_temp.create_generation_health_job(
  'b8400000-0000-4000-8000-000000000003',
  'b8300000-0000-4000-8000-000000000003',
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'submitted', 'primary-submitted', now() - interval '10 minutes',
  now() - interval '5 minutes'
);
select pg_temp.create_generation_health_job(
  'b8400000-0000-4000-8000-000000000004',
  'b8300000-0000-4000-8000-000000000004',
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'processing', 'primary-processing', now() - interval '5 minutes',
  now() + interval '5 minutes', now() - interval '2 minutes'
);
select pg_temp.create_generation_health_job(
  'b8400000-0000-4000-8000-000000000005',
  'b8300000-0000-4000-8000-000000000005',
  'b8100000-0000-4000-8000-000000000002',
  'b8200000-0000-4000-8000-000000000002',
  'b8000000-0000-4000-8000-000000000004',
  'queued', 'other-queued', now() - interval '1 hour'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values
  (
    'b8600000-0000-4000-8000-000000000001',
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'b8200000-0000-4000-8000-000000000001',
    'contentengine-private',
    'b8100000-0000-4000-8000-000000000001/b8000000-0000-4000-8000-000000000001/health/ready.webp',
    'image/webp', 1000, repeat('a', 64), 'ready', '{}'::jsonb,
    'generation-health-media-ready'
  ),
  (
    'b8600000-0000-4000-8000-000000000002',
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'b8200000-0000-4000-8000-000000000001',
    'contentengine-private',
    'b8100000-0000-4000-8000-000000000001/b8000000-0000-4000-8000-000000000001/health/archived.webp',
    'image/webp', 2000, repeat('b', 64), 'archived', '{}'::jsonb,
    'generation-health-media-archived'
  ),
  (
    'b8600000-0000-4000-8000-000000000003',
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'b8200000-0000-4000-8000-000000000001',
    'contentengine-private',
    'b8100000-0000-4000-8000-000000000001/b8000000-0000-4000-8000-000000000001/health/uploading.webp',
    'image/webp', 3000, repeat('c', 64), 'uploading', '{}'::jsonb,
    'generation-health-media-uploading'
  ),
  (
    'b8600000-0000-4000-8000-000000000004',
    'b8100000-0000-4000-8000-000000000001',
    'b8000000-0000-4000-8000-000000000001',
    'b8200000-0000-4000-8000-000000000001',
    'contentengine-private',
    'b8100000-0000-4000-8000-000000000001/b8000000-0000-4000-8000-000000000001/health/deleted.webp',
    'image/webp', 4000, repeat('d', 64), 'deleted', '{}'::jsonb,
    'generation-health-media-deleted'
  ),
  (
    'b8600000-0000-4000-8000-000000000005',
    'b8100000-0000-4000-8000-000000000002',
    'b8000000-0000-4000-8000-000000000004',
    'b8200000-0000-4000-8000-000000000002',
    'contentengine-private',
    'b8100000-0000-4000-8000-000000000002/b8000000-0000-4000-8000-000000000004/health/other.webp',
    'image/webp', 9000, repeat('e', 64), 'ready', '{}'::jsonb,
    'generation-health-media-other'
  );

do $authenticated_claims$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'b8000000-0000-4000-8000-000000000001',
    true
  );
end;
$authenticated_claims$;
set local role authenticated;

select ok(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) ?& array[
    'ok', 'organization_id', 'scheduler', 'worker',
    'generation', 'content_review', 'storage'
  ],
  'generation and storage extend rather than replace the health response'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,queued}',
  '1',
  'queued generation count is organization scoped'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,starting}',
  '1',
  'starting generation count is reported'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,submitted}',
  '1',
  'submitted generation count is reported'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,processing}',
  '1',
  'processing generation count is reported'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,active}',
  '2',
  'legacy active semantics remain submitted plus processing'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,due}',
  '1',
  'legacy due semantics remain eligible provider polls'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{generation,stalled}',
  '1',
  'legacy stalled semantics remain durable provider stalls'
);
select ok(
  (
    public.creator_operational_health(jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001'
    )) #>> '{generation,oldest_active_age_seconds}'
  )::bigint between 590 and 900,
  'oldest active age uses the oldest submitted or processing job'
);
select ok(
  (
    public.creator_operational_health(jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001'
    )) #>> '{generation,oldest_queued_age_seconds}'
  )::bigint between 1190 and 1500,
  'oldest queued age is reported in seconds'
);
select ok(
  (
    public.creator_operational_health(jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001'
    )) #>> '{generation,oldest_starting_age_seconds}'
  )::bigint between 890 and 1200,
  'oldest starting age is reported in seconds'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{storage,registered_count}',
  '3',
  'registered storage counts only quota-consuming states'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{storage,registered_bytes}',
  '6000',
  'registered storage bytes exclude deleted registrations and other tenants'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{storage,quota_bytes}',
  '107374182400',
  'organization storage quota matches the authoritative registration guard'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) #>> '{storage,remaining_bytes}',
  '107216890000',
  'remaining storage subtracts media and three active generation reservations'
);
select is(
  (
    public.creator_operational_health(jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001'
    )) #>> '{storage,utilization_percent}'
  )::numeric,
  0.15::numeric,
  'combined media and reservation utilization is a bounded two-decimal percentage'
);

select set_config(
  'request.jwt.claim.sub',
  'b8000000-0000-4000-8000-000000000002',
  true
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  )) ->> 'organization_id',
  'b8100000-0000-4000-8000-000000000001',
  'an active administrator may inspect organization operational health'
);

select set_config(
  'request.jwt.claim.sub',
  'b8000000-0000-4000-8000-000000000004',
  true
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000002'
  )) #>> '{generation,queued}',
  '1',
  'the other owner sees only that tenant generation queue'
);
select is(
  public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000002'
  )) #>> '{storage,registered_bytes}',
  '9000',
  'the other owner sees only that tenant registered storage'
);

select set_config(
  'request.jwt.claim.sub',
  'b8000000-0000-4000-8000-000000000003',
  true
);
select throws_ok(
  $$select public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001'
  ))$$,
  '42501',
  'role_not_allowed',
  'an operator cannot inspect organization-wide health'
);

select set_config(
  'request.jwt.claim.sub',
  'b8000000-0000-4000-8000-000000000001',
  true
);
select throws_ok(
  $$select public.creator_operational_health(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000002'
  ))$$,
  '42501',
  'active_membership_required',
  'an owner cannot inspect another organization health scope'
);

reset role;

select is(
  (
    select count(*)
    from content_factory.media_objects media
    where media.organization_id = 'b8100000-0000-4000-8000-000000000001'
  ),
  4::bigint,
  'health reads do not delete or rewrite media registrations'
);
select is(
  (
    select count(*)
    from content_factory.generation_jobs job
    where job.organization_id = 'b8100000-0000-4000-8000-000000000001'
  ),
  4::bigint,
  'health reads do not retry or replace generation jobs'
);

select * from finish();
rollback;
