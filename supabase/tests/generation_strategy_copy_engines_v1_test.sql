begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(22);

-- Движки «Копии», заведённые 23.08.2026 (миграция 202608230020): каждая
-- строка реестра обязана быть исполнимой парой, проходить рубильник запуска и
-- нести уникальную подпись (provider, pricing_version) среди включённых.

insert into content_factory.organizations (id, name, slug, status)
values (
  '00000000-0000-4000-8000-000000000220'::uuid,
  'Copy engines fixture',
  'copy-engines-fixture',
  'active'
);

select is(
  (select count(*)::integer
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap'),
  7,
  'the Copy strategy has seven engines in the registry'
);

select is(
  (select count(*)::integer
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap' and enabled),
  7,
  'all seven Copy engines are enabled'
);

select is(
  (select count(*)::integer
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap' and recommended),
  1,
  'exactly one Copy engine is the global default'
);

select is(
  (select count(distinct (provider, pricing_version))::integer
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap' and enabled),
  7,
  'every enabled Copy engine carries its own (provider, pricing_version) signature'
);

-- Каждая новая строка: исполнимая пара, рубильник, ставка, профиль.
select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal',
    'fal-ai/kling-video/o3/standard/video-to-video/edit',
    'fal-ai/kling-video/o3/standard/video-to-video/edit', 'fal_request',
    'fal-usd-per-second-kling-standard-2026-08-23.v1'
  ),
  'Kling O3 Standard is an exact executable route'
);
select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'alibaba/happy-horse/video-edit',
    'alibaba/happy-horse/video-edit', 'fal_request',
    'fal-usd-per-second-happy-horse-2026-08-23.v1'
  ),
  'Happy Horse video-edit is an exact executable route'
);
select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'bytedance/seedance-2.5/reference-to-video',
    'bytedance/seedance-2.5/reference-to-video', 'fal_request',
    'fal-usd-per-second-bytedance-2-5-2026-08-23.v1'
  ),
  'Seedance 2.5 reference-to-video is an exact executable route'
);
select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'minimax/h3/reference-to-video',
    'minimax/h3/reference-to-video', 'fal_request',
    'fal-usd-per-second-minimax-h3-2026-08-23.v1'
  ),
  'MiniMax H3 reference-to-video is an exact executable route'
);
select ok(
  not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_product_swap', 'fal', 'alibaba/happy-horse/video-edit',
    'alibaba/happy-horse/video-edit', 'fal_request',
    'fal-usd-per-second-2026-08-18.v1'
  ),
  'a new engine under the Kling Pro pricing version fails closed'
);

select ok(
  (select bool_and(content_factory_private.generation_provider_launch_enabled(
     '00000000-0000-4000-8000-000000000220', route.provider, route.model_key
   ))
   from content_factory.generation_strategy_provider_routes route
   where route.strategy_id = 'viral_product_swap'),
  'the active organization launch gate accepts every Copy engine'
);

select ok(
  (select bool_and(content_factory_private.generation_strategy_provider_route_allowed(
     route.strategy_id, route.provider, route.model_key,
     route.provider_path, route.poll_kind, route.pricing_version
   ))
   from content_factory.generation_strategy_provider_routes route
   where route.strategy_id = 'viral_product_swap'),
  'every registry row of the Copy strategy is an exact executable route'
);

select is(
  (select price_rate_minor from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap'
     and model_key = 'bytedance/seedance-2.5/reference-to-video'),
  58,
  'Seedance 2.5 reserves 58 cents per second (token price, input + output)'
);

select is(
  (select duration_source from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap'
     and model_key = 'minimax/h3/reference-to-video'),
  'operator_choice',
  'MiniMax H3 regenerates: the operator picks the duration'
);

select is(
  (select engine_family from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_product_swap'
     and model_key = 'minimax/h3/reference-to-video'),
  'regenerate',
  'MiniMax H3 is a regenerate engine'
);

select is(
  (select engine_family from content_factory.generation_strategy_provider_routes
   where provider = 'heygen'),
  'overlay',
  'the duet presenter is an overlay engine'
);

select is(
  (select (input_profile -> 'images' ->> 'max')::integer
   from content_factory.generation_strategy_provider_routes
   where model_key = 'alibaba/happy-horse/video-edit'),
  5,
  'Happy Horse accepts five product photos'
);

select is(
  (select input_profile -> 'keeps_source_audio'
   from content_factory.generation_strategy_provider_routes
   where model_key = 'fal-ai/pika/v2/pikaswaps'),
  'true'::jsonb,
  'Pika keeps the source audio track'
);

-- Форма профиля входа проверяется функцией, как quality_modes.
select ok(
  not content_factory_private.generation_strategy_input_profile_valid(
    '{"video": {"min_seconds": 3, "max_seconds": 2, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 1, "style": "region"}, "keeps_source_audio": true}'::jsonb
  ),
  'an inverted duration window is not a valid input profile'
);
select ok(
  not content_factory_private.generation_strategy_input_profile_valid(
    '{"video": {"min_seconds": 3, "max_seconds": 15, "min_short_side_px": null, "max_long_side_px": null}, "images": {"max": 2, "style": "none"}, "keeps_source_audio": true}'::jsonb
  ),
  'photos without a naming style are not a valid input profile'
);
select throws_ok(
  $$update content_factory.generation_strategy_provider_routes
    set input_profile = '{"video": {}, "images": {}, "keeps_source_audio": true}'::jsonb
    where model_key = 'alibaba/happy-horse/video-edit'$$,
  '23514',
  null,
  'the registry rejects a malformed input profile'
);
select throws_ok(
  $$update content_factory.generation_strategy_provider_routes
    set engine_family = 'magic'
    where model_key = 'alibaba/happy-horse/video-edit'$$,
  '23514',
  null,
  'the registry rejects an unknown engine family'
);

-- Витрина каталога отдаёт новые свойства каждому движку.
select ok(
  position('input_profile' in pg_get_functiondef(
    'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
  )) > 0
  and position('engine_family' in pg_get_functiondef(
    'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
  )) > 0,
  'the catalog policy publishes engine_family and input_profile'
);

select * from finish();
rollback;
