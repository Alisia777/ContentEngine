begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(37);

select ok(
  has_function_privilege(
    'authenticated', 'public.creator_start_real_generation(jsonb)', 'execute'
  ),
  'authenticated keeps the one-jsonb paid start RPC'
);
select ok(
  not has_function_privilege(
    'anon', 'public.creator_start_real_generation(jsonb)', 'execute'
  ),
  'anon cannot start Seedance generation'
);
select ok(
  has_function_privilege(
    'service_role', 'public.system_update_real_generation(jsonb)', 'execute'
  ),
  'service role can advance either exact Runway SKU'
);
select ok(
  not has_function_privilege(
    'authenticated', 'public.system_update_real_generation(jsonb)', 'execute'
  ),
  'authenticated cannot mutate provider state'
);
select is(
  (
    select count(*)::integer
    from information_schema.columns column_info
    where column_info.table_schema = 'content_factory'
      and column_info.table_name = 'generation_batches'
      and column_info.column_name in (
        'provider', 'model', 'duration_seconds', 'audio',
        'estimated_cost_minor', 'estimated_credits', 'currency'
      )
  ),
  7,
  'generation batches expose seven first-class SKU and billing facts'
);
select is(
  content_factory_private.real_generation_sku_config(
    'seedance2_fast', '8'::jsonb, 'true'::jsonb, '9:16',
    'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
  ) #>> '{estimated_credits}',
  '232',
  'Seedance exact SKU resolves to 232 credits'
);
select is(
  content_factory_private.real_generation_sku_config(
    'gen4_turbo', '5'::jsonb, null, '16:9',
    'RUNWAY_GEN4_TURBO_5S_USD_0.25'
  ) #>> '{ratio}',
  '1280:720',
  'existing Gen-4 SKU remains in the exact config catalog'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
values (
  '91111111-1111-4111-8111-111111111111',
  '00000000-0000-0000-0000-000000000000',
  'authenticated',
  'authenticated',
  'seedance-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Seedance Owner"}'::jsonb,
  now(),
  now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  '90000000-0000-4000-8000-000000000001',
  'Seedance 8s Test',
  'seedance-8s-test',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  '90000000-0000-4000-8000-000000000001',
  '91111111-1111-4111-8111-111111111111',
  'owner',
  'active'
);

with inserted_attempt as (
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '90000000-0000-4000-8000-000000000001',
    '91111111-1111-4111-8111-111111111111',
    'operator_final_exam', 'completed', 1, 12, 12, 12, true,
    '{}'::jsonb, repeat('9', 64), 'seedance-owner-exam-0001'
  )
  returning id, organization_id, profile_id, module_code
)
insert into content_factory.training_certifications (
  organization_id, profile_id, module_code, attempt_id, status
)
select organization_id, profile_id, module_code, id, 'passed'
from inserted_attempt;

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values (
  '92000000-0000-4000-8000-000000000001',
  '90000000-0000-4000-8000-000000000001',
  'SEEDANCE-SKU-1',
  'Seedance product',
  'active',
  '91111111-1111-4111-8111-111111111111'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values
  (
    '93000000-0000-4000-8000-000000000001',
    '90000000-0000-4000-8000-000000000001',
    '91111111-1111-4111-8111-111111111111',
    '92000000-0000-4000-8000-000000000001',
    'contentengine-private',
    '90000000-0000-4000-8000-000000000001/91111111-1111-4111-8111-111111111111/uploads/approved-seedance.jpg',
    'image/jpeg', 4096, repeat('a', 64), 'ready',
    '{"kind":"product_photo","original_filename":"approved-seedance.jpg","rights_confirmed":true}'::jsonb,
    'seedance-approved-media-0001'
  ),
  (
    '93000000-0000-4000-8000-000000000002',
    '90000000-0000-4000-8000-000000000001',
    '91111111-1111-4111-8111-111111111111',
    '92000000-0000-4000-8000-000000000001',
    'contentengine-private',
    '90000000-0000-4000-8000-000000000001/91111111-1111-4111-8111-111111111111/uploads/unapproved-seedance.jpg',
    'image/jpeg', 4096, repeat('b', 64), 'ready',
    '{"kind":"packshot","original_filename":"unapproved-seedance.jpg","rights_confirmed":false}'::jsonb,
    'seedance-unapproved-media-0001'
  );

create temporary table seedance_test_context (
  success_response jsonb,
  failure_response jsonb,
  gen4_response jsonb
) on commit drop;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    '91111111-1111-4111-8111-111111111111',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-audio-reject-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking.',
      'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
      'duration_seconds', 8, 'audio', false, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
    ))
  $$,
  '42501', 'real_generation_spend_confirmation_required',
  'Seedance SKU rejects audio=false'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-ratio-reject-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '16:9', 'brief', 'Show the exact product speaking.',
      'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
      'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
    ))
  $$,
  '42501', 'real_generation_spend_confirmation_required',
  'Seedance SKU is fixed to internal format 9:16'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-confirm-reject-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking.',
      'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
      'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '42501', 'real_generation_spend_confirmation_required',
  'Seedance SKU requires its exact $2.32 confirmation'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-prompt-reject-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '9:16', 'brief', '',
      'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
      'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
    ))
  $$,
  '22023', 'brief_invalid',
  'Seedance SKU requires a nonempty bounded prompt'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-media-reject-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking.',
      'media_ids', '["93000000-0000-4000-8000-000000000002"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
      'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
    ))
  $$,
  '42501', 'seedance_approved_product_media_required',
  'ready product media without rights approval is rejected'
);

insert into seedance_test_context (success_response)
values (public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '90000000-0000-4000-8000-000000000001',
  'idempotency_key', 'seedance-success-0001',
  'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
  'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking clearly.',
  'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'seedance-test',
  'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
  'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
)));

select is(
  (select success_response #>> '{job,model}' from seedance_test_context),
  'seedance2_fast',
  'valid request returns the exact provider model'
);
select is(
  (
    select concat_ws(':',
      success_response #>> '{job,duration_seconds}',
      success_response #>> '{job,audio}',
      success_response #>> '{job,ratio}',
      success_response #>> '{job,estimated_cost_minor}',
      success_response #>> '{job,estimated_credits}'
    )
    from seedance_test_context
  ),
  '8:true:720:1280:232:232',
  'wire response carries 8s, audio, provider ratio and exact price'
);
select ok(
  exists (
    select 1
    from content_factory.generation_batches batch
    where batch.id = (
      select (success_response #>> '{batch,id}')::uuid from seedance_test_context
    )
      and batch.provider = 'runway'
      and batch.model = 'seedance2_fast'
      and batch.duration_seconds = 8
      and batch.audio
      and batch.estimated_cost_minor = 232
      and batch.estimated_credits = 232
      and batch.currency = 'USD'
      and batch.input ->> 'job_id' = (
        select success_response #>> '{job,id}' from seedance_test_context
      )
  ),
  'batch stores first-class and snapshot Seedance facts consistently'
);
select ok(
  exists (
    select 1
    from content_factory.generation_jobs job
    where job.id = (
      select (success_response #>> '{job,id}')::uuid from seedance_test_context
    )
      and job.status = 'queued'
      and job.estimated_cost_minor = 232
      and job.actual_cost_minor = 0
      and job.input -> 'audio' = 'true'::jsonb
      and job.input ->> 'ratio' = '720:1280'
  ),
  'queued job is fixed to Seedance audio and has no actual cost yet'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    where task.generation_job_id = (
      select (success_response #>> '{job,id}')::uuid from seedance_test_context
    )
      and task.task_type = 'video_review'
      and task.status = 'blocked'
      and task.result -> 'audio' = 'true'::jsonb
  ),
  'Seedance start creates a blocked audio review task'
);
select is(
  public.creator_start_real_generation(jsonb_build_object(
    'organization_id', '90000000-0000-4000-8000-000000000001',
    'idempotency_key', 'seedance-success-0001',
    'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
    'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking clearly.',
    'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
    'platform', 'wildberries', 'destination_ref', 'seedance-test',
    'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
    'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
  ))::text,
  (select success_response::text from seedance_test_context),
  'Seedance start replays before quota evaluation'
);
select is(
  public.creator_real_generation_status(jsonb_build_object(
    'organization_id', '90000000-0000-4000-8000-000000000001',
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context)
  )) #>> '{job,audio}',
  'true',
  'user status exposes audio=true'
);

select ok(
  (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
    'status', 'starting'
  )) ->> 'claimed')::boolean,
  'Seedance uses the same atomic paid-call claim'
);
select ok(
  not (public.system_update_real_generation(jsonb_build_object(
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
    'status', 'starting'
  )) ->> 'claimed')::boolean,
  'duplicate Seedance claim cannot call Runway twice'
);
select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
    'status', 'submitted', 'provider_task_id', 'seedance-task-success-001'
  )) #>> '{job,status}',
  'submitted',
  'Seedance starting moves to submitted with one provider task id'
);
select is(
  (
    select actual_cost_minor::text
    from content_factory.generation_jobs
    where id = (
      select (success_response #>> '{job,id}')::uuid from seedance_test_context
    )
  ),
  '232',
  'submitted Seedance job records its persisted SKU cost, never Gen-4 cost'
);
select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
    'status', 'processing', 'provider_task_id', 'seedance-task-success-001'
  )) #>> '{job,status}',
  'processing',
  'Seedance submitted moves to processing'
);

insert into storage.objects (bucket_id, name, metadata, user_metadata)
select
  'contentengine-private',
  success_response #>> '{job,output_object_name}',
  jsonb_build_object('size', 8192, 'mimetype', 'video/mp4'),
  jsonb_build_object('sha256', repeat('c', 64))
from seedance_test_context;

select throws_ok(
  $$
    select public.system_update_real_generation(jsonb_build_object(
      'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
      'status', 'succeeded', 'provider_task_id', 'seedance-task-success-001',
      'output_object_name', (select success_response #>> '{job,output_object_name}' from seedance_test_context),
      'mime_type', 'video/mp4', 'size_bytes', 8192, 'sha256', repeat('d', 64)
    ))
  $$,
  '22023', 'real_generation_storage_metadata_mismatch',
  'Seedance success rejects mismatched Storage SHA-256'
);

select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context),
    'status', 'succeeded', 'provider_task_id', 'seedance-task-success-001',
    'output_object_name', (select success_response #>> '{job,output_object_name}' from seedance_test_context),
    'mime_type', 'video/mp4', 'size_bytes', 8192, 'sha256', repeat('c', 64)
  )) #>> '{job,status}',
  'succeeded',
  'validated Seedance MP4 reaches succeeded'
);
select ok(
  exists (
    select 1
    from content_factory.media_objects media
    where media.object_name = (
      select success_response #>> '{job,output_object_name}' from seedance_test_context
    )
      and media.metadata ->> 'model' = 'seedance2_fast'
      and media.metadata ->> 'duration_seconds' = '8'
      and media.metadata -> 'audio' = 'true'::jsonb
      and media.metadata ->> 'estimated_credits' = '232'
  ),
  'generated media stores direct Seedance model/audio/credit facts'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    join content_factory.generation_batches batch
      on batch.organization_id = task.organization_id
     and batch.id = (
       select (success_response #>> '{batch,id}')::uuid from seedance_test_context
     )
    where task.generation_job_id = (
      select (success_response #>> '{job,id}')::uuid from seedance_test_context
    )
      and task.status = 'review'
      and task.result ->> 'model' = 'seedance2_fast'
      and task.result -> 'audio' = 'true'::jsonb
      and batch.status = 'succeeded'
      and batch.total_created = 1
  ),
  'success atomically releases review and completes the matching batch'
);
select is(
  public.creator_real_generation_status(jsonb_build_object(
    'organization_id', '90000000-0000-4000-8000-000000000001',
    'job_id', (select success_response #>> '{job,id}' from seedance_test_context)
  )) #>> '{job,estimated_credits}',
  '232',
  'terminal user status retains exact Seedance credits'
);

update seedance_test_context
set failure_response = public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '90000000-0000-4000-8000-000000000001',
  'idempotency_key', 'seedance-failure-0001',
  'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
  'count', 1, 'format', '9:16', 'brief', 'A second exact speaking product video.',
  'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'seedance-test',
  'mode', 'real', 'provider', 'runway', 'model', 'seedance2_fast',
  'duration_seconds', 8, 'audio', true, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_SEEDANCE2_FAST_8S_AUDIO_USD_2.32'
));

do $$
declare
  job_id_value uuid := (
    select (failure_response #>> '{job,id}')::uuid from seedance_test_context
  );
begin
  perform public.system_update_real_generation(jsonb_build_object(
    'job_id', job_id_value, 'status', 'starting'
  ));
  perform public.system_update_real_generation(jsonb_build_object(
    'job_id', job_id_value, 'status', 'submitted',
    'provider_task_id', 'seedance-task-failure-001'
  ));
end;
$$;

select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select failure_response #>> '{job,id}' from seedance_test_context),
    'status', 'failed', 'provider_task_id', 'seedance-task-failure-001',
    'failure_code', 'provider_task_failed'
  )) #>> '{job,status}',
  'failed',
  'submitted Seedance provider failure reaches sanitized failed state'
);
select ok(
  exists (
    select 1
    from content_factory.generation_jobs job
    join content_factory.creator_tasks task
      on task.organization_id = job.organization_id
     and task.generation_job_id = job.id
    where job.id = (
      select (failure_response #>> '{job,id}')::uuid from seedance_test_context
    )
      and job.actual_cost_minor = 232
      and job.output ->> 'failure_code' = 'provider_task_failed'
      and task.status = 'cancelled'
      and task.result ->> 'model' = 'seedance2_fast'
  ),
  'failed Seedance state uses persisted cost and cancels its review task'
);

select throws_ok(
  $$
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', '90000000-0000-4000-8000-000000000001',
      'idempotency_key', 'seedance-success-0001',
      'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
      'count', 1, 'format', '9:16', 'brief', 'Show the exact product speaking clearly.',
      'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
      'platform', 'wildberries', 'destination_ref', 'seedance-test',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'audio', false, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
    ))
  $$,
  '23505', 'idempotency_key_conflict',
  'one idempotency key cannot switch between paid SKUs'
);

update seedance_test_context
set gen4_response = public.creator_start_real_generation(jsonb_build_object(
  'organization_id', '90000000-0000-4000-8000-000000000001',
  'idempotency_key', 'gen4-after-seedance-0001',
  'sku', 'SEEDANCE-SKU-1', 'product_name', 'Seedance product',
  'count', 1, 'format', '16:9', 'brief', 'Preserve the Gen-4 path.',
  'media_ids', '["93000000-0000-4000-8000-000000000001"]'::jsonb,
  'platform', 'wildberries', 'destination_ref', 'seedance-test',
  'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
  'duration_seconds', 5, 'audio', false, 'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25'
));

select is(
  (
    select concat_ws(':',
      gen4_response #>> '{job,model}',
      gen4_response #>> '{job,audio}',
      gen4_response #>> '{job,estimated_credits}'
    )
    from seedance_test_context
  ),
  'gen4_turbo:false:25',
  'public dispatcher preserves Gen-4 and adds compatible audio/credits fields'
);
select ok(
  exists (
    select 1
    from content_factory.generation_batches batch
    where batch.id = (
      select (gen4_response #>> '{batch,id}')::uuid from seedance_test_context
    )
      and batch.model = 'gen4_turbo'
      and batch.duration_seconds = 5
      and not batch.audio
      and batch.estimated_cost_minor = 25
      and batch.estimated_credits = 25
  ),
  'legacy Gen-4 inserts receive consistent first-class batch facts'
);
select is(
  public.system_update_real_generation(jsonb_build_object(
    'job_id', (select gen4_response #>> '{job,id}' from seedance_test_context),
    'status', 'failed', 'failure_code', 'provider_request_failed'
  )) #>> '{job,status}',
  'failed',
  'model-neutral system updater also preserves queued Gen-4 failure handling'
);

select is(
  (
    select count(*)::integer
    from content_factory.command_receipts receipt
    where receipt.command_name = 'creator_start_real_generation'
      and receipt.idempotency_key = 'seedance-success-0001'
  ),
  1,
  'Seedance idempotent start stores one durable command receipt'
);
select is(
  (
    select count(*)::integer
    from content_factory.factory_events event
    where event.event_name = 'real_generation_starting'
      and event.entity_id = (
        select success_response #>> '{job,id}' from seedance_test_context
      )
  ),
  1,
  'duplicate Seedance starting claim emits one system audit event'
);

select * from finish();
rollback;
