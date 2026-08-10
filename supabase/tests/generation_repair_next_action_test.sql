begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(9);

select ok(
  to_regprocedure(
    'content_factory_private.generated_media_repair_next_action(uuid,uuid,uuid,text)'
  ) is not null,
  'private repair next-action resolver exists'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.generated_media_repair_next_action(uuid,uuid,uuid,text)',
    'execute'
  ),
  'browser users cannot probe repair actions outside the catalog'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.generated_media_repair_next_action(uuid,uuid,uuid,text)',
    'execute'
  ),
  'service role does not receive a new repair endpoint'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_content_review_catalog_without_repair_actions(jsonb)'
  ) is not null,
  'assignment-aware catalog is preserved privately'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname = 'creator_content_review_catalog'
  ),
  'repair-aware catalog remains SECURITY DEFINER'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'authenticated workspace members retain catalog access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'anonymous callers cannot read repair routing'
);

select is(
  content_factory_private.generated_media_repair_next_action(
    '00000000-0000-4000-8000-000000000090'::uuid,
    '00000000-0000-4000-8000-000000000091'::uuid,
    '00000000-0000-4000-8000-000000000092'::uuid,
    'owner'
  ),
  null::jsonb,
  'a forged current-user argument produces no routing state'
);

select ok(
  (
    select lower(pg_get_functiondef(
      'content_factory_private.creator_content_review_catalog_pre_project_v47(jsonb)'::regprocedure
    ))
  ) like '%repair_next_action%'
  and pg_get_functiondef(
    'content_factory_private.creator_content_review_catalog_pre_media_status(jsonb)'::regprocedure
  ) like '%creator_content_review_catalog_pre_project_v47%'
  and pg_get_functiondef(
    'public.creator_content_review_catalog(jsonb)'::regprocedure
  ) like '%creator_content_review_catalog_pre_media_status%',
  'public catalog preserves the privacy-minimized repair action through the status wrapper'
);

select * from finish();
rollback;
