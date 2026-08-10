begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    'Show instagram.com/raw, youtu.be/abc, instagram.com), and youtu.be.'
  ),
  'bare social and video domains never cross the provider boundary'
);
select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    'youtu.be'
  ),
  'a bare YouTube short domain is rejected in isolation'
);
select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    'youtu.be.'
  ),
  'a punctuated bare YouTube short domain is rejected in isolation'
);
select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    'competitor.de'
  ),
  'a bare two-letter country-code domain is rejected in isolation'
);
select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    'Fetch ftp://source.example/path'
  ),
  'non-http URI schemes never cross the provider boundary'
);
select ok(
  content_factory_private.generation_spec_prompt_has_external_reference(
    U&'Sources: \043F\0440\0438\043C\0435\0440.\0440\0444/path example.xn--p1ai/path 192.168.0.1/path data:text/plain,secret'
  ),
  'IDN, punycode, IP paths and non-slash URI schemes stay in the ledger'
);
select ok(
  not content_factory_private.generation_spec_prompt_has_external_reference(
    'Exact products: Dr.Jart+ Cicapair, Dr.Ceuracle and Gen4.Turbo.'
  ),
  'dotted product and model names are not mistaken for URLs'
);

select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object('scenarios', jsonb_build_array(jsonb_build_object(
      'hook', 'anywhy', 'shot_list', '[]'::jsonb
    ))),
    1
  ) -> 'hook_patterns',
  '["concise"]'::jsonb,
  'embedded why text is not misclassified as a research hook'
);
select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object('scenarios', jsonb_build_array(jsonb_build_object(
      'hook', 'vsready', 'shot_list', '[]'::jsonb
    ))),
    1
  ) -> 'hook_patterns',
  '["comparison", "concise"]'::jsonb,
  'the SQL compiler shares the browser start-boundary comparison rule'
);
select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object('scenarios', jsonb_build_array(jsonb_build_object(
      'hook', '', 'shot_list', jsonb_build_array('before', 'buying')
    ))),
    1
  ) -> 'hook_patterns',
  '["before_buying"]'::jsonb,
  'array shot lines are normalized exactly like the browser handoff'
);
select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object('scenarios', jsonb_build_array(jsonb_build_object(
      'hook', '',
      'shot_list', jsonb_build_array(jsonb_build_object(
        'seconds', '0-2',
        'visual', E'before\nbuying',
        'voiceover', 'neutral',
        'on_screen_text', 'без текста'
      ))
    ))),
    1
  ) -> 'hook_patterns',
  '["before_buying", "numbered"]'::jsonb,
  'object shot fields are reconstructed before whitespace normalization'
);
select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object('scenarios', jsonb_build_array(jsonb_build_object(
      'hook', repeat('a', 71) || '😀', 'shot_list', '[]'::jsonb
    ))),
    1
  ) -> 'hook_patterns',
  '["concise"]'::jsonb,
  'the 72-code-point hook boundary matches JavaScript Unicode semantics'
);
select is(
  content_factory_private.generation_spec_research_structure(
    jsonb_build_object(
      'category_analysis', jsonb_build_object('maturity', 'growing'),
      'competitor_analysis', jsonb_build_object('coverage', 'sufficient'),
      'trend_analysis', jsonb_build_object(
        'signal_catalog_version', 'structural_v1',
        'signals', jsonb_build_array(jsonb_build_object(
          'signal_key', 'format.comparison',
          'direction', 'growing',
          'confidence', 'medium',
          'recommended_use', 'test'
        ))
      ),
      'scenarios', jsonb_build_array(jsonb_build_object(
        'hook', 'Compare options', 'shot_list', '[]'::jsonb
      ))
    ),
    1
  ) - array['creative_angle', 'hook_patterns', 'compiler_version']::text[],
  jsonb_build_object(
    'category_maturity', 'growing',
    'competitor_coverage', 'sufficient',
    'primary_signal', 'format.comparison'
  ),
  'the category rule consumes only bounded approved category research enums'
);
select is(
  content_factory_private.generation_spec_prompt_has_exact_category_rule(
    'Safe line' || E'\n'
      || 'ResearchCategoryRule/v2 category_maturity=growing '
      || 'competitor_coverage=sufficient primary_signal=format.comparison '
      || 'creative_angle=comparison primary_hook=question_led.' || E'\n'
      || 'ResearchCategoryRule/v2 category_maturity=saturated '
      || 'competitor_coverage=limited primary_signal=proof.product_in_use '
      || 'creative_angle=trust_builder primary_hook=concise.',
    'ResearchCategoryRule/v2 category_maturity=growing '
      || 'competitor_coverage=sufficient primary_signal=format.comparison '
      || 'creative_angle=comparison '
      || 'primary_hook=question_led.'
  ),
  false,
  'a second conflicting reserved category rule can never be receipted'
);

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
  (select strpos(contract.definition, '''category_evidence_readiness_not_model_iq''') > 0
     and strpos(contract.definition, '''retained_youtube_evidence''') > 0
     and strpos(contract.definition, '''lineage_history_limit_per_source'', 10') > 0
     and strpos(contract.definition, '''analysis_history_limit_per_source'', 10') > 0
     and strpos(contract.definition, '''item_limit'', 50') > 0
   from (select lower(
     pg_get_functiondef(
       'public.creator_research_category_learning_status(jsonb)'::regprocedure
     ) || pg_get_functiondef(
       'content_factory_private.creator_research_category_learning_status_pre_truth_v1(jsonb)'::regprocedure
     )
   ) definition) contract),
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
  )), 'complete_product_research_pre_ai_handoff_v1') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.complete_product_research_pre_ai_handoff_v1(jsonb)'::regprocedure
  )), 'complete_product_research_v2_base') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.complete_product_research_pre_ai_handoff_v1(jsonb)'::regprocedure
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
  perform set_config(
    'contentengine.project_id',
    'c0100000-0000-4000-8000-000000000007',
    true
  );
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
insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind, system_role,
  status, position, created_by, updated_by
) values (
  'c0100000-0000-4000-8000-000000000007',
  'c0100000-0000-4000-8000-000000000002', null,
  'Category Readiness project', 'blue', 'project', null,
  'active', 1024,
  'c0100000-0000-4000-8000-000000000001',
  'c0100000-0000-4000-8000-000000000001'
), (
  'c0100000-0000-4000-8000-000000000008',
  'c0100000-0000-4000-8000-000000000002', null,
  'Unrelated category project', 'violet', 'project', null,
  'active', 2048,
  'c0100000-0000-4000-8000-000000000001',
  'c0100000-0000-4000-8000-000000000001'
);
insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000001',
  'owner', 'owner',
  'TEST-ONLY waiver for correction freshness generation coverage.',
  'c0100000-0000-4000-8000-000000000001'
);
insert into content_factory.generation_spend_policies (
  organization_id, paid_generation_enabled,
  daily_limit_minor, monthly_limit_minor, per_request_limit_minor,
  currency, timezone, version, reason, updated_by
) values (
  'c0100000-0000-4000-8000-000000000002',
  true, 1000, 10000, 100,
  'USD', 'Europe/Moscow', 1,
  'Correction freshness generation guard fixture.',
  'c0100000-0000-4000-8000-000000000001'
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
insert into content_factory.media_objects (
  id, organization_id, project_id, owner_id, product_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
) values (
  'c0100000-0000-4000-8000-000000000006',
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000007',
  'c0100000-0000-4000-8000-000000000001',
  'c0100000-0000-4000-8000-000000000003',
  'contentengine-private',
  'c0100000-0000-4000-8000-000000000002/c0100000-0000-4000-8000-000000000001/uploads/correction-source.jpg',
  'image/jpeg', 2048, repeat('c', 64), 'ready',
  jsonb_build_object(
    'kind', 'product_photo',
    'original_filename', 'correction-source.jpg',
    'rights_confirmed', true
  ),
  'category-readiness-correction-source'
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
      'coverage', 'sufficient',
      'competitors', jsonb_build_array(jsonb_build_object(
        'name', 'PROVIDER_PROSE_NEVER_COPY',
        'source_ids', jsonb_build_array('web:s1')
      )),
      'saturated_patterns', '[]'::jsonb,
      'content_gaps', '[]'::jsonb
    ),
    'trend_analysis', jsonb_build_object(
      'signal_catalog_version', 'structural_v1',
      'signals', jsonb_build_array(jsonb_build_object(
        'signal_key', 'format.comparison',
        'signal', 'PROVIDER_TREND_PROSE_NEVER_COPY',
        'direction', 'growing',
        'confidence', 'high',
        'recommended_use', 'test',
        'source_ids', jsonb_build_array('web:s1', 'web:s2')
      ))
    ),
    'scenarios', jsonb_build_array(jsonb_build_object(
      'hook', 'Почему этот продукт проще показать в одном честном действии?',
      'shot_list', jsonb_build_array(
        'Покажите точный продукт крупно и продемонстрируйте одно действие.'
      )
    )),
    'sources', jsonb_build_array(jsonb_build_object(
      'id', 'web:s1',
      'type', 'market_data'
    )),
    'claims', jsonb_build_object(
      'safe', jsonb_build_array(jsonb_build_object(
        'claim', 'Показан точный товар из подтвержденного источника.',
        'basis', 'Точный SKU и исходное фото подтверждены человеком.',
        'source_ids', jsonb_build_array('web:s1')
      )),
      'forbidden', jsonb_build_array(jsonb_build_object(
        'claim', 'Гарантированный пользовательский результат.',
        'reason', 'Источник не подтверждает обещание результата.',
        'safer_alternative', 'Показывать только наблюдаемое действие с товаром.',
        'source_ids', jsonb_build_array('web:s1')
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
    'title', 'Runtime category evidence draft',
    'brief', run.summary,
    'source_ids', (
      select jsonb_agg(source.id order by source.created_at, source.id)
      from content_factory.product_research_sources source
      where source.organization_id = run.organization_id
        and source.run_id = run.id
    ),
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Verify runtime lifecycle',
      'instructions', 'Exercise bounded persisted-result parsing.'
    ))
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

select throws_ok(
  $same_category_new_project$
    do $new_project$
    declare
      brief_value jsonb := jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'category_name', 'Runtime evidence category',
          'definition', 'The same stable category with project-local evidence.',
          'maturity', 'saturated'
        ),
        'competitor_analysis', jsonb_build_object('coverage', 'limited'),
        'trend_analysis', jsonb_build_object(
          'signal_catalog_version', 'structural_v1',
          'signals', jsonb_build_array(jsonb_build_object(
            'signal_key', 'proof.social_proof',
            'direction', 'stable',
            'confidence', 'high',
            'recommended_use', 'test'
          ))
        ),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'hook', 'Before buying, verify the exact product in use',
          'shot_list', jsonb_build_array('Show the exact product')
        ))
      );
      temporal_binding record;
      structure_value jsonb;
    begin
      perform set_config(
        'contentengine.project_id',
        'c0100000-0000-4000-8000-000000000008',
        true
      );
      insert into content_factory.product_research_runs (
        id, organization_id, project_id, product_id, created_by, status,
        input, summary, request_hash, completion_hash, idempotency_key,
        finished_at
      ) values (
        'c0100000-0000-4000-8000-000000000077',
        'c0100000-0000-4000-8000-000000000002',
        'c0100000-0000-4000-8000-000000000008',
        'c0100000-0000-4000-8000-000000000003',
        'c0100000-0000-4000-8000-000000000001',
        'completed', '{}'::jsonb, brief_value,
        repeat('7', 64), repeat('8', 64),
        'category-rule-same-category-new-project', clock_timestamp()
      );
      insert into content_factory.product_research_sources (
        id, organization_id, run_id, product_id, created_by, source_type,
        source_url, title, content_hash, trust_level, extracted_facts,
        metadata, fetched_at, created_at
      ) values (
        'c0100000-0000-4000-8000-000000000082',
        'c0100000-0000-4000-8000-000000000002',
        'c0100000-0000-4000-8000-000000000077',
        'c0100000-0000-4000-8000-000000000003',
        'c0100000-0000-4000-8000-000000000001',
        'social_video',
        'https://example.test/same-category-new-project-source',
        'Same category project-local source', repeat('b', 64), 'public',
        jsonb_build_array('Project-local category evidence'),
        jsonb_build_object(
          'model_source_id', 'web:same-category-new-project',
          'classification', 'category'
        ),
        clock_timestamp(), clock_timestamp()
      );
      insert into content_factory.creative_brief_drafts (
        id, organization_id, project_id, run_id, product_id, created_by,
        origin, version, status, title, brief, source_ids, task_blueprint,
        content_hash, approved_by, approved_at
      ) values (
        'c0100000-0000-4000-8000-000000000078',
        'c0100000-0000-4000-8000-000000000002',
        'c0100000-0000-4000-8000-000000000008',
        'c0100000-0000-4000-8000-000000000077',
        'c0100000-0000-4000-8000-000000000003',
        'c0100000-0000-4000-8000-000000000001',
        'human', 1, 'approved', 'Same category in another project',
        brief_value,
        jsonb_build_array('c0100000-0000-4000-8000-000000000082'),
        jsonb_build_array(jsonb_build_object(
          'title', 'Verify project-local category evidence',
          'instructions', 'Compile only the later project evidence.'
        )),
        content_factory_private.json_hash(brief_value),
        'c0100000-0000-4000-8000-000000000001', clock_timestamp()
      );
      select * into temporal_binding
      from content_factory_private
        .generation_spec_research_category_temporal_binding(
          'c0100000-0000-4000-8000-000000000002',
          'c0100000-0000-4000-8000-000000000077',
          'c0100000-0000-4000-8000-000000000078'
        );
      if temporal_binding.category_binding_id is null
         or temporal_binding.category_binding_source_run_id <>
              'c0100000-0000-4000-8000-000000000004'::uuid then
        raise exception 'same_category_new_project_identity_failed';
      end if;
      structure_value := content_factory_private
        .generation_spec_research_structure(brief_value, 1);
      if structure_value ->> 'category_maturity' <> 'saturated'
         or structure_value ->> 'competitor_coverage' <> 'limited'
         or structure_value ->> 'primary_signal' <> 'proof.social_proof' then
        raise exception 'same_category_new_project_rule_failed';
      end if;
      perform content_factory_private
        .require_generation_project_provenance_v49(
          'c0100000-0000-4000-8000-000000000002',
          'c0100000-0000-4000-8000-000000000008',
          'c0100000-0000-4000-8000-000000000003',
          jsonb_build_object(
            'research_id', 'c0100000-0000-4000-8000-000000000077',
            'creative_brief_draft_id',
              'c0100000-0000-4000-8000-000000000078',
            'scenario_position', 1
          ),
          null, null, '{}'::jsonb
        );
      perform set_config(
        'contentengine.project_id',
        'c0100000-0000-4000-8000-000000000007',
        true
      );
      raise exception 'same_category_new_project_ok';
    end
    $new_project$
  $same_category_new_project$,
  'P0001', 'same_category_new_project_ok',
  'a later project reuses stable category identity but compiles its own rule'
);

insert into content_factory.research_market_categories (
  id, organization_id, canonical_name, normalized_name, definition,
  status, created_by
) values (
  'c0100000-0000-4000-8000-000000000076',
  'c0100000-0000-4000-8000-000000000002',
  'Runtime retirement category', 'runtime retirement category',
  'A temporary category used to verify audited retirement and replay.',
  'active', 'c0100000-0000-4000-8000-000000000001'
);
create temporary table runtime_category_retirement on commit drop as
select public.creator_retire_research_market_category(jsonb_build_object(
  'organization_id', 'c0100000-0000-4000-8000-000000000002',
  'category_id', 'c0100000-0000-4000-8000-000000000076',
  'reason', 'Retire a temporary category through the audited control.',
  'confirmation', true,
  'idempotency_key', 'category-readiness-runtime-retirement'
)) value;
select is(
  (select value ->> 'status' from runtime_category_retirement),
  'retired',
  'an owner can retire a category through the confirmed audited control'
);
select is(
  (select status
   from content_factory.research_market_categories
   where id = 'c0100000-0000-4000-8000-000000000076'),
  'retired',
  'the audited category retirement updates the registry status'
);
create temporary table runtime_category_retirement_replay on commit drop as
select public.creator_retire_research_market_category(jsonb_build_object(
  'organization_id', 'c0100000-0000-4000-8000-000000000002',
  'category_id', 'c0100000-0000-4000-8000-000000000076',
  'reason', 'Retire a temporary category through the audited control.',
  'confirmation', true,
  'idempotency_key', 'category-readiness-runtime-retirement'
)) value;
select is(
  (select value ->> 'replayed' from runtime_category_retirement_replay),
  'true',
  'category retirement is safely idempotent on retry'
);
select is(
  (select count(*)::integer
   from content_factory.research_market_category_retirement_events
   where category_id = 'c0100000-0000-4000-8000-000000000076'),
  1,
  'category retirement records exactly one immutable audit event'
);
select throws_ok(
  $$
    update content_factory.research_market_categories
    set status = 'active'
    where id = 'c0100000-0000-4000-8000-000000000076'
  $$,
  '55000', 'research_market_categories_append_only',
  'a retired category cannot be restored by direct mutation'
);

select throws_ok(
  $same_category_temporal$
    do $same_category$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      resolved record;
      brief_value jsonb := jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'category_name', 'Runtime evidence category',
          'definition', 'Changed evidence for the same stable market identity.',
          'maturity', 'established'
        ),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'hook', 'Show one updated category scenario',
          'shot_list', jsonb_build_array('Show the exact product')
        ))
      );
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;
      insert into content_factory.product_research_runs (
        id, organization_id, product_id, created_by, status, input, summary,
        request_hash, completion_hash, idempotency_key, finished_at
      ) values (
        'c0100000-0000-4000-8000-000000000070',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'completed', '{}'::jsonb, brief_value,
        repeat('7', 64), repeat('8', 64),
        'category-rule-same-category-new-evidence', clock_timestamp()
      );
      insert into content_factory.product_research_sources (
        id, organization_id, run_id, product_id, created_by, source_type,
        source_url, title, content_hash, trust_level, extracted_facts,
        metadata, fetched_at, created_at
      ) values (
        'c0100000-0000-4000-8000-000000000083',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000070',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'market_data',
        'https://example.test/same-category-new-evidence-source',
        'Same category changed evidence source', repeat('c', 64), 'public',
        jsonb_build_array('Changed evidence for the stable category'),
        jsonb_build_object(
          'model_source_id', 'web:same-category-new-evidence',
          'classification', 'category'
        ),
        clock_timestamp(), clock_timestamp()
      );
      insert into content_factory.creative_brief_drafts (
        id, organization_id, run_id, product_id, created_by, origin, version,
        status, title, brief, source_ids, task_blueprint, content_hash
      ) values (
        'c0100000-0000-4000-8000-000000000071',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000070',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'human', 1, 'draft', 'Same category changed evidence', brief_value,
        jsonb_build_array('c0100000-0000-4000-8000-000000000083'),
        jsonb_build_array(jsonb_build_object(
          'title', 'Verify changed category evidence',
          'instructions', 'Retain the stable category identity.'
        )),
        content_factory_private.json_hash(brief_value)
      );
      select * into resolved
      from content_factory_private
        .generation_spec_research_category_temporal_binding(
          current_binding.organization_id,
          'c0100000-0000-4000-8000-000000000070',
          'c0100000-0000-4000-8000-000000000071'
        );
      if resolved.category_binding_id is distinct from current_binding.id then
        raise exception 'same_category_temporal_binding_failed';
      end if;
      raise exception 'same_category_temporal_binding_ok';
    end
    $same_category$
  $same_category_temporal$,
  'P0001', 'same_category_temporal_binding_ok',
  'changed evidence in the same canonical category reuses stable identity'
);

select throws_ok(
  $same_category_new_alias$
    do $new_alias$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      resolution_value jsonb;
      replay_value jsonb;
      temporal_binding record;
      brief_value jsonb := jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'category_name', 'Runtime evidence synonym',
          'definition', 'A new synonym for the same stable market category.',
          'maturity', 'growing'
        ),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'hook', 'Show the same category under its new synonym',
          'shot_list', jsonb_build_array('Show the exact product')
        ))
      );
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;
      insert into content_factory.product_research_runs (
        id, organization_id, product_id, created_by, status, input, summary,
        request_hash, completion_hash, idempotency_key, finished_at
      ) values (
        'c0100000-0000-4000-8000-000000000080',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'completed', '{}'::jsonb, brief_value,
        repeat('1', 64), repeat('2', 64),
        'category-rule-new-alias-run', clock_timestamp()
      );
      insert into content_factory.product_research_sources (
        id, organization_id, run_id, product_id, created_by, source_type,
        source_url, title, content_hash, trust_level, extracted_facts,
        metadata, fetched_at, created_at
      ) values (
        'c0100000-0000-4000-8000-000000000084',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000080',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'social_video',
        'https://example.test/same-category-new-alias-source',
        'Same category new synonym source', repeat('d', 64), 'public',
        jsonb_build_array('Evidence described with a new category synonym'),
        jsonb_build_object(
          'model_source_id', 'web:same-category-new-alias',
          'classification', 'category'
        ),
        clock_timestamp(), clock_timestamp()
      );
      insert into content_factory.creative_brief_drafts (
        id, organization_id, run_id, product_id, created_by, origin, version,
        status, title, brief, source_ids, task_blueprint, content_hash
      ) values (
        'c0100000-0000-4000-8000-000000000081',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000080',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'ai', 1, 'draft', 'Same category new synonym', brief_value,
        jsonb_build_array('c0100000-0000-4000-8000-000000000084'),
        jsonb_build_array(jsonb_build_object(
          'title', 'Verify the new category synonym',
          'instructions', 'Reaffirm the stable category without duplication.'
        )),
        content_factory_private.json_hash(brief_value)
      );
      resolution_value :=
        public.creator_reaffirm_research_market_category(
          jsonb_build_object(
            'organization_id', current_binding.organization_id,
            'run_id', 'c0100000-0000-4000-8000-000000000080',
            'action', 'reaffirm',
            'category_id', current_binding.category_id,
            'candidate_hash', content_factory_private.json_hash(
              brief_value -> 'category_analysis'
            ),
            'confirmation', true,
            'reason', 'Confirm the proposed name as the same category.',
            'idempotency_key', 'category-rule-new-alias-reaffirm'
          )
        );
      replay_value := public.creator_reaffirm_research_market_category(
        jsonb_build_object(
          'organization_id', current_binding.organization_id,
          'run_id', 'c0100000-0000-4000-8000-000000000080',
          'action', 'reaffirm',
          'category_id', current_binding.category_id,
          'candidate_hash', content_factory_private.json_hash(
            brief_value -> 'category_analysis'
          ),
          'confirmation', true,
          'reason', 'Confirm the proposed name as the same category.',
          'idempotency_key', 'category-rule-new-alias-reaffirm'
        )
      );
      select * into temporal_binding
      from content_factory_private
        .generation_spec_research_category_temporal_binding(
          current_binding.organization_id,
          'c0100000-0000-4000-8000-000000000080',
          'c0100000-0000-4000-8000-000000000081'
        );
      if resolution_value #>> '{binding,decision_action}' <> 'reaffirm'
         or resolution_value #>> '{binding,category_key}' <>
              current_binding.category_id::text
         or replay_value #>> '{binding,binding_id}' <>
              resolution_value #>> '{binding,binding_id}'
         or temporal_binding.category_binding_id::text <>
              resolution_value #>> '{binding,binding_id}'
         or content_factory_private.research_draft_market_category_id(
              current_binding.organization_id,
              'c0100000-0000-4000-8000-000000000080',
              'c0100000-0000-4000-8000-000000000081'
            ) is distinct from current_binding.category_id
         or not exists (
              select 1
              from content_factory.research_market_category_aliases alias
              where alias.organization_id = current_binding.organization_id
                and alias.category_id = current_binding.category_id
                and alias.normalized_alias =
                  'runtime evidence synonym'
            ) then
        raise exception 'same_category_new_alias_failed';
      end if;
      raise exception 'same_category_new_alias_ok';
    end
    $new_alias$
  $same_category_new_alias$,
  'P0001', 'same_category_new_alias_ok',
  'a user can append one audited synonym without duplicating the category'
);

select throws_ok(
  $exact_reclass_temporal$
    do $exact_reclass$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      resolved record;
      analysis_event_id_value uuid;
      brief_value jsonb := jsonb_build_object(
        'category_analysis', jsonb_build_object(
          'category_name', 'Runtime reclassified category',
          'definition', 'A new exact category selected for this research draft.',
          'maturity', 'emerging'
        ),
        'scenarios', jsonb_build_array(jsonb_build_object(
          'hook', 'Show one reclassified category scenario',
          'shot_list', jsonb_build_array('Show the exact product')
        ))
      );
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;
      insert into content_factory.product_research_runs (
        id, organization_id, product_id, created_by, status, input, summary,
        request_hash, completion_hash, idempotency_key, finished_at
      ) values (
        'c0100000-0000-4000-8000-000000000072',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'completed', '{}'::jsonb, brief_value,
        repeat('9', 64), repeat('a', 64),
        'category-rule-exact-reclass-run', clock_timestamp()
      );
      insert into content_factory.product_research_sources (
        id, organization_id, run_id, product_id, created_by, source_type,
        source_url, title, content_hash, trust_level, extracted_facts,
        metadata, fetched_at, created_at
      ) values (
        'c0100000-0000-4000-8000-000000000079',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000072',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'social_video',
        'https://example.test/exact-reclassification-source',
        'Exact reclassification source', repeat('f', 64), 'public',
        '[]'::jsonb,
        jsonb_build_object(
          'model_source_id', 'web:exact-reclass',
          'classification', 'category'
        ),
        clock_timestamp(), clock_timestamp()
      );
      insert into content_factory.creative_brief_drafts (
        id, organization_id, run_id, product_id, created_by, origin, version,
        status, title, brief, source_ids, task_blueprint, content_hash
      ) values (
        'c0100000-0000-4000-8000-000000000073',
        current_binding.organization_id,
        'c0100000-0000-4000-8000-000000000072',
        current_binding.product_id,
        'c0100000-0000-4000-8000-000000000001',
        'human', 1, 'draft', 'Exact reclassification source', brief_value,
        jsonb_build_array('c0100000-0000-4000-8000-000000000079'),
        jsonb_build_array(jsonb_build_object(
          'title', 'Verify exact source-draft reclassification',
          'instructions', 'Bind the source to the exact reclassified category.'
        )),
        content_factory_private.json_hash(brief_value)
      );
      insert into content_factory.research_market_categories (
        id, organization_id, canonical_name, normalized_name, definition,
        status, created_by
      ) values (
        'c0100000-0000-4000-8000-000000000074',
        current_binding.organization_id, 'Runtime reclassified category',
        'runtime reclassified category',
        'A new exact category selected for this research draft.', 'active',
        'c0100000-0000-4000-8000-000000000001'
      );
      insert into content_factory.research_product_market_category_bindings (
        id, organization_id, product_id, category_id, previous_binding_id,
        binding_version, decision_action, source_run_id, source_draft_id,
        candidate_hash, reason, confirmed_by, idempotency_key
      ) values (
        'c0100000-0000-4000-8000-000000000075',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000074', current_binding.id,
        current_binding.binding_version + 1, 'reclassify',
        'c0100000-0000-4000-8000-000000000072',
        'c0100000-0000-4000-8000-000000000073',
        content_factory_private.json_hash(brief_value -> 'category_analysis'),
        'Confirm exact source-draft reclassification.',
        'c0100000-0000-4000-8000-000000000001',
        'category-rule-exact-reclass-binding'
      );
      perform public.system_register_research_category_sources(
        jsonb_build_object(
          'organization_id', current_binding.organization_id,
          'run_id', 'c0100000-0000-4000-8000-000000000072'
        )
      );
      select event.id into analysis_event_id_value
      from content_factory.research_category_source_ledger ledger
      join content_factory.research_source_analysis_events event
        on event.organization_id = ledger.organization_id
       and event.source_ledger_id = ledger.id
      where ledger.organization_id = current_binding.organization_id
        and ledger.market_category_id =
          'c0100000-0000-4000-8000-000000000074'
        and ledger.source_id =
          'c0100000-0000-4000-8000-000000000079'
      order by event.analysis_version desc, event.id desc
      limit 1;
      perform content_factory_private
        .append_research_draft_source_analysis_binding(
          current_binding.organization_id,
          'c0100000-0000-4000-8000-000000000072',
          'c0100000-0000-4000-8000-000000000073',
          'c0100000-0000-4000-8000-000000000079',
          analysis_event_id_value, 'baseline_adoption'
        );
      if content_factory_private.research_draft_market_category_id(
           current_binding.organization_id,
           'c0100000-0000-4000-8000-000000000072',
           'c0100000-0000-4000-8000-000000000073'
         ) is distinct from
           'c0100000-0000-4000-8000-000000000074'::uuid then
        raise exception 'exact_reclass_source_category_failed';
      end if;
      if not content_factory_private.research_draft_source_analysis_fresh(
           current_binding.organization_id,
           'c0100000-0000-4000-8000-000000000072',
           'c0100000-0000-4000-8000-000000000073'
         ) then
        raise exception 'exact_reclass_source_freshness_failed';
      end if;
      if (
        select binding.market_category_id
        from content_factory.research_draft_source_analysis_bindings binding
        where binding.organization_id = current_binding.organization_id
          and binding.run_id =
            'c0100000-0000-4000-8000-000000000072'
          and binding.draft_id =
            'c0100000-0000-4000-8000-000000000073'
          and binding.source_id =
            'c0100000-0000-4000-8000-000000000079'
        order by binding.binding_version desc, binding.id desc
        limit 1
      ) is distinct from
          'c0100000-0000-4000-8000-000000000074'::uuid then
        raise exception 'exact_reclass_source_binding_failed';
      end if;
      select * into resolved
      from content_factory_private
        .generation_spec_research_category_temporal_binding(
          current_binding.organization_id,
          'c0100000-0000-4000-8000-000000000072',
          'c0100000-0000-4000-8000-000000000073'
        );
      if resolved.category_binding_id is distinct from
           'c0100000-0000-4000-8000-000000000075'::uuid then
        raise exception 'exact_reclass_temporal_binding_failed';
      end if;
      raise exception 'exact_reclass_temporal_binding_ok';
    end
    $exact_reclass$
  $exact_reclass_temporal$,
  'P0001', 'exact_reclass_temporal_binding_ok',
  'exact source-draft reclassification wins even after draft creation'
);

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, idempotency_key, finished_at, created_at
) values (
  'c0100000-0000-4000-8000-000000000009',
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  'cancelled', '{}'::jsonb, '{}'::jsonb,
  repeat('d', 64), 'category-readiness-newer-unbound-run',
  clock_timestamp(),
  clock_timestamp() + interval '1 minute'
);
create temporary table runtime_ai_market_scope_index on commit drop as
select public.creator_ai_learning_market_scope_index(jsonb_build_object(
  'organization_id', 'c0100000-0000-4000-8000-000000000002',
  'project_id', 'c0100000-0000-4000-8000-000000000007',
  'limit', 50
)) value;
select is(
  (select value ->> 'version' from runtime_ai_market_scope_index),
  'ai-learning-market-scope-index-v2',
  'the AI control room reads the project-scoped dynamic market contract'
);
select is(
  (select value ->> 'project_id' from runtime_ai_market_scope_index),
  'c0100000-0000-4000-8000-000000000007',
  'the AI market index preserves the exact requested workspace project'
);
select is(
  (select jsonb_array_length(value -> 'scopes')
   from runtime_ai_market_scope_index),
  1,
  'one current product binding creates one explicit AI market context'
);
select is(
  (select value #>> '{scopes,0,project_id}'
   from runtime_ai_market_scope_index),
  'c0100000-0000-4000-8000-000000000007',
  'each AI market scope is bound to its exact source-run project'
);
select is(
  jsonb_array_length(
    public.creator_ai_learning_market_scope_index(jsonb_build_object(
      'organization_id', 'c0100000-0000-4000-8000-000000000002',
      'project_id', 'c0100000-0000-4000-8000-000000000008',
      'limit', 50
    )) -> 'scopes'
  ),
  0,
  'a different workspace project cannot see the bound research scope'
);
select is(
  (select value #>> '{scopes,0,run_id}'
   from runtime_ai_market_scope_index),
  'c0100000-0000-4000-8000-000000000004',
  'the AI context keeps the exact binding source run instead of a newer unrelated run'
);
select is(
  (select value #>> '{scopes,0,market_category_id}'
   from runtime_ai_market_scope_index),
  (select binding.category_id::text
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
   order by binding.binding_version desc, binding.id desc
   limit 1),
  'the index exposes the exact dynamic category UUID without other fallback'
);
select is(
  (select value #>> '{scopes,0,readiness,definition_version}'
   from runtime_ai_market_scope_index),
  'category-evidence-readiness-v3',
  'the index publishes only the current truthful readiness formula'
);
select is(
  (select (value #>> '{scopes,0,readiness,score}')::integer
   from runtime_ai_market_scope_index),
  (select (
     content_factory_private.research_category_evidence_readiness(
       'c0100000-0000-4000-8000-000000000002',
       binding.category_id,
       (select (value ->> 'as_of')::timestamptz
        from runtime_ai_market_scope_index)
     ) ->> 'score'
   )::integer
   from content_factory.research_product_market_category_bindings binding
   where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
   order by binding.binding_version desc, binding.id desc
   limit 1),
  'the AI index score exactly equals research evidence readiness at one as-of'
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
  (select count(distinct binding.source_id)::integer
   from content_factory.research_draft_source_analysis_bindings binding
   where binding.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and binding.run_id = 'c0100000-0000-4000-8000-000000000004'
     and binding.draft_id = 'c0100000-0000-4000-8000-000000000005'),
  30,
  'every draft source is bound to its exact semantic analysis head'
);
select is(
  (select count(*)::integer
   from content_factory.research_draft_source_analysis_bindings binding
   where binding.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and binding.run_id = 'c0100000-0000-4000-8000-000000000004'
     and binding.draft_id = 'c0100000-0000-4000-8000-000000000005'
     and binding.binding_kind = 'baseline_adoption'),
  24,
  'parser baselines extend draft lineage append-only after ledger capture'
);
select is(
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000004',
    'c0100000-0000-4000-8000-000000000005'
  ),
  true,
  'the initial draft is fresh against its immutable source-analysis bindings'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_branches branch
   join content_factory.research_stage_heads head
     on head.organization_id = branch.organization_id
    and head.run_id = branch.run_id
    and head.branch_id = branch.id
   where branch.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and branch.run_id = 'c0100000-0000-4000-8000-000000000004'
     and branch.branch_key = 'main'
     and head.state = 'current'),
  7,
  'all seven governed research stages start current'
);

create temporary table correction_generation_state (
  draft_approval_result jsonb,
  prepare_result jsonb,
  approve_result jsonb,
  start_result jsonb,
  stale_start_result jsonb,
  cross_run_recompute_result jsonb
) on commit drop;
insert into correction_generation_state default values;

update correction_generation_state state
set draft_approval_result = public.creator_approve_creative_brief(
  jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'idempotency_key', 'category-readiness-draft-approval',
    'draft_id', 'c0100000-0000-4000-8000-000000000005'
  )
);
select is(
  (select draft.status
   from content_factory.creative_brief_drafts draft
   where draft.id = 'c0100000-0000-4000-8000-000000000005'),
  'approved',
  'the exact fresh research draft can be approved before correction'
);

update correction_generation_state state
set prepare_result = public.creator_prepare_generation_spec(
  jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'project_id', 'c0100000-0000-4000-8000-000000000007',
    'idempotency_key', 'category-readiness-spec-prepare',
    'exact_scope', jsonb_build_object(
      'primary_media_id', 'c0100000-0000-4000-8000-000000000006',
      'media_ids', jsonb_build_array(
        'c0100000-0000-4000-8000-000000000006'
      ),
      'platform', 'wildberries',
      'model', 'gen4_turbo',
      'duration_seconds', 5,
      'product_category', 'other',
      'format', '9:16',
      'audio', false
    ),
    'editable_intent',
      'Show the exact approved-research product in one honest interaction.',
    'proposed_prompt',
      'Точный товар: Category Readiness Runtime Product, артикул CATEGORY-READINESS-RUNTIME. Создай один непрерывный вертикальный ролик длительностью 5 секунд. Без речи, дикторского текста и сгенерированных надписей. Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений. Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара. '
      || content_factory_private.generation_product_interaction_requirement(
        'Category Readiness Runtime Product', 'other'
      )
      || E'\n'
      || content_factory_private
        .generation_spec_research_category_rule_fragment(
          content_factory_private.generation_spec_research_structure(
            (select draft.brief
             from content_factory.creative_brief_drafts draft
             where draft.id =
               'c0100000-0000-4000-8000-000000000005'),
            1
          ) || jsonb_build_object('source', 'approved_research')
        ),
    'learning_context',
      content_factory_private.generation_spec_research_structure(
        (select draft.brief
         from content_factory.creative_brief_drafts draft
         where draft.id = 'c0100000-0000-4000-8000-000000000005'),
        1
      ) - array[
        'category_maturity', 'competitor_coverage', 'primary_signal'
      ]::text[] || jsonb_build_object(
        'source', 'approved_research',
        'creative_brief_draft_id',
          'c0100000-0000-4000-8000-000000000005',
        'scenario_position', 1,
        'product_category', 'other'
      ),
    'repair_context', null,
    'research_provenance', jsonb_build_object(
      'research_id', 'c0100000-0000-4000-8000-000000000004',
      'creative_brief_draft_id',
        'c0100000-0000-4000-8000-000000000005',
      'scenario_position', 1
    ),
    'performance_policy_provenance', null,
    'repair_provenance', null,
    'confirmation', true,
    'reason', 'Prepare an exact approved-research generation specification.'
  )
);
select is(
  (select prepare_result #>> '{generation_spec,status}'
   from correction_generation_state),
  'draft',
  'fresh source-analysis evidence can prepare a governed generation spec'
);
select is(
  (select count(*)::integer
   from content_factory.generation_spec_research_category_rule_bindings receipt
   join correction_generation_state state
     on receipt.spec_id =
       (state.prepare_result #>> '{generation_spec,spec_id}')::uuid
    and receipt.spec_version =
       (state.prepare_result #>> '{generation_spec,spec_version}')::integer
   join content_factory.generation_spec_versions version
     on version.organization_id = receipt.organization_id
    and version.version_id = receipt.generation_spec_version_id
   where receipt.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and receipt.research_run_id =
       'c0100000-0000-4000-8000-000000000004'
     and receipt.research_draft_id =
       'c0100000-0000-4000-8000-000000000005'
     and receipt.market_category_id = (
       select binding.category_id
       from content_factory.research_product_market_category_bindings binding
       where binding.organization_id = receipt.organization_id
         and binding.product_id = receipt.product_id
       order by binding.binding_version desc, binding.id desc
       limit 1
     )
     and receipt.prompt_hash = version.prompt_hash
     and receipt.rule_hash = content_factory_private.raw_text_sha256(
       receipt.rule_version || ' category_maturity='
         || receipt.category_maturity
       || ' competitor_coverage=' || receipt.competitor_coverage
       || ' primary_signal=' || receipt.primary_signal
       || ' creative_angle=' || receipt.creative_angle
       || ' primary_hook=' || receipt.primary_hook || '.'
     )
     and content_factory_private
       .generation_spec_prompt_has_exact_category_rule(
         version.compiled_prompt,
         receipt.rule_version || ' category_maturity='
           || receipt.category_maturity
           || ' competitor_coverage=' || receipt.competitor_coverage
           || ' primary_signal=' || receipt.primary_signal
           || ' creative_angle=' || receipt.creative_angle
           || ' primary_hook=' || receipt.primary_hook || '.'
       )),
  1,
  'approved research appends one exact category/spec/prompt/rule receipt'
);
select is(
  (select concat_ws('|', receipt.category_maturity,
                           receipt.competitor_coverage,
                           receipt.primary_signal)
   from content_factory.generation_spec_research_category_rule_bindings receipt
   join correction_generation_state state
     on receipt.spec_id =
       (state.prepare_result #>> '{generation_spec,spec_id}')::uuid
    and receipt.spec_version =
       (state.prepare_result #>> '{generation_spec,spec_version}')::integer),
  'growing|sufficient|format.comparison',
  'the DB end-to-end receipt binds non-default category research fields'
);
select is(
  (select count(*)::integer
   from content_factory.generation_spec_research_category_rule_bindings receipt
   join correction_generation_state state
     on receipt.spec_id =
       (state.prepare_result #>> '{generation_spec,spec_id}')::uuid
    and receipt.spec_version =
       (state.prepare_result #>> '{generation_spec,spec_version}')::integer
   where to_jsonb(receipt)::text ~*
     '(https?://|do_not_copy|provider_|source_url|title|extracted_fact)'),
  0,
  'the immutable category-rule receipt contains no source URL or source prose'
);
select is(
  (select content_factory_private
     .generation_spec_research_category_rule_current(
       'c0100000-0000-4000-8000-000000000002',
       (state.prepare_result #>> '{generation_spec,spec_id}')::uuid,
       (state.prepare_result #>> '{generation_spec,spec_version}')::integer,
       state.prepare_result #>> '{generation_spec,spec_hash}'
     )
   from correction_generation_state state),
  true,
  'the exact research category rule is current before category drift'
);
select throws_ok(
  $category_retirement_stale$
    do $retirement$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      spec_state record;
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;
      perform public.creator_retire_research_market_category(
        jsonb_build_object(
          'organization_id', current_binding.organization_id,
          'category_id', current_binding.category_id,
          'reason', 'Retire the bound category and invalidate its old rule.',
          'confirmation', true,
          'idempotency_key', 'category-rule-retirement-stale-rolled-back'
        )
      );
      select
        (state.prepare_result #>> '{generation_spec,spec_id}')::uuid as spec_id,
        (state.prepare_result #>> '{generation_spec,spec_version}')::integer
          as spec_version,
        state.prepare_result #>> '{generation_spec,spec_hash}' as spec_hash
      into spec_state
      from correction_generation_state state;
      perform public.creator_control_generation_spec(jsonb_build_object(
        'organization_id', current_binding.organization_id,
        'project_id', 'c0100000-0000-4000-8000-000000000007',
        'spec_id', spec_state.spec_id,
        'expected_spec_version', spec_state.spec_version,
        'expected_spec_hash', spec_state.spec_hash,
        'action', 'approve',
        'confirmation', true,
        'reason', 'A retired category rule must fail closed.',
        'idempotency_key', 'category-rule-retired-approval-rolled-back'
      ));
    end
    $retirement$
  $category_retirement_stale$,
  '55000',
  'generation_spec_research_category_rule_stale',
  'retiring a bound category invalidates its old generation rule'
);
select throws_ok(
  $category_drift$
    do $drift$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      spec_state record;
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;

      insert into content_factory.research_market_categories (
        id, organization_id, canonical_name, normalized_name, definition,
        status, created_by
      ) values (
        'c0100000-0000-4000-8000-000000000060',
        'c0100000-0000-4000-8000-000000000002',
        'Temporary drift category', 'temporary drift category',
        'A temporary alternative category used only inside a rolled-back test.',
        'active', 'c0100000-0000-4000-8000-000000000001'
      );
      insert into content_factory.research_product_market_category_bindings (
        id, organization_id, product_id, category_id, previous_binding_id,
        binding_version, decision_action, source_run_id, source_draft_id,
        candidate_hash, reason, confirmed_by, idempotency_key
      ) values (
        'c0100000-0000-4000-8000-000000000061',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000060', current_binding.id,
        current_binding.binding_version + 1, 'create_and_reclassify',
        current_binding.source_run_id, current_binding.source_draft_id,
        repeat('6', 64), 'Exercise category drift fail-close.',
        'c0100000-0000-4000-8000-000000000001',
        'category-rule-drift-rolled-back'
      );

      select
        (state.prepare_result #>> '{generation_spec,spec_id}')::uuid as spec_id,
        (state.prepare_result #>> '{generation_spec,spec_version}')::integer
          as spec_version,
        state.prepare_result #>> '{generation_spec,spec_hash}' as spec_hash
      into spec_state
      from correction_generation_state state;
      perform public.creator_control_generation_spec(jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'project_id', 'c0100000-0000-4000-8000-000000000007',
        'spec_id', spec_state.spec_id,
        'expected_spec_version', spec_state.spec_version,
        'expected_spec_hash', spec_state.spec_hash,
        'action', 'approve',
        'confirmation', true,
        'reason', 'Stale category approval must fail closed.',
        'idempotency_key', 'category-rule-stale-approval-rolled-back'
      ));
    end
    $drift$
  $category_drift$,
  '55000',
  'generation_spec_research_category_rule_stale',
  'a newer category classification invalidates the old research rule'
);

update correction_generation_state state
set approve_result = public.creator_control_generation_spec(
  jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'project_id', 'c0100000-0000-4000-8000-000000000007',
    'spec_id', state.prepare_result #>> '{generation_spec,spec_id}',
    'expected_spec_version',
      (state.prepare_result #>> '{generation_spec,spec_version}')::integer,
    'expected_spec_hash', state.prepare_result #>> '{generation_spec,spec_hash}',
    'action', 'approve',
    'confirmation', true,
    'reason', 'Approve the exact fresh evidence-bound specification.',
    'idempotency_key', 'category-readiness-spec-approve'
  )
);
select is(
  (select approve_result #>> '{generation_spec,status}'
   from correction_generation_state),
  'approved',
  'fresh evidence-bound generation spec can be explicitly approved'
);
select is(
  (select content_factory_private.research_generation_spec_evidence_fresh(
     'c0100000-0000-4000-8000-000000000002',
     (state.approve_result #>> '{generation_spec,spec_id}')::uuid,
     (state.approve_result #>> '{generation_spec,spec_version}')::integer,
     state.approve_result #>> '{generation_spec,spec_hash}'
   )
   from correction_generation_state state),
  true,
  'approved generation provenance is fresh before source correction'
);

update correction_generation_state state
set start_result = public.creator_start_real_generation(
  jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'project_id', 'c0100000-0000-4000-8000-000000000007',
    'campaign_id', (
      select campaign.id
      from content_factory.generation_campaigns campaign
      where campaign.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and campaign.kind = 'default'
    ),
    'idempotency_key', 'category-readiness-generation-start',
    'sku', 'CATEGORY-READINESS-RUNTIME',
    'product_name', 'Category Readiness Runtime Product',
    'product_category', 'other',
    'count', 1,
    'format', '9:16',
    'brief', state.approve_result #>> '{generation_spec,compiled_prompt}',
    'media_ids', jsonb_build_array(
      'c0100000-0000-4000-8000-000000000006'
    ),
    'platform', 'wildberries',
    'destination_ref', 'wb-category-readiness-correction',
    'mode', 'real',
    'provider', 'runway',
    'model', 'gen4_turbo',
    'duration_seconds', 5,
    'allow_real_spend', true,
    'spend_confirmation', 'RUNWAY_GEN4_TURBO_5S_USD_0.25',
    'learning_context',
      content_factory_private.generation_spec_research_structure(
        (select draft.brief
         from content_factory.creative_brief_drafts draft
         where draft.id = 'c0100000-0000-4000-8000-000000000005'),
        1
      ) - array[
        'category_maturity', 'competitor_coverage', 'primary_signal'
      ]::text[] || jsonb_build_object(
        'source', 'approved_research',
        'creative_brief_draft_id',
          'c0100000-0000-4000-8000-000000000005',
        'scenario_position', 1,
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
  )
);
select is(
  (select start_result #>> '{job,status}'
   from correction_generation_state),
  'queued',
  'fresh approved research can reserve one paid job without provider start'
);

select throws_ok(
  $queued_category_drift$
    do $queued_drift$
    declare
      current_binding
        content_factory.research_product_market_category_bindings%rowtype;
      spec_state record;
      claim_result jsonb;
    begin
      select binding.* into current_binding
      from content_factory.research_product_market_category_bindings binding
      where binding.organization_id =
          'c0100000-0000-4000-8000-000000000002'
        and binding.product_id =
          'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc, binding.id desc
      limit 1;
      insert into content_factory.research_market_categories (
        id, organization_id, canonical_name, normalized_name, definition,
        status, created_by
      ) values (
        'c0100000-0000-4000-8000-000000000064',
        current_binding.organization_id,
        'Queued drift category', 'queued drift category',
        'A temporary category proving the final provider-start category gate.',
        'active', 'c0100000-0000-4000-8000-000000000001'
      );
      insert into content_factory.research_product_market_category_bindings (
        id, organization_id, product_id, category_id, previous_binding_id,
        binding_version, decision_action, source_run_id, source_draft_id,
        candidate_hash, reason, confirmed_by, idempotency_key
      ) values (
        'c0100000-0000-4000-8000-000000000065',
        current_binding.organization_id, current_binding.product_id,
        'c0100000-0000-4000-8000-000000000064', current_binding.id,
        current_binding.binding_version + 1, 'create_and_reclassify',
        current_binding.source_run_id, current_binding.source_draft_id,
        repeat('6', 64), 'Exercise the queued provider-start category guard.',
        'c0100000-0000-4000-8000-000000000001',
        'category-rule-queued-drift-rolled-back'
      );
      select
        (state.approve_result #>> '{generation_spec,spec_id}')::uuid as spec_id,
        (state.approve_result #>> '{generation_spec,spec_version}')::integer
          as spec_version,
        state.approve_result #>> '{generation_spec,spec_hash}' as spec_hash,
        state.start_result #>> '{job,id}' as job_id
      into spec_state
      from correction_generation_state state;
      if content_factory_private
           .generation_spec_research_category_rule_current(
             current_binding.organization_id, spec_state.spec_id,
             spec_state.spec_version, spec_state.spec_hash
           ) then
        raise exception 'queued_category_drift_not_detected';
      end if;
      claim_result := public.system_update_real_generation(
        jsonb_build_object('job_id', spec_state.job_id, 'status', 'starting')
      );
      if claim_result ->> 'code' <>
           'generation_spec_provider_start_stale'
         or claim_result #>> '{job,status}' <> 'failed'
         or claim_result #>> '{job,failure_code}' <>
           'generation_spec_provider_start_stale' then
        raise exception 'queued_category_guard_failed';
      end if;
      raise exception 'queued_category_guard_ok';
    end
    $queued_drift$
  $queued_category_drift$,
  'P0001', 'queued_category_guard_ok',
  'queued work is terminalized when its category changes before provider IO'
);

-- A second run observes the same category content through new local source
-- occurrences. It must inherit the canonical analysis heads rather than
-- silently falling back to legacy freshness.
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
)
select
  'c0100000-0000-4000-8000-000000000030', organization_id, product_id,
  created_by, 'completed', jsonb_build_object(
    'objective', 'Cross-run canonical source-analysis recovery fixture.',
    'marketplace_url', null,
    'source_media_ids', jsonb_build_array(
      'c0100000-0000-4000-8000-000000000006'
    ),
    'platforms', jsonb_build_array('youtube')
  ), summary, repeat('a', 64), repeat('b', 64),
  'category-readiness-cross-run-before-correction', now()
from content_factory.product_research_runs
where id = 'c0100000-0000-4000-8000-000000000004';
insert into content_factory.product_research_sources (
  organization_id, run_id, product_id, created_by, source_type, source_url,
  media_object_id, title, content_hash, trust_level, extracted_facts,
  metadata, fetched_at, published_at, created_at
)
select source.organization_id,
  'c0100000-0000-4000-8000-000000000030', source.product_id,
  source.created_by, source.source_type, source.source_url,
  source.media_object_id, source.title, source.content_hash,
  source.trust_level, source.extracted_facts, source.metadata,
  source.fetched_at, source.published_at, clock_timestamp()
from content_factory.product_research_sources source
where source.run_id = 'c0100000-0000-4000-8000-000000000004'
order by source.created_at, source.id;
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash
)
select
  'c0100000-0000-4000-8000-000000000032', run.organization_id, run.id,
  run.product_id, run.created_by, 'ai', 1, 'draft',
  'Cross-run canonical evidence draft', run.summary,
  source_set.source_ids,
  jsonb_build_array(jsonb_build_object(
    'title', 'Verify canonical cross-run evidence',
    'instructions', 'Keep the canonical source correction in later runs.'
  )),
  content_factory_private.json_hash(jsonb_build_object(
    'title', 'Cross-run canonical evidence draft',
    'brief', run.summary,
    'source_ids', source_set.source_ids,
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Verify canonical cross-run evidence',
      'instructions', 'Keep the canonical source correction in later runs.'
    ))
  ))
from content_factory.product_research_runs run
cross join lateral (
  select jsonb_agg(source.id order by source.created_at, source.id)
    as source_ids
  from content_factory.product_research_sources source
  where source.organization_id = run.organization_id
    and source.run_id = run.id
) source_set
where run.id = 'c0100000-0000-4000-8000-000000000030';
select is(
  (select count(distinct binding.source_id)::integer
   from content_factory.research_draft_source_analysis_bindings binding
   where binding.run_id = 'c0100000-0000-4000-8000-000000000030'
     and binding.draft_id = 'c0100000-0000-4000-8000-000000000032'),
  30,
  'a later run maps all local occurrences onto canonical category ledgers'
);
select is(
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000030',
    'c0100000-0000-4000-8000-000000000032'
  ),
  true,
  'the cross-run draft starts fresh against inherited canonical heads'
);
update correction_generation_state state
set cross_run_recompute_result = control.result
from (
  select public.creator_control_research_stage(jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'project_id', 'c0100000-0000-4000-8000-000000000007',
    'run_id', 'c0100000-0000-4000-8000-000000000030',
    'branch_id', branch.id,
    'stage', 'category',
    'action', 'recompute',
    'expected_head_event_id', head.head_event_id,
    'expected_artifact_id', head.artifact_id,
    'expected_content_hash', artifact.content_hash,
    'expected_branch_revision_hash',
      content_factory_private.research_stage_branch_revision_hash(
        branch.organization_id, branch.run_id, branch.id
      ),
    'paid_analysis_ack', true,
    'confirmation', true,
    'user_input',
      'Recompute this inherited category only after explicit confirmation.',
    'reason',
      'Save one cross-run recompute before the canonical source changes.',
    'idempotency_key', 'category-readiness-cross-run-recompute'
  )) as result
  from content_factory.research_stage_branches branch
  join content_factory.research_stage_heads head
    on head.organization_id = branch.organization_id
   and head.run_id = branch.run_id
   and head.branch_id = branch.id
   and head.stage = 'category'
  join content_factory.research_stage_artifacts artifact
    on artifact.organization_id = head.organization_id
   and artifact.run_id = head.run_id
   and artifact.stage = head.stage
   and artifact.id = head.artifact_id
  where branch.run_id = 'c0100000-0000-4000-8000-000000000030'
    and branch.branch_key = 'main'
) control;
select is(
  (select cross_run_recompute_result #>> '{recompute_request,status}'
   from correction_generation_state),
  'queued',
  'the cross-run paid recompute is saved before provider claim'
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
          select binding.candidate_hash
          from content_factory.research_product_market_category_bindings binding
          where binding.organization_id =
              'c0100000-0000-4000-8000-000000000002'
            and binding.source_run_id =
              'c0100000-0000-4000-8000-000000000004'
          order by binding.binding_version desc, binding.id desc
          limit 1
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
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000004',
    'c0100000-0000-4000-8000-000000000005'
  ),
  false,
  'a later human correction makes the exact draft evidence binding stale'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_branches branch
   join content_factory.research_stage_heads head
     on head.organization_id = branch.organization_id
    and head.run_id = branch.run_id
    and head.branch_id = branch.id
   where branch.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and branch.run_id = 'c0100000-0000-4000-8000-000000000004'
     and branch.branch_key = 'main'
     and head.state = 'stale_dependency'),
  7,
  'one corrected source invalidates all seven dependent main-branch stages'
);
select ok(
  exists (
    select 1
    from correction_generation_state state
    join content_factory.research_stage_recompute_requests request
      on request.id = (
        state.cross_run_recompute_result
          #>> '{recompute_request,request_id}'
      )::uuid
    join content_factory.product_research_runs child
      on child.organization_id = request.organization_id
     and child.id = request.child_run_id
    where request.status = 'superseded'
      and request.error_code =
        'source_analysis_changed_before_provider_claim'
      and request.provider_attempt_count = 0
      and child.status = 'cancelled'
      and child.error_code =
        'stage_recompute_source_analysis_superseded'
  ),
  'canonical correction terminalizes the saved cross-run recompute before claim'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_branches branch
   join content_factory.research_stage_heads head
     on head.organization_id = branch.organization_id
    and head.run_id = branch.run_id
    and head.branch_id = branch.id
   where branch.run_id = 'c0100000-0000-4000-8000-000000000030'
     and branch.branch_key = 'main'
     and head.state = 'stale_dependency'),
  7,
  'one canonical correction invalidates all seven stages in the later run'
);
select is(
  (select count(*)::integer
   from correction_generation_state state
   join content_factory.research_run_provider_bindings provider_binding
     on provider_binding.run_id = (
       state.cross_run_recompute_result
         #>> '{recompute_request,child_run_id}'
     )::uuid),
  0,
  'source-analysis supersession creates no cross-run provider binding'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_head_events event
   where event.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and event.run_id = 'c0100000-0000-4000-8000-000000000004'
     and event.action = 'dependency_refresh'
     and event.state = 'stale_dependency'
     and event.correction_source_id = (
       select source.id
       from content_factory.product_research_sources source
       where source.organization_id =
           'c0100000-0000-4000-8000-000000000002'
         and source.run_id = 'c0100000-0000-4000-8000-000000000004'
         and source.metadata ->> 'model_source_id' = 'web:s5'
       limit 1
     )),
  7,
  'source correction invalidation is append-only and auditable per stage'
);
select is(
  (select head.state
   from correction_generation_state state
   join lateral (
     select event.state
     from content_factory.generation_spec_head_events event
     where event.organization_id =
         'c0100000-0000-4000-8000-000000000002'
       and event.spec_id =
         (state.approve_result #>> '{generation_spec,spec_id}')::uuid
     order by event.event_sequence desc
     limit 1
   ) head on true),
  'draft',
  'source correction returns the exact dependent generation spec to draft'
);
select is(
  (select head.action
   from correction_generation_state state
   join lateral (
     select event.action
     from content_factory.generation_spec_head_events event
     where event.organization_id =
         'c0100000-0000-4000-8000-000000000002'
       and event.spec_id =
         (state.approve_result #>> '{generation_spec,spec_id}')::uuid
     order by event.event_sequence desc
     limit 1
   ) head on true),
  'recompute',
  'generation-spec invalidation is an append-only recompute head event'
);
select is(
  (select content_factory_private.generation_spec_envelope(
     'c0100000-0000-4000-8000-000000000002',
     (state.approve_result #>> '{generation_spec,spec_id}')::uuid
   ) #>> '{recommended_next_action,action}'
   from correction_generation_state state),
  'start_new_research',
  'stale generation guidance starts an append-only research recovery run'
);
select throws_ok(
  $$
    select public.creator_control_generation_spec(jsonb_build_object(
      'organization_id', 'c0100000-0000-4000-8000-000000000002',
      'project_id', 'c0100000-0000-4000-8000-000000000007',
      'spec_id', state.approve_result #>> '{generation_spec,spec_id}',
      'expected_spec_version',
        (state.approve_result #>> '{generation_spec,spec_version}')::integer,
      'expected_spec_hash', state.approve_result #>> '{generation_spec,spec_hash}',
      'action', 'approve',
      'confirmation', true,
      'reason', 'Attempt to approve stale source-analysis provenance.',
      'idempotency_key', 'category-readiness-stale-spec-approval'
    ))
    from correction_generation_state state
  $$,
  '55000',
  'generation_spec_research_provenance_stale',
  'stale source-analysis provenance blocks generation-spec reapproval'
);
select is(
  (select content_factory_private.research_generation_spec_evidence_fresh(
     'c0100000-0000-4000-8000-000000000002',
     (state.approve_result #>> '{generation_spec,spec_id}')::uuid,
     (state.approve_result #>> '{generation_spec,spec_version}')::integer,
     state.approve_result #>> '{generation_spec,spec_hash}'
   )
   from correction_generation_state state),
  false,
  'the same immutable generation provenance is stale after source correction'
);
select is(
  (select count(*)::integer
   from correction_generation_state state
   join content_factory.generation_spec_approval_events event
     on event.organization_id =
       'c0100000-0000-4000-8000-000000000002'
    and event.spec_id =
      (state.approve_result #>> '{generation_spec,spec_id}')::uuid),
  1,
  'failed stale reapproval preserves the single immutable approval event'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    where task.creative_brief_draft_id =
        'c0100000-0000-4000-8000-000000000005'
      and task.status = 'cancelled'
      and task.result #>> '{research_evidence_stale,analysis_event_id}' = (
        select event.id::text
        from content_factory.research_source_analysis_events event
        join content_factory.research_category_source_ledger ledger
          on ledger.id = event.source_ledger_id
        join content_factory.product_research_sources source
          on source.id = ledger.source_id
        where source.metadata ->> 'model_source_id' = 'web:s5'
        order by event.analysis_version desc
        limit 1
      )
  ),
  'source correction cancels actionable tasks while preserving stale lineage'
);

update correction_generation_state state
set stale_start_result = public.system_update_real_generation(
  jsonb_build_object(
    'job_id', state.start_result #>> '{job,id}',
    'status', 'starting'
  )
);
select ok(
  (select stale_start_result -> 'ok' = 'false'::jsonb
     and stale_start_result -> 'terminal' = 'true'::jsonb
     and stale_start_result -> 'retryable' = 'false'::jsonb
     and stale_start_result ->> 'code' =
       'generation_spec_provider_start_stale'
     and stale_start_result #>> '{job,status}' = 'failed'
     and stale_start_result #>> '{job,failure_code}' =
       'generation_spec_provider_start_stale'
   from correction_generation_state),
  'queued paid work fails closed before provider start after source correction'
);
select ok(
  (select count(*) = 2
     and count(*) filter (where ledger.event_type = 'reserved') = 1
     and count(*) filter (where ledger.event_type = 'released') = 1
     and sum(ledger.reserved_delta_minor) = 0
     and sum(ledger.committed_delta_minor) = 0
   from content_factory.generation_spend_ledger ledger
   where ledger.generation_job_id = (
     select (start_result #>> '{job,id}')::uuid
     from correction_generation_state
   )),
  'pre-provider source staleness releases the full reservation with zero spend'
);
select is(
  (select count(*)::integer
   from content_factory.factory_events event
   where event.entity_id = (
     select start_result #>> '{job,id}'
     from correction_generation_state
   )
     and event.event_name = 'real_generation_starting'),
  0,
  'source correction emits no provider-start event'
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

-- Starting a separate research run is the append-only recovery path for an
-- immutable approved snapshot. It inherits the corrected canonical head and
-- can be reviewed/approved without mutating the old run.
insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
)
select
  'c0100000-0000-4000-8000-000000000040', organization_id, product_id,
  created_by, 'completed', jsonb_build_object(
    'objective', 'Append-only recovery after source-analysis correction.',
    'marketplace_url', null,
    'source_media_ids', jsonb_build_array(
      'c0100000-0000-4000-8000-000000000006'
    ),
    'platforms', jsonb_build_array('youtube')
  ), summary, repeat('c', 64), repeat('d', 64),
  'category-readiness-recovery-run', now()
from content_factory.product_research_runs
where id = 'c0100000-0000-4000-8000-000000000004';
insert into content_factory.product_research_sources (
  organization_id, run_id, product_id, created_by, source_type, source_url,
  media_object_id, title, content_hash, trust_level, extracted_facts,
  metadata, fetched_at, published_at, created_at
)
select source.organization_id,
  'c0100000-0000-4000-8000-000000000040', source.product_id,
  source.created_by, source.source_type, source.source_url,
  source.media_object_id, source.title, source.content_hash,
  source.trust_level, source.extracted_facts, source.metadata,
  source.fetched_at, source.published_at, clock_timestamp()
from content_factory.product_research_sources source
where source.run_id = 'c0100000-0000-4000-8000-000000000004'
  and source.metadata ->> 'model_source_id' ~ '^web:s([1-9]|[12][0-9]|30)$'
order by source.created_at, source.id;
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash
)
select
  'c0100000-0000-4000-8000-000000000042', run.organization_id, run.id,
  run.product_id, run.created_by, 'human', 1, 'draft',
  'Recovered canonical evidence draft', run.summary,
  source_set.source_ids,
  jsonb_build_array(jsonb_build_object(
    'title', 'Review recovered canonical evidence',
    'instructions', 'Use the corrected source interpretation in this run.'
  )),
  content_factory_private.json_hash(jsonb_build_object(
    'title', 'Recovered canonical evidence draft',
    'brief', run.summary,
    'source_ids', source_set.source_ids,
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'Review recovered canonical evidence',
      'instructions', 'Use the corrected source interpretation in this run.'
    ))
  ))
from content_factory.product_research_runs run
cross join lateral (
  select jsonb_agg(source.id order by source.created_at, source.id)
    as source_ids
  from content_factory.product_research_sources source
  where source.organization_id = run.organization_id
    and source.run_id = run.id
) source_set
where run.id = 'c0100000-0000-4000-8000-000000000040';
select is(
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000040',
    'c0100000-0000-4000-8000-000000000042'
  ),
  true,
  'a new recovery run is fresh against inherited corrected canonical heads'
);
select is(
  (select event.origin
   from content_factory.product_research_sources source
   join lateral (
     select binding.*
     from content_factory.research_draft_source_analysis_bindings binding
     where binding.run_id = source.run_id
       and binding.draft_id = 'c0100000-0000-4000-8000-000000000042'
       and binding.source_id = source.id
     order by binding.binding_version desc, binding.id desc
     limit 1
   ) exact_binding on true
   join content_factory.research_source_analysis_events event
     on event.id = exact_binding.analysis_event_id
   where source.run_id = 'c0100000-0000-4000-8000-000000000040'
     and source.metadata ->> 'model_source_id' = 'web:s5'),
  'human_correction',
  'the recovery run inherits the exact human-corrected source head'
);
select lives_ok(
  $$
    select public.creator_approve_creative_brief(jsonb_build_object(
      'organization_id', 'c0100000-0000-4000-8000-000000000002',
      'idempotency_key', 'category-readiness-recovery-approval',
      'draft_id', 'c0100000-0000-4000-8000-000000000042'
    ))
  $$,
  'the new evidence-complete recovery draft can be explicitly approved'
);
select is(
  (select count(*)::integer
   from content_factory.creator_tasks task
   where task.creative_brief_draft_id =
       'c0100000-0000-4000-8000-000000000042'
     and task.status = 'todo'),
  1,
  'recovery approval creates one actionable task only while evidence is fresh'
);

select lives_ok(
  $parser_v2$
    select public.system_record_research_source_analysis(
      jsonb_build_object(
        'organization_id', 'c0100000-0000-4000-8000-000000000002',
        'source_ledger_id', head.source_ledger_id,
        'expected_head_event_id', head.id,
        'expected_head_hash', head.event_hash,
        'parser_key', 'automatic_social_semantic_parser',
        'parser_version', '2.0.0',
        'analysis', head.analysis || jsonb_build_object(
          'summary',
            'Parser v2 conservatively revalidated the same uncited source.'
        ),
        'idempotency_key', 'category-readiness-parser-v2-upgrade'
      )
    )
    from (
      select event.id, event.event_hash, event.source_ledger_id,
        event.analysis
      from content_factory.research_source_analysis_events event
      join content_factory.research_category_source_ledger ledger
        on ledger.id = event.source_ledger_id
      join content_factory.product_research_sources source
        on source.id = ledger.source_id
      where source.metadata ->> 'model_source_id' = 'web:s4'
      order by event.analysis_version desc
      limit 1
    ) head
  $parser_v2$,
  'a newer automatic parser can append an exact semantic head'
);
select is(
  (select event.origin || ':' || event.parser_version || ':'
      || event.analysis_version::text
   from content_factory.research_source_analysis_events event
   join content_factory.research_category_source_ledger ledger
     on ledger.id = event.source_ledger_id
   join content_factory.product_research_sources source
     on source.id = ledger.source_id
   where source.metadata ->> 'model_source_id' = 'web:s4'
   order by event.analysis_version desc limit 1),
  'system_parser:2.0.0:2',
  'the parser-v2 event becomes the full semantic source head'
);
select is(
  (select count(*)::integer
   from content_factory.research_stage_head_events stage_event
   where stage_event.command_id = (
     select event.id
     from content_factory.research_source_analysis_events event
     join content_factory.research_category_source_ledger ledger
       on ledger.id = event.source_ledger_id
     join content_factory.product_research_sources source
       on source.id = ledger.source_id
     where source.metadata ->> 'model_source_id' = 'web:s4'
     order by event.analysis_version desc limit 1
   )
     and stage_event.run_id = 'c0100000-0000-4000-8000-000000000040'
     and stage_event.action = 'dependency_refresh'
     and stage_event.state = 'stale_dependency'),
  7,
  'a parser-v2 semantic change invalidates every dependent governed stage'
);
select is(
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000040',
    'c0100000-0000-4000-8000-000000000042'
  ),
  false,
  'parser v2 makes the previously fresh recovery draft stale'
);
select ok(
  exists (
    select 1
    from content_factory.creator_tasks task
    where task.creative_brief_draft_id =
        'c0100000-0000-4000-8000-000000000042'
      and task.status = 'cancelled'
      and task.result #>> '{research_evidence_stale,analysis_event_id}' = (
        select event.id::text
        from content_factory.research_source_analysis_events event
        join content_factory.research_category_source_ledger ledger
          on ledger.id = event.source_ledger_id
        join content_factory.product_research_sources source
          on source.id = ledger.source_id
        where source.metadata ->> 'model_source_id' = 'web:s4'
        order by event.analysis_version desc
        limit 1
      )
  ),
  'parser-v2 invalidation cancels the recovered draft task before downstream use'
);

insert into content_factory.product_research_runs (
  id, organization_id, product_id, created_by, status, input, summary,
  request_hash, completion_hash, idempotency_key, finished_at
)
select
  'c0100000-0000-4000-8000-000000000050', organization_id, product_id,
  created_by, 'completed', input, summary, repeat('e', 64), repeat('f', 64),
  'category-readiness-partial-ledger-run', now()
from content_factory.product_research_runs
where id = 'c0100000-0000-4000-8000-000000000004';
insert into content_factory.product_research_sources (
  organization_id, run_id, product_id, created_by, source_type, source_url,
  media_object_id, title, content_hash, trust_level, extracted_facts,
  metadata, fetched_at, published_at, created_at
)
select source.organization_id,
  'c0100000-0000-4000-8000-000000000050', source.product_id,
  source.created_by, source.source_type, source.source_url,
  source.media_object_id, source.title, source.content_hash,
  source.trust_level, source.extracted_facts, source.metadata,
  source.fetched_at, source.published_at, clock_timestamp()
from content_factory.product_research_sources source
where source.run_id = 'c0100000-0000-4000-8000-000000000004'
  and source.metadata ->> 'model_source_id' ~ '^web:s([1-9]|[12][0-9]|30)$'
order by source.created_at, source.id;
insert into content_factory.product_research_sources (
  id, organization_id, run_id, product_id, created_by, source_type,
  source_url, title, content_hash, trust_level, extracted_facts, metadata,
  fetched_at
) values (
  'c0100000-0000-4000-8000-000000000051',
  'c0100000-0000-4000-8000-000000000002',
  'c0100000-0000-4000-8000-000000000050',
  'c0100000-0000-4000-8000-000000000003',
  'c0100000-0000-4000-8000-000000000001',
  'market_data', 'https://example.test/unregistered-category-source',
  'Unregistered category evidence', repeat('9', 64), 'public',
  '[]'::jsonb, jsonb_build_object('model_source_id', 'web:unregistered'),
  now()
);
insert into content_factory.creative_brief_drafts (
  id, organization_id, run_id, product_id, created_by, origin, version,
  status, title, brief, source_ids, task_blueprint, content_hash
)
select
  'c0100000-0000-4000-8000-000000000052', run.organization_id, run.id,
  run.product_id, run.created_by, 'human', 1, 'draft',
  'Incomplete ledger evidence draft', run.summary,
  source_set.source_ids,
  jsonb_build_array(jsonb_build_object(
    'title', 'This task must never become actionable',
    'instructions', 'The exact source is not registered in the category ledger.'
  )),
  content_factory_private.json_hash(jsonb_build_object(
    'title', 'Incomplete ledger evidence draft',
    'brief', run.summary,
    'source_ids', source_set.source_ids,
    'task_blueprint', jsonb_build_array(jsonb_build_object(
      'title', 'This task must never become actionable',
      'instructions',
        'The exact source is not registered in the category ledger.'
    ))
  ))
from content_factory.product_research_runs run
cross join lateral (
  select jsonb_agg(source.id order by source.created_at, source.id)
    as source_ids
  from content_factory.product_research_sources source
  where source.organization_id = run.organization_id
    and source.run_id = run.id
) source_set
where run.id = 'c0100000-0000-4000-8000-000000000050';
select is(
  content_factory_private.research_draft_source_analysis_fresh(
    'c0100000-0000-4000-8000-000000000002',
    'c0100000-0000-4000-8000-000000000050',
    'c0100000-0000-4000-8000-000000000052'
  ),
  false,
  'a category-bound draft with partial canonical ledger coverage fails closed'
);
select throws_ok(
  $$
    select public.creator_approve_creative_brief(jsonb_build_object(
      'organization_id', 'c0100000-0000-4000-8000-000000000002',
      'idempotency_key', 'category-readiness-partial-ledger-approval',
      'draft_id', 'c0100000-0000-4000-8000-000000000052'
    ))
  $$,
  '55000',
  'research_draft_source_analysis_incomplete_or_stale',
  'incomplete canonical coverage blocks approval and task creation'
);
select is(
  (select count(*)::integer
   from content_factory.creator_tasks task
   where task.creative_brief_draft_id =
       'c0100000-0000-4000-8000-000000000052'),
  0,
  'failed incomplete-ledger approval leaves no actionable task'
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
create temporary table deterministic_source_status on commit drop as
select case when exists (
  select 1
  from content_factory.research_product_market_category_bindings binding
  where binding.organization_id =
      'c0100000-0000-4000-8000-000000000002'
    and binding.product_id = 'c0100000-0000-4000-8000-000000000003'
) then public.creator_research_category_learning_status(jsonb_build_object(
    'organization_id', 'c0100000-0000-4000-8000-000000000002',
    'run_id', 'c0100000-0000-4000-8000-000000000004'
  )) else '{}'::jsonb end value;
select is(
  (select count(*)::integer
   from content_factory.research_product_market_category_bindings binding
   where binding.organization_id =
       'c0100000-0000-4000-8000-000000000002'
     and binding.product_id = 'c0100000-0000-4000-8000-000000000003'),
  1,
  'canonical product category binding survives cross-run source reuse'
);
select is(
  (select item.value ->> 'title'
   from deterministic_source_status status,
        jsonb_array_elements(status.value #> '{source_ledger,items}') item(value)
   where item.value ->> 'source_url' = 'https://example.test/category-source/5'),
  'DO_NOT_COPY_NEW_CONTENT_VERSION',
  'status deterministically selects the newest same-URL content version'
);
select is(
  (select item.value -> 'current_analysis'
   from deterministic_source_status status,
        jsonb_array_elements(status.value #> '{source_ledger,items}') item(value)
   where item.value ->> 'source_url' = 'https://example.test/category-source/5'),
  'null'::jsonb,
  'a superseded parser head is not presented as analysis of newer content'
);
select is(
  (select jsonb_array_length(item.value -> 'lineage_history')
   from deterministic_source_status status,
        jsonb_array_elements(status.value #> '{source_ledger,items}') item(value)
   where item.value ->> 'source_url' = 'https://example.test/category-source/5'),
  2,
  'both same-URL content versions remain visible in immutable lineage history'
);

-- Current retention-bound YouTube metadata affects source volume/platform
-- coverage without ever being copied into the durable source ledger.  Raw,
-- unconfirmed videos must not manufacture competitor or analysis credit.
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
  1,
  'unconfirmed retained channels add no competitor credit beside one durable competitor'
);
select is(
  (select (dimension.value ->> 'current')::integer
   from readiness_same_channel snapshot,
        jsonb_array_elements(snapshot.value -> 'dimensions') dimension(value)
   where dimension.value ->> 'key' = 'analysis_coverage'),
  23,
  'raw retained YouTube metadata does not count as structured source analysis; the superseded content version has no current parser head'
);
select is(
  (select value ->> 'definition_version' from readiness_same_channel),
  'category-evidence-readiness-v3',
  'truthful YouTube semantics and parser heads are isolated in readiness definition v3'
);
select is(
  (select count(*)::integer
   from content_factory.research_category_source_ledger ledger
   where ledger.source_url like 'https://www.youtube.com/watch?v=%'),
  0,
  'retention-bound YouTube observations are never copied to durable lineage'
);

-- A fourth video uses a second channel.  Excluding an unconfirmed candidate
-- may remove raw volume, but cannot remove semantic credit it never received.
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
select is(
  (select (readiness.value ->> 'score')::integer
   from (select content_factory_private.research_category_evidence_readiness(
     'c0100000-0000-4000-8000-000000000002',
     (select binding.category_id
      from content_factory.research_product_market_category_bindings binding
      where binding.product_id = 'c0100000-0000-4000-8000-000000000003'
      order by binding.binding_version desc limit 1),
     clock_timestamp()
   ) value) readiness),
  (select (value ->> 'score')::integer from readiness_before_exclusion),
  'excluding an unconfirmed saturated-volume candidate removes no invented semantic score'
);

insert into content_factory.research_youtube_candidate_decisions (
  organization_id, ingestion_id, observation_id, observation_hash, decision,
  reason, decided_by, retention_expires_at, idempotency_key, decision_hash
)
select observation.organization_id, observation.ingestion_id, observation.id,
  observation.observation_hash, 'confirm_candidate',
  'Human confirmed one bounded competitor candidate',
  'c0100000-0000-4000-8000-000000000001',
  now() + interval '29 days', 'category-readiness-confirm-video-1',
  content_factory_private.json_hash(jsonb_build_object(
    'youtube_runtime_confirmation', observation.id
  ))
from content_factory.research_youtube_video_observations observation
where observation.video_id = 'AAAAAAA0001';
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
   where dimension.value ->> 'key' = 'competitor_observations'),
  2,
  'one human-confirmed YouTube channel adds one deduplicated competitor observation'
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
   where dimension.value ->> 'key' = 'human_validation'),
  1,
  'a confirmed YouTube candidate adds one human-validation credit without analysis credit'
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
