begin;

-- 202608230010_no_executable_route_no_paid_start_v1
--
-- Нет исполнимого маршрута — нет платного старта. Замок на сервере.
--
-- ЧТО НАБЛЮДАЛОСЬ. Стратегия «Создание» (viral_rebuild) не имеет НИ ОДНОЙ
-- строки в реестре маршрутов. При этом её платный запуск сервером не
-- запирается: три независимых отката говорят «да».
--
--   1. Цена: `generation_strategy_recipe_price` делает
--      `provider_value := coalesce(route_row.provider, 'runway')` и возвращает
--      рунвеевскую лестницу кредитов.
--   2. Привязка: ветка «нет строк реестра → каталог» отдаёт эту цену как
--      действительную.
--   3. Готовность: такая же ветка стоит в `system_record_generation_strategy_readiness`.
--
-- Наряд создаётся, деньги резервируются, запрос уходит на
-- `/v1/recipes/product_ad` — и получает 404, потому что эндпоинтов
-- `/v1/recipes/*` У RUNWAY НЕ СУЩЕСТВУЕТ. Это проверено и записано дословно в
-- миграции 202608170006: живой фильтр Request History знает
-- text_to_image, text_to_video, image_to_video, video_to_video,
-- character_performance, text_to_speech, organization — и всё.
--
-- 404 стоит в списке детерминированных отказов, то есть деньги списываются, а
-- ролика нет. Единственное, что стоит между оператором и этим исходом сегодня,
-- — булев флаг `REBUILD_PAID_START_CLOSED` в браузере (`web/app/app.js`), и
-- комментарий рядом с ним сам называет себя «временный клиентский стоп-кран, а
-- не архитектура».
--
-- ПОЧЕМУ ЗАМОК ПО МАРШРУТУ, А НЕ ПО ИМЕНИ СТРАТЕГИИ. Запретить `viral_rebuild`
-- по имени значило бы завести четвёртое место, где перечислены стратегии, и
-- отпирать «Дуэт» отдельной правкой, когда его строку включат. Признак
-- «существует включённая и разрешённая политикой строка реестра» отвечает на
-- тот самый вопрос, который на самом деле задаётся: есть ли кому платить и
-- куда отправлять. «Дуэт» пройдёт замок в ту же секунду, когда его строку
-- включат, — без единой правки кода.
--
-- ПРЕДИКАТ ВЫНЕСЕН В ФУНКЦИЮ. Не ради красоты: он нужен замку, он же нужен
-- проверке готовности и политике провайдера, и разойтись эти три места не
-- должны. Заодно предикат становится проверяемым вызовом, а не текстом.
--
-- ЧЕГО ЭТА МИГРАЦИЯ НЕ ДЕЛАЕТ. Не трогает `generation_strategy_recipe_price`:
-- каталог рецептов остаётся справочником и продолжает отвечать. Меняется
-- только то, что на его ответ больше никто не опирается как на цену запуска.
-- Браузерный стоп-кран снимается ОТДЕЛЬНО и ПОСЛЕ этой миграции — снять его
-- раньше значило бы открыть ровно ту дыру, которую он затыкает.

-- 1. Предикат: есть ли у стратегии исполнимый маршрут.
create or replace function
  content_factory_private.generation_strategy_executable_route_exists(
    p_strategy_id text
  ) returns boolean
language sql
stable
security definer
set search_path to ''
as $function$
  select exists (
    select 1
    from content_factory.generation_strategy_provider_routes as route
    where route.strategy_id = p_strategy_id
      and route.enabled
      and content_factory_private.generation_strategy_provider_route_allowed(
        route.strategy_id,
        route.provider,
        route.model_key,
        route.provider_path,
        route.poll_kind,
        route.pricing_version
      )
  );
$function$;

revoke all on function
  content_factory_private.generation_strategy_executable_route_exists(text)
  from public, anon, authenticated;

-- 2. Замок в привязке — раньше цены, раньше наряда, раньше денег.
do $bind_route_lock$
declare
  source_text text;
  patched_text text;
  anchor text;
begin
  source_text := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  if position('generation_strategy_no_executable_route' in source_text) > 0 then
    return;
  end if;
  patched_text := source_text;

  -- 2.1. Сам замок. Ставится сразу после расчёта цены и ДО проверки её
  --      наличия: цена считается чистыми функциями без побочных действий, а
  --      денег здесь ещё никто не резервировал — резерв и наряд идут дальше.
  --
  --      ЯКОРЬ — ТОЛЬКО КОД, БЕЗ КОММЕНТАРИЯ. Прежний якорь включал русский
  --      комментарий ветки движка, а в проде комментарии тел функций,
  --      применённых 19–21.08 через MCP, искажены до «?» — такой якорь там
  --      не находится никогда. Голая строка `if p_payload ? 'engine' then`
  --      встречается дважды, поэтому якорь взят из единственной в теле
  --      проверки «цена отсутствует».
  anchor := E'  if price_value is null then\n'
         || E'    raise exception using errcode = ''22023'',\n'
         || E'      message = ''generation_strategy_catalog_selection_invalid'';';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'bind_lock_anchor_engine_branch';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'  -- ЗАМОК ИСПОЛНИМОГО МАРШРУТА.\n'
      || E'  --\n'
      || E'  -- Стратегия, у которой нет ни одной включённой и разрешённой строки\n'
      || E'  -- реестра, не может быть запущена: платить некому и отправлять\n'
      || E'  -- некуда. Прежде такой запуск доходил до 404 у провайдера — то есть\n'
      || E'  -- ПОСЛЕ резерва денег, с детерминированным отказом и повисшей\n'
      || E'  -- бронью.\n'
      || E'  --\n'
      || E'  -- Признак маршрутный, а не именной: «Дуэт» пройдёт здесь в ту же\n'
      || E'  -- секунду, когда его строку включат, и править для этого нечего.\n'
      || E'  if not content_factory_private\n'
      || E'       .generation_strategy_executable_route_exists(strategy_id_value)\n'
      || E'  then\n'
      || E'    raise exception using errcode = ''42501'',\n'
      || E'      message = ''generation_strategy_no_executable_route'';\n'
      || E'  end if;\n'
      || E'\n'
      || anchor
  );

  -- 2.2. Откат на каталог рецептов снимается. Он и есть та ложь, из-за которой
  --      «Создание» оценивалось по Runway: 344 цента за восемь секунд по
  --      адресу, которого не существует.
  anchor := E'    -- Строк реестра нет — стратегия живёт по каталогу, как жила.\n'
         || E'    -- Строки есть, но включённой рекомендованной среди них нет — цена\n'
         || E'    -- остаётся NULL, и ниже это станет громким отказом до денег.\n'
         || E'    if not exists (\n'
         || E'      select 1\n'
         || E'      from content_factory.generation_strategy_provider_routes as route\n'
         || E'      where route.strategy_id = strategy_id_value\n'
         || E'    ) then\n'
         || E'      price_value := content_factory_private.generation_strategy_recipe_price(\n'
         || E'        strategy_id_value, duration_seconds_value, resolution_value,\n'
         || E'        ratio_value, audio_value\n'
         || E'      );\n'
         || E'    end if;\n';
  if (length(patched_text) - length(replace(patched_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'bind_lock_anchor_catalog_fallback';
  end if;
  patched_text := replace(
    patched_text,
    anchor,
    E'    -- Отката на каталог рецептов здесь БОЛЬШЕ НЕТ. Каталог остаётся\n'
      || E'    -- справочником и продолжает отвечать, но ценой запуска его ответ\n'
      || E'    -- быть не может: у стратегии без реестра он называет провайдера\n'
      || E'    -- ''runway'' простым coalesce, и запуск уходил бы по цене движка,\n'
      || E'    -- которого никто не вызовет.\n'
      || E'    --\n'
      || E'    -- Стратегия без включённой рекомендованной строки сюда уже не\n'
      || E'    -- доходит: её отвергает замок исполнимого маршрута выше. Если же\n'
      || E'    -- строки есть, а рекомендованной среди включённых нет — цена\n'
      || E'    -- остаётся NULL и становится громким отказом ниже.\n'
  );

  if patched_text = source_text then
    raise exception using message = 'bind_lock_unchanged';
  end if;
  execute patched_text;
end;
$bind_route_lock$;

-- 3. Тот же откат снимается в проверке готовности: две функции обязаны считать
--    цену одинаково, иначе готовность подтвердит то, чего привязка не давала.
do $readiness_catalog_fallback$
declare
  source_text text;
  patched_text text;
  anchor constant text :=
    E'    case when not exists (\n'
    || E'      select 1\n'
    || E'      from content_factory.generation_strategy_provider_routes as route\n'
    || E'      where route.strategy_id = binding_row.strategy_id\n'
    || E'    ) then content_factory_private.generation_strategy_recipe_price(\n'
    || E'      binding_row.strategy_id,\n'
    || E'      (selection_row.selection_snapshot ->> ''duration_seconds'')::integer,\n'
    || E'      selection_row.price_snapshot ->> ''resolution'',\n'
    || E'      selection_row.price_snapshot ->> ''ratio'',\n'
    || E'      (selection_row.selection_snapshot ->> ''audio'')::boolean\n'
    || E'    ) else null end';
begin
  source_text := pg_get_functiondef(
    'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
  );
  if position(anchor in source_text) = 0 then
    -- Повторный прогон: откат уже снят.
    return;
  end if;
  if (length(source_text) - length(replace(source_text, anchor, ''))) /
     length(anchor) <> 1 then
    raise exception using message = 'readiness_catalog_fallback_anchor';
  end if;
  patched_text := replace(
    source_text,
    anchor,
    E'    -- Каталог рецептов здесь больше не подставляется: цена запуска\n'
      || E'    -- приходит только из реестра маршрутов, и привязка считает её так\n'
      || E'    -- же. Расхождение этих двух функций означало бы, что готовность\n'
      || E'    -- подтверждает сумму, которой привязка не называла.\n'
      || E'    null'
  );
  execute patched_text;
end;
$readiness_catalog_fallback$;

-- ПРОВЕРКА ПОВЕДЕНИЕМ.
do $route_lock_verify$
declare
  duet_before boolean;
  duet_inside boolean;
  rebuild_exists boolean;
  copy_exists boolean;
  bind_body text;
  readiness_body text;
begin
  -- 1. Предикат отвечает по фактам реестра, а не по имени стратегии.
  copy_exists := content_factory_private
    .generation_strategy_executable_route_exists('viral_product_swap');
  rebuild_exists := content_factory_private
    .generation_strategy_executable_route_exists('viral_rebuild');
  duet_before := content_factory_private
    .generation_strategy_executable_route_exists('viral_avatar_ugc');

  if copy_exists is not true then
    raise exception using message = 'copy_lost_its_executable_route';
  end if;
  if rebuild_exists is not false then
    raise exception using message = 'rebuild_unexpectedly_has_a_route';
  end if;
  if duet_before is not false then
    raise exception using message = 'duet_route_enabled_too_early';
  end if;
  if content_factory_private
       .generation_strategy_executable_route_exists('no_such_strategy')
     is not false then
    raise exception using message = 'unknown_strategy_passed_the_lock';
  end if;

  -- 2. Замок ОТПИРАЕТСЯ включением строки, а не правкой кода. Проверяется
  --    вложенным блоком, который затем намеренно прерывается: строки
  --    откатываются, значения переменных остаются (переменные PL/pgSQL не
  --    транзакционны, и это здесь используется сознательно).
  begin
    update content_factory.generation_strategy_provider_routes
      set enabled = true
    where strategy_id = 'viral_avatar_ugc';
    duet_inside := content_factory_private
      .generation_strategy_executable_route_exists('viral_avatar_ugc');
    raise exception using errcode = '40000', message = 'route_lock_probe';
  exception when sqlstate '40000' then
    null;
  end;
  if duet_inside is not true then
    raise exception using message = 'lock_does_not_open_on_enabled_route';
  end if;

  -- Проба обязана была откатиться. Если это утверждение однажды упадёт, значит
  -- маршрут дуэта оказался включён файлом, который этого не обещал.
  if content_factory_private
       .generation_strategy_executable_route_exists('viral_avatar_ugc')
     is not false then
    raise exception using message = 'duet_route_left_enabled_by_probe';
  end if;

  -- 3. Замок стоит в привязке, и откатов на каталог больше нет ни в одной из
  --    двух функций, считающих цену.
  bind_body := pg_get_functiondef(
    'public.system_resolve_and_bind_generation_strategy_pre_execution_v1(jsonb)'
      ::regprocedure
  );
  readiness_body := pg_get_functiondef(
    'public.system_record_generation_strategy_readiness(jsonb)'::regprocedure
  );
  if position('generation_strategy_no_executable_route' in bind_body) = 0 then
    raise exception using message = 'bind_lock_missing';
  end if;
  if position('generation_strategy_recipe_price' in bind_body) > 0 then
    raise exception using message = 'bind_still_prices_from_catalog';
  end if;
  if position('generation_strategy_recipe_price' in readiness_body) > 0 then
    raise exception using message = 'readiness_still_prices_from_catalog';
  end if;

  -- 4. Каталог рецептов НЕ сломан: он остаётся справочником и продолжает
  --    отвечать. Изменилось только то, что на его ответ больше не опираются
  --    как на цену запуска. Если он однажды замолчит сам, это надо заметить.
  if content_factory_private.generation_strategy_recipe_price(
       'viral_rebuild', 8, '720p', '720:1280', true
     ) is null then
    raise exception using message = 'recipe_catalog_went_silent';
  end if;

  -- 5. «Копия» не тронута: цена её рекомендованного маршрута на месте.
  if content_factory_private.generation_strategy_route_price(
       'viral_product_swap', 'fal', 'fal-ai/pika/v2/pikaswaps',
       8, '720p', 'source', true
     ) ->> 'spend_confirmation'
     is distinct from 'FAL_PRODUCT_SWAP_8S_720P_AUDIO_USD_0.47' then
    raise exception using message = 'copy_route_price_changed';
  end if;
end;
$route_lock_verify$;

commit;
