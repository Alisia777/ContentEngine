begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(9);

select is(
  content_factory_private.generation_mode_prompt_requirements(
    'seedream5_lite'
  ),
  array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.',
    'Создай одно квадратное товарное фото 2048 × 2048.',
    'Используй @ProductReference как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали.',
    'Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.'
  ]::text[],
  'photo requirements bind the exact reference and text-safe square output'
);

select is(
  content_factory_private.generation_mode_prompt_requirements(
    'gen4_turbo'
  ),
  array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.',
    'Без речи, дикторского текста и сгенерированных надписей.'
  ]::text[],
  'Gen4 reusable requirements bind one silent output'
);

select is(
  content_factory_private.generation_mode_prompt_requirements(
    'seedance2_fast'
  ),
  array[
    'Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.',
    'Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.',
    'Без сгенерированных надписей, субтитров и декоративного текста.'
  ]::text[],
  'Seedance reusable requirements prohibit generated captions'
);

select is(
  content_factory_private.generation_mode_prompt_requirements(
    'unknown_model'
  ),
  null::text[],
  'unknown paid models cannot produce a base prompt contract'
);

select is(
  content_factory_private.generation_product_interaction_requirement(
    'Пароварка',
    'household'
  ),
  'Масштаб и действие: товар показан целиком в естественном размере на устойчивой столешнице; герой взаимодействует с крышкой, панелью управления и готовым результатом.',
  'countertop appliance interaction matches the browser compiler exactly'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_start_real_generation_pre_mode_prompt_v10(jsonb)'
  ) is not null,
  'the complete previous paid-generation chain remains private'
);

select ok(
  to_regprocedure(
    'public.creator_start_real_generation(jsonb)'
  ) is not null,
  'the final paid-generation RPC remains available'
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
  'the final model-prompt wrapper remains SECURITY DEFINER'
);

select matches(
  pg_get_functiondef(
    'public.creator_start_real_generation(jsonb)'::regprocedure
  ) || pg_get_functiondef(
    'content_factory_private.creator_start_real_generation_pre_review_autostart_v11(jsonb)'::regprocedure
  ),
  'generation_mode_prompt_binding_invalid',
  'the paid database boundary fails closed on a missing mode prompt fragment'
);

select * from finish();
rollback;
