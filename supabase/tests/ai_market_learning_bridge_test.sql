begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_function(
  'public', 'creator_ai_learning_market_scope_index', array['jsonb'],
  'dynamic AI market-category scope index exists'
);
select has_function(
  'content_factory_private',
  'creator_generation_learning_policy_pre_project_v47',
  array['jsonb'],
  'the project-scoped learning policy keeps its private delegate'
);

select is(
  (select procedure.provolatile::text
   from pg_proc procedure
   where procedure.oid =
     'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure),
  's',
  'the market scope index is declared STABLE and read-only'
);

select ok(
  (select procedure.prosecdef
   from pg_proc procedure
   where procedure.oid =
     'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure),
  'the market scope index keeps its SECURITY DEFINER boundary'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_ai_learning_market_scope_index(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.creator_ai_learning_market_scope_index(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role',
    'public.creator_ai_learning_market_scope_index(jsonb)', 'execute'
  ),
  'the market scope index is an authenticated creator boundary only'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
  )), 'research_category_evidence_readiness') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
  )), 'require_workspace_project') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
  )), 'source_run.project_id = project_id_value') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
  )), 'source_run.project_id = project_id_value')
    < strpos(lower(pg_get_functiondef(
      'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
    )), 'bounded_bindings as')
  and (
    select count(*)
    from regexp_matches(
      lower(pg_get_functiondef(
        'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
      )),
      'source_run\.project_id = project_id_value',
      'g'
    )
  ) = 3
  and strpos(lower(pg_get_functiondef(
    'public.creator_ai_learning_market_scope_index(jsonb)'::regprocedure
  )), 'ai_category_knowledge_sources') = 0,
  'the index project-filters exact source runs before latest-binding selection'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_advisory_v9') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'advisory_generation_allowed') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_advisory_v9(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_historical_case_v1') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_ai_control_room_v8') = 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'::regprocedure
  )), 'call_project_scoped_v47') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_project_v47') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'::regprocedure
  )), 'project_payload_from_context_v47') > 0
  and strpos(regexp_replace(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_historical_case_v1(jsonb)'::regprocedure
  )), '[[:space:]]+', ' ', 'g'), '''media'', ''media_id'', false') > 0,
  'the advisory learning policy preserves exact project-scoped dispatch through the historical wrapper'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_ai_control_room_v8') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure
  )), 'ai_effective_category_policies') > 0,
  'the private project delegate reapplies confirmed teaching policies over the audited v8 base'
);

select ok(
  not has_function_privilege(
    'anon',
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)',
    'execute'
  ),
  'the safe project delegate remains private to the SECURITY DEFINER dispatcher'
);

select is(
  (select procedure.provolatile::text
   from pg_proc procedure
   where procedure.oid =
     'public.creator_generation_learning_policy(jsonb)'::regprocedure),
  'v',
  'the public project policy wrapper preserves the audited VOLATILE contract'
);

select ok(
  (select procedure.prosecdef
   from pg_proc procedure
   where procedure.oid =
     'public.creator_generation_learning_policy(jsonb)'::regprocedure),
  'the public project policy wrapper keeps its SECURITY DEFINER boundary'
);

select is(
  (select procedure.provolatile::text
   from pg_proc procedure
   where procedure.oid =
     'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure),
  'v',
  'the private safe policy delegate preserves the audited VOLATILE contract'
);

select ok(
  (select procedure.prosecdef
   from pg_proc procedure
   where procedure.oid =
     'content_factory_private.creator_generation_learning_policy_pre_project_v47(jsonb)'::regprocedure),
  'the private safe policy delegate keeps its SECURITY DEFINER boundary'
);

select * from finish();
rollback;
