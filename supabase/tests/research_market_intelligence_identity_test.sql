begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

create or replace function pg_temp.market_identity_brief(
  first_source_id uuid,
  second_source_id uuid,
  category_name_value text,
  trend_direction_value text,
  signal_key_value text
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  signal_value jsonb;
begin
  signal_value := jsonb_build_object(
    'signal', 'Single-action product demonstration',
    'direction', trend_direction_value,
    'confidence', 'medium',
    'evidence', 'Two exact fixture sources support this structural direction.',
    'source_ids', jsonb_build_array(
      first_source_id::text, second_source_id::text
    ),
    'recommended_use', 'test'
  );
  if signal_key_value is not null then
    signal_value := signal_value || jsonb_build_object(
      'signal_key', signal_key_value
    );
  end if;

  return jsonb_build_object(
    'summary', 'Market identity fixture research',
    'category_analysis', jsonb_build_object(
      'category_name', category_name_value,
      'maturity', 'growing',
      'definition', 'A bounded market category used only by the identity fixture.',
      'buyer_jobs', jsonb_build_array('Complete a repeatable routine'),
      'substitute_categories', '[]'::jsonb,
      'unknowns', '[]'::jsonb,
      'source_ids', jsonb_build_array(first_source_id::text)
    ),
    'competitor_analysis', jsonb_build_object(
      'coverage', 'sufficient',
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'Fixture competitor',
        'positioning', 'A bounded positioning summary',
        'price_positioning', 'Middle price segment',
        'recurring_formats', jsonb_build_array('One action demonstration'),
        'strengths', jsonb_build_array('Clear proof'),
        'weaknesses', jsonb_build_array('Limited context'),
        'reusable_structures', jsonb_build_array('One action and one result'),
        'source_ids', jsonb_build_array(second_source_id::text)
      )),
      'saturated_patterns', '[]'::jsonb,
      'content_gaps', '[]'::jsonb,
      'limitations', jsonb_build_array('Fixture sample is intentionally small')
    ),
    'trend_analysis', jsonb_build_object(
      'as_of', current_date::text,
      'signals', jsonb_build_array(signal_value),
      'limitations', jsonb_build_array('Direction is bounded to fixture evidence')
    ),
    'guidance', jsonb_build_object(
      'status', 'ready_for_brief',
      'recommended_next_step', 'Confirm the market category',
      'reason', 'Bounded source evidence is present',
      'questions_for_user', '[]'::jsonb,
      'suggested_actions', jsonb_build_array('Review before publishing')
    ),
    'facts', jsonb_build_array(jsonb_build_object(
      'statement', 'A bounded fixture fact',
      'source_ids', jsonb_build_array(first_source_id::text)
    )),
    'audience', jsonb_build_array(jsonb_build_object('name', 'Fixture buyers')),
    'scenarios', jsonb_build_array(jsonb_build_object(
      'title', 'Demonstration',
      'hook', 'Show one action and one result'
    )),
    'task_blueprint', jsonb_build_object('title', 'Produce bounded test'),
    'creative_potential', jsonb_build_object(
      'method', 'prepublication_heuristic_not_probability',
      'score', 60
    )
  );
end;
$$;

create or replace function pg_temp.make_market_identity_run(
  organization_id_value uuid,
  product_id_value uuid,
  actor_id_value uuid,
  run_id_value uuid,
  first_source_id uuid,
  second_source_id uuid,
  ai_draft_id uuid,
  human_draft_id uuid,
  category_name_value text,
  trend_direction_value text,
  signal_key_value text,
  approved_at_value timestamptz
)
returns void
language plpgsql
set search_path = ''
as $$
declare
  brief_value jsonb;
  source_ids_value jsonb;
begin
  brief_value := pg_temp.market_identity_brief(
    first_source_id,
    second_source_id,
    category_name_value,
    trend_direction_value,
    signal_key_value
  );
  source_ids_value := jsonb_build_array(
    first_source_id::text, second_source_id::text
  );

  insert into content_factory.product_research_runs (
    id, organization_id, product_id, created_by, status, input, summary,
    request_hash, completion_hash, idempotency_key, finished_at,
    created_at, updated_at
  ) values (
    run_id_value,
    organization_id_value,
    product_id_value,
    actor_id_value,
    'completed',
    jsonb_build_object('fixture', run_id_value),
    jsonb_build_object('fixture', true),
    content_factory_private.json_hash(jsonb_build_object('run', run_id_value)),
    content_factory_private.json_hash(jsonb_build_object('done', run_id_value)),
    'market-run-' || run_id_value::text,
    approved_at_value - interval '1 hour',
    approved_at_value - interval '2 hours',
    approved_at_value - interval '1 hour'
  );

  insert into content_factory.product_research_sources (
    id, organization_id, run_id, product_id, created_by, source_type,
    title, content_hash, trust_level, extracted_facts, metadata, created_at
  ) values
  (
    first_source_id, organization_id_value, run_id_value, product_id_value,
    actor_id_value, 'user_input', 'First exact market source',
    content_factory_private.json_hash(jsonb_build_object(
      'run', run_id_value, 'source', first_source_id
    )),
    'first_party', '[]'::jsonb,
    jsonb_build_object('model_source_id', 'market-fixture-1'),
    approved_at_value - interval '90 minutes'
  ),
  (
    second_source_id, organization_id_value, run_id_value, product_id_value,
    actor_id_value, 'user_input', 'Second exact market source',
    content_factory_private.json_hash(jsonb_build_object(
      'run', run_id_value, 'source', second_source_id
    )),
    'first_party', '[]'::jsonb,
    jsonb_build_object('model_source_id', 'market-fixture-2'),
    approved_at_value - interval '80 minutes'
  );

  insert into content_factory.creative_brief_drafts (
    id, organization_id, run_id, product_id, previous_draft_id,
    created_by, origin, version, status, title, brief, source_ids,
    task_blueprint, content_hash, created_at
  ) values (
    ai_draft_id,
    organization_id_value,
    run_id_value,
    product_id_value,
    null,
    actor_id_value,
    'ai',
    1,
    'draft',
    'AI market identity evidence',
    brief_value,
    source_ids_value,
    jsonb_build_array(jsonb_build_object('title', 'Produce bounded test')),
    content_factory_private.json_hash(jsonb_build_object(
      'brief', brief_value, 'origin', 'ai'
    )),
    approved_at_value - interval '45 minutes'
  );
  insert into content_factory.creative_brief_drafts (
    id, organization_id, run_id, product_id, previous_draft_id,
    created_by, origin, version, status, title, brief, source_ids,
    task_blueprint, content_hash, created_at
  ) values (
    human_draft_id,
    organization_id_value,
    run_id_value,
    product_id_value,
    ai_draft_id,
    actor_id_value,
    'human',
    2,
    'draft',
    'Human market identity evidence',
    brief_value,
    source_ids_value,
    jsonb_build_array(jsonb_build_object('title', 'Produce bounded test')),
    content_factory_private.json_hash(jsonb_build_object(
      'brief', brief_value, 'origin', 'human'
    )),
    approved_at_value - interval '30 minutes'
  );
  update content_factory.creative_brief_drafts draft
  set status = 'approved',
      approved_by = actor_id_value,
      approved_at = approved_at_value
  where draft.id = human_draft_id;
end;
$$;

select has_table(
  'content_factory', 'research_market_categories',
  'tenant market category registry exists'
);
select has_table(
  'content_factory', 'research_market_category_aliases',
  'exact market category aliases exist'
);
select has_table(
  'content_factory', 'research_product_market_category_bindings',
  'append-only product category bindings exist'
);
select has_table(
  'content_factory', 'research_structural_trend_signal_types',
  'structural trend signal allowlist exists'
);
select has_table(
  'content_factory', 'research_watchlist_snapshot_trend_signals',
  'canonical trend observations exist'
);
select has_table(
  'content_factory', 'research_watchlist_snapshot_trend_signal_sources',
  'exact canonical trend source junction exists'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_market_categories'::regclass),
     ('content_factory.research_market_category_aliases'::regclass),
     ('content_factory.research_product_market_category_bindings'::regclass),
     ('content_factory.research_structural_trend_signal_types'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signals'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signal_sources'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  6,
  'all market identity tables have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_market_categories'::regclass),
     ('content_factory.research_market_category_aliases'::regclass),
     ('content_factory.research_product_market_category_bindings'::regclass),
     ('content_factory.research_structural_trend_signal_types'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signals'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signal_sources'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('authenticated', table_oid, privilege.name)),
  0,
  'authenticated has no direct market identity table privileges'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_market_categories'::regclass),
     ('content_factory.research_market_category_aliases'::regclass),
     ('content_factory.research_product_market_category_bindings'::regclass),
     ('content_factory.research_structural_trend_signal_types'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signals'::regclass),
     ('content_factory.research_watchlist_snapshot_trend_signal_sources'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('service_role', table_oid, privilege.name)),
  0,
  'service role cannot bypass the market identity RPC boundary'
);

select has_function(
  'public', 'creator_research_market_category_registry', array['jsonb'],
  'bounded market category registry RPC exists'
);
select has_function(
  'public', 'creator_resolve_research_market_category', array['jsonb'],
  'explicit market category decision RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_research_market_category_registry(jsonb)',
    'execute'
  ),
  'authenticated may call the registry RPC'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_resolve_research_market_category(jsonb)',
    'execute'
  ),
  'authenticated may call the decision RPC'
);
select ok(
  not has_function_privilege(
    'service_role',
    'public.creator_resolve_research_market_category(jsonb)',
    'execute'
  ),
  'service role cannot bypass explicit human category confirmation'
);
select is(
  (select count(*)::integer
   from content_factory.research_structural_trend_signal_types),
  14,
  'the initial structural signal catalog is small and allowlisted'
);
select ok(
  not exists (
    select 1
    from content_factory.research_structural_trend_signal_types signal
    where signal.signal_key !~ '^[a-z][a-z0-9_]*[.][a-z][a-z0-9_.]*$'
      or signal.status <> 'active'
      or signal.catalog_version <> 1
  ),
  'every seed has a stable structural key and explicit catalog version'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_resolve_research_market_category(jsonb)'::regprocedure
  )), 'insert into content_factory.product_research_runs') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_resolve_research_market_category(jsonb)'::regprocedure
  )), 'creator_start_product_research') = 0,
  'category decisions contain no research-run creation or paid provider path'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_market_category_registry(jsonb)'::regprocedure
  )), 'limit timeline_limit_value') > 0,
  'canonical trend timeline is server-bounded'
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
  ('b8000000-0000-4000-8000-000000000001', 'market-owner@example.test', 'Market Owner'),
  ('b8000000-0000-4000-8000-000000000002', 'market-producer@example.test', 'Market Producer'),
  ('b8000000-0000-4000-8000-000000000003', 'market-reviewer@example.test', 'Market Reviewer'),
  ('b8000000-0000-4000-8000-000000000004', 'market-other@example.test', 'Other Market Owner')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('b8100000-0000-4000-8000-000000000001', 'Market Tenant', 'market-tenant-test', 'active'),
  ('b8100000-0000-4000-8000-000000000002', 'Other Market Tenant', 'other-market-test', 'active');
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('b8100000-0000-4000-8000-000000000001', 'b8000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('b8100000-0000-4000-8000-000000000001', 'b8000000-0000-4000-8000-000000000002', 'producer', 'active'),
  ('b8100000-0000-4000-8000-000000000001', 'b8000000-0000-4000-8000-000000000003', 'reviewer', 'active'),
  ('b8100000-0000-4000-8000-000000000002', 'b8000000-0000-4000-8000-000000000004', 'owner', 'active');
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values
  ('b8200000-0000-4000-8000-000000000001', 'b8100000-0000-4000-8000-000000000001', 'MARKET-1', 'Market Product One', 'active', 'b8000000-0000-4000-8000-000000000001'),
  ('b8200000-0000-4000-8000-000000000002', 'b8100000-0000-4000-8000-000000000001', 'MARKET-2', 'Market Product Two', 'active', 'b8000000-0000-4000-8000-000000000001'),
  ('b8200000-0000-4000-8000-000000000003', 'b8100000-0000-4000-8000-000000000001', 'MARKET-3', 'Legacy Product', 'active', 'b8000000-0000-4000-8000-000000000001'),
  ('b8200000-0000-4000-8000-000000000004', 'b8100000-0000-4000-8000-000000000001', 'MARKET-4', 'Unknown Signal Product', 'active', 'b8000000-0000-4000-8000-000000000001'),
  ('b8200000-0000-4000-8000-000000000005', 'b8100000-0000-4000-8000-000000000002', 'OTHER-1', 'Other Tenant Product', 'active', 'b8000000-0000-4000-8000-000000000004');

select pg_temp.make_market_identity_run(
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000001',
  'b8400000-0000-4000-8000-000000000001',
  'b8400000-0000-4000-8000-000000000002',
  'b8500000-0000-4000-8000-000000000001',
  'b8500000-0000-4000-8000-000000000002',
  'Hair styling tools', 'growing', 'format.single_action_demo',
  now() - interval '4 days'
);
select pg_temp.make_market_identity_run(
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000002',
  'b8000000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000003',
  'b8400000-0000-4000-8000-000000000005',
  'b8400000-0000-4000-8000-000000000006',
  'b8500000-0000-4000-8000-000000000005',
  'b8500000-0000-4000-8000-000000000006',
  'Hair care routines', 'stable', null,
  now() - interval '3 days'
);
select pg_temp.make_market_identity_run(
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000003',
  'b8000000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000004',
  'b8400000-0000-4000-8000-000000000007',
  'b8400000-0000-4000-8000-000000000008',
  'Styling accessories', 'stable', null,
  now() - interval '2 days'
);
select pg_temp.make_market_identity_run(
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000004',
  'b8000000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000005',
  'b8400000-0000-4000-8000-000000000009',
  'b8400000-0000-4000-8000-000000000010',
  'Unknown signal fixture', 'growing', 'format.not_allowlisted',
  now() - interval '1 day'
);
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, idempotency_key, created_at, updated_at
) values (
  'b8300000-0000-4000-8000-000000000006',
  'b8100000-0000-4000-8000-000000000002',
  'b8200000-0000-4000-8000-000000000005',
  'b8000000-0000-4000-8000-000000000004',
  'queued',
  '{"fixture":true}'::jsonb,
  '{}'::jsonb,
  repeat('a', 64),
  'other-market-run-fixture',
  now(), now()
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', 'b8000000-0000-4000-8000-000000000001', true
  );
end $$;

create temporary table market_identity_context (
  explicit_run_count integer,
  product_one_registry jsonb,
  category_a_result jsonb,
  category_b_result jsonb,
  category_a_id uuid,
  category_b_id uuid,
  product_two_candidate_hash text,
  product_three_candidate_hash text,
  second_product_one_candidate_hash text
) on commit drop;
insert into market_identity_context (explicit_run_count)
select count(*)::integer from content_factory.product_research_runs;

update market_identity_context
set product_one_registry = public.creator_research_market_category_registry(
  jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001'
  )
);
select is(
  (select jsonb_agg(key.value order by key.value)
   from market_identity_context context,
     lateral jsonb_object_keys(context.product_one_registry) key(value)),
  '["can_resolve","candidate","categories","current_binding","guidance","ok","product_id","trend_timeline"]'::jsonb,
  'registry response has the exact bounded top-level contract'
);
select is(
  (select product_one_registry ->> 'can_resolve'
   from market_identity_context),
  'true',
  'owner receives an explicit category decision capability'
);
select is(
  (select product_one_registry #>> '{guidance,status}'
   from market_identity_context),
  'needs_user_decision',
  'an unbound product asks for an explicit category decision'
);
select is(
  (select product_one_registry -> 'current_binding'
   from market_identity_context),
  'null'::jsonb,
  'the initial registry has no implicit binding'
);
select is(
  length((select product_one_registry #>> '{candidate,candidate_hash}'
          from market_identity_context)),
  64,
  'candidate exposes a stable exact hash for stale-tab protection'
);

select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'create_and_bind',
    'candidate_hash', repeat('0', 64),
    'canonical_name', 'Hair styling tools',
    'definition', 'A stale candidate must never create this category.',
    'confirmation', true,
    'idempotency_key', 'market-stale-candidate'
  ))$$,
  '55000', 'research_market_category_candidate_stale',
  'stale candidate hashes are rejected under the decision lock'
);
select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'create_and_bind',
    'candidate_hash', (
      select product_one_registry #>> '{candidate,candidate_hash}'
      from market_identity_context
    ),
    'canonical_name', 'Hair styling tools',
    'definition', 'A category cannot be created without explicit confirmation.',
    'confirmation', false,
    'idempotency_key', 'market-no-confirmation'
  ))$$,
  '22023', 'research_market_decision_confirmation_required',
  'every market category decision requires explicit true confirmation'
);

update market_identity_context
set category_a_result = public.creator_resolve_research_market_category(
  jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'create_and_bind',
    'candidate_hash', product_one_registry #>> '{candidate,candidate_hash}',
    'canonical_name', 'Hair-Styling Tools',
    'definition', 'Tools used for a bounded and repeatable hair styling routine.',
    'aliases', jsonb_build_array('Hot Styling Devices', 'Hair Styling Tools'),
    'confirmation', true,
    'reason', 'Owner confirmed the stable market identity.',
    'idempotency_key', 'market-create-category-a'
  )
);
update market_identity_context
set category_a_id = (category_a_result #>> '{category,category_key}')::uuid;
select is(
  (select jsonb_agg(key.value order by key.value)
   from market_identity_context context,
     lateral jsonb_object_keys(context.category_a_result) key(value)),
  '["binding","category","guidance","ok"]'::jsonb,
  'decision response has the exact top-level contract'
);
select is(
  (select count(*)::integer from content_factory.research_market_categories),
  1,
  'create_and_bind creates one stable tenant category'
);
select is(
  (select count(*)::integer from content_factory.research_market_category_aliases),
  2,
  'canonical and supplied aliases are exactly normalized and deduplicated'
);
select is(
  (select count(*)::integer
   from content_factory.research_product_market_category_bindings),
  1,
  'create_and_bind appends the first product binding'
);
select is(
  (select count(*)::integer from content_factory.product_research_runs),
  (select explicit_run_count from market_identity_context),
  'category creation never creates or queues product research'
);
select is(
  public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'create_and_bind',
    'candidate_hash', (
      select product_one_registry #>> '{candidate,candidate_hash}'
      from market_identity_context
    ),
    'canonical_name', 'Hair-Styling Tools',
    'definition', 'Tools used for a bounded and repeatable hair styling routine.',
    'aliases', jsonb_build_array('Hot Styling Devices', 'Hair Styling Tools'),
    'confirmation', true,
    'reason', 'Owner confirmed the stable market identity.',
    'idempotency_key', 'market-create-category-a'
  )),
  (select category_a_result from market_identity_context),
  'an exact idempotency replay returns its stored response'
);
select is(
  (select count(*)::integer
   from content_factory.research_product_market_category_bindings),
  1,
  'idempotency replay cannot append another binding'
);
select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'create_and_bind',
    'candidate_hash', (
      select product_one_registry #>> '{candidate,candidate_hash}'
      from market_identity_context
    ),
    'canonical_name', 'Hair-Styling Tools',
    'definition', 'Tools used for a bounded and repeatable hair styling routine.',
    'aliases', jsonb_build_array('Hot Styling Devices', 'Hair Styling Tools'),
    'confirmation', true,
    'reason', 'A conflicting reuse of the same command key.',
    'idempotency_key', 'market-create-category-a'
  ))$$,
  '23505', 'idempotency_key_conflict',
  'same idempotency key with a different request is rejected'
);

select is(
  jsonb_array_length(public.creator_research_market_category_registry(
    jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001',
      'run_id', 'b8300000-0000-4000-8000-000000000001',
      'query', '  HAIR styling tools  '
    )
  ) -> 'categories'),
  1,
  'case, punctuation, and whitespace normalization find an exact alias'
);
select is(
  jsonb_array_length(public.creator_research_market_category_registry(
    jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001',
      'run_id', 'b8300000-0000-4000-8000-000000000001',
      'query', 'Hair stylng tools'
    )
  ) -> 'categories'),
  0,
  'the registry performs no fuzzy or typo-based merge'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'b8000000-0000-4000-8000-000000000002', true
  );
end $$;
update market_identity_context
set product_two_candidate_hash =
  public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000003'
  )) #>> '{candidate,candidate_hash}';
select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000003',
    'action', 'create_and_bind',
    'candidate_hash', (
      select product_two_candidate_hash from market_identity_context
    ),
    'canonical_name', 'hair styling tools',
    'definition', 'An exact alias collision must be resolved by choosing the existing category.',
    'confirmation', true,
    'idempotency_key', 'market-exact-alias-conflict'
  ))$$,
  '23505', 'research_market_category_alias_conflict',
  'exact normalized aliases cannot identify two tenant categories'
);
update market_identity_context
set category_b_result = public.creator_resolve_research_market_category(
  jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000003',
    'action', 'create_and_bind',
    'candidate_hash', product_two_candidate_hash,
    'canonical_name', 'Hair care routines',
    'definition', 'A distinct routine category confirmed by the tenant producer.',
    'confirmation', true,
    'idempotency_key', 'market-create-category-b'
  )
);
update market_identity_context
set category_b_id = (category_b_result #>> '{category,category_key}')::uuid;
select is(
  (select category_b_result #>> '{binding,decision_action}'
   from market_identity_context),
  'create_and_bind',
  'producer role may make an explicitly confirmed category decision'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'b8000000-0000-4000-8000-000000000003', true
  );
end $$;
select lives_ok(
  $$select public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001'
  ))$$,
  'reviewer may read tenant-local category intelligence'
);
select is(
  public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001'
  )) ->> 'can_resolve',
  'false',
  'reviewer receives read-only category capability'
);
select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'reclassify',
    'candidate_hash', (
      select product_one_registry #>> '{candidate,candidate_hash}'
      from market_identity_context
    ),
    'category_id', (select category_b_id from market_identity_context),
    'confirmation', true,
    'idempotency_key', 'market-reviewer-denied'
  ))$$,
  '42501', 'role_not_allowed',
  'reviewer cannot write category decisions'
);
select throws_ok(
  $$select public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000002',
    'run_id', 'b8300000-0000-4000-8000-000000000006'
  ))$$,
  '22023', 'research_run_not_found',
  'another tenant run is hidden behind the exact membership boundary'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'b8000000-0000-4000-8000-000000000001', true
  );
end $$;
update market_identity_context
set product_three_candidate_hash =
  public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000004'
  )) #>> '{candidate,candidate_hash}';
select is(
  public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000004',
    'action', 'bind_existing',
    'candidate_hash', (
      select product_three_candidate_hash from market_identity_context
    ),
    'category_id', (select category_a_id from market_identity_context),
    'confirmation', true,
    'idempotency_key', 'market-bind-existing-product-three'
  )) #>> '{binding,decision_action}',
  'bind_existing',
  'an unbound product can explicitly choose an existing exact category'
);
select is(
  public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000004',
    'action', 'reclassify',
    'candidate_hash', (
      select product_three_candidate_hash from market_identity_context
    ),
    'category_id', (select category_b_id from market_identity_context),
    'confirmation', true,
    'reason', 'Owner chose a different existing category before capture.',
    'idempotency_key', 'market-reclassify-existing-product-three'
  )) #>> '{binding,decision_action}',
  'reclassify',
  'a bound product can explicitly reclassify into an existing category'
);
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000004',
    'action', 'enable', 'refresh_interval_days', 14,
    'idempotency_key', 'market-enable-legacy-v2'
  ))$$,
  'legacy v2 research without signal_key remains valid'
);
select is(
  (select count(*)::integer
   from content_factory.research_watchlist_snapshot_trend_signals observation
   where observation.product_id = 'b8200000-0000-4000-8000-000000000003'),
  0,
  'legacy signals are not guessed or fuzzily mapped to canonical keys'
);
select throws_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000005',
    'action', 'enable', 'refresh_interval_days', 14,
    'idempotency_key', 'market-enable-unknown-signal'
  ))$$,
  '22023', 'canonical_trend_signal_not_allowlisted',
  'a present but unknown signal_key fails closed instead of being guessed'
);

select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'enable', 'refresh_interval_days', 14,
    'idempotency_key', 'market-enable-product-one'
  ))$$,
  'bound canonical research captures its first trend observation'
);
select is(
  (select market_category_id
   from content_factory.research_watchlist_snapshot_trend_signals observation
   where observation.product_id = 'b8200000-0000-4000-8000-000000000001'),
  (select category_a_id from market_identity_context),
  'first canonical observation freezes category A identity'
);
select is(
  (select count(*)::integer
   from content_factory.research_watchlist_snapshot_trend_signal_sources source_link
   join content_factory.research_watchlist_snapshot_trend_signals observation
     on observation.organization_id = source_link.organization_id
    and observation.snapshot_id = source_link.snapshot_id
    and observation.signal_key = source_link.signal_key
   where observation.product_id = 'b8200000-0000-4000-8000-000000000001'),
  2,
  'canonical observation stores its exact two-source junction'
);
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'pause',
    'idempotency_key', 'market-pause-before-reclassify'
  ))$$,
  'watchlist may pause while a category is reconsidered'
);

select pg_temp.make_market_identity_run(
  'b8100000-0000-4000-8000-000000000001',
  'b8200000-0000-4000-8000-000000000001',
  'b8000000-0000-4000-8000-000000000001',
  'b8300000-0000-4000-8000-000000000002',
  'b8400000-0000-4000-8000-000000000003',
  'b8400000-0000-4000-8000-000000000004',
  'b8500000-0000-4000-8000-000000000003',
  'b8500000-0000-4000-8000-000000000004',
  'Heat styling workflows', 'declining', 'format.single_action_demo',
  now() - interval '1 hour'
);
update market_identity_context
set explicit_run_count = (
      select count(*)::integer from content_factory.product_research_runs
    ),
    second_product_one_candidate_hash =
      public.creator_research_market_category_registry(jsonb_build_object(
        'organization_id', 'b8100000-0000-4000-8000-000000000001',
        'run_id', 'b8300000-0000-4000-8000-000000000002'
      )) #>> '{candidate,candidate_hash}';
select is(
  public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001'
  )) -> 'candidate',
  'null'::jsonb,
  'an older run stops offering a category candidate after newer product evidence exists'
);
select throws_ok(
  $$select public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000001',
    'action', 'reclassify',
    'candidate_hash', (
      select product_one_registry #>> '{candidate,candidate_hash}'
      from market_identity_context
    ),
    'category_id', (select category_b_id from market_identity_context),
    'confirmation', true,
    'reason', 'Old evidence must not change the current category.',
    'idempotency_key', 'market-old-run-stale-after-newer-evidence'
  ))$$,
  '55000', 'research_market_category_candidate_stale',
  'an old run cannot reclassify after newer product evidence exists'
);
select is(
  public.creator_resolve_research_market_category(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000002',
    'action', 'create_and_reclassify',
    'candidate_hash', (
      select second_product_one_candidate_hash from market_identity_context
    ),
    'canonical_name', 'Heat styling workflows',
    'definition', 'A newly confirmed workflow category created during explicit reclassification.',
    'aliases', jsonb_build_array('Heated styling workflow'),
    'confirmation', true,
    'reason', 'New approved research changes the market boundary.',
    'idempotency_key', 'market-create-reclassify-product-one'
  )) #>> '{binding,binding_version}',
  '2',
  'create_and_reclassify appends binding version two'
);
select is(
  (select decision_action
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'b8200000-0000-4000-8000-000000000001'
   order by binding.binding_version desc limit 1),
  'create_and_reclassify',
  'an already-bound product can safely create a genuinely new category'
);
select is(
  (select count(*)::integer
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'b8200000-0000-4000-8000-000000000001'),
  2,
  'reclassification preserves the previous binding row'
);
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000002',
    'action', 'resume', 'refresh_interval_days', 14,
    'idempotency_key', 'market-resume-after-reclassify'
  ))$$,
  'resume captures the explicitly selected post-reclassification snapshot'
);
select is(
  (select count(*)::integer
   from content_factory.research_watchlist_snapshot_trend_signals observation
   where observation.product_id = 'b8200000-0000-4000-8000-000000000001'),
  2,
  'two canonical snapshots produce two immutable observations'
);
select is(
  (select count(distinct observation.market_category_id)::integer
   from content_factory.research_watchlist_snapshot_trend_signals observation
   where observation.product_id = 'b8200000-0000-4000-8000-000000000001'),
  2,
  'old and new observations retain their exact category identities'
);
select is(
  (public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000002'
  )) #>> '{trend_timeline,0,comparison_mode}'),
  'category_reset',
  'timeline resets comparison when the stable category identity changes'
);
select is(
  (public.creator_research_market_category_registry(jsonb_build_object(
    'organization_id', 'b8100000-0000-4000-8000-000000000001',
    'run_id', 'b8300000-0000-4000-8000-000000000002'
  )) #> '{trend_timeline,0,potential_contradiction}'),
  'false'::jsonb,
  'growing-to-declining across categories is not a false contradiction'
);
select is(
  (select count(*)::integer
   from content_factory.research_watchlist_snapshot_trend_signal_sources source_link
   join content_factory.research_watchlist_snapshot_trend_signals observation
     on observation.organization_id = source_link.organization_id
    and observation.snapshot_id = source_link.snapshot_id
    and observation.signal_key = source_link.signal_key
   where observation.product_id = 'b8200000-0000-4000-8000-000000000001'),
  4,
  'both observations retain two exact source links'
);
select ok(
  not (
    public.creator_research_market_category_registry(jsonb_build_object(
      'organization_id', 'b8100000-0000-4000-8000-000000000001',
      'run_id', 'b8300000-0000-4000-8000-000000000002'
    )) -> 'trend_timeline'
  )::text ~* 'competitor|evidence|caption|transcript|source_url',
  'canonical timeline exposes no competitor copy or raw evidence fields'
);
select is(
  (select count(*)::integer from content_factory.product_research_runs),
  (select explicit_run_count from market_identity_context),
  'bind, reclassify, registry, and timeline operations create no research run'
);

select throws_ok(
  $$update content_factory.research_market_categories
    set canonical_name = canonical_name
    where id = (select category_a_id from market_identity_context)$$,
  '55000', 'research_market_categories_append_only',
  'stable market categories reject every update'
);
select throws_ok(
  $$delete from content_factory.research_market_category_aliases
    where category_id = (select category_a_id from market_identity_context)$$,
  '55000', 'research_market_category_aliases_append_only',
  'exact aliases reject deletion'
);
select throws_ok(
  $$delete from content_factory.research_product_market_category_bindings
    where product_id = 'b8200000-0000-4000-8000-000000000001'$$,
  '55000', 'research_product_market_category_bindings_append_only',
  'category binding decisions reject deletion'
);
select throws_ok(
  $$update content_factory.research_structural_trend_signal_types
    set canonical_label = canonical_label
    where signal_key = 'format.single_action_demo'$$,
  '55000', 'research_structural_trend_signal_types_append_only',
  'seeded signal identities reject every update'
);
select throws_ok(
  $$update content_factory.research_watchlist_snapshot_trend_signals
    set direction = direction
    where product_id = 'b8200000-0000-4000-8000-000000000001'$$,
  '55000', 'research_watchlist_snapshot_trend_signals_append_only',
  'canonical observations reject every update'
);
select throws_ok(
  $$delete from content_factory.research_watchlist_snapshot_trend_signal_sources
    where signal_key = 'format.single_action_demo'$$,
  '55000', 'research_watchlist_snapshot_trend_signal_sources_append_only',
  'exact canonical source links reject deletion'
);

select * from finish();
rollback;
