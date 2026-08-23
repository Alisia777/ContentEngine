begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(11);

insert into content_factory.organizations (id, name, slug, status)
values (
  '00000000-0000-4000-8000-000000000202'::uuid,
  'Strategy route policy fixture',
  'strategy-route-policy-fixture',
  'active'
);

select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'runway', 'aleph2', '/v1/video_to_video',
    'runway_task',
    'runway-recipe-credits-2026-08-14.v1'
  ),
  'Runway Aleph Product Swap is an exact executable route'
);

select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
    'fal-ai/pika/v2/pikaswaps', 'fal_request',
    'fal-usd-per-run-2026-08-18.v1'
  ),
  'fal Pika Product Swap is an exact executable route'
);

select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal',
    'fal-ai/kling-video/o3/pro/video-to-video/edit',
    'fal-ai/kling-video/o3/pro/video-to-video/edit',
    'fal_request',
    'fal-usd-per-second-2026-08-18.v1'
  ),
  'fal Kling Product Swap is an exact executable route'
);

select ok(
  not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'fal-ai/unknown/video-to-video',
    'fal-ai/unknown/video-to-video', 'fal_request',
    'fal-usd-per-run-2026-08-18.v1'
  ),
  'an unknown fal model tuple fails the executable route allowlist'
);

select ok(
  not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
    'fal-ai/pika/v2/pikaswaps', 'runway_task',
    'fal-usd-per-run-2026-08-18.v1'
  ),
  'a known fal model with the wrong poll contract fails closed'
);

select ok(
  content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000202', 'runway', 'aleph2'
  ),
  'the active organization launch gate accepts exact Runway Aleph'
);

select ok(
  content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000202',
    'fal', 'fal-ai/pika/v2/pikaswaps'
  ),
  'the active organization launch gate accepts exact fal Pika'
);

select ok(
  content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000202', 'fal',
    'fal-ai/kling-video/o3/pro/video-to-video/edit'
  ),
  'the active organization launch gate accepts exact fal Kling'
);

select ok(
  not content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000202',
    'fal', 'fal-ai/unknown/video-to-video'
  ),
  'the active organization launch gate rejects an unknown fal model'
);

-- Прежде здесь проверялось наличие текста `case when not exists` — той самой
-- ветки, которая подставляла каталожную цену, когда у стратегии не было ни
-- одной строки реестра. Миграция 202608230010 сняла эту ветку ЦЕЛИКОМ: цена
-- запуска приходит только из реестра маршрутов, и «Создание» больше не
-- оценивается по Runway за адрес, которого у Runway не существует.
--
-- Замысел утверждения от этого не ослаб, а усилился, поэтому проверяется
-- теперь более сильный факт: каталожная цена в проверке готовности не
-- упоминается вовсе, а разрешение маршрута — по-прежнему да.
select ok(
  strpos(
    pg_get_functiondef(
      'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
    ),
    'generation_strategy_provider_route_allowed'
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
    ),
    'generation_strategy_recipe_price'
  ) = 0,
  'readiness prices only from the registry and never from the recipe catalog'
);

-- Замок исполнимого маршрута отвечает по фактам реестра, а не по имени
-- стратегии: «Копия» и «Создание» (с 202608230021 у него четыре строки fal)
-- проходят, «Дуэт» с выключенной строкой и несуществующая стратегия — нет.
select ok(
  content_factory_private.generation_strategy_executable_route_exists(
    'viral_product_swap'
  )
  and content_factory_private.generation_strategy_executable_route_exists(
    'viral_rebuild'
  )
  and not content_factory_private.generation_strategy_executable_route_exists(
    'no_such_strategy'
  ),
  'the executable-route lock answers from the registry, not from a name list'
);

select * from finish();
rollback;
