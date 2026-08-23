begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(12);

-- Движки «Создания» (миграция 202608230021): четыре строки fal, замок
-- 202608230010 отпирается фактом строки, цена идёт из реестра, 1080p не
-- продаётся движкам, которые делают только 720p.

insert into content_factory.organizations (id, name, slug, status)
values (
  '00000000-0000-4000-8000-000000000221'::uuid,
  'Rebuild engines fixture',
  'rebuild-engines-fixture',
  'active'
);

select is(
  (select count(*)::integer from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_rebuild' and enabled),
  4,
  'the Rebuild strategy has four enabled fal engines'
);

select is(
  (select model_key from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_rebuild' and recommended),
  'minimax/h3/reference-to-video',
  'MiniMax H3 is the default Rebuild engine'
);

select ok(
  content_factory_private.generation_strategy_executable_route_exists('viral_rebuild'),
  'the executable-route lock opens for Rebuild'
);

select ok(
  (select bool_and(content_factory_private.generation_strategy_provider_route_allowed(
     route.strategy_id, route.provider, route.model_key,
     route.provider_path, route.poll_kind, route.pricing_version
   ) and content_factory_private.generation_provider_launch_enabled(
     '00000000-0000-4000-8000-000000000221', route.provider, route.model_key
   ))
   from content_factory.generation_strategy_provider_routes route
   where route.strategy_id = 'viral_rebuild'),
  'every Rebuild engine is an exact executable route and passes the launch gate'
);

select ok(
  not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_rebuild', 'runway', 'gen4_turbo', '/v1/recipes/product_ad',
    'runway_task', 'runway-recipe-credits-2026-08-14.v1'
  ),
  'the non-existent Runway recipe address is no longer an executable route'
);

select is(
  (select count(distinct (provider, pricing_version))::integer
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_rebuild' and enabled),
  4,
  'every enabled Rebuild engine carries its own signature'
);

select is(
  content_factory_private.generation_strategy_route_price(
    'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
    10, '720p', '720:1280', false
  ) ->> 'estimated_cost_minor',
  '60',
  'MiniMax prices ten seconds at sixty cents'
);

select is(
  content_factory_private.generation_strategy_route_price(
    'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
    10, '720p', '720:1280', false
  ) ->> 'spend_confirmation',
  'FAL_PRODUCT_AD_10S_720P_SILENT_USD_0.60',
  'the Rebuild spend confirmation names the fal provider and the product_ad recipe'
);

select is(
  content_factory_private.generation_strategy_route_price(
    'viral_rebuild', 'fal', 'minimax/h3/reference-to-video',
    10, '1080p', '1080:1920', false
  ),
  null::jsonb,
  'a 1080p frame is refused for an engine whose only quality mode is 720p'
);

select is(
  content_factory_private.generation_strategy_route_price(
    'viral_rebuild', 'fal', 'xai/grok-imagine-video/reference-to-video',
    12, '720p', '720:1280', false
  ),
  null::jsonb,
  'Grok refuses twelve seconds: its window is 4–10'
);

select is(
  content_factory_private.generation_strategy_route_price(
    'viral_product_swap', 'runway', 'aleph2', 10, '1080p', 'source', false
  ) ->> 'estimated_credits',
  '468',
  'Runway Aleph keeps its 1080p tier: the quality-mode check does not touch it'
);

select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_rebuild', 5, '720p', '1280:720', false
  ) ->> 'estimated_credits',
  '30',
  'the active Rebuild route prices five seconds at thirty cents'
);

select * from finish();
rollback;
