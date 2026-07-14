begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(42);

select ok(
  has_function_privilege(
    'authenticated', 'public.creator_start_real_generation(jsonb)', 'execute'
  ),
  'authenticated may start a real generation'
);
select ok(
  not has_function_privilege(
    'anon', 'public.creator_start_real_generation(jsonb)', 'execute'
  ),
  'anon may not start a real generation'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_real_generation_status(jsonb)', 'execute'
  ),
  'authenticated may read an authorized real generation status'
);
select ok(
  not has_function_privilege(
    'anon', 'public.creator_real_generation_status(jsonb)', 'execute'
  ),
  'anon may not read a real generation status'
);
select ok(
  has_function_privilege(
    'service_role', 'public.system_update_real_generation(jsonb)', 'execute'
  ),
  'service_role may update provider state'
);
select ok(
  not has_function_privilege(
    'authenticated', 'public.system_update_real_generation(jsonb)', 'execute'
  ),
  'authenticated may not update provider state'
);
select ok(
  not has_function_privilege(
    'anon', 'public.system_update_real_generation(jsonb)', 'execute'
  ),
  'anon may not update provider state'
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
  ('81111111-1111-4111-8111-111111111111', 'real-owner@example.test', 'Real Owner'),
  ('81222222-2222-4222-8222-222222222222', 'real-reviewer@example.test', 'Real Reviewer'),
  ('81333333-3333-4333-8333-333333333333', 'real-operator@example.test', 'Real Operator'),
  ('81444444-4444-4444-8444-444444444444', 'real-producer@example.test', 'Real Producer'),
  ('81555555-5555-4555-8555-555555555555', 'real-viewer@example.test', 'Real Viewer'),
  ('81666666-6666-4666-8666-666666666666', 'uncertified-operator@example.test', 'Uncertified Operator')
) as fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  '80000000-0000-4000-8000-000000000001',
  'Paid Runway Test',
  'paid-runway-test',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('80000000-0000-4000-8000-000000000001', '81111111-1111-4111-8111-111111111111', 'owner', 'active'),
  ('80000000-0000-4000-8000-000000000001', '81222222-2222-4222-8222-222222222222', 'reviewer', 'active'),
  ('80000000-0000-4000-8000-000000000001', '81333333-3333-4333-8333-333333333333', 'operator', 'active'),
  ('80000000-0000-4000-8000-000000000001', '81444444-4444-4444-8444-444444444444', 'producer', 'active'),
  ('80000000-0000-4000-8000-000000000001', '81555555-5555-4555-8555-555555555555', 'viewer', 'active'),
  ('80000000-0000-4000-8000-000000000001', '81666666-6666-4666-8666-666666666666', 'operator', 'active');

with inserted_attempts as (
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  )
  select
    '80000000-0000-4000-8000-000000000001'::uuid,
    fixture.profile_id::uuid,
    'operator_final_exam',
    'completed', 1, 12, 12, 12, true, '{}'::jsonb,
    repeat(fixture.hash_character, 64),
    fixture.idempotency_key
  from (values
    ('81111111-1111-4111-8111-111111111111', 'a', 'real-owner-exam-0001'),
    ('81222222-2222-4222-8222-222222222222', 'b', 'real-reviewer-exam-0001'),
    ('81333333-3333-4333-8333-333333333333', 'c', 'real-operator-exam-0001'),
    ('81444444-4444-4444-8444-444444444444', 'd', 'real-producer-exam-0001'),
    ('81555555-5555-4555-8555-555555555555', 'e', 'real-viewer-exam-0001')
  ) as fixture(profile_id, hash_character, idempotency_key)
  returning id, organization_id, profile_id, module_code
)
insert into content_factory.training_certifications (
  organization_id, profile_id, module_code, attempt_id, status
)
select organization_id, profile_id, module_code, id, 'passed'
from inserted_attempts;

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  '82000000-0000-4000-8000-000000000001',
  '80000000-0000-4000-8000-000000000001',
  'REAL-SKU-1',
  'Runway product',
  'active',
  '81111111-1111-4111-8111-111111111111'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values (
  '83000000-0000-4000-8000-000000000001',
  '80000000-0000-4000-8000-000000000001',
  '81111111-1111-4111-8111-111111111111',
  '82000000-0000-4000-8000-000000000001',
  'contentengine-private',
  '80000000-0000-4000-8000-000000000001/81111111-1111-4111-8111-111111111111/uploads/runway-source.jpg',
  'image/jpeg',
  2048,
  repeat('a', 64),
  'ready',
  '{"kind":"product_photo","original_filename":"runway-source.jpg","rights_confirmed":true}'::jsonb,
  'paid-runway-source-0001'
);

create temporary table paid_runway_context (
  initial_response jsonb,
  reviewer_response jsonb,
  operator_response jsonb
) on commit drop;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '81111111-1111-4111-8111-111111111111',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-bad-spend-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'YES'
    ))
  $$,
  '42501',
  'real_generation_spend_confirmation_required',
  'paid generation requires the exact price-bearing confirmation'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-bad-count-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 2, 'format', '9:16', 'brief', 'A clean product turntable.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '22023',
  'real_generation_count_must_be_one',
  'a paid request is fixed at one video'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-bad-media-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
      'media_ids', '[]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '22023',
  'exact_one_product_media_required',
  'a paid request requires exactly one product media object'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '81555555-5555-4555-8555-555555555555',
    true
  );
end;
$$;
select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '80000000-0000-4000-8000-000000000001'
  )) #>> '{capabilities,real_generation}',
  'false',
  'bootstrap keeps real generation disabled for a certified viewer'
);
select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-viewer-denied-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '42501', 'role_not_allowed',
  'a certified viewer still cannot spend'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '81666666-6666-4666-8666-666666666666',
    true
  );
end;
$$;
select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-uncertified-denied-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '42501', 'final_exam_required',
  'an uncertified operator cannot spend'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '81111111-1111-4111-8111-111111111111',
    true
  );
end;
$$;

select is(
  public.creator_bootstrap(jsonb_build_object(
    'organization_id', '80000000-0000-4000-8000-000000000001'
  )) #>> '{capabilities,real_generation}',
  'true',
  'bootstrap advertises real generation only after role and exam gates pass'
);

insert into paid_runway_context (initial_response)
values (public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '80000000-0000-4000-8000-000000000001',
  'idempotency_key', 'real-success-path-0001',
  'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
  'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
  'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'wb-real-test',
  'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
  'duration_seconds', 5, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
)));

select is(
  (select initial_response #>> '{job,status}' from paid_runway_context),
  'queued',
  'valid paid request creates a queued job'
);
select is(
  (select initial_response #>> '{job,ratio}' from paid_runway_context),
  '720:1280',
  '9:16 maps to the exact Runway ratio'
);
select is(
  (
    select job.estimated_cost_minor::text || ':' || job.actual_cost_minor::text
    from content_factory.generation_jobs job
    where job.id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
  ),
  '25:0',
  'queued Runway job records 25 USD minor estimated and zero actual spend'
);
select ok(
  exists (
    select 1
    from content_factory.generation_batches batch
    where batch.id = (
      select (initial_response #>> '{batch,id}')::uuid from paid_runway_context
    )
      and batch.input ->> 'job_id' = (
        select initial_response #>> '{job,id}' from paid_runway_context
      )
      and batch.input #>> '{billing,currency}' = 'USD'
      and batch.input #>> '{billing,estimated_credits}' = '25'
  ),
  'batch stores the exact job id and fixed USD/credits metadata'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    where task.generation_job_id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
      and task.task_type = 'video_review'
      and task.status = 'blocked'
  ),
  'start creates exactly one blocked video review task'
);
select throws_ok(
  $$
    update content_factory.creator_tasks
    set status = 'in_progress'
    where generation_job_id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
  $$,
  '55000', 'real_generation_review_task_locked',
  'generic task actions cannot unblock an active paid generation review'
);
select is(
  public.creator_start_real_generation(jsonb_build_object(
    'organization_id', '80000000-0000-4000-8000-000000000001',
    'idempotency_key', 'real-success-path-0001',
    'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
    'count', 1, 'format', '9:16', 'brief', 'A clean product turntable.',
    'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
    'platform', 'wildberries', 'destination_ref', 'wb-real-test',
    'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
    'duration_seconds', 5, 'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
  ))::text,
  (select initial_response::text from paid_runway_context),
  'start is idempotent before quota evaluation'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-assignee-concurrency-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '1:1', 'brief', 'Second paid job.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '54000', 'real_generation_assignee_concurrency_exceeded',
  'one assignee cannot hold two paid generations concurrently'
);

update paid_runway_context
set reviewer_response = public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '80000000-0000-4000-8000-000000000001',
  'idempotency_key', 'real-org-concurrency-reviewer-0001',
  'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
  'count', 1, 'format', '1:1', 'brief', 'Reviewer-assigned job.',
  'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'wb-real-test',
  'assignee_id', '81222222-2222-4222-8222-222222222222',
  'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
  'duration_seconds', 5, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
));
update paid_runway_context
set operator_response = public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '80000000-0000-4000-8000-000000000001',
  'idempotency_key', 'real-org-concurrency-operator-0001',
  'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
  'count', 1, 'format', '16:9', 'brief', 'Operator-assigned job.',
  'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'wb-real-test',
  'assignee_id', '81333333-3333-4333-8333-333333333333',
  'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
  'duration_seconds', 5, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
));

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-org-concurrency-reject-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '1:1', 'brief', 'Fourth concurrent job.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'assignee_id', '81444444-4444-4444-8444-444444444444',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '54000', 'real_generation_organization_concurrency_exceeded',
  'organization concurrency is capped at three paid jobs'
);

select ok(
  (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select reviewer_response #>> '{job,id}' from paid_runway_context),
    'status', 'failed',
    'failure_code', 'provider_request_failed'
  )) #>> '{job,status}') = 'failed',
  'a pre-provider queued job can fail without a provider task id'
);
select ok(
  (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select operator_response #>> '{job,id}' from paid_runway_context),
    'status', 'failed',
    'failure_code', 'provider_request_failed'
  )) #>> '{job,status}') = 'failed',
  'queued cleanup frees a second organization concurrency slot'
);

select ok(
  (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
    'status', 'starting'
  )) ->> 'claimed')::boolean,
  'queued to starting atomically claims the paid provider call'
);
select ok(
  not (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
    'status', 'starting'
  )) ->> 'claimed')::boolean,
  'a duplicate starting claim cannot call the provider twice'
);

select throws_ok(
  $$
    select public.system_update_real_generation(jsonb_build_object(
      'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
      'status', 'succeeded',
      'provider_task_id', 'runway-task-001',
      'output_object_name', (select initial_response #>> '{job,output_object_name}' from paid_runway_context),
      'mime_type', 'video/mp4', 'size_bytes', 4096, 'sha256', repeat('b', 64)
    ))
  $$,
  '55000', 'real_generation_state_transition_invalid',
  'success cannot skip submitted and processing states'
);

select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
    'status', 'submitted', 'provider_task_id', 'runway-task-001'
  )) #>> '{job,status}',
  'submitted',
  'starting moves to submitted with one exact provider task id'
);

select throws_ok(
  $$
    select public.system_update_real_generation(jsonb_build_object(
      'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
      'status', 'processing', 'provider_task_id', 'runway-task-other'
    ))
  $$,
  '55000', 'real_generation_state_transition_invalid',
  'provider task id cannot change during polling'
);

select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
    'status', 'processing', 'provider_task_id', 'runway-task-001'
  )) #>> '{job,status}',
  'processing',
  'submitted moves to processing with the same task id'
);

insert into storage.objects (bucket_id, name, metadata, user_metadata)
select
  'contentengine-private',
  initial_response #>> '{job,output_object_name}',
  jsonb_build_object('size', 4096, 'mimetype', 'video/mp4'),
  jsonb_build_object('sha256', repeat('c', 64))
from paid_runway_context;

select throws_ok(
  $$
    select public.system_update_real_generation(jsonb_build_object(
      'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
      'status', 'succeeded', 'provider_task_id', 'runway-task-001',
      'output_object_name', (select initial_response #>> '{job,output_object_name}' from paid_runway_context),
      'mime_type', 'video/mp4', 'size_bytes', 4096, 'sha256', repeat('b', 64)
    ))
  $$,
  '22023', 'real_generation_storage_metadata_mismatch',
  'success rejects a Storage object with a mismatched SHA-256'
);

update storage.objects
set user_metadata = jsonb_build_object('sha256', repeat('b', 64))
where bucket_id = 'contentengine-private'
  and name = (select initial_response #>> '{job,output_object_name}' from paid_runway_context);

select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
    'status', 'succeeded', 'provider_task_id', 'runway-task-001',
    'output_object_name', (select initial_response #>> '{job,output_object_name}' from paid_runway_context),
    'mime_type', 'video/mp4', 'size_bytes', 4096, 'sha256', repeat('b', 64)
  )) #>> '{job,status}',
  'succeeded',
  'validated MP4 moves processing to succeeded'
);

select ok(
  exists (
    select 1
    from content_factory.media_objects media
    join content_factory.generation_jobs job
      on job.organization_id = media.organization_id
     and job.id::text = media.metadata ->> 'generation_job_id'
    where job.id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
      and media.status = 'ready'
      and media.mime_type = 'video/mp4'
      and media.sha256 = repeat('b', 64)
      and media.metadata ->> 'kind' = 'generated_video'
  ),
  'success registers the exact generated MP4 as ready media'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    where task.generation_job_id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
      and task.status = 'review'
      and task.result ->> 'generation_status' = 'succeeded'
  ),
  'success releases the video review task for human review'
);
select ok(
  exists (
    select 1
    from content_factory.generation_jobs job
    join content_factory.generation_batches batch
      on batch.organization_id = job.organization_id
     and batch.id = job.batch_id
    where job.id = (
      select (initial_response #>> '{job,id}')::uuid from paid_runway_context
    )
      and job.status = 'succeeded'
      and job.actual_cost_minor = 25
      and batch.status = 'succeeded'
      and batch.total_created = 1
  ),
  'job and batch complete together with the fixed actual cost'
);
select ok(
  (public.creator_real_generation_status(jsonb_build_object(
    'organization_id', '80000000-0000-4000-8000-000000000001',
    'job_id', (select initial_response #>> '{job,id}' from paid_runway_context)
  )) #>> '{job,updated_at}') is not null,
  'authorized user status includes updated_at for timeout recovery'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '81555555-5555-4555-8555-555555555555',
    true
  );
end;
$$;
select throws_ok(
  $$
    select public.creator_real_generation_status(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'job_id', (select initial_response #>> '{job,id}' from paid_runway_context)
    ))
  $$,
  '42501', 'role_not_allowed',
  'viewer cannot inspect paid generation state'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '81111111-1111-4111-8111-111111111111',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.system_update_real_generation(
      jsonb_build_object(
        'job_id', (select initial_response #>> '{job,id}' from paid_runway_context),
        'status', 'failed', 'failure_code', 'provider_request_failed',
        'provider_message', 'must never be persisted'
      )
    )
  $$,
  '22023', 'real_generation_update_payload_invalid',
  'system update rejects raw provider details instead of persisting them'
);

do $$
declare
  response jsonb;
  job_id_value uuid;
  ordinal integer;
begin
  -- Three jobs already count against the daily cap. Add and immediately fail
  -- seven more; failed provider attempts still consume the anti-abuse quota.
  for ordinal in 1..7 loop
    response := public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-daily-seed-' || lpad(ordinal::text, 4, '0'),
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '1:1', 'brief', 'Daily quota seed.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ));
    job_id_value := (response #>> '{job,id}')::uuid;
    perform public.system_update_real_generation(jsonb_build_object(
      'job_id', job_id_value,
      'status', 'failed',
      'failure_code', 'provider_request_failed'
    ));
  end loop;
end;
$$;

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '80000000-0000-4000-8000-000000000001',
      'idempotency_key', 'real-daily-reject-0001',
      'sku', 'REAL-SKU-1', 'product_name', 'Runway product',
      'count', 1, 'format', '1:1', 'brief', 'Over the daily quota.',
      'media_ids', '["83000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'wb-real-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '54000', 'real_generation_user_daily_quota_exceeded',
  'paid generation is capped at ten user jobs per rolling day'
);

select is(
  (
    select count(*)::integer
    from content_factory.factory_events event
    where event.event_name = 'real_generation_starting'
      and event.entity_id = (
        select initial_response #>> '{job,id}' from paid_runway_context
      )
  ),
  1,
  'duplicate starting claims emit one audit event'
);

select is(
  (
    select count(*)::integer
    from content_factory.command_receipts receipt
    where receipt.command_name = 'creator_start_real_generation'
      and receipt.idempotency_key = 'real-success-path-0001'
  ),
  1,
  'idempotent start stores one durable command receipt'
);

select * from finish();
rollback;
