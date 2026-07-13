begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(47);

-- TEST-ONLY grading material. These deliberately synthetic keys are derived
-- from the first option and disappear with the transaction rollback.
insert into content_factory_private.training_answer_keys (
  question_code,
  correct_answers,
  rubric
)
select
  question.code,
  jsonb_build_array(question.options ->> 0),
  'TEST-ONLY synthetic pgTAP key'
from content_factory.training_questions question
where question.module_code = 'operator_final_exam';

select is(
  (
    select count(*)::integer
    from content_factory.training_modules module
    where module.module_type = 'course' and module.is_active
  ),
  4,
  'catalog has four active courses'
);

select is(
  (
    select count(*)::integer
    from content_factory.training_questions question
    where question.module_code = 'operator_final_exam'
  ),
  12,
  'final exam has twelve scenarios'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = any(array[
        'creator_bootstrap', 'creator_complete_module', 'creator_submit_exam',
        'creator_workspace_section', 'creator_create_mock_batch',
        'creator_confirm_placement', 'creator_record_metric',
        'creator_set_wb_alias', 'creator_decide_payout',
        'creator_transition_task', 'creator_create_feedback',
        'creator_register_media', 'creator_capture_event'
      ])
      and procedure.pronargs = 1
      and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'
  ),
  13,
  'all browser RPCs expose exactly p_payload jsonb'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname like 'creator_%'
      and has_function_privilege('authenticated', procedure.oid, 'execute')
  ),
  13,
  'authenticated can execute all creator RPCs'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname like 'creator_%'
      and has_function_privilege('anon', procedure.oid, 'execute')
  ),
  0,
  'anon cannot execute creator RPCs'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'system_initialize_owner',
        'system_provision_invited_member',
        'system_reconcile_invited_member'
      )
      and has_function_privilege('authenticated', procedure.oid, 'execute')
  ),
  0,
  'authenticated cannot execute system onboarding RPCs'
);

select is(
  (
    select count(*)::integer
    from pg_proc procedure
    join pg_namespace namespace on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname in (
        'system_initialize_owner',
        'system_provision_invited_member',
        'system_reconcile_invited_member'
      )
      and has_function_privilege('service_role', procedure.oid, 'execute')
  ),
  3,
  'service_role can execute all system onboarding RPCs'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '11111111-1111-4111-8111-111111111111'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'creator-factory-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Factory Owner"}'::jsonb,
  now(),
  now()
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    '11111111-1111-4111-8111-111111111111',
    true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;

select ok(
  (public.system_initialize_owner(jsonb_build_object(
    'user_id', '11111111-1111-4111-8111-111111111111',
    'idempotency_key', 'pgtap-initialize-owner-0001'
  )) ->> 'ok')::boolean,
  'service-role owner initialization succeeds'
);

select ok(
  (public.system_initialize_owner(jsonb_build_object(
    'user_id', '11111111-1111-4111-8111-111111111111',
    'idempotency_key', 'pgtap-initialize-owner-0001'
  )) ->> 'ok')::boolean,
  'owner initialization retry is idempotent'
);

create temporary table creator_test_context (
  organization_id uuid not null,
  profile_id uuid not null,
  media_id uuid,
  bootstrap jsonb not null
) on commit drop;

insert into creator_test_context (organization_id, profile_id, bootstrap)
select
  (bootstrap -> 'organization' ->> 'id')::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  bootstrap
from (select public.creator_bootstrap('{}'::jsonb) as bootstrap) response;

select is(
  (select bootstrap -> 'membership' ->> 'role' from creator_test_context),
  'owner',
  'first authenticated user becomes owner'
);

select ok(
  not (select (bootstrap ->> 'workspace_open')::boolean from creator_test_context),
  'first owner workspace is closed before training'
);

do $$
declare
  context_row creator_test_context%rowtype;
  module_row record;
  exact_answers jsonb;
begin
  select * into context_row from creator_test_context;

  for module_row in
    select code
    from content_factory.training_modules
    where module_type = 'course' and is_active
    order by order_index
  loop
    perform public.creator_complete_module(jsonb_build_object(
      'organization_id', context_row.organization_id,
      'module_code', module_row.code,
      'idempotency_key', 'pgtap-course-' || module_row.code
    ));
  end loop;

  select jsonb_object_agg(answer.question_code, answer.correct_answers)
    into exact_answers
  from content_factory_private.training_answer_keys answer
  join content_factory.training_questions question
    on question.code = answer.question_code
  where question.module_code = 'operator_final_exam';

  perform public.creator_submit_exam(jsonb_build_object(
    'organization_id', context_row.organization_id,
    'module_code', 'operator_final_exam',
    'answers', exact_answers,
    'idempotency_key', 'pgtap-exam-pass-0001'
  ));

  update creator_test_context
  set bootstrap = public.creator_bootstrap(jsonb_build_object(
    'organization_id', context_row.organization_id
  ));
end;
$$;

select ok(
  (select (bootstrap ->> 'workspace_open')::boolean from creator_test_context),
  'workspace opens after all courses and exact server-side exam grading'
);

select ok(
  (select bootstrap::text from creator_test_context) !~* 'correct_answers|answer_key|rubric',
  'bootstrap never exposes private answer material'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  invited_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '22222222-2222-4222-8222-222222222222'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'creator-factory-invited@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Invited Creator"}'::jsonb,
  now(),
  now()
);

select set_config(
  'request.jwt.claim.sub',
  '22222222-2222-4222-8222-222222222222',
  true
);

select is(
  public.creator_bootstrap('{}'::jsonb) ->> 'state',
  'membership_required',
  'bootstrap never autojoins an authenticated user'
);

do $$
declare
  organization_id_value uuid;
begin
  select organization_id into organization_id_value from creator_test_context;
  perform set_config(
    'request.jwt.claim.sub',
    '11111111-1111-4111-8111-111111111111',
    true
  );
  perform public.system_provision_invited_member(jsonb_build_object(
    'organization_id', organization_id_value,
    'user_id', '22222222-2222-4222-8222-222222222222',
    'invited_by', '11111111-1111-4111-8111-111111111111',
    'idempotency_key', 'pgtap-provision-invited-0001'
  ));
  update content_factory.memberships
  set status = 'suspended'
  where organization_id = organization_id_value
    and profile_id = '22222222-2222-4222-8222-222222222222';
  perform set_config(
    'request.jwt.claim.sub',
    '22222222-2222-4222-8222-222222222222',
    true
  );
end;
$$;

select is(
  public.creator_bootstrap('{}'::jsonb) ->> 'state',
  'membership_suspended',
  'suspended membership receives the exact fail-closed state'
);

select is(
  (
    select status
    from content_factory.memberships
    where profile_id = '22222222-2222-4222-8222-222222222222'
  ),
  'suspended',
  'bootstrap does not reactivate a suspended membership'
);

update content_factory.memberships
set status = 'revoked'
where profile_id = '22222222-2222-4222-8222-222222222222';

select is(
  public.creator_bootstrap('{}'::jsonb) ->> 'state',
  'membership_revoked',
  'revoked membership receives the exact fail-closed state'
);

select is(
  (
    select status
    from content_factory.memberships
    where profile_id = '22222222-2222-4222-8222-222222222222'
  ),
  'revoked',
  'bootstrap does not reactivate a revoked membership'
);

select set_config(
  'request.jwt.claim.sub',
  '11111111-1111-4111-8111-111111111111',
  true
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  '33333333-3333-4333-8333-333333333333'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated',
  'authenticated',
  'existing-confirmed@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Existing Confirmed Creator"}'::jsonb,
  now(),
  now()
);

select is(
  public.system_reconcile_invited_member(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'email', ' Existing-Confirmed@Example.Test ',
    'invited_by', '11111111-1111-4111-8111-111111111111'
  )) ->> 'role',
  'trainee',
  'exact normalized confirmed email is safely reconciled'
);

select ok(
  (public.system_provision_invited_member(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'user_id', '33333333-3333-4333-8333-333333333333',
    'invited_by', '11111111-1111-4111-8111-111111111111',
    'idempotency_key', 'pgtap-existing-active-member-0001'
  )) ->> 'already_active')::boolean,
  'active existing membership is idempotently confirmed'
);

update content_factory.memberships
set status = 'suspended'
where profile_id = '33333333-3333-4333-8333-333333333333';

select throws_ok(
  $$
    select public.system_reconcile_invited_member(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'email', 'existing-confirmed@example.test',
      'invited_by', '11111111-1111-4111-8111-111111111111'
    ))
  $$,
  '23505',
  'target_membership_history_conflict',
  'reconciliation never restores a suspended membership'
);

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  organization_id::text || '/' || profile_id::text || '/uploads/pgtap-product.jpg',
  jsonb_build_object('size', 1024, 'mimetype', 'image/jpeg')
from creator_test_context;

do $$
declare
  context_row creator_test_context%rowtype;
  response jsonb;
begin
  select * into context_row from creator_test_context;
  response := public.creator_register_media(jsonb_build_object(
    'organization_id', context_row.organization_id,
    'bucket', 'contentengine-private',
    'object_key', context_row.organization_id::text || '/' ||
      context_row.profile_id::text || '/uploads/pgtap-product.jpg',
    'original_filename', 'pgtap-product.jpg',
    'mime_type', 'image/jpeg',
    'size_bytes', 1024,
    'sha256', repeat('a', 64),
    'kind', 'product_photo',
    'sku', 'PGTAP-SKU-1',
    'product_name', 'PgTAP product',
    'rights_confirmed', true,
    'idempotency_key', 'pgtap-media-register-0001'
  ));
  update creator_test_context
  set media_id = (response -> 'media' ->> 'id')::uuid;
end;
$$;

select ok(
  not content_factory.storage_object_is_unregistered(
    'contentengine-private',
    (select organization_id::text || '/' || profile_id::text ||
      '/uploads/pgtap-product.jpg' from creator_test_context)
  ),
  'registered ready media cannot be deleted as an upload rollback'
);

select ok(
  content_factory.storage_object_is_unregistered(
    'contentengine-private',
    (select organization_id::text || '/' || profile_id::text ||
      '/uploads/unregistered.jpg' from creator_test_context)
  ),
  'an unregistered own upload remains removable after failed registration'
);

select throws_ok(
  $$
    select public.creator_create_mock_batch(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'sku', 'PGTAP-SKU-1',
      'product_name', 'PgTAP product',
      'count', 2,
      'format', '9:16',
      'brief', 'Runtime contract test',
      'media_ids', jsonb_build_array((select media_id from creator_test_context)),
      'platform', 'wildberries',
      'destination_ref', 'PgTAP WB destination',
      'payout_minor', 0,
      'mode', 'real',
      'allow_real_spend', true,
      'spend_confirmation', 'REAL',
      'idempotency_key', 'pgtap-real-spend-reject-0001'
    ))
  $$,
  '42501',
  'mock_only_required',
  'real generation request is rejected server-side'
);

do $$
declare
  context_row creator_test_context%rowtype;
begin
  select * into context_row from creator_test_context;
  perform public.creator_create_mock_batch(jsonb_build_object(
    'organization_id', context_row.organization_id,
    'sku', 'PGTAP-SKU-1',
    'product_name', 'PgTAP product',
    'count', 2,
    'format', '9:16',
    'brief', 'Runtime contract test',
    'media_ids', jsonb_build_array(context_row.media_id),
    'platform', 'wildberries',
    'destination_ref', 'PgTAP WB destination',
    'payout_minor', 0,
    'mode', 'mock',
    'allow_real_spend', false,
    'spend_confirmation', 'MOCK_ONLY',
    'idempotency_key', 'pgtap-mock-batch-0001'
  ));
end;
$$;

select is(
  (
    select count(*)::integer
    from content_factory.generation_batches batch
    join creator_test_context context
      on context.organization_id = batch.organization_id
    where batch.mode = 'mock'
      and not batch.allow_real_spend
      and batch.total_requested = 2
  ),
  1,
  'valid exact-media request creates one mock-only batch'
);

select is(
  (
    select count(*)::integer
    from content_factory.placements placement
    join creator_test_context context
      on context.organization_id = placement.organization_id
    where placement.status = 'ready'
      and placement.platform = 'wildberries'
  ),
  2,
  'mock batch creates one ready placement per requested variant'
);

select is(
  (
    select count(*)::integer
    from content_factory.creator_tasks task
    join creator_test_context context
      on context.organization_id = task.organization_id
    where task.task_type = 'placement'
      and task.status = 'todo'
  ),
  2,
  'mock batch creates one assigned placement task per variant'
);

select is(
  (
    select count(*)::integer
    from content_factory.generation_jobs job
    join creator_test_context context
      on context.organization_id = job.organization_id
    where job.mode = 'mock'
      and job.provider = 'mock'
      and not job.allow_real_spend
      and job.estimated_cost_minor = 0
      and job.actual_cost_minor = 0
  ),
  2,
  'every generated job remains physically mock-only and zero-cost'
);

select is(
  (
    public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'generation'
    )) -> '_meta' ->> 'page_size'
  )::integer,
  50,
  'workspace collections default to fifty rows'
);

select ok(
  (
    select
      jsonb_array_length(response -> 'batches') <= 1
      and jsonb_array_length(response -> 'media') <= 1
      and jsonb_array_length(response -> 'wb_aliases') <= 1
    from (
      select public.creator_workspace_section(jsonb_build_object(
        'organization_id', (select organization_id from creator_test_context),
        'section', 'generation',
        'page_size', 1
      )) as response
    ) bounded
  ),
  'one page size independently bounds every generation collection'
);

select throws_ok(
  $$
    select public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'generation',
      'page_size', 101
    ))
  $$,
  '22023',
  'workspace_page_size_invalid',
  'ordinary workspace pages reject cap plus one'
);

select is(
  (
    public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'team',
      'page_size', 200
    )) -> '_meta' ->> 'page_size'
  )::integer,
  200,
  'team workspace accepts its exact two-hundred-row cap'
);

select throws_ok(
  $$
    select public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'team',
      'page_size', 201
    ))
  $$,
  '22023',
  'workspace_page_size_invalid',
  'team workspace rejects cap plus one'
);

select throws_ok(
  $$
    select public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'generation',
      'page_size', 999999999999999999999999999999::numeric
    ))
  $$,
  '22023',
  'workspace_page_size_invalid',
  'workspace page integer overflow has a stable validation error'
);

select throws_ok(
  $$
    select public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'generation',
      'cursor', jsonb_build_object(
        'unknown_collection', jsonb_build_object(
          'at', now(),
          'id', (select profile_id from creator_test_context)
        )
      )
    ))
  $$,
  '22023',
  'workspace_cursor_invalid',
  'workspace rejects a cursor for an unknown collection'
);

select throws_ok(
  $$
    select public.creator_workspace_section(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'section', 'feedback',
      'cursor', jsonb_build_object(
        'feedback_items', jsonb_build_object(
          'at', 'not-a-time',
          'id', 'not-a-uuid'
        )
      )
    ))
  $$,
  '22023',
  'workspace_cursor_invalid',
  'malformed cursor fails even when its collection is empty'
);

select is(
  (
    with first_page as (
      select public.creator_workspace_section(jsonb_build_object(
        'organization_id', (select organization_id from creator_test_context),
        'section', 'generation',
        'page_size', 1
      )) as response
    )
    select jsonb_array_length(
      public.creator_workspace_section(jsonb_build_object(
        'organization_id', (select organization_id from creator_test_context),
        'section', 'generation',
        'page_size', 1,
        'cursor', jsonb_build_object(
          'generation_batches', response -> 'batches' -> 0 -> '_cursor'
        )
      )) -> 'batches'
    )
    from first_page
  ),
  0,
  'strict keyset cursor excludes the boundary batch without overlap'
);

select throws_ok(
  $$
    select public.creator_create_mock_batch(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'sku', 'PGTAP-SKU-1',
      'product_name', 'PgTAP product',
      'count', 999999999999999999999999999999::numeric,
      'format', '9:16',
      'brief', 'Overflow must be rejected',
      'media_ids', jsonb_build_array((select media_id from creator_test_context)),
      'platform', 'wildberries',
      'destination_ref', 'PgTAP WB destination',
      'payout_minor', 0,
      'mode', 'mock',
      'allow_real_spend', false,
      'spend_confirmation', 'MOCK_ONLY',
      'idempotency_key', 'pgtap-count-overflow-0001'
    ))
  $$,
  '22023',
  'count_invalid',
  'mock batch count integer overflow has a stable validation error'
);

insert into content_factory.generation_batches (
  organization_id, product_id, created_by, name,
  mode, allow_real_spend, status, total_requested, total_created,
  input, request_hash, idempotency_key
)
select
  context.organization_id,
  product.id,
  context.profile_id,
  'PgTAP quota seed ' || seed.ordinal::text,
  'mock', false, 'mock_ready', seed.variant_count, seed.variant_count,
  '{}'::jsonb, repeat('b', 64),
  'pgtap-quota-seed-' || lpad(seed.ordinal::text, 4, '0')
from creator_test_context context
join content_factory.products product
  on product.organization_id = context.organization_id
 and product.sku = 'PGTAP-SKU-1'
cross join (values (1, 50), (2, 50), (3, 50), (4, 47))
  seed(ordinal, variant_count);

select ok(
  (public.creator_create_mock_batch(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'sku', 'PGTAP-SKU-1',
    'product_name', 'PgTAP product',
    'count', 1,
    'format', '9:16',
    'brief', 'Exact rolling quota boundary',
    'media_ids', jsonb_build_array((select media_id from creator_test_context)),
    'platform', 'wildberries',
    'destination_ref', 'PgTAP WB destination',
    'payout_minor', 0,
    'mode', 'mock',
    'allow_real_spend', false,
    'spend_confirmation', 'MOCK_ONLY',
    'idempotency_key', 'pgtap-quota-boundary-0001'
  )) ->> 'ok')::boolean,
  'the exact two-hundred variant rolling boundary succeeds'
);

select throws_ok(
  $$
    select public.creator_create_mock_batch(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'sku', 'PGTAP-SKU-1',
      'product_name', 'PgTAP product',
      'count', 1,
      'format', '9:16',
      'brief', 'One over rolling quota',
      'media_ids', jsonb_build_array((select media_id from creator_test_context)),
      'platform', 'wildberries',
      'destination_ref', 'PgTAP WB destination',
      'payout_minor', 0,
      'mode', 'mock',
      'allow_real_spend', false,
      'spend_confirmation', 'MOCK_ONLY',
      'idempotency_key', 'pgtap-quota-reject-0001'
    ))
  $$,
  '54000',
  'mock_batch_user_15m_quota_exceeded',
  'rolling variant quota rejects the first item over the limit'
);

select ok(
  not exists (
    select 1
    from content_factory.generation_batches batch
    where batch.idempotency_key = 'pgtap-quota-reject-0001'
  )
  and not exists (
    select 1
    from content_factory.command_receipts receipt
    where receipt.command_name = 'creator_create_mock_batch'
      and receipt.idempotency_key = 'pgtap-quota-reject-0001'
  )
  and not exists (
    select 1
    from content_factory.factory_events event
    where event.idempotency_key = 'mock_batch:pgtap-quota-reject-0001'
  ),
  'a rejected quota request leaves no batch receipt or event'
);

select ok(
  (public.creator_create_mock_batch(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'sku', 'PGTAP-SKU-1',
    'product_name', 'PgTAP product',
    'count', 1,
    'format', '9:16',
    'brief', 'Exact rolling quota boundary',
    'media_ids', jsonb_build_array((select media_id from creator_test_context)),
    'platform', 'wildberries',
    'destination_ref', 'PgTAP WB destination',
    'payout_minor', 0,
    'mode', 'mock',
    'allow_real_spend', false,
    'spend_confirmation', 'MOCK_ONLY',
    'idempotency_key', 'pgtap-quota-boundary-0001'
  )) ->> 'ok')::boolean,
  'idempotent replay still succeeds after the rolling quota is full'
);

insert into content_factory.media_objects (
  organization_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
select
  context.organization_id,
  context.profile_id,
  'contentengine-private',
  context.organization_id::text || '/' || context.profile_id::text ||
    '/uploads/quota-seed-' || lpad(seed.ordinal::text, 4, '0') || '.jpg',
  'image/jpeg', 1, repeat('c', 64), 'ready',
  jsonb_build_object(
    'original_filename', 'quota-seed-' || seed.ordinal::text || '.jpg',
    'kind', 'creator_reference',
    'rights_confirmed', true
  ),
  'pgtap-media-quota-seed-' || lpad(seed.ordinal::text, 4, '0')
from creator_test_context context
cross join generate_series(1, 198) seed(ordinal);

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  organization_id::text || '/' || profile_id::text || '/uploads/quota-boundary.jpg',
  jsonb_build_object('size', 1, 'mimetype', 'image/jpeg')
from creator_test_context;

select ok(
  (public.creator_register_media(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'bucket', 'contentengine-private',
    'object_key', (select organization_id::text || '/' || profile_id::text ||
      '/uploads/quota-boundary.jpg' from creator_test_context),
    'original_filename', 'quota-boundary.jpg',
    'mime_type', 'image/jpeg',
    'size_bytes', 1,
    'sha256', repeat('d', 64),
    'kind', 'creator_reference',
    'rights_confirmed', true,
    'idempotency_key', 'pgtap-media-quota-boundary-0001'
  )) ->> 'ok')::boolean,
  'the exact two-hundred media object daily boundary succeeds'
);

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  organization_id::text || '/' || profile_id::text || '/uploads/quota-reject.jpg',
  jsonb_build_object('size', 1, 'mimetype', 'image/jpeg')
from creator_test_context;

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'bucket', 'contentengine-private',
      'object_key', (select organization_id::text || '/' || profile_id::text ||
        '/uploads/quota-reject.jpg' from creator_test_context),
      'original_filename', 'quota-reject.jpg',
      'mime_type', 'image/jpeg',
      'size_bytes', 1,
      'sha256', repeat('e', 64),
      'kind', 'creator_reference',
      'rights_confirmed', true,
      'idempotency_key', 'pgtap-media-quota-reject-0001'
    ))
  $$,
  '54000',
  'media_user_daily_object_quota_exceeded',
  'daily media object quota rejects object two-hundred-and-one'
);

select ok(
  content_factory.storage_object_is_unregistered(
    'contentengine-private',
    (select organization_id::text || '/' || profile_id::text ||
      '/uploads/quota-reject.jpg' from creator_test_context)
  ),
  'quota-rejected storage upload remains unregistered and removable'
);

select ok(
  (public.creator_register_media(jsonb_build_object(
    'organization_id', (select organization_id from creator_test_context),
    'bucket', 'contentengine-private',
    'object_key', (select organization_id::text || '/' || profile_id::text ||
      '/uploads/quota-boundary.jpg' from creator_test_context),
    'original_filename', 'quota-boundary.jpg',
    'mime_type', 'image/jpeg',
    'size_bytes', 1,
    'sha256', repeat('d', 64),
    'kind', 'creator_reference',
    'rights_confirmed', true,
    'idempotency_key', 'pgtap-existing-media-reuse-0001'
  )) ->> 'ok')::boolean,
  'identical existing media can be reused when the quota is full'
);

select throws_ok(
  $$
    select public.creator_register_media(jsonb_build_object(
      'organization_id', (select organization_id from creator_test_context),
      'bucket', 'contentengine-private',
      'object_key', (select organization_id::text || '/' || profile_id::text ||
        '/uploads/quota-boundary.jpg' from creator_test_context),
      'original_filename', 'different-name.jpg',
      'mime_type', 'image/jpeg',
      'size_bytes', 1,
      'sha256', repeat('d', 64),
      'kind', 'creator_reference',
      'rights_confirmed', true,
      'idempotency_key', 'pgtap-existing-media-conflict-0001'
    ))
  $$,
  '23505',
  'media_object_conflict',
  'existing media immutable metadata cannot bypass registration quotas'
);

select * from finish();
rollback;
