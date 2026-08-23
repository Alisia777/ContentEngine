begin;

-- 202608210005_generation_strategy_avatar_video_to_video_route_v1
--
-- Продолжение 202608210004. «Аватар» переведён с несуществующего рецептного
-- адреса на настоящий video_to_video, и база обязана согласиться с каталогом.
--
-- ПОЧЕМУ ЭТО СРОЧНО. Edge сверяет путь из каталога JS с путём из каталожной
-- политики базы и при расхождении возвращает null, а обработчик отдаёт 503
-- generation_unavailable. Отказ при этом накрывает НЕ «Аватар», а весь экран
-- стратегий: политика читается один раз на все три. То есть рассинхрон этих
-- двух строк гасит и работающую «Копию».
--
-- ЧТО МЕНЯЕТСЯ. Везде, где для viral_avatar_ugc записан '/v1/recipes/product_ugc',
-- ставится '/v1/video_to_video'. Таких мест в живой базе три:
--   * generation_strategy_provider_route_allowed — точный список исполнимых пар;
--   * system_generation_strategy_catalog_policy — витрина возможностей;
--   * system_generation_strategy_provider_policy — политика запуска и её
--     фолбэк «у стратегии нет строк реестра».
--
-- Модель при этом остаётся прежней (gen4_turbo): её значение сверяется с
-- квитанцией и реестром, и менять её здесь значило бы чинить две вещи одной
-- миграцией. Маршруты fal для «Аватара» заводятся отдельно — вместе со строками
-- реестра и сверенными ставками.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Она не включает «Аватар»: строк в реестре
-- маршрутов у него по-прежнему нет, поэтому расчёт готовности в браузере держит
-- модуль заблокированным, а платный старт недостижим. Здесь только устраняется
-- ложь о адресе.

do $avatar_video_to_video$
declare
  target record;
  definition_value text;
  patched_value text;
  fictional constant text := '/v1/recipes/product_ugc';
  real_path constant text := '/v1/video_to_video';
begin
  for target in
    select p.oid::regprocedure::text as signature
    from pg_proc p
    where p.prokind = 'f'
      and pg_get_functiondef(p.oid) like '%' || fictional || '%'
    order by 1
  loop
    definition_value := pg_get_functiondef(target.signature::regprocedure);
    patched_value := replace(definition_value, fictional, real_path);
    if patched_value = definition_value then
      raise exception using message =
        'avatar_path_patch_noop:' || target.signature;
    end if;
    execute patched_value;
  end loop;
end;
$avatar_video_to_video$;

-- Проверка: несуществующего адреса не осталось нигде, настоящий на месте, и
-- пути двух других стратегий не сдвинулись. Последнее важнее первого — правка
-- соседнего рецепта прошла бы молча.
do $avatar_video_to_video_verify$
declare
  leftovers integer;
  allowed_definition text;
begin
  select count(*) into leftovers
  from pg_proc p
  where p.prokind = 'f'
    and pg_get_functiondef(p.oid) like '%/v1/recipes/product_ugc%';
  if leftovers <> 0 then
    raise exception using message =
      'avatar_fictional_path_left:' || leftovers::text;
  end if;

  allowed_definition := pg_get_functiondef(
    'content_factory_private.generation_strategy_provider_route_allowed(text,text,text,text,text,text)'
      ::regprocedure
  );
  if position('/v1/video_to_video' in allowed_definition) = 0 then
    raise exception using message = 'avatar_real_path_missing';
  end if;
  -- «Создание» по-прежнему указывает на свой рецептный адрес: оно не переведено
  -- на правку видео и в этой миграции не участвует.
  if position('/v1/recipes/product_ad' in allowed_definition) = 0 then
    raise exception using message = 'rebuild_path_drifted';
  end if;
  -- Точный список пар обязан продолжать пускать три движка «Копии».
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       'fal-ai/pika/v2/pikaswaps', 'fal_request',
       'fal-usd-per-run-2026-08-18.v1'
     ) then
    raise exception using message = 'product_swap_pika_route_lost';
  end if;
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_product_swap', 'runway', 'aleph2', '/v1/video_to_video',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'product_swap_runway_route_lost';
  end if;
  -- И «Аватар» теперь исполним по настоящему адресу, а по выдуманному — нет.
  if not content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'runway', 'gen4_turbo', '/v1/video_to_video',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'avatar_real_route_not_allowed';
  end if;
  if content_factory_private.generation_strategy_provider_route_allowed(
       'viral_avatar_ugc', 'runway', 'gen4_turbo', '/v1/recipes/product_ugc',
       'runway_task', 'runway-recipe-credits-2026-08-14.v1'
     ) then
    raise exception using message = 'avatar_fictional_route_still_allowed';
  end if;
end;
$avatar_video_to_video_verify$;

commit;
