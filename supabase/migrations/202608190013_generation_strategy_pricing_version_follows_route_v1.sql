begin;

-- 202608190013_generation_strategy_pricing_version_follows_route_v1
--
-- Версия прайса следует за выбранным движком, а не за «рекомендованным».
--
-- Обёртка begin/commit открывает файл первой строкой, а не после шапки:
-- загрузчик миграций (scripts/deploy_supabase_management_api.py) сверяет её
-- регулярным выражением от начала файла, и комментарий перед BEGIN отвергает
-- вместе с ним всю цепочку. Поэтому «почему» живёт внутри транзакции.
--
-- ЧТО НАБЛЮДАЛОСЬ. Выбор второго движка («Kling O3 Pro») на том же исходнике
-- не доходил до запуска: портал показывал «Сервер не подтвердил точную
-- привязку исходников». При этом сама привязка на сервере создавалась и цену
-- считала верно — 5 секунд по посекундной ставке, 85 центов.
--
-- ПОЧЕМУ. Цена и версия прайса разъезжались. Снимок цены собирает
-- generation_strategy_route_price по маршруту выбранного движка и кладёт внутрь
-- pricing_version этого маршрута (у Kling — посекундный). А поле
-- pricing_version и в ответе, и в сохранённой строке бралось из
-- generation_strategy_pricing_version(strategy_id) — версии РЕКОМЕНДОВАННОГО
-- маршрута (у «Копии» это Pika, цена за ролик целиком). Получалась привязка,
-- где цена посекундная, а версия прайса — за ролик. Браузер сверяет пару и
-- отвергает такую привязку — и правильно делает: это два разных прайса в одной
-- записи.
--
-- И ЭТО НЕ ТОЛЬКО ПРИВЯЗКА. Тем же способом версия прайса пришпилена в допуске
-- к запуску: system_generation_strategy_provider_policy ищет квитанцию
-- готовности с условием «pricing_version равен рекомендованному». Квитанция
-- второго движка под это условие не подходит, то есть даже исправленная
-- привязка не дошла бы до старта. Поэтому обе точки правятся одной миграцией:
-- починить одну и оставить другую значит поменять один отказ на другой.
--
-- ЧТО ИМЕННО ПРАВИТСЯ. Версия прайса берётся из снимка цены — из того самого,
-- по которому считаются деньги, — и только если снимок её не несёт, остаётся
-- прежнее значение по умолчанию. В допуске условие «равен рекомендованному»
-- заменяется на «принадлежит включённому маршруту этой стратегии»: строгость
-- сохраняется (произвольную версию квитанция не пронесёт), но перестаёт
-- исключать второй движок.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Не меняет ни одной цены и ни одного маршрута.
-- Для запроса без выбора движка поведение дословно прежнее: снимок цены
-- рекомендованного маршрута несёт ровно ту версию, которую возвращает
-- generation_strategy_pricing_version, — coalesce выбирает то же значение.

do $pricing_version_follows_route$
declare
  definition_value text;
  patched_value text;
  anchor text;
  replacement text;
begin
  -- 1. Привязка: ответ и сохранённая строка.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_resolve_and_bind_generation_strategy';
  if definition_value is null then
    raise exception using message = 'bind_low_level_missing';
  end if;

  if position($f$price_value ->> 'pricing_version'$f$ in definition_value) = 0
  then
    anchor := $f$    'pricing_version',
    content_factory_private.generation_strategy_pricing_version(
      strategy_id_value
    ),$f$;
    replacement := $f$    'pricing_version',
    coalesce(
      price_value ->> 'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      )
    ),$f$;
    if (length(definition_value) - length(replace(definition_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'bind_low_level_response_anchor_invalid';
    end if;
    patched_value := replace(definition_value, anchor, replacement);

    anchor := $f$    '2026-06',
    content_factory_private.generation_strategy_pricing_version(
      strategy_id_value
    ), selection_value,$f$;
    replacement := $f$    '2026-06',
    coalesce(
      price_value ->> 'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      )
    ), selection_value,$f$;
    if (length(patched_value) - length(replace(patched_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'bind_low_level_insert_anchor_invalid';
    end if;
    patched_value := replace(patched_value, anchor, replacement);
    execute patched_value;
  end if;

  -- 2. Привязка верхнего уровня: ответ оператору.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null then
    raise exception using message = 'bind_pre_execution_missing';
  end if;

  if position($f$price_value ->> 'pricing_version'$f$ in definition_value) = 0
  then
    anchor := $f$      'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      ),$f$;
    replacement := $f$      'pricing_version',
      coalesce(
        price_value ->> 'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )
      ),$f$;
    if (length(definition_value) - length(replace(definition_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'bind_pre_execution_anchor_invalid';
    end if;
    execute replace(definition_value, anchor, replacement);
  end if;

  -- 3. Допуск к запуску: поиск квитанции и два места в ответе.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_provider_policy';
  if definition_value is null then
    raise exception using message = 'strategy_provider_policy_missing';
  end if;

  if position('route.pricing_version' in definition_value) = 0 then
    anchor := $f$      and receipt.pricing_version =
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )$f$;
    replacement := $f$      and receipt.pricing_version in (
        select route.pricing_version
        from content_factory.generation_strategy_provider_routes route
        where route.strategy_id = strategy_id_value
          and route.enabled
      )$f$;
    if (length(definition_value) - length(replace(definition_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'strategy_policy_receipt_anchor_invalid';
    end if;
    patched_value := replace(definition_value, anchor, replacement);

    anchor := $f$        'pricing_version',
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )$f$;
    replacement := $f$        'pricing_version',
        coalesce(
          receipt_row.pricing_version,
          content_factory_private.generation_strategy_pricing_version(
            strategy_id_value
          )
        )$f$;
    if (length(patched_value) - length(replace(patched_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'strategy_policy_launch_anchor_invalid';
    end if;
    patched_value := replace(patched_value, anchor, replacement);

    anchor := $f$      'pricing_version',
      content_factory_private.generation_strategy_pricing_version(
        strategy_id_value
      )$f$;
    replacement := $f$      'pricing_version',
      coalesce(
        receipt_row.pricing_version,
        content_factory_private.generation_strategy_pricing_version(
          strategy_id_value
        )
      )$f$;
    if (length(patched_value) - length(replace(patched_value, anchor, '')))
       / length(anchor) <> 1 then
      raise exception using message = 'strategy_policy_context_anchor_invalid';
    end if;
    patched_value := replace(patched_value, anchor, replacement);
    execute patched_value;
  end if;
end;
$pricing_version_follows_route$;

-- Права после create or replace сохраняются, но повторяются явно.
revoke all on function
  public.system_resolve_and_bind_generation_strategy(jsonb)
  from public, anon, authenticated;
grant execute on function
  public.system_resolve_and_bind_generation_strategy(jsonb)
  to service_role;
revoke all on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)
  to service_role;

do $pricing_version_follows_route_verify$
declare
  definition_value text;
begin
  -- 1. Обе привязки берут версию из снимка цены.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_resolve_and_bind_generation_strategy';
  if definition_value is null
     or (length(definition_value)
         - length(replace(
             definition_value, $f$price_value ->> 'pricing_version'$f$, ''
           )))
        / length($f$price_value ->> 'pricing_version'$f$) <> 2 then
    raise exception using message = 'bind_low_level_verify_failed';
  end if;
  -- И по-прежнему умеют отказывать: сверка снимка цены на месте.
  if position('generation_strategy_binding_selection_invalid'
       in definition_value) = 0
     or position('generation_strategy_binding_selection_conflict'
       in definition_value) = 0 then
    raise exception using message = 'bind_low_level_guard_lost';
  end if;

  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname =
      'system_resolve_and_bind_generation_strategy_pre_execution_v1';
  if definition_value is null
     or position($f$price_value ->> 'pricing_version'$f$ in definition_value) = 0
     or position('engine_choice_v1' in definition_value) = 0 then
    raise exception using message = 'bind_pre_execution_verify_failed';
  end if;

  -- 2. Допуск ищет квитанцию по включённым маршрутам и не потерял проверок.
  select pg_get_functiondef(p.oid) into definition_value
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'public'
    and p.proname = 'system_generation_strategy_provider_policy';
  if definition_value is null
     or position('route.pricing_version' in definition_value) = 0
     or position('receipt.ready' in definition_value) = 0
     or position('receipt.expires_at > statement_timestamp()'
       in definition_value) = 0
     or position('generation_strategy_selection_current'
       in definition_value) = 0 then
    raise exception using message = 'strategy_policy_verify_failed';
  end if;

  -- 3. Ни одной пришпиленной к рекомендованному маршруту версии не осталось
  --    там, где решается судьба квитанции.
  if position($f$receipt.pricing_version =$f$ in definition_value) > 0 then
    raise exception using message = 'strategy_policy_pin_left';
  end if;
end;
$pricing_version_follows_route_verify$;

commit;
