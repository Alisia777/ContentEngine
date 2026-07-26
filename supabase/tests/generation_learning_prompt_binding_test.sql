begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(8);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'demonstration',
      'preferred_hook_patterns', jsonb_build_array('demonstration'),
      'quality_guard_codes',
        jsonb_build_array('product_fidelity', 'technical_stability')
    ),
    'seedance2_fast'
  ),
  array[
    'Обученное направление: одно видимое действие с товаром.',
    'Структурный hook: одно простое действие с товаром.',
    'QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.',
    'QA: стабильный проход без чёрных кадров, скачков и мерцания.'
  ]::text[],
  'video policy resolves to the exact angle, hook and QA prompt fragments'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'trust_builder',
      'preferred_hook_patterns', jsonb_build_array('comparison'),
      'quality_guard_codes',
        jsonb_build_array('visual_quality', 'platform_fit')
    ),
    'seedream5_lite'
  ),
  array[
    'Обученный ракурс: естественная предметная подача.',
    'QA: чистые края без дублей, деформаций и AI-артефактов.',
    'QA: мастер 1:1, безопасные поля.'
  ]::text[],
  'photo policy excludes video hook copy and keeps exact photo QA guards'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'raw_untrusted_angle',
      'preferred_hook_patterns', '[]'::jsonb,
      'quality_guard_codes', '[]'::jsonb
    ),
    'gen4_turbo'
  ),
  null::text[],
  'an unallowlisted learned angle cannot produce prompt requirements'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', '[]'::jsonb,
      'quality_guard_codes', jsonb_build_array('raw_review_copy')
    ),
    'gen4_turbo'
  ),
  null::text[],
  'raw or unknown review material cannot become a QA prompt guard'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', true,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', '[]'::jsonb,
      'quality_guard_codes',
        jsonb_build_array('product_fidelity', 'product_fidelity')
    ),
    'gen4_turbo'
  ),
  null::text[],
  'duplicated guard codes are rejected instead of silently normalized'
);

select is(
  content_factory_private.generation_learning_prompt_requirements(
    jsonb_build_object(
      'applied', false,
      'preferred_angle', 'product_focus',
      'preferred_hook_patterns', '[]'::jsonb,
      'quality_guard_codes', '[]'::jsonb
    ),
    'gen4_turbo'
  ),
  null::text[],
  'an unapplied policy cannot add learned provider instructions'
);

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null,
  'the authenticated paid-generation RPC remains available'
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
  'the final prompt-binding wrapper remains SECURITY DEFINER'
);

select * from finish();
rollback;
