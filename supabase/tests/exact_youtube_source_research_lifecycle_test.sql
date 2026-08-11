begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_function(
  'public', 'contentengine_exact_youtube_source_queue', array['jsonb'],
  'exact YouTube queue keeps its single rolling-safe browser RPC'
);

select ok(
  (select procedure.prosecdef
   from pg_proc procedure
   where procedure.oid =
     'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure),
  'the queue keeps its SECURITY DEFINER boundary'
);

select is(
  (select procedure.provolatile::text
   from pg_proc procedure
   where procedure.oid =
     'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure),
  'v',
  'the replacement preserves the existing queue volatility contract'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.contentengine_exact_youtube_source_queue(jsonb)', 'execute'
  )
  and has_function_privilege(
    'service_role',
    'public.contentengine_exact_youtube_source_queue(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.contentengine_exact_youtube_source_queue(jsonb)', 'execute'
  ),
  'only authenticated and service-role callers keep queue execution access'
);

select ok(
  to_regclass(
    'content_factory.exact_youtube_research_source_lifecycle_idx'
  ) is not null,
  'latest and effective lifecycle lookup has a source/attachment index'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''version'', ''exact-youtube-source-queue-v2''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''analysis_ready_is_media_ready'', true') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''research_lifecycle_projected'', true') > 0,
  'queue v2 is retained while media readiness and lifecycle are additive'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'require_workspace_project_access') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'binding.organization_id = source.organization_id') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'binding.project_id = source.project_id') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'binding.source_id = source.id') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'binding.attachment_id = attachment.id') > 0,
  'project ACL and exact source/attachment binding drive every lifecycle row'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'product_research_runs run') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'ai_research_evidence_receipts receipt') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'ai_research_evidence_dispositions disposition') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'ai_research_learning_selections selection') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'selection.project_id = binding.project_id') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'selection.run_id = binding.run_id') > 0,
  'run, completion receipt, review and learning selection are authoritatively joined'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'order by binding.bound_at desc, binding.id desc') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'order by selection.selected_at desc, selection.event_cursor desc') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''has_approved_recommendations''') > 0,
  'latest-run status and still-effective approved recommendations are independent axes'
);

select ok(
  (select bool_and(strpos(source, quote_literal(state)) > 0)
   from (
     select lower(pg_get_functiondef(
       'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
     )) as source
   ) function_source
   cross join unnest(array[
     'not_started',
     'analysis_in_progress',
     'analysis_failed',
     'completed_without_ai_receipt',
     'awaiting_learning_selection',
     'recommendations_ready',
     'excluded'
   ]) as states(state)),
  'the complete deterministic research lifecycle is projected'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''research_lifecycle_read_only'', true') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''research_lifecycle_starts_analysis'', false') > 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), '''research_lifecycle_starts_provider_call'', false') > 0
  and lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )) !~ '\m(insert|update|delete|merge|truncate)\M'
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'research_provider_attempt') = 0
  and strpos(lower(pg_get_functiondef(
    'public.contentengine_exact_youtube_source_queue(jsonb)'::regprocedure
  )), 'net.http') = 0,
  'reading lifecycle performs no mutation, analysis start or provider call'
);

select * from finish();
rollback;
