begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(20);

select ok(
  to_regclass(
    'content_factory.content_review_assignments'
  ) is not null,
  'generated-media review assignments are persisted'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_assignments'
  ),
  'review assignments keep RLS enabled'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.content_review_assignments',
    'select'
  ),
  'browser users cannot read raw reviewer identities'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.content_review_assignments',
    'insert'
  ),
  'browser users cannot assign their own reviews'
);

select ok(
  not has_table_privilege(
    'service_role',
    'content_factory.content_review_assignments',
    'select'
  ),
  'service role cannot bypass the privacy-minimized catalog'
);

select ok(
  to_regprocedure(
    'content_factory_private.assign_generated_media_review(uuid,uuid)'
  ) is not null,
  'private deterministic assignment resolver exists'
);

select ok(
  not has_function_privilege(
    'service_role',
    'content_factory_private.assign_generated_media_review(uuid,uuid)',
    'execute'
  ),
  'assignment resolver is not an application endpoint'
);

select ok(
  to_regprocedure(
    'content_factory_private.generated_media_reviewer_access_allowed(uuid,uuid)'
  ) is not null,
  'reviewer routing has a dedicated current-training predicate'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.generated_media_reviewer_access_allowed(uuid,uuid)',
    'execute'
  ),
  'browser users cannot probe another member training access'
);

select ok(
  to_regprocedure(
    'content_factory_private.generated_media_review_assignment_required(uuid,uuid)'
  ) is not null,
  'paid generated-media assignment requirement is explicit'
);

select ok(
  to_regprocedure(
    'content_factory_private.guard_content_review_assignment()'
  ) is not null,
  'immutable assignment guard exists'
);

select ok(
  to_regprocedure(
    'content_factory_private.guard_generated_media_review_assignment_decision()'
  ) is not null,
  'decision assignment guard exists'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row
      on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_decisions'
      and trigger_row.tgname =
        'guard_generated_media_review_assignment_decision'
      and not trigger_row.tgisinternal
  ),
  'only the assigned independent reviewer may decide'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row
      on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_runs'
      and trigger_row.tgname =
        'route_completed_generated_media_review'
      and not trigger_row.tgisinternal
  ),
  'completed generated review is routed automatically'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row
      on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'content_review_decisions'
      and trigger_row.tgname =
        'complete_content_review_assignment'
      and not trigger_row.tgisinternal
  ),
  'immutable human decision completes the assignment'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_content_review_catalog'
  ),
  'privacy-minimized review catalog remains SECURITY DEFINER'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'authenticated members keep review-catalog access'
);

select ok(
  not has_function_privilege(
    'anon',
    'public.creator_content_review_catalog(jsonb)',
    'execute'
  ),
  'anonymous callers cannot read assignment routing'
);

select is(
  content_factory_private.generated_media_reviewer_access_allowed(
    '00000000-0000-4000-8000-000000000090'::uuid,
    '00000000-0000-4000-8000-000000000091'::uuid
  ),
  false,
  'missing member is never an eligible reviewer'
);

select is(
  content_factory_private.assign_generated_media_review(
    '00000000-0000-4000-8000-000000000090'::uuid,
    '00000000-0000-4000-8000-000000000091'::uuid
  ),
  null::uuid,
  'missing review produces no synthetic assignment'
);

select * from finish();
rollback;
