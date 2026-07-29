begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(12);

select has_table(
  'content_factory',
  'generation_review_autostart_consents',
  'durable generated-video QA consent table exists'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname =
        'generation_review_autostart_consents'
  ),
  'generated-video QA consent table has RLS enabled'
);

select ok(
  not has_table_privilege(
    'authenticated',
    'content_factory.generation_review_autostart_consents',
    'select'
  )
  and not has_table_privilege(
    'authenticated',
    'content_factory.generation_review_autostart_consents',
    'insert'
  ),
  'authenticated callers cannot read or forge consent rows'
);

select has_trigger(
  'content_factory',
  'generation_review_autostart_consents',
  'generation_review_autostart_consent_append_only',
  'generated-video QA consent is append-only'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_review_autostart_v11(jsonb)'
  ) is not null,
  'complete prior paid-start chain remains private'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_real_generation_status_pre_review_autostart_v2(jsonb)'
  ) is not null,
  'complete prior status chain remains private'
);

select ok(
  pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_category_learning_v14%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_category_learning_v14(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_single_reference_v13%'
  and pg_get_functiondef(
    'public.creator_start_real_generation_single_reference_v13(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_flexible_duration_v12%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_review_autostart_v11%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_review_autostart_v11(jsonb)'::regprocedure
  ) like '%creator_start_real_generation_pre_mode_prompt_v10%',
  'paid-start wrapper preserves every earlier validation layer'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  ) like '%generation_review_autostart_consent_invalid%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  ) like '%generated-video-qa-autostart-v1%'
  and pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_flexible_duration_v12(jsonb)'::regprocedure
  ) like '%''transcription_requested'', false%',
  'paid-start records only the exact no-transcription consent'
);

select ok(
  pg_get_functiondef(
    'public.creator_real_generation_status(jsonb)'::regprocedure
  ) like '%''{job,review_autostart_confirmed}''%'
  and pg_get_functiondef(
    'public.creator_real_generation_status(jsonb)'::regprocedure
  ) not like '%confirmed_by%',
  'status returns the bounded consent flag without actor identity'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname = 'creator_start_real_generation'
  ),
  'paid-start wrapper remains SECURITY DEFINER'
);

select ok(
  (
    select function_row.prosecdef
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname = 'creator_real_generation_status'
  ),
  'status wrapper remains SECURITY DEFINER'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_real_generation_pre_review_autostart_v11(jsonb)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'content_factory_private.creator_real_generation_status_pre_review_autostart_v2(jsonb)',
    'execute'
  ),
  'authenticated callers cannot bypass either public wrapper'
);

select * from finish();
rollback;
