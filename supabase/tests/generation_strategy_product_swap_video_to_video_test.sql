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

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_catalog_policy(jsonb)'::regprocedure
    ),
    '''/v1/recipes/product_ugc'''
  ) > 0,
  'catalog policy keeps the product_ugc path untouched (Stage 2 scope)'
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

select ok(
  strpos(
    pg_get_functiondef(
      'public.system_generation_strategy_provider_policy(jsonb)'::regprocedure
    ),
    '''pricing_version'', ''runway-recipe-credits-2026-08-14.v1'''
  ) > 0,
  'pricing stays the untouched internal spend-contour authority'
);

select * from finish();
rollback;
