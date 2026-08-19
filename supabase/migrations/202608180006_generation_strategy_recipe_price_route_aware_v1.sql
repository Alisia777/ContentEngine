begin;

-- 202608180006_generation_strategy_recipe_price_route_aware_v1
--
-- Цена стратегии становится ценой её действующего маршрута.
--
-- Цена сверяется в шести местах: дважды при привязке, дважды в проверках
-- механики, при записи квитанции и при клейме. Все шесть зовут одну и ту же
-- функцию, поэтому расширяется именно она — тогда рассогласование между
-- местами невозможно по построению, а не по внимательности.
--
-- Действующим считается маршрут реестра, помеченный одновременно
-- рекомендованным и включённым; такой маршрут у стратегии ровно один
-- (частичный уникальный индекс из 202608180002). Пока это Runway, все цифры
-- остаются прежними — за этим следит verify-блок в конце файла.

create or replace function content_factory_private.generation_strategy_recipe_price(
  p_strategy_id text,
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
  recipe_value text;
  base_credits integer;
  incremental_credits integer;
  credits_value integer;
  cost_usd_value text;
  input_mode_value text;
  route_row content_factory.generation_strategy_provider_routes%rowtype;
  provider_value text;
  pricing_version_value text;
begin
  recipe_value := content_factory_private.generation_strategy_recipe(
    p_strategy_id
  );
  if recipe_value is null
     or p_resolution not in ('720p', '1080p')
     or (
       p_strategy_id = 'viral_avatar_ugc'
       and p_ratio <> case p_resolution
         when '720p' then '720:1280' else '1080:1920' end
     )
     or (p_strategy_id = 'viral_product_swap' and p_ratio <> 'source')
     or (
       p_strategy_id = 'viral_rebuild'
       and not (
         (p_resolution = '720p' and p_ratio in (
           '1280:720', '720:1280', '960:960', '834:1112'
         ))
         or
         (p_resolution = '1080p' and p_ratio in (
           '1920:1080', '1080:1920', '1440:1440', '1248:1664'
         ))
       )
     ) then
    return null;
  end if;

  select route.* into route_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = p_strategy_id
    and route.recommended
    and route.enabled;
  provider_value := coalesce(route_row.provider, 'runway');
  pricing_version_value := coalesce(
    route_row.pricing_version, 'runway-recipe-credits-2026-08-14.v1'
  );

  if provider_value <> 'runway' then
    if p_duration_seconds not between route_row.min_duration_seconds
       and route_row.max_duration_seconds then
      return null;
    end if;
    credits_value := case route_row.price_kind
      when 'usd_minor_per_run' then route_row.price_rate_minor
      when 'usd_minor_per_second' then
        route_row.price_rate_minor * p_duration_seconds
      else null
    end;
    if credits_value is null or credits_value <= 0 then
      return null;
    end if;
  else
    -- Прежняя арифметика Runway: база на четыре секунды плюс надбавка за
    -- каждую следующую. Ни одна цифра не изменена.
    if p_duration_seconds not between 4 and 15 then
      return null;
    end if;
    base_credits := case p_strategy_id
      when 'viral_avatar_ugc' then
        case p_resolution when '720p' then 192 else 208 end
      when 'viral_product_swap' then
        case p_resolution when '720p' then 212 else 228 end
      when 'viral_rebuild' then
        case p_resolution when '720p' then 200 else 216 end
    end;
    incremental_credits := case p_resolution
      when '720p' then 36 else 40 end;
    credits_value := base_credits
      + ((p_duration_seconds - 4) * incremental_credits);
  end if;

  cost_usd_value := to_char(
    credits_value::numeric / 100::numeric, 'FM999990.00'
  );
  input_mode_value := case p_strategy_id
    when 'viral_avatar_ugc' then 'character_and_product_images'
    when 'viral_product_swap' then 'video_and_product_images'
    when 'viral_rebuild' then 'product_images'
  end;

  return jsonb_build_object(
    'version', 'generation-strategy-price-snapshot-v1',
    'strategy_id', p_strategy_id,
    'provider', provider_value,
    'recipe', recipe_value,
    'input_mode', input_mode_value,
    'duration_seconds', p_duration_seconds,
    'resolution', p_resolution,
    'ratio', p_ratio,
    'audio', p_audio,
    'estimated_credits', credits_value,
    'estimated_pre_tax_usd_minor', credits_value,
    'estimated_cost_minor', credits_value,
    'estimated_cost_usd', cost_usd_value,
    'currency', 'USD',
    'credit_unit_cost_minor', 1,
    'catalog_version', '2026-08-14.v1',
    'pricing_version', pricing_version_value,
    'recipe_version', '2026-06',
    'spend_confirmation', concat(
      upper(provider_value), '_', upper(recipe_value), '_',
      p_duration_seconds::text, 'S_', upper(p_resolution), '_',
      case when p_audio then 'AUDIO' else 'SILENT' end,
      '_USD_', cost_usd_value
    )
  );
end;
$$;

do $recipe_price_route_aware_verify$
declare
  snapshot_value jsonb;
begin
  -- Действующий маршрут — Runway, значит все прежние цифры обязаны совпасть.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 10, '720p', 'source', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 428
     or snapshot_value ->> 'provider' <> 'runway'
     or snapshot_value ->> 'spend_confirmation' <>
        'RUNWAY_PRODUCT_SWAP_10S_720P_SILENT_USD_4.28' then
    raise exception using message = 'recipe_price_runway_drift';
  end if;
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 5, '720p', '720:1280', true
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 228 then
    raise exception using message = 'recipe_price_avatar_drift';
  end if;
  -- Пятнадцать секунд Product Swap: 212 + 11 * 36 = 608.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 15, '720p', 'source', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 608 then
    raise exception using message = 'recipe_price_duration_drift';
  end if;
end;
$recipe_price_route_aware_verify$;

commit;
