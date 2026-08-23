begin;

-- 202608180008_generation_strategy_pricing_version_route_aware_v1
--
-- Версия прайса перестаёт быть литералом «runway» и становится свойством
-- действующего маршрута.
--
-- Литерал 'runway-recipe-credits-2026-08-14.v1' сидел в девяти местах четырёх
-- функций. Блокирующих из них три, но починить только их нельзя по двум
-- причинам. Во-первых, браузер сверяет версию прайса точным совпадением, и
-- шесть «безобидных» мест сборки ответа отвергли бы второй провайдер уже на
-- клиенте. Во-вторых, версия входит в хеш-подпись строки привязки: правка по
-- частям пересчитала бы подписи существующих строк, и любая повторная привязка
-- упёрлась бы в конфликт. Поэтому все девять правятся одним патчем.
--
-- Значение берётся у маршрута, помеченного одновременно рекомендованным и
-- включённым; такой маршрут у стратегии ровно один (частичный уникальный
-- индекс generation_strategy_provider_routes_recommended_key). Если маршрута
-- нет вовсе — а сейчас его нет у «Аватара» и «Пересборки» — отдаётся прежний
-- литерал. Это не задел на будущие стратегии, а защита настоящего: все три
-- стратегии живут в одном ответе каталога, и пустая версия у двух из них
-- обрушила бы ответ вместе с «Копией».
--
-- Сегодня активен маршрут Runway, поэтому выражение отдаёт ту же строку, что
-- стояла литералом: вывод остаётся байт в байт прежним, подписи существующих
-- строк не сдвигаются. За этим следит verify-блок в конце файла.
--
-- Тела функций правятся точечной заменой известного фрагмента: полные тела
-- живут в прежних миграциях, и переписывать их целиком ради одной строки
-- означало бы рисковать остальным содержимым. Каждый якорь проверяется на
-- единственность ДО замены, иначе миграция падает с именем якоря.


create or replace function content_factory_private.generation_strategy_pricing_version(
  p_strategy_id text
)
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    (
      select route.pricing_version
      from content_factory.generation_strategy_provider_routes as route
      where route.strategy_id = p_strategy_id
        and route.recommended
        and route.enabled
    ),
    'runway-recipe-credits-2026-08-14.v1'
  );
$$;

-- Инструмент времени сборки: заменяет фрагмент ровно один раз или падает.
-- Живёт только внутри этой миграции и удаляется в конце.
create or replace function content_factory_private.migration_patch_once(
  p_source text,
  p_search text,
  p_replace text,
  p_tag text
)
returns text
language plpgsql
immutable
as $$
declare
  hits integer;
begin
  if p_source is null or p_search is null or length(p_search) = 0 then
    raise exception using message = 'patch_arguments_invalid:' || p_tag;
  end if;
  hits := (length(p_source) - length(replace(p_source, p_search, '')))
    / length(p_search);
  if hits <> 1 then
    raise exception using
      message = 'patch_anchor_not_unique:' || p_tag || ':' || hits::text;
  end if;
  return replace(p_source, p_search, p_replace);
end;
$$;

-- 1. Политика провайдера. Первое вхождение — настоящий страж: условие WHERE по
--    таблице квитанций готовности. Квитанция маршрута fal несёт свою версию
--    прайса, не попадала в выборку, receipt_row оставался пустым, и наружу
--    уходил отказ. Остальные два — сборка ответа, которую сверяет браузер.
do $patch_provider_policy$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_provider_policy';
  if definition_value is null then
    raise exception using message = 'provider_policy_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$and receipt.pricing_version =
        'runway-recipe-credits-2026-08-14.v1'$s$,
    $r$and receipt.pricing_version =
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )$r$,
    'provider_policy.receipt_guard'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      )$s$,
    $r$        'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )
      )$r$,
    'provider_policy.execution_capabilities'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$      'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
    ),$s$,
    $r$      'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      )
    ),$r$,
    'provider_policy.context'
  );

  execute patched_value;
end;
$patch_provider_policy$;

-- 2. Политика каталога. Все три вхождения — сборка ответа, по разу на
--    стратегию. Литерал сам по себе неуникален, поэтому якорем служит
--    предшествующая строка с путём провайдера: она у каждой стратегии своя.
do $patch_catalog_policy$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_catalog_policy';
  if definition_value is null then
    raise exception using message = 'catalog_policy_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$        'provider_path', '/v1/recipes/product_ugc',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'$s$,
    $r$        'provider_path', '/v1/recipes/product_ugc',
        'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          'viral_avatar_ugc'
        )$r$,
    'catalog_policy.viral_avatar_ugc'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$        'provider_path', '/v1/video_to_video',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'$s$,
    $r$        'provider_path', '/v1/video_to_video',
        'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          'viral_product_swap'
        )$r$,
    'catalog_policy.viral_product_swap'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$        'provider_path', '/v1/recipes/product_ad',
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'$s$,
    $r$        'provider_path', '/v1/recipes/product_ad',
        'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          'viral_rebuild'
        )$r$,
    'catalog_policy.viral_rebuild'
  );

  execute patched_value;
end;
$patch_catalog_policy$;

-- 3. Низкоуровневая привязка. Первое вхождение уходит в хеш-подпись строки,
--    второе — прямо в колонку pricing_version. Именно второе штампует
--    «runway» поверх снимка цены, посчитанного по другому провайдеру: из 24
--    существующих строк во всех 24 колонка говорит runway, а в строке за
--    18.08.2026 15:53 внутри снимка лежит fal. Оба вхождения правятся вместе,
--    иначе подпись и данные разъедутся.
do $patch_resolve_bind$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_resolve_and_bind_generation_strategy';
  if definition_value is null then
    raise exception using message = 'resolve_bind_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$'pricing_version', 'runway-recipe-credits-2026-08-14.v1',$s$,
    $r$'pricing_version',
    content_factory_private.generation_strategy_pricing_version(
      strategy_id_value
    ),$r$,
    'resolve_bind.snapshot_hash'
  );

  patched_value := content_factory_private.migration_patch_once(
    patched_value,
    $s$'2026-06', 'runway-recipe-credits-2026-08-14.v1', selection_value,$s$,
    $r$'2026-06',
    content_factory_private.generation_strategy_pricing_version(
      strategy_id_value
    ), selection_value,$r$,
    'resolve_bind.selection_column'
  );

  execute patched_value;
end;
$patch_resolve_bind$;

-- 4. Обёртка привязки: единственное вхождение в ответе порталу.
do $patch_pre_execution$
declare
  definition_value text;
  patched_value text;
begin
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null then
    raise exception using message = 'pre_execution_missing';
  end if;

  patched_value := content_factory_private.migration_patch_once(
    definition_value,
    $s$      'pricing_version', 'runway-recipe-credits-2026-08-14.v1',$s$,
    $r$      'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      ),$r$,
    'pre_execution.selection_response'
  );

  execute patched_value;
end;
$patch_pre_execution$;

drop function content_factory_private.migration_patch_once(
  text, text, text, text
);

do $pricing_version_route_aware_verify$
declare
  strategy_name text;
  function_name text;
  version_value text;
  definition_value text;
  snapshot_value jsonb;
begin
  -- Помощник обязан отдавать прежнюю строку всем трём стратегиям: у «Копии»
  -- активен маршрут Runway, у двух других маршрута нет вовсе.
  foreach strategy_name in array array[
    'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
  ] loop
    version_value :=
      content_factory_private.generation_strategy_pricing_version(
        strategy_name
      );
    if version_value is distinct from
       'runway-recipe-credits-2026-08-14.v1' then
      raise exception using
        message = 'pricing_version_drift:' || strategy_name || ':'
          || coalesce(version_value, '<null>');
    end if;
  end loop;

  -- Ни в одной из четырёх функций литерала больше нет, и все четыре зовут
  -- помощника.
  foreach function_name in array array[
    'system_generation_strategy_provider_policy',
    'system_generation_strategy_catalog_policy',
    'system_resolve_and_bind_generation_strategy',
    'system_resolve_and_bind_generation_strategy_pre_execution_v1'
  ] loop
    select pg_get_functiondef(p.oid) into definition_value
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname = function_name;
    if definition_value is null then
      raise exception using message = 'verify_function_missing:' || function_name;
    end if;
    if position('runway-recipe-credits-2026-08-14.v1' in definition_value) > 0
    then
      raise exception using
        message = 'pricing_version_literal_left:' || function_name;
    end if;
    if position(
         'generation_strategy_pricing_version' in definition_value
       ) = 0 then
      raise exception using
        message = 'pricing_version_helper_missing:' || function_name;
    end if;
  end loop;

  -- Цена Runway обязана остаться прежней до цента.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 10, '720p', 'source', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 428
     or snapshot_value ->> 'provider' <> 'runway'
     or snapshot_value ->> 'pricing_version' <>
        'runway-recipe-credits-2026-08-14.v1'
     or snapshot_value ->> 'spend_confirmation' <>
        'RUNWAY_PRODUCT_SWAP_10S_720P_SILENT_USD_4.28' then
    raise exception using message = 'recipe_price_runway_drift';
  end if;

  -- Инструмент времени сборки не должен остаться в базе.
  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'content_factory_private'
      and p.proname = 'migration_patch_once'
  ) then
    raise exception using message = 'migration_helper_left_behind';
  end if;
end;
$pricing_version_route_aware_verify$;

commit;
