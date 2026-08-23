begin;

-- 202608180010_generation_strategy_product_swap_active_route_pika_v1
--
-- Действующим маршрутом «Копии» становится fal / fal-ai/pika/v2/pikaswaps.
--
-- Обёртка begin/commit открывает файл первой же строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет
-- обёртку регулярным выражением от начала файла. Поэтому «почему» живёт внутри
-- транзакции.
--
-- ЗАЧЕМ ЭТА МИГРАЦИЯ ВООБЩЕ ЕСТЬ. Переключение «Копии» с Runway на Pika было
-- сделано в проде руками, обычным UPDATE, и не попало ни в один файл. С этого
-- момента прод и репозиторий описывали разные системы: пересборка с нуля
-- поднимала «Копию» на Runway по 4.28 за десятисекундный ролик вместо 47
-- центов у Pika — разница почти в девять раз, и молча, потому что оба
-- состояния внутренне непротиворечивы. Ручная правка боевых данных, которой
-- нет в миграциях, — это не «мелкая настройка», а расхождение источника
-- правды; чинится оно ровно одним способом: тем же изменением, записанным в
-- цепочку.
--
-- ПОЧЕМУ ДВА ОТДЕЛЬНЫХ UPDATE И ИМЕННО В ТАКОМ ПОРЯДКЕ. Частичный уникальный
-- индекс generation_strategy_provider_routes_recommended_key разрешает у
-- стратегии ровно один маршрут с recommended = true. Индекс не отложенный,
-- поэтому уникальность проверяется по ходу изменения строк, а не в конце
-- транзакции: попытка снять отметку с одного маршрута и поставить другому
-- одним запросом может упереться в собственный промежуточный результат.
-- Сначала отметка снимается со всех прежних, затем ставится новому — тогда
-- состояния «две отметки одновременно» не существует ни на одно мгновение.
--
-- ПОЧЕМУ RUNWAY ОСТАЁТСЯ ВКЛЮЧЁННЫМ. Pika меняет объект в кадре по фото и
-- срывается там, где нужно переписать сцену целиком. Runway это умеет и стоит
-- дороже — это осознанный дорогой уровень, а не мусор: он остаётся в реестре
-- включённым и выбираемым, просто перестаёт быть выбором по умолчанию.
-- Выключить его значило бы оставить оператора без запасного движка.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ЧИНИТ И ПОЧЕМУ ОБ ЭТОМ НАДО ЗНАТЬ. Диспетчер
-- generation_strategy_route_price (202608180004) для provider = 'runway'
-- перенаправляет запрос в generation_strategy_recipe_price, а та с
-- 202608180006 отдаёт цену ДЕЙСТВУЮЩЕГО маршрута, а не спрошенного. Пока
-- действующим был Runway, разницы не было. С этой миграции спросить цену
-- запасного уровня Runway для «Копии» больше нельзя: ответом придут 47 центов
-- Pika под именем провайдера fal. То же самое уже верно в проде, где маршрут
-- переключили руками, — миграция лишь воспроизводит это состояние, а не
-- создаёт его. Здесь оно не чинится сознательно: правка диспетчера меняет
-- расчёт денег и обязана ехать отдельным файлом со своими проверками.
--
-- ИДЕМПОТЕНТНОСТЬ. Оба запроса написаны как приведение к состоянию, а не как
-- переключение: повторный прогон на уже переключённой базе не находит строк
-- для первого запроса и переписывает второй теми же значениями. Отдельно
-- проставляется enabled: в 202608180002 маршрут Pika заведён выключенным
-- («включим, когда код научится его исполнять»), а действующим считается
-- маршрут, помеченный одновременно рекомендованным И включённым. Ставка Pika
-- сверена там же, при заведении строки, поэтому verified_rate_at здесь не
-- трогается: если его почему-то нет, ограничение
-- generation_strategy_provider_routes_enabled_requires_verified_check обязано
-- уронить миграцию, а не пропустить запуск по неподтверждённой цене.

-- 1. Снять отметку со всех прежних действующих маршрутов «Копии», кроме самой
--    Pika. Условие «кроме Pika» нужно на случай повторного прогона: иначе
--    второй запуск сначала снял бы отметку с уже правильного маршрута.
update content_factory.generation_strategy_provider_routes as route
set recommended = false,
    updated_at = now()
where route.strategy_id = 'viral_product_swap'
  and route.recommended
  and not (
    route.provider = 'fal'
    and route.model_key = 'fal-ai/pika/v2/pikaswaps'
  );

-- 2. Пометить Pika действующим маршрутом и включить его.
update content_factory.generation_strategy_provider_routes as route
set recommended = true,
    enabled = true,
    updated_at = now()
where route.strategy_id = 'viral_product_swap'
  and route.provider = 'fal'
  and route.model_key = 'fal-ai/pika/v2/pikaswaps';

do $product_swap_active_route_pika_verify$
declare
  active_row content_factory.generation_strategy_provider_routes%rowtype;
  runway_row content_factory.generation_strategy_provider_routes%rowtype;
  recommended_count integer;
  snapshot_value jsonb;
  confirmation_value text;
begin
  -- 1. Действующий маршрут — Pika, и он ровно один.
  select route.* into active_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.recommended
    and route.enabled;
  if active_row.id is null
     or active_row.provider <> 'fal'
     or active_row.model_key <> 'fal-ai/pika/v2/pikaswaps'
     or active_row.price_kind <> 'usd_minor_per_run'
     or active_row.price_rate_minor <> 47
     or active_row.pricing_version <> 'fal-usd-per-run-2026-08-18.v1' then
    raise exception using message = 'active_route_is_not_pika';
  end if;

  select count(*) into recommended_count
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.recommended;
  if recommended_count <> 1 then
    raise exception using
      message = 'recommended_route_count_invalid:' || recommended_count::text;
  end if;

  -- 2. Цена «Копии» — 47 центов за ролик, и строка подтверждения называет
  --    провайдера, которым за него платят. Префикс FAL_ проверяется отдельно:
  --    именно он отличает квитанцию нового маршрута от старой Runway-овской, и
  --    именно по нему разбирается журнал списаний.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 10, '720p', 'source', false
  );
  confirmation_value := snapshot_value ->> 'spend_confirmation';
  if snapshot_value is null
     or (snapshot_value ->> 'estimated_cost_minor')::integer <> 47
     or (snapshot_value ->> 'estimated_credits')::integer <> 47
     or snapshot_value ->> 'estimated_cost_usd' <> '0.47'
     or snapshot_value ->> 'provider' <> 'fal'
     or snapshot_value ->> 'pricing_version' <>
        'fal-usd-per-run-2026-08-18.v1'
     or confirmation_value is null
     or left(confirmation_value, 4) <> 'FAL_'
     or confirmation_value <> 'FAL_PRODUCT_SWAP_10S_720P_SILENT_USD_0.47' then
    raise exception using message = 'active_route_price_is_not_fal_47';
  end if;

  -- Цена за ролик не зависит от длительности: пять секунд стоят те же 47
  -- центов. Если бы отметка досталась посекундному Kling, здесь было бы 85.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_product_swap', 5, '720p', 'source', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 47
     or snapshot_value ->> 'provider' <> 'fal' then
    raise exception using message = 'active_route_price_not_per_run';
  end if;

  -- Версия прайса, которую отдают каталог, привязка и квитанция, взята у
  -- действующего маршрута: браузер сверяет её точным совпадением.
  if content_factory_private.generation_strategy_pricing_version(
       'viral_product_swap'
     ) <> 'fal-usd-per-run-2026-08-18.v1' then
    raise exception using message = 'pricing_version_not_switched';
  end if;

  -- 3. Runway остался включённым дорогим уровнем: строка на месте, ступенчатый
  --    прайс цел, отметки «Советуем» на ней больше нет.
  select route.* into runway_row
  from content_factory.generation_strategy_provider_routes as route
  where route.strategy_id = 'viral_product_swap'
    and route.provider = 'runway'
    and route.model_key = 'aleph2';
  if runway_row.id is null
     or runway_row.enabled is not true
     or runway_row.recommended is not false
     or runway_row.price_kind <> 'runway_credit_tiers'
     or runway_row.pricing_version <> 'runway-recipe-credits-2026-08-14.v1' then
    raise exception using message = 'runway_tier_lost';
  end if;
  -- Ступенчатую арифметику Runway тут НЕЛЬЗЯ спросить про «Копию» вживую, и это
  -- не придирка, а прямое следствие переключения. Диспетчер маршрутов
  -- (202608180004) для provider = 'runway' сразу зовёт
  -- generation_strategy_recipe_price, а та с 202608180006 отдаёт цену
  -- ДЕЙСТВУЮЩЕГО маршрута кому угодно. С этой миграции действующий — Pika,
  -- поэтому запрос про Runway вернул бы 47 центов и провайдера fal, и проверка
  -- на 428 упала бы, хотя ступени целы. Сторожем ступеней служит «Аватар»: у
  -- него рекомендованного маршрута нет вовсе, значит формула считается вживую и
  -- даёт 192 + 6 * 36 = 408 по той же таблице, что даёт «Копии» её 428.
  snapshot_value := content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 10, '720p', '720:1280', false
  );
  if (snapshot_value ->> 'estimated_cost_minor')::integer <> 408
     or snapshot_value ->> 'provider' <> 'runway'
     or snapshot_value ->> 'pricing_version' <>
        'runway-recipe-credits-2026-08-14.v1'
     or snapshot_value ->> 'spend_confirmation' <>
        'RUNWAY_PRODUCT_UGC_10S_720P_SILENT_USD_4.08' then
    raise exception using message = 'runway_credit_ladder_drift';
  end if;

  -- 4. Kling из 202608180009 отметку не получил и остался включённым вторым
  --    уровнем: переключение действующего маршрута не должно было его задеть.
  if exists (
    select 1
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = 'viral_product_swap'
      and route.model_key = 'fal-ai/kling-video/o3/pro/video-to-video/edit'
      and (route.recommended or route.enabled is not true)
  ) then
    raise exception using message = 'kling_route_disturbed';
  end if;
end;
$product_swap_active_route_pika_verify$;

commit;
