begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select plan(45);

-- Network-free integration fixture for the least-privilege employee path:
-- explicit project ACL -> exact metered confirmation -> own run/receipt ->
-- own AI decision.  Provider bindings are created only where the test calls
-- the server-only begin function explicitly; no HTTP/provider worker runs.
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
    'dc000000-0000-4000-8000-000000000001',
    'operator-research-owner@example.test',
    'Operator Research Owner'
  ),
  (
    'dc000000-0000-4000-8000-000000000002',
    'operator-research-a@example.test',
    'Operator Research A'
  ),
  (
    'dc000000-0000-4000-8000-000000000003',
    'operator-research-b@example.test',
    'Operator Research B'
  ),
  (
    'dc000000-0000-4000-8000-000000000004',
    'operator-research-no-acl@example.test',
    'Operator Research No ACL'
  ),
  (
    'dc000000-0000-4000-8000-000000000005',
    'operator-research-revoked@example.test',
    'Operator Research Revoked'
  )
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values (
  'dc100000-0000-4000-8000-000000000001',
  'Operator Project Research AI pgTAP',
  'operator-project-research-ai-pgtap',
  'active'
);

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values
  (
    'dc100000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000001',
    'owner', 'active'
  ),
  (
    'dc100000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000002',
    'operator', 'active'
  ),
  (
    'dc100000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000003',
    'operator', 'active'
  ),
  (
    'dc100000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000004',
    'operator', 'active'
  ),
  (
    'dc100000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000005',
    'operator', 'active'
  );

insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by, revoked_by, revoked_at, revocation_reason
)
select
  'dc100000-0000-4000-8000-000000000001'::uuid,
  fixture.profile_id::uuid,
  'workspace_generation', fixture.status,
  'trainee', 'operator',
  'TEST-ONLY exact operator research qualification fixture.',
  'dc000000-0000-4000-8000-000000000001'::uuid,
  case when fixture.status = 'revoked'
    then 'dc000000-0000-4000-8000-000000000001'::uuid end,
  case when fixture.status = 'revoked' then now() end,
  case when fixture.status = 'revoked'
    then 'TEST-ONLY revoked research qualification fixture.' end
from (values
  ('dc000000-0000-4000-8000-000000000002', 'active'),
  ('dc000000-0000-4000-8000-000000000003', 'active'),
  ('dc000000-0000-4000-8000-000000000004', 'active'),
  ('dc000000-0000-4000-8000-000000000005', 'revoked')
) fixture(profile_id, status);

-- Project membership grants intentionally retain the mature training gate.
-- Qualify this test-only owner so the ACL setup exercises the real RPC rather
-- than bypassing or weakening its authorization boundary.
insert into content_factory.training_access_waivers (
  organization_id, profile_id, scope, status, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'dc100000-0000-4000-8000-000000000001'::uuid,
  'dc000000-0000-4000-8000-000000000001'::uuid,
  'workspace_generation', 'active', 'owner', 'owner',
  'TEST-ONLY owner qualification for project ACL fixture.',
  'dc000000-0000-4000-8000-000000000001'::uuid
);

do $$
begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values
  (
    'dc200000-0000-4000-8000-000000000001',
    'dc100000-0000-4000-8000-000000000001',
    null, 'Operator research project', 'blue', 'project', null,
    'active', 1024,
    'dc000000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000001'
  ),
  (
    'dc200000-0000-4000-8000-000000000002',
    'dc100000-0000-4000-8000-000000000001',
    null, 'Foreign operator research project', 'violet', 'project', null,
    'active', 2048,
    'dc000000-0000-4000-8000-000000000001',
    'dc000000-0000-4000-8000-000000000001'
  );

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'profile_id', 'dc000000-0000-4000-8000-000000000002',
    'idempotency_key', 'operator-research-grant-a-main-0001'
  )) ->> 'ok')::boolean,
  'owner grants operator A the exact research project'
);

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000002',
    'profile_id', 'dc000000-0000-4000-8000-000000000002',
    'idempotency_key', 'operator-research-grant-a-foreign-0001'
  )) ->> 'ok')::boolean,
  'operator A also has ACL to the foreign-project substitution fixture'
);

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'profile_id', 'dc000000-0000-4000-8000-000000000003',
    'idempotency_key', 'operator-research-grant-b-main-0001'
  )) ->> 'ok')::boolean,
  'owner grants operator B the same explicit project'
);

select ok(
  (public.creator_grant_project_member(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'profile_id', 'dc000000-0000-4000-8000-000000000005',
    'idempotency_key', 'operator-research-grant-revoked-main-0001'
  )) ->> 'ok')::boolean,
  'revoked qualification fixture retains project ACL for gate isolation'
);

insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'dc300000-0000-4000-8000-000000000001',
  'dc100000-0000-4000-8000-000000000001',
  'OPERATOR-RESEARCH-SKU-1',
  'Operator research detergent',
  'active',
  '{"brand":"Fixture","description":"Exact household product"}'::jsonb,
  'dc000000-0000-4000-8000-000000000001'
);

create or replace function pg_temp.operator_research_start_payload(
  p_idempotency_key text
)
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'idempotency_key', p_idempotency_key,
    'product_id', 'dc300000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'objective', 'Create one bounded evidence brief for this exact product.',
    'marketplace_url', 'https://example.test/operator-research/product',
    'platforms', jsonb_build_array('youtube'),
    'paid_analysis_ack', true,
    'paid_analysis_authorization',
      content_factory_private.research_price_contract()
  )
$$;

create temporary table operator_research_context (
  actor_id uuid primary key,
  start_result jsonb,
  replay_result jsonb,
  completion_result jsonb,
  queue_result jsonb,
  decision_result jsonb,
  run_id uuid,
  receipt_id uuid,
  receipt_hash text,
  selection_id uuid
) on commit drop;

insert into operator_research_context (actor_id) values
  ('dc000000-0000-4000-8000-000000000002'),
  ('dc000000-0000-4000-8000-000000000003');

-- The completion fixture is production-shaped but deterministic.  It calls
-- no transport and supplies the same validated source/draft/forecast shape
-- used by the mature research handoff pgTAP.
create or replace function pg_temp.complete_operator_research_fixture(
  p_run_id uuid,
  p_actor_id uuid,
  p_suffix text
)
returns jsonb
language plpgsql
as $$
declare
  claim_value jsonb;
begin
  claim_value := public.system_claim_product_research(
    jsonb_build_object('run_id', p_run_id)
  );
  if claim_value -> 'claimed' is distinct from 'true'::jsonb
     and claim_value #>> '{run,status}' <> 'processing' then
    raise exception 'fixture claim failed for %', p_run_id;
  end if;

  return public.system_complete_product_research(jsonb_build_object(
    'run_id', p_run_id,
    'status', 'completed',
    'summary', jsonb_build_object(
      'results', jsonb_build_array(
        'Exact package visibility is the strongest observable product cue.'
      ),
      'conclusions', jsonb_build_array(
        'Recommend one editable demonstration for the exact product.'
      ),
      'category_analysis', jsonb_build_object(
        'category', 'household',
        'finding', 'Trust grows when the product is shown honestly.'
      ),
      'trend_analysis', jsonb_build_object(
        'finding', 'Short demonstrations remain useful for testing.'
      )
    ),
    'sources', jsonb_build_array(jsonb_build_object(
      'source_type', 'review',
      'source_url',
        'https://example.test/operator-research/review-' || p_suffix,
      'title', 'Bounded public review evidence ' || p_suffix,
      'trust_level', 'public',
      'extracted_facts', jsonb_build_array(jsonb_build_object(
        'statement', 'Buyers ask to see the exact package.',
        'source_ids', jsonb_build_array('review:1')
      )),
      'metadata', jsonb_build_object('model_source_id', 'review:1')
    )),
    'draft', jsonb_build_object(
      'title', 'Exact operator product demonstration brief ' || p_suffix,
      'brief', jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'finding', 'Use an honest product demonstration.'
        ),
        'competitor_analysis', jsonb_build_object(
          'finding', 'Avoid unverifiable comparisons.'
        ),
        'trend_analysis', jsonb_build_object(
          'finding', 'A concise visual proof is suitable for testing.'
        ),
        'guidance', jsonb_build_object(
          'status', 'ready_for_brief',
          'recommendation', 'Keep every recommendation editable.'
        ),
        'audience', jsonb_build_array('Household product buyer'),
        'pains', jsonb_build_array('Unclear package identity'),
        'objections', jsonb_build_array('Is this the exact product?'),
        'claims', jsonb_build_array('Show only observable details.'),
        'facts', jsonb_build_array('The product URL is registered.'),
        'creative_potential', jsonb_build_object('score', 0.82),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'position', 1,
          'title', 'One honest product detail',
          'platform', 'tiktok',
          'recommended_generation_mode', 'seedance2_fast',
          'duration_seconds', 8,
          'format', '9:16',
          'hook', 'Watch one honest product detail?',
          'shot_list', jsonb_build_array(
            'Show the exact package in one clear frame.'
          ),
          'goal', 'Demonstrate exact product identity.',
          'proof_points', jsonb_build_array(
            'The exact product URL is registered.'
          ),
          'avoid_claims', jsonb_build_array(
            'Do not invent performance claims.'
          ),
          'cta', 'Review the product details.'
        ))
      ),
      'task_blueprint', jsonb_build_array(jsonb_build_object(
        'title', 'Review the exact product concept',
        'instructions', 'Check that the product identity remains exact.',
        'task_type', 'general',
        'assignee_id', p_actor_id,
        'priority', 2,
        'payout_minor', 0
      ))
    ),
    'forecast', jsonb_build_object(
      'score', 82,
      'confidence', 0.71,
      'model_provider', 'deterministic_fixture',
      'model_version', 'operator-research-v1',
      'factors', jsonb_build_object('exact_product', 0.9),
      'limitations', jsonb_build_array(
        'No external provider is invoked by this pgTAP fixture.'
      )
    )
  ));
end;
$$;

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_start_project_research(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_project_research_status(jsonb)',
    'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.contentengine_decide_ai_research_training(jsonb)',
    'execute'
  ),
  'public operator research wrappers remain authenticated browser RPCs'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_project_research_pre_operator_price_v1(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_project_research_status_pre_operator_own_v1(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.contentengine_decide_ai_research_training_pre_operator_own_v1(jsonb)',
    'execute'
  ),
  'private mature delegates remain unavailable to authenticated'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
        'content_factory.product_research_runs'::regclass
      and trigger_row.tgname =
        'enforce_operator_research_price_confirmation'
      and upper(pg_get_triggerdef(trigger_row.oid)) like
        '%AFTER INSERT ON CONTENT_FACTORY.PRODUCT_RESEARCH_RUNS%'
      and upper(pg_get_triggerdef(trigger_row.oid)) not like '% OR UPDATE %'
      and trigger_row.tgdeferrable
      and trigger_row.tginitdeferred
  ),
  'operator price confirmation constraint is deferred and INSERT-only'
);

select is(
  content_factory_private.research_price_contract(),
  jsonb_build_object(
    'version', 'openai-api-2026-08-13-gpt-5.5-standard-context-v3',
    'provider', 'openai',
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'model', 'gpt-5.5',
    'currency', 'USD',
    'billing_mode', 'metered_actual_usage',
    'service_tier', 'default',
    'input_usd_per_million_tokens', '5.00',
    'output_usd_per_million_tokens', '30.00',
    'long_context_threshold_input_tokens', 272000,
    'long_context_input_usd_per_million_tokens', '10.00',
    'long_context_output_usd_per_million_tokens', '45.00',
    'web_search_usd_per_call', '0.01',
    'max_output_tokens', 18000,
    'max_provider_attempts', 1,
    'fixed_total', false,
    'confirmation_value',
      'OPENAI_GPT_5_5_WEB_RESEARCH_20260813_DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000'
  ),
  'the exact full metered tariff is one canonical server snapshot'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.creator_ai_research_training_queue(jsonb)'::regprocedure
    ),
    'qualified_operator_own_ai_research_receipt_allowed'
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.creator_ai_research_training_queue(jsonb)'::regprocedure
    ),
    'qualified_operator_own_ai_research_receipt_allowed'
  ) < strpos(
    pg_get_functiondef(
      'public.creator_ai_research_training_queue(jsonb)'::regprocedure
    ),
    'limit limit_value'
  )
  and strpos(
    pg_get_functiondef(
      'public.creator_ai_research_training_queue(jsonb)'::regprocedure
    ),
    '''ownership'''
  ) > 0,
  'own receipt and ownership filters are installed before pending pagination'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.contentengine_decide_ai_research_training(jsonb)'::regprocedure
    ),
    'qualified_operator_own_ai_research_receipt_allowed'
  ) < strpos(
    pg_get_functiondef(
      'public.contentengine_decide_ai_research_training(jsonb)'::regprocedure
    ),
    'contentengine_decide_ai_research_training_pre_operator_own_v1'
  ),
  'outer AI decision ownership check executes before its mature delegate'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

-- Immediate mode makes the deferred INSERT-only invariant executable inside
-- throws_ok.  No direct operator run may survive without its exact snapshot.
set constraints enforce_operator_research_price_confirmation immediate;

select throws_ok(
  $unconfirmed_insert$
    insert into content_factory.product_research_runs (
      id, organization_id, project_id, product_id, created_by, status,
      input, request_hash, idempotency_key
    ) values (
      'dc400000-0000-4000-8000-000000000001',
      'dc100000-0000-4000-8000-000000000001',
      'dc200000-0000-4000-8000-000000000001',
      'dc300000-0000-4000-8000-000000000001',
      'dc000000-0000-4000-8000-000000000002',
      'queued', '{}'::jsonb, repeat('a', 64),
      'unconfirmed-direct-operator-run-0001'
    )
  $unconfirmed_insert$,
  '23514',
  'operator_research_price_confirmation_required',
  'future direct operator run insert without exact snapshot is rejected'
);

set constraints enforce_operator_research_price_confirmation deferred;

-- Seed both actor-scoped runs before exercising status and queue boundaries.
-- The later calls with the same raw key are deliberate replay assertions.
do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

update operator_research_context context_row
set start_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

update operator_research_context
set run_id = (start_result #>> '{run,id}')::uuid
where actor_id = 'dc000000-0000-4000-8000-000000000002';

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

update operator_research_context context_row
set start_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000003';

update operator_research_context
set run_id = (start_result #>> '{run,id}')::uuid
where actor_id = 'dc000000-0000-4000-8000-000000000003';

set constraints enforce_operator_research_price_confirmation immediate;
set constraints enforce_operator_research_price_confirmation deferred;

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select is(
  (
    select public.creator_project_research_status(jsonb_build_object(
      'organization_id', 'dc100000-0000-4000-8000-000000000001',
      'project_id', 'dc200000-0000-4000-8000-000000000001',
      'run_id', context_row.run_id
    )) #>> '{run,id}'
    from operator_research_context context_row
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
  ),
  (
    select run_id::text
    from operator_research_context
    where actor_id = 'dc000000-0000-4000-8000-000000000002'
  ),
  'operator own exact run passes the public status boundary'
);

select throws_ok(
  format(
    $status_sibling$
      select public.creator_project_research_status(jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'run_id', %L
      ))
    $status_sibling$,
    (select run_id::text
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000003')
  ),
  '42501',
  'research_run_not_allowed',
  'sibling operator is rejected before the mature status delegate'
);

select throws_ok(
  format(
    $status_foreign$
      select public.creator_project_research_status(jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000002',
        'run_id', %L
      ))
    $status_foreign$,
    (select run_id::text
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000002')
  ),
  '42501',
  'research_run_not_allowed',
  'foreign project cannot be substituted at the status boundary'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000004',
    true
  );
end;
$$;

select throws_ok(
  format(
    $status_no_acl$
      select public.creator_project_research_status(jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'run_id', %L
      ))
    $status_no_acl$,
    (select run_id::text
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000002')
  ),
  '42501',
  'workspace_project_access_required',
  'operator without explicit project ACL is rejected before status delegation'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000005',
    true
  );
end;
$$;

select throws_ok(
  format(
    $status_revoked$
      select public.creator_project_research_status(jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'run_id', %L
      ))
    $status_revoked$,
    (select run_id::text
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000002')
  ),
  '42501',
  'research_run_not_allowed',
  'revoked qualification is rejected before status delegation'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.contentengine_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'product_category', 'household'
      )
    )
  $$,
  '22023',
  'project_id_invalid',
  'operator AI queue requires one explicit project id'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000004',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.contentengine_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'product_category', 'household'
      )
    )
  $$,
  '42501',
  'workspace_project_access_required',
  'operator without project ACL is rejected before queue queries'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000005',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.contentengine_ai_research_training_queue(
      jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'product_category', 'household'
      )
    )
  $$,
  '42501',
  'role_not_allowed',
  'revoked operator qualification is rejected before queue queries'
);

create temporary table operator_exact_source_context (
  actor_id uuid primary key,
  source_id uuid not null
) on commit drop;

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

insert into operator_exact_source_context (actor_id, source_id)
select
  'dc000000-0000-4000-8000-000000000002',
  (public.contentengine_register_exact_youtube_source(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'video_id', 'A1b2C3d4E5F',
    'canonical_url', 'https://youtube.com/watch?v=A1b2C3d4E5F',
    'product_name', 'Operator research detergent',
    'product_sku', 'OPERATOR-RESEARCH-SKU-1',
    'idempotency_key', 'operator-exact-source-a-0001'
  )) #>> '{source,id}')::uuid;

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

insert into operator_exact_source_context (actor_id, source_id)
select
  'dc000000-0000-4000-8000-000000000003',
  (public.contentengine_register_exact_youtube_source(jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'video_id', 'F5e4D3c2B1A',
    'canonical_url', 'https://youtube.com/watch?v=F5e4D3c2B1A',
    'product_name', 'Operator research detergent',
    'product_sku', 'OPERATOR-RESEARCH-SKU-1',
    'idempotency_key', 'operator-exact-source-b-0001'
  )) #>> '{source,id}')::uuid;

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select ok(
  (
    select
      (snapshot -> 'sources' -> 0 ->> 'id') = source_id::text
      and jsonb_array_length(snapshot -> 'sources') = 1
    from (
      select
        public.contentengine_exact_youtube_source_queue(jsonb_build_object(
          'organization_id', 'dc100000-0000-4000-8000-000000000001',
          'project_id', 'dc200000-0000-4000-8000-000000000001',
          'limit', 10
        )) as snapshot,
        source_id
      from operator_exact_source_context
      where actor_id = 'dc000000-0000-4000-8000-000000000002'
    ) operator_queue
  ),
  'operator exact-YouTube queue contains only their own registered source'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select is(
  jsonb_array_length(
    public.contentengine_exact_youtube_source_queue(jsonb_build_object(
      'organization_id', 'dc100000-0000-4000-8000-000000000001',
      'project_id', 'dc200000-0000-4000-8000-000000000001',
      'limit', 10
    )) -> 'sources'
  ),
  2,
  'manager exact-YouTube queue retains the project-wide view'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  $missing_price$
    select public.creator_start_project_research(
      pg_temp.operator_research_start_payload(
        'operator-price-missing-0001'
      ) - 'paid_analysis_authorization'
    )
  $missing_price$,
  '22023',
  'research_price_confirmation_required',
  'operator must personally submit the current paid tariff snapshot'
);

select throws_ok(
  $mutated_price$
    select public.creator_start_project_research(
      jsonb_set(
        pg_temp.operator_research_start_payload(
          'operator-price-mutated-0001'
        ),
        '{paid_analysis_authorization,model}',
        '"gpt-5.4"'::jsonb
      )
    )
  $mutated_price$,
  '22023',
  'research_price_confirmation_required',
  'a stale or reconstructed tariff object is rejected as a whole object'
);

update operator_research_context context_row
set start_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

update operator_research_context
set run_id = (start_result #>> '{run,id}')::uuid
where actor_id = 'dc000000-0000-4000-8000-000000000002';

select is(
  (
    select count(*)::integer
    from content_factory.research_run_provider_bindings binding
    where binding.run_id = (
      select run_id
      from operator_research_context
      where actor_id = 'dc000000-0000-4000-8000-000000000002'
    )
  ),
  0,
  'fresh operator start returns with zero provider binding'
);

-- Flushing the deferred event proves the wrapper inserted its append-only
-- confirmation in the same statement as the new run.
set constraints enforce_operator_research_price_confirmation immediate;

select ok(
  exists (
    select 1
    from operator_research_context context_row
    join content_factory.research_operator_price_confirmations confirmation
      on confirmation.organization_id =
           'dc100000-0000-4000-8000-000000000001'
     and confirmation.project_id =
           'dc200000-0000-4000-8000-000000000001'
     and confirmation.run_id = context_row.run_id
     and confirmation.confirmed_by = context_row.actor_id
     and confirmation.pricing_version =
           'openai-api-2026-08-13-gpt-5.5-standard-context-v3'
     and confirmation.provider_key = 'openai_web_search'
     and confirmation.adapter_version =
           'openai-responses-web-search-v1'
     and confirmation.model = 'gpt-5.5'
     and confirmation.billing_mode = 'metered_actual_usage'
     and confirmation.service_tier = 'default'
     and confirmation.input_usd_micros_per_million_tokens = 5000000
     and confirmation.output_usd_micros_per_million_tokens = 30000000
     and confirmation.long_context_threshold_input_tokens = 272000
     and confirmation.long_context_input_usd_micros_per_million_tokens = 10000000
     and confirmation.long_context_output_usd_micros_per_million_tokens = 45000000
     and confirmation.web_search_usd_micros_per_call = 10000
     and confirmation.max_output_tokens = 18000
     and confirmation.max_provider_attempts = 1
     and not confirmation.fixed_total
     and confirmation.price_snapshot_hash ~ '^[0-9a-f]{64}$'
    join content_factory.research_execution_authorizations authorization_entry
      on authorization_entry.organization_id = confirmation.organization_id
     and authorization_entry.run_id = confirmation.run_id
     and authorization_entry.authorized_by = confirmation.confirmed_by
     and authorization_entry.authorization_kind = 'explicit_paid_analysis'
     and authorization_entry.paid_analysis_ack
     and authorization_entry.provider_key = 'openai_web_search'
     and authorization_entry.adapter_version =
           'openai-responses-web-search-v1'
     and authorization_entry.max_provider_attempts = 1
     and not authorization_entry.automatic_fallback_allowed
     and authorization_entry.reason_code = 'user_confirmed_paid_analysis'
    join content_factory.product_research_runs run
      on run.organization_id = authorization_entry.organization_id
     and run.id = authorization_entry.run_id
     and run.created_by = context_row.actor_id
     and run.request_hash = authorization_entry.run_request_hash
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
  ),
  'operator run carries the exact full metered authorization'
);

set constraints enforce_operator_research_price_confirmation deferred;

update operator_research_context context_row
set replay_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

select is(
  (
    select (replay_result #>> '{run,id}')::uuid
    from operator_research_context
    where actor_id = 'dc000000-0000-4000-8000-000000000002'
  ),
  (
    select run_id
    from operator_research_context
    where actor_id = 'dc000000-0000-4000-8000-000000000002'
  ),
  'same operator and raw key replay the exact same run'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

update operator_research_context context_row
set start_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000003';

update operator_research_context
set run_id = (start_result #>> '{run,id}')::uuid
where actor_id = 'dc000000-0000-4000-8000-000000000003';

set constraints enforce_operator_research_price_confirmation immediate;

select ok(
  (select a.run_id <> b.run_id
   from operator_research_context a
   cross join operator_research_context b
   where a.actor_id = 'dc000000-0000-4000-8000-000000000002'
     and b.actor_id = 'dc000000-0000-4000-8000-000000000003')
  and (
    select count(distinct run.idempotency_key) = 2
    from content_factory.product_research_runs run
    where run.id in (
      select run_id from operator_research_context
    )
  ),
  'same raw key is actor-scoped and cannot replay the sibling run'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_run_provider_bindings binding
    where binding.run_id in (
      select run_id from operator_research_context
    )
  ),
  0,
  'both fresh actor-scoped starts are provider-attempt free'
);

set constraints enforce_operator_research_price_confirmation deferred;

-- A later explicit server action may bind the one paid provider attempt.
-- This is a direct test call, never a side effect of start/queue/decision.
update operator_research_context context_row
set replay_result = public.system_claim_product_research(
  jsonb_build_object('run_id', context_row.run_id)
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

update operator_research_context context_row
set replay_result = public.system_begin_research_provider_attempt(
  jsonb_build_object(
    'run_id', context_row.run_id,
    'provider_key', 'openai_web_search',
    'adapter_version', 'openai-responses-web-search-v1',
    'model', 'gpt-5.5'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

update operator_research_context context_row
set replay_result = public.creator_start_project_research(
  pg_temp.operator_research_start_payload(
    'operator-shared-raw-research-key-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

select ok(
  (select replay_result #>> '{run,id}' = run_id::text
   from operator_research_context
   where actor_id = 'dc000000-0000-4000-8000-000000000002')
  and exists (
    select 1
    from operator_research_context context_row
    join content_factory.research_run_provider_bindings binding
      on binding.run_id = context_row.run_id
     and binding.provider_key = 'openai_web_search'
     and binding.adapter_version = 'openai-responses-web-search-v1'
     and binding.model = 'gpt-5.5'
     and binding.attempt_number = 1
    join content_factory.research_operator_price_confirmations confirmation
      on confirmation.organization_id = binding.organization_id
     and confirmation.run_id = binding.run_id
     and confirmation.confirmed_by = context_row.actor_id
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
  ),
  'committed replay after exact claimed binding remains idempotent'
);

update operator_research_context context_row
set completion_result = pg_temp.complete_operator_research_fixture(
  context_row.run_id,
  context_row.actor_id,
  case
    when context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002' then 'operator-a'
    else 'operator-b'
  end
);

update operator_research_context
set receipt_id = (completion_result #>> '{ai_handoff,receipt_id}')::uuid;

update operator_research_context context_row
set receipt_hash = receipt.receipt_hash
from content_factory.ai_research_evidence_receipts receipt
where receipt.id = context_row.receipt_id;

select ok(
  (
    select bool_and(
      completion_result ->> 'status' = 'completed'
      and completion_result #>> '{ai_handoff,status}' =
        'awaiting_human_review'
      and receipt_id is not null
      and receipt_hash ~ '^[0-9a-f]{64}$'
    )
    from operator_research_context
  ),
  'both own completed runs produce immutable AI Center receipts'
);

select ok(
  (
    select
      snapshot #>> '{run,id}' = context_row.run_id::text
      and snapshot #>> '{research_context,run_id}' = context_row.run_id::text
      and snapshot #>> '{research_context,project_id}' =
        'dc200000-0000-4000-8000-000000000001'
      and snapshot #>> '{research_context,ownership}' = 'own'
      and snapshot #>> '{research_context,product_category}' = 'household'
      and snapshot #>> '{research_context,ai_receipt,receipt_id}' =
        context_row.receipt_id::text
    from operator_research_context context_row
    cross join lateral (
      select public.creator_project_research_status(jsonb_build_object(
        'organization_id', 'dc100000-0000-4000-8000-000000000001',
        'project_id', 'dc200000-0000-4000-8000-000000000001',
        'run_id', context_row.run_id
      )) snapshot
    ) exact_status
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
  ),
  'older own run status returns exact project ownership category and receipt'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

update operator_research_context context_row
set queue_result = public.contentengine_ai_research_training_queue(
  jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'receipt_id', context_row.receipt_id,
    'limit', 1
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

select ok(
  (select
     jsonb_array_length(queue_result -> 'queue') = 1
     and jsonb_array_length(queue_result -> 'learned') = 0
     and queue_result #>> '{queue,0,receipt_id}' = receipt_id::text
     and queue_result #>> '{queue,0,run_id}' = run_id::text
     and queue_result #>> '{queue,0,project_id}' =
       'dc200000-0000-4000-8000-000000000001'
     and queue_result #>> '{queue,0,ownership}' = 'own'
     and queue_result #>> '{capabilities,operator_own_receipts_only}' = 'true'
     and queue_result #>> '{capabilities,can_decide}' = 'true'
     and queue_result #>> '{capabilities,can_edit_recommendations}' = 'true'
   from operator_research_context
   where actor_id = 'dc000000-0000-4000-8000-000000000002'),
  'exact own receipt selector bypasses category queue pagination'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

update operator_research_context context_row
set queue_result = public.contentengine_ai_research_training_queue(
  jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'receipt_id', context_row.receipt_id,
    'limit', 10
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000003';

select ok(
  (select
     jsonb_array_length(queue_result -> 'queue') = 1
     and jsonb_array_length(queue_result -> 'learned') = 0
     and queue_result #>> '{queue,0,receipt_id}' = receipt_id::text
     and queue_result #>> '{queue,0,ownership}' = 'own'
   from operator_research_context
   where actor_id = 'dc000000-0000-4000-8000-000000000003'),
  'sibling operator queue contains only the sibling own receipt'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000002',
    true
  );
end;
$$;

select throws_ok(
  format(
    $sibling_decision$
      select public.contentengine_decide_ai_research_training(
        jsonb_build_object(
          'organization_id', 'dc100000-0000-4000-8000-000000000001',
          'project_id', 'dc200000-0000-4000-8000-000000000001',
          'product_category', 'household',
          'receipt_id', %L,
          'receipt_hash', %L,
          'decision', 'approve',
          'selected_insight_keys', jsonb_build_array('category'),
          'selected_scenario_positions', jsonb_build_array(1),
          'confirmation', true,
          'idempotency_key', 'operator-sibling-decision-0001'
        )
      )
    $sibling_decision$,
    (select receipt_id::text
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000003'),
    (select receipt_hash
     from operator_research_context
     where actor_id = 'dc000000-0000-4000-8000-000000000003')
  ),
  '42501',
  'role_not_allowed',
  'sibling receipt is rejected before decision command replay'
);

select ok(
  not exists (
    select 1
    from content_factory.command_receipts receipt
    where receipt.organization_id =
      'dc100000-0000-4000-8000-000000000001'
      and receipt.command_name = 'creator_decide_ai_research_training'
      and receipt.idempotency_key = 'operator-sibling-decision-0001'
  )
  and not exists (
    select 1
    from content_factory.ai_research_learning_selections selection
    where selection.receipt_id = (
      select receipt_id
      from operator_research_context
      where actor_id = 'dc000000-0000-4000-8000-000000000003'
    )
  ),
  'rejected sibling decision leaves no replay receipt or selection'
);

update operator_research_context context_row
set decision_result = public.contentengine_decide_ai_research_training(
  jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'receipt_id', context_row.receipt_id,
    'receipt_hash', context_row.receipt_hash,
    'decision', 'approve',
    'selected_insight_keys', jsonb_build_array('category'),
    'selected_scenario_positions', jsonb_build_array(1),
    'operator_notes', 'Keep this own-run recommendation editable.',
    'confirmation', true,
    'idempotency_key', 'operator-own-decision-0001'
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

update operator_research_context
set selection_id = (decision_result #>> '{selection,selection_id}')::uuid
where actor_id = 'dc000000-0000-4000-8000-000000000002';

select ok(
  exists (
    select 1
    from operator_research_context context_row
    join content_factory.ai_research_learning_selections selection
      on selection.id = context_row.selection_id
     and selection.organization_id =
       'dc100000-0000-4000-8000-000000000001'
     and selection.project_id =
       'dc200000-0000-4000-8000-000000000001'
     and selection.run_id = context_row.run_id
     and selection.receipt_id = context_row.receipt_id
     and selection.selected_by = context_row.actor_id
     and selection.decision = 'approve'
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
  ),
  'own receipt decision creates one actor-owned append-only selection'
);

update operator_research_context context_row
set queue_result = public.contentengine_ai_research_training_queue(
  jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'receipt_id', context_row.receipt_id,
    'limit', 10
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000002';

select ok(
  (select
     jsonb_array_length(queue_result -> 'queue') = 0
     and jsonb_array_length(queue_result -> 'learned') = 1
     and queue_result #>> '{learned,0,selection_id}' = selection_id::text
     and queue_result #>> '{learned,0,receipt_id}' = receipt_id::text
     and queue_result #>> '{learned,0,project_id}' =
       'dc200000-0000-4000-8000-000000000001'
     and queue_result #>> '{learned,0,ownership}' = 'own'
   from operator_research_context
   where actor_id = 'dc000000-0000-4000-8000-000000000002'),
  'operator learned queue contains only their own selection'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

update operator_research_context context_row
set queue_result = public.contentengine_ai_research_training_queue(
  jsonb_build_object(
    'organization_id', 'dc100000-0000-4000-8000-000000000001',
    'project_id', 'dc200000-0000-4000-8000-000000000001',
    'product_category', 'household',
    'limit', 10
  )
)
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000003';

select ok(
  (select
     jsonb_array_length(queue_result -> 'queue') = 1
     and jsonb_array_length(queue_result -> 'learned') = 0
     and queue_result #>> '{queue,0,receipt_id}' = receipt_id::text
     and queue_result #>> '{queue,0,ownership}' = 'own'
   from operator_research_context
   where actor_id = 'dc000000-0000-4000-8000-000000000003'),
  'sibling cannot inherit the other operator learned selection'
);

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000001',
    true
  );
end;
$$;

select ok(
  (
    select
      jsonb_array_length(snapshot -> 'queue') = 1
      and jsonb_array_length(snapshot -> 'learned') = 1
      and not (snapshot #> '{queue,0}' ? 'ownership')
      and not (snapshot #> '{learned,0}' ? 'ownership')
      and snapshot #>> '{capabilities,can_decide}' = 'true'
      and snapshot #>> '{capabilities,can_edit_recommendations}' = 'true'
    from (
      select public.contentengine_ai_research_training_queue(
        jsonb_build_object(
          'organization_id', 'dc100000-0000-4000-8000-000000000001',
          'project_id', 'dc200000-0000-4000-8000-000000000001',
          'product_category', 'household',
          'limit', 10
        )
      ) as snapshot
    ) manager_queue
  ),
  'manager AI queue behavior remains project-wide without own markers'
);

select is(
  (
    select public.creator_project_research_status(jsonb_build_object(
      'organization_id', 'dc100000-0000-4000-8000-000000000001',
      'project_id', 'dc200000-0000-4000-8000-000000000001',
      'run_id', context_row.run_id
    )) #>> '{run,id}'
    from operator_research_context context_row
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000003'
  ),
  (
    select run_id::text
    from operator_research_context
    where actor_id = 'dc000000-0000-4000-8000-000000000003'
  ),
  'manager status behavior remains project-wide'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_run_provider_bindings binding
    where binding.run_id in (
      select run_id from operator_research_context
    )
  ),
  1,
  'research start, queues and decisions create no provider attempt'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_run_provider_bindings binding
    join operator_research_context context_row
      on context_row.run_id = binding.run_id
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000002'
      and binding.provider_key = 'openai_web_search'
      and binding.adapter_version = 'openai-responses-web-search-v1'
      and binding.model = 'gpt-5.5'
      and binding.attempt_number = 1
  ),
  1,
  'the only provider binding is the one explicit server action in this test'
);

-- Test-only tamper simulation: remove B's immutable confirmation only while
-- its guard is explicitly disabled, then forge a syntactically valid pinned
-- binding.  The public replay postcondition must reject that lineage instead
-- of recreating or silently accepting the missing action-time consent.
alter table content_factory.research_operator_price_confirmations
  disable trigger research_operator_price_confirmation_immutable;

delete from content_factory.research_operator_price_confirmations confirmation
where confirmation.run_id = (
  select run_id
  from operator_research_context
  where actor_id = 'dc000000-0000-4000-8000-000000000003'
);

alter table content_factory.research_operator_price_confirmations
  enable trigger research_operator_price_confirmation_immutable;

insert into content_factory.research_run_provider_bindings (
  organization_id, run_id, authorization_id, provider_key,
  adapter_version, model, attempt_number, binding_hash
)
select
  authorization_entry.organization_id,
  authorization_entry.run_id,
  authorization_entry.id,
  'openai_web_search',
  'openai-responses-web-search-v1',
  'gpt-5.5',
  1,
  repeat('e', 64)
from content_factory.research_execution_authorizations authorization_entry
join operator_research_context context_row
  on context_row.run_id = authorization_entry.run_id
where context_row.actor_id =
  'dc000000-0000-4000-8000-000000000003';

do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'dc000000-0000-4000-8000-000000000003',
    true
  );
end;
$$;

select throws_ok(
  $$
    select public.creator_start_project_research(
      pg_temp.operator_research_start_payload(
        'operator-shared-raw-research-key-0001'
      )
    )
  $$,
  '55000',
  'operator_project_research_lineage_invalid',
  'forged provider binding without immutable confirmation cannot replay'
);

select is(
  (
    select count(*)::integer
    from content_factory.research_operator_price_confirmations confirmation
    join operator_research_context context_row
      on context_row.run_id = confirmation.run_id
    where context_row.actor_id =
      'dc000000-0000-4000-8000-000000000003'
  ),
  0,
  'failed forged replay cannot backfill a price confirmation'
);

-- Simulate one pre-migration operator-authored row.  The new constraint is
-- deliberately INSERT-only: after installation, ordinary worker/status
-- updates to an existing legacy row must not demand a fabricated snapshot.
alter table content_factory.product_research_runs
  disable trigger enforce_operator_research_price_confirmation;

insert into content_factory.product_research_runs (
  id, organization_id, project_id, product_id, created_by, status,
  input, request_hash, idempotency_key
) values (
  'dc400000-0000-4000-8000-000000000098',
  'dc100000-0000-4000-8000-000000000001',
  'dc200000-0000-4000-8000-000000000001',
  'dc300000-0000-4000-8000-000000000001',
  'dc000000-0000-4000-8000-000000000002',
  'queued', '{}'::jsonb, repeat('d', 64),
  'legacy-operator-run-before-price-gate-0001'
);

alter table content_factory.product_research_runs
  enable trigger enforce_operator_research_price_confirmation;

update content_factory.product_research_runs run
set status = 'cancelled'
where run.id = 'dc400000-0000-4000-8000-000000000098';

select ok(
  exists (
    select 1
    from content_factory.product_research_runs run
    where run.id = 'dc400000-0000-4000-8000-000000000098'
      and run.status = 'cancelled'
      and run.finished_at is not null
  )
  and not exists (
    select 1
    from content_factory.research_operator_price_confirmations confirmation
    where confirmation.run_id =
      'dc400000-0000-4000-8000-000000000098'
  ),
  'legacy existing operator run update remains valid without backfilled price'
);

select * from finish();
rollback;
