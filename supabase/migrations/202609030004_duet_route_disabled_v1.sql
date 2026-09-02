begin;
-- 202609030004_duet_route_disabled_v1
--
-- «Дуэт» (viral_avatar_ugc) выводится из витрины: 1 успешный запуск за всю
-- историю ($0.30), после фиксов 202608290001 маршрут не перепроверялся, и
-- решение владельца 03.09 — выключить сразу, без перепроверочного запуска.
-- Рычаг — enabled=false у единственного маршрута heygen/avatar_v3: сервер
-- не подпишет платный старт без включённого маршрута (гвард
-- 202608230010_no_executable_route_no_paid_start_v1), а guided-слой веба
-- показывает на вкладке честный блокер «нет ни одного проверенного
-- маршрута» вместо гашения экрана. Стратегия из каталога НЕ удаляется:
-- контракт каталога требует ровно три стратегии (supabase-api пинит
-- catalog.strategies.length === 3). Обратный путь — enabled=true той же
-- строки после успешного перепроверочного запуска.

update content_factory.generation_strategy_provider_routes
set enabled = false
where strategy_id = 'viral_avatar_ugc'
  and provider = 'heygen'
  and model_key = 'avatar_v3';

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
declare
  enabled_count integer;
  route_count integer;
begin
  select
    count(*) filter (where route.enabled),
    count(*)
  into enabled_count, route_count
  from content_factory.generation_strategy_provider_routes route
  where route.strategy_id = 'viral_avatar_ugc';
  if route_count = 0 then
    raise exception using message = 'duet_route_missing_entirely';
  end if;
  if enabled_count <> 0 then
    raise exception using message = 'duet_route_still_enabled';
  end if;
  -- Денежный гвард на месте: платный старт без включённого маршрута
  -- невозможен. Проверяем ПОВЕДЕНИЕМ: функция гварда из 202608230010
  -- отвечает false для стратегии без единого enabled-маршрута, и замок
  -- по-прежнему вшит в привязку платного запуска.
  if content_factory_private.generation_strategy_executable_route_exists(
       'viral_avatar_ugc'
     ) then
    raise exception using message = 'duet_executable_route_still_exists';
  end if;
  if position('generation_strategy_no_executable_route'
       in pg_get_functiondef(
         'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'::regprocedure
       )) = 0 then
    raise exception using message = 'duet_paid_start_guard_missing';
  end if;
end;
$verify$;

commit;
