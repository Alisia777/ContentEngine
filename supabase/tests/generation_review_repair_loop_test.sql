begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(12);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array(
      'product_fidelity',
      'technical_stability',
      'hook_clarity'
    ),
    'seedance2_fast'
  ),
  array[
    'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.',
    'QA: стабильный проход без чёрных кадров, скачков и мерцания.',
    'QA: точный товар и одно действие видны в первые 2 секунды.'
  ]::text[],
  'video repair uses only exact canonical QA fragments'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('visual_quality', 'trust', 'platform_fit'),
    'seedream5_lite'
  ),
  array[
    'QA: чистые края без дублей, деформаций и AI-артефактов.',
    'QA: естественные материалы, свет и масштаб.',
    'QA: мастер 1:1, безопасные поля.'
  ]::text[],
  'photo repair uses the exact photo-specific QA fragments'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('raw_review_comment'),
    'gen4_turbo'
  ),
  null::text[],
  'raw review copy cannot become a repair requirement'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array('trust', 'trust'),
    'seedance2_fast'
  ),
  null::text[],
  'duplicate repair guards fail closed'
);

select is(
  content_factory_private.generation_repair_prompt_requirements(
    jsonb_build_array(
      'product_fidelity',
      'technical_stability',
      'hook_clarity',
      'visual_quality'
    ),
    'seedance2_fast'
  ),
  null::text[],
  'repair guard count is bounded to three'
);

select ok(
  to_regprocedure(
    'public.creator_generation_repair_policy(jsonb)'
  ) is not null,
  'the authenticated repair-policy RPC is available'
);

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null,
  'the paid-generation RPC remains available'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_repair_v6(jsonb)'
  ) is not null,
  'the prior paid implementation is private behind the repair wrapper'
);

select ok(
  exists (
    select 1
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname = 'creator_generation_repair_policy'
      and function_row.prosecdef
  ),
  'the repair policy is SECURITY DEFINER'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'generation_repair_signals'
  ),
  'repair provenance keeps RLS enabled'
);

select is(
  has_table_privilege(
    'authenticated',
    'content_factory.generation_repair_signals',
    'select'
  ),
  false,
  'browser users cannot read repair provenance directly'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    join pg_class table_row on table_row.oid = trigger_row.tgrelid
    join pg_namespace namespace_row
      on namespace_row.oid = table_row.relnamespace
    where namespace_row.nspname = 'content_factory'
      and table_row.relname = 'generation_repair_signals'
      and trigger_row.tgname = 'generation_repair_signal_append_only'
      and not trigger_row.tgisinternal
  ),
  'repair provenance is append-only'
);

select * from finish();
rollback;
