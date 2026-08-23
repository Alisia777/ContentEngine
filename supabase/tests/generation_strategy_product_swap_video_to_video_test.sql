begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(8);

-- ---------------------------------------------------------------------------
-- Product Swap provider path contract.  Mirrors the verification DO block in
-- 202608170006_generation_strategy_product_swap_video_to_video_v1.sql so the
-- exact production incident (paid dispatch POSTing the non-existent
-- /v1/recipes/product_swap endpoint and dying with "provider unavailable")
-- can never land silently again.  Runway's live API exposes video_to_video
-- (Gen-4 Aleph); the SQL policy layer must agree with the edge catalog and
-- the recipe adapter on '/v1/video_to_video' for product_swap only.
-- ---------------------------------------------------------------------------

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    ),
    '''/v1/video_to_video'''
  ) > 0,
  'catalog policy advertises the real video_to_video path for product_swap'
);

select is(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    ),
    '/v1/recipes/product_swap'
  ),
  0,
  'catalog policy no longer embeds the fictional /v1/recipes/product_swap'
);

-- 22.08.2026: «Аватар» стал «Дуэтом» и ушёл с выдуманного /v1/recipes/product_ugc
-- на настоящий /v1/video_to_video (миграция 202608220003). Прежнее утверждение
-- «product_ugc не тронут» описывало объём работы 17.08 и с тех пор перестало
-- быть правдой.
--
-- Заменять его на «путь равен video_to_video» здесь не нужно: этим занят пункт 1
-- выше, а тут стережётся другое — что НИ ОДИН выдуманный адрес не вернулся.
-- У Runway эндпоинтов /v1/recipes/* не существует вовсе, и обе стратегии,
-- которые с них ушли, обязаны на них не возвращаться.
select is(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    ),
    '''/v1/recipes/product_ugc'''
  ),
  0,
  'catalog policy no longer embeds the fictional /v1/recipes/product_ugc'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    ),
    '''/v1/recipes/product_ad'''
  ) > 0,
  'catalog policy keeps the product_ad path untouched (Stage 2 scope)'
);

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    '''/v1/video_to_video'''
  ) > 0,
  'provider policy returns the real video_to_video path for product_swap'
);

select is(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    '/v1/recipes/product_swap'
  ),
  0,
  'provider policy no longer embeds the fictional /v1/recipes/product_swap'
);

select ok(
  (
    select
      strpos(policy.definition, 'case when recipe_value = ''product_swap''') > 0
      and strpos(policy.definition, '''/v1/recipes/'' || recipe_value') > 0
    from (
      select pg_get_functiondef(
        'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
      ) as definition
    ) policy
  ),
  'provider policy branches on product_swap only; other recipes keep their paths'
);

-- Версия прайса перестала быть литералом Runway в 202608180008, а
-- 202608200002 связала её с точным provider/model/path/poll маршрутом.
-- Политика обязана восстановить включённый маршрут из подписанных provider +
-- pricing_version квитанции и пропустить его через exact allowlist. Спенд-
-- контур от этого не ослаб: неизвестная строка реестра не становится правом
-- на запуск только потому, что ей поставили enabled.
select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    'content_factory_private.generation_strategy_route_provider_current('
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    'generation_strategy_provider_route_allowed('
  ) > 0
  and strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    '''pricing_version'', ''runway-recipe-credits-2026-08-14.v1'''
  ) = 0,
  'pricing stays the untouched internal spend-contour authority'
);

select * from finish();
rollback;
