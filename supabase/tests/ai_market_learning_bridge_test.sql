begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_function(
  'public', 'creator_ai_learning_market_scope_index', array['jsonb'],
  'dynamic AI market-category scope index exists'
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
  )), 'ai_category_knowledge_sources') = 0,
  'the index delegates readiness to the research evidence ledger'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'creator_generation_learning_policy_pre_ai_control_room_v8') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_generation_learning_policy(jsonb)'::regprocedure
  )), 'ai_effective_category_policies') = 0,
  'legacy static teaching cannot alter the current generation policy'
);

select is(
  (select procedure.provolatile::text
   from pg_proc procedure
   where procedure.oid =
     'public.creator_generation_learning_policy(jsonb)'::regprocedure),
  'v',
  'the generation policy wrapper preserves the audited VOLATILE contract'
);

select ok(
  (select procedure.prosecdef
   from pg_proc procedure
   where procedure.oid =
     'public.creator_generation_learning_policy(jsonb)'::regprocedure),
  'the generation policy wrapper keeps its SECURITY DEFINER boundary'
);

select * from finish();
rollback;
