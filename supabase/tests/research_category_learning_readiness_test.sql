begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_table(
  'content_factory', 'research_category_source_ledger',
  'durable category source lineage ledger exists'
);
select has_table(
  'content_factory', 'research_source_analysis_events',
  'append-only source analysis history exists'
);
select has_table(
  'content_factory', 'research_category_readiness_snapshots',
  'explicit readiness snapshot history exists'
);
select has_table(
  'content_factory', 'research_source_collection_policies',
  'provider-neutral collection policy history exists'
);
select has_table(
  'content_factory', 'research_source_collection_intents',
  'fail-closed collection intent history exists'
);

select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_category_source_ledger'::regclass),
     ('content_factory.research_source_analysis_events'::regclass),
     ('content_factory.research_category_readiness_snapshots'::regclass),
     ('content_factory.research_source_collection_policies'::regclass),
     ('content_factory.research_source_collection_intents'::regclass)
   ) protected(table_oid)
   join pg_class relation on relation.oid = protected.table_oid
   where relation.relrowsecurity),
  5,
  'all category-learning ledgers have RLS enabled'
);
select is(
  (select count(*)::integer
   from (values
     ('content_factory.research_category_source_ledger'::regclass),
     ('content_factory.research_source_analysis_events'::regclass),
     ('content_factory.research_category_readiness_snapshots'::regclass),
     ('content_factory.research_source_collection_policies'::regclass),
     ('content_factory.research_source_collection_intents'::regclass)
   ) protected(table_oid)
   cross join (values ('anon'), ('authenticated')) grantee(role_name)
   cross join (values ('select'), ('insert'), ('update'), ('delete')) privilege(name)
   where has_table_privilege(
     grantee.role_name, protected.table_oid, privilege.name
   )),
  0,
  'browser roles have no direct category-learning ledger privileges'
);
select is(
  (select count(*)::integer
   from pg_trigger trigger_entry
   where trigger_entry.tgrelid in (
     'content_factory.research_category_source_ledger'::regclass,
     'content_factory.research_source_analysis_events'::regclass,
     'content_factory.research_category_readiness_snapshots'::regclass,
     'content_factory.research_source_collection_policies'::regclass,
     'content_factory.research_source_collection_intents'::regclass
   )
     and not trigger_entry.tgisinternal
     and trigger_entry.tgname like 'reject_research_%_mutation'),
  5,
  'every category-learning ledger rejects update and delete'
);

select has_function(
  'public', 'creator_research_category_learning_status', array['jsonb'],
  'read-only category-learning status RPC exists'
);
select has_function(
  'public', 'creator_capture_research_category_readiness', array['jsonb'],
  'explicit readiness capture RPC exists'
);
select has_function(
  'public', 'creator_correct_research_source_analysis', array['jsonb'],
  'human source analysis correction RPC exists'
);
select has_function(
  'public', 'creator_configure_research_source_collection_policy', array['jsonb'],
  'append-only collection policy RPC exists'
);
select has_function(
  'public', 'system_record_research_source_analysis', array['jsonb'],
  'service-only structured parser result RPC exists'
);
select has_function(
  'public', 'system_register_research_category_sources', array['jsonb'],
  'service-only durable source registration RPC exists'
);
select has_function(
  'public', 'system_claim_due_research_youtube_collection', array['jsonb'],
  'bulk automatic YouTube claim RPC exists'
);
select has_function(
  'public', 'system_read_automatic_research_youtube_ingestion', array['jsonb'],
  'automatic claimed-ingestion reader exists'
);
select has_function(
  'public', 'system_begin_automatic_research_youtube_transport', array['jsonb'],
  'automatic transport gate wrapper exists'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_research_category_learning_status(jsonb)', 'execute'
  )
  and has_function_privilege(
    'authenticated',
    'public.creator_correct_research_source_analysis(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_research_category_learning_status(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_correct_research_source_analysis(jsonb)', 'execute'
  ),
  'creator status and corrections are authenticated-only boundaries'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_record_research_source_analysis(jsonb)', 'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_register_research_category_sources(jsonb)', 'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.system_claim_due_research_youtube_collection(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_record_research_source_analysis(jsonb)', 'execute'
  ),
  'parser, registration and automatic dispatch RPCs are service-only'
);

select ok(
  not content_factory_private.research_source_analysis_is_valid('{}'::jsonb)
  and not content_factory_private.research_source_analysis_is_valid(
    jsonb_build_object('summary', 'arbitrary legacy payload')
  )
  and not content_factory_private.research_source_analysis_is_valid(
    jsonb_build_object(
      'schema_version', 'research-source-interpretation-v1',
      'classification', 'competitor',
      'relevance_score', 90,
      'confidence', 'high',
      'summary', 'This otherwise valid object contains a forbidden raw field.',
      'structural_signal_keys', '[]'::jsonb,
      'limitations', '[]'::jsonb,
      'raw_transcript', 'forbidden'
    )
  ),
  'empty, arbitrary and raw-text analysis payloads fail closed'
);
select ok(
  content_factory_private.research_source_analysis_is_valid(
    jsonb_build_object(
      'schema_version', 'research-source-interpretation-v1',
      'classification', 'trend_signal',
      'relevance_score', 70,
      'confidence', 'medium',
      'summary', 'Validated structural evidence supports one bounded trend role.',
      'structural_signal_keys', jsonb_build_array('format.comparison'),
      'limitations', jsonb_build_array('Only persisted citations were used.')
    )
  ),
  'the exact strict interpretation schema is accepted'
);
select ok(
  content_factory_private.research_analysis_has_forbidden_keys(
    jsonb_build_object(
      'summary', 'bounded analysis',
      'nested', jsonb_build_array(jsonb_build_object('transcript', 'forbidden'))
    )
  )
  and not content_factory_private.research_analysis_has_forbidden_keys(
    jsonb_build_object('summary', 'bounded synthetic analysis')
  ),
  'raw caption and transcript keys are rejected recursively'
);

select is(
  content_factory_private.research_source_identity_key(
    'https://www.youtube.com/watch?v=AAAAAAAAAAA', repeat('a', 64)
  ) = content_factory_private.research_source_identity_key(
    'https://www.youtube.com/watch?v=AAAAAAAAAAA#fragment', repeat('b', 64)
  ),
  true,
  'the same exact URL keeps one identity across fragments and content versions'
);
select isnt(
  content_factory_private.research_source_identity_key(
    'https://www.youtube.com/watch?v=AAAAAAAAAAA', repeat('a', 64)
  ),
  content_factory_private.research_source_identity_key(
    'https://www.youtube.com/watch?v=BBBBBBBBBBB', repeat('a', 64)
  ),
  'distinct YouTube query IDs never collapse to one source identity'
);

select is(
  content_factory_private.research_readiness_dimension(
    'source_volume', 'Current reviewable source volume', 20, 6, 12,
    'collect_more_reviewable_sources'
  ) ->> 'score',
  '50',
  'dimension score is deterministic evidence coverage, not model opinion'
);
select is(
  content_factory_private.research_readiness_dimension(
    'source_volume', 'Current reviewable source volume', 20, 4, 12,
    'collect_more_reviewable_sources'
  ) ->> 'missing',
  '8',
  'missing evidence remains explicit for hover guidance'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), '''category_evidence_readiness_not_model_iq''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), '''retained_youtube_evidence''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), '''lineage_history_limit_per_source'', 10') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), '''analysis_history_limit_per_source'', 10') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), '''item_limit'', 50') > 0,
  'status exposes honest metric, bounded lineage and retained YouTube evidence'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), 'insert into') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), 'update ') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), 'delete from') = 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_research_category_learning_status(jsonb)'::regprocedure
  )), 'current_profile_id') = 0,
  'status is truly read-only and never creates profile state or snapshots'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_capture_research_category_readiness(jsonb)'::regprocedure
  )), 'before_value :=') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_capture_research_category_readiness(jsonb)'::regprocedure
  )), 'research_category_evidence_changed') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_capture_research_category_readiness(jsonb)'::regprocedure
  )), 'insert into content_factory.research_category_source_ledger') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_capture_research_category_readiness(jsonb)'::regprocedure
  )), 'insert into content_factory.research_category_readiness_snapshots') > 0
  and length(regexp_replace(lower(pg_get_functiondef(
    'public.creator_capture_research_category_readiness(jsonb)'::regprocedure
  )), '[^a-z_]', '', 'g')) > 0,
  'capture checks the pre-registration hash, registers, recomputes and snapshots'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), 'limit 24') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), 'research_structural_trend_signal_types') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), 'source_row.title') = 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), '''source.type.''') = 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), 'when competitor_cited_value then ''competitor''') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.bootstrap_persisted_research_source_analyses(uuid,uuid)'::regprocedure
  )), 'if exists') > 0,
  'fallback parser is bounded, anti-copy, allowlisted and protects every head'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_complete_product_research(jsonb)'::regprocedure
  )), 'complete_product_research_v2_base') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_complete_product_research(jsonb)'::regprocedure
  )), 'system_register_research_category_sources') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_resolve_research_market_category(jsonb)'::regprocedure
  )), 'resolve_research_market_category_v1_base') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_resolve_research_market_category(jsonb)'::regprocedure
  )), 'system_register_research_category_sources') > 0,
  'completion and category resolution preserve responses and atomically register'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_configure_research_source_collection_policy(jsonb)'::regprocedure
  )), 'array[''owner'', ''admin'']') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_configure_research_source_collection_policy(jsonb)'::regprocedure
  )), 'automatic_collection_ack') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_configure_research_source_collection_policy(jsonb)'::regprocedure
  )), 'research_instagram_provider_legal_choice_required') > 0,
  'only owners/admins can acknowledge automatic collection and Instagram fails closed'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_source_collection(jsonb)'::regprocedure
  )), 'scheduled_for_value - interval ''90 days''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_source_collection(jsonb)'::regprocedure
  )), 'monthly_hard_budget_exhausted') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_source_collection(jsonb)'::regprocedure
  )), 'pg_advisory_xact_lock') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_propose_due_research_source_collection(jsonb)'::regprocedure
  )), '''external_call_started'', false') > 0,
  'scheduler reserves deterministic bounded work under a monthly lock without HTTP'
);
select ok(
  strpos(lower(pg_get_functiondef(
    'public.system_claim_due_research_youtube_collection(jsonb)'::regprocedure
  )), 'for update of ingestion skip locked') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_claim_due_research_youtube_collection(jsonb)'::regprocedure
  )), 'ingestion.mode = ''category_refresh''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_claim_due_research_youtube_collection(jsonb)'::regprocedure
  )), '''automatic_retry_started'', false') > 0
  and strpos(lower(pg_get_functiondef(
    'public.system_begin_automatic_research_youtube_transport(jsonb)'::regprocedure
  )), 'research_automatic_youtube_dispatch_allowed') > 0,
  'bulk claim recovers queued automatic work, excludes canaries and rechecks policy'
);

-- Runtime lifecycle fixture: 30 sources are durably registered after the first
-- category confirmation, but the deterministic parser intentionally creates at
-- most 24 editable heads.  Unique provider-authored strings make leakage tests
-- exact rather than heuristic.
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'c0100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'category-readiness-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Category Readiness Owner"}'::jsonb, now(), now()
);
do $$
begin
  perform set_config(
    'request.jwt.claim.sub',
    'c0100000-0000-4000-8000-000000000001', true
  );
  perform set_config('request.jwt.claim.role', 'authenticated', true);
end;
$$;
insert into content_factory.organizations (id, name, slug, status)
values (
  'c0100000-0000-4000-8000-000000000002',
  'Category Readiness Runtime', 'category-readiness-runtime', 'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000001', 'owner', 'active'
);
insert into content_factory.products (
  id, organization_id, sku, title, status, metadata, created_by
) values (
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000002',
  'CATEGORY-READINESS-RUNTIME', 'Category Readiness Runtime Product',
  'active', '{}'::jsonb,
  'c0100000-0000-4000-8000-000000000001'
);
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
) values (
  'c0100000-0000-4000-8000-000000000004',
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  'completed', '{}'::jsonb,
  jsonb_build_object(
    'category_analysis', jsonb_build_object(
      'category_name', 'Runtime evidence category',
      'definition', 'A bounded runtime category for evidence lifecycle tests.',
      'maturity', 'growing',
      'source_ids', jsonb_build_array('web:s7')
    ),
    'competitor_analysis', jsonb_build_object(
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'PROVIDER_PROSE_NEVER_COPY',
        'source_ids', jsonb_build_array('web:s1')
      )),
      'saturated_patterns', '[]'::jsonb,
      'content_gaps', '[]'::jsonb
    ),
    'trend_analysis', jsonb_build_object(
      'signals', jsonb_build_array(jsonb_build_object(
        'signal_key', 'format.comparison',
        'signal', 'PROVIDER_TREND_PROSE_NEVER_COPY',
        'source_ids', jsonb_build_array('web:s1', 'web:s2')
      ))
    ),
    'facts', jsonb_build_array(jsonb_build_object(
      'statement', 'PROVIDER_FACT_NEVER_COPY',
      'source_ids', jsonb_build_array('web:s3', 'web:s6')
    ))
  ),
  repeat('a', 64), repeat('b', 64),
  'category-readiness-runtime-run', now()
);
insert into content_factory.product_research_sources (
  organization_id, run_id, product_id, created_by, source_type, source_url,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at,
  created_at
)
select
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000004',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  case source_number
    when 1 then 'market_data'
    when 2 then 'social_video'
    when 3 then 'social_video'
    when 4 then 'market_data'
    when 5 then 'social_video'
    else 'other'
  end,
  'https://example.test/category-source/' || source_number,
  'DO_NOT_COPY_UNIQUE_TITLE_' || source_number,
  content_factory_private.json_hash(jsonb_build_object(
    'runtime_source', source_number
  )),
  'public',
  jsonb_build_array('DO_NOT_COPY_EXTRACTED_FACT_' || source_number),
  jsonb_build_object(
    'model_source_id', 'web:s' || source_number,
    'classification', 'competitor',
    'original_source_type', case source_number
      when 3 then 'social'
      when 4 then 'editorial'
      when 5 then 'social'
      when 6 then 'official'
      else 'other'
    end
  ),
  now(),
  '2026-08-03 00:00:00+00'::timestamptz
    + source_number * interval '1 second'
from generate_series(1, 30) source_number;
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash
)
select
  'c0100000-0000-4000-8000-000000000005',
  run.organization_id, run.id, run.product_id, run.created_by,
  'ai', 1, 'draft', 'Runtime category evidence draft', run.summary,
  (select jsonb_agg(source.id order by source.created_at, source.id)
   from content_factory.product_research_sources source
   where source.organization_id = run.organization_id
     and source.run_id = run.id),
  jsonb_build_array(jsonb_build_object(
    'title', 'Verify runtime lifecycle',
    'instructions', 'Exercise bounded persisted-result parsing.'
  )),
  content_factory_private.json_hash(jsonb_build_object(
    'runtime_draft', run.id
  ))
from content_factory.product_research_runs run
where run.id = 'c0100000-0000-4000-8000-000000000004';

select lives_ok(
  $runtime_resolve$
    select public.creator_resolve_research_market_category(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'run_id', 'c0100000-0000-4000-8000-000000000004',
        'action', 'create_and_bind',
        'candidate_hash', (
          content_factory_private.research_market_category_candidate(
            'c0100000-0000-4000-8000-000000000002',
            'c0100000-0000-4000-8000-000000000004'
          ) ->> 'candidate_hash'
        ),
        'canonical_name', 'Runtime evidence category',
        'definition', 'A bounded runtime category for evidence lifecycle tests.',
        'aliases', '[]'::jsonb,
        'confirmation', true,
        'reason', 'Confirm the bounded runtime lifecycle',
        'idempotency_key', 'category-readiness-runtime-bind'
      )
    )
  $runtime_resolve$,
  'first category confirmation atomically registers and bootstraps sources'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'),
  30,
  'all thirty persisted sources are durably registered'
);
select is(
  (select count(*)::integer
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'),
  24,
  'fallback parsing is deterministically capped at twenty-four sources'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'
     and not exists (
       select 1
       from content_factory.research_source_analysis_events event
       where event.source_ledger_id = ledger.id
     )),
  6,
  'sources beyond the parser bound remain explicit analysis gaps'
);

select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s1'),
  'competitor',
  'competitor citation takes precedence over a simultaneous trend role'
);
select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s2'),
  'trend_signal',
  'an exact trend citation produces the trend-signal role'
);
select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s3'),
  'adjacent',
  'a social source cited only elsewhere remains adjacent'
);
select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s4'),
  'unknown',
  'uncited market data never manufactures a trend or competitor role'
);
select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s5'),
  'unknown',
  'uncited social video remains unknown despite arbitrary legacy metadata'
);
select is(
  (select event.analysis ->> 'classification'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s6'),
  'reference',
  'an official source cited only elsewhere is still a conservative reference'
);
select is(
  (select event.analysis -> 'structural_signal_keys'
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s2'),
  jsonb_build_array('format.comparison'),
  'only the exact active trend-catalog key is retained'
);
select is(
  (select count(*)::integer
   from content_factory.research_source_analysis_events event
   where event.analysis::text ~ 'DO_NOT_COPY|PROVIDER_'
      or event.analysis::text ~ 'source[.](type|platform|trust)[.]'),
  0,
  'no provider title, fact, prose or invented source signal is copied'
);

select lives_ok(
  $runtime_replay$
    select public.creator_resolve_research_market_category(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'run_id', 'c0100000-0000-4000-8000-000000000004',
        'action', 'create_and_bind',
        'candidate_hash', (
          content_factory_private.research_market_category_candidate(
            'c0100000-0000-4000-8000-000000000002',
            'c0100000-0000-4000-8000-000000000004'
          ) ->> 'candidate_hash'
        ),
        'canonical_name', 'Runtime evidence category',
        'definition', 'A bounded runtime category for evidence lifecycle tests.',
        'aliases', '[]'::jsonb,
        'confirmation', true,
        'reason', 'Confirm the bounded runtime lifecycle',
        'idempotency_key', 'category-readiness-runtime-bind'
      )
    )
  $runtime_replay$,
  'lost-response replay re-enters registration safely'
);
select is(
  (select count(*)::integer
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'),
  24,
  'resolution replay creates no duplicate parser heads'
);

-- A human correction becomes the immutable head and every later bootstrap
-- replay must leave it untouched.
select lives_ok(
  $human_correction$
    select public.creator_correct_research_source_analysis(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'source_ledger_id', head.source_ledger_id,
        'expected_head_event_id', head.id,
        'expected_head_hash', head.event_hash,
        'analysis', jsonb_build_object(
          'schema_version', 'research-source-interpretation-v1',
          'classification', 'irrelevant',
          'relevance_score', 0,
          'confidence', 'high',
          'summary', 'Human review marked this persisted source irrelevant to the category.',
          'structural_signal_keys', '[]'::jsonb,
          'limitations', jsonb_build_array('Human decision supersedes fallback parsing.')
        ),
        'correction_reason', 'Runtime correction verifies current-evidence exclusion.',
        'idempotency_key', 'category-readiness-human-correction'
      )
    )
    from (
      select event.id, event.event_hash, event.source_ledger_id
      from content_factory.research_source_analysis_events event
      join content_factory.research_category_source_ledger ledger
        on ledger.id = event.source_ledger_id
      join content_factory.product_research_sources source
        on source.id = ledger.source_id
      where source.metadata ->> 'model_source_id' = 'web:s5'
      order by event.analysis_version desc
      limit 1
    ) head
  $human_correction$,
  'a creator can append an exact-head irrelevant correction'
);
select is(
  (select (dimension.value ->> 'current')::integer
   from jsonb_array_elements(
     content_factory_private.research_category_evidence_readiness(
       'c0100000-0000-4000-8000-000000000002',
       (select binding.category_id
        from content_factory.research_product_market_category_bindings binding
        where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
        order by binding.binding_version desc limit 1),
       clock_timestamp()
     ) -> 'dimensions'
   ) dimension(value)
   where dimension.value ->> 'key' = 'source_volume'),
  29,
  'an irrelevant current correction removes the source from readiness evidence'
);
select lives_ok(
  $register_replay$
    select public.system_register_research_category_sources(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'run_id', 'c0100000-0000-4000-8000-000000000004'
      )
    )
  $register_replay$,
  'service registration replay is idempotent after a human correction'
);
select is(
  (select event.origin || ':' || event.analysis_version::text
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s5'
   order by event.analysis_version desc limit 1),
  'human_correction:2',
  'fallback replay never overwrites or appends after a human head'
);

-- A second content version at the same exact URL is retained for lineage but
-- replaces, rather than inflates, current source-volume evidence.
insert into content_factory.product_research_sources (
  organization_id, run_id, product_id, created_by, source_type, source_url,
  title, content_hash, trust_level, extracted_facts, metadata, fetched_at,
  created_at
) values (
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000004',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  'social_video', 'https://example.test/category-source/5',
  'DO_NOT_COPY_NEW_CONTENT_VERSION',
  content_factory_private.json_hash(jsonb_build_object(
    'runtime_source', 5, 'version', 2
  )),
  'public', '[]'::jsonb,
  jsonb_build_object('model_source_id', 'web:s31'),
  now(), '2026-08-03 01:00:00+00'
);
select lives_ok(
  $register_version$
    select public.system_register_research_category_sources(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'run_id', 'c0100000-0000-4000-8000-000000000004'
      )
    )
  $register_version$,
  'a changed content version at the same URL is retained safely'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'),
  31,
  'lineage retains both exact-URL content versions'
);
select is(
  (select count(distinct ledger.source_identity_key)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000004'),
  30,
  'same-URL content versions do not inflate current source identity volume'
);

-- Current retention-bound YouTube metadata affects readiness without ever
-- being copied into the durable source ledger.  Three videos from one channel
-- contribute one competitor observation.
insert into content_factory.research_youtube_ingestion_runs (
  id, organization_id, run_id, product_id, binding_id, market_category_id,
  requested_by, mode, status, provider_key, adapter_version, query_text,
  query_hash, published_after, max_results, max_http_requests,
  max_quota_units, request_hash, idempotency_key, terms_version, no_retry
)
select
  'c0100000-0000-4000-8000-000000000010',
  binding.organization_id, binding.source_run_id, binding.product_id,
  binding.id, binding.category_id,
  'c0100000-0000-4000-8000-000000000001',
  'category_refresh', 'queued', 'youtube_data_api_v3',
  'youtube-data-api-v3-public-metadata-v1', 'runtime category evidence',
  repeat('c', 64), now() - interval '90 days', 4, 2, 2,
  repeat('d', 64), 'category-readiness-youtube-runtime',
  'youtube-developer-policies-2026-08-03-v1', true
from content_factory.research_product_market_category_bindings binding
where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
order by binding.binding_version desc limit 1;
insert into content_factory.research_youtube_video_observations (
  id, organization_id, ingestion_id, product_id, binding_id,
  market_category_id, search_position, video_id, channel_id, title,
  channel_title, youtube_category_id, published_at, duration_iso8601,
  privacy_status, embeddable, observed_at, retention_expires_at,
  observation_hash
)
select
  ('c0100000-0000-4000-8000-' || lpad(video_number::text, 12, '0'))::uuid,
  ingestion.organization_id, ingestion.id, ingestion.product_id,
  ingestion.binding_id, ingestion.market_category_id, video_number,
  case video_number
    when 1 then 'AAAAAAA0001'
    when 2 then 'AAAAAAA0002'
    else 'AAAAAAA0003'
  end,
  'UCAAAAAAAAAAAAAAAAAAAAAA',
  'Retention-bound runtime title ' || video_number,
  'Runtime channel', '22', now() - video_number * interval '1 day',
  'PT30S', 'public', true, now(), now() + interval '29 days',
  content_factory_private.json_hash(jsonb_build_object(
    'youtube_runtime_video', video_number
  ))
from content_factory.research_youtube_ingestion_runs ingestion
cross join generate_series(1, 3) video_number
where ingestion.id = 'c0100000-0000-4000-8000-000000000010';

create temporary table readiness_same_channel on commit drop as
select content_factory_private.research_category_evidence_readiness(
  'c0100000-0000-4000-8000-000000000002',
  (select binding.category_id
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
   order by binding.binding_version desc limit 1),
  clock_timestamp()
) value;
select is(
  (select (dimension.value ->> 'current')::integer
   from readiness_same_channel snapshot,
        jsonb_array_elements(snapshot.value -> 'dimensions') dimension(value)
   where dimension.value ->> 'key' = 'competitor_observations'),
  2,
  'many retained videos from one channel count once beside one durable competitor'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.source_url like 'https://www.youtube.com/watch?v=%'),
  0,
  'retention-bound YouTube observations are never copied to durable lineage'
);

-- A fourth video uses a second channel so excluding that one candidate changes
-- the unique-channel component even though the first three remain eligible.
insert into content_factory.research_youtube_video_observations (
  id, organization_id, ingestion_id, product_id, binding_id,
  market_category_id, search_position, video_id, channel_id, title,
  channel_title, youtube_category_id, published_at, duration_iso8601,
  privacy_status, embeddable, observed_at, retention_expires_at,
  observation_hash
)
select
  'c0100000-0000-4000-8000-000000000004',
  ingestion.organization_id, ingestion.id, ingestion.product_id,
  ingestion.binding_id, ingestion.market_category_id, 4,
  'AAAAAAA0004', 'UCBBBBBBBBBBBBBBBBBBBBBB',
  'Retention-bound second-channel title', 'Second runtime channel',
  '22', now() - interval '1 day', 'PT30S', 'public', true,
  now(), now() + interval '29 days',
  content_factory_private.json_hash(jsonb_build_object(
    'youtube_runtime_video', 4
  ))
from content_factory.research_youtube_ingestion_runs ingestion
where ingestion.id = 'c0100000-0000-4000-8000-000000000010';

create temporary table readiness_before_exclusion on commit drop as
select content_factory_private.research_category_evidence_readiness(
  'c0100000-0000-4000-8000-000000000002',
  (select binding.category_id
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
   order by binding.binding_version desc limit 1),
  clock_timestamp()
) value;
insert into content_factory.research_youtube_candidate_decisions (
  organization_id, ingestion_id, observation_id, observation_hash, decision,
  reason, decided_by, retention_expires_at, idempotency_key, decision_hash
)
select observation.organization_id, observation.ingestion_id, observation.id,
  observation.observation_hash, 'exclude_candidate',
  'Exclude one runtime candidate',
  'c0100000-0000-4000-8000-000000000001',
  now() + interval '29 days', 'category-readiness-exclude-video-4',
  content_factory_private.json_hash(jsonb_build_object(
    'youtube_runtime_exclusion', observation.id
  ))
from content_factory.research_youtube_video_observations observation
where observation.video_id = 'AAAAAAA0004';
select ok(
  (select (readiness.value ->> 'score')::integer
   from (select content_factory_private.research_category_evidence_readiness(
     'c0100000-0000-4000-8000-000000000002',
     (select binding.category_id
      from content_factory.research_product_market_category_bindings binding
      where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc limit 1),
     clock_timestamp()
   ) value) readiness)
  < (select (value ->> 'score')::integer from readiness_before_exclusion),
  'excluding a current candidate lowers the evidence-readiness score'
);
select ok(
  (select value ->> 'evidence_hash'
   from readiness_before_exclusion)
  = (select content_factory_private.research_category_evidence_readiness(
      'c0100000-0000-4000-8000-000000000002',
      (select binding.category_id
       from content_factory.research_product_market_category_bindings binding
       where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
       order by binding.binding_version desc limit 1),
      value_as_of.timestamp_value
    ) ->> 'evidence_hash'
    from (select (value ->> 'as_of')::timestamptz timestamp_value
          from readiness_before_exclusion) value_as_of),
  'the same evidence at the exact same as-of timestamp has a stable hash'
);
select ok(
  (select (expired.value ->> 'score')::integer
   from (select content_factory_private.research_category_evidence_readiness(
     'c0100000-0000-4000-8000-000000000002',
     (select binding.category_id
      from content_factory.research_product_market_category_bindings binding
      where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc limit 1),
     clock_timestamp() + interval '30 days'
   ) value) expired)
  < (select (value ->> 'score')::integer from readiness_before_exclusion),
  'readiness drops after retention expiry when current YouTube evidence is gone'
);

-- Existing-category completion is the other lifecycle entry.  The wrapper
-- must return the legacy completion response unchanged while registering and
-- bootstrapping in the same transaction; a lost-response replay must not add
-- another ledger version or parser event.
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, idempotency_key, started_at, lease_expires_at
) values (
  'c0100000-0000-4000-8000-000000000020',
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  'processing', '{}'::jsonb, '{}'::jsonb, repeat('e', 64),
  'category-readiness-existing-completion', now(), now() + interval '15 minutes'
);
create temporary table existing_completion_payload on commit drop as
select jsonb_build_object(
  'run_id', 'c0100000-0000-4000-8000-000000000020',
  'status', 'completed',
  'summary', jsonb_build_object(
    'category_analysis', jsonb_build_object(
      'category_name', 'Runtime evidence category',
      'definition', 'A bounded runtime category for evidence lifecycle tests.',
      'maturity', 'growing',
      'source_ids', jsonb_build_array('web:completion')
    ),
    'competitor_analysis', jsonb_build_object(
      'competitors', '[]'::jsonb,
      'saturated_patterns', '[]'::jsonb,
      'content_gaps', '[]'::jsonb
    ),
    'trend_analysis', jsonb_build_object('signals', '[]'::jsonb)
  ),
  'sources', jsonb_build_array(jsonb_build_object(
    'source_type', 'market_data',
    'source_url', 'https://example.test/existing-completion-source',
    'title', 'DO_NOT_COPY_EXISTING_COMPLETION_TITLE',
    'content_hash', repeat('f', 64),
    'trust_level', 'public',
    'extracted_facts', jsonb_build_array(
      'DO_NOT_COPY_EXISTING_COMPLETION_FACT'
    ),
    'metadata', jsonb_build_object(
      'model_source_id', 'web:completion',
      'original_source_type', 'official',
      'provider_citation_verified', true
    )
  )),
  'draft', jsonb_build_object(
    'title', 'Existing category completion draft',
    'brief', jsonb_build_object(
      'category_analysis', jsonb_build_object(
        'category_name', 'Runtime evidence category',
        'definition', 'A bounded runtime category for evidence lifecycle tests.',
        'maturity', 'growing',
        'source_ids', jsonb_build_array('web:completion')
      ),
      'competitor_analysis', jsonb_build_object(
        'competitors', '[]'::jsonb,
        'saturated_patterns', '[]'::jsonb,
        'content_gaps', '[]'::jsonb
      ),
      'trend_analysis', jsonb_build_object('signals', '[]'::jsonb)
    ),
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Verify existing category completion',
      'instructions', 'Exercise atomic completion registration and replay.'
    ))
  )
) value;
create temporary table existing_completion_first on commit drop as
select public.system_complete_product_research(payload.value) value
from existing_completion_payload payload;
create temporary table existing_completion_replay on commit drop as
select public.system_complete_product_research(payload.value) value
from existing_completion_payload payload;
select is(
  (select value from existing_completion_replay),
  (select value from existing_completion_first),
  'lost-response completion replay returns the exact same legacy response'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000020'),
  1,
  'existing-category completion registers exactly one durable source version'
);
select is(
  (select count(*)::integer
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000020'),
  1,
  'existing-category completion replay creates one parser head only'
);
select is(
  (select count(*)::integer
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   where ledger.run_id = 'c0100000-0000-4000-8000-000000000020'
     and event.analysis::text ~ 'DO_NOT_COPY_EXISTING_COMPLETION'),
  0,
  'completion-time parsing also stores no provider title or fact prose'
);

select * from finish();
rollback;
