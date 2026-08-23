begin;

-- 202608180002_generation_strategy_provider_routes_v1
--
-- Реестр провайдерских маршрутов для стратегий генерации.
--
-- До этой миграции провайдер был не полем, а инвариантом: строка 'runway',
-- версия рецепта, версия прайса и путь эндпоинта дублировались в четырёх
-- слоях, и каждый слой сверял их с остальными. Это защищало деньги, но делало
-- невозможным второй провайдер: у стратегии физически один маршрут.
--
-- Таблица ниже — единственный источник правды о том, какими движками можно
-- выполнять стратегию, по какой цене и с какими режимами качества. Она только
-- ДОБАВЛЯЕТ данные: ни одна существующая функция, проверка или строка пока их
-- не читает, поэтому работающий маршрут Runway остаётся нетронутым.
--
-- Платный запуск нового маршрута включается отдельно, полем enabled, и только
-- после того как его ставка сверена с прайсом провайдера. Маршрут без
-- проверенной ставки не может быть включён — за это отвечает CHECK.

create table if not exists content_factory.generation_strategy_provider_routes (
  id uuid primary key default gen_random_uuid(),
  strategy_id text not null,
  provider text not null,
  model_key text not null,
  provider_path text not null,
  poll_kind text not null,
  pricing_version text not null,
  price_kind text not null,
  -- Ставка в минимальных единицах валюты (центах): за секунду результата или
  -- за ролик целиком — в зависимости от price_kind. Для ступенчатого прайса
  -- Runway остаётся null: там формула живёт в generation_strategy_recipe_price.
  -- Дробные центы провайдера округляются ВВЕРХ: резерв не может быть меньше
  -- фактического списания.
  price_rate_minor integer,
  min_duration_seconds integer not null,
  max_duration_seconds integer not null,
  tier text not null,
  quality_modes jsonb not null default '[]'::jsonb,
  recommended boolean not null default false,
  enabled boolean not null default false,
  verified_rate_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint generation_strategy_provider_routes_strategy_check
    check (strategy_id in ('viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild')),
  constraint generation_strategy_provider_routes_provider_check
    check (provider in ('runway', 'google', 'fal')),
  constraint generation_strategy_provider_routes_poll_kind_check
    check (poll_kind in ('runway_task', 'google_long_running_operation', 'fal_request')),
  constraint generation_strategy_provider_routes_price_kind_check
    check (price_kind in (
      'runway_credit_tiers', 'usd_minor_per_second', 'usd_minor_per_run'
    )),
  constraint generation_strategy_provider_routes_tier_check
    check (tier in ('cheap', 'medium', 'premium')),
  constraint generation_strategy_provider_routes_duration_check
    check (
      min_duration_seconds >= 1
      and max_duration_seconds >= min_duration_seconds
      and max_duration_seconds <= 60
    ),
  -- Маршрут с собственной ставкой обязан её нести; ступенчатый прайс Runway
  -- обязан её НЕ нести, иначе появятся два несогласованных источника цены.
  constraint generation_strategy_provider_routes_rate_shape_check
    check (
      (price_kind in ('usd_minor_per_second', 'usd_minor_per_run')
        and price_rate_minor is not null
        and price_rate_minor > 0 and price_rate_minor <= 10000)
      or (price_kind = 'runway_credit_tiers' and price_rate_minor is null)
    ),
  -- Включить маршрут можно только со сверенной ставкой: это прямая защита от
  -- запуска по выдуманной цене.
  constraint generation_strategy_provider_routes_enabled_requires_verified_check
    check (enabled = false or verified_rate_at is not null),
  constraint generation_strategy_provider_routes_modes_check
    check (jsonb_typeof(quality_modes) = 'array'),
  constraint generation_strategy_provider_routes_identity_key
    unique (strategy_id, provider, model_key)
);

comment on table content_factory.generation_strategy_provider_routes is
  'Реестр движков стратегии: какой провайдер, по какому пути, с какой ценой и режимами качества выполняет стратегию. Маршрут включается только со сверенной ставкой.';

-- Рекомендованный маршрут у стратегии ровно один: оператор видит одну отметку
-- «Советуем», а не спор нескольких.
create unique index if not exists generation_strategy_provider_routes_recommended_key
  on content_factory.generation_strategy_provider_routes (strategy_id)
  where recommended;

alter table content_factory.generation_strategy_provider_routes
  enable row level security;

revoke all on table content_factory.generation_strategy_provider_routes
  from public, anon, authenticated;

grant select on table content_factory.generation_strategy_provider_routes
  to service_role;

-- Действующий маршрут Runway описывается как строка реестра, чтобы каталог
-- читал оба движка одинаково. Ставка помечена сверенной: она уже действует и
-- подтверждена платными прогонами 17–18.08.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, recommended, enabled, verified_rate_at, notes
)
values (
  'viral_product_swap', 'runway', 'aleph2', '/v1/video_to_video', 'runway_task',
  'runway-recipe-credits-2026-08-14.v1', 'runway_credit_tiers', null,
  4, 15, 'premium',
  '["standard"]'::jsonb, true, true, now(),
  'Действующий маршрут. Переписывает кадр целиком: сильные сцены, но выдумывает мелкий текст и срывается на частых монтажных склейках.'
)
on conflict (strategy_id, provider, model_key) do nothing;

-- Маршрут fal.ai: ставка сверена со страницей модели 18.08.2026 — $0.465 за
-- ролик целиком, независимо от длительности. Округляем вверх до 47 центов,
-- чтобы резерв никогда не был меньше фактического списания. Маршрут заведён
-- выключенным: включим, когда код научится его исполнять.
insert into content_factory.generation_strategy_provider_routes (
  strategy_id, provider, model_key, provider_path, poll_kind,
  pricing_version, price_kind, price_rate_minor,
  min_duration_seconds, max_duration_seconds, tier,
  quality_modes, recommended, enabled, verified_rate_at, notes
)
values (
  'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
  'fal-ai/pika/v2/pikaswaps', 'fal_request',
  'fal-usd-per-run-2026-08-18.v1', 'usd_minor_per_run', 47,
  1, 15, 'cheap',
  '["standard"]'::jsonb, false, false, now(),
  'Точечная замена объекта по фото товара: video_url + image_url + modify_region. Провайдер берёт $0.465 за ролик, резервируем 47 центов.'
)
on conflict (strategy_id, provider, model_key) do nothing;

do $generation_strategy_provider_routes_verify$
declare
  runway_enabled_value boolean;
  fal_disabled_value boolean;
begin
  select enabled into runway_enabled_value
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap'
    and provider = 'runway'
    and model_key = 'aleph2';
  select not enabled into fal_disabled_value
  from content_factory.generation_strategy_provider_routes
  where strategy_id = 'viral_product_swap'
    and provider = 'fal';
  if runway_enabled_value is not true or fal_disabled_value is not true then
    raise exception using message = 'provider_routes_seed_invalid';
  end if;
end;
$generation_strategy_provider_routes_verify$;

commit;
