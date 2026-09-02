begin;
-- 202609030005_duet_route_reenabled_v1
--
-- Откат 202609030004 по решению владельца (03.09, спустя час): «Дуэт» —
-- одна из трёх стратегий витрины и остаётся живой. Маршрут heygen/avatar_v3
-- включается обратно. Гейт формы (.57) остаётся в коде как страховка: он
-- срабатывает ТОЛЬКО когда реестр отдал маршруты и все выключены, при
-- живом маршруте заглушка не показывается. Остаётся в силе рекомендация
-- аудита: перед продажей «Дуэта» клиентам сделать один перепроверочный
-- запуск (~$0.30) — маршрут не проверялся после фиксов 202608290001.

update content_factory.generation_strategy_provider_routes
set enabled = true
where strategy_id = 'viral_avatar_ugc'
  and provider = 'heygen'
  and model_key = 'avatar_v3';

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $verify$
begin
  if not content_factory_private.generation_strategy_executable_route_exists(
       'viral_avatar_ugc'
     ) then
    raise exception using message = 'duet_route_still_disabled';
  end if;
end;
$verify$;

commit;
