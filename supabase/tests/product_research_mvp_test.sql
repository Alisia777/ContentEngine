begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(75);

select has_table('content_factory', 'product_research_runs', 'research runs table exists');
select has_table('content_factory', 'product_research_sources', 'research sources table exists');
select has_table('content_factory', 'creative_brief_drafts', 'creative brief drafts table exists');
select has_table('content_factory', 'creative_forecasts', 'creative forecasts table exists');
select has_column(
  'content_factory', 'product_research_runs', 'lease_expires_at',
  'processing runs carry a hard worker lease'
);
select has_column(
  'content_factory', 'creator_tasks', 'creative_brief_draft_id',
  'creator tasks link back to their approved brief'
);

select ok(
  exists (
    select 1 from pg_constraint
    where conrelid = 'content_factory.creator_tasks'::regclass
      and conname = 'creator_tasks_creative_brief_draft_fk'
      and contype = 'f'
  ),
  'creator task brief link is a database foreign key'
);

select ok((select relrowsecurity from pg_class where oid = 'content_factory.product_research_runs'::regclass), 'runs use RLS');
select ok((select relrowsecurity from pg_class where oid = 'content_factory.product_research_sources'::regclass), 'sources use RLS');
select ok((select relrowsecurity from pg_class where oid = 'content_factory.creative_brief_drafts'::regclass), 'drafts use RLS');
select ok((select relrowsecurity from pg_class where oid = 'content_factory.creative_forecasts'::regclass), 'forecasts use RLS');

select is(
  (select count(*)::integer from (values
    ('content_factory.product_research_runs'::regclass),
    ('content_factory.product_research_sources'::regclass),
    ('content_factory.creative_brief_drafts'::regclass),
    ('content_factory.creative_forecasts'::regclass)
  ) protected(table_oid) where has_table_privilege('authenticated', table_oid, 'select')),
  0,
  'authenticated receives no direct table reads'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_start_product_research', 'creator_product_research_status',
       'creator_save_creative_brief_draft', 'creator_approve_creative_brief'
     ) and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb'),
  4,
  'four browser research RPCs expose one jsonb payload'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_start_product_research', 'creator_product_research_status',
       'creator_save_creative_brief_draft', 'creator_approve_creative_brief'
     ) and has_function_privilege('authenticated', procedure.oid, 'execute')),
  4,
  'authenticated can execute all creator research RPCs'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_start_product_research', 'creator_product_research_status',
       'creator_save_creative_brief_draft', 'creator_approve_creative_brief'
     ) and has_function_privilege('anon', procedure.oid, 'execute')),
  0,
  'anon cannot execute creator research RPCs'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_product_research', 'system_complete_product_research'
     )),
  2,
  'two worker RPCs exist'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_product_research', 'system_complete_product_research'
     ) and has_function_privilege('service_role', procedure.oid, 'execute')),
  2,
  'service role can execute both worker RPCs'
);

select is(
  (select count(*)::integer from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_product_research', 'system_complete_product_research'
     ) and has_function_privilege('authenticated', procedure.oid, 'execute')),
  0,
  'browser sessions cannot claim or complete worker jobs'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
select fixture.id::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated', fixture.email,
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  jsonb_build_object('display_name', fixture.display_name), now(), now()
from (values
  ('93000000-0000-4000-8000-000000000001', 'research-owner@example.test', 'Research Owner'),
  ('93000000-0000-4000-8000-000000000002', 'research-viewer@example.test', 'Research Viewer'),
  ('93000000-0000-4000-8000-000000000003', 'research-producer@example.test', 'Research Producer')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('93100000-0000-4000-8000-000000000001', 'Research Main', 'research-main', 'active'),
  ('93100000-0000-4000-8000-000000000002', 'Research Other', 'research-other', 'active');

insert into content_factory.memberships (organization_id, profile_id, role, status)
values
  ('93100000-0000-4000-8000-000000000001', '93000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('93100000-0000-4000-8000-000000000002', '93000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('93100000-0000-4000-8000-000000000001', '93000000-0000-4000-8000-000000000002', 'viewer', 'active'),
  ('93100000-0000-4000-8000-000000000001', '93000000-0000-4000-8000-000000000003', 'producer', 'active');

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  '93200000-0000-4000-8000-000000000001',
  '93100000-0000-4000-8000-000000000001',
  'RESEARCH-SKU-1', 'Кровавый пилинг', 'active',
  '{"brand":"ALTEA","description":"AHA 30% BHA 2%"}'::jsonb,
  '93000000-0000-4000-8000-000000000001'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  '93200000-0000-4000-8000-000000000002',
  '93100000-0000-4000-8000-000000000001',
  'UPLOAD-AUTO-SKU', 'Upload placeholder product', 'active', '{}'::jsonb,
  '93000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  '93300000-0000-4000-8000-000000000001',
  '93100000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001',
  '93200000-0000-4000-8000-000000000002',
  'contentengine-private',
  '93100000-0000-4000-8000-000000000001/93000000-0000-4000-8000-000000000001/research/photo.webp',
  'image/webp', 2048, repeat('a', 64), 'ready',
  '{"kind":"product_photo","rights_confirmed":true}'::jsonb, 'research-media-0001'
);

do $$
declare attempt_id_value uuid;
begin
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '93100000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000001',
    'operator_final_exam', 'completed', 1, 12, 12, 12, true, '{}'::jsonb,
    repeat('b', 64), 'research-final-exam-0001'
  ) returning id into attempt_id_value;
  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    '93100000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000001',
    'operator_final_exam', attempt_id_value, 'passed'
  );

  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '93100000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000003',
    'operator_final_exam', 'completed', 1, 12, 12, 12, true, '{}'::jsonb,
    repeat('c', 64), 'research-final-exam-0002'
  ) returning id into attempt_id_value;
  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    '93100000-0000-4000-8000-000000000001',
    '93000000-0000-4000-8000-000000000003',
    'operator_final_exam', attempt_id_value, 'passed'
  );
end;
$$;

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config('request.jwt.claim.sub', '93000000-0000-4000-8000-000000000001', true);
end;
$$;

create temporary table research_test_context (
  start_result jsonb,
  run_id uuid,
  first_draft_id uuid,
  human_draft_id uuid,
  save_result jsonb,
  approve_result jsonb,
  completion_payload jsonb
) on commit drop;

insert into research_test_context (start_result)
select public.creator_start_product_research(jsonb_build_object(
  'organization_id', '93100000-0000-4000-8000-000000000001',
  'idempotency_key', 'research-start-0001',
  'product_id', '93200000-0000-4000-8000-000000000001',
  'objective', 'Составить доказательное ТЗ для восьмисекундного ролика',
  'marketplace_url', 'https://example.test/product/1',
  'source_media_ids', jsonb_build_array('93300000-0000-4000-8000-000000000001'::text),
  'platforms', jsonb_build_array('instagram', 'vk')
));
update research_test_context
set run_id = (start_result -> 'run' ->> 'id')::uuid;

select ok((select (start_result ->> 'ok')::boolean from research_test_context), 'manager starts research');
select is((select start_result -> 'run' ->> 'status' from research_test_context), 'queued', 'new research is queued');
select is((select (start_result -> 'run' ->> 'source_count')::integer from research_test_context), 2, 'URL and exact product photo become sources');
select is(
  (select count(*)::integer from content_factory.product_research_runs run
   where run.id = (select run_id from research_test_context)),
  1,
  'one durable run is created'
);
select ok(
  not ((select input from content_factory.product_research_runs
        where id = (select run_id from research_test_context)) ? 'idempotency_key'),
  'run stores only sanitized research input'
);

select throws_ok(
  $$select public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-too-many-photos',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'too many product photos',
    'source_media_ids', jsonb_build_array(
      '93300000-0000-4000-8000-000000000001'::text,
      '93300000-0000-4000-8000-000000000001'::text,
      '93300000-0000-4000-8000-000000000001'::text,
      '93300000-0000-4000-8000-000000000001'::text,
      '93300000-0000-4000-8000-000000000001'::text,
      '93300000-0000-4000-8000-000000000001'::text
    )
  ))$$,
  '22023', 'source_media_ids_invalid',
  'research accepts at most five photos, matching the Edge limit'
);

select throws_ok(
  $$select public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-platform-required',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'platform is required for a usable research brief',
    'marketplace_url', 'https://example.test/product/platform-required',
    'platforms', '[]'::jsonb
  ))$$,
  '22023', 'platforms_invalid',
  'research requires at least one supported publishing platform'
);

insert into content_factory.product_research_runs (
  organization_id, product_id, created_by, status, input,
  request_hash, idempotency_key
)
select
  '93100000-0000-4000-8000-000000000001',
  '93200000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001', 'queued',
  jsonb_build_object('objective', 'quota fixture', 'marketplace_url', 'https://example.test/quota/' || series,
    'source_media_ids', '[]'::jsonb, 'platforms', '[]'::jsonb,
    'product_id', '93200000-0000-4000-8000-000000000001'),
  repeat(to_hex(series), 64), 'research-quota-' || lpad(series::text, 4, '0')
from generate_series(1, 9) series;

select is(
  public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-start-0001',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'Составить доказательное ТЗ для восьмисекундного ролика',
    'marketplace_url', 'https://example.test/product/1',
    'source_media_ids', jsonb_build_array('93300000-0000-4000-8000-000000000001'::text),
    'platforms', jsonb_build_array('instagram', 'vk')
  )) -> 'run' ->> 'id',
  (select run_id::text from research_test_context),
  'idempotent replay bypasses a now-exhausted quota'
);

select throws_ok(
  $$select public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-start-over-limit',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'one more paid research',
    'marketplace_url', 'https://example.test/product/over-limit',
    'platforms', jsonb_build_array('instagram')
  ))$$,
  '54000', 'research_user_daily_limit',
  'an eleventh user research request is rejected'
);

insert into content_factory.product_research_runs (
  organization_id, product_id, created_by, status, input,
  request_hash, idempotency_key
)
select
  '93100000-0000-4000-8000-000000000001',
  '93200000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001', 'queued',
  jsonb_build_object('objective', 'organization quota fixture',
    'marketplace_url', 'https://example.test/org-quota/' || series,
    'source_media_ids', '[]'::jsonb, 'platforms', '[]'::jsonb,
    'product_id', '93200000-0000-4000-8000-000000000001'),
  lpad(to_hex(series), 64, 'd'), 'research-org-quota-' || lpad(series::text, 4, '0')
from generate_series(10, 49) series;

do $$ begin
  perform set_config('request.jwt.claim.sub', '93000000-0000-4000-8000-000000000003', true);
end $$;

select throws_ok(
  $$select public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-org-over-limit',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'organization paid research over limit',
    'marketplace_url', 'https://example.test/product/org-over-limit',
    'platforms', jsonb_build_array('instagram')
  ))$$,
  '54000', 'research_org_daily_limit',
  'a fifty-first organization research request is rejected'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '93000000-0000-4000-8000-000000000001', true);
end $$;

select throws_ok(
  $$update content_factory.product_research_sources
    set title = 'rewritten'
    where run_id = (select run_id from research_test_context)$$,
  '55000', 'product_research_sources_immutable',
  'research evidence cannot be rewritten'
);

create temporary table claim_result on commit drop as
select public.system_claim_product_research(jsonb_build_object(
  'run_id', (select run_id from research_test_context)
)) as value;

select ok((select (value ->> 'claimed')::boolean from claim_result), 'first worker atomically claims the run');
select ok(
  (select (value -> 'run' ->> 'lease_expires_at')::timestamptz > now() from claim_result),
  'claim exposes a future hard lease to the Edge worker'
);
select is(
  (select value -> 'run' -> 'photos' -> 0 ->> 'object_name' from claim_result),
  '93100000-0000-4000-8000-000000000001/93000000-0000-4000-8000-000000000001/research/photo.webp',
  'worker receives trusted storage object name from media_objects'
);
select is(
  (select value -> 'run' -> 'photos' -> 0 ->> 'product_id' from claim_result),
  '93200000-0000-4000-8000-000000000001',
  'selected photo is coherently bound to the research product without mutating media'
);
select is((select value -> 'run' -> 'product' ->> 'sku' from claim_result), 'RESEARCH-SKU-1', 'worker receives trusted product SKU');
select is((select value -> 'run' -> 'product' ->> 'brand' from claim_result), 'ALTEA', 'worker receives product brand metadata');
select ok(
  not (public.system_claim_product_research(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  )) ->> 'claimed')::boolean,
  'second worker cannot claim the paid job'
);

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input,
  request_hash, idempotency_key
) values (
  '93400000-0000-4000-8000-000000000001',
  '93100000-0000-4000-8000-000000000001',
  '93200000-0000-4000-8000-000000000001',
  '93000000-0000-4000-8000-000000000001', 'queued',
  jsonb_build_object(
    'objective', 'stale paid worker fixture',
    'marketplace_url', 'https://example.test/stale-worker',
    'source_media_ids', '[]'::jsonb,
    'platforms', jsonb_build_array('instagram'),
    'product_id', '93200000-0000-4000-8000-000000000001'
  ),
  repeat('e', 64), 'research-stale-worker-0001'
);

create temporary table stale_claim_result on commit drop as
select public.system_claim_product_research(jsonb_build_object(
  'run_id', '93400000-0000-4000-8000-000000000001'
)) as value;

update content_factory.product_research_runs
set lease_expires_at = now() - interval '1 second'
where id = '93400000-0000-4000-8000-000000000001';

create temporary table stale_status_result on commit drop as
select public.creator_product_research_status(jsonb_build_object(
  'run_id', '93400000-0000-4000-8000-000000000001'
)) as value;

select is(
  (select value -> 'run' ->> 'status' from stale_status_result),
  'failed',
  'an expired processing lease becomes terminal instead of being reclaimed'
);
select is(
  (select value -> 'run' ->> 'error_code' from stale_status_result),
  'processing_lease_expired',
  'lease expiration has an explicit restart-required error code'
);
select ok(
  not (public.system_claim_product_research(jsonb_build_object(
    'run_id', '93400000-0000-4000-8000-000000000001'
  )) ->> 'claimed')::boolean,
  'a timed-out paid run cannot invoke OpenAI a second time'
);
select throws_ok(
  $$select public.system_complete_product_research(jsonb_build_object(
    'run_id', '93400000-0000-4000-8000-000000000001',
    'status', 'failed',
    'error_code', 'late_worker_timeout'
  ))$$,
  '23505', 'research_completion_conflict',
  'a late uncertain worker cannot overwrite the timeout terminal state'
);

update research_test_context set completion_payload = jsonb_build_object(
  'run_id', run_id,
  'status', 'completed',
  'summary', jsonb_build_object('audience', 'Люди с неровной текстурой кожи'),
  'sources', jsonb_build_array(
    jsonb_build_object(
      'source_type', 'review',
      'source_url', 'https://example.test/product/1/reviews',
      'title', 'Отзывы покупателей',
      'trust_level', 'public',
      'extracted_facts', jsonb_build_array(jsonb_build_object(
        'claim', 'Покупатели обсуждают текстуру', 'confidence', 0.8
      ))
    ),
    jsonb_build_object(
      'source_type', 'product_photo',
      'source_url', null,
      'media_object_id', '93300000-0000-4000-8000-000000000001',
      'title', 'Фото этикетки товара',
      'trust_level', 'first_party',
      'extracted_facts', jsonb_build_array(jsonb_build_object(
        'statement', 'На этикетке видны AHA 30% и BHA 2%',
        'source_ids', jsonb_build_array('photo:1')
      )),
      'metadata', jsonb_build_object(
        'model_source_id', 'photo:1', 'visual_analysis', true
      )
    )
  ),
  'draft', jsonb_build_object(
    'title', 'Пилинг: фактический сценарий',
    'brief', jsonb_build_object('hook', 'Текстура кожи выглядит неровной?'),
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Снять UGC-ролик о пилинге',
      'instructions', 'Показать продукт в первые две секунды.',
      'task_type', 'general',
      'assignee_id', '93000000-0000-4000-8000-000000000001',
      'priority', 2,
      'payout_minor', 0
    ))
  ),
  'forecast', jsonb_build_object(
    'score', 74, 'confidence', 0.62,
    'model_provider', 'openai', 'model_version', 'research-mvp-v1',
    'factors', jsonb_build_object('hook', 80),
    'limitations', jsonb_build_array('Нет исторических метрик аккаунта')
  )
);

create temporary table completion_result on commit drop as
select public.system_complete_product_research(
  (select completion_payload from research_test_context)
) as value;
update research_test_context
set first_draft_id = (select (value ->> 'draft_id')::uuid from completion_result);

select ok((select (value ->> 'ok')::boolean from completion_result), 'worker completes research atomically');
select is((select value ->> 'status' from completion_result), 'completed', 'completion returns terminal status');
select is(
  (select status from content_factory.product_research_runs where id = (select run_id from research_test_context)),
  'completed',
  'run is completed'
);
select ok(
  (select finished_at is not null and completion_hash is not null
   from content_factory.product_research_runs where id = (select run_id from research_test_context)),
  'completion is timestamped and hash-bound'
);
select is(
  (select count(*)::integer from content_factory.product_research_sources
   where run_id = (select run_id from research_test_context)),
  4,
  'worker appends sourced evidence without replacing input evidence'
);
select is(
  (select jsonb_array_length(source.extracted_facts)
   from content_factory.product_research_sources source
   where source.run_id = (select run_id from research_test_context)
     and source.source_type = 'product_photo'
     and source.metadata ->> 'model_source_id' = 'photo:1'),
  1,
  'visual facts are persisted as immutable evidence linked to the trusted input photo'
);
select is(
  (select origin from content_factory.creative_brief_drafts
   where id = (select first_draft_id from research_test_context)),
  'ai',
  'worker creates an explicitly AI-origin draft'
);
select is(
  (select count(*)::integer from content_factory.creative_forecasts
   where draft_id = (select first_draft_id from research_test_context)),
  1,
  'worker stores a source-aware forecast'
);
select is(
  public.system_complete_product_research(
    (select completion_payload from research_test_context)
  ) ->> 'draft_id',
  (select first_draft_id::text from research_test_context),
  'identical worker completion replays without duplicates'
);
select throws_ok(
  $$select public.system_complete_product_research(
    (select completion_payload || '{"summary":{"changed":true}}'::jsonb
     from research_test_context)
  )$$,
  '23505', 'research_completion_conflict',
  'terminal result cannot be replaced by a different completion'
);

select is(
  public.creator_product_research_status(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  )) -> 'run' ->> 'status',
  'completed',
  'multi-organization creator resolves status safely by global run id'
);

select is(
  public.creator_product_research_status(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'run_id', (select run_id from research_test_context)
  )) -> 'run' ->> 'status',
  'completed',
  'creator reads completed research status'
);
select is(
  jsonb_array_length(public.creator_product_research_status(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'run_id', (select run_id from research_test_context)
  )) -> 'sources'),
  3,
  'status returns its citations'
);

update research_test_context context
set save_result = public.creator_save_creative_brief_draft(jsonb_build_object(
  'organization_id', '93100000-0000-4000-8000-000000000001',
  'idempotency_key', 'research-save-draft-0001',
  'run_id', context.run_id,
  'title', 'Отредактированный сценарий пилинга',
  'brief', jsonb_build_object(
    'hook', 'Вот почему кислотный уход оценивают курсом',
    'claims', jsonb_build_array('AHA 30%', 'BHA 2%')
  ),
  'source_ids', (select jsonb_agg(source.id order by source.created_at, source.id)
    from content_factory.product_research_sources source where source.run_id = context.run_id),
  'task_blueprint', jsonb_build_array(jsonb_build_object(
    'title', 'Снять отредактированный ролик',
    'instructions', 'Не обещать медицинский результат.',
    'assignee_id', '93000000-0000-4000-8000-000000000001',
    'priority', 1
  )),
  'forecast', jsonb_build_object(
    'score', 78, 'confidence', 0.66,
    'model_provider', 'human-review', 'model_version', 'manual-v1',
    'factors', jsonb_build_object('clarity', 85),
    'limitations', jsonb_build_array('Предпубликационная оценка')
  )
));
update research_test_context set human_draft_id = (save_result -> 'draft' ->> 'id')::uuid;

select is((select save_result -> 'draft' ->> 'version' from research_test_context), '2', 'human edit creates version two');
select is((select save_result -> 'draft' ->> 'status' from research_test_context), 'draft', 'human edit remains reviewable');
select is(
  public.creator_save_creative_brief_draft(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-save-draft-0001',
    'run_id', (select run_id from research_test_context),
    'title', 'Отредактированный сценарий пилинга',
    'brief', jsonb_build_object('hook', 'Вот почему кислотный уход оценивают курсом',
      'claims', jsonb_build_array('AHA 30%', 'BHA 2%')),
    'source_ids', (select jsonb_agg(source.id order by source.created_at, source.id)
      from content_factory.product_research_sources source
      where source.run_id = (select run_id from research_test_context)),
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Снять отредактированный ролик',
      'instructions', 'Не обещать медицинский результат.',
      'assignee_id', '93000000-0000-4000-8000-000000000001', 'priority', 1)),
    'forecast', jsonb_build_object(
      'score', 78, 'confidence', 0.66, 'model_provider', 'human-review',
      'model_version', 'manual-v1', 'factors', jsonb_build_object('clarity', 85),
      'limitations', jsonb_build_array('Предпубликационная оценка'))
  )) -> 'draft' ->> 'id',
  (select human_draft_id::text from research_test_context),
  'draft save is idempotent'
);
select is(
  (select count(*)::integer from content_factory.creative_brief_drafts
   where run_id = (select run_id from research_test_context)),
  2,
  'draft retry creates no version three'
);
select throws_ok(
  $$select public.creator_save_creative_brief_draft(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-save-bad-source',
    'run_id', (select run_id from research_test_context),
    'title', 'Bad source draft', 'brief', '{}'::jsonb,
    'source_ids', jsonb_build_array('99999999-9999-4999-8999-999999999999'::text),
    'task_blueprint', jsonb_build_array(jsonb_build_object('title', 'Valid task title'))
  ))$$,
  '42501', 'brief_source_mismatch',
  'draft cannot cite a source outside its run'
);

update research_test_context context
set approve_result = public.creator_approve_creative_brief(jsonb_build_object(
  'organization_id', '93100000-0000-4000-8000-000000000001',
  'idempotency_key', 'research-approve-0001',
  'draft_id', context.human_draft_id
));

select ok((select (approve_result ->> 'ok')::boolean from research_test_context), 'certified manager approves the latest draft');
select is((select jsonb_array_length(approve_result -> 'task_ids') from research_test_context), 1, 'approval creates one blueprint task');
select is(
  (select status from content_factory.creative_brief_drafts
   where id = (select human_draft_id from research_test_context)),
  'approved',
  'approved draft is terminal'
);
select is(
  (select count(*)::integer from content_factory.creator_tasks
   where creative_brief_draft_id = (select human_draft_id from research_test_context)),
  1,
  'task has a durable brief foreign key'
);
select is(
  public.creator_product_research_status(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  )) -> 'approval' ->> 'status',
  'approved',
  'status exposes an explicit approved state'
);
select is(
  public.creator_product_research_status(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  )) -> 'task_ids',
  (select approve_result -> 'task_ids' from research_test_context),
  'status recovers every task id created by approval'
);
select is(
  (public.creator_product_research_status(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  )) -> 'approval' ->> 'task_count')::integer,
  1,
  'approval state reports the durable task count'
);
select ok(
  (select result ?& array[
    'product_research_run_id', 'creative_brief_draft_id',
    'brief_version', 'source_ids', 'blueprint_ordinal'
  ] from content_factory.creator_tasks
  where creative_brief_draft_id = (select human_draft_id from research_test_context)),
  'task result carries traceable run, version, and citations'
);
select is(
  public.creator_approve_creative_brief(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-approve-0001',
    'draft_id', (select human_draft_id from research_test_context)
  )) -> 'task_ids',
  (select approve_result -> 'task_ids' from research_test_context),
  'approval retry returns the same tasks'
);
select ok(
  (public.creator_approve_creative_brief(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'research-approve-0002',
    'draft_id', (select human_draft_id from research_test_context)
  )) ->> 'already_approved')::boolean,
  'a new command key still recognizes an approved draft'
);
select is(
  (select count(*)::integer from content_factory.creator_tasks
   where creative_brief_draft_id = (select human_draft_id from research_test_context)),
  1,
  'alternate approval key cannot duplicate tasks'
);
select is(
  (select status from content_factory.creative_brief_drafts
   where id = (select first_draft_id from research_test_context)),
  'superseded',
  'older AI draft is superseded on approval'
);

select throws_ok(
  $$update content_factory.product_research_runs set summary = '{"changed":true}'::jsonb
    where id = (select run_id from research_test_context)$$,
  '55000', 'research_run_terminal',
  'completed research result is immutable'
);
select throws_ok(
  $$update content_factory.creative_brief_drafts set title = 'rewritten'
    where id = (select human_draft_id from research_test_context)$$,
  '55000', 'creative_brief_payload_immutable',
  'brief payload is immutable'
);
select throws_ok(
  $$delete from content_factory.creative_forecasts
    where draft_id = (select human_draft_id from research_test_context)$$,
  '55000', 'creative_forecasts_immutable',
  'forecast history is append-only'
);

do $$ begin
  perform set_config('request.jwt.claim.sub', '93000000-0000-4000-8000-000000000002', true);
end $$;

select throws_ok(
  $$select public.creator_start_product_research(jsonb_build_object(
    'organization_id', '93100000-0000-4000-8000-000000000001',
    'idempotency_key', 'viewer-research-start-0001',
    'product_id', '93200000-0000-4000-8000-000000000001',
    'objective', 'viewer must not spend',
    'marketplace_url', 'https://example.test/viewer'
  ))$$,
  '42501', 'role_not_allowed',
  'viewer cannot start a potentially paid analysis'
);
select throws_ok(
  $$select public.creator_product_research_status(jsonb_build_object(
    'run_id', (select run_id from research_test_context)
  ))$$,
  '42501', 'research_run_not_allowed',
  'viewer cannot read another member research'
);

select * from finish();
rollback;
