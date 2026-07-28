begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(15);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    '[]'::jsonb
  ),
  true,
  'a generation may correctly have no learned QA guards'
);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    jsonb_build_array(
      'product_fidelity',
      'technical_stability',
      'visual_quality'
    )
  ),
  true,
  'three allowlisted visual QA guards are accepted'
);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    jsonb_build_array('audio_quality', 'speech_fidelity')
  ),
  true,
  'specialized audio and speech QA guards are accepted'
);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    jsonb_build_array('raw_review_comment')
  ),
  false,
  'review copy cannot become an applied QA guard'
);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    jsonb_build_array('trust', 'trust')
  ),
  false,
  'duplicate applied QA guards fail closed'
);

select is(
  content_factory_private.valid_generation_quality_guard_codes(
    jsonb_build_array(
      'product_fidelity',
      'technical_stability',
      'hook_clarity',
      'visual_quality'
    )
  ),
  false,
  'applied QA guard lineage remains bounded to three'
);

select ok(
  to_regclass(
    'content_factory.generation_quality_guard_lineage'
  ) is not null,
  'the immutable QA guard lineage table exists'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'generation_quality_guard_lineage'
  ),
  'QA guard lineage keeps RLS enabled'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.generation_quality_guard_lineage',
    'select'
  ),
  false,
  'browser users cannot read QA guard lineage directly'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.generation_quality_guard_lineage',
    'insert'
  ),
  false,
  'browser users cannot forge QA guard lineage'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'generation_quality_guard_lineage'
      and trigger_row.tgname =
        'generation_quality_guard_lineage_append_only'
      and not trigger_row.tgisinternal
  ),
  'QA guard lineage is append-only'
);

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null,
  'the paid-generation RPC remains available'
);

select ok(
  exists (
    select 1
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname = 'creator_start_real_generation'
      and function_row.prosecdef
  ),
  'the final paid-generation wrapper remains SECURITY DEFINER'
);

select is(
  has_function_privilege(
    'authenticated',
    'public.creator_start_real_generation(jsonb)',
    'execute'
  ),
  true,
  'authenticated callers can execute the final paid-generation RPC'
);

select is(
  has_function_privilege(
    'authenticated',
    'content_factory_private.creator_start_real_generation_pre_guard_lineage_v8(jsonb)',
    'execute'
  ),
  false,
  'the prior complete paid command is private'
);

select * from finish();
rollback;
