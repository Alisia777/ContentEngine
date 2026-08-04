begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

create or replace function pg_temp.watch_brief(
  first_source_id uuid,
  second_source_id uuid,
  competitor_positioning text,
  trend_direction text,
  as_of_value date
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'summary', 'Approved v2 temporal research fixture',
    'category_analysis', jsonb_build_object(
      'category_name', 'Hair styling tools',
      'maturity', 'growing',
      'definition', 'Tools used for a bounded hair styling routine.',
      'buyer_jobs', jsonb_build_array('Create a repeatable style'),
      'substitute_categories', '[]'::jsonb,
      'unknowns', '[]'::jsonb,
      'source_ids', jsonb_build_array(first_source_id::text)
    ),
    'competitor_analysis', jsonb_build_object(
      'coverage', 'sufficient',
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'Competitor A',
        'positioning', competitor_positioning,
        'price_positioning', 'Middle price segment',
        'recurring_formats', jsonb_build_array('Demonstration'),
        'strengths', jsonb_build_array('Clear proof'),
        'weaknesses', jsonb_build_array('Limited context'),
        'reusable_structures', jsonb_build_array('One action and one result'),
        'source_ids', jsonb_build_array(second_source_id::text)
      )),
      'saturated_patterns', '[]'::jsonb,
      'content_gaps', '[]'::jsonb,
      'limitations', jsonb_build_array('Small public sample')
    ),
    'trend_analysis', jsonb_build_object(
      'as_of', as_of_value::text,
      'signals', jsonb_build_array(jsonb_build_object(
        'signal', 'Single-action demonstrations',
        'direction', trend_direction,
        'confidence', 'medium',
        'evidence', 'Two source-bound examples support the bounded direction.',
        'source_ids', jsonb_build_array(
          first_source_id::text, second_source_id::text
        ),
        'recommended_use', 'test'
      )),
      'limitations', jsonb_build_array('Directional evidence is bounded')
    ),
    'guidance', jsonb_build_object(
      'status', 'ready_for_brief',
      'recommended_next_step', 'Test one source-backed demonstration',
      'reason', 'Category, competitor, and trend evidence are available',
      'questions_for_user', '[]'::jsonb,
      'suggested_actions', jsonb_build_array('Review sources before publishing')
    ),
    'facts', jsonb_build_array(jsonb_build_object(
      'statement', 'A bounded fixture fact',
      'source_ids', jsonb_build_array(first_source_id::text)
    )),
    'audience', jsonb_build_array(jsonb_build_object('name', 'Home stylists')),
    'scenarios', jsonb_build_array(jsonb_build_object(
      'title', 'Demonstration',
      'hook', 'Show one action and one visible result'
    )),
    'task_blueprint', jsonb_build_object('title', 'Produce bounded test'),
    'creative_potential', jsonb_build_object(
      'method', 'prepublication_heuristic_not_probability',
      'score', 60
    )
  )
$$;

create or replace function pg_temp.make_approved_watch_run(
  organization_id_value uuid,
  product_id_value uuid,
  actor_id_value uuid,
  run_id_value uuid,
  first_source_id uuid,
  second_source_id uuid,
  ai_draft_id uuid,
  human_draft_id uuid,
  competitor_positioning text,
  trend_direction text,
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
  brief_value := pg_temp.watch_brief(
    first_source_id,
    second_source_id,
    competitor_positioning,
    trend_direction,
    approved_at_value::date
  );
  source_ids_value := jsonb_build_array(
    second_source_id::text, first_source_id::text, first_source_id::text
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
    content_factory_private.json_hash(jsonb_build_object('complete', run_id_value)),
    'watch-run-' || run_id_value::text,
    approved_at_value - interval '1 hour',
    approved_at_value - interval '2 hours',
    approved_at_value - interval '1 hour'
  );

  insert into content_factory.product_research_sources (
    id, organization_id, run_id, product_id, created_by, source_type,
    title, content_hash, trust_level, extracted_facts, metadata,
    created_at
  ) values
  (
    first_source_id, organization_id_value, run_id_value, product_id_value,
    actor_id_value, 'user_input', 'First bounded source',
    content_factory_private.json_hash(jsonb_build_object(
      'run', run_id_value, 'source', first_source_id
    )),
    'first_party', '[]'::jsonb,
    jsonb_build_object('model_source_id', 'fixture-source-1'),
    approved_at_value - interval '90 minutes'
  ),
  (
    second_source_id, organization_id_value, run_id_value, product_id_value,
    actor_id_value, 'user_input', 'Second bounded source',
    content_factory_private.json_hash(jsonb_build_object(
      'run', run_id_value, 'source', second_source_id
    )),
    'first_party', '[]'::jsonb,
    jsonb_build_object('model_source_id', 'fixture-source-2'),
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
    'Research evidence',
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
    'Research evidence',
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
  'content_factory', 'research_watchlists', 'research watchlists table exists'
);
select has_table(
  'content_factory', 'research_watchlist_snapshots',
  'immutable research snapshots table exists'
);
select has_table(
  'content_factory', 'research_watchlist_snapshot_sources',
  'exact snapshot source junction exists'
);
select has_table(
  'content_factory', 'research_refresh_proposals',
  'provider-free refresh proposals table exists'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_watchlists'::regclass),
     ('content_factory.research_watchlist_snapshots'::regclass),
     ('content_factory.research_watchlist_snapshot_sources'::regclass),
     ('content_factory.research_refresh_proposals'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  4,
  'all watchlist memory tables have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_watchlists'::regclass),
     ('content_factory.research_watchlist_snapshots'::regclass),
     ('content_factory.research_watchlist_snapshot_sources'::regclass),
     ('content_factory.research_refresh_proposals'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('authenticated', table_oid, privilege.name)),
  0,
  'authenticated has no direct watchlist memory table privileges'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_watchlists'::regclass),
     ('content_factory.research_watchlist_snapshots'::regclass),
     ('content_factory.research_watchlist_snapshot_sources'::regclass),
     ('content_factory.research_refresh_proposals'::regclass)
   ) protected(table_oid)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege('service_role', table_oid, privilege.name)),
  0,
  'service role also uses RPCs instead of direct watchlist table access'
);

select has_function(
  'public', 'creator_configure_research_watchlist', array['jsonb'],
  'watchlist configure RPC exists'
);
select has_function(
  'public', 'creator_research_watchlist_status', array['jsonb'],
  'bounded watchlist status RPC exists'
);
select has_function(
  'public', 'system_propose_due_research_refreshes', array['jsonb'],
  'provider-free due proposal RPC exists'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_configure_research_watchlist(jsonb)',
    'execute'
  ),
  'authenticated may call configure RPC'
);
select ok(
  has_function_privilege(
    'authenticated', 'public.creator_research_watchlist_status(jsonb)',
    'execute'
  ),
  'authenticated may call status RPC'
);
select ok(
  not has_function_privilege(
    'authenticated', 'public.system_propose_due_research_refreshes(jsonb)',
    'execute'
  ),
  'browser roles cannot call the system proposal RPC'
);
select ok(
  has_function_privilege(
    'service_role', 'public.system_propose_due_research_refreshes(jsonb)',
    'execute'
  ),
  'service role may call the bounded proposal RPC'
);
select ok(
  not has_function_privilege(
    'service_role', 'public.creator_configure_research_watchlist(jsonb)',
    'execute'
  ),
  'service role cannot bypass the authenticated configure contract'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_refreshes(jsonb)'::regprocedure
  )), 'product_research_runs') = 0
  and strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_refreshes(jsonb)'::regprocedure
  )), 'creator_start_product_research') = 0,
  'due proposal function has no research-run creation or start path'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_watchlist_status(jsonb)'::regprocedure
  )), 'limit 8') > 0,
  'status implementation bounds snapshot payload to latest eight'
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
  ('a8000000-0000-4000-8000-000000000001', 'watch-owner@example.test', 'Watch Owner'),
  ('a8000000-0000-4000-8000-000000000002', 'watch-reviewer@example.test', 'Watch Reviewer'),
  ('a8000000-0000-4000-8000-000000000003', 'other-owner@example.test', 'Other Owner')
) fixture(id, email, display_name);

insert into content_factory.organizations (id, name, slug, status)
values
  ('a8100000-0000-4000-8000-000000000001', 'Watch Tenant', 'watch-tenant-test', 'active'),
  ('a8100000-0000-4000-8000-000000000002', 'Other Tenant', 'other-watch-test', 'active');
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values
  ('a8100000-0000-4000-8000-000000000001', 'a8000000-0000-4000-8000-000000000001', 'owner', 'active'),
  ('a8100000-0000-4000-8000-000000000001', 'a8000000-0000-4000-8000-000000000002', 'reviewer', 'active'),
  ('a8100000-0000-4000-8000-000000000002', 'a8000000-0000-4000-8000-000000000003', 'owner', 'active');
insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
)
values
  ('a8200000-0000-4000-8000-000000000001', 'a8100000-0000-4000-8000-000000000001', 'WATCH-1', 'Watch Product', 'active', 'a8000000-0000-4000-8000-000000000001'),
  ('a8200000-0000-4000-8000-000000000002', 'a8100000-0000-4000-8000-000000000002', 'WATCH-2', 'Other Product', 'active', 'a8000000-0000-4000-8000-000000000003');

select pg_temp.make_approved_watch_run(
  'a8100000-0000-4000-8000-000000000001',
  'a8200000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000001',
  'a8300000-0000-4000-8000-000000000001',
  'a8400000-0000-4000-8000-000000000001',
  'a8400000-0000-4000-8000-000000000002',
  'a8500000-0000-4000-8000-000000000001',
  'a8500000-0000-4000-8000-000000000002',
  'Practical daily styling',
  'growing',
  now() - interval '10 days'
);
select pg_temp.make_approved_watch_run(
  'a8100000-0000-4000-8000-000000000002',
  'a8200000-0000-4000-8000-000000000002',
  'a8000000-0000-4000-8000-000000000003',
  'a8300000-0000-4000-8000-000000000004',
  'a8400000-0000-4000-8000-000000000007',
  'a8400000-0000-4000-8000-000000000008',
  'a8500000-0000-4000-8000-000000000007',
  'a8500000-0000-4000-8000-000000000008',
  'Other tenant positioning',
  'stable',
  now() - interval '8 days'
);

do $$ begin
  perform set_config('request.jwt.claim.role', 'authenticated', true);
  perform set_config(
    'request.jwt.claim.sub', 'a8000000-0000-4000-8000-000000000001', true
  );
end $$;

create temporary table watch_test_context (
  research_run_count integer,
  enable_result jsonb,
  first_system_result jsonb,
  repeat_system_result jsonb
) on commit drop;
insert into watch_test_context (research_run_count)
select count(*)::integer from content_factory.product_research_runs;

update watch_test_context
set enable_result = public.creator_configure_research_watchlist(
  jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'enable',
    'refresh_interval_days', 3,
    'idempotency_key', 'watch-enable-baseline'
  )
);

select is(
  (select count(*)::integer from content_factory.product_research_runs),
  (select research_run_count from watch_test_context),
  'enabling a watchlist never creates a research run'
);
select is(
  (select count(*)::integer from content_factory.research_watchlists),
  1,
  'enable creates one tenant-local watchlist'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  1,
  'enable captures one approved-v2 baseline snapshot'
);
select is(
  (select count(*)::integer
   from content_factory.research_watchlist_snapshot_sources),
  2,
  'baseline snapshot has an exact two-row source junction'
);
select is(
  (select change_set -> 'baseline'
   from content_factory.research_watchlist_snapshots),
  'true'::jsonb,
  'first approved snapshot is explicitly marked as a baseline'
);
select is(
  (select source_ids
   from content_factory.research_watchlist_snapshots),
  (select jsonb_agg(source_link.source_id order by source_link.ordinal)
   from content_factory.research_watchlist_snapshot_sources source_link),
  'stored canonical sources equal the exact ordered junction'
);
select is(
  public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'enable',
    'refresh_interval_days', 3,
    'idempotency_key', 'watch-enable-baseline'
  )),
  (select enable_result from watch_test_context),
  'configure replay returns the stored response'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  1,
  'configure replay cannot duplicate an immutable snapshot'
);

select throws_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'update', 'refresh_interval_days', 2,
    'idempotency_key', 'watch-interval-too-short'
  ))$$,
  '22023', 'refresh_interval_days_invalid',
  'server rejects refresh intervals below three days'
);
select throws_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'update', 'refresh_interval_days', 91,
    'idempotency_key', 'watch-interval-too-long'
  ))$$,
  '22023', 'refresh_interval_days_invalid',
  'server rejects refresh intervals above ninety days'
);

select is(
  (select jsonb_agg(key.value order by key.value)
   from jsonb_object_keys(public.creator_research_watchlist_status(
     jsonb_build_object(
       'organization_id', 'a8100000-0000-4000-8000-000000000001',
       'run_id', 'a8300000-0000-4000-8000-000000000001'
     )
   )) key(value)),
  '["guidance","ok","proposal","snapshots","watchlist"]'::jsonb,
  'status response has the exact top-level contract'
);
select is(
  public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001'
  )) #> '{guidance,paid_refresh_requires_confirmation}',
  'true'::jsonb,
  'status guidance always requires confirmation for paid refresh'
);
select is(
  public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001'
  )) #>> '{watchlist,freshness,status}',
  'stale',
  'baseline older than the configured interval is stale'
);
select is(
  (public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001'
  )) #>> '{watchlist,snapshot_count}')::integer,
  1,
  'status exposes total snapshot count outside the bounded array'
);

update watch_test_context
set first_system_result = public.system_propose_due_research_refreshes(
  jsonb_build_object('limit', 50)
);
select is(
  (select jsonb_agg(key.value order by key.value)
   from watch_test_context context,
     lateral jsonb_object_keys(context.first_system_result) key(value)),
  '["created","due","existing","ok","selected"]'::jsonb,
  'system proposal response has the exact counter contract'
);
select is(
  (select first_system_result
   from watch_test_context),
  '{"ok":true,"selected":1,"created":1,"existing":0,"due":1}'::jsonb,
  'first bounded due scan creates one provider-free proposal'
);
select ok(
  (select bool_and(
     jsonb_typeof(first_system_result -> counter.key) = 'number'
     and (first_system_result ->> counter.key)::integer >= 0
   )
   from watch_test_context
   cross join (values ('selected'), ('created'), ('existing'), ('due')) counter(key)),
  'all system counters are nonnegative JSON integers'
);
select is(
  (select count(*)::integer from content_factory.product_research_runs),
  (select research_run_count from watch_test_context),
  'due proposal scan never creates a research run'
);
select is(
  (select count(*)::integer
   from content_factory.research_refresh_proposals
   where status = 'open'),
  1,
  'due scan creates exactly one open proposal'
);
select is(
  (select count(*)::integer
   from content_factory.notification_outbox notification
   where notification.kind = 'research_refresh_due'
     and notification.recipient_id = 'a8000000-0000-4000-8000-000000000001'
     and notification.deep_link = '#/workspace/research?research=a8300000-0000-4000-8000-000000000001'
     and notification.properties ->> 'run_id' = 'a8300000-0000-4000-8000-000000000001'
     and notification.properties -> 'paid_refresh_requires_confirmation' = 'true'::jsonb
     and notification.properties -> 'auto_spend' = 'false'::jsonb),
  1,
  'new proposal enqueues one idempotent tenant-scoped discoverability notice'
);

update watch_test_context
set repeat_system_result = public.system_propose_due_research_refreshes(
  jsonb_build_object('limit', 50)
);
select is(
  (select repeat_system_result from watch_test_context),
  '{"ok":true,"selected":1,"created":0,"existing":1,"due":1}'::jsonb,
  'replayed due scan reports the existing proposal without duplication'
);
select is(
  (select count(*)::integer
   from content_factory.notification_outbox
   where kind = 'research_refresh_due'),
  1,
  'replayed due scan cannot duplicate its outbox notification'
);
select throws_ok(
  $$select public.system_propose_due_research_refreshes('{"limit":101}'::jsonb)$$,
  '22023', 'research_refresh_proposal_limit_invalid',
  'system scan enforces its maximum batch size'
);

select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'update', 'refresh_interval_days', 14,
    'idempotency_key', 'watch-extend-fourteen'
  ))$$,
  'owner may extend the refresh interval without a new snapshot'
);
select ok(
  (select next_refresh_at > now()
   from content_factory.research_watchlists),
  'extended interval moves next refresh into the future'
);
select is(
  (select status || ':' || superseded_reason
   from content_factory.research_refresh_proposals
   order by created_at desc, id desc limit 1),
  'superseded:configuration_changed',
  'interval extension supersedes the now-cancelled stale proposal'
);
select is(
  public.system_propose_due_research_refreshes('{"limit":50}'::jsonb)
    ->> 'selected',
  '0',
  'extended freshness deadline is no longer selected as due'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  1,
  'interval-only update reuses the immutable snapshot'
);

select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'update', 'refresh_interval_days', 3,
    'idempotency_key', 'watch-contract-three'
  ))$$,
  'owner may shorten the refresh interval explicitly'
);
select is(
  public.system_propose_due_research_refreshes('{"limit":50}'::jsonb)
    ->> 'created',
  '1',
  'shortened interval creates a new proposal for the current due fact'
);
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'pause',
    'idempotency_key', 'watch-pause-due'
  ))$$,
  'owner can pause an active watchlist'
);
select is(
  (select status from content_factory.research_watchlists),
  'paused',
  'pause changes watchlist state'
);
select is(
  (select count(*)::integer
   from content_factory.research_refresh_proposals
   where status = 'open'),
  0,
  'pause supersedes every open proposal'
);
select ok(
  exists (
    select 1 from content_factory.research_refresh_proposals
    where superseded_reason = 'watchlist_paused'
  ),
  'pause records why the proposal stopped being actionable'
);

select pg_temp.make_approved_watch_run(
  'a8100000-0000-4000-8000-000000000001',
  'a8200000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000001',
  'a8300000-0000-4000-8000-000000000002',
  'a8400000-0000-4000-8000-000000000003',
  'a8400000-0000-4000-8000-000000000004',
  'a8500000-0000-4000-8000-000000000003',
  'a8500000-0000-4000-8000-000000000004',
  'Premium evidence-led styling',
  'declining',
  now() - interval '5 days'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  1,
  'approval while paused does not mutate temporal memory automatically'
);
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000002',
    'action', 'resume', 'refresh_interval_days', 3,
    'idempotency_key', 'watch-resume-catchup'
  ))$$,
  'resume captures the explicitly selected approved catch-up snapshot'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  2,
  'resume appends one catch-up snapshot'
);
select is(
  (select change_set #> '{competitors,changed_names}'
   from content_factory.research_watchlist_snapshots
   where snapshot_version = 2),
  '["Competitor A"]'::jsonb,
  'deterministic change set detects changed competitor evidence'
);
select is(
  (select change_set #>> '{trends,contradiction_count}'
   from content_factory.research_watchlist_snapshots
   where snapshot_version = 2),
  '1',
  'growing-to-declining exact signal flip is a direction contradiction'
);
select is(
  (select change_set -> 'has_potential_contradiction'
   from content_factory.research_watchlist_snapshots
   where snapshot_version = 2),
  'true'::jsonb,
  'catch-up snapshot surfaces its potential contradiction'
);
select is(
  public.system_propose_due_research_refreshes('{"limit":50}'::jsonb)
    ->> 'created',
  '1',
  'stale catch-up snapshot produces one new proposal'
);

select pg_temp.make_approved_watch_run(
  'a8100000-0000-4000-8000-000000000001',
  'a8200000-0000-4000-8000-000000000001',
  'a8000000-0000-4000-8000-000000000001',
  'a8300000-0000-4000-8000-000000000003',
  'a8400000-0000-4000-8000-000000000005',
  'a8400000-0000-4000-8000-000000000006',
  'a8500000-0000-4000-8000-000000000005',
  'a8500000-0000-4000-8000-000000000006',
  'Practical evidence-led styling',
  'growing',
  now() - interval '1 day'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  3,
  'approval on an active watchlist appends the snapshot automatically'
);
select is(
  (select count(*)::integer
   from content_factory.research_refresh_proposals
   where status = 'open'),
  0,
  'new approved snapshot supersedes the prior due proposal'
);
select ok(
  exists (
    select 1 from content_factory.research_refresh_proposals
    where superseded_reason = 'snapshot_captured'
  ),
  'snapshot capture records proposal supersession reason'
);
select is(
  public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000003'
  )) #>> '{snapshots,0,version}',
  '3',
  'bounded status snapshots are newest-first'
);
select is(
  (public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000003'
  )) #>> '{watchlist,snapshot_count}')::integer,
  3,
  'watchlist exposes total snapshot count independently of result bound'
);
select is(
  (select count(*)::integer from content_factory.product_research_runs),
  4,
  'all system proposal calls leave only the four explicitly fixture-created runs'
);

select throws_ok(
  $$update content_factory.research_watchlist_snapshots
    set change_set = change_set
    where snapshot_version = 3$$,
  '55000', 'research_watchlist_snapshots_append_only',
  'approved snapshots reject every update'
);
select throws_ok(
  $$delete from content_factory.research_watchlist_snapshots
    where snapshot_version = 3$$,
  '55000', 'research_watchlist_snapshots_append_only',
  'approved snapshots reject deletion'
);
select throws_ok(
  $$delete from content_factory.research_watchlist_snapshot_sources
    where snapshot_id = (
      select id from content_factory.research_watchlist_snapshots
      where snapshot_version = 3
    )$$,
  '55000', 'research_watchlist_snapshot_sources_append_only',
  'exact snapshot evidence junction rejects deletion'
);

select throws_ok(
  $$select public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000004'
  ))$$,
  '22023', 'research_run_not_found',
  'a run from another tenant is hidden behind the exact tenant boundary'
);
select throws_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000002',
    'run_id', 'a8300000-0000-4000-8000-000000000004',
    'action', 'enable',
    'idempotency_key', 'watch-cross-tenant-denied'
  ))$$,
  '22023', 'research_run_not_found',
  'configure cannot cross into an organization without membership'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'a8000000-0000-4000-8000-000000000002', true
  );
end $$;
select lives_ok(
  $$select public.creator_research_watchlist_status(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000003'
  ))$$,
  'reviewer may read tenant-local watchlist status'
);
select throws_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000003',
    'action', 'pause',
    'idempotency_key', 'watch-reviewer-mutate-denied'
  ))$$,
  '42501', 'role_not_allowed',
  'reviewer cannot mutate watchlist configuration'
);

do $$ begin
  perform set_config(
    'request.jwt.claim.sub', 'a8000000-0000-4000-8000-000000000001', true
  );
end $$;
select lives_ok(
  $$select public.creator_configure_research_watchlist(jsonb_build_object(
    'organization_id', 'a8100000-0000-4000-8000-000000000001',
    'run_id', 'a8300000-0000-4000-8000-000000000001',
    'action', 'update', 'refresh_interval_days', 14,
    'idempotency_key', 'watch-old-tab-latest-product'
  ))$$,
  'update from an old run locator still uses the latest product approval'
);
select is(
  (select run_id
   from content_factory.research_watchlist_snapshots
   order by snapshot_version desc limit 1),
  'a8300000-0000-4000-8000-000000000003'::uuid,
  'old locator never regresses memory behind the latest approved product run'
);
select is(
  (select count(*)::integer from content_factory.research_watchlist_snapshots),
  3,
  'old-tab interval update reuses latest snapshot instead of duplicating it'
);

select is(
  content_factory_private.research_trend_change_set(
    jsonb_build_object(
      'as_of', '2026-07-01',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal', 'Comparison format', 'direction', 'growing'
      ))
    ),
    jsonb_build_object(
      'signal_catalog_version', 'structural_v1',
      'as_of', '2026-08-01',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal_key', 'format.comparison',
        'signal', 'Comparison described in new words',
        'direction', 'growing'
      ))
    )
  ) ->> 'comparison_mode',
  'canonical_reset',
  'first canonical trend snapshot starts a new comparison baseline'
);
select is(
  jsonb_array_length(
    content_factory_private.research_trend_change_set(
      jsonb_build_object(
        'as_of', '2026-07-01',
        'signals', jsonb_build_array(jsonb_build_object(
          'signal', 'Comparison format', 'direction', 'growing'
        ))
      ),
      jsonb_build_object(
        'signal_catalog_version', 'structural_v1',
        'as_of', '2026-08-01',
        'signals', jsonb_build_array(jsonb_build_object(
          'signal_key', 'format.comparison',
          'signal', 'Comparison described in new words',
          'direction', 'growing'
        ))
      )
    ) -> 'added_signals'
  ),
  0,
  'legacy-to-canonical reset never invents an added trend'
);
select is(
  content_factory_private.research_trend_change_set(
    jsonb_build_object(
      'signal_catalog_version', 'structural_v1',
      'as_of', '2026-07-01',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal_key', 'format.comparison',
        'signal', 'Old wording', 'direction', 'growing'
      ))
    ),
    jsonb_build_object(
      'signal_catalog_version', 'structural_v1',
      'as_of', '2026-08-01',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal_key', 'format.comparison',
        'signal', 'New wording', 'direction', 'declining'
      ))
    )
  ) ->> 'contradiction_count',
  '1',
  'canonical trend identity detects a growing-to-declining contradiction'
);

select * from finish();
rollback;
