begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

create or replace function pg_temp.generation_spec_prompt(
  product_name_value text,
  sku_value text,
  duration_value integer
)
returns text
language sql
stable
as $prompt$
  select format(
    'Точный товар: %s, артикул %s. Создай один непрерывный вертикальный ролик длительностью %s секунд. Без речи, дикторского текста и сгенерированных надписей. Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений. Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.',
    product_name_value,
    sku_value,
    duration_value
  ) || ' ' || content_factory_private
    .generation_product_interaction_requirement(product_name_value, 'other');
$prompt$;

select ok(
  to_regclass('content_factory.generation_spec_versions') is not null
  and to_regclass('content_factory.generation_spec_approval_events') is not null
  and to_regclass('content_factory.generation_spec_head_events') is not null
  and to_regclass('content_factory.generation_job_spec_bindings') is not null,
  'the immutable version, approval, head, and job-binding ledgers exist'
);

select ok(
  has_function_privilege(
    'authenticated', 'public.creator_prepare_generation_spec(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated', 'public.creator_control_generation_spec(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated', 'public.creator_generation_spec_status(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_generation_spec_effective_policy(jsonb)', 'execute'
  ),
  'authenticated creators reach the four narrow generation-spec RPCs'
);

select ok(
  not has_function_privilege(
    'anon', 'public.creator_prepare_generation_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role', 'public.creator_control_generation_spec(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.create_generation_spec_version(uuid,uuid,uuid,jsonb,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,uuid,text,uuid)',
    'execute'
  ),
  'anonymous, worker, and authenticated callers cannot bypass the RPC seams'
);

select ok(
  not has_table_privilege(
    'authenticated', 'content_factory.generation_spec_versions', 'insert'
  )
  and not has_table_privilege(
    'service_role', 'content_factory.generation_spec_versions', 'insert'
  )
  and not has_table_privilege(
    'authenticated', 'content_factory.generation_spec_head_events', 'update'
  )
  and not has_table_privilege(
    'service_role', 'content_factory.generation_job_spec_bindings', 'delete'
  ),
  'direct writes are revoked even from authenticated and service roles'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger
    where trigger.tgrelid = 'content_factory.generation_jobs'::regclass
      and trigger.tgname = 'a_generation_spec_binding_guard'
      and not trigger.tgisinternal
  )
  and exists (
    select 1
    from pg_trigger trigger
    where trigger.tgrelid = 'content_factory.generation_jobs'::regclass
      and trigger.tgname = 'b_generation_spec_provider_start_guard'
      and not trigger.tgisinternal
  ),
  'paid insert and queued-to-starting both have database spec guards'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'f1000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'generation-spec-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Generation Spec Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'f1100000-0000-4000-8000-000000000001',
  'Generation Spec pgTAP',
  'generation-spec-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'f1100000-0000-4000-8000-000000000001',
  'f1000000-0000-4000-8000-000000000001',
  'owner', 'active'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'f1150000-0000-4000-8000-000000000001',
  'f1100000-0000-4000-8000-000000000001', null,
  'Generation Spec project', 'blue', 'project', null,
  'active', 1024,
  'f1000000-0000-4000-8000-000000000001',
  'f1000000-0000-4000-8000-000000000001'
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'f1150000-0000-4000-8000-000000000002',
  'f1100000-0000-4000-8000-000000000001', null,
  'Other generation spec project', 'violet', 'project', null,
  'active', 2048,
  'f1000000-0000-4000-8000-000000000001',
  'f1000000-0000-4000-8000-000000000001'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'f1100000-0000-4000-8000-000000000001',
  'f1000000-0000-4000-8000-000000000001',
  'owner', 'owner',
  'TEST-ONLY waiver for generation spec control pgTAP coverage.',
  'f1000000-0000-4000-8000-000000000001'
);

insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
) values (
  'f1100000-0000-4000-8000-000000000001',
  true, 1000, 10000, 100,
  'USD', 'Europe/Moscow', 1,
  'Generation spec pgTAP fixture policy.',
  'f1000000-0000-4000-8000-000000000001'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'f1200000-0000-4000-8000-000000000001',
  'f1100000-0000-4000-8000-000000000001',
  'GEN-SPEC-1', 'Generation spec product', 'active',
  'f1000000-0000-4000-8000-000000000001'
);

insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'f1300000-0000-4000-8000-000000000001',
  'f1100000-0000-4000-8000-000000000001',
  'f1150000-0000-4000-8000-000000000001',
  'f1000000-0000-4000-8000-000000000001',
  'f1200000-0000-4000-8000-000000000001',
  'contentengine-private',
  'f1100000-0000-4000-8000-000000000001/f1000000-0000-4000-8000-000000000001/uploads/spec-source.jpg',
  'image/jpeg', 2048, repeat('a', 64), 'ready',
  '{"kind":"product_photo","original_filename":"spec-source.jpg","rights_confirmed":true}'::jsonb,
  'generation-spec-source-0001'
);

create temporary table generation_spec_test_state (
  prompt_text text not null,
  prepare_result jsonb,
  approve_result jsonb,
  effective_result jsonb,
  start_result jsonb,
  patch_result jsonb,
  stale_claim_result jsonb,
  before_failure_counts jsonb,
  bounded_performance_claim_succeeded boolean not null default false,
  fresh_claim_succeeded boolean not null default false,
  unexpected_fault_rethrown boolean not null default false,
  missing_binding_rejected boolean not null default false
) on commit drop;

insert into generation_spec_test_state (prompt_text)
values (pg_temp.generation_spec_prompt(
  'Generation spec product', 'GEN-SPEC-1', 5
));

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'f1000000-0000-4000-8000-000000000001',
    true
  );
  perform set_config(
    'contentengine.project_id',
    'f1150000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

do $bounded_performance$
declare
  policy_value jsonb;
  learning_context_value jsonb;
  prompt_requirements text[];
  bounded_prompt text;
  prepare_value jsonb;
  approve_value jsonb;
  start_value jsonb;
  claim_value jsonb;
  claim_succeeded boolean := false;
begin
  begin
    policy_value := public.creator_generation_learning_policy(
      jsonb_build_object(
        'organization_id', 'f1100000-0000-4000-8000-000000000001',
        'project_id', 'f1150000-0000-4000-8000-000000000001',
        'media_id', 'f1300000-0000-4000-8000-000000000001',
        'platform', 'wildberries',
        'model', 'gen4_turbo',
        'product_category', 'other'
      )
    );
    if policy_value ->> 'selection_mode' <> 'bounded_exploration'
       or policy_value -> 'applied' is distinct from 'true'::jsonb then
      raise exception 'bounded_performance_fixture_policy_invalid';
    end if;
    learning_context_value := jsonb_build_object(
      'creative_angle', policy_value ->> 'preferred_angle',
      'hook_patterns', policy_value -> 'preferred_hook_patterns',
      'source', 'performance_learning',
      'compiler_version', 'safe-brief-v7',
      'applied_policy_hash', policy_value ->> 'policy_hash',
      'product_category', 'other'
    );
    prompt_requirements := content_factory_private
      .generation_learning_prompt_requirements(
        policy_value, 'gen4_turbo'
      );
    if prompt_requirements is null
       or cardinality(prompt_requirements) = 0 then
      raise exception 'bounded_performance_prompt_requirements_invalid';
    end if;
    select state.prompt_text || ' ' ||
      array_to_string(prompt_requirements, ' ')
      into bounded_prompt
    from generation_spec_test_state state;
    select public.creator_prepare_generation_spec(jsonb_build_object(
      'organization_id', 'f1100000-0000-4000-8000-000000000001',
      'project_id', 'f1150000-0000-4000-8000-000000000001',
      'idempotency_key', 'generation-spec-bounded-prepare-0001',
      'exact_scope', jsonb_build_object(
        'primary_media_id', 'f1300000-0000-4000-8000-000000000001',
        'media_ids', jsonb_build_array(
          'f1300000-0000-4000-8000-000000000001'
        ),
        'platform', 'wildberries', 'model', 'gen4_turbo',
        'duration_seconds', 5, 'product_category', 'other',
        'format', '9:16', 'audio', false
      ),
      'editable_intent',
        'Exercise the current bounded learning choice under explicit approval.',
      'proposed_prompt', bounded_prompt,
      'learning_context', learning_context_value,
      'repair_context', null,
      'research_provenance', null,
      'performance_policy_provenance', jsonb_build_object(
        'policy_hash', policy_value ->> 'policy_hash',
        'policy_version', policy_value ->> 'version'
      ),
      'repair_provenance', null,
      'confirmation', true,
      'reason', 'Prepare a bounded performance-learning specification.'
    )) into prepare_value
    from generation_spec_test_state state;
    approve_value := public.creator_control_generation_spec(
      jsonb_build_object(
        'organization_id', 'f1100000-0000-4000-8000-000000000001',
        'project_id', 'f1150000-0000-4000-8000-000000000001',
        'spec_id', prepare_value #>> '{generation_spec,spec_id}',
        'expected_spec_version',
          (prepare_value #>> '{generation_spec,spec_version}')::integer,
        'expected_spec_hash', prepare_value #>> '{generation_spec,spec_hash}',
        'action', 'approve', 'confirmation', true,
        'reason', 'Approve the exact bounded performance-learning handoff.',
        'idempotency_key', 'generation-spec-bounded-approve-0001'
      )
    );
    select public.creator_start_real_generation(jsonb_build_object(
      'organization_id', 'f1100000-0000-4000-8000-000000000001',
      'project_id', 'f1150000-0000-4000-8000-000000000001',
      'campaign_id', (
        select id from content_factory.generation_campaigns
        where organization_id = 'f1100000-0000-4000-8000-000000000001'
          and kind = 'default'
      ),
      'idempotency_key', 'generation-spec-bounded-start-0001',
      'sku', 'GEN-SPEC-1', 'product_name', 'Generation spec product',
      'product_category', 'other', 'count', 1, 'format', '9:16',
      'brief', bounded_prompt,
      'media_ids', jsonb_build_array(
        'f1300000-0000-4000-8000-000000000001'
      ),
      'platform', 'wildberries',
      'destination_ref', 'wb-generation-spec-bounded',
      'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
      'duration_seconds', 5, 'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'learning_context', learning_context_value,
      'review_autostart_confirmed', true,
      'review_autostart_terms_version', 'generated-video-qa-autostart-v1',
      'generation_spec_context', jsonb_build_object(
        'spec_id', approve_value #>> '{generation_spec,spec_id}',
        'spec_version',
          (approve_value #>> '{generation_spec,spec_version}')::integer,
        'spec_hash', approve_value #>> '{generation_spec,spec_hash}'
      )
    )) into start_value
    from generation_spec_test_state state;
    claim_value := public.system_update_real_generation(jsonb_build_object(
      'job_id', start_value #>> '{job,id}',
      'status', 'starting'
    ));
    claim_succeeded :=
      claim_value -> 'ok' = 'true'::jsonb
      and claim_value -> 'claimed' = 'true'::jsonb
      and claim_value #>> '{job,status}' = 'starting';
    if not claim_succeeded then
      raise exception 'bounded_performance_claim_failed';
    end if;
    -- Roll the isolated fixture back after proving the complete consumption
    -- boundary. The primary baseline fixture below remains easy to inspect.
    raise exception 'rollback_bounded_performance_fixture';
  exception when raise_exception then
    if sqlerrm <> 'rollback_bounded_performance_fixture' then
      raise;
    end if;
  end;
  update generation_spec_test_state
  set bounded_performance_claim_succeeded = claim_succeeded;
end;
$bounded_performance$;

select ok(
  (select bounded_performance_claim_succeeded
   from generation_spec_test_state)
  and not exists (
    select 1 from content_factory.generation_batches
    where idempotency_key = 'generation-spec-bounded-start-0001'
  ),
  'bounded performance learning survives only its own exact queued-signal drift'
);

update generation_spec_test_state state
set prepare_result = public.creator_prepare_generation_spec(
  jsonb_build_object(
    'organization_id', 'f1100000-0000-4000-8000-000000000001',
    'project_id', 'f1150000-0000-4000-8000-000000000001',
    'idempotency_key', 'generation-spec-prepare-0001',
    'exact_scope', jsonb_build_object(
      'primary_media_id', 'f1300000-0000-4000-8000-000000000001',
      'media_ids', jsonb_build_array(
        'f1300000-0000-4000-8000-000000000001'
      ),
      'platform', 'wildberries',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'product_category', 'other',
      'format', '9:16',
      'audio', false
    ),
    'editable_intent',
      'Show the exact product in one simple, trustworthy interaction.',
    'proposed_prompt', state.prompt_text,
    'learning_context', jsonb_build_object(
      'creative_angle', 'product_focus',
      'hook_patterns', '[]'::jsonb,
      'source', 'baseline',
      'compiler_version', 'safe-brief-v7',
      'product_category', 'other'
    ),
    'repair_context', null,
    'research_provenance', null,
    'performance_policy_provenance', null,
    'repair_provenance', null,
    'confirmation', true,
    'reason', 'Prepare an explicit baseline generation specification.'
  )
);

select ok(
  (select prepare_result - array[
    'ok', 'version', 'generation_spec', 'history',
    'recommended_next_action', 'automatic_approval',
    'automatic_spend', 'automatic_generation'
  ]::text[] = '{}'::jsonb from generation_spec_test_state)
  and (select prepare_result ->> 'version' = 'generation-spec-control-v1'
    from generation_spec_test_state),
  'prepare returns only the bounded generation-spec-control-v1 envelope'
);

select ok(
  (select prepare_result #>> '{generation_spec,status}' = 'draft'
    and jsonb_array_length(prepare_result -> 'history') = 1
    and prepare_result #>> '{recommended_next_action,action}' = 'approve'
    and prepare_result -> 'automatic_approval' = 'false'::jsonb
    and prepare_result -> 'automatic_spend' = 'false'::jsonb
    and prepare_result -> 'automatic_generation' = 'false'::jsonb
    from generation_spec_test_state),
  'prepare creates a draft with one recommendation and no automatic action'
);

select is(
  (select prepare_result #>> '{generation_spec,outcome_selection_id}'
   from generation_spec_test_state),
  null,
  'a new-category baseline specification requires no outcome selection'
);

select throws_ok(
  $$
    update content_factory.generation_spec_versions
    set reason = 'Attempted mutation of immutable version.'
    where spec_id = (
      select (prepare_result #>> '{generation_spec,spec_id}')::uuid
      from generation_spec_test_state
    )
  $$,
  '55000',
  'generation_spec_ledger_append_only',
  'approved handoff versions cannot be updated in place'
);

update generation_spec_test_state state
set approve_result = public.creator_control_generation_spec(
  jsonb_build_object(
    'organization_id', 'f1100000-0000-4000-8000-000000000001',
    'project_id', 'f1150000-0000-4000-8000-000000000001',
    'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
    'expected_spec_version',
      (state.prepare_result #>> '{generation_spec,spec_version}')::integer,
    'expected_spec_hash',
      state.prepare_result #>> '{generation_spec,spec_hash}',
    'action', 'approve',
    'confirmation', true,
    'reason', 'Human reviewed the exact prompt, scope, and provenance.',
    'idempotency_key', 'generation-spec-approve-0001'
  )
);

select ok(
  (select approve_result #>> '{generation_spec,status}' = 'approved'
    and approve_result #>> '{recommended_next_action,action}' = 'confirm_spend'
    and approve_result #> '{generation_spec,approved_at}' is not null
    and jsonb_array_length(approve_result -> 'history') = 1
    from generation_spec_test_state),
  'explicit approval preserves the version and exposes confirm_spend only'
);

select lives_ok(
  $$
    select public.creator_generation_spec_status(jsonb_build_object(
      'organization_id', 'f1100000-0000-4000-8000-000000000001',
      'project_id', 'f1150000-0000-4000-8000-000000000001',
      'spec_id', approve_result #>> '{generation_spec,spec_id}',
      'spec_version',
        (approve_result #>> '{generation_spec,spec_version}')::integer,
      'spec_hash', approve_result #>> '{generation_spec,spec_hash}'
    ))
    from generation_spec_test_state
  $$,
  'status accepts and revalidates the exact approved identity'
);

update generation_spec_test_state state
set effective_result = public.creator_generation_spec_effective_policy(
  jsonb_build_object(
    'organization_id', 'f1100000-0000-4000-8000-000000000001',
    'project_id', 'f1150000-0000-4000-8000-000000000001',
    'spec_id', state.approve_result #>> '{generation_spec,spec_id}',
    'spec_version',
      (state.approve_result #>> '{generation_spec,spec_version}')::integer,
    'spec_hash', state.approve_result #>> '{generation_spec,spec_hash}'
  )
);

select ok(
  (select effective_result - array[
    'ok', 'version', 'project_id', 'generation_spec_context', 'status', 'exact_scope',
    'compiled_prompt', 'prompt_hash', 'learning_context', 'repair_context',
    'final_policy_hash', 'outcome_selection', 'automatic_approval',
    'automatic_spend', 'automatic_generation'
  ]::text[] = '{}'::jsonb
  and effective_result ->> 'project_id' =
    'f1150000-0000-4000-8000-000000000001'
  and effective_result ->> 'status' = 'approved_current'
  and effective_result -> 'repair_context' = 'null'::jsonb
  and effective_result -> 'outcome_selection' = 'null'::jsonb
  from generation_spec_test_state),
  'effective policy exposes only the strict approved Edge handoff'
);

select throws_ok(
  $$
    select public.creator_generation_spec_effective_policy(
      jsonb_build_object(
        'organization_id', 'f1100000-0000-4000-8000-000000000001',
        'spec_id', approve_result #>> '{generation_spec,spec_id}',
        'spec_version',
          (approve_result #>> '{generation_spec,spec_version}')::integer,
        'spec_hash', approve_result #>> '{generation_spec,spec_hash}'
      )
    )
    from generation_spec_test_state
  $$,
  '22023',
  'project_id_required',
  'effective policy never falls back to ambient project context'
);

select throws_ok(
  $$
    select public.creator_generation_spec_effective_policy(
      jsonb_build_object(
        'organization_id', 'f1100000-0000-4000-8000-000000000001',
        'project_id', 'f1150000-0000-4000-8000-000000000002',
        'spec_id', approve_result #>> '{generation_spec,spec_id}',
        'spec_version',
          (approve_result #>> '{generation_spec,spec_version}')::integer,
        'spec_hash', approve_result #>> '{generation_spec,spec_hash}'
      )
    )
    from generation_spec_test_state
  $$,
  '42501',
  'generation_spec_project_scope_mismatch',
  'effective policy rejects a valid but foreign project for the exact spec'
);

select is(
  (select effective_result ->> 'prompt_hash'
   from generation_spec_test_state),
  (select encode(
    extensions.digest(convert_to(prompt_text, 'UTF8'), 'sha256'), 'hex'
   ) from generation_spec_test_state),
  'prompt_hash is SHA-256 of the raw UTF-8 prompt, not JSON encoding'
);

update generation_spec_test_state state
set before_failure_counts = jsonb_build_object(
  'batches', (select count(*) from content_factory.generation_batches
    where organization_id = 'f1100000-0000-4000-8000-000000000001'),
  'jobs', (select count(*) from content_factory.generation_jobs
    where organization_id = 'f1100000-0000-4000-8000-000000000001'),
  'tasks', (select count(*) from content_factory.creator_tasks
    where organization_id = 'f1100000-0000-4000-8000-000000000001'),
  'spend', (select count(*) from content_factory.generation_spend_ledger
    where organization_id = 'f1100000-0000-4000-8000-000000000001')
);

select throws_ok(
  format($sql$
    select public.creator_start_real_generation(%L::jsonb)
  $sql$, (
    select jsonb_build_object(
      'organization_id', 'f1100000-0000-4000-8000-000000000001',
      'project_id', 'f1150000-0000-4000-8000-000000000001',
      'campaign_id', (
        select id from content_factory.generation_campaigns
        where organization_id = 'f1100000-0000-4000-8000-000000000001'
          and kind = 'default'
      ),
      'idempotency_key', 'generation-spec-missing-0001',
      'sku', 'GEN-SPEC-1',
      'product_name', 'Generation spec product',
      'product_category', 'other',
      'count', 1, 'format', '9:16', 'brief', state.prompt_text,
      'media_ids', jsonb_build_array(
        'f1300000-0000-4000-8000-000000000001'
      ),
      'platform', 'wildberries',
      'destination_ref', 'wb-generation-spec',
      'mode', 'real', 'provider', 'runway',
      'model', 'gen4_turbo', 'duration_seconds', 5,
      'allow_real_spend', true,
      'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
      'learning_context', jsonb_build_object(
        'creative_angle', 'product_focus', 'hook_patterns', '[]'::jsonb,
        'source', 'baseline', 'compiler_version', 'safe-brief-v7',
        'product_category', 'other'
      ),
      'review_autostart_confirmed', true,
      'review_autostart_terms_version', 'generated-video-qa-autostart-v1'
    ) from generation_spec_test_state state
  )),
  '22023',
  'generation_spec_context_invalid',
  'paid start without the exact approved spec context fails closed'
);

select is(
  (select before_failure_counts from generation_spec_test_state),
  jsonb_build_object(
    'batches', (select count(*) from content_factory.generation_batches
      where organization_id = 'f1100000-0000-4000-8000-000000000001'),
    'jobs', (select count(*) from content_factory.generation_jobs
      where organization_id = 'f1100000-0000-4000-8000-000000000001'),
    'tasks', (select count(*) from content_factory.creator_tasks
      where organization_id = 'f1100000-0000-4000-8000-000000000001'),
    'spend', (select count(*) from content_factory.generation_spend_ledger
      where organization_id = 'f1100000-0000-4000-8000-000000000001')
  ),
  'missing spec creates no batch, job, task, or spend reservation'
);

update generation_spec_test_state state
set start_result = public.creator_start_real_generation(jsonb_build_object(
  'organization_id', 'f1100000-0000-4000-8000-000000000001',
  'project_id', 'f1150000-0000-4000-8000-000000000001',
  'campaign_id', (
    select id from content_factory.generation_campaigns
    where organization_id = 'f1100000-0000-4000-8000-000000000001'
      and kind = 'default'
  ),
  'idempotency_key', 'generation-spec-success-0001',
  'sku', 'GEN-SPEC-1',
  'product_name', 'Generation spec product',
  'product_category', 'other',
  'count', 1, 'format', '9:16', 'brief', state.prompt_text,
  'media_ids', jsonb_build_array(
    'f1300000-0000-4000-8000-000000000001'
  ),
  'platform', 'wildberries',
  'destination_ref', 'wb-generation-spec',
  'mode', 'real', 'provider', 'runway',
  'model', 'gen4_turbo', 'duration_seconds', 5,
  'allow_real_spend', true,
  'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
  'learning_context', jsonb_build_object(
    'creative_angle', 'product_focus', 'hook_patterns', '[]'::jsonb,
    'source', 'baseline', 'compiler_version', 'safe-brief-v7',
    'product_category', 'other'
  ),
  'repair_context', 'null'::jsonb,
  'review_autostart_confirmed', true,
  'review_autostart_terms_version', 'generated-video-qa-autostart-v1',
  'generation_spec_context', jsonb_build_object(
    'spec_id', state.approve_result #>> '{generation_spec,spec_id}',
    'spec_version',
      (state.approve_result #>> '{generation_spec,spec_version}')::integer,
    'spec_hash', state.approve_result #>> '{generation_spec,spec_hash}'
  )
));

select ok(
  (select start_result #>> '{job,status}' = 'queued'
    and start_result #> '{job,generation_spec_context}' =
      (approve_result -> 'generation_spec') - array[
        'status', 'exact_scope', 'editable_intent', 'compiled_prompt',
        'prompt_hash', 'research_provenance',
        'performance_policy_provenance', 'repair_provenance',
        'outcome_selection_id', 'created_at', 'updated_at', 'approved_at'
      ]::text[]
    from generation_spec_test_state),
  'approved spec normalizes explicit null repair only at the legacy boundary'
);

select ok(
  exists (
    select 1
    from content_factory.generation_jobs job
    join content_factory.generation_job_spec_bindings binding
      on binding.organization_id = job.organization_id
     and binding.generation_job_id = job.id
     and binding.spec_id = job.generation_spec_id
     and binding.spec_version = job.generation_spec_version
     and binding.spec_hash = job.generation_spec_hash
    where job.id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    )
      and job.status = 'queued'
  ),
  'job columns and append-only binding agree on exact spec identity'
);

select ok(
  exists (
    select 1
    from content_factory.generation_jobs job
    join content_factory.generation_job_spec_bindings binding
      on binding.organization_id = job.organization_id
     and binding.generation_job_id = job.id
    where job.id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    )
      and binding.claim_snapshot ->> 'version' =
        'generation-spec-claim-snapshot-v1'
      and binding.claim_snapshot_hash =
        binding.claim_snapshot ->> 'snapshot_hash'
      and binding.claim_snapshot =
        content_factory_private.generation_spec_live_claim_snapshot(
          job.organization_id, job.id, job.generation_spec_id,
          job.generation_spec_version, job.generation_spec_hash
        )
  ),
  'the queued job creative signal is included in a stable live claim snapshot'
);

select throws_ok(
  $$
    update content_factory.generation_job_spec_bindings
    set claim_snapshot = claim_snapshot
    where generation_job_id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    )
  $$,
  '55000',
  'generation_spec_ledger_append_only',
  'the paid-job claim snapshot cannot be edited after binding'
);

do $fresh_claim$
declare
  claim_result jsonb;
  claim_succeeded boolean := false;
begin
  begin
    select public.system_update_real_generation(jsonb_build_object(
      'job_id', state.start_result #>> '{job,id}',
      'status', 'starting'
    )) into claim_result
    from generation_spec_test_state state;
    claim_succeeded :=
      claim_result -> 'ok' = 'true'::jsonb
      and claim_result -> 'claimed' = 'true'::jsonb
      and claim_result #>> '{job,status}' = 'starting';
    if not claim_succeeded then
      raise exception 'fresh_generation_spec_claim_failed';
    end if;
    -- Keep the primary fixture queued for the later stale-policy claim. The
    -- exception rolls back job/batch/task/event/storage changes only.
    raise exception 'rollback_successful_generation_spec_claim';
  exception when raise_exception then
    if sqlerrm <> 'rollback_successful_generation_spec_claim' then
      raise;
    end if;
  end;
  update generation_spec_test_state
  set fresh_claim_succeeded = claim_succeeded;
end;
$fresh_claim$;

select ok(
  (select fresh_claim_succeeded from generation_spec_test_state)
  and (select job.status = 'queued'
       from generation_spec_test_state state
       join content_factory.generation_jobs job
         on job.id = (state.start_result #>> '{job,id}')::uuid)
  and not exists (
    select 1
    from generation_spec_test_state state
    join content_factory.generation_storage_reservations reservation
      on reservation.generation_job_id =
        (state.start_result #>> '{job,id}')::uuid
     and reservation.status = 'active'
  ),
  'a fresh exact snapshot permits queued-to-starting before any provider call'
);

do $unexpected_fault$
declare
  caught_message text;
  fault_rethrown boolean := false;
begin
  begin
    execute $ddl$
      create or replace function public.creator_generation_learning_policy(
        p_payload jsonb default '{}'::jsonb
      )
      returns jsonb
      language plpgsql
      volatile
      security definer
      set search_path = ''
      as $fault_function$
      begin
        raise exception using
          errcode = 'XX000', message = 'generation_spec_test_internal_fault';
      end;
      $fault_function$
    $ddl$;
    perform public.system_update_real_generation(jsonb_build_object(
      'job_id', state.start_result #>> '{job,id}',
      'status', 'starting'
    ))
    from generation_spec_test_state state;
  exception when sqlstate 'XX000' then
    get stacked diagnostics caught_message = message_text;
    if caught_message <> 'generation_spec_test_internal_fault' then
      raise;
    end if;
    fault_rethrown := true;
  end;
  -- The failed subtransaction also restores the real policy function.
  update generation_spec_test_state
  set unexpected_fault_rethrown = fault_rethrown;
end;
$unexpected_fault$;

select ok(
  (select unexpected_fault_rethrown from generation_spec_test_state)
  and (select job.status = 'queued'
              and batch.status = 'queued'
              and task.status = 'blocked'
       from generation_spec_test_state state
       join content_factory.generation_jobs job
         on job.id = (state.start_result #>> '{job,id}')::uuid
       join content_factory.generation_batches batch
         on batch.organization_id = job.organization_id
        and batch.id = job.batch_id
       join content_factory.creator_tasks task
         on task.organization_id = job.organization_id
        and task.generation_job_id = job.id)
  and (select count(*) filter (
                where ledger.event_type = 'reserved'
              ) = 1
              and count(*) filter (
                where ledger.event_type = 'released'
              ) = 0
       from content_factory.generation_spend_ledger ledger
       where ledger.generation_job_id = (
         select (start_result #>> '{job,id}')::uuid
         from generation_spec_test_state
       )),
  'unexpected claim dependency faults rethrow and preserve queued reservation'
);

do $missing_binding$
declare
  caught_message text;
  rejected boolean := false;
begin
  begin
    perform set_config(
      'content_factory.generation_spec_id',
      state.start_result #>> '{job,generation_spec_context,spec_id}', true
    ) from generation_spec_test_state state;
    perform set_config(
      'content_factory.generation_spec_version',
      state.start_result #>> '{job,generation_spec_context,spec_version}', true
    ) from generation_spec_test_state state;
    perform set_config(
      'content_factory.generation_spec_hash',
      state.start_result #>> '{job,generation_spec_context,spec_hash}', true
    ) from generation_spec_test_state state;
    perform set_config(
      'content_factory.generation_product_category', 'other', true
    );
    insert into content_factory.generation_jobs (
      id, organization_id, product_id, batch_id, ordinal,
      requested_by, assigned_to, mode, provider, allow_real_spend,
      estimated_cost_minor, actual_cost_minor, status,
      input, output, request_hash, idempotency_key
    )
    select
      'f1500000-0000-4000-8000-000000000002',
      job.organization_id, job.product_id, job.batch_id, 2,
      job.requested_by, job.assigned_to, job.mode, job.provider,
      job.allow_real_spend, job.estimated_cost_minor, 0, 'queued',
      job.input, '{}'::jsonb, repeat('c', 64),
      'generation-spec-missing-binding-0001'
    from content_factory.generation_jobs job
    where job.id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    );
    -- Exercise the database consumption boundary directly. Reusing the
    -- original batch is intentionally harmless here because the provider
    -- guard must reject the missing immutable binding before any state write.
    update content_factory.generation_jobs
    set status = 'starting'
    where id = 'f1500000-0000-4000-8000-000000000002';
  exception when sqlstate '55000' then
    get stacked diagnostics caught_message = message_text;
    if caught_message <> 'generation_spec_provider_start_stale' then
      raise;
    end if;
    rejected := true;
  end;
  update generation_spec_test_state
  set missing_binding_rejected = rejected;
end;
$missing_binding$;

select ok(
  (select missing_binding_rejected from generation_spec_test_state)
  and not exists (
    select 1 from content_factory.generation_jobs
    where id = 'f1500000-0000-4000-8000-000000000002'
  ),
  'an approved queued job without the immutable binding is rejected atomically'
);

select is(
  (select count(*)::integer
   from content_factory.generation_spend_ledger ledger
   where ledger.generation_job_id = (
     select (start_result #>> '{job,id}')::uuid
     from generation_spec_test_state
   ) and ledger.event_type = 'reserved'),
  1,
  'successful SQL start writes exactly one transactional reservation'
);

select is(
  (select count(*)::integer
   from content_factory.factory_events event
   where event.event_name = 'real_generation_starting'
     and event.entity_id = (
       select start_result #>> '{job,id}' from generation_spec_test_state
     )),
  0,
  'spec approval and SQL start never claim or contact the provider'
);

select is(
  (select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'f1100000-0000-4000-8000-000000000001',
    'project_id', 'f1150000-0000-4000-8000-000000000001',
    'campaign_id', (
      select id from content_factory.generation_campaigns
      where organization_id = 'f1100000-0000-4000-8000-000000000001'
        and kind = 'default'
    ),
    'idempotency_key', 'generation-spec-success-0001',
    'sku', 'GEN-SPEC-1', 'product_name', 'Generation spec product',
    'product_category', 'other', 'count', 1, 'format', '9:16',
    'brief', state.prompt_text,
    'media_ids', jsonb_build_array(
      'f1300000-0000-4000-8000-000000000001'
    ),
    'platform', 'wildberries', 'destination_ref', 'wb-generation-spec',
    'mode', 'real', 'provider', 'runway', 'model', 'gen4_turbo',
    'duration_seconds', 5, 'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'learning_context', jsonb_build_object(
      'creative_angle', 'product_focus', 'hook_patterns', '[]'::jsonb,
      'source', 'baseline', 'compiler_version', 'safe-brief-v7',
      'product_category', 'other'
    ),
    'repair_context', 'null'::jsonb,
    'review_autostart_confirmed', true,
    'review_autostart_terms_version', 'generated-video-qa-autostart-v1',
    'generation_spec_context', state.start_result #> '{job,generation_spec_context}'
  )) from generation_spec_test_state state),
  (select start_result from generation_spec_test_state),
  'exact retry returns the stored result without a second job or spend'
);

update generation_spec_test_state state
set patch_result = public.creator_control_generation_spec(jsonb_build_object(
  'organization_id', 'f1100000-0000-4000-8000-000000000001',
  'project_id', 'f1150000-0000-4000-8000-000000000001',
  'spec_id', state.approve_result #>> '{generation_spec,spec_id}',
  'expected_spec_version',
    (state.approve_result #>> '{generation_spec,spec_version}')::integer,
  'expected_spec_hash', state.approve_result #>> '{generation_spec,spec_hash}',
  'action', 'patch', 'confirmation', true,
  'reason', 'Save a corrected editable intent as a new immutable draft.',
  'idempotency_key', 'generation-spec-patch-0001',
  'patch', jsonb_build_object(
    'editable_intent',
      'Use a calmer product interaction while preserving every approved fact.'
  )
));

select ok(
  (select patch_result #>> '{generation_spec,status}' = 'draft'
    and (patch_result #>> '{generation_spec,spec_version}')::integer = 2
    and jsonb_array_length(patch_result -> 'history') = 2
    and patch_result #>> '{history,1,status}' = 'superseded'
    and (select count(distinct item.value ->> 'spec_version')
         from jsonb_array_elements(patch_result -> 'history') item(value)) = 2
    from generation_spec_test_state),
  'patch appends version two and returns unique full version documents'
);

select is(
  (select public.creator_start_real_generation(jsonb_build_object(
    'organization_id', 'f1100000-0000-4000-8000-000000000001',
    'project_id', 'f1150000-0000-4000-8000-000000000001',
    'campaign_id', (
      select id from content_factory.generation_campaigns
      where organization_id = 'f1100000-0000-4000-8000-000000000001'
        and kind = 'default'
    ),
    'idempotency_key', 'generation-spec-success-0001',
    'sku', 'GEN-SPEC-1',
    'product_name', 'Generation spec product',
    'product_category', 'other',
    'count', 1, 'format', '9:16', 'brief', state.prompt_text,
    'media_ids', jsonb_build_array(
      'f1300000-0000-4000-8000-000000000001'
    ),
    'platform', 'wildberries',
    'destination_ref', 'wb-generation-spec',
    'mode', 'real', 'provider', 'runway',
    'model', 'gen4_turbo', 'duration_seconds', 5,
    'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'learning_context', jsonb_build_object(
      'creative_angle', 'product_focus', 'hook_patterns', '[]'::jsonb,
      'source', 'baseline', 'compiler_version', 'safe-brief-v7',
      'product_category', 'other'
    ),
    'repair_context', 'null'::jsonb,
    'review_autostart_confirmed', true,
    'review_autostart_terms_version', 'generated-video-qa-autostart-v1',
    'generation_spec_context', state.start_result #> '{job,generation_spec_context}'
  )) from generation_spec_test_state state),
  (select start_result from generation_spec_test_state),
  'an exact bound replay survives a later patch without re-spending'
);

select throws_ok(
  format($sql$
    select public.creator_start_real_generation(%L::jsonb)
  $sql$, (
    select jsonb_build_object(
      'organization_id', 'f1100000-0000-4000-8000-000000000001',
      'project_id', 'f1150000-0000-4000-8000-000000000001',
      'idempotency_key', 'generation-spec-success-0001',
      'generation_spec_context', jsonb_build_object(
        'spec_id', patch_result #>> '{generation_spec,spec_id}',
        'spec_version',
          (patch_result #>> '{generation_spec,spec_version}')::integer,
        'spec_hash', patch_result #>> '{generation_spec,spec_hash}'
      )
    ) from generation_spec_test_state
  )),
  '23505',
  'idempotency_key_conflict',
  'same idempotency key cannot be replayed under another spec version'
);

select set_config('content_factory.generation_spec_id', '', true);
select set_config('content_factory.generation_spec_version', '', true);
select set_config('content_factory.generation_spec_hash', '', true);

select throws_ok(
  $$
    insert into content_factory.generation_jobs (
      id, organization_id, product_id, batch_id, ordinal,
      requested_by, assigned_to, mode, provider, allow_real_spend,
      estimated_cost_minor, actual_cost_minor, status,
      input, output, request_hash, idempotency_key
    )
    select
      'f1500000-0000-4000-8000-000000000001',
      job.organization_id, job.product_id, job.batch_id, 2,
      job.requested_by, job.assigned_to,
      'real', 'runway', true, job.estimated_cost_minor, 0, 'queued',
      job.input - 'generation_spec_context', '{}'::jsonb,
      repeat('b', 64), 'generation-spec-direct-bypass-0001'
    from content_factory.generation_jobs job
    where job.id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    )
  $$,
  '42501',
  'generation_spec_approval_required',
  'direct paid job insertion cannot bypass the transaction-owned spec context'
);

select is(
  (select count(*)::integer
   from content_factory.generation_spend_ledger
   where generation_job_id = 'f1500000-0000-4000-8000-000000000001'),
  0,
  'failed direct bypass reserves no money'
);

update generation_spec_test_state state
set stale_claim_result = public.system_update_real_generation(
  jsonb_build_object(
    'job_id', state.start_result #>> '{job,id}',
    'status', 'starting'
  )
);

select ok(
  (select
     stale_claim_result ?& array[
       'ok', 'claimed', 'terminal', 'code', 'retryable', 'job'
     ]::text[]
     and stale_claim_result - array[
       'ok', 'claimed', 'terminal', 'code', 'retryable', 'job'
     ]::text[] = '{}'::jsonb
     and stale_claim_result -> 'ok' = 'false'::jsonb
     and stale_claim_result -> 'claimed' = 'false'::jsonb
     and stale_claim_result -> 'terminal' = 'true'::jsonb
     and stale_claim_result -> 'retryable' = 'false'::jsonb
     and stale_claim_result ->> 'code' =
       'generation_spec_provider_start_stale'
     and (stale_claim_result -> 'job') ?& array[
       'id', 'batch_id', 'status', 'provider', 'failure_code', 'updated_at'
     ]::text[]
     and (stale_claim_result -> 'job') - array[
       'id', 'batch_id', 'status', 'provider', 'failure_code', 'updated_at'
     ]::text[] = '{}'::jsonb
     and stale_claim_result #>> '{job,status}' = 'failed'
     and stale_claim_result #>> '{job,provider}' = 'runway'
     and stale_claim_result #>> '{job,failure_code}' =
       'generation_spec_provider_start_stale'
   from generation_spec_test_state),
  'a superseded exact spec returns the strict terminal stale-claim envelope'
);

select ok(
  (select job.status = 'failed'
          and job.actual_cost_minor = 0
          and job.output ->> 'failure_code' =
            'generation_spec_provider_start_stale'
          and batch.status = 'failed'
          and batch.total_created = 0
          and task.status = 'cancelled'
          and task.result ->> 'failure_code' =
            'generation_spec_provider_start_stale'
   from generation_spec_test_state state
   join content_factory.generation_jobs job
     on job.id = (state.start_result #>> '{job,id}')::uuid
   join content_factory.generation_batches batch
     on batch.organization_id = job.organization_id
    and batch.id = job.batch_id
   join content_factory.creator_tasks task
     on task.organization_id = job.organization_id
    and task.generation_job_id = job.id),
  'definitive pre-provider staleness atomically terminalizes job, batch, and task'
);

select ok(
  (select count(*) = 2
          and count(*) filter (where ledger.event_type = 'reserved') = 1
          and count(*) filter (
            where ledger.event_type = 'released'
              and ledger.reserved_delta_minor = -25
              and ledger.committed_delta_minor = 0
          ) = 1
          and sum(ledger.reserved_delta_minor) = 0
          and sum(ledger.committed_delta_minor) = 0
   from content_factory.generation_spend_ledger ledger
   where ledger.generation_job_id = (
     select (start_result #>> '{job,id}')::uuid
     from generation_spec_test_state
   )),
  'terminal stale claim releases the exact reservation without committed spend'
);

select ok(
  (select count(*) filter (
            where event.event_name = 'real_generation_starting'
          ) = 0
          and count(*) filter (
            where event.event_name = 'real_generation_failed'
              and event.properties ->> 'failure_code' =
                'generation_spec_provider_start_stale'
              and event.properties -> 'provider_action' = 'false'::jsonb
              and event.properties -> 'spend_released' = 'true'::jsonb
          ) = 1
   from content_factory.factory_events event
   where event.entity_id = (
     select start_result #>> '{job,id}' from generation_spec_test_state
   )),
  'terminal stale claim emits one safe failure event and no provider-start event'
);

select ok(
  not exists (
    select 1
    from content_factory.generation_storage_reservations reservation
    where reservation.generation_job_id = (
      select (start_result #>> '{job,id}')::uuid
      from generation_spec_test_state
    )
      and reservation.status = 'active'
  ),
  'terminal stale claim leaves no active storage reservation'
);

select is(
  (select public.system_update_real_generation(jsonb_build_object(
     'job_id', state.start_result #>> '{job,id}',
     'status', 'starting'
   )) from generation_spec_test_state state),
  (select stale_claim_result from generation_spec_test_state),
  'terminal stale-claim replay is exact and does not repeat side effects'
);

select is(
  (select count(*)::integer
   from content_factory.generation_jobs
   where organization_id = 'f1100000-0000-4000-8000-000000000001'),
  1,
  'all failure and replay paths preserve exactly one paid job'
);

select is(
  (select count(*)::integer
   from content_factory.generation_spend_ledger
   where organization_id = 'f1100000-0000-4000-8000-000000000001'
     and event_type = 'reserved'),
  1,
  'all failure and replay paths preserve exactly one spend reservation'
);

select is(
  (select count(*)::integer
   from content_factory.generation_spend_ledger
   where organization_id = 'f1100000-0000-4000-8000-000000000001'
     and event_type = 'released'),
  1,
  'the definitive stale claim appends exactly one spend release'
);

select * from finish();
rollback;
