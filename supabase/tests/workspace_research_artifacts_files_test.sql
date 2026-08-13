begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(13);

select has_function(
  'content_factory_private',
  'workspace_research_artifacts_projection',
  array['uuid', 'uuid', 'uuid'],
  'Files has a private Research artifact projection'
);

select ok(
  (select procedure.prosecdef and procedure.provolatile = 's'
   from pg_proc procedure
   where procedure.oid =
     'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure),
  'Research projection is stable and SECURITY DEFINER'
);

select ok(
  not has_function_privilege(
    'anon',
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)',
    'execute'
  ),
  'no browser or service role can execute the private projection directly'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'workspace_project_access_allowed') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'qualified_operator_project_research_allowed') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'qualified_operator_own_ai_research_receipt_allowed') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'run.created_by = p_profile_id') > 0,
  'project ACL plus qualification and own-run lineage bound operator reads'
);

select ok(
  lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )) !~ '\m(insert|update|delete|merge|truncate)\M'
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'summary') = 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'analysis_snapshot') = 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), 'folder_id') = 0,
  'Research projection cannot mutate ledgers or expose content/fake folders'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), '&receipt=') > 0
  and strpos(lower(pg_get_functiondef(
    'content_factory_private.workspace_research_artifacts_projection(uuid,uuid,uuid)'::regprocedure
  )), '&research_receipt=') = 0,
  'AI artifact deep links use the receipt route parameter'
);

select has_function(
  'public', 'creator_workspace_browser', array['jsonb'],
  'the exact-project Files reader remains public'
);

select ok(
  has_function_privilege(
    'authenticated', 'public.creator_workspace_browser(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon', 'public.creator_workspace_browser(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'service_role', 'public.creator_workspace_browser(jsonb)', 'execute'
  ),
  'only authenticated callers execute the public Files reader'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), 'workspace_artifact_classes_invalid') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), 'media.artifact_class = any(artifact_classes_value)') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), 'media.artifact_class = any(artifact_classes_value)')
    < strpos(lower(pg_get_functiondef(
      'public.creator_workspace_browser(jsonb)'::regprocedure
    )), 'candidates as materialized'),
  'strict provenance filtering happens before keyset pagination'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), 'coalesce(media.owner_id = user_id, false)') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), 'coalesce(task.assignee_id = user_id, false)') > 0,
  'per-item move authority matches manager and operator ownership rules'
);

select ok(
  strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), '''research_artifacts'', research_artifacts_value') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_workspace_browser(jsonb)'::regprocedure
  )), '''research''::text as entity_type') = 0,
  'Research artifacts remain a separate top-level projection'
);

select has_function(
  'content_factory_private',
  'creator_project_media_pre_files_v438',
  array['jsonb'],
  'the mature exact media reader is preserved privately'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.creator_project_media_pre_files_v438(jsonb)',
    'execute'
  )
  and strpos(lower(pg_get_functiondef(
    'public.creator_project_media(jsonb)'::regprocedure
  )), 'surface_value <> ''files''') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_project_media(jsonb)'::regprocedure
  )), 'creator_project_media_pre_files_v438(p_payload)') > 0
  and strpos(lower(pg_get_functiondef(
    'public.creator_project_media(jsonb)'::regprocedure
  )), '''workspace_item_key'', ''media:'' || media_id_value::text') > 0,
  'Files exact-media deep links wrap the mature reader without exposing its alias'
);

select * from finish();
rollback;
