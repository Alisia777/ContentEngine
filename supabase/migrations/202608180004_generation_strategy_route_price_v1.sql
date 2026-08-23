begin;

-- 202608180004_generation_strategy_route_price_v1
--
-- Цена по маршруту вместо цены по стратегии.
--
-- До этой миграции цена считалась только для Runway: ступени «база на 4 секунды
-- плюс надбавка за каждую следующую», единица — кредит Runway. Провайдера в
-- расчёте не было вовсе, поэтому второй движок не мог получить цену, а без
-- цены не может быть ни резерва, ни квитанции, ни запуска.
--
-- Ключевое наблюдение, которое избавляет от переписывания половины контура:
-- у Runway один кредит равен одному центу. Значит для маршрута с собственной
-- ставкой можно считать центы напрямую и класть их и в estimated_credits, и в
-- estimated_cost_minor. Инвариант «кредит = цент», на который опираются
-- контракт и edge, остаётся верным для обоих провайдеров.
--
-- Функция ниже — диспетчер: для Runway она вызывает действующий расчёт без
-- изменений, для остальных берёт ставку из реестра маршрутов (202608180002).

create or replace function content_factory_private.generation_strategy_route_price(
  p_strategy_id text,
  p_provider text,
  p_model_key text,
  p_duration_seconds integer,
  p_resolution text,
  p_ratio text,
  p_audio boolean
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  route_row content_factory.generation_strategy_provider_routes%rowtype;
  recipe_value text;
  cost_minor_value integer;
  cost_usd_value text;
  input_mode_value text;
begin
  -- Действующий маршрут считается прежней функцией: ни одна цифра Runway не
  -- должна измениться из-за появления второго провайдера.
  if p_provider = 'runway' then
    return content_factory_private.generation_strategy_recipe_price(
      p_strategy_id, p_duration_seconds, p_resolution, p_ratio, p_audio
    );
  end if;

  select route.* into route_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = p_strategy_id
    and route.provider = p_provider
    and route.model_key = p_model_key;
  if route_row.id is null or route_row.enabled is not true then
    return null;
  end if;

  recipe_value := content_factory_private.generation_strategy_recipe(
    p_strategy_id
  );
  if recipe_value is null
     or p_duration_seconds not between route_row.min_duration_seconds
       and route_row.max_duration_seconds
     or p_resolution not in ('720p', '1080p')
     or (p_strategy_id = 'viral_product_swap' and p_ratio <> 'source') then
    return null;
  end if;

  cost_minor_value := case route_row.price_kind
    when 'usd_minor_per_run' then route_row.price_rate_minor
    when 'usd_minor_per_second' then
      route_row.price_rate_minor * p_duration_seconds
    else null
  end;
  if cost_minor_value is null or cost_minor_value <= 0 then
    return null;
  end if;
  cost_usd_value := to_char(
    cost_minor_value::numeric / 100::numeric, 'FM999990.00'
  );
  input_mode_value := case p_strategy_id
    when 'viral_avatar_ugc' then 'character_and_product_images'
    when 'viral_product_swap' then 'video_and_product_images'
    when 'viral_rebuild' then 'product_images'
  end;

  return jsonb_build_object(
    'version', 'generation-strategy-price-snapshot-v1',
    'strategy_id', p_strategy_id,
    'provider', p_provider,
    'recipe', recipe_value,
    'input_mode', input_mode_value,
    'duration_seconds', p_duration_seconds,
    'resolution', p_resolution,
    'ratio', p_ratio,
    'audio', p_audio,
    'estimated_credits', cost_minor_value,
    'estimated_pre_tax_usd_minor', cost_minor_value,
    'estimated_cost_minor', cost_minor_value,
    'estimated_cost_usd', cost_usd_value,
    'currency', 'USD',
    'credit_unit_cost_minor', 1,
    'catalog_version', '2026-08-14.v1',
    'pricing_version', route_row.pricing_version,
    'recipe_version', '2026-06',
    -- Префикс подтверждения называет провайдера: оператор и журнал видят, чем
    -- именно оплачен запуск, а разбор строки остаётся однозначным.
    'spend_confirmation', concat(
      upper(p_provider), '_', upper(recipe_value), '_',
      p_duration_seconds::text, 'S_', upper(p_resolution), '_',
      case when p_audio then 'AUDIO' else 'SILENT' end,
      '_USD_', cost_usd_value
    )
  );
end;
$$;

revoke all on function
  content_factory_private.generation_strategy_route_price(
    text, text, text, integer, text, text, boolean
  )
  from public, anon, authenticated, service_role;

comment on function content_factory_private.generation_strategy_route_price(
  text, text, text, integer, text, text, boolean
) is
  'Цена запуска по маршруту реестра. Runway считается прежней функцией без изменений; остальные маршруты — по своей ставке, в центах, с сохранением инварианта «кредит = цент».';

-- Квитанция готовности и снимок выбора перестают быть привязаны к единственному
-- провайдеру. Ограничения не снимаются, а расширяются на известный список:
-- случайная строка по-прежнему не пройдёт.
alter table content_factory.generation_strategy_readiness_receipts
  drop constraint if exists generation_strategy_readiness_receipts_provider_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_provider_check
  check (provider in ('runway', 'fal'));

alter table content_factory.generation_strategy_readiness_receipts
  drop constraint if exists generation_strategy_readiness_receipts_pricing_version_check;
alter table content_factory.generation_strategy_readiness_receipts
  add constraint generation_strategy_readiness_receipts_pricing_version_check
  check (pricing_version in (
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1'
  ));

alter table content_factory.generation_strategy_binding_selections
  drop constraint if exists generation_strategy_binding_selections_pricing_version_check;
alter table content_factory.generation_strategy_binding_selections
  add constraint generation_strategy_binding_selections_pricing_version_check
  check (pricing_version in (
    'runway-recipe-credits-2026-08-14.v1',
    'fal-usd-per-run-2026-08-18.v1'
  ));

do $generation_strategy_route_price_verify$
declare
  runway_snapshot jsonb;
  fal_snapshot jsonb;
begin
  -- Цена Runway обязана совпасть с прежней до цента.
  runway_snapshot := content_factory_private.generation_strategy_route_price(
    'viral_product_swap', 'runway', 'aleph2', 10, '720p', 'source', false
  );
  if runway_snapshot is distinct from
     content_factory_private.generation_strategy_recipe_price(
       'viral_product_swap', 10, '720p', 'source', false
     ) then
    raise exception using message = 'route_price_runway_drift';
  end if;
  if (runway_snapshot ->> 'estimated_cost_minor')::integer <> 428 then
    raise exception using message = 'route_price_runway_unexpected';
  end if;
  -- Выключенный маршрут цены не имеет: без включения запуск невозможен.
  fal_snapshot := content_factory_private.generation_strategy_route_price(
    'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
    10, '720p', 'source', false
  );
  if fal_snapshot is not null then
    raise exception using message = 'route_price_disabled_route_priced';
  end if;
end;
$generation_strategy_route_price_verify$;

commit;
