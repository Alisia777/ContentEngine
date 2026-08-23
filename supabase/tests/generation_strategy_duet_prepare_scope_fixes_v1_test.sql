begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(8);

-- «Дуэт» после 202608230023: подготовка ТЗ, ворота проекта, версия ТЗ и
-- триггер подписи привязки согласованы между собой. До миграции ни одно ТЗ
-- дуэта не могло быть подготовлено (scope_invalid → project_scope_mismatch →
-- primary_media_invalid → spec_authority_required, по одной причине за раз).

-- 1. reference_video у дуэта false, как ждут валидатор области и зеркало.
select ok(
  position(
    '''reference_video'', recipe_value = ''product_swap'''
    in pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) > 0,
  'prepare marks only product_swap as a provider reference video'
);
select ok(
  position(
    '''reference_video'', recipe_value in (''product_swap'', ''product_ugc'')'
    in pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) = 0,
  'the 202608220003 reference_video widening is gone'
);

-- 2. Разбор механики дуэта читается из payload в ветке правки готового видео.
select ok(
  position(
    '    if recipe_value = ''product_ugc'' then'
    in pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) > 0,
  'prepare parses mechanics_summary for the duet recipe'
);

-- 3. Исходник дуэта привязывается к названному товару при подготовке ТЗ.
select ok(
  position(
    'update content_factory.media_objects source_media'
    in pg_get_functiondef(
      'public.creator_prepare_generation_strategy_spec(jsonb)'::regprocedure
    )
  ) > 0,
  'prepare binds an unowned duet source video to the named product'
);

-- 4. Версия ТЗ и сверка актуальности принимают исходник как цель работы.
select ok(
  (
    select count(*)
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname in (
        'create_generation_spec_version',
        'assert_generation_spec_current_pre_advisory_v1'
      )
      and position(
        '''product_photo'', ''packshot'', ''source_video'''
        in pg_get_functiondef(p.oid)
      ) > 0
  ) = 2,
  'spec version and currency checks accept a source_video target'
);

-- 5. Триггер подписи привязки больше не исключает исходник дуэта из реестра.
select ok(
  position(
    'and new.strategy_id = ''viral_avatar_ugc'''
    in pg_get_functiondef(
      'content_factory_private.enforce_generation_strategy_spec_authority()'
        ::regprocedure
    )
  ) = 0,
  'the binding authority trigger checks the duet source like any other source'
);

-- 6. Валидатор области по-прежнему ждёт false у всего, кроме «Копии».
select ok(
  position(
    '(strategy_id_value = ''viral_product_swap'')'
    in pg_get_functiondef(
      'content_factory_private.generation_strategy_spec_scope_legacy_v1(jsonb)'
        ::regprocedure
    )
  ) > 0,
  'the scope validator still expects reference_video only for product_swap'
);

-- 7. Цена дуэта считается по разрешению исходника (ratio source).
select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 6, '720p', 'source', false
  ) ->> 'estimated_cost_minor',
  '30',
  'a 6-second duet at 720p costs 30 cents on the HeyGen route'
);

select * from finish();
rollback;
