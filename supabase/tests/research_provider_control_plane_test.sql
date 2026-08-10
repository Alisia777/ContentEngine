begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

-- TEST-ONLY refreshed-course fixture. The production start RPC retains the
-- complete installed course/practical gate behind the provider-control wrapper.
create or replace function pg_temp.grant_provider_control_course_gate(
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
  for module_row in
    select module.code,
      jsonb_array_length(
        module.content #> '{knowledge_check,questions}'
      ) as question_count
    from content_factory.training_modules module
    where module.module_type = 'course'
      and module.is_active
    order by module.order_index
  loop
    select coalesce(jsonb_object_agg(
      question.code,
      answer_key.correct_answers
      order by question.order_index
    ), '{}'::jsonb)
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
       or (select count(*) from jsonb_object_keys(answers_value))
         <> module_row.question_count then
      raise exception using
        errcode = '55000',
        message = 'test_course_gate_fixture_invalid';
    end if;

    insert into content_factory.training_attempts (
      organization_id, profile_id, module_code, status, score,
      correct_count, answered_count, question_count, passed, answers,
      request_hash, idempotency_key
    ) values (
      p_organization_id, p_profile_id, module_row.code, 'completed', 1,
      module_row.question_count, module_row.question_count,
      module_row.question_count, true, answers_value,
      content_factory_private.json_hash(jsonb_build_object(
        'module_code', module_row.code,
        'answers', answers_value
      )),
      left('course-check:' || p_key_prefix || ':' || module_row.code, 180)
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
      organization_id, profile_id, module_code, attempt_id, status
    ) values (
      p_organization_id, p_profile_id, module_row.code,
      attempt_id_value, 'passed'
    )
    on conflict on constraint
      training_certifications_org_profile_module_uq
    do update set
      attempt_id = excluded.attempt_id,
      status = 'passed',
      granted_at = now(),
      expires_at = null;
  end loop;
end;
$course_gate_fixture$;

select has_table(
  'content_factory', 'research_provider_catalog',
  'provider catalog exists'
);
select has_table(
  'content_factory', 'research_execution_authorizations',
  'immutable execution authorizations exist'
);
select has_table(
  'content_factory', 'research_run_provider_bindings',
  'immutable run-provider bindings exist'
);
select has_table(
  'content_factory', 'research_provider_health_receipts',
  'append-only passive health receipts exist'
);

select has_function(
  'public', 'creator_start_product_research', array['jsonb'],
  'paid research start wrapper exists'
);
select has_function(
  'public', 'system_claim_product_research', array['jsonb'],
  'authorized claim wrapper exists'
);
select has_function(
  'public', 'system_begin_research_provider_attempt', array['jsonb'],
  'service begin-attempt RPC exists'
);
select has_function(
  'public', 'system_record_research_provider_health', array['jsonb'],
  'service passive-health RPC exists'
);
select has_function(
  'public', 'creator_research_provider_status', array['jsonb'],
  'authenticated bounded status RPC exists'
);

select is(
  (select count(*)::integer
   from content_factory.research_provider_catalog),
  2,
  'catalog is an exact two-provider allowlist'
);
select ok(
  exists (
    select 1
    from content_factory.research_provider_catalog catalog
    where catalog.provider_key = 'openai_web_search'
      and catalog.adapter_version = 'openai-responses-web-search-v1'
      and catalog.lifecycle_status = 'active'
      and catalog.billing_mode = 'metered'
      and catalog.health_mode = 'passive'
      and catalog.canary_mode = 'forbidden'
      and not catalog.automatic_canary_allowed
      and not catalog.automatic_fallback_allowed
  ),
  'OpenAI is active, metered, passive-health-only and cannotary'
);
select ok(
  exists (
    select 1
    from content_factory.research_provider_catalog catalog
    where catalog.provider_key = 'youtube_data_api_v3'
      and catalog.adapter_version =
        'youtube-data-api-v3-public-metadata-v1'
      and catalog.lifecycle_status = 'disabled'
      and catalog.rollout_stage = 'planned'
      and catalog.billing_mode = 'quota'
      and catalog.health_mode = 'manual'
      and catalog.canary_mode = 'manual_only'
      and catalog.max_canary_requests = 1
      and catalog.max_canary_cost_minor = 0
      and not catalog.automatic_canary_allowed
      and not catalog.automatic_fallback_allowed
  ),
  'YouTube is planned, disabled, quota-bounded and manual-only'
);
select ok(
  not exists (
    select 1
    from content_factory.research_provider_catalog catalog
    where catalog.automatic_canary_allowed
       or catalog.automatic_fallback_allowed
       or catalog.max_canary_cost_minor <> 0
  ),
  'catalog cannot authorize automatic canaries, fallback, or canary spend'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_provider_catalog'::regclass),
     ('content_factory.research_execution_authorizations'::regclass),
     ('content_factory.research_run_provider_bindings'::regclass),
     ('content_factory.research_provider_health_receipts'::regclass)
   ) protected(table_oid)
   where (select relrowsecurity from pg_class where oid = table_oid)),
  4,
  'all provider-control tables use RLS'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_provider_catalog'::regclass),
     ('content_factory.research_execution_authorizations'::regclass),
     ('content_factory.research_run_provider_bindings'::regclass),
     ('content_factory.research_provider_health_receipts'::regclass)
   ) protected(table_oid)
   where has_table_privilege('authenticated', table_oid, 'select')),
  0,
  'browser sessions have no direct provider-control reads'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_begin_research_provider_attempt',
       'system_record_research_provider_health'
     )
     and has_function_privilege('service_role', procedure.oid, 'execute')),
  2,
  'service role can begin attempts and record passive health'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_product_research',
       'system_begin_research_provider_attempt',
       'system_record_research_provider_health'
     )
     and has_function_privilege('authenticated', procedure.oid, 'execute')),
  0,
  'browser sessions cannot claim or write provider-control facts'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_start_project_research',
       'creator_research_provider_status'
     )
     and has_function_privilege('authenticated', procedure.oid, 'execute')),
  2,
  'authenticated users receive only the narrow start and status RPCs'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'creator_start_project_research',
       'creator_research_provider_status'
     )
     and has_function_privilege('anon', procedure.oid, 'execute')),
  0,
  'anonymous sessions receive no provider-control RPCs'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_product_research_pre_provider_control(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.system_claim_product_research_pre_provider_control(jsonb)',
    'execute'
  ),
  'preserved implementations are callable only through security-definer wrappers'
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
  (
    '98000000-0000-4000-8000-000000000001',
    'provider-control-owner@example.test',
    'Provider Control Owner'
  ),
  (
    '98000000-0000-4000-8000-000000000002',
    'provider-control-reviewer@example.test',
    'Provider Control Reviewer'
  ),
  (
    '98000000-0000-4000-8000-000000000003',
    'provider-control-viewer@example.test',
    'Provider Control Viewer'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  (
    '98100000-0000-4000-8000-000000000001',
    'Provider Control Main', 'provider-control-main', 'active'
  ),
  (
    '98100000-0000-4000-8000-000000000002',
    'Provider Control Other', 'provider-control-other', 'active'
  );

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001', 'owner', 'active'
  ),
  (
    '98100000-0000-4000-8000-000000000002',
    '98000000-0000-4000-8000-000000000001', 'owner', 'active'
  ),
  (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000002', 'reviewer', 'active'
  ),
  (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000003', 'viewer', 'active'
  );

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  '98200000-0000-4000-8000-000000000001',
  '98100000-0000-4000-8000-000000000001',
  'PROVIDER-CONTROL-SKU', 'Provider control test product', 'active',
  '{}'::jsonb,
  '98000000-0000-4000-8000-000000000001'
);

do $training_fixture$
declare
  attempt_id_value uuid;
begin
  perform pg_temp.grant_provider_control_course_gate(
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'provider-control-owner'
  );
  insert into content_factory.training_attempts (
    organization_id, profile_id, module_code, status, score,
    correct_count, answered_count, question_count, passed, answers,
    request_hash, idempotency_key
  ) values (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'operator_final_exam', 'completed', 1, 12, 12, 12, true,
    '{}'::jsonb, repeat('9', 64), 'provider-control-final-exam'
  ) returning id into attempt_id_value;
  insert into content_factory.training_certifications (
    organization_id, profile_id, module_code, attempt_id, status
  ) values (
    '98100000-0000-4000-8000-000000000001',
    '98000000-0000-4000-8000-000000000001',
    'operator_final_exam', attempt_id_value, 'passed'
  );
end;
$training_fixture$;

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  '98000000-0000-4000-8000-000000000001',
  true
);

create temporary table provider_control_context (
  start_result jsonb,
  replay_result jsonb,
  run_id uuid,
  claim_result jsonb,
  begin_result jsonb,
  replay_begin_result jsonb,
  attempt_id uuid,
  checked_at_value timestamptz,
  health_result jsonb,
  replay_health_result jsonb,
  status_result jsonb,
  other_status_result jsonb
) on commit drop;

select throws_ok(
  $$
    select public.creator_start_product_research(jsonb_build_object(
      'organization_id', '98100000-0000-4000-8000-000000000001',
      'idempotency_key', 'provider-control-missing-ack',
      'product_id', '98200000-0000-4000-8000-000000000001',
      'objective', 'Research without an acknowledgement must stop',
      'marketplace_url', 'https://example.test/provider-control/missing',
      'platforms', jsonb_build_array('youtube')
    ))
  $$,
  '22023',
  'paid_analysis_ack_required',
  'start rejects a missing paid-analysis acknowledgement'
);
select throws_ok(
  $$
    select public.creator_start_product_research(jsonb_build_object(
      'organization_id', '98100000-0000-4000-8000-000000000001',
      'idempotency_key', 'provider-control-false-ack',
      'product_id', '98200000-0000-4000-8000-000000000001',
      'objective', 'A false acknowledgement must stop',
      'marketplace_url', 'https://example.test/provider-control/false',
      'platforms', jsonb_build_array('youtube'),
      'paid_analysis_ack', false
    ))
  $$,
  '22023',
  'paid_analysis_ack_required',
  'start rejects a false paid-analysis acknowledgement'
);

insert into provider_control_context (start_result)
select public.creator_start_product_research(jsonb_build_object(
  'organization_id', '98100000-0000-4000-8000-000000000001',
  'idempotency_key', 'provider-control-explicit-start',
  'product_id', '98200000-0000-4000-8000-000000000001',
  'objective', 'Collect source-backed category and competitor evidence',
  'marketplace_url', 'https://example.test/provider-control/product',
  'platforms', jsonb_build_array('youtube', 'wildberries'),
  'paid_analysis_ack', true
));
update provider_control_context
set run_id = (start_result #>> '{run,id}')::uuid;

select ok(
  (select (start_result ->> 'ok')::boolean from provider_control_context),
  'explicitly acknowledged start succeeds'
);
select is(
  (select start_result #>> '{run,status}' from provider_control_context),
  'queued',
  'explicitly acknowledged run is durably queued'
);
select is(
  (select count(*)::integer
   from content_factory.research_execution_authorizations authorization_entry
   where authorization_entry.run_id =
     (select run_id from provider_control_context)),
  1,
  'start stores exactly one execution authorization atomically'
);
select is(
  (select authorization_entry.authorization_kind
   from content_factory.research_execution_authorizations authorization_entry
   where authorization_entry.run_id =
     (select run_id from provider_control_context)),
  'explicit_paid_analysis',
  'new authorization records the explicit gate kind'
);
select ok(
  (select authorization_entry.paid_analysis_ack
   from content_factory.research_execution_authorizations authorization_entry
   where authorization_entry.run_id =
     (select run_id from provider_control_context)),
  'new authorization stores the server-validated acknowledgement'
);
select ok(
  exists (
    select 1
    from content_factory.research_execution_authorizations authorization_entry
    where authorization_entry.run_id =
      (select run_id from provider_control_context)
      and authorization_entry.provider_key = 'openai_web_search'
      and authorization_entry.adapter_version = 'openai-responses-web-search-v1'
      and authorization_entry.max_provider_attempts = 1
      and not authorization_entry.automatic_fallback_allowed
  ),
  'authorization fixes one provider attempt and forbids fallback'
);

update provider_control_context
set replay_result = public.creator_start_product_research(jsonb_build_object(
  'organization_id', '98100000-0000-4000-8000-000000000001',
  'idempotency_key', 'provider-control-explicit-start',
  'product_id', '98200000-0000-4000-8000-000000000001',
  'objective', 'Collect source-backed category and competitor evidence',
  'marketplace_url', 'https://example.test/provider-control/product',
  'platforms', jsonb_build_array('youtube', 'wildberries'),
  'paid_analysis_ack', true
));
select is(
  (select replay_result #>> '{run,id}' from provider_control_context),
  (select run_id::text from provider_control_context),
  'acknowledged start replay returns the exact existing run'
);
select is(
  (select count(*)::integer
   from content_factory.research_execution_authorizations authorization_entry
   where authorization_entry.run_id =
     (select run_id from provider_control_context)),
  1,
  'acknowledged replay cannot duplicate authorization'
);
select throws_ok(
  $$
    select public.creator_start_product_research(jsonb_build_object(
      'organization_id', '98100000-0000-4000-8000-000000000001',
      'idempotency_key', 'provider-control-explicit-start',
      'product_id', '98200000-0000-4000-8000-000000000001',
      'objective', 'Changed objective must conflict',
      'marketplace_url', 'https://example.test/provider-control/product',
      'platforms', jsonb_build_array('youtube', 'wildberries'),
      'paid_analysis_ack', true
    ))
  $$,
  '23505',
  'idempotency_key_conflict',
  'changed replay cannot reuse the start idempotency key'
);

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input,
  request_hash, idempotency_key
) values (
  '98300000-0000-4000-8000-000000000001',
  '98100000-0000-4000-8000-000000000001',
  '98200000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000001',
  'queued',
  jsonb_build_object(
    'objective', 'Hand-inserted unauthorized run',
    'marketplace_url', 'https://example.test/provider-control/unauthorized',
    'source_media_ids', '[]'::jsonb,
    'platforms', jsonb_build_array('youtube')
  ),
  repeat('a', 64),
  'provider-control-unauthorized-run'
);
select throws_ok(
  $$
    select public.system_claim_product_research(jsonb_build_object(
      'run_id', '98300000-0000-4000-8000-000000000001'
    ))
  $$,
  '55000',
  'research_execution_authorization_required',
  'claim refuses a queued run without an execution authorization'
);

insert into content_factory.research_execution_authorizations (
  organization_id, run_id, authorized_by, authorization_kind,
  paid_analysis_ack, provider_key, adapter_version, run_request_hash,
  max_provider_attempts, automatic_fallback_allowed, reason_code,
  authorized_at, authorization_hash
) values (
  '98100000-0000-4000-8000-000000000001',
  '98300000-0000-4000-8000-000000000001',
  '98000000-0000-4000-8000-000000000001',
  'legacy_pre_gate', false, 'openai_web_search',
  'openai-responses-web-search-v1', repeat('a', 64), 1, false,
  'migration_legacy_pre_gate', now() - interval '1 day',
  content_factory_private.json_hash(jsonb_build_object(
    'fixture', 'explicit-legacy-pre-gate-receipt'
  ))
);
select is(
  (public.system_claim_product_research(jsonb_build_object(
    'run_id', '98300000-0000-4000-8000-000000000001'
  )) ->> 'claimed')::boolean,
  true,
  'an explicit legacy-pre-gate receipt transparently preserves queued work'
);
select ok(
  exists (
    select 1
    from content_factory.research_execution_authorizations authorization_entry
    where authorization_entry.run_id =
      '98300000-0000-4000-8000-000000000001'
      and authorization_entry.authorization_kind = 'legacy_pre_gate'
      and not authorization_entry.paid_analysis_ack
      and authorization_entry.reason_code = 'migration_legacy_pre_gate'
  ),
  'legacy compatibility is explicit and never masquerades as a new ACK'
);

update provider_control_context
set claim_result = public.system_claim_product_research(jsonb_build_object(
  'run_id', run_id
));
select ok(
  (select (claim_result ->> 'claimed')::boolean
   from provider_control_context),
  'authorized worker atomically claims the run'
);
select is(
  (select status
   from content_factory.product_research_runs
   where id = (select run_id from provider_control_context)),
  'processing',
  'claimed run enters processing with its original lease contract'
);

update provider_control_context
set begin_result = public.system_begin_research_provider_attempt(
  jsonb_build_object(
    'run_id', run_id,
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'model', 'gpt-5.5'
  )
);
update provider_control_context
set attempt_id = (begin_result ->> 'attempt_id')::uuid;
select ok(
  (select (begin_result ->> 'ok')::boolean
   from provider_control_context),
  'service begins the exact authorized provider attempt'
);
select is(
  (select begin_result ->> 'provider_key'
   from provider_control_context),
  'openai_web_search',
  'begin response returns the exact bound provider'
);
select is(
  (select count(*)::integer
   from content_factory.research_run_provider_bindings binding
   where binding.run_id = (select run_id from provider_control_context)),
  1,
  'one run receives one immutable provider binding'
);

update provider_control_context
set replay_begin_result = public.system_begin_research_provider_attempt(
  jsonb_build_object(
    'run_id', run_id,
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'model', 'gpt-5.5'
  )
);
select is(
  (select replay_begin_result ->> 'attempt_id'
   from provider_control_context),
  (select attempt_id::text from provider_control_context),
  'identical begin replay returns the exact attempt'
);
select throws_ok(
  format(
    $sql$
      select public.system_begin_research_provider_attempt(jsonb_build_object(
        'run_id', %L,
        'provider_key', 'openai_web_search',
        'adapter_version', 'openai-responses-web-search-v1',
        'model', 'different-model'
      ))
    $sql$,
    (select run_id::text from provider_control_context)
  ),
  '23505',
  'research_provider_attempt_conflict',
  'a run cannot silently switch model after its provider binding'
);
select throws_ok(
  format(
    $sql$
      select public.system_begin_research_provider_attempt(jsonb_build_object(
        'run_id', %L,
        'provider_key', 'youtube_data_api_v3',
        'adapter_version', 'youtube-data-api-v3-public-metadata-v1',
        'model', 'public-metadata'
      ))
    $sql$,
    (select run_id::text from provider_control_context)
  ),
  '55000',
  'research_provider_attempt_not_authorized',
  'begin never auto-falls back to the planned provider'
);

update provider_control_context
set checked_at_value = clock_timestamp();
update provider_control_context
set health_result = public.system_record_research_provider_health(
  jsonb_build_object(
    'attempt_id', attempt_id,
    'status', 'ready',
    'citation_count', 3,
    'checked_at', checked_at_value
  )
);
update provider_control_context
set replay_health_result = public.system_record_research_provider_health(
  jsonb_build_object(
    'attempt_id', attempt_id,
    'status', 'ready',
    'citation_count', 3,
    'checked_at', checked_at_value
  )
);
select ok(
  (select (health_result ->> 'ok')::boolean
   from provider_control_context),
  'service records a bounded passive health fact'
);
select ok(
  exists (
    select 1
    from content_factory.research_provider_health_receipts receipt
    where receipt.id = (
      select (health_result ->> 'receipt_id')::uuid
      from provider_control_context
    )
      and receipt.check_kind = 'passive_execution'
      and not receipt.provider_request_created
      and receipt.actual_cost_minor = 0
      and receipt.citation_count = 3
  ),
  'health receipt cannot claim a canary call or a control-plane cost'
);
select is(
  (select replay_health_result ->> 'receipt_id'
   from provider_control_context),
  (select health_result ->> 'receipt_id'
   from provider_control_context),
  'identical passive-health replay is idempotent'
);
select throws_ok(
  format(
    $sql$
      select public.system_record_research_provider_health(
        jsonb_build_object(
          'attempt_id', %L,
          'status', 'ready',
          'citation_count', 4,
          'checked_at', %L
        )
      )
    $sql$,
    (select attempt_id::text from provider_control_context),
    (select checked_at_value::text from provider_control_context)
  ),
  '23505',
  'research_provider_health_conflict',
  'same attempt/status cannot rewrite a passive health fact'
);

update provider_control_context
set status_result = public.creator_research_provider_status(
  jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001',
    'run_id', run_id
  )
);
select ok(
  (select (status_result ->> 'ok')::boolean
   from provider_control_context),
  'authorized member reads provider control status'
);
select is(
  (select jsonb_array_length(status_result -> 'providers')
   from provider_control_context),
  2,
  'status response is bounded to the allowlisted providers'
);
select ok(
  position(
    'credential_reference'
    in (select status_result::text from provider_control_context)
  ) = 0
  and position(
    'OPENAI_API_KEY'
    in (select status_result::text from provider_control_context)
  ) = 0,
  'status never exposes logical credential references or secret names'
);
select ok(
  (select (status_result #>>
    '{controls,explicit_paid_analysis_required}')::boolean
   from provider_control_context)
  and not (select (status_result #>>
    '{controls,creates_research_runs}')::boolean
   from provider_control_context)
  and not (select (status_result #>>
    '{controls,automatic_canary}')::boolean
   from provider_control_context)
  and not (select (status_result #>>
    '{controls,automatic_fallback}')::boolean
   from provider_control_context)
  and not (select (status_result #>>
    '{controls,external_call_performed}')::boolean
   from provider_control_context),
  'status makes the no-auto-spend control boundary explicit'
);
select ok(
  (select (status_result #>> '{run_control,authorized}')::boolean
   from provider_control_context)
  and (select status_result #>> '{run_control,attempt,attempt_id}'
       from provider_control_context)
    = (select attempt_id::text from provider_control_context),
  'run status exposes its authorization and exact immutable attempt'
);
select is(
  (
    select provider -> 'health' ->> 'status'
    from provider_control_context context,
      jsonb_array_elements(context.status_result -> 'providers') provider
    where provider ->> 'provider_key' = 'openai_web_search'
  ),
  'ready',
  'tenant status includes the fresh passive OpenAI health receipt'
);

select throws_ok(
  format(
    $sql$
      select public.creator_research_provider_status(jsonb_build_object(
        'organization_id', '98100000-0000-4000-8000-000000000002',
        'run_id', %L
      ))
    $sql$,
    (select run_id::text from provider_control_context)
  ),
  '22023',
  'research_run_not_found',
  'cross-tenant run status is indistinguishable from a missing run'
);
update provider_control_context
set other_status_result = public.creator_research_provider_status(
  jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000002'
  )
);
select is(
  (
    select provider -> 'health' ->> 'status'
    from provider_control_context context,
      jsonb_array_elements(context.other_status_result -> 'providers') provider
    where provider ->> 'provider_key' = 'openai_web_search'
  ),
  'unknown',
  'passive health does not leak across organizations'
);

select set_config(
  'request.jwt.claim.sub',
  '98000000-0000-4000-8000-000000000002',
  true
);
select ok(
  (public.creator_research_provider_status(jsonb_build_object(
    'organization_id', '98100000-0000-4000-8000-000000000001'
  )) ->> 'ok')::boolean,
  'reviewer can read bounded provider status'
);
select set_config(
  'request.jwt.claim.sub',
  '98000000-0000-4000-8000-000000000003',
  true
);
select throws_ok(
  $$
    select public.creator_research_provider_status(jsonb_build_object(
      'organization_id', '98100000-0000-4000-8000-000000000001'
    ))
  $$,
  '42501',
  'role_not_allowed',
  'viewer cannot read provider control status'
);
select set_config(
  'request.jwt.claim.sub',
  '98000000-0000-4000-8000-000000000001',
  true
);

select throws_ok(
  $$
    update content_factory.research_provider_catalog
    set display_name = display_name
    where provider_key = 'openai_web_search'
  $$,
  '55000',
  'research_provider_catalog_immutable',
  'provider allowlist is immutable'
);
select throws_ok(
  format(
    $sql$
      update content_factory.research_execution_authorizations
      set reason_code = reason_code
      where run_id = %L
    $sql$,
    (select run_id::text from provider_control_context)
  ),
  '55000',
  'research_execution_authorizations_immutable',
  'execution authorization is immutable'
);
select throws_ok(
  format(
    $sql$
      delete from content_factory.research_run_provider_bindings
      where id = %L
    $sql$,
    (select attempt_id::text from provider_control_context)
  ),
  '55000',
  'research_run_provider_bindings_immutable',
  'run-provider binding is immutable'
);
select throws_ok(
  format(
    $sql$
      update content_factory.research_provider_health_receipts
      set citation_count = citation_count
      where id = %L
    $sql$,
    (select health_result ->> 'receipt_id'
     from provider_control_context)
  ),
  '55000',
  'research_provider_health_receipts_immutable',
  'passive health receipt is append-only'
);

select matches(
  pg_get_functiondef(
    'public.creator_start_product_research(jsonb)'::regprocedure
  ),
  'paid_analysis_ack_required',
  'start wrapper contains the fail-closed server acknowledgement gate'::text
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_claim_product_research(jsonb)'::regprocedure
  )), 'system_claim_product_research_pre_exact_video_v1') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_claim_product_research_pre_exact_video_v1(jsonb)'::regprocedure
  )), 'system_claim_product_research_pre_background_v417') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_claim_product_research_pre_background_v417(jsonb)'::regprocedure
  )), 'system_claim_product_research_pre_stage_recompute_v3') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.system_claim_product_research_pre_stage_recompute_v3(jsonb)'::regprocedure
  )), 'research_execution_authorization_required') > 0,
  'exact claim wrapper delegates only through the immutable authorization gate'
);
select ok(
  position(
    'product_research_runs'
    in pg_get_functiondef(
      'public.creator_research_provider_status(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'insert into content_factory.product_research_runs'
    in lower(pg_get_functiondef(
      'public.creator_research_provider_status(jsonb)'::regprocedure
    ))
  ) = 0,
  'status may inspect a run but can never create one'
);

select * from finish();
rollback;
