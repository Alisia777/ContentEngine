begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(19);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    '[]'::jsonb,
    '{}'::jsonb
  ),
  true,
  'an empty guard profile is valid'
);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    '[]'::jsonb,
    null::jsonb
  ),
  false,
  'a SQL-null guard profile fails closed'
);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    jsonb_build_array('product_fidelity', 'visual_quality'),
    jsonb_build_object('product_fidelity', 1, 'visual_quality', 2)
  ),
  true,
  'each allowlisted guard can bind one bounded variant'
);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    jsonb_build_array('product_fidelity'),
    '{}'::jsonb
  ),
  false,
  'a missing guard variant fails closed'
);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    jsonb_build_array('product_fidelity'),
    jsonb_build_object('product_fidelity', 1, 'trust', 1)
  ),
  false,
  'an extra guard variant fails closed'
);

select is(
  content_factory_private.valid_generation_quality_guard_variants(
    jsonb_build_array('product_fidelity'),
    jsonb_build_object('product_fidelity', 3)
  ),
  false,
  'a third unreviewed prompt variant cannot enter the policy'
);

select is(
  content_factory_private.generation_quality_guard_requirement(
    'product_fidelity',
    1,
    'seedream5_lite'
  ),
  'QA: точная геометрия, этикетка, текст, цвет и пропорции.',
  'variant 1 remains backward compatible'
);

select is(
  content_factory_private.generation_quality_guard_requirement(
    'product_fidelity',
    2,
    'seedream5_lite'
  ),
  'QA+: один товар строго по исходнику; не изменять ни одну букву, край, цвет или пропорцию упаковки.',
  'photo variant 2 is the exact stronger canonical instruction'
);

select is(
  content_factory_private.generation_quality_guard_requirement(
    'audio_quality',
    2,
    'seedance2_fast'
  ),
  'QA+: непрерывная разборчивая дорожка; без тишины, клиппинга, шума и рассинхронизации.',
  'Seedance variant 2 has an exact stronger audio instruction'
);

select is(
  content_factory_private.generation_quality_guard_requirement(
    'audio_quality',
    2,
    'gen4_turbo'
  ),
  null::text,
  'Gen4 cannot accept an audio guard variant'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', jsonb_build_array('concise'),
      'quality_guard_codes',
        jsonb_build_array('product_fidelity'),
      'quality_guard_variants',
        jsonb_build_object('product_fidelity', 2)
    ),
    'gen4_turbo'
  ),
  array[
    'Обученное направление: товар главный во всех кадрах.',
    'Структурный hook: простой первый кадр сразу показывает товар.',
    'QA+: один точный товар по исходнику; упаковка, этикетка, текст, цвет и пропорции неизменны в каждом кадре.'
  ]::text[],
  'the database binds variant 2 into the exact provider prompt'
);

select is(
  content_factory_private.generation_quality_guard_effectiveness(
    'fa000000-0000-4000-8000-000000000001',
    'fa000000-0000-4000-8000-000000000002',
    'wildberries',
    'gen4_turbo',
    'product_fidelity',
    '2026-07-28T12:00:00Z'::timestamptz
  ) ->> 'status',
  'collecting_variant_1',
  'a scope without outcomes starts on bounded variant 1'
);

select ok(
  to_regclass(
    'content_factory.generation_learning_policy_snapshots'
  ) is not null,
  'the structural policy snapshot table exists'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname =
        'generation_learning_policy_snapshots'
  ),
  'policy snapshots keep RLS enabled'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.generation_learning_policy_snapshots',
    'select'
  ),
  false,
  'browser users cannot read structural policy snapshots directly'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname =
        'generation_learning_policy_snapshots'
      and trigger_row.tgname =
        'generation_learning_policy_snapshot_append_only'
      and not trigger_row.tgisinternal
  ),
  'policy snapshots are append-only'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_generation_learning_policy_rejection_v6(jsonb)'
  ) is not null,
  'the complete v6 policy remains private underneath effectiveness'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_policy_snapshot_v9(jsonb)'
  ) is not null,
  'the complete paid command remains private underneath snapshots'
);

select ok(
  exists (
    select 1
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname =
        'creator_generation_learning_policy'
      and function_row.prosecdef
  ),
  'the final learning policy remains SECURITY DEFINER'
);

select * from finish();
rollback;
